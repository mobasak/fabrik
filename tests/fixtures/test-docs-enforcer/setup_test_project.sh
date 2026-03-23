#!/bin/bash
# Creates a temporary git repo at /tmp/test-docs-enforcer for testing kilo_docs_enforcer.py
set -e

TARGET="/tmp/test-docs-enforcer"
FIXTURE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Setting up test project at $TARGET ==="

# Clean previous
rm -rf "$TARGET"
mkdir -p "$TARGET/src/myapp" "$TARGET/docs/reference" "$TARGET/docs/database"

# Create base files
cat > "$TARGET/src/myapp/__init__.py" << 'EOF'
"""MyApp package."""
EOF

cat > "$TARGET/CHANGELOG.md" << 'EOF'
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

EOF

cat > "$TARGET/.env.example" << 'EOF'
# MyApp Configuration
DB_HOST=localhost
DB_PORT=5432
EOF

cat > "$TARGET/README.md" << 'EOF'
# MyApp

## Features
| Feature | Status | Description |
|---------|--------|-------------|
EOF

touch "$TARGET/docs/CONFIGURATION.md"
touch "$TARGET/docs/QUICKSTART.md"
touch "$TARGET/docs/TROUBLESHOOTING.md"
touch "$TARGET/docs/MIGRATION.md"

# Initialize git repo with local identity (works on machines without global git config)
cd "$TARGET"
git init
git -c user.name="Test Runner" -c user.email="test@test.local" commit --allow-empty -m "root"
git add -A
git -c user.name="Test Runner" -c user.email="test@test.local" commit -m "initial commit"

# Configure repo-local identity for subsequent commits by run_tests.sh
git config user.name "Test Runner"
git config user.email "test@test.local"

# Scenarios are read directly from $FIXTURE_DIR/scenarios by run_tests.sh
# Do NOT copy them into the temp repo — git clean would destroy them

echo "=== Test project ready at $TARGET ==="
echo "Run: bash $FIXTURE_DIR/run_tests.sh"
