---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - prd.md
  - architecture.md
  - _reference/TSUKUYOMI/TSUKUYOMI_Doc.md
  - _reference/TSUKUYOMI/README.md
  - _reference/TSUKUYOMI/CLAUDE.md
---

# Ignifer - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Ignifer, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

**Intelligence Briefings (FR1-FR5)**
- FR1: Users can request a topic briefing on any geopolitical topic or region
- FR2: Users can receive news/event analysis with source attribution and timestamps
- FR3: Users can receive economic context alongside news analysis for relevant topics
- FR4: Users can specify a time range for briefing queries (e.g., "last 48 hours", "this week")
- FR5: Users can request briefings in natural language without learning specific syntax

**Entity Intelligence (FR6-FR10)**
- FR6: Users can look up any named entity (person, organization, location, vessel, aircraft)
- FR7: Users can receive Wikidata-enriched entity information (aliases, relationships, identifiers)
- FR8: Users can receive cross-referenced sanctions/PEP status for entities
- FR9: Users can search entities by alternative identifiers (IMO number, MMSI, callsign, Q-ID)
- FR10: System automatically links related entities across data sources via Wikidata Q-IDs

**Transportation Tracking (FR11-FR15)**
- FR11: Users can track aircraft by callsign, tail number, or flight number
- FR12: Users can track vessels by name, IMO number, or MMSI
- FR13: Users can receive historical position data with timestamps for tracked assets
- FR14: Users can receive current status information (last known position, destination, speed)
- FR15: Users receive clear explanation when tracking data is incomplete

**Security Intelligence (FR16-FR20)**
- FR16: Users can request conflict analysis for any country or region
- FR17: Users can receive ACLED event data including incident types, actors, and casualties
- FR18: Users can screen any entity against sanctions lists (OFAC, EU, UN, national lists)
- FR19: Users can identify Politically Exposed Persons (PEPs) associated with entities
- FR20: Users can receive geographic distribution of conflict incidents

**Multi-Source Analysis (FR21-FR25)**
- FR21: Users can request deep-dive analysis that correlates multiple data sources
- FR22: System automatically identifies which sources are relevant to a query
- FR23: System presents corroborating evidence when multiple sources agree
- FR24: System highlights conflicting information when sources disagree
- FR25: Users can see which sources contributed to each part of an analysis

**Output & Verification Framework (FR26-FR31)**
- FR26: Users can receive clean summary briefings by default (no clutter)
- FR27: Users can enable Rigor Mode for IC-standard confidence levels
- FR28: Users can receive ICD 203-compliant confidence language in Rigor Mode
- FR29: Users can access source URLs and retrieval timestamps for all data points
- FR30: Users can receive output formatted for academic citation (Rigor Mode)
- FR31: System includes confidence percentages for entity matching and correlation

**Error Handling & Recovery (FR32-FR36)**
- FR32: System explains failures in user-friendly language (not raw API errors)
- FR33: System suggests alternative queries when primary source fails
- FR34: System offers cross-source triangulation when one source returns no results
- FR35: System indicates when data may be incomplete or outdated
- FR36: System gracefully degrades when upstream APIs are unavailable

**System Configuration (FR37-FR41)**
- FR37: Users can install via pip with zero additional configuration for Phase 1 sources
- FR38: Users can configure API keys for Phase 2-3 sources via environment variables or config file
- FR39: Users can check configured source status and API key validity
- FR40: Users can manually clear cache for specific sources or all sources
- FR41: Contributors can add new data source adapters by implementing OSINTAdapter protocol

**Visualization - Phase 5 (FR42-FR45)**
- FR42: Users can request trend charts for time-series data
- FR43: Users can request geographic maps for location-based data (vessel tracks, conflict events)
- FR44: Users can request entity relationship graphs
- FR45: System generates visual artifacts in standard formats (PNG, SVG)

**Power User & Advanced Controls (FR46-FR51)**
- FR46: Users can invoke tools directly by name as a power-user escape hatch
- FR47: Users can check real-time availability status of data sources
- FR48: Users can set rigor mode preference globally or per-query
- FR49: Users can explicitly include or exclude specific sources from a query
- FR50: Users can accept or modify suggested alternative queries
- FR51: Users can customize visualization parameters (time range, filters, zoom level)

### NonFunctional Requirements

**Performance (NFR-P1 to NFR-P7)**
- NFR-P1: Single-source queries return within 5 seconds (p95 response time)
- NFR-P2: Multi-source queries return within 15 seconds (p95 response time)
- NFR-P3: Cache lookups return within 100ms (p95 response time)
- NFR-P4: Phase 1 sources (zero-auth) respond within 3 seconds (per-source p95)
- NFR-P5: System remains responsive during API timeouts (no UI freeze)
- NFR-P6: Individual API calls timeout after 10 seconds with graceful fallback
- NFR-P7: Total query timeout of 30 seconds prevents infinite waits

**Integration (NFR-I1 to NFR-I5)**
- NFR-I1: All 7 data source APIs properly authenticated per their requirements
- NFR-I2: Rate limits respected for all upstream APIs
- NFR-I3: API response parsing handles schema variations gracefully
- NFR-I4: WebSocket connections (AISStream) auto-reconnect on disconnect
- NFR-I5: Each adapter isolated - one adapter failure doesn't affect others

**Reliability (NFR-R1 to NFR-R7)**
- NFR-R1: System continues operating when individual data sources unavailable
- NFR-R2: Cache serves stale data with warning when source unavailable
- NFR-R3: All errors presented as user-friendly explanations
- NFR-R4: When sources are available, 95% of well-formed queries return useful results
- NFR-R5: No data loss from cache corruption or process termination
- NFR-R6: Cache TTL configurable per source (default: news 1hr, positions 15min, sanctions 24hr)
- NFR-R7: Adapter failure modes are testable via mock injection

**Maintainability (NFR-M1 to NFR-M6)**
- NFR-M1: Code passes mypy strict type checking
- NFR-M2: Test coverage ≥80% for core modules (excluding CLI and generated code)
- NFR-M3: New adapter can be added without modifying core code
- NFR-M4: All public APIs documented with docstrings
- NFR-M5: Unit tests complete in <2 minutes; integration tests run separately
- NFR-M6: All dependencies pinned with hash verification for supply chain security

**API Key Security (NFR-S1 to NFR-S3)**
- NFR-S1: API keys never logged or included in error messages
- NFR-S2: API keys read from environment variables or secure config file
- NFR-S3: API keys never transmitted to any system except intended API

### Additional Requirements

**From Architecture - Project Foundation:**
- AR1: Initialize project using FastMCP 2.x + Modern Python Stack with `uv init`
- AR2: Use src layout with `src/ignifer/` package structure
- AR3: Build tooling: hatchling backend, uv dependency management
- AR4: Code quality enforcement: mypy strict mode, ruff linting, pytest testing
- AR5: MCP Transport: stdio (standard for Claude Desktop integration)
- AR6: Async-first design using httpx for REST APIs, websockets library for AIS

**From Architecture - Data Layer:**
- AR7: Multi-tier caching: L1 memory (hot), L2 SQLite (warm)
- AR8: Cache TTL defaults by source: GDELT 1hr, OpenSky 5min, AISStream 15min, World Bank 24hr, ACLED 12hr, OpenSanctions 24hr, Wikidata 7 days
- AR9: Deterministic cache key generation with parameter hash

**From Architecture - Adapter Pattern:**
- AR10: Protocol-based adapter pattern using `typing.Protocol` with `@runtime_checkable`
- AR11: Adapter-owned httpx clients (never share clients across adapters)
- AR12: Hybrid error handling: exceptions for unexpected failures, Result type for expected states (rate limit, no data)
- AR13: Error hierarchy: AdapterTimeoutError, AdapterParseError, AdapterAuthError, AdapterError (base)

**From Architecture - Entity Resolution:**
- AR14: Tiered entity resolution: exact → normalized → Wikidata lookup → fuzzy match
- AR15: Stop at first successful match tier; log which tier produced the match
- AR16: EntityMatch model tracking resolution_tier and match_confidence

**From Architecture - Output & Confidence:**
- AR17: Layered output architecture: summary → details → raw (progressive disclosure)
- AR18: ICD 203 confidence levels as ConfidenceLevel enum (REMOTE to ALMOST_CERTAIN)
- AR19: QualityTier enum (HIGH, MEDIUM, LOW) for source quality assessment
- AR20: Confidence scoring happens at adapter level based on source reliability

**From Architecture - Patterns & Conventions:**
- AR21: snake_case for all JSON fields (no camelCase)
- AR22: ISO 8601 datetime serialization with explicit timezone (UTC internally)
- AR23: Adapter class naming: {Source}Adapter (e.g., GDELTAdapter, OpenSkyAdapter)
- AR24: Python stdlib logging with `logging.getLogger(__name__)`
- AR25: Import organization via ruff (stdlib → third-party → local)

