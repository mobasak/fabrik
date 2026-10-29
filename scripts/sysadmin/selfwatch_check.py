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
`<lockdir>/<safe-sid>.selfwatch.lock` for its whole life (its lines 30-37), so HELD means ARMED.
No registry, no pgrep (a name match returns the caller's own wrapper — measured today), no
guessing. Unarmed → print the arm order with the LITERAL sid, every prompt, until it is armed.
Armed → silent. Same gates as the SessionStart order EXCEPT compact, which is the whole point:
real sid · not headless · an /opt tree (the /tmp one-shot helpers have no pane) · watch script
present. FAIL-OPEN: any exception → silent exit 0; a check must never block a prompt.

It also says, before the arm order, when this window's hooks load from ANOTHER worktree than the one it works in
(`_project_dir_order`, W-456aa02a): CLAUDE_PROJECT_DIR is the folder the window was launched in and survives a move
into another worktree, so a pane launched in a stale tree runs that tree's hooks. Running here — user level, from the
hub's main checkout — is what lets it reach exactly the window whose own hook copies are the stale ones.
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import shlex
import stat
import subprocess
import sys
import time
from pathlib import Path

WATCH = Path.home() / ".claude" / "bin" / "claude-selfwatch.sh"
# ONE notion of where the hub lives (`FABRIK_HUB_ROOT`, trailing slash tolerated): the arm scripts,
# the whoami resolver and the kaizen cwd gate all derive from it, so a relocated hub cannot be
# recognised by one and pointed at the wrong path by another (review pass 1, D-S4/D-S5/D-S6/C-S5)
HUB_ROOT = (os.environ.get("FABRIK_HUB_ROOT") or "/opt/fabrik").rstrip("/") or "/opt/fabrik"
ARM = f"{HUB_ROOT}/scripts/sysadmin/selfwatch_arm.sh"  # runs WATCH as one background Bash task (D-356)
# The fourth hub agent's second watch (kaizen, 2026-10-06): the feedback loop's owner is woken when a
# command-feedback queue rises or mail addressed to it lands. Same shape, its own lock suffix. It
# needs NO self-watch binary — its order is evaluated before the self-watch's own gates.
FEEDBACK_ARM = f"{HUB_ROOT}/scripts/sysadmin/feedback_watch_arm.sh"
FEEDBACK_AGENT = "kaizen"


def _safe(sid: str) -> str:
    """The watcher's own transform, BYTE for byte: `tr -c 'A-Za-z0-9_-' '_' | head -c 64` maps every
    non-matching BYTE to `_` and cuts at 64 BYTES (review B12: a char-wise copy diverged on
    non-ASCII; sids are UUIDs today, the mirror is exact anyway)."""
    out = bytearray()
    for b in sid.encode("utf-8", "surrogateescape"):  # a non-UTF-8 name must not raise (R3)
        out.append(b if (chr(b).isalnum() and b < 128) or b in b"_-" else ord("_"))
    return out[:64].decode("ascii")


def _lock_dir() -> Path:
    return Path(os.environ.get("CLAUDE_SOUND_LOCKDIR") or f"/tmp/claude-sound-locks-{os.getuid()}")


def _held_per_proc_locks(st: os.stat_result) -> bool:
    """POSITIVE-ONLY read-only probe: `/proc/locks` lists `… FLOCK ADVISORY WRITE <pid>
    <maj>:<min>:<ino> …` — but it OMITS a lock whose creating task has exited, and the watcher
    arms with `exec 9>lock; flock -n 9` (flock(1) takes the lock and exits; the shell keeps the
    fd). So an absence here proves nothing (review P2-1: every armed window got the arm order on
    every prompt); a presence is authoritative."""
    try:
        text = Path("/proc/locks").read_text()
    except OSError:
        return False
    maj, mnr = os.major(st.st_dev), os.minor(st.st_dev)
    want = f"{maj:02x}:{mnr:02x}:{st.st_ino}"
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[1] == "FLOCK" and parts[5] == want:
            return True
    return False


def _agent_name() -> str:
    """`CLAUDE_AGENT` when set, else the whoami binding for this process's session — the hub's
    resolver, imported by path; "" on any failure (a check must never block a prompt)."""
    env = (os.environ.get("CLAUDE_AGENT") or "").strip()
    if env:
        return env
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "_selfwatch_whoami", f"{HUB_ROOT}/scripts/whoami_agent.py"
        )
        if spec is None or spec.loader is None:
            return ""
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return str(mod.resolve_agent_name() or "")
    except Exception:
        return ""


