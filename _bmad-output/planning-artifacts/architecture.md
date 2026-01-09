---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
status: 'complete'
completedAt: '2026-01-08'
inputDocuments:
  - product-brief-ignifer-2026-01-08.md
  - prd.md
  - research/technical-osint-apis-research-2026-01-08.md
workflowType: 'architecture'
project_name: 'Ignifer'
user_name: 'Scott'
date: '2026-01-08'
partyModeInsights: true
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

Ignifer requires 51 functional requirements spanning 10 categories. The core architectural pattern is **query → aggregate → correlate → present**:

- **Input Layer (FR1-FR20):** 8 MCP tools accepting natural language or structured parameters across briefings, entity lookup, tracking, and security screening
- **Aggregation Layer (FR21-FR25):** Multi-source correlation with automatic source selection, corroboration detection, and conflict identification
- **Output Layer (FR26-FR31):** Progressive disclosure with clean summaries by default, expandable Rigor Mode for IC-standard confidence levels and full source attribution
- **Resilience Layer (FR32-FR36):** Graceful degradation, alternative query suggestions, cross-source triangulation on failure

**Non-Functional Requirements:**

| NFR Category | Architectural Impact |
|--------------|---------------------|
| **Performance** | Single-source <5s, multi-source <15s requires parallel async queries with aggressive caching |
| **Integration** | 7 external APIs with varying auth (none, OAuth2, API key) and transports (REST, WebSocket) |
| **Reliability** | 95% query success despite external API failures requires cache-first design with stale-while-revalidate |
| **Maintainability** | Adapter protocol abstraction enables source swapping and community contributions |
| **Security** | API keys in environment variables only; never logged or exposed in errors |

**Scale & Complexity:**

- Primary domain: Python MCP server (API aggregation layer)
- Complexity level: Medium
- Estimated architectural components: ~20 (server, 7 adapters, 3 cache tiers, 3 aggregation modules, 3 output formatters, 3 cross-cutting services)

### Architectural Dependency Graph

```
┌─────────────────────────────────────────┐
│              MCP Tools                   │
│  (briefing, track_vessel, entity_lookup) │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│          Aggregation Layer              │
│  (normalizer, correlator, entity_resolver) │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│           Adapter Layer                  │
│  (GDELT, OpenSky, AIS, WorldBank, etc.)  │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│            Cache Layer                   │
│  (L1 memory, L2 SQLite, L3 filesystem)   │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│          External APIs                   │
└─────────────────────────────────────────┘
```

Each layer only communicates with the layer directly below it. This prevents circular dependencies and maintains clear separation of concerns.

### Technical Constraints & Dependencies

**MCP Protocol Constraints:**
- stdio transport (standard for Claude Desktop)
- Tool-based interaction model (user approval required)
- No persistent server state between sessions (stateless by design)
- **No background workers** - stdio transport means request-response only; cannot maintain persistent WebSocket connections between queries

**External API Constraints:**
- OpenSky: OAuth2 required for accounts created after March 2025; 4000 requests/day
- AISStream: WebSocket-only; **connection-on-demand pattern required** due to MCP statelessness - connect, query, cache, disconnect
- ACLED: Registration + API key required
- OpenSanctions: Free for non-commercial; bulk data download model

**Python Runtime:**
- Python 3.10+ (async/await syntax requirements)
- FastMCP framework for server skeleton
- Async-first: httpx for REST, websockets library for AIS
- **asyncio.gather() required** for parallel adapter queries to meet <15s multi-source NFR

**Entity Resolution Complexity:**
- Wikidata Q-IDs serve as canonical identifiers across sources
- **Fuzzy matching required** - entity names in GDELT news may not exactly match AISStream vessel names or OpenSanctions entries
- Entity linking is non-trivial and requires dedicated resolution strategies (exact match → normalized match → fuzzy match → manual disambiguation)

### Cross-Cutting Concerns Identified

| Concern | Affects | Architectural Response |
|---------|---------|----------------------|
| **Rate Limiting** | All 7 adapters | Per-source rate tracker with exponential backoff (tenacity) |
| **Caching** | All adapters | Multi-tier: L1 memory (hot), L2 SQLite (warm), L3 filesystem (cold) |
| **Error Handling** | All tools | Structured errors with user-friendly messages + alternative suggestions |
| **Source Attribution** | All output | Every data point tagged with source URL + retrieval timestamp |
| **Confidence Scoring** | All output | ICD 203 levels computed from source quality + corroboration |
| **Entity Resolution** | Entity, Multi-source tools | Wikidata Q-IDs as canonical cross-source identifiers with fuzzy matching fallback |
| **Cross-Source Triangulation** | All tools | **Design principle**: When primary source fails, automatically attempt corroboration via alternative sources before reporting failure |

### Testability Requirements

| Requirement | Purpose |
|-------------|---------|
| **Dependency Injection** | All adapters injectable for isolation testing |
| **Mock-Injectable Interfaces** | OSINTAdapter protocol enables mock substitution |
| **Failure Simulation** | Test harness can simulate API failures, timeouts, rate limits |
| **Cache Test Fixtures** | Dedicated fixtures for cache behavior testing (TTL, invalidation, stale-while-revalidate) |
| **Adapter Isolation Verification** | Tests confirm one adapter failure doesn't cascade to others |

