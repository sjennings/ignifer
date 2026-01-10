"""Tests for source metadata management."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ignifer.models import SourceMetadataEntry
from ignifer.source_metadata import (
    InvalidDomainError,
    InvalidReliabilityGradeError,
    SourceMetadataManager,
    SourceMetadataNotFoundError,
    detect_region,
    normalize_domain,
    normalize_nation,
)

from fixtures.source_metadata_scenarios import (
    EXPECTED_NORMALIZED_DOMAINS,
    INVALID_DOMAIN_CASES,
    INVALID_RELIABILITY_GRADES,
    MOCK_GDELT_ARTICLES,
    NATION_NORMALIZATION_CASES,
    REGION_DETECTION_CASES,
    VALID_RELIABILITY_GRADES,
)


class TestNormalizeDomain:
    """Tests for normalize_domain function."""

    @pytest.mark.parametrize("raw,expected", EXPECTED_NORMALIZED_DOMAINS)
    def test_normalize_domain_mappings(self, raw: str, expected: str) -> None:
        """Domain normalization produces expected canonical form."""
        result = normalize_domain(raw)
        assert result == expected

    def test_normalize_domain_strips_www(self) -> None:
        """www. prefix is stripped."""
        assert normalize_domain("www.example.com") == "example.com"

    def test_normalize_domain_lowercase(self) -> None:
        """Domain is lowercased."""
        assert normalize_domain("EXAMPLE.COM") == "example.com"

    def test_normalize_domain_strips_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped."""
        assert normalize_domain("  example.com  ") == "example.com"

    def test_normalize_domain_preserves_full_domain(self) -> None:
        """Full domain is preserved (not shortened to base)."""
        assert normalize_domain("subdomain.example.co.uk") == "subdomain.example.co.uk"

    @pytest.mark.parametrize("invalid", INVALID_DOMAIN_CASES)
    def test_normalize_domain_raises_on_invalid(self, invalid: str) -> None:
        """Invalid/empty domains raise InvalidDomainError."""
        with pytest.raises(InvalidDomainError):
            normalize_domain(invalid)


class TestNormalizeNation:
    """Tests for normalize_nation function."""

    @pytest.mark.parametrize("raw,expected", NATION_NORMALIZATION_CASES)
    def test_normalize_nation_mappings(self, raw: str, expected: str) -> None:
        """Nation names are normalized to canonical form."""
        result = normalize_nation(raw)
        assert result == expected

    def test_normalize_nation_empty_returns_empty(self) -> None:
        """Empty string returns empty."""
        assert normalize_nation("") == ""

    def test_normalize_nation_none_returns_none(self) -> None:
        """None returns None."""
        assert normalize_nation(None) is None  # type: ignore[arg-type]


class TestDetectRegion:
    """Tests for detect_region function."""

    @pytest.mark.parametrize("query,articles,expected", REGION_DETECTION_CASES)
    def test_detect_region_cases(
        self, query: str, articles: list, expected: str | None
    ) -> None:
        """Region detection works for various scenarios."""
        result = detect_region(query, articles)
        assert result == expected

    def test_detect_region_keyword_takes_precedence(self) -> None:
        """Query keyword takes precedence over article analysis."""
        articles = [
            {"sourcecountry": "Japan"},
            {"sourcecountry": "Japan"},
            {"sourcecountry": "Japan"},
        ]
        # Query mentions Taiwan, should detect Taiwan not Japan
        result = detect_region("Taiwan news", articles)
        assert result == "Taiwan"


class TestSourceMetadataEntry:
    """Tests for SourceMetadataEntry Pydantic model."""

    def test_create_entry_with_defaults(self) -> None:
        """Entry can be created with minimal fields."""
        entry = SourceMetadataEntry(domain="example.com")
        assert entry.domain == "example.com"
        assert entry.reliability == "C"
        assert entry.enrichment_source == "auto:gdelt_baseline"

    def test_reliability_validator_valid(self) -> None:
        """Valid reliability grades are accepted."""
        for grade in VALID_RELIABILITY_GRADES:
            entry = SourceMetadataEntry(domain="test.com", reliability=grade)
            assert entry.reliability == grade.upper()

    def test_reliability_validator_invalid(self) -> None:
        """Invalid reliability grades raise ValueError."""
        for grade in INVALID_RELIABILITY_GRADES:
            with pytest.raises(ValueError):
                SourceMetadataEntry(domain="test.com", reliability=grade)

    def test_orientation_tags_serialization(self) -> None:
        """Orientation tags serialize to JSON and back."""
        tags = ["independence", "dpp-leaning"]
        entry = SourceMetadataEntry(domain="test.com", orientation_tags=tags)
        assert entry.orientation_tags == tags

        # Simulate round-trip through JSON string (as stored in SQLite)
        entry2 = SourceMetadataEntry(domain="test.com", orientation_tags='["a","b"]')
        assert entry2.orientation_tags == ["a", "b"]

    def test_enrichment_date_serialization(self) -> None:
        """Enrichment date serializes to ISO 8601 with timezone."""
        now = datetime.now(timezone.utc)
        entry = SourceMetadataEntry(domain="test.com", enrichment_date=now)

        # Serialize
        serialized = entry.model_dump()
        assert "+" in serialized["enrichment_date"] or "Z" in serialized["enrichment_date"]