**From TSUKUYOMI Reference - OSINT Best Practices:**
- TR1: IC-standard analytical tradecraft (ICD 203, ICD 206 compliance)
- TR2: Confidence calibration with professional uncertainty communication
- TR3: Source quality assurance with correlation awareness
- TR4: Multi-domain intelligence methodology (structured OSINT approach)
- TR5: Source attribution and protection protocols
- TR6: Cross-source triangulation for validation

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 1 | Topic briefing requests |
| FR2 | Epic 1 | News/event analysis with attribution |
| FR3 | Epic 2 | Economic context alongside news |
| FR4 | Epic 2 | Time range specification |
| FR5 | Epic 1 | Natural language briefings |
| FR6 | Epic 3 | Named entity lookup |
| FR7 | Epic 3 | Wikidata-enriched entity info |
| FR8 | Epic 6 | Sanctions/PEP cross-reference |
| FR9 | Epic 3 | Alternative identifier search |
| FR10 | Epic 3 | Cross-source entity linking |
| FR11 | Epic 4 | Aircraft tracking |
| FR12 | Epic 5 | Vessel tracking |
| FR13 | Epic 4, 5 | Historical position data |
| FR14 | Epic 4, 5 | Current status information |
| FR15 | Epic 4, 5 | Incomplete data explanation |
| FR16 | Epic 6 | Conflict analysis by region |
| FR17 | Epic 6 | ACLED event data |
| FR18 | Epic 6 | Sanctions list screening |
| FR19 | Epic 6 | PEP identification |
| FR20 | Epic 6 | Conflict geographic distribution |
| FR21 | Epic 7 | Deep-dive multi-source analysis |
| FR22 | Epic 7 | Automatic source identification |
| FR23 | Epic 7 | Corroborating evidence presentation |
| FR24 | Epic 7 | Conflicting information highlighting |
| FR25 | Epic 7 | Source contribution visibility |
| FR26 | Epic 1 | Clean summary briefings |
| FR27 | Epic 8 | Rigor Mode enablement |
| FR28 | Epic 8 | ICD 203-compliant confidence |
| FR29 | Epic 8 | Source URLs and timestamps |
| FR30 | Epic 8 | Academic citation formatting |
| FR31 | Epic 8 | Confidence percentages |
| FR32 | Epic 1 | User-friendly error explanations |
| FR33 | Epic 1 | Alternative query suggestions |
| FR34 | Epic 1 | Cross-source triangulation |
| FR35 | Epic 1 | Incomplete/outdated data indication |
| FR36 | Epic 1 | Graceful degradation |
| FR37 | Epic 1 | Zero-config pip installation |
| FR38 | Epic 4 | API key configuration |
| FR39 | Epic 9 | Source status checking |
| FR40 | Epic 9 | Cache management |
| FR41 | Epic 9 | Adapter protocol for contributors |
| FR42 | Epic 10 | Trend charts (Phase 5) |
| FR43 | Epic 10 | Geographic maps (Phase 5) |
| FR44 | Epic 10 | Entity relationship graphs (Phase 5) |
| FR45 | Epic 10 | Visual artifact formats (Phase 5) |
| FR46 | Epic 9 | Direct tool invocation |
| FR47 | Epic 9 | Source availability status |
| FR48 | Epic 9 | Rigor mode preference setting |
| FR49 | Epic 9 | Source inclusion/exclusion |
| FR50 | Epic 9 | Alternative query modification |
| FR51 | Epic 10 | Visualization parameters (Phase 5) |

## Epic List

### Epic 1: Project Foundation & First Insight
**Goal:** Users can install Ignifer via pip and immediately get their first topic briefing — no API keys required. This epic delivers the PRD's "aha moment": User asks "What's happening in Ukraine?" and gets a cited briefing.

**FRs covered:** FR1, FR2, FR5, FR26, FR32-36, FR37
**ARs covered:** AR1-AR13, AR17, AR21-AR25
**NFRs addressed:** NFR-P1, P3, P5-P7, NFR-M1-M6, NFR-S1-S3

---

### Epic 2: Economic Context & Time Ranges
**Goal:** Users receive economic indicators alongside news analysis and can specify time ranges for queries, enriching briefings with World Bank data.

**FRs covered:** FR3, FR4

---

### Epic 3: Entity Intelligence
**Goal:** Users can look up any entity (person, organization, vessel, location) and get Wikidata-enriched information with aliases, relationships, and identifiers. Completes **Phase 1: Zero-Config OSINT**.

**FRs covered:** FR6, FR7, FR9, FR10
**ARs covered:** AR14-AR16 (entity resolution patterns)

---

### Epic 4: Aviation Tracking
**Goal:** Users can track aircraft by callsign/tail number and get historical position data with timestamps. Introduces API key configuration for OpenSky.

**FRs covered:** FR11, FR13-15, FR38

---

### Epic 5: Maritime Tracking
**Goal:** Users can track vessels by name/IMO/MMSI and get position history via AISStream WebSocket. Completes **Phase 2: Tracking**.

**FRs covered:** FR12-15
**NFRs addressed:** NFR-I4 (WebSocket reconnection)

---

### Epic 6: Conflict & Security Analysis
**Goal:** Users can analyze conflicts by region (ACLED data) and screen entities against sanctions lists (OpenSanctions). Completes **Phase 3: Security Intelligence**.

**FRs covered:** FR8, FR16-20

---

### Epic 7: Multi-Source Correlation
**Goal:** Users can request deep-dive analysis that correlates all seven data sources, with automatic source selection and cross-source entity linking.

**FRs covered:** FR21-25

---

### Epic 8: Rigor Mode & Citation Framework
**Goal:** Researchers get IC-standard output with ICD 203 confidence levels, complete source attribution, and academic citation formatting. Completes **Phase 4: Integration & Rigor**.

**FRs covered:** FR27-31
**TRs covered:** TR1-TR6 (OSINT best practices)

---

### Epic 9: System Administration & Power Features
**Goal:** Power users have full control — check source status, manage cache, invoke tools directly, and customize source selection.

**FRs covered:** FR39-41, FR46-50

---

### Epic 10: Visualization (Future - Phase 5)
**Goal:** Users can generate trend charts, geographic maps, and entity relationship graphs. **Deferred** per PRD scope.

**FRs covered:** FR42-45, FR51

---

## Epic 1: Project Foundation & First Insight

**Goal:** Users can install Ignifer via pip and immediately get their first topic briefing — no API keys required. This epic delivers the "aha moment": User asks "What's happening in Ukraine?" and gets a cited briefing.

### Story 1.1: Project Initialization & Build Configuration

As a **developer**,
I want **a properly structured Python MCP server project with modern build tooling**,
So that **I can install, develop, and distribute Ignifer following Python best practices**.

**Acceptance Criteria:**

**Given** a clean development environment with Python 3.10+ and uv installed
**When** I run `uv init` and set up the project structure
**Then** the following structure exists:
- `src/ignifer/` package directory with `__init__.py` and `__main__.py`
- `src/ignifer/adapters/` directory with `__init__.py`
- `tests/` directory with `conftest.py`
- `tests/adapters/` directory
- `tests/fixtures/` directory
**And** `pyproject.toml` includes:
- Project metadata (name="ignifer", requires-python=">=3.10")
- Dependencies: fastmcp>=2.14, httpx>=0.28, pydantic>=2.12, tenacity>=9.1
- Dev dependencies: pytest, pytest-asyncio, pytest-cov, pytest-httpx, mypy, ruff
- Build system using hatchling
- Entry point: `ignifer = "ignifer.server:main"`

**Given** the project is initialized
**When** I run `uv pip install -e ".[dev]"`
**Then** the package installs successfully in editable mode
**And** running `python -m ignifer` executes without import errors (may exit with "not implemented" message)

**Given** the Makefile exists
**When** I run `make lint`
**Then** ruff checks pass on the project skeleton
**And** `make type-check` runs mypy without configuration errors

---

### Story 1.2: Core Models & Configuration

As a **developer**,
I want **well-defined Pydantic models and centralized configuration**,
So that **all components share consistent data structures and settings**.

**Acceptance Criteria:**

**Given** the project structure from Story 1.1
**When** I create `src/ignifer/models.py`
**Then** it defines the following models with proper type hints:
- `QueryParams`: topic (str), time_range (optional), sources (optional list)
- `SourceMetadata`: source_name (str), source_url (str), retrieved_at (datetime with timezone)
- `ConfidenceLevel`: Enum with REMOTE, UNLIKELY, EVEN_CHANCE, LIKELY, VERY_LIKELY, ALMOST_CERTAIN and methods `to_percentage_range()`, `to_label()`
- `QualityTier`: Enum with HIGH, MEDIUM, LOW
- `ResultStatus`: Enum with SUCCESS, NO_DATA, RATE_LIMITED, ERROR
- `OSINTResult`: status, data (dict), sources (list[SourceMetadata]), confidence, quality_tier
- `SourceAttribution`: source (str), url (str), retrieved_at (datetime)
**And** all datetime fields serialize to ISO 8601 with timezone
**And** all field names use snake_case

**Given** models.py exists
**When** I create `src/ignifer/config.py`
**Then** it provides:
- `Settings` class reading from environment variables (IGNIFER_* prefix)
- TTL defaults per source (GDELT=3600, OPENSKY=300, etc.)
- Logging configuration using stdlib logging
- `get_settings()` function returning singleton Settings instance
**And** API keys are never logged even at DEBUG level

