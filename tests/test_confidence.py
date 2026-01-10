"""Tests for ICD 203 Confidence Framework.

Tests:
- ConfidenceLevel enum values and percentage ranges
- confidence_to_language() for all 7 levels
- ConfidenceCalculator with various source quality combinations
- Corroboration boost
- Conflict penalty
- Data age penalty
- percentage_to_level() mapping
- Edge cases
"""

import pytest

from ignifer.confidence import (
    ConfidenceAssessment,
    ConfidenceCalculator,
    confidence_to_language,
)
from ignifer.models import ConfidenceLevel, QualityTier


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""

    def test_has_seven_levels(self) -> None:
        """ConfidenceLevel should have exactly 7 ICD 203 levels."""
        levels = list(ConfidenceLevel)
        assert len(levels) == 7

    def test_level_order(self) -> None:
        """Levels should be ordered from lowest to highest confidence."""
        assert ConfidenceLevel.REMOTE.value < ConfidenceLevel.VERY_UNLIKELY.value
        assert ConfidenceLevel.VERY_UNLIKELY.value < ConfidenceLevel.UNLIKELY.value
        assert ConfidenceLevel.UNLIKELY.value < ConfidenceLevel.ROUGHLY_EVEN.value
        assert ConfidenceLevel.ROUGHLY_EVEN.value < ConfidenceLevel.LIKELY.value
        assert ConfidenceLevel.LIKELY.value < ConfidenceLevel.VERY_LIKELY.value
        assert ConfidenceLevel.VERY_LIKELY.value < ConfidenceLevel.ALMOST_CERTAIN.value

    def test_percentage_range_remote(self) -> None:
        """REMOTE should be <5%."""
        assert ConfidenceLevel.REMOTE.percentage_range == (0, 5)

    def test_percentage_range_very_unlikely(self) -> None:
        """VERY_UNLIKELY should be 5-20%."""
        assert ConfidenceLevel.VERY_UNLIKELY.percentage_range == (5, 20)

    def test_percentage_range_unlikely(self) -> None:
        """UNLIKELY should be 20-45%."""
        assert ConfidenceLevel.UNLIKELY.percentage_range == (20, 45)

    def test_percentage_range_roughly_even(self) -> None:
        """ROUGHLY_EVEN should be 45-55%."""
        assert ConfidenceLevel.ROUGHLY_EVEN.percentage_range == (45, 55)

    def test_percentage_range_likely(self) -> None:
        """LIKELY should be 55-80%."""
        assert ConfidenceLevel.LIKELY.percentage_range == (55, 80)

    def test_percentage_range_very_likely(self) -> None:
        """VERY_LIKELY should be 80-95%."""
        assert ConfidenceLevel.VERY_LIKELY.percentage_range == (80, 95)

    def test_percentage_range_almost_certain(self) -> None:
        """ALMOST_CERTAIN should be 95-100%."""
        assert ConfidenceLevel.ALMOST_CERTAIN.percentage_range == (95, 100)

    def test_to_percentage_range_backward_compat(self) -> None:
        """to_percentage_range() should return same as percentage_range property."""
        for level in ConfidenceLevel:
            assert level.to_percentage_range() == level.percentage_range

    def test_to_label_all_levels(self) -> None:
        """All levels should have human-readable labels."""
        expected_labels = {
            ConfidenceLevel.REMOTE: "Remote possibility",
            ConfidenceLevel.VERY_UNLIKELY: "Very unlikely",
            ConfidenceLevel.UNLIKELY: "Unlikely",
            ConfidenceLevel.ROUGHLY_EVEN: "Roughly even chance",
            ConfidenceLevel.LIKELY: "Likely",
            ConfidenceLevel.VERY_LIKELY: "Very likely",
            ConfidenceLevel.ALMOST_CERTAIN: "Almost certain",
        }
        for level, expected in expected_labels.items():
            assert level.to_label() == expected


