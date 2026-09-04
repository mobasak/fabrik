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
# libs/alerting (the retired orchestrator's alert, kept), and the liveness heartbeat —
# `$HEARTBEAT`, `external-services-chain` in .fabrik/liveness-registry.json — is stamped by THIS
# script ONLY, after every DATA step succeeded (gather_envs, reconsolidate, registry_sync) and the
# dashboard was written, so a half-dead chain lets the stamp age past its 30 h budget and reads
# DEAD instead of green (review 2026-09-02); a stamp the script cannot write is alerted (exit 1)
# and never replaces the previous one. The dashboard file's own mtime is NOT the heartbeat:
# a manual `gen_dashboard.py` run refreshed it and certified LIVE a chain the cron had not run
# for 46 h (CY1);
# a failed classify (the paid, optional pass) alerts but does not age the heartbeat. Each step runs under
# `timeout`.
set -u
FABRIK_ROOT="${FABRIK_ROOT:-/opt/fabrik}"
cd "$FABRIK_ROOT" || exit 1  # the boot hook reaches this script from /opt/session-recall (its `cd` never returns): the classifier's alerting autoload read THAT repo's .env and its "new providers" alert was never delivered on the boot path (FD6)
VENV_PY="${VENV_PY:-$FABRIK_ROOT/.venv/bin/python}"
STEP_TIMEOUT="${STEP_TIMEOUT:-900}"
[ "$STEP_TIMEOUT" -gt 0 ] 2>/dev/null || STEP_TIMEOUT=900  # `0` DISABLES timeout(1): a numeric override passed every guard and switched the only hang protection off (FC6)
CLASSIFY_TIMEOUT="${CLASSIFY_TIMEOUT:-2100}"
[ "$CLASSIFY_TIMEOUT" -gt 0 ] 2>/dev/null || CLASSIFY_TIMEOUT=2100  # same guard (FC6)  # the paid step: 10 units × up to 7 model calls + web searches, ALL in parallel (the pool caps concurrency at the unit count); one unit's wall clock is 1800 s + 30 s grace, so the budget must exceed 1830 — the generic 900 s was shorter than one unit (DM1/DO1)
LOG_FILE="${LOG_FILE:-/dev/stderr}"
DASHBOARD="$FABRIK_ROOT/external-services-dashboard.html"
HEARTBEAT="$FABRIK_ROOT/.tmp/external-services/chain-heartbeat"  # the liveness evidence path (mirrored in .fabrik/liveness-registry.json)
chain_failed=0   # any step failed (exit code of this script)
core_failed=0    # a step the dashboard DEPENDS on failed (gather_envs / reconsolidate / registry_sync)

