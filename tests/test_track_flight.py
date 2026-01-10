"""Tests for the track_flight tool."""

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
    _analyze_track_coverage,
    _format_altitude,
    _format_heading,
    _format_position,
    _format_speed,
    _format_timestamp,
    _identify_aircraft_identifier,
    track_flight,
)


class TestIdentifyAircraftIdentifier:
    """Tests for identifier type detection."""

    def test_icao24_lowercase(self) -> None:
        """ICAO24 codes are detected and lowercased."""
        id_type, normalized = _identify_aircraft_identifier("abc123")
        assert id_type == "icao24"
        assert normalized == "abc123"

    def test_icao24_uppercase(self) -> None:
        """Uppercase ICAO24 codes are normalized to lowercase."""
        id_type, normalized = _identify_aircraft_identifier("ABC123")
        assert id_type == "icao24"
        assert normalized == "abc123"

    def test_icao24_mixed_case(self) -> None:
        """Mixed case ICAO24 codes are normalized."""
        id_type, normalized = _identify_aircraft_identifier("AbC12F")
        assert id_type == "icao24"
        assert normalized == "abc12f"

    def test_us_tail_number(self) -> None:
        """US N-numbers are detected as tail numbers."""
        id_type, normalized = _identify_aircraft_identifier("N12345")
        assert id_type == "tail_number"
        assert normalized == "N12345"

    def test_us_tail_number_alphanumeric(self) -> None:
        """US N-numbers with letters are detected."""
        id_type, normalized = _identify_aircraft_identifier("N123AB")
        assert id_type == "tail_number"
        assert normalized == "N123AB"

    def test_uk_tail_number(self) -> None:
        """UK G-prefix registrations are detected as tail numbers."""
        id_type, normalized = _identify_aircraft_identifier("G-ABCD")
        assert id_type == "tail_number"
        assert normalized == "G-ABCD"

    def test_french_tail_number(self) -> None:
        """French F-prefix registrations are detected as tail numbers."""
        id_type, normalized = _identify_aircraft_identifier("F-GXYZ")
        assert id_type == "tail_number"
        assert normalized == "F-GXYZ"

    def test_callsign_airline(self) -> None:
        """Airline callsigns are detected."""
        id_type, normalized = _identify_aircraft_identifier("UAL123")
        assert id_type == "callsign"
        assert normalized == "UAL123"

    def test_callsign_short(self) -> None:
        """Short callsigns are detected."""
        id_type, normalized = _identify_aircraft_identifier("BAW1")
        assert id_type == "callsign"
        assert normalized == "BAW1"

    def test_callsign_lowercase_normalized(self) -> None:
        """Lowercase callsigns are uppercased."""
        id_type, normalized = _identify_aircraft_identifier("ual123")
        assert id_type == "callsign"
        assert normalized == "UAL123"

    def test_whitespace_stripped(self) -> None:
        """Whitespace is stripped from identifiers."""
        id_type, normalized = _identify_aircraft_identifier("  UAL123  ")
        assert id_type == "callsign"
        assert normalized == "UAL123"

    def test_non_hex_six_chars_is_callsign(self) -> None:
        """Six chars that aren't valid hex are treated as callsign."""
        # "UAL123" starts with U which isn't hex, but is 6 chars
        id_type, normalized = _identify_aircraft_identifier("ZZZZZ1")
        assert id_type == "callsign"
        assert normalized == "ZZZZZ1"


