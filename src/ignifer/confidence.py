"""ICD 203 Confidence Framework for Ignifer.

Provides IC-standard confidence levels, language conversion, and
confidence calculation from source quality factors.

Implements:
- TR1: Full ICD 203 confidence levels
- FR28: ICD 203-compliant confidence language
- TR2/TR3: Confidence derived from source quality
"""

from pydantic import BaseModel, ConfigDict, Field

from ignifer.models import ConfidenceLevel, QualityTier


class ConfidenceAssessment(BaseModel):
    """Structured confidence assessment with ICD 203 compliance.

    Attributes:
        level: ICD 203 confidence level (REMOTE to ALMOST_CERTAIN).
        percentage: Numeric confidence as 0.0-1.0 float.
        reasoning: Explanation of confidence derivation.
        key_factors: List of factors affecting the confidence assessment.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    level: ConfidenceLevel
    percentage: float = Field(ge=0.0, le=1.0)
    reasoning: str
    key_factors: list[str] = Field(default_factory=list)

    @property
    def percentage_range(self) -> tuple[int, int]:
        """Return the percentage range for this confidence level.

        Returns:
            Tuple of (min_percentage, max_percentage) from the confidence level.
        """
        return self.level.percentage_range


def confidence_to_language(level: ConfidenceLevel, assessment_text: str = "") -> str:
    """Convert confidence level to IC-standard phrasing.

    Generates professional analytical language following ICD 203 standards.
    If assessment_text is provided, it is incorporated into the phrase.

    Args:
        level: ConfidenceLevel enum value.
        assessment_text: Optional text to incorporate (e.g., "the target is located in Moscow").

    Returns:
        IC-standard phrasing for the confidence level.

    Examples:
        >>> confidence_to_language(ConfidenceLevel.LIKELY)
        "We assess with moderate confidence (55-80%) that..."

        >>> confidence_to_language(ConfidenceLevel.LIKELY, "the entity is sanctioned")
        "We assess with moderate confidence (55-80%) that the entity is sanctioned."
    """
    phrases = {
        ConfidenceLevel.REMOTE: ("It is remote that", "<5%"),
        ConfidenceLevel.VERY_UNLIKELY: ("It is very unlikely that", "5-20%"),
        ConfidenceLevel.UNLIKELY: ("It is unlikely that", "20-45%"),
        ConfidenceLevel.ROUGHLY_EVEN: ("It is roughly even odds that", "45-55%"),
        ConfidenceLevel.LIKELY: ("We assess with moderate confidence that", "55-80%"),
        ConfidenceLevel.VERY_LIKELY: ("We assess with high confidence that", "80-95%"),
        ConfidenceLevel.ALMOST_CERTAIN: ("We assess with very high confidence that", ">95%"),
    }

    phrase, range_str = phrases[level]

    if assessment_text:
        # Clean up text - ensure it doesn't start with capital after "that"
        text = assessment_text.strip()
        if text and text[0].isupper():
            text = text[0].lower() + text[1:]
        # Ensure proper ending punctuation
        if text and not text.endswith((".", "!", "?")):
            text = text + "."
        return f"{phrase} ({range_str}) {text}"
    else:
        return f"{phrase} ({range_str})..."


class ConfidenceCalculator:
    """Calculate confidence from source quality and corroboration.

    Implements confidence scoring based on:
    - Source quality tier (HIGH/MEDIUM/LOW)
    - Number of corroborating sources
    - Number of conflicting sources
    - Data age/recency

    Rules:
    - Base confidence from weakest source quality tier
    - Corroboration boost: +0.05 per corroborating source (max +0.15)
    - Conflict penalty: -0.1 per conflict (max -0.2)
    - Data age penalty: -0.02 per 24 hours over 7 days (max -0.1)
    - Final result clamped to 0.05-0.98 range
    """

    # Base confidence for each quality tier
    QUALITY_BASE = {
        QualityTier.HIGH: 0.8,
        QualityTier.MEDIUM: 0.6,
        QualityTier.LOW: 0.4,
    }

    # Adjustment limits
    CORROBORATION_BOOST_PER_SOURCE = 0.05
    CORROBORATION_BOOST_MAX = 0.15
    CONFLICT_PENALTY_PER_CONFLICT = 0.1
    CONFLICT_PENALTY_MAX = 0.2
    AGE_PENALTY_PER_DAY_OVER_THRESHOLD = 0.02 / 1.0  # Per day after threshold
    AGE_THRESHOLD_DAYS = 7
    AGE_PENALTY_MAX = 0.1

    # Clamp limits
    MIN_CONFIDENCE = 0.05
    MAX_CONFIDENCE = 0.98

    def calculate_from_sources(
        self,
        quality_tiers: list[QualityTier],
        corroborating_count: int = 0,
        conflicting_count: int = 0,
        data_age_hours: float = 0,
    ) -> ConfidenceAssessment:
        """Calculate confidence based on source quality factors.

        Args:
            quality_tiers: List of QualityTier values from contributing sources.
            corroborating_count: Number of sources that corroborate the finding.
            conflicting_count: Number of sources with conflicting information.
            data_age_hours: Age of the data in hours (0 = fresh).

        Returns:
            ConfidenceAssessment with calculated level, percentage, and reasoning.
        """
        key_factors: list[str] = []

        # Handle empty sources case
        if not quality_tiers:
            return ConfidenceAssessment(
                level=ConfidenceLevel.REMOTE,
                percentage=self.MIN_CONFIDENCE,
                reasoning="No source quality information available.",
                key_factors=["No sources provided"],
            )

        # Weakest link: use lowest quality tier
        weakest_tier = max(quality_tiers, key=lambda t: t.ordering)
        base_confidence = self.QUALITY_BASE.get(weakest_tier, 0.4)
        key_factors.append(
            f"Base confidence from {weakest_tier.name} quality source: {base_confidence:.0%}"
        )

        # Corroboration boost
        corroboration_boost = min(
            corroborating_count * self.CORROBORATION_BOOST_PER_SOURCE,
            self.CORROBORATION_BOOST_MAX,
        )
        if corroboration_boost > 0:
            key_factors.append(
                f"Corroboration boost: +{corroboration_boost:.0%} "
                f"({corroborating_count} corroborating source(s))"
            )

        # Conflict penalty
        conflict_penalty = min(
            conflicting_count * self.CONFLICT_PENALTY_PER_CONFLICT,
            self.CONFLICT_PENALTY_MAX,
        )
        if conflict_penalty > 0:
            key_factors.append(
                f"Conflict penalty: -{conflict_penalty:.0%} "
                f"({conflicting_count} conflicting source(s))"
            )

        # Data age penalty (only after 7 days)
        age_penalty = 0.0
        if data_age_hours > self.AGE_THRESHOLD_DAYS * 24:
            days_over_threshold = (data_age_hours - self.AGE_THRESHOLD_DAYS * 24) / 24
            age_penalty = min(
                days_over_threshold * self.AGE_PENALTY_PER_DAY_OVER_THRESHOLD,
                self.AGE_PENALTY_MAX,
            )
            if age_penalty > 0:
                key_factors.append(
                    f"Data age penalty: -{age_penalty:.0%} "
                    f"(data is {data_age_hours / 24:.1f} days old)"
                )

        # Calculate final confidence
        final_confidence = base_confidence + corroboration_boost - conflict_penalty - age_penalty

        # Clamp to valid range
        final_confidence = max(self.MIN_CONFIDENCE, min(self.MAX_CONFIDENCE, final_confidence))

        # Map to level
        level = self.percentage_to_level(final_confidence)

        # Build reasoning
        reasoning_parts = [
            f"Based on {len(quality_tiers)} source(s) "
            f"with {weakest_tier.name} as weakest quality tier."
        ]
        if corroborating_count > 0:
            reasoning_parts.append(f"{corroborating_count} source(s) corroborate this finding.")
        if conflicting_count > 0:
            reasoning_parts.append(
                f"{conflicting_count} source(s) present conflicting information."
            )
        if age_penalty > 0:
            reasoning_parts.append("Data freshness has been factored into assessment.")

        return ConfidenceAssessment(
            level=level,
            percentage=final_confidence,
            reasoning=" ".join(reasoning_parts),
            key_factors=key_factors,
        )

    def percentage_to_level(self, percentage: float) -> ConfidenceLevel:
        """Map percentage (0.0-1.0) to appropriate ConfidenceLevel.

        Args:
            percentage: Confidence as float between 0.0 and 1.0.

        Returns:
            ConfidenceLevel corresponding to the percentage.
        """
        return ConfidenceLevel.from_percentage(percentage)


__all__ = [
    "ConfidenceAssessment",
    "ConfidenceCalculator",
    "confidence_to_language",
]
