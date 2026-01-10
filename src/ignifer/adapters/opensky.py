"""OpenSky Network adapter for live flight tracking data.

OpenSky Network provides real-time global air traffic data from a network
of ADS-B receivers. Authenticated requests have higher rate limits and
access to more data.

API Reference: https://openskynetwork.github.io/opensky-api/
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

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


class OpenSkyAdapter:
    """OpenSky Network adapter for live aircraft tracking.

    Provides access to real-time aircraft positions, state vectors,
    and flight track history. Requires authentication for full access.

    Attributes:
        source_name: "opensky"
        base_quality_tier: QualityTier.HIGH (ADS-B transponder data)
    """

    BASE_URL = "https://opensky-network.org"
    DEFAULT_TIMEOUT = 15.0  # seconds

    def __init__(self, cache: CacheManager | None = None) -> None:
        """Initialize the OpenSky adapter.

        Args:
            cache: Optional cache manager for caching results.
        """
        self._client: httpx.AsyncClient | None = None
        self._cache = cache

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        return "opensky"

    @property
    def base_quality_tier(self) -> QualityTier:
        """Default quality tier for this source's data."""
        return QualityTier.HIGH

    def _get_auth(self) -> tuple[str, str] | None:
        """Get Basic Auth credentials from settings.

        Returns:
            Tuple of (username, password) or None if not configured.
        """
        settings = get_settings()
        if not settings.has_opensky_credentials():
            return None

        # Use get_secret_value() to extract actual credential values
        username = settings.opensky_username.get_secret_value()  # type: ignore[union-attr]
        password = settings.opensky_password.get_secret_value()  # type: ignore[union-attr]
        return (username, password)

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client with Basic Auth.

        Raises:
            AdapterAuthError: If credentials are not configured.
        """
        if self._client is None:
            auth = self._get_auth()
            if auth is None:
                settings = get_settings()
                raise AdapterAuthError(
                    self.source_name, settings.get_credential_error_message("opensky")
                )

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.DEFAULT_TIMEOUT),
                headers={"User-Agent": "Ignifer/1.0"},
                auth=auth,
            )
        return self._client

    def _parse_state_vector(self, state: list[Any]) -> dict[str, Any]:
        """Parse OpenSky state vector array into named dict.

        OpenSky returns state vectors as arrays with fixed positions:
        [0] icao24, [1] callsign, [2] origin_country, [3] time_position,
        [4] last_contact, [5] longitude, [6] latitude, [7] baro_altitude,
        [8] on_ground, [9] velocity, [10] true_track, [11] vertical_rate,
        [12] sensors, [13] geo_altitude, [14] squawk, [15] spi, [16] position_source

        Args:
            state: Raw state vector array from OpenSky API

        Returns:
            Dictionary with named fields
        """
        return {
            "icao24": state[0],
            "callsign": (state[1] or "").strip(),
            "origin_country": state[2],
            "time_position": state[3],
            "last_contact": state[4],
            "longitude": state[5],
            "latitude": state[6],
            "altitude_barometric": state[7],
            "on_ground": state[8],
            "velocity": state[9],
            "heading": state[10],
            "vertical_rate": state[11],
            "altitude_geometric": state[13],
            "squawk": state[14],
        }

    def _parse_track_point(self, waypoint: list[Any]) -> dict[str, Any]:
        """Parse OpenSky track waypoint array into named dict.

        Track waypoints: [0] time, [1] latitude, [2] longitude, [3] baro_altitude,
        [4] true_track, [5] on_ground

        Args:
            waypoint: Raw waypoint array from OpenSky API

        Returns:
            Dictionary with named fields
        """
        return {
            "timestamp": waypoint[0],
            "latitude": waypoint[1],
            "longitude": waypoint[2],
            "altitude": waypoint[3],
            "heading": waypoint[4],
            "on_ground": waypoint[5],
        }

    async def query(self, params: QueryParams) -> OSINTResult:
        """Query OpenSky by callsign.

        Args:
            params: Query parameters with callsign in query field.

        Returns:
            OSINTResult with aircraft state vectors matching callsign.

        Raises:
            AdapterAuthError: If credentials not configured or invalid.
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        callsign = params.query.strip().upper()

        # Generate cache key
        key = cache_key(self.source_name, "callsign", callsign=callsign)

        # Check cache first
        if self._cache:
            cached = await self._cache.get(key)
            if cached and cached.data and not cached.is_stale:
                logger.debug(f"Cache hit for {key}")
                return self._build_result_from_cache(callsign, cached.data)

        client = await self._get_client()
        url = f"{self.BASE_URL}/api/states/all"
        logger.info(f"Querying OpenSky by callsign: {callsign}")

        try:
            response = await client.get(url)

            if response.status_code == 401:
                raise AdapterAuthError(self.source_name, "Invalid credentials")

            if response.status_code == 429:
                logger.warning("OpenSky rate limited")
                return OSINTResult(
                    status=ResultStatus.RATE_LIMITED,
                    query=callsign,
                    results=[],
                    sources=[],
                    retrieved_at=datetime.now(timezone.utc),
                )

            response.raise_for_status()

        except httpx.TimeoutException as e:
            logger.warning(f"OpenSky timeout: {e}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AdapterAuthError(self.source_name, "Invalid credentials") from e
            if e.response.status_code == 429:
                return OSINTResult(
                    status=ResultStatus.RATE_LIMITED,
                    query=callsign,
                    results=[],
                    sources=[],
                    retrieved_at=datetime.now(timezone.utc),
                )
            logger.error(f"OpenSky HTTP error: {e}")
            raise AdapterParseError(self.source_name, str(e)) from e

        except httpx.HTTPError as e:
            logger.error(f"OpenSky HTTP error: {e}")
            raise AdapterParseError(self.source_name, str(e)) from e

        # Parse response
        try:
            data = response.json()
        except Exception as e:
            raise AdapterParseError(self.source_name, "Invalid JSON response") from e

        # Filter states by callsign
        states = data.get("states") or []
        matching_states = []
        for state in states:
            state_callsign = (state[1] or "").strip().upper()
            if callsign in state_callsign or state_callsign.startswith(callsign):
                matching_states.append(self._parse_state_vector(state))

        if not matching_states:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=callsign,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error=f"No aircraft found with callsign matching '{callsign}'",
            )

        # Cache results
        if self._cache:
            settings = get_settings()
            await self._cache.set(
                key=key,
                data={"states": matching_states, "time": data.get("time")},
                ttl_seconds=settings.ttl_opensky,
                source=self.source_name,
            )

        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=callsign,
            results=matching_states,
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,  # ADS-B data
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=url,
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    async def get_states(self, icao24: str | None = None) -> OSINTResult:
        """Get current state vectors for aircraft.

        Args:
            icao24: Optional ICAO24 transponder code to filter by.
                   If None, returns all current states (large response).

        Returns:
            OSINTResult with aircraft state vectors.

        Raises:
            AdapterAuthError: If credentials not configured or invalid.
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        # Generate cache key
        key = cache_key(self.source_name, "states", icao24=icao24 or "all")

        # Check cache first
        if self._cache:
            cached = await self._cache.get(key)
            if cached and cached.data and not cached.is_stale:
                logger.debug(f"Cache hit for {key}")
                return self._build_result_from_cache(icao24 or "all", cached.data)

        client = await self._get_client()
        url = f"{self.BASE_URL}/api/states/all"
        params: dict[str, str] = {}
        if icao24:
            params["icao24"] = icao24.lower()

        logger.info(f"Querying OpenSky states: icao24={icao24 or 'all'}")

        try:
            response = await client.get(url, params=params if params else None)

            if response.status_code == 401:
                raise AdapterAuthError(self.source_name, "Invalid credentials")

            if response.status_code == 429:
                logger.warning("OpenSky rate limited")
                return OSINTResult(
                    status=ResultStatus.RATE_LIMITED,
                    query=icao24 or "all",
                    results=[],
                    sources=[],
                    retrieved_at=datetime.now(timezone.utc),
                )

            response.raise_for_status()

        except httpx.TimeoutException as e:
            logger.warning(f"OpenSky timeout: {e}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AdapterAuthError(self.source_name, "Invalid credentials") from e
            if e.response.status_code == 429:
                return OSINTResult(
                    status=ResultStatus.RATE_LIMITED,
                    query=icao24 or "all",
                    results=[],
                    sources=[],
                    retrieved_at=datetime.now(timezone.utc),
                )
            logger.error(f"OpenSky HTTP error: {e}")
            raise AdapterParseError(self.source_name, str(e)) from e

        except httpx.HTTPError as e:
            logger.error(f"OpenSky HTTP error: {e}")
            raise AdapterParseError(self.source_name, str(e)) from e

        # Parse response
        try:
            data = response.json()
        except Exception as e:
            raise AdapterParseError(self.source_name, "Invalid JSON response") from e

        states = data.get("states") or []
        if not states:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=icao24 or "all",
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error="No aircraft found" + (f" with ICAO24 '{icao24}'" if icao24 else ""),
            )

        parsed_states = [self._parse_state_vector(s) for s in states]

        # Cache results
        if self._cache:
            settings = get_settings()
            await self._cache.set(
                key=key,
                data={"states": parsed_states, "time": data.get("time")},
                ttl_seconds=settings.ttl_opensky,
                source=self.source_name,
            )

        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=icao24 or "all",
            results=parsed_states,
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=url + (f"?icao24={icao24}" if icao24 else ""),
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    async def get_track(self, icao24: str) -> OSINTResult:
        """Get flight track history for an aircraft.

        Returns the historical positions over the past 24 hours,
        ordered chronologically.

        Args:
            icao24: ICAO24 transponder code of the aircraft.

        Returns:
            OSINTResult with flight track waypoints.

        Raises:
            AdapterAuthError: If credentials not configured or invalid.
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        icao24_lower = icao24.lower()

        # Generate cache key
        key = cache_key(self.source_name, "track", icao24=icao24_lower)

        # Check cache first
        if self._cache:
            cached = await self._cache.get(key)
            if cached and cached.data and not cached.is_stale:
                logger.debug(f"Cache hit for {key}")
                return self._build_track_result_from_cache(icao24_lower, cached.data)

        client = await self._get_client()
        # time=0 means get track for current flight
        url = f"{self.BASE_URL}/api/tracks/all"
        params = {"icao24": icao24_lower, "time": "0"}

        logger.info(f"Querying OpenSky track: icao24={icao24}")

        try:
            response = await client.get(url, params=params)

            if response.status_code == 401:
                raise AdapterAuthError(self.source_name, "Invalid credentials")

            if response.status_code == 429:
                logger.warning("OpenSky rate limited")
                return OSINTResult(
                    status=ResultStatus.RATE_LIMITED,
                    query=icao24_lower,
                    results=[],
                    sources=[],
                    retrieved_at=datetime.now(timezone.utc),
                )

            if response.status_code == 404:
                return OSINTResult(
                    status=ResultStatus.NO_DATA,
                    query=icao24_lower,
                    results=[],
                    sources=[],
                    retrieved_at=datetime.now(timezone.utc),
                    error=f"No track data found for aircraft '{icao24}'",
                )

            response.raise_for_status()

        except httpx.TimeoutException as e:
            logger.warning(f"OpenSky timeout: {e}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AdapterAuthError(self.source_name, "Invalid credentials") from e
            if e.response.status_code == 429:
                return OSINTResult(
                    status=ResultStatus.RATE_LIMITED,
                    query=icao24_lower,
                    results=[],
                    sources=[],
                    retrieved_at=datetime.now(timezone.utc),
                )
            if e.response.status_code == 404:
                return OSINTResult(
                    status=ResultStatus.NO_DATA,
                    query=icao24_lower,
                    results=[],
                    sources=[],
                    retrieved_at=datetime.now(timezone.utc),
                    error=f"No track data found for aircraft '{icao24}'",
                )
            logger.error(f"OpenSky HTTP error: {e}")
            raise AdapterParseError(self.source_name, str(e)) from e

        except httpx.HTTPError as e:
            logger.error(f"OpenSky HTTP error: {e}")
            raise AdapterParseError(self.source_name, str(e)) from e

        # Parse response
        try:
            data = response.json()
        except Exception as e:
            raise AdapterParseError(self.source_name, "Invalid JSON response") from e

        path = data.get("path") or []
        if not path:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=icao24_lower,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error=f"No track data found for aircraft '{icao24}'",
            )

        # Parse waypoints and sort chronologically
        raw_waypoints = [self._parse_track_point(wp) for wp in path]
        raw_waypoints.sort(key=lambda x: x.get("timestamp", 0))

        # Include track metadata in each waypoint for flat structure
        # OSINTResult.results only supports flat dicts with scalar values
        icao24_val = data.get("icao24")
        callsign_val = (data.get("callsign") or "").strip()
        start_time_val = data.get("startTime")
        end_time_val = data.get("endTime")

        waypoints: list[dict[str, str | int | float | bool | None]] = []
        for wp in raw_waypoints:
            waypoints.append({
                "icao24": icao24_val,
                "callsign": callsign_val,
                "start_time": start_time_val,
                "end_time": end_time_val,
                "timestamp": wp.get("timestamp"),
                "latitude": wp.get("latitude"),
                "longitude": wp.get("longitude"),
                "altitude": wp.get("altitude"),
                "heading": wp.get("heading"),
                "on_ground": wp.get("on_ground"),
            })

        # Cache the raw waypoints for later retrieval
        cache_data = {
            "icao24": icao24_val,
            "callsign": callsign_val,
            "start_time": start_time_val,
            "end_time": end_time_val,
            "waypoints": raw_waypoints,
        }
        if self._cache:
            settings = get_settings()
            await self._cache.set(
                key=key,
                data=cache_data,
                ttl_seconds=settings.ttl_opensky,
                source=self.source_name,
            )

        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=icao24_lower,
            results=waypoints,
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=f"{url}?icao24={icao24_lower}&time=0",
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    def _build_result_from_cache(
        self, query: str, cached_data: dict[str, Any]
    ) -> OSINTResult:
        """Build OSINTResult from cached state data."""
        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=query,
            results=cached_data.get("states", []),
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=f"{self.BASE_URL}/api/states/all",
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    def _build_track_result_from_cache(
        self, icao24: str, cached_data: dict[str, Any]
    ) -> OSINTResult:
        """Build OSINTResult from cached track data."""
        # Reconstruct flat waypoint list from cached data
        icao24_val = cached_data.get("icao24")
        callsign_val = cached_data.get("callsign", "")
        start_time_val = cached_data.get("start_time")
        end_time_val = cached_data.get("end_time")
        raw_waypoints = cached_data.get("waypoints", [])

        waypoints: list[dict[str, str | int | float | bool | None]] = []
        for wp in raw_waypoints:
            waypoints.append({
                "icao24": icao24_val,
                "callsign": callsign_val,
                "start_time": start_time_val,
                "end_time": end_time_val,
                "timestamp": wp.get("timestamp"),
                "latitude": wp.get("latitude"),
                "longitude": wp.get("longitude"),
                "altitude": wp.get("altitude"),
                "heading": wp.get("heading"),
                "on_ground": wp.get("on_ground"),
            })

        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=icao24,
            results=waypoints,
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=f"{self.BASE_URL}/api/tracks/all?icao24={icao24}&time=0",
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    async def health_check(self) -> bool:
        """Check if OpenSky API is reachable and credentials are valid.

        Returns:
            True if API responds with valid credentials, False otherwise.
        """
        try:
            client = await self._get_client()
            # Use a simple states query to test connectivity
            response = await client.get(
                f"{self.BASE_URL}/api/states/all",
                params={"icao24": "abc123"},  # Specific query to minimize response size
            )
            # 200 = success, even with no results
            # 401 = invalid credentials
            return response.status_code == 200
        except AdapterAuthError:
            logger.warning("OpenSky health check failed: No credentials configured")
            return False
        except Exception as e:
            logger.warning(f"OpenSky health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("OpenSky adapter client closed")
