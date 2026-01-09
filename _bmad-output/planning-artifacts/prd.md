---
stepsCompleted: [1, 2, 3, 4, 6, 7, 8, 9, 10, 11]
inputDocuments:
  - product-brief-ignifer-2026-01-08.md
  - research/technical-osint-apis-research-2026-01-08.md
documentCounts:
  briefCount: 1
  researchCount: 1
  brainstormingCount: 0
  projectDocsCount: 0
workflowType: 'prd'
lastStep: 11
date: '2026-01-08'
projectType: 'developer_tool'
domain: 'scientific'
complexity: 'medium'
skippedSteps: [5]
status: 'complete'
---

# Product Requirements Document - Ignifer

**Author:** Scott
**Date:** 2026-01-08

## Executive Summary

Ignifer is a Python MCP server extension for Claude Desktop that democratizes intelligence analysis by providing structured access to seven free OSINT data sources. Named after the flaming sword that cuts through the fog of information, Ignifer brings IC-standard analytical rigor to geopolitical enthusiasts, independent researchers, and security professionals through natural conversation.

**The Problem:** Global events unfold across dozens of fragmented data sources—news feeds, flight trackers, vessel movements, economic indicators, conflict databases, and sanctions lists. Professional analysts have access to classified systems and expensive commercial tools costing thousands per month. Enthusiasts, journalists, and researchers must manually navigate dozens of websites, correlating information without systematic verification frameworks.

**The Solution:** Ignifer provides multi-source OSINT aggregation with optional intelligence-grade rigor, accessible through conversation. Users ask about the world in natural language; Claude routes to the appropriate tools and returns verified, multi-source intelligence with transparent attribution.

**Target Users:**
- **Primary:** Geopolitical enthusiasts who follow global events and want real answers backed by real data
- **Secondary:** Independent researchers and journalists who need citable sources without commercial tool pricing
- **Tertiary:** Security professionals seeking a free second opinion on commercial intelligence feeds

### What Makes This Special

- **Zero-config to first insight** — No API key setup required for Phase 1 sources (GDELT, World Bank, Wikidata)
- **The interface is conversation** — Natural language as primary interaction; explicit commands as power-user escape hatch
- **Progressive disclosure of rigor** — Clean summaries first, expandable IC-standard verification (ICD 203/206 confidence levels) on demand
- **Seven intelligence domains** — News/Events, Aviation, Maritime, Economic, Conflict, Sanctions/PEPs, and Entity intelligence
- **Verb-forward tool design** — `briefing()`, `track_vessel()`, `entity_lookup()` — not implementation-leaking names

## Project Classification

**Technical Type:** developer_tool (Python MCP server/package)
**Domain:** Scientific/Research (OSINT specialization)
**Complexity:** Medium
**Project Context:** Greenfield - new project

Ignifer is modeled after TSUKUYOMI, an advanced modular intelligence framework, adapted for free/open data sources, Claude Desktop MCP integration, and enthusiast-friendly access with professional depth available. The architecture uses async Python patterns with httpx for REST APIs, websockets for real-time streaming (AIS), and a multi-tier caching strategy to manage API rate limits across seven data source adapters.

## Success Criteria

### User Success

**North Star Metric:** Users get answers they couldn't easily get elsewhere

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to first insight | < 30 seconds | From query to useful response |
| Multi-source queries | 60%+ | Queries pulling from 2+ data sources |
| Return usage | Weekly active | User returns within 7 days |
| Query graduation | Observed | Users progress: briefing → tracking → entity lookup |
| Zero-config success | 90%+ | Phase 1 queries work without API key setup |

**Qualitative Success Indicators:**
- Users share specific insights they discovered (not just "it's cool")
- Users ask follow-up questions (engagement depth)
- Users report replacing manual workflows (tab-switching reduction)

**The "Aha" Moment:** User asks "What's the situation with grain shipments from Ukraine?" and gets a coherent briefing pulling from GDELT news, AISStream vessel data, and World Bank trade indicators—with sources cited. No tab-switching. No manual correlation. Just answers.

### Technical Success

| Metric | Target | Rationale |
|--------|--------|-----------|
| Query success rate | 95%+ | Queries return useful data |
| API availability | 99%+ | Upstream sources accessible |
| Cache hit rate | 70%+ | Reduce redundant API calls |
| Error handling | Graceful | Failures explained, not crashed |
| Entity resolution | 80%+ | Wikidata linkage success rate |
| Source coverage | 7 domains | All planned OSINT categories |

