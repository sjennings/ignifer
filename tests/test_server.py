"""Tests for FastMCP server and briefing tool."""

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
from ignifer.server import briefing


class TestBriefingTool:
    @pytest.mark.asyncio
    async def test_briefing_success(self) -> None:
        """Briefing tool returns formatted output on success."""
        mock_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Taiwan",
            results=[{"title": "Test", "domain": "test.com"}],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_adapter") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.query.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await briefing.fn("Taiwan")

            assert "INTELLIGENCE BRIEFING" in result
            assert "TAIWAN" in result  # Uppercase in header
            assert "KEY ASSESSMENT" in result

    @pytest.mark.asyncio
    async def test_briefing_timeout_returns_friendly_message(self) -> None:
        """Timeout errors return user-friendly message."""
        with patch("ignifer.server._get_adapter") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.query.side_effect = AdapterTimeoutError("gdelt", 10.0)
            mock_adapter.return_value = adapter_instance

            result = await briefing.fn("Taiwan")

            assert "Timed Out" in result
            assert "Taiwan" in result
            assert "Suggestions" in result

    @pytest.mark.asyncio
    async def test_briefing_no_data_returns_suggestions(self) -> None:
        """No data results include helpful suggestions."""
        mock_result = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="xyznonexistent",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
            error="Try broader terms",
        )

        with patch("ignifer.server._get_adapter") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.query.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await briefing.fn("xyznonexistent")

            assert "NO DATA AVAILABLE" in result
            assert "xyznonexistent" in result

    @pytest.mark.asyncio
    async def test_briefing_handles_generic_exception(self) -> None:
        """Generic exceptions are caught and formatted."""
        with patch("ignifer.server._get_adapter") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.query.side_effect = ValueError("Unexpected error")
            mock_adapter.return_value = adapter_instance

            result = await briefing.fn("test")

            assert "Error" in result

    @pytest.mark.asyncio
    async def test_briefing_with_time_range(self) -> None:
        """Briefing tool accepts and uses time_range parameter."""
        mock_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Syria",
            results=[{"title": "Test", "domain": "test.com"}],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_adapter") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.query.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await briefing.fn("Syria", time_range="last 48 hours")

            # Check that time_range appears in output
            assert "TIME RANGE: last 48 hours" in result
            assert "SYRIA" in result

            # Verify query was called with time_range
            adapter_instance.query.assert_called_once()
            call_args = adapter_instance.query.call_args
            assert call_args[0][0].query == "Syria"
            assert call_args[0][0].time_range == "last 48 hours"

    @pytest.mark.asyncio
    async def test_briefing_invalid_time_range_returns_error(self) -> None:
        """Invalid time_range returns error message with examples."""
        result = await briefing.fn("Syria", time_range="yesterday")

        assert "Invalid Time Range" in result
        assert "yesterday" in result
        assert "Supported formats" in result
        assert "last 24 hours" in result
        assert "Examples" in result

    @pytest.mark.asyncio
    async def test_briefing_default_time_range(self) -> None:
        """Briefing without time_range uses default (no TIME RANGE line)."""
        mock_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Ukraine",
            results=[{"title": "Test", "domain": "test.com"}],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_adapter") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.query.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await briefing.fn("Ukraine")

            # Should not have TIME RANGE line when not specified
            assert "TIME RANGE:" not in result
            assert "UKRAINE" in result

            # Verify query was called with time_range=None
            adapter_instance.query.assert_called_once()
            call_args = adapter_instance.query.call_args
            assert call_args[0][0].time_range is None

    @pytest.mark.asyncio
    async def test_briefing_rate_limited(self) -> None:
        """Rate limited results are properly formatted."""
        mock_result = OSINTResult(
            status=ResultStatus.RATE_LIMITED,
            query="test",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_adapter") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.query.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await briefing.fn("test")

            assert "RATE LIMITED" in result or "rate limiting" in result.lower()
