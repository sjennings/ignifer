"""ACLED adapter for conflict event data.

ACLED (Armed Conflict Location & Event Data) provides comprehensive
conflict event data compiled from reports and local sources.

API Reference: https://acleddata.com/resources/api-documentation/

Authentication:
    ACLED uses OAuth2 password grant flow. Users authenticate with their
    email and password to obtain time-limited access tokens.
    See: https://acleddata.com/api-documentation/getting-started
"""

import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

# OAuth2 token endpoint
ACLED_TOKEN_URL = "https://acleddata.com/oauth/token"

from ignifer.adapters.base import AdapterAuthError, AdapterParseError, AdapterTimeoutError
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

logger = logging.getLogger(__name__)

# Regex patterns for date range parsing
LAST_N_PATTERN = re.compile(
    r"last\s+(\d+)\s+(day|days|week|weeks|month|months)",
    re.IGNORECASE
)


class ACLEDAdapter:
    """ACLED adapter for conflict event data.

    Provides access to conflict event data including battles, violence
    against civilians, protests, and strategic developments.
    Requires registration at https://acleddata.com/register/

    Authentication uses OAuth2 password grant flow:
    - Tokens are valid for 24 hours
    - Refresh tokens are valid for 14 days

    Attributes:
        source_name: "acled"
        base_quality_tier: QualityTier.HIGH (academic research quality)
    """

    BASE_URL = "https://api.acleddata.com/acled/read"
    DEFAULT_TIMEOUT = 15.0  # seconds
    DEFAULT_LIMIT = 500  # Default number of events to fetch
    TOKEN_REFRESH_MARGIN = 300  # Refresh token 5 minutes before expiry

    def __init__(self, cache: CacheManager | None = None) -> None:
        """Initialize the ACLED adapter.

        Args:
            cache: Optional cache manager for caching results.
        """
        self._client: httpx.AsyncClient | None = None
        self._cache = cache
        # OAuth2 token management
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        return "acled"

    @property
    def base_quality_tier(self) -> QualityTier:
        """Default quality tier for this source's data."""
        return QualityTier.HIGH

    def _get_credentials(self) -> tuple[str, str] | None:
        """Get email and password from settings.

        Returns:
            Tuple of (email, password), or None if not configured.
        """
        settings = get_settings()
        if not settings.has_acled_credentials():
            return None
        return (
            settings.acled_email.get_secret_value(),  # type: ignore[union-attr]
            settings.acled_password.get_secret_value(),  # type: ignore[union-attr]
        )

    async def _get_access_token(self) -> str:
        """Get a valid OAuth2 access token, refreshing if necessary.

        Uses the OAuth2 password grant flow to obtain tokens.

        Returns:
            Valid access token string.

        Raises:
            AdapterAuthError: If authentication fails or credentials are missing.
        """
        # Check if we have a valid cached token
        if self._access_token and self._token_expires_at:
            now = datetime.now(timezone.utc)
            if now < self._token_expires_at - timedelta(seconds=self.TOKEN_REFRESH_MARGIN):
                return self._access_token

        # Get credentials
        credentials = self._get_credentials()
        if credentials is None:
            raise AdapterAuthError(
                self.source_name,
                "ACLED credentials not configured"
            )
        email, password = credentials

        # Request new token using password grant
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as token_client:
                response = await token_client.post(
                    ACLED_TOKEN_URL,
                    data={
                        "grant_type": "password",
                        "username": email,
                        "password": password,
                        "client_id": "acled",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                if response.status_code != 200:
                    error_detail = "Invalid credentials or token request failed"
                    try:
                        error_data = response.json()
                        if "error_description" in error_data:
                            error_detail = error_data["error_description"]
                        elif "error" in error_data:
                            error_detail = error_data["error"]
                    except Exception:
                        pass
                    raise AdapterAuthError(self.source_name, error_detail)

                token_data = response.json()
                self._access_token = token_data["access_token"]

                # Token expires_in is in seconds (typically 24 hours = 86400)
                expires_in = token_data.get("expires_in", 86400)
                self._token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=expires_in
                )

                logger.debug(f"ACLED token obtained, expires in {expires_in}s")
                return self._access_token

        except httpx.HTTPError as e:
            raise AdapterAuthError(
                self.source_name, f"Token request failed: {e}"
            ) from e

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.DEFAULT_TIMEOUT),
                headers={"User-Agent": "Ignifer/1.0"},
            )
        return self._client

    def _parse_date_range(self, date_range: str) -> tuple[str, str] | None:
        """Parse date range string to ACLED date format.

        ACLED expects dates in YYYY-MM-DD|YYYY-MM-DD format.

        Args:
            date_range: Natural language date range like "last 30 days".

        Returns:
            Tuple of (start_date, end_date) in YYYY-MM-DD format, or None if parsing fails.
        """
        date_range = date_range.strip().lower()
        now = datetime.now(timezone.utc)
        end_date = now.strftime("%Y-%m-%d")

        # Handle "last N days/weeks/months"
        match = LAST_N_PATTERN.match(date_range)
        if match:
            n = int(match.group(1))
            unit = match.group(2).lower()

            if unit in ("day", "days"):
                start = now - timedelta(days=n)
            elif unit in ("week", "weeks"):
                start = now - timedelta(weeks=n)
            elif unit in ("month", "months"):
                start = now - timedelta(days=n * 30)  # Approximate
            else:
                return None

            return (start.strftime("%Y-%m-%d"), end_date)

        # Handle explicit date range "YYYY-MM-DD to YYYY-MM-DD"
        date_range_match = re.match(
            r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})",
            date_range,
            re.IGNORECASE
        )
        if date_range_match:
            return (date_range_match.group(1), date_range_match.group(2))

        return None

    def _calculate_previous_period(
        self, start_date: str, end_date: str
    ) -> tuple[str, str] | None:
        """Calculate the previous period of the same duration.

        Args:
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.

        Returns:
            Tuple of (prev_start, prev_end) in YYYY-MM-DD format, or None if calculation fails.
        """
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            duration = end - start

            # Previous period ends the day before current period starts
            prev_end = start - timedelta(days=1)
            prev_start = prev_end - duration

            return (prev_start.strftime("%Y-%m-%d"), prev_end.strftime("%Y-%m-%d"))
        except (ValueError, TypeError):
            return None

    def _calculate_trend(self, current: int, previous: int) -> str:
        """Calculate trend direction based on current and previous values.

        Args:
            current: Current period value.
            previous: Previous period value.

        Returns:
            "increasing", "decreasing", or "stable".
        """
        if previous == 0:
            return "increasing" if current > 0 else "stable"

        # Calculate percentage change
        change_pct = ((current - previous) / previous) * 100

        # Use 10% threshold for significant change
        if change_pct > 10:
            return "increasing"
        elif change_pct < -10:
            return "decreasing"
        else:
            return "stable"

    async def _fetch_events_for_period(
        self,
        country: str,
        date_range: str,
        access_token: str,
    ) -> list[dict[str, Any]] | None:
        """Fetch raw events for a specific period (for trend comparison).

        Args:
            country: Country name.
            date_range: Date range in YYYY-MM-DD|YYYY-MM-DD format.
            access_token: OAuth2 access token.

        Returns:
            List of events, or None if request fails.
        """
        try:
            query_params: dict[str, str | int] = {
                "country": country,
                "limit": self.DEFAULT_LIMIT,
                "event_date": date_range,
                "event_date_where": "BETWEEN",
            }
            url = f"{self.BASE_URL}?{urlencode(query_params)}"

            client = await self._get_client()
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                return None

            data = response.json()
            if not data.get("success", True):
                return None

            events: list[dict[str, Any]] = data.get("data", [])
            return events
        except Exception as e:
            logger.debug(f"Failed to fetch previous period events: {e}")
            return None

    def _calculate_period_stats(
        self, events: list[dict[str, Any]]
    ) -> tuple[int, int]:
        """Calculate event count and fatality count from events.

        Args:
            events: List of raw events.

        Returns:
            Tuple of (event_count, fatality_count).
        """
        event_count = len(events)
        fatality_count = 0
        for event in events:
            fatalities = event.get("fatalities")
            if fatalities and isinstance(fatalities, (int, float)):
                fatality_count += int(fatalities)
        return event_count, fatality_count

    def _normalize_event(self, event: dict[str, Any]) -> dict[str, str | int | float | bool | None]:
        """Normalize ACLED event to flat dict structure.

        Args:
            event: Raw event from ACLED API.

        Returns:
            Flattened event dict with scalar values only.
        """
        return {
            "event_id": event.get("data_id"),
            "event_date": event.get("event_date"),
            "year": event.get("year"),
            "event_type": event.get("event_type"),
            "sub_event_type": event.get("sub_event_type"),
            "actor1": event.get("actor1"),
            "actor2": event.get("actor2"),
            "country": event.get("country"),
            "admin1": event.get("admin1"),
            "admin2": event.get("admin2"),
            "location": event.get("location"),
            "latitude": event.get("latitude"),
            "longitude": event.get("longitude"),
            "fatalities": event.get("fatalities"),
            "notes": event.get("notes"),
            "source": event.get("source"),
            "source_scale": event.get("source_scale"),
        }

    def _build_summary(
        self,
        events: list[dict[str, Any]],
        country: str,
        date_range_start: str | None,
        date_range_end: str | None,
    ) -> dict[str, str | int | float | bool | None]:
        """Build summary statistics from events.

        Args:
            events: List of raw events from ACLED API.
            country: The queried country.
            date_range_start: Start date of the query.
            date_range_end: End date of the query.

        Returns:
            Summary dict with aggregated statistics.
        """
        # Count event types
        event_types: Counter[str] = Counter()
        actors: Counter[str] = Counter()
        regions: Counter[str] = Counter()
        total_fatalities = 0

        for event in events:
            event_type = event.get("event_type", "Unknown")
            event_types[event_type] += 1

            actor1 = event.get("actor1")
            actor2 = event.get("actor2")
            if actor1:
                actors[actor1] += 1
            if actor2:
                actors[actor2] += 1

            admin1 = event.get("admin1")
            if admin1:
                regions[admin1] += 1

            fatalities = event.get("fatalities")
            if fatalities and isinstance(fatalities, (int, float)):
                total_fatalities += int(fatalities)

        # Build summary with flattened structure
        summary: dict[str, str | int | float | bool | None] = {
            "summary_type": "conflict_analysis",
            "country": country,
            "total_events": len(events),
            "total_fatalities": total_fatalities,
            "date_range_start": date_range_start,
            "date_range_end": date_range_end,
        }

        # Add event type breakdown (flattened)
        for event_type, count in event_types.most_common(10):
            safe_key = event_type.lower().replace(" ", "_").replace("/", "_")
            summary[f"event_type_{safe_key}"] = count

        # Add top actors (flattened)
        top_actors = actors.most_common(5)
        for i, (actor, count) in enumerate(top_actors):
            summary[f"top_actor_{i+1}_name"] = actor
            summary[f"top_actor_{i+1}_count"] = count

        # Add affected regions with counts (flattened, like actors)
        top_regions = regions.most_common(10)
        for i, (region, count) in enumerate(top_regions):
            summary[f"top_region_{i+1}_name"] = region
            summary[f"top_region_{i+1}_count"] = count

        # Keep comma-separated list for backward compatibility
        region_names = [r for r, _ in top_regions]
        summary["affected_regions"] = ", ".join(region_names) if region_names else None

        return summary

    async def query(self, params: QueryParams) -> OSINTResult:
        """Query ACLED for conflict events.

        The query string should contain a country name or region.
        Use time_range parameter for date filtering.

        Args:
            params: Query parameters with country/region in query field.

        Returns:
            OSINTResult with conflict event summary and attribution.

        Raises:
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        # Check credentials first - return helpful error if missing
        credentials = self._get_credentials()
        if credentials is None:
            settings = get_settings()
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=params.query,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error=settings.get_credential_error_message("acled"),
            )

        country = params.query.strip()

        # Parse date range if provided
        date_range_parsed = None
        if params.time_range:
            date_range_parsed = self._parse_date_range(params.time_range)

        return await self.get_events(
            country=country,
            date_range=f"{date_range_parsed[0]}|{date_range_parsed[1]}" if date_range_parsed else None,
        )

    async def get_events(
        self,
        country: str,
        date_range: str | None = None,
    ) -> OSINTResult:
        """Get conflict events for a specific country.

        Args:
            country: Country name or ISO code.
            date_range: Optional date range in "YYYY-MM-DD|YYYY-MM-DD" format
                       or natural language like "last 30 days".

        Returns:
            OSINTResult with conflict event data.

        Raises:
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        # Check credentials first
        credentials = self._get_credentials()
        if credentials is None:
            settings = get_settings()
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=country,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error=settings.get_credential_error_message("acled"),
            )

        # Get OAuth2 access token
        try:
            access_token = await self._get_access_token()
        except AdapterAuthError:
            raise

        # Parse date range if natural language
        date_range_start: str | None = None
        date_range_end: str | None = None

        if date_range:
            if "|" in date_range:
                # Already in ACLED format
                parts = date_range.split("|")
                if len(parts) == 2:
                    date_range_start, date_range_end = parts
            else:
                # Try to parse natural language
                parsed = self._parse_date_range(date_range)
                if parsed:
                    date_range_start, date_range_end = parsed
                    date_range = f"{date_range_start}|{date_range_end}"

        # Generate cache key
        key = cache_key(
            self.source_name,
            "events",
            country=country,
            date_range=date_range or "default"
        )

        # Check cache first
        if self._cache:
            cached = await self._cache.get(key)
            if cached and cached.data and not cached.is_stale:
                logger.debug(f"Cache hit for {key}")
                return self._build_result_from_cache(country, cached.data)

        # Build request URL (no credentials in query params - use Bearer token)
        query_params: dict[str, str | int] = {
            "country": country,
            "limit": self.DEFAULT_LIMIT,
        }

        if date_range and "|" in date_range:
            query_params["event_date"] = date_range
            query_params["event_date_where"] = "BETWEEN"

        url = f"{self.BASE_URL}?{urlencode(query_params)}"

        client = await self._get_client()
        logger.info(f"Querying ACLED for country: {country}")

        try:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            # Handle authentication errors
            if response.status_code in (401, 403):
                raise AdapterAuthError(self.source_name, "Invalid or expired token")

            # Handle rate limiting
            if response.status_code == 429:
                logger.warning("ACLED rate limited")
                return OSINTResult(
                    status=ResultStatus.RATE_LIMITED,
                    query=country,
                    results=[],
                    sources=[],
                    retrieved_at=datetime.now(timezone.utc),
                )

            response.raise_for_status()

        except httpx.TimeoutException as e:
            logger.warning(f"ACLED timeout for query: {country}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                raise AdapterAuthError(self.source_name, "Invalid or expired token") from e
            if e.response.status_code == 429:
                return OSINTResult(
                    status=ResultStatus.RATE_LIMITED,
                    query=country,
                    results=[],
                    sources=[],
                    retrieved_at=datetime.now(timezone.utc),
                )
            logger.error(f"ACLED HTTP error: {e}")
            raise AdapterParseError(self.source_name, str(e)) from e

        except httpx.HTTPError as e:
            logger.error(f"ACLED HTTP error: {e}")
            raise AdapterParseError(self.source_name, str(e)) from e

        # Parse response
        try:
            data = response.json()
        except Exception as e:
            raise AdapterParseError(self.source_name, "Invalid JSON response") from e

        # Check for API-level success
        if not data.get("success", True):
            error_msg = data.get("error", "Unknown API error")
            logger.error(f"ACLED API error: {error_msg}")
            raise AdapterParseError(self.source_name, f"API error: {error_msg}")

        # Get events data
        events = data.get("data", [])
        if not events:
            logger.info(f"No ACLED events found for: {country}")
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=country,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error=(
                    f"No conflict events found for '{country}'. "
                    "This may indicate peaceful conditions or limited data coverage for this region."
                ),
            )

        # Build summary and normalize events
        summary = self._build_summary(events, country, date_range_start, date_range_end)
        normalized_events = [self._normalize_event(event) for event in events[:20]]  # Top 20 events

        # Calculate trend comparison if date range is specified (best-effort)
        if date_range_start and date_range_end:
            previous_period = self._calculate_previous_period(date_range_start, date_range_end)
            if previous_period:
                prev_start, prev_end = previous_period
                prev_date_range = f"{prev_start}|{prev_end}"
                prev_events = await self._fetch_events_for_period(
                    country, prev_date_range, access_token
                )
                if prev_events is not None:
                    # Calculate stats for both periods
                    current_event_count, current_fatalities = self._calculate_period_stats(events)
                    prev_event_count, prev_fatalities = self._calculate_period_stats(prev_events)

                    # Add trend fields to summary
                    summary["event_trend"] = self._calculate_trend(current_event_count, prev_event_count)
                    summary["fatality_trend"] = self._calculate_trend(current_fatalities, prev_fatalities)
                    summary["previous_period_start"] = prev_start
                    summary["previous_period_end"] = prev_end
                    summary["previous_period_events"] = prev_event_count
                    summary["previous_period_fatalities"] = prev_fatalities

        # Combine summary with sample events
        results: list[dict[str, str | int | float | bool | None]] = [summary]
        results.extend(normalized_events)

        # Cache results
        if self._cache:
            settings = get_settings()
            await self._cache.set(
                key=key,
                data={
                    "summary": summary,
                    "events": normalized_events,
                    "country": country,
                    "date_range_start": date_range_start,
                    "date_range_end": date_range_end,
                },
                ttl_seconds=settings.ttl_acled,
                source=self.source_name,
            )

        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=country,
            results=results,
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.VERY_LIKELY,  # Academic research quality
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=self.BASE_URL,
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    def _build_result_from_cache(
        self, query: str, cached_data: dict[str, Any]
    ) -> OSINTResult:
        """Build OSINTResult from cached data."""
        summary = cached_data.get("summary", {})
        events = cached_data.get("events", [])

        results: list[dict[str, str | int | float | bool | None]] = []
        if summary:
            results.append(summary)
        results.extend(events)

        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=query,
            results=results,
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.VERY_LIKELY,
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=self.BASE_URL,
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    async def health_check(self) -> bool:
        """Check if ACLED API is reachable and credentials are valid.

        Returns:
            True if API responds and credentials are valid, False otherwise.
        """
        try:
            credentials = self._get_credentials()
            if credentials is None:
                logger.warning("ACLED health check failed: No credentials configured")
                return False

            # Try to get an OAuth2 token - this validates credentials
            try:
                access_token = await self._get_access_token()
            except AdapterAuthError as e:
                logger.warning(f"ACLED health check failed: {e}")
                return False

            client = await self._get_client()
            # Make a minimal query to test connectivity
            query_params = {
                "limit": 1,
                "country": "Norway",  # Use a country with typically few events
            }
            url = f"{self.BASE_URL}?{urlencode(query_params)}"

            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code in (401, 403):
                logger.warning("ACLED health check failed: Invalid or expired token")
                return False

            return response.status_code == 200

        except Exception as e:
            logger.warning(f"ACLED health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("ACLED adapter client closed")


__all__ = ["ACLEDAdapter"]
