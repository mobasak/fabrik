#!/usr/bin/env python3
# AFTER-EDIT: tests/test_user_hook_gate.py | docs/workstation/hooks-index.md
"""USER-level hook gate: run a hub hook for every window UNLESS the project already wires it.

Closes the sync-excluded gap (fabrik-lib had no MCP banner and no quota hold, 2026-09-06)
without editing a fleet-synced hook and without touching the exclusion ruling: the hub's
`.claude/hooks/mcp_watch.py` and `quota_stop.py` are registered at user level THROUGH this gate.
In the 42 synced repos the project's own copy fires and this exits silently — no double banner,
no double deny. In fabrik-lib, /opt itself, and any cwd with no project hooks, the hub copy fires.

    user_hook_gate.py /opt/fabrik/.claude/hooks/<hook>.py     (stdin: the hook payload, passed through)

Detection is by BASENAME in `<cwd>/.claude/settings.json`'s hook commands — the same string the
project registration carries. Unreadable or absent settings → the hook RUNS (fail-open toward
coverage: a broken settings file must not silently strip a window of its hold). The hook's exit
code and stdout pass through untouched — `quota_stop.py` DENIES with a non-zero exit and this
gate must never launder that into an allow.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _project_wires(cwd: str, basename: str) -> bool:
    try:
        settings = Path(cwd) / ".claude" / "settings.json"
        if not settings.is_file():
            return False
        return basename in settings.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001 — fail-open toward running the hook
        return False


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        return 0
    hook = Path(argv[1])
    raw = sys.stdin.read()
    try:
        cwd = str(json.loads(raw or "{}").get("cwd") or os.getcwd())
    except Exception:  # noqa: BLE001
        cwd = os.getcwd()
    if _project_wires(cwd, hook.name):
        return 0
    if not hook.is_file():
        return 0
    proc = subprocess.run(
        [sys.executable, str(hook)], input=raw, capture_output=True, text=True, timeout=120
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
