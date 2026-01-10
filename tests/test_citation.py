"""Tests for Citation & Attribution System.

Tests:
- CitationFormatter class methods
- Data freshness calculation
- Source display names and titles
- Inline, footnote, and bibliography formatting
- Multi-source attribution with corroboration
- Data age warnings
- Edge cases (missing URL, missing title)
"""

from datetime import datetime, timedelta, timezone

import pytest

from ignifer.aggregation.correlator import SourceContribution
from ignifer.citation import (
    POINT_IN_TIME_DISCLAIMER,
    SOURCE_DISPLAY_NAMES,
    SOURCE_TITLES,
    CitationFormatter,
    CitationWithWarnings,
    DataFreshness,
    get_data_freshness,
    get_freshness_label,
)
from ignifer.models import QualityTier, SourceMetadata


class TestDataFreshness:
    """Tests for DataFreshness enum and get_data_freshness function."""

    def test_enum_has_four_values(self) -> None:
        """DataFreshness should have exactly 4 values."""
        assert len(DataFreshness) == 4

    def test_fresh_threshold_under_one_hour(self) -> None:
        """Data retrieved less than 1 hour ago should be FRESH."""
        now = datetime.now(timezone.utc)
        retrieved_at = now - timedelta(minutes=30)
        assert get_data_freshness(retrieved_at) == DataFreshness.FRESH

    def test_fresh_threshold_just_under_one_hour(self) -> None:
        """Data retrieved just under 1 hour ago should be FRESH."""
        now = datetime.now(timezone.utc)
        retrieved_at = now - timedelta(minutes=59)
        assert get_data_freshness(retrieved_at) == DataFreshness.FRESH

    def test_recent_threshold_one_hour(self) -> None:
        """Data retrieved exactly 1 hour ago should be RECENT."""
        now = datetime.now(timezone.utc)
        retrieved_at = now - timedelta(hours=1)
        assert get_data_freshness(retrieved_at) == DataFreshness.RECENT

    def test_recent_threshold_between_1_and_24_hours(self) -> None:
        """Data retrieved between 1-24 hours ago should be RECENT."""
        now = datetime.now(timezone.utc)
        retrieved_at = now - timedelta(hours=12)
        assert get_data_freshness(retrieved_at) == DataFreshness.RECENT

    def test_stale_threshold_over_24_hours(self) -> None:
        """Data retrieved over 24 hours ago should be STALE."""
        now = datetime.now(timezone.utc)
        retrieved_at = now - timedelta(hours=25)
        assert get_data_freshness(retrieved_at) == DataFreshness.STALE

    def test_stale_threshold_between_1_and_7_days(self) -> None:
        """Data retrieved between 1-7 days ago should be STALE."""
        now = datetime.now(timezone.utc)
        retrieved_at = now - timedelta(days=3)
        assert get_data_freshness(retrieved_at) == DataFreshness.STALE

    def test_archived_threshold_over_7_days(self) -> None:
        """Data retrieved over 7 days ago should be ARCHIVED."""
        now = datetime.now(timezone.utc)
        retrieved_at = now - timedelta(days=8)
        assert get_data_freshness(retrieved_at) == DataFreshness.ARCHIVED

    def test_archived_threshold_old_data(self) -> None:
        """Very old data should be ARCHIVED."""
        now = datetime.now(timezone.utc)
        retrieved_at = now - timedelta(days=30)
        assert get_data_freshness(retrieved_at) == DataFreshness.ARCHIVED

    def test_naive_datetime_handled(self) -> None:
        """Naive datetime should be treated as UTC."""
        # Create a naive datetime that would be fresh
        now = datetime.now(timezone.utc)
        retrieved_at = (now - timedelta(minutes=30)).replace(tzinfo=None)
        # Should not raise, should return FRESH
        result = get_data_freshness(retrieved_at)
        assert result == DataFreshness.FRESH


