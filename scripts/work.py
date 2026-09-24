#!/usr/bin/env python3
# AFTER-EDIT: tests/test_work.py, tests/test_work_claims.py, tests/test_work_sync.py, tests/test_work_migrate.py, docs/reference/work-tracking.md
"""Work tracking — one open-work record per repo, shared by its agents (spec 2026-09-24).

THE STORE. One pretty-printed, sorted-key JSON file per item under ``<repo>/.fabrik/work/``,
committed with the code; ``config.json`` beside them names the distributor. Items are never
deleted — they end ``done`` or ``dropped``. Shared, unversioned state (the lock, and later the
claims, closed markers and readings) lives in ``<git common dir>/fabrik-work/``, which the main
checkout and every worktree of the repo see as one directory.

NO IMPLICIT STORE. ``init`` is the only writer of ``config.json``. Every other verb, in a repo
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
the hook API (T01b); status, sync --check (T02). render and migrate-backlog are later tickets.
"""

from __future__ import annotations

import argparse
import contextlib
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
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover — non-POSIX; the store is POSIX-only
    fcntl = None  # type: ignore[assignment]

STORE_REL = Path(".fabrik") / "work"
SHARED_NAME = "fabrik-work"
KINDS = ("backlog", "decision", "next", "task")
STATUSES = ("open", "blocked", "awaiting-operator", "done", "dropped")
RESOLVED = ("done", "dropped")
LINK_KEYS = ("spec", "plan", "decision")
DEFAULT_PRIORITY = 2
CLI_LOCK_TIMEOUT_S = 10.0
HOOK_LOCK_TIMEOUT_S = 2.0
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
_BACKLOG_BLOCK_RE = re.compile(
    r"<!--\s*AUTO-GENERATED:BACKLOG:START\s*-->(.*?)<!--\s*AUTO-GENERATED:BACKLOG:END\s*-->", re.S
)
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
NAME_RULE = "[a-z0-9-]{1,32}"  # whoami_agent.py's agent-name rule: owners are agent names only
_NAME_RE = re.compile(NAME_RULE)
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


def _git(path: Path | str, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkError(f"git {' '.join(args)} failed in {path}: {exc}") from exc
    if proc.returncode != 0:
        lines = proc.stderr.strip().splitlines()
        reason = lines[0] if lines else f"exit {proc.returncode}"
        raise WorkError(f"git {' '.join(args)} failed in {path}: {reason}")
    return proc.stdout.strip()


def _repo_root(path: Path | str = ".") -> Path:
    """The work tree's top level, so a caller may pass any subdirectory."""
    return Path(_git(path, "rev-parse", "--show-toplevel")).resolve()


def _store_dir(repo: Path) -> Path:
    """``<repo>/.fabrik/work`` — the committed items and ``config.json``."""
    return repo / STORE_REL


def _config_path(repo: Path) -> Path:
    return _store_dir(repo) / "config.json"


def _common_dir(repo: Path) -> Path:
    """The git common directory: shared by the main checkout and every worktree."""
    return Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()


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


def _worktrees(repo: Path) -> list[Path]:
    """Every working tree of ``repo``'s repository, main checkout first (``git worktree list``)."""
    try:
        out = _git(repo, "worktree", "list", "--porcelain")
    except WorkError:
        return []
    return [
        Path(line[len("worktree ") :]).resolve()
        for line in out.splitlines()
        if line.startswith("worktree ")
    ]


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


def _agent_name() -> str:
    """The resolver's name (``whoami_agent.resolve_agent_name()``, imported by path) when it gives
    one, else ``CLAUDE_AGENT`` when it matches NAME_RULE, else ""; never raises. Both paths apply
    the same name rule, so a failed import never loosens identity."""
    name = ""
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
    return env if _valid_name(env) else ""


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
        "links": {key: links.get(key, "") for key in LINK_KEYS},
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


def _ready_from(
    items: list[dict],
    closed: set[str],
    claims: dict[str, dict],
    *,
    mine: bool = False,
    agent: str = "",
) -> list[dict]:
    by_id = {str(it["id"]): it for it in items}
    ready = [it for it in items if _is_ready(it, by_id, closed) and it["id"] not in claims]
    ready.sort(key=lambda it: (_priority(it), str(it.get("created", "")), str(it["id"])))
    if not mine:
        return ready
    owned = [it for it in ready if agent and it.get("owner") == agent]
    free = [it for it in ready if not it.get("owner")]
    return owned + free


def _ready_items(repo: Path, *, mine: bool = False, agent: str = "") -> list[dict]:
    """Open, unblocked items with no live claim and no effective closed marker, by priority then
    age; ``mine`` puts ``agent``'s own first, then the unassigned ones, and leaves out items owned
    by anyone else. "Claimed" is derived here, never stored on the item."""
    items = list(_iter_items(repo))
    return _ready_from(items, _closed_ids(repo), _live_claims(repo), mine=mine, agent=agent)


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


def _base_statuses(repo: Path, ids: list[str]) -> dict[str, str]:
    """The status each id's item has on the store's BASE BRANCH, read as a ref (one ``cat-file
    --batch`` call) — never whatever a checkout has checked out. An id missing there is absent
    from the result, and any git failure yields {}: a marker then keeps hiding its item."""
    branch = _base_branch(repo) if ids else ""
    if not branch:
        return {}
    req = "".join(f"refs/heads/{branch}:{STORE_REL.as_posix()}/{i}.json\n" for i in ids)
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "--batch"],
            input=req.encode(),
            capture_output=True,
            timeout=_GIT_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if proc.returncode != 0:
        return {}
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
        return {}
    return found


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
    return f"{item['id']}  P{_priority(item)}  {owner}  {item.get('kind', '')}  {item.get('title', '')}"


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


