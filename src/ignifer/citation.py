"""Citation and attribution formatting for OSINT sources.

Provides academic citation formatting for Ignifer data sources,
supporting inline citations, footnotes, bibliographies, and
multi-source attribution with corroboration notes.

Implements:
- FR29: Source URLs and retrieval timestamps for all data points
- FR30: Academic citation formatting for Rigor Mode output
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from ignifer.aggregation.correlator import SourceContribution

from ignifer.models import SourceMetadata

logger = logging.getLogger(__name__)


class DataFreshness(str, Enum):
    """Data freshness classification based on retrieval time."""

    FRESH = "fresh"  # < 1 hour
    RECENT = "recent"  # 1-24 hours
    STALE = "stale"  # > 24 hours
    ARCHIVED = "archived"  # > 7 days


def get_data_freshness(retrieved_at: datetime) -> DataFreshness:
    """Determine data freshness based on retrieval time.

    Args:
        retrieved_at: The datetime when the data was retrieved.

    Returns:
        DataFreshness enum indicating how fresh the data is.
    """
    now = datetime.now(timezone.utc)

    # Ensure retrieved_at is timezone-aware
    if retrieved_at.tzinfo is None:
        retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)

    age = now - retrieved_at

    if age < timedelta(hours=1):
        return DataFreshness.FRESH
    elif age < timedelta(hours=24):
        return DataFreshness.RECENT
    elif age < timedelta(days=7):
        return DataFreshness.STALE
    else:
        return DataFreshness.ARCHIVED


def get_freshness_label(freshness: DataFreshness) -> str:
    """Get human-readable label for data freshness.

    Args:
        freshness: The DataFreshness enum value.

    Returns:
        Human-readable description of the freshness.
    """
    labels = {
        DataFreshness.FRESH: "Fresh (<1 hour old)",
        DataFreshness.RECENT: "Recent (1-24 hours old)",
        DataFreshness.STALE: "Stale (1-7 days old)",
        DataFreshness.ARCHIVED: "Archived (>7 days old)",
    }
    return labels[freshness]


class CitationWithWarnings(BaseModel):
    """Citation text with associated warnings and disclaimers."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    citation: str
    warnings: list[str]
    disclaimer: str


# Source display names for academic citations
SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "gdelt": "GDELT Project",
    "worldbank": "World Bank",
    "wikidata": "Wikidata",
    "opensky": "OpenSky Network",
    "aisstream": "AISStream",
    "acled": "Armed Conflict Location & Event Data Project (ACLED)",
    "opensanctions": "OpenSanctions",
}

# Dataset titles for bibliography entries
SOURCE_TITLES: dict[str, str] = {
    "gdelt": "Global Database of Events, Language, and Tone",
    "worldbank": "World Development Indicators",
    "wikidata": "Wikidata Knowledge Base",
    "opensky": "OpenSky Network ADS-B Data",
    "aisstream": "AISStream Maritime AIS Data",
    "acled": "Armed Conflict Location & Event Data Project",
    "opensanctions": "OpenSanctions Consolidated Sanctions Database",
}

# Standard disclaimer text
POINT_IN_TIME_DISCLAIMER = (
    "Note: Data reflects point-in-time snapshot. URLs may change; "
    "consider archiving via archive.org for permanent reference."
)


