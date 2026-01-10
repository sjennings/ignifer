"""AISStream adapter for real-time maritime vessel tracking.

AISStream provides real-time AIS (Automatic Identification System) data
for vessels worldwide via WebSocket streaming. This adapter implements
a connection-on-demand pattern: connect -> query -> cache -> disconnect.

API Reference: https://aisstream.io/documentation
"""

import asyncio
import json
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import websockets
from websockets.exceptions import (
    ConnectionClosed,
    InvalidStatus,
    WebSocketException,
)

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


# Python 3.10 compatibility for asyncio.timeout
@asynccontextmanager
async def async_timeout(seconds: float) -> AsyncIterator[None]:
    """Async timeout context manager compatible with Python 3.10+."""
    if sys.version_info >= (3, 11):
        async with asyncio.timeout(seconds):
            yield
    else:
        # For Python 3.10, use asyncio.wait_for pattern via task cancellation
        task = asyncio.current_task()
        loop = asyncio.get_event_loop()
        timeout_handle = loop.call_later(seconds, task.cancel)  # type: ignore[union-attr]
        try:
            yield
        except asyncio.CancelledError:
            raise TimeoutError() from None
        finally:
            timeout_handle.cancel()


class AISStreamAdapter:
    """AISStream adapter for real-time vessel tracking via WebSocket.

    Uses connection-on-demand pattern: establishes WebSocket connection,
    subscribes for specific vessel data, waits for response, then disconnects.
    Results are cached with 15-minute TTL.

    Attributes:
        source_name: "aisstream"
        base_quality_tier: QualityTier.HIGH (AIS transponder data)
    """

    WEBSOCKET_URL = "wss://stream.aisstream.io/v0/stream"
    DEFAULT_TIMEOUT = 30.0  # seconds to wait for vessel data (AIS broadcasts every 2-180s)
    CONNECTION_TIMEOUT = 10.0  # seconds to establish WebSocket connection
    MAX_RETRIES = 2
    INITIAL_BACKOFF = 1.0  # seconds
    MAX_BACKOFF = 5.0  # seconds

    def __init__(self, cache: CacheManager | None = None) -> None:
        """Initialize the AISStream adapter.

        Args:
            cache: Optional cache manager for caching results.
        """
        self._cache = cache

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        return "aisstream"

    @property
    def base_quality_tier(self) -> QualityTier:
        """Default quality tier for this source's data."""
        return QualityTier.HIGH

    def _get_api_key(self) -> str:
        """Get API key from settings.

        Returns:
            API key string.

        Raises:
            AdapterAuthError: If API key is not configured.
        """
        settings = get_settings()
        if not settings.has_aisstream_credentials():
            raise AdapterAuthError(
                self.source_name, settings.get_credential_error_message("aisstream")
            )
        # Use get_secret_value() to extract actual credential value
        return settings.aisstream_key.get_secret_value()  # type: ignore[union-attr]

    def _build_subscribe_message(
        self,
        mmsi_list: list[str] | None = None,
        bounding_boxes: list[list[list[float]]] | None = None,
    ) -> dict[str, Any]:
        """Build WebSocket subscription message.

        Args:
            mmsi_list: Optional list of MMSI numbers to filter by.
            bounding_boxes: Optional list of bounding boxes [[SW, NE], ...].
                           If None, uses global coverage.

        Returns:
            Subscription message dict (without API key for logging safety).
        """
        msg: dict[str, Any] = {
            "APIKey": self._get_api_key(),
        }

        # Default to global bounding box if none specified
        if bounding_boxes:
            msg["BoundingBoxes"] = bounding_boxes
        else:
            # Global coverage: SW corner [-90, -180], NE corner [90, 180]
            msg["BoundingBoxes"] = [[[-90, -180], [90, 180]]]

        if mmsi_list:
            msg["FiltersShipMMSI"] = mmsi_list

        return msg

    def _parse_position_message(self, raw_msg: dict[str, Any]) -> dict[str, Any] | None:
        """Parse AIS position report message.

        Args:
            raw_msg: Raw message from AISStream WebSocket.

        Returns:
            Parsed vessel position dict, or None if not a position report.
        """
        msg_type = raw_msg.get("MessageType")
        if msg_type != "PositionReport":
            return None

        message = raw_msg.get("Message", {})
        position_report = message.get("PositionReport", {})
        metadata = raw_msg.get("MetaData", {})

        # Extract core position data
        return {
            "mmsi": str(metadata.get("MMSI", "")),
            "imo": metadata.get("IMO"),
            "vessel_name": metadata.get("ShipName", "").strip(),
            "vessel_type": position_report.get("Type"),
            "latitude": position_report.get("Latitude"),
            "longitude": position_report.get("Longitude"),
            "speed_over_ground": position_report.get("Sog"),
            "course_over_ground": position_report.get("Cog"),
            "heading": position_report.get("TrueHeading"),
            "navigational_status": position_report.get("NavigationalStatus"),
            "destination": metadata.get("Destination", "").strip() or None,
            "eta": metadata.get("ETA"),
            "timestamp": metadata.get("time_utc"),
            "country": metadata.get("country"),
        }

    async def _connect_and_receive(
        self,
        subscribe_msg: dict[str, Any],
        timeout: float,
    ) -> list[dict[str, Any]]:
        """Connect to WebSocket, subscribe, and receive messages.

        Args:
            subscribe_msg: Subscription message to send.
            timeout: Maximum time to wait for data.

        Returns:
            List of parsed position messages.

        Raises:
            AdapterTimeoutError: If connection or data retrieval times out.
            AdapterAuthError: If authentication fails.
            AdapterParseError: If message parsing fails.
        """
        positions: list[dict[str, Any]] = []
        backoff = self.INITIAL_BACKOFF

        for attempt in range(self.MAX_RETRIES):
            try:
                # websockets.connect has its own open_timeout (default 10s)
                # We set it explicitly to CONNECTION_TIMEOUT for clarity
                async with websockets.connect(
                    self.WEBSOCKET_URL,
                    open_timeout=self.CONNECTION_TIMEOUT,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    # Send subscription message
                    await ws.send(json.dumps(subscribe_msg))
                    logger.debug("Sent subscription to AISStream")

                    # Receive messages until data timeout or we get data
                    start_time = asyncio.get_event_loop().time()
                    while (asyncio.get_event_loop().time() - start_time) < timeout:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                            msg = json.loads(raw)

                            # Check for error messages
                            if msg.get("MessageType") == "Error":
                                error_msg = msg.get("Message", "Unknown error")
                                if "API" in str(error_msg) or "auth" in str(error_msg).lower():
                                    raise AdapterAuthError(
                                        self.source_name, f"AISStream: {error_msg}"
                                    )
                                raise AdapterParseError(
                                    self.source_name, f"AISStream error: {error_msg}"
                                )

                            # Parse position report
                            position = self._parse_position_message(msg)
                            if position:
                                positions.append(position)
                                # For single MMSI query, return after first position
                                if subscribe_msg.get("FiltersShipMMSI"):
                                    return positions

                        except asyncio.TimeoutError:
                            # No message received in 5s, continue waiting
                            continue

                    # Data timeout reached, return what we have (may be empty)
                    return positions

            except InvalidStatus as e:
                # InvalidStatus has a response attribute with status code
                status_code = getattr(e.response, "status_code", 0) if hasattr(e, "response") else 0
                if status_code == 401:
                    raise AdapterAuthError(
                        self.source_name, "Invalid API key"
                    ) from e
                logger.warning(f"AISStream WebSocket error (attempt {attempt + 1}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                else:
                    raise AdapterTimeoutError(self.source_name, timeout) from e

            except ConnectionClosed as e:
                logger.warning(f"AISStream WebSocket closed (attempt {attempt + 1}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                else:
                    raise AdapterTimeoutError(self.source_name, timeout) from e

            except WebSocketException as e:
                logger.warning(f"AISStream WebSocket error (attempt {attempt + 1}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                else:
                    raise AdapterTimeoutError(self.source_name, timeout) from e

            except TimeoutError:
                logger.warning(f"AISStream connection timeout (attempt {attempt + 1})")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                else:
                    raise AdapterTimeoutError(self.source_name, self.CONNECTION_TIMEOUT)

            except json.JSONDecodeError as e:
                raise AdapterParseError(
                    self.source_name, f"Invalid JSON from AISStream: {e}"
                ) from e

        return positions

    async def query(self, params: QueryParams) -> OSINTResult:
        """Query AISStream by MMSI or vessel search.

        The query field should contain an MMSI number.
        Use get_vessel_position() for direct MMSI lookups.

        Args:
            params: Query parameters with MMSI in query field.

        Returns:
            OSINTResult with vessel position data.

        Raises:
            AdapterAuthError: If API key not configured or invalid.
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        mmsi = params.query.strip()

        # Validate MMSI format (should be 9 digits)
        if not mmsi.isdigit() or len(mmsi) != 9:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=mmsi,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error=f"Invalid MMSI format: '{mmsi}'. MMSI should be 9 digits.",
            )

        return await self.get_vessel_position(mmsi)

    async def get_vessel_position(self, mmsi: str) -> OSINTResult:
        """Get current position for a specific vessel by MMSI.

        Args:
            mmsi: Maritime Mobile Service Identity (9-digit number).

        Returns:
            OSINTResult with vessel position data.

        Raises:
            AdapterAuthError: If API key not configured or invalid.
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        mmsi = mmsi.strip()

        # Generate cache key
        key = cache_key(self.source_name, "vessel", mmsi=mmsi)

        # Check cache first
        if self._cache:
            cached = await self._cache.get(key)
            if cached and cached.data and not cached.is_stale:
                logger.debug(f"Cache hit for {key}")
                return self._build_result_from_cache(mmsi, cached.data)

        # Build subscription message for specific MMSI
        subscribe_msg = self._build_subscribe_message(mmsi_list=[mmsi])

        logger.info(f"Querying AISStream for MMSI: {mmsi}")

        # Connect and receive position data
        positions = await self._connect_and_receive(
            subscribe_msg, timeout=self.DEFAULT_TIMEOUT
        )

        if not positions:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=mmsi,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error=f"No position data found for MMSI '{mmsi}'",
            )

        # Cache results
        if self._cache:
            settings = get_settings()
            await self._cache.set(
                key=key,
                data={"positions": positions},
                ttl_seconds=settings.ttl_aisstream,
                source=self.source_name,
            )

        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=mmsi,
            results=positions,
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,  # AIS transponder data
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=self.WEBSOCKET_URL,
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    def _build_result_from_cache(
        self, query: str, cached_data: dict[str, Any]
    ) -> OSINTResult:
        """Build OSINTResult from cached position data."""
        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=query,
            results=cached_data.get("positions", []),
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=self.WEBSOCKET_URL,
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    async def health_check(self) -> bool:
        """Check if AISStream is reachable and API key is valid.

        Returns:
            True if connection succeeds, False otherwise.
        """
        try:
            # Verify credentials are configured
            api_key = self._get_api_key()
            if not api_key:
                return False

            # Attempt a quick WebSocket connection
            async with async_timeout(10.0):
                async with websockets.connect(
                    self.WEBSOCKET_URL,
                    ping_interval=None,
                    close_timeout=2,
                ) as ws:
                    # Send minimal subscription to test auth
                    subscribe_msg = {
                        "APIKey": api_key,
                        "BoundingBoxes": [[[0, 0], [1, 1]]],  # Small area
                    }
                    await ws.send(json.dumps(subscribe_msg))

                    # Wait briefly for any error response
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        msg = json.loads(raw)
                        if msg.get("MessageType") == "Error":
                            logger.warning(f"AISStream health check error: {msg}")
                            return False
                    except asyncio.TimeoutError:
                        # No error message means connection is working
                        pass

                    return True

        except AdapterAuthError:
            logger.warning("AISStream health check failed: No credentials configured")
            return False
        except Exception as e:
            logger.warning(f"AISStream health check failed: {e}")
            return False

    async def close(self) -> None:
        """Cleanup method (no persistent connections to close)."""
        # Connection-on-demand pattern means no persistent connections
        # This method exists for protocol compliance
        logger.debug("AISStream adapter closed (no persistent connections)")


__all__ = ["AISStreamAdapter"]