def _in_hub(cwd: str) -> bool:
    """The hub's main checkout or one of its linked worktrees — the only trees whose kaizen window
    watches the box-global feedback ledger (a project window named kaizen is not the hub's)."""
    cwd = cwd.rstrip("/") or "/"
    return cwd == HUB_ROOT or cwd.startswith(HUB_ROOT + "/")


def _feedback_order(sid: str, cwd: str) -> str:
    """The feedback-watch arm order for a kaizen window in the hub whose feedbackwatch lock is free;
    "" for every other window. Evaluated BEFORE the self-watch's own early return, because an armed
    self-watch is the normal state of a live window (design critique, Opus #6)."""
    if _agent_name() != FEEDBACK_AGENT or not _in_hub(cwd):
        return ""
    if _armed(sid, "feedbackwatch"):
        return ""
    return (
        "## ⚠️ FEEDBACK WATCH NOT ARMED (kaizen window, mechanical check)\n"
        "No process holds this session's `feedbackwatch.lock`, so a queue that rises or mail "
        "addressed to you lands unseen until your next prompt. ARM IT NOW — one background Bash "
        "task; once the lock is held this notice stops:\n"
        f'`Bash(run_in_background: true, command: "bash {FEEDBACK_ARM} {_safe(sid)}")`\n'
        "(ONE wake per arm: its wake line names the `/fabrik-command-improve <cmd>` or the mail id "
        "to claim — act on it, then re-arm. Authority: docs/workstation/hooks-index.md.)\n"
    )


# W-456aa02a — a window's hooks, settings and permissions load from CLAUDE_PROJECT_DIR, the folder it was LAUNCHED in,
# and Claude Code keeps that folder after the session moves into another worktree (infra's window ran a tree 1602
# commits behind the one it worked in, unseen, for days). This hook is registered at user level and runs from the hub's
# main checkout for every window, so a stale tree's own hook copies can never silence the notice. The whole check gets
# one deadline, under the registration's 10 s timeout, so the self-watch order after it still prints. Cobra (D-253):
# the cheapest silence is to `cd` back into the stale launch tree (the trees then match while the hooks stay stale) —
# the notice forbids it, and `agents_up.sh --print` still flags such a pane's start folder.
_TREE_BUDGET_S = 4.0
_GIT_ENV_DROP = ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")


def _git_tree(path: str, deadline: float) -> tuple[str, str, str] | None:
    """(toplevel, common dir, git dir) of the tree holding `path`, every path real and absolute; None on any failure.
    Inherited GIT_* location variables are dropped, so a hook's or an IDE's GIT_DIR cannot answer for another tree."""
    left = deadline - time.monotonic()
    if left <= 0:
        return None
    env = {k: v for k, v in os.environ.items() if k not in _GIT_ENV_DROP}
    done = subprocess.run(
        [
            "git",
            "rev-parse",
            "--path-format=absolute",
            "--show-toplevel",
            "--git-common-dir",
            "--git-dir",
        ],
        cwd=path,
        env=env,
        capture_output=True,
        text=True,
        timeout=left,
    )
    lines = done.stdout.splitlines()
    if done.returncode != 0 or len(lines) != 3:
        return None
    top, common, gitdir = (os.path.realpath(ln) for ln in lines)
    return top, common, gitdir


