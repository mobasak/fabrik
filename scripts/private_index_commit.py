#!/usr/bin/env python3
# AFTER-EDIT: CLAUDE.md | templates/governance/CLAUDE.md | tests/test_private_index_commit.py
"""Commit shared-append files through a PRIVATE index — the executable form of the recipe that
`CLAUDE.md` § Behavior (shared repo) carried as prose until 2026-09-21 (D-328).

Why a script: three sessions and a pipeline append to the same five files (`CHANGELOG.md`,
`docs/DECISIONS.md`, `docs/STRATEGIC_BACKLOG.md`, `INDEX.md`, `docs/LESSONS_LEARNT.md`). A pathspec
commit ships the WORKING TREE, so it carries a sibling's half-finished hunk under your name; a bare
commit ships the SHARED INDEX, which may hold a sibling's staged blob. The recipe builds each shared
file as HEAD's blob plus your own hunk in an index nobody else touches, commits with a
compare-and-swap on the base SHA, asserts what landed by blob, and carries your hunk into the working
file by INSERT. Three prose cuts of that recipe produced nine executed defects in the prose itself —
`env -u` scope, `set -e` short-circuits, `printf` format positions, `HEAD` as the CAS old-value — which
a script does not have: every git call here gets its own environment, so the private index cannot
leak into the shared one by construction.

What it does, in the recipe's own step numbers:
  1  base = HEAD, branch = the current branch (a detached HEAD is refused).
  2  a throwaway index is read from `base`; each `--append` file is `base`'s blob plus the hunk
     inserted after the first line matching its anchor regex (and the blank lines that follow it);
     each `--own` file is the working file as-is. A `--append` file absent at `base` starts empty and
     SAYS so.
  3  `update-index --cacheinfo <mode>,<blob>,<path>` with the mode read from `base`'s tree (a new
     file: 100644, or 100755 when the working file is executable).
  4  `diff-index --cached --numstat base` must name exactly the given paths, with zero deletions on
     any `--append` path — a deletion there means a stale blob and is a stop.
  5  `commit-tree` on `write-tree`, then `update-ref refs/heads/<branch> <new> <base>` — the old-value
     is the captured base, never `HEAD`. rc 128 means a sibling committed in the window: the base is
     re-captured and steps 2–5 rerun (bounded by --attempts); nothing is weakened.
  5a `ls-tree <new> -- <path>` must equal `<mode> blob <blob>` for every path, and the branch ref must
     equal `<new>`.
  6  the SHARED index is reset to HEAD for those paths, so a stale staged blob cannot revert the
     commit on the next bare `git commit` by anyone.
  7  the hunk is inserted into the WORKING file at the same anchor (never copied over it — a sibling's
     uncommitted hunks in that file are preserved), and the file is checked to carry the hunk once.
  ⚠  no commit hook runs (this is plumbing). The gate, the corpus check and the trailer check are the
     caller's; on a governance-sync trigger path the post-commit sync never fires and this script
     says so — run `scripts/sync_enforcement_to_projects.py --force` yourself.

The message file is checked for `Agent-Role:` and `Agent-Context:` trailers BEFORE anything is
written, because no hook will check them after.

Cobra (D-253): the cheapest way to satisfy "the commit landed" without the outcome is to pass a
`--own` path for a shared-append file, which ships whatever the working file holds. RefusedError by name.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

SHARED_APPEND = frozenset(
    {
        "CHANGELOG.md",
        "docs/DECISIONS.md",
        "docs/STRATEGIC_BACKLOG.md",
        "INDEX.md",
        "docs/LESSONS_LEARNT.md",
    }
)
REQUIRED_TRAILERS = ("Agent-Role", "Agent-Context")


class RefusedError(RuntimeError):
    """A pre-check failed; nothing was written."""


class FailedError(RuntimeError):
    """A post-commit assertion failed; the commit may be dangling — read the message."""


@dataclass
class Result:
    base: str
    new: str
    branch: str
    paths: list[str]
    attempts: int
    sync_trigger: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _git(
    repo: Path, *args: str, env: dict[str, str] | None = None, input_text: str | None = None
) -> tuple[int, str, str]:
    e = dict(os.environ)
    e.pop("GIT_INDEX_FILE", None)  # never inherit a caller's private index
    if env:
        e.update(env)
    p = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=e,
        capture_output=True,
        text=True,
        errors="replace",
        stdin=subprocess.DEVNULL if input_text is None else None,
        input=input_text,
        check=False,
    )
    return p.returncode, p.stdout, p.stderr


def _must(
    repo: Path, *args: str, env: dict[str, str] | None = None, input_text: str | None = None
) -> str:
    rc, out, err = _git(repo, *args, env=env, input_text=input_text)
    if rc != 0:
        raise FailedError(f"git {' '.join(args)} → rc {rc}: {err.strip()}")
    return out


def insert_after_anchor(text: str, hunk: str, anchor: str) -> str:
    """Insert `hunk` after the first line matching `anchor` (a whole-line regex) and after the run of
    blank lines that immediately follows it. Raises RefusedError when the anchor is absent."""
    lines = text.split("\n")
    rx = re.compile(anchor)
    at = next((i for i, ln in enumerate(lines) if rx.search(ln)), -1)
    if at < 0:
        raise RefusedError(f"anchor {anchor!r} not found")
    j = at + 1
    while j < len(lines) and lines[j].strip() == "":
        j += 1
    head = "\n".join(lines[:j])
    tail = "\n".join(lines[j:])
    if not head.endswith("\n"):
        head += "\n"
    return head + hunk + tail


def _mode_at(repo: Path, base: str, path: str) -> str | None:
    out = _must(repo, "ls-tree", base, "--", path)
    return out.split()[0] if out.strip() else None


def _sync_trigger_paths(repo: Path, paths: list[str]) -> list[str]:
    cfg = repo / ".pre-commit-config.yaml"
    if not cfg.is_file():
        return []
    text = cfg.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"id:\s*governance-sync.*?\n\s*files:\s*['\"]?(.+?)['\"]?\s*$", text, re.S | re.M)
    if not m:
        return []
    try:
        rx = re.compile(m.group(1))
    except re.error:
        return []
    return [p for p in paths if rx.search(p)]


def run(
    repo: Path,
    msg_file: Path,
    appends: list[tuple[str, str, str]],
    owns: list[str],
    *,
    attempts: int = 3,
    before_update_ref=None,
    out=None,
) -> Result:
    out = out if out is not None else sys.stdout
    repo = Path(repo).resolve()
    if not appends and not owns:
        raise RefusedError("nothing to commit: give --append and/or --own")
    for p in owns:
        if p in SHARED_APPEND:
            raise RefusedError(
                f"{p} is a shared-append file — use --append with a hunk and an anchor, never --own"
            )
    paths = [p for p, _, _ in appends] + list(owns)
    if len(set(paths)) != len(paths):
        raise RefusedError("a path is given twice")
    msg = Path(msg_file).read_text(encoding="utf-8")
    parsed = _must(repo, "interpret-trailers", "--parse", input_text=msg)
    for key in REQUIRED_TRAILERS:
        if not re.search(rf"^{key}:", parsed, re.M):
            raise RefusedError(
                f"message lacks a parseable {key}: trailer (git interpret-trailers --parse saw none)"
            )
    for p in owns:
        if not (repo / p).is_file():
            raise RefusedError(f"--own {p}: not a file in the working tree")

    rc, branch, _ = _git(repo, "symbolic-ref", "--short", "-q", "HEAD")
    branch = branch.strip()
    if rc != 0 or not branch:
        raise RefusedError("detached HEAD — the CAS needs a branch")

    notes: list[str] = []
    base = _must(repo, "rev-parse", "HEAD").strip()
    original_base = base
    # pre-check the anchors against base so a missing anchor refuses before any write
    for p, hunk, anchor in appends:
        rc, blob_text, _ = _git(repo, "show", f"{base}:{p}")
        if rc == 0:
            insert_after_anchor(blob_text, hunk, anchor)

    new = ""
    n = 0
    with tempfile.TemporaryDirectory(prefix="pic-") as td:
        while True:
            n += 1
            if n > attempts:
                raise FailedError(
                    f"gave up after {attempts} CAS refusals — a sibling is committing faster than this retries"
                )
            idx = os.path.join(td, f"idx{n}")
            env = {"GIT_INDEX_FILE": idx}
            _must(repo, "read-tree", base, env=env)
            built: dict[str, tuple[str, str]] = {}
            for p, hunk, anchor in appends:
                rc, blob_text, _ = _git(repo, "show", f"{base}:{p}")
                if rc != 0:
                    blob_text = ""
                    notes.append(f"NOTE: {p} is new to HEAD — building on an empty base")
                content = insert_after_anchor(blob_text, hunk, anchor) if blob_text else hunk
                blob = _must(repo, "hash-object", "-w", "--stdin", input_text=content).strip()
                mode = _mode_at(repo, base, p) or "100644"
                _must(repo, "update-index", "--add", "--cacheinfo", f"{mode},{blob},{p}", env=env)
                built[p] = (mode, blob)
            for p in owns:
                data = (repo / p).read_bytes()
                clean = {k: v for k, v in os.environ.items() if k != "GIT_INDEX_FILE"}
                bp = subprocess.run(
                    ["git", "hash-object", "-w", "--stdin"],
                    cwd=repo,
                    input=data,
                    capture_output=True,
                    check=True,
                    env=clean,
                )
                blob = bp.stdout.decode().strip()
                mode = _mode_at(repo, base, p) or (
                    "100755" if os.access(repo / p, os.X_OK) else "100644"
                )
                _must(repo, "update-index", "--add", "--cacheinfo", f"{mode},{blob},{p}", env=env)
                built[p] = (mode, blob)
            # step 4 — the private index differs from base by exactly these paths
            numstat = _must(repo, "diff-index", "--cached", "--numstat", base, env=env)
            seen: dict[str, tuple[str, str]] = {}
            for ln in numstat.splitlines():
                a, d, pth = ln.split("\t", 2)
                seen[pth] = (a, d)
            if set(seen) != set(paths):
                raise FailedError(
                    f"step 4: index differs from base on {sorted(set(seen) ^ set(paths))}, not only the given paths"
                )
            for p, _, _ in appends:
                a, d = seen[p]
                if d != "0":
                    raise FailedError(
                        f"step 4: {p} shows deletions ({d}) against base — a stale blob; stopped"
                    )
            tree = _must(repo, "write-tree", env=env).strip()
            new = _must(repo, "commit-tree", tree, "-p", base, "-F", str(msg_file)).strip()
            if before_update_ref is not None and n == 1:
                before_update_ref()
            rc, _, err = _git(repo, "update-ref", f"refs/heads/{branch}", new, base)
            if rc == 0:
                break
            if "cannot lock ref" in err or rc == 128:
                notes.append(
                    f"CAS refused on attempt {n} (a sibling committed in the window); rebuilding from the new base"
                )
                base = _must(repo, "rev-parse", "HEAD").strip()
                continue
            raise FailedError(f"update-ref rc {rc}: {err.strip()}")
    # 5a — what landed, against the bound `new`, never HEAD
    for p, (mode, blob) in built.items():
        got = _must(repo, "ls-tree", new, "--", p).rstrip("\n")
        want = f"{mode} blob {blob}\t{p}"
        if got != want:
            raise FailedError(f"5a: {p} landed as {got!r}, expected {want!r}")
    ref = _must(repo, "rev-parse", "-q", "--verify", f"refs/heads/{branch}").strip()
    if ref != new:
        raise FailedError(f"5a: refs/heads/{branch} is {ref}, not {new}")
    # 6 — align the SHARED index for those paths
    _must(repo, "reset", "-q", "HEAD", "--", *paths)
    # 5b — the base moved under us: a sibling's landed hunk is in HEAD but not in the working file,
    # and the next pathspec commit by anyone would delete it. Bring the working file up to the new
    # base with a three-way merge (working ← original base → new base) before the carry.
    if base != original_base:
        for p, _, _ in appends:
            wp = repo / p
            if not wp.is_file():
                continue
            with tempfile.TemporaryDirectory(prefix="pic-merge-") as md:
                old_f, new_f = Path(md) / "old", Path(md) / "new"
                rc_o, old_txt, _ = _git(repo, "show", f"{original_base}:{p}")
                rc_n, new_txt, _ = _git(repo, "show", f"{base}:{p}")
                old_f.write_text(old_txt if rc_o == 0 else "", encoding="utf-8")
                new_f.write_text(new_txt if rc_n == 0 else "", encoding="utf-8")
                rc, _, err = _git(repo, "merge-file", "-q", str(wp), str(old_f), str(new_f))
                if rc != 0:
                    raise FailedError(
                        f"5b: merging the sibling's landed change into the working {p} conflicted ({rc}); "
                        f"resolve by hand — the commit {new[:11]} is landed and correct"
                    )
                notes.append(
                    f"5b: working {p} brought up to the new base {base[:11]} by three-way merge"
                )
    # 7 — carry each hunk into the WORKING file by insert, never by copy
    for p, hunk, anchor in appends:
        wp = repo / p
        current = wp.read_text(encoding="utf-8") if wp.is_file() else ""
        if current.count(hunk) == 0:
            current = insert_after_anchor(current, hunk, anchor) if current else hunk
            wp.parent.mkdir(parents=True, exist_ok=True)
            wp.write_text(current, encoding="utf-8")
        if current.count(hunk) != 1:
            raise FailedError(
                f"7: {p} carries the hunk {current.count(hunk)} times after the carry"
            )
        rc, d, _ = _git(repo, "diff", "HEAD", "--", p)
        if d.strip():
            notes.append(
                f"INFO: {p} still differs from HEAD after the carry — a sibling's uncommitted hunks, left in place"
            )
    sync = _sync_trigger_paths(repo, paths)
    res = Result(
        base=base, new=new, branch=branch, paths=paths, attempts=n, sync_trigger=sync, notes=notes
    )
    print(
        f"private-index commit {new[:11]} on {branch} (base {base[:11]}, attempt {n}/{attempts})",
        file=out,
    )
    for p, (mode, blob) in built.items():
        print(f"  {mode} {blob[:11]} {p}", file=out)
    for note in notes:
        print(f"  {note}", file=out)
    if sync:
        print(
            f"  ⚠ governance-sync trigger path(s) {sync}: no post-commit hook ran — run\n"
            "    python3 scripts/sync_enforcement_to_projects.py --force  yourself, or the change reaches no project",
            file=out,
        )
    print(
        "  no commit hook ran: the gate, the corpus check and the trailer check are yours", file=out
    )
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--repo", default=None, help="repo root (default: git rev-parse --show-toplevel of cwd)"
    )
    ap.add_argument("--msg-file", required=True)
    ap.add_argument(
        "--append",
        nargs=3,
        action="append",
        default=[],
        metavar=("PATH", "HUNK_FILE", "ANCHOR_REGEX"),
        help="a shared-append file: HEAD's blob + the hunk after the anchor line",
    )
    ap.add_argument(
        "--own",
        action="append",
        default=[],
        metavar="PATH",
        help="a file of your own: the working file as-is",
    )
    ap.add_argument("--attempts", type=int, default=3)
    a = ap.parse_args(argv)
    repo = (
        Path(a.repo)
        if a.repo
        else Path(
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
                stdin=subprocess.DEVNULL,
            ).stdout.strip()
        )
    )
    appends = [(p, Path(h).read_text(encoding="utf-8"), rx) for p, h, rx in a.append]
    try:
        run(repo, Path(a.msg_file), appends, a.own, attempts=a.attempts)
    except RefusedError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    except FailedError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
