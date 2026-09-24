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
within a process) and writes through a unique, fsynced ``*.tmp`` plus ``os.replace`` — the store's
``.gitignore`` keeps an orphaned temp out of commits. ``init`` alone takes no lock: config.json is
an exclusive link (one winner), and the lock's directory must not exist before the store does.
CLI verbs wait 10 s and then FAIL LOUD; the hook-facing callers (T01b) pass a 2 s timeout and
``fail_open=True``. Every wait over 0.1 s is appended to ``fabrik-work/readings.jsonl``.
COBRA (D-253): the cheapest way to keep ``readings.jsonl`` quiet is to skip the lock; every write
path here goes through ``_store_lock``, and the readings count WAITS, not writes, so a lockless
write shows up as a torn item instead of as silence.

This module is import-safe: nothing runs outside ``if __name__ == "__main__"``.
Implemented here (T01a): init, add, assign, ready [--mine], next. Claims, done/drop/answer,
status/sync, render and migrate-backlog are later tickets that build on the helpers below.
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
import time
from collections.abc import Iterator
from datetime import UTC, datetime
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
READING_MIN_WAIT_S = 0.1
DECISIONS_PY = Path("/opt/fabrik/scripts/decisions.py")  # hub-only, by absolute path
WHOAMI_PY = Path(__file__).with_name("whoami_agent.py")
NAME_RULE = "[a-z0-9-]{1,32}"  # whoami_agent.py's agent-name rule: owners are agent names only
_NAME_RE = re.compile(NAME_RULE)
_ID_RE = re.compile(r"W-[0-9a-f]{8}")  # always .fullmatch — `$` admits a trailing newline
_GIT_TIMEOUT_S = 10.0
# Re-entrancy: the depth of this process's hold per shared dir. flock is per open-file
# description, so a nested acquisition through a fresh fd would wait on its own outer hold.
_HELD: dict[str, int] = {}


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


def _main_checkout(repo: Path) -> Path | None:
    """The main checkout of ``repo``'s repository (first entry of ``git worktree list``)."""
    try:
        out = _git(repo, "worktree", "list", "--porcelain")
    except WorkError:
        return None
    first = out.splitlines()[0] if out else ""
    if not first.startswith("worktree "):
        return None
    return Path(first[len("worktree ") :]).resolve()


def _store_elsewhere(repo: Path) -> Path | None:
    """The main checkout, when ``repo`` is a linked worktree and only the main checkout has a
    store: this branch was cut before ``init``, and a second ``init`` here would fork config."""
    main = _main_checkout(repo)
    if main is not None and main != repo and _has_store(main):
        return main
    return None


def _require_store(repo: Path) -> None:
    if _has_store(repo):
        return
    main = _store_elsewhere(repo)
    if main is not None:
        raise WorkError(
            f"no work store in this worktree {repo}, but the main checkout {main} has one — "
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
    repo is untouched by every hook), otherwise the ``init`` refusal is raised. Re-entrant within
    one process: a nested acquisition yields True at once and leaves the outer hold in place.
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
    key = str(shared)
    if _HELD.get(key):
        _HELD[key] += 1
        try:
            yield True
        finally:
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
        _HELD[key] = 1
        try:
            yield True
        finally:
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


def _is_ready(item: dict, by_id: dict[str, dict]) -> bool:
    if item.get("status") != "open":
        return False
    for dep in item.get("blocked_by") or []:
        blocker = by_id.get(str(dep))
        if blocker is None or blocker.get("status") not in RESOLVED:
            return False
    return True


def _priority(item: dict) -> int:
    p = item.get("priority", DEFAULT_PRIORITY)
    return p if isinstance(p, int) and not isinstance(p, bool) else DEFAULT_PRIORITY


def _ready_items(repo: Path, *, mine: bool = False, agent: str = "") -> list[dict]:
    """Open, unblocked items by priority then age; ``mine`` puts ``agent``'s own first, then the
    unassigned ones, and leaves out items owned by anyone else."""
    items = list(_iter_items(repo))
    by_id = {str(it["id"]): it for it in items}
    ready = [it for it in items if _is_ready(it, by_id)]
    ready.sort(key=lambda it: (_priority(it), str(it.get("created", "")), str(it["id"])))
    if not mine:
        return ready
    owned = [it for it in ready if agent and it.get("owner") == agent]
    free = [it for it in ready if not it.get("owner")]
    return owned + free


def _line(item: dict) -> str:
    owner = item.get("owner") or "-"
    return f"{item['id']}  P{_priority(item)}  {owner}  {item.get('kind', '')}  {item.get('title', '')}"


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
    main = _store_elsewhere(repo)
    if main is not None:
        raise WorkError(
            f"the main checkout {main} already has a work store — this worktree shares it through "
            "git; merge or rebase onto its branch instead of running init here"
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
    try:
        _write_json(cfg, {"distributor": distributor}, exclusive=True)
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
