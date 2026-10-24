#!/usr/bin/env python3
# AFTER-EDIT: docs/development/plans/2026-09-06-plan-1-session-history-retention.md | docs/workstation/session-history-retention.md | docs/CONFIGURATION.md
"""prune_transcripts — Phase C.2/C.3 of the session-history retention plan (D-736).

THE ONLY DELETER of MAIN Claude transcripts under `~/.claude/projects`. `--dry-run` is the default
and prints a table; `--apply` deletes. It runs after the archiver, from the same systemd unit, as a
second `ExecStart=-` line (the `-` keeps a refusal from failing the unit; see the unit file).

THE INVARIANT (C.2.1) — a MAIN transcript is deleted only when EVERY clause holds, and every clause
FAILS CLOSED (a doubt is a refusal, printed with its reason):
  r1  its `mtime` is older than PRUNE_AFTER_DAYS (default 3);
  r2  it is NOT OPEN: no `~/.claude/sessions/<pid>.json` entry carries its session id with a live
      process — `/proc/<pid>` exists AND the entry's `procStart` equals field 22 of `/proc/<pid>/stat`,
      both as integers; a missing or non-numeric `procStart` beside a live pid COUNTS AS ALIVE (a
      recycled pid does not) — and no `agent-identity.jsonl` row carries its session id with
      `pid`+`pid_start` alive the same way;
  r3  it is not the newest session of its project slug, and not the newest of its agent (the `agent`
      tag, C.1.1) — a long-idle project keeps its resume point, each hub agent its latest chain link;
  r8  session-recall holds it: an `index_state` row whose `inode` is the file's `st_ino` AND whose
      `size` is the file's current size, read BY INODE through SESSION_RECALL_RO_DSN (session-recall
      keeps one row per inode and prefers the worktree name). No DSN, no connection, no row, or a
      size mismatch ⇒ `not-indexed`;
  r4  its CURRENT sha256 (hashed now, never trusted from archive time) equals the latest manifest
      row's for (project_slug, session_id);
  r5  the `.zst` under the ROW's project_slug exists, decompresses, and the sha256 of its CONTENT
      equals the row's (`zstd -t` proves the frame, not the bytes);
  r6  the bucket lists that object with the SAME size and SHA1 as the local `.zst` (one
      `rclone lsf --format psh --hash SHA1` per slug; a listing that fails refuses the whole slug);
  r7  every name of the inode — found NOW by (st_dev, st_ino) over the whole tree, never from the
      manifest's `also_slugs` — passes r1–r3 and has its own manifest row; one name failing ⇒ the
      inode is skipped, and names with DIFFERENT session ids (`names-differ`) are refused outright.
      The names are unlinked in one pass after ONE ledger row naming them all.
  Then THE LAST LOOK, immediately before the unlink: a re-`stat` (size and mtime_ns unchanged since
  the hash) and r2 again; a change ⇒ `changed-under-hash`.

THE LEDGER BEFORE THE UNLINK: a deletion appends its row to `~/.claude/archive/pruned.jsonl`
(project_slug, session_id, sha256, bytes, paths, agent, object, object_bytes, object_sha1,
pruned_at) and fsyncs it BEFORE any unlink — a crash between them leaves a row with the file still
present, never a vanished file without a row. The file sits in ARCHIVE_ROOT, so the archiver's
`ship()` uploads it nightly: the restore list is off-box too. `--restore <session_id>` (MAIN rows
only) and `--restore agent-<id>` (subagent-tier sidechain rows only; two distinct paths for one id
refuse, listing both) are its consumers; `--verify-ledger` its integrity check.

THE CAP (C.2.2): every run orders the deletable inodes OLDEST first and takes at most
PRUNE_MAX_PER_RUN (default 200; `--max M` on a hand run) as THIS RUN's set; the rest are `deferred`.
A hand `--apply` needs `--expect N` equal to this run's count — a mismatch deletes nothing and
prints both numbers. `--apply --nightly` (the unit) needs no `--expect`.
  COBRA, stated honestly (D-253): `--expect` is an ECHO, not a proof — this run's count is
  `min(cap, deletable)`, 200 on every night the backlog exceeds the cap, so it can be typed without
  reading anything; it guards a stale or mistyped command (the count moved since the table was
  read), nothing more. The brakes that hold are the cap, the summary row and the ledger row per
  deletion; the proof Gate C demands is the pasted dry-run table.

THE SUBAGENT TIER (C.3, `--tier subagents`, included by `--nightly`): `<slug>/<sid>/subagents/
agent-*.jsonl` older than the window whose parent session is not OPEN and which is not in flight
(the stop-decider's rule: a sidechain older than SUBAGENT_STALE_S is never in flight; a younger one
is in flight while its tail ends mid-exchange), plus `~/.claude/tasks/` and `~/.claude/shell-snapshots/`
entries older than the window; one ledger row each, no cap. Since D-1182 the archiver ships the
sidechains too, so a sidechain is deleted only when the archive VOUCHES for it — a row for (slug, rel)
in `manifest-subagents.jsonl` (`not-archived`), then the same r4–r6 as MAIN (`_vouch`: current sha256,
the `.zst`'s decompressed bytes, the bucket's size and SHA1 for `<slug>/<rel>.zst`), then the last look
(OPEN re-read, re-stat) before its fsynced row and unlink; its row carries sha256 + object so
`--restore agent-<id>` can put it back. Tasks and shell snapshots are never archived — a cliff.

THE SUMMARY ROW: a dry-run or apply run appends one row to `~/.claude/archive/prune-log.jsonl`
(run_at, mode, tiers, scanned, deletable, this_run, deleted, deferred, refusals by reason,
over_threshold — every MAIN transcript larger than ROTATE_ADVISE_MB — and `error` with the traceback
when there was one) BEFORE exiting, whatever happened; `--status` prints the last row AND the last
APPLY row. `--restore`, `--verify-ledger` and `--status` write no row.

EXIT CODES: 0 ran (0 or more deletions) · 3 refused (`--expect` mismatch, lock held, no manifest,
`--verify-ledger` MISSING, `--restore` with a survivor of another sha256 or a failed fetch) ·
1 error (a dry-run/apply run writes its summary row first) · 2 usage.

Env (12-Factor III) — read from the process environment, else the `SESSION_RECALL_RO_DSN`,
`PRUNE_*` and `ROTATE_ADVISE_MB` lines of SESSION_ARCHIVE_ENV_FILE (default /opt/fabrik/.env), the
archiver's `_env_value` grammar; nothing else in that file is read:
  PRUNE_AFTER_DAYS        the window, days (default 3)
  PRUNE_MAX_PER_RUN       the cap on MAIN deletions per run (default 200)
  SESSION_RECALL_RO_DSN   session-recall's read-only role; absent ⇒ every MAIN file is `not-indexed`
  ROTATE_ADVISE_MB        the over-threshold report's size (default 200)
  CLAUDE_PROJECTS_DIR · ARCHIVE_ROOT · CLAUDE_SESSIONS_DIR · AGENT_IDENTITY_FILE — the archiver's
  CLAUDE_TASKS_DIR (~/.claude/tasks) · CLAUDE_SHELL_SNAPSHOTS_DIR (~/.claude/shell-snapshots)
The DSN is never printed. The B2 key reaches rclone through the archiver's own child env only.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "archive_transcripts", _HERE / "archive_transcripts.py"
)
at = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(at)

LEDGER_NAME = "pruned.jsonl"
LOG_NAME = "prune-log.jsonl"
DEFAULT_AFTER_DAYS = 3.0
DEFAULT_MAX_PER_RUN = 200
DEFAULT_ROTATE_ADVISE_MB = 200
SUBAGENT_STALE_S = (
    int(os.environ.get("CLAUDE_SOUND_SUBAGENT_STALE_MIN", "30")) * 60
)  # the decider's
TIERS = ("main", "subagents")
_ENV_LINE = re.compile(
    r"^(?:export\s+)?(SESSION_RECALL_RO_DSN|PRUNE_[A-Z0-9_]+|ROTATE_ADVISE_MB)=(.*)$"
)
_PROC_ROOT = Path("/proc")  # the test seam for r2: a fake proc tree with `<pid>/stat` files
_SID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_REFUSED = 0, 1, 2, 3


class RefusalError(RuntimeError):
    """A clean stop with a reason: printed to stderr, exit 3, nothing written."""


# ── settings ────────────────────────────────────────────────────────────────────────────────


def _setting(name: str, default: str = "") -> str:
    """The process environment when non-empty, else the LAST matching line of the env file (as
    dotenv reads it), else the default. Only the three prefixes `_ENV_LINE` names are read."""
    if os.environ.get(name):
        return os.environ[name]
    path = at._env_path("SESSION_ARCHIVE_ENV_FILE", "/opt/fabrik/.env")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return default
    found = ""
    for line in lines:
        m = _ENV_LINE.match(line.rstrip("\r").strip())
        if m and m.group(1) == name:
            found = at._env_value(m.group(2))
    return found or default


def _number(name: str, default: float, *, floor: float = 0.0) -> float:
    raw = _setting(name, "")
    try:
        value = float(raw) if raw else default
    except ValueError as exc:
        raise RefusalError(f"{name} must be a number, got {raw!r}") from exc
    return max(floor, value)


# ── r2: liveness, fail-closed ───────────────────────────────────────────────────────────────


def _proc_start(pid: int) -> int | None:
    """Field 22 of `<proc>/<pid>/stat`, or None when the pid has no stat file (dead)."""
    try:
        raw = (_PROC_ROOT / str(pid) / "stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        return int(raw[raw.rindex(")") + 1 :].split()[19])
    except (ValueError, IndexError):
        return -1  # a stat we cannot parse is a live pid of unknown start: alive (fail-closed)


def _alive(pid: int | None, start: int | None) -> bool:
    """A live pid with the recorded start; an unknown start beside a live pid counts as alive;
    a recycled pid (another start) and a dead pid do not."""
    if pid is None:
        return True  # an entry we cannot test is an OPEN session (fail-closed)
    actual = _proc_start(pid)
    if actual is None:
        return False
    if start is None or actual == -1:
        return True
    return actual == start


def open_sessions(sessions_dir: Path, identity: Path) -> set[str]:
    """Session ids with a live process: the peer registry (primary) and the identity rows (belt).
    Both legs read `_alive` the same way — an entry or row whose pid cannot be tested is OPEN."""
    out: set[str] = set()
    try:
        entries = sorted(sessions_dir.glob("*.json"))
    except OSError:
        entries = []
    for entry in entries:
        e = at._json_doc(entry)
        if not e:
            continue
        sid = str(e.get("sessionId") or "")
        if sid and _alive(at._as_int(e.get("pid")), at._as_int(e.get("procStart"))):
            out.add(sid)
    for r in at._json_rows(identity):
        sid = str(r.get("session_id") or "")
        # the same fail-closed `_alive`: a row without a pid is an untestable binding, so OPEN
        # (review 2026-10-11, pruner-S1 — the registry leg already read it that way)
        if sid and _alive(at._as_int(r.get("pid")), at._as_int(r.get("pid_start"))):
            out.add(sid)
    return out


# ── r8: session-recall's index_state, by inode ──────────────────────────────────────────────


def _fetch_index_rows(dsn: str) -> list[tuple[int, int]]:
    """`(inode, size)` for every index_state row — the one query, through the read-only role.
    The seam tests replace; the DSN is never printed."""
    import psycopg2  # declared in pyproject.toml (the one deps edit C.2 authorises)

    conn = psycopg2.connect(dsn, connect_timeout=10)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT inode, size FROM index_state")
            return [(int(i), int(s)) for i, s in cur.fetchall()]
    finally:
        conn.close()


def index_state(dsn: str) -> dict[int, set[int]] | None:
    """inode → the sizes session-recall has indexed to the end; None when the index cannot be
    read (no DSN, no connection, no table) — which refuses every file as `not-indexed`."""
    if not dsn:
        return None
    try:
        rows = _fetch_index_rows(dsn)
    except Exception as exc:  # noqa: BLE001 — any failure to read the index is a refusal, not a crash
        print(
            f"prune_transcripts: session-recall index unreadable ({type(exc).__name__})",
            file=sys.stderr,
        )
        return None
    out: dict[int, set[int]] = {}
    for inode, size in rows:
        out.setdefault(inode, set()).add(size)
    return out


# ── r5/r6: the object and the bucket ────────────────────────────────────────────────────────


def _sha1(path: Path) -> str:
    # B2's listing hash — an identity check against the bucket's own SHA1, never a signature
    h = hashlib.sha1(usedforsecurity=False)  # noqa: S324
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _zst_content_sha256(zst: Path) -> str | None:
    """sha256 of the DECOMPRESSED bytes, streamed; None when zstd refuses the frame."""
    try:
        proc = subprocess.Popen(
            ["zstd", "-dc", "-q", str(zst)], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )  # noqa: S603
    except OSError:
        return None
    h = hashlib.sha256()
    assert proc.stdout is not None
    for chunk in iter(lambda: proc.stdout.read(1 << 20), b""):
        h.update(chunk)
    proc.stdout.close()
    proc.wait(timeout=3600)
    return h.hexdigest() if proc.returncode == 0 else None


class RemoteListing:
    """One `rclone lsf` per slug, cached; a failed listing refuses every object of that slug."""

    def __init__(self) -> None:
        self._env: dict[str, str] | None = None
        self._by_slug: dict[str, dict[str, tuple[int, str]] | None] = {}

    def env(self) -> dict[str, str]:
        if self._env is None:
            at._probe_binaries(("rclone",))
            self._env = at._child_env(*at._credentials())
        return self._env

    def objects(self, slug: str) -> dict[str, tuple[int, str]] | None:
        if slug not in self._by_slug:
            try:
                # -R: a subagent object sits below the slug (`<sid>/subagents/…`, D-1182) and a MAIN
                # object stays a bare top-level name; --fast-list: one recursive B2 list per slug,
                # not one per directory
                done = at._rclone(
                    "lsf",
                    "-R",
                    "--fast-list",
                    "--files-only",
                    "--format",
                    "psh",
                    "--hash",
                    "SHA1",
                    "--separator",
                    ";",
                    f"{at._remote_base()}/{slug}/",
                    env=self.env(),
                )
                listed: dict[str, tuple[int, str]] = {}
                for line in done.stdout.splitlines():
                    parts = line.rstrip("\n").split(";")
                    if len(parts) == 3 and parts[1].isdigit():
                        listed[parts[0]] = (int(parts[1]), parts[2].strip().lower())
                self._by_slug[slug] = listed
            except (at.ArchiveError, ValueError, OSError) as exc:
                print(
                    f"prune_transcripts: listing {slug} failed — nothing in it is deleted ({exc})",
                    file=sys.stderr,
                )
                self._by_slug[slug] = None
        return self._by_slug[slug]


@dataclass
class Proof:
    """r4–r6's verdict on one file: `reason` None means the archive vouches for its current bytes."""

    reason: str | None
    sha256: str = ""
    object_bytes: int = 0
    object_sha1: str = ""


