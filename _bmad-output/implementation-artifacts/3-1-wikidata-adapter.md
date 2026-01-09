# Story 3.1: Wikidata Adapter

Status: ready-for-dev

## Story

As a **researcher**,
I want **to query Wikidata for entity information**,
so that **I can get authoritative data about people, organizations, places, and things**.

## Acceptance Criteria

1. **AC1: WikidataAdapter Class Created**
   - **Given** the adapter protocol from Epic 1
   - **When** I create `src/ignifer/adapters/wikidata.py`
   - **Then** `WikidataAdapter` class:
     - Implements `OSINTAdapter` protocol
     - Has `source_name = "wikidata"`
     - Has `base_quality_tier = QualityTier.HIGH`
     - Uses adapter-owned httpx client (NOT SPARQLWrapper - see Dev Notes)
     - Creates client lazily via `_get_client()` pattern

2. **AC2: Entity Search Query Works**
   - **Given** WikidataAdapter is instantiated
   - **When** I call `await adapter.query(QueryParams(query="Vladimir Putin"))`
   - **Then** it executes search against Wikidata API
   - **And** returns `OSINTResult` containing entity data:
     - Wikidata Q-ID (e.g., Q7747)
     - Labels (primary language + English)
     - Aliases and alternative names
     - Description
     - Key properties (instance of, occupation, country, etc.)
   - **And** includes source attribution with Wikidata URL and retrieval timestamp

3. **AC3: Multiple Results Handling**
   - **Given** an entity search returns multiple matches
   - **When** I call `await adapter.query(QueryParams(query="Paris"))`
   - **Then** returns ranked results (most notable first)
   - **And** each result includes Q-ID and description for disambiguation
   - **And** limits to top 5-10 results

4. **AC4: Direct Q-ID Lookup Works**
   - **Given** a Wikidata Q-ID is provided
   - **When** I call `await adapter.lookup_by_qid("Q7747")`
   - **Then** returns full entity details for that specific Q-ID
   - **And** bypasses search, directly fetching entity data via wbgetentities API
   - **And** includes related entities with their Q-IDs

5. **AC5: Caching with 7-Day TTL**
   - **Given** WikidataAdapter is configured with CacheManager
   - **When** the same query is made twice within 7 days
   - **Then** second call returns cached result
   - **And** cache key includes query type (search vs qid) for isolation
   - **And** uses `settings.ttl_wikidata` (604800 seconds)

6. **AC6: Error Handling Follows Contract**
   - **Given** Wikidata API times out
   - **When** the adapter encounters the timeout
   - **Then** it raises `AdapterTimeoutError`
   - **And** rate limits return `OSINTResult(status=ResultStatus.RATE_LIMITED)`
   - **And** no results return `OSINTResult(status=ResultStatus.NO_DATA)`
   - **And** malformed JSON raises `AdapterParseError`

7. **AC7: Health Check Works**
   - **Given** WikidataAdapter instance
   - **When** I call `await adapter.health_check()`
   - **Then** returns `True` if Wikidata API is reachable
   - **And** returns `False` on connection failure

8. **AC8: Tests Pass with Good Coverage**
   - **Given** the WikidataAdapter implementation
   - **When** I run `pytest tests/adapters/test_wikidata.py -v`
   - **Then** all tests pass
   - **And** coverage for wikidata.py is ≥80%

## Tasks / Subtasks