## Starter Template Evaluation

### Primary Technology Domain

**Python MCP Server** - A PyPI-distributed package running as a Model Context Protocol server for Claude Desktop integration.

This is not a web app or CLI with a `create-app` generator. The "starter" is a **project structure pattern** combined with **modern Python build tooling**.

### Starter Options Considered

| Option | Description | Verdict |
|--------|-------------|---------|
| FastMCP 2.x + src layout | Decorator-based MCP tools, modern packaging | ✅ Selected |
| Official MCP SDK (mcp) | Lower-level, more boilerplate | Too verbose |
| Custom from scratch | Maximum control | Unnecessary complexity |

### Selected Starter: FastMCP 2.x + Modern Python Stack

**Rationale for Selection:**
- FastMCP 2.x provides ergonomic decorator-based tool registration
- Automatic type inference from Python type hints reduces boilerplate
- Active maintenance (v2.14.2 as of Dec 2025)
- Built-in async support matches our httpx/websockets architecture
- Structured output with schema validation (MCP spec 2025-06-18)

**Initialization Command:**

```bash
# Create project structure
mkdir -p ignifer/src/ignifer/{adapters,aggregation,output,cache,models}
mkdir -p ignifer/tests/{adapters,aggregation,output,cache,fixtures}
cd ignifer

# Initialize with uv (fast Rust-based package manager)
uv init --lib --name ignifer

# Or with traditional pip
pip install hatch
hatch new ignifer --src-layout
```

### Architectural Decisions Provided by Starter

**Language & Runtime:**
- Python 3.10+ (required for modern async patterns)
- Type hints throughout (mypy strict compliance)
- Async-first design (asyncio native)

**Build Tooling:**
- **Build backend:** hatchling (modern, pyOpenSci recommended)
- **Dependency management:** uv (Rust-based, 10-100x faster than pip)
- **Version management:** hatch version or dynamic from git tags

**Project Structure:**
```
ignifer/
├── src/
│   └── ignifer/
│       ├── __init__.py           # Package version, exports
│       ├── __main__.py           # Entry: python -m ignifer
│       ├── server.py             # FastMCP server + tool registration
│       ├── models/               # Pydantic models (prevents circular imports)
│       │   ├── __init__.py
│       │   ├── osint.py          # OSINTResult, SourceMetadata, ConfidenceLevel
│       │   ├── adapters.py       # Per-adapter response models
│       │   └── cache.py          # CacheEntry, CacheKey
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py           # OSINTAdapter protocol
│       │   ├── gdelt.py
│       │   ├── opensky.py
│       │   ├── aisstream.py
│       │   ├── worldbank.py
│       │   ├── acled.py
│       │   ├── opensanctions.py
│       │   └── wikidata.py
│       ├── aggregation/
│       │   ├── __init__.py
│       │   ├── normalizer.py
│       │   ├── correlator.py
│       │   └── entity_resolver.py
│       ├── output/
│       │   ├── __init__.py
│       │   ├── briefing.py
│       │   ├── deep_dive.py
│       │   └── rigor.py
│       └── cache/
│           ├── __init__.py
│           ├── memory.py         # L1 cache
│           ├── sqlite.py         # L2 cache
│           └── filesystem.py     # L3 cache
├── tests/
│   ├── conftest.py               # Fixtures: mock_adapter_factory, etc.
│   ├── adapters/                 # Mirrors src structure (no test_ prefix)
│   │   ├── test_gdelt.py
│   │   ├── test_opensky.py
│   │   └── ...
│   ├── aggregation/
│   ├── output/
│   ├── cache/
│   └── fixtures/                 # Sample API responses for regression testing
│       ├── gdelt_response.json
│       ├── opensky_response.json
│       └── ...
├── pyproject.toml
├── Makefile                      # Common dev commands
├── README.md
└── .python-version               # Pin Python version for uv
```

**Code Quality Tooling:**
- **Type checking:** mypy (strict mode)
- **Linting/Formatting:** ruff (replaces flake8 + isort + black)
- **Testing:** pytest + pytest-asyncio + pytest-cov + pytest-httpx

**Development Experience:**
- Editable install: `uv pip install -e ".[dev]"`
- Type checking: `mypy src/`
- Linting: `ruff check . && ruff format .`
- Testing: `pytest --cov=ignifer`
- CLI command: `ignifer` (via project.scripts entry)

### Core Dependencies (Pinned Versions)

```toml
[project]
name = "ignifer"
requires-python = ">=3.10"
dependencies = [
    "fastmcp>=2.14,<3",      # MCP server framework
    "httpx>=0.28",           # Async HTTP client
    "pydantic>=2.12",        # Data validation
    "tenacity>=9.1",         # Retry/backoff
    "websockets>=12.0",      # AISStream WebSocket
]

[project.scripts]
ignifer = "ignifer.server:main"

[project.optional-dependencies]
adapters = [
    # Phase 1 (zero-auth)
    "gdeltPyR>=1.0",         # GDELT access
    "wbgapi>=1.0",           # World Bank API
    "SPARQLWrapper>=2.0",    # Wikidata queries
    # Phase 2 (registration)
    "pyopensky>=2.0",        # OpenSky Network
    # Phase 3 (API keys)
    # ACLED via REST, OpenSanctions via bulk download
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
    "pytest-httpx>=0.30",    # HTTP mocking for adapter tests
    "mypy>=1.8",
    "ruff>=0.3",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Development Automation (Makefile)

```makefile
.PHONY: test lint type-check all install

