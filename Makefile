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