class TestConfidenceToLanguage:
    """Tests for confidence_to_language() function."""

    def test_remote_language(self) -> None:
        """REMOTE should use 'remote' phrasing."""
        result = confidence_to_language(ConfidenceLevel.REMOTE)
        assert "remote" in result.lower()
        assert "<5%" in result

    def test_very_unlikely_language(self) -> None:
        """VERY_UNLIKELY should use 'very unlikely' phrasing."""
        result = confidence_to_language(ConfidenceLevel.VERY_UNLIKELY)
        assert "very unlikely" in result.lower()
        assert "5-20%" in result

    def test_unlikely_language(self) -> None:
        """UNLIKELY should use 'unlikely' phrasing."""
        result = confidence_to_language(ConfidenceLevel.UNLIKELY)
        assert "unlikely" in result.lower()
        assert "20-45%" in result

    def test_roughly_even_language(self) -> None:
        """ROUGHLY_EVEN should use 'roughly even' phrasing."""
        result = confidence_to_language(ConfidenceLevel.ROUGHLY_EVEN)
        assert "roughly even" in result.lower()
        assert "45-55%" in result

    def test_likely_language(self) -> None:
        """LIKELY should use 'moderate confidence' phrasing."""
        result = confidence_to_language(ConfidenceLevel.LIKELY)
        assert "moderate confidence" in result.lower()
        assert "55-80%" in result

    def test_very_likely_language(self) -> None:
        """VERY_LIKELY should use 'high confidence' phrasing."""
        result = confidence_to_language(ConfidenceLevel.VERY_LIKELY)
        assert "high confidence" in result.lower()
        assert "80-95%" in result

    def test_almost_certain_language(self) -> None:
        """ALMOST_CERTAIN should use 'very high confidence' phrasing."""
        result = confidence_to_language(ConfidenceLevel.ALMOST_CERTAIN)
        assert "very high confidence" in result.lower()
        assert ">95%" in result

    def test_with_assessment_text(self) -> None:
        """Assessment text should be incorporated into the phrase."""
        result = confidence_to_language(
            ConfidenceLevel.LIKELY,
            "the entity is sanctioned",
        )
        assert "the entity is sanctioned" in result
        assert result.endswith(".")

    def test_assessment_text_lowercase_start(self) -> None:
        """Assessment text starting with capital should be lowercased."""
        result = confidence_to_language(
            ConfidenceLevel.LIKELY,
            "The entity is sanctioned",
        )
        # Should lowercase "The" to "the" after "that"
        assert "the entity is sanctioned" in result

    def test_assessment_text_punctuation(self) -> None:
        """Assessment text should end with period if not punctuated."""
        result = confidence_to_language(
            ConfidenceLevel.LIKELY,
            "the entity is sanctioned",
        )
        assert result.endswith(".")

    def test_assessment_text_existing_punctuation(self) -> None:
        """Assessment text with existing punctuation should not get extra period."""
        result = confidence_to_language(
            ConfidenceLevel.LIKELY,
            "the entity is sanctioned.",
        )
        assert not result.endswith("..")


class TestConfidenceAssessment:
    """Tests for ConfidenceAssessment model."""

    def test_create_valid_assessment(self) -> None:
        """Should create valid assessment with all fields."""
        assessment = ConfidenceAssessment(
            level=ConfidenceLevel.LIKELY,
            percentage=0.65,
            reasoning="Based on multiple sources.",
            key_factors=["Factor 1", "Factor 2"],
        )
        assert assessment.level == ConfidenceLevel.LIKELY
        assert assessment.percentage == 0.65
        assert assessment.reasoning == "Based on multiple sources."
        assert len(assessment.key_factors) == 2

    def test_percentage_range_property(self) -> None:
        """percentage_range should return level's range."""
        assessment = ConfidenceAssessment(
            level=ConfidenceLevel.LIKELY,
            percentage=0.65,
            reasoning="Test",
        )
        assert assessment.percentage_range == (55, 80)

    def test_percentage_validation_min(self) -> None:
        """Percentage should not be less than 0.0."""
        with pytest.raises(ValueError):
            ConfidenceAssessment(
                level=ConfidenceLevel.REMOTE,
                percentage=-0.1,
                reasoning="Test",
            )

    def test_percentage_validation_max(self) -> None:
        """Percentage should not exceed 1.0."""
        with pytest.raises(ValueError):
            ConfidenceAssessment(
                level=ConfidenceLevel.ALMOST_CERTAIN,
                percentage=1.1,
                reasoning="Test",
            )

    def test_default_key_factors(self) -> None:
        """key_factors should default to empty list."""
        assessment = ConfidenceAssessment(
            level=ConfidenceLevel.LIKELY,
            percentage=0.65,
            reasoning="Test",
        )
        assert assessment.key_factors == []


