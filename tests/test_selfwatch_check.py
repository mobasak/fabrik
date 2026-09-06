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
import importlib.util as _ilu
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "scripts" / "sysadmin" / "selfwatch_check.py"
_spec = _ilu.spec_from_file_location("selfwatch_check", HOOK)
_selfwatch = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_selfwatch)

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


# --- review pass 1 (2026-09-06), Finder B: B4 B5 B6 B7 B11 B12 ----------------------------------


def test_a_read_only_lock_file_is_still_probed(tmp_path):
    """B4: O_WRONLY on a 0400 lock raised, the bare `except: pass` swallowed it, and the check
    said NOTHING forever — the exact failure it was built to end. flock needs no write access."""
    fd = _hold_lock(tmp_path)
    try:
        locks = tmp_path / "locks"
        lock = next(locks.glob("*.selfwatch.lock"))
        lock.chmod(0o400)
        assert _run(tmp_path) == "", "held + read-only must read as ARMED, not as silence-by-crash"
    finally:
        os.close(fd)


def test_an_unwritable_lock_dir_prints_the_diagnosis_not_an_arm_order(tmp_path):
    """B5: the watcher exits 1 when it cannot open the lock; the check kept ordering an arm that
    could never succeed, on every prompt, while promising 'then this notice stops'."""
    locks = tmp_path / "locks"
    locks.mkdir(exist_ok=True)
    locks.chmod(0o500)
    try:
        out = _run(tmp_path)
        assert "lock DIR" in out and "not writable" in out, out
        assert "Monitor(" not in out, "must not order an arm that will die at once"
    finally:
        locks.chmod(0o700)


def test_probe_is_read_only_and_never_races_an_arm(tmp_path):
    """B6: taking LOCK_EX to probe could make a concurrent `flock -n` in the watcher see 'already
    armed' and exit 0 — a prober that mutates what it probes. /proc/locks is consulted first."""
    fd = _hold_lock(tmp_path)
    try:
        locks = tmp_path / "locks"
        lock = next(locks.glob("*.selfwatch.lock"))
        st = os.stat(lock)
        assert _selfwatch._held_per_proc_locks(st) is True
    finally:
        os.close(fd)


def test_cwd_exactly_opt_is_a_pane_too(tmp_path):
    """B7: the `cwd == "/opt"` disjunct had no grader — the exact class that silently dropped 4
    sessions on 2026-08-16 (a /opt/*-only glob)."""
    assert "NOT ARMED" in _run(tmp_path, cwd="/opt")


def test_autonomous_headless_workers_are_silent(tmp_path):
    """B11: ci_fix_dispatcher.py:208 runs `claude -p` under CLAUDE_MESH_AUTONOMOUS=1 (the only producer in a repo-wide grep — review P2-13)
    (not HEADLESS) from /opt cwds — no Monitor tool exists there, the order is noise per prompt."""
    assert _run(tmp_path, CLAUDE_MESH_AUTONOMOUS="1") == ""


def test_safe_sid_mirrors_the_watchers_byte_transform():
    """B12: the watcher's `tr -c … | head -c 64` works on BYTES; a char-wise copy diverged on
    non-ASCII. UUIDs are ASCII today; the mirror must be exact anyway."""
    assert _selfwatch._safe("é" * 40) == "_" * 64  # 2 bytes each → 80 underscores → cut at 64
    assert _selfwatch._safe("abc-DEF_9") == "abc-DEF_9"


def _hold_lock_like_the_watcher(tmp_path: Path, sid: str = SID) -> subprocess.Popen:
    """The REAL arm idiom (`claude-selfwatch.sh`): `exec 9>lock; flock -n 9` — flock(1) takes the
    lock and EXITS, the shell keeps the fd. `/proc/locks` omits a lock whose creating task is
    gone, so a probe that trusts its absence calls an armed session unarmed (review P2-1)."""
    locks = tmp_path / "locks"
    locks.mkdir(exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in sid)[:64]
    lock = locks / f"{safe}.selfwatch.lock"
    proc = subprocess.Popen(
        ["bash", "-c", f'exec 9>"{lock}"; flock -n 9 || exit 3; echo ready; exec sleep 30'],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout.readline().strip() == "ready", "the bash holder did not take the lock"
    return proc


def test_the_watchers_own_flock_idiom_reads_as_armed(tmp_path):
    """P2-1 (CRITICAL): with the lock held exactly as claude-selfwatch.sh holds it, the check
    must be SILENT — the pre-fix probe printed the arm order on every prompt, forever."""
    holder = _hold_lock_like_the_watcher(tmp_path)
    try:
        assert _run(tmp_path) == ""
        # …and a lock file made read-only AFTER the arm is still probed (B4, on the real idiom)
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in SID)[:64]
        (tmp_path / "locks" / f"{safe}.selfwatch.lock").chmod(0o400)
        assert _run(tmp_path) == ""
    finally:
        holder.kill()
        holder.wait()


def test_an_unwritable_lock_file_prints_the_diagnosis_not_an_arm_order(tmp_path):
    """P2-10: the watcher opens `exec 9>"$lock"` — an unwritable FILE kills the arm exactly like
    an unwritable dir; the B5 diagnosis looked at the dir only."""
    locks = tmp_path / "locks"
    locks.mkdir(exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in SID)[:64]
    lock = locks / f"{safe}.selfwatch.lock"
    lock.write_text("")
    lock.chmod(0o400)
    out = _run(tmp_path)
    assert "CANNOT ARM" in out and "lock FILE" in out, out
    assert "ARM IT NOW" not in out