def _import_enforcement(repo: Path, name: str) -> object | None:
    """``scripts/enforcement/<name>.py`` of ``repo``, imported by path; None (with one stderr
    line) when the file is absent or fails to import — never raises."""
    path = repo / "scripts" / "enforcement" / f"{name}.py"
    try:
        spec = importlib.util.spec_from_file_location(f"_work_{name}", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"no loader for {path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as exc:
        _warn(f"{name} import failed ({exc}) — using the local regex fallback for its grammar")
        return None


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


def _iter_plan_spines(repo: Path) -> Iterator[Path]:
    """Every plan spine: a standalone dated file, or a same-stem file inside a dated plan-set
    directory (archived and ticket files are excluded by construction — neither matches)."""
    d = repo / PLANS_DIR
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


_STATUS_TOKEN_CONTINUATION_RE = re.compile(r"[A-Za-z0-9_-]*")


def _status_value(repo: Path, text: str) -> str:
    """``_STATUS_LINE``'s own character class excludes digits and ``_``, so it truncates a raw
    ``IN_PROGRESS``-shaped value at the underscore (`IN`); extend the match with whatever
    word/hyphen/underscore characters immediately follow, so the alias map sees the whole token
    rather than reusing the reader's class as a normaliser it was never built to be."""
    head = text[:4000]
    m = _status_line_re(repo).search(head)
    if not m:
        return ""
    cont = _STATUS_TOKEN_CONTINUATION_RE.match(head, m.end(1))
    return (m.group(1) + (cont.group(0) if cont else "")).strip()


def _normalize_plan_status(raw: str) -> str:
    up = raw.strip().upper()
    return _PLAN_STATUS_ALIASES.get(up, up)


def _commit_epoch(repo: Path, relpath: str) -> float | None:
    """The epoch of the last commit touching ``relpath`` at HEAD, or None with no history — never
    the filesystem mtime, which a fresh checkout resets to the checkout instant."""
    try:
        out = _git(repo, "log", "-1", "--format=%ct", "HEAD", "--", relpath)
    except WorkError:
        return None
    out = out.strip()
    return float(out) if out else None


def _age_seconds(repo: Path, relpath: str) -> float:
    """Seconds since ``relpath``'s last commit; 0 with no history (as fresh as it gets)."""
    epoch = _commit_epoch(repo, relpath)
    return max(0.0, time.time() - epoch) if epoch is not None else 0.0


def _active_plan_locks(repo: Path) -> dict[str, dict]:
    """plan relpath -> lock record, for every ``.fabrik/plan-locks/*.json`` whose status is
    literally ``active`` (``released``/``executed``/``complete`` do not count as a lock)."""
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
            plan = str(data.get("plan") or "").strip()
            if plan:
                out[plan] = data
    return out


def _backlog_needs_render(repo: Path, items: list[dict]) -> bool:
    """True when the open ``kind: backlog`` item ids differ from the ids the rendered
    ``AUTO-GENERATED:BACKLOG`` block currently lists — the cheapest honest proxy for "render
    would change it" without duplicating ``render`` itself (T03)."""
    path = repo / _BACKLOG_REL
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    m = _BACKLOG_BLOCK_RE.search(text)
    if not m:
        return False
    open_ids = {
        str(it["id"])
        for it in items
        if it.get("kind") == "backlog" and it.get("status") not in RESOLVED
    }
    block_ids = set(_ID_RE.findall(m.group(1)))
    return open_ids != block_ids


def _drift_report(repo: Path) -> dict[int, list[str]]:
    """The eight drift classes of spec § Spec and plan state is derived, never copied, each a
    sorted list of the relpaths (item files for 5-6, the backlog doc for 7) that trip it."""
    report: dict[int, list[str]] = {n: [] for n in range(1, 9)}
    items = list(_iter_items(repo))
    linked_specs = {str((it.get("links") or {}).get("spec") or "") for it in items}
    linked_specs.discard("")
    linked_plans: dict[str, list[dict]] = {}
    for it in items:
        plan = str((it.get("links") or {}).get("plan") or "")
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
        cited_specs.update(cite_fn(text))

    for spec_path in _iter_specs(repo):
        rel = _rel(repo, spec_path)
        try:
            text = spec_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _status_value(repo, text).strip().upper() != "CONVERGED":
            continue
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
                and _age_seconds(repo, rel) > STALE_PLAN_DAYS * 86400
            ):
                report[2].append(rel)
        elif norm == "IN-PROGRESS":
            if not has_lock:
                report[3].append(rel)
        elif norm == "EXECUTED":
            if any(li.get("status") not in RESOLVED for li in linked_plans.get(rel, [])):
                report[4].append(rel)

    store = _store_dir(repo)
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
            if data.get("status") == "done" and not data.get("legacy"):
                if _age_seconds(repo, rel) <= RECENT_WINDOW_S:
                    ev = str(data.get("evidence") or "")
                    if _evidence_commit(repo, path.stem, ev) is None:
                        report[6].append(rel)

    now = time.time()
    for item_id, marker in _read_records(_closed_dir(repo)).items():
        at = _num(marker.get("at"), _num(marker.get("_mtime")))
        if now - at <= MARKER_MAX_AGE_S:
            continue
        try:
            own = _read_item(repo, item_id)
        except WorkError:
            continue
        if own.get("status") not in RESOLVED:
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
    counts = row.get("counts") or {}
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
    drift class (spec § Constraints — shared tree)."""
    store_rel = STORE_REL.as_posix()
    try:
        out = _git(repo, "status", "--porcelain", "--untracked-files=all", "--", store_rel)
    except WorkError:
        return []
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
    trees = _worktrees(repo)
    base_branch = _branch_of(trees[0] if trees else repo)
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
    with _store_lock(repo, CLI_LOCK_TIMEOUT_S, fail_open=False, label="add"):
        path = _create_item(repo, item)
        _after_write(repo, _session())
    print(_rel(repo, path))
    return 0


def cmd_assign(repo: Path, args: argparse.Namespace) -> int:
    _require_store(repo)
    if args.owner is None and args.priority is None:
        raise WorkError("assign needs --owner and/or --priority")
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
        path = _write_item(repo, item)
        _after_write(repo, _session())
    print(_rel(repo, path))
    return 0


def cmd_ready(repo: Path, args: argparse.Namespace) -> int:
    _require_store(repo)
    for item in _ready_items(repo, mine=args.mine, agent=_agent_name() if args.mine else ""):
        print(_line(item))
    return 0


def cmd_next(repo: Path, args: argparse.Namespace) -> int:
    _require_store(repo)
    items = _ready_items(repo, mine=True, agent=_agent_name())
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
    """Close ``item`` (already updated): the marker FIRST, then the item — a failed item write
    removes the marker and re-raises — and the claim LAST, so a failure never leaves an item closed
    here while every other tree still lists it, nor a closed marker for an open item."""
    _write_marker(repo, item, session=session, evidence=evidence, note=note, decision=decision)
    try:
        path = _write_item(repo, item)
    except BaseException:
        with contextlib.suppress(OSError):
            (_closed_dir(repo) / f"{item['id']}.json").unlink()
        raise
    _end_claim(repo, str(item["id"]))
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
    else None — the read-only half of ``_verify_evidence``, reused by drift class 6 (T02)."""
    if not sha or sha.startswith("-"):
        return None
    try:
        _git(repo, "cat-file", "-e", f"{sha}^{{commit}}")
        resolved = _git(repo, "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}")
    except WorkError:
        return None
    try:
        message = _git(repo, "log", "-1", "--format=%B", resolved)
    except WorkError:
        return None
    return resolved if item_id in _ITEM_REF_RE.findall(message) else None


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
        claim = _claim_of(repo, args.id)
        now = time.time()
        if _is_live(claim, now) and claim is not None:
            if claim.get("session") != session:
                raise WorkError(f"claim {args.id} refused: it is held by {_holder(claim)}")
            claim["at"] = now  # the live holder's claim renews it
            verb = "renewed"
        else:
            token = int(_num((claim or {}).get("token"))) + 1
            claim = {
                "agent": _agent_name(),
                "at": now,
                "lease_s": DEFAULT_LEASE_S,
                "session": session,
                "token": token,
            }
            verb = "claimed"
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


