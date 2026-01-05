#!/bin/bash
# Fabrik Python Formatter Hook - PostToolUse
#
# Auto-formats Python files using ruff (fast) after edits.
# Falls back to black if ruff not available.

# Don't use set -e - we want to continue even if formatting fails
# set -e

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Only process Python files
if ! echo "$file_path" | grep -qE '\.py$'; then
  exit 0
fi

# Skip if file doesn't exist
if [ ! -f "$file_path" ]; then
  exit 0
fi

# Skip test fixtures and generated files
if echo "$file_path" | grep -qE '(fixtures|generated|__pycache__|\.pyc)'; then
  exit 0
fi

# Format with ruff (preferred - fast)
if command -v ruff &> /dev/null; then
  ruff format "$file_path" 2>&1 || true
  ruff check --fix "$file_path" 2>&1 || true
  echo "✓ Formatted with ruff: $file_path"
  exit 0
fi

# Fallback to black
if command -v black &> /dev/null; then
  black --quiet "$file_path" 2>&1 || true
  echo "✓ Formatted with black: $file_path"
  exit 0
fi

# No formatter available - just continue
exit 0
