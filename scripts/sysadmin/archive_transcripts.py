#!/usr/bin/env python3
# AFTER-EDIT: docs/development/plans/2026-09-06-plan-1-session-history-retention.md | docs/superpowers/specs/2026-09-05-session-history-retention-design.md | docs/workstation/session-history-retention.md
"""archive_transcripts — Phase A of the session-history retention plan (revision 2026-10-05).

Compresses MAIN Claude transcripts to zstd, records them in a manifest, and ships the archive
straight to the Backblaze B2 bucket with rclone (D-565). Nothing lands on a VPS.

⚠️ THIS SCRIPT NEVER DELETES A TRANSCRIPT OR AN ARCHIVED OBJECT — locally or in the bucket (it
removes only its own temporary `.snapshot-*` copy). Pruning is Phase C, which
is DEFERRED (D-565). The `.bak` incident that started this work happened because a
"provably lossless" deletion was argued from a size comparison instead of from bytes.

⚠️ EVERY rclone CALL GOES THROUGH `_rclone`, AND ITS VERB IS AN ALLOW-LIST: copy, copyto,
lsf. Any other verb (sync, move, cleanup — which on B2 deletes old versions — purge, …) and
any option whose NAME is `--b2-hard-delete` or starts with `--delete` raises before a process
starts. A deny-list of spellings covers only the spellings someone thought of; an allow-list
at run time does not depend on how a future caller spells the call. Graded by
`tests/test_archive_transcripts.py` (A-B7).

THE REMOTE LIVES IN THE CHILD'S ENVIRONMENT ONLY — `RCLONE_CONFIG_SESSIONB2_*` — never in
argv (readable by every process via `ps`) and never in `rclone.conf`. Inherited `RCLONE_*`
variables are stripped first, so nothing like `RCLONE_B2_HARD_DELETE` can ride in.

THE MANIFEST KEY IS (project_slug, session_id, sha256). Only the LATEST row per
(project_slug, session_id) describes the object at `<slug>/<session-id>.jsonl.zst`; an
older row's bytes live on as a prior version in the bucket (it keeps all versions).
`archived_at` is the COMPRESSION time, not the upload time.

Hard links (D-467 links worktree transcripts into their repo's lane) are archived ONCE per
(st_dev, st_ino), under the first slug in sorted order; the others go in `also_slugs`.

THE `agent` KEY (Phase C.1, D-736): a row carries `"agent": "<name>"` when the session is bound to
a hub agent — the latest `agent-identity.jsonl` row for its session id (what `whoami_agent.py`
writes), else the REGISTRY JOIN: the `~/.claude/sessions/<pid>.json` entry carrying this session
id, joined on `pid`+`procStart` to an identity row's `pid`+`pid_start` (both as integers; the
registry stores `procStart` as a string). The join is what tags a window after `/clear`, which
mints a new session id but keeps the claude process. An unbound session's row has no `agent`
key. `--agent <name>` lists that agent's rows, newest first — "infra's history" is this list.

Env (12-Factor III):
  ARCHIVE_ROOT                local archive dir                       (default ~/.claude/archive)
  ARCHIVE_AFTER_DAYS          only files idle longer than this        (default 0: every MAIN
                              transcript, so a window open for days ships a daily snapshot)
  ARCHIVE_MAX_FILE_MB         per-file ceiling; larger files are REPORTED, never archived
  CLAUDE_PROJECTS_DIR         source tree                             (default ~/.claude/projects)
  SESSION_ARCHIVE_B2_BUCKET   the bucket                              (default wsl-ozgur)
  SESSION_ARCHIVE_B2_PREFIX   the path under the bucket               (default archive)
  SESSION_ARCHIVE_B2_KEY_ID / SESSION_ARCHIVE_B2_APPLICATION_KEY      the application key
  SESSION_ARCHIVE_ENV_FILE    where the two key variables are read from when the process
                              environment lacks them; only `SESSION_ARCHIVE_*` lines are read
                              (default /opt/fabrik/.env)
  AGENT_IDENTITY_FILE         the agent↔session binding store, read-only here
                              (default ~/.claude/state/agent-identity.jsonl)
  CLAUDE_SESSIONS_DIR         Claude Code's own peer registry, read-only here
                              (default ~/.claude/sessions)
SESSION_ARCHIVE_B2_ENDPOINT is recorded in .env for humans and is NEVER passed to rclone: it is
B2's S3 endpoint, and rclone's native b2 backend wants its endpoint left blank.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MANIFEST_NAME = "manifest.jsonl"
LOCK_NAME = ".archive.lock"
SNAPSHOT_PREFIX = ".snapshot-"  # the frozen copy of a transcript being archived; never shipped
REMOTE = "sessionb2"
RCLONE_VERBS = frozenset({"copy", "copyto", "lsf"})
KEY_VARS = ("SESSION_ARCHIVE_B2_KEY_ID", "SESSION_ARCHIVE_B2_APPLICATION_KEY")
_ENV_LINE = re.compile(r"^(?:export\s+)?(SESSION_ARCHIVE_[A-Z0-9_]+)=(.*)$")


class ArchiveError(RuntimeError):
    """A loud, non-destructive stop: the message is printed and the run exits 1."""


def _env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── credentials (A.2a) ──────────────────────────────────────────────────────────────────────


def _read_env_file(path: Path) -> dict[str, str]:
    """The `SESSION_ARCHIVE_*` lines of an env file, and nothing else. Unreadable ⇒ {}."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    out: dict[str, str] = {}
    for raw in text.splitlines():
        m = _ENV_LINE.match(raw.rstrip("\r").strip())
        if m:
            out[m.group(1)] = _env_value(m.group(2))
    return out


