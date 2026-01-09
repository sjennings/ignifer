"""Cache test scenarios for parametrized testing."""

CACHE_TEST_SCENARIOS = [
    # (adapter, ttl_seconds, scenario, expect_cache_hit)
    ("gdelt", 3600, "within_ttl", True),
    ("gdelt", 3600, "expired", False),
    ("opensky", 300, "within_ttl", True),
    ("opensky", 300, "expired", False),
    ("wikidata", 604800, "within_ttl", True),
]
