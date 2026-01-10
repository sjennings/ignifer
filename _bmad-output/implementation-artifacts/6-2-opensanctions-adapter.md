# Story 6.2: OpenSanctions Adapter

**Epic:** Epic 6 - Conflict & Security Analysis
**Status:** done
**Priority:** High
**Estimate:** Medium

## User Story

As a **compliance researcher**,
I want **to screen entities against sanctions lists**,
So that **I can identify sanctioned entities and politically exposed persons**.

## Acceptance Criteria

1. **AC1: OpenSanctionsAdapter Class Created**
   - **Given** the adapter protocol from Epic 1
   - **When** I create `src/ignifer/adapters/opensanctions.py`
   - **Then** `OpenSanctionsAdapter` class:
     - Implements `OSINTAdapter` protocol
     - Has `source_name = "opensanctions"` and `base_quality_tier = QualityTier.HIGH`
     - Uses OpenSanctions API (free for non-commercial use)
     - Implements `async query(params: QueryParams) -> OSINTResult`
     - Implements `async search_entity(name: str) -> OSINTResult`
     - Implements `async check_sanctions(entity_id: str) -> OSINTResult`
     - Implements `async health_check() -> bool`

2. **AC2: Entity Screening Queries Work**
   - **Given** OpenSanctionsAdapter is instantiated
   - **When** I call `await adapter.query(QueryParams(topic="Viktor Vekselberg"))`
   - **Then** it searches OpenSanctions database
   - **And** returns `OSINTResult` with:
     - Match confidence score
     - Entity type (person, organization, vessel, etc.)
     - Sanctions lists matched (OFAC SDN, EU, UN, etc.)
     - PEP status if applicable
     - Associated entities (companies, family members)
     - Source references and dates
   - **And** results are cached with 24-hour TTL

3. **AC3: Multiple Sanctions Lists Handling**
   - **Given** entity matches multiple sanctions lists
   - **When** results are returned
   - **Then** lists each sanctions program separately
   - **And** includes effective dates and reasons where available

4. **AC4: PEP Detection Without Sanctions (FR19)**
   - **Given** entity is a PEP but not sanctioned
   - **When** search completes
   - **Then** indicates PEP status with position held
   - **And** notes PEP is not currently sanctioned
   - **And** suggests enhanced due diligence

5. **AC5: No Match Handling**
   - **Given** no match is found
   - **When** search completes
   - **Then** returns clear "No matches found" result
   - **And** includes confidence that search was comprehensive
   - **And** notes entity may use aliases not in database

6. **AC6: Tests Pass with Mocked Responses**
   - **Given** test fixtures exist in `tests/fixtures/opensanctions_entity.json`
   - **When** I run `pytest tests/adapters/test_opensanctions.py`
   - **Then** all tests pass using mocked HTTP responses

## Technical Notes

### OpenSanctions API Reference

**Base URL:** `https://api.opensanctions.org/`

**Authentication:**
- Free for non-commercial use (no API key required for basic queries)
- Rate limits apply to free tier
- API key available for higher rate limits (check if config needed)

**Key Endpoints:**

| Endpoint | Description |
|----------|-------------|
| `/match/default` | Match entities against sanctions database |
| `/search/default` | Search entities by name/text |
| `/entities/{id}` | Get entity by OpenSanctions ID |

**Match Request (POST):**
```json
{
  "queries": {
    "q1": {
      "schema": "Person",
      "properties": {
        "name": ["Viktor Vekselberg"]
      }
    }
  }
}
```

**Search Parameters:**
| Parameter | Description |
|-----------|-------------|
| `q` | Search query string |
| `schema` | Filter by entity type (Person, Company, Vessel, etc.) |
| `datasets` | Filter by specific sanctions lists |
| `limit` | Number of results (default 10) |

**Entity Types (OpenSanctions schema):**
- Person
- Company
- Organization
- LegalEntity
- Vessel
- Aircraft

**Dataset/Sanctions Lists:**
- us_ofac_sdn (OFAC SDN List)
- eu_fsf (EU Financial Sanctions)
- un_sc_sanctions (UN Security Council)
- gb_hmt_sanctions (UK HMT)
- ch_seco_sanctions (Swiss SECO)
- ru_rupep (Russian PEPs)
- ua_nazk_pep (Ukrainian PEPs)
- Various national PEP lists

