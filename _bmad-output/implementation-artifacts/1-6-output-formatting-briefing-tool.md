# Story 1.6: Output Formatting & Briefing Tool

Status: ready-for-dev

## Story

As a **geopolitical enthusiast**,
I want **to ask about any topic and get a clean, cited intelligence briefing**,
so that **I can understand what's happening in the world without tab-switching**.

## Acceptance Criteria

1. **AC1: OutputFormatter Created**
   - **Given** the GDELT adapter from Story 1.5
   - **When** I create `src/ignifer/output.py`
   - **Then** `OutputFormatter` class:
     - Takes `OSINTResult` and formats to clean summary string
     - Includes source attribution (source name, URL, timestamp)
     - Uses progressive disclosure (summary first, details available)
     - Handles error results with user-friendly messages

2. **AC2: Successful Results Formatted Cleanly**
   - **Given** OutputFormatter receives successful GDELT results
   - **When** I call `formatter.format(result)`
   - **Then** output includes:
     - Brief summary of key findings
     - Source count and quality indication
     - Timestamp of data retrieval
     - No raw API response details (clean output)

3. **AC3: FastMCP Briefing Tool Implemented**
   - **Given** the server module exists
   - **When** I update `src/ignifer/server.py`
   - **Then** it implements:
     - FastMCP server using `mcp = FastMCP("ignifer")`
     - `@mcp.tool()` decorated `briefing(topic: str)` function
     - Tool wires: parse params → GDELTAdapter.query() → OutputFormatter.format()
     - Graceful error handling returning user-friendly messages (FR32)
     - Alternative query suggestions on failure (FR33)
     - Data freshness indication (FR35)

4. **AC4: End-to-End Flow Works**
   - **Given** Ignifer is installed and Claude Desktop config includes it
   - **When** user asks "What's happening in Taiwan?"
   - **Then** Claude calls `briefing("Taiwan")`
   - **And** returns a cited briefing with GDELT news analysis
   - **And** response includes source URLs for verification

5. **AC5: Graceful Error Handling**
   - **Given** GDELT is unavailable
   - **When** user asks for a briefing
   - **Then** system returns graceful error message explaining the issue (FR36)
   - **And** suggests trying again later or narrowing the query

6. **AC6: All Quality Checks Pass**
   - **Given** the complete Epic 1 implementation
   - **When** I run `make all` (lint + type-check + test)
   - **Then** all checks pass
   - **And** test coverage for core modules is ≥80%

## Tasks / Subtasks

