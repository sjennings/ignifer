"""Tests for rigor mode integration (Story 8.3).

Tests the rigor mode functionality across all tools, including:
- Global setting resolution (FR48)
- Per-tool rigor parameter (AC #1, #5)
- IC-standard output format (FR27-FR31)
- Bibliography generation (FR30)
"""

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from ignifer.config import Settings, reset_settings
from ignifer.models import ConfidenceLevel, SourceMetadata
from ignifer.rigor import (
    format_analytical_caveats,
    format_bibliography,
    format_confidence_statement,
    format_entity_match_confidence,
    format_rigor_header,
    format_rigor_output,
    format_sanctions_match_confidence,
    format_source_attribution,
    resolve_rigor_mode,
)


class TestResolveRigorMode:
    """Tests for resolve_rigor_mode function."""

    def test_explicit_true_overrides_global_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit rigor=True should override global False."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "false")

        result = resolve_rigor_mode(True)

        assert result is True

    def test_explicit_false_overrides_global_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit rigor=False should override global True."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "true")

        result = resolve_rigor_mode(False)

        assert result is False

    def test_none_uses_global_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """rigor=None should use global setting (True)."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "true")

        result = resolve_rigor_mode(None)

        assert result is True

    def test_none_uses_global_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """rigor=None should use global setting (False)."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "false")

        result = resolve_rigor_mode(None)

        assert result is False

    def test_default_is_false(self) -> None:
        """Default global setting should be False."""
        reset_settings()
        # Clear any env var
        with patch.dict(os.environ, {}, clear=True):
            reset_settings()
            result = resolve_rigor_mode(None)

        assert result is False


class TestFormatRigorHeader:
    """Tests for format_rigor_header function."""

    def test_header_contains_title(self) -> None:
        """Header should contain the provided title."""
        result = format_rigor_header("Test Topic")

        assert "INTELLIGENCE ASSESSMENT:" in result
        assert "TEST TOPIC" in result

    def test_header_contains_classification(self) -> None:
        """Header should include UNCLASSIFIED // OSINT marking."""
        result = format_rigor_header("Test")

        assert "UNCLASSIFIED // OSINT" in result

    def test_header_contains_timestamp(self) -> None:
        """Header should contain date timestamp."""
        timestamp = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        result = format_rigor_header("Test", timestamp)

        assert "2026-01-10" in result

    def test_header_has_border_characters(self) -> None:
        """Header should have visual border characters."""
        result = format_rigor_header("Test")

        assert "=" * 59 in result


class TestFormatConfidenceStatement:
    """Tests for format_confidence_statement function."""

    def test_almost_certain_language(self) -> None:
        """ALMOST_CERTAIN should produce proper IC language."""
        result = format_confidence_statement(
            ConfidenceLevel.ALMOST_CERTAIN,
            "the assessment is correct",
        )

        # ICD 203 uses "very high confidence" for ALMOST_CERTAIN
        assert "very high confidence" in result.lower()
        assert "the assessment is correct" in result

    def test_likely_language(self) -> None:
        """LIKELY should produce proper IC language."""
        result = format_confidence_statement(
            ConfidenceLevel.LIKELY,
            "the information is accurate",
        )

        # ICD 203 uses "moderate confidence" for LIKELY
        assert "moderate confidence" in result.lower()
        assert "the information is accurate" in result


class TestFormatSourceAttribution:
    """Tests for format_source_attribution function."""

    def test_empty_sources_returns_no_sources(self) -> None:
        """Empty source list should indicate no sources."""
        result = format_source_attribution([])

        assert "No sources available" in result

    def test_sources_include_retrieval_timestamp(self) -> None:
        """Source attribution should include retrieval timestamp."""
        sources = [
            SourceMetadata(
                source_name="gdelt",
                source_url="https://api.gdeltproject.org/",
                retrieved_at=datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
            )
        ]

        result = format_source_attribution(sources)

        assert "2026-01-10" in result
        assert "GDELT" in result

    def test_sources_include_freshness(self) -> None:
        """Source attribution should include data freshness label."""
        sources = [
            SourceMetadata(
                source_name="worldbank",
                source_url="https://api.worldbank.org/",
                retrieved_at=datetime.now(timezone.utc),
            )
        ]

        result = format_source_attribution(sources)

        assert "freshness" in result.lower()


class TestFormatAnalyticalCaveats:
    """Tests for format_analytical_caveats function."""

    def test_gdelt_caveat_generated(self) -> None:
        """GDELT sources should generate coverage caveat."""
        result = format_analytical_caveats(source_names=["gdelt"])

        assert "GDELT" in result
        assert "Caveats" in result

    def test_acled_caveat_generated(self) -> None:
        """ACLED sources should generate reporting caveat."""
        result = format_analytical_caveats(source_names=["acled"])

        assert "ACLED" in result

    def test_custom_caveats_included(self) -> None:
        """Custom caveats should be included in output."""
        result = format_analytical_caveats(
            caveats=["This is a custom caveat"],
            source_names=[],
        )

        assert "custom caveat" in result

    def test_point_in_time_caveat_always_included(self) -> None:
        """Point-in-time caveat should always be present."""
        result = format_analytical_caveats(source_names=["gdelt"])

        assert "point-in-time" in result.lower()


