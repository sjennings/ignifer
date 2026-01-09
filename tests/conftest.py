"""Shared pytest fixtures for Ignifer tests."""

import pytest


@pytest.fixture
def sample_topic() -> str:
    """Sample topic for testing."""
    return "Ukraine"