- [ ] Task 1: Create OutputFormatter class (AC: #1, #2)
  - [ ] 1.1: Create src/ignifer/output.py
  - [ ] 1.2: Implement format(result: OSINTResult) -> str method
  - [ ] 1.3: Format SUCCESS results with summary, source count, quality, timestamp
  - [ ] 1.4: Format NO_DATA results with helpful suggestions
  - [ ] 1.5: Format error results with user-friendly messages
  - [ ] 1.6: Add OutputMode enum (BRIEFING, RIGOR) for future expansion

- [ ] Task 2: Update server.py with FastMCP (AC: #3, #4)
  - [ ] 2.1: Replace stub with working FastMCP server
  - [ ] 2.2: Create @mcp.tool() decorated briefing(topic: str) function
  - [ ] 2.3: Wire adapter → formatter flow
  - [ ] 2.4: Add data freshness indication in output

- [ ] Task 3: Implement error handling (AC: #5)
  - [ ] 3.1: Catch AdapterTimeoutError and return friendly message
  - [ ] 3.2: Catch AdapterError and return friendly message
  - [ ] 3.3: Include alternative query suggestions
  - [ ] 3.4: Never expose raw exceptions to user

- [ ] Task 4: Create tests (AC: #6)
  - [ ] 4.1: Create tests/test_output.py
  - [ ] 4.2: Create tests/test_server.py
  - [ ] 4.3: Test OutputFormatter with SUCCESS result
  - [ ] 4.4: Test OutputFormatter with NO_DATA result
  - [ ] 4.5: Test briefing tool end-to-end with mocked adapter
  - [ ] 4.6: Test error handling scenarios

- [ ] Task 5: Verify quality (AC: #6)
  - [ ] 5.1: Run `make lint` and fix any issues
  - [ ] 5.2: Run `make type-check` and fix any issues
  - [ ] 5.3: Run `make test` and verify coverage ≥80%
  - [ ] 5.4: Run `make all` for final validation

## Dev Notes

### CRITICAL: Architecture Compliance

**FROM project-context.md:**

1. **stdlib logging only** - use `logging.getLogger(__name__)`
2. **ISO 8601 + timezone** for datetime display
3. **Layer rule:** server.py CAN import from adapters, output, cache, models, config

**FROM architecture.md - Output Architecture:**

| Decision | Choice |
|----------|--------|
| Structure | Layered (progressive disclosure) - Summary → Detail → Raw |

**Output Modes (for future expansion):**
```python
class OutputMode(Enum):
    BRIEFING = 'briefing'  # Summary only (default for MVP)
    RIGOR = 'rigor'        # Full attribution + raw data (Phase 4)
```

### File Locations

| File | Path | Purpose |
|------|------|---------|
| output.py | `src/ignifer/output.py` | OutputFormatter class |
| server.py | `src/ignifer/server.py` | FastMCP server + briefing tool |

### OutputFormatter Implementation

```python
"""Output formatting for OSINT results."""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ignifer.models import OSINTResult, ResultStatus, QualityTier

logger = logging.getLogger(__name__)


class OutputMode(Enum):
    """Output verbosity modes."""
    BRIEFING = "briefing"  # Summary only (default)
    RIGOR = "rigor"        # Full attribution + raw data (Phase 4)


class OutputFormatter:
    """Formats OSINTResult into human-readable output.

    Uses progressive disclosure: summary first, details available.
    Handles all result statuses with appropriate messaging.
    """

    def __init__(self, mode: OutputMode = OutputMode.BRIEFING) -> None:
        self.mode = mode

    def format(self, result: OSINTResult) -> str:
        """Format an OSINTResult into a clean, readable string.

        Args:
            result: The OSINT result to format.

        Returns:
            Formatted string suitable for display to users.
        """
        if result.status == ResultStatus.SUCCESS:
            return self._format_success(result)
        elif result.status == ResultStatus.NO_DATA:
            return self._format_no_data(result)
        elif result.status == ResultStatus.RATE_LIMITED:
            return self._format_rate_limited(result)
        else:
            return self._format_error(result)

    def _format_success(self, result: OSINTResult) -> str:
        """Format successful result with summary and attribution."""
        lines = []

        # Extract data
        data = result.data
        article_count = data.get("article_count", 0)
        query = data.get("query", "unknown topic")
        articles = data.get("articles", [])

        # Header with quality indicator
        quality_label = self._quality_label(result.quality_tier)
        lines.append(f"## Intelligence Briefing: {query}")
        lines.append(f"*{article_count} sources analyzed ({quality_label})*")
        lines.append("")

        # Summary of top articles
        lines.append("### Key Findings")
        for i, article in enumerate(articles[:5], 1):
            title = article.get("title", "Untitled")
            domain = article.get("domain", "unknown source")
            lines.append(f"{i}. **{title}** ({domain})")

        if article_count > 5:
            lines.append(f"\n*...and {article_count - 5} more sources*")

        # Source attribution
        lines.append("")
        lines.append("### Sources")
        for source in result.sources:
            timestamp = source.retrieved_at.strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"- {source.source_name}: Retrieved {timestamp}")
            lines.append(f"  {source.source_url}")

        # Freshness indicator
        if result.sources:
            freshness = self._freshness_indicator(result.sources[0].retrieved_at)
            lines.append(f"\n*Data freshness: {freshness}*")

        return "\n".join(lines)

    def _format_no_data(self, result: OSINTResult) -> str:
        """Format no-data result with helpful suggestions."""
        query = result.data.get("query", "your topic")
        suggestion = result.data.get("suggestion", "Try different search terms")

        return (
            f"## No Results Found\n\n"
            f"No intelligence data found for **{query}**.\n\n"
            f"**Suggestions:**\n"
            f"- {suggestion}\n"
            f"- Try more specific keywords\n"
            f"- Check spelling of names or places\n"
            f"- Use English terms for better coverage"
        )

    def _format_rate_limited(self, result: OSINTResult) -> str:
        """Format rate-limited result."""
        return (
            "## Temporarily Unavailable\n\n"
            "The data source is temporarily rate-limited.\n\n"
            "**What to do:**\n"
            "- Wait a few minutes and try again\n"
            "- Try a different, more specific query"
        )

    def _format_error(self, result: OSINTResult) -> str:
        """Format generic error result."""
        return (
            "## Error Retrieving Data\n\n"
            "An error occurred while fetching intelligence data.\n\n"
            "**What to do:**\n"
            "- Try again in a few moments\n"
            "- Check if your query is well-formed\n"
            "- If the problem persists, the source may be unavailable"
        )

    def _quality_label(self, tier: QualityTier | None) -> str:
        """Convert QualityTier to human-readable label."""
        labels = {
            QualityTier.HIGH: "High reliability",
            QualityTier.MEDIUM: "Verified news sources",
            QualityTier.LOW: "Unverified sources",
        }
        return labels.get(tier, "Unknown reliability") if tier else "Unknown reliability"

    def _freshness_indicator(self, retrieved_at: datetime) -> str:
        """Generate freshness indicator based on retrieval time."""
        now = datetime.now(timezone.utc)
        delta = now - retrieved_at

        if delta.total_seconds() < 300:  # 5 minutes
            return "Live (just retrieved)"
        elif delta.total_seconds() < 3600:  # 1 hour
            minutes = int(delta.total_seconds() / 60)
            return f"Recent ({minutes} minutes ago)"
        elif delta.total_seconds() < 86400:  # 24 hours
            hours = int(delta.total_seconds() / 3600)
            return f"Today ({hours} hours ago)"
        else:
            days = int(delta.total_seconds() / 86400)
            return f"Cached ({days} days ago)"
```

### Server Implementation with FastMCP

```python
"""FastMCP server for Ignifer OSINT tools."""

import logging
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ignifer.adapters import GDELTAdapter, AdapterError, AdapterTimeoutError
from ignifer.cache import CacheManager
from ignifer.config import get_settings, configure_logging
from ignifer.models import QueryParams
from ignifer.output import OutputFormatter

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("ignifer")

# Global instances (initialized on first use)
_cache: CacheManager | None = None
_adapter: GDELTAdapter | None = None
_formatter: OutputFormatter | None = None


def _get_cache() -> CacheManager:
    global _cache
    if _cache is None:
        _cache = CacheManager()
    return _cache


def _get_adapter() -> GDELTAdapter:
    global _adapter
    if _adapter is None:
        _adapter = GDELTAdapter(cache=_get_cache())
    return _adapter


def _get_formatter() -> OutputFormatter:
    global _formatter
    if _formatter is None:
        _formatter = OutputFormatter()
    return _formatter


@mcp.tool()
async def briefing(topic: str) -> str:
    """Get an intelligence briefing on any topic.

    Queries global news sources and provides a cited summary
    of recent coverage on the specified topic.

    Args:
        topic: The topic to research (e.g., "Taiwan", "climate change", "AI regulation")

    Returns:
        A formatted intelligence briefing with source citations.
    """
    logger.info(f"Briefing requested for topic: {topic}")

    try:
        # Query the adapter
        adapter = _get_adapter()
        params = QueryParams(topic=topic)
        result = await adapter.query(params)

        # Format the result
        formatter = _get_formatter()
        output = formatter.format(result)

        logger.info(f"Briefing completed for topic: {topic}")
        return output

    except AdapterTimeoutError as e:
        logger.warning(f"Timeout getting briefing for {topic}: {e}")
        return (
            f"## Request Timed Out\n\n"
            f"The request for **{topic}** timed out.\n\n"
            f"**Suggestions:**\n"
            f"- Try again in a moment\n"
            f"- Use a more specific query\n"
            f"- Check your network connection"
        )

    except AdapterError as e:
        logger.error(f"Adapter error for {topic}: {e}")
        return (
            f"## Unable to Retrieve Data\n\n"
            f"Could not get intelligence on **{topic}**.\n\n"
            f"**What happened:** {e.message}\n\n"
            f"**Suggestions:**\n"
            f"- Try again in a few moments\n"
            f"- Try different search terms"
        )

    except Exception as e:
        logger.exception(f"Unexpected error for {topic}: {e}")
        return (
            f"## Error\n\n"
            f"An unexpected error occurred while researching **{topic}**.\n\n"
            f"Please try again later."
        )


def main() -> None:
    """Run the Ignifer MCP server."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Starting Ignifer MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
```

### Test Files

**tests/test_output.py:**
```python
"""Tests for output formatting."""

import pytest
from datetime import datetime, timezone

from ignifer.models import OSINTResult, ResultStatus, QualityTier, SourceMetadata
from ignifer.output import OutputFormatter, OutputMode


class TestOutputFormatter:
    def test_format_success_includes_summary(self) -> None:
        """Successful results include summary and source count."""
        result = OSINTResult(
            status=ResultStatus.SUCCESS,
            data={
                "articles": [
                    {"title": "Test Article", "domain": "example.com"},
                ],
                "article_count": 1,
                "query": "test topic",
            },
            sources=[SourceMetadata(
                source_name="gdelt",
                source_url="https://api.gdeltproject.org/...",
                retrieved_at=datetime.now(timezone.utc),
            )],
            confidence=None,
            quality_tier=QualityTier.MEDIUM,
        )

        formatter = OutputFormatter()
        output = formatter.format(result)

        assert "Intelligence Briefing" in output
        assert "test topic" in output
        assert "1 sources analyzed" in output
        assert "Test Article" in output
        assert "gdelt" in output

    def test_format_no_data_includes_suggestions(self) -> None:
        """NO_DATA results include helpful suggestions."""
        result = OSINTResult(
            status=ResultStatus.NO_DATA,
            data={
                "query": "xyznonexistent",
                "suggestion": "Try broader terms",
            },
            sources=[],
            confidence=None,
            quality_tier=None,
        )

        formatter = OutputFormatter()
        output = formatter.format(result)

        assert "No Results Found" in output
        assert "xyznonexistent" in output
        assert "Try broader terms" in output or "Suggestions" in output

    def test_format_rate_limited(self) -> None:
        """RATE_LIMITED results explain the situation."""
        result = OSINTResult(
            status=ResultStatus.RATE_LIMITED,
            data={},
            sources=[],
            confidence=None,
            quality_tier=None,
        )

        formatter = OutputFormatter()
        output = formatter.format(result)

        assert "Temporarily Unavailable" in output or "rate-limited" in output.lower()

    def test_quality_labels(self) -> None:
        """Quality tiers are labeled correctly."""
        formatter = OutputFormatter()

        assert "High" in formatter._quality_label(QualityTier.HIGH)
        assert "Verified" in formatter._quality_label(QualityTier.MEDIUM)
        assert "Unverified" in formatter._quality_label(QualityTier.LOW)
```

**tests/test_server.py:**
```python
"""Tests for FastMCP server and briefing tool."""

import re
import pytest
from unittest.mock import AsyncMock, patch

from ignifer.server import briefing
from ignifer.models import OSINTResult, ResultStatus, QualityTier, SourceMetadata
from ignifer.adapters.base import AdapterTimeoutError


class TestBriefingTool:
    @pytest.mark.asyncio
    async def test_briefing_success(self) -> None:
        """Briefing tool returns formatted output on success."""
        from datetime import datetime, timezone

        mock_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            data={
                "articles": [{"title": "Test", "domain": "test.com"}],
                "article_count": 1,
                "query": "Taiwan",
            },
            sources=[SourceMetadata(
                source_name="gdelt",
                source_url="https://api.gdeltproject.org/...",
                retrieved_at=datetime.now(timezone.utc),
            )],
            confidence=None,
            quality_tier=QualityTier.MEDIUM,
        )

        with patch("ignifer.server._get_adapter") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.query.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await briefing("Taiwan")

            assert "Intelligence Briefing" in result
            assert "Taiwan" in result

    @pytest.mark.asyncio
    async def test_briefing_timeout_returns_friendly_message(self) -> None:
        """Timeout errors return user-friendly message."""
        with patch("ignifer.server._get_adapter") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.query.side_effect = AdapterTimeoutError("gdelt", 10.0)
            mock_adapter.return_value = adapter_instance

            result = await briefing("Taiwan")

            assert "Timed Out" in result
            assert "Taiwan" in result
            assert "Suggestions" in result

    @pytest.mark.asyncio
    async def test_briefing_no_data_returns_suggestions(self) -> None:
        """No data results include helpful suggestions."""
        mock_result = OSINTResult(
            status=ResultStatus.NO_DATA,
            data={"query": "xyznonexistent", "suggestion": "Try broader terms"},
            sources=[],
            confidence=None,
            quality_tier=None,
        )

        with patch("ignifer.server._get_adapter") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.query.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await briefing("xyznonexistent")

            assert "No Results" in result
```

### Claude Desktop Configuration

After installation, add to Claude Desktop config:

```json
{
  "mcpServers": {
    "ignifer": {
      "command": "ignifer"
    }
  }
}
```

**Config file locations:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Anti-Patterns to AVOID

```python
# WRONG: Exposing raw exceptions to users
except Exception as e:
    return str(e)  # NO - expose friendly message only

# WRONG: Not handling timeout specifically
except Exception:
    return "Error"  # NO - handle AdapterTimeoutError specially

# WRONG: Naive datetime
datetime.now()  # NO - use datetime.now(timezone.utc)

# WRONG: loguru
from loguru import logger  # NO - use stdlib logging

# WRONG: Missing tool docstring
@mcp.tool()
async def briefing(topic: str) -> str:
    pass  # NO - docstring is used by LLM to understand the tool
```

### Dependencies on Previous Stories

**Story 1.2 provides:**
- `OSINTResult`, `ResultStatus`, `QualityTier`, `SourceMetadata` models
- `QueryParams` for adapter queries
- `get_settings()`, `configure_logging()` for configuration

**Story 1.3 provides:**
- `CacheManager` for caching (injected into adapter)

**Story 1.4 provides:**
- `AdapterError`, `AdapterTimeoutError` for error handling

**Story 1.5 provides:**
- `GDELTAdapter` for querying GDELT

### Project Structure After This Story (Epic 1 Complete)

```
src/ignifer/
├── __init__.py      # __version__ = "0.1.0"
├── __main__.py      # Entry point
├── server.py        # UPDATED - FastMCP server + briefing tool
├── models.py        # Story 1.2
├── config.py        # Story 1.2
├── cache.py         # Story 1.3
├── output.py        # NEW - OutputFormatter
└── adapters/
    ├── __init__.py
    ├── base.py      # Story 1.4
    └── gdelt.py     # Story 1.5

tests/
├── conftest.py
├── test_cache.py
├── test_output.py   # NEW
├── test_server.py   # NEW
├── adapters/
│   ├── test_base.py
│   └── test_gdelt.py
└── fixtures/
    ├── cache_scenarios.py
    ├── gdelt_response.json
    └── gdelt_empty.json
```

### Epic 1 Completion Checklist

After this story, verify:
- [ ] `make lint` passes
- [ ] `make type-check` passes
- [ ] `make test` passes with ≥80% coverage
- [ ] `make all` succeeds
- [ ] `python -m ignifer` starts server without errors
- [ ] Claude Desktop can call `briefing("Taiwan")` successfully

### References

- [Source: architecture.md#Output-Architecture] - Progressive disclosure pattern
- [Source: project-context.md#Output-Modes] - BRIEFING vs RIGOR modes
- [Source: epics.md#Story-1.6] - Acceptance criteria
- [FastMCP Documentation](https://gofastmcp.com/) - Tool decorator patterns

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

- [ ] OutputFormatter class created with format() method
- [ ] SUCCESS results formatted with summary, sources, freshness
- [ ] NO_DATA results include helpful suggestions
- [ ] Error results provide user-friendly messages
- [ ] server.py updated with working FastMCP server
- [ ] @mcp.tool() decorated briefing(topic) function
- [ ] AdapterTimeoutError handled gracefully
- [ ] AdapterError handled gracefully
- [ ] tests/test_output.py created
- [ ] tests/test_server.py created
- [ ] `make all` passes
- [ ] Coverage ≥80%

### File List

_Files created/modified during implementation:_

- [ ] src/ignifer/output.py (NEW)
- [ ] src/ignifer/server.py (UPDATED - replace stub)
- [ ] tests/test_output.py (NEW)
- [ ] tests/test_server.py (NEW)
