---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'Free/Open OSINT Data Sources and APIs for Ignifer'
research_goals: 'Identify and evaluate available free OSINT sources across all categories (News/Events, Aviation, Maritime, Economic/Financial, Conflict/Security, Entity/People, Social Media) with deep dives on top candidates for building a Python MCP server Claude Desktop extension'
user_name: 'Scott'
date: '2026-01-08'
web_research_enabled: true
source_verification: true
---

# Technical Research Report: Free/Open OSINT Data Sources and APIs

**Date:** 2026-01-08
**Author:** Scott
**Research Type:** Technical
**Project:** Ignifer - OSINT Claude Desktop Extension

---

## Research Overview

This research evaluates free and open-source OSINT (Open Source Intelligence) data sources and APIs for integration into Ignifer, a Python MCP server extension for Claude Desktop. The goal is to identify top candidates across all major OSINT categories with deep technical evaluation of capabilities, limitations, and integration patterns.

---

## Technical Research Scope Confirmation

**Research Topic:** Free/Open OSINT Data Sources and APIs for Ignifer
**Research Goals:** Identify and evaluate available free OSINT sources across all categories (News/Events, Aviation, Maritime, Economic/Financial, Conflict/Security, Entity/People, Social Media) with deep dives on top candidates for building a Python MCP server Claude Desktop extension

**Technical Research Scope:**

- Data Source Evaluation - capabilities, coverage, data freshness, reliability
- API Architecture - REST/GraphQL patterns, authentication, rate limits
- Integration Patterns - Python client libraries, SDK availability, raw API access
- Data Formats - JSON, CSV, GeoJSON, streaming formats
- Performance Considerations - rate limits, bulk access, caching strategies

**Research Methodology:**

- Current web data with rigorous source verification
- Multi-source validation for critical technical claims
- Confidence level framework for uncertain information
- Comprehensive technical coverage with Python integration focus

**Scope Confirmed:** 2026-01-08

---

## Technology Stack Analysis: OSINT Data Sources by Category

### 1. News & Global Events

#### GDELT (Global Database of Events, Language, and Tone) ⭐ TOP PICK

**Overview:** The largest, most comprehensive, and highest resolution open database of human society ever created. GDELT monitors print, broadcast, and web news media in over 100 languages from across every country, with archives back to 1979 and updates every 15 minutes.

**API Access:**
- **GDELT DOC 2.0 API** - Rolling 3-month window of articles
- **BigQuery** - Full historical access at limitless scale
- **Direct Downloads** - Raw datafiles available

