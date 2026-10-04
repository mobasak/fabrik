#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/work-tracking.md
"""next_census — the NEXT: line measurement, as one script (T06, spec
2026-09-25-work-store-single-tracker-design.md § Why this exists, § Validation V5).

TRANSCRIPT SHAPE READ: one JSON object per line in ``<root>/<project-dir>/*.jsonl`` (a one-level
glob — a subagent's inline transcript row, ``isSidechain`` truthy, lives inside the same file and
is skipped, never counted as the parent session's own turn). Only a top-level key ``"type"`` ==
``"assistant"`` entry whose ``"message"`` is an object is a ROW the census reads; its text is
every block of ``"message"."content"`` (a list) whose own ``"type"`` == ``"text"``, joined in
order (a bare string ``content`` — some older rows — is read as-is). A main-thread ``"user"`` row
with content (text or an image, no ``tool_result`` block) ends a TURN — that is where Stop fired —
unless the turn is still mid-tool (the last assistant row carried a ``tool_use`` block, or a tool
result came since); an ``[Request interrupted by user`` row ends the turn WITHOUT judging it (no
Stop fired). A user row's own text is never read as a NEXT.
Every other entry shape — a tool-result ``"user"`` row, ``"attachment"``, ``"queue-operation"``,
a textless (tool-use/thinking-only) assistant row — contributes NOTHING: a line inside one of
those counts for nothing, on purpose (a NEXT: written by the OPERATOR, inside a quoted mail body,
or a tool result must never be read as the agent's own). A turn's FINAL text is its last
assistant text row with list content — the one the Stop harvest judges
(``thread_anchor._final_message_text``, which skips a bare-string row). A row's identity — the transcript row's own top-level ``uuid`` (unique per JSONL row: Claude
Code writes one row per content BLOCK, and every block of one API message shares that message's
``message.id``, so keying on ``message.id`` alone would silently drop a NEXT: line living in a
message's LATER block), falling back to ``(message.id, the row's own extracted text)`` only when
``uuid`` is absent — is kept in one GLOBAL seen-set for the whole run: a row already seen (the
same row written twice, or copied verbatim — keeping its uuid — into a resumed session's file)
contributes nothing to any count, the second time it is met. Files are read in path order, so a
row shared by two files is credited to the one whose path sorts first — a row first met in ANOTHER
file is never judged as this file's turn, while a row written twice in the same file is simply
counted once. Which file wrote a shared row first is not knowable from the files (a resumed or
forked copy keeps the original rows' timestamps), and it does not occur today: measured
2026-10-04 over the 7-day window, no row ``uuid`` sat in two files among ~1.4M main-thread
assistant rows, each carrying its own file's ``sessionId``.

A NEXT: LINE is one value ``thread_anchor._next_values`` reads from a turn's text — the
harvest's own reader, so the census counts exactly the lines the harvest can turn into items:
bold (``**NEXT:**``), bulleted (``- NEXT:``) and quoted (``> NEXT:``) footers count, a NEXT:
inside a closed fenced block does not, and a quoted value counts only in a ROW with no unquoted
one; a row's operative value is its LAST one. Its value is classified with
``work.classify_next`` (T05a), imported by path from ``scripts/work.py`` beside this script — the harvest and the census share one
classifier so they never disagree about a line. A ``"hold"`` verdict is split for REPORTING
(never for the store) by its own leading word into ``none``, ``blocked``, or — anything else,
including a mid-line ``operator decision`` — ``operator-decision``.

Four measurements, one line each (plus a closing ``skipped:`` line, never a silent zero):

1. Classes — every NEXT: line of every row, classified, with the session denominator: the
   transcripts in the window that carry at least one main-thread assistant text row (a user-only
   or sidechain-only file is not a session; headless ``-p`` sessions are).
2. Distinct — the count of distinct ``free-text`` values (normalised whitespace).
3. Sessions per repo — a session at least one of whose turns ENDED on a NEXT the harvest keeps:
   the operative value of the turn's final text, cut to the 300 characters the register judges,
   is ``free-text`` and ``thread_anchor._is_anchor`` accepts it (the spec's "ended at least one
   turn on a free-text NEXT the register accepts"; ``thread_anchor`` imported by path from ``Path(__file__).resolve().parents[1]``, the way
   ``scripts/thread_anchor.py:245-270`` loads ``work.py``) — grouped by repo, the Claude Code
   project directory's name (every non-alphanumeric character becomes ``-``) with a leading
   ``-opt-`` stripped.
4. ``--repo <path>`` — the store's Validation V5 reading: PASS when the repo's open ``kind: next``
   items whose ``next_at`` reads between 1 day in the future (clock skew) and 7 days in the past
   number no more than measurement 3's count, AND the repo shows more than 0 live claims
   (``work._live_claims``). Both sides cover the same trees — the main checkout and every
   registered worker tree under its ``.claude/worktrees/`` (``work._workers``; harness
   ``agent-<hex>`` trees and scratch worktrees elsewhere are out): items are read from each tree's
   store and counted once per id, sessions are summed over ``<main>`` and every
   ``<main>--claude-worktrees-<tree>`` project directory (by the raw directory name, never the
   display name); an id is closed when any tree's copy is closed or hidden by a closed marker
   (``work._closed_ids``), and is in the window by its FRESHEST ``next_at`` across copies; a tree
   git cannot read is skipped, and when git cannot list the trees ``--repo``'s own tree is read as
   the main checkout (fail-soft — the census is advisory); else FAIL naming whichever bound missed; a repo with
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
    loader, ``scripts/thread_anchor.py:245-270``, is the pattern this mirrors) — its
    ``_next_values`` and ``_is_anchor`` are used; loading it never touches ``work.py`` a second
    time."""
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


