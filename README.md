# Ignifer

<p align="center">
  <img src="ignifer_logo.png" alt="Ignifer Logo" width="400">
</p>

<p align="center"><strong>OSINT MCP Server for Claude Desktop</strong></p>

Ignifer is a Model Context Protocol (MCP) server that provides Claude Desktop with powerful Open Source Intelligence (OSINT) capabilities. It aggregates seven authoritative data sources into a unified interface, enabling comprehensive intelligence briefings, entity research, transportation tracking, conflict analysis, and sanctions screening directly within your Claude conversations.

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

### Conflict Analysis
Armed conflict event data via ACLED:
- Event counts and trends by type (battles, violence against civilians, protests)
- Actor analysis (state forces, rebel groups, militias)
- Fatality trends and geographic distribution
- Regional hotspot identification

### Sanctions Screening
Entity screening against global sanctions lists via OpenSanctions:
- OFAC SDN, EU, UN, and national sanctions lists
- Politically Exposed Persons (PEP) identification
- Associated entities and ownership chains
- Match confidence scoring

## Data Sources

| Source | Type | Quality | Auth Required |
|--------|------|---------|---------------|
| **GDELT** | Global news & events | Medium | No |
| **World Bank** | Economic indicators | High | No |
| **Wikidata** | Entity information | High | No |
| **OpenSky** | Aviation tracking | High | Yes (free) |
| **AISStream** | Maritime tracking | High | Yes (free) |
| **ACLED** | Conflict events | High | Yes (free) |
| **OpenSanctions** | Sanctions data | High | No |

## MCP Tools

Ignifer exposes eight tools to Claude Desktop:

### `briefing`
Generate OSINT intelligence briefings on any topic.

```
briefing(topic: str, time_range: str | None = None) -> str
```

**Parameters:**
- `topic` - Topic to research (2-4 words recommended)
- `time_range` - Optional time filter:
  - `"last 24 hours"`, `"last 48 hours"`
  - `"last 7 days"`, `"last 30 days"`
  - `"this week"`, `"last week"`
  - `"2026-01-01 to 2026-01-08"` (ISO date range)

**Example:**
```
briefing("Syria conflict", time_range="last 48 hours")
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
economic_context(country: str) -> str
```

**Parameters:**
- `country` - Country name (e.g., "Germany") or ISO code (e.g., "DEU")

**Returns:** Structured economic report with key indicators, vulnerability assessment, trade profile, and financial indicators.

---

### `entity_lookup`
Look up any entity and get comprehensive intelligence.

```
entity_lookup(name: str = "", identifier: str = "") -> str
```

**Parameters:**
- `name` - Entity name to search for
- `identifier` - Alternative identifier (Wikidata Q-ID, IMO number, etc.)

**Returns:** Entity profile with type, description, aliases, relationships, and cross-reference identifiers.

**Example:**
```
entity_lookup(name="Gazprom")
entity_lookup(identifier="Q102673")
```

---

### `track_flight`
Track any aircraft by callsign, tail number, or ICAO24 code.

```
track_flight(identifier: str) -> str
```

**Parameters:**
- `identifier` - Callsign (UAL123), tail number (N12345), or ICAO24 code

**Returns:** Current position, altitude, heading, speed, and 24-hour track history.

**Note:** Requires OpenSky credentials. Set `IGNIFER_OPENSKY_USERNAME` and `IGNIFER_OPENSKY_PASSWORD` environment variables.

---

### `track_vessel`
Track any vessel by name, IMO number, or MMSI.

```
track_vessel(identifier: str) -> str
```

**Parameters:**
- `identifier` - Vessel name, IMO number (IMO 9811000), or MMSI (367596480)

**Returns:** Current position, speed, course, destination, and vessel details.

**Note:** Requires AISStream API key. Set `IGNIFER_AISSTREAM_KEY` environment variable.

---

### `conflict_analysis`
Analyze conflict situations in any country or region.

```
conflict_analysis(region: str, time_range: str | None = None) -> str
```

**Parameters:**
- `region` - Country name or region
- `time_range` - Optional time filter (same formats as briefing)

**Returns:** Conflict event summary with event types, actors, fatalities, and geographic distribution.

**Note:** Requires ACLED API key. Set `IGNIFER_ACLED_KEY` and `IGNIFER_ACLED_EMAIL` environment variables.

---

### `sanctions_check`
Screen any entity against global sanctions lists.

```
sanctions_check(entity: str) -> str
```

**Parameters:**
- `entity` - Entity name (person, company, vessel, etc.)

**Returns:** Match results with sanctions lists, PEP status, associated entities, and match confidence.

**Example:**
```
sanctions_check("Rosneft")
sanctions_check("Alisher Usmanov")
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
# OpenSky (Aviation Tracking)
export IGNIFER_OPENSKY_USERNAME="your_username"
export IGNIFER_OPENSKY_PASSWORD="your_password"

# AISStream (Maritime Tracking)
export IGNIFER_AISSTREAM_KEY="your_api_key"

# ACLED (Conflict Data)
export IGNIFER_ACLED_KEY="your_api_key"
export IGNIFER_ACLED_EMAIL="your_email"
```

Alternatively, create a config file at `~/.config/ignifer/config.toml`:

```toml
[opensky]
username = "your_username"
password = "your_password"

[aisstream]
api_key = "your_api_key"

[acled]
api_key = "your_api_key"
email = "your_email"
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
│   ├── aisstream.py       # AISStream maritime adapter
│   ├── acled.py           # ACLED conflict data adapter
│   └── opensanctions.py   # OpenSanctions sanctions adapter
├── aggregation/
│   └── entity_resolver.py # Tiered entity resolution system
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

### Entity Resolution

The entity resolver uses a tiered matching approach:
1. **Exact match** - Direct string equality
2. **Normalized match** - Lowercase, strip whitespace, remove diacritics
3. **Wikidata lookup** - Query Wikidata for Q-ID and aliases
4. **Fuzzy match** - Levenshtein distance (last resort)

### Caching

Ignifer uses SQLite-based caching with source-specific TTLs:
- GDELT: 1 hour
- World Bank: 24 hours
- Wikidata: 7 days
- OpenSky: 5 minutes
- AISStream: 15 minutes
- ACLED: 12 hours
- OpenSanctions: 24 hours

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
- Phase 3: Security Intelligence (ACLED, OpenSanctions)

### In Progress
- Phase 4: Multi-Source Correlation & Deep Dive Analysis

### Planned
- Rigor Mode with ICD 203 confidence levels
- Academic citation formatting
- System administration tools
- Visualization (Phase 5)

## License

MIT License - see LICENSE file for details.
