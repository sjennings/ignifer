"""Pydantic models for Ignifer OSINT aggregation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


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

    @classmethod
    def from_percentage(cls, percentage: float) -> "ConfidenceLevel":
        """Map percentage (0.0-1.0) to appropriate ConfidenceLevel.

        Args:
            percentage: Confidence as float between 0.0 and 1.0.

        Returns:
            ConfidenceLevel corresponding to the percentage.
        """
        if percentage >= 0.95:
            return cls.ALMOST_CERTAIN
        elif percentage >= 0.80:
            return cls.VERY_LIKELY
        elif percentage >= 0.55:
            return cls.LIKELY
        elif percentage >= 0.45:
            return cls.ROUGHLY_EVEN
        elif percentage >= 0.20:
            return cls.UNLIKELY
        elif percentage >= 0.05:
            return cls.VERY_UNLIKELY
        else:
            return cls.REMOTE


class QualityTier(Enum):
    """Source quality tier classification."""

    HIGH = "H"  # Official sources, academic research
    MEDIUM = "M"  # Reputable news, verified OSINT
    LOW = "L"  # Social media, unverified reports

    @property
    def ordering(self) -> int:
        """Numeric ordering for comparisons (lower is better quality).

        Returns:
            0 for HIGH, 1 for MEDIUM, 2 for LOW.
        """
        return {QualityTier.HIGH: 0, QualityTier.MEDIUM: 1, QualityTier.LOW: 2}[self]


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


class SourceMetadataEntry(BaseModel):
    """Persistent metadata about a news source domain.

    Stores language, nation, political orientation, and IC-style reliability
    grades for news domains. Auto-enriched from GDELT data on first encounter,
    with user override capability.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    domain: str
    language: str | None = None
    nation: str | None = None
    political_orientation: str | None = None
    orientation_axis: str | None = None
    orientation_tags: list[str] = []
    reliability: str = "C"  # IC-style A-F grade, default "Fairly reliable"
    enrichment_source: str = "auto:gdelt_baseline"
    enrichment_date: datetime = datetime.now(timezone.utc)
    original_reliability: str | None = None  # For rollback after user override
    original_orientation: str | None = None  # For rollback after user override

    @field_validator("reliability")
    @classmethod
    def validate_reliability(cls, v: str) -> str:
        """Validate reliability is A-F grade."""
        valid_grades = ("A", "B", "C", "D", "E", "F")
        if v.upper() not in valid_grades:
            msg = f"Invalid reliability grade '{v}'. Must be A-F."
            raise ValueError(msg)
        return v.upper()

    @field_serializer("orientation_tags")
    def serialize_tags(self, tags: list[str]) -> str:
        """Serialize to JSON for SQLite storage."""
        return json.dumps(tags)

    @field_validator("orientation_tags", mode="before")
    @classmethod
    def deserialize_tags(cls, v: str | list[str] | None) -> list[str]:
        """Deserialize from JSON string if needed."""
        if isinstance(v, str):
            return json.loads(v) if v else []
        return v or []

    @field_serializer("enrichment_date")
    def serialize_date(self, dt: datetime) -> str:
        """Serialize to ISO 8601 with UTC timezone."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    @field_validator("enrichment_date", mode="before")
    @classmethod
    def parse_date(cls, v: str | datetime) -> datetime:
        """Parse from ISO string, assume UTC if no timezone."""
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        return v


__all__ = [
    "QueryParams",
    "SourceMetadata",
    "SourceMetadataEntry",
    "SourceAttribution",
    "ConfidenceLevel",
    "QualityTier",
    "ResultStatus",
    "OSINTResult",
]
