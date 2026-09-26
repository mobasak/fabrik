#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/work-tracking.md
"""next_census — the NEXT: line measurement, as one script (T06, spec
2026-09-25-work-store-single-tracker-design.md § Why this exists, § Validation V5).

TRANSCRIPT SHAPE READ: one JSON object per line in ``<root>/<project-dir>/*.jsonl`` (a one-level
glob — a subagent's inline transcript row, ``isSidechain`` truthy, lives inside the same file and
is skipped, never counted as the parent session's own turn). Only a top-level key ``"type"`` ==
``"assistant"`` entry whose ``"message"`` is an object counts as a TURN; its text is every block
of ``"message"."content"`` (a list) whose own ``"type"`` == ``"text"``, joined in order (a bare
string ``content`` — some older rows — is read as-is). Every other entry shape — ``"user"``,
``"attachment"``, ``"queue-operation"``, a textless (tool-use/thinking-only) assistant row —
contributes NOTHING: a line inside one of those counts for nothing, on purpose (a NEXT: written
by the OPERATOR, inside a quoted mail body, or a tool result must never be read as the agent's
own). A row's identity — ``message.id`` (the API message id), falling back to the transcript
row's own top-level ``uuid`` when that is absent — is kept in one GLOBAL seen-set for the whole
run: a row already seen (the same assistant turn written twice, or copied verbatim into a resumed
session's file) contributes nothing to any count, the second time it is met.

A NEXT: LINE is one line of a turn's text — after ``str.strip()``, and OUTSIDE a fenced code
block (a line matching ```` ``` ```` or ``~~~``, any leading blockquote/whitespace, toggles the
fence; a NEXT: inside stays unread) — that starts with the literal ``"NEXT:"`` (the rule the
2026-09-25 fleet measurement used; deliberately simpler than ``thread_anchor._next_values``'s
markdown/quote handling). Its value is classified with ``work.classify_next`` (T05a), imported by
path from ``scripts/work.py`` beside this script — the harvest and the census share one
classifier so they never disagree about a line. A ``"hold"`` verdict is split for REPORTING
(never for the store) by its own leading word into ``none``, ``blocked``, or — anything else,
including a mid-line ``operator decision`` — ``operator-decision``.

Four measurements, one line each (plus a closing ``skipped:`` line, never a silent zero):

1. Classes — every NEXT: line of every turn, classified, with the session denominator.
2. Distinct — the count of distinct ``free-text`` values (normalised whitespace).
3. Sessions per repo — a session whose transcript's LAST turn carrying a NEXT: line ends on a
   ``free-text`` value ``thread_anchor._is_anchor`` accepts (``scripts/thread_anchor.py:465``,
   imported by path from ``Path(__file__).resolve().parents[1]``, the way
   ``scripts/thread_anchor.py:245-270`` loads ``work.py``) — grouped by repo, the Claude Code
   project directory's name (every non-alphanumeric character becomes ``-``) with a leading
   ``-opt-`` stripped.
4. ``--repo <path>`` — the store's Validation V5 reading: PASS when the repo's open ``kind: next``
   items whose ``next_at`` reads between 1 day in the future (clock skew) and 7 days in the past
   number no more than measurement 3's count for that repo, AND the repo shows more than 0 live
   claims (``work._live_claims``); an item hidden by a closed marker in ANOTHER tree
   (``work._closed_ids``) is never counted; else FAIL naming whichever bound missed; a repo with
   no store prints ``V5: no store in <path>``.

No write anywhere, no network. Exit 0 always except a bad argument (argparse's 2) — including a
non-positive ``--since``, since a zero or negative window silently reads as all-zero counts rather
than the "no window" it looks like. When ``scripts/work.py`` or ``scripts/thread_anchor.py``
itself fails to import, the run prints ``census unavailable — <file> import failed: <exc>``
instead of a real-looking (but meaningless) all-zero census, and still exits 0.

    python3 scripts/sysadmin/next_census.py --root <projects-tree> --since 7 [--repo <path>]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

_HERE = Path(__file__).resolve()
_SCRIPTS_DIR = _HERE.parents[1]  # scripts/sysadmin/next_census.py -> scripts/
_WORK_PATH = _SCRIPTS_DIR / "work.py"
_THREAD_ANCHOR_PATH = _SCRIPTS_DIR / "thread_anchor.py"

_WORK: ModuleType | None = None
_WORK_ERR: str | None = None
_THREAD_ANCHOR: ModuleType | None = None
_THREAD_ANCHOR_ERR: str | None = None


def _load_by_path(mod_name: str, path: Path) -> ModuleType:
    """One module, imported BY PATH — never re-implemented (the T05a -> T06 seam)."""
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"no loader for {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _work() -> ModuleType:
    """``scripts/work.py``, imported by path once per process; a failure is cached and re-raised
    (``census`` cannot classify a NEXT: line without ``work.classify_next``, so this is fatal to
    the run — ``main`` still guarantees exit 0, by reporting the failure instead of the counts)."""
    global _WORK, _WORK_ERR
    if _WORK is not None:
        return _WORK
    if _WORK_ERR is not None:
        raise ImportError(_WORK_ERR)
    try:
        _WORK = _load_by_path("_next_census_work", _WORK_PATH)
    except BaseException as e:  # noqa: BLE001 - reported, then re-raised as ImportError
        _WORK_ERR = f"cannot import {_WORK_PATH}: {type(e).__name__}: {e}"
        raise ImportError(_WORK_ERR) from None
    return _WORK


def _thread_anchor() -> ModuleType:
    """``scripts/thread_anchor.py``, imported by path once per process (its own ``_work()``
    loader, ``scripts/thread_anchor.py:245-270``, is the pattern this mirrors) — only its
    ``_is_anchor`` is used; loading it never touches ``work.py`` a second time."""
    global _THREAD_ANCHOR, _THREAD_ANCHOR_ERR
    if _THREAD_ANCHOR is not None:
        return _THREAD_ANCHOR
    if _THREAD_ANCHOR_ERR is not None:
        raise ImportError(_THREAD_ANCHOR_ERR)
    try:
        _THREAD_ANCHOR = _load_by_path("_next_census_thread_anchor", _THREAD_ANCHOR_PATH)
    except BaseException as e:  # noqa: BLE001 - reported, then re-raised as ImportError
        _THREAD_ANCHOR_ERR = f"cannot import {_THREAD_ANCHOR_PATH}: {type(e).__name__}: {e}"
        raise ImportError(_THREAD_ANCHOR_ERR) from None
    return _THREAD_ANCHOR


# Leading-word split of a "hold" verdict, for REPORTING only — mirrors work.py's own
# ``_HOLD_LEAD_RE`` leading-markdown-run shape so the two never drift apart on what "leading"
# means; unlike ``_HOLD_LEAD_RE`` this one captures WHICH word matched.
_HOLD_LEAD_SPLIT_RE = re.compile(r"^[\s*_`(\-]*(none|BLOCKED)(?![0-9A-Za-z])", re.I)


def _split_hold(text: str) -> str:
    """A ``"hold"`` classify_next verdict, split for reporting: ``none``/``blocked`` when the
    text STARTS (after any markdown run) with that word, else ``operator-decision`` — the
    catch-all for a mid-line ``operator decision`` or any other hold shape."""
    m = _HOLD_LEAD_SPLIT_RE.match(text)
    if m is None:
        return "operator-decision"
    return "none" if m.group(1).lower() == "none" else "blocked"


def _classify_for_report(work_mod: ModuleType, value: str) -> str:
    """One NEXT: value's REPORTING class — one of the five census buckets — via
    ``work.classify_next`` plus the hold split above. Pure."""
    cls = work_mod.classify_next(value)
    return _split_hold(value) if cls == "hold" else cls


_CLASS_ORDER = ("names-item", "none", "operator-decision", "blocked", "free-text")

# A fenced code block's opening/closing line — leading blockquote/whitespace tolerated so a
# quoted turn's fence is still recognised. A NEXT: line inside one is never read (item 8).
_FENCE_LINE_RE = re.compile(r"^[ \t>]*(?:```|~~~)")


def _extract_next_lines(text: str) -> list[str]:
    """Every NEXT: line's value, in order, from one turn's joined text, OUTSIDE any fenced code
    block — a line whose ``str.strip()`` starts with the literal ``"NEXT:"``. Deliberately no
    markdown/quote handling beyond the fence toggle (module docstring)."""
    out = []
    in_fence = False
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _FENCE_LINE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        s = line.strip()
        if s.startswith("NEXT:"):
            out.append(s[len("NEXT:") :].strip())
    return out


def _assistant_text(entry: dict[str, Any]) -> str:
    """Every text block of one ``"type": "assistant"`` transcript row, joined in order; empty
    when the row is tool-use/thinking-only or the row's shape is not what it claims to be."""
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        str(b.get("text") or "") for b in content if isinstance(b, dict) and b.get("type") == "text"
    )


