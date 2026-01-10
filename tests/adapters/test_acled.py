"""Tests for ACLED adapter."""

import json
import re
from pathlib import Path

import httpx
import pytest

from ignifer.adapters.acled import ACLEDAdapter
from ignifer.adapters.base import AdapterAuthError, AdapterParseError, AdapterTimeoutError
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
def mock_acled_credentials(monkeypatch):
    """Set mock ACLED credentials in environment."""
    monkeypatch.setenv("IGNIFER_ACLED_KEY", "test_acled_key_12345")
    monkeypatch.setenv("IGNIFER_ACLED_EMAIL", "test@example.com")
    reset_settings()  # Force reload with new env vars
    yield
    reset_settings()


@pytest.fixture
def clear_acled_credentials(monkeypatch):
    """Ensure no ACLED credentials are set."""
    monkeypatch.delenv("IGNIFER_ACLED_KEY", raising=False)
    monkeypatch.delenv("IGNIFER_ACLED_EMAIL", raising=False)
    reset_settings()
    yield
    reset_settings()


class TestACLEDAdapter:
    """Tests for the ACLEDAdapter class."""

    def test_source_name(self, mock_acled_credentials) -> None:
        """Test source_name property returns 'acled'."""
        adapter = ACLEDAdapter()
        assert adapter.source_name == "acled"

    def test_base_quality_tier_is_high(self, mock_acled_credentials) -> None:
        """Test base_quality_tier property returns QualityTier.HIGH."""
        adapter = ACLEDAdapter()
        assert adapter.base_quality_tier == QualityTier.HIGH

    @pytest.mark.asyncio
    async def test_query_success(self, httpx_mock, mock_acled_credentials) -> None:
        """Test successful query returns OSINTResult with SUCCESS status."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        result = await adapter.query(QueryParams(query="Burkina Faso"))

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) > 0
        assert result.sources[0].source == "acled"
        assert result.sources[0].quality == QualityTier.HIGH

        await adapter.close()

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    async def test_query_with_date_range(self, httpx_mock, mock_acled_credentials) -> None:
        """Test query with date range parameter works correctly."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        result = await adapter.query(
            QueryParams(query="Burkina Faso", time_range="last 30 days")
        )

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) > 0

        # Verify request included date parameters (may have multiple due to trend comparison)
        requests = httpx_mock.get_requests()
        assert any("event_date" in str(req.url) for req in requests)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_get_events_returns_events(self, httpx_mock, mock_acled_credentials) -> None:
        """Test get_events method returns conflict events."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        result = await adapter.get_events("Burkina Faso")

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) > 0

        # First result should be summary
        summary = result.results[0]
        assert summary.get("summary_type") == "conflict_analysis"
        assert summary.get("country") == "Burkina Faso"
        assert summary.get("total_events") == 3

        await adapter.close()

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    async def test_get_events_with_date_range(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test get_events with explicit date range."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        result = await adapter.get_events("Syria", date_range="2024-01-01|2024-01-31")

        assert result.status == ResultStatus.SUCCESS

        # Verify request included date parameters (may have multiple due to trend comparison)
        requests = httpx_mock.get_requests()
        assert any("event_date" in str(req.url) for req in requests)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_no_api_key_returns_error(self, clear_acled_credentials) -> None:
        """Test that missing API key returns helpful error message."""
        adapter = ACLEDAdapter()
        result = await adapter.query(QueryParams(query="Syria"))

        # Should return NO_DATA with error message, not raise exception
        assert result.status == ResultStatus.NO_DATA
        assert result.error is not None
        assert "ACLED" in result.error
        assert "API key" in result.error.lower() or "IGNIFER_ACLED_KEY" in result.error
        assert "email" in result.error.lower() or "IGNIFER_ACLED_EMAIL" in result.error
        # Check for registration link
        assert "https://acleddata.com/register/" in result.error

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_invalid_api_key_raises_auth_error(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that 401 response raises AdapterAuthError."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            status_code=401,
        )

        adapter = ACLEDAdapter()

        with pytest.raises(AdapterAuthError) as exc_info:
            await adapter.query(QueryParams(query="Syria"))

        assert exc_info.value.source_name == "acled"
        assert "Invalid" in str(exc_info.value) or "API key" in str(exc_info.value)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_forbidden_raises_auth_error(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that 403 response raises AdapterAuthError."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            status_code=403,
        )

        adapter = ACLEDAdapter()

        with pytest.raises(AdapterAuthError) as exc_info:
            await adapter.query(QueryParams(query="Syria"))

        assert exc_info.value.source_name == "acled"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_no_data(self, httpx_mock, mock_acled_credentials) -> None:
        """Test query returns NO_DATA status for regions with no events."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json={"status": 200, "success": True, "count": 0, "data": []},
        )

        adapter = ACLEDAdapter()
        result = await adapter.query(QueryParams(query="Antarctica"))

        assert result.status == ResultStatus.NO_DATA
        assert result.error is not None
        assert "peaceful" in result.error.lower() or "no conflict" in result.error.lower()

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_rate_limited(self, httpx_mock, mock_acled_credentials) -> None:
        """Test that 429 response returns RATE_LIMITED status."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            status_code=429,
        )

        adapter = ACLEDAdapter()
        result = await adapter.query(QueryParams(query="Syria"))

        assert result.status == ResultStatus.RATE_LIMITED
        assert result.results == []

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_timeout_raises_timeout_error(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that timeout raises AdapterTimeoutError."""
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timed out"),
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
        )

        adapter = ACLEDAdapter()

        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.query(QueryParams(query="Syria"))

        assert exc_info.value.source_name == "acled"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_malformed_response_raises_parse_error(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that invalid JSON raises AdapterParseError."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            content=b"not valid json {{{",
            status_code=200,
        )

        adapter = ACLEDAdapter()

        with pytest.raises(AdapterParseError) as exc_info:
            await adapter.query(QueryParams(query="Syria"))

        assert exc_info.value.source_name == "acled"
        assert "JSON" in str(exc_info.value)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_success(self, httpx_mock, mock_acled_credentials) -> None:
        """Test health check returns True when API responds."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json={"status": 200, "success": True, "count": 0, "data": []},
            status_code=200,
        )

        adapter = ACLEDAdapter()
        result = await adapter.health_check()

        assert result is True
        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_failure_no_credentials(
        self, clear_acled_credentials
    ) -> None:
        """Test health check returns False when credentials not configured."""
        adapter = ACLEDAdapter()
        result = await adapter.health_check()

        assert result is False
        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_failure_invalid_key(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test health check returns False when API key is invalid."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            status_code=401,
        )

        adapter = ACLEDAdapter()
        result = await adapter.health_check()

        assert result is False
        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_failure_connection_error(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test health check returns False when API fails."""
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused"),
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
        )

        adapter = ACLEDAdapter()
        result = await adapter.health_check()

        assert result is False
        await adapter.close()

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    async def test_cache_hit(self, httpx_mock, mock_acled_credentials, tmp_path) -> None:
        """Test that cached results are returned without making HTTP request."""
        from ignifer.cache import CacheManager, MemoryCache, SQLiteCache

        # Create a cache with temporary SQLite database
        db_path = tmp_path / "test_cache.db"
        cache = CacheManager(l1=MemoryCache(), l2=SQLiteCache(db_path=db_path))

        # First request - will hit API
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter(cache=cache)
        result1 = await adapter.get_events("Burkina Faso")

        assert result1.status == ResultStatus.SUCCESS

        # Verify that only one request was made to the API
        requests_made = len(httpx_mock.get_requests())
        assert requests_made == 1, "First query should have made exactly one HTTP request"

        # Second request - should hit cache, not API
        result2 = await adapter.get_events("Burkina Faso")

        assert result2.status == ResultStatus.SUCCESS

        # Verify no additional HTTP requests were made (cache hit)
        assert len(httpx_mock.get_requests()) == 1, "Second query should not have made an HTTP request (cache hit)"

        await adapter.close()
        await cache.close()

    @pytest.mark.asyncio
    async def test_results_include_event_types(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that response includes event type breakdown."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        result = await adapter.get_events("Burkina Faso")

        assert result.status == ResultStatus.SUCCESS
        summary = result.results[0]

        # Should have event type counts in summary
        assert summary.get("total_events") == 3
        # Check for flattened event type keys
        has_event_type = any(
            key.startswith("event_type_") for key in summary.keys()
        )
        assert has_event_type, "Summary should include event type breakdown"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_results_include_actors(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that response includes actor information."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        result = await adapter.get_events("Burkina Faso")

        assert result.status == ResultStatus.SUCCESS
        summary = result.results[0]

        # Should have top actors in summary
        has_actor = any(
            key.startswith("top_actor_") for key in summary.keys()
        )
        assert has_actor, "Summary should include top actors"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_results_include_fatalities(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that response includes fatality counts."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        result = await adapter.get_events("Burkina Faso")

        assert result.status == ResultStatus.SUCCESS
        summary = result.results[0]

        # Should have total fatalities in summary
        assert "total_fatalities" in summary
        # From fixture: 12 + 5 + 0 = 17
        assert summary["total_fatalities"] == 17

        await adapter.close()

    @pytest.mark.asyncio
    async def test_results_include_geographic_distribution(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that response includes geographic distribution."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        result = await adapter.get_events("Burkina Faso")

        assert result.status == ResultStatus.SUCCESS
        summary = result.results[0]

        # Should have affected regions
        assert "affected_regions" in summary
        assert summary["affected_regions"] is not None
        # From fixture: Sahel, Nord, Centre
        assert "Sahel" in str(summary["affected_regions"])

        await adapter.close()

    @pytest.mark.asyncio
    async def test_close_client(self, mock_acled_credentials) -> None:
        """Test that close() properly cleans up the HTTP client."""
        adapter = ACLEDAdapter()

        # Client is not created until first use
        assert adapter._client is None

        # After close, client should be None
        await adapter.close()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_close_client_after_use(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that close() properly cleans up HTTP client after use."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        await adapter.get_events("Burkina Faso")

        # Client should exist after use
        assert adapter._client is not None

        # After close, client should be None
        await adapter.close()
        assert adapter._client is None

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    async def test_date_range_parsing_last_days(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test parsing 'last N days' format."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        result = await adapter.get_events("Syria", date_range="last 30 days")

        assert result.status == ResultStatus.SUCCESS

        # Verify request included date parameters (may have multiple due to trend comparison)
        requests = httpx_mock.get_requests()
        assert any("event_date" in str(req.url) for req in requests)

        await adapter.close()

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    async def test_date_range_parsing_last_weeks(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test parsing 'last N weeks' format."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        result = await adapter.get_events("Syria", date_range="last 2 weeks")

        assert result.status == ResultStatus.SUCCESS

        # Verify request included date parameters (may have multiple due to trend comparison)
        requests = httpx_mock.get_requests()
        assert any("event_date" in str(req.url) for req in requests)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_api_error_response(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test handling of API-level error response."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json={"status": 400, "success": False, "error": "Invalid country"},
            status_code=200,  # API returns 200 with error in body
        )

        adapter = ACLEDAdapter()

        with pytest.raises(AdapterParseError) as exc_info:
            await adapter.query(QueryParams(query="InvalidCountry"))

        assert "Invalid country" in str(exc_info.value) or "API error" in str(exc_info.value)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_normalized_events_in_results(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that individual events are normalized and included in results."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        result = await adapter.get_events("Burkina Faso")

        assert result.status == ResultStatus.SUCCESS
        # First result is summary, rest are events
        assert len(result.results) > 1

        # Check normalized event structure
        event = result.results[1]  # First event after summary
        assert "event_id" in event
        assert "event_date" in event
        assert "event_type" in event
        assert "actor1" in event
        assert "country" in event
        assert "fatalities" in event

        await adapter.close()

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    async def test_trend_comparison_with_date_range(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that trend comparison is calculated when date range is specified."""
        # Mock current period response
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )
        # Mock previous period response (for trend comparison)
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json={
                "status": 200,
                "success": True,
                "count": 2,
                "data": [
                    {"data_id": "101", "event_date": "2023-12-01", "fatalities": 5, "event_type": "Battles"},
                    {"data_id": "102", "event_date": "2023-12-15", "fatalities": 3, "event_type": "Violence against civilians"},
                ]
            },
        )

        adapter = ACLEDAdapter()
        result = await adapter.get_events("Burkina Faso", date_range="2024-01-01|2024-01-31")

        assert result.status == ResultStatus.SUCCESS
        summary = result.results[0]

        # Should have trend comparison fields
        assert "event_trend" in summary
        assert summary["event_trend"] in ("increasing", "decreasing", "stable")
        assert "fatality_trend" in summary
        assert summary["fatality_trend"] in ("increasing", "decreasing", "stable")
        assert "previous_period_start" in summary
        assert "previous_period_end" in summary
        assert "previous_period_events" in summary
        assert "previous_period_fatalities" in summary

        await adapter.close()

    @pytest.mark.asyncio
    async def test_trend_comparison_not_included_without_date_range(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that trend comparison is not included when no date range is specified."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        result = await adapter.get_events("Burkina Faso")  # No date_range

        assert result.status == ResultStatus.SUCCESS
        summary = result.results[0]

        # Should NOT have trend comparison fields when no date range
        assert "event_trend" not in summary
        assert "fatality_trend" not in summary

        await adapter.close()

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    async def test_trend_comparison_fails_gracefully(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that trend comparison failure doesn't break the main query."""
        # Mock current period response
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )
        # Mock previous period response with error
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            status_code=500,
        )

        adapter = ACLEDAdapter()
        result = await adapter.get_events("Burkina Faso", date_range="2024-01-01|2024-01-31")

        # Main query should still succeed even if trend comparison fails
        assert result.status == ResultStatus.SUCCESS
        summary = result.results[0]

        # Trend fields should not be present if comparison failed
        assert "event_trend" not in summary
        assert "fatality_trend" not in summary

        await adapter.close()

    @pytest.mark.asyncio
    async def test_api_request_includes_email(
        self, httpx_mock, mock_acled_credentials
    ) -> None:
        """Test that API requests include email parameter."""
        httpx_mock.add_response(
            url=re.compile(r".*api\.acleddata\.com/acled/read.*"),
            json=load_fixture("acled_events.json"),
        )

        adapter = ACLEDAdapter()
        await adapter.get_events("Burkina Faso")

        # Verify request included email parameter
        request = httpx_mock.get_request()
        assert "email" in str(request.url)
        assert "test%40example.com" in str(request.url) or "test@example.com" in str(request.url)

        await adapter.close()