def _vouch(
    path: Path, row: dict, zst: Path, slug: str, key: str, listing: RemoteListing
) -> Proof:
    """r4–r6 for one file of EITHER tier against its manifest row, every doubt a refusal: r4 the file's
    CURRENT sha256 equals the row's; r5 the `.zst` exists and its decompressed bytes hash to it; r6 the
    bucket lists `key` under `slug` with the local `.zst`'s size and SHA1."""
    try:
        sha = at._sha256(path)
    except OSError:
        return Proof("changed-under-hash")
    if sha != row.get("sha256"):
        return Proof("sha-mismatch", sha)
    if not zst.is_file():
        return Proof("zst-missing", sha)
    content = _zst_content_sha256(zst)
    if content is None:
        return Proof("zst-corrupt", sha)
    if content != sha:
        return Proof("zst-bytes-differ", sha)
    try:
        size, sha1 = zst.stat().st_size, _sha1(zst)
    except OSError:  # the object went between the decompress and here: refuse this file, not the night
        return Proof("zst-missing", sha)
    objects = listing.objects(slug)
    if objects is None:
        return Proof("listing-failed", sha, size, sha1)
    remote = objects.get(key)
    if remote is None:
        return Proof("remote-missing", sha, size, sha1)
    if remote != (size, sha1):
        return Proof("remote-differs", sha, size, sha1)
    return Proof(None, sha, size, sha1)


