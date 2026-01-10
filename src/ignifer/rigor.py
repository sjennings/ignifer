"""Rigor Mode output formatting for IC-standard analytical products.

Provides enhanced output formatting when rigor mode is enabled,
including ICD 203 confidence language, full source attribution,
bibliographies, and analytical caveats.

Implements:
- FR27: Rigor Mode enablement
- FR28: ICD 203-compliant confidence language
- FR29: Source URLs and retrieval timestamps
- FR30: Academic citation formatting
- FR31: Confidence percentages for entity matching
- FR48: Global rigor mode preference setting
- TR1-TR6: TSUKUYOMI OSINT methodology compliance
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ignifer.citation import (
    CitationFormatter,
    SOURCE_DISPLAY_NAMES,
    get_data_freshness,
    get_freshness_label,
)
from ignifer.confidence import (
    ConfidenceAssessment,
    ConfidenceCalculator,
    confidence_to_language,
)
from ignifer.config import get_settings
from ignifer.models import ConfidenceLevel, QualityTier, SourceMetadata

logger = logging.getLogger(__name__)


def resolve_rigor_mode(rigor_param: bool | None) -> bool:
    """Resolve rigor mode from parameter or global setting.

    Per-query rigor parameter overrides global setting (AC #1, #5).

    Args:
        rigor_param: Per-query rigor mode parameter. If None, uses global setting.

    Returns:
        True if rigor mode should be enabled, False otherwise.
    """
    if rigor_param is not None:
        return rigor_param
    return get_settings().rigor_mode


def format_rigor_header(title: str, timestamp: datetime | None = None) -> str:
    """Format the header section for rigor mode output.

    Args:
        title: The assessment title (e.g., "INTELLIGENCE BRIEFING: Ukraine").
        timestamp: Optional timestamp. If None, uses current UTC time.

    Returns:
        Formatted header string with IC-style borders.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    header = "=" * 59 + "\n"
    header += f"INTELLIGENCE ASSESSMENT: {title.upper()}\n"
    header += "UNCLASSIFIED // OSINT\n"
    header += f"Date: {timestamp_str}\n"
    header += "=" * 59 + "\n"

    return header


def format_confidence_statement(
    level: ConfidenceLevel,
    assessment_text: str,
) -> str:
    """Format ICD 203 confidence statement.

    Uses confidence_to_language() for IC-standard phrasing.

    Args:
        level: The confidence level.
        assessment_text: The text to incorporate into the statement.

    Returns:
        IC-standard confidence statement.
    """
    return confidence_to_language(level, assessment_text)


def format_source_attribution(
    sources: list[SourceMetadata],
    include_quality: bool = True,
) -> str:
    """Format source attribution section for rigor mode.

    Args:
        sources: List of source metadata to attribute.
        include_quality: Whether to include quality tier assessments.

    Returns:
        Formatted source attribution section.
    """
    if not sources:
        return "## Source Attribution\n\nNo sources available.\n"

    lines = ["## Source Attribution", ""]

    for source in sources:
        # Use SOURCE_DISPLAY_NAMES dict directly (public API) instead of private method
        source_key = source.source_name.lower()
        display_name = SOURCE_DISPLAY_NAMES.get(
            source_key, source.source_name.replace("_", " ").title()
        )
        timestamp = source.retrieved_at.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        freshness = get_data_freshness(source.retrieved_at)
        freshness_label = get_freshness_label(freshness)

        # Build attribution line
        line = f"* {display_name} - Retrieved {timestamp}"
        if include_quality and hasattr(source, "quality_tier"):
            # Quality tier is on the source if available
            quality = getattr(source, "quality_tier", QualityTier.MEDIUM)
            line += f" ({quality.name} quality)"
        line += f"\n  Data freshness: {freshness_label}"

        lines.append(line)

    return "\n".join(lines) + "\n"


def format_analytical_caveats(
    caveats: list[str] | None = None,
    source_names: list[str] | None = None,
) -> str:
    """Format analytical caveats section.

    Generates standard caveats based on source types and adds custom caveats.

    Args:
        caveats: Custom caveats to include.
        source_names: Source names to generate standard caveats for.

    Returns:
        Formatted caveats section.
    """
    all_caveats: list[str] = []

    # Standard caveats by source type
    source_caveats = {
        "gdelt": "GDELT coverage may be incomplete for some languages/regions.",
        "worldbank": "World Bank data reflects latest available year, which may be 1-2 years old.",
        "acled": "ACLED data reflects reported incidents; unreported events may occur.",
        "opensanctions": "Sanctions status reflects point-in-time; lists are updated frequently.",
        "opensky": "ADS-B coverage is not global; some flights may not be visible.",
        "aisstream": "AIS coverage varies; some vessels may disable transponders.",
        "wikidata": "Wikidata is community-maintained; verify critical facts.",
    }

    if source_names:
        for name in source_names:
            name_lower = name.lower()
            if name_lower in source_caveats:
                all_caveats.append(source_caveats[name_lower])

    # Add custom caveats
    if caveats:
        all_caveats.extend(caveats)

    # Standard caveat for all assessments
    all_caveats.append("Data reflects point-in-time snapshot and may change rapidly.")

    lines = ["## Analytical Caveats", ""]
    for caveat in all_caveats:
        lines.append(f"* {caveat}")

    return "\n".join(lines) + "\n"


def format_bibliography(
    sources: list[SourceMetadata],
) -> str:
    """Format complete bibliography section.

    Uses CitationFormatter for academic-style citations.

    Args:
        sources: List of source metadata to include.

    Returns:
        Formatted bibliography section with disclaimer.
    """
    formatter = CitationFormatter()
    return formatter.format_bibliography(sources)


def format_rigor_output(
    title: str,
    content: str,
    sources: list[SourceMetadata],
    confidence: ConfidenceAssessment | None = None,
    caveats: list[str] | None = None,
    include_corroboration: bool = False,
    corroboration_notes: list[str] | None = None,
) -> str:
    """Format complete rigor mode output.

    Combines all rigor mode elements into IC-standard format.

    Args:
        title: The assessment title.
        content: The main content/analysis.
        sources: List of source metadata.
        confidence: Optional confidence assessment.
        caveats: Optional custom caveats.
        include_corroboration: Whether to include corroboration section.
        corroboration_notes: Optional corroboration notes.

    Returns:
        Complete rigor mode formatted output.
    """
    timestamp = datetime.now(timezone.utc)
    source_names = [s.source_name for s in sources]

    # Build output sections
    output = format_rigor_header(title, timestamp)

    # Key Findings / Executive Summary with confidence
    if confidence:
        output += "\n## Key Findings\n\n"
        confidence_statement = format_confidence_statement(
            confidence.level,
            f"the following assessment regarding {title.lower()} is accurate",
        )
        output += confidence_statement + "\n\n"

    # Main content
    output += content

    # Source attribution
    output += "\n\n"
    output += format_source_attribution(sources)

    # Corroboration analysis
    if include_corroboration and corroboration_notes:
        output += "\n## Corroboration Analysis\n\n"
        for note in corroboration_notes:
            output += f"* {note}\n"
        output += "\n"

    # Analytical caveats
    output += "\n"
    output += format_analytical_caveats(caveats, source_names)

    # Bibliography
    output += "\n"
    output += format_bibliography(sources)

    return output


def format_entity_match_confidence(
    confidence_score: float,
    resolution_tier: str,
    wikidata_qid: str | None = None,
    match_factors: list[str] | None = None,
) -> str:
    """Format entity match confidence for rigor mode (FR31).

    Args:
        confidence_score: Match confidence as 0.0-1.0 float.
        resolution_tier: How the entity was resolved (exact, normalized, fuzzy, etc.).
        wikidata_qid: Optional Wikidata Q-ID if matched.
        match_factors: Optional list of factors affecting the confidence.

    Returns:
        Formatted match confidence statement.

    Example:
        "Entity matched with 87% confidence (VERY_LIKELY) based on normalized
         name match via Wikidata Q-ID Q12345"
    """
    # Calculate confidence level
    calculator = ConfidenceCalculator()
    level = calculator.percentage_to_level(confidence_score)
    percentage = int(confidence_score * 100)

    # Build statement
    statement = f"Entity matched with {percentage}% confidence ({level.name})"
    statement += f" based on {resolution_tier} match"

    if wikidata_qid:
        statement += f" via Wikidata {wikidata_qid}"

    if match_factors:
        statement += "\n\nMatch factors:\n"
        for factor in match_factors:
            statement += f"  * {factor}\n"

    return statement


def format_sanctions_match_confidence(
    match_score: float,
    entity_name: str,
    matched_name: str,
    match_type: str = "name",
) -> str:
    """Format sanctions match confidence for rigor mode (FR31).

    Args:
        match_score: Match score as 0.0-1.0 float.
        entity_name: The queried entity name.
        matched_name: The matched entity name from sanctions list.
        match_type: Type of match (name, alias, etc.).

    Returns:
        Formatted sanctions match confidence statement.
    """
    calculator = ConfidenceCalculator()
    level = calculator.percentage_to_level(match_score)
    percentage = int(match_score * 100)

    statement = f"Match confidence: {percentage}% ({level.name})\n"
    statement += f'Query: "{entity_name}"\n'
    statement += f'Matched: "{matched_name}" (via {match_type} comparison)\n'

    if level in (ConfidenceLevel.VERY_LIKELY, ConfidenceLevel.ALMOST_CERTAIN):
        statement += "Assessment: HIGH confidence match - likely the same entity.\n"
    elif level == ConfidenceLevel.LIKELY:
        statement += "Assessment: MODERATE confidence match - probable but verify.\n"
    else:
        statement += "Assessment: LOW confidence match - requires verification.\n"

    return statement


__all__ = [
    "resolve_rigor_mode",
    "format_rigor_header",
    "format_confidence_statement",
    "format_source_attribution",
    "format_analytical_caveats",
    "format_bibliography",
    "format_rigor_output",
    "format_entity_match_confidence",
    "format_sanctions_match_confidence",
]
