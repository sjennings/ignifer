"""Output formatting for OSINT results - TSUKUYOMI/Amaterasu style."""

import logging
from datetime import datetime, timezone
from enum import Enum

from ignifer.models import OSINTResult, QualityTier, ResultStatus

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

    def format(self, result: OSINTResult, time_range: str | None = None) -> str:
        """Format an OSINTResult into a professional intelligence briefing.

        Args:
            result: The OSINT result to format.
            time_range: Optional time range string to display in header.

        Returns:
            Formatted string suitable for display to users.
        """
        if result.status == ResultStatus.SUCCESS:
            return self._format_success(result, time_range)
        elif result.status == ResultStatus.NO_DATA:
            return self._format_no_data(result, time_range)
        elif result.status == ResultStatus.RATE_LIMITED:
            return self._format_rate_limited(result)
        else:
            return self._format_error(result)

    def _format_success(self, result: OSINTResult, time_range: str | None = None) -> str:
        """Format successful result as full intelligence briefing."""
        lines = []
        articles = result.results
        article_count = len(articles)
        query = result.query
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # DIRECTIVE - must be at very start
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

        # Key Findings - select diverse articles across languages
        lines.append("### KEY FINDINGS")
        lines.append("")
        selected_articles = self._select_diverse_articles(articles, max_count=12)
        for article in selected_articles:
            title = article.get("title", "Untitled")
            domain = article.get("domain", "unknown source")
            language = article.get("language", "").capitalize()
            date_str = self._format_article_date(article)
            url = article.get("url", "")

            # Confidence indicator based on domain reputation (simplified)
            conf = self._domain_confidence(domain)

            lang_tag = f" [{language}]" if language and language.lower() != "english" else ""
            lines.append(f"{conf} **{title}**{lang_tag}")
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

        # Source Attribution
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

    def _select_diverse_articles(self, articles: list[dict], max_count: int = 10) -> list[dict]:
        """Select articles ensuring language and source diversity."""
        if len(articles) <= max_count:
            return articles

        selected = []
        seen_domains = set()
        seen_languages = set()

        # First pass: get one article per language (prioritize diversity)
        for article in articles:
            lang = article.get("language", "English").lower()
            domain = article.get("domain", "")

            if lang not in seen_languages and len(selected) < max_count:
                selected.append(article)
                seen_languages.add(lang)
                seen_domains.add(domain)

        # Second pass: fill remaining slots with unique domains
        for article in articles:
            if len(selected) >= max_count:
                break
            domain = article.get("domain", "")
            if domain not in seen_domains:
                selected.append(article)
                seen_domains.add(domain)

        # Third pass: if still need more, add any remaining
        for article in articles:
            if len(selected) >= max_count:
                break
            if article not in selected:
                selected.append(article)

        return selected

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


__all__ = ["OutputMode", "OutputFormatter"]