def _project_dir_order(sid: str, cwd: str) -> str:
    """The notice for a window whose hooks load from ANOTHER linked worktree of the repo it works in; "" otherwise.
    Never raises: any failure is one stderr line and silence, so the self-watch order after it still prints."""
    try:
        proj = (os.environ.get("CLAUDE_PROJECT_DIR") or "").strip()
        if not proj or os.path.realpath(proj) == os.path.realpath(cwd):
            return ""
        deadline = time.monotonic() + _TREE_BUDGET_S
        p, c = _git_tree(proj, deadline), _git_tree(cwd, deadline)
        if p is None or c is None or p[1] != c[1] or p[0] == c[0]:
            return ""  # unreadable, another repo, or the same tree
        if p[2] == p[1]:
            return ""  # launched in the main checkout: its hooks are the repo's own
        main = os.path.dirname(c[1])  # the common dir of a non-bare repo is `<main>/.git`
        if c[0] != main and os.path.dirname(c[0]) != os.path.join(main, ".claude", "worktrees"):
            return ""  # a probe worktree elsewhere: no pane works there, so no relaunch applies
        env = {k: v for k, v in os.environ.items() if k not in _GIT_ENV_DROP}
        short = _git_out(["rev-parse", "--short", "HEAD"], p[0], env, deadline)
        theirs = _git_out(["rev-parse", "HEAD"], c[0], env, deadline)
        counts = _git_out(
            ["rev-list", "--left-right", "--count", f"HEAD...{theirs}"], p[0], env, deadline
        )
        behind, ahead = (
            counts.split()
        )  # left = only in the launch tree, right = only in the tree worked in
        cfg = (os.environ.get("CLAUDE_CONFIG_DIR") or "").strip()
        agent = (os.environ.get("CLAUDE_AGENT") or "").strip()
        q = shlex.quote  # every value reaches a command line the agent is told to run
        launch = (
            f"cd {q(c[0])} && "
            + (f"CLAUDE_CONFIG_DIR={q(cfg)} " if cfg else "")
            + "claude "
            + (f"-n {q(agent)} " if agent else "")
            + f"--resume {q(sid)}"
        )
        return (
            "## ⚠️ HOOKS LOAD FROM ANOTHER TREE (mechanical check, every prompt)\n"
            f"This window's hooks, settings and permissions load from `{p[0]}` (the folder it was launched in, "
            f"CLAUDE_PROJECT_DIR), but you work in `{c[0]}`. That tree is at {short}: your tree has "
            f"{ahead} commit(s) it lacks, and it has {behind} yours lacks — a hook or settings fix in your tree does "
            "not run for you.\n"
            "Tell your coordinator ONCE (it relaunches you at the next rotation; `agents_up.sh` starts a builder in "
            f"the worktree its session lives in). Never `cd` back into `{p[0]}` to silence this — that keeps the stale "
            f"hooks. A hand relaunch: `{launch}`.\n"
        )
    except Exception as exc:  # noqa: BLE001 — fail-open by contract, but never SILENT (B4)
        print(
            f"selfwatch_check: tree notice skipped — {type(exc).__name__}: {exc}", file=sys.stderr
        )
        return ""


def _git_out(args: list[str], tree: str, env: dict[str, str], deadline: float) -> str:
    """One git answer from `tree` inside the shared deadline; raises when git cannot say or the deadline has passed
    (the caller turns that into silence)."""
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError("the tree check's deadline passed")
    done = subprocess.run(
        ["git", *args], cwd=tree, env=env, capture_output=True, text=True, check=True, timeout=left
    )
    return done.stdout.strip()


def _armed(sid: str, suffix: str = "selfwatch") -> bool:
    path = _lock_dir() / f"{_safe(sid)}.{suffix}.lock"
    # ONE open decides the type and probes the lock: a check by path then an open by path could
    # meet a FIFO swapped in between and block forever — the Stop hook's quota checkpoint reads
    # this decider too (W-117b1916 review). O_NONBLOCK makes a FIFO open return at once and
    # O_NOFOLLOW refuses a symlink; the watcher's lock is a plain regular file.
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except FileNotFoundError:
        return False
    except PermissionError:
        # a lock this reader may not open: /proc/locks still answers by inode with no open at all
        st = os.lstat(path)
        if stat.S_ISREG(st.st_mode) and _held_per_proc_locks(st):
            return True
        raise
    except OSError as e:
        if e.errno == errno.ELOOP:
            return False
        raise
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return False
        if _held_per_proc_locks(st):
            return True
        # The decider: a non-blocking SHARED flock probe. A held exclusive lock (the watcher's)
        # refuses it at once; a shared probe never blocks a reader and is released within
        # microseconds, so it cannot hand the watcher's own `flock -n` a false "already armed" the
        # way an exclusive probe could (B6). O_RDONLY — flock needs no write access, and O_WRONLY
        # raised on a read-only lock file, which a bare except then swallowed into silence (B4).
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def _headless() -> bool:
    # headless: the reviver sets CLAUDE_MESH_HEADLESS, the declared spawners set FABRIK_HEADLESS —
    # a `claude -p` worker HAS Monitor unless `--tools` removes it, and obeying the order burns
    # its timeout (intel, 01M3C9BH)
    return (
        os.environ.get("CLAUDE_MESH_HEADLESS") == "1"
        or os.environ.get("FABRIK_HEADLESS") == "1"
        or os.environ.get("CLAUDE_MESH_AUTONOMOUS") == "1"
    )


