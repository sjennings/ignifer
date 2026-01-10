# Ignifer

<p align="center">
  <img src="ignifer_logo.png" alt="Ignifer Logo" width="400">
</p>

<p align="center"><strong>OSINT MCP Server for Claude Desktop</strong></p>

Ignifer is a Model Context Protocol (MCP) server that provides Claude Desktop with powerful Open Source Intelligence (OSINT) capabilities. It aggregates five authoritative data sources into a unified interface, enabling comprehensive intelligence briefings, entity research, transportation tracking, and multi-source deep dive analysis directly within your Claude conversations.

## Features

### Intelligence Briefings
Real-time news intelligence from 65+ language sources worldwide via GDELT (Global Database of Events, Language, and Tone). Get synthesized briefings on any topic with automatic article extraction, translation support, and configurable time ranges.

### Economic Analysis
Comprehensive country economic profiles using World Bank Open Data, organized by E-series analysis categories:
- **E1 - Vulnerability Assessment**: External debt, current account balance, reserves
- **E2 - Trade Profile**: Exports, imports, trade openness, trade balance
- **E4 - Financial Indicators**: Inflation, unemployment, FDI, domestic credit

### Entity Intelligence
Rich contextual data from Wikidata including:
- Entity profiles (people, organizations, vessels, locations)
- Aliases and alternative names
- Relationships and associated entities
- Government leadership and institutional context
- Cross-reference identifiers (Q-IDs, IMO numbers, etc.)

### Aviation Tracking
Real-time aircraft tracking via OpenSky Network:
- Track by callsign, tail number, or ICAO24 code
- Current position, altitude, heading, and speed
- 24-hour flight track history
- Aircraft type and registration details

### Maritime Tracking
Real-time vessel tracking via AISStream:
- Track by vessel name, IMO number, or MMSI
- Current position, speed, and course
- Destination and ETA information
- Vessel type and flag state

### Multi-Source Deep Dive
Comprehensive analysis correlating all available sources:
- Automatic source selection based on query type
- Concurrent querying of relevant sources
- Corroboration detection when sources agree
- Conflict identification when sources disagree
- Source attribution for every finding

### Rigor Mode (IC-Standard Output)
Toggle enhanced analytical output for professional analysts:
- ICD 203 confidence levels (REMOTE to ALMOST_CERTAIN)
- IC-standard phrasing: "We assess with moderate confidence..."
- Full source attribution with URLs and timestamps
- Academic citation formatting (bibliography)
- Analytical caveats and limitations
- Source quality assessments

## Data Sources

| Source | Type | Quality | Auth Required |
|--------|------|---------|---------------|
| **GDELT** | Global news & events | Medium | No |
| **World Bank** | Economic indicators | High | No |
| **Wikidata** | Entity information | High | No |
| **OpenSky** | Aviation tracking | High | Yes (free) |
| **AISStream** | Maritime tracking | High | Yes (free) |

## MCP Tools

Ignifer exposes seven tools to Claude Desktop:

### `briefing`
Generate OSINT intelligence briefings on any topic.

```
briefing(topic: str, time_range: str | None = None, rigor: bool | None = None) -> str
```

**Parameters:**
- `topic` - Topic to research (2-4 words recommended)
- `time_range` - Optional time filter:
  - `"last 24 hours"`, `"last 48 hours"`
  - `"last 7 days"`, `"last 30 days"`
  - `"this week"`, `"last week"`
  - `"2026-01-01 to 2026-01-08"` (ISO date range)
- `rigor` - Enable IC-standard output with confidence levels and citations

**Example:**
```
briefing("Syria", time_range="last 48 hours")
briefing("Ukraine", rigor=True)  # IC-standard output
```

---

### `extract_article`
Extract full article content from any news URL.

```
extract_article(url: str) -> str
```

**Parameters:**
- `url` - Full URL of the article to extract

**Returns:** Clean article text with ads and navigation removed.

---

### `economic_context`
Get comprehensive economic analysis for any country.

```
economic_context(country: str, rigor: bool | None = None) -> str
```

**Parameters:**
- `country` - Country name (e.g., "Germany") or ISO code (e.g., "DEU")
- `rigor` - Enable IC-standard output with confidence levels and citations

**Returns:** Structured economic report with key indicators, vulnerability assessment, trade profile, and financial indicators.

---

### `entity_lookup`
Look up any entity and get comprehensive intelligence.