def cmd_done(repo: Path, args: argparse.Namespace) -> int:
    _require_store(repo)
    _refuse_closed(repo, _read_item(repo, args.id), "done")
    session = _call_session(args)
    sha = _verify_evidence(repo, args.id, args.evidence)
    with _store_lock(repo, CLI_LOCK_TIMEOUT_S, fail_open=False, label="done"):
        item = _read_item(repo, args.id)
        _refuse_closed(repo, item, "done")
        _fence(repo, args.id, session, "done")
        item.update(status="done", evidence=sha)
        path = _close(repo, item, session=session, evidence=sha)
        _after_write(repo, session)
    print(_rel(repo, path))
    return 0


def cmd_drop(repo: Path, args: argparse.Namespace) -> int:
    _require_store(repo)
    _read_item(repo, args.id)
    why = " ".join((args.why or "").split())
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


def cmd_status(repo: Path, args: argparse.Namespace) -> int:
    """Items by state, uncommitted item files (a listing, never a drift class), and the eight
    derived spec/plan drift classes — read-only, no lock."""
    _require_store(repo)
    claims = _live_claims(repo)
    for item in sorted(
        _iter_items(repo), key=lambda it: (str(it.get("status")), _priority(it), str(it["id"]))
    ):
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
    try:
        return _repo_root(path)
    except Exception:
        return None


