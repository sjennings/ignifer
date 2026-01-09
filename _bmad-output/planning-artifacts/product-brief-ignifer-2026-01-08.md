---
stepsCompleted: [1, 2, 3, 4, 5, 6]
workflowStatus: complete
inputDocuments:
  - technical-osint-apis-research-2026-01-08.md
  - _reference/TSUKUYOMI (framework architecture reference)
date: 2026-01-08
author: Scott
project: Ignifer
partyModeInsights: true
---

# Product Brief: Ignifer

**The Flaming Sword of Intelligence**

An open-source OSINT assistant for Claude Desktop that analyzes global events using intelligence community patterns and free data sources.

**One-liner:** *"Ignifer is a conversational OSINT layer for Claude - you talk about the world, Claude now has eyes across seven intelligence domains."*

---

## Vision Statement

Ignifer democratizes intelligence analysis by bringing IC-standard analytical rigor to curious geopolitical enthusiasts, researchers, and journalists through a Claude Desktop extension. Like a flaming sword cutting through the fog of information, Ignifer illuminates global events with verified, multi-source intelligence.

---

## Party Mode Insights (Team Discussion)

The following decisions were crystallized through multi-agent discussion:

| Aspect | Decision |
|--------|----------|
| **Primary Interface** | Natural language - Claude routes to tools semantically |
| **Secondary Interface** | Explicit menu/commands for power users |
| **Rigor Approach** | Progressive reveal - always present, never intrusive |
| **Tool Naming** | Verb-forward, intent-based (not implementation-based) |
| **Maritime Strategy** | Historical queries for MVP; defer real-time to Phase 2 |
| **WebSocket Risk** | Validate MCP with REST sources first |
| **Paid Sources** | None official; plugin architecture for community extensions |
| **Onboarding** | Zero-config, no tutorial - just ask questions |
| **Output Format** | Clean summary + expandable rigor details |

### Design Principles (from Party Mode)

1. **Zero-config to first insight** - No API key setup before seeing value
2. **Transparency without friction** - Rigor is always present, never in the way
3. **The interface is conversation** - Natural language as primary, menus as power-user escape hatch
4. **Verb-forward tool naming** - `briefing()`, `track_vessel()`, not `get_gdelt_data()`
5. **Progressive disclosure in output** - Clean summary first, expandable rigor details

---

## Problem Statement

### The Information Fog

Global events unfold across dozens of data sources - news feeds, flight trackers, vessel movements, economic indicators, conflict databases, and sanctions lists. Understanding these events requires:

1. **Access** - Knowing which data sources exist and how to query them
2. **Correlation** - Connecting dots across disparate sources
3. **Verification** - Assessing source quality and confidence
4. **Context** - Understanding historical patterns and relationships
5. **Synthesis** - Producing actionable intelligence from raw data

### Current State

- **Professional analysts** have access to classified systems and expensive commercial tools
- **Enthusiasts** must manually navigate dozens of websites and APIs
- **Journalists** lack systematic verification frameworks
- **Researchers** spend more time on data collection than analysis

### The Gap

No free, integrated tool exists that provides:
- Multi-source OSINT aggregation
- IC-standard analytical rigor (optional)
- Accessible interface for non-professionals
- Transparent source attribution

---

## Solution: Ignifer

A Python MCP server extension for Claude Desktop that provides structured access to free OSINT data sources with optional intelligence-grade rigor.

### Core Concept

Ignifer is modeled after TSUKUYOMI, an advanced modular intelligence framework, adapted for:
- Free/open data sources only
- Claude Desktop MCP integration
- Enthusiast-friendly with professional depth available

### Architecture Inspiration (TSUKUYOMI)

| TSUKUYOMI Pattern | Ignifer Implementation |
|-------------------|----------------------|
| Modular `.tsukuyomi` modules | Python source adapters |
| Intelligence orchestration core | MCP server with tool handlers |
| Personality cores (stakeholder adaptation) | Output modes (Briefing/Deep Dive/Rigor) |
| Source correlation matrix | Cross-source entity linking |
| IC-standard confidence (ICD 203/206) | Optional "Rigor Mode" |
| Multi-domain fusion | OSINT category integration |

---

## Target Users (Refined)

### Primary User: The Geopolitical Enthusiast