**Given** both modules exist
**When** I run `make type-check`
**Then** mypy passes with strict mode
**And** all public classes are importable from `ignifer.models` and `ignifer.config`

---

### Story 1.3: Cache Layer Implementation

As a **developer**,
I want **a multi-tier caching system with TTL support**,
So that **API responses are cached to reduce latency and respect rate limits**.

**Acceptance Criteria:**

**Given** the models and config from Story 1.2
**When** I create `src/ignifer/cache.py`
**Then** it implements:
- `cache_key(adapter: str, query: str, **params) -> str` function generating deterministic keys
- `CacheEntry` model with: key, data, created_at, ttl_seconds, source
- `MemoryCache` class (L1) with get/set/invalidate methods
- `SQLiteCache` class (L2) with get/set/invalidate methods using WAL mode
- `CacheManager` class coordinating L1 → L2 lookup with stale-while-revalidate

**Given** CacheManager is initialized
**When** I call `cache.get(key)` for a non-existent key
**Then** it returns `None`
**And** no errors are raised

**Given** CacheManager has a cached entry within TTL
**When** I call `cache.get(key)`
**Then** it returns the cached data
**And** L1 is checked before L2
**And** cache hit is logged at DEBUG level

**Given** CacheManager has an expired entry
**When** I call `cache.get(key)` with `allow_stale=True`
**Then** it returns the stale data with `is_stale=True` flag
**And** a warning is logged about serving stale data

**Given** cache.py exists
**When** I run `pytest tests/test_cache.py`
**Then** all cache scenarios pass including TTL expiration and L1/L2 coordination

---

### Story 1.4: Adapter Protocol & Error Hierarchy

As a **developer**,
I want **a well-defined adapter interface with consistent error handling**,
So that **all data source adapters follow the same contract and errors are handled predictably**.

**Acceptance Criteria:**

**Given** the models from Story 1.2
**When** I create `src/ignifer/adapters/base.py`
**Then** it defines:
- `OSINTAdapter` Protocol with `@runtime_checkable` decorator
- Protocol requires: `source_name` property, `base_quality_tier` property, `async query(params)` method, `async health_check()` method
- `AdapterError` base exception class
- `AdapterTimeoutError(AdapterError)` for network timeouts
- `AdapterParseError(AdapterError)` for malformed responses
- `AdapterAuthError(AdapterError)` for authentication failures

**Given** base.py exists
**When** I check `isinstance(adapter, OSINTAdapter)` on a conforming class
**Then** it returns `True`
**And** the check works at runtime without explicit inheritance

**Given** an adapter raises `AdapterTimeoutError`
**When** the error is caught
**Then** it includes the source name in the error message
**And** the original exception is chained via `from`

**Given** adapters/__init__.py exists
**When** I import `from ignifer.adapters import OSINTAdapter, AdapterError`
**Then** imports succeed
**And** `__all__` explicitly lists public exports

---

### Story 1.5: GDELT Adapter

As a **OSINT enthusiast**,
I want **to query GDELT for news and event data**,
So that **I can get intelligence briefings on any topic without API keys**.

**Acceptance Criteria:**

**Given** the adapter protocol from Story 1.4 and cache from Story 1.3
**When** I create `src/ignifer/adapters/gdelt.py`
**Then** `GDELTAdapter` class:
- Implements `OSINTAdapter` protocol
- Has `source_name = "gdelt"` and `base_quality_tier = QualityTier.MEDIUM`
- Creates adapter-owned `httpx.AsyncClient` (not shared)
- Implements `async query(params: QueryParams) -> OSINTResult`
- Implements `async health_check() -> bool`
- Implements `async close()` for cleanup

**Given** GDELTAdapter is instantiated
**When** I call `await adapter.query(QueryParams(topic="Ukraine"))`
**Then** it queries GDELT API v2 for articles matching the topic
**And** returns `OSINTResult` with status=SUCCESS and populated data
**And** includes source attribution with GDELT URL and retrieval timestamp
**And** results are cached using CacheManager with 1-hour TTL

**Given** GDELT API returns no results
**When** I call `await adapter.query(params)`
**Then** it returns `OSINTResult` with status=NO_DATA
**And** suggests alternative query approaches in the result

**Given** GDELT API times out (>10 seconds)
**When** I call `await adapter.query(params)`
**Then** it raises `AdapterTimeoutError` with source name
**And** the timeout is enforced via httpx timeout configuration

**Given** test fixtures exist in `tests/fixtures/gdelt_response.json`
**When** I run `pytest tests/adapters/test_gdelt.py`
**Then** all tests pass using mocked HTTP responses
**And** no actual API calls are made during tests

---

### Story 1.6: Output Formatting & Briefing Tool

As a **geopolitical enthusiast**,
I want **to ask about any topic and get a clean, cited intelligence briefing**,
So that **I can understand what's happening in the world without tab-switching**.

**Acceptance Criteria:**

**Given** the GDELT adapter from Story 1.5
**When** I create `src/ignifer/output.py`
**Then** `OutputFormatter` class:
- Takes `OSINTResult` and formats to clean summary string
- Includes source attribution (source name, URL, timestamp)
- Uses progressive disclosure (summary first, details available)
- Handles error results with user-friendly messages

**Given** OutputFormatter receives successful GDELT results
**When** I call `formatter.format(result)`
**Then** output includes:
- Brief summary of key findings
- Source count and quality indication
- Timestamp of data retrieval
- No raw API response details (clean output)

**Given** the server module exists
**When** I create/update `src/ignifer/server.py`
**Then** it implements:
- FastMCP server using `mcp = FastMCP("ignifer")`
- `@mcp.tool()` decorated `briefing(topic: str)` function
- Tool wires: parse params → GDELTAdapter.query() → OutputFormatter.format()
- Graceful error handling returning user-friendly messages (FR32)
- Alternative query suggestions on failure (FR33)
- Data freshness indication (FR35)

**Given** Ignifer is installed and Claude Desktop config includes it
**When** user asks "What's happening in Taiwan?"
**Then** Claude calls `briefing("Taiwan")`
**And** returns a cited briefing with GDELT news analysis
**And** response includes source URLs for verification

**Given** GDELT is unavailable
**When** user asks for a briefing
**Then** system returns graceful error message explaining the issue (FR36)
**And** suggests trying again later or narrowing the query

**Given** the complete Epic 1 implementation
**When** I run `make all` (lint + type-check + test)
**Then** all checks pass
**And** test coverage for core modules is ≥80%

---

## Epic 2: Economic Context & Time Ranges

**Goal:** Users receive economic indicators alongside news analysis and can specify time ranges for queries, enriching briefings with World Bank data.

### Story 2.1: World Bank Adapter

As a **researcher**,
I want **to access World Bank economic indicators**,
So that **I can understand economic context for countries I'm researching**.

**Acceptance Criteria:**

**Given** the adapter protocol from Epic 1
**When** I create `src/ignifer/adapters/worldbank.py`
**Then** `WorldBankAdapter` class:
- Implements `OSINTAdapter` protocol
- Has `source_name = "worldbank"` and `base_quality_tier = QualityTier.HIGH`
- Creates adapter-owned `httpx.AsyncClient`
- Uses wbgapi library or direct REST API calls
- Implements `async query(params: QueryParams) -> OSINTResult`
- Implements `async health_check() -> bool`

**Given** WorldBankAdapter is instantiated
**When** I call `await adapter.query(QueryParams(topic="Germany"))`
**Then** it fetches key economic indicators:
- GDP (current, growth rate)
- Inflation rate
- Unemployment rate
- Trade balance
- Population
**And** returns `OSINTResult` with status=SUCCESS and structured data
**And** includes source attribution with World Bank URL and retrieval timestamp
**And** results are cached with 24-hour TTL

**Given** World Bank API returns no data for a country
**When** I call `await adapter.query(params)`
**Then** it returns `OSINTResult` with status=NO_DATA
**And** suggests checking country name spelling or using ISO country code

**Given** test fixtures exist in `tests/fixtures/worldbank_response.json`
**When** I run `pytest tests/adapters/test_worldbank.py`
**Then** all tests pass using mocked responses

---

### Story 2.2: Economic Context Tool

As a **geopolitical analyst**,
I want **to get economic indicators for any country**,
So that **I can assess economic factors affecting geopolitical situations**.

**Acceptance Criteria:**

**Given** the WorldBankAdapter from Story 2.1
**When** I add `economic_context(country: str)` tool to server.py
**Then** it:
- Accepts country name or ISO code
- Calls WorldBankAdapter.query() with the country
- Returns formatted economic summary via OutputFormatter
- Includes key indicators with year of measurement
- Provides source attribution

**Given** user asks "What's the economic situation in Argentina?"
**When** Claude calls `economic_context("Argentina")`
**Then** returns formatted output including:
- GDP and growth trends
- Inflation and unemployment rates
- Key economic context
- Source: World Bank with data year

**Given** an invalid country name is provided
**When** `economic_context("Fakeland")` is called
**Then** returns user-friendly error suggesting valid alternatives
**And** does not expose raw API errors

