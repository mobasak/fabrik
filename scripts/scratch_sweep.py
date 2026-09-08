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
import fcntl
import glob as globmod
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# ── the refusal set — printed verbatim by --help and by every apply run (constraint 2) ──────────
REFUSAL_SET = """NEVER TOUCHES (hard-coded; this text is printed by --help and by every --apply run):
  * /opt/<repo> tracked or untracked files — except a `git worktree remove` of a worktree this
    script classified removable
  * ~/.claude*/projects transcripts, and ~/.claude*/state EXCEPT the one file it creates and locks,
    $HOME/.claude/state/scratch-sweep.lock — it reads, writes and deletes nothing else there
  * <repo>/.tmp/** as a scan root (the subagent spools; a worktree git itself reports under .tmp is
    classified like any other worktree and spared by the ordinary guards, never swept as a spool)
  * docker anything — volumes are DATA
  * another LIVE session's scratch, and this session's own tasks/ directory
  * a symlink's target — a symlinked entry is `unclassified` and is never followed
  * a HARNESS-owned worktree (<repo>/.claude/worktrees/**, or a .git/worktrees/<n>/CLAUDE_BASE
    marker) unless --include-harness AND its own chain verdict is wt-removable
  * a worktree this session did not create (wt-foreign), one holding IGNORED files outside the
    cache allowlist (wt-ignored-data), or a directory git does not register (wt-orphan-dir)
  * anything holding a BACKUP SHAPE — *.bak, *.original, *pristine* (case-insensitive),
    before.txt/after.txt, .keep — the entry's OWN NAME included, unless --include-backups
  * a root-level entry of the scratch root, unless --unowned-older-than DAYS
Held, kept, fresh, dirty, unmerged, locked, foreign, orphan-dir, ignored-data and unclassifiable
entries are LISTED with their reason and never removed."""

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

        for _dirpath, dirnames, filenames in os.walk(entry, followlinks=False, onerror=_boom):
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
            # Only a SAME-REAL-UID denial is a gap; anything else cannot reach the 0700 root.
            if _real_uid(proc_root, pid) == me:
                gaps.append(f"{pid} ({comm})")
        for link in links:
            for prefix, target in prefixes:
                if link == prefix or link.startswith(prefix.rstrip("/") + "/"):
                    held.setdefault(str(target), f"pid {pid} {comm}")
    return held, gaps, True


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


