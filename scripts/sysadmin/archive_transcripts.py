#!/usr/bin/env python3
# AFTER-EDIT: docs/development/plans/2026-09-06-plan-1-session-history-retention.md | docs/superpowers/specs/2026-09-05-session-history-retention-design.md
"""archive_transcripts — Phase A of the session-history retention plan.

Compresses MAIN Claude transcripts to zstd, records them in a manifest, and ships the
archive to the VPS where Backrest carries it to Backblaze B2.

⚠️ THIS SCRIPT NEVER DELETES ANYTHING. Pruning is Phase C and is blocked behind a proven
restore (Gate B) and its own graders. If you are reading this while adding a delete, stop:
the plan's safety property is that the archive exists before anything is removed, and the
`.bak` incident that started this work happened because a "provably lossless" deletion was
argued from a size comparison instead of from bytes.

⚠️ `--delete` AND `--remove-source-files` ARE BANNED FROM THE TRANSPORT, and the ban is
GRADED (`tests/test_archive_transcripts.py`) rather than trusted. Either flag turns rsync
into a mirror that deletes the ARCHIVE when the local side is pruned — silently inverting
the whole safety model. A guard that depends on future humans not adding a flag is not a
guard, which is why a test greps this file.

THE MANIFEST KEY IS (project_slug, session_id, sha256), all three:
  * `session_id` is unique inside its project directory, NOT across all 266 of them, so a
    two-part key could match a transcript against another project's archive;
  * `sha256` is the CURRENT hash of the source. Transcripts are mutated in place here —
    that is what produced 15 `.bak` files, 13 of which diverged from their live counterpart
    mid-stream — so an archive row vouches for the bytes it saw, never for a session id.

Env (12-Factor III; `core/10-python.md:128` bans hardcoded hosts):
  ARCHIVE_ROOT          local archive dir      (default ~/.claude/archive)
  ARCHIVE_REMOTE        rsync destination      (default vps:/opt/session-archive/)
  ARCHIVE_AFTER_DAYS    only archive files older than this   (default 0 = all)
  ARCHIVE_MAX_FILE_MB   per-file ceiling; larger files are REPORTED, never archived
  CLAUDE_PROJECTS_DIR   source tree            (default ~/.claude/projects)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

MANIFEST_NAME = "manifest.jsonl"


def _env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main_transcripts(projects: Path, after_days: float) -> list[Path]:
    """MAIN transcripts only — `*/subagents/*` is a separate tier (7 days, no archive) and
    must never enter the archive or the manifest."""
    cutoff = time.time() - after_days * 86400
    out = []
    for p in projects.glob("*/*.jsonl"):
        if "/subagents/" in str(p):  # defensive: the glob cannot reach them, the tier can
            continue
        if p.stat().st_mtime <= cutoff:
            out.append(p)
    return sorted(out)


def archive_one(src: Path, archive_root: Path, max_bytes: int | None) -> dict | None:
    """Compress one transcript and return its manifest row, or None when it is skipped.

    A file over the per-file ceiling is REPORTED and skipped, never silently archived: the
    aggregate bound cannot see a runaway session (the largest transcript measured was
    733,603,901 bytes, and 50% of all bytes live in the top 14 files)."""
    size = src.stat().st_size
    if max_bytes is not None and size > max_bytes:
        print(f"  OVER-CEILING {src.name}: {size} bytes > {max_bytes} — reported, NOT archived")
        return None
    slug, session_id = src.parent.name, src.stem
    dest_dir = archive_root / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{session_id}.jsonl.zst"
    digest = _sha256(src)
    subprocess.run(  # noqa: S603
        ["zstd", "-12", "-q", "-f", str(src), "-o", str(dest)], check=True, timeout=1800
    )
    # Verify the artifact before it is allowed into the manifest. A manifest row is a
    # PROMISE that the bytes exist and are readable; Phase C deletes on that promise.
    subprocess.run(["zstd", "-t", "-q", str(dest)], check=True, timeout=600)  # noqa: S603
    return {
        "project_slug": slug,
        "session_id": session_id,
        "sha256": digest,
        "bytes": size,
        "archived_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def ship(archive_root: Path, remote: str) -> None:
    """rsync the archive to the VPS. Flags are argued, not copied from the nearest example.

    -a       recurse + preserve times/perms (the shape of scripts/sync-vps-sysadmin.sh:28)
    --no-o   ) owner/group across two machines with different uid maps is meaningless here
    --no-g   ) and fails as non-root
    --partial a dropped link resumes rather than restarting a large .zst
    NO -z     the payload is already zstd; compressing it again is wasted CPU every run

    NOT --delete. NOT --remove-source-files. See the module docstring; a test enforces it.
    """
    host = remote.split(":", 1)[0]
    remote_dir = remote.split(":", 1)[1] if ":" in remote else remote
    subprocess.run(["ssh", host, f"mkdir -p {remote_dir}"], check=True, timeout=120)  # noqa: S603
    subprocess.run(  # noqa: S603
        ["rsync", "-a", "--no-o", "--no-g", "--partial", f"{archive_root}/", remote],
        check=True,
        timeout=7200,
    )


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-ship", action="store_true", help="archive locally, skip the transport")
    ap.add_argument("--dry-run", action="store_true", help="list what would be archived")
    args = ap.parse_args(argv)

    projects = _env_path("CLAUDE_PROJECTS_DIR", "~/.claude/projects")
    archive_root = _env_path("ARCHIVE_ROOT", "~/.claude/archive")
    remote = os.environ.get("ARCHIVE_REMOTE", "vps:/opt/session-archive/")
    after_days = float(os.environ.get("ARCHIVE_AFTER_DAYS", "0"))
    max_mb = os.environ.get("ARCHIVE_MAX_FILE_MB")
    max_bytes = int(float(max_mb) * 1024 * 1024) if max_mb else None

    if not projects.is_dir():
        print(f"archive_transcripts: projects dir not found: {projects}", file=sys.stderr)
        return 1

    todo = main_transcripts(projects, after_days)
    print(
        f"archive_transcripts: {len(todo)} MAIN transcript(s) eligible (older than {after_days}d)"
    )
    if args.dry_run:
        for p in todo:
            print(f"  would archive {p}")
        return 0

    archive_root.mkdir(parents=True, exist_ok=True)
    manifest = archive_root / MANIFEST_NAME
    already = set()
    if manifest.exists():
        for line in manifest.read_text().splitlines():
            try:
                r = json.loads(line)
                already.add((r["project_slug"], r["session_id"], r["sha256"]))
            except Exception:  # noqa: BLE001, S112
                continue

    rows = []
    for src in todo:
        try:
            row = archive_one(src, archive_root, max_bytes)
        except subprocess.CalledProcessError as exc:
            print(f"archive_transcripts: FAILED on {src}: {exc}", file=sys.stderr)
            return 1
        if row and (row["project_slug"], row["session_id"], row["sha256"]) not in already:
            rows.append(row)

    # ⚠️ THE TRANSPORT RUNS BEFORE THE MANIFEST IS APPENDED. A manifest row is what Phase C
    # will one day accept as permission to delete a local file, so it must never exist for
    # bytes that did not land remotely. rsync failure => non-zero exit, NO rows written.
    if not args.no_ship:
        try:
            ship(archive_root, remote)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            print(
                f"archive_transcripts: TRANSPORT FAILED ({exc}) — no manifest rows written",
                file=sys.stderr,
            )
            return 1

    with manifest.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    print(f"archive_transcripts: {len(rows)} new manifest row(s); archive at {archive_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