# ── the MAIN tier ───────────────────────────────────────────────────────────────────────────


@dataclass
class Candidate:
    session_id: str
    names: list[Path]
    mtime_ns: int
    size: int
    inode: int
    reason: str | None = None
    row: dict | None = None
    sha256: str = ""
    agent: str | None = None
    zst: Path | None = None
    object_key: str = ""
    object_bytes: int = 0
    object_sha1: str = ""

    @property
    def mtime(self) -> float:
        return self.mtime_ns / 1e9


@dataclass
class World:
    projects: Path
    archive_root: Path
    sessions_dir: Path
    identity: Path
    tasks_dir: Path
    snapshots_dir: Path
    after_days: float
    cap: int
    advise_mb: int
    dsn: str
    now: float = field(default_factory=time.time)


def _world(cap_override: int | None) -> World:
    return World(
        projects=at._env_path("CLAUDE_PROJECTS_DIR", "~/.claude/projects"),
        archive_root=at._env_path("ARCHIVE_ROOT", "~/.claude/archive"),
        sessions_dir=at._env_path("CLAUDE_SESSIONS_DIR", "~/.claude/sessions"),
        identity=at._env_path("AGENT_IDENTITY_FILE", "~/.claude/state/agent-identity.jsonl"),
        tasks_dir=at._env_path("CLAUDE_TASKS_DIR", "~/.claude/tasks"),
        snapshots_dir=at._env_path("CLAUDE_SHELL_SNAPSHOTS_DIR", "~/.claude/shell-snapshots"),
        after_days=_number("PRUNE_AFTER_DAYS", DEFAULT_AFTER_DAYS),
        cap=cap_override
        if cap_override is not None
        else int(_number("PRUNE_MAX_PER_RUN", DEFAULT_MAX_PER_RUN, floor=1)),
        advise_mb=int(_number("ROTATE_ADVISE_MB", DEFAULT_ROTATE_ADVISE_MB, floor=1)),
        dsn=_setting("SESSION_RECALL_RO_DSN", ""),
    )