def newest_mtime(entry: Path, budget: WalkBudget) -> tuple[float, bool]:
    """`(newest mtime in the entry's tree, complete?)`.

    NOT the directory's own mtime: a directory's mtime moves only when a direct child is added,
    removed or renamed — a file rewritten in place ten levels down never touches it, so an entry
    under active work read `stale` (measured; plan review pass 2).
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

        for dirpath, dirnames, filenames in os.walk(entry, followlinks=False, onerror=_boom):
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
            ["du", "-sk", str(path)], capture_output=True, text=True, timeout=3
        ).stdout.split()
        return int(out[0]) if out else None
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


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
                and SID_RE.match(child.name)
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
) -> tuple[list[Row], list[str], bool]:
    """`(rows, proc gaps, probe_ok)` — one row per top-level entry. `tasks/` is never touched."""
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
        gaps.extend(probe_gaps)
        probe_ok = probe_ok and ok
        for entry in paths:
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
    """

    def __init__(self) -> None:
        self.path = Path(os.path.expanduser(LOCK_PATH))
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
                shutil.rmtree(p)  # raises on a symlink by design — never follows one
            else:
                continue
            removed += 1
            print(f"REMOVED {r.path} ({r.cls}, {r.reason})", file=out)
        except OSError as exc:
            print(f"FAILED {r.path} ({exc.errno}: {exc.strerror})", file=out)
    return removed


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
        "--include-harness",
        action="store_true",
        help="let a harness worktree be removed when its own verdict is wt-removable",
    )
    ap.add_argument(
        "--include-backups", action="store_true", help="let a backup-holding entry be removed"
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
    return ap


def _downgrade(rows: list[Row], args: argparse.Namespace, reason: str) -> list[Row]:
    """Turn every REMOVABLE row into `probe-error` — the whole removal set, not just `stale`.

    Downgrading `stale` alone INVERTS the protection under `--strict-proc --include-backups`: the
    plain entries are spared while the ones carrying revert-test baselines are removed (round-3).
    """
    allowed = _allowed_classes(args)
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
    args = build_parser().parse_args(argv)
    try:
        if args.unowned_older_than is not None and not (args.unowned_older_than >= 1):
            # `--unowned-older-than 0` made every non-protected root entry removable at any age
            # (review F5): 33 entries / 2.3 GB on the live box, including one 60 seconds old.
            raise ValueError(
                f"--unowned-older-than must be at least 1 day, got {args.unowned_older_than!r}"
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
        sid = session_id(args.session)
        if not sid:
            print("no session id — pass --session or set CLAUDE_SESSION_ID", file=sys.stderr)
            return RC_USAGE
        if not SID_RE.match(sid):
            print(f"refusing a malformed session id {sid!r}", file=sys.stderr)
            return RC_USAGE
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

    newest, complete = newest_mtime(sid_dir, WalkBudget(stats=10**9, deadline_s=30.0))
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
    rows, unreadable, gaps = dead_sessions(
        root,
        sessions_dirs(),
        transcript_dirs(),
        _proc_root(),
        _now(),
        older,
        args.unowned_older_than,
    )
    if args.strict_proc and gaps:
        rows = _downgrade(rows, args, f"a same-uid /proc gap under --strict-proc ({len(gaps)})")
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
    if args.apply:
        with _Lock() as got:
            if not got:
                print("another sweep holds the lock — nothing done (rc 0, never a wait)")
                return RC_OK
            print(REFUSAL_SET)
            print(render(rows, gaps=gaps, allowed=_allowed_classes(args)))
            apply_rows(rows, _allowed_classes(args), proc_root=_proc_root())
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
    return RC_OK


# ── mode 3: --worktrees ─────────────────────────────────────────────────────────────────────────
def _git(repo: Path, *args: str, timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def _worktree_registrations(repo: Path) -> list[dict]:
    """`git worktree list --porcelain` → one dict per registration; the FIRST is the main checkout."""
    rc, out = _git(repo, "worktree", "list", "--porcelain")
    if rc != 0:
        return []
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


def _merged_from(repo: Path, target: str, branch: str) -> bool:
    """Was `branch` squash-merged into `target`? Read the `Merged-From` trailer.

    The trailer is a COMMA LIST of `branch (free-text description)` entries, so each item is
    `.strip()`ped (without it every item after the first keeps its leading space and matches
    nothing), the trailing ` (…)` description is removed, and the comparison is WHOLE-STRING — a
    substring test would let one branch's description word mark a different branch merged.
    `git log --format=` also emits a BLANK line between commits, so empties are skipped.
    """
    rc, out = _git(repo, "log", "--format=%(trailers:key=Merged-From,valueonly)", target)
    if rc != 0:
        return False
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        for item in line.split(","):
            name = item.strip()
            if name.endswith(")") and " (" in name:
                name = name[: name.rindex(" (")].strip()
            if name and name == branch:
                return True
    return False


def _ignored_data(repo_wt: Path) -> list[str]:
    """Ignored paths that are DATA, not rebuildable cache.

    `git worktree remove` deletes ignored files silently even WITHOUT `--force` (measured), so a
    worktree holding `.tmp/subagents/pg_outbox.jsonl` — which cleanup-automation § D marks
    NEVER-delete — would be removed while `git status --porcelain` reported it clean.
    """
    rc, out = _git(repo_wt, "status", "--porcelain", "--ignored=matching")
    if rc != 0:
        return []
    hits: list[str] = []
    for line in out.splitlines():
        if not line.startswith("!!"):
            continue
        path = line[2:].strip()
        if not any(path.startswith(c) or f"/{c}" in path for c in CACHE_ALLOWLIST):
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
    if registered < session_start:
        return Row(
            p,
            "worktree",
            "wt-foreign",
            "registered before this session started — not this run's to remove",
            f"registered {_human(now - registered)} ago",
        )

    is_harness = (
        ".claude/worktrees/" in p
        or (repo / ".git" / "worktrees" / path.name / "CLAUDE_BASE").exists()
    )
    verdict, reason, evidence = _worktree_chain(
        path, entry, main_path, target, branch, stashed, detached_stash, held
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
    rc, status = _git(path, "status", "--porcelain")
    if rc == 0 and status.strip():
        all_names = [ln[3:] for ln in status.splitlines()]
        shown = ", ".join(all_names[:5]) + ("…" if len(all_names) > 5 else "")
        return "wt-dirty", f"uncommitted work ({len(all_names)}): {shown}", ""
    if branch in stashed:
        return (
            "wt-dirty",
            "a stash names this branch — invisible to status and to worktree list",
            "",
        )
    if detached_stash:
        return "wt-dirty", "a `(no branch)` stash exists and cannot be attributed to a branch", ""
    ignored = _ignored_data(path)
    if ignored:
        shown = ", ".join(ignored[:5]) + ("…" if len(ignored) > 5 else "")
        return (
            "wt-ignored-data",
            f"ignored DATA git would delete anyway ({len(ignored)}): {shown}",
            "",
        )
    rc_anc, _ = _git(main_path, "merge-base", "--is-ancestor", branch, target)
    if rc_anc != 0 and not _merged_from(main_path, target, branch):
        rc_n, ahead = _git(main_path, "rev-list", "--count", f"{target}..{branch}")
        n = ahead.strip() if rc_n == 0 else "?"
        return "wt-unmerged", f"not merged into {target} (ahead {n})", ""
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


def apply_worktrees(repo: Path, rows: list[Row], allowed: set[str], out=sys.stdout) -> int:
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
        rc, msg = _git(repo, "worktree", "remove", r.path)
        if rc != 0:
            print(
                f"REFUSED {r.path} — git: {msg.strip().splitlines()[0] if msg.strip() else rc}",
                file=out,
            )
            continue
        removed += 1
        print(f"REMOVED {r.path} ({r.cls}, {r.reason})", file=out)
        branch = branches.get(r.path, "")
        if not branch:
            print("  branch kept — git registered no branch for it", file=out)
            continue
        rc_b, msg_b = _git(repo, "branch", "-d", branch)
        if rc_b != 0 and msg_b.strip():
            # A SQUASH-merged branch is not an ancestor, so `-d` refuses it. The worktree is gone
            # and the branch survives with git's own words — the conservative end state, never -D.
            print(f"  branch {branch} kept — git: {msg_b.strip().splitlines()[0]}", file=out)
    if removed:
        # Only after we actually removed something, and said so: `git worktree prune` is REPO-WIDE
        # and drops other sessions' stale registrations too, so running it unconditionally made a
        # zero-candidate apply mutate the repo silently (round-3, sub-threshold).
        print("PRUNED stale registrations (repo-wide `git worktree prune`)", file=out)
        _git(repo, "worktree", "prune")
    return removed


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
    elif sid and SID_RE.match(sid):
        by_sid, _ = read_sessions(sessions_dirs())
        start = session_start_epoch(by_sid.get(sid, []))
    rows = classify_worktrees(repo, _now(), _proc_root(), start, args.include_harness)
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
        if not sid or not SID_RE.match(sid):
            return RC_OK
        cwd = str(payload.get("cwd") or os.getcwd())
        if (
            os.environ.get("CLAUDE_MESH_HEADLESS") == "1"
            or os.environ.get("CLAUDE_MESH_AUTONOMOUS") == "1"
            or not (cwd == "/opt" or cwd.startswith("/opt/"))
        ):
            return RC_OK
        root = _scratch_root()
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
            root, sid, _now(), older, budget=budget, with_size=False, cwd=cwd
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
            "never touches: /opt files, transcripts, ~/.claude/state (beyond its own lock), "
            "another live session's scratch, or tasks/"
        )
    except Exception as exc:  # noqa: BLE001 — fail-open by contract, but never SILENT
        print(f"scratch_sweep --hook: skipped — {type(exc).__name__}: {exc}", file=sys.stderr)
    return RC_OK


if __name__ == "__main__":
    sys.exit(main())
