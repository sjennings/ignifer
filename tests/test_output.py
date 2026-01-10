"""Tests for output formatting - TSUKUYOMI/Amaterasu style."""

from datetime import datetime, timedelta, timezone

from ignifer.models import (
    ConfidenceLevel,
    OSINTResult,
    QualityTier,
    ResultStatus,
    SourceAttribution,
    SourceMetadata,
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
