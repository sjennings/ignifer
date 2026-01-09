# Story 3.1: Wikidata Adapter

Status: done

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

- [x] Task 1: Create WikidataAdapter class (AC: #1)
  - [x] 1.1: Create `src/ignifer/adapters/wikidata.py`
  - [x] 1.2: Implement `source_name` and `base_quality_tier` properties
  - [x] 1.3: Create adapter-owned httpx.AsyncClient via `_get_client()`
  - [x] 1.4: Add `async def close()` method for cleanup

- [x] Task 2: Implement entity search via wbsearchentities API (AC: #2, #3)
  - [x] 2.1: Implement `async query(params: QueryParams) -> OSINTResult`
  - [x] 2.2: Use Wikidata `wbsearchentities` action for text search
  - [x] 2.3: Parse search results into normalized format
  - [x] 2.4: For each result, fetch basic properties via wbgetentities
  - [x] 2.5: Rank results by search relevance (Wikidata provides this)
  - [x] 2.6: Limit to top 10 results (MAX_SEARCH_RESULTS constant)
  - [x] 2.7: Return `OSINTResult` with proper attribution

- [x] Task 3: Implement direct Q-ID lookup (AC: #4)
  - [x] 3.1: Implement `async lookup_by_qid(qid: str) -> OSINTResult`
  - [x] 3.2: Use Wikidata `wbgetentities` action with Q-ID
  - [x] 3.3: Extract labels, aliases, descriptions, claims
  - [x] 3.4: Parse key properties (P31 instance of, P106 occupation, etc.)
  - [x] 3.5: Extract related entities with their Q-IDs
  - [x] 3.6: Return comprehensive entity data

- [x] Task 4: Implement property extraction helpers (AC: #2, #4)
  - [x] 4.1: Create `_extract_labels(entity_data)` - returns dict of language:label
  - [x] 4.2: Create `_extract_aliases(entity_data)` - returns list of aliases (English first)
  - [x] 4.3: Create `_extract_claims(entity_data)` - returns dict of property:values
  - [x] 4.4: Define KEY_PROPERTIES dict for 8 common properties to extract

- [x] Task 5: Integrate caching (AC: #5)
  - [x] 5.1: Accept CacheManager in constructor
  - [x] 5.2: Generate cache keys: `wikidata:search:{hash}` and `wikidata:entity:{hash}`
  - [x] 5.3: Check cache before API calls
  - [x] 5.4: Store results with 7-day TTL (settings.ttl_wikidata)

- [x] Task 6: Implement error handling (AC: #6)
  - [x] 6.1: Catch httpx.TimeoutException - raises AdapterTimeoutError
  - [x] 6.2: Handle rate limits (429) - returns ResultStatus.RATE_LIMITED
  - [x] 6.3: Handle empty search results - returns ResultStatus.NO_DATA
  - [x] 6.4: Handle malformed JSON - raises AdapterParseError

- [x] Task 7: Implement health check (AC: #7)
  - [x] 7.1: Create simple API ping query using wbsearchentities
  - [x] 7.2: Return True on success, False on failure

- [x] Task 8: Update exports (AC: #1)
  - [x] 8.1: Add WikidataAdapter to `adapters/__init__.py`

- [x] Task 9: Create tests (AC: #8)
  - [x] 9.1: Create `tests/adapters/test_wikidata.py` (38 tests)
  - [x] 9.2: Create `tests/fixtures/wikidata_search.json`
  - [x] 9.3: Create `tests/fixtures/wikidata_entity.json`
  - [x] 9.4: Test entity search query
  - [x] 9.5: Test multiple results handling
  - [x] 9.6: Test direct Q-ID lookup
  - [x] 9.7: Test cache hit behavior
  - [x] 9.8: Test timeout error handling
  - [x] 9.9: Test no data scenario

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

---

## Implementation Details

**Completed:** 2026-01-09

### Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `src/ignifer/adapters/wikidata.py` | Created | WikidataAdapter class (556 lines) |
| `src/ignifer/adapters/__init__.py` | Modified | Added WikidataAdapter export |
| `tests/adapters/test_wikidata.py` | Created | 38 comprehensive tests |
| `tests/fixtures/wikidata_search.json` | Created | Entity search response fixture |
| `tests/fixtures/wikidata_entity.json` | Created | Entity details response fixture |
| `tests/fixtures/wikidata_entities_batch.json` | Created | Batch entity lookup fixture |

### Test Results

- **Tests:** 60 passed (38 original + 22 new tests for code review fixes)
- **Coverage:** 89% (exceeds 80% requirement)
- **Type Check:** mypy strict mode passes

### Key Implementation Decisions

1. **Used httpx instead of SPARQLWrapper** - Better async support, consistency with other adapters
2. **Cache key uses `text=` param** - Avoids conflict with `cache_key()` positional `query` parameter
3. **Missing entity detection via key presence** - Wikidata returns `{"missing": ""}` which has falsy value but key exists
4. **Property extraction helpers** - Factored into reusable `_extract_labels()`, `_extract_aliases()`, `_extract_claims()` methods
5. **Batch entity fetch** - `_fetch_entity_details()` fetches multiple entities in one request for search results

### Architecture Compliance

- [x] Adapter-owned httpx client (lazy initialization via `_get_client()`)
- [x] `{Source}Adapter` naming convention
- [x] stdlib logging only (`logging.getLogger(__name__)`)
- [x] ISO 8601 + timezone for all datetime
- [x] snake_case for all JSON fields
- [x] QualityTier.HIGH for base quality tier
- [x] Hybrid error handling (exceptions for unexpected, Result type for expected)

### API Endpoints Used

| Action | Purpose |
|--------|---------|
| `wbsearchentities` | Text search for entities |
| `wbgetentities` | Fetch entity details by Q-ID(s) |

### Properties Extracted (KEY_PROPERTIES)

| Code | Name | Description |
|------|------|-------------|
| P31 | instance_of | Entity type (person, org, etc.) |
| P106 | occupation | Person's occupation |
| P17 | country | Country associated with entity |
| P27 | citizenship | Person's citizenship |
| P159 | headquarters | Organization's HQ location |
| P571 | inception | When founded/created |
| P856 | website | Official website URL |
| P625 | coordinates | Geographic coordinates |

---

## Senior Developer Review

**Review Date:** 2026-01-09

**Reviewer:** Senior Developer (Adversarial Review)

**Files Reviewed:**
- `/Volumes/IceStationZero/Projects/ignifer/src/ignifer/adapters/wikidata.py` (626 lines)
- `/Volumes/IceStationZero/Projects/ignifer/tests/adapters/test_wikidata.py` (605 lines)
- `/Volumes/IceStationZero/Projects/ignifer/src/ignifer/adapters/__init__.py` (exports)
- Test fixtures: `wikidata_search.json`, `wikidata_entity.json`, `wikidata_entities_batch.json`

### Test Verification

**Test Execution:**
```bash
pytest tests/adapters/test_wikidata.py -v
```
**Result:** ✅ All 38 tests PASSED

**Coverage Check:**
```bash
pytest tests/adapters/test_wikidata.py --cov=ignifer.adapters.wikidata --cov-report=term-missing
```
**Result:** ✅ 91% coverage (exceeds 80% requirement)

**Uncovered Lines:** 140, 164-175, 282-284, 381, 425-427, 432-433, 494-495, 534, 552-554 (mostly error paths and edge cases)

### Issues Found

#### **Issue #1: HTTP Error Status Code Mishandling (MAJOR)**
- **Location:** `wikidata.py:276, 419` - `response.raise_for_status()`
- **Problem:** Only 429 (rate limit) is handled before calling `raise_for_status()`. Other HTTP errors (400, 403, 404, 500, 503) get caught by the generic `httpx.HTTPError` handler (lines 282, 425) and incorrectly converted to `AdapterParseError`.
- **Impact:** A 404 or 503 from Wikidata will be reported as "Failed to parse API response: HTTP error" rather than a more appropriate error type. This violates the error handling contract and confuses users.
- **Example Scenario:** Wikidata returns 503 Service Unavailable → user sees "parse error" instead of timeout/availability error.
- **Fix Required:** Add specific handling for common HTTP status codes (404 → NO_DATA, 503/502 → AdapterTimeoutError or custom availability error).

#### **Issue #2: Cache Key Collision Risk (MAJOR)**
- **Location:** `wikidata.py:241, 384`
- **Problem:** Query cache uses `text=query_text.lower()` and entity cache uses `qid=qid`. Edge case: if someone searches for text "q7747" (lowercase), then looks up entity "Q7747", these generate different cache keys but semantically refer to the same entity. Worse, the query path doesn't validate whether the search text looks like a Q-ID.
- **Impact:** Potential cache inconsistency. User searches for "q7747" (gets search results), then looks up "Q7747" (gets entity details) - two separate cache entries for same entity. Could also enable cache poisoning if query text matches entity ID patterns.
- **Fix Required:** Validate Q-ID format in `query()` method. If query text matches Q-ID pattern (e.g., regex `^[Qq]\d+$`), reject or redirect to `lookup_by_qid()`.

#### **Issue #3: Silent Data Loss in Batch Entity Fetch (MAJOR)**
- **Location:** `wikidata.py:546-554` - `_fetch_entity_details()`
- **Problem:** The helper method catches all exceptions with `except Exception as e` and silently returns empty dict `{}`. If the batch entity fetch times out or fails, the query will succeed but return incomplete data (search results without property details). User won't know data is missing.
- **Impact:** Silent data loss. User gets search results but without instance_of, aliases, or other enrichment. No indication of failure.
- **Fix Required:** Log error at WARNING level with details. Consider whether critical failures (timeout, connection error) should propagate up rather than being swallowed.

#### **Issue #4: Incomplete Claim Value Type Coverage (MINOR)**
- **Location:** `wikidata.py:127-175` - `_extract_claim_value()`
- **Problem:** Method handles 5 datavalue types (`wikibase-entityid`, `string`, `time`, `globecoordinate`, `quantity`) but Wikidata has additional types:
  - `monolingualtext` (language + text)
  - `external-id` (external identifiers)
  - `commonsMedia` (Wikimedia Commons files)
  - `url` (distinct from string)
- **Impact:** Properties with these types fall through to line 175 and return stringified value or None. Data loss for uncommon property types.
- **Coverage Gap:** No tests for these edge cases.
- **Fix Required:** Add handling for additional types or log warning when unknown type encountered.

#### **Issue #5: Missing Q-ID Format Validation (MINOR)**
- **Location:** `wikidata.py:378-381` - `lookup_by_qid()`
- **Problem:** Code normalizes Q-ID (strip, uppercase, prepend "Q") but doesn't validate format:
  - `lookup_by_qid("Q")` → sends "Q" to API (invalid)
  - `lookup_by_qid("Q-7747")` → sends "Q-7747" to API (invalid)
  - `lookup_by_qid("QQ7747")` → sends "QQ7747" to API (invalid)
- **Impact:** Invalid Q-IDs hit API unnecessarily, return NO_DATA, but don't explain why input was invalid.
- **Fix Required:** Validate Q-ID format with regex (e.g., `^Q\d+$` after normalization). Return immediate NO_DATA with helpful error message for invalid format.

#### **Issue #6: Type Annotation Inconsistency (MINOR)**
- **Location:** `wikidata.py:309, 322, 468, 488`
- **Problem:** Result entries typed as `dict[str, str | int | float | bool | None]` but:
  - Line 326: `aliases` stored as comma-separated string (should semantically be list)
  - Line 488: `related_entities_count` stored as int
  - Annotation promises uniform value types but implementation violates this
- **Impact:** Type checking tools won't catch violations. Potential runtime errors if consumers assume consistent types.
- **Fix Required:** Either change type annotation to `dict[str, Any]` or normalize all values to strings for consistency.

#### **Issue #7: Inconsistent Output Schema (MINOR)**
- **Location:** `wikidata.py:459-466, 487-489`
- **Problem:** `related_entities_count` only added if related_entities list is non-empty (line 487). If claims are empty, this field is absent. Creates inconsistent response schema.
- **Impact:** Consumers must handle optional field. Inconsistent API.
- **Fix Required:** Always include `related_entities_count` (default 0 if no related entities).

#### **Issue #8: Overly Broad HTTP Error Catching (MINOR)**
- **Location:** `wikidata.py:282-284, 425-427`
- **Problem:** `except httpx.HTTPError as e` catches ALL HTTP errors (HTTPStatusError, RequestError, ConnectError, etc.) and treats them all as parse errors. A connection error is semantically different from a parse error.
- **Impact:** Misleading error categorization in logs and user-facing messages.
- **Fix Required:** Split into specific exception types (ConnectError → timeout, HTTPStatusError → parse, etc.).

### Suggestions (Optional Improvements)

1. **Rate Limiting:** Story mentions Wikidata has ~200 req/min limit and suggests exponential backoff (Dev Notes line 497-500), but implementation only detects 429. Consider adding retry logic with tenacity for rate limit scenarios.

2. **Multi-Value Claims:** Wikidata properties can have multiple values (e.g., person with multiple occupations). Current code takes only first value (line 196: `claim_list[0]`). Consider returning all values or adding logic to prefer "preferred" rank claims.

3. **Claim Qualifiers:** Wikidata claims have qualifiers (e.g., "occupation: politician" qualified with "start date: 1999"). Current implementation ignores qualifiers. Consider extracting them for richer data.

4. **Test Coverage Gaps:**
   - No test for claims with `snaktype: "novalue"` or `"somevalue"` (lines not checking snaktype)
   - No test for multiple values per property
   - No test for invalid Q-ID formats
   - No test for batch entity fetch failure (Issue #3)

### Architecture Compliance

**✅ PASS - Follows All Standards:**
- Implements `OSINTAdapter` protocol correctly
- Uses adapter-owned httpx client (lazy initialization via `_get_client()`)
- Correct naming convention: `WikidataAdapter`
- Uses stdlib logging only (`logging.getLogger(__name__)`)
- ISO 8601 + timezone for all datetime
- snake_case for all JSON fields
- QualityTier.HIGH appropriate for Wikidata (curated data)
- Hybrid error handling pattern (exceptions for unexpected, Result type for expected)
- 7-day TTL matches architecture.md specification

**✅ PASS - Code Quality:**
- Clean separation of concerns with helper methods
- Good use of property extraction helpers (`_extract_labels`, `_extract_aliases`, `_extract_claims`)
- Proper docstrings on all public methods
- Type hints throughout

### Security Review

**✅ PASS:**
- No hardcoded secrets
- Input validation via httpx URL encoding
- User-Agent header present and appropriate
- No credential exposure in error messages

**⚠️ CAUTION:**
- No rate limiting implementation (429 detected but no exponential backoff/retry)
- Could hammer API if client retries aggressively

### Performance Review

**✅ GOOD:**
- Batch entity fetch optimization (line 306: fetches all search result details in one request)
- Proper caching with 7-day TTL per specification
- Lazy client initialization

**⚠️ CONSIDER:**
- No rate limiting/backoff could lead to thundering herd issues
- Batch fetch size not limited (could request 10+ entities at once)

### Final Verdict

**OUTCOME:** ⚠️ **Changes Requested**

The implementation demonstrates solid architecture compliance, good test coverage (91%), and clean code structure. However, **8 issues were identified** (3 Major, 5 Minor) that should be addressed before production deployment:

**Must Fix Before Merge:**
1. ❌ HTTP error status code mishandling (Issue #1 - Major)
2. ❌ Cache key collision risk (Issue #2 - Major)
3. ❌ Silent data loss in batch fetch (Issue #3 - Major)

**Should Fix:**
4. ⚠️ Incomplete claim value type coverage (Issue #4 - Minor)
5. ⚠️ Missing Q-ID format validation (Issue #5 - Minor)

**Nice to Have:**
6. Type annotation inconsistency (Issue #6 - Minor)
7. Inconsistent output schema (Issue #7 - Minor)
8. Overly broad HTTP error catching (Issue #8 - Minor)

**Recommendation:** Address the 3 major issues before merging. The adapter will function correctly for common use cases, but edge cases (HTTP errors, cache collisions, batch fetch failures) could cause production issues or poor user experience.

**Testing Note:** While test coverage is excellent at 91%, additional tests should be added for the identified edge cases, particularly around error handling and invalid input scenarios.

---

## Code Review Fixes Applied

**Date:** 2026-01-09

All 8 issues identified in the Senior Developer Review have been addressed:

### Issue #1: HTTP Error Status Code Mishandling (MAJOR) - FIXED

**Changes:**
- Refactored error handling to check HTTP status codes before attempting JSON parsing
- 5xx errors (500, 503) now raise `AdapterTimeoutError` (service unavailable)
- 404 errors return `ResultStatus.NO_DATA` with descriptive error message
- Other 4xx errors raise `AdapterParseError` with HTTP status code in message
- Applied to both `query()` and `lookup_by_qid()` methods

### Issue #2: Cache Key Collision Risk (MAJOR) - FIXED

**Changes:**
- Added Q-ID pattern detection in `query()` method
- If query text matches Q-ID pattern (e.g., "q7747", "Q7747", "7747"), redirects to `lookup_by_qid()`
- Prevents duplicate cache entries for same entity via different query paths
- Added `QID_PATTERN` regex constant for validation

### Issue #3: Silent Data Loss in Batch Fetch (MAJOR) - FIXED

**Changes:**
- Refactored `_fetch_entity_details()` to log detailed warnings when errors occur
- Specific handling for `TimeoutException`, `ConnectError`, `RequestError`
- HTTP status check before JSON parsing
- Logs warning with entity count and error details
- Logs missing entities if API returns fewer entities than requested
- Search results still returned with warning that enrichment data is missing

### Issue #4: Incomplete Claim Value Type Coverage (MINOR) - FIXED

**Changes:**
- Added handlers for `monolingualtext` (returns text + language)
- Added handlers for `external-id` (returns value + type indicator)
- Added handlers for `commonsMedia` (returns filename + type indicator)
- Added handlers for `url` (distinct from string type)
- Added handling for `novalue` and `somevalue` snaktypes
- Added logging for unknown value types

### Issue #5: Missing Q-ID Format Validation (MINOR) - FIXED

**Changes:**
- Added `QID_PATTERN = re.compile(r"^Q\d+$")` constant
- Validation in `lookup_by_qid()` after normalization
- Invalid Q-IDs return `ResultStatus.NO_DATA` with helpful error message
- Prevents unnecessary API calls for malformed Q-IDs

### Issue #6: Type Annotation Inconsistency (MINOR) - FIXED

**Changes:**
- Changed result type annotations from `dict[str, str | int | float | bool | None]` to `dict[str, Any]`
- More accurately reflects actual usage (mixed types, optional fields)
- Applied to both `query()` and `lookup_by_qid()` result building

### Issue #7: Inconsistent Output Schema (MINOR) - FIXED

**Changes:**
- `related_entities_count` now always included in lookup results
- Set to 0 when no related entities exist
- Provides consistent output schema for consumers

### Issue #8: Overly Broad HTTP Error Catching (MINOR) - FIXED

**Changes:**
- Split generic `httpx.HTTPError` catch into specific exception types
- `TimeoutException` - raises `AdapterTimeoutError`
- `ConnectError` - raises `AdapterTimeoutError` (connection unavailable)
- `RequestError` - raises `AdapterTimeoutError` (network issues)
- HTTP status errors handled separately with appropriate error types

### New Tests Added

22 new tests added to cover the fixes:

| Test Class | Tests | Coverage |
|------------|-------|----------|
| `TestWikidataAdapterHTTPErrorHandling` | 7 | Issues #1, #8 |
| `TestWikidataAdapterQIDValidation` | 4 | Issue #5 |
| `TestWikidataAdapterQIDRedirect` | 2 | Issue #2 |
| `TestWikidataAdapterClaimValueTypes` | 6 | Issue #4 |
| `TestWikidataAdapterOutputConsistency` | 1 | Issue #7 |
| `TestWikidataAdapterBatchFetchErrorHandling` | 2 | Issue #3 |

**Final Test Results:** 60 tests passed, 89% coverage

---

## Senior Developer Review - Round 2

**Review Date:** 2026-01-09

**Reviewer:** Senior Developer (Adversarial Review - Post-Fix Verification)

**Context:** This is the second review after the developer addressed all 8 issues from the first review (3 major, 5 minor). This review verifies the fixes and searches for any new issues introduced by the changes.

### Test Verification

**Test Execution:**
```bash
pytest tests/adapters/test_wikidata.py -v
```
**Result:** ✅ All 60 tests PASSED (38 original + 22 new tests for fixes)

**Coverage Check:**
```bash
pytest tests/adapters/test_wikidata.py --cov=ignifer.adapters.wikidata --cov-report=term-missing
```
**Result:** ✅ 89% coverage (exceeds 80% requirement)

**Test Breakdown:**
- Original tests: 38
- New tests for Issue #1, #8 (HTTP error handling): 7
- New tests for Issue #5 (Q-ID validation): 4
- New tests for Issue #2 (Q-ID redirect): 2
- New tests for Issue #4 (claim value types): 6
- New tests for Issue #7 (output consistency): 1
- New tests for Issue #3 (batch fetch error handling): 2
- **Total:** 60 tests

### Verification of Fixes

#### **Issue #1: HTTP Error Status Code Mishandling (MAJOR) - ✅ FIXED**

**Original Problem:** Only 429 handled before `raise_for_status()`. Other HTTP errors (404, 500, 503) incorrectly converted to `AdapterParseError`.

**Fix Verification:**
- Lines 327-361 (`query()` method): HTTP status codes now checked BEFORE JSON parsing
  - 429 → `ResultStatus.RATE_LIMITED` ✅
  - 5xx (500, 503) → `AdapterTimeoutError` ✅
  - 404 → `ResultStatus.NO_DATA` with descriptive error ✅
  - Other 4xx → `AdapterParseError` with HTTP status in message ✅
- Lines 512-546 (`lookup_by_qid()` method): Same pattern applied ✅
- Tests added: `test_query_500_server_error_raises_timeout`, `test_query_503_server_error_raises_timeout`, `test_query_404_returns_no_data`, `test_query_400_client_error_raises_parse_error`, `test_lookup_500_server_error_raises_timeout`, `test_lookup_404_returns_no_data`

**Verdict:** ✅ **FULLY FIXED** - Proper status code handling now in place. Error categorization is semantically correct.

#### **Issue #2: Cache Key Collision Risk (MAJOR) - ✅ FIXED**

**Original Problem:** Query for "q7747" and lookup for "Q7747" created different cache keys despite referring to same entity. Potential cache inconsistency.

**Fix Verification:**
- Lines 274-285 (`query()` method): Q-ID pattern detection added
  - Uses `QID_PATTERN.match()` to detect Q-IDs (line 18: `QID_PATTERN = re.compile(r"^Q\d+$")`)
  - Normalizes query text: uppercase, prepends "Q" if numeric
  - Redirects to `lookup_by_qid()` if pattern matches
  - Prevents cache collision by ensuring Q-ID queries always use entity cache path
- Tests added: `test_query_with_qid_redirects_to_lookup`, `test_query_with_numeric_id_redirects_to_lookup`

**Verdict:** ✅ **FULLY FIXED** - Cache collision prevented through redirect pattern. Tests confirm both "q7747" and "7747" redirect to lookup.

#### **Issue #3: Silent Data Loss in Batch Fetch (MAJOR) - ✅ FIXED**

**Original Problem:** `_fetch_entity_details()` caught all exceptions and silently returned `{}`, causing incomplete search results without user notification.

**Fix Verification:**
- Lines 665-713 (`_fetch_entity_details()` method): Comprehensive error logging added
  - `TimeoutException` → logged with warning (lines 667-672) ✅
  - `ConnectError` → logged with warning (lines 673-678) ✅
  - `RequestError` → logged with warning (lines 679-684) ✅
  - HTTP status check → logged if non-200 (lines 686-692) ✅
  - JSON parse failure → logged with error details (lines 694-701) ✅
  - Missing entities detection → logged specific Q-IDs (lines 706-711) ✅
- All warnings indicate "Search results will be returned without enriched properties"
- Tests added: `test_batch_fetch_timeout_returns_empty_with_warning`, `test_batch_fetch_http_error_returns_empty_with_warning`

**Verdict:** ✅ **FULLY FIXED** - No longer silent. Detailed logging ensures operators know when enrichment fails. Search still succeeds gracefully with partial data.

#### **Issue #4: Incomplete Claim Value Type Coverage (MINOR) - ✅ FIXED**

**Original Problem:** Missing handlers for `monolingualtext`, `external-id`, `commonsMedia`, `url` claim types. Also missing `novalue`/`somevalue` snaktype handling.

**Fix Verification:**
- Lines 166-171 (`_extract_claim_value()`): `monolingualtext` handler added ✅
- Lines 196-197: `commonsMedia` handler added ✅
- Lines 199-201: `url` handler added ✅
- Lines 203-205: `external-id` handler added ✅
- Lines 143-148: `novalue` and `somevalue` snaktype handlers added ✅
- Lines 207-209: Unknown type logging added ✅
- Tests added: `test_extract_monolingualtext`, `test_extract_external_id`, `test_extract_commons_media`, `test_extract_url`, `test_extract_novalue`, `test_extract_somevalue`

**Verdict:** ✅ **FULLY FIXED** - All additional claim types now handled. Unknown types logged for future extension.

#### **Issue #5: Missing Q-ID Format Validation (MINOR) - ✅ FIXED**

**Original Problem:** `lookup_by_qid()` normalized input but didn't validate format. Invalid Q-IDs ("Q", "Q-7747", "QQ7747") hit API unnecessarily.

**Fix Verification:**
- Line 18: `QID_PATTERN = re.compile(r"^Q\d+$")` defined ✅
- Lines 460-470 (`lookup_by_qid()`): Format validation after normalization
  - Validation uses `QID_PATTERN.match(qid)` after normalization
  - Invalid format → `ResultStatus.NO_DATA` with helpful error message
  - Error message explains valid format: "'Q' followed by digits (e.g., 'Q7747')"
- Tests added: `test_invalid_qid_empty_q`, `test_invalid_qid_with_hyphen`, `test_invalid_qid_double_q`, `test_invalid_qid_letters_after_q`

**Verdict:** ✅ **FULLY FIXED** - Q-ID validation prevents invalid API calls and provides user-friendly error messages.

#### **Issue #6: Type Annotation Inconsistency (MINOR) - ✅ FIXED**

**Original Problem:** Result entries typed as `dict[str, str | int | float | bool | None]` but implementation stored mixed types (comma-separated aliases as string, related_entities_count as int).

**Fix Verification:**
- Line 399 (`query()` method): Changed to `result_entry: dict[str, Any]` ✅
- Line 587 (`lookup_by_qid()` method): Changed to `result_entry: dict[str, Any]` ✅
- Consistent with actual usage where values can be strings, ints, nested dicts, etc.

**Verdict:** ✅ **FULLY FIXED** - Type annotation now accurately reflects implementation. No false precision.

#### **Issue #7: Inconsistent Output Schema (MINOR) - ✅ FIXED**

**Original Problem:** `related_entities_count` only included when related entities existed, creating inconsistent schema.

**Fix Verification:**
- Line 606 (`lookup_by_qid()` method): `related_entities_count` always included
  - Set to `len(related_entities)` which is 0 when no related entities
  - Ensures consistent field presence regardless of data
- Test added: `test_lookup_always_includes_related_entities_count`

**Verdict:** ✅ **FULLY FIXED** - Output schema now consistent. Consumers can always expect `related_entities_count` field.

#### **Issue #8: Overly Broad HTTP Error Catching (MINOR) - ✅ FIXED**

**Original Problem:** Generic `httpx.HTTPError` catch treated all HTTP errors (connection, timeout, status) as parse errors. Misleading categorization.

**Fix Verification:**
- Lines 312-325 (`query()` method): Specific exception handling
  - `httpx.TimeoutException` → `AdapterTimeoutError` ✅
  - `httpx.ConnectError` → `AdapterTimeoutError` ✅
  - `httpx.RequestError` → `AdapterTimeoutError` (DNS, connection reset) ✅
  - HTTP status codes handled separately before JSON parsing ✅
- Lines 495-510 (`lookup_by_qid()` method): Same pattern ✅
- Tests added: `test_query_connection_error_raises_timeout` (covered in Issue #1 tests)

**Verdict:** ✅ **FULLY FIXED** - Exception handling now granular and semantically correct. Network issues properly categorized as timeout errors, not parse errors.

### New Issues Search (Adversarial Analysis)

I conducted a thorough adversarial review looking for:
1. Logic errors introduced by fixes
2. Edge cases not covered by new tests
3. Performance regressions
4. Security vulnerabilities
5. Architecture violations

**Findings:**

#### ❌ **NEW ISSUE #9: Q-ID Redirect Logic Gap (MINOR)**

**Location:** Lines 274-285 (`query()` method)

**Problem:** The Q-ID detection logic has a subtle edge case. When query is "7747" (just numbers), it prepends "Q" to create "Q7747". However, if someone searches for "123abc", it would:
1. Not match the pattern initially (line 277-281 logic prepends Q only if not starting with Q)
2. Create "Q123abc"
3. Still not match `QID_PATTERN` (requires Q + only digits)
4. Proceed to search API

This isn't broken behavior (search for "123abc" is valid), but the logic is slightly convoluted. The fix correctly validates with `QID_PATTERN.match()` at line 283, so no incorrect redirects occur.

**Impact:** Low. The code works correctly due to final pattern validation. Just slightly harder to understand.

**Recommendation:** Optional - add code comment explaining the two-step normalization + validation flow.

#### ✅ **No Other Issues Found**

After thorough review:
- No logic errors introduced by fixes
- No architecture violations
- No security issues
- Error handling paths properly tested
- Logging is appropriate (WARNING level for data loss scenarios)
- Type safety improved with `Any` annotations
- Performance unchanged (no extra API calls)

### Additional Observations

**Strengths of the Fixes:**
1. **Comprehensive test coverage** - 22 new tests for 8 issues shows thorough verification
2. **Logging discipline** - All batch fetch errors logged with appropriate severity
3. **User-friendly errors** - Q-ID validation errors explain valid format
4. **Defensive programming** - Q-ID redirect prevents cache collisions proactively
5. **Semantic correctness** - HTTP error categorization now aligns with error meaning

**Minor Nitpicks (Not Blocking):**
1. Line 208: Warning message for unknown claim types could include example value for debugging
2. Lines 706-711: Missing entity warning could be DEBUG level instead of WARNING (may be expected behavior)
3. Q-ID redirect logging at DEBUG level (line 284) is appropriate but could mention cache collision prevention in comment

### Architecture & Standards Compliance

**✅ PASS - All Standards Met:**
- Implements `OSINTAdapter` protocol correctly
- Adapter-owned httpx client (lazy initialization)
- Correct naming: `WikidataAdapter`
- stdlib logging only
- ISO 8601 + timezone for datetime
- snake_case for all JSON fields
- QualityTier.HIGH appropriate
- Hybrid error handling (exceptions for unexpected, Result for expected)
- 7-day TTL per specification
- Type hints throughout
- Proper docstrings

**✅ Code Quality:**
- Clean separation of concerns
- Comprehensive error handling
- Appropriate logging levels
- Well-structured test suite
- No code duplication

### Final Verdict

**OUTCOME:** ✅ **APPROVE**

**Summary:**
All 8 issues from the first review have been **successfully fixed and properly tested**. The implementation demonstrates:

✅ **All Major Issues Resolved:**
1. HTTP error status codes now properly categorized
2. Cache key collisions prevented through Q-ID redirect
3. Batch fetch errors comprehensively logged (no silent failures)

✅ **All Minor Issues Resolved:**
4. Complete claim value type coverage
5. Q-ID format validation with helpful errors
6. Type annotations reflect actual usage
7. Consistent output schema (related_entities_count always present)
8. Granular HTTP exception handling

✅ **Test Quality:**
- 60 tests pass (38 original + 22 new)
- 89% coverage (exceeds 80% requirement)
- Edge cases covered (invalid Q-IDs, HTTP errors, batch failures)

✅ **Production Readiness:**
- Robust error handling for all failure modes
- Comprehensive logging for operational visibility
- User-friendly error messages
- No breaking changes to API contract
- No performance regressions

**New Issue Found:** 1 minor issue (#9: Q-ID redirect logic gap) - does not block approval. The code works correctly; minor comment improvement suggested for future.

**Recommendation:** **MERGE TO MAIN**. The adapter is production-ready. All identified issues have been properly addressed with comprehensive test coverage. The implementation demonstrates high code quality and attention to detail.

**Kudos to Developer:**
The fix quality is excellent. All 8 issues addressed with proper tests, no corner-cutting, and thoughtful error messages. The 22 new tests demonstrate thorough understanding of the problems and commitment to verification.

---

**Status Update:** Story 3.1 (Wikidata Adapter) - **APPROVED** and ready for production deployment.