- [ ] Task 1: Create WikidataAdapter class (AC: #1)
  - [ ] 1.1: Create `src/ignifer/adapters/wikidata.py`
  - [ ] 1.2: Implement `source_name` and `base_quality_tier` properties
  - [ ] 1.3: Create adapter-owned httpx.AsyncClient via `_get_client()`
  - [ ] 1.4: Add `async def close()` method for cleanup

- [ ] Task 2: Implement entity search via wbsearchentities API (AC: #2, #3)
  - [ ] 2.1: Implement `async query(params: QueryParams) -> OSINTResult`
  - [ ] 2.2: Use Wikidata `wbsearchentities` action for text search
  - [ ] 2.3: Parse search results into normalized format
  - [ ] 2.4: For each result, fetch basic properties via wbgetentities
  - [ ] 2.5: Rank results by search relevance (Wikidata provides this)
  - [ ] 2.6: Limit to top 5-10 results
  - [ ] 2.7: Return `OSINTResult` with proper attribution

- [ ] Task 3: Implement direct Q-ID lookup (AC: #4)
  - [ ] 3.1: Implement `async lookup_by_qid(qid: str) -> OSINTResult`
  - [ ] 3.2: Use Wikidata `wbgetentities` action with Q-ID
  - [ ] 3.3: Extract labels, aliases, descriptions, claims
  - [ ] 3.4: Parse key properties (P31 instance of, P106 occupation, etc.)
  - [ ] 3.5: Extract related entities with their Q-IDs
  - [ ] 3.6: Return comprehensive entity data

- [ ] Task 4: Implement property extraction helpers (AC: #2, #4)
  - [ ] 4.1: Create `_extract_labels(entity_data)` → dict of language:label
  - [ ] 4.2: Create `_extract_aliases(entity_data)` → list of aliases
  - [ ] 4.3: Create `_extract_claims(entity_data)` → dict of property:values
  - [ ] 4.4: Define KEY_PROPERTIES list for common properties to extract

- [ ] Task 5: Integrate caching (AC: #5)
  - [ ] 5.1: Accept CacheManager in constructor
  - [ ] 5.2: Generate cache keys: `wikidata:search:{query_hash}` and `wikidata:qid:{qid}`
  - [ ] 5.3: Check cache before API calls
  - [ ] 5.4: Store results with 7-day TTL

- [ ] Task 6: Implement error handling (AC: #6)
  - [ ] 6.1: Catch httpx.TimeoutException → AdapterTimeoutError
  - [ ] 6.2: Handle rate limits (429) → ResultStatus.RATE_LIMITED
  - [ ] 6.3: Handle empty search results → ResultStatus.NO_DATA
  - [ ] 6.4: Handle malformed JSON → AdapterParseError

- [ ] Task 7: Implement health check (AC: #7)
  - [ ] 7.1: Create simple API ping query
  - [ ] 7.2: Return True on success, False on failure

- [ ] Task 8: Update exports (AC: #1)
  - [ ] 8.1: Add WikidataAdapter to `adapters/__init__.py`

- [ ] Task 9: Create tests (AC: #8)
  - [ ] 9.1: Create `tests/adapters/test_wikidata.py`
  - [ ] 9.2: Create `tests/fixtures/wikidata_search.json`
  - [ ] 9.3: Create `tests/fixtures/wikidata_entity.json`
  - [ ] 9.4: Test entity search query
  - [ ] 9.5: Test multiple results handling
  - [ ] 9.6: Test direct Q-ID lookup
  - [ ] 9.7: Test cache hit behavior
  - [ ] 9.8: Test timeout error handling
  - [ ] 9.9: Test no data scenario

## Dev Notes

### CRITICAL: Architecture Compliance

**FROM project-context.md:**

1. **Adapter-owned httpx clients** - never shared across adapters
2. **`{Source}Adapter` naming** - class MUST be `WikidataAdapter`
3. **stdlib `logging` only** - use `logging.getLogger(__name__)`
4. **ISO 8601 + timezone** for all datetime
5. **snake_case** for all JSON fields
6. **QualityTier.HIGH** - Wikidata is authoritative, curated data

**FROM architecture.md - TTL Defaults:**

| Source | TTL | Rationale |
|--------|-----|-----------|
| Wikidata | 7 days | Entity data rarely changes |

Already configured in `config.py`: `ttl_wikidata: int = 604800`

### WHY NOT SPARQLWrapper

The epics mention SPARQLWrapper, but we should use **httpx directly** for these reasons:

1. **Consistency**: All other adapters use httpx
2. **Async support**: SPARQLWrapper is sync-only, would need `asyncio.to_thread()`
3. **Simpler**: Wikidata API actions are REST-based, no need for SPARQL complexity
4. **Control**: Direct HTTP gives us full control over timeouts, retries, caching

**Use Wikidata API actions instead of SPARQL:**
- `wbsearchentities` - Text search for entities
- `wbgetentities` - Fetch entity details by Q-ID

### Wikidata API Reference

**Base URL:** `https://www.wikidata.org/w/api.php`

**Entity Search (wbsearchentities):**
```
GET /w/api.php?action=wbsearchentities
  &search=Vladimir Putin
  &language=en
  &limit=10
  &format=json
```

Response:
```json
{
  "search": [
    {
      "id": "Q7747",
      "title": "Q7747",
      "pageid": 7896,
      "display": {
        "label": {"value": "Vladimir Putin", "language": "en"},
        "description": {"value": "President of Russia", "language": "en"}
      },
      "label": "Vladimir Putin",
      "description": "President of Russia",
      "match": {"type": "label", "language": "en", "text": "Vladimir Putin"}
    }
  ],
  "success": 1
}
```

**Entity Details (wbgetentities):**
```
GET /w/api.php?action=wbgetentities
  &ids=Q7747
  &props=labels|descriptions|aliases|claims
  &languages=en
  &format=json
```

Response structure:
```json
{
  "entities": {
    "Q7747": {
      "type": "item",
      "id": "Q7747",
      "labels": {"en": {"language": "en", "value": "Vladimir Putin"}},
      "descriptions": {"en": {"language": "en", "value": "President of Russia"}},
      "aliases": {"en": [{"language": "en", "value": "Putin"}, ...]},
      "claims": {
        "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],  // instance of: human
        "P106": [...],  // occupation
        "P27": [...]    // country of citizenship
      }
    }
  },
  "success": 1
}
```

### Key Wikidata Properties to Extract

| Property | Code | Description |
|----------|------|-------------|
| instance of | P31 | What type of entity (person, organization, etc.) |
| occupation | P106 | Person's occupation |
| country | P17 | Country associated with entity |
| country of citizenship | P27 | Person's citizenship |
| headquarters location | P159 | Organization's HQ |
| inception | P571 | When founded/created |
| official website | P856 | URL |
| image | P18 | Wikimedia Commons image |
| coordinate location | P625 | Geographic coordinates |

```python
KEY_PROPERTIES = {
    "P31": "instance_of",
    "P106": "occupation",
    "P17": "country",
    "P27": "citizenship",
    "P159": "headquarters",
    "P571": "inception",
    "P856": "website",
    "P625": "coordinates",
}
```

### Adapter Class Pattern

Follow the existing WorldBankAdapter pattern:

```python
"""Wikidata adapter for entity information."""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from ignifer.adapters.base import AdapterParseError, AdapterTimeoutError
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

# Key properties to extract from Wikidata claims
KEY_PROPERTIES = {
    "P31": "instance_of",
    "P106": "occupation",
    # ... etc
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

    def __init__(self, cache: CacheManager | None = None) -> None:
        self._client: httpx.AsyncClient | None = None
        self._cache = cache

    @property
    def source_name(self) -> str:
        return "wikidata"

    @property
    def base_quality_tier(self) -> QualityTier:
        return QualityTier.HIGH

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.DEFAULT_TIMEOUT),
                headers={"User-Agent": "Ignifer/1.0 (OSINT research tool)"},
            )
        return self._client

    async def query(self, params: QueryParams) -> OSINTResult:
        """Search for entities matching the query."""
        # Implementation here
        ...

    async def lookup_by_qid(self, qid: str) -> OSINTResult:
        """Fetch entity details by Wikidata Q-ID."""
        # Implementation here
        ...

    async def health_check(self) -> bool:
        """Check if Wikidata API is reachable."""
        ...

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
```

### Result Data Structure

For entity search results:
```python
results = [
    {
        "qid": "Q7747",
        "label": "Vladimir Putin",
        "description": "President of Russia",
        "aliases": ["Putin", "V. Putin"],
        "instance_of": "human",
        "instance_of_qid": "Q5",
    },
    # ... more results
]
```

For full entity details:
```python
results = [
    {
        "qid": "Q7747",
        "label": "Vladimir Putin",
        "description": "President of Russia",
        "aliases": ["Putin", "V. Putin", "Владимир Путин"],
        "properties": {
            "instance_of": {"value": "human", "qid": "Q5"},
            "occupation": {"value": "politician", "qid": "Q82955"},
            "citizenship": {"value": "Russia", "qid": "Q159"},
            "inception": "1952-10-07",
        },
        "related_entities": [
            {"qid": "Q159", "label": "Russia", "relation": "citizenship"},
            {"qid": "Q649", "label": "Moscow", "relation": "birthplace"},
        ],
    }
]
```

### Cache Key Pattern

```python
# For text search
key = cache_key(self.source_name, "search", query=params.query.lower())

# For Q-ID lookup
key = cache_key(self.source_name, "entity", qid=qid.upper())
```

### Error Handling

```python
# Timeout
try:
    response = await client.get(url, params=query_params)
except httpx.TimeoutException as e:
    raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e

# Rate limiting (Wikidata returns 429)
if response.status_code == 429:
    return OSINTResult(
        status=ResultStatus.RATE_LIMITED,
        query=params.query,
        results=[],
        sources=[],
        retrieved_at=datetime.now(timezone.utc),
    )

# Parse error
try:
    data = response.json()
except Exception as e:
    raise AdapterParseError(self.source_name, "Invalid JSON response") from e

# No results
if not data.get("search"):
    return OSINTResult(
        status=ResultStatus.NO_DATA,
        query=params.query,
        results=[],
        sources=[],
        retrieved_at=datetime.now(timezone.utc),
        error="No entities found matching the query. Try different spelling or more specific terms.",
    )
```

### Test Fixtures

**tests/fixtures/wikidata_search.json:**
```json
{
  "searchinfo": {"search": "Vladimir Putin"},
  "search": [
    {
      "id": "Q7747",
      "title": "Q7747",
      "label": "Vladimir Putin",
      "description": "President of Russia",
      "match": {"type": "label", "language": "en", "text": "Vladimir Putin"}
    }
  ],
  "success": 1
}
```

**tests/fixtures/wikidata_entity.json:**
```json
{
  "entities": {
    "Q7747": {
      "type": "item",
      "id": "Q7747",
      "labels": {"en": {"language": "en", "value": "Vladimir Putin"}},
      "descriptions": {"en": {"language": "en", "value": "President of Russia"}},
      "aliases": {"en": [{"language": "en", "value": "Putin"}]},
      "claims": {
        "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}]
      }
    }
  },
  "success": 1
}
```

### Dependencies

- **Requires:** Story 1.4 (Adapter Protocol & Error Hierarchy) - implemented
- **Blocked by:** None (no API key required)
- **Enables:** Story 3.2 (Entity Resolution Module), Story 3.3 (Entity Lookup Tool)

### Previous Story Intelligence

From WorldBankAdapter (Story 2-1):
- Lazy client initialization pattern works well
- Cache key generation via `cache_key()` helper
- Error handling contract: timeout → exception, rate limit → Result type
- Property extraction can be factored into helper methods

From GDELT Adapter:
- Retry logic with exponential backoff for rate limiting (consider adding)
- MAX_RETRIES = 3, RETRY_BASE_DELAY = 2.0

### Wikidata Rate Limits

Wikidata API has usage limits:
- Soft limit: ~200 requests per minute for anonymous users
- Consider implementing exponential backoff for 429 responses
- User-Agent header required (already in template)
