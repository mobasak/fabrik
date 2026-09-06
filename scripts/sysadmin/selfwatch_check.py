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
    """The watcher's own transform, BYTE for byte: `tr -c 'A-Za-z0-9_-' '_' | head -c 64` maps every
    non-matching BYTE to `_` and cuts at 64 BYTES (review B12: a char-wise copy diverged on
    non-ASCII; sids are UUIDs today, the mirror is exact anyway)."""
    out = bytearray()
    for b in sid.encode("utf-8"):
        out.append(b if (chr(b).isalnum() and b < 128) or b in b"_-" else ord("_"))
    return out[:64].decode("ascii")


def _lock_dir() -> Path:
    return Path(os.environ.get("CLAUDE_SOUND_LOCKDIR") or f"/tmp/claude-sound-locks-{os.getuid()}")


def _held_per_proc_locks(st: os.stat_result) -> bool | None:
    """READ-ONLY probe (review B6): does any process hold a FLOCK on this inode? `/proc/locks`
    lists `… FLOCK ADVISORY WRITE <pid> <maj>:<min>:<ino> …`. None when unreadable (not Linux,
    hidepid) — the caller falls back to the flock probe, which is racy by nature: taking LOCK_EX
    to ask could make the watcher's own `flock -n` see "already armed" and exit 0."""
    try:
        text = Path("/proc/locks").read_text()
    except OSError:
        return None
    maj, mnr = os.major(st.st_dev), os.minor(st.st_dev)
    want = f"{maj:02x}:{mnr:02x}:{st.st_ino}"
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[1] == "FLOCK" and parts[5] == want:
            return True
    return False


def _armed(sid: str) -> bool:
    path = _lock_dir() / f"{_safe(sid)}.selfwatch.lock"
    if not path.exists():
        return False
    st = os.stat(path)
    held = _held_per_proc_locks(st)
    if held is not None:
        return held
    # Fallback: a non-blocking flock probe. O_RDONLY — flock needs no write access, and O_WRONLY
    # raised on a read-only lock file, which the bare except then swallowed into silence (B4).
    fd = os.open(str(path), os.O_RDONLY)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
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
            or os.environ.get("CLAUDE_MESH_AUTONOMOUS")
            == "1"  # `claude -p` workers: no Monitor tool (B11)
            or not (cwd == "/opt" or cwd.startswith("/opt/"))
            or not WATCH.is_file()
        ):
            return 0
        if _armed(sid):
            return 0
        locks = _lock_dir()
        if locks.exists() and not os.access(locks, os.W_OK):
            # B5: the watcher exits 1 when it cannot open its lock — ordering an arm here loops
            # forever ("arm → dies → arm"). Say what is actually wrong.
            print(
                "## ⚠️ SELF-WATCH CANNOT ARM — LOCK DIR not writable\n"
                f"`{locks}` is not writable by this user, so `claude-selfwatch.sh` exits at once "
                "(its line 25) and an arm order would never stop this notice. Fix the directory "
                "(permissions/ownership), then arm.\n"
            )
            return 0
        print(
            "## ⚠️ SELF-WATCH NOT ARMED (mechanical check, every prompt)\n"
            "No process holds this session's `selfwatch.lock`, so a mid-stream death would wait "
            'for a human "proceed". ARM IT NOW — one persistent Monitor; once the lock is held this '
            "notice stops:\n"
            f'`Monitor(persistent: true, command: "bash {WATCH} {sid}", '
            'description: "resume-mesh self-watch")`\n'
            "(The literal sid above is required — an empty arg exits the watch as you arm it. "
            "Never a `nohup … &` arm. Authority: docs/workstation/hooks-index.md.)"
        )
    except Exception as exc:  # noqa: BLE001 — fail-open by contract, but never SILENT (B4)
        print(f"selfwatch_check: skipped — {type(exc).__name__}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