class TestFormatHelpers:
    """Tests for formatting helper functions."""

    def test_format_heading_north(self) -> None:
        """North heading is formatted correctly."""
        result = _format_heading(0.0)
        assert "000" in result
        assert "North" in result

    def test_format_heading_northeast(self) -> None:
        """Northeast heading is formatted correctly."""
        result = _format_heading(45.0)
        assert "045" in result
        assert "Northeast" in result

    def test_format_heading_south(self) -> None:
        """South heading is formatted correctly."""
        result = _format_heading(180.0)
        assert "180" in result
        assert "South" in result

    def test_format_heading_none(self) -> None:
        """None heading returns N/A."""
        assert _format_heading(None) == "N/A"

    def test_format_altitude_cruising(self) -> None:
        """Cruising altitude is formatted in feet and meters."""
        result = _format_altitude(10668.0, False)
        assert "ft" in result
        assert "m" in result
        assert "35,000" in result or "35000" in result

    def test_format_altitude_on_ground(self) -> None:
        """On ground returns 'On Ground'."""
        result = _format_altitude(0.0, True)
        assert result == "On Ground"

    def test_format_altitude_none(self) -> None:
        """None altitude returns N/A."""
        result = _format_altitude(None, False)
        assert result == "N/A"

    def test_format_speed(self) -> None:
        """Speed is formatted in knots and km/h."""
        result = _format_speed(230.0)  # ~450 kts
        assert "kts" in result
        assert "km/h" in result

    def test_format_speed_none(self) -> None:
        """None speed returns N/A."""
        assert _format_speed(None) == "N/A"

    def test_format_timestamp(self) -> None:
        """Unix timestamp is formatted as UTC string."""
        # 2026-01-07 12:52:00 UTC
        ts = 1767790320
        result = _format_timestamp(ts)
        assert "2026-01-07" in result
        assert "12:52:00" in result
        assert "UTC" in result

    def test_format_timestamp_none(self) -> None:
        """None timestamp returns N/A."""
        assert _format_timestamp(None) == "N/A"

    def test_format_position_north_east(self) -> None:
        """Northern, Eastern position is formatted correctly."""
        result = _format_position(37.7749, 122.4194)
        assert "37.7749" in result
        assert "N" in result
        assert "122.4194" in result
        assert "E" in result

    def test_format_position_south_west(self) -> None:
        """Southern, Western position is formatted correctly."""
        result = _format_position(-33.8688, -151.2093)
        assert "33.8688" in result
        assert "S" in result
        assert "151.2093" in result
        assert "W" in result

    def test_format_position_none(self) -> None:
        """None coordinates return N/A."""
        assert _format_position(None, 122.0) == "N/A"
        assert _format_position(37.0, None) == "N/A"
        assert _format_position(None, None) == "N/A"


class TestAnalyzeTrackCoverage:
    """Tests for track coverage analysis."""

    def test_empty_waypoints(self) -> None:
        """Empty waypoints returns 'No data'."""
        coverage, gaps = _analyze_track_coverage([])
        assert coverage == "No data"
        assert gaps == []

    def test_single_waypoint(self) -> None:
        """Single waypoint returns 'Limited'."""
        coverage, gaps = _analyze_track_coverage([{"timestamp": 1000}])
        assert coverage == "Limited"
        assert gaps == []

    def test_good_coverage(self) -> None:
        """Continuous coverage returns 'Good'."""
        # Waypoints every 60 seconds (no gaps > 300s)
        waypoints = [{"timestamp": 1000 + i * 60} for i in range(10)]
        coverage, gaps = _analyze_track_coverage(waypoints)
        assert "Good" in coverage
        assert gaps == []

    def test_fair_coverage(self) -> None:
        """One or two gaps returns 'Fair'."""
        waypoints = [
            {"timestamp": 1000},
            {"timestamp": 1060},
            {"timestamp": 2000},  # Gap > 300s
            {"timestamp": 2060},
        ]
        coverage, gaps = _analyze_track_coverage(waypoints)
        assert "Fair" in coverage
        assert len(gaps) == 1

    def test_poor_coverage(self) -> None:
        """Multiple gaps returns 'Poor'."""
        waypoints = [
            {"timestamp": 1000},
            {"timestamp": 2000},  # Gap
            {"timestamp": 3000},  # Gap
            {"timestamp": 4000},  # Gap
        ]
        coverage, gaps = _analyze_track_coverage(waypoints)
        assert "Poor" in coverage
        assert len(gaps) == 3


