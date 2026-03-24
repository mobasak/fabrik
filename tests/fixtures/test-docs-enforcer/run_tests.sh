#!/bin/bash
# Runs all documentator test scenarios against kilo_docs_enforcer.py
# Usage: bash run_tests.sh [--live]  (--live runs actual Kilo generation)
set -eo pipefail

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

# Safety guard: abort if we're somehow running in /opt/fabrik
if [ "$(pwd)" = "/opt/fabrik" ]; then
    echo "FATAL: Working directory is /opt/fabrik — refusing to run tests here."
    echo "Tests must run in $TARGET to avoid modifying the real repository."
    exit 2
fi

PASS=0
FAIL=0
TOTAL_START=$(date +%s)

# Summary arrays (associative to avoid octal interpretation of 08/09)
declare -A SCENARIO_NAMES
declare -A DETECT_RESULTS
declare -A ENFORCE_RESULTS
declare -A AUTOGEN_RESULTS
declare -A SCENARIO_TIMES

run_scenario() {
    local num="$1"
    local file="$2"
    local expected_triggers="$3"
    local dest="$4"
    local expected_doc_paths="$5"   # comma-separated expected doc_path values
    local scenario_start=$(date +%s)

    echo ""
    echo "=== Scenario $num: $file ==="

    SCENARIO_NAMES[$num]="$file"

    # Copy scenario file directly from the fixture source (not from inside the temp repo)
    if [ -d "$SCENARIO_SRC/$file" ]; then
        cp -r "$SCENARIO_SRC/$file" "$TARGET/$dest"
    else
        mkdir -p "$(dirname "$TARGET/$dest")"
        cp "$SCENARIO_SRC/$file" "$TARGET/$dest"
    fi
    git add "$dest"

    # Run detection — capture output to temp file for assertion checks
    local detect_result="PASS"
    local detect_tmpfile
    detect_tmpfile=$(mktemp)
    local detect_exit=0
    python "$ENFORCER" --detect --output json --project-root "$TARGET" >"$detect_tmpfile" 2>/dev/null || detect_exit=$?

    if [ "$detect_exit" -ne 0 ]; then
        echo "  ❌ DETECT: Enforcer exited with code $detect_exit"
        FAIL=$((FAIL + 1))
        detect_result="FAIL"
    else
        triggers=$(python3 -c "import sys,json; data=json.load(sys.stdin); print(','.join(sorted(set(v['trigger'] for v in data['violations']))))" <"$detect_tmpfile" 2>/dev/null || echo "PARSE_ERROR")

        if echo "$triggers" | grep -q "$expected_triggers"; then
            echo "  ✅ DETECT: Found expected trigger(s): $triggers"
            PASS=$((PASS + 1))
        else
            echo "  ❌ DETECT: Expected '$expected_triggers' but got '$triggers'"
            FAIL=$((FAIL + 1))
            detect_result="FAIL"
        fi

        # Verify expected doc_path values in the detection report
        if [ -n "$expected_doc_paths" ]; then
            local doc_paths_result="PASS"
            actual_doc_paths=$(python3 -c "import sys,json; data=json.load(sys.stdin); print(','.join(sorted(r['doc_path'] for r in data['requirements'])))" <"$detect_tmpfile" 2>/dev/null || echo "PARSE_ERROR")
            # Check each expected doc_path is present
            IFS=',' read -ra EXPECTED_PATHS <<< "$expected_doc_paths"
            for expected_path in "${EXPECTED_PATHS[@]}"; do
                if ! echo "$actual_doc_paths" | grep -q "$expected_path"; then
                    echo "  ❌ DOC_PATH: Expected '$expected_path' in requirements but got: $actual_doc_paths"
                    FAIL=$((FAIL + 1))
                    doc_paths_result="FAIL"
                fi
            done
            if [ "$doc_paths_result" = "PASS" ]; then
                echo "  ✅ DOC_PATHS: Found expected doc paths"
                PASS=$((PASS + 1))
            fi
        fi
    fi
    rm -f "$detect_tmpfile"
    DETECT_RESULTS[$num]="$detect_result"

    # Run enforce (should fail — docs not staged)
    local enforce_result="PASS"
    if python "$ENFORCER" --enforce --project-root "$TARGET" >/dev/null 2>&1; then
        echo "  ❌ ENFORCE: Should have failed (docs not staged)"
        FAIL=$((FAIL + 1))
        enforce_result="FAIL"
    else
        echo "  ✅ ENFORCE: Correctly blocked (exit 1)"
        PASS=$((PASS + 1))
    fi
    ENFORCE_RESULTS[$num]="$enforce_result"

    # Run auto-generate (dry-run or live) — capture exit status explicitly
    local autogen_result="PASS"
    local autogen_exit=0
    if [ "$LIVE_MODE" = true ]; then
        echo "  🔄 AUTO-GENERATE: Running live..."
        local autogen_tmpfile
        autogen_tmpfile=$(mktemp)
        python "$ENFORCER" --auto-generate --verbose --project-root "$TARGET" >"$autogen_tmpfile" 2>&1 || autogen_exit=$?
        # Show truncated preview
        head -20 "$autogen_tmpfile"
        rm -f "$autogen_tmpfile"
        if [ "$autogen_exit" -ne 0 ]; then
            echo "  ❌ AUTO-GENERATE: Failed with exit code $autogen_exit"
            FAIL=$((FAIL + 1))
            autogen_result="FAIL"
        else
            echo "  ✅ AUTO-GENERATE: Succeeded"
            PASS=$((PASS + 1))
        fi
    else
        python "$ENFORCER" --auto-generate --dry-run --project-root "$TARGET" 2>/dev/null || autogen_exit=$?
        if [ "$autogen_exit" -ne 0 ]; then
            echo "  ❌ AUTO-GENERATE (dry-run): Failed with exit code $autogen_exit"
            FAIL=$((FAIL + 1))
            autogen_result="FAIL"
        else
            echo "  ✅ AUTO-GENERATE (dry-run): Passed"
            PASS=$((PASS + 1))
            echo "  ℹ️  AUTO-GENERATE: Dry-run only (use --live for real)"
        fi
    fi
    AUTOGEN_RESULTS[$num]="$autogen_result"

    # Reset: restore repo to clean initial-commit state before next scenario
    # Order matters: unstage first, then restore working tree, then clean untracked
    git reset HEAD -- . 2>/dev/null || true
    git checkout -- . 2>/dev/null || true
    git clean -fd 2>/dev/null || true

    # Verify working tree is actually clean
    local dirty=$(git status --porcelain 2>/dev/null)
    if [ -n "$dirty" ]; then
        echo "  ⚠️ WARNING: Working tree not clean after reset:"
        echo "$dirty" | head -5
        echo "  Attempting harder clean..."
        git checkout -- . 2>/dev/null || true
        git clean -fdx 2>/dev/null || true
    fi

    local scenario_end=$(date +%s)
    SCENARIO_TIMES[$num]=$((scenario_end - scenario_start))
    echo "  ⏱️  Time: ${SCENARIO_TIMES[$num]}s"
}

