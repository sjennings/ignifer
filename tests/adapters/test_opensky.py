"""Tests for OpenSky Network adapter."""

import json
import re
from pathlib import Path

import httpx
import pytest

from ignifer.adapters.base import AdapterAuthError, AdapterTimeoutError
from ignifer.adapters.opensky import OpenSkyAdapter
from ignifer.config import reset_settings
from ignifer.models import QualityTier, QueryParams, ResultStatus


def load_fixture(name: str) -> dict:
    """Load JSON fixture file."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / name
    return json.loads(fixture_path.read_text())


@pytest.fixture(autouse=True)
def reset_settings_fixture():
    """Reset settings singleton before each test."""
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def mock_opensky_credentials(monkeypatch):
    """Set mock OpenSky credentials in environment."""
    monkeypatch.setenv("IGNIFER_OPENSKY_USERNAME", "test_user")
    monkeypatch.setenv("IGNIFER_OPENSKY_PASSWORD", "test_pass")
    reset_settings()  # Force reload with new env vars
    yield
    reset_settings()


@pytest.fixture
def clear_opensky_credentials(monkeypatch):
    """Ensure no OpenSky credentials are set."""
    monkeypatch.delenv("IGNIFER_OPENSKY_USERNAME", raising=False)
    monkeypatch.delenv("IGNIFER_OPENSKY_PASSWORD", raising=False)
    reset_settings()
    yield
    reset_settings()


class TestOpenSkyAdapter:
    def test_source_name(self, mock_opensky_credentials) -> None:
        adapter = OpenSkyAdapter()
        assert adapter.source_name == "opensky"

    def test_base_quality_tier(self, mock_opensky_credentials) -> None:
        adapter = OpenSkyAdapter()
        assert adapter.base_quality_tier == QualityTier.HIGH

    @pytest.mark.asyncio
    async def test_query_success(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test successful query by callsign returns OSINTResult with SUCCESS status."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            json=load_fixture("opensky_states.json"),
        )

        adapter = OpenSkyAdapter()
        result = await adapter.query(QueryParams(query="UAL123"))

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 1  # Only UAL123 matches
        assert result.results[0]["callsign"] == "UAL123"
        assert result.results[0]["icao24"] == "abc123"
        assert len(result.sources) == 1
        assert result.sources[0].source == "opensky"
        assert result.sources[0].quality == QualityTier.HIGH

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_multiple_matches(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test query matching multiple aircraft."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            json=load_fixture("opensky_states.json"),
        )

        adapter = OpenSkyAdapter()
        result = await adapter.query(QueryParams(query="UAL"))

        assert result.status == ResultStatus.SUCCESS
        # UAL123 and UAL456 should match
        assert len(result.results) == 2

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_no_match(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test query with no matching callsign returns NO_DATA status."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            json=load_fixture("opensky_states.json"),
        )

        adapter = OpenSkyAdapter()
        result = await adapter.query(QueryParams(query="ZZZZZ"))

        assert result.status == ResultStatus.NO_DATA
        assert result.error is not None
        assert "ZZZZZ" in result.error

        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_states_with_icao24(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test get_states with specific ICAO24 returns state vector."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            json=load_fixture("opensky_states.json"),
        )

        adapter = OpenSkyAdapter()
        result = await adapter.get_states(icao24="abc123")

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 3  # Returns all states from fixture
        assert result.sources[0].source == "opensky"

        # Verify request included icao24 parameter
        request = httpx_mock.get_request()
        assert "icao24=abc123" in str(request.url)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_states_all(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test get_states without ICAO24 returns all states."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            json=load_fixture("opensky_states.json"),
        )

        adapter = OpenSkyAdapter()
        result = await adapter.get_states()

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 3
        assert result.query == "all"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_track(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test get_track returns flight history ordered chronologically."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/tracks/all.*"),
            json=load_fixture("opensky_track.json"),
        )

        adapter = OpenSkyAdapter()
        result = await adapter.get_track(icao24="abc123")

        assert result.status == ResultStatus.SUCCESS
        # Each waypoint is a separate result item (flat structure)
        assert len(result.results) == 12

        # All waypoints should have track metadata
        for waypoint in result.results:
            assert waypoint["icao24"] == "abc123"
            assert waypoint["callsign"] == "UAL123"

        # Verify chronological order
        timestamps = [wp["timestamp"] for wp in result.results]
        assert timestamps == sorted(timestamps)

        # Verify request parameters
        request = httpx_mock.get_request()
        assert "icao24=abc123" in str(request.url)
        assert "time=0" in str(request.url)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_no_credentials_raises_auth_error(
        self, httpx_mock, clear_opensky_credentials
    ) -> None:
        """Test that missing credentials raises AdapterAuthError with helpful message."""
        adapter = OpenSkyAdapter()

        with pytest.raises(AdapterAuthError) as exc_info:
            await adapter.query(QueryParams(query="UAL123"))

        assert exc_info.value.source_name == "opensky"
        assert "IGNIFER_OPENSKY_USERNAME" in str(exc_info.value)
        assert "IGNIFER_OPENSKY_PASSWORD" in str(exc_info.value)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_invalid_credentials_raises_auth_error(
        self, httpx_mock, mock_opensky_credentials
    ) -> None:
        """Test that 401 response raises AdapterAuthError."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            status_code=401,
        )

        adapter = OpenSkyAdapter()

        with pytest.raises(AdapterAuthError) as exc_info:
            await adapter.query(QueryParams(query="UAL123"))

        assert exc_info.value.source_name == "opensky"
        assert "Invalid credentials" in str(exc_info.value)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_rate_limited_returns_rate_limited_status(
        self, httpx_mock, mock_opensky_credentials
    ) -> None:
        """Test that 429 response returns OSINTResult with RATE_LIMITED status."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            status_code=429,
        )

        adapter = OpenSkyAdapter()
        result = await adapter.query(QueryParams(query="UAL123"))

        assert result.status == ResultStatus.RATE_LIMITED
        assert result.results == []

        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_states_rate_limited(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test get_states with rate limiting."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            status_code=429,
        )

        adapter = OpenSkyAdapter()
        result = await adapter.get_states(icao24="abc123")

        assert result.status == ResultStatus.RATE_LIMITED

        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_track_rate_limited(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test get_track with rate limiting."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/tracks/all.*"),
            status_code=429,
        )

        adapter = OpenSkyAdapter()
        result = await adapter.get_track(icao24="abc123")

        assert result.status == ResultStatus.RATE_LIMITED

        await adapter.close()

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(
        self, httpx_mock, mock_opensky_credentials
    ) -> None:
        """Test timeout raises AdapterTimeoutError."""
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timed out"),
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
        )

        adapter = OpenSkyAdapter()

        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.query(QueryParams(query="UAL123"))

        assert exc_info.value.source_name == "opensky"
        assert exc_info.value.__cause__ is not None

        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_states_timeout(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test get_states timeout raises AdapterTimeoutError."""
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timed out"),
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
        )

        adapter = OpenSkyAdapter()

        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.get_states(icao24="abc123")

        assert exc_info.value.source_name == "opensky"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_track_timeout(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test get_track timeout raises AdapterTimeoutError."""
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timed out"),
            url=re.compile(r".*opensky-network\.org/api/tracks/all.*"),
        )

        adapter = OpenSkyAdapter()

        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.get_track(icao24="abc123")

        assert exc_info.value.source_name == "opensky"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_track_not_found(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test get_track with 404 returns NO_DATA status."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/tracks/all.*"),
            status_code=404,
        )

        adapter = OpenSkyAdapter()
        result = await adapter.get_track(icao24="abc123")

        assert result.status == ResultStatus.NO_DATA
        assert result.error is not None
        assert "abc123" in result.error

        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_success(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test health check returns True when API responds."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            status_code=200,
        )

        adapter = OpenSkyAdapter()
        result = await adapter.health_check()

        assert result is True
        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_failure_no_credentials(
        self, httpx_mock, clear_opensky_credentials
    ) -> None:
        """Test health check returns False when credentials not configured."""
        adapter = OpenSkyAdapter()
        result = await adapter.health_check()

        assert result is False
        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_failure_connection_error(
        self, httpx_mock, mock_opensky_credentials
    ) -> None:
        """Test health check returns False when API fails."""
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused"),
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
        )

        adapter = OpenSkyAdapter()
        result = await adapter.health_check()

        assert result is False
        await adapter.close()

    @pytest.mark.asyncio
    async def test_empty_states_returns_no_data(
        self, httpx_mock, mock_opensky_credentials
    ) -> None:
        """Test empty states array returns NO_DATA status."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            json={"time": 1704672000, "states": []},
        )

        adapter = OpenSkyAdapter()
        result = await adapter.get_states(icao24="nonexistent")

        assert result.status == ResultStatus.NO_DATA
        assert result.error is not None

        await adapter.close()

    @pytest.mark.asyncio
    async def test_null_states_returns_no_data(
        self, httpx_mock, mock_opensky_credentials
    ) -> None:
        """Test null states returns NO_DATA status."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            json={"time": 1704672000, "states": None},
        )

        adapter = OpenSkyAdapter()
        result = await adapter.get_states(icao24="nonexistent")

        assert result.status == ResultStatus.NO_DATA

        await adapter.close()

    @pytest.mark.asyncio
    async def test_empty_track_returns_no_data(
        self, httpx_mock, mock_opensky_credentials
    ) -> None:
        """Test empty track path returns NO_DATA status."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/tracks/all.*"),
            json={"icao24": "abc123", "callsign": "UAL123", "path": []},
        )

        adapter = OpenSkyAdapter()
        result = await adapter.get_track(icao24="abc123")

        assert result.status == ResultStatus.NO_DATA
        assert result.error is not None

        await adapter.close()

    @pytest.mark.asyncio
    async def test_state_vector_parsing(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test that state vectors are parsed correctly into named fields."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            json=load_fixture("opensky_states.json"),
        )

        adapter = OpenSkyAdapter()
        result = await adapter.get_states()

        assert result.status == ResultStatus.SUCCESS
        state = result.results[0]

        # Verify all expected fields are present
        assert state["icao24"] == "abc123"
        assert state["callsign"] == "UAL123"
        assert state["origin_country"] == "United States"
        assert state["longitude"] == -122.3894
        assert state["latitude"] == 37.6213
        assert state["altitude_barometric"] == 10668.0
        assert state["on_ground"] is False
        assert state["velocity"] == 257.45
        assert state["heading"] == 142.5
        assert state["vertical_rate"] == -0.65

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_case_insensitive(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test that callsign matching is case-insensitive."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            json=load_fixture("opensky_states.json"),
        )

        adapter = OpenSkyAdapter()
        result = await adapter.query(QueryParams(query="ual123"))  # lowercase

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 1
        assert result.results[0]["callsign"] == "UAL123"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_track_icao24_lowercase(
        self, httpx_mock, mock_opensky_credentials
    ) -> None:
        """Test that ICAO24 is passed to API in lowercase."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/tracks/all.*"),
            json=load_fixture("opensky_track.json"),
        )

        adapter = OpenSkyAdapter()
        result = await adapter.get_track(icao24="ABC123")  # uppercase input

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 12  # All waypoints returned

        # Verify request used lowercase
        request = httpx_mock.get_request()
        assert "icao24=abc123" in str(request.url)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_close_client(self, mock_opensky_credentials) -> None:
        """Test that close() properly cleans up the HTTP client."""
        adapter = OpenSkyAdapter()

        # Client is not created until first use
        assert adapter._client is None

        # After close, client should be None
        await adapter.close()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_close_client_after_use(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test that close() properly cleans up HTTP client after it was used."""
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            json=load_fixture("opensky_states.json"),
        )

        adapter = OpenSkyAdapter()
        await adapter.get_states()

        # Client should exist after use
        assert adapter._client is not None

        # After close, client should be None
        await adapter.close()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test that invalid JSON response raises AdapterParseError."""
        from ignifer.adapters.base import AdapterParseError

        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            content=b"not valid json {{{",
            status_code=200,
        )

        adapter = OpenSkyAdapter()

        with pytest.raises(AdapterParseError) as exc_info:
            await adapter.query(QueryParams(query="UAL123"))

        assert exc_info.value.source_name == "opensky"
        assert "Invalid JSON" in str(exc_info.value)

        await adapter.close()

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    async def test_cache_hit(self, httpx_mock, mock_opensky_credentials, tmp_path) -> None:
        """Test that cached results are returned without making HTTP request."""
        from ignifer.cache import CacheManager, MemoryCache, SQLiteCache

        # Create a cache with temporary SQLite database
        db_path = tmp_path / "test_cache.db"
        cache = CacheManager(l1=MemoryCache(), l2=SQLiteCache(db_path=db_path))

        # First request - will hit API
        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            json=load_fixture("opensky_states.json"),
        )

        adapter = OpenSkyAdapter(cache=cache)
        result1 = await adapter.query(QueryParams(query="UAL123"))

        assert result1.status == ResultStatus.SUCCESS
        assert len(result1.results) == 1

        # Verify that only one request was made to the API
        requests_made = len(httpx_mock.get_requests())
        assert requests_made == 1, "First query should have made exactly one HTTP request"

        # Second request - should hit cache, not API
        result2 = await adapter.query(QueryParams(query="UAL123"))

        assert result2.status == ResultStatus.SUCCESS
        assert len(result2.results) == 1  # Should have same data as first result
        assert result2.results[0]["callsign"] == "UAL123"

        # Verify no additional HTTP requests were made (cache hit)
        assert len(httpx_mock.get_requests()) == 1, "Second query should not have made an HTTP request (cache hit)"

        await adapter.close()
        await cache.close()

    @pytest.mark.asyncio
    async def test_get_track_invalid_json(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test that invalid JSON response on track endpoint raises AdapterParseError."""
        from ignifer.adapters.base import AdapterParseError

        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/tracks/all.*"),
            content=b"invalid json",
            status_code=200,
        )

        adapter = OpenSkyAdapter()

        with pytest.raises(AdapterParseError) as exc_info:
            await adapter.get_track(icao24="abc123")

        assert exc_info.value.source_name == "opensky"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_states_invalid_json(self, httpx_mock, mock_opensky_credentials) -> None:
        """Test that invalid JSON response on states endpoint raises AdapterParseError."""
        from ignifer.adapters.base import AdapterParseError

        httpx_mock.add_response(
            url=re.compile(r".*opensky-network\.org/api/states/all.*"),
            content=b"<html>error</html>",
            status_code=200,
        )

        adapter = OpenSkyAdapter()

        with pytest.raises(AdapterParseError) as exc_info:
            await adapter.get_states(icao24="abc123")

        assert exc_info.value.source_name == "opensky"

        await adapter.close()