def has_store(repo: Path | str) -> bool:
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


def _ensure_decision_locked(repo: Path, block: str, msg_digest: str, session: str) -> str:
    """The three rules (caller holds the store lock): a known message digest → that item; an OPEN
    awaiting item with this block digest → add the digest; else → a new awaiting decision item."""
    items = list(_iter_items(repo))
    for it in items:
        if msg_digest in (it.get("msg_digests") or []):
            return str(it["id"])
    bd = _block_digest(block)
    same = [
        it
        for it in items
        if it.get("status") == "awaiting-operator" and it.get("block_digest") == bd
    ]
    closed = _closed_ids(repo) if same else set()
    for it in same:
        if it["id"] not in closed:
            it["msg_digests"] = [*(it.get("msg_digests") or []), msg_digest]
            _write_item(repo, it)
            return str(it["id"])
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
        creator=_agent_name() or session,
        ground=gm.group(1).lower() if gm else "",
        msg_digests=[msg_digest],
        question=question,
        status="awaiting-operator",
    )
    _create_item(repo, item)
    return str(item["id"])


def ensure_decision_item(
    repo: Path | str,
    *,
    block: str,
    msg_digest: str,
    session: str,
    lock_timeout: float = HOOK_LOCK_TIMEOUT_S,
) -> str | None:
    """The DECISION block's item id (found, refreshed or created), or None."""
    got = ensure_decision_items(repo, [(block, msg_digest, session)], lock_timeout=lock_timeout)
    return got[0] if got else None


def ensure_decision_items(
    repo: Path | str,
    entries: list[tuple[str, str, str]],
    *,
    lock_timeout: float = HOOK_LOCK_TIMEOUT_S,
) -> list[str] | None:
    """``ensure_decision_item`` for every ``(block, msg_digest, session)`` under ONE lock: the ids
    of the entries that succeeded (an entry that raises is skipped with one stderr line); None
    only when the store is absent or the lock was not taken."""
    try:
        root = _api_root(repo)
        if root is None:
            return None
        with _store_lock(root, lock_timeout, fail_open=True, label="decision") as held:
            if not held:
                return None
            ids = []
            for b, d, s in entries:
                try:  # one bad entry never costs the others their item
                    ids.append(_ensure_decision_locked(root, b, d, s))
                except Exception as exc:
                    _warn(f"decision item not written — {type(exc).__name__}: {exc}")
            _after_write(root, *(s for _, _, s in entries))
            return ids
    except Exception as exc:
        _warn(f"decision item not written — {type(exc).__name__}: {exc}")
        return None


