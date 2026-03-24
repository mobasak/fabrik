# Makefile for Fabrik CLI
# Usage: make help
#
# Fabrik is a CLI tool, not a deployed service.
# No docker-smoke target (N/A for CLI tools).

.PHONY: help install dev test lint format clean pre-commit global-gates mypy-safe

# Default target
help:
	@echo "Fabrik Development Commands"
	@echo ""
	@echo "  make install     Install dependencies (uv sync)"
	@echo "  make dev         Install in editable mode for development"
	@echo "  make test        Run pytest"
	@echo "  make lint        Run ruff + mypy"
	@echo "  make mypy-safe   Run mypy with timeout protection (auto-recovers from cache corruption)"
	@echo "  make format      Auto-format code with ruff"
	@echo "  make pre-commit  Run all pre-commit hooks"
	@echo "  make clean       Remove cache files"
	@echo ""

# ============================================================
# Development Setup
# ============================================================

install:
	uv sync

dev: install
	uv pip install -e .
	@echo "Fabrik installed in editable mode. Run 'fabrik --help' to verify."

# ============================================================
# Quality Checks
# ============================================================

test:
	pytest -v

lint:
	ruff check src/
	mypy src/

mypy-safe:
	@# Robust mypy with timeout protection and auto-recovery
	@timeout 30 mypy src/ scripts/ --ignore-missing-imports 2>/dev/null || { \
		echo "⚠ mypy hung - clearing cache and retrying..."; \
		rm -rf .mypy_cache/; \
		mypy src/ scripts/ --ignore-missing-imports --no-incremental; \
	}

format:
	ruff format src/
	ruff check --fix src/

pre-commit:
	pre-commit run --all-files

check:
	python scripts/final_gate.py

docs-check:
	python scripts/docs_updater.py --check

global-gates:
	python3 -m scripts.enforcement.check_global_gates

# ============================================================
# Cleanup
# ============================================================

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/