### Architecture Compliance

**FROM project-context.md:**
1. **Adapter-owned httpx clients** - never shared across adapters
2. **`{Source}Adapter` naming** - class must be `OpenSanctionsAdapter`
3. **stdlib `logging` only** - use `logging.getLogger(__name__)`
4. **ISO 8601 + timezone** for all datetime
5. **snake_case** for all JSON fields

**TTL Default:** 24 hours (configured in config.py as `ttl_opensanctions = 86400`)

### Error Handling Contract

| Scenario | Handling | Type |
|----------|----------|------|
| Network timeout | `AdapterTimeoutError` | Exception |
| Rate limited | `OSINTResult(status=RATE_LIMITED)` | Result type |
| No data found | `OSINTResult(status=NO_DATA)` | Result type |
| Malformed response | `AdapterParseError` | Exception |
| Auth failure (if API key used) | `AdapterAuthError` | Exception |

### Match Confidence Scoring

OpenSanctions returns a `score` field (0.0-1.0) for each match. Map to ConfidenceLevel:
- `score >= 0.9` -> `ConfidenceLevel.HIGH`
- `score >= 0.7` -> `ConfidenceLevel.MEDIUM`
- `score >= 0.5` -> `ConfidenceLevel.LOW`
- `score < 0.5` -> Consider excluding or flagging as low confidence

### Sample OpenSanctions API Response

**Match Response:**
```json
{
  "responses": {
    "q1": {
      "query": {...},
      "total": {"value": 2, "relation": "eq"},
      "results": [
        {
          "id": "NK-....",
          "caption": "Viktor Vekselberg",
          "schema": "Person",
          "properties": {
            "name": ["Viktor Vekselberg", "Виктор Вексельберг"],
            "birthDate": ["1957-04-14"],
            "nationality": ["ru"],
            "position": ["Businessman"],
            "topics": ["sanction"]
          },
          "datasets": ["us_ofac_sdn", "eu_fsf", "ch_seco_sanctions"],
          "referents": ["ofac-..."],
          "score": 0.98
        }
      ]
    }
  }
}
```

**Entity Detail Response:**
```json
{
  "id": "NK-....",
  "caption": "Viktor Vekselberg",
  "schema": "Person",
  "properties": {
    "name": ["Viktor Vekselberg"],
    "alias": ["Виктор Вексельберг"],
    "birthDate": ["1957-04-14"],
    "nationality": ["ru"],
    "topics": ["sanction"],
    "position": ["Chairman of Renova Group"]
  },
  "datasets": ["us_ofac_sdn", "eu_fsf"],
  "referents": ["ofac-12345"],
  "first_seen": "2018-04-06",
  "last_seen": "2024-01-15"
}
```

### PEP Detection Logic

OpenSanctions includes PEP (Politically Exposed Person) data alongside sanctions. The `topics` field indicates status:
- `"sanction"` - Currently sanctioned
- `"poi"` - Person of Interest
- `"role.pep"` - Politically Exposed Person
- `"crime"` - Linked to criminal activity

For FR19 compliance, when `topics` includes `"role.pep"` but NOT `"sanction"`:
- Return PEP status with position held
- Include "NOT CURRENTLY SANCTIONED" flag
- Add note: "Enhanced due diligence recommended for PEPs"

## Dependencies

- Story 1.4: Adapter Protocol & Error Hierarchy (base protocol and error classes)
- Story 1.3: Cache Layer Implementation (caching with 24-hour TTL)

## Files to Create/Modify

### New Files

| File | Description |
|------|-------------|
| `src/ignifer/adapters/opensanctions.py` | OpenSanctionsAdapter implementation |
| `tests/adapters/test_opensanctions.py` | Test suite for OpenSanctionsAdapter |
| `tests/fixtures/opensanctions_entity.json` | Mock OpenSanctions match response |
| `tests/fixtures/opensanctions_pep.json` | Mock PEP-only response for FR19 |
| `tests/fixtures/opensanctions_no_match.json` | Mock empty response |

### Modified Files

| File | Change |
|------|--------|
| `src/ignifer/adapters/__init__.py` | Add OpenSanctionsAdapter export |

