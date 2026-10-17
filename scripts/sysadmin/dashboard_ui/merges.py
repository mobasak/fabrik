"""The fleet-wide blocked-merge reader behind the Overview's *Blocked merges* (plan 2026-10-17-plan-1, T03).

`merge_request.py` keeps one JSON record per merge request in the repo's git COMMON dir,
``<repo>/.git/fabrik-merge/<id>.json`` — so a worktree's requests sit with its main checkout's. A
record's ``id`` is a Crockford-base32 ULID (`mail.py::_ulid`), so the greatest id per branch is the
newest request. A branch is blocked when that newest record was refused (``outcome: refused``) or parked
(``phase: catchup-refused``); a later merged record, or one still in flight, unblocks it.

Read-only: this module never merges, retries or writes. The merge owner it names is the one
`merge_request.py::_merge_owner` would resolve — the same resolver (`decisions.py --merge-owner`),
under the same interpreter, asked once per repo with a blocked branch and cached `OWNER_TTL_S`. A
render NEVER waits on it (it sits on every Overview GET and on the pause rebuild-on-miss): the
lookup runs in the background, every repo in parallel, one call per repo however many renders ask
at once; until the first answer lands a branch reads ``owner_resolving``, and an expired answer is
served while its refresh runs (`_owners`).

Cobra check (D-253): the cheapest way to pass "the blocked list is right" without the outcome is
reading only ``outcome`` — a parked ``catchup-refused`` record carries none and would vanish, and a
refused record superseded by a merge would linger. The tests write both shapes and assert each.
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

__all__ = ["OWNER_TIMEOUT_S", "OWNER_TTL_S", "blocked"]

OWNER_TIMEOUT_S: float = 10.0  # one resolver subprocess's own timeout
OWNER_TTL_S: float = (
    20.0  # the Overview's refresh cadence: one resolver call per repo per view period
)

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_LEN = 26
# (hub root, repo dir) -> (monotonic time read, owner, owner_error)
_OWNER_CACHE: dict[tuple[str, str], tuple[float, str | None, str | None]] = {}
_owner_lock = threading.Lock()


def _ulid_ms(ident: object) -> int | None:
    """The 48-bit millisecond time of a 26-character Crockford ULID; None for anything else."""
    if not isinstance(ident, str) or len(ident) != _ULID_LEN:
        return None
    value = 0
    for ch in ident.upper():
        digit = _CROCKFORD.find(ch)
        if digit < 0:
            return None
        value = value * 32 + digit
    return value >> 80


def _resolve_owner(fabrik_root: Path, repo_dir: Path) -> tuple[str | None, str | None]:
    """(owner, None) on exit 0; (None, its stdout) on exit 3 — ``UNDECLARED``; (None, its stderr or
    "timed out") on any other exit, a timeout or a resolver that cannot start."""
    argv = [
        sys.executable,
        str(fabrik_root / "scripts" / "decisions.py"),
        "--merge-owner",
        str(repo_dir),
    ]
    try:
        r = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=OWNER_TIMEOUT_S,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "timed out"
    except (OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    out = r.stdout.strip()
    if r.returncode == 0 and out:
        return out, None
    if r.returncode == 3:
        return None, out or "UNDECLARED"
    return None, r.stderr.strip() or out or f"exit {r.returncode}"


class _Flight:
    """One resolver call in progress for one repo; every render that needs it waits on ``done``."""

    __slots__ = ("done", "result")

    def __init__(self) -> None:
        self.done = threading.Event()
        self.result: tuple[str | None, str | None] = (None, "timed out")


# (hub root, repo dir) -> the call in flight; a key is in here at most once (single-flight)
_INFLIGHT: dict[tuple[str, str], _Flight] = {}


def _run_flight(key: tuple[str, str], flight: _Flight) -> None:
    try:
        owner, error = _resolve_owner(Path(key[0]), Path(key[1]))
    except Exception as exc:  # noqa: BLE001 — a resolver fault is that repo's message, never a hang
        owner, error = None, f"{type(exc).__name__}: {exc}"
    with _owner_lock:
        _OWNER_CACHE[key] = (time.monotonic(), owner, error)
        _INFLIGHT.pop(key, None)
    flight.result = (owner, error)
    flight.done.set()


def _owners(
    fabrik_root: Path, repo_dirs: list[Path]
) -> dict[Path, tuple[str | None, str | None, bool]]:
    """``(owner, owner_error, resolving)`` for every repo in ``repo_dirs``, from the cache ONLY —
    this never waits on the resolver. A fresh cached answer is served as is; an expired one is served
    too while ONE background call refreshes it (stale-while-revalidate); a repo with no answer yet
    reads ``resolving`` while the call in flight for it (single-flight; every repo in parallel) runs.
    A resolver thread that cannot start is that render's ``owner_error``, never cached."""
    out: dict[Path, tuple[str | None, str | None, bool]] = {}
    with _owner_lock:
        for repo_dir in repo_dirs:
            key = (str(fabrik_root), str(repo_dir))
            hit = _OWNER_CACHE.get(key)
            if hit is not None and time.monotonic() - hit[0] < OWNER_TTL_S:
                out[repo_dir] = (hit[1], hit[2], False)
                continue
            flight = _INFLIGHT.get(key)
            if flight is None:
                flight = _INFLIGHT[key] = _Flight()
                try:
                    threading.Thread(
                        target=_run_flight, args=(key, flight), name="merge-owner", daemon=True
                    ).start()
                except Exception as exc:  # noqa: BLE001 — no thread: this render's message, and
                    # the key is released (never cached) so the next render tries again
                    _INFLIGHT.pop(key, None)
                    flight.result = (None, f"{type(exc).__name__}: {exc}")
                    flight.done.set()
            if hit is not None:  # stale: keep serving it while the refresh runs
                out[repo_dir] = (hit[1], hit[2], False)
            elif flight.done.is_set():  # the thread could not start: this render's message
                out[repo_dir] = (*flight.result, False)
            else:  # nothing known yet: the page says "resolving" and the next render has it
                out[repo_dir] = (None, None, True)
    return out


