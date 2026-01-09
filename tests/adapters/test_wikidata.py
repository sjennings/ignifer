"""Tests for Wikidata adapter."""

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from ignifer.adapters.base import AdapterParseError, AdapterTimeoutError
from ignifer.adapters.wikidata import WikidataAdapter, KEY_PROPERTIES
from ignifer.cache import CacheEntry
from ignifer.models import QueryParams, QualityTier, ResultStatus


# Load fixture once at module level
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


class TestWikidataAdapterProperties:
    """Tests for WikidataAdapter class properties."""

    def test_source_name(self) -> None:
        """Source name is 'wikidata'."""
        adapter = WikidataAdapter()
        assert adapter.source_name == "wikidata"

    def test_base_quality_tier_is_high(self) -> None:
        """Base quality tier is HIGH (curated encyclopedic data)."""
        adapter = WikidataAdapter()
        assert adapter.base_quality_tier == QualityTier.HIGH

    def test_base_url_is_wikidata(self) -> None:
        """Base URL points to Wikidata API."""
        adapter = WikidataAdapter()
        assert adapter.BASE_URL == "https://www.wikidata.org/w/api.php"

    def test_key_properties_defined(self) -> None:
        """Key properties mapping is defined."""
        assert "P31" in KEY_PROPERTIES  # instance_of
        assert "P106" in KEY_PROPERTIES  # occupation
        assert "P17" in KEY_PROPERTIES  # country
        assert "P27" in KEY_PROPERTIES  # citizenship
        assert "P856" in KEY_PROPERTIES  # website


class TestWikidataAdapterLazyClient:
    """Tests for lazy HTTP client initialization."""

    @pytest.mark.asyncio
    async def test_get_client_creates_client(self) -> None:
        """_get_client creates httpx.AsyncClient lazily."""
        adapter = WikidataAdapter()
        assert adapter._client is None

        client = await adapter._get_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        assert adapter._client is client

        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_client_returns_same_client(self) -> None:
        """_get_client returns the same client on subsequent calls."""
        adapter = WikidataAdapter()

        client1 = await adapter._get_client()
        client2 = await adapter._get_client()
        assert client1 is client2

        await adapter.close()


class TestWikidataAdapterHelpers:
    """Tests for helper methods."""

    def test_extract_labels(self) -> None:
        """_extract_labels extracts language-keyed labels."""
        adapter = WikidataAdapter()
        entity_data = {
            "labels": {
                "en": {"language": "en", "value": "Vladimir Putin"},
                "ru": {"language": "ru", "value": "Владимир Путин"},
            }
        }

        labels = adapter._extract_labels(entity_data)
        assert labels["en"] == "Vladimir Putin"
        assert labels["ru"] == "Владимир Путин"

    def test_extract_labels_empty(self) -> None:
        """_extract_labels handles empty/missing labels."""
        adapter = WikidataAdapter()
        assert adapter._extract_labels({}) == {}
        assert adapter._extract_labels({"labels": {}}) == {}

    def test_extract_aliases(self) -> None:
        """_extract_aliases extracts alias list with English first."""
        adapter = WikidataAdapter()
        entity_data = {
            "aliases": {
                "en": [
                    {"language": "en", "value": "Putin"},
                    {"language": "en", "value": "V. Putin"},
                ],
                "ru": [{"language": "ru", "value": "Путин"}],
            }
        }

        aliases = adapter._extract_aliases(entity_data)
        assert "Putin" in aliases
        assert "V. Putin" in aliases
        assert "Путин" in aliases
        # English aliases should come first
        assert aliases.index("Putin") < aliases.index("Путин")

    def test_extract_aliases_empty(self) -> None:
        """_extract_aliases handles empty/missing aliases."""
        adapter = WikidataAdapter()
        assert adapter._extract_aliases({}) == []
        assert adapter._extract_aliases({"aliases": {}}) == []

    def test_extract_claims_entity_reference(self) -> None:
        """_extract_claims extracts entity references."""
        adapter = WikidataAdapter()
        entity_data = {
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q5"},
                                "type": "wikibase-entityid",
                            }
                        }
                    }
                ]
            }
        }

        claims = adapter._extract_claims(entity_data)
        assert "instance_of" in claims
        assert claims["instance_of"]["qid"] == "Q5"

    def test_extract_claims_string_value(self) -> None:
        """_extract_claims extracts string values."""
        adapter = WikidataAdapter()
        entity_data = {
            "claims": {
                "P856": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": "http://kremlin.ru/",
                                "type": "string",
                            }
                        }
                    }
                ]
            }
        }

        claims = adapter._extract_claims(entity_data)
        assert "website" in claims
        assert claims["website"]["value"] == "http://kremlin.ru/"

    def test_extract_claims_time_value(self) -> None:
        """_extract_claims extracts and normalizes time values."""
        adapter = WikidataAdapter()
        entity_data = {
            "claims": {
                "P571": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {
                                    "time": "+1952-10-07T00:00:00Z",
                                    "timezone": 0,
                                },
                                "type": "time",
                            }
                        }
                    }
                ]
            }
        }

        claims = adapter._extract_claims(entity_data)
        assert "inception" in claims
        assert claims["inception"]["value"] == "1952-10-07"

    def test_build_entity_url(self) -> None:
        """_build_entity_url creates correct Wikidata URL."""
        adapter = WikidataAdapter()
        url = adapter._build_entity_url("Q7747")
        assert url == "https://www.wikidata.org/wiki/Q7747"


