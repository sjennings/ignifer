"""Tests for the SourceRelevanceEngine module."""

import pytest

from ignifer.aggregation.relevance import (
    QueryType,
    RelevanceResult,
    RelevanceScore,
    SourceRelevance,
    SourceRelevanceEngine,
)
from ignifer.config import Settings, reset_settings


class TestRelevanceScore:
    """Tests for RelevanceScore enum."""

    def test_relevance_score_values(self) -> None:
        """RelevanceScore values should match expected strings."""
        assert RelevanceScore.HIGH.value == "high"
        assert RelevanceScore.MEDIUM_HIGH.value == "medium_high"
        assert RelevanceScore.MEDIUM.value == "medium"
        assert RelevanceScore.LOW.value == "low"

    def test_numeric_value_ordering(self) -> None:
        """Numeric values should be ordered correctly."""
        assert RelevanceScore.HIGH.numeric_value > RelevanceScore.MEDIUM_HIGH.numeric_value
        assert RelevanceScore.MEDIUM_HIGH.numeric_value > RelevanceScore.MEDIUM.numeric_value
        assert RelevanceScore.MEDIUM.numeric_value > RelevanceScore.LOW.numeric_value

    def test_numeric_values(self) -> None:
        """Numeric values should match specification."""
        assert RelevanceScore.HIGH.numeric_value == 1.0
        assert RelevanceScore.MEDIUM_HIGH.numeric_value == 0.75
        assert RelevanceScore.MEDIUM.numeric_value == 0.5
        assert RelevanceScore.LOW.numeric_value == 0.25


class TestQueryType:
    """Tests for QueryType enum."""

    def test_query_type_values(self) -> None:
        """QueryType values should match expected strings."""
        assert QueryType.COUNTRY.value == "country"
        assert QueryType.PERSON.value == "person"
        assert QueryType.ORGANIZATION.value == "organization"
        assert QueryType.VESSEL.value == "vessel"
        assert QueryType.AIRCRAFT.value == "aircraft"
        assert QueryType.GENERAL.value == "general"


class TestSourceRelevance:
    """Tests for SourceRelevance model."""

    def test_source_relevance_creation(self) -> None:
        """SourceRelevance should be created with all required fields."""
        relevance = SourceRelevance(
            source_name="gdelt",
            score=RelevanceScore.HIGH,
            reasoning="GDELT provides comprehensive news coverage",
            available=True,
        )

        assert relevance.source_name == "gdelt"
        assert relevance.score == RelevanceScore.HIGH
        assert relevance.reasoning == "GDELT provides comprehensive news coverage"
        assert relevance.available is True
        assert relevance.unavailable_reason is None

    def test_source_relevance_unavailable(self) -> None:
        """SourceRelevance should handle unavailable sources."""
        relevance = SourceRelevance(
            source_name="opensky",
            score=RelevanceScore.HIGH,
            reasoning="OpenSky provides aircraft tracking",
            available=False,
            unavailable_reason="OpenSky requires authentication",
        )

        assert relevance.available is False
        assert relevance.unavailable_reason is not None


