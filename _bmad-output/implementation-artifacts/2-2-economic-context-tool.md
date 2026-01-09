# Story 2.2: Economic Context Tool

Status: ready-for-dev

## Story

As a **geopolitical analyst**,
I want **to get economic indicators for any country**,
so that **I can assess economic factors affecting geopolitical situations**.

## Acceptance Criteria

1. **AC1: `economic_context` Tool Registered**
   - **Given** the WorldBankAdapter from Story 2.1
   - **When** I add `economic_context(country: str)` tool to server.py
   - **Then** it:
     - Is decorated with `@mcp.tool()`
     - Accepts country name or ISO code as parameter
     - Has comprehensive docstring for MCP tool discovery

2. **AC2: WorldBankAdapter Integration**
   - **Given** `economic_context("United States")` is called
   - **When** the tool executes
   - **Then** it:
     - Uses `_get_worldbank()` lazy initializer pattern (like `_get_adapter()`)
     - Calls `WorldBankAdapter.query()` with appropriate QueryParams
     - Returns formatted economic summary

3. **AC3: Output Formatting Works**
   - **Given** WorldBankAdapter returns successful result
   - **When** output is formatted
   - **Then** includes:
     - GDP value with year of measurement
     - GDP per capita
     - Inflation rate
     - Unemployment rate (if available)
     - Trade balance (if available)
     - Population
     - Source attribution (World Bank + retrieval timestamp)
   - **And** uses consistent formatting style with existing `briefing()` output

4. **AC4: Invalid Country Handling**
   - **Given** an invalid country name like "Fakeland"
   - **When** `economic_context("Fakeland")` is called
   - **Then** returns user-friendly error message
   - **And** suggests checking spelling or using ISO country code
   - **And** does NOT expose raw API errors to user

5. **AC5: Country Alias Resolution Works**
   - **Given** various country name formats
   - **When** queries use "USA", "United States", "US", "America"
   - **Then** all resolve correctly via WorldBankAdapter
   - **And** regional aggregates work ("European Union", "Sub-Saharan Africa")

6. **AC6: Error Handling Follows Contract**
   - **Given** WorldBankAdapter raises AdapterTimeoutError
   - **When** the tool catches the error
   - **Then** returns user-friendly timeout message (like `briefing()` does)
   - **And** handles AdapterError gracefully
   - **And** handles unexpected exceptions with generic error message

7. **AC7: Tests Pass with Good Coverage**
   - **Given** the economic_context tool implementation
   - **When** I run `pytest tests/test_server.py -v -k economic`
   - **Then** all economic_context tests pass
   - **And** tool is exercised for success, error, and edge cases

## Tasks / Subtasks