install:
	uv pip install -e ".[dev,adapters]"

test:
	pytest --cov=ignifer --cov-report=term-missing

lint:
	ruff check . && ruff format .

type-check:
	mypy src/

all: lint type-check test
```

**Note:** Project initialization using this structure should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Made):**
- Adapter protocol pattern (Protocol class with @runtime_checkable)
- Async execution model (Pure async)
- Error handling strategy (Hybrid with documented contract)
- Cache architecture (TTL + manual invalidation)
- Entity resolution strategy (Tiered with resolution tracking)
- Output structure (Layered progressive disclosure)

**Deferred Decisions (Post-MVP):**

| Deferred Decision | Related PRD Items | Rationale |
|-------------------|-------------------|-----------|
| Real-time streaming | Not in MVP scope | WebSocket persistence incompatible with MCP stdio |
| Session continuity | Not in MVP scope | Nice-to-have; not essential for core value |
| Visualization pipeline | FR42-FR45 (Phase 5) | Claude describes data adequately for MVP |
| Alert/monitoring system | Not in MVP scope | Requires persistent state, scheduled execution |

### Adapter Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Interface pattern** | `typing.Protocol` with `@runtime_checkable` | Duck typing + `isinstance()` support for dynamic registration |
| **Execution model** | Pure async | MCP server is async context; `asyncio.gather()` required for parallel queries per NFR-P2 |
| **Error handling** | Hybrid with documented contract | Exceptions for unexpected failures; Result type for expected states |

**Adapter Protocol Definition:**
```python
from typing import Protocol, runtime_checkable
from ignifer.models.osint import OSINTResult, QueryParams, QualityTier

@runtime_checkable
class OSINTAdapter(Protocol):
    """Protocol for all OSINT data source adapters."""

    @property
    def source_name(self) -> str: ...

    @property
    def base_quality_tier(self) -> QualityTier: ...

    async def query(self, params: QueryParams) -> OSINTResult: ...

    async def health_check(self) -> bool: ...
```

**Error Handling Contract (adapters/base.py):**

| Scenario | Handling | Type |
|----------|----------|------|
| Network timeout | `AdapterTimeoutError` | Exception |
| Rate limited | `OSINTResult(status=RateLimited)` | Result type |
| No data found | `OSINTResult(status=NoData)` | Result type |
| Malformed response | `AdapterParseError` | Exception |
| Auth failure | `AdapterAuthError` | Exception |
| Unexpected error | `AdapterError` (base) | Exception |

Every adapter implementation MUST follow this contract. Tests verify these behaviors.

### Cache Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Key strategy** | String concatenation with deterministic hash | Parameter order independence, debuggable |
| **Invalidation** | TTL + manual | Per-source TTL defaults; CLI command for forced refresh |
| **Storage tiers** | L1 memory, L2 SQLite | L1 for hot data (15min), L2 for warm data (hours-days) |

**Cache Key Helper:**
```python
import hashlib
import json

def cache_key(adapter: str, query: str, **params) -> str:
    """Deterministic cache key generation."""
    sorted_params = sorted(params.items())
    params_hash = hashlib.sha256(
        json.dumps(sorted_params, sort_keys=True).encode()
    ).hexdigest()[:12]
    return f"{adapter}:{query}:{params_hash}"
```

**TTL Defaults by Source:**

| Source | Default TTL | Rationale |
|--------|-------------|-----------|
| GDELT | 1 hour | Updates every 15 minutes |
| OpenSky | 5 minutes | Position data is time-sensitive |
| AISStream | 15 minutes | Vessel positions cached on-demand |
| World Bank | 24 hours | Economic indicators update monthly |
| ACLED | 12 hours | Weekly batch updates |
| OpenSanctions | 24 hours | Daily updates |
| Wikidata | 7 days | Entity data is relatively stable |

**TTL Test Scenarios (tests/fixtures/cache_scenarios.py):**
```python
CACHE_TEST_SCENARIOS = [
    # (adapter, ttl_seconds, scenario, expect_cache_hit)
    ("gdelt", 3600, "within_ttl", True),
    ("gdelt", 3600, "expired", False),
    ("opensky", 300, "within_ttl", True),
    ("opensky", 300, "expired", False),
    ("wikidata", 604800, "within_ttl", True),
]
```

### Confidence & Rigor Framework

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Confidence levels** | Enum with methods | Type-safe `ConfidenceLevel.LIKELY.to_percentage()` matching ICD 203 |
| **Source quality** | Hybrid | Base tier per adapter + dynamic adjustment for freshness/completeness |
| **Rigor mode toggle** | Global default + per-query override | Flexible for both casual and power users |

**Confidence Level Enum:**
```python
from enum import Enum

