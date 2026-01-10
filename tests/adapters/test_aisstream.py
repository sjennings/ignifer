"""Tests for AISStream adapter."""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from ignifer.adapters.aisstream import AISStreamAdapter
from ignifer.adapters.base import AdapterAuthError, AdapterParseError, AdapterTimeoutError
from ignifer.config import reset_settings
from ignifer.models import QualityTier, QueryParams, ResultStatus


def load_fixture(name: str) -> dict[str, Any]:
    """Load JSON fixture file."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / name
    return json.loads(fixture_path.read_text())


@pytest.fixture(autouse=True)
def reset_settings_fixture():
    """Reset settings singleton before each test."""
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def mock_aisstream_credentials(monkeypatch):
    """Set mock AISStream credentials in environment."""
    monkeypatch.setenv("IGNIFER_AISSTREAM_KEY", "test_api_key_12345")
    reset_settings()  # Force reload with new env vars
    yield
    reset_settings()


@pytest.fixture
def clear_aisstream_credentials(monkeypatch):
    """Ensure no AISStream credentials are set."""
    monkeypatch.delenv("IGNIFER_AISSTREAM_KEY", raising=False)
    # Prevent loading credentials from config file
    monkeypatch.setattr("ignifer.config._load_config_file", lambda *args, **kwargs: {})
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def position_message() -> dict[str, Any]:
    """Load AISStream position message fixture."""
    return load_fixture("aisstream_message.json")


class MockWebSocket:
    """Mock WebSocket connection for testing."""

    def __init__(
        self,
        messages: list[dict[str, Any]] | None = None,
        error_on_connect: Exception | None = None,
        error_on_send: Exception | None = None,
        error_on_recv: Exception | None = None,
        recv_timeout: bool = False,
        recv_raises_timeout_when_empty: bool = False,
    ):
        self.messages = messages or []
        self.message_index = 0
        self.error_on_connect = error_on_connect
        self.error_on_send = error_on_send
        self.error_on_recv = error_on_recv
        self.recv_timeout = recv_timeout
        self.recv_raises_timeout_when_empty = recv_raises_timeout_when_empty
        self.sent_messages: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        if self.error_on_send:
            raise self.error_on_send
        self.sent_messages.append(message)

    async def recv(self) -> str:
        if self.error_on_recv:
            raise self.error_on_recv
        if self.recv_timeout:
            await asyncio.sleep(10)  # Will trigger timeout
        if self.message_index < len(self.messages):
            msg = self.messages[self.message_index]
            self.message_index += 1
            return json.dumps(msg)
        # No more messages
        if self.recv_raises_timeout_when_empty:
            # Simulate inner wait_for timeout (adapter catches this and continues loop)
            raise asyncio.TimeoutError()
        # Default: wait forever (will trigger outer timeout)
        await asyncio.sleep(100)
        return ""

    async def close(self) -> None:
        self.closed = True

    async def __aenter__(self) -> "MockWebSocket":
        if self.error_on_connect:
            raise self.error_on_connect
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.closed = True


class TestAISStreamAdapter:
    """Tests for AISStreamAdapter class."""

    def test_source_name(self, mock_aisstream_credentials) -> None:
        """Test that source_name property returns 'aisstream'."""
        adapter = AISStreamAdapter()
        assert adapter.source_name == "aisstream"

    def test_base_quality_tier(self, mock_aisstream_credentials) -> None:
        """Test that base_quality_tier is HIGH (AIS transponder data)."""
        adapter = AISStreamAdapter()
        assert adapter.base_quality_tier == QualityTier.HIGH

    @pytest.mark.asyncio
    async def test_query_success(
        self, mock_aisstream_credentials, position_message
    ) -> None:
        """Test successful query by MMSI returns OSINTResult with SUCCESS status."""
        mock_ws = MockWebSocket(messages=[position_message])

        with patch("ignifer.adapters.aisstream.websockets.connect", return_value=mock_ws):
            adapter = AISStreamAdapter()
            result = await adapter.query(QueryParams(query="123456789"))

            assert result.status == ResultStatus.SUCCESS
            assert len(result.results) == 1
            assert result.results[0]["mmsi"] == "123456789"
            assert result.results[0]["vessel_name"] == "EVER GIVEN"
            assert result.results[0]["latitude"] == 37.7749
            assert result.results[0]["longitude"] == -122.4194
            assert result.results[0]["speed_over_ground"] == 12.5
            assert result.results[0]["destination"] == "LONG BEACH"
            assert len(result.sources) == 1
            assert result.sources[0].source == "aisstream"
            assert result.sources[0].quality == QualityTier.HIGH

            await adapter.close()

    @pytest.mark.asyncio
    async def test_get_vessel_position_success(
        self, mock_aisstream_credentials, position_message
    ) -> None:
        """Test get_vessel_position returns vessel position data."""
        mock_ws = MockWebSocket(messages=[position_message])

        with patch("ignifer.adapters.aisstream.websockets.connect", return_value=mock_ws):
            adapter = AISStreamAdapter()
            result = await adapter.get_vessel_position("123456789")

            assert result.status == ResultStatus.SUCCESS
            assert len(result.results) == 1
            assert result.results[0]["mmsi"] == "123456789"
            assert result.results[0]["imo"] == 9876543
            assert result.results[0]["course_over_ground"] == 225.0
            assert result.results[0]["heading"] == 223

            await adapter.close()

    @pytest.mark.asyncio
    async def test_query_invalid_mmsi_format(self, mock_aisstream_credentials) -> None:
        """Test query with invalid MMSI format returns NO_DATA with error."""
        adapter = AISStreamAdapter()

        # Too short
        result = await adapter.query(QueryParams(query="12345"))
        assert result.status == ResultStatus.NO_DATA
        assert "Invalid MMSI format" in result.error  # type: ignore[operator]

        # Non-numeric
        result = await adapter.query(QueryParams(query="ABC123456"))
        assert result.status == ResultStatus.NO_DATA
        assert "Invalid MMSI format" in result.error  # type: ignore[operator]

        await adapter.close()

    @pytest.mark.asyncio
    async def test_no_credentials_raises_auth_error(
        self, clear_aisstream_credentials
    ) -> None:
        """Test that missing credentials raises AdapterAuthError with helpful message."""
        adapter = AISStreamAdapter()

        with pytest.raises(AdapterAuthError) as exc_info:
            await adapter.query(QueryParams(query="123456789"))

        assert exc_info.value.source_name == "aisstream"
        assert "IGNIFER_AISSTREAM_KEY" in str(exc_info.value)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_websocket_auth_error(self, mock_aisstream_credentials) -> None:
        """Test WebSocket 401 response raises AdapterAuthError."""
        from unittest.mock import MagicMock

        from websockets.exceptions import InvalidStatus

        # Create a mock response with status_code attribute
        mock_response = MagicMock()
        mock_response.status_code = 401
        error = InvalidStatus(mock_response)
        mock_ws = MockWebSocket(error_on_connect=error)

        with patch("ignifer.adapters.aisstream.websockets.connect", return_value=mock_ws):
            adapter = AISStreamAdapter()

            with pytest.raises(AdapterAuthError) as exc_info:
                await adapter.get_vessel_position("123456789")

            assert exc_info.value.source_name == "aisstream"
            assert "Invalid API key" in str(exc_info.value)

            await adapter.close()

    @pytest.mark.asyncio
    async def test_websocket_error_message(
        self, mock_aisstream_credentials
    ) -> None:
        """Test AISStream error message in WebSocket response raises AdapterAuthError."""
        error_msg = {
            "MessageType": "Error",
            "Message": "Invalid API key",
        }
        mock_ws = MockWebSocket(messages=[error_msg])

        with patch("ignifer.adapters.aisstream.websockets.connect", return_value=mock_ws):
            adapter = AISStreamAdapter()

            with pytest.raises(AdapterAuthError) as exc_info:
                await adapter.get_vessel_position("123456789")

            assert exc_info.value.source_name == "aisstream"
            assert "Invalid API key" in str(exc_info.value)

            await adapter.close()

    @pytest.mark.asyncio
    async def test_websocket_connection_failure_retry(
        self, mock_aisstream_credentials
    ) -> None:
        """Test WebSocket connection failure with exponential backoff retry."""
        from websockets.exceptions import WebSocketException

        call_count = 0

        def mock_connect(*args: Any, **kwargs: Any) -> MockWebSocket:
            nonlocal call_count
            call_count += 1
            # All attempts fail to trigger retry behavior
            return MockWebSocket(error_on_connect=WebSocketException("Connection failed"))

        with patch(
            "ignifer.adapters.aisstream.websockets.connect",
            side_effect=mock_connect
        ):
            adapter = AISStreamAdapter()

            # Should fail after MAX_RETRIES (2) attempts
            with pytest.raises(AdapterTimeoutError):
                await adapter.get_vessel_position("123456789")

            # Verify retries happened (MAX_RETRIES = 2)
            assert call_count == 2

            await adapter.close()

    @pytest.mark.asyncio
    async def test_websocket_disconnect_reconnect(
        self, mock_aisstream_credentials, position_message
    ) -> None:
        """Test WebSocket disconnect triggers reconnection attempt."""
        from websockets.exceptions import ConnectionClosed

        call_count = 0

        def mock_connect(*args: Any, **kwargs: Any) -> MockWebSocket:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First connection succeeds but recv fails
                mock_ws = MockWebSocket(error_on_recv=ConnectionClosed(None, None))  # type: ignore[arg-type]
                return mock_ws
            # Subsequent connections succeed with data
            return MockWebSocket(messages=[position_message])

        with patch(
            "ignifer.adapters.aisstream.websockets.connect",
            side_effect=mock_connect
        ):
            adapter = AISStreamAdapter()
            result = await adapter.get_vessel_position("123456789")

            assert result.status == ResultStatus.SUCCESS
            assert call_count == 2  # Initial + 1 retry

            await adapter.close()

    @pytest.mark.asyncio
    async def test_slow_data_returns_no_data(
        self, mock_aisstream_credentials
    ) -> None:
        """Test that slow data reception returns NO_DATA (not timeout error)."""
        # Create mock that has very slow recv - simulates vessel not broadcasting
        # With DATA_TIMEOUT exceeded, should return empty positions (NO_DATA)
        mock_ws = MockWebSocket(messages=[], recv_raises_timeout_when_empty=True)

        with patch(
            "ignifer.adapters.aisstream.websockets.connect",
            return_value=mock_ws
        ):
            adapter = AISStreamAdapter()
            # Override timeout for faster test
            adapter.DEFAULT_TIMEOUT = 0.1

            result = await adapter.get_vessel_position("123456789")

            # Should return NO_DATA, not raise timeout error
            assert result.status == ResultStatus.NO_DATA
            assert result.results == []

            await adapter.close()

    @pytest.mark.asyncio
    async def test_no_position_data_returns_no_data(
        self, mock_aisstream_credentials
    ) -> None:
        """Test that no position messages returns NO_DATA status."""
        # Empty message list - recv will raise TimeoutError repeatedly
        # until the outer loop time expires, then return empty positions
        mock_ws = MockWebSocket(messages=[], recv_raises_timeout_when_empty=True)

        with patch("ignifer.adapters.aisstream.websockets.connect", return_value=mock_ws):
            adapter = AISStreamAdapter()
            adapter.DEFAULT_TIMEOUT = 0.2  # Speed up test (outer timeout)

            result = await adapter.get_vessel_position("123456789")

            assert result.status == ResultStatus.NO_DATA
            assert "No position data found" in result.error  # type: ignore[operator]

            await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_aisstream_credentials) -> None:
        """Test health check returns True when connection succeeds."""
        mock_ws = MockWebSocket(messages=[])

        with patch("ignifer.adapters.aisstream.websockets.connect", return_value=mock_ws):
            adapter = AISStreamAdapter()
            result = await adapter.health_check()

            assert result is True
            await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_failure_no_credentials(
        self, clear_aisstream_credentials
    ) -> None:
        """Test health check returns False when credentials not configured."""
        adapter = AISStreamAdapter()
        result = await adapter.health_check()

        assert result is False
        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_failure_connection_error(
        self, mock_aisstream_credentials
    ) -> None:
        """Test health check returns False when connection fails."""
        from websockets.exceptions import WebSocketException

        def failing_connect(*args: Any, **kwargs: Any) -> MockWebSocket:
            # Return a MockWebSocket that raises on enter
            return MockWebSocket(error_on_connect=WebSocketException("Connection refused"))

        with patch(
            "ignifer.adapters.aisstream.websockets.connect",
            side_effect=failing_connect
        ):
            adapter = AISStreamAdapter()
            result = await adapter.health_check()

            assert result is False
            await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_error_response(
        self, mock_aisstream_credentials
    ) -> None:
        """Test health check returns False when API returns error."""
        error_msg = {"MessageType": "Error", "Message": "Rate limited"}
        mock_ws = MockWebSocket(messages=[error_msg])

        with patch("ignifer.adapters.aisstream.websockets.connect", return_value=mock_ws):
            adapter = AISStreamAdapter()
            result = await adapter.health_check()

            assert result is False
            await adapter.close()

    @pytest.mark.asyncio
    async def test_subscription_message_format(
        self, mock_aisstream_credentials, position_message
    ) -> None:
        """Test that subscription message has correct format."""
        mock_ws = MockWebSocket(messages=[position_message])

        with patch("ignifer.adapters.aisstream.websockets.connect", return_value=mock_ws):
            adapter = AISStreamAdapter()
            await adapter.get_vessel_position("123456789")

            # Verify subscription message
            assert len(mock_ws.sent_messages) == 1
            sent = json.loads(mock_ws.sent_messages[0])

            assert "APIKey" in sent
            assert sent["APIKey"] == "test_api_key_12345"
            assert "BoundingBoxes" in sent
            assert "FiltersShipMMSI" in sent
            assert sent["FiltersShipMMSI"] == ["123456789"]

            await adapter.close()

    @pytest.mark.asyncio
    async def test_parse_position_message_complete(
        self, mock_aisstream_credentials, position_message
    ) -> None:
        """Test that position message is fully parsed."""
        mock_ws = MockWebSocket(messages=[position_message])

        with patch("ignifer.adapters.aisstream.websockets.connect", return_value=mock_ws):
            adapter = AISStreamAdapter()
            result = await adapter.get_vessel_position("123456789")

            assert result.status == ResultStatus.SUCCESS
            pos = result.results[0]

            # Verify all fields are parsed
            assert pos["mmsi"] == "123456789"
            assert pos["imo"] == 9876543
            assert pos["vessel_name"] == "EVER GIVEN"
            assert pos["vessel_type"] == 70
            assert pos["latitude"] == 37.7749
            assert pos["longitude"] == -122.4194
            assert pos["speed_over_ground"] == 12.5
            assert pos["course_over_ground"] == 225.0
            assert pos["heading"] == 223
            assert pos["navigational_status"] == 0
            assert pos["destination"] == "LONG BEACH"
            assert pos["eta"] == "04-15 12:00"
            assert pos["timestamp"] == "2024-01-15T10:30:45Z"
            assert pos["country"] == "Panama"

            await adapter.close()

    @pytest.mark.asyncio
    async def test_non_position_messages_ignored(
        self, mock_aisstream_credentials, position_message
    ) -> None:
        """Test that non-position messages are ignored."""
        other_msg = {"MessageType": "StaticDataReport", "Message": {}}
        mock_ws = MockWebSocket(messages=[other_msg, position_message])

        with patch("ignifer.adapters.aisstream.websockets.connect", return_value=mock_ws):
            adapter = AISStreamAdapter()
            result = await adapter.get_vessel_position("123456789")

            assert result.status == ResultStatus.SUCCESS
            assert len(result.results) == 1
            assert result.results[0]["vessel_name"] == "EVER GIVEN"

            await adapter.close()

    @pytest.mark.asyncio
    async def test_invalid_json_raises_parse_error(
        self, mock_aisstream_credentials
    ) -> None:
        """Test that invalid JSON response raises AdapterParseError."""
        mock_ws = MockWebSocket(messages=[])
        mock_ws.messages = ["not valid json"]  # type: ignore[list-item]

        # Override recv to return raw string
        async def bad_recv() -> str:
            return "not valid json {"

        mock_ws.recv = bad_recv  # type: ignore[method-assign]

        with patch("ignifer.adapters.aisstream.websockets.connect", return_value=mock_ws):
            adapter = AISStreamAdapter()

            with pytest.raises(AdapterParseError) as exc_info:
                await adapter.get_vessel_position("123456789")

            assert exc_info.value.source_name == "aisstream"
            assert "Invalid JSON" in str(exc_info.value)

            await adapter.close()

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    async def test_cache_hit(
        self, mock_aisstream_credentials, position_message, tmp_path
    ) -> None:
        """Test that cached results are returned without making WebSocket connection."""
        from ignifer.cache import CacheManager, MemoryCache, SQLiteCache

        # Create a cache with temporary SQLite database
        db_path = tmp_path / "test_cache.db"
        cache = CacheManager(l1=MemoryCache(), l2=SQLiteCache(db_path=db_path))

        connection_count = 0

        def counting_connect(*args: Any, **kwargs: Any) -> MockWebSocket:
            nonlocal connection_count
            connection_count += 1
            return MockWebSocket(messages=[position_message])

        with patch(
            "ignifer.adapters.aisstream.websockets.connect",
            side_effect=counting_connect
        ):
            adapter = AISStreamAdapter(cache=cache)

            # First request - will connect to WebSocket
            result1 = await adapter.get_vessel_position("123456789")
            assert result1.status == ResultStatus.SUCCESS
            assert connection_count == 1

            # Second request - should hit cache, not WebSocket
            result2 = await adapter.get_vessel_position("123456789")
            assert result2.status == ResultStatus.SUCCESS
            assert connection_count == 1  # No additional connection

            # Verify same data
            assert result2.results[0]["vessel_name"] == "EVER GIVEN"

            await adapter.close()
            await cache.close()

    @pytest.mark.asyncio
    async def test_close_method(self, mock_aisstream_credentials) -> None:
        """Test that close() method exists and runs without error."""
        adapter = AISStreamAdapter()

        # close() should not raise, even without any connections
        await adapter.close()

    @pytest.mark.asyncio
    async def test_api_key_not_logged(
        self, mock_aisstream_credentials, position_message, caplog
    ) -> None:
        """Test that API key is never logged."""
        mock_ws = MockWebSocket(messages=[position_message])

        with patch("ignifer.adapters.aisstream.websockets.connect", return_value=mock_ws):
            adapter = AISStreamAdapter()
            await adapter.get_vessel_position("123456789")

            # Check that API key is not in any log messages
            for record in caplog.records:
                assert "test_api_key_12345" not in record.message

            await adapter.close()

    @pytest.mark.asyncio
    async def test_general_websocket_error_returns_parse_error(
        self, mock_aisstream_credentials
    ) -> None:
        """Test that general non-auth error messages raise AdapterParseError."""
        error_msg = {
            "MessageType": "Error",
            "Message": "Rate limit exceeded",
        }
        mock_ws = MockWebSocket(messages=[error_msg])

        with patch("ignifer.adapters.aisstream.websockets.connect", return_value=mock_ws):
            adapter = AISStreamAdapter()

            with pytest.raises(AdapterParseError) as exc_info:
                await adapter.get_vessel_position("123456789")

            assert "Rate limit exceeded" in str(exc_info.value)

            await adapter.close()