- [ ] Task 1: Add WorldBankAdapter initialization to server.py (AC: #1, #2)
  - [ ] 1.1: Add `from ignifer.adapters import WorldBankAdapter` import
  - [ ] 1.2: Create `_worldbank: WorldBankAdapter | None = None` global
  - [ ] 1.3: Create `_get_worldbank() -> WorldBankAdapter` lazy initializer
  - [ ] 1.4: Wire WorldBankAdapter to use shared CacheManager via `_get_cache()`

- [ ] Task 2: Implement `economic_context` tool (AC: #1, #2, #3)
  - [ ] 2.1: Add `@mcp.tool()` decorated `async def economic_context(country: str) -> str`
  - [ ] 2.2: Add comprehensive docstring with usage examples
  - [ ] 2.3: Call WorldBankAdapter.query() with QueryParams constructed from country
  - [ ] 2.4: Handle successful result - format output

- [ ] Task 3: Create economic output formatting (AC: #3)
  - [ ] 3.1: Create `_format_economic_result()` helper function in server.py
  - [ ] 3.2: Format indicator values with proper units (USD, %, millions)
  - [ ] 3.3: Include year of measurement for each indicator
  - [ ] 3.4: Add source attribution footer
  - [ ] 3.5: Use TSUKUYOMI-style formatting consistent with `briefing()`

- [ ] Task 4: Implement error handling (AC: #4, #6)
  - [ ] 4.1: Handle NO_DATA status with country suggestions
  - [ ] 4.2: Handle RATE_LIMITED status with retry suggestion
  - [ ] 4.3: Catch AdapterTimeoutError → friendly timeout message
  - [ ] 4.4: Catch AdapterError → friendly error message
  - [ ] 4.5: Catch Exception → generic error (log full exception)

- [ ] Task 5: Create tests (AC: #7)
  - [ ] 5.1: Create `tests/test_server_economic.py` or add to existing test_server.py
  - [ ] 5.2: Test successful economic context query
  - [ ] 5.3: Test invalid country name handling
  - [ ] 5.4: Test timeout error handling
  - [ ] 5.5: Test country alias resolution (mock adapter response)

- [ ] Task 6: Verify integration (AC: #5)
  - [ ] 6.1: Run `make lint` - passes
  - [ ] 6.2: Run `make type-check` - passes
  - [ ] 6.3: Run `pytest tests/` - all pass
  - [ ] 6.4: Manual test via Claude Desktop (optional smoke test)

## Dev Notes

### CRITICAL: Architecture Compliance

**FROM project-context.md:**

1. **Adapter-owned httpx clients** - WorldBankAdapter already handles this
2. **Layer rule** - server.py imports from adapters, NOT vice versa
3. **stdlib `logging` only** - use `logging.getLogger(__name__)`
4. **ISO 8601 + timezone** for all datetime
5. **snake_case** for all JSON fields
6. **Hybrid error handling** - exceptions for unexpected, Result type for expected

### Implementation Pattern from server.py

Follow the existing pattern for adapter initialization:

```python
# Global instances (initialized on first use)
_worldbank: WorldBankAdapter | None = None

def _get_worldbank() -> WorldBankAdapter:
    global _worldbank
    if _worldbank is None:
        _worldbank = WorldBankAdapter(cache=_get_cache())
    return _worldbank
```

### Tool Docstring Pattern

Match the `briefing()` docstring style for MCP tool discovery:

```python
@mcp.tool()
async def economic_context(country: str) -> str:
    """Get economic indicators for any country.

    Returns key economic data including GDP, inflation, unemployment,
    and trade balance from World Bank official statistics.

    Args:
        country: Country name (e.g., "Germany", "Japan") or ISO code (e.g., "DEU", "JPN")

    Returns:
        Formatted economic summary with source attribution.
    """
```

### Output Format Specification

Economic context output should follow a clean format:

```
═══════════════════════════════════════════════════════
              ECONOMIC CONTEXT
═══════════════════════════════════════════════════════
COUNTRY: United States

KEY INDICATORS (2023):
  GDP:              $25.46 trillion
  GDP per Capita:   $76,330
  Inflation:        4.1%
  Unemployment:     3.6%
  Trade Balance:    -$948.1 billion
  Population:       334.9 million

───────────────────────────────────────────────────────
Source: World Bank Open Data
Retrieved: 2026-01-09 12:34 UTC
═══════════════════════════════════════════════════════
```

### WorldBankAdapter Query Pattern

The WorldBankAdapter from Story 2-1 expects queries like:
- `QueryParams(query="GDP United States")` - single indicator
- The adapter parses the query to extract indicator + country

For economic_context, we need to query multiple indicators. Options:
1. Make multiple calls with different indicators (GDP, inflation, etc.)
2. Modify WorldBankAdapter to support a "summary" query mode

**Recommended approach:** Multiple sequential calls with different indicators:
```python
indicators = ["GDP", "inflation", "unemployment", "population"]
results = []
for indicator in indicators:
    params = QueryParams(query=f"{indicator} {country}")
    result = await adapter.query(params)
    if result.status == ResultStatus.SUCCESS:
        results.extend(result.results)
```

This works with the existing WorldBankAdapter without modifications.

### Error Message Templates

```python
# Timeout
f"## Request Timed Out\n\n"
f"Economic data request for **{country}** timed out.\n\n"
f"**Suggestions:**\n"
f"- Try again in a moment\n"
f"- Check your network connection"

# Invalid country
f"## Country Not Found\n\n"
f"Could not find economic data for **{country}**.\n\n"
f"**Suggestions:**\n"
f"- Check the spelling of the country name\n"
f"- Try using the ISO country code (e.g., 'DEU' for Germany)\n"
f"- Try common aliases (e.g., 'USA' instead of 'United States of America')"

# Rate limited
f"## Service Temporarily Unavailable\n\n"
f"World Bank API is rate limiting requests.\n\n"
f"**Suggestions:**\n"
f"- Wait a few minutes before trying again\n"
f"- Results may be cached - try your last query again"
```

### Test Fixture Reuse

Reuse `tests/fixtures/worldbank_response.json` from Story 2-1 for mocking.

### Dependencies

- **Requires:** Story 2.1 (WorldBankAdapter) - COMPLETED ✅
- **Blocked by:** None
- **Enables:** Multi-source correlation in Epic 7

### Previous Story Intelligence

From Story 2-1 code review:
- WorldBankAdapter is fully implemented and tested (18 tests, 96% coverage)
- COUNTRY_ALIASES includes USA, UK, Germany, Japan, France, India, Brazil, Russia, EU, Sub-Saharan Africa
- INDICATOR_CODES includes: gdp, gdp per capita, inflation, population, trade, trade balance, unemployment
- Caching works with 24-hour TTL via settings.ttl_worldbank
- Error handling follows contract: AdapterTimeoutError, AdapterParseError, RATE_LIMITED, NO_DATA