## Testing Requirements

### Unit Tests

1. **test_source_name** - Verify `source_name == "opensanctions"`
2. **test_base_quality_tier_is_high** - Verify `base_quality_tier == QualityTier.HIGH`
3. **test_query_success** - Successful query returns normalized results with sanctions lists
4. **test_query_with_high_confidence_match** - High-score match returns HIGH confidence
5. **test_query_with_medium_confidence_match** - Medium-score match returns MEDIUM confidence
6. **test_search_entity_success** - `search_entity()` method works
7. **test_check_sanctions_by_id** - `check_sanctions()` looks up entity by ID
8. **test_multiple_sanctions_lists** - Entity on multiple lists returns all lists
9. **test_pep_only_entity** - PEP without sanctions returns appropriate status (FR19)
10. **test_pep_suggests_due_diligence** - PEP result includes due diligence note
11. **test_query_no_match** - Returns NO_DATA status with comprehensive search note
12. **test_query_rate_limited** - Returns RATE_LIMITED on 429
13. **test_query_timeout** - Raises AdapterTimeoutError on timeout
14. **test_query_malformed_response** - Raises AdapterParseError on bad JSON
15. **test_health_check_success** - Returns True when API responds
16. **test_health_check_failure** - Returns False on connection error
17. **test_cache_hit** - Cached results returned on second call
18. **test_results_include_entity_type** - Response includes schema/entity type
19. **test_results_include_associated_entities** - Response includes referents/related entities
20. **test_results_include_dates** - Response includes first_seen/last_seen dates

### Coverage Target

- Minimum 80% coverage on `src/ignifer/adapters/opensanctions.py`

## Tasks / Subtasks