class TestWikidataAdapterQuery:
    """Tests for entity search via query()."""

    @pytest.mark.asyncio
    async def test_query_success(self, httpx_mock) -> None:
        """Successful query returns normalized search results."""
        search_fixture = load_fixture("wikidata_search.json")
        entities_fixture = load_fixture("wikidata_entities_batch.json")

        # Mock search request
        httpx_mock.add_response(
            url=re.compile(r".*wbsearchentities.*"),
            json=search_fixture,
        )
        # Mock entity details request
        httpx_mock.add_response(
            url=re.compile(r".*wbgetentities.*"),
            json=entities_fixture,
        )

        adapter = WikidataAdapter()
        result = await adapter.query(QueryParams(query="Vladimir Putin"))

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 2
        assert result.results[0]["qid"] == "Q7747"
        assert result.results[0]["label"] == "Vladimir Putin"
        assert result.results[0]["description"] == "President of Russia"
        assert result.sources[0].source == "wikidata"
        assert result.sources[0].quality == QualityTier.HIGH

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_empty_string_returns_no_data(self) -> None:
        """Empty query string returns NO_DATA status."""
        adapter = WikidataAdapter()
        result = await adapter.query(QueryParams(query="   "))

        assert result.status == ResultStatus.NO_DATA
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_query_no_results(self, httpx_mock) -> None:
        """No search results returns NO_DATA status."""
        httpx_mock.add_response(
            url=re.compile(r".*wbsearchentities.*"),
            json={"search": [], "success": 1},
        )

        adapter = WikidataAdapter()
        result = await adapter.query(QueryParams(query="xyznonexistent123"))

        assert result.status == ResultStatus.NO_DATA
        assert result.error is not None
        assert "No entities found" in result.error

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_timeout_raises_error(self, httpx_mock) -> None:
        """Timeout raises AdapterTimeoutError."""
        httpx_mock.add_exception(
            httpx.TimeoutException("Timeout"),
            url=re.compile(r".*wikidata.*"),
        )

        adapter = WikidataAdapter()
        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.query(QueryParams(query="Vladimir Putin"))

        assert exc_info.value.source_name == "wikidata"

    @pytest.mark.asyncio
    async def test_query_rate_limited(self, httpx_mock) -> None:
        """429 response returns RATE_LIMITED status."""
        httpx_mock.add_response(
            url=re.compile(r".*wikidata.*"),
            status_code=429,
        )

        adapter = WikidataAdapter()
        result = await adapter.query(QueryParams(query="Vladimir Putin"))

        assert result.status == ResultStatus.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_query_malformed_json_raises_parse_error(self, httpx_mock) -> None:
        """Malformed JSON response raises AdapterParseError."""
        httpx_mock.add_response(
            url=re.compile(r".*wikidata.*"),
            content=b"not valid json {{{",
            status_code=200,
        )

        adapter = WikidataAdapter()
        with pytest.raises(AdapterParseError) as exc_info:
            await adapter.query(QueryParams(query="Vladimir Putin"))

        assert "Invalid JSON response" in str(exc_info.value)


