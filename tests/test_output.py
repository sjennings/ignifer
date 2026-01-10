"""Tests for output formatting - TSUKUYOMI/Amaterasu style."""

from datetime import datetime, timedelta, timezone

from ignifer.models import (
    ConfidenceLevel,
    OSINTResult,
    QualityTier,
    ResultStatus,
    SourceAttribution,
    SourceMetadata,
    SourceMetadataEntry,
)
from ignifer.output import OutputFormatter, CONF_HIGH, CONF_MEDIUM, CONF_LOW


class TestOutputFormatter:
    def test_format_success_includes_briefing_header(self) -> None:
        """Successful results include professional briefing header."""
        result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="test topic",
            results=[
                {"title": "Test Article", "domain": "example.com"},
            ],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        formatter = OutputFormatter()
        output = formatter.format(result)

        assert "INTELLIGENCE BRIEFING" in output
        assert "UNCLASSIFIED" in output
        assert "TEST TOPIC" in output  # Query is uppercased in header
        assert "KEY ASSESSMENT" in output
        assert "Test Article" in output
        assert "GDELT" in output

    def test_format_success_includes_source_analysis(self) -> None:
        """Successful results include source correlation matrix."""
        result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="test",
            results=[
                {"title": f"Article {i}", "domain": f"source{i}.com"}
                for i in range(5)
            ],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        formatter = OutputFormatter()
        output = formatter.format(result)

        assert "SOURCE ANALYSIS" in output
        assert "SOURCE CORRELATION MATRIX" in output
        assert "Unique Domains" in output

    def test_format_success_includes_information_gaps(self) -> None:
        """Successful results include information gaps section."""
        result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="test",
            results=[{"title": "Test", "domain": "example.com"}],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        formatter = OutputFormatter()
        output = formatter.format(result)

        assert "INFORMATION GAPS" in output
        assert "►" in output  # Gap bullet point

    def test_format_success_includes_recommended_actions(self) -> None:
        """Successful results include recommended next steps."""
        result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="test",
            results=[{"title": "Test", "domain": "example.com"}],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        formatter = OutputFormatter()
        output = formatter.format(result)

        assert "RECOMMENDED ACTIONS" in output

    def test_format_no_data_includes_suggestions(self) -> None:
        """NO_DATA results include helpful suggestions."""
        result = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="xyznonexistent",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
            error="Try broader terms",
        )

        formatter = OutputFormatter()
        output = formatter.format(result)

        assert "NO DATA AVAILABLE" in output
        assert "xyznonexistent" in output
        assert "RECOMMENDED ACTIONS" in output

    def test_format_rate_limited(self) -> None:
        """RATE_LIMITED results explain the situation."""
        result = OSINTResult(
            status=ResultStatus.RATE_LIMITED,
            query="test",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        formatter = OutputFormatter()
        output = formatter.format(result)

        assert "RATE LIMITED" in output or "rate limit" in output.lower()
        assert "RECOMMENDED ACTIONS" in output

    def test_freshness_indicator_live(self) -> None:
        """Freshness indicator shows 'LIVE' for recent data."""
        formatter = OutputFormatter()
        now = datetime.now(timezone.utc)

        freshness = formatter._freshness_indicator(now)
        assert "LIVE" in freshness

    def test_freshness_indicator_hours(self) -> None:
        """Freshness indicator shows hours for data retrieved today."""
        formatter = OutputFormatter()
        hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)

        freshness = formatter._freshness_indicator(hours_ago)
        assert "TODAY" in freshness or "hours" in freshness

    def test_format_error_with_message(self) -> None:
        """Error results include error message."""
        result = OSINTResult(
            status=ResultStatus.ERROR,
            query="test",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
            error="API connection failed",
        )

        formatter = OutputFormatter()
        output = formatter.format(result)

        assert "COLLECTION ERROR" in output
        assert "API connection failed" in output

    def test_format_success_truncates_long_list(self) -> None:
        """Success format shows top 7 and indicates more."""
        articles = [{"title": f"Article {i}", "domain": "example.com"} for i in range(15)]

        result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="test",
            results=articles,
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        formatter = OutputFormatter()
        output = formatter.format(result)

        assert "3 additional sources in dataset" in output  # 15 - 12 = 3 (now shows 12 diverse articles)
        assert "Article 0" in output  # First article shown
        assert "Article 14" not in output  # Last article not shown

    def test_confidence_indicators(self) -> None:
        """Confidence indicators are properly assigned."""
        formatter = OutputFormatter()

        # High reliability domains
        assert formatter._domain_confidence("reuters.com") == CONF_HIGH
        assert formatter._domain_confidence("bbc.com") == CONF_HIGH

        # Medium reliability domains
        assert formatter._domain_confidence("cnn.com") == CONF_MEDIUM

        # Unknown domains default to low
        assert formatter._domain_confidence("randomsite.com") == CONF_LOW

    def test_coverage_assessment(self) -> None:
        """Coverage level is assessed based on article count."""
        formatter = OutputFormatter()

        assert "EXTENSIVE" in formatter._assess_coverage_level(50)
        assert "SUBSTANTIAL" in formatter._assess_coverage_level(25)
        assert "MODERATE" in formatter._assess_coverage_level(10)
        assert "LIMITED" in formatter._assess_coverage_level(5)
        assert "MINIMAL" in formatter._assess_coverage_level(2)

    def test_source_reliability_grade(self) -> None:
        """Source reliability grades are IC-standard."""
        result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="test",
            results=[],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        formatter = OutputFormatter()
        grade = formatter._source_reliability_grade(result)

        assert "C" in grade  # MEDIUM = C grade
        assert "Fairly reliable" in grade

    def test_format_with_source_metadata(self) -> None:
        """Format uses source metadata when provided."""
        result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="test",
            results=[
                {"title": "Test Article", "domain": "reuters.com", "sourcecountry": "United Kingdom"}
            ],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        # Create source metadata map
        source_metadata = {
            "reuters.com": SourceMetadataEntry(
                domain="reuters.com",
                language="English",
                nation="United Kingdom",
                reliability="A",
            )
        }

        formatter = OutputFormatter()
        output = formatter.format(result, source_metadata=source_metadata)

        # Should use ◉ for A reliability
        assert CONF_HIGH in output
        assert "INTELLIGENCE BRIEFING" in output

    def test_format_with_detected_region_shows_websearch_instruction(self) -> None:
        """Format includes WebSearch instruction when region detected."""
        result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Taiwan semiconductors",
            results=[
                {"title": "Test Article", "domain": "example.com", "sourcecountry": "Taiwan"}
            ],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        formatter = OutputFormatter()
        output = formatter.format(
            result,
            detected_region="Taiwan",
            query="Taiwan semiconductors"
        )

        assert "REGIONAL SUPPLEMENTATION" in output
        assert "Taiwan" in output
        assert "WebSearch" in output

    def test_format_multi_region_shows_note(self) -> None:
        """Format shows multi-region note when >3 nations detected."""
        articles = [
            {"title": f"Article {i}", "domain": f"source{i}.com", "sourcecountry": country}
            for i, country in enumerate(["US", "UK", "Germany", "France", "Japan"])
        ]

        result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="global economy",
            results=articles,
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        formatter = OutputFormatter()
        output = formatter.format(result, detected_region=None)

        assert "Multi-region topic detected" in output

    def test_get_reliability_indicator_with_metadata(self) -> None:
        """Reliability indicator uses source metadata grades."""
        formatter = OutputFormatter()

        metadata = {
            "high.com": SourceMetadataEntry(domain="high.com", reliability="A"),
            "medium.com": SourceMetadataEntry(domain="medium.com", reliability="C"),
            "low.com": SourceMetadataEntry(domain="low.com", reliability="F"),
        }

        assert formatter._get_reliability_indicator("high.com", metadata) == CONF_HIGH
        assert formatter._get_reliability_indicator("medium.com", metadata) == CONF_MEDIUM
        assert formatter._get_reliability_indicator("low.com", metadata) == CONF_LOW

    def test_get_reliability_indicator_fallback(self) -> None:
        """Reliability indicator falls back to medium when no metadata."""
        formatter = OutputFormatter()

        # None metadata
        assert formatter._get_reliability_indicator("test.com", None) == CONF_MEDIUM

        # Missing domain in metadata
        metadata = {"other.com": SourceMetadataEntry(domain="other.com")}
        assert formatter._get_reliability_indicator("test.com", metadata) == CONF_MEDIUM

    def test_select_diverse_articles_with_region_priority(self) -> None:
        """Article selection prioritizes regional sources."""
        articles = [
            {"title": "US Article", "domain": "us.com", "sourcecountry": "United States", "language": "English"},
            {"title": "Taiwan Article", "domain": "tw.com", "sourcecountry": "Taiwan", "language": "Chinese"},
            {"title": "UK Article", "domain": "uk.com", "sourcecountry": "United Kingdom", "language": "English"},
        ]

        metadata = {
            "us.com": SourceMetadataEntry(domain="us.com", nation="United States", reliability="C"),
            "tw.com": SourceMetadataEntry(domain="tw.com", nation="Taiwan", reliability="B"),
            "uk.com": SourceMetadataEntry(domain="uk.com", nation="United Kingdom", reliability="C"),
        }

        formatter = OutputFormatter()
        selected = formatter._select_diverse_articles(
            articles,
            max_count=2,
            detected_region="Taiwan",
            source_metadata=metadata
        )

        # Taiwan article should be prioritized
        assert len(selected) == 2
        domains = [a["domain"] for a in selected]
        assert "tw.com" in domains

    def test_format_with_political_orientation(self) -> None:
        """Format includes political orientation in SOURCE ATTRIBUTION."""
        result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="test",
            results=[
                {"title": "Test Article", "domain": "focustaiwan.tw", "sourcecountry": "Taiwan"}
            ],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        source_metadata = {
            "focustaiwan.tw": SourceMetadataEntry(
                domain="focustaiwan.tw",
                language="English",
                nation="Taiwan",
                political_orientation="Pro-independence",
                orientation_axis="china-independence",
                reliability="B",
            )
        }

        formatter = OutputFormatter()
        output = formatter.format(result, source_metadata=source_metadata)

        assert "Source Political Orientations" in output
        assert "Pro-independence" in output

    def test_get_domains_needing_analysis_filters_baseline(self) -> None:
        """_get_domains_needing_analysis returns only auto:gdelt_baseline domains."""
        articles = [
            {"domain": "analyzed.com"},
            {"domain": "analyzed.com"},
            {"domain": "unanalyzed.com"},
        ]

        metadata = {
            "analyzed.com": SourceMetadataEntry(
                domain="analyzed.com",
                nation="US",
                enrichment_source="user_override"  # Already analyzed
            ),
            "unanalyzed.com": SourceMetadataEntry(
                domain="unanalyzed.com",
                nation="UK",
                enrichment_source="auto:gdelt_baseline"  # Needs analysis
            ),
        }

        formatter = OutputFormatter()
        result = formatter._get_domains_needing_analysis(articles, metadata)

        assert len(result) == 1
        assert result[0][0] == "unanalyzed.com"
        assert result[0][1] == "UK"  # nation

    def test_get_domains_needing_analysis_sorts_by_frequency(self) -> None:
        """_get_domains_needing_analysis sorts by article count descending."""
        articles = [
            {"domain": "low.com"},
            {"domain": "high.com"},
            {"domain": "high.com"},
            {"domain": "high.com"},
            {"domain": "medium.com"},
            {"domain": "medium.com"},
        ]

        metadata = {
            "low.com": SourceMetadataEntry(
                domain="low.com", enrichment_source="auto:gdelt_baseline"
            ),
            "medium.com": SourceMetadataEntry(
                domain="medium.com", enrichment_source="auto:gdelt_baseline"
            ),
            "high.com": SourceMetadataEntry(
                domain="high.com", enrichment_source="auto:gdelt_baseline"
            ),
        }

        formatter = OutputFormatter()
        result = formatter._get_domains_needing_analysis(articles, metadata)

        assert len(result) == 3
        assert result[0][0] == "high.com"  # 3 articles
        assert result[0][3] == 3
        assert result[1][0] == "medium.com"  # 2 articles
        assert result[1][3] == 2
        assert result[2][0] == "low.com"  # 1 article
        assert result[2][3] == 1

    def test_get_domains_needing_analysis_empty_when_all_analyzed(self) -> None:
        """_get_domains_needing_analysis returns empty when all analyzed."""
        articles = [{"domain": "analyzed.com"}]

        metadata = {
            "analyzed.com": SourceMetadataEntry(
                domain="analyzed.com",
                enrichment_source="user_override"
            ),
        }

        formatter = OutputFormatter()
        result = formatter._get_domains_needing_analysis(articles, metadata)

        assert result == []

    def test_format_source_analysis_instructions_empty_when_none_needed(self) -> None:
        """_format_source_analysis_instructions returns empty when no analysis needed."""
        articles = [{"domain": "analyzed.com"}]

        metadata = {
            "analyzed.com": SourceMetadataEntry(
                domain="analyzed.com",
                enrichment_source="user_override"
            ),
        }

        formatter = OutputFormatter()
        result = formatter._format_source_analysis_instructions(articles, metadata, None)

        assert result == []

    def test_format_source_analysis_instructions_generates_block(self) -> None:
        """_format_source_analysis_instructions generates instruction block."""
        articles = [
            {"domain": "news1.com"},
            {"domain": "news1.com"},
            {"domain": "news2.com"},
        ]

        metadata = {
            "news1.com": SourceMetadataEntry(
                domain="news1.com",
                nation="Taiwan",
                language="Chinese",
                enrichment_source="auto:gdelt_baseline"
            ),
            "news2.com": SourceMetadataEntry(
                domain="news2.com",
                nation="US",
                enrichment_source="auto:gdelt_baseline"
            ),
        }

        formatter = OutputFormatter()
        result = formatter._format_source_analysis_instructions(articles, metadata, None)

        # Check structure
        output = "\n".join(result)
        assert "MANDATORY: SOURCE QUALITY ANALYSIS REQUIRED" in output
        assert "you MUST analyze 2 sources" in output
        assert "ACTION REQUIRED" in output
        assert "news1.com" in output
        assert "WebSearch" in output
        assert "RELIABILITY GRADES" in output
        assert "set_source_reliability" in output

    def test_format_source_analysis_instructions_includes_regional_axis(self) -> None:
        """_format_source_analysis_instructions includes regional axis hints."""
        articles = [{"domain": "news.com"}]

        metadata = {
            "news.com": SourceMetadataEntry(
                domain="news.com",
                nation="Taiwan",
                enrichment_source="auto:gdelt_baseline"
            ),
        }

        formatter = OutputFormatter()
        result = formatter._format_source_analysis_instructions(
            articles, metadata, "Taiwan"
        )

        output = "\n".join(result)
        assert "Taiwan sources" in output
        assert "china-independence" in output
        assert "set_source_orientation" in output

    def test_format_includes_analysis_instructions_when_needed(self) -> None:
        """Full format includes source analysis instructions when domains need analysis."""
        result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Taiwan news",
            results=[
                {"title": "Test Article", "domain": "unanalyzed.tw", "sourcecountry": "Taiwan"}
            ],
            sources=[
                SourceAttribution(
                    source="gdelt",
                    quality=QualityTier.MEDIUM,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="gdelt",
                        source_url="https://api.gdeltproject.org/...",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        source_metadata = {
            "unanalyzed.tw": SourceMetadataEntry(
                domain="unanalyzed.tw",
                language="Chinese",
                nation="Taiwan",
                enrichment_source="auto:gdelt_baseline"  # Needs analysis
            )
        }

        formatter = OutputFormatter()
        output = formatter.format(
            result,
            source_metadata=source_metadata,
            detected_region="Taiwan"
        )

        assert "MANDATORY: SOURCE QUALITY ANALYSIS REQUIRED" in output
        assert "unanalyzed.tw" in output
        assert "Taiwan sources" in output
        assert "china-independence" in output