**Persona: Alex**
- **Demographics:** 35, software engineer, urban professional
- **Context:** Spends evenings and weekends following global events. Technically capable but not an intelligence professional.

**Current Behavior:**
- Bounces between Twitter/X, Reddit (r/geopolitics, r/credibledefense), FlightRadar24, MarineTraffic, various news sites
- Manually correlates information across sources
- Frustrated by paywalls, fragmented data, unverified claims
- Wants to understand *what's actually happening* beyond headlines

**Pain Points:**
- "I saw a ship mentioned in the news but can't find where it went"
- "Is this Twitter account's claim actually true?"
- "I spend hours piecing together what a professional analyst could see in minutes"
- "I don't know what I don't know"

**Jobs to Be Done:**
- Get a quick briefing on a developing situation
- Track specific vessels, aircraft, or entities of interest
- Verify claims with actual data sources
- Understand economic and conflict context for regions
- Feel informed, not overwhelmed

**Success Moment:**
Alex asks Claude "What's the situation with grain shipments from Ukraine this week?" and gets a coherent briefing pulling from GDELT news, AISStream vessel data, and World Bank trade indicators - with sources cited. No tab-switching. No manual correlation. Just answers.

**Value Proposition:** *"Finally, I can ask about the world and get real answers backed by real data."*

---

### Secondary User: The Independent Researcher

**Persona: Maya**
- **Demographics:** 28, graduate student in international relations / freelance journalist
- **Context:** Writes analysis pieces, needs citable sources, operates on limited budget

**Current Behavior:**
- Uses academic databases, government reports, ACLED for research
- Manually builds entity timelines and relationship maps
- Needs proper attribution for publication
- Can't afford Bloomberg/Refinitiv/Palantir

**Pain Points:**
- "I need to cite my sources properly, not just summarize news"
- "Building a timeline of events for one actor takes days"
- "I know the data exists somewhere but finding it is half the battle"
- "Commercial tools are thousands per month - I'm a grad student"

**Jobs to Be Done:**
- Produce verifiable, citable intelligence products
- Track specific actors (people, organizations, vessels) over time
- Cross-reference sanctions lists and entity databases
- Generate reports with proper source attribution

**Rigor Mode Value:**
Maya enables Rigor Mode and gets IC-standard confidence levels, full source URLs, data freshness timestamps, and bias indicators. Her analysis can be published with proper attribution.

**Value Proposition:** *"Professional-grade intelligence research without the professional-grade price tag."*

---

### Tertiary User: The Security Professional

**Persona: David**
- **Demographics:** 42, corporate security analyst at a multinational
- **Context:** Monitors geopolitical risk for business operations, needs structured reports for leadership

**Current Behavior:**
- Subscribes to commercial risk intelligence services
- Uses Ignifer to supplement/validate commercial feeds
- Needs consistent formatting for internal reports

**Jobs to Be Done:**
- Monitor specific regions where company operates
- Screen entities for sanctions/PEP exposure
- Generate executive briefings on emerging situations

**Value Proposition:** *"A free second opinion on what the expensive services are telling me."*

---

### User Journey: Alex (Primary)

| Stage | Experience |
|-------|------------|
| **Discovery** | Sees Ignifer mentioned on Reddit/HackerNews as "OSINT for Claude Desktop" |
| **Installation** | `pip install ignifer`, adds to Claude Desktop config - 2 minutes |
| **First Query** | "What's happening with China and Taiwan this week?" → Gets structured briefing with news, military movements context, economic indicators |
| **Aha Moment** | Asks "Track the vessel [name]" and gets actual AIS position history, not just a link to MarineTraffic |
| **Habit Formation** | Starts morning with "Brief me on overnight developments in [regions of interest]" |
| **Power Usage** | Discovers entity tracking, starts monitoring specific actors across sessions |
| **Advocacy** | Shares on Reddit: "This thing actually pulls real data, not just summarizes news" |

---

### User Anti-Patterns (Who This Is NOT For)

| User Type | Why Not |
|-----------|---------|
| **Nation-state analysts** | Need classified sources, formal dissemination channels |
| **Real-time traders** | Need millisecond data, Ignifer is analysis not trading |
| **Casual news readers** | Don't need multi-source correlation, news apps suffice |
| **Non-technical users** | MCP/Claude Desktop setup requires basic technical comfort |

---

## Key Features

