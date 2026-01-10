"""FastMCP server for Ignifer OSINT tools."""

import asyncio
import atexit
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import trafilatura
from fastmcp import FastMCP

from ignifer.adapters import (
    AdapterAuthError,
    AdapterError,
    AdapterTimeoutError,
    AISStreamAdapter,
    GDELTAdapter,
    OpenSkyAdapter,
    OSINTAdapter,
    WikidataAdapter,
    WorldBankAdapter,
)
from ignifer.aggregation import EntityResolver
from ignifer.aggregation.correlator import (
    AggregatedResult,
    Conflict,
    Correlator,
    CorroborationStatus,
    Finding,
)
from ignifer.aggregation.relevance import (
    RelevanceScore,
    SourceRelevanceEngine,
)
from ignifer.cache import CacheManager
from ignifer.confidence import (
    ConfidenceCalculator,
    confidence_to_language,
)
from ignifer.config import configure_logging, get_settings
from ignifer.models import QualityTier, QueryParams, ResultStatus, SourceMetadata
from ignifer.output import OutputFormatter
from ignifer.source_metadata import (
    InvalidReliabilityGradeError,
    SourceMetadataManager,
    SourceMetadataNotFoundError,
    detect_region,
    normalize_domain,
)
from ignifer.rigor import (
    format_analytical_caveats,
    format_bibliography,
    format_entity_match_confidence,
    format_source_attribution,
    resolve_rigor_mode,
)
from ignifer.timeparse import parse_time_range

logger = logging.getLogger(__name__)

# Article extraction settings
MAX_AUTO_EXTRACTS = 4  # Number of articles to auto-extract
EXTRACT_TIMEOUT = 12.0  # Timeout per article extraction

# Initialize FastMCP server
mcp = FastMCP("ignifer")

# Global instances (initialized on first use)
_cache: CacheManager | None = None
_adapter: GDELTAdapter | None = None
_worldbank: WorldBankAdapter | None = None
_wikidata: WikidataAdapter | None = None
_opensky: OpenSkyAdapter | None = None
_aisstream: AISStreamAdapter | None = None
_entity_resolver: EntityResolver | None = None
_formatter: OutputFormatter | None = None
_relevance_engine: SourceRelevanceEngine | None = None
_correlator: Correlator | None = None
_source_metadata: SourceMetadataManager | None = None


def _get_cache() -> CacheManager:
    global _cache
    if _cache is None:
        _cache = CacheManager()
    return _cache


def _get_adapter() -> GDELTAdapter:
    global _adapter
    if _adapter is None:
        _adapter = GDELTAdapter(cache=_get_cache())
    return _adapter


def _get_worldbank() -> WorldBankAdapter:
    global _worldbank
    if _worldbank is None:
        _worldbank = WorldBankAdapter(cache=_get_cache())
    return _worldbank


def _get_wikidata() -> WikidataAdapter:
    global _wikidata
    if _wikidata is None:
        _wikidata = WikidataAdapter(cache=_get_cache())
    return _wikidata


def _get_opensky() -> OpenSkyAdapter:
    global _opensky
    if _opensky is None:
        _opensky = OpenSkyAdapter(cache=_get_cache())
    return _opensky


def _get_aisstream() -> AISStreamAdapter:
    global _aisstream
    if _aisstream is None:
        _aisstream = AISStreamAdapter(cache=_get_cache())
    return _aisstream


def _get_entity_resolver() -> EntityResolver:
    global _entity_resolver
    if _entity_resolver is None:
        _entity_resolver = EntityResolver(wikidata_adapter=_get_wikidata())
    return _entity_resolver


def _get_formatter() -> OutputFormatter:
    global _formatter
    if _formatter is None:
        _formatter = OutputFormatter()
    return _formatter


def _get_relevance_engine() -> SourceRelevanceEngine:
    global _relevance_engine
    if _relevance_engine is None:
        _relevance_engine = SourceRelevanceEngine(get_settings())
    return _relevance_engine


def _get_correlator() -> Correlator:
    global _correlator
    if _correlator is None:
        # Build adapters dict from existing getters
        # Explicit type annotation for mypy compatibility
        adapters: dict[str, OSINTAdapter] = {
            "gdelt": _get_adapter(),
            "worldbank": _get_worldbank(),
            "wikidata": _get_wikidata(),
            "opensky": _get_opensky(),
            "aisstream": _get_aisstream(),
        }
        _correlator = Correlator(
            adapters=adapters,
            relevance_engine=_get_relevance_engine(),
            settings=get_settings(),
        )
    return _correlator


def _get_source_metadata() -> SourceMetadataManager:
    global _source_metadata
    if _source_metadata is None:
        _source_metadata = SourceMetadataManager()
    return _source_metadata


async def _cleanup_resources() -> None:
    """Close all open resources (adapters, cache connections)."""
    global _adapter, _worldbank, _wikidata, _opensky, _aisstream
    global _entity_resolver, _cache, _source_metadata
    global _relevance_engine, _correlator

    # Clear aggregation components first (they reference adapters)
    _correlator = None
    _relevance_engine = None
    _entity_resolver = None

    # Close adapters first, then cache (adapters may use cache)
    adapters = [
        (_adapter, "_adapter"),
        (_worldbank, "_worldbank"),
        (_wikidata, "_wikidata"),
        (_opensky, "_opensky"),
        (_aisstream, "_aisstream"),
    ]
    for adapter, name in adapters:
        if adapter is not None:
            await adapter.close()
            globals()[name] = None

    # Close source metadata manager
    if _source_metadata is not None:
        await _source_metadata.close()
        _source_metadata = None

    if _cache is not None:
        await _cache.close()
        _cache = None

    logger.debug("All resources cleaned up")


