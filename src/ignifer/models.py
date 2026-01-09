"""Pydantic models for Ignifer OSINT aggregation."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_serializer


class ConfidenceLevel(Enum):
    """ICD 203 intelligence confidence levels."""

    REMOTE = 1  # <20%
    UNLIKELY = 2  # 20-40%
    EVEN_CHANCE = 3  # 40-60%
    LIKELY = 4  # 60-80%
    VERY_LIKELY = 5  # 80-95%
    ALMOST_CERTAIN = 6  # >95%

    def to_percentage_range(self) -> tuple[int, int]:
        """Convert confidence level to percentage range."""
        ranges = {
            ConfidenceLevel.REMOTE: (0, 20),
            ConfidenceLevel.UNLIKELY: (20, 40),
            ConfidenceLevel.EVEN_CHANCE: (40, 60),
            ConfidenceLevel.LIKELY: (60, 80),
            ConfidenceLevel.VERY_LIKELY: (80, 95),
            ConfidenceLevel.ALMOST_CERTAIN: (95, 100),
        }
        return ranges[self]

    def to_label(self) -> str:
        """Convert confidence level to human-readable label."""
        labels = {
            ConfidenceLevel.REMOTE: "Remote possibility",
            ConfidenceLevel.UNLIKELY: "Unlikely",
            ConfidenceLevel.EVEN_CHANCE: "Even chance",
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
