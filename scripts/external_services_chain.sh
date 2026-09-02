#!/usr/bin/env bash
# AFTER-EDIT: scripts/kilo-benchmarks/daily_refresh.sh scripts/wsl_startup_hook.sh docs/reference/external-services-registry.md tests/test_external_services_chain.py
# The external-services chain — ONE definition, TWO entry points (daily_refresh.sh at 06:00 and
# wsl_startup_hook.sh at boot share the daily lock, so whichever wins must carry the same steps;
# the 2026-08-14 back-port note in the hook explains why a step that lives in only one of them
# silently never runs on the days the other wins).
#
#   gather_envs (env keys + code call sites) → classify (bounded, cursor-walked, paid pool)
#   → gather_envs again (today's classifications leave NEEDS-TRIAGE before the sync reads it)
#   → registry_sync --fetch-credits (Postgres fabrik_services) → gen_dashboard (static HTML)
#
# Every step is non-fatal to the caller but NEVER silent: a non-zero exit alerts via
# libs/alerting (the retired orchestrator's alert, kept), and the dashboard — the liveness
# heartbeat, `external-services-chain` in .fabrik/liveness-registry.json — is written ONLY
# when every DATA step succeeded (gather_envs, reconsolidate, registry_sync), so a half-dead chain
# lets the mtime age past its 30 h budget and reads DEAD instead of green (review 2026-09-02);
# a failed classify (the paid, optional pass) alerts but does not age the heartbeat. Each step runs under
# `timeout`.
set -u
FABRIK_ROOT="${FABRIK_ROOT:-/opt/fabrik}"
VENV_PY="${VENV_PY:-$FABRIK_ROOT/.venv/bin/python}"
STEP_TIMEOUT="${STEP_TIMEOUT:-900}"
LOG_FILE="${LOG_FILE:-/dev/stderr}"
DASHBOARD="$FABRIK_ROOT/external-services-dashboard.html"
chain_failed=0   # any step failed (exit code of this script)
core_failed=0    # a step the dashboard DEPENDS on failed (gather_envs / reconsolidate / registry_sync)

_alert() {  # $1 title, $2 body, $3 severity
  "$VENV_PY" -c "import sys; sys.path.insert(0, '$FABRIK_ROOT/libs'); from dotenv import load_dotenv; load_dotenv('$FABRIK_ROOT/.env', override=False); from alerting import send_alert; send_alert(title=sys.argv[1], body=sys.argv[2], severity=sys.argv[3])" "$1" "$2" "$3" 2>&1 || true
}
_step() {  # $1 label, rest = command; records timing, alerts + flags on failure
  local label="$1"; shift
  local t0=$SECONDS
  timeout -k 30 "$STEP_TIMEOUT" "$@"  # SIGKILL 30 s after SIGTERM: a hung child never outlives the budget (AF13)
  local rc=$?
  printf '[timing] %s: %ds (exit=%d)\n' "$label" "$((SECONDS - t0))" "$rc"
  if [ "$rc" -ne 0 ]; then
    chain_failed=1
    case "$label" in gather_envs|gather_envs_reconsolidate|registry_sync) core_failed=1 ;; esac
    echo "[external-services-chain] $label failed (exit=$rc) — non-fatal, alerting"
    _alert "external-services chain: step $label FAILED (exit $rc)" "gather_envs -> classify_services -> gather_envs -> registry_sync -> gen_dashboard lost step $label in today's run (exit $rc; 124 = timeout ${STEP_TIMEOUT}s, 137 = SIGKILL 30 s after an ignored SIGTERM, 2 = registry_sync could not read the catalog: provenance UNKNOWN, every credential stored unattributed; 1 = the scan REFUSED the catalog — unreadable, undecodable, not an object, a whitespace key, a prefix two providers claim, or a catalog emptied while the last consolidation knew vendors — the cause is the step's first stderr line). A bounded-prune refusal needs REGISTRY_PRUNE_FORCE=1 after a look; an exhausted pool or a dead registry DB needs a hand. The dashboard is NOT rewritten on a failed chain, so liveness will read DEAD until this is fixed. Log: $LOG_FILE" warning
  fi
  return $rc
}

_step gather_envs "$VENV_PY" "$FABRIK_ROOT/scripts/gather_envs.py" --apply
if [ "$core_failed" -eq 0 ]; then  # never spend the pool on YESTERDAY's queue after a failed scan (Z9)
  _step classify_services "$VENV_PY" "$FABRIK_ROOT/scripts/classify_services.py" --apply --tombstone-unresolved --max-per-run 10
else
  echo "[external-services-chain] gather_envs failed — classify skipped (stale queue, paid step)"
fi
if [ "$core_failed" -eq 0 ]; then  # a failed scan would fail identically twice — one alert, not two (AC13)
  _step gather_envs_reconsolidate "$VENV_PY" "$FABRIK_ROOT/scripts/gather_envs.py" --apply
fi
if [ "$core_failed" -eq 0 ]; then  # a failed scan leaves a STALE file: syncing it re-pages the same cause and, on a catalog error, flips every credential unattributed (BR4)
  _step registry_sync "$VENV_PY" "$FABRIK_ROOT/scripts/registry_sync.py" --fetch-credits
fi
# The heartbeat depends on the DATA steps. classify is the paid, optional pass: its failure
# (credits, pool transport) is alerted but must not report a fresh registry as DEAD (pass 2, G9).
if [ "$core_failed" -eq 0 ]; then
  _step gen_dashboard "$VENV_PY" "$FABRIK_ROOT/scripts/gen_dashboard.py" "$DASHBOARD"
else
  echo "[external-services-chain] a data step failed — dashboard NOT rewritten (heartbeat left to age)"
fi
exit $chain_failed