class TestGetFreshnessLabel:
    """Tests for get_freshness_label function."""

    def test_fresh_label(self) -> None:
        """FRESH should have appropriate label."""
        label = get_freshness_label(DataFreshness.FRESH)
        assert "Fresh" in label
        assert "<1 hour" in label

    def test_recent_label(self) -> None:
        """RECENT should have appropriate label."""
        label = get_freshness_label(DataFreshness.RECENT)
        assert "Recent" in label
        assert "1-24 hours" in label

    def test_stale_label(self) -> None:
        """STALE should have appropriate label."""
        label = get_freshness_label(DataFreshness.STALE)
        assert "Stale" in label
        assert "1-7 days" in label

    def test_archived_label(self) -> None:
        """ARCHIVED should have appropriate label."""
        label = get_freshness_label(DataFreshness.ARCHIVED)
        assert "Archived" in label
        assert ">7 days" in label


class TestSourceDisplayNames:
    """Tests for source display name mappings."""

    def test_gdelt_display_name(self) -> None:
        """GDELT should have proper display name."""
        assert SOURCE_DISPLAY_NAMES["gdelt"] == "GDELT Project"

    def test_worldbank_display_name(self) -> None:
        """World Bank should have proper display name."""
        assert SOURCE_DISPLAY_NAMES["worldbank"] == "World Bank"

    def test_wikidata_display_name(self) -> None:
        """Wikidata should have proper display name."""
        assert SOURCE_DISPLAY_NAMES["wikidata"] == "Wikidata"

    def test_opensky_display_name(self) -> None:
        """OpenSky should have proper display name."""
        assert SOURCE_DISPLAY_NAMES["opensky"] == "OpenSky Network"

    def test_aisstream_display_name(self) -> None:
        """AISStream should have proper display name."""
        assert SOURCE_DISPLAY_NAMES["aisstream"] == "AISStream"

    def test_opensanctions_display_name(self) -> None:
        """OpenSanctions should have proper display name."""
        assert SOURCE_DISPLAY_NAMES["opensanctions"] == "OpenSanctions"

    def test_all_sources_have_display_names(self) -> None:
        """All sources should have display names defined."""
        expected_sources = [
            "gdelt",
            "worldbank",
            "wikidata",
            "opensky",
            "aisstream",
            "opensanctions",
        ]
        for source in expected_sources:
            assert source in SOURCE_DISPLAY_NAMES


class TestSourceTitles:
    """Tests for source title mappings."""

    def test_gdelt_title(self) -> None:
        """GDELT should have proper title."""
        assert SOURCE_TITLES["gdelt"] == "Global Database of Events, Language, and Tone"

    def test_worldbank_title(self) -> None:
        """World Bank should have proper title."""
        assert SOURCE_TITLES["worldbank"] == "World Development Indicators"

    def test_all_sources_have_titles(self) -> None:
        """All sources should have titles defined."""
        expected_sources = [
            "gdelt",
            "worldbank",
            "wikidata",
            "opensky",
            "aisstream",
            "opensanctions",
        ]
        for source in expected_sources:
            assert source in SOURCE_TITLES


class TestCitationFormatter:
    """Tests for CitationFormatter class."""

    @pytest.fixture
    def formatter(self) -> CitationFormatter:
        """Provide a CitationFormatter instance."""
        return CitationFormatter()

    @pytest.fixture
    def gdelt_source(self) -> SourceMetadata:
        """Provide a GDELT source metadata fixture."""
        return SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/api/v2/doc/doc?query=ukraine",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )

    @pytest.fixture
    def worldbank_source(self) -> SourceMetadata:
        """Provide a World Bank source metadata fixture."""
        return SourceMetadata(
            source_name="worldbank",
            source_url="https://api.worldbank.org/v2/country/DEU/indicator/NY.GDP.MKTP.CD",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 15, tzinfo=timezone.utc),
        )

    @pytest.fixture
    def source_no_url(self) -> SourceMetadata:
        """Provide a source without URL."""
        return SourceMetadata(
            source_name="unknown_source",
            source_url="",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )


class TestFormatInline:
    """Tests for format_inline method."""

    @pytest.fixture
    def formatter(self) -> CitationFormatter:
        """Provide a CitationFormatter instance."""
        return CitationFormatter()

    def test_gdelt_inline(self, formatter: CitationFormatter) -> None:
        """GDELT inline citation should be formatted correctly."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )
        result = formatter.format_inline(source)
        assert result == "(GDELT Project, 2026-01-10)"

    def test_worldbank_inline(self, formatter: CitationFormatter) -> None:
        """World Bank inline citation should be formatted correctly."""
        source = SourceMetadata(
            source_name="worldbank",
            source_url="https://api.worldbank.org/",
            retrieved_at=datetime(2026, 1, 8, 10, 0, 0, tzinfo=timezone.utc),
        )
        result = formatter.format_inline(source)
        assert result == "(World Bank, 2026-01-08)"

    def test_wikidata_inline(self, formatter: CitationFormatter) -> None:
        """Wikidata inline citation should be formatted correctly."""
        source = SourceMetadata(
            source_name="wikidata",
            source_url="https://www.wikidata.org/",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )
        result = formatter.format_inline(source)
        assert result == "(Wikidata, 2026-01-10)"

    def test_opensky_inline(self, formatter: CitationFormatter) -> None:
        """OpenSky inline citation should be formatted correctly."""
        source = SourceMetadata(
            source_name="opensky",
            source_url="https://opensky-network.org/",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )
        result = formatter.format_inline(source)
        assert result == "(OpenSky Network, 2026-01-10)"

    def test_aisstream_inline(self, formatter: CitationFormatter) -> None:
        """AISStream inline citation should be formatted correctly."""
        source = SourceMetadata(
            source_name="aisstream",
            source_url="https://aisstream.io/",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )
        result = formatter.format_inline(source)
        assert result == "(AISStream, 2026-01-10)"

    def test_opensanctions_inline(self, formatter: CitationFormatter) -> None:
        """OpenSanctions inline citation should be formatted correctly."""
        source = SourceMetadata(
            source_name="opensanctions",
            source_url="https://opensanctions.org/",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )
        result = formatter.format_inline(source)
        assert result == "(OpenSanctions, 2026-01-10)"

    def test_unknown_source_inline(self, formatter: CitationFormatter) -> None:
        """Unknown source should use title case with underscores replaced by spaces."""
        source = SourceMetadata(
            source_name="custom_source",
            source_url="https://example.com/",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )
        result = formatter.format_inline(source)
        assert result == "(Custom Source, 2026-01-10)"


class TestFormatFootnote:
    """Tests for format_footnote method."""

    @pytest.fixture
    def formatter(self) -> CitationFormatter:
        """Provide a CitationFormatter instance."""
        return CitationFormatter()

    def test_footnote_with_url(self, formatter: CitationFormatter) -> None:
        """Footnote with URL should include full reference."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/api/v2/doc/doc?query=ukraine",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )
        result = formatter.format_footnote(source, 1)
        assert result.startswith("[1]")
        assert "GDELT Project" in result
        assert "Retrieved" in result
        assert "2026-01-10T14:32:00+00:00" in result
        assert "https://api.gdeltproject.org" in result

    def test_footnote_numbering(self, formatter: CitationFormatter) -> None:
        """Footnote should use correct number."""
        source = SourceMetadata(
            source_name="worldbank",
            source_url="https://api.worldbank.org/",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 15, tzinfo=timezone.utc),
        )
        result = formatter.format_footnote(source, 42)
        assert result.startswith("[42]")

    def test_footnote_without_url(self, formatter: CitationFormatter) -> None:
        """Footnote without URL should still be formatted correctly."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )
        result = formatter.format_footnote(source, 1)
        assert result.startswith("[1]")
        assert "GDELT Project" in result
        assert "Retrieved" in result
        assert result.endswith(".")

    def test_footnote_iso8601_format(self, formatter: CitationFormatter) -> None:
        """Footnote should use ISO 8601 timestamp."""
        source = SourceMetadata(
            source_name="opensky",
            source_url="https://opensky-network.org/api/",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )
        result = formatter.format_footnote(source, 1)
        assert "2026-01-10T14:32:00+00:00" in result


class TestFormatUrlWithTimestamp:
    """Tests for format_url_with_timestamp method."""

    @pytest.fixture
    def formatter(self) -> CitationFormatter:
        """Provide a CitationFormatter instance."""
        return CitationFormatter()

    def test_url_with_timestamp(self, formatter: CitationFormatter) -> None:
        """URL should include retrieval timestamp."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/api/v2/doc/doc?query=test",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )
        result = formatter.format_url_with_timestamp(source)
        assert "https://api.gdeltproject.org/api/v2/doc/doc?query=test" in result
        assert "(retrieved 2026-01-10T14:32:00+00:00)" in result

    def test_url_with_timestamp_no_url(self, formatter: CitationFormatter) -> None:
        """Missing URL should return just timestamp."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )
        result = formatter.format_url_with_timestamp(source)
        assert result == "(retrieved 2026-01-10T14:32:00+00:00)"


class TestFormatBibliography:
    """Tests for format_bibliography method."""

    @pytest.fixture
    def formatter(self) -> CitationFormatter:
        """Provide a CitationFormatter instance."""
        return CitationFormatter()

    def test_bibliography_empty(self, formatter: CitationFormatter) -> None:
        """Empty sources should return 'No sources available'."""
        result = formatter.format_bibliography([])
        assert "Sources" in result
        assert "No sources available" in result

    def test_bibliography_single_source(self, formatter: CitationFormatter) -> None:
        """Single source bibliography should be formatted correctly."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/",
            retrieved_at=datetime.now(timezone.utc) - timedelta(hours=12),
        )
        result = formatter.format_bibliography([source])
        assert "Sources" in result
        assert "GDELT Project" in result
        assert "Global Database of Events, Language, and Tone" in result
        assert POINT_IN_TIME_DISCLAIMER in result

    def test_bibliography_multiple_sources(self, formatter: CitationFormatter) -> None:
        """Multiple sources should all appear in bibliography."""
        now = datetime.now(timezone.utc)
        sources = [
            SourceMetadata(
                source_name="gdelt",
                source_url="https://api.gdeltproject.org/",
                retrieved_at=now - timedelta(minutes=30),
            ),
            SourceMetadata(
                source_name="worldbank",
                source_url="https://api.worldbank.org/",
                retrieved_at=now - timedelta(hours=12),
            ),
        ]
        result = formatter.format_bibliography(sources)
        assert "GDELT Project" in result
        assert "World Bank" in result
        assert "World Development Indicators" in result
        assert POINT_IN_TIME_DISCLAIMER in result

    def test_bibliography_includes_freshness(self, formatter: CitationFormatter) -> None:
        """Bibliography should include data freshness indicators."""
        source = SourceMetadata(
            source_name="worldbank",
            source_url="https://api.worldbank.org/",
            retrieved_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
        result = formatter.format_bibliography([source])
        assert "Data freshness:" in result
        assert "Fresh" in result

    def test_bibliography_header_format(self, formatter: CitationFormatter) -> None:
        """Bibliography should have proper header format."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/",
            retrieved_at=datetime.now(timezone.utc),
        )
        result = formatter.format_bibliography([source])
        lines = result.split("\n")
        assert lines[0] == "Sources"
        assert "=" in lines[1]


class TestFormatMultiSourceAttribution:
    """Tests for format_multi_source_attribution method."""

    @pytest.fixture
    def formatter(self) -> CitationFormatter:
        """Provide a CitationFormatter instance."""
        return CitationFormatter()

    def test_empty_sources(self, formatter: CitationFormatter) -> None:
        """Empty sources should return 'No sources available'."""
        result = formatter.format_multi_source_attribution([])
        assert "Source Attribution" in result
        assert "No sources available" in result

    def test_single_source_attribution(self, formatter: CitationFormatter) -> None:
        """Single source should be marked as single source."""
        contribution = SourceContribution(
            source_name="gdelt",
            data={"topic": "events"},
            quality_tier=QualityTier.MEDIUM,
            retrieved_at=datetime.now(timezone.utc),
            source_url="https://api.gdeltproject.org/",
        )
        result = formatter.format_multi_source_attribution([contribution])
        assert "Source Attribution" in result
        assert "GDELT Project" in result
        assert "MEDIUM quality" in result
        assert "[Single source]" in result

    def test_multi_source_with_corroboration(self, formatter: CitationFormatter) -> None:
        """Multiple sources for same type should show corroboration."""
        now = datetime.now(timezone.utc)
        contributions = [
            SourceContribution(
                source_name="worldbank",
                data={"indicator": "GDP"},
                quality_tier=QualityTier.HIGH,
                retrieved_at=now,
                source_url="https://api.worldbank.org/",
            ),
            SourceContribution(
                source_name="wikidata",
                data={"indicator": "GDP"},
                quality_tier=QualityTier.MEDIUM,
                retrieved_at=now,
                source_url="https://www.wikidata.org/",
            ),
        ]
        result = formatter.format_multi_source_attribution(contributions)
        # They should be grouped by inferred data type
        assert "Source Attribution" in result

    def test_multi_source_without_corroboration(self, formatter: CitationFormatter) -> None:
        """Should work without corroboration notes when disabled."""
        contribution = SourceContribution(
            source_name="opensanctions",
            data={"sanctioned": True},
            quality_tier=QualityTier.HIGH,
            retrieved_at=datetime.now(timezone.utc),
            source_url="https://opensanctions.org/",
        )
        result = formatter.format_multi_source_attribution(
            [contribution], include_corroboration=False
        )
        assert "OpenSanctions" in result
        # Should still indicate single source when include_corroboration is True by default
        # but not show corroboration details when disabled

    def test_quality_tier_displayed(self, formatter: CitationFormatter) -> None:
        """Quality tier should be displayed in attribution."""
        contribution = SourceContribution(
            source_name="worldbank",
            data={},
            quality_tier=QualityTier.HIGH,
            retrieved_at=datetime.now(timezone.utc),
        )
        result = formatter.format_multi_source_attribution([contribution])
        assert "HIGH quality" in result

    def test_different_source_types(self, formatter: CitationFormatter) -> None:
        """Different source types should be listed separately."""
        now = datetime.now(timezone.utc)
        contributions = [
            SourceContribution(
                source_name="gdelt",
                data={},
                quality_tier=QualityTier.MEDIUM,
                retrieved_at=now,
            ),
            SourceContribution(
                source_name="worldbank",
                data={},
                quality_tier=QualityTier.HIGH,
                retrieved_at=now,
            ),
            SourceContribution(
                source_name="opensanctions",
                data={},
                quality_tier=QualityTier.HIGH,
                retrieved_at=now,
            ),
        ]
        result = formatter.format_multi_source_attribution(contributions)
        assert "Recent events" in result
        assert "Economic indicators" in result
        assert "Sanctions status" in result


class TestFormatWithDisclaimer:
    """Tests for format_with_disclaimer method."""

    @pytest.fixture
    def formatter(self) -> CitationFormatter:
        """Provide a CitationFormatter instance."""
        return CitationFormatter()

    def test_includes_disclaimer(self, formatter: CitationFormatter) -> None:
        """Result should include point-in-time disclaimer."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/",
            retrieved_at=datetime.now(timezone.utc),
        )
        result = formatter.format_with_disclaimer(source)
        assert POINT_IN_TIME_DISCLAIMER in result

    def test_stale_data_warning(self, formatter: CitationFormatter) -> None:
        """Stale data should include warning."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/",
            retrieved_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        result = formatter.format_with_disclaimer(source)
        assert "stale" in result.lower() or "Stale" in result

    def test_archived_data_warning(self, formatter: CitationFormatter) -> None:
        """Archived data should include archival warning."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/",
            retrieved_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        result = formatter.format_with_disclaimer(source)
        assert "archived" in result.lower() or "Archived" in result
        assert "Wayback Machine" in result


