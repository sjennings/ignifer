---
project_name: 'ignifer'
user_name: 'Scott'
date: '2026-01-08'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'code_quality', 'workflow_rules', 'critical_rules']
party_mode_reviewed: true
status: 'complete'
rule_count: 35
optimized_for_llm: true
---

# Project Context for AI Agents

_Critical rules and patterns for implementing Ignifer - a Python MCP server aggregating 7 OSINT data sources._

---

## TL;DR - Absolute Must-Knows

1. **snake_case** for all JSON fields - no exceptions
2. **`datetime.now(timezone.utc)`** - never naive datetime
3. **Adapter-owned httpx clients** - never shared across adapters
4. **Stop entity resolution at first successful match** - don't over-resolve
5. **stdlib `logging` only** - no loguru, no structlog
6. **`{Source}Adapter` naming** - e.g., `GDELTAdapter`, `OpenSkyAdapter`
7. **Hybrid error handling** - exceptions for unexpected, Result type for expected
8. **ISO 8601 + timezone** for all datetime serialization
9. **First thing to check:** `adapters/base.py` for Protocol and error contract
10. **Layer rule:** Adapters MUST NOT import from server.py or tools

---

## Technology Stack & Versions

**Runtime:**
- Python >=3.10 (required for modern async patterns)

**Core Dependencies:**
- fastmcp >=2.14,<3 (MCP server framework)
- httpx >=0.28 (async HTTP client)
- pydantic >=2.12 (data validation)
- tenacity >=9.1 (retry/backoff)
- websockets >=12.0 (AISStream)

**Build & Dev Tools:**
- Build backend: hatchling
- Package manager: uv (preferred) or pip
- Linting/formatting: ruff
- Type checking: mypy (strict mode)
- Testing: pytest + pytest-asyncio + pytest-httpx

---

## Critical Implementation Rules

### Python Language Rules

- **Always use timezone-aware datetime:**
  ```python
  # CORRECT
  from datetime import datetime, timezone
  timestamp = datetime.now(timezone.utc)

  # WRONG - naive datetime
  timestamp = datetime.now()
  timestamp = datetime.utcnow()  # deprecated
  ```

- **Use `typing.Protocol` with `@runtime_checkable` for interfaces**

- **Pure async execution** - no sync wrappers, no `asyncio.run()` inside async context

- **Type hints required** on all public functions and methods

- **Import from package root preferred:**
  ```python
  # CORRECT
  from ignifer.models import OSINTResult

  # AVOID in most cases
  from .models import OSINTResult
  ```

### Pydantic Rules

- **Use ConfigDict for model configuration:**
  ```python
  from pydantic import BaseModel, ConfigDict

  class OSINTResult(BaseModel):
      model_config = ConfigDict(
          str_strip_whitespace=True,
          validate_assignment=True,
      )
  ```

- **JSON fields: snake_case always**
  ```python
  # CORRECT
  source_name: str
  confidence_level: ConfidenceLevel
  retrieved_at: datetime

  # WRONG - no camelCase
  sourceName: str
  ```

- **Datetime serialization: ISO 8601 with timezone**
  - Format: `YYYY-MM-DDTHH:MM:SS+00:00`

### FastMCP & Adapter Rules

- **Adapter-owned httpx clients** - each adapter creates and manages its own client
- **Never share httpx clients across adapters**
- **MCP stdio constraint** - no persistent WebSocket connections; use connection-on-demand
- **Adapter registration pattern:**
  ```python
  # server.py
  adapters: dict[str, OSINTAdapter] = {
      'gdelt': GDELTAdapter(),
      'opensky': OpenSkyAdapter(),
  }
  ```

- **Layer boundary rule:** Adapters MUST NOT import from server.py or tools. Data flows DOWN only.

### Error Handling Contract

| Scenario | Handling | Type |
|----------|----------|------|
| Network timeout | `AdapterTimeoutError` | Exception |
| Rate limited | `OSINTResult(status=RateLimited)` | Result type |
| No data found | `OSINTResult(status=NoData)` | Result type |
| Malformed response | `AdapterParseError` | Exception |
| Auth failure | `AdapterAuthError` | Exception |

**Rule:** Exceptions for unexpected failures; Result type for expected operational states.

### Entity Resolution Rules

- **Tiered resolution:** Exact → Normalized → Wikidata → Fuzzy
- **STOP at first successful tier** - do not proceed if earlier tier matches
- **Log which tier matched** via `resolution_tier` field

### Confidence Scoring

- **Adapter-level ownership** - each adapter assigns confidence based on source reliability
- **Aggregator may adjust** based on corroboration across sources

### Output Modes

```python
class OutputMode(Enum):
    BRIEFING = 'briefing'  # Summary only
    RIGOR = 'rigor'        # Full attribution + raw data
```