def _repos(opt_root: Path) -> list[tuple[str, Path]]:
    """(name, records dir) for every repo under ``opt_root`` whose git dir keeps merge records; a
    symlinked alias of a repo already listed is skipped, real directories first."""
    try:
        entries = sorted(opt_root.iterdir(), key=lambda p: (p.is_symlink(), p.name))
    except OSError:
        return []
    out: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for repo in entries:
        records = repo / ".git" / "fabrik-merge"
        try:
            if not records.is_dir():
                continue
            real = repo.resolve()
        except OSError:
            continue
        if real in seen:
            continue
        seen.add(real)
        out.append((repo.name, records))
    return out


def blocked(
    opt_root: Path,
    fabrik_root: Path,
    *,
    unreadable: list[str] | None = None,
    now: float | None = None,
) -> list[dict]:
    """Every blocked branch across ``<opt_root>/*/.git/fabrik-merge/``: ``{repo, branch, item, requester,
    id, age_s, reason, owner, owner_error, owner_resolving}``. A record that cannot be read, is not JSON, is not an
    object or has no ULID ``id`` is skipped and its path appended to ``unreadable`` — never raised."""
    clock = time.time() if now is None else now
    out: list[dict] = []
    found: list[tuple[str, list[dict]]] = []
    for name, records in _repos(opt_root):
        newest: dict[str, dict] = {}
        try:
            paths = sorted(records.glob("*.json"))
        except OSError:
            paths = []
        for path in paths:
            try:
                if not path.is_file():  # a FIFO or a directory would hang or raise
                    raise OSError("not a regular file")
                rec = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                rec = None
            if not isinstance(rec, dict) or _ulid_ms(rec.get("id")) is None:
                if unreadable is not None:
                    unreadable.append(str(path))
                continue
            branch = str(rec.get("branch") or "")
            # Crockford is case-insensitive: compare the canonical upper-case spelling
            if branch not in newest or rec["id"].upper() > newest[branch]["id"].upper():
                newest[branch] = rec
        stuck = [
            r
            for r in newest.values()
            if r.get("outcome") == "refused" or r.get("phase") == "catchup-refused"
        ]
        if stuck:
            found.append((name, sorted(stuck, key=lambda r: r["id"].upper())))
    owners = _owners(fabrik_root, [opt_root / name for name, _recs in found])
    for name, stuck in found:
        owner, owner_error, resolving = owners[opt_root / name]
        for rec in stuck:
            ms = _ulid_ms(rec["id"])
            out.append(
                {
                    "repo": name,
                    "branch": str(rec.get("branch") or ""),
                    "item": str(rec.get("item") or ""),
                    "requester": str(rec.get("requester") or ""),
                    "id": rec["id"],
                    "age_s": None if ms is None else max(0.0, clock - ms / 1000.0),
                    "reason": str(rec.get("reason") or ""),
                    "owner": owner,
                    "owner_error": owner_error,
                    "owner_resolving": resolving,
                }
            )
    return out
