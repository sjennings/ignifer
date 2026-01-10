"""Entity aggregation and resolution module.

Provides tiered entity resolution for cross-source matching
and source relevance analysis.
"""

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
    "EntityMatch",
    "EntityResolver",
    "ResolutionTier",
    "QueryType",
    "RelevanceResult",
    "RelevanceScore",
    "SourceRelevance",
    "SourceRelevanceEngine",
]
