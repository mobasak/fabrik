#!/usr/bin/env bash
# AFTER-EDIT: none
#
# Re-vendor canonical /opt/fabrik-lib/subagents into the hub fleet-source copy, then distribute it to
# every project (atomic writes). Called by the /opt/fabrik-lib `post-commit` hook so a fabrik-lib
# subagents change reaches all projects with NO manual step — and safely, even while a project is
# actively importing the module (sync_enforcement_to_projects writes each file via tmp+os.replace, so a
# running dispatch keeps its in-memory copy and never sees a torn read).
#
# It does NOT commit the hub copy: an automated committer on the shared /opt/fabrik master is the wrong
# trade (collision risk). The sync's per-project .fabrik/synced.lock keeps check_synced_unmodified green
# regardless of whether the hub copy is committed; the hub copy is picked up by the next normal hub commit.
set -euo pipefail

CANON=/opt/fabrik-lib/subagents
HUB=/opt/fabrik/libs/subagents
PY=/opt/fabrik/.venv/bin/python

# Guard: act only when subagents/ actually changed in the triggering commit (cheap no-op otherwise).
if git -C /opt/fabrik-lib rev-parse HEAD~1 >/dev/null 2>&1; then
  if ! git -C /opt/fabrik-lib diff --name-only HEAD~1 HEAD -- subagents/ | grep -q .; then
    exit 0  # commit didn't touch the subagents module
  fi
fi

# Re-vendor canonical -> hub (flat). Prefer rsync --delete so a file canonical REMOVED is dropped from
# the hub too (no stale source); fall back to cp -r where rsync is absent.
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete --exclude='__pycache__' --exclude='*.pyc' "$CANON/subagents/" "$HUB/"
else
  cp -r "$CANON/subagents/." "$HUB/"
fi
cp "$CANON/requirements.txt" "$HUB/requirements.txt" 2>/dev/null || true

# FAIL-CLOSED: never distribute a module that doesn't import (canonical may be mid-edit). Leave the hub
# as-is and bail loudly — the next good commit re-fires this and heals it.
if ! "$PY" -c "import sys; sys.path.insert(0,'/opt/fabrik'); from libs.subagents import fanout, pick_models, record_agent_run" 2>/dev/null; then
  echo "distribute_subagents: hub copy fails to import — NOT distributing (canonical mid-edit?)." >&2
  exit 1
fi

# ⚠️ HUB-ONLY since D-196 (2026-09-08). `libs/subagents` was retired from VENDORED_DIRS, so the fleet
# sync no longer carries this module to the ~46 projects — a canonical fix reaches the HUB copy and
# stops there. The sync is still run because this script may be the only thing that fires after a
# fabrik-lib commit and other governance surfaces still ride it, but do NOT read its output as
# "the module reached the fleet": it did not, by design. Re-enabling fleet distribution means
# re-adding the entry to VENDORED_DIRS (and removing it from RETIRED_VENDORED_DIRS), not editing this.
echo "distribute_subagents: re-vendored canonical -> HUB ONLY (fleet distribution retired, D-196);"
echo "distribute_subagents: running the fleet sync for the OTHER governance surfaces…"
"$PY" /opt/fabrik/scripts/sync_enforcement_to_projects.py 2>&1 | tail -2
