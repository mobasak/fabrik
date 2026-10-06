#!/usr/bin/env python3
# AFTER-EDIT: tests/test_work.py, tests/test_work_claims.py, tests/test_work_sync.py, tests/test_work_migrate.py, docs/reference/work-tracking.md, tests/test_work_coordinator.py, tests/test_stop_hook_coordinator.py
"""Work tracking — one open-work record per repo, shared by its agents (spec 2026-09-24).

THE STORE. One pretty-printed, sorted-key JSON file per item under ``<repo>/.fabrik/work/``,
committed with the code; ``config.json`` beside them names the distributor. Items are never
deleted — they end ``done`` or ``dropped``. Shared, unversioned state (the lock, and later the
claims, closed markers and readings) lives in ``<git common dir>/fabrik-work/``, which the main
checkout and every worktree of the repo see as one directory.

NO IMPLICIT STORE. ``init`` is the only writer of ``config.json``, save one key a merge owner
sets by hand: ``"autonomy": true`` turns on the Stop ladder (``_autonomy_candidates``). Every other verb, in a repo
without ``.fabrik/work/``, exits non-zero naming ``init`` and creates nothing — not in the tree,
not in the git common directory.

THE LOCK. Every item write takes one exclusive ``fcntl`` lock on ``fabrik-work/.lock`` (re-entrant
within one thread) and writes through a unique, fsynced ``*.tmp`` plus ``os.replace`` — the store's
``.gitignore`` keeps an orphaned temp out of commits. ``init`` alone takes no lock: config.json is
an exclusive link (one winner), and the lock's directory must not exist before the store does.
CLI verbs wait 10 s and then FAIL LOUD; the hook-facing callers (T01b) pass a 2 s timeout and
``fail_open=True``. Every wait over 0.1 s is appended to ``fabrik-work/readings.jsonl``.
COBRA (D-253): the cheapest way to keep ``readings.jsonl`` quiet is to skip the lock; every write
path here goes through ``_store_lock``, and the readings count WAITS, not writes, so a lockless
write shows up as a torn item instead of as silence.

CLAIMS AND CLOSING (T01b). ``claim``/``release`` hold a leased claim in ``fabrik-work/claims/``;
"claimed" is derived from a live lease, never stored on the item. ``done`` (a commit naming the id),
``drop`` and ``answer`` write the item in the caller's own tree only, plus a closed marker in
``fabrik-work/closed/`` so the other trees stop listing it. ``work.py`` never writes
``docs/DECISIONS.md``. The hook-facing API (``on_harvest``, ``ensure_decision_item[s]``,
``has_msg_digest``, ``prompt_block``) is fail-open and creates nothing in a store-less repo.

STATUS AND DRIFT (T02). ``status`` lists items, uncommitted item files (``git status
--porcelain``, a listing not a drift class) and the eight drift classes of spec § Spec and plan
state is derived, never copied. ``sync --check`` prints the same drift, appends one ``kind: sync``
reading to ``readings.jsonl``, and exits non-zero on classes 2-6 only once the repo has migrated
and ``readings.jsonl`` shows 7 consecutive clean calendar days after ``migrated_at`` — re-derived
from the readings on every run, never a stored flag. Spec and plan Status values are read with
``scripts/enforcement/check_convergence.py``'s ``_STATUS_LINE``, plan Ticket Boards with
``check_plan_tickets.py``'s ``_board_states``, and a plan's designated spec citation with
``check_stage_artifacts.py``'s ``_designated_spec_citations`` — imported by file path from the
repo's own ``scripts/enforcement/``, falling back to an equivalent local regex (with one stderr
line) when that import fails.

This module is import-safe: nothing runs outside ``if __name__ == "__main__"``.
Implemented: init, add, assign, ready [--mine], next (T01a); claim, release, done, drop, answer and
the hook API (T01b); status, sync --check (T02); render, migrate-backlog (T03).
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover — non-POSIX; the store is POSIX-only
    fcntl = None  # type: ignore[assignment]

STORE_REL = Path(".fabrik") / "work"
SHARED_NAME = "fabrik-work"
KINDS = ("backlog", "decision", "feedback", "mail", "next", "task")
LINKED_KINDS = ("mail", "feedback")  # made and closed only by open_linked/close_linked
STATUSES = ("open", "blocked", "awaiting-operator", "done", "dropped")
RESOLVED = ("done", "dropped")
LINK_KEYS = ("spec", "plan", "decision")  # written on EVERY item
EXTRA_LINK_KEYS = ("mail", "command", "session")  # written only when non-empty
DEFAULT_PRIORITY = 2
CLI_LOCK_TIMEOUT_S = 10.0
HOOK_LOCK_TIMEOUT_S = 2.0
HOOK_GIT_TIMEOUT_S = 1.0  # every git call a hook-facing function makes (P2, T04 review)
DEFAULT_LEASE_S = 7200  # a claim's lease: 2 h, renewed by every write of its session
MARKER_MAX_AGE_S = 14 * 86400  # a closed marker older than this stops hiding its item
LINE_MAX = 300  # one prompt_block line
_DECISION_ID_RE = re.compile(r"D-[0-9]+")
_ITEM_REF_RE = re.compile(r"(?<![0-9A-Za-z_])W-[0-9a-f]{8}(?![0-9A-Za-z_])")  # a whole word
_BRANCH_RE = re.compile(r"[A-Za-z0-9._/-]+")
_QUESTION_RE = re.compile(
    r"^[ \t]*(?:[-*\u2022][ \t]+)?[*_]{0,2}Question[*_]{0,2}[ \t]*:[*_]{0,2}[ \t]*(.*)$",
    re.I | re.M,
)
_GROUND_RE = re.compile(r"\([ \t]*ground:[ \t]*`?([A-Za-z-]+)", re.I)
READING_MIN_WAIT_S = 0.1
# ── T02: status / sync drift ────────────────────────────────────────────────────────────────
SPECS_DIR = Path("docs") / "superpowers" / "specs"
PLANS_DIR = Path("docs") / "development" / "plans"
_PLAN_DIR_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+$")
_PLAN_FILE_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+\.md$")
_BACKLOG_REL = "docs/STRATEGIC_BACKLOG.md"
# T03 review pass 1, Decision B.2: match START/END as WHOLE LINES only — a line merely QUOTING the
# marker in prose (A-O4) must never be read as the real block. Multiple STARTs or an orphan
# START/END is a loud refusal (`_find_backlog_block`), never a silent first-match guess.
# A-O24: `\r?` before `$` — a marker line is still matched when it is itself CRLF-terminated in a
# file `render` is NOT blanket-normalizing (a non-uniform file; see `cmd_render`).
_BACKLOG_START_RE = re.compile(r"^<!-- AUTO-GENERATED:BACKLOG:START -->\r?$", re.M)
_BACKLOG_END_RE = re.compile(r"^<!-- AUTO-GENERATED:BACKLOG:END -->\r?$", re.M)
# Decision B.6 (A-O13): class-7 reads only an id in a rendered line's TRAILING backtick-parens
# position — never any W-xxxxxxxx-shaped substring anywhere in the block (which could appear
# inside an item's own title).
_BACKLOG_TRAILING_ID_RE = re.compile(r"\(`(W-[0-9a-f]{8})`\)[ \t]*$", re.M)


def _find_backlog_block(text: str) -> tuple[int, int, int, int] | None:
    """``(start_begin, start_end, end_begin, end_end)`` character offsets of the ONE whole-line
    START/END marker pair in ``text``, or ``None`` when neither is present. Raises ``WorkError``
    (a CLI verb fails loud, per spec § Lifecycle — Degradation is a hook-side rule only) on more
    than one START line, an orphan START with no END, an orphan END with no START, more than one
    END line, or an END that precedes its START — never silently picking the first match, which
    is exactly how A-O4 corrupted hand-written text that merely quoted the marker."""
    starts = list(_BACKLOG_START_RE.finditer(text))
    ends = list(_BACKLOG_END_RE.finditer(text))
    if not starts and not ends:
        return None
    if len(starts) > 1:
        raise WorkError(
            f"{_BACKLOG_REL} has {len(starts)} AUTO-GENERATED:BACKLOG:START lines — expected "
            "exactly one; refusing to guess which is the real block"
        )
    if not starts:
        raise WorkError(
            f"{_BACKLOG_REL} has an AUTO-GENERATED:BACKLOG:END line with no matching START"
        )
    if not ends:
        raise WorkError(
            f"{_BACKLOG_REL} has an AUTO-GENERATED:BACKLOG:START line with no matching END — "
            "refusing to write past an unterminated block"
        )
    if len(ends) > 1:
        raise WorkError(
            f"{_BACKLOG_REL} has {len(ends)} AUTO-GENERATED:BACKLOG:END lines — expected exactly "
            "one; refusing to guess which is the real block"
        )
    s, e = starts[0], ends[0]
    if e.start() < s.end():
        raise WorkError(f"{_BACKLOG_REL}'s AUTO-GENERATED:BACKLOG END precedes its START")
    return s.start(), s.end(), e.start(), e.end()


BLOCKING_CLASSES = frozenset({2, 3, 4, 5, 6})  # classes 1, 7, 8 are always advisory
RECENT_WINDOW_S = MARKER_MAX_AGE_S  # 14 days — shared by class 6's two predicates
STALE_PLAN_DAYS = 7  # class 2's "more than 7 days" CONVERGED-with-nothing-carrying-it threshold
SYNC_BLOCKING_DAYS = 7  # consecutive clean calendar days after migrated_at before sync blocks
_PLAN_STATUS_ALIASES = {
    "IN_PROGRESS": "IN-PROGRESS",
    "COMPLETE": "EXECUTED",
    "DONE": "EXECUTED",
    "SHIPPED": "EXECUTED",
    "PLANNED": "DRAFT",
}
_PLAN_STATUSES = frozenset({"DRAFT", "IN-PROGRESS", "CONVERGED", "EXECUTED", "BLOCKED"})
DECISIONS_PY = Path("/opt/fabrik/scripts/decisions.py")  # hub-only, by absolute path
WHOAMI_PY = Path(__file__).with_name("whoami_agent.py")
DOCS_UPDATER_PY = Path(__file__).with_name("docs_updater.py")  # T03: migrate-backlog / render
NAME_RULE = "[a-z0-9-]{1,32}"  # whoami_agent.py's agent-name rule: owners are agent names only
_NAME_RE = re.compile(NAME_RULE)
# A tag is the constraint that must travel WITH an item (tryton-crm 01M3PM5H) — the repo's own
# vocabulary, e.g. `runtime` for "applying this needs the shared-runtime act" (multi-agent model
# § The shared runtime). Written only when non-empty, so an untagged item's JSON never changes.
# COBRA (D-253): a tag is a label, never a gate — nothing refuses or orders on it, so the cheap
# path (tag nothing) costs only what the tag was for: the distributor seeing the constraint.
TAG_RULE = "[a-z0-9][a-z0-9-]{0,31}"
_TAG_RE = re.compile(TAG_RULE)
_ID_RE = re.compile(r"W-[0-9a-f]{8}")  # always .fullmatch — `$` admits a trailing newline
_GIT_TIMEOUT_S = 10.0
# Re-entrancy is per THREAD: the depth of each (shared dir, thread) hold. flock is per open-file
# description, so a nested acquisition through a fresh fd would wait on its own outer hold; another
# thread must NOT share the hold, so it opens its own fd and the flock excludes it.
_HELD: dict[tuple[str, int], int] = {}
_HELD_GUARD = threading.Lock()


class WorkError(Exception):
    """A loud, named CLI failure: ``main`` prints it and exits non-zero."""


class StoreBusyError(WorkError):
    """The store lock was not taken within the caller's timeout (fail-loud mode)."""


# ── paths ────────────────────────────────────────────────────────────────────────────────────

# P2 (T04 review): a hook-facing call re-ran `git rev-parse` several times per hook against a 5 s
# Stop subprocess / 10 s prompt hook, each at the CLI's 10 s timeout. `_GIT_TIMEOUT_OVERRIDE` is a
# per-thread budget every `_git()` call (and `_base_statuses`' own raw `subprocess.run`) reads;
# `_hook_git_budget()` narrows it to `HOOK_GIT_TIMEOUT_S` for the duration of one hook-facing call,
# so a slow git fails FAST inside it — the existing fail-open `except Exception` in each of those
# six functions already turns that into the function's ordinary empty value, no new handling
# needed. CLI verbs never enter this context, so they keep the full `_GIT_TIMEOUT_S`.
_GIT_TIMEOUT_OVERRIDE = threading.local()
# Per-process caches for `_repo_root`/`_common_dir`, keyed by the RESOLVED input path (never the
# raw string a caller passed — "." resolves against the CURRENT cwd each time, so a mid-process
# chdir misses the cache instead of reading a stale one). A repo's top level and common dir don't
# change for a given resolved path within one process, and a hook that calls several hook-facing
# functions in sequence previously paid for both `git rev-parse` calls every single time.
_REPO_ROOT_CACHE: dict[str, Path] = {}
_COMMON_DIR_CACHE: dict[str, Path] = {}


def _git_timeout() -> float:
    return getattr(_GIT_TIMEOUT_OVERRIDE, "value", _GIT_TIMEOUT_S)


@contextlib.contextmanager
def _hook_git_budget() -> Iterator[None]:
    """Caps every git call made anywhere inside this block — any call depth — to
    ``HOOK_GIT_TIMEOUT_S``. Wraps each of the hook-facing entry points (``repo_root``,
    ``has_store``, ``on_harvest``, ``ensure_decision_item``/``ensure_decision_items``,
    ``open_linked``/``close_linked``, ``has_msg_digest``, ``prompt_block``)."""
    prev = getattr(_GIT_TIMEOUT_OVERRIDE, "value", None)
    _GIT_TIMEOUT_OVERRIDE.value = HOOK_GIT_TIMEOUT_S
    try:
        yield
    finally:
        if prev is None:
            del _GIT_TIMEOUT_OVERRIDE.value
        else:
            _GIT_TIMEOUT_OVERRIDE.value = prev


