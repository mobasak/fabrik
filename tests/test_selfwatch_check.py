"""Behavior Contract — `scripts/sysadmin/selfwatch_check.py`, the mechanical half of the self-watch.

The arm has always been an ORDER printed at SessionStart (`session_orient.py` in synced repos,
`claude_selfwatch_orient.sh` elsewhere) and nothing ever checked that the agent obeyed. Measured
2026-09-06: 4 of 12 live /opt sessions unarmed (2 fabrik-lib, 1 /opt, 1 /opt/fabrik) — and a
compact-resumed session never even sees the order (both hooks skip `source=compact` by design).
An unarmed pane that dies mid-stream waits for a human "proceed" (the 2026-09-03 class, 3 of 4).

This hook runs on EVERY prompt at user level (all windows, every project, fabrik-lib included)
and asks the one thing that is true or false: is the per-sid `selfwatch.lock` HELD? The watcher
holds a `flock` on it for its whole life (`claude-selfwatch.sh:30-34`), so "held" IS "armed" —
no registry, no pgrep, no guessing from process names.
"""

from __future__ import annotations

import fcntl
import importlib.util as _ilu
import json
import os
import subprocess
import sys
import time
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
    e.pop("FABRIK_HEADLESS", None)
    # the kaizen window runs this suite too: its CLAUDE_AGENT would print the feedback-watch
    # order and fail the "armed is silent" grader there alone (design critique, Fable #3)
    e.pop("CLAUDE_AGENT", None)
    # a window launched in another tree would print the tree notice into every other grader (W-456aa02a)
    e.pop("CLAUDE_PROJECT_DIR", None)
    (tmp_path / "identity.jsonl").write_text("")
    e["AGENT_IDENTITY_FILE"] = str(tmp_path / "identity.jsonl")
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
    assert (
        "selfwatch_arm.sh" in out
        and "Bash(run_in_background: true" in out
        and "Monitor(" not in out
    )


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
    # the declared headless spawners set FABRIK_HEADLESS alone (intel, 01M3C9BH)
    assert _run(tmp_path, FABRIK_HEADLESS="1") == "", "FABRIK_HEADLESS is headless too"
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
        assert "run_in_background" not in out, "must not order an arm that will die at once"
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
    (not HEADLESS) from /opt cwds — a headless worker has no pane to wake, so the order is noise
    per prompt (and with tools on it obeys and re-arms until its timeout)."""
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


def test_the_printed_arm_order_carries_the_sanitized_sid(tmp_path):
    """Review of D-356, B-H2/A-S3: the order is a command the agent RUNS; the sid goes in through the
    watcher's own transform, never raw from the payload (the two orient hooks already sanitize)."""
    out = _run(tmp_path, sid="ab c;touch x")
    assert "selfwatch_arm.sh ab_c_touch_x" in out, out
    assert "touch x" not in out


def test_the_notice_text_is_unchanged(tmp_path):
    """W-117b1916: `arm_state` moved main's gates; main's arm notice must stay BYTE-identical."""
    out = _run(tmp_path)
    arm = f"{_selfwatch.HUB_ROOT}/scripts/sysadmin/selfwatch_arm.sh"
    assert out == (
        "## ⚠️ SELF-WATCH NOT ARMED (mechanical check, every prompt)\n"
        "No process holds this session's `selfwatch.lock`, so a mid-stream death would wait "
        'for a human "proceed". ARM IT NOW — one background Bash task; once the lock is held '
        "this notice stops:\n"
        f'`Bash(run_in_background: true, command: "bash {arm} {SID}")`\n'
        "(The literal sid above is required — an empty arg exits the watch as you arm it. ONE "
        "wake per arm (D-356): after a wake this notice returns — re-arm. Never a Monitor arm "
        "(it ends within 30 minutes) and never a `nohup … &` arm. Authority: "
        "docs/workstation/hooks-index.md.)\n"
    )


