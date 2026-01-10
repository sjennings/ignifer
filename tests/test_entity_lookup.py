"""Tests for entity_lookup tool."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ignifer.adapters.base import AdapterError, AdapterTimeoutError
from ignifer.aggregation.entity_resolver import EntityMatch, ResolutionTier
from ignifer.models import (
    ConfidenceLevel,
    OSINTResult,
    QualityTier,
    ResultStatus,
    SourceAttribution,
    SourceMetadata,
)
from ignifer.server import entity_lookup


class TestEntityLookupTool:
    """Tests for the entity_lookup MCP tool."""

    @pytest.mark.asyncio
    async def test_entity_lookup_by_name_success(self) -> None:
        """Entity lookup by name returns formatted output."""
        # Mock the EntityResolver
        mock_resolution = EntityMatch(
            entity_id="Q102673",
            wikidata_qid="Q102673",
            resolution_tier=ResolutionTier.WIKIDATA,
            match_confidence=0.85,
            original_query="Gazprom",
            matched_label="Gazprom",
        )

        # Mock the WikidataAdapter lookup result
        mock_entity_data = {
            "qid": "Q102673",
            "label": "Gazprom",
            "description": "Russian state-controlled natural gas company",
            "aliases": "OAO Gazprom, PAO Gazprom",
            "url": "https://www.wikidata.org/wiki/Q102673",
            "instance_of": "Q4830453",  # enterprise
            "headquarters": "Saint Petersburg",
            "inception": "1989",
            "country": "Q159",  # Russia
            "related_entities_count": 12,
        }

        mock_wikidata_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Q102673",
            results=[mock_entity_data],
            sources=[
                SourceAttribution(
                    source="wikidata",
                    quality=QualityTier.HIGH,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,
                    metadata=SourceMetadata(
                        source_name="wikidata",
                        source_url="https://www.wikidata.org/wiki/Q102673",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        with (
            patch("ignifer.server._get_entity_resolver") as mock_resolver_getter,
            patch("ignifer.server._get_wikidata") as mock_wikidata_getter,
        ):
            # Set up resolver mock
            mock_resolver = MagicMock()
            mock_resolver.resolve = AsyncMock(return_value=mock_resolution)
            mock_resolver_getter.return_value = mock_resolver

            # Set up wikidata mock
            mock_wikidata = MagicMock()
            mock_wikidata.lookup_by_qid = AsyncMock(return_value=mock_wikidata_result)
            mock_wikidata_getter.return_value = mock_wikidata

            result = await entity_lookup.fn(name="Gazprom")

            # Verify output contains expected elements
            assert "ENTITY LOOKUP" in result
            assert "Gazprom" in result
            assert "Q102673" in result
            assert "Russian state-controlled" in result
            assert "Saint Petersburg" in result
            assert "1989" in result
            assert "Resolution: wikidata" in result
            assert "confidence: 0.85" in result

    @pytest.mark.asyncio
    async def test_entity_lookup_by_qid(self) -> None:
        """Entity lookup by Q-ID directly fetches entity."""
        mock_entity_data = {
            "qid": "Q7747",
            "label": "Vladimir Putin",
            "description": "President of Russia",
            "aliases": "Vladimir Vladimirovich Putin, Putin",
            "url": "https://www.wikidata.org/wiki/Q7747",
            "occupation": "Politician",
            "citizenship": "Russia",
            "related_entities_count": 5,
        }

        mock_wikidata_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Q7747",
            results=[mock_entity_data],
            sources=[
                SourceAttribution(
                    source="wikidata",
                    quality=QualityTier.HIGH,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,
                    metadata=SourceMetadata(
                        source_name="wikidata",
                        source_url="https://www.wikidata.org/wiki/Q7747",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_wikidata") as mock_wikidata_getter:
            mock_wikidata = MagicMock()
            mock_wikidata.lookup_by_qid = AsyncMock(return_value=mock_wikidata_result)
            mock_wikidata_getter.return_value = mock_wikidata

            result = await entity_lookup.fn(identifier="Q7747")

            # Verify direct lookup was used
            mock_wikidata.lookup_by_qid.assert_called_once_with("Q7747")

            # Verify output
            assert "ENTITY LOOKUP" in result
            assert "Vladimir Putin" in result
            assert "Q7747" in result
            assert "direct Q-ID lookup" in result
            assert "confidence: 1.00" in result

    @pytest.mark.asyncio
    async def test_entity_lookup_qid_lowercase(self) -> None:
        """Entity lookup normalizes lowercase Q-ID to uppercase."""
        mock_entity_data = {
            "qid": "Q102673",
            "label": "Gazprom",
            "description": "Company",
            "url": "https://www.wikidata.org/wiki/Q102673",
        }

        mock_wikidata_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Q102673",
            results=[mock_entity_data],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_wikidata") as mock_wikidata_getter:
            mock_wikidata = MagicMock()
            mock_wikidata.lookup_by_qid = AsyncMock(return_value=mock_wikidata_result)
            mock_wikidata_getter.return_value = mock_wikidata

            result = await entity_lookup.fn(identifier="q102673")

            # Should normalize to uppercase
            mock_wikidata.lookup_by_qid.assert_called_once_with("Q102673")
            assert "Gazprom" in result

    @pytest.mark.asyncio
    async def test_entity_lookup_qid_without_prefix(self) -> None:
        """Entity lookup adds Q prefix if missing."""
        mock_entity_data = {
            "qid": "Q102673",
            "label": "Gazprom",
            "description": "Company",
            "url": "https://www.wikidata.org/wiki/Q102673",
        }

        mock_wikidata_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Q102673",
            results=[mock_entity_data],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_wikidata") as mock_wikidata_getter:
            mock_wikidata = MagicMock()
            mock_wikidata.lookup_by_qid = AsyncMock(return_value=mock_wikidata_result)
            mock_wikidata_getter.return_value = mock_wikidata

            result = await entity_lookup.fn(identifier="102673")

            # Should add Q prefix
            mock_wikidata.lookup_by_qid.assert_called_once_with("Q102673")
            assert "Gazprom" in result

    @pytest.mark.asyncio
    async def test_entity_lookup_failed_resolution(self) -> None:
        """Failed resolution returns suggestions."""
        mock_resolution = EntityMatch(
            entity_id=None,
            wikidata_qid=None,
            resolution_tier=ResolutionTier.FAILED,
            match_confidence=0.0,
            original_query="xyznonexistent",
            matched_label=None,
            suggestions=[
                "Try checking the spelling",
                "Try using a more complete name",
            ],
        )

        with patch("ignifer.server._get_entity_resolver") as mock_resolver_getter:
            mock_resolver = MagicMock()
            mock_resolver.resolve = AsyncMock(return_value=mock_resolution)
            mock_resolver_getter.return_value = mock_resolver

            result = await entity_lookup.fn(name="xyznonexistent")

            # Verify failure output
            assert "Entity Not Found" in result
            assert "xyznonexistent" in result
            assert "Suggestions" in result
            assert "spelling" in result

    @pytest.mark.asyncio
    async def test_entity_lookup_disambiguation(self) -> None:
        """Multiple matches returns disambiguation list."""
        mock_resolution = EntityMatch(
            entity_id="Q90",
            wikidata_qid="Q90",
            resolution_tier=ResolutionTier.WIKIDATA,
            match_confidence=0.85,
            original_query="Paris",
            matched_label="Paris",
        )

        # Mock lookup_by_qid to return empty (simulating need for disambiguation)
        mock_empty_result = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="Q90",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        # Mock search results with multiple matches
        mock_search_results = [
            {
                "qid": "Q90",
                "label": "Paris",
                "description": "Capital city of France",
                "url": "https://www.wikidata.org/wiki/Q90",
            },
            {
                "qid": "Q830149",
                "label": "Paris",
                "description": "City in Texas, United States",
                "url": "https://www.wikidata.org/wiki/Q830149",
            },
            {
                "qid": "Q23538",
                "label": "Paris",
                "description": "Mythological figure",
                "url": "https://www.wikidata.org/wiki/Q23538",
            },
        ]

        mock_search_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Paris",
            results=mock_search_results,
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with (
            patch("ignifer.server._get_entity_resolver") as mock_resolver_getter,
            patch("ignifer.server._get_wikidata") as mock_wikidata_getter,
        ):
            mock_resolver = MagicMock()
            mock_resolver.resolve = AsyncMock(return_value=mock_resolution)
            mock_resolver_getter.return_value = mock_resolver

            mock_wikidata = MagicMock()
            mock_wikidata.lookup_by_qid = AsyncMock(return_value=mock_empty_result)
            mock_wikidata.query = AsyncMock(return_value=mock_search_result)
            mock_wikidata_getter.return_value = mock_wikidata

            result = await entity_lookup.fn(name="Paris")

            # Verify disambiguation output
            assert "Multiple Entities Found" in result
            assert "Paris" in result
            assert "Q90" in result
            assert "Capital city of France" in result
            assert "Q830149" in result
            assert "Texas" in result
            assert "identifier=" in result  # Tip about using Q-ID

    @pytest.mark.asyncio
    async def test_entity_lookup_timeout_error(self) -> None:
        """Timeout errors return user-friendly message."""
        with patch("ignifer.server._get_wikidata") as mock_wikidata_getter:
            mock_wikidata = MagicMock()
            mock_wikidata.lookup_by_qid = AsyncMock(
                side_effect=AdapterTimeoutError("wikidata", 15.0)
            )
            mock_wikidata_getter.return_value = mock_wikidata

            result = await entity_lookup.fn(identifier="Q7747")

            assert "Timed Out" in result
            assert "Q7747" in result
            assert "Suggestions" in result

    @pytest.mark.asyncio
    async def test_entity_lookup_adapter_error(self) -> None:
        """Adapter errors return user-friendly message."""
        with patch("ignifer.server._get_wikidata") as mock_wikidata_getter:
            mock_wikidata = MagicMock()
            mock_wikidata.lookup_by_qid = AsyncMock(
                side_effect=AdapterError("wikidata", "Connection refused")
            )
            mock_wikidata_getter.return_value = mock_wikidata

            result = await entity_lookup.fn(identifier="Q7747")

            assert "Unable to Retrieve Data" in result
            assert "Q7747" in result
            assert "Suggestions" in result

    @pytest.mark.asyncio
    async def test_entity_lookup_generic_exception(self) -> None:
        """Generic exceptions are caught and formatted."""
        with patch("ignifer.server._get_wikidata") as mock_wikidata_getter:
            mock_wikidata = MagicMock()
            mock_wikidata.lookup_by_qid = AsyncMock(side_effect=ValueError("Unexpected error"))
            mock_wikidata_getter.return_value = mock_wikidata

            result = await entity_lookup.fn(identifier="Q7747")

            assert "Error" in result
            assert "unexpected" in result.lower()

    @pytest.mark.asyncio
    async def test_entity_lookup_no_input(self) -> None:
        """No input returns helpful error message."""
        result = await entity_lookup.fn()

        assert "Invalid Request" in result
        assert "name" in result
        assert "identifier" in result
        assert "Examples" in result

    @pytest.mark.asyncio
    async def test_entity_lookup_empty_strings(self) -> None:
        """Empty string inputs return helpful error message."""
        result = await entity_lookup.fn(name="", identifier="")

        assert "Invalid Request" in result

    @pytest.mark.asyncio
    async def test_entity_lookup_whitespace_only(self) -> None:
        """Whitespace-only inputs are treated as invalid."""
        result = await entity_lookup.fn(name="   ", identifier="  ")

        assert "Invalid Request" in result

    @pytest.mark.asyncio
    async def test_entity_lookup_qid_not_found(self) -> None:
        """Non-existent Q-ID returns helpful message."""
        mock_wikidata_result = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="Q999999999",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
            error="Entity Q999999999 not found in Wikidata.",
        )

        with patch("ignifer.server._get_wikidata") as mock_wikidata_getter:
            mock_wikidata = MagicMock()
            mock_wikidata.lookup_by_qid = AsyncMock(return_value=mock_wikidata_result)
            mock_wikidata_getter.return_value = mock_wikidata

            result = await entity_lookup.fn(identifier="Q999999999")

            assert "Entity Not Found" in result
            assert "Q999999999" in result
            assert "Suggestions" in result
            assert "name" in result  # Suggest trying by name

class TestEntityOutputFormatting:
    """Tests for entity output formatting."""

    @pytest.mark.asyncio
    async def test_format_includes_all_key_facts(self) -> None:
        """Output includes all available key facts."""
        mock_resolution = EntityMatch(
            entity_id="Q102673",
            wikidata_qid="Q102673",
            resolution_tier=ResolutionTier.WIKIDATA,
            match_confidence=0.85,
            original_query="Gazprom",
            matched_label="Gazprom",
        )

        mock_entity_data = {
            "qid": "Q102673",
            "label": "Gazprom",
            "description": "Russian natural gas company",
            "aliases": "OAO Gazprom, PAO Gazprom",
            "url": "https://www.wikidata.org/wiki/Q102673",
            "instance_of": "Company",
            "headquarters": "Saint Petersburg",
            "inception": "1989-08-08",
            "country": "Russia",
            "website": "https://www.gazprom.com",
            "related_entities_count": 15,
        }

        mock_wikidata_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Q102673",
            results=[mock_entity_data],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with (
            patch("ignifer.server._get_entity_resolver") as mock_resolver_getter,
            patch("ignifer.server._get_wikidata") as mock_wikidata_getter,
        ):
            mock_resolver = MagicMock()
            mock_resolver.resolve = AsyncMock(return_value=mock_resolution)
            mock_resolver_getter.return_value = mock_resolver

            mock_wikidata = MagicMock()
            mock_wikidata.lookup_by_qid = AsyncMock(return_value=mock_wikidata_result)
            mock_wikidata_getter.return_value = mock_wikidata

            result = await entity_lookup.fn(name="Gazprom")

            # Verify all sections present
            assert "ENTITY LOOKUP" in result
            assert "Gazprom" in result
            assert "TYPE: Company" in result
            assert "DESCRIPTION:" in result
            assert "KEY FACTS:" in result
            assert "Headquarters" in result
            assert "Saint Petersburg" in result
            assert "Founded" in result
            assert "1989" in result
            assert "Country" in result
            assert "Russia" in result
            assert "Website" in result
            assert "gazprom.com" in result
            assert "ALIASES:" in result
            assert "OAO Gazprom" in result
            assert "RELATED ENTITIES: 15" in result
            assert "Source: Wikidata" in result

    @pytest.mark.asyncio
    async def test_format_handles_missing_optional_fields(self) -> None:
        """Output handles missing optional fields gracefully."""
        mock_resolution = EntityMatch(
            entity_id="Q12345",
            wikidata_qid="Q12345",
            resolution_tier=ResolutionTier.WIKIDATA,
            match_confidence=0.85,
            original_query="Test Entity",
            matched_label="Test Entity",
        )

        # Minimal entity data - only required fields
        mock_entity_data = {
            "qid": "Q12345",
            "label": "Test Entity",
            "url": "https://www.wikidata.org/wiki/Q12345",
        }

        mock_wikidata_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="Q12345",
            results=[mock_entity_data],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with (
            patch("ignifer.server._get_entity_resolver") as mock_resolver_getter,
            patch("ignifer.server._get_wikidata") as mock_wikidata_getter,
        ):
            mock_resolver = MagicMock()
            mock_resolver.resolve = AsyncMock(return_value=mock_resolution)
            mock_resolver_getter.return_value = mock_resolver

            mock_wikidata = MagicMock()
            mock_wikidata.lookup_by_qid = AsyncMock(return_value=mock_wikidata_result)
            mock_wikidata_getter.return_value = mock_wikidata

            result = await entity_lookup.fn(name="Test Entity")

            # Basic info should be present
            assert "ENTITY LOOKUP" in result
            assert "Test Entity" in result
            assert "Q12345" in result

            # Optional sections should not cause errors
            # No TYPE if instance_of is missing or empty
            # No KEY FACTS if no facts available
            # No ALIASES if none
            # No RELATED ENTITIES if count is 0
            assert "Resolution: wikidata" in result
            assert "Source: Wikidata" in result