def _row_identity(entry: dict[str, Any]) -> str | None:
    """This transcript row's identity for the global dedup set (item 3): the API message id
    (``message.id``) when present, else the row's own top-level ``uuid``; None when neither
    exists — such a row is never treated as a duplicate (there is nothing stable to key it on)."""
    msg = entry.get("message")
    if isinstance(msg, dict):
        mid = msg.get("id")
        if isinstance(mid, str) and mid:
            return mid
    row_uuid = entry.get("uuid")
    if isinstance(row_uuid, str) and row_uuid:
        return row_uuid
    return None


# The Claude Code project-directory name for an absolute repo path: EVERY character that is not
# an ASCII letter or digit becomes ``-`` (observed under ``~/.claude/projects/`` — not just the
# path separator, which under-mapped a name carrying a dot, space or underscore, item 4).
_NON_ALNUM_RE = re.compile(r"[^A-Za-z0-9]")


def _dir_name_for_path(path: Path) -> str:
    """The Claude Code project-directory name for an absolute repo path."""
    return _NON_ALNUM_RE.sub("-", str(path))


def _display_repo(dir_name: str) -> str:
    """The project directory's name with a leading ``-opt-`` stripped (spec's own convention);
    any other shape is shown with just its leading ``-`` dropped."""
    if dir_name.startswith("-opt-"):
        return dir_name[len("-opt-") :]
    return dir_name.lstrip("-") or dir_name