---

### Story 2.3: Time Range Support for Briefings

As a **news follower**,
I want **to specify time ranges for my briefings**,
So that **I can focus on recent events or investigate specific periods**.

**Acceptance Criteria:**

**Given** the existing `briefing()` tool from Epic 1
**When** I add optional `time_range` parameter
**Then** it accepts values like:
- "last 24 hours", "last 48 hours"
- "this week", "last week"
- "last 7 days", "last 30 days"
- ISO date range: "2026-01-01 to 2026-01-08"

**Given** user asks "What happened in Syria last 48 hours?"
**When** Claude calls `briefing("Syria", time_range="last 48 hours")`
**Then** GDELT query is filtered to that time range
**And** results only include articles from that period
**And** output indicates the time range covered

**Given** user asks "Brief me on Ukraine" without time range
**When** Claude calls `briefing("Ukraine")`
**Then** defaults to sensible time range (e.g., last 7 days)
**And** output indicates the default time range used

**Given** time_range parsing encounters an invalid format
**When** user provides "yesterday morning"
**Then** returns helpful error explaining supported formats
**And** suggests alternatives like "last 24 hours"

**Given** GDELT returns no results for the specified time range
**When** query completes
**Then** suggests trying a broader time range
**And** indicates no articles found for that specific period

---

## Epic 3: Entity Intelligence

**Goal:** Users can look up any entity (person, organization, vessel, location) and get Wikidata-enriched information with aliases, relationships, and identifiers. Completes **Phase 1: Zero-Config OSINT**.

### Story 3.1: Wikidata Adapter

As a **researcher**,
I want **to query Wikidata for entity information**,
So that **I can get authoritative data about people, organizations, places, and things**.

**Acceptance Criteria:**

**Given** the adapter protocol from Epic 1
**When** I create `src/ignifer/adapters/wikidata.py`
**Then** `WikidataAdapter` class:
- Implements `OSINTAdapter` protocol
- Has `source_name = "wikidata"` and `base_quality_tier = QualityTier.HIGH`
- Uses SPARQLWrapper library for Wikidata Query Service
- Implements `async query(params: QueryParams) -> OSINTResult`
- Implements `async health_check() -> bool`
- Implements `async lookup_by_qid(qid: str) -> OSINTResult` for direct Q-ID lookup

**Given** WikidataAdapter is instantiated
**When** I call `await adapter.query(QueryParams(topic="Vladimir Putin"))`
**Then** it executes SPARQL query against Wikidata
**And** returns `OSINTResult` containing:
- Wikidata Q-ID (e.g., Q7747)
- Labels in multiple languages
- Aliases and alternative names
- Description
- Key properties (instance of, occupation, country, etc.)
- Related entities with their Q-IDs
**And** results are cached with 7-day TTL

**Given** an entity search returns multiple matches
**When** I call `await adapter.query(QueryParams(topic="Paris"))`
**Then** returns ranked results (Paris, France first; then Paris, Texas, etc.)
**And** each result includes disambiguation information

**Given** a Wikidata Q-ID is provided directly
**When** I call `await adapter.lookup_by_qid("Q7747")`
**Then** returns full entity details for that specific Q-ID
**And** bypasses search, directly fetching entity data

**Given** test fixtures exist in `tests/fixtures/wikidata_entity.json`
**When** I run `pytest tests/adapters/test_wikidata.py`
**Then** all tests pass using mocked SPARQL responses

---

### Story 3.2: Entity Resolution Module

As a **developer**,
I want **a tiered entity resolution system**,
So that **entities can be matched across different data sources reliably**.

**Acceptance Criteria:**

**Given** the models from Epic 1
**When** I create `src/ignifer/aggregation/entity_resolver.py`
**Then** it implements:
- `EntityMatch` model with: entity_id, wikidata_qid, resolution_tier, match_confidence, original_query
- `EntityResolver` class with `async resolve(query: str) -> EntityMatch`
- Resolution tiers: "exact", "normalized", "wikidata", "fuzzy", "failed"

**Given** EntityResolver receives a query
**When** I call `await resolver.resolve("Vladimir Putin")`
**Then** it attempts resolution in order:
1. **Exact match**: Direct string equality against known entities
2. **Normalized match**: Lowercase, strip whitespace, remove diacritics
3. **Wikidata lookup**: Query Wikidata for Q-ID and aliases
4. **Fuzzy match**: Levenshtein distance with configurable threshold (last resort)
**And** stops at first successful tier
**And** logs which tier produced the match

**Given** exact match succeeds
**When** resolution completes
**Then** returns `EntityMatch` with:
- resolution_tier="exact"
- match_confidence=1.0
- wikidata_qid if known

**Given** only fuzzy match succeeds
**When** resolution completes
**Then** returns `EntityMatch` with:
- resolution_tier="fuzzy"
- match_confidence=0.7-0.9 (based on distance)
- warning about lower confidence

**Given** no match is found at any tier
**When** resolution completes
**Then** returns `EntityMatch` with:
- resolution_tier="failed"
- match_confidence=0.0
- suggestions for alternative queries

**Given** tests exist in `tests/aggregation/test_entity_resolver.py`
**When** I run pytest
**Then** all resolution scenarios pass including tier progression

---

### Story 3.3: Entity Lookup Tool

As a **OSINT analyst**,
I want **to look up any entity and get comprehensive intelligence**,
So that **I can quickly understand who or what I'm researching**.

**Acceptance Criteria:**

**Given** WikidataAdapter and EntityResolver from Stories 3.1-3.2
**When** I add `entity_lookup(name: str, identifier: str = None)` tool to server.py
**Then** it:
- Accepts entity name or alternative identifier
- Uses EntityResolver for name matching
- Calls WikidataAdapter for entity details
- Returns formatted entity intelligence via OutputFormatter

**Given** user asks "Tell me about Gazprom"
**When** Claude calls `entity_lookup("Gazprom")`
**Then** returns formatted output including:
- Entity type (company/organization)
- Wikidata Q-ID for cross-referencing
- Headquarters, founding date, key facts
- Related entities (subsidiaries, key people)
- Aliases and alternative names
- Source attribution

**Given** user provides alternative identifier
**When** Claude calls `entity_lookup(identifier="Q102673")` (Wikidata Q-ID)
**Then** directly fetches entity by Q-ID
**And** returns same comprehensive output

**Given** user searches for vessel by IMO
**When** Claude calls `entity_lookup(identifier="IMO 9312456")`
**Then** searches Wikidata for vessel with that IMO number
**And** returns vessel information if found
**And** notes this identifier can be used for tracking in Epic 5

**Given** entity resolution fails
**When** no match is found
**Then** returns helpful message with:
- Suggestions for alternative spellings
- Tip to try Wikidata Q-ID if known
- Note about which resolution tiers were attempted

**Given** multiple entities match the query
**When** disambiguation is needed
**Then** returns top matches with disambiguation info
**And** suggests user clarify or use Q-ID for specific entity

---

### Story 3.4: Economic Context Wikidata Integration

As a **geopolitical analyst**,
I want **economic context to include government and institutional information**,
So that **I can understand the political context affecting economic conditions**.

**Acceptance Criteria:**

**Given** the economic_context tool from Epic 2
**When** I enhance it with Wikidata integration
**Then** it:
- Queries Wikidata for country institutional context (head of government, currency)
- Displays government leadership information when available
- Displays currency information when available
- Silently omits government context section if Wikidata lookup fails

**Given** the economic_context tool
**When** I add GDELT integration
**Then** it:
- Queries GDELT for recent economic events mentioning the country
- Displays up to 5 recent economic events (sanctions, trade, inflation news)
- Silently omits events section if GDELT lookup fails

**Given** the economic_context output format
**When** I restructure with E-series categories
**Then** output includes:
- KEY INDICATORS section with core economic data
- VULNERABILITY ASSESSMENT (E1) section with debt and reserves metrics
- TRADE PROFILE (E2) section with export/import metrics
- FINANCIAL INDICATORS (E4) section with inflation, unemployment, FDI
- RECENT ECONOMIC EVENTS section with GDELT news
- Sources attribution listing all contributing data sources

**Given** Wikidata lookup fails
**When** economic_context completes
**Then** output still displays all World Bank indicators successfully
**And** government context line is simply omitted (no error message)
**And** "Wikidata" is not listed in sources

**Given** GDELT lookup fails
**When** economic_context completes
**Then** output still displays all World Bank indicators successfully
**And** RECENT ECONOMIC EVENTS section is simply omitted (no error message)
**And** "GDELT" is not listed in sources

**Given** all sources succeed
**When** economic_context completes
**Then** sources line shows: "Sources: World Bank Open Data, Wikidata, GDELT"

---

## Epic 4: Aviation Tracking

**Goal:** Users can track aircraft by callsign/tail number and get historical position data with timestamps. Introduces API key configuration for OpenSky.

### Story 4.1: API Key Configuration Enhancement

As a **user**,
I want **to configure API keys for data sources that require authentication**,
So that **I can access OpenSky, ACLED, and other Phase 2+ sources**.

