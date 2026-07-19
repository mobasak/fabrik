"""Worktree manager + owned_paths disjointness + diff-scope checks.

This is the *write* side of containment (the file that `tools.py` defers to):

* :func:`create_worktree` / :func:`worktree_diff` / :func:`remove_worktree` give
  each subagent its own throwaway git worktree. Its edits are captured as a diff
  and **never applied to the caller's repo** — the caller reviews the diff and
  decides.
* :func:`disjoint` partitions agents by whether their ``owned_paths`` globs could
  overlap: overlapping agents share a group (the orchestrator serializes them, so
  two agents never race on the same file), disjoint agents land in separate
  groups (run in parallel). The overlap test is deliberately **conservative** —
  on any doubt it reports overlap (serialize), never a false "safe to parallel".
* :func:`in_scope` checks a finished diff only touched paths the agent owned.

Git is driven via ``subprocess`` on the system ``git`` (no GitPython dependency).
"""

from __future__ import annotations

import contextlib
import fnmatch
import functools
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

# Ownership sidecar: `<base>/.owner-<agent_id>` records the PID that created a worktree, so the GC can
# tell a LIVE agent's worktree (owner still running) from an ORPHAN (owner dead) — dir mtime is a
# creation-time proxy, NOT a liveness signal. A SIBLING file (not inside the worktree) → never in
# `worktree_diff`, and `.owner-*` never matches the sweep's `agent-*` glob.
_OWNER_PREFIX = ".owner-"

try:
    import fcntl  # POSIX advisory file locking (Linux/WSL — the fleet target)
except ImportError:  # pragma: no cover - non-POSIX; the cross-process lock no-ops
    fcntl = None  # type: ignore[assignment]

_WILDCARD = re.compile(r"[*?\[]")
# File-header lines of a git unified diff. We require the `a/`/`b/` prefix (git's
# default) or `/dev/null` so a *content* line that happens to render as `+++ b/x`
# (an added source line beginning `++ b/…`) is NOT misread as a file header.
_DIFF_PLUS = re.compile(r"^\+\+\+ (?:b/(?P<p>.+)|/dev/null)$")
_DIFF_MINUS = re.compile(r"^--- (?:a/(?P<p>.+)|/dev/null)$")
# rename/copy from|to lines carry a path but NO ---/+++ (git omits those for a
# pure rename), so a `---`/`+++`-only parser misses them.
_DIFF_RENAME = re.compile(r"^(?:rename|copy) (?:from|to) (?P<p>.+)$")


def _run_git(args: list[str], *, cwd: str) -> str:
    """Run a git command, raising on failure, returning stdout."""
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return proc.stdout


@contextlib.contextmanager
def _repo_worktree_lock(repo: str):
    """CROSS-PROCESS advisory lock serializing git worktree admin (add/remove/prune) on ONE
    repo's shared ``.git`` registry.

    ``run_agents`` already serializes worktree admin *within* a process (its asyncio ``git_lock``);
    this adds the *cross-process* guarantee so several independent orchestrators (e.g. multiple
    Claude sessions in the same repo) can't race on git's worktree registry — a race that otherwise
    surfaces as a spurious ``git worktree add/prune`` lock error. Held only for the fast admin op.
    Best-effort: a no-op on non-POSIX (no ``fcntl``), and the lock releases on ``close()``.
    """
    if fcntl is None:
        yield
        return
    lock_dir = Path(repo) / ".tmp" / "subagents"
    lock_dir.mkdir(parents=True, exist_ok=True)
    with (lock_dir / ".worktree-admin.lock").open("w") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            with contextlib.suppress(Exception):
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def create_worktree(repo: str, agent_id: str, *, base: str = "HEAD") -> str:
    """Add a detached worktree for ``agent_id`` under ``<repo>/.tmp/subagents/``.

    Returns the worktree path. Uses ``.tmp`` (not ``/tmp``) per project rule. The shared-``.git``
    ``worktree add`` is serialized cross-process (see :func:`_repo_worktree_lock`) so concurrent
    orchestrators in one repo don't contend on git's registry.
    """
    wt = Path(repo) / ".tmp" / "subagents" / agent_id
    wt.parent.mkdir(parents=True, exist_ok=True)
    with _repo_worktree_lock(repo):
        _run_git(["worktree", "add", "--detach", str(wt), base], cwd=repo)
        # Ownership marker (INSIDE the lock so a concurrent sweep never sees the worktree without it):
        # the creating PID, so `sweep_stale_worktrees` skips this worktree while this process lives.
        with contextlib.suppress(OSError):
            (wt.parent / f"{_OWNER_PREFIX}{agent_id}").write_text(
                str(os.getpid()), encoding="utf-8"
            )
    return str(wt)


