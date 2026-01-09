# Story 3.2: Entity Resolution Module

Status: ready-for-dev

## Story

As a **developer**,
I want **a tiered entity resolution system**,
so that **entities can be matched across different data sources reliably**.

## Acceptance Criteria

1. **AC1: EntityMatch Model Created**
   - **Given** the models from Epic 1
   - **When** I create `src/ignifer/aggregation/entity_resolver.py`
   - **Then** `EntityMatch` Pydantic model includes:
     - `entity_id: str | None` - Internal entity identifier
     - `wikidata_qid: str | None` - Wikidata Q-ID if resolved
     - `resolution_tier: str` - Which tier matched ("exact", "normalized", "wikidata", "fuzzy", "failed")
     - `match_confidence: float` - 0.0 to 1.0 confidence score
     - `original_query: str` - The original search query
     - `matched_label: str | None` - The label that matched
     - `suggestions: list[str]` - Alternative query suggestions (on failure)

2. **AC2: EntityResolver Class Created**
   - **Given** the EntityMatch model
   - **When** I implement `EntityResolver` class
   - **Then** it has:
     - `__init__(wikidata_adapter: WikidataAdapter | None = None)`
     - `async resolve(query: str) -> EntityMatch`
     - Resolution tiers executed in order: exact → normalized → wikidata → fuzzy

3. **AC3: Tiered Resolution with Early Exit**
   - **Given** EntityResolver receives a query
   - **When** I call `await resolver.resolve("Vladimir Putin")`
   - **Then** it attempts resolution in order:
     1. **Exact match**: Direct string equality against known entities
     2. **Normalized match**: Lowercase, strip whitespace, remove diacritics
     3. **Wikidata lookup**: Query WikidataAdapter for Q-ID and aliases
     4. **Fuzzy match**: Levenshtein distance with configurable threshold
   - **And** STOPS at first successful tier
   - **And** logs which tier produced the match

4. **AC4: Exact Match Returns Confidence 1.0**
   - **Given** exact match succeeds against known entities
   - **When** resolution completes
   - **Then** returns `EntityMatch` with:
     - `resolution_tier = "exact"`
     - `match_confidence = 1.0`
     - `wikidata_qid` if known from entity registry

5. **AC5: Normalized Match Works**
   - **Given** normalized match succeeds
   - **When** resolution completes with "VLADIMIR PUTIN" or "vladimir  putin"
   - **Then** returns `EntityMatch` with:
     - `resolution_tier = "normalized"`
     - `match_confidence = 0.95`
     - Query normalized before matching

6. **AC6: Wikidata Lookup Integration**
   - **Given** WikidataAdapter is provided
   - **When** earlier tiers fail but Wikidata finds a match
   - **Then** returns `EntityMatch` with:
     - `resolution_tier = "wikidata"`
     - `match_confidence = 0.85` (reduced due to external lookup)
     - `wikidata_qid` populated from Wikidata response

7. **AC7: Fuzzy Match as Last Resort**
   - **Given** only fuzzy match succeeds
   - **When** Levenshtein distance is within threshold (e.g., 0.8 similarity)
   - **Then** returns `EntityMatch` with:
     - `resolution_tier = "fuzzy"`
     - `match_confidence = 0.7-0.9` (based on similarity score)
     - Warning logged about lower confidence

8. **AC8: Failed Resolution Returns Suggestions**
   - **Given** no match is found at any tier
   - **When** resolution completes
   - **Then** returns `EntityMatch` with:
     - `resolution_tier = "failed"`
     - `match_confidence = 0.0`
     - `suggestions` containing alternative query suggestions
     - `wikidata_qid = None`

9. **AC9: Tests Pass with Good Coverage**
   - **Given** the EntityResolver implementation
   - **When** I run `pytest tests/aggregation/test_entity_resolver.py -v`
   - **Then** all tests pass
   - **And** coverage for entity_resolver.py is ≥85%

## Tasks / Subtasks

