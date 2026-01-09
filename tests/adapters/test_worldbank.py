"""Tests for World Bank adapter."""

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from ignifer.adapters.base import AdapterParseError, AdapterTimeoutError
from ignifer.adapters.worldbank import WorldBankAdapter
from ignifer.cache import CacheEntry
from ignifer.models import QueryParams, QualityTier, ResultStatus


# Load fixture once at module level
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


class TestWorldBankAdapter:
    """Tests for WorldBankAdapter class."""

    # Sample country lookup for testing _parse_query directly
    SAMPLE_COUNTRY_LOOKUP = {
        "usa": "USA",
        "us": "USA",
        "united states": "USA",
        "america": "USA",
        "uk": "GBR",
        "united kingdom": "GBR",
        "britain": "GBR",
        "germany": "DEU",
        "deu": "DEU",
        "eu": "EUU",
        "european union": "EUU",
        "sub-saharan africa": "SSF",
        "ssa": "SSF",
    }

    def test_source_name(self) -> None:
        """Source name is 'worldbank'."""
        adapter = WorldBankAdapter()
        assert adapter.source_name == "worldbank"

    def test_base_quality_tier_is_high(self) -> None:
        """Base quality tier is HIGH (official government data)."""
        adapter = WorldBankAdapter()
        assert adapter.base_quality_tier == QualityTier.HIGH

    def test_parse_query_gdp_usa(self) -> None:
        """Parse query extracts GDP indicator and USA country."""
        adapter = WorldBankAdapter()
        indicator, country = adapter._parse_query(
            "GDP United States", self.SAMPLE_COUNTRY_LOOKUP
        )
        assert indicator == "NY.GDP.MKTP.CD"
        assert country == "USA"

    def test_parse_query_inflation_germany(self) -> None:
        """Parse query extracts inflation indicator and DEU country."""
        adapter = WorldBankAdapter()
        indicator, country = adapter._parse_query(
            "inflation Germany", self.SAMPLE_COUNTRY_LOOKUP
        )
        assert indicator == "FP.CPI.TOTL.ZG"
        assert country == "DEU"

    def test_parse_query_country_aliases(self) -> None:
        """Country aliases resolve to correct ISO codes."""
        adapter = WorldBankAdapter()

        # Test various aliases for USA
        for alias in ["USA", "US", "United States", "America"]:
            _, country = adapter._parse_query(
                f"GDP {alias}", self.SAMPLE_COUNTRY_LOOKUP
            )
            assert country == "USA", f"Failed for alias: {alias}"

        # Test UK aliases
        for alias in ["UK", "United Kingdom", "Britain"]:
            _, country = adapter._parse_query(
                f"GDP {alias}", self.SAMPLE_COUNTRY_LOOKUP
            )
            assert country == "GBR", f"Failed for alias: {alias}"

    def test_parse_query_regional_aggregates(self) -> None:
        """Regional aggregates resolve correctly."""
        adapter = WorldBankAdapter()

        _, country = adapter._parse_query(
            "GDP European Union", self.SAMPLE_COUNTRY_LOOKUP
        )
        assert country == "EUU"

        _, country = adapter._parse_query("GDP EU", self.SAMPLE_COUNTRY_LOOKUP)
        assert country == "EUU"

        # Sub-Saharan Africa (H1 fix verification)
        _, country = adapter._parse_query(
            "GDP Sub-Saharan Africa", self.SAMPLE_COUNTRY_LOOKUP
        )
        assert country == "SSF"

        _, country = adapter._parse_query("GDP SSA", self.SAMPLE_COUNTRY_LOOKUP)
        assert country == "SSF"

    def test_parse_query_unparseable_returns_none(self) -> None:
        """Unparseable queries return None for both fields."""
        adapter = WorldBankAdapter()
        indicator, country = adapter._parse_query(
            "random gibberish", self.SAMPLE_COUNTRY_LOOKUP
        )
        assert indicator is None
        assert country is None

    def _adapter_with_country_lookup(self, cache=None) -> WorldBankAdapter:
        """Create adapter with pre-populated country lookup to avoid HTTP calls."""
        adapter = WorldBankAdapter(cache=cache)
        adapter._country_lookup = dict(self.SAMPLE_COUNTRY_LOOKUP)
        return adapter

    @pytest.mark.asyncio
    async def test_query_success(self, httpx_mock) -> None:
        """Successful query returns normalized results."""
        fixture_data = load_fixture("worldbank_response.json")
        httpx_mock.add_response(
            url=re.compile(r".*worldbank.*"),
            json=fixture_data,
        )

        adapter = self._adapter_with_country_lookup()
        result = await adapter.query(QueryParams(query="GDP United States"))

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 5  # Fixture has 5 records
        assert result.results[0]["country"] == "United States"
        assert result.results[0]["year"] == "2023"
        assert result.results[0]["value"] == 25462700000000
        assert result.sources[0].source == "worldbank"

    @pytest.mark.asyncio
    async def test_query_no_data_unparseable(self) -> None:
        """Unparseable query returns NO_DATA with helpful message."""
        adapter = self._adapter_with_country_lookup()
        result = await adapter.query(QueryParams(query="random gibberish"))

        assert result.status == ResultStatus.NO_DATA
        assert result.error is not None
        assert "Could not parse" in result.error

    @pytest.mark.asyncio
    async def test_query_timeout_raises_error(self, httpx_mock) -> None:
        """Timeout raises AdapterTimeoutError."""
        httpx_mock.add_exception(
            httpx.TimeoutException("Timeout"),
            url=re.compile(r".*worldbank.*"),
        )

        adapter = self._adapter_with_country_lookup()
        with pytest.raises(AdapterTimeoutError):
            await adapter.query(QueryParams(query="GDP United States"))

    @pytest.mark.asyncio
    async def test_query_rate_limited(self, httpx_mock) -> None:
        """429 response returns RATE_LIMITED status."""
        httpx_mock.add_response(
            url=re.compile(r".*worldbank.*"),
            status_code=429,
        )

        adapter = self._adapter_with_country_lookup()
        result = await adapter.query(QueryParams(query="GDP United States"))

        assert result.status == ResultStatus.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_query_empty_results(self, httpx_mock) -> None:
        """Empty API results return NO_DATA status."""
        httpx_mock.add_response(
            url=re.compile(r".*worldbank.*"),
            json=[
                {"page": 1, "pages": 0, "per_page": 10, "total": 0},
                [],
            ],
        )

        adapter = self._adapter_with_country_lookup()
        result = await adapter.query(QueryParams(query="GDP United States"))

        assert result.status == ResultStatus.NO_DATA

    @pytest.mark.asyncio
    async def test_query_malformed_json_raises_parse_error(self, httpx_mock) -> None:
        """Malformed JSON response raises AdapterParseError (H3 fix)."""
        httpx_mock.add_response(
            url=re.compile(r".*worldbank.*"),
            content=b"not valid json {{{",
            status_code=200,
        )

        adapter = self._adapter_with_country_lookup()
        with pytest.raises(AdapterParseError) as exc_info:
            await adapter.query(QueryParams(query="GDP United States"))

        assert "Invalid JSON response" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_cache_hit(self) -> None:
        """Cache hit returns cached result without API call (H2 fix)."""
        # Create mock cache manager
        mock_cache = MagicMock()
        cached_data = {
            "results": [
                {
                    "indicator": "GDP (current US$)",
                    "country": "United States",
                    "year": "2023",
                    "value": 25462700000000,
                }
            ],
            "indicator": "NY.GDP.MKTP.CD",
            "country": "USA",
        }

        # Create mock cache entry that is not stale
        mock_entry = MagicMock(spec=CacheEntry)
        mock_entry.data = cached_data
        mock_entry.is_stale = False

        mock_cache.get = AsyncMock(return_value=mock_entry)

        adapter = self._adapter_with_country_lookup(cache=mock_cache)
        result = await adapter.query(QueryParams(query="GDP United States"))

        # Verify cache was checked
        mock_cache.get.assert_called_once()

        # Verify result comes from cache
        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 1
        assert result.results[0]["country"] == "United States"
        assert result.results[0]["value"] == 25462700000000

    @pytest.mark.asyncio
    async def test_query_cache_miss_fetches_from_api(self, httpx_mock) -> None:
        """Cache miss fetches from API and caches result."""
        fixture_data = load_fixture("worldbank_response.json")
        httpx_mock.add_response(
            url=re.compile(r".*worldbank.*"),
            json=fixture_data,
        )

        # Create mock cache manager that returns None (cache miss)
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()

        adapter = self._adapter_with_country_lookup(cache=mock_cache)
        result = await adapter.query(QueryParams(query="GDP United States"))

        # Verify cache was checked
        mock_cache.get.assert_called_once()

        # Verify result was cached
        mock_cache.set.assert_called_once()

        # Verify result is from API
        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 5

    @pytest.mark.asyncio
    async def test_health_check_success(self, httpx_mock) -> None:
        """Health check returns True when API responds."""
        httpx_mock.add_response(
            url=re.compile(r".*worldbank.*"),
            status_code=200,
        )

        adapter = WorldBankAdapter()
        result = await adapter.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, httpx_mock) -> None:
        """Health check returns False on connection error."""
        httpx_mock.add_exception(
            httpx.ConnectError("Connection failed"),
            url=re.compile(r".*worldbank.*"),
        )

        adapter = WorldBankAdapter()
        result = await adapter.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_close_cleans_up_client(self) -> None:
        """Close method cleans up the HTTP client."""
        adapter = WorldBankAdapter()
        # Initialize client by accessing it
        await adapter._get_client()
        assert adapter._client is not None

        await adapter.close()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_ensure_country_lookup_fetches_countries(self, httpx_mock) -> None:
        """Country lookup fetches countries from World Bank API."""
        # Mock response with sample countries
        country_response = [
            {"page": 1, "pages": 1, "per_page": 400, "total": 3},
            [
                {"id": "VEN", "name": "Venezuela, RB", "iso2Code": "VE"},
                {"id": "MEX", "name": "Mexico", "iso2Code": "MX"},
                {"id": "ARG", "name": "Argentina", "iso2Code": "AR"},
            ],
        ]
        httpx_mock.add_response(
            url=re.compile(r".*country\?format=json.*"),
            json=country_response,
        )

        adapter = WorldBankAdapter()
        lookup = await adapter._ensure_country_lookup()

        # Verify countries are in lookup
        assert lookup["venezuela, rb"] == "VEN"
        assert lookup["mexico"] == "MEX"
        assert lookup["argentina"] == "ARG"
        # ISO2 codes
        assert lookup["ve"] == "VEN"
        assert lookup["mx"] == "MEX"
        # ISO3 codes
        assert lookup["ven"] == "VEN"
        assert lookup["mex"] == "MEX"

    @pytest.mark.asyncio
    async def test_ensure_country_lookup_caches_result(self, httpx_mock) -> None:
        """Country lookup is cached after first fetch."""
        country_response = [
            {"page": 1, "pages": 1, "per_page": 400, "total": 1},
            [{"id": "USA", "name": "United States", "iso2Code": "US"}],
        ]
        httpx_mock.add_response(
            url=re.compile(r".*country\?format=json.*"),
            json=country_response,
        )

        adapter = WorldBankAdapter()

        # First call fetches
        lookup1 = await adapter._ensure_country_lookup()
        # Second call uses cache
        lookup2 = await adapter._ensure_country_lookup()

        assert lookup1 is lookup2
        # Only one HTTP request should have been made
        assert len(httpx_mock.get_requests()) == 1

    @pytest.mark.asyncio
    async def test_ensure_country_lookup_falls_back_on_error(self, httpx_mock) -> None:
        """Country lookup falls back to aliases on API error."""
        httpx_mock.add_exception(
            httpx.ConnectError("Connection failed"),
            url=re.compile(r".*country\?format=json.*"),
        )

        adapter = WorldBankAdapter()
        lookup = await adapter._ensure_country_lookup()

        # Should still have hardcoded aliases
        assert lookup["usa"] == "USA"
        assert lookup["uk"] == "GBR"
        # But no dynamic countries
        assert "venezuela" not in lookup
