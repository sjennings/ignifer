# Story 1.1: Project Initialization & Build Configuration

Status: ready-for-dev

## Story

As a **developer**,
I want **a properly structured Python MCP server project with modern build tooling**,
so that **I can install, develop, and distribute Ignifer following Python best practices**.

## Acceptance Criteria

1. **AC1: Project Structure Created**
   - **Given** a clean development environment with Python 3.10+ and uv installed
   - **When** I run `uv init` and set up the project structure
   - **Then** the following structure exists:
     - `src/ignifer/` package directory with `__init__.py` and `__main__.py`
     - `src/ignifer/adapters/` directory with `__init__.py`
     - `tests/` directory with `conftest.py`
     - `tests/adapters/` directory
     - `tests/fixtures/` directory

2. **AC2: pyproject.toml Complete**
   - **And** `pyproject.toml` includes:
     - Project metadata (name="ignifer", requires-python=">=3.10")
     - Dependencies: fastmcp>=2.14, httpx>=0.28, pydantic>=2.12, tenacity>=9.1
     - Dev dependencies: pytest, pytest-asyncio, pytest-cov, pytest-httpx, mypy, ruff
     - Build system using hatchling
     - Entry point: `ignifer = "ignifer.server:main"`

3. **AC3: Editable Install Works**
   - **Given** the project is initialized
   - **When** I run `uv pip install -e ".[dev]"`
   - **Then** the package installs successfully in editable mode
   - **And** running `python -m ignifer` executes without import errors (may exit with "not implemented" message)

4. **AC4: Development Tools Pass**
   - **Given** the Makefile exists
   - **When** I run `make lint`
   - **Then** ruff checks pass on the project skeleton
   - **And** `make type-check` runs mypy without configuration errors

## Tasks / Subtasks