def test_arm_state_matches_the_notice_gates(tmp_path, monkeypatch):
    """W-117b1916: the Stop checkpoint reads the SAME decision the prompt notice prints from."""
    locks = tmp_path / "locks"
    locks.mkdir()
    watch = tmp_path / "claude-selfwatch.sh"
    watch.write_text("#!/bin/sh\n")
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(locks))
    for k in ("CLAUDE_MESH_HEADLESS", "FABRIK_HEADLESS", "CLAUDE_MESH_AUTONOMOUS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(_selfwatch, "WATCH", watch)
    state = _selfwatch.arm_state
    assert state(SID, "/opt/x") == "arm"
    assert state("", "/opt/x") == "skip"
    assert state(SID, "/home/x") == "skip"
    monkeypatch.setenv("FABRIK_HEADLESS", "1")
    assert state(SID, "/opt/x") == "skip"
    monkeypatch.delenv("FABRIK_HEADLESS")
    fd = _hold_lock(tmp_path)
    try:
        assert state(SID, "/opt/x") == "armed"
    finally:
        os.close(fd)
    os.chmod(locks, 0o500)
    try:
        assert state(SID, "/opt/x").startswith("unwritable:lock ")
    finally:
        os.chmod(locks, 0o700)
    monkeypatch.setattr(_selfwatch, "WATCH", tmp_path / "absent")
    assert state(SID, "/opt/x") == "skip"


def test_a_fifo_at_the_lock_path_never_hangs_the_decision(tmp_path):
    """W-117b1916 review: the Stop hook reads this decider too — a FIFO at the lock path blocked the
    O_RDONLY open forever. A non-regular lock is not armed, and no arm is ordered onto it."""
    locks = tmp_path / "locks"
    locks.mkdir()
    os.mkfifo(locks / f"{SID}.selfwatch.lock")
    watch = tmp_path / "w.sh"
    watch.write_text("#!/bin/sh\n")
    code = (
        "import importlib.util as u,sys;"
        f"s=u.spec_from_file_location('m',{str(HOOK)!r});m=u.module_from_spec(s);s.loader.exec_module(m);"
        f"from pathlib import Path;m.WATCH=Path({str(watch)!r});"
        f"print(m.arm_state({SID!r},'/opt/x'))"
    )
    env = {**os.environ, "CLAUDE_SOUND_LOCKDIR": str(locks)}
    for k in ("CLAUDE_MESH_HEADLESS", "FABRIK_HEADLESS", "CLAUDE_MESH_AUTONOMOUS"):
        env.pop(k, None)
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=20, env=env
    ).stdout.strip()
    assert out.startswith("unwritable:") and "not a regular file" in out, out


def test_a_fifo_swapped_in_after_the_type_check_never_hangs(tmp_path, monkeypatch):
    """Round-2 review N3: the type check and the open must be ONE operation — a check by path
    (`lstat`) that reads a regular file, then an open that meets a FIFO, blocked forever."""
    import threading

    spec = _ilu.spec_from_file_location("swc_n3", HOOK)
    m = _ilu.module_from_spec(spec)
    spec.loader.exec_module(m)
    locks = tmp_path / "locks"
    locks.mkdir()
    fifo = locks / f"{SID}.selfwatch.lock"
    os.mkfifo(fifo)
    regular = tmp_path / "regular"
    regular.write_text("")
    real_lstat = os.lstat
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(locks))
    monkeypatch.setattr(
        os,
        "lstat",
        lambda p, *a, **k: real_lstat(regular) if str(p) == str(fifo) else real_lstat(p, *a, **k),
    )
    got: list[bool] = []
    t = threading.Thread(target=lambda: got.append(m._armed(SID)), daemon=True)
    t.start()
    t.join(5)
    if t.is_alive():  # release the hung reader so the suite can continue
        os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
        t.join(5)
        raise AssertionError("_armed hung on a FIFO that appeared after its type check")
    assert got == [False]


def test_a_held_lock_without_read_permission_still_reads_armed(tmp_path, monkeypatch):
    """Round-3 review: HEAD found a held lock in /proc/locks before any open, so a lock its reader
    may not open still read armed; the one-open decider must keep that verdict, not raise."""
    if os.geteuid() == 0:
        import pytest

        pytest.skip("root opens a 0000 file")
    spec = _ilu.spec_from_file_location("swc_r3", HOOK)
    m = _ilu.module_from_spec(spec)
    spec.loader.exec_module(m)
    locks = tmp_path / "locks"
    locks.mkdir()
    lock = locks / f"{SID}.selfwatch.lock"
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock.chmod(0)
        monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(locks))
        assert m._armed(SID) is True
    finally:
        lock.chmod(0o644)
        os.close(fd)