def _set_next(repo: Path, next_text: str, session: str) -> None:
    """The named item's ``next`` — unless ANOTHER session holds a live claim on it."""
    m = _ITEM_REF_RE.search(next_text)
    if not m or not _item_path(repo, m.group(0)).is_file():
        return
    claim = _claim_of(repo, m.group(0))
    if _is_live(claim) and claim is not None and claim.get("session") != session:
        return
    item = _read_item(repo, m.group(0))
    text = " ".join(next_text.split())[:LINE_MAX]
    if item.get("status") not in RESOLVED and item.get("next") != text:
        item["next"] = text
        _write_item(repo, item)


def on_harvest(
    repo: Path | str,
    *,
    session: str,
    block: str | None = None,
    msg_digest: str | None = None,
    next_text: str | None = None,
    lock_timeout: float = HOOK_LOCK_TIMEOUT_S,
) -> str | None:
    """The Stop harvest's ONE store call, under ONE lock: (1) the decision item, first — the write
    that must not be lost; (2) the ``next`` of an item a NEXT line names; (3) renew ``session``'s
    live claims; the marker prune runs last. Returns the decision item's id, else None."""
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
                    decision = _ensure_decision_locked(root, block, msg_digest, session)
                except Exception as exc:
                    _warn(f"decision item not written — {type(exc).__name__}: {exc}")
            if next_text:
                try:
                    _set_next(root, next_text, session)
                except Exception as exc:
                    _warn(f"item next not written — {type(exc).__name__}: {exc}")
            _after_write(root, session)
            return decision
    except Exception as exc:
        _warn(f"harvest not written — {type(exc).__name__}: {exc}")
        return None


def has_msg_digest(repo: Path | str, msg_digest: str) -> bool:
    try:
        root = _api_root(repo)
        if root is None:
            return False
        return any(msg_digest in (it.get("msg_digests") or []) for it in _iter_items(root))
    except Exception:
        return False


def _clip(line: str) -> str:
    return line if len(line) <= LINE_MAX else line[: LINE_MAX - 1] + "…"


def prompt_block(repo: Path | str, session: str) -> str:
    """Read-only, no lock, the caller's own tree: every awaiting-operator item with its question,
    ``session``'s live claims, and the ready count — or "" when all three are empty."""
    try:
        root = _api_root(repo)
        if root is None:
            return ""
        items = list(_iter_items(root))
        closed = _closed_ids(root)
        claims = _live_claims(root)
        by_id = {str(it["id"]): it for it in items}
        lines = []
        awaiting = [
            it for it in items if it.get("status") == "awaiting-operator" and it["id"] not in closed
        ]
        awaiting.sort(key=lambda it: (str(it.get("created", "")), str(it["id"])))
        for it in awaiting:
            question = it.get("question") or it.get("title") or ""
            ground = f" ({it['ground']})" if it.get("ground") else ""
            lines.append(f"work: awaiting operator — {it['id']}{ground}: {question}")
        for item_id, claim in sorted(claims.items()):
            if session and claim.get("session") == session:
                title = by_id.get(item_id, {}).get("title") or "(not in this tree)"
                lines.append(
                    f"work: your claim — {item_id}: {title} "
                    f"(token {claim.get('token')}, lease until {_iso(_claim_end(claim))})"
                )
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
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("assign", help="set owner and/or priority (the distributor's verb)")
    s.add_argument("id")
    s.add_argument("--owner")
    s.add_argument("--priority", type=_priority_arg)
    s.set_defaults(fn=cmd_assign)

    s = sub.add_parser("ready", help="open, unblocked items by priority then age")
    s.add_argument("--mine", action="store_true", help="own items first, then unassigned")
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
    s.add_argument("--evidence", help="a commit SHA whose message names the item id")
    s.add_argument("--session", help=session_help)
    s.set_defaults(fn=cmd_done)

    s = sub.add_parser("drop", help="end an item that won't be done (owner/distributor)")
    s.add_argument("id")
    s.add_argument("--why", required=True, help="the reason, kept in `note`")
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

    s = sub.add_parser("sync", help="drift check — the completion gate's row")
    s.add_argument(
        "--check", action="store_true", required=True, help="required: the only sync mode"
    )
    s.set_defaults(fn=cmd_sync)
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
