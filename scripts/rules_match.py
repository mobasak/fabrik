#!/usr/bin/env python3
# AFTER-EDIT: scripts/select_rules.py scripts/review_rubric.py tests/test_rules_match.py
"""The ONE path <-> `.windsurf/rules` pack glob matcher — extracted so
`select_rules.py` (plan-time ACTIVE/AVAILABLE split, whole-tree scan) and
`review_rubric.py` (review-time rubric injection, single changed-path match) share one
implementation instead of two independently-maintained ones.

Two shapes, one glob-normalization core:

  · `pack_matches_path(path, glob, *, empty_matches_all)` — does ONE path match?
    (review_rubric's per-changed-path question.)
  · `any_path_matches(root, glob, *, empty_matches_all)` — does ANY file/dir already in
    the project match? Backed by `_tree_paths`, a SINGLE pruned `os.walk` (not `rglob`
    per glob per pack): `rglob` re-walks the whole tree every call, which — with
    `.tmp/subagents/` worktree copies in the mix (~80 full repo trees at the hub) —
    effectively hung `select_rules.py` (proven live 2026-07-18, repeated 2-minute
    timeouts). Never swap this back to a per-glob `rglob` loop.

`empty_matches_all` is deliberately a KEYWORD with NO default: after stripping `**/` /
`/**`, an empty pattern (a wildcard-only glob) is ambiguous on its own, and the two
callers resolve it in OPPOSITE directions on purpose —
  · review_rubric: True  — arming a reviewer errs SAFE (match-everything).
  · select_rules:  False — activating a pack project-wide on a wildcard-only glob would
                            make every pack ACTIVE, defeating the ACTIVE/AVAILABLE split.
A caller that forgets the flag gets a TypeError, not a silently wrong default.

`packs_for_paths(paths, root)` is the plan-stage routing entry point: given a set of
changed paths, which packs (relative to `.windsurf/rules/`, posix) does ANY of them
match — the same GLOB question `review_rubric.py --changed` asks per-path. NOTE: it is
NOT equal to the rubric's MATCHED section, which suppresses FLOOR_PACKS it has already
emitted; a floor pack whose glob fires appears here and not there
to a caller that just wants the pack id list (e.g. `select_rules.py --changed`).
"""

from __future__ import annotations

import fnmatch
import functools
import os
import re
import sys
from pathlib import Path

# Noise dirs excluded from the tree scan — deps or bundled reference copies, not the
# project's OWN source (e.g. templates/saas-skeleton ships .tsx, which would otherwise
# false-flag the TS/Node/Chrome packs as ACTIVE in a pure-Python project).
_EXCLUDE = {
    "node_modules",
    ".venv",
    "venv",  # non-dotted virtualenv (bundles deps like playwright's electron/ — false-flags packs)
    ".git",
    "templates",
    "dist",
    "build",
    "__pycache__",
    ".next",
    ".expo",
    "output",
    "backups",
    ".droid",
    "docs-site",
    ".tmp",  # subagent worktrees (full repo copies under .tmp/subagents/) — traversing them
    #          made rglob effectively HANG at the hub (~80 tree copies; proven live 2026-07-18)
}


def _expand_braces(pat: str) -> list[str]:
    """Expand a single `{a,b,c}` group (pathlib globs don't support brace expansion)."""
    m = re.search(r"\{([^}]*)\}", pat)
    if not m:
        return [pat]
    pre, post = pat[: m.start()], pat[m.end() :]
    return [pre + opt.strip() + post for opt in m.group(1).split(",") if opt.strip()]


@functools.lru_cache(maxsize=4)
def _tree_paths(root: Path) -> tuple[str, ...]:
    """Every file AND directory path under root (relative, posix), with `_EXCLUDE` dirs pruned
    DURING the walk. One pruned walk replaces per-glob `rglob` traversals: `rglob` cannot prune,
    so it re-walked the ENTIRE tree (incl. `.tmp/subagents/` worktree copies — ~80 full repo
    trees at the hub) once per glob per pack, which effectively hung the script (proven live
    2026-07-18: repeated 2-minute timeouts at `/opt/fabrik`)."""
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE]
        rel = os.path.relpath(dirpath, root)
        base = "" if rel == "." else rel.replace(os.sep, "/") + "/"
        out.extend(base + d for d in dirnames)
        out.extend(base + f for f in filenames)
    return tuple(out)


