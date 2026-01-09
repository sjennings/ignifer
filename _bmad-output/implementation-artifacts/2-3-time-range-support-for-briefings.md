# Story 2.3: Time Range Support for Briefings

Status: done

## Story

As a **news follower**,
I want **to specify time ranges for my briefings**,
so that **I can focus on recent events or investigate specific periods**.

## Acceptance Criteria

1. **AC1: Optional `time_range` Parameter Added to `briefing()` Tool**
   - **Given** the existing `briefing()` tool from Epic 1
   - **When** I add optional `time_range` parameter
   - **Then** the tool signature becomes `briefing(topic: str, time_range: str | None = None) -> str`
   - **And** docstring is updated to document supported formats
   - **And** MCP tool discovery shows the new parameter

2. **AC2: Natural Language Time Range Parsing**
   - **Given** user provides time_range parameter
   - **When** time_range uses natural language like:
     - "last 24 hours", "last 48 hours"
     - "this week", "last week"
     - "last 7 days", "last 30 days"
   - **Then** these are parsed and converted to GDELT-compatible timespan format
   - **And** parsing is case-insensitive

3. **AC3: ISO Date Range Support**
   - **Given** user provides ISO date range
   - **When** time_range is "2026-01-01 to 2026-01-08"
   - **Then** uses GDELT STARTDATETIME/ENDDATETIME parameters
   - **And** validates date formats before API call

4. **AC4: GDELT Query Time-Filtered**
   - **Given** `briefing("Syria", time_range="last 48 hours")` is called
   - **When** GDELTAdapter.query() is invoked
   - **Then** GDELT API receives appropriate timespan parameter (e.g., `timespan=48h`)
   - **And** results only include articles from that period
   - **And** output indicates the time range covered

5. **AC5: Default Time Range Behavior**
   - **Given** user calls `briefing("Ukraine")` without time_range
   - **When** GDELTAdapter.query() is invoked
   - **Then** defaults to sensible time range (current: 1 week)
   - **And** output indicates the default time range used

6. **AC6: Invalid Time Range Error Handling**
   - **Given** time_range parsing encounters an invalid format
   - **When** user provides "yesterday morning" or other unparseable string
   - **Then** returns helpful error explaining supported formats
   - **And** suggests alternatives like "last 24 hours"
   - **And** does NOT make API call with invalid parameters

7. **AC7: No Results for Time Range Handling**
   - **Given** GDELT returns no results for the specified time range
   - **When** query completes with empty results
   - **Then** suggests trying a broader time range
   - **And** indicates no articles found for that specific period

8. **AC8: Cache Key Includes Time Range**
   - **Given** time_range affects query results
   - **When** caching is applied
   - **Then** cache key includes time_range to prevent stale results
   - **And** different time ranges don't share cached results

9. **AC9: Tests Pass with Good Coverage**
   - **Given** the time range implementation
   - **When** I run `pytest tests/ -v -k time_range`
   - **Then** all time range tests pass
   - **And** covers parsing, GDELT integration, and error cases

## Tasks / Subtasks

