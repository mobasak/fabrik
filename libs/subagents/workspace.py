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

import fnmatch
import functools
import re
import subprocess
from pathlib import Path

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


def create_worktree(repo: str, agent_id: str, *, base: str = "HEAD") -> str:
    """Add a detached worktree for ``agent_id`` under ``<repo>/.tmp/subagents/``.

    Returns the worktree path. Uses ``.tmp`` (not ``/tmp``) per project rule.
    """
    wt = Path(repo) / ".tmp" / "subagents" / agent_id
    wt.parent.mkdir(parents=True, exist_ok=True)
    _run_git(["worktree", "add", "--detach", str(wt), base], cwd=repo)
    return str(wt)


def worktree_diff(worktree: str) -> str:
    """Stage everything in ``worktree`` and return its unified diff.

    ``git add -A`` + ``git diff --cached`` operate on the *worktree's own* index,
    never the caller's — the diff is returned, not applied anywhere.
    """
    _run_git(["add", "-A"], cwd=worktree)
    return _run_git(["diff", "--cached"], cwd=worktree)


def remove_worktree(repo: str, worktree: str) -> None:
    """Force-remove a worktree (discards its uncommitted changes)."""
    _run_git(["worktree", "remove", "--force", worktree], cwd=repo)


def prune_worktrees(repo: str) -> None:
    """Prune stale/dangling worktree registrations (best-effort admin cleanup —
    e.g. after a `git worktree add` that failed partway)."""
    _run_git(["worktree", "prune"], cwd=repo)


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
    "changed_paths",
    "paths_in_scope",
    "diff_paths",
    "in_scope",
    "disjoint",
]
