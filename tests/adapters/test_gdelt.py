"""Tests for GDELT adapter."""

import json
import re
from pathlib import Path

import httpx
import pytest

from ignifer.adapters.base import AdapterTimeoutError
from ignifer.adapters.gdelt import GDELTAdapter, _sanitize_gdelt_query
from ignifer.models import QualityTier, QueryParams, ResultStatus


def load_fixture(name: str) -> dict:
    """Load JSON fixture file."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / name
    return json.loads(fixture_path.read_text())


class TestGDELTAdapter:
    def test_source_name(self) -> None:
        adapter = GDELTAdapter()
        assert adapter.source_name == "gdelt"

    def test_base_quality_tier(self) -> None:
        adapter = GDELTAdapter()
        assert adapter.base_quality_tier == QualityTier.MEDIUM

    @pytest.mark.asyncio
    async def test_query_success(self, httpx_mock) -> None:
        """Test successful query returns OSINTResult with SUCCESS status."""
        httpx_mock.add_response(
            url=re.compile(r".*gdeltproject.*"),
            json=load_fixture("gdelt_response.json"),
        )

        adapter = GDELTAdapter()
        result = await adapter.query(QueryParams(query="Ukraine"))

        assert result.status == ResultStatus.SUCCESS
        assert len(result.results) == 2
        assert len(result.sources) == 1
        assert result.sources[0].source == "gdelt"
        assert result.sources[0].quality == QualityTier.MEDIUM

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_empty_returns_no_data(self, httpx_mock) -> None:
        """Test empty results return NO_DATA status with error message."""
        httpx_mock.add_response(
            url=re.compile(r".*gdeltproject.*"),
            json=load_fixture("gdelt_empty.json"),
        )

        adapter = GDELTAdapter()
        result = await adapter.query(QueryParams(query="xyznonexistent123"))

        assert result.status == ResultStatus.NO_DATA
        assert result.error is not None
        assert "broader search terms" in result.error

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_timeout_raises_error(self, httpx_mock) -> None:
        """Test timeout raises AdapterTimeoutError with source name."""
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timed out"),
            url=re.compile(r".*gdeltproject.*"),
        )

        adapter = GDELTAdapter()

        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.query(QueryParams(query="Ukraine"))

        assert exc_info.value.source_name == "gdelt"
        assert exc_info.value.__cause__ is not None

        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_success(self, httpx_mock) -> None:
        """Test health check returns True when API responds."""
        httpx_mock.add_response(
            url=re.compile(r".*gdeltproject.*"),
            status_code=200,
        )

        adapter = GDELTAdapter()
        result = await adapter.health_check()

        assert result is True
        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, httpx_mock) -> None:
        """Test health check returns False when API fails."""
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused"),
            url=re.compile(r".*gdeltproject.*"),
        )

        adapter = GDELTAdapter()
        result = await adapter.health_check()

        assert result is False
        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_with_time_range_uses_timespan(self, httpx_mock) -> None:
        """Test query with time_range uses GDELT timespan parameter."""
        httpx_mock.add_response(
            url=re.compile(r".*gdeltproject.*"),
            json=load_fixture("gdelt_response.json"),
        )

        adapter = GDELTAdapter()
        result = await adapter.query(QueryParams(query="Ukraine", time_range="last 48 hours"))

        assert result.status == ResultStatus.SUCCESS

        # Check that the request included timespan=48h
        request = httpx_mock.get_request()
        assert "timespan=48h" in str(request.url)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_with_date_range_uses_datetime_params(self, httpx_mock) -> None:
        """Test query with date range uses startdatetime/enddatetime parameters."""
        httpx_mock.add_response(
            url=re.compile(r".*gdeltproject.*"),
            json=load_fixture("gdelt_response.json"),
        )

        adapter = GDELTAdapter()
        result = await adapter.query(
            QueryParams(query="Syria", time_range="2026-01-01 to 2026-01-08")
        )

        assert result.status == ResultStatus.SUCCESS

        # Check that the request included startdatetime and enddatetime
        request = httpx_mock.get_request()
        assert "startdatetime=20260101000000" in str(request.url)
        assert "enddatetime=20260108000000" in str(request.url)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_default_time_range(self, httpx_mock) -> None:
        """Test query without time_range uses default '1week' timespan."""
        httpx_mock.add_response(
            url=re.compile(r".*gdeltproject.*"),
            json=load_fixture("gdelt_response.json"),
        )

        adapter = GDELTAdapter()
        result = await adapter.query(QueryParams(query="Ukraine"))

        assert result.status == ResultStatus.SUCCESS

        # Check that the request included default timespan=1week
        request = httpx_mock.get_request()
        assert "timespan=1week" in str(request.url)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_cache_key_includes_time_range(self, httpx_mock) -> None:
        """Test that time_range is included in generated URLs."""
        httpx_mock.add_response(
            url=re.compile(r".*gdeltproject.*"),
            json=load_fixture("gdelt_response.json"),
        )

        adapter = GDELTAdapter()

        result = await adapter.query(QueryParams(query="Ukraine", time_range="last 24 hours"))
        assert result.status == ResultStatus.SUCCESS

        # Check the URL contains the correct timespan
        request = httpx_mock.get_request()
        assert "timespan=24h" in str(request.url)
        assert "query=Ukraine" in str(request.url)

        await adapter.close()


class TestSanitizeGdeltQuery:
    """Tests for _sanitize_gdelt_query function."""

    def test_quotes_hyphenated_words(self) -> None:
        """Hyphenated words are quoted for GDELT API."""
        assert _sanitize_gdelt_query("Japan-China tensions") == '"Japan-China" tensions'
        assert _sanitize_gdelt_query("F-16 fighter jets") == '"F-16" fighter jets'

    def test_leaves_normal_words_unchanged(self) -> None:
        """Non-hyphenated queries pass through unchanged."""
        assert _sanitize_gdelt_query("Ukraine conflict") == "Ukraine conflict"
        assert _sanitize_gdelt_query("Taiwan semiconductors") == "Taiwan semiconductors"

    def test_handles_multiple_hyphenated_words(self) -> None:
        """Multiple hyphenated words are all quoted."""
        result = _sanitize_gdelt_query("Japan-China US-Russia tensions")
        assert result == '"Japan-China" "US-Russia" tensions'

    def test_handles_complex_hyphenated_words(self) -> None:
        """Complex multi-hyphen words are quoted."""
        assert _sanitize_gdelt_query("step-by-step guide") == '"step-by-step" guide'

    def test_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert _sanitize_gdelt_query("") == ""
