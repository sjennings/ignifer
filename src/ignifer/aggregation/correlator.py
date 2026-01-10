"""Aggregator and correlation module for multi-source OSINT results.

Queries multiple adapters concurrently, combines results, identifies
corroborating evidence, and highlights conflicting information.

Implements:
- FR23: Corroborating evidence presentation
- FR24: Conflicting information highlighting
- FR25: Source contribution visibility
"""

import asyncio
import hashlib
import logging
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ignifer.adapters.base import AdapterError, OSINTAdapter
from ignifer.aggregation.relevance import SourceRelevanceEngine
from ignifer.config import Settings, get_settings
from ignifer.models import (
    ConfidenceLevel,
    OSINTResult,
    QualityTier,
    QueryParams,
    ResultStatus,
)

logger = logging.getLogger(__name__)


class CorroborationStatus(str, Enum):
    """Finding corroboration status."""

    CORROBORATED = "corroborated"  # 2+ sources agree
    SINGLE_SOURCE = "single_source"  # Only one source
    CONFLICTING = "conflicting"  # Sources disagree


class SourceContribution(BaseModel):
    """Contribution from a single source to a finding."""

    model_config = ConfigDict(str_strip_whitespace=True)

    source_name: str
    data: dict[str, Any]
    quality_tier: QualityTier
    retrieved_at: datetime
    source_url: str | None = None
    confidence: ConfidenceLevel | None = None


class Finding(BaseModel):
    """A single finding with source attribution and corroboration status."""

    model_config = ConfigDict(str_strip_whitespace=True)

    topic: str  # Category/topic of finding
    content: str  # The actual finding content
    sources: list[SourceContribution]  # Contributing sources
    status: CorroborationStatus
    # "Corroborated by [Source A, Source B]" or "Single source - corroboration not possible"
    corroboration_note: str | None = None
    # Positive for corroborated, 0 for single, negative for conflicting
    confidence_boost: float = 0.0


class Conflict(BaseModel):
    """A conflict between sources on a specific topic."""

    model_config = ConfigDict(str_strip_whitespace=True)

    topic: str
    source_a: SourceContribution
    source_a_value: str
    source_b: SourceContribution
    source_b_value: str
    suggested_authority: str | None = None  # Source name with highest quality tier
    # "Conflicting: Source A says X, Source B says Y"
    resolution_note: str | None = None

    @property
    def perspectives(self) -> list[SourceContribution]:
        """Return list of perspectives for API compatibility."""
        return [self.source_a, self.source_b]


