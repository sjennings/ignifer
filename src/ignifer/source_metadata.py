"""Source metadata management for news domain quality tracking."""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from ignifer.models import SourceMetadataEntry

logger = logging.getLogger(__name__)

# Enrichment source constants
ENRICHMENT_GDELT_BASELINE = "auto:gdelt_baseline"
ENRICHMENT_LLM_ANALYZED = "auto:llm_analyzed"
ENRICHMENT_USER_OVERRIDE = "user_override"

# Maximum domains to include in analysis instructions
MAX_DOMAINS_FOR_ANALYSIS = 25


class SourceMetadataError(Exception):
    """Base exception for source metadata operations."""

    pass


class SourceMetadataNotFoundError(SourceMetadataError):
    """Domain not found in metadata table."""

    pass


class InvalidReliabilityGradeError(SourceMetadataError):
    """Invalid reliability grade (not A-F)."""

    def __init__(self, grade: str) -> None:
        super().__init__(f"Invalid reliability grade '{grade}'. Must be A-F.")
        self.grade = grade


class InvalidDomainError(SourceMetadataError):
    """Invalid or empty domain."""

    pass


# Known domain aliases for normalization
DOMAIN_ALIASES: dict[str, str] = {
    "news.bbc.co.uk": "bbc.co.uk",
    "bbc.com": "bbc.co.uk",
}

# Nation name aliases for normalization
NATION_ALIASES: dict[str, str] = {
    "peoples republic of china": "China",
    "prc": "China",
    "republic of china": "Taiwan",
    "roc": "Taiwan",
    "russian federation": "Russia",
    "united states of america": "United States",
    "usa": "United States",
    "uk": "United Kingdom",
    "great britain": "United Kingdom",
}

# Region detection keywords (ordered list - checked in order, more specific first)
REGION_KEYWORDS: list[tuple[str, str]] = [
    # More specific keywords first
    ("north korea", "North Korea"),
    ("south korea", "South Korea"),
    # General keywords
    ("taiwan", "Taiwan"),
    ("china", "China"),
    ("ukraine", "Ukraine"),
    ("russia", "Russia"),
    ("israel", "Israel"),
    ("gaza", "Palestine"),
    ("palestine", "Palestine"),
    ("iran", "Iran"),
    ("syria", "Syria"),
    ("korea", "South Korea"),  # Default if just "korea"
    ("japan", "Japan"),
    ("india", "India"),
    ("pakistan", "Pakistan"),
    ("afghanistan", "Afghanistan"),
    ("iraq", "Iraq"),
    ("yemen", "Yemen"),
    ("saudi", "Saudi Arabia"),
    ("turkey", "Turkey"),
    ("germany", "Germany"),
    ("france", "France"),
    ("uk", "United Kingdom"),
    ("britain", "United Kingdom"),
    ("brazil", "Brazil"),
    ("mexico", "Mexico"),
    ("venezuela", "Venezuela"),
    ("argentina", "Argentina"),
]


def normalize_domain(raw_domain: str) -> str:
    """Normalize domain for consistent lookups.

    Strategy: Keep meaningful domain info, strip only noise.
    - Strip 'www.' prefix
    - Lowercase
    - Keep full domain (bbc.co.uk stays bbc.co.uk, NOT just 'bbc')
    - Known aliases mapped explicitly

    Args:
        raw_domain: Raw domain string from article data

    Returns:
        Normalized domain string (e.g., 'bbc.co.uk', 'nytimes.com')

    Raises:
        InvalidDomainError: If domain is empty or whitespace
    """
    if not raw_domain or not raw_domain.strip():
        raise InvalidDomainError("Domain cannot be empty or whitespace")

    domain = raw_domain.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]

    if not domain:  # Was just "www."
        raise InvalidDomainError("Domain cannot be empty after normalization")

    return DOMAIN_ALIASES.get(domain, domain)


def normalize_nation(raw_nation: str) -> str:
    """Normalize nation name for consistent matching.

    Args:
        raw_nation: Raw nation name from GDELT or user input

    Returns:
        Normalized nation name
    """
    if not raw_nation:
        return raw_nation
    normalized = raw_nation.lower().strip()
    return NATION_ALIASES.get(normalized, raw_nation)


def detect_region(query: str, articles: list[dict[str, Any]]) -> str | None:
    """Detect primary region from query and article data.

    Algorithm:
    1. Check query for explicit country/region keywords
    2. If not found, analyze sourcecountry distribution from articles
    3. If >50% from one nation, use that as region
    4. If >3 distinct nations, return None (multi-region)

    Args:
        query: User's search query
        articles: List of article dicts with sourcecountry field

    Returns:
        Nation name string or None for multi-region
    """
    # Step 1: Keyword extraction from query
    query_lower = query.lower()
    for keyword, nation in REGION_KEYWORDS:
        if keyword in query_lower:
            return nation

    # Step 2: Analyze article sourcecountry distribution
    countries = [a.get("sourcecountry") for a in articles if a.get("sourcecountry")]
    if not countries:
        return None

    counts = Counter(countries)
    total = len(countries)
    top_country, top_count = counts.most_common(1)[0]

    # Step 3: >50% threshold
    if top_count / total > 0.5:
        return top_country

    # Step 4: >3 nations = multi-region
    if len(counts) > 3:
        return None

    return top_country  # Use plurality if <= 3 nations