_INTERRUPT_MARK = "[Request interrupted by user"


def _user_row(entry: dict[str, Any]) -> str | None:
    """What a main-thread ``"user"`` row is: ``"tool_result"`` (the middle of a turn),
    ``"interrupt"`` (Claude Code's ``[Request interrupted by user`` marker — the turn was cut
    short and no Stop fired), ``"content"`` (text or an image — typed by the operator or injected
    by Claude Code), or None (not a user row, or an empty one). Whether a ``"content"`` row ENDS a
    turn depends on the row before it, not on the row itself (``_scan``)."""
    if entry.get("type") != "user":
        return None
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        kinds = {b.get("type") for b in content if isinstance(b, dict)}
        if "tool_result" in kinds:
            return "tool_result"
        if not kinds:
            return None
        text = " ".join(
            str(b.get("text") or "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
        if not text.strip():
            return "content"  # an image or another non-text block
    else:
        return None
    if not text.strip():
        return None
    return "interrupt" if text.lstrip().startswith(_INTERRUPT_MARK) else "content"


def _qualifies(work_mod: ModuleType, anchor_mod: ModuleType, turn_final: str) -> bool:
    """Whether one turn ENDED on a NEXT the harvest keeps as a ``next`` item: the operative value
    of the turn's final text, cut to the 300 characters the register judges, is ``free-text`` and
    ``thread_anchor._is_anchor`` accepts it."""
    values = anchor_mod._next_values(turn_final) if turn_final else []
    if not values:
        return False
    final_value = " ".join(values[-1][:300].split())
    return work_mod.classify_next(final_value) == "free-text" and bool(
        anchor_mod._is_anchor(final_value)
    )


def _asks_for_tool(entry: dict[str, Any]) -> bool:
    """Whether an assistant row carries a ``tool_use`` block — the turn goes on after it."""
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    return isinstance(content, list) and any(
        isinstance(b, dict) and b.get("type") == "tool_use" for b in content
    )


def _row_identity(entry: dict[str, Any], text: str) -> str | None:
    """This transcript row's identity for the global dedup set: the row's own top-level ``uuid``
    when present (one JSONL row per content block, so a message's several blocks — sharing one
    ``message.id`` — each keep their OWN uuid and must never collide); only when ``uuid`` is
    absent does the key fall back to ``(message.id, text)`` — ``text`` (this row's own
    ``_assistant_text``) disambiguates sibling blocks of that message when there is no row-level
    uuid to key on. None when neither ``uuid`` nor ``message.id`` exists — such a row is never
    treated as a duplicate (there is nothing stable to key it on)."""
    row_uuid = entry.get("uuid")
    if isinstance(row_uuid, str) and row_uuid:
        return row_uuid
    msg = entry.get("message")
    mid = msg.get("id") if isinstance(msg, dict) else None
    if isinstance(mid, str) and mid:
        return f"{mid}\x00{text}"
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
        "dir_sessions",
        "skipped_files",
        "skipped_lines",
    )

    def __init__(self) -> None:
        self.class_counts: Counter[str] = Counter()
        self.free_text_values: set[str] = set()
        self.sessions_total = 0
        self.repo_sessions: Counter[str] = Counter()
        # the same count keyed by the RAW project-directory name: display names collapse
        # (/opt/x and /x both show as "x"), so V5 keys on the raw name
        self.dir_sessions: Counter[str] = Counter()
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
    seen: dict[str, Path] = {}  # row identity -> the file that met it first
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
        counted = False
        qualifies = False
        met_here: set[str] = set()
        turn_final = ""  # the current turn's last main-thread assistant text: what Stop harvests
        # Stop fires when the assistant ENDS its turn, so a user row ends a turn unless the turn is
        # still mid-tool — the last assistant row asked for a tool, or a tool result came since:
        # rows Claude Code injects mid-turn (a loaded skill, a command re-invocation) follow a tool
        # result, while Stop-hook feedback, a peer message and the operator's next prompt follow
        # the assistant's last row (measured 2026-10-04 over the 7-day window: every isMeta skill
        # row sat after a tool result or another user row)
        mid_tool = False
        try:
            with path.open("rb") as fh:
                for raw in fh:
                    try:
                        entry = json.loads(raw)
                    except Exception:  # noqa: BLE001 - any parse failure is one skipped line
                        result.skipped_lines += 1
                        continue
                    if not isinstance(entry, dict) or entry.get("isSidechain"):
                        continue
                    kind = _user_row(entry)
                    if kind == "tool_result":
                        mid_tool = True
                        continue
                    if kind == "interrupt":
                        # no Stop fired, so the harvest never judged this turn: drop its text
                        turn_final = ""
                        mid_tool = False
                        continue
                    if kind == "content":
                        if not mid_tool:
                            qualifies = qualifies or _qualifies(work_mod, anchor_mod, turn_final)
                            turn_final = ""
                        continue
                    if entry.get("type") != "assistant":
                        continue
                    mid_tool = _asks_for_tool(entry)
                    text = _assistant_text(entry)
                    if not text.strip():
                        continue
                    identity = _row_identity(entry, text)
                    if identity is not None:
                        first = seen.setdefault(identity, path)
                        if first != path:
                            # a copied row belongs to another file's turn: never judge it here,
                            # and never let an earlier row stand in as this turn's final text
                            turn_final = ""
                            continue
                        if identity in met_here:
                            continue  # the same row written twice in this file: counted once
                        met_here.add(identity)
                    if not counted:
                        # a session is a transcript with a main-thread assistant text row of its own
                        result.sessions_total += 1
                        counted = True
                    msg = entry.get("message")
                    if isinstance(msg, dict) and isinstance(msg.get("content"), list):
                        # the harvest's _final_message_text reads list content only
                        turn_final = text
                    for raw_value in anchor_mod._next_values(text):
                        value = " ".join(raw_value.split())
                        cls = _classify_for_report(work_mod, value)
                        result.class_counts[cls] += 1
                        if cls == "free-text":
                            result.free_text_values.add(value)
        except OSError:
            result.skipped_files += 1
            continue
        if qualifies or _qualifies(work_mod, anchor_mod, turn_final):
            result.repo_sessions[repo] += 1
            result.dir_sessions[path.parent.name] += 1
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
    no more than measurement 3's session count for that repo, AND the repo shows a live claim.
    Both sides cover the same trees: the main checkout and every registered worker tree under its
    ``.claude/worktrees/`` (``work._workers``) — a worktree session harvests into its OWN tree's
    store until the branch merges, so items are read from each tree and counted once per id.
    When git cannot list the trees, ``--repo``'s own tree is read as the main checkout (fail-soft:
    the census is advisory, and the PASS/FAIL line still prints the bound it compared)."""
    root = work_mod.repo_root(repo_arg)
    if root is None or not work_mod.has_store(root):
        return f"V5: no store in {repo_arg}"
    main = work_mod._worktrees(root)[0].resolve()
    now = time.time()
    # one id, several copies (a worker forks with master's items): a close in ANY tree is final
    # (closure is terminal, and work.py's shared closed marker hides it in every tree), while the
    # window is judged on the FRESHEST next_at — a stale fork-time copy must not veto a live one
    closed_ids: set[str] = set()
    latest_at: dict[str, float] = {}
    for tree in [main, *work_mod._workers(main).values()]:
        try:
            closed = work_mod._closed_ids(tree)
            items = list(work_mod._iter_items(tree))
        except work_mod.WorkError:
            continue  # e.g. registered but deleted (prunable): git cannot read it, nothing to count
        for item in items:
            if item.get("kind") != "next":
                continue
            item_id = str(item.get("id"))
            if item.get("status") != "open" or item_id in closed:
                closed_ids.add(item_id)
                continue
            at = work_mod._parse_iso(str(item.get("next_at") or ""))
            if at is not None:
                latest_at[item_id] = max(latest_at.get(item_id, at.timestamp()), at.timestamp())
    open_next = sum(
        1
        for item_id, at in latest_at.items()
        if item_id not in closed_ids and -_V5_SKEW_S <= now - at <= _V5_WINDOW_S
    )
    live_claims = len(work_mod._live_claims(root))
    sessions = _repo_sessions(main, scan, work_mod)
    if open_next <= sessions and live_claims > 0:
        # the bound is printed on PASS too: a vacuous 0 <= 0 and a real 3 <= 3 are different readings
        return (
            f"V5: PASS — {open_next} open next item(s) <= {sessions} qualifying session(s), "
            f"{live_claims} live claim(s)"
        )
    if live_claims == 0:
        return f"V5: FAIL — {live_claims} live claims"
    return f"V5: FAIL — {open_next} open next item(s) > {sessions} qualifying session(s)"


def _repo_sessions(main: Path, scan: _Scan, work_mod: ModuleType) -> int:
    """Measurement 3's count for the main checkout ``main`` and every worktree under its
    ``.claude/worktrees/`` — hub work runs in linked worktrees whose transcripts live under their
    own project directories (``<main's name>--claude-worktrees-<tree>``). Keyed by name, not by
    ``git worktree list``: a tree removed inside the window keeps its transcripts, and the same
    transcripts must give the same reading. A tree's name must be a valid worker name (what
    ``work._workers`` accepts on the items side); harness trees (``agent-<hex>``) are left out — no
    Stop hook harvests a subagent — and so is a scratch worktree outside ``.claude/worktrees/``."""
    base = _dir_name_for_path(main)
    prefix = base + "--claude-worktrees-"
    return sum(
        count
        for name, count in scan.dir_sessions.items()
        if name == base
        or (
            name.startswith(prefix)
            and work_mod._valid_name(name[len(prefix) :])
            and not work_mod._HARNESS_RE.fullmatch(name[len(prefix) :])
        )
    )


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