- [ ] Task 1: Initialize project with uv (AC: #1, #2)
  - [ ] 1.1: Run `uv init --lib --name ignifer` in project root
  - [ ] 1.2: Configure pyproject.toml with exact dependencies
  - [ ] 1.3: Set up .python-version file with "3.10"

- [ ] Task 2: Create directory structure (AC: #1)
  - [ ] 2.1: Create `src/ignifer/` package with `__init__.py`
  - [ ] 2.2: Create `src/ignifer/__main__.py` entry point
  - [ ] 2.3: Create `src/ignifer/server.py` stub with `main()` function
  - [ ] 2.4: Create `src/ignifer/adapters/` directory with `__init__.py`
  - [ ] 2.5: Create `tests/` directory with `conftest.py`
  - [ ] 2.6: Create `tests/adapters/` directory
  - [ ] 2.7: Create `tests/fixtures/` directory

- [ ] Task 3: Configure build tooling (AC: #2, #4)
  - [ ] 3.1: Create Makefile with install, test, lint, type-check, all targets
  - [ ] 3.2: Configure pyproject.toml [tool.ruff] section
  - [ ] 3.3: Configure pyproject.toml [tool.mypy] section with strict mode
  - [ ] 3.4: Configure pyproject.toml [tool.pytest.ini_options] with asyncio_mode

- [ ] Task 4: Create essential files (AC: #3)
  - [ ] 4.1: Create .gitignore with Python patterns
  - [ ] 4.2: Create README.md with basic project info
  - [ ] 4.3: Create LICENSE file (MIT recommended)

- [ ] Task 5: Verify installation (AC: #3, #4)
  - [ ] 5.1: Run `uv pip install -e ".[dev]"` and verify success
  - [ ] 5.2: Run `python -m ignifer` and verify it executes
  - [ ] 5.3: Run `make lint` and verify ruff passes
  - [ ] 5.4: Run `make type-check` and verify mypy passes
  - [ ] 5.5: Run `make test` and verify pytest runs (even with 0 tests)

## Dev Notes

### Architecture Compliance

This story implements the MVP project structure defined in architecture.md. Key decisions:

- **Build backend:** hatchling (pyOpenSci recommended, modern)
- **Package manager:** uv (Rust-based, 10-100x faster than pip)
- **Source layout:** `src/ignifer/` (isolation, prevents import confusion)
- **Python version:** 3.10+ (required for modern async patterns)

### Critical File Contents

**src/ignifer/__init__.py:**
```python
"""Ignifer - OSINT MCP Server aggregating 7 data sources."""

__version__ = "0.1.0"
```

**src/ignifer/__main__.py:**
```python
"""Entry point for python -m ignifer."""

from ignifer.server import main

if __name__ == "__main__":
    main()
```

**src/ignifer/server.py (stub):**
```python
"""FastMCP server for Ignifer OSINT tools."""

from fastmcp import FastMCP

mcp = FastMCP("ignifer")


def main() -> None:
    """Run the Ignifer MCP server."""
    # Will be implemented in Story 1.6
    raise NotImplementedError("Server implementation pending Story 1.6")


if __name__ == "__main__":
    main()
```

**src/ignifer/adapters/__init__.py:**
```python
"""OSINT data source adapters."""

__all__: list[str] = []
```

### pyproject.toml Configuration

```toml
[project]
name = "ignifer"
version = "0.1.0"
description = "OSINT MCP Server aggregating 7 data sources for Claude Desktop"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Scott"}
]
dependencies = [
    "fastmcp>=2.14,<3",
    "httpx>=0.28",
    "pydantic>=2.12",
    "tenacity>=9.1",
    "websockets>=12.0",
]

[project.scripts]
ignifer = "ignifer.server:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
    "pytest-httpx>=0.30",
    "mypy>=1.8",
    "ruff>=0.3",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ignifer"]

[tool.ruff]
target-version = "py310"
line-length = 100
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
disallow_incomplete_defs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Makefile

```makefile
.PHONY: install test lint type-check all clean

install:
	uv pip install -e ".[dev]"

test:
	pytest --cov=ignifer --cov-report=term-missing

lint:
	ruff check . && ruff format --check .

format:
	ruff format .

type-check:
	mypy src/

all: lint type-check test

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache *.egg-info dist build
	find . -type d -name __pycache__ -exec rm -rf {} +
```

### tests/conftest.py

```python
"""Shared pytest fixtures for Ignifer tests."""

import pytest


@pytest.fixture
def sample_topic() -> str:
    """Sample topic for testing."""
    return "Ukraine"
```

### Project Structure Notes

Final structure after this story:

```
ignifer/
├── .gitignore
├── .python-version          # Contains: 3.10
├── LICENSE
├── Makefile
├── README.md
├── pyproject.toml
├── src/
│   └── ignifer/
│       ├── __init__.py      # __version__ = "0.1.0"
│       ├── __main__.py      # Entry point
│       ├── server.py        # Stub with main()
│       └── adapters/
│           └── __init__.py
└── tests/
    ├── conftest.py
    ├── adapters/
    └── fixtures/
```

### References

- [Source: architecture.md#Starter-Template-Evaluation] - FastMCP 2.x + Modern Python Stack
- [Source: architecture.md#MVP-Project-Structure] - Directory structure
- [Source: architecture.md#Core-Dependencies] - Pinned versions
- [Source: architecture.md#Development-Automation] - Makefile targets
- [Source: project-context.md#Technology-Stack] - Version requirements

### Important Constraints

1. **DO NOT** create additional files beyond what's specified
2. **DO NOT** add functionality to server.py beyond the stub
3. **DO NOT** install actual adapters yet (just the directory structure)
4. **VERIFY** all four acceptance criteria pass before marking complete

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

- [ ] All acceptance criteria verified
- [ ] `make all` passes without errors
- [ ] Package installs in editable mode
- [ ] Entry point executes (even if NotImplementedError)

### File List

_Files created/modified during implementation:_

- [ ] pyproject.toml
- [ ] .python-version
- [ ] .gitignore
- [ ] LICENSE
- [ ] README.md
- [ ] Makefile
- [ ] src/ignifer/__init__.py
- [ ] src/ignifer/__main__.py
- [ ] src/ignifer/server.py
- [ ] src/ignifer/adapters/__init__.py
- [ ] tests/conftest.py
