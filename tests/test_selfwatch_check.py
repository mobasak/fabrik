"""Behavior Contract — `scripts/sysadmin/selfwatch_check.py`, the mechanical half of the self-watch.

The arm has always been an ORDER printed at SessionStart (`session_orient.py` in synced repos,
`claude_selfwatch_orient.sh` elsewhere) and nothing ever checked that the agent obeyed. Measured
2026-09-06: 4 of 12 live /opt sessions unarmed (2 fabrik-lib, 1 /opt, 1 /opt/fabrik) — and a
compact-resumed session never even sees the order (both hooks skip `source=compact` by design).
An unarmed pane that dies mid-stream waits for a human "proceed" (the 2026-09-03 class, 3 of 4).

This hook runs on EVERY prompt at user level (all windows, every project, fabrik-lib included)
and asks the one thing that is true or false: is the per-sid `selfwatch.lock` HELD? The watcher
holds a `flock` on it for its whole life (`claude-selfwatch.sh:25-29`), so "held" IS "armed" —
no registry, no pgrep, no guessing from process names.
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "scripts" / "sysadmin" / "selfwatch_check.py"
SID = "11111111-2222-3333-4444-555555555555"


def _run(tmp_path: Path, cwd: str = "/opt/anything", sid: str = SID, **env: str) -> str:
    locks = tmp_path / "locks"
    locks.mkdir(exist_ok=True)
    e = {**os.environ, "CLAUDE_SOUND_LOCKDIR": str(locks)}
    e.pop("CLAUDE_MESH_HEADLESS", None)  # the box's own env must not decide the test
    e.update(env)  # …but a test that SETS it must win (the first draft popped it after merging)
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"session_id": sid, "cwd": cwd, "hook_event_name": "UserPromptSubmit"}),
        capture_output=True,
        text=True,
        timeout=30,
        env=e,
    )
    assert proc.returncode == 0, (
        f"a check must never block a prompt: rc={proc.returncode} {proc.stderr}"
    )
    return proc.stdout


def _hold_lock(tmp_path: Path, sid: str = SID):
    """Hold the SAME flock the real watcher holds, from a live file descriptor."""
    locks = tmp_path / "locks"
    locks.mkdir(exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in sid)[:64]
    fd = os.open(str(locks / f"{safe}.selfwatch.lock"), os.O_WRONLY | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fd


def test_unarmed_session_gets_the_arm_order_with_its_own_sid(tmp_path):
    out = _run(tmp_path)
    assert "NOT ARMED" in out, out
    assert SID in out, "the order must carry the literal sid — an empty arg exits the watch at once"
    assert "claude-selfwatch.sh" in out and "Monitor(" in out


def test_armed_session_is_silent(tmp_path):
    fd = _hold_lock(tmp_path)
    try:
        assert _run(tmp_path) == "", "a held lock IS an armed watch; nothing to say"
    finally:
        os.close(fd)


def test_a_released_lock_reads_as_unarmed_again(tmp_path):
    """A lock FILE left behind by a dead watcher is not an arm — only a HELD lock is."""
    fd = _hold_lock(tmp_path)
    os.close(fd)  # watcher gone, file remains
    assert "NOT ARMED" in _run(tmp_path)


def test_tmp_helpers_and_headless_and_sidless_are_silent(tmp_path):
    assert _run(tmp_path, cwd="/tmp/vscode-helper") == "", "a /tmp one-shot has no pane to wake"
    assert _run(tmp_path, CLAUDE_MESH_HEADLESS="1") == "", "headless never arms, by design"
    assert _run(tmp_path, sid="") == ""


def test_compact_resume_is_not_exempt(tmp_path):
    """The whole point: SessionStart orders skip source=compact, so this per-prompt check must
    not. A payload carrying source=compact still gets the order when unarmed."""
    locks = tmp_path / "locks"
    locks.mkdir(exist_ok=True)
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"session_id": SID, "cwd": "/opt/x", "source": "compact"}),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "CLAUDE_SOUND_LOCKDIR": str(locks)},
    )
    assert "NOT ARMED" in proc.stdout
