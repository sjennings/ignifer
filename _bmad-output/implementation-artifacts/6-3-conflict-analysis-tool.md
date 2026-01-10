# Story 6.3: Conflict Analysis Tool

**Epic:** Epic 6 - Conflict & Security Analysis
**Status:** done
**Priority:** High
**Estimate:** Medium

## User Story

As a **geopolitical analyst**,
I want **to analyze conflict situations in any country or region**,
So that **I can assess security conditions and violence trends**.

## Acceptance Criteria

1. **AC1: Conflict Analysis Tool Created**
   - **Given** ACLEDAdapter from Story 6.1
   - **When** I add `conflict_analysis(region: str, time_range: str = None)` tool to server.py
   - **Then** it:
     - Accepts country name, region, or geographic area
     - Calls ACLEDAdapter for conflict events
     - Returns formatted conflict intelligence via OutputFormatter

2. **AC2: Country/Region Conflict Analysis Works**
   - **Given** user asks "What's the conflict situation in Ethiopia?"
   - **When** Claude calls `conflict_analysis("Ethiopia")`
   - **Then** returns formatted output including:
     - Summary of recent conflict activity
     - Event count by type (battles, civilian targeting, protests)
     - Primary actors involved
     - Fatality trends (increasing/decreasing/stable)
     - Geographic hotspots within the country
     - Source: ACLED with data date range

3. **AC3: Time Range Filtering Works**
   - **Given** user specifies time range
   - **When** Claude calls `conflict_analysis("Sahel", time_range="last 90 days")`
   - **Then** returns events for that period
   - **And** includes comparison to previous period

4. **AC4: Geographic Distribution Display (FR20)**
   - **Given** user asks about geographic distribution
   - **When** conflict_analysis returns results
   - **Then** includes breakdown by admin region/province
   - **And** identifies areas with highest incident concentration

5. **AC5: Missing Credentials Error Handling**
   - **Given** ACLED credentials are not configured
   - **When** user attempts conflict analysis
   - **Then** returns helpful error with registration instructions

6. **AC6: No Conflict Activity Handling**
   - **Given** region has no recent conflict events
   - **When** analysis completes
   - **Then** indicates low/no conflict activity
   - **And** notes this could indicate stability or data coverage limitations

## Technical Notes

### Tool Implementation Pattern

This is a **tool** story, not an adapter story. The ACLEDAdapter is already implemented (Story 6.1). This story:
1. Creates a new MCP tool in `server.py`
2. Uses ACLEDAdapter for data retrieval
3. Uses OutputFormatter for response formatting

**FROM Story 6.1:** ACLEDAdapter provides:
- `source_name = "acled"` and `base_quality_tier = QualityTier.HIGH`
- `async query(params: QueryParams) -> OSINTResult`
- `async get_events(country: str, date_range: str = None) -> OSINTResult`
- Results include: event types, actor categories, fatality counts, geographic distribution
- Trend comparison when date range is specified

### Tool Registration Pattern

Follow the existing tool registration pattern in server.py:

```python
from fastmcp import FastMCP

mcp = FastMCP("ignifer")

@mcp.tool()
async def conflict_analysis(
    region: str,
    time_range: str | None = None
) -> str:
    """
    Analyze conflict situations in a country or region.

    Args:
        region: Country name, region, or geographic area (e.g., "Ethiopia", "Sahel")
        time_range: Optional time filter (e.g., "last 30 days", "last 90 days")

    Returns:
        Formatted conflict analysis with event counts, actors, and trends
    """
    # Implementation
```

### Output Format Requirements

The OutputFormatter should produce output like:

```
CONFLICT ANALYSIS: Ethiopia
Period: Last 30 days (2025-12-10 to 2026-01-09)

SUMMARY
-------
Total Events: 127
Total Fatalities: 342
Trend: INCREASING (+23% vs previous period)

EVENT TYPES
-----------
- Battles: 45 events (35%)
- Violence against civilians: 38 events (30%)
- Protests: 24 events (19%)
- Explosions/Remote violence: 12 events (9%)
- Strategic developments: 8 events (6%)

PRIMARY ACTORS
--------------
- Ethiopian National Defense Force (ENDF): 52 events
- Fano Militia: 34 events
- Oromo Liberation Army (OLA): 28 events
- Unidentified armed groups: 13 events

GEOGRAPHIC HOTSPOTS
-------------------
- Amhara Region: 47 events (37%)
- Oromia Region: 35 events (28%)
- Tigray Region: 22 events (17%)
- SNNPR: 14 events (11%)

FATALITY TRENDS
---------------
Current period: 342 fatalities
Previous period: 278 fatalities
Change: +23% (INCREASING)

Sources: ACLED (https://acleddata.com/)
Data retrieved: 2026-01-09T14:30:00+00:00
```