def _main_files(projects: Path) -> list[tuple[Path, os.stat_result]]:
    out = []
    for p in sorted(projects.glob("*/*.jsonl")):
        if "/subagents/" in str(p):
            continue
        try:
            st = p.stat()
        except FileNotFoundError:
            continue  # vanished between the glob and the stat
        if p.is_file():
            out.append((p, st))
    return out


def _group(files: list[tuple[Path, os.stat_result]]) -> list[Candidate]:
    groups: dict[tuple[int, int], Candidate] = {}
    for p, st in files:
        key = (st.st_dev, st.st_ino)
        if key in groups:
            groups[key].names.append(p)
        else:
            groups[key] = Candidate(p.stem, [p], st.st_mtime_ns, st.st_size, st.st_ino)
    return list(groups.values())


def _newest(
    files: list[tuple[Path, os.stat_result]], agents: dict[str, str], latest: dict
) -> tuple[dict[str, str], dict[str, str]]:
    """(slug → newest session id, agent → newest session id) over EVERY MAIN file, any age."""
    by_slug: dict[str, tuple[int, str]] = {}
    by_agent: dict[str, tuple[int, str]] = {}
    for p, st in files:
        slug, sid = p.parent.name, p.stem
        if slug not in by_slug or st.st_mtime_ns > by_slug[slug][0]:
            by_slug[slug] = (st.st_mtime_ns, sid)
        row = latest.get((slug, sid)) or {}
        agent = agents.get(sid) or row.get("agent")
        if (
            isinstance(agent, str)
            and agent
            and (agent not in by_agent or st.st_mtime_ns > by_agent[agent][0])
        ):
            by_agent[agent] = (st.st_mtime_ns, sid)
    return {s: sid for s, (_, sid) in by_slug.items()}, {a: sid for a, (_, sid) in by_agent.items()}


def evaluate_main(
    w: World, listing: RemoteListing | None = None
) -> tuple[list[Candidate], dict[str, int], list[str]]:
    """Every MAIN inode with its verdict — `reason` None means deletable. Order: r1–r3, r8 (cheap)
    → r4 (the hash) → r5–r6. `listing` is created lazily so a tree the cheap rules refuse whole
    never needs credentials."""
    files = _main_files(w.projects)
    over = [str(p) for p, st in files if st.st_size > w.advise_mb * 1024 * 1024]
    manifest = w.archive_root / at.MANIFEST_NAME
    latest = at._latest_rows(manifest)
    agents = at.agent_map(w.identity, w.sessions_dir)
    newest_slug, newest_agent = _newest(files, agents, latest)
    opened = open_sessions(w.sessions_dir, w.identity)
    cutoff_ns = int((w.now - w.after_days * 86400) * 1e9)
    index: dict[int, set[int]] | None | bool = False  # False = not fetched yet
    cands = _group(files)
    for c in cands:
        c.agent = agents.get(c.session_id) or next(
            (
                r.get("agent")
                for r in (latest.get((n.parent.name, c.session_id)) for n in c.names)
                if r and r.get("agent")
            ),
            None,
        )
        if len({n.stem for n in c.names}) > 1:
            # a hand-made link under another session id: every per-name lookup (r3, r4, r7) would
            # key on ONE stem, so the inode is refused outright (review 2026-10-11, pruner-S2)
            c.reason = "names-differ"
        elif c.mtime_ns > cutoff_ns:
            c.reason = "in-window"
        elif c.session_id in opened:
            c.reason = "open"
        elif any(newest_slug.get(n.parent.name) == c.session_id for n in c.names):
            c.reason = "newest-of-slug"
        elif c.agent and newest_agent.get(c.agent) == c.session_id:
            c.reason = "newest-of-agent"
        else:
            if index is False:
                index = index_state(w.dsn)
            if not index or c.size not in index.get(c.inode, ()):
                c.reason = "not-indexed"
    # r4–r6 only for what survived the cheap rules
    for c in cands:
        if c.reason:
            continue
        rows = [latest.get((n.parent.name, c.session_id)) for n in c.names]
        if any(r is None for r in rows):
            c.reason = "not-archived"  # r7: one name without a row ⇒ the inode is skipped
            continue
        c.row = rows[0]
        if any(r.get("sha256") != c.row.get("sha256") for r in rows):
            c.reason = "sha-mismatch"
            continue
        slug = str(c.row.get("project_slug") or "")
        c.zst = w.archive_root / slug / f"{c.session_id}.jsonl.zst"
        c.object_key = f"{slug}/{c.session_id}.jsonl.zst"
        listing = listing or RemoteListing()  # its credentials are read on the first listing only
        p = _vouch(c.names[0], c.row, c.zst, slug, f"{c.session_id}.jsonl.zst", listing)
        c.reason, c.sha256, c.object_bytes, c.object_sha1 = (
            p.reason,
            p.sha256,
            p.object_bytes,
            p.object_sha1,
        )
    refusals: dict[str, int] = {}
    for c in cands:
        if c.reason:
            refusals[c.reason] = refusals.get(c.reason, 0) + 1
    return cands, refusals, over


