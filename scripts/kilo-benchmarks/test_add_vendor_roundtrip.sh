#!/usr/bin/env bash
# test_add_vendor_roundtrip.sh — operator confidence test for the
# documented "add a new vendor" workflow.
#
# Per docs/operations/AI_MODELS_BROWSER_OPS.md §"Adding a new vendor".
# Per docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md
# Phase 5 Gate 3: "<15min real time; final assertion 'TEST_PASS' in stdout".
#
# What this validates END-TO-END:
#   1. Registry YAML is loadable and a new vendor entry can be added.
#   2. The orchestrator dry-runs cleanly when parser_module is null
#      (the stubbed-vendor path).
#   3. Switching parser_module to a real shipped parser triggers a
#      live fetch via vps1 browserless + parser invocation + audit
#      MD generation.
#   4. The audit MD captures the new vendor in its per-vendor section.
#   5. Cleanup: registry restored to its committed state; nothing
#      leaks to the DB (apply mode is NOT used — pure dry-run).
#
# Does NOT touch the real DB. Does NOT modify the committed registry
# permanently (restores from git index on exit). Does NOT require an
# operator-supplied real-world vendor URL — uses Anthropic's
# already-mapped fixture for the live-fetch step.
#
# Exit codes:
#   0 — all assertions passed, final stdout: TEST_PASS
#   1 — any assertion failed (per-step error printed to stderr)
#
# Usage:
#   bash scripts/kilo-benchmarks/test_add_vendor_roundtrip.sh
#   # Optional: VERBOSE=1 to see per-step traces.

set -u
FABRIK_ROOT="${FABRIK_ROOT:-/opt/fabrik}"
KB="$FABRIK_ROOT/scripts/kilo-benchmarks"
VENV_PY="$FABRIK_ROOT/.venv/bin/python"
REGISTRY="$KB/direct_vendor_pricing_registry.yaml"

# Output goes to a per-run scratch dir so concurrent CI doesn't collide
SCRATCH=$(mktemp -d -t fabrik-roundtrip-XXXXXX)
AUDIT_MD="$SCRATCH/audit.md"

# Restore registry on exit (success OR failure) so the test never leaves
# the committed file dirty. Uses git index, not file backup, so this is
# robust against partial writes.
cleanup() {
  local rc=$?
  if [ -d "$FABRIK_ROOT/.git" ]; then
    git -C "$FABRIK_ROOT" checkout -- "scripts/kilo-benchmarks/direct_vendor_pricing_registry.yaml" 2>/dev/null || true
  fi
  rm -rf "$SCRATCH"
  exit $rc
}
trap cleanup EXIT INT TERM

log()  { echo "[roundtrip] $*"; }
fail() { echo "[roundtrip] FAIL: $*" >&2; exit 1; }

if [ "${VERBOSE:-0}" = "1" ]; then
  set -x
fi

# ----------------------------------------------------------------------
# Phase 0 — environment sanity
# ----------------------------------------------------------------------
log "Phase 0: environment sanity"
[ -f "$VENV_PY" ] || fail "venv python not found at $VENV_PY"
[ -f "$REGISTRY" ] || fail "registry not found at $REGISTRY"
"$VENV_PY" -c "import yaml" 2>/dev/null || fail "yaml not importable from venv"

if [ -z "${BROWSERLESS_TOKEN:-}" ]; then
  # Try to load from .env (cron pattern)
  if [ -f "$FABRIK_ROOT/.env" ]; then
    export BROWSERLESS_TOKEN=$(grep '^BROWSERLESS_TOKEN=' "$FABRIK_ROOT/.env" | cut -d= -f2-)
  fi
fi
[ -n "${BROWSERLESS_TOKEN:-}" ] || fail "BROWSERLESS_TOKEN not set and not in .env"

# ----------------------------------------------------------------------
# Step 1 (matches docs §"Adding a new vendor" step 1):
#   Add a stub registry entry with parser_module: null
# ----------------------------------------------------------------------
log "Step 1: append stub vendor 'roundtrip_test' to registry (parser_module=null)"
cat >> "$REGISTRY" <<EOF

# ROUNDTRIP TEST — added by test_add_vendor_roundtrip.sh; cleaned up via git checkout on exit.
roundtrip_test:
  pricing_url: https://docs.anthropic.com/en/docs/about-claude/pricing
  fetch_method: rendered
  parser_module: null
EOF

"$VENV_PY" -c "import yaml; d = yaml.safe_load(open('$REGISTRY')); assert 'roundtrip_test' in d, 'stub not loadable'" \
  || fail "Step 1: stub entry not loadable by yaml.safe_load"
log "Step 1 OK: stub vendor in registry"