def _atexit_cleanup() -> None:
    """Synchronous atexit handler that runs async cleanup."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule cleanup in running loop
            loop.create_task(_cleanup_resources())
        else:
            # Run cleanup in new loop
            asyncio.run(_cleanup_resources())
    except Exception as e:
        # Don't let cleanup errors prevent shutdown
        logger.debug(f"Cleanup error (non-fatal): {e}")


# Register cleanup on process exit
atexit.register(_atexit_cleanup)


async def _extract_single_article(url: str, language: str = "") -> dict[str, str | None]:
    """Extract a single article's content.

    Returns dict with url, language, content, and error fields.
    """
    result: dict[str, str | None] = {
        "url": url,
        "language": language,
        "content": None,
        "error": None,
    }

    try:
        async with httpx.AsyncClient(
            timeout=EXTRACT_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; IgniferBot/1.0; OSINT research)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,*;q=0.5",
            },
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            favor_precision=True,
        )

        if extracted:
            # Truncate if very long
            if len(extracted) > 4000:
                extracted = extracted[:4000] + "\n\n[Content truncated...]"
            result["content"] = extracted
        else:
            result["error"] = "Content could not be extracted"

    except httpx.TimeoutException:
        result["error"] = "Timeout"
    except httpx.HTTPStatusError as e:
        result["error"] = f"HTTP {e.response.status_code}"
    except Exception as e:
        result["error"] = str(e)[:50]

    return result


async def _auto_extract_articles(
    articles: list[dict[str, Any]], max_count: int = MAX_AUTO_EXTRACTS
) -> list[dict[str, str | None]]:
    """Extract content from top articles in parallel.

    Prioritizes articles from different languages for diversity.
    Returns list of extraction results.
    """
    # Select diverse articles for extraction
    selected: list[dict[str, str]] = []
    seen_languages: set[str] = set()
    seen_domains: set[str] = set()

    # First: one article per unique language
    for article in articles:
        if len(selected) >= max_count:
            break
        lang = article.get("language", "english").lower()
        domain = article.get("domain", "")
        url = article.get("url")
        if url and lang not in seen_languages:
            selected.append(
                {"url": url, "language": lang, "title": article.get("title", ""), "domain": domain}
            )
            seen_languages.add(lang)
            seen_domains.add(domain)

    # Second: fill remaining with unique domains
    for article in articles:
        if len(selected) >= max_count:
            break
        domain = article.get("domain", "")
        url = article.get("url")
        if url and domain not in seen_domains:
            lang = article.get("language", "english").lower()
            selected.append(
                {"url": url, "language": lang, "title": article.get("title", ""), "domain": domain}
            )
            seen_domains.add(domain)

    if not selected:
        return []

    # Extract all in parallel
    tasks = [_extract_single_article(s["url"], s.get("language", "")) for s in selected]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Combine metadata with extraction results
    extracted: list[dict[str, str | None]] = []
    for i, res in enumerate(results):
        if isinstance(res, BaseException):
            extracted.append(
                {
                    "url": selected[i]["url"],
                    "title": selected[i]["title"],
                    "language": selected[i].get("language", ""),
                    "domain": selected[i]["domain"],
                    "content": None,
                    "error": str(res)[:50],
                }
            )
        else:
            # res is dict[str, str | None] at this point
            res_dict: dict[str, str | None] = res
            extracted.append(
                {
                    "url": selected[i]["url"],
                    "title": selected[i]["title"],
                    "language": selected[i].get("language", ""),
                    "domain": selected[i]["domain"],
                    "content": res_dict.get("content"),
                    "error": res_dict.get("error"),
                }
            )

    return extracted


@mcp.tool()
async def briefing(
    topic: str,
    time_range: str | None = None,
    rigor: bool | None = None,
) -> str:
    """OSINT intelligence briefing from 65+ language sources.

    YOUR RESPONSE MUST HAVE TWO PARTS:

    PART 1 - YOUR EXECUTIVE SUMMARY (2-3 paragraphs):
    Synthesize key findings, main actors, and implications.

    PART 2 - THE COMPLETE REPORT (MANDATORY - DO NOT OMIT):
    Include the ENTIRE output below in your response:
    - The formatted briefing (INTELLIGENCE BRIEFING header through RECOMMENDED ACTIONS)
    - The PRIMARY SOURCE EXTRACTS section with full article text

    The article extracts contain the actual evidence. DO NOT SKIP THEM.
    Translate [Language] tagged content inline. Do not use web search.

    Args:
        topic: Topic to research (2-4 words)
        time_range: Optional time filter. Supported formats:
            - "last 24 hours", "last 48 hours"
            - "last 7 days", "last 30 days"
            - "this week", "last week"
            - "2026-01-01 to 2026-01-08" (ISO date range)
            If not specified, defaults to last 7 days.
        rigor: Enable rigor mode for IC-standard output with full source
            attribution, confidence levels, and bibliography. If not specified,
            uses global IGNIFER_RIGOR_MODE setting.

    Returns:
        Full briefing + article extracts. Include ALL of it in Part 2.
        In rigor mode, includes ICD 203 confidence language and bibliography.
    """
    effective_rigor = resolve_rigor_mode(rigor)
    logger.info(
        f"Briefing requested: topic={topic}, time_range={time_range}, rigor={effective_rigor}"
    )

    # Validate time_range if provided
    if time_range:
        time_result = parse_time_range(time_range)
        if not time_result.is_valid:
            logger.warning(f"Invalid time range: {time_range} - {time_result.error}")
            return (
                f"## Invalid Time Range\n\n"
                f"Could not parse time range: **{time_range}**\n\n"
                f"**Supported formats:**\n"
                f'- "last 24 hours", "last 48 hours"\n'
                f'- "last 7 days", "last 30 days"\n'
                f'- "this week", "last week"\n'
                f'- "2026-01-01 to 2026-01-08" (ISO date range)\n\n'
                f"**Examples:**\n"
                f'- briefing("Syria", time_range="last 48 hours")\n'
                f'- briefing("Ukraine", time_range="last 7 days")'
            )

    try:
        # Query the adapter
        adapter = _get_adapter()
        params = QueryParams(query=topic, time_range=time_range)
        result = await adapter.query(params)

        # Pre-fetch source metadata for all domains
        from ignifer.models import SourceMetadataEntry

        source_metadata_map: dict[str, SourceMetadataEntry] = {}
        detected_region: str | None = None

        if result.results:
            # Detect region from query and results
            detected_region = detect_region(topic, result.results)

            # Get source metadata manager
            manager = _get_source_metadata()

            # Extract unique domains and fetch/enrich metadata
            domains = {
                article.get("domain")
                for article in result.results
                if article.get("domain")
            }
            for domain in domains:
                if domain:
                    try:
                        normalized = normalize_domain(domain)
                        entry = await manager.get(normalized)
                        if entry is None:
                            # Find an article with this domain for enrichment
                            article = next(
                                (a for a in result.results if a.get("domain") == domain),
                                {},
                            )
                            entry = await manager.enrich_from_gdelt(normalized, article)
                        source_metadata_map[normalized] = entry
                    except Exception as e:
                        logger.debug(f"Failed to get metadata for {domain}: {e}")

        # Check if there are sources that need analysis BEFORE providing the report
        from ignifer.source_metadata import ENRICHMENT_GDELT_BASELINE, MAX_DOMAINS_FOR_ANALYSIS

        unanalyzed_domains = []
        if source_metadata_map:
            # Count articles per domain for sorting
            domain_counts: dict[str, int] = {}
            for article in result.results:
                domain = article.get("domain", "")
                if domain:
                    try:
                        normalized = normalize_domain(domain)
                        domain_counts[normalized] = domain_counts.get(normalized, 0) + 1
                    except Exception:
                        pass

            # Find domains that need analysis
            for domain, entry in source_metadata_map.items():
                if entry.enrichment_source == ENRICHMENT_GDELT_BASELINE:
                    count = domain_counts.get(domain, 1)
                    unanalyzed_domains.append((domain, entry.nation, entry.language, count))

            # Sort by frequency and limit
            unanalyzed_domains.sort(key=lambda x: -x[3])
            unanalyzed_domains = unanalyzed_domains[:MAX_DOMAINS_FOR_ANALYSIS]

        # If there are unanalyzed sources, return ONLY analysis instructions (no report)
        if unanalyzed_domains:
            num = len(unanalyzed_domains)
            lines = []
            lines.append("## Source Analysis Required")
            lines.append("")
            lines.append(f"Found {len(result.results)} articles from {num} unanalyzed sources.")
            lines.append("**You must analyze these sources before I can provide the briefing.**")
            lines.append("")
            lines.append("### Sources to Analyze")
            lines.append("")

            for i, (domain, nation, language, count) in enumerate(unanalyzed_domains[:10], 1):
                nation_str = nation if nation else "Unknown"
                lines.append(f"{i}. **{domain}** ({nation_str}) - {count} articles")
                lines.append(f"   - WebSearch: `{domain} media bias reliability rating`")
                lines.append(f"   - Then call: `set_source_reliability(\"{domain}\", \"<A-F>\")`")
                lines.append("")

            if num > 10:
                lines.append(f"*...plus {num - 10} more sources*")
                lines.append("")

            lines.append("### Reliability Scale")
            lines.append("- **A** = Wire services (Reuters, AP, AFP)")
            lines.append("- **B** = Major outlets (BBC, NYT, established regional)")
            lines.append("- **C** = General news sites")
            lines.append("- **D** = Known bias issues")
            lines.append("- **E** = Unreliable/propaganda")
            lines.append("- **F** = Cannot judge")
            lines.append("")

            if detected_region:
                region_axes = {
                    "Taiwan": "china-independence",
                    "China": "china-independence",
                    "Hong Kong": "china-independence",
                    "Ukraine": "russia-west",
                    "Russia": "russia-west",
                }
                axis = region_axes.get(detected_region)
                if axis:
                    lines.append(f"### Regional Orientation ({detected_region})")
                    lines.append(f"For sources covering {detected_region}, also set orientation:")
                    lines.append(f"- `set_source_orientation(\"domain\", \"<orientation>\", \"{axis}\")`")
                    lines.append("")

            lines.append("---")
            lines.append(f"**After analyzing sources, call `briefing(\"{topic}\")` again to get the full report.**")

            return "\n".join(lines)

        # Format the result with time_range and source metadata
        formatter = _get_formatter()
        output = formatter.format(
            result,
            time_range=time_range,
            source_metadata=source_metadata_map if source_metadata_map else None,
            detected_region=detected_region,
            query=topic,
        )

        # Auto-extract top articles if we have results
        if result.results:
            logger.info(f"Auto-extracting {MAX_AUTO_EXTRACTS} articles...")
            extracts = await _auto_extract_articles(result.results, MAX_AUTO_EXTRACTS)

            if extracts:
                output += "\n\n"
                output += "=" * 55 + "\n"
                output += f"{'PRIMARY SOURCE EXTRACTS':^55}\n"
                output += "(MANDATORY - INCLUDE ALL ARTICLES BELOW)\n"
                output += "=" * 55 + "\n\n"

                for i, ext in enumerate(extracts, 1):
                    lang_val = ext.get("language", "")
                    lang = str(lang_val) if lang_val else ""
                    is_non_english = lang and lang.lower() != "english"
                    lang_tag = f" [{lang.upper()}]" if is_non_english else ""
                    output += f"### ARTICLE {i}{lang_tag}: {ext['title']}\n"
                    output += f"**Source:** {ext['domain']}\n"
                    output += f"**URL:** {ext['url']}\n\n"

                    content = ext.get("content")
                    if content:
                        output += content + "\n"
                    else:
                        output += f"*[Extraction failed: {ext.get('error', 'Unknown error')}]*\n"

                    output += "\n" + "-" * 55 + "\n\n"

        # Add rigor mode enhancements if enabled
        if effective_rigor and result.sources:
            # Build source metadata list
            sources = [s.metadata for s in result.sources if s.metadata]

            # Calculate confidence from sources
            quality_tiers = [s.quality for s in result.sources]
            calculator = ConfidenceCalculator()
            confidence = calculator.calculate_from_sources(quality_tiers)

            # Add rigor footer
            output += "\n" + "=" * 59 + "\n"
            output += "RIGOR MODE ANALYSIS\n"
            output += "=" * 59 + "\n\n"

            # Confidence statement
            output += "## Confidence Assessment\n\n"
            output += (
                confidence_to_language(
                    confidence.level,
                    f"the information in this briefing regarding {topic} is accurate",
                )
                + "\n\n"
            )

            # Source attribution
            output += format_source_attribution(sources, include_quality=True)

            # Analytical caveats
            output += "\n"
            output += format_analytical_caveats(
                caveats=["GDELT may not capture all sources in all languages."],
                source_names=["gdelt"],
            )

            # Bibliography
            output += "\n"
            output += format_bibliography(sources)

        logger.info(f"Briefing completed for topic: {topic}")
        return output

    except AdapterTimeoutError as e:
        logger.warning(f"Timeout getting briefing for {topic}: {e}")
        return (
            f"## Request Timed Out\n\n"
            f"The request for **{topic}** timed out.\n\n"
            f"**Suggestions:**\n"
            f"- Try again in a moment\n"
            f"- Use a more specific query\n"
            f"- Check your network connection"
        )

    except AdapterError as e:
        logger.error(f"Adapter error for {topic}: {e}")
        return (
            f"## Unable to Retrieve Data\n\n"
            f"Could not get intelligence on **{topic}**.\n\n"
            f"**What happened:** {e.message}\n\n"
            f"**Suggestions:**\n"
            f"- Try again in a few moments\n"
            f"- Try different search terms"
        )

    except Exception as e:
        logger.exception(f"Unexpected error for {topic}: {e}")
        return (
            f"## Error\n\n"
            f"An unexpected error occurred while researching **{topic}**.\n\n"
            f"Please try again later."
        )


@mcp.tool()
async def extract_article(url: str) -> str:
    """Extract article content from a news URL.

    Use this tool to get the full text of articles from ignifer briefings.
    Extracts main content, removing ads/navigation. Works with most news sites.

    Args:
        url: Full URL of the article to extract (from ignifer briefing)

    Returns:
        Extracted article text, or error message if extraction fails.
        For non-English articles, the original language text is returned -
        translate it for the user.
    """
    logger.info(f"Extracting article from: {url}")

    try:
        # Fetch with reasonable timeout and headers
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; IgniferBot/1.0; OSINT research)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,*;q=0.5",
            },
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        # Extract article content
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            favor_precision=True,
        )

        if not extracted:
            return f"Could not extract article content from {url}. Site may block extraction."

        # Truncate if very long
        if len(extracted) > 8000:
            extracted = extracted[:8000] + "\n\n[Article truncated - full text available at source]"

        logger.info(f"Successfully extracted {len(extracted)} chars from {url}")
        return f"**Source:** {url}\n\n{extracted}"

    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching {url}")
        return f"Timeout fetching article from {url}. Site may be slow or blocking."

    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error {e.response.status_code} for {url}")
        return f"HTTP error {e.response.status_code} fetching {url}."

    except Exception as e:
        logger.exception(f"Error extracting article from {url}: {e}")
        return f"Error extracting article: {e}"


@mcp.tool()
async def set_source_reliability(domain: str, reliability: str) -> str:
    """Set the reliability grade for a news source domain.

    Use this tool to override the auto-assigned reliability grade for a source.
    Grades follow IC standard (A=Completely reliable through F=Cannot be judged).

    Args:
        domain: The news source domain (e.g., 'reuters.com', 'scmp.com')
        reliability: Reliability grade A-F:
            A = Completely reliable
            B = Usually reliable
            C = Fairly reliable
            D = Not usually reliable
            E = Unreliable
            F = Reliability cannot be judged

    Returns:
        Confirmation message with updated reliability grade.
    """
    try:
        normalized = normalize_domain(domain)
        manager = _get_source_metadata()
        await manager.set_reliability(normalized, reliability)
        return f"Updated reliability for '{normalized}' to {reliability.upper()}."
    except InvalidReliabilityGradeError as e:
        return str(e)
    except SourceMetadataNotFoundError:
        return (
            f"No metadata found for '{domain}'. "
            "Run a briefing containing this source to auto-enrich, or manually set values."
        )
    except Exception as e:
        logger.exception(f"Error setting reliability for {domain}: {e}")
        return f"Error setting reliability: {e}"


@mcp.tool()
async def set_source_orientation(
    domain: str, orientation: str, axis: str | None = None
) -> str:
    """Set the political orientation for a news source domain.

    Use this tool to record the political leaning or bias of a source.
    Orientations are region-specific (e.g., pro-China/pro-independence for Taiwan).

    Args:
        domain: The news source domain (e.g., 'focustaiwan.tw')
        orientation: Political orientation description (e.g., 'Pro-independence', 'Center-right')
        axis: Optional orientation axis for context (e.g., 'china-independence', 'left-right')

    Returns:
        Confirmation message with updated orientation.
    """
    try:
        normalized = normalize_domain(domain)
        manager = _get_source_metadata()
        await manager.set_orientation(normalized, orientation, axis)
        axis_note = f" (axis: {axis})" if axis else ""
        return f"Updated orientation for '{normalized}' to '{orientation}'{axis_note}."
    except SourceMetadataNotFoundError:
        return (
            f"No metadata found for '{domain}'. "
            "Run a briefing containing this source to auto-enrich, or manually set values."
        )
    except Exception as e:
        logger.exception(f"Error setting orientation for {domain}: {e}")
        return f"Error setting orientation: {e}"


@mcp.tool()
async def set_source_nation(domain: str, nation: str) -> str:
    """Set the nation of origin for a news source domain.

    Use this tool to correct the auto-detected nation for a source.

    Args:
        domain: The news source domain (e.g., 'scmp.com')
        nation: Nation of origin (e.g., 'Hong Kong', 'Taiwan', 'United States')

    Returns:
        Confirmation message with updated nation.
    """
    try:
        normalized = normalize_domain(domain)
        manager = _get_source_metadata()
        await manager.set_nation(normalized, nation)
        return f"Updated nation for '{normalized}' to '{nation}'."
    except SourceMetadataNotFoundError:
        return (
            f"No metadata found for '{domain}'. "
            "Run a briefing containing this source to auto-enrich, or manually set values."
        )
    except Exception as e:
        logger.exception(f"Error setting nation for {domain}: {e}")
        return f"Error setting nation: {e}"


@mcp.tool()
async def get_source_metadata(domain: str) -> str:
    """Get stored metadata for a news source domain.

    Use this tool to inspect the reliability, orientation, and other
    metadata stored for a source.

    Args:
        domain: The news source domain (e.g., 'reuters.com')

    Returns:
        Formatted metadata including nation, language, reliability, and orientation.
    """
    try:
        normalized = normalize_domain(domain)
        manager = _get_source_metadata()
        entry = await manager.get(normalized)

        if entry is None:
            return (
                f"No metadata found for '{normalized}'. "
                "Run a briefing containing this source to auto-enrich, or manually set values."
            )

        lines = [f"**Source Metadata: {normalized}**", ""]
        lines.append(f"  Nation: {entry.nation or 'Unknown'}")
        lines.append(f"  Language: {entry.language or 'Unknown'}")
        lines.append(f"  Reliability: {entry.reliability} ({_reliability_description(entry.reliability)})")
        if entry.political_orientation:
            axis_note = f" ({entry.orientation_axis})" if entry.orientation_axis else ""
            lines.append(f"  Orientation: {entry.political_orientation}{axis_note}")
        lines.append(f"  Enrichment Source: {entry.enrichment_source}")
        if entry.original_reliability:
            lines.append(f"  Original Reliability: {entry.original_reliability}")

        return "\n".join(lines)
    except Exception as e:
        logger.exception(f"Error getting metadata for {domain}: {e}")
        return f"Error getting metadata: {e}"


@mcp.tool()
async def reset_source_metadata(domain: str) -> str:
    """Reset source metadata to original auto-enriched values.

    Use this tool to undo user overrides and restore the original
    auto-enriched reliability and orientation values.

    Args:
        domain: The news source domain to reset

    Returns:
        Confirmation message or error if no original values exist.
    """
    try:
        normalized = normalize_domain(domain)
        manager = _get_source_metadata()
        was_reset = await manager.reset(normalized)

        if was_reset:
            return f"Reset metadata for '{normalized}' to original auto-enriched values."
        else:
            return (
                f"No original values to restore for '{normalized}'. "
                "This source was manually added, not auto-enriched."
            )
    except SourceMetadataNotFoundError:
        return f"No metadata found for '{domain}'."
    except Exception as e:
        logger.exception(f"Error resetting metadata for {domain}: {e}")
        return f"Error resetting metadata: {e}"


def _reliability_description(grade: str) -> str:
    """Get human-readable description for reliability grade."""
    descriptions = {
        "A": "Completely reliable",
        "B": "Usually reliable",
        "C": "Fairly reliable",
        "D": "Not usually reliable",
        "E": "Unreliable",
        "F": "Reliability cannot be judged",
    }
    return descriptions.get(grade.upper(), "Unknown")


async def _get_economic_events(country: str, days: int = 7) -> list[dict[str, Any]]:
    """Query GDELT for recent economic events mentioning the country.

    Args:
        country: Country name to search for
        days: Number of days to look back (default 7)

    Returns:
        List of up to 5 recent economic event articles
    """
    try:
        gdelt = _get_adapter()
        query = f"{country} (economy OR sanctions OR trade OR tariffs OR inflation OR currency)"
        params = QueryParams(query=query, time_range=f"last {days} days")
        result = await gdelt.query(params)

        if result.status == ResultStatus.SUCCESS and result.results:
            return result.results[:5]
    except Exception as e:
        logger.debug(f"Failed to get economic events for {country}: {e}")

    return []


async def _get_country_context(country: str) -> dict[str, Any] | None:
    """Query Wikidata for country institutional context.

    Args:
        country: Country name to search for

    Returns:
        Dict with head_of_government, currency, etc. or None if lookup fails
    """
    try:
        wikidata = _get_wikidata()

        # Step 1: Search for the country to get its Q-ID
        params = QueryParams(query=country)
        search_result = await wikidata.query(params)

        if search_result.status != ResultStatus.SUCCESS or not search_result.results:
            return None

        qid_raw = search_result.results[0].get("qid")
        if not qid_raw:
            return None
        qid = str(qid_raw)

        # Step 2: Lookup by Q-ID to get full properties
        entity_result = await wikidata.lookup_by_qid(qid)

        if entity_result.status != ResultStatus.SUCCESS or not entity_result.results:
            return None

        # Properties are flattened directly on the entity
        entity = entity_result.results[0]

        return {
            "head_of_government": entity.get("head_of_government"),
            "head_of_state": entity.get("head_of_state"),
            "currency": entity.get("currency"),
            "central_bank": entity.get("central_bank"),
            "member_of": entity.get("member_of"),
        }
    except Exception as e:
        logger.debug(f"Failed to get country context for {country}: {e}")

    return None


# Indicator formatting configuration: (label, query_name, format_func)
# Format functions receive the value and return formatted string or None
def _fmt_trillion(v: float) -> str:
    """Format as USD trillions."""
    return f"${v / 1_000_000_000_000:.2f} trillion"


def _fmt_currency(v: float) -> str:
    """Format as USD with commas."""
    return f"${v:,.0f}"


def _fmt_million(v: float) -> str:
    """Format as millions."""
    return f"{v / 1_000_000:.1f} million"


def _fmt_pct_gni(v: float) -> str:
    """Format as percentage of GNI."""
    return f"{v:.1f}% of GNI"


def _fmt_pct_gdp_signed(v: float) -> str:
    """Format as signed percentage of GDP."""
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}% of GDP"


def _fmt_months(v: float) -> str:
    """Format as months of imports."""
    return f"{v:.1f} months imports"


def _fmt_pct_reserves(v: float) -> str:
    """Format as percentage of reserves."""
    return f"{v:.1f}% of reserves"


def _fmt_pct_gdp(v: float) -> str:
    """Format as percentage of GDP."""
    return f"{v:.1f}% of GDP"


def _fmt_billion_signed(v: float) -> str:
    """Format as signed USD billions."""
    sign = "+" if v >= 0 else "-"
    return f"{sign}${abs(v / 1_000_000_000):.1f} billion"


def _fmt_pct(v: float) -> str:
    """Format as percentage."""
    return f"{v:.1f}%"


# Indicator definitions: (display_label, query_term, formatter, display_name_width)
CORE_INDICATORS = [
    ("GDP", "gdp", _fmt_trillion, "GDP"),
    ("GDP per Capita", "gdp per capita", _fmt_currency, "GDP per Capita"),
    ("Population", "population", _fmt_million, "Population"),
]

E1_VULNERABILITY_INDICATORS = [
    ("External Debt", "external debt", _fmt_pct_gni, "External Debt"),
    ("Current Account", "current account", _fmt_pct_gdp_signed, "Current Account"),
    ("Total Reserves", "total reserves", _fmt_months, "Reserves"),
    ("Short-term Debt", "short-term debt", _fmt_pct_reserves, "Short-term Debt"),
]

E2_TRADE_INDICATORS = [
    ("Exports", "exports", _fmt_pct_gdp, "Exports"),
    ("Imports", "imports", _fmt_pct_gdp, "Imports"),
    ("Trade Openness", "trade openness", _fmt_pct_gdp, "Trade Openness"),
    ("Trade Balance", "trade balance", _fmt_billion_signed, "Trade Balance"),
]

E4_FINANCIAL_INDICATORS = [
    ("Inflation", "inflation", _fmt_pct, "Inflation"),
    ("Unemployment", "unemployment", _fmt_pct, "Unemployment"),
    ("FDI Inflows", "fdi inflows", _fmt_pct_gdp, "FDI Inflows"),
    ("Domestic Credit", "domestic credit", _fmt_pct_gdp, "Domestic Credit"),
]


def _format_indicator_section(
    all_results: dict[str, dict[str, Any]],
    indicators: list[tuple[str, str, Any, str]],
) -> list[str]:
    """Format a section of economic indicators.

    Args:
        all_results: Dictionary of indicator label -> result dict
        indicators: List of (key, query_term, formatter, display_name) tuples

    Returns:
        List of formatted lines (empty if no data)
    """
    lines = []
    for key, _, formatter, display_name in indicators:
        if key in all_results:
            val = all_results[key].get("value")
            if val is not None:
                formatted = formatter(val)
                # Pad display name to align values
                padded_name = f"{display_name} ".ljust(22, ".")
                lines.append(f"  {padded_name} {formatted}\n")
    return lines


@mcp.tool()
async def economic_context(
    country: str,
    rigor: bool | None = None,
) -> str:
    """Get comprehensive economic analysis for any country.

    Returns economic indicators organized by E-series analysis categories:
    - Key indicators (GDP, population)
    - Vulnerability assessment (E1): debt ratios, reserves
    - Trade profile (E2): exports, imports, openness
    - Financial indicators (E4): inflation, FDI, credit

    Also includes recent economic events from GDELT and government context
    from Wikidata when available.

    Args:
        country: Country name (e.g., "Germany", "Japan") or ISO code (e.g., "DEU", "JPN")
        rigor: Enable rigor mode for IC-standard output with full source
            attribution, confidence levels, and bibliography. If not specified,
            uses global IGNIFER_RIGOR_MODE setting.

    Returns:
        Formatted economic analysis with source attribution.
        In rigor mode, includes ICD 203 confidence language and bibliography.
    """
    effective_rigor = resolve_rigor_mode(rigor)
    logger.info(f"Economic context requested for: {country}, rigor: {effective_rigor}")

    # Build flat list of all indicators for querying
    all_indicator_defs = (
        CORE_INDICATORS
        + E1_VULNERABILITY_INDICATORS
        + E2_TRADE_INDICATORS
        + E4_FINANCIAL_INDICATORS
    )

    try:
        adapter = _get_worldbank()
        all_results: dict[str, dict[str, Any]] = {}
        rate_limited = False

        # Query each indicator
        for label, query_term, _, _ in all_indicator_defs:
            params = QueryParams(query=f"{query_term} {country}")
            result = await adapter.query(params)

            if result.status == ResultStatus.RATE_LIMITED:
                rate_limited = True
                break

            if result.status == ResultStatus.SUCCESS and result.results:
                sorted_results = sorted(
                    result.results, key=lambda x: str(x.get("year", "")), reverse=True
                )
                if sorted_results:
                    all_results[label] = sorted_results[0]

        # If rate limited, inform the user
        if rate_limited:
            logger.warning(f"Rate limited when fetching data for: {country}")
            return (
                "## Service Temporarily Unavailable\n\n"
                "World Bank API is rate limiting requests. "
                "Try again in a few minutes.\n\n"
                "**Suggestions:**\n"
                "- Wait a few minutes before trying again\n"
                "- Results may be cached - try your last query again"
            )

        # If no results at all, country not found
        if not all_results:
            logger.warning(f"No economic data found for: {country}")
            return (
                f"## Country Not Found\n\n"
                f"Could not find economic data for **{country}**.\n\n"
                f"**Suggestions:**\n"
                f"- Check the spelling of the country name\n"
                f"- Try using the ISO country code (e.g., 'DEU' for Germany)\n"
                f"- Try common aliases (e.g., 'USA' instead of 'United States of America')"
            )

        # Get country name and year from first result
        first_result = next(iter(all_results.values()))
        country_name = first_result.get("country", country)
        year = first_result.get("year", "N/A")

        # Fetch auxiliary data concurrently (silent degradation)
        context_task = asyncio.create_task(_get_country_context(country_name))
        events_task = asyncio.create_task(_get_economic_events(country_name))

        country_context = await context_task
        economic_events = await events_task

        # Track which sources contributed
        sources_used = ["World Bank Open Data"]

        # Format output
        output = "═" * 59 + "\n"
        output += f"{'ECONOMIC CONTEXT':^59}\n"
        output += "═" * 59 + "\n"
        output += f"COUNTRY: {country_name}\n"

        # Add government/currency context if available
        if country_context:
            sources_used.append("Wikidata")
            context_parts = []
            if country_context.get("head_of_government"):
                context_parts.append(country_context["head_of_government"])
            if country_context.get("currency"):
                context_parts.append(f"Currency: {country_context['currency']}")
            if context_parts:
                output += " | ".join(context_parts) + "\n"

        output += "\n"

        # === KEY INDICATORS ===
        output += f"KEY INDICATORS ({year}):\n"
        output += "".join(_format_indicator_section(all_results, CORE_INDICATORS))

        # === VULNERABILITY ASSESSMENT (E1) ===
        e1_lines = _format_indicator_section(all_results, E1_VULNERABILITY_INDICATORS)
        if e1_lines:
            output += "\nVULNERABILITY ASSESSMENT (E1):\n"
            output += "".join(e1_lines)

        # === TRADE PROFILE (E2) ===
        e2_lines = _format_indicator_section(all_results, E2_TRADE_INDICATORS)
        if e2_lines:
            output += "\nTRADE PROFILE (E2):\n"
            output += "".join(e2_lines)

        # === FINANCIAL INDICATORS (E4) ===
        e4_lines = _format_indicator_section(all_results, E4_FINANCIAL_INDICATORS)
        if e4_lines:
            output += "\nFINANCIAL INDICATORS (E4):\n"
            output += "".join(e4_lines)

        # === RECENT ECONOMIC EVENTS ===
        if economic_events:
            sources_used.append("GDELT")
            output += "\nRECENT ECONOMIC EVENTS:\n"
            for event in economic_events:
                title = event.get("title", "")
                date = event.get("seendate", "")[:10] if event.get("seendate") else ""
                # Truncate title if too long
                if len(title) > 50:
                    title = title[:47] + "..."
                if date and title:
                    output += f"  \u2022 [{date}] {title}\n"
                elif title:
                    output += f"  \u2022 {title}\n"

        # Footer
        output += "\n" + "-" * 59 + "\n"
        output += f"Sources: {', '.join(sources_used)}\n"
        retrieved_at_dt = datetime.now(timezone.utc)
        retrieved_at = retrieved_at_dt.strftime("%Y-%m-%d %H:%M UTC")
        output += f"Retrieved: {retrieved_at}\n"
        output += "=" * 59 + "\n"

        # Add rigor mode enhancements if enabled
        if effective_rigor:
            # Build source metadata
            source_names_lower = [s.lower() for s in sources_used]
            sources: list[SourceMetadata] = []
            for name in source_names_lower:
                if name == "world bank open data":
                    url = f"https://api.worldbank.org/v2/country/{country}"
                else:
                    url = f"https://{name.replace(' ', '-')}.org/"
                sources.append(
                    SourceMetadata(
                        source_name=name,
                        source_url=url,
                        retrieved_at=retrieved_at_dt,
                    )
                )

            # Calculate confidence
            quality_tiers = [QualityTier.HIGH] * len(sources)  # World Bank is high quality
            calculator = ConfidenceCalculator()
            confidence = calculator.calculate_from_sources(quality_tiers)

            output += "\n" + "=" * 59 + "\n"
            output += "RIGOR MODE ANALYSIS\n"
            output += "=" * 59 + "\n\n"

            # Confidence statement
            output += "## Confidence Assessment\n\n"
            output += (
                confidence_to_language(
                    confidence.level,
                    f"the economic data for {country_name} is accurate",
                )
                + "\n\n"
            )

            # Analytical caveats
            output += format_analytical_caveats(
                source_names=source_names_lower,
            )

            # Bibliography
            output += "\n"
            output += format_bibliography(sources)

        logger.info(f"Economic context completed for: {country}")
        return output

    except AdapterTimeoutError as e:
        logger.warning(f"Timeout getting economic context for {country}: {e}")
        return (
            f"## Request Timed Out\n\n"
            f"Economic data request for **{country}** timed out.\n\n"
            f"**Suggestions:**\n"
            f"- Try again in a moment\n"
            f"- Check your network connection"
        )

    except AdapterError as e:
        logger.error(f"Adapter error for {country}: {e}")
        if "rate limit" in str(e).lower():
            return (
                "## Service Temporarily Unavailable\n\n"
                "World Bank API is rate limiting requests.\n\n"
                "**Suggestions:**\n"
                "- Wait a few minutes before trying again\n"
                "- Results may be cached - try your last query again"
            )
        return (
            f"## Unable to Retrieve Data\n\n"
            f"Could not get economic data for **{country}**.\n\n"
            f"**What happened:** {e.message}\n\n"
            f"**Suggestions:**\n"
            f"- Try again in a few moments\n"
            f"- Try a different country name or code"
        )

    except Exception as e:
        logger.exception(f"Unexpected error for {country}: {e}")
        return (
            f"## Error\n\n"
            f"An unexpected error occurred while retrieving economic data for **{country}**.\n\n"
            f"Please try again later."
        )


def _format_entity_output(
    entity_data: dict[str, Any],
    resolution_tier: str,
    confidence: float,
    rigor_mode: bool = False,
) -> str:
    """Format entity data for user-friendly output.

    Args:
        entity_data: Entity information from WikidataAdapter
        resolution_tier: How the entity was resolved (exact, normalized, etc.)
        confidence: Confidence score of the resolution (0.0 to 1.0)
        rigor_mode: If True, include explicit match confidence (FR31)

    Returns:
        Formatted string with entity intelligence
    """
    # Extract key fields
    label = entity_data.get("label", "Unknown")
    qid = entity_data.get("qid", "")
    description = entity_data.get("description", "")
    aliases = entity_data.get("aliases", "")
    url = entity_data.get("url", f"https://www.wikidata.org/wiki/{qid}")
    retrieved_at_dt = datetime.now(timezone.utc)

    # Format entity type from instance_of
    instance_of = entity_data.get("instance_of", "")
    entity_type = instance_of if instance_of else "Entity"

    # Build output
    output = "=" * 55 + "\n"
    output += f"{'ENTITY LOOKUP':^55}\n"
    output += "=" * 55 + "\n"
    output += f"ENTITY: {label}\n"
    if entity_type and entity_type != "Entity":
        output += f"TYPE: {entity_type}\n"
    output += f"WIKIDATA: {qid} ({url})\n"

    if description:
        output += f"\nDESCRIPTION:\n{description}\n"

    # Key facts section
    key_facts = []
    if entity_data.get("headquarters"):
        key_facts.append(("Headquarters", entity_data["headquarters"]))
    if entity_data.get("inception"):
        key_facts.append(("Founded", entity_data["inception"]))
    if entity_data.get("country"):
        key_facts.append(("Country", entity_data["country"]))
    if entity_data.get("occupation"):
        key_facts.append(("Occupation", entity_data["occupation"]))
    if entity_data.get("citizenship"):
        key_facts.append(("Citizenship", entity_data["citizenship"]))
    if entity_data.get("website"):
        key_facts.append(("Website", entity_data["website"]))

    if key_facts:
        output += "\nKEY FACTS:\n"
        for fact_name, fact_value in key_facts:
            padded_name = f"{fact_name} ".ljust(20, ".")
            output += f"  {padded_name} {fact_value}\n"

    # Aliases
    if aliases:
        output += f"\nALIASES:\n  {aliases}\n"

    # Related entities count
    related_count = entity_data.get("related_entities_count", 0)
    if related_count > 0:
        output += f"\nRELATED ENTITIES: {related_count} linked entities in Wikidata\n"

    # Footer with resolution info
    output += "\n" + "-" * 55 + "\n"
    output += f"Resolution: {resolution_tier} (confidence: {confidence:.2f})\n"
    output += "Source: Wikidata\n"
    retrieved_at = retrieved_at_dt.strftime("%Y-%m-%d %H:%M UTC")
    output += f"Retrieved: {retrieved_at}\n"
    output += "=" * 55 + "\n"

    # Add rigor mode enhancements (FR31)
    if rigor_mode:
        output += "\n" + "=" * 59 + "\n"
        output += "RIGOR MODE ANALYSIS\n"
        output += "=" * 59 + "\n\n"

        # Explicit match confidence (FR31)
        output += "## Match Confidence\n\n"
        output += (
            format_entity_match_confidence(
                confidence_score=confidence,
                resolution_tier=resolution_tier,
                wikidata_qid=qid,
                match_factors=[
                    f"Resolution method: {resolution_tier}",
                    f"Wikidata entity found: {qid}",
                    "Entity type verified" if entity_type != "Entity" else "Entity type unknown",
                ],
            )
            + "\n\n"
        )

        # Source metadata
        source = SourceMetadata(
            source_name="wikidata",
            source_url=url,
            retrieved_at=retrieved_at_dt,
        )

        # Analytical caveats
        output += format_analytical_caveats(source_names=["wikidata"])

        # Bibliography
        output += "\n"
        output += format_bibliography([source])

    return output


def _format_disambiguation(
    results: list[dict[str, Any]],
    query: str,
) -> str:
    """Format multiple entity matches for disambiguation.

    Args:
        results: List of entity search results
        query: Original query string

    Returns:
        Formatted disambiguation message
    """
    output = "## Multiple Entities Found\n\n"
    output += f'Found {len(results)} entities matching "{query}". Please specify:\n\n'

    for i, result in enumerate(results[:5], 1):
        qid = result.get("qid", "")
        label = result.get("label", "Unknown")
        description = result.get("description", "No description")
        url = result.get("url", f"https://www.wikidata.org/wiki/{qid}")

        output += f"{i}. **{label}** ({qid})\n"
        output += f"   {description}\n"
        output += f"   {url}\n\n"

    output += '**Tip:** Use `identifier="Q..."` for precise lookup.\n'
    output += 'Example: `entity_lookup(identifier="Q90")` for Paris, France.\n'

    return output


def _format_resolution_failure(
    query: str,
    suggestions: list[str],
) -> str:
    """Format a failed resolution message with suggestions.

    Args:
        query: Original query string
        suggestions: List of suggestions from EntityResolver

    Returns:
        Formatted error message with suggestions
    """
    output = "## Entity Not Found\n\n"
    output += f'Could not find entity matching "{query}".\n\n'

    output += "**Suggestions:**\n"
    for suggestion in suggestions:
        output += f"- {suggestion}\n"

    return output


@mcp.tool()
async def entity_lookup(
    name: str = "",
    identifier: str = "",
    rigor: bool | None = None,
) -> str:
    """Look up any entity and get comprehensive intelligence.

    Use this tool to research people, organizations, companies, places, or things.
    Returns Wikidata-enriched information including entity type, description,
    key facts, aliases, and cross-reference identifiers.

    Args:
        name: Entity name to look up (e.g., "Gazprom", "Vladimir Putin", "NATO")
        identifier: Optional Wikidata Q-ID for direct lookup (e.g., "Q102673")
            Use this when you know the exact entity Q-ID for precise results.
        rigor: Enable rigor mode for IC-standard output with explicit match
            confidence percentages and full source attribution. If not specified,
            uses global IGNIFER_RIGOR_MODE setting.

    Returns:
        Formatted entity intelligence with source attribution, or
        disambiguation list if multiple matches found.
        In rigor mode, includes explicit match confidence percentages.
    """
    effective_rigor = resolve_rigor_mode(rigor)
    logger.info(
        f"Entity lookup requested: name='{name}', id='{identifier}', rigor={effective_rigor}"
    )

    # Normalize inputs - strip whitespace
    name = name.strip() if name else ""
    identifier = identifier.strip() if identifier else ""

    # Validate input - need at least one of name or identifier
    if not name and not identifier:
        return (
            "## Invalid Request\n\n"
            "Please provide either an entity `name` or `identifier`.\n\n"
            "**Examples:**\n"
            '- `entity_lookup(name="Gazprom")`\n'
            '- `entity_lookup(identifier="Q102673")`'
        )

    wikidata = _get_wikidata()

    try:
        # If identifier provided (Q-ID), do direct lookup
        if identifier:
            qid = identifier.upper()
            if not qid.startswith("Q"):
                qid = f"Q{qid}"

            logger.info(f"Direct Q-ID lookup: {qid}")
            result = await wikidata.lookup_by_qid(qid)

            if result.status != ResultStatus.SUCCESS or not result.results:
                error_msg = result.error or f"Entity {qid} not found in Wikidata."
                return (
                    f"## Entity Not Found\n\n"
                    f"{error_msg}\n\n"
                    f"**Suggestions:**\n"
                    f"- Check the Q-ID format (should be Q followed by digits)\n"
                    f'- Try searching by name instead: `entity_lookup(name="...")`\n'
                    f"- Browse Wikidata directly: https://www.wikidata.org"
                )

            entity_data = result.results[0]
            return _format_entity_output(
                entity_data,
                resolution_tier="direct Q-ID lookup",
                confidence=1.0,
                rigor_mode=effective_rigor,
            )

        # Name-based lookup - use EntityResolver first
        resolver = _get_entity_resolver()
        resolution = await resolver.resolve(name)

        if not resolution.is_successful():
            # Resolution failed - return suggestions
            return _format_resolution_failure(
                query=name,
                suggestions=resolution.suggestions,
            )

        # Resolution succeeded - fetch full entity details
        resolved_qid = resolution.wikidata_qid

        if resolved_qid:
            # Fetch full entity details by Q-ID
            result = await wikidata.lookup_by_qid(resolved_qid)

            if result.status == ResultStatus.SUCCESS and result.results:
                entity_data = result.results[0]
                return _format_entity_output(
                    entity_data,
                    resolution_tier=resolution.resolution_tier.value,
                    confidence=resolution.match_confidence,
                    rigor_mode=effective_rigor,
                )

        # If we have a resolution but no Q-ID or lookup failed,
        # try a direct search which may return multiple results
        params = QueryParams(query=name)
        search_result = await wikidata.query(params)

        if search_result.status != ResultStatus.SUCCESS or not search_result.results:
            return _format_resolution_failure(
                query=name,
                suggestions=resolution.suggestions
                or [
                    "Try checking the spelling",
                    "Try a more complete name",
                ],
            )

        # Multiple results - show disambiguation
        if len(search_result.results) > 1:
            return _format_disambiguation(search_result.results, name)

        # Single result - fetch full details
        entity_qid_raw = search_result.results[0].get("qid")
        if entity_qid_raw:
            entity_qid = str(entity_qid_raw)
            detail_result = await wikidata.lookup_by_qid(entity_qid)
            if detail_result.status == ResultStatus.SUCCESS and detail_result.results:
                return _format_entity_output(
                    detail_result.results[0],
                    resolution_tier=resolution.resolution_tier.value,
                    confidence=resolution.match_confidence,
                    rigor_mode=effective_rigor,
                )

        # Fallback to search result
        return _format_entity_output(
            search_result.results[0],
            resolution_tier=resolution.resolution_tier.value,
            confidence=resolution.match_confidence,
            rigor_mode=effective_rigor,
        )

    except AdapterTimeoutError as e:
        logger.warning(f"Timeout looking up entity '{name or identifier}': {e}")
        return (
            f"## Request Timed Out\n\n"
            f"The entity lookup for **{name or identifier}** timed out.\n\n"
            f"**Suggestions:**\n"
            f"- Try again in a moment\n"
            f"- Check your network connection\n"
            f"- Wikidata may be experiencing high load"
        )

    except AdapterError as e:
        logger.error(f"Adapter error looking up entity '{name or identifier}': {e}")
        return (
            f"## Unable to Retrieve Data\n\n"
            f"Could not look up entity **{name or identifier}**.\n\n"
            f"**What happened:** {e.message}\n\n"
            f"**Suggestions:**\n"
            f"- Try again in a few moments\n"
            f"- Try a different spelling or identifier"
        )

    except Exception as e:
        logger.exception(f"Unexpected error looking up entity '{name or identifier}': {e}")
        return (
            f"## Error\n\n"
            f"An unexpected error occurred while looking up **{name or identifier}**.\n\n"
            f"Please try again later."
        )


# =============================================================================
# Flight Tracking Tool
# =============================================================================


def _identify_aircraft_identifier(identifier: str) -> tuple[str, str]:
    """Identify the type of aircraft identifier and normalize it.

    Detects whether the identifier is:
    - ICAO24: 6 hex characters (e.g., 'abc123', 'A12F4E')
    - Tail number: N-number (US) or other national registration (e.g., 'N12345', 'G-ABCD')
    - Callsign: Airline code + flight number (e.g., 'UAL123', 'BAW456')

    Args:
        identifier: Aircraft identifier string

    Returns:
        Tuple of (identifier_type, normalized_value) where identifier_type is
        one of 'icao24', 'tail_number', or 'callsign'
    """
    # Normalize: strip whitespace, uppercase
    normalized = identifier.strip().upper()

    # ICAO24: exactly 6 hex characters
    if len(normalized) == 6:
        try:
            int(normalized, 16)
            return ("icao24", normalized.lower())
        except ValueError:
            pass  # Not hex, continue checking

    # US tail numbers: N followed by digits and optional letters
    # e.g., N12345, N123AB, N1234A
    if normalized.startswith("N") and len(normalized) >= 2:
        rest = normalized[1:]
        # Check if it looks like a US registration
        if rest[0].isdigit():
            return ("tail_number", normalized)

    # Other country tail numbers: letter-dash-letters (e.g., G-ABCD, F-GXYZ)
    if len(normalized) >= 5 and normalized[1] == "-":
        return ("tail_number", normalized)

    # Default to callsign
    return ("callsign", normalized)


def _format_heading(heading: float | None) -> str:
    """Format heading in degrees with cardinal direction.

    Args:
        heading: Heading in degrees (0-360), or None

    Returns:
        Formatted string like "045 (Northeast)" or "N/A"
    """
    if heading is None:
        return "N/A"

    # Cardinal directions
    directions = [
        (0, "North"),
        (45, "Northeast"),
        (90, "East"),
        (135, "Southeast"),
        (180, "South"),
        (225, "Southwest"),
        (270, "West"),
        (315, "Northwest"),
        (360, "North"),
    ]

    # Find closest direction
    direction = "North"
    min_diff: float = 360.0
    for deg, name in directions:
        diff = abs(heading - deg)
        if diff < min_diff:
            min_diff = diff
            direction = name

    return f"{heading:03.0f} ({direction})"


def _format_altitude(altitude_m: float | None, on_ground: bool | None) -> str:
    """Format altitude in feet and meters.

    Args:
        altitude_m: Altitude in meters, or None
        on_ground: Whether aircraft is on ground

    Returns:
        Formatted string like "35,000 ft (10,668 m)" or "On Ground"
    """
    if on_ground:
        return "On Ground"
    if altitude_m is None:
        return "N/A"

    altitude_ft = altitude_m * 3.28084
    return f"{altitude_ft:,.0f} ft ({altitude_m:,.0f} m)"


def _format_speed(velocity_ms: float | None) -> str:
    """Format ground speed in knots and km/h.

    Args:
        velocity_ms: Velocity in m/s, or None

    Returns:
        Formatted string like "452 kts (837 km/h)" or "N/A"
    """
    if velocity_ms is None:
        return "N/A"

    velocity_kts = velocity_ms * 1.94384
    velocity_kmh = velocity_ms * 3.6
    return f"{velocity_kts:.0f} kts ({velocity_kmh:.0f} km/h)"


def _format_timestamp(unix_timestamp: int | None) -> str:
    """Format Unix timestamp to human-readable UTC string.

    Args:
        unix_timestamp: Unix timestamp (seconds since epoch), or None

    Returns:
        Formatted string like "2026-01-09 14:32:00 UTC" or "N/A"
    """
    if unix_timestamp is None:
        return "N/A"

    dt = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _format_position(latitude: float | None, longitude: float | None) -> str:
    """Format latitude/longitude as human-readable coordinates.

    Args:
        latitude: Latitude in degrees
        longitude: Longitude in degrees

    Returns:
        Formatted string like "37.7749N, 122.4194W" or "N/A"
    """
    if latitude is None or longitude is None:
        return "N/A"

    lat_dir = "N" if latitude >= 0 else "S"
    lon_dir = "E" if longitude >= 0 else "W"

    return f"{abs(latitude):.4f}{lat_dir}, {abs(longitude):.4f}{lon_dir}"


def _analyze_track_coverage(
    waypoints: list[dict[str, Any]],
) -> tuple[str, list[tuple[str, str]]]:
    """Analyze track history for coverage quality and gaps.

    Args:
        waypoints: List of waypoint dictionaries with timestamp field

    Returns:
        Tuple of (coverage_assessment, gaps) where:
        - coverage_assessment is "Good", "Fair", or "Poor"
        - gaps is a list of (start_time, end_time) strings for significant gaps
    """
    if not waypoints:
        return ("No data", [])

    if len(waypoints) < 2:
        return ("Limited", [])

    # Analyze gaps between consecutive waypoints
    # Significant gap = more than 5 minutes (300 seconds)
    gap_threshold = 300
    gaps: list[tuple[str, str]] = []

    for i in range(1, len(waypoints)):
        prev_ts = waypoints[i - 1].get("timestamp")
        curr_ts = waypoints[i].get("timestamp")

        if prev_ts is not None and curr_ts is not None:
            gap_seconds = curr_ts - prev_ts
            if gap_seconds > gap_threshold:
                gaps.append(
                    (
                        _format_timestamp(prev_ts),
                        _format_timestamp(curr_ts),
                    )
                )

    # Assess coverage quality
    if not gaps:
        coverage = "Good (no significant gaps)"
    elif len(gaps) <= 2:
        coverage = "Fair (some gaps in coverage)"
    else:
        coverage = "Poor (multiple gaps - limited ADS-B reception)"

    return (coverage, gaps)


def _format_flight_output(
    identifier: str,
    state: dict[str, Any] | None,
    track_waypoints: list[dict[str, Any]],
    retrieved_at: datetime,
    rigor_mode: bool = False,
) -> str:
    """Format flight tracking data for user-friendly output.

    Args:
        identifier: Original identifier provided by user
        state: Current aircraft state dict, or None if not broadcasting
        track_waypoints: List of track waypoints
        retrieved_at: When data was retrieved
        rigor_mode: If True, add full source attribution and caveats

    Returns:
        Formatted string with flight tracking information
    """
    output = f"FLIGHT TRACKING: {identifier.upper()}\n"
    output += "=" * 55 + "\n\n"

    if state is None:
        # Aircraft not currently broadcasting
        output += "CURRENT POSITION:\n"
        output += "  Status: Aircraft not currently broadcasting position\n\n"

        if track_waypoints:
            # Show last known position from track
            last_wp = track_waypoints[-1]
            lat = last_wp.get("latitude")
            lon = last_wp.get("longitude")
            alt = last_wp.get("altitude")
            on_gnd = last_wp.get("on_ground")
            output += "LAST KNOWN POSITION:\n"
            output += f"  Location: {_format_position(lat, lon)}\n"
            output += f"  Altitude: {_format_altitude(alt, on_gnd)}\n"
            output += f"  Heading: {_format_heading(last_wp.get('heading'))}\n"
            output += f"  Last Contact: {_format_timestamp(last_wp.get('timestamp'))}\n\n"
        else:
            output += "  No recent position data available.\n\n"

        output += "NOTE: ADS-B coverage is not global. Aircraft may be:\n"
        output += "  - Out of range of ground receivers\n"
        output += "  - Flying over ocean or remote areas\n"
        output += "  - On the ground with transponder off\n"
        output += "  - Using a different flight identifier\n\n"

    else:
        # Current position available
        lat = state.get("latitude")
        lon = state.get("longitude")
        alt_baro = state.get("altitude_barometric")
        on_gnd = state.get("on_ground")
        output += "CURRENT POSITION:\n"
        output += f"  Location: {_format_position(lat, lon)}\n"
        output += f"  Altitude: {_format_altitude(alt_baro, on_gnd)}\n"
        output += f"  Heading: {_format_heading(state.get('heading'))}\n"
        output += f"  Ground Speed: {_format_speed(state.get('velocity'))}\n"
        output += f"  Last Contact: {_format_timestamp(state.get('last_contact'))}\n\n"

        output += "AIRCRAFT INFO:\n"
        output += f"  ICAO24: {state.get('icao24', 'N/A')}\n"
        if state.get("callsign"):
            output += f"  Callsign: {state.get('callsign')}\n"
        output += f"  Origin Country: {state.get('origin_country', 'N/A')}\n"
        output += f"  On Ground: {'Yes' if state.get('on_ground') else 'No'}\n"
        if state.get("squawk"):
            output += f"  Squawk: {state.get('squawk')}\n"
        output += "\n"

    # Track history section
    if track_waypoints:
        coverage, gaps = _analyze_track_coverage(track_waypoints)

        output += "TRACK HISTORY (last 24h):\n"
        output += f"  Waypoints: {len(track_waypoints)} positions recorded\n"

        first_ts = track_waypoints[0].get("timestamp")
        last_ts = track_waypoints[-1].get("timestamp")
        output += f"  First seen: {_format_timestamp(first_ts)}\n"
        output += f"  Last seen: {_format_timestamp(last_ts)}\n"
        output += f"  Coverage: {coverage}\n"

        if gaps:
            output += "\n  Gaps in coverage:\n"
            for gap_start, gap_end in gaps[:3]:  # Show max 3 gaps
                output += f"    - {gap_start} to {gap_end}\n"
            if len(gaps) > 3:
                output += f"    ... and {len(gaps) - 3} more gaps\n"
    else:
        output += "TRACK HISTORY:\n"
        output += "  No track history available for this aircraft.\n"

    output += "\n"

    # Footer
    output += "-" * 55 + "\n"
    timestamp_str = retrieved_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    output += f"Source: OpenSky Network (retrieved {timestamp_str})\n"
    output += "=" * 55 + "\n"

    # Add rigor mode enhancements
    if rigor_mode:
        output += "\n" + "=" * 59 + "\n"
        output += "RIGOR MODE ANALYSIS\n"
        output += "=" * 59 + "\n\n"

        # Source metadata
        source = SourceMetadata(
            source_name="opensky",
            source_url="https://opensky-network.org/api",
            retrieved_at=retrieved_at,
        )

        # Confidence - based on data freshness
        calculator = ConfidenceCalculator()
        confidence = calculator.calculate_from_sources([QualityTier.MEDIUM])

        output += "## Confidence Assessment\n\n"
        output += (
            confidence_to_language(
                confidence.level,
                f"the position data for {identifier.upper()} is accurate",
            )
            + "\n\n"
        )

        # Analytical caveats
        output += format_analytical_caveats(source_names=["opensky"])

        # Bibliography
        output += "\n"
        output += format_bibliography([source])

    return output


def _format_credentials_error() -> str:
    """Format error message when OpenSky credentials are not configured.

    Returns:
        Formatted error message with registration instructions
    """
    return (
        "## OpenSky Authentication Required\n\n"
        "Flight tracking requires OpenSky Network credentials.\n\n"
        "**How to configure:**\n\n"
        "1. Register for a free account at: https://opensky-network.org/login\n"
        "2. Configure credentials via environment variables:\n"
        "   ```\n"
        "   export IGNIFER_OPENSKY_USERNAME=your_username\n"
        "   export IGNIFER_OPENSKY_PASSWORD=your_password\n"
        "   ```\n"
        "   Or add to ~/.config/ignifer/config.toml:\n"
        "   ```toml\n"
        '   opensky_username = "your_username"\n'
        '   opensky_password = "your_password"\n'
        "   ```\n\n"
        "**Why authentication is required:**\n"
        "- Unauthenticated requests have very low rate limits\n"
        "- Track history requires authentication\n"
        "- Free accounts get 400 API credits/day (sufficient for typical use)\n"
    )


@mcp.tool()
async def track_flight(
    identifier: str,
    rigor: bool | None = None,
) -> str:
    """Track any aircraft by callsign, tail number, or ICAO24 code.

    Returns current position, aircraft info, and 24-hour track history
    from the OpenSky Network (community-driven ADS-B receiver network).

    Args:
        identifier: Aircraft identifier. Accepts:
            - Callsign: "UAL123", "BAW456" (airline code + flight number)
            - Tail number: "N12345" (US), "G-ABCD" (UK), etc.
            - ICAO24: "abc123" (6 hex chars, transponder address)
        rigor: Enable rigor mode for IC-standard output with full source
            attribution, confidence levels, and bibliography. If not specified,
            uses global IGNIFER_RIGOR_MODE setting.

    Returns:
        Formatted flight tracking report including position, heading,
        speed, and track history. Or helpful error if not found.
        In rigor mode, includes full source attribution and caveats.

    Note:
        ADS-B coverage varies by region. Aircraft may not be visible when:
        - Over oceans or remote areas without ground receivers
        - On the ground with transponder off
        - Flying under ADS-B mandate altitude
    """
    effective_rigor = resolve_rigor_mode(rigor)
    # Validate identifier is not empty
    if not identifier or not identifier.strip():
        return (
            "## Invalid Identifier\n\n"
            "Please provide a valid flight identifier.\n\n"
            "**Accepted formats:**\n"
            "- Callsign: UAL123, BAW456\n"
            "- Tail number: N12345, G-ABCD\n"
            "- ICAO24: abc123 (6 hex characters)"
        )

    logger.info(f"Track flight requested for: {identifier}")

    # Identify and normalize the identifier
    identifier_type, normalized = _identify_aircraft_identifier(identifier)
    logger.debug(f"Identifier type: {identifier_type}, normalized: {normalized}")

    try:
        opensky = _get_opensky()
        retrieved_at = datetime.now(timezone.utc)

        # Query strategy depends on identifier type
        state: dict[str, Any] | None = None
        icao24_for_track: str | None = None
        track_waypoints: list[dict[str, Any]] = []

        if identifier_type == "icao24":
            # Direct ICAO24 lookup
            state_result = await opensky.get_states(icao24=normalized)

            if state_result.status == ResultStatus.SUCCESS and state_result.results:
                state = state_result.results[0]
                icao24_for_track = normalized

            elif state_result.status == ResultStatus.RATE_LIMITED:
                return (
                    "## Rate Limited\n\n"
                    "OpenSky Network is rate limiting requests.\n\n"
                    "**Suggestions:**\n"
                    "- Wait a few minutes before trying again\n"
                    "- Authenticated users get higher rate limits"
                )

        elif identifier_type == "callsign":
            # Query by callsign
            params = QueryParams(query=normalized)
            state_result = await opensky.query(params)

            if state_result.status == ResultStatus.SUCCESS and state_result.results:
                state = state_result.results[0]
                icao24_raw = state.get("icao24")
                icao24_for_track = str(icao24_raw) if icao24_raw is not None else None

            elif state_result.status == ResultStatus.RATE_LIMITED:
                return (
                    "## Rate Limited\n\n"
                    "OpenSky Network is rate limiting requests.\n\n"
                    "**Suggestions:**\n"
                    "- Wait a few minutes before trying again\n"
                    "- Authenticated users get higher rate limits"
                )

        elif identifier_type == "tail_number":
            # Tail numbers require database lookup for ICAO24 mapping
            # For now, try as callsign (some aircraft use registration as callsign)
            params = QueryParams(query=normalized.replace("-", ""))
            state_result = await opensky.query(params)

            if state_result.status == ResultStatus.SUCCESS and state_result.results:
                state = state_result.results[0]
                icao24_raw = state.get("icao24")
                icao24_for_track = str(icao24_raw) if icao24_raw is not None else None
            else:
                # Tail number resolution not yet implemented
                callsign_suggestion = normalized.replace("-", "")
                return (
                    f"## Tail Number Lookup\n\n"
                    f"Could not find aircraft with tail number **{identifier}**.\n\n"
                    f"**Note:** Tail number to ICAO24 resolution requires additional "
                    f"database lookups not yet implemented.\n\n"
                    f"**Suggestions:**\n"
                    f"- Try searching by the flight's callsign instead (e.g., 'UAL123')\n"
                    f"- Use the ICAO24 hex code if known (6 characters, e.g., 'abc123')\n"
                    f"- Some aircraft use their registration as callsign - "
                    f"try '{callsign_suggestion}'"
                )

        # Get track history if we have an ICAO24
        if icao24_for_track:
            try:
                track_result = await opensky.get_track(icao24_for_track)

                if track_result.status == ResultStatus.SUCCESS and track_result.results:
                    track_waypoints = track_result.results

            except AdapterAuthError:
                # Track history requires auth - continue without it
                logger.debug("Track history unavailable (requires authentication)")

            except AdapterTimeoutError:
                # Timeout getting track - continue with state only
                logger.warning("Timeout getting track history")

            except AdapterError as e:
                # Other error - log and continue
                logger.warning(f"Error getting track history: {e}")

        # Format output
        return _format_flight_output(
            identifier=identifier,
            state=state,
            track_waypoints=track_waypoints,
            retrieved_at=retrieved_at,
            rigor_mode=effective_rigor,
        )

    except AdapterAuthError:
        logger.warning("OpenSky credentials not configured")
        return _format_credentials_error()

    except AdapterTimeoutError as e:
        logger.warning(f"Timeout tracking flight {identifier}: {e}")
        return (
            f"## Request Timed Out\n\n"
            f"The flight tracking request for **{identifier}** timed out.\n\n"
            f"**Suggestions:**\n"
            f"- Try again in a moment\n"
            f"- Check your network connection\n"
            f"- OpenSky Network may be experiencing high load"
        )

    except AdapterError as e:
        logger.error(f"Adapter error tracking flight {identifier}: {e}")
        return (
            f"## Unable to Track Flight\n\n"
            f"Could not track flight **{identifier}**.\n\n"
            f"**What happened:** {e.message}\n\n"
            f"**Suggestions:**\n"
            f"- Try again in a few moments\n"
            f"- Verify the identifier format"
        )

    except Exception as e:
        logger.exception(f"Unexpected error tracking flight {identifier}: {e}")
        return (
            f"## Error\n\n"
            f"An unexpected error occurred while tracking **{identifier}**.\n\n"
            f"Please try again later."
        )


# =============================================================================
# Vessel Tracking Tool
# =============================================================================


# Navigational status codes from AIS spec
NAVIGATIONAL_STATUS_MAP = {
    0: "Under way using engine",
    1: "At anchor",
    2: "Not under command",
    3: "Restricted manoeuvrability",
    4: "Constrained by draught",
    5: "Moored",
    6: "Aground",
    7: "Engaged in fishing",
    8: "Under way sailing",
    9: "Reserved (HSC)",
    10: "Reserved (WIG)",
    11: "Reserved",
    12: "Reserved",
    13: "Reserved",
    14: "AIS-SART (active)",
    15: "Not defined",
}


# Vessel type categories from AIS spec (simplified)
VESSEL_TYPE_MAP = {
    20: "Wing in ground",
    30: "Fishing",
    31: "Towing",
    32: "Towing (large)",
    33: "Dredging/Underwater ops",
    34: "Diving ops",
    35: "Military ops",
    36: "Sailing",
    37: "Pleasure craft",
    40: "High speed craft",
    50: "Pilot vessel",
    51: "Search and Rescue",
    52: "Tug",
    53: "Port tender",
    54: "Anti-pollution",
    55: "Law enforcement",
    58: "Medical transport",
    59: "Special craft",
    60: "Passenger",
    70: "Cargo",
    80: "Tanker",
    90: "Other",
}


def _identify_vessel_identifier(identifier: str) -> tuple[str, str]:
    """Identify the type of vessel identifier and normalize it.

    Detects whether the identifier is:
    - MMSI: 9 digits (e.g., '367596480', '353136000')
    - IMO: 'IMO' prefix + 7 digits (e.g., 'IMO 9811000', 'IMO9811000')
    - Vessel name: everything else (e.g., 'Ever Given', 'MAERSK ALABAMA')

    Args:
        identifier: Vessel identifier string

    Returns:
        Tuple of (identifier_type, normalized_value) where identifier_type is
        one of 'mmsi', 'imo', or 'vessel_name'
    """
    # Normalize: strip whitespace
    normalized = identifier.strip()

    # Check for MMSI: exactly 9 digits
    if normalized.isdigit() and len(normalized) == 9:
        return ("mmsi", normalized)

    # Check for IMO number: "IMO" followed by 7 digits
    # Handle various formats: "IMO 9811000", "IMO9811000", "imo 9811000"
    upper = normalized.upper()
    if upper.startswith("IMO"):
        # Extract digits after "IMO"
        rest = upper[3:].strip()
        if rest.isdigit() and len(rest) == 7:
            return ("imo", rest)

    # Default to vessel name
    return ("vessel_name", normalized)


async def _resolve_vessel_to_mmsi(
    identifier: str, identifier_type: str
) -> tuple[str | None, str | None, str | None]:
    """Resolve vessel name or IMO to MMSI using Wikidata.

    Wikidata contains many vessels with their MMSI (P587) and IMO (P458) numbers.

    Args:
        identifier: The vessel name or IMO number to look up
        identifier_type: Either 'vessel_name' or 'imo'

    Returns:
        Tuple of (mmsi, vessel_label, vessel_description) if found, or (None, None, None)
    """
    wikidata = _get_wikidata()

    try:
        # Search Wikidata for the vessel
        from ignifer.models import QueryParams

        result = await wikidata.query(QueryParams(query=identifier))

        if result.status != ResultStatus.SUCCESS or not result.results:
            logger.debug(f"Wikidata search for vessel '{identifier}' returned no results")
            return None, None, None

        # Check each result for MMSI property
        for search_result in result.results:
            qid = search_result.get("qid")
            if not qid:
                continue

            # Fetch full entity to get claims (including MMSI)
            entity_result = await wikidata.lookup_by_qid(qid)

            if entity_result.status != ResultStatus.SUCCESS or not entity_result.results:
                continue

            entity_data = entity_result.results[0]

            # Check for MMSI (stored in entity data if present)
            # We need to look at the raw claims - let's check if it's a ship
            # by looking for MMSI in the entity properties
            # The Wikidata adapter extracts key properties, but MMSI (P587) isn't
            # in the default list, so we need to fetch it directly

            # For now, let's do a direct API call to get P587 (MMSI)
            mmsi = await _get_wikidata_property(qid, "P587")

            if mmsi:
                label = entity_data.get("label", identifier)
                description = entity_data.get("description", "")
                logger.info(f"Resolved vessel '{identifier}' to MMSI {mmsi} via Wikidata ({qid})")
                return mmsi, label, description

        logger.debug(f"No MMSI found in Wikidata for vessel '{identifier}'")
        return None, None, None

    except Exception as e:
        logger.warning(f"Error resolving vessel '{identifier}' via Wikidata: {e}")
        return None, None, None


async def _get_wikidata_property(qid: str, property_id: str) -> str | None:
    """Fetch a specific property value from a Wikidata entity.

    Args:
        qid: Wikidata Q-ID (e.g., 'Q117072551')
        property_id: Wikidata property ID (e.g., 'P587' for MMSI)

    Returns:
        Property value as string, or None if not found
    """
    import httpx

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            headers={
                "User-Agent": "Ignifer/1.0 (https://github.com/ignifer/ignifer; ignifer@example.com)"
            },
        ) as client:
            response = await client.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbgetclaims",
                    "entity": qid,
                    "property": property_id,
                    "format": "json",
                },
            )

            if response.status_code != 200:
                return None

            data = response.json()
            claims = data.get("claims", {})

            if property_id not in claims:
                return None

            # Get the first claim's value
            claim_list = claims[property_id]
            if not claim_list:
                return None

            mainsnak = claim_list[0].get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})

            if datavalue.get("type") == "string":
                return datavalue.get("value")

            return None

    except Exception as e:
        logger.debug(f"Error fetching Wikidata property {property_id} for {qid}: {e}")
        return None


def _get_vessel_type_name(vessel_type: int | None) -> str:
    """Get human-readable vessel type from AIS type code.

    Args:
        vessel_type: AIS vessel type code (0-99), or None

    Returns:
        Human-readable vessel type string
    """
    if vessel_type is None:
        return "Unknown"

    # Exact match first
    if vessel_type in VESSEL_TYPE_MAP:
        return VESSEL_TYPE_MAP[vessel_type]

    # Check ranges for common types
    if 20 <= vessel_type <= 29:
        return "Wing in ground"
    if 30 <= vessel_type <= 39:
        return VESSEL_TYPE_MAP.get(vessel_type, "Fishing/Service")
    if 40 <= vessel_type <= 49:
        return "High speed craft"
    if 50 <= vessel_type <= 59:
        return VESSEL_TYPE_MAP.get(vessel_type, "Special craft")
    if 60 <= vessel_type <= 69:
        return "Passenger"
    if 70 <= vessel_type <= 79:
        return "Cargo"
    if 80 <= vessel_type <= 89:
        return "Tanker"
    if 90 <= vessel_type <= 99:
        return "Other"

    return f"Type {vessel_type}"


def _get_navigational_status_name(status: int | None) -> str:
    """Get human-readable navigational status from AIS status code.

    Args:
        status: AIS navigational status code (0-15), or None

    Returns:
        Human-readable status string
    """
    if status is None:
        return "Unknown"
    return NAVIGATIONAL_STATUS_MAP.get(status, f"Status {status}")


def _format_vessel_speed(sog: float | None) -> str:
    """Format speed over ground in knots and km/h.

    Args:
        sog: Speed over ground in knots, or None

    Returns:
        Formatted string like "12.5 kts (23.2 km/h)" or "N/A"
    """
    if sog is None:
        return "N/A"

    kmh = sog * 1.852
    return f"{sog:.1f} kts ({kmh:.1f} km/h)"


def _get_cardinal_direction(degrees: float) -> str:
    """Get cardinal direction from degrees (0-360).

    Uses sector-based approach: N is 337.5-22.5, NE is 22.5-67.5, etc.

    Args:
        degrees: Heading or course in degrees (0-360)

    Returns:
        Cardinal direction string (e.g., "North", "Northeast")
    """
    # Normalize to 0-360 range
    normalized = degrees % 360

    # Sector boundaries (each sector is 45 degrees centered on the direction)
    if normalized >= 337.5 or normalized < 22.5:
        return "North"
    elif normalized < 67.5:
        return "Northeast"
    elif normalized < 112.5:
        return "East"
    elif normalized < 157.5:
        return "Southeast"
    elif normalized < 202.5:
        return "South"
    elif normalized < 247.5:
        return "Southwest"
    elif normalized < 292.5:
        return "West"
    else:
        return "Northwest"


def _format_vessel_course(cog: float | None) -> str:
    """Format course over ground in degrees with cardinal direction.

    Args:
        cog: Course over ground in degrees (0-360), or None

    Returns:
        Formatted string like "225 (Southwest)" or "N/A"
    """
    if cog is None:
        return "N/A"

    direction = _get_cardinal_direction(cog)
    return f"{cog:.0f} ({direction})"


def _format_vessel_heading(heading: int | None) -> str:
    """Format vessel heading in degrees with cardinal direction.

    Args:
        heading: True heading in degrees (0-359), or None.
                 AIS value 511 means "not available".

    Returns:
        Formatted string like "312 (Northwest)" or "N/A"
    """
    if heading is None or heading == 511:  # 511 = not available in AIS spec
        return "N/A"

    direction = _get_cardinal_direction(float(heading))
    return f"{heading} ({direction})"


def _format_vessel_position_coords(lat: float | None, lon: float | None) -> str:
    """Format latitude/longitude as human-readable coordinates.

    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees

    Returns:
        Formatted string like "31.2340N, 32.3456E" or "N/A"
    """
    if lat is None or lon is None:
        return "N/A"

    lat_dir = "N" if lat >= 0 else "S"
    lon_dir = "E" if lon >= 0 else "W"

    return f"{abs(lat):.4f}{lat_dir}, {abs(lon):.4f}{lon_dir}"


def _is_vessel_stationary(nav_status: int | None, sog: float | None) -> tuple[bool, str]:
    """Determine if vessel is stationary and why.

    Args:
        nav_status: Navigational status code
        sog: Speed over ground in knots

    Returns:
        Tuple of (is_stationary, reason)
    """
    # Check navigational status first
    if nav_status == 1:  # At anchor
        return (True, "At anchor")
    if nav_status == 5:  # Moored
        return (True, "Moored")
    if nav_status == 6:  # Aground
        return (True, "Aground")

    # Check speed (< 0.5 kts is effectively stationary)
    if sog is not None and sog < 0.5:
        return (True, "Stationary (speed < 0.5 kts)")

    return (False, "")


def _format_vessel_output(
    identifier: str,
    position_data: dict[str, Any] | None,
    retrieved_at: datetime,
    rigor_mode: bool = False,
) -> str:
    """Format vessel tracking data for user-friendly output.

    Args:
        identifier: Original identifier provided by user
        position_data: Vessel position dict from AISStreamAdapter, or None
        retrieved_at: When data was retrieved
        rigor_mode: If True, add full source attribution and caveats

    Returns:
        Formatted string with vessel tracking information
    """
    # Get vessel name for display
    display_name = identifier.upper()
    if position_data and position_data.get("vessel_name"):
        display_name = position_data["vessel_name"].upper()

    output = f"VESSEL TRACKING: {display_name}\n"
    output += "=" * 55 + "\n\n"

    if position_data is None:
        # Vessel not currently broadcasting
        output += "CURRENT POSITION:\n"
        output += "  Status: Vessel not currently broadcasting AIS\n\n"
        output += "NOTE: This vessel is not currently visible in the AIS network.\n"
        output += "Possible reasons:\n"
        output += "  - AIS transponder is turned off or malfunctioning\n"
        output += "  - Vessel is outside AIS receiver coverage area\n"
        output += "  - Vessel is in port with shore-power AIS disabled\n"
        output += "  - Some vessels intentionally disable AIS for security\n\n"
    else:
        # Extract position data
        lat = position_data.get("latitude")
        lon = position_data.get("longitude")
        sog = position_data.get("speed_over_ground")
        cog = position_data.get("course_over_ground")
        heading = position_data.get("heading")
        nav_status = position_data.get("navigational_status")
        timestamp = position_data.get("timestamp")

        # Check if stationary
        is_stationary, stationary_reason = _is_vessel_stationary(nav_status, sog)

        output += "CURRENT POSITION:\n"
        output += f"  Location: {_format_vessel_position_coords(lat, lon)}\n"
        output += f"  Speed: {_format_vessel_speed(sog)}\n"
        output += f"  Course: {_format_vessel_course(cog)}\n"
        formatted_heading = _format_vessel_heading(heading)
        if formatted_heading != "N/A":
            output += f"  Heading: {formatted_heading}\n"
        output += f"  Status: {_get_navigational_status_name(nav_status)}\n"

        if is_stationary:
            output += f"  ** {stationary_reason} **\n"

        output += "\n"

        # Vessel info section
        output += "VESSEL INFO:\n"
        mmsi = position_data.get("mmsi")
        if mmsi:
            output += f"  MMSI: {mmsi}\n"
        imo = position_data.get("imo")
        if imo:
            output += f"  IMO: {imo}\n"
        vessel_type = position_data.get("vessel_type")
        output += f"  Type: {_get_vessel_type_name(vessel_type)}\n"
        country = position_data.get("country")
        if country:
            output += f"  Flag: {country}\n"
        destination = position_data.get("destination")
        if destination:
            output += f"  Destination: {destination}\n"
        eta = position_data.get("eta")
        if eta:
            output += f"  ETA: {eta}\n"

        output += "\n"

        # AIS update timestamp
        if timestamp:
            output += f"Last AIS Update: {timestamp}\n"

    output += "\n"

    # Footer
    output += "-" * 55 + "\n"
    timestamp_str = retrieved_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    output += f"Source: AISStream (retrieved {timestamp_str})\n"
    output += "=" * 55 + "\n"

    # Add rigor mode enhancements
    if rigor_mode:
        output += "\n" + "=" * 59 + "\n"
        output += "RIGOR MODE ANALYSIS\n"
        output += "=" * 59 + "\n\n"

        # Source metadata
        source = SourceMetadata(
            source_name="aisstream",
            source_url="https://aisstream.io/",
            retrieved_at=retrieved_at,
        )

        # Confidence
        calculator = ConfidenceCalculator()
        confidence = calculator.calculate_from_sources([QualityTier.MEDIUM])

        output += "## Confidence Assessment\n\n"
        output += (
            confidence_to_language(
                confidence.level,
                f"the position data for {identifier.upper()} is accurate",
            )
            + "\n\n"
        )

        # Analytical caveats
        output += format_analytical_caveats(source_names=["aisstream"])

        # Bibliography
        output += "\n"
        output += format_bibliography([source])

    return output


def _format_vessel_credentials_error() -> str:
    """Format error message when AISStream credentials are not configured.

    Returns:
        Formatted error message with registration instructions
    """
    return (
        "## AISStream Authentication Required\n\n"
        "Vessel tracking requires an AISStream API key.\n\n"
        "**How to configure:**\n\n"
        "1. Register for a free account at: https://aisstream.io/\n"
        "2. Get your API key from the AISStream dashboard\n"
        "3. Configure credentials via environment variable:\n"
        "   ```\n"
        "   export IGNIFER_AISSTREAM_KEY=your_api_key\n"
        "   ```\n"
        "   Or add to ~/.config/ignifer/config.toml:\n"
        "   ```toml\n"
        '   aisstream_key = "your_api_key"\n'
        "   ```\n\n"
        "**Why AISStream:**\n"
        "- Free tier available for hobbyists\n"
        "- Real-time global AIS data via WebSocket\n"
        "- Covers 99%+ of commercial shipping\n"
    )


def _format_vessel_disambiguation(
    matches: list[dict[str, Any]],
    query: str,
) -> str:
    """Format multiple vessel matches for disambiguation.

    Args:
        matches: List of vessel position dicts
        query: Original query string

    Returns:
        Formatted disambiguation message
    """
    output = "## Multiple Vessels Found\n\n"
    output += f'Found {len(matches)} vessels matching "{query}". Please specify:\n\n'

    for i, vessel in enumerate(matches[:5], 1):
        name = vessel.get("vessel_name", "Unknown")
        mmsi = vessel.get("mmsi", "N/A")
        imo = vessel.get("imo")
        vessel_type = _get_vessel_type_name(vessel.get("vessel_type"))
        country = vessel.get("country", "Unknown")
        destination = vessel.get("destination", "N/A")

        output += f"{i}. **{name}** (MMSI: {mmsi})\n"
        output += f"   Type: {vessel_type} | Flag: {country}\n"
        if imo:
            output += f"   IMO: {imo}\n"
        if destination and destination != "N/A":
            output += f"   Destination: {destination}\n"
        output += "\n"

    output += "**Tip:** Use MMSI or IMO number for precise lookup.\n"
    output += 'Example: `track_vessel(identifier="367596480")` for MMSI\n'
    output += 'Example: `track_vessel(identifier="IMO 9811000")` for IMO\n'

    return output


@mcp.tool()
async def track_vessel(
    identifier: str,
    rigor: bool | None = None,
) -> str:
    """Track any vessel by name, IMO number, or MMSI.

    Returns current position, speed, heading, and vessel details from
    real-time AIS (Automatic Identification System) data via AISStream.

    Args:
        identifier: Vessel identifier. Accepts:
            - MMSI: 9 digits (e.g., "367596480", "353136000")
            - IMO: "IMO" + 7 digits (e.g., "IMO 9811000", "IMO9811000")
            - Vessel name: Ship name (e.g., "Ever Given", "MAERSK ALABAMA")
        rigor: Enable rigor mode for IC-standard output with full source
            attribution, confidence levels, and bibliography. If not specified,
            uses global IGNIFER_RIGOR_MODE setting.

    Returns:
        Formatted vessel tracking report including position, speed, heading,
        vessel type, destination, and flag state. Or helpful error if not found.
        In rigor mode, includes full source attribution and caveats.

    Note:
        AIS coverage is global but not 100%. Vessels may not be visible when:
        - AIS transponder is disabled or malfunctioning
        - In port with shore-based equipment
        - Some vessels intentionally disable AIS for security
    """
    effective_rigor = resolve_rigor_mode(rigor)
    # Validate identifier is not empty
    if not identifier or not identifier.strip():
        return (
            "## Invalid Identifier\n\n"
            "Please provide a valid vessel identifier.\n\n"
            "**Accepted formats:**\n"
            "- MMSI: 367596480 (9 digits)\n"
            "- IMO: IMO 9811000 (IMO + 7 digits)\n"
            "- Vessel name: Ever Given"
        )

    logger.info(f"Track vessel requested for: {identifier}")

    # Identify and normalize the identifier
    identifier_type, normalized = _identify_vessel_identifier(identifier)
    logger.debug(f"Identifier type: {identifier_type}, normalized: {normalized}")

    try:
        aisstream = _get_aisstream()
        retrieved_at = datetime.now(timezone.utc)

        position_data: dict[str, Any] | None = None

        if identifier_type == "mmsi":
            # Direct MMSI lookup
            result = await aisstream.get_vessel_position(normalized)

            if result.status == ResultStatus.SUCCESS and result.results:
                position_data = result.results[0]
            elif result.status == ResultStatus.NO_DATA:
                # Vessel not broadcasting
                return _format_vessel_output(identifier, None, retrieved_at, effective_rigor)
            elif result.status == ResultStatus.RATE_LIMITED:
                return (
                    "## Rate Limited\n\n"
                    "AISStream is rate limiting requests.\n\n"
                    "**Suggestions:**\n"
                    "- Wait a few minutes before trying again\n"
                    "- Check your API key usage limits"
                )

        elif identifier_type == "imo":
            # IMO lookup - try to resolve via Wikidata first
            mmsi, vessel_label, vessel_desc = await _resolve_vessel_to_mmsi(
                f"IMO {normalized}", identifier_type
            )

            if mmsi:
                logger.info(f"Resolved IMO {normalized} to MMSI {mmsi} via Wikidata")
                result = await aisstream.get_vessel_position(mmsi)

                if result.status == ResultStatus.SUCCESS and result.results:
                    position_data = result.results[0]
                    # Add resolved vessel info to position data
                    if vessel_label:
                        position_data["resolved_name"] = vessel_label
                    if vessel_desc:
                        position_data["resolved_description"] = vessel_desc
                elif result.status == ResultStatus.NO_DATA:
                    return _format_vessel_output(
                        vessel_label or f"IMO {normalized}",
                        None,
                        retrieved_at,
                        effective_rigor,
                    )
            else:
                # Wikidata doesn't have this IMO - return helpful message
                return (
                    f"## IMO Lookup\n\n"
                    f"IMO number **{normalized}** could not be resolved to MMSI.\n\n"
                    f"The vessel was not found in Wikidata's vessel database.\n\n"
                    f"**Suggestions:**\n"
                    f"- Try searching by vessel name instead\n"
                    f"- Use the vessel's MMSI if known (9 digits)\n"
                    f"- Look up MMSI from IMO at: https://www.marinetraffic.com\n"
                )

        elif identifier_type == "vessel_name":
            # Vessel name search - try to resolve via Wikidata
            mmsi, vessel_label, vessel_desc = await _resolve_vessel_to_mmsi(
                normalized, identifier_type
            )

            if mmsi:
                logger.info(f"Resolved vessel '{normalized}' to MMSI {mmsi} via Wikidata")
                result = await aisstream.get_vessel_position(mmsi)

                if result.status == ResultStatus.SUCCESS and result.results:
                    position_data = result.results[0]
                    # Add resolved vessel info to position data
                    if vessel_label:
                        position_data["resolved_name"] = vessel_label
                    if vessel_desc:
                        position_data["resolved_description"] = vessel_desc
                elif result.status == ResultStatus.NO_DATA:
                    return _format_vessel_output(
                        vessel_label or normalized,
                        None,
                        retrieved_at,
                        effective_rigor,
                    )
            else:
                # Wikidata doesn't have this vessel - return helpful message
                return (
                    f"## Vessel Name Search\n\n"
                    f'Vessel **"{normalized}"** could not be resolved to MMSI.\n\n'
                    f"The vessel was not found in Wikidata's vessel database.\n\n"
                    f"**Suggestions:**\n"
                    f"- Use the vessel's MMSI if known (9 digits)\n"
                    f"- Use the vessel's IMO number (IMO + 7 digits)\n"
                    f"- Look up MMSI from vessel name at:\n"
                    f"  - https://www.marinetraffic.com\n"
                    f"  - https://www.vesselfinder.com\n"
                )

        # Format output
        return _format_vessel_output(identifier, position_data, retrieved_at, effective_rigor)

    except AdapterAuthError:
        logger.warning("AISStream credentials not configured")
        return _format_vessel_credentials_error()

    except AdapterTimeoutError as e:
        logger.warning(f"Timeout tracking vessel {identifier}: {e}")
        return (
            f"## Request Timed Out\n\n"
            f"The vessel tracking request for **{identifier}** timed out.\n\n"
            f"**Suggestions:**\n"
            f"- Try again in a moment\n"
            f"- Check your network connection\n"
            f"- AISStream may be experiencing high load"
        )

    except AdapterError as e:
        logger.error(f"Adapter error tracking vessel {identifier}: {e}")
        return (
            f"## Unable to Track Vessel\n\n"
            f"Could not track vessel **{identifier}**.\n\n"
            f"**What happened:** {e.message}\n\n"
            f"**Suggestions:**\n"
            f"- Try again in a few moments\n"
            f"- Verify the identifier format"
        )

    except Exception as e:
        logger.exception(f"Unexpected error tracking vessel {identifier}: {e}")
        return (
            f"## Error\n\n"
            f"An unexpected error occurred while tracking **{identifier}**.\n\n"
            f"Please try again later."
        )


# ============================================================================
# DEEP DIVE MULTI-SOURCE ANALYSIS TOOL
# ============================================================================


# Focus area to source mapping for boosting relevance
FOCUS_SOURCE_BOOST: dict[str, list[str]] = {
    "economic": ["worldbank", "gdelt"],
    "entity": ["wikidata"],
    "news": ["gdelt"],
    "aviation": ["opensky", "wikidata", "gdelt"],
    "maritime": ["aisstream", "wikidata", "gdelt"],
}

# Confidence level labels for display (ICD 203 compliant)
# Ranges match ConfidenceLevel.percentage_range from models.py
CONFIDENCE_LABELS: dict[str, str] = {
    "ALMOST_CERTAIN": "ALMOST CERTAIN (95-100%)",
    "VERY_LIKELY": "VERY LIKELY (80-95%)",
    "LIKELY": "LIKELY (55-80%)",
    "ROUGHLY_EVEN": "ROUGHLY EVEN (45-55%)",
    "UNLIKELY": "UNLIKELY (20-45%)",
    "VERY_UNLIKELY": "VERY UNLIKELY (5-20%)",
    "REMOTE": "REMOTE (0-5%)",
}


def _format_deep_dive_header(
    topic: str,
    sources_queried: list[str],
    timestamp: str,
) -> str:
    """Format the header section of a deep dive report.

    Args:
        topic: The topic being analyzed
        sources_queried: List of source names that were queried
        timestamp: UTC timestamp string

    Returns:
        Formatted header string
    """
    sources_str = ", ".join(s.upper() for s in sources_queried) if sources_queried else "None"
    header = "=" * 55 + "\n"
    header += f"{'DEEP DIVE INTELLIGENCE REPORT':^55}\n"
    header += f"{'UNCLASSIFIED // OSINT':^55}\n"
    header += "=" * 55 + "\n"
    header += f"TOPIC: {topic.upper()}\n"
    header += f"DATE:  {timestamp}\n"
    header += f"SOURCES QUERIED: {sources_str}\n"
    header += "-" * 55 + "\n"
    return header


def _format_finding_section(
    finding: Finding,
    section_title: str,
) -> str:
    """Format a single finding section.

    Args:
        finding: The Finding object to format
        section_title: Section header title

    Returns:
        Formatted finding section string
    """
    output = f"\n### {section_title}\n"
    source_names = [s.source_name.upper() for s in finding.sources]
    output += f"[Source: {', '.join(source_names)}]\n"
    output += f"- {finding.content}\n"

    if finding.status == CorroborationStatus.CORROBORATED:
        output += f"  {finding.corroboration_note}\n"

    return output


def _format_corroboration_section(findings: list[Finding]) -> str:
    """Format the corroboration analysis section.

    Args:
        findings: List of findings to analyze

    Returns:
        Formatted corroboration section string
    """
    output = "\n" + "-" * 55 + "\n"
    output += "CORRELATION ANALYSIS\n"
    output += "-" * 55 + "\n"

    # Corroborated findings
    corroborated = [f for f in findings if f.status == CorroborationStatus.CORROBORATED]
    if corroborated:
        output += "\n### CORROBORATED FINDINGS\n"
        for finding in corroborated:
            source_names = [s.source_name.upper() for s in finding.sources]
            output += f"* [{finding.topic}] - Corroborated by [{', '.join(source_names)}]\n"
    else:
        output += "\n### CORROBORATED FINDINGS\n"
        output += "No findings corroborated by multiple sources.\n"

    return output


def _format_conflicts_section(conflicts: list[Conflict]) -> str:
    """Format the information conflicts section.

    Args:
        conflicts: List of conflicts to display

    Returns:
        Formatted conflicts section string
    """
    if not conflicts:
        return "\n### INFORMATION CONFLICTS\nNo conflicts detected between sources.\n"

    output = "\n### INFORMATION CONFLICTS\n"
    for conflict in conflicts:
        output += f"! [{conflict.topic}]: {conflict.source_a.source_name.upper()} says "
        output += f"{conflict.source_a_value}, {conflict.source_b.source_name.upper()} says "
        output += f"{conflict.source_b_value}\n"
        if conflict.suggested_authority:
            output += f"  Suggested authority: {conflict.suggested_authority.upper()} "
            output += "(higher quality tier)\n"

    return output


def _format_unavailable_sources_section(
    unavailable: list[tuple[str, str]],
) -> str:
    """Format the unavailable sources section.

    Args:
        unavailable: List of (source_name, reason) tuples

    Returns:
        Formatted unavailable sources section string
    """
    if not unavailable:
        return ""

    output = "\n### SOURCES NOT QUERIED\n"
    for source_name, reason in unavailable:
        output += f"- {source_name.upper()}: {reason}\n"

    return output


def _format_source_attribution_section(
    result: AggregatedResult,
    timestamp: str,
) -> str:
    """Format the source attribution section.

    Args:
        result: The aggregated result
        timestamp: Current timestamp string

    Returns:
        Formatted attribution section string
    """
    output = "\n" + "-" * 55 + "\n"
    output += "SOURCE ATTRIBUTION\n"
    output += "-" * 55 + "\n"

    for attribution in result.source_attributions:
        retrieved = attribution.retrieved_at.strftime("%Y-%m-%d %H:%M UTC")
        output += f"{attribution.source_name.upper():15} Retrieved: {retrieved}\n"

    if result.sources_failed:
        output += "\nFailed sources: " + ", ".join(s.upper() for s in result.sources_failed)
        output += "\n"

    return output


def _format_deep_dive_footer(confidence_level: str) -> str:
    """Format the footer section with overall confidence.

    Args:
        confidence_level: The confidence level name

    Returns:
        Formatted footer string
    """
    label = CONFIDENCE_LABELS.get(confidence_level, confidence_level)
    footer = "\n" + "=" * 55 + "\n"
    footer += f"Overall Confidence: {label}\n"
    footer += "=" * 55 + "\n"
    return footer


async def _format_deep_dive_output(
    topic: str,
    result: AggregatedResult,
    unavailable_sources: list[tuple[str, str]],
    focus: str | None,
    rigor_mode: bool = False,
) -> str:
    """Format the complete deep dive output.

    Args:
        topic: The topic being analyzed
        result: The aggregated result from Correlator
        unavailable_sources: List of (source_name, reason) tuples
        focus: Optional focus area
        rigor_mode: If True, add full rigor mode enhancements

    Returns:
        Complete formatted deep dive report
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Header
    output = _format_deep_dive_header(topic, result.sources_queried, timestamp)

    # Group findings by topic/source for organized output
    findings_by_source: dict[str, list[Finding]] = {}
    for finding in result.findings:
        # Use the first source name as key for grouping
        if finding.sources:
            key = finding.sources[0].source_name
            if key not in findings_by_source:
                findings_by_source[key] = []
            findings_by_source[key].append(finding)

    # Source-specific sections with proper titles
    section_titles = {
        "gdelt": "NEWS & EVENTS (GDELT)",
        "worldbank": "ECONOMIC CONTEXT (World Bank)",
        "wikidata": "KEY ENTITIES (Wikidata)",
        "opensky": "AVIATION TRACKING (OpenSky)",
        "aisstream": "MARITIME TRACKING (AISStream)",
    }

    # Output findings grouped by source
    # Limit news articles to avoid overwhelming output
    max_news_articles = 15

    source_order = [
        "gdelt",
        "worldbank",
        "wikidata",
        "opensky",
        "aisstream",
    ]
    for source_name in source_order:
        if source_name in findings_by_source:
            section_title = section_titles.get(source_name, source_name.upper())
            # Emphasize focus area if specified
            if focus and source_name in FOCUS_SOURCE_BOOST.get(focus.lower(), []):
                section_title = f"** {section_title} (FOCUS) **"
            output += f"\n### {section_title}\n"
            output += f"[Source: {source_name.upper()}]\n"

            source_findings = findings_by_source[source_name]
            # Limit news articles to avoid overwhelming output
            if source_name == "gdelt" and len(source_findings) > max_news_articles:
                output += f"*Showing {max_news_articles} of {len(source_findings)} articles*\n"
                source_findings = source_findings[:max_news_articles]

            for finding in source_findings:
                # Rich formatting for GDELT news articles
                if source_name == "gdelt" and finding.sources:
                    article_data = finding.sources[0].data
                    title = finding.content
                    url = article_data.get("url", "")
                    domain = article_data.get("domain", "")
                    language = article_data.get("language", "")
                    seendate = article_data.get("seendate", "")

                    # Format date if available (e.g., "20251213T091500Z" -> "2025-12-13")
                    date_str = ""
                    if seendate and len(seendate) >= 8:
                        date_str = f"{seendate[:4]}-{seendate[4:6]}-{seendate[6:8]}"

                    # Build rich article entry
                    is_non_english = language and language.lower() != "english"
                    lang_tag = f" [{language}]" if is_non_english else ""
                    output += f"\n**{title}**{lang_tag}\n"
                    if domain:
                        output += f"  Source: {domain}"
                        if date_str:
                            output += f" ({date_str})"
                        output += "\n"
                    if url:
                        output += f"  URL: {url}\n"
                else:
                    # Standard formatting for other sources
                    output += f"- {finding.content}\n"
                    if finding.corroboration_note:
                        output += f"  {finding.corroboration_note}\n"

    # If no findings, note that
    if not result.findings:
        output += "\nNo findings retrieved from available sources.\n"

    # Extract full article content for GDELT findings
    if "gdelt" in findings_by_source and findings_by_source["gdelt"]:
        gdelt_findings = findings_by_source["gdelt"]
        # Build article list from finding data for extraction
        articles_to_extract = []
        for finding in gdelt_findings[:5]:  # Extract up to 5 articles
            if finding.sources:
                article_data = finding.sources[0].data
                if article_data.get("url"):
                    articles_to_extract.append(article_data)

        if articles_to_extract:
            logger.info(f"Extracting {len(articles_to_extract)} articles for deep dive...")
            extracts = await _auto_extract_articles(articles_to_extract, max_count=5)

            if extracts:
                output += "\n" + "=" * 55 + "\n"
                output += f"{'PRIMARY SOURCE EXTRACTS':^55}\n"
                output += "=" * 55 + "\n\n"

                for i, ext in enumerate(extracts, 1):
                    lang_val = ext.get("language", "")
                    lang = str(lang_val) if lang_val else ""
                    is_non_english = lang and lang.lower() != "english"
                    lang_tag = f" [{lang.upper()}]" if is_non_english else ""
                    output += f"### ARTICLE {i}{lang_tag}: {ext['title']}\n"
                    output += f"**Source:** {ext['domain']}\n"
                    output += f"**URL:** {ext['url']}\n\n"

                    content = ext.get("content")
                    if content:
                        output += content + "\n"
                    else:
                        output += f"*[Extraction failed: {ext.get('error', 'Unknown error')}]*\n"

                    output += "\n" + "-" * 55 + "\n\n"

    # Corroboration analysis
    output += _format_corroboration_section(result.findings)

    # Conflicts
    output += _format_conflicts_section(result.conflicts)

    # Unavailable sources
    output += _format_unavailable_sources_section(unavailable_sources)

    # Source attribution
    output += _format_source_attribution_section(result, timestamp)

    # Footer with confidence
    confidence_level = result.to_confidence_level().name
    output += _format_deep_dive_footer(confidence_level)

    # Add rigor mode enhancements
    if rigor_mode:
        timestamp_dt = datetime.now(timezone.utc)

        output += "\n" + "=" * 59 + "\n"
        output += "RIGOR MODE ANALYSIS\n"
        output += "=" * 59 + "\n\n"

        # Confidence statement in IC language
        output += "## Confidence Assessment\n\n"
        conf_level = result.to_confidence_level()
        output += (
            confidence_to_language(
                conf_level,
                f"the analysis of {topic} accurately represents current conditions",
            )
            + "\n\n"
        )

        # Build source metadata list
        sources: list[SourceMetadata] = []
        source_url_map = {
            "gdelt": "https://api.gdeltproject.org/",
            "worldbank": "https://api.worldbank.org/",
            "wikidata": "https://www.wikidata.org/",
            "opensky": "https://opensky-network.org/",
            "aisstream": "https://aisstream.io/",
        }
        for source_name in result.sources_queried:
            url = source_url_map.get(source_name.lower(), f"https://{source_name}.org/")
            sources.append(
                SourceMetadata(
                    source_name=source_name,
                    source_url=url,
                    retrieved_at=timestamp_dt,
                )
            )

        # Analytical caveats
        output += format_analytical_caveats(
            source_names=[s.lower() for s in result.sources_queried],
        )

        # Bibliography
        output += "\n"
        output += format_bibliography(sources)

    return output


