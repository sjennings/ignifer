"""Tests for OpenSanctions adapter."""

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from ignifer.adapters.base import AdapterParseError, AdapterTimeoutError
from ignifer.adapters.opensanctions import OpenSanctionsAdapter
from ignifer.cache import CacheEntry
from ignifer.models import ConfidenceLevel, QueryParams, QualityTier, ResultStatus


# Load fixture once at module level
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


class TestOpenSanctionsAdapterProperties:
    """Tests for OpenSanctionsAdapter class properties."""

    def test_source_name(self) -> None:
        """Source name is 'opensanctions'."""
        adapter = OpenSanctionsAdapter()
        assert adapter.source_name == "opensanctions"

    def test_base_quality_tier_is_high(self) -> None:
        """Base quality tier is HIGH (official sanctions data)."""
        adapter = OpenSanctionsAdapter()
        assert adapter.base_quality_tier == QualityTier.HIGH

    def test_base_url_is_opensanctions(self) -> None:
        """Base URL points to OpenSanctions API."""
        adapter = OpenSanctionsAdapter()
        assert adapter.BASE_URL == "https://api.opensanctions.org"


class TestOpenSanctionsAdapterLazyClient:
    """Tests for lazy HTTP client initialization."""

    @pytest.mark.asyncio
    async def test_get_client_creates_client(self) -> None:
        """_get_client creates httpx.AsyncClient lazily."""
        adapter = OpenSanctionsAdapter()
        assert adapter._client is None

        client = await adapter._get_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        assert adapter._client is client

        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_client_returns_same_client(self) -> None:
        """_get_client returns the same client on subsequent calls."""
        adapter = OpenSanctionsAdapter()

        client1 = await adapter._get_client()
        client2 = await adapter._get_client()
        assert client1 is client2

        await adapter.close()


class TestOpenSanctionsAdapterHelpers:
    """Tests for helper methods."""

    def test_map_score_to_confidence_very_likely(self) -> None:
        """Score >= 0.9 maps to VERY_LIKELY."""
        adapter = OpenSanctionsAdapter()
        assert adapter._map_score_to_confidence(0.9) == ConfidenceLevel.VERY_LIKELY
        assert adapter._map_score_to_confidence(0.98) == ConfidenceLevel.VERY_LIKELY
        assert adapter._map_score_to_confidence(1.0) == ConfidenceLevel.VERY_LIKELY

    def test_map_score_to_confidence_likely(self) -> None:
        """Score >= 0.7 and < 0.9 maps to LIKELY."""
        adapter = OpenSanctionsAdapter()
        assert adapter._map_score_to_confidence(0.7) == ConfidenceLevel.LIKELY
        assert adapter._map_score_to_confidence(0.85) == ConfidenceLevel.LIKELY
        assert adapter._map_score_to_confidence(0.89) == ConfidenceLevel.LIKELY

    def test_map_score_to_confidence_even_chance(self) -> None:
        """Score >= 0.5 and < 0.7 maps to EVEN_CHANCE."""
        adapter = OpenSanctionsAdapter()
        assert adapter._map_score_to_confidence(0.5) == ConfidenceLevel.EVEN_CHANCE
        assert adapter._map_score_to_confidence(0.6) == ConfidenceLevel.EVEN_CHANCE
        assert adapter._map_score_to_confidence(0.69) == ConfidenceLevel.EVEN_CHANCE

    def test_map_score_to_confidence_unlikely(self) -> None:
        """Score < 0.5 maps to UNLIKELY."""
        adapter = OpenSanctionsAdapter()
        assert adapter._map_score_to_confidence(0.4) == ConfidenceLevel.UNLIKELY
        assert adapter._map_score_to_confidence(0.2) == ConfidenceLevel.UNLIKELY
        assert adapter._map_score_to_confidence(0.0) == ConfidenceLevel.UNLIKELY

    def test_is_pep_only_true(self) -> None:
        """_is_pep_only returns True for PEP without sanctions."""
        adapter = OpenSanctionsAdapter()
        assert adapter._is_pep_only(["role.pep"]) is True
        assert adapter._is_pep_only(["role.pep", "poi"]) is True

    def test_is_pep_only_false_when_sanctioned(self) -> None:
        """_is_pep_only returns False when also sanctioned."""
        adapter = OpenSanctionsAdapter()
        assert adapter._is_pep_only(["role.pep", "sanction"]) is False
        assert adapter._is_pep_only(["sanction"]) is False

    def test_is_pep_only_false_when_not_pep(self) -> None:
        """_is_pep_only returns False when not a PEP."""
        adapter = OpenSanctionsAdapter()
        assert adapter._is_pep_only([]) is False
        assert adapter._is_pep_only(["poi"]) is False

    def test_normalize_entity_basic(self) -> None:
        """_normalize_entity extracts basic fields."""
        adapter = OpenSanctionsAdapter()
        entity = {
            "id": "NK-abc123",
            "caption": "Test Entity",
            "schema": "Person",
            "properties": {
                "name": ["Test Name"],
                "alias": ["Alias 1"],
                "birthDate": ["1990-01-01"],
                "nationality": ["us"],
                "position": ["CEO"],
                "topics": ["sanction"],
            },
            "datasets": ["us_ofac_sdn"],
            "referents": ["ofac-123"],
            "first_seen": "2020-01-01",
            "last_seen": "2024-01-01",
        }

        result = adapter._normalize_entity(entity, score=0.95)

        assert result["entity_id"] == "NK-abc123"
        assert result["caption"] == "Test Entity"
        assert result["schema"] == "Person"
        assert result["name"] == "Test Name"
        assert result["aliases"] == "Alias 1"
        assert result["birth_date"] == "1990-01-01"
        assert result["nationality"] == "us"
        assert result["position"] == "CEO"
        assert result["sanctions_lists"] == "us_ofac_sdn"
        assert result["sanctions_count"] == 1
        assert result["is_sanctioned"] is True
        assert result["is_pep"] is False
        assert result["first_seen"] == "2020-01-01"
        assert result["last_seen"] == "2024-01-01"
        assert result["match_score"] == 0.95
        assert result["match_confidence"] == "VERY_LIKELY"
        assert result["referents"] == "ofac-123"
        assert result["referents_count"] == 1

    def test_normalize_entity_pep_only(self) -> None:
        """_normalize_entity adds PEP-specific fields for non-sanctioned PEPs."""
        adapter = OpenSanctionsAdapter()
        entity = {
            "id": "pep-123",
            "caption": "Foreign Minister",
            "schema": "Person",
            "properties": {
                "name": ["Minister Name"],
                "position": ["Foreign Minister"],
                "topics": ["role.pep"],
            },
            "datasets": ["country_pep"],
            "referents": [],
        }

        result = adapter._normalize_entity(entity)

        assert result["is_pep"] is True
        assert result["is_sanctioned"] is False
        assert result["pep_status"] == "PEP - NOT CURRENTLY SANCTIONED"
        assert result["due_diligence_note"] == "Enhanced due diligence recommended for PEPs"


