"""Multi-tier caching system with TTL support for Ignifer."""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite
from pydantic import BaseModel, ConfigDict, field_serializer

logger = logging.getLogger(__name__)


def cache_key(adapter: str, query: str, **params: Any) -> str:
    """Deterministic cache key generation.

    Format: {adapter}:{query}:{params_hash}
    Hash is first 12 chars of SHA256 of sorted JSON params.

    Args:
        adapter: Adapter name (e.g., "gdelt", "opensky")
        query: Query type (e.g., "topic", "flights")
        **params: Query parameters

    Returns:
        Cache key string in format {adapter}:{query}:{params_hash}
    """
    sorted_params = sorted(params.items())
    params_hash = hashlib.sha256(json.dumps(sorted_params, sort_keys=True).encode()).hexdigest()[
        :12
    ]
    return f"{adapter}:{query}:{params_hash}"


class CacheEntry(BaseModel):
    """Cache entry with metadata and expiration tracking."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    key: str
    data: dict[str, Any]
    created_at: datetime
    ttl_seconds: int
    source: str  # adapter name for invalidation by source

    @field_serializer("created_at")
    def serialize_dt(self, dt: datetime) -> str:
        """Serialize datetime to ISO format."""
        return dt.isoformat()

    @property
    def expires_at(self) -> datetime:
        """Calculate expiration timestamp."""
        return self.created_at + timedelta(seconds=self.ttl_seconds)

    @property
    def is_expired(self) -> bool:
        """Check if entry has passed TTL."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_stale(self) -> bool:
        """Alias for is_expired, used for stale-while-revalidate semantics."""
        return self.is_expired


class MemoryCache:
    """L1 in-memory cache with dict-based storage."""

    def __init__(self) -> None:
        """Initialize empty memory cache."""
        self._cache: dict[str, CacheEntry] = {}

    async def get(self, key: str) -> CacheEntry | None:
        """Retrieve entry from memory cache.

        Args:
            key: Cache key

        Returns:
            CacheEntry if found, None otherwise
        """
        entry = self._cache.get(key)
        if entry is None:
            logger.debug(f"L1 cache miss: {key}")
            return None
        logger.debug(f"L1 cache hit: {key}")
        return entry

    async def set(self, key: str, entry: CacheEntry) -> None:
        """Store entry in memory cache.

        Args:
            key: Cache key
            entry: CacheEntry to store
        """
        self._cache[key] = entry
        logger.debug(f"L1 cache set: {key}")

    async def invalidate(self, key: str) -> bool:
        """Remove entry from memory cache.

        Args:
            key: Cache key

        Returns:
            True if entry was removed, False if not found
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"L1 cache invalidated: {key}")
            return True
        return False

    async def invalidate_by_source(self, source: str) -> int:
        """Remove all entries for a source adapter.

        Args:
            source: Adapter name

        Returns:
            Number of entries removed
        """
        keys_to_remove = [k for k, v in self._cache.items() if v.source == source]
        for key in keys_to_remove:
            del self._cache[key]
        logger.debug(f"L1 cache invalidated {len(keys_to_remove)} entries for source: {source}")
        return len(keys_to_remove)

    async def clear(self) -> None:
        """Clear all entries from memory cache."""
        count = len(self._cache)
        self._cache.clear()
        logger.debug(f"L1 cache cleared: {count} entries")


class SQLiteCache:
    """L2 SQLite cache with WAL mode for persistence."""

    def __init__(self, db_path: str | Path = "~/.cache/ignifer/cache.db") -> None:
        """Initialize SQLite cache with database path.

        Args:
            db_path: Path to SQLite database file
        """
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
        """Close SQLite connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def get(self, key: str) -> CacheEntry | None:
        """Retrieve entry from SQLite cache.

        Args:
            key: Cache key

        Returns:
            CacheEntry if found, None otherwise
        """
        if not self._conn:
            await self.connect()

        assert self._conn is not None  # For mypy
        cursor = await self._conn.execute(
            "SELECT key, data, created_at, ttl_seconds, source FROM cache WHERE key = ?",
            (key,),
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
        """Store entry in SQLite cache.

        Args:
            key: Cache key
            entry: CacheEntry to store
        """
        if not self._conn:
            await self.connect()

        assert self._conn is not None  # For mypy
        await self._conn.execute(
            """INSERT OR REPLACE INTO cache (key, data, created_at, ttl_seconds, source)
               VALUES (?, ?, ?, ?, ?)""",
            (
                entry.key,
                json.dumps(entry.data),
                entry.created_at.isoformat(),
                entry.ttl_seconds,
                entry.source,
            ),
        )
        await self._conn.commit()
        logger.debug(f"L2 cache set: {key}")

    async def invalidate(self, key: str) -> bool:
        """Remove entry from SQLite cache.

        Args:
            key: Cache key

        Returns:
            True if entry was removed, False if not found
        """
        if not self._conn:
            await self.connect()

        assert self._conn is not None  # For mypy
        cursor = await self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        await self._conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug(f"L2 cache invalidated: {key}")
        return deleted

    async def invalidate_by_source(self, source: str) -> int:
        """Remove all entries for a source adapter.

        Args:
            source: Adapter name

        Returns:
            Number of entries removed
        """
        if not self._conn:
            await self.connect()

        assert self._conn is not None  # For mypy
        cursor = await self._conn.execute("DELETE FROM cache WHERE source = ?", (source,))
        await self._conn.commit()
        count = cursor.rowcount
        logger.debug(f"L2 cache invalidated {count} entries for source: {source}")
        return count

    async def clear(self) -> None:
        """Clear all entries from SQLite cache."""
        if not self._conn:
            await self.connect()

        assert self._conn is not None  # For mypy
        await self._conn.execute("DELETE FROM cache")
        await self._conn.commit()
        logger.debug("L2 cache cleared")


class CacheResult:
    """Result from cache lookup with stale indicator."""

    def __init__(self, data: dict[str, Any] | None, is_stale: bool = False) -> None:
        """Initialize cache result.

        Args:
            data: Cached data
            is_stale: Whether data is expired
        """
        self.data = data
        self.is_stale = is_stale


class CacheManager:
    """Coordinates L1 (memory) and L2 (SQLite) cache tiers."""

    def __init__(self, l1: MemoryCache | None = None, l2: SQLiteCache | None = None) -> None:
        """Initialize cache manager with L1 and L2 tiers.

        Args:
            l1: MemoryCache instance (creates default if None)
            l2: SQLiteCache instance (creates default if None)
        """
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
        """Store in both L1 and L2 caches.

        Args:
            key: Cache key
            data: Data to cache
            ttl_seconds: Time-to-live in seconds
            source: Adapter name
        """
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
        """Invalidate entry from both tiers.

        Args:
            key: Cache key

        Returns:
            True if entry was removed from either tier
        """
        l1_result = await self._l1.invalidate(key)
        l2_result = await self._l2.invalidate(key)
        return l1_result or l2_result

    async def invalidate_by_source(self, source: str) -> int:
        """Invalidate all entries for a source from both tiers.

        Args:
            source: Adapter name

        Returns:
            Number of entries removed (from L2, source of truth)
        """
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


__all__ = [
    "cache_key",
    "CacheEntry",
    "CacheResult",
    "MemoryCache",
    "SQLiteCache",
    "CacheManager",
]