**Acceptance Criteria:**

**Given** the existing config.py from Epic 1
**When** I extend the Settings class
**Then** it supports:
- `IGNIFER_OPENSKY_USERNAME` environment variable
- `IGNIFER_OPENSKY_PASSWORD` environment variable
- `IGNIFER_ACLED_KEY` environment variable (for Epic 6)
- `IGNIFER_AISSTREAM_KEY` environment variable (for Epic 5)
- Optional config file at `~/.config/ignifer/config.toml`

**Given** environment variables are set
**When** Settings is loaded
**Then** API keys are accessible via `settings.opensky_username`, etc.
**And** keys are NEVER logged at any log level
**And** keys are NEVER included in error messages

**Given** no API key is configured for a source
**When** an adapter requiring that key is used
**Then** returns clear error message: "OpenSky requires authentication. Set IGNIFER_OPENSKY_USERNAME and IGNIFER_OPENSKY_PASSWORD environment variables."
**And** does not attempt API call without credentials

**Given** config file exists at `~/.config/ignifer/config.toml`
**When** Settings is loaded
**Then** reads API keys from file if environment variables not set
**And** environment variables take precedence over config file

**Given** tests exist
**When** I run `pytest tests/test_config.py`
**Then** all API key handling scenarios pass
**And** no actual credentials are logged or exposed in test output

---

### Story 4.2: OpenSky Adapter

As a **aviation enthusiast**,
I want **to query OpenSky Network for flight data**,
So that **I can track aircraft positions and flight paths**.

**Acceptance Criteria:**

**Given** the adapter protocol and API key config from previous stories
**When** I create `src/ignifer/adapters/opensky.py`
**Then** `OpenSkyAdapter` class:
- Implements `OSINTAdapter` protocol
- Has `source_name = "opensky"` and `base_quality_tier = QualityTier.HIGH`
- Creates adapter-owned `httpx.AsyncClient` with OAuth2 credentials
- Implements `async query(params: QueryParams) -> OSINTResult`
- Implements `async get_states(icao24: str = None) -> OSINTResult` for current state vectors
- Implements `async get_track(icao24: str) -> OSINTResult` for flight track history
- Implements `async health_check() -> bool`

**Given** OpenSkyAdapter is instantiated with valid credentials
**When** I call `await adapter.query(QueryParams(topic="UAL123"))` with callsign
**Then** it queries OpenSky API for matching aircraft
**And** returns `OSINTResult` with:
- ICAO24 transponder code
- Callsign
- Current position (lat, lon, altitude)
- Velocity and heading
- Origin/destination if available
- Last contact timestamp
**And** results are cached with 5-minute TTL

**Given** I request flight track history
**When** I call `await adapter.get_track("a1b2c3")` with ICAO24 code
**Then** returns historical positions over past 24 hours
**And** each position includes timestamp, lat, lon, altitude
**And** positions are ordered chronologically

**Given** OpenSky API is unavailable or rate limited
**When** query fails
**Then** raises appropriate adapter error
**And** suggests checking credentials or trying later

**Given** credentials are invalid
**When** I call any query method
**Then** raises `AdapterAuthError` with clear message
**And** does not retry with bad credentials

**Given** test fixtures exist in `tests/fixtures/opensky_states.json`
**When** I run `pytest tests/adapters/test_opensky.py`
**Then** all tests pass using mocked HTTP responses

---

### Story 4.3: Track Flight Tool

As a **flight tracker**,
I want **to track any aircraft by callsign or identifier**,
So that **I can see where planes are and where they've been**.

**Acceptance Criteria:**

**Given** OpenSkyAdapter from Story 4.2
**When** I add `track_flight(identifier: str)` tool to server.py
**Then** it:
- Accepts callsign (UAL123), tail number (N12345), or ICAO24 code
- Resolves identifier to ICAO24 if needed
- Calls OpenSkyAdapter for current state and track history
- Returns formatted flight intelligence via OutputFormatter

**Given** user asks "Where is flight UAL123?"
**When** Claude calls `track_flight("UAL123")`
**Then** returns formatted output including:
- Current position (lat/lon/altitude) with timestamp
- Heading and ground speed
- Aircraft type if available
- Last 24-hour track summary (departure, current, trajectory)
- Source: OpenSky Network with data timestamp

**Given** user asks "Track N12345" (tail number)
**When** Claude calls `track_flight("N12345")`
**Then** resolves tail number to ICAO24
**And** returns same position and track information

**Given** flight is not currently broadcasting (FR15)
**When** no current data is available
**Then** returns clear explanation:
- "Aircraft not currently broadcasting position"
- Shows last known position with timestamp if available
- Explains ADS-B coverage limitations
- Suggests aircraft may be on ground or out of coverage

**Given** OpenSky credentials are not configured
**When** user attempts to track a flight
**Then** returns helpful error:
- Explains OpenSky requires free registration
- Provides link to OpenSky registration
- Shows how to configure credentials

**Given** track history is incomplete
**When** gaps exist in position data
**Then** indicates gaps in the output
**And** explains ADS-B coverage is not global

---

## Epic 5: Maritime Tracking

**Goal:** Users can track vessels by name/IMO/MMSI and get position history via AISStream WebSocket. Completes **Phase 2: Tracking**.

### Story 5.1: AISStream Adapter

As a **maritime analyst**,
I want **to query AISStream for vessel position data**,
So that **I can track ships and understand maritime activity**.

**Acceptance Criteria:**

**Given** the adapter protocol and API key config from Epic 4
**When** I create `src/ignifer/adapters/aisstream.py`
**Then** `AISStreamAdapter` class:
- Implements `OSINTAdapter` protocol
- Has `source_name = "aisstream"` and `base_quality_tier = QualityTier.HIGH`
- Uses `websockets` library for WebSocket connections
- Implements connection-on-demand pattern: connect → query → cache → disconnect
- Implements `async query(params: QueryParams) -> OSINTResult`
- Implements `async get_vessel_position(mmsi: str) -> OSINTResult`
- Implements `async health_check() -> bool`

**Given** the MCP stdio transport constraint
**When** AISStreamAdapter needs vessel data
**Then** it follows connection-on-demand pattern:
1. Open WebSocket connection to AISStream
2. Subscribe to vessel by MMSI/IMO
3. Receive position message(s)
4. Cache the result with 15-minute TTL
5. Close WebSocket connection
**And** does NOT maintain persistent WebSocket between queries

**Given** AISStreamAdapter is instantiated with valid API key
**When** I call `await adapter.query(QueryParams(topic="367596480"))` with MMSI
**Then** returns `OSINTResult` with:
- MMSI and IMO numbers
- Vessel name and type
- Current position (lat, lon)
- Speed over ground, course
- Destination and ETA if available
- Last AIS message timestamp
**And** results are cached with 15-minute TTL

**Given** WebSocket connection fails or times out
**When** query is attempted
**Then** implements auto-reconnect with exponential backoff (NFR-I4)
**And** raises `AdapterTimeoutError` after 3 retry attempts
**And** suggests checking API key or network connectivity

**Given** WebSocket disconnects during query
**When** reconnection is needed
**Then** reconnects within 30 seconds
**And** completes query if possible
**And** returns partial data with warning if reconnection fails

**Given** test fixtures exist in `tests/fixtures/aisstream_message.json`
**When** I run `pytest tests/adapters/test_aisstream.py`
**Then** all tests pass using mocked WebSocket responses
**And** reconnection scenarios are tested

---

### Story 5.2: Track Vessel Tool

As a **maritime researcher**,
I want **to track any vessel by name, IMO, or MMSI**,
So that **I can monitor ship movements and locations**.

**Acceptance Criteria:**

**Given** AISStreamAdapter from Story 5.1
**When** I add `track_vessel(identifier: str)` tool to server.py
**Then** it:
- Accepts vessel name, IMO number (IMO 9312456), or MMSI (367596480)
- Resolves name to MMSI via search if needed
- Calls AISStreamAdapter for current position
- Returns formatted vessel intelligence via OutputFormatter

**Given** user asks "Where is the vessel Ever Given?"
**When** Claude calls `track_vessel("Ever Given")`
**Then** returns formatted output including:
- Current position (lat/lon) with timestamp
- Speed and heading
- Vessel type and flag state
- Destination and ETA if broadcasting
- IMO and MMSI numbers for future reference
- Source: AISStream with data timestamp

**Given** user provides IMO number
**When** Claude calls `track_vessel("IMO 9811000")`
**Then** looks up vessel by IMO
**And** returns same comprehensive position information

**Given** user provides MMSI
**When** Claude calls `track_vessel("367596480")`
**Then** directly queries by MMSI
**And** returns position data

**Given** vessel is not broadcasting AIS (FR15)
**When** no current data is available
**Then** returns clear explanation:
- "Vessel not currently broadcasting AIS"
- Shows last cached position with timestamp if available
- Explains possible reasons (AIS disabled, out of receiver range, in port)
- Notes that some vessels intentionally disable AIS

**Given** AISStream API key is not configured
**When** user attempts to track a vessel
**Then** returns helpful error:
- Explains AISStream requires free API key
- Provides link to AISStream registration
- Shows how to configure the API key