### Community Success (Open Source Health)

| Metric | 6-Month Target |
|--------|----------------|
| GitHub stars | 500+ |
| PyPI downloads | 1,000+ |
| Activation rate | 70% of installs complete first query |
| Contributors | 5+ beyond maintainer |
| Issues filed | Active (users care enough to report) |
| PRs merged | 10+ |
| Adapter contributions | 2+ community-contributed sources |

### Anti-Metrics (What We're NOT Optimizing)

| Anti-Metric | Why We Avoid It |
|-------------|-----------------|
| Query volume | More queries ≠ more value; could indicate confusion |
| Time in app | Efficiency is the goal, not engagement farming |
| Daily active users | Weekly/monthly patterns more realistic for OSINT |
| Feature count | Depth over breadth; fewer tools done well |

### Measurable Outcomes

**Phase 1 Success (MVP):**
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

## Product Scope

### MVP - Minimum Viable Product

**MCP Server Foundation:**
- FastMCP server skeleton with stdio transport
- Tool registration and semantic routing
- SQLite cache layer
- Progressive rigor output formatting
- Error handling with graceful degradation

**Phase 1 Data Sources (Zero Auth):**
| Domain | Adapter | Tools |
|--------|---------|-------|
| News/Events | GDELT | `briefing()` |
| Economic | World Bank | `economic_context()` |
| Entities | Wikidata | `entity_lookup()` |

**Phase 2 Data Sources (Registration Required):**
| Domain | Adapter | Tools |
|--------|---------|-------|
| Aviation | OpenSky Network | `track_flight()` |
| Maritime | AISStream | `track_vessel()` |

**Phase 3 Data Sources (API Keys):**
| Domain | Adapter | Tools |
|--------|---------|-------|
| Conflict | ACLED | `conflict_analysis()` |
| Sanctions/PEPs | OpenSanctions | `sanctions_check()` |

### Out of Scope (MVP)

| Feature | Rationale |
|---------|-----------|
| Real-time streaming | WebSocket complexity deferred; historical queries cover use cases |
| Session continuity | Nice-to-have; not essential for core value |
| Visualization generation | Claude describes data adequately; charts/maps are v2 |
| Alert/monitoring system | Future feature for persistent tracking |
| Paid data source integrations | Community can contribute via plugin architecture |

### Vision (Future)

| Feature | Description |
|---------|-------------|
| Real-time streaming | WebSocket integration for live vessel/flight tracking |
| Session continuity | Export/import analytical state across sessions |
| Visualization helpers | Generate charts, maps, relationship graphs |
| Alert system | Monitor entities/regions for changes |
| Community adapters | Plugin architecture for contributed data sources |
| TSUKUYOMI parity | Additional modules inspired by full framework |

## User Journeys

### Journey 1: Alex Chen - From Tab-Switcher to Intelligence Consumer

Alex is a software engineer in Seattle who spends his evenings following geopolitical events. Tonight, he's trying to understand reports about unusual military activity near the Taiwan Strait. He has 12 browser tabs open: Twitter threads, FlightRadar24, MarineTraffic, Reuters, and three different Reddit discussions. After an hour, he's still not sure what's actually happening versus what's speculation.

He remembers seeing someone on r/OSINT mention "Ignifer" - a Claude extension that aggregates OSINT data. Skeptical but curious, he runs `pip install ignifer`, adds three lines to his Claude Desktop config, and restarts the app.

"What's the current situation around Taiwan?" he types.

Within seconds, Claude returns a structured briefing: GDELT shows a 340% spike in Taiwan-related news coverage over the past 48 hours, primarily from defense and diplomatic sources. World Bank shipping indicators show no disruption to semiconductor supply chains. The response includes confidence levels and source URLs.

The breakthrough moment comes when Alex asks "Were there any unusual flight patterns near Taipei this week?" Instead of getting a link to FlightRadar24, he gets actual OpenSky data showing a 15% increase in military transponder activity, with specific callsigns and timestamps. Sources cited. Data he can verify.

Three months later, Alex starts each morning with "Brief me on overnight developments in East Asia and Eastern Europe." He's stopped maintaining his spreadsheet of vessels to track - Ignifer remembers. When a colleague asks how he stays so informed, Alex shares the GitHub link. "It's like having a junior analyst who actually cites their sources."

