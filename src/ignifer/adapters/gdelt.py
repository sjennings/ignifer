"""GDELT adapter for news and event data."""

import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from ignifer.adapters.base import AdapterParseError, AdapterTimeoutError
from ignifer.cache import CacheManager, cache_key
from ignifer.config import get_settings
from ignifer.models import (
    ConfidenceLevel,
    OSINTResult,
    QualityTier,
    QueryParams,
    ResultStatus,
    SourceAttribution,
    SourceMetadata,
)
from ignifer.timeparse import parse_time_range

logger = logging.getLogger(__name__)


def _sanitize_gdelt_query(query: str) -> str:
    """Sanitize query for GDELT API.

    GDELT treats hyphens as operators. Words containing hyphens must be quoted.
    For example: Japan-China -> "Japan-China"

    Args:
        query: Raw user query

    Returns:
        Sanitized query safe for GDELT API
    """
    import re

    # Find words containing hyphens that aren't already quoted
    # Match word-word patterns not inside quotes
    def quote_hyphenated(match: re.Match) -> str:
        word = match.group(0)
        # Don't re-quote if already quoted
        return f'"{word}"'

    # Pattern: word-word (hyphenated terms not already in quotes)
    # This regex finds hyphenated words
    sanitized = re.sub(r'\b\w+(?:-\w+)+\b', quote_hyphenated, query)

    return sanitized


class GDELTAdapter:
    """GDELT adapter for news and event data.

    GDELT (Global Database of Events, Language, and Tone) provides
    real-time monitoring of global news coverage. No API key required.

    Attributes:
        source_name: "gdelt"
        base_quality_tier: QualityTier.MEDIUM (reputable news sources)
    """

    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    DEFAULT_TIMEOUT = 30.0  # seconds (GDELT can be slow during high load)
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2.0  # seconds

    def __init__(self, cache: CacheManager | None = None) -> None:
        self._client: httpx.AsyncClient | None = None
        self._cache = cache

    @property
    def source_name(self) -> str:
        return "gdelt"

    @property
    def base_quality_tier(self) -> QualityTier:
        return QualityTier.MEDIUM

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.DEFAULT_TIMEOUT),
                headers={"User-Agent": "Ignifer/1.0"},
            )
        return self._client

    async def query(self, params: QueryParams) -> OSINTResult:
        """Query GDELT for articles matching the query.

        Args:
            params: Query parameters including query string.

        Returns:
            OSINTResult with articles or NO_DATA status.

        Raises:
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        # Generate cache key (include time_range to invalidate when parameters change)
        timespan = params.time_range or "1week"
        key = cache_key(self.source_name, "articles", search_query=f"{params.query}:{timespan}")

        # Check cache first
        if self._cache:
            cached = await self._cache.get(key)
            if cached and cached.data and not cached.is_stale:
                logger.debug(f"Cache hit for {key}")
                # Reconstruct OSINTResult from cached data
                cached_results = cached.data.get("articles", [])
                retrieved_at = datetime.now(timezone.utc)
                return OSINTResult(
                    status=ResultStatus.SUCCESS,
                    query=params.query,
                    results=cached_results,
                    sources=[
                        SourceAttribution(
                            source=self.source_name,
                            quality=self.base_quality_tier,
                            confidence=ConfidenceLevel.LIKELY,
                            metadata=SourceMetadata(
                                source_name=self.source_name,
                                source_url=self.BASE_URL,
                                retrieved_at=retrieved_at,
                            ),
                        )
                    ],
                    retrieved_at=retrieved_at,
                )

        # Parse time range if provided
        time_result = parse_time_range(params.time_range) if params.time_range else None

        # Build request URL
        # TIMESPAN limits to recent articles; GDELT defaults to 3 months by relevance
        # "sort:datedesc" sorts newest first within the timespan
        sanitized_query = _sanitize_gdelt_query(params.query)
        query_params = {
            "query": sanitized_query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": 75,
            "sort": "datedesc",
        }

        # Add time parameters based on parse result
        if time_result and time_result.gdelt_timespan:
            query_params["timespan"] = time_result.gdelt_timespan
        elif time_result and time_result.start_datetime:
            query_params["startdatetime"] = time_result.start_datetime
            if time_result.end_datetime:
                query_params["enddatetime"] = time_result.end_datetime
        else:
            query_params["timespan"] = "1week"  # Default

        url = f"{self.BASE_URL}?{urlencode(query_params)}"

        client = await self._get_client()
        logger.info(f"Querying GDELT: {params.query}")

        # Retry loop with exponential backoff for rate limiting
        last_error: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await client.get(url)

                # Handle rate limiting with retry
                if response.status_code == 429:
                    delay = self.RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        f"GDELT rate limited (429), retry {attempt + 1}/{self.MAX_RETRIES} "
                        f"after {delay}s"
                    )
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()
                break  # Success

            except httpx.TimeoutException as e:
                logger.warning(f"GDELT timeout for query: {params.query}")
                raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    delay = self.RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        f"GDELT rate limited (429), retry {attempt + 1}/{self.MAX_RETRIES} "
                        f"after {delay}s"
                    )
                    last_error = e
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"GDELT HTTP error: {e}")
                raise AdapterParseError(self.source_name, str(e)) from e

            except httpx.HTTPError as e:
                logger.error(f"GDELT HTTP error: {e}")
                raise AdapterParseError(self.source_name, str(e)) from e
        else:
            # All retries exhausted
            logger.error(f"GDELT rate limit exceeded after {self.MAX_RETRIES} retries")
            raise AdapterParseError(
                self.source_name,
                f"Rate limited by GDELT API after {self.MAX_RETRIES} retries. "
                "Please wait a moment before trying again.",
            ) from last_error

        # Parse response
        try:
            data = response.json()
        except Exception as e:
            raise AdapterParseError(self.source_name, "Invalid JSON response") from e

        # Check for empty results
        articles = data.get("articles", [])
        if not articles:
            logger.info(f"No GDELT results for: {params.query}")
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=params.query,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error="No articles found. Try broader search terms or different keywords.",
            )

        # Build successful result
        retrieved_at = datetime.now(timezone.utc)

        # Cache the result
        if self._cache:
            settings = get_settings()
            await self._cache.set(
                key=key,
                data={"articles": articles},
                ttl_seconds=settings.ttl_gdelt,
                source=self.source_name,
            )

        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=params.query,
            results=articles,
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=url,
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    async def health_check(self) -> bool:
        """Check if GDELT API is reachable.

        Returns:
            True if API responds, False otherwise.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.BASE_URL}?query=test&mode=ArtList&format=json&maxrecords=1"
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"GDELT health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("GDELT adapter client closed")