### 1. Multi-Source Intelligence Aggregation

**Data Sources (All Free/Open):**

| Category | Primary Source | Backup Source |
|----------|---------------|---------------|
| News/Events | GDELT | NewsAPI.org |
| Aviation | OpenSky Network | - |
| Maritime | AISStream.io | AISHub |
| Economic | World Bank API | UN OCHA HDX |
| Conflict | ACLED | - |
| Sanctions/PEPs | OpenSanctions | - |
| Entity Enrichment | Wikidata | - |

### 2. Output Modes

**Briefing Mode** (Default)
- Quick, digestible summaries
- Key facts highlighted
- Sources linked but not detailed

**Deep Dive Mode**
- Comprehensive analysis
- Historical context
- Cross-source correlation
- Visualizations where helpful

**Rigor Mode** (IC-Standard)
- ICD 203/206 compliant confidence levels
- Full source attribution with quality scores
- Bias detection flags
- Analytical limitations stated
- Suitable for citation/publication

### 3. MCP Tools

| Tool | Purpose | Output |
|------|---------|--------|
| `briefing(topic)` | Quick intelligence summary | Formatted briefing |
| `deep_dive(topic)` | Comprehensive analysis | Detailed report |
| `track_flight(callsign)` | Aviation tracking | Position, route, history |
| `track_vessel(mmsi/name)` | Maritime tracking | Position, voyage, flags |
| `entity_lookup(name)` | Entity intelligence | Wikidata + sanctions check |
| `economic_context(country)` | Economic indicators | World Bank data summary |
| `conflict_analysis(region)` | Conflict assessment | ACLED event analysis |
| `correlation_map(entities)` | Cross-source linking | Entity relationship graph |

### 4. Confidence Framework (Rigor Mode)

Adapted from ICD 203 Analytic Standards:

| Level | Label | Meaning |
|-------|-------|---------|
| 1 | Remote | Very unlikely (<20%) |
| 2 | Unlikely | Improbable (20-40%) |
| 3 | Even Chance | Roughly equal probability |
| 4 | Likely | Probable (60-80%) |
| 5 | Very Likely | Highly probable (80-95%) |
| 6 | Almost Certain | Near certainty (>95%) |

Source quality indicators:
- **[H]** High - Official sources, academic research
- **[M]** Medium - Reputable news, verified OSINT
- **[L]** Low - Social media, unverified reports

### 5. Session Continuity

Inspired by TSUKUYOMI's session management:
- Export analytical state for later continuation
- Track entities of interest across sessions
- Build cumulative intelligence on topics

---

## Technical Architecture

### MCP Server Structure

```
ignifer/
├── src/
│   ├── server.py              # FastMCP server entry
│   ├── tools/                  # MCP tool handlers
│   │   ├── briefing.py
│   │   ├── deep_dive.py
│   │   ├── tracking.py
│   │   └── entity.py
│   ├── adapters/              # Data source adapters
│   │   ├── base.py            # OSINTAdapter protocol
│   │   ├── gdelt.py
│   │   ├── opensky.py
│   │   ├── aisstream.py
│   │   ├── worldbank.py
│   │   ├── acled.py
│   │   ├── opensanctions.py
│   │   └── wikidata.py
│   ├── aggregation/           # Data fusion layer
│   │   ├── normalizer.py
│   │   ├── correlator.py
│   │   └── confidence.py
│   ├── output/                # Output formatters
│   │   ├── briefing.py
│   │   ├── deep_dive.py
│   │   └── rigor.py
│   └── cache/                 # Caching layer
│       └── sqlite_cache.py
├── tests/
├── pyproject.toml
└── README.md
```

### Key Dependencies

```
mcp                 # Model Context Protocol SDK
httpx               # Async HTTP client
websockets          # AISStream WebSocket
tenacity            # Retry/backoff
gdeltPyR            # GDELT access
wbgapi              # World Bank data
pyopensky           # OpenSky Network
SPARQLWrapper       # Wikidata queries
pydantic            # Data validation
```

---

## MVP Scope (Revised)

### Philosophy: Open-Source Full Vision

Since Ignifer is an open-source personal project without commercial time pressure, the MVP encompasses the complete OSINT data source vision. Development proceeds sequentially, but all core data domains are in scope.

---

### Core Features (All In MVP)