---

### Journey 2: Maya Okonkwo - The Citation-Ready Researcher

Maya is a graduate student writing her thesis on sanctions evasion in maritime shipping. Her advisor has rejected her last draft, noting that "Twitter threads are not citable sources." She needs to track specific vessels flagged in leaked documents, cross-reference them against sanctions lists, and build a timeline with proper attribution. Commercial tools would cost her entire research stipend.

She discovers Ignifer through an academic OSINT mailing list. After installation, she enables Rigor Mode - she needs IC-standard confidence levels and full source URLs for her citations.

"Look up the vessel Oceanic Spirit, IMO 9312456" she asks.

The response is different from what she's seen before. Instead of a paragraph summary, she gets structured data: vessel registry information from AISStream, last known positions with timestamps, and - critically - an OpenSanctions cross-reference showing the vessel's registered owner appears on the EU sanctions list with 73% entity match confidence. Every data point has a source URL and retrieval timestamp.

Maya's thesis breakthrough comes when she asks for a `deep_dive()` on six vessels mentioned in her leaked documents. Ignifer correlates AIS position data with port calls, flags vessels that have gone dark (AIS off) near sanctioned ports, and cross-references ownership structures against PEP databases. The output includes ICD 203-compliant confidence language she can use directly in her academic writing.

Her thesis defense goes smoothly. The committee is impressed by her "rigorous methodology for open-source verification." One professor asks if she'd teach a workshop on OSINT research methods. Maya's first slide will feature Ignifer's Rigor Mode output format.

---

### Journey 3: David Park - The Second Opinion Analyst

David runs the geopolitical risk desk at a Fortune 500 manufacturing company with operations in 30 countries. He pays $45,000 annually for a commercial intelligence platform, but lately he's been questioning whether he's getting his money's worth. The platform's alerts are often 6-12 hours behind Twitter, and their "AI-powered analysis" reads like rewritten Reuters articles.

He installs Ignifer not to replace his commercial tools, but to validate them. When his paid platform sends an alert about civil unrest in a West African country where his company has a factory, he asks Ignifer for context.

"What's the current conflict situation in Burkina Faso? Include ACLED data."

Ignifer returns ACLED event data showing the geographic distribution of recent incidents, casualty trends, and actor analysis. The commercial platform's alert mentioned "rising tensions" - Ignifer shows him that violence has actually decreased 23% in the past month, with incidents concentrated 200km from his company's facility. The commercial alert was triggered by a single high-profile incident, not a trend.

David starts running parallel queries. When his commercial platform says "moderate risk," he asks Ignifer for the underlying data. Sometimes they align. Sometimes they don't. When they diverge, he investigates - and he's finding that Ignifer's source-cited analysis often provides better context than his paid service's confident-but-vague assessments.

At his next budget review, David doesn't cancel the commercial subscription - yet. But he does start CC'ing his Ignifer findings when he sends intelligence briefs to the C-suite. "For validation," he notes. The CFO starts asking why they're paying for analysis that a free tool can verify - or contradict.

---

### Journey 4: Alex Chen - When the Data Isn't There (Edge Case)

Alex is trying to track a specific cargo vessel he saw mentioned in a news article about alleged sanctions evasion. He asks Ignifer to track it.

"Track vessel Phantom Trader"

Ignifer responds that it can't find a vessel with that name in AISStream data. But instead of just failing, it explains: "No vessel named 'Phantom Trader' found in AIS records. This could mean: (1) the vessel is operating with AIS transponder disabled, (2) the name in the article may be a pseudonym or mistranslation, or (3) the vessel may be registered under a different name. Would you like me to search GDELT for news articles mentioning this vessel name to find alternative identifiers?"

Alex says yes, and Ignifer finds a news article that mentions the vessel's IMO number. With the IMO number, the AIS lookup succeeds - the vessel is currently registered under a different name and is flagged on an OpenSanctions watchlist.

Alex learns that OSINT often requires this kind of pivot - when one source fails, triangulate through another. Ignifer doesn't just fail gracefully; it suggests the next investigative step.

---

### Journey Requirements Summary

These journeys reveal the following capability requirements:

**Core Query Capabilities:**
- Natural language topic queries (`briefing()`)
- Specific entity lookups (`entity_lookup()`, `track_vessel()`, `track_flight()`)
- Deep analysis with correlation (`deep_dive()`)
- Conflict/security analysis (`conflict_analysis()`)
- Sanctions screening (`sanctions_check()`)

