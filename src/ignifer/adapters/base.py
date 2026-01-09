"""Base protocol and error hierarchy for OSINT adapters.

This module defines the OSINTAdapter protocol that all data source adapters
must implement, along with a standardized error hierarchy for consistent
error handling across all adapters.
"""

from typing import Protocol, runtime_checkable

from ignifer.models import OSINTResult, QualityTier, QueryParams


@runtime_checkable
class OSINTAdapter(Protocol):
    """Protocol for all OSINT data source adapters.

    All adapters MUST implement this protocol. The @runtime_checkable
    decorator enables isinstance() checks without explicit inheritance.

    Error Handling Contract:
    - AdapterTimeoutError: Network timeouts (unexpected)
    - AdapterParseError: Malformed API responses (unexpected)
    - AdapterAuthError: Authentication failures (unexpected)
    - OSINTResult(status=RateLimited): Rate limiting (expected)
    - OSINTResult(status=NoData): No results found (expected)
    """

    @property
    def source_name(self) -> str:
        """Unique identifier for this data source (e.g., 'gdelt', 'opensky')."""
        ...

    @property
    def base_quality_tier(self) -> QualityTier:
        """Default quality tier for this source's data."""
        ...

    async def query(self, params: QueryParams) -> OSINTResult:
        """Execute a query against this data source.

        Args:
            params: Query parameters including topic, time_range, etc.

        Returns:
            OSINTResult with status, data, and source attribution.

        Raises:
            AdapterTimeoutError: If the request times out.
            AdapterParseError: If the response cannot be parsed.
            AdapterAuthError: If authentication fails.
        """
        ...

    async def health_check(self) -> bool:
        """Check if the data source is reachable and responding.

        Returns:
            True if healthy, False otherwise.
        """
        ...


class AdapterError(Exception):
    """Base exception for all adapter errors.

    All adapter exceptions inherit from this class, enabling
    catch-all handling at the tool/server level.

    Attributes:
        source_name: The adapter that raised this error.
        message: Human-readable error description.
    """

    def __init__(self, source_name: str, message: str) -> None:
        self.source_name = source_name
        self.message = message
        super().__init__(f"[{source_name}] {message}")


class AdapterTimeoutError(AdapterError):
    """Raised when an adapter request times out.

    This is an UNEXPECTED failure - the API was unreachable or too slow.
    Callers should consider retry with backoff or cache fallback.
    """

    def __init__(self, source_name: str, timeout_seconds: float | None = None) -> None:
        msg = "Request timed out"
        if timeout_seconds is not None:
            msg = f"Request timed out after {timeout_seconds}s"
        super().__init__(source_name, msg)
        self.timeout_seconds = timeout_seconds


class AdapterParseError(AdapterError):
    """Raised when an API response cannot be parsed.

    This is an UNEXPECTED failure - the API returned malformed data.
    This typically indicates an API schema change or corruption.
    """

    def __init__(self, source_name: str, details: str | None = None) -> None:
        msg = "Failed to parse API response"
        if details:
            msg = f"Failed to parse API response: {details}"
        super().__init__(source_name, msg)
        self.details = details


class AdapterAuthError(AdapterError):
    """Raised when authentication fails.

    This is an UNEXPECTED failure - credentials are invalid or expired.
    Callers should NOT retry without fixing credentials.
    """

    def __init__(self, source_name: str, details: str | None = None) -> None:
        msg = "Authentication failed"
        if details:
            msg = f"Authentication failed: {details}"
        super().__init__(source_name, msg)
        self.details = details


__all__ = [
    "OSINTAdapter",
    "AdapterError",
    "AdapterTimeoutError",
    "AdapterParseError",
    "AdapterAuthError",
]