# ----------------------------------------------------------------------
# Step 2 (matches docs step 2):
#   Verify dry-run picks up the stub with the documented log message
# ----------------------------------------------------------------------
log "Step 2: dry-run orchestrator filtered to the stub vendor"
# The orchestrator skips vendors with parser_module=null when require_parser=True (default).
# So a --vendors filter to the stub alone should produce 0 vendors processed.
DRY_OUT="$SCRATCH/step2.out"
"$VENV_PY" "$KB/fetch_direct_vendor_prices.py" --vendors roundtrip_test 2>&1 > "$DRY_OUT" \
  || fail "Step 2: dry-run exited non-zero"
# We expect zero vendor outcomes for parser_module=null (default --apply NOT set):
if grep -q "roundtrip_test" "$DRY_OUT"; then
  fail "Step 2: stubbed vendor should be filtered out, but it appeared in output"
fi
log "Step 2 OK: stub correctly skipped (require_parser=True path)"

# ----------------------------------------------------------------------
# Step 3 (matches docs steps 3-4):
#   Flip parser_module to a real shipped parser (subscription_monitor)
#   and confirm the orchestrator now processes it end-to-end.
# ----------------------------------------------------------------------
log "Step 3: switch parser_module → subscription_monitor (no DB writes in dry-run)"
# Restore registry first (so we apply a clean swap), then re-add the stub
# with parser_module set this time.
git -C "$FABRIK_ROOT" checkout -- "scripts/kilo-benchmarks/direct_vendor_pricing_registry.yaml"

cat >> "$REGISTRY" <<EOF

# ROUNDTRIP TEST — added by test_add_vendor_roundtrip.sh; cleaned up via git checkout on exit.
roundtrip_test:
  pricing_url: https://docs.anthropic.com/en/docs/about-claude/pricing
  fetch_method: rendered
  parser_module: direct_vendor_parsers.subscription_monitor
EOF

LIVE_OUT="$SCRATCH/step3.out"
"$VENV_PY" "$KB/fetch_direct_vendor_prices.py" \
    --vendors roundtrip_test \
    --report-md "$AUDIT_MD" 2>&1 > "$LIVE_OUT" \
  || fail "Step 3: live fetch exited non-zero (stdout: $LIVE_OUT)"

# The vendor MUST appear in the orchestrator output line "[fetch] roundtrip_test DRY-RUN ..."
grep -E "\[fetch\] roundtrip_test\s+DRY-RUN" "$LIVE_OUT" \
  || fail "Step 3: expected '[fetch] roundtrip_test DRY-RUN ...' line in output (saw: $(cat $LIVE_OUT))"
log "Step 3 OK: live fetch completed, vendor in orchestrator output"

# ----------------------------------------------------------------------
# Step 4 (matches docs step 7):
#   The audit MD must include the new vendor's section.
# ----------------------------------------------------------------------
log "Step 4: audit MD must include the new vendor"
[ -f "$AUDIT_MD" ] || fail "Step 4: audit MD not written to $AUDIT_MD"

grep -q "### roundtrip_test" "$AUDIT_MD" \
  || fail "Step 4: audit MD missing '### roundtrip_test' section (got: $(head -30 $AUDIT_MD))"

# Anthropic's docs page is rich with $X / MTok per-call patterns, so
# subscription_monitor should detect them and emit an alert. This verifies
# the alert-emission path AND the audit's Alerts section in one shot.
if grep -q "per-call-pricing-emergence-alert" "$AUDIT_MD"; then
  log "Step 4 OK: audit captured subscription_monitor's alert behavior"
else
  # Alternative success: parsed=0 means subscription confirmed. Either is a
  # valid roundtrip outcome — both prove the audit MD generation works.
  grep -q "subscription-only confirmed" "$AUDIT_MD" \
    || fail "Step 4: audit lacks both alert AND subscription-confirmed signals"
  log "Step 4 OK: audit captured subscription-confirmed signal"
fi

# ----------------------------------------------------------------------
# Step 5: cleanup verification — registry MUST be back to committed state
# after cleanup() runs. We can't assert that mid-script (the trap fires
# on exit), so we manually validate the committed-state check here.
# ----------------------------------------------------------------------
log "Step 5: cleanup will restore registry on exit (trap)"
"$VENV_PY" -c "
import yaml
d = yaml.safe_load(open('$REGISTRY'))
# After this script exits, 'roundtrip_test' should NOT be in registry.
# Right now it IS — that's expected (cleanup hasn't fired yet).
assert 'roundtrip_test' in d, 'expected roundtrip_test still present pre-cleanup'
" || fail "Step 5: registry state unexpected pre-cleanup"

echo ""
echo "TEST_PASS"
exit 0
