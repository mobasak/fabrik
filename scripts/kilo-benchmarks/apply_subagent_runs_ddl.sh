#!/bin/bash
# AFTER-EDIT: none (one-shot DDL applier)
# Applies SUBAGENT_RUNS_DDL imported verbatim from /opt/fabrik-lib/subagents to the
# local WSL postgres. Idempotent (CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS).
#
# Auth: uses `sudo -n -u postgres psql` (peer auth on unix socket) — WSL pg_hba.conf
# has `local all postgres peer` (verified 2026-07-06). TCP would require scram-sha-256
# password auth (fe_sendauth: no password supplied), which we don't have set up in
# WSL dev. Projects that write to this table via SUBAGENT_RUNS_DSN over TCP will
# need POSTGRES_PASSWORD in their env — module fails-open (JSONL-only) if not.
#
# Source of truth for the DDL is the module's pg_ledger.py:35 export — NEVER author
# the schema locally. `python -c "from subagents import SUBAGENT_RUNS_DDL"` imports it.
set -euo pipefail

DDL=$(cd /opt/fabrik-lib/subagents && python3 -c "from subagents import SUBAGENT_RUNS_DDL; print(SUBAGENT_RUNS_DDL)")

# Ensure fabrik_analytics DB exists (cost_ledger already lives there).
DB_EXISTS=$(sudo -n -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='fabrik_analytics'" 2>/dev/null || echo "")
if [ "$DB_EXISTS" != "1" ]; then
  sudo -n -u postgres psql -c "CREATE DATABASE fabrik_analytics"
  echo "Created database: fabrik_analytics"
else
  echo "Database exists: fabrik_analytics"
fi

# Apply DDL (idempotent via CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS).
echo "$DDL" | sudo -n -u postgres psql -d fabrik_analytics

# Verify columns landed.
sudo -n -u postgres psql -d fabrik_analytics -tAc \
  "SELECT string_agg(column_name, ',' ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name='subagent_runs'"

echo "OK — subagent_runs applied to fabrik_analytics"
