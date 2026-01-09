"""Tests for adapter protocol and error hierarchy."""

from datetime import datetime, timezone

from ignifer.adapters import (
    AdapterAuthError,
    AdapterError,
    AdapterParseError,
    AdapterTimeoutError,
    OSINTAdapter,
)
from ignifer.models import (
    ConfidenceLevel,
    OSINTResult,
    QualityTier,
    QueryParams,
    ResultStatus,
    SourceAttribution,
    SourceMetadata,
)


class MockAdapter:
    """A minimal adapter that conforms to OSINTAdapter protocol."""

    @property
    def source_name(self) -> str:
        return "mock"

    @property
    def base_quality_tier(self) -> QualityTier:
        return QualityTier.MEDIUM

    async def query(self, params: QueryParams) -> OSINTResult:
        now = datetime.now(timezone.utc)
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=params.query,
            results=[{"mock": "data"}],
            sources=[
                SourceAttribution(
                    source="mock",
                    quality=self.base_quality_tier,
                    confidence=ConfidenceLevel.LIKELY,
                    metadata=SourceMetadata(
                        source_name="mock",
                        source_url="http://mock.example.com",
                        retrieved_at=now,
                    ),
                )
            ],
            retrieved_at=now,
        )

    async def health_check(self) -> bool:
        return True


class TestOSINTAdapterProtocol:
    def test_isinstance_works_with_conforming_class(self) -> None:
        """Protocol check works without explicit inheritance."""
        adapter = MockAdapter()
        assert isinstance(adapter, OSINTAdapter)

    def test_isinstance_fails_with_non_conforming_class(self) -> None:
        """Protocol check fails for classes missing required methods."""

        class IncompleteAdapter:
            @property
            def source_name(self) -> str:
                return "incomplete"

            # Missing: base_quality_tier, query, health_check

        adapter = IncompleteAdapter()
        assert not isinstance(adapter, OSINTAdapter)


class TestAdapterErrors:
    def test_adapter_error_includes_source_name(self) -> None:
        error = AdapterError("gdelt", "Something went wrong")
        assert "gdelt" in str(error)
        assert error.source_name == "gdelt"

    def test_timeout_error_includes_timeout_value(self) -> None:
        error = AdapterTimeoutError("opensky", timeout_seconds=10.0)
        assert "10.0s" in str(error)
        assert error.timeout_seconds == 10.0

    def test_timeout_error_without_timeout_value(self) -> None:
        error = AdapterTimeoutError("opensky")
        assert "Request timed out" in str(error)
        assert error.timeout_seconds is None

    def test_parse_error_includes_details(self) -> None:
        error = AdapterParseError("gdelt", details="Invalid JSON")
        assert "Invalid JSON" in str(error)

    def test_parse_error_without_details(self) -> None:
        error = AdapterParseError("gdelt")
        assert "Failed to parse API response" in str(error)
        assert error.details is None

    def test_auth_error_includes_details(self) -> None:
        error = AdapterAuthError("acled", details="Invalid API key")
        assert "Invalid API key" in str(error)

    def test_auth_error_without_details(self) -> None:
        error = AdapterAuthError("acled")
        assert "Authentication failed" in str(error)
        assert error.details is None

    def test_error_hierarchy(self) -> None:
        """All specific errors inherit from AdapterError."""
        assert issubclass(AdapterTimeoutError, AdapterError)
        assert issubclass(AdapterParseError, AdapterError)
        assert issubclass(AdapterAuthError, AdapterError)

    def test_exception_chaining(self) -> None:
        """Errors can chain original exceptions."""
        original = ValueError("original error")
        try:
            raise AdapterParseError("gdelt", "parse failed") from original
        except AdapterParseError as e:
            assert e.__cause__ is original
