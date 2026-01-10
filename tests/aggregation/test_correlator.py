"""Tests for the Correlator module."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ignifer.aggregation.correlator import (
    AggregatedResult,
    Conflict,
    Correlator,
    CorroborationStatus,
    Finding,
    SourceContribution,
)
from ignifer.config import Settings
from ignifer.models import (
    ConfidenceLevel,
    OSINTResult,
    QualityTier,
    ResultStatus,
    SourceAttribution,
    SourceMetadata,
)


class TestCorroborationStatus:
    """Tests for CorroborationStatus enum."""

    def test_corroboration_status_values(self) -> None:
        """CorroborationStatus values should match expected strings."""
        assert CorroborationStatus.CORROBORATED.value == "corroborated"
        assert CorroborationStatus.SINGLE_SOURCE.value == "single_source"
        assert CorroborationStatus.CONFLICTING.value == "conflicting"


class TestSourceContribution:
    """Tests for SourceContribution model."""

    def test_source_contribution_creation(self) -> None:
        """SourceContribution should be created with all required fields."""
        contribution = SourceContribution(
            source_name="gdelt",
            data={"title": "Test Article"},
            quality_tier=QualityTier.MEDIUM,
            retrieved_at=datetime.now(timezone.utc),
            source_url="https://api.gdeltproject.org",
        )

        assert contribution.source_name == "gdelt"
        assert contribution.data == {"title": "Test Article"}
        assert contribution.quality_tier == QualityTier.MEDIUM
        assert contribution.source_url == "https://api.gdeltproject.org"

    def test_source_contribution_optional_url(self) -> None:
        """SourceContribution should work without source_url."""
        contribution = SourceContribution(
            source_name="wikidata",
            data={"id": "Q12345"},
            quality_tier=QualityTier.HIGH,
            retrieved_at=datetime.now(timezone.utc),
        )

        assert contribution.source_url is None

    def test_source_contribution_optional_confidence(self) -> None:
        """SourceContribution should accept optional confidence field."""
        contribution = SourceContribution(
            source_name="opensanctions",
            data={"sanctioned": True},
            quality_tier=QualityTier.HIGH,
            retrieved_at=datetime.now(timezone.utc),
            confidence=ConfidenceLevel.VERY_LIKELY,
        )

        assert contribution.confidence == ConfidenceLevel.VERY_LIKELY

    def test_source_contribution_confidence_defaults_to_none(self) -> None:
        """SourceContribution confidence should default to None."""
        contribution = SourceContribution(
            source_name="gdelt",
            data={"title": "News"},
            quality_tier=QualityTier.MEDIUM,
            retrieved_at=datetime.now(timezone.utc),
        )

        assert contribution.confidence is None


class TestFinding:
    """Tests for Finding model."""

    def test_finding_creation(self) -> None:
        """Finding should be created with all required fields."""
        contribution = SourceContribution(
            source_name="gdelt",
            data={"title": "News Article"},
            quality_tier=QualityTier.MEDIUM,
            retrieved_at=datetime.now(timezone.utc),
        )

        finding = Finding(
            topic="sanctions",
            content="Entity X is sanctioned",
            sources=[contribution],
            status=CorroborationStatus.SINGLE_SOURCE,
            confidence_boost=0.0,
        )

        assert finding.topic == "sanctions"
        assert finding.content == "Entity X is sanctioned"
        assert len(finding.sources) == 1
        assert finding.status == CorroborationStatus.SINGLE_SOURCE
        assert finding.confidence_boost == 0.0

    def test_finding_corroborated(self) -> None:
        """Corroborated finding should have positive confidence boost."""
        contributions = [
            SourceContribution(
                source_name="opensanctions",
                data={"sanctioned": True},
                quality_tier=QualityTier.HIGH,
                retrieved_at=datetime.now(timezone.utc),
            ),
            SourceContribution(
                source_name="wikidata",
                data={"status": "sanctioned"},
                quality_tier=QualityTier.HIGH,
                retrieved_at=datetime.now(timezone.utc),
            ),
        ]

        finding = Finding(
            topic="sanctions",
            content="Entity is sanctioned",
            sources=contributions,
            status=CorroborationStatus.CORROBORATED,
            corroboration_note="Corroborated by [opensanctions, wikidata]",
            confidence_boost=0.2,
        )

        assert finding.status == CorroborationStatus.CORROBORATED
        assert finding.confidence_boost > 0

    def test_finding_corroboration_note_format(self) -> None:
        """Corroborated finding should have proper corroboration_note format."""
        contributions = [
            SourceContribution(
                source_name="source_a",
                data={"key": "value"},
                quality_tier=QualityTier.HIGH,
                retrieved_at=datetime.now(timezone.utc),
            ),
            SourceContribution(
                source_name="source_b",
                data={"key": "value"},
                quality_tier=QualityTier.MEDIUM,
                retrieved_at=datetime.now(timezone.utc),
            ),
        ]

        finding = Finding(
            topic="test_topic",
            content="Test content",
            sources=contributions,
            status=CorroborationStatus.CORROBORATED,
            corroboration_note="Corroborated by [source_a, source_b]",
        )

        assert finding.corroboration_note is not None
        assert "Corroborated by" in finding.corroboration_note
        assert "source_a" in finding.corroboration_note
        assert "source_b" in finding.corroboration_note

    def test_single_source_finding_note_format(self) -> None:
        """Single source finding should have proper corroboration_note format."""
        contribution = SourceContribution(
            source_name="gdelt",
            data={"title": "Unique finding"},
            quality_tier=QualityTier.MEDIUM,
            retrieved_at=datetime.now(timezone.utc),
        )

        finding = Finding(
            topic="unique_topic",
            content="Unique finding",
            sources=[contribution],
            status=CorroborationStatus.SINGLE_SOURCE,
            corroboration_note="Single source: [gdelt] - corroboration not possible",
        )

        assert finding.corroboration_note is not None
        assert "Single source" in finding.corroboration_note
        assert "corroboration not possible" in finding.corroboration_note
        assert "gdelt" in finding.corroboration_note


class TestConflict:
    """Tests for Conflict model."""

    def test_conflict_creation(self) -> None:
        """Conflict should be created with all required fields."""
        source_a = SourceContribution(
            source_name="opensanctions",
            data={"sanctioned": True},
            quality_tier=QualityTier.HIGH,
            retrieved_at=datetime.now(timezone.utc),
        )

        source_b = SourceContribution(
            source_name="wikidata",
            data={"sanctioned": False},
            quality_tier=QualityTier.HIGH,
            retrieved_at=datetime.now(timezone.utc),
        )

        conflict = Conflict(
            topic="sanctioned",
            source_a=source_a,
            source_a_value="True",
            source_b=source_b,
            source_b_value="False",
            suggested_authority=None,
        )

        assert conflict.topic == "sanctioned"
        assert conflict.source_a_value == "True"
        assert conflict.source_b_value == "False"

    def test_conflict_with_suggested_authority(self) -> None:
        """Conflict should include suggested authority when quality differs."""
        source_a = SourceContribution(
            source_name="opensanctions",
            data={"sanctioned": True},
            quality_tier=QualityTier.HIGH,
            retrieved_at=datetime.now(timezone.utc),
        )

        source_b = SourceContribution(
            source_name="news_source",
            data={"sanctioned": False},
            quality_tier=QualityTier.LOW,
            retrieved_at=datetime.now(timezone.utc),
        )

        conflict = Conflict(
            topic="sanctioned",
            source_a=source_a,
            source_a_value="True",
            source_b=source_b,
            source_b_value="False",
            suggested_authority="opensanctions",
            resolution_note="Conflicting: opensanctions says True, news_source says False",
        )

        assert conflict.suggested_authority == "opensanctions"

    def test_conflict_resolution_note_format(self) -> None:
        """Conflict resolution_note should follow the required format."""
        source_a = SourceContribution(
            source_name="source_a",
            data={"status": "active"},
            quality_tier=QualityTier.HIGH,
            retrieved_at=datetime.now(timezone.utc),
        )

        source_b = SourceContribution(
            source_name="source_b",
            data={"status": "inactive"},
            quality_tier=QualityTier.MEDIUM,
            retrieved_at=datetime.now(timezone.utc),
        )

        conflict = Conflict(
            topic="status",
            source_a=source_a,
            source_a_value="active",
            source_b=source_b,
            source_b_value="inactive",
            resolution_note="Conflicting: source_a says active, source_b says inactive",
        )

        assert conflict.resolution_note is not None
        assert "Conflicting:" in conflict.resolution_note
        assert "source_a says active" in conflict.resolution_note
        assert "source_b says inactive" in conflict.resolution_note

    def test_conflict_perspectives_property(self) -> None:
        """Conflict perspectives property should return list of both sources."""
        source_a = SourceContribution(
            source_name="opensanctions",
            data={"sanctioned": True},
            quality_tier=QualityTier.HIGH,
            retrieved_at=datetime.now(timezone.utc),
        )

        source_b = SourceContribution(
            source_name="wikidata",
            data={"sanctioned": False},
            quality_tier=QualityTier.HIGH,
            retrieved_at=datetime.now(timezone.utc),
        )

        conflict = Conflict(
            topic="sanctioned",
            source_a=source_a,
            source_a_value="True",
            source_b=source_b,
            source_b_value="False",
        )

        perspectives = conflict.perspectives
        assert len(perspectives) == 2
        assert source_a in perspectives
        assert source_b in perspectives


class TestAggregatedResult:
    """Tests for AggregatedResult model."""

    def test_aggregated_result_creation(self) -> None:
        """AggregatedResult should be created with all required fields."""
        result = AggregatedResult(
            query="Test query",
            findings=[],
            conflicts=[],
            sources_queried=["gdelt", "wikidata"],
            sources_failed=["opensky"],
            overall_confidence=0.5,
            source_attributions=[],
        )

        assert result.query == "Test query"
        assert result.sources_queried == ["gdelt", "wikidata"]
        assert result.sources_failed == ["opensky"]
        assert result.overall_confidence == 0.5

    def test_aggregated_result_defaults(self) -> None:
        """AggregatedResult should have correct defaults."""
        result = AggregatedResult(
            query="Test query",
            overall_confidence=0.5,
        )

        assert result.findings == []
        assert result.conflicts == []
        assert result.sources_queried == []
        assert result.sources_failed == []
        assert result.source_attributions == []

    def test_to_confidence_level_almost_certain(self) -> None:
        """to_confidence_level should return ALMOST_CERTAIN for >=0.95."""
        result = AggregatedResult(query="Test", overall_confidence=0.95)
        assert result.to_confidence_level() == ConfidenceLevel.ALMOST_CERTAIN

        result_high = AggregatedResult(query="Test", overall_confidence=1.0)
        assert result_high.to_confidence_level() == ConfidenceLevel.ALMOST_CERTAIN

    def test_to_confidence_level_very_likely(self) -> None:
        """to_confidence_level should return VERY_LIKELY for 0.80-0.95."""
        result = AggregatedResult(query="Test", overall_confidence=0.85)
        assert result.to_confidence_level() == ConfidenceLevel.VERY_LIKELY

    def test_to_confidence_level_likely(self) -> None:
        """to_confidence_level should return LIKELY for 0.60-0.80."""
        result = AggregatedResult(query="Test", overall_confidence=0.70)
        assert result.to_confidence_level() == ConfidenceLevel.LIKELY

    def test_to_confidence_level_even_chance(self) -> None:
        """to_confidence_level should return EVEN_CHANCE for 0.40-0.60."""
        result = AggregatedResult(query="Test", overall_confidence=0.50)
        assert result.to_confidence_level() == ConfidenceLevel.EVEN_CHANCE

    def test_to_confidence_level_unlikely(self) -> None:
        """to_confidence_level should return UNLIKELY for 0.20-0.40."""
        result = AggregatedResult(query="Test", overall_confidence=0.30)
        assert result.to_confidence_level() == ConfidenceLevel.UNLIKELY

    def test_to_confidence_level_remote(self) -> None:
        """to_confidence_level should return REMOTE for <0.20."""
        result = AggregatedResult(query="Test", overall_confidence=0.10)
        assert result.to_confidence_level() == ConfidenceLevel.REMOTE

        result_zero = AggregatedResult(query="Test", overall_confidence=0.0)
        assert result_zero.to_confidence_level() == ConfidenceLevel.REMOTE


def make_mock_adapter(
    source_name: str,
    quality_tier: QualityTier = QualityTier.MEDIUM,
    results: list[dict] | None = None,
    status: ResultStatus = ResultStatus.SUCCESS,
    should_fail: bool = False,
) -> MagicMock:
    """Create a mock adapter conforming to OSINTAdapter protocol."""
    adapter = MagicMock()
    adapter.source_name = source_name
    adapter.base_quality_tier = quality_tier

    if should_fail:
        adapter.query = AsyncMock(side_effect=Exception("Adapter failed"))
    else:
        result_data = results or []
        adapter.query = AsyncMock(
            return_value=OSINTResult(
                status=status,
                query="test",
                results=result_data,
                sources=[
                    SourceAttribution(
                        source=source_name,
                        quality=quality_tier,
                        confidence=ConfidenceLevel.LIKELY,
                        metadata=SourceMetadata(
                            source_name=source_name,
                            source_url=f"https://api.{source_name}.test",
                            retrieved_at=datetime.now(timezone.utc),
                        ),
                    )
                ],
                retrieved_at=datetime.now(timezone.utc),
            )
        )
    adapter.health_check = AsyncMock(return_value=True)
    return adapter


@pytest.fixture
def mock_gdelt_adapter() -> MagicMock:
    """Create a mock GDELT adapter."""
    return make_mock_adapter(
        "gdelt",
        QualityTier.MEDIUM,
        [
            {"title": "News about Entity X", "topic": "sanctions", "name": "Entity X"},
            {"title": "Another article", "topic": "economy", "name": "Country Y"},
        ],
    )


@pytest.fixture
def mock_opensanctions_adapter() -> MagicMock:
    """Create a mock OpenSanctions adapter."""
    return make_mock_adapter(
        "opensanctions",
        QualityTier.HIGH,
        [
            {"name": "Entity X", "sanctioned": True, "topic": "sanctions"},
            {"name": "Entity Z", "pep": True, "topic": "pep"},
        ],
    )


@pytest.fixture
def mock_wikidata_adapter() -> MagicMock:
    """Create a mock Wikidata adapter."""
    return make_mock_adapter(
        "wikidata",
        QualityTier.HIGH,
        [
            {"name": "Entity X", "description": "A sanctioned entity", "topic": "sanctions"},
        ],
    )


@pytest.fixture
def mock_failing_adapter() -> MagicMock:
    """Create a mock adapter that fails."""
    return make_mock_adapter("failing_source", should_fail=True)


@pytest.fixture
def correlator_with_mocks(
    mock_gdelt_adapter: MagicMock,
    mock_opensanctions_adapter: MagicMock,
    mock_wikidata_adapter: MagicMock,
) -> Correlator:
    """Create Correlator with mock adapters."""
    adapters = {
        "gdelt": mock_gdelt_adapter,
        "opensanctions": mock_opensanctions_adapter,
        "wikidata": mock_wikidata_adapter,
    }
    return Correlator(adapters=adapters)


class TestCorrelatorInit:
    """Tests for Correlator initialization."""

    def test_correlator_with_adapters(self, mock_gdelt_adapter: MagicMock) -> None:
        """Correlator should accept adapters dict."""
        correlator = Correlator(adapters={"gdelt": mock_gdelt_adapter})

        assert "gdelt" in correlator._adapters

    def test_correlator_with_custom_settings(self) -> None:
        """Correlator should accept custom Settings."""
        settings = Settings()
        correlator = Correlator(settings=settings)

        assert correlator._settings is settings

    def test_correlator_defaults(self) -> None:
        """Correlator should have sensible defaults."""
        correlator = Correlator()

        assert correlator._adapters == {}
        assert correlator._relevance_engine is not None
        assert correlator._settings is not None


class TestConcurrentSourceQuerying:
    """Tests for concurrent source querying."""

    @pytest.mark.asyncio
    async def test_queries_multiple_sources_concurrently(
        self, correlator_with_mocks: Correlator
    ) -> None:
        """Correlator should query multiple sources concurrently."""
        result = await correlator_with_mocks.aggregate(
            "Test query",
            sources=["gdelt", "opensanctions", "wikidata"],
        )

        assert "gdelt" in result.sources_queried
        assert "opensanctions" in result.sources_queried
        assert "wikidata" in result.sources_queried

    @pytest.mark.asyncio
    async def test_all_adapters_called(
        self,
        mock_gdelt_adapter: MagicMock,
        mock_opensanctions_adapter: MagicMock,
        correlator_with_mocks: Correlator,
    ) -> None:
        """All specified adapters should be called."""
        await correlator_with_mocks.aggregate(
            "Test query",
            sources=["gdelt", "opensanctions"],
        )

        mock_gdelt_adapter.query.assert_called_once()
        mock_opensanctions_adapter.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_adapter_handled(
        self, correlator_with_mocks: Correlator
    ) -> None:
        """Missing adapter should be handled gracefully."""
        result = await correlator_with_mocks.aggregate(
            "Test query",
            sources=["gdelt", "nonexistent_source"],
        )

        assert "gdelt" in result.sources_queried
        assert "nonexistent_source" in result.sources_failed


class TestAdapterFailureHandling:
    """Tests for handling adapter failures."""

    @pytest.mark.asyncio
    async def test_adapter_failure_continues_with_others(
        self,
        mock_gdelt_adapter: MagicMock,
        mock_failing_adapter: MagicMock,
    ) -> None:
        """One adapter failure should not stop the whole aggregation."""
        adapters = {
            "gdelt": mock_gdelt_adapter,
            "failing_source": mock_failing_adapter,
        }
        correlator = Correlator(adapters=adapters)

        result = await correlator.aggregate(
            "Test query",
            sources=["gdelt", "failing_source"],
        )

        assert "gdelt" in result.sources_queried
        assert "failing_source" in result.sources_failed

    @pytest.mark.asyncio
    async def test_all_adapters_fail_returns_empty_result(
        self, mock_failing_adapter: MagicMock
    ) -> None:
        """When all adapters fail, should return result with no findings."""
        adapters = {"failing_source": mock_failing_adapter}
        correlator = Correlator(adapters=adapters)

        result = await correlator.aggregate(
            "Test query",
            sources=["failing_source"],
        )

        assert len(result.findings) == 0
        assert "failing_source" in result.sources_failed
        assert result.overall_confidence < 0.5

    @pytest.mark.asyncio
    async def test_partial_failure_includes_successful_results(
        self,
        mock_gdelt_adapter: MagicMock,
        mock_opensanctions_adapter: MagicMock,
        mock_failing_adapter: MagicMock,
    ) -> None:
        """Partial failure should include results from successful sources."""
        adapters = {
            "gdelt": mock_gdelt_adapter,
            "opensanctions": mock_opensanctions_adapter,
            "failing_source": mock_failing_adapter,
        }
        correlator = Correlator(adapters=adapters)

        result = await correlator.aggregate(
            "Test query",
            sources=["gdelt", "opensanctions", "failing_source"],
        )

        assert len(result.sources_queried) == 2
        assert len(result.sources_failed) == 1
        assert len(result.findings) > 0


class TestCorroborationDetection:
    """Tests for corroboration detection."""

    @pytest.mark.asyncio
    async def test_corroborated_findings_marked_correctly(
        self, correlator_with_mocks: Correlator
    ) -> None:
        """When 2+ sources agree, findings should be marked as corroborated."""
        result = await correlator_with_mocks.aggregate(
            "Test query",
            sources=["gdelt", "opensanctions", "wikidata"],
        )

        # Check corroborated findings (sanctions topic has data from multiple sources)
        corroborated = [
            f for f in result.findings
            if f.status == CorroborationStatus.CORROBORATED
        ]
        assert len(corroborated) > 0

        for finding in corroborated:
            assert len(finding.sources) >= 2
            assert finding.confidence_boost > 0
            # Verify corroboration_note is set correctly
            assert finding.corroboration_note is not None
            assert "Corroborated by" in finding.corroboration_note

    @pytest.mark.asyncio
    async def test_corroborated_finding_has_multiple_sources(
        self, correlator_with_mocks: Correlator
    ) -> None:
        """Corroborated findings should have sources from multiple adapters."""
        result = await correlator_with_mocks.aggregate(
            "Test query",
            sources=["gdelt", "opensanctions", "wikidata"],
        )

        corroborated = [
            f for f in result.findings
            if f.status == CorroborationStatus.CORROBORATED
        ]

        for finding in corroborated:
            source_names = {s.source_name for s in finding.sources}
            assert len(source_names) >= 2

    @pytest.mark.asyncio
    async def test_corroboration_boosts_confidence(
        self, correlator_with_mocks: Correlator
    ) -> None:
        """Corroborated findings should have positive confidence boost."""
        result = await correlator_with_mocks.aggregate(
            "Test query",
            sources=["gdelt", "opensanctions", "wikidata"],
        )

        corroborated = [
            f for f in result.findings
            if f.status == CorroborationStatus.CORROBORATED
        ]

        for finding in corroborated:
            assert finding.confidence_boost > 0


class TestSingleSourceHandling:
    """Tests for single source handling."""

    @pytest.mark.asyncio
    async def test_single_source_findings_marked_correctly(
        self,
    ) -> None:
        """Findings from single source should be marked appropriately."""
        adapter = make_mock_adapter(
            "gdelt",
            QualityTier.MEDIUM,
            [{"title": "Unique finding", "topic": "unique_topic"}],
        )
        correlator = Correlator(adapters={"gdelt": adapter})

        result = await correlator.aggregate("Test query", sources=["gdelt"])

        single_source = [
            f for f in result.findings
            if f.status == CorroborationStatus.SINGLE_SOURCE
        ]

        assert len(single_source) > 0
        for finding in single_source:
            assert len(finding.sources) == 1
            assert finding.confidence_boost == 0.0
            # Verify corroboration_note is set correctly
            assert finding.corroboration_note is not None
            assert "Single source" in finding.corroboration_note
            assert "corroboration not possible" in finding.corroboration_note

    @pytest.mark.asyncio
    async def test_single_source_no_confidence_boost(self) -> None:
        """Single source findings should not have confidence boost."""
        adapter = make_mock_adapter(
            "opensanctions",
            QualityTier.HIGH,
            [{"name": "Entity", "topic": "standalone_topic"}],
        )
        correlator = Correlator(adapters={"opensanctions": adapter})

        result = await correlator.aggregate(
            "Test query",
            sources=["opensanctions"],
        )

        for finding in result.findings:
            assert finding.status == CorroborationStatus.SINGLE_SOURCE
            assert finding.confidence_boost == 0.0
            # Verify corroboration_note includes source name
            assert finding.corroboration_note is not None
            assert "opensanctions" in finding.corroboration_note


class TestConflictDetection:
    """Tests for conflict detection."""

    @pytest.mark.asyncio
    async def test_conflicts_detected_when_sources_disagree(self) -> None:
        """Conflicts should be detected when sources have different values."""
        adapter_a = make_mock_adapter(
            "opensanctions",
            QualityTier.HIGH,
            [{"name": "Entity X", "sanctioned": True}],
        )
        adapter_b = make_mock_adapter(
            "wikidata",
            QualityTier.HIGH,
            [{"name": "Entity X", "sanctioned": False}],
        )
        correlator = Correlator(adapters={
            "opensanctions": adapter_a,
            "wikidata": adapter_b,
        })

        result = await correlator.aggregate(
            "Test query",
            sources=["opensanctions", "wikidata"],
        )

        assert len(result.conflicts) > 0
        # Verify resolution_note is set
        for conflict in result.conflicts:
            assert conflict.resolution_note is not None
            assert "Conflicting:" in conflict.resolution_note

    @pytest.mark.asyncio
    async def test_conflict_preserves_both_perspectives(self) -> None:
        """Conflicts should include both perspectives without suppression."""
        adapter_a = make_mock_adapter(
            "source_a",
            QualityTier.HIGH,
            [{"name": "Entity", "status": "active"}],
        )
        adapter_b = make_mock_adapter(
            "source_b",
            QualityTier.MEDIUM,
            [{"name": "Entity", "status": "inactive"}],
        )
        correlator = Correlator(adapters={
            "source_a": adapter_a,
            "source_b": adapter_b,
        })

        result = await correlator.aggregate(
            "Test query",
            sources=["source_a", "source_b"],
        )

        for conflict in result.conflicts:
            # Both values should be present
            assert conflict.source_a_value is not None
            assert conflict.source_b_value is not None
            assert conflict.source_a_value != conflict.source_b_value
            # Verify resolution_note contains both source names and values
            assert conflict.resolution_note is not None
            assert "source_a" in conflict.resolution_note
            assert "source_b" in conflict.resolution_note

    @pytest.mark.asyncio
    async def test_conflict_suggests_authority_based_on_quality(self) -> None:
        """Conflicts should suggest authority based on quality tier."""
        adapter_high = make_mock_adapter(
            "high_quality",
            QualityTier.HIGH,
            [{"name": "Entity", "sanctioned": True}],
        )
        adapter_low = make_mock_adapter(
            "low_quality",
            QualityTier.LOW,
            [{"name": "Entity", "sanctioned": False}],
        )
        correlator = Correlator(adapters={
            "high_quality": adapter_high,
            "low_quality": adapter_low,
        })

        result = await correlator.aggregate(
            "Test query",
            sources=["high_quality", "low_quality"],
        )

        for conflict in result.conflicts:
            assert conflict.suggested_authority == "high_quality"

    @pytest.mark.asyncio
    async def test_no_conflict_when_same_quality_differs(self) -> None:
        """When quality tiers are equal, no authority should be suggested."""
        adapter_a = make_mock_adapter(
            "source_a",
            QualityTier.MEDIUM,
            [{"name": "Entity", "active": True}],
        )
        adapter_b = make_mock_adapter(
            "source_b",
            QualityTier.MEDIUM,
            [{"name": "Entity", "active": False}],
        )
        correlator = Correlator(adapters={
            "source_a": adapter_a,
            "source_b": adapter_b,
        })

        result = await correlator.aggregate(
            "Test query",
            sources=["source_a", "source_b"],
        )

        for conflict in result.conflicts:
            assert conflict.suggested_authority is None


class TestConfidenceCalculation:
    """Tests for overall confidence calculation."""

    @pytest.mark.asyncio
    async def test_no_findings_low_confidence(self) -> None:
        """No findings should result in low confidence."""
        adapter = make_mock_adapter("empty", results=[])
        correlator = Correlator(adapters={"empty": adapter})

        result = await correlator.aggregate("Test", sources=["empty"])

        assert result.overall_confidence < 0.5

    @pytest.mark.asyncio
    async def test_corroboration_increases_confidence(
        self, correlator_with_mocks: Correlator
    ) -> None:
        """Corroborated findings should increase overall confidence."""
        result = await correlator_with_mocks.aggregate(
            "Test query",
            sources=["gdelt", "opensanctions", "wikidata"],
        )

        # With corroborated findings, confidence should be higher
        corroborated_count = sum(
            1 for f in result.findings
            if f.status == CorroborationStatus.CORROBORATED
        )

        if corroborated_count > 0:
            assert result.overall_confidence >= 0.5

    @pytest.mark.asyncio
    async def test_conflicts_reduce_confidence(self) -> None:
        """Conflicts should reduce overall confidence."""
        adapter_a = make_mock_adapter(
            "source_a",
            QualityTier.HIGH,
            [{"name": "Entity", "sanctioned": True, "topic": "test"}],
        )
        adapter_b = make_mock_adapter(
            "source_b",
            QualityTier.HIGH,
            [{"name": "Entity", "sanctioned": False, "topic": "test"}],
        )
        correlator = Correlator(adapters={
            "source_a": adapter_a,
            "source_b": adapter_b,
        })

        result = await correlator.aggregate(
            "Test",
            sources=["source_a", "source_b"],
        )

        # With conflicts, confidence should be reduced
        if len(result.conflicts) > 0:
            assert result.overall_confidence <= 0.6

    @pytest.mark.asyncio
    async def test_confidence_clamped_to_valid_range(
        self, correlator_with_mocks: Correlator
    ) -> None:
        """Confidence should always be between 0.0 and 1.0."""
        result = await correlator_with_mocks.aggregate(
            "Test query",
            sources=["gdelt", "opensanctions", "wikidata"],
        )

        assert 0.0 <= result.overall_confidence <= 1.0


class TestSourceAttribution:
    """Tests for source attribution."""

    @pytest.mark.asyncio
    async def test_source_attributions_included(
        self, correlator_with_mocks: Correlator
    ) -> None:
        """Source attributions should be included in result."""
        result = await correlator_with_mocks.aggregate(
            "Test query",
            sources=["gdelt", "opensanctions"],
        )

        assert len(result.source_attributions) >= 2
        source_names = {a.source_name for a in result.source_attributions}
        assert "gdelt" in source_names
        assert "opensanctions" in source_names

    @pytest.mark.asyncio
    async def test_source_attribution_has_quality_tier(
        self, correlator_with_mocks: Correlator
    ) -> None:
        """Source attributions should include quality tier."""
        result = await correlator_with_mocks.aggregate(
            "Test query",
            sources=["gdelt", "opensanctions"],
        )

        for attribution in result.source_attributions:
            assert attribution.quality_tier is not None
            assert attribution.quality_tier in QualityTier

    @pytest.mark.asyncio
    async def test_source_attribution_has_url(
        self, correlator_with_mocks: Correlator
    ) -> None:
        """Source attributions should include source URL when available."""
        result = await correlator_with_mocks.aggregate(
            "Test query",
            sources=["gdelt"],
        )

        for attribution in result.source_attributions:
            assert attribution.source_url is not None


class TestRelevanceEngineIntegration:
    """Tests for SourceRelevanceEngine integration."""

    @pytest.mark.asyncio
    async def test_uses_relevance_engine_when_no_sources_specified(
        self,
        mock_gdelt_adapter: MagicMock,
        mock_opensanctions_adapter: MagicMock,
    ) -> None:
        """Should use relevance engine to select sources when none specified."""
        adapters = {
            "gdelt": mock_gdelt_adapter,
            "opensanctions": mock_opensanctions_adapter,
        }
        correlator = Correlator(adapters=adapters)

        # Query without specifying sources
        result = await correlator.aggregate("Test query about Venezuela")

        # Should have queried some sources
        assert len(result.sources_queried) > 0 or len(result.sources_failed) > 0

    @pytest.mark.asyncio
    async def test_uses_provided_sources_when_specified(
        self,
        mock_gdelt_adapter: MagicMock,
        mock_opensanctions_adapter: MagicMock,
        mock_wikidata_adapter: MagicMock,
    ) -> None:
        """Should use only provided sources when specified."""
        adapters = {
            "gdelt": mock_gdelt_adapter,
            "opensanctions": mock_opensanctions_adapter,
            "wikidata": mock_wikidata_adapter,
        }
        correlator = Correlator(adapters=adapters)

        result = await correlator.aggregate(
            "Test query",
            sources=["gdelt"],  # Only gdelt
        )

        assert "gdelt" in result.sources_queried
        assert "opensanctions" not in result.sources_queried
        assert "wikidata" not in result.sources_queried


class TestLogging:
    """Tests for logging behavior."""

    @pytest.mark.asyncio
    async def test_aggregate_logs_query(
        self,
        correlator_with_mocks: Correlator,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """aggregate() should log the query being processed."""
        import logging

        with caplog.at_level(logging.INFO):
            await correlator_with_mocks.aggregate(
                "Test query for logging",
                sources=["gdelt"],
            )

        assert any("aggregat" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_aggregate_logs_completion(
        self,
        correlator_with_mocks: Correlator,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """aggregate() should log completion info."""
        import logging

        with caplog.at_level(logging.INFO):
            await correlator_with_mocks.aggregate(
                "Test query",
                sources=["gdelt"],
            )

        assert any("complete" in record.message.lower() for record in caplog.records)