class SourceMetadataManager:
    """Manages persistent source metadata in SQLite.

    Stores domain-level metadata including language, nation, political
    orientation, and IC-style reliability grades. Supports auto-enrichment
    from GDELT data and user overrides with rollback capability.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize manager with database path.

        Args:
            db_path: Path to SQLite database. Defaults to cache directory.
        """
        if db_path is None:
            # Use the cache directory (could be configured via settings in future)
            cache_dir = Path.home() / ".cache" / "ignifer"
            db_path = cache_dir / "cache.db"
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Initialize connection and create table if needed."""
        self._conn = await aiosqlite.connect(str(self._db_path), timeout=30.0)

        # Enable WAL mode for better concurrency
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")

        # Create table with CHECK constraint on reliability
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS source_metadata (
                domain TEXT PRIMARY KEY,
                language TEXT,
                nation TEXT,
                political_orientation TEXT,
                orientation_axis TEXT,
                orientation_tags TEXT,
                reliability TEXT CHECK(reliability IN ('A','B','C','D','E','F')),
                enrichment_source TEXT,
                enrichment_date TEXT,
                original_reliability TEXT,
                original_orientation TEXT
            )
        """)
        await self._conn.commit()
        logger.info(f"Source metadata table initialized at {self._db_path}")

    async def close(self) -> None:
        """Close SQLite connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _ensure_connected(self) -> None:
        """Ensure database connection is established."""
        if self._conn is None:
            await self.connect()

    async def get(self, domain: str) -> SourceMetadataEntry | None:
        """Retrieve metadata for a domain.

        Args:
            domain: Normalized domain name

        Returns:
            SourceMetadataEntry if found, None otherwise
        """
        await self._ensure_connected()
        assert self._conn is not None

        cursor = await self._conn.execute(
            """
            SELECT domain, language, nation, political_orientation,
                   orientation_axis, orientation_tags, reliability,
                   enrichment_source, enrichment_date,
                   original_reliability, original_orientation
            FROM source_metadata WHERE domain = ?
            """,
            (domain,),
        )
        row = await cursor.fetchone()

        if row is None:
            logger.debug(f"No metadata for domain: {domain}")
            return None

        return SourceMetadataEntry(
            domain=str(row[0]),
            language=str(row[1]) if row[1] else None,
            nation=str(row[2]) if row[2] else None,
            political_orientation=str(row[3]) if row[3] else None,
            orientation_axis=str(row[4]) if row[4] else None,
            orientation_tags=str(row[5]) if row[5] else "[]",
            reliability=str(row[6]) if row[6] else "C",
            enrichment_source=str(row[7]) if row[7] else "auto:gdelt_baseline",
            enrichment_date=str(row[8]) if row[8] else datetime.now(timezone.utc).isoformat(),
            original_reliability=str(row[9]) if row[9] else None,
            original_orientation=str(row[10]) if row[10] else None,
        )

    async def set(self, entry: SourceMetadataEntry) -> None:
        """Store or update metadata for a domain.

        Args:
            entry: SourceMetadataEntry to store
        """
        await self._ensure_connected()
        assert self._conn is not None

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO source_metadata
            (domain, language, nation, political_orientation,
             orientation_axis, orientation_tags, reliability,
             enrichment_source, enrichment_date,
             original_reliability, original_orientation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.domain,
                entry.language,
                entry.nation,
                entry.political_orientation,
                entry.orientation_axis,
                json.dumps(entry.orientation_tags),
                entry.reliability,
                entry.enrichment_source,
                entry.enrichment_date.isoformat()
                if isinstance(entry.enrichment_date, datetime)
                else entry.enrichment_date,
                entry.original_reliability,
                entry.original_orientation,
            ),
        )
        await self._conn.commit()
        logger.debug(f"Stored metadata for domain: {entry.domain}")

    async def enrich_from_gdelt(
        self, domain: str, article: dict[str, Any]
    ) -> SourceMetadataEntry:
        """Create baseline entry from GDELT article data. Race-safe.

        Uses INSERT OR IGNORE to handle concurrent briefings.

        Args:
            domain: Normalized domain name
            article: GDELT article dict with language, sourcecountry

        Returns:
            SourceMetadataEntry for the domain (existing or newly created)
        """
        await self._ensure_connected()
        assert self._conn is not None

        language = article.get("language")
        nation = article.get("sourcecountry")
        now = datetime.now(timezone.utc).isoformat()

        # Use INSERT OR IGNORE to handle race conditions
        await self._conn.execute(
            """
            INSERT OR IGNORE INTO source_metadata
            (domain, language, nation, reliability, enrichment_source, enrichment_date)
            VALUES (?, ?, ?, 'C', 'auto:gdelt_baseline', ?)
            """,
            (domain, language, nation, now),
        )
        await self._conn.commit()

        # Fetch to return (handles both insert and existing cases)
        entry = await self.get(domain)
        if entry is None:
            # Should not happen, but create default
            entry = SourceMetadataEntry(
                domain=domain,
                language=language,
                nation=nation,
                reliability="C",
                enrichment_source="auto:gdelt_baseline",
            )
        return entry

    async def _preserve_original_if_needed(self, domain: str, field: str) -> None:
        """Preserve original auto-enriched value before first user override.

        Args:
            domain: Domain to check
            field: Field being overridden ('reliability' or 'political_orientation')
        """
        await self._ensure_connected()
        assert self._conn is not None

        entry = await self.get(domain)
        if entry is None:
            return

        if field == "reliability" and entry.original_reliability is None:
            await self._conn.execute(
                "UPDATE source_metadata SET original_reliability = reliability WHERE domain = ?",
                (domain,),
            )
        elif field == "political_orientation" and entry.original_orientation is None:
            await self._conn.execute(
                "UPDATE source_metadata SET original_orientation = political_orientation WHERE domain = ?",
                (domain,),
            )

    async def _update(self, domain: str, field: str, value: str | None) -> None:
        """Update a single field for a domain.

        Args:
            domain: Domain to update
            field: Column name to update
            value: New value
        """
        await self._ensure_connected()
        assert self._conn is not None

        # Whitelist valid field names to prevent SQL injection
        valid_fields = {
            "language",
            "nation",
            "political_orientation",
            "orientation_axis",
            "reliability",
            "enrichment_source",
        }
        if field not in valid_fields:
            msg = f"Invalid field name: {field}"
            raise ValueError(msg)

        await self._conn.execute(
            f"UPDATE source_metadata SET {field} = ? WHERE domain = ?",  # noqa: S608
            (value, domain),
        )
        await self._conn.commit()

    async def set_reliability(self, domain: str, reliability: str) -> bool:
        """Update reliability with validation.

        Args:
            domain: Domain to update
            reliability: New reliability grade (A-F)

        Returns:
            True if successful

        Raises:
            InvalidReliabilityGradeError: If grade is not A-F
            SourceMetadataNotFoundError: If domain not found
        """
        if reliability.upper() not in ("A", "B", "C", "D", "E", "F"):
            raise InvalidReliabilityGradeError(reliability)

        entry = await self.get(domain)
        if entry is None:
            raise SourceMetadataNotFoundError(domain)

        await self._preserve_original_if_needed(domain, "reliability")
        await self._update(domain, "reliability", reliability.upper())
        await self._update(domain, "enrichment_source", "user_override")
        return True

    async def set_orientation(
        self, domain: str, orientation: str, axis: str | None
    ) -> bool:
        """Update orientation fields.

        Args:
            domain: Domain to update
            orientation: Political orientation description
            axis: Relevant orientation axis for region

        Returns:
            True if successful

        Raises:
            SourceMetadataNotFoundError: If domain not found
        """
        entry = await self.get(domain)
        if entry is None:
            raise SourceMetadataNotFoundError(domain)

        await self._preserve_original_if_needed(domain, "political_orientation")
        await self._update(domain, "political_orientation", orientation)
        if axis:
            await self._update(domain, "orientation_axis", axis)
        await self._update(domain, "enrichment_source", "user_override")
        return True

    async def set_nation(self, domain: str, nation: str) -> bool:
        """Update nation field.

        Args:
            domain: Domain to update
            nation: New nation value

        Returns:
            True if successful

        Raises:
            SourceMetadataNotFoundError: If domain not found
        """
        entry = await self.get(domain)
        if entry is None:
            raise SourceMetadataNotFoundError(domain)

        await self._update(domain, "nation", nation)
        await self._update(domain, "enrichment_source", "user_override")
        return True

    async def reset(self, domain: str) -> bool:
        """Restore original auto-enriched values.

        If original_reliability is NULL (never auto-enriched, only manually added),
        returns False with no changes.

        Args:
            domain: Domain to reset

        Returns:
            True if reset was performed, False if no original values to restore

        Raises:
            SourceMetadataNotFoundError: If domain not found
        """
        await self._ensure_connected()
        assert self._conn is not None

        entry = await self.get(domain)
        if entry is None:
            raise SourceMetadataNotFoundError(domain)

        if entry.original_reliability is None and entry.original_orientation is None:
            return False  # Nothing to reset to

        # Restore original values
        if entry.original_reliability:
            await self._update(domain, "reliability", entry.original_reliability)
        if entry.original_orientation:
            await self._update(domain, "political_orientation", entry.original_orientation)
        await self._update(domain, "enrichment_source", "auto:gdelt_baseline")
        return True


__all__ = [
    "SourceMetadataManager",
    "SourceMetadataError",
    "SourceMetadataNotFoundError",
    "InvalidReliabilityGradeError",
    "InvalidDomainError",
    "normalize_domain",
    "normalize_nation",
    "detect_region",
]