# ── the subagent tier (C.3) ─────────────────────────────────────────────────────────────────


def _tail_lines(path: Path, nbytes: int) -> list[str]:
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - nbytes))
            return fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def subagent_running(sidechain: Path) -> bool:
    """`claude-stop-decider.subagent_running`, verbatim in rule: a running sidechain ends mid-exchange;
    a finished one ends with an assistant entry whose stop_reason is `end_turn`."""
    lines = _tail_lines(sidechain, 64 * 1024)
    for i, raw in enumerate(reversed(lines)):
        if not raw.strip():
            continue
        try:
            e = json.loads(raw)
        except ValueError:
            return i == 0
        if not isinstance(e, dict):
            continue
        msg = e.get("message")
        msg = msg if isinstance(msg, dict) else {}
        if msg.get("role") == "assistant":
            return msg.get("stop_reason") != "end_turn"
        if msg.get("role") == "user":
            return True
    return False


@dataclass
class Scrap:
    kind: str  # subagent · task · shell-snapshot
    path: Path
    mtime: float
    size: int
    session_id: str = ""
    project_slug: str = ""
    reason: str | None = None
    mtime_ns: int = 0  # a sidechain's: the last look compares it, with the size, before the unlink
    proof: Proof | None = None  # a sidechain's vouch (D-1182); None for a task or a shell snapshot
    object_key: str = ""


def _newest_mtime(path: Path) -> float:
    newest = path.lstat().st_mtime
    if path.is_dir() and not path.is_symlink():
        for sub in path.rglob("*"):
            with contextlib.suppress(OSError):
                newest = max(newest, sub.lstat().st_mtime)
    return newest


def _tree_size(path: Path) -> int:
    if path.is_dir() and not path.is_symlink():
        return sum(f.lstat().st_size for f in path.rglob("*") if f.is_file())
    return path.lstat().st_size


def evaluate_subagents(
    w: World, listing: RemoteListing | None = None
) -> tuple[list[Scrap], dict[str, int]]:
    """Sidechains past the cheap rules are deleted only when the archive vouches for them (D-1182):
    a row in `manifest-subagents.jsonl` for (slug, rel) — else `not-archived` — then `_vouch`'s r4–r6
    against the object `<slug>/<rel>.zst`. Tasks and shell snapshots stay a cliff (never archived)."""
    opened = open_sessions(w.sessions_dir, w.identity)
    cutoff = w.now - w.after_days * 86400
    latest = at._latest_subagent_rows(w.archive_root / at.SUBAGENT_MANIFEST_NAME)
    out: list[Scrap] = []
    for f in sorted(w.projects.glob("*/*/subagents/agent-*.jsonl")):
        try:
            st = f.stat()
        except FileNotFoundError:
            continue
        s = Scrap(
            "subagent",
            f,
            st.st_mtime,
            st.st_size,
            f.parent.parent.name,
            f.parent.parent.parent.name,
            mtime_ns=st.st_mtime_ns,
        )
        if st.st_mtime > cutoff:
            s.reason = "in-window"
        elif s.session_id in opened:
            s.reason = "parent-open"
        elif (w.now - st.st_mtime) <= SUBAGENT_STALE_S and subagent_running(f):
            s.reason = "in-flight"
        else:
            rel = f.relative_to(w.projects / s.project_slug).as_posix()
            row = latest.get((s.project_slug, rel))
            if row is None:
                s.reason = "not-archived"
            else:
                listing = listing or RemoteListing()
                s.object_key = f"{s.project_slug}/{rel}.zst"
                zst = w.archive_root / s.object_key
                s.proof = _vouch(f, row, zst, s.project_slug, f"{rel}.zst", listing)
                s.reason = s.proof.reason
        out.append(s)
    for kind, root in (("task", w.tasks_dir), ("shell-snapshot", w.snapshots_dir)):
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            try:
                mtime = _newest_mtime(entry)
                s = Scrap(kind, entry, mtime, _tree_size(entry))
            except OSError:
                continue
            if mtime > cutoff:
                s.reason = "in-window"
            out.append(s)
    refusals: dict[str, int] = {}
    for s in out:
        if s.reason:
            refusals[s.reason] = refusals.get(s.reason, 0) + 1
    return out, refusals


# ── the ledger and the summary row ──────────────────────────────────────────────────────────


def _append_fsync(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _now_iso(ts: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts if ts is not None else time.time()))


def _ledger_rows(archive_root: Path) -> list[dict]:
    return at._json_rows(archive_root / LEDGER_NAME)


# ── the run (dry-run / apply) ───────────────────────────────────────────────────────────────