class AggregatedResult(BaseModel):
    """Complete aggregated result from multiple sources."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str
    findings: list[Finding] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    sources_queried: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)
    overall_confidence: float  # 0.0 to 1.0
    source_attributions: list[SourceContribution] = Field(default_factory=list)

    def to_confidence_level(self) -> ConfidenceLevel:
        """Convert overall_confidence float to ConfidenceLevel enum.

        Maps the 0.0-1.0 float to ICD 203 confidence levels based on
        percentage thresholds.

        Returns:
            ConfidenceLevel corresponding to the overall_confidence value.
        """
        return ConfidenceLevel.from_percentage(self.overall_confidence)


class Correlator:
    """Multi-source result aggregation and correlation engine.

    Queries multiple adapters concurrently, combines results,
    identifies corroboration, and highlights conflicts.

    Implements:
    - FR23: Corroborating evidence presentation
    - FR24: Conflicting information highlighting
    - FR25: Source contribution visibility
    """

    def __init__(
        self,
        adapters: dict[str, OSINTAdapter] | None = None,
        relevance_engine: SourceRelevanceEngine | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the correlator.

        Args:
            adapters: Dict mapping source names to adapter instances.
            relevance_engine: Optional SourceRelevanceEngine for source selection.
            settings: Optional Settings instance.
        """
        self._adapters = adapters or {}
        self._relevance_engine = relevance_engine or SourceRelevanceEngine()
        self._settings = settings or get_settings()

    async def aggregate(
        self,
        query: str,
        sources: list[str] | None = None,
    ) -> AggregatedResult:
        """Aggregate results from multiple sources.

        Args:
            query: The query to execute across sources.
            sources: Optional list of source names to query.
                     If None, uses SourceRelevanceEngine for selection.

        Returns:
            AggregatedResult with findings, conflicts, and attribution.
        """
        logger.info(f"Aggregating results for query: {query}")

        # Determine which sources to query
        if sources is None:
            relevance_result = await self._relevance_engine.analyze(query)
            sources = relevance_result.get_high_relevance_sources()
            if not sources:
                # Fall back to all available sources
                sources = relevance_result.available_sources
            logger.debug(f"Selected sources via relevance engine: {sources}")
        else:
            logger.debug(f"Using provided sources: {sources}")

        # Query sources concurrently
        source_results = await self._query_sources_concurrently(query, sources)

        # Track which sources succeeded and failed
        sources_queried = []
        sources_failed = []
        for source_name in sources:
            if source_results.get(source_name) is not None:
                sources_queried.append(source_name)
            else:
                sources_failed.append(source_name)

        # Extract findings from results
        findings_by_topic = self._extract_findings(source_results)

        # Detect corroboration
        findings = self._detect_corroboration(findings_by_topic)

        # Detect conflicts
        conflicts = self._detect_conflicts(source_results)

        # Calculate overall confidence
        overall_confidence = self._calculate_confidence(findings, conflicts)

        # Build source attributions
        source_attributions = self._build_attributions(source_results)

        result = AggregatedResult(
            query=query,
            findings=findings,
            conflicts=conflicts,
            sources_queried=sources_queried,
            sources_failed=sources_failed,
            overall_confidence=overall_confidence,
            source_attributions=source_attributions,
        )

        logger.info(
            f"Aggregation complete: {len(findings)} findings, "
            f"{len(conflicts)} conflicts, {len(sources_queried)} sources succeeded"
        )

        return result

    async def _query_sources_concurrently(
        self,
        query: str,
        sources: list[str],
    ) -> dict[str, OSINTResult | None]:
        """Query multiple sources concurrently.

        Returns dict mapping source_name to result (or None on failure).
        """

        async def query_single(source_name: str) -> tuple[str, OSINTResult | None]:
            adapter = self._adapters.get(source_name)
            if adapter is None:
                logger.warning(f"No adapter found for source: {source_name}")
                return source_name, None

            try:
                params = QueryParams(query=query)
                result = await adapter.query(params)
                logger.debug(f"Source {source_name} returned {len(result.results)} results")
                return source_name, result
            except AdapterError as e:
                logger.warning(f"Adapter {source_name} failed: {e}")
                return source_name, None
            except Exception as e:
                logger.error(f"Unexpected error from {source_name}: {e}")
                return source_name, None

        # Query all sources concurrently
        tasks = [query_single(source) for source in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dict, handling any exceptions
        result_dict: dict[str, OSINTResult | None] = {}
        for item in results:
            if isinstance(item, BaseException):
                logger.error(f"Unexpected gather exception: {item}")
                continue
            # item is now narrowed to tuple[str, OSINTResult | None]
            source_name, result = item
            result_dict[source_name] = result

        return result_dict

    def _extract_findings(
        self,
        source_results: dict[str, OSINTResult | None],
    ) -> dict[str, list[tuple[str, SourceContribution, str]]]:
        """Extract findings organized by topic from source results.

        Returns a dict mapping normalized topic to list of
        (source_name, contribution, content_value) tuples.
        """
        findings_by_topic: dict[str, list[tuple[str, SourceContribution, str]]] = {}

        for source_name, result in source_results.items():
            if result is None or result.status != ResultStatus.SUCCESS:
                continue

            # Get adapter for quality tier
            adapter = self._adapters.get(source_name)
            quality_tier = adapter.base_quality_tier if adapter else QualityTier.MEDIUM

            # Get source URL from result sources if available
            source_url = None
            if result.sources:
                source_url = result.sources[0].metadata.source_url

            for item in result.results:
                # Extract topic and content from result item
                topic, content = self._extract_topic_content(item, source_name)
                if not topic or not content:
                    continue

                normalized_topic = topic.lower().strip()

                contribution = SourceContribution(
                    source_name=source_name,
                    data=item,
                    quality_tier=quality_tier,
                    retrieved_at=result.retrieved_at,
                    source_url=source_url,
                )

                if normalized_topic not in findings_by_topic:
                    findings_by_topic[normalized_topic] = []
                findings_by_topic[normalized_topic].append((source_name, contribution, content))

        return findings_by_topic

    def _extract_topic_content(
        self,
        item: dict[str, Any],
        source_name: str,
    ) -> tuple[str, str]:
        """Extract topic and content from a result item.

        Different sources have different field structures.
        Returns (topic, content) tuple.

        Special handling:
        - GDELT: Each article is a unique finding (topic = "news_article_<hash>")
        - Other sources: Group by topic/category fields for corroboration
        """
        # Try common field patterns
        topic = ""
        content = ""

        # Special handling for news sources (GDELT)
        # Each article should be its own finding, not grouped together
        if source_name == "gdelt":
            # Use title as content
            content = str(item.get("title", ""))
            # Create unique topic per article using URL hash
            url = item.get("url", "")
            if url:
                # Use URL hash to make each article unique
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                topic = f"news_article_{url_hash}"
            else:
                # Fallback to title hash if no URL
                title_hash = hashlib.md5(content.encode()).hexdigest()[:8]
                topic = f"news_article_{title_hash}"
            return topic, content

        # Topic extraction - try various field names
        topic_fields = ["topic", "category", "type", "event_type", "indicator"]
        for field in topic_fields:
            if field in item and item[field]:
                topic = str(item[field])
                break

        # If no topic field, use source name as topic
        if not topic:
            topic = source_name

        # Content extraction - try various field names
        content_fields = [
            "title",
            "name",
            "description",
            "summary",
            "content",
            "value",
            "text",
        ]
        for field in content_fields:
            if field in item and item[field]:
                content = str(item[field])
                break

        # Fallback: use string representation of first few fields
        if not content and item:
            first_values = list(item.values())[:3]
            content = " | ".join(str(v) for v in first_values if v)

        return topic, content

    def _detect_corroboration(
        self,
        findings_by_topic: dict[str, list[tuple[str, SourceContribution, str]]],
    ) -> list[Finding]:
        """Detect corroboration across sources.

        Groups findings by normalized topic and marks as corroborated
        when 2+ sources have findings on the same topic.
        """
        corroborated_findings: list[Finding] = []

        for topic, source_findings in findings_by_topic.items():
            unique_sources = set(sf[0] for sf in source_findings)

            if len(unique_sources) >= 2:
                # CORROBORATED - combine into single finding
                sources = [sf[1] for sf in source_findings]
                # Use content from highest quality source
                best_content = self._get_best_content(source_findings)
                source_list = ", ".join(sorted(unique_sources))

                finding = Finding(
                    topic=topic,
                    content=best_content,
                    sources=sources,
                    status=CorroborationStatus.CORROBORATED,
                    corroboration_note=f"Corroborated by [{source_list}]",
                    confidence_boost=0.2,  # Boost confidence for corroboration
                )
                corroborated_findings.append(finding)
            else:
                # SINGLE_SOURCE
                source_name, contribution, content = source_findings[0]
                note = f"Single source: [{source_name}] - corroboration not possible"
                finding = Finding(
                    topic=topic,
                    content=content,
                    sources=[contribution],
                    status=CorroborationStatus.SINGLE_SOURCE,
                    corroboration_note=note,
                    confidence_boost=0.0,  # No boost for single source
                )
                corroborated_findings.append(finding)

        return corroborated_findings

    def _get_best_content(
        self,
        source_findings: list[tuple[str, SourceContribution, str]],
    ) -> str:
        """Get content from the highest quality source."""
        # Sort by quality tier (HIGH > MEDIUM > LOW)
        sorted_findings = sorted(
            source_findings,
            key=lambda sf: sf[1].quality_tier.ordering,
        )

        return sorted_findings[0][2] if sorted_findings else ""

    def _detect_conflicts(
        self,
        source_results: dict[str, OSINTResult | None],
    ) -> list[Conflict]:
        """Detect conflicting information across sources.

        Identifies cases where sources disagree on the same data point.
        Never suppresses conflicting information - both views are preserved.
        """
        conflicts: list[Conflict] = []

        # Get successful results only
        valid_results = {
            name: result
            for name, result in source_results.items()
            if result is not None and result.status == ResultStatus.SUCCESS
        }

        if len(valid_results) < 2:
            return conflicts

        # Compare results pairwise for key fields
        source_names = list(valid_results.keys())
        for i, source_a_name in enumerate(source_names):
            for source_b_name in source_names[i + 1 :]:
                result_a = valid_results[source_a_name]
                result_b = valid_results[source_b_name]

                # Check for conflicting values on matching entities
                pair_conflicts = self._find_conflicts_between_sources(
                    source_a_name,
                    result_a,
                    source_b_name,
                    result_b,
                )
                conflicts.extend(pair_conflicts)

        return conflicts

    def _find_conflicts_between_sources(
        self,
        source_a_name: str,
        result_a: OSINTResult,
        source_b_name: str,
        result_b: OSINTResult,
    ) -> list[Conflict]:
        """Find conflicts between two source results."""
        conflicts: list[Conflict] = []

        # Key fields that might conflict
        conflict_fields = [
            "status",
            "sanctioned",
            "is_sanctioned",
            "pep",
            "is_pep",
            "active",
            "is_active",
        ]

        # Get adapter quality tiers
        adapter_a = self._adapters.get(source_a_name)
        adapter_b = self._adapters.get(source_b_name)
        quality_a = adapter_a.base_quality_tier if adapter_a else QualityTier.MEDIUM
        quality_b = adapter_b.base_quality_tier if adapter_b else QualityTier.MEDIUM

        # Look for matching entities with conflicting values
        for item_a in result_a.results:
            for item_b in result_b.results:
                # Check if items refer to same entity (by name or identifier)
                if not self._items_match_entity(item_a, item_b):
                    continue

                # Check for conflicting field values
                for field in conflict_fields:
                    if field not in item_a or field not in item_b:
                        continue

                    value_a = item_a[field]
                    value_b = item_b[field]

                    # Skip if values are the same or both null
                    if value_a == value_b:
                        continue
                    if value_a is None or value_b is None:
                        continue

                    # Get source URL
                    url_a = result_a.sources[0].metadata.source_url if result_a.sources else None
                    url_b = result_b.sources[0].metadata.source_url if result_b.sources else None

                    contribution_a = SourceContribution(
                        source_name=source_a_name,
                        data=item_a,
                        quality_tier=quality_a,
                        retrieved_at=result_a.retrieved_at,
                        source_url=url_a,
                    )

                    contribution_b = SourceContribution(
                        source_name=source_b_name,
                        data=item_b,
                        quality_tier=quality_b,
                        retrieved_at=result_b.retrieved_at,
                        source_url=url_b,
                    )

                    # Determine suggested authority based on quality tier
                    suggested = self._suggest_authority(
                        source_a_name, quality_a, source_b_name, quality_b
                    )

                    # Build resolution note per AC4
                    resolution_note = (
                        f"Conflicting: {source_a_name} says {value_a}, "
                        f"{source_b_name} says {value_b}"
                    )

                    conflict = Conflict(
                        topic=field,
                        source_a=contribution_a,
                        source_a_value=str(value_a),
                        source_b=contribution_b,
                        source_b_value=str(value_b),
                        suggested_authority=suggested,
                        resolution_note=resolution_note,
                    )
                    conflicts.append(conflict)

        return conflicts

    def _items_match_entity(
        self,
        item_a: dict[str, Any],
        item_b: dict[str, Any],
    ) -> bool:
        """Check if two items refer to the same entity."""
        # Check by identifier fields
        id_fields = ["id", "entity_id", "imo", "mmsi", "icao24", "callsign", "name"]

        for field in id_fields:
            if field in item_a and field in item_b:
                val_a = str(item_a[field]).lower().strip() if item_a[field] else ""
                val_b = str(item_b[field]).lower().strip() if item_b[field] else ""
                if val_a and val_b and val_a == val_b:
                    return True

        return False

    def _suggest_authority(
        self,
        source_a_name: str,
        quality_a: QualityTier,
        source_b_name: str,
        quality_b: QualityTier,
    ) -> str | None:
        """Suggest which source is more authoritative based on quality tier."""
        order_a = quality_a.ordering
        order_b = quality_b.ordering

        if order_a < order_b:
            return source_a_name
        elif order_b < order_a:
            return source_b_name
        else:
            # Same quality tier - no suggestion
            return None

    def _calculate_confidence(
        self,
        findings: list[Finding],
        conflicts: list[Conflict],
    ) -> float:
        """Calculate overall confidence for aggregated result.

        Returns a float between 0.0 and 1.0.

        Rules:
        - Base confidence: 0.5
        - Corroboration bonus: +0.1 per corroborated finding (max +0.3)
        - Conflict penalty: -0.1 per conflict (max -0.3)
        - Single source penalty: -0.05 if all findings are single source
        """
        if not findings:
            return 0.2  # Low confidence if no findings

        base_confidence = 0.5

        # Corroboration bonus
        corroborated_count = sum(
            1 for f in findings if f.status == CorroborationStatus.CORROBORATED
        )
        corroboration_bonus = min(corroborated_count * 0.1, 0.3)

        # Conflict penalty
        conflict_penalty = min(len(conflicts) * 0.1, 0.3)

        # Single source penalty
        single_source_count = sum(
            1 for f in findings if f.status == CorroborationStatus.SINGLE_SOURCE
        )
        single_source_penalty = 0.05 if single_source_count == len(findings) else 0.0

        # Calculate final confidence
        confidence = (
            base_confidence + corroboration_bonus - conflict_penalty - single_source_penalty
        )

        # Clamp to valid range
        return max(0.0, min(1.0, confidence))

    def _build_attributions(
        self,
        source_results: dict[str, OSINTResult | None],
    ) -> list[SourceContribution]:
        """Build list of source attributions from results."""
        attributions: list[SourceContribution] = []

        for source_name, result in source_results.items():
            if result is None or result.status != ResultStatus.SUCCESS:
                continue

            adapter = self._adapters.get(source_name)
            quality_tier = adapter.base_quality_tier if adapter else QualityTier.MEDIUM

            source_url = None
            if result.sources:
                source_url = result.sources[0].metadata.source_url

            attribution = SourceContribution(
                source_name=source_name,
                data={"result_count": len(result.results)},
                quality_tier=quality_tier,
                retrieved_at=result.retrieved_at,
                source_url=source_url,
            )
            attributions.append(attribution)

        return attributions


__all__ = [
    "CorroborationStatus",
    "SourceContribution",
    "Finding",
    "Conflict",
    "AggregatedResult",
    "Correlator",
]
