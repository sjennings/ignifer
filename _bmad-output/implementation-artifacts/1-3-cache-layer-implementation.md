# Story 1.3: Cache Layer Implementation

Status: ready-for-dev

## Story

As a **developer**,
I want **a multi-tier caching system with TTL support**,
so that **API responses are cached to reduce latency and respect rate limits**.

## Acceptance Criteria

1. **AC1: Cache Module Created**
   - **Given** the models and config from Story 1.2
   - **When** I create `src/ignifer/cache.py`
   - **Then** it implements:
     - `cache_key(adapter: str, query: str, **params) -> str` function generating deterministic keys
     - `CacheEntry` model with: key, data, created_at, ttl_seconds, source
     - `MemoryCache` class (L1) with get/set/invalidate methods
     - `SQLiteCache` class (L2) with get/set/invalidate methods using WAL mode
     - `CacheManager` class coordinating L1 -> L2 lookup with stale-while-revalidate

2. **AC2: Cache Miss Behavior**
   - **Given** CacheManager is initialized
   - **When** I call `cache.get(key)` for a non-existent key
   - **Then** it returns `None`
   - **And** no errors are raised

3. **AC3: Cache Hit Behavior**
   - **Given** CacheManager has a cached entry within TTL
   - **When** I call `cache.get(key)`
   - **Then** it returns the cached data
   - **And** L1 is checked before L2
   - **And** cache hit is logged at DEBUG level

4. **AC4: Stale-While-Revalidate**
   - **Given** CacheManager has an expired entry
   - **When** I call `cache.get(key)` with `allow_stale=True`
   - **Then** it returns the stale data with `is_stale=True` flag
   - **And** a warning is logged about serving stale data

5. **AC5: Tests Pass**
   - **Given** cache.py exists
   - **When** I run `pytest tests/test_cache.py`
   - **Then** all cache scenarios pass including TTL expiration and L1/L2 coordination

## Tasks / Subtasks

