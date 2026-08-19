#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/kaizen.md, .fabrik/liveness-registry.json | none
#
# Wake-proof weekly runner (M0 shrink ruling, 2026-08-19). The three Monday-06:xx
# crons silently missed their slots whenever the host hibernated through Monday
# morning (cron has no catch-up; the 2026-08-17 week was lost). This runs HOURLY
# and fires the named job only when its success stamp is >= ~7 days old — the
# weekly cadence survives any sleep pattern, and a missed week is caught up
# within an hour of the box waking.
#
# Contract: quiet when fresh (exit 0, no output — the job logs stay weekly, which
# is exactly what the liveness registry's max_age_hours heartbeat expects);
# stamp touched ONLY on job success, so a failing job retries hourly and its
# log shows every attempt. Job keys are the SCRIPT FILENAMES so the liveness
# registry's cron_match entries keep matching the crontab lines.
set -u

JOB="${1:?usage: weekly_catchup.sh <job-key: audit_authelia_gates.py|fleet_doc_audit.py|kaizen_metrics.py>}"
STATE="$HOME/.claude/state"
mkdir -p "$STATE"
STAMP="$STATE/weekly-${JOB}.stamp"
PERIOD=$(( 7*86400 - 1800 ))  # a week minus 30 min slack so hourly drift never skips a week

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
        PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/audit_authelia_gates.py
        ;;
    fleet_doc_audit.py)
        cd /opt/fabrik && .venv/bin/python scripts/fleet_doc_audit.py --commit
        ;;
    kaizen_metrics.py)
        cd /opt/fabrik && .venv/bin/python scripts/sysadmin/kaizen_metrics.py --once
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