- [ ] Task 1: Create OpenSanctionsAdapter class (AC: #1)
  - [ ] 1.1: Create `src/ignifer/adapters/opensanctions.py`
  - [ ] 1.2: Implement `source_name` and `base_quality_tier` properties
  - [ ] 1.3: Create adapter-owned httpx.AsyncClient with lazy initialization
  - [ ] 1.4: Add `async def close()` method for cleanup

- [ ] Task 2: Implement query logic (AC: #2)
  - [ ] 2.1: Parse query topic to extract entity name
  - [ ] 2.2: Build OpenSanctions match/search API request
  - [ ] 2.3: Parse JSON response into normalized format
  - [ ] 2.4: Extract entity type (schema)
  - [ ] 2.5: Extract sanctions lists (datasets)
  - [ ] 2.6: Map API score to ConfidenceLevel
  - [ ] 2.7: Extract associated entities (referents)
  - [ ] 2.8: Return `OSINTResult` with proper attribution

- [ ] Task 3: Implement search_entity method (AC: #1, #2)
  - [ ] 3.1: Build search endpoint request
  - [ ] 3.2: Return results in same format as query()

- [ ] Task 4: Implement check_sanctions method (AC: #1)
  - [ ] 4.1: Look up entity by OpenSanctions ID
  - [ ] 4.2: Return detailed sanctions information

- [ ] Task 5: Implement multiple sanctions list handling (AC: #3)
  - [ ] 5.1: Parse datasets array into individual sanctions programs
  - [ ] 5.2: Extract effective dates where available
  - [ ] 5.3: Include reason/basis for sanction if provided

- [ ] Task 6: Implement PEP detection (AC: #4)
  - [ ] 6.1: Check topics field for "role.pep"
  - [ ] 6.2: Distinguish PEP-only from sanctioned entities
  - [ ] 6.3: Include position held for PEPs
  - [ ] 6.4: Add due diligence recommendation for PEPs

- [ ] Task 7: Integrate caching (AC: #2)
  - [ ] 7.1: Accept CacheManager in constructor
  - [ ] 7.2: Generate cache keys with entity name/ID
  - [ ] 7.3: Check cache before API calls
  - [ ] 7.4: Store results with 24-hour TTL

- [ ] Task 8: Implement error handling (AC: #5)
  - [ ] 8.1: Handle 429 as ResultStatus.RATE_LIMITED
  - [ ] 8.2: Handle empty results as ResultStatus.NO_DATA with comprehensive search note
  - [ ] 8.3: Include alias warning in no-match response
  - [ ] 8.4: Catch httpx.TimeoutException -> AdapterTimeoutError
  - [ ] 8.5: Handle malformed JSON -> AdapterParseError

- [ ] Task 9: Implement health check (AC: #1)
  - [ ] 9.1: Create simple API ping query
  - [ ] 9.2: Return True on success, False on failure

- [ ] Task 10: Update exports (AC: #1)
  - [ ] 10.1: Add OpenSanctionsAdapter to `adapters/__init__.py`

- [ ] Task 11: Create tests (AC: #6)
  - [ ] 11.1: Create `tests/adapters/test_opensanctions.py`
  - [ ] 11.2: Create `tests/fixtures/opensanctions_entity.json`
  - [ ] 11.3: Create `tests/fixtures/opensanctions_pep.json`
  - [ ] 11.4: Create `tests/fixtures/opensanctions_no_match.json`
  - [ ] 11.5: Test successful query with mocked response
  - [ ] 11.6: Test confidence score mapping
  - [ ] 11.7: Test multiple sanctions lists
  - [ ] 11.8: Test PEP detection (FR19)
  - [ ] 11.9: Test no match scenario
  - [ ] 11.10: Test rate limiting
  - [ ] 11.11: Test timeout error
  - [ ] 11.12: Test cache hit behavior
  - [ ] 11.13: Test health check success/failure

## Story Metadata

| Field | Value |
|-------|-------|
| Epic | 6 - Conflict & Security Analysis |
| Story ID | 6.2 |
| Story Key | 6-2-opensanctions-adapter |
| Priority | High |
| Complexity | Medium |
| Dependencies | Stories 1.3, 1.4 |

## References

- [Source: architecture.md#Adapter-Architecture] - Protocol pattern
- [Source: architecture.md#Cache-Architecture] - TTL defaults (24 hours for OpenSanctions)
- [Source: project-context.md#Error-Handling-Contract] - Exception types
- [OpenSanctions API Documentation](https://www.opensanctions.org/docs/api/)
- [OpenSanctions Data Model](https://www.opensanctions.org/docs/entities/)
- [OpenSanctions Datasets](https://www.opensanctions.org/datasets/)

---

## Senior Developer Review

**Reviewer:** Senior Developer Agent
**Date:** 2026-01-09
**Review Cycle:** 1

### Review Outcome: APPROVE

### Issues Found

#### Issue 1: Minor - Confidence Level Mapping Mismatch with Story Specification
**Severity:** Minor
**File:** `/Volumes/IceStationZero/Projects/ignifer/src/ignifer/adapters/opensanctions.py:74-90`
**Description:** The story specification (lines 148-152) defines the mapping as:
- `score >= 0.9` -> `ConfidenceLevel.HIGH`
- `score >= 0.7` -> `ConfidenceLevel.MEDIUM`
- `score >= 0.5` -> `ConfidenceLevel.LOW`

However, the implementation uses `VERY_LIKELY`, `LIKELY`, `EVEN_CHANCE`, and `UNLIKELY` which are the correct enum values from the `ConfidenceLevel` enum. The story specification incorrectly references non-existent enum values (HIGH, MEDIUM, LOW). The implementation is actually correct - it uses the proper ICD 203 confidence levels that exist in the codebase.
**Impact:** None - implementation is correct; story spec should be updated.
**Fix:** Update story specification to reflect actual enum values used.

#### Issue 2: Minor - Missing Test for Stale Cache Behavior
**Severity:** Minor
**File:** `/Volumes/IceStationZero/Projects/ignifer/tests/adapters/test_opensanctions.py`
**Description:** The `_build_result_from_cache` method is tested via `test_cache_hit`, but there's no explicit test for when `cached.is_stale` is True. The code correctly checks `not cached.is_stale` (line 205, 365), but there's no test verifying that stale cache entries trigger a fresh API call.
**Impact:** Low - edge case not covered but main path works.
**Fix:** Add test case that mocks a cache entry with `is_stale=True` and verifies API is called.

#### Issue 3: Minor - f-string in Logging Statement with Potential Performance Impact
**Severity:** Minor/Nitpick
**File:** `/Volumes/IceStationZero/Projects/ignifer/src/ignifer/adapters/opensanctions.py:206, 224, 374`
**Description:** The code uses f-strings inside `logger.debug()` and `logger.info()` calls, e.g., `logger.debug(f"Cache hit for {key}")`. While functional, lazy string formatting with `%s` is preferred for logging performance when debug logging is disabled.
**Impact:** Minimal performance impact in production with debug disabled.
**Fix:** Consider using `logger.debug("Cache hit for %s", key)` format. This is a nitpick - current approach is acceptable.

#### Issue 4: Minor - Inconsistent Query Parameter in AC2
**Severity:** Minor
**File:** Story specification line 30-31
**Description:** AC2 states: `await adapter.query(QueryParams(topic="Viktor Vekselberg"))` but `QueryParams` doesn't have a `topic` field - it has a `query` field. The implementation correctly uses `params.query` (line 171).
**Impact:** None - story spec has a typo, implementation is correct.
**Fix:** Update story specification AC2 to use `query=` instead of `topic=`.

#### Issue 5: Minor - No Test for httpx.RequestError Exception Path
**Severity:** Minor
**File:** `/Volumes/IceStationZero/Projects/ignifer/tests/adapters/test_opensanctions.py`
**Description:** Lines 235-236 in the adapter handle `httpx.RequestError`, but tests only cover `TimeoutException` and `ConnectError`. The generic `RequestError` path should be tested.
**Impact:** Low - code path exists but isn't explicitly tested.
**Fix:** Add test case for generic `httpx.RequestError`.

#### Issue 6: Nitpick - Missing birthDate in opensanctions_pep.json Fixture
**Severity:** Nitpick
**File:** `/Volumes/IceStationZero/Projects/ignifer/tests/fixtures/opensanctions_pep.json`
**Description:** The PEP fixture doesn't include a `birthDate` field in properties, while the entity fixture does. This provides less coverage of the `_normalize_entity` method's handling of missing fields.
**Impact:** Minimal - handled by defensive code.
**Fix:** Consider adding `birthDate` to PEP fixture for consistency.

#### Issue 7: Minor - Uncovered Lines in check_sanctions for Rate Limiting and Errors
**Severity:** Minor
**File:** `/Volumes/IceStationZero/Projects/ignifer/src/ignifer/adapters/opensanctions.py:394-396, 413-414, 419-420, 428-429`
**Description:** The `check_sanctions` method has similar error handling paths as `search_entity`, but the rate limiting and server error paths in `check_sanctions` aren't covered by tests (lines 394-396, 413-414). Coverage report shows 86% with these lines missing.
**Impact:** Low - these paths mirror tested paths in `search_entity`.
**Fix:** Add test cases for `check_sanctions` with 429 and 500 responses for completeness.

### Summary

The OpenSanctions adapter implementation is **well-structured and production-ready**. The code:

1. **Correctly implements the OSINTAdapter protocol** with all required methods (`query`, `health_check`, `source_name`, `base_quality_tier`)
2. **Follows all project rules** including:
   - Adapter-owned httpx client with lazy initialization
   - stdlib logging with `__name__`
   - `datetime.now(timezone.utc)` for all timestamps
   - snake_case for all JSON fields
   - Correct error handling contract (exceptions for unexpected, Result types for expected)
3. **Meets all acceptance criteria**:
   - AC1: Full OSINTAdapter implementation with all methods
   - AC2: Entity screening with match confidence, entity type, sanctions lists, PEP status
   - AC3: Multiple sanctions lists handling with counts
   - AC4: PEP detection without sanctions (FR19 compliance)
   - AC5: No match handling with comprehensive confidence note
   - AC6: All 49 tests pass
4. **Exceeds coverage requirement** at 86% (target was 80%)
5. **Correct layering** - no imports from server.py or tools

All issues found are Minor or Nitpick severity. The implementation follows established patterns from other adapters (WikidataAdapter, ACLEDAdapter) and integrates properly with the cache layer.

**Recommendation:** APPROVE for merge. Consider addressing minor test coverage gaps in a follow-up PR.

---

## Change Log

| Date | Change |
|------|--------|
| 2026-01-09 | Story 6.2 drafted |
| 2026-01-09 | Senior Developer Review: APPROVED with minor issues noted |