class TestRelevanceResult:
    """Tests for RelevanceResult model."""

    def test_relevance_result_creation(self) -> None:
        """RelevanceResult should be created with all required fields."""
        result = RelevanceResult(
            query="Deep dive on Venezuela",
            query_type="country",
            sources=[],
            available_sources=["gdelt", "worldbank"],
            unavailable_sources=["opensky"],
        )

        assert result.query == "Deep dive on Venezuela"
        assert result.query_type == "country"
        assert result.available_sources == ["gdelt", "worldbank"]
        assert result.unavailable_sources == ["opensky"]

    def test_get_high_relevance_sources(self) -> None:
        """get_high_relevance_sources should return only HIGH available sources."""
        sources = [
            SourceRelevance(
                source_name="gdelt",
                score=RelevanceScore.HIGH,
                reasoning="test",
                available=True,
            ),
            SourceRelevance(
                source_name="worldbank",
                score=RelevanceScore.HIGH,
                reasoning="test",
                available=True,
            ),
            SourceRelevance(
                source_name="opensky",
                score=RelevanceScore.HIGH,
                reasoning="test",
                available=False,
            ),
            SourceRelevance(
                source_name="wikidata",
                score=RelevanceScore.MEDIUM,
                reasoning="test",
                available=True,
            ),
        ]

        result = RelevanceResult(
            query="test",
            query_type="country",
            sources=sources,
            available_sources=["gdelt", "worldbank", "wikidata"],
            unavailable_sources=["opensky"],
        )

        high_sources = result.get_high_relevance_sources()
        assert "gdelt" in high_sources
        assert "worldbank" in high_sources
        assert "opensky" not in high_sources  # unavailable
        assert "wikidata" not in high_sources  # not HIGH


@pytest.fixture
def engine() -> SourceRelevanceEngine:
    """Create engine with default settings."""
    return SourceRelevanceEngine()


@pytest.fixture
def engine_with_all_credentials(monkeypatch: pytest.MonkeyPatch) -> SourceRelevanceEngine:
    """Create engine with all credentials configured."""
    monkeypatch.setenv("IGNIFER_OPENSKY_USERNAME", "test")
    monkeypatch.setenv("IGNIFER_OPENSKY_PASSWORD", "test")
    monkeypatch.setenv("IGNIFER_AISSTREAM_KEY", "test")
    monkeypatch.setenv("IGNIFER_ACLED_KEY", "test")
    monkeypatch.setenv("IGNIFER_ACLED_EMAIL", "test@test.com")
    reset_settings()
    engine = SourceRelevanceEngine()
    yield engine
    reset_settings()


@pytest.fixture
def engine_no_credentials(monkeypatch: pytest.MonkeyPatch) -> SourceRelevanceEngine:
    """Create engine with no optional credentials configured."""
    # Clear any existing credentials
    monkeypatch.delenv("IGNIFER_OPENSKY_USERNAME", raising=False)
    monkeypatch.delenv("IGNIFER_OPENSKY_PASSWORD", raising=False)
    monkeypatch.delenv("IGNIFER_AISSTREAM_KEY", raising=False)
    monkeypatch.delenv("IGNIFER_ACLED_KEY", raising=False)
    monkeypatch.delenv("IGNIFER_ACLED_EMAIL", raising=False)
    reset_settings()
    engine = SourceRelevanceEngine()
    yield engine
    reset_settings()


