# Story 1.5: GDELT Adapter

Status: ready-for-dev

## Story

As a **OSINT enthusiast**,
I want **to query GDELT for news and event data**,
so that **I can get intelligence briefings on any topic without API keys**.

## Acceptance Criteria

1. **AC1: GDELTAdapter Class Created**
   - **Given** the adapter protocol from Story 1.4 and cache from Story 1.3
   - **When** I create `src/ignifer/adapters/gdelt.py`
   - **Then** `GDELTAdapter` class:
     - Implements `OSINTAdapter` protocol
     - Has `source_name = "gdelt"` and `base_quality_tier = QualityTier.MEDIUM`
     - Creates adapter-owned `httpx.AsyncClient` (not shared)
     - Implements `async query(params: QueryParams) -> OSINTResult`
     - Implements `async health_check() -> bool`
     - Implements `async close()` for cleanup

2. **AC2: Successful Query Returns Results**
   - **Given** GDELTAdapter is instantiated
   - **When** I call `await adapter.query(QueryParams(topic="Ukraine"))`
   - **Then** it queries GDELT API v2 for articles matching the topic
   - **And** returns `OSINTResult` with status=SUCCESS and populated data
   - **And** includes source attribution with GDELT URL and retrieval timestamp
   - **And** results are cached using CacheManager with 1-hour TTL

3. **AC3: No Results Returns NO_DATA Status**
   - **Given** GDELT API returns no results
   - **When** I call `await adapter.query(params)`
   - **Then** it returns `OSINTResult` with status=NO_DATA
   - **And** suggests alternative query approaches in the result

4. **AC4: Timeout Raises AdapterTimeoutError**
   - **Given** GDELT API times out (>10 seconds)
   - **When** I call `await adapter.query(params)`
   - **Then** it raises `AdapterTimeoutError` with source name
   - **And** the timeout is enforced via httpx timeout configuration

5. **AC5: Tests Pass with Mocked Responses**
   - **Given** test fixtures exist in `tests/fixtures/gdelt_response.json`
   - **When** I run `pytest tests/adapters/test_gdelt.py`
   - **Then** all tests pass using mocked HTTP responses
   - **And** no actual API calls are made during tests

## Tasks / Subtasks

