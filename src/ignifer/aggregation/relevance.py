"""Source relevance engine for intelligent source selection.

Analyzes queries to determine which OSINT data sources are most relevant,
scoring each source based on query type and context.
"""

import logging
import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from ignifer.config import Settings, get_settings
from ignifer.models import QueryParams

logger = logging.getLogger(__name__)


class RelevanceScore(str, Enum):
    """Source relevance scoring levels."""

    HIGH = "high"
    MEDIUM_HIGH = "medium_high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def numeric_value(self) -> float:
        """Numeric value for sorting (higher is better)."""
        return {
            RelevanceScore.HIGH: 1.0,
            RelevanceScore.MEDIUM_HIGH: 0.75,
            RelevanceScore.MEDIUM: 0.5,
            RelevanceScore.LOW: 0.25,
        }[self]


class QueryType(str, Enum):
    """Query type classification."""

    COUNTRY = "country"
    PERSON = "person"
    ORGANIZATION = "organization"
    VESSEL = "vessel"
    AIRCRAFT = "aircraft"
    GENERAL = "general"


class SourceRelevance(BaseModel):
    """Relevance assessment for a single source."""

    model_config = ConfigDict(str_strip_whitespace=True)

    source_name: str
    score: RelevanceScore
    reasoning: str
    available: bool = True
    unavailable_reason: str | None = None