class _Scan:
    __slots__ = (
        "class_counts",
        "free_text_values",
        "sessions_total",
        "repo_sessions",
        "skipped_files",
        "skipped_lines",
    )

    def __init__(self) -> None:
        self.class_counts: Counter[str] = Counter()
        self.free_text_values: set[str] = set()
        self.sessions_total = 0
        self.repo_sessions: Counter[str] = Counter()
        self.skipped_files = 0
        self.skipped_lines = 0


def _scan(root: Path, since_days: int, work_mod: ModuleType, anchor_mod: ModuleType) -> _Scan:
    """One pass over every ``<root>/<project-dir>/*.jsonl`` transcript modified within the last
    ``since_days`` days, read line by line (never loaded whole into memory). A non-regular path
    or a file that cannot be opened is skipped whole (``skipped_files``, never the session
    denominator); inside a readable file, a line that is not JSON — including one whose parse
    overflows Python's recursion limit — is skipped the same way (``skipped_lines``) and the rest
    of the file is still read. A row already seen once this run (``_row_identity``) is silently
    skipped a second time — it contributes to no count."""
    result = _Scan()
    if not root.is_dir():
        return result
    cutoff = time.time() - since_days * 86400
    seen: set[str] = set()
    for path in sorted(root.glob("*/*.jsonl")):
        try:
            if not path.is_file():
                result.skipped_files += 1
                continue
            mtime = path.stat().st_mtime
        except OSError:
            result.skipped_files += 1
            continue
        if mtime < cutoff:
            continue
        repo = _display_repo(path.parent.name)
        last_turn_next_lines: list[str] = []
        try:
            with path.open("rb") as fh:
                result.sessions_total += 1
                for raw in fh:
                    try:
                        entry = json.loads(raw)
                    except Exception:  # noqa: BLE001 - any parse failure is one skipped line
                        result.skipped_lines += 1
                        continue
                    if not isinstance(entry, dict) or entry.get("type") != "assistant":
                        continue
                    if entry.get("isSidechain"):
                        continue
                    text = _assistant_text(entry)
                    if not text.strip():
                        continue
                    identity = _row_identity(entry)
                    if identity is not None:
                        if identity in seen:
                            continue
                        seen.add(identity)
                    next_lines = _extract_next_lines(text)
                    for raw_value in next_lines:
                        value = " ".join(raw_value.split())
                        cls = _classify_for_report(work_mod, value)
                        result.class_counts[cls] += 1
                        if cls == "free-text":
                            result.free_text_values.add(value)
                    if next_lines:
                        # overwritten only by a turn that itself carries a NEXT: line — a later
                        # textless (or duplicate) turn must never erase an earlier one (item 1)
                        last_turn_next_lines = next_lines
        except OSError:
            result.skipped_files += 1
            continue
        if last_turn_next_lines:
            final_value = " ".join(last_turn_next_lines[-1].split())
            if work_mod.classify_next(final_value) == "free-text" and anchor_mod._is_anchor(
                final_value
            ):
                result.repo_sessions[repo] += 1
    return result


