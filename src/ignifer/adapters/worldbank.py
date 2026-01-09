"""World Bank adapter for economic indicators."""

import logging
from datetime import datetime, timezone
from typing import Any

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

logger = logging.getLogger(__name__)


# Indicator code mapping
INDICATOR_CODES: dict[str, str] = {
    "gdp": "NY.GDP.MKTP.CD",
    "gdp per capita": "NY.GDP.PCAP.CD",
    "inflation": "FP.CPI.TOTL.ZG",
    "population": "SP.POP.TOTL",
    "trade": "NE.RSB.GNFS.CD",
    "trade balance": "NE.RSB.GNFS.CD",
    "unemployment": "SL.UEM.TOTL.ZS",
}

# Common aliases not in World Bank data (lowercase keys)
COUNTRY_ALIASES: dict[str, str] = {
    "usa": "USA",
    "us": "USA",
    "america": "USA",
    "uk": "GBR",
    "britain": "GBR",
    "prc": "CHN",
    "eu": "EUU",
    "ssa": "SSF",
}


class WorldBankAdapter:
    """World Bank adapter for economic indicator data.

    Provides access to GDP, inflation, trade, and other economic indicators
    from the World Bank Open Data API. No API key required.

    Attributes:
        source_name: "worldbank"
        base_quality_tier: QualityTier.HIGH (official government data)
    """

    BASE_URL = "https://api.worldbank.org/v2"
    DEFAULT_TIMEOUT = 15.0  # seconds

    def __init__(self, cache: CacheManager | None = None) -> None:
        """Initialize the World Bank adapter.

        Args:
            cache: Optional cache manager for caching results.
        """
        self._client: httpx.AsyncClient | None = None
        self._cache = cache
        self._country_lookup: dict[str, str] | None = None

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        return "worldbank"

    @property
    def base_quality_tier(self) -> QualityTier:
        """Default quality tier for this source's data."""
        return QualityTier.HIGH

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.DEFAULT_TIMEOUT),
                headers={"User-Agent": "Ignifer/1.0"},
            )
        return self._client

    async def _ensure_country_lookup(self) -> dict[str, str]:
        """Fetch and cache country lookup from World Bank API.

        Returns:
            Dictionary mapping country names/codes (lowercase) to ISO3 codes.
        """
        if self._country_lookup is not None:
            return self._country_lookup

        # Build lookup starting with hardcoded aliases
        lookup: dict[str, str] = dict(COUNTRY_ALIASES)

        try:
            client = await self._get_client()
            # Fetch all countries from World Bank
            url = f"{self.BASE_URL}/country?format=json&per_page=400"
            response = await client.get(url)
            response.raise_for_status()

            data = response.json()
            if isinstance(data, list) and len(data) >= 2 and data[1]:
                for country in data[1]:
                    iso3 = country.get("id", "").upper()
                    if not iso3:
                        continue

                    # Map country name -> ISO3
                    name = country.get("name", "")
                    if name:
                        lookup[name.lower()] = iso3

                    # Map ISO2 -> ISO3
                    iso2 = country.get("iso2Code", "")
                    if iso2:
                        lookup[iso2.lower()] = iso3

                    # Map ISO3 -> ISO3 (for direct code usage)
                    lookup[iso3.lower()] = iso3

                logger.info(f"Loaded {len(data[1])} countries from World Bank API")

        except Exception as e:
            logger.warning(f"Failed to fetch country list from World Bank: {e}")
            # Fall back to aliases only - don't fail completely

        self._country_lookup = lookup
        return lookup

    def _parse_query(
        self, query: str, country_lookup: dict[str, str]
    ) -> tuple[str | None, str | None]:
        """Parse query string to extract indicator and country.

        Args:
            query: Natural language query like "GDP United States"
            country_lookup: Dictionary mapping country names/codes to ISO3 codes

        Returns:
            Tuple of (indicator_code, country_code) or (None, None) if not parseable
        """
        query_lower = query.lower()

        # Find indicator (check longer phrases first)
        indicator_code = None
        for indicator_name in sorted(INDICATOR_CODES.keys(), key=len, reverse=True):
            if indicator_name in query_lower:
                indicator_code = INDICATOR_CODES[indicator_name]
                break

        # Find country (check longer phrases first for multi-word names)
        country_code = None
        for name in sorted(country_lookup.keys(), key=len, reverse=True):
            if name in query_lower:
                country_code = country_lookup[name]
                break

        return indicator_code, country_code

    async def query(self, params: QueryParams) -> OSINTResult:
        """Query World Bank for economic indicators.

        Args:
            params: Query parameters including query string.

        Returns:
            OSINTResult with indicator data or NO_DATA status.

        Raises:
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        # Ensure country lookup is loaded
        country_lookup = await self._ensure_country_lookup()
        indicator_code, country_code = self._parse_query(params.query, country_lookup)

        if not indicator_code or not country_code:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=params.query,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error="Could not parse indicator or country from query. "
                "Try: 'GDP United States' or 'inflation Germany'",
            )

        # Generate cache key
        key = cache_key(
            self.source_name, "indicator", indicator=indicator_code, country=country_code
        )

        # Check cache
        if self._cache:
            cached = await self._cache.get(key)
            if cached and cached.data and not cached.is_stale:
                logger.debug(f"Cache hit for {key}")
                return self._build_result_from_cache(
                    params.query, cached.data, indicator_code, country_code
                )

        # Build API URL
        url = (
            f"{self.BASE_URL}/country/{country_code}/indicator/{indicator_code}"
            f"?format=json&per_page=10&date=2019:2024"
        )

        client = await self._get_client()
        logger.info(f"Querying World Bank: {indicator_code} for {country_code}")

        try:
            response = await client.get(url)

            if response.status_code == 429:
                logger.warning("World Bank rate limited")
                return OSINTResult(
                    status=ResultStatus.RATE_LIMITED,
                    query=params.query,
                    results=[],
                    sources=[],
                    retrieved_at=datetime.now(timezone.utc),
                )

            response.raise_for_status()

        except httpx.TimeoutException as e:
            logger.warning(f"World Bank timeout: {e}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e

        except httpx.HTTPError as e:
            logger.error(f"World Bank HTTP error: {e}")
            raise AdapterParseError(self.source_name, str(e)) from e

        # Parse response
        try:
            data = response.json()
        except Exception as e:
            raise AdapterParseError(self.source_name, "Invalid JSON response") from e

        # World Bank returns [metadata, data] array
        if not isinstance(data, list) or len(data) < 2:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=params.query,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error="No data available for this indicator/country combination.",
            )

        records = data[1]
        if not records:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=params.query,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error="No data available for this indicator/country combination.",
            )

        # Normalize results
        results: list[dict[str, str | int | float | bool | None]] = []
        for record in records:
            if record.get("value") is not None:
                results.append({
                    "indicator": record.get("indicator", {}).get("value", ""),
                    "country": record.get("country", {}).get("value", ""),
                    "year": record.get("date", ""),
                    "value": record.get("value"),
                })

        # Cache results
        if self._cache and results:
            settings = get_settings()
            await self._cache.set(
                key=key,
                data={
                    "results": results,
                    "indicator": indicator_code,
                    "country": country_code,
                },
                ttl_seconds=settings.ttl_worldbank,
                source=self.source_name,
            )

        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=params.query,
            results=results,
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,  # Official data
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=url,
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    def _build_result_from_cache(
        self,
        query: str,
        cached_data: dict[str, Any],
        indicator: str,
        country: str,
    ) -> OSINTResult:
        """Build OSINTResult from cached data."""
        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=query,
            results=cached_data.get("results", []),
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=f"{self.BASE_URL}/country/{country}/indicator/{indicator}",
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    async def health_check(self) -> bool:
        """Check if World Bank API is reachable.

        Returns:
            True if API responds, False otherwise.
        """
        try:
            client = await self._get_client()
            # Simple query to test connectivity
            response = await client.get(
                f"{self.BASE_URL}/country/USA/indicator/NY.GDP.MKTP.CD"
                f"?format=json&per_page=1"
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"World Bank health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("World Bank adapter client closed")
