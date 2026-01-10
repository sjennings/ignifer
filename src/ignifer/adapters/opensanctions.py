"""OpenSanctions adapter for sanctions and PEP screening.

Provides access to sanctions lists (OFAC, EU, UN, etc.) and
Politically Exposed Person (PEP) data via the OpenSanctions API.

API Reference: https://www.opensanctions.org/docs/api/
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from ignifer.adapters.base import AdapterParseError, AdapterTimeoutError, handle_http_status
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


class OpenSanctionsAdapter:
    """OpenSanctions adapter for sanctions and PEP screening.

    Provides screening against global sanctions lists and PEP databases.
    Free for non-commercial use (no API key required for basic queries).

    Attributes:
        source_name: "opensanctions"
        base_quality_tier: QualityTier.HIGH (official sanctions data)
    """

    BASE_URL = "https://api.opensanctions.org"
    DEFAULT_TIMEOUT = 15.0  # seconds
    MAX_RESULTS = 10

    def __init__(self, cache: CacheManager | None = None) -> None:
        """Initialize the OpenSanctions adapter.

        Args:
            cache: Optional cache manager for caching results.
        """
        self._client: httpx.AsyncClient | None = None
        self._cache = cache

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        return "opensanctions"

    @property
    def base_quality_tier(self) -> QualityTier:
        """Default quality tier for this source's data."""
        return QualityTier.HIGH

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.DEFAULT_TIMEOUT),
                headers={"User-Agent": "Ignifer/1.0 (OSINT research tool)"},
            )
        return self._client

    def _map_score_to_confidence(self, score: float) -> ConfidenceLevel:
        """Map OpenSanctions match score to ConfidenceLevel.

        Args:
            score: OpenSanctions match score (0.0-1.0)

        Returns:
            Appropriate ConfidenceLevel enum value
        """
        if score >= 0.9:
            return ConfidenceLevel.VERY_LIKELY
        elif score >= 0.7:
            return ConfidenceLevel.LIKELY
        elif score >= 0.5:
            return ConfidenceLevel.EVEN_CHANCE
        else:
            return ConfidenceLevel.UNLIKELY

    def _is_pep_only(self, topics: list[str]) -> bool:
        """Check if entity is PEP but not sanctioned (FR19).

        Args:
            topics: List of topics from entity properties

        Returns:
            True if PEP but not sanctioned
        """
        is_sanctioned = "sanction" in topics
        is_pep = "role.pep" in topics
        return is_pep and not is_sanctioned

    def _normalize_entity(
        self, entity: dict[str, Any], score: float | None = None
    ) -> dict[str, str | int | float | bool | None]:
        """Normalize OpenSanctions entity to flat dict.

        Args:
            entity: Raw entity from API response
            score: Optional match score

        Returns:
            Flattened entity dict with scalar values only
        """
        # Extract from entity
        properties = entity.get("properties", {})
        topics = properties.get("topics", [])
        datasets = entity.get("datasets", [])
        referents = entity.get("referents", [])

        # Build flat result dict
        result: dict[str, str | int | float | bool | None] = {
            "entity_id": entity.get("id"),
            "caption": entity.get("caption"),
            "schema": entity.get("schema"),  # Person, Company, Vessel, etc.
            "name": ", ".join(properties.get("name", [])),
            "aliases": ", ".join(properties.get("alias", [])),
            "birth_date": (
                properties.get("birthDate", [None])[0]
                if properties.get("birthDate")
                else None
            ),
            "nationality": ", ".join(properties.get("nationality", [])),
            "position": ", ".join(properties.get("position", [])),
            "sanctions_lists": ", ".join(datasets),
            "sanctions_count": len(datasets),
            "is_sanctioned": "sanction" in topics,
            "is_pep": "role.pep" in topics,
            "is_poi": "poi" in topics,
            "first_seen": entity.get("first_seen"),
            "last_seen": entity.get("last_seen"),
            "referents": ", ".join(referents) if referents else None,
            "referents_count": len(referents),
            "url": f"https://www.opensanctions.org/entities/{entity.get('id')}",
        }

        # Add match score if provided
        if score is not None:
            result["match_score"] = score
            result["match_confidence"] = self._map_score_to_confidence(score).name

        # Add PEP-specific fields (FR19)
        if self._is_pep_only(topics):
            result["pep_status"] = "PEP - NOT CURRENTLY SANCTIONED"
            result["due_diligence_note"] = "Enhanced due diligence recommended for PEPs"

        return result

    async def query(self, params: QueryParams) -> OSINTResult:
        """Search for entities matching the query.

        Args:
            params: Query parameters with entity name in query field.

        Returns:
            OSINTResult with sanctions/PEP screening results.
        """
        # Delegate to search_entity
        return await self.search_entity(params.query)

    async def search_entity(self, name: str) -> OSINTResult:
        """Search for entity by name using match API.

        Uses the POST /match/default endpoint for better matching.

        Args:
            name: Entity name to search for.

        Returns:
            OSINTResult with matching entities.

        Raises:
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        query_text = name.strip()
        if not query_text:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=name,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error="Query string is empty.",
            )

        # Generate cache key for match query
        key = cache_key(self.source_name, "match", name=query_text.lower())

        # Check cache
        if self._cache:
            cached = await self._cache.get(key)
            if cached and cached.data and not cached.is_stale:
                logger.debug(f"Cache hit for {key}")
                return self._build_result_from_cache(name, cached.data)

        client = await self._get_client()

        # Use match API for better entity matching
        match_url = f"{self.BASE_URL}/match/default"
        match_payload = {
            "queries": {
                "q1": {
                    "schema": "Thing",  # Match any entity type
                    "properties": {
                        "name": [query_text],
                    },
                }
            }
        }

        logger.info(f"Searching OpenSanctions for: {query_text}")

        try:
            response = await client.post(match_url, json=match_payload)
        except httpx.TimeoutException as e:
            logger.warning(f"OpenSanctions timeout: {e}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e
        except httpx.ConnectError as e:
            logger.error(f"OpenSanctions connection error: {e}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e
        except httpx.RequestError as e:
            logger.error(f"OpenSanctions request error: {e}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e

        # Handle HTTP status codes
        status_type, exc = handle_http_status(
            self.source_name,
            response.status_code,
            "OpenSanctions API endpoint not found.",
        )
        if status_type == "rate_limited":
            logger.warning("OpenSanctions rate limited")
            return OSINTResult(
                status=ResultStatus.RATE_LIMITED,
                query=name,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
            )
        if status_type == "no_data":
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=name,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error="OpenSanctions API endpoint not found.",
            )
        if exc:
            logger.error(f"OpenSanctions HTTP error: {response.status_code}")
            raise exc

        # Parse response
        try:
            data = response.json()
        except Exception as e:
            raise AdapterParseError(self.source_name, "Invalid JSON response") from e

        # Extract results from match API response
        responses = data.get("responses", {})
        q1_response = responses.get("q1", {})
        match_results = q1_response.get("results", [])

        if not match_results:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=name,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error=(
                    f"No matches found for '{query_text}' in sanctions databases. "
                    "Search was comprehensive across OFAC, EU, UN, and other lists. "
                    "Note: Entity may use aliases not in database."
                ),
            )

        # Normalize results
        results: list[dict[str, str | int | float | bool | None]] = []
        max_confidence = ConfidenceLevel.UNLIKELY

        for match in match_results[: self.MAX_RESULTS]:
            score = match.get("score", 0.0)
            normalized = self._normalize_entity(match, score)
            results.append(normalized)

            # Track highest confidence for attribution
            match_confidence = self._map_score_to_confidence(score)
            if match_confidence.value > max_confidence.value:
                max_confidence = match_confidence

        # Cache results
        if self._cache and results:
            settings = get_settings()
            await self._cache.set(
                key=key,
                data={"results": results, "query": query_text},
                ttl_seconds=settings.ttl_opensanctions,
                source=self.source_name,
            )

        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=name,
            results=results,
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=max_confidence,
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=f"{self.BASE_URL}/match/default",
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    async def check_sanctions(self, entity_id: str) -> OSINTResult:
        """Look up entity by OpenSanctions ID.

        Args:
            entity_id: OpenSanctions entity ID.

        Returns:
            OSINTResult with detailed entity information.

        Raises:
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        entity_id = entity_id.strip()
        if not entity_id:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=entity_id,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error="Entity ID is empty.",
            )

        # Generate cache key for entity lookup
        key = cache_key(self.source_name, "entity", entity_id=entity_id)

        # Check cache
        if self._cache:
            cached = await self._cache.get(key)
            if cached and cached.data and not cached.is_stale:
                logger.debug(f"Cache hit for {key}")
                return self._build_result_from_cache(entity_id, cached.data)

        client = await self._get_client()

        # Fetch entity details
        entity_url = f"{self.BASE_URL}/entities/{entity_id}"

        logger.info(f"Looking up OpenSanctions entity: {entity_id}")

        try:
            response = await client.get(entity_url)
        except httpx.TimeoutException as e:
            logger.warning(f"OpenSanctions timeout: {e}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e
        except httpx.ConnectError as e:
            logger.error(f"OpenSanctions connection error: {e}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e
        except httpx.RequestError as e:
            logger.error(f"OpenSanctions request error: {e}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e

        # Handle HTTP status codes
        status_type, exc = handle_http_status(
            self.source_name,
            response.status_code,
            f"Entity {entity_id} not found in OpenSanctions.",
        )
        if status_type == "rate_limited":
            logger.warning("OpenSanctions rate limited")
            return OSINTResult(
                status=ResultStatus.RATE_LIMITED,
                query=entity_id,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
            )
        if status_type == "no_data":
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=entity_id,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error=f"Entity {entity_id} not found in OpenSanctions.",
            )
        if exc:
            logger.error(f"OpenSanctions HTTP error: {response.status_code}")
            raise exc

        # Parse response
        try:
            entity_data = response.json()
        except Exception as e:
            raise AdapterParseError(self.source_name, "Invalid JSON response") from e

        # Normalize entity
        normalized = self._normalize_entity(entity_data)
        results: list[dict[str, str | int | float | bool | None]] = [normalized]

        # Cache results
        if self._cache:
            settings = get_settings()
            await self._cache.set(
                key=key,
                data={"results": results, "entity_id": entity_id},
                ttl_seconds=settings.ttl_opensanctions,
                source=self.source_name,
            )

        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=entity_id,
            results=results,
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,  # Direct ID lookup
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=entity_url,
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    def _build_result_from_cache(
        self, query: str, cached_data: dict[str, Any]
    ) -> OSINTResult:
        """Build OSINTResult from cached data.

        Args:
            query: Original query string
            cached_data: Data retrieved from cache

        Returns:
            OSINTResult constructed from cache
        """
        retrieved_at = datetime.now(timezone.utc)
        results = cached_data.get("results", [])

        # Determine source URL based on query type
        if cached_data.get("entity_id"):
            source_url = f"{self.BASE_URL}/entities/{cached_data['entity_id']}"
        else:
            source_url = f"{self.BASE_URL}/match/default"

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
                        source_url=source_url,
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    async def health_check(self) -> bool:
        """Check if OpenSanctions API is reachable.

        Returns:
            True if API responds, False otherwise.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.BASE_URL}/search/default",
                params={"q": "test", "limit": 1},
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"OpenSanctions health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("OpenSanctions adapter client closed")


__all__ = ["OpenSanctionsAdapter"]