run_scenario "01" "01_new_public_function.py" "new_public_function" "src/myapp/api.py" "CHANGELOG.md,docs/reference/myapp.md"
run_scenario "02" "02_new_class.py" "new_class" "src/myapp/service.py" "CHANGELOG.md,docs/reference/myapp.md"
run_scenario "03" "03_new_endpoint.py" "new_endpoint" "src/myapp/routes.py" "CHANGELOG.md,README.md,docs/reference/myapp.md"
run_scenario "04" "04_new_env_var.py" "new_env_var" "src/myapp/config.py" ".env.example,docs/CONFIGURATION.md"
run_scenario "05" "05_breaking_change.py" "breaking_change" "src/myapp/payment.py" "CHANGELOG.md,docs/MIGRATION.md,docs/reference/myapp.md"
run_scenario "06" "06_schema_change.py" "schema_change" "src/myapp/models.py" "CHANGELOG.md,docs/database/schema.md,docs/reference/myapp.md"
run_scenario "07" "07_large_change.py" "large_code_change" "src/myapp/utils.py" "CHANGELOG.md,docs/reference/myapp.md,docs/TROUBLESHOOTING.md"
run_scenario "08" "08_combined.py" "new_class" "src/myapp/cache.py" "CHANGELOG.md,docs/reference/myapp.md,README.md,.env.example,docs/CONFIGURATION.md"
run_scenario "09" "09_docker_change/Dockerfile" "docker_change" "Dockerfile" "README.md"
run_scenario "10" "10_cli_command.py" "new_cli_command" "src/myapp/cli.py" "README.md,docs/QUICKSTART.md,docs/reference/myapp.md,CHANGELOG.md"

TOTAL_END=$(date +%s)
TOTAL_TIME=$((TOTAL_END - TOTAL_START))

echo ""
echo "==============================="
echo "RESULTS: $PASS passed, $FAIL failed"
echo "==============================="

# Summary table
echo ""
echo "┌────────┬────────────────────────────────┬────────┬─────────┬─────────┬───────┐"
echo "│ Scenario│ File                           │ Detect │ Enforce │ AutoGen │ Time  │"
echo "├────────┼────────────────────────────────┼────────┼─────────┼─────────┼───────┤"
for i in 01 02 03 04 05 06 07 08 09 10; do
    name="${SCENARIO_NAMES[$i]:-?}"
    detect="${DETECT_RESULTS[$i]:-?}"
    enforce="${ENFORCE_RESULTS[$i]:-?}"
    autogen="${AUTOGEN_RESULTS[$i]:-?}"
    time_s="${SCENARIO_TIMES[$i]:-0}"
    printf "│ %-7s│ %-31s│ %-7s│ %-8s│ %-8s│ %-5ss│\n" "$i" "$name" "$detect" "$enforce" "$autogen" "$time_s"
done
echo "└────────┴────────────────────────────────┴────────┴─────────┴─────────┴───────┘"
echo ""
echo "Total time: ${TOTAL_TIME}s"

if [ $FAIL -gt 0 ]; then
    exit 1
fi