def _classes_line(scan: _Scan) -> str:
    total = sum(scan.class_counts.get(c, 0) for c in _CLASS_ORDER)
    parts = " · ".join(f"{c} {scan.class_counts.get(c, 0)}" for c in _CLASS_ORDER)
    return f"next: {total} lines over {scan.sessions_total} sessions — {parts}"


def _distinct_line(scan: _Scan) -> str:
    return f"distinct free-text: {len(scan.free_text_values)}"


def _sessions_line(scan: _Scan) -> str:
    n = sum(scan.repo_sessions.values())
    if not scan.repo_sessions:
        return f"sessions with an accepted free-text NEXT: {n}"
    ordered = sorted(scan.repo_sessions.items(), key=lambda kv: (-kv[1], kv[0]))
    detail = " · ".join(f"{repo} {count}" for repo, count in ordered)
    return f"sessions with an accepted free-text NEXT: {n} ({detail})"


# An item due within this many seconds in the FUTURE still counts (one day of clock skew); one
# due further out than that is not a real due date yet and must not inflate the bound (item 2).
_V5_SKEW_S = 86400
_V5_WINDOW_S = 7 * 86400


def _v5_line(repo_arg: str, scan: _Scan, work_mod: ModuleType) -> str:
    """Validation V5: PASS when the repo's open ``kind: next`` items due within the window number
    no more than measurement 3's session count for that repo, AND the repo shows a live claim."""
    root = work_mod.repo_root(repo_arg)
    if root is None or not work_mod.has_store(root):
        return f"V5: no store in {repo_arg}"
    closed = work_mod._closed_ids(root)
    now = time.time()
    open_next = 0
    for item in work_mod._iter_items(root):
        if item.get("kind") != "next" or item.get("status") != "open":
            continue
        if item.get("id") in closed:
            continue
        at = work_mod._parse_iso(str(item.get("next_at") or ""))
        if at is None:
            continue
        delta = now - at.timestamp()
        if -_V5_SKEW_S <= delta <= _V5_WINDOW_S:
            open_next += 1
    live_claims = len(work_mod._live_claims(root))
    repo_name = _display_repo(_dir_name_for_path(root))
    sessions = scan.repo_sessions.get(repo_name, 0)
    if open_next <= sessions and live_claims > 0:
        return "V5: PASS"
    if live_claims == 0:
        return f"V5: FAIL — {live_claims} live claims"
    return f"V5: FAIL — {open_next} open next item(s) > {sessions} qualifying session(s)"


def _default_root() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    if base:
        return Path(base) / "projects"
    return Path.home() / ".claude" / "projects"


def _since_arg(value: str) -> int:
    """argparse ``type=`` for ``--since``: a positive integer only — 0 or a negative window
    reads as "everything is too old", a silent all-zero census that looks like a real reading
    rather than a bad argument (item 10)."""
    try:
        n = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer") from e
    if n <= 0:
        raise argparse.ArgumentTypeError(f"{value!r} must be a positive integer")
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--root", type=Path, default=None, help="the <repo>/<session>.jsonl root")
    parser.add_argument(
        "--since", type=_since_arg, default=7, help="only files modified this many days"
    )
    parser.add_argument("--repo", default=None, help="print V5's reading for this repo path")
    args = parser.parse_args(argv)

    root = args.root if args.root is not None else _default_root()

    try:
        work_mod = _work()
    except ImportError as e:
        print(f"census unavailable — {_WORK_PATH.name} import failed: {e}")
        return 0
    try:
        anchor_mod = _thread_anchor()
    except ImportError as e:
        print(f"census unavailable — {_THREAD_ANCHOR_PATH.name} import failed: {e}")
        return 0

    scan = _scan(root, args.since, work_mod, anchor_mod)

    print(_classes_line(scan))
    print(_distinct_line(scan))
    print(_sessions_line(scan))
    if args.repo:
        print(_v5_line(args.repo, scan, work_mod))
    print(f"skipped: {scan.skipped_files} file(s), {scan.skipped_lines} line(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