class TestWikidataAdapterLookupByQid:
    """Tests for direct Q-ID lookup via lookup_by_qid()."""

    @pytest.mark.asyncio
    async def test_lookup_by_qid_success(self, httpx_mock) -> None:
        """Successful Q-ID lookup returns full entity details."""
        fixture = load_fixture("wikidata_entity.json")
        httpx_mock.add_response(
            url=re.compile(r".*wbgetentities.*"),
            json=fixture,
        )

        adapter = WikidataAdapter()
        result = await adapter.lookup_by_qid("Q7747")

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 1
        assert result.results[0]["qid"] == "Q7747"
        assert result.results[0]["label"] == "Vladimir Putin"
        assert result.results[0]["description"] == "President of Russia"
        # Check extracted properties
        assert result.results[0]["instance_of_qid"] == "Q5"
        assert result.results[0]["citizenship_qid"] == "Q159"
        assert result.results[0]["website"] == "http://kremlin.ru/"
        # Check aliases are present
        assert "Putin" in result.results[0]["aliases"]

        await adapter.close()

    @pytest.mark.asyncio
    async def test_lookup_by_qid_normalizes_input(self, httpx_mock) -> None:
        """Q-ID is normalized (uppercase, Q prefix added)."""
        fixture = load_fixture("wikidata_entity.json")
        httpx_mock.add_response(
            url=re.compile(r".*wbgetentities.*"),
            json=fixture,
        )

        adapter = WikidataAdapter()

        # Test lowercase
        result = await adapter.lookup_by_qid("q7747")
        assert result.status == ResultStatus.SUCCESS

        await adapter.close()

    @pytest.mark.asyncio
    async def test_lookup_by_qid_missing_entity(self, httpx_mock) -> None:
        """Missing entity returns NO_DATA status."""
        # The API returns an entry with "missing" key when entity doesn't exist
        httpx_mock.add_response(
            url=re.compile(r".*wbgetentities.*"),
            json={
                "entities": {
                    "Q999999999": {"id": "Q999999999", "missing": ""}
                },
                "success": 1,
            },
        )

        adapter = WikidataAdapter()
        result = await adapter.lookup_by_qid("Q999999999")

        assert result.status == ResultStatus.NO_DATA
        assert result.error is not None
        assert "not found" in result.error.lower()

        await adapter.close()

    @pytest.mark.asyncio
    async def test_lookup_by_qid_timeout(self, httpx_mock) -> None:
        """Timeout raises AdapterTimeoutError."""
        httpx_mock.add_exception(
            httpx.TimeoutException("Timeout"),
            url=re.compile(r".*wikidata.*"),
        )

        adapter = WikidataAdapter()
        with pytest.raises(AdapterTimeoutError):
            await adapter.lookup_by_qid("Q7747")

    @pytest.mark.asyncio
    async def test_lookup_by_qid_rate_limited(self, httpx_mock) -> None:
        """429 response returns RATE_LIMITED status."""
        httpx_mock.add_response(
            url=re.compile(r".*wikidata.*"),
            status_code=429,
        )

        adapter = WikidataAdapter()
        result = await adapter.lookup_by_qid("Q7747")

        assert result.status == ResultStatus.RATE_LIMITED


