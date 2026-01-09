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
    AdapterError,
    AdapterTimeoutError,
    GDELTAdapter,
    WikidataAdapter,
    WorldBankAdapter,
)
from ignifer.cache import CacheManager
from ignifer.config import configure_logging, get_settings
from ignifer.models import QueryParams, ResultStatus
from ignifer.output import OutputFormatter
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
_formatter: OutputFormatter | None = None


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


def _get_formatter() -> OutputFormatter:
    global _formatter
    if _formatter is None:
        _formatter = OutputFormatter()
    return _formatter


async def _cleanup_resources() -> None:
    """Close all open resources (adapters, cache connections)."""
    global _adapter, _worldbank, _wikidata, _cache

    # Close adapters first, then cache (adapters may use cache)
    adapters = [(_adapter, "_adapter"), (_worldbank, "_worldbank"), (_wikidata, "_wikidata")]
    for adapter, name in adapters:
        if adapter is not None:
            await adapter.close()
            globals()[name] = None

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
        "url": url, "language": language, "content": None, "error": None
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
            selected.append({
                "url": url, "language": lang,
                "title": article.get("title", ""), "domain": domain
            })
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
            selected.append({
                "url": url, "language": lang,
                "title": article.get("title", ""), "domain": domain
            })
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
            extracted.append({
                "url": selected[i]["url"],
                "title": selected[i]["title"],
                "language": selected[i].get("language", ""),
                "domain": selected[i]["domain"],
                "content": None,
                "error": str(res)[:50],
            })
        else:
            # res is dict[str, str | None] at this point
            res_dict: dict[str, str | None] = res
            extracted.append({
                "url": selected[i]["url"],
                "title": selected[i]["title"],
                "language": selected[i].get("language", ""),
                "domain": selected[i]["domain"],
                "content": res_dict.get("content"),
                "error": res_dict.get("error"),
            })

    return extracted


@mcp.tool()
async def briefing(topic: str, time_range: str | None = None) -> str:
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

    Returns:
        Full briefing + article extracts. Include ALL of it in Part 2.
    """
    logger.info(f"Briefing requested for topic: {topic}, time_range: {time_range}")

    # Validate time_range if provided
    if time_range:
        time_result = parse_time_range(time_range)
        if not time_result.is_valid:
            logger.warning(f"Invalid time range: {time_range} - {time_result.error}")
            return (
                f"## Invalid Time Range\n\n"
                f"Could not parse time range: **{time_range}**\n\n"
                f"**Supported formats:**\n"
                f"- \"last 24 hours\", \"last 48 hours\"\n"
                f"- \"last 7 days\", \"last 30 days\"\n"
                f"- \"this week\", \"last week\"\n"
                f"- \"2026-01-01 to 2026-01-08\" (ISO date range)\n\n"
                f"**Examples:**\n"
                f"- briefing(\"Syria\", time_range=\"last 48 hours\")\n"
                f"- briefing(\"Ukraine\", time_range=\"last 7 days\")"
            )

    try:
        # Query the adapter
        adapter = _get_adapter()
        params = QueryParams(query=topic, time_range=time_range)
        result = await adapter.query(params)

        # Format the result with time_range
        formatter = _get_formatter()
        output = formatter.format(result, time_range=time_range)

        # Auto-extract top articles if we have results
        if result.results:
            logger.info(f"Auto-extracting {MAX_AUTO_EXTRACTS} articles...")
            extracts = await _auto_extract_articles(result.results, MAX_AUTO_EXTRACTS)

            if extracts:
                output += "\n\n"
                output += "═" * 55 + "\n"
                output += f"{'PRIMARY SOURCE EXTRACTS':^55}\n"
                output += "(MANDATORY - INCLUDE ALL ARTICLES BELOW)\n"
                output += "═" * 55 + "\n\n"

                for i, ext in enumerate(extracts, 1):
                    lang = ext.get("language", "")
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

                    output += "\n" + "─" * 55 + "\n\n"

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

        qid = search_result.results[0].get("qid")
        if not qid:
            return None

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
async def economic_context(country: str) -> str:
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

    Returns:
        Formatted economic analysis with source attribution.
    """
    logger.info(f"Economic context requested for: {country}")

    # Build flat list of all indicators for querying
    all_indicator_defs = (
        CORE_INDICATORS + E1_VULNERABILITY_INDICATORS +
        E2_TRADE_INDICATORS + E4_FINANCIAL_INDICATORS
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
                    result.results,
                    key=lambda x: str(x.get("year", "")),
                    reverse=True
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
        output += "\n" + "\u2500" * 59 + "\n"
        output += f"Sources: {', '.join(sources_used)}\n"
        retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        output += f"Retrieved: {retrieved_at}\n"
        output += "\u2550" * 59 + "\n"

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


def main() -> None:
    """Run the Ignifer MCP server."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Starting Ignifer MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
