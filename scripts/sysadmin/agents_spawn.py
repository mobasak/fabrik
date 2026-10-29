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
    (3) cold start     — no tmux session: `agents_up.sh --detach <root>` (exit 0 restored the grid: wait for it to
                         settle; exit 3 no builder: step 6 starts the grid with the new one)
    (4) the binding    — `whoami_agent.py --spawned` under the held lock; plus the registry row where one exists
    (5) the item       — `work.py assign <W-id> --owner <name>` on the main checkout, never committed here
    (6) place + launch — adoption, the registry heal, headroom again after a cold start, then the one pane command
                         `agents_up.sh --pane-cmd … --new` placed by `place_pane` (or the second `--detach`)
    — the lock is released —
    (7) the launchers  — `agents_bat.py --tabbed` (it takes the desktop lock), and when step 6 opened `agents-<k>`
                         (k >= 2) a live `wt.exe -w fabrik-agents new-tab` attaching `=<S>+<k>`; every failure here is
                         said on stderr and `add` still exits 0 (spec § Lifecycle)

Each step checks its own artifact first and skips when it is there, so a re-run completes what a failed run left; a
failing step leaves the earlier ones and says which step to re-run. Every refusal exits 2 and appends one JSON line
`{"at", "repo", "name", "step", "reason"}` to `~/.claude/state/agents-spawn.jsonl` (a state record beside
`rotations.jsonl`, never a logfile).

`agents_up.sh remove <repo> <name>` (T09, spec D7) retires a builder under the same lock — see `remove()`: every
check that would lose work refuses (all named in one row carrying `"verb": "remove"`), then the pane, the worktree
(never --force), the branch (only an ancestor of the base), the registry row, and the launchers outside the lock.

COBRA (D-253): the cheapest way to pass the preflight without its outcome is FABRIK_AGENTS_UNCAPPED=1 left in a
profile — it also skips the headroom floor, since no slice exists to measure — so every run that uses it says so on
stderr; and a coordinator could hand-edit the trust entry, which is the operator's own act either way.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import glob
import importlib.util
import json
import math
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
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
    # the settle bound step 3 validated (FABRIK_AGENTS_SETTLE_S); step 6's no-builder waits reuse it
    settle: float = 0.0
    # step 6's PlaceResult.new_window_k and window_id: k is None when this add opened no new window (a split, an
    # adoption, the grid's first pane); step 7 reads both
    new_window_k: int | None = None
    new_window_id: str = ""
    # the repo's /opt ENTRY name as the caller gave it (unresolved; agents_bat.py titles its tabs by it), else root's
    entry: str = ""


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


def record_refusal(repo: str, name: str, step: int, reason: str, verb: str = "") -> None:
    """One JSON line; a `remove` refusal also carries `"verb": "remove"` (an `add` row keeps its five keys)."""
    path = spawn_log_path()
    row = {"at": int(time.time()), "repo": repo, "name": name, "step": step, "reason": reason}
    if verb:
        row["verb"] = verb
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
    if _coordinator_name(role):  # T10 F3: a builder pane never runs under a coordinator charter
        raise RefusedError(
            f"--role {role!r} is a coordinator role — a coordinator gets no builder pane"
        )
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
    if not NAME_RE.fullmatch(
        ctx.coordinator
    ):  # T10 F2: whoami's grammar is wider than the launcher's
        raise RefusedError(
            f"the caller is bound as {ctx.coordinator!r}: whoami accepts it ([a-z0-9-]{{1,32}}) but agents_up.sh's "
            "name grammar ([a-z0-9][a-z0-9-]{0,31}) does not — re-bind with whoami_agent.py --as <name>"
        )
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