class TestWikidataAdapterCaching:
    """Tests for caching behavior."""

    @pytest.mark.asyncio
    async def test_query_cache_hit(self) -> None:
        """Cache hit returns cached result without API call."""
        mock_cache = MagicMock()
        cached_data = {
            "results": [
                {
                    "qid": "Q7747",
                    "label": "Vladimir Putin",
                    "description": "President of Russia",
                    "aliases": "Putin",
                    "instance_of": "Q5",
                    "instance_of_qid": "Q5",
                    "url": "https://www.wikidata.org/wiki/Q7747",
                }
            ],
            "query": "vladimir putin",
        }

        mock_entry = MagicMock(spec=CacheEntry)
        mock_entry.data = cached_data
        mock_entry.is_stale = False

        mock_cache.get = AsyncMock(return_value=mock_entry)

        adapter = WikidataAdapter(cache=mock_cache)
        result = await adapter.query(QueryParams(query="Vladimir Putin"))

        mock_cache.get.assert_called_once()
        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 1
        assert result.results[0]["qid"] == "Q7747"

    @pytest.mark.asyncio
    async def test_lookup_by_qid_cache_hit(self) -> None:
        """Cache hit for Q-ID lookup returns cached result."""
        mock_cache = MagicMock()
        cached_data = {
            "results": [
                {
                    "qid": "Q7747",
                    "label": "Vladimir Putin",
                    "description": "President of Russia",
                }
            ],
            "qid": "Q7747",
        }

        mock_entry = MagicMock(spec=CacheEntry)
        mock_entry.data = cached_data
        mock_entry.is_stale = False

        mock_cache.get = AsyncMock(return_value=mock_entry)

        adapter = WikidataAdapter(cache=mock_cache)
        result = await adapter.lookup_by_qid("Q7747")

        mock_cache.get.assert_called_once()
        assert result.status == ResultStatus.SUCCESS
        assert result.results[0]["qid"] == "Q7747"

    @pytest.mark.asyncio
    async def test_query_cache_miss_caches_result(self, httpx_mock) -> None:
        """Cache miss fetches from API and caches result."""
        search_fixture = load_fixture("wikidata_search.json")
        entities_fixture = load_fixture("wikidata_entities_batch.json")

        httpx_mock.add_response(
            url=re.compile(r".*wbsearchentities.*"),
            json=search_fixture,
        )
        httpx_mock.add_response(
            url=re.compile(r".*wbgetentities.*"),
            json=entities_fixture,
        )

        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()

        adapter = WikidataAdapter(cache=mock_cache)
        result = await adapter.query(QueryParams(query="Vladimir Putin"))

        mock_cache.get.assert_called_once()
        mock_cache.set.assert_called_once()
        assert result.status == ResultStatus.SUCCESS

        await adapter.close()

    def test_cache_key_isolation(self) -> None:
        """Different query types use different cache keys."""
        from ignifer.cache import cache_key

        # Search and lookup should generate different keys
        search_key = cache_key("wikidata", "search", text="test")
        entity_key = cache_key("wikidata", "entity", qid="Q7747")

        # Verify different key patterns
        assert "search" in search_key
        assert "entity" in entity_key
        assert search_key != entity_key


class TestWikidataAdapterHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, httpx_mock) -> None:
        """Health check returns True when API responds."""
        httpx_mock.add_response(
            url=re.compile(r".*wikidata.*"),
            status_code=200,
            json={"search": [], "success": 1},
        )

        adapter = WikidataAdapter()
        result = await adapter.health_check()
        assert result is True

        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_failure_timeout(self, httpx_mock) -> None:
        """Health check returns False on timeout."""
        httpx_mock.add_exception(
            httpx.TimeoutException("Timeout"),
            url=re.compile(r".*wikidata.*"),
        )

        adapter = WikidataAdapter()
        result = await adapter.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_failure_connection(self, httpx_mock) -> None:
        """Health check returns False on connection error."""
        httpx_mock.add_exception(
            httpx.ConnectError("Connection failed"),
            url=re.compile(r".*wikidata.*"),
        )

        adapter = WikidataAdapter()
        result = await adapter.health_check()
        assert result is False


class TestWikidataAdapterClose:
    """Tests for resource cleanup."""

    @pytest.mark.asyncio
    async def test_close_cleans_up_client(self) -> None:
        """Close method cleans up the HTTP client."""
        adapter = WikidataAdapter()
        await adapter._get_client()
        assert adapter._client is not None

        await adapter.close()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_close_without_client_is_safe(self) -> None:
        """Close is safe to call without initialized client."""
        adapter = WikidataAdapter()
        assert adapter._client is None

        # Should not raise
        await adapter.close()
        assert adapter._client is None


