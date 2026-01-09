# Story 2.3: Time Range Support for Briefings

Status: ready-for-dev

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