def _agents_up(
    step: int, *args: str, spawn: dict[str, str] | None = None, timeout: float | None = None
):
    """Run agents_up.sh with `args` (bounded by `timeout`, default AGENTS_UP_TIMEOUT_S). The FABRIK_SPAWN_* variables are
    the caller's to set for THIS call only (`spawn`); any the environment carries are dropped, so a stale one never
    reaches another verb's first prompt."""
    env = {k: v for k, v in os.environ.items() if k not in SPAWN_VARS}
    env.update(spawn or {})
    try:
        return subprocess.run(
            [_agents_up_path(), *args],
            capture_output=True,
            text=True,
            timeout=AGENTS_UP_TIMEOUT_S if timeout is None else timeout,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RefusedError(
            f"agents_up.sh {args[0]} could not run: {type(exc).__name__}: {exc}", step
        ) from None


def _settle_s() -> float:
    """FABRIK_AGENTS_SETTLE_S (default 20): a finite number of seconds from 0 to AGENTS_UP_TIMEOUT_S (300). Read BEFORE
    the first --detach, so a bad value refuses at step 3 with nothing started."""
    raw = os.environ.get("FABRIK_AGENTS_SETTLE_S") or "20"
    bad = f"FABRIK_AGENTS_SETTLE_S={raw!r} is not a number of seconds"
    try:
        value = float(raw)
    except ValueError:
        raise RefusedError(bad, 3) from None
    if not math.isfinite(value):  # nan, inf, 1e999 (float() reads it as inf)
        raise RefusedError(
            f"FABRIK_AGENTS_SETTLE_S={raw!r} is not a finite number of seconds (0 to {AGENTS_UP_TIMEOUT_S})",
            3,
        )
    if value < 0:
        raise RefusedError(
            f"FABRIK_AGENTS_SETTLE_S={raw!r} is negative — 0 to {AGENTS_UP_TIMEOUT_S} seconds", 3
        )
    if value > AGENTS_UP_TIMEOUT_S:
        raise RefusedError(
            f"FABRIK_AGENTS_SETTLE_S={raw!r} is over the bound — at most {AGENTS_UP_TIMEOUT_S} seconds",
            3,
        )
    return value


def _all_running(root: str, timeout: float) -> bool:
    """`agents_up.sh --print <root>` (bounded by `timeout`): every `pane <name> <sid> <dir> <status>` line reads
    `running` (no builder at all, exit 3, is settled too). A report that cannot run (exec failure, timeout), fails, or
    is unreadable is NOT settled — the wait goes on to its bound."""
    try:
        out = _agents_up(3, "--print", root, timeout=timeout)
    except RefusedError:
        return False
    if out.returncode == 3:
        return True
    if out.returncode != 0:
        return False
    states = [ln.split()[-1] for ln in out.stdout.splitlines() if ln.startswith("pane ")]
    return all(s == "running" for s in states)


def _settle(root: str, bound: float) -> None:
    """PF4: wait until every restored pane reads `running`, or `bound` seconds elapse; each `--print` is cut off at the
    time left, so a slow report never overruns the bound by more than one poll."""
    deadline = time.monotonic() + bound
    while True:
        left = deadline - time.monotonic()
        if left > 0 and _all_running(root, min(AGENTS_UP_TIMEOUT_S, left)):
            return
        left = deadline - time.monotonic()
        if left <= 0:
            print(
                "agents_spawn: step 3 — the restored panes did not all read running in time; measuring anyway",
                file=sys.stderr,
            )
            return
        time.sleep(min(SETTLE_POLL_S, left))


def _spawn_facts(ctx: Spawn) -> dict[str, str]:
    """The FABRIK_SPAWN_* set naming this builder's first-prompt facts (agents_up.sh reads them on --detach)."""
    facts = {"FABRIK_SPAWN_NAME": ctx.name, "FABRIK_SPAWN_COORDINATOR": ctx.coordinator}
    if ctx.item:
        facts["FABRIK_SPAWN_ITEM"] = ctx.item
    return facts


def cold_start(ctx: Spawn) -> None:
    """D2 (3), D4: when the repo has no tmux session, `agents_up.sh --detach <root>` first. Exit 0 restored every
    registered builder (wait for them to settle; step 6 measures again); exit 3 had no builder and started nothing
    (step 6 runs --detach again once the binding exists); any other exit stops `add` here with its stderr. A re-run
    whose earlier add already bound the name (an unstarted spawn the grid will now start) passes its facts too."""
    sess = session_name(ctx.root)
    try:
        up = _has_session(sess)
    except RefusedError as exc:  # FABRIK_TMUX is not a command
        raise RefusedError(exc.reason, 3) from None
    if up:
        return
    bound = ctx.settle = _settle_s()
    spawn = _spawn_facts(ctx) if _bound_sid(ctx) else None
    out = _agents_up(3, "--detach", ctx.root, spawn=spawn)
    if out.returncode == 0:
        ctx.cold = "up"
        print(f"agents_spawn: step 3 — no {sess} session: the grid was started with its builders")
        _settle(ctx.root, bound)
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


def _claude_procs(pane_id: str, pane_pid: int, want: str | None) -> list[tuple[int, str]]:
    """(pid, argv session id) of every claude process under `pane_pid` (itself included), walked RECURSIVELY: a capped
    pane is the pane's shell → systemd-run --scope → bash -c → claude, an uncapped one shell → claude. A claude is a
    process whose argv[0] is `claude` (any directory); "" stands for a claude carrying no id. The walk stops as soon as
    a claude carrying `want` is found (`want=None`: never — the whole tree); a tree larger than the walk's bound without
    it refuses: a partial walk could miss the claude and read as "runs no claude"."""
    proc = _proc_root()
    found: list[tuple[int, str]] = []
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
            found.append((pid, _sid_of(argv)))
            if want is not None and found[-1][1] == want:
                return found
        stack.extend(_children(proc, pid))
    return found


def _claude_sids(pane_id: str, pane_pid: int, want: str) -> list[str]:
    """The argv session id of every claude under the pane (`_claude_procs`), the walk stopping at one carrying `want`."""
    return [sid for _, sid in _claude_procs(pane_id, pane_pid, want)]


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


_SID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)  # agents_up.sh's SID


def _session_files(home: Path) -> list[Path]:
    """Claude's per-process session records — hibernate.py::_session_files, mirrored (rotate_session.py reads it)."""
    seen: set[str] = set()
    out: list[Path] = []
    for pattern in (
        str(home / ".claude*" / "sessions" / "*.json"),
        str(home / ".claude-fleet" / "*" / "sessions" / "*.json"),
    ):
        for f in sorted(glob.glob(pattern)):
            real = os.path.realpath(f)
            if real not in seen:
                seen.add(real)
                out.append(Path(f))
    return out