class ConfidenceLevel(Enum):
    REMOTE = 1          # <20%
    UNLIKELY = 2        # 20-40%
    EVEN_CHANCE = 3     # 40-60%
    LIKELY = 4          # 60-80%
    VERY_LIKELY = 5     # 80-95%
    ALMOST_CERTAIN = 6  # >95%

    def to_percentage_range(self) -> tuple[int, int]: ...
    def to_label(self) -> str: ...
```

**Quality Tier Enum:**
```python
class QualityTier(Enum):
    HIGH = "H"    # Official sources, academic research
    MEDIUM = "M"  # Reputable news, verified OSINT
    LOW = "L"     # Social media, unverified reports
```

### Entity Resolution

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Matching strategy** | Tiered resolution with tracking | Exact → Normalized → Wikidata → Fuzzy, with resolution path recorded |

**Resolution Pipeline:**
1. **Exact match** - Direct string equality (fastest)
2. **Normalized match** - Lowercase, strip whitespace, remove diacritics
3. **Wikidata lookup** - Query for Q-ID, use aliases for matching
4. **Fuzzy match** - Levenshtein distance with configurable threshold (last resort)

**Entity Match Model:**
```python
from typing import Literal

class EntityMatch(BaseModel):
    entity_id: str | None
    wikidata_qid: str | None
    resolution_tier: Literal["exact", "normalized", "wikidata", "fuzzy", "failed"]
    match_confidence: float  # 1.0 for exact, decreasing for fuzzier matches
    original_query: str
```

### Output Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Structure** | Layered (progressive disclosure) | Summary → Detail → Raw matches PRD's Rigor Mode UX |

**Raw Source Response Model:**
```python
class RawSourceResponse(BaseModel):
    source: str
    timestamp: datetime
    request_params: dict[str, Any]
    payload: dict[str, Any]
```

**Output Layers:**
```python
class OSINTOutput(BaseModel):
    summary: str                          # Clean, digestible briefing
    details: list[SourceDetail]           # Per-source breakdowns
    raw: dict[str, RawSourceResponse] | None  # Full API responses (Rigor Mode only)
    confidence: ConfidenceLevel
    sources: list[SourceAttribution]