# --- W-456aa02a: the window whose hooks load from another tree is told so, every prompt ----------------------------
# Claude Code keeps the folder a window was LAUNCHED in as its project folder (CLAUDE_PROJECT_DIR: hooks, settings,
# permissions) after the session moves into another worktree. infra's window ran `worktrees/infra`'s hooks, 1602
# commits behind the tree it worked in, for days, and nothing said so. This hook runs from the hub's main checkout at
# user level for every window, so a stale tree's own copies can never silence it.

TREE_NOTICE = "## ⚠️ HOOKS LOAD FROM ANOTHER TREE"


def _git(*args: str, cwd: Path) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _trees(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    """A main checkout with two linked worktrees under `.claude/worktrees/`: `stale` at the first commit, `work` two
    commits ahead of it. Returns (main, stale, work, stale's short sha)."""
    main = (tmp_path / "repo").resolve()
    main.mkdir()
    _git("init", "-q", cwd=main)
    _git("commit", "-q", "--allow-empty", "-m", "one", cwd=main)
    stale_sha = _git("rev-parse", "--short", "HEAD", cwd=main)
    wts = main / ".claude" / "worktrees"
    _git("worktree", "add", "-q", "--detach", str(wts / "stale"), cwd=main)
    _git("worktree", "add", "-q", "-b", "w", str(wts / "work"), cwd=main)
    work = wts / "work"
    _git("commit", "-q", "--allow-empty", "-m", "two", cwd=work)
    _git("commit", "-q", "--allow-empty", "-m", "three", cwd=work)
    return main, wts / "stale", work, stale_sha


def test_hooks_from_another_tree_are_said(tmp_path):
    """B5: a cwd in one linked worktree with CLAUDE_PROJECT_DIR another of the same repo → the notice names the tree the
    hooks load from, the tree worked in, the stale tree's head and both counts, and the remedy the reader can act on;
    an inherited GIT_DIR (a hook or IDE env) never redirects the decision."""
    _main, stale, work, sha = _trees(tmp_path)
    for extra in ({}, {"GIT_DIR": str(_main / ".git")}):
        out = _run(tmp_path, cwd=str(work), CLAUDE_PROJECT_DIR=str(stale), **extra)
        assert TREE_NOTICE in out, (extra, out)
        assert f"load from `{stale}`" in out and f"you work in `{work}`" in out, out
        assert f"at {sha}" in out, out
        assert "your tree has 2 commit(s) it lacks, and it has 0 yours lacks" in out, out
        assert "Tell your coordinator ONCE" in out and "Never `cd` back" in out, out
        assert f"--resume {SID}" in out, out
    # the hand relaunch carries the config dir and the agent name when this window has them
    out = _run(
        tmp_path,
        cwd=str(work),
        CLAUDE_PROJECT_DIR=str(stale),
        CLAUDE_CONFIG_DIR="/cfg",
        CLAUDE_AGENT="infra",
    )
    assert f"cd {work} && CLAUDE_CONFIG_DIR=/cfg claude -n infra --resume {SID}" in out, out
    # …each value shell-quoted, so a space or a metacharacter never splits or runs the line the agent is told to run
    out = _run(
        tmp_path,
        cwd=str(work),
        CLAUDE_PROJECT_DIR=str(stale),
        CLAUDE_CONFIG_DIR="/c f g;x",
    )
    assert "CLAUDE_CONFIG_DIR='/c f g;x' claude --resume" in out, out
    # a window working in the MAIN checkout while launched in a stale linked worktree is told too
    out = _run(tmp_path, cwd=str(_main), CLAUDE_PROJECT_DIR=str(stale))
    assert TREE_NOTICE in out and f"you work in `{_main}`" in out, out


def test_hooks_from_the_same_tree_say_nothing(tmp_path):
    """B6: no notice when the trees match (a trailing slash or a symlink to the same tree included), when the window
    was launched in the main checkout, across two repos, with no CLAUDE_PROJECT_DIR, or when the tree worked in is a
    probe worktree outside `.claude/worktrees/`."""
    main, stale, work, _sha = _trees(tmp_path)
    link = tmp_path / "link-to-work"
    link.symlink_to(work)
    other = (tmp_path / "other").resolve()
    other.mkdir()
    _git("init", "-q", cwd=other)
    _git("commit", "-q", "--allow-empty", "-m", "x", cwd=other)
    probe = (tmp_path / "probe").resolve()
    _git("worktree", "add", "-q", "--detach", str(probe), cwd=main)
    cases = {
        "same tree, trailing slash": (str(work), str(work) + "/"),
        "same tree, via a symlink": (str(work), str(link)),
        "a subfolder of the same tree": (str(work / ".claude"), str(work)),
        "launched in the main checkout": (str(work), str(main)),
        "another repo": (str(work), str(other)),
        "a probe tree outside worktrees/": (str(probe), str(stale)),
    }
    (work / ".claude").mkdir(exist_ok=True)
    for why, (cwd, proj) in cases.items():
        assert TREE_NOTICE not in _run(tmp_path, cwd=cwd, CLAUDE_PROJECT_DIR=proj), why
    assert TREE_NOTICE not in _run(tmp_path, cwd=str(work)), "unset"
    # a LINKED worktree of another repo is decided as another repo up front — never by a cross-repo git error
    other_wt = other / ".claude" / "worktrees" / "x"
    _git("worktree", "add", "-q", "--detach", str(other_wt), cwd=other)
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_AGENT")}
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"session_id": SID, "cwd": str(work)}),
        capture_output=True,
        text=True,
        timeout=30,
        env={
            **env,
            "CLAUDE_PROJECT_DIR": str(other_wt),
            "CLAUDE_SOUND_LOCKDIR": str(tmp_path / "locks"),
        },
    )
    assert TREE_NOTICE not in proc.stdout and "tree notice skipped" not in proc.stderr, (
        proc.stdout,
        proc.stderr,
    )


