"""Entity resolution module for cross-source matching.

Provides entity resolution via Wikidata lookup.
"""

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from ignifer.models import ConfidenceLevel

if TYPE_CHECKING:
    from ignifer.adapters.wikidata import WikidataAdapter

logger = logging.getLogger(__name__)


class ResolutionTier(str, Enum):
    """Entity resolution tiers."""

    WIKIDATA = "wikidata"
    FAILED = "failed"

    @property
    def default_confidence(self) -> float:
        """Default confidence score for this tier."""
        return {
            ResolutionTier.WIKIDATA: 0.85,
            ResolutionTier.FAILED: 0.0,
        }[self]


class EntityMatch(BaseModel):
    """Result of entity resolution.

    Attributes:
        entity_id: Internal entity identifier (may be same as wikidata_qid)
        wikidata_qid: Wikidata Q-ID if resolved
        resolution_tier: Which tier matched ("wikidata", "failed")
        match_confidence: 0.0 to 1.0 confidence score
        original_query: The original search query
        matched_label: The label that matched
        suggestions: Alternative query suggestions (on failure)
        confidence_factors: List of factors explaining the confidence score
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    entity_id: str | None = None
    wikidata_qid: str | None = None
    resolution_tier: ResolutionTier
    match_confidence: float = Field(ge=0.0, le=1.0)
    original_query: str
    matched_label: str | None = None
    suggestions: list[str] = []
    confidence_factors: list[str] = Field(default_factory=list)

    def is_successful(self) -> bool:
        """Check if resolution was successful."""
        return self.resolution_tier != ResolutionTier.FAILED

    def to_confidence_level(self) -> ConfidenceLevel:
        """Convert match_confidence float to ConfidenceLevel enum.

        Maps the 0.0-1.0 float to ICD 203 confidence levels based on
        percentage thresholds.

        Returns:
            ConfidenceLevel corresponding to the match_confidence value.
        """
        return ConfidenceLevel.from_percentage(self.match_confidence)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary.

        Returns:
            Dictionary representation of the entity match.
        """
        return {
            "entity_id": self.entity_id,
            "wikidata_qid": self.wikidata_qid,
            "resolution_tier": self.resolution_tier.value,
            "match_confidence": self.match_confidence,
            "confidence_level": self.to_confidence_level().name,
            "original_query": self.original_query,
            "matched_label": self.matched_label,
            "suggestions": self.suggestions,
            "confidence_factors": self.confidence_factors,
        }


class EntityResolver:
    """Entity resolution via Wikidata lookup.

    Attributes:
        wikidata_adapter: WikidataAdapter for remote lookups.
    """

    def __init__(
        self,
        wikidata_adapter: "WikidataAdapter | None" = None,
    ) -> None:
        """Initialize the entity resolver.

        Args:
            wikidata_adapter: WikidataAdapter for Wikidata lookups.
        """
        self._wikidata = wikidata_adapter

    async def resolve(self, query: str) -> EntityMatch:
        """Resolve an entity query via Wikidata.

        Args:
            query: Entity name or identifier to resolve.

        Returns:
            EntityMatch with resolution details.
        """
        query = query.strip()
        if not query:
            return self._create_failed_match(query, "Empty query")

        logger.info(f"Resolving entity: {query}")

        # Try Wikidata lookup
        if self._wikidata:
            match = await self._try_wikidata_lookup(query)
            if match:
                self._log_resolution(query, match)
                return match

        # Wikidata lookup failed
        failed_match = self._create_failed_match(query)
        self._log_resolution(query, failed_match)
        return failed_match

    def _log_resolution(self, query: str, match: EntityMatch) -> None:
        """Log the resolution result.

        Args:
            query: Original query string.
            match: Resolution result.
        """
        if match.is_successful():
            logger.info(
                f"Entity '{query}' resolved via {match.resolution_tier.value} "
                f"(confidence: {match.match_confidence:.2f})"
            )
        else:
            logger.warning(f"Entity '{query}' could not be resolved")

    async def _try_wikidata_lookup(self, query: str) -> EntityMatch | None:
        """Try to resolve via Wikidata lookup.

        Args:
            query: Entity query string.

        Returns:
            EntityMatch if found, None otherwise.
        """
        if not self._wikidata:
            return None

        try:
            from ignifer.models import QueryParams, ResultStatus

            result = await self._wikidata.query(QueryParams(query=query))

            if result.status != ResultStatus.SUCCESS:
                logger.warning(
                    f"Wikidata lookup for '{query}' returned status: {result.status}, "
                    f"error: {result.error}"
                )
                return None

            if not result.results:
                logger.warning(f"Wikidata lookup for '{query}' returned no results")
                return None

            # Get top result
            top = result.results[0]
            qid_raw = top.get("qid")
            label = top.get("label", query)

            if not qid_raw:
                logger.warning(f"Wikidata result for '{query}' has no Q-ID: {top}")
                return None

            # Ensure qid is a string
            qid = str(qid_raw)

            return EntityMatch(
                entity_id=qid,
                wikidata_qid=qid,
                resolution_tier=ResolutionTier.WIKIDATA,
                match_confidence=0.85,
                original_query=query,
                matched_label=str(label) if label else query,
                confidence_factors=[
                    "Resolved via Wikidata knowledge graph",
                    "85% confidence for remote API lookup",
                    f"Matched Q-ID: {qid}",
                ],
            )

        except Exception as e:
            logger.warning(f"Wikidata lookup failed for '{query}': {type(e).__name__}: {e}")
            return None

    def _create_failed_match(self, query: str, reason: str | None = None) -> EntityMatch:
        """Create a failed match result with suggestions.

        Args:
            query: Original query string.
            reason: Optional reason for failure.

        Returns:
            EntityMatch with failed tier and suggestions.
        """
        suggestions = [
            "Try checking the spelling",
            "Try using a more complete name",
            "Try using the Wikidata Q-ID if known (e.g., identifier='Q12345')",
        ]

        factors = ["Wikidata lookup returned no results"]
        if reason:
            factors.append(reason)

        return EntityMatch(
            entity_id=None,
            wikidata_qid=None,
            resolution_tier=ResolutionTier.FAILED,
            match_confidence=0.0,
            original_query=query,
            matched_label=None,
            suggestions=suggestions,
            confidence_factors=factors,
        )


__all__ = [
    "EntityMatch",
    "EntityResolver",
    "ResolutionTier",
]