class TestCitationWithWarnings:
    """Tests for CitationWithWarnings model."""

    @pytest.fixture
    def formatter(self) -> CitationFormatter:
        """Provide a CitationFormatter instance."""
        return CitationFormatter()

    def test_fresh_data_no_warnings(self, formatter: CitationFormatter) -> None:
        """Fresh data should have no warnings."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/",
            retrieved_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
        result = formatter.get_citation_with_warnings(source)
        assert isinstance(result, CitationWithWarnings)
        assert len(result.warnings) == 0

    def test_stale_data_has_warning(self, formatter: CitationFormatter) -> None:
        """Stale data should have warning."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/",
            retrieved_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        result = formatter.get_citation_with_warnings(source)
        assert len(result.warnings) > 0
        assert any("stale" in w.lower() for w in result.warnings)

    def test_archived_data_has_multiple_warnings(self, formatter: CitationFormatter) -> None:
        """Archived data should have multiple warnings."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/",
            retrieved_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        result = formatter.get_citation_with_warnings(source)
        assert len(result.warnings) >= 2  # Age warning + archival suggestion

    def test_disclaimer_always_present(self, formatter: CitationFormatter) -> None:
        """Disclaimer should always be present."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/",
            retrieved_at=datetime.now(timezone.utc),
        )
        result = formatter.get_citation_with_warnings(source)
        assert result.disclaimer == POINT_IN_TIME_DISCLAIMER


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def formatter(self) -> CitationFormatter:
        """Provide a CitationFormatter instance."""
        return CitationFormatter()

    def test_empty_source_url(self, formatter: CitationFormatter) -> None:
        """Empty source URL should be handled gracefully."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="",
            retrieved_at=datetime.now(timezone.utc),
        )
        result = formatter.format_bibliography([source])
        assert "GDELT Project" in result

    def test_unknown_source_name(self, formatter: CitationFormatter) -> None:
        """Unknown source name should use title case with underscores as spaces."""
        source = SourceMetadata(
            source_name="new_source_xyz",
            source_url="https://example.com/",
            retrieved_at=datetime.now(timezone.utc),
        )
        result = formatter.format_inline(source)
        assert "New Source Xyz" in result

    def test_naive_datetime_in_source(self, formatter: CitationFormatter) -> None:
        """Naive datetime should be handled as UTC."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0),  # Naive datetime
        )
        result = formatter.format_footnote(source, 1)
        # Should not raise and should include timestamp
        assert "Retrieved" in result

    def test_case_insensitive_source_lookup(self, formatter: CitationFormatter) -> None:
        """Source name lookup should be case-insensitive."""
        source = SourceMetadata(
            source_name="GDELT",
            source_url="https://api.gdeltproject.org/",
            retrieved_at=datetime.now(timezone.utc),
        )
        result = formatter.format_inline(source)
        assert "GDELT Project" in result

    def test_mixed_case_source_lookup(self, formatter: CitationFormatter) -> None:
        """Mixed case source name should work."""
        source = SourceMetadata(
            source_name="OpenSky",
            source_url="https://opensky-network.org/",
            retrieved_at=datetime.now(timezone.utc),
        )
        result = formatter.format_inline(source)
        assert "OpenSky Network" in result