class TestFormatBibliography:
    """Tests for format_bibliography function."""

    def test_bibliography_has_header(self) -> None:
        """Bibliography should have Sources header."""
        sources = [
            SourceMetadata(
                source_name="gdelt",
                source_url="https://api.gdeltproject.org/",
                retrieved_at=datetime.now(timezone.utc),
            )
        ]

        result = format_bibliography(sources)

        assert "Sources" in result or "SOURCES" in result

    def test_bibliography_includes_disclaimer(self) -> None:
        """Bibliography should include point-in-time disclaimer."""
        sources = [
            SourceMetadata(
                source_name="gdelt",
                source_url="https://api.gdeltproject.org/",
                retrieved_at=datetime.now(timezone.utc),
            )
        ]

        result = format_bibliography(sources)

        # Should mention archiving or point-in-time
        assert "archive" in result.lower() or "point-in-time" in result.lower()


class TestFormatEntityMatchConfidence:
    """Tests for format_entity_match_confidence function (FR31)."""

    def test_high_confidence_match(self) -> None:
        """High confidence should show percentage and level."""
        result = format_entity_match_confidence(
            confidence_score=0.95,
            resolution_tier="exact",
            wikidata_qid="Q12345",
        )

        assert "95%" in result
        assert "Q12345" in result

    def test_includes_resolution_tier(self) -> None:
        """Output should include resolution method."""
        result = format_entity_match_confidence(
            confidence_score=0.8,
            resolution_tier="normalized",
        )

        assert "normalized" in result

    def test_includes_match_factors(self) -> None:
        """Match factors should be listed if provided."""
        result = format_entity_match_confidence(
            confidence_score=0.9,
            resolution_tier="exact",
            match_factors=["Name match", "Type verified"],
        )

        assert "Name match" in result
        assert "Type verified" in result


class TestFormatSanctionsMatchConfidence:
    """Tests for format_sanctions_match_confidence function (FR31)."""

    def test_high_confidence_assessment(self) -> None:
        """High confidence should indicate likely match."""
        result = format_sanctions_match_confidence(
            match_score=0.95,
            entity_name="Rosneft",
            matched_name="Rosneft Oil Company",
        )

        assert "95%" in result
        assert "HIGH confidence" in result
        assert "Rosneft" in result

    def test_low_confidence_requires_verification(self) -> None:
        """Low confidence should recommend verification."""
        result = format_sanctions_match_confidence(
            match_score=0.45,
            entity_name="Generic Company",
            matched_name="Generic Company Ltd",
        )

        assert "verification" in result.lower()


class TestFormatRigorOutput:
    """Tests for format_rigor_output function."""

    def test_complete_output_has_all_sections(self) -> None:
        """Complete rigor output should have all required sections."""
        sources = [
            SourceMetadata(
                source_name="gdelt",
                source_url="https://api.gdeltproject.org/",
                retrieved_at=datetime.now(timezone.utc),
            )
        ]

        result = format_rigor_output(
            title="Test Topic",
            content="Test content here.",
            sources=sources,
        )

        assert "INTELLIGENCE ASSESSMENT" in result
        assert "Test content" in result
        assert "Source Attribution" in result
        assert "Caveats" in result
        assert "Sources" in result or "SOURCES" in result

    def test_corroboration_included_when_requested(self) -> None:
        """Corroboration section should appear when requested."""
        sources = [
            SourceMetadata(
                source_name="gdelt",
                source_url="https://api.gdeltproject.org/",
                retrieved_at=datetime.now(timezone.utc),
            )
        ]

        result = format_rigor_output(
            title="Test",
            content="Content",
            sources=sources,
            include_corroboration=True,
            corroboration_notes=["Finding corroborated by GDELT and ACLED"],
        )

        assert "Corroboration" in result
        assert "corroborated" in result.lower()


class TestRigorModeConfigSetting:
    """Tests for rigor_mode in Settings class."""

    def test_rigor_mode_env_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IGNIFER_RIGOR_MODE=true should enable rigor mode."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "true")

        settings = Settings()

        assert settings.rigor_mode is True

    def test_rigor_mode_env_yes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IGNIFER_RIGOR_MODE=yes should enable rigor mode."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "yes")

        settings = Settings()

        assert settings.rigor_mode is True

    def test_rigor_mode_env_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IGNIFER_RIGOR_MODE=1 should enable rigor mode."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "1")

        settings = Settings()

        assert settings.rigor_mode is True

    def test_rigor_mode_default_false(self) -> None:
        """Default rigor_mode should be False."""
        with patch.dict(os.environ, {}, clear=True):
            reset_settings()
            settings = Settings()

        assert settings.rigor_mode is False

    def test_rigor_mode_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IGNIFER_RIGOR_MODE should be case insensitive."""
        reset_settings()
        monkeypatch.setenv("IGNIFER_RIGOR_MODE", "TRUE")

        settings = Settings()

        assert settings.rigor_mode is True
