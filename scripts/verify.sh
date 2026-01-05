#!/bin/bash
# Fabrik Verification Script - 3-Lane Static Verification
# Lane A: Static guarantees (types, lint, security)
# Run before commits and in CI
#
# Last Updated: 2026-01-04
set -e

cd "$(dirname "$0")/.." || exit 1

echo "🔍 Running Fabrik 3-Lane Static Verification..."
echo ""

echo "━━━ Lane A: Static Guarantees ━━━"
echo ""

echo "1. Ruff (Linting)..."
ruff check src/ scripts/ tests/ --ignore E501 || { echo "❌ Linting failed"; exit 1; }
echo "   ✅ Linting passed"

echo ""
echo "2. Mypy (Type Checking)..."
mypy src/fabrik/ --ignore-missing-imports || { echo "❌ Type checking failed"; exit 1; }
echo "   ✅ Type checking passed"

echo ""
echo "3. Secret Scanner..."
if [ -f "$HOME/.factory/hooks/secret-scanner.py" ]; then
    python3 "$HOME/.factory/hooks/secret-scanner.py" --scan . || { echo "❌ Secrets found"; exit 1; }
    echo "   ✅ No secrets found"
else
    echo "   ⚠️  Secret scanner not found, skipping"
fi

echo ""
echo "━━━ Lane B: Dynamic Guarantees ━━━"
echo ""

echo "4. Pytest (Unit Tests)..."
pytest tests/ -q --tb=short || { echo "❌ Tests failed"; exit 1; }
echo "   ✅ Tests passed"

echo ""
echo "5. Contract Tests..."
if [ -d "tests/contracts" ] && [ "$(ls -A tests/contracts/*.py 2>/dev/null)" ]; then
    pytest tests/contracts/ -q --tb=short || { echo "❌ Contract tests failed"; exit 1; }
    echo "   ✅ Contract tests passed"
else
    echo "   ⚠️  No contract tests found, skipping"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All verification checks passed!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
