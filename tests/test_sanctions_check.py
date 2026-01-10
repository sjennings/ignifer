"""Tests for sanctions_check tool."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from ignifer.adapters.base import AdapterError, AdapterTimeoutError
from ignifer.models import (
    ConfidenceLevel,
    OSINTResult,
    QualityTier,
    ResultStatus,
    SourceAttribution,
    SourceMetadata,
)
from ignifer.server import sanctions_check


def _create_mock_sanctions_result(
    entity_name: str = "Rosneft",
    is_sanctioned: bool = True,
    is_pep: bool = False,
    match_score: float = 0.98,
    schema: str = "Company",
    sanctions_lists: str = "us_ofac_sdn, eu_fsf",
    first_seen: str = "2014-07-16",
    last_seen: str = "2024-01-15",
    aliases: str = "",
    nationality: str = "ru",
    position: str = "",
    referents: str | None = None,
) -> OSINTResult:
    """Create a mock OpenSanctions result for testing."""
    result_data: dict[str, str | int | float | bool | None] = {
        "entity_id": "NK-12345",
        "caption": entity_name,
        "schema": schema,
        "name": entity_name,
        "aliases": aliases if aliases else f"{entity_name} Corp",
        "birth_date": None,
        "nationality": nationality,
        "position": position,
        "sanctions_lists": sanctions_lists,
        "sanctions_count": len(sanctions_lists.split(", ")) if sanctions_lists else 0,
        "is_sanctioned": is_sanctioned,
        "is_pep": is_pep,
        "is_poi": False,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "referents": referents,
        "referents_count": len(referents.split(", ")) if referents else 0,
        "url": "https://www.opensanctions.org/entities/NK-12345",
        "match_score": match_score,
        "match_confidence": "VERY_LIKELY" if match_score >= 0.9 else "LIKELY",
    }

    if is_pep and not is_sanctioned:
        result_data["pep_status"] = "PEP - NOT CURRENTLY SANCTIONED"
        result_data["due_diligence_note"] = "Enhanced due diligence recommended for PEPs"

    return OSINTResult(
        status=ResultStatus.SUCCESS,
        query=entity_name,
        results=[result_data],
        sources=[
            SourceAttribution(
                source="opensanctions",
                quality=QualityTier.HIGH,
                confidence=ConfidenceLevel.VERY_LIKELY,
                metadata=SourceMetadata(
                    source_name="opensanctions",
                    source_url="https://api.opensanctions.org/match/default",
                    retrieved_at=datetime.now(timezone.utc),
                ),
            )
        ],
        retrieved_at=datetime.now(timezone.utc),
    )


class TestSanctionsCheckTool:
    @pytest.mark.asyncio
    async def test_sanctions_check_success_match(self) -> None:
        """Sanctions check returns formatted output for sanctioned entity."""
        mock_result = _create_mock_sanctions_result()

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Rosneft")

            assert "SANCTIONS SCREENING" in result
            assert "ROSNEFT" in result.upper()
            assert "MATCH RESULT: MATCH" in result
            assert "Currently Sanctioned: YES" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_pep_detection(self) -> None:
        """PEP-only entity shows appropriate status (FR19)."""
        mock_result = _create_mock_sanctions_result(
            entity_name="John Smith",
            is_sanctioned=False,
            is_pep=True,
            schema="Person",
            sanctions_lists="",
            match_score=0.85,
            position="Minister of Finance",
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("John Smith")

            assert "PEP" in result
            assert "NOT SANCTIONED" in result
            assert "due diligence" in result.lower()
            assert "FR19" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_no_match(self) -> None:
        """No match returns appropriate message."""
        mock_result = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="Example Corp",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Example Corp")

            assert "EXAMPLE CORP" in result.upper()
            assert "NO MATCH" in result
            assert "No matches found" in result
            assert "opensanctions.org" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_partial_match(self) -> None:
        """Low confidence match shows PARTIAL MATCH status."""
        mock_result = _create_mock_sanctions_result(
            entity_name="Rosneft Corp",
            is_sanctioned=False,
            is_pep=False,
            match_score=0.55,  # Low confidence
            schema="Company",
            sanctions_lists="",
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Rosneft Corp")

            assert "PARTIAL MATCH" in result
            assert "VERIFICATION RECOMMENDED" in result
            assert "55% (LOW)" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_empty_entity(self) -> None:
        """Empty entity returns validation error."""
        result = await sanctions_check.fn("")
        assert "provide" in result.lower()
        assert "entity" in result.lower()
        assert "Examples" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_whitespace_entity(self) -> None:
        """Whitespace-only entity returns validation error."""
        result = await sanctions_check.fn("   ")
        assert "provide" in result.lower()
        assert "entity" in result.lower()

    @pytest.mark.asyncio
    async def test_sanctions_check_multiple_sanctions_lists(self) -> None:
        """Multiple sanctions lists are displayed correctly."""
        mock_result = _create_mock_sanctions_result(
            entity_name="Test Entity",
            sanctions_lists="us_ofac_sdn, eu_fsf, gb_hmt_sanctions, ch_seco_sanctions",
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Test Entity")

            assert "Sanctions Lists:" in result
            assert "US OFAC SDN" in result
            assert "EU Financial Sanctions" in result
            assert "UK HMT" in result
            assert "Swiss SECO" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_vessel(self) -> None:
        """Vessel screening returns correct format."""
        mock_result = _create_mock_sanctions_result(
            entity_name="Akademik Cherskiy",
            schema="Vessel",
            sanctions_lists="us_ofac_sdn, eu_fsf",
            nationality="ru",
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Akademik Cherskiy")

            assert "AKADEMIK CHERSKIY" in result.upper()
            assert "Type: Vessel" in result
            assert "MATCH" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_rate_limited(self) -> None:
        """Rate limiting returns user-friendly message."""
        mock_result = OSINTResult(
            status=ResultStatus.RATE_LIMITED,
            query="Test Entity",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Test Entity")

            assert "Rate Limited" in result
            assert "OpenSanctions" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_timeout(self) -> None:
        """Timeout returns user-friendly message."""
        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.side_effect = AdapterTimeoutError(
                "opensanctions", 15.0
            )
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Rosneft")

            assert "Timed Out" in result
            assert "Rosneft" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_adapter_error(self) -> None:
        """Adapter errors return user-friendly message."""
        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.side_effect = AdapterError(
                "opensanctions", "Connection failed"
            )
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Rosneft")

            assert "Unable to Retrieve Data" in result
            assert "Connection failed" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_source_attribution(self) -> None:
        """Output includes OpenSanctions source info."""
        mock_result = _create_mock_sanctions_result()

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Rosneft")

            assert "OpenSanctions" in result
            assert "opensanctions.org" in result
            assert "Data retrieved" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_includes_timestamps(self) -> None:
        """First seen and last seen dates are included."""
        mock_result = _create_mock_sanctions_result(
            first_seen="2014-07-16",
            last_seen="2024-01-15",
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Rosneft")

            assert "First Sanctioned: 2014-07-16" in result
            assert "Last Updated: 2024-01-15" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_high_confidence(self) -> None:
        """High match score (>=0.9) displays HIGH confidence."""
        mock_result = _create_mock_sanctions_result(match_score=0.98)

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Rosneft")

            assert "98% (HIGH)" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_medium_confidence(self) -> None:
        """Medium match score (0.7-0.9) displays MEDIUM confidence."""
        mock_result = _create_mock_sanctions_result(match_score=0.75)

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Rosneft")

            assert "75% (MEDIUM)" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_includes_aliases(self) -> None:
        """Alias information is displayed in output."""
        mock_result = _create_mock_sanctions_result(
            entity_name="Rosneft Oil Company",
            aliases="Rosneft, PAO Rosneft, NK Rosneft",
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Rosneft")

            assert "Aliases:" in result
            assert "PAO Rosneft" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_person_with_position(self) -> None:
        """Person screening includes position information."""
        mock_result = _create_mock_sanctions_result(
            entity_name="Viktor Vekselberg",
            schema="Person",
            position="Oligarch, Businessman",
            nationality="ru",
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Viktor Vekselberg")

            assert "Type: Person" in result
            assert "Position:" in result
            assert "Oligarch" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_cross_references(self) -> None:
        """Output includes cross-reference links."""
        mock_result = _create_mock_sanctions_result()

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Rosneft")

            assert "CROSS-REFERENCES" in result
            assert "OpenSanctions ID:" in result or "OpenSanctions:" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_no_match_suggestions(self) -> None:
        """No match result includes verification suggestions."""
        mock_result = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="Unknown Corp",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Unknown Corp")

            assert "legal name" in result.lower()
            assert "alternative spellings" in result.lower() or "transliterations" in result.lower()
            assert "parent/subsidiary" in result.lower()

    @pytest.mark.asyncio
    async def test_sanctions_check_exception_handling(self) -> None:
        """Generic exceptions are caught and formatted."""
        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.side_effect = ValueError("Unexpected error")
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Test Entity")

            assert "Error" in result
            assert "Test Entity" in result
            assert "try again" in result.lower()

    @pytest.mark.asyncio
    async def test_sanctions_check_pep_includes_due_diligence(self) -> None:
        """PEP result includes due diligence note."""
        mock_result = _create_mock_sanctions_result(
            entity_name="Political Figure",
            is_sanctioned=False,
            is_pep=True,
            schema="Person",
            sanctions_lists="",
            position="Government Official",
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Political Figure")

            assert "Enhanced due diligence" in result
            assert "Politically Exposed" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_sanctioned_pep(self) -> None:
        """Entity that is both sanctioned AND a PEP shows both statuses."""
        mock_result = _create_mock_sanctions_result(
            entity_name="Sanctioned Official",
            is_sanctioned=True,
            is_pep=True,
            schema="Person",
            sanctions_lists="us_ofac_sdn",
            position="Former Government Official",
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Sanctioned Official")

            # Primary status should be MATCH (sanctioned)
            assert "MATCH RESULT: MATCH" in result
            assert "Currently Sanctioned: YES" in result
            # Should also note PEP status
            assert "Politically Exposed Person" in result or "PEP STATUS" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_entity_information_section(self) -> None:
        """Entity information section includes all expected fields."""
        mock_result = _create_mock_sanctions_result(
            entity_name="Test Company Ltd",
            schema="Company",
            aliases="TC Ltd, Test Co",
            nationality="gb",
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Test Company Ltd")

            assert "ENTITY INFORMATION" in result
            assert "Type: Company" in result
            assert "Full Name:" in result
            assert "Nationality:" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_databases_searched(self) -> None:
        """No match message lists databases that were searched."""
        mock_result = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="Clean Entity",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Clean Entity")

            assert "Databases Searched:" in result
            assert "US OFAC SDN" in result
            assert "EU Financial Sanctions" in result
            assert "UN Security Council" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_includes_associated_entities(self) -> None:
        """Associated entities (referents) are displayed when available."""
        mock_result = _create_mock_sanctions_result(
            entity_name="Rosneft Oil Company",
            referents="NK-ABC123, NK-DEF456, NK-GHI789",
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Rosneft Oil Company")

            assert "ASSOCIATED ENTITIES" in result
            assert "NK-ABC123" in result
            assert "NK-DEF456" in result
            assert "NK-GHI789" in result

    @pytest.mark.asyncio
    async def test_sanctions_check_very_low_confidence(self) -> None:
        """Very low confidence match (< 0.5) displays VERY LOW indicator for sanctioned entities."""
        # Note: Score < 0.5 for non-sanctioned entities returns NO MATCH (by design)
        # This test verifies VERY LOW confidence is displayed for sanctioned entities with low scores
        mock_result = _create_mock_sanctions_result(
            entity_name="Possible Sanctioned Corp",
            is_sanctioned=True,  # Must be sanctioned to show as MATCH
            is_pep=False,
            match_score=0.35,  # Very low confidence
            schema="Company",
            sanctions_lists="us_ofac_sdn",
        )

        with patch("ignifer.server._get_opensanctions") as mock_adapter:
            adapter_instance = AsyncMock()
            adapter_instance.search_entity.return_value = mock_result
            mock_adapter.return_value = adapter_instance

            result = await sanctions_check.fn("Possible Sanctioned Corp")

            assert "35%" in result
            assert "VERY LOW" in result
            assert "MATCH RESULT: MATCH" in result