@mcp.tool()
async def deep_dive(
    topic: str,
    focus: str | None = None,
    rigor: bool | None = None,
) -> str:
    """Comprehensive multi-source OSINT analysis.

    Queries all relevant data sources concurrently and correlates results
    to provide a complete picture of any topic, entity, or situation.

    Args:
        topic: The subject to analyze (country, person, organization, vessel, event)
        focus: Optional focus area to emphasize (e.g., "sanctions", "conflict", "economic")
        rigor: Enable rigor mode for IC-standard output with full source
            attribution, confidence levels, corroboration analysis, and
            bibliography. If not specified, uses global IGNIFER_RIGOR_MODE setting.

    Returns:
        Comprehensive intelligence report with:
        - Findings from all relevant sources
        - Source attribution for each finding
        - Corroboration notes where sources agree
        - Conflict notes where sources disagree
        - Overall confidence assessment
        In rigor mode, includes ICD 203 confidence language and full bibliography.

    Examples:
        deep_dive("Myanmar")  # Country analysis
        deep_dive("Roman Abramovich")  # Person analysis
        deep_dive("Iran", focus="sanctions")  # Focused analysis
        deep_dive("NS Champion")  # Vessel analysis
    """
    effective_rigor = resolve_rigor_mode(rigor)
    # Input validation
    if not topic or not topic.strip():
        return (
            "## Invalid Topic\n\n"
            "Please provide a topic to analyze.\n\n"
            "**Examples:**\n"
            '- deep_dive("Myanmar")\n'
            '- deep_dive("Roman Abramovich")\n'
            '- deep_dive("Iran", focus="sanctions")'
        )

    topic_cleaned = topic.strip()
    logger.info(f"Deep dive: topic={topic_cleaned}, focus={focus}, rigor={effective_rigor}")

    try:
        # Get relevance engine and analyze the topic
        relevance_engine = _get_relevance_engine()
        relevance_result = await relevance_engine.analyze(topic_cleaned)

        # Determine which sources to query based on relevance
        sources_to_query: list[str] = []
        unavailable_sources: list[tuple[str, str]] = []

        for source in relevance_result.sources:
            # Include HIGH or MEDIUM_HIGH relevance sources
            if source.score in (RelevanceScore.HIGH, RelevanceScore.MEDIUM_HIGH):
                if source.available:
                    sources_to_query.append(source.source_name)
                else:
                    unavailable_sources.append(
                        (source.source_name, source.unavailable_reason or "Not configured")
                    )

        # If focus is specified, boost focus-related sources
        if focus and focus.lower() in FOCUS_SOURCE_BOOST:
            focus_sources = FOCUS_SOURCE_BOOST[focus.lower()]
            for source_name in focus_sources:
                # Check if source is available
                source_info = next(
                    (s for s in relevance_result.sources if s.source_name == source_name), None
                )
                if source_info:
                    already_unavailable = source_name in [u[0] for u in unavailable_sources]
                    if source_info.available and source_name not in sources_to_query:
                        sources_to_query.append(source_name)
                    elif not source_info.available and not already_unavailable:
                        unavailable_sources.append(
                            (source_name, source_info.unavailable_reason or "Not configured")
                        )

        # If no sources selected, fall back to all available
        if not sources_to_query:
            sources_to_query = relevance_result.available_sources
            logger.debug("No high relevance sources, using all available")

        # Ensure at least some sources
        if not sources_to_query:
            return (
                f"## No Sources Available\n\n"
                f"No data sources are available to analyze **{topic_cleaned}**.\n\n"
                f"**Configure credentials for:**\n"
                + "\n".join(f"- {s[0]}: {s[1]}" for s in unavailable_sources)
            )

        logger.debug(f"Sources to query: {sources_to_query}")

        # Get correlator and aggregate results
        correlator = _get_correlator()
        result = await correlator.aggregate(topic_cleaned, sources_to_query)

        # Format and return output
        output = await _format_deep_dive_output(
            topic_cleaned,
            result,
            unavailable_sources,
            focus,
            rigor_mode=effective_rigor,
        )

        logger.info(f"Deep dive completed for: {topic_cleaned}")
        return output

    except AdapterTimeoutError as e:
        logger.warning(f"Timeout in deep dive for {topic_cleaned}: {e}")
        return (
            f"## Deep Dive Timed Out\n\n"
            f"The analysis for **{topic_cleaned}** timed out.\n\n"
            f"**Suggestions:**\n"
            f"- Try narrowing your topic\n"
            f"- Use a focus area to limit sources\n"
            f"- Try again in a moment"
        )

    except AdapterAuthError as e:
        logger.warning(f"Authentication error in deep dive: {e}")
        return (
            "## Authentication Error\n\n"
            "One or more data sources require authentication.\n\n"
            "Check your API credentials configuration."
        )

    except AdapterError as e:
        logger.error(f"Adapter error in deep dive for {topic_cleaned}: {e}")
        return (
            f"## Data Source Error\n\n"
            f"Error querying data sources for **{topic_cleaned}**.\n\n"
            f"**What happened:** {e.message}\n\n"
            f"**Suggestions:**\n"
            f"- Try again in a few moments\n"
            f"- Try a different topic or focus area"
        )

    except Exception as e:
        logger.exception(f"Unexpected error in deep dive for {topic_cleaned}: {e}")
        return (
            f"## Error\n\n"
            f"An unexpected error occurred while analyzing **{topic_cleaned}**.\n\n"
            f"Please try again later."
        )


def main() -> None:
    """Run the Ignifer MCP server."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Starting Ignifer MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
