# Story 1.4: Adapter Protocol & Error Hierarchy

Status: ready-for-dev

## Story

As a **developer**,
I want **a well-defined adapter interface with consistent error handling**,
so that **all data source adapters follow the same contract and errors are handled predictably**.

## Acceptance Criteria

1. **AC1: OSINTAdapter Protocol Created**
   - **Given** the models from Story 1.2
   - **When** I create `src/ignifer/adapters/base.py`
   - **Then** it defines:
     - `OSINTAdapter` Protocol with `@runtime_checkable` decorator
     - Protocol requires: `source_name` property, `base_quality_tier` property, `async query(params)` method, `async health_check()` method

2. **AC2: Error Hierarchy Created**
   - **Given** base.py exists
   - **When** I define error classes
   - **Then** it includes:
     - `AdapterError` base exception class
     - `AdapterTimeoutError(AdapterError)` for network timeouts
     - `AdapterParseError(AdapterError)` for malformed responses
     - `AdapterAuthError(AdapterError)` for authentication failures

3. **AC3: Protocol Runtime Check Works**
   - **Given** base.py exists
   - **When** I check `isinstance(adapter, OSINTAdapter)` on a conforming class
   - **Then** it returns `True`
   - **And** the check works at runtime without explicit inheritance

4. **AC4: Error Chaining Works**
   - **Given** an adapter raises `AdapterTimeoutError`
   - **When** the error is caught
   - **Then** it includes the source name in the error message
   - **And** the original exception is chained via `from`

5. **AC5: Module Exports Work**
   - **Given** adapters/__init__.py is updated
   - **When** I import `from ignifer.adapters import OSINTAdapter, AdapterError`
   - **Then** imports succeed
   - **And** `__all__` explicitly lists public exports

## Tasks / Subtasks

