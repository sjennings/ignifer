"""Shared pytest fixtures for Ignifer tests."""

import pytest

from ignifer.cache import CacheManager


@pytest.fixture
def sample_topic() -> str:
    """Sample topic for testing."""
    return "Ukraine"


@pytest.fixture
async def cache_manager():
    """Provide a CacheManager that is properly closed after tests."""
    manager = CacheManager()
    yield manager
    await manager.close()