def _git(path: Path | str, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            timeout=_git_timeout(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkError(f"git {' '.join(args)} failed in {path}: {exc}") from exc
    if proc.returncode != 0:
        lines = proc.stderr.strip().splitlines()
        reason = lines[0] if lines else f"exit {proc.returncode}"
        raise WorkError(f"git {' '.join(args)} failed in {path}: {reason}")
    return proc.stdout.strip()


def _repo_root(path: Path | str = ".") -> Path:
    """The work tree's top level, so a caller may pass any subdirectory. Cached per process."""
    key = str(Path(path).resolve())
    cached = _REPO_ROOT_CACHE.get(key)
    if cached is not None:
        return cached
    root = Path(_git(path, "rev-parse", "--show-toplevel")).resolve()
    _REPO_ROOT_CACHE[key] = root
    return root


def _store_dir(repo: Path) -> Path:
    """``<repo>/.fabrik/work`` — the committed items and ``config.json``."""
    return repo / STORE_REL


def _config_path(repo: Path) -> Path:
    return _store_dir(repo) / "config.json"


def _common_dir(repo: Path) -> Path:
    """The git common directory: shared by the main checkout and every worktree. Cached per
    process."""
    key = str(Path(repo).resolve())
    cached = _COMMON_DIR_CACHE.get(key)
    if cached is not None:
        return cached
    common = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
    _COMMON_DIR_CACHE[key] = common
    return common


def _shared_dir(repo: Path) -> Path:
    """``<git common dir>/fabrik-work`` — lock, claims, closed markers, readings (unversioned)."""
    return _common_dir(repo) / SHARED_NAME


def _item_path(repo: Path, item_id: str) -> Path:
    if not _ID_RE.fullmatch(item_id):
        raise WorkError(f"{item_id!r} is not an item id (W- plus 8 hex characters)")
    return _store_dir(repo) / f"{item_id}.json"


def _rel(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def _has_store(repo: Path) -> bool:
    return _config_path(repo).is_file()


def _store_elsewhere(repo: Path) -> Path | None:
    """Another working tree of this repository that holds a store, or None. All of them share one
    git common dir (lock, claims, readings), so a second ``init`` anywhere would fork config."""
    for tree in _worktrees(repo):
        if tree != repo and _has_store(tree):
            return tree
    return None


def _require_store(repo: Path) -> None:
    if _has_store(repo):
        return
    other = _store_elsewhere(repo)
    if other is not None:
        raise WorkError(
            f"no work store in this worktree {repo}, but the working tree {other} has one — "
            "merge or rebase onto its branch; do not run `work.py init` here"
        )
    raise WorkError(
        f"no work store in {repo} ({STORE_REL}/config.json is missing) — "
        "run `work.py init` first; no store is ever created implicitly"
    )


# ── identity ─────────────────────────────────────────────────────────────────────────────────


def _valid_name(value: str) -> bool:
    return bool(_NAME_RE.fullmatch(value))


def _agent_name(*, session: str = "") -> str:
    """The resolver's name (``whoami_agent.resolve_agent_name()``, imported by path) when it gives
    one, else ``CLAUDE_AGENT`` when it matches NAME_RULE, else — only when ``session`` is given and
    ``CLAUDE_CODE_SESSION_ID`` is empty (a hook process handed its session in the payload) — the
    whoami binding for ``session`` (last row wins, whoami's own name rule), else ""; never raises.
    Both paths apply the same name rule, so a failed import never loosens identity; the env
    session id, when set, always wins over the passed one."""
    name = ""
    mod: Any = None
    try:
        spec = importlib.util.spec_from_file_location("_work_whoami", WHOAMI_PY)
        if spec is not None and spec.loader is not None:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            name = str(mod.resolve_agent_name() or "")
    except Exception:
        name = ""
    if _valid_name(name):
        return name
    env = (os.environ.get("CLAUDE_AGENT") or "").strip()
    if _valid_name(env):
        return env
    if not session or mod is None or (os.environ.get("CLAUDE_CODE_SESSION_ID") or "").strip():
        return ""
    bound = ""
    try:
        for row in mod._rows(mod.store_path()):  # LAST row wins, exactly as whoami resolves
            value = str(row.get("name") or "")
            if row.get("session_id") == session and mod._NAME_RE.fullmatch(value):
                bound = value
    except Exception:
        bound = ""
    return bound if _valid_name(bound) else ""


def _actor_label() -> str:
    """The caller for an error message: its name, or why it has none (unset vs invalid)."""
    name = _agent_name()
    if name:
        return name
    raw = (os.environ.get("CLAUDE_AGENT") or "").strip()
    if not raw:
        return "unnamed (CLAUDE_AGENT unset)"
    return f"unnamed (CLAUDE_AGENT={raw!r} is not a valid agent name, {NAME_RULE})"


def _session() -> str:
    return (os.environ.get("CLAUDE_CODE_SESSION_ID") or "").strip()


# ── atomic IO ────────────────────────────────────────────────────────────────────────────────


def _dump(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _umask() -> int:
    """The process umask, read without changing it where /proc allows (Linux >= 4.7)."""
    try:
        for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
            if line.startswith("Umask:"):
                return int(line.split()[1], 8)
    except (OSError, ValueError, IndexError):
        pass
    mask = os.umask(0o022)
    os.umask(mask)
    return mask


def _write_temp(target: Path, text: str) -> str:
    """A unique ``*.tmp`` beside ``target`` (ignored by the store's .gitignore), fsynced, with the
    mode an ordinary create would get — mkstemp's 0600 would lock other users out of the store."""
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=target.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fchmod(f.fileno(), 0o666 & ~_umask())
            os.fsync(f.fileno())
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    return tmp


def _write_json(path: Path, data: dict, *, exclusive: bool = False) -> None:
    _write_text(path, _dump(data), exclusive=exclusive)


def _write_text(path: Path, text: str, *, exclusive: bool = False) -> None:
    """Write through a unique temp file. ``exclusive`` links it into place, so an existing file is
    never replaced (``FileExistsError``); otherwise ``os.replace`` swaps it in atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _write_temp(path, text)
    try:
        if exclusive:
            os.link(tmp, path)
        else:
            os.replace(tmp, path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


def _read_item(repo: Path, item_id: str) -> dict:
    """One item, or a named ``WorkError`` naming the id and the tree it looked in."""
    path = _item_path(repo, item_id)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise WorkError(f"no item {item_id} in {_store_dir(repo)}") from None
    except OSError as exc:
        raise WorkError(f"cannot read item {item_id} ({path}): {exc}") from exc
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise WorkError(f"item {item_id} is corrupt ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise WorkError(f"item {item_id} is corrupt ({path}): not an object")
    if data.get("id") != item_id:
        raise WorkError(
            f"{_rel(repo, path)} holds id {data.get('id')!r}, not {item_id} — "
            "refusing to write through a mismatched item file"
        )
    return data


def _write_item(repo: Path, item: dict, *, create: bool = False) -> Path:
    """Write ``item`` to its file (caller holds the store lock); returns the path."""
    path = _item_path(repo, str(item.get("id", "")))
    _write_json(path, item, exclusive=create)
    return path


def _iter_items(repo: Path) -> Iterator[dict]:
    """Every readable item; a corrupt file is skipped with one stderr line."""
    store = _store_dir(repo)
    if not store.is_dir():
        return
    for path in sorted(store.glob("W-*.json")):
        if not _ID_RE.fullmatch(path.stem):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _warn(f"skipping corrupt item {_rel(repo, path)}: {exc}")
            continue
        if isinstance(data, dict) and data.get("id") == path.stem:
            yield data
        else:
            _warn(f"skipping corrupt item {_rel(repo, path)}: id does not match the file name")


def _read_config(repo: Path) -> dict:
    try:
        data = json.loads(_config_path(repo).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkError(f"cannot read {_config_path(repo)}: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkError(f"{_config_path(repo)} is not a JSON object")
    return data


def _warn(msg: str) -> None:
    sys.stderr.write("work: " + msg + "\n")


# ── the lock ─────────────────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _append_reading(repo: Path, row: dict) -> None:
    """One JSON line under O_APPEND in ``readings.jsonl``; never raises, and writes nothing in a
    repo without a store (the shared dir is never created implicitly)."""
    try:
        if not _has_store(repo):
            return
        path = _shared_dir(repo) / "readings.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        buf = (json.dumps(row, sort_keys=True) + "\n").encode("utf-8")
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            while buf:
                buf = buf[os.write(fd, buf) :]
        finally:
            os.close(fd)
    except Exception as exc:
        _warn(f"reading not recorded — {type(exc).__name__}: {exc}")


@contextlib.contextmanager
def _store_lock(repo: Path, timeout: float, *, fail_open: bool, label: str = "") -> Iterator[bool]:
    """The one exclusive store lock, waited on for at most ``timeout`` seconds.

    Yields True once held. On timeout: ``fail_open`` yields False (the caller skips its write);
    otherwise it raises ``StoreBusyError``. A wait over 0.1 s is recorded in ``readings.jsonl``.
    In a repo without a store it creates nothing: ``fail_open`` yields False silently (such a
    repo is untouched by every hook), otherwise the ``init`` refusal is raised. Re-entrant per
    thread: a nested acquisition by the SAME thread yields True at once and leaves the outer hold
    in place; another thread of the same process goes through the real ``flock`` and waits.
    """
    if not _has_store(repo):
        if fail_open:
            yield False
            return
        _require_store(repo)
    if fcntl is None:  # pragma: no cover
        yield True
        return
    try:
        shared = _shared_dir(repo)
    except WorkError as exc:
        if fail_open:
            _warn(f"store lock unavailable — {exc}")
            yield False
            return
        raise
    key = (str(shared), threading.get_ident())
    with _HELD_GUARD:
        nested = key in _HELD
        if nested:
            _HELD[key] += 1
    if nested:
        try:
            yield True
        finally:
            with _HELD_GUARD:
                _HELD[key] -= 1
        return
    try:
        shared.mkdir(parents=True, exist_ok=True)
        fd = os.open(shared / ".lock", os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as exc:
        if fail_open:
            _warn(f"store lock unavailable — {exc}")
            yield False
            return
        raise WorkError(f"store lock unavailable: {exc}") from exc
    try:
        t0 = time.monotonic()
        acquired = False
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() - t0 >= timeout:
                    break
                time.sleep(0.02)
        waited = time.monotonic() - t0
        if waited > READING_MIN_WAIT_S:
            _append_reading(
                repo,
                {
                    "acquired": acquired,
                    "at": _now_iso(),
                    "kind": "lock-wait",
                    "label": label,
                    "wait_s": round(waited, 3),
                },
            )
        if not acquired:
            if fail_open:
                _warn(f"store lock busy for over {timeout:g} s — this write was skipped")
                yield False
                return
            raise StoreBusyError(
                f"the store lock ({shared / '.lock'}) was held for over {timeout:g} s — "
                "nothing was written; retry"
            )
        with _HELD_GUARD:
            _HELD[key] = 1
        try:
            yield True
        finally:
            with _HELD_GUARD:
                _HELD.pop(key, None)
    finally:
        os.close(fd)


# ── items ────────────────────────────────────────────────────────────────────────────────────


def _mint_id(title: str, creator: str, created: str) -> str:
    nonce = secrets.token_hex(2)
    digest = hashlib.sha256(f"{title}\0{creator}\0{created}\0{nonce}".encode()).hexdigest()
    return "W-" + digest[:8]


def _new_item(
    *, kind: str, title: str, next_action: str, links: dict[str, str], priority: int
) -> dict:
    creator = _agent_name() or _session()
    return {
        "blocked_by": [],
        "created": _now_iso(),
        "creator": creator,
        "evidence": "",
        "id": "",
        "kind": kind,
        "legacy": False,
        "links": {
            **{key: links.get(key, "") for key in LINK_KEYS},
            **{key: links[key] for key in EXTRA_LINK_KEYS if links.get(key)},
        },
        "next": next_action,
        "note": "",
        "owner": "",
        "priority": priority,
        "status": "open",
        "title": title,
    }


def _create_item(repo: Path, item: dict, *, attempts: int = 8) -> Path:
    """Mint an id and exclusive-create the file, retrying with a fresh nonce on a collision."""
    for _ in range(attempts):
        item["id"] = _mint_id(item["title"], item["creator"], item["created"])
        try:
            return _write_item(repo, item, create=True)
        except FileExistsError:
            continue
        except OSError as exc:
            raise WorkError(f"cannot write the new item {item['id']}: {exc}") from exc
    raise WorkError(f"could not mint a free item id after {attempts} attempts")


def _is_ready(
    item: dict, by_id: dict[str, dict], closed: set[str] | frozenset = frozenset()
) -> bool:
    """Open here, not closed in another tree, and every blocker resolved (here or elsewhere)."""
    if item.get("status") != "open" or item["id"] in closed:
        return False
    for dep in item.get("blocked_by") or []:
        blocker = by_id.get(str(dep))
        if str(dep) in closed:
            continue
        if blocker is None or blocker.get("status") not in RESOLVED:
            return False
    return True


def _priority(item: dict) -> int:
    p = item.get("priority", DEFAULT_PRIORITY)
    return p if isinstance(p, int) and not isinstance(p, bool) else DEFAULT_PRIORITY


def _links(item: dict) -> dict:
    """The item's ``links`` for a READ path — a hand-edited non-dict value reads as none, so one
    malformed item never crashes ``status`` or ``sync --check`` for every other item."""
    links = item.get("links")
    return links if isinstance(links, dict) else {}


def _ready_from(
    items: list[dict],
    closed: set[str],
    claims: dict[str, dict],
    *,
    mine: bool = False,
    agent: str = "",
) -> list[dict]:
    by_id = {str(it["id"]): it for it in items}
    ready = [
        it
        for it in items
        if it.get("kind") != "next"  # a session's own NEXT, never distributable work
        and _is_ready(it, by_id, closed)
        and it["id"] not in claims
    ]
    ready.sort(key=lambda it: (_priority(it), str(it.get("created", "")), str(it["id"])))
    if not mine:
        return ready
    owned = [it for it in ready if agent and it.get("owner") == agent]
    free = [it for it in ready if not it.get("owner")]
    return owned + free


def _ready_items(repo: Path, *, mine: bool = False, agent: str = "") -> list[dict]:
    """Open, unblocked items with no live claim and no effective closed marker, never a ``kind:
    next`` item (its session's), by priority then age; ``mine`` puts ``agent``'s own first, then the unassigned ones, and leaves out items owned
    by anyone else. "Claimed" is derived here, never stored on the item."""
    items = list(_iter_items(repo))
    return _ready_from(items, _closed_ids(repo), _live_claims(repo), mine=mine, agent=agent)


# ── the view: obligations read live (spec D1) ───────────────────────────────────────────
#
# Mail and the command-feedback queues stay the truth: they are READ here, never copied into the
# store, and nothing is moved (``mail.py``'s ``list_msgs`` quarantines a malformed file, so it is
# never called — its header parser ``_parse`` is). Both sources are imported by path from beside
# this file, once per process, fail-open: every error drops that one line with one stderr line.
# COBRA (D-253): the cheapest way to empty these lines without answering anything is to ack mail
# unread or mark feedback rows answered with no edit — both leave their own audit trail (the
# ``acked-by:`` disposition, the answered row's commit), which the line does not try to police.

MAIL_ROOT_DEFAULT = "/opt/fabrik-mail"
FEEDBACK_QUEUES_SHOWN = 3
_SIBLING_CACHE: dict[str, Any] = {}


def _sibling(name: str) -> Any:
    """``scripts/<name>.py`` beside this file, imported by path and cached (a failure too — None,
    with one stderr line per process). Registered in ``sys.modules`` under a private name while it
    executes, as ``_import_enforcement`` does, so a module defining a dataclass imports cleanly."""
    if name in _SIBLING_CACHE:
        return _SIBLING_CACHE[name]
    path = Path(__file__).resolve().with_name(f"{name}.py")
    mod_name = f"_work_sibling_{name}"
    result: Any = None
    try:
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"no loader for {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        try:
            with contextlib.redirect_stdout(sys.stderr):
                spec.loader.exec_module(mod)
        except BaseException:
            sys.modules.pop(mod_name, None)
            raise
        result = mod
    except KeyboardInterrupt:
        raise
    except BaseException as exc:
        _warn(f"{name}.py unavailable — {type(exc).__name__}: {exc}")
    _SIBLING_CACHE[name] = result
    return result


def _age_label(seconds: float) -> str:
    seconds = max(seconds, 0.0)
    return f"{int(seconds // 86400)} d" if seconds >= 86400 else f"{int(seconds // 3600)} h"


def _mail_root() -> Path:
    """Exactly ``mail.py``'s expression — a set-but-empty variable is ``Path("")`` (the cwd) in
    both tools, so the two always read the same mailbox."""
    return Path(os.environ.get("FABRIK_MAIL_ROOT", MAIL_ROOT_DEFAULT))


def _mail_line(repo: Path) -> str | None:
    inbox = _mail_root() / _worktrees(repo)[0].name / "inbox"
    if not inbox.is_dir():
        return None
    mail = _sibling("mail")
    if mail is None:
        return None
    count = 0
    oldest: float | None = None
    # os.scandir, not Path.glob: glob swallows an unreadable directory's PermissionError, which
    # would silently read as "no mail"; scandir raises it to obligations' one-line warning
    with os.scandir(inbox) as entries:
        names = sorted(e.name for e in entries)
    for name in names:
        if name.startswith(".") or not name.endswith(".md"):
            continue
        path = inbox / name
        try:
            fm = mail._parse(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if not fm or fm.get("ack") != "required":
            continue
        count += 1
        ts = mail._ts_epoch(fm.get("ts", ""))
        if ts is not None and (oldest is None or ts < oldest):
            oldest = ts
    if not count:
        return None
    age = f" (oldest {_age_label(time.time() - oldest)})" if oldest is not None else ""
    return f"mail: {count} need an answer{age} — python3 scripts/mail.py list"


def _feedback_line(repo: Path) -> str | None:
    if not (repo / "commands" / "_sources").is_dir():
        return None
    report = _sibling("command_feedback_report")
    depths_fn = getattr(report, "queue_depths", None) if report is not None else None
    if depths_fn is None:
        return None
    depths = depths_fn()
    if not isinstance(depths, dict) or not depths:
        return None
    top = sorted(depths.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))[:FEEDBACK_QUEUES_SHOWN]
    shown = " · ".join(f"{cmd} {n}" for cmd, n in top)
    return f"feedback queues: {shown} — /fabrik-command-improve <command>"


def obligations(repo: Path) -> list[str]:
    """At most two lines, read live (spec D1): the ``ack: required`` mail in this repo's inbox
    with the oldest one's age, and — only in the repo holding ``commands/_sources/`` — the three
    deepest command-feedback queues. Read-only, no lock; any error drops that line with one
    stderr line and never raises."""
    lines = []
    for label, fn in (("mail", _mail_line), ("feedback queues", _feedback_line)):
        try:
            line = fn(repo)
        except Exception as exc:
            _warn(f"{label} line skipped — {type(exc).__name__}: {exc}")
            continue
        if line:
            lines.append(line)
    return lines


# ── claims, leases, closed markers ───────────────────────────────────────────────────────────
#
# A claim is ``fabrik-work/claims/<id>.json`` = {agent, session, at, lease_s, token}; it is LIVE
# while ``at + lease_s`` is in the future (read-time expiry: no reaper, no daemon). A release or a
# close sets ``lease_s`` to 0 and keeps the file, so ``token`` only ever grows — the fencing token:
# ``done``/``release`` are refused unless the caller's session holds the live claim, or there is
# none, so a session whose lease lapsed and was taken over cannot overwrite the new holder's work.
# COBRA (D-253): the cheapest way past the fence is to wait out the other lease and claim again —
# which is exactly a takeover, recorded as a higher token; the other cheap path, ``--session
# <someone else's id>``, is impersonation the CLI cannot see and the item's git history shows.
#
# A closed marker is ``fabrik-work/closed/<id>.json``, written by done/drop/answer, so every
# other tree of the repo stops listing an item closed on an unmerged branch. A marker HIDES its
# item until the store's BASE BRANCH (``base_branch`` in config.json, read as a ref) reads it
# done/dropped — then every locked write prunes it, always as that write's last step — or until
# it is 14 days old (a branch never merged). Closing writes the marker FIRST, then the item (a
# failed item write removes the marker again), and ends the claim LAST.


def _claims_dir(repo: Path) -> Path:
    return _shared_dir(repo) / "claims"


def _closed_dir(repo: Path) -> Path:
    return _shared_dir(repo) / "closed"


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_records(folder: Path) -> dict[str, dict]:
    """``<id>.json`` records of a shared folder; never creates it; corrupt files are skipped."""
    out: dict[str, dict] = {}
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("W-*.json")):
        if not _ID_RE.fullmatch(path.stem):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            mtime = path.stat().st_mtime
        except (OSError, ValueError) as exc:
            _warn(f"skipping unreadable {path}: {exc}")
            continue
        if isinstance(data, dict):
            data.setdefault("_mtime", mtime)
            out[path.stem] = data
    return out


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _claim_end(claim: dict) -> float:
    return _num(claim.get("at")) + _num(claim.get("lease_s"))


def _is_live(claim: dict | None, now: float | None = None) -> bool:
    if not claim or not str(claim.get("session") or ""):
        return False
    return _claim_end(claim) > (time.time() if now is None else now)


def _claim_of(repo: Path, item_id: str) -> dict | None:
    return _read_records(_claims_dir(repo)).get(item_id)


def _live_claims(repo: Path) -> dict[str, dict]:
    now = time.time()
    return {i: c for i, c in _read_records(_claims_dir(repo)).items() if _is_live(c, now)}


def _write_claim(repo: Path, item_id: str, claim: dict) -> None:
    claim = {k: v for k, v in claim.items() if not k.startswith("_")}
    _write_json(_claims_dir(repo) / f"{item_id}.json", claim)


def _holder(claim: dict) -> str:
    agent = str(claim.get("agent") or "")
    who = f"session {claim.get('session')}" + (f" (agent {agent})" if agent else "")
    return f"{who}, token {claim.get('token')}, lease until {_iso(_claim_end(claim))}"


def _end_claim(repo: Path, item_id: str) -> None:
    """Close the item's claim (lease 0) and keep its token counter."""
    claim = _claim_of(repo, item_id)
    if claim is not None and _num(claim.get("lease_s")) > 0:
        claim.update(at=time.time(), lease_s=0)
        _write_claim(repo, item_id, claim)


def _renew_claims(repo: Path, session: str) -> None:
    """Push the end of every live claim ``session`` holds (the harvest's heartbeat)."""
    if not session:
        return
    now = time.time()
    for item_id, claim in _live_claims(repo).items():
        if claim.get("session") == session:
            claim["at"] = now
            _write_claim(repo, item_id, claim)


def _branch_of(tree: Path) -> str:
    """The branch checked out in ``tree`` ("" when detached or unreadable)."""
    try:
        return _git(tree, "symbolic-ref", "--short", "-q", "HEAD")
    except WorkError:
        return ""


def _base_branch(repo: Path) -> str:
    """The store's base branch: ``base_branch`` from config.json, as ``init`` recorded it — never
    whatever a checkout has checked out now. "" (no recorded key, a detached main at init, or not
    a usable branch name) means no branch is ever read: markers then expire by age alone."""
    try:
        name = str(_read_config(repo).get("base_branch") or "").strip()
    except WorkError:
        name = ""
    return name if _BRANCH_RE.fullmatch(name) and not name.startswith("-") else ""


def _base_ref_resolves(repo: Path, branch: str) -> bool:
    """Whether ``refs/heads/<branch>`` exists at all (A-O16, T02 review pass 2): a renamed or
    deleted base branch must not be silently treated as "every item unresolved there" — a
    ``cat-file --batch`` request against a missing ref returns rc 0 with every entry reported
    "missing", indistinguishable from a resolving-but-empty result unless checked separately."""
    try:
        _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
        return True
    except WorkError:
        return False


def _base_statuses_raw(repo: Path, branch: str, ids: list[str]) -> dict[str, str] | None:
    """The one ``cat-file --batch`` read behind ``_base_statuses``, returning None (never ``{}``)
    on a genuine git failure — subprocess error, non-zero exit, or a malformed batch response —
    so a caller that must tell "the read failed" apart from "these ids are legitimately absent on
    a resolving ref" can (A-O16, T02 review pass 2; ``_base_statuses`` itself still collapses both
    to ``{}``, preserving its existing callers' contract unchanged)."""
    req = "".join(f"refs/heads/{branch}:{STORE_REL.as_posix()}/{i}.json\n" for i in ids)
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "--batch"],
            input=req.encode(),
            capture_output=True,
            timeout=_git_timeout(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    out, pos, found = proc.stdout, 0, {}
    try:
        for item_id in ids:
            nl = out.index(b"\n", pos)
            head = out[pos:nl].split()
            pos = nl + 1
            if len(head) == 3 and head[1] == b"blob":
                size = int(head[2])
                body = out[pos : pos + size]
                pos += size + 1
                with contextlib.suppress(ValueError):
                    data = json.loads(body.decode("utf-8", "replace"))
                    if isinstance(data, dict):
                        found[item_id] = str(data.get("status") or "")
    except ValueError:
        return None
    return found


def _base_statuses(repo: Path, ids: list[str]) -> dict[str, str]:
    """The status each id's item has on the store's BASE BRANCH, read as a ref (one ``cat-file
    --batch`` call) — never whatever a checkout has checked out. An id missing there is absent
    from the result, and any git failure yields {}: a marker then keeps hiding its item."""
    branch = _base_branch(repo) if ids else ""
    if not branch:
        return {}
    return _base_statuses_raw(repo, branch, ids) or {}


def _is_residue(repo: Path, item_id: str, marker: dict) -> bool:
    """A marker THIS tree wrote over an item this tree still reads open: the writer died between
    the marker write and the item write (``_close`` writes the marker first). It closes nothing."""
    tree = str(marker.get("tree") or "").strip()
    if not tree:  # only a marker that NAMES this tree can be its residue — never Path("") = cwd
        return False
    try:
        if Path(tree).resolve() != repo:
            return False
        own = json.loads(_item_path(repo, item_id).read_text(encoding="utf-8"))
    except (OSError, ValueError, WorkError):
        return False
    return isinstance(own, dict) and own.get("status") not in RESOLVED


def _closed_ids(repo: Path) -> set[str]:
    """Ids hidden by an effective closed marker: one whose item the base branch does not yet read
    done/dropped, that is at most 14 days old, and that is not this tree's own crash residue.
    Nothing else hides an item — every verb acts on the caller's own tree (D-403)."""
    markers = _read_records(_closed_dir(repo))
    heads = _base_statuses(repo, sorted(markers))
    now = time.time()
    closed = set()
    for item_id, marker in markers.items():
        at = _num(marker.get("at"), _num(marker.get("_mtime")))
        if heads.get(item_id) in RESOLVED or now - at > MARKER_MAX_AGE_S:
            continue
        if not _is_residue(repo, item_id, marker):
            closed.add(item_id)
    return closed


def _write_marker(
    repo: Path, item: dict, *, session: str, evidence: str = "", note: str = "", decision: str = ""
) -> None:
    _write_json(
        _closed_dir(repo) / f"{item['id']}.json",
        {
            "agent": _agent_name(),
            "at": time.time(),
            "decision": decision,
            "evidence": evidence,
            "id": item["id"],
            "note": note,
            "session": session,
            "status": item["status"],
            "tree": str(repo),
            **({"resolved_by": item["resolved_by"]} if item.get("resolved_by") else {}),
        },
    )


def _prune_markers(repo: Path) -> None:
    """Delete every marker whose item the store's base branch already reads resolved, and this
    tree's own crash residue (a marker it wrote over an item it still reads open)."""
    markers = _read_records(_closed_dir(repo))
    heads = _base_statuses(repo, sorted(markers))
    for item_id, marker in markers.items():
        if heads.get(item_id) in RESOLVED or _is_residue(repo, item_id, marker):
            with contextlib.suppress(FileNotFoundError):
                (_closed_dir(repo) / f"{item_id}.json").unlink()


def _after_write(repo: Path, *sessions: str) -> None:
    """The tail of every locked write: renew the writers' live claims, then prune markers LAST.
    Never raises — the write it follows already happened."""
    try:
        for session in dict.fromkeys(s for s in sessions if s):
            _renew_claims(repo, session)
        _prune_markers(repo)
    except Exception as exc:
        _warn(f"claim renewal / marker prune skipped — {type(exc).__name__}: {exc}")


def _line(item: dict) -> str:
    owner = item.get("owner") or "-"
    line = f"{item['id']}  P{_priority(item)}  {owner}  {item.get('kind', '')}  {item.get('title', '')}"
    tags = item.get("tags")
    if isinstance(tags, list) and tags:
        line += f"  [tags: {','.join(str(t) for t in tags)}]"
    return line


# ── T02: readers reused by import, with a local fallback ────────────────────────────────────
#
# check_convergence.py, check_plan_tickets.py and check_stage_artifacts.py are fleet-synced
# under the CALLING repo's own `scripts/enforcement/` — imported by file path so this module
# never depends on their package layout. A repo whose enforcement copy predates these readers
# (or has none) falls back to an equivalent local regex, and says so once on stderr: the drift
# report is never silently empty because a sibling script drifted.

_FALLBACK_STATUS_LINE = re.compile(r"^\s*\**Status:\**\s*([A-Za-z][A-Za-z -]*)", re.M)
_FALLBACK_BOARD_SECTION_RE = re.compile(
    r"^##\s+Ticket Board\b(.*?)(?=^##\s|\Z)", re.I | re.M | re.S
)
_FALLBACK_BOARD_ROW_RE = re.compile(r"^\|\s*\**\s*(T\d{2}[a-z]?)\b", re.M)
_FALLBACK_TICKET_ID_RE = re.compile(r"T\d{2}[a-z]?")
_FALLBACK_SPEC_CITE = re.compile(r"docs/superpowers/specs/(?!archived/)[\w./-]+\.md")
_FALLBACK_SPEC_FIELD_LINE = re.compile(
    r"^\s*(?:[-*>]\s+)?\*{0,2}(?:Design spec|Spec)\*{0,2}[^\S\n]*:[^\S\n]*(?P<val>[^\n]*)$",
    re.I | re.M,
)


_ENFORCEMENT_CACHE: dict[tuple[str, str], object | None] = {}
_ENFORCEMENT_WARNED: set[tuple[str, str]] = set()


def _import_enforcement(repo: Path, name: str) -> object | None:
    """``scripts/enforcement/<name>.py`` of ``repo``, imported by path; None (with one stderr
    line, at most once per process) when the file is absent or fails to import — never raises.

    Cached per (repo, name): a repo's copy of a reader doesn't change mid-process, and
    ``_drift_report`` previously re-executed this import for EVERY spec and plan it read (once
    per file, not once per process) — a real cost for a real-sized repo, and a warning printed
    once per file instead of once per process (A-O5, T02 review pass 1).

    The module is registered in ``sys.modules`` under a private name BEFORE ``exec_module``
    (removed again if it raises): a module defining a ``@dataclass`` (``check_plan_tickets.py``)
    looks up ``sys.modules[cls.__module__]`` while processing its class body, and an unregistered
    module makes that lookup return None — an import that would ALWAYS fail, silently turning
    "reuse the real reader" into permanently dead code (A-S1). That private name is keyed by a
    short hash of the RESOLVED repo path as well as ``name`` (A-O19, T02 review pass 2): with only
    ``_work_<name>``, two repos importing the same-named reader share one ``sys.modules`` slot, so
    a FAILING import from repo B pops repo A's already-registered module out from under it, and
    the second repo silently overwrites the first's entry. A module whose import raises
    ``SystemExit`` (not an ``Exception`` subclass) is also caught here and falls back with one
    warning — never ``KeyboardInterrupt``, which still propagates."""
    key = (str(Path(repo).resolve()), name)
    if key in _ENFORCEMENT_CACHE:
        return _ENFORCEMENT_CACHE[key]
    path = repo / "scripts" / "enforcement" / f"{name}.py"
    repo_hash = hashlib.sha256(key[0].encode("utf-8", "replace")).hexdigest()[:8]
    mod_name = f"_work_{name}_{repo_hash}"
    result: object | None = None
    try:
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"no loader for {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            sys.modules.pop(mod_name, None)
            raise
        result = mod
    except (Exception, SystemExit) as exc:
        if key not in _ENFORCEMENT_WARNED:
            _ENFORCEMENT_WARNED.add(key)
            _warn(f"{name} import failed ({exc}) — using the local regex fallback for its grammar")
    _ENFORCEMENT_CACHE[key] = result
    return result


_DOCS_UPDATER_CACHE: Any | None = None


def _docs_updater() -> Any:
    """``scripts/docs_updater.py``, imported by path (T03): ``migrate-backlog`` and ``render``
    reuse its fence-aware backlog-row grammar and its ``AUTO-GENERATED`` block writer
    (``replace_block``) rather than duplicating either. Unlike ``_import_enforcement``'s
    best-effort fallback for an OPTIONAL per-repo reader, this raises loud: ``docs_updater.py``
    ships beside ``work.py`` in every synced repo (both are ``CORE_SCRIPTS``), so a missing or
    broken module here is a broken sync, and every CLI verb fails loud (spec § Lifecycle —
    Degradation is a hook-side rule, not a CLI one). Cached per process — the module never changes
    mid-process."""
    global _DOCS_UPDATER_CACHE
    if _DOCS_UPDATER_CACHE is not None:
        return _DOCS_UPDATER_CACHE
    spec = importlib.util.spec_from_file_location("_work_docs_updater", DOCS_UPDATER_PY)
    if spec is None or spec.loader is None:
        raise WorkError(f"cannot import {DOCS_UPDATER_PY} (needed by migrate-backlog/render)")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        raise WorkError(f"cannot import {DOCS_UPDATER_PY}: {exc}") from exc
    _DOCS_UPDATER_CACHE = mod
    return mod


def _status_line_re(repo: Path) -> re.Pattern:
    mod = _import_enforcement(repo, "check_convergence")
    pattern = getattr(mod, "_STATUS_LINE", None) if mod is not None else None
    return pattern if pattern is not None else _FALLBACK_STATUS_LINE


def _fallback_norm_cell(c: str) -> str:
    return c.strip().strip("`").strip("*").strip()


def _fallback_board_states(spine_text: str) -> dict[str, str]:
    board = _FALLBACK_BOARD_SECTION_RE.search(spine_text)
    if not board:
        return {}
    state_idx = 5
    for line in board.group(1).splitlines():
        if _FALLBACK_BOARD_ROW_RE.match(line):
            break
        if line.strip().startswith("|"):
            cells = [_fallback_norm_cell(c) for c in line.split("|")]
            content = [c for c in cells if c]
            state_cols = [i for i, c in enumerate(cells) if c.lower() == "state"]
            if (
                state_cols
                and len(content) >= 3
                and not any(
                    _FALLBACK_TICKET_ID_RE.search(c.replace("`", "").replace("*", ""))
                    for c in content
                )
            ):
                state_idx = state_cols[0]
    states: dict[str, str] = {}
    for m in _FALLBACK_BOARD_ROW_RE.finditer(board.group(1)):
        cells = [_fallback_norm_cell(c) for c in m.string[m.start() :].split("\n", 1)[0].split("|")]
        states[m.group(1).upper()] = (
            (cells[state_idx] if len(cells) > state_idx else "").replace("️", "").strip()
        )
    return states


def _board_states_fn(repo: Path):
    mod = _import_enforcement(repo, "check_plan_tickets")
    fn = getattr(mod, "_board_states", None) if mod is not None else None
    return fn if fn is not None else _fallback_board_states


def _fallback_designated_spec_citations(text: str) -> list[str]:
    m = _FALLBACK_SPEC_FIELD_LINE.search(text)
    if m:
        return list(dict.fromkeys(_FALLBACK_SPEC_CITE.findall(m.group("val"))))
    lines = text.splitlines()[:40]
    head = "\n".join(ln for ln in lines if not ln.lstrip().startswith("|"))
    return list(dict.fromkeys(_FALLBACK_SPEC_CITE.findall(head)))


def _designated_spec_citations_fn(repo: Path):
    mod = _import_enforcement(repo, "check_stage_artifacts")
    fn = getattr(mod, "_designated_spec_citations", None) if mod is not None else None
    return fn if fn is not None else _fallback_designated_spec_citations


# ── T02: derived spec/plan discovery and drift ───────────────────────────────────────────────


def _iter_specs(repo: Path) -> Iterator[Path]:
    d = repo / SPECS_DIR
    if d.is_dir():
        yield from sorted(d.glob("*.md"))


def _iter_plan_spines(repo: Path, *, archived: bool = False) -> Iterator[Path]:
    """Every plan spine: a standalone dated file, or a same-stem file inside a dated plan-set
    directory (ticket files are excluded by construction — neither matches). ``archived=False``
    reads the live plans; ``archived=True`` reads ``plans/archived/`` instead, the settled plans
    that still CARRY their spec (class 1) and still name their items (class 4)."""
    d = repo / PLANS_DIR / "archived" if archived else repo / PLANS_DIR
    if not d.is_dir():
        return
    for p in sorted(d.glob("*.md")):
        if _PLAN_FILE_NAME_RE.match(p.name):
            yield p
    for sub in sorted(d.iterdir()):
        if sub.is_dir() and _PLAN_DIR_NAME_RE.match(sub.name):
            spine = sub / f"{sub.name}.md"
            if spine.is_file():
                yield spine


# The reused/fallback _STATUS_LINE requires the literal run "Status:" with only leading bold
# markers — it misses a bullet/blockquote-prefixed line and a line where the bold wraps just the
# word ("- Status:", "**Status**:"), both of which check_convergence's OWN ANY_STATUS_LINE
# recognises as present (A-O3/A-O7, T02 review pass 1). This local, richer grammar recovers the
# VALUE for those shapes; it is tried only when the reused/fallback regex does not match.
_STATUS_VALUE_RE = re.compile(
    r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*([A-Za-z][A-Za-z -]*)",
    re.M,
)
# Case-SENSITIVE (A-O15, T02 review pass 2): status tokens are uppercase by the repo's own
# convention, and a case-insensitive match wrongly excludes prose like "CONVERGED (not yet
# implemented)" from class 1 — the word there is lowercase, unlike the real annotation shape
# "CONVERGED, IMPLEMENTED in D-12".
_IMPLEMENTED_OR_SUPERSEDED_RE = re.compile(r"\b(?:IMPLEMENTED|SUPERSEDED)\b")


def _status_line_raw(repo: Path, text: str) -> str:
    """The whole remainder of the matched Status: line — never just the narrow first-word
    capture a value regex's character class allows — so a trailing annotation like ", IMPLEMENTED
    in D-12" is visible to a caller checking for it, even when the primary word is CONVERGED
    (A-O3/A-O7, T02 review pass 1).

    Tries BOTH the reused/fallback regex and the richer local one, and takes the EARLIEST match
    BY POSITION (A-O18, T02 review pass 2): trying the narrow regex first and returning its match
    unconditionally meant a real HEADER only the rich regex can parse (a bullet or bold-word form)
    lost to a LATER body line the narrow regex happens to match, e.g. a `## Notes` section quoting
    `Status: CONVERGED in the spec it implements`."""
    head = text[:4000]
    candidates = [
        m for m in (_status_line_re(repo).search(head), _STATUS_VALUE_RE.search(head)) if m
    ]
    if not candidates:
        return ""
    m = min(candidates, key=lambda match: match.start())
    return head[m.start(1) :].splitlines()[0].strip()


def _status_value(repo: Path, text: str) -> str:
    """The normalised FIRST WORD of the Status: line's value (e.g. ``IN_PROGRESS``,
    ``CONVERGED``, ``WEIRD``). The reused/fallback regex's own capture class excludes digits and
    ``_``, truncating a raw ``IN_PROGRESS``-shaped value at the underscore (`IN`); matching
    against the whole raw line (never the narrow capture) recovers the full token."""
    raw = _status_line_raw(repo, text)
    if not raw:
        return ""
    m = re.match(r"[A-Za-z][A-Za-z0-9_-]*", raw)
    return m.group(0) if m else ""


def _normalize_plan_status(raw: str) -> str:
    up = raw.strip().upper()
    return _PLAN_STATUS_ALIASES.get(up, up)


# A-O13 (T02 review pass 2): "Status" with -i matched ANY prose line mentioning the word (e.g.
# "See the status page for details."), silently resetting class 2's age clock. Anchored to the
# STATUS HEADER LINE shape itself — an optional bullet/quote, optional bold, the literal
# capitalised word, optional bold, then a colon — case-fixed (no -i): a header always spells it
# "Status", never "status"/"STATUS" by the repo's own convention, and prose mentioning the word
# almost never happens to open its own line with this exact shape.
#
# A-O21 (T02 review pass 3): this pattern is a git -G ARGUMENT — POSIX extended regex, where a
# bracket expression has no backslash-escape support at all, so `[ \t]` means "a space, OR a
# literal backslash, OR the letter t" (three characters), never "space or tab". Executed proof: a
# commit adding a TAB-indented "\tStatus: DRAFT" line was NOT found by `[ \t]*`, while a commit
# adding the unrelated prose "t Status: prose" WAS (its leading "t " satisfies the mis-parsed
# class). `[[:blank:]]` is the POSIX bracket-expression class for space-or-tab and needs no
# escape. This is a git-side-only fix: `_QUESTION_RE`/`_GROUND_RE` (Python `re.compile`, where
# `\t` IS a real escape) are untouched.
_PLAN_STATUS_GIT_PATTERN = r"^[[:blank:]]*([-*>][[:blank:]]+)?\*{0,2}Status\*{0,2}[[:blank:]]*:"
_ITEM_STATUS_GIT_PATTERN = '"status":'  # the JSON status field's own line; already case-fixed
_DIR_SCOPE_MIN = 8  # wanted paths under one parent before the batch scopes the directory
_EVIDENCE_REV_RE = re.compile(r"[0-9A-Za-z^{}~@./_:-]+")  # a revision, never a protocol byte
_HEX_SHA_RE = re.compile(r"[0-9a-fA-F]{7,40}")  # a recorded (abbreviated) SHA, never a ref


def _git_status_porcelain(repo: Path, *args: str) -> str:
    """``git status --porcelain`` output, UNSTRIPPED. Found while building A-O17 (T02 review pass
    2): routing this through ``_git()`` — whose ``return proc.stdout.strip()`` strips the WHOLE
    blob, not per line — eats the leading space of a first-line `` M ``-shaped status code
    (unmodified index, modified working tree), shifting the fixed-column parse (`line[3:]`) by one
    character and silently dropping the path's leading directory segment. ``_uncommitted_items``
    carried the identical bug (only ever exercised with a leading ``??`` untracked code, which has
    no leading space to lose) and is fixed the same way."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain", *args],
            capture_output=True,
            text=True,
            timeout=_git_timeout(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def _dirty_paths(repo: Path) -> frozenset[str]:
    """Every repo-relative path whose WORKING TREE differs from HEAD (modified, added, deleted or
    renamed — anything ``git status`` reports), computed with ONE ``git status --porcelain`` call
    and reused by every ``_status_change_age_seconds`` call in the run (A-O17, T02 review pass 2):
    a path here took its most recent write in the WORKING TREE, so a commit-history pickaxe search
    would read a stale, pre-flip status line and report a stale age."""
    out = _git_status_porcelain(repo, "--untracked-files=all")
    paths: set[str] = set()
    for line in out.splitlines():
        if len(line) < 4:
            continue
        rest = line[3:].strip()
        dst = (rest.split(" -> ", 1)[1] if " -> " in rest else rest).strip().strip('"')
        if dst:
            paths.add(dst)
    return frozenset(paths)


def _head_blobs(repo: Path, relpaths: list[str]) -> dict[str, str | None]:
    """The text content of each relpath's blob AT HEAD, decoded, in ONE ``cat-file --batch`` call
    for every path (never one per file) — or None when the path is absent there (untracked or
    newly added). Lets a caller tell a genuine status-line CHANGE apart from an unrelated dirty
    edit (A-O20, T02 review pass 3)."""
    if not relpaths:
        return {}
    req = "".join(f"HEAD:{p}\n" for p in relpaths)
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "--batch"],
            input=req.encode(),
            capture_output=True,
            timeout=_git_timeout(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return dict.fromkeys(relpaths)
    if proc.returncode != 0:
        return dict.fromkeys(relpaths)
    out, pos = proc.stdout, 0
    found: dict[str, str | None] = {}
    try:
        for relpath in relpaths:
            nl = out.index(b"\n", pos)
            head = out[pos:nl].split()
            pos = nl + 1
            if len(head) == 3 and head[1] == b"blob":
                size = int(head[2])
                body = out[pos : pos + size]
                pos += size + 1
                found[relpath] = body.decode("utf-8", "replace")
            else:
                found[relpath] = None
    except ValueError:
        return dict.fromkeys(relpaths)
    return found


_UNPARSEABLE = object()  # a shared sentinel: two unparseable reads compare equal (not "changed")


def _item_status_field(text: str) -> object:
    """The JSON ``"status"`` field's value, or the shared ``_UNPARSEABLE`` sentinel for text that
    doesn't parse as a JSON object — comparison-only (A-O20, T02 review pass 3)."""
    try:
        data = json.loads(text)
    except ValueError:
        return _UNPARSEABLE
    return data.get("status") if isinstance(data, dict) else _UNPARSEABLE


def _status_change_age_seconds(
    repo: Path,
    relpath: str,
    pattern: str,
    dirty: frozenset[str],
    head_blobs: dict[str, str | None],
    status_of: Callable[[str], object],
) -> float:
    """Seconds since the last commit whose diff added or removed a line matching ``pattern``
    in ``relpath`` — the one-path form of ``_status_change_ages``, which owns the rule."""
    return _status_change_ages(repo, [relpath], pattern, dirty, head_blobs, status_of)[relpath]


def _status_change_ages(
    repo: Path,
    relpaths: list[str],
    pattern: str,
    dirty: frozenset[str],
    head_blobs: dict[str, str | None],
    status_of: Callable[[str], object],
) -> dict[str, float]:
    """Seconds since, for each relpath, the last commit whose diff added or removed a line
    matching ``pattern`` (``git log -G``, a regex) in that path at HEAD — never the file's last
    commit for ANY reason, so a typo fix or a note edit does not reset the age clock (A-S2/A-S3,
    T02 review pass 1). A file's creation commit always counts (it "adds" the line), so a path
    with no match has no commit history at all.

    ONE ``git log -G`` read serves every path (W-5937c2cd: one call per done item cost the hub's
    ``status`` ~5 s). Pickaxe without ``--pickaxe-all`` names only the files whose OWN diff
    matched, so the newest commit naming a path is exactly what the per-path ``log -1 -G`` read.
    COBRA (D-253): the cheap way to pass the call-count grader is to drop paths from the batch;
    the per-path age tests (class 2 and class 6) are the counter.

    A path in ``dirty`` (working copy differs from HEAD, A-O17) uses its own mtime ONLY when its
    STATUS reading (``status_of`` — the same concept the pickaxe pattern targets: the plan
    header's primary word, or the item's ``"status"`` field) genuinely DIFFERS between the
    working copy and HEAD, or when the path is absent from HEAD entirely (untracked or new) —
    never for JUST ANY uncommitted change (A-O20, T02 review pass 3): a notes-only edit to an old
    done item, or a body typo in an old CONVERGED plan, must still take the normal commit-history
    age, not read as freshly changed. A failed log read degrades every path to its mtime, as the
    per-path read did on a git error."""
    now = time.time()
    use_mtime: set[str] = set()
    for relpath in relpaths:
        if relpath not in dirty:
            continue
        head_text = head_blobs.get(relpath)
        if head_text is None:
            use_mtime.add(relpath)
            continue
        try:
            working_text = (repo / relpath).read_text(encoding="utf-8", errors="replace")
        except OSError:
            working_text = ""
        if status_of(working_text) != status_of(head_text):
            use_mtime.add(relpath)
    wanted = [p for p in relpaths if p not in use_mtime]
    # pathspec: a parent directory holding at least _DIR_SCOPE_MIN wanted paths is scoped as the
    # directory, filtered back to ``wanted`` below — git matches one directory far faster than
    # hundreds of file pathspecs (0.26 s vs 1.39 s over the hub's 360-item store, 2026-10-04);
    # every other path is its own pathspec, so a lone plan never walks its whole plans directory
    # (1.27 s over 405 files). A multi-path scope does not simplify history per file: a merge
    # that kept one side's status line can surface the other side's newer change, so an age may
    # read YOUNGER than the per-file read — class 6 then checks evidence it would have skipped
    # (stricter, never laxer). ``core.quotePath=false`` keeps non-ASCII names literal; a name
    # git still quotes (a quote or control character) misses the filter and takes its mtime.
    by_parent: dict[str, list[str]] = {}
    for p in wanted:
        by_parent.setdefault(str(PurePosixPath(p).parent) if "/" in p else "", []).append(p)
    scopes = sorted(
        scope
        for parent, paths in by_parent.items()
        for scope in ([parent] if parent and len(paths) >= _DIR_SCOPE_MIN else paths)
    )
    last: dict[str, float] = {}
    if wanted:
        try:
            out = _git(
                repo,
                "-c",
                "core.quotePath=false",
                "log",
                "--format=%x00%ct",
                "--name-only",
                "--no-renames",
                "-G",
                pattern,
                "HEAD",
                "--",
                *scopes,
            )
        except WorkError:
            out = ""
        wanted_set = set(wanted)
        stamp: float | None = None
        for line in out.splitlines():
            if line.startswith("\x00"):
                try:
                    stamp = float(line[1:])
                except ValueError:
                    stamp = None
            elif line and stamp is not None and line in wanted_set and line not in last:
                last[line] = stamp
    ages: dict[str, float] = {}
    for relpath in relpaths:
        if relpath in last:
            ages[relpath] = max(0.0, now - last[relpath])
            continue
        try:
            mtime = (repo / relpath).stat().st_mtime
        except OSError:
            ages[relpath] = 0.0
            continue
        ages[relpath] = max(0.0, now - mtime)
    return ages


def _normalize_repo_path(repo: Path, raw: str) -> str:
    """Strip a leading ``./`` and any trailing ``/`` (A-O14, T02 review pass 2: a trailing slash
    survived into the directory-expansion join and produced ``dir//dir.md``), and rewrite an
    absolute path under ``repo`` to repo-relative posix (a path outside the repo, or one git
    cannot resolve, is returned as-is — it simply matches nothing downstream). Shared by plan
    references and a plan's spec citation (A-O1/A-O2, T02 review pass 1): both may be written
    ``./docs/...``, as an absolute path, or with a trailing ``/``."""
    value = (raw or "").strip()
    if not value:
        return ""
    p = Path(value)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(repo.resolve()).as_posix()
        except (OSError, ValueError):
            return value
    if value.startswith("./"):
        value = value[2:]
    return value.rstrip("/")


def _normalize_plan_ref(repo: Path, raw: str) -> str:
    """A plan lock's ``plan`` field or an item's ``links.plan``, normalised to the repo-relative
    SPINE path: after ``_normalize_repo_path``, a reference naming the plan-set DIRECTORY (no
    ``.md``, and genuinely a directory on disk) expands to its same-stem spine — the same shape
    ``_iter_plan_spines`` discovers (A-O1/A-O2, T02 review pass 1)."""
    rel = _normalize_repo_path(repo, raw)
    # A link written before its plan was archived still names the live path; when that path is
    # gone and the archived copy exists, the link means the archived plan (class 4, D-412).
    live = PLANS_DIR.as_posix() + "/"
    if (
        rel.startswith(live)
        and not rel.startswith(live + "archived/")
        and not (repo / rel).exists()
    ):
        moved = f"{live}archived/{rel[len(live) :]}"
        if (repo / moved).exists():
            rel = moved
    if not rel or rel.endswith(".md"):
        return rel
    if (repo / rel).is_dir():
        return f"{rel}/{Path(rel).name}.md"
    return rel


def _active_plan_locks(repo: Path) -> dict[str, dict]:
    """plan relpath (normalised) -> lock record, for every ``.fabrik/plan-locks/*.json`` whose
    status is literally ``active`` (``released``/``executed``/``complete`` do not count)."""
    locks_dir = repo / ".fabrik" / "plan-locks"
    out: dict[str, dict] = {}
    if not locks_dir.is_dir():
        return out
    for p in sorted(locks_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and str(data.get("status") or "") == "active":
            plan = _normalize_plan_ref(repo, str(data.get("plan") or ""))
            if plan:
                out[plan] = data
    return out


def _backlog_needs_render(repo: Path, items: list[dict]) -> bool:
    """True when the open ``kind: backlog`` item ids differ from the ids the rendered
    ``AUTO-GENERATED:BACKLOG`` block currently lists in each line's TRAILING backtick-parens
    position — the cheapest honest proxy for "render would change it" without duplicating
    ``render`` itself (T03; T03 review pass 1 Decision B.6/A-O13, A-S2). A MISSING block while
    open backlog items exist is drift too — the un-rendered state is exactly the one class 7
    exists to name; a malformed block (ambiguous START/END) reads as drift the same way rather
    than raising here, since ``status``/``sync`` are read-only reporting paths."""
    path = repo / _BACKLOG_REL
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    open_ids = {
        str(it["id"])
        for it in items
        if it.get("kind") == "backlog" and it.get("status") not in RESOLVED
    }
    try:
        found = _find_backlog_block(text)
    except WorkError:
        return bool(open_ids)
    if found is None:
        return bool(open_ids)
    _, s_end, e_begin, _ = found
    inner = text[s_end:e_begin]
    block_ids = set(_BACKLOG_TRAILING_ID_RE.findall(inner))
    return open_ids != block_ids


def _stale_marker_statuses(repo: Path, ids: list[str]) -> dict[str, str]:
    """Each stale marker's item status, read from the store's RECORDED base branch when one is
    configured AND resolves (a missing id there reads as "", i.e. not resolved — the same
    convention ``_closed_ids`` uses); with none recorded, OR the recorded ref no longer resolves
    (renamed/deleted), OR the batch read itself fails, from the CURRENT TREE — exactly as when no
    base is recorded, and never flagging purely because a read failed (A-O9, T02 review pass 1;
    A-O16, T02 review pass 2). "still open in the main checkout" means the canonical base branch
    when one genuinely exists, not a stale pointer to a branch nobody kept."""
    if not ids:
        return {}
    base_branch = _base_branch(repo)
    if base_branch and _base_ref_resolves(repo, base_branch):
        heads = _base_statuses_raw(repo, base_branch, ids)
        if heads is not None:
            return {i: heads.get(i, "") for i in ids}
    out: dict[str, str] = {}
    for i in ids:
        try:
            out[i] = str(_read_item(repo, i).get("status") or "")
        except WorkError:
            out[i] = ""
    return out


def _drift_report(repo: Path) -> dict[int, list[str]]:
    """The eight drift classes of spec § Spec and plan state is derived, never copied, each a
    sorted list of the relpaths (item files for 5-6, the backlog doc for 7) that trip it."""
    report: dict[int, list[str]] = {n: [] for n in range(1, 9)}
    dirty = _dirty_paths(repo)  # ONE git status call per run (A-O17), reused below
    head_blobs = _head_blobs(repo, sorted(dirty))  # ONE cat-file batch per run (A-O20)
    items = list(_iter_items(repo))
    linked_specs = {_normalize_repo_path(repo, _links(it).get("spec") or "") for it in items}
    linked_specs.discard("")
    linked_plans: dict[str, list[dict]] = {}
    for it in items:
        plan = _normalize_plan_ref(repo, _links(it).get("plan") or "")
        if plan:
            linked_plans.setdefault(plan, []).append(it)

    cite_fn = _designated_spec_citations_fn(repo)
    cited_specs: set[str] = set()
    plan_texts: dict[str, str] = {}
    for spine in _iter_plan_spines(repo):
        rel = _rel(repo, spine)
        try:
            text = spine.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        plan_texts[rel] = text
        cited_specs.update(_normalize_repo_path(repo, c) for c in cite_fn(text))
    # An ARCHIVED plan is settled: it is never a subject of classes 2, 3 or 8, but it still names
    # its spec (class 1 — "no plan names it") and it is EXECUTED, so an item still open against it
    # is class 4. Reading only the live plans reported every spec whose plan had been archived as
    # carried by nothing (24 of the hub's 28 class-1 lines at adoption, 2026-09-25).
    archived_texts: dict[str, str] = {}
    for spine in _iter_plan_spines(repo, archived=True):
        try:
            text = spine.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        archived_texts[_rel(repo, spine)] = text
        cited_specs.update(_normalize_repo_path(repo, c) for c in cite_fn(text))

    for spec_path in _iter_specs(repo):
        rel = _rel(repo, spec_path)
        try:
            text = spec_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _status_value(repo, text).strip().upper() != "CONVERGED":
            continue
        if _IMPLEMENTED_OR_SUPERSEDED_RE.search(_status_line_raw(repo, text)):
            continue  # e.g. "CONVERGED, IMPLEMENTED in D-12" — already carried forward
        if rel not in cited_specs and rel not in linked_specs:
            report[1].append(rel)

    active_locks = _active_plan_locks(repo)
    for rel, text in plan_texts.items():
        norm = _normalize_plan_status(_status_value(repo, text))
        if norm not in _PLAN_STATUSES:
            report[8].append(rel)
        has_lock = rel in active_locks
        if norm == "CONVERGED":
            if (
                not has_lock
                and rel not in linked_plans
                and _status_change_age_seconds(
                    repo,
                    rel,
                    _PLAN_STATUS_GIT_PATTERN,
                    dirty,
                    head_blobs,
                    lambda t: _status_value(repo, t),
                )
                > STALE_PLAN_DAYS * 86400
            ):
                report[2].append(rel)
        elif norm == "IN-PROGRESS":
            if not has_lock:
                report[3].append(rel)
        elif norm == "EXECUTED":
            if any(li.get("status") not in RESOLVED for li in linked_plans.get(rel, [])):
                report[4].append(rel)
    for rel, text in archived_texts.items():
        if _normalize_plan_status(_status_value(repo, text)) == "EXECUTED" and any(
            li.get("status") not in RESOLVED for li in linked_plans.get(rel, [])
        ):
            report[4].append(rel)

    store = _store_dir(repo)
    done_candidates: list[tuple[str, str, str]] = []
    if store.is_dir():
        for path in sorted(store.glob("W-*.json")):
            if not _ID_RE.fullmatch(path.stem):
                continue
            rel = _rel(repo, path)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                report[5].append(rel)
                continue
            if not isinstance(data, dict) or data.get("id") != path.stem:
                report[5].append(rel)
                continue
            if data.get("status") not in STATUSES:
                report[5].append(rel)
                continue
            # `answer` closes an awaiting-operator decision with the operator's words in `note` and
            # no commit, so an answered decision carries no evidence by design. COBRA (D-253): a
            # hand-written note on a decision dodges this predicate; that edit is in the item's git
            # history, and a decision done with neither note nor evidence still reads class 6.
            note = data.get("note")
            answered = (
                data.get("kind") == "decision" and isinstance(note, str) and bool(note.strip())
            )
            if (
                data.get("status") == "done"
                and not data.get("legacy")
                and data.get("kind") not in LINKED_KINDS
                and not answered
            ):
                # W-f154f3f3: an item closed `--resolved-by` carries its root item's fix, whose
                # commit names that root. Cobra: a hand-written `resolved_by` dodges class 6
                # exactly as a hand-written `note` does above; the edit is in the item's history.
                cited = str(data.get("resolved_by") or path.stem)
                done_candidates.append((rel, cited, str(data.get("evidence") or "")))
        # W-5937c2cd: one batched age read and one batched evidence read, never per item
        ages = _status_change_ages(
            repo,
            [rel for rel, _, _ in done_candidates],
            _ITEM_STATUS_GIT_PATTERN,
            dirty,
            head_blobs,
            _item_status_field,
        )
        recent = [c for c in done_candidates if ages[c[0]] <= RECENT_WINDOW_S]
        resolved = _evidence_commits(repo, [(item_id, ev) for _, item_id, ev in recent])
        for rel, item_id, ev in recent:
            if resolved[(item_id, ev)] is None:
                report[6].append(rel)

    now = time.time()
    markers = _read_records(_closed_dir(repo))
    stale_ids = [
        item_id
        for item_id, marker in markers.items()
        if now - _num(marker.get("at"), _num(marker.get("_mtime"))) > MARKER_MAX_AGE_S
    ]
    stale_statuses = _stale_marker_statuses(repo, stale_ids)
    for item_id in stale_ids:
        if stale_statuses.get(item_id, "") not in RESOLVED:
            report[6].append(_rel(repo, _item_path(repo, item_id)))

    if _backlog_needs_render(repo, items):
        report[7].append(_BACKLOG_REL)

    return {n: sorted(set(paths)) for n, paths in report.items()}


def _sync_readings(repo: Path) -> list[dict]:
    try:
        lines = (_shared_dir(repo) / "readings.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("kind") == "sync":
            out.append(row)
    return out


def _parse_iso(raw: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _reading_clean(row: dict) -> bool:
    """False (never clean) for a malformed reading — e.g. a ``counts`` that isn't a dict at all
    — rather than raising: a corrupt row must never look clean, and it must never crash
    ``sync --check`` either (A-O4, T02 review pass 1). ``_num`` already tolerates a non-numeric
    individual value; the only crash risk was ``counts`` lacking ``.get`` entirely."""
    counts = row.get("counts")
    if not isinstance(counts, dict):
        return False
    return all(_num(counts.get(str(n)), 0) == 0 for n in range(2, 7))


def _sync_blocking_active(repo: Path) -> bool:
    """Re-derived from the readings on every call, never a stored flag: True once
    ``readings.jsonl`` shows ``SYNC_BLOCKING_DAYS`` consecutive CLEAN calendar days (every
    reading that day clean for classes 2-6) strictly after ``config.json``'s ``migrated_at``."""
    try:
        migrated_raw = str(_read_config(repo).get("migrated_at") or "").strip()
    except WorkError:
        return False
    migrated_dt = _parse_iso(migrated_raw) if migrated_raw else None
    if migrated_dt is None:
        return False
    by_day: dict[date, list[dict]] = {}
    for row in _sync_readings(repo):
        at_dt = _parse_iso(str(row.get("at") or ""))
        if at_dt is None or at_dt <= migrated_dt:
            continue
        by_day.setdefault(at_dt.date(), []).append(row)
    clean_days = {day for day, rows in by_day.items() if rows and all(map(_reading_clean, rows))}
    for day in sorted(clean_days):
        if all((day + timedelta(days=i)) in clean_days for i in range(SYNC_BLOCKING_DAYS)):
            return True
    return False


def _uncommitted_items(repo: Path) -> list[str]:
    """Item files ``git status --porcelain`` shows untracked or modified — a listing, never a
    drift class (spec § Constraints — shared tree). Fails OPEN to ``[]`` on a git error."""
    store_rel = STORE_REL.as_posix()
    return _parse_store_status(
        _git_status_porcelain(repo, "--untracked-files=all", "--", store_rel)
    )


def _uncommitted_items_strict(repo: Path) -> list[str] | None:
    """`_uncommitted_items`, but ``None`` when git fails — for a caller that must tell "nothing is
    uncommitted" from "could not look" (an empty answer there would read as an all-clear)."""
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--",
                STORE_REL.as_posix(),
            ],
            capture_output=True,
            text=True,
            timeout=_git_timeout(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return _parse_store_status(proc.stdout) if proc.returncode == 0 else None


def _parse_store_status(out: str) -> list[str]:
    """The item-file paths in UNSTRIPPED ``git status --porcelain`` output."""
    store_rel = STORE_REL.as_posix()
    paths: set[str] = set()
    for line in out.splitlines():
        if len(line) < 4:
            continue
        rest = line[3:].strip()
        dst = (rest.split(" -> ", 1)[1] if " -> " in rest else rest).strip().strip('"')
        if dst.startswith(store_rel + "/") and _ID_RE.fullmatch(Path(dst).stem):
            paths.add(dst)
    return sorted(paths)


# ── verbs ────────────────────────────────────────────────────────────────────────────────────


def _merge_owner(repo: Path) -> str:
    """The hub's declared merge owner for ``repo``, or "" on UNDECLARED/anything but a name."""
    if not DECISIONS_PY.is_file():
        return ""
    try:
        proc = subprocess.run(
            [sys.executable, str(DECISIONS_PY), "--merge-owner", str(repo)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    name = proc.stdout.strip()
    if proc.returncode != 0 or not name:
        return ""
    if not _valid_name(name):
        _warn(
            f"merge owner {name!r} from {DECISIONS_PY} is not an agent name ({NAME_RULE}) — "
            "distributor left empty"
        )
        return ""
    return name


# ── T03: migrate-backlog, render (spec § The backlog becomes a view; T03 review pass 1) ─────────
#
# Decision R (review pass 1, D-row minted at merge): the ticket's literal body rule ("a body runs
# to the next line starting `##`, `### `, `- ` or `|`") contradicted the ticket's own shape counts
# (~287-293) and the spec's V2 (253 open, 36 resolved) — V2 measures rows as TAGGED ENTRIES, and
# the literal rule inflated the hub count to 601 (pass-1.json A-S1/A-O1). Resolution: a ROW starts
# ONLY at a column-0 line of one of six shapes — a `## ` heading (any); a `### ` heading that
# carries a tag or a resolved marker; a bullet whose content begins with a bracket tag (bold or
# not); a checkbox bullet `- [ ]`/`- [x]` (`* ` counts identically — A-O10); a bullet whose content
# begins with `~~`; a table row under a header carrying a Tag/Owner cell. EVERYTHING ELSE —
# untagged column-0 bullets, untagged `### ` narrative sub-headers, indented continuation, prose,
# fenced blocks — is BODY of the row above, kept in its text; a body runs to the next ROW line,
# never to the next `- `. A row-start line that fails to parse (an untagged `## `) still becomes an
# item with an empty owner (contract row 2); non-row text before the first row, or belonging to no
# row, is never an item. D-566 narrows the `## ` case: a row whose body is empty or template
# boilerplate is dropped by `_is_structural_row` when it is an untagged, unresolved `## ` section or a
# template placeholder row — a row with any real body line is never dropped.
#
# `docs_updater.classify_backlog_row` decides whether an UNTAGGED row NEEDS a tag (`--adopt`'s own
# job): its "skip" verdict fires equally on an already-tagged, resolved, or non-row line — the
# inverse of what migration needs — so this scanner classifies independently. It still reuses
# docs_updater's lower-level grammar (`_BACKLOG_BULLET_RE`, the table-header/separator/legend
# helpers, `_BACKLOG_TAG_AT_POS_RE`); `docs_updater.replace_block` is NOT reused by `render` (see
# Decision B below — its always-stamp, first-match semantics don't fit the no-timestamp,
# ambiguity-refusing contract review pass 1 requires).

_HEADING2_RE = re.compile(r"^## (.*)$")
_HEADING3_RE = re.compile(r"^### (.*)$")
_FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})")
_RESOLVED_STATUS_WORDS = ("RESOLVED", "CLOSED", "DONE", "LANDED", "MOOT", "DRILLED", "SHIPPED")
# A-O17: \b word boundaries so RESOLVED never matches inside UNRESOLVED, DONE inside UNDONE, etc.
# A-S3: ✅ joins the SAME status-position scan as the uppercase words, rather than an unconditional
# "appears anywhere" test — a title merely discussing "the ✅ row" stays open.
_STATUS_OR_CHECK_RE = re.compile(r"✅|\b(?:" + "|".join(_RESOLVED_STATUS_WORDS) + r")\b")
_STATUS_AFTER_RE = re.compile(r"^[ \t:,\-—]{0,4}(?:\d{4}-\d{2}-\d{2}|in D-\d+)")
_STATUS_BEFORE_DASH_RE = re.compile(r"—[ \t]*$")
# D-566: an uppercase status word that opens an untagged title is a status only when a separator
# follows it — `CLOSED — x`, `RESOLVED (D-044) — x`, `DONE:` — never `CLOSED-door policy`, `MOOT court`.
_FIRST_WORD_SEPARATOR_RE = re.compile(r"^[ \t*_~]*(?:—|:|\(|,|\d{4}-\d{2}-\d{2}|$)")
# A-O19/A-O27: a status word this close behind PARTIALLY/PARTLY/NOT never resolves the row on its
# own — hyphen- and whitespace-tolerant ("PARTIALLY-CLOSED", "NOT DONE").
_NEGATION_PREFIX_RE = re.compile(r"\b(?:PARTIALLY|PARTLY|NOT)[ \t-]*$", re.I)
# A-O19/A-O26/A-O27: "stays/still/remains open" (hyphen- or whitespace-joined, "still-open") cancels
# a status-position hit that it FOLLOWS — checked per-marker, in the text AFTER that marker, never
# as a blanket whole-title pre-check (A-O26): a PAST-TENSE mention ("was/were still open") of a
# historical state never cancels a dated resolution that precedes it.
_STAYS_OPEN_RE = re.compile(r"\b(?:stays|still|remains)[ \t-]+open\b", re.I)
_PAST_TENSE_BEFORE_RE = re.compile(r"\b(?:was|were)[ \t]*$", re.I)
# A-O25: a match sitting as the first TOKEN of a TABLE CELL (right after a `|`, through up to 4
# chars of bold/strike/backtick decoration) is a status position too — checked only when the row
# IS a table (`is_table=True`), never for a heading/bullet that happens to contain a literal `|`.
_STATUS_AFTER_PIPE_RE = re.compile(r"\|[ \t]*(?:[*_~`]{0,4})$")
_MIGRATED_DIGEST_RE = re.compile(r"migrated-digest:([0-9a-f]{12})")
_ROW_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_BRACKET_RE = re.compile(r"\[([^\]\n]{1,80})\]")
# A-O21/A-O22: work.py's OWN fallback for a cross-tag with spaces around its separator
# (docs_updater's `_BACKLOG_TAG_AT_POS_RE` — never edited here — requires the separator flush
# against the head). Carries the SAME two guards as that regex, restated for a spaced head: never
# a bare checkbox mark (`[x + y]`) and never a bare date (`[2026-09-20 → 2026-09-22]`) — without
# them the head group's `[a-z0-9-]` happily swallows a lone "x" or a full YYYY-MM-DD as the "owner".
_CROSS_TAG_SPACED_RE = re.compile(
    r"^(?!x[ \t]*[/+→])(?!\d{4}-\d{2}-\d{2}[ \t]*[/+→])"
    r"[a-z0-9-]{1,32}[ \t]*[/+→][ \t]*[^\]\n]{0,60}$"
)
_LEGEND_HEADER = ("Tag", "Agent", "Beat")
# W-02a0f674: the scaffold template's own body lines (templates/scaffold/docs/STRATEGIC_BACKLOG_TEMPLATE.md),
# stripped. A row whose body holds nothing but these, blanks, `---`, comments and table separators carries
# no content — migrating it made "Later", "Activation" and two `[Item]` placeholders OPEN items in every
# scaffolded store. `tests/test_work_migrate.py` pins this set to the template, so a template edit fails
# the suite instead of migrating silently into every new project.
_TEMPLATE_PLACEHOLDER_LINES = frozenset(
    {
        "| Effort | Item | Why Priority | Ready When |",
        "| **M** | [Feature/Refactor] | [1-liner value] | [Specific trigger] |",
        "| **S** | [Small hardening/refactor] | [1-liner value] | [Specific trigger] |",
        "- [ ] **[Item]**: [Brief description]. Blocked by [resource/trigger].",
        "- ⚠️ **[System X]**: Avoid [Library A]; use [Library B]. Prior attempt failed due to [Z].",
        "- 💡 **[Pattern Insight]**: [Lesson to preserve regarding architecture or logic.]",
        "Items move to active development when:",
        "1. **Focus window opens** — a block of 4+ hours of uninterrupted time is identified.",
        "2. **Resource/budget availability** — external tools, APIs, or budget tiers become accessible.",
        '3. **Measurable failure** — a "functional but fragile" component produces a real incident',
        "(link the TROUBLESHOOTING.md entry); prevention is promoted to a plan at the second occurrence.",
    }
)
_LIST_MARKER_RE = re.compile(r"^(?:[-*][ \t]+(?:\[[ xX]\][ \t]+)?)")


def _sans_list_marker(line: str) -> str:
    """A line with its leading bullet/checkbox marker removed — a bullet row's ``title_line`` holds
    only its content, the template holds the whole line; both are compared through this."""
    return _LIST_MARKER_RE.sub("", line.strip())


_TEMPLATE_PLACEHOLDER_CONTENT = frozenset(_sans_list_marker(x) for x in _TEMPLATE_PLACEHOLDER_LINES)
_TABLE_SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|$")
_RULE_LINE_RE = re.compile(r"^-{3,}$")


def _looks_bracket_led(content: str) -> bool:
    """True when ``content`` begins with a bracket — ANY bracket, tag-valid or not — after
    stripping up to three layers of leading decoration (``~~``, ``**``, one backtick). This is the
    ROW-START trigger (Decision R.1's "content begins with a bracket tag (bold or not)"),
    deliberately looser than tag VALIDATION: a malformed leading bracket (``[RESOLVED …]``) still
    starts a row — finding the real tag past it is `_find_first_tag`'s job (A-O11)."""
    s = content.lstrip()
    for _ in range(3):
        if s[:2] in ("~~", "**"):
            s = s[2:]
        elif s[:1] == "`":
            s = s[1:]
        else:
            break
    return s.startswith("[")


def _find_first_tag(text: str, du: Any) -> tuple[str, str, tuple[int, int]] | None:
    """The FIRST canonical bracket tag anywhere in ``text`` (Decision R.6, A-O11 — not only at
    position 0: a leading ``[RESOLVED …]`` bracket is skipped in favor of a real ``[infra]`` one
    bracket over). Returns ``(owner, "[<raw>]", (start, end))`` — the span covers the whole
    ``[...]`` including brackets, for the render title-strip (A-O12) and the resolved "first word
    after tag" check (Decision M); ``None`` when no bracket in ``text`` validates as a tag."""
    for m in _BRACKET_RE.finditer(text):
        inner = m.group(1)
        if du._BACKLOG_TAG_AT_POS_RE.match(f"[{inner}]") or _CROSS_TAG_SPACED_RE.match(inner):
            owner = re.split(r"[/+→]", inner, maxsplit=1)[0].strip().lower()
            return owner, f"[{inner}]", m.span()
    return None


def _row_is_resolved(
    title_line: str,
    *,
    checkbox: str = "",
    strike_content: str = "",
    tag_span: tuple[int, int] | None = None,
    is_table: bool = False,
) -> bool:
    """Decision M (A-O7, A-S3, A-O17, A-O19, A-O25, A-O26, A-O27): a row is resolved when the
    checkbox is ``[x]``, or ``strike_content`` (the row's own content after its marker) begins with
    a strike. Otherwise ``✅`` and an uppercase WHOLE word (``\\b``-bounded, A-O17) from
    RESOLVED/CLOSED/DONE/LANDED/MOOT/DRILLED/SHIPPED are scanned together for a STATUS POSITION —
    followed (after optional spaces/punctuation) by a date or ``in D-<n>``, sitting AFTER the tag
    span as its first word (never before it — A-O17), as the FIRST word of an untagged title on a row
    with no checkbox (D-566), following an em dash, or — for a TABLE row
    only (``is_table=True``, A-O25) — sitting as the first token of ANY cell (right after a ``|``).
    A bare mid-sentence occurrence ("a CLOSED review's edits", "file 5, DONE", "the ✅ row") is NOT
    resolved. Two negations, each checked PER MARKER rather than once for the whole title: a word
    directly preceded by PARTIALLY/PARTLY/NOT, hyphen-tolerant (A-O27); or a "stays/still/remains
    open" phrase (hyphen-tolerant) that FOLLOWS this marker (never one merely somewhere in the
    title, and never a PAST-TENSE mention — "was/were still open" — of a historical state, which
    must not cancel a dated resolution that precedes it — A-O26). A checkbox or a genuine leading
    strike are unambiguous enough to skip both negations."""
    if checkbox.lower() == "x":
        return True
    if strike_content.lstrip().startswith("~~"):
        return True
    for m in _STATUS_OR_CHECK_RE.finditer(title_line):
        ws, we = m.span()
        if _NEGATION_PREFIX_RE.search(title_line[:ws]):
            continue
        first_word_after_tag = (
            tag_span is not None
            and ws >= tag_span[1]
            and bool(re.fullmatch(r"[\s*_~]*", title_line[tag_span[1] : ws]))
        )
        # W-02a0f674: an UNTAGGED title's first word is a status position too (`✅ CLOSED — …`),
        # but never on an unchecked checkbox, whose open box outranks the marker.
        first_word_untagged = (
            tag_span is None
            and not checkbox
            and bool(re.fullmatch(r"[\s*_~]*", title_line[:ws]))
            and (m.group(0) == "✅" or bool(_FIRST_WORD_SEPARATOR_RE.match(title_line[we:])))
        )
        resolves = (
            bool(_STATUS_AFTER_RE.match(title_line[we:]))
            or (is_table and bool(_STATUS_AFTER_PIPE_RE.search(title_line[:ws])))
            or first_word_after_tag
            or first_word_untagged
            or bool(_STATUS_BEFORE_DASH_RE.search(title_line[:ws]))
        )
        if not resolves:
            continue
        after_text = title_line[we:]
        stay_m = _STAYS_OPEN_RE.search(after_text)
        if stay_m and not _PAST_TENSE_BEFORE_RE.search(after_text[: stay_m.start()]):
            continue  # A-O26: negated by a FOLLOWING, non-past-tense stays-open phrase
        return True
    return False


def _title_without_tag(text: str, tag_span: tuple[int, int] | None) -> str:
    """Drop the tag bracket ``render`` re-prefixes as ``**[owner]**`` — every other markdown
    character (``_``/``*``/backticks) stays intact; the store is never the field that mangles a
    real identifier like ``the_thing_x`` (A-O12). A-O16: when the tag sits inside its OWN isolated
    ``**[tag]**`` bold pair (as opposed to one bold span wrapping both the tag and the title), that
    wrapper is removed WITH the tag — otherwise a bare bracket removal leaves an empty ``****`` on
    124 of 325 real hub titles.

    A-O23: every cleanup below touches ONLY the two ends of the SPLICE POINT (``before``/``after``
    around the removed span) — never the whole string via a global regex, which would corrupt an
    unrelated code span or prose elsewhere in the title (`x****y` -> `xy`, a genuine ``****b****``
    emphasis run untouched: the plain-prose case, where ``before`` ends in ordinary text rather
    than a bold-open, triggers NEITHER rule below). When the tag's OWN bold-open survives right
    before the splice (``before`` ends with ``**`` — the merged ``**[tag] Title**`` span; an empty
    ``before`` needs no rule at all, the function's own final ``.strip()`` already squeezes a
    leading gap left by nothing preceding it): (a) ``after`` begins with an optional space then
    ANOTHER ``**`` — an accidental empty/re-opened bold pair straddling the boundary — drop that
    redundant ``**`` (and the space), keeping the ONE already in ``before``; otherwise (b) squeeze
    just the stray leading space ``**[tag] Title**`` left in ``after`` -> ``**Title**``."""
    if tag_span is None:
        return text.strip()
    start, end = tag_span
    lead, trail = start, end
    if text[max(0, start - 2) : start] == "**" and text[end : end + 2] == "**":
        lead -= 2
        trail += 2
    before, after = text[:lead], text[trail:]
    if before.endswith("**"):
        m = re.match(r"^[ \t]?\*\*", after)
        # (a) drop the redundant "**" (before keeps its own); else (b) squeeze the stray gap
        after = after[m.end() :] if m else re.sub(r"^[ \t]+", "", after, count=1)
    return (before + after).strip()


def _row_title_text(content: str, tag_span: tuple[int, int] | None) -> str:
    """A short, readable title for id-minting and ``render``'s display — tag stripped, every other
    character of markdown kept (A-O12); never the field the store trusts for content (``next``
    keeps the row's full, untruncated text)."""
    first_line = content.splitlines()[0] if content else ""
    cleaned = " ".join(_title_without_tag(first_line, tag_span).split())
    if len(cleaned) > 197:
        cleaned = cleaned[:197] + "..."
    return cleaned or "(untitled backlog row)"


def _row_created(text: str) -> str | None:
    """The row's own creation date (spec: "creation date from the row's date") — the FIRST
    ``YYYY-MM-DD`` in the row's title line, which every sampled row carries right after its
    title; ``None`` when none is found, so the caller falls back to now."""
    m = _ROW_DATE_RE.search(text)
    if not m:
        return None
    try:
        d = date.fromisoformat(m.group(1))
    except ValueError:
        return None
    return d.isoformat() + "T00:00:00.000000Z"


def _table_cell_owner(cell_text: str, du: Any) -> tuple[str, str]:
    """Owner from a table's Tag/Owner cell — a bare word (``infra``) or a bracket, backtick-wrapped
    or not (Decision R.5, A-O8): ``because X``/``when Y`` never enter the owner, only the cell's
    own text does."""
    s = cell_text.strip()
    if s.startswith("`") and s.endswith("`") and len(s) >= 2:
        s = s[1:-1].strip()
    found = _find_first_tag(s, du)
    if found:
        return found[0], found[1]
    if re.fullmatch(r"[a-z0-9-]{1,32}", s):
        return s, ""
    return "", ""


def _scan_backlog_rows(text: str) -> list[dict]:
    """Every ROW of a STRATEGIC_BACKLOG.md-shaped file, per Decision R above. Returns one dict per
    row: ``shape`` (``heading2``/``heading3``/``bullet``/``table``), ``owner`` (lowercase, "" when
    none), ``full_tag`` (the raw bracket text, for a cross-tag note), ``title`` (markdown-intact,
    tag stripped), ``resolved`` (bool), ``title_line`` (the row's own first line, for date/resolved
    grounding), ``text`` (the row's own line PLUS every absorbed body line, up to but excluding the
    next row-start line — never truncated). Fences are tracked by their OPENING delimiter type
    (``` vs ~~~) through row bodies too, so nothing inside a fence is ever read as a row (A-O9,
    A-O15); the legend table is recognised by its EXACT ``Tag | Agent | Beat`` header, never by
    "cell 0 == Tag" alone (B-S2)."""
    du = _docs_updater()
    lines = text.split("\n")
    n = len(lines)
    rows: list[dict] = []

    current: dict | None = None
    body: list[str] = []

    def finish() -> None:
        nonlocal current, body
        if current is not None:
            current["text"] = "\n".join(body).strip("\n")
            rows.append(current)
        current = None
        body = []

    def start(
        shape: str, *, owner: str, full_tag: str, title: str, resolved: bool, title_line: str
    ) -> None:
        nonlocal current, body
        finish()
        current = {
            "shape": shape,
            "owner": owner,
            "full_tag": full_tag,
            "title": title,
            "resolved": resolved,
            "title_line": title_line,
        }
        body = [title_line]

    def append_body(line: str) -> None:
        if current is not None:
            body.append(line)

    in_fence = False
    fence_char = ""
    fence_len = 0
    header_cells: list[str] | None = None
    header_is_legend = False

    i = 0
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if in_fence:
            close_re = re.compile(r"^" + re.escape(fence_char * fence_len) + r"+\s*$")
            if close_re.match(stripped):
                in_fence = False
            append_body(line)
            i += 1
            continue

        fm = _FENCE_OPEN_RE.match(stripped)
        if fm:
            in_fence = True
            fence_char = fm.group(1)[0]
            fence_len = len(fm.group(1))
            append_body(line)
            header_cells = None
            i += 1
            continue

        if stripped.startswith("|"):
            if i + 1 < n and du._BACKLOG_SEPARATOR_RE.match(lines[i + 1].strip()):
                header_cells = du._backlog_row_cells(line)
                header_is_legend = tuple(c.strip() for c in header_cells) == _LEGEND_HEADER
                append_body(line)
                i += 1
                continue
            if header_cells is not None and du._BACKLOG_SEPARATOR_RE.match(stripped):
                append_body(line)
                i += 1
                continue
            if header_cells is not None and not header_is_legend:
                names = [c.strip() for c in header_cells]
                tag_idx = du._backlog_tag_header_index(names)
                if tag_idx is not None:
                    cells = du._backlog_row_cells(line)
                    if cells != names:  # the header row, re-offered — never a data row
                        owner, full_tag = _table_cell_owner(
                            cells[tag_idx] if tag_idx < len(cells) else "", du
                        )
                        # the same Item lookup --adopt uses (case-insensitive, W-77e00147)
                        item_idx = du._backlog_item_header_index(names)
                        if item_idx is None:
                            # no Item column: the first NON-EMPTY column that is not the tag
                            # column — the old fixed `1` titled tryton-crm's `Gap | Measured | … |
                            # Owner` rows by their measurement and a `Lane | Owner | …` table by its
                            # owner tag; a blank first cell must not blank a row with content later
                            item_idx = next(
                                (k for k, c in enumerate(cells) if k != tag_idx and c.strip()),
                                len(cells),
                            )
                        title_src = cells[item_idx] if item_idx < len(cells) else line
                        start(
                            "table",
                            owner=owner,
                            full_tag=full_tag,
                            title=" ".join(title_src.split())[:197] or "(untitled backlog row)",
                            # A-O18: a table row runs through the SAME resolved rule as any other
                            # row — the Item cell as strike_content, so `~~Old item~~` resolves.
                            resolved=_row_is_resolved(
                                line, strike_content=title_src, is_table=True
                            ),
                            title_line=line,
                        )
                        i += 1
                        continue
            append_body(line)
            i += 1
            continue
        header_cells = None

        m3 = _HEADING3_RE.match(line)
        if m3:
            content = m3.group(1)
            tag = _find_first_tag(content, du)
            span = tag[2] if tag else None
            resolved = _row_is_resolved(content, strike_content=content, tag_span=span)
            if tag is not None or resolved:
                owner, full_tag = (tag[0], tag[1]) if tag else ("", "")
                start(
                    "heading3",
                    owner=owner,
                    full_tag=full_tag,
                    title=_row_title_text(content, span),
                    resolved=resolved,
                    title_line=line,
                )
                i += 1
                continue
            append_body(line)
            i += 1
            continue

        m2 = _HEADING2_RE.match(line)
        if m2:
            content = m2.group(1)
            tag = _find_first_tag(content, du)
            owner, full_tag, span = tag if tag else ("", "", None)
            start(
                "heading2",
                owner=owner,
                full_tag=full_tag,
                title=_row_title_text(content, span),
                resolved=_row_is_resolved(content, strike_content=content, tag_span=span),
                title_line=line,
            )
            i += 1
            continue

        if line[:2] in ("- ", "* "):
            bm = du._BACKLOG_BULLET_RE.match(line)
            if bm:
                marker, content = bm.group(1), bm.group(2)
                checkbox_m = re.search(r"\[([ xX])\]", marker)
                checkbox = checkbox_m.group(1) if checkbox_m else ""
                struck = content.lstrip().startswith("~~")
                if checkbox or struck or _looks_bracket_led(content):
                    tag = _find_first_tag(content, du)
                    owner, full_tag, span = tag if tag else ("", "", None)
                    start(
                        "bullet",
                        owner=owner,
                        full_tag=full_tag,
                        title=_row_title_text(content, span),
                        resolved=_row_is_resolved(
                            content, checkbox=checkbox, strike_content=content, tag_span=span
                        ),
                        title_line=content,
                    )
                    i += 1
                    continue

        append_body(line)
        i += 1

    finish()
    return [row for row in rows if not _is_structural_row(row)]


def _body_is_empty(row: dict) -> bool:
    """W-02a0f674: True when every line of the row after its own first line is structure or template
    boilerplate — blank, `---`, an HTML comment, a table separator, or a `_TEMPLATE_PLACEHOLDER_LINES`
    line. Anything else is content, and a row holding content is never dropped (migration runs once per
    repo, so a dropped line would be lost for good)."""
    in_comment = False
    for raw in row["text"].split("\n")[1:]:
        line, in_comment = _strip_comments(raw, in_comment)
        if (
            not line
            or _RULE_LINE_RE.match(line)
            or _TABLE_SEPARATOR_RE.match(line)
            or _sans_list_marker(line) in _TEMPLATE_PLACEHOLDER_CONTENT
        ):
            continue
        return False
    # A comment still open at the row's end never closed: its "content" is unjudgeable, and migration
    # runs once — keep the row rather than drop text behind a typo (review r2).
    return not in_comment


def _strip_comments(raw: str, in_comment: bool) -> tuple[str, bool]:
    """``raw`` with every HTML-comment span removed (a comment may open or close mid-line, or span
    lines), stripped, plus whether a comment is still open at its end. Text OUTSIDE a span is kept,
    so `<!-- note --> real text` is judged on `real text`, never skipped whole."""
    out: list[str] = []
    rest = raw
    while rest:
        if in_comment:
            end = rest.find("-->")
            if end < 0:
                return " ".join(out).strip(), True
            rest, in_comment = rest[end + 3 :], False
        else:
            start = rest.find("<!--")
            if start < 0:
                out.append(rest)
                break
            out.append(rest[:start])
            rest, in_comment = rest[start + 4 :], True
    return " ".join(out).strip(), in_comment


def _is_structural_row(row: dict) -> bool:
    """D-566 (W-02a0f674), superseding Decision R's "a `## ` heading (any)" for one case: a row is structure, not
    work, when its body is empty AND it is either an untagged, unresolved `## ` section heading or a row
    whose own line is a template placeholder. A heading with real body content — a "Now" table holding
    real rows, a project's own constraints — still migrates, exactly as before."""
    if not _body_is_empty(row):
        return False
    if row["shape"] == "heading2" and not row["owner"] and not row["resolved"]:
        return True
    return _sans_list_marker(row["title_line"]) in _TEMPLATE_PLACEHOLDER_CONTENT


def _row_digest(text: str, ordinal: int) -> str:
    """Decision R.7 (A-O3): the digest covers the row's text PLUS its occurrence ordinal among
    identical texts in this scan, so two genuinely duplicated source rows (the hub file carries one
    byte-for-byte duplicated heading section) become two items, never a silent collapse. Dedupe is
    against the STORE's existing digests only — the caller never adds a newly-created digest back
    into that set, so two duplicates within one run are never compared against each other, only
    against what already existed before this run."""
    return hashlib.sha1(f"{text}\x00{ordinal}".encode(), usedforsecurity=False).hexdigest()[:12]


def _existing_backlog_digests(repo: Path) -> set[str]:
    out: set[str] = set()
    for it in _iter_items(repo):
        if it.get("kind") != "backlog":
            continue
        m = _MIGRATED_DIGEST_RE.search(str(it.get("note") or ""))
        if m:
            out.add(m.group(1))
    return out


def _row_note(row: dict, digest: str) -> str:
    plain_tag = f"[{row['owner']}]" if row["owner"] else ""
    if row["full_tag"] and row["full_tag"] != plain_tag:
        return f"full-tag:{row['full_tag']}; migrated-digest:{digest}"
    return f"migrated-digest:{digest}"


def _strip_backlog_block(text: str) -> str:
    """Remove the rendered AUTO-GENERATED:BACKLOG block, together with the EXACT whitespace
    ``_insert_backlog_block`` added around it, before scanning — never re-scan ``render``'s own
    output as fresh source rows (a migrate-backlog run after a render would otherwise treat every
    rendered `` - **[owner]** title (`W-…`) `` line as a brand-new bullet row and recreate the
    whole open set on every later run). Symmetric removal (Decision B.3, A-O5): stripping exactly
    what was inserted means a row whose body happened to run up to the insertion point reads
    byte-identically whether the block exists or not, so its digest never drifts across a
    migrate → render → migrate cycle. Raises ``WorkError`` on an ambiguous block (Decision B.2)."""
    found = _find_backlog_block(text)
    if found is None:
        return text
    s_begin, s_end, e_begin, e_end = found
    lead = s_begin
    if text[max(0, s_begin - 2) : s_begin] == "\n\n":
        lead = s_begin - 2
    elif text[max(0, s_begin - 1) : s_begin] == "\n":
        lead = s_begin - 1
    trail = e_end
    if text[e_end : e_end + 1] == "\n":
        trail = e_end + 1
    return text[:lead] + text[trail:]


def cmd_migrate_backlog(repo: Path, args: argparse.Namespace) -> int:
    """Turn every ROW of ``docs/STRATEGIC_BACKLOG.md`` into a ``kind: backlog`` item — idempotent
    against the STORE's own existing digests, kept in ``note`` (spec § The backlog becomes a view;
    Decision R.7). Never writes the backlog file itself; that is ``render``'s job alone.

    Once per repo (spec § Lifecycle): after ``migrated_at`` is set the verb creates nothing. The
    adopting agent then trims the migrated rows and keeps the hand-written context (D-413), and a
    second scan would read that context's ``## `` sections as fresh rows (D-407) and turn them
    into ownerless items; new backlog work is ``work.py add --kind backlog``."""
    _require_store(repo)
    done_at = _read_config(repo).get("migrated_at")
    if done_at:
        print(
            f"work: migrate-backlog — already migrated at {done_at}; 0 item(s) created "
            "(new backlog work is `work.py add --kind backlog`)"
        )
        return 0
    path = repo / _BACKLOG_REL
    if not path.is_file():
        # T09 review A-O5: a repo with no backlog file still COMPLETES its migration (there is
        # nothing to migrate, but the migration itself is done) — otherwise `migrated_at` is never
        # recorded here and `sync --check` can never become blocking in this repo (class 7's own
        # gate, ``_backlog_needs_render``, already reads "no file" as "no drift", never a flag).
        with _store_lock(repo, CLI_LOCK_TIMEOUT_S, fail_open=False, label="migrate-backlog"):
            cfg = _read_config(repo)
            if not cfg.get("migrated_at"):
                cfg["migrated_at"] = _now_iso()
                _write_json(_config_path(repo), cfg)
        print(
            f"work: migrate-backlog — no {_rel(repo, path)}, nothing to migrate — "
            "migration recorded complete"
        )
        return 0
    text = _strip_backlog_block(path.read_text(encoding="utf-8", errors="replace"))
    rows = _scan_backlog_rows(text)
    created = 0
    unowned: list[str] = []
    occurrence: dict[str, int] = {}
    with _store_lock(repo, CLI_LOCK_TIMEOUT_S, fail_open=False, label="migrate-backlog"):
        existing = _existing_backlog_digests(repo)  # read ONCE; never mutated (Decision R.7)
        for row in rows:
            ordinal = occurrence.get(row["text"], 0)
            occurrence[row["text"]] = ordinal + 1
            digest = _row_digest(row["text"], ordinal)
            if digest in existing:
                continue
            item = _new_item(
                kind="backlog",
                title=row["title"],
                next_action=row["text"],
                links={},
                priority=DEFAULT_PRIORITY,
            )
            created_at = _row_created(row["title_line"])
            if created_at:
                item["created"] = created_at
            item["owner"] = row["owner"]
            item["note"] = _row_note(row, digest)
            if row["resolved"]:
                item["status"] = "done"
                item["legacy"] = True
            _create_item(repo, item)
            created += 1
            if not row["owner"]:
                unowned.append(str(item["id"]))
        if created:
            _after_write(repo, _session())
        cfg = _read_config(repo)
        if not cfg.get("migrated_at"):
            cfg["migrated_at"] = _now_iso()
            _write_json(_config_path(repo), cfg)
    print(
        f"work: migrate-backlog — {created} item(s) created from {len(rows)} "
        f"row(s) in {_rel(repo, path)}"
    )
    if unowned:
        print("work: needs the distributor (no owner tag) — " + ", ".join(unowned))
    return 0


def _render_backlog_body(items: list[dict]) -> str:
    """Deterministic BACKLOG block body — open ``kind: backlog`` items only, sorted by priority,
    owner, then id; no timestamp, so two renders of the same store are byte-identical. Every open
    item's id must appear here, in its line's TRAILING backtick-parens position, and no other id
    may: ``_backlog_needs_render``'s class-7 reader trusts exactly that (Decision B.6, A-O13)."""
    open_items = [
        it for it in items if it.get("kind") == "backlog" and it.get("status") not in RESOLVED
    ]
    open_items.sort(key=lambda it: (_priority(it), str(it.get("owner") or ""), str(it["id"])))
    if not open_items:
        return (
            '_No open backlog items. New backlog work: `work.py add --kind backlog --title "..."`._'
        )
    lines = []
    for it in open_items:
        owner = it.get("owner") or "unassigned"
        title = " ".join(str(it.get("title") or "(untitled)").split())
        lines.append(f"- **[{owner}]** {title} (`{it['id']}`)")
    return "\n".join(lines)


_BACKLOG_HR_RE = re.compile(r"^---[ \t]*$", re.M)
_H1_RE = re.compile(r"^# ")


def _insert_backlog_block(text: str, body: str) -> str:
    """Insert a brand-new BACKLOG block below the first ``^---$`` rule AFTER the file's first
    ``# `` (H1) heading, outside YAML front matter and outside fences (Decision B.4, A-O6); with no
    such rule, after the H1 heading's own paragraph (or right after the heading when it has none).
    No timestamp anywhere, including the version comment (Decision B.1, A-H1) — the output is
    byte-deterministic from the store alone."""
    block = (
        "<!-- AUTO-GENERATED:BACKLOG:START -->\n"
        "<!-- AUTO-GENERATED:BACKLOG v1 -->\n"
        f"{body}\n"
        "<!-- AUTO-GENERATED:BACKLOG:END -->"
    )
    lines = text.split("\n")
    n = len(lines)
    start_i = 0
    if lines and lines[0].strip() == "---":  # YAML front matter — skip past its closing `---`
        j = 1
        while j < n and lines[j].strip() != "---":
            j += 1
        start_i = j + 1 if j < n else 0
    h1_idx = None
    for k in range(start_i, n):
        if _H1_RE.match(lines[k]):
            h1_idx = k
            break
    if h1_idx is None:
        head, sep, rest = text.partition("\n")
        return f"{head}\n\n{block}\n{sep}{rest}"
    in_fence = False
    fence_char = ""
    fence_len = 0
    hr_idx = None
    for k in range(h1_idx + 1, n):
        s = lines[k].strip()
        if in_fence:
            close_re = re.compile(r"^" + re.escape(fence_char * fence_len) + r"+\s*$")
            if close_re.match(s):
                in_fence = False
            continue
        fm = _FENCE_OPEN_RE.match(s)
        if fm:
            in_fence = True
            fence_char = fm.group(1)[0]
            fence_len = len(fm.group(1))
            continue
        if s == "---":
            hr_idx = k
            break
    if hr_idx is not None:
        before = "\n".join(lines[: hr_idx + 1])
        after = "\n".join(lines[hr_idx + 1 :])
        return f"{before}\n\n{block}\n\n{after}" if after.strip() else f"{before}\n\n{block}\n"
    k = h1_idx + 1
    while k < n and lines[k].strip() != "":
        k += 1
    before = "\n".join(lines[:k])
    after = "\n".join(lines[k:])
    return f"{before}\n\n{block}\n\n{after}" if after.strip() else f"{before}\n\n{block}\n"


def cmd_render(repo: Path, args: argparse.Namespace) -> int:
    """Regenerate the backlog's ``AUTO-GENERATED:BACKLOG`` block — the only writer of it. Never
    calls ``docs_updater.replace_block``: that helper always stamps a changed block with the
    current time and matches its markers by first-occurrence search, neither of which Decision B
    permits here (no timestamp ever, ever; whole-line markers, refuse loud on ambiguity) — so this
    verb splices the block directly at the offsets ``_find_backlog_block`` returns.

    A-O20/A-O24: the file's own newline style is preserved, but ONLY when it is UNIFORM — every
    newline in the file is part of a CRLF pair. In that case all internal logic — scanning,
    diffing, splicing — runs on an LF-normalized copy, and CRLF is restored on the WHOLE string
    right before the write (safe exactly because every line was CRLF to begin with, so blanket
    restoration reproduces the original for every untouched line too). A file with even ONE bare
    LF line is left ENTIRELY alone outside the block: no normalization, no restoration, so the
    untouched prefix/suffix bytes pass through byte-for-byte and only the spliced block itself is
    new content — a single stray CRLF line elsewhere must never become the whole file's style
    (previously a lone CRLF line anywhere flipped every other line to CRLF too)."""
    _require_store(repo)
    path = repo / _BACKLOG_REL
    if not path.is_file():
        # T09 review A-O5: a repo with no backlog file is a no-op, not an error — T10's adoption
        # runs `init` -> `migrate-backlog` -> `render` in every repo, including backlog-less
        # template repos that "migrate to an empty store"; render never CREATES the backlog file.
        print(f"work: render — no {_rel(repo, path)} — nothing to render")
        return 0
    raw = path.read_bytes()
    crlf_n = raw.count(b"\r\n")
    lf_n = raw.count(b"\n")
    uniform_crlf = crlf_n > 0 and crlf_n == lf_n
    text = raw.decode("utf-8")
    working = text.replace("\r\n", "\n") if uniform_crlf else text
    body = _render_backlog_body(list(_iter_items(repo)))
    found = _find_backlog_block(working)  # raises WorkError on an ambiguous/orphan marker
    if found is None:
        new_text = _insert_backlog_block(working, body)
        changed = new_text != working
    else:
        s_begin, s_end, e_begin, e_end = found
        current_inner = working[s_end:e_begin]
        if _block_body_norm(current_inner) == _block_body_norm(body):
            new_text, changed = working, False
        else:
            new_inner = f"\n<!-- AUTO-GENERATED:BACKLOG v1 -->\n{body}\n"
            new_text = working[:s_end] + new_inner + working[e_begin:]
            changed = True
    if changed:
        out_text = new_text.replace("\n", "\r\n") if uniform_crlf else new_text
        _write_text(path, out_text)
        print(f"work: render — updated {_rel(repo, path)}")
    else:
        print(f"work: render — {_rel(repo, path)} already current")
    return 0


def _block_body_norm(body: str) -> str:
    """The comparable form of a BACKLOG block's inner text: strip any ``<!-- AUTO-GENERATED:``
    machinery line (the version comment) before comparing, so that line alone never reads as a
    content change — mirrors ``docs_updater._block_body_norm``'s convention without importing it
    (this module never calls ``replace_block`` for the backlog block; see ``cmd_render``)."""
    return "\n".join(
        ln for ln in body.split("\n") if not ln.startswith("<!-- AUTO-GENERATED:")
    ).strip()


def cmd_init(repo: Path, args: argparse.Namespace) -> int:
    """Create the store. It takes no lock: config.json is created by an exclusive link (one
    winner), and the lock lives in a shared dir that must not exist before the store does."""
    cfg = _config_path(repo)
    if cfg.exists():
        raise WorkError(f"{_rel(repo, cfg)} already exists — the store is initialised")
    other = _store_elsewhere(repo)
    if other is not None:
        raise WorkError(
            f"the working tree {other} already has a work store — every worktree of this "
            "repository shares it through git; merge or rebase onto its branch instead of init"
        )
    if args.distributor is None:
        distributor = _merge_owner(repo)
    else:
        distributor = args.distributor.strip()
        if distributor and not _valid_name(distributor):
            raise WorkError(f"--distributor {distributor!r} is not an agent name ({NAME_RULE})")
    store = _store_dir(repo)
    try:
        store.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkError(f"cannot create {_rel(repo, store)}: {exc}") from exc
    ignore = store / ".gitignore"
    if not ignore.exists():
        _write_text(ignore, "*.tmp\n")  # a writer killed mid-write leaves a temp nobody commits
    base_branch = _branch_of(_worktrees(repo)[0])
    try:
        _write_json(cfg, {"base_branch": base_branch, "distributor": distributor}, exclusive=True)
    except FileExistsError:
        raise WorkError(f"{_rel(repo, cfg)} already exists — the store is initialised") from None
    print(_rel(repo, cfg))
    if not distributor:
        print(f"no distributor named — set `distributor` in {_rel(repo, cfg)}")
    return 0


def _parse_links(raw: list[str]) -> dict[str, str]:
    links: dict[str, str] = {}
    for entry in raw:
        key, sep, value = entry.partition("=")
        if not sep or key not in LINK_KEYS or not value:
            raise WorkError(f"--link {entry!r}: expected one of {'|'.join(LINK_KEYS)}=<value>")
        links[key] = value
    return links


def cmd_add(repo: Path, args: argparse.Namespace) -> int:
    _require_store(repo)
    if args.kind == "decision":
        raise WorkError(
            "--kind decision is refused: decision items come only from DECISION blocks "
            "(the Stop-hook harvest), never from `add`"
        )
    if args.kind in LINKED_KINDS:
        raise WorkError(
            f"--kind {args.kind} is refused: {args.kind} items come only from taking the "
            "obligation (a mail claim, a feedback queue), never from `add`"
        )
    if args.kind == "next":
        raise WorkError(
            "--kind next is refused: a next item comes only from the Stop harvest of a "
            "session's NEXT line, never from `add`"
        )
    title = " ".join(args.title.split())
    if not title:
        raise WorkError("--title is empty")
    item = _new_item(
        kind=args.kind,
        title=title,
        next_action=" ".join((args.next or "").split()),
        links=_parse_links(args.link or []),
        priority=args.priority,
    )
    tags = _parse_tags(args.tag or [])
    if tags:
        item["tags"] = tags
    with _store_lock(repo, CLI_LOCK_TIMEOUT_S, fail_open=False, label="add"):
        path = _create_item(repo, item)
        _after_write(repo, _session())
    print(_rel(repo, path))
    return 0


def _parse_tags(values: list[str]) -> list[str]:
    for tag in values:
        if not _TAG_RE.fullmatch(tag):
            raise WorkError(f"--tag {tag!r} is not a tag ({TAG_RULE})")
        if tag.startswith(HELD_PREFIX):
            rest = tag[len(HELD_PREFIX) :]
            if not rest or (rest[:1].isdigit() and _waits_until(tag) is None):
                raise WorkError(
                    f"--tag {tag!r}: a wait is `waits-<slug>` or `waits-YYYY-MM-DD` with a real "
                    "date; a typo would park the item forever"
                )
    return sorted(set(values))


def cmd_assign(repo: Path, args: argparse.Namespace) -> int:
    _require_store(repo)
    # --untag is NOT validated against TAG_RULE: removing must work for any value already stored,
    # including one a hand edit or an older rule let in (a validated --untag could never clear it).
    add_tags, drop_tags = _parse_tags(args.tag or []), sorted(set(args.untag or []))
    both = set(add_tags) & set(drop_tags)
    if both:
        raise WorkError(f"--tag and --untag both name {', '.join(sorted(both))}; pick one")
    if args.owner is None and args.priority is None and not add_tags and not drop_tags:
        raise WorkError("assign needs --owner, --priority, --tag and/or --untag")
    owner = None if args.owner is None else args.owner.strip()
    if owner and not _valid_name(owner):
        raise WorkError(f"--owner {owner!r} is not an agent name ({NAME_RULE}); owners are agents")
    _read_item(repo, args.id)  # a missing id is named before any ownership check
    with _store_lock(repo, CLI_LOCK_TIMEOUT_S, fail_open=False, label="assign"):
        distributor = str(_read_config(repo).get("distributor") or "").strip()
        if distributor and _agent_name() != distributor:
            raise WorkError(
                f"assign is the distributor's ({distributor}); this caller is {_actor_label()}"
            )
        item = _read_item(repo, args.id)
        if owner is not None:
            item["owner"] = owner
        if args.priority is not None:
            item["priority"] = args.priority
        if add_tags or drop_tags:
            tags = (set(item.get("tags") or []) | set(add_tags)) - set(drop_tags)
            if tags:
                item["tags"] = sorted(tags)
            else:
                item.pop("tags", None)
        path = _write_item(repo, item)
        _after_write(repo, _session())
    print(_rel(repo, path))
    return 0


READY_OTHERS_SHOWN = 10


def cmd_ready(repo: Path, args: argparse.Namespace) -> int:
    """``--all``: every ready item (the old default). Default (spec D4 — crisp): the obligation
    lines; this session's claims; open items owned by this agent; awaiting items; then the top 10
    remaining ready items and how many more ``--all`` would show. No item prints twice.
    COBRA (D-253): the cheapest crisp ``ready`` is one where nothing is ever assigned (so nothing
    is "owned") — ``status`` prints the unowned count to the distributor for exactly that."""
    _require_store(repo)
    agent = _agent_name()
    if args.all:
        for item in _ready_items(repo, mine=args.mine, agent=agent if args.mine else ""):
            print(_line(item))
        return 0
    for line in obligations(repo):
        print(line)
    items = list(_iter_items(repo))
    closed = _closed_ids(repo)
    claims = _live_claims(repo)
    by_id = {str(it["id"]): it for it in items}
    shown: set[str] = set()
    session = _session()
    for item_id, claim in sorted(claims.items()):
        mine = by_id.get(item_id)
        if session and claim.get("session") == session and mine is not None:
            if mine.get("status") not in RESOLVED and item_id not in closed:
                print(_line(mine) + " (yours)")
                shown.add(item_id)

    def order(it: dict) -> tuple:
        return (_priority(it), str(it.get("created", "")), str(it["id"]))

    owned = [
        it
        for it in items
        if agent
        and it.get("owner") == agent
        and it.get("status") == "open"
        and it.get("kind") != "next"
        and it["id"] not in closed
        and it["id"] not in claims
    ]
    awaiting = [
        it for it in items if it.get("status") == "awaiting-operator" and it["id"] not in closed
    ]
    awaiting.sort(key=lambda it: (str(it.get("created", "")), str(it["id"])))
    for item in [*sorted(owned, key=order), *awaiting]:
        if item["id"] not in shown:
            print(_line(item))
            shown.add(item["id"])
    rest = [
        it
        for it in _ready_from(items, closed, claims, mine=args.mine, agent=agent)
        if it["id"] not in shown
    ]
    for item in rest[:READY_OTHERS_SHOWN]:
        print(_line(item))
    if len(rest) > READY_OTHERS_SHOWN:
        print(f"… and {len(rest) - READY_OTHERS_SHOWN} more — work.py ready --all")
    return 0


def cmd_next(repo: Path, args: argparse.Namespace) -> int:
    _require_store(repo)
    items = [i for i in _ready_items(repo, mine=True, agent=_agent_name()) if not _is_parked(i)]
    if items:
        print(_line(items[0]))
    else:
        _warn("nothing ready")
    return 0


def _call_session(args: argparse.Namespace) -> str:
    return (getattr(args, "session", None) or "").strip() or _session()


def _refuse_closed(repo: Path, item: dict, verb: str) -> None:
    """``verb`` needs an item that is still open here and not closed in another tree."""
    status = item.get("status")
    if status == "awaiting-operator":
        raise WorkError(
            f"{verb} {item['id']} refused: it is awaiting-operator — only `work.py answer` "
            "closes an awaiting item, with the operator's words"
        )
    if status in RESOLVED:
        raise WorkError(f"{verb} {item['id']} refused: it is already {status}")
    if item["id"] in _closed_ids(repo):
        raise WorkError(
            f"{verb} {item['id']} refused: it was closed in another working tree "
            f"(a closed marker in {_closed_dir(repo)}) — "
            "merge that branch instead"
        )


def _refuse_blocked(repo: Path, item: dict) -> None:
    """``claim`` needs a claimable item — ``ready``'s rule: not ``blocked``, and every
    ``blocked_by`` id done or dropped (here, or closed by a marker)."""
    if item.get("status") == "blocked":
        raise WorkError(f"claim {item['id']} refused: its status is blocked")
    by_id = {str(it["id"]): it for it in _iter_items(repo)}
    closed = _closed_ids(repo)
    waiting = [
        str(dep)
        for dep in item.get("blocked_by") or []
        if str(dep) not in closed and by_id.get(str(dep), {}).get("status") not in RESOLVED
    ]
    if waiting:
        raise WorkError(
            f"claim {item['id']} refused: it is blocked by {', '.join(waiting)} "
            "(not yet done or dropped)"
        )


def _close(
    repo: Path, item: dict, *, session: str, evidence: str = "", note: str = "", decision: str = ""
) -> Path:
    """Close ``item`` (already updated). The commit is the marker FIRST, then the item — a failed
    item write removes the marker and re-raises — so a failure never leaves an item closed here
    while every other tree still lists it, nor a closed marker for an open item. Ending the claim
    comes AFTER the commit and is best-effort: a failure there is one stderr line and a normal
    return (the lease expires on its own). So ``_close`` raises ONLY when nothing was committed —
    every caller may read an exception as "not closed"."""
    _write_marker(repo, item, session=session, evidence=evidence, note=note, decision=decision)
    try:
        path = _write_item(repo, item)
    except BaseException:
        with contextlib.suppress(OSError):
            (_closed_dir(repo) / f"{item['id']}.json").unlink()
        raise
    try:
        _end_claim(repo, str(item["id"]))
    except Exception as exc:
        _warn(
            f"{item['id']} closed; its claim was not ended — {type(exc).__name__}: {exc}; "
            "the lease expires on its own"
        )
    return path


def _fence(repo: Path, item_id: str, session: str, verb: str) -> dict | None:
    """The fencing check: refused unless ``session`` holds the live claim, or there is none."""
    claim = _claim_of(repo, item_id)
    if _is_live(claim) and claim is not None and claim.get("session") != session:
        raise WorkError(
            f"{verb} {item_id} refused: token mismatch — the live claim is held by "
            f"{_holder(claim)}; this caller is session {session or '(none)'}. "
            "Nothing was changed"
        )
    return claim


def _evidence_commit(repo: Path, item_id: str, sha: str) -> str | None:
    """The resolved commit SHA if ``sha`` exists in ``repo`` and its message names ``item_id``,
    else None — the one-pair form of ``_evidence_commits``, shared by ``_verify_evidence`` and
    drift class 6 (T02)."""
    return _evidence_commits(repo, [(item_id, sha)])[(item_id, sha)]


def _evidence_commits(
    repo: Path, pairs: list[tuple[str, str]]
) -> dict[tuple[str, str], str | None]:
    """For each ``(item_id, sha)``, the resolved commit SHA when ``sha`` names a commit in
    ``repo`` whose message names ``item_id``, else None — every pair in ONE ``git cat-file
    --batch`` fed ``<sha>^{commit}`` (W-5937c2cd: three git calls per done item cost the hub's
    ``status`` seconds). The header line resolves the object (a short, tag or full sha peels to
    its commit; ``missing``/``ambiguous`` and a non-commit are None) and the body carries the
    message (the raw object: split at the first blank line, never re-encoded). An empty value,
    one starting with ``-`` and one outside ``_EVIDENCE_REV_RE`` are None without asking git — a
    newline would split the batch's records and a NUL would truncate one, letting a valid prefix
    pass (the per-pair read raised on a NUL instead). A failed batch read degrades every pair to
    None, as the per-pair read did."""
    result: dict[tuple[str, str], str | None] = dict.fromkeys(pairs)
    asked = [
        (item_id, sha)
        for item_id, sha in dict.fromkeys(pairs)
        if not sha.startswith("-") and _EVIDENCE_REV_RE.fullmatch(sha)
    ]
    if not asked:
        return result
    req = "".join(f"{sha}^{{commit}}\n" for _, sha in asked)
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "--batch"],
            input=req.encode(),
            capture_output=True,
            timeout=_git_timeout(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return result
    if proc.returncode != 0:
        return result
    out, pos = proc.stdout, 0
    try:
        for item_id, sha in asked:
            nl = out.index(b"\n", pos)
            head = out[pos:nl].split()
            pos = nl + 1
            if len(head) != 3:
                continue  # "<rev> missing" / "<rev> ambiguous" carry no body
            size = int(head[2])
            body = out[pos : pos + size]
            pos += size + 1
            if head[1] != b"commit":
                continue
            text = body.decode("utf-8", "replace")
            message = text.split("\n\n", 1)[1] if "\n\n" in text else ""
            if item_id in _ITEM_REF_RE.findall(message):
                result[(item_id, sha)] = head[0].decode()
    except ValueError:
        return dict.fromkeys(pairs)
    return result


def _verify_evidence(repo: Path, item_id: str, evidence: str | None) -> str:
    """The full SHA of a commit that exists and whose message names ``item_id``."""
    ev = (evidence or "").strip()
    if not ev:
        raise WorkError(
            f"done {item_id} needs --evidence <sha>: a commit whose message names {item_id}"
        )
    resolved = _evidence_commit(repo, item_id, ev)
    if resolved is None:
        raise WorkError(
            f"--evidence {ev!r} does not resolve to a commit in {repo} naming {item_id} — "
            "the evidence is the commit that did the work, and it says so"
        )
    return resolved


def _claim_record(
    claim: dict | None, session: str, now: float, *, agent: str | None = None
) -> tuple[dict, str] | None:
    """``claim`` taken or renewed for ``session``: the renewed record and ``"renewed"`` when
    ``session`` holds it live, a new record with the old token + 1 and ``"claimed"`` when nobody
    does, None when ANOTHER session holds it live (the caller decides whether that refuses).
    A new record's ``agent`` is ``agent`` when given, else ``_agent_name()`` (the CLI's)."""
    if _is_live(claim, now) and claim is not None:
        if claim.get("session") != session:
            return None
        return {**claim, "at": now}, "renewed"  # the live holder's claim renews it
    fresh = {
        "agent": _agent_name() if agent is None else agent,
        "at": now,
        "lease_s": DEFAULT_LEASE_S,
        "session": session,
        "token": int(_num((claim or {}).get("token"))) + 1,
    }
    return fresh, "claimed"


def cmd_claim(repo: Path, args: argparse.Namespace) -> int:
    _require_store(repo)
    _read_item(repo, args.id)  # a missing id is named before anything else
    session = _call_session(args)
    if not session:
        raise WorkError(
            "claim needs a session: CLAUDE_CODE_SESSION_ID is unset and no --session <id> "
            "was given (cron and plain shells cannot hold a lease)"
        )
    with _store_lock(repo, CLI_LOCK_TIMEOUT_S, fail_open=False, label="claim"):
        item = _read_item(repo, args.id)
        _refuse_closed(repo, item, "claim")
        _refuse_blocked(repo, item)
        held = _claim_of(repo, args.id)
        taken = _claim_record(held, session, time.time())
        if taken is None:  # only a live claim held by ANOTHER session refuses
            raise WorkError(f"claim {args.id} refused: it is held by {_holder(held or {})}")
        claim, verb = taken
        _write_claim(repo, args.id, claim)
        _after_write(repo, session)
    print(f"{verb} {args.id} — token {claim['token']}, lease until {_iso(_claim_end(claim))}")
    return 0


def cmd_release(repo: Path, args: argparse.Namespace) -> int:
    _require_store(repo)
    _read_item(repo, args.id)
    session = _call_session(args)
    with _store_lock(repo, CLI_LOCK_TIMEOUT_S, fail_open=False, label="release"):
        claim = _fence(repo, args.id, session, "release")
        if not _is_live(claim):
            print(f"{args.id} has no live claim — nothing to release")
            return 0
        _end_claim(repo, args.id)
        _after_write(repo, session)
    print(f"released {args.id}")
    return 0


_LINKED_CLOSE = {"mail": "mail is acked", "feedback": "queue is marked answered"}


def _base_record(repo: Path, item_id: str) -> dict | None:
    """``item_id``'s whole record on the store's base branch, or None (no branch, no file, a git
    failure, malformed JSON) — the full-record sibling of ``_base_statuses``."""
    branch = _base_branch(repo)
    if not branch:
        return None
    try:
        raw = _git(repo, "show", f"refs/heads/{branch}:{STORE_REL.as_posix()}/{item_id}.json")
    except WorkError:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _resolve_commit(repo: Path, rev: str) -> str:
    """The full SHA ``rev`` names as a commit, or "" (an option-shaped or unknown rev)."""
    if rev.startswith("-") or not _EVIDENCE_REV_RE.fullmatch(rev):
        return ""
    try:
        return _git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").strip()
    except WorkError:
        return ""


def _cited_done(repo: Path, cited: str) -> tuple[dict, str]:
    """``(record, source)`` of ``cited`` closed DONE, read in order from this tree's file, the
    base branch, then an effective closed marker — the three places a done item can be seen from
    a checkout (D-403). Refused (WorkError) when none reads it done or its record carries no
    evidence (an answered decision, a linked mail/feedback item, a legacy row)."""
    looked = []
    path = _item_path(repo, cited)
    if path.exists():
        rec = _read_item(repo, cited)
        if rec.get("status") == "done":
            looked.append((rec, "this tree"))
    base = _base_record(repo, cited)
    if base is not None and base.get("status") == "done":
        looked.append((base, "the base branch"))
    marker = _read_records(_closed_dir(repo)).get(cited)
    if marker and marker.get("status") == "done" and cited in _closed_ids(repo):
        looked.append((marker, "a closed marker"))
    for rec, source in looked:
        if str(rec.get("evidence") or "").strip():
            return rec, source
    if looked:
        raise WorkError(
            f"--resolved-by {cited} refused: {cited} is done but records no evidence commit "
            "(an answered decision, a linked item or a legacy row) — there is no fix to carry"
        )
    raise WorkError(
        f"--resolved-by {cited} refused: {cited} is not done in this tree, on the base branch "
        "or in a closed marker — close it first, or cite the item whose commit fixed this one"
    )


def cmd_done(repo: Path, args: argparse.Namespace) -> int:
    _require_store(repo)
    first = _read_item(repo, args.id)
    kind = str(first.get("kind") or "")
    if kind in LINKED_KINDS:
        raise WorkError(
            f"done {args.id} refused: a {kind} item closes when its {_LINKED_CLOSE[kind]}"
        )
    _refuse_closed(repo, first, "done")
    session = _call_session(args)
    cited = (getattr(args, "resolved_by", None) or "").strip()
    if cited:
        if cited == args.id:
            raise WorkError(f"--resolved-by {cited} refused: an item cannot be resolved by itself")
    else:
        sha = _verify_evidence(repo, args.id, args.evidence)
    with _store_lock(repo, CLI_LOCK_TIMEOUT_S, fail_open=False, label="done"):
        item = _read_item(repo, args.id)
        _refuse_closed(repo, item, "done")
        _fence(repo, args.id, session, "done")
        extra: dict = {}
        if cited:
            rec, source = _cited_done(repo, cited)
            stored = str(rec["evidence"]).strip()
            # recorded evidence is a SHA, never a ref: a branch name would re-resolve to
            # whatever it points at NOW, so two citations of one root could carry two commits
            sha = _resolve_commit(repo, stored) if _HEX_SHA_RE.fullmatch(stored) else ""
            if not sha:
                raise WorkError(
                    f"--resolved-by {cited} refused: {cited}'s recorded evidence "
                    f"{stored!r} (read from {source}) is not a commit SHA here"
                )
            given = (args.evidence or "").strip()
            if given and _resolve_commit(repo, given) != sha:
                raise WorkError(
                    f"--resolved-by {cited} refused: {cited} was closed by {sha[:12]} (read from "
                    f"{source}); cite that commit, or omit --evidence to carry it"
                )
            extra = {"resolved_by": str(rec.get("resolved_by") or cited)}
        item.update(status="done", evidence=sha, **extra)
        path = _close(repo, item, session=session, evidence=sha)
        _after_write(repo, session)
    print(_rel(repo, path))
    return 0


def _drop_duplicate(repo: Path, args: argparse.Namespace, keep_id: str, why: str) -> int:
    """D5: retire the awaiting ``args.id`` into the open awaiting ``keep_id`` — the distributor's
    verb, or a caller whose NON-EMPTY agent name or session id is the ``creator`` of BOTH items
    (the owner rule of a plain drop does not apply)."""
    item_id = args.id
    verb = f"drop {item_id} --duplicate-of {keep_id}"
    if keep_id == item_id:
        raise WorkError(f"{verb} refused: an item cannot be a duplicate of itself")
    _read_item(repo, keep_id)
    session = _call_session(args)
    with _store_lock(repo, CLI_LOCK_TIMEOUT_S, fail_open=False, label="drop"):
        item = _read_item(repo, item_id)
        keep = _read_item(repo, keep_id)
        closed = _closed_ids(repo)
        for it in (item, keep):
            if it.get("status") != "awaiting-operator":
                raise WorkError(
                    f"{verb} refused: {it['id']} is {it.get('status')}, "
                    "not an open awaiting-operator item"
                )
            if it["id"] in closed:
                marker = _read_records(_closed_dir(repo)).get(str(it["id"])) or {}
                tree = str(marker.get("tree") or "") or "an unnamed tree"
                raise WorkError(
                    f"{verb} refused: {it['id']} was closed in another working tree, {tree} "
                    f"(a closed marker in {_closed_dir(repo)})"
                )
        distributor = str(_read_config(repo).get("distributor") or "").strip()
        agent = _agent_name()
        me = {agent, _session()} - {""}  # an empty identity never matches an empty creator
        creators = [str(it.get("creator") or "") for it in (item, keep)]
        if not ((distributor and agent == distributor) or all(c in me for c in creators)):
            raise WorkError(
                f"{verb} is the distributor's ({distributor or 'none named'}) or the creator's "
                f"of both items ({creators[0] or 'none'}, {creators[1] or 'none'}); this caller "
                f"is {_actor_label()}, session {_session() or '(none)'}"
            )
        _fence(repo, item_id, session, "drop")
        pre_image = copy.deepcopy(keep)  # restored if the duplicate's close fails
        own = str(keep.get("block_digest") or "")
        digests = [
            *(keep.get("alt_block_digests") or []),
            item.get("block_digest"),
            *(item.get("alt_block_digests") or []),
        ]
        keep["alt_block_digests"] = list(
            dict.fromkeys(str(d) for d in digests if d and str(d) != own)
        )
        ids = [*(keep.get("alt_ids") or []), item_id, *(item.get("alt_ids") or [])]
        keep["alt_ids"] = list(dict.fromkeys(str(i) for i in ids if i and str(i) != keep_id))
        # the duplicate's messages too: a re-harvest of one must resolve to keep, not the dropped
        msgs = [*(keep.get("msg_digests") or []), *(item.get("msg_digests") or [])]
        keep["msg_digests"] = list(dict.fromkeys(str(d) for d in msgs if d))
        _write_item(repo, keep)
        note = f"duplicate of {keep_id}" + (f" — {why}" if why else "")
        item.update(status="dropped", note=note)
        try:
            path = _close(repo, item, session=session, note=note)
        except BaseException:
            # all or nothing: _close raises only when nothing was committed, so the duplicate is
            # still awaiting and keep must not claim it. The status re-read is a guard: should the
            # duplicate read `dropped` after all, keep's record of it is the truth and stays
            with contextlib.suppress(Exception):
                if _read_item(repo, item_id).get("status") != "dropped":
                    _write_item(repo, pre_image)
            raise
        _after_write(repo, session)
    print(_rel(repo, path))
    return 0


def cmd_drop(repo: Path, args: argparse.Namespace) -> int:
    _require_store(repo)
    _read_item(repo, args.id)
    why = " ".join((args.why or "").split())
    keep_id = (args.duplicate_of or "").strip()
    if keep_id:
        return _drop_duplicate(repo, args, keep_id, why)
    if not why:
        raise WorkError(f"drop {args.id} needs --why <reason>; the reason is kept in `note`")
    session = _call_session(args)
    with _store_lock(repo, CLI_LOCK_TIMEOUT_S, fail_open=False, label="drop"):
        item = _read_item(repo, args.id)
        _refuse_closed(repo, item, "drop")
        owner = str(item.get("owner") or "")
        distributor = str(_read_config(repo).get("distributor") or "").strip()
        agent = _agent_name()
        if owner and agent not in {owner, distributor} - {""}:
            raise WorkError(
                f"drop {args.id} is the owner's ({owner}) or the distributor's "
                f"({distributor or 'none named'}); this caller is {_actor_label()}"
            )
        _fence(repo, args.id, session, "drop")
        item.update(status="dropped", note=why)
        path = _close(repo, item, session=session, note=why)
        _after_write(repo, session)
    print(_rel(repo, path))
    return 0


def cmd_answer(repo: Path, args: argparse.Namespace) -> int:
    _require_store(repo)
    _read_item(repo, args.id)
    note = " ".join((args.note or "").split())
    if not note:
        raise WorkError(f"answer {args.id} needs --note <the operator's words>")
    decision = (args.decision or "").strip()
    if decision and not _DECISION_ID_RE.fullmatch(decision):
        raise WorkError(
            f"--decision {decision!r} is not a ledger id (D-NNN); mint the row first — "
            "work.py never writes docs/DECISIONS.md"
        )
    session = _call_session(args)
    with _store_lock(repo, CLI_LOCK_TIMEOUT_S, fail_open=False, label="answer"):
        item = _read_item(repo, args.id)
        if item.get("status") != "awaiting-operator":
            raise WorkError(
                f"answer closes only an awaiting-operator item; {args.id} is "
                f"{item.get('status')} (use done or drop)"
            )
        if item.get("kind") != "decision":
            # only the decision harvest sets awaiting-operator; drift class 6 exempts an answered
            # item by kind, so an answer on any other kind would read as unevidenced drift
            raise WorkError(
                f"answer closes only a decision item; {args.id} is kind {item.get('kind')!r} "
                "(use done with evidence, or drop)"
            )
        if args.id in _closed_ids(repo):
            raise WorkError(f"answer {args.id} refused: it was already closed in another tree")
        _fence(repo, args.id, session, "answer")
        links = dict(item.get("links") or {})
        if decision:
            links["decision"] = decision
        item.update(status="done", note=note, links=links)
        path = _close(repo, item, session=session, note=note, decision=decision)
        _after_write(repo, session)
    print(_rel(repo, path))
    return 0


CLAIMS_FLAG_OVER = 5  # a session holding more live claims than this is flagged
STALE_NEXT_DAYS = 6  # the Stop harvest closes a next item at 7 days; status warns a day before
AGED_MAIL_DAYS = 14
AGED_MAIL_FLAG_OVER = 50


NO_SESSION = "(no session)"


def _session_label(session: str) -> str:
    return session[:8] if session else NO_SESSION


def _distributor_lines(
    items: list[dict], closed: set[str], claims: dict[str, dict], *, now: float | None = None
) -> list[str]:
    """``status``'s lines for the distributor (spec D4): unowned open items, live claims per
    session, stale ``next`` items, aged open mail items — every item count over ``status ==
    "open"`` items only. A claim with no session is grouped by its agent (one line each), and an
    empty session prints ``(no session)``, never a blank column. COBRA (D-253): the claims flag
    is dodged by spreading claims across sessions, and the unowned count by assigning everything
    to one name — both show up here as the lines they create, never as a hidden score."""
    now = time.time() if now is None else now
    open_items = [it for it in items if it.get("status") == "open" and it["id"] not in closed]
    unowned = sum(1 for it in open_items if not it.get("owner") and it.get("kind") != "next")
    lines = [f"{'UNOWNED':<17}{unowned} open item(s) with no owner"]
    groups: dict[tuple[str, str], list[dict]] = {}
    for claim in claims.values():
        session = str(claim.get("session") or "")
        agent_key = "" if session else str(claim.get("agent") or "")
        groups.setdefault((session, agent_key), []).append(claim)
    for (session, _agent), held in sorted(groups.items()):
        agents = sorted({str(c.get("agent") or "") for c in held} - {""})
        flag = f" — over {CLAIMS_FLAG_OVER}" if len(held) > CLAIMS_FLAG_OVER else ""
        who = ",".join(agents) or "unnamed"
        lines.append(f"{'CLAIMS':<17}{_session_label(session)} ({who}) {len(held)}{flag}")
    for it in sorted(open_items, key=lambda it: str(it["id"])):
        if it.get("kind") != "next":
            continue
        set_at = _parse_iso(str(it.get("next_at") or ""))
        if set_at is None:
            continue
        age = now - set_at.timestamp()
        if age > STALE_NEXT_DAYS * 86400:
            session = str(_links(it).get("session") or "")
            lines.append(
                f"{'STALE NEXT':<17}{it['id']} {_session_label(session)} "
                f"set {int(age // 86400)} d ago"
            )
    aged = 0
    for it in open_items:
        if it.get("kind") != "mail":
            continue
        created = _parse_iso(str(it.get("created") or ""))
        if created is not None and now - created.timestamp() > AGED_MAIL_DAYS * 86400:
            aged += 1
    if aged:
        flag = f" — over {AGED_MAIL_FLAG_OVER}" if aged > AGED_MAIL_FLAG_OVER else ""
        lines.append(
            f"{'AGED MAIL':<17}{aged} open mail item(s) created more than "
            f"{AGED_MAIL_DAYS} days ago{flag}"
        )
    return lines


def _is_linked_worktree(repo: Path) -> bool:
    """True when ``repo`` is a linked worktree (its git dir is not the common dir)."""
    git_dir = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-dir")).resolve()
    return git_dir != _common_dir(repo)


_GIT_ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")


def _commit_store_files(repo: Path, paths: list[str], context: str) -> str:
    """Commit exactly ``paths`` (their WORKING-TREE content) on the current branch and return the
    commit's sha. Built with ``git commit --only``: git holds ``index.lock`` across the tree, the
    ref move and the index update, so a sibling's bare ``git commit`` can neither interleave nor
    ship a stale index entry for these paths, and another session's STAGED files stay staged and
    out of this commit. Untracked paths get an intent-to-add entry first (undone on failure).
    Hooks are skipped (``core.hooksPath=/dev/null``, ``--no-verify``): item JSON triggers no
    check and no sync. A refused commit (index lock held, HEAD moved) raises — nothing landed."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_ENV_DROP}
    agent = _agent_name()
    message = "\n".join(
        [
            f"chore(work): commit {len(paths)} work-item file(s) from the main store",
            "",
            "Agent-Role: primary",
            *([f"Agent-Name: {agent}"] if agent else []),
            f"Agent-Context: {context}",
        ]
    )

    def git(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            input=stdin,
            env=env,
            timeout=_git_timeout(),
        )

    tracked = set(git("ls-files", "--", *paths).stdout.split())
    new = [p for p in paths if p not in tracked]
    if new:
        added = git("add", "-N", "--", *new)
        if added.returncode != 0:
            raise WorkError(f"git add -N failed: {added.stderr.strip()[:200]} — nothing committed")
    done = git(
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "--no-verify",
        "--only",
        "-F",
        "-",
        "--",
        *paths,
        stdin=message + "\n",
    )
    if done.returncode != 0:
        if new:
            git("reset", "-q", "--", *new)  # best effort: drop the intent-to-add entries
        raise WorkError(f"git commit failed: {done.stderr.strip()[:300]} — nothing committed")
    m = re.search(r"^\[[^\]\s]+ (?:\(root-commit\) )?([0-9a-f]{7,40})\]", done.stdout, re.M)
    if not m:
        raise WorkError(f"commit landed but its sha was not printed: {done.stdout[:200]}")
    sha = _git(repo, "rev-parse", m.group(1))
    landed = set(_git(repo, "show", "--name-only", "--format=", sha).splitlines())
    if landed != set(paths):
        raise WorkError(f"{sha[:9]} holds {sorted(landed ^ set(paths))} beyond/short of the list")
    return sha


def _valid_item_file(repo: Path, rel: str) -> bool:
    """True when ``rel`` holds a JSON object whose ``id`` is the file's own stem."""
    try:
        data = json.loads((repo / rel).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("id") == Path(rel).stem


def _store_commit_plan(repo: Path) -> tuple[list[str], list[str], list[str], list[str]]:
    """(committable, staged by another session, deleted, not a valid item) among the store's
    uncommitted item files. "Staged" reads the index against HEAD, so an intent-to-add entry
    counts too. A deleted item file is never committed here: no verb deletes one, so a deletion is
    a hand edit for its author to commit (or restore) — never read as "invalid"."""
    pending = _uncommitted_items(repo)
    try:
        staged = set(
            _git(
                repo, "diff-index", "--cached", "--name-only", "HEAD", "--", STORE_REL.as_posix()
            ).splitlines()
        )
    except WorkError:
        staged = set()
    held = [p for p in pending if p in staged]
    rest = [p for p in pending if p not in staged]
    deleted = [p for p in rest if not (repo / p).exists()]
    invalid = [p for p in rest if p not in deleted and not _valid_item_file(repo, p)]
    files = [p for p in rest if p not in deleted and p not in invalid]
    return files, held, deleted, invalid


def _store_refusal(repo: Path) -> str | None:
    """Why the store cannot be committed in this checkout's state, or None (the caller-side
    checks live in `_commit_refusal`)."""
    if _is_linked_worktree(repo):
        return "this is a linked worktree; the main checkout's session commits the main store"
    try:
        _git(repo, "symbolic-ref", "--short", "-q", "HEAD")
    except WorkError:
        return "HEAD is detached; check out a branch first"
    git_dir = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-dir"))
    for head in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
        if (git_dir / head).exists():
            op = head.split("_HEAD")[0].lower().replace("_", "-")
            return f"a {op} is in progress; finish it first"
    if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
        return "a rebase is in progress; finish it first"
    return None


def _commit_refusal(repo: Path) -> str | None:
    """Why ``commit-items`` must not run here, or None: the store's own state, then the caller —
    a session must run it from inside the main checkout, never name it with ``--repo``."""
    why = _store_refusal(repo)
    if why:
        return why
    try:
        caller = _repo_root(Path.cwd())
    except WorkError:
        caller = None
    if caller != repo:
        return f"run it from inside the main checkout ({repo}), not from {Path.cwd()}"
    return None


def cmd_commit_items(repo: Path, args: argparse.Namespace) -> int:
    """Commit every uncommitted, valid, unstaged item file of THIS main checkout's store in one
    commit (W-4238b6ec). The store lock is held only while the list is taken — the commit itself
    runs outside it, so hook writers (2 s fail-open waits) are never starved; a file a verb
    rewrites after the listing is committed in its newer, equally complete state."""
    why = _commit_refusal(repo)
    if why:
        print(f"work.py commit-items: refused — {why}.", file=sys.stderr)
        return 2
    for attempt in (1, 2):
        with _store_lock(repo, CLI_LOCK_TIMEOUT_S, fail_open=False, label="commit-items"):
            files, held, deleted, invalid = _store_commit_plan(repo)
        if not files:
            print("work.py commit-items: nothing to commit")
            break
        try:
            sha = _commit_store_files(
                repo, files, f"work.py commit-items: {len(files)} item file(s) from the main store"
            )
        except WorkError as exc:
            if attempt == 2:
                print(f"work.py commit-items: {exc}", file=sys.stderr)
                return 1
            continue  # a sibling held the index or moved HEAD: re-list against the new state
        branch = _git(repo, "symbolic-ref", "--short", "-q", "HEAD")
        print(f"[{branch} {sha[:9]}] committed {len(files)} item file(s) — push it: git push")
        break
    # a race may have committed them since the listing — but only a listing that SUCCEEDED may
    # drop a line: a git failure here must never read as an all-clear (round 2, A-S6)
    fresh = _uncommitted_items_strict(repo)
    still = set(fresh) if fresh is not None else set(held) | set(deleted) | set(invalid)
    for rel in (r for r in held if r in still):
        print(f"skipped (staged by another session): {rel}")
    for rel in (r for r in deleted if r in still):
        print(f"skipped (deleted — this verb commits no deletion; restore it or commit it): {rel}")
    for rel in (r for r in invalid if r in still):
        print(f"skipped (not a valid item file): {rel}")
    return 0


def cmd_status(repo: Path, args: argparse.Namespace) -> int:
    """The obligation lines and the distributor's lines (spec D1, D4), items by state,
    uncommitted item files (a listing, never a drift class), and the eight derived spec/plan
    drift classes — read-only, no lock."""
    _require_store(repo)
    claims = _live_claims(repo)
    items = list(_iter_items(repo))
    for line in obligations(repo):
        print(line)
    for line in _distributor_lines(items, _closed_ids(repo), claims):
        print(line)
    for item in sorted(items, key=lambda it: (str(it.get("status")), _priority(it), str(it["id"]))):
        tag = " (claimed)" if item["id"] in claims and item.get("status") not in RESOLVED else ""
        print(f"{item.get('status', ''):<17}{_line(item)}{tag}")
    for rel in _uncommitted_items(repo):
        print(f"UNCOMMITTED      {rel}")
    board_fn = _board_states_fn(repo)
    for spine in _iter_plan_spines(repo):
        try:
            text = spine.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        states = board_fn(text)
        if states:
            done = sum(1 for v in states.values() if v.strip() == "✅")
            print(f"PLAN             {_rel(repo, spine)}  tickets {done}/{len(states)} done")
    report = _drift_report(repo)
    for cls in range(1, 9):
        label = "blocking" if cls in BLOCKING_CLASSES else "advisory"
        for rel in report[cls]:
            print(f"DRIFT {cls} ({label})  {rel}")
    return 0


def cmd_sync(repo: Path, args: argparse.Namespace) -> int:
    """``sync --check``: print the drift, append one reading, and exit non-zero on classes 2-6
    only once the repo is past its migration window — never in a repo without a store, which
    prints one line, exits 0 and creates nothing."""
    if not _has_store(repo):
        print(f"no work store in {repo} — nothing to sync")
        return 0
    report = _drift_report(repo)
    for cls in range(1, 9):
        label = "blocking" if cls in BLOCKING_CLASSES else "advisory"
        for rel in report[cls]:
            print(f"DRIFT {cls} ({label})  {rel}")
    blocking_active = _sync_blocking_active(repo)
    _append_reading(
        repo,
        {
            "at": _now_iso(),
            "blocking_active": blocking_active,
            "counts": {str(n): len(report[n]) for n in range(1, 9)},
            "kind": "sync",
        },
    )
    if blocking_active and any(report[cls] for cls in BLOCKING_CLASSES):
        return 1
    return 0


# ── the hook-facing API (imported by path by scripts/thread_anchor.py) ──────────────────────
#
# Every function but repo_root checks has_store FIRST and returns its empty value (False / None /
# "") before touching the lock, the readings or the git common dir, so a store-less repo gets
# nothing created anywhere. Every function is fail-open: its empty value on a lock timeout or any
# exception (one stderr line). A write takes the store lock ONCE, for at most ``lock_timeout``.


def repo_root(path: Path | str) -> Path | None:
    """``git rev-parse --show-toplevel`` of ``path``, resolved; None outside a git repo."""
    with _hook_git_budget():
        try:
            return _repo_root(path)
        except Exception:
            return None


def has_store(repo: Path | str) -> bool:
    with _hook_git_budget():
        try:
            root = repo_root(repo)
            return root is not None and _has_store(root)
        except Exception:
            return False


def _api_root(repo: Path | str) -> Path | None:
    root = repo_root(repo)
    return root if root is not None and _has_store(root) else None


def _block_digest(block: str) -> str:
    return hashlib.sha256(block.strip().encode("utf-8", "replace")).hexdigest()


def _decision_index(repo: Path) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """One parse of every item file (P3, T04 review's confirmed defect): ``msg_digest`` ->
    the item that already carries it, and ``block_digest`` -> every OPEN awaiting item carrying
    it. Built ONCE per ``ensure_decision_items`` call (or ``on_harvest``'s single entry) and
    updated IN MEMORY by ``_ensure_decision_locked`` after every write, so a later entry in the
    same call sees what an earlier one just created or extended without a second disk read.
    Re-parsing the whole store per entry cost slots x items under the store lock — measured at
    6.1-6.8 s for 50 rescued slots over 5000 items (0.19 s baseline), blowing thread_anchor's 3 s
    prompt deadline and silently dropping every awaiting line from the prompt."""
    by_msg: dict[str, dict] = {}
    by_block: dict[str, list[dict]] = {}
    for it in _iter_items(repo):
        for d in it.get("msg_digests") or []:
            held = by_msg.get(str(d))
            # first holder wins (an answered item still guards its echo), except that a
            # `dropped` holder yields to a live one — the item a duplicate was retired into
            if held is None or (held.get("status") == "dropped" and it.get("status") != "dropped"):
                by_msg[str(d)] = it
        if it.get("status") == "awaiting-operator":  # its own wording and every retired one
            wordings = [it.get("block_digest"), *(it.get("alt_block_digests") or [])]
            for bd in dict.fromkeys(str(d) for d in wordings if d):
                by_block.setdefault(bd, []).append(it)
    return by_msg, by_block


def _ensure_decision_locked(
    repo: Path,
    block: str,
    msg_digest: str,
    session: str,
    *,
    by_msg: dict[str, dict],
    by_block: dict[str, list[dict]],
    closed: set[str] | None,
    own: bool = True,
) -> tuple[str, set[str] | None]:
    """The three rules (caller holds the store lock), against the shared indexes
    ``_decision_index`` built ONCE for the whole call (P3): a known message digest → that item; an
    OPEN awaiting item with this block digest → add the digest; else → a new awaiting decision
    item. ``by_msg``/``by_block`` are updated in place so a LATER entry of the same call sees this
    one's write. ``closed`` is ``_closed_ids(repo)``, read at most once per call and only when
    first needed — returned back so the caller passes the SAME set into the next entry."""
    existing = by_msg.get(msg_digest)
    if existing is not None:
        return str(existing["id"]), closed
    bd = _block_digest(block)
    same = by_block.get(bd, [])
    if same:
        if closed is None:
            closed = _closed_ids(repo)
        for it in same:
            if it["id"] not in closed:
                it["msg_digests"] = [*(it.get("msg_digests") or []), msg_digest]
                _write_item(repo, it)
                by_msg[msg_digest] = it
                return str(it["id"]), closed
    qm = _QUESTION_RE.search(block)
    question = " ".join((qm.group(1) if qm else "").strip(" *_").split())
    gm = _GROUND_RE.search(block)
    first = block.strip().splitlines()[0] if block.strip() else ""
    title = question or " ".join(first.split())
    item = _new_item(
        kind="decision",
        title=title or "DECISION block",
        next_action="",
        links={},
        priority=DEFAULT_PRIORITY,
    )
    item.update(
        block_digest=bd,
        # a slot rescued for ANOTHER session keeps that session as its creator, never the
        # rescuing process's agent name (D7 W4-O6)
        creator=(_agent_name() or session) if own else session,
        ground=gm.group(1).lower() if gm else "",
        msg_digests=[msg_digest],
        question=question,
        status="awaiting-operator",
    )
    _create_item(repo, item)
    by_msg[msg_digest] = item
    by_block.setdefault(bd, []).append(item)
    return str(item["id"]), closed


def ensure_decision_item(
    repo: Path | str,
    *,
    block: str,
    msg_digest: str,
    session: str,
    lock_timeout: float = HOOK_LOCK_TIMEOUT_S,
) -> str | None:
    """The DECISION block's item id (found, refreshed or created), or None."""
    with _hook_git_budget():
        got = ensure_decision_items(repo, [(block, msg_digest, session)], lock_timeout=lock_timeout)
        return got[0] if got else None


def ensure_decision_items(
    repo: Path | str,
    entries: list[tuple[str, str, str]],
    *,
    lock_timeout: float = HOOK_LOCK_TIMEOUT_S,
    own_session: str | None = None,
) -> list[str] | None:
    """``ensure_decision_item`` for every ``(block, msg_digest, session)`` under ONE lock: the ids
    of the entries that succeeded (an entry that raises is skipped with one stderr line); None
    only when the store is absent or the lock was not taken.
    ``own_session`` names the caller's own session: an entry for any OTHER session keeps that
    session as the new item's creator (None: every entry is the caller's own, as before).

    P1 (T04 review): renews NO claims. An entry's ``session`` is whoever's DECISION slot this
    call is refreshing or creating an item for — T04's second chance can pass ANOTHER (possibly
    dead) session's id to rescue its slot, and renewing that session's claims here would extend a
    dead session's lease to a full ``DEFAULT_LEASE_S``, defeating read-time expiry. Only
    ``on_harvest`` renews a claim, and only the harvester's own session. Markers still prune.

    P3 (T04 review): the store is parsed ONCE for the whole call (``_decision_index``), never once
    per entry — ``_ensure_decision_locked`` updates the shared indexes in memory after every write
    so a later entry sees what an earlier one just created or extended."""
    with _hook_git_budget():
        try:
            root = _api_root(repo)
            if root is None:
                return None
            with _store_lock(root, lock_timeout, fail_open=True, label="decision") as held:
                if not held:
                    return None
                by_msg, by_block = _decision_index(root)
                closed: set[str] | None = None
                ids = []
                for b, d, s in entries:
                    try:  # one bad entry never costs the others their item
                        item_id, closed = _ensure_decision_locked(
                            root,
                            b,
                            d,
                            s,
                            by_msg=by_msg,
                            by_block=by_block,
                            closed=closed,
                            own=own_session is None or s == own_session,
                        )
                        ids.append(item_id)
                    except Exception as exc:
                        _warn(f"decision item not written — {type(exc).__name__}: {exc}")
                _after_write(root)  # no *sessions — never renew a passed session's claim
                return ids
        except Exception as exc:
            _warn(f"decision item not written — {type(exc).__name__}: {exc}")
            return None


NEXT_IDLE_S = 7 * 86400  # the Stop harvest closes a ``next`` item this long after its next_at
HOOK_NO_SESSION = "nosession"  # the Stop hook's id for a payload without one: never a claimant
# a leading markdown run (`**none**`, `- none`, `(none)`) is still the word; the Stop hook's
# own none-matcher accepts a leading `[ \t*_]` run the same way
_HOLD_LEAD_RE = re.compile(r"[\s*_`(\-]*(?:none|BLOCKED)(?![0-9A-Za-z])", re.I)  # `_none_`
_HOLD_ANY_RE = re.compile(r"(?<![0-9A-Za-z_])operator[\s-]+decisions?(?![0-9A-Za-z_])", re.I)
# an id a NEXT names is judged by its whitespace TOKEN: `_next_refs`. `_ITEM_REF_RE` stays the
# evidence reader's.
_NEXT_TOKEN_ID_RE = re.compile(r"W-[0-9a-f]{8}(?![0-9A-Za-z_])(?!\.[0-9A-Za-z])")
_NEXT_OPENERS = "*`([{<\"'_—–"  # decoration before an id; never `#`, `=`, `?` (a URL's)


def _next_refs(text: str) -> list[str]:
    """The ids a NEXT names, in order: a token counts only when it holds no ``/`` (a path or URL)
    and — once its leading decoration (``_NEXT_OPENERS``) is stripped — STARTS with the id, not followed by
    ``.`` plus an alphanumeric (a file extension). Trailing decoration (``**``, ``)``, ``,``,
    ``:``, ``;``, ``.``, ``!``, ``?``) needs no strip: the match is anchored at the id and its
    lookaheads read only the next characters. So ``?item=W-…``, ``#W-…``, ``x/W-…`` and
    ``W-….json`` name nothing; ``**W-…**``, ``W-…:`` and ``W-….`` do."""
    refs = []
    for token in text.split():
        if "/" in token:
            continue
        m = _NEXT_TOKEN_ID_RE.match(token.lstrip(_NEXT_OPENERS))
        if m:
            refs.append(m.group(0))
    return refs


def classify_next(v: str) -> str:
    """One NEXT value's class, shared by the harvest and the census (T06 loads it by path):
    ``"hold"`` when it STARTS (after any markdown run) with the word ``none`` or ``BLOCKED``, or
    carries ``operator decision(s)`` / ``operator-decision`` ANYWHERE (whole words, any case) —
    a hold whatever else the line names; ``"names-item"`` when it names a ``W-`` id outside a
    path or URL; else ``"free-text"``. Pure."""
    text = " ".join(v.split())
    if _HOLD_LEAD_RE.match(text) or _HOLD_ANY_RE.search(text):
        return "hold"
    if _next_refs(text):
        return "names-item"
    return "free-text"


def _session_next_items(repo: Path, session: str, closed: set[str]) -> list[dict]:
    """The session's open ``kind: next`` items not closed in another tree (``closed``) — one by
    construction; a hand-made twin is listed."""
    return [
        it
        for it in _iter_items(repo)
        if it.get("kind") == "next"
        and it.get("status") == "open"
        and it["id"] not in closed
        and _links(it).get("session") == session
    ]


def _close_next(repo: Path, item: dict, session: str, note: str) -> None:
    item.update(status="dropped", note=note)
    _close(repo, item, session=session, note=note)


def _supersede_next(repo: Path, session: str, closed: set[str]) -> None:
    """Rules 1 and 2's tail: the session's open ``next`` item closes ``dropped`` ``superseded``."""
    for item in _session_next_items(repo, session, closed):
        try:
            _close_next(repo, item, session, "superseded")
        except Exception as exc:
            _warn(f"next item {item.get('id')} not closed — {type(exc).__name__}: {exc}")


def _claim_named(repo: Path, v: str, session: str, closed: set[str]) -> None:
    """Rule 2: the FIRST named id that is open, ready, not a ``next`` item and not held live by
    another session gets ``claim``'s own write (``_claim_record``, the agent resolved for
    ``session``) and nothing else: the item file is never written, because its ``next`` is the
    item's own authored next action (a migrated item's whole body lives there) and the session's
    NEXT line is already kept by the thread-anchor register. When none qualifies nothing is."""
    by_id = {str(it["id"]): it for it in _iter_items(repo)}
    now = time.time()
    for ref in _next_refs(v):
        item = by_id.get(ref)
        if item is None or item.get("kind") == "next" or not _is_ready(item, by_id, closed):
            continue
        taken = _claim_record(
            _claim_of(repo, ref), session, now, agent=_agent_name(session=session)
        )
        if taken is None:  # another session's live claim: its item stays byte-identical
            continue
        _write_claim(repo, ref, taken[0])
        return


def _keep_next(repo: Path, v: str, session: str, closed: set[str]) -> None:
    """Rule 3: the session's one open ``next`` item carries ``v`` as its title and ``next`` —
    rewritten only when the text differs (a repeated harvest writes nothing), created when the
    session has none."""
    text = v[:LINE_MAX]
    mine = _session_next_items(repo, session, closed)
    if mine:
        item = mine[0]
        if item.get("next") != text:
            item.update(title=text, next=text, next_at=_now_iso())
            _write_item(repo, item)
        return
    item = _new_item(
        kind="next",
        title=text,
        next_action=text,
        links={"session": session},
        priority=DEFAULT_PRIORITY,
    )
    item.update(creator=session, owner=_agent_name(session=session), next_at=item["created"])
    _create_item(repo, item)


def _apply_next_rules(repo: Path, next_text: str, session: str, anchored: bool) -> None:
    """Spec D3, the first match decides: a hold (1) closes the session's ``next`` item; a line
    naming an item (2) claims the first qualifying id, then closes it too; free text the register
    accepted (3) becomes the session's ``next`` item; anything else (4) is nothing. A session
    that cannot hold a claim ("" or ``nosession``) is never acted for."""
    v = " ".join(next_text.split())
    if not v or not session or session == HOOK_NO_SESSION:
        return
    cls = classify_next(v)
    if cls == "free-text":
        if anchored:
            _keep_next(repo, v, session, _closed_ids(repo))
        return
    closed = _closed_ids(repo)
    if cls == "names-item":
        try:
            _claim_named(repo, v, session, closed)
        except Exception as exc:  # the supersede below still runs
            _warn(f"named item not claimed — {type(exc).__name__}: {exc}")
    _supersede_next(repo, session, closed)


def _close_idle_next(repo: Path, session: str) -> None:
    """Every open ``next`` item — not already closed in another tree — whose ``next_at`` (else
    ``created``) is over 7 days old closes ``dropped`` ``idle 7 days``, whichever session
    harvests. Each item is judged alone: one that cannot be judged or closed is one stderr line,
    never a stop for the rest."""
    now = time.time()
    closed = _closed_ids(repo)
    for item in _iter_items(repo):
        try:
            if item.get("kind") != "next" or item.get("status") != "open" or item["id"] in closed:
                continue
            at = _parse_iso(str(item.get("next_at") or "")) or _parse_iso(
                str(item.get("created") or "")
            )
            if at is None:
                _warn(f"next item {item.get('id')} skipped — no readable next_at or created")
                continue
            if now - at.timestamp() > NEXT_IDLE_S:
                _close_next(repo, item, session, "idle 7 days")
        except Exception as exc:
            _warn(f"next item {item.get('id')} not judged — {type(exc).__name__}: {exc}")


def on_harvest(
    repo: Path | str,
    *,
    session: str,
    block: str | None = None,
    msg_digest: str | None = None,
    next_text: str | None = None,
    next_anchored: bool = False,
    lock_timeout: float = HOOK_LOCK_TIMEOUT_S,
) -> str | None:
    """The Stop harvest's ONE store call, under ONE lock: (1) the decision item, first — the write
    that must not be lost; (2) the NEXT rules (spec D3, ``_apply_next_rules``) — ``next_anchored``
    says the register accepted the NEXT, and only then does free text become the session's
    ``next`` item; a caller that omits it still gets rules 1 and 2, so a NEXT naming an open
    unclaimed item CLAIMS it; (3) the 7-day close of idle ``next`` items; (4) renew ``session``'s
    live claims, the marker prune last. Steps 2 and 3 each fail open with one stderr line.
    Returns the decision item's id, else None."""
    with _hook_git_budget():
        try:
            root = _api_root(repo)
            if root is None:
                return None
            with _store_lock(root, lock_timeout, fail_open=True, label="harvest") as held:
                if not held:
                    return None
                decision = None
                if block and msg_digest:
                    try:  # a failure returns None (T04's second chance) but still renews claims
                        by_msg, by_block = _decision_index(root)
                        decision, _closed = _ensure_decision_locked(
                            root,
                            block,
                            msg_digest,
                            session,
                            by_msg=by_msg,
                            by_block=by_block,
                            closed=None,
                        )
                    except Exception as exc:
                        _warn(f"decision item not written — {type(exc).__name__}: {exc}")
                if next_text:
                    try:
                        _apply_next_rules(root, next_text, session, next_anchored)
                    except Exception as exc:
                        _warn(f"NEXT rules not applied — {type(exc).__name__}: {exc}")
                try:
                    _close_idle_next(root, session)
                except Exception as exc:
                    _warn(f"idle next items not closed — {type(exc).__name__}: {exc}")
                _after_write(root, session)  # only the harvester's OWN session ever renews here
                return decision
        except Exception as exc:
            _warn(f"harvest not written — {type(exc).__name__}: {exc}")
            return None


def _check_linked(kind: str, link: tuple[str, str]) -> tuple[str, str]:
    """A programming error in a linked-item call is RAISED, before the lock — never failed open."""
    if kind not in LINKED_KINDS:
        raise ValueError(f"kind {kind!r}: a linked item is one of {'|'.join(LINKED_KINDS)}")
    key, value = link
    value = str(value).strip()
    if key not in EXTRA_LINK_KEYS or not value:
        raise ValueError(f"link {link!r}: expected ({'|'.join(EXTRA_LINK_KEYS)}, <value>)")
    return key, value


def _linked_items(repo: Path, kind: str, key: str, value: str) -> list[dict]:
    """Every OPEN item of ``kind`` whose ``links[key]`` is ``value``, not closed in another tree,
    in id order (``_iter_items``'s)."""
    found = [
        it
        for it in _iter_items(repo)
        if it.get("kind") == kind
        and it.get("status") not in RESOLVED
        and (it.get("links") or {}).get(key) == value
    ]
    if not found:
        return []
    closed = _closed_ids(repo)
    return [it for it in found if it["id"] not in closed]


def open_linked(
    repo: Path | str,
    *,
    kind: str,
    link: tuple[str, str],
    title: str,
    session: str,
    lock_timeout: float = HOOK_LOCK_TIMEOUT_S,
) -> str | None:
    """Taking an obligation (spec D2), under ONE lock: the open ``kind`` item linked by ``link``
    (found, else created — owned by this agent's name, or unassigned), then, when ``session`` is
    given, ``claim``'s rule for it: a live claim of ANOTHER session is left alone, the caller's
    own is renewed, otherwise a new claim with the old token + 1. The item id, or None."""
    key, value = _check_linked(kind, link)
    with _hook_git_budget():
        try:
            root = _api_root(repo)
            if root is None:
                return None
            with _store_lock(root, lock_timeout, fail_open=True, label="linked") as held:
                if not held:
                    return None
                found = _linked_items(root, kind, key, value)
                item = found[0] if found else None
                if item is None:
                    item = _new_item(
                        kind=kind,
                        title=" ".join(str(title).split()) or f"{kind} {value}",
                        next_action="",
                        links={key: value},
                        priority=DEFAULT_PRIORITY,
                    )
                    item["owner"] = _agent_name()
                    _create_item(root, item)
                item_id = str(item["id"])
                if session:
                    taken = _claim_record(_claim_of(root, item_id), session, time.time())
                    if taken is not None:
                        _write_claim(root, item_id, taken[0])
                _after_write(root, session)
                return item_id
        except Exception as exc:
            _warn(f"{kind} item not written — {type(exc).__name__}: {exc}")
            return None


def close_linked(
    repo: Path | str,
    *,
    kind: str,
    link: tuple[str, str],
    status: str,
    note: str,
    lock_timeout: float = HOOK_LOCK_TIMEOUT_S,
) -> str | None:
    """Closing an obligation (spec D2), under ONE lock: EVERY open ``kind`` item linked by
    ``link`` closes ``status`` (done | dropped) with ``note`` — for each, the marker, the item,
    then its claim ended — and the first one's id is returned. No such item: None and nothing
    written (an ack with no prior claim creates nothing)."""
    key, value = _check_linked(kind, link)
    if status not in RESOLVED:
        raise ValueError(f"status {status!r}: a linked close is one of {'|'.join(RESOLVED)}")
    with _hook_git_budget():
        try:
            root = _api_root(repo)
            if root is None:
                return None
            with _store_lock(root, lock_timeout, fail_open=True, label="linked") as held:
                if not held:
                    return None
                found = _linked_items(root, kind, key, value)
                if not found:
                    return None
                text = " ".join(str(note).split())
                done: list[str] = []
                for item in found:  # every open item of the link; one failure skips only itself
                    try:
                        item.update(status=status, note=text)
                        _close(root, item, session="", note=text)
                        done.append(str(item["id"]))
                    except Exception as exc:
                        _warn(f"{kind} item {item['id']} not closed — {type(exc).__name__}: {exc}")
                _after_write(root)
                return done[0] if done else None
        except Exception as exc:
            _warn(f"{kind} item not closed — {type(exc).__name__}: {exc}")
            return None


def has_msg_digest(repo: Path | str, msg_digest: str) -> bool:
    with _hook_git_budget():
        try:
            root = _api_root(repo)
            if root is None:
                return False
            return any(msg_digest in (it.get("msg_digests") or []) for it in _iter_items(root))
        except Exception:
            return False


def _clip(line: str) -> str:
    return line if len(line) <= LINE_MAX else line[: LINE_MAX - 1] + "…"


UNNAMED_WINDOW_LINE = (
    "work: this window has no agent name — owned items cannot reach it; "
    "run python3 scripts/whoami_agent.py --as <name>"
)


def _claim_session(claim: dict) -> str:
    return str(claim.get("session") or "")


def _fit_ids(head: str, ids: list[str]) -> str:
    """``head`` + the ids; when they overflow LINE_MAX, as many WHOLE ids as fit and ``… and <n>
    more`` — an id is never cut and the missing count is said. Only a head that alone overflows
    LINE_MAX (one session's claims under dozens of agent names) loses both: ``_clip`` cuts it."""
    line = head + ", ".join(ids)
    if len(line) <= LINE_MAX:
        return line
    for shown in range(len(ids) - 1, -1, -1):
        line = f"{head}{', '.join(ids[:shown])} … and {len(ids) - shown} more"
        if len(line) <= LINE_MAX:
            return line
    return line  # a head alone over LINE_MAX: _clip cuts it, as any other line


def _on_it_lines(claims: dict[str, dict], session: str) -> list[str]:
    """One ``on it:`` line per OTHER session holding live claims (spec D4), so every OTHER
    session's live claim appears here once (the caller's own beyond ``PROMPT_CLAIM_LINES`` are its
    count line). A live claim always has a session
    (``_is_live``), so the line is keyed by it alone."""
    groups: dict[str, list[tuple[str, dict]]] = {}
    for item_id, claim in claims.items():
        claim_session = _claim_session(claim)
        if session and claim_session == session:
            continue  # the caller's own: its ``your claim`` line
        groups.setdefault(claim_session, []).append((item_id, claim))
    lines = []
    for claim_session, held in sorted(groups.items()):
        agents = sorted({str(c.get("agent") or "") for _i, c in held} - {""})
        who = ",".join(agents) or "unnamed"
        head = f"work: on it: {claim_session[:8]} ({who}) — "
        lines.append(_fit_ids(head, sorted(i for i, _c in held)))
    return lines


PROMPT_CLAIM_LINES = 3  # this session's claims named per prompt; the rest are one count line


def prompt_block(repo: Path | str, session: str) -> str:
    """Read-only, no lock, the caller's own tree, in order: the unnamed-window line (spec D6), the
    obligation lines (D1), every awaiting-operator item with its question, ``session``'s live
    claims (the first ``PROMPT_CLAIM_LINES`` by priority, then a count line, then one line naming any
    claim on an item not in this tree), one ``on it:`` line per other session's live claims (D4), and the ready count — or ""
    when all of them are empty. A store-less repo is "" whatever the window's name."""
    with _hook_git_budget():
        try:
            root = _api_root(repo)
            if root is None:
                return ""
            items = list(_iter_items(root))
            closed = _closed_ids(root)
            claims = _live_claims(root)
            by_id = {str(it["id"]): it for it in items}
            lines = [] if _agent_name(session=session) else [UNNAMED_WINDOW_LINE]
            lines.extend(f"work: {line}" for line in obligations(root))
            # ready's ``(yours)`` rule: a claim whose close failed to end it stays live, but its
            # item is closed or resolved and prints nowhere (the ready count keeps every claim)
            shown = {
                i: c
                for i, c in claims.items()
                if i not in closed and by_id.get(i, {}).get("status") not in RESOLVED
            }
            awaiting = [
                it
                for it in items
                if it.get("status") == "awaiting-operator" and it["id"] not in closed
            ]
            awaiting.sort(key=lambda it: (str(it.get("created", "")), str(it["id"])))
            for it in awaiting:
                question = it.get("question") or it.get("title") or ""
                ground = f" ({it['ground']})" if it.get("ground") else ""
                also = ", ".join(str(i) for i in it.get("alt_ids") or [] if i)
                also = f" (also asked as {also})" if also else ""
                lines.append(f"work: awaiting operator — {it['id']}{ground}: {question}{also}")
            # Capped (fleet 01M3QJKE): one hub session held 117 claims, a 29 KB block re-sent on
            # every prompt. The lines shown use the Stop hook's sort (`_by_priority`) — a
            # lease end cannot rank them, `_renew_claims` stamps every claim of a session alike —
            # and the count line keeps the rest visible (COBRA: a hidden claim stays counted).
            own_ids = [i for i, c in shown.items() if session and _claim_session(c) == session]
            # ranked and counted from items IN this tree — `ready` lists only those, so the count
            # line's pointer holds; a claim on an item missing here is named on its own line
            own = _by_priority([by_id[i] for i in own_ids if i in by_id])
            elsewhere = sorted(i for i in own_ids if i not in by_id)
            for it in own[:PROMPT_CLAIM_LINES]:
                claim = shown[str(it["id"])]
                title = it.get("title") or ""
                lines.append(
                    f"work: your claim — {it['id']}: {title} "
                    f"(token {claim.get('token')}, lease until {_iso(_claim_end(claim))})"
                )
            if len(own) > PROMPT_CLAIM_LINES:
                lines.append(
                    f"work: … and {len(own) - PROMPT_CLAIM_LINES} more of your claims — "
                    "`python3 scripts/work.py ready` lists them"
                )
            if elsewhere:
                lines.append(_fit_ids("work: your claims on items not in this tree — ", elsewhere))
            lines.extend(_on_it_lines(shown, session))
            ready = len(_ready_from(items, closed, claims))
            if ready:
                lines.append(f"work: {ready} ready — `work.py next`")
            return "\n".join(_clip(" ".join(line.split())) for line in lines)
        except Exception as exc:
            _warn(f"prompt block skipped — {type(exc).__name__}: {exc}")
            return ""


def _priority_arg(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        value = -1
    if value not in (0, 1, 2, 3):
        raise argparse.ArgumentTypeError("priority is 0 (urgent) to 3 (someday)")
    return value


# ── the coordinator's queue (W-83021827, D-512 rebuilt in the simpler shape, D-521) ──────────
#
# "No agent waits idle if there is work to be done": `queue` shows each window's queued work,
# `triage` tops present workers up to the floor, and `queue --stop` hands the Stop hook ONE action.
# QUEUED work is only what was handed out: an owned `task`, or owned backlog the coordinator promoted
# with the `queued` tag — backlog is a list, not an order, and `mail` items are already-claimed
# obligations closed by `mail.py ack`. Three tags keep an item out of AUTOMATIC assignment
# (`runtime` — a serialising act the distributor assigns by hand; `hold`; `waits-*`); every other
# tag stays a label (the rule above TAG_RULE) — `triage` prints them so the coordinator judges role
# fit before `--apply`. A worker counts its queue in ITS OWN tree (each tree holds its own copy of
# the store; `claim` reads it there); routable and backlog counts read the main checkout's.
# COBRA (D-253): claim-and-idle is met by the 2 h lease and the `on it` banner; promoting nothing
# by `queue` printing the waiting backlog to the coordinator at every refusal; hoarding by `triage`
# firing while the coordinator's own queue is above the floor; `queue_floor: 0` is clamped to 1;
# tagging everything `hold` by `queue` printing the held count.
QUEUE_FLOOR = 3
QUEUED_TAG = "queued"
HELD_TAGS = frozenset({"runtime", "hold"})
HELD_PREFIX = "waits-"
_HARNESS_RE = re.compile(r"agent-[0-9a-f]{16,}")
_PLAN_DONE = frozenset({"EXECUTED", "COMPLETE", "SUPERSEDED", "SHIPPED", "ARCHIVED"})


def _tags(item: dict) -> set[str]:
    return set(item.get("tags") or [])


# `waits-YYYY-MM-DD`, strict: `date.fromisoformat` would also take `20261009` and week dates.
_WAITS_DATE_RE = re.compile(r"waits-(\d{4})-(\d{2})-(\d{2})")
_PARK_TAGS = frozenset({"hold"})


def _waits_until(tag: str) -> date | None:
    """The date a `waits-YYYY-MM-DD` tag names, or None (a slug, or not a real date)."""
    m = _WAITS_DATE_RE.fullmatch(tag)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _is_parked(item: dict, today: date | None = None) -> bool:
    """Not doable now: `hold`, a `waits-<slug>`, or a `waits-YYYY-MM-DD` before that UTC date.
    `runtime` is never parked — assigned by hand it is due work (D-558 follow-up)."""
    tags = _tags(item)
    if tags & _PARK_TAGS:
        return True
    day = today or datetime.now(UTC).date()
    for t in tags:
        if t.startswith(HELD_PREFIX):
            until = _waits_until(t)
            if until is None or day < until:
                return True
    return False


def _is_held(item: dict, today: date | None = None) -> bool:
    """Kept out of AUTOMATIC assignment: `runtime`, or parked."""
    return bool(_tags(item) & HELD_TAGS) or _is_parked(item, today)


def _is_work(item: dict) -> bool:
    """Handed-out work: a task, or backlog the coordinator promoted with the `queued` tag."""
    kind = item.get("kind")
    return kind == "task" or (kind == "backlog" and QUEUED_TAG in _tags(item))


def _worktrees(repo: Path) -> list[Path]:
    """Every working tree of ``repo``'s repository, resolved, the main checkout first (`git
    worktree list --porcelain`); ``[repo]`` when git cannot answer — callers index ``[0]``, so the
    list is never empty. The ONE definition: a second, older one at the top of the module returned
    ``[]`` on failure and was silently shadowed by this one (01M422716X)."""
    try:
        out = _git(repo, "worktree", "list", "--porcelain")
    except Exception:
        return [repo.resolve()]
    trees = [
        Path(line[len("worktree ") :]).resolve()
        for line in out.splitlines()
        if line.startswith("worktree ")
    ]
    return trees or [repo.resolve()]


def _workers(main: Path) -> dict[str, Path]:
    """Registered `<main>/.claude/worktrees/<name>` trees that are not harness worktrees."""
    base = (main / ".claude" / "worktrees").resolve()
    out: dict[str, Path] = {}
    for tree in _worktrees(main)[1:]:
        tree = tree.resolve()
        if tree.parent == base and not _HARNESS_RE.fullmatch(tree.name) and _valid_name(tree.name):
            out[tree.name] = tree
    return out


def _present(workers: dict[str, Path]) -> set[str] | None:
    """Workers with a live `claude` process inside their tree, read from /proc (or the root in
    FABRIK_WORK_PROC); None when the process table cannot be read — then nobody is topped up."""
    root = Path(os.environ.get("FABRIK_WORK_PROC") or "/proc")
    try:
        entries = [e for e in root.iterdir() if e.name.isdigit()]
    except OSError:
        return None
    found: set[str] = set()
    for entry in entries:
        try:
            if (entry / "comm").read_text(encoding="utf-8").strip() != "claude":
                continue
            cwd = Path(os.readlink(entry / "cwd")).resolve()
        except OSError:
            continue
        for name, tree in workers.items():
            if cwd == tree or tree in cwd.parents:
                found.add(name)
    return found


def _queued(tree: Path, agent: str) -> list[dict]:
    if not agent or not _has_store(tree):
        return []
    return [
        i
        for i in _ready_items(tree)
        if i.get("owner") == agent and _is_work(i) and not _is_parked(i)
    ]


def _pool(main: Path) -> dict[str, list[dict]]:
    """The main checkout's unowned, ready items: routable work, waiting backlog, held."""
    pool: dict[str, list[dict]] = {"routable": [], "backlog": [], "held": []}
    for item in _ready_items(main):
        if item.get("owner"):
            continue
        if _is_held(item):
            pool["held"].append(item)
        elif _is_work(item):
            pool["routable"].append(item)
        elif item.get("kind") == "backlog":
            pool["backlog"].append(item)
    return pool


def _floor(main: Path) -> int:
    try:
        return max(1, int(_read_config(main).get("queue_floor", QUEUE_FLOOR)))
    except (TypeError, ValueError):
        return QUEUE_FLOOR


def _holds_claim(tree: Path, session: str) -> bool:
    return bool(session) and any(c.get("session") == session for c in _live_claims(tree).values())


def _sessions_of(agent: str, main: Path) -> list[str]:
    """The agent's live Claude Code session names (`mail.py who`), [] when none or on any error."""
    try:
        r = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("mail.py")), "who", agent],
            cwd=main,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    return [n for n in (line.strip() for line in r.stdout.splitlines()) if n and n != "none"]


def _open_plans(main: Path) -> list[str]:
    """Plan spines whose status is not terminal (docs_updater's own parser), [] on any error."""
    try:
        spec = importlib.util.spec_from_file_location(
            "_work_docs_updater", Path(__file__).with_name("docs_updater.py")
        )
        if spec is None or spec.loader is None:
            return []
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out = []
        plans = main / "docs" / "development" / "plans"
        # a plan SET is `plans/<stem>/<stem>.md` + T## tickets; its spine carries the status
        # (web-ecommerce-factory 01M46V7T0CR4MAXBF3K5D0FSDD: a one-level glob never listed one).
        # Sets are matched as `_iter_plan_spines` matches them; top-level files keep the wider
        # `*.md` glob, so an undated plan this view always listed is not dropped
        spines = [d / f"{d.name}.md" for d in plans.glob("*/") if _PLAN_DIR_NAME_RE.match(d.name)]
        for path in sorted([*plans.glob("*.md"), *spines]):
            # one unreadable plan is skipped, never the whole view (review round 1)
            try:
                if not path.is_file():
                    continue  # a dated set directory holding tickets but no spine
                status = str(mod.parse_plan_status(path)[0]).upper().strip()
            except OSError:
                continue
            if (status.split() or [""])[0] not in _PLAN_DONE:
                out.append(f"{path.relative_to(main).as_posix()} ({status})")
        return out
    except Exception:
        return []


def _bucket(n: int) -> str:
    return "0" if n <= 0 else ("few" if n < 5 else "many")


def _stop_action(tree: Path, session: str) -> dict:
    """The ONE action the Stop hook acts on for `session` working in `tree` (see the block above).
    Pure reads; every unknown is a null action (the hook fails open)."""
    main = _worktrees(tree)[0].resolve()
    tree = tree.resolve()
    workers = _workers(main)
    coordinator = (
        str(_read_config(main).get("distributor") or "").strip() if _has_store(main) else ""
    )
    agent = _agent_name(session=session)
    is_worker = tree in workers.values()
    if not agent and is_worker:
        agent = next(n for n, t in workers.items() if t == tree)
    if not agent and tree == main and coordinator:
        agent = coordinator
    none = {"agent": agent, "role": "", "action": None, "fp": "", "text": ""}
    if not _has_store(main):
        return none
    commit = _commit_items_subject(tree, main)
    if _autonomy_on(main):
        result = _autonomy_action(tree, main, session, agent, is_worker, workers, coordinator, none)
        if commit:
            # FIRST on the ladder: it exhausts after three blocks and the ladder moves on, and its
            # fingerprint carries the store's last commit, so it re-arms once that commit lands
            cands = [
                commit,
                *[c for c in result.get("candidates") or [] if c["fp"] != commit["fp"]],
            ]
            result = {**result, **commit, "candidates": cands[:AUTONOMY_MAX_CANDIDATES]}
        return result
    if _holds_claim(tree, session):
        return none  # mid-task: the task's own commit carries its item files
    rung = _classic_rungs(tree, main, agent, is_worker, workers, coordinator, none)
    if rung.get("action") or not commit:
        return rung
    return {**none, **commit}  # LAST on the classic path: it never masks claim/doorbell/triage


def _commit_items_subject(tree: Path, main: Path) -> dict | None:
    """The Stop subject for a session working IN the main checkout while its store holds
    committable item files (W-4238b6ec); a worktree session is never handed it. It counts only
    what `commit-items` would commit, so a skipped file never keeps it alive; when the checkout's
    state refuses the verb (detached HEAD, a merge or rebase in progress) it names that instead.
    The fingerprint carries the store's last commit AND the backlog's power-of-two bucket, so the
    ladder re-arms after a store commit and again each time the backlog doubles. COBRA: ignoring
    ``W-*.json`` in the store's .gitignore would empty the listing and silence this without
    committing anything; a test pins the file."""
    if tree != main:
        return None
    try:
        files = _store_commit_plan(main)[0]
        why = _store_refusal(main) if files else None
    except Exception:
        return None
    if not files:
        return None
    try:
        last = _git(main, "log", "-1", "--format=%h", "--", STORE_REL.as_posix()) or "none"
    except WorkError:
        last = "none"  # no commit yet (a fresh store): still a subject, never silence
    n = len(files)
    head = (
        f"{n} work-item file(s) are uncommitted in this main checkout's store (mail claims, "
        "triage, Stop-hook DECISION items and this checkout's own verbs write it; only this "
        "checkout can commit it)"
    )
    if why:
        text = f"{head}, but they cannot be committed yet: {why} — then `python3 scripts/work.py commit-items`"
    else:
        text = f"{head}: `python3 scripts/work.py commit-items`, then `git push`"
    return {
        "action": "commit-items",
        "fp": f"rung:commit-items:{last}:{n.bit_length()}{':blocked' if why else ''}",
        "text": text + _ESCAPE,
    }


def _classic_rungs(
    tree: Path,
    main: Path,
    agent: str,
    is_worker: bool,
    workers: dict[str, Path],
    coordinator: str,
    none: dict,
) -> dict:
    """The coordinator rungs of D-521 — claim · doorbell · triage · self — for a session that holds
    no claim (the classic path) or, under autonomy, as the ladder's middle rungs."""
    pool = _pool(main)
    routable, backlog = len(pool["routable"]), len(pool["backlog"])
    mine = _queued(tree, agent)
    if mine:
        first = mine[0]
        return {
            "agent": agent,
            "role": "worker" if is_worker else "main",
            "action": "claim",
            "fp": f"claim:{_bucket(len(mine))}",
            "text": f"{len(mine)} item(s) are queued for you ({agent}) and you hold no claim — "
            f"first {first['id']} — {first.get('title', '')}. Claim it in this tree: "
            f"`python3 scripts/work.py claim {first['id']}` and start it, or end on a formatted "
            "`BLOCKED:` escalation naming why it cannot start.",
        }
    if is_worker:
        if not (routable or backlog):
            return {**none, "role": "worker"}
        names = _sessions_of(coordinator, main) if coordinator else []
        ring = " · ".join(
            f"`SendMessage to={n}: queue empty — {routable} routable, {backlog} backlog`"
            for n in names
        )
        how = (
            f"ring the coordinator ({coordinator}): {ring}"
            if ring
            else "the coordinator has no live window — take the next unowned item your own tree "
            "shows (`python3 scripts/work.py next`) and claim it"
        )
        return {
            "agent": agent,
            "role": "worker",
            "action": "doorbell",
            "fp": f"doorbell:{_bucket(routable)}:{_bucket(backlog)}",
            "text": f"Your queue is empty while {routable} routable and {backlog} backlog item(s) "
            f"wait in the main checkout: {how}. Message delivery is best effort.",
        }
    if workers and coordinator and agent == coordinator:
        present = _present(workers) or set()
        floor = _floor(main)
        below = sorted(w for w in present if len(_queued(workers[w], w)) < floor)
        own = len(_queued(main, coordinator))
        if below and (routable or backlog or own > floor):
            return {
                "agent": agent,
                "role": "coordinator",
                "action": "triage",
                "fp": f"triage:{','.join(below)}:{_bucket(routable)}:{_bucket(backlog)}",
                "text": f"{len(below)} worker(s) below the floor of {floor} ({', '.join(below)}) "
                f"while {routable} routable, {backlog} backlog and {own} of your own queued items "
                "wait: run `python3 scripts/work.py triage`, promote the backlog you want done "
                "(`python3 scripts/work.py assign <id> --owner <worker> --tag queued`), then "
                "`python3 scripts/work.py triage --apply`, `python3 scripts/work.py commit-items`, and send the "
                "SendMessage lines it prints.",
            }
        return {**none, "role": "coordinator"}
    if not (workers and coordinator) and (routable or backlog):
        me = agent or "<you>"
        return {
            "agent": agent,
            "role": "self",
            "action": "self",
            "fp": f"self:{_bucket(routable)}:{_bucket(backlog)}",
            "text": f"Nothing is queued for you while {routable} routable and {backlog} backlog "
            f"item(s) wait — this repo has no other coordinator, so you are your own: promote one "
            f"(`python3 scripts/work.py assign <id> --owner {me} --tag queued`) and claim it, or "
            "end on a formatted `BLOCKED:` escalation naming why not.",
        }
    return none


# ── AUTONOMY: the Stop ladder for a hub that opted in (operator ruling 2026-10-04) ────────────
# "handle them all waiting tasks, feedbacks, kaizen items by one autonomously … only stop if you
# cant find answers in our repo" — and "also mails should be handled". With ``"autonomy": true``
# in the MAIN checkout's config the Stop hook is handed an ORDERED list of candidates, one per
# SUBJECT (an item, a mail, a feedback queue at its depth), and blocks on the first it has not
# yet exhausted (``final_gate_stop.py::_coordinator_duty``). The classic path above silenced
# itself whenever the session held ANY claim — and ending a turn on ``NEXT: W-x`` claims W-x —
# so the cause never fired for the agent that most needed it (measured: 143 of the hub's 145 live
# claims held by one session, its last stop passing clean with 12 items queued).
# COBRA (D-253): the cheapest way past a rung is to make its subject vanish without doing it —
# ``release`` a claim, ``ack`` a mail unread, mark feedback rows answered with no edit. Each leaves
# its own audit trail (the next rung names the same owned item; the ``acked-by:`` disposition; the
# answered row's commit), and every block is a kaizen ``stop_block`` event naming its action.
AUTONOMY_KEY = "autonomy"
AUTONOMY_MAX_CANDIDATES = 512
_ESCAPE = (
    " — or end on a formatted `BLOCKED:` escalation; a decision goes to an Opus + Fable panel "
    "first (CLAUDE.md § Autonomy)."
)


def _autonomy_on(main: Path) -> bool:
    try:
        return _read_config(main).get(AUTONOMY_KEY) is True
    except WorkError:
        return False


def _by_priority(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda i: (_priority(i), str(i.get("created") or ""), str(i["id"])))


def _held_text(item: dict, held: int) -> str:
    head = f"You hold {held} claims; next (or another held item): " if held > 5 else ""
    title = item.get("title", "")
    if item.get("kind") == "mail":
        mid = _links(item).get("mail") or "?"
        how = (
            f"handle mail {mid} — validate, do the work, review it, reply — then "
            f"`python3 scripts/mail.py ack {mid} --disposition done|blocked|wontfix`"
        )
    elif item.get("kind") == "feedback":
        how = (
            "answer it with `/fabrik-command-improve`; it closes when its rows are marked answered"
        )
    else:
        how = (
            f"finish it (`python3 scripts/work.py done {item['id']} --evidence <sha>`) or release "
            "it; not due yet or waiting on an event → ask the distributor to park it: "
            f"`work.py assign {item['id']} --tag waits-YYYY-MM-DD|waits-<slug>`"
        )
    return f"{head}{item['id']} — {title}: {how}{_ESCAPE}"


def _mail_candidates(main: Path, agent: str, coordinator: str) -> list[dict]:
    """``ack: required`` mail in the repo's inbox for ``agent`` — addressed to it, or unaddressed
    when ``agent`` is the distributor — oldest first; merge-requests are the seventh cause's."""
    inbox = _mail_root() / main.name / "inbox"
    mail = _sibling("mail")
    if mail is None or not inbox.is_dir() or not agent:
        return []
    found = []
    with os.scandir(inbox) as entries:
        names = sorted(e.name for e in entries)
    for name in names:
        if name.startswith(".") or not name.endswith(".md"):
            continue
        try:
            fm = mail._parse((inbox / name).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if not fm or fm.get("ack") != "required" or fm.get("kind") == "merge-request":
            continue
        to = (fm.get("agent") or "").strip()
        if to != agent and not (not to and agent == coordinator):
            continue
        mid = str(fm.get("id") or name[:-3])
        found.append(
            {
                "action": "mail",
                "fp": f"mail:{mid}",
                "ts": str(fm.get("ts") or ""),
                "text": f"Mail {mid} from {fm.get('from', '?')} ({fm.get('kind', '?')}) needs an "
                f"answer: `python3 scripts/mail.py claim {mid}`, validate it, do the work, review "
                f"it, reply, then `python3 scripts/mail.py ack {mid} --disposition …`{_ESCAPE}",
            }
        )
    found.sort(key=lambda c: c.pop("ts"))
    return found


def _feedback_candidates(tree: Path) -> list[dict]:
    if not (tree / "commands" / "_sources").is_dir():
        return []
    report = _sibling("command_feedback_report")
    depths_fn = getattr(report, "queue_depths", None) if report is not None else None
    depths = depths_fn() if depths_fn is not None else None
    if not isinstance(depths, dict):
        return []
    out = []
    for cmd, n in sorted(depths.items(), key=lambda kv: (-int(kv[1]), str(kv[0]))):
        if int(n) <= 0:
            continue
        out.append(
            {
                "action": "feedback",
                "fp": f"feedback:{cmd}",  # never the depth: a moving count would re-arm it
                "text": f"/{cmd} has {int(n)} unanswered feedback verdict(s): run "
                f"`/fabrik-command-improve {cmd}` — one edit answering the rows it can{_ESCAPE}",
            }
        )
    return out


def _autonomy_candidates(
    tree: Path,
    main: Path,
    session: str,
    agent: str,
    is_worker: bool,
    workers: dict[str, Path],
    coordinator: str,
    none: dict,
) -> list[dict]:
    """The ordered ladder (design: held claims → mail → queued → coordinator rungs → owned →
    the distributor's feedback queues), one candidate per subject, deduplicated by fingerprint.
    `_stop_action` puts the main checkout's `commit-items` subject in front of it."""
    items = list(_iter_items(tree))
    closed = _closed_ids(tree)
    claims = _live_claims(tree)
    cands: list[dict] = []
    mine = [
        i
        for i in items
        if (claims.get(i["id"]) or {}).get("session") == session
        and session
        and i.get("status") == "open"
        and i["id"] not in closed
        and i.get("kind") != "next"
    ]
    held = _by_priority([i for i in mine if not _is_parked(i)])
    for it in held:
        cands.append(
            {"action": "continue", "fp": f"item:{it['id']}", "text": _held_text(it, len(held))}
        )
    for it in _by_priority([i for i in mine if _is_parked(i)]):
        # a parked claim idles: hand it back, and the parked item then sits in no rung
        why = ", ".join(sorted(t for t in _tags(it) if t == "hold" or t.startswith(HELD_PREFIX)))
        cands.append(
            {
                "action": "release",
                "fp": f"release:{it['id']}",
                "text": f"{it['id']} — {it.get('title', '')} is parked ({why}) but you hold its "
                f"claim: `python3 scripts/work.py release {it['id']}`{_ESCAPE}",
            }
        )
    cands.extend(_mail_candidates(main, agent, coordinator))
    classic = _classic_rungs(tree, main, agent, is_worker, workers, coordinator, none)
    if classic.get("action"):
        # a STABLE subject per rung: the classic fps carry live counts and worker names, and a
        # fingerprint that moves between stops re-arms the ladder forever (round 1, A-sonnet)
        # Triage keys on WHICH workers sit below the floor — a new one is a new subject (round 2),
        # while the routable/backlog buckets that moved between stops are dropped.
        first = _queued(tree, agent)[:1] if classic["action"] == "claim" else []
        if first:
            fp = f"item:{first[0]['id']}"
        elif classic["action"] == "triage":
            fp = "rung:triage:" + str(classic["fp"])[len("triage:") :].rsplit(":", 2)[0]
        else:
            fp = f"rung:{classic['action']}"
        classic = {**classic, "fp": fp}
        cands.append({k: classic[k] for k in ("action", "fp", "text")})
    queued = {i["id"] for i in _queued(tree, agent)}
    owned = _by_priority(
        [
            i
            for i in _ready_items(tree)
            if agent
            and i.get("owner") == agent
            and i["id"] not in queued
            and not _is_parked(i)
            and i.get("status") == "open"
        ]
    )
    for it in owned:
        cands.append(
            {
                "action": "owned",
                "fp": f"item:{it['id']}",
                "text": f"{it['id']} ({it.get('kind', '?')}, P{_priority(it)}) is yours and "
                f"waits — {it.get('title', '')}: `python3 scripts/work.py claim {it['id']}` and "
                f"start it{_ESCAPE}",
            }
        )
    if agent and agent == coordinator:
        cands.extend(_feedback_candidates(tree))
    seen: set[str] = set()
    out = []
    for c in cands:
        if c["fp"] not in seen:
            seen.add(c["fp"])
            out.append(c)
    return out[:AUTONOMY_MAX_CANDIDATES]


def _autonomy_action(
    tree: Path,
    main: Path,
    session: str,
    agent: str,
    is_worker: bool,
    workers: dict[str, Path],
    coordinator: str,
    none: dict,
) -> dict:
    cands = _autonomy_candidates(tree, main, session, agent, is_worker, workers, coordinator, none)
    role = "worker" if is_worker else ("coordinator" if agent and agent == coordinator else "main")
    parked = _parked_count(tree, agent, session)
    if not cands:
        return {**none, "role": role, "candidates": [], "parked": parked}
    return {**none, **cands[0], "role": role, "candidates": cands, "parked": parked}


def _parked_count(tree: Path, agent: str, session: str = "") -> int:
    """Open parked items this agent owns or this session has claimed — parking stays visible
    (cobra, D-253: a far date could otherwise park unwanted work out of sight)."""
    if not _has_store(tree):
        return 0
    claims = _live_claims(tree)
    closed = _closed_ids(tree)
    return sum(
        1
        for i in _iter_items(tree)
        if i.get("status") == "open"
        and i["id"] not in closed
        and _is_parked(i)
        and (
            (agent and i.get("owner") == agent)
            or (session and (claims.get(i["id"]) or {}).get("session") == session)
        )
    )


def cmd_queue(repo: Path, args: argparse.Namespace) -> int:
    if args.stop:
        try:
            result = _stop_action(_repo_root(args.cwd or repo), (args.session or "").strip())
        except Exception as exc:  # the hook fails open on a null action
            result = {
                "agent": "",
                "role": "",
                "action": None,
                "fp": "",
                "text": "",
                "error": str(exc),
            }
        print(json.dumps(result, sort_keys=True))
        return 0
    main = _worktrees(repo)[0].resolve()
    _require_store(main)
    workers = _workers(main)
    present = _present(workers)
    coordinator = str(_read_config(main).get("distributor") or "").strip()
    floor = _floor(main)
    pool = _pool(main)
    agents = []
    if coordinator:
        agents.append(
            {
                "agent": coordinator,
                "role": "coordinator",
                "present": True,
                "queued": len(_queued(main, coordinator)),
                "parked": _parked_count(main, coordinator),
                "tree": str(main),
            }
        )
    for name, tree in sorted(workers.items()):
        agents.append(
            {
                "agent": name,
                "role": "worker",
                "present": present is not None and name in present,
                "queued": len(_queued(tree, name)),
                "parked": _parked_count(tree, name),
                "tree": str(tree),
            }
        )
    open_plans = _open_plans(main)  # typed here: the mixed-value report dict widens it to a union
    report = {
        "coordinator": coordinator or None,
        "floor": floor,
        "agents": agents,
        "routable": len(pool["routable"]),
        "backlog_waiting": len(pool["backlog"]),
        "held": len(pool["held"]),
        "plans": open_plans,
    }
    if args.json:
        print(json.dumps(report, sort_keys=True))
        return 0
    if not coordinator:
        print("coordinator: none — set distributor in .fabrik/work/config.json")
    for a in agents:
        mark = "" if a["present"] else " (no live window)"
        print(
            f"{a['agent']:<16} {a['role']:<11} queued {a['queued']}/{floor} · "
            f"parked {a['parked']}{mark}"
        )
    print(
        f"routable {report['routable']} · backlog waiting {report['backlog_waiting']} · "
        f"held {report['held']} (runtime/hold/waits-*)"
    )
    for plan in open_plans:
        print(f"plan not executed: {plan}")
    return 0


def cmd_triage(repo: Path, args: argparse.Namespace) -> int:
    main = _worktrees(repo)[0].resolve()
    _require_store(main)
    distributor = str(_read_config(main).get("distributor") or "").strip()
    if args.apply and distributor and _agent_name() != distributor:
        raise WorkError(
            f"triage --apply is the distributor's ({distributor}); this caller is {_actor_label()}"
        )
    workers = _workers(main)
    present = _present(workers) or set()
    floor = _floor(main)
    pool = _pool(main)
    free = list(pool["routable"])
    plan: dict[str, list[dict]] = {}
    for name in sorted(present):
        need = floor - len(_queued(workers[name], name))
        if need > 0 and free:
            plan[name], free = free[:need], free[need:]
    for name, items in plan.items():
        for item in items:
            tags = ",".join(sorted(_tags(item))) or "-"
            print(
                f"plan: {name:<14} {item['id']}  P{_priority(item)}  [{tags}]  {item.get('title', '')}"
            )
    if not plan:
        print("plan: nothing to assign (no present worker below the floor, or nothing routable)")
    print(
        f"backlog waiting {len(pool['backlog'])} — promote with "
        "`assign <id> --owner <worker> --tag queued`"
    )
    if distributor:
        print(
            f"your own queued items ({distributor}): {len(_queued(main, distributor))} — hand out or keep"
        )
    print(f"held {len(pool['held'])} (runtime/hold/waits-*) — assign by hand")
    for line in _open_plans(main):
        print(f"plan not executed: {line}")
    if not args.apply or not plan:
        return 0
    done: dict[str, list[str]] = {}
    with _store_lock(main, CLI_LOCK_TIMEOUT_S, fail_open=False, label="triage"):
        for name, items in plan.items():
            for item in items:
                fresh = _read_item(main, item["id"])
                if fresh.get("owner"):
                    print(f"skipped {item['id']}: assigned to {fresh['owner']} meanwhile")
                    continue  # never overwrite another assignment
                fresh["owner"] = name
                _write_item(main, fresh)
                done.setdefault(name, []).append(item["id"])
        _after_write(main, _session())
    if not done:
        return 0
    base = _base_branch(main) or "the base branch"
    print("commit the store (`python3 scripts/work.py commit-items`), then send:")
    for name, written in done.items():
        ids = " ".join(written)
        for session in _sessions_of(name, main) or [f"<{name}'s session>"]:
            print(
                f"SendMessage to={session}: assigned {ids} — merge {base} into your branch, then claim"
            )
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="work.py", description=__doc__.split("\n", 1)[0])
    p.add_argument("--repo", default=".", help="any path inside the repo (default: cwd)")
    sub = p.add_subparsers(dest="verb", required=True)

    s = sub.add_parser("init", help="create .fabrik/work/ and config.json (once per repo)")
    s.add_argument("--distributor", help="the agent that owns `assign`")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("add", help="create an item")
    s.add_argument("--kind", required=True, choices=KINDS)
    s.add_argument("--title", required=True)
    s.add_argument("--next", help="the concrete next action, one line")
    s.add_argument("--link", action="append", help="spec=<path> | plan=<path> | decision=D-NNN")
    s.add_argument("--priority", type=_priority_arg, default=DEFAULT_PRIORITY)
    s.add_argument("--tag", action="append", help=f"a constraint label ({TAG_RULE}), repeatable")
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("queue", help="read-only: each window's queued work against the floor")
    s.add_argument("--json", action="store_true", help="one JSON line")
    s.add_argument("--stop", action="store_true", help="the Stop hook's one-line action")
    s.add_argument("--session", default="", help="--stop: the session id")
    s.add_argument("--cwd", default="", help="--stop: the session's working directory")
    s.set_defaults(fn=cmd_queue)

    s = sub.add_parser(
        "triage", help="top present workers up to the floor (the distributor's verb)"
    )
    s.add_argument("--apply", action="store_true", help="assign the plan (otherwise report only)")
    s.set_defaults(fn=cmd_triage)

    s = sub.add_parser("assign", help="set owner, priority, tags (the distributor's verb)")
    s.add_argument("id")
    s.add_argument("--owner")
    s.add_argument("--priority", type=_priority_arg)
    s.add_argument("--tag", action="append", help="add a tag, repeatable")
    s.add_argument("--untag", action="append", help="remove a tag, repeatable")
    s.set_defaults(fn=cmd_assign)

    s = sub.add_parser(
        "ready", help="obligations, your claims, owned, awaiting, then the top 10 ready items"
    )
    s.add_argument("--mine", action="store_true", help="own items first, then unassigned")
    s.add_argument(
        "--all", action="store_true", help="every open, unblocked item by priority then age"
    )
    s.set_defaults(fn=cmd_ready)

    s = sub.add_parser("next", help="the first item `ready --mine` would list")
    s.set_defaults(fn=cmd_next)

    session_help = "the acting session (default: CLAUDE_CODE_SESSION_ID)"
    s = sub.add_parser("claim", help="take (or renew) the live claim on an item")
    s.add_argument("id")
    s.add_argument("--session", help=session_help)
    s.set_defaults(fn=cmd_claim)

    s = sub.add_parser("release", help="give up this session's live claim")
    s.add_argument("id")
    s.add_argument("--session", help=session_help)
    s.set_defaults(fn=cmd_release)

    s = sub.add_parser("done", help="close an item with a commit that names it")
    s.add_argument("id")
    s.add_argument(
        "--evidence",
        help="a commit SHA whose message names the item id (with --resolved-by: optional, and "
        "it must equal the cited item's recorded evidence)",
    )
    s.add_argument(
        "--resolved-by",
        metavar="W-ID",
        help="the DONE item whose recorded fix also resolved this one: this item carries that "
        "item's evidence and records resolved_by (W-f154f3f3)",
    )
    s.add_argument("--session", help=session_help)
    s.set_defaults(fn=cmd_done)

    s = sub.add_parser("drop", help="end an item that won't be done (owner/distributor)")
    s.add_argument("id")
    s.add_argument("--why", help="the reason, kept in `note` (required unless --duplicate-of)")
    s.add_argument(
        "--duplicate-of",
        metavar="KEEP",
        help="retire an awaiting item into the open awaiting item KEEP (distributor/creator)",
    )
    s.add_argument("--session", help=session_help)
    s.set_defaults(fn=cmd_drop)

    s = sub.add_parser("answer", help="close an awaiting-operator item with the operator's words")
    s.add_argument("id")
    s.add_argument("--note", required=True, help="the operator's words")
    s.add_argument("--decision", help="the ledger row already minted (D-NNN)")
    s.add_argument("--session", help=session_help)
    s.set_defaults(fn=cmd_answer)

    s = sub.add_parser("status", help="items, uncommitted item files, and spec/plan drift")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser(
        "commit-items", help="commit the main store's uncommitted item files (main checkout only)"
    )
    s.set_defaults(fn=cmd_commit_items)

    s = sub.add_parser("sync", help="drift check — the completion gate's row")
    s.add_argument(
        "--check", action="store_true", required=True, help="required: the only sync mode"
    )
    s.set_defaults(fn=cmd_sync)

    s = sub.add_parser("render", help="regenerate the backlog's AUTO-GENERATED:BACKLOG block")
    s.set_defaults(fn=cmd_render)

    s = sub.add_parser(
        "migrate-backlog", help="turn existing backlog rows into items (once per repo)"
    )
    s.set_defaults(fn=cmd_migrate_backlog)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        repo = _repo_root(args.repo)
        return int(args.fn(repo, args))
    except WorkError as exc:
        _warn(str(exc))
        return 1
    except OSError as exc:
        _warn(f"{args.verb} failed — {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