class TestTrackFlightTool:
    """Tests for the track_flight tool."""

    @pytest.fixture
    def mock_opensky_state(self) -> dict[str, str | int | float | bool | None]:
        """Sample aircraft state from OpenSky."""
        return {
            "icao24": "abc123",
            "callsign": "UAL123",
            "origin_country": "United States",
            "time_position": 1767790320,
            "last_contact": 1767790320,
            "longitude": -122.4194,
            "latitude": 37.7749,
            "altitude_barometric": 10668.0,
            "on_ground": False,
            "velocity": 230.0,
            "heading": 45.0,
            "vertical_rate": 0.0,
            "altitude_geometric": 10700.0,
            "squawk": "1234",
        }

    @pytest.fixture
    def mock_track_waypoints(self) -> list[dict[str, str | int | float | bool | None]]:
        """Sample track waypoints from OpenSky."""
        base_ts = 1767700000
        return [
            {
                "icao24": "abc123",
                "callsign": "UAL123",
                "start_time": base_ts,
                "end_time": base_ts + 3600,
                "timestamp": base_ts + i * 60,
                "latitude": 37.0 + i * 0.01,
                "longitude": -122.0 - i * 0.01,
                "altitude": 10000 + i * 100,
                "heading": 45.0,
                "on_ground": False,
            }
            for i in range(10)
        ]

    @pytest.mark.asyncio
    async def test_track_by_callsign_success(
        self,
        mock_opensky_state: dict[str, str | int | float | bool | None],
        mock_track_waypoints: list[dict[str, str | int | float | bool | None]],
    ) -> None:
        """Tracking by callsign returns formatted output."""
        state_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="UAL123",
            results=[mock_opensky_state],
            sources=[
                SourceAttribution(
                    source="opensky",
                    quality=QualityTier.HIGH,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,
                    metadata=SourceMetadata(
                        source_name="opensky",
                        source_url="https://opensky-network.org/api/states/all",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        track_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="abc123",
            results=mock_track_waypoints,
            sources=[
                SourceAttribution(
                    source="opensky",
                    quality=QualityTier.HIGH,
                    confidence=ConfidenceLevel.ALMOST_CERTAIN,
                    metadata=SourceMetadata(
                        source_name="opensky",
                        source_url="https://opensky-network.org/api/tracks/all",
                        retrieved_at=datetime.now(timezone.utc),
                    ),
                )
            ],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_opensky") as mock_get:
            adapter = AsyncMock()
            adapter.query.return_value = state_result
            adapter.get_track.return_value = track_result
            mock_get.return_value = adapter

            result = await track_flight.fn("UAL123")

            assert "FLIGHT TRACKING: UAL123" in result
            assert "CURRENT POSITION" in result
            assert "United States" in result
            assert "TRACK HISTORY" in result
            assert "OpenSky Network" in result

    @pytest.mark.asyncio
    async def test_track_by_icao24_success(
        self,
        mock_opensky_state: dict[str, str | int | float | bool | None],
        mock_track_waypoints: list[dict[str, str | int | float | bool | None]],
    ) -> None:
        """Tracking by ICAO24 returns formatted output."""
        state_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="abc123",
            results=[mock_opensky_state],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        track_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="abc123",
            results=mock_track_waypoints,
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_opensky") as mock_get:
            adapter = AsyncMock()
            adapter.get_states.return_value = state_result
            adapter.get_track.return_value = track_result
            mock_get.return_value = adapter

            result = await track_flight.fn("abc123")

            assert "FLIGHT TRACKING: ABC123" in result
            assert "CURRENT POSITION" in result
            assert "ICAO24: abc123" in result

    @pytest.mark.asyncio
    async def test_track_tail_number_not_found(self) -> None:
        """Tail number lookup returns helpful message when not found."""
        no_data_result = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="N12345",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
            error="No aircraft found",
        )

        with patch("ignifer.server._get_opensky") as mock_get:
            adapter = AsyncMock()
            adapter.query.return_value = no_data_result
            mock_get.return_value = adapter

            result = await track_flight.fn("N12345")

            assert "Tail Number Lookup" in result
            assert "N12345" in result
            assert "Suggestions" in result

    @pytest.mark.asyncio
    async def test_flight_not_broadcasting(
        self, mock_track_waypoints: list[dict[str, str | int | float | bool | None]]
    ) -> None:
        """Aircraft not broadcasting returns last known position."""
        no_state_result = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="UAL123",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_opensky") as mock_get:
            adapter = AsyncMock()
            adapter.query.return_value = no_state_result
            mock_get.return_value = adapter

            result = await track_flight.fn("UAL123")

            # Should indicate not broadcasting
            assert "not currently broadcasting" in result
            # Should explain ADS-B limitations
            assert "ADS-B" in result

    @pytest.mark.asyncio
    async def test_credentials_not_configured(self) -> None:
        """Missing credentials returns helpful setup message."""
        with patch("ignifer.server._get_opensky") as mock_get:
            adapter = AsyncMock()
            adapter.query.side_effect = AdapterAuthError(
                "opensky",
                "OpenSky requires authentication. Set IGNIFER_OPENSKY_USERNAME...",
            )
            mock_get.return_value = adapter

            result = await track_flight.fn("UAL123")

            assert "OpenSky Authentication Required" in result
            assert "opensky-network.org" in result
            assert "IGNIFER_OPENSKY_USERNAME" in result
            assert "config.toml" in result

    @pytest.mark.asyncio
    async def test_timeout_error(self) -> None:
        """Timeout errors return user-friendly message."""
        with patch("ignifer.server._get_opensky") as mock_get:
            adapter = AsyncMock()
            adapter.query.side_effect = AdapterTimeoutError("opensky", 15.0)
            mock_get.return_value = adapter

            result = await track_flight.fn("UAL123")

            assert "Timed Out" in result
            assert "UAL123" in result
            assert "Suggestions" in result

    @pytest.mark.asyncio
    async def test_rate_limited(self) -> None:
        """Rate limiting returns appropriate message."""
        rate_limited_result = OSINTResult(
            status=ResultStatus.RATE_LIMITED,
            query="UAL123",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_opensky") as mock_get:
            adapter = AsyncMock()
            adapter.query.return_value = rate_limited_result
            mock_get.return_value = adapter

            result = await track_flight.fn("UAL123")

            assert "Rate Limited" in result
            assert "Suggestions" in result

    @pytest.mark.asyncio
    async def test_track_history_with_gaps(
        self, mock_opensky_state: dict[str, str | int | float | bool | None]
    ) -> None:
        """Track history with gaps indicates coverage issues."""
        state_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="UAL123",
            results=[mock_opensky_state],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        # Create waypoints with large gaps (>300s each)
        base_ts = 1767700000
        waypoints_with_gaps: list[dict[str, str | int | float | bool | None]] = [
            {
                "timestamp": base_ts,
                "latitude": 37.0,
                "longitude": -122.0,
                "altitude": 10000,
                "heading": 45,
                "on_ground": False,
            },
            {
                "timestamp": base_ts + 1000,  # Gap > 300s
                "latitude": 37.1,
                "longitude": -122.1,
                "altitude": 10100,
                "heading": 45,
                "on_ground": False,
            },
            {
                "timestamp": base_ts + 2000,  # Gap > 300s
                "latitude": 37.2,
                "longitude": -122.2,
                "altitude": 10200,
                "heading": 45,
                "on_ground": False,
            },
            {
                "timestamp": base_ts + 3000,  # Gap > 300s
                "latitude": 37.3,
                "longitude": -122.3,
                "altitude": 10300,
                "heading": 45,
                "on_ground": False,
            },
        ]

        track_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="abc123",
            results=waypoints_with_gaps,
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_opensky") as mock_get:
            adapter = AsyncMock()
            adapter.query.return_value = state_result
            adapter.get_track.return_value = track_result
            mock_get.return_value = adapter

            result = await track_flight.fn("UAL123")

            # Should indicate gaps in coverage
            assert "TRACK HISTORY" in result
            # Coverage should mention gaps
            assert "gaps" in result.lower() or "Poor" in result

    @pytest.mark.asyncio
    async def test_adapter_error_handling(self) -> None:
        """Generic adapter errors are handled gracefully."""
        with patch("ignifer.server._get_opensky") as mock_get:
            adapter = AsyncMock()
            adapter.query.side_effect = AdapterError("opensky", "Connection refused")
            mock_get.return_value = adapter

            result = await track_flight.fn("UAL123")

            assert "Unable to Track Flight" in result
            assert "UAL123" in result
            assert "Connection refused" in result

    @pytest.mark.asyncio
    async def test_unexpected_exception_handling(self) -> None:
        """Unexpected exceptions are caught and return error message."""
        with patch("ignifer.server._get_opensky") as mock_get:
            adapter = AsyncMock()
            adapter.query.side_effect = ValueError("Unexpected error")
            mock_get.return_value = adapter

            result = await track_flight.fn("UAL123")

            assert "Error" in result
            assert "UAL123" in result

    @pytest.mark.asyncio
    async def test_track_history_timeout_graceful_degradation(
        self, mock_opensky_state: dict[str, str | int | float | bool | None]
    ) -> None:
        """Track history timeout still returns state data."""
        state_result = OSINTResult(
            status=ResultStatus.SUCCESS,
            query="UAL123",
            results=[mock_opensky_state],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_opensky") as mock_get:
            adapter = AsyncMock()
            adapter.query.return_value = state_result
            adapter.get_track.side_effect = AdapterTimeoutError("opensky", 15.0)
            mock_get.return_value = adapter

            result = await track_flight.fn("UAL123")

            # Should still have current position
            assert "CURRENT POSITION" in result
            assert "United States" in result
            # Track history section should indicate no data
            assert "No track history" in result or "TRACK HISTORY" in result

    @pytest.mark.asyncio
    async def test_track_by_icao24_rate_limited(self) -> None:
        """ICAO24 lookup rate limiting returns appropriate message."""
        rate_limited_result = OSINTResult(
            status=ResultStatus.RATE_LIMITED,
            query="abc123",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        with patch("ignifer.server._get_opensky") as mock_get:
            adapter = AsyncMock()
            adapter.get_states.return_value = rate_limited_result
            mock_get.return_value = adapter

            result = await track_flight.fn("abc123")  # ICAO24 format

            assert "Rate Limited" in result
            assert "Suggestions" in result

    @pytest.mark.asyncio
    async def test_empty_identifier(self) -> None:
        """Empty identifier returns validation error."""
        result = await track_flight.fn("")

        assert "Invalid Identifier" in result
        assert "Callsign" in result
        assert "Tail number" in result
        assert "ICAO24" in result

    @pytest.mark.asyncio
    async def test_whitespace_only_identifier(self) -> None:
        """Whitespace-only identifier returns validation error."""
        result = await track_flight.fn("   ")

        assert "Invalid Identifier" in result