def _proc_start(proc: Path, pid: int) -> str | None:
    """`/proc/<pid>/stat` field 22, the start time — hibernate.py::_proc_start, mirrored."""
    try:
        return (proc / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def _live_session_id(pid: int) -> str | None:
    """The session a claude process runs NOW: its session record matched by pid AND start time (rotate_session.py::
    _registry) — never its argv, which a /clear leaves on the old id. None when no record matches."""
    start = _proc_start(_proc_root(), pid)
    if start is None:
        return None
    for f in _session_files(Path.home()):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("pid") == pid and str(d.get("procStart")) == str(start):
            sid = d.get("sessionId")
            return sid if isinstance(sid, str) else ""
    return None


def heal_registry(root: str, panes: list[_Pane]) -> None:
    """PF3: re-point each `.fabrik/session-agents.json` row whose name has ONE live pane (tagged `@agent <name>`) whose
    claude runs ONE session other than the row's — a rotation that could not take the agents lock left the row on the
    old id. The live session is read from each claude's session record by pid + start time (as rotate_session.py does),
    never from its argv: a rotation /clears the same process, whose argv keeps the old id forever. PRECONDITION: the
    caller holds the repo's agents lock (`add` step 6; T09's verbs). No registry file: nothing is touched. A row is KEPT
    (said on stderr where a pane was seen) when: no pane, two panes, no claude, a claude with no matching record, two
    different live ids, a tree too large to read, an id that is not a session id (agents_up.sh's SID shape), or an id
    another name's row already holds. One atomic replace, only when a row changed."""
    reg = _read_registry(root)
    if reg is None:
        return
    healed = dict(reg)

    def kept(name: str, why: str) -> None:
        print(f"agents_spawn: registry row for {name} kept ({why})", file=sys.stderr)

    for name in sorted(set(reg.values())):
        tagged = [p for p in panes if p.agent == name]
        if len(tagged) != 1:
            continue
        rows = [sid for sid, n in reg.items() if n == name]
        try:
            pids = [pid for pid, _ in _claude_procs(tagged[0].pane_id, tagged[0].pane_pid, None)]
        except RefusedError as exc:
            kept(name, exc.reason)
            continue
        if not pids:
            continue
        live = {pid: _live_session_id(pid) for pid in pids}
        missing = [str(pid) for pid, sid in live.items() if sid is None]
        if missing:
            kept(
                name,
                f"no session record matches claude pid {', '.join(missing)} and its start time",
            )
            continue
        ids = set(live.values())
        if len(ids) != 1:
            kept(name, f"its pane runs {len(ids)} different sessions")
            continue
        new = ids.pop()
        if new in rows:
            continue
        if not _SID_RE.fullmatch(new):
            kept(name, f"its live session {new!r} is not a session id")
            continue
        if new in healed and healed[new] != name:
            kept(
                name,
                f"its live session {new} is already {healed[new]}'s row — fix the registry by hand",
            )
            continue
        healed = {sid: n for sid, n in healed.items() if n != name}
        healed[new] = name
        print(
            f"agents_spawn: registry row for {name} re-pointed {', '.join(rows)} -> {new} (its live session record)",
            file=sys.stderr,
        )
    if healed != reg:
        _replace_registry(root, healed)


def _building_live(value: str) -> bool:
    """agents_up.sh::building_live, mirrored: `@agents_up_building` is `<pid>:<start time>` and counts only while that
    pid answers `kill -0` AND its /proc start time is still the stored one. Anything malformed reads "not building"."""
    m = re.fullmatch(r"([1-9][0-9]*):([0-9]+)", value)
    if not m:
        return False
    try:
        os.kill(int(m.group(1)), 0)
    except (OSError, OverflowError):  # kill -0 fails on ESRCH and EPERM alike
        return False
    return _proc_start(Path("/proc"), int(m.group(1))) == m.group(
        2
    )  # agents_up.sh reads /proc itself


def _building(sess: str) -> bool:
    """Another agents_up.sh start is still building `<S>` (its `@agents_up_building` option names a live builder)."""
    out = _tmux("show-options", "-t", f"={sess}:", "-v", "@agents_up_building")
    return out.returncode == 0 and _building_live(out.stdout.strip())


def _await_claude(sess: str, name: str, deadline: float) -> list[_Pane]:
    """P1: right after the second --detach, the pane tagged `name` may still be `sh → systemd-run --scope → bash -c`
    with no claude yet. While exactly one pane carries the tag and its tree holds no claude, re-read every
    SETTLE_POLL_S until `deadline`; returns the last live read (`_adopt` then decides — a different session refuses at
    once, a claude still absent refuses with its own text)."""
    while True:
        panes = live_panes(sess)
        tagged = [p for p in panes if p.agent == name]
        if len(tagged) != 1 or _claude_procs(tagged[0].pane_id, tagged[0].pane_pid, None):
            return panes
        left = deadline - time.monotonic()
        if left <= 0:
            return panes
        time.sleep(min(SETTLE_POLL_S, left))


def place_and_launch(ctx: Spawn) -> None:
    """D2 (6), D1, D4. After a cold start that found no builder, `agents_up.sh --detach` AGAIN makes the grid with this
    builder as its first pane (it now resolves: binding and worktree in place, no transcript). Its exit 0 is not
    trusted alone — it also exits 0 when another --detach raced it and the grid was already up — so, within the settle
    bound step 3 validated, it waits while another start still builds the grid (still building at the bound refuses:
    never a second launch) and for the new pane's claude to start; then the live read: a pane of the name running its
    bound session is adopted (DONE); none falls through to the normal path.
    The normal path: the live read, adoption (a live pane of the name running its bound session is kept, whatever the
    resolver would now say), the registry heal (housekeeping: a failure is said, never a refusal); then — after a cold
    start that restored the grid — headroom again; then the ONE pane command `agents_up.sh --pane-cmd <root> <name>
    <sid> --new` handed to place_pane unchanged."""
    root, name = ctx.root, ctx.name
    sess = session_name(root)
    facts = {"--coordinator": ctx.coordinator}
    if ctx.item:
        facts["--item"] = ctx.item
    if ctx.cold == "empty":
        out = _agents_up(6, "--detach", root, spawn=_spawn_facts(ctx))
        if out.returncode != 0:
            raise RefusedError(
                f"agents_up.sh --detach (the grid's first pane, {name}) exited {out.returncode}: "
                f"{out.stderr.strip() or '(no stderr)'}",
                6,
            )
        deadline = time.monotonic() + ctx.settle
        while _building(
            sess
        ):  # P2: another start still placing panes — falling through could launch a second one
            left = deadline - time.monotonic()
            if left <= 0:
                raise RefusedError(f"another start is building the {sess} grid — re-run add", 6)
            time.sleep(min(SETTLE_POLL_S, left))
        panes = _await_claude(sess, name, deadline)
        tagged = [p for p in panes if p.agent == name]
        if len(tagged) == 1 and not _claude_procs(tagged[0].pane_id, tagged[0].pane_pid, None):
            # a claude only slow to start: never the respawn advice, which would kill it (Q1)
            raise RefusedError(
                f"{name}'s new pane started no claude within the settle bound ({ctx.settle:g} s) — "
                "re-run add once it starts",
                6,
            )
    else:
        panes = live_panes(sess)
    adopted = _adopt(panes, name, ctx.sid)
    try:
        heal_registry(root, panes)
    except (RefusedError, OSError) as exc:
        reason = exc.reason if isinstance(exc, RefusedError) else str(exc)
        print(f"agents_spawn: step 6 — registry heal skipped: {reason}", file=sys.stderr)
    if adopted is not None:
        if ctx.cold == "empty":
            print(f"agents_spawn: step 6 — the grid was started with {name} as its first pane")
        else:
            print(f"agents_spawn: step 6 — {name}'s live pane {adopted.pane_id} is adopted")
        return
    if ctx.cold == "empty":
        print(
            f"agents_spawn: step 6 — the grid came up without {name} (another start raced this one); launching it",
            file=sys.stderr,
        )
    if ctx.cold == "up":
        check_headroom(6, " after the cold start")
    args = ["--pane-cmd", root, name, ctx.sid, "--new"]
    for flag, value in facts.items():
        args += [flag, value]
    out = _agents_up(6, *args)
    cmd = (
        out.stdout[:-1] if out.stdout.endswith("\n") else out.stdout
    )  # exactly ONE trailing newline
    if out.returncode != 0 or not cmd or "\n" in cmd:
        raise RefusedError(
            f"agents_up.sh --pane-cmd exited {out.returncode}: "
            f"{out.stderr.strip() or ('(no stderr)' if out.returncode else 'no single command line')}",
            6,
        )
    placed = place_pane(root, sess, name, ctx.sid, _worktree_dir(ctx), cmd)
    ctx.new_window_k, ctx.new_window_id = placed.new_window_k, placed.window_id
    print(f"agents_spawn: step 6 — {name} launched in pane {placed.pane_id} ({placed.window_id})")


# ---- step 7: the launchers (T08c) -------------------------------------------------------------------------------
# Spec D5 + § Lifecycle's degradation rule: the .bat is the source of truth at every click, so nothing here can fail
# `add` — a generator that fails, a desktop never remembered, a wt.exe missing or failing, a distro that cannot be
# derived: each is SAID on stderr and step 7 returns; the next add/remove regenerates the .bat.

WT_WINDOW = "fabrik-agents"  # agents_bat.py::WINDOW — the named Windows Terminal window the tabbed .bat opens
WT_GLOB = "/mnt/c/Users/*/AppData/Local/Microsoft/WindowsApps/wt.exe"
WT_TIMEOUT_S = 30.0
# agents_bat.py asks agents_up.sh --print once per /opt repo, outside its desktop lock
LAUNCHER_TIMEOUT_S = 300

_deck: object = None


def _load_deck():
    """fabrik_deck.py loaded by path, once (agents_bat.py::_load_deck): `_default_distro`, the ONE distro resolver."""
    global _deck
    if _deck is None:
        spec = importlib.util.spec_from_file_location(
            "fabrik_deck_for_agents_spawn", Path(__file__).with_name("fabrik_deck.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _deck = mod
    return _deck


def _agents_bat_path() -> str:
    """agents_bat.py — FABRIK_AGENTS_BAT (tests run a fake or a wrapper), else the one beside this script."""
    return os.environ.get("FABRIK_AGENTS_BAT") or str(Path(__file__).with_name("agents_bat.py"))


def _wt_exe() -> tuple[str, str]:
    """(wt.exe, '') or ('', why none): $FABRIK_WT_EXE, else `wt.exe` on PATH, else the single WT_GLOB match."""
    env = os.environ.get("FABRIK_WT_EXE")
    if env:
        return env, ""
    found = shutil.which("wt.exe")
    if found:
        return found, ""
    matches = sorted(glob.glob(WT_GLOB))
    if len(matches) == 1:
        return matches[0], ""
    if not matches:
        return "", f"wt.exe not found ($FABRIK_WT_EXE unset, not on PATH, no {WT_GLOB})"
    return "", f"wt.exe is ambiguous: {len(matches)} matches of {WT_GLOB}"


def _say7(text: str) -> None:
    print(f"agents_spawn: step 7 — {text}", file=sys.stderr)


def _run_agents_bat(distro: str) -> bool:
    """`agents_bat.py --tabbed [--distro D]` (no --desktop: the remembered folder). Its stderr notes ("no desktop
    remembered", a refusal) and its own status lines reach the caller; the .bat text it prints when no desktop is
    remembered does not. True only when it exited 0 having written (or found current) a .bat on the desktop."""
    args = [sys.executable, _agents_bat_path(), "--tabbed"]
    if distro:
        args += ["--distro", distro]
    try:
        out = subprocess.run(
            args,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=LAUNCHER_TIMEOUT_S,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _say7(
            f"agents_bat.py --tabbed could not run ({type(exc).__name__}: {exc}); "
            "the .bat is regenerated at the next add or remove"
        )
        return False
    status = [ln for ln in out.stdout.splitlines() if ln.startswith("agents_bat:")]
    for line in status:
        print(line)
    if out.stderr:
        sys.stderr.write(out.stderr if out.stderr.endswith("\n") else out.stderr + "\n")
    if out.returncode != 0:
        _say7(
            f"agents_bat.py --tabbed exited {out.returncode}; the .bat is regenerated at the next add or remove"
        )
        return False
    return any(ln.startswith("agents_bat: wrote ") or ln.endswith(" is current") for ln in status)


def _overflow_ready(sess: str, k: int, window_id: str) -> bool:
    """`<S>+<k>` exists and lists the window step 6 opened — `_ensure_overflow` only SAYS its failures, so a new window
    k does not prove its session is there (one bounded `list-windows`; a tmux that cannot run reads not ready)."""
    if not window_id:
        return False
    try:
        out = _tmux("list-windows", "-t", f"={sess}+{k}", "-F", "#{window_id}")
    except RefusedError:  # FABRIK_TMUX is not a command
        return False
    return out.returncode == 0 and window_id in out.stdout.split()


def _append_tab(ctx: Spawn, k: int, distro: str, bat_written: bool) -> None:
    """D5's live tab: `wt.exe -w fabrik-agents new-tab … tmux attach -t =<S>+<k>` (the overflow session, T03)."""
    later = "; the .bat opens it at the next click" if bat_written else ""
    if not distro:
        _say7("no WSL distro could be derived — tab not appended")
        return
    sess = session_name(ctx.root)
    if not _overflow_ready(sess, k, ctx.new_window_id):
        _say7(f"{sess}+{k} is not ready — tab not appended{later}")
        return
    wt, why = _wt_exe()
    if not wt:
        _say7(f"{why} — tab not appended{later}")
        return
    repo = ctx.entry or os.path.basename(ctx.root)
    title = f"{repo[:1].upper()}{repo[1:]} Agents {k}"  # agents_bat.py::tabbed_text's title for window k
    argv = [
        wt,
        "-w",
        WT_WINDOW,
        "new-tab",
        "--suppressApplicationTitle",  # as the .bat's tabs: tmux and wsl never overwrite the title
        "--title",
        title,
        "wsl.exe",
        "--distribution",
        distro,
        "--exec",
        "tmux",
        "attach",
        "-t",
        f"={sess}+{k}",
    ]
    try:
        out = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=WT_TIMEOUT_S,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _say7(
            f"wt.exe ({wt}) could not run ({type(exc).__name__}: {exc}) — tab not appended{later}"
        )
        return
    if out.returncode != 0:
        _say7(
            f"wt.exe ({wt}) exited {out.returncode}: {out.stderr.strip() or '(no stderr)'}"
            f" — tab not appended{later}"
        )
        return
    print(f'agents_spawn: step 7 — tab "{title}" appended to the {WT_WINDOW} window')


def regenerate_launchers(ctx: Spawn) -> None:
    """D2 (7), D5 — outside the agents lock (agents_bat.py takes the desktop lock itself, panel PF3). The distro is
    derived once in this process (C8) and passed to agents_bat.py only when non-empty — agents_bat.py derives it again
    only when --distro is omitted; the live tab is appended only when step 6 opened an overflow window `agents-<k>`
    (k >= 2) whose `<S>+<k>` is ready — a re-created `agents` (k = 1) is the .bat's first tab, `<S>` itself. Every
    failure is said; `add` runs this outside its refusal handling and still exits 0."""
    try:
        distro = _load_deck()._default_distro()
    except Exception as exc:  # noqa: BLE001 — the resolver's failure is a said '' distro, never a refusal
        _say7(f"the distro resolver failed ({type(exc).__name__}: {exc})")
        distro = ""
    written = _run_agents_bat(distro)
    if ctx.new_window_k is not None and ctx.new_window_k >= 2:
        _append_tab(ctx, ctx.new_window_k, distro, written)


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
    ctx.entry = os.path.basename(os.path.abspath(args.repo))
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
    # step 7, unlocked (the desktop lock alone, panel PF3) and OUTSIDE the refusal handling above: the builder is
    # placed, so nothing here may become a refusal row or exit 2 — any escape is said and add still exits 0
    try:
        regenerate_launchers(ctx)
    except Exception as exc:  # noqa: BLE001 — a launcher failure never undoes a placed builder
        _say7(
            f"the launchers failed ({type(exc).__name__}: {exc}); "
            "the .bat is regenerated at the next add or remove"
        )
    print(
        f"agents_spawn: {ctx.name} added in {root} (session {ctx.sid}, worktree {_worktree_dir(ctx)})"
    )
    return 0


# ---- remove (T09) -------------------------------------------------------------------------------------------------
# Spec § The delta D7, D4's remove half, D9's guard. Under the repo's agents lock: (1) the checks — every failing one
# named in ONE refusal; (2) the pane; (3) `git worktree remove` (never --force); (4) the branch, deleted only when an
# ancestor of the base; (5) the registry row and the heal; then, unlocked, the launchers (add's step 7).
# COBRA (D-253): the cheapest way past the ignored-file check without its outcome is a too-wide `remove_ignored_ok`
# entry — a top-level directory such as `data/`, or one entry per ignored name — the coordinator's store edit, reviewed
# like any config change; every path let go is printed, so a too-wide entry shows on the first run. (`/` cannot be
# that entry: `_ok_prefixes` refuses an entry that is only slashes as malformed. `.` lets nothing go: `_prefix_ok`
# matches `.` or `./…`, and `ls-files` never prints a path in that form.)

REGENERABLE = (
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)
LOST_NAMED = 20  # T10 F8: the lost files one refusal names before it counts the rest
_PLAIN_SID_RE = re.compile(
    r"[A-Za-z0-9_-]+"
)  # a record filename command_run.py::_safe_sid leaves unchanged


def _command_runs_dir() -> Path:
    """command_run.py::_state_dir — `$COMMAND_RUN_DIR`, else `~/.claude/state/command-runs`."""
    raw = os.environ.get("COMMAND_RUN_DIR")
    return Path(raw) if raw else Path.home() / ".claude" / "state" / "command-runs"


def _base_ref(root: str, base: str) -> str:
    for ref in (f"refs/heads/{base}", f"refs/remotes/origin/{base}"):
        if _git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}").returncode == 0:
            return ref
    raise RefusedError(f"the base branch {base!r} has no local or origin ref in {root}")


def _owned_ids(root: str, scope: str, name: str, reg: dict | None) -> list[str]:
    """Every session id the name owns: its registry rows AND every id the identity store binds to it in scope."""
    ids = [sid for sid, n in (reg or {}).items() if n == name]
    for row in _store_rows():
        sid = row.get("session_id")
        if (
            row.get("name") == name
            and row.get("toplevel") == scope
            and isinstance(sid, str)
            and sid
        ):
            ids.append(sid)
    return list(dict.fromkeys(ids))


def _running_failures(ids: list[str]) -> list[str]:
    fails = []
    state = _command_runs_dir()
    for sid in ids:
        if not _PLAIN_SID_RE.fullmatch(sid):
            fails.append(
                f"session id {sid!r} has no plain run-record name — check its record by hand"
            )
            continue
        path = state / f"{sid}.json"
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, ValueError) as exc:
            fails.append(f"the run record {path} cannot be read ({exc})")
            continue
        if isinstance(rec, dict) and "running" in (rec.get("state"), rec.get("status")):
            fails.append(f"session {sid} has a run record running ({path}) — let it close first")
    return fails


def _grid_state(sess: str) -> bool:
    """True when `<S>` is up, False when tmux answers that no server or no such session exists; anything else (a tmux
    that cannot run, an error it does not explain) refuses — never read as "the grid is down"."""
    out = _tmux("list-sessions", "-F", "#{session_name}")
    if out.returncode == 0:
        return sess in out.stdout.splitlines()
    err = out.stderr.strip()
    if "no server running" in err or ("error connecting to" in err and "No such file" in err):
        return False
    raise RefusedError(f"tmux read failed — not removing (list-sessions: {err or out.returncode})")


def _ok_prefixes(root: str) -> list[str]:
    """`remove_ignored_ok` from `<root>/.fabrik/work/config.json` (path prefixes); absent is []; malformed refuses."""
    path = os.path.join(root, ".fabrik", "work", "config.json")
    try:
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        raise RefusedError(f"{path} cannot be read ({exc})") from None
    raw = cfg.get("remove_ignored_ok", []) if isinstance(cfg, dict) else None
    if not isinstance(raw, list) or not all(isinstance(p, str) and p.strip("/") for p in raw):
        raise RefusedError(f"{path}: remove_ignored_ok must be a list of path prefixes")
    return raw


def _prefix_ok(rel: str, prefixes: list[str]) -> bool:
    bare = rel.rstrip("/")
    for p in prefixes:
        q = p.rstrip("/")
        if bare == q or bare.startswith(q + "/"):
            return True
    return False


def _seed_texts() -> list[tuple[str, str]]:
    """(path, text) of every seed under `<state>/seeds/`; a symlinked seed is read through its link (pass-1 F1). A seed
    that is dangling, unreadable or not a regular file (a FIFO, or a link to one, would block a read for ever under the
    agents lock — pass-2 P2) refuses, every one named. Opened O_NONBLOCK and checked with fstat on the open descriptor,
    so a file swapped for a FIFO after the listing still never blocks. A real directory there is no seed and is skipped."""
    seeds = _command_runs_dir() / "seeds"
    if not os.path.lexists(seeds):
        return []
    texts = []
    bad = []
    try:
        entries = sorted(os.scandir(seeds), key=lambda e: e.name)
    except OSError as exc:
        raise RefusedError(f"the resume seeds in {seeds} cannot be listed ({exc})") from None
    for entry in entries:
        if entry.is_dir(follow_symlinks=False):
            continue
        try:
            fd = os.open(entry.path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        except OSError as exc:
            bad.append(f"the resume seed {entry.path} cannot be read ({exc})")
            continue
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                bad.append(f"the resume seed {entry.path} is not a regular file — not reading it")
                continue
            with os.fdopen(fd, "rb", closefd=False) as fh:
                texts.append((entry.path, fh.read().decode("utf-8", errors="replace")))
        except OSError as exc:
            bad.append(f"the resume seed {entry.path} cannot be read ({exc})")
        finally:
            os.close(fd)
    if bad:
        raise RefusedError("; ".join(bad))
    return texts


# pass-2 P1: ONE tail match, `.tmp/runs/<sid>/<run>`, whatever leads it (an absolute path, the repo-root-relative
# `.claude/worktrees/<name>/…`, `./`, a backtick or a quote): the character before `.tmp` is not a name character
# (`x.tmp` does not match), and the run name is not continued (`r1` never matches inside `r10` or `r1x`; `r1.`,
# `r1/f` and a backtick after it do). It also matches the same <sid>/<run> under ANOTHER checkout — over-refusal is
# the safe direction.
_SEED_START = r"(?<![A-Za-z0-9_.-])"
_SEED_END = r"(?![A-Za-z0-9_-])"


def _named_by_seed(folder: str, wt: str, texts: list[tuple[str, str]]) -> str:
    """The first seed naming `folder` by its `.tmp/runs/<sid>/<run>` tail on a boundary; "" when none does."""
    pat = re.compile(_SEED_START + re.escape(os.path.relpath(folder, wt)) + _SEED_END)
    for path, text in texts:
        if pat.search(text):
            return path
    return ""


def _walk_runs(wt: str, let_go: list[str], fails: list[str], texts: list[tuple[str, str]]) -> None:
    """`.tmp/runs/<sid>/<run>`, two levels by os.scandir (command_run.py's layout): a run folder a seed names refuses,
    any other is let go; a symlink or a file where a folder belongs refuses, named."""
    runs = os.path.join(wt, ".tmp", "runs")
    if os.path.islink(runs) or not os.path.isdir(runs):
        if os.path.lexists(runs):
            fails.append(f"ignored {runs} is not a plain directory")
        return
    try:
        for sid_dir in sorted(os.scandir(runs), key=lambda e: e.name):
            if not sid_dir.is_dir(follow_symlinks=False):
                fails.append(f"ignored {sid_dir.path} would be lost")
                continue
            for run in sorted(os.scandir(sid_dir.path), key=lambda e: e.name):
                if not run.is_dir(follow_symlinks=False):
                    fails.append(f"ignored {run.path} would be lost")
                elif seed := _named_by_seed(run.path, wt, texts):
                    fails.append(
                        f"the run folder {run.path} is named by the resume seed {seed} — keep it until that run resumes"
                    )
                else:
                    let_go.append(run.path)
    except OSError as exc:
        fails.append(f"{runs} cannot be read ({exc})")


def _ignored_failures(wt: str, root: str, let_go: list[str]) -> list[str]:
    """D7 + panel PF1: the ignored files `git worktree remove` would delete unasked, classified. `-z` (T10 F7): without
    it git C-quotes a non-ASCII or control-character name, and the quoted form matches no prefix and no file."""
    out = _git(wt, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory")
    if out.returncode != 0:
        return [f"git ls-files --ignored failed in {wt}: {out.stderr.strip() or out.returncode}"]
    fails: list[str] = []
    prefixes = _ok_prefixes(root)
    try:
        texts = _seed_texts()
    except RefusedError as exc:
        fails.append(exc.reason)
        texts = []
    walk_runs = False
    lost: list[str] = []

    def judge(rel: str) -> None:
        if any(seg in REGENERABLE for seg in rel.rstrip("/").split("/")) or _prefix_ok(
            rel, prefixes
        ):
            let_go.append(os.path.join(wt, rel))
        elif rel.endswith("/"):
            # `--directory` collapses a directory holding ONLY ignored paths (a `tests/` of nothing but
            # `__pycache__/`) to one entry: judge what it holds, never the collapsed name
            try:
                children = sorted(os.scandir(os.path.join(wt, rel)), key=lambda e: e.name)
            except OSError as exc:
                fails.append(f"{os.path.join(wt, rel)} cannot be read ({exc})")
                return
            for child in children:
                judge(rel + child.name + ("/" if child.is_dir(follow_symlinks=False) else ""))
        else:
            lost.append(os.path.join(wt, rel))

    for rel in out.stdout.split("\0"):
        if not rel:
            continue
        bare = rel.rstrip("/")
        if bare == ".tmp":
            tmp = os.path.join(wt, ".tmp")
            try:
                children = sorted(os.scandir(tmp), key=lambda e: e.name)
            except OSError as exc:
                fails.append(f"{tmp} cannot be read ({exc})")
                continue
            for child in children:
                if child.name == "runs":
                    walk_runs = True
                else:
                    judge(
                        f".tmp/{child.name}" + ("/" if child.is_dir(follow_symlinks=False) else "")
                    )
        elif bare == ".tmp/runs" or bare.startswith(".tmp/runs/"):
            walk_runs = True
        else:
            judge(rel)
    if lost:
        # T10 F8: a large tree names its first LOST_NAMED files and counts the rest exactly — never every file into
        # stderr and the refusal row
        named = ", ".join(lost[:LOST_NAMED])
        more = (
            f" … and {len(lost) - LOST_NAMED} more ({len(lost)} files)"
            if len(lost) > LOST_NAMED
            else ""
        )
        fails.append(f"ignored {named}{more} would be lost — delete or keep it by hand")
    if walk_runs:
        _walk_runs(wt, let_go, fails, texts)
    return fails


def _worktree_records(root: str) -> list[list[str]]:
    """`git worktree list --porcelain -z`, one list of attribute lines per worktree (`-z`, T10 F7: a path is never
    quoted); its first line is `worktree <path>`."""
    out = _git(root, "worktree", "list", "--porcelain", "-z")
    if out.returncode != 0:
        raise RefusedError(f"git worktree list failed: {out.stderr.strip() or out.returncode}")
    records: list[list[str]] = [[]]
    for field_ in out.stdout.split("\0"):
        if field_:
            records[-1].append(field_)
        elif records[-1]:
            records.append([])
    return [r for r in records if r and r[0].startswith("worktree ")]


def _lock_reason(root: str, wt: str) -> str | None:
    """T10 F10: None when `wt` is not locked; else its lock reason ("" when it gave none)."""
    for rec in _worktree_records(root):
        if os.path.realpath(rec[0][len("worktree ") :]) != os.path.realpath(wt):
            continue
        for line in rec[1:]:
            if line == "locked" or line.startswith("locked "):
                return line[len("locked ") :]
    return None


def _kept_elsewhere(root: str, wt: str, ids: list[str]) -> list[str]:
    """D6: the name's run folders under ANOTHER checkout's `.tmp/runs/<sid>/` — listed, never touched."""
    kept = []
    for rec in _worktree_records(root):
        tree = rec[0][len("worktree ") :]
        if os.path.realpath(tree) == os.path.realpath(wt):
            continue
        for sid in ids:
            d = os.path.join(tree, ".tmp", "runs", sid)
            if os.path.isdir(d) and not os.path.islink(d):
                with contextlib.suppress(OSError):
                    kept += [e.path for e in sorted(os.scandir(d), key=lambda e: e.name)]
    return kept


@dataclass
class Removal:
    present: bool = False
    branch: str = ""
    base: str = ""
    base_ref: str = ""
    let_go: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)


def _check_removal(ctx: Spawn, wt: str, ids: list[str], tagged: list) -> Removal:
    """(1): every check; all failures collected into ONE refusal. A worktree already gone (a resumed remove) skips the
    worktree checks; the run-record check still applies, and the name must have a registry row, an in-scope binding
    (both are in `ids`) or a tagged pane."""
    rm = Removal(present=os.path.lexists(wt))
    if not rm.present and not (ids or tagged):
        raise RefusedError(f"no such builder {ctx.name} in {ctx.root}")
    fails = _running_failures(ids)
    if rm.present:
        if not _in_place(wt):
            fails.append(f"{wt} is not a linked git worktree")
        else:
            try:
                locked = _lock_reason(ctx.root, wt)
            except RefusedError as exc:
                fails.append(exc.reason)
            else:
                if locked is not None:
                    why = f" ({locked})" if locked else ""
                    fails.append(
                        f"{wt} is locked{why} — `git worktree unlock` it first, or keep it"
                    )
            # T10 F6: explicit flags — a user's `status.showUntrackedFiles=no` (or `ignoreSubmodules`) must never read
            # an untracked file or a dirty submodule as clean, which `git worktree remove` would then delete
            status = _git(
                wt, "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"
            )
            if status.returncode != 0:
                fails.append(
                    f"git status failed in {wt}: {status.stderr.strip() or status.returncode}"
                )
            elif status.stdout.strip():
                fails.append(
                    f"{wt} is not clean (git status --porcelain: {status.stdout.strip().splitlines()[0]} …)"
                )
            head = _git(wt, "symbolic-ref", "-q", "HEAD")
            ref = head.stdout.strip()
            if head.returncode == 1:
                fails.append(
                    f"{wt} has a detached HEAD — its commits sit on no branch; check out a branch first"
                )
            elif head.returncode != 0 or not ref.startswith("refs/heads/"):
                fails.append(
                    f"git symbolic-ref HEAD failed in {wt}: {head.stderr.strip() or head.returncode}"
                )
            else:
                rm.branch = ref[len("refs/heads/") :]
            try:
                rm.base = resolve_base(ctx.root)
                rm.base_ref = _base_ref(ctx.root, rm.base)
            except RefusedError as exc:
                fails.append(exc.reason)
            if rm.branch and rm.base_ref:
                ahead = _git(wt, "rev-list", f"{rm.base_ref}..HEAD")
                if ahead.returncode != 0:
                    fails.append(
                        f"git rev-list {rm.base}..HEAD failed: {ahead.stderr.strip() or ahead.returncode}"
                    )
                elif ahead.stdout.strip():
                    n = len(ahead.stdout.split())
                    up = _git(wt, "rev-list", "@{u}..HEAD")
                    if up.returncode != 0:
                        fails.append(
                            f"{rm.branch} has {n} commit(s) beyond {rm.base} and no upstream (never pushed) — push it"
                        )
                    elif up.stdout.strip():
                        fails.append(
                            f"{rm.branch} has {len(up.stdout.split())} commit(s) not pushed to its upstream — push it"
                        )
            fails += _ignored_failures(wt, ctx.root, rm.let_go)
    try:
        rm.kept = _kept_elsewhere(ctx.root, wt, ids)
    except RefusedError as exc:
        fails.append(exc.reason)
    if fails:
        raise RefusedError("; ".join(fails))
    return rm


def _drop_pane(sess: str, pane: _Pane) -> None:
    """(2): kill the pane; re-lay its window when it still exists, else kill that window's overflow session `<S>+<k>`
    (tmux removed the window itself, D4)."""
    gone = _tmux("kill-pane", "-t", pane.pane_id)
    if gone.returncode != 0:
        raise RefusedError(
            f"tmux kill-pane -t {pane.pane_id} failed: {gone.stderr.strip() or gone.returncode}", 2
        )
    still = _tmux("display-message", "-p", "-t", pane.window_id, "#{window_id}")
    if still.returncode == 0 and still.stdout.strip() == pane.window_id:
        if _tmux("select-layout", "-t", pane.window_id, "even-horizontal").returncode != 0:
            print(f"agents_spawn: could not re-lay window {pane.window_name}", file=sys.stderr)
        return
    k = _window_k(pane.window_name)
    if k is not None and k >= 2 and _has_session(f"{sess}+{k}"):
        killed = _tmux("kill-session", "-t", f"={sess}+{k}")
        if killed.returncode != 0:
            print(
                f"agents_spawn: could not kill the emptied window's session {sess}+{k} "
                f"({killed.stderr.strip() or killed.returncode})",
                file=sys.stderr,
            )


def _drop_branch(root: str, branch: str, base: str, base_ref: str) -> None:
    """(4): `git branch -D` ONLY after `merge-base --is-ancestor <branch> <base>` succeeds; an unmerged one is kept."""
    if not branch or branch == base:
        return
    if _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode != 0:
        return
    merged = _git(root, "merge-base", "--is-ancestor", f"refs/heads/{branch}", base_ref)
    if merged.returncode == 1:
        print(f"agents_spawn: branch {branch} is not merged into {base}; kept")
        return
    if merged.returncode != 0:
        raise RefusedError(
            f"git merge-base --is-ancestor {branch} {base} failed: {merged.stderr.strip()}", 4
        )
    gone = _git(root, "branch", "-D", branch)
    if gone.returncode != 0:
        raise RefusedError(f"could not delete the merged branch {branch}: {gone.stderr.strip()}", 4)
    print(f"agents_spawn: branch {branch} (merged into {base}) deleted")


def _drop_rows(root: str, sess: str, name: str) -> None:
    """(5): the name's rows dropped (only where a registry exists), then heal_registry for the rest (a failed live read
    or heal is said, never a refusal: the builder is already gone)."""
    reg = _read_registry(root)
    if reg is not None and name in reg.values():
        _replace_registry(root, {sid: n for sid, n in reg.items() if n != name})
    try:
        if _grid_state(sess):
            heal_registry(root, live_panes(sess))
    except (RefusedError, OSError) as exc:
        reason = exc.reason if isinstance(exc, RefusedError) else str(exc)
        print(f"agents_spawn: remove — registry heal skipped: {reason}", file=sys.stderr)


def _pane_live_ids(pane: _Pane) -> list[str]:
    """Pass-1 F4: every session the tagged pane's claude processes run NOW (heal_registry's reads: the walk, then each
    claude's session record by pid + start time), plus any id in their argv — so a rotation the registry has not caught
    up with is still checked under its live id. A claude whose live id cannot be read refuses, named; nothing is
    written."""
    ids = []
    unread = []
    for pid, argv_sid in _claude_procs(pane.pane_id, pane.pane_pid, None):
        live = _live_session_id(pid)
        if not live:
            unread.append(str(pid))
            continue
        ids.append(live)
        if argv_sid:
            ids.append(argv_sid)
    if unread:
        raise RefusedError(
            f"claude pid {', '.join(unread)} in pane {pane.pane_id} runs a session whose live id cannot be read "
            "(no session record matches its pid and start time) — not removing"
        )
    return ids


def remove(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="agents_up.sh remove", allow_abbrev=False)
    ap.add_argument("repo")
    ap.add_argument("name")
    args = ap.parse_args(argv)
    root = os.path.realpath(args.repo)
    ctx = Spawn(root=root, name=args.name, role="", item=None, argv=list(argv))
    ctx.entry = os.path.basename(os.path.abspath(args.repo))
    step = 1
    rm = Removal()
    try:
        if not os.path.isdir(root):
            raise RefusedError(f"{args.repo} is not a directory")
        if not NAME_RE.fullmatch(ctx.name):
            raise RefusedError(f"{ctx.name!r} is not an agent name ([a-z0-9][a-z0-9-]{{0,31}})")
        if _coordinator_name(ctx.name):
            raise RefusedError(f"{ctx.name!r} is a coordinator name — remove retires builders only")
        if _merge_owner(root) == ctx.name:  # T10 F9: add's refusal, mirrored
            raise RefusedError(
                f"{ctx.name!r} is the repo's merge owner (its coordinator) — remove retires builders only"
            )
        ctx.scope = git_common_dir(root)
        if not _is_main_checkout(root):
            raise RefusedError(f"{root} is not the repo's main checkout — pass the main checkout")
        with agents_lock(root):
            wt = _worktree_dir(ctx)
            sess = session_name(root)
            reg = _read_registry(root)
            ids = _owned_ids(root, ctx.scope, ctx.name, reg)
            try:
                panes = live_panes(sess) if _grid_state(sess) else []
                tagged = [p for p in panes if p.agent == ctx.name]
                if len(tagged) > 1:
                    raise RefusedError(
                        f"{len(tagged)} panes are tagged {ctx.name} ({', '.join(p.pane_id for p in tagged)}) — fix by hand"
                    )
                if tagged:  # T10 F11: the process walk's refusals are placement's wording too
                    ids = list(dict.fromkeys([*ids, *_pane_live_ids(tagged[0])]))
            except PlacementRefusedError as exc:
                raise RefusedError(exc.reason.replace("not placing", "not removing")) from None
            rm = _check_removal(ctx, wt, ids, tagged)
            step = 2
            if tagged:
                _drop_pane(sess, tagged[0])
            step = 3
            if rm.present:
                # pass-1 F5: the builder may have written until its pane died — classify again over the same ids,
                # and print `let go:` from this final classification only
                final: list[str] = []
                late = _running_failures(ids) + _ignored_failures(wt, root, final)
                if late:
                    raise RefusedError(
                        "after the pane was killed: "
                        + "; ".join(late)
                        + " — re-run remove once settled",
                        3,
                    )
                for path in final:
                    print(f"let go: {path}")
            else:
                # pass-1 F3: the worktree dir is gone but git may still register it, which would refuse the branch
                # delete for ever; prune only drops entries whose directory is gone
                pruned = _git(root, "worktree", "prune")
                if pruned.returncode != 0:
                    raise RefusedError(
                        f"git worktree prune failed: {pruned.stderr.strip() or pruned.returncode}",
                        3,
                    )
            if rm.present:
                # T10 F6: git's own clean check runs `git status` under the user's config — force untracked files
                # visible, so a file the dying builder wrote after step 1's check still refuses here
                out = _git(
                    root,
                    "-c",
                    "status.showUntrackedFiles=all",
                    "worktree",
                    "remove",
                    os.path.join(".claude", "worktrees", ctx.name),
                    timeout=120,
                )
                if out.returncode != 0:
                    raise RefusedError(
                        f"git worktree remove failed: {out.stderr.strip() or out.returncode}", 3
                    )
            step = 4
            branch = (
                rm.branch or f"worktree-{ctx.name}"
            )  # a resume knows only the spec's own branch name
            if (
                not rm.base_ref
                and _git(
                    root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"
                ).returncode
                == 0
            ):
                rm.base = resolve_base(root)
                rm.base_ref = _base_ref(root, rm.base)
            if rm.base_ref:
                _drop_branch(root, branch, rm.base, rm.base_ref)
            step = 5
            _drop_rows(root, sess, ctx.name)
    except Exception as raised:  # noqa: BLE001 — every failure is a recorded refusal at its step, never a traceback
        refusal = (
            raised
            if isinstance(raised, RefusedError)
            else RefusedError(f"{type(raised).__name__}: {raised}", step)
        )
        refusal.step = step
        record_refusal(root, ctx.name, step, refusal.reason, verb="remove")
        print(f"agents_spawn: {refusal.reason}", file=sys.stderr)
        print(
            f"remove stopped at step {step} ({ctx.name}) — re-run: agents_up.sh remove {' '.join(ctx.argv)}",
            file=sys.stderr,
        )
        return 2
    try:
        regenerate_launchers(ctx)
    except Exception as failed:  # noqa: BLE001 — a launcher failure never undoes a finished remove
        _say7(
            f"the launchers failed ({type(failed).__name__}: {failed}); "
            "the .bat is regenerated at the next add or remove"
        )
    for path in rm.kept:
        print(f"kept: {path}")
    print(f"agents_spawn: {ctx.name} removed from {root} (charter and transcript kept)")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("add", "remove"):
        print(
            "usage: agents_spawn.py add <repo> <name> [--role <role>] [--item <W-id>]\n"
            "       agents_spawn.py remove <repo> <name>",
            file=sys.stderr,
        )
        return 2
    return add(argv[1:]) if argv[0] == "add" else remove(argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