- [ ] Task 1: Create GDELTAdapter class (AC: #1)
  - [ ] 1.1: Create src/ignifer/adapters/gdelt.py
  - [ ] 1.2: Implement source_name and base_quality_tier properties
  - [ ] 1.3: Create adapter-owned httpx.AsyncClient with 10s timeout
  - [ ] 1.4: Implement async close() for client cleanup

- [ ] Task 2: Implement query method (AC: #2, #3)
  - [ ] 2.1: Build GDELT API v2 URL with query parameters
  - [ ] 2.2: Execute async HTTP request with error handling
  - [ ] 2.3: Parse JSON response into article list
  - [ ] 2.4: Create OSINTResult with SUCCESS status and data
  - [ ] 2.5: Handle empty results with NO_DATA status
  - [ ] 2.6: Include source attribution with URL and timestamp

- [ ] Task 3: Implement caching (AC: #2)
  - [ ] 3.1: Generate cache key using cache_key() function
  - [ ] 3.2: Check cache before making API request
  - [ ] 3.3: Store results in cache with 1-hour TTL from config

- [ ] Task 4: Implement error handling (AC: #4)
  - [ ] 4.1: Catch httpx.TimeoutException and raise AdapterTimeoutError
  - [ ] 4.2: Catch parsing errors and raise AdapterParseError
  - [ ] 4.3: Chain original exceptions using `from e`

- [ ] Task 5: Implement health_check (AC: #1)
  - [ ] 5.1: Make lightweight request to verify API reachability
  - [ ] 5.2: Return True if successful, False otherwise

- [ ] Task 6: Create test fixtures and tests (AC: #5)
  - [ ] 6.1: Create tests/fixtures/gdelt_response.json
  - [ ] 6.2: Create tests/fixtures/gdelt_empty.json
  - [ ] 6.3: Create tests/adapters/test_gdelt.py
  - [ ] 6.4: Test successful query with mocked response
  - [ ] 6.5: Test empty results returns NO_DATA
  - [ ] 6.6: Test timeout raises AdapterTimeoutError
  - [ ] 6.7: Test cache integration

- [ ] Task 7: Update adapters/__init__.py (AC: #1)
  - [ ] 7.1: Add GDELTAdapter to exports
  - [ ] 7.2: Update __all__ list

## Dev Notes

### CRITICAL: Architecture Compliance

**FROM project-context.md:**

1. **Adapter-owned httpx clients** - GDELTAdapter creates its own client, never shared
2. **`{Source}Adapter` naming** - Class MUST be named `GDELTAdapter`
3. **Hybrid error handling:**
   - `AdapterTimeoutError` for timeouts (exception - unexpected)
   - `OSINTResult(status=NO_DATA)` for empty results (result type - expected)
   - `AdapterParseError` for malformed responses (exception - unexpected)
4. **Layer rule:** Adapters MUST NOT import from server.py or tools
5. **stdlib logging only** - use `logging.getLogger(__name__)`

### File Locations

| File | Path | Purpose |
|------|------|---------|
| gdelt.py | `src/ignifer/adapters/gdelt.py` | GDELT adapter implementation |
| test_gdelt.py | `tests/adapters/test_gdelt.py` | Adapter tests |
| gdelt_response.json | `tests/fixtures/gdelt_response.json` | Mock successful response |
| gdelt_empty.json | `tests/fixtures/gdelt_empty.json` | Mock empty response |

### GDELT API v2 Details

**Base URL:**
```
https://api.gdeltproject.org/api/v2/doc/doc
```

**Key Parameters:**
| Parameter | Value | Description |
|-----------|-------|-------------|
| `query` | topic string | Search term (URL-encoded) |
| `mode` | `ArtList` | Return article list |
| `format` | `json` | JSON response format |
| `maxrecords` | `75` (default, max 250) | Number of results |
| `timespan` | `3m` (default) | Time window (3 months) |

**Example Request:**
```
https://api.gdeltproject.org/api/v2/doc/doc?query=Ukraine&mode=ArtList&format=json&maxrecords=75
```

**No API key required** - GDELT is free and open.

### GDELTAdapter Implementation

```python
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from ignifer.adapters.base import AdapterParseError, AdapterTimeoutError
from ignifer.cache import CacheManager, cache_key
from ignifer.config import get_settings
from ignifer.models import OSINTResult, QueryParams, QualityTier, ResultStatus, SourceMetadata

logger = logging.getLogger(__name__)


class GDELTAdapter:
    """GDELT adapter for news and event data.

    GDELT (Global Database of Events, Language, and Tone) provides
    real-time monitoring of global news coverage. No API key required.

    Attributes:
        source_name: "gdelt"
        base_quality_tier: QualityTier.MEDIUM (reputable news sources)
    """

    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    DEFAULT_TIMEOUT = 10.0  # seconds

    def __init__(self, cache: CacheManager | None = None) -> None:
        self._client: httpx.AsyncClient | None = None
        self._cache = cache

    @property
    def source_name(self) -> str:
        return "gdelt"

    @property
    def base_quality_tier(self) -> QualityTier:
        return QualityTier.MEDIUM

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.DEFAULT_TIMEOUT),
                headers={"User-Agent": "Ignifer/1.0"},
            )
        return self._client

    async def query(self, params: QueryParams) -> OSINTResult:
        """Query GDELT for articles matching the topic.

        Args:
            params: Query parameters including topic and optional time_range.

        Returns:
            OSINTResult with articles data or NO_DATA status.

        Raises:
            AdapterTimeoutError: If request times out.
            AdapterParseError: If response cannot be parsed.
        """
        # Generate cache key
        key = cache_key(self.source_name, "topic", topic=params.topic)

        # Check cache first
        if self._cache:
            cached = await self._cache.get(key)
            if cached and not cached.is_stale:
                logger.debug(f"Cache hit for {key}")
                return OSINTResult(
                    status=ResultStatus.SUCCESS,
                    data=cached.data,
                    sources=[SourceMetadata(
                        source_name=self.source_name,
                        source_url=self.BASE_URL,
                        retrieved_at=datetime.now(timezone.utc),  # Cache hit time
                    )],
                    confidence=None,
                    quality_tier=self.base_quality_tier,
                )

        # Build request URL
        query_params = {
            "query": params.topic,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": 75,
        }
        url = f"{self.BASE_URL}?{urlencode(query_params)}"

        try:
            client = await self._get_client()
            logger.info(f"Querying GDELT: {params.topic}")
            response = await client.get(url)
            response.raise_for_status()

        except httpx.TimeoutException as e:
            logger.warning(f"GDELT timeout for query: {params.topic}")
            raise AdapterTimeoutError(self.source_name, self.DEFAULT_TIMEOUT) from e

        except httpx.HTTPError as e:
            logger.error(f"GDELT HTTP error: {e}")
            raise AdapterParseError(self.source_name, str(e)) from e

        # Parse response
        try:
            data = response.json()
        except Exception as e:
            raise AdapterParseError(self.source_name, "Invalid JSON response") from e

        # Check for empty results
        articles = data.get("articles", [])
        if not articles:
            logger.info(f"No GDELT results for: {params.topic}")
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                data={
                    "query": params.topic,
                    "suggestion": "Try broader search terms or different keywords",
                },
                sources=[],
                confidence=None,
                quality_tier=None,
            )

        # Build successful result
        retrieved_at = datetime.now(timezone.utc)
        result_data = {
            "articles": articles,
            "article_count": len(articles),
            "query": params.topic,
        }

        # Cache the result
        if self._cache:
            settings = get_settings()
            await self._cache.set(
                key=key,
                data=result_data,
                ttl_seconds=settings.ttl_gdelt,
                source=self.source_name,
            )

        return OSINTResult(
            status=ResultStatus.SUCCESS,
            data=result_data,
            sources=[SourceMetadata(
                source_name=self.source_name,
                source_url=url,
                retrieved_at=retrieved_at,
            )],
            confidence=None,
            quality_tier=self.base_quality_tier,
        )

    async def health_check(self) -> bool:
        """Check if GDELT API is reachable.

        Returns:
            True if API responds, False otherwise.
        """
        try:
            client = await self._get_client()
            # Use a minimal query to check connectivity
            response = await client.get(
                f"{self.BASE_URL}?query=test&mode=ArtList&format=json&maxrecords=1"
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"GDELT health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("GDELT adapter client closed")
```

### Test Fixtures

**tests/fixtures/gdelt_response.json:**
```json
{
  "articles": [
    {
      "url": "https://example.com/article1",
      "title": "Ukraine Update: Latest Developments",
      "seendate": "20260108T120000Z",
      "domain": "example.com",
      "language": "English",
      "sourcecountry": "United States"
    },
    {
      "url": "https://example.com/article2",
      "title": "Analysis: Ukraine Situation",
      "seendate": "20260108T110000Z",
      "domain": "example.com",
      "language": "English",
      "sourcecountry": "United Kingdom"
    }
  ]
}
```

**tests/fixtures/gdelt_empty.json:**
```json
{
  "articles": []
}
```

### Test File Structure (tests/adapters/test_gdelt.py)

```python
"""Tests for GDELT adapter."""

import re
import pytest
from datetime import datetime, timezone

from ignifer.adapters.gdelt import GDELTAdapter
from ignifer.adapters.base import AdapterTimeoutError, AdapterParseError
from ignifer.models import QueryParams, ResultStatus, QualityTier


def load_fixture(name: str) -> dict:
    """Load JSON fixture file."""
    import json
    from pathlib import Path
    fixture_path = Path(__file__).parent.parent / "fixtures" / name
    return json.loads(fixture_path.read_text())


class TestGDELTAdapter:
    def test_source_name(self) -> None:
        adapter = GDELTAdapter()
        assert adapter.source_name == "gdelt"

    def test_base_quality_tier(self) -> None:
        adapter = GDELTAdapter()
        assert adapter.base_quality_tier == QualityTier.MEDIUM

    @pytest.mark.asyncio
    async def test_query_success(self, httpx_mock) -> None:
        """Test successful query returns OSINTResult with SUCCESS status."""
        httpx_mock.add_response(
            url=re.compile(r".*gdeltproject.*"),
            json=load_fixture("gdelt_response.json"),
        )

        adapter = GDELTAdapter()
        result = await adapter.query(QueryParams(topic="Ukraine"))

        assert result.status == ResultStatus.SUCCESS
        assert result.data["article_count"] == 2
        assert len(result.sources) == 1
        assert result.sources[0].source_name == "gdelt"
        assert result.quality_tier == QualityTier.MEDIUM

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_empty_returns_no_data(self, httpx_mock) -> None:
        """Test empty results return NO_DATA status with suggestion."""
        httpx_mock.add_response(
            url=re.compile(r".*gdeltproject.*"),
            json=load_fixture("gdelt_empty.json"),
        )

        adapter = GDELTAdapter()
        result = await adapter.query(QueryParams(topic="xyznonexistent123"))

        assert result.status == ResultStatus.NO_DATA
        assert "suggestion" in result.data

        await adapter.close()

    @pytest.mark.asyncio
    async def test_query_timeout_raises_error(self, httpx_mock) -> None:
        """Test timeout raises AdapterTimeoutError with source name."""
        import httpx
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timed out"),
            url=re.compile(r".*gdeltproject.*"),
        )

        adapter = GDELTAdapter()

        with pytest.raises(AdapterTimeoutError) as exc_info:
            await adapter.query(QueryParams(topic="Ukraine"))

        assert exc_info.value.source_name == "gdelt"
        assert exc_info.value.__cause__ is not None  # Exception chained

        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_success(self, httpx_mock) -> None:
        """Test health check returns True when API responds."""
        httpx_mock.add_response(
            url=re.compile(r".*gdeltproject.*"),
            status_code=200,
        )

        adapter = GDELTAdapter()
        result = await adapter.health_check()

        assert result is True
        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, httpx_mock) -> None:
        """Test health check returns False when API fails."""
        import httpx
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused"),
            url=re.compile(r".*gdeltproject.*"),
        )

        adapter = GDELTAdapter()
        result = await adapter.health_check()

        assert result is False
        await adapter.close()
```

### Anti-Patterns to AVOID

```python
# WRONG: Shared client across adapters
_shared_client = httpx.AsyncClient()  # NO - adapter-owned only

# WRONG: New client per request (defeats connection pooling)
async def query(self, params):
    async with httpx.AsyncClient() as client:  # NO!
        return await client.get(...)

# WRONG: Missing exception chaining
except httpx.TimeoutException:
    raise AdapterTimeoutError("gdelt")  # NO - use 'from e'

# WRONG: Hardcoded TTL
ttl = 3600  # NO - use get_settings().ttl_gdelt

# WRONG: Naive datetime
retrieved_at = datetime.now()  # NO - use datetime.now(timezone.utc)

# WRONG: Adapter naming
class GDELT:  # NO - use GDELTAdapter
class GdeltAdapter:  # NO - uppercase source name: GDELTAdapter

# WRONG: Importing from server
from ignifer.server import ...  # NO - layer violation
```

### Dependencies on Previous Stories

**Story 1.2 provides:**
- `QueryParams` model for query method input
- `OSINTResult` model for query return value
- `QualityTier.MEDIUM` for base_quality_tier
- `ResultStatus.SUCCESS`, `ResultStatus.NO_DATA`
- `SourceMetadata` for source attribution

**Story 1.3 provides:**
- `CacheManager` for caching results
- `cache_key()` for generating cache keys
- `get_settings().ttl_gdelt` for TTL value (3600 seconds)

**Story 1.4 provides:**
- `OSINTAdapter` Protocol that GDELTAdapter must satisfy
- `AdapterTimeoutError` for timeout exceptions
- `AdapterParseError` for parsing exceptions

### Project Structure After This Story

```
src/ignifer/
├── __init__.py
├── __main__.py
├── server.py
├── models.py        # Story 1.2
├── config.py        # Story 1.2
├── cache.py         # Story 1.3
└── adapters/
    ├── __init__.py  # UPDATED - add GDELTAdapter export
    ├── base.py      # Story 1.4
    └── gdelt.py     # NEW - GDELT adapter

tests/
├── conftest.py
├── test_cache.py
├── adapters/
│   ├── test_base.py
│   └── test_gdelt.py  # NEW
└── fixtures/
    ├── cache_scenarios.py
    ├── gdelt_response.json  # NEW
    └── gdelt_empty.json     # NEW
```

### Updated adapters/__init__.py

```python
"""OSINT data source adapters."""

from ignifer.adapters.base import (
    AdapterAuthError,
    AdapterError,
    AdapterParseError,
    AdapterTimeoutError,
    OSINTAdapter,
)
from ignifer.adapters.gdelt import GDELTAdapter

__all__ = [
    "OSINTAdapter",
    "AdapterError",
    "AdapterTimeoutError",
    "AdapterParseError",
    "AdapterAuthError",
    "GDELTAdapter",
]
```

### References

- [Source: architecture.md#Adapter-Architecture] - Protocol pattern, error handling
- [Source: project-context.md#FastMCP-Adapter-Rules] - Client ownership, layer rules
- [Source: project-context.md#Cache-Rules] - TTL for GDELT (1 hour)
- [Source: epics.md#Story-1.5] - Acceptance criteria
- [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) - API documentation

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

- [ ] GDELTAdapter class created implementing OSINTAdapter protocol
- [ ] source_name = "gdelt" and base_quality_tier = QualityTier.MEDIUM
- [ ] Adapter-owned httpx.AsyncClient with 10s timeout
- [ ] query() method queries GDELT API v2
- [ ] Empty results return OSINTResult(status=NO_DATA)
- [ ] Timeout raises AdapterTimeoutError with chained exception
- [ ] Results cached with TTL from config
- [ ] health_check() verifies API reachability
- [ ] close() method cleans up client
- [ ] Test fixtures created (gdelt_response.json, gdelt_empty.json)
- [ ] tests/adapters/test_gdelt.py created
- [ ] adapters/__init__.py updated with GDELTAdapter export
- [ ] `make type-check` passes
- [ ] `make lint` passes
- [ ] `make test` passes

### File List

_Files created/modified during implementation:_

- [ ] src/ignifer/adapters/gdelt.py (NEW)
- [ ] src/ignifer/adapters/__init__.py (UPDATED)
- [ ] tests/adapters/test_gdelt.py (NEW)
- [ ] tests/fixtures/gdelt_response.json (NEW)
- [ ] tests/fixtures/gdelt_empty.json (NEW)