**MCP Server Foundation:**
- [ ] FastMCP server skeleton with stdio transport
- [ ] Tool registration and semantic routing
- [ ] SQLite cache layer
- [ ] Progressive rigor output formatting
- [ ] Error handling with graceful degradation

**Data Source Adapters (7 Domains):**

| Domain | Adapter | Auth Required | Priority |
|--------|---------|---------------|----------|
| News/Events | GDELT | None | 1 |
| Economic | World Bank | None | 1 |
| Entities | Wikidata | None | 1 |
| Aviation | OpenSky Network | OAuth2 (registration) | 2 |
| Maritime | AISStream | API key | 2 |
| Conflict | ACLED | API key (registration) | 3 |
| Sanctions/PEPs | OpenSanctions | None (bulk data) | 3 |

**MCP Tools:**

| Tool | Purpose | Data Sources |
|------|---------|--------------|
| `briefing(topic)` | Quick intelligence summary | GDELT, World Bank, ACLED |
| `deep_dive(topic)` | Comprehensive analysis | All sources |
| `entity_lookup(name)` | Entity intelligence | Wikidata, OpenSanctions |
| `track_flight(callsign)` | Aviation tracking | OpenSky |
| `track_vessel(identifier)` | Maritime tracking (historical) | AISStream |
| `conflict_analysis(region)` | Conflict assessment | ACLED |
| `economic_context(country)` | Economic indicators | World Bank |
| `sanctions_check(entity)` | Sanctions screening | OpenSanctions |

**Rigor Framework:**
- [ ] IC-standard confidence levels (ICD 203)
- [ ] Source quality indicators (H/M/L)
- [ ] Full source attribution with URLs
- [ ] Data freshness timestamps
- [ ] Progressive disclosure (clean summary + expandable rigor)

---

### Out of Scope for MVP

| Feature | Rationale |
|---------|-----------|
| **Real-time streaming** | WebSocket complexity deferred; historical queries cover use cases |
| **Session continuity** | Nice-to-have; not essential for core value |
| **Visualization generation** | Claude describes data adequately; charts/maps are v2 |
| **Alert/monitoring system** | Future feature for persistent tracking |
| **Paid data source integrations** | Community can contribute adapters via plugin architecture |

---

### MVP Success Criteria

**Technical Validation:**
- [ ] All 7 data source adapters functional
- [ ] Zero-config works for Phase 1 sources (GDELT, World Bank, Wikidata)
- [ ] Registered-config works for Phase 2-3 sources (OpenSky, AISStream, ACLED)
- [ ] Query success rate > 95%
- [ ] Cache hit rate > 70%

**User Validation:**
- [ ] 10+ users report useful insights
- [ ] Users successfully query across multiple domains
- [ ] Rigor mode output is citable by researcher users
- [ ] Installation documented and reproducible

**Community Validation:**
- [ ] Published on GitHub with MIT/Apache license
- [ ] README with clear setup instructions
- [ ] First external contributor (issue or PR)

---

### Development Sequence

Since there's no rush, development proceeds in logical order building on foundations:

**Sequence 1: Foundation (Zero Auth)**
1. MCP server skeleton
2. GDELT adapter + `briefing()`
3. World Bank adapter + `economic_context()`
4. Wikidata adapter + `entity_lookup()`
5. SQLite cache layer
6. Progressive rigor output

**Sequence 2: Tracking (Registration Required)**
7. OpenSky adapter + `track_flight()`
8. AISStream adapter + `track_vessel()` (historical)

**Sequence 3: Security Intelligence**
9. ACLED adapter + `conflict_analysis()`
10. OpenSanctions adapter + `sanctions_check()`

**Sequence 4: Integration**
11. `deep_dive()` multi-source correlation
12. Entity resolution across sources
13. Full rigor framework validation

---

### Future Vision (Post-MVP)

| Feature | Description |
|---------|-------------|
| **Real-time streaming** | WebSocket integration for live vessel/flight tracking |
| **Session continuity** | Export/import analytical state across sessions |
| **Visualization helpers** | Generate charts, maps, relationship graphs |
| **Alert system** | Monitor entities/regions for changes |
| **Community adapters** | Plugin architecture for contributed data sources |
| **TSUKUYOMI parity** | Additional modules inspired by full TSUKUYOMI framework |

---

## Success Metrics (Refined)