def arm_state(sid: str, cwd: str) -> str:
    """The ONE self-watch decision, shared by this prompt notice and the quota checkpoint's Stop
    (`.claude/hooks/final_gate_stop.py::_arm_order`, W-117b1916): `"skip"` (no sid, headless or
    autonomous, a cwd outside /opt, or no watcher binary — no order is ever owed), `"armed"` (a
    process holds the lock), `"unwritable:<what>"` (an order would die at once — say what is
    wrong instead) or `"arm"` (order the arm). Raises on a probe failure; callers fail open."""
    if not sid or _headless():
        return "skip"
    # `SELFWATCH_OPT_ROOT` is a TEST seam only (the Stop hook's suites build their project in
    # a temp dir); unset, the gate is the box's `/opt` tree exactly as before
    opt = (os.environ.get("SELFWATCH_OPT_ROOT") or "/opt").rstrip("/") or "/opt"
    if not (cwd == opt or cwd.startswith(opt + "/")) or not WATCH.is_file():
        return "skip"
    if _armed(sid):
        return "armed"
    locks = _lock_dir()
    lock = locks / f"{_safe(sid)}.selfwatch.lock"
    if locks.exists() and not os.access(locks, os.W_OK):
        return f"unwritable:lock DIR `{locks}`"
    if lock.is_symlink() or (lock.exists() and not lock.is_file()):
        return f"unwritable:lock FILE `{lock}` (not a regular file)"
    if lock.exists() and not os.access(lock, os.W_OK):
        return f"unwritable:lock FILE `{lock}`"
    return "arm"


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        sid = str(payload.get("session_id") or "")
        cwd = str(payload.get("cwd") or os.getcwd())
        if not sid or _headless():
            return 0
        # the kaizen feedback-watch order first: it is gated on the HUB tree (`_in_hub`), never on
        # the `/opt` prefix or the self-watch binary below, which belong to the self-watch alone
        # (review pass 1, A-S1/A-S2/D-S4)
        order = _feedback_order(sid, cwd)
        if order:
            print(order)
        # the tree notice shares only the real-sid and not-headless gates above — not the `/opt` prefix or the watch
        # binary (a project window elsewhere has the same defect) — and never raises, so the self-watch order below
        # still prints (W-456aa02a)
        tree = _project_dir_order(sid, cwd)
        if tree:
            print(tree)
        state = arm_state(sid, cwd)
        if state in ("skip", "armed"):
            return 0
        if state.startswith("unwritable:"):
            unwritable = state.split(":", 1)[1]
            # B5/P2-10: the watcher opens its lock with `exec 9>"$lock"`, which fails on an
            # unwritable dir AND on an unwritable file — ordering an arm here loops forever
            # ("arm → dies → arm"). Say what is actually wrong.
            print(
                "## ⚠️ SELF-WATCH CANNOT ARM — not writable\n"
                f"The {unwritable} is not writable by this user, so `claude-selfwatch.sh` exits "
                "at once (its line 30) and an arm order would never stop this notice. Fix the "
                "permissions/ownership, then arm.\n"
            )
            return 0
        print(
            "## ⚠️ SELF-WATCH NOT ARMED (mechanical check, every prompt)\n"
            "No process holds this session's `selfwatch.lock`, so a mid-stream death would wait "
            'for a human "proceed". ARM IT NOW — one background Bash task; once the lock is held '
            "this notice stops:\n"
            f'`Bash(run_in_background: true, command: "bash {ARM} {_safe(sid)}")`\n'
            "(The literal sid above is required — an empty arg exits the watch as you arm it. ONE "
            "wake per arm (D-356): after a wake this notice returns — re-arm. Never a Monitor arm "
            "(it ends within 30 minutes) and never a `nohup … &` arm. Authority: "
            "docs/workstation/hooks-index.md.)"
        )
    except Exception as exc:  # noqa: BLE001 — fail-open by contract, but never SILENT (B4)
        print(f"selfwatch_check: skipped — {type(exc).__name__}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