- [ ] Task 1: Create OSINTAdapter Protocol (AC: #1, #3)
  - [ ] 1.1: Define Protocol class with @runtime_checkable decorator
  - [ ] 1.2: Add source_name property returning str
  - [ ] 1.3: Add base_quality_tier property returning QualityTier
  - [ ] 1.4: Add async query(params: QueryParams) -> OSINTResult method
  - [ ] 1.5: Add async health_check() -> bool method

- [ ] Task 2: Create Error Hierarchy (AC: #2, #4)
  - [ ] 2.1: Create AdapterError base exception with source_name attribute
  - [ ] 2.2: Create AdapterTimeoutError(AdapterError)
  - [ ] 2.3: Create AdapterParseError(AdapterError)
  - [ ] 2.4: Create AdapterAuthError(AdapterError)
  - [ ] 2.5: Ensure all errors support exception chaining via `from`

- [ ] Task 3: Update adapters/__init__.py (AC: #5)
  - [ ] 3.1: Import all public classes from base.py
  - [ ] 3.2: Define __all__ with explicit exports

- [ ] Task 4: Create tests (AC: #3, #4)
  - [ ] 4.1: Create tests/adapters/test_base.py
  - [ ] 4.2: Test Protocol isinstance check with conforming class
  - [ ] 4.3: Test error hierarchy and exception chaining
  - [ ] 4.4: Verify error messages include source name

## Dev Notes

### CRITICAL: Architecture Compliance

**FROM project-context.md - Error Handling Contract:**

| Scenario | Handling | Type |
|----------|----------|------|
| Network timeout | `AdapterTimeoutError` | Exception |
| Rate limited | `OSINTResult(status=RateLimited)` | Result type |
| No data found | `OSINTResult(status=NoData)` | Result type |
| Malformed response | `AdapterParseError` | Exception |
| Auth failure | `AdapterAuthError` | Exception |

**CRITICAL RULE:** Exceptions for **unexpected** failures; Result type for **expected** operational states.

**FROM project-context.md - Adapter Rules:**
- **Layer boundary rule:** Adapters MUST NOT import from server.py or tools
- **Adapter-owned httpx clients** - each adapter creates and manages its own client
- **`{Source}Adapter` naming** - e.g., `GDELTAdapter`, `OpenSkyAdapter`

### File Locations

| File | Path | Purpose |
|------|------|---------|
| base.py | `src/ignifer/adapters/base.py` | Protocol + Error hierarchy |
| __init__.py | `src/ignifer/adapters/__init__.py` | Module exports |

### OSINTAdapter Protocol Implementation

**CRITICAL: Use `typing.Protocol` with `@runtime_checkable` for duck typing + isinstance support.**

```python
from typing import Protocol, runtime_checkable

from ignifer.models import OSINTResult, QueryParams, QualityTier


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
```

### Error Hierarchy Implementation

**All errors MUST include source_name and support exception chaining.**

```python
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
```

### Exception Chaining Pattern

**CRITICAL: Always chain original exceptions using `from`:**

```python
import httpx

# CORRECT - chain the original exception
try:
    response = await client.get(url)
except httpx.TimeoutException as e:
    raise AdapterTimeoutError("gdelt", timeout_seconds=10.0) from e

# WRONG - loses original exception context
try:
    response = await client.get(url)
except httpx.TimeoutException:
    raise AdapterTimeoutError("gdelt")  # NO - missing 'from e'
```

### Module Exports (adapters/__init__.py)

```python
"""OSINT data source adapters."""

from ignifer.adapters.base import (
    AdapterAuthError,
    AdapterError,
    AdapterParseError,
    AdapterTimeoutError,
    OSINTAdapter,
)

__all__ = [
    "OSINTAdapter",
    "AdapterError",
    "AdapterTimeoutError",
    "AdapterParseError",
    "AdapterAuthError",
]
```

### Test File Structure (tests/adapters/test_base.py)

```python
"""Tests for adapter protocol and error hierarchy."""

import pytest
from ignifer.adapters import (
    AdapterAuthError,
    AdapterError,
    AdapterParseError,
    AdapterTimeoutError,
    OSINTAdapter,
)
from ignifer.models import OSINTResult, QueryParams, QualityTier, ResultStatus


class MockAdapter:
    """A minimal adapter that conforms to OSINTAdapter protocol."""

    @property
    def source_name(self) -> str:
        return "mock"

    @property
    def base_quality_tier(self) -> QualityTier:
        return QualityTier.MEDIUM

    async def query(self, params: QueryParams) -> OSINTResult:
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            data={"mock": "data"},
            sources=[],
            confidence=None,
            quality_tier=self.base_quality_tier,
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

    def test_parse_error_includes_details(self) -> None:
        error = AdapterParseError("gdelt", details="Invalid JSON")
        assert "Invalid JSON" in str(error)

    def test_auth_error_includes_details(self) -> None:
        error = AdapterAuthError("acled", details="Invalid API key")
        assert "Invalid API key" in str(error)

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
```

### Anti-Patterns to AVOID

```python
# WRONG: Using ABC instead of Protocol
from abc import ABC, abstractmethod
class OSINTAdapter(ABC):  # NO - use typing.Protocol

# WRONG: Missing @runtime_checkable
class OSINTAdapter(Protocol):  # NO - add @runtime_checkable

# WRONG: Forgetting exception chaining
raise AdapterTimeoutError("gdelt")  # NO - use 'from e'

# WRONG: Importing from server.py
from ignifer.server import ...  # NO - layer violation

# WRONG: Adapter class naming
class GDELT:  # NO - use GDELTAdapter
class GdeltAdapter:  # NO - use GDELTAdapter (source name capitalized)

# WRONG: Shared httpx client
_client = httpx.AsyncClient()  # NO - each adapter owns its client
```

### Dependencies on Previous Stories

**Story 1.2 provides:**
- `QueryParams` model for query method signature
- `OSINTResult` model for query return type
- `QualityTier` enum for base_quality_tier property
- `ResultStatus` enum for expected operational states

**Import pattern:**
```python
from ignifer.models import OSINTResult, QueryParams, QualityTier, ResultStatus
```

### Project Structure After This Story

```
src/ignifer/
├── __init__.py      # __version__ = "0.1.0"
├── __main__.py      # Entry point
├── server.py        # Stub with main()
├── models.py        # Pydantic models (Story 1.2)
├── config.py        # Settings and logging (Story 1.2)
├── cache.py         # Cache layer (Story 1.3)
└── adapters/
    ├── __init__.py  # UPDATED - exports Protocol + errors
    └── base.py      # NEW - Protocol + error hierarchy

tests/
├── conftest.py
├── test_cache.py
├── adapters/
│   └── test_base.py  # NEW - Protocol + error tests
└── fixtures/
    └── cache_scenarios.py
```

### References

- [Source: architecture.md#Adapter-Architecture] - Protocol definition, error handling contract
- [Source: project-context.md#Error-Handling-Contract] - Exception vs Result type rules
- [Source: project-context.md#FastMCP-Adapter-Rules] - Layer boundaries, client ownership
- [Source: epics.md#Story-1.4] - Acceptance criteria

### Important Constraints

1. **DO NOT** add any adapter implementations in this story (that's Story 1.5+)
2. **DO NOT** import from server.py or tools - adapters are a lower layer
3. **DO NOT** use ABC - use typing.Protocol with @runtime_checkable
4. **ALWAYS** chain original exceptions using `from e`
5. **ALWAYS** include source_name in all error messages

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

- [ ] OSINTAdapter Protocol created with @runtime_checkable
- [ ] All four required members defined (source_name, base_quality_tier, query, health_check)
- [ ] AdapterError base class with source_name attribute
- [ ] AdapterTimeoutError, AdapterParseError, AdapterAuthError created
- [ ] adapters/__init__.py updated with exports
- [ ] tests/adapters/test_base.py created
- [ ] Protocol isinstance check verified
- [ ] Exception chaining tested
- [ ] `make type-check` passes
- [ ] `make lint` passes
- [ ] `make test` passes

### File List

_Files created/modified during implementation:_

- [ ] src/ignifer/adapters/base.py (NEW)
- [ ] src/ignifer/adapters/__init__.py (UPDATED)
- [ ] tests/adapters/test_base.py (NEW)
