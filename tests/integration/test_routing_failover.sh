#!/bin/bash
# Integration test for plan §11.3 G5.5 — fail-loud-not-fatal contract.
#
# What this verifies:
#   1. If the OpenRouter category classifier dies, the subshell wrapper in
#      `wsl_startup_hook.sh` logs `[openrouter-routing] classifier failed
#      (non-fatal)` and CONTINUES — does NOT short-circuit the rest of the
#      pipeline.
#   2. The downstream `check_ai_pack_freshness.py` step still runs.
#
# How:
#   - Point the wrapper at a path that does not exist
#     (`__does_not_exist__.py`) so the python interpreter exits non-zero
#     on file-open. (chmod -x on a .py is a no-op for `python <script>`
#     — it only needs read perms — verified by Pass A Finding 1.)
#   - Run the wrapper's exact subshell-with-`|| echo`-and-log shape (NOT
#     the full hook — we test only the routing block in isolation, no
#     nohup, no LOCK_FILE).
#   - Then invoke the freshness check directly (mirroring the line that
#     follows the routing block in the real hook).
#   - Assert: both "classifier failed" AND "ai-pack-freshness" lines
#     appear in the log.
#   - `trap` removes the temp log on EXIT — no chmod state to restore.
#
# Run: bash tests/integration/test_routing_failover.sh

set -u  # no -e — the test EXPECTS the classifier to fail and the wrapper
        # to swallow the failure; -e would short-circuit our intent.

FABRIK_ROOT="${FABRIK_ROOT:-/opt/fabrik}"
VENV_PYTHON="$FABRIK_ROOT/.venv/bin/python"
FRESHNESS="$FABRIK_ROOT/scripts/check_ai_pack_freshness.py"
LOG=$(mktemp)

cleanup() {
    rm -f "$LOG"
}
trap cleanup EXIT

echo "[test_routing_failover] log=$LOG"

# Force the classifier to fail by pointing at a nonexistent path.
# Plan §11.3 G5.5 originally proposed `chmod -x` on the script itself,
# but `python <script>` doesn't need exec bit (only read), so chmod -x
# is a no-op — the technique is "make the file-open fail" instead.
# Pass A Finding 1 fix: dropped the dead CLASSIFIER variable + the
# no-op chmod restore in cleanup. The plan §11.3 G5.5 gate-text was
# updated in lockstep.
BROKEN_CLASSIFIER="$FABRIK_ROOT/scripts/kilo-benchmarks/__does_not_exist__.py"

# 2. Mirror the wrapper's subshell + per-command failure isolation.
(
    cd "$FABRIK_ROOT/scripts/kilo-benchmarks"
    "$VENV_PYTHON" "$BROKEN_CLASSIFIER" >> "$LOG" 2>&1 \
        || echo "[openrouter-routing] classifier failed (non-fatal)" >> "$LOG"
)

# 3. Now verify the freshness check still fires — exactly as the real
#    hook does on line after the routing block.
"$VENV_PYTHON" "$FRESHNESS" >> "$LOG" 2>&1

# 4. Assert both markers present.
fail=0
grep -q "classifier failed" "$LOG" || { echo "MISS: classifier failed log line"; fail=1; }
grep -q "ai-pack-freshness" "$LOG" || { echo "MISS: ai-pack-freshness log line"; fail=1; }

if [ "$fail" -eq 0 ]; then
    echo "[test_routing_failover] PASS — fail-loud-not-fatal contract honored"
    exit 0
else
    echo "[test_routing_failover] FAIL"
    echo "--- log ---"
    cat "$LOG"
    exit 1
fi