### User Success Metrics

**North Star Metric:** *Users get answers they couldn't easily get elsewhere*

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Time to first insight** | < 30 seconds | From query to useful response |
| **Multi-source queries** | 60%+ | Queries that pull from 2+ data sources |
| **Return usage** | Weekly active | User returns within 7 days |
| **Query graduation** | Observed | Users progress: briefing → tracking → entity lookup |
| **Zero-config success** | 90%+ | Phase 1 queries work without API key setup |

**Qualitative Indicators:**
- Users share specific insights they discovered (not just "it's cool")
- Users ask follow-up questions (engagement depth)
- Users report replacing manual workflows (tab-switching reduction)

---

### Community & Adoption Metrics

**Adoption Funnel:**

| Stage | Metric | 6-Month Target |
|-------|--------|----------------|
| **Awareness** | GitHub stars | 500+ |
| **Installation** | PyPI downloads | 1,000+ |
| **Activation** | First successful query | 70% of installs |
| **Retention** | Weekly active users | 20% of activations |
| **Advocacy** | Reddit/HN mentions | 10+ organic mentions |

**Community Health:**

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| **Contributors** | 5+ | Beyond solo maintainer |
| **Issues filed** | Active | Users care enough to report |
| **PRs merged** | 10+ | Community building on core |
| **Adapter contributions** | 2+ | Plugin architecture validated |

---

### Technical Quality Metrics

**Reliability:**

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Query success rate** | 95%+ | Queries that return useful data |
| **API availability** | 99%+ | Upstream sources accessible |
| **Error handling** | Graceful | Failures explained, not crashed |
| **Cache hit rate** | 70%+ | Reducing redundant API calls |

**Coverage & Accuracy:**

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Source coverage** | 7 domains | All planned OSINT categories integrated |
| **Entity resolution** | 80%+ | Wikidata linkage success rate |
| **Data freshness** | Appropriate | GDELT < 1hr, World Bank < 24hr, etc. |
| **Rigor mode accuracy** | Validated | Confidence levels match actual reliability |

---

### Anti-Metrics (What We're NOT Optimizing For)

| Anti-Metric | Why We Avoid It |
|-------------|-----------------|
| **Query volume** | More queries ≠ more value; could indicate confusion |
| **Time in app** | Efficiency is the goal, not engagement farming |
| **Daily active users** | Weekly/monthly patterns more realistic for OSINT |
| **Feature count** | Depth over breadth; fewer tools done well |

---

### Success Milestones

**Phase 1 (MVP) Success:**
- [ ] 3 data sources working (GDELT, World Bank, Wikidata)
- [ ] Zero-config installation succeeds
- [ ] First 10 users report useful insights
- [ ] No API keys required for basic queries

**Phase 2 Success:**
- [ ] Aviation + Maritime tracking functional
- [ ] 100+ GitHub stars
- [ ] First community-contributed adapter

**Phase 3 Success:**
- [ ] Conflict + Sanctions sources integrated
- [ ] Rigor mode validated by researcher user
- [ ] 500+ GitHub stars

**Phase 4 Success:**
- [ ] Full 7-domain coverage
- [ ] IC-standard confidence framework complete
- [ ] Mentioned in OSINT community resources

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| API rate limits | Medium | Multi-tier caching |
| Source deprecation | Low | Adapter abstraction layer |
| Data accuracy | Medium | Multi-source verification |
| Scope creep | Medium | Phased implementation |

---

## Open Questions

1. **Visualization** - Should Ignifer generate charts/maps, or just structured data for Claude to describe?
2. **Alerting** - Future feature for monitoring specific entities/regions?
3. **Community Modules** - Plugin architecture for community adapters?
4. **Commercial Sources** - Optional paid source integration for power users?

---

## References

### Technical Research
- `_bmad-output/planning-artifacts/research/technical-osint-apis-research-2026-01-08.md`

### Architecture Reference
- `_reference/TSUKUYOMI/` - TSUKUYOMI Intelligence Framework
  - Module architecture patterns
  - IC-standard confidence levels
  - Source quality framework
  - Session management patterns

---

**Document Status:** Complete
**Created:** 2026-01-08
**Completed:** 2026-01-08
**Author:** Scott (with Mary, Business Analyst)
**Workflow:** Product Brief workflow completed successfully
