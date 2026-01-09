"""Tests for cache module."""

from datetime import datetime, timedelta, timezone

import pytest

from ignifer.cache import (
    CacheEntry,
    CacheManager,
    MemoryCache,
    cache_key,
)


class TestCacheKey:
    """Tests for cache_key function."""

    def test_cache_key_deterministic(self) -> None:
        """Cache keys should be deterministic for same inputs."""
        key1 = cache_key("gdelt", "topic", topic="Ukraine", days=7)
        key2 = cache_key("gdelt", "topic", topic="Ukraine", days=7)
        assert key1 == key2

    def test_cache_key_param_order_independent(self) -> None:
        """Cache keys should be independent of parameter order."""
        key1 = cache_key("gdelt", "topic", a=1, b=2)
        key2 = cache_key("gdelt", "topic", b=2, a=1)
        assert key1 == key2

    def test_cache_key_format(self) -> None:
        """Cache keys should follow {adapter}:{query}:{hash} format."""
        key = cache_key("gdelt", "topic", topic="test")
        assert key.startswith("gdelt:topic:")
        assert len(key.split(":")) == 3


class TestCacheEntry:
    """Tests for CacheEntry model."""

    def test_is_expired_false_when_within_ttl(self) -> None:
        """Entry should not be expired when within TTL."""
        entry = CacheEntry(
            key="test",
            data={"foo": "bar"},
            created_at=datetime.now(timezone.utc),
            ttl_seconds=3600,
            source="gdelt",
        )
        assert not entry.is_expired

    def test_is_expired_true_when_past_ttl(self) -> None:
        """Entry should be expired when past TTL."""
        entry = CacheEntry(
            key="test",
            data={"foo": "bar"},
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            ttl_seconds=3600,
            source="gdelt",
        )
        assert entry.is_expired


class TestMemoryCache:
    """Tests for MemoryCache (L1)."""

    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self) -> None:
        """Get on nonexistent key should return None."""
        cache = MemoryCache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_hit_returns_entry(self) -> None:
        """Get on existing key should return entry."""
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
    """Tests for CacheManager coordinating L1 and L2."""

    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self) -> None:
        """Get on nonexistent key should return None."""
        manager = CacheManager()
        result = await manager.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_allow_stale_returns_expired_with_flag(self) -> None:
        """Get with allow_stale should return expired entries with flag."""
        manager = CacheManager()
        # Set entry that's already expired
        await manager._l1.set(
            "test",
            CacheEntry(
                key="test",
                data={"foo": "bar"},
                created_at=datetime.now(timezone.utc) - timedelta(hours=2),
                ttl_seconds=3600,
                source="gdelt",
            ),
        )

        # Without allow_stale, should return None
        result = await manager.get("test", allow_stale=False)
        assert result is None

        # With allow_stale, should return data with is_stale=True
        result = await manager.get("test", allow_stale=True)
        assert result is not None
        assert result.is_stale is True
        assert result.data == {"foo": "bar"}