def test_the_tree_notice_does_not_wait_for_the_self_watch(tmp_path):
    """B7: the notice prints before, and beside, an unarmed self-watch's arm order; and a guard that cannot run git
    (git missing from PATH) is silent while the self-watch order still prints — the guard never costs the window its
    arm order; a git that hangs costs at most the guard's one budget, well inside the hook's 10 s registration, and
    the arm order still prints."""
    _main, stale, work, _sha = _trees(tmp_path)
    # a HOME of the test's own holding the watch binary, so the arm order never depends on this box's ~/.claude
    home = tmp_path / "home"
    (home / ".claude" / "bin").mkdir(parents=True)
    (home / ".claude" / "bin" / "claude-selfwatch.sh").write_text("#!/bin/sh\n")
    opt = {"SELFWATCH_OPT_ROOT": str(tmp_path), "HOME": str(home)}
    out = _run(tmp_path, cwd=str(work), CLAUDE_PROJECT_DIR=str(stale), **opt)
    assert TREE_NOTICE in out and "SELF-WATCH NOT ARMED" in out, out
    assert out.index(TREE_NOTICE) < out.index("SELF-WATCH NOT ARMED"), out
    nogit = tmp_path / "nogit"
    nogit.mkdir()
    out = _run(tmp_path, cwd=str(work), CLAUDE_PROJECT_DIR=str(stale), PATH=str(nogit), **opt)
    assert TREE_NOTICE not in out and "SELF-WATCH NOT ARMED" in out, out
    hung = tmp_path / "hung"
    hung.mkdir()
    (hung / "git").write_text(f"#!{sys.executable}\nimport time\ntime.sleep(30)\n")
    (hung / "git").chmod(0o755)
    t0 = time.monotonic()
    out = _run(tmp_path, cwd=str(work), CLAUDE_PROJECT_DIR=str(stale), PATH=str(hung), **opt)
    took = time.monotonic() - t0
    assert TREE_NOTICE not in out and "SELF-WATCH NOT ARMED" in out, out
    assert took < _selfwatch._TREE_BUDGET_S + 3 < 10, took