- [ ] Task 1: Create CacheEntry model (AC: #1)
  - [ ] 1.1: Define CacheEntry Pydantic model with key, data, created_at, ttl_seconds, source
  - [ ] 1.2: Add is_expired property checking TTL
  - [ ] 1.3: Add is_stale property for stale-while-revalidate

- [ ] Task 2: Implement cache_key function (AC: #1)
  - [ ] 2.1: Create deterministic key with adapter:query:params_hash format
  - [ ] 2.2: Use SHA256 hash of sorted JSON params
  - [ ] 2.3: Truncate hash to 12 characters for readability

- [ ] Task 3: Implement MemoryCache (L1) (AC: #1, #2, #3)
  - [ ] 3.1: Create MemoryCache class with dict-based storage
  - [ ] 3.2: Implement async get(key) method
  - [ ] 3.3: Implement async set(key, entry) method
  - [ ] 3.4: Implement async invalidate(key) and invalidate_by_source(source) methods

- [ ] Task 4: Implement SQLiteCache (L2) (AC: #1, #2, #3)
  - [ ] 4.1: Create SQLiteCache class with aiosqlite
  - [ ] 4.2: Configure WAL mode and performance PRAGMAs
  - [ ] 4.3: Implement async get(key) method
  - [ ] 4.4: Implement async set(key, entry) method
  - [ ] 4.5: Implement async invalidate(key) and invalidate_by_source(source) methods
  - [ ] 4.6: Add connection lifecycle management (connect/close)

- [ ] Task 5: Implement CacheManager (AC: #1, #2, #3, #4)
  - [ ] 5.1: Create CacheManager coordinating L1 -> L2 lookup
  - [ ] 5.2: Implement get(key, allow_stale=False) with tier fallthrough
  - [ ] 5.3: Implement set(key, data, ttl, source) storing to both tiers
  - [ ] 5.4: Implement invalidate methods
  - [ ] 5.5: Promote L2 hits to L1 for faster subsequent access

- [ ] Task 6: Create tests (AC: #5)
  - [ ] 6.1: Create tests/test_cache.py
  - [ ] 6.2: Create tests/fixtures/cache_scenarios.py
  - [ ] 6.3: Test cache miss returns None
  - [ ] 6.4: Test cache hit within TTL
  - [ ] 6.5: Test L1 before L2 lookup order
  - [ ] 6.6: Test expired entry with allow_stale=True
  - [ ] 6.7: Test invalidation by key and by source

## Dev Notes

### CRITICAL: Architecture Compliance

**FROM project-context.md - Cache Rules:**

1. **Key format:** `{adapter}:{query_type}:{params_hash}`
2. **Include query type** in cache key to prevent collisions
3. **Parameter order independence** via sorted JSON + SHA256 hash
4. **TTL defaults from config.py** - DO NOT hardcode TTLs in cache module

**FROM architecture.md - Cache Architecture:**

| Decision | Choice |
|----------|--------|
| Key strategy | String concatenation with deterministic hash |
| Invalidation | TTL + manual |
| Storage tiers | L1 memory, L2 SQLite |

### File Location

| File | Path | Purpose |
|------|------|---------|
| cache.py | `src/ignifer/cache.py` | ALL cache logic (L1 + L2, split later when >300 lines) |

### Dependencies Required

Add to pyproject.toml `[project.dependencies]`:
```toml
"aiosqlite>=0.20",
```

**NOTE:** This dependency is NOT in the current pyproject.toml. You MUST add it.

### CacheEntry Model

```python
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, ConfigDict, field_serializer

class CacheEntry(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    key: str
    data: dict[str, Any]
    created_at: datetime
    ttl_seconds: int
    source: str  # adapter name for invalidation by source

    @field_serializer('created_at')
    def serialize_dt(self, dt: datetime) -> str:
        return dt.isoformat()

    @property
    def expires_at(self) -> datetime:
        from datetime import timedelta
        return self.created_at + timedelta(seconds=self.ttl_seconds)

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_stale(self) -> bool:
        """Alias for is_expired, used for stale-while-revalidate semantics."""
        return self.is_expired
```

### Cache Key Function (From Architecture)

```python
import hashlib
import json

def cache_key(adapter: str, query: str, **params) -> str:
    """Deterministic cache key generation.

    Format: {adapter}:{query}:{params_hash}
    Hash is first 12 chars of SHA256 of sorted JSON params.
    """
    sorted_params = sorted(params.items())
    params_hash = hashlib.sha256(
        json.dumps(sorted_params, sort_keys=True).encode()
    ).hexdigest()[:12]
    return f"{adapter}:{query}:{params_hash}"
```

### MemoryCache (L1) Implementation

```python
import logging
from typing import Any

logger = logging.getLogger(__name__)

class MemoryCache:
    """L1 in-memory cache with dict-based storage."""

    def __init__(self) -> None:
        self._cache: dict[str, CacheEntry] = {}

    async def get(self, key: str) -> CacheEntry | None:
        entry = self._cache.get(key)
        if entry is None:
            logger.debug(f"L1 cache miss: {key}")
            return None
        logger.debug(f"L1 cache hit: {key}")
        return entry

    async def set(self, key: str, entry: CacheEntry) -> None:
        self._cache[key] = entry
        logger.debug(f"L1 cache set: {key}")

    async def invalidate(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"L1 cache invalidated: {key}")
            return True
        return False

    async def invalidate_by_source(self, source: str) -> int:
        keys_to_remove = [k for k, v in self._cache.items() if v.source == source]
        for key in keys_to_remove:
            del self._cache[key]
        logger.debug(f"L1 cache invalidated {len(keys_to_remove)} entries for source: {source}")
        return len(keys_to_remove)

    async def clear(self) -> None:
        count = len(self._cache)
        self._cache.clear()
        logger.debug(f"L1 cache cleared: {count} entries")
```

### SQLiteCache (L2) Implementation

**CRITICAL: Use WAL mode for better concurrent read/write performance.**

```python
import aiosqlite
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

class SQLiteCache:
    """L2 SQLite cache with WAL mode for persistence."""

    def __init__(self, db_path: str | Path = "~/.cache/ignifer/cache.db") -> None:
        self._db_path = Path(db_path).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Initialize connection and configure SQLite for performance."""
        self._conn = await aiosqlite.connect(str(self._db_path), timeout=30.0)

        # Enable WAL mode for better concurrency
        await self._conn.execute("PRAGMA journal_mode=WAL")
        # Faster sync (less durable but faster)
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        # Increase cache size to 64MB
        await self._conn.execute("PRAGMA cache_size=-64000")

        # Create table if not exists
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                ttl_seconds INTEGER NOT NULL,
                source TEXT NOT NULL
            )
        """)
        await self._conn.commit()
        logger.info(f"SQLite cache initialized at {self._db_path}")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def get(self, key: str) -> CacheEntry | None:
        if not self._conn:
            await self.connect()

        cursor = await self._conn.execute(
            "SELECT key, data, created_at, ttl_seconds, source FROM cache WHERE key = ?",
            (key,)
        )
        row = await cursor.fetchone()

        if row is None:
            logger.debug(f"L2 cache miss: {key}")
            return None

        logger.debug(f"L2 cache hit: {key}")
        return CacheEntry(
            key=row[0],
            data=json.loads(row[1]),
            created_at=datetime.fromisoformat(row[2]),
            ttl_seconds=row[3],
            source=row[4],
        )

    async def set(self, key: str, entry: CacheEntry) -> None:
        if not self._conn:
            await self.connect()

        await self._conn.execute(
            """INSERT OR REPLACE INTO cache (key, data, created_at, ttl_seconds, source)
               VALUES (?, ?, ?, ?, ?)""",
            (
                entry.key,
                json.dumps(entry.data),
                entry.created_at.isoformat(),
                entry.ttl_seconds,
                entry.source,
            )
        )
        await self._conn.commit()
        logger.debug(f"L2 cache set: {key}")

    async def invalidate(self, key: str) -> bool:
        if not self._conn:
            await self.connect()

        cursor = await self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        await self._conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug(f"L2 cache invalidated: {key}")
        return deleted

    async def invalidate_by_source(self, source: str) -> int:
        if not self._conn:
            await self.connect()

        cursor = await self._conn.execute("DELETE FROM cache WHERE source = ?", (source,))
        await self._conn.commit()
        count = cursor.rowcount
        logger.debug(f"L2 cache invalidated {count} entries for source: {source}")
        return count

    async def clear(self) -> None:
        if not self._conn:
            await self.connect()

        await self._conn.execute("DELETE FROM cache")
        await self._conn.commit()
        logger.debug("L2 cache cleared")
```

### CacheManager Implementation

```python
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

class CacheResult:
    """Result from cache lookup with stale indicator."""

    def __init__(self, data: dict[str, Any] | None, is_stale: bool = False) -> None:
        self.data = data
        self.is_stale = is_stale

class CacheManager:
    """Coordinates L1 (memory) and L2 (SQLite) cache tiers."""

    def __init__(self, l1: MemoryCache | None = None, l2: SQLiteCache | None = None) -> None:
        self._l1 = l1 or MemoryCache()
        self._l2 = l2 or SQLiteCache()

    async def get(self, key: str, allow_stale: bool = False) -> CacheResult | None:
        """Get from cache, checking L1 then L2.

        Args:
            key: Cache key
            allow_stale: If True, return expired entries with is_stale=True

        Returns:
            CacheResult with data and stale flag, or None if not found
        """
        # Check L1 first
        entry = await self._l1.get(key)

        if entry is None:
            # Check L2
            entry = await self._l2.get(key)
            if entry is not None:
                # Promote to L1 for faster subsequent access
                await self._l1.set(key, entry)

        if entry is None:
            return None

        # Check expiration
        if entry.is_expired:
            if allow_stale:
                logger.warning(f"Serving stale cache entry: {key}")
                return CacheResult(data=entry.data, is_stale=True)
            else:
                # Entry expired and stale not allowed
                return None

        return CacheResult(data=entry.data, is_stale=False)

    async def set(
        self,
        key: str,
        data: dict[str, Any],
        ttl_seconds: int,
        source: str,
    ) -> None:
        """Store in both L1 and L2 caches."""
        entry = CacheEntry(
            key=key,
            data=data,
            created_at=datetime.now(timezone.utc),
            ttl_seconds=ttl_seconds,
            source=source,
        )
        await self._l1.set(key, entry)
        await self._l2.set(key, entry)

    async def invalidate(self, key: str) -> bool:
        """Invalidate entry from both tiers."""
        l1_result = await self._l1.invalidate(key)
        l2_result = await self._l2.invalidate(key)
        return l1_result or l2_result

    async def invalidate_by_source(self, source: str) -> int:
        """Invalidate all entries for a source from both tiers."""
        l1_count = await self._l1.invalidate_by_source(source)
        l2_count = await self._l2.invalidate_by_source(source)
        return max(l1_count, l2_count)  # L2 is source of truth

    async def clear(self) -> None:
        """Clear both cache tiers."""
        await self._l1.clear()
        await self._l2.clear()

    async def close(self) -> None:
        """Close L2 connection."""
        await self._l2.close()
```

### Module Exports

```python
__all__ = [
    "cache_key",
    "CacheEntry",
    "CacheResult",
    "MemoryCache",
    "SQLiteCache",
    "CacheManager",
]
```

### Test Fixtures (tests/fixtures/cache_scenarios.py)

From architecture.md:

```python
"""Cache test scenarios for parametrized testing."""

CACHE_TEST_SCENARIOS = [
    # (adapter, ttl_seconds, scenario, expect_cache_hit)
    ("gdelt", 3600, "within_ttl", True),
    ("gdelt", 3600, "expired", False),
    ("opensky", 300, "within_ttl", True),
    ("opensky", 300, "expired", False),
    ("wikidata", 604800, "within_ttl", True),
]
```

### Test File Structure (tests/test_cache.py)

```python
"""Tests for cache module."""

import pytest
from datetime import datetime, timezone, timedelta
from ignifer.cache import (
    cache_key,
    CacheEntry,
    CacheManager,
    MemoryCache,
    SQLiteCache,
)


class TestCacheKey:
    def test_cache_key_deterministic(self) -> None:
        key1 = cache_key("gdelt", "topic", topic="Ukraine", days=7)
        key2 = cache_key("gdelt", "topic", topic="Ukraine", days=7)
        assert key1 == key2

    def test_cache_key_param_order_independent(self) -> None:
        key1 = cache_key("gdelt", "topic", a=1, b=2)
        key2 = cache_key("gdelt", "topic", b=2, a=1)
        assert key1 == key2

    def test_cache_key_format(self) -> None:
        key = cache_key("gdelt", "topic", topic="test")
        assert key.startswith("gdelt:topic:")
        assert len(key.split(":")) == 3


class TestCacheEntry:
    def test_is_expired_false_when_within_ttl(self) -> None:
        entry = CacheEntry(
            key="test",
            data={"foo": "bar"},
            created_at=datetime.now(timezone.utc),
            ttl_seconds=3600,
            source="gdelt",
        )
        assert not entry.is_expired

    def test_is_expired_true_when_past_ttl(self) -> None:
        entry = CacheEntry(
            key="test",
            data={"foo": "bar"},
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            ttl_seconds=3600,
            source="gdelt",
        )
        assert entry.is_expired


class TestMemoryCache:
    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self) -> None:
        cache = MemoryCache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_hit_returns_entry(self) -> None:
        cache = MemoryCache()
        entry = CacheEntry(
            key="test",
            data={"foo": "bar"},
            created_at=datetime.now(timezone.utc),
            ttl_seconds=3600,
            source="gdelt",
        )
        await cache.set("test", entry)
        result = await cache.get("test")
        assert result is not None
        assert result.data == {"foo": "bar"}


class TestCacheManager:
    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self) -> None:
        manager = CacheManager()
        result = await manager.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_allow_stale_returns_expired_with_flag(self) -> None:
        manager = CacheManager()
        # Set entry that's already expired
        await manager._l1.set("test", CacheEntry(
            key="test",
            data={"foo": "bar"},
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            ttl_seconds=3600,
            source="gdelt",
        ))

        # Without allow_stale, should return None
        result = await manager.get("test", allow_stale=False)
        assert result is None

        # With allow_stale, should return data with is_stale=True
        result = await manager.get("test", allow_stale=True)
        assert result is not None
        assert result.is_stale is True
        assert result.data == {"foo": "bar"}
```

### Anti-Patterns to AVOID

```python
# WRONG: Hardcoded TTL values in cache module
DEFAULT_TTL = 3600  # NO - get from config.py

# WRONG: Synchronous SQLite
import sqlite3  # NO - use aiosqlite

# WRONG: Shared database connection
_shared_conn = aiosqlite.connect(...)  # NO - per-instance

# WRONG: Naive datetime
created_at = datetime.now()  # NO - use datetime.now(timezone.utc)

# WRONG: camelCase
cacheKey: str  # NO - use cache_key: str
isExpired: bool  # NO - use is_expired: bool
```

### Previous Story Intelligence

**From Story 1.1:**
- Project uses `uv` for package management
- asyncio_mode = "auto" for pytest
- Strict mypy mode enabled

**From Story 1.2:**
- `config.py` provides TTL defaults via Settings class
- TTL values: `ttl_gdelt`, `ttl_opensky`, etc.
- Use `get_settings()` to access TTL values
- Import: `from ignifer.config import get_settings`

**Makefile targets available:**
- `make install` - Install with dev dependencies
- `make lint` - Run ruff checks
- `make type-check` - Run mypy strict
- `make test` - Run pytest with coverage

### Project Structure After This Story

```
src/ignifer/
├── __init__.py      # __version__ = "0.1.0"
├── __main__.py      # Entry point
├── server.py        # Stub with main()
├── models.py        # Pydantic models (Story 1.2)
├── config.py        # Settings and logging (Story 1.2)
├── cache.py         # NEW - Cache layer
└── adapters/
    └── __init__.py

tests/
├── conftest.py
├── test_cache.py    # NEW - Cache tests
├── adapters/
└── fixtures/
    └── cache_scenarios.py  # NEW - Test scenarios
```

### References

- [Source: architecture.md#Cache-Architecture] - Cache key helper, TTL defaults
- [Source: project-context.md#Cache-Rules] - Key format, TTL table
- [Source: epics.md#Story-1.3] - Acceptance criteria
- [aiosqlite documentation](https://aiosqlite.omnilib.dev/en/stable/) - Async SQLite library
- [SQLite WAL mode](https://sqlite.org/asyncvfs.html) - Write-ahead logging

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

- [ ] aiosqlite added to pyproject.toml dependencies
- [ ] CacheEntry model with is_expired property created
- [ ] cache_key function generates deterministic keys
- [ ] MemoryCache (L1) implemented with get/set/invalidate
- [ ] SQLiteCache (L2) implemented with WAL mode
- [ ] CacheManager coordinates L1 -> L2 lookup
- [ ] Stale-while-revalidate implemented
- [ ] tests/test_cache.py created
- [ ] tests/fixtures/cache_scenarios.py created
- [ ] `make type-check` passes
- [ ] `make lint` passes
- [ ] `make test` passes

### File List

_Files created/modified during implementation:_

- [ ] pyproject.toml (add aiosqlite dependency)
- [ ] src/ignifer/cache.py (NEW)
- [ ] tests/test_cache.py (NEW)
- [ ] tests/fixtures/cache_scenarios.py (NEW)
