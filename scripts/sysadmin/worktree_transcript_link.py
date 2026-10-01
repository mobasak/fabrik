#!/usr/bin/env python3
# AFTER-EDIT: tests/test_worktree_transcript_link.py | docs/workstation/session-recall.md | docs/workstation/hooks-index.md | scripts/sysadmin/install_user_hooks.py
"""SessionStart + Stop (USER level, every window, every repo): keep a worktree session listed in its repo's window.

Claude Code files a transcript under the session's cwd, path-mangled. A session that enters
`<repo>/.claude/worktrees/<name>`, through `EnterWorktree` or a `--worktree` launch, has its whole
transcript moved to `<projects>/<repo-key>--claude-worktrees-<name>/`. The VS Code extension builds
its session list with `includeWorktrees: false` hard-coded (extension.js 2.1.280
`buildSessionList`), so a window opened at the repo root never lists that session. After a reload,
which ends every session in the window, the lane is gone from the picker. Measured 2026-10-01:
wef1 and wef3 at web-ecommerce-factory, and 14 of 18 worktree transcripts box-wide (D-467).

This keeps a HARDLINK of the transcript under the repo-root key. Claude Code appends in place
(inode stable across `--resume`, measured 2026-09-11), so both names stay one file: no copy, no
extra blocks, and `rm` of the extra name undoes it. The webview groups the listed session under its
worktree and resumes it with the worktree as cwd.

    worktree_transcript_link.py                 # hook mode: hook JSON on stdin, silent, exit 0
    worktree_transcript_link.py --sweep         # link every worktree transcript on the box
    worktree_transcript_link.py --sweep --dry-run

Never overwrites: a root-key name that exists as a DIFFERENT file is left alone and reported by
`--sweep`. FAIL-OPEN in hook mode: any error, silent exit 0; a hook must never block a turn.
`--sweep` reports a per-file `error` and goes on; it exits 1 on any conflict or error.

The cheapest way to look done without the outcome: a `--sweep` that reports `linked` counts while
the extension still lists nothing, for example because a future extension stops reading the
root-key dir. The check that answers it is the picker itself, not this script's count.
"""

from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

MARK = "--claude-worktrees-"


def projects_root() -> Path:
    return Path(
        os.environ.get("WORKTREE_LINK_PROJECTS_ROOT") or Path.home() / ".claude" / "projects"
    )


def root_key_path(transcript: Path) -> Path | None:
    """The repo-root name for a worktree-filed transcript, or None when it is not worktree-filed.

    `-opt-x--claude-worktrees-a/<sid>.jsonl` → `-opt-x/<sid>.jsonl`. The first marker wins, so a
    worktree inside a worktree still lands at the repo root. A key that STARTS with the marker
    names no repo and is skipped.
    """
    head, mark, tail = transcript.parent.name.partition(MARK)
    if not (mark and head and tail) or transcript.suffix != ".jsonl":
        return None
    return transcript.parent.parent / head / transcript.name


def link(transcript: Path, create_key: bool = False, dry_run: bool = False) -> str:
    """Make the repo-root name for one transcript. Returns a one-word verdict.

    The repo-root key dir is created only when `create_key` says the repo is real (hook mode, from
    the session's own cwd). Otherwise a missing key means no session ever ran at that root, so the
    sweep links nothing there rather than inventing a project dir for a repo it cannot see.
    `dry_run` walks the same checks and stops before the first write, answering `would-link`.
    """
    dst = root_key_path(transcript)
    if dst is None:
        return "not-worktree"
    if not transcript.is_file():
        return "missing"
    if dst.exists():
        return "already" if os.path.samefile(transcript, dst) else "conflict"
    if not dst.parent.is_dir() and not create_key:
        return "no-root-key"
    if dry_run:
        return "would-link"
    if not dst.parent.is_dir():
        dst.parent.mkdir(mode=0o700, exist_ok=True)  # exist_ok: a concurrent hook may win
    try:
        os.link(transcript, dst)
    except FileExistsError:
        # a concurrent hook (two windows, one session) made it between the check and the link
        return "already" if os.path.samefile(transcript, dst) else "conflict"
    return "linked"


def _candidates(payload: dict, root: Path) -> list[Path]:
    out = []
    tp = payload.get("transcript_path")
    if isinstance(tp, str) and tp:
        out.append(Path(tp))
    sid = payload.get("session_id")
    # the transcript MOVES when the session enters a worktree; the path the hook was handed may
    # predate the move, so the session id finds it wherever it lives now
    # escaped: the id is a literal file stem, never a pattern — an unescaped `*` matched every
    # worktree transcript on the box and linked other sessions' files into other repos' keys
    if isinstance(sid, str) and sid and "/" not in sid:
        out += sorted(root.glob(f"*{MARK}*/{glob.escape(sid)}.jsonl"))
    return list(dict.fromkeys(out))


def _repo_root_exists(cwd: object) -> bool:
    """True when the session's cwd sits in `<repo>/.claude/worktrees/<name>` and `<repo>` exists."""
    if not isinstance(cwd, str):
        return False
    repo, mark, _ = cwd.partition("/.claude/worktrees/")
    return bool(mark and repo) and Path(repo).is_dir()


def hook(stdin_text: str) -> None:
    try:
        payload = json.loads(stdin_text or "{}")
        if not isinstance(payload, dict):
            return
        create_key = _repo_root_exists(payload.get("cwd"))
        for t in _candidates(payload, projects_root()):
            link(t, create_key=create_key)
    except Exception:  # noqa: BLE001 — fail-open: a hook must never block a turn
        return


def sweep(dry_run: bool) -> int:
    root = projects_root()
    tally: dict[str, int] = {}
    files = sorted(root.glob(f"*{MARK}*/*.jsonl"))
    for t in files:
        # one file's OSError (a read-only key dir, a transcript removed mid-sweep) is that file's
        # verdict, never the end of the sweep for every file after it
        try:
            verdict = link(t, dry_run=dry_run)
        except OSError as exc:
            verdict = "error"
            print(f"error: {t.parent.name}/{t.name}: {exc.strerror or exc}")
        tally[verdict] = tally.get(verdict, 0) + 1
        if verdict in ("conflict", "linked", "would-link"):
            print(f"{verdict}: {t.parent.name}/{t.name}")
    summary = " · ".join(f"{k} {v}" for k, v in sorted(tally.items())) or "nothing"
    print(f"worktree transcripts examined: {len(files)} under {root} — {summary}")
    return 1 if tally.get("conflict") or tally.get("error") else 0


def main(argv: list[str]) -> int:
    if "--sweep" in argv:
        return sweep("--dry-run" in argv)
    hook(sys.stdin.read() if not sys.stdin.isatty() else "")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