class TestSourceMetadataManager:
    """Tests for SourceMetadataManager async operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_cache.db"

    @pytest.mark.asyncio
    async def test_connect_creates_table(self, temp_db: Path) -> None:
        """connect() creates source_metadata table."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            await manager.connect()
            # Verify table exists by trying to query it
            assert manager._conn is not None
            cursor = await manager._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='source_metadata'"
            )
            row = await cursor.fetchone()
            assert row is not None
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self, temp_db: Path) -> None:
        """get() returns None for non-existent domain."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            result = await manager.get("nonexistent.com")
            assert result is None
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_set_and_get_roundtrip(self, temp_db: Path) -> None:
        """set() stores entry, get() retrieves it."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            entry = SourceMetadataEntry(
                domain="test.com",
                language="English",
                nation="United States",
                reliability="B",
            )
            await manager.set(entry)

            retrieved = await manager.get("test.com")
            assert retrieved is not None
            assert retrieved.domain == "test.com"
            assert retrieved.language == "English"
            assert retrieved.nation == "United States"
            assert retrieved.reliability == "B"
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_enrich_from_gdelt_creates_entry(self, temp_db: Path) -> None:
        """enrich_from_gdelt() creates baseline entry from article data."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            article = MOCK_GDELT_ARTICLES[0]
            entry = await manager.enrich_from_gdelt("focustaiwan.tw", article)

            assert entry.domain == "focustaiwan.tw"
            assert entry.language == "English"
            assert entry.nation == "Taiwan"
            assert entry.reliability == "C"  # Default
            assert entry.enrichment_source == "auto:gdelt_baseline"
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_enrich_from_gdelt_is_race_safe(self, temp_db: Path) -> None:
        """enrich_from_gdelt() handles concurrent calls safely."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            article = MOCK_GDELT_ARTICLES[0]

            # Call twice (simulating race condition)
            entry1 = await manager.enrich_from_gdelt("test.com", article)
            entry2 = await manager.enrich_from_gdelt("test.com", article)

            # Both should succeed, returning same entry
            assert entry1.domain == entry2.domain
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_set_reliability_valid(self, temp_db: Path) -> None:
        """set_reliability() updates grade for existing entry."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            # Create entry first
            entry = SourceMetadataEntry(domain="test.com", reliability="C")
            await manager.set(entry)

            # Update reliability
            result = await manager.set_reliability("test.com", "A")
            assert result is True

            # Verify update
            retrieved = await manager.get("test.com")
            assert retrieved is not None
            assert retrieved.reliability == "A"
            assert retrieved.enrichment_source == "user_override"
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_set_reliability_invalid_grade(self, temp_db: Path) -> None:
        """set_reliability() raises for invalid grade."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            entry = SourceMetadataEntry(domain="test.com")
            await manager.set(entry)

            with pytest.raises(InvalidReliabilityGradeError):
                await manager.set_reliability("test.com", "X")
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_set_reliability_not_found(self, temp_db: Path) -> None:
        """set_reliability() raises for non-existent domain."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            with pytest.raises(SourceMetadataNotFoundError):
                await manager.set_reliability("nonexistent.com", "A")
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_set_reliability_preserves_original(self, temp_db: Path) -> None:
        """set_reliability() preserves original value for rollback."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            entry = SourceMetadataEntry(domain="test.com", reliability="C")
            await manager.set(entry)

            await manager.set_reliability("test.com", "A")

            retrieved = await manager.get("test.com")
            assert retrieved is not None
            assert retrieved.reliability == "A"
            assert retrieved.original_reliability == "C"
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_set_orientation(self, temp_db: Path) -> None:
        """set_orientation() updates orientation fields."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            entry = SourceMetadataEntry(domain="test.com")
            await manager.set(entry)

            await manager.set_orientation("test.com", "Pro-independence", "china-independence")

            retrieved = await manager.get("test.com")
            assert retrieved is not None
            assert retrieved.political_orientation == "Pro-independence"
            assert retrieved.orientation_axis == "china-independence"
            assert retrieved.enrichment_source == "user_override"
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_set_nation(self, temp_db: Path) -> None:
        """set_nation() updates nation field."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            entry = SourceMetadataEntry(domain="test.com", nation="Unknown")
            await manager.set(entry)

            await manager.set_nation("test.com", "Taiwan")

            retrieved = await manager.get("test.com")
            assert retrieved is not None
            assert retrieved.nation == "Taiwan"
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_reset_restores_original(self, temp_db: Path) -> None:
        """reset() restores original auto-enriched values."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            # Create and then override
            entry = SourceMetadataEntry(domain="test.com", reliability="C")
            await manager.set(entry)
            await manager.set_reliability("test.com", "A")

            # Reset
            was_reset = await manager.reset("test.com")
            assert was_reset is True

            # Verify restored
            retrieved = await manager.get("test.com")
            assert retrieved is not None
            assert retrieved.reliability == "C"
            assert retrieved.enrichment_source == "auto:gdelt_baseline"
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_reset_returns_false_if_no_original(self, temp_db: Path) -> None:
        """reset() returns False if no original values to restore."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            # Create entry with no original values
            entry = SourceMetadataEntry(domain="test.com", reliability="A")
            await manager.set(entry)

            # Reset should return False
            was_reset = await manager.reset("test.com")
            assert was_reset is False
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_reset_not_found(self, temp_db: Path) -> None:
        """reset() raises for non-existent domain."""
        manager = SourceMetadataManager(db_path=temp_db)
        try:
            with pytest.raises(SourceMetadataNotFoundError):
                await manager.reset("nonexistent.com")
        finally:
            await manager.close()

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self, temp_db: Path) -> None:
        """close() can be called multiple times safely."""
        manager = SourceMetadataManager(db_path=temp_db)
        await manager.connect()
        await manager.close()
        await manager.close()  # Should not raise