- [ ] Task 1: Create aggregation package (AC: #1, #2)
  - [ ] 1.1: Create `src/ignifer/aggregation/` directory
  - [ ] 1.2: Create `src/ignifer/aggregation/__init__.py`
  - [ ] 1.3: Create `src/ignifer/aggregation/entity_resolver.py`

- [ ] Task 2: Implement EntityMatch model (AC: #1)
  - [ ] 2.1: Create `EntityMatch` Pydantic model with all fields
  - [ ] 2.2: Add `model_config` with ConfigDict
  - [ ] 2.3: Add helper method `is_successful() -> bool`
  - [ ] 2.4: Add `to_dict()` method for serialization

- [ ] Task 3: Implement ResolutionTier enum (AC: #3)
  - [ ] 3.1: Create `ResolutionTier` enum with values: EXACT, NORMALIZED, WIKIDATA, FUZZY, FAILED
  - [ ] 3.2: Add confidence score mapping per tier

- [ ] Task 4: Implement EntityResolver class (AC: #2)
  - [ ] 4.1: Create `EntityResolver` class with `__init__(wikidata_adapter=None)`
  - [ ] 4.2: Initialize internal entity registry (dict of known entities)
  - [ ] 4.3: Implement `async resolve(query: str) -> EntityMatch`
  - [ ] 4.4: Implement private `_log_resolution()` helper

- [ ] Task 5: Implement Exact Match tier (AC: #4)
  - [ ] 5.1: Create `_try_exact_match(query: str) -> EntityMatch | None`
  - [ ] 5.2: Check against known entity registry
  - [ ] 5.3: Return EntityMatch with confidence=1.0 if found

- [ ] Task 6: Implement Normalized Match tier (AC: #5)
  - [ ] 6.1: Create `_normalize(query: str) -> str` helper
  - [ ] 6.2: Implement lowercase, strip whitespace, collapse spaces
  - [ ] 6.3: Implement diacritics removal (using unicodedata.normalize)
  - [ ] 6.4: Create `_try_normalized_match(query: str) -> EntityMatch | None`
  - [ ] 6.5: Return EntityMatch with confidence=0.95 if found

- [ ] Task 7: Implement Wikidata Lookup tier (AC: #6)
  - [ ] 7.1: Create `async _try_wikidata_lookup(query: str) -> EntityMatch | None`
  - [ ] 7.2: Call WikidataAdapter.query() if adapter available
  - [ ] 7.3: Extract Q-ID from top result
  - [ ] 7.4: Return EntityMatch with confidence=0.85 if found

- [ ] Task 8: Implement Fuzzy Match tier (AC: #7)
  - [ ] 8.1: Create `_try_fuzzy_match(query: str, threshold: float = 0.8) -> EntityMatch | None`
  - [ ] 8.2: Implement Levenshtein ratio calculation (use rapidfuzz if available, else stdlib)
  - [ ] 8.3: Compare against known entities
  - [ ] 8.4: Return EntityMatch with confidence based on similarity score

- [ ] Task 9: Implement Failed Resolution (AC: #8)
  - [ ] 9.1: Create `_create_failed_match(query: str) -> EntityMatch`
  - [ ] 9.2: Generate suggestions based on similar entities
  - [ ] 9.3: Return EntityMatch with tier="failed", confidence=0.0

- [ ] Task 10: Update package exports (AC: #2)
  - [ ] 10.1: Export EntityMatch and EntityResolver from `__init__.py`
  - [ ] 10.2: Export ResolutionTier enum

- [ ] Task 11: Create tests (AC: #9)
  - [ ] 11.1: Create `tests/aggregation/` directory
  - [ ] 11.2: Create `tests/aggregation/__init__.py`
  - [ ] 11.3: Create `tests/aggregation/test_entity_resolver.py`
  - [ ] 11.4: Test exact match scenario
  - [ ] 11.5: Test normalized match scenario
  - [ ] 11.6: Test Wikidata lookup scenario (mock adapter)
  - [ ] 11.7: Test fuzzy match scenario
  - [ ] 11.8: Test failed resolution with suggestions
  - [ ] 11.9: Test early exit (stops at first match)
  - [ ] 11.10: Test without WikidataAdapter (graceful degradation)

## Dev Notes

### CRITICAL: Architecture Compliance

**FROM project-context.md:**

1. **Stop entity resolution at first successful match** - don't over-resolve
2. **Log which tier matched** via `resolution_tier` field
3. **stdlib `logging` only** - use `logging.getLogger(__name__)`
4. **snake_case** for all JSON/model fields
5. **Pydantic ConfigDict** for model configuration

**Entity Resolution Rules (from architecture):**
- **Tiered resolution:** Exact → Normalized → Wikidata → Fuzzy
- **STOP at first successful tier** - do not proceed if earlier tier matches
- **Log which tier matched** via `resolution_tier` field

### Module Location

```
src/ignifer/
├── aggregation/           # NEW DIRECTORY
│   ├── __init__.py
│   └── entity_resolver.py
├── adapters/
│   └── wikidata.py        # From Story 3.1
└── models.py              # Existing models
```

### EntityMatch Model Design

```python
from enum import Enum
from pydantic import BaseModel, ConfigDict


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
    """Result of entity resolution."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    entity_id: str | None = None
    wikidata_qid: str | None = None
    resolution_tier: ResolutionTier
    match_confidence: float
    original_query: str
    matched_label: str | None = None
    suggestions: list[str] = []

    def is_successful(self) -> bool:
        """Check if resolution was successful."""
        return self.resolution_tier != ResolutionTier.FAILED
```

### EntityResolver Class Design

```python
"""Entity resolution module for cross-source matching."""

import logging
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ignifer.adapters.wikidata import WikidataAdapter

logger = logging.getLogger(__name__)


# Known entities registry (can be expanded)
KNOWN_ENTITIES: dict[str, dict[str, str]] = {
    "vladimir putin": {"qid": "Q7747", "label": "Vladimir Putin"},
    "joe biden": {"qid": "Q6279", "label": "Joe Biden"},
    "gazprom": {"qid": "Q102673", "label": "Gazprom"},
    # Add more as needed
}


class EntityResolver:
    """Tiered entity resolution system.

    Attempts resolution in order: exact → normalized → wikidata → fuzzy.
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
        self._wikidata = wikidata_adapter
        self._fuzzy_threshold = fuzzy_threshold

    async def resolve(self, query: str) -> EntityMatch:
        """Resolve an entity query through tiered matching.

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
        """Log the resolution result."""
        if match.is_successful():
            logger.info(
                f"Entity '{query}' resolved via {match.resolution_tier.value} "
                f"(confidence: {match.match_confidence:.2f})"
            )
        else:
            logger.warning(f"Entity '{query}' could not be resolved")

    # ... implementation methods follow
```

### Normalization Implementation

```python
import unicodedata
import re


def _normalize(self, query: str) -> str:
    """Normalize query string for comparison.

    - Lowercase
    - Strip whitespace
    - Collapse multiple spaces
    - Remove diacritics (NFD normalization)
    """
    # Lowercase and strip
    normalized = query.lower().strip()

    # Collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized)

    # Remove diacritics (accents)
    # NFD decomposes characters, then we filter out combining marks
    normalized = unicodedata.normalize('NFD', normalized)
    normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

    return normalized
```

### Fuzzy Matching

**Option 1: Use rapidfuzz (recommended if available)**
```python
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False


def _calculate_similarity(self, s1: str, s2: str) -> float:
    """Calculate string similarity ratio (0.0 to 1.0)."""
    if HAS_RAPIDFUZZ:
        return fuzz.ratio(s1, s2) / 100.0
    else:
        # Fallback: simple Levenshtein ratio using difflib
        from difflib import SequenceMatcher
        return SequenceMatcher(None, s1, s2).ratio()
```

**Option 2: Use stdlib difflib only (simpler)**
```python
from difflib import SequenceMatcher


def _calculate_similarity(self, s1: str, s2: str) -> float:
    """Calculate string similarity ratio (0.0 to 1.0)."""
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
```

**Recommendation:** Use stdlib `difflib.SequenceMatcher` to avoid adding a dependency. It's good enough for entity resolution.

### Wikidata Integration

```python
async def _try_wikidata_lookup(self, query: str) -> EntityMatch | None:
    """Try to resolve via Wikidata lookup."""
    if not self._wikidata:
        return None

    try:
        from ignifer.models import QueryParams, ResultStatus

        result = await self._wikidata.query(QueryParams(query=query))

        if result.status != ResultStatus.SUCCESS or not result.results:
            return None

        # Get top result
        top = result.results[0]
        qid = top.get("qid")
        label = top.get("label", query)

        if not qid:
            return None

        return EntityMatch(
            entity_id=qid,
            wikidata_qid=qid,
            resolution_tier=ResolutionTier.WIKIDATA,
            match_confidence=0.85,
            original_query=query,
            matched_label=label,
        )

    except Exception as e:
        logger.warning(f"Wikidata lookup failed for '{query}': {e}")
        return None
```

### Generating Suggestions

```python
def _generate_suggestions(self, query: str) -> list[str]:
    """Generate alternative query suggestions."""
    suggestions = []

    normalized = self._normalize(query)

    # Find similar known entities
    for known, data in KNOWN_ENTITIES.items():
        similarity = self._calculate_similarity(normalized, known)
        if 0.5 <= similarity < self._fuzzy_threshold:
            suggestions.append(f"Did you mean '{data['label']}'?")

    # Generic suggestions
    if not suggestions:
        suggestions = [
            "Try checking the spelling",
            "Try using a more complete name",
            "Try using the Wikidata Q-ID if known",
        ]

    return suggestions[:3]  # Limit to 3 suggestions
```

### Test Patterns

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from ignifer.aggregation.entity_resolver import (
    EntityMatch,
    EntityResolver,
    ResolutionTier,
)


class TestEntityResolver:
    """Tests for EntityResolver."""

    @pytest.mark.asyncio
    async def test_resolve_exact_match_returns_confidence_one(self) -> None:
        """Exact match should return confidence 1.0."""
        resolver = EntityResolver()
        match = await resolver.resolve("Vladimir Putin")

        assert match.resolution_tier == ResolutionTier.EXACT
        assert match.match_confidence == 1.0
        assert match.wikidata_qid == "Q7747"

    @pytest.mark.asyncio
    async def test_resolve_normalized_match_handles_case(self) -> None:
        """Normalized match should handle case differences."""
        resolver = EntityResolver()
        match = await resolver.resolve("VLADIMIR PUTIN")

        assert match.resolution_tier == ResolutionTier.NORMALIZED
        assert match.match_confidence == 0.95

    @pytest.mark.asyncio
    async def test_resolve_stops_at_first_match(self) -> None:
        """Resolution should stop at first successful tier."""
        resolver = EntityResolver()
        match = await resolver.resolve("vladimir putin")  # lowercase - would match normalized

        # Should match at exact (lowercase is in registry)
        # OR normalized if exact doesn't match
        assert match.is_successful()
        assert match.resolution_tier in [ResolutionTier.EXACT, ResolutionTier.NORMALIZED]

    @pytest.mark.asyncio
    async def test_resolve_wikidata_fallback(self) -> None:
        """Wikidata should be tried when local tiers fail."""
        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock(return_value=MagicMock(
            status=MagicMock(value="success"),
            results=[{"qid": "Q12345", "label": "Test Entity"}]
        ))

        resolver = EntityResolver(wikidata_adapter=mock_adapter)
        match = await resolver.resolve("Unknown Entity XYZ")

        mock_adapter.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_failed_returns_suggestions(self) -> None:
        """Failed resolution should include suggestions."""
        resolver = EntityResolver()  # No Wikidata adapter
        match = await resolver.resolve("Completely Unknown Entity XYZABC")

        assert match.resolution_tier == ResolutionTier.FAILED
        assert match.match_confidence == 0.0
        assert len(match.suggestions) > 0
```

### Dependencies

- **Requires:** Story 3.1 (WikidataAdapter) - for Wikidata tier
- **Blocked by:** None (can work without WikidataAdapter)
- **Enables:** Story 3.3 (Entity Lookup Tool)

### Previous Story Intelligence

From Story 3-1 (WikidataAdapter):
- WikidataAdapter returns `OSINTResult` with `results` list
- Each result has `qid`, `label`, `description` fields
- Use `QueryParams(query=...)` to call adapter

From project-context.md:
- Entity resolution MUST stop at first successful match
- Log which tier matched for debugging
- Use stdlib logging only

### Import Pattern

Use TYPE_CHECKING to avoid circular imports:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ignifer.adapters.wikidata import WikidataAdapter
```

### Package Structure After Implementation

```
src/ignifer/
├── __init__.py
├── aggregation/
│   ├── __init__.py           # Exports EntityMatch, EntityResolver, ResolutionTier
│   └── entity_resolver.py    # Main implementation
├── adapters/
│   ├── __init__.py
│   ├── base.py
│   ├── gdelt.py
│   ├── worldbank.py
│   └── wikidata.py           # From Story 3.1
└── models.py

tests/
├── aggregation/
│   ├── __init__.py
│   └── test_entity_resolver.py
└── adapters/
    ├── test_gdelt.py
    ├── test_worldbank.py
    └── test_wikidata.py
```