def _fmt_refusals(refusals: dict[str, int]) -> str:
    return " · ".join(f"{k} {v}" for k, v in sorted(refusals.items())) or "none"


def prune(
    w: World,
    *,
    apply: bool,
    nightly: bool,
    expect: int | None,
    tiers: tuple[str, ...],
    summary: dict,
) -> int:
    mode = "apply" if apply else "dry-run"
    summary.update(mode=mode, tiers=list(tiers))
    run_main: list[Candidate] = []
    run_scraps: list[Scrap] = []
    deferred = 0
    listing = RemoteListing()  # one listing per slug for both tiers; credentials on first use only
    if "main" in tiers:
        cands, refusals, over = evaluate_main(w, listing)
        deletable = sorted((c for c in cands if c.reason is None), key=lambda c: c.mtime_ns)
        run_main, deferred = deletable[: w.cap], max(0, len(deletable) - w.cap)
        summary.update(
            scanned=len(cands),
            deletable=len(deletable),
            this_run=len(run_main),
            deferred=deferred,
            refusals=refusals,
            over_threshold=over,
        )
        print(
            f"prune_transcripts ({mode}): MAIN tier — {len(cands)} transcript inode(s) scanned · "
            f"deletable {len(deletable)} · this run {len(run_main)} (cap {w.cap}) · deferred {deferred}"
        )
        print(f"  refusals: {_fmt_refusals(refusals)}")
        print(f"  over-threshold (> {w.advise_mb} MB): {len(over)} file(s)")
        for c in run_main:
            twins = f" (+{len(c.names) - 1} twin)" if len(c.names) > 1 else ""
            print(
                f"  {'delete' if apply else 'would delete'} {c.names[0]}{twins} agent={c.agent or '-'}"
            )
    if "subagents" in tiers:
        scraps, s_ref = evaluate_subagents(w, listing)
        run_scraps = [s for s in scraps if s.reason is None]
        summary.update(
            subagents_scanned=len(scraps),
            subagents_this_run=len(run_scraps),
            subagents_refusals=s_ref,
        )
        print(
            f"prune_transcripts ({mode}): SUBAGENT tier — {len(scraps)} entr(ies) scanned · "
            f"this run {len(run_scraps)} · refusals: {_fmt_refusals(s_ref)}"
        )
    this_run = len(run_main) + len(run_scraps)
    if not apply:
        return EXIT_OK
    if not nightly and expect != this_run:
        print(
            f"prune_transcripts: REFUSED — --expect {expect} but this run's count is {this_run} "
            f"(MAIN {len(run_main)} + subagents {len(run_scraps)}); nothing deleted",
            file=sys.stderr,
        )
        summary["deleted"] = 0
        return EXIT_REFUSED
    ledger = w.archive_root / LEDGER_NAME
    deleted = 0
    for c in run_main:
        # r2 again, right before THIS inode's unlink — a session resumed while an earlier
        # candidate was being deleted is caught here (review 2026-10-11, pruner-S3)
        opened = open_sessions(w.sessions_dir, w.identity)
        fresh = []
        for n in c.names:
            try:
                st = n.stat()
            except FileNotFoundError:
                st = None
            fresh.append(st)
        if (
            any(st is None or st.st_size != c.size or st.st_mtime_ns != c.mtime_ns for st in fresh)
            or c.session_id in opened
        ):
            summary.setdefault("refusals", {})
            summary["refusals"]["changed-under-hash"] = (
                summary["refusals"].get("changed-under-hash", 0) + 1
            )
            print(f"  skipped {c.names[0]}: changed-under-hash")
            continue
        _append_fsync(
            ledger,
            {
                "tier": "main",
                "project_slug": c.row.get("project_slug"),
                "session_id": c.session_id,
                "sha256": c.sha256,
                "bytes": c.size,
                "paths": [str(n) for n in c.names],
                "agent": c.agent,
                "object": c.object_key,
                "object_bytes": c.object_bytes,
                "object_sha1": c.object_sha1,
                "pruned_at": _now_iso(),
            },
        )
        for n in c.names:
            with contextlib.suppress(FileNotFoundError):
                n.unlink()
        deleted += 1
    deleted_main = deleted  # a MAIN inode skipped by its last look is in neither count
    for s in run_scraps:
        row = {
            "tier": "subagents",
            "kind": s.kind,
            "project_slug": s.project_slug,
            "session_id": s.session_id,
            "bytes": s.size,
            "paths": [str(s.path)],
            "pruned_at": _now_iso(),
        }
        if s.kind == "subagent":
            # the last look, in MAIN's order: OPEN re-read, then the re-stat, right before this unlink
            opened = open_sessions(w.sessions_dir, w.identity)
            try:
                st = s.path.stat()
            except FileNotFoundError:
                st = None
            if (
                s.proof is None  # never vouched: not deletable (fail-closed)
                or st is None
                or st.st_size != s.size
                or st.st_mtime_ns != s.mtime_ns
                or s.session_id in opened
            ):
                refs = summary.setdefault("subagents_refusals", {})
                refs["changed-under-hash"] = refs.get("changed-under-hash", 0) + 1
                print(f"  skipped {s.path}: changed-under-hash")
                continue
            row.update(
                sha256=s.proof.sha256,
                object=s.object_key,
                object_bytes=s.proof.object_bytes,
                object_sha1=s.proof.object_sha1,
            )
        _append_fsync(ledger, row)
        if s.path.is_dir() and not s.path.is_symlink():
            shutil.rmtree(s.path, ignore_errors=True)
        else:
            with contextlib.suppress(FileNotFoundError):
                s.path.unlink()
        deleted += 1
    summary["deleted"] = deleted
    print(
        f"prune_transcripts: deleted {deleted} (MAIN {deleted_main} inode(s), "
        f"subagent-tier {deleted - deleted_main}); deferred {deferred}; ledger {ledger}"
    )
    return EXIT_OK


