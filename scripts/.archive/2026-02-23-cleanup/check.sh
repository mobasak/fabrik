#!/bin/bash
# Fabrik quality gate script
# Usage: ./scripts/check.sh
# Exit codes: 0 = pass, non-zero = fail

set -e

echo "=== Fabrik Quality Check ==="
echo ""

echo "1/4 Checking format..."
ruff format --check src/ scripts/

echo "2/4 Running linter..."
ruff check src/ scripts/

echo "3/4 Running tests..."
pytest tests/ -q

echo "4/4 Checking documentation..."
python scripts/docs_updater.py --check

echo ""
echo "=== All checks passed ==="