class TestOpenSanctionsAdapterQuery:
    """Tests for entity search via query()."""

    @pytest.mark.asyncio
    async def test_query_success(self, httpx_mock) -> None:
        """Successful query returns normalized search results."""
        fixture = load_fixture("opensanctions_entity.json")

        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/match.*"),
            json=fixture,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.query(QueryParams(query="Viktor Vekselberg"))

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 1
        assert result.results[0]["entity_id"] == "NK-abc123"
        assert result.results[0]["caption"] == "Viktor Vekselberg"
        assert result.results[0]["is_sanctioned"] is True
        assert result.sources[0].source == "opensanctions"
        assert result.sources[0].quality == QualityTier.HIGH

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_with_high_confidence_match(self, httpx_mock) -> None:
        """High-score match returns VERY_LIKELY confidence."""
        fixture = load_fixture("opensanctions_entity.json")

        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/match.*"),
            json=fixture,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.query(QueryParams(query="Viktor Vekselberg"))

        assert result.status == ResultStatus.SUCCESS
        assert result.results[0]["match_score"] == 0.98
        assert result.results[0]["match_confidence"] == "VERY_LIKELY"
        assert result.sources[0].confidence == ConfidenceLevel.VERY_LIKELY

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_with_medium_confidence_match(self, httpx_mock) -> None:
        """Medium-score match returns LIKELY confidence."""
        fixture = {
            "responses": {
                "q1": {
                    "query": {},
                    "total": {"value": 1, "relation": "eq"},
                    "results": [
                        {
                            "id": "test-123",
                            "caption": "Test Entity",
                            "schema": "Person",
                            "properties": {
                                "name": ["Test"],
                                "topics": ["sanction"],
                            },
                            "datasets": ["us_ofac_sdn"],
                            "referents": [],
                            "score": 0.75,
                        }
                    ],
                }
            }
        }

        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/match.*"),
            json=fixture,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.query(QueryParams(query="Test Entity"))

        assert result.status == ResultStatus.SUCCESS
        assert result.results[0]["match_confidence"] == "LIKELY"
        assert result.sources[0].confidence == ConfidenceLevel.LIKELY

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_empty_string_returns_no_data(self) -> None:
        """Empty query string returns NO_DATA status."""
        adapter = OpenSanctionsAdapter()
        result = await adapter.query(QueryParams(query="   "))

        assert result.status == ResultStatus.NO_DATA
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_query_no_match(self, httpx_mock) -> None:
        """No matches returns NO_DATA status with comprehensive note."""
        fixture = load_fixture("opensanctions_no_match.json")

        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/match.*"),
            json=fixture,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.query(QueryParams(query="John Doe Nonexistent"))

        assert result.status == ResultStatus.NO_DATA
        assert result.error is not None
        assert "No matches found" in result.error
        assert "comprehensive" in result.error.lower()
        assert "aliases" in result.error.lower()

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_rate_limited(self, httpx_mock) -> None:
        """429 response returns RATE_LIMITED status."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org.*"),
            status_code=429,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.query(QueryParams(query="Test"))

        assert result.status == ResultStatus.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_query_timeout_raises_error(self, httpx_mock) -> None:
        """Timeout raises AdapterTimeoutError."""
        httpx_mock.add_exception(
            httpx.TimeoutException("Timeout"),
            url=re.compile(r".*api\.opensanctions\.org.*"),
        )

        adapter = OpenSanctionsAdapter()
        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.query(QueryParams(query="Test"))

        assert exc_info.value.source_name == "opensanctions"

    @pytest.mark.asyncio
    async def test_query_malformed_json_raises_parse_error(self, httpx_mock) -> None:
        """Malformed JSON response raises AdapterParseError."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org.*"),
            content=b"not valid json {{{",
            status_code=200,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        with pytest.raises(AdapterParseError) as exc_info:
            await adapter.query(QueryParams(query="Test"))

        assert "Invalid JSON response" in str(exc_info.value)