```
entity_lookup(name: str = "", identifier: str = "", rigor: bool | None = None) -> str
```

**Parameters:**
- `name` - Entity name to search for
- `identifier` - Alternative identifier (Wikidata Q-ID, IMO number, etc.)
- `rigor` - Enable IC-standard output with match confidence percentages

**Returns:** Entity profile with type, description, aliases, relationships, and cross-reference identifiers.

**Example:**
```
entity_lookup(name="Gazprom")
entity_lookup(identifier="Q102673", rigor=True)  # Shows "87% match confidence (VERY_LIKELY)"
```

---

### `track_flight`
Track any aircraft by callsign, tail number, or ICAO24 code.

```
track_flight(identifier: str, rigor: bool | None = None) -> str
```

**Parameters:**
- `identifier` - Callsign (UAL123), tail number (N12345), or ICAO24 code
- `rigor` - Enable IC-standard output with ADS-B coverage caveats

**Returns:** Current position, altitude, heading, speed, and 24-hour track history.

**Note:** Requires OpenSky OAuth2 credentials. Set `IGNIFER_OPENSKY_CLIENT_ID` and `IGNIFER_OPENSKY_CLIENT_SECRET` environment variables. Create API credentials at https://opensky-network.org/account

---

### `track_vessel`
Track any vessel by name, IMO number, or MMSI.

```
track_vessel(identifier: str, rigor: bool | None = None) -> str
```

**Parameters:**
- `identifier` - Vessel name, IMO number (IMO 9811000), or MMSI (367596480)
- `rigor` - Enable IC-standard output with AIS coverage caveats

**Returns:** Current position, speed, course, destination, and vessel details.

**Note:** Requires AISStream API key. Set `IGNIFER_AISSTREAM_KEY` environment variable.

---

### `deep_dive`
Comprehensive multi-source analysis correlating all available data sources.

```
deep_dive(topic: str, focus: str | None = None, rigor: bool | None = None) -> str
```

**Parameters:**
- `topic` - The subject to analyze (country, person, organization, vessel, event)
- `focus` - Optional focus area to emphasize (e.g., "economic", "entity", "aviation", "maritime")
- `rigor` - Enable IC-standard output with full source attribution and bibliography

**Returns:** Comprehensive analysis with:
- Automatic source selection based on query type
- News & events (GDELT)
- Economic context (World Bank)
- Entity profiles (Wikidata)
- Corroboration notes where sources agree
- Conflict markers where sources disagree

**Example:**
```
deep_dive("Myanmar")
deep_dive("Venezuela", focus="economic")
deep_dive("Roman Abramovich", rigor=True)  # Full IC-standard analysis
```

## Rigor Mode

Rigor mode provides IC-standard analytical output suitable for professional intelligence products.

### Enabling Rigor Mode

**Per-query:** Add `rigor=True` to any tool call:
```
briefing("Ukraine", rigor=True)
deep_dive("Venezuela", rigor=True)
```

**Globally:** Set environment variable:
```bash
export IGNIFER_RIGOR_MODE=true
```

Or in config file (`~/.config/ignifer/config.toml`):
```toml
rigor_mode = true
```

### Rigor Mode Output

When enabled, output includes:

**ICD 203 Confidence Levels:**
- REMOTE (<5%), VERY_UNLIKELY (5-20%), UNLIKELY (20-45%)
- ROUGHLY_EVEN (45-55%), LIKELY (55-80%)
- VERY_LIKELY (80-95%), ALMOST_CERTAIN (>95%)

**IC-Standard Phrasing:**
- "We assess with moderate confidence (55-80%) that..."
- "It is very likely (80-95%) that..."

**Source Attribution:**
- Full URLs with retrieval timestamps
- Data freshness indicators (Fresh, Recent, Stale, Archived)
- Source quality tier (HIGH, MEDIUM, LOW)

**Academic Citations:**
```
Sources
═══════

GDELT Project. "Global Database of Events, Language, and Tone."
  Retrieved 2026-01-10T14:32:00Z from https://api.gdeltproject.org/...
  Data freshness: Fresh (<1 hour old)

World Bank. "World Development Indicators: Germany."
  Retrieved 2026-01-10T14:32:15Z from https://api.worldbank.org/...
  Data freshness: Recent (1-24 hours old)

Note: Data reflects point-in-time snapshot. URLs may change;
consider archiving via archive.org for permanent reference.
```

## Installation