class TestWikidataAdapterProtocolCompliance:
    """Tests for OSINTAdapter protocol compliance."""

    def test_has_source_name_property(self) -> None:
        """Adapter has source_name property."""
        adapter = WikidataAdapter()
        assert hasattr(adapter, "source_name")
        assert isinstance(adapter.source_name, str)

    def test_has_base_quality_tier_property(self) -> None:
        """Adapter has base_quality_tier property."""
        adapter = WikidataAdapter()
        assert hasattr(adapter, "base_quality_tier")
        assert isinstance(adapter.base_quality_tier, QualityTier)

    @pytest.mark.asyncio
    async def test_has_query_method(self) -> None:
        """Adapter has async query method."""
        adapter = WikidataAdapter()
        assert hasattr(adapter, "query")
        assert callable(adapter.query)

    @pytest.mark.asyncio
    async def test_has_health_check_method(self) -> None:
        """Adapter has async health_check method."""
        adapter = WikidataAdapter()
        assert hasattr(adapter, "health_check")
        assert callable(adapter.health_check)


class TestWikidataAdapterHTTPErrorHandling:
    """Tests for improved HTTP error handling (Issues #1, #8)."""

    @pytest.mark.asyncio
    async def test_query_500_server_error_raises_timeout(self, httpx_mock) -> None:
        """500 server error raises AdapterTimeoutError (service unavailable)."""
        httpx_mock.add_response(
            url=re.compile(r".*wikidata.*"),
            status_code=500,
        )

        adapter = WikidataAdapter()
        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.query(QueryParams(query="Test"))

        assert exc_info.value.source_name == "wikidata"

    @pytest.mark.asyncio
    async def test_query_503_server_error_raises_timeout(self, httpx_mock) -> None:
        """503 server error raises AdapterTimeoutError (service unavailable)."""
        httpx_mock.add_response(
            url=re.compile(r".*wikidata.*"),
            status_code=503,
        )

        adapter = WikidataAdapter()
        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.query(QueryParams(query="Test"))

        assert exc_info.value.source_name == "wikidata"

    @pytest.mark.asyncio
    async def test_query_404_returns_no_data(self, httpx_mock) -> None:
        """404 error returns NO_DATA status."""
        httpx_mock.add_response(
            url=re.compile(r".*wikidata.*"),
            status_code=404,
        )

        adapter = WikidataAdapter()
        result = await adapter.query(QueryParams(query="Test"))

        assert result.status == ResultStatus.NO_DATA
        assert "not found" in result.error.lower()

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_400_client_error_raises_parse_error(self, httpx_mock) -> None:
        """400 client error raises AdapterParseError."""
        httpx_mock.add_response(
            url=re.compile(r".*wikidata.*"),
            status_code=400,
        )

        adapter = WikidataAdapter()
        with pytest.raises(AdapterParseError) as exc_info:
            await adapter.query(QueryParams(query="Test"))

        assert "HTTP 400" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_connection_error_raises_timeout(self, httpx_mock) -> None:
        """Connection error raises AdapterTimeoutError."""
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused"),
            url=re.compile(r".*wikidata.*"),
        )

        adapter = WikidataAdapter()
        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.query(QueryParams(query="Test"))

        assert exc_info.value.source_name == "wikidata"

    @pytest.mark.asyncio
    async def test_lookup_500_server_error_raises_timeout(self, httpx_mock) -> None:
        """500 server error in lookup raises AdapterTimeoutError."""
        httpx_mock.add_response(
            url=re.compile(r".*wikidata.*"),
            status_code=500,
        )

        adapter = WikidataAdapter()
        with pytest.raises(AdapterTimeoutError):
            await adapter.lookup_by_qid("Q7747")

    @pytest.mark.asyncio
    async def test_lookup_404_returns_no_data(self, httpx_mock) -> None:
        """404 error in lookup returns NO_DATA status."""
        httpx_mock.add_response(
            url=re.compile(r".*wikidata.*"),
            status_code=404,
        )

        adapter = WikidataAdapter()
        result = await adapter.lookup_by_qid("Q7747")

        assert result.status == ResultStatus.NO_DATA

        await adapter.close()


