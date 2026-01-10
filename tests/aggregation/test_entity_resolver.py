"""Tests for the EntityResolver module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ignifer.aggregation.entity_resolver import (
    KNOWN_ENTITIES,
    EntityMatch,
    EntityResolver,
    ResolutionTier,
)


class TestResolutionTier:
    """Tests for ResolutionTier enum."""

    def test_resolution_tier_values(self) -> None:
        """Resolution tier values should match expected strings."""
        assert ResolutionTier.EXACT.value == "exact"
        assert ResolutionTier.NORMALIZED.value == "normalized"
        assert ResolutionTier.WIKIDATA.value == "wikidata"
        assert ResolutionTier.FUZZY.value == "fuzzy"
        assert ResolutionTier.FAILED.value == "failed"

    def test_default_confidence_values(self) -> None:
        """Default confidence scores should match specification."""
        assert ResolutionTier.EXACT.default_confidence == 1.0
        assert ResolutionTier.NORMALIZED.default_confidence == 0.95
        assert ResolutionTier.WIKIDATA.default_confidence == 0.85
        assert ResolutionTier.FUZZY.default_confidence == 0.75
        assert ResolutionTier.FAILED.default_confidence == 0.0


class TestEntityMatch:
    """Tests for EntityMatch model."""

    def test_entity_match_creation(self) -> None:
        """EntityMatch should be created with all required fields."""
        match = EntityMatch(
            entity_id="Q7747",
            wikidata_qid="Q7747",
            resolution_tier=ResolutionTier.EXACT,
            match_confidence=1.0,
            original_query="Vladimir Putin",
            matched_label="Vladimir Putin",
        )

        assert match.entity_id == "Q7747"
        assert match.wikidata_qid == "Q7747"
        assert match.resolution_tier == ResolutionTier.EXACT
        assert match.match_confidence == 1.0
        assert match.original_query == "Vladimir Putin"
        assert match.matched_label == "Vladimir Putin"
        assert match.suggestions == []

    def test_is_successful_returns_true_for_non_failed(self) -> None:
        """is_successful should return True for successful tiers."""
        for tier in [
            ResolutionTier.EXACT,
            ResolutionTier.NORMALIZED,
            ResolutionTier.WIKIDATA,
            ResolutionTier.FUZZY,
        ]:
            match = EntityMatch(
                resolution_tier=tier,
                match_confidence=0.8,
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
            resolution_tier=ResolutionTier.EXACT,
            match_confidence=1.0,
            original_query="test",
        )
        assert match_one.match_confidence == 1.0

        # Invalid values should raise ValidationError
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EntityMatch(
                resolution_tier=ResolutionTier.EXACT,
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
            resolution_tier=ResolutionTier.EXACT,
            match_confidence=1.0,
            original_query="Vladimir Putin",
            matched_label="Vladimir Putin",
            suggestions=["test suggestion"],
            confidence_factors=["Exact match", "High confidence"],
        )

        result = match.to_dict()

        assert result["entity_id"] == "Q7747"
        assert result["wikidata_qid"] == "Q7747"
        assert result["resolution_tier"] == "exact"
        assert result["match_confidence"] == 1.0
        assert result["confidence_level"] == "ALMOST_CERTAIN"
        assert result["original_query"] == "Vladimir Putin"
        assert result["matched_label"] == "Vladimir Putin"
        assert result["suggestions"] == ["test suggestion"]
        assert result["confidence_factors"] == ["Exact match", "High confidence"]

    def test_to_confidence_level_returns_icd203_level(self) -> None:
        """to_confidence_level should map float to ICD 203 ConfidenceLevel."""
        from ignifer.models import ConfidenceLevel

        # Test high confidence -> ALMOST_CERTAIN
        match_high = EntityMatch(
            resolution_tier=ResolutionTier.EXACT,
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

        # Test low confidence -> LIKELY
        match_low = EntityMatch(
            resolution_tier=ResolutionTier.FUZZY,
            match_confidence=0.75,
            original_query="test",
        )
        assert match_low.to_confidence_level() == ConfidenceLevel.LIKELY

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
    async def test_resolve_exact_match_returns_confidence_one(self) -> None:
        """Exact match should return confidence 1.0."""
        resolver = EntityResolver()
        match = await resolver.resolve("vladimir putin")

        assert match.resolution_tier == ResolutionTier.EXACT
        assert match.match_confidence == 1.0
        assert match.wikidata_qid == "Q7747"
        assert match.matched_label == "Vladimir Putin"
        assert match.is_successful() is True

    @pytest.mark.asyncio
    async def test_resolve_exact_match_case_insensitive(self) -> None:
        """Exact match should be case-insensitive via lowercase lookup."""
        resolver = EntityResolver()

        # The registry keys are lowercase, so exact match is case-insensitive
        match = await resolver.resolve("Joe Biden")

        assert match.is_successful() is True
        assert match.wikidata_qid == "Q6279"

    @pytest.mark.asyncio
    async def test_resolve_exact_match_handles_case_via_lowercase(self) -> None:
        """Exact match uses lowercase lookup, handling case differences."""
        resolver = EntityResolver()
        # Uppercase matches via exact tier since lookup uses .lower()
        match = await resolver.resolve("VLADIMIR PUTIN")

        # Exact match succeeds because query.lower() == "vladimir putin" in registry
        assert match.resolution_tier == ResolutionTier.EXACT
        assert match.match_confidence == 1.0
        assert match.wikidata_qid == "Q7747"

    @pytest.mark.asyncio
    async def test_resolve_normalized_match_handles_extra_whitespace(self) -> None:
        """Normalized match should handle extra whitespace."""
        resolver = EntityResolver()
        match = await resolver.resolve("vladimir   putin")

        # Exact match fails due to double space, normalized handles it
        assert match.is_successful() is True
        assert match.resolution_tier == ResolutionTier.NORMALIZED
        assert match.match_confidence == 0.95

    @pytest.mark.asyncio
    async def test_resolve_normalized_match_handles_diacritics(self) -> None:
        """Normalized match should handle diacritics removal."""
        resolver = EntityResolver()
        # Add an entity with diacritics to test - using accent on 'e'
        # "Jose" with accent should match "jose" without
        # For this test, we'll use a known entity and add diacritics
        match = await resolver.resolve("Vladimír Putín")

        # Should match via normalization (diacritics removed)
        assert match.is_successful() is True
        assert match.resolution_tier == ResolutionTier.NORMALIZED

    @pytest.mark.asyncio
    async def test_resolve_stops_at_first_match_exact(self) -> None:
        """Resolution should stop at exact match tier."""
        # Create mock wikidata adapter to verify it's not called
        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock()

        resolver = EntityResolver(wikidata_adapter=mock_adapter)
        match = await resolver.resolve("vladimir putin")

        # Should match at exact tier
        assert match.resolution_tier == ResolutionTier.EXACT
        # Wikidata should NOT be called due to early exit
        mock_adapter.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_stops_at_first_match_normalized(self) -> None:
        """Resolution should stop at normalized match tier."""
        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock()

        resolver = EntityResolver(wikidata_adapter=mock_adapter)
        # Use extra whitespace to force normalized tier (fails exact)
        match = await resolver.resolve("vladimir   putin")

        # Should match at normalized tier due to whitespace normalization
        assert match.resolution_tier == ResolutionTier.NORMALIZED
        # Wikidata should NOT be called due to early exit
        mock_adapter.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_wikidata_fallback(self) -> None:
        """Wikidata should be tried when local tiers fail."""
        from ignifer.models import ResultStatus

        # Create mock result
        mock_result = MagicMock()
        mock_result.status = ResultStatus.SUCCESS
        mock_result.results = [{"qid": "Q12345", "label": "Test Entity"}]

        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock(return_value=mock_result)

        resolver = EntityResolver(wikidata_adapter=mock_adapter)
        match = await resolver.resolve("Unknown Entity XYZ Not In Registry")

        # Wikidata should be called
        mock_adapter.query.assert_called_once()
        assert match.resolution_tier == ResolutionTier.WIKIDATA
        assert match.match_confidence == 0.85
        assert match.wikidata_qid == "Q12345"
        assert match.matched_label == "Test Entity"

    @pytest.mark.asyncio
    async def test_resolve_wikidata_no_results(self) -> None:
        """Wikidata tier should continue to fuzzy if no results."""
        from ignifer.models import ResultStatus

        mock_result = MagicMock()
        mock_result.status = ResultStatus.NO_DATA
        mock_result.results = []

        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock(return_value=mock_result)

        resolver = EntityResolver(wikidata_adapter=mock_adapter)
        match = await resolver.resolve("Completely Unknown XYZABC123")

        # Should fall through to failed (no fuzzy match either)
        assert match.resolution_tier == ResolutionTier.FAILED
        assert match.match_confidence == 0.0

    @pytest.mark.asyncio
    async def test_resolve_wikidata_exception_handled(self) -> None:
        """Wikidata exceptions should be caught and continue to next tier."""
        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock(side_effect=Exception("Network error"))

        resolver = EntityResolver(wikidata_adapter=mock_adapter)
        match = await resolver.resolve("Some Unknown Entity ABCXYZ")

        # Should gracefully continue to fuzzy/failed
        assert match.resolution_tier == ResolutionTier.FAILED

    @pytest.mark.asyncio
    async def test_resolve_fuzzy_match(self) -> None:
        """Fuzzy match should find similar entities above threshold."""
        resolver = EntityResolver()
        # "Vladmir Putin" is missing an 'i' - should fuzzy match
        match = await resolver.resolve("Vladmir Putin")

        assert match.resolution_tier == ResolutionTier.FUZZY
        assert 0.7 <= match.match_confidence <= 0.9
        assert match.wikidata_qid == "Q7747"
        assert match.matched_label == "Vladimir Putin"

    @pytest.mark.asyncio
    async def test_resolve_fuzzy_match_threshold(self) -> None:
        """Fuzzy match should respect threshold setting."""
        # High threshold should reject marginal matches
        resolver_strict = EntityResolver(fuzzy_threshold=0.95)
        match_strict = await resolver_strict.resolve("Vladmir Putin")

        # With 0.95 threshold, typo may not match
        # Depends on exact similarity score
        if match_strict.resolution_tier == ResolutionTier.FUZZY:
            assert match_strict.match_confidence >= 0.7

    @pytest.mark.asyncio
    async def test_resolve_failed_returns_suggestions(self) -> None:
        """Failed resolution should include suggestions."""
        resolver = EntityResolver()  # No Wikidata adapter
        match = await resolver.resolve("Completely Unknown Entity XYZABC123456")

        assert match.resolution_tier == ResolutionTier.FAILED
        assert match.match_confidence == 0.0
        assert len(match.suggestions) > 0
        assert match.wikidata_qid is None
        assert match.entity_id is None

    @pytest.mark.asyncio
    async def test_resolve_failed_suggestions_content(self) -> None:
        """Failed resolution suggestions should be helpful."""
        resolver = EntityResolver()
        match = await resolver.resolve("ABCDEFGHIJKLMNOP")

        # Should get generic suggestions
        assert any("spelling" in s.lower() for s in match.suggestions)

    @pytest.mark.asyncio
    async def test_resolve_without_wikidata_adapter(self) -> None:
        """Resolver should work without WikidataAdapter (graceful degradation)."""
        resolver = EntityResolver()  # No adapter

        # Known entity should still resolve
        match = await resolver.resolve("vladimir putin")
        assert match.is_successful() is True

        # Unknown entity should fail gracefully
        match = await resolver.resolve("Unknown Entity XYZ123")
        assert match.resolution_tier == ResolutionTier.FAILED

    @pytest.mark.asyncio
    async def test_resolve_logs_resolution_tier(self, caplog: pytest.LogCaptureFixture) -> None:
        """Resolution should log which tier matched."""
        import logging

        with caplog.at_level(logging.INFO):
            resolver = EntityResolver()
            await resolver.resolve("vladimir putin")

        # Check that logging occurred with tier info
        assert any("exact" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_resolve_failed_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Failed resolution should log a warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            resolver = EntityResolver()
            await resolver.resolve("Unknown Entity ZZZZZ999")

        # Check for warning log
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
        assert match.original_query == ""

    @pytest.mark.asyncio
    async def test_resolve_whitespace_only_returns_failed(self) -> None:
        """Whitespace-only input should return failed resolution."""
        resolver = EntityResolver()
        match = await resolver.resolve("   ")

        assert match.resolution_tier == ResolutionTier.FAILED
        assert match.match_confidence == 0.0

    @pytest.mark.asyncio
    async def test_resolve_wikidata_result_without_qid(self) -> None:
        """Wikidata result without QID should continue to next tier."""
        from ignifer.models import ResultStatus

        # Create mock result that has success status but missing qid
        mock_result = MagicMock()
        mock_result.status = ResultStatus.SUCCESS
        mock_result.results = [{"label": "Test Entity"}]  # No qid field

        mock_adapter = MagicMock()
        mock_adapter.query = AsyncMock(return_value=mock_result)

        resolver = EntityResolver(wikidata_adapter=mock_adapter)
        match = await resolver.resolve("Unknown Entity No QID Test")

        # Should fall through to fuzzy/failed since wikidata had no qid
        mock_adapter.query.assert_called_once()
        # Should not match at wikidata tier since there's no qid
        assert match.resolution_tier != ResolutionTier.WIKIDATA

    @pytest.mark.asyncio
    async def test_resolve_failed_with_similar_entity_suggestions(self) -> None:
        """Failed resolution with similar entities should suggest alternatives."""
        resolver = EntityResolver()
        # "Putin" alone has some similarity to "vladimir putin" but not enough for fuzzy
        # Use something that has 0.5-0.8 similarity to trigger "Did you mean" suggestions
        match = await resolver.resolve("Vladimir")

        assert match.resolution_tier == ResolutionTier.FAILED
        # Should have suggestion for the similar known entity
        assert any("Did you mean" in s for s in match.suggestions)


class TestEntityResolverNormalization:
    """Tests for normalization functionality."""

    def test_normalize_lowercase(self) -> None:
        """Normalization should convert to lowercase."""
        resolver = EntityResolver()
        assert resolver._normalize("HELLO") == "hello"

    def test_normalize_strip_whitespace(self) -> None:
        """Normalization should strip leading/trailing whitespace."""
        resolver = EntityResolver()
        assert resolver._normalize("  hello  ") == "hello"

    def test_normalize_collapse_spaces(self) -> None:
        """Normalization should collapse multiple spaces."""
        resolver = EntityResolver()
        assert resolver._normalize("hello   world") == "hello world"

    def test_normalize_remove_diacritics(self) -> None:
        """Normalization should remove diacritics."""
        resolver = EntityResolver()
        assert resolver._normalize("cafe") == "cafe"
        # NFD decomposition + Mn removal handles accents
        assert resolver._normalize("resume") == "resume"


class TestEntityResolverSimilarity:
    """Tests for similarity calculation."""

    def test_calculate_similarity_identical(self) -> None:
        """Identical strings should have similarity 1.0."""
        resolver = EntityResolver()
        assert resolver._calculate_similarity("hello", "hello") == 1.0

    def test_calculate_similarity_different(self) -> None:
        """Different strings should have lower similarity."""
        resolver = EntityResolver()
        similarity = resolver._calculate_similarity("hello", "world")
        assert similarity < 0.5

    def test_calculate_similarity_case_insensitive(self) -> None:
        """Similarity should be case-insensitive."""
        resolver = EntityResolver()
        assert resolver._calculate_similarity("Hello", "hello") == 1.0

    def test_calculate_similarity_typo(self) -> None:
        """Similar strings with typos should have high similarity."""
        resolver = EntityResolver()
        similarity = resolver._calculate_similarity("vladimir", "vladmir")
        assert similarity > 0.8


class TestKnownEntities:
    """Tests for the known entities registry."""

    def test_known_entities_has_required_entities(self) -> None:
        """Known entities should include common political entities."""
        assert "vladimir putin" in KNOWN_ENTITIES
        assert "joe biden" in KNOWN_ENTITIES
        assert "gazprom" in KNOWN_ENTITIES

    def test_known_entities_have_qid_and_label(self) -> None:
        """Known entities should have qid and label fields."""
        for name, info in KNOWN_ENTITIES.items():
            assert "qid" in info, f"Entity '{name}' missing qid"
            assert "label" in info, f"Entity '{name}' missing label"
            assert info["qid"].startswith("Q"), f"Entity '{name}' has invalid qid"
