"""Entity resolution module for cross-source matching.

Provides a tiered entity resolution system that attempts to match entities
through exact matching, normalization, Wikidata lookup, and fuzzy matching.
"""

import logging
import re
import unicodedata
from difflib import SequenceMatcher
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from ignifer.adapters.wikidata import WikidataAdapter

logger = logging.getLogger(__name__)


class ResolutionTier(str, Enum):
    """Entity resolution tiers in priority order."""

    EXACT = "exact"
    NORMALIZED = "normalized"
    WIKIDATA = "wikidata"
    FUZZY = "fuzzy"
    FAILED = "failed"

    @property
    def default_confidence(self) -> float:
        """Default confidence score for this tier."""
        return {
            ResolutionTier.EXACT: 1.0,
            ResolutionTier.NORMALIZED: 0.95,
            ResolutionTier.WIKIDATA: 0.85,
            ResolutionTier.FUZZY: 0.75,
            ResolutionTier.FAILED: 0.0,
        }[self]


class EntityMatch(BaseModel):
    """Result of entity resolution.

    Attributes:
        entity_id: Internal entity identifier (may be same as wikidata_qid)
        wikidata_qid: Wikidata Q-ID if resolved
        resolution_tier: Which tier matched ("exact", "normalized", "wikidata", "fuzzy", "failed")
        match_confidence: 0.0 to 1.0 confidence score
        original_query: The original search query
        matched_label: The label that matched
        suggestions: Alternative query suggestions (on failure)
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

    def is_successful(self) -> bool:
        """Check if resolution was successful."""
        return self.resolution_tier != ResolutionTier.FAILED

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
            "original_query": self.original_query,
            "matched_label": self.matched_label,
            "suggestions": self.suggestions,
        }


# Known entities registry with common entities
# Maps normalized name -> entity info dict
KNOWN_ENTITIES: dict[str, dict[str, str]] = {
    "vladimir putin": {"qid": "Q7747", "label": "Vladimir Putin"},
    "joe biden": {"qid": "Q6279", "label": "Joe Biden"},
    "gazprom": {"qid": "Q102673", "label": "Gazprom"},
    "united states": {"qid": "Q30", "label": "United States"},
    "russia": {"qid": "Q159", "label": "Russia"},
    "china": {"qid": "Q148", "label": "China"},
    "european union": {"qid": "Q458", "label": "European Union"},
    "nato": {"qid": "Q7184", "label": "NATO"},
    "united nations": {"qid": "Q1065", "label": "United Nations"},
    "world bank": {"qid": "Q7164", "label": "World Bank"},
    "imf": {"qid": "Q7797", "label": "International Monetary Fund"},
    "opec": {"qid": "Q7795", "label": "OPEC"},
}


class EntityResolver:
    """Tiered entity resolution system.

    Attempts resolution in order: exact -> normalized -> wikidata -> fuzzy.
    Stops at first successful match.

    Attributes:
        wikidata_adapter: Optional WikidataAdapter for remote lookups.
        fuzzy_threshold: Minimum similarity for fuzzy matching (default: 0.8).
    """

    def __init__(
        self,
        wikidata_adapter: "WikidataAdapter | None" = None,
        fuzzy_threshold: float = 0.8,
    ) -> None:
        """Initialize the entity resolver.

        Args:
            wikidata_adapter: Optional WikidataAdapter for Wikidata tier.
            fuzzy_threshold: Minimum similarity ratio for fuzzy matching (0.0-1.0).
        """
        self._wikidata = wikidata_adapter
        self._fuzzy_threshold = fuzzy_threshold

    async def resolve(self, query: str) -> EntityMatch:
        """Resolve an entity query through tiered matching.

        Tries resolution in order: exact -> normalized -> wikidata -> fuzzy.
        Stops at first successful match (early exit).

        Args:
            query: Entity name or identifier to resolve.

        Returns:
            EntityMatch with resolution details.
        """
        logger.info(f"Resolving entity: {query}")

        # Tier 1: Exact match
        if match := self._try_exact_match(query):
            self._log_resolution(query, match)
            return match

        # Tier 2: Normalized match
        if match := self._try_normalized_match(query):
            self._log_resolution(query, match)
            return match

        # Tier 3: Wikidata lookup (if adapter available)
        if self._wikidata:
            if match := await self._try_wikidata_lookup(query):
                self._log_resolution(query, match)
                return match

        # Tier 4: Fuzzy match
        if match := self._try_fuzzy_match(query):
            self._log_resolution(query, match)
            return match

        # All tiers failed
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

    def _normalize(self, query: str) -> str:
        """Normalize query string for comparison.

        Applies:
        - Lowercase conversion
        - Strip leading/trailing whitespace
        - Collapse multiple spaces to single space
        - Remove diacritics (accents) via NFD normalization

        Args:
            query: Original query string.

        Returns:
            Normalized query string.
        """
        # Lowercase and strip
        normalized = query.lower().strip()

        # Collapse multiple spaces
        normalized = re.sub(r"\s+", " ", normalized)

        # Remove diacritics (accents)
        # NFD decomposes characters, then we filter out combining marks
        normalized = unicodedata.normalize("NFD", normalized)
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

        return normalized

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity ratio.

        Uses stdlib difflib.SequenceMatcher for Levenshtein-like ratio.

        Args:
            s1: First string.
            s2: Second string.

        Returns:
            Similarity ratio (0.0 to 1.0).
        """
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

    def _try_exact_match(self, query: str) -> EntityMatch | None:
        """Try exact match against known entities.

        Args:
            query: Entity query string.

        Returns:
            EntityMatch if found, None otherwise.
        """
        # Check exact lowercase match in registry keys
        query_lower = query.lower()
        if query_lower in KNOWN_ENTITIES:
            entity_info = KNOWN_ENTITIES[query_lower]
            return EntityMatch(
                entity_id=entity_info["qid"],
                wikidata_qid=entity_info["qid"],
                resolution_tier=ResolutionTier.EXACT,
                match_confidence=1.0,
                original_query=query,
                matched_label=entity_info["label"],
            )
        return None

    def _try_normalized_match(self, query: str) -> EntityMatch | None:
        """Try normalized match against known entities.

        Normalizes both query and known entity names before comparison.

        Args:
            query: Entity query string.

        Returns:
            EntityMatch if found, None otherwise.
        """
        normalized_query = self._normalize(query)

        for known_name, entity_info in KNOWN_ENTITIES.items():
            normalized_known = self._normalize(known_name)
            if normalized_query == normalized_known:
                return EntityMatch(
                    entity_id=entity_info["qid"],
                    wikidata_qid=entity_info["qid"],
                    resolution_tier=ResolutionTier.NORMALIZED,
                    match_confidence=0.95,
                    original_query=query,
                    matched_label=entity_info["label"],
                )
        return None

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

            if result.status != ResultStatus.SUCCESS or not result.results:
                return None

            # Get top result
            top = result.results[0]
            qid_raw = top.get("qid")
            label = top.get("label", query)

            if not qid_raw:
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
            )

        except Exception as e:
            logger.warning(f"Wikidata lookup failed for '{query}': {e}")
            return None

    def _try_fuzzy_match(self, query: str) -> EntityMatch | None:
        """Try fuzzy match against known entities.

        Uses SequenceMatcher to find similar entities above threshold.

        Args:
            query: Entity query string.

        Returns:
            EntityMatch if similarity >= threshold, None otherwise.
        """
        normalized_query = self._normalize(query)
        best_match: tuple[float, dict[str, str]] | None = None

        for known_name, entity_info in KNOWN_ENTITIES.items():
            normalized_known = self._normalize(known_name)
            similarity = self._calculate_similarity(normalized_query, normalized_known)

            if similarity >= self._fuzzy_threshold:
                if best_match is None or similarity > best_match[0]:
                    best_match = (similarity, entity_info)

        if best_match:
            similarity, entity_info = best_match
            # Scale confidence: 0.8 threshold -> 0.7, 1.0 similarity -> 0.9
            # confidence = 0.7 + (similarity - 0.8) * 1.0 for range 0.7-0.9
            confidence = 0.7 + (similarity - self._fuzzy_threshold) * 1.0
            confidence = min(0.9, max(0.7, confidence))

            logger.warning(
                f"Fuzzy match for '{query}' -> '{entity_info['label']}' "
                f"(similarity: {similarity:.2f}, confidence: {confidence:.2f})"
            )

            return EntityMatch(
                entity_id=entity_info["qid"],
                wikidata_qid=entity_info["qid"],
                resolution_tier=ResolutionTier.FUZZY,
                match_confidence=confidence,
                original_query=query,
                matched_label=entity_info["label"],
            )
        return None

    def _generate_suggestions(self, query: str) -> list[str]:
        """Generate alternative query suggestions.

        Finds similar entities below threshold and provides guidance.

        Args:
            query: Original query string.

        Returns:
            List of suggestion strings (max 3).
        """
        suggestions: list[str] = []
        normalized_query = self._normalize(query)

        # Find similar known entities below fuzzy threshold
        for known_name, entity_info in KNOWN_ENTITIES.items():
            normalized_known = self._normalize(known_name)
            similarity = self._calculate_similarity(normalized_query, normalized_known)

            # Suggest entities with 0.5-0.8 similarity (below fuzzy threshold)
            if 0.5 <= similarity < self._fuzzy_threshold:
                suggestions.append(f"Did you mean '{entity_info['label']}'?")

        # Generic suggestions if no similar entities found
        if not suggestions:
            suggestions = [
                "Try checking the spelling",
                "Try using a more complete name",
                "Try using the Wikidata Q-ID if known",
            ]

        return suggestions[:3]  # Limit to 3 suggestions

    def _create_failed_match(self, query: str) -> EntityMatch:
        """Create a failed match result with suggestions.

        Args:
            query: Original query string.

        Returns:
            EntityMatch with failed tier and suggestions.
        """
        return EntityMatch(
            entity_id=None,
            wikidata_qid=None,
            resolution_tier=ResolutionTier.FAILED,
            match_confidence=0.0,
            original_query=query,
            matched_label=None,
            suggestions=self._generate_suggestions(query),
        )


__all__ = [
    "EntityMatch",
    "EntityResolver",
    "ResolutionTier",
    "KNOWN_ENTITIES",
]
