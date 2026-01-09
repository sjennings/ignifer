# Story 1.2: Core Models & Configuration

Status: ready-for-dev

## Story

As a **developer**,
I want **well-defined Pydantic models and centralized configuration**,
so that **all components share consistent data structures and settings**.

## Acceptance Criteria

1. **AC1: Core Models Created**
   - **Given** the project structure from Story 1.1
   - **When** I create `src/ignifer/models.py`
   - **Then** it defines the following models with proper type hints:
     - `QueryParams`: topic (str), time_range (optional str), sources (optional list[str])
     - `SourceMetadata`: source_name (str), source_url (str), retrieved_at (datetime with timezone)
     - `ConfidenceLevel`: Enum with REMOTE, UNLIKELY, EVEN_CHANCE, LIKELY, VERY_LIKELY, ALMOST_CERTAIN and methods `to_percentage_range()`, `to_label()`
     - `QualityTier`: Enum with HIGH, MEDIUM, LOW
     - `ResultStatus`: Enum with SUCCESS, NO_DATA, RATE_LIMITED, ERROR
     - `OSINTResult`: status (ResultStatus), data (dict), sources (list[SourceMetadata]), confidence (ConfidenceLevel | None), quality_tier (QualityTier | None)
     - `SourceAttribution`: source (str), url (str), retrieved_at (datetime)
   - **And** all datetime fields serialize to ISO 8601 with timezone
   - **And** all field names use snake_case

2. **AC2: Configuration Module Created**
   - **Given** models.py exists
   - **When** I create `src/ignifer/config.py`
   - **Then** it provides:
     - `Settings` class reading from environment variables (IGNIFER_* prefix)
     - TTL defaults per source (GDELT=3600, OPENSKY=300, etc.)
     - Logging configuration using stdlib logging
     - `get_settings()` function returning singleton Settings instance
   - **And** API keys are never logged even at DEBUG level

3. **AC3: Type Checking Passes**
   - **Given** both modules exist
   - **When** I run `make type-check`
   - **Then** mypy passes with strict mode
   - **And** all public classes are importable from `ignifer.models` and `ignifer.config`

## Tasks / Subtasks

