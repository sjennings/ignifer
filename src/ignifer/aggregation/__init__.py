"""Entity aggregation and resolution module.

Provides tiered entity resolution for cross-source matching.
"""

from ignifer.aggregation.entity_resolver import (
    EntityMatch,
    EntityResolver,
    ResolutionTier,
)

__all__ = [
    "EntityMatch",
    "EntityResolver",
    "ResolutionTier",
]
