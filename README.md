# Ignifer

![Ignifer Logo](ignifer_logo.png)

**OSINT MCP Server for Claude Desktop**

Ignifer is a Model Context Protocol (MCP) server that provides Claude Desktop with powerful Open Source Intelligence (OSINT) capabilities. It aggregates multiple authoritative data sources into a unified interface, enabling comprehensive intelligence briefings and economic analysis directly within your Claude conversations.

## Features

### Intelligence Briefings
Real-time news intelligence from 65+ language sources worldwide via GDELT (Global Database of Events, Language, and Tone). Get synthesized briefings on any topic with automatic article extraction and translation support.

### Economic Analysis
Comprehensive country economic profiles using World Bank Open Data, organized by E-series analysis categories:
- **E1 - Vulnerability Assessment**: External debt, current account balance, reserves
- **E2 - Trade Profile**: Exports, imports, trade openness, trade balance
- **E4 - Financial Indicators**: Inflation, unemployment, FDI, domestic credit

### Entity Context
Rich contextual data from Wikidata including government leadership, currency information, and institutional memberships.

## Data Sources

| Source | Type | Quality | API Key |
|--------|------|---------|---------|
| **GDELT** | Global news & events | Medium | Not required |
| **World Bank** | Economic indicators | High | Not required |
| **Wikidata** | Entity information | High | Not required |

## MCP Tools

Ignifer exposes three tools to Claude Desktop:

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

**Returns:** Formatted intelligence briefing with:
- Coverage statistics (article count, language diversity, geographic spread)
- Language breakdown of source coverage
- Top sources by publication volume
- Recent article summaries with URLs
- Automatically extracted full-text from top articles
- Recommended actions and analysis guidance

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

**Returns:** Clean article text with ads and navigation removed. Non-English articles return original language text for translation.

**Example:**
```
extract_article("https://example.com/news/article")
```

---

### `economic_context`
Get comprehensive economic analysis for any country.

```
economic_context(country: str) -> str
```

**Parameters:**
- `country` - Country name (e.g., "Germany", "Japan") or ISO code (e.g., "DEU", "JPN")

**Returns:** Structured economic report including:

**Key Indicators:**
- GDP (current USD)
- GDP per capita
- Population

**Vulnerability Assessment (E1):**
- External debt (% of GNI)
- Current account balance (% of GDP)
- Total reserves (months of imports)
- Short-term debt (% of reserves)

**Trade Profile (E2):**
- Exports (% of GDP)
- Imports (% of GDP)
- Trade openness (% of GDP)
- Trade balance (USD)

**Financial Indicators (E4):**
- Inflation rate
- Unemployment rate
- FDI inflows (% of GDP)
- Domestic credit (% of GDP)

**Context:**
- Head of government (from Wikidata)
- Currency
- Recent economic events (from GDELT)

**Example:**
```
economic_context("Germany")
economic_context("JPN")
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

## Architecture

```
ignifer/
├── server.py          # FastMCP server with tool definitions
├── adapters/
│   ├── base.py        # Base adapter interface
│   ├── gdelt.py       # GDELT news adapter
│   ├── worldbank.py   # World Bank economic data adapter
│   └── wikidata.py    # Wikidata entity adapter
├── cache.py           # SQLite-based response caching
├── config.py          # Configuration management
├── models.py          # Pydantic data models
├── output.py          # Output formatting
└── timeparse.py       # Time range parsing
```

### Caching

Ignifer uses SQLite-based caching to:
- Reduce API calls to upstream services
- Improve response times for repeated queries
- Handle rate limiting gracefully

### Error Handling

All tools provide graceful degradation:
- Timeout errors suggest retry or query refinement
- Rate limiting returns helpful wait guidance
- Missing data offers alternative search suggestions
- Partial data returns available results with source attribution

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
uv run pytest tests/test_server.py -v
```

## License

MIT License - see LICENSE file for details.