# ── the coordinator's builder watch (W-c814836f) ────────────────────────────────────────────────────────────────────

BUILDER_ORDER = "BUILDER WATCH NOT ARMED"
_FAKE_GRID_TMUX = """#!/usr/bin/env python3
import os, sys
if os.environ.get("FAKE_GRID_FAIL"):
    sys.stderr.write("server exited unexpectedly\\n")
    sys.exit(1)
if sys.argv[1] == "list-panes":
    print(os.environ.get("FAKE_GRID_ROW", ""))
"""


def _coord_repo(
    tmp_path: Path, name: str = "proj", coordinator_mode: bool = False
) -> tuple[Path, Path]:
    """A main checkout (`.git` a directory) and one linked worktree (`.git` a file) under it."""
    main = tmp_path / name
    (main / ".git").mkdir(parents=True)
    (main / ".fabrik" / "work").mkdir(parents=True)
    cfg = {"distributor": "coord", **({"coordinator_mode": True} if coordinator_mode else {})}
    (main / ".fabrik" / "work" / "config.json").write_text(json.dumps(cfg))
    wt = main / ".claude" / "worktrees" / "dev1"
    wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {main}/.git/worktrees/dev1\n")
    return main, wt


def _grid(tmp_path: Path, row: str = "", fail: bool = False) -> dict[str, str]:
    exe = tmp_path / "grid-tmux"
    exe.write_text(_FAKE_GRID_TMUX)
    exe.chmod(0o755)
    env = {"ROTATE_TMUX": str(exe), "FAKE_GRID_ROW": row}
    if fail:
        env["FAKE_GRID_FAIL"] = "1"
    return env


def test_builder_watch_order_gates(tmp_path):
    main, wt = _coord_repo(tmp_path)
    builder = "\t".join(("%3", "proj", "proj", "dev1", str(wt)))
    # a window launched in the main checkout of a repo with a live builder grid: ordered, with its sid and repo
    out = _run(tmp_path, cwd=str(main), CLAUDE_PROJECT_DIR=str(main), **_grid(tmp_path, builder))
    assert BUILDER_ORDER in out, out
    assert f"watch_builders.py {SID} {main}" in out and "Bash(run_in_background: true" in out, out
    # the launch folder decides, not cwd: a builder that `cd`s into the main checkout is never ordered …
    assert BUILDER_ORDER not in _run(
        tmp_path, cwd=str(main), CLAUDE_PROJECT_DIR=str(wt), **_grid(tmp_path, builder)
    )
    # … and a coordinator whose cwd moved below its checkout still is (no CLAUDE_PROJECT_DIR: cwd is the launch)
    (main / "src").mkdir()
    assert BUILDER_ORDER in _run(tmp_path, cwd=str(main / "src"), **_grid(tmp_path, builder))
    # another repo's grid only, and no coordinator_mode: nothing to watch
    other = "\t".join(("%9", "elsewhere", "", "dev9", "/x/elsewhere"))
    assert BUILDER_ORDER not in _run(
        tmp_path, cwd=str(main), CLAUDE_PROJECT_DIR=str(main), **_grid(tmp_path, other)
    )
    # coordinator_mode alone is enough (its builders may all be down; the watch still reads its mail)
    main2, _ = _coord_repo(tmp_path, "proj2", coordinator_mode=True)
    assert BUILDER_ORDER in _run(
        tmp_path, cwd=str(main2), CLAUDE_PROJECT_DIR=str(main2), **_grid(tmp_path)
    )
    # armed: the watcher's flock on <safe-sid>.builderwatch.lock is held → silent
    fd = os.open(
        str(tmp_path / "locks" / f"{SID}.builderwatch.lock"), os.O_WRONLY | os.O_CREAT, 0o644
    )
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        assert BUILDER_ORDER not in _run(
            tmp_path, cwd=str(main), CLAUDE_PROJECT_DIR=str(main), **_grid(tmp_path, builder)
        )
    finally:
        os.close(fd)