class TestCountryQueryDetection:
    """Tests for country query detection and scoring."""

    @pytest.mark.asyncio
    async def test_country_query_ranks_gdelt_high(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Country query should rank GDELT as HIGH."""
        result = await engine.analyze("Deep dive on Venezuela")

        gdelt = next(s for s in result.sources if s.source_name == "gdelt")
        assert gdelt.score == RelevanceScore.HIGH
        assert "news" in gdelt.reasoning.lower()

    @pytest.mark.asyncio
    async def test_country_query_ranks_worldbank_high(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Country query should rank World Bank as HIGH."""
        result = await engine.analyze("Deep dive on Venezuela")

        worldbank = next(s for s in result.sources if s.source_name == "worldbank")
        assert worldbank.score == RelevanceScore.HIGH
        assert "economic" in worldbank.reasoning.lower()

    @pytest.mark.asyncio
    async def test_country_query_detects_type(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Country query should be detected as country type."""
        result = await engine.analyze("What's happening in Ukraine")

        assert result.query_type == "country"

    @pytest.mark.asyncio
    async def test_conflict_region_boosts_acled(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Conflict-prone regions should boost ACLED to MEDIUM_HIGH."""
        result = await engine.analyze("Analysis of Syria")

        acled = next(s for s in result.sources if s.source_name == "acled")
        assert acled.score == RelevanceScore.MEDIUM_HIGH
        assert "conflict" in acled.reasoning.lower()

    @pytest.mark.asyncio
    async def test_non_conflict_region_acled_medium(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Non-conflict regions should have ACLED at MEDIUM."""
        result = await engine.analyze("Analysis of Japan")

        acled = next(s for s in result.sources if s.source_name == "acled")
        assert acled.score == RelevanceScore.MEDIUM

    @pytest.mark.asyncio
    async def test_country_query_ranks_tracking_sources_low(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Country query should rank OpenSky and AISStream as LOW."""
        result = await engine.analyze("Deep dive on Brazil")

        opensky = next(s for s in result.sources if s.source_name == "opensky")
        aisstream = next(s for s in result.sources if s.source_name == "aisstream")

        assert opensky.score == RelevanceScore.LOW
        assert aisstream.score == RelevanceScore.LOW


class TestPersonQueryDetection:
    """Tests for person query detection and scoring."""

    @pytest.mark.asyncio
    async def test_person_query_ranks_wikidata_high(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Person query should rank Wikidata as HIGH."""
        result = await engine.analyze("individual Oleg Deripaska oligarch")

        wikidata = next(s for s in result.sources if s.source_name == "wikidata")
        assert wikidata.score == RelevanceScore.HIGH
        reasoning_lower = wikidata.reasoning.lower()
        assert "entity" in reasoning_lower or "people" in reasoning_lower

    @pytest.mark.asyncio
    async def test_person_query_ranks_opensanctions_high(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Person query should rank OpenSanctions as HIGH."""
        result = await engine.analyze("Background check on this oligarch")

        opensanctions = next(
            s for s in result.sources if s.source_name == "opensanctions"
        )
        assert opensanctions.score == RelevanceScore.HIGH
        reasoning_lower = opensanctions.reasoning.lower()
        assert "sanctions" in reasoning_lower or "pep" in reasoning_lower

    @pytest.mark.asyncio
    async def test_person_query_ranks_gdelt_medium(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Person query should rank GDELT as MEDIUM."""
        result = await engine.analyze("Who is John Smith oligarch")

        gdelt = next(s for s in result.sources if s.source_name == "gdelt")
        assert gdelt.score == RelevanceScore.MEDIUM
        assert "news" in gdelt.reasoning.lower() or "mention" in gdelt.reasoning.lower()

    @pytest.mark.asyncio
    async def test_person_query_detects_type(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Person query should be detected as person type."""
        result = await engine.analyze("Who is the CEO of Gazprom")

        assert result.query_type == "person"

    @pytest.mark.asyncio
    async def test_person_query_with_title(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Person query with title keyword should be detected."""
        result = await engine.analyze("who is the president")

        assert result.query_type == "person"


class TestVesselQueryDetection:
    """Tests for vessel query detection and scoring."""

    @pytest.mark.asyncio
    async def test_vessel_query_ranks_aisstream_high(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Vessel query should rank AISStream as HIGH."""
        result = await engine.analyze("Track vessel IMO 1234567")

        aisstream = next(s for s in result.sources if s.source_name == "aisstream")
        assert aisstream.score == RelevanceScore.HIGH
        reasoning_lower = aisstream.reasoning.lower()
        assert "position" in reasoning_lower or "tracking" in reasoning_lower

    @pytest.mark.asyncio
    async def test_vessel_query_ranks_wikidata_high(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Vessel query should rank Wikidata as HIGH."""
        result = await engine.analyze("Information on cargo ship")

        wikidata = next(s for s in result.sources if s.source_name == "wikidata")
        assert wikidata.score == RelevanceScore.HIGH

    @pytest.mark.asyncio
    async def test_vessel_query_ranks_opensanctions_high(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Vessel query should rank OpenSanctions as HIGH."""
        result = await engine.analyze("Is this vessel sanctioned MMSI 123456789")

        opensanctions = next(
            s for s in result.sources if s.source_name == "opensanctions"
        )
        assert opensanctions.score == RelevanceScore.HIGH

    @pytest.mark.asyncio
    async def test_vessel_query_detects_imo_pattern(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Vessel query with IMO number should be detected."""
        result = await engine.analyze("IMO 9876543 current position")

        assert result.query_type == "vessel"

    @pytest.mark.asyncio
    async def test_vessel_query_detects_mmsi_pattern(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Vessel query with MMSI number should be detected."""
        result = await engine.analyze("MMSI 123456789 tracking")

        assert result.query_type == "vessel"

    @pytest.mark.asyncio
    async def test_vessel_query_detects_keywords(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Vessel query with maritime keywords should be detected."""
        result = await engine.analyze("track maritime cargo tanker")

        assert result.query_type == "vessel"


class TestAircraftQueryDetection:
    """Tests for aircraft query detection and scoring."""

    @pytest.mark.asyncio
    async def test_aircraft_query_ranks_opensky_high(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Aircraft query should rank OpenSky as HIGH."""
        result = await engine.analyze("Track flight UAL123")

        opensky = next(s for s in result.sources if s.source_name == "opensky")
        assert opensky.score == RelevanceScore.HIGH
        reasoning_lower = opensky.reasoning.lower()
        assert "aircraft" in reasoning_lower or "tracking" in reasoning_lower

    @pytest.mark.asyncio
    async def test_aircraft_query_ranks_wikidata_medium(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Aircraft query should rank Wikidata as MEDIUM."""
        result = await engine.analyze("What is this aircraft type")

        wikidata = next(s for s in result.sources if s.source_name == "wikidata")
        assert wikidata.score == RelevanceScore.MEDIUM

    @pytest.mark.asyncio
    async def test_aircraft_query_ranks_gdelt_medium(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Aircraft query should rank GDELT as MEDIUM for news."""
        result = await engine.analyze("aviation incidents today")

        gdelt = next(s for s in result.sources if s.source_name == "gdelt")
        assert gdelt.score == RelevanceScore.MEDIUM

    @pytest.mark.asyncio
    async def test_aircraft_query_detects_type(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Aircraft query should be detected as aircraft type."""
        result = await engine.analyze("Track flight position")

        assert result.query_type == "aircraft"

    @pytest.mark.asyncio
    async def test_aircraft_query_detects_keywords(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Aircraft query with aviation keywords should be detected."""
        result = await engine.analyze("plane aviation jet helicopter")

        assert result.query_type == "aircraft"

    @pytest.mark.asyncio
    async def test_aircraft_query_detects_callsign_only(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Aircraft query with callsign pattern only (no keywords) should be detected."""
        result = await engine.analyze("UAL123")

        assert result.query_type == "aircraft"

    @pytest.mark.asyncio
    async def test_aircraft_query_detects_us_tail_number(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Aircraft query with US tail number pattern should be detected."""
        result = await engine.analyze("N12345")

        assert result.query_type == "aircraft"

    @pytest.mark.asyncio
    async def test_aircraft_query_detects_uk_tail_number(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Aircraft query with UK tail number pattern should be detected."""
        result = await engine.analyze("G-ABCD")

        assert result.query_type == "aircraft"


class TestOrganizationQueryDetection:
    """Tests for organization query detection and scoring."""

    @pytest.mark.asyncio
    async def test_organization_query_ranks_wikidata_high(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Organization query should rank Wikidata as HIGH."""
        result = await engine.analyze("Information on Gazprom company")

        wikidata = next(s for s in result.sources if s.source_name == "wikidata")
        assert wikidata.score == RelevanceScore.HIGH

    @pytest.mark.asyncio
    async def test_organization_query_ranks_opensanctions_high(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Organization query should rank OpenSanctions as HIGH."""
        result = await engine.analyze("Is this corporation sanctioned")

        opensanctions = next(
            s for s in result.sources if s.source_name == "opensanctions"
        )
        assert opensanctions.score == RelevanceScore.HIGH

    @pytest.mark.asyncio
    async def test_organization_query_detects_type(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Organization query should be detected as organization type."""
        result = await engine.analyze("Rosneft company information")

        assert result.query_type == "organization"

    @pytest.mark.asyncio
    async def test_organization_query_detects_suffix(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Organization query with Corp/Ltd suffix should be detected."""
        result = await engine.analyze("ABC Corp financial data")

        assert result.query_type == "organization"


class TestGeneralQueryDetection:
    """Tests for general/mixed query detection."""

    @pytest.mark.asyncio
    async def test_general_query_fallback(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Ambiguous queries should fall back to general type."""
        result = await engine.analyze("random text with no clear type")

        assert result.query_type == "general"

    @pytest.mark.asyncio
    async def test_general_query_balanced_scoring(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """General queries should have balanced source scoring."""
        result = await engine.analyze("xyz123 unclear query")

        # No source should have LOW except specialized ones
        scores = {s.source_name: s.score for s in result.sources}

        # General query should have MEDIUM for most sources
        assert scores["gdelt"] == RelevanceScore.MEDIUM
        assert scores["wikidata"] == RelevanceScore.MEDIUM


class TestSourceAvailability:
    """Tests for source availability checking."""

    @pytest.mark.asyncio
    async def test_always_available_sources(
        self, engine_no_credentials: SourceRelevanceEngine
    ) -> None:
        """Sources without auth should always be available."""
        result = await engine_no_credentials.analyze("test query")

        # These sources don't require authentication
        assert "gdelt" in result.available_sources
        assert "worldbank" in result.available_sources
        assert "wikidata" in result.available_sources
        assert "opensanctions" in result.available_sources

    @pytest.mark.asyncio
    async def test_auth_required_sources_unavailable_without_credentials(
        self, engine_no_credentials: SourceRelevanceEngine
    ) -> None:
        """Auth-required sources should be unavailable without credentials."""
        result = await engine_no_credentials.analyze("test query")

        # These sources require authentication
        assert "opensky" in result.unavailable_sources
        assert "aisstream" in result.unavailable_sources
        assert "acled" in result.unavailable_sources

    @pytest.mark.asyncio
    async def test_auth_required_sources_available_with_credentials(
        self, engine_with_all_credentials: SourceRelevanceEngine
    ) -> None:
        """Auth-required sources should be available with credentials."""
        result = await engine_with_all_credentials.analyze("test query")

        # All sources should be available
        assert "opensky" in result.available_sources
        assert "aisstream" in result.available_sources
        assert "acled" in result.available_sources
        assert len(result.unavailable_sources) == 0

    @pytest.mark.asyncio
    async def test_unavailable_source_has_reason(
        self, engine_no_credentials: SourceRelevanceEngine
    ) -> None:
        """Unavailable sources should include a reason."""
        result = await engine_no_credentials.analyze("track flight")

        opensky = next(s for s in result.sources if s.source_name == "opensky")
        assert opensky.available is False
        assert opensky.unavailable_reason is not None
        reason_lower = opensky.unavailable_reason.lower()
        assert "opensky" in reason_lower or "authentication" in reason_lower


class TestSourceRanking:
    """Tests for source ranking order."""

    @pytest.mark.asyncio
    async def test_sources_ranked_by_score_descending(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Sources should be ranked by score in descending order."""
        result = await engine.analyze("Deep dive on Venezuela")

        # Verify descending order
        scores = [s.score.numeric_value for s in result.sources]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_all_sources_included(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """All sources should be included in results."""
        result = await engine.analyze("test query")

        source_names = {s.source_name for s in result.sources}
        expected_sources = {
            "gdelt",
            "worldbank",
            "wikidata",
            "opensky",
            "aisstream",
            "acled",
            "opensanctions",
        }

        assert source_names == expected_sources

    @pytest.mark.asyncio
    async def test_high_relevance_sources_at_top(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """HIGH relevance sources should appear at the top."""
        result = await engine.analyze("Deep dive on Venezuela")

        # First sources should be HIGH
        first_few = result.sources[:2]
        for source in first_few:
            assert source.score in (RelevanceScore.HIGH, RelevanceScore.MEDIUM_HIGH)


class TestRelevanceReasons:
    """Tests for relevance reasoning strings."""

    @pytest.mark.asyncio
    async def test_reasons_are_descriptive(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Relevance reasons should be descriptive."""
        result = await engine.analyze("Deep dive on Venezuela")

        for source in result.sources:
            assert len(source.reasoning) > 10
            assert source.reasoning[0].isupper()  # Proper sentence

    @pytest.mark.asyncio
    async def test_country_query_reasons_mention_country_context(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Country query reasons should mention relevant context."""
        result = await engine.analyze("Analysis of Brazil")

        gdelt = next(s for s in result.sources if s.source_name == "gdelt")
        worldbank = next(s for s in result.sources if s.source_name == "worldbank")

        gdelt_reasoning = gdelt.reasoning.lower()
        worldbank_reasoning = worldbank.reasoning.lower()
        assert "news" in gdelt_reasoning or "coverage" in gdelt_reasoning
        assert "economic" in worldbank_reasoning or "indicator" in worldbank_reasoning

    @pytest.mark.asyncio
    async def test_person_query_reasons_mention_person_context(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """Person query reasons should mention relevant context."""
        result = await engine.analyze("Who is this oligarch politician")

        wikidata = next(s for s in result.sources if s.source_name == "wikidata")
        opensanctions = next(
            s for s in result.sources if s.source_name == "opensanctions"
        )

        wikidata_reasoning = wikidata.reasoning.lower()
        opensanctions_reasoning = opensanctions.reasoning.lower()
        assert "entity" in wikidata_reasoning or "people" in wikidata_reasoning
        assert "sanctions" in opensanctions_reasoning or "pep" in opensanctions_reasoning


class TestQueryParams:
    """Tests for QueryParams integration."""

    @pytest.mark.asyncio
    async def test_analyze_accepts_query_params(
        self, engine: SourceRelevanceEngine
    ) -> None:
        """analyze() should accept optional QueryParams."""
        from ignifer.models import QueryParams

        params = QueryParams(query="Venezuela", max_results_per_source=5)
        result = await engine.analyze("Deep dive on Venezuela", params=params)

        assert result.query == "Deep dive on Venezuela"
        assert result.query_type == "country"


class TestEngineInitialization:
    """Tests for engine initialization."""

    def test_engine_with_custom_settings(self) -> None:
        """Engine should accept custom Settings."""
        settings = Settings()
        engine = SourceRelevanceEngine(settings=settings)

        assert engine._settings is settings

    def test_engine_with_default_settings(self) -> None:
        """Engine should use get_settings() by default."""
        engine = SourceRelevanceEngine()

        assert engine._settings is not None


class TestLogging:
    """Tests for logging behavior."""

    @pytest.mark.asyncio
    async def test_analyze_logs_query(
        self, engine: SourceRelevanceEngine, caplog: pytest.LogCaptureFixture
    ) -> None:
        """analyze() should log the query being analyzed."""
        import logging

        with caplog.at_level(logging.INFO):
            await engine.analyze("Test query for logging")

        assert any("relevance" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_analyze_logs_completion(
        self, engine: SourceRelevanceEngine, caplog: pytest.LogCaptureFixture
    ) -> None:
        """analyze() should log completion info."""
        import logging

        with caplog.at_level(logging.INFO):
            await engine.analyze("Test query")

        assert any("complete" in record.message.lower() for record in caplog.records)
