#!/bin/bash
# AFTER-EDIT: none (one-shot DDL applier)
# Applies SUBAGENT_RUNS_DDL imported verbatim from /opt/fabrik-lib/subagents to the
# local WSL postgres. Idempotent (CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT
# EXISTS + verify-columns assertion).
#
# Auth: uses `sudo -n -u postgres psql` (peer auth on unix socket) — WSL pg_hba.conf
# has `local all postgres peer` (verified 2026-07-06). TCP would require scram-sha-256
# password auth. Projects that write to this table via SUBAGENT_RUNS_DSN over TCP
# need a password in their DSN — the module fails-open (JSONL-only) if not.
#
# Source of truth for the DDL is the module's pg_ledger.py:35 export — NEVER author
# the schema locally. `python3 -c "from subagents import SUBAGENT_RUNS_DDL"` imports it.
#
# Failure discipline (per /fabrik-review Finder B#1, B#2):
#   * `-v ON_ERROR_STOP=1` on every psql invocation → mid-batch failure exits non-zero
#     (was: psql's default continue-on-error returned 0 even on partial DDL apply).
#   * The verify step ASSERTS the emitted column set matches EXPECTED_COLUMNS — was
#     display-only before, so a partial migration would silently print "OK" with the
#     wrong schema live on disk.
set -euo pipefail

# Expected column set — kept in ordinal order. Update this constant WHEN AND ONLY
# WHEN SUBAGENT_RUNS_DDL in /opt/fabrik-lib/subagents/subagents/pg_ledger.py changes
# its column list (13 columns as of 2026-07-06). The assertion below compares against
# this string byte-for-byte, so a schema evolution that misses this update fails loudly.
EXPECTED_COLUMNS="id,ts,project,agent_id,task_type,model,provider,status,cost_usd,turns,latency_s,quality_score,tool_calls"

DDL=$(cd /opt/fabrik-lib/subagents && python3 -c "from subagents import SUBAGENT_RUNS_DDL; print(SUBAGENT_RUNS_DDL)")

# Ensure fabrik_analytics DB exists (cost_ledger already lives there).
DB_EXISTS=$(sudo -n -u postgres psql -v ON_ERROR_STOP=1 -tAc \
  "SELECT 1 FROM pg_database WHERE datname='fabrik_analytics'" 2>/dev/null || echo "")
if [ "$DB_EXISTS" != "1" ]; then
  sudo -n -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE fabrik_analytics"
  echo "Created database: fabrik_analytics"
else
  echo "Database exists: fabrik_analytics"
fi

# Apply DDL — ON_ERROR_STOP so mid-batch failure exits non-zero (Finder B#1).
echo "$DDL" | sudo -n -u postgres psql -v ON_ERROR_STOP=1 -d fabrik_analytics

# Assert the emitted column set matches expectations (Finder B#2). Not just display.
ACTUAL_COLUMNS=$(sudo -n -u postgres psql -v ON_ERROR_STOP=1 -d fabrik_analytics -tAc \
  "SELECT string_agg(column_name, ',' ORDER BY ordinal_position) \
   FROM information_schema.columns \
   WHERE table_name='subagent_runs' AND table_schema='public'")

if [ "$ACTUAL_COLUMNS" != "$EXPECTED_COLUMNS" ]; then
  echo "FAIL — subagent_runs schema drift detected."
  echo "Expected: $EXPECTED_COLUMNS"
  echo "Actual:   $ACTUAL_COLUMNS"
  echo ""
  echo "The DDL was applied but the resulting column set is not what this script expects."
  echo "Either (a) SUBAGENT_RUNS_DDL in /opt/fabrik-lib/subagents evolved and this"
  echo "script's EXPECTED_COLUMNS constant needs to be updated, or (b) the table was"
  echo "manually altered out-of-band. Fix upstream, then re-run this script."
  exit 1
fi

echo "OK — subagent_runs applied to fabrik_analytics ($ACTUAL_COLUMNS)"