**Given** vessel name search returns multiple matches
**When** disambiguation is needed
**Then** returns top matches with vessel details
**And** suggests using IMO or MMSI for specific vessel

**Given** AIS data shows vessel is stationary
**When** position is returned
**Then** indicates "At anchor" or "Moored" status if available
**And** shows how long vessel has been stationary if known

---

## Epic 6: Conflict & Security Analysis

**Goal:** Users can analyze conflicts by region (ACLED data) and screen entities against sanctions lists (OpenSanctions). Completes **Phase 3: Security Intelligence**.

### Story 6.1: ACLED Adapter

As a **security analyst**,
I want **to query ACLED for conflict event data**,
So that **I can understand violence patterns and security situations in any region**.

**Acceptance Criteria:**

**Given** the adapter protocol and API key config from Epic 4
**When** I create `src/ignifer/adapters/acled.py`
**Then** `ACLEDAdapter` class:
- Implements `OSINTAdapter` protocol
- Has `source_name = "acled"` and `base_quality_tier = QualityTier.HIGH`
- Creates adapter-owned `httpx.AsyncClient`
- Implements `async query(params: QueryParams) -> OSINTResult`
- Implements `async get_events(country: str, date_range: str = None) -> OSINTResult`
- Implements `async health_check() -> bool`

**Given** ACLEDAdapter is instantiated with valid API key
**When** I call `await adapter.query(QueryParams(topic="Burkina Faso"))`
**Then** it queries ACLED API for conflict events
**And** returns `OSINTResult` with:
- Event count and date range
- Event types (battles, violence against civilians, protests, etc.)
- Actor categories (state forces, rebel groups, militias, etc.)
- Fatality counts and trends
- Geographic distribution (admin regions)
**And** results are cached with 12-hour TTL

**Given** I request events with date range
**When** I call `await adapter.get_events("Syria", date_range="last 30 days")`
**Then** returns events filtered to that period
**And** includes trend comparison to previous period if available

**Given** ACLED API key is not configured
**When** query is attempted
**Then** returns clear error explaining ACLED registration requirement
**And** provides link to ACLED access registration

**Given** ACLED returns no events for region
**When** query completes
**Then** returns `OSINTResult` with status=NO_DATA
**And** notes this may indicate peaceful conditions or data coverage gap

**Given** test fixtures exist in `tests/fixtures/acled_events.json`
**When** I run `pytest tests/adapters/test_acled.py`
**Then** all tests pass using mocked HTTP responses

---

### Story 6.2: OpenSanctions Adapter

As a **compliance researcher**,
I want **to screen entities against sanctions lists**,
So that **I can identify sanctioned entities and politically exposed persons**.

**Acceptance Criteria:**

**Given** the adapter protocol from Epic 1
**When** I create `src/ignifer/adapters/opensanctions.py`
**Then** `OpenSanctionsAdapter` class:
- Implements `OSINTAdapter` protocol
- Has `source_name = "opensanctions"` and `base_quality_tier = QualityTier.HIGH`
- Uses OpenSanctions API (free for non-commercial use)
- Implements `async query(params: QueryParams) -> OSINTResult`
- Implements `async search_entity(name: str) -> OSINTResult`
- Implements `async check_sanctions(entity_id: str) -> OSINTResult`
- Implements `async health_check() -> bool`

**Given** OpenSanctionsAdapter is instantiated
**When** I call `await adapter.query(QueryParams(topic="Viktor Vekselberg"))`
**Then** it searches OpenSanctions database
**And** returns `OSINTResult` with:
- Match confidence score
- Entity type (person, organization, vessel, etc.)
- Sanctions lists matched (OFAC SDN, EU, UN, etc.)
- PEP status if applicable
- Associated entities (companies, family members)
- Source references and dates
**And** results are cached with 24-hour TTL

**Given** entity matches multiple sanctions lists
**When** results are returned
**Then** lists each sanctions program separately
**And** includes effective dates and reasons where available

**Given** entity is a PEP but not sanctioned (FR19)
**When** search completes
**Then** indicates PEP status with position held
**And** notes PEP is not currently sanctioned
**And** suggests enhanced due diligence

**Given** no match is found
**When** search completes
**Then** returns clear "No matches found" result
**And** includes confidence that search was comprehensive
**And** notes entity may use aliases not in database

**Given** test fixtures exist in `tests/fixtures/opensanctions_entity.json`
**When** I run `pytest tests/adapters/test_opensanctions.py`
**Then** all tests pass using mocked HTTP responses

---

### Story 6.3: Conflict Analysis Tool

As a **geopolitical analyst**,
I want **to analyze conflict situations in any country or region**,
So that **I can assess security conditions and violence trends**.

**Acceptance Criteria:**

**Given** ACLEDAdapter from Story 6.1
**When** I add `conflict_analysis(region: str, time_range: str = None)` tool to server.py
**Then** it:
- Accepts country name, region, or geographic area
- Calls ACLEDAdapter for conflict events
- Returns formatted conflict intelligence via OutputFormatter

**Given** user asks "What's the conflict situation in Ethiopia?"
**When** Claude calls `conflict_analysis("Ethiopia")`
**Then** returns formatted output including:
- Summary of recent conflict activity
- Event count by type (battles, civilian targeting, protests)
- Primary actors involved
- Fatality trends (increasing/decreasing/stable)
- Geographic hotspots within the country
- Source: ACLED with data date range

**Given** user specifies time range
**When** Claude calls `conflict_analysis("Sahel", time_range="last 90 days")`
**Then** returns events for that period
**And** includes comparison to previous period

**Given** user asks about geographic distribution (FR20)
**When** conflict_analysis returns results
**Then** includes breakdown by admin region/province
**And** identifies areas with highest incident concentration

**Given** ACLED credentials are not configured
**When** user attempts conflict analysis
**Then** returns helpful error with registration instructions

**Given** region has no recent conflict events
**When** analysis completes
**Then** indicates low/no conflict activity
**And** notes this could indicate stability or data coverage limitations

---

### Story 6.4: Sanctions Check Tool

As a **compliance professional**,
I want **to screen any entity against global sanctions lists**,
So that **I can identify risks and meet due diligence requirements**.

**Acceptance Criteria:**

**Given** OpenSanctionsAdapter from Story 6.2
**When** I add `sanctions_check(entity: str)` tool to server.py
**Then** it:
- Accepts entity name (person, company, vessel, etc.)
- Uses EntityResolver for name matching
- Calls OpenSanctionsAdapter for sanctions/PEP screening
- Returns formatted screening results via OutputFormatter

**Given** user asks "Is Rosneft sanctioned?"
**When** Claude calls `sanctions_check("Rosneft")`
**Then** returns formatted output including:
- Match result (MATCH / NO MATCH / PARTIAL MATCH)
- Match confidence percentage
- Sanctions lists where entity appears (FR18)
- Sanctions details (date, reason, authority)
- Associated entities also sanctioned
- Source: OpenSanctions with search timestamp

**Given** user asks about a person
**When** Claude calls `sanctions_check("Alisher Usmanov")`
**Then** returns sanctions status
**And** includes PEP status if applicable (FR19)
**And** lists associated companies and family members flagged

**Given** partial or fuzzy match is found
**When** results are returned
**Then** clearly indicates match confidence
**And** shows which name variations matched
**And** recommends verification for low-confidence matches

**Given** entity has cross-referenced sanctions status (FR8)
**When** sanctions_check is called for entity found via entity_lookup
**Then** can link using Wikidata Q-ID for precise matching
**And** notes cross-reference source

**Given** user screens a vessel
**When** Claude calls `sanctions_check("Akademik Cherskiy")`
**Then** searches by vessel name and IMO if available
**And** returns owner/operator sanctions status
**And** flags if vessel itself is designated

---

## Epic 7: Multi-Source Correlation

**Goal:** Users can request deep-dive analysis that correlates all seven data sources, with automatic source selection and cross-source entity linking.

### Story 7.1: Source Relevance Engine

As a **developer**,
I want **automatic identification of relevant data sources for any query**,
So that **the system queries only appropriate sources without user intervention**.

**Acceptance Criteria:**

**Given** all seven adapters are available (GDELT, World Bank, Wikidata, OpenSky, AISStream, ACLED, OpenSanctions)
**When** I create `src/ignifer/aggregation/relevance.py`
**Then** `SourceRelevanceEngine` class:
- Analyzes query text and parameters
- Returns ranked list of relevant sources with confidence scores
- Explains why each source is relevant
- Considers source availability (configured API keys)

**Given** user queries about a country (e.g., "Deep dive on Venezuela")
**When** relevance engine analyzes the query (FR22)
**Then** identifies relevant sources:
- GDELT: HIGH (news/events)
- World Bank: HIGH (economic indicators)
- ACLED: MEDIUM-HIGH (if conflict-prone region)
- Wikidata: MEDIUM (entity context)
- OpenSanctions: MEDIUM (sanctioned entities in region)
- OpenSky/AISStream: LOW (unless query mentions aviation/maritime)

