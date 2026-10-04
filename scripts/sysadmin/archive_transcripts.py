#!/usr/bin/env python3
# AFTER-EDIT: docs/development/plans/2026-09-06-plan-1-session-history-retention.md | docs/superpowers/specs/2026-09-05-session-history-retention-design.md | docs/workstation/session-history-retention.md
"""archive_transcripts — Phase A of the session-history retention plan (revision 2026-10-05).

Compresses MAIN Claude transcripts to zstd, records them in a manifest, and ships the archive
straight to the Backblaze B2 bucket with rclone (D-565). Nothing lands on a VPS.

⚠️ THIS SCRIPT NEVER DELETES ANYTHING — locally or in the bucket. Pruning is Phase C, which
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

Env (12-Factor III):
  ARCHIVE_ROOT                local archive dir                       (default ~/.claude/archive)
  ARCHIVE_AFTER_DAYS          only files idle longer than this        (default 1)
  ARCHIVE_MAX_FILE_MB         per-file ceiling; larger files are REPORTED, never archived
  CLAUDE_PROJECTS_DIR         source tree                             (default ~/.claude/projects)
  SESSION_ARCHIVE_B2_BUCKET   the bucket                              (default wsl-ozgur)
  SESSION_ARCHIVE_B2_PREFIX   the path under the bucket               (default archive)
  SESSION_ARCHIVE_B2_KEY_ID / SESSION_ARCHIVE_B2_APPLICATION_KEY      the application key
  SESSION_ARCHIVE_ENV_FILE    where the two key variables are read from when the process
                              environment lacks them; only `SESSION_ARCHIVE_*` lines are read
                              (default /opt/fabrik/.env)
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
        if not m:
            continue
        value = m.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[m.group(1)] = value
    return out


def _credentials() -> tuple[str, str]:
    env_file = _env_path("SESSION_ARCHIVE_ENV_FILE", "/opt/fabrik/.env")
    found = {k: os.environ.get(k, "") for k in KEY_VARS}
    if not all(found.values()):
        from_file = _read_env_file(env_file)
        found = {k: found[k] or from_file.get(k, "") for k in KEY_VARS}
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
        tail = (done.stderr or "").strip().splitlines()[-3:]
        raise ArchiveError(f"rclone {verb} failed (rc {done.returncode}): {' | '.join(tail)}")
    return done


def _remote_base() -> str:
    bucket = os.environ.get("SESSION_ARCHIVE_B2_BUCKET", "wsl-ozgur")
    prefix = os.environ.get("SESSION_ARCHIVE_B2_PREFIX", "archive").strip("/")
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
            except (ValueError, KeyError, TypeError):
                continue
    return latest


def archive_one(
    src: Path,
    archive_root: Path,
    max_bytes: int | None,
    latest: dict[tuple[str, str], dict],
    also_slugs: list[str],
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
    if prev and dest.exists():
        if prev.get("bytes") == st.st_size and prev.get("mtime_ns") == st.st_mtime_ns:
            return None  # A.1a: unchanged since the last archive — no hash, no compression
    digest = _sha256(src)
    if prev and dest.exists() and prev.get("sha256") == digest:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(  # noqa: S603
        ["zstd", "-12", "-q", "-f", str(src), "-o", str(dest)], check=True, timeout=1800
    )
    # A manifest row is a PROMISE that the bytes exist and are readable.
    subprocess.run(["zstd", "-t", "-q", str(dest)], check=True, timeout=600)  # noqa: S603
    return {
        "project_slug": slug,
        "session_id": session_id,
        "sha256": digest,
        "bytes": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "also_slugs": also_slugs,
        "archived_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


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
        env=env,
    )


def ship_manifest(archive_root: Path, env: dict[str, str]) -> None:
    _rclone(
        "copyto", str(archive_root / MANIFEST_NAME), f"{_remote_base()}/{MANIFEST_NAME}", env=env
    )


# ── the verification verbs the gates use (A.2b) ─────────────────────────────────────────────


def remote_count(env: dict[str, str]) -> tuple[int, str]:
    listed = _rclone("lsf", "-R", "--files-only", "--fast-list", f"{_remote_base()}/", env=env)
    count = sum(1 for line in listed.stdout.splitlines() if line.endswith(".jsonl.zst"))
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / MANIFEST_NAME
        _rclone("copyto", f"{_remote_base()}/{MANIFEST_NAME}", str(local), env=env)
        return count, _sha256(local)


def fetch(path_under_prefix: str, local: str, version_at: str | None, env: dict[str, str]) -> None:
    extra = ["--b2-version-at", version_at] if version_at else []
    _rclone("copyto", *extra, f"{_remote_base()}/{path_under_prefix.lstrip('/')}", local, env=env)


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
    after_days = float(os.environ.get("ARCHIVE_AFTER_DAYS", "1"))
    max_mb = os.environ.get("ARCHIVE_MAX_FILE_MB")
    max_bytes = int(float(max_mb) * 1024 * 1024) if max_mb else None

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
        manifest = archive_root / MANIFEST_NAME
        latest = _latest_rows(manifest)
        rows = []
        for src, also in _group_by_inode(todo):
            try:
                row = archive_one(src, archive_root, max_bytes, latest, also)
            except subprocess.CalledProcessError as exc:
                raise ArchiveError(f"zstd failed on {src}: {exc}") from exc
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
        "--fetch", nargs=2, metavar=("PATH_UNDER_PREFIX", "LOCAL"), help="download one object"
    )
    ap.add_argument(
        "--version-at", help="with --fetch: the object as it was at this RFC3339 instant"
    )
    args = ap.parse_args(argv)
    try:
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
    except ArchiveError as exc:
        print(f"archive_transcripts: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
