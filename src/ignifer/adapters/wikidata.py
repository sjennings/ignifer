"""Wikidata adapter for entity information.

Provides access to entity data (people, organizations, places, things)
from Wikidata via the MediaWiki Action API. Uses wbsearchentities for
text search and wbgetentities for direct Q-ID lookup.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from ignifer.adapters.base import AdapterParseError, AdapterTimeoutError, handle_http_status

# Regex pattern for valid Wikidata Q-ID format (Q followed by one or more digits)
QID_PATTERN = re.compile(r"^Q\d+$")

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

# Key Wikidata properties to extract from claims
KEY_PROPERTIES: dict[str, str] = {
    "P31": "instance_of",
    "P106": "occupation",
    "P17": "country",
    "P27": "citizenship",
    "P159": "headquarters",
    "P571": "inception",
    "P856": "website",
    "P625": "coordinates",
    # Country context properties (for economic_context)
    "P6": "head_of_government",
    "P35": "head_of_state",
    "P38": "currency",
    "P1304": "central_bank",
    "P463": "member_of",
}


class WikidataAdapter:
    """Wikidata adapter for entity information.

    Provides access to entity data (people, organizations, places)
    from Wikidata. No API key required.

    Attributes:
        source_name: "wikidata"
        base_quality_tier: QualityTier.HIGH (curated encyclopedic data)
    """

    BASE_URL = "https://www.wikidata.org/w/api.php"
    DEFAULT_TIMEOUT = 15.0  # seconds
    MAX_SEARCH_RESULTS = 10

    def __init__(self, cache: CacheManager | None = None) -> None:
        """Initialize the Wikidata adapter.

        Args:
            cache: Optional cache manager for caching results.
        """
        self._client: httpx.AsyncClient | None = None
        self._cache = cache

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        return "wikidata"

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

    def _extract_labels(self, entity_data: dict[str, Any]) -> dict[str, str]:
        """Extract labels from entity data.

        Args:
            entity_data: Raw entity data from Wikidata API

        Returns:
            Dict of language code to label value
        """
        labels = {}
        raw_labels = entity_data.get("labels", {})
        for lang, label_data in raw_labels.items():
            labels[lang] = label_data.get("value", "")
        return labels

    def _extract_aliases(self, entity_data: dict[str, Any]) -> list[str]:
        """Extract aliases from entity data.

        Args:
            entity_data: Raw entity data from Wikidata API

        Returns:
            List of alias strings (English preferred, then others)
        """
        aliases = []
        raw_aliases = entity_data.get("aliases", {})

        # Prefer English aliases first
        if "en" in raw_aliases:
            for alias_data in raw_aliases["en"]:
                aliases.append(alias_data.get("value", ""))

        # Add aliases from other languages
        for lang, alias_list in raw_aliases.items():
            if lang != "en":
                for alias_data in alias_list:
                    value = alias_data.get("value", "")
                    if value and value not in aliases:
                        aliases.append(value)

        return aliases

    def _extract_claim_value(self, claim: dict[str, Any]) -> dict[str, Any] | None:
        """Extract value from a single claim.

        Args:
            claim: Raw claim data from Wikidata

        Returns:
            Dict with value and optionally qid, or None if no value
        """
        mainsnak = claim.get("mainsnak", {})

        # Handle novalue and somevalue snaktypes
        snaktype = mainsnak.get("snaktype", "value")
        if snaktype == "novalue":
            return {"value": None, "snaktype": "novalue"}
        elif snaktype == "somevalue":
            return {"value": None, "snaktype": "somevalue"}

        datavalue = mainsnak.get("datavalue", {})

        if not datavalue:
            return None

        value_type = datavalue.get("type")
        value = datavalue.get("value")

        if value_type == "wikibase-entityid":
            # Entity reference (e.g., Q5 for human)
            entity_id = value.get("id", "")
            return {"qid": entity_id, "value": entity_id}

        elif value_type == "string":
            return {"value": value}

        elif value_type == "monolingualtext":
            # Language-tagged text (e.g., motto in specific language)
            return {
                "value": value.get("text", ""),
                "language": value.get("language", ""),
            }

        elif value_type == "time":
            # Extract just the date portion
            time_value = value.get("time", "")
            # Remove leading + and trailing time component if present
            if time_value.startswith("+"):
                time_value = time_value[1:]
            # Extract date portion (YYYY-MM-DD)
            if "T" in time_value:
                time_value = time_value.split("T")[0]
            return {"value": time_value}

        elif value_type == "globecoordinate":
            return {
                "value": {
                    "latitude": value.get("latitude"),
                    "longitude": value.get("longitude"),
                }
            }

        elif value_type == "quantity":
            return {"value": value.get("amount", "")}

        elif value_type == "commonsMedia":
            # Wikimedia Commons file name
            return {"value": value, "type": "commonsMedia"}

        elif value_type == "url":
            # URL value (distinct from string)
            return {"value": value}

        elif value_type == "external-id":
            # External identifier (e.g., IMDB ID)
            return {"value": value, "type": "external-id"}

        # Unknown type - log warning and return stringified value
        logger.warning(f"Unknown Wikidata claim value type: {value_type}")
        return {"value": str(value) if value else None}

    def _extract_claims(
        self, entity_data: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Extract key properties from entity claims.

        Args:
            entity_data: Raw entity data from Wikidata API

        Returns:
            Dict of property name to extracted value
        """
        extracted = {}
        claims = entity_data.get("claims", {})

        for prop_id, prop_name in KEY_PROPERTIES.items():
            if prop_id in claims:
                claim_list = claims[prop_id]
                if claim_list:
                    # Get the first (preferred) value
                    value_data = self._extract_claim_value(claim_list[0])
                    if value_data:
                        extracted[prop_name] = value_data

        return extracted

    def _build_entity_url(self, qid: str) -> str:
        """Build URL to Wikidata entity page.

        Args:
            qid: Wikidata Q-ID (e.g., "Q7747")

        Returns:
            URL to entity page
        """
        return f"https://www.wikidata.org/wiki/{qid}"

    async def query(self, params: QueryParams) -> OSINTResult:
        """Search for entities matching the query.

        Uses Wikidata wbsearchentities API to find entities by text search,
        then fetches basic details for each result.

        Args:
            params: Query parameters including query string.

        Returns:
            OSINTResult with entity search results.

        Raises:
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        query_text = params.query.strip()
        if not query_text:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=params.query,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error="Query string is empty.",
            )

        # Check if query looks like a Q-ID and redirect to lookup_by_qid
        # This prevents cache collisions and provides better results
        normalized_query = query_text.upper()
        if not normalized_query.startswith("Q"):
            # Try prepending Q to see if it's just a number
            potential_qid = f"Q{normalized_query}"
        else:
            potential_qid = normalized_query

        if QID_PATTERN.match(potential_qid):
            logger.debug(f"Query '{query_text}' looks like Q-ID, redirecting to lookup_by_qid")
            return await self.lookup_by_qid(query_text)

        # Generate cache key for search (use "search:" prefix to avoid collision with entity keys)
        key = cache_key(self.source_name, "search", text=query_text.lower())

        # Check cache
        if self._cache:
            cached = await self._cache.get(key)
            if cached and cached.data and not cached.is_stale:
                logger.debug(f"Cache hit for {key}")
                return self._build_result_from_cache(params.query, cached.data)

        client = await self._get_client()

        # Search for entities
        search_params: dict[str, str | int] = {
            "action": "wbsearchentities",
            "search": query_text,
            "language": "en",
            "limit": self.MAX_SEARCH_RESULTS,
            "format": "json",
        }

        logger.info(f"Searching Wikidata for: {query_text}")

        try:
            response = await client.get(self.BASE_URL, params=search_params)
        except httpx.TimeoutException as e:
            logger.warning(f"Wikidata timeout: {e}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e
        except httpx.ConnectError as e:
            logger.error(f"Wikidata connection error: {e}")
            raise AdapterTimeoutError(
                self.source_name, self.DEFAULT_TIMEOUT
            ) from e
        except httpx.RequestError as e:
            # Other request errors (DNS, connection reset, etc.)
            logger.error(f"Wikidata request error: {e}")
            raise AdapterTimeoutError(
                self.source_name, self.DEFAULT_TIMEOUT
            ) from e

        # Handle HTTP status codes
        status_type, exc = handle_http_status(
            self.source_name, response.status_code, "Wikidata API endpoint not found."
        )
        if status_type == "rate_limited":
            logger.warning("Wikidata rate limited")
            return OSINTResult(
                status=ResultStatus.RATE_LIMITED,
                query=params.query,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
            )
        if status_type == "no_data":
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=params.query,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error="Wikidata API endpoint not found.",
            )
        if exc:
            logger.error(f"Wikidata HTTP error: {response.status_code}")
            raise exc

        # Parse response
        try:
            data = response.json()
        except Exception as e:
            raise AdapterParseError(self.source_name, "Invalid JSON response") from e

        search_results = data.get("search", [])

        if not search_results:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=params.query,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error="No entities found matching the query. Try different spelling or more specific terms.",
            )

        # Fetch entity details for search results
        qids = [result.get("id") for result in search_results if result.get("id")]
        entity_details = await self._fetch_entity_details(qids)

        # Build normalized results
        results: list[dict[str, Any]] = []
        for search_result in search_results:
            qid = search_result.get("id", "")
            entity_data = entity_details.get(qid, {})

            # Get instance_of from claims
            instance_of = None
            instance_of_qid = None
            claims = self._extract_claims(entity_data)
            if "instance_of" in claims:
                instance_of_qid = claims["instance_of"].get("qid")
                instance_of = instance_of_qid  # Will be resolved to label later if needed

            result_entry: dict[str, Any] = {
                "qid": qid,
                "label": search_result.get("label", ""),
                "description": search_result.get("description", ""),
                "aliases": ", ".join(self._extract_aliases(entity_data)) if entity_data else "",
                "instance_of": instance_of,
                "instance_of_qid": instance_of_qid,
                "url": self._build_entity_url(qid),
            }
            results.append(result_entry)

        # Cache results
        if self._cache and results:
            settings = get_settings()
            await self._cache.set(
                key=key,
                data={"results": results, "query": query_text},
                ttl_seconds=settings.ttl_wikidata,
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
                    confidence=ConfidenceLevel.VERY_LIKELY,  # Search results may vary
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=f"{self.BASE_URL}?action=wbsearchentities&search={query_text}",
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    async def lookup_by_qid(self, qid: str) -> OSINTResult:
        """Fetch entity details by Wikidata Q-ID.

        Directly fetches entity data via wbgetentities API, bypassing search.

        Args:
            qid: Wikidata Q-ID (e.g., "Q7747")

        Returns:
            OSINTResult with full entity details.

        Raises:
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        # Normalize Q-ID format
        qid = qid.strip().upper()
        if not qid.startswith("Q"):
            qid = f"Q{qid}"

        # Validate Q-ID format (must be Q followed by one or more digits)
        if not QID_PATTERN.match(qid):
            logger.warning(f"Invalid Q-ID format: {qid}")
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=qid,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error=f"Invalid Q-ID format: '{qid}'. Q-ID must be 'Q' followed by digits (e.g., 'Q7747').",
            )

        # Generate cache key for entity lookup
        key = cache_key(self.source_name, "entity", qid=qid)

        # Check cache
        if self._cache:
            cached = await self._cache.get(key)
            if cached and cached.data and not cached.is_stale:
                logger.debug(f"Cache hit for {key}")
                return self._build_result_from_cache(qid, cached.data)

        client = await self._get_client()

        # Fetch entity details
        entity_params = {
            "action": "wbgetentities",
            "ids": qid,
            "props": "labels|descriptions|aliases|claims",
            "languages": "en",
            "format": "json",
        }

        logger.info(f"Looking up Wikidata entity: {qid}")

        try:
            response = await client.get(self.BASE_URL, params=entity_params)
        except httpx.TimeoutException as e:
            logger.warning(f"Wikidata timeout: {e}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e
        except httpx.ConnectError as e:
            logger.error(f"Wikidata connection error: {e}")
            raise AdapterTimeoutError(
                self.source_name, self.DEFAULT_TIMEOUT
            ) from e
        except httpx.RequestError as e:
            # Other request errors (DNS, connection reset, etc.)
            logger.error(f"Wikidata request error: {e}")
            raise AdapterTimeoutError(
                self.source_name, self.DEFAULT_TIMEOUT
            ) from e

        # Handle HTTP status codes
        status_type, exc = handle_http_status(
            self.source_name, response.status_code, f"Entity {qid} not found in Wikidata."
        )
        if status_type == "rate_limited":
            logger.warning("Wikidata rate limited")
            return OSINTResult(
                status=ResultStatus.RATE_LIMITED,
                query=qid,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
            )
        if status_type == "no_data":
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=qid,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error=f"Entity {qid} not found in Wikidata.",
            )
        if exc:
            logger.error(f"Wikidata HTTP error: {response.status_code}")
            raise exc

        # Parse response
        try:
            data = response.json()
        except Exception as e:
            raise AdapterParseError(self.source_name, "Invalid JSON response") from e

        entities = data.get("entities", {})
        entity_data = entities.get(qid, {})

        # Check for missing entity (Wikidata returns {"missing": ""} for non-existent entities)
        if not entity_data or "missing" in entity_data:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=qid,
                results=[],
                sources=[],
                retrieved_at=datetime.now(timezone.utc),
                error=f"Entity {qid} not found in Wikidata.",
            )

        # Extract entity details
        labels = self._extract_labels(entity_data)
        aliases = self._extract_aliases(entity_data)
        claims = self._extract_claims(entity_data)

        # Get description
        descriptions = entity_data.get("descriptions", {})
        description = descriptions.get("en", {}).get("value", "")

        # Build related entities list from claims
        related_entities = []
        for prop_name, prop_value in claims.items():
            if "qid" in prop_value and prop_value["qid"]:
                related_entities.append({
                    "qid": prop_value["qid"],
                    "relation": prop_name,
                })

        # Build normalized result
        result_entry: dict[str, Any] = {
            "qid": qid,
            "label": labels.get("en", ""),
            "description": description,
            "aliases": ", ".join(aliases),
            "url": self._build_entity_url(qid),
        }

        # Add properties as flattened fields
        for prop_name, prop_value in claims.items():
            if "qid" in prop_value:
                result_entry[f"{prop_name}_qid"] = prop_value["qid"]
            result_entry[prop_name] = (
                str(prop_value["value"])
                if isinstance(prop_value.get("value"), dict)
                else prop_value.get("value")
            )

        # Always include related_entities_count for consistent output schema
        result_entry["related_entities_count"] = len(related_entities)

        results: list[dict[str, Any]] = [result_entry]

        # Cache results
        if self._cache:
            settings = get_settings()
            await self._cache.set(
                key=key,
                data={"results": results, "qid": qid},
                ttl_seconds=settings.ttl_wikidata,
                source=self.source_name,
            )

        retrieved_at = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=qid,
            results=results,
            sources=[
                SourceAttribution(
                    source=self.source_name,
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,  # Direct Q-ID lookup
                    metadata=SourceMetadata(
                        source_name=self.source_name,
                        source_url=self._build_entity_url(qid),
                        retrieved_at=retrieved_at,
                    ),
                )
            ],
            retrieved_at=retrieved_at,
        )

    async def _fetch_entity_details(
        self, qids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Fetch entity details for multiple Q-IDs.

        Args:
            qids: List of Wikidata Q-IDs

        Returns:
            Dict mapping Q-ID to entity data. Returns empty dict on critical errors,
            but logs warnings so users know data may be incomplete.
        """
        if not qids:
            return {}

        client = await self._get_client()

        entity_params = {
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "props": "labels|descriptions|aliases|claims",
            "languages": "en",
            "format": "json",
        }

        try:
            response = await client.get(self.BASE_URL, params=entity_params)
        except httpx.TimeoutException as e:
            logger.warning(
                f"Timeout fetching entity details for {len(qids)} entities. "
                f"Search results will be returned without enriched properties. Error: {e}"
            )
            return {}
        except httpx.ConnectError as e:
            logger.warning(
                f"Connection error fetching entity details for {len(qids)} entities. "
                f"Search results will be returned without enriched properties. Error: {e}"
            )
            return {}
        except httpx.RequestError as e:
            logger.warning(
                f"Request error fetching entity details for {len(qids)} entities. "
                f"Search results will be returned without enriched properties. Error: {e}"
            )
            return {}

        # Check HTTP status before parsing
        if response.status_code != 200:
            logger.warning(
                f"HTTP {response.status_code} fetching entity details for {len(qids)} entities. "
                f"Search results will be returned without enriched properties."
            )
            return {}

        try:
            data = response.json()
        except Exception as e:
            logger.warning(
                f"Failed to parse entity details JSON for {len(qids)} entities. "
                f"Search results will be returned without enriched properties. Error: {e}"
            )
            return {}

        entities: dict[str, dict[str, Any]] = data.get("entities", {})

        # Log if any entities are missing (different from requested)
        missing_entities = [qid for qid in qids if qid not in entities]
        if missing_entities:
            logger.warning(
                f"Missing entity data for {len(missing_entities)} of {len(qids)} requested entities: "
                f"{missing_entities[:5]}{'...' if len(missing_entities) > 5 else ''}"
            )

        return entities

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
        if cached_data.get("qid"):
            source_url = self._build_entity_url(cached_data["qid"])
        else:
            source_url = f"{self.BASE_URL}?action=wbsearchentities&search={query}"

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
        """Check if Wikidata API is reachable.

        Returns:
            True if API responds, False otherwise.
        """
        try:
            client = await self._get_client()
            # Simple query to test connectivity
            response = await client.get(
                self.BASE_URL,
                params={
                    "action": "wbsearchentities",
                    "search": "test",
                    "language": "en",
                    "limit": 1,
                    "format": "json",
                },
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Wikidata health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("Wikidata adapter client closed")