**Given** user queries about a person (e.g., "Deep dive on Oleg Deripaska")
**When** relevance engine analyzes
**Then** identifies:
- Wikidata: HIGH (entity information)
- OpenSanctions: HIGH (sanctions/PEP status)
- GDELT: MEDIUM (news mentions)
- Other sources: LOW unless contextually relevant

**Given** user queries about a vessel
**When** relevance engine analyzes
**Then** identifies:
- AISStream: HIGH (position tracking)
- Wikidata: HIGH (vessel entity data)
- OpenSanctions: HIGH (sanctioned vessels)
- GDELT: MEDIUM (news about vessel)

**Given** source requires API key that's not configured
**When** relevance scoring completes
**Then** notes source as "relevant but unavailable"
**And** suggests configuring credentials

**Given** tests exist
**When** I run `pytest tests/aggregation/test_relevance.py`
**Then** all query type scenarios pass

---

### Story 7.2: Aggregator & Correlation Module

As a **analyst**,
I want **multi-source results to be correlated and conflicts identified**,
So that **I can see where sources agree and where they disagree**.

**Acceptance Criteria:**

**Given** SourceRelevanceEngine from Story 7.1
**When** I create `src/ignifer/aggregation/correlator.py`
**Then** `Correlator` class:
- Queries multiple adapters concurrently
- Combines results into unified response
- Identifies corroborating evidence across sources (FR23)
- Highlights conflicting information (FR24)
- Tracks source attribution for each data point (FR25)

**Given** Correlator receives results from multiple sources
**When** `await correlator.aggregate(query, sources)` is called
**Then** returns `AggregatedResult` with:
- Combined findings organized by topic
- Per-source attribution for each finding
- Corroboration markers where multiple sources agree
- Conflict markers where sources disagree
- Overall confidence assessment

**Given** two sources provide the same information
**When** results are aggregated (FR23)
**Then** marks finding as "Corroborated by [Source A, Source B]"
**And** increases confidence score for that finding

**Given** two sources provide conflicting information
**When** results are aggregated (FR24)
**Then** marks finding as "Conflicting: Source A says X, Source B says Y"
**And** includes both perspectives in output
**And** does NOT suppress either source
**And** suggests which source may be more authoritative based on quality tier

**Given** a finding comes from single source
**When** results are aggregated
**Then** marks as "Single source: [Source]"
**And** notes corroboration was not possible

**Given** user needs to trace information to source (FR25)
**When** output is generated
**Then** each paragraph/finding includes source tag
**And** sources are listed with URLs at end of output

**Given** tests exist
**When** I run `pytest tests/aggregation/test_correlator.py`
**Then** all correlation and conflict scenarios pass

---

### Story 7.3: Deep Dive Tool

As a **intelligence analyst**,
I want **to request comprehensive analysis correlating all available sources**,
So that **I can get a complete picture of any topic, entity, or situation**.

**Acceptance Criteria:**

**Given** SourceRelevanceEngine and Correlator from Stories 7.1-7.2
**When** I add `deep_dive(topic: str, focus: str = None)` tool to server.py
**Then** it:
- Accepts any topic (country, person, organization, vessel, event)
- Uses SourceRelevanceEngine to identify relevant sources
- Queries all relevant sources concurrently
- Uses Correlator to combine and analyze results
- Returns comprehensive formatted output via OutputFormatter

**Given** user asks "Give me a deep dive on Myanmar"
**When** Claude calls `deep_dive("Myanmar")` (FR21)
**Then** returns comprehensive analysis including:
- **News & Events** (GDELT): Recent developments, key stories
- **Economic Context** (World Bank): GDP, inflation, trade data
- **Conflict Situation** (ACLED): Violence trends, actors, hotspots
- **Key Entities** (Wikidata): Government, military leadership
- **Sanctions Exposure** (OpenSanctions): Sanctioned persons/entities in country
- **Source Attribution**: Clear indication of which source provided what
- **Corroboration Notes**: Where multiple sources agree
- **Conflicts/Gaps**: Where sources disagree or data is missing

**Given** user specifies focus area
**When** Claude calls `deep_dive("Iran", focus="sanctions")`
**Then** emphasizes sanctions-related sources
**And** still includes context from other relevant sources
**And** provides deeper detail on focus area

**Given** user deep dives on a person
**When** Claude calls `deep_dive("Roman Abramovich")`
**Then** returns:
- Entity profile (Wikidata)
- Sanctions status (OpenSanctions)
- News coverage (GDELT)
- Associated entities with their statuses
- Cross-source corroboration

**Given** user deep dives on a vessel
**When** Claude calls `deep_dive("NS Champion")`
**Then** returns:
- Vessel details (Wikidata/entity resolver)
- Current position (AISStream if available)
- Owner/operator sanctions (OpenSanctions)
- News mentions (GDELT)
- Related vessels or entities

**Given** some sources are unavailable (missing API keys)
**When** deep dive completes
**Then** notes which sources were not queried
**And** suggests configuring credentials for fuller analysis
**And** still returns best available analysis

**Given** sources return conflicting information
**When** deep dive output is generated
**Then** presents both perspectives clearly
**And** notes the conflict for user awareness
**And** does NOT attempt to resolve the conflict automatically

---

## Epic 8: Rigor Mode & Citation Framework

**Goal:** Researchers get IC-standard output with ICD 203 confidence levels, complete source attribution, and academic citation formatting. Completes **Phase 4: Integration & Rigor**.

### Story 8.1: ICD 203 Confidence Framework

As a **professional analyst**,
I want **IC-standard confidence levels in my intelligence products**,
So that **my assessments follow recognized analytical tradecraft standards**.

**Acceptance Criteria:**

**Given** the existing ConfidenceLevel enum from Epic 1
**When** I enhance `src/ignifer/models.py` and create `src/ignifer/confidence.py`
**Then** the confidence framework includes:
- Full ICD 203 confidence levels (TR1)
- `ConfidenceLevel` enum with: REMOTE (<5%), VERY_UNLIKELY (5-20%), UNLIKELY (20-45%), ROUGHLY_EVEN (45-55%), LIKELY (55-80%), VERY_LIKELY (80-95%), ALMOST_CERTAIN (>95%)
- `ConfidenceAssessment` model with: level, percentage_range, reasoning, key_factors
- `confidence_to_language(level: ConfidenceLevel) -> str` returning IC-standard phrasing

**Given** ConfidenceLevel.LIKELY is used
**When** converted to language (FR28)
**Then** returns phrases like:
- "We assess with moderate confidence that..."
- "It is likely that..." (55-80% probability)
**And** includes percentage range in parenthetical

**Given** confidence is derived from source quality
**When** assessment is made (TR2, TR3)
**Then** factors in:
- Source quality tier (HIGH/MEDIUM/LOW)
- Number of corroborating sources
- Recency of data
- Known source biases or limitations

**Given** entity matching produces confidence score (FR31)
**When** EntityMatch is returned
**Then** includes percentage confidence (e.g., "87% match confidence")
**And** maps to appropriate ConfidenceLevel
**And** explains factors affecting confidence

**Given** correlation analysis produces confidence
**When** aggregated result is returned
**Then** overall confidence reflects:
- Weakest link in source chain
- Corroboration boost (multiple sources agreeing)
- Conflict penalty (sources disagreeing)

**Given** tests exist
**When** I run `pytest tests/test_confidence.py`
**Then** all confidence calculation and language scenarios pass

---

### Story 8.2: Citation & Attribution System

As a **researcher**,
I want **complete source attribution with academic citation formatting**,
So that **I can verify sources and cite Ignifer output in my work**.

**Acceptance Criteria:**

**Given** all adapters return SourceMetadata
**When** I create `src/ignifer/citation.py`
**Then** `CitationFormatter` class provides:
- `format_inline(source: SourceMetadata) -> str` for inline citations
- `format_footnote(source: SourceMetadata) -> str` for footnotes
- `format_bibliography(sources: list[SourceMetadata]) -> str` for reference list
- `format_url_with_timestamp(source: SourceMetadata) -> str` for URL + retrieval date

**Given** a GDELT source is cited (FR29)
**When** formatted for rigor mode
**Then** includes:
- Full URL to source article/data
- Retrieval timestamp in ISO 8601
- Source name (GDELT)
- Data freshness indication

**Given** academic citation is requested (FR30)
**When** `CitationFormatter.format_bibliography()` is called
**Then** produces citations like:
```
GDELT Project. "Global Database of Events, Language, and Tone."
  Retrieved 2026-01-08T14:32:00Z from https://api.gdeltproject.org/...

World Bank. "World Development Indicators: Germany."
  Retrieved 2026-01-08T14:32:15Z from https://api.worldbank.org/...
```

**Given** multiple sources contribute to a finding
**When** citation is generated
**Then** lists all contributing sources
**And** indicates which source provided which data point
**And** notes corroboration or conflicts

**Given** source URL may change or expire
**When** citation is generated
**Then** includes retrieval timestamp prominently
**And** notes that data reflects point-in-time snapshot
**And** suggests archiving for permanent reference

**Given** tests exist
**When** I run `pytest tests/test_citation.py`
**Then** all citation format scenarios pass

---