class TestIntegration:
    """Integration tests for citation formatting."""

    @pytest.fixture
    def formatter(self) -> CitationFormatter:
        """Provide a CitationFormatter instance."""
        return CitationFormatter()

    def test_full_citation_workflow(self, formatter: CitationFormatter) -> None:
        """Test complete citation workflow from source to bibliography."""
        now = datetime.now(timezone.utc)

        # Create sources
        sources = [
            SourceMetadata(
                source_name="gdelt",
                source_url="https://api.gdeltproject.org/api/v2/doc/doc?query=ukraine",
                retrieved_at=now - timedelta(minutes=30),
            ),
            SourceMetadata(
                source_name="worldbank",
                source_url="https://api.worldbank.org/v2/country/DEU",
                retrieved_at=now - timedelta(hours=12),
            ),
            SourceMetadata(
                source_name="opensanctions",
                source_url="https://api.opensanctions.org/",
                retrieved_at=now - timedelta(hours=2),
            ),
        ]

        # Test inline citations
        for source in sources:
            inline = formatter.format_inline(source)
            assert inline.startswith("(")
            assert inline.endswith(")")

        # Test footnotes
        for i, source in enumerate(sources, 1):
            footnote = formatter.format_footnote(source, i)
            assert f"[{i}]" in footnote

        # Test bibliography
        bibliography = formatter.format_bibliography(sources)
        assert "Sources" in bibliography
        assert "GDELT Project" in bibliography
        assert "World Bank" in bibliography
        assert "OpenSanctions" in bibliography
        assert POINT_IN_TIME_DISCLAIMER in bibliography

    def test_citation_consistency(self, formatter: CitationFormatter) -> None:
        """Formatting should be consistent across methods."""
        source = SourceMetadata(
            source_name="gdelt",
            source_url="https://api.gdeltproject.org/",
            retrieved_at=datetime(2026, 1, 10, 14, 32, 0, tzinfo=timezone.utc),
        )

        inline = formatter.format_inline(source)
        footnote = formatter.format_footnote(source, 1)
        bibliography = formatter.format_bibliography([source])

        # All should reference GDELT Project
        assert "GDELT Project" in inline
        assert "GDELT Project" in footnote
        assert "GDELT Project" in bibliography