class TestOpenSanctionsAdapterSearchEntity:
    """Tests for search_entity method."""

    @pytest.mark.asyncio
    async def test_search_entity_success(self, httpx_mock) -> None:
        """search_entity() returns normalized results."""
        fixture = load_fixture("opensanctions_entity.json")

        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/match.*"),
            json=fixture,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.search_entity("Viktor Vekselberg")

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 1
        assert result.results[0]["entity_id"] == "NK-abc123"

        await adapter.close()


class TestOpenSanctionsAdapterCheckSanctions:
    """Tests for check_sanctions method (entity by ID)."""

    @pytest.mark.asyncio
    async def test_check_sanctions_success(self, httpx_mock) -> None:
        """check_sanctions() returns detailed entity info."""
        entity_fixture = {
            "id": "NK-abc123",
            "caption": "Viktor Vekselberg",
            "schema": "Person",
            "properties": {
                "name": ["Viktor Vekselberg"],
                "alias": ["Виктор Вексельберг"],
                "birthDate": ["1957-04-14"],
                "nationality": ["ru"],
                "position": ["Chairman"],
                "topics": ["sanction"],
            },
            "datasets": ["us_ofac_sdn", "eu_fsf"],
            "referents": ["ofac-12345"],
            "first_seen": "2018-04-06",
            "last_seen": "2024-01-15",
        }

        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/entities/NK-abc123"),
            json=entity_fixture,
            method="GET",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.check_sanctions("NK-abc123")

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 1
        assert result.results[0]["entity_id"] == "NK-abc123"
        assert result.results[0]["is_sanctioned"] is True
        assert result.sources[0].confidence == ConfidenceLevel.ALMOST_CERTAIN

        await adapter.close()

    @pytest.mark.asyncio
    async def test_check_sanctions_not_found(self, httpx_mock) -> None:
        """check_sanctions() returns NO_DATA for unknown ID."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/entities.*"),
            status_code=404,
            method="GET",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.check_sanctions("unknown-id")

        assert result.status == ResultStatus.NO_DATA
        assert "not found" in result.error.lower()

        await adapter.close()

    @pytest.mark.asyncio
    async def test_check_sanctions_empty_id(self) -> None:
        """check_sanctions() returns NO_DATA for empty ID."""
        adapter = OpenSanctionsAdapter()
        result = await adapter.check_sanctions("   ")

        assert result.status == ResultStatus.NO_DATA
        assert "empty" in result.error.lower()


class TestOpenSanctionsAdapterMultipleSanctionsLists:
    """Tests for multiple sanctions lists handling."""

    @pytest.mark.asyncio
    async def test_multiple_sanctions_lists(self, httpx_mock) -> None:
        """Entity on multiple lists returns all lists."""
        fixture = load_fixture("opensanctions_entity.json")

        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/match.*"),
            json=fixture,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.query(QueryParams(query="Viktor Vekselberg"))

        assert result.status == ResultStatus.SUCCESS
        # Check multiple sanctions lists are included
        sanctions_lists = result.results[0]["sanctions_lists"]
        assert "us_ofac_sdn" in sanctions_lists
        assert "eu_fsf" in sanctions_lists
        assert "ch_seco_sanctions" in sanctions_lists
        assert result.results[0]["sanctions_count"] == 3

        await adapter.close()


class TestOpenSanctionsAdapterPEPDetection:
    """Tests for PEP detection (FR19)."""

    @pytest.mark.asyncio
    async def test_pep_only_entity(self, httpx_mock) -> None:
        """PEP without sanctions returns appropriate status."""
        fixture = load_fixture("opensanctions_pep.json")

        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/match.*"),
            json=fixture,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.query(QueryParams(query="Hans Schmidt"))

        assert result.status == ResultStatus.SUCCESS
        assert result.results[0]["is_pep"] is True
        assert result.results[0]["is_sanctioned"] is False
        assert result.results[0]["pep_status"] == "PEP - NOT CURRENTLY SANCTIONED"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_pep_suggests_due_diligence(self, httpx_mock) -> None:
        """PEP result includes due diligence note."""
        fixture = load_fixture("opensanctions_pep.json")

        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/match.*"),
            json=fixture,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.query(QueryParams(query="Hans Schmidt"))

        assert result.status == ResultStatus.SUCCESS
        assert "due_diligence_note" in result.results[0]
        assert "Enhanced due diligence" in result.results[0]["due_diligence_note"]

        await adapter.close()


class TestOpenSanctionsAdapterEntityDetails:
    """Tests for entity details in results."""

    @pytest.mark.asyncio
    async def test_results_include_entity_type(self, httpx_mock) -> None:
        """Response includes schema/entity type."""
        fixture = load_fixture("opensanctions_entity.json")

        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/match.*"),
            json=fixture,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.query(QueryParams(query="Viktor Vekselberg"))

        assert result.status == ResultStatus.SUCCESS
        assert result.results[0]["schema"] == "Person"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_results_include_associated_entities(self, httpx_mock) -> None:
        """Response includes referents/associated entities."""
        fixture = load_fixture("opensanctions_entity.json")

        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/match.*"),
            json=fixture,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.query(QueryParams(query="Viktor Vekselberg"))

        assert result.status == ResultStatus.SUCCESS
        assert result.results[0]["referents"] is not None
        assert "ofac-12345" in result.results[0]["referents"]
        assert result.results[0]["referents_count"] == 2

        await adapter.close()

    @pytest.mark.asyncio
    async def test_results_include_dates(self, httpx_mock) -> None:
        """Response includes first_seen/last_seen dates."""
        fixture = load_fixture("opensanctions_entity.json")

        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/match.*"),
            json=fixture,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.query(QueryParams(query="Viktor Vekselberg"))

        assert result.status == ResultStatus.SUCCESS
        assert result.results[0]["first_seen"] == "2018-04-06"
        assert result.results[0]["last_seen"] == "2024-01-15"

        await adapter.close()


class TestOpenSanctionsAdapterCaching:
    """Tests for caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_hit(self) -> None:
        """Cache hit returns cached result without API call."""
        mock_cache = MagicMock()
        cached_data = {
            "results": [
                {
                    "entity_id": "NK-abc123",
                    "caption": "Viktor Vekselberg",
                    "is_sanctioned": True,
                }
            ],
            "query": "viktor vekselberg",
        }

        mock_entry = MagicMock(spec=CacheEntry)
        mock_entry.data = cached_data
        mock_entry.is_stale = False

        mock_cache.get = AsyncMock(return_value=mock_entry)

        adapter = OpenSanctionsAdapter(cache=mock_cache)
        result = await adapter.query(QueryParams(query="Viktor Vekselberg"))

        mock_cache.get.assert_called_once()
        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 1
        assert result.results[0]["entity_id"] == "NK-abc123"

    @pytest.mark.asyncio
    async def test_cache_miss_caches_result(self, httpx_mock) -> None:
        """Cache miss fetches from API and caches result."""
        fixture = load_fixture("opensanctions_entity.json")

        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/match.*"),
            json=fixture,
            method="POST",
        )

        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()

        adapter = OpenSanctionsAdapter(cache=mock_cache)
        result = await adapter.query(QueryParams(query="Viktor Vekselberg"))

        mock_cache.get.assert_called_once()
        mock_cache.set.assert_called_once()
        assert result.status == ResultStatus.SUCCESS

        await adapter.close()

    def test_cache_key_isolation(self) -> None:
        """Different query types use different cache keys."""
        from ignifer.cache import cache_key

        # Match and entity lookups should generate different keys
        match_key = cache_key("opensanctions", "match", name="test")
        entity_key = cache_key("opensanctions", "entity", entity_id="NK-123")

        # Verify different key patterns
        assert "match" in match_key
        assert "entity" in entity_key
        assert match_key != entity_key


class TestOpenSanctionsAdapterHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, httpx_mock) -> None:
        """Health check returns True when API responds."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org/search.*"),
            status_code=200,
            json={"results": []},
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.health_check()
        assert result is True

        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_failure_timeout(self, httpx_mock) -> None:
        """Health check returns False on timeout."""
        httpx_mock.add_exception(
            httpx.TimeoutException("Timeout"),
            url=re.compile(r".*api\.opensanctions\.org.*"),
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_failure_connection(self, httpx_mock) -> None:
        """Health check returns False on connection error."""
        httpx_mock.add_exception(
            httpx.ConnectError("Connection failed"),
            url=re.compile(r".*api\.opensanctions\.org.*"),
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.health_check()
        assert result is False


class TestOpenSanctionsAdapterClose:
    """Tests for resource cleanup."""

    @pytest.mark.asyncio
    async def test_close_cleans_up_client(self) -> None:
        """Close method cleans up the HTTP client."""
        adapter = OpenSanctionsAdapter()
        await adapter._get_client()
        assert adapter._client is not None

        await adapter.close()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_close_without_client_is_safe(self) -> None:
        """Close is safe to call without initialized client."""
        adapter = OpenSanctionsAdapter()
        assert adapter._client is None

        # Should not raise
        await adapter.close()
        assert adapter._client is None


class TestOpenSanctionsAdapterProtocolCompliance:
    """Tests for OSINTAdapter protocol compliance."""

    def test_has_source_name_property(self) -> None:
        """Adapter has source_name property."""
        adapter = OpenSanctionsAdapter()
        assert hasattr(adapter, "source_name")
        assert isinstance(adapter.source_name, str)

    def test_has_base_quality_tier_property(self) -> None:
        """Adapter has base_quality_tier property."""
        adapter = OpenSanctionsAdapter()
        assert hasattr(adapter, "base_quality_tier")
        assert isinstance(adapter.base_quality_tier, QualityTier)

    @pytest.mark.asyncio
    async def test_has_query_method(self) -> None:
        """Adapter has async query method."""
        adapter = OpenSanctionsAdapter()
        assert hasattr(adapter, "query")
        assert callable(adapter.query)

    @pytest.mark.asyncio
    async def test_has_health_check_method(self) -> None:
        """Adapter has async health_check method."""
        adapter = OpenSanctionsAdapter()
        assert hasattr(adapter, "health_check")
        assert callable(adapter.health_check)


class TestOpenSanctionsAdapterHTTPErrorHandling:
    """Tests for HTTP error handling."""

    @pytest.mark.asyncio
    async def test_query_500_server_error_raises_timeout(self, httpx_mock) -> None:
        """500 server error raises AdapterTimeoutError (service unavailable)."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org.*"),
            status_code=500,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.query(QueryParams(query="Test"))

        assert exc_info.value.source_name == "opensanctions"

    @pytest.mark.asyncio
    async def test_query_503_server_error_raises_timeout(self, httpx_mock) -> None:
        """503 server error raises AdapterTimeoutError (service unavailable)."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org.*"),
            status_code=503,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.query(QueryParams(query="Test"))

        assert exc_info.value.source_name == "opensanctions"

    @pytest.mark.asyncio
    async def test_query_404_returns_no_data(self, httpx_mock) -> None:
        """404 error returns NO_DATA status."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org.*"),
            status_code=404,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        result = await adapter.query(QueryParams(query="Test"))

        assert result.status == ResultStatus.NO_DATA
        assert "not found" in result.error.lower()

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_400_client_error_raises_parse_error(self, httpx_mock) -> None:
        """400 client error raises AdapterParseError."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.opensanctions\.org.*"),
            status_code=400,
            method="POST",
        )

        adapter = OpenSanctionsAdapter()
        with pytest.raises(AdapterParseError) as exc_info:
            await adapter.query(QueryParams(query="Test"))

        assert "HTTP 400" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_connection_error_raises_timeout(self, httpx_mock) -> None:
        """Connection error raises AdapterTimeoutError."""
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused"),
            url=re.compile(r".*api\.opensanctions\.org.*"),
        )

        adapter = OpenSanctionsAdapter()
        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.query(QueryParams(query="Test"))

        assert exc_info.value.source_name == "opensanctions"