### Story 8.3: Rigor Mode Integration

As a **power user**,
I want **to toggle rigor mode for enhanced analytical output**,
So that **I can get IC-standard products when I need them**.

**Acceptance Criteria:**

**Given** confidence and citation frameworks from Stories 8.1-8.2
**When** I update all tools in server.py
**Then** each tool accepts optional `rigor: bool = False` parameter
**And** rigor mode can be set globally via `IGNIFER_RIGOR_MODE` environment variable
**And** per-query parameter overrides global setting

**Given** rigor mode is enabled (FR27)
**When** any tool returns output
**Then** output includes:
- ICD 203 confidence levels with percentage ranges
- Full source attribution with URLs and timestamps
- Academic citation section at end
- Analytical caveats and limitations
- Source quality assessments

**Given** rigor mode is disabled (default)
**When** tools return output
**Then** output is clean and readable (FR26)
**And** source names are mentioned but not full URLs
**And** confidence is implied but not formally stated
**And** no citation section

**Given** user calls `briefing("Ukraine", rigor=True)`
**When** output is generated
**Then** includes:
- "We assess with moderate confidence (55-80%) that..."
- Per-paragraph source attribution
- Sources section with full URLs and timestamps
- Analytical limitations noted
- Citation-ready format

**Given** user sets global rigor mode preference (FR48)
**When** `IGNIFER_RIGOR_MODE=true` is set
**Then** all queries default to rigor mode
**And** can still be overridden with `rigor=False`

**Given** deep_dive is called with rigor mode
**When** multi-source analysis completes
**Then** each section includes source attribution
**And** corroboration/conflict is formally noted
**And** overall confidence assessment uses IC language
**And** complete bibliography is generated

**Given** entity matching is performed in rigor mode
**When** results are returned (FR31)
**Then** includes explicit match confidence: "Entity matched with 87% confidence (VERY_LIKELY) based on normalized name match via Wikidata Q-ID"

**Given** user needs TSUKUYOMI-style output (TR4, TR5, TR6)
**When** rigor mode is enabled
**Then** output follows structured OSINT methodology
**And** includes source triangulation notes
**And** follows IC-compliant formatting

---

## Epic 9: System Administration & Power Features

**Goal:** Power users have full control — check source status, manage cache, invoke tools directly, and customize source selection.

### Story 9.1: Source Status & Health Tool

As a **power user**,
I want **to check the status and health of all configured data sources**,
So that **I can diagnose issues and verify my configuration**.

**Acceptance Criteria:**

**Given** all adapters implement `health_check()` method
**When** I add `source_status(source: str = None)` tool to server.py
**Then** it:
- Lists all available sources if no source specified
- Checks specific source health if source name provided
- Reports API key configuration status
- Tests actual connectivity to source

**Given** user asks "What sources are available?"
**When** Claude calls `source_status()` (FR39, FR47)
**Then** returns formatted output including:
```
Source Status Report:
─────────────────────
GDELT        ✓ Available    (no auth required)
World Bank   ✓ Available    (no auth required)
Wikidata     ✓ Available    (no auth required)
OpenSky      ✓ Configured   (credentials valid)
AISStream    ✗ Not configured (API key missing)
ACLED        ✓ Configured   (credentials valid)
OpenSanctions ✓ Available   (no auth required)
```

**Given** user checks specific source
**When** Claude calls `source_status("opensky")`
**Then** returns detailed status:
- Configuration status (API key present/missing)
- Last health check result with timestamp
- Response time from last query
- Cache statistics for this source
- Rate limit status if applicable

**Given** API key is configured but invalid
**When** health check is performed
**Then** reports "Configured but authentication failed"
**And** does NOT expose the actual API key in output
**And** suggests checking credentials

**Given** source is temporarily unavailable
**When** health check fails
**Then** reports "Source unreachable" with error summary
**And** shows last successful contact time if cached
**And** suggests trying again later

**Given** tests exist
**When** I run `pytest tests/test_source_status.py`
**Then** all status scenarios pass with mocked adapters

---

### Story 9.2: Cache Management Tool

As a **power user**,
I want **to manage the cache for troubleshooting and freshness**,
So that **I can force fresh data or clear stale entries**.

**Acceptance Criteria:**

**Given** CacheManager from Epic 1
**When** I add `cache_control(action: str, source: str = None)` tool to server.py
**Then** it supports actions:
- `status`: Show cache statistics
- `clear`: Clear cache (all or specific source)
- `info`: Show cache configuration

**Given** user asks about cache status
**When** Claude calls `cache_control("status")` (FR40)
**Then** returns:
```
Cache Status:
─────────────
L1 Memory Cache: 47 entries, 2.3 MB
L2 SQLite Cache: 312 entries, 15.7 MB

By Source:
  GDELT:        89 entries, TTL 1h, oldest 45m
  World Bank:   23 entries, TTL 24h, oldest 18h
  Wikidata:    156 entries, TTL 7d, oldest 3d
  OpenSky:      12 entries, TTL 5m, oldest 3m
  ACLED:        32 entries, TTL 12h, oldest 8h
```

**Given** user wants to clear all cache
**When** Claude calls `cache_control("clear")`
**Then** clears both L1 and L2 cache
**And** reports number of entries cleared
**And** confirms cache is now empty

**Given** user wants to clear specific source cache
**When** Claude calls `cache_control("clear", source="gdelt")`
**Then** clears only GDELT entries from cache
**And** leaves other source data intact
**And** reports entries cleared for that source

**Given** user requests cache info
**When** Claude calls `cache_control("info")`
**Then** returns:
- Cache location (SQLite path)
- TTL configuration per source
- Maximum cache size settings
- Stale-while-revalidate policy

**Given** tests exist
**When** I run `pytest tests/test_cache_control.py`
**Then** all cache management scenarios pass

---

### Story 9.3: Source Selection Controls

As a **power user**,
I want **to include or exclude specific sources from my queries**,
So that **I can customize which data sources are consulted**.

**Acceptance Criteria:**

**Given** all query tools (briefing, deep_dive, etc.)
**When** I add `sources` parameter to relevant tools
**Then** parameter accepts:
- `include=["gdelt", "worldbank"]` - only use these sources
- `exclude=["acled"]` - use all except these
- Default: use all relevant available sources

**Given** user wants only specific sources (FR49)
**When** Claude calls `briefing("Iran", sources={"include": ["gdelt", "acled"]})`
**Then** queries only GDELT and ACLED
**And** ignores other sources even if relevant
**And** notes which sources were used in output

**Given** user wants to exclude a source
**When** Claude calls `deep_dive("Russia", sources={"exclude": ["opensanctions"]})`
**Then** queries all relevant sources except OpenSanctions
**And** notes exclusion in output for transparency

**Given** user specifies unavailable source
**When** `include` contains source without configured API key
**Then** returns warning about unavailable source
**And** proceeds with available sources from the list
**And** suggests configuring credentials

**Given** user excludes all relevant sources
**When** no sources remain after exclusion
**Then** returns error explaining no sources available
**And** suggests adjusting source selection

**Given** alternative query is suggested (FR50)
**When** primary query returns no results
**Then** suggests modified query with different sources
**And** user can accept or modify the suggestion
**And** provides reasoning for the alternative

---

### Story 9.4: Adapter Protocol Documentation & Extensibility

As a **contributor**,
I want **clear documentation for implementing new adapters**,
So that **I can extend Ignifer with additional data sources**.

**Acceptance Criteria:**

**Given** the OSINTAdapter protocol from Epic 1 (FR41)
**When** I create `docs/adapter-development.md`
**Then** documentation includes:
- Complete OSINTAdapter protocol specification
- Required methods and their signatures
- Error handling expectations
- Cache integration requirements
- Testing requirements

**Given** a developer wants to add a new source
**When** they follow the documentation
**Then** they can create a new adapter by:
1. Creating `src/ignifer/adapters/newsource.py`
2. Implementing `OSINTAdapter` protocol
3. Adding adapter-owned httpx client
4. Implementing query(), health_check(), close()
5. Adding to adapter registry
6. Adding tests in `tests/adapters/test_newsource.py`

**Given** documentation exists
**When** developer implements new adapter
**Then** adapter is automatically discovered
**And** included in source_status() output
**And** available for source selection
**And** integrated with cache system

**Given** adapter template exists
**When** I create `src/ignifer/adapters/_template.py`
**Then** it provides:
- Commented skeleton implementing protocol
- Example query implementation
- Example error handling
- Example cache integration
- Example test structure

**Given** adapter doesn't implement protocol correctly
**When** server starts
**Then** logs warning about non-conforming adapter
**And** excludes adapter from available sources
**And** continues operating with valid adapters

**Given** adapter has runtime error
**When** query is executed
**Then** error is contained to that adapter (NFR-I5)
**And** other adapters continue functioning
**And** user receives graceful error for failed source

---

## Epic 10: Visualization (Future - Phase 5)

**Goal:** Users can generate trend charts, geographic maps, and entity relationship graphs. **Deferred** per PRD scope.

**FRs covered:** FR42-45, FR51

*This epic is planned for Phase 5 and not detailed in this document.*