def _tail_matches(relpath: str, pat: str) -> bool:
    """rglob-equivalent match: do the TRAILING segments of relpath match pat segment-wise?
    (`root.rglob("a/b.py")` hits any path whose last two components match `a`/`b.py`.)"""
    psegs = [p for p in pat.replace("**/", "").replace("**", "*").split("/") if p]
    rsegs = relpath.split("/")
    if not psegs or len(psegs) > len(rsegs):
        return False
    return all(fnmatch.fnmatch(r, p) for r, p in zip(rsegs[-len(psegs) :], psegs, strict=True))


def _prefixes(rel: str) -> list[str]:
    """Every leading-path prefix of rel (`a/b/c` -> `["a", "a/b", "a/b/c"]`) — a dir-glob
    like `uploads/**` must match a PARENT segment too, not just the full path."""
    segs = rel.split("/")
    return ["/".join(segs[: i + 1]) for i in range(len(segs))]


def _strip_wildcards(glob: str) -> str | None:
    """Strip a leading `**/` / trailing `/**` off glob; None if that empties the pattern
    (a wildcard-only glob, e.g. `**/` or `/**`) — callers resolve None via `empty_matches_all`."""
    pat = glob.strip().lstrip("/")
    if pat.startswith("**/"):
        pat = pat[3:]
    if pat.endswith("/**"):
        pat = pat[:-3]
    return pat or None


def pack_matches_path(path: str, glob: str, *, empty_matches_all: bool) -> bool:
    """Does this ONE path match this pack glob? (review_rubric's per-changed-path question.)"""
    pat = _strip_wildcards(glob)
    if pat is None:
        return empty_matches_all
    rel = path.strip().lstrip("/")
    return any(
        _tail_matches(prefix, expanded)
        for expanded in _expand_braces(pat)
        for prefix in _prefixes(rel)
    )


def any_path_matches(root: Path, glob: str, *, empty_matches_all: bool) -> bool:
    """Best-effort: does an existing file/dir in the project's OWN source (root, tree-scanned)
    match this glob? (select_rules' whole-tree ACTIVE/AVAILABLE question.)"""
    pat = _strip_wildcards(glob)
    if pat is None:
        return empty_matches_all
    try:
        paths = _tree_paths(root)
    except OSError:
        return False
    return any(_tail_matches(rel, expanded) for expanded in _expand_braces(pat) for rel in paths)


def packs_for_paths(paths: list[str], root: Path) -> list[str]:
    """Sorted pack ids (relative to `.windsurf/rules/`, posix) whose frontmatter glob
    matches ANY of `paths` — the plan-stage routing entry point (review-time asks this
    per-path via `review_rubric.py --changed`; this generalizes it to a pack-id list)."""
    # Local import breaks the load-time cycle: select_rules imports rules_match (for
    # any_path_matches) at module scope, so importing select_rules back at module scope
    # here would deadlock partial-module resolution. Deferred to call time, by which
    # point both modules are always fully loaded regardless of which loaded first.
    _scripts_dir = Path(__file__).resolve().parent
    if str(_scripts_dir) not in sys.path:
        sys.path.insert(0, str(_scripts_dir))
    import select_rules  # noqa: E402 - the shared frontmatter parser

    rules_dir = root / ".windsurf" / "rules"
    matched: set[str] = set()
    if rules_dir.exists():
        for pack in rules_dir.rglob("*.md"):
            text = pack.read_text(encoding="utf-8", errors="replace")
            globs, _desc = select_rules._parse_frontmatter(text)
            if any(
                pack_matches_path(p, g, empty_matches_all=True) for p in paths for g in globs
            ):
                matched.add(pack.relative_to(rules_dir).as_posix())
    return sorted(matched)
