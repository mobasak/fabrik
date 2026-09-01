#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/kaizen.md, .fabrik/liveness-registry.json | none
#
# Wake-proof periodic runner (M0 shrink ruling, 2026-08-19). Fixed cron slots are
# silently missed whenever the host hibernates through them (cron has no catch-up;
# the 2026-08-17 kaizen week was lost that way). This runs HOURLY from cron and
# fires the named job only when its success stamp is older than the job's PERIOD
# (weekly or daily, minus 30 min slack so hourly drift never skips a cycle) — the
# cadence survives any sleep pattern, and a missed cycle is caught up within an
# hour of the box waking.
#
# Contract: quiet when fresh (exit 0, no output — job logs stay at the job's own
# cadence, which is exactly what the liveness registry's max_age_hours heartbeat
# expects); stamp touched ONLY on job success, so a failing job retries hourly and
# its log shows every attempt. Job keys are the SCRIPT FILENAMES so the liveness
# registry's cron_match entries keep matching the crontab lines.
set -u

JOB="${1:?usage: weekly_catchup.sh <job-key: audit_authelia_gates.py|fleet_doc_audit.py|kaizen_collect_v2.py|kaizen_outcomes.py|kaizen_coroner.py>}"
STATE="$HOME/.claude/state"
mkdir -p "$STATE"
# Repo root + interpreter, overridable for tests (a worktree run must not depend on
# the main tree's uncommitted state). Live crontab lines never set these.
ROOT="${FABRIK_ROOT:-/opt/fabrik}"
PY="${FABRIK_PY:-$ROOT/.venv/bin/python}"

WEEKLY=$(( 7*86400 - 1800 ))  # cadence minus 30 min slack so hourly drift never skips
DAILY=$(( 86400 - 1800 ))
# Key validation FIRST — a retired job's leftover stamp must never mask the
# retirement behind a quiet fresh-stamp exit (kaizen_metrics.py, 2026-08-20).
# RETIRED keys exit 0 (never noise-rc: a stale crontab somewhere may still carry
# the old line — hourly rc=2 forever is the trap; the hub's was swapped 2026-08-22)
# and nudge ONCE per day via their own stamp, so a leftover line stays visible without spam.
case "$JOB" in
    kaizen_metrics.py)
        NUDGE="$STATE/retired-${JOB}.nudge"
        now=$(date +%s)
        if [ -f "$NUDGE" ] && [ $(( now - $(stat -c %Y "$NUDGE") )) -lt "$DAILY" ]; then
            exit 0
        fi
        echo "weekly_catchup: kaizen_metrics.py retired (M1 T09) — superseded by kaizen_collect_v2.py; update the crontab line"
        touch "$NUDGE"
        exit 0
        ;;
    kaizen_collect_v2.py|kaizen_outcomes.py|kaizen_coroner.py)
        PERIOD=$DAILY
        STAMP="$STATE/daily-${JOB}.stamp"
        ;;
    audit_authelia_gates.py|fleet_doc_audit.py)
        PERIOD=$WEEKLY
        STAMP="$STATE/weekly-${JOB}.stamp"
        ;;
    *)
        echo "weekly_catchup: unknown job '${JOB}'" >&2
        exit 2
        ;;
esac

now=$(date +%s)
if [ -f "$STAMP" ]; then
    age=$(( now - $(stat -c %Y "$STAMP") ))
    [ "$age" -lt "$PERIOD" ] && exit 0
fi

echo "weekly_catchup: running ${JOB} ($(date -Is))"
# rc semantics differ per job: audit_authelia_gates exits 1 when the AUDIT RAN and
# found drift (a finding, not a run failure) — stamping on it keeps the weekly
# cadence instead of re-auditing every hour until the drift is fixed. rc>=2 = crash.
OK_MAX=0
case "$JOB" in
    audit_authelia_gates.py)
        OK_MAX=1
        PYTHONPATH="$ROOT/src" "$PY" "$ROOT/scripts/audit_authelia_gates.py"
        ;;
    fleet_doc_audit.py)
        cd "$ROOT" && "$PY" scripts/fleet_doc_audit.py --commit
        ;;
    kaizen_collect_v2.py)
        # The DAILY kaizen collector (M1 cutover): consolidates YESTERDAY's events
        # into derived facts, series and the kaizen-log row. Replaced the retired
        # weekly kaizen_metrics.py (scripts/sysadmin/archived/, M0 operator ruling).
        cd "$ROOT" && "$PY" scripts/sysadmin/kaizen_collect_v2.py --daily
        # RIDER (D-055, non-fatal): relay persisted FEEDBACK verdict texts from command
        # closes to the fabrik inbox (--to-agent infra) so an AGENT reads and handles
        # them — the operator does not read dashboards. Watermarked inside the relay,
        # so double-runs are no-ops; a relay failure never unstamps the collector.
        "$PY" "$ROOT/scripts/sysadmin/feedback_relay.py" || true
        # RIDER (rules pass 2026-09-01, non-fatal): version-pin tripwire — mails infra
        # when a rules pack pins a python/node version the world has moved past
        # (the answer to "what happens in one year"). Watermarked per upstream
        # release; silent on network blips.
        "$PY" "$ROOT/scripts/sysadmin/rules_currency_watch.py" || true
        ;;
    kaizen_outcomes.py)
        # The nightly fleet-health sweep (T07 outcome tier): clean HEAD worktrees,
        # install-less checks, one fleet_health event per swept project.
        cd "$ROOT" && "$PY" scripts/sysadmin/kaizen_outcomes.py --sweep
        ;;
    kaizen_coroner.py)
        # The DAILY coroner sweep (review fix-wave H5): post-hoc death/revival
        # reconstruction + closure of run records that can no longer close
        # themselves. Nothing else on the box runs it — the hole metric and the
        # record TTLs depend on this job. Crontab line (INSTALLED 2026-08-22 on
        # the hub crontab, same pattern as the siblings):
        #   53 * * * * flock -n $HOME/.claude/state/daily-kaizen-coroner.lock /opt/fabrik/scripts/sysadmin/weekly_catchup.sh kaizen_coroner.py >> $HOME/.claude/kaizen-coroner.log 2>&1
        cd "$ROOT" && "$PY" scripts/sysadmin/kaizen_coroner.py --sweep
        ;;
    *)
        echo "weekly_catchup: unknown job '${JOB}'" >&2
        exit 2
        ;;
esac
rc=$?
if [ "$rc" -le "$OK_MAX" ]; then
    touch "$STAMP"
else
    echo "weekly_catchup: ${JOB} FAILED (rc=${rc}) — will retry next hour" >&2
fi
exit "$rc"