class TestWikidataAdapterQIDValidation:
    """Tests for Q-ID format validation (Issue #5)."""

    @pytest.mark.asyncio
    async def test_invalid_qid_empty_q(self) -> None:
        """Invalid Q-ID 'Q' returns NO_DATA."""
        adapter = WikidataAdapter()
        result = await adapter.lookup_by_qid("Q")

        assert result.status == ResultStatus.NO_DATA
        assert "Invalid Q-ID format" in result.error

    @pytest.mark.asyncio
    async def test_invalid_qid_with_hyphen(self) -> None:
        """Invalid Q-ID 'Q-7747' returns NO_DATA."""
        adapter = WikidataAdapter()
        result = await adapter.lookup_by_qid("Q-7747")

        assert result.status == ResultStatus.NO_DATA
        assert "Invalid Q-ID format" in result.error

    @pytest.mark.asyncio
    async def test_invalid_qid_double_q(self) -> None:
        """Invalid Q-ID 'QQ7747' returns NO_DATA."""
        adapter = WikidataAdapter()
        result = await adapter.lookup_by_qid("QQ7747")

        assert result.status == ResultStatus.NO_DATA
        assert "Invalid Q-ID format" in result.error

    @pytest.mark.asyncio
    async def test_invalid_qid_letters_after_q(self) -> None:
        """Invalid Q-ID 'QABC' returns NO_DATA."""
        adapter = WikidataAdapter()
        result = await adapter.lookup_by_qid("QABC")

        assert result.status == ResultStatus.NO_DATA
        assert "Invalid Q-ID format" in result.error


class TestWikidataAdapterQIDRedirect:
    """Tests for Q-ID pattern detection in query (Issue #2)."""

    @pytest.mark.asyncio
    async def test_query_with_qid_redirects_to_lookup(self, httpx_mock) -> None:
        """Query with Q-ID pattern redirects to lookup_by_qid."""
        fixture = load_fixture("wikidata_entity.json")
        httpx_mock.add_response(
            url=re.compile(r".*wbgetentities.*"),
            json=fixture,
        )

        adapter = WikidataAdapter()
        # Query with lowercase q-id should redirect to lookup
        result = await adapter.query(QueryParams(query="q7747"))

        assert result.status == ResultStatus.SUCCESS
        assert result.results[0]["qid"] == "Q7747"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_with_numeric_id_redirects_to_lookup(self, httpx_mock) -> None:
        """Query with just numbers (like '7747') redirects to lookup_by_qid."""
        fixture = load_fixture("wikidata_entity.json")
        httpx_mock.add_response(
            url=re.compile(r".*wbgetentities.*"),
            json=fixture,
        )

        adapter = WikidataAdapter()
        result = await adapter.query(QueryParams(query="7747"))

        assert result.status == ResultStatus.SUCCESS
        assert result.results[0]["qid"] == "Q7747"

        await adapter.close()


class TestWikidataAdapterClaimValueTypes:
    """Tests for additional claim value types (Issue #4)."""

    def test_extract_monolingualtext(self) -> None:
        """Monolingualtext claim type is extracted correctly."""
        adapter = WikidataAdapter()
        claim = {
            "mainsnak": {
                "snaktype": "value",
                "datavalue": {
                    "type": "monolingualtext",
                    "value": {"text": "E pluribus unum", "language": "la"},
                },
            }
        }

        result = adapter._extract_claim_value(claim)
        assert result["value"] == "E pluribus unum"
        assert result["language"] == "la"

    def test_extract_external_id(self) -> None:
        """External-id claim type is extracted correctly."""
        adapter = WikidataAdapter()
        claim = {
            "mainsnak": {
                "snaktype": "value",
                "datavalue": {
                    "type": "external-id",
                    "value": "tt0111161",
                },
            }
        }

        result = adapter._extract_claim_value(claim)
        assert result["value"] == "tt0111161"
        assert result["type"] == "external-id"

    def test_extract_commons_media(self) -> None:
        """CommonsMedia claim type is extracted correctly."""
        adapter = WikidataAdapter()
        claim = {
            "mainsnak": {
                "snaktype": "value",
                "datavalue": {
                    "type": "commonsMedia",
                    "value": "Flag of the United States.svg",
                },
            }
        }

        result = adapter._extract_claim_value(claim)
        assert result["value"] == "Flag of the United States.svg"
        assert result["type"] == "commonsMedia"

    def test_extract_url(self) -> None:
        """URL claim type is extracted correctly."""
        adapter = WikidataAdapter()
        claim = {
            "mainsnak": {
                "snaktype": "value",
                "datavalue": {
                    "type": "url",
                    "value": "https://example.com",
                },
            }
        }

        result = adapter._extract_claim_value(claim)
        assert result["value"] == "https://example.com"

    def test_extract_novalue(self) -> None:
        """Novalue snaktype is handled correctly."""
        adapter = WikidataAdapter()
        claim = {
            "mainsnak": {
                "snaktype": "novalue",
            }
        }

        result = adapter._extract_claim_value(claim)
        assert result["value"] is None
        assert result["snaktype"] == "novalue"

    def test_extract_somevalue(self) -> None:
        """Somevalue snaktype is handled correctly."""
        adapter = WikidataAdapter()
        claim = {
            "mainsnak": {
                "snaktype": "somevalue",
            }
        }

        result = adapter._extract_claim_value(claim)
        assert result["value"] is None
        assert result["snaktype"] == "somevalue"