### Architecture Compliance

**FROM project-context.md:**
1. **Layer rule:** Tools in server.py, adapters in adapters/ - never mix
2. **Adapter access:** Get adapter instance via `_get_adapter("acled")` helper
3. **OutputFormatter usage:** Use existing OutputFormatter class from output.py
4. **Error handling:** Catch AdapterError exceptions, convert to user-friendly messages
5. **stdlib `logging` only** - use `logging.getLogger(__name__)`
6. **ISO 8601 + timezone** for all datetime fields

### Error Handling Pattern

```python
from ignifer.adapters.base import AdapterError, AdapterAuthError, AdapterTimeoutError

async def conflict_analysis(region: str, time_range: str | None = None) -> str:
    try:
        adapter = _get_acled_adapter()
        result = await adapter.get_events(region, date_range=time_range)

        if result.status == ResultStatus.NO_DATA:
            return _format_no_conflict_message(region)

        if result.status == ResultStatus.RATE_LIMITED:
            return "ACLED API rate limit reached. Please try again later."

        return _format_conflict_analysis(result, region, time_range)

    except AdapterAuthError:
        return Settings.get_credential_error_message("acled")
    except AdapterTimeoutError:
        return f"ACLED API timed out while analyzing {region}. Please try again."
    except AdapterError as e:
        logger.error(f"ACLED adapter error: {e}")
        return f"Unable to retrieve conflict data for {region}. Please try again later."
```

### ACLEDAdapter Result Structure

From Story 6.1, the ACLEDAdapter returns `OSINTResult` with `results` dict containing:

```python
{
    "country": "Ethiopia",
    "date_range_start": "2025-12-10",
    "date_range_end": "2026-01-09",
    "total_events": 127,
    "total_fatalities": 342,
    "event_types": {
        "Battles": 45,
        "Violence against civilians": 38,
        "Protests": 24,
        "Explosions/Remote violence": 12,
        "Strategic developments": 8
    },
    "actors": {
        "Ethiopian National Defense Force (ENDF)": 52,
        "Fano Militia": 34,
        ...
    },
    "admin_regions": {
        "Amhara Region": 47,
        "Oromia Region": 35,
        ...
    },
    # Trend comparison (when date_range specified)
    "event_trend": "INCREASING",
    "fatality_trend": "INCREASING",
    "previous_period_start": "2025-11-10",
    "previous_period_end": "2025-12-09",
    "previous_period_events": 103,
    "previous_period_fatalities": 278
}
```

### Region Name Handling

The tool should handle various region formats:
- Country names: "Ethiopia", "Syria", "Burkina Faso"
- Regions: "Sahel", "Horn of Africa", "Middle East"
- Specific admin regions: "Tigray Region", "Donetsk Oblast"

For multi-country regions (e.g., "Sahel"), consider:
1. Mapping region names to country lists
2. Querying ACLED for multiple countries
3. Aggregating results

**Simplification for MVP:** Start with single-country queries. Multi-country regions can be a follow-up enhancement.

## Dependencies

- Story 6.1: ACLED Adapter (required - provides ACLEDAdapter with `get_events()`)
- Story 1.6: Output Formatting & Briefing Tool (OutputFormatter patterns)

## Files to Create/Modify

### Modified Files

| File | Change |
|------|--------|
| `src/ignifer/server.py` | Add `conflict_analysis` tool |
| `src/ignifer/output.py` | Add conflict analysis formatting (if not using existing) |

### New Files (if needed)

| File | Description |
|------|-------------|
| `tests/test_conflict_analysis.py` | Tool-level tests |

## Testing Requirements

### Unit Tests

1. **test_conflict_analysis_success** - Returns formatted analysis for valid country
2. **test_conflict_analysis_with_time_range** - Time range filtering works
3. **test_conflict_analysis_includes_event_types** - Event type breakdown present
4. **test_conflict_analysis_includes_actors** - Actor breakdown present
5. **test_conflict_analysis_includes_geographic_distribution** - Admin regions present (FR20)
6. **test_conflict_analysis_includes_trends** - Trend comparison when date range specified
7. **test_conflict_analysis_no_credentials** - Returns credential error message
8. **test_conflict_analysis_no_data** - Returns appropriate message for peaceful regions
9. **test_conflict_analysis_rate_limited** - Handles rate limiting gracefully
10. **test_conflict_analysis_timeout** - Handles timeout gracefully
11. **test_conflict_analysis_source_attribution** - Includes ACLED source info