### Cache Rules

- **Key format:** `{adapter}:{query_type}:{params_hash}`
- **Include query type** in cache key to prevent collisions between different query types to same adapter
- **Parameter order independence** via sorted JSON + SHA256 hash
- **TTL defaults:**
  | Source | TTL |
  |--------|-----|
  | OpenSky | 5 min |
  | AISStream | 15 min |
  | GDELT | 1 hour |
  | ACLED | 12 hours |
  | World Bank, OpenSanctions | 24 hours |
  | Wikidata | 7 days |

### Logging Rules

- **stdlib only:** `logging.getLogger(__name__)`
- **No loguru, no structlog**
- **Levels:** DEBUG (verbose), INFO (operations), WARNING (recoverable), ERROR (failures)

---

## Testing Rules

### Configuration Required

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### Test Organization

- **File pattern:** `test_{module_name}.py`
- **Location:** `tests/{package}/test_{module}.py`
- **Function naming:** `test_{action}_{scenario}_{expected}`
  - `test_query_valid_params_returns_result`
  - `test_query_timeout_raises_adapter_error`

### Mock Pattern

```python
import re
import pytest

@pytest.fixture
def mock_gdelt_response(httpx_mock):
    httpx_mock.add_response(
        url=re.compile(r'.*gdeltproject.*'),
        json=load_fixture('gdelt_response.json')
    )
```

### Required Fixtures

- `tests/fixtures/cache_scenarios.py`
- `tests/fixtures/error_scenarios.py`
- `tests/fixtures/{source}_response.json` for each adapter

---

## Anti-Patterns (NEVER DO)

```python
# WRONG: Shared client
_shared_client = httpx.AsyncClient()

# WRONG: New client per request (defeats connection pooling)
async def query(self, params):
    async with httpx.AsyncClient() as client:  # NO!
        return await client.get(...)

# WRONG: camelCase JSON
eventId: str

# WRONG: loguru
from loguru import logger

# WRONG: Naive datetime
datetime.now()

# WRONG: Adapter naming
class GDELT:        # Should be GDELTAdapter
class GDELTClient:  # Should be GDELTAdapter

# WRONG: Running all entity resolution tiers
# Always stop at first successful match

# WRONG: Adapter importing from server
from ignifer.server import ...  # NO! Layer violation

# WRONG: Hardcoding reference data from APIs
COUNTRY_CODES = {"usa": "USA", "germany": "DEU"}  # NO! Incomplete
# Instead: Fetch dynamically from API and cache in memory
```

### External API Reference Data

When an API provides reference data (country lists, indicator codes, etc.), **fetch dynamically and cache** rather than hardcoding:

```python
# CORRECT: Dynamic lookup with in-memory cache
class WorldBankAdapter:
    def __init__(self):
        self._country_lookup: dict[str, str] | None = None

    async def _ensure_country_lookup(self) -> dict[str, str]:
        if self._country_lookup is not None:
            return self._country_lookup
        # Fetch from API: /v2/country?format=json&per_page=400
        # Build lookup mapping names and codes
        self._country_lookup = lookup
        return lookup
```

**World Bank API endpoints:**
- Countries: `https://api.worldbank.org/v2/country?format=json&per_page=400`
- Indicators: `https://api.worldbank.org/v2/indicator/{code}/country/{iso3}?format=json`

---

## Project Structure (MVP)

```
src/ignifer/
├── __init__.py, __main__.py, server.py, config.py
├── models.py, cache.py, output.py
└── adapters/
    ├── __init__.py, base.py
    └── gdelt.py (first adapter)
```

**When to split:** >300 lines or clear domain separation

---

## Quick Reference

| Pattern | Value |
|---------|-------|
| JSON fields | `snake_case` |
| Datetime | ISO 8601 + TZ |
| Logging | stdlib only |
| Clients | Adapter-owned |
| Errors | Hybrid (exception + Result) |
| Entity match | Stop at first success |
| Test naming | `test_{action}_{scenario}_{expected}` |
| Adapter naming | `{Source}Adapter` |

---

## First Thing to Check

Before implementing any adapter, **read `adapters/base.py`** for:
- `OSINTAdapter` Protocol definition
- Error class hierarchy (`AdapterError`, `AdapterTimeoutError`, etc.)
- `ResultStatus` enum for expected operational states

When implementing features, reference PRD FR numbers in code comments for complex logic.

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code
- Follow ALL rules exactly as documented
- When in doubt, prefer the more restrictive option
- Reference `adapters/base.py` for Protocol definition

**For Humans:**
- Keep this file lean and focused on agent needs
- Update when technology stack changes
- Review quarterly for outdated rules
- Remove rules that become obvious over time

---

_Last Updated: 2026-01-08_