### Requirements
- Python 3.10+
- uv (package manager)

### Install
```bash
make install
```

### Configure Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ignifer": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ignifer", "ignifer"]
    }
  }
}
```

Or if installed globally:
```json
{
  "mcpServers": {
    "ignifer": {
      "command": "ignifer"
    }
  }
}
```

### API Key Configuration

For sources requiring authentication, set environment variables:

```bash
# OpenSky (Aviation Tracking - OAuth2)
export IGNIFER_OPENSKY_CLIENT_ID="your_client_id"
export IGNIFER_OPENSKY_CLIENT_SECRET="your_client_secret"

# AISStream (Maritime Tracking)
export IGNIFER_AISSTREAM_KEY="your_api_key"

# Rigor Mode (Optional - enables IC-standard output globally)
export IGNIFER_RIGOR_MODE=true
```

Alternatively, create a config file at `~/.config/ignifer/config.toml`:

```toml
rigor_mode = true  # Optional: enable rigor mode globally

# OpenSky OAuth2 credentials
opensky_client_id = "your_client_id"
opensky_client_secret = "your_client_secret"

# AISStream API key
aisstream_key = "your_api_key"
```

## Architecture

```
ignifer/
├── server.py              # FastMCP server with tool definitions
├── adapters/
│   ├── base.py            # Base adapter protocol & error hierarchy
│   ├── gdelt.py           # GDELT news adapter
│   ├── worldbank.py       # World Bank economic data adapter
│   ├── wikidata.py        # Wikidata entity adapter
│   ├── opensky.py         # OpenSky aviation adapter
│   └── aisstream.py       # AISStream maritime adapter
├── aggregation/
│   ├── entity_resolver.py # Tiered entity resolution system
│   ├── relevance.py       # Source relevance engine
│   └── correlator.py      # Multi-source correlation
├── confidence.py          # ICD 203 confidence framework
├── citation.py            # Academic citation formatting
├── rigor.py               # Rigor mode output formatting
├── cache.py               # SQLite-based response caching
├── config.py              # Configuration management
├── models.py              # Pydantic data models
├── output.py              # Output formatting
└── timeparse.py           # Time range parsing
```

### Adapter Pattern

All data source adapters implement the `OSINTAdapter` protocol:
- `source_name` - Unique identifier for the source
- `base_quality_tier` - Quality tier (HIGH, MEDIUM, LOW)
- `query(params)` - Execute a query against the source
- `health_check()` - Verify source availability
- `close()` - Clean up resources

### Multi-Source Correlation

The aggregation layer provides intelligent source selection and correlation:
- **SourceRelevanceEngine** - Analyzes queries to identify relevant sources
- **Correlator** - Queries sources concurrently, detects corroboration/conflicts
- **EntityResolver** - Tiered entity matching (exact → normalized → Wikidata → fuzzy)

### Caching

Ignifer uses SQLite-based caching with source-specific TTLs:
- GDELT: 1 hour
- World Bank: 24 hours
- Wikidata: 7 days
- OpenSky: 5 minutes
- AISStream: 15 minutes

### Error Handling

All tools provide graceful degradation:
- Timeout errors suggest retry or query refinement
- Rate limiting returns helpful wait guidance
- Missing data offers alternative search suggestions
- Partial data returns available results with source attribution
- Authentication failures provide configuration guidance

## Development

```bash
# Run tests
make test

# Run linting
make lint

# Run type checking
make type-check

# Format code
make format

# Run all checks
make all

# Clean build artifacts
make clean
```

### Running Tests

```bash
# All tests
make test

# With coverage
uv run pytest --cov=ignifer --cov-report=term-missing

# Specific test file
uv run pytest tests/adapters/test_gdelt.py -v
```

## Roadmap

### Completed
- Phase 1: Zero-Config OSINT (GDELT, World Bank, Wikidata)
- Phase 2: Transportation Tracking (OpenSky, AISStream)
- Phase 3: Multi-Source Correlation & Rigor Mode

### Planned
- Enhancements to briefing tool (categorization/evaluation of sources, ability to uprank/downrank, gap analysis)
- Enhancements to economic tool (trade network/resource security)
- Social media monitoring/trend analysis
- Infrastructure monitoring (power/internet/telecom outages)
- Strategic modeling (scenario modeling/actor capability/strategic impact)
- System Administration & Power Features
- Visualization

## License

MIT License - see LICENSE file for details.
