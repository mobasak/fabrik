#!/bin/bash
# Runs all documentator test scenarios against kilo_docs_enforcer.py
# Usage: bash run_tests.sh [--live]  (--live runs actual Kilo generation)
set -e

FIXTURE_DIR="$(cd "$(dirname "$0")" && pwd)"
ENFORCER="/opt/fabrik/scripts/kilo_docs_enforcer.py"
TARGET="/tmp/test-docs-enforcer"
SCENARIO_SRC="$FIXTURE_DIR/scenarios"
LIVE_MODE=false

if [ "$1" = "--live" ]; then
    LIVE_MODE=true
fi

# Setup test project
bash "$FIXTURE_DIR/setup_test_project.sh"
cd "$TARGET"

PASS=0
FAIL=0

run_scenario() {
    local num="$1"
    local file="$2"
    local expected_triggers="$3"
    local dest="$4"

    echo ""
    echo "=== Scenario $num: $file ==="

    # Copy scenario file directly from the fixture source (not from inside the temp repo)
    if [ -d "$SCENARIO_SRC/$file" ]; then
        cp -r "$SCENARIO_SRC/$file" "$TARGET/$dest"
    else
        mkdir -p "$(dirname "$TARGET/$dest")"
        cp "$SCENARIO_SRC/$file" "$TARGET/$dest"
    fi
    git add "$dest"

    # Run detection
    output=$(python "$ENFORCER" --detect --output json 2>/dev/null || true)
    triggers=$(echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); print(','.join(sorted(set(v['trigger'] for v in data['violations']))))" 2>/dev/null || echo "PARSE_ERROR")

    if echo "$triggers" | grep -q "$expected_triggers"; then
        echo "  ✅ DETECT: Found expected trigger(s): $triggers"
        PASS=$((PASS + 1))
    else
        echo "  ❌ DETECT: Expected '$expected_triggers' but got '$triggers'"
        FAIL=$((FAIL + 1))
    fi

    # Run enforce (should fail — docs not staged)
    if python "$ENFORCER" --enforce >/dev/null 2>&1; then
        echo "  ❌ ENFORCE: Should have failed (docs not staged)"
        FAIL=$((FAIL + 1))
    else
        echo "  ✅ ENFORCE: Correctly blocked (exit 1)"
        PASS=$((PASS + 1))
    fi

    # Run auto-generate (dry-run or live)
    if [ "$LIVE_MODE" = true ]; then
        echo "  🔄 AUTO-GENERATE: Running live..."
        python "$ENFORCER" --auto-generate --verbose 2>&1 | head -20
    else
        python "$ENFORCER" --auto-generate --dry-run 2>/dev/null || true
        echo "  ℹ️  AUTO-GENERATE: Dry-run only (use --live for real)"
    fi

    # Reset: restore repo to clean initial-commit state before next scenario
    # Order matters: unstage first, then restore working tree, then clean untracked
    git reset HEAD -- . 2>/dev/null || true
    git checkout -- . 2>/dev/null || true
    git clean -fd 2>/dev/null || true
}

run_scenario "01" "01_new_public_function.py" "new_public_function" "src/myapp/api.py"
run_scenario "02" "02_new_class.py" "new_class" "src/myapp/service.py"
run_scenario "03" "03_new_endpoint.py" "new_endpoint" "src/myapp/routes.py"
run_scenario "04" "04_new_env_var.py" "new_env_var" "src/myapp/config.py"
run_scenario "05" "05_breaking_change.py" "breaking_change" "src/myapp/payment.py"
run_scenario "06" "06_schema_change.py" "schema_change" "src/myapp/models.py"
run_scenario "07" "07_large_change.py" "large_code_change" "src/myapp/utils.py"
run_scenario "08" "08_combined.py" "new_class" "src/myapp/cache.py"
run_scenario "09" "09_docker_change/Dockerfile" "docker_change" "Dockerfile"
run_scenario "10" "10_cli_command.py" "new_cli_command" "src/myapp/cli.py"

echo ""
echo "==============================="
echo "RESULTS: $PASS passed, $FAIL failed"
echo "==============================="

if [ $FAIL -gt 0 ]; then
    exit 1
fi
