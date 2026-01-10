"""Tests for conflict_analysis tool."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from ignifer.adapters.base import AdapterTimeoutError
from ignifer.models import (
    ConfidenceLevel,
    OSINTResult,
    QualityTier,
    ResultStatus,
    SourceAttribution,
    SourceMetadata,
)
from ignifer.server import conflict_analysis


def _create_mock_conflict_result(
    country: str = "Ethiopia",
    total_events: int = 127,
    total_fatalities: int = 342,
    with_trends: bool = True,
) -> OSINTResult:
    """Create a mock ACLED result for testing."""
    summary: dict[str, str | int | float | bool | None] = {
        "summary_type": "conflict_analysis",
        "country": country,
        "total_events": total_events,
        "total_fatalities": total_fatalities,
        "date_range_start": "2025-12-10",
        "date_range_end": "2026-01-09",
        "event_type_battles": 45,
        "event_type_violence_against_civilians": 38,
        "event_type_protests": 24,
        "event_type_explosions_remote_violence": 12,
        "event_type_strategic_developments": 8,
        "top_actor_1_name": "Ethiopian National Defense Force",
        "top_actor_1_count": 52,
        "top_actor_2_name": "Fano Militia",
        "top_actor_2_count": 34,
        "top_actor_3_name": "Oromo Liberation Army (OLA)",
        "top_actor_3_count": 28,
        "affected_regions": "Amhara Region, Oromia Region, Tigray Region, SNNPR",
    }

    if with_trends:
        summary.update({
            "event_trend": "increasing",
            "fatality_trend": "increasing",
            "previous_period_start": "2025-11-10",
            "previous_period_end": "2025-12-09",
            "previous_period_events": 103,
            "previous_period_fatalities": 278,
        })

    return OSINTResult(
        status=ResultStatus.SUCCESS,
        query=country,
        results=[summary],
        sources=[
            SourceAttribution(
                source="acled",
                quality=QualityTier.HIGH,
                confidence=ConfidenceLevel.VERY_LIKELY,
                metadata=SourceMetadata(
                    source_name="acled",
                    source_url="https://api.acleddata.com/acled/read",
                    retrieved_at=datetime.now(timezone.utc),
                ),
            )
        ],
        retrieved_at=datetime.now(timezone.utc),
    )


class TestConflictAnalysisTool:
    @pytest.mark.asyncio
    async def test_conflict_analysis_success(self) -> None:
        """Conflict analysis returns formatted output on success."""
        mock_result = _create_mock_conflict_result()

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia")

            assert "CONFLICT ANALYSIS" in result
            assert "ETHIOPIA" in result.upper()
            assert "127" in result  # Total events

    @pytest.mark.asyncio
    async def test_conflict_analysis_with_time_range(self) -> None:
        """Time range parameter is passed to adapter."""
        mock_result = _create_mock_conflict_result()

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia", time_range="last 90 days")

            adapter_instance.get_events.assert_called_once_with(
                "Ethiopia", date_range="last 90 days"
            )
            assert "CONFLICT ANALYSIS" in result

    @pytest.mark.asyncio
    async def test_conflict_analysis_includes_event_types(self) -> None:
        """Event type breakdown is included in output."""
        mock_result = _create_mock_conflict_result()

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia")

            assert "EVENT TYPES" in result
            assert "Battles" in result
            assert "45" in result  # Battles count

    @pytest.mark.asyncio
    async def test_conflict_analysis_includes_actors(self) -> None:
        """Actor breakdown is included in output."""
        mock_result = _create_mock_conflict_result()

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia")

            assert "PRIMARY ACTORS" in result
            assert "Ethiopian National Defense Force" in result
            assert "52 events" in result

    @pytest.mark.asyncio
    async def test_conflict_analysis_includes_geographic_distribution(self) -> None:
        """Geographic hotspots section is included (FR20)."""
        mock_result = _create_mock_conflict_result()

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia")

            assert "GEOGRAPHIC HOTSPOTS" in result
            assert "Amhara Region" in result
            assert "Oromia Region" in result

    @pytest.mark.asyncio
    async def test_conflict_analysis_includes_trends(self) -> None:
        """Trend comparison is included when date range is specified."""
        mock_result = _create_mock_conflict_result(with_trends=True)

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia", time_range="last 30 days")

            assert "Trend:" in result or "INCREASING" in result
            assert "FATALITY TRENDS" in result

    @pytest.mark.asyncio
    async def test_conflict_analysis_no_credentials(self) -> None:
        """Missing credentials returns helpful error message with registration link."""
        mock_result = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="Ethiopia",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
            error="ACLED API credentials not configured. Register at https://acleddata.com/register/",
        )

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia")

            assert "credential" in result.lower() or "ACLED" in result
            # Verify registration link is included for user convenience
            assert "acleddata.com/register" in result

    @pytest.mark.asyncio
    async def test_conflict_analysis_no_data(self) -> None:
        """No conflict data returns appropriate message."""
        mock_result = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="Norway",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Norway")

            assert "Norway" in result
            assert "No Conflict" in result or "no data" in result.lower()

    @pytest.mark.asyncio
    async def test_conflict_analysis_rate_limited(self) -> None:
        """Rate limiting returns user-friendly message."""
        mock_result = OSINTResult(
            status=ResultStatus.RATE_LIMITED,
            query="Ethiopia",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia")

            assert "Rate Limited" in result
            assert "ACLED" in result

    @pytest.mark.asyncio
    async def test_conflict_analysis_timeout(self) -> None:
        """Timeout returns user-friendly message."""
        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.side_effect = AdapterTimeoutError("acled", 15.0)
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia")

            assert "Timed Out" in result
            assert "Ethiopia" in result

    @pytest.mark.asyncio
    async def test_conflict_analysis_source_attribution(self) -> None:
        """Output includes ACLED source attribution."""
        mock_result = _create_mock_conflict_result()

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia")

            assert "ACLED" in result
            assert "acleddata.com" in result
            assert "Data retrieved" in result

    @pytest.mark.asyncio
    async def test_conflict_analysis_summary_section(self) -> None:
        """Summary section includes total events and fatalities."""
        mock_result = _create_mock_conflict_result()

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia")

            assert "SUMMARY" in result
            assert "Total Events: 127" in result
            assert "Total Fatalities: 342" in result

    @pytest.mark.asyncio
    async def test_conflict_analysis_handles_exception(self) -> None:
        """Generic exceptions are caught and formatted."""
        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.side_effect = ValueError("Unexpected error")
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia")

            assert "Error" in result
            assert "Ethiopia" in result

    @pytest.mark.asyncio
    async def test_conflict_analysis_without_trends(self) -> None:
        """Output works when trend data is not available."""
        mock_result = _create_mock_conflict_result(with_trends=False)

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia")

            # Should still have basic info
            assert "CONFLICT ANALYSIS" in result
            assert "ETHIOPIA" in result.upper()
            assert "Total Events: 127" in result
            # But should NOT have fatality trends section
            assert "FATALITY TRENDS" not in result

    @pytest.mark.asyncio
    async def test_conflict_analysis_date_range_in_output(self) -> None:
        """Date range is shown in output when provided."""
        mock_result = _create_mock_conflict_result()

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia", time_range="last 30 days")

            assert "Period:" in result
            assert "last 30 days" in result

    @pytest.mark.asyncio
    async def test_conflict_analysis_empty_region(self) -> None:
        """Empty region input returns helpful error message."""
        result = await conflict_analysis.fn("")
        assert "provide a country or region" in result.lower()

    @pytest.mark.asyncio
    async def test_conflict_analysis_whitespace_region(self) -> None:
        """Whitespace-only region input returns helpful error message."""
        result = await conflict_analysis.fn("   ")
        assert "provide a country or region" in result.lower()

    @pytest.mark.asyncio
    async def test_conflict_analysis_geographic_hotspots_with_counts(self) -> None:
        """Geographic hotspots include event counts and percentages (FR20)."""
        # Create mock with region counts
        summary: dict[str, str | int | float | bool | None] = {
            "summary_type": "conflict_analysis",
            "country": "Ethiopia",
            "total_events": 100,
            "total_fatalities": 200,
            "date_range_start": "2025-12-10",
            "date_range_end": "2026-01-09",
            "top_region_1_name": "Amhara Region",
            "top_region_1_count": 45,
            "top_region_2_name": "Oromia Region",
            "top_region_2_count": 30,
            "top_region_3_name": "Tigray Region",
            "top_region_3_count": 25,
            "affected_regions": "Amhara Region, Oromia Region, Tigray Region",
        }

        mock_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Ethiopia",
            results=[summary],
            sources=[
                SourceAttribution(
                    source="acled",
                    quality=QualityTier.HIGH,
                    confidence=ConfidenceLevel.VERY_LIKELY,
                    metadata=SourceMetadata(
                        source_name="acled",
                        source_url="https://api.acleddata.com/acled/read",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_acled") as mock_acled:
            adapter_instance = AsyncMock()
            adapter_instance.get_events.return_value = mock_result
            mock_acled.return_value = adapter_instance

            result = await conflict_analysis.fn("Ethiopia")

            # Verify counts and percentages are shown
            assert "GEOGRAPHIC HOTSPOTS" in result
            assert "45 events" in result
            assert "45.0%" in result
            assert "Amhara Region" in result