class TestConfidenceCalculator:
    """Tests for ConfidenceCalculator class."""

    @pytest.fixture
    def calculator(self) -> ConfidenceCalculator:
        """Provide a ConfidenceCalculator instance."""
        return ConfidenceCalculator()

    def test_high_quality_base_confidence(self, calculator: ConfidenceCalculator) -> None:
        """HIGH quality should have 0.8 base confidence."""
        result = calculator.calculate_from_sources([QualityTier.HIGH])
        assert result.percentage == pytest.approx(0.8, abs=0.01)

    def test_medium_quality_base_confidence(self, calculator: ConfidenceCalculator) -> None:
        """MEDIUM quality should have 0.6 base confidence."""
        result = calculator.calculate_from_sources([QualityTier.MEDIUM])
        assert result.percentage == pytest.approx(0.6, abs=0.01)

    def test_low_quality_base_confidence(self, calculator: ConfidenceCalculator) -> None:
        """LOW quality should have 0.4 base confidence."""
        result = calculator.calculate_from_sources([QualityTier.LOW])
        assert result.percentage == pytest.approx(0.4, abs=0.01)

    def test_weakest_link_used(self, calculator: ConfidenceCalculator) -> None:
        """Base confidence should use weakest (lowest) quality tier."""
        result = calculator.calculate_from_sources(
            [QualityTier.HIGH, QualityTier.MEDIUM, QualityTier.LOW]
        )
        # Weakest is LOW (0.4 base)
        assert result.percentage == pytest.approx(0.4, abs=0.01)

    def test_corroboration_boost_one_source(self, calculator: ConfidenceCalculator) -> None:
        """Corroboration boost should be +0.05 per corroborating source."""
        result = calculator.calculate_from_sources(
            [QualityTier.MEDIUM],
            corroborating_count=1,
        )
        # 0.6 base + 0.05 boost = 0.65
        assert result.percentage == pytest.approx(0.65, abs=0.01)

    def test_corroboration_boost_three_sources(self, calculator: ConfidenceCalculator) -> None:
        """Corroboration boost should max at +0.15."""
        result = calculator.calculate_from_sources(
            [QualityTier.MEDIUM],
            corroborating_count=3,
        )
        # 0.6 base + 0.15 boost = 0.75
        assert result.percentage == pytest.approx(0.75, abs=0.01)

    def test_corroboration_boost_capped(self, calculator: ConfidenceCalculator) -> None:
        """Corroboration boost should not exceed +0.15."""
        result = calculator.calculate_from_sources(
            [QualityTier.MEDIUM],
            corroborating_count=10,
        )
        # 0.6 base + 0.15 (capped) = 0.75
        assert result.percentage == pytest.approx(0.75, abs=0.01)

    def test_conflict_penalty_one_conflict(self, calculator: ConfidenceCalculator) -> None:
        """Conflict penalty should be -0.1 per conflict."""
        result = calculator.calculate_from_sources(
            [QualityTier.MEDIUM],
            conflicting_count=1,
        )
        # 0.6 base - 0.1 penalty = 0.5
        assert result.percentage == pytest.approx(0.5, abs=0.01)

    def test_conflict_penalty_two_conflicts(self, calculator: ConfidenceCalculator) -> None:
        """Conflict penalty should max at -0.2."""
        result = calculator.calculate_from_sources(
            [QualityTier.MEDIUM],
            conflicting_count=2,
        )
        # 0.6 base - 0.2 penalty = 0.4
        assert result.percentage == pytest.approx(0.4, abs=0.01)

    def test_conflict_penalty_capped(self, calculator: ConfidenceCalculator) -> None:
        """Conflict penalty should not exceed -0.2."""
        result = calculator.calculate_from_sources(
            [QualityTier.MEDIUM],
            conflicting_count=10,
        )
        # 0.6 base - 0.2 (capped) = 0.4
        assert result.percentage == pytest.approx(0.4, abs=0.01)

    def test_data_age_no_penalty_within_threshold(self, calculator: ConfidenceCalculator) -> None:
        """No penalty for data within 7 days."""
        result = calculator.calculate_from_sources(
            [QualityTier.MEDIUM],
            data_age_hours=24 * 6,  # 6 days
        )
        # 0.6 base, no penalty
        assert result.percentage == pytest.approx(0.6, abs=0.01)

    def test_data_age_penalty_over_threshold(self, calculator: ConfidenceCalculator) -> None:
        """Penalty should apply for data over 7 days old."""
        result = calculator.calculate_from_sources(
            [QualityTier.MEDIUM],
            data_age_hours=24 * 8,  # 8 days (1 day over threshold)
        )
        # 0.6 base - 0.02 (1 day penalty) = 0.58
        assert result.percentage == pytest.approx(0.58, abs=0.01)

    def test_data_age_penalty_capped(self, calculator: ConfidenceCalculator) -> None:
        """Age penalty should not exceed -0.1."""
        result = calculator.calculate_from_sources(
            [QualityTier.MEDIUM],
            data_age_hours=24 * 30,  # 30 days (23 days over threshold)
        )
        # 0.6 base - 0.1 (capped) = 0.5
        assert result.percentage == pytest.approx(0.5, abs=0.01)

    def test_combined_adjustments(self, calculator: ConfidenceCalculator) -> None:
        """Multiple adjustments should combine correctly."""
        result = calculator.calculate_from_sources(
            [QualityTier.HIGH],
            corroborating_count=2,
            conflicting_count=1,
            data_age_hours=24 * 10,  # 3 days over threshold
        )
        # 0.8 base + 0.1 (2 corroborating) - 0.1 (1 conflict) - 0.06 (3 days * 0.02)
        expected = 0.8 + 0.1 - 0.1 - 0.06
        assert result.percentage == pytest.approx(expected, abs=0.01)

    def test_clamped_minimum(self, calculator: ConfidenceCalculator) -> None:
        """Confidence should not go below 0.05."""
        result = calculator.calculate_from_sources(
            [QualityTier.LOW],
            conflicting_count=10,  # Massive penalty
            data_age_hours=24 * 100,  # Very old data
        )
        assert result.percentage >= 0.05

    def test_clamped_maximum(self, calculator: ConfidenceCalculator) -> None:
        """Confidence should not exceed 0.98."""
        result = calculator.calculate_from_sources(
            [QualityTier.HIGH],
            corroborating_count=10,  # Maximum boost
        )
        assert result.percentage <= 0.98

    def test_empty_sources(self, calculator: ConfidenceCalculator) -> None:
        """Empty sources should return minimum confidence."""
        result = calculator.calculate_from_sources([])
        assert result.level == ConfidenceLevel.REMOTE
        assert result.percentage == 0.05

    def test_all_high_sources(self, calculator: ConfidenceCalculator) -> None:
        """All HIGH sources should use HIGH base confidence."""
        result = calculator.calculate_from_sources(
            [QualityTier.HIGH, QualityTier.HIGH, QualityTier.HIGH]
        )
        assert result.percentage == pytest.approx(0.8, abs=0.01)

    def test_all_low_sources(self, calculator: ConfidenceCalculator) -> None:
        """All LOW sources should use LOW base confidence."""
        result = calculator.calculate_from_sources(
            [QualityTier.LOW, QualityTier.LOW, QualityTier.LOW]
        )
        assert result.percentage == pytest.approx(0.4, abs=0.01)

    def test_key_factors_populated(self, calculator: ConfidenceCalculator) -> None:
        """key_factors should explain all adjustments."""
        result = calculator.calculate_from_sources(
            [QualityTier.MEDIUM],
            corroborating_count=1,
            conflicting_count=1,
            data_age_hours=24 * 10,
        )
        assert len(result.key_factors) >= 4  # Base + 3 adjustments

    def test_reasoning_populated(self, calculator: ConfidenceCalculator) -> None:
        """reasoning should explain the assessment."""
        result = calculator.calculate_from_sources([QualityTier.HIGH])
        assert len(result.reasoning) > 0
        assert "HIGH" in result.reasoning