### Coverage Target

- Minimum 80% coverage on conflict analysis tool code

## Tasks / Subtasks

- [ ] Task 1: Add conflict_analysis tool to server.py (AC: #1)
  - [ ] 1.1: Add tool function with `@mcp.tool()` decorator
  - [ ] 1.2: Implement region and time_range parameter handling
  - [ ] 1.3: Wire to ACLEDAdapter.get_events()
  - [ ] 1.4: Add proper docstring for MCP tool description

- [ ] Task 2: Implement output formatting (AC: #2)
  - [ ] 2.1: Create conflict analysis section in OutputFormatter (or separate function)
  - [ ] 2.2: Format summary with total events and fatalities
  - [ ] 2.3: Format event type breakdown with percentages
  - [ ] 2.4: Format actor breakdown
  - [ ] 2.5: Add source attribution with ACLED URL and timestamp

- [ ] Task 3: Implement geographic distribution display (AC: #4)
  - [ ] 3.1: Extract admin_regions from ACLED results
  - [ ] 3.2: Format as "Geographic Hotspots" section
  - [ ] 3.3: Calculate percentages for each region
  - [ ] 3.4: Sort by event count descending

- [ ] Task 4: Implement trend comparison display (AC: #3)
  - [ ] 4.1: Check if trend data exists in results
  - [ ] 4.2: Format trend comparison section
  - [ ] 4.3: Include previous period dates
  - [ ] 4.4: Calculate percentage change

- [ ] Task 5: Implement error handling (AC: #5, #6)
  - [ ] 5.1: Handle missing ACLED credentials
  - [ ] 5.2: Handle NO_DATA status with appropriate message
  - [ ] 5.3: Handle rate limiting
  - [ ] 5.4: Handle timeout and general errors

- [ ] Task 6: Create tests (AC: all)
  - [ ] 6.1: Create `tests/test_conflict_analysis.py`
  - [ ] 6.2: Test successful analysis with mocked adapter
  - [ ] 6.3: Test time range filtering
  - [ ] 6.4: Test geographic distribution (FR20)
  - [ ] 6.5: Test error scenarios
  - [ ] 6.6: Test output format validation

## Dev Notes

### Previous Story Learnings (from 6.1 and 6.2)

1. **Credential handling:** Use `settings.has_acled_credentials()` and `Settings.get_credential_error_message("acled")` for consistent error messages
2. **Trend comparison:** ACLEDAdapter already implements trend comparison - just format the output
3. **Cache integration:** ACLEDAdapter handles caching internally with 12-hour TTL
4. **Test patterns:** Use `pytest-httpx` for mocking HTTP responses

### Project Structure Notes

- Tool goes in `server.py` (not a new file)
- Follow existing tool patterns (briefing, track_flight, track_vessel)
- Output formatting should be consistent with other tools

### References

- [Source: epics.md#Story-6.3] - Story definition and acceptance criteria
- [Source: architecture.md#Tool-Registration] - MCP tool patterns
- [Source: project-context.md#Error-Handling-Contract] - Exception types
- [Source: 6-1-acled-adapter.md] - ACLEDAdapter implementation details
- [ACLED Data Documentation](https://acleddata.com/resources/general-guides/)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

---

## Story Metadata

| Field | Value |
|-------|-------|
| Epic | 6 - Conflict & Security Analysis |
| Story ID | 6.3 |
| Story Key | 6-3-conflict-analysis-tool |
| Priority | High |
| Complexity | Medium |
| Dependencies | Stories 6.1, 1.6 |

---

_Story created: 2026-01-09_
_Ultimate context engine analysis completed - comprehensive developer guide created_

---

## Senior Developer Review

**Reviewer:** Senior Developer Agent
**Date:** 2026-01-09
**Review Cycle:** 1

### Review Outcome: Changes Requested

### Issues Found

#### MAJOR Issues

**1. Geographic Hotspots Missing Event Counts and Percentages (AC4/FR20 Partial Compliance)**
- **Location:** `/Volumes/IceStationZero/Projects/ignifer/src/ignifer/server.py`, lines 2312-2340 (`_format_geographic_hotspots`)
- **Problem:** The story explicitly requires "breakdown by admin region/province" and "identifies areas with highest incident concentration" with percentages (see example output lines 130-135). The ACLEDAdapter computes region counts but discards them, only storing comma-separated region names in `affected_regions`. The formatter then cannot display counts or percentages.
- **Evidence:**
  ```python
  # In _format_geographic_hotspots (line 2337):
  for region in regions[:10]:  # Top 10
      lines.append(f"- {region}")  # No count, no percentage
  ```
- **Required Fix:** Either modify ACLEDAdapter to provide `top_region_N_name` and `top_region_N_count` fields (similar to actors), or add a function to count regions from the individual events in `result.results[1:]`.
- **Impact:** The geographic distribution display is incomplete compared to the acceptance criteria and example output.

**2. Missing Input Validation for Empty Region Parameter**
- **Location:** `/Volumes/IceStationZero/Projects/ignifer/src/ignifer/server.py`, lines 2471-2497 (`conflict_analysis`)
- **Problem:** The `region` parameter is not validated for empty or whitespace-only strings. Other tools (`track_flight`, `track_vessel`) validate their identifier parameters and return helpful guidance. An empty region produces a confusing message: "No conflict events found for **** in the requested time period."
- **Evidence:** Calling `conflict_analysis("")` or `conflict_analysis("   ")` results in messages with empty region names displayed as `****` or `**   **`.
- **Required Fix:** Add validation at the start of the function:
  ```python
  if not region or not region.strip():
      return (
          "## Invalid Region\n\n"
          "Please provide a valid country or region name.\n\n"
          "**Examples:**\n"
          "- Country: Ethiopia, Syria, Ukraine\n"
          "- Region: Sahel, Horn of Africa\n"
          "- Province: Tigray Region, Donetsk Oblast"
      )
  ```

#### MINOR Issues

**3. Test for Credential Error Uses Hardcoded Mock Instead of Actual Error Message**
- **Location:** `/Volumes/IceStationZero/Projects/ignifer/tests/test_conflict_analysis.py`, lines 176-194
- **Problem:** The test mocks the error message with a hardcoded string rather than using `Settings.get_credential_error_message("acled")`, and the assertion only checks for "credential" OR "ACLED" rather than verifying the registration link is present.
- **Evidence:**
  ```python
  error="ACLED API credentials not configured. Register at https://acleddata.com/register/"
  # ...
  assert "credential" in result.lower() or "ACLED" in result  # Weak assertion
  ```
- **Suggested Fix:** Use the actual error message from settings and assert the registration link is present:
  ```python
  from ignifer.config import Settings
  error=Settings.get_credential_error_message("acled")
  # ...
  assert "acleddata.com/register" in result
  ```

**4. Missing Test for Empty/Whitespace Region Input**
- **Location:** `/Volumes/IceStationZero/Projects/ignifer/tests/test_conflict_analysis.py`
- **Problem:** No test case validates the behavior when an empty or whitespace-only region is provided. Given that input validation should be added (Issue #2), a corresponding test is needed.
- **Suggested Fix:** Add test case:
  ```python
  @pytest.mark.asyncio
  async def test_conflict_analysis_invalid_region(self) -> None:
      """Empty region returns helpful error."""
      result = await conflict_analysis.fn("")
      assert "Invalid Region" in result
      assert "Ethiopia" in result  # Example in guidance
  ```

#### NITPICK Issues

**5. Inconsistent Error Response Format Headers**
- **Location:** `/Volumes/IceStationZero/Projects/ignifer/src/ignifer/server.py`, lines 2510-2555
- **Problem:** Error responses use `## Rate Limited`, `## Request Timed Out`, `## Unable to Retrieve Data`, and `## Error` but the no-data message uses `## No Conflict Data Available`. The mix of markdown-style headers (`##`) is appropriate, but the naming could be more consistent (e.g., "## No Data" vs "## No Conflict Data Available").
- **Note:** This is stylistic and does not affect functionality.

**6. Comment in `_format_geographic_hotspots` Acknowledges the Missing Functionality**
- **Location:** `/Volumes/IceStationZero/Projects/ignifer/src/ignifer/server.py`, lines 2317-2319
- **Problem:** The docstring explicitly states "Without event counts per region, we just list them. For full implementation with percentages, individual events would need to be processed." This is a self-documented known limitation that conflicts with the story requirements.
- **Note:** This is effectively a TODO that was left in place rather than addressed.

### Acceptance Criteria Compliance Summary

| AC | Status | Notes |
|----|--------|-------|
| AC1: Tool registered with @mcp.tool() | PASS | Line 2470 |
| AC2: Uses ACLEDAdapter.get_events() | PASS | Line 2501 |
| AC3: Handles time_range parameter | PASS | Line 2473, passed to adapter |
| AC4: Geographic distribution with percentages (FR20) | PARTIAL | Regions listed but no counts/percentages |
| AC5: Missing credentials -> helpful error with link | PASS | Via Settings.get_credential_error_message() |
| AC6: No data -> appropriate message | PASS | _format_no_conflict_message() |

### Summary

The `conflict_analysis` tool implementation is functional and passes all existing tests. However, two Major issues require attention:

1. **Geographic hotspots lack event counts and percentages** - This is explicitly required by AC4/FR20 and shown in the expected output example. The current implementation only lists region names without the quantitative data that would make this feature useful for analysts.

2. **No input validation for empty region** - Unlike peer tools (track_flight, track_vessel), this tool doesn't validate its primary input parameter, leading to confusing error messages.

The test coverage is adequate but could be strengthened by testing the actual credential error message and adding validation edge cases.

**Recommendation:** Address the two Major issues before marking the story complete. The geographic hotspots enhancement may require coordination with ACLEDAdapter (Story 6.1) to expose region counts in the summary structure.

---

## Senior Developer Review - Cycle 2

**Reviewer:** Senior Developer Agent
**Date:** 2026-01-09
**Review Cycle:** 2

### Previous Issues Status

- **Issue 1 (Geographic hotspots missing event counts/percentages - FR20):** FIXED
  - ACLEDAdapter (`acled.py` lines 346-355) now provides `top_region_N_name` and `top_region_N_count` fields in the `_build_summary` method
  - `_format_geographic_hotspots` (`server.py` lines 2312-2352) extracts these fields, calculates percentages, and formats output as "- Region: N events (X.X%)"
  - Test `test_conflict_analysis_geographic_hotspots_with_counts` validates the fix

- **Issue 2 (Missing input validation for empty region):** FIXED
  - Validation added at `server.py` lines 2509-2511: `if not region or not region.strip(): return "Please provide a country or region name to analyze."`
  - Returns helpful guidance instead of confusing output

- **Issue 3 (Test credential error assertion weak):** FIXED
  - Test now includes assertion at line 196: `assert "acleddata.com/register" in result`
  - This validates the registration link is present in the error message

- **Issue 4 (Missing test for empty region):** FIXED
  - `test_conflict_analysis_empty_region` (line 333) tests empty string input
  - `test_conflict_analysis_whitespace_region` (line 339) tests whitespace-only input
  - Both verify the "provide a country or region" guidance message

### New Issues Found

None

### Acceptance Criteria Compliance Summary

| AC | Status | Notes |
|----|--------|-------|
| AC1: Tool registered with @mcp.tool() | PASS | Line 2482 |
| AC2: Returns formatted output with summary, event types, actors | PASS | `_format_conflict_analysis` |
| AC3: Time range filtering works | PASS | Passed through to adapter |
| AC4: Geographic distribution with percentages (FR20) | PASS | Now includes counts and percentages |
| AC5: Missing credentials -> helpful error with link | PASS | Via Settings.get_credential_error_message() |
| AC6: No data -> appropriate message | PASS | `_format_no_conflict_message()` |

### Code Quality Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Correctness | Excellent | All previous issues addressed |
| Test Coverage | Good | 15 test cases covering success, errors, edge cases |
| Error Handling | Good | Consistent error messages with guidance |
| Documentation | Good | Clear docstrings on all helper functions |

### Review Outcome: APPROVE

### Summary

All four issues from Review Cycle 1 have been properly addressed:

1. **Geographic hotspots** now display event counts and percentages per region, fulfilling FR20 requirements. The adapter provides structured data (`top_region_N_name/count`), and the formatter calculates percentages against total events.

2. **Input validation** catches empty/whitespace region inputs early with a helpful message, preventing confusing output.

3. **Test assertions** are now more specific, verifying the actual content (registration link) rather than just presence of generic keywords.

4. **Edge case tests** cover both empty string and whitespace-only inputs.

The implementation is ready for merge. Story 6.3: Conflict Analysis Tool is complete.