class RelevanceResult(BaseModel):
    """Complete relevance analysis result."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str
    query_type: str  # QueryType value
    sources: list[SourceRelevance] = Field(default_factory=list)
    available_sources: list[str] = Field(default_factory=list)
    unavailable_sources: list[str] = Field(default_factory=list)

    def get_high_relevance_sources(self) -> list[str]:
        """Get list of available HIGH relevance source names."""
        return [
            s.source_name
            for s in self.sources
            if s.score == RelevanceScore.HIGH and s.available
        ]


# Country name patterns
COUNTRY_KEYWORDS: set[str] = {
    "country",
    "nation",
    "region",
    "government of",
    "ministry of",
    "republic of",
}

# Common country names for detection
COMMON_COUNTRIES: set[str] = {
    "afghanistan",
    "albania",
    "algeria",
    "argentina",
    "australia",
    "austria",
    "bangladesh",
    "belgium",
    "brazil",
    "bulgaria",
    "cambodia",
    "cameroon",
    "canada",
    "chile",
    "china",
    "colombia",
    "croatia",
    "cuba",
    "czech republic",
    "denmark",
    "egypt",
    "ethiopia",
    "finland",
    "france",
    "germany",
    "ghana",
    "greece",
    "guatemala",
    "haiti",
    "hungary",
    "india",
    "indonesia",
    "iran",
    "iraq",
    "ireland",
    "israel",
    "italy",
    "japan",
    "jordan",
    "kazakhstan",
    "kenya",
    "kuwait",
    "laos",
    "lebanon",
    "libya",
    "malaysia",
    "mexico",
    "morocco",
    "mozambique",
    "myanmar",
    "netherlands",
    "new zealand",
    "nigeria",
    "north korea",
    "norway",
    "pakistan",
    "palestine",
    "panama",
    "peru",
    "philippines",
    "poland",
    "portugal",
    "qatar",
    "romania",
    "russia",
    "saudi arabia",
    "senegal",
    "serbia",
    "singapore",
    "south africa",
    "south korea",
    "south sudan",
    "spain",
    "sri lanka",
    "sudan",
    "sweden",
    "switzerland",
    "syria",
    "taiwan",
    "tanzania",
    "thailand",
    "tunisia",
    "turkey",
    "uganda",
    "ukraine",
    "united arab emirates",
    "uae",
    "united kingdom",
    "uk",
    "united states",
    "usa",
    "uzbekistan",
    "venezuela",
    "vietnam",
    "yemen",
    "zambia",
    "zimbabwe",
}

# Person detection keywords
PERSON_KEYWORDS: set[str] = {
    "person",
    "individual",
    "ceo",
    "leader",
    "president",
    "minister",
    "chairman",
    "director",
    "oligarch",
    "politician",
    "official",
    "executive",
}

# Vessel detection patterns and keywords
VESSEL_KEYWORDS: set[str] = {
    "vessel",
    "ship",
    "maritime",
    "cargo",
    "tanker",
    "container",
    "freighter",
    "yacht",
    "fishing boat",
    "track vessel",
}

# Aircraft detection patterns and keywords
AIRCRAFT_KEYWORDS: set[str] = {
    "flight",
    "aircraft",
    "plane",
    "aviation",
    "track flight",
    "helicopter",
    "jet",
    "airline",
}

# Organization detection keywords
ORGANIZATION_KEYWORDS: set[str] = {
    "company",
    "corporation",
    "organization",
    "ngo",
    "agency",
    "bank",
    "firm",
    "enterprise",
    "group",
    "foundation",
}

# Organization suffixes
ORGANIZATION_SUFFIXES: tuple[str, ...] = (
    "inc",
    "llc",
    "ltd",
    "corp",
    "gmbh",
    "plc",
    "ag",
    "sa",
    "bv",
    "nv",
)


class SourceRelevanceEngine:
    """Engine for analyzing query relevance to data sources.

    Analyzes query text and parameters to determine which OSINT sources
    are most relevant, considering both query type and source availability.

    Attributes:
        _settings: Settings instance for credential checking.
    """

    # All available sources
    ALL_SOURCES: tuple[str, ...] = (
        "gdelt",
        "worldbank",
        "wikidata",
        "opensky",
        "aisstream",
        "opensanctions",
    )

    # Sources that don't require authentication
    ALWAYS_AVAILABLE_SOURCES: set[str] = {
        "gdelt",
        "worldbank",
        "wikidata",
        "opensanctions",
    }

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the source relevance engine.

        Args:
            settings: Optional Settings instance. Uses get_settings() if not provided.
        """
        self._settings = settings or get_settings()

    async def analyze(
        self, query: str, params: QueryParams | None = None
    ) -> RelevanceResult:
        """Analyze query to determine relevant data sources.

        Args:
            query: The query text to analyze.
            params: Optional query parameters for additional context.

        Returns:
            RelevanceResult with ranked sources and availability information.
        """
        logger.info(f"Analyzing query relevance: {query}")

        # Detect query type
        query_type = self._detect_query_type(query)
        logger.debug(f"Detected query type: {query_type.value}")

        # Score all sources
        source_relevances: list[SourceRelevance] = []
        available_sources: list[str] = []
        unavailable_sources: list[str] = []

        for source_name in self.ALL_SOURCES:
            # Get relevance score and reasoning
            score, reasoning = self._score_source(source_name, query_type, query)

            # Check availability
            is_available, unavailable_reason = self._check_source_availability(
                source_name
            )

            source_relevance = SourceRelevance(
                source_name=source_name,
                score=score,
                reasoning=reasoning,
                available=is_available,
                unavailable_reason=unavailable_reason,
            )
            source_relevances.append(source_relevance)

            if is_available:
                available_sources.append(source_name)
            else:
                unavailable_sources.append(source_name)

        # Sort by score (descending)
        source_relevances.sort(key=lambda s: s.score.numeric_value, reverse=True)

        result = RelevanceResult(
            query=query,
            query_type=query_type.value,
            sources=source_relevances,
            available_sources=available_sources,
            unavailable_sources=unavailable_sources,
        )

        logger.info(
            f"Relevance analysis complete: {len(available_sources)} available, "
            f"{len(unavailable_sources)} unavailable sources"
        )

        return result

    def _detect_query_type(self, query: str) -> QueryType:
        """Detect the type of entity being queried.

        Args:
            query: The query text to analyze.

        Returns:
            QueryType indicating the detected entity type.
        """
        query_lower = query.lower()

        # Check for vessel patterns first (IMO/MMSI numbers)
        if self._is_vessel_query(query_lower):
            return QueryType.VESSEL

        # Check for aircraft patterns (callsigns, tail numbers)
        if self._is_aircraft_query(query_lower):
            return QueryType.AIRCRAFT

        # Check for country
        if self._is_country_query(query_lower):
            return QueryType.COUNTRY

        # Check for organization
        if self._is_organization_query(query_lower):
            return QueryType.ORGANIZATION

        # Check for person
        if self._is_person_query(query_lower):
            return QueryType.PERSON

        # Default to general
        return QueryType.GENERAL

    def _is_vessel_query(self, query_lower: str) -> bool:
        """Check if query is about a vessel.

        Args:
            query_lower: Lowercase query text.

        Returns:
            True if query appears to be about a vessel.
        """
        # Check for IMO or MMSI patterns
        if re.search(r"\bimo\s*\d+\b", query_lower):
            return True
        if re.search(r"\bmmsi\s*\d+\b", query_lower):
            return True

        # Check for vessel keywords
        return any(keyword in query_lower for keyword in VESSEL_KEYWORDS)

    def _is_aircraft_query(self, query_lower: str) -> bool:
        """Check if query is about an aircraft.

        Args:
            query_lower: Lowercase query text.

        Returns:
            True if query appears to be about an aircraft.
        """
        # Check for callsign pattern (e.g., UAL123, BAW456)
        # Airlines use 2-3 letter ICAO codes followed by 1-4 digits
        if re.search(r"\b[a-z]{2,3}\d{1,4}\b", query_lower):
            return True

        # Check for tail number patterns (e.g., N12345, G-ABCD, VP-ABC)
        # US: N followed by up to 5 alphanumeric characters
        # UK: G-XXXX format
        # Other countries: 1-2 letter prefix, hyphen, 3-5 alphanumeric
        if re.search(r"\bn\d{1,5}[a-z]{0,2}\b", query_lower):
            return True
        if re.search(r"\b[a-z]{1,2}-[a-z0-9]{3,5}\b", query_lower):
            return True

        # Check for aircraft keywords
        return any(keyword in query_lower for keyword in AIRCRAFT_KEYWORDS)

    def _is_country_query(self, query_lower: str) -> bool:
        """Check if query is about a country.

        Args:
            query_lower: Lowercase query text.

        Returns:
            True if query appears to be about a country.
        """
        # Check for country keywords
        if any(keyword in query_lower for keyword in COUNTRY_KEYWORDS):
            return True

        # Check for known country names
        return any(country in query_lower for country in COMMON_COUNTRIES)

    def _is_organization_query(self, query_lower: str) -> bool:
        """Check if query is about an organization.

        Args:
            query_lower: Lowercase query text.

        Returns:
            True if query appears to be about an organization.
        """
        # Check for organization keywords
        if any(keyword in query_lower for keyword in ORGANIZATION_KEYWORDS):
            return True

        # Check for organization suffixes
        words = query_lower.split()
        return any(word.rstrip(".,") in ORGANIZATION_SUFFIXES for word in words)

    def _is_person_query(self, query_lower: str) -> bool:
        """Check if query is about a person.

        Args:
            query_lower: Lowercase query text.

        Returns:
            True if query appears to be about a person.
        """
        # Check for person keywords - these are strong signals
        if any(keyword in query_lower for keyword in PERSON_KEYWORDS):
            return True

        return False

    def _score_source(
        self, source_name: str, query_type: QueryType, query: str
    ) -> tuple[RelevanceScore, str]:
        """Score a source's relevance for a given query type.

        Args:
            source_name: Name of the source to score.
            query_type: Detected query type.
            query: Original query text.

        Returns:
            Tuple of (RelevanceScore, reasoning string).
        """
        query_lower = query.lower()

        if source_name == "gdelt":
            return self._score_gdelt(query_type, query_lower)
        elif source_name == "worldbank":
            return self._score_worldbank(query_type, query_lower)
        elif source_name == "wikidata":
            return self._score_wikidata(query_type, query_lower)
        elif source_name == "opensky":
            return self._score_opensky(query_type, query_lower)
        elif source_name == "aisstream":
            return self._score_aisstream(query_type, query_lower)
        elif source_name == "opensanctions":
            return self._score_opensanctions(query_type, query_lower)
        else:
            return RelevanceScore.LOW, f"Unknown source: {source_name}"

    def _score_gdelt(
        self, query_type: QueryType, query_lower: str
    ) -> tuple[RelevanceScore, str]:
        """Score GDELT relevance.

        Args:
            query_type: Detected query type.
            query_lower: Lowercase query text.

        Returns:
            Tuple of (RelevanceScore, reasoning).
        """
        if query_type == QueryType.COUNTRY:
            return RelevanceScore.HIGH, "GDELT provides comprehensive news coverage for countries"
        elif query_type == QueryType.PERSON:
            return RelevanceScore.MEDIUM, "GDELT may have news mentions of this person"
        elif query_type == QueryType.ORGANIZATION:
            return RelevanceScore.MEDIUM, "GDELT may have news coverage of this organization"
        elif query_type == QueryType.VESSEL:
            return RelevanceScore.MEDIUM, "GDELT may have news about this vessel"
        elif query_type == QueryType.AIRCRAFT:
            return RelevanceScore.MEDIUM, "GDELT may have news about aviation incidents"
        else:
            return RelevanceScore.MEDIUM, "GDELT provides general news coverage"

    def _score_worldbank(
        self, query_type: QueryType, query_lower: str
    ) -> tuple[RelevanceScore, str]:
        """Score World Bank relevance.

        Args:
            query_type: Detected query type.
            query_lower: Lowercase query text.

        Returns:
            Tuple of (RelevanceScore, reasoning).
        """
        if query_type == QueryType.COUNTRY:
            return (
                RelevanceScore.HIGH,
                "World Bank provides economic indicators for countries",
            )
        elif query_type == QueryType.ORGANIZATION:
            return (
                RelevanceScore.LOW,
                "World Bank focuses on country-level data, not organizations",
            )
        else:
            return RelevanceScore.LOW, "World Bank focuses on country economic data"

    def _score_wikidata(
        self, query_type: QueryType, query_lower: str
    ) -> tuple[RelevanceScore, str]:
        """Score Wikidata relevance.

        Args:
            query_type: Detected query type.
            query_lower: Lowercase query text.

        Returns:
            Tuple of (RelevanceScore, reasoning).
        """
        if query_type == QueryType.PERSON:
            return RelevanceScore.HIGH, "Wikidata provides detailed entity information for people"
        elif query_type == QueryType.VESSEL:
            return RelevanceScore.HIGH, "Wikidata has vessel entity data and identifiers"
        elif query_type == QueryType.ORGANIZATION:
            return RelevanceScore.HIGH, "Wikidata provides organization entity information"
        elif query_type == QueryType.COUNTRY:
            return RelevanceScore.MEDIUM, "Wikidata provides country entity context"
        elif query_type == QueryType.AIRCRAFT:
            return RelevanceScore.MEDIUM, "Wikidata may have aircraft type information"
        else:
            return RelevanceScore.MEDIUM, "Wikidata provides general entity information"

    def _score_opensky(
        self, query_type: QueryType, query_lower: str
    ) -> tuple[RelevanceScore, str]:
        """Score OpenSky relevance.

        Args:
            query_type: Detected query type.
            query_lower: Lowercase query text.

        Returns:
            Tuple of (RelevanceScore, reasoning).
        """
        if query_type == QueryType.AIRCRAFT:
            return RelevanceScore.HIGH, "OpenSky provides real-time aircraft tracking"
        elif query_type == QueryType.COUNTRY:
            # Check for aviation context
            if any(kw in query_lower for kw in AIRCRAFT_KEYWORDS):
                return (
                    RelevanceScore.MEDIUM_HIGH,
                    "OpenSky can track aircraft in this region",
                )
            return RelevanceScore.LOW, "OpenSky focuses on aircraft, not country analysis"
        else:
            return RelevanceScore.LOW, "OpenSky is specific to aircraft tracking"

    def _score_aisstream(
        self, query_type: QueryType, query_lower: str
    ) -> tuple[RelevanceScore, str]:
        """Score AISStream relevance.

        Args:
            query_type: Detected query type.
            query_lower: Lowercase query text.

        Returns:
            Tuple of (RelevanceScore, reasoning).
        """
        if query_type == QueryType.VESSEL:
            return RelevanceScore.HIGH, "AISStream provides real-time vessel position tracking"
        elif query_type == QueryType.COUNTRY:
            # Check for maritime context
            if any(kw in query_lower for kw in VESSEL_KEYWORDS):
                return (
                    RelevanceScore.MEDIUM_HIGH,
                    "AISStream can track vessels in this region",
                )
            return RelevanceScore.LOW, "AISStream focuses on vessels, not country analysis"
        else:
            return RelevanceScore.LOW, "AISStream is specific to vessel tracking"

    def _score_opensanctions(
        self, query_type: QueryType, query_lower: str
    ) -> tuple[RelevanceScore, str]:
        """Score OpenSanctions relevance.

        Args:
            query_type: Detected query type.
            query_lower: Lowercase query text.

        Returns:
            Tuple of (RelevanceScore, reasoning).
        """
        if query_type == QueryType.PERSON:
            return (
                RelevanceScore.HIGH,
                "OpenSanctions provides sanctions and PEP status for individuals",
            )
        elif query_type == QueryType.VESSEL:
            return RelevanceScore.HIGH, "OpenSanctions tracks sanctioned vessels"
        elif query_type == QueryType.ORGANIZATION:
            return (
                RelevanceScore.HIGH,
                "OpenSanctions provides sanctions data for organizations",
            )
        elif query_type == QueryType.COUNTRY:
            return (
                RelevanceScore.MEDIUM,
                "OpenSanctions can identify sanctioned entities in this region",
            )
        else:
            return RelevanceScore.MEDIUM, "OpenSanctions provides sanctions screening"

    def _check_source_availability(
        self, source_name: str
    ) -> tuple[bool, str | None]:
        """Check if a source is available (has required credentials).

        Args:
            source_name: Name of the source to check.

        Returns:
            Tuple of (is_available, error_message_if_not).
        """
        # Always available sources (no auth required)
        if source_name in self.ALWAYS_AVAILABLE_SOURCES:
            return True, None

        # Check credentials for auth-required sources
        if source_name == "opensky":
            if self._settings.has_opensky_credentials():
                return True, None
            return False, Settings.get_credential_error_message("opensky")

        if source_name == "aisstream":
            if self._settings.has_aisstream_credentials():
                return True, None
            return False, Settings.get_credential_error_message("aisstream")

        # Unknown source - assume available
        return True, None


__all__ = [
    "RelevanceScore",
    "QueryType",
    "SourceRelevance",
    "RelevanceResult",
    "SourceRelevanceEngine",
]