**Python Libraries:**
| Library | Purpose | Status |
|---------|---------|--------|
| [gdeltPyR](https://github.com/linwoodc3/gdeltPyR) | Full GDELT 1.0/2.0 access, Pandas integration | Active |
| [gdelt-doc-api](https://github.com/alex9smith/gdelt-doc-api) | DOC 2.0 API client for small-scale analysis | Active |
| [newsfeed](https://pypi.org/project/newsfeed/) | Continuous querying with time-range splitting | Active |

**Key Features:**
- 65 machine-translated languages (98.4% of non-English coverage)
- Visual Global Knowledge Graph (VGKG) for image search
- Entity extraction, tone analysis, event coding
- Completely free and open

**Rate Limits:** No explicit limits documented for API; BigQuery has Google Cloud quotas
**Data Format:** JSON, CSV via API; various formats via download
**Confidence:** [High] - Well-documented, actively maintained

_Sources: [GDELT Project](https://www.gdeltproject.org/data.html), [gdeltPyR GitHub](https://github.com/linwoodc3/gdeltPyR), [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)_

#### Alternative News APIs

| API | Free Tier | Coverage | Notes |
|-----|-----------|----------|-------|
| [NewsAPI.org](https://newsapi.org/) | Limited | 50k+ sources, 50 countries | 14 languages supported |
| [Mediastack](https://mediastack.com/) | Yes | 50+ countries, 13 languages | REST API, JSON format |
| [NewsAPI.ai](https://newsapi.ai/) | Trial (2000 searches) | 150k+ publishers | Formerly Event Registry; NLP/AI features |

---

### 2. Aviation Tracking

#### OpenSky Network ⭐ TOP PICK (Free)

**Overview:** Community-driven ADS-B/Mode S/MLAT network providing live and historical aircraft position data for research and non-commercial purposes.

**API Access:**
- REST API with OAuth2 authentication (required for new accounts since March 2025)
- Historical data access for registered users
- Live state vectors for all tracked aircraft

**Python Libraries:**
| Library | Purpose | Status |
|---------|---------|--------|
| [opensky-api](https://openskynetwork.github.io/opensky-api/python.html) | Official Python bindings | Active (Nov 2025) |
| [pyopensky](https://github.com/open-aviation/pyopensky) | Enhanced interface for live/historical data | Active |

**Rate Limits:**
- Anonymous: 400 API credits/day
- Registered: 4000 API credits/day
- Data up to 1 hour in past; 5-second resolution

**Authentication:** OAuth2 client credentials flow (required for accounts created after March 2025)
**Data Format:** JSON
**Confidence:** [High] - Official documentation, active development

_Sources: [OpenSky API Documentation](https://openskynetwork.github.io/opensky-api/), [pyopensky GitHub](https://github.com/open-aviation/pyopensky)_

#### ADS-B Exchange (Paid as of 2025)

**Status Change:** As of March 2025, ADS-B Exchange discontinued free API access. Now requires paid subscription via RapidAPI.

**Why It Matters:** ADS-B Exchange provides *unfiltered* flight data including blocked tail numbers not visible on other platforms - valuable for OSINT on private/government aircraft.

**Pricing:** Basic plan ~10,000 requests/month via RapidAPI subscription
**Confidence:** [High] - Confirmed March 2025 pricing change

_Sources: [ADS-B Exchange](https://www.adsbexchange.com/), [ADS-B Exchange Data Access](https://www.adsbexchange.com/data/)_

---

### 3. Maritime Tracking (AIS)

#### AISStream.io ⭐ TOP PICK

**Overview:** Free API to stream global AIS data via WebSockets, using a worldwide network of receiving stations.

**API Features:**
- Real-time WebSocket streaming
- Filter by MMSI list or message types
- OpenAPI 3.0 schema definitions
- Vessel position, identity, port calls

**Integration Pattern:**
```python
# WebSocket connection for real-time AIS data
# Filter by MMSI or message type in subscription
```

**Data Format:** JSON via WebSocket
**Rate Limits:** Not explicitly documented (free tier)
**Confidence:** [High] - Active GitHub presence

_Sources: [AISStream.io](https://aisstream.io/), [AISStream GitHub](https://github.com/aisstream/aisstream)_

#### AISHub (Data Exchange Model)

**Model:** Contribute AIS data from your receiver → receive aggregated global feed
**Formats:** JSON, XML, CSV
**Best For:** Users with their own AIS receiving equipment

_Source: [AISHub](https://www.aishub.net/)_

#### Commercial Options (Reference)
- **MarineTraffic** - Freemium web interface; API requires paid subscription
- **Datalastic** - Commercial vessel API with historical data

---

### 4. Economic & Financial Data

#### World Bank API ⭐ TOP PICK

**Overview:** Free and open access to global development data across 63+ databases with 17,500+ indicators.

**Python Libraries:**
| Library | Purpose | Recommendation |
|---------|---------|----------------|
| [wbgapi](https://pypi.org/project/wbgapi/) | Modern, Pythonic access; handles API quirks | ⭐ Recommended |
| [wbdata](https://wbdata.readthedocs.io/) | Simple interface with metadata support | Good alternative |
| [world_bank_data](https://pypi.org/project/world-bank-data/) | API v2 implementation, speed-focused | Speed-optimized |

**Key Features:**
- World Development Indicators (primary database)
- Automatic request chunking for large queries
- Returns pandas DataFrames or dictionaries
- No authentication required

**Rate Limits:** Generous; library handles chunking automatically
**Data Format:** JSON, XML
**Confidence:** [High] - Official World Bank support

_Sources: [World Bank Open Data](https://data.worldbank.org/), [wbgapi PyPI](https://pypi.org/project/wbgapi/), [wbgapi GitHub](https://github.com/tgherzog/wbgapi)_

#### UN OCHA Humanitarian Data Exchange (HDX)

**Overview:** Open platform for sharing humanitarian data with 18,110+ datasets from 254 locations.

**APIs Available:**
- **HDX CKAN API** - General purpose, all datasets
- **HDX HAPI** - Curated standardized humanitarian indicators

**Python Library:** [hdx-python-api](https://github.com/OCHA-DAP/hdx-python-api)

**Data Coverage:** Crisis data, humanitarian operations, displacement, food security
**Confidence:** [High] - UN-backed, actively maintained

_Sources: [HDX Platform](https://data.humdata.org/), [HDX Python API GitHub](https://github.com/OCHA-DAP/hdx-python-api)_

---

### 5. Conflict & Security Data

#### ACLED (Armed Conflict Location & Event Data) ⭐ TOP PICK

**Overview:** Disaggregated data on political violence and protest events worldwide, from 1997 to present with real-time updates.

**Data Access:**
- Data Export Tool (registration required)
- API access with API key
- Weekly updated curated datasets

**Coverage:**
- Global coverage (all countries since 2021)
- 45+ variables per event; 120+ for recent events
- Event types: battles, violence against civilians, explosions, protests

**Tools:**
- **ACLED Explorer** - Filter by location, actor, event type
- **CAST** - Conflict Alert System with 6-week forecasts
- **Early Warning Dashboard** (2025) - Integrated risk tools

**Rate Limits:** Registration required; API key-based access
**Data Format:** CSV, Excel
**Confidence:** [High] - Academic standard, widely cited

_Sources: [ACLED](https://acleddata.com/), [ACLED Data Access](https://acleddata.com/conflict-data/)_

#### Global Terrorism Database (GTD)

**Status:** Registration required; no public API (download only)
**Coverage:** 1970-2020, 200,000+ incidents
**Limitation:** Closed access model as of 2025; requires personal information to request use

_Source: [START GTD](https://www.start.umd.edu/data-tools/GTD)_

---

### 6. Entity & People Intelligence

#### OpenSanctions ⭐ TOP PICK

**Overview:** Open-source database aggregating sanctions data, politically exposed persons (PEPs), and entities of interest from 269 dataset collections.

**API Access:**
- Search API for entity lookup
- Batch screening for compliance
- Pay-as-you-go or bulk data license

**Python Package:** [opensanctions](https://pypi.org/project/opensanctions/)
**Data Model:** Follow the Money (FtM) JSON-based anti-corruption data model

**Licensing:**
- **Free:** Non-commercial use
- **Paid:** Commercial/business use

**Coverage:** 269 datasets; 28 countries for PEPs + EU dataset
**Data Format:** JSON (FtM schema)
**Confidence:** [High] - Active development, Bellingcat recommended

_Sources: [OpenSanctions API](https://www.opensanctions.org/api/), [OpenSanctions GitHub](https://github.com/opensanctions/opensanctions)_

#### Wikidata ⭐ TOP PICK (Completely Free)

**Overview:** Free, multilingual knowledge graph with 100M+ items of structured data on people, places, organizations, and concepts.

**Query Access:**
- SPARQL endpoint: `https://query.wikidata.org/sparql`
- REST API for entity retrieval
- No authentication required

**Python Libraries:**
| Library | Purpose |
|---------|---------|
| [SPARQLWrapper](https://pypi.org/project/SPARQLWrapper/) | General SPARQL queries |
| [qwikidata](https://qwikidata.readthedocs.io/) | Pythonic entity representation |
| [WikidataIntegrator](https://github.com/SuLab/WikidataIntegrator) | Full integration with SPARQL |

**Entity System:** Q-IDs for items (e.g., Q30 = United States), P-IDs for properties
**Rate Limits:** Fair use policy; no hard limits for reasonable queries
**Confidence:** [High] - Wikimedia Foundation backed

_Sources: [Wikidata Data Access](https://www.wikidata.org/wiki/Wikidata:Data_access), [Wikidata SPARQL](https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service)_

---

### 7. Social Media & Alternative OSINT

#### Python OSINT Frameworks

| Tool | Purpose | GitHub Stars |
|------|---------|--------------|
| [Sherlock](https://github.com/sherlock-project/sherlock) | Username search across 300+ platforms | 60k+ |
| [Holehe](https://github.com/megadose/holehe) | Email registration check across sites | 9.8k |
| [theHarvester](https://github.com/laramies/theHarvester) | Email, subdomain, IP harvesting | 12k+ |
| [SpiderFoot](https://github.com/smicallef/spiderfoot) | 200+ module OSINT automation | 13k+ |
| [PhoneInfoga](https://github.com/sundowndev/phoneinfoga) | Phone number intelligence | 13k+ |
| [Recon-ng](https://github.com/lanmaster53/recon-ng) | Modular web reconnaissance framework | 10k+ |

#### Additional Resources

- **OSINT Framework** (osintframework.com) - Curated directory of free OSINT tools
- **awesome-osint** (GitHub) - Comprehensive OSINT resource list
- **IntelOwl** - Threat intelligence management platform

**Confidence:** [High] - Active open-source communities

_Sources: [OSINT Framework](https://osintframework.com/), [awesome-osint GitHub](https://github.com/jivoi/awesome-osint)_

---

## Integration Patterns Analysis

### MCP Server Architecture for Ignifer

#### Model Context Protocol Overview

MCP (Model Context Protocol) is Anthropic's open standard enabling secure two-way connections between data sources and AI tools. The architecture consists of:

| Component | Role in Ignifer |
|-----------|-----------------|
| **Host** | Claude Desktop application |
| **MCP Client** | Connector within Claude Desktop (1:1 session) |
| **MCP Server** | Ignifer Python server exposing OSINT tools |
| **Tools** | Functions callable by Claude (query APIs, analyze data) |
| **Resources** | Data sources (cached results, knowledge bases) |

**Python SDK:** [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)

**Server Capabilities:**
- **Tools** - Functions callable by LLM with user approval
- **Resources** - File-like data readable by clients
- **Prompts** - Pre-written templates for common OSINT tasks

**Configuration:** `~/Library/Application Support/Claude/claude_desktop_config.json`

_Sources: [MCP Official Docs](https://modelcontextprotocol.io/quickstart/server), [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)_

---

### API Integration Patterns

#### Async HTTP Client Selection

| Library | Best For | HTTP/2 | Async | Notes |
|---------|----------|--------|-------|-------|
| **httpx** | General use, mixed sync/async | Yes | Yes | Django REST framework author; recommended |
| **aiohttp** | High-concurrency, WebSocket | No | Only | Better raw performance; WebSocket native |

**Recommendation for Ignifer:** Use **httpx** as primary HTTP client for REST APIs (GDELT, World Bank, ACLED, OpenSky) and **aiohttp** for WebSocket connections (AISStream).

**Pattern: Async Client Session**
```python
async with httpx.AsyncClient() as client:
    results = await asyncio.gather(
        client.get(gdelt_url),
        client.get(worldbank_url),
        client.get(acled_url)
    )
```

**Performance:** Using asyncio + aiohttp reduced 27K API calls from 2.5 hours to ~7 minutes in benchmark tests.

_Sources: [HTTPX Async Docs](https://www.python-httpx.org/async/), [aiohttp GitHub](https://github.com/aio-libs/aiohttp)_

---

### WebSocket Integration (Real-Time Data)

#### Pattern for AISStream Maritime Data

**Library:** `websockets` (asyncio-native, high-concurrency optimized)

**Key Patterns:**

| Pattern | Use Case |
|---------|----------|
| **Async Context Manager** | `async with connect(...) as ws` - auto-cleanup |
| **Auto-Reconnect Iterator** | `async for ws in connect(...)` - resilient connection |
| **Message Queue** | Buffer messages during processing to prevent backpressure |

**Production Considerations:**
- Message queue with size limits prevents memory exhaustion
- Auto-reconnect handles network instability
- Single process can handle thousands of concurrent connections

_Sources: [websockets Documentation](https://websockets.readthedocs.io/), [Asyncio WebSocket Clients](https://superfastpython.com/asyncio-websocket-clients/)_

---

### Data Aggregation & Normalization

#### OSINT Data Pipeline Architecture

**Recommended: Lambda Architecture Pattern**
- **Batch Layer:** Historical analysis (GDELT archives, ACLED historical)
- **Stream Layer:** Real-time updates (AISStream, OpenSky live)
- **Serving Layer:** Unified query interface for Claude

**Normalization Pipeline:**

```
Raw Data → Extraction → Standardization → Correlation → Enrichment → Output
```

| Stage | Purpose |
|-------|---------|
| **Extraction** | Pull atomic attributes from each source |
| **Standardization** | Normalize formats, timestamps, entity names |
| **Correlation** | Link entities across sources (Wikidata IDs) |
| **Enrichment** | Add context (OpenSanctions flags, economic indicators) |
| **Output** | Unified JSON for Claude consumption |

**Entity Resolution:** Use Wikidata Q-IDs as canonical identifiers to link entities across:
- News articles (GDELT)
- Sanctions lists (OpenSanctions)
- Economic data (World Bank)
- Conflict events (ACLED)

_Sources: [MDPI - Automated OSINT Techniques](https://www.mdpi.com/2073-431X/14/10/430), [ETIP Platform Research](https://www.researchgate.net/publication/349585768_ETIP)_

---

### Rate Limiting & Resilience

#### Multi-Source Rate Limiting Strategy

**Libraries:**
| Library | Purpose |
|---------|---------|
| [ratelimit](https://pypi.org/project/ratelimit/) | Decorator-based rate limiting |
| [tenacity](https://pypi.org/project/tenacity/) | Retry with exponential backoff |
| [backoff](https://pypi.org/project/backoff/) | Exponential backoff decorator |

**Pattern: Exponential Backoff with Jitter**
```python
@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(5))
async def fetch_with_retry(url):
    ...
```

**Per-Source Rate Limits:**

| Source | Rate Limit | Strategy |
|--------|------------|----------|
| OpenSky | 4000/day (registered) | Token bucket, daily reset |
| ACLED | API key based | Per-key tracking |
| World Bank | Generous | Chunking handled by library |
| GDELT | No explicit limit | Respect server response |
| Wikidata | Fair use | Batch queries, cache results |

**429 Handling:**
1. Check `Retry-After` header
2. Fall back to exponential backoff with jitter
3. Limit retries to 3-5 attempts
4. Log and surface persistent failures

_Sources: [OpenAI Rate Limit Cookbook](https://cookbook.openai.com/examples/how_to_handle_rate_limits), [tenacity docs](https://tenacity.readthedocs.io/)_

---

### Caching Strategy

#### Multi-Tier Cache Architecture

| Tier | Storage | TTL | Use Case |
|------|---------|-----|----------|
| **L1** | In-memory (dict/lru_cache) | 5-15 min | Hot queries, session data |
| **L2** | SQLite/Redis | 1-24 hours | API responses, entity data |
| **L3** | File system | Days-weeks | Historical datasets, bulk downloads |

**Cache Invalidation by Source:**

| Source | Recommended TTL | Rationale |
|--------|-----------------|-----------|
| OpenSky (live) | 10-30 seconds | Real-time aircraft positions |
| AISStream | No cache (streaming) | Real-time vessel data |
| GDELT | 15-60 minutes | Updates every 15 min |
| World Bank | 24+ hours | Indicators update monthly/yearly |
| ACLED | 1-24 hours | Weekly batch updates |
| OpenSanctions | 24+ hours | Daily/weekly updates |
| Wikidata | 24+ hours | Entity data relatively stable |

---

### Security Patterns

#### API Key Management

**Pattern: Environment Variables + Secrets Manager**
```python
# .env file (gitignored)
ACLED_API_KEY=xxx
OPENSKY_CLIENT_ID=xxx
OPENSKY_CLIENT_SECRET=xxx
```

**OAuth2 Flow (OpenSky):**
- New accounts (post-March 2025) require OAuth2 client credentials
- Store client_id/client_secret securely
- Token refresh handled automatically

**MCP Security:**
- Claude Desktop enforces consent/authorization
- Tools require user approval before execution
- No automatic credential exposure to LLM

---

### Recommended Ignifer Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Claude Desktop                      │
│                   (MCP Host)                         │
└─────────────────────┬───────────────────────────────┘
                      │ MCP Protocol (stdio/SSE)
┌─────────────────────▼───────────────────────────────┐
│              Ignifer MCP Server                      │
│  ┌─────────────────────────────────────────────┐    │
│  │            Tool Handlers                     │    │
│  │  • analyze_event()  • track_vessel()        │    │
│  │  • briefing()       • deep_dive()           │    │
│  │  • entity_lookup()  • trend_analysis()      │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │         Data Aggregation Layer              │    │
│  │  • Normalization  • Entity Resolution       │    │
│  │  • Correlation    • Confidence Scoring      │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │         Source Adapters (async)             │    │
│  │  ┌──────┐ ┌───────┐ ┌─────────┐ ┌───────┐  │    │
│  │  │GDELT │ │OpenSky│ │AISStream│ │ ACLED │  │    │
│  │  └──────┘ └───────┘ └─────────┘ └───────┘  │    │
│  │  ┌──────────┐ ┌────────┐ ┌──────────────┐  │    │
│  │  │WorldBank │ │Wikidata│ │OpenSanctions │  │    │
│  │  └──────────┘ └────────┘ └──────────────┘  │    │
│  └─────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │         Cache Layer (SQLite/Redis)          │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**Confidence:** [High] - Based on MCP SDK patterns and established async Python practices

---

## Executive Summary

### Research Overview

This technical research evaluated free and open-source OSINT data sources for **Ignifer**, a Claude Desktop MCP extension designed to provide geopolitical analysis capabilities. The research covered 7 major OSINT categories, identified top candidates in each, and designed an integration architecture optimized for Python MCP servers.

### Key Findings

**1. Viable Free OSINT Ecosystem Exists**

A robust ecosystem of free, high-quality OSINT APIs is available for all target categories:

| Category | Top Source | Quality | Python Support |
|----------|------------|---------|----------------|
| News/Events | GDELT | Excellent | gdeltPyR, gdelt-doc-api |
| Aviation | OpenSky Network | Good | pyopensky (official) |
| Maritime | AISStream.io | Good | WebSocket (native) |
| Economic | World Bank | Excellent | wbgapi |
| Humanitarian | UN OCHA HDX | Excellent | hdx-python-api |
| Conflict | ACLED | Excellent | REST API |
| Entities | OpenSanctions + Wikidata | Good/Excellent | opensanctions, SPARQLWrapper |

**2. Architecture is Well-Defined**

The MCP Python SDK provides a mature foundation. The recommended architecture uses:
- **httpx** for async REST API calls
- **websockets** for real-time streaming (AIS)
- **Lambda architecture** for batch + stream processing
- **Wikidata Q-IDs** for cross-source entity resolution

**3. Key Constraint: Rate Limits**

Free tier rate limits are the primary constraint:
- OpenSky: 4,000 requests/day (registered)
- ACLED: API key required
- Wikidata: Fair use policy

Mitigation: Multi-tier caching + intelligent request batching.

**4. 2025 Landscape Change**

ADS-B Exchange moved to paid model (March 2025). OpenSky Network is now the primary free aviation source. Unfiltered data (blocked tail numbers) requires paid subscription.

---

## Implementation Roadmap

### Phase 1: Foundation (MVP)

**Goal:** Working MCP server with 3 core data sources

| Component | Implementation |
|-----------|----------------|
| MCP Server | FastMCP framework, stdio transport |
| Data Sources | GDELT, World Bank, Wikidata |
| Tools | `briefing()`, `entity_lookup()`, `economic_indicator()` |
| Cache | SQLite (simple, no external deps) |

**Deliverables:**
- [ ] MCP server skeleton with tool registration
- [ ] GDELT adapter (news/events queries)
- [ ] World Bank adapter (economic indicators)
- [ ] Wikidata adapter (entity enrichment)
- [ ] Basic SQLite cache layer
- [ ] Claude Desktop integration tested

**Dependencies:**
```
mcp
httpx
gdeltPyR
wbgapi
SPARQLWrapper
pydantic
```

### Phase 2: Real-Time & Tracking

**Goal:** Add aviation and maritime tracking

| Component | Implementation |
|-----------|----------------|
| Aviation | OpenSky Network (OAuth2 flow) |
| Maritime | AISStream.io (WebSocket) |
| Tools | `track_flight()`, `track_vessel()`, `airspace_scan()` |

**Deliverables:**
- [ ] OpenSky adapter with OAuth2 authentication
- [ ] AISStream WebSocket client with auto-reconnect
- [ ] Flight tracking tool
- [ ] Vessel tracking tool
- [ ] Rate limit management per source

**New Dependencies:**
```
pyopensky
websockets
tenacity
```

### Phase 3: Conflict & Security Intelligence

**Goal:** Add conflict data and sanctions screening

| Component | Implementation |
|-----------|----------------|
| Conflict | ACLED API integration |
| Sanctions | OpenSanctions bulk data |
| Humanitarian | UN OCHA HDX |
| Tools | `conflict_analysis()`, `sanctions_check()`, `crisis_briefing()` |

**Deliverables:**
- [ ] ACLED adapter (requires registration)
- [ ] OpenSanctions local database (Follow the Money schema)
- [ ] HDX adapter for humanitarian data
- [ ] Conflict analysis tools
- [ ] Entity screening against sanctions lists

**New Dependencies:**
```
opensanctions
hdx-python-api
```

### Phase 4: Analysis & Rigor Mode

**Goal:** Advanced analysis with IC-standard confidence levels

| Component | Implementation |
|-----------|----------------|
| Correlation | Cross-source entity linking |
| Confidence | ICD 203-style confidence scoring |
| Output | Structured reports with source attribution |
| Tools | `deep_dive()`, `trend_analysis()`, `correlation_map()` |

**Deliverables:**
- [ ] Entity resolution engine (Wikidata-based)
- [ ] Confidence scoring framework
- [ ] Source quality assessment
- [ ] Rigor mode toggle for detailed attribution
- [ ] Trend visualization helpers

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API rate limits exceeded | Medium | High | Multi-tier caching, request batching |
| OpenSky OAuth2 complexity | Low | Medium | Use official pyopensky library |
| WebSocket connection instability | Medium | Medium | Auto-reconnect with backoff |
| Data source API changes | Low | High | Adapter abstraction layer |
| Cache invalidation bugs | Medium | Low | Conservative TTLs, manual refresh option |

### Dependency Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GDELT service disruption | Low | High | Cache historical data, fallback to NewsAPI |
| OpenSky registration required | Certain | Low | Document registration in setup |
| ACLED registration required | Certain | Low | Document registration in setup |
| Free tier deprecation | Low | Medium | Monitor announcements, design for paid fallback |

### Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API key exposure | Low | High | Environment variables, .gitignore |
| Excessive API costs (if upgraded) | Low | Medium | Usage monitoring, alerts |
| Data accuracy issues | Medium | Medium | Multi-source verification, confidence flags |

---

## Strategic Recommendations

### 1. Start with GDELT + World Bank + Wikidata

These three sources provide:
- **GDELT:** Event detection, news coverage, entity extraction
- **World Bank:** Economic context (17,500+ indicators)
- **Wikidata:** Entity enrichment, canonical IDs

All are completely free with no registration required (except BigQuery for GDELT historical).

### 2. Register Early for Rate-Limited Sources

Register now for:
- **OpenSky Network** - OAuth2 credentials for 10x rate limit increase
- **ACLED** - API key for conflict data access
- **OpenSanctions** - Free for non-commercial use

### 3. Design for Rigor Mode from Day One

Build the confidence scoring and source attribution infrastructure early:
- Tag every data point with source URL
- Track data freshness (timestamp of retrieval)
- Design output schemas with optional `rigor_details` field

### 4. Cache Aggressively

Given rate limits, cache everything:
- **Hot cache (memory):** 15-minute TTL for live queries
- **Warm cache (SQLite):** 24-hour TTL for entity data
- **Cold cache (files):** Bulk datasets (OpenSanctions, ACLED historical)

### 5. Abstract Data Sources Behind Adapters

Create a consistent adapter interface:
```python
class OSINTAdapter(Protocol):
    async def query(self, params: QueryParams) -> OSINTResult
    def get_confidence(self) -> ConfidenceLevel
    def get_source_url(self) -> str
```

This allows swapping sources (e.g., OpenSky → ADS-B Exchange paid) without changing tool logic.

---

## Future Opportunities

### Near-Term Enhancements
- **Telegram/Social Media:** Add social media monitoring (subject to ToS)
- **Satellite Imagery Metadata:** Sentinel Hub, NASA Earthdata
- **Financial Markets:** FRED, Alpha Vantage free tiers

### Advanced Capabilities
- **Predictive Analysis:** Leverage ACLED's CAST forecasting
- **Network Visualization:** Entity relationship graphs
- **Alert System:** Configurable triggers for events of interest

### Community & Ecosystem
- **Open Source Release:** Publish on GitHub for community contributions
- **MCP Registry:** Submit to official MCP server registry
- **Plugin Architecture:** Allow community-contributed data source adapters

---

## Conclusion

Ignifer is highly feasible as a free, open-source OSINT assistant for Claude Desktop. The research confirms:

1. **All target OSINT categories have viable free data sources** with Python library support
2. **MCP architecture is mature** and well-suited for this use case
3. **Rate limits are manageable** with proper caching and batching
4. **Rigor mode (IC-standard confidence levels)** can be implemented as an optional layer

**Recommended Next Step:** Begin Phase 1 implementation with GDELT, World Bank, and Wikidata integration.

---

## Source Documentation

### Primary Sources Consulted

| Source | URL | Data Retrieved |
|--------|-----|----------------|
| GDELT Project | https://www.gdeltproject.org/ | 2026-01-08 |
| OpenSky Network | https://opensky-network.org/ | 2026-01-08 |
| AISStream.io | https://aisstream.io/ | 2026-01-08 |
| World Bank Open Data | https://data.worldbank.org/ | 2026-01-08 |
| ACLED | https://acleddata.com/ | 2026-01-08 |
| OpenSanctions | https://www.opensanctions.org/ | 2026-01-08 |
| Wikidata | https://www.wikidata.org/ | 2026-01-08 |
| UN OCHA HDX | https://data.humdata.org/ | 2026-01-08 |
| MCP Python SDK | https://github.com/modelcontextprotocol/python-sdk | 2026-01-08 |

### Python Libraries Evaluated

| Library | PyPI | Purpose |
|---------|------|---------|
| gdeltPyR | https://pypi.org/project/gdelt/ | GDELT access |
| pyopensky | https://github.com/open-aviation/pyopensky | OpenSky Network |
| wbgapi | https://pypi.org/project/wbgapi/ | World Bank data |
| opensanctions | https://pypi.org/project/opensanctions/ | Sanctions data |
| hdx-python-api | https://github.com/OCHA-DAP/hdx-python-api | Humanitarian data |
| SPARQLWrapper | https://pypi.org/project/SPARQLWrapper/ | Wikidata queries |
| httpx | https://www.python-httpx.org/ | Async HTTP |
| websockets | https://websockets.readthedocs.io/ | WebSocket client |
| tenacity | https://tenacity.readthedocs.io/ | Retry/backoff |
| mcp | https://github.com/modelcontextprotocol/python-sdk | MCP server |

---

**Research Completed:** 2026-01-08
**Document Status:** Final
**Confidence Level:** High - All claims verified with current sources
**Author:** Scott (with Mary, Business Analyst)

---