class TestPercentageToLevel:
    """Tests for percentage_to_level() method."""

    @pytest.fixture
    def calculator(self) -> ConfidenceCalculator:
        """Provide a ConfidenceCalculator instance."""
        return ConfidenceCalculator()

    def test_remote_boundary(self, calculator: ConfidenceCalculator) -> None:
        """<0.05 should map to REMOTE."""
        assert calculator.percentage_to_level(0.0) == ConfidenceLevel.REMOTE
        assert calculator.percentage_to_level(0.04) == ConfidenceLevel.REMOTE

    def test_very_unlikely_boundary(self, calculator: ConfidenceCalculator) -> None:
        """0.05-0.19 should map to VERY_UNLIKELY."""
        assert calculator.percentage_to_level(0.05) == ConfidenceLevel.VERY_UNLIKELY
        assert calculator.percentage_to_level(0.10) == ConfidenceLevel.VERY_UNLIKELY
        assert calculator.percentage_to_level(0.19) == ConfidenceLevel.VERY_UNLIKELY

    def test_unlikely_boundary(self, calculator: ConfidenceCalculator) -> None:
        """0.20-0.44 should map to UNLIKELY."""
        assert calculator.percentage_to_level(0.20) == ConfidenceLevel.UNLIKELY
        assert calculator.percentage_to_level(0.30) == ConfidenceLevel.UNLIKELY
        assert calculator.percentage_to_level(0.44) == ConfidenceLevel.UNLIKELY

    def test_roughly_even_boundary(self, calculator: ConfidenceCalculator) -> None:
        """0.45-0.54 should map to ROUGHLY_EVEN."""
        assert calculator.percentage_to_level(0.45) == ConfidenceLevel.ROUGHLY_EVEN
        assert calculator.percentage_to_level(0.50) == ConfidenceLevel.ROUGHLY_EVEN
        assert calculator.percentage_to_level(0.54) == ConfidenceLevel.ROUGHLY_EVEN

    def test_likely_boundary(self, calculator: ConfidenceCalculator) -> None:
        """0.55-0.79 should map to LIKELY."""
        assert calculator.percentage_to_level(0.55) == ConfidenceLevel.LIKELY
        assert calculator.percentage_to_level(0.65) == ConfidenceLevel.LIKELY
        assert calculator.percentage_to_level(0.79) == ConfidenceLevel.LIKELY

    def test_very_likely_boundary(self, calculator: ConfidenceCalculator) -> None:
        """0.80-0.94 should map to VERY_LIKELY."""
        assert calculator.percentage_to_level(0.80) == ConfidenceLevel.VERY_LIKELY
        assert calculator.percentage_to_level(0.85) == ConfidenceLevel.VERY_LIKELY
        assert calculator.percentage_to_level(0.94) == ConfidenceLevel.VERY_LIKELY

    def test_almost_certain_boundary(self, calculator: ConfidenceCalculator) -> None:
        """>=0.95 should map to ALMOST_CERTAIN."""
        assert calculator.percentage_to_level(0.95) == ConfidenceLevel.ALMOST_CERTAIN
        assert calculator.percentage_to_level(0.99) == ConfidenceLevel.ALMOST_CERTAIN
        assert calculator.percentage_to_level(1.0) == ConfidenceLevel.ALMOST_CERTAIN

    def test_negative_percentage_maps_to_remote(self, calculator: ConfidenceCalculator) -> None:
        """Negative percentages should map to REMOTE (edge case handling)."""
        assert calculator.percentage_to_level(-0.1) == ConfidenceLevel.REMOTE
        assert calculator.percentage_to_level(-1.0) == ConfidenceLevel.REMOTE

    def test_percentage_above_one_maps_to_almost_certain(
        self, calculator: ConfidenceCalculator
    ) -> None:
        """Percentages above 1.0 should map to ALMOST_CERTAIN (edge case handling)."""
        assert calculator.percentage_to_level(1.5) == ConfidenceLevel.ALMOST_CERTAIN
        assert calculator.percentage_to_level(2.0) == ConfidenceLevel.ALMOST_CERTAIN


