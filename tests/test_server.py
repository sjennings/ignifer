"""Tests for FastMCP server and briefing tool."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ignifer.adapters.base import AdapterTimeoutError
from ignifer.aggregation.correlator import (
    AggregatedResult,
    Conflict,
    CorroborationStatus,
    Finding,
    SourceContribution,
)
from ignifer.aggregation.relevance import (
    RelevanceResult,
    RelevanceScore,
    SourceRelevance,
)
from ignifer.models import (
    ConfidenceLevel,
    OSINTResult,
    QualityTier,
    ResultStatus,
    SourceAttribution,
    SourceMetadata,
)
from ignifer.server import briefing, deep_dive


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
        """Briefing without time_range shows default indicator."""
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

            # Should show default time range indicator
            assert "TIME RANGE:" in result
            assert "7 days" in result
            assert "default" in result.lower()
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


class TestDeepDiveTool:
    """Tests for the deep_dive multi-source analysis tool."""

    @pytest.fixture
    def mock_relevance_result(self) -> RelevanceResult:
        """Create a mock relevance analysis result."""
        return RelevanceResult(
            query="Myanmar",
            query_type="country",
            sources=[
                SourceRelevance(
                    source_name="gdelt",
                    score=RelevanceScore.HIGH,
                    reasoning="GDELT provides comprehensive news coverage",
                    available=True,
                ),
                SourceRelevance(
                    source_name="worldbank",
                    score=RelevanceScore.HIGH,
                    reasoning="World Bank provides economic indicators",
                    available=True,
                ),
                SourceRelevance(
                    source_name="acled",
                    score=RelevanceScore.MEDIUM_HIGH,
                    reasoning="ACLED has conflict data",
                    available=False,
                    unavailable_reason="ACLED API key not configured",
                ),
                SourceRelevance(
                    source_name="wikidata",
                    score=RelevanceScore.MEDIUM,
                    reasoning="Wikidata provides entity context",
                    available=True,
                ),
                SourceRelevance(
                    source_name="opensanctions",
                    score=RelevanceScore.MEDIUM,
                    reasoning="OpenSanctions provides sanctions data",
                    available=True,
                ),
            ],
            available_sources=["gdelt", "worldbank", "wikidata", "opensanctions"],
            unavailable_sources=["acled"],
        )

    @pytest.fixture
    def mock_aggregated_result(self) -> AggregatedResult:
        """Create a mock aggregated result."""
        now = datetime.now(timezone.utc)
        return AggregatedResult(
            query="Myanmar",
            findings=[
                Finding(
                    topic="news",
                    content="Recent military conflict in Myanmar",
                    sources=[
                        SourceContribution(
                            source_name="gdelt",
                            data={"title": "Myanmar conflict"},
                            quality_tier=QualityTier.MEDIUM,
                            retrieved_at=now,
                        )
                    ],
                    status=CorroborationStatus.SINGLE_SOURCE,
                    corroboration_note="Single source: [gdelt]",
                ),
                Finding(
                    topic="economic",
                    content="Myanmar GDP declined in recent years",
                    sources=[
                        SourceContribution(
                            source_name="worldbank",
                            data={"indicator": "GDP"},
                            quality_tier=QualityTier.HIGH,
                            retrieved_at=now,
                        )
                    ],
                    status=CorroborationStatus.SINGLE_SOURCE,
                    corroboration_note="Single source: [worldbank]",
                ),
            ],
            conflicts=[],
            sources_queried=["gdelt", "worldbank"],
            sources_failed=[],
            overall_confidence=0.5,
            source_attributions=[
                SourceContribution(
                    source_name="gdelt",
                    data={"result_count": 10},
                    quality_tier=QualityTier.MEDIUM,
                    retrieved_at=now,
                ),
                SourceContribution(
                    source_name="worldbank",
                    data={"result_count": 5},
                    quality_tier=QualityTier.HIGH,
                    retrieved_at=now,
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_deep_dive_country_returns_expected_sections(
        self, mock_relevance_result: RelevanceResult, mock_aggregated_result: AggregatedResult
    ) -> None:
        """Country deep dive returns formatted output with expected sections."""
        with (
            patch("ignifer.server._get_relevance_engine") as mock_rel_engine,
            patch("ignifer.server._get_correlator") as mock_correlator,
        ):
            # Setup mocks
            rel_engine = MagicMock()
            rel_engine.analyze = AsyncMock(return_value=mock_relevance_result)
            mock_rel_engine.return_value = rel_engine

            correlator = MagicMock()
            correlator.aggregate = AsyncMock(return_value=mock_aggregated_result)
            mock_correlator.return_value = correlator

            result = await deep_dive.fn("Myanmar")

            # Check expected sections
            assert "DEEP DIVE INTELLIGENCE REPORT" in result
            assert "MYANMAR" in result
            assert "SOURCES QUERIED" in result
            assert "CORRELATION ANALYSIS" in result
            assert "SOURCE ATTRIBUTION" in result
            assert "Overall Confidence" in result

    @pytest.mark.asyncio
    async def test_deep_dive_person_returns_entity_sections(
        self, mock_aggregated_result: AggregatedResult
    ) -> None:
        """Person deep dive returns entity-related sections."""
        # Create person-specific relevance result
        person_relevance = RelevanceResult(
            query="Roman Abramovich",
            query_type="person",
            sources=[
                SourceRelevance(
                    source_name="wikidata",
                    score=RelevanceScore.HIGH,
                    reasoning="Wikidata provides entity information",
                    available=True,
                ),
                SourceRelevance(
                    source_name="opensanctions",
                    score=RelevanceScore.HIGH,
                    reasoning="OpenSanctions provides sanctions data",
                    available=True,
                ),
                SourceRelevance(
                    source_name="gdelt",
                    score=RelevanceScore.MEDIUM,
                    reasoning="GDELT may have news mentions",
                    available=True,
                ),
            ],
            available_sources=["wikidata", "opensanctions", "gdelt"],
            unavailable_sources=[],
        )

        with (
            patch("ignifer.server._get_relevance_engine") as mock_rel_engine,
            patch("ignifer.server._get_correlator") as mock_correlator,
        ):
            rel_engine = MagicMock()
            rel_engine.analyze = AsyncMock(return_value=person_relevance)
            mock_rel_engine.return_value = rel_engine

            correlator = MagicMock()
            correlator.aggregate = AsyncMock(return_value=mock_aggregated_result)
            mock_correlator.return_value = correlator

            result = await deep_dive.fn("Roman Abramovich")

            assert "DEEP DIVE INTELLIGENCE REPORT" in result
            assert "ROMAN ABRAMOVICH" in result

    @pytest.mark.asyncio
    async def test_deep_dive_focus_area_boosts_sources(
        self, mock_relevance_result: RelevanceResult, mock_aggregated_result: AggregatedResult
    ) -> None:
        """Focus parameter emphasizes correct sources."""
        with (
            patch("ignifer.server._get_relevance_engine") as mock_rel_engine,
            patch("ignifer.server._get_correlator") as mock_correlator,
        ):
            rel_engine = MagicMock()
            rel_engine.analyze = AsyncMock(return_value=mock_relevance_result)
            mock_rel_engine.return_value = rel_engine

            correlator = MagicMock()
            correlator.aggregate = AsyncMock(return_value=mock_aggregated_result)
            mock_correlator.return_value = correlator

            await deep_dive.fn("Iran", focus="sanctions")

            # Verify correlator was called
            correlator.aggregate.assert_called_once()
            # Check the sources passed include sanctions-related ones
            call_args = correlator.aggregate.call_args
            sources_called = call_args[0][1]
            # Should include opensanctions due to focus boost
            assert "opensanctions" in sources_called or "gdelt" in sources_called

    @pytest.mark.asyncio
    async def test_deep_dive_unavailable_sources_noted(
        self, mock_relevance_result: RelevanceResult, mock_aggregated_result: AggregatedResult
    ) -> None:
        """Unavailable sources are noted in output."""
        with (
            patch("ignifer.server._get_relevance_engine") as mock_rel_engine,
            patch("ignifer.server._get_correlator") as mock_correlator,
        ):
            rel_engine = MagicMock()
            rel_engine.analyze = AsyncMock(return_value=mock_relevance_result)
            mock_rel_engine.return_value = rel_engine

            correlator = MagicMock()
            correlator.aggregate = AsyncMock(return_value=mock_aggregated_result)
            mock_correlator.return_value = correlator

            result = await deep_dive.fn("Myanmar")

            # Check that unavailable source is noted
            assert "ACLED" in result or "acled" in result.lower()
            assert "not configured" in result.lower() or "SOURCES NOT QUERIED" in result

    @pytest.mark.asyncio
    async def test_deep_dive_empty_topic_returns_error(self) -> None:
        """Empty topic returns error message."""
        result = await deep_dive.fn("")

        assert "Invalid Topic" in result
        assert "Please provide a topic" in result
        assert "Examples" in result

    @pytest.mark.asyncio
    async def test_deep_dive_handles_timeout(
        self, mock_relevance_result: RelevanceResult
    ) -> None:
        """Timeout errors are handled gracefully."""
        with (
            patch("ignifer.server._get_relevance_engine") as mock_rel_engine,
            patch("ignifer.server._get_correlator") as mock_correlator,
        ):
            rel_engine = MagicMock()
            rel_engine.analyze = AsyncMock(return_value=mock_relevance_result)
            mock_rel_engine.return_value = rel_engine

            correlator = MagicMock()
            correlator.aggregate = AsyncMock(
                side_effect=AdapterTimeoutError("gdelt", 30.0)
            )
            mock_correlator.return_value = correlator

            result = await deep_dive.fn("Myanmar")

            assert "Timed Out" in result
            assert "Suggestions" in result

    @pytest.mark.asyncio
    async def test_deep_dive_handles_generic_exception(
        self, mock_relevance_result: RelevanceResult
    ) -> None:
        """Generic exceptions are caught and formatted."""
        with (
            patch("ignifer.server._get_relevance_engine") as mock_rel_engine,
            patch("ignifer.server._get_correlator") as mock_correlator,
        ):
            rel_engine = MagicMock()
            rel_engine.analyze = AsyncMock(return_value=mock_relevance_result)
            mock_rel_engine.return_value = rel_engine

            correlator = MagicMock()
            correlator.aggregate = AsyncMock(side_effect=ValueError("Unexpected error"))
            mock_correlator.return_value = correlator

            result = await deep_dive.fn("Myanmar")

            assert "Error" in result
            assert "unexpected" in result.lower()

    @pytest.mark.asyncio
    async def test_deep_dive_corroboration_displayed(self) -> None:
        """Corroborated findings are displayed with markers."""
        now = datetime.now(timezone.utc)
        # Create result with corroborated finding
        corroborated_result = AggregatedResult(
            query="Myanmar",
            findings=[
                Finding(
                    topic="conflict",
                    content="Ongoing conflict in Myanmar",
                    sources=[
                        SourceContribution(
                            source_name="gdelt",
                            data={"title": "Conflict"},
                            quality_tier=QualityTier.MEDIUM,
                            retrieved_at=now,
                        ),
                        SourceContribution(
                            source_name="acled",
                            data={"event": "Violence"},
                            quality_tier=QualityTier.HIGH,
                            retrieved_at=now,
                        ),
                    ],
                    status=CorroborationStatus.CORROBORATED,
                    corroboration_note="Corroborated by [gdelt, acled]",
                ),
            ],
            conflicts=[],
            sources_queried=["gdelt", "acled"],
            sources_failed=[],
            overall_confidence=0.7,
            source_attributions=[],
        )

        relevance_result = RelevanceResult(
            query="Myanmar",
            query_type="country",
            sources=[
                SourceRelevance(
                    source_name="gdelt",
                    score=RelevanceScore.HIGH,
                    reasoning="News coverage",
                    available=True,
                ),
                SourceRelevance(
                    source_name="acled",
                    score=RelevanceScore.HIGH,
                    reasoning="Conflict data",
                    available=True,
                ),
            ],
            available_sources=["gdelt", "acled"],
            unavailable_sources=[],
        )

        with (
            patch("ignifer.server._get_relevance_engine") as mock_rel_engine,
            patch("ignifer.server._get_correlator") as mock_correlator,
        ):
            rel_engine = MagicMock()
            rel_engine.analyze = AsyncMock(return_value=relevance_result)
            mock_rel_engine.return_value = rel_engine

            correlator = MagicMock()
            correlator.aggregate = AsyncMock(return_value=corroborated_result)
            mock_correlator.return_value = correlator

            result = await deep_dive.fn("Myanmar")

            assert "CORROBORATED" in result
            assert "gdelt" in result.lower() or "GDELT" in result

    @pytest.mark.asyncio
    async def test_deep_dive_conflicts_preserved(self) -> None:
        """Conflicting information is preserved and displayed."""
        now = datetime.now(timezone.utc)
        # Create result with conflict
        conflict_result = AggregatedResult(
            query="Test Entity",
            findings=[],
            conflicts=[
                Conflict(
                    topic="status",
                    source_a=SourceContribution(
                        source_name="sourceA",
                        data={"status": "active"},
                        quality_tier=QualityTier.MEDIUM,
                        retrieved_at=now,
                    ),
                    source_a_value="active",
                    source_b=SourceContribution(
                        source_name="sourceB",
                        data={"status": "inactive"},
                        quality_tier=QualityTier.HIGH,
                        retrieved_at=now,
                    ),
                    source_b_value="inactive",
                    suggested_authority="sourceB",
                    resolution_note="Conflicting: sourceA says active, sourceB says inactive",
                ),
            ],
            sources_queried=["sourceA", "sourceB"],
            sources_failed=[],
            overall_confidence=0.4,
            source_attributions=[],
        )

        relevance_result = RelevanceResult(
            query="Test Entity",
            query_type="general",
            sources=[
                SourceRelevance(
                    source_name="sourceA",
                    score=RelevanceScore.HIGH,
                    reasoning="Test source",
                    available=True,
                ),
                SourceRelevance(
                    source_name="sourceB",
                    score=RelevanceScore.HIGH,
                    reasoning="Test source",
                    available=True,
                ),
            ],
            available_sources=["sourceA", "sourceB"],
            unavailable_sources=[],
        )

        with (
            patch("ignifer.server._get_relevance_engine") as mock_rel_engine,
            patch("ignifer.server._get_correlator") as mock_correlator,
        ):
            rel_engine = MagicMock()
            rel_engine.analyze = AsyncMock(return_value=relevance_result)
            mock_rel_engine.return_value = rel_engine

            correlator = MagicMock()
            correlator.aggregate = AsyncMock(return_value=conflict_result)
            mock_correlator.return_value = correlator

            result = await deep_dive.fn("Test Entity")

            assert "CONFLICTS" in result
            assert "active" in result
            assert "inactive" in result

    @pytest.mark.asyncio
    async def test_deep_dive_no_sources_returns_error(self) -> None:
        """No available sources returns helpful error."""
        no_sources_result = RelevanceResult(
            query="Test",
            query_type="general",
            sources=[
                SourceRelevance(
                    source_name="acled",
                    score=RelevanceScore.HIGH,
                    reasoning="Test",
                    available=False,
                    unavailable_reason="Not configured",
                ),
            ],
            available_sources=[],
            unavailable_sources=["acled"],
        )

        with patch("ignifer.server._get_relevance_engine") as mock_rel_engine:
            rel_engine = MagicMock()
            rel_engine.analyze = AsyncMock(return_value=no_sources_result)
            mock_rel_engine.return_value = rel_engine

            result = await deep_dive.fn("Test")

            assert "No Sources Available" in result
            assert "Configure credentials" in result

    @pytest.mark.asyncio
    async def test_deep_dive_vessel_returns_maritime_sections(self) -> None:
        """Vessel deep dive returns maritime-related sections."""
        now = datetime.now(timezone.utc)
        vessel_relevance = RelevanceResult(
            query="NS Champion",
            query_type="vessel",
            sources=[
                SourceRelevance(
                    source_name="aisstream",
                    score=RelevanceScore.HIGH,
                    reasoning="AISStream tracks vessel positions",
                    available=True,
                ),
                SourceRelevance(
                    source_name="opensanctions",
                    score=RelevanceScore.MEDIUM_HIGH,
                    reasoning="OpenSanctions tracks vessel sanctions",
                    available=True,
                ),
                SourceRelevance(
                    source_name="gdelt",
                    score=RelevanceScore.MEDIUM,
                    reasoning="GDELT may have news mentions",
                    available=True,
                ),
            ],
            available_sources=["aisstream", "opensanctions", "gdelt"],
            unavailable_sources=[],
        )

        vessel_result = AggregatedResult(
            query="NS Champion",
            findings=[
                Finding(
                    topic="maritime",
                    content="Vessel NS Champion last seen in port",
                    sources=[
                        SourceContribution(
                            source_name="aisstream",
                            data={"vessel": "NS Champion"},
                            quality_tier=QualityTier.MEDIUM,
                            retrieved_at=now,
                        )
                    ],
                    status=CorroborationStatus.SINGLE_SOURCE,
                    corroboration_note="Single source: [aisstream]",
                ),
            ],
            conflicts=[],
            sources_queried=["aisstream", "opensanctions", "gdelt"],
            sources_failed=[],
            overall_confidence=0.5,
            source_attributions=[],
        )

        with (
            patch("ignifer.server._get_relevance_engine") as mock_rel_engine,
            patch("ignifer.server._get_correlator") as mock_correlator,
        ):
            rel_engine = MagicMock()
            rel_engine.analyze = AsyncMock(return_value=vessel_relevance)
            mock_rel_engine.return_value = rel_engine

            correlator = MagicMock()
            correlator.aggregate = AsyncMock(return_value=vessel_result)
            mock_correlator.return_value = correlator

            result = await deep_dive.fn("NS Champion")

            assert "DEEP DIVE INTELLIGENCE REPORT" in result
            assert "NS CHAMPION" in result
            # Verify maritime source was queried
            correlator.aggregate.assert_called_once()

    @pytest.mark.asyncio
    async def test_deep_dive_all_sources_fail_gracefully(self) -> None:
        """Deep dive handles all sources failing gracefully."""
        relevance_result = RelevanceResult(
            query="Test Topic",
            query_type="general",
            sources=[
                SourceRelevance(
                    source_name="gdelt",
                    score=RelevanceScore.HIGH,
                    reasoning="GDELT provides news",
                    available=True,
                ),
            ],
            available_sources=["gdelt"],
            unavailable_sources=[],
        )

        # All sources fail - empty findings and failed sources
        failed_result = AggregatedResult(
            query="Test Topic",
            findings=[],
            conflicts=[],
            sources_queried=[],
            sources_failed=["gdelt"],
            overall_confidence=0.0,
            source_attributions=[],
        )

        with (
            patch("ignifer.server._get_relevance_engine") as mock_rel_engine,
            patch("ignifer.server._get_correlator") as mock_correlator,
        ):
            rel_engine = MagicMock()
            rel_engine.analyze = AsyncMock(return_value=relevance_result)
            mock_rel_engine.return_value = rel_engine

            correlator = MagicMock()
            correlator.aggregate = AsyncMock(return_value=failed_result)
            mock_correlator.return_value = correlator

            result = await deep_dive.fn("Test Topic")

            # Should still return a valid report, even if empty
            assert "DEEP DIVE INTELLIGENCE REPORT" in result
            assert "No findings" in result or "REMOTE" in result


# ============================================================================
# RIGOR MODE INTEGRATION TESTS
# ============================================================================

from ignifer.config import reset_settings
from ignifer.server import entity_lookup, sanctions_check


class TestBriefingRigorMode:
    """Integration tests for briefing tool with rigor mode."""

    @pytest.mark.asyncio
    async def test_briefing_rigor_mode_includes_confidence_language(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Briefing with rigor=True includes ICD 203 confidence language."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "false")

        mock_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Ukraine",
            results=[{"title": "Test", "domain": "test.com", "url": "https://test.com"}],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/",
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

            result = await briefing.fn("Ukraine", rigor=True)

            # Should include IC confidence language
            assert "RIGOR MODE ANALYSIS" in result
            assert "Confidence Assessment" in result
            # ICD 203 confidence phrasing
            assert "confidence" in result.lower()
            assert "assess" in result.lower()

    @pytest.mark.asyncio
    async def test_briefing_rigor_mode_includes_bibliography(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Briefing with rigor=True includes bibliography section."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "false")

        mock_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Syria",
            results=[{"title": "Test", "domain": "test.com", "url": "https://test.com"}],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/",
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

            result = await briefing.fn("Syria", rigor=True)

            # Should include bibliography section
            assert "Sources" in result or "SOURCES" in result
            # Should include analytical caveats
            assert "Caveats" in result
            # Should include source attribution
            assert "GDELT" in result

    @pytest.mark.asyncio
    async def test_briefing_default_no_rigor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Briefing without rigor param uses global default (False)."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "false")

        mock_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Taiwan",
            results=[{"title": "Test", "domain": "test.com", "url": "https://test.com"}],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/",
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

            # Should NOT include rigor mode sections
            assert "RIGOR MODE ANALYSIS" not in result
            # Standard output should still work
            assert "INTELLIGENCE BRIEFING" in result


class TestDeepDiveRigorMode:
    """Integration tests for deep_dive tool with rigor mode."""

    @pytest.fixture
    def mock_relevance_result(self) -> RelevanceResult:
        """Create a mock relevance analysis result."""
        return RelevanceResult(
            query="Myanmar",
            query_type="country",
            sources=[
                SourceRelevance(
                    source_name="gdelt",
                    score=RelevanceScore.HIGH,
                    reasoning="GDELT provides news coverage",
                    available=True,
                ),
            ],
            available_sources=["gdelt"],
            unavailable_sources=[],
        )

    @pytest.fixture
    def mock_aggregated_result(self) -> AggregatedResult:
        """Create a mock aggregated result."""
        now = datetime.now(timezone.utc)
        return AggregatedResult(
            query="Myanmar",
            findings=[
                Finding(
                    topic="news",
                    content="Recent events in Myanmar",
                    sources=[
                        SourceContribution(
                            source_name="gdelt",
                            data={"title": "Myanmar news"},
                            quality_tier=QualityTier.MEDIUM,
                            retrieved_at=now,
                        )
                    ],
                    status=CorroborationStatus.SINGLE_SOURCE,
                    corroboration_note="Single source: [gdelt]",
                ),
            ],
            conflicts=[],
            sources_queried=["gdelt"],
            sources_failed=[],
            overall_confidence=0.6,
            source_attributions=[],
        )

    @pytest.mark.asyncio
    async def test_deep_dive_rigor_mode_includes_ic_assessment(
        self,
        mock_relevance_result: RelevanceResult,
        mock_aggregated_result: AggregatedResult,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Deep dive with rigor=True includes IC-standard confidence assessment."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "false")

        with (
            patch("ignifer.server._get_relevance_engine") as mock_rel_engine,
            patch("ignifer.server._get_correlator") as mock_correlator,
        ):
            rel_engine = MagicMock()
            rel_engine.analyze = AsyncMock(return_value=mock_relevance_result)
            mock_rel_engine.return_value = rel_engine

            correlator = MagicMock()
            correlator.aggregate = AsyncMock(return_value=mock_aggregated_result)
            mock_correlator.return_value = correlator

            result = await deep_dive.fn("Myanmar", rigor=True)

            # Should include rigor mode section
            assert "RIGOR MODE ANALYSIS" in result
            # Should include IC-standard confidence assessment
            assert "Confidence Assessment" in result
            # ICD 203 language
            assert "assess" in result.lower()

    @pytest.mark.asyncio
    async def test_deep_dive_rigor_mode_includes_source_attribution(
        self,
        mock_relevance_result: RelevanceResult,
        mock_aggregated_result: AggregatedResult,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Deep dive with rigor=True includes full source attribution."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "false")

        with (
            patch("ignifer.server._get_relevance_engine") as mock_rel_engine,
            patch("ignifer.server._get_correlator") as mock_correlator,
        ):
            rel_engine = MagicMock()
            rel_engine.analyze = AsyncMock(return_value=mock_relevance_result)
            mock_rel_engine.return_value = rel_engine

            correlator = MagicMock()
            correlator.aggregate = AsyncMock(return_value=mock_aggregated_result)
            mock_correlator.return_value = correlator

            result = await deep_dive.fn("Myanmar", rigor=True)

            # Should include analytical caveats
            assert "Caveats" in result
            # Should include bibliography
            assert "Sources" in result or "SOURCES" in result


class TestEntityLookupRigorMode:
    """Integration tests for entity_lookup tool with rigor mode."""

    @pytest.mark.asyncio
    async def test_entity_lookup_rigor_includes_match_confidence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Entity lookup with rigor=True includes explicit match confidence (FR31)."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "false")

        mock_entity_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Gazprom",
            results=[
                {
                    "qid": "Q102673",
                    "label": "Gazprom",
                    "description": "Russian energy company",
                    "instance_of": "company",
                    "url": "https://www.wikidata.org/wiki/Q102673",
                }
            ],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        # Mock both resolution and Wikidata lookup
        with (
            patch("ignifer.server._get_entity_resolver") as mock_resolver,
            patch("ignifer.server._get_wikidata") as mock_wikidata,
        ):
            # Setup resolver mock
            resolver_instance = MagicMock()
            resolution_mock = MagicMock()
            resolution_mock.is_successful.return_value = True
            resolution_mock.wikidata_qid = "Q102673"
            resolution_mock.resolution_tier.value = "exact"
            resolution_mock.match_confidence = 0.95
            resolution_mock.suggestions = []
            resolver_instance.resolve = AsyncMock(return_value=resolution_mock)
            mock_resolver.return_value = resolver_instance

            # Setup wikidata mock
            wikidata_instance = AsyncMock()
            wikidata_instance.lookup_by_qid.return_value = mock_entity_result
            mock_wikidata.return_value = wikidata_instance

            result = await entity_lookup.fn(name="Gazprom", rigor=True)

            # Should include rigor mode section
            assert "RIGOR MODE ANALYSIS" in result
            # Should include match confidence (FR31)
            assert "Match Confidence" in result
            # Should show percentage
            assert "95%" in result or "confidence" in result.lower()
            # Should include analytical caveats
            assert "Caveats" in result


class TestSanctionsCheckRigorMode:
    """Integration tests for sanctions_check tool with rigor mode."""

    @pytest.mark.asyncio
    async def test_sanctions_check_rigor_includes_match_confidence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sanctions check with rigor=True includes explicit match confidence (FR31)."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "false")

        # Use properly structured result data that matches OSINTResult expectations
        mock_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Rosneft",
            results=[
                {
                    "entity_id": "NK-12345",
                    "caption": "Rosneft Oil Company",
                    "schema": "Company",
                    "name": "Rosneft Oil Company",
                    "aliases": "Rosneft Corp",
                    "birth_date": None,
                    "nationality": "ru",
                    "position": "",
                    "sanctions_lists": "us_ofac_sdn, eu_fsf",
                    "sanctions_count": 2,
                    "is_sanctioned": True,
                    "is_pep": False,
                    "is_poi": False,
                    "first_seen": "2014-07-16",
                    "last_seen": "2024-01-15",
                    "referents": None,
                    "referents_count": 0,
                    "url": "https://www.opensanctions.org/entities/NK-12345",
                    "match_score": 0.92,
                    "match_confidence": "VERY_LIKELY",
                }
            ],
            sources=[
                SourceAttribution(
                    source="opensanctions",
                    quality=QualityTier.HIGH,
                    confidence=ConfidenceLevel.VERY_LIKELY,
                    metadata=SourceMetadata(
                        source_name="opensanctions",
                        source_url="https://api.opensanctions.org/match/default",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn(entity="Rosneft", rigor=True)

            # Should include rigor mode section
            assert "RIGOR MODE ANALYSIS" in result
            # Should include match confidence (FR31)
            assert "Match Confidence" in result
            # Should show assessment
            assert "confidence" in result.lower()
            # Should include analytical caveats
            assert "Caveats" in result
            # Should include bibliography
            assert "Sources" in result or "SOURCES" in result


class TestRigorModeResolution:
    """Integration tests for rigor mode parameter vs global resolution."""

    @pytest.mark.asyncio
    async def test_rigor_param_overrides_global_setting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit rigor=False should override global IGNIFER_RIGOR_MODE=true."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "true")

        mock_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Iran",
            results=[{"title": "Test", "domain": "test.com", "url": "https://test.com"}],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/",
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

            # Global is true but param is False - should NOT have rigor output
            result = await briefing.fn("Iran", rigor=False)

            # Should NOT include rigor mode sections
            assert "RIGOR MODE ANALYSIS" not in result
            # Standard output should still work
            assert "INTELLIGENCE BRIEFING" in result

    @pytest.mark.asyncio
    async def test_global_rigor_mode_applies_when_param_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When rigor param is None, global IGNIFER_RIGOR_MODE=true should apply."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "true")

        mock_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="China",
            results=[{"title": "Test", "domain": "test.com", "url": "https://test.com"}],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/",
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

            # No rigor param - should use global (True)
            result = await briefing.fn("China")

            # Should include rigor mode sections due to global setting
            assert "RIGOR MODE ANALYSIS" in result
            assert "Confidence Assessment" in result