def _env_value(raw: str) -> str:
    """A dotenv value: a quoted value is the text inside its quotes (a trailing comment is
    ignored); an unquoted one ends at the first whitespace-preceded `#`."""
    raw = raw.strip()
    if raw[:1] in ("'", '"'):
        end = raw.find(raw[0], 1)
        return raw[1:end] if end > 0 else raw[1:]
    if raw.startswith("#"):
        return ""  # `KEY= # note`: the strip above ate the space, the rest is all comment
    return re.split(r"\s+#", raw, maxsplit=1)[0].strip()


def _setting(name: str, default: str = "") -> str:
    """A `SESSION_ARCHIVE_*` setting: the process environment when set and non-empty, then the
    env file, then the default (an empty value anywhere counts as unset)."""
    if os.environ.get(name):
        return os.environ[name]
    env_file = _env_path("SESSION_ARCHIVE_ENV_FILE", "/opt/fabrik/.env")
    return _read_env_file(env_file).get(name) or default


def _credentials() -> tuple[str, str]:
    env_file = _env_path("SESSION_ARCHIVE_ENV_FILE", "/opt/fabrik/.env")
    found = {k: _setting(k) for k in KEY_VARS}
    if not all(found.values()):
        raise ArchiveError(
            f"missing B2 key: set {KEY_VARS[0]} and {KEY_VARS[1]} in the environment or in "
            f"{env_file} (an application key restricted to the session-archive bucket)"
        )
    return found[KEY_VARS[0]], found[KEY_VARS[1]]


# ── the one rclone door (A.2) ───────────────────────────────────────────────────────────────


def _refused_option(arg: str) -> bool:
    name = arg.split("=", 1)[0]
    return name == "--b2-hard-delete" or name.startswith("--delete")


def _child_env(key_id: str, key: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("RCLONE_")}
    env[f"RCLONE_CONFIG_{REMOTE.upper()}_TYPE"] = "b2"
    env[f"RCLONE_CONFIG_{REMOTE.upper()}_ACCOUNT"] = key_id
    env[f"RCLONE_CONFIG_{REMOTE.upper()}_KEY"] = key
    return env