def test_a_failing_builder_check_never_costs_the_self_watch_order(tmp_path):
    main, _wt = _coord_repo(tmp_path)
    home = tmp_path / "home"
    (home / ".claude" / "bin").mkdir(parents=True)
    (home / ".claude" / "bin" / "claude-selfwatch.sh").write_text("#!/bin/sh\n")
    e = {**os.environ, "CLAUDE_SOUND_LOCKDIR": str(tmp_path / "locks"), "HOME": str(home)}
    for k in ("CLAUDE_MESH_HEADLESS", "FABRIK_HEADLESS", "CLAUDE_AGENT"):
        e.pop(k, None)
    (tmp_path / "locks").mkdir(exist_ok=True)
    (tmp_path / "identity.jsonl").write_text("")
    e.update(
        AGENT_IDENTITY_FILE=str(tmp_path / "identity.jsonl"),
        SELFWATCH_OPT_ROOT=str(tmp_path),
        CLAUDE_PROJECT_DIR=str(main),
        **_grid(tmp_path, fail=True),
    )
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(
            {"session_id": SID, "cwd": str(main), "hook_event_name": "UserPromptSubmit"}
        ),
        capture_output=True,
        text=True,
        timeout=30,
        env=e,
    )
    assert proc.returncode == 0, proc.stderr
    assert BUILDER_ORDER not in proc.stdout and "SELF-WATCH NOT ARMED" in proc.stdout, proc.stdout
    assert "builder watch" in proc.stderr and "RuntimeError" in proc.stderr, proc.stderr


def test_the_builder_order_never_prints_a_command_it_cannot_carry(tmp_path):
    """Review B-1, B-2, B-3: a launch folder the shell would mangle, a symlinked launch folder and an unwritable lock
    directory each get the right answer — never an order that breaks or loops."""
    # B-1: a repo path with a double quote or `$` cannot ride inside the order's double-quoted command
    bad, _ = _coord_repo(tmp_path, 'pro"j$x', coordinator_mode=True)
    out = _run(tmp_path, cwd=str(bad), CLAUDE_PROJECT_DIR=str(bad), **_grid(tmp_path))
    assert BUILDER_ORDER not in out and "BUILDER WATCH CANNOT ARM" in out and "path" in out, out
    # B-2: a launch folder reached through a symlink names the REAL checkout, as the watcher does
    real, _ = _coord_repo(tmp_path, "realrepo", coordinator_mode=True)
    link = tmp_path / "linkrepo"
    link.symlink_to(real)
    out = _run(tmp_path, cwd=str(link), CLAUDE_PROJECT_DIR=str(link), **_grid(tmp_path))
    assert BUILDER_ORDER in out and f"watch_builders.py {SID} {real}" in out, out
    # B-3: an unwritable lock directory: the watcher would die at once, so the order would loop — say what is wrong
    locks = tmp_path / "locks"
    locks.mkdir(exist_ok=True)
    locks.chmod(0o555)
    try:
        out = _run(tmp_path, cwd=str(real), CLAUDE_PROJECT_DIR=str(real), **_grid(tmp_path))
    finally:
        locks.chmod(0o755)
    assert (
        BUILDER_ORDER not in out and "BUILDER WATCH CANNOT ARM" in out and "not writable" in out
    ), out


def test_a_gone_launch_folder_or_a_fifo_config_never_misorders_or_hangs(tmp_path):
    """Review Bh-1: a launch folder that no longer exists (a removed worktree) must not climb to the main checkout's
    `.git` and order a builder to arm; Bh-2: a `config.json` that is a FIFO must not hang the hook."""
    main, _wt = _coord_repo(tmp_path, coordinator_mode=True)
    gone = main / ".claude" / "worktrees" / "removed-dev"
    out = _run(tmp_path, cwd=str(main), CLAUDE_PROJECT_DIR=str(gone), **_grid(tmp_path))
    assert BUILDER_ORDER not in out, out
    cfg = main / ".fabrik" / "work" / "config.json"
    cfg.unlink()
    os.mkfifo(cfg)
    t0 = time.monotonic()
    out = _run(tmp_path, cwd=str(main), CLAUDE_PROJECT_DIR=str(main), **_grid(tmp_path))
    assert time.monotonic() - t0 < 8, "a FIFO config must never hang the prompt hook"
    assert BUILDER_ORDER not in out, out  # no config read and no grid: nothing to watch
