"""Tests for the track_vessel tool."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from ignifer.adapters.base import AdapterAuthError, AdapterError, AdapterTimeoutError
from ignifer.models import (
    ConfidenceLevel,
    OSINTResult,
    QualityTier,
    ResultStatus,
    SourceAttribution,
    SourceMetadata,
)
from ignifer.server import (
    _format_vessel_course,
    _format_vessel_credentials_error,
    _format_vessel_disambiguation,
    _format_vessel_heading,
    _format_vessel_output,
    _format_vessel_position_coords,
    _format_vessel_speed,
    _get_cardinal_direction,
    _get_navigational_status_name,
    _get_vessel_type_name,
    _identify_vessel_identifier,
    _is_vessel_stationary,
    track_vessel,
)


class TestIdentifyVesselIdentifier:
    """Tests for vessel identifier type detection."""

    def test_mmsi_nine_digits(self) -> None:
        """MMSI is detected for 9-digit numbers."""
        id_type, normalized = _identify_vessel_identifier("367596480")
        assert id_type == "mmsi"
        assert normalized == "367596480"

    def test_mmsi_with_whitespace(self) -> None:
        """MMSI with surrounding whitespace is stripped."""
        id_type, normalized = _identify_vessel_identifier("  353136000  ")
        assert id_type == "mmsi"
        assert normalized == "353136000"

    def test_imo_with_space(self) -> None:
        """IMO number with space is detected."""
        id_type, normalized = _identify_vessel_identifier("IMO 9811000")
        assert id_type == "imo"
        assert normalized == "9811000"

    def test_imo_without_space(self) -> None:
        """IMO number without space is detected."""
        id_type, normalized = _identify_vessel_identifier("IMO9811000")
        assert id_type == "imo"
        assert normalized == "9811000"

    def test_imo_lowercase(self) -> None:
        """IMO number with lowercase prefix is detected."""
        id_type, normalized = _identify_vessel_identifier("imo 9811000")
        assert id_type == "imo"
        assert normalized == "9811000"

    def test_imo_mixed_case(self) -> None:
        """IMO number with mixed case prefix is detected."""
        id_type, normalized = _identify_vessel_identifier("Imo9312456")
        assert id_type == "imo"
        assert normalized == "9312456"

    def test_vessel_name_simple(self) -> None:
        """Simple vessel name is detected."""
        id_type, normalized = _identify_vessel_identifier("Ever Given")
        assert id_type == "vessel_name"
        assert normalized == "Ever Given"

    def test_vessel_name_uppercase(self) -> None:
        """Uppercase vessel name is detected."""
        id_type, normalized = _identify_vessel_identifier("MAERSK ALABAMA")
        assert id_type == "vessel_name"
        assert normalized == "MAERSK ALABAMA"

    def test_vessel_name_with_numbers(self) -> None:
        """Vessel name with numbers is detected (not MMSI if not 9 digits)."""
        id_type, normalized = _identify_vessel_identifier("MSC OSCAR 3")
        assert id_type == "vessel_name"
        assert normalized == "MSC OSCAR 3"

    def test_eight_digit_number_is_vessel_name(self) -> None:
        """8-digit number is treated as vessel name (not MMSI)."""
        id_type, normalized = _identify_vessel_identifier("12345678")
        assert id_type == "vessel_name"
        assert normalized == "12345678"

    def test_ten_digit_number_is_vessel_name(self) -> None:
        """10-digit number is treated as vessel name (not MMSI)."""
        id_type, normalized = _identify_vessel_identifier("1234567890")
        assert id_type == "vessel_name"
        assert normalized == "1234567890"

    def test_imo_wrong_length_is_vessel_name(self) -> None:
        """IMO with wrong digit count is treated as vessel name."""
        # IMO followed by 6 digits (should be 7)
        id_type, normalized = _identify_vessel_identifier("IMO 981100")
        assert id_type == "vessel_name"
        assert normalized == "IMO 981100"

    def test_imo_with_letters_is_vessel_name(self) -> None:
        """IMO with letters after prefix is treated as vessel name."""
        id_type, normalized = _identify_vessel_identifier("IMO ABC1234")
        assert id_type == "vessel_name"
        assert normalized == "IMO ABC1234"


class TestCardinalDirection:
    """Tests for cardinal direction calculation."""

    def test_north_at_zero(self) -> None:
        """0 degrees is North."""
        assert _get_cardinal_direction(0.0) == "North"

    def test_north_at_360(self) -> None:
        """360 degrees is North."""
        assert _get_cardinal_direction(360.0) == "North"

    def test_north_sector_boundary(self) -> None:
        """North sector spans 337.5 to 22.5."""
        assert _get_cardinal_direction(22.4) == "North"
        assert _get_cardinal_direction(337.5) == "North"
        assert _get_cardinal_direction(350.0) == "North"

    def test_northeast_sector(self) -> None:
        """Northeast sector spans 22.5 to 67.5."""
        assert _get_cardinal_direction(22.5) == "Northeast"
        assert _get_cardinal_direction(45.0) == "Northeast"
        assert _get_cardinal_direction(67.4) == "Northeast"

    def test_east_sector(self) -> None:
        """East sector spans 67.5 to 112.5."""
        assert _get_cardinal_direction(67.5) == "East"
        assert _get_cardinal_direction(90.0) == "East"
        assert _get_cardinal_direction(112.4) == "East"

    def test_southwest_sector(self) -> None:
        """Southwest sector spans 202.5 to 247.5."""
        assert _get_cardinal_direction(225.0) == "Southwest"
        assert _get_cardinal_direction(210.0) == "Southwest"

    def test_northwest_sector(self) -> None:
        """Northwest sector spans 292.5 to 337.5."""
        assert _get_cardinal_direction(315.0) == "Northwest"
        assert _get_cardinal_direction(312.0) == "Northwest"


class TestVesselFormatHelpers:
    """Tests for vessel formatting helper functions."""

    def test_format_vessel_speed(self) -> None:
        """Speed is formatted in knots and km/h."""
        result = _format_vessel_speed(12.5)
        assert "12.5 kts" in result
        assert "23.2 km/h" in result

    def test_format_vessel_speed_zero(self) -> None:
        """Zero speed is formatted correctly."""
        result = _format_vessel_speed(0.0)
        assert "0.0 kts" in result
        assert "0.0 km/h" in result

    def test_format_vessel_speed_none(self) -> None:
        """None speed returns N/A."""
        assert _format_vessel_speed(None) == "N/A"

    def test_format_vessel_course_southwest(self) -> None:
        """Southwest course is formatted correctly."""
        result = _format_vessel_course(225.0)
        assert "225" in result
        assert "Southwest" in result

    def test_format_vessel_course_north(self) -> None:
        """North course (0 degrees) is formatted correctly."""
        result = _format_vessel_course(0.0)
        assert "0" in result
        assert "North" in result

    def test_format_vessel_course_east(self) -> None:
        """East course (90 degrees) is formatted correctly."""
        result = _format_vessel_course(90.0)
        assert "90" in result
        assert "East" in result

    def test_format_vessel_course_none(self) -> None:
        """None course returns N/A."""
        assert _format_vessel_course(None) == "N/A"

    def test_format_vessel_heading_with_cardinal(self) -> None:
        """Heading is formatted with cardinal direction."""
        result = _format_vessel_heading(312)
        assert "312" in result
        assert "Northwest" in result

    def test_format_vessel_heading_none(self) -> None:
        """None heading returns N/A."""
        assert _format_vessel_heading(None) == "N/A"

    def test_format_vessel_heading_511_not_available(self) -> None:
        """AIS value 511 (not available) returns N/A."""
        assert _format_vessel_heading(511) == "N/A"

    def test_format_vessel_heading_zero(self) -> None:
        """Heading 0 (North) is formatted correctly."""
        result = _format_vessel_heading(0)
        assert "0" in result
        assert "North" in result

    def test_format_vessel_position_coords_positive(self) -> None:
        """Positive lat/lon formatted correctly."""
        result = _format_vessel_position_coords(37.7749, 122.4194)
        assert "37.7749" in result
        assert "N" in result
        assert "122.4194" in result
        assert "E" in result

    def test_format_vessel_position_coords_negative(self) -> None:
        """Negative lat/lon formatted correctly."""
        result = _format_vessel_position_coords(-33.8688, -151.2093)
        assert "33.8688" in result
        assert "S" in result
        assert "151.2093" in result
        assert "W" in result

    def test_format_vessel_position_coords_none(self) -> None:
        """None coordinates return N/A."""
        assert _format_vessel_position_coords(None, 122.0) == "N/A"
        assert _format_vessel_position_coords(37.0, None) == "N/A"
        assert _format_vessel_position_coords(None, None) == "N/A"


class TestVesselTypeMapping:
    """Tests for vessel type name mapping."""

    def test_cargo_vessel(self) -> None:
        """Cargo vessel type (70) returns Cargo."""
        assert _get_vessel_type_name(70) == "Cargo"

    def test_tanker_vessel(self) -> None:
        """Tanker type (80) returns Tanker."""
        assert _get_vessel_type_name(80) == "Tanker"

    def test_passenger_vessel(self) -> None:
        """Passenger type (60) returns Passenger."""
        assert _get_vessel_type_name(60) == "Passenger"

    def test_fishing_vessel(self) -> None:
        """Fishing type (30) returns Fishing."""
        assert _get_vessel_type_name(30) == "Fishing"

    def test_tug(self) -> None:
        """Tug type (52) returns Tug."""
        assert _get_vessel_type_name(52) == "Tug"

    def test_cargo_range(self) -> None:
        """Cargo range (70-79) returns Cargo."""
        assert _get_vessel_type_name(75) == "Cargo"
        assert _get_vessel_type_name(79) == "Cargo"

    def test_tanker_range(self) -> None:
        """Tanker range (80-89) returns Tanker."""
        assert _get_vessel_type_name(85) == "Tanker"
        assert _get_vessel_type_name(89) == "Tanker"

    def test_unknown_type(self) -> None:
        """None type returns Unknown."""
        assert _get_vessel_type_name(None) == "Unknown"

    def test_out_of_range_type(self) -> None:
        """Out of range type returns Type X."""
        assert "Type" in _get_vessel_type_name(100)


class TestNavigationalStatusMapping:
    """Tests for navigational status name mapping."""

    def test_under_way(self) -> None:
        """Status 0 returns Under way using engine."""
        assert _get_navigational_status_name(0) == "Under way using engine"

    def test_at_anchor(self) -> None:
        """Status 1 returns At anchor."""
        assert _get_navigational_status_name(1) == "At anchor"

    def test_moored(self) -> None:
        """Status 5 returns Moored."""
        assert _get_navigational_status_name(5) == "Moored"

    def test_fishing(self) -> None:
        """Status 7 returns Engaged in fishing."""
        assert _get_navigational_status_name(7) == "Engaged in fishing"

    def test_unknown_status(self) -> None:
        """None status returns Unknown."""
        assert _get_navigational_status_name(None) == "Unknown"


class TestIsVesselStationary:
    """Tests for stationary vessel detection."""

    def test_at_anchor(self) -> None:
        """Vessel at anchor is stationary."""
        is_stationary, reason = _is_vessel_stationary(1, 0.0)
        assert is_stationary is True
        assert "anchor" in reason.lower()

    def test_moored(self) -> None:
        """Moored vessel is stationary."""
        is_stationary, reason = _is_vessel_stationary(5, 0.0)
        assert is_stationary is True
        assert "Moored" in reason

    def test_aground(self) -> None:
        """Aground vessel is stationary."""
        is_stationary, reason = _is_vessel_stationary(6, 0.0)
        assert is_stationary is True
        assert "Aground" in reason

    def test_low_speed(self) -> None:
        """Vessel with speed < 0.5 kts is stationary."""
        is_stationary, reason = _is_vessel_stationary(0, 0.3)
        assert is_stationary is True
        assert "speed" in reason.lower()

    def test_moving(self) -> None:
        """Vessel under way with speed is not stationary."""
        is_stationary, reason = _is_vessel_stationary(0, 12.5)
        assert is_stationary is False
        assert reason == ""

    def test_status_none_with_speed(self) -> None:
        """Vessel with unknown status but speed is not stationary."""
        is_stationary, reason = _is_vessel_stationary(None, 10.0)
        assert is_stationary is False


class TestFormatVesselOutput:
    """Tests for vessel output formatting."""

    @pytest.fixture
    def sample_vessel_position(self) -> dict[str, str | int | float | None]:
        """Sample vessel position data from AISStream."""
        return {
            "mmsi": "353136000",
            "imo": 9811000,
            "vessel_name": "EVER GIVEN",
            "vessel_type": 70,
            "latitude": 31.2340,
            "longitude": 32.3456,
            "speed_over_ground": 12.5,
            "course_over_ground": 315.0,
            "heading": 312,
            "navigational_status": 0,
            "destination": "ROTTERDAM",
            "eta": "01-15 08:00",
            "timestamp": "2026-01-09T15:30:00Z",
            "country": "Panama",
        }

    def test_format_with_position_data(
        self, sample_vessel_position: dict[str, str | int | float | None]
    ) -> None:
        """Vessel with position data is formatted correctly."""
        retrieved_at = datetime(2026, 1, 9, 15, 30, 15, tzinfo=timezone.utc)
        result = _format_vessel_output("353136000", sample_vessel_position, retrieved_at)

        assert "VESSEL TRACKING: EVER GIVEN" in result
        assert "CURRENT POSITION" in result
        assert "31.2340" in result
        assert "32.3456" in result
        assert "12.5 kts" in result
        assert "315" in result
        assert "Northwest" in result
        assert "VESSEL INFO" in result
        assert "353136000" in result
        assert "9811000" in result
        assert "Cargo" in result
        assert "Panama" in result
        assert "ROTTERDAM" in result
        assert "AISStream" in result

    def test_format_vessel_not_broadcasting(self) -> None:
        """Vessel not broadcasting shows appropriate message."""
        retrieved_at = datetime(2026, 1, 9, 15, 30, 15, tzinfo=timezone.utc)
        result = _format_vessel_output("367596480", None, retrieved_at)

        assert "VESSEL TRACKING: 367596480" in result
        assert "not currently broadcasting AIS" in result
        assert "AIS transponder" in result
        assert "intentionally disable" in result

    def test_format_stationary_vessel(self) -> None:
        """Stationary vessel shows stationary indicator."""
        position = {
            "mmsi": "123456789",
            "vessel_name": "TEST SHIP",
            "navigational_status": 1,  # At anchor
            "speed_over_ground": 0.0,
            "latitude": 37.0,
            "longitude": -122.0,
        }
        retrieved_at = datetime(2026, 1, 9, 15, 30, 15, tzinfo=timezone.utc)
        result = _format_vessel_output("123456789", position, retrieved_at)

        assert "anchor" in result.lower()


class TestFormatVesselCredentialsError:
    """Tests for credentials error formatting."""

    def test_credentials_error_contains_url(self) -> None:
        """Credentials error contains AISStream URL."""
        result = _format_vessel_credentials_error()
        assert "aisstream.io" in result

    def test_credentials_error_contains_env_var(self) -> None:
        """Credentials error contains environment variable name."""
        result = _format_vessel_credentials_error()
        assert "IGNIFER_AISSTREAM_KEY" in result

    def test_credentials_error_contains_config_info(self) -> None:
        """Credentials error contains config.toml info."""
        result = _format_vessel_credentials_error()
        assert "config.toml" in result


class TestFormatVesselDisambiguation:
    """Tests for vessel disambiguation formatting."""

    def test_disambiguation_shows_multiple_vessels(self) -> None:
        """Disambiguation message shows multiple vessels."""
        matches = [
            {
                "vessel_name": "EVER GIVEN",
                "mmsi": "353136000",
                "imo": 9811000,
                "vessel_type": 70,
                "country": "Panama",
                "destination": "ROTTERDAM",
            },
            {
                "vessel_name": "EVER GREEN",
                "mmsi": "353136001",
                "vessel_type": 70,
                "country": "Taiwan",
            },
        ]
        result = _format_vessel_disambiguation(matches, "Ever")

        assert "Multiple Vessels Found" in result
        assert "EVER GIVEN" in result
        assert "EVER GREEN" in result
        assert "353136000" in result
        assert "353136001" in result
        assert "MMSI or IMO" in result


class TestTrackVesselTool:
    """Tests for the track_vessel tool."""

    @pytest.fixture
    def mock_vessel_position(self) -> dict[str, str | int | float | None]:
        """Sample vessel position from AISStreamAdapter."""
        return {
            "mmsi": "123456789",
            "imo": 9876543,
            "vessel_name": "EVER GIVEN",
            "vessel_type": 70,
            "latitude": 37.7749,
            "longitude": -122.4194,
            "speed_over_ground": 12.5,
            "course_over_ground": 225.0,
            "heading": 223,
            "navigational_status": 0,
            "destination": "LONG BEACH",
            "eta": "04-15 12:00",
            "timestamp": "2024-01-15T10:30:45Z",
            "country": "Panama",
        }

    @pytest.mark.asyncio
    async def test_track_by_mmsi_success(
        self,
        mock_vessel_position: dict[str, str | int | float | None],
    ) -> None:
        """Tracking by MMSI returns formatted output."""
        position_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="123456789",
            results=[mock_vessel_position],
            sources=[
                SourceAttribution(
                    source="aisstream",
                    quality=QualityTier.HIGH,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,
                    metadata=SourceMetadata(
                        source_name="aisstream",
                        source_url="wss://stream.aisstream.io/v0/stream",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_aisstream") as mock_get:
            adapter = AsyncMock()
            adapter.get_vessel_position.return_value = position_result
            mock_get.return_value = adapter

            result = await track_vessel.fn("123456789")

            assert "VESSEL TRACKING: EVER GIVEN" in result
            assert "CURRENT POSITION" in result
            assert "37.7749" in result
            assert "122.4194" in result
            assert "12.5 kts" in result
            assert "VESSEL INFO" in result
            assert "123456789" in result
            assert "Panama" in result
            assert "AISStream" in result

    @pytest.mark.asyncio
    async def test_track_vessel_not_broadcasting(self) -> None:
        """Vessel not broadcasting returns appropriate message."""
        no_data_result = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="999999999",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
            error="No position data found for MMSI '999999999'",
        )

        with patch("ignifer.server._get_aisstream") as mock_get:
            adapter = AsyncMock()
            adapter.get_vessel_position.return_value = no_data_result
            mock_get.return_value = adapter

            result = await track_vessel.fn("999999999")

            assert "not currently broadcasting AIS" in result
            assert "AIS transponder" in result

    @pytest.mark.asyncio
    async def test_track_by_imo_returns_limitation_message(self) -> None:
        """IMO lookup returns helpful limitation message."""
        with patch("ignifer.server._get_aisstream") as mock_get:
            adapter = AsyncMock()
            mock_get.return_value = adapter

            result = await track_vessel.fn("IMO 9811000")

            assert "IMO Lookup" in result
            assert "9811000" in result
            assert "MMSI" in result
            assert "marinetraffic.com" in result

    @pytest.mark.asyncio
    async def test_track_by_vessel_name_returns_limitation_message(self) -> None:
        """Vessel name search returns helpful limitation message."""
        with patch("ignifer.server._get_aisstream") as mock_get:
            adapter = AsyncMock()
            mock_get.return_value = adapter

            result = await track_vessel.fn("Ever Given")

            assert "Vessel Name Search" in result
            assert "Ever Given" in result
            assert "MMSI" in result
            assert "marinetraffic.com" in result or "vesselfinder.com" in result

    @pytest.mark.asyncio
    async def test_credentials_not_configured(self) -> None:
        """Missing credentials returns helpful setup message."""
        with patch("ignifer.server._get_aisstream") as mock_get:
            adapter = AsyncMock()
            adapter.get_vessel_position.side_effect = AdapterAuthError(
                "aisstream",
                "AISStream requires API key. Set IGNIFER_AISSTREAM_KEY...",
            )
            mock_get.return_value = adapter

            result = await track_vessel.fn("123456789")

            assert "AISStream Authentication Required" in result
            assert "aisstream.io" in result
            assert "IGNIFER_AISSTREAM_KEY" in result

    @pytest.mark.asyncio
    async def test_timeout_error(self) -> None:
        """Timeout errors return user-friendly message."""
        with patch("ignifer.server._get_aisstream") as mock_get:
            adapter = AsyncMock()
            adapter.get_vessel_position.side_effect = AdapterTimeoutError("aisstream", 30.0)
            mock_get.return_value = adapter

            result = await track_vessel.fn("123456789")

            assert "Timed Out" in result
            assert "123456789" in result
            assert "Suggestions" in result

    @pytest.mark.asyncio
    async def test_rate_limited(self) -> None:
        """Rate limiting returns appropriate message."""
        rate_limited_result = OSINTResult(
            status=ResultStatus.RATE_LIMITED,
            query="123456789",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_aisstream") as mock_get:
            adapter = AsyncMock()
            adapter.get_vessel_position.return_value = rate_limited_result
            mock_get.return_value = adapter

            result = await track_vessel.fn("123456789")

            assert "Rate Limited" in result
            assert "Suggestions" in result

    @pytest.mark.asyncio
    async def test_adapter_error_handling(self) -> None:
        """Generic adapter errors are handled gracefully."""
        with patch("ignifer.server._get_aisstream") as mock_get:
            adapter = AsyncMock()
            adapter.get_vessel_position.side_effect = AdapterError(
                "aisstream", "Connection refused"
            )
            mock_get.return_value = adapter

            result = await track_vessel.fn("123456789")

            assert "Unable to Track Vessel" in result
            assert "123456789" in result
            assert "Connection refused" in result

    @pytest.mark.asyncio
    async def test_unexpected_exception_handling(self) -> None:
        """Unexpected exceptions are caught and return error message."""
        with patch("ignifer.server._get_aisstream") as mock_get:
            adapter = AsyncMock()
            adapter.get_vessel_position.side_effect = ValueError("Unexpected error")
            mock_get.return_value = adapter

            result = await track_vessel.fn("123456789")

            assert "Error" in result
            assert "123456789" in result

    @pytest.mark.asyncio
    async def test_empty_identifier(self) -> None:
        """Empty identifier returns validation error."""
        result = await track_vessel.fn("")

        assert "Invalid Identifier" in result
        assert "MMSI" in result
        assert "IMO" in result

    @pytest.mark.asyncio
    async def test_whitespace_only_identifier(self) -> None:
        """Whitespace-only identifier returns validation error."""
        result = await track_vessel.fn("   ")

        assert "Invalid Identifier" in result

    @pytest.mark.asyncio
    async def test_stationary_vessel_indicator(
        self,
    ) -> None:
        """Stationary vessel shows at anchor indicator."""
        stationary_position: dict[str, str | int | float | None] = {
            "mmsi": "123456789",
            "vessel_name": "ANCHORED SHIP",
            "vessel_type": 70,
            "latitude": 37.0,
            "longitude": -122.0,
            "speed_over_ground": 0.0,
            "course_over_ground": 0.0,
            "heading": 0,
            "navigational_status": 1,  # At anchor
            "country": "USA",
        }

        position_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="123456789",
            results=[stationary_position],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_aisstream") as mock_get:
            adapter = AsyncMock()
            adapter.get_vessel_position.return_value = position_result
            mock_get.return_value = adapter

            result = await track_vessel.fn("123456789")

            assert "At anchor" in result
            assert "ANCHORED SHIP" in result


class TestVesselIdentifierEdgeCases:
    """Edge case tests for vessel identifier handling."""

    def test_mmsi_with_leading_zeros(self) -> None:
        """MMSI starting with zeros is detected correctly."""
        id_type, normalized = _identify_vessel_identifier("012345678")
        assert id_type == "mmsi"
        assert normalized == "012345678"

    def test_imo_extra_whitespace(self) -> None:
        """IMO with extra whitespace is handled."""
        id_type, normalized = _identify_vessel_identifier("IMO   9811000")
        assert id_type == "imo"
        assert normalized == "9811000"

    def test_vessel_name_single_word(self) -> None:
        """Single word vessel name is detected."""
        id_type, normalized = _identify_vessel_identifier("Titanic")
        assert id_type == "vessel_name"
        assert normalized == "Titanic"

    def test_vessel_name_with_special_chars(self) -> None:
        """Vessel name with special characters is detected."""
        id_type, normalized = _identify_vessel_identifier("MSC ISABELLA F")
        assert id_type == "vessel_name"
        assert normalized == "MSC ISABELLA F"