def _run_rclone(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    """The single seam that starts rclone; tests replace it with a recorder."""
    return subprocess.run(argv, env=env, capture_output=True, text=True, timeout=7200)  # noqa: S603


def _rclone(verb: str, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    if verb not in RCLONE_VERBS:
        raise ValueError(f"rclone verb {verb!r} is not allowed (allowed: {sorted(RCLONE_VERBS)})")
    bad = [a for a in args if _refused_option(a)]
    if bad:
        raise ValueError(f"rclone option(s) {bad} are refused — the transport never deletes")
    argv = ["rclone", verb, *args]
    try:
        done = _run_rclone(argv, env)
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise ArchiveError(f"rclone {verb} did not complete: {type(exc).__name__}") from exc
    if done.returncode != 0:
        tail = " | ".join((done.stderr or "").strip().splitlines()[-3:])
        for secret in (env.get(f"RCLONE_CONFIG_{REMOTE.upper()}_{k}") for k in ("ACCOUNT", "KEY")):
            if secret:
                tail = tail.replace(secret, "<redacted>")  # never echo the key into logs
        raise ArchiveError(f"rclone {verb} failed (rc {done.returncode}): {tail}")
    return done


def _remote_base() -> str:
    bucket = _setting("SESSION_ARCHIVE_B2_BUCKET", "wsl-ozgur")
    prefix = _setting("SESSION_ARCHIVE_B2_PREFIX", "archive").strip("/")
    return f"{REMOTE}:{bucket}/{prefix}"


# ── selection and archiving (A.1, A.1a, A.1b) ───────────────────────────────────────────────


def main_transcripts(projects: Path, after_days: float) -> list[Path]:
    """MAIN transcripts only — `*/subagents/*` is a separate tier and never enters the archive."""
    cutoff = time.time() - after_days * 86400
    out = []
    for p in projects.glob("*/*.jsonl"):
        if "/subagents/" in str(p):  # defensive: the glob cannot reach them, the tier can
            continue
        if p.is_file() and p.stat().st_mtime <= cutoff:
            out.append(p)
    return sorted(out)


def _group_by_inode(paths: list[Path]) -> list[tuple[Path, list[str]]]:
    """One (primary path, other slugs) per file; the primary is the first path in sorted order."""
    groups: dict[tuple[int, int], list[Path]] = {}
    for p in sorted(paths):
        st = p.stat()
        groups.setdefault((st.st_dev, st.st_ino), []).append(p)
    return [(ps[0], sorted({q.parent.name for q in ps[1:]})) for ps in groups.values()]


def _latest_rows(manifest: Path) -> dict[tuple[str, str], dict]:
    latest: dict[tuple[str, str], dict] = {}
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                latest[(r["project_slug"], r["session_id"])] = r
                # a hard link's other slugs find the same row, so a surviving link whose
                # primary folder vanished is not archived a second time
                for alias in r.get("also_slugs") or []:
                    latest[(alias, r["session_id"])] = r
            except (ValueError, KeyError, TypeError):
                continue
    return latest


# ── the agent tag (C.1.1) ───────────────────────────────────────────────────────────────────

_NAME_RE = re.compile(r"[a-z0-9-]{1,32}")  # whoami_agent._NAME_RE, byte-identical


def _as_int(v: object) -> int | None:
    try:
        return int(str(v).strip()) if v is not None and str(v).strip() else None
    except ValueError:
        return None


def _json_rows(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    out = []
    for line in text.splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def agent_map(identity: Path, sessions: Path) -> dict[str, str]:
    """session_id → agent name: the latest identity row per session id, then the registry join.

    The join: a `<pid>.json` entry's `sessionId` is tagged with the name of the identity row whose
    `(pid, pid_start)` equals the entry's `(pid, procStart)` AS INTEGERS — the registry stores
    `procStart` as a JSON string, `whoami_agent._pid_start` writes an int. Read-only: this never
    writes the identity file. Unreadable or absent inputs ⇒ fewer tags, never an error."""
    rows = [r for r in _json_rows(identity) if _NAME_RE.fullmatch(str(r.get("name") or ""))]
    by_sid: dict[str, tuple[int, str]] = {}
    by_proc: dict[tuple[int, int], tuple[int, str]] = {}
    for r in rows:
        at = _as_int(r.get("at")) or 0
        sid = str(r.get("session_id") or "")
        if sid and (sid not in by_sid or at >= by_sid[sid][0]):
            by_sid[sid] = (at, str(r["name"]))
        pid, start = _as_int(r.get("pid")), _as_int(r.get("pid_start"))
        if pid is not None and start is not None:
            key = (pid, start)
            if key not in by_proc or at >= by_proc[key][0]:
                by_proc[key] = (at, str(r["name"]))
    out = {sid: name for sid, (_, name) in by_sid.items()}
    try:
        entries = sorted(sessions.glob("*.json"))
    except OSError:
        entries = []
    for entry in entries:
        for e in _json_rows(entry)[:1] if entry.suffix == ".json" else []:
            sid = str(e.get("sessionId") or "")
            if not sid or sid in out:
                continue
            pid, start = _as_int(e.get("pid")), _as_int(e.get("procStart"))
            if pid is not None and start is not None and (pid, start) in by_proc:
                out[sid] = by_proc[(pid, start)][1]
    return out


def _agents() -> dict[str, str]:
    return agent_map(
        _env_path("AGENT_IDENTITY_FILE", "~/.claude/state/agent-identity.jsonl"),
        _env_path("CLAUDE_SESSIONS_DIR", "~/.claude/sessions"),
    )


def list_agent(manifest: Path, name: str, projects: Path) -> list[str]:
    """`--agent <name>` (C.1.2): that agent's rows, newest `archived_at` first, with whether the
    local transcript still exists — read-only."""
    rows = [r for r in _json_rows(manifest) if r.get("agent") == name]
    rows.sort(key=lambda r: str(r.get("archived_at") or ""), reverse=True)
    out = []
    for r in rows:
        local = (
            projects / str(r.get("project_slug") or "") / f"{r.get('session_id')}.jsonl"
        ).exists()
        out.append(
            f"{r.get('session_id')} {r.get('project_slug')} bytes={r.get('bytes')} "
            f"archived_at={r.get('archived_at')} local={'yes' if local else 'no'}"
        )
    return out


def archive_one(
    src: Path,
    archive_root: Path,
    max_bytes: int | None,
    latest: dict[tuple[str, str], dict],
    also_slugs: list[str],
    agent: str | None = None,
) -> dict | None:
    """Compress one transcript and return its NEW manifest row, or None when nothing changed.

    A file over the per-file ceiling is REPORTED and skipped, never silently archived."""
    st = src.stat()
    if max_bytes is not None and st.st_size > max_bytes:
        print(
            f"  OVER-CEILING {src.name}: {st.st_size} bytes > {max_bytes} — reported, NOT archived"
        )
        return None
    slug, session_id = src.parent.name, src.stem
    dest = archive_root / slug / f"{session_id}.jsonl.zst"
    prev = latest.get((slug, session_id))
    archived = bool(prev) and (archive_root / prev["project_slug"] / dest.name).exists()
    if archived and prev.get("bytes") == st.st_size and prev.get("mtime_ns") == st.st_mtime_ns:
        return None  # A.1a: unchanged since the last archive — no hash, no compression
    # An open window appends while we read, so hash and compress ONE frozen copy: the row must
    # describe exactly the bytes that are uploaded (a JSONL copy is a prefix; its last line may
    # be cut mid-write, and the next day's snapshot supersedes it).
    with tempfile.TemporaryDirectory(prefix=SNAPSHOT_PREFIX, dir=archive_root) as tmp:
        snap = Path(tmp) / src.name
        shutil.copyfile(src, snap)
        digest = _sha256(snap)
        if archived and prev.get("sha256") == digest:
            return None
        size = snap.stat().st_size
        # The skip state (A.1a) must describe THESE bytes: a turn written between the stat above
        # and the copy is in the snapshot but not in `st`. JSONL only appends, so a live size
        # equal to the snapshot's means its mtime is this content's; otherwise it grew again and
        # the next run archives the new bytes anyway.
        after = src.stat()
        mtime_ns = after.st_mtime_ns if after.st_size == size else st.st_mtime_ns
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(  # noqa: S603
            ["zstd", "-12", "-q", "-f", str(snap), "-o", str(dest)], check=True, timeout=1800
        )
    # A manifest row is a PROMISE that the bytes exist and are readable.
    subprocess.run(["zstd", "-t", "-q", str(dest)], check=True, timeout=600)  # noqa: S603
    row = {
        "project_slug": slug,
        "session_id": session_id,
        "sha256": digest,
        "bytes": size,
        "mtime_ns": mtime_ns,
        "also_slugs": also_slugs,
        "archived_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if agent:
        row["agent"] = agent  # absent, never null, for an unbound session (C.1.1)
    return row


def ship(archive_root: Path, env: dict[str, str]) -> None:
    """Upload every archived object; the manifest is excluded here and shipped by copyto."""
    _rclone(
        "copy",
        f"{archive_root}/",
        f"{_remote_base()}/",
        "--fast-list",
        "--transfers",
        "4",
        "--exclude",
        f"/{MANIFEST_NAME}",
        "--exclude",
        f"/{LOCK_NAME}",
        "--exclude",
        f"/{SNAPSHOT_PREFIX}*/**",
        env=env,
    )


def ship_manifest(archive_root: Path, env: dict[str, str]) -> None:
    # --no-check-dest: copyto otherwise HEADs the object through B2's DOWNLOAD host first, and a
    # network that blocks that host (an SNI filter did on 2026-10-08, while uploads worked) hangs
    # the upload. Cost: a run that appended no row uploads an identical manifest, one more kept
    # version (~2 MB); with open windows changing daily, nearly every run appends rows anyway.
    _rclone(
        "copyto",
        "--no-check-dest",
        str(archive_root / MANIFEST_NAME),
        f"{_remote_base()}/{MANIFEST_NAME}",
        env=env,
    )


# ── the verification verbs the gates use (A.2b) ─────────────────────────────────────────────


def remote_count(env: dict[str, str]) -> tuple[int, str]:
    listed = _rclone("lsf", "-R", "--files-only", "--fast-list", f"{_remote_base()}/", env=env)
    count = sum(1 for line in listed.stdout.splitlines() if line.endswith(".jsonl.zst"))
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / MANIFEST_NAME
        _rclone("copyto", f"{_remote_base()}/{MANIFEST_NAME}", str(local), env=env)
        # rclone copyto exits 0 for an absent source and writes nothing: no file = no manifest yet
        return count, _sha256(local) if local.exists() else "absent"


def fetch(path_under_prefix: str, local: str, version_at: str | None, env: dict[str, str]) -> None:
    # rclone copyto exits 0 having written NOTHING when it cannot find the source as one object
    # (absent, or the download host unreachable), and copies a PREFIX as a directory tree: only
    # a regular file that did not exist before the call is a restored object.
    if Path(local).exists():
        raise ArchiveError(f"{local} already exists — fetch writes to a fresh path")
    extra = ["--b2-version-at", version_at] if version_at else []
    _rclone("copyto", *extra, f"{_remote_base()}/{path_under_prefix.lstrip('/')}", local, env=env)
    if Path(local).is_dir():
        raise ArchiveError(
            f"{path_under_prefix} is a prefix, not a single object ({local} is a tree)"
        )
    if not Path(local).is_file():
        raise ArchiveError(
            f"{path_under_prefix} was not downloaded: absent from the bucket, or B2's download "
            "host is unreachable from this network"
        )


# ── the run ─────────────────────────────────────────────────────────────────────────────────


def _probe_binaries(names: tuple[str, ...]) -> None:
    missing = [n for n in names if shutil.which(n) is None]
    if missing:
        raise ArchiveError(f"required binary not found on PATH: {', '.join(missing)}")


MARKER = """THIS DIRECTORY IS DATA, NOT CACHE.

Every *.jsonl here is a Claude Code session transcript — the only resumable copy of that
session, and what session-recall indexes. Deleting them to free disk space loses history
(it happened on 2026-09-03: 11 project folders emptied, found days later).

An off-site copy is shipped daily to Backblaze B2 by scripts/sysadmin/archive_transcripts.py
(docs/workstation/session-history-retention.md in /opt/fabrik). Nothing on this box prunes
these files; if disk is short, ask before removing anything.
"""


def _ensure_marker(projects: Path) -> None:
    """A.6 — the README aimed at the failure that actually happened: a human freeing disk."""
    readme = projects / "README"
    if not readme.exists():
        readme.write_text(MARKER, encoding="utf-8")


@contextlib.contextmanager
def _locked(archive_root: Path):
    archive_root.mkdir(parents=True, exist_ok=True)
    with (archive_root / LOCK_NAME).open("a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _archive(args: argparse.Namespace) -> int:
    projects = _env_path("CLAUDE_PROJECTS_DIR", "~/.claude/projects")
    archive_root = _env_path("ARCHIVE_ROOT", "~/.claude/archive")
    try:
        after_days = float(os.environ.get("ARCHIVE_AFTER_DAYS", "0"))
        max_mb = os.environ.get("ARCHIVE_MAX_FILE_MB")
        max_bytes = int(float(max_mb) * 1024 * 1024) if max_mb else None
    except ValueError as exc:
        raise ArchiveError(
            f"ARCHIVE_AFTER_DAYS / ARCHIVE_MAX_FILE_MB must be numbers: {exc}"
        ) from exc

    if not projects.is_dir():
        raise ArchiveError(f"projects dir not found: {projects}")
    todo = main_transcripts(projects, after_days)
    print(f"archive_transcripts: {len(todo)} MAIN transcript(s) eligible (idle > {after_days}d)")
    if args.dry_run:
        for p in todo:
            print(f"  would archive {p}")
        return 0

    _probe_binaries(("zstd",) if args.no_ship else ("zstd", "rclone"))
    _ensure_marker(projects)
    env = None if args.no_ship else _child_env(*_credentials())

    with _locked(archive_root) as held:
        if not held:
            print("archive_transcripts: another run holds the archive lock — nothing to do")
            return 0
        # A killed run (SIGKILL, power loss) never unwinds its snapshot's with-block; holding the
        # lock, no live run owns one, so every leftover is an orphan.
        for orphan in archive_root.glob(f"{SNAPSHOT_PREFIX}*"):
            if orphan.is_dir() and not orphan.is_symlink():  # ours are real dirs, never links
                shutil.rmtree(orphan)
        manifest = archive_root / MANIFEST_NAME
        latest = _latest_rows(manifest)
        agents = _agents()
        rows = []
        for src, also in _group_by_inode(todo):
            try:
                row = archive_one(src, archive_root, max_bytes, latest, also, agents.get(src.stem))
            except FileNotFoundError as exc:
                if src.exists():  # a missing zstd or archive dir, not a vanished transcript
                    raise ArchiveError(f"could not archive {src}: {exc}") from exc
                print(f"  vanished {src} (removed since the scan) — skipped")
                continue
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise ArchiveError(f"zstd failed on {src}: {exc}") from exc
            except OSError as exc:
                raise ArchiveError(f"could not archive {src}: {exc}") from exc
            if row:
                rows.append(row)

        # ⚠️ The objects ship BEFORE their rows are appended: a row must never vouch for bytes
        # that did not land. A failed copy ⇒ exit 1, no rows.
        if env is not None:
            try:
                ship(archive_root, env)
            except ArchiveError as exc:
                raise ArchiveError(f"TRANSPORT FAILED ({exc}) — no manifest rows written") from exc
        with manifest.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
        print(f"archive_transcripts: {len(rows)} new manifest row(s); archive at {archive_root}")
        if env is not None and manifest.exists():
            # The bytes landed, so the rows are true; a failed manifest upload is retried next run.
            try:
                ship_manifest(archive_root, env)
            except ArchiveError as exc:
                raise ArchiveError(
                    f"manifest upload failed ({exc}) — rows kept, re-shipped next run"
                ) from exc
    return 0


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--no-ship", action="store_true", help="archive locally, skip the transport")
    ap.add_argument("--dry-run", action="store_true", help="list what would be archived")
    ap.add_argument(
        "--remote-count",
        action="store_true",
        help="count remote .zst objects + hash the remote manifest",
    )
    ap.add_argument(
        "--fetch",
        nargs=2,
        metavar=("PATH_UNDER_PREFIX", "LOCAL"),
        help="download one object; write a slug that starts with '-' with a leading '/' "
        "(/-opt-x/<sid>.jsonl.zst), or argparse reads it as an option",
    )
    ap.add_argument(
        "--version-at", help="with --fetch: the object as it was at this RFC3339 instant"
    )
    ap.add_argument(
        "--agent",
        metavar="NAME",
        help="list the manifest rows tagged with this agent, newest first (read-only, C.1.2)",
    )
    args = ap.parse_args(argv)
    try:
        if args.agent:
            if not _NAME_RE.fullmatch(args.agent):
                raise ArchiveError(
                    f"--agent: {args.agent!r} is not an agent name ([a-z0-9-]{{1,32}})"
                )
            archive_root = _env_path("ARCHIVE_ROOT", "~/.claude/archive")
            projects = _env_path("CLAUDE_PROJECTS_DIR", "~/.claude/projects")
            for line in list_agent(archive_root / MANIFEST_NAME, args.agent, projects):
                print(line)
            return 0
        if args.remote_count or args.fetch:
            _probe_binaries(("rclone",))
            env = _child_env(*_credentials())
            if args.remote_count:
                count, digest = remote_count(env)
                print(f"remote_objects {count}")
                print(f"remote_manifest_sha256 {digest}")
            else:
                fetch(args.fetch[0], args.fetch[1], args.version_at, env)
                print(f"fetched {args.fetch[0]} -> {args.fetch[1]}")
            return 0
        return _archive(args)
    except (ArchiveError, OSError) as exc:  # OSError: a full disk outside the loop, too
        print(f"archive_transcripts: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
