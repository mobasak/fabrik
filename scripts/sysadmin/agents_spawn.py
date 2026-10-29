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
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

HUB = (
    Path(__file__).resolve().parents[2]
)  # the checkout this runs from — its scripts/ are the tools
AGENTS_LOCK = (
    "fabrik-agents.lock"  # whoami_agent.py::AGENTS_LOCK — the file its --spawned proof checks
)
NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")  # agents_up.sh NAME_RE
ITEM_RE = re.compile(r"W-[0-9a-f]{8}")  # agents_up.sh ITEM_RE
CHARTER_MARKER = "# Agent charter"  # .claude/hooks/agent_role.py::_CHARTER_MARKER
HEADROOM_FLOOR = 2 * 1024**3  # one Claude session is 1.3-3.6 GB (spec D6)
SLICE = "fabrik-agents.slice"
GIT_LOCATION_VARS = ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")
GIT_TIMEOUT_S = 30
REMOTE_TIMEOUT_S = 20


class RefusedError(Exception):
    """A refusal: exit 2, the reason named, one line in the spawn record."""

    def __init__(self, reason: str, step: int = 1) -> None:
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


def _whoami():
    """whoami_agent.py from THIS checkout — its store reader and liveness test, never a second copy."""
    spec = importlib.util.spec_from_file_location(
        "whoami_agent_for_spawn", HUB / "scripts" / "whoami_agent.py"
    )
    if spec is None or spec.loader is None:
        raise RefusedError(f"cannot load {HUB / 'scripts' / 'whoami_agent.py'}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- measurements -------------------------------------------------------------------------------------------------


def _cgroup_dir() -> Path:
    seam = os.environ.get("FABRIK_AGENTS_CGROUP_DIR")
    if seam:
        return Path(seam)
    out = subprocess.run(
        ["systemctl", "--user", "show", "-p", "ControlGroup", "--value", SLICE],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    cg = out.stdout.strip()
    if out.returncode != 0 or not cg.startswith("/"):
        raise RefusedError(
            f"no measurable memory limit on {SLICE} (its cgroup is not known to the user manager)"
        )
    return Path("/sys/fs/cgroup" + cg)


def headroom_bytes() -> int:
    """The slice's headroom: limit − (memory.current − memory.stat inactive_file), so reclaimable page cache does not
    refuse falsely. limit = memory.high, or memory.max when memory.high reads `max` (FABRIK_AGENT_SLICE_MAX sets
    MemoryHigh to infinity); both `max`, or any value unreadable, raises RefusedError."""
    no_limit = f"no measurable memory limit on {SLICE}"
    try:
        cg = _cgroup_dir()
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
    return limit - (current - inactive)


def _capped() -> bool:
    """agents_up.sh's CAPPED: systemd-run on PATH and a user manager that answers."""
    if not os.environ.get("XDG_RUNTIME_DIR"):
        bus = f"/run/user/{os.getuid()}"
        if os.path.exists(f"{bus}/bus"):
            os.environ["XDG_RUNTIME_DIR"] = bus
    if not shutil.which("systemd-run"):
        return False
    try:
        out = subprocess.run(
            ["systemctl", "--user", "show-environment"],
            capture_output=True,
            timeout=10,
            check=False,
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


def preflight(ctx: Spawn) -> None:
    """D2 (1): every refusal BEFORE any write, so a refused add leaves no worktree or branch."""
    name, role, root = ctx.name, ctx.role, ctx.root
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
    if not name.startswith(f"{role}-"):
        raise RefusedError(
            f"{name!r} does not start with '{role}-' (role {role}: names read {role}-1, {role}-2, …)"
        )
    if _coordinator_name(name):
        raise RefusedError(f"{name!r} is a coordinator name — a coordinator gets no builder pane")
    owner = _merge_owner(root)
    if owner and owner == name:
        raise RefusedError(
            f"{name!r} is the repo's merge owner (its coordinator) — a coordinator gets no builder pane"
        )
    who = subprocess.run(
        [sys.executable, str(HUB / "scripts" / "whoami_agent.py"), "--who"],
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
    whoami = _whoami()
    for row in whoami._rows(whoami.store_path()):
        if (
            row.get("name") == name
            and row.get("toplevel") == ctx.scope
            and whoami._pid_alive_same_start(row)
        ):
            raise RefusedError(
                f"{name!r} is bound to a LIVE session (pid {row.get('pid')}) in this repo — pick another name"
            )
    if not _trusted(root):
        raise RefusedError(
            f"{root} is not trusted — open {root} once in Claude Code and accept the trust dialog"
        )
    _read_registry(root)
    ctx.base = resolve_base(root)
    if _capped():
        room = headroom_bytes()
        if room < HEADROOM_FLOOR:
            raise RefusedError(
                f"{SLICE} has {room / 1024**3:.1f} GB headroom, under the 2 GB floor — retire a builder first"
            )
    elif os.environ.get("FABRIK_AGENTS_UNCAPPED") == "1":
        print(
            "agents_spawn: FABRIK_AGENTS_UNCAPPED=1 — the builder runs UNCAPPED (no user manager); "
            "the headroom floor is not measured",
            file=sys.stderr,
        )
    else:
        raise RefusedError(
            "no systemd-run on PATH, or no systemd user manager answers — the builder would run uncapped; "
            "set FABRIK_AGENTS_UNCAPPED=1 to start it anyway"
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


def cold_start(ctx: Spawn) -> None:
    """D2 (3), D4 — T08b: start the whole grid first when the repo has no tmux session. Nothing yet."""


def _bound_sid(ctx: Spawn) -> str:
    """The session id the identity store binds to the name in this scope (the LAST such row whose session the name
    still owns — agents_up.sh's `binding`), or ""."""
    whoami = _whoami()
    rows = whoami._rows(whoami.store_path())
    owner = {str(r.get("session_id")): str(r.get("name") or "") for r in rows}
    sid = ""
    for r in rows:
        if (
            r.get("toplevel") == ctx.scope
            and r.get("name") == ctx.name
            and owner.get(str(r.get("session_id"))) == ctx.name
        ):
            sid = str(r.get("session_id"))
    return sid


def _write_registry_row(ctx: Spawn) -> None:
    reg = _read_registry(ctx.root)
    # a repo with no registry gets NO file: the resolver would then read only registry names (agents_up.sh)
    if reg is None:
        return
    if ctx.name in reg.values():
        return
    reg[ctx.sid] = ctx.name
    path = _registry_path(ctx.root)
    fd, tmp = tempfile.mkstemp(prefix=".session-agents.", suffix=".tmp", dir=os.path.dirname(path))
    try:
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
                str(HUB / "scripts" / "whoami_agent.py"),
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


def place_and_launch(ctx: Spawn) -> None:
    """D2 (6), D3, D4 — T08a/T08b: place the pane and launch `agents_up.sh --pane-cmd … --new`. Nothing yet."""


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
    except (RefusedError, OSError, subprocess.SubprocessError) as raised:
        # a tool that hung or could not run is a refusal at the step it stopped, never a traceback
        exc = (
            raised
            if isinstance(raised, RefusedError)
            else RefusedError(f"{type(raised).__name__}: {raised}", step)
        )
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
