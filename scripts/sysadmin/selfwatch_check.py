#!/usr/bin/env python3
# AFTER-EDIT: tests/test_selfwatch_check.py | docs/workstation/hooks-index.md | scripts/sysadmin/claude_selfwatch_orient.sh
"""UserPromptSubmit (USER level — every window, every project) — is this session's self-watch ARMED?

The arm was always an ORDER: `session_orient.py` prints it at SessionStart in the synced repos,
`claude_selfwatch_orient.sh` prints it for the rest, and nothing ever checked that the agent
obeyed. Measured 2026-09-06: 4 of 12 live /opt sessions were unarmed (2 fabrik-lib, 1 /opt,
1 /opt/fabrik). A compact-resumed session never even sees the order — both SessionStart hooks
skip `source=compact` by design. An unarmed pane that dies mid-stream waits for a human "proceed"
(the 2026-09-03 class, 3 of 4 unarmed sessions that day).

This asks the one thing that is true or false. `claude-selfwatch.sh` holds a `flock` on
`<lockdir>/<safe-sid>.selfwatch.lock` for its whole life (its lines 25-29), so HELD means ARMED.
No registry, no pgrep (a name match returns the caller's own wrapper — measured today), no
guessing. Unarmed → print the arm order with the LITERAL sid, every prompt, until it is armed.
Armed → silent. Same gates as the SessionStart order EXCEPT compact, which is the whole point:
real sid · not headless · an /opt tree (the /tmp one-shot helpers have no pane) · watch script
present. FAIL-OPEN: any exception → silent exit 0; a check must never block a prompt.
"""

from __future__ import annotations

import fcntl
import json
import os
import sys
from pathlib import Path

WATCH = Path.home() / ".claude" / "bin" / "claude-selfwatch.sh"


def _safe(sid: str) -> str:
    # the watcher's own transform: tr -c 'A-Za-z0-9_-' '_' | head -c 64
    return "".join(c if (c.isalnum() or c in "_-") else "_" for c in sid)[:64]


def _armed(sid: str) -> bool:
    locks = Path(os.environ.get("CLAUDE_SOUND_LOCKDIR") or f"/tmp/claude-sound-locks-{os.getuid()}")
    path = locks / f"{_safe(sid)}.selfwatch.lock"
    if not path.exists():
        return False
    # O_APPEND, never truncate: the watcher's fd 9 points at this inode.
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True  # somebody holds it → the standing watch is alive
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False  # nobody holds it → a stale file, not an arm
    finally:
        os.close(fd)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        sid = str(payload.get("session_id") or "")
        cwd = str(payload.get("cwd") or os.getcwd())
        if (
            not sid
            or os.environ.get("CLAUDE_MESH_HEADLESS") == "1"
            or not (cwd == "/opt" or cwd.startswith("/opt/"))
            or not WATCH.is_file()
        ):
            return 0
        if _armed(sid):
            return 0
        print(
            "## ⚠️ SELF-WATCH NOT ARMED (mechanical check, every prompt)\n"
            f"No process holds this session's `selfwatch.lock`, so a mid-stream death would wait "
            "for a human \"proceed\". ARM IT NOW — one persistent Monitor, then this notice stops:\n"
            f'`Monitor(persistent: true, command: "bash {WATCH} {sid}", '
            'description: "resume-mesh self-watch")`\n'
            "(The literal sid above is required — an empty arg exits the watch as you arm it. "
            "Never a `nohup … &` arm. Authority: docs/workstation/hooks-index.md.)"
        )
    except Exception:  # noqa: BLE001 — fail-open by contract
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