def worktree_diff(worktree: str) -> str:
    """Stage everything in ``worktree`` and return its unified diff.

    ``git add -A`` + ``git diff --cached`` operate on the *worktree's own* index,
    never the caller's — the diff is returned, not applied anywhere.
    """
    _run_git(["add", "-A"], cwd=worktree)
    return _run_git(["diff", "--cached"], cwd=worktree)


def _owner_alive(owner_file: Path) -> bool:
    """True if ``owner_file`` records the PID of a STILL-RUNNING process (a live worktree owner → the
    GC must not sweep it). Absent / garbled / non-positive / dead-PID → False (an orphan, reclaimable).

    NB (bounded, accepted limitation): PID REUSE — if the original owner died and its PID was recycled
    by an unrelated long-lived process — reads as alive and delays this orphan's reclaim until that
    process exits (a leak, never corruption; probability ~ live_procs/pid_max)."""
    try:
        pid = int(owner_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    if pid <= 0:
        # `os.kill(0, 0)` targets the CALLER's process group and `os.kill(-N, 0)` a process group —
        # both succeed, falsely reading "alive". A truncated/corrupted sidecar ("0"/negative) must read
        # DEAD (else it pins the worktree forever, bypassing the age gate). The docstring's "garbled →
        # False" contract requires this — `int()` accepts "0"/"-1" without raising.
        return False
    try:
        os.kill(pid, 0)  # signal 0 = liveness probe, sends nothing
    except ProcessLookupError:
        return False  # no such process → dead
    except PermissionError:
        return True  # exists but owned by another user → alive
    except (OSError, OverflowError):
        return False  # a bad/huge pid can't be alive
    return True


def remove_worktree(repo: str, worktree: str) -> None:
    """Force-remove a worktree (discards its uncommitted changes) and drop its ownership sidecar."""
    p = Path(worktree)
    try:
        with _repo_worktree_lock(repo):
            _run_git(["worktree", "remove", "--force", worktree], cwd=repo)
    finally:
        # Drop the sidecar EVEN IF git-remove raised — otherwise a failed remove leaks the marker until
        # the next startup sweep. (The sweep's orphan-sidecar cleanup is only a backstop.)
        with contextlib.suppress(OSError):
            (p.parent / f"{_OWNER_PREFIX}{p.name}").unlink()


def prune_worktrees(repo: str) -> None:
    """Prune stale/dangling worktree registrations (best-effort admin cleanup —
    e.g. after a `git worktree add` that failed partway).

    Serialized cross-process: prune walks the shared registry, so it must not run while another
    orchestrator is mid ``worktree add`` in the same repo.
    """
    with _repo_worktree_lock(repo):
        _run_git(["worktree", "prune"], cwd=repo)


def sweep_stale_worktrees(repo: str, *, max_age_s: float) -> int:
    """Reclaim ORPHANED subagent worktrees a prior run's cleanup ``finally`` never removed.

    A ``finally`` cannot be guaranteed: an OOM-kill / SIGKILL, or the outer wall-clock backstop
    abandoning ``_run_one``'s event-loop thread (a Python thread can't be cancelled), leaves BOTH the
    ``<repo>/.tmp/subagents/agent-*`` directory AND git's registration behind — which piled up
    fleet-wide (~2.9 GB across projects, proportional to pool use). ``git worktree prune`` alone can't
    reclaim these (the directory still exists), so this removes the directory too.

    **Self-healing**: :func:`~subagents.agent.arun_agents` calls this at batch startup, so orphans
    from a crashed run are reclaimed on the NEXT pool run instead of accumulating forever. It removes
    a worktree ONLY when its directory mtime is older than ``max_age_s`` — chosen well beyond any live
    batch's ``wall_clock_s`` — so a CONCURRENTLY-running agent's fresh worktree (recent mtime) is never
    swept. Best-effort per item: a ``git worktree remove`` failure falls back to ``rmtree``. Returns
    the count reclaimed. NEVER raises.
    """
    base = Path(repo) / ".tmp" / "subagents"
    if not base.is_dir():
        return 0
    now = time.time()
    reclaimed = 0
    # Hold the cross-process admin lock ONCE for the whole sweep and call `_run_git` DIRECTLY —
    # `remove_worktree`/`prune_worktrees` re-acquire the same lock, which would self-deadlock.
    with _repo_worktree_lock(repo):
        for wt in sorted(base.glob("agent-*")):
            if not wt.is_dir():
                continue
            owner = base / f"{_OWNER_PREFIX}{wt.name}"
            # Reclaim ONLY a dir WE created — a real git worktree (has a `.git` file) or one still
            # carrying our ownership sidecar. A foreign/user dir under this private scratch path is
            # NEVER deleted (a bare `agent-*` dir with neither is left untouched).
            if not ((wt / ".git").exists() or owner.exists()):
                continue
            if _owner_alive(owner):  # the creating process is STILL RUNNING → live worktree, keep it
                continue
            try:
                # Secondary guard: even for a dead/absent owner, only sweep a stale dir — this catches
                # a live agent whose sidecar write failed (its dir is still fresh).
                if now - wt.stat().st_mtime < max_age_s:
                    continue
            except OSError:
                continue
            with contextlib.suppress(subprocess.CalledProcessError, OSError):
                _run_git(["worktree", "remove", "--force", str(wt)], cwd=repo)
            if wt.exists():  # remove refused (e.g. a half-created wt) → force the dir
                shutil.rmtree(wt, ignore_errors=True)
            with contextlib.suppress(OSError):
                owner.unlink()
            if not wt.exists():
                reclaimed += 1
        # Clean any orphaned ownership sidecar whose worktree is already gone (a prior `finally`
        # rmtree'd the dir but not the sidecar) — else `.owner-*` files pile up as their own tiny leak.
        for sc in base.glob(f"{_OWNER_PREFIX}agent-*"):
            if not (base / sc.name[len(_OWNER_PREFIX) :]).exists():
                with contextlib.suppress(OSError):
                    sc.unlink()
        with contextlib.suppress(subprocess.CalledProcessError, OSError):
            _run_git(["worktree", "prune"], cwd=repo)  # drop the now-dangling registrations
    return reclaimed


def changed_paths(worktree: str) -> list[str]:
    """**Authoritative** list of paths the worktree's staged changes touch.

    Uses ``git diff --cached --name-status -z``, so unlike the textual
    :func:`diff_paths` it correctly reports **renames** (both old + new path),
    **copies**, **quoted / non-ASCII** filenames (``-z`` emits raw, unquoted
    paths), and **mode-only** changes — the cases a `---`/`+++` text parse misses.
    Stages (``add -A``) first, like :func:`worktree_diff`. This is what scope
    enforcement must use; ``diff_paths`` is only a best-effort text helper.
    """
    _run_git(["add", "-A"], cwd=worktree)
    out = _run_git(["diff", "--cached", "--name-status", "-z"], cwd=worktree)
    tokens = out.split("\0")
    paths: dict[str, None] = {}
    i = 0
    while i < len(tokens):
        status = tokens[i]
        if not status:
            i += 1
            continue
        if status[0] in ("R", "C"):  # rename/copy → STATUS \0 old \0 new
            for j in (i + 1, i + 2):
                if j < len(tokens) and tokens[j]:
                    paths.setdefault(tokens[j], None)
            i += 3
        else:  # A/M/D/T → STATUS \0 path
            if i + 1 < len(tokens) and tokens[i + 1]:
                paths.setdefault(tokens[i + 1], None)
            i += 2
    return list(paths)


def _glob_to_regex(glob: str) -> str:
    """Anchored glob→regex with gitignore-style semantics: ``*`` matches within ONE
    path segment (not across ``/``), ``**/`` matches zero-or-more directories,
    ``**`` (not followed by ``/``) matches across segments, ``?`` matches one
    non-``/`` char, and ``[abc]`` / ``[!abc]`` are character classes. Unlike
    ``fnmatch`` (whose ``*`` spans ``/``), ``docs/*.md`` matches ``docs/a.md`` but
    NOT ``docs/sub/deep.md`` — the scope guard can't be widened by depth — while
    ``docs/**/x`` correctly matches ``docs/x`` (zero dirs) and ``docs/a/x``."""
    out: list[str] = []
    i = 0
    n = len(glob)
    while i < n:
        c = glob[i]
        if c == "*":
            if i + 1 < n and glob[i + 1] == "*":
                if i + 2 < n and glob[i + 2] == "/":
                    out.append("(?:.*/)?")  # **/ → zero-or-more directories
                    i += 3
                else:
                    out.append(".*")  # ** → any chars incl. /
                    i += 2
            else:
                out.append("[^/]*")  # * → any chars except /
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            j = i + 1
            if j < n and glob[j] in ("!", "^"):
                j += 1
            if j < n and glob[j] == "]":
                j += 1
            while j < n and glob[j] != "]":
                j += 1
            if j >= n:  # unterminated '[' → treat literally
                out.append(re.escape(c))
                i += 1
            else:
                inner = glob[i + 1 : j]
                if inner[:1] in ("!", "^"):
                    # a negated class also excludes / (stay /-aware) — both the
                    # gitignore `!` form and a regex-style `^` form
                    inner = "^/" + inner[1:]
                out.append("[" + inner + "]")
                i = j + 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


@functools.lru_cache(maxsize=512)
def _compiled_glob(glob: str) -> re.Pattern[str]:
    try:
        return re.compile(_glob_to_regex(glob) + r"\Z")
    except re.error:
        # An owned glob with an invalid char-class (reversed range like [z-a], a
        # trailing backslash, or a POSIX class) would otherwise crash the scope
        # check. Fall back to matching the glob LITERALLY — fail-closed: it won't
        # match a normal path, so the change is flagged out_of_scope, never a crash.
        return re.compile(re.escape(glob) + r"\Z")


def _path_matches(path: str, glob: str) -> bool:
    return _compiled_glob(glob).match(path) is not None


def out_of_scope_paths(paths: list[str], owned_paths: list[str]) -> list[str]:
    """The paths matching NO owned glob (empty ``owned_paths`` ⇒ unrestricted ⇒ ``[]``). Names the
    offenders so an ``out_of_scope`` result is actionable instead of an audit."""
    if not owned_paths:
        return []
    return [p for p in paths if not any(_path_matches(p, g) for g in owned_paths)]


def paths_in_scope(paths: list[str], owned_paths: list[str]) -> bool:
    """True if every path matches ≥1 owned glob. Empty ``owned_paths`` ⇒ True
    (unrestricted). This is the authoritative scope check (pair with
    :func:`changed_paths`). Matching is anchored and ``/``-aware (see
    :func:`_glob_to_regex`) — ``*`` does not cross a directory separator, so an
    agent can't widen its lane by nesting deeper under an owned prefix."""
    if not owned_paths:
        return True
    return all(any(_path_matches(p, glob) for glob in owned_paths) for p in paths)


def diff_paths(diff: str) -> list[str]:
    """Best-effort repo-relative paths a unified diff *text* touches (added,
    modified, deleted, renamed, copied), de-duplicated, order-preserving.

    NOTE: prefer :func:`changed_paths` for scope enforcement — a textual parse
    cannot fully handle quoted/octal-escaped filenames. This helper handles the
    common `---`/`+++` and `rename/copy from/to` forms and skips `/dev/null`.
    """
    seen: dict[str, None] = {}
    in_hunk = False  # header `---`/`+++` lines appear BEFORE the first `@@`; a
    # `+++ b/x` INSIDE a hunk is file content, not a header. Track structure so a
    # crafted content line cannot masquerade as a header.
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
            continue
        if line.startswith("@@ "):
            in_hunk = True
            continue
        if in_hunk:
            continue
        rc = _DIFF_RENAME.match(line)  # rename/copy from|to <path> (no ---/+++)
        if rc is not None:
            seen.setdefault(rc.group("p").strip().strip('"'), None)
            continue
        m = _DIFF_PLUS.match(line) or _DIFF_MINUS.match(line)
        if m is None:
            continue
        path = m.group("p")  # None for the /dev/null branch → skip
        if path:
            seen.setdefault(path.strip(), None)
    return list(seen)


def in_scope(diff: str, owned_paths: list[str]) -> bool:
    """True if every path the ``diff`` *text* touches matches an owned glob. Empty
    ``owned_paths`` ⇒ True. Best-effort — see :func:`changed_paths`/
    :func:`paths_in_scope` for the authoritative check."""
    return paths_in_scope(diff_paths(diff), owned_paths)


def _static_prefix(glob: str) -> tuple[str, ...]:
    """The leading path components of ``glob`` before the first wildcard.

    ``src/pkg/*.py`` -> ``("src", "pkg")``; ``src/a.py`` -> ``("src", "a.py")``.
    """
    m = _WILDCARD.search(glob)
    head = glob[: m.start()] if m else glob
    # if we cut mid-component (e.g. "src/foo*"), drop the partial trailing part
    if m and not head.endswith("/"):
        head = head.rsplit("/", 1)[0]
    return tuple(p for p in head.split("/") if p and p != ".")


def _globs_overlap(a: str, b: str) -> bool:
    """Conservative: could any single path match BOTH globs? Err toward True."""
    if a == b:
        return True
    if fnmatch.fnmatch(a, b) or fnmatch.fnmatch(b, a):
        return True
    ta, tb = _static_prefix(a), _static_prefix(b)
    n = min(len(ta), len(tb))
    # shared static prefix ⇒ the wildcard tails could meet ⇒ assume overlap
    return ta[:n] == tb[:n]


def _owned_overlap(owned_a: list[str], owned_b: list[str]) -> bool:
    return any(_globs_overlap(ga, gb) for ga in owned_a for gb in owned_b)


def disjoint(owned: list[list[str]]) -> list[set[int]]:
    """Partition agent indices into overlap-connected groups.

    Two agents are connected when any of their ``owned_paths`` globs overlap;
    connected components become one group (serialized by the orchestrator).
    Distinct groups are guaranteed non-overlapping and safe to run in parallel.
    An agent with empty ``owned_paths`` (unrestricted) overlaps everything.
    """
    n = len(owned)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for i in range(n):
        for j in range(i + 1, n):
            unrestricted = not owned[i] or not owned[j]
            if unrestricted or _owned_overlap(owned[i], owned[j]):
                union(i, j)

    groups: dict[int, set[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), set()).add(i)
    return list(groups.values())


__all__ = [
    "create_worktree",
    "worktree_diff",
    "remove_worktree",
    "prune_worktrees",
    "sweep_stale_worktrees",
    "changed_paths",
    "paths_in_scope",
    "diff_paths",
    "in_scope",
    "disjoint",
]
