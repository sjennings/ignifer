"""Pydantic models for Ignifer OSINT aggregation."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_serializer


class ConfidenceLevel(Enum):
    """ICD 203 intelligence confidence levels.

    Based on Intelligence Community Directive 203 probabilistic language:
    - REMOTE: <5% probability
    - VERY_UNLIKELY: 5-20% probability
    - UNLIKELY: 20-45% probability
    - ROUGHLY_EVEN: 45-55% probability
    - LIKELY: 55-80% probability
    - VERY_LIKELY: 80-95% probability
    - ALMOST_CERTAIN: >95% probability
    """

    REMOTE = 1  # <5%
    VERY_UNLIKELY = 2  # 5-20%
    UNLIKELY = 3  # 20-45%
    ROUGHLY_EVEN = 4  # 45-55%
    LIKELY = 5  # 55-80%
    VERY_LIKELY = 6  # 80-95%
    ALMOST_CERTAIN = 7  # >95%

    @property
    def percentage_range(self) -> tuple[int, int]:
        """Return percentage range as tuple (min, max).

        Returns:
            Tuple of (min_percentage, max_percentage).
        """
        ranges = {
            ConfidenceLevel.REMOTE: (0, 5),
            ConfidenceLevel.VERY_UNLIKELY: (5, 20),
            ConfidenceLevel.UNLIKELY: (20, 45),
            ConfidenceLevel.ROUGHLY_EVEN: (45, 55),
            ConfidenceLevel.LIKELY: (55, 80),
            ConfidenceLevel.VERY_LIKELY: (80, 95),
            ConfidenceLevel.ALMOST_CERTAIN: (95, 100),
        }
        return ranges[self]

    def to_percentage_range(self) -> tuple[int, int]:
        """Convert confidence level to percentage range.

        Deprecated: Use percentage_range property instead.
        Maintained for backward compatibility.

        Returns:
            Tuple of (min_percentage, max_percentage).
        """
        return self.percentage_range

    def to_label(self) -> str:
        """Convert confidence level to human-readable label.

        Returns:
            Human-readable label for the confidence level.
        """
        labels = {
            ConfidenceLevel.REMOTE: "Remote possibility",
            ConfidenceLevel.VERY_UNLIKELY: "Very unlikely",
            ConfidenceLevel.UNLIKELY: "Unlikely",
            ConfidenceLevel.ROUGHLY_EVEN: "Roughly even chance",
            ConfidenceLevel.LIKELY: "Likely",
            ConfidenceLevel.VERY_LIKELY: "Very likely",
            ConfidenceLevel.ALMOST_CERTAIN: "Almost certain",
        }
        return labels[self]


class QualityTier(Enum):
    """Source quality tier classification."""

    HIGH = "H"  # Official sources, academic research
    MEDIUM = "M"  # Reputable news, verified OSINT
    LOW = "L"  # Social media, unverified reports


class ResultStatus(Enum):
    """Result status enumeration."""

    SUCCESS = "success"
    NO_DATA = "no_data"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


class QueryParams(BaseModel):
    """Parameters for OSINT query."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    query: str
    include_sources: list[str] | None = None
    exclude_sources: list[str] | None = None
    max_results_per_source: int = 10
    time_range: str | None = None


class SourceMetadata(BaseModel):
    """Metadata about a data source."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    source_name: str
    source_url: str
    retrieved_at: datetime

    @field_serializer("retrieved_at")
    def serialize_dt(self, dt: datetime) -> str:
        """Serialize datetime to ISO 8601 format with timezone."""
        return dt.isoformat()


class SourceAttribution(BaseModel):
    """Attribution for a specific data source."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    source: str
    quality: QualityTier
    confidence: ConfidenceLevel
    metadata: SourceMetadata


class OSINTResult(BaseModel):
    """OSINT query result."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    status: ResultStatus
    query: str
    results: list[dict[str, str | int | float | bool | None]]
    sources: list[SourceAttribution]
    retrieved_at: datetime
    error: str | None = None

    @field_serializer("retrieved_at")
    def serialize_dt(self, dt: datetime) -> str:
        """Serialize datetime to ISO 8601 format with timezone."""
        return dt.isoformat()


__all__ = [
    "QueryParams",
    "SourceMetadata",
    "SourceAttribution",
    "ConfidenceLevel",
    "QualityTier",
    "ResultStatus",
    "OSINTResult",
]