- [ ] Task 1: Create models.py with Pydantic models (AC: #1, #3)
  - [ ] 1.1: Create ResultStatus, QualityTier enums
  - [ ] 1.2: Create ConfidenceLevel enum with to_percentage_range() and to_label() methods
  - [ ] 1.3: Create QueryParams model
  - [ ] 1.4: Create SourceMetadata model with datetime serialization
  - [ ] 1.5: Create SourceAttribution model
  - [ ] 1.6: Create OSINTResult model
  - [ ] 1.7: Add module-level __all__ exports

- [ ] Task 2: Create config.py with Settings (AC: #2, #3)
  - [ ] 2.1: Create Settings class extending pydantic_settings.BaseSettings
  - [ ] 2.2: Add IGNIFER_* environment variable prefix
  - [ ] 2.3: Define TTL defaults as class attributes
  - [ ] 2.4: Configure logging with stdlib logging module
  - [ ] 2.5: Create get_settings() singleton function
  - [ ] 2.6: Ensure API keys are never logged

- [ ] Task 3: Verify implementation (AC: #3)
  - [ ] 3.1: Run `make type-check` and fix any mypy errors
  - [ ] 3.2: Run `make lint` and fix any ruff errors
  - [ ] 3.3: Verify imports work from package root

## Dev Notes

### CRITICAL: Architecture Compliance

**FROM project-context.md - ABSOLUTE MUST-KNOWS:**

1. **snake_case** for all JSON fields - no exceptions
2. **`datetime.now(timezone.utc)`** - never naive datetime
3. **stdlib `logging` only** - no loguru, no structlog
4. **ISO 8601 + timezone** for all datetime serialization
5. **Layer rule:** Models MUST NOT import from any other layer (they are the leaf layer)

### File Locations (DO NOT CHANGE)

| File | Path | Purpose |
|------|------|---------|
| models.py | `src/ignifer/models.py` | ALL Pydantic models (split later when >300 lines) |
| config.py | `src/ignifer/config.py` | Environment config, TTL defaults, logging |

### Dependencies Required

Add to pyproject.toml `[project.dependencies]`:
```toml
"pydantic-settings>=2.0",
```

**NOTE:** This is NOT currently in pyproject.toml from Story 1.1. You MUST add it.

### ConfidenceLevel Enum Implementation

Per architecture.md, use ICD 203 confidence levels:

```python
from enum import Enum

class ConfidenceLevel(Enum):
    REMOTE = 1          # <20%
    UNLIKELY = 2        # 20-40%
    EVEN_CHANCE = 3     # 40-60%
    LIKELY = 4          # 60-80%
    VERY_LIKELY = 5     # 80-95%
    ALMOST_CERTAIN = 6  # >95%

    def to_percentage_range(self) -> tuple[int, int]:
        ranges = {
            ConfidenceLevel.REMOTE: (0, 20),
            ConfidenceLevel.UNLIKELY: (20, 40),
            ConfidenceLevel.EVEN_CHANCE: (40, 60),
            ConfidenceLevel.LIKELY: (60, 80),
            ConfidenceLevel.VERY_LIKELY: (80, 95),
            ConfidenceLevel.ALMOST_CERTAIN: (95, 100),
        }
        return ranges[self]

    def to_label(self) -> str:
        labels = {
            ConfidenceLevel.REMOTE: "Remote possibility",
            ConfidenceLevel.UNLIKELY: "Unlikely",
            ConfidenceLevel.EVEN_CHANCE: "Even chance",
            ConfidenceLevel.LIKELY: "Likely",
            ConfidenceLevel.VERY_LIKELY: "Very likely",
            ConfidenceLevel.ALMOST_CERTAIN: "Almost certain",
        }
        return labels[self]
```

### QualityTier and ResultStatus Enums

```python
from enum import Enum

class QualityTier(Enum):
    HIGH = "H"    # Official sources, academic research
    MEDIUM = "M"  # Reputable news, verified OSINT
    LOW = "L"     # Social media, unverified reports

class ResultStatus(Enum):
    SUCCESS = "success"
    NO_DATA = "no_data"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
```

### Pydantic Model Patterns

**CRITICAL: Use ConfigDict for model configuration (Pydantic v2 pattern):**

```python
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, field_serializer

class SourceMetadata(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    source_name: str
    source_url: str
    retrieved_at: datetime

    @field_serializer('retrieved_at')
    def serialize_dt(self, dt: datetime) -> str:
        return dt.isoformat()
```

**NEVER use naive datetime:**
```python
# CORRECT
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc)

# WRONG - naive datetime
timestamp = datetime.now()
timestamp = datetime.utcnow()  # deprecated
```

### Settings Configuration Pattern

**Use pydantic-settings for environment variable loading:**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix='IGNIFER_',
        env_file='.env',
        env_file_encoding='utf-8',
    )

    # API Keys (Phase 2+) - NEVER log these
    opensky_username: str | None = None
    opensky_password: str | None = None
    aisstream_key: str | None = None
    acled_key: str | None = None

    # Cache TTL defaults (seconds)
    ttl_gdelt: int = 3600       # 1 hour
    ttl_opensky: int = 300      # 5 minutes
    ttl_aisstream: int = 900    # 15 minutes
    ttl_worldbank: int = 86400  # 24 hours
    ttl_acled: int = 43200      # 12 hours
    ttl_opensanctions: int = 86400  # 24 hours
    ttl_wikidata: int = 604800  # 7 days

    # Logging
    log_level: str = "INFO"

    # Rigor mode (Phase 4)
    rigor_mode: bool = False
```

### Singleton Pattern for Settings

```python
_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

### Logging Configuration

**CRITICAL: Use stdlib logging ONLY:**

```python
import logging

def configure_logging(level: str = "INFO") -> None:
    """Configure stdlib logging for Ignifer."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Suppress httpx debug logs (too verbose)
    logging.getLogger("httpx").setLevel(logging.WARNING)
```

### Anti-Patterns to AVOID

```python
# WRONG: camelCase JSON fields
class OSINTResult(BaseModel):
    sourceName: str        # NO - use source_name
    confidenceLevel: str   # NO - use confidence_level

# WRONG: loguru or structlog
from loguru import logger  # NO - use stdlib logging

# WRONG: Naive datetime
retrieved_at = datetime.now()  # NO - use datetime.now(timezone.utc)

# WRONG: Logging API keys
logger.debug(f"Using API key: {settings.acled_key}")  # NEVER DO THIS
```

### Module Exports

**models.py should export:**
```python
__all__ = [
    "QueryParams",
    "SourceMetadata",
    "SourceAttribution",
    "ConfidenceLevel",
    "QualityTier",
    "ResultStatus",
    "OSINTResult",
]
```

**config.py should export:**
```python
__all__ = [
    "Settings",
    "get_settings",
    "configure_logging",
]
```

### Previous Story Intelligence

From Story 1.1 implementation:
- Project uses `uv` for package management
- Entry point is `ignifer.server:main`
- Strict mypy mode enabled in pyproject.toml
- ruff configured for linting/formatting
- asyncio_mode = "auto" for pytest

**Makefile targets available:**
- `make install` - Install with dev dependencies
- `make lint` - Run ruff checks
- `make type-check` - Run mypy strict
- `make test` - Run pytest with coverage

### Testing Requirements

After implementation, verify:
1. `make type-check` passes with no errors
2. `make lint` passes with no errors
3. Python imports work:
   ```python
   from ignifer.models import QueryParams, OSINTResult, ConfidenceLevel
   from ignifer.config import Settings, get_settings
   ```

### Project Structure After This Story

```
src/ignifer/
├── __init__.py      # __version__ = "0.1.0"
├── __main__.py      # Entry point
├── server.py        # Stub with main()
├── models.py        # NEW - All Pydantic models
├── config.py        # NEW - Settings and logging
└── adapters/
    └── __init__.py
```

### References

- [Source: architecture.md#Core-Architectural-Decisions] - ConfidenceLevel, QualityTier definitions
- [Source: architecture.md#Cache-Architecture] - TTL defaults by source
- [Source: architecture.md#Implementation-Patterns] - Datetime serialization, snake_case
- [Source: project-context.md#Critical-Implementation-Rules] - Python patterns
- [Source: project-context.md#Pydantic-Rules] - ConfigDict usage
- [Source: epics.md#Story-1.2] - Acceptance criteria

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

- [ ] pydantic-settings added to pyproject.toml dependencies
- [ ] All models created with proper type hints
- [ ] All enums have required methods
- [ ] Settings class reads IGNIFER_* environment variables
- [ ] Logging configured with stdlib only
- [ ] `make type-check` passes
- [ ] `make lint` passes
- [ ] Package imports verified

### File List

_Files created/modified during implementation:_

- [ ] pyproject.toml (add pydantic-settings dependency)
- [ ] src/ignifer/models.py (NEW)
- [ ] src/ignifer/config.py (NEW)
