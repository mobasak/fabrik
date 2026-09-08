#!/usr/bin/env bash
# AFTER-EDIT: none
#
# Re-vendor canonical /opt/fabrik-lib/subagents into the hub copy — HUB-ONLY since D-196
# (2026-09-08). `libs/subagents` left VENDORED_DIRS, so this NO LONGER distributes the module to the
# projects; a canonical fix reaches the hub copy and stops there. Called by the /opt/fabrik-lib
# `post-commit` hook. It fires NO fleet sync (D-202 — see the note at the end of this file); the hub's
# own post-commit governance-sync distributes the other synced surfaces, on a hub commit.
#
# It does NOT commit the hub copy: an automated committer on the shared /opt/fabrik master is the wrong
# trade (collision risk). The hub copy is picked up by the next normal hub commit.
# (The old justification here cited the per-project .fabrik/synced.lock — but this script writes no
# lock since D-202, and the only locks still carrying the module are 2 of 47 under /opt, both
# worktree-shaped fabrik-lib repos the sync skips by design. Re-derive:
#   ls /opt/*/.fabrik/synced.lock | wc -l   +   grep -l libs/subagents /opt/*/.fabrik/synced.lock
# tests/test_synced_manifest.py measures the same quantity and must agree. The collision-risk
# reason stands on its own and is the only one that was ever load-bearing.)
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

# BAIL LOUDLY on a module that doesn't import (canonical may be mid-edit) — but be honest about what
# this does and does not protect. It is NOT fail-closed for the hub: the rsync/cp above has ALREADY
# overwritten /opt/fabrik/libs/subagents by the time this runs, so a mid-edit canonical commit leaves
# a broken module in place and exits 1. That matters because three hub scripts import it unguarded at
# module level and one runs weekly from cron (pinned by tests/test_synced_manifest.py). And since
# D-202 nothing is DISTRIBUTED here at all, so "never distribute" describes a step that no longer
# exists. The exit-1 is a signal to the operator, not a guard — the next good commit re-fires this
# and heals the hub copy.
if ! "$PY" -c "import sys; sys.path.insert(0,'/opt/fabrik'); from libs.subagents import fanout, pick_models, record_agent_run" 2>/dev/null; then
  echo "distribute_subagents: hub copy FAILS TO IMPORT and is now BROKEN in place (the re-vendor
  above already overwrote it; canonical was probably mid-edit). Hub scripts import this module
  unguarded — re-run after the next good fabrik-lib commit." >&2
  exit 1
fi

# ⚠️ HUB-ONLY since D-196 (2026-09-08). `libs/subagents` was retired from VENDORED_DIRS, so the fleet
# sync no longer carries this module to the ~46 projects — a canonical fix reaches the HUB copy and
# stops there. Re-enabling fleet distribution means re-adding the entry to VENDORED_DIRS (and
# removing it from RETIRED_VENDORED_DIRS), not editing this script.
echo "distribute_subagents: re-vendored canonical -> HUB ONLY (fleet distribution retired, D-196)."
echo "distribute_subagents: no fleet sync fired — see the note above (D-202)."

# ⚠️ THE UNATTENDED FLEET SYNC THAT USED TO RUN HERE IS GONE (D-202, 2026-09-08).
# It was justified as "the OTHER governance surfaces still ride it", but the trigger above gates this
# whole script on "did this fabrik-lib commit touch subagents/?" — the ONE thing D-196 stopped
# distributing. So the retirement inverted it: the fleet-wide push fired exactly and only for the
# module it no longer carries.
# What made that dangerous rather than merely pointless: the sync copies WORKING-TREE contents
# (shutil.copy2), unattended, to ~45 repos. Measured at the moment this was found, 13 synced-surface
# files in the hub carried uncommitted sibling WIP — a fabrik-lib commit in that minute would have
# force-shipped all 13. `check_sync_trigger_coverage.py` names this exact hazard in its own exemption
# list as the reason PROJECT_CATALOG.md is not a trigger.
# The hub's own post-commit governance-sync still distributes those surfaces, on a HUB commit, made by
# an agent who knows the tree state. That is the correct trigger; this was not.