class TestWikidataAdapterOutputConsistency:
    """Tests for consistent output schema (Issue #7)."""

    @pytest.mark.asyncio
    async def test_lookup_always_includes_related_entities_count(self, httpx_mock) -> None:
        """Lookup results always include related_entities_count, even when 0."""
        # Use an entity with no related entities
        httpx_mock.add_response(
            url=re.compile(r".*wbgetentities.*"),
            json={
                "entities": {
                    "Q12345": {
                        "type": "item",
                        "id": "Q12345",
                        "labels": {"en": {"language": "en", "value": "Test Entity"}},
                        "descriptions": {"en": {"language": "en", "value": "A test"}},
                        "aliases": {},
                        "claims": {},  # No claims = no related entities
                    }
                },
                "success": 1,
            },
        )

        adapter = WikidataAdapter()
        result = await adapter.lookup_by_qid("Q12345")

        assert result.status == ResultStatus.SUCCESS
        assert "related_entities_count" in result.results[0]
        assert result.results[0]["related_entities_count"] == 0

        await adapter.close()


class TestWikidataAdapterBatchFetchErrorHandling:
    """Tests for batch fetch error handling (Issue #3)."""

    @pytest.mark.asyncio
    async def test_batch_fetch_timeout_returns_empty_with_warning(
        self, httpx_mock, caplog
    ) -> None:
        """Batch fetch timeout logs warning and returns empty dict."""
        search_fixture = load_fixture("wikidata_search.json")

        # First request for search succeeds
        httpx_mock.add_response(
            url=re.compile(r".*wbsearchentities.*"),
            json=search_fixture,
        )
        # Second request for entity details times out
        httpx_mock.add_exception(
            httpx.TimeoutException("Timeout"),
            url=re.compile(r".*wbgetentities.*"),
        )

        adapter = WikidataAdapter()
        result = await adapter.query(QueryParams(query="Vladimir Putin"))

        # Should still succeed with partial results
        assert result.status == ResultStatus.SUCCESS
        # But results won't have enriched details
        assert len(result.results) > 0

        # Check that warning was logged
        assert "Timeout fetching entity details" in caplog.text

        await adapter.close()

    @pytest.mark.asyncio
    async def test_batch_fetch_http_error_returns_empty_with_warning(
        self, httpx_mock, caplog
    ) -> None:
        """Batch fetch HTTP error logs warning and returns empty dict."""
        search_fixture = load_fixture("wikidata_search.json")

        # First request for search succeeds
        httpx_mock.add_response(
            url=re.compile(r".*wbsearchentities.*"),
            json=search_fixture,
        )
        # Second request for entity details fails
        httpx_mock.add_response(
            url=re.compile(r".*wbgetentities.*"),
            status_code=500,
        )

        adapter = WikidataAdapter()
        result = await adapter.query(QueryParams(query="Vladimir Putin"))

        # Should still succeed with partial results
        assert result.status == ResultStatus.SUCCESS

        # Check that warning was logged
        assert "HTTP 500" in caplog.text

        await adapter.close()