- [ ] Task 1: Add `time_range` field to QueryParams model (AC: #1, #4)
  - [ ] 1.1: Update `src/ignifer/models.py` - add `time_range: str | None = None` to QueryParams
  - [ ] 1.2: Run `make type-check` to verify model change

- [ ] Task 2: Create time range parser module (AC: #2, #3, #6)
  - [ ] 2.1: Create `src/ignifer/timeparse.py` (or add to existing module)
  - [ ] 2.2: Implement `parse_time_range(time_range: str) -> TimeRangeResult` function
  - [ ] 2.3: Return dataclass with `gdelt_timespan: str | None` and `start_datetime: str | None`, `end_datetime: str | None`
  - [ ] 2.4: Handle natural language: "last N hours/days/weeks", "this week", "last week"
  - [ ] 2.5: Handle ISO date range: "YYYY-MM-DD to YYYY-MM-DD"
  - [ ] 2.6: Return parse error with helpful message for invalid formats
  - [ ] 2.7: Write unit tests for parser in `tests/test_timeparse.py`

- [ ] Task 3: Update GDELTAdapter to support time range (AC: #4, #5, #8)
  - [ ] 3.1: Modify `GDELTAdapter.query()` to read `params.time_range`
  - [ ] 3.2: If time_range provided, parse and add to GDELT query params
  - [ ] 3.3: Update cache key generation to include time_range
  - [ ] 3.4: Default to "1week" if time_range is None (current behavior)
  - [ ] 3.5: Add tests for time-filtered queries in `test_gdelt.py`

- [ ] Task 4: Update `briefing()` tool in server.py (AC: #1, #5, #6, #7)
  - [ ] 4.1: Add `time_range: str | None = None` parameter to `briefing()`
  - [ ] 4.2: Update docstring to document supported formats
  - [ ] 4.3: Pass time_range to QueryParams when calling adapter
  - [ ] 4.4: Handle time_range parse errors with user-friendly message
  - [ ] 4.5: Indicate time range in output (covered period)

- [ ] Task 5: Update OutputFormatter for time range display (AC: #4, #7)
  - [ ] 5.1: Add time range info to briefing output header
  - [ ] 5.2: Update NO_DATA message to suggest broader time range
  - [ ] 5.3: Preserve existing output formatting

- [ ] Task 6: Create integration tests (AC: #9)
  - [ ] 6.1: Test `briefing()` with various time_range values
  - [ ] 6.2: Test cache isolation for different time ranges
  - [ ] 6.3: Test error handling for invalid time ranges
  - [ ] 6.4: Run `make lint && make type-check && pytest tests/`

## Dev Notes

### CRITICAL: Architecture Compliance

**FROM project-context.md:**

1. **snake_case** for all fields - `time_range` NOT `timeRange`
2. **`datetime.now(timezone.utc)`** - if parsing dates, ensure timezone awareness
3. **stdlib `logging` only** - use `logging.getLogger(__name__)`
4. **Hybrid error handling** - time_range parse errors return user-friendly message (not exception)
5. **Layer rule** - timeparse.py can be imported by adapters and server.py

### GDELT API Time Range Parameters

**FROM GDELT DOC 2.0 API Documentation:**

| Parameter | Format | Description |
|-----------|--------|-------------|
| `timespan` | `Nmin`, `Nh`, `Nd`, `Nw`, `Nm` | Relative offset from now |
| `startdatetime` | `YYYYMMDDHHMMSS` | Absolute start time |
| `enddatetime` | `YYYYMMDDHHMMSS` | Absolute end time |

**Timespan Examples:**
- `15min` - last 15 minutes (minimum)
- `1h`, `24hours` - hours
- `1d`, `7days` - days
- `1w`, `2weeks` - weeks
- `1m`, `3months` - months

**Reference:** [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)

### Time Range Parser Design

```python
# src/ignifer/timeparse.py
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import re

@dataclass
class TimeRangeResult:
    """Result of parsing a time range string."""
    gdelt_timespan: str | None = None  # e.g., "48h", "7d"
    start_datetime: str | None = None  # YYYYMMDDHHMMSS format
    end_datetime: str | None = None    # YYYYMMDDHHMMSS format
    error: str | None = None           # User-friendly error message

    @property
    def is_valid(self) -> bool:
        return self.error is None

def parse_time_range(time_range: str) -> TimeRangeResult:
    """Parse user time range into GDELT parameters."""
    ...
```

### Natural Language Patterns to Support

| User Input | GDELT Timespan |
|------------|----------------|
| "last 24 hours" | `24h` |
| "last 48 hours" | `48h` |
| "last 7 days" | `7d` |
| "last 30 days" | `30d` |
| "this week" | `7d` |
| "last week" | `14d` (offset by 7) → Use startdatetime/enddatetime |
| "1 hour" | `1h` |
| "3 days" | `3d` |

**Regex patterns:**
```python
# "last N hours/days/weeks"
LAST_N_PATTERN = re.compile(r"last\s+(\d+)\s+(hour|hours|day|days|week|weeks)", re.IGNORECASE)

# "N hours/days/weeks"
N_UNIT_PATTERN = re.compile(r"(\d+)\s+(hour|hours|day|days|week|weeks)", re.IGNORECASE)

# ISO date range "YYYY-MM-DD to YYYY-MM-DD"
DATE_RANGE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
```

### GDELTAdapter Modification

Current code in `gdelt.py:107-116`:
```python
query_params = {
    "query": params.query,
    "mode": "ArtList",
    "format": "json",
    "maxrecords": 75,
    "timespan": "1week",  # <-- This needs to be dynamic
    "sort": "datedesc",
}
```

**Modified approach:**
```python
# Parse time range if provided
time_result = parse_time_range(params.time_range) if params.time_range else None

query_params = {
    "query": params.query,
    "mode": "ArtList",
    "format": "json",
    "maxrecords": 75,
    "sort": "datedesc",
}

if time_result and time_result.gdelt_timespan:
    query_params["timespan"] = time_result.gdelt_timespan
elif time_result and time_result.start_datetime:
    query_params["startdatetime"] = time_result.start_datetime
    if time_result.end_datetime:
        query_params["enddatetime"] = time_result.end_datetime
else:
    query_params["timespan"] = "1week"  # Default
```

### Cache Key Update

Current cache key in `gdelt.py:77`:
```python
key = cache_key(self.source_name, "articles", search_query=f"{params.query}:1week")
```

**Updated:**
```python
timespan = params.time_range or "1week"
key = cache_key(self.source_name, "articles", search_query=f"{params.query}:{timespan}")
```

### briefing() Tool Update

Current signature:
```python
async def briefing(topic: str) -> str:
```

**Updated:**
```python
@mcp.tool()
async def briefing(topic: str, time_range: str | None = None) -> str:
    """OSINT intelligence briefing from 65+ language sources.

    ...existing docstring...

    Args:
        topic: Topic to research (2-4 words)
        time_range: Optional time filter. Supported formats:
            - "last 24 hours", "last 48 hours"
            - "last 7 days", "last 30 days"
            - "this week", "last week"
            - "2026-01-01 to 2026-01-08" (ISO date range)
            If not specified, defaults to last 7 days.

    Returns:
        Full briefing + article extracts. Include ALL of it in Part 2.
    """
```

### Error Message for Invalid Time Range

```python
f"## Invalid Time Range\n\n"
f"Could not parse time range: **{time_range}**\n\n"
f"**Supported formats:**\n"
f"- \"last 24 hours\", \"last 48 hours\"\n"
f"- \"last 7 days\", \"last 30 days\"\n"
f"- \"this week\", \"last week\"\n"
f"- \"2026-01-01 to 2026-01-08\" (ISO date range)\n\n"
f"**Examples:**\n"
f"- briefing(\"Syria\", time_range=\"last 48 hours\")\n"
f"- briefing(\"Ukraine\", time_range=\"last 7 days\")"
```

### Output Formatting Update

Add time range to briefing header:
```
═══════════════════════════════════════════════════════
              INTELLIGENCE BRIEFING
              UNCLASSIFIED // OSINT
═══════════════════════════════════════════════════════
TOPIC: UKRAINE
DATE:  2026-01-09 14:30 UTC
TIME RANGE: Last 48 hours                    <-- NEW
───────────────────────────────────────────────────────
```

### Test Cases Required

1. **Parser unit tests (`test_timeparse.py`):**
   - `test_parse_last_n_hours_valid`
   - `test_parse_last_n_days_valid`
   - `test_parse_this_week`
   - `test_parse_last_week`
   - `test_parse_iso_date_range`
   - `test_parse_invalid_format_returns_error`
   - `test_parse_case_insensitive`

2. **GDELT adapter tests (`test_gdelt.py`):**
   - `test_query_with_time_range_uses_timespan`
   - `test_query_with_date_range_uses_datetime_params`
   - `test_query_default_time_range`
   - `test_cache_key_includes_time_range`

3. **Integration tests (`test_server.py`):**
   - `test_briefing_with_time_range`
   - `test_briefing_invalid_time_range_returns_error`
   - `test_briefing_default_time_range`

### Dependencies

- **Requires:** Story 1.5 (GDELTAdapter) - implemented (existing code)
- **Requires:** Story 1.6 (briefing tool) - implemented (existing code)
- **Blocked by:** None
- **Enables:** Time-filtered economic queries (future enhancement)

### Previous Story Intelligence

From Story 2-2 patterns:
- Use lazy initializer pattern for adapters
- Follow existing docstring style for MCP tools
- Error messages should be user-friendly markdown
- Use pytest-httpx for mocking HTTP responses

From GDELT adapter code review:
- `query_params` dict built at line 109-116
- Cache key generated at line 77
- Default timespan is "1week"
- Retry logic with exponential backoff for rate limiting

### File Impact Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/ignifer/models.py` | MODIFY | Add `time_range` to QueryParams |
| `src/ignifer/timeparse.py` | CREATE | New time range parser module |
| `src/ignifer/adapters/gdelt.py` | MODIFY | Support time_range in query() |
| `src/ignifer/server.py` | MODIFY | Add time_range param to briefing() |
| `src/ignifer/output.py` | MODIFY | Display time range in output |
| `tests/test_timeparse.py` | CREATE | Unit tests for parser |
| `tests/adapters/test_gdelt.py` | MODIFY | Add time range tests |
| `tests/test_server.py` | MODIFY | Add briefing time range tests |

---

## Senior Developer Review (AI)

**Review Date:** 2026-01-09
**Reviewer:** Claude (Adversarial Code Review)
**Story:** 2-3 Time Range Support for Briefings

---

### Acceptance Criteria Coverage Analysis

| AC | Status | Notes |
|----|--------|-------|
| AC1 | PASS | `briefing(topic: str, time_range: str \| None = None)` signature implemented, docstring updated |
| AC2 | PASS | Natural language parsing works for hours/days/weeks/months, case-insensitive |
| AC3 | PASS | ISO date range "YYYY-MM-DD to YYYY-MM-DD" implemented with validation |
| AC4 | PASS | GDELT adapter uses timespan parameter correctly |
| AC5 | PARTIAL | Default is "1week" but output does NOT indicate default time range (see Issue #1) |
| AC6 | PASS | Invalid formats return helpful error with examples |
| AC7 | PARTIAL | NO_DATA message does not suggest broader time range (see Issue #2) |
| AC8 | PASS | Cache key includes time_range via `f"{params.query}:{timespan}"` |
| AC9 | PASS | Tests cover parsing, GDELT integration, error cases |

---

### Issues Found

#### Issue #1: AC5 Violation - Default Time Range Not Indicated in Output
**Severity:** MEDIUM

**Location:** `src/ignifer/output.py` line 112-113

**Problem:** AC5 explicitly states "output indicates the default time range used" when no time_range is provided. However, the `_format_success` method only displays TIME RANGE when `time_range` is explicitly provided:

```python
if time_range:
    lines.append(f"TIME RANGE: {time_range}")
```

When `time_range` is `None`, no indication is given that the default "Last 7 days" was applied.

**Expected Behavior:** When `time_range=None`, output should show `TIME RANGE: Last 7 days (default)` to inform users what period is covered.

**Fix Required:** Modify `output.py` to display default time range:
```python
if time_range:
    lines.append(f"TIME RANGE: {time_range}")
else:
    lines.append("TIME RANGE: Last 7 days (default)")
```

---

#### Issue #2: AC7 Violation - NO_DATA Message Missing Time Range Suggestion
**Severity:** MEDIUM

**Location:** `src/ignifer/output.py` lines 235-258

**Problem:** AC7 explicitly requires "suggests trying a broader time range" when GDELT returns no results. The current `_format_no_data` method does NOT mention time ranges:

```python
def _format_no_data(self, result: OSINTResult) -> str:
    ...
    lines.append("### RECOMMENDED ACTIONS")
    lines.append("")
    lines.append(f"1. {suggestion}")
    lines.append("2. Try more specific or alternative keywords")
    lines.append("3. Verify spelling of names or locations")
    lines.append("4. Use English terms for broader coverage")
    lines.append("5. Expand temporal search range if available")  # Generic, not specific
```

The message "Expand temporal search range if available" is vague. AC7 requires explicitly suggesting a broader time range when a specific time range was used.

**Expected Behavior:** When NO_DATA with a time_range, output should say something like "Try a broader time range (e.g., 'last 30 days' instead of 'last 24 hours')"

**Fix Required:** The `_format_no_data` method needs to accept `time_range` parameter and provide specific suggestions when a time range was used.

---

#### Issue #3: Test Does Not Verify AC5 Fully
**Severity:** LOW

**Location:** `tests/test_server.py` lines 152-188

**Problem:** The test `test_briefing_default_time_range` asserts that `TIME RANGE:` is NOT in the output when `time_range=None`:

```python
# Should not have TIME RANGE line when not specified
assert "TIME RANGE:" not in result
```

This test is asserting the **wrong behavior**. According to AC5, the output SHOULD indicate the default time range. The test is validating the bug, not the requirement.

**Fix Required:** After fixing Issue #1, update test to assert:
```python
assert "TIME RANGE: Last 7 days (default)" in result
```

---

#### Issue #4: Cache Key Uses Raw User Input Instead of Normalized Value
**Severity:** LOW

**Location:** `src/ignifer/adapters/gdelt.py` lines 77-79

**Problem:** The cache key uses `params.time_range or "1week"`:

```python
timespan = params.time_range or "1week"
key = cache_key(self.source_name, "articles", search_query=f"{params.query}:{timespan}")
```

This means `"last 24 hours"`, `"LAST 24 HOURS"`, and `"Last 24 Hours"` would generate different cache keys despite producing the same API request (`timespan=24h`).

**Impact:** Reduced cache efficiency - same query may hit API multiple times due to case differences.

**Fix Required:** Use the parsed/normalized timespan value in cache key:
```python
time_result = parse_time_range(params.time_range) if params.time_range else None
if time_result and time_result.gdelt_timespan:
    cache_timespan = time_result.gdelt_timespan
elif time_result and time_result.start_datetime:
    cache_timespan = f"{time_result.start_datetime}-{time_result.end_datetime}"
else:
    cache_timespan = "1week"
key = cache_key(self.source_name, "articles", search_query=f"{params.query}:{cache_timespan}")
```

---

#### Issue #5: TimeRangeResult.is_valid Returns True for Empty Result
**Severity:** LOW

**Location:** `src/ignifer/timeparse.py` lines 31-34

**Problem:** The test `test_time_range_result_is_valid_property` (line 158-159) reveals an edge case:

```python
empty_result = TimeRangeResult()
assert empty_result.is_valid  # No error means valid
```

A `TimeRangeResult` with no `gdelt_timespan`, no `start_datetime`, and no `error` is considered "valid" but is actually useless - it provides no time filtering. This could lead to silent failures if parsing logic has a bug.

**Impact:** If a regex pattern fails to capture groups properly, a result with all `None` fields except `error` would be considered valid.

**Fix Required:** Strengthen the `is_valid` property:
```python
@property
def is_valid(self) -> bool:
    """Check if the result is valid and has actionable data."""
    if self.error is not None:
        return False
    # Must have either timespan or date range
    return self.gdelt_timespan is not None or self.start_datetime is not None
```

---

#### Issue #6: "last week" Implementation May Be Off By One Day
**Severity:** LOW

**Location:** `src/ignifer/timeparse.py` lines 60-67

**Problem:** The "last week" implementation calculates 7-14 days ago:

```python
if time_range.lower() == "last week":
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=14)
    end = now - timedelta(days=7)
```

This includes the current moment in the calculation. If "now" is Friday 10:00 AM:
- `end` = Friday 10:00 AM last week (7 days ago)
- `start` = Friday 10:00 AM two weeks ago (14 days ago)

The problem is the `end` time cuts off at the exact moment 7 days ago, potentially excluding articles from "last week" that were published after that moment on the start day of "this week".

**Impact:** User asking for "last week" on Friday 10 AM would miss articles from last Friday 10:01 AM to midnight.

**Recommendation:** Consider setting `end` to the START of "this week" (Sunday/Monday 00:00:00 UTC) and `start` to the START of "last week" for more intuitive weekly boundaries. However, this is a design decision - current implementation is acceptable if documented.

---

### Summary

| Severity | Count | Issues |
|----------|-------|--------|
| HIGH | 0 | - |
| MEDIUM | 2 | #1 (AC5 default indicator), #2 (AC7 time range suggestion) |
| LOW | 4 | #3 (test validates bug), #4 (cache key normalization), #5 (empty result valid), #6 (week boundary) |

---

### Final Outcome: **Changes Requested**

The implementation is mostly complete and well-structured, but two MEDIUM severity issues directly violate acceptance criteria:

1. **AC5 Violation:** Output must indicate default time range - currently silent
2. **AC7 Violation:** NO_DATA message must suggest broader time range - currently generic

**Required Fixes Before Approval:**
1. Modify `output.py` `_format_success()` to display "Last 7 days (default)" when `time_range` is None
2. Modify `output.py` `_format_no_data()` to accept `time_range` parameter and suggest broader ranges
3. Update `test_server.py` `test_briefing_default_time_range` to verify default range appears in output

**Recommended Improvements (not blocking):**
- Normalize cache key to use parsed timespan value
- Strengthen `TimeRangeResult.is_valid` to require actionable data

---

**Status:** Do NOT update sprint-status.yaml until fixes are applied.

---

## Follow-Up Review (Post-Fix Verification)

**Review Date:** 2026-01-09
**Reviewer:** Claude (Verification Review)
**Story:** 2-3 Time Range Support for Briefings

---

### Fix Verification Summary

All three requested fixes have been properly implemented:

#### Fix #1: AC5 - Default Time Range Display (VERIFIED)
**Location:** `src/ignifer/output.py` lines 112-115

```python
if time_range:
    lines.append(f"TIME RANGE: {time_range}")
else:
    lines.append("TIME RANGE: Last 7 days (default)")
```

The output now correctly displays "TIME RANGE: Last 7 days (default)" when no time_range is provided.

#### Fix #2: AC7 - NO_DATA Suggestion for Broader Time Range (VERIFIED)
**Location:** `src/ignifer/output.py` lines 237-261

```python
def _format_no_data(self, result: OSINTResult, time_range: str | None = None) -> str:
    ...
    if time_range:
        lines.append("5. Try a broader time range like 'last 30 days'")
    else:
        lines.append("5. Expand temporal search range if available")
```

The method now accepts `time_range` parameter and provides specific suggestions when a time_range was used.

#### Fix #3: Test Update (VERIFIED)
**Location:** `tests/test_server.py` lines 179-184

```python
result = await briefing.fn("Ukraine")

# Should show default time range indicator
assert "TIME RANGE:" in result
assert "7 days" in result
assert "default" in result.lower()
```

The test now correctly validates that the default time range IS shown in output.

---

### Test Results

All tests pass:
- `test_briefing_default_time_range` - PASSED
- `test_briefing_with_time_range` - PASSED
- `test_briefing_no_data_returns_suggestions` - PASSED
- Full test suite: 158 tests PASSED

---

### Acceptance Criteria Final Status

| AC | Status | Notes |
|----|--------|-------|
| AC1 | PASS | `briefing(topic: str, time_range: str \| None = None)` signature implemented |
| AC2 | PASS | Natural language parsing works for hours/days/weeks/months |
| AC3 | PASS | ISO date range "YYYY-MM-DD to YYYY-MM-DD" implemented |
| AC4 | PASS | GDELT adapter uses timespan parameter correctly |
| AC5 | PASS | Default time range now displayed in output (FIX APPLIED) |
| AC6 | PASS | Invalid formats return helpful error with examples |
| AC7 | PASS | NO_DATA now suggests broader time range (FIX APPLIED) |
| AC8 | PASS | Cache key includes time_range |
| AC9 | PASS | All tests pass (158/158) |

---

### Remaining Advisory Notes (Non-Blocking)

The following low-severity items from the original review were not addressed but do not block approval:

1. **Cache Key Uses Raw User Input** (Issue #4): Cache efficiency could be improved by normalizing time_range values before generating cache keys.

2. **TimeRangeResult.is_valid Edge Case** (Issue #5): A `TimeRangeResult` with all None fields (except error) is considered valid. Consider strengthening validation.

3. **"last week" Boundary Calculation** (Issue #6): Current implementation uses relative 7-14 day offset. Weekly boundary alignment could be more intuitive but current behavior is acceptable.

These are recommended improvements for future maintenance.

---

### Final Outcome: **APPROVED**

All MEDIUM severity issues have been resolved. The implementation now fully satisfies all acceptance criteria for Story 2-3: Time Range Support for Briefings.

**Status:** Ready to update sprint-status.yaml to 'done'