**Output Modes:**
- Default briefing mode (clean summaries for Alex)
- Rigor Mode with IC-standard confidence (for Maya's citations)
- Source-comparative analysis (for David's validation)

**Error Handling & Recovery:**
- Graceful failure with explanation
- Suggested alternative queries
- Cross-source triangulation when primary source fails

**Data Requirements:**
- GDELT for news/event trends
- OpenSky for aviation tracking
- AISStream for maritime tracking
- World Bank for economic indicators
- ACLED for conflict data
- OpenSanctions for sanctions/PEP screening
- Wikidata for entity enrichment

**User Experience:**
- Zero-config first query (Alex's 2-minute setup)
- Progressive disclosure of rigor details
- Citable output format (Maya's academic needs)
- Confidence levels and source attribution throughout

## Innovation & Novel Patterns

### Core Innovation: Conversational OSINT

Ignifer's fundamental innovation is the shift from **tool-centric OSINT** to **conversation-centric OSINT**.

**Traditional OSINT Workflow:**
```
User → Opens FlightRadar24 → Searches → Copies data
User → Opens MarineTraffic → Searches → Copies data
User → Opens GDELT → Searches → Copies data
User → Manually correlates in spreadsheet
User → Writes analysis with citations
```

**Ignifer Workflow:**
```
User → Asks question in natural language
Claude → Routes to appropriate tools semantically
Ignifer → Queries multiple sources in parallel
Claude → Correlates and synthesizes
User → Receives cited analysis ready to use
```

The interface IS the conversation. Users don't learn tools; they ask questions.

### What Makes This Novel

| Aspect | Traditional OSINT Tools | Ignifer |
|--------|------------------------|---------|
| Primary Interface | Dashboards, query builders, APIs | Natural language conversation |
| Source Selection | User chooses which tool to use | Claude routes semantically |
| Data Correlation | Manual, user-driven | Automatic, multi-source |
| Output Format | Raw data exports | Synthesized briefings |
| Rigor/Citation | Separate verification step | Built-in, progressive disclosure |
| Learning Curve | Learn each tool separately | Ask questions, get answers |

### Market Context

**No direct competitors exist** in the "conversational OSINT for Claude Desktop" space:
- **Existing OSINT tools** (Maltego, SpiderFoot, theHarvester) are investigator-centric with steep learning curves
- **Commercial intelligence platforms** (Palantir, Recorded Future) cost $10K-100K+ annually
- **MCP servers** exist for many domains, but none aggregate OSINT sources with IC-standard rigor

Ignifer occupies a unique position: **professional analytical patterns, enthusiast accessibility, zero cost**.

### Validation Approach

The conversational OSINT paradigm will be validated through:

1. **Zero-config Success Rate**: Do 90%+ of Phase 1 queries work without setup?
2. **Natural Language Routing Accuracy**: Does Claude correctly interpret user intent and select appropriate tools?
3. **Multi-source Query Adoption**: Do 60%+ of queries naturally pull from multiple sources?
4. **Tab-Switching Reduction**: Do users report replacing manual workflows?

**Key Hypothesis to Validate:**
> Users will prefer asking questions over learning specialized tools, even when specialized tools offer more granular control.

### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Claude misroutes queries to wrong tools | Clear tool descriptions, semantic routing tests, fallback suggestions |
| Users expect real-time data (WebSocket complexity) | MVP uses historical queries; set expectations in documentation |
| Natural language ambiguity causes poor results | Clarifying questions, explicit tool invocation as escape hatch |
| Users don't discover advanced features | Progressive disclosure, "did you know" hints after basic queries |

### Innovation Constraints

The conversational paradigm has intentional boundaries:
- **Not replacing professional tools**: Power users who need granular control should use native interfaces
- **Not real-time monitoring**: Conversation is request-response, not streaming dashboards
- **Not visualization-first**: Claude describes data; charts/maps are future scope

## Developer Tool Specific Requirements

### Project-Type Overview

Ignifer is a **Python MCP server** distributed via PyPI, designed for seamless integration with Claude Desktop. As a developer tool, it prioritizes:
- Zero-friction installation
- Stable APIs for community adapter contributions
- Clear documentation with working examples
- Semantic versioning for predictable upgrades

### Language & Platform Matrix

| Aspect | Specification |
|--------|---------------|
| **Language** | Python 3.10+ (async/await required) |
| **Runtime** | CPython (PyPy not tested) |
| **Platform** | macOS, Linux, Windows (Claude Desktop supported platforms) |
| **MCP Transport** | stdio (standard for Claude Desktop) |

### Installation Methods

**Primary: PyPI**
```bash
pip install ignifer
```

**Development:**
```bash
git clone https://github.com/[user]/ignifer
cd ignifer
pip install -e ".[dev]"
```

**Claude Desktop Configuration:**
```json
{
  "mcpServers": {
    "ignifer": {
      "command": "python",
      "args": ["-m", "ignifer"]
    }
  }
}
```

### Dependencies

| Package | Purpose | Required |
|---------|---------|----------|
| mcp | MCP Python SDK | Yes |
| httpx | Async HTTP client | Yes |
| pydantic | Data validation | Yes |
| tenacity | Retry/backoff | Yes |
| gdeltPyR | GDELT access | Phase 1 |
| wbgapi | World Bank data | Phase 1 |
| SPARQLWrapper | Wikidata queries | Phase 1 |
| pyopensky | OpenSky Network | Phase 2 |
| websockets | AISStream | Phase 2 |

### API Surface (MCP Tools)

| Tool | Description | Data Sources |
|------|-------------|--------------|
| `briefing(topic)` | Quick intelligence summary on any topic | GDELT, World Bank |
| `entity_lookup(name)` | Entity intelligence with sanctions check | Wikidata, OpenSanctions |
| `economic_context(country)` | Economic indicators for a country | World Bank |
| `track_flight(callsign)` | Aviation tracking by callsign | OpenSky |
| `track_vessel(identifier)` | Maritime tracking by MMSI/IMO/name | AISStream |
| `conflict_analysis(region)` | Conflict event analysis | ACLED |
| `sanctions_check(entity)` | Sanctions/PEP screening | OpenSanctions |
| `deep_dive(topic)` | Comprehensive multi-source analysis | All sources |

### Adapter Interface (For Contributors)

Community contributors can add new data source adapters by implementing the `OSINTAdapter` protocol:

```python
class OSINTAdapter(Protocol):
    """Base protocol for all OSINT data source adapters."""

    async def query(self, params: QueryParams) -> OSINTResult:
        """Execute a query against this data source."""
        ...

    def get_source_metadata(self) -> SourceMetadata:
        """Return source name, URL, quality tier, freshness."""
        ...

    def get_confidence_level(self) -> ConfidenceLevel:
        """Return ICD 203 confidence level for this source type."""
        ...
```

**Adapter Stability Commitment:**
- `OSINTAdapter` protocol interface will remain stable within major versions
- Breaking changes to adapter interface = major version bump
- New optional methods can be added in minor versions

### Versioning Strategy

**Semantic Versioning (semver):**
- **MAJOR** (1.0.0 → 2.0.0): Breaking changes to MCP tool signatures or adapter interface
- **MINOR** (1.0.0 → 1.1.0): New tools, new adapters, new optional features
- **PATCH** (1.0.0 → 1.0.1): Bug fixes, documentation updates, dependency bumps

**Stability Guarantees:**
| Component | Stability |
|-----------|-----------|
| MCP tool signatures | Stable within major version |
| OSINTAdapter protocol | Stable within major version |
| Output format (briefing mode) | Stable within major version |
| Output format (rigor mode) | Stable within major version |
| Internal implementation | No guarantees |
| Cache schema | No guarantees |

### Documentation Requirements

| Document | Purpose | Location |
|----------|---------|----------|
| README.md | Quick start, installation, basic usage | Repository root |
| CONTRIBUTING.md | Adapter development guide | Repository root |
| API Reference | Tool signatures and parameters | docs/ or README |
| Examples | Working query examples | README + examples/ |

### Code Examples

**Basic Briefing:**
```
User: "What's happening in the South China Sea?"
Claude: [calls briefing("South China Sea")]
Ignifer: Returns GDELT news analysis + World Bank shipping indicators
```

**Entity Investigation:**
```
User: "Tell me about the vessel Akademik Cherskiy"
Claude: [calls entity_lookup("Akademik Cherskiy"), track_vessel("Akademik Cherskiy")]
Ignifer: Returns Wikidata entity info + AIS position history + OpenSanctions flags
```

**Rigor Mode Research:**
```
User: "I need a citable analysis of conflict trends in the Sahel region"
Claude: [calls conflict_analysis("Sahel", rigor_mode=true)]
Ignifer: Returns ACLED data with ICD 203 confidence levels, source URLs, retrieval timestamps
```

### Implementation Considerations

**Error Handling:**
- All adapter failures return structured error with explanation
- Suggest alternative queries when primary source fails
- Never expose raw API errors to user

**Caching:**
- SQLite cache for API responses (configurable TTL per source)
- Cache key includes query parameters + source version
- Manual cache invalidation via `ignifer cache clear`

**Rate Limiting:**
- Per-source rate limit tracking
- Exponential backoff with jitter on 429 responses
- Graceful degradation when limits exceeded

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Platform MVP - Build the MCP foundation that enables future expansion, with zero-config first value.

**Development Philosophy:** Phases are sequenced to manage solo developer bandwidth, not user complexity. Each phase is a complete, shippable increment.

**Resource Model:** Solo developer, open-source, no commercial timeline pressure.

### Development Phases

#### Phase 1: Foundation (MVP)
**Goal:** Zero-config OSINT queries that deliver immediate value

| Component | Deliverable |
|-----------|-------------|
| MCP Server | FastMCP skeleton, stdio transport, tool registration |
| GDELT Adapter | `briefing(topic)` - news/event analysis |
| World Bank Adapter | `economic_context(country)` - economic indicators |
| Wikidata Adapter | `entity_lookup(name)` - entity enrichment |
| Cache Layer | SQLite with configurable TTL |
| Output Formatting | Progressive rigor (clean summary + expandable details) |

**Success Gate:** User can ask "What's happening in Ukraine?" and get a cited, multi-source briefing without any API key setup.

---

#### Phase 2: Tracking
**Goal:** Add aviation and maritime tracking for users willing to register

| Component | Deliverable |
|-----------|-------------|
| OpenSky Adapter | `track_flight(callsign)` - aviation tracking |
| AISStream Adapter | `track_vessel(identifier)` - maritime tracking (historical) |
| OAuth2 Flow | OpenSky authentication handling |
| WebSocket Client | AISStream connection with auto-reconnect |

**Success Gate:** User can ask "Where is flight UAL123?" or "Track vessel IMO 9312456" and get position history with timestamps.

---

#### Phase 3: Security Intelligence
**Goal:** Add conflict data and sanctions screening for power users

| Component | Deliverable |
|-----------|-------------|
| ACLED Adapter | `conflict_analysis(region)` - conflict event data |
| OpenSanctions Adapter | `sanctions_check(entity)` - sanctions/PEP screening |
| Entity Correlation | Cross-source entity linking via Wikidata Q-IDs |

**Success Gate:** User can ask "Is this company sanctioned?" and get a verified answer with confidence level and source attribution.

---

#### Phase 4: Integration & Rigor
**Goal:** Multi-source correlation and full IC-standard rigor framework

| Component | Deliverable |
|-----------|-------------|
| `deep_dive(topic)` | Multi-source correlation across all 7 domains |
| Full Rigor Mode | ICD 203 confidence levels, complete source attribution |
| Entity Resolution | Automatic entity linking across all sources |
| Output Validation | Rigor mode output suitable for academic citation |

**Success Gate:** Maya (researcher persona) can generate thesis-quality, citable intelligence products.

---

#### Phase 5: Visualization
**Goal:** Generate visual artifacts to complement textual analysis

| Component | Deliverable |
|-----------|-------------|
| Chart Generation | Trend charts, time series, comparative visualizations |
| Map Generation | Geographic plots for vessel/flight tracks, conflict events |
| Relationship Graphs | Entity relationship visualizations |
| Export Formats | PNG, SVG, or embedded in Claude response |

**Success Gate:** User can ask "Show me a map of vessel movements in the Black Sea" and get a visual artifact, not just a text description.

---

### Out of Scope (All Phases)

| Feature | Rationale | Reconsider When |
|---------|-----------|-----------------|
| Real-time streaming | WebSocket complexity, conversation model is request-response | Community demand + stable Phase 2 |
| Session continuity | Nice-to-have, not essential for core value | Post-Phase 4 |
| Alert/monitoring system | Requires persistent state, scheduled execution | Post-Phase 5 |
| Paid data sources | Keep it free; community can contribute adapters | Never (design principle) |

### Risk Mitigation Strategy

**Technical Risks:**
| Risk | Mitigation |
|------|------------|
| API rate limits exceeded | Multi-tier caching (L1 memory, L2 SQLite), request batching |
| Upstream API changes | Adapter abstraction layer isolates changes |
| WebSocket instability (AISStream) | Auto-reconnect with exponential backoff, historical fallback |

**Development Risks:**
| Risk | Mitigation |
|------|------------|
| Solo developer burnout | Phases are independent; can pause between phases |
| Scope creep | Explicit out-of-scope list; future features go to Phase 5+ |
| Community expectations | Clear roadmap in README; no promised timelines |

**Adoption Risks:**
| Risk | Mitigation |
|------|------------|
| Low initial adoption | Focus on r/OSINT, HackerNews launch; quality over marketing |
| No contributors | Design for solo sustainability; contributions are bonus |

## Functional Requirements

### Intelligence Briefings

- FR1: Users can request a topic briefing on any geopolitical topic or region
- FR2: Users can receive news/event analysis with source attribution and timestamps
- FR3: Users can receive economic context alongside news analysis for relevant topics
- FR4: Users can specify a time range for briefing queries (e.g., "last 48 hours", "this week")
- FR5: Users can request briefings in natural language without learning specific syntax

### Entity Intelligence

- FR6: Users can look up any named entity (person, organization, location, vessel, aircraft)
- FR7: Users can receive Wikidata-enriched entity information (aliases, relationships, identifiers)
- FR8: Users can receive cross-referenced sanctions/PEP status for entities
- FR9: Users can search entities by alternative identifiers (IMO number, MMSI, callsign, Q-ID)
- FR10: System automatically links related entities across data sources via Wikidata Q-IDs

### Transportation Tracking

- FR11: Users can track aircraft by callsign, tail number, or flight number
- FR12: Users can track vessels by name, IMO number, or MMSI
- FR13: Users can receive historical position data with timestamps for tracked assets
- FR14: Users can receive current status information (last known position, destination, speed)
- FR15: Users receive clear explanation when tracking data is incomplete

### Security Intelligence

- FR16: Users can request conflict analysis for any country or region
- FR17: Users can receive ACLED event data including incident types, actors, and casualties
- FR18: Users can screen any entity against sanctions lists (OFAC, EU, UN, national lists)
- FR19: Users can identify Politically Exposed Persons (PEPs) associated with entities
- FR20: Users can receive geographic distribution of conflict incidents

### Multi-Source Analysis

- FR21: Users can request deep-dive analysis that correlates multiple data sources
- FR22: System automatically identifies which sources are relevant to a query
- FR23: System presents corroborating evidence when multiple sources agree
- FR24: System highlights conflicting information when sources disagree
- FR25: Users can see which sources contributed to each part of an analysis

### Output & Verification Framework

- FR26: Users can receive clean summary briefings by default (no clutter)
- FR27: Users can enable Rigor Mode for IC-standard confidence levels
- FR28: Users can receive ICD 203-compliant confidence language in Rigor Mode
- FR29: Users can access source URLs and retrieval timestamps for all data points
- FR30: Users can receive output formatted for academic citation (Rigor Mode)
- FR31: System includes confidence percentages for entity matching and correlation

### Error Handling & Recovery

- FR32: System explains failures in user-friendly language (not raw API errors)
- FR33: System suggests alternative queries when primary source fails
- FR34: System offers cross-source triangulation when one source returns no results
- FR35: System indicates when data may be incomplete or outdated
- FR36: System gracefully degrades when upstream APIs are unavailable

### System Configuration

- FR37: Users can install via pip with zero additional configuration for Phase 1 sources
- FR38: Users can configure API keys for Phase 2-3 sources via environment variables or config file
- FR39: Users can check configured source status and API key validity
- FR40: Users can manually clear cache for specific sources or all sources
- FR41: Contributors can add new data source adapters by implementing OSINTAdapter protocol

### Visualization (Phase 5)

- FR42: Users can request trend charts for time-series data
- FR43: Users can request geographic maps for location-based data (vessel tracks, conflict events)
- FR44: Users can request entity relationship graphs
- FR45: System generates visual artifacts in standard formats (PNG, SVG)

### Power User & Advanced Controls

- FR46: Users can invoke tools directly by name as a power-user escape hatch
- FR47: Users can check real-time availability status of data sources
- FR48: Users can set rigor mode preference globally or per-query
- FR49: Users can explicitly include or exclude specific sources from a query
- FR50: Users can accept or modify suggested alternative queries
- FR51: Users can customize visualization parameters (time range, filters, zoom level)

## Non-Functional Requirements

### Performance

| NFR | Requirement | Measurement |
|-----|-------------|-------------|
| NFR-P1 | Single-source queries return within 5 seconds | p95 response time |
| NFR-P2 | Multi-source queries return within 15 seconds (measured from query submission to complete response) | p95 response time |
| NFR-P3 | Cache lookups return within 100ms | p95 response time |
| NFR-P4 | Phase 1 sources (zero-auth) respond within 3 seconds | Per-source p95 |
| NFR-P5 | System remains responsive during API timeouts | No UI freeze |
| NFR-P6 | Individual API calls timeout after 10 seconds with graceful fallback | Timeout enforced |
| NFR-P7 | Total query timeout of 30 seconds prevents infinite waits | Hard timeout enforced |

**Performance Context:**
- Success metric: Time to first insight < 30 seconds
- External APIs are the bottleneck, not local processing
- Caching is critical for repeat queries
- Timeouts prevent runaway queries from blocking the system

### Integration

| NFR | Requirement | Measurement |
|-----|-------------|-------------|
| NFR-I1 | All 7 data source APIs properly authenticated per their requirements | 100% auth success when credentials valid |
| NFR-I2 | Rate limits respected for all upstream APIs | Zero 429 errors from limit violation |
| NFR-I3 | API response parsing handles schema variations gracefully | No crashes from unexpected response format |
| NFR-I4 | WebSocket connections (AISStream) auto-reconnect on disconnect | Reconnection within 30 seconds |
| NFR-I5 | Each adapter isolated - one adapter failure doesn't affect others | Fault isolation verified |

**Integration Context:**
- External APIs have varying reliability and rate limits
- API schemas may change without notice
- Some APIs require registration/API keys

### Reliability

| NFR | Requirement | Measurement |
|-----|-------------|-------------|
| NFR-R1 | System continues operating when individual data sources unavailable | Graceful degradation to available sources |
| NFR-R2 | Cache serves stale data with warning when source unavailable | Stale-while-revalidate pattern |
| NFR-R3 | All errors presented as user-friendly explanations | Zero raw stack traces in output |
| NFR-R4 | When sources are available, 95% of well-formed queries return useful results | Measured via test suite |
| NFR-R5 | No data loss from cache corruption or process termination | SQLite WAL mode, atomic writes |
| NFR-R6 | Cache TTL configurable per source (default: news 1hr, positions 15min, sanctions 24hr) | Configuration validated |
| NFR-R7 | Adapter failure modes are testable via mock injection | Mock framework available |

**Reliability Context:**
- Success metric: 95%+ query success rate
- External API availability is outside our control
- Caching provides resilience layer
- Testable failure modes ensure reliability can be verified

### Maintainability

| NFR | Requirement | Measurement |
|-----|-------------|-------------|
| NFR-M1 | Code passes mypy strict type checking | Zero type errors |
| NFR-M2 | Test coverage ≥80% for core modules (excluding CLI and generated code) | pytest-cov measurement |
| NFR-M3 | New adapter can be added without modifying core code | Plugin architecture validated |
| NFR-M4 | All public APIs documented with docstrings | 100% coverage |
| NFR-M5 | Unit tests complete in <2 minutes; integration tests run separately | CI timing verified |
| NFR-M6 | All dependencies pinned with hash verification for supply chain security | pyproject.toml verified |

**Maintainability Context:**
- Open-source project needs contributor-friendly codebase
- Adapter interface stability commitment (semver)
- Solo developer must maintain long-term
- Supply chain security matters for open-source

### API Key Security

| NFR | Requirement | Measurement |
|-----|-------------|-------------|
| NFR-S1 | API keys never logged or included in error messages | Log audit passes |
| NFR-S2 | API keys read from environment variables or secure config file | No hardcoded credentials |
| NFR-S3 | API keys never transmitted to any system except intended API | Network audit passes |

**Security Context:**
- Users provide their own API keys
- No Ignifer-hosted infrastructure, no user data collection
- API key protection is primary security concern