# ── --restore ───────────────────────────────────────────────────────────────────────────────


def _restore_match(r: dict, ident: str) -> bool:
    """A session id selects MAIN rows only; an `agent-<id>` selects subagent-tier sidechain rows whose
    path's stem is that id (D-1182). The two never mix: a sidechain row carries its PARENT's session id,
    so a MAIN restore must not read it."""
    if ident.startswith("agent-"):
        paths = r.get("paths") or []
        return (
            r.get("tier") == "subagents"
            and r.get("kind") == "subagent"
            and bool(paths)
            and Path(str(paths[0])).stem == ident
        )
    return r.get("session_id") == ident and r.get("tier", "main") == "main"


def _restore_rows(w: World, session_id: str, slug: str | None) -> list[dict]:
    rows = [r for r in _ledger_rows(w.archive_root) if _restore_match(r, session_id)]
    if not rows:  # the bucket's copy of the restore list; unreachable ⇒ no rows, a refusal below
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / LEDGER_NAME
            try:
                at.fetch(LEDGER_NAME, str(local), None, at._child_env(*at._credentials()))
            except at.ArchiveError as exc:
                print(
                    f"prune_transcripts: the bucket's {LEDGER_NAME} was not read ({exc})",
                    file=sys.stderr,
                )
                return []
            rows = [r for r in at._json_rows(local) if _restore_match(r, session_id)]
    if slug:
        rows = [r for r in rows if r.get("project_slug") == slug]
    return rows


def restore(w: World, session_id: str, slug: str | None) -> int:
    if not _SID_RE.fullmatch(session_id):
        raise RefusalError(f"--restore: {session_id!r} is not a session id")
    try:
        at._probe_binaries(("zstd",))  # before any fetch: a restore cannot finish without it
    except at.ArchiveError as exc:
        raise RefusalError(f"--restore: {exc}") from exc
    rows = _restore_rows(w, session_id, slug)
    if not rows:
        raise RefusalError(
            f"--restore: no pruned.jsonl row for session {session_id}"
            + (f" under {slug}" if slug else "")
        )
    if session_id.startswith("agent-"):
        pruned_at = {str(r["paths"][0]): r.get("pruned_at") for r in rows}  # the newest per path
        if len(pruned_at) > 1:  # the same agent id pruned under two session dirs: never guess which
            listed = "; ".join(f"{p} (pruned_at {t})" for p, t in sorted(pruned_at.items()))
            raise RefusalError(
                f"--restore: {session_id} was pruned under {len(pruned_at)} paths — {listed}; "
                "nothing written"
            )
    row = rows[-1]
    paths = [Path(p) for p in row.get("paths") or []]
    want = str(row.get("sha256") or "")
    if not paths or not want:
        raise RefusalError(f"--restore: the row for {session_id} names no paths or no sha256")
    survivor: Path | None = None
    for p in paths:
        if p.exists():
            have = at._sha256(p)
            if have != want:
                raise RefusalError(
                    f"--restore: {p} exists with sha256 {have[:12]}… ≠ the row's {want[:12]}… — live history, "
                    "not a restore target; nothing written"
                )
            survivor = survivor or p
    missing = [p for p in paths if not p.exists()]
    if not missing:
        print(
            f"restore: every path of {session_id} is present with the row's sha256; nothing to do"
        )
        return EXIT_OK
    fetched = False
    if survivor is None:
        target = missing[0]
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
            zst = Path(tmp) / "object.jsonl.zst"
            try:
                at.fetch(
                    str(row.get("object") or f"{row.get('project_slug')}/{session_id}.jsonl.zst"),
                    str(zst),
                    None,
                    at._child_env(*at._credentials()),
                )
            except at.ArchiveError as exc:
                raise RefusalError(
                    f"--restore: --fetch failed — the object is absent from the bucket, B2's download host is "
                    f"unreachable from this network, or rclone itself failed (a revoked key); nothing written. "
                    f"--fetch said: {exc}"
                ) from exc
            plain = Path(tmp) / "object.jsonl"
            subprocess.run(
                ["zstd", "-dc", "-q", str(zst), "-o", str(plain)], check=True, capture_output=True
            )  # noqa: S603
            if at._sha256(plain) != want:
                raise RefusalError(
                    "--restore: the fetched object decompresses to sha256 ≠ the row's; nothing written"
                )
            fd = os.open(
                target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644
            )  # never overwrite a path
            with os.fdopen(fd, "wb") as out, plain.open("rb") as src:
                shutil.copyfileobj(src, out)
        survivor, fetched = target, True
        missing = missing[1:]
    for p in missing:
        p.parent.mkdir(parents=True, exist_ok=True)
        os.link(survivor, p)
    now = time.time()
    os.utime(
        survivor, (now, now)
    )  # a hard link inherits the old mtime; untouched, r1 would offer it again
    print(
        f"restore: {session_id} — {'fetched' if fetched else 'hard-linked to the surviving twin'}; "
        f"paths {[str(p) for p in paths]}; sha256 {want[:12]}… verified; mtime now"
    )
    return EXIT_OK


# ── --verify-ledger ─────────────────────────────────────────────────────────────────────────


