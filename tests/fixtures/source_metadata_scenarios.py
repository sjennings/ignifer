"""Test fixtures for source metadata functionality."""

# Mock GDELT articles with domain, language, sourcecountry
MOCK_GDELT_ARTICLES = [
    {
        "title": "Taiwan Semiconductor Expansion Plans",
        "domain": "focustaiwan.tw",
        "language": "English",
        "sourcecountry": "Taiwan",
        "url": "https://focustaiwan.tw/business/202601100001",
        "seendate": "20260110",
    },
    {
        "title": "中國對台灣施壓",
        "domain": "udn.com",
        "language": "Chinese",
        "sourcecountry": "Taiwan",
        "url": "https://udn.com/news/story/202601100002",
        "seendate": "20260110",
    },
    {
        "title": "China Responds to US Taiwan Visit",
        "domain": "scmp.com",
        "language": "English",
        "sourcecountry": "Hong Kong",
        "url": "https://scmp.com/news/china/202601100003",
        "seendate": "20260109",
    },
    {
        "title": "Taiwan Chip Industry Analysis",
        "domain": "reuters.com",
        "language": "English",
        "sourcecountry": "United Kingdom",
        "url": "https://reuters.com/tech/202601100004",
        "seendate": "20260108",
    },
    {
        "title": "US Semiconductors Tariff Discussion",
        "domain": "nytimes.com",
        "language": "English",
        "sourcecountry": "United States",
        "url": "https://nytimes.com/2026/01/10/business/semiconductors.html",
        "seendate": "20260109",
    },
]

# Expected normalized domain mappings
EXPECTED_NORMALIZED_DOMAINS = [
    ("www.bbc.co.uk", "bbc.co.uk"),
    ("bbc.co.uk", "bbc.co.uk"),
    ("news.bbc.co.uk", "bbc.co.uk"),
    ("bbc.com", "bbc.co.uk"),
    ("www.reuters.com", "reuters.com"),
    ("reuters.com", "reuters.com"),
    ("REUTERS.COM", "reuters.com"),
    ("  scmp.com  ", "scmp.com"),
]

# Domain normalization edge cases that should raise errors
INVALID_DOMAIN_CASES = [
    "",
    "   ",
    "www.",
]

# Region detection test cases: (query, articles, expected_region)
REGION_DETECTION_CASES = [
    # Query keyword detection
    ("Taiwan semiconductors", [], "Taiwan"),
    ("China economy", [], "China"),
    ("Ukraine conflict", [], "Ukraine"),
    # Multi-word keyword
    ("North Korea missiles", [], "North Korea"),
    # Case insensitive
    ("TAIWAN technology", [], "Taiwan"),
    # No keyword, use article sourcecountry majority
    (
        "chip manufacturing",
        [
            {"sourcecountry": "Taiwan"},
            {"sourcecountry": "Taiwan"},
            {"sourcecountry": "Taiwan"},
            {"sourcecountry": "United States"},
        ],
        "Taiwan",  # >50% from Taiwan
    ),
    # No keyword, plurality with <=3 nations
    (
        "regional news",
        [
            {"sourcecountry": "Japan"},
            {"sourcecountry": "Japan"},
            {"sourcecountry": "South Korea"},
        ],
        "Japan",  # plurality
    ),
    # Multi-region (>3 nations, no keyword)
    (
        "global economy",
        [
            {"sourcecountry": "United States"},
            {"sourcecountry": "United Kingdom"},
            {"sourcecountry": "Germany"},
            {"sourcecountry": "France"},
            {"sourcecountry": "Japan"},
        ],
        None,  # multi-region
    ),
    # No articles, no keyword
    ("random query", [], None),
]

# Nation normalization test cases
NATION_NORMALIZATION_CASES = [
    ("United States of America", "United States"),
    ("USA", "United States"),
    ("uk", "United Kingdom"),
    ("Great Britain", "United Kingdom"),
    ("Peoples Republic of China", "China"),
    ("PRC", "China"),
    ("Republic of China", "Taiwan"),
    ("ROC", "Taiwan"),
    ("Russian Federation", "Russia"),
    # Pass-through for unknown
    ("Japan", "Japan"),
    ("Taiwan", "Taiwan"),
]

# Reliability grade validation cases
VALID_RELIABILITY_GRADES = ["A", "B", "C", "D", "E", "F", "a", "b", "c", "d", "e", "f"]
INVALID_RELIABILITY_GRADES = ["G", "H", "Z", "1", "AA", ""]

# Sample source metadata entry for testing
SAMPLE_SOURCE_ENTRY = {
    "domain": "focustaiwan.tw",
    "language": "English",
    "nation": "Taiwan",
    "political_orientation": "Pro-independence",
    "orientation_axis": "china-independence",
    "orientation_tags": ["independence", "dpp-leaning"],
    "reliability": "B",
    "enrichment_source": "user_override",
}
