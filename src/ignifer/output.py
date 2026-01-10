"""Output formatting for OSINT results - TSUKUYOMI/Amaterasu style."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from ignifer.models import OSINTResult, QualityTier, ResultStatus
from ignifer.source_metadata import (
    ENRICHMENT_GDELT_BASELINE,
    MAX_DOMAINS_FOR_ANALYSIS,
)

if TYPE_CHECKING:
    from ignifer.models import SourceMetadataEntry

logger = logging.getLogger(__name__)

# Visual formatting constants (TSUKUYOMI style)
DIVIDER_PRIMARY = "═" * 55
DIVIDER_SECONDARY = "─" * 55
DIVIDER_SECTION = "▬" * 55

# Confidence indicators
CONF_HIGH = "◉"
CONF_MEDIUM = "◐"
CONF_LOW = "◯"

# IC-standard probabilistic language mapping
CONFIDENCE_LANGUAGE = {
    "almost_certain": "almost certainly (95-99%)",
    "highly_likely": "highly likely (80-94%)",
    "likely": "likely (60-79%)",
    "possible": "possible (40-59%)",
    "unlikely": "unlikely (20-39%)",
    "highly_unlikely": "highly unlikely (5-19%)",
    "remote": "remote possibility (1-4%)",
}

# Source reliability scale (IC standard A-F)
RELIABILITY_SCALE = {
    "A": "Completely reliable",
    "B": "Usually reliable",
    "C": "Fairly reliable",
    "D": "Not usually reliable",
    "E": "Unreliable",
    "F": "Reliability cannot be judged",
}

# Information credibility scale (IC standard 1-6)
CREDIBILITY_SCALE = {
    1: "Confirmed by other sources",
    2: "Probably true",
    3: "Possibly true",
    4: "Doubtful",
    5: "Improbable",
    6: "Truth cannot be judged",
}

# Source ranking scoring weights
SCORE_REGION_MATCH = 3
SCORE_LANGUAGE_MATCH = 2
SCORE_RELIABILITY_A = 2
SCORE_RELIABILITY_B = 1


class OutputMode(Enum):
    """Output verbosity modes."""

    BRIEFING = "briefing"  # Summary only (default)
    RIGOR = "rigor"  # Full attribution + raw data (Phase 4)


class OutputFormatter:
    """Formats OSINTResult into professional intelligence briefings.

    Uses TSUKUYOMI/Amaterasu formatting conventions with IC-standard
    terminology, confidence levels, and structured presentation.
    """

    def __init__(self, mode: OutputMode = OutputMode.BRIEFING) -> None:
        self.mode = mode

    def format(
        self,
        result: OSINTResult,
        time_range: str | None = None,
        source_metadata: dict[str, SourceMetadataEntry] | None = None,
        detected_region: str | None = None,
        query: str | None = None,
    ) -> str:
        """Format an OSINTResult into a professional intelligence briefing.

        Args:
            result: The OSINT result to format.
            time_range: Optional time range string to display in header.
            source_metadata: Pre-fetched metadata map (normalized domain -> entry).
            detected_region: Detected region for source ranking and supplementation.
            query: Original query for WebSearch instruction block.

        Returns:
            Formatted string suitable for display to users.
        """
        if result.status == ResultStatus.SUCCESS:
            return self._format_success(
                result, time_range, source_metadata, detected_region, query
            )
        elif result.status == ResultStatus.NO_DATA:
            return self._format_no_data(result, time_range)
        elif result.status == ResultStatus.RATE_LIMITED:
            return self._format_rate_limited(result)
        else:
            return self._format_error(result)

    def _format_success(
        self,
        result: OSINTResult,
        time_range: str | None = None,
        source_metadata: dict[str, SourceMetadataEntry] | None = None,
        detected_region: str | None = None,
        query_param: str | None = None,
    ) -> str:
        """Format successful result as full intelligence briefing."""
        lines = []
        articles = result.results
        article_count = len(articles)
        query = result.query
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # DIRECTIVE for report
        lines.append("═══════════════════════════════════════════════════════")
        lines.append("PART 2 OF YOUR RESPONSE - INCLUDE THIS ENTIRE REPORT")
        lines.append("(Your Part 1 executive summary should appear above this)")
        lines.append("═══════════════════════════════════════════════════════")
        lines.append("")

        # Header block
        lines.append("```")
        lines.append(DIVIDER_PRIMARY)
        lines.append(f"{'INTELLIGENCE BRIEFING':^55}")
        lines.append(f"{'UNCLASSIFIED // OSINT':^55}")
        lines.append(DIVIDER_PRIMARY)
        lines.append(f"TOPIC: {query.upper()}")
        lines.append(f"DATE:  {timestamp}")
        if time_range:
            lines.append(f"TIME RANGE: {time_range}")
        else:
            lines.append("TIME RANGE: Last 7 days (default)")
        lines.append(DIVIDER_SECONDARY)
        lines.append("```")
        lines.append("")

        # Disclaimer
        lines.append("*OSINT COLLECTION NOTICE: This briefing synthesizes publicly")
        lines.append("available information from 65+ languages via machine translation.")
        lines.append("Source reliability varies. Information may be incomplete or subject")
        lines.append("to manipulation. Request article translation for non-English sources.*")
        lines.append("")

        # Key Assessment (BLUF - Bottom Line Up Front)
        reliability_grade = self._source_reliability_grade(result)
        coverage_assessment = self._assess_coverage_level(article_count)
        confidence_indicator = self._coverage_to_confidence(article_count)

        lines.append("```")
        lines.append(DIVIDER_SECONDARY)
        lines.append(f"{'KEY ASSESSMENT':^55}")
        lines.append(DIVIDER_SECONDARY)
        lines.append("")
        lines.append(f"{confidence_indicator} Current open-source reporting on {query}")
        lines.append(f"  is {coverage_assessment}.")
        lines.append("")
        lines.append(f"  Sources Analyzed: {article_count}")
        lines.append(f"  Source Reliability: {reliability_grade}")
        lines.append(f"  Assessment Confidence: {self._article_count_to_confidence_label(article_count)}")
        lines.append("```")
        lines.append("")

        # Date range context
        date_range = self._extract_date_range(articles)
        if date_range:
            lines.append(f"*Coverage Period: {date_range}*")
            lines.append("")

        # Key Findings - select diverse articles across languages with region priority
        lines.append("### KEY FINDINGS")
        lines.append("")

        # Check for multi-region topic
        if detected_region is None and len(articles) > 0:
            # Count distinct nations
            countries = {
                a.get("sourcecountry") for a in articles if a.get("sourcecountry")
            }
            if len(countries) > 3:
                lines.append(
                    "*Multi-region topic detected — using all sources without region prioritization.*"
                )
                lines.append("")

        selected_articles = self._select_diverse_articles(
            articles,
            max_count=12,
            detected_region=detected_region,
            source_metadata=source_metadata,
        )
        for article in selected_articles:
            title = article.get("title", "Untitled")
            domain = article.get("domain", "unknown source")
            language = article.get("language", "").capitalize()
            source_country = article.get("sourcecountry", "")
            date_str = self._format_article_date(article)
            url = article.get("url", "")

            # Confidence indicator based on source metadata or fallback
            conf = self._get_reliability_indicator(domain, source_metadata)

            lang_tag = (
                f" [{language}]" if language and language.lower() != "english" else ""
            )
            # Add nation tag if different from sourcecountry (indicates foreign coverage)
            nation_tag = ""
            if source_metadata and source_country:
                try:
                    from ignifer.source_metadata import normalize_domain

                    normalized = normalize_domain(domain)
                    entry = source_metadata.get(normalized)
                    if entry and entry.nation and entry.nation != source_country:
                        nation_tag = f" [from {entry.nation}]"
                except Exception:
                    pass

            lines.append(f"{conf} **{title}**{lang_tag}{nation_tag}")
            if date_str:
                lines.append(f"   {domain} — {date_str}")
            else:
                lines.append(f"   {domain}")
            if url:
                lines.append(f"   {url}")
            lines.append("")

        remaining = article_count - len(selected_articles)
        if remaining > 0:
            lines.append(f"*...and {remaining} additional sources in dataset*")
            lines.append("")

        # Source Analysis
        lines.append("### SOURCE ANALYSIS")
        lines.append("")
        source_diversity = self._analyze_source_diversity(articles)
        lines.append("```")
        lines.append(DIVIDER_SECONDARY)
        lines.append(f"{'SOURCE CORRELATION MATRIX':^55}")
        lines.append(DIVIDER_SECONDARY)
        lines.append(f"  Unique Domains:     {source_diversity['unique_domains']}")
        lines.append(f"  Language Coverage:  {source_diversity['languages']}")
        lines.append(f"  Geographic Spread:  {source_diversity['geo_assessment']}")
        lines.append(f"  Temporal Range:     {source_diversity['temporal']}")
        lines.append(DIVIDER_SECONDARY)
        lines.append("```")
        lines.append("")

        # Information Gaps
        lines.append("### INFORMATION GAPS")
        lines.append("")
        gaps = self._identify_info_gaps(articles, query)
        for gap in gaps:
            lines.append(f"► {gap}")
        lines.append("")

        # Recommended Next Steps
        lines.append("### RECOMMENDED ACTIONS")
        lines.append("")
        actions = self._generate_recommended_actions(articles, query, gaps)
        for i, action in enumerate(actions, 1):
            lines.append(f"{i}. {action}")
        lines.append("")

        # Source Attribution (include political orientation if available)
        lines.append("### SOURCE ATTRIBUTION")
        lines.append("")
        for source_attr in result.sources:
            src_timestamp = source_attr.metadata.retrieved_at.strftime("%Y-%m-%d %H:%M UTC")
            grade = self._quality_to_grade(source_attr.quality)
            reliability_desc = RELIABILITY_SCALE.get(grade, "Cannot be judged")
            lines.append(f"**{source_attr.metadata.source_name.upper()}**")
            lines.append(f"  Reliability: {grade} ({reliability_desc})")
            lines.append(f"  Retrieved:   {src_timestamp}")
        lines.append("")

        # Source Quality Intelligence summary
        if source_metadata:
            # Count sources by nation
            nation_counts: dict[str, int] = {}
            for entry in source_metadata.values():
                if entry.nation:
                    nation_counts[entry.nation] = nation_counts.get(entry.nation, 0) + 1

            if nation_counts:
                lines.append("**Source Origin Distribution:**")
                # Show top 5 nations
                sorted_nations = sorted(nation_counts.items(), key=lambda x: -x[1])
                for nation, count in sorted_nations[:5]:
                    lines.append(f"  • {nation}: {count} source{'s' if count > 1 else ''}")
                if len(sorted_nations) > 5:
                    others = sum(c for _, c in sorted_nations[5:])
                    lines.append(f"  • Others: {others} sources")
                lines.append("")

            # Show political orientations if any are set
            orientation_notes = []
            for domain, entry in source_metadata.items():
                if entry.political_orientation:
                    axis_note = f" ({entry.orientation_axis})" if entry.orientation_axis else ""
                    orientation_notes.append(
                        f"  • {domain}: {entry.political_orientation}{axis_note}"
                    )
            if orientation_notes:
                lines.append("**Source Political Orientations:**")
                lines.extend(orientation_notes[:5])  # Limit to top 5
                if len(orientation_notes) > 5:
                    lines.append(f"  *...and {len(orientation_notes) - 5} more*")
                lines.append("")

        # Regional supplementation instruction for Claude (WebSearch)
        if detected_region and query_param:
            lines.append("---")
            lines.append("**REGIONAL SUPPLEMENTATION (for Claude):**")
            lines.append(f"Detected region: {detected_region}. Consider using WebSearch for 2-3 additional")
            lines.append(f'recent articles from {detected_region}-based sources about "{query_param}".')
            lines.append("---")
            lines.append("")

        # Footer
        freshness = self._freshness_indicator(result.sources[0].metadata.retrieved_at) if result.sources else "Unknown"
        lines.append("```")
        lines.append(DIVIDER_PRIMARY)
        lines.append(f"{'CLASSIFICATION: UNCLASSIFIED':^55}")
        lines.append(f"{'HANDLING: OSINT - NO RESTRICTIONS':^55}")
        lines.append(f"Data Freshness: {freshness:^43}")
        lines.append(DIVIDER_PRIMARY)
        lines.append("```")

        return "\n".join(lines)

    def _format_no_data(self, result: OSINTResult, time_range: str | None = None) -> str:
        """Format no-data result with helpful suggestions."""
        query = result.query
        suggestion = result.error or "Try different search terms"

        lines = []
        lines.append("```")
        lines.append(DIVIDER_PRIMARY)
        lines.append(f"{'INTELLIGENCE BRIEFING':^55}")
        lines.append(f"{'NO DATA AVAILABLE':^55}")
        lines.append(DIVIDER_PRIMARY)
        lines.append("```")
        lines.append("")
        lines.append(f"No open-source intelligence found for **{query}**.")
        lines.append("")
        lines.append("### RECOMMENDED ACTIONS")
        lines.append("")
        lines.append(f"1. {suggestion}")
        lines.append("2. Try more specific or alternative keywords")
        lines.append("3. Verify spelling of names or locations")
        lines.append("4. Use English terms for broader coverage")
        if time_range:
            lines.append("5. Try a broader time range like 'last 30 days'")
        else:
            lines.append("5. Expand temporal search range if available")

        return "\n".join(lines)

    def _format_rate_limited(self, result: OSINTResult) -> str:
        """Format rate-limited result."""
        lines = []
        lines.append("```")
        lines.append(DIVIDER_PRIMARY)
        lines.append(f"{'COLLECTION INTERRUPTED':^55}")
        lines.append(f"{'SOURCE RATE LIMITED':^55}")
        lines.append(DIVIDER_PRIMARY)
        lines.append("```")
        lines.append("")
        lines.append("Data source temporarily unavailable due to rate limiting.")
        lines.append("")
        lines.append("### RECOMMENDED ACTIONS")
        lines.append("")
        lines.append("1. Wait 2-5 minutes before retrying")
        lines.append("2. Use a more specific query to reduce API load")
        lines.append("3. Consider alternative collection times")

        return "\n".join(lines)

    def _format_error(self, result: OSINTResult) -> str:
        """Format generic error result."""
        error_msg = result.error or "An unknown error occurred"
        lines = []
        lines.append("```")
        lines.append(DIVIDER_PRIMARY)
        lines.append(f"{'COLLECTION ERROR':^55}")
        lines.append(DIVIDER_PRIMARY)
        lines.append("```")
        lines.append("")
        lines.append(f"**Error:** {error_msg}")
        lines.append("")
        lines.append("### RECOMMENDED ACTIONS")
        lines.append("")
        lines.append("1. Retry the request in a few moments")
        lines.append("2. Verify query formatting")
        lines.append("3. Check source availability status")

        return "\n".join(lines)

    # Helper methods

    def _source_reliability_grade(self, result: OSINTResult) -> str:
        """Generate IC-style reliability grade for sources."""
        if not result.sources:
            return "F - Cannot be judged"

        tier = result.sources[0].quality
        grade_map = {
            QualityTier.HIGH: "B - Usually reliable",
            QualityTier.MEDIUM: "C - Fairly reliable",
            QualityTier.LOW: "D - Not usually reliable",
        }
        return grade_map.get(tier, "F - Cannot be judged")

    def _quality_to_grade(self, tier: QualityTier | None) -> str:
        """Convert QualityTier to IC-style letter grade."""
        if tier is None:
            return "F"
        grade_map = {
            QualityTier.HIGH: "B",
            QualityTier.MEDIUM: "C",
            QualityTier.LOW: "D",
        }
        return grade_map.get(tier, "F")

    def _assess_coverage_level(self, article_count: int) -> str:
        """Assess coverage level based on article count with IC language."""
        if article_count >= 50:
            return "EXTENSIVE — high media attention detected"
        elif article_count >= 25:
            return "SUBSTANTIAL — active multi-source coverage"
        elif article_count >= 10:
            return "MODERATE — several outlets reporting"
        elif article_count >= 5:
            return "LIMITED — sparse but present coverage"
        else:
            return "MINIMAL — few sources currently reporting"

    def _coverage_to_confidence(self, article_count: int) -> str:
        """Return confidence indicator based on coverage."""
        if article_count >= 25:
            return CONF_HIGH
        elif article_count >= 10:
            return CONF_MEDIUM
        else:
            return CONF_LOW

    def _article_count_to_confidence_label(self, article_count: int) -> str:
        """Convert article count to confidence label."""
        if article_count >= 25:
            return "HIGH — Multiple independent sources"
        elif article_count >= 10:
            return "MEDIUM — Several corroborating sources"
        else:
            return "LOW — Limited source corroboration"

    def _domain_confidence(self, domain: str) -> str:
        """Estimate confidence based on domain (simplified heuristic)."""
        high_reliability = ["reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
                          "theguardian.com", "nytimes.com", "washingtonpost.com",
                          "ft.com", "economist.com", "wsj.com"]
        medium_reliability = ["cnn.com", "foxnews.com", "nbcnews.com", "abcnews.go.com",
                            "politico.com", "axios.com", "bloomberg.com"]

        domain_lower = domain.lower()
        if any(d in domain_lower for d in high_reliability):
            return CONF_HIGH
        elif any(d in domain_lower for d in medium_reliability):
            return CONF_MEDIUM
        else:
            return CONF_LOW

    def _extract_date_range(self, articles: list[dict]) -> str | None:
        """Extract date range from articles if date information available."""
        dates = []
        for article in articles:
            date_str = article.get("seendate")
            if date_str:
                try:
                    dt = datetime.strptime(date_str[:8], "%Y%m%d")
                    dates.append(dt)
                except (ValueError, TypeError):
                    continue

        if not dates:
            return None

        min_date = min(dates)
        max_date = max(dates)

        if min_date.date() == max_date.date():
            return min_date.strftime("%B %d, %Y")
        else:
            return f"{min_date.strftime('%B %d')} — {max_date.strftime('%B %d, %Y')}"

    def _format_article_date(self, article: dict) -> str | None:
        """Format article date for display."""
        date_str = article.get("seendate")
        if not date_str:
            return None
        try:
            dt = datetime.strptime(date_str[:8], "%Y%m%d")
            return dt.strftime("%d %b %Y")
        except (ValueError, TypeError):
            return None

    def _analyze_source_diversity(self, articles: list[dict]) -> dict:
        """Analyze diversity of sources for correlation matrix."""
        domains = {a.get("domain", "") for a in articles if a.get("domain")}
        languages = {a.get("language", "").lower() for a in articles if a.get("language")}

        # Geographic assessment based on domain TLDs and known sources
        geo_indicators = set()
        for domain in domains:
            if ".uk" in domain or "bbc" in domain or "guardian" in domain:
                geo_indicators.add("UK")
            elif ".de" in domain:
                geo_indicators.add("Germany")
            elif ".fr" in domain:
                geo_indicators.add("France")
            elif ".au" in domain:
                geo_indicators.add("Australia")
            elif ".jp" in domain:
                geo_indicators.add("Japan")
            elif ".cn" in domain:
                geo_indicators.add("China")
            elif ".in" in domain:
                geo_indicators.add("India")
            else:
                geo_indicators.add("US/Intl")

        # Temporal assessment
        dates = []
        for article in articles:
            date_str = article.get("seendate")
            if date_str:
                try:
                    dt = datetime.strptime(date_str[:8], "%Y%m%d")
                    dates.append(dt)
                except (ValueError, TypeError):
                    continue

        if dates:
            date_range = (max(dates) - min(dates)).days
            if date_range == 0:
                temporal = "Single day"
            elif date_range <= 7:
                temporal = f"{date_range + 1} days"
            else:
                temporal = f"{date_range + 1} days ({date_range // 7} weeks)"
        else:
            temporal = "Unknown"

        return {
            "unique_domains": len(domains),
            "languages": ", ".join(sorted(languages)) if languages else "English (assumed)",
            "geo_assessment": ", ".join(sorted(geo_indicators)[:4]) if geo_indicators else "Unknown",
            "temporal": temporal,
        }

    def _select_diverse_articles(
        self,
        articles: list[dict],
        max_count: int = 10,
        detected_region: str | None = None,
        source_metadata: dict[str, SourceMetadataEntry] | None = None,
    ) -> list[dict]:
        """Select articles ensuring language and source diversity with region priority.

        Prioritizes:
        1. Sources from detected region (nation match)
        2. Sources in regional language
        3. High reliability (A, B grades)
        4. Diversity as tiebreaker
        """
        if len(articles) <= max_count:
            return articles

        # Score and sort articles
        scored_articles: list[tuple[int, int, dict]] = []  # (score, -index, article)
        for idx, article in enumerate(articles):
            score = self._calculate_article_score(
                article, detected_region, source_metadata
            )
            scored_articles.append((score, -idx, article))  # -idx for stable sort

        # Sort by score descending, then by original order
        scored_articles.sort(key=lambda x: (x[0], x[1]), reverse=True)

        # Select top scored articles while maintaining diversity
        selected = []
        seen_domains: set[str] = set()
        seen_languages: set[str] = set()

        # First pass: top scored articles with domain diversity
        for score, _, article in scored_articles:
            if len(selected) >= max_count:
                break
            domain = article.get("domain", "")
            lang = article.get("language", "English").lower()

            if domain not in seen_domains:
                selected.append(article)
                seen_domains.add(domain)
                seen_languages.add(lang)

        # Second pass: fill with language diversity if slots remain
        for score, _, article in scored_articles:
            if len(selected) >= max_count:
                break
            lang = article.get("language", "English").lower()
            if article not in selected and lang not in seen_languages:
                selected.append(article)
                seen_languages.add(lang)

        # Third pass: fill remaining slots
        for score, _, article in scored_articles:
            if len(selected) >= max_count:
                break
            if article not in selected:
                selected.append(article)

        return selected

    def _calculate_article_score(
        self,
        article: dict,
        detected_region: str | None,
        source_metadata: dict[str, SourceMetadataEntry] | None,
    ) -> int:
        """Calculate priority score for an article.

        Higher scores indicate higher priority for selection.
        """
        score = 0
        domain = article.get("domain", "")
        source_country = article.get("sourcecountry", "")
        language = article.get("language", "").lower()

        if not source_metadata or not detected_region:
            return score

        # Try to get metadata for this domain
        try:
            from ignifer.source_metadata import normalize_domain, normalize_nation

            normalized = normalize_domain(domain)
            entry = source_metadata.get(normalized)
        except Exception:
            entry = None

        # Region match scoring
        if detected_region:
            normalized_region = detected_region.lower()
            normalized_country = (
                normalize_nation(source_country).lower() if source_country else ""
            )
            if entry and entry.nation:
                normalized_entry_nation = normalize_nation(entry.nation).lower()
                if normalized_entry_nation == normalized_region:
                    score += SCORE_REGION_MATCH

            # Also check article's sourcecountry
            if normalized_country == normalized_region:
                score += SCORE_REGION_MATCH

            # Language match for region
            region_languages = {
                "taiwan": ["chinese", "mandarin"],
                "china": ["chinese", "mandarin"],
                "japan": ["japanese"],
                "south korea": ["korean"],
                "russia": ["russian"],
                "ukraine": ["ukrainian", "russian"],
                "france": ["french"],
                "germany": ["german"],
                "brazil": ["portuguese"],
                "mexico": ["spanish"],
            }
            region_langs = region_languages.get(normalized_region, [])
            if language in region_langs:
                score += SCORE_LANGUAGE_MATCH

        # Reliability scoring
        if entry:
            if entry.reliability == "A":
                score += SCORE_RELIABILITY_A
            elif entry.reliability == "B":
                score += SCORE_RELIABILITY_B

        return score

    def _get_reliability_indicator(
        self,
        domain: str,
        source_metadata: dict[str, SourceMetadataEntry] | None,
    ) -> str:
        """Get reliability indicator with fallback.

        Maps reliability grade (A-F) to visual indicator:
        - A, B → ◉ (high)
        - C, D → ◐ (medium)
        - E, F → ◯ (low)
        """
        if source_metadata is None:
            return CONF_MEDIUM  # Default: medium confidence (old behavior)

        try:
            from ignifer.source_metadata import normalize_domain

            normalized = normalize_domain(domain)
            entry = source_metadata.get(normalized)
        except Exception:
            return CONF_MEDIUM

        if entry is None:
            return CONF_MEDIUM  # Fallback: treat as medium confidence

        grade = entry.reliability
        if grade in ("A", "B"):
            return CONF_HIGH
        elif grade in ("C", "D"):
            return CONF_MEDIUM
        else:
            return CONF_LOW

    def _identify_info_gaps(self, articles: list[dict], query: str) -> list[str]:
        """Identify potential information gaps based on article analysis."""
        gaps = []

        domains = {a.get("domain", "") for a in articles}
        languages = {a.get("language", "").lower() for a in articles if a.get("language")}

        if len(domains) < 5:
            gaps.append("Limited source diversity — assess for single-narrative bias")

        # GDELT searches 65 languages; flag if results are monolingual
        if languages and len(languages) == 1:
            lang = list(languages)[0]
            gaps.append(f"Single-language results ({lang}) — request translation of specific articles if needed")

        if len(articles) < 10:
            gaps.append("Low source volume — confidence limited by sparse reporting")

        # Check for recency
        dates = []
        for article in articles:
            date_str = article.get("seendate")
            if date_str:
                try:
                    dt = datetime.strptime(date_str[:8], "%Y%m%d")
                    dates.append(dt)
                except (ValueError, TypeError):
                    continue

        if dates:
            newest = max(dates)
            age = (datetime.now() - newest).days
            if age > 3:
                gaps.append(f"Most recent coverage is {age} days old — situation may have evolved")

        if not gaps:
            gaps.append("No critical gaps identified in available coverage")

        return gaps

    def _generate_recommended_actions(self, articles: list[dict], query: str, gaps: list[str]) -> list[str]:
        """Generate recommended next steps based on analysis."""
        actions = []

        # Based on gaps
        if any("diversity" in g.lower() for g in gaps):
            actions.append("Cross-reference with additional OSINT sources (social media, local news)")

        if any("language" in g.lower() for g in gaps):
            actions.append("Request translation of non-English article titles/content for deeper analysis")

        if any("volume" in g.lower() or "sparse" in g.lower() for g in gaps):
            actions.append("Expand search with related keywords or broader topic scope")

        if any("days old" in g.lower() for g in gaps):
            actions.append("Monitor for breaking developments — set collection alert")

        # Standard recommendations
        if len(articles) >= 10:
            actions.append("Identify key actors and entities for deeper profiling")

        actions.append("Verify critical claims through independent source triangulation")

        if len(actions) > 5:
            actions = actions[:5]  # Cap at 5 recommendations

        return actions

    def _freshness_indicator(self, retrieved_at: datetime) -> str:
        """Generate freshness indicator based on retrieval time."""
        now = datetime.now(timezone.utc)
        delta = now - retrieved_at

        if delta.total_seconds() < 300:
            return "LIVE — Just retrieved"
        elif delta.total_seconds() < 3600:
            minutes = int(delta.total_seconds() / 60)
            return f"RECENT — {minutes} minutes ago"
        elif delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"TODAY — {hours} hours ago"
        else:
            days = int(delta.total_seconds() / 86400)
            return f"CACHED — {days} days ago"

    def _get_domains_needing_analysis(
        self,
        articles: list[dict],
        source_metadata: dict[str, SourceMetadataEntry] | None,
    ) -> list[tuple[str, str | None, str | None, int]]:
        """Get domains that need reliability/orientation analysis.

        Filters to domains with enrichment_source == "auto:gdelt_baseline"
        (i.e., only auto-enriched from GDELT, not yet analyzed by LLM or user).

        Args:
            articles: List of article dicts from GDELT
            source_metadata: Pre-fetched metadata map

        Returns:
            List of (domain, nation, language, count) tuples sorted by frequency
        """
        if source_metadata is None:
            return []

        # Count articles per domain
        domain_counts: dict[str, int] = {}
        for article in articles:
            domain = article.get("domain", "")
            if domain:
                try:
                    from ignifer.source_metadata import normalize_domain

                    normalized = normalize_domain(domain)
                    domain_counts[normalized] = domain_counts.get(normalized, 0) + 1
                except Exception:
                    pass

        # Filter to domains needing analysis
        domains_needing_analysis = []
        for domain, count in domain_counts.items():
            entry = source_metadata.get(domain)
            if entry and entry.enrichment_source == ENRICHMENT_GDELT_BASELINE:
                domains_needing_analysis.append(
                    (domain, entry.nation, entry.language, count)
                )

        # Sort by frequency (most articles first)
        domains_needing_analysis.sort(key=lambda x: -x[3])

        # Limit to MAX_DOMAINS_FOR_ANALYSIS
        return domains_needing_analysis[:MAX_DOMAINS_FOR_ANALYSIS]

    def _format_source_analysis_instructions(
        self,
        articles: list[dict],
        source_metadata: dict[str, SourceMetadataEntry] | None,
        detected_region: str | None,
    ) -> list[str]:
        """Generate instructions for Claude to analyze source reliability.

        Creates an instruction block telling Claude to use WebSearch to research
        each unanalyzed source's reliability and political orientation, then
        save findings using set_source_reliability and set_source_orientation.

        Args:
            articles: List of article dicts from GDELT
            source_metadata: Pre-fetched metadata map
            detected_region: Detected region for orientation axis hints

        Returns:
            List of formatted instruction lines (empty if no analysis needed)
        """
        domains_to_analyze = self._get_domains_needing_analysis(articles, source_metadata)

        if not domains_to_analyze:
            return []

        lines = []
        num_domains = len(domains_to_analyze)

        lines.append("")
        lines.append("╔═══════════════════════════════════════════════════════╗")
        lines.append("║     ⚠️  MANDATORY: SOURCE QUALITY ANALYSIS REQUIRED    ║")
        lines.append("╚═══════════════════════════════════════════════════════╝")
        lines.append("")
        lines.append(f"STOP! Before providing your response, you MUST analyze {num_domains} sources.")
        lines.append("This is NOT optional. Complete ALL steps below FIRST.")
        lines.append("")
        lines.append("ACTION REQUIRED - Do this NOW:")
        lines.append("")

        # Limit to top 5 for immediate action, show count of others
        top_domains = domains_to_analyze[:5]
        for i, (domain, nation, language, article_count) in enumerate(top_domains, 1):
            nation_str = nation if nation else "Unknown"
            lines.append(f"  {i}. WebSearch: \"{domain} media bias reliability\"")
            lines.append(f"     Then call: set_source_reliability(\"{domain}\", \"<A-F>\")")
            lines.append("")

        if num_domains > 5:
            lines.append(f"  ... plus {num_domains - 5} more sources to analyze after these.")
            lines.append("")

        lines.append("RELIABILITY GRADES:")
        lines.append("  A=Wire services  B=Major outlets  C=Regional media")
        lines.append("  D=Known bias  E=Unreliable  F=Cannot judge")
        lines.append("")

        # Add region-specific axis hint
        if detected_region:
            region_axes = {
                "Taiwan": "china-independence",
                "China": "china-independence",
                "Hong Kong": "china-independence",
                "Ukraine": "russia-west",
                "Russia": "russia-west",
            }
            axis_hint = region_axes.get(detected_region)
            if axis_hint:
                lines.append(f"For {detected_region} sources, also set orientation axis: {axis_hint}")
                lines.append("  set_source_orientation(\"domain\", \"<orientation>\", \"{}\")".format(axis_hint))
                lines.append("")

        lines.append("After completing source analysis, provide the intelligence report below.")
        lines.append("─" * 55)
        lines.append("")

        return lines


__all__ = ["OutputMode", "OutputFormatter"]