def verify_ledger(w: World) -> int:
    """Every MAIN row, and every subagent-tier row that names an archived object (D-1182; a task, a
    shell snapshot and a pre-D-1182 sidechain row name none), listed in the bucket as recorded."""
    rows = [
        r
        for r in _ledger_rows(w.archive_root)
        if r.get("tier", "main") == "main" or (r.get("tier") == "subagents" and r.get("object"))
    ]
    if not rows:
        print("verify-ledger: no archived rows in pruned.jsonl")
        return EXIT_OK
    listing = RemoteListing()
    missing = 0
    for r in rows:
        slug, key = str(r.get("project_slug") or ""), str(r.get("object") or "")
        objects = listing.objects(slug)
        remote = objects.get(key.split("/", 1)[-1]) if objects else None
        ok = remote is not None and remote == (
            int(r.get("object_bytes") or -1),
            str(r.get("object_sha1") or ""),
        )
        print(
            f"{'OK     ' if ok else 'MISSING'} {key} bytes={r.get('object_bytes')} sha1={str(r.get('object_sha1') or '')[:12]}"
        )
        missing += 0 if ok else 1
    print(f"verify-ledger: {len(rows)} row(s), {missing} MISSING")
    return EXIT_REFUSED if missing else EXIT_OK


# ── --status ────────────────────────────────────────────────────────────────────────────────


def status(w: World) -> int:
    rows = at._json_rows(w.archive_root / LOG_NAME)
    if not rows:
        print("status: no prune-log.jsonl rows yet")
        return EXIT_OK
    last = rows[-1]
    last_apply = next((r for r in reversed(rows) if r.get("mode") == "apply"), None)
    print("last run:   " + json.dumps(last, sort_keys=True))
    print("last apply: " + (json.dumps(last_apply, sort_keys=True) if last_apply else "none yet"))
    return EXIT_OK


# ── main ────────────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="the default: print the table, delete nothing"
    )
    ap.add_argument(
        "--apply", action="store_true", help="delete this run's set (needs --expect N or --nightly)"
    )
    ap.add_argument(
        "--expect", type=int, help="with --apply: this run's count, as the dry-run printed it"
    )
    ap.add_argument(
        "--max", type=int, help="this run's size instead of PRUNE_MAX_PER_RUN (a hand run)"
    )
    ap.add_argument(
        "--nightly", action="store_true", help="the unit's mode: both tiers, the cap, no --expect"
    )
    ap.add_argument(
        "--tier",
        choices=[*TIERS, "all"],
        help="main (default), subagents, or all (--nightly's default)",
    )
    ap.add_argument(
        "--restore",
        metavar="SESSION_ID|agent-ID",
        help="put a pruned session back (C.2.5), or a pruned subagent transcript (agent-<id>, D-1182)",
    )
    ap.add_argument(
        "--slug", help="with --restore: the project slug when the id was pruned under several"
    )
    ap.add_argument(
        "--verify-ledger",
        action="store_true",
        help="every pruned.jsonl object listed in the bucket (C.2.6)",
    )
    ap.add_argument(
        "--status", action="store_true", help="the last summary row and the last APPLY row"
    )
    return ap


def run(argv: list[str] | None = None) -> int:
    ap = _parser()
    args = ap.parse_args(argv)
    verbs = [
        v
        for v, on in (
            ("--restore", args.restore),
            ("--verify-ledger", args.verify_ledger),
            ("--status", args.status),
        )
        if on
    ]
    if len(verbs) > 1 or (
        verbs
        and (
            args.apply
            or args.nightly
            or args.expect is not None
            or args.max is not None
            or args.tier
        )
    ):
        ap.error(f"{' '.join(verbs)} takes no other verb or flag")
    if args.apply and args.dry_run:
        ap.error("--apply and --dry-run exclude each other")
    if args.apply and not args.nightly and args.expect is None:
        ap.error("--apply needs --expect N (this run's count from the dry-run) or --nightly")
    if args.max is not None and args.max < 1:
        ap.error("--max must be at least 1")
    try:
        w = _world(args.max)
        if verbs:
            if args.restore:
                return restore(w, args.restore, args.slug)
            if args.verify_ledger:
                return verify_ledger(w)
            return status(w)
    except RefusalError as exc:
        print(f"prune_transcripts: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception as exc:  # noqa: BLE001 — the three read-only verbs: exit 1, no summary row
        print(f"prune_transcripts: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR
    tiers: tuple[str, ...] = (
        TIERS
        if (args.tier == "all" or (args.nightly and not args.tier))
        else ((args.tier,) if args.tier else ("main",))
    )
    summary: dict = {
        "run_at": _now_iso(),
        "mode": "apply" if args.apply else "dry-run",
        "tiers": list(tiers),
        "deleted": 0,
    }
    rc = EXIT_ERROR
    try:
        if not w.projects.is_dir():
            raise RefusalError(f"projects dir not found: {w.projects}")
        if "main" in tiers and not (w.archive_root / at.MANIFEST_NAME).is_file():
            raise RefusalError(
                f"no manifest at {w.archive_root / at.MANIFEST_NAME} — nothing is provably archived"
            )
        at._probe_binaries(("zstd",))
        with at._locked(w.archive_root) as held:
            if not held:
                raise RefusalError(
                    "the archive lock is held (the archiver or another pruner is running); nothing deleted"
                )
            rc = prune(
                w,
                apply=args.apply,
                nightly=args.nightly,
                expect=args.expect,
                tiers=tiers,
                summary=summary,
            )
    except RefusalError as exc:
        summary["refused"] = str(exc)
        print(f"prune_transcripts: REFUSED — {exc}", file=sys.stderr)
        rc = EXIT_REFUSED
    except BaseException as exc:  # noqa: BLE001 — the row is written before the exit, whatever happened
        summary["error"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        print(f"prune_transcripts: ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        rc = EXIT_ERROR
    finally:
        with contextlib.suppress(OSError):
            _append_fsync(w.archive_root / LOG_NAME, summary)
    return rc


if __name__ == "__main__":
    raise SystemExit(run())