class CitationFormatter:
    """Academic citation formatting for OSINT sources.

    Provides methods to format source metadata as inline citations,
    footnotes, bibliographies, and multi-source attributions.
    """

    def __init__(self) -> None:
        """Initialize the citation formatter."""
        self.source_names = SOURCE_DISPLAY_NAMES
        self.source_titles = SOURCE_TITLES

    def _get_display_name(self, source_name: str) -> str:
        """Get display name for a source.

        Args:
            source_name: The internal source identifier.

        Returns:
            Human-readable display name.
        """
        # Replace underscores with spaces before title-casing for unknown sources
        display = self.source_names.get(source_name.lower())
        if display is None:
            display = source_name.replace("_", " ").title()
        return display

    def _get_source_title(self, source_name: str) -> str:
        """Get dataset title for a source.

        Args:
            source_name: The internal source identifier.

        Returns:
            Dataset title for bibliography entry.
        """
        return self.source_titles.get(source_name.lower(), f"{source_name.title()} Data")

    def _format_timestamp(self, dt: datetime) -> str:
        """Format datetime as ISO 8601 string with timezone.

        Args:
            dt: The datetime to format.

        Returns:
            ISO 8601 formatted string.
        """
        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    def _format_date(self, dt: datetime) -> str:
        """Format datetime as date string (YYYY-MM-DD).

        Args:
            dt: The datetime to format.

        Returns:
            Date string in YYYY-MM-DD format.
        """
        return dt.strftime("%Y-%m-%d")

    def format_inline(self, source: SourceMetadata) -> str:
        """Format as inline citation: (GDELT Project, 2026-01-08).

        Args:
            source: The source metadata to format.

        Returns:
            Inline citation string in parentheses.
        """
        display_name = self._get_display_name(source.source_name)
        date_str = self._format_date(source.retrieved_at)
        return f"({display_name}, {date_str})"

    def format_footnote(self, source: SourceMetadata, note_number: int) -> str:
        """Format as footnote with number, source, and URL.

        Args:
            source: The source metadata to format.
            note_number: The footnote number (e.g., 1, 2, 3).

        Returns:
            Footnote citation string with number prefix.
        """
        display_name = self._get_display_name(source.source_name)
        timestamp = self._format_timestamp(source.retrieved_at)

        if source.source_url:
            return f"[{note_number}] {display_name}. Retrieved {timestamp} from {source.source_url}"
        else:
            return f"[{note_number}] {display_name}. Retrieved {timestamp}."

    def format_url_with_timestamp(self, source: SourceMetadata) -> str:
        """Format URL with retrieval timestamp.

        Args:
            source: The source metadata to format.

        Returns:
            URL with timestamp annotation, or just timestamp if no URL.
        """
        timestamp = self._format_timestamp(source.retrieved_at)

        if source.source_url:
            return f"{source.source_url} (retrieved {timestamp})"
        else:
            return f"(retrieved {timestamp})"

    def format_bibliography_entry(self, source: SourceMetadata) -> str:
        """Format a single bibliography entry.

        Args:
            source: The source metadata to format.

        Returns:
            Multi-line bibliography entry string.
        """
        display_name = self._get_display_name(source.source_name)
        title = self._get_source_title(source.source_name)
        timestamp = self._format_timestamp(source.retrieved_at)
        freshness = get_data_freshness(source.retrieved_at)
        freshness_label = get_freshness_label(freshness)

        lines = [f'{display_name}. "{title}."']

        if source.source_url:
            lines.append(f"  Retrieved {timestamp} from {source.source_url}")
        else:
            lines.append(f"  Retrieved {timestamp}.")

        lines.append(f"  Data freshness: {freshness_label}")

        return "\n".join(lines)

    def format_bibliography(self, sources: list[SourceMetadata]) -> str:
        """Format as bibliography with all sources.

        Args:
            sources: List of source metadata to format.

        Returns:
            Complete bibliography with header and disclaimer.
        """
        if not sources:
            return "Sources\n" + "=" * 7 + "\n\nNo sources available."

        lines = ["Sources", "=" * 7, ""]

        for source in sources:
            entry = self.format_bibliography_entry(source)
            lines.append(entry)
            lines.append("")  # Blank line between entries

        lines.append(POINT_IN_TIME_DISCLAIMER)

        return "\n".join(lines)

    def format_multi_source_attribution(
        self,
        sources: list[SourceContribution],
        include_corroboration: bool = True,
    ) -> str:
        """Format attribution for multiple sources with corroboration notes.

        Args:
            sources: List of SourceContribution objects from the correlator.
            include_corroboration: Whether to include corroboration notes.

        Returns:
            Multi-source attribution string with quality and corroboration.
        """
        if not sources:
            return "Source Attribution\n" + "=" * 18 + "\n\nNo sources available."

        lines = ["Source Attribution", "=" * 18]

        # Group sources by data type/topic
        source_by_type: dict[str, list[SourceContribution]] = {}
        for src in sources:
            # Try to determine data type from the source data
            data_type = self._infer_data_type(src)
            if data_type not in source_by_type:
                source_by_type[data_type] = []
            source_by_type[data_type].append(src)

        # Format each data type with its sources
        for data_type, type_sources in source_by_type.items():
            primary = type_sources[0]
            display_name = self._get_display_name(primary.source_name)
            quality_label = primary.quality_tier.name

            # Check for corroboration
            if include_corroboration and len(type_sources) > 1:
                corroborating = [
                    self._get_display_name(s.source_name) for s in type_sources[1:]
                ]
                corroboration_text = f" [Corroborated by: {', '.join(corroborating)}]"
            else:
                corroboration_text = " [Single source]"

            lines.append(
                f"* {data_type}: {display_name} ({quality_label} quality){corroboration_text}"
            )

        return "\n".join(lines)

    def _infer_data_type(self, source: SourceContribution) -> str:
        """Infer data type from source contribution.

        Args:
            source: The source contribution to analyze.

        Returns:
            Inferred data type string.
        """
        source_name = source.source_name.lower()

        # Map sources to their primary data types
        type_mapping = {
            "gdelt": "Recent events",
            "worldbank": "Economic indicators",
            "wikidata": "Entity information",
            "opensky": "Flight tracking",
            "aisstream": "Maritime tracking",
            "acled": "Conflict data",
            "opensanctions": "Sanctions status",
        }

        return type_mapping.get(source_name, f"{source.source_name} data")

    def format_with_disclaimer(self, source: SourceMetadata) -> str:
        """Format citation with full disclaimer and warnings.

        Args:
            source: The source metadata to format.

        Returns:
            Citation text with all warnings and disclaimers.
        """
        entry = self.format_bibliography_entry(source)
        warnings = self._get_data_age_warnings(source.retrieved_at)

        lines = [entry, ""]

        if warnings:
            lines.append("Warnings:")
            for warning in warnings:
                lines.append(f"  - {warning}")
            lines.append("")

        lines.append(POINT_IN_TIME_DISCLAIMER)

        return "\n".join(lines)

    def get_citation_with_warnings(self, source: SourceMetadata) -> CitationWithWarnings:
        """Get structured citation with warnings.

        Args:
            source: The source metadata to format.

        Returns:
            CitationWithWarnings model with citation, warnings, and disclaimer.
        """
        citation = self.format_bibliography_entry(source)
        warnings = self._get_data_age_warnings(source.retrieved_at)

        return CitationWithWarnings(
            citation=citation,
            warnings=warnings,
            disclaimer=POINT_IN_TIME_DISCLAIMER,
        )

    def _get_data_age_warnings(self, retrieved_at: datetime) -> list[str]:
        """Get warnings based on data age.

        Args:
            retrieved_at: The datetime when data was retrieved.

        Returns:
            List of warning strings, may be empty.
        """
        freshness = get_data_freshness(retrieved_at)
        warnings: list[str] = []

        if freshness == DataFreshness.STALE:
            warnings.append("Data is stale (1-7 days old). Consider refreshing.")
        elif freshness == DataFreshness.ARCHIVED:
            now = datetime.now(timezone.utc)
            if retrieved_at.tzinfo is None:
                retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
            age = now - retrieved_at
            days = age.days
            warnings.append(
                f"Data is archived ({days} days old). May not reflect current state."
            )
            warnings.append("Consider archiving via Wayback Machine for permanent reference.")

        return warnings


__all__ = [
    "DataFreshness",
    "get_data_freshness",
    "get_freshness_label",
    "CitationFormatter",
    "CitationWithWarnings",
    "SOURCE_DISPLAY_NAMES",
    "SOURCE_TITLES",
    "POINT_IN_TIME_DISCLAIMER",
]
