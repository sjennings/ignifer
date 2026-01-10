"""Tests for the EntityResolver module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ignifer.aggregation.entity_resolver import (
    EntityMatch,
    EntityResolver,
    ResolutionTier,
)


class TestResolutionTier:
    """Tests for ResolutionTier enum."""

    def test_resolution_tier_values(self) -> None:
        """Resolution tier values should match expected strings."""
        assert ResolutionTier.WIKIDATA.value == "wikidata"
        assert ResolutionTier.FAILED.value == "failed"

    def test_default_confidence_values(self) -> None:
        """Default confidence scores should match specification."""
        assert ResolutionTier.WIKIDATA.default_confidence == 0.85
        assert ResolutionTier.FAILED.default_confidence == 0.0


class TestEntityMatch:
    """Tests for EntityMatch model."""

    def test_entity_match_creation(self) -> None:
        """EntityMatch should be created with all required fields."""
        match = EntityMatch(
            entity_id="Q7747",
            wikidata_qid="Q7747",
            resolution_tier=ResolutionTier.WIKIDATA,
            match_confidence=0.85,
            original_query="Vladimir Putin",
            matched_label="Vladimir Putin",
        )

        assert match.entity_id == "Q7747"
        assert match.wikidata_qid == "Q7747"
        assert match.resolution_tier == ResolutionTier.WIKIDATA
        assert match.match_confidence == 0.85
        assert match.original_query == "Vladimir Putin"
        assert match.matched_label == "Vladimir Putin"
        assert match.suggestions == []

    def test_is_successful_returns_true_for_wikidata(self) -> None:
        """is_successful should return True for wikidata tier."""
        match = EntityMatch(
            resolution_tier=ResolutionTier.WIKIDATA,
            match_confidence=0.85,
            original_query="test",
        )
        assert match.is_successful() is True

    def test_is_successful_returns_false_for_failed(self) -> None:
        """is_successful should return False for failed tier."""
        match = EntityMatch(
            resolution_tier=ResolutionTier.FAILED,
            match_confidence=0.0,
            original_query="test",
        )
        assert match.is_successful() is False

    def test_match_confidence_validates_range(self) -> None:
        """match_confidence should be validated to 0.0-1.0 range."""
        # Valid boundary values
        match_zero = EntityMatch(
            resolution_tier=ResolutionTier.FAILED,
            match_confidence=0.0,
            original_query="test",
        )
        assert match_zero.match_confidence == 0.0

        match_one = EntityMatch(
            resolution_tier=ResolutionTier.WIKIDATA,
            match_confidence=1.0,
            original_query="test",
        )
        assert match_one.match_confidence == 1.0

        # Invalid values should raise ValidationError
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EntityMatch(
                resolution_tier=ResolutionTier.WIKIDATA,
                match_confidence=1.5,
                original_query="test",
            )

        with pytest.raises(ValidationError):
            EntityMatch(
                resolution_tier=ResolutionTier.FAILED,
                match_confidence=-0.1,
                original_query="test",
            )

    def test_to_dict_serialization(self) -> None:
        """to_dict should serialize all fields correctly."""
        match = EntityMatch(
            entity_id="Q7747",
            wikidata_qid="Q7747",
            resolution_tier=ResolutionTier.WIKIDATA,
            match_confidence=0.85,
            original_query="Vladimir Putin",
            matched_label="Vladimir Putin",
            suggestions=["test suggestion"],
            confidence_factors=["Wikidata match", "High confidence"],
        )

        result = match.to_dict()

        assert result["entity_id"] == "Q7747"
        assert result["wikidata_qid"] == "Q7747"
        assert result["resolution_tier"] == "wikidata"
        assert result["match_confidence"] == 0.85
        assert result["confidence_level"] == "VERY_LIKELY"
        assert result["original_query"] == "Vladimir Putin"
        assert result["matched_label"] == "Vladimir Putin"
        assert result["suggestions"] == ["test suggestion"]
        assert result["confidence_factors"] == ["Wikidata match", "High confidence"]

    def test_to_confidence_level_returns_icd203_level(self) -> None:
        """to_confidence_level should map float to ICD 203 ConfidenceLevel."""
        from ignifer.models import ConfidenceLevel

        # Test high confidence -> ALMOST_CERTAIN
        match_high = EntityMatch(
            resolution_tier=ResolutionTier.WIKIDATA,
            match_confidence=1.0,
            original_query="test",
        )
        assert match_high.to_confidence_level() == ConfidenceLevel.ALMOST_CERTAIN

        # Test medium confidence -> VERY_LIKELY
        match_medium = EntityMatch(
            resolution_tier=ResolutionTier.WIKIDATA,
            match_confidence=0.85,
            original_query="test",
        )
        assert match_medium.to_confidence_level() == ConfidenceLevel.VERY_LIKELY

        # Test failed -> REMOTE
        match_failed = EntityMatch(
            resolution_tier=ResolutionTier.FAILED,
            match_confidence=0.0,
            original_query="test",
        )
        assert match_failed.to_confidence_level() == ConfidenceLevel.REMOTE


class TestEntityResolver:
    """Tests for EntityResolver."""

    @pytest.mark.asyncio
    async def test_resolve_wikidata_success(self) -> None:
        """Wikidata lookup should return match on success."""
        from ignifer.models import ResultStatus

        mock_result = MagicMock()
        mock_result.status = ResultStatus.SUCCESS
        mock_result.results = [{"qid": "Q12345", "label": "Test Entity"}]

        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock(return_value=mock_result)

        resolver = EntityResolver(wikidata_adapter=mock_adapter)
        match = await resolver.resolve("Test Entity")

        mock_adapter.query.assert_called_once()
        assert match.resolution_tier == ResolutionTier.WIKIDATA
        assert match.match_confidence == 0.85
        assert match.wikidata_qid == "Q12345"
        assert match.matched_label == "Test Entity"
        assert match.is_successful() is True

    @pytest.mark.asyncio
    async def test_resolve_wikidata_no_results(self) -> None:
        """Wikidata tier should return failed if no results."""
        from ignifer.models import ResultStatus

        mock_result = MagicMock()
        mock_result.status = ResultStatus.NO_DATA
        mock_result.results = []
        mock_result.error = "No entities found"

        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock(return_value=mock_result)

        resolver = EntityResolver(wikidata_adapter=mock_adapter)
        match = await resolver.resolve("Completely Unknown XYZABC123")

        assert match.resolution_tier == ResolutionTier.FAILED
        assert match.match_confidence == 0.0

    @pytest.mark.asyncio
    async def test_resolve_wikidata_exception_handled(self) -> None:
        """Wikidata exceptions should be caught and return failed."""
        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock(side_effect=Exception("Network error"))

        resolver = EntityResolver(wikidata_adapter=mock_adapter)
        match = await resolver.resolve("Some Entity")

        assert match.resolution_tier == ResolutionTier.FAILED

    @pytest.mark.asyncio
    async def test_resolve_failed_returns_suggestions(self) -> None:
        """Failed resolution should include suggestions."""
        from ignifer.models import ResultStatus

        mock_result = MagicMock()
        mock_result.status = ResultStatus.NO_DATA
        mock_result.results = []
        mock_result.error = None

        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock(return_value=mock_result)

        resolver = EntityResolver(wikidata_adapter=mock_adapter)
        match = await resolver.resolve("Unknown Entity XYZABC123456")

        assert match.resolution_tier == ResolutionTier.FAILED
        assert match.match_confidence == 0.0
        assert len(match.suggestions) > 0
        assert match.wikidata_qid is None
        assert match.entity_id is None

    @pytest.mark.asyncio
    async def test_resolve_without_wikidata_adapter(self) -> None:
        """Resolver should return failed without WikidataAdapter."""
        resolver = EntityResolver()  # No adapter

        match = await resolver.resolve("Any Entity")
        assert match.resolution_tier == ResolutionTier.FAILED

    @pytest.mark.asyncio
    async def test_resolve_logs_resolution_tier(self, caplog: pytest.LogCaptureFixture) -> None:
        """Resolution should log which tier matched."""
        import logging
        from ignifer.models import ResultStatus

        mock_result = MagicMock()
        mock_result.status = ResultStatus.SUCCESS
        mock_result.results = [{"qid": "Q12345", "label": "Test"}]

        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock(return_value=mock_result)

        with caplog.at_level(logging.INFO):
            resolver = EntityResolver(wikidata_adapter=mock_adapter)
            await resolver.resolve("Test")

        assert any("wikidata" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_resolve_failed_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Failed resolution should log a warning."""
        import logging
        from ignifer.models import ResultStatus

        mock_result = MagicMock()
        mock_result.status = ResultStatus.NO_DATA
        mock_result.results = []
        mock_result.error = None

        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock(return_value=mock_result)

        with caplog.at_level(logging.WARNING):
            resolver = EntityResolver(wikidata_adapter=mock_adapter)
            await resolver.resolve("Unknown Entity ZZZZZ999")

        assert any(
            "could not be resolved" in record.message.lower()
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_resolve_empty_string_returns_failed(self) -> None:
        """Empty string input should return failed resolution."""
        resolver = EntityResolver()
        match = await resolver.resolve("")

        assert match.resolution_tier == ResolutionTier.FAILED
        assert match.match_confidence == 0.0

    @pytest.mark.asyncio
    async def test_resolve_whitespace_only_returns_failed(self) -> None:
        """Whitespace-only input should return failed resolution."""
        resolver = EntityResolver()
        match = await resolver.resolve("   ")

        assert match.resolution_tier == ResolutionTier.FAILED
        assert match.match_confidence == 0.0

    @pytest.mark.asyncio
    async def test_resolve_wikidata_result_without_qid(self) -> None:
        """Wikidata result without QID should return failed."""
        from ignifer.models import ResultStatus

        mock_result = MagicMock()
        mock_result.status = ResultStatus.SUCCESS
        mock_result.results = [{"label": "Test Entity"}]  # No qid field

        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock(return_value=mock_result)

        resolver = EntityResolver(wikidata_adapter=mock_adapter)
        match = await resolver.resolve("Unknown Entity No QID Test")

        mock_adapter.query.assert_called_once()
        assert match.resolution_tier == ResolutionTier.FAILED

    @pytest.mark.asyncio
    async def test_resolve_strips_whitespace_from_query(self) -> None:
        """Query should be stripped before resolution."""
        from ignifer.models import ResultStatus

        mock_result = MagicMock()
        mock_result.status = ResultStatus.SUCCESS
        mock_result.results = [{"qid": "Q123", "label": "Test"}]

        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock(return_value=mock_result)

        resolver = EntityResolver(wikidata_adapter=mock_adapter)
        match = await resolver.resolve("  Test  ")

        assert match.is_successful()
        # Verify the query was stripped
        call_args = mock_adapter.query.call_args
        assert call_args[0][0].query == "Test"