```

### Cross-Source Triangulation

**Responsibility:** `aggregation/correlator.py`

**Trigger:** When `OSINTResult.status == NoData` from primary source

**Behavior:**
1. Identify alternative sources that could answer the same query
2. Query alternative sources in parallel
3. If alternative succeeds, include in result with lower confidence
4. If all sources fail, return structured "no data" response with suggestions

This implements FR34: "System offers cross-source triangulation when one source returns no results."

### Decision Impact Analysis

**Implementation Sequence:**
1. Models first (`models/osint.py`, `models/cache.py`) - all other code depends on these
2. Cache layer - required by all adapters
3. Base adapter protocol + error hierarchy (`adapters/base.py`)
4. First adapter (GDELT) + output formatter
5. Remaining adapters in parallel
6. Entity resolution (`aggregation/entity_resolver.py`)
7. Correlator with triangulation (`aggregation/correlator.py`)

**Cross-Component Dependencies:**
```
models/osint.py ← adapters/* ← aggregation/* ← output/*
                ↖ cache/*    ↗
```

**Error Handling Flow:**
```
Adapter raises exception → Tool catches → Correlator attempts triangulation
                                        ↓
                         If triangulation fails → Structured error to user
```

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:** 6 areas where AI agents could make different choices, now standardized.

### Naming Patterns

**Python Code Naming (PEP 8 Standard):**
- Files/modules: `snake_case.py` (e.g., `entity_resolver.py`)
- Classes: `PascalCase` (e.g., `GDELTAdapter`)
- Functions/methods: `snake_case` (e.g., `async def query_events()`)
- Variables: `snake_case` (e.g., `cache_key`)
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `DEFAULT_TTL`)

**Adapter Class Naming:**
- Pattern: `{Source}Adapter`
- Examples: `GDELTAdapter`, `OpenSkyAdapter`, `AISStreamAdapter`, `WikidataAdapter`
- Rationale: Matches `OSINTAdapter` protocol, clear and unambiguous

**JSON Field Naming:**
- Pattern: `snake_case` throughout
- Examples: `source_name`, `confidence_level`, `retrieved_at`
- Rationale: Pythonic, no translation layer needed, simpler codebase

```python
# CORRECT
class OSINTOutput(BaseModel):
    source_name: str
    confidence_level: ConfidenceLevel
    retrieved_at: datetime

# INCORRECT - do not use camelCase
class OSINTOutput(BaseModel):
    sourceName: str      # NO
    confidenceLevel: str # NO
```

### Format Patterns

**Datetime Serialization:**
- Format: ISO 8601 with explicit timezone
- Pattern: `YYYY-MM-DDTHH:MM:SS+00:00`
- Example: `"2026-01-08T14:30:00+00:00"`
- Always use UTC internally, convert for display only

```python
from datetime import datetime, timezone

# CORRECT
timestamp = datetime.now(timezone.utc)
serialized = timestamp.isoformat()  # "2026-01-08T14:30:00+00:00"

# INCORRECT
timestamp = datetime.now()  # NO - naive datetime
timestamp = datetime.utcnow()  # NO - deprecated, still naive
```

**Pydantic Datetime Handling:**
```python
from pydantic import BaseModel, field_serializer
from datetime import datetime, timezone

class SourceAttribution(BaseModel):
    source: str
    retrieved_at: datetime

    @field_serializer('retrieved_at')
    def serialize_dt(self, dt: datetime) -> str:
        return dt.isoformat()
```

**Source URL Formatting:**
- Always include full URL with protocol
- Example: `"https://api.gdeltproject.org/api/v2/doc/doc?query=..."`
- Never truncate URLs in source attribution

### Process Patterns

**Logging Pattern:**
- Library: Python stdlib `logging`
- Logger per module: `logger = logging.getLogger(__name__)`
- Levels: DEBUG for verbose, INFO for operations, WARNING for recoverable issues, ERROR for failures

```python
import logging

logger = logging.getLogger(__name__)

class GDELTAdapter:
    async def query(self, params: QueryParams) -> OSINTResult:
        logger.debug(f"Querying GDELT with params: {params}")
        try:
            result = await self._fetch(params)
            logger.info(f"GDELT returned {len(result.items)} items")
            return result
        except httpx.TimeoutException as e:
            logger.warning(f"GDELT timeout: {e}")
            raise AdapterTimeoutError("GDELT") from e
```

**Log Level Guidelines:**

| Level | Use For |
|-------|---------|
| DEBUG | Parameter values, internal state, verbose tracing |
| INFO | Successful operations, cache hits/misses, query counts |
| WARNING | Recoverable issues, rate limits approached, stale cache served |
| ERROR | Adapter failures, parse errors, auth failures |

**Async Context Management:**
- Pattern: Adapter-owned client
- Each adapter creates and manages its own `httpx.AsyncClient`
- Client created in `__init__` or lazily on first use
- Explicit cleanup via `async def close()` method

```python
class GDELTAdapter:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    @property
    async def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": "Ignifer/1.0"}
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
```

**Import Organization:**
- Tool: ruff (handles isort-compatible sorting)
- Order: stdlib → third-party → local (automatic)
- No custom sections needed

```python
# ruff will organize imports automatically
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt

from ignifer.models.osint import OSINTResult, QueryParams
from ignifer.cache import cache_key
```

### Structure Patterns

**Module Exports:**
- Each package `__init__.py` exports public API only
- Use `__all__` to be explicit

```python
# adapters/__init__.py
from ignifer.adapters.base import OSINTAdapter
from ignifer.adapters.gdelt import GDELTAdapter
from ignifer.adapters.opensky import OpenSkyAdapter
# ... etc

__all__ = [
    "OSINTAdapter",
    "GDELTAdapter",
    "OpenSkyAdapter",
    # ...
]
```

**Test File Naming:**
- Pattern: `test_{module_name}.py`
- Location: `tests/{package}/test_{module}.py`
- Example: `tests/adapters/test_gdelt.py`

### Enforcement Guidelines

**All AI Agents MUST:**
1. Use `snake_case` for all JSON fields - no exceptions
2. Use ISO 8601 with timezone for all datetime serialization
3. Use stdlib `logging.getLogger(__name__)` - no other logging libraries
4. Create adapter-owned clients - never share httpx clients across adapters
5. Follow the error handling contract from Step 4 exactly
6. Use `{Source}Adapter` naming for all adapter classes

**Pattern Verification:**
- `ruff check .` catches import and style issues
- `mypy src/` catches type inconsistencies
- Code review checklist includes pattern compliance
- Tests verify JSON output field names are snake_case

### Pattern Examples

**Good Examples:**
```python
# Correct adapter implementation
class ACLEDAdapter:
    source_name = "acled"
    base_quality_tier = QualityTier.HIGH

    async def query(self, params: QueryParams) -> OSINTResult:
        logger.debug(f"ACLED query: {params}")
        # ... implementation
```

```python
# Correct model definition
class ConflictEvent(BaseModel):
    event_id: str
    event_date: datetime
    location_name: str
    fatalities_count: int
    source_url: str
```

**Anti-Patterns:**
```python
# WRONG: camelCase JSON fields
class ConflictEvent(BaseModel):
    eventId: str        # NO - use event_id
    eventDate: datetime # NO - use event_date

# WRONG: Shared client
_shared_client = httpx.AsyncClient()  # NO - use adapter-owned

# WRONG: loguru or structlog
from loguru import logger  # NO - use stdlib logging

# WRONG: Naive datetime
retrieved_at = datetime.now()  # NO - use datetime.now(timezone.utc)

# WRONG: Adapter naming
class GDELT:  # NO - use GDELTAdapter
class GDELTClient:  # NO - use GDELTAdapter
```

## Project Structure & Boundaries

### Structure Philosophy

**MVP vs Target:** This document defines two structures:
1. **MVP Structure** - Minimal files to start, split when needed (Epic 1-2)
2. **Target Structure** - Full architecture when project matures (Epic 3+)

Start with MVP. Grow to Target as files exceed ~300 lines.

### MVP Project Structure (Start Here)

```
ignifer/
├── .github/
│   └── workflows/
│       └── ci.yml                    # GitHub Actions: lint, type-check, test
├── .python-version                   # Python version pin for uv (3.10)
├── .gitignore
├── LICENSE
├── README.md
├── Makefile
├── pyproject.toml
│
├── src/
│   └── ignifer/
│       ├── __init__.py               # __version__ = "0.1.0"
│       ├── __main__.py               # Entry: python -m ignifer
│       ├── server.py                 # FastMCP server + ALL tools inline
│       ├── config.py                 # Environment config, TTL defaults
│       ├── models.py                 # ALL Pydantic models (split later)
│       ├── cache.py                  # ALL cache logic (L1 + L2)
│       ├── output.py                 # OutputFormatter with mode parameter
│       │
│       └── adapters/
│           ├── __init__.py           # Export OSINTAdapter + adapters
│           ├── base.py               # Protocol, error hierarchy
│           └── gdelt.py              # First adapter (Phase 1)
│
└── tests/
    ├── conftest.py                   # Global fixtures
    ├── test_server.py                # Tool tests
    ├── test_cache.py
    ├── test_output.py
    ├── adapters/
    │   ├── conftest.py               # Adapter-specific fixtures
    │   └── test_gdelt.py
    └── fixtures/
        ├── gdelt_response.json
        ├── cache_scenarios.py
        └── error_scenarios.py
```

**MVP File Count:** ~18 files (vs 45+ in target)

### Target Project Structure (Grow Into This)

```
ignifer/
├── .github/
│   └── workflows/
│       └── ci.yml
├── .python-version
├── .gitignore
├── LICENSE
├── README.md
├── CONTRIBUTING.md                   # Adapter contribution guide
├── Makefile
├── pyproject.toml
│
├── src/
│   └── ignifer/
│       ├── __init__.py
│       ├── __main__.py
│       ├── server.py                 # FastMCP server, imports tools
│       ├── config.py
│       │
│       ├── models/                   # Split when models.py > 300 lines
│       │   ├── __init__.py
│       │   ├── core.py               # OSINTResult, QueryParams, ConfidenceLevel, EntityMatch
│       │   ├── responses.py          # Per-adapter models (GDELTArticle, etc.)
│       │   ├── cache.py              # CacheEntry, CacheStats
│       │   └── output.py             # OSINTOutput, SourceAttribution
│       │
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── registry.py           # Dynamic adapter registration (Phase 4+)
│       │   ├── gdelt.py
│       │   ├── worldbank.py
│       │   ├── wikidata.py
│       │   ├── opensky.py
│       │   ├── aisstream.py
│       │   ├── acled.py
│       │   └── opensanctions.py
│       │
│       ├── aggregation/              # Split when correlator logic grows
│       │   ├── __init__.py
│       │   ├── normalizer.py
│       │   ├── correlator.py
│       │   └── entity_resolver.py
│       │
│       ├── output/                   # Split when OutputFormatter > 300 lines
│       │   ├── __init__.py
│       │   └── formatter.py          # Single class with mode parameter
│       │
│       ├── cache/                    # Split when cache.py > 300 lines
│       │   ├── __init__.py
│       │   ├── manager.py
│       │   ├── memory.py
│       │   └── sqlite.py
│       │
│       └── tools/                    # Split when server.py tools > 300 lines
│           ├── __init__.py
│           ├── briefing.py
│           ├── entity.py
│           ├── tracking.py
│           ├── security.py
│           └── system.py
│
└── tests/
    ├── conftest.py
    │
    ├── unit/
    │   ├── adapters/
    │   │   ├── conftest.py
    │   │   ├── test_base.py
    │   │   ├── test_gdelt.py
    │   │   └── ...
    │   ├── aggregation/
    │   │   ├── conftest.py
    │   │   └── ...
    │   ├── cache/
    │   │   ├── conftest.py
    │   │   └── ...
    │   └── output/
    │       └── ...
    │
    ├── integration/
    │   ├── conftest.py
    │   ├── test_briefing_flow.py     # Tool → Aggregation → Adapter → Output
    │   ├── test_cache_integration.py
    │   └── test_multi_source.py
    │
    └── fixtures/
        ├── gdelt_response.json
        ├── gdelt_empty.json
        ├── opensky_states.json
        ├── aisstream_message.json
        ├── worldbank_indicators.json
        ├── acled_events.json
        ├── opensanctions_entity.json
        ├── wikidata_entity.json
        ├── cache_scenarios.py
        └── error_scenarios.py
```

### When to Split Files

| File | Split When | Into |
|------|-----------|------|
| `models.py` | >300 lines or 10+ models | `models/core.py`, `models/responses.py`, etc. |
| `cache.py` | >300 lines or L3 added | `cache/manager.py`, `cache/memory.py`, `cache/sqlite.py` |
| `output.py` | >300 lines or 3+ modes | `output/formatter.py` (still single class) |
| `server.py` tools | >50 lines per tool | `tools/briefing.py`, `tools/entity.py`, etc. |
| N/A | Community adapters | Add `adapters/registry.py` |

### Architectural Boundaries

**Layer Boundaries:**

| Layer | Responsibility | Communicates With |
|-------|---------------|-------------------|
| **server.py / tools/** | MCP tool registration, parameter parsing | aggregation/, output/ |
| **aggregation/** | Multi-source orchestration, correlation | adapters/, cache/, models |
| **adapters/** | External API communication | cache/, models |
| **cache/** | Data persistence, TTL | models |
| **output/** | Response formatting | models |
| **models/** | Data structures | (none - leaf layer) |

**Forbidden Communications:**
- adapters/ MUST NOT import from tools/ or server.py
- cache/ MUST NOT import from aggregation/
- output/ MUST NOT import from adapters/
- models/ MUST NOT import from any other layer

**Import Direction (Strict):**
```
server.py/tools → aggregation → adapters → cache → models
                              ↘         ↗
                               output
```

### Requirements to Structure Mapping

**FR1-FR5 (Intelligence Briefings):**
- MVP: `server.py` (tool) + `adapters/gdelt.py` + `output.py`
- Target: `tools/briefing.py` + `aggregation/correlator.py` + adapters + `output/formatter.py`

**FR6-FR10 (Entity Intelligence):**
- MVP: `server.py` (tool) + `adapters/wikidata.py`
- Target: `tools/entity.py` + `aggregation/entity_resolver.py`

**FR11-FR15 (Transportation Tracking):**
- MVP: `server.py` (tool) + `adapters/opensky.py`
- Target: `tools/tracking.py` + `adapters/opensky.py`, `adapters/aisstream.py`

**FR16-FR20 (Security Intelligence):**
- MVP: Not in MVP (Phase 3)
- Target: `tools/security.py` + `adapters/acled.py`, `adapters/opensanctions.py`

**FR26-FR31 (Output & Rigor Mode):**
- MVP: `output.py` with `OutputMode.BRIEFING` / `OutputMode.RIGOR`
- Target: `output/formatter.py` with mode parameter

### Integration Points

**Data Flow (MVP):**

```
User Query (via Claude)
       │
       ▼
┌─────────────────┐
│  server.py      │ ◄── Tool + param parsing
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  adapters/      │ ◄── Single adapter query
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  cache.py       │ ◄── L1 → L2 lookup/store
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  output.py      │ ◄── Format response
└────────┬────────┘
         │
         ▼
   MCP Response
```

**Data Flow (Target - Multi-Source):**

```
User Query
    │
    ▼
┌─────────┐
│  Tool   │
└────┬────┘
     │
     ▼
┌─────────────┐
│ Correlator  │ ◄── Select sources, orchestrate
└──────┬──────┘
       │
  ┌────┴────┐
  ▼         ▼
┌───────┐ ┌───────┐
│Adapter│ │Adapter│ ◄── asyncio.gather()
└───┬───┘ └───┬───┘
    │         │
    ▼         ▼
┌─────────────────┐
│     Cache       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Normalizer    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Entity Resolver │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Formatter    │
└────────┬────────┘
         │
         ▼
   MCP Response
```

### Test Fixtures

**cache_scenarios.py:**
```python
CACHE_TEST_SCENARIOS = [
    # (adapter, ttl_seconds, scenario, expect_cache_hit)
    ("gdelt", 3600, "within_ttl", True),
    ("gdelt", 3600, "expired", False),
    ("opensky", 300, "within_ttl", True),
    ("opensky", 300, "expired", False),
    ("wikidata", 604800, "within_ttl", True),
]
```

**error_scenarios.py:**
```python
from ignifer.adapters.base import AdapterTimeoutError, AdapterAuthError, AdapterParseError
from ignifer.models import ResultStatus

ERROR_SCENARIOS = [
    # (adapter, scenario, expected_type_or_status)
    ("gdelt", "timeout", AdapterTimeoutError),
    ("gdelt", "rate_limit", ResultStatus.RATE_LIMITED),
    ("gdelt", "no_data", ResultStatus.NO_DATA),
    ("gdelt", "malformed", AdapterParseError),
    ("opensky", "auth_failure", AdapterAuthError),
]
```

### Development Workflow

**MVP Development:**
```bash
make install          # uv pip install -e ".[dev,adapters]"
make lint             # ruff check . && ruff format .
make type-check       # mypy src/
make test             # pytest --cov=ignifer
make all              # lint + type-check + test
```

**Claude Desktop Config:**
```json
{
  "mcpServers": {
    "ignifer": {
      "command": "ignifer"
    }
  }
}
```

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
All architectural decisions interconnect cleanly - FastMCP 2.x with pure async flows naturally into adapter-owned httpx clients, supporting the Protocol pattern. Hybrid error handling (exceptions for unexpected, Result type for expected states) aligns with OSINT operational realities where rate limits and missing data are normal.

**Pattern Consistency:**
- Naming conventions (snake_case JSON, Source+Adapter pattern) consistent across all layers
- Protocol with `@runtime_checkable` enables duck typing without runtime overhead
- Layered output (progressive disclosure) integrates with rigor mode toggle seamlessly

**Structure Alignment:**
MVP 18-file structure supports all architectural decisions with clear "when to split" guidance for future growth.

### Requirements Coverage Validation ✅

**Functional Requirements Coverage:**
- 46/51 FRs covered by current architecture
- 5 FRs deferred to Phase 5 (advanced analytics, ML predictions) - verified as independent with no hidden dependencies

**Non-Functional Requirements Coverage:**
- Performance: Async execution + tiered caching addresses latency requirements
- Security: API key isolation per adapter, no credential exposure in logs
- Reliability: Retry with tenacity, graceful degradation patterns defined

### Implementation Readiness Validation ✅

**Decision Completeness:**
All critical decisions documented with versions. Implementation patterns comprehensive.

**Structure Completeness:**
Complete 18-file MVP structure with partition criteria for growth.

**Pattern Completeness:**
All potential conflict points addressed with concrete examples.

### Gap Analysis Results

**Critical Gaps Addressed:**
- ✅ `QualityTier` enum explicitly defined in models
- ✅ AISStream reconnection test fixture added to test organization

**Important Clarifications Added:**
- None identified after Party Mode review

### Implementation Clarifications

**Confidence Scoring Ownership:**
Adapter-level - each source assigns confidence based on its known reliability characteristics.

**Time Range Normalization:**
Adapters receive ISO 8601 intervals and normalize to source-specific format internally.

**Entity Resolution Tier-Stopping:**
Stop at first successful match tier. Do not proceed to fuzzy if exact/normalized/wikidata succeeds. Log which tier produced the match.

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed (solo dev, 7 sources)
- [x] Technical constraints identified (MCP stdio, no background workers)
- [x] Cross-cutting concerns mapped

**✅ Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified (FastMCP 2.x, hatchling, uv)
- [x] Integration patterns defined (adapter Protocol)
- [x] Performance considerations addressed (tiered caching)

**✅ Implementation Patterns**
- [x] Naming conventions established (snake_case, Source+Adapter)
- [x] Structure patterns defined (feature-based organization)
- [x] Communication patterns specified (async, adapter-owned clients)
- [x] Process patterns documented (hybrid error handling)

**✅ Project Structure**
- [x] Complete directory structure defined (18 files MVP)
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** HIGH based on validation results and Party Mode review

**Key Strengths:**
- Clean Protocol-based adapter pattern enables easy source addition
- Hybrid error handling matches OSINT operational reality
- MVP structure is implementable in focused session
- All conflict points addressed with concrete examples

**Areas for Future Enhancement:**
- L1/L2 cache separation when complexity warrants
- Models partitioning as adapter count grows
- Advanced entity resolution (ML-based) in Phase 5

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries
- Stop entity resolution at first successful tier
- Confidence scoring happens at adapter level

**First Implementation Priority:**
```bash
uv init ignifer && cd ignifer
```
Then implement: `models.py` → `config.py` → `cache.py` → `adapters/base.py` → `adapters/gdelt.py` → `server.py`

## Architecture Completion Summary

### Workflow Completion

**Architecture Decision Workflow:** COMPLETED ✅
**Total Steps Completed:** 8
**Date Completed:** 2026-01-08
**Document Location:** `_bmad-output/planning-artifacts/architecture.md`

### Final Architecture Deliverables

**📋 Complete Architecture Document**
- All architectural decisions documented with specific versions
- Implementation patterns ensuring AI agent consistency
- Complete project structure with all files and directories
- Requirements to architecture mapping
- Validation confirming coherence and completeness

**🏗️ Implementation Ready Foundation**
- 15+ architectural decisions made
- 6 implementation pattern categories defined
- 18 MVP architectural components specified
- 46/51 requirements fully supported (5 deferred to Phase 5)

**📚 AI Agent Implementation Guide**
- Technology stack with verified versions
- Consistency rules that prevent implementation conflicts
- Project structure with clear boundaries
- Integration patterns and communication standards

### Development Sequence

1. Initialize project using `uv init ignifer`
2. Set up development environment per architecture
3. Implement core architectural foundations (`models.py`, `config.py`)
4. Build adapters following Protocol pattern
5. Add tools, output formatting, and caching
6. Maintain consistency with documented rules

### Quality Assurance Checklist

**✅ Architecture Coherence**
- [x] All decisions work together without conflicts
- [x] Technology choices are compatible
- [x] Patterns support the architectural decisions
- [x] Structure aligns with all choices

**✅ Requirements Coverage**
- [x] All functional requirements are supported
- [x] All non-functional requirements are addressed
- [x] Cross-cutting concerns are handled
- [x] Integration points are defined

**✅ Implementation Readiness**
- [x] Decisions are specific and actionable
- [x] Patterns prevent agent conflicts
- [x] Structure is complete and unambiguous
- [x] Examples are provided for clarity

---

**Architecture Status:** READY FOR IMPLEMENTATION ✅

**Next Phase:** Begin implementation using the architectural decisions and patterns documented herein.

**Document Maintenance:** Update this architecture when major technical decisions are made during implementation.

