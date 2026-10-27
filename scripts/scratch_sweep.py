#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/cleanup-automation.md | docs/workstation/hooks-index.md | tests/test_scratch_sweep.py
"""Sweep YOUR OWN session scratch, YOUR OWN agent worktrees, and DEAD sessions' scratch — never blindly.

Operator directive 2026-09-08: *"i want agents delete their own scratchpads when they are done, but
time to time their work can be interrupt by network issues, they can fill context, or account quota
holds interrupts them"* → *"ok but we should not cause data loss, agents must know what will this
script do while using it."* Those two sentences are the whole design:

  DRY-RUN IS THE DEFAULT. `--apply` is opt-in. Every row carries a class, a reason and its evidence,
  and the refusal set below is printed by `--help` and by every apply run, so an agent knows what
  this script will and will not touch BEFORE it runs it.

THREE MODES
  (default)     this session's scratchpad — one row per top-level entry
  --worktrees   this repo's agent worktrees — one row per registration, plus orphan directories
  --dead        the janitor: sessions that can never clean themselves (cron; see § F of
                docs/workstation/cleanup-automation.md)

WHY A SID IS `dead` ONLY ON THREE POSITIVE SIGNALS (plan review, pass 4): a gone pid is NOT a
finished session — `--resume`/`--continue` keeps the sid alive across a network death, a context
fill or a quota hold, which are exactly the interruptions this tool exists to serve. Measured on
this box 2026-09-08: 18 sids had a gone-pid sessions file and a live directory, and ALL 18 dirs were
younger than 7 d — one of them 8 minutes old. So `dead` requires: no live signal, AND a death
signal, AND the directory itself idle past the threshold. Absence of evidence is `unclassified`,
which is never removed.

WHY A `/proc` GAP IS REPORTED AND NOT BLOCKING (plan review, pass 5): the holder probe cannot read
`/fd` for some pids. Measured: 152 of 466 deny it and 150 are FOREIGN-uid, which cannot hold a
descriptor under the 0700 scratch root anyway; the two same-uid deniers are `(sd-pam)` and
`fusermount3`, both permanent. A rule that downgraded every entry whenever such a pid existed would
make this tool inert on every run, forever. So gaps are COUNTED and named in the summary line, and
only `--strict-proc` turns them into `probe-error`.

Stdlib-only, on purpose: `scripts/command_run.py` is synced to ~46 repos and invokes this script
with that repo's own interpreter.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import functools
import glob as globmod
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TypeGuard

# ── the refusal set — printed verbatim by --help and by every apply run (constraint 2) ──────────
REFUSAL_SET = """NEVER TOUCHES (hard-coded; this text is printed by --help and by every --apply run):
  * /opt/<repo> tracked or untracked files — except a `git worktree remove` of a worktree this
    script classified removable
  * ~/.claude*/projects transcripts, and ~/.claude*/state EXCEPT the one file it creates and locks,
    $HOME/.claude/state/scratch-sweep.lock, and the size report beside it,
    $HOME/.claude/state/scratch-size-report.json (written only by --dead --apply) — it reads,
    writes and deletes nothing else there
  * <repo>/.tmp/** as a scan root (the subagent spools; a worktree git itself reports under .tmp is
    classified like any other worktree and spared by the ordinary guards, never swept as a spool)
  * docker anything — volumes are DATA
  * another LIVE session's scratch, and this session's own tasks/ directory
  * a symlink's target — a symlinked entry is `unclassified` and is never followed
  * a HARNESS-owned worktree (<repo>/.claude/worktrees/**, or a .git/worktrees/<n>/CLAUDE_BASE
    marker) unless --include-harness AND its own chain verdict is wt-removable
    — and in --dead only the hub's `.claude/worktrees/agent-<hex>` trees, dormant 3 days by their
    last commit or checkout, with no repo-wide `git worktree prune`
  * a worktree this session did not create (wt-foreign) unless --foreign-older-than DURATION, and
    then ONLY when its own chain verdict is wt-removable — merged, clean, unlocked and unheld; a
    dormant tree whose registration is merely STALE stays wt-foreign, because acting on it runs
    the REPO-WIDE `git worktree prune` and would drop other sessions' registrations too
  * a worktree holding IGNORED files outside the cache allowlist (wt-ignored-data) — an ignored
    copy whose bytes sit in the main checkout's backups/ under a name naming it is not data — or a directory
    git does not register (wt-orphan-dir)
  * a worktree whose dirt is ENTIRELY the governance sync's own output (wt-sync-only), and a clean
    worktree whose branch is not merged (wt-unmerged), unless --include-unmerged: then the FOLDER
    goes and no commit is lost — an unmerged branch is always kept, and any other is offered only
    to git's own `branch -d`, which refuses an unmerged one; a sync-only tree is removed with
    --force only after its state is re-read at removal time — any authored file, a stash naming
    its branch, or ignored data keeps it
  * anything holding a BACKUP SHAPE — *.bak, *.original, *pristine* (case-insensitive),
    before.txt/after.txt, .keep — the entry's OWN NAME included, unless --include-backups;
    inside a CONSUMED run folder (scratchpad/run-<key>/) backup shapes are disposable by contract
  * a run folder (scratchpad/run-<key>/) by its AGE or by a walk — it is judged only by its .owner
    marker and the holder probe: removed when its run closed past the grace (30 minutes, or 36 h
    when a seat wrote after the close or that cannot be read) or when its session is dead and its
    heartbeat is 7 days stale; a running, resumable, held, kept, worktree-holding or unmarked one
    is never removed
  * a root-level entry of the scratch root, unless --unowned-older-than DAYS
Held, kept, fresh, dirty, unmerged, locked, orphan-dir, ignored-data, sync-only and unclassifiable entries are
LISTED with their reason and never removed. Foreign is the one CONDITIONAL class: listed and never
removed by default, and judged on its own state only under --foreign-older-than (see above)."""

# Ignored paths that are rebuildable caches, not data — a worktree holding only these stays removable.
CACHE_ALLOWLIST = (
    ".venv/",
    "node_modules/",
    "__pycache__/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".mypy_cache/",
)

# A scratchpad entry (or root-level entry) matching any of these may hold the ONLY copy of a
# pre-mutation file. The hub contract itself tells agents to `cp f /tmp/f.bak` for a revert test.
BACKUP_SUFFIXES = (".bak", ".original")
BACKUP_NAMES = ("before.txt", "after.txt", ".keep")
BACKUP_SUBSTRING = "pristine"  # case-insensitive; `fe-pristine/` and `agent.py.pristine` both match

# Root-level entries that are LIVE system state, not residue.
PROTECTED_NAMES = ("mcp-health-cache", "bundled-skills", "e2e-quota")
PROTECTED_SUFFIXES = (".hb", ".seen")

SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
KEEP_FILE = ".keep"
NAG_STAMP = ".scratch-nagged"
LOCK_PATH = "~/.claude/state/scratch-sweep.lock"

BRIEF_ROWS = 5  # the close-out shows this many candidates, then a count — never the whole table
DEFAULT_OLDER_THAN = "6h"
DEFAULT_DEAD_OLDER_THAN = "7d"
WALK_BUDGET = 60_000  # TOTAL stats across all entries, session/worktree mode only


def _env_int(name: str, default: int) -> int:
    """A stat-cap test seam: an unset or unparseable value is the default, never an error."""
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


WALK_DEADLINE_S = 8.0  # and the close-out's caller waits longer than this — see command_run.py
# `_scratch_advisory`. Truncating the close-out walk INSTEAD would have been the wrong fix: a
# truncated session walk has no CERTAIN candidates, so `--brief` prints nothing at all. Silence
# sooner is not an improvement over silence later; the caller has to wait.
HOOK_DEADLINE_S = 4.0  # measured: the largest live scratchpad's holder probe alone costs 2.2 s,
# and the SessionStart registration allows 10 s. At 1.0 s the budget was exhausted before the first
# stat on 3 of the 6 largest pads — by the DEADLINE, not the stat cap — so the advisory was
# structurally dead on exactly the sessions that needed it.
DU_DEADLINE_S = 10.0

RC_OK, RC_USAGE, RC_REFUSED = 0, 1, 2


@dataclass(frozen=True)
class Row:
    """One classified entry. `cls` decides removal; `reason` and `evidence` are why (constraint 2)."""

    path: str
    kind: str  # "entry" | "worktree" | "session" | "root"
    cls: str
    reason: str
    evidence: str = ""
    size_kb: int | None = None
    age_s: float | None = (
        None  # idle seconds, when the classifier computed one — the brief sorts on it
    )


# Only these are EVER removed, and the last three only behind their own explicit flag.
REMOVABLE = frozenset({"stale", "wt-removable", "wt-prunable", "dead"})
FLAG_GATED = {
    "wt-harness": "--include-harness",
    "holds-backups": "--include-backups",
    "dead-holds-backups": "--include-backups",
    "unowned": "--unowned-older-than",
}


# ── time, paths, small helpers ──────────────────────────────────────────────────────────────────
def _now() -> float:
    """The clock. `SCRATCH_SWEEP_NOW` is the test seam; production reads the real one."""
    raw = os.environ.get("SCRATCH_SWEEP_NOW")
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return time.time()


def parse_duration(text: str) -> float:
    """`6h` / `7d` / `90m` / `3600` → seconds. Raises ValueError on anything else.

    A non-finite or non-positive threshold makes EVERY entry stale — `--older-than 0` removed a
    directory written one second earlier (review F13) — so both are refused here, not downstream.
    """
    t = str(text).strip().lower()
    if not t:
        raise ValueError("empty duration")
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    value = float(t[:-1]) * units[t[-1]] if t[-1] in units else float(t)
    if not (value > 0) or value in (float("inf"),) or value != value:
        raise ValueError(f"a threshold must be a finite positive duration, got {text!r}")
    return value


def _scratch_root() -> Path:
    return Path(os.environ.get("SCRATCH_SWEEP_ROOT") or f"/tmp/claude-{os.getuid()}")


def _proc_root() -> Path:
    return Path(os.environ.get("FABRIK_PROC_ROOT") or "/proc")


def _lock_dir() -> Path:
    return Path(os.environ.get("CLAUDE_SOUND_LOCKDIR") or f"/tmp/claude-sound-locks-{os.getuid()}")


def _home() -> Path:
    return Path(os.environ.get("HOME") or str(Path.home()))


def _split_env_paths(name: str) -> list[Path] | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    return [Path(p) for p in raw.split(os.pathsep) if p]


def _dedup(paths: list[Path]) -> list[Path]:
    """Resolve then de-duplicate — `~/.claude-fleet/active` is a symlink to an account dir."""
    seen: dict[str, Path] = {}
    for p in paths:
        try:
            seen.setdefault(str(p.resolve()), p)
        except OSError:
            seen.setdefault(str(p), p)
    return list(seen.values())


def session_id(explicit: str | None) -> str:
    """`--session` → CLAUDE_SESSION_ID → CLAUDE_CODE_SESSION_ID.

    The Bash-tool shell carries an EMPTY `CLAUDE_SESSION_ID` but a populated
    `CLAUDE_CODE_SESSION_ID`, which is why both are read, in that order
    (`scripts/command_run.py::_session_id` uses the same chain).
    """
    return (
        (explicit or "").strip()
        or os.environ.get("CLAUDE_SESSION_ID", "").strip()
        or os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    )


def _is_backup_shape(name: str) -> bool:
    low = name.lower()
    return low.endswith(BACKUP_SUFFIXES) or low in BACKUP_NAMES or BACKUP_SUBSTRING in low


def _holds_backup(entry: Path) -> bool | None:
    """A backup shape ANYWHERE in the entry's tree — and the entry's OWN NAME is part of its tree.

    Without the own-name half, `pristine/` and `fe-pristine/` (names carrying the marker, contents
    that do not) read as ordinary residue and the operator's source baselines are removed.
    """
    if _is_backup_shape(entry.name):
        return True
    if entry.is_file():
        return False
    try:
        # onerror RAISES: the default swallows a scandir failure, which made this function's own
        # KEEP branch unreachable and let an unreadable subtree read as "holds no backup" (F9).
        def _boom(exc: OSError) -> None:
            raise exc

        for dirpath, dirnames, filenames in os.walk(entry, followlinks=False, onerror=_boom):
            if Path(dirpath) == entry / "scratchpad":
                # a run folder is marker-governed: inside a CONSUMED one a backup shape is disposable
                # by contract, and an ACTIVE one is kept whole anyway (plan P8, P10). Only the mint's
                # KEYED name directly in the session's OWN pad is one (`is_run_entry`, `run_entries`):
                # an agent's own `run-tests/`, `.trash-old/` or a nested `…/scratchpad/run-<key>/` is
                # ordinary scratch, and pruning those hid their backups and removed them (F11)
                dirnames[:] = [d for d in dirnames if not is_run_entry(Path(dirpath) / d)]
            for n in list(dirnames) + list(filenames):
                if _is_backup_shape(n):
                    return True
    except OSError:
        return None  # unreadable ⇒ UNKNOWN, which the caller maps to probe-error, never a claim
    return False


# ── the holder probe ────────────────────────────────────────────────────────────────────────────
def _real_uid(proc_root: Path, pid: str) -> int | None:
    """The REAL uid from `/proc/<pid>/status`, never `os.stat().st_uid`.

    `st_uid` on `/proc/<pid>` is the EFFECTIVE uid: pid 17559 `fusermount3` runs with real uid 1000
    and euid 0, so a stat-based test reads a same-uid process as foreign and silently ignores its
    gap. Measured 2026-09-08.
    """
    try:
        with open(proc_root / pid / "status", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("Uid:"):
                    return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return None


def _is_zombie(proc_root: Path, pid: str) -> bool:
    """`State: Z` in `/proc/<pid>/status` — exited, unreaped, holding nothing."""
    try:
        with open(proc_root / pid / "status", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("State:"):
                    return line.split()[1:2] == ["Z"]
    except OSError:
        return False
    return False


def probe_holders(
    targets: list[Path], proc_root: Path | None = None
) -> tuple[dict[str, str], list[str], bool]:
    """`({resolved target: "pid <n> <comm>"}, [same-uid pids whose /fd was unreadable], probe_ok)`.

    A match on `<target>/` as a prefix, so a descriptor opened deep inside the entry counts. A
    foreign-uid pid that denies `/fd` is NOT a gap — it cannot hold a descriptor under the 0700
    scratch root; counting those would report a gap on every run (150 of 152 deniers today).
    """
    proc_root = proc_root or _proc_root()
    me = os.getuid()
    prefixes = [(str(t.resolve()) if t.exists() else str(t), t) for t in targets]
    held: dict[str, str] = {}
    gaps: list[str] = []
    try:
        pids = [p for p in os.listdir(proc_root) if p.isdigit()]
    except OSError:
        # The whole probe is dead, not one pid. Both /proc-dependent liveness signals collapse
        # while the death signals survive — the same asymmetry the unreadable-root rule refuses
        # for sessions roots. Returning "no holders" here would have deleted a directory with an
        # OPEN fd inside it, and a LIVE session's dir in --dead (measured, review F2).
        return held, gaps, False
    if not pids:
        # A listable but pid-less /proc (a `hidepid` mount, a pid namespace, the test seam) is a
        # dead probe wearing a working one's clothes — the same liveness/death asymmetry (A3).
        return held, gaps, False
    for pid in pids:
        comm = ""
        links: list[str] = []
        try:
            comm = (proc_root / pid / "comm").read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            comm = "?"
        try:
            links.append(os.readlink(proc_root / pid / "cwd"))
        except OSError:
            pass
        try:
            fd_dir = proc_root / pid / "fd"
            for fd in os.listdir(fd_dir):
                try:
                    links.append(os.readlink(fd_dir / fd))
                except OSError:
                    continue
        except OSError:
            # Only a SAME-REAL-UID denial is a gap; anything else cannot reach the 0700 root. A
            # zombie denies `/fd` too but holds no descriptor at all (panel, 2026-10-15).
            if _real_uid(proc_root, pid) == me and not _is_zombie(proc_root, pid):
                gaps.append(f"{pid} ({comm})")
        for link in links:
            for prefix, target in prefixes:
                if link == prefix or link.startswith(prefix.rstrip("/") + "/"):
                    held.setdefault(str(target), f"pid {pid} {comm}")
    return held, gaps, True


# ── run-bound scratch: the marker and the ONE classifier (scratch lifecycle plan, P2) ───────────
# A run's bulky work lives in `<session dir>/scratchpad/run-<key>/`, which `command_run.py` mints at
# `start` with a `.owner` marker and marks at every close. Removal reads ONLY that marker plus the
# holder probe — never age, never a tree walk — so a multi-GB folder is judged in constant time.
OWNER_NAME = ".owner"
RUN_PREFIX = "run-"
TRASH_PREFIX = ".trash-"
RUN_STATES = ("running", "done", "resumable")
GRACE_FAST_S = 30 * 60  # a `done` run with no seat write after its close (the operator's 30 min)


def _grace_ceiling_s() -> float:
    """P1: 36 h unless the test seam says otherwise — a seat wrote after the close, or we cannot tell."""
    return float(_env_int("SCRATCH_RUN_GRACE_S", 129_600))


def _dead_heartbeat_s() -> float:
    """A `running` run in a session with a death signal is consumed only past this heartbeat age."""
    return float(_env_int("SCRATCH_RUN_HEARTBEAT_S", 604_800))


def _refuse_constant(name: str) -> float:
    raise ValueError(f"non-finite {name} in a run marker")


def _finite_float(text: str) -> float:
    """An overflowing literal (`-1e999`) parses to ±inf WITHOUT reaching `parse_constant`."""
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"non-finite {text} in a run marker")
    return value


def _finite_int(text: str) -> int:
    """An integer literal no float can hold: every time reader converts with `float()`, which
    raises OverflowError and aborted the sweep — refused here instead, like the other two."""
    value = int(text)
    try:
        float(value)
    except OverflowError:
        raise ValueError(
            f"an integer too large for a time in a run marker ({len(text)} digits)"
        ) from None
    return value


def read_owner(folder: Path) -> dict | None:
    """The parsed `.owner` marker; None when it is missing, unreadable or not a JSON object.

    `NaN` / `Infinity` / `-Infinity`, overflowing literals such as `-1e999` and integers no float can
    hold are refused (F10):
    `json.loads` accepts them, and a NaN or -inf time read as a past close or creation made a
    clobbered marker CONSUMED at every reader of it (`judge_run_folder`, `gap_keeps`,
    `write_size_report`). A marker nested past the recursion limit is refused too, never a crash
    that aborts the sweep. None is INV-1 doubt: kept, never removed.
    """
    try:
        text = (folder / OWNER_NAME).read_text(encoding="utf-8")
        data = json.loads(
            text, parse_constant=_refuse_constant, parse_float=_finite_float, parse_int=_finite_int
        )
    except (OSError, ValueError, RecursionError):
        return None
    return data if isinstance(data, dict) else None


@dataclass(frozen=True)
class RunFacts:
    """Everything the classifier reads about one run folder — gathered by the caller, judged here."""

    state: str | None
    closed_at: float | None
    heartbeat_age_s: float
    session_dead: bool  # no live signal AND a death signal (the heartbeat age is judged below)
    held: bool
    gaps: bool
    probe_ok: bool
    worktree: bool
    keep: bool
    sid_matches: bool = True  # a D3 (own-session) input only; D4 passes True (plan P6)
    seat_write_after_close: bool | None = None  # None = could not read → the 36 h ceiling (P13)


def classify_run_folder(f: RunFacts, now: float) -> tuple[str, str]:
    """`("active" | "consumed", reason)` — spec § Invariants, INV-1 first: any doubt is ACTIVE.

    Cobra (D-253): the cheap way to make this "remove more" is to drop an INV-1 condition; the
    partition test in tests/test_scratch_sweep_run_folders.py enumerates every state against an
    independent restatement of INV-1, so a dropped condition reads red, not faster.
    """
    if f.state not in RUN_STATES:
        return "active", "no readable marker, or an unknown state — never removed on doubt"
    if f.state == "resumable":
        return "active", "resumable — a quota-wall resume may still adopt it"
    if f.state == "running":
        if not f.session_dead:
            return "active", "running in a session with a live signal or no death signal"
        if f.heartbeat_age_s <= _dead_heartbeat_s():
            return "active", "running; the session looks dead but the heartbeat is recent"
    if f.state == "done":
        if f.closed_at is None:
            return "active", "done without a close time — never removed on doubt"
        grace = GRACE_FAST_S if f.seat_write_after_close is False else _grace_ceiling_s()
        if now - f.closed_at < grace:
            return "active", f"closed {_human(now - f.closed_at)} ago, inside its grace"
    if not f.probe_ok:
        return "active", "the holder probe could not complete"
    if f.held:
        return "active", "held by a live process (fd or cwd inside)"
    if f.gaps:
        return "active", "a same-uid process's /fd could not be read"
    if f.worktree:
        return "active", "holds a registered git worktree"
    if f.keep:
        return "active", f"holds its own {KEEP_FILE}"
    if not f.sid_matches:
        return "active", "the marker's session differs from its directory"
    if f.state == "running":
        return "consumed", "running, but its session is dead and its heartbeat is stale"
    closed_ago = now - f.closed_at if f.closed_at is not None else 0.0  # 0.0 is a time, not None
    return "consumed", f"done, closed {_human(closed_ago)} ago, past its grace"


# ── run-bound scratch: gathering the facts and consuming (plan Phase B, D3 and D4) ─────────────
RUN_LOCK_NAME = ".run-folders.lock"  # beside scratchpad/, never inside it (P3)
GAP_CLOCK_MARGIN_S = 300.0  # WSL's clock can jump after a suspend — a margin on the safe side
# A run folder's own mtime later than its close by more than this: an entry was created or removed in
# it after the close — still in use (W-9f3f097c). The close's own marker write (tmp + os.replace)
# lands about 0.1 ms after `closed_at` (measured over 200 closes: median 0.1 ms, tail ~10 ms); never
# GAP_CLOCK_MARGIN_S, which would hide a write made minutes after a close.
WRITE_AFTER_CLOSE_MARGIN_S = 5.0


def gap_starts(gaps: list[str], proc_root: Path | None = None) -> list[float | None]:
    """The start epoch of each gap pid (`"<pid> (<comm>)"`) — `stat` stays readable when `/fd` is
    not. None for any pid whose start cannot be computed; a pid that has EXITED since the probe is
    dropped — it holds nothing (measured: transient same-uid gaps in 2 of 8 live probes)."""
    proc_root = proc_root or _proc_root()
    boot = _btime()
    try:
        hz = os.sysconf("SC_CLK_TCK")
    except (ValueError, OSError):
        hz = 0
    out: list[float | None] = []
    for g in gaps:
        start: float | None = None
        try:
            pid = int(g.split()[0])
            if not (proc_root / str(pid)).exists():
                continue
            ticks = _proc_start_ticks(proc_root, pid)
            if boot is not None and ticks is not None and hz > 0:
                start = boot + int(ticks) / hz
        except (ValueError, IndexError):
            start = None
        out.append(start)
    return out


def _usable_time(value: object) -> TypeGuard[float]:
    """A marker time a comparison can use: a number, not a bool (`True` is an int), and finite (NaN
    passes a type guard and every comparison with it reads False) — W-a39d4c86. An int always compares
    exactly, so it is usable at any size (`math.isfinite` raises OverflowError on one no float holds)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    return isinstance(value, int) or math.isfinite(value)


def _created_for(folder: Path, owner: dict | None) -> object:
    """The `created` a gap is judged against. A `.trash-*` whose marker carries no usable one (an
    interrupted rmtree may have taken it) falls back to the folder's ctime: its last entry change —
    the rename that made it, or later if an interrupted rmtree unlinked entries since. Either way it
    is at or after the moment the folder was judged CONSUMED, so a process that started before it
    never owned the run (INV-2)."""
    created = (owner or {}).get("created")
    if folder.name.startswith(TRASH_PREFIX) and not _usable_time(created):
        with contextlib.suppress(OSError):
            created = folder.lstat().st_ctime
    return created


def gap_keeps(starts: list[float | None], created: object, now: float) -> bool:
    """Does a same-uid `/proc` gap keep a run folder? Only a gap process that STARTED at or after
    the folder's marker was written (less the clock margin): a process already running before the
    run began cannot be one of its writers, and this box carries three such daemons permanently
    (sd-pam, gpg-agent, a setuid fusermount3), which kept every folder for ever under the spec's
    bare "a non-empty gaps list". Any unknown — a start, or a missing, non-numeric, non-finite or
    future `created` — keeps (the split panel's interim ruling; the decision row names both verdicts).

    Cobra (D-253): an EARLIER `created` makes every gap read newer and so keeps more; the cheap way
    to make this keep nothing is to move `created` LATER than the run's true start — to the present,
    or forward inside the clock margin (further ahead is "future" and keeps). Residual: any `created`
    in (true start, now + margin] is indistinguishable from a younger run or clock skew, so this rule
    cannot see it; the writers that heal a marker therefore stamp the run's true start (D-902).
    Dropping `created`, or making it NaN, a bool or text, KEEPS; a test pins each case (W-a39d4c86
    corrected the direction this note first named).
    """
    if not starts:
        return False
    if not _usable_time(created) or created > now + GAP_CLOCK_MARGIN_S:
        return True
    # `s + margin >= created`, not `s >= created - margin`: a huge int `created` is only ever COMPARED
    # (exact for any size), never converted to a float by arithmetic (OverflowError)
    # an unusable start (None, or NaN from a NaN boot time) is an UNKNOWN start: INV-1 doubt keeps
    return any(not _usable_time(s) or s + GAP_CLOCK_MARGIN_S >= created for s in starts)


# the mint's key is `<command>-<started_at>-<6 hex>` (P4); `started_at` is `%Y-%m-%dT%H:%M:%S%z`
# sanitised, so `2026-10-15T05-40-42-0300` — a name merely ending in a hex-only word never matches
RUN_KEY_RE = re.compile(
    r"^(?:run|\.trash)-.+-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{4}-[0-9a-f]{6}$"
)


def is_run_entry(entry: Path) -> bool:
    """A `run-<key>` folder, or the `.trash-<key>` an interrupted removal left — marker-governed
    (P8). Only the mint's keyed name counts: an agent's own `run-tests/` or `.trash-old/` stays an
    untagged entry, judged by age as before — never removed by name, never kept for ever."""
    return bool(RUN_KEY_RE.match(entry.name)) and not entry.is_symlink() and entry.is_dir()


def run_entries(session_dir: Path) -> list[Path]:
    """The run folders (and `.trash-*` leftovers) directly under `<session dir>/scratchpad/`."""
    try:
        return sorted(
            Path(e.path)
            for e in os.scandir(session_dir / "scratchpad")
            if is_run_entry(Path(e.path))
        )
    except OSError:
        return []


def write_owner(folder: Path, fields: dict) -> bool:
    """`command_run.py`'s marker write, mirrored: temp file + `os.replace`, False on any OSError."""
    target = folder / OWNER_NAME
    tmp = folder / f"{OWNER_NAME}.{os.getpid()}.tmp"
    try:
        tmp.write_text(json.dumps(fields, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, target)
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink()
        return False
    return True


def _seat_write_after_close(sid: str, closed_at: float, tx_dirs: list[Path] | None) -> bool | None:
    """P13: was any seat transcript of this session written after the close? None = cannot tell."""
    dirs = transcript_dirs() if tx_dirs is None else tx_dirs
    if not any(globmod.glob(str(root / "*" / f"{sid}.jsonl")) for root in dirs):
        return None  # the session's own transcript is not visible: "no seat wrote" is unknowable
    try:
        for root in dirs:
            for path in globmod.glob(str(root / "*" / sid / "subagents" / "agent-*.jsonl")):
                if os.stat(path).st_mtime > closed_at:
                    return True
    except OSError:
        return None
    return False


GIT_POINTER_SCAN_BUDGET = 200_000  # directory entries read at depths 0-3 before the scan stops
SCAN_BUDGET_KEPT = "the .git pointer scan stopped at its budget — a worktree may be unseen"


def git_pointer_files(folder: Path, max_depth: int = 3) -> list[Path]:
    """The list form of :func:`git_pointer_scan`, the shape `command_run.py`'s resume adoption
    reads (a NON-EMPTY answer refuses the move): an incomplete scan adds a sentinel path, so a
    folder the scan could not finish is never moved (doubt keeps)."""
    found, complete = git_pointer_scan(folder, max_depth)
    return found if complete else [*found, folder / ".git-scan-incomplete"]


def git_pointer_scan(
    folder: Path, max_depth: int = 3, budget: int | None = None
) -> tuple[list[Path], bool]:
    """`(every .git pointer FILE found, complete?)` at depths 0-`max_depth` under the folder
    (hidden directories included, symlinks never followed) whose gitdir lies OUTSIDE the folder —
    a worktree or submodule some repository elsewhere refers to. A `.git` DIRECTORY (a plain clone)
    and a pointer into the folder itself are self-contained: nothing outside refers to them, so they
    are scratch. An unreadable pointer counts (doubt keeps).

    BOUNDED (W-c0a1d324 F2): at most `budget` entries (default `SCRATCH_SWEEP_GIT_SCAN_BUDGET`, else
    `GIT_POINTER_SCAN_BUDGET`) are read — a wide folder cost a full scan at classification. Past
    the budget the answer is INCOMPLETE and the caller keeps the folder (doubt keeps); the budget
    is set well above a staged tree's depth-3 breadth, so a big seat copy is still judged."""
    if budget is None:
        budget = _env_int("SCRATCH_SWEEP_GIT_SCAN_BUDGET", GIT_POINTER_SCAN_BUDGET)
    real = os.path.realpath(folder)
    found: list[Path] = []
    level = [folder]
    seen = 0
    for _depth in range(max_depth + 1):
        nxt: list[Path] = []
        for d in level:
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            seen += len(entries)
            if seen > budget:
                return found, False
            for e in entries:
                if e.name == ".git" and e.is_file(follow_symlinks=False):
                    try:
                        text = Path(e.path).read_text(encoding="utf-8", errors="replace")
                        target = text.split("gitdir:", 1)[1].strip().splitlines()[0]
                        resolved = os.path.realpath(os.path.join(d, target))
                        inside = resolved == real or resolved.startswith(real + "/")
                    except (OSError, IndexError):
                        inside = False
                    if not inside:
                        found.append(Path(e.path))
                elif e.is_dir(follow_symlinks=False) and e.name != ".git":
                    nxt.append(Path(e.path))
        level = nxt
    return found, True


def _worktrees_under(folder: Path, repo: str) -> tuple[list[dict], list[dict], bool]:
    """`(registrations inside the folder, every registration, ok)` — P7. `ok` False means the list
    could not be read on a repo that resolves, which reads ACTIVE. A `repo` that no longer resolves
    falls back to a `.git` entry at depths 1-3 — an unjudgeable worktree, so the folder is kept."""
    real = os.path.realpath(folder)
    if repo and Path(repo).is_dir():
        try:
            proc = subprocess.run(
                ["git", f"--git-dir={repo}", "worktree", "list", "--porcelain"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="surrogateescape",
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return [], [], False
        if proc.returncode != 0:
            return [], [], False
        regs = _parse_worktree_porcelain(proc.stdout)
        inside = [
            e
            for e in regs
            if e.get("worktree")
            and (
                os.path.realpath(e["worktree"]) == real
                or os.path.realpath(e["worktree"]).startswith(real + "/")
            )
        ]
    else:
        regs, inside = [], []
    # a pointer this repo does not list — another repo's worktree, or a repo that no longer
    # resolves (depths 0-3, hidden directories too): unjudgeable, so the folder is kept
    known = {os.path.realpath(e["worktree"]) for e in inside}
    pointers, complete = git_pointer_scan(folder)
    for pointer in pointers:
        if os.path.realpath(pointer.parent) not in known:
            inside.append({"worktree": str(pointer.parent), "unjudgeable": "1"})
    if not complete:  # the scan stopped at its budget: an unseen pointer may exist, so it keeps
        inside.append({"worktree": str(folder), "unjudgeable": "3"})
    if not repo or not Path(repo).is_dir():
        for e in inside:
            if e.get("unjudgeable") != "3":  # an unfinished scan says so, whatever the repo
                e["unjudgeable"] = "2"  # the marker's repo itself no longer resolves
    return inside, regs, True


def _worktree_removable(entry: dict, regs: list[dict], repo: str) -> tuple[bool, str]:
    """P14: may this worktree inside a CONSUMED folder be removed? Never through
    `_classify_worktree` (it calls every detached tree `unclassified`, every tree `wt-foreign`)."""
    path = Path(entry["worktree"])
    if entry.get("unjudgeable") == "2":
        return False, "its marker's repository no longer resolves"
    if entry.get("unjudgeable") == "3":
        return False, SCAN_BUDGET_KEPT
    if entry.get("unjudgeable"):
        return False, "a worktree pointer the marker's repository does not list"
    if "locked" in entry:
        return False, "locked"
    if "prunable" in entry or not path.exists():
        # nothing on disk to lose; the registration is left for git's own prune (never run
        # repo-wide from here)
        return True, "its directory is already gone — a stale registration"
    branch = entry.get("branch", "").removeprefix("refs/heads/")
    if branch:
        main_path = Path(regs[0].get("worktree", "")) if regs else path
        rc, out = _git(main_path, "branch", "--show-current")
        target = out.strip() if rc == 0 else ""
        if not target:
            return False, "the main checkout has no branch to merge against"
        stashed, detached_stash = _stash_branches(main_path)
        verdict, reason, _ = _worktree_chain(
            path, entry, main_path, target, branch, stashed, detached_stash, {}
        )
        return verdict == "wt-removable", reason
    rc, out = _git(path, "status", "--porcelain")
    if rc != 0 or out.strip():
        return False, "detached, with uncommitted work or an unreadable status"
    head = entry.get("HEAD", "")
    rc, out = _git(Path(repo), "for-each-ref", "--contains", head, "--format=%(refname)")
    if rc != 0 or not head or not out.strip():
        return False, "detached, and no ref contains its HEAD — removing it could lose a commit"
    return True, "detached, clean, and a ref contains its HEAD"


def _marker_fingerprint(folder: Path) -> str:
    """The marker's bytes and mtime — any rewrite or heartbeat between classification and removal
    changes it."""
    try:
        st = (folder / OWNER_NAME).stat()
        digest = hashlib.blake2b((folder / OWNER_NAME).read_bytes(), digest_size=6).hexdigest()
        return f"marker={st.st_mtime_ns}:{digest}"
    except OSError:
        return "marker=none"


def _close_is_vouched(created: object, closed_at: float, now: float) -> bool:
    """D-900 (W-de2c34c1, F13): a `done` marker's close is believed only against a sane creation
    time — `created` numeric (not a bool), not in the future, and the close not before it (less the
    clock margin). A clobbered `closed_at` of 0 or -1e308 otherwise read as a long-past close.

    Applied in `judge_run_folder`, never in `classify_run_folder`: the `.trash-*` path builds
    `closed_at` 0.0 by construction and would be kept for ever (INV-2). Cobra (D-253): the cheap
    way past it is to clobber or drop `created` too — so a missing or bad `created` is doubt as
    well, mirroring `gap_keeps` (D-877/D-878). Residual, wider than D-900's row states (review of
    b5c1abd69): ANY `closed_at` in [`created` − margin, now − grace] is believed, so a co-clobber
    of both fields within the margin (created 0 / closed 0, or both -1e308) or a `closed_at`
    backdated to `created` still reads as a past close. The writers that heal a marker
    (`command_run._mark_run_scratch`, `_retire`) stamp a missing `created`, so a legitimate run
    is never kept for ever by this rule.
    """
    if not _usable_time(created):  # missing, text, a bool, or NaN/±inf (W-a39d4c86's one guard)
        return False
    if created > now + GAP_CLOCK_MARGIN_S:
        return False
    if closed_at > now + GAP_CLOCK_MARGIN_S:
        return False  # a close in the future is no close; kept either way, but the report names it
    return (
        closed_at + GAP_CLOCK_MARGIN_S >= created
    )  # compared, never converted: a huge int is exact


def _done_close_is_vouched(owner: dict, now: float) -> bool:
    """A `done` marker's close, as `judge_run_folder` reads it: numeric (not a bool) AND vouched."""
    closed = owner.get("closed_at")
    if not isinstance(closed, int | float) or isinstance(closed, bool):
        return False
    return _close_is_vouched(owner.get("created"), float(closed), now)


def _written_after_close(folder: Path, closed_at: float, now: float) -> float | None:
    """When an entry was created or removed in ``folder`` after its close: the folder's own mtime
    (its last top-level change), else None. Doubt answers ``closed_at`` — the long grace from the
    close, bounded: an unreadable stat, and an mtime further ahead of ``now`` than the clock margin
    (a `touch -d` or a clock jump would otherwise keep the folder until that future date). One stat,
    never a walk — so a write that only modifies an existing file, or lands inside an existing
    subfolder, is not seen (W-9f3f097c, stated in docs/workstation/cleanup-automation.md)."""
    try:
        mtime = folder.stat().st_mtime
    except OSError:
        return closed_at
    if not math.isfinite(mtime) or mtime > now + GAP_CLOCK_MARGIN_S:
        return closed_at
    return mtime if mtime > closed_at + WRITE_AFTER_CLOSE_MARGIN_S else None


def _in_use_since_close(folder: Path, owner: dict | None, now: float) -> bool:
    """The removal-time re-check of the write-after-close rule: a `done` folder whose last top-level
    change is still inside the long grace. Re-applies the rule, never compares two mtimes — a folder
    consumed because its last write is itself past the grace still goes."""
    if folder.name.startswith(TRASH_PREFIX):
        return False  # the judge consumed it by name alone ("left by an interrupted removal")
    raw = (owner or {}).get("closed_at")
    if (
        (owner or {}).get("state") != "done"
        or not isinstance(raw, int | float)
        or isinstance(raw, bool)
    ):
        return False
    if not math.isfinite(raw):
        return False
    written = _written_after_close(folder, float(raw), now)
    return written is not None and now - max(float(raw), written) < _grace_ceiling_s()


def judge_run_folder(
    folder: Path,
    sid: str,
    now: float,
    *,
    session_dead: bool,
    held: dict[str, str],
    gaps: list[float | None],
    probe_ok: bool,
    tx_dirs: list[Path] | None = None,
    check_sid: bool = True,
) -> Row:
    """One run folder → a `kept` or `consumed` row; `classify_run_folder` decides, this gathers.

    `check_sid` is D3's own-session input (P6) — D4 judges by marker state alone. The `git worktree
    list` runs only for a folder that would otherwise be consumed: it is the one costly fact.
    """
    p = str(folder)
    is_held = p in held or os.path.realpath(p) in held
    owner = read_owner(folder)
    created = _created_for(folder, owner)
    gap = gap_keeps(gaps, created, now)
    if folder.name.startswith(TRASH_PREFIX):
        # already judged CONSUMED before the crash that left it — only a holder can keep it now
        facts = RunFacts("done", 0.0, 0.0, True, is_held, gap, probe_ok, False, False, True, False)
        verdict, reason = classify_run_folder(facts, now)
        if verdict == "consumed":
            reason = "left by an interrupted removal"
        cls = "consumed" if verdict == "consumed" else "kept"
        return Row(p, "run", cls, reason, _marker_fingerprint(folder))
    state = owner.get("state") if owner else None
    raw_closed = (owner or {}).get("closed_at")
    closed_at = (
        float(raw_closed)
        if isinstance(raw_closed, int | float) and not isinstance(raw_closed, bool)
        else None
    )
    if closed_at is not None and not _close_is_vouched(created, closed_at, now):
        closed_at = None  # D-900: a close the marker cannot vouch for is unknown — INV-1, ACTIVE
    try:
        heartbeat_age = now - (folder / OWNER_NAME).stat().st_mtime
    except OSError:
        heartbeat_age = 0.0  # unknowable reads recent — a `running` folder stays ACTIVE
    try:
        keep = (folder / KEEP_FILE).exists()
    except OSError:
        keep = True
    seat = (
        _seat_write_after_close(sid, closed_at, tx_dirs)
        if state == "done" and closed_at is not None
        else None
    )
    # W-9f3f097c: an entry made in the folder after its close is a folder still in use — the long
    # grace, counted from that last top-level change rather than from the close
    grace_from = closed_at
    written = (
        _written_after_close(folder, closed_at, now)
        if state == "done" and closed_at is not None
        else None
    )
    if written is not None and closed_at is not None:
        seat = True
        grace_from = max(closed_at, written)
    facts = RunFacts(
        state=state if isinstance(state, str) else None,
        closed_at=grace_from,
        heartbeat_age_s=heartbeat_age,
        session_dead=session_dead,
        held=is_held,
        gaps=gap,
        probe_ok=probe_ok,
        worktree=False,
        keep=keep,
        sid_matches=(not check_sid) or (owner or {}).get("sid") == sid,
        seat_write_after_close=seat,
    )
    verdict, reason = classify_run_folder(facts, now)
    if (
        written is not None
        and closed_at is not None
        and reason.startswith(("done, closed", "closed"))
    ):
        if written != closed_at:  # the grace ran from the last write: say so, never "closed"
            reason = reason.replace("closed", "last written", 1) + " (written into after its close)"
        else:
            reason += " (its folder's time could not be trusted — the long grace)"
    evidence = _marker_fingerprint(folder)
    if verdict == "consumed":
        inside, regs, ok = _worktrees_under(folder, str((owner or {}).get("repo") or ""))
        if not ok:
            return Row(p, "run", "kept", "`git worktree list` failed — never removed on doubt")
        for wt in inside:
            removable, why = _worktree_removable(wt, regs, str((owner or {}).get("repo") or ""))
            if not removable:
                if wt.get("unjudgeable") == "3":  # no worktree is known — the scan did not finish
                    return Row(p, "run", "kept", SCAN_BUDGET_KEPT, why)
                return Row(p, "run", "kept", f"holds a registered worktree {wt['worktree']}", why)
        if inside:
            reason += f"; its {len(inside)} worktree(s) are removable and go first"
        return Row(p, "run", "consumed", reason, evidence)
    return Row(p, "run", "kept", reason, evidence)


def plan_run_folders(
    session_dirs: list[Path],
    now: float,
    *,
    dead_of=None,
    proc_root: Path | None = None,
    tx_dirs: list[Path] | None = None,
    check_sid: bool = True,
) -> list[Row]:
    """Judge every run folder under these session directories with ONE holder probe (which also
    covers each session directory, for `dead_of`'s live signal). Read-only."""
    by_dir = {d: run_entries(d) for d in session_dirs}
    by_dir = {d: es for d, es in by_dir.items() if es}
    if not by_dir:
        return []
    targets = list(by_dir) + [e for es in by_dir.values() for e in es]
    held, gaps, probe_ok = probe_holders(targets, proc_root)
    starts = gap_starts(gaps, proc_root)
    rows: list[Row] = []
    for d, entries in by_dir.items():
        dead = bool(dead_of(d, held)) if dead_of is not None else False
        for e in entries:
            rows.append(
                judge_run_folder(
                    e,
                    d.name,
                    now,
                    session_dead=dead,
                    held=held,
                    gaps=starts,
                    probe_ok=probe_ok,
                    tx_dirs=tx_dirs,
                    check_sid=check_sid,
                )
            )
    return rows


def _rmtree_gone_ok(path: Path) -> None:
    """`shutil.rmtree` where a child that vanished mid-removal is not an error (P3: a D3 and the
    nightly D4 may race on one folder — 3.12's rmtree does not ignore it for children)."""

    def _onexc(_fn: object, _path: str, exc: BaseException) -> None:
        if not isinstance(exc, FileNotFoundError):
            raise exc

    try:
        shutil.rmtree(path, onexc=_onexc)
    except PermissionError:
        _own_tree(path)
        shutil.rmtree(path, onexc=_onexc)


def apply_run_rows(rows: list[Row], out=None, proc_root: Path | None = None) -> int:
    """Remove the `consumed` rows: holder re-probe, worktrees first (P14), `os.rename` to
    `.trash-<key>`, then the walk-free `rmtree`. Never reads a folder's age; per-row errors."""
    out = out or sys.stdout  # resolved per call: a default bound at import misses a swapped stdout
    targets = [Path(r.path) for r in rows if r.cls == "consumed"]
    if not targets:
        return 0
    held_now, gaps_now, probe_ok = probe_holders(targets, proc_root)
    if not probe_ok:
        print("REFUSED — the /proc holder probe went unreadable; no run folder removed", file=out)
        return 0
    starts_now = gap_starts(gaps_now, proc_root)
    removed = 0
    for r in rows:
        if r.cls != "consumed":
            continue
        path = Path(r.path)
        if r.path in held_now or os.path.realpath(r.path) in held_now:
            print(f"KEPT {r.path} — a holder appeared since classification", file=out)
            continue
        if not path.exists():
            print(f"gone — skipped {r.path}", file=out)
            continue
        # re-checked at removal time: the marker (bytes + mtime), a `.keep`, a new gap (R1-3)
        owner = read_owner(path)
        if _marker_fingerprint(path) != r.evidence:
            print(f"KEPT {r.path} — its marker changed since classification", file=out)
            continue
        if (path / KEEP_FILE).exists():
            print(f"KEPT {r.path} — a {KEEP_FILE} appeared since classification", file=out)
            continue
        if _in_use_since_close(path, owner, _now()):
            print(f"KEPT {r.path} — written into since its close (W-9f3f097c)", file=out)
            continue
        created = _created_for(path, owner)
        if gap_keeps(starts_now, created, _now()):
            print(f"KEPT {r.path} — an unreadable process appeared since classification", file=out)
            continue
        trash = path
        if path.name.startswith(RUN_PREFIX):
            repo = str((owner or {}).get("repo") or "")
            inside, regs, ok = _worktrees_under(path, repo)
            if not ok:
                print(f"KEPT {r.path} — `git worktree list` failed at removal time", file=out)
                continue
            blocked = ""
            for wt in inside:
                removable, why = _worktree_removable(wt, regs, repo)
                rc = 0
                # a prunable registration (its `.git` file or its directory gone) cannot be
                # removed by git — the tree, if any, is a broken one inside a consumed folder
                if removable and "prunable" not in wt and Path(wt["worktree"]).exists():
                    rc, msg = _git(Path(repo), "worktree", "remove", wt["worktree"])
                    why = msg.strip() or why
                if not removable or rc != 0:
                    blocked = f"{wt['worktree']} ({why})"
                    break
            if blocked:
                print(f"KEPT {r.path} — holds a registered worktree {blocked}", file=out)
                continue
            if inside:
                # `git worktree remove` can take seconds: re-probe this folder before the rename
                held_again, _g, ok_again = probe_holders([path], proc_root)
                if not ok_again or r.path in held_again or os.path.realpath(r.path) in held_again:
                    print(
                        f"KEPT {r.path} — a holder appeared during the worktree removal", file=out
                    )
                    continue
            trash = path.with_name(TRASH_PREFIX + path.name[len(RUN_PREFIX) :])
            try:
                os.rename(path, trash)
            except FileNotFoundError:
                print(f"gone — skipped {r.path}", file=out)
                continue
            except OSError as exc:
                print(f"FAILED {r.path} ({exc.errno}: {exc.strerror})", file=out)
                continue
        try:
            _rmtree_gone_ok(trash)
        except OSError as exc:
            print(f"FAILED {trash} ({exc.errno}: {exc.strerror})", file=out)
            continue
        removed += 1
        print(f"REMOVED {r.path} (consumed, {r.reason})", file=out)
    return removed


def _session_dead_for_runs(
    sid_dir: Path,
    by_sid: dict[str, list[dict]],
    tx_dirs: list[Path],
    held: dict[str, str],
    proc_root: Path,
    now: float,
    older_than_s: float,
) -> bool:
    """P9: no live signal AND a death signal — without the idleness walk, which comes back
    `unclassified` on exactly the sessions whose `running` folders this plan exists to remove."""
    sid = sid_dir.name
    records = by_sid.get(sid, [])
    if live_record(records, proc_root) is not None or _selfwatch_held(sid):
        return False
    if str(sid_dir) in held or os.path.realpath(sid_dir) in held:
        return False
    if records:
        return True  # its sessions file names a pid that is gone
    tx_age = _transcript_age(sid, tx_dirs, now)
    return tx_age is not None and tx_age > older_than_s


def _resplit_survivors(rows: list[Row], out=None) -> list[Row]:
    """After the run pass: a dead session row whose directory still holds a run folder (one the
    apply-time re-check KEPT — a changed marker, a holder, a failed worktree removal) is split
    rather than removed whole, so INV-1 holds past classification, not only at it."""
    out = out or sys.stdout
    result: list[Row] = []
    for r in rows:
        if (
            r.kind == "session"
            and r.cls in ("dead", "dead-holds-backups")
            and run_entries(Path(r.path))
        ):
            print(
                f"SPLIT {r.path} — a run folder survived the run pass; the directory stays",
                file=out,
            )
            result.extend(_split_dead_session(r, Path(r.path)))
        else:
            result.append(r)
    return result


def _split_dead_session(row: Row, sid_dir: Path) -> list[Row]:
    """A dead session that still holds an ACTIVE run folder: the directory stays, every other entry
    goes — a keyed `run-<key>`/`.trash-<key>` is never listed here, marked or not (plan B5); an
    agent's own `run-tests/` is an ordinary entry (P8)."""
    out = [Row(row.path, "session", "kept", "holds an active run folder", row.reason)]

    def _entry(e: Path) -> Row:
        backup = _holds_backup(e)
        if backup is None:
            return Row(str(e), "entry", "unclassified", "part of its tree is unreadable")
        if backup:
            return Row(str(e), "entry", "dead-holds-backups", "dead session; holds a backup shape")
        return Row(
            str(e), "entry", "dead", "dead session; the directory holds an active run folder"
        )

    try:
        for child in sorted(sid_dir.iterdir()):
            if child.name == "scratchpad" and child.is_dir() and not child.is_symlink():
                for e in sorted(child.iterdir()):
                    if not is_run_entry(e):  # the mint's keyed name only: `run-tests/` goes (P8)
                        out.append(_entry(e))
            else:
                out.append(_entry(child))
    except OSError:
        return [
            Row(row.path, "session", "unclassified", "unreadable while splitting a dead session")
        ]
    return out


def _retire(root: Path, sid: str, name: str, cwd: str | None) -> int:
    """P12: end one `resumable` folder's resume by hand — its marker reads `done`, nothing else."""
    if not name.startswith(RUN_PREFIX) or "/" in name or name in (".", ".."):
        print(f"refusing --retire {name!r} — name one run-<key> folder", file=sys.stderr)
        return RC_USAGE
    dirs = find_session_dirs(root, sid, cwd)
    folder = dirs[0] / "scratchpad" / name if len(dirs) == 1 else None
    if folder is None or folder.is_symlink() or not folder.is_dir():
        print(f"REFUSED — no run folder {name} in this session's scratchpad")
        return RC_REFUSED
    owner = read_owner(folder)
    if owner is None or owner.get("sid") != sid:
        print(f"REFUSED — {name}'s marker is unreadable or names another session")
        return RC_REFUSED
    if owner.get("state") != "resumable":
        # it ends a RESUME; a running run closes through its own record, never through here
        print(
            f"REFUSED — {name} is {owner.get('state')!r}, not resumable; --retire ends a resume only"
        )
        return RC_REFUSED
    now = _now()
    owner.update({"state": "done", "closed_at": now})
    if not write_owner(folder, owner):
        print(f"FAILED — cannot rewrite {folder / OWNER_NAME}")
        return RC_REFUSED
    if not _done_close_is_vouched(owner, now):
        # no `created` to vouch the close (D-900), and none is invented: a stamped `now` would strip
        # `gap_keeps`' protection from the run's writers (review of 2dd7ac9e6, A1) — so say the truth
        print(
            f"RETIRED {folder} — marked done, but its creation time is unknown or bad, so every "
            f"sweep keeps it (D-900); inspect, then remove it by hand: rm -rf {folder}"
        )
        return RC_OK
    print(f"RETIRED {folder} — marked done; it is removed after its grace")
    return RC_OK


def run_run_folders_mode(args: argparse.Namespace, sid: str) -> int:
    """D3: this session's run folders, judged by marker, removed walk-free under the PER-SESSION
    lock (never the global one — P3). `_own_session` is not applied: removal is marker-governed,
    so who runs it cannot make an ACTIVE folder removable (P16)."""
    root = _scratch_root()
    if args.retire:
        return _retire(root, sid, args.retire, args.cwd)
    dirs = find_session_dirs(root, sid, args.cwd)
    if len(dirs) != 1:
        print(f"run folders: {len(dirs)} session directories for {sid} — nothing done")
        return RC_OK
    sdir = dirs[0]
    if not args.apply:
        rows = plan_run_folders([sdir], _now(), proc_root=_proc_root())
        print(render(rows, allowed={"consumed"}) if rows else "no run folders")
        return RC_OK
    with _Lock(sdir / RUN_LOCK_NAME) as got:
        if not got:
            print("another run-folder sweep holds this session's lock — nothing done (rc 0)")
            return RC_OK
        rows = plan_run_folders([sdir], _now(), proc_root=_proc_root())
        if rows:
            print(render(rows, allowed={"consumed"}))
            apply_run_rows(rows, proc_root=_proc_root())
    return RC_OK


# ── the freshness walk ──────────────────────────────────────────────────────────────────────────
class WalkBudget:
    """A TOTAL stat budget shared across entries, plus a wall-clock deadline.

    It covers the FRESHNESS walk only. The backup scan (`_holds_backup`) is deliberately outside
    it, exactly as `--dead`'s is: a truncated backup scan would report "no backup" and hand a
    revert-test baseline to `--apply`. Measured cost on the largest live scratchpad (54,647 tree
    entries): 0.06 s when a backup is found early, 0.54 s for the budgeted walk beside it.

    Per-entry was the wrong axis: the cost is the sum, and the largest live scratchpad walks ~55 k
    entries. On exhaustion the entry being walked is `probe-error` (a truncated walk has neither a
    trustworthy newest-mtime nor a complete backup scan) and the REMAINING entries are `fresh`.
    """

    def __init__(self, stats: int = WALK_BUDGET, deadline_s: float = WALK_DEADLINE_S) -> None:
        self.left = stats
        self.until = time.monotonic() + deadline_s
        self.exhausted = False

    def spend(self, n: int = 1) -> bool:
        self.left -= n
        if self.left <= 0 or time.monotonic() > self.until:
            self.exhausted = True
            return False
        return True

    @property
    def spent_out(self) -> bool:
        """True once the budget is gone — the caller uses it to class REMAINING entries `fresh`."""
        return self.exhausted


def newest_mtime(
    entry: Path, budget: WalkBudget, *, skip_run_folders: bool = False
) -> tuple[float, bool]:
    """`(newest mtime in the entry's tree, complete?)`.

    NOT the directory's own mtime: a directory's mtime moves only when a direct child is added,
    removed or renamed — a file rewritten in place ten levels down never touches it, so an entry
    under active work read `stale` (measured; plan review pass 2).

    ``skip_run_folders`` (the dead-session idleness walk, spec D4): a marker-governed run folder (a
    direct child of `<entry>/scratchpad/` that passes `is_run_entry`) is never entered — only its
    own mtime and `.owner` are read; it is classified from its marker, and walking a
    multi-GB seat copy spent the walk's budget, so a dead session read "cut short" and was never
    removed (W-c0a1d324 F9).
    """
    try:
        newest = entry.lstat().st_mtime
    except OSError:
        return 0.0, False
    if not entry.is_dir() or entry.is_symlink():
        return newest, True
    try:

        def _boom(exc: OSError) -> None:
            raise exc

        scratchpad = os.path.join(entry, "scratchpad")
        for dirpath, dirnames, filenames in os.walk(entry, followlinks=False, onerror=_boom):
            if skip_run_folders and dirpath == scratchpad:
                # ONLY the marker-governed run folders — a direct child of `<sid>/scratchpad/` the
                # sweep judges by its `.owner` (`is_run_entry`). A run-named directory anywhere else
                # (a copy, an agent's own) is ordinary content whose activity is the session's
                # sign of life, so it is walked as before (W-c0a1d324 F9 review)
                runs = [d for d in dirnames if is_run_entry(Path(dirpath) / d)]
                dirnames[:] = [d for d in dirnames if d not in runs]
                # ...but a live run's heartbeat is the session's sign of life: two stats per run
                # folder (its own mtime and its `.owner`), never a walk — skipping them blind read a
                # live session idle and removed its scratchpad entries
                for d in runs:
                    for p in (os.path.join(dirpath, d), os.path.join(dirpath, d, OWNER_NAME)):
                        try:
                            newest = max(newest, os.lstat(p).st_mtime)
                        except OSError:
                            continue
            for name in list(dirnames) + list(filenames):
                if not budget.spend():
                    return newest, False
                try:
                    st = os.lstat(os.path.join(dirpath, name))
                except OSError:
                    continue
                newest = max(newest, st.st_mtime)
    except OSError:
        # An unreadable subtree means the newest mtime is UNKNOWN, not old — the default
        # onerror swallowed this and reported a stale-looking answer for a live entry (F9).
        return newest, False
    return newest, True


def _entry_newest(entry: Path) -> float:
    """Newest mtime in an entry, unbudgeted and error-tolerant — for the advisory line's age only."""
    try:
        newest = entry.lstat().st_mtime
        if entry.is_dir() and not entry.is_symlink():
            for dirpath, dirnames, filenames in os.walk(entry, followlinks=False):
                for name in list(dirnames) + list(filenames):
                    try:
                        newest = max(newest, os.lstat(os.path.join(dirpath, name)).st_mtime)
                    except OSError:
                        continue
        return newest
    except OSError:
        return 0.0


def _du_kb(path: Path, deadline: float) -> int | None:
    """Best-effort size. A size is a courtesy; a class is the contract."""
    if time.monotonic() > deadline:
        return None
    try:
        out = subprocess.run(
            ["du", "-sk", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            timeout=3,
        ).stdout.split()
        return int(out[0]) if out else None
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


SIZE_REPORT_PATH = "~/.claude/state/scratch-size-report.json"
REPORT_STALE_S = 72 * 3600  # a run folder older than this and not `done` is named (spec D6)
ALARM_DISK_PCT = 85.0
ALARM_SESSION_BYTES = 5 * 1024**3


def _du_apparent(path: Path, deadline_s: float, exclude: tuple[str, ...] = ()) -> int | None:
    """Apparent bytes under `path` (`du -s --apparent-size --block-size=1`), `exclude` naming
    basenames to skip; None past the deadline or on any failure — a size is advisory, never a class."""
    if deadline_s <= 0:
        return None
    argv = ["du", "-s", "--apparent-size", "--block-size=1"]
    argv += [f"--exclude={name}" for name in exclude] + [str(path)]
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=deadline_s).stdout
        return int(out.split()[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


REPORT_FRESH_S = 48 * 3600  # an older report is not evidence about today


def write_size_report(sid_dirs: list[Path], run_rows: list[Row], now: float) -> Path | None:
    """D6: the nightly size report, written atomically by `--dead --apply` only (P10), AFTER the
    global lock is released. Per session id — every directory of that sid summed, a worktree
    session has two — apparent bytes outside `running` run folders (`unmeasured` when a `du` missed
    its deadline); every run folder older than 72 h, or of unknown age, and not `done` (a
    `resumable` one names `--retire`); every `done` folder past its grace a worktree keeps.
    Cobra (D-253): it is advice — the cheap way to quiet it is to keep a run open, and a `running`
    folder older than 72 h is itself named."""
    budget_end = time.monotonic() + float(_env_int("SCRATCH_SWEEP_REPORT_BUDGET_S", 600))
    sessions: dict[str, dict] = {}
    flagged: list[dict] = []
    worktree_kept = {
        r.path: r.reason
        for r in run_rows
        if r.cls == "kept" and r.reason.startswith("holds a registered worktree")
    }
    # a consumed folder too wide to scan is kept every night: the operator must SEE it, with the
    # remedy it actually needs, or its bytes leak silently (W-c0a1d324 F2 review)
    scan_kept = {r.path for r in run_rows if r.cls == "kept" and r.reason == SCAN_BUDGET_KEPT}
    for sdir in sid_dirs:
        if not sdir.is_dir():
            continue
        running: list[str] = []
        for folder in run_entries(sdir):
            if not folder.name.startswith(RUN_PREFIX):
                continue  # a `.trash-*` leftover is the next sweep's, never advice
            owner = read_owner(folder) or {}
            state = owner.get("state")
            if state == "running":
                running.append(folder.name)
            created = owner.get("created")
            adopted = owner.get("adopted")
            known_created = isinstance(created, int | float) and not isinstance(created, bool)
            if isinstance(adopted, int | float) and not isinstance(adopted, bool) and known_created:
                created = max(created, adopted)  # an unknown `created` stays unknown (F-B2)
            known = isinstance(created, int | float) and not isinstance(created, bool)
            if state != "done" and (not known or now - created > REPORT_STALE_S):
                action = (
                    f"python3 /opt/fabrik/scripts/scratch_sweep.py --run-folders --session "
                    f"{sdir.name} --retire {folder.name}"
                    if state == "resumable"
                    else "close the run; a dead session's folder goes after a 7-day-stale heartbeat"
                )
                why = (
                    "older than 72 h and not done" if known else "not done, and its age is unknown"
                )
                flagged.append(
                    {
                        "path": str(folder),
                        "sid": sdir.name,
                        "state": state,
                        "why": why,
                        "action": action,
                    }
                )
            elif state == "done" and not _done_close_is_vouched(owner, now):
                # D-900's cost made visible: every sweep keeps this folder (INV-1), so name it
                flagged.append(
                    {
                        "path": str(folder),
                        "sid": sdir.name,
                        "state": state,
                        "why": "done, but its close time cannot be vouched for (D-900) — kept by every sweep",
                        "action": f"inspect, then remove by hand: rm -rf {folder}",
                    }
                )
            elif str(folder) in worktree_kept:
                flagged.append(
                    {
                        "path": str(folder),
                        "sid": sdir.name,
                        "state": state,
                        "why": f"done past its grace, kept: {worktree_kept[str(folder)]}",
                        "action": "remove or merge that worktree; the next sweep then removes the folder",
                    }
                )
            elif str(folder) in scan_kept:
                flagged.append(
                    {
                        "path": str(folder),
                        "sid": sdir.name,
                        "state": state,
                        "why": f"done past its grace, kept: {SCAN_BUDGET_KEPT}",
                        "action": (
                            f"check it holds no worktree (git worktree list), then rm -rf {folder}; "
                            "or raise SCRATCH_SWEEP_GIT_SCAN_BUDGET"
                        ),
                    }
                )
        left = min(60.0, budget_end - time.monotonic())
        size = _du_apparent(sdir, left, tuple(running))
        entry = sessions.setdefault(sdir.name, {"dirs": [], "bytes": 0, "unmeasured": False})
        entry["dirs"].append(str(sdir))
        if size is None:
            entry["unmeasured"] = True
        else:
            entry["bytes"] += size
    target = Path(os.path.expanduser(SIZE_REPORT_PATH))
    tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(
            json.dumps({"generated": now, "sessions": sessions, "run_folders": flagged}, indent=1),
            encoding="utf-8",
        )
        os.replace(tmp, target)
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink()
        return None
    return target


def _disk_used_pct(root: Path) -> float | None:
    """df's Use%: used / (used + free to unprivileged users) — `used / total` hides the reserved
    blocks and reads several points low. `SCRATCH_SWEEP_DISK_USED_PCT` is the test seam."""
    raw = os.environ.get("SCRATCH_SWEEP_DISK_USED_PCT")
    try:
        if raw:
            return float(raw)
        du = shutil.disk_usage(root)
        return 100.0 * du.used / (du.used + du.free) if (du.used + du.free) else None
    except (OSError, ValueError):
        return None


def _report_reasons(sid: str, now: float) -> list[str]:
    """The nightly report's reasons for this session (stale, too big, unmeasured, an old run
    folder). Any shape it cannot read yields no reason — never an exception (RC-B, RC-B2)."""
    reasons: list[str] = []
    try:
        report = json.loads(Path(os.path.expanduser(SIZE_REPORT_PATH)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = None
    if isinstance(report, dict):
        generated = report.get("generated")
        dated = (
            isinstance(generated, int | float)
            and not isinstance(generated, bool)
            and math.isfinite(generated)
        )
        # a future date (clock skew, a test clock left set) is no more evidence than an old one
        fresh = dated and 0 <= now - generated <= REPORT_FRESH_S
        if not fresh:
            if not dated:
                age = "undated"
            elif generated > now:
                age = "dated in the future"
            else:
                age = f"{_human(now - generated)} old"
            reasons.append(
                f"the nightly size report is {age} — has `scratch_sweep.py --dead --apply` stopped?"
            )
        else:
            sessions = report.get("sessions")
            mine = sessions.get(sid) if isinstance(sessions, dict) else None
            if isinstance(mine, dict):
                size = mine.get("bytes")
                if isinstance(size, int) and size > ALARM_SESSION_BYTES:
                    reasons.append(
                        f"this session holds {size / 1024**3:.1f} GB outside running run folders"
                    )
                elif mine.get("unmeasured"):
                    reasons.append(
                        "this session's scratch could not be measured within its deadline"
                    )
            folders = report.get("run_folders")
            for r in folders if isinstance(folders, list) else []:
                if isinstance(r, dict) and r.get("sid") == sid:
                    reasons.append(
                        f"{Path(str(r.get('path'))).name} {r.get('why')} — {r.get('action')}"
                    )
    return reasons


def _size_alarm_line(sid: str, root: Path, now: float | None = None) -> str:
    """D6's SessionStart alarm — one line, advice only: disk use past 85 %, this session holding
    more than 5 GB outside running run folders (or too much to measure in time), a run folder of
    its own older than 72 h and not `done`, or a report too old to be evidence. "" when none
    holds. A report of any wrong shape is treated as no report — it never raises."""
    now = _now() if now is None else now
    reasons: list[str] = []
    pct = _disk_used_pct(root)
    if pct is not None and pct > ALARM_DISK_PCT:
        reasons.append(f"disk {pct:.0f}% used")
    try:
        reasons += _report_reasons(sid, now)
    except Exception:  # noqa: BLE001 — a report of any shape never costs the live disk reason
        pass
    if not reasons:
        return ""
    return "## 🚨 SCRATCH ALARM: " + " · ".join(reasons)


# ── session liveness ────────────────────────────────────────────────────────────────────────────
def sessions_dirs() -> list[Path]:
    """Every DISCOVERABLE `<config-root>/sessions`, deduped.

    Discovered, never a hand-written pair: `~/.claude-youtube-headless` is a real config root with
    132 session files that a two-root scan missed entirely, and a live process can declare a root
    outside `~/.claude*` through `CLAUDE_CONFIG_DIR` — which is why the live processes' own
    environment is folded in below.
    """
    override = _split_env_paths("SCRATCH_SWEEP_SESSIONS_DIRS")
    if override is not None:
        return _dedup(override)
    home = _home()
    found = [Path(p) for p in globmod.glob(str(home / ".claude*" / "sessions"))]
    found += [Path(p) for p in globmod.glob(str(home / ".claude-fleet" / "*" / "sessions"))]
    for root in _live_config_roots():
        found.append(root / "sessions")
    return _dedup([p for p in found if p.is_dir()])


def transcript_dirs() -> list[Path]:
    override = _split_env_paths("SCRATCH_SWEEP_TRANSCRIPT_DIRS")
    if override is not None:
        return _dedup(override)
    home = _home()
    found = [Path(p) for p in globmod.glob(str(home / ".claude*" / "projects"))]
    found += [Path(p) for p in globmod.glob(str(home / ".claude-fleet" / "*" / "projects"))]
    for root in _live_config_roots():
        found.append(root / "projects")
    return _dedup([p for p in found if p.is_dir()])


def _live_config_roots() -> list[Path]:
    """`CLAUDE_CONFIG_DIR` as declared by each live process's own environment."""
    proc_root = _proc_root()
    roots: list[Path] = []
    try:
        pids = [p for p in os.listdir(proc_root) if p.isdigit()]
    except OSError:
        return roots
    for pid in pids:
        try:
            raw = (proc_root / pid / "environ").read_bytes()
        except OSError:
            continue
        for item in raw.split(b"\0"):
            if item.startswith(b"CLAUDE_CONFIG_DIR="):
                value = item.split(b"=", 1)[1].decode("utf-8", "replace").strip()
                if value:
                    roots.append(Path(value))
    return roots


def _proc_start_ticks(proc_root: Path, pid: int) -> str | None:
    """Field 22 of `/proc/<pid>/stat` — start time in clock ticks since boot."""
    try:
        raw = (proc_root / str(pid) / "stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        return raw[raw.rindex(")") + 2 :].split()[19]
    except (ValueError, IndexError):
        return None


def _btime() -> float | None:
    """Boot epoch from `/proc/stat`. `SCRATCH_SWEEP_BTIME` is the test seam."""
    raw = os.environ.get("SCRATCH_SWEEP_BTIME")
    if raw:
        try:
            return float(raw)
        except ValueError:
            return None
    try:
        for line in (
            (_proc_root() / "stat").read_text(encoding="utf-8", errors="replace").splitlines()
        ):
            if line.startswith("btime"):
                return float(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return None


def read_sessions(dirs: list[Path]) -> tuple[dict[str, list[dict]], list[str]]:
    """`({sid: [records]}, [unreadable roots])`.

    An unreadable root is returned rather than swallowed: it has no enumerable sids, so the LIVE
    signal collapses while the DEATH signal survives — the janitor must refuse the whole run rather
    than call a live session dead.
    """
    by_sid: dict[str, list[dict]] = {}
    unreadable: list[str] = []
    for d in dirs:
        try:
            names = os.listdir(d)
        except OSError:
            unreadable.append(str(d))
            continue
        for name in names:
            if not name.endswith(".json"):
                continue
            try:
                rec = json.loads((d / name).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get("sessionId") or "")
            if sid:
                by_sid.setdefault(sid, []).append(rec)
    return by_sid, unreadable


def live_record(records: list[dict], proc_root: Path | None = None) -> dict | None:
    """The record whose `pid` + `procStart` still match a running process, or None."""
    proc_root = proc_root or _proc_root()
    for rec in records:
        pid = rec.get("pid")
        if not isinstance(pid, int):
            continue
        actual = _proc_start_ticks(proc_root, pid)
        if actual is not None and str(rec.get("procStart")) == str(actual):
            return rec
    return None


def session_start_epoch(records: list[dict], proc_root: Path | None = None) -> float | None:
    """When the live session actually started: `btime + procStart / SC_CLK_TCK`.

    `procStart` is CLOCK TICKS SINCE BOOT, not an epoch. Comparing a file mtime to the raw tick
    count classes 0 of 8 hub worktrees foreign; the conversion classes 8 of 8, correctly.
    """
    rec = live_record(records, proc_root)
    if rec is None:
        return None
    btime = _btime()
    if btime is None:
        return None
    try:
        hz = os.sysconf("SC_CLK_TCK") or 100
        return btime + float(rec["procStart"]) / float(hz)
    except (KeyError, ValueError, TypeError, OSError):
        return None


def _selfwatch_held(sid: str) -> bool:
    """Is this sid's self-watch lock HELD? A held lock means the pane is alive."""
    safe = "".join(c if (c.isalnum() and ord(c) < 128) or c in "_-" else "_" for c in sid)[:64]
    path = _lock_dir() / f"{safe}.selfwatch.lock"
    if not path.exists():
        return False
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def find_session_dirs(root: Path, sid: str, cwd: str | None = None) -> list[Path]:
    """`<root>/*/<sid>/` — FOUND by glob, never computed from the cwd.

    The harness's slug is `re.sub(r"[^A-Za-z0-9]", "-", cwd)`, so a naive `cwd.replace("/", "-")`
    computes a directory that does not exist and reports a false "clean" (`/opt/iterative_image_editor`
    → `-opt-iterative-image-editor`). A sid that entered an agent worktree has scratch under two
    slugs; `--cwd` picks one, otherwise both are listed.
    """
    # CONTAINMENT (Global Constraints: "every computed target is `Path.resolve()`d and asserted
    # `is_relative_to(root)` before classification"). `is_dir()` FOLLOWS symlinks, so a sid-level
    # symlink pointed the whole classification at another tree — and the entries it then yielded
    # were real paths under the target, so `_classify_one`'s symlink guard never saw a link and
    # `--apply` rmtree'd outside the scratch root entirely (round-4).
    #
    # This is one of TWO layers. Measured isolation: removing the `scratchpad/` test in
    # `classify_session` alone goes RED, removing THIS one alone stays green — so that one is
    # load-bearing and this one is defence in depth. It is kept because it costs one `resolve()`
    # per glob hit AND it is the only containment on the `--hook` stamp-write path.
    hits: list[Path] = []
    try:
        real_root = root.resolve()
    except OSError:
        return []
    for candidate in sorted(globmod.glob(str(root / "*" / sid))):
        c = Path(candidate)
        try:
            resolved = c.resolve()
        except OSError:
            continue
        if not resolved.is_relative_to(real_root) or not resolved.is_dir():
            continue
        hits.append(c)
    if cwd:
        slug = re.sub(r"[^A-Za-z0-9]", "-", cwd)
        exact = [h for h in hits if h.parent.name == slug]
        if exact:
            return exact
    return hits


def _is_slug_dir(entry: Path) -> bool:
    """A slug dir holds SID-SHAPED children — the janitor's territory, never `unowned`.

    Not a `scratchpad/` test: 7 sid dirs inside 5 agent-worktree slugs hold only `tasks/`, and a
    presence test would push those whole slug trees into the removable `unowned` set.
    """
    if not entry.is_dir() or entry.is_symlink():
        return False
    try:
        for child in os.scandir(entry):
            if (
                child.is_dir(follow_symlinks=False)
                and SID_RE.fullmatch(child.name)
                and "-" in child.name
            ):
                return True
    except OSError:
        # Unreadable ⇒ KEEP it in the janitor's per-sid territory. Falling through to `unowned`
        # would offer a whole slug tree of session scratch to `--unowned-older-than` (F10).
        return True
    return False


# ── mode 1: this session's scratchpad ───────────────────────────────────────────────────────────
def _read_keep_list(pad: Path) -> tuple[set[str], list[Row]]:
    """The keep list, plus a row per invalid or unmatched name.

    A keep list that silently protects nothing is worse than none, so an unmatched name is REPORTED
    rather than swallowed, and a name carrying `/` or `..` is refused outright.
    """
    names: set[str] = set()
    notes: list[Row] = []
    path = pad / KEEP_FILE
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return names, notes  # no keep list is the normal case
    except OSError as exc:
        # An UNREADABLE keep list silently disabled every protection it carried — the opposite of
        # "any probe error ⇒ KEEP". Say so, and keep the whole scratchpad rather than sweeping it.
        notes.append(
            Row(
                str(path),
                "entry",
                "keep-unreadable",
                f"the keep list cannot be read ({exc.strerror})",
            )
        )
        return names, notes
    for raw in text.splitlines():
        name = raw.split("#", 1)[0].strip()
        if not name:
            continue
        if "/" in name or ".." in name:
            notes.append(
                Row(str(path), "entry", "keep-invalid", f"{name!r} is not a bare basename")
            )
            continue
        if not (pad / name).exists():
            notes.append(Row(str(path), "entry", "keep-unmatched", f"{name!r} matches no entry"))
            continue
        names.add(name)
    return names, notes


def classify_session(
    root: Path,
    sid: str,
    now: float,
    older_than_s: float,
    proc_root: Path | None = None,
    budget: WalkBudget | None = None,
    with_size: bool = True,
    cwd: str | None = None,
    run_folders: bool = True,
) -> tuple[list[Row], list[str], bool]:
    """`(rows, proc gaps, probe_ok)` — one row per top-level entry. `tasks/` is never touched.

    A `run-*`/`.trash-*` entry is routed to `judge_run_folder` BEFORE the age walk (plan P8): a
    `done` run inside its 36 h grace, or a `resumable` one idle 7 h, would otherwise read `stale`.
    `run_folders=False` (the hook, whose deadline cannot afford a `git worktree list`) leaves them
    out of the rows entirely.
    """
    proc_root = proc_root or _proc_root()
    budget = budget or WalkBudget()
    rows: list[Row] = []
    gaps: list[str] = []
    probe_ok = True
    du_deadline = time.monotonic() + DU_DEADLINE_S
    found_any = False
    for session_dir in find_session_dirs(root, sid, cwd):
        pad = session_dir / "scratchpad"
        try:
            # The same containment test one level down: a symlinked `scratchpad/` would escape too.
            if (
                pad.is_symlink()
                or not pad.resolve().is_relative_to(root.resolve())
                or not pad.is_dir()
            ):
                continue
        except OSError:
            rows.append(
                Row(str(pad), "entry", "probe-error", "unreadable — no classification is provable")
            )
            continue
        found_any = True
        keep_names, notes = _read_keep_list(pad)
        rows.extend(notes)
        if any(r.cls == "keep-unreadable" for r in notes):
            # Nothing here is provably unprotected while the list itself is unreadable.
            try:
                for e in sorted(os.scandir(pad), key=lambda x: x.name):
                    rows.append(
                        Row(
                            e.path,
                            "entry",
                            "probe-error",
                            "the keep list is unreadable — nothing is provably unprotected",
                        )
                    )
            except OSError:
                pass
            continue
        try:
            entries = sorted(os.scandir(pad), key=lambda e: e.name)
        except OSError as exc:
            rows.append(Row(str(pad), "entry", "probe-error", f"scandir failed: {exc}"))
            continue
        paths = [Path(e.path) for e in entries]
        held, probe_gaps, ok = probe_holders(paths, proc_root)
        starts = gap_starts(probe_gaps, proc_root) if run_folders else []
        gaps.extend(probe_gaps)
        probe_ok = probe_ok and ok
        for entry in paths:
            if is_run_entry(entry) and entry.name not in keep_names:
                if run_folders:
                    r = judge_run_folder(
                        entry,
                        sid,
                        now,
                        session_dead=False,
                        held=held,
                        gaps=starts,
                        probe_ok=ok,
                    )
                    if r.cls == "kept":
                        r = Row(r.path, "entry", "kept", "run folder, marker-governed", r.reason)
                    rows.append(r)
                continue
            rows.append(
                _classify_one(
                    entry, keep_names, held, now, older_than_s, budget, du_deadline, with_size
                )
            )
    if not found_any:
        # "nothing to classify" and "I could not find your scratchpad" are different facts, and
        # the second is the false-clean shape the glob-by-sid resolution exists to prevent (F17).
        rows.append(
            Row(str(root), "entry", "unclassified", f"no scratchpad found for {sid} under {root}")
        )
    return rows, sorted(set(gaps)), probe_ok


def _classify_one(
    entry: Path,
    keep_names: set[str],
    held: dict[str, str],
    now: float,
    older_than_s: float,
    budget: WalkBudget,
    du_deadline: float,
    with_size: bool,
) -> Row:
    """The ordered decision procedure. Order is the contract — see the plan's Phase A.2."""
    p = str(entry)
    if entry.is_symlink():
        return Row(p, "entry", "unclassified", "a symlink — never followed, never removed")
    if entry.name == KEEP_FILE:
        return Row(p, "entry", "kept", "the keep list itself — kept at any age")
    if entry.name in keep_names:
        return Row(p, "entry", "kept", f"named in {KEEP_FILE}")
    try:
        has_own_keep = (entry / KEEP_FILE).exists()
    except OSError:
        # `Path.exists()` RAISES EACCES; it does not return False. An entry directory missing the
        # owner x-bit crashed the whole run with a traceback and rc 1 — shadowing all three of the
        # unreadable-tree guards below it, which are the ones that make this fail SAFE (round-3).
        return Row(p, "entry", "probe-error", "unreadable — no classification is provable")
    if has_own_keep:
        return Row(p, "entry", "kept", f"holds its own {KEEP_FILE}")
    if p in held or str(entry.resolve()) in held:
        who = held.get(p) or held.get(str(entry.resolve()), "a live process")
        return Row(p, "entry", "held", "held by a live process", who)
    if budget.spent_out:
        # The budget ran out on an EARLIER entry: this one was never walked at all, so it is
        # `fresh` (the plan's degradation rule) rather than a claim about a walk we did not do.
        return Row(p, "entry", "fresh", "not walked — the shared freshness budget was exhausted")
    newest, complete = newest_mtime(entry, budget)
    if not complete:
        return Row(
            p, "entry", "probe-error", "the freshness walk was cut short — never assumed stale"
        )
    age = now - newest
    if age < older_than_s:
        return Row(p, "entry", "fresh", f"newest file {_human(age)} old", age_s=age)
    # LAST, and only over an entry that would otherwise be `stale`: `holds-backups` is a REMOVABLE
    # class under `--include-backups`, so testing it before the holder probe and the freshness
    # check made the flag delete FRESH and HELD entries — the guard written to protect revert-test
    # baselines was the only thing deleting them (round-2 A1). `_classify_sid` had the order right.
    backup = _holds_backup(entry)
    if backup is None:
        return Row(
            p, "entry", "probe-error", "part of its tree is unreadable — no backup scan, no claim"
        )
    if backup:
        return Row(
            p,
            "entry",
            "holds-backups",
            "stale, but holds a backup shape (--include-backups to remove)",
        )
    size = _du_kb(entry, du_deadline) if with_size else None
    return Row(p, "entry", "stale", f"newest file {_human(age)} old", size_kb=size, age_s=age)


def _human(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 90:
        return f"{int(seconds)}s"
    if seconds < 90 * 60:
        return f"{int(seconds / 60)}m"
    if seconds < 48 * 3600:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


# ── rendering ───────────────────────────────────────────────────────────────────────────────────
def render(
    rows: list[Row],
    brief: bool = False,
    gaps: list[str] | None = None,
    apply_cmd: str = "",
    allowed: set[str] | None = None,
) -> str:
    """The table. Under `--brief`, zero candidates produce ZERO BYTES.

    `allowed` is what THIS invocation may remove, not the bare `REMOVABLE` set: with
    `--include-backups` or `--unowned-older-than` armed, a `REMOVABLE`-only candidate test printed
    no `apply:` line and left `--brief` silent while a removal was pending (round-2 A5).
    """
    gaps = gaps or []
    candidates = [r for r in rows if r.cls in (allowed if allowed is not None else REMOVABLE)]
    if brief and not candidates:
        return ""
    out: list[str] = []
    # `--brief` is the CLOSE-OUT shape, and a close-out prints into the agent's own context at the
    # moment it is composing its final block: the full table was 477 lines / 64 KB on a real
    # scratchpad, fleet-wide, at every close. It shows the OLDEST candidates and says how many it
    # did not show. The sort is what makes "oldest" true: `classify_session` yields entries in
    # directory order, so a bare head-slice showed five day-old dirs and hid every 40-day one
    # behind the "and N more" (round 2). Rows with no age sort last, never first.
    # The interactive dry run is uncapped — that reader asked for the whole list.
    shown = sorted(candidates, key=lambda r: -(r.age_s or 0.0))[:BRIEF_ROWS] if brief else rows
    for r in shown:
        size = f"{r.size_kb} KB" if r.size_kb is not None else "?"
        cells = [r.path, size, r.cls, r.reason]
        if r.evidence:
            cells.append(r.evidence)
        out.append(" · ".join(cells))
    if brief and len(candidates) > len(shown):
        out.append(
            f"… and {len(candidates) - len(shown)} more — run the dry-run command for the full table"
        )
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.cls] = counts.get(r.cls, 0) + 1
    summary = " · ".join(f"{k} {counts[k]}" for k in sorted(counts))
    if not summary:
        summary = "nothing to classify"  # computed BEFORE the gaps, or the fallback never fires
    if gaps:
        summary += f" · proc-gaps {len(gaps)} ({', '.join(gaps[:4])})"
    out.append(summary)
    if candidates and apply_cmd:
        out.append(f"apply: {apply_cmd}")
    return "\n".join(out)


# ── the lock ────────────────────────────────────────────────────────────────────────────────────
class _Lock:
    """A NON-blocking flock. A held lock is one line and rc 0 — never a wait.

    The cron line deliberately carries NO `flock -n` wrapper: `flock(1)` holds the lock across the
    exec, so a wrapper on this same path makes the acquire below fail and the sweep exits 0 having
    done nothing, silently, every night. Reproduced 2026-09-08.

    `path` is the per-session run-folder lock (`<session dir>/.run-folders.lock`, plan P3): a D3
    removal holds only that one, so it never makes the nightly `--dead --apply` skip its night.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(os.path.expanduser(LOCK_PATH))
        self.fd: int | None = None

    def __enter__(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT, 0o600)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False
        except OSError:
            return True  # a lock we cannot take must not block the sweep

    def __exit__(self, *_exc: object) -> None:
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)


# ── apply ───────────────────────────────────────────────────────────────────────────────────────
def apply_rows(
    rows: list[Row], allowed: set[str], out=sys.stdout, proc_root: Path | None = None
) -> int:
    """Remove only rows whose class is in `allowed`. Per-ROW error handling, never all-or-nothing.

    The holder probe is RE-RUN here, inside the lock and immediately before removal: the
    classification probe ran seconds earlier and outside it, so a process that opened a descriptor
    in between was invisible — two racing applies deleted a live-held directory and reported it
    `stale` (round-2 A4). A row now held is dropped, with a line saying so.
    """
    targets = [Path(r.path) for r in rows if r.cls in allowed]
    held_now: dict[str, str] = {}
    if targets:
        held_now, _gaps, probe_ok = probe_holders(targets, proc_root)
        if not probe_ok:
            print("REFUSED — the /proc holder probe went unreadable; nothing removed", file=out)
            return 0
    removed = 0
    for r in rows:
        if r.cls not in allowed:
            continue
        if r.path in held_now or str(Path(r.path).resolve()) in held_now:
            who = held_now.get(r.path) or held_now.get(
                str(Path(r.path).resolve()), "a live process"
            )
            print(f"KEPT {r.path} — a holder appeared since classification ({who})", file=out)
            continue
        p = Path(r.path)
        try:
            if p.is_symlink() or p.is_file():
                os.unlink(p)
            elif p.is_dir():
                try:
                    shutil.rmtree(p)  # raises on a symlink by design — never follows one
                except PermissionError:
                    _own_tree(p)
                    shutil.rmtree(p)
            else:
                continue
            removed += 1
            print(f"REMOVED {r.path} ({r.cls}, {r.reason})", file=out)
        except OSError as exc:
            print(f"FAILED {r.path} ({exc.errno}: {exc.strerror})", file=out)
    return removed


def _own_tree(root: Path) -> None:
    """Give the owner rwx on `root` and on every real directory under it, top-down, so a retried
    rmtree can list and unlink inside: a review seat's copied pin is a READ-ONLY tree
    (`dr-xr-xr-x`, files 0444, a dir may be 000), and rmtree's EACCES left the stale dir behind on
    every `--apply` (intel 01M4E3M1JJ). Only `root` and what is under it change — never its
    parent — and a symlink is never chmodded or descended (chmod would follow it out of the tree);
    a file needs no bit, since unlinking reads only its directory's."""
    if root.is_symlink() or not root.is_dir():
        return
    os.chmod(root, root.stat().st_mode | 0o700)
    for dirpath, dirnames, _files in os.walk(root, followlinks=False):
        for name in dirnames:
            d = os.path.join(dirpath, name)
            if not os.path.islink(d):
                os.chmod(d, os.stat(d).st_mode | 0o700)


# ── CLI ─────────────────────────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="scratch_sweep.py",
        description=__doc__.split("\n\n")[0],
        epilog=REFUSAL_SET,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--session", help="session id (default: $CLAUDE_SESSION_ID / $CLAUDE_CODE_SESSION_ID)"
    )
    ap.add_argument("--cwd", help="disambiguate a sid whose scratch sits under two slugs")
    ap.add_argument(
        "--older-than",
        default=None,
        help=f"an entry newer than this is `fresh` (default {DEFAULT_OLDER_THAN}; {DEFAULT_DEAD_OLDER_THAN} in --dead)",
    )
    ap.add_argument("--apply", action="store_true", help="actually remove the candidates (opt-in)")
    ap.add_argument(
        "--worktrees",
        nargs="?",
        const=".",
        metavar="REPO",
        help="classify this repo's agent worktrees",
    )
    ap.add_argument(
        "--dead", action="store_true", help="janitor: sessions that can never clean themselves"
    )
    ap.add_argument(
        "--unowned-older-than",
        type=float,
        metavar="DAYS",
        help="also remove root-level entries older than DAYS",
    )
    ap.add_argument(
        "--foreign-older-than",
        default=None,
        metavar="DURATION",
        help=(
            "let a worktree registered before this session started be judged on its own state "
            "once it is older than DURATION (e.g. 14d) — every refusal still applies"
        ),
    )
    ap.add_argument(
        "--include-harness",
        action="store_true",
        help="let a harness worktree be removed when its own verdict is wt-removable",
    )
    ap.add_argument(
        "--include-backups", action="store_true", help="let a backup-holding entry be removed"
    )
    ap.add_argument(
        "--include-unmerged",
        action="store_true",
        help=(
            "also remove a clean worktree whose branch is unmerged (wt-unmerged) or whose only "
            "dirt is the sync's output (wt-sync-only) — no commit is lost: an unmerged branch is "
            "kept, a merged one goes only through git's own `branch -d`"
        ),
    )
    ap.add_argument(
        "--strict-proc",
        action="store_true",
        help="turn a same-uid /proc gap into probe-error (default: report it)",
    )
    ap.add_argument(
        "--hook",
        action="store_true",
        help="SessionStart hook mode: one advisory line, exit 0 always",
    )
    ap.add_argument(
        "--brief", action="store_true", help="the close-out shape: zero candidates print zero bytes"
    )
    ap.add_argument(
        "--run-folders",
        action="store_true",
        help=(
            "this session's run folders only (requires --session): judged by their .owner marker, "
            "removed walk-free under a per-session lock — what `command_run.py start` launches"
        ),
    )
    ap.add_argument(
        "--retire",
        metavar="RUN_FOLDER",
        help="with --run-folders: mark one resumable run-<key> folder done (ends its resume)",
    )
    return ap


def _downgrade(rows: list[Row], args: argparse.Namespace, reason: str) -> list[Row]:
    """Turn every REMOVABLE row into `probe-error` — the whole removal set, not just `stale`.

    Downgrading `stale` alone INVERTS the protection under `--strict-proc --include-backups`: the
    plain entries are spared while the ones carrying revert-test baselines are removed (round-3).
    A `consumed` run folder is in that set too — `apply_run_rows` removes it by class, never
    through `_allowed_classes`, so leaving it out made `--strict-proc` inert on run folders
    (W-c0a1d324 F5).
    """
    allowed = _allowed_classes(args) | {"consumed"}
    return [
        Row(r.path, r.kind, "probe-error", reason, r.evidence) if r.cls in allowed else r
        for r in rows
    ]


def _allowed_classes(args: argparse.Namespace) -> set[str]:
    """Exactly what `--apply` may remove, given the flags actually passed."""
    allowed = set(REMOVABLE)
    if args.include_harness:
        allowed.add("wt-harness")
    if args.include_backups:
        allowed |= {"holds-backups", "dead-holds-backups"}
    if args.unowned_older_than is not None:
        allowed.add("unowned")
    if getattr(args, "include_unmerged", False):
        allowed |= {"wt-unmerged", "wt-sync-only"}
    return allowed


def _apply_command(argv: list[str], args: argparse.Namespace | None = None) -> str:
    """The EXACT command that would apply what was just listed — flags included (constraint 2)."""
    extra: list[str] = []
    if args is not None:
        if args.older_than:
            extra += ["--older-than", str(args.older_than)]
        if args.include_backups:
            extra.append("--include-backups")
        if args.include_harness:
            extra.append("--include-harness")
        if args.strict_proc:
            extra.append("--strict-proc")
        if args.unowned_older_than is not None:
            extra += ["--unowned-older-than", str(args.unowned_older_than)]
        if getattr(args, "foreign_older_than", None):
            extra += ["--foreign-older-than", str(args.foreign_older_than)]
        if getattr(args, "include_unmerged", False):
            extra.append("--include-unmerged")
    return "python3 /opt/fabrik/scripts/scratch_sweep.py " + " ".join(argv + extra + ["--apply"])


def run_session_mode(args: argparse.Namespace, sid: str) -> int:
    root = _scratch_root()
    older = parse_duration(args.older_than or DEFAULT_OLDER_THAN)
    rows, gaps, probe_ok = classify_session(
        root,
        sid,
        _now(),
        older,
        budget=WalkBudget(stats=_env_int("SCRATCH_SWEEP_WALK_BUDGET", WALK_BUDGET)),
        with_size=not (args.brief or args.hook),
        cwd=args.cwd,
    )
    if not probe_ok:
        rows = _downgrade(
            rows, args, "the /proc holder probe is unreadable — nothing is provably unheld"
        )
    elif args.strict_proc and gaps:
        rows = _downgrade(rows, args, f"a same-uid /proc gap under --strict-proc ({len(gaps)})")
    argv = ["--session", sid] + (["--cwd", args.cwd] if args.cwd else [])
    if args.apply:
        ok, unreadable = _own_session(sid)
        if unreadable or not ok:
            print(render(rows, gaps=gaps, allowed=_allowed_classes(args)))
        if unreadable:
            print(
                f"REFUSED — cannot read {', '.join(unreadable)}, so no session's liveness is "
                "provable; nothing removed (the dry-run above still stands)."
            )
            return RC_REFUSED
        if not ok:
            print(
                f"REFUSED — sid {sid} belongs to a LIVE session that is not this one; "
                "its scratch is not yours to remove (dry-run is still available)."
            )
            return RC_REFUSED
        with _Lock() as got:
            if not got:
                print("another sweep holds the lock — nothing done (rc 0, never a wait)")
                return RC_OK
            print(REFUSAL_SET)
            print(render(rows, gaps=gaps, allowed=_allowed_classes(args)))
            apply_rows(rows, _allowed_classes(args), proc_root=_proc_root())
        # Consumed run folders go AFTER the global lock is released, under each session's own
        # lock only — never through `apply_rows`, and `consumed` is not in REMOVABLE (plan P8).
        by_dir: dict[Path, list[Row]] = {}
        for r in rows:
            if r.cls == "consumed":
                by_dir.setdefault(Path(r.path).parent.parent, []).append(r)
        for sdir, consumed in by_dir.items():
            with _Lock(sdir / RUN_LOCK_NAME) as got:
                if not got:
                    print(f"another run-folder sweep holds {sdir}'s lock — its run folders wait")
                    continue
                apply_run_rows(consumed, proc_root=_proc_root())
        return RC_OK
    out = render(
        rows,
        brief=args.brief,
        gaps=gaps,
        apply_cmd=_apply_command(argv, args),
        allowed=_allowed_classes(args),
    )
    if out:
        print(out)
    return RC_OK


def _shares_our_process_session(pid: object) -> bool:
    """Is `pid` in this process's own POSIX session?

    An ancestor WALK is the wrong test: pid 1 is every process's ancestor, so it read as "mine"
    and a genuine peer's scratch became sweepable.

    ⚠️ This is a real widening, not a no-op: a peer whose live pid genuinely shares this process's
    POSIX session WOULD become sweepable, and a review fixture proved it. It is kept because the
    measured population is empty — every tool-spawned shell is its own session leader, and all 9
    live sessions on this box sit in one sid that no sweeper invocation shares — and because none
    of the three callers passes a foreign `--session` with `--apply` (the close-out is `--brief`,
    the hook never applies, the cron uses `--dead`'s three-signal rule). Reaching it needs a peer's
    sid typed by hand from the launching terminal.
    """
    if not isinstance(pid, int) or pid <= 1:
        return False
    try:
        return os.getsid(pid) == os.getsid(0)
    except (OSError, AttributeError):
        return False


def _own_session(sid: str) -> tuple[bool, list[str]]:
    """`(safe to apply?, unreadable roots)`.

    A LIVE session that is not this one owns its scratch; we refuse rather than race it. The
    unreadable list is RETURNED, never discarded: a peer whose only liveness record lives in a
    root we cannot read would otherwise read as "no live claim ⇒ yours", and the review removed a
    running peer's scratch exactly that way (F3). `--dead` already refuses on this; so does this.
    """
    mine = session_id(None)
    if sid == mine:
        return True, []
    by_sid, unreadable = read_sessions(sessions_dirs())
    rec = live_record(by_sid.get(sid, []))
    if rec is not None and _shares_our_process_session(rec.get("pid")):
        # The sid IS this process's session — the env just did not carry it (a cron shell, `env -i`,
        # a nested tool call). Refusing your own scratch is fail-safe but useless (round-2 A12).
        return True, []
    return rec is None, unreadable


def main(argv: list[str] | None = None) -> int:
    # Scratch legitimately holds paths with non-UTF-8 bytes (the git-decoder spec's fixture repos), which
    # os.fsdecode turns into lone surrogates. One reconfigure covers every print this script makes: under a UTF-8
    # locale a strict stdout raised "surrogates not allowed" and killed the run, under the C locale it wrote the raw
    # byte (mail 01M2ZF211DF1AQ5PKGKSEGQA19). Paths now render escaped (`\udcff`); the filesystem ops keep the bytes.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    args = build_parser().parse_args(argv)
    try:
        if args.unowned_older_than is not None and not (args.unowned_older_than >= 1):
            # `--unowned-older-than 0` made every non-protected root entry removable at any age
            # (review F5): 33 entries / 2.3 GB on the live box, including one 60 seconds old.
            raise ValueError(
                f"--unowned-older-than must be at least 1 day, got {args.unowned_older_than!r}"
            )
        if (args.run_folders or args.retire) and (
            args.dead or args.hook or args.worktrees is not None
        ):
            raise ValueError(
                "--run-folders/--retire is its own mode — drop --dead/--hook/--worktrees"
            )
        if args.worktrees is not None:
            return run_worktrees_mode(args)
        if args.dead:
            return run_dead_mode(args)
        if args.hook:
            # The hook's sid comes from the PAYLOAD first — `selfwatch_check.py:92` reads it the
            # same way, and a SessionStart hook is invoked with no `--session` and no env sid
            # (review F7: it exited 1 and printed nothing, so Phase B would register an inert hook).
            return run_hook_mode(args, session_id(args.session))
        if args.retire and not args.run_folders:
            raise ValueError("--retire needs --run-folders")
        if args.run_folders and not args.session:
            raise ValueError("--run-folders needs --session")
        sid = session_id(args.session)
        if not sid:
            print("no session id — pass --session or set CLAUDE_SESSION_ID", file=sys.stderr)
            return RC_USAGE
        if not SID_RE.fullmatch(sid):
            print(f"refusing a malformed session id {sid!r}", file=sys.stderr)
            return RC_USAGE
        if args.run_folders:
            return run_run_folders_mode(args, sid)
        return run_session_mode(args, sid)
    except ValueError as exc:
        print(f"bad invocation: {exc}", file=sys.stderr)
        return RC_USAGE


# ── mode 2: the janitor (--dead) ────────────────────────────────────────────────────────────────
def _transcript_age(sid: str, dirs: list[Path], now: float) -> float | None:
    """Seconds since the sid's most recent transcript was written, across every discovered root."""
    newest: float | None = None
    for root in dirs:
        for path in globmod.glob(str(root / "*" / f"{sid}.jsonl")):
            try:
                mt = os.stat(path).st_mtime
            except OSError:
                continue
            newest = mt if newest is None else max(newest, mt)
    return None if newest is None else now - newest


def dead_sessions(
    root: Path,
    sess_dirs: list[Path],
    tx_dirs: list[Path],
    proc_root: Path,
    now: float,
    older_than_s: float,
    unowned_days: float | None = None,
) -> tuple[list[Row], list[str], list[str]]:
    """`(rows, unreadable roots, proc gaps)` — one row per sid dir, plus the root-level entries.

    A sid is `dead` only with ALL THREE of: no live signal, a death signal, and its own directory
    idle past the threshold. Absence of evidence is `unclassified`, which is never removed.
    """
    by_sid, unreadable = read_sessions(sess_dirs)
    rows: list[Row] = []
    gaps: list[str] = []
    try:
        top = sorted(os.scandir(root), key=lambda e: e.name)
    except OSError as exc:
        return [Row(str(root), "root", "probe-error", f"scandir failed: {exc}")], unreadable, gaps

    slug_dirs = [Path(e.path) for e in top if _is_slug_dir(Path(e.path))]
    root_level = [Path(e.path) for e in top if Path(e.path) not in slug_dirs]

    sid_dirs: list[Path] = []
    unreadable_slugs: list[Path] = []
    for slug in slug_dirs:
        try:
            sid_dirs.extend(
                Path(c.path) for c in os.scandir(slug) if c.is_dir(follow_symlinks=False)
            )
        except OSError:
            unreadable_slugs.append(slug)  # a row, not a silence: it vanished from the table (A14)
    held, probe_gaps, probe_ok = probe_holders(sid_dirs + root_level, proc_root)
    gaps.extend(probe_gaps)
    if not probe_ok:
        # Same asymmetry as an unreadable sessions root: liveness collapses, death survives.
        unreadable = unreadable + [str(proc_root)]

    for sid_dir in sorted(sid_dirs):
        rows.append(_classify_sid(sid_dir, by_sid, tx_dirs, held, proc_root, now, older_than_s))
    for entry in sorted(root_level):
        rows.append(_classify_root_entry(entry, held, now, unowned_days))
    for slug in sorted(unreadable_slugs):
        rows.append(
            Row(str(slug), "session", "probe-error", "a session-slug dir this run cannot read")
        )
    return rows, unreadable, sorted(set(gaps))


def _classify_sid(
    sid_dir: Path,
    by_sid: dict[str, list[dict]],
    tx_dirs: list[Path],
    held: dict[str, str],
    proc_root: Path,
    now: float,
    older_than_s: float,
) -> Row:
    sid = sid_dir.name
    p = str(sid_dir)
    records = by_sid.get(sid, [])

    if live_record(records, proc_root) is not None:
        return Row(p, "session", "live", "a sessions file matches a running pid + procStart")
    if _selfwatch_held(sid):
        return Row(p, "session", "live", "its self-watch lock is held")
    if p in held or str(sid_dir.resolve()) in held:
        return Row(p, "session", "live", "a live process holds it", held.get(p, ""))

    death = ""
    if records:
        death = "its sessions file names a pid that is gone"
    tx_age = _transcript_age(sid, tx_dirs, now)
    if tx_age is not None and tx_age > older_than_s:
        death = death or f"its transcript is {_human(tx_age)} idle"
    if not death:
        return Row(
            p, "session", "unclassified", "no live signal and no death signal — never removed"
        )

    newest, complete = newest_mtime(
        sid_dir, WalkBudget(stats=10**9, deadline_s=30.0), skip_run_folders=True
    )
    if not complete:
        # A truncated walk yields the top-level mtime, which does not move for deep in-place
        # edits — a LIVE dir would read maximally idle and be removed (review F4).
        return Row(p, "session", "unclassified", f"{death}, but the idleness walk was cut short")
    dir_age = now - newest
    if dir_age <= older_than_s:
        return Row(
            p,
            "session",
            "unclassified",
            f"{death}, but its dir was touched {_human(dir_age)} ago — a gone pid is not a finished session",
        )
    backup = _holds_backup(sid_dir)
    if backup is None:
        return Row(p, "session", "unclassified", f"{death}, but part of its tree is unreadable")
    if backup:
        return Row(
            p, "session", "dead-holds-backups", f"{death}; holds a backup shape (--include-backups)"
        )
    return Row(p, "session", "dead", f"{death}; dir idle {_human(dir_age)}", age_s=dir_age)


def _classify_root_entry(
    entry: Path, held: dict[str, str], now: float, unowned_days: float | None
) -> Row:
    p = str(entry)
    if entry.name in PROTECTED_NAMES or entry.name.endswith(PROTECTED_SUFFIXES):
        return Row(p, "root", "protected", "live system state, by name")
    backup = _holds_backup(entry)
    if backup is None:
        return Row(
            p, "root", "protected", "part of its tree is unreadable — no backup scan, no claim"
        )
    if backup:
        return Row(
            p, "root", "protected", "holds a backup shape — the root level is where baselines sit"
        )
    if p in held or str(entry.resolve()) in held:
        return Row(p, "root", "protected", "held by a live process", held.get(p, ""))
    if unowned_days is None:
        return Row(
            p, "root", "unowned", "unowned residue — pass --unowned-older-than DAYS to remove"
        )
    try:
        age = now - entry.lstat().st_mtime
    except OSError:
        return Row(p, "root", "probe-error", "stat failed")
    if age <= unowned_days * 86400:
        return Row(
            p, "root", "protected", f"only {_human(age)} old, under the {unowned_days:g}d threshold"
        )
    return Row(p, "root", "unowned", f"unowned and {_human(age)} idle")


def run_dead_mode(args: argparse.Namespace) -> int:
    root = _scratch_root()
    older = parse_duration(args.older_than or DEFAULT_DEAD_OLDER_THAN)
    sess, tx, proc, now = sessions_dirs(), transcript_dirs(), _proc_root(), _now()
    rows, unreadable, gaps = dead_sessions(
        root,
        sess,
        tx,
        proc,
        now,
        older,
        args.unowned_older_than,
    )
    if unreadable:
        # A root we cannot list has no enumerable sids: the LIVE signal collapses while the DEATH
        # signal survives, so the whole table degrades rather than calling a live session dead.
        rows = [
            Row(r.path, r.kind, "unclassified", f"unreadable root {unreadable[0]}") for r in rows
        ]
        print(render(rows, gaps=gaps))
        if args.apply:
            print(
                f"REFUSED — cannot read {', '.join(unreadable)}; no sid classified, nothing removed"
            )
            return RC_REFUSED
        return RC_OK
    # D4 (plan P9): every session's run folders, judged by marker with a walk-free DEAD rule, AFTER
    # the unreadable-root refusal above; a dead session still holding an ACTIVE one is split.
    by_sid, _ = read_sessions(sess)
    sid_dirs = [
        Path(r.path) for r in rows if r.kind == "session" and Path(r.path).parent.parent == root
    ]
    run_rows = plan_run_folders(
        sid_dirs,
        now,
        dead_of=lambda d, held: _session_dead_for_runs(d, by_sid, tx, held, proc, now, older),
        proc_root=proc,
        tx_dirs=tx,
        check_sid=False,
    )
    active = {Path(r.path).parent.parent for r in run_rows if r.cls == "kept"}
    split: list[Row] = []
    for r in rows:
        if (
            r.kind == "session"
            and r.cls in ("dead", "dead-holds-backups")
            and Path(r.path) in active
        ):
            split.extend(_split_dead_session(r, Path(r.path)))
        else:
            split.append(r)
    rows = run_rows + split
    if args.strict_proc and gaps:
        # AFTER the run rows are planned (F5): downgraded first, the run folders were planned
        # after it and escaped the flag; the dead-session split is decided first on purpose — a
        # session with an active run folder keeps its dir either way
        rows = _downgrade(rows, args, f"a same-uid /proc gap under --strict-proc ({len(gaps)})")
        run_rows = [r for r in rows if r.kind == "run"]
    if args.apply:
        with _Lock() as got:
            if not got:
                print("another sweep holds the lock — nothing done (rc 0, never a wait)")
                return RC_OK
            print(REFUSAL_SET)
            print(render(rows, gaps=gaps, allowed=_allowed_classes(args)))
            apply_run_rows(run_rows, proc_root=_proc_root())  # consumed run folders go first
            rows = _resplit_survivors(rows)  # a folder the apply-time re-check kept keeps its dir
            apply_rows(rows, _allowed_classes(args), proc_root=_proc_root())
            hub = _janitor_repo_root()
            if hub is not None:
                janitor_worktrees(hub, _now(), _proc_root(), apply=True)
        # measured AFTER the global lock drops: its `du` budget never holds the lock (review RC-F)
        if write_size_report(sid_dirs, run_rows, now) is None:
            print("size report not written (see ~/.claude/state)")
        return RC_OK
    out = render(
        rows,
        brief=args.brief,
        gaps=gaps,
        apply_cmd=_apply_command(["--dead"], args),
        allowed=_allowed_classes(args),
    )
    if out:  # `print("")` is a blank line, and --brief promises ZERO bytes
        print(out)
    hub = _janitor_repo_root()
    if hub is not None:
        janitor_worktrees(hub, _now(), _proc_root(), apply=False, brief=args.brief)
    return RC_OK


# ── mode 3: --worktrees ─────────────────────────────────────────────────────────────────────────
def _status_z(repo: Path, *extra: str) -> tuple[int, list[tuple[str, str]]]:
    """`git status --porcelain -z` → `[(XY, path)]`, git's own bytes with no C-quoting to undo.

    The line form quotes a path holding a tab, newline, quote or (with core.quotePath) any
    non-ASCII byte, and stripping the quotes without unescaping resolved the wrong path
    (W-fe6e0ed3). A rename's second field (its source) is consumed, never read as an entry.
    """
    rc, out = _git(repo, "status", "--porcelain", "-z", *extra)
    if rc != 0:
        return rc, []
    entries: list[tuple[str, str]] = []
    fields = iter(out.split("\0"))
    for rec in fields:
        if len(rec) < 4:
            continue
        entries.append((rec[:2], rec[3:]))
        if rec[0] in "RC":
            next(fields, None)
    return 0, entries


def _git(repo: Path, *args: str, timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            # git prints a non-UTF-8 byte in a worktree path unescaped; a strict decode blanked the whole
            # --worktrees table as "bad invocation". surrogateescape round-trips to the real bytes for the
            # filesystem calls, and the reconfigured stdout renders it escaped (review of 01M2ZF211…).
            errors="surrogateescape",
            timeout=timeout,
        )
        if "-z" in args:
            # a `-z` listing is machine-parsed: stderr glued on became a fake entry, and a warning at
            # rc 0 ("could not open directory") means the listing is INCOMPLETE — unreadable, so every
            # verdict built on it keeps the worktree (W-d81efab9 review A-O1)
            if p.returncode == 0 and p.stderr:
                return 1, p.stderr
            return p.returncode, p.stdout or ""
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def _worktree_registrations(repo: Path) -> list[dict]:
    """`git worktree list --porcelain` → one dict per registration; the FIRST is the main checkout."""
    rc, out = _git(repo, "worktree", "list", "--porcelain")
    if rc != 0:
        return []
    return _parse_worktree_porcelain(out)


def _parse_worktree_porcelain(out: str) -> list[dict]:
    """One dict per `git worktree list --porcelain` stanza, keyed by each line's first word."""
    entries: list[dict] = []
    cur: dict = {}
    for line in out.splitlines():
        if not line.strip():
            if cur:
                entries.append(cur)
                cur = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree" and cur:
            entries.append(cur)
            cur = {}
        cur[key] = value
    if cur:
        entries.append(cur)
    return entries


def _trailer_names(value: str) -> list[str]:
    """The branch names in one `Merged-From` value: a COMMA LIST of `branch (free-text description)`.

    Commas split only at parenthesis depth 0, so a description such as `(vendor, wiring)` or
    `(see, hotfix (x))` never yields a name of its own, and an item ending in `)` is cut at its
    FIRST ` (`. A value holding an unclosed `(` names NOBODY: past it no grammar can tell a name
    from a description word (`feat (wip, hotfix` must not vouch for `hotfix`). Each name is `.strip()`ped (else every item after the first keeps its leading
    space and matches nothing) and compared WHOLE-STRING by the caller — a substring test would let
    one branch's description word mark a different branch merged. Model limits (D-1290): a branch
    whose own name holds a comma cannot be told from two names (none exists here), and a stray `)`
    in a description (`(smile :), b (x))`) can close it early and make its later text a name.
    """
    matched, opened = set(), []
    for i, ch in enumerate(value):
        if ch == "(":
            opened.append(i)
        elif ch == ")" and opened:
            matched.add(opened.pop())
            matched.add(i)
    if opened:
        return []
    items, depth, cur = [], 0, []
    for i, ch in enumerate(value):
        if ch == "," and depth == 0:
            items.append("".join(cur))
            cur = []
            continue
        if i in matched:
            depth += 1 if ch == "(" else -1
        cur.append(ch)
    items.append("".join(cur))
    names = []
    for item in items:
        name = item.strip()
        if " (" in name and name.endswith(")"):
            name = name[: name.index(" (")].strip()
        if name:
            names.append(name)
    return names


def _target_commit(repo: Path, target: str) -> str | None:
    """`target` resolved to its commit sha, or None — ONE state for every read of one decision."""
    rc, sha = _git(repo, "rev-parse", "--verify", "-q", f"{target}^{{commit}}")
    sha = sha.strip()
    return sha if rc == 0 and re.fullmatch(r"[0-9a-f]{40,64}", sha) else None


def _vouch_map(repo: Path, target: str) -> dict[str, int] | None:
    """Each branch a `Merged-From` squash on `target` names → the time up to which it vouches.

    `target` is resolved to its commit on every call and the map is cached per COMMIT, so a
    process reads the history once per target state, and a target that moved since — forward, or
    rewound past a squash — is read afresh, never answered from the old state (D-1290). A caller
    that pairs the map with other reads passes the resolved sha as `target`, so all of them read
    the same state.
    """
    sha = _target_commit(repo, target)
    return None if sha is None else _vouch_map_at(repo, sha)


@functools.cache
def _vouch_map_at(repo: Path, sha: str) -> dict[str, int] | None:
    """The vouch map of the history ending at commit `sha` (see `_vouch_map`).

    `-z` ends each commit's record with NUL (a commit message cannot hold one), `separator=,` joins
    two trailer lines on one commit, and a record whose fields or times do not parse is skipped — it
    never vouches — instead of failing the read for every branch.

    `--no-merges` (D-1290): a merge commit's parents already say what it took, and the caller's
    `merge-base --is-ancestor` arm is the truth for it — hand merges carry reused names
    (`Merged-From: worktree-fleet`), which read merged for ever otherwise. A squash's vouch is
    `min(author, committer)` time: an amend or a rebase of the target moves only the committer
    date forward, past work the squash never took. That reading also refuses a hand squash that
    kept its first commit's author date (`commit -C`, `rebase -i`), which no date can tell from an
    amend — it fails closed. The NEWEST vouch wins (a re-squash covers the work before it).
    """
    rc, out = _git(
        repo,
        "log",
        "-z",
        "--no-merges",
        "--format=%at%x1f%ct%x1f%(trailers:key=Merged-From,valueonly,separator=%x2c)",
        sha,
    )
    if rc != 0:
        return None
    vouches: dict[str, int] = {}
    for record in out.split("\0"):
        fields = record.split("\x1f")
        if len(fields) != 3 or not fields[2].strip():
            continue
        if not (fields[0].isdigit() and fields[1].isdigit()):
            continue
        when = min(int(fields[0]), int(fields[1]))
        for name in _trailer_names(fields[2]):
            if when > vouches.get(name, -1):
                vouches[name] = when
    return vouches


def _squash_vouch(repo: Path, target: str, branch: str) -> int | None:
    """The time up to which a `Merged-From` squash on `target` vouches for `branch`, or None."""
    vouches = _vouch_map(repo, target)
    return None if vouches is None else vouches.get(branch)


def _newer_than_vouch(repo: Path, target: str, branch: str, vouch: int) -> int | None:
    """How many commits of `target..branch` are newer than `vouch`, or None when unreadable.

    A commit counts by `max(author, committer)` time, so new work reads new whichever clock
    stamped it. Equal seconds do not count: an orchestrator squash may land in the same second as
    the branch's last commit. A merge commit whose every parent after the first is already in
    `target` is read as the branch catching up and skipped, so a branch that merged its target
    back after the squash still reads merged; any other merge counts by its own time, since the
    commits it brought in may be old-dated work `target` never took. Known fail-OPEN (D-1290): work
    made inside the squash window, a commit whose BOTH dates were set before the vouch, a name
    re-pointed at older work, and a catch-up merge that also carries edits of its own (its
    content is not compared). Known fail-closed: a branch rebased after its squash (the rebase
    re-dates its commits). Pass `target` as a resolved sha when the vouch was read from one.
    """
    rc, out = _git(repo, "log", "--format=%at%x1f%ct%x1f%P", f"{target}..{branch}")
    if rc != 0:
        return None
    newer = 0
    for line in out.splitlines():
        if not line.strip():
            continue
        fields = line.split("\x1f")
        if len(fields) != 3 or not (fields[0].isdigit() and fields[1].isdigit()):
            return None
        parents = fields[2].split()
        if len(parents) > 1 and all(
            _git(repo, "merge-base", "--is-ancestor", p, target)[0] == 0 for p in parents[1:]
        ):
            continue
        if max(int(fields[0]), int(fields[1])) > vouch:
            newer += 1
    return newer


def _merged_from(repo: Path, target: str, branch: str) -> bool:
    """Was `branch` squash-merged into `target`, with nothing committed to it since?

    A trailer names a branch, not a state: branch names are reused, so a `Merged-From` squash
    vouches only when no commit of `target..branch` that `_newer_than_vouch` counts is newer than
    it. Every uncertain answer — no vouch, an unreadable log — is `False`, which keeps the worktree.
    """
    sha = _target_commit(repo, target)
    vouch = None if sha is None else _squash_vouch(repo, sha, branch)
    if sha is None or vouch is None:
        return False
    return _newer_than_vouch(repo, sha, branch, vouch) == 0


def _sync_source_for(worktree: Path, rel: str) -> Path | None:
    """The HUB file whose content the sync writes to `rel` inside `worktree`, or None.

    ⚠️ NOT `FABRIK_ROOT / rel`. Of the 208 `(src, dest)` pairs the manifest yields, 15 have
    `src != dest` — most conspicuously `CLAUDE.md`, whose source is `templates/governance/CLAUDE.md`
    (the hub's own root `CLAUDE.md` is the hub contract and is never distributed), and
    `.worktreeinclude`, which has no hub file at its dest path at all. A first cut compared against
    the dest path and could therefore never recognise the single most common synced file: measured,
    `.worktreeinclude` blocked 90 of 118 dirty worktrees by itself.
    """
    try:
        # The manifest lives in the HUB's scripts/ and this module is run from anywhere, so the
        # path insert is load-bearing: without it the import raises ModuleNotFoundError, the
        # `except` swallows it, and EVERY path answers "not sync-owned" — which is exactly why the
        # first cut cleared 0 of 118 worktrees while looking correct. Measured after fixing it.
        _hub_scripts = str(Path("/opt/fabrik") / "scripts")
        if _hub_scripts not in sys.path:
            sys.path.insert(0, _hub_scripts)
        import fabrik_synced_manifest as _fsm  # noqa: PLC0415 — optional, hub-only
    except Exception:  # noqa: BLE001
        return None
    try:
        for src, dest in _fsm.iter_synced_pairs(worktree):
            if dest == worktree / rel:
                return src
    except Exception:  # noqa: BLE001 — a manifest that cannot enumerate owns nothing
        return None
    return None


def _sync_materialised_paths(worktree: Path, names: list[str]) -> set[str]:
    """Of `names` (porcelain paths from `git status`), the ones that are the SYNC'S OWN OUTPUT.

    A path qualifies only when the manifest maps it to a hub source AND the bytes match what the
    sync would write. Three corrections the Phase E review forced, each measured:

    * the hub side is resolved through `iter_synced_pairs`, not assumed to be the same path;
    * a porcelain entry ending in `/` is an all-untracked DIRECTORY — `read_bytes` on it raises
      `IsADirectoryError` and the first cut therefore answered "not sync output" for it. Measured:
      `libs/health_probe/` blocked 62 of 118 worktrees that way. Its files are expanded and each
      one checked;
    * the comparison reads the hub's COMMITTED bytes, because `sync_enforcement_to_projects.py`
      ships `git show HEAD:<src>` for a tracked file. Comparing against the hub's working tree made
      the verdict depend on whether a sibling happened to have that file dirty.

    Anything unanswerable is simply absent from the result, which keeps the path counted as
    authored — the verdict this feeds is destructive-adjacent and fails toward keeping the work.
    """
    out: set[str] = set()
    for raw in names:
        rel = raw
        if not rel:
            continue
        if not rel.endswith("/"):
            if _is_sync_materialised(worktree, rel):
                out.add(raw)
            continue
        base = worktree / rel
        if not base.is_dir():
            continue
        # ⚠️ LAZY ON PURPOSE. Materialising the whole `rglob` into a list before `all()` can
        # short-circuit walks the entire tree for a verdict the FIRST file already decided.
        # Measured on this repo: `_sync_materialised_paths(Path("/opt/fabrik"), [".venv/"])` took
        # 1.27 s (≈32,700 files) against 0.006 s for the same answer — and an untracked
        # `node_modules/`, `dist/`, `.venv/` or `.tmp/` is exactly the shape a dirty worktree
        # carries, once per porcelain entry, across every registered worktree (round 3 of the
        # Phase E review). `any()` over the generator also gives us the empty-directory case for
        # free: `saw_one` stays False and the entry is left alone, as before.
        saw_one = False
        materialised = True
        for f in base.rglob("*"):
            if not f.is_file():
                continue
            saw_one = True
            if not _is_sync_materialised(worktree, str(f.relative_to(worktree).as_posix())):
                materialised = False
                break
        if saw_one and materialised:
            out.add(raw)
    return out


def _is_sync_materialised(worktree: Path, rel: str) -> bool:
    """Is `rel` inside this worktree byte-identical to what the sync would write there?

    The hub side is `git show HEAD:<src>` for a tracked source (what the sync ships) and the
    working-tree bytes for an untracked one. Any failure to answer returns False, which keeps the
    worktree counted as carrying authored work: this feeds a verdict about DELETING a directory.
    """
    src = _sync_source_for(worktree, rel)
    if src is None:
        return False
    try:
        mine = (worktree / rel).read_bytes()
    except OSError:
        return False
    try:
        rel_src = src.resolve().relative_to(Path("/opt/fabrik").resolve()).as_posix()
        proc = subprocess.run(
            ["git", "show", f"HEAD:{rel_src}"],
            cwd="/opt/fabrik",
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0:
            return mine == proc.stdout or _in_hub_history(rel_src, mine)
    except (OSError, ValueError):
        pass
    try:
        return mine == src.read_bytes()  # untracked hub source: the tree is all there is
    except OSError:
        return False


_HISTORY_SEEN: dict[tuple[str, str], bool] = {}


def _in_hub_history(rel_src: str, data: bytes) -> bool:
    """Do these exact bytes appear in a hub COMMIT of the sync source `rel_src`?

    The sync ships `git show HEAD:<src>`, so every copy it ever wrote is a committed version of its
    source; a worktree last synced weeks ago holds an older one, which HEAD-only comparison read as
    authored (measured 2026-10-01: CLAUDE.md, scripts/final_gate.py and scripts/enforcement/ kept 8
    of 52 wef worktrees). A COMMIT on that path is required, never mere object presence — an
    unreachable blob can be pruned, and then this copy would be the last one.
    """
    proc = subprocess.run(
        ["git", "hash-object", "--stdin"], input=data, capture_output=True, check=False
    )
    blob = proc.stdout.decode().strip()
    if proc.returncode != 0 or not blob:
        return False
    key = (rel_src, blob)
    if key not in _HISTORY_SEEN:
        found = subprocess.run(
            ["git", "log", "-1", "--format=%H", f"--find-object={blob}", "--", rel_src],
            cwd="/opt/fabrik",
            capture_output=True,
            text=True,
            check=False,
        )
        _HISTORY_SEEN[key] = found.returncode == 0 and bool(found.stdout.strip())
    return _HISTORY_SEEN[key]


# A worktree's own local settings — written per worktree (e.g. `autoMemoryDirectory`), never work.
LOCAL_SETTINGS = ".claude/settings.local.json"
# The governance sync's per-worktree ledger: path -> md5 of the bytes it wrote there
# (`sync_enforcement_to_projects.py::_WORKTREE_LEDGER_REL`). A file still matching its entry is
# exactly what the sync wrote; the hub's CURRENT bytes are the wrong test, because the sync moves on
# and every older worktree then reads its synced copies as authored (measured 2026-10-01: wef 31 of
# 52 worktrees held only such copies and build output).
SYNC_LEDGER = ".fabrik/worktree-synced.lock"
# Build output and caches judged by PATH COMPONENT anywhere in the tree — `sites/x/node_modules`
# slipped past CACHE_ALLOWLIST's prefix match. ONLY for an IGNORED path: the repo's own ignore rules
# are the proof that a `dist/` is build output; an untracked, unignored `dist/` is someone's
# directory with a familiar name, and the name alone once let `--force` delete it (review R1-S1).
# TOOL CACHES only, the class D-184's allowlist already accepted: an OUTPUT directory (`dist`,
# `test-results`) is where a report or the one trace of a failing run lands, so the name is no
# proof even when ignored (review R2-S1) — such a tree stays `wt-ignored-data` for a human.
REBUILD_DIRS = frozenset(
    {
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".astro",
    }
)


def _sync_ledger(wt: Path) -> dict[str, str]:
    try:
        data = json.loads((wt / SYNC_LEDGER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _rebuildable(
    wt: Path,
    rel: str,
    main_path: Path | None,
    ledger: dict[str, str] | None = None,
    *,
    ignored: bool = False,
) -> bool:
    """True when `rel` in worktree `wt` is NOT anyone's work, file by file.

    An IGNORED build output or cache (REBUILD_DIRS, any path component), any symlink (removal
    unlinks it, never its target), the worktree's own local settings, the sync ledger, a file still matching its sync-ledger md5,
    or a regular file byte-identical to the main checkout's file at the same path — what
    `.worktreeinclude` copied in at creation. A collapsed directory entry (`dir/`) is rebuildable
    only when every file under it is; an empty one is not.
    """
    if ignored and (
        rel.startswith(CACHE_ALLOWLIST) or REBUILD_DIRS & set(rel.rstrip("/").split("/"))
    ):
        return True
    if rel in (LOCAL_SETTINGS, SYNC_LEDGER):
        return True
    if (wt / rel.rstrip("/")).is_symlink():
        return True  # removal unlinks it; `worktree remove --force` never follows into the target
    if rel.endswith("/"):
        rc, out = _git(
            wt, "ls-files", "-z", "--others", "--exclude-standard", "--ignored", "--", rel
        )
        rc2, out2 = _git(wt, "ls-files", "-z", "--others", "--exclude-standard", "--", rel)
        if rc != 0 or rc2 != 0:
            return False
        ign = [(f, True) for f in out.split("\0") if f]
        unign = [(f, False) for f in out2.split("\0") if f]
        if not ign and not unign:
            return False
        ledger = _sync_ledger(wt)
        return all(_rebuildable(wt, f, main_path, ledger, ignored=i) for f, i in ign + unign)
    mine = wt / rel
    if mine.is_symlink() or not mine.is_file():
        return False
    try:
        data = mine.read_bytes()
    except OSError:
        return False
    want = (_sync_ledger(wt) if ledger is None else ledger).get(rel)
    if isinstance(want, str) and hashlib.md5(data, usedforsecurity=False).hexdigest() == want:
        return True
    if _is_sync_materialised(wt, rel):  # a current or older committed version of its hub source
        return True
    if main_path is None:
        return False
    if ignored and _preserved_in_backups(main_path, data, rel):
        return True
    if not (main_path / rel).is_file():
        return False
    try:
        return data == (main_path / rel).read_bytes()
    except OSError:
        return False


# The main checkout's `backups/` index — size -> top-level regular files — keyed on the directory's
# own mtime so a file archived mid-run is seen (W-18e66a92).
_BACKUP_INDEX: dict[str, tuple[int, dict[int, list[Path]]]] = {}


def _preserved_in_backups(main_path: Path, data: bytes, rel: str) -> bool:
    """True when `data` — a NON-EMPTY ignored file's bytes — equals a top-level regular file in the
    main checkout's `backups/` (the sanctioned secrets archive, CLAUDE.md § Pointers): a stale
    `.worktreeinclude` copy whose bytes are preserved is not data (W-18e66a92). Only IGNORED files
    reach here — an untracked file is someone's work whatever it equals. Fails CLOSED: an empty file,
    a symlinked or non-directory `backups/`, a symlinked, unreadable or non-regular entry never match.
    The backup's NAME must name the file it preserves (`hub.env.retired-….backup` for `.env`): a
    short generic file may share its bytes with an unrelated backup (review S1). Each candidate is
    opened `O_NOFOLLOW|O_NONBLOCK` and `fstat`-checked before it is read, because the index is cached
    on the directory's mtime and an entry swapped for a FIFO or a symlink inside one tick would
    otherwise hang the janitor or be followed (review C3).
    COBRA: the cheapest way to make a tree removable is to copy its bytes into backups/ — which
    preserves them, the outcome this rule exists for."""
    name = Path(rel.rstrip("/")).name
    if not data or not name:
        return False
    root = main_path / "backups"
    try:
        if root.is_symlink() or not root.is_dir():
            return False
        stamp = root.stat().st_mtime_ns
    except OSError:
        return False
    cached = _BACKUP_INDEX.get(str(root))
    if cached is None or cached[0] != stamp:
        index: dict[int, list[Path]] = {}
        try:
            with os.scandir(root) as it:
                for e in it:
                    try:
                        if e.is_file(follow_symlinks=False):
                            index.setdefault(e.stat(follow_symlinks=False).st_size, []).append(
                                Path(e.path)
                            )
                    except OSError:
                        continue
        except OSError:
            return False
        cached = (stamp, index)
        _BACKUP_INDEX[str(root)] = cached
    for candidate in cached[1].get(len(data), []):
        if name not in candidate.name:
            continue
        try:
            fd = os.open(candidate, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            continue
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_size != len(data):
                continue
            with os.fdopen(os.dup(fd), "rb") as fh:
                if fh.read(len(data) + 1) == data:
                    return True
        except OSError:
            continue
        finally:
            os.close(fd)
    return False


def _ignored_data(repo_wt: Path, main_path: Path | None = None) -> list[str]:
    """Ignored paths that are DATA, not rebuildable cache.

    `git worktree remove` deletes ignored files silently even WITHOUT `--force` (measured), so a
    worktree holding `.tmp/subagents/pg_outbox.jsonl` — which cleanup-automation § D marks
    NEVER-delete — would be removed while `git status --porcelain` reported it clean.
    """
    rc, entries = _status_z(repo_wt, "--ignored=matching")
    if rc != 0:
        # unreadable is not "no data": both callers keep the worktree on any hit (review A-O5)
        return ["(the --ignored listing is unreadable)"]
    hits: list[str] = []
    for xy, path in entries:
        if xy != "!!":
            continue
        if any(path.startswith(c) or f"/{c}" in path for c in CACHE_ALLOWLIST):
            continue
        if main_path is not None and _rebuildable(repo_wt, path, main_path, ignored=True):
            continue  # a creation copy identical to the main checkout's — not data (D-478)
        hits.append(path)
    return hits


def _stash_branches(repo: Path) -> tuple[set[str], bool]:
    """`({branch names named by a stash}, any detached `(no branch)` stash?)`.

    Stashes live in the shared repo, not per-worktree, and neither `status --porcelain` nor
    `worktree list` shows them — so a worktree whose only unfinished state is a stash reads clean.
    """
    rc, out = _git(repo, "stash", "list")
    named: set[str] = set()
    detached = False
    if rc != 0:
        return named, detached
    for line in out.splitlines():
        for marker in ("WIP on ", "On "):
            if marker in line:
                rest = line.split(marker, 1)[1]
                name = rest.split(":", 1)[0].strip()
                if name == "(no branch)":
                    detached = True
                elif name:
                    named.add(name)
                break
    return named, detached


def classify_worktrees(
    repo: Path,
    now: float,
    proc_root: Path,
    session_start: float | None,
    include_harness: bool = False,
    foreign_older_than_s: float | None = None,
) -> list[Row]:
    """One row per registration, plus every unregistered directory under `.claude/worktrees/`."""
    entries = _worktree_registrations(repo)
    if not entries:
        return [
            Row(str(repo), "worktree", "unclassified", "not a git repo, or git refused to list")
        ]
    main_path = Path(entries[0].get("worktree", str(repo)))
    rc, target_out = _git(main_path, "branch", "--show-current")
    target = target_out.strip() if rc == 0 else ""
    others = entries[1:]

    if not target:
        return [
            Row(
                e.get("worktree", "?"),
                "worktree",
                "unclassified",
                "the main checkout is on a detached HEAD — no merge target, nothing removable",
            )
            for e in others
        ]

    stashed, detached_stash = _stash_branches(main_path)
    paths = [Path(e["worktree"]) for e in others if e.get("worktree")]
    held, _gaps, probe_ok = probe_holders(paths, proc_root)
    if not probe_ok:
        return [
            Row(
                e.get("worktree", "?"),
                "worktree",
                "unclassified",
                f"the /proc holder probe ({proc_root}) is unreadable — nothing is provably unheld",
            )
            for e in others
        ]
    rows: list[Row] = []
    for e in others:
        rows.append(
            _classify_worktree(
                Path(e["worktree"]),
                e,
                repo,
                main_path,
                target,
                stashed,
                detached_stash,
                held,
                session_start,
                now,
                foreign_older_than_s,
            )
        )
    rows.extend(_orphan_worktree_dirs(repo, {e.get("worktree", "") for e in entries}))
    return rows


def _classify_worktree(
    path: Path,
    entry: dict,
    repo: Path,
    main_path: Path,
    target: str,
    stashed: set[str],
    detached_stash: bool,
    held: dict[str, str],
    session_start: float | None,
    now: float,
    foreign_older_than_s: float | None = None,
) -> Row:
    p = str(path)
    # `refs/heads/feat/foo` is the branch `feat/foo`, not `foo`. Truncating at the LAST slash
    # judged the wrong branch on every consumer and `git branch -d` deleted an unrelated branch
    # that happened to share the basename (round-2 A2, proven). 5 of 104 live worktree branches
    # carry a slash today.
    branch = entry.get("branch", "").removeprefix("refs/heads/") if entry.get("branch") else ""

    if not branch:
        return Row(
            p, "worktree", "unclassified", "a detached-HEAD worktree — no branch to reason about"
        )

    # Provenance by AGE, not by a sid marker: CLAUDE_BASE holds the base COMMIT SHA and nothing in
    # the repo reads it, so the implementable test is the registration's own mtime against this
    # session's start — and it fails CLOSED when the start cannot be resolved.
    gitdir_meta = repo / ".git" / "worktrees" / path.name / "gitdir"
    if session_start is None:
        return Row(
            p,
            "worktree",
            "wt-foreign",
            "this session's start time is unresolvable — nothing removable",
        )
    try:
        registered = gitdir_meta.stat().st_mtime
    except OSError:
        return Row(p, "worktree", "wt-foreign", "no registration metadata — provenance unprovable")
    # DORMANCY, not authorship. The provenance guard used to RETURN here, so dirty / unmerged /
    # held / ignored-data were never evaluated for a foreign tree — which made `--apply` a
    # guaranteed no-op for the only population this mode exists for: accumulated residue is BY
    # DEFINITION older than every future session, so the one session allowed to remove it is the
    # one that created it, and that session is gone. Filed independently by two repos on the same
    # day with the same denominator shape (web-ecommerce-factory 30 of 30 rows `wt-foreign`,
    # fabrik-lib 10 of 10, oldest 66-68d). `--foreign-older-than` does not WEAKEN the chain — it
    # lets the chain RUN, and only a `wt-removable` verdict is promoted.
    dormant = (
        registered < session_start
        and foreign_older_than_s is not None
        and (now - registered) >= foreign_older_than_s
    )
    if registered < session_start and not dormant:
        return Row(
            p,
            "worktree",
            "wt-foreign",
            "registered before this session started — not this run's to remove",
            f"registered {_human(now - registered)} ago"
            + ("" if foreign_older_than_s is None else "; --foreign-older-than to judge it"),
        )

    is_harness = (
        ".claude/worktrees/" in p
        or (repo / ".git" / "worktrees" / path.name / "CLAUDE_BASE").exists()
    )
    verdict, reason, evidence = _worktree_chain(
        path, entry, main_path, target, branch, stashed, detached_stash, held
    )
    if dormant and verdict == "wt-prunable":
        # `wt-prunable` is in REMOVABLE, but acting on it runs `git worktree prune`, which is
        # REPO-WIDE: it would drop OTHER sessions' stale registrations as a side effect of a flag
        # aimed at one dormant tree. The dormancy flag never buys that; the operator runs prune.
        return Row(
            p,
            "worktree",
            "wt-foreign",
            "dormant, but its registration is stale and `git worktree prune` is repo-wide — "
            "run it yourself rather than have one tree's flag drop every session's registration",
            f"registered {_human(now - registered)} ago",
        )
    if is_harness:
        # TAG, never short-circuit — and the tag is only applied when the CHAIN said removable.
        # Returning `wt-harness` for a dirty / unmerged / ignored-data tree too would let
        # `--include-harness` delete it: the flag gates on the CLASS, so a non-removable chain
        # verdict must survive as the class. A clean-but-unmerged tree gets no git refusal to save
        # it (measured — the review's F1 removed a `data/only-copy.jsonl` this way).
        if verdict in ("wt-removable", "wt-prunable"):
            # `wt-prunable` is in REMOVABLE too, so a harness tree whose dir is gone would have had
            # its registration pruned with no flag — and `git worktree prune` is repo-wide, so it
            # drops other sessions' stale registrations with it (round-2 A13).
            return Row(
                p,
                "worktree",
                "wt-harness",
                f"harness-created ({verdict}); --include-harness to act",
                reason,
            )
        return Row(p, "worktree", verdict, f"harness-created; {reason}", evidence)
    if dormant:
        # Every refusal keeps its OWN class — dirty / unmerged / held / locked / ignored-data are
        # each strictly more informative than the blanket `wt-foreign` this used to return, and
        # only `wt-removable` is in REMOVABLE. The dormancy is named in the reason so an operator
        # reading the table sees WHY this row became actionable when it never was before.
        return Row(
            p,
            "worktree",
            verdict,
            f"dormant {_human(now - registered)} — {reason}",
            evidence,
        )
    return Row(p, "worktree", verdict, reason, evidence)


def _worktree_chain(
    path: Path,
    entry: dict,
    main_path: Path,
    target: str,
    branch: str,
    stashed: set[str],
    detached_stash: bool,
    held: dict[str, str],
) -> tuple[str, str, str]:
    p = str(path)
    if "locked" in entry:
        return (
            "wt-locked",
            f"locked — `git worktree unlock {p}` then re-run",
            entry.get("locked", ""),
        )
    if "prunable" in entry or not path.exists():
        return (
            "wt-prunable",
            "its directory is gone — the registration is stale",
            entry.get("prunable", ""),
        )
    if p in held or str(path.resolve()) in held:
        return "wt-held", "a live process is working in it", held.get(p, "")
    rc, entries = _status_z(path)
    if rc != 0:
        # an unreadable status is not a clean one: the verdict this feeds is destructive-adjacent
        return "wt-dirty", f"its status is unreadable (git status rc {rc})", ""
    if entries:
        all_names = [n for _, n in entries]
        untracked = {n for xy, n in entries if xy == "??"}
        # T12.23 (01M23JK2R, reported by wef3): the governance sync MATERIALISES manifest-owned
        # files into a worktree, so a worktree nobody has touched reads dirty. Those paths are not
        # "uncommitted work" by any session — nothing authored them.
        #
        # ⚠️ BUT THIS DOES NOT MAKE THE WORKTREE REMOVABLE, and the first cut of this fix wrongly
        # implied it would. Executed: `git worktree remove` REFUSES while any untracked file is
        # present ("contains modified or untracked files, use --force"), and `apply_worktrees`
        # never passes `--force` — deliberately, because forcing is how work disappears. The sync's
        # output is untracked, so promoting such a worktree to `wt-removable` would trade a correct
        # informative row for a wrong one plus a refusal at runtime. It gets its OWN verdict:
        # nothing authored here, and still not ours to delete.
        sync_only = _sync_materialised_paths(path, all_names)
        rebuildable = {
            n
            for n in all_names
            if n in untracked and n not in sync_only and _rebuildable(path, n, main_path)
        }
        authored = [n for n in all_names if n not in sync_only and n not in rebuildable]
        sync_only |= rebuildable
        if authored:
            shown = ", ".join(authored[:5]) + ("…" if len(authored) > 5 else "")
            return "wt-dirty", f"uncommitted work ({len(authored)}): {shown}", ""
    else:
        sync_only = set()
    # The sync-only verdict waits until the stash and ignored-data checks have run: removing such a
    # tree needs --force, and --force also deletes ignored files and orphans a stash's branch work.
    if branch in stashed:
        return (
            "wt-dirty",
            "a stash names this branch — invisible to status and to worktree list",
            "",
        )
    if detached_stash:
        return "wt-dirty", "a `(no branch)` stash exists and cannot be attributed to a branch", ""
    ignored = _ignored_data(path, main_path)
    if ignored:
        shown = ", ".join(ignored[:5]) + ("…" if len(ignored) > 5 else "")
        return (
            "wt-ignored-data",
            f"ignored DATA git would delete anyway ({len(ignored)}): {shown}",
            "",
        )
    if sync_only:
        shown = ", ".join(sorted(sync_only)[:5]) + ("…" if len(sync_only) > 5 else "")
        return (
            "wt-sync-only",
            f"nothing authored — all {len(sync_only)} dirty path(s) are the governance sync's "
            f"output or creation copies identical to the main checkout ({shown}); removable only "
            f"under --include-unmerged (with --force, re-checked at removal); git's own `branch -d` then "
            f"drops the branch only if it is merged",
            "",
        )
    rc_anc, _ = _git(main_path, "merge-base", "--is-ancestor", branch, target)
    if rc_anc != 0 and not _merged_from(main_path, target, branch):
        rc_n, ahead = _git(main_path, "rev-list", "--count", f"{target}..{branch}")
        n = ahead.strip() if rc_n == 0 else "?"
        why = f"not merged into {target} (ahead {n})"
        sha = _target_commit(main_path, target)
        vouch = None if sha is None else _squash_vouch(main_path, sha, branch)
        newer = None if vouch is None else _newer_than_vouch(main_path, sha, branch, vouch)
        if newer:
            why += f"; {newer} commit(s) newer than the Merged-From squash that names it"
        return "wt-unmerged", why, ""
    return "wt-removable", f"merged into {target}, clean, unlocked, unheld", ""


def _orphan_worktree_dirs(repo: Path, registered: set[str]) -> list[Row]:
    """A directory under `.claude/worktrees/` that git does not register at all.

    Invisible to `git worktree list`, so the mode would under-report the residue it exists to
    surface. Never removable at any flag — it is a `/opt/<repo>` path.
    """
    base = repo / ".claude" / "worktrees"
    rows: list[Row] = []
    if not base.is_dir():
        return rows
    try:
        for child in sorted(os.scandir(base), key=lambda e: e.name):
            if not child.is_dir(follow_symlinks=False):
                continue
            if str(Path(child.path).resolve()) in {str(Path(r).resolve()) for r in registered if r}:
                continue
            rows.append(
                Row(
                    child.path,
                    "worktree",
                    "wt-orphan-dir",
                    "a directory git does not register — listed, never removable",
                    size_kb=_du_kb(Path(child.path), time.monotonic() + 2),
                )
            )
    except OSError:
        pass
    return rows


def _not_sync_only_now(path: Path, branch: str, repo: Path) -> str:
    """Why a `wt-sync-only` tree may NOT be force-removed now ('' when it still may).

    `--force` deletes untracked AND ignored files, so the classification is re-earned at removal
    time: a file authored since the dry run, a stash naming the branch, or ignored data keeps it.
    """
    rc, entries = _status_z(path)
    if rc != 0:
        return "its status is unreadable"
    names = [n for _, n in entries]
    untracked = {n for xy, n in entries if xy == "??"}
    synced = _sync_materialised_paths(path, names)
    authored = [
        n for n in names if n not in synced and not (n in untracked and _rebuildable(path, n, repo))
    ]
    if authored:
        return f"{len(authored)} authored path(s) appeared ({authored[0]})"
    stashed, detached = _stash_branches(repo)
    if branch in stashed or detached:
        return "a stash now names its branch"
    if _ignored_data(path, repo):
        return "it now holds ignored data"
    return ""


def apply_worktrees(
    repo: Path, rows: list[Row], allowed: set[str], out=sys.stdout, prune: bool = True
) -> int:
    """`git worktree remove` (never `--force`) then `git branch -d` (never `-D`).

    A SQUASH-merged branch is not an ancestor, so `-d` REFUSES it: the worktree goes and the branch
    survives with git's own refusal printed. That is the correct conservative end state.
    """
    # The branch comes from git's OWN registration, never from the directory name: a worktree at
    # `wt-merged` can be on `feat-merged`, and a name-derived guess silently deletes nothing.
    branches = {
        e["worktree"]: e.get("branch", "").removeprefix("refs/heads/")
        for e in _worktree_registrations(repo)
        if e.get("worktree")
    }
    removed = 0
    for r in rows:
        if r.cls not in allowed:
            continue
        if r.cls == "wt-prunable":
            _git(repo, "worktree", "prune")
            print(f"PRUNED {r.path} (stale registration)", file=out)
            removed += 1
            continue
        branch = branches.get(r.path, "")
        force: list[str] = []
        if r.cls == "wt-sync-only":
            why = _not_sync_only_now(Path(r.path), branch, repo)
            if why:
                print(f"REFUSED {r.path} — {why} since it was classified", file=out)
                continue
            force = ["--force"]
        rc, msg = _git(repo, "worktree", "remove", *force, r.path)
        if rc != 0:
            print(
                f"REFUSED {r.path} — git: {msg.strip().splitlines()[0] if msg.strip() else rc}",
                file=out,
            )
            continue
        removed += 1
        print(f"REMOVED {r.path} ({r.cls}, {r.reason})", file=out)
        if not branch:
            print("  branch kept — git registered no branch for it", file=out)
            continue
        if r.cls == "wt-unmerged":
            print(f"  branch {branch} kept — unmerged, its commits stay reachable", file=out)
            continue
        rc_b, msg_b = _git(repo, "branch", "-d", branch)
        if rc_b != 0 and msg_b.strip():
            # A SQUASH-merged branch is not an ancestor, so `-d` refuses it. The worktree is gone
            # and the branch survives with git's own words — the conservative end state, never -D.
            print(f"  branch {branch} kept — git: {msg_b.strip().splitlines()[0]}", file=out)
    if removed and prune:
        # Only after we actually removed something, and said so: `git worktree prune` is REPO-WIDE
        # and drops other sessions' stale registrations too, so running it unconditionally made a
        # zero-candidate apply mutate the repo silently (round-3, sub-threshold).
        print("PRUNED stale registrations (repo-wide `git worktree prune`)", file=out)
        _git(repo, "worktree", "prune")
    return removed


# ── the janitor's harness pass (W-18e66a92) ─────────────────────────────────────────────────────
# A dead subagent's harness worktree is never removed by the session that made it (that session is
# gone) and `--worktrees` cannot run from cron (no session start resolves). `--dead` therefore runs
# this pass over the hub's MAIN checkout: only `<repo>/.claude/worktrees/agent-<hex>` trees (work.py's
# `_HARNESS_RE`; the named `fleet`/`intel`/`kaizen` trees are peers' and never taken), only when the
# chain says removable AND the registration shows no commit or checkout for HARNESS_DORMANT_S, and never a
# repo-wide `git worktree prune`. A removed tree's MERGED branch goes with `git branch -d`, as every
# `--worktrees --apply` does; its commits stay reachable.
HARNESS_DORMANT_S = 3 * 24 * 3600
_HARNESS_NAME_RE = re.compile(r"agent-[0-9a-f]{16,}")


def _janitor_repo_root() -> Path | None:
    """The MAIN checkout of the repo this script lives in — a linked worktree's copy resolves to it
    through the common git dir, so the pass never runs against a worktree's own `.git` file."""
    # The seam (review C1): the existing `--dead --apply` tests run this script as a subprocess, and
    # a repo derived from `__file__` alone pointed them at the LIVE hub. Set, it names the repo;
    # set and empty, the pass is skipped.
    seam = os.environ.get("SCRATCH_SWEEP_JANITOR_REPO")
    if seam is not None:
        return Path(seam) if seam and Path(seam).is_dir() else None
    here = Path(__file__).resolve().parent
    rc, out = _git(here, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if rc != 0 or not out.strip():
        return None
    common = Path(out.strip().splitlines()[0])
    return common.parent if common.name == ".git" else None


def _tree_registration(repo: Path, tree: Path) -> Path | None:
    """The tree's OWN registration dir, read from its `.git` file (`gitdir: <meta>`), and only when
    that dir sits in `repo/.git/worktrees/`. Git suffixes a colliding basename (`agent-x1`), so
    `repo/.git/worktrees/<basename>` can be ANOTHER tree's registration (review C2)."""
    try:
        text = (tree / ".git").read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("gitdir:"):
        return None
    meta = Path(text[len("gitdir:") :].strip())
    try:
        if meta.parent.resolve() != (repo / ".git" / "worktrees").resolve():
            return None
    except OSError:
        return None
    return meta


def _last_git_activity(meta: Path) -> float | None:
    """The newest mtime of the registration's gitdir, HEAD and logs/HEAD — the last commit or
    checkout in the tree, not its creation. Never `index`: the classifier's own `git status`
    rewrites it, so every run would read every tree as active (measured on the fixture). A tree
    with uncommitted work is caught by the chain as dirty, so HEAD's movement is the activity left."""
    stamps: list[float] = []
    for rel in ("gitdir", "HEAD", "logs/HEAD"):
        try:
            stamps.append((meta / rel).stat().st_mtime)
        except OSError:
            continue
    return max(stamps) if stamps else None


def janitor_worktrees(
    repo: Path,
    now: float,
    proc_root: Path,
    apply: bool,
    out=sys.stdout,
    brief: bool = False,
) -> list[Row]:
    """Classify, and with `apply` remove, the dormant harness worktrees of `repo`."""
    rows = classify_worktrees(repo, now, proc_root, now, True, HARNESS_DORMANT_S)
    try:
        home = (repo / ".claude" / "worktrees").resolve()
    except OSError:
        return []
    picked: list[Row] = []
    for r in rows:
        p = Path(r.path)
        if p.parent.resolve() != home or not _HARNESS_NAME_RE.fullmatch(p.name):
            continue
        if r.cls == "wt-harness":
            meta = _tree_registration(repo, p)
            last = None if meta is None else _last_git_activity(meta)
            if last is None or now - last < HARNESS_DORMANT_S:
                r = Row(
                    r.path,
                    r.kind,
                    "wt-foreign",
                    "harness tree with recent git activity — not dormant",
                    "" if last is None else f"last git activity {_human(now - last)} ago",
                )
            else:
                r = Row(
                    r.path,
                    r.kind,
                    r.cls,
                    "dormant harness tree, merged and clean — the janitor removes it",
                    f"last git activity {_human(now - last)} ago",
                )
        picked.append(r)
    if picked and not brief:
        print(render(picked, allowed={"wt-harness"}), file=out)
    if apply:
        apply_worktrees(repo, picked, {"wt-harness"}, out=out, prune=False)
    return picked


def run_worktrees_mode(args: argparse.Namespace) -> int:
    repo = Path(args.worktrees or ".").resolve()
    sid = session_id(args.session)
    start = None
    forced = os.environ.get("SCRATCH_SWEEP_FORCE_START")
    if forced and os.environ.get("SCRATCH_SWEEP_TEST") == "1":
        # Gated behind an explicit test flag, unlike SCRATCH_SWEEP_NOW: a clock cannot by itself
        # authorize removing another session's worktree, but this seam overrides the provenance
        # guard whose whole fail direction is "everything foreign" (review F8).
        try:
            start = float(forced)
        except ValueError:
            start = None
    elif sid and SID_RE.fullmatch(sid):
        by_sid, _ = read_sessions(sessions_dirs())
        start = session_start_epoch(by_sid.get(sid, []))
    foreign_s: float | None = None
    if args.foreign_older_than is not None:
        try:
            foreign_s = parse_duration(args.foreign_older_than)
        except ValueError as exc:
            print(f"--foreign-older-than: {exc}", file=sys.stderr)
            return RC_USAGE
    rows = classify_worktrees(repo, _now(), _proc_root(), start, args.include_harness, foreign_s)
    if args.strict_proc:
        _held, wt_gaps, _ok = probe_holders([Path(r.path) for r in rows], _proc_root())
        if wt_gaps:
            rows = _downgrade(
                rows, args, f"a same-uid /proc gap under --strict-proc ({len(wt_gaps)})"
            )
    if args.apply:
        with _Lock() as got:
            if not got:
                print("another sweep holds the lock — nothing done (rc 0, never a wait)")
                return RC_OK
            print(REFUSAL_SET)
            print(render(rows, allowed=_allowed_classes(args)))
            apply_worktrees(repo, rows, _allowed_classes(args))
        return RC_OK
    out = render(
        rows,
        brief=args.brief,
        apply_cmd=_apply_command(
            ["--worktrees", str(repo), "--session", sid] if sid else ["--worktrees", str(repo)],
            args,
        ),
        allowed=_allowed_classes(args),
    )
    if out:
        print(out)
    return RC_OK


# ── mode 4: --hook (SessionStart) ───────────────────────────────────────────────────────────────
def run_hook_mode(args: argparse.Namespace, sid_hint: str) -> int:
    """One advisory line at SessionStart, at most once per session — and again only if it GREW.

    `UserPromptSubmit` was measured and rejected: 9 of 9 live sessions fire on EVERY prompt, which
    is wallpaper. The stamp records the count seen at EVERY evaluation, a silent zero included —
    recording only on a PRINT makes it a monotone high-water mark that `--apply` never lowers, so
    an agent that complied would silence its own advisory.

    Exit 0 on every path: a hook must never block a session start.
    """
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
        sid = str(payload.get("session_id") or "").strip() or sid_hint
        if not sid or not SID_RE.fullmatch(sid):
            return RC_OK
        cwd = str(payload.get("cwd") or os.getcwd())
        if (
            os.environ.get("CLAUDE_MESH_HEADLESS") == "1"
            or os.environ.get("CLAUDE_MESH_AUTONOMOUS") == "1"
            or not (cwd == "/opt" or cwd.startswith("/opt/"))
        ):
            return RC_OK
        root = _scratch_root()
        try:
            alarm = _size_alarm_line(sid, root)
        except Exception as exc:  # noqa: BLE001 — the alarm never costs the session its other line
            alarm = ""
            print(
                f"scratch_sweep --hook: alarm skipped — {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
        if alarm:
            print(alarm)
        older = parse_duration(args.older_than or DEFAULT_OLDER_THAN)
        # `SCRATCH_SWEEP_HOOK_BUDGET` is the test seam for the truncation path — the real budget is
        # a wall-clock deadline, which a grader cannot force deterministically.
        try:
            stats = int(os.environ.get("SCRATCH_SWEEP_HOOK_BUDGET") or WALK_BUDGET)
        except ValueError:
            stats = WALK_BUDGET
        budget = WalkBudget(stats=stats, deadline_s=HOOK_DEADLINE_S)
        # The budget's clock starts at CONSTRUCTION and `probe_holders` runs inside it, so the
        # holder probe spends the same deadline the walk does — measured 2.64 s of probe + 0.50 s
        # of walk on this box's largest pad (52,320 entries), which is why HOOK_DEADLINE_S is 4.0
        # and not 1.0. A pad that outgrows the deadline truncates and stays silent rather than
        # printing a shrunken count; it is not built earlier than this on purpose.
        rows, _gaps, probe_ok = classify_session(
            root, sid, _now(), older, budget=budget, with_size=False, cwd=cwd, run_folders=False
        )
        if not probe_ok:
            return RC_OK  # nothing is provably unheld — say nothing rather than something false
        candidates = [r for r in rows if r.cls == "stale"]
        session_dirs = find_session_dirs(root, sid, cwd)
        stamp = (session_dirs[0] / NAG_STAMP) if session_dirs else None
        previous = -1
        if stamp is not None and stamp.exists():
            try:
                previous = int(stamp.read_text(encoding="utf-8").strip() or -1)
            except (OSError, ValueError):
                previous = -1
        if budget.exhausted:
            # A truncated walk yields a LOWER BOUND that varies run to run — the unwalked entries
            # default to `fresh`, so the same pad reports 300 then 340 and reads as "grown", and
            # the line re-fired on every SessionStart (measured on the three largest live pads).
            # So an uncertain count is neither SPOKEN nor RECORDED: returning before the stamp
            # write leaves the last certain number in place, and the next complete walk speaks
            # normally. Recording it here instead would be the worse bug — it silenced exactly the
            # scratchpads with the most residue, which is the "never to silence" rule inverted.
            return RC_OK
        if stamp is not None:
            try:
                stamp.write_text(str(len(candidates)), encoding="utf-8")
            except OSError:
                pass
        if not candidates or len(candidates) <= previous:
            return RC_OK
        # `Row.age_s` is set on every stale row by the walk that just ran, so the exact oldest is
        # free. It used to be `max(...) for r in candidates[:20]` over NAME order — a bounded max
        # printed as if unbounded (measured: `oldest 3.52d` where the true oldest was 3.73d), and
        # it re-walked 20 entries AFTER the deadline the rest of this function respects.
        ages = [r.age_s for r in candidates if r.age_s is not None]
        oldest = f"oldest {_human(max(ages))}" if ages else ""
        print(
            f"## 🧹 SCRATCH: {len(candidates)} stale entries in this session's scratchpad "
            f"({oldest}) — dry-run: python3 /opt/fabrik/scripts/scratch_sweep.py · "
            "apply: python3 /opt/fabrik/scripts/scratch_sweep.py --apply · "
            "never touches: /opt files, transcripts, ~/.claude/state (beyond its own lock and "
            "scratch-size-report.json), "
            "another live session's scratch, or tasks/"
        )
    except Exception as exc:  # noqa: BLE001 — fail-open by contract, but never SILENT
        print(f"scratch_sweep --hook: skipped — {type(exc).__name__}: {exc}", file=sys.stderr)
    return RC_OK


if __name__ == "__main__":
    sys.exit(main())