_alert() {  # $1 title, $2 body, $3 severity
  # a False return is SAID in the log with its cause (disabled vs every method failed — dedup
  # cannot fire across processes); the root is argv, never source text (a `'` in FABRIK_ROOT was
  # a swallowed SyntaxError); an unreadable .env is said, not a traceback; bounded at 60 s (FB10/FC6);
  # a MISSING interpreter is said too — `timeout: failed to run command` was swallowed by `|| true`
  # and the chain went on as if every step alert had fired (FD6)
  if [ ! -f "$VENV_PY" ] || [ ! -x "$VENV_PY" ]; then
    echo "[chain] alert NOT delivered (no interpreter at $VENV_PY): $1"
    return 0
  fi
  timeout -k 5 60 "$VENV_PY" -c '
import os, sys
os.environ.setdefault("FABRIK_NO_AUTOLOAD", "1")
root = sys.argv[4]
sys.path.insert(0, root + "/libs")
try:
    from dotenv import load_dotenv
    load_dotenv(root + "/.env", override=False)
except Exception as exc:
    print("[chain] .env not loaded: " + type(exc).__name__ + ": " + str(exc))
try:
    import alerting
    sent = alerting.send_alert(title=sys.argv[1], body=sys.argv[2], severity=sys.argv[3])
    if not sent:
        try:
            why = "alerting disabled (no TELEGRAM_*/ALERT_VPS_HOST in the environment)" if not alerting._is_enabled() else "every delivery method failed (see the per-method causes above)"
        except Exception:
            why = "reason unavailable"
        print("[chain] alert NOT delivered (" + why + "): " + sys.argv[1])
except Exception as exc:
    print("[chain] alert NOT delivered (" + type(exc).__name__ + ": " + str(exc) + "): " + sys.argv[1])
' "$1" "$2" "$3" "$FABRIK_ROOT" 2>&1 || true
}
_step() {  # $1 label, rest = command; records timing, alerts + flags on failure
  local label="$1"; shift
  local t0=$SECONDS
  local budget="$STEP_TIMEOUT"
  [ "$label" = classify_services ] && budget="$CLASSIFY_TIMEOUT"  # a kill here loses the slice: the cursor moved before the paid dispatch (AC5, by design) — so the budget must cover the units
  timeout -k 30 "$budget" "$@"  # SIGKILL 30 s after SIGTERM: a hung child never outlives the budget (AF13)
  local rc=$?
  printf '[timing] %s: %ds (exit=%d)\n' "$label" "$((SECONDS - t0))" "$rc"
  if [ "$rc" -eq 3 ] && [ "$label" = registry_sync ]; then
    # the registry IS written; only the post-commit credit phase failed — a stderr WARNING that
    # nobody was paged for, surfacing 48 h later as a `credit stale` cell (FD7)
    echo "[external-services-chain] registry_sync: registry written, the credit phase FAILED (exit 3) — alerting, the dashboard proceeds"
    _alert "external-services chain: credit fetch failed after the registry commit" "registry-sync exited 3: the registry is written and the dashboard is rendered; balances age until the next lap. See the WARNING line in the chain log." warning
    rc=0
  fi
  if [ "$rc" -ne 0 ]; then
    chain_failed=1
    case "$label" in gather_envs|gather_envs_reconsolidate|registry_sync) core_failed=1 ;; esac
    echo "[external-services-chain] $label failed (exit=$rc) — non-fatal, alerting"
    local hb="Dashboard not rewritten; liveness DEAD."  # rendered per label: the paid step never ages the heartbeat (G9/DA2)
    [ "$label" = classify_services ] && hb="Dashboard and heartbeat unaffected (paid step)"
    _alert "external-services chain: step $label FAILED (exit $rc)" "Step $label failed (exit $rc). 124 timeout; 137 SIGKILL; 125-127 wrapper; 2 the sync could not read the catalog (keys stored unattributed); 1 gather steps: inputs refused (catalog, ripgrep, env files) or output path unusable; 1 elsewhere: the step's own failure, a prune refusal needs the force knob. stderr names the cause; legend: docs/reference/external-services-registry.md. $hb Log: $LOG_FILE" warning
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
  if _step gen_dashboard "$VENV_PY" "$FABRIK_ROOT/scripts/gen_dashboard.py" "$DASHBOARD"; then
    # the heartbeat is stamped HERE and nowhere else — after every step ran (CY1), via tmp + rename:
    # a bare `> "$HEARTBEAT"` truncated BEFORE `date` ran, so a failed write left a fresh EMPTY stamp
    # that read LIVE (DA3); a failed stamp keeps the previous one, alerts and exits 1 — it was the
    # only failure in this script nobody was told about; `-T`: a DIRECTORY at the stamp path fails the
    # rename instead of receiving the tmp inside it and reading LIVE by its own mtime forever (DC2);
    # the mirror: a SYMLINK at the stamp path is replaced by the file, never followed (DE3)
    if mkdir -p "$(dirname "$HEARTBEAT")" && date -u +%FT%TZ > "$HEARTBEAT.tmp.$$" && mv -fT "$HEARTBEAT.tmp.$$" "$HEARTBEAT"; then :; else
      rm -f "$HEARTBEAT.tmp.$$"
      chain_failed=1
      echo "[external-services-chain] heartbeat NOT stamped ($HEARTBEAT) — liveness will read DEAD"
      _alert "external-services chain: heartbeat NOT stamped" "Every step ran but $HEARTBEAT could not be written (mkdir, write or rename failed); liveness reads DEAD until the next successful run. Log: $LOG_FILE" warning
    fi
  fi
else
  echo "[external-services-chain] a data step failed — dashboard NOT rewritten (heartbeat left to age)"
fi
exit $chain_failed
