#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/hooks-index.md docs/workstation/claude-configuration-inventory.md tests/test_claude_selfwatch_orient.py
# claude_selfwatch_orient.sh — user-level SessionStart hook (registered in ~/.claude/settings.json,
# so it runs for EVERY session on the box). Emits the resume-mesh self-watch ARM order for
# sessions whose project has NO session_orient.py: sync-excluded repos (fabrik-lib) never got
# the hub hook, so their panes never armed a watch and every API-error death there waited
# for a human "proceed" (3 of the 4 unarmed /opt sessions on 2026-09-03).
#
# Mirrors the hub hook's gates — a real sid, not headless, not source=compact, the watch
# script present — and adds two of its own: /opt trees only (the VS Code one-shot helper
# sessions in /tmp have no pane to wake) and no project session_orient.py (which already
# emits the order; two orders breed two arms). Fail-open: any parse error prints nothing.
# Authority for every mesh claim: docs/workstation/hooks-index.md.
set -u
payload=$(cat 2>/dev/null || true)
python3 - "$payload" <<'PY'
import json, os, re, sys
from pathlib import Path
try:
    d = json.loads(sys.argv[1] or "{}")
except Exception:
    d = {}
if not isinstance(d, dict):
    d = {}
sid = re.sub(r"[^A-Za-z0-9_-]", "_", str(d.get("session_id") or ""))[:64]
cwd = str(d.get("cwd") or os.getcwd())
proj = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
home = Path(os.environ.get("HOME", str(Path.home())))
if (
    not sid
    or os.environ.get("CLAUDE_MESH_HEADLESS") == "1"
    or d.get("source") == "compact"
    or not (home / ".claude/bin/claude-selfwatch.sh").is_file()
    or not (cwd == "/opt" or cwd.startswith("/opt/"))
    or Path(proj, ".claude/hooks/session_orient.py").is_file()
):
    sys.exit(0)
print(
    "## ORIENT (resume mesh — this repo has no session_orient hook)\n"
    "- **ARM YOUR SELF-WATCH NOW (first tool action, operator-mandated):** call "
    f"Monitor(persistent: true, command: \"bash ~/.claude/bin/claude-selfwatch.sh {sid}\", "
    "description: \"resume-mesh self-watch\") — it wakes THIS pane automatically when a turn "
    "dies on a healed API error or a lost waker. It is a STANDING watch: never re-arm after a "
    "wake (a duplicate arm for this session exits at once). NEVER a `nohup ... &` Bash arm — "
    "its wake line lands in /dev/null. Authority: /opt/fabrik/docs/workstation/hooks-index.md"
)
PY
