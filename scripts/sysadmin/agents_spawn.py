#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/repo-coordinator-rollout.md | tests/test_agents_spawn.py
"""agents_spawn — spawn one builder into a repo: `agents_up.sh add <repo> <name> [--role R] [--item W-id]`.

W-b9ad80ae (spec docs/superpowers/specs/2026-10-28-dynamic-builders-design.md § The delta D1, D2, D3, D6). The
coordinator's verb; `agents_up.sh add` dispatches here. Every `add` for one repo holds ONE exclusive lock — `flock` on
`<git common dir>/fabrik-agents.lock`, shared by every worktree — and runs, in this order:

    (1) preflight      — before any write: the name, the role's charter, not a coordinator or the merge owner, a bound
                         caller (the coordinator a builder asks), no LIVE binding of the name in scope, a trusted
                         root, a capped start (or FABRIK_AGENTS_UNCAPPED=1), and >= 2 GB slice headroom
    (2) the worktree   — `.claude/worktrees/<name>` on `worktree-<name>` from the base branch's tip
    (3) cold start     — T08b
    (4) the binding    — `whoami_agent.py --spawned` under the held lock; plus the registry row where one exists
    (5) the item       — `work.py assign <W-id> --owner <name>` on the main checkout, never committed here
    (6) place + launch — T08a/T08b
    — the lock is released —
    (7) the launchers  — T08c, under the desktop lock only

Each step checks its own artifact first and skips when it is there, so a re-run completes what a failed run left; a
failing step leaves the earlier ones and says which step to re-run. Every refusal exits 2 and appends one JSON line
`{"at", "repo", "name", "step", "reason"}` to `~/.claude/state/agents-spawn.jsonl` (a state record beside
`rotations.jsonl`, never a logfile).

COBRA (D-253): the cheapest way to pass the preflight without its outcome is FABRIK_AGENTS_UNCAPPED=1 left in a
profile — it also skips the headroom floor, since no slice exists to measure — so every run that uses it says so on
stderr; and a coordinator could hand-edit the trust entry, which is the operator's own act either way.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

# the checkout this runs from — its scripts/ are the tools
HUB = Path(__file__).resolve().parents[2]
WHOAMI = HUB / "scripts" / "whoami_agent.py"
# whoami_agent.py::AGENTS_LOCK — the file its --spawned proof checks
AGENTS_LOCK = "fabrik-agents.lock"
NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")  # agents_up.sh NAME_RE
ITEM_RE = re.compile(r"W-[0-9a-f]{8}")  # agents_up.sh ITEM_RE
CHARTER_MARKER = "# Agent charter"  # .claude/hooks/agent_role.py::_CHARTER_MARKER
HEADROOM_FLOOR = 2 * 1024**3  # one Claude session is 1.3-3.6 GB (spec D6)
SLICE = "fabrik-agents.slice"
GIT_LOCATION_VARS = ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")
GIT_TIMEOUT_S = 30
REMOTE_TIMEOUT_S = 20


class RefusedError(Exception):
    """A refusal: exit 2, the reason named, one line in the spawn record. `step=None` is the step `add` was running."""

    def __init__(self, reason: str, step: int | None = 1) -> None:
        super().__init__(reason)
        self.reason = reason
        self.step = step


@dataclass
class Spawn:
    root: str
    name: str
    role: str
    item: str | None
    argv: list[str]
    coordinator: str = ""
    base: str = ""
    sid: str = ""
    scope: str = ""
    # step 3's outcome: "" the grid was up, "up" the cold start restored it (exit 0), "empty" no builder (exit 3)
    cold: str = ""


def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in GIT_LOCATION_VARS}


def _git(root: str, *args: str, timeout: int = GIT_TIMEOUT_S, env: dict | None = None):
    return subprocess.run(
        ["git", "-C", root, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env or _git_env(),
    )


def git_common_dir(root: str) -> str:
    """The repo's git common dir (absolute), with git's location variables removed (agents_up.sh SCOPE)."""
    out = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if out.returncode != 0 or not out.stdout.strip():
        raise RefusedError(
            f"{root} is not a git repository ({out.stderr.strip() or out.returncode})"
        )
    return out.stdout.strip()


def lock_path(root: str) -> str:
    """`<git common dir>/fabrik-agents.lock` — inside `.git`, shared by the main checkout and every worktree."""
    return os.path.join(git_common_dir(root), AGENTS_LOCK)


@contextlib.contextmanager
def agents_lock(root: str) -> Iterator[int]:
    """Hold the repo's agents lock (exclusive, blocking); yields the descriptor `whoami_agent.py --spawned` checks."""
    fd = os.open(lock_path(root), os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        os.close(fd)  # closing the only description releases the flock


def spawn_log_path() -> Path:
    return Path.home() / ".claude" / "state" / "agents-spawn.jsonl"


def record_refusal(repo: str, name: str, step: int, reason: str) -> None:
    path = spawn_log_path()
    row = {"at": int(time.time()), "repo": repo, "name": name, "step": step, "reason": reason}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(
            f"agents_spawn: could not append the refusal to {path} ({exc.strerror or exc})",
            file=sys.stderr,
        )


def _crashed(exc: BaseException) -> RefusedError:
    return RefusedError(f"whoami crashed: {type(exc).__name__}: {exc}", None)


def _whoami():
    """whoami_agent.py from THIS checkout — its store reader and liveness test, never a second copy. A load that
    fails is a refusal at the running step ("whoami crashed: …"), never a traceback. Loaded once per path."""
    key = str(WHOAMI)
    if key in _WHOAMI_LOADED:
        return _WHOAMI_LOADED[key]
    try:
        spec = importlib.util.spec_from_file_location("whoami_agent_for_spawn", WHOAMI)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {WHOAMI}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001 — any failure of the helper is reported, never raised through
        sys.modules.pop("whoami_agent_for_spawn", None)
        raise _crashed(exc) from None
    _WHOAMI_LOADED[key] = mod
    return mod


_WHOAMI_LOADED: dict[str, object] = {}


def _store_rows() -> list[dict]:
    """The identity store's rows, read by whoami_agent.py's own reader."""
    whoami = _whoami()
    try:
        return whoami._rows(whoami.store_path())
    except Exception as exc:  # noqa: BLE001
        raise _crashed(exc) from None


def _alive(row: dict) -> bool:
    """whoami_agent.py's liveness test: a pid that is alive AND the process the row was written for."""
    whoami = _whoami()
    try:
        return bool(whoami._pid_alive_same_start(row))
    except Exception as exc:  # noqa: BLE001
        raise _crashed(exc) from None


# ---- measurements -------------------------------------------------------------------------------------------------


def _user_env() -> dict[str, str]:
    """A COPY of the environment for a systemctl call, with the XDG_RUNTIME_DIR a .bat launch lacks (as capped_run.sh
    sets it). Never os.environ itself: that is the caller's, passed unchanged to `work.py assign`."""
    env = dict(os.environ)
    if not env.get("XDG_RUNTIME_DIR"):
        bus = f"/run/user/{os.getuid()}"
        if os.path.exists(f"{bus}/bus"):
            env["XDG_RUNTIME_DIR"] = bus
    return env


def _cgroup_dir() -> Path | None:
    """The slice's cgroup directory; None when the user manager reports NO cgroup for it (an inactive slice: no grid
    has started since boot, and agents_up.sh asserts the ceiling only at a grid start)."""
    seam = os.environ.get("FABRIK_AGENTS_CGROUP_DIR")
    if seam:
        return Path(seam)
    out = subprocess.run(
        ["systemctl", "--user", "show", "-p", "ControlGroup", "--value", SLICE],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=_user_env(),
    )
    cg = out.stdout.strip()
    if out.returncode == 0 and not cg:
        return None
    if out.returncode != 0 or not cg.startswith("/"):
        raise RefusedError(
            f"no measurable memory limit on {SLICE} (its cgroup is not known to the user manager)"
        )
    return Path("/sys/fs/cgroup" + cg)


def box_available_bytes() -> int:
    """The box's MemAvailable (`/proc/meminfo`, seam FABRIK_AGENTS_MEMINFO), in bytes; unreadable raises."""
    path = Path(os.environ.get("FABRIK_AGENTS_MEMINFO") or "/proc/meminfo")
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition(":")
            if key == "MemAvailable":
                return int(value.split()[0]) * 1024
    except (OSError, ValueError, IndexError) as exc:
        raise RefusedError(f"the box's MemAvailable cannot be read from {path} ({exc})") from None
    raise RefusedError(f"the box's MemAvailable cannot be read from {path} (no MemAvailable line)")


def headroom() -> tuple[int, str]:
    """(bytes, what was measured). An ACTIVE slice: limit − (memory.current − memory.stat inactive_file), so
    reclaimable page cache does not refuse falsely; limit = memory.high, or memory.max when memory.high reads `max`
    (FABRIK_AGENT_SLICE_MAX sets MemoryHigh to infinity); both `max`, or any value unreadable, raises RefusedError.
    A slice with no cgroup yet (inactive) measures the box's MemAvailable instead — the floor always applies."""
    no_limit = f"no measurable memory limit on {SLICE}"
    try:
        cg = _cgroup_dir()
        if cg is None:
            return box_available_bytes(), f"the box's MemAvailable ({SLICE} is not active yet)"
        high = (cg / "memory.high").read_text(encoding="utf-8").strip()
        limit_raw = (
            high if high != "max" else (cg / "memory.max").read_text(encoding="utf-8").strip()
        )
        if limit_raw == "max":
            raise RefusedError(f"{no_limit} (memory.high and memory.max both read max)")
        limit = int(limit_raw)
        current = int((cg / "memory.current").read_text(encoding="utf-8").strip())
        inactive = None
        for line in (cg / "memory.stat").read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition(" ")
            if key == "inactive_file":
                inactive = int(value.strip())
        if inactive is None:
            raise RefusedError(f"{no_limit} (memory.stat has no inactive_file)")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise RefusedError(f"{no_limit} ({exc})") from None
    return limit - (current - inactive), SLICE


def headroom_bytes() -> int:
    """The headroom `headroom()` measures, in bytes (T08's re-measure)."""
    return headroom()[0]


def _capped() -> bool:
    """agents_up.sh's CAPPED: systemd-run on PATH and a user manager that answers."""
    env = _user_env()
    if not shutil.which("systemd-run"):
        return False
    try:
        out = subprocess.run(
            ["systemctl", "--user", "show-environment"],
            capture_output=True,
            timeout=10,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0


def _ls_remote_head(root: str) -> str:
    """origin's HEAD branch from `git ls-remote --symref origin HEAD` (merge_request.py::_remote_refs), or ""."""
    env = {**_git_env(), "GIT_TERMINAL_PROMPT": "0"}
    try:
        out = _git(
            root, "ls-remote", "--symref", "origin", "HEAD", timeout=REMOTE_TIMEOUT_S, env=env
        )
    except subprocess.SubprocessError:
        return ""
    if out.returncode != 0:
        return ""
    for line in out.stdout.splitlines():
        left, _, ref = line.partition("\t")
        if left.startswith("ref: refs/heads/") and ref.strip() == "HEAD":
            return left[len("ref: refs/heads/") :].strip()
    return ""


def resolve_base(root: str) -> str:
    """The base branch: `.fabrik/work/config.json`'s `base_branch` FIRST (no network), else origin's HEAD."""
    cfg_path = os.path.join(root, ".fabrik", "work", "config.json")
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            raw = json.load(fh).get("base_branch")
    except (OSError, ValueError, AttributeError):
        raw = None
    base = raw.strip() if isinstance(raw, str) else ""
    if not base:
        base = _ls_remote_head(root)
    if not base:
        raise RefusedError(
            f"no base_branch in {cfg_path} and origin's HEAD cannot be read (offline?) — set base_branch"
        )
    if base.startswith("-") or _git(root, "check-ref-format", "--branch", base).returncode != 0:
        raise RefusedError(f"base {base!r} is not a branch name")
    return base


# ---- step 1: preflight --------------------------------------------------------------------------------------------


def _coordinator_name(name: str) -> bool:
    return name == "coordinator" or name.endswith("-coordinator")


def _merge_owner(root: str) -> str:
    """agents_up.sh's merge-owner read: exit 0 a name, 3 undeclared, an absent ledger declares nobody."""
    if not os.path.isfile(os.path.join(root, "docs", "DECISIONS.md")):
        return ""
    out = subprocess.run(
        [sys.executable, str(HUB / "scripts" / "decisions.py"), "--merge-owner", root],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if out.returncode == 3:
        return ""
    if out.returncode != 0:
        raise RefusedError(
            f"could not read the merge owner of {root} (decisions.py --merge-owner failed)"
        )
    return out.stdout.strip().lower()


def _has_charter(path: str) -> bool:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            first = fh.readline().rstrip("\r\n")
    except OSError:
        return False
    rest = first[len(CHARTER_MARKER) :]
    return first.startswith(CHARTER_MARKER) and (rest == "" or rest[:1].isspace())


def _trusted(root: str) -> bool:
    cfg = Path.home() / ".claude-fleet" / "active" / ".claude.json"
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        return data["projects"][root]["hasTrustDialogAccepted"] is True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _registry_path(root: str) -> str:
    return os.path.join(root, ".fabrik", "session-agents.json")


def _read_registry(root: str) -> dict | None:
    """The registry, None when the repo has none; a malformed one refuses."""
    path = _registry_path(root)
    if not os.path.lexists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            reg = json.load(fh)
    except (OSError, ValueError) as exc:
        raise RefusedError(f"{path} is not a valid registry ({exc})") from None
    if not isinstance(reg, dict):
        raise RefusedError(f"{path} must be an object of session id -> agent name")
    return reg


def _rev(path: str, *args: str) -> str:
    """`git rev-parse <args>` in `path` (location variables unset), realpath'd; "" when git refuses."""
    out = _git(path, "rev-parse", *args)
    if out.returncode != 0 or not out.stdout.strip():
        return ""
    return os.path.realpath(out.stdout.strip())


def _is_main_checkout(path: str) -> bool:
    """`path` (realpath'd) is a main checkout: its own toplevel, not a linked worktree (`--absolute-git-dir` IS the
    common dir), and not the common dir itself (a bare repo or a separate git dir). Never `dirname(common dir)`: a main
    checkout whose `.git` is a `gitdir:` pointer (`--separate-git-dir`) keeps its common dir elsewhere."""
    common = _rev(path, "--path-format=absolute", "--git-common-dir")
    return (
        bool(common)
        and _rev(path, "--show-toplevel") == path
        and _rev(path, "--absolute-git-dir") == common
        and path != common
    )


def _main_checkout_hint(root: str) -> str:
    """A main checkout to name in the refusal — the first `git worktree list` entry, else `root`'s toplevel — only
    when it really is one (under a separate git dir or a bare repo the first entry is the git dir); else ""."""
    candidates = []
    listed = _git(root, "worktree", "list", "--porcelain")
    if listed.returncode == 0:
        for line in listed.stdout.splitlines():
            if line.startswith("worktree "):
                candidates.append(os.path.realpath(line[len("worktree ") :]))
                break
    candidates.append(_rev(root, "--show-toplevel"))
    return next((c for c in candidates if c and _is_main_checkout(c)), "")


def preflight(ctx: Spawn) -> None:
    """D2 (1): every refusal BEFORE any write, so a refused add leaves no worktree or branch."""
    name, role, root = ctx.name, ctx.role, ctx.root
    if not _is_main_checkout(root):
        hint = _main_checkout_hint(root)
        where = f"pass the main checkout {hint}" if hint else "pass the repo's main checkout"
        raise RefusedError(
            f"{root} is not the repo's main checkout — {where}, not a linked worktree or a subdirectory"
        )
    if not NAME_RE.fullmatch(name):
        raise RefusedError(f"{name!r} is not an agent name ([a-z0-9][a-z0-9-]{{0,31}})")
    if not NAME_RE.fullmatch(role):
        raise RefusedError(f"--role {role!r} is not an agent name ([a-z0-9][a-z0-9-]{{0,31}})")
    if ctx.item is not None and not ITEM_RE.fullmatch(ctx.item):
        raise RefusedError(f"--item {ctx.item!r} is not a work item id (W- and 8 lowercase hex)")
    charter = os.path.join(root, "docs", "reference", "agents", f"{role}.md")
    if not _has_charter(charter):
        raise RefusedError(
            f"--role {role}: {charter} is missing or its first line is not '{CHARTER_MARKER}'"
        )
    suffix = name[len(role) + 1 :]
    if not name.startswith(f"{role}-"):
        raise RefusedError(
            f"{name!r} does not start with '{role}-' (role {role}: names read {role}-1, {role}-2, …)"
        )
    if not suffix or not name[-1].isalnum():
        raise RefusedError(
            f"{name!r} needs an ordinal after '{role}-' that ends in a letter or digit ({role}-1, {role}-2, …)"
        )
    if _coordinator_name(name):
        raise RefusedError(f"{name!r} is a coordinator name — a coordinator gets no builder pane")
    owner = _merge_owner(root)
    if owner and owner == name:
        raise RefusedError(
            f"{name!r} is the repo's merge owner (its coordinator) — a coordinator gets no builder pane"
        )
    who = subprocess.run(
        [sys.executable, str(WHOAMI), "--who"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    ctx.coordinator = who.stdout.strip() if who.returncode == 0 else ""
    if not ctx.coordinator:
        raise RefusedError("add needs a bound coordinator — run whoami_agent.py --as <name>")
    if ctx.coordinator == name:
        raise RefusedError(f"{name!r} is the caller's own name")
    for row in _store_rows():
        if row.get("name") == name and row.get("toplevel") == ctx.scope and _alive(row):
            raise RefusedError(
                f"{name!r} is bound to a LIVE session (pid {row.get('pid')}) in this repo — pick another name"
            )
    if not _trusted(root):
        raise RefusedError(
            f"{root} is not trusted — open {root} once in Claude Code and accept the trust dialog"
        )
    _read_registry(root)
    ctx.base = resolve_base(root)
    check_headroom(1)


def check_headroom(step: int, after: str = "") -> None:
    """The headroom floor at `step`: the slice when capped, the box's MemAvailable under FABRIK_AGENTS_UNCAPPED=1 (said),
    else a refusal. Under 2 GB refuses. `after` names what ran first (T08b's second measure, after the cold start)."""
    try:
        if _capped():
            room, what = headroom()
        elif os.environ.get("FABRIK_AGENTS_UNCAPPED") == "1":
            print(
                "agents_spawn: FABRIK_AGENTS_UNCAPPED=1 — the builder runs UNCAPPED (no user manager)",
                file=sys.stderr,
            )
            room, what = box_available_bytes(), "the box's MemAvailable (no slice: uncapped)"
        else:
            room, what = -1, ""
    except RefusedError as exc:
        raise RefusedError(exc.reason, step) from None
    if not what:
        raise RefusedError(
            "no systemd-run on PATH, or no systemd user manager answers — the builder would run uncapped; "
            "set FABRIK_AGENTS_UNCAPPED=1 to start it anyway",
            step,
        )
    if what != SLICE or after:
        print(
            f"agents_spawn: headroom measured on {what}{after}: {room / 1024**3:.1f} GB",
            file=sys.stderr,
        )
    if room < HEADROOM_FLOOR:
        raise RefusedError(
            f"{what} has {room / 1024**3:.1f} GB headroom{after}, under the 2 GB floor — retire a builder first",
            step,
        )


# ---- steps 2-7 ----------------------------------------------------------------------------------------------------


def _worktree_dir(ctx: Spawn) -> str:
    return os.path.join(ctx.root, ".claude", "worktrees", ctx.name)


def _in_place(path: str) -> bool:
    """A linked git worktree in place (agents_up.sh's `linked`)."""
    return (
        os.path.isdir(path)
        and os.path.isfile(os.path.join(path, ".git"))
        and os.path.realpath(path) == path
    )


def make_worktree(ctx: Spawn) -> None:
    """D2 (2): `.claude/worktrees/<name>` on `worktree-<name>` from the base tip; a worktree in place is kept."""
    path, branch = _worktree_dir(ctx), f"worktree-{ctx.name}"
    if _in_place(path):
        print(f"agents_spawn: step 2 — {path} is already in place; kept")
        return
    start = ""
    for ref in (f"refs/heads/{ctx.base}", f"refs/remotes/origin/{ctx.base}"):
        if _git(ctx.root, "rev-parse", "--verify", "--quiet", ref + "^{commit}").returncode == 0:
            start = ref
            break
    if not start:
        raise RefusedError(
            f"the base branch {ctx.base!r} has no local or origin ref in {ctx.root}", 2
        )
    if _git(ctx.root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0:
        merged = _git(ctx.root, "merge-base", "--is-ancestor", f"refs/heads/{branch}", start)
        if merged.returncode != 0:
            raise RefusedError(
                f"a leftover branch {branch} holds work not in {ctx.base} — merge or delete it by hand, then re-run",
                2,
            )
        # -D only after the explicit ancestry check: plain -d tests HEAD/upstream, not the base
        gone = _git(ctx.root, "branch", "-D", branch)
        if gone.returncode != 0:
            raise RefusedError(
                f"could not delete the merged leftover branch {branch}: {gone.stderr.strip()}", 2
            )
    rel = os.path.join(".claude", "worktrees", ctx.name)
    made = _git(ctx.root, "worktree", "add", "-b", branch, rel, start, timeout=120)
    if made.returncode != 0:
        raise RefusedError(f"git worktree add failed: {made.stderr.strip() or made.returncode}", 2)


# ---- step 3: the cold start (T08b) --------------------------------------------------------------------------------
# Spec § The delta D2 (3), D4's cold start, W-14219e6f points 1 and 7. agents_up.sh takes no lock, so calling it while
# the agents lock is held cannot deadlock. COBRA (D-253): the cheapest way to "settle" without the outcome is to stop
# waiting at once — so the wait only ends early on every restored pane reading `running`, and whatever it ends on, the
# headroom is measured again before the launch (step 6); the settle wait itself refuses nothing.

AGENTS_UP_TIMEOUT_S = 300
SETTLE_POLL_S = 0.25
SPAWN_VARS = ("FABRIK_SPAWN_NAME", "FABRIK_SPAWN_COORDINATOR", "FABRIK_SPAWN_ITEM")


def session_name(root: str) -> str:
    """agents_up.sh's `<S>`: the root's basename, every character outside [A-Za-z0-9_-] replaced by `-`."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", os.path.basename(root))


def _agents_up_path() -> str:
    """agents_up.sh — FABRIK_AGENTS_UP (tests run a fake), else this checkout's."""
    return os.environ.get("FABRIK_AGENTS_UP") or str(HUB / "scripts" / "sysadmin" / "agents_up.sh")


def _agents_up(step: int, *args: str, spawn: dict[str, str] | None = None):
    """Run agents_up.sh with `args`. The FABRIK_SPAWN_* variables are the caller's to set for THIS call only (`spawn`);
    any the environment carries are dropped, so a stale one never reaches another verb's first prompt."""
    env = {k: v for k, v in os.environ.items() if k not in SPAWN_VARS}
    env.update(spawn or {})
    try:
        return subprocess.run(
            [_agents_up_path(), *args],
            capture_output=True,
            text=True,
            timeout=AGENTS_UP_TIMEOUT_S,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RefusedError(
            f"agents_up.sh {args[0]} could not run: {type(exc).__name__}: {exc}", step
        ) from None


def _settle_s() -> float:
    raw = os.environ.get("FABRIK_AGENTS_SETTLE_S") or "20"
    try:
        value = float(raw)
    except ValueError:
        raise RefusedError(f"FABRIK_AGENTS_SETTLE_S={raw!r} is not a number of seconds", 3) from None
    if not value >= 0:  # also refuses nan
        raise RefusedError(f"FABRIK_AGENTS_SETTLE_S={raw!r} is not a number of seconds", 3)
    return value


def _all_running(root: str) -> bool:
    """`agents_up.sh --print <root>`: every `pane <name> <sid> <dir> <status>` line reads `running` (no builder at all,
    exit 3, is settled too). A failed or unreadable report is not settled — the wait goes on to its bound."""
    out = _agents_up(3, "--print", root)
    if out.returncode == 3:
        return True
    if out.returncode != 0:
        return False
    states = [ln.split()[-1] for ln in out.stdout.splitlines() if ln.startswith("pane ")]
    return all(s == "running" for s in states)


def _settle(root: str) -> None:
    """PF4: wait until every restored pane reads `running`, or FABRIK_AGENTS_SETTLE_S (20) seconds elapse."""
    deadline = time.monotonic() + _settle_s()
    while not _all_running(root):
        left = deadline - time.monotonic()
        if left <= 0:
            print(
                "agents_spawn: step 3 — the restored panes did not all read running in time; measuring anyway",
                file=sys.stderr,
            )
            return
        time.sleep(min(SETTLE_POLL_S, left))


def cold_start(ctx: Spawn) -> None:
    """D2 (3), D4: when the repo has no tmux session, `agents_up.sh --detach <root>` first. Exit 0 restored every
    registered builder (wait for them to settle; step 6 measures again); exit 3 had no builder and started nothing
    (step 6 runs --detach again once the binding exists); any other exit stops `add` here with its stderr."""
    sess = session_name(ctx.root)
    try:
        up = _has_session(sess)
    except RefusedError as exc:  # FABRIK_TMUX is not a command
        raise RefusedError(exc.reason, 3) from None
    if up:
        return
    out = _agents_up(3, "--detach", ctx.root)
    if out.returncode == 0:
        ctx.cold = "up"
        print(f"agents_spawn: step 3 — no {sess} session: the grid was started with its builders")
        _settle(ctx.root)
    elif out.returncode == 3:
        ctx.cold = "empty"
        print(f"agents_spawn: step 3 — no {sess} session and no builder: {ctx.name} will start it")
    else:
        raise RefusedError(
            f"agents_up.sh --detach exited {out.returncode}: {out.stderr.strip() or '(no stderr)'}",
            3,
        )


def _bound_sid(ctx: Spawn) -> str:
    """The session id an EARLIER `add` bound to the name and nobody has started yet, or "". Reused only when the
    LAST row naming the name in this scope is that `--spawned` row (`spawned: true`, no live pid) AND the session is
    still the name's (its own last row anywhere). Anything else — an `--as` row, a dead pid row, a spawned session its
    builder has since re-bound — mints a fresh id: resuming a started session would resume a dead transcript."""
    rows = _store_rows()
    owner = {str(r.get("session_id")): str(r.get("name") or "") for r in rows}
    last = None
    for r in rows:
        if r.get("toplevel") == ctx.scope and r.get("name") == ctx.name:
            last = r
    if last is None or last.get("spawned") is not True or _alive(last):
        return ""
    sid = str(last.get("session_id"))
    return sid if owner.get(sid) == ctx.name else ""


def _write_registry_row(ctx: Spawn) -> None:
    reg = _read_registry(ctx.root)
    # a repo with no registry gets NO file: the resolver would then read only registry names (agents_up.sh)
    if reg is None:
        return
    if reg.get(ctx.sid) == ctx.name and list(reg.values()).count(ctx.name) == 1:
        return
    # exactly one row for the name, the bound session's: a stale `{old: name}` row would resume a dead session
    reg = {sid: n for sid, n in reg.items() if n != ctx.name}
    reg[ctx.sid] = ctx.name
    _replace_registry(ctx.root, reg)


def _replace_registry(root: str, reg: dict) -> None:
    """Write `reg` as the registry by an atomic replace in its own directory, keeping the file's mode."""
    path = _registry_path(root)
    try:
        mode = os.stat(path).st_mode & 0o7777
    except OSError:
        mode = 0o644
    fd, tmp = tempfile.mkstemp(prefix=".session-agents.", suffix=".tmp", dir=os.path.dirname(path))
    try:
        os.fchmod(fd, mode)  # mkstemp makes 0600; the replaced file keeps the registry's own mode
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(reg, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def bind(ctx: Spawn, lock_fd: int) -> None:
    """D2 (4): mint a UUID and bind it through whoami_agent.py --spawned (holding the lock), then the registry row."""
    ctx.sid = _bound_sid(ctx)
    if ctx.sid:
        print(f"agents_spawn: step 4 — {ctx.name} is already bound to {ctx.sid}; kept")
    else:
        sid = str(uuid.uuid4())
        out = subprocess.run(
            [
                sys.executable,
                str(WHOAMI),
                "--spawned",
                ctx.name,
                "--session-id",
                sid,
                "--repo",
                ctx.root,
                "--lock-fd",
                str(lock_fd),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            pass_fds=(lock_fd,),
        )
        if out.returncode == 1:
            raise RefusedError(f"{ctx.name!r} is held by a live session: {out.stderr.strip()}", 4)
        if out.returncode == 2:
            raise RefusedError(out.stderr.strip() or "whoami_agent.py --spawned refused", 4)
        if out.returncode != 0:
            raise RefusedError(f"whoami crashed: {out.stderr.strip() or out.returncode}", 4)
        ctx.sid = sid
    try:
        _write_registry_row(ctx)
    except (RefusedError, OSError) as exc:
        raise RefusedError(f"the registry row was not written: {exc}", 4) from None


def _item_owner(ctx: Spawn) -> str:
    path = os.path.join(ctx.root, ".fabrik", "work", f"{ctx.item}.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return str(json.load(fh).get("owner") or "")
    except (OSError, ValueError, AttributeError):
        return ""


def assign_item(ctx: Spawn) -> None:
    """D2 (5): `work.py assign <W-id> --owner <name>` on the main checkout, as the caller (the distributor), before
    any pane exists. Never `commit-items`: that commits the main checkout's branch and is the coordinator's job."""
    if not ctx.item:
        return
    if _item_owner(ctx) != ctx.name:
        out = subprocess.run(
            [
                sys.executable,
                os.path.join(ctx.root, "scripts", "work.py"),
                "assign",
                ctx.item,
                "--owner",
                ctx.name,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            cwd=ctx.root,
        )
        if out.returncode != 0:
            raise RefusedError(
                (
                    out.stderr.strip()
                    or out.stdout.strip()
                    or f"work.py assign exited {out.returncode}"
                ),
                5,
            )
    print(
        f"{ctx.item} is assigned on {ctx.root}; it reaches {ctx.name}'s tree after your store commit "
        "(`work.py commit-items`) merges"
    )


# ---- step 6: placement (T08a) -------------------------------------------------------------------------------------
# Spec § The delta D4 (placement), D9 (the live read), D2 (adoption); the grid's other writer is agents_up.sh's
# "windows of four and the grouped overflow sessions" block, whose rules this mirrors: windows `agents`, `agents-<k>`
# (k >= 2) of at most four panes, found by an EXACT name match over a read and targeted by `#{window_id}` only (tmux
# resolves a window NAME target loosely: with only `agents-2` present `-t =s:agents` selects it); the overflow window
# `agents-<k>` is shown in its own session `<S>+<k>`, grouped with `<S>`; every session target is the exact `=` form.
# COBRA (D-253): the cheapest way to "place" without the outcome is to read a failed tmux call as an empty grid and open
# a window beside a live one — so a read that errors or answers nothing refuses, and nothing is created on a refusal.

PER_WINDOW = 4
TMUX_TIMEOUT_S = 20
_WINDOW_RE = re.compile(r"agents(?:-([2-9]|[1-9][0-9]+))?")
_DIGITS_RE = re.compile(r"[0-9]+")  # the shell's ^[0-9]+$ — never str.isdigit(), which takes `²`
_SID_LONG = ("--session-id", "--resume")  # also read as `--flag=<id>`
_SID_FLAGS = (*_SID_LONG, "-r")  # agents_up.sh::status_of's running test
_PROC_WALK_MAX = 4096


class PlacementRefusedError(RefusedError):
    """A placement refusal: step 6, nothing created."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason, 6)


PlacementRefused = PlacementRefusedError  # the name T08b and T09 import (plan IF7)


@dataclass
class PlaceResult:
    window_id: str
    pane_id: str
    # 1 = `agents` was (re-)created, k = `agents-<k>` was opened, None = an existing window
    new_window_k: int | None
    adopted: bool


@dataclass
class _Pane:
    window_id: str
    window_name: str
    pane_id: str
    pane_pid: int
    agent: str


def _digits(text: str) -> bool:
    return _DIGITS_RE.fullmatch(text) is not None


def _tmux_argv() -> list[str]:
    """The tmux command: FABRIK_TMUX (a command prefix, e.g. `tmux -L <scratch>` in tests), else `tmux`. A value that is
    not a command (an unbalanced quote, only whitespace) refuses — never a traceback, never a tmux verb run as the
    program."""
    raw = os.environ.get("FABRIK_TMUX") or "tmux"
    try:
        argv = shlex.split(raw)
    except ValueError as exc:
        raise PlacementRefusedError(f"FABRIK_TMUX is not a command: {raw!r} ({exc})") from None
    if not argv:
        raise PlacementRefusedError(f"FABRIK_TMUX is not a command: {raw!r} (it names no program)")
    return argv


def _tmux(*args: str) -> subprocess.CompletedProcess[str]:
    argv = _tmux_argv()
    try:
        return subprocess.run(
            [*argv, *args],
            capture_output=True,
            text=True,
            timeout=TMUX_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(args, 1, "", f"{type(exc).__name__}: {exc}")


def _tmux_ok(what: str, *args: str) -> str:
    """Run a tmux write; its failure is a refusal naming `what`."""
    out = _tmux(*args)
    if out.returncode != 0:
        raise PlacementRefusedError(f"tmux {what} failed: {out.stderr.strip() or out.returncode}")
    return out.stdout.strip()


def _has_session(name: str) -> bool:
    return _tmux("has-session", "-t", f"={name}").returncode == 0


def _group(session: str) -> str | None:
    """The session's group: "" when it has none, None when the READ failed — never a failure read as "ungrouped" (the
    `=<name>:` form: option/format reads refuse the bare `=<name>`)."""
    out = _tmux("display-message", "-p", "-t", f"={session}:", "#{session_group}")
    return out.stdout.strip() if out.returncode == 0 else None


def live_panes(sess: str) -> list[_Pane]:
    """D9's live read: `list-panes -s -t =<S>` — the base session only, one line per pane (a grouped window is listed
    once, never once per member). Tab-separated: tmux prints a tab INSIDE a value as `\\011`, so only the separators
    are tabs. An error, an empty answer or a malformed line refuses; it is never read as an empty grid."""
    fmt = "\t".join(("#{window_id}", "#{window_name}", "#{pane_id}", "#{pane_pid}", "#{@agent}"))
    out = _tmux("list-panes", "-s", "-t", f"={sess}", "-F", fmt)
    if out.returncode != 0:
        raise PlacementRefusedError(
            f"tmux read failed — not placing (list-panes -s -t ={sess}: {out.stderr.strip() or out.returncode})"
        )
    panes = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if (
            len(parts) != 5
            or not re.fullmatch(r"@[0-9]+", parts[0])
            or not re.fullmatch(r"%[0-9]+", parts[2])
            or not _digits(parts[3])
        ):
            raise PlacementRefusedError(
                f"tmux read failed — not placing (an unreadable pane line {line!r})"
            )
        panes.append(_Pane(parts[0], parts[1], parts[2], int(parts[3]), parts[4]))
    if not panes:
        up = "the grid is up" if _has_session(sess) else f"no session {sess}"
        raise PlacementRefusedError(
            f"tmux read failed — not placing (list-panes answered nothing; {up})"
        )
    return panes


# -- adoption ---------------------------------------------------------------------------------------------------------


def _proc_root() -> Path:
    return Path(os.environ.get("FABRIK_PROC_ROOT") or "/proc")


def _children(proc: Path, pid: int) -> list[int]:
    """Every child of every thread of `pid` (the kernel's `/proc/<pid>/task/<tid>/children`)."""
    kids: list[int] = []
    try:
        tasks = sorted((proc / str(pid) / "task").iterdir())
    except OSError:
        return kids
    for task in tasks:
        try:
            text = (task / "children").read_text(encoding="utf-8")
        except OSError:
            continue
        kids.extend(int(t) for t in text.split() if _digits(t))
    return kids


def _argv(proc: Path, pid: int) -> list[str]:
    """`/proc/<pid>/cmdline` split on NUL; only ONE trailing empty element is dropped, and only when the bytes end in
    NUL — a cmdline without one (a process that rewrote its argv) keeps its last argument."""
    try:
        raw = (proc / str(pid) / "cmdline").read_bytes()
    except OSError:
        return []
    if not raw:
        return []
    parts = raw.split(b"\0")
    if raw.endswith(b"\0"):
        parts = parts[:-1]
    return [a.decode("utf-8", "replace") for a in parts]


def _sid_of(argv: list[str]) -> str:
    """A claude argv's session id: the value after `--session-id`/`--resume`/`-r`, or `--session-id=`/`--resume=`'s;
    a flag with no value (absent, or the next token is another option) gives no id and the scan goes on."""
    for i, arg in enumerate(argv[1:], start=1):
        if arg in _SID_FLAGS:
            nxt = argv[i + 1] if i + 1 < len(argv) else ""
            if nxt and not nxt.startswith("-"):
                return nxt
            continue
        flag, eq, value = arg.partition("=")
        if eq and flag in _SID_LONG and value:
            return value
    return ""


def _claude_sids(pane_id: str, pane_pid: int, want: str) -> list[str]:
    """The session id of every claude process under `pane_pid` (itself included), walked RECURSIVELY: a capped pane is
    the pane's shell → systemd-run --scope → bash -c → claude, an uncapped one shell → claude. A claude is a process
    whose argv[0] is `claude` (any directory); "" stands for a claude carrying no id. The walk stops as soon as a claude
    carrying `want` is found; a tree larger than the walk's bound without it refuses: a partial walk could miss the
    claude and read as "runs no claude"."""
    proc = _proc_root()
    sids: list[str] = []
    seen: set[int] = set()
    stack = [pane_pid]
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        if len(seen) >= _PROC_WALK_MAX:
            raise PlacementRefusedError(
                f"the process tree of pane {pane_id} is too large to read (over {_PROC_WALK_MAX}) — not placing"
            )
        seen.add(pid)
        argv = _argv(proc, pid)
        if argv and os.path.basename(argv[0]) == "claude":
            sids.append(_sid_of(argv))
            if sids[-1] == want:
                return sids
        stack.extend(_children(proc, pid))
    return sids


def _adopt(panes: list[_Pane], name: str, sid: str) -> PlaceResult | None:
    """D2, C1: a pane tagged `@agent <name>` whose claude runs the name's bound session is adopted; a tagged pane
    without it refuses (never a second pane for the name)."""
    tagged = [p for p in panes if p.agent == name]
    if not tagged:
        return None
    if len(tagged) > 1:
        ids = ", ".join(p.pane_id for p in tagged)
        raise PlacementRefusedError(
            f"{len(tagged)} panes are tagged @agent {name} ({ids}) — remove all but one"
        )
    pane = tagged[0]
    sids = _claude_sids(pane.pane_id, pane.pane_pid, sid)
    if sid in sids:
        return PlaceResult(pane.window_id, pane.pane_id, None, True)
    if not sids:
        raise PlacementRefusedError(
            f"{name}'s pane runs no claude — respawn it (`tmux respawn-pane -k -t {pane.pane_id}`) or remove it"
        )
    others = ", ".join(s or "(no session id)" for s in sids)
    raise PlacementRefusedError(
        f"{name}'s pane {pane.pane_id} runs claude with session {others}, not {name}'s bound session {sid} — "
        f"respawn it (`tmux respawn-pane -k -t {pane.pane_id}`) or remove it"
    )


# -- the overflow sessions --------------------------------------------------------------------------------------------


def _is_overflow(sess: str, candidate: str) -> bool:
    """`<S>+<digits>` — ours by construction: `+` is outside the base-name alphabet."""
    return candidate.startswith(f"{sess}+") and _digits(candidate[len(sess) + 1 :])


# The decision and the kill list below come from ONE list-sessions snapshot, so no second read can disagree with the
# first. The window between that snapshot and the kill stays open to a concurrent agents_up.sh writer; it closes only
# when agents_up.sh's grid writers take the same agents lock (recorded in W-53f246f3, outside T08a).
def _clear_stale_group(sess: str, k: int) -> None:
    """Before any `new-session -t =<S>` (agents_up.sh::clear_stale_group), only while `<S>` is UNGROUPED: a session in
    a group NAMED `<S>` would be joined by that new-session and drag `<S>` into its windows. Of those, a `<S>+<digits>`
    is a leftover of an older grid (ours by construction) and is killed; any OTHER is not ours and refuses, naming it,
    BEFORE anything is killed. An `<S>+<k>` that is ungrouped or grouped under another name is never touched. A failed
    read, or a snapshot without `<S>`, refuses."""
    out = _tmux("list-sessions", "-F", "#{session_name}|~|#{session_group}")
    if out.returncode != 0:
        raise PlacementRefusedError(
            f"tmux read failed — not placing (list-sessions: {out.stderr.strip() or out.returncode})"
        )
    groups: dict[str, str] = {}
    for line in out.stdout.splitlines():
        session, _, group = line.rpartition(
            "|~|"
        )  # the LAST `|~|`: a name may hold one, <S> cannot
        groups[session] = group
    if sess not in groups:
        raise PlacementRefusedError(
            f"tmux read failed — not placing (no session {sess} in list-sessions)"
        )
    if groups[sess]:
        return
    in_s = [n for n, g in groups.items() if n != sess and g == sess]
    leftovers = [n for n in in_s if _is_overflow(sess, n)]
    stale = [n for n in in_s if not _is_overflow(sess, n)]
    if stale:
        frees = "; ".join(f"tmux kill-session -t ={m}" for m in stale)
        also = (
            f" (and the leftovers {', '.join(leftovers)} would then be cleared)"
            if leftovers
            else ""
        )
        raise PlacementRefusedError(
            f"the tmux session(s) {', '.join(stale)} are still grouped under the name {sess} (left by an older grid) — "
            f"not opening agents-{k}; free the group with: {frees}{also}"
        )
    for n in leftovers:
        killed = _tmux("kill-session", "-t", f"={n}")
        if killed.returncode != 0:  # it would still be joined: refuse, nothing is created yet
            raise PlacementRefusedError(
                f"could not kill the leftover tmux session {n} ({killed.stderr.strip() or killed.returncode}) — "
                f"not opening agents-{k}"
            )


def _ensure_overflow(sess: str, k: int, window_id: str) -> None:
    """agents_up.sh::ensure_overflow. The one rule (T03 invariant 4): reuse `<S>+<k>` only when it exists AND its group
    is non-empty AND equals `<S>`'s; otherwise kill it (when present) and `new-session -d -t =<S> -s <S>+<k>` (a failed
    create is accepted only when the session now exists in `<S>`'s group). Then the session must LIST the window and
    select it; else it is killed when this call made it. Every failure comes AFTER the pane exists, so it is said on
    stderr (agents_up.sh's "stays in <S>"), never raised."""
    name = f"{sess}+{k}"
    stays = f"it stays in {sess}"
    created = False
    if _has_session(name):
        own = _group(name)
        base = _group(sess)  # read AFTER own, as agents_up.sh does
        if own is None or base is None:  # a failed read decides nothing, and never kills
            print(
                f"agents_spawn: could not read the groups of {name} and {sess} — not touching {name}; {stays}",
                file=sys.stderr,
            )
            return
        if not own or own != base:
            _tmux("kill-session", "-t", f"={name}")
    if not _has_session(name):
        made = _tmux("new-session", "-d", "-t", f"={sess}", "-s", name)
        if made.returncode == 0:
            created = True
        else:
            own, base = _group(name), _group(sess)
            if not own or own != base:  # None (a failed read) or "" never accepts
                print(
                    f"agents_spawn: could not create the tmux session {name} for window agents-{k} "
                    f"({made.stderr.strip() or made.returncode}) — it stays in {sess}",
                    file=sys.stderr,
                )
                return
    listed = _tmux("list-windows", "-t", f"={name}", "-F", "#{window_id}")
    if (
        listed.returncode != 0
        or window_id not in listed.stdout.split()
        or _tmux("select-window", "-t", f"={name}:{window_id}").returncode != 0
    ):
        print(
            f"agents_spawn: the tmux session {name} shows other windows than window agents-{k} ({window_id}) — "
            f"not using it; it stays in {sess}",
            file=sys.stderr,
        )
        if created:
            _tmux("kill-session", "-t", f"={name}")


# -- placement --------------------------------------------------------------------------------------------------------


def _window_k(name: str) -> int | None:
    """1 for `agents`, k for `agents-<k>` (k >= 2, no leading zero), None for any other name (exact match)."""
    m = _WINDOW_RE.fullmatch(name)
    if not m:
        return None
    return int(m.group(1)) if m.group(1) else 1


def _undo(pane: str, wid: str, made_window: bool) -> None:
    """Remove what this call created after a later step failed, so a re-run never finds an untagged builder: the pane
    (a window whose last pane goes with it), or the created window when only its id was readable."""
    if re.fullmatch(r"%[0-9]+", pane):
        _tmux("kill-pane", "-t", pane)
    elif made_window and re.fullmatch(r"@[0-9]+", wid):
        _tmux("kill-window", "-t", wid)


def place_pane(root: str, sess: str, name: str, uuid: str, worktree: str, cmd: str) -> PlaceResult:
    """D4: put `name`'s pane (running `cmd` in `worktree`) into `<S>` — or adopt the tagged pane already running its
    bound session `uuid` (D2). The lowest existing window with room (order `agents`, `agents-2`, …) takes it, split
    after its LAST pane; only when none has room is the lowest free name opened in the background. Every window target
    is a `#{window_id}`. `<S>`'s current window moves only when `agents` itself was re-created (W-14219e6f point 8).
    `root` names the repo in messages; the grid must already be up (T08b's cold start). Every refusal comes before
    anything is created, or removes what this call created first."""
    if not uuid:
        raise PlacementRefusedError(f"no session id bound to {name} — not placing")
    panes = live_panes(sess)
    adopted = _adopt(panes, name, uuid)
    if adopted is not None:
        return adopted
    windows: dict[str, list[_Pane]] = {}
    for p in panes:
        windows.setdefault(p.window_id, []).append(p)
    by_k: dict[int, str] = {}
    for wid, ps in windows.items():
        k = _window_k(ps[0].window_name)
        if k is None:
            continue
        if k in by_k:  # spec D4: a target by a name two windows share fails
            raise PlacementRefusedError(
                f"two windows of {sess} are named {ps[0].window_name} ({by_k[k]}, {wid}) — rename or close one"
            )
        by_k[k] = wid
    for k in sorted(by_k):
        wid = by_k[k]
        if len(windows[wid]) < PER_WINDOW:
            last = windows[wid][-1].pane_id
            pane = _tmux_ok(
                f"split-window in {sess}'s window {wid}",
                "split-window",
                "-d",
                "-t",
                last,
                "-c",
                worktree,
                "-P",
                "-F",
                "#{pane_id}",
                cmd,
            )
            new_k = None
            break
    else:
        new_k = next(k for k in range(1, len(by_k) + 2) if k not in by_k)
        wname = "agents" if new_k == 1 else f"agents-{new_k}"
        if new_k > 1:
            _clear_stale_group(sess, new_k)  # before anything is created
        made = _tmux_ok(
            f"new-window {wname} in {sess}",
            "new-window",
            "-d",
            "-t",
            f"={sess}:",
            "-n",
            wname,
            "-P",
            "-F",
            "#{window_id} #{pane_id}",
            "-c",
            worktree,
            cmd,
        )
        wid, _, pane = made.partition(" ")
    if not re.fullmatch(r"%[0-9]+", pane) or not re.fullmatch(r"@[0-9]+", wid):
        _undo(pane, wid, new_k is not None)
        raise PlacementRefusedError(
            f"tmux gave no window and pane id for {name}'s pane ({wid!r} {pane!r}) in {root}"
        )
    _tmux("select-layout", "-t", wid, "even-horizontal")
    tagged = _tmux("set", "-p", "-t", pane, "@agent", name)
    if tagged.returncode != 0:
        _undo(pane, wid, new_k is not None)
        raise PlacementRefusedError(
            f"tmux could not tag {name}'s pane {pane} ({tagged.stderr.strip() or tagged.returncode}) — removed it"
        )
    if new_k == 1:
        if _tmux("select-window", "-t", f"={sess}:{wid}").returncode != 0:
            print(
                f"agents_spawn: could not make the re-created window agents ({wid}) {sess}'s current window",
                file=sys.stderr,
            )
    elif new_k is not None:
        _ensure_overflow(sess, new_k, wid)
    return PlaceResult(wid, pane, new_k, False)


def heal_registry(root: str, panes: list[_Pane]) -> None:
    """PF3: re-point each `.fabrik/session-agents.json` row whose name has ONE live pane (tagged `@agent <name>`) whose
    claude runs ONE session id other than the row's — a rotation that could not take the agents lock left the row on
    the old id. PRECONDITION: the caller holds the repo's agents lock (`add` step 6; T09's verbs). No registry file:
    nothing is touched. A name with no pane, two panes, no claude, two different ids, or a tree too large to read keeps
    its row (said on stderr where a pane was seen). One atomic replace, only when a row changed."""
    reg = _read_registry(root)
    if reg is None:
        return
    healed = dict(reg)
    for name in sorted(set(reg.values())):
        tagged = [p for p in panes if p.agent == name]
        if len(tagged) != 1:
            continue
        rows = [sid for sid, n in reg.items() if n == name]
        try:
            sids = _claude_sids(tagged[0].pane_id, tagged[0].pane_pid, rows[0])
        except RefusedError as exc:
            print(f"agents_spawn: registry row for {name} kept ({exc.reason})", file=sys.stderr)
            continue
        live = {s for s in sids if s}
        if len(live) != 1 or live & set(rows):
            continue
        new = live.pop()
        healed = {sid: n for sid, n in healed.items() if n != name}
        healed[new] = name
        print(
            f"agents_spawn: registry row for {name} re-pointed {', '.join(rows)} -> {new} (its live pane's session)",
            file=sys.stderr,
        )
    if healed != reg:
        _replace_registry(root, healed)


def place_and_launch(ctx: Spawn) -> None:
    """D2 (6), D1, D4. After a cold start that found no builder, `agents_up.sh --detach` AGAIN makes the grid with this
    builder as its first pane (it now resolves: binding and worktree in place, no transcript) — DONE, no place_pane.
    Otherwise: the live read, adoption (a live pane of the name running its bound session is kept, whatever the
    resolver would now say), the registry heal; then — after a cold start that restored the grid — headroom again;
    then the ONE pane command `agents_up.sh --pane-cmd <root> <name> <sid> --new` handed to place_pane unchanged."""
    root, name = ctx.root, ctx.name
    facts = {"--coordinator": ctx.coordinator}
    if ctx.item:
        facts["--item"] = ctx.item
    if ctx.cold == "empty":
        spawn = {"FABRIK_SPAWN_NAME": name, "FABRIK_SPAWN_COORDINATOR": ctx.coordinator}
        if ctx.item:
            spawn["FABRIK_SPAWN_ITEM"] = ctx.item
        out = _agents_up(6, "--detach", root, spawn=spawn)
        if out.returncode != 0:
            raise RefusedError(
                f"agents_up.sh --detach (the grid's first pane, {name}) exited {out.returncode}: "
                f"{out.stderr.strip() or '(no stderr)'}",
                6,
            )
        print(f"agents_spawn: step 6 — the grid was started with {name} as its first pane")
        return
    sess = session_name(root)
    panes = live_panes(sess)
    adopted = _adopt(panes, name, ctx.sid)
    try:
        heal_registry(root, panes)
    except (RefusedError, OSError) as exc:
        reason = exc.reason if isinstance(exc, RefusedError) else str(exc)
        raise RefusedError(f"the registry could not be healed: {reason}", 6) from None
    if adopted is not None:
        print(f"agents_spawn: step 6 — {name}'s live pane {adopted.pane_id} is adopted")
        return
    if ctx.cold == "up":
        check_headroom(6, " after the cold start")
    args = ["--pane-cmd", root, name, ctx.sid, "--new"]
    for flag, value in facts.items():
        args += [flag, value]
    out = _agents_up(6, *args)
    cmd = out.stdout.rstrip("\n")
    if out.returncode != 0 or not cmd or "\n" in cmd:
        raise RefusedError(
            f"agents_up.sh --pane-cmd exited {out.returncode}: "
            f"{out.stderr.strip() or ('(no stderr)' if out.returncode else 'no single command line')}",
            6,
        )
    placed = place_pane(root, sess, name, ctx.sid, _worktree_dir(ctx), cmd)
    print(f"agents_spawn: step 6 — {name} launched in pane {placed.pane_id} ({placed.window_id})")


def regenerate_launchers(ctx: Spawn) -> None:
    """D2 (7), D5 — T08c: regenerate the launchers under the desktop lock, never the agents lock. Nothing yet."""


# ---- the verb -----------------------------------------------------------------------------------------------------


def _rerun_hint(ctx: Spawn) -> str:
    return "agents_up.sh add " + " ".join(ctx.argv)


def add(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="agents_up.sh add", allow_abbrev=False)
    ap.add_argument("repo")
    ap.add_argument("name")
    ap.add_argument("--role", default="builder")
    ap.add_argument("--item")
    args = ap.parse_args(argv)
    root = os.path.realpath(args.repo)
    ctx = Spawn(root=root, name=args.name, role=args.role, item=args.item, argv=list(argv))
    step = 1
    try:
        if not os.path.isdir(root):
            raise RefusedError(f"{args.repo} is not a directory")
        ctx.scope = git_common_dir(root)
        with agents_lock(root) as fd:
            preflight(ctx)
            step = 2
            make_worktree(ctx)
            step = 3
            cold_start(ctx)
            step = 4
            bind(ctx, fd)
            step = 5
            assign_item(ctx)
            step = 6
            place_and_launch(ctx)
        step = 7
        regenerate_launchers(ctx)  # unlocked: the desktop lock alone (panel PF3)
    except Exception as raised:  # noqa: BLE001 — every failure is a recorded refusal at its step, never a traceback
        exc = (
            raised
            if isinstance(raised, RefusedError)
            else RefusedError(f"{type(raised).__name__}: {raised}", step)
        )
        if exc.step is None:
            exc.step = step
        record_refusal(root, ctx.name, exc.step, exc.reason)
        print(f"agents_spawn: {exc.reason}", file=sys.stderr)
        print(
            f"add stopped at step {exc.step} ({ctx.name}) — re-run: {_rerun_hint(ctx)}",
            file=sys.stderr,
        )
        return 2
    print(
        f"agents_spawn: {ctx.name} added in {root} (session {ctx.sid}, worktree {_worktree_dir(ctx)})"
    )
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] != "add":
        print(
            "usage: agents_spawn.py add <repo> <name> [--role <role>] [--item <W-id>]",
            file=sys.stderr,
        )
        return 2
    return add(argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
