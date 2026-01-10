"""Entity aggregation and resolution module.

Provides tiered entity resolution for cross-source matching,
source relevance analysis, and multi-source correlation.
"""

from ignifer.aggregation.correlator import (
    AggregatedResult,
    Conflict,
    CorroborationStatus,
    Correlator,
    Finding,
    SourceContribution,
)
from ignifer.aggregation.entity_resolver import (
    EntityMatch,
    EntityResolver,
    ResolutionTier,
)
from ignifer.aggregation.relevance import (
    QueryType,
    RelevanceResult,
    RelevanceScore,
    SourceRelevance,
    SourceRelevanceEngine,
)

__all__ = [
    # Correlator exports
    "AggregatedResult",
    "Conflict",
    "CorroborationStatus",
    "Correlator",
    "Finding",
    "SourceContribution",
    # Entity resolver exports
    "EntityMatch",
    "EntityResolver",
    "ResolutionTier",
    # Relevance exports
    "QueryType",
    "RelevanceResult",
    "RelevanceScore",
    "SourceRelevance",
    "SourceRelevanceEngine",
]