class TestConfidenceIntegration:
    """Integration tests for confidence framework."""

    def test_high_confidence_scenario(self) -> None:
        """High quality sources with corroboration should yield high confidence."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate_from_sources(
            [QualityTier.HIGH, QualityTier.HIGH],
            corroborating_count=2,
        )
        assert result.level in (
            ConfidenceLevel.VERY_LIKELY,
            ConfidenceLevel.ALMOST_CERTAIN,
        )
        lang = confidence_to_language(result.level, "the assessment is accurate")
        assert "confidence" in lang.lower()

    def test_low_confidence_scenario(self) -> None:
        """Low quality sources with conflicts should yield low confidence."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate_from_sources(
            [QualityTier.LOW],
            conflicting_count=2,
            data_age_hours=24 * 15,
        )
        assert result.level in (
            ConfidenceLevel.REMOTE,
            ConfidenceLevel.VERY_UNLIKELY,
            ConfidenceLevel.UNLIKELY,
        )
        lang = confidence_to_language(result.level)
        assert "unlikely" in lang.lower() or "remote" in lang.lower()

    def test_moderate_confidence_scenario(self) -> None:
        """Mixed quality sources should yield moderate confidence."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate_from_sources(
            [QualityTier.MEDIUM, QualityTier.HIGH],
            corroborating_count=1,
        )
        # Medium as weakest: 0.6 + 0.05 = 0.65 -> LIKELY
        assert result.level == ConfidenceLevel.LIKELY
        lang = confidence_to_language(result.level)
        assert "moderate confidence" in lang.lower()
