#!/usr/bin/env python3
# AFTER-EDIT: docs/development/plans/2026-09-06-plan-1-session-history-retention.md | docs/superpowers/specs/2026-09-05-session-history-retention-design.md | docs/workstation/session-history-retention.md
"""archive_transcripts — Phase A of the session-history retention plan (revision 2026-10-05).

Compresses MAIN Claude transcripts to zstd, records them in a manifest, and ships the archive
straight to the Backblaze B2 bucket with rclone (D-565). Nothing lands on a VPS.

THE SUBAGENT TIER (D-1182): every `<slug>/<session-dir>/subagents/**/*.jsonl` — sidechains, workflow
sidechains and workflow journals; never a `.meta.json` — is archived the same way, keyed
(project_slug, rel) where `rel` is its path under the slug dir, the object at `<slug>/<rel>.zst` (the
local layout, so `ship()` uploads it unchanged), its rows in their OWN manifest
`manifest-subagents.jsonl` (project_slug, rel, session_id = the session dir, sha256, bytes, mtime_ns,
archived_at) so no reader of the MAIN manifest can mis-key one. A tier file that fails to archive is
printed `FAILED … the pruner keeps it` and the night goes on: `prune_transcripts.py` deletes a sidechain
only when this manifest, its `.zst` and the bucket vouch for its bytes.

⚠️ THIS SCRIPT NEVER DELETES A TRANSCRIPT OR AN ARCHIVED OBJECT — locally or in the bucket (it
removes only its own temporary `.snapshot-*` copy). Pruning is Phase C's
`prune_transcripts.py` — the ONLY deleter, eight fail-closed guards, a 3-day window (D-736) — which
runs AFTER this script in the same unit; this script still never deletes. The `.bak` incident
that started this work happened because a
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

SET-ASIDES (D-1188): Claude Code renames a transcript it relocates over to
`<slug>/<sid>.jsonl.superseded-<ms>` (`SET_ASIDE_RE`). It is a MAIN name: an inode that also has a live
`<sid>.jsonl` name is archived under that live name (live names sort first, `main_sort_key`) and the
set-aside's slug never enters `also_slugs`; a set-aside-ONLY inode is archived under its own key
`<sid>.superseded-<ms>`, object `<slug>/<sid>.superseded-<ms>.jsonl.zst` (`main_key`, `local_name`).

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
SUBAGENT_MANIFEST_NAME = "manifest-subagents.jsonl"  # the subagent tier's rows (D-1182)
SUBAGENT_GLOB = "*/*/subagents/**/*.jsonl"
# A set-aside (W-a2cae11b): Claude Code's `relocateSessionTranscript` renames a transcript occupying a
# destination to `<sid>.jsonl.superseded-<ms>`. ASCII classes on purpose: `\d` takes non-ASCII digits,
# which `prune_transcripts._SID_RE` could not restore.
SET_ASIDE_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9_-]*)\.jsonl\.superseded-([0-9]+)")
_SET_ASIDE_KEY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\.superseded-[0-9]+")
MAIN_GLOBS = ("*/*.jsonl", "*/*.jsonl.superseded-*")
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


def main_key(p: Path) -> tuple[str, str, bool] | None:
    """(manifest key, base session id, is a set-aside) for a MAIN name, else None. A live
    `<sid>.jsonl` keys as `<sid>`; a set-aside `<sid>.jsonl.superseded-<ms>` as `<sid>.superseded-<ms>`,
    so a set-aside-ONLY inode never takes the key of a different live file beside it. A live stem that
    itself reads `<sid>.superseded-<ms>` would collide with that key and is not a MAIN name."""
    m = SET_ASIDE_RE.fullmatch(p.name)
    if m:
        return f"{m.group(1)}.superseded-{m.group(2)}", m.group(1), True
    if p.suffix == ".jsonl" and not _SET_ASIDE_KEY_RE.fullmatch(p.stem):
        return p.stem, p.stem, False
    return None


def main_sort_key(p: Path) -> tuple[bool, Path]:
    """Live names before set-asides, so an inode with a live name keeps its live key and primary slug
    (plain Path order puts `-opt-x/<sid>.jsonl.superseded-*` before `-opt-x--wt/<sid>.jsonl`)."""
    return SET_ASIDE_RE.fullmatch(p.name) is not None, p


def local_name(key: str) -> str:
    """The on-disk name a manifest key describes."""
    m = re.fullmatch(r"(.+)\.superseded-([0-9]+)", key)
    return f"{m.group(1)}.jsonl.superseded-{m.group(2)}" if m else f"{key}.jsonl"


def main_transcripts(projects: Path, after_days: float) -> list[Path]:
    """MAIN transcripts only — live names and set-asides; `*/subagents/*` is a separate tier."""
    cutoff = time.time() - after_days * 86400
    out = []
    for p in {q for g in MAIN_GLOBS for q in projects.glob(g)}:
        if "/subagents/" in str(p) or main_key(p) is None:  # the tier reaches subagents/, not this
            continue
        try:
            if p.is_file() and p.stat().st_mtime <= cutoff:
                out.append(p)
        except FileNotFoundError:  # vanished between the glob and the stat
            continue
    return sorted(out)


def subagent_transcripts(projects: Path, after_days: float) -> list[Path]:
    """The subagent tier (D-1182): every `.jsonl` below a `<slug>/<session-dir>/subagents/` dir."""
    cutoff = time.time() - after_days * 86400
    out = []
    for p in projects.glob(SUBAGENT_GLOB):
        try:
            if p.is_file() and not p.is_symlink() and p.stat().st_mtime <= cutoff:
                out.append(p)
        except FileNotFoundError:  # vanished between the glob and the stat
            continue
    return sorted(out)


def _group_by_inode(paths: list[Path]) -> list[tuple[Path, list[str]]]:
    """One (primary path, other slugs) per file; the primary is the first path in `main_sort_key`
    order (a live name when the inode has one). The other slugs are those of its other LIVE names: a
    set-aside is never written into a row, since `also_slugs` reads as "`<slug>/<sid>.jsonl` is a name
    of this inode" — the pruner vouches a set-aside link through its inode's live rows."""
    groups: dict[tuple[int, int], list[Path]] = {}
    for p in sorted(paths, key=main_sort_key):
        try:
            st = p.stat()
        except FileNotFoundError:  # vanished between the scan and this stat (C.2): say so, go on
            print(f"  vanished {p} (removed since the scan) — skipped")
            continue
        groups.setdefault((st.st_dev, st.st_ino), []).append(p)
    return [
        (ps[0], sorted({q.parent.name for q in ps[1:] if not SET_ASIDE_RE.fullmatch(q.name)}))
        for ps in groups.values()
    ]


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


def _latest_subagent_rows(manifest: Path) -> dict[tuple[str, str], dict]:
    """(project_slug, rel) → the latest row of the subagent tier's own manifest (D-1182)."""
    latest: dict[tuple[str, str], dict] = {}
    for r in _json_rows(manifest):
        slug, rel = r.get("project_slug"), r.get("rel")
        if isinstance(slug, str) and isinstance(rel, str) and slug and rel:
            latest[(slug, rel)] = r
    return latest


# ── the agent tag (C.1.1) ───────────────────────────────────────────────────────────────────

_NAME_RE = re.compile(r"[a-z0-9-]{1,32}")  # whoami_agent._NAME_RE, byte-identical


def _as_int(v: object) -> int | None:
    try:
        return int(str(v).strip()) if v is not None and str(v).strip() else None
    except ValueError:
        return None


def _json_rows(path: Path) -> list[dict]:
    """A JSONL file's dict rows (the identity file); unreadable ⇒ []."""
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


def _json_doc(path: Path) -> dict | None:
    """ONE JSON document (a `<pid>.json` registry entry) — pretty-printed or not; unreadable ⇒ None."""
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return d if isinstance(d, dict) else None


def _at(r: dict) -> int:
    """A row's `at` for ordering: a missing or unparsable value ranks BELOW an explicit 0."""
    at = _as_int(r.get("at"))
    return -1 if at is None else at


def agent_map(identity: Path, sessions: Path) -> dict[str, str]:
    """session_id → agent name: the latest identity row per session id, then the registry join.

    The join: a `<pid>.json` entry's `sessionId` is tagged with the name of the identity row whose
    `(pid, pid_start)` equals the entry's `(pid, procStart)` AS INTEGERS — the registry stores
    `procStart` as a JSON string, `whoami_agent._pid_start` writes an int. An AMBIGUOUS join — two
    registry entries for one session id resolving to different names — tags nothing (review
    2026-10-11, archiver-S1). Equal `at` → the later row wins, as `whoami_agent.resolve_agent_name`
    reads; a missing `at` ranks below an explicit 0 (archiver-S5). Read-only: this never writes the
    identity file. Unreadable or absent inputs ⇒ fewer tags, never an error."""
    rows = [r for r in _json_rows(identity) if _NAME_RE.fullmatch(str(r.get("name") or ""))]
    by_sid: dict[str, tuple[int, str]] = {}
    by_proc: dict[tuple[int, int], tuple[int, str]] = {}
    for r in rows:
        at = _at(r)
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
    joined: dict[str, set[str]] = {}
    for entry in entries:
        e = _json_doc(entry)
        if not e:
            continue
        sid = str(e.get("sessionId") or "")
        if not sid or sid in out:
            continue
        pid, start = _as_int(e.get("pid")), _as_int(e.get("procStart"))
        if pid is not None and start is not None and (pid, start) in by_proc:
            joined.setdefault(sid, set()).add(by_proc[(pid, start)][1])
    for sid, names in joined.items():
        if len(names) == 1:
            out[sid] = names.pop()
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
        # local = ANY name of the inode still on disk: the primary slug or a hard-linked twin's
        # (`also_slugs`, D-467) — the primary alone read a surviving twin as gone (archiver-S3)
        raw_also = r.get("also_slugs")
        if isinstance(raw_also, str):  # one slug, never a sequence of characters (archiver-S6)
            also = [raw_also]
        elif isinstance(raw_also, list):
            also = [str(s) for s in raw_also if isinstance(s, str) and s]
        else:  # absent, null, or a scalar the archiver never writes: no aliases (archiver-S8)
            also = []
        slugs = [str(r.get("project_slug") or ""), *also]
        name = local_name(str(r.get("session_id")))
        local = any((projects / s / name).exists() for s in slugs if s)
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
    *,
    tier_key: tuple[str, str] | None = None,
) -> dict | None:
    """Compress one transcript and return its NEW manifest row, or None when nothing changed.

    MAIN (`tier_key` None): keyed (slug, session id) from `<slug>/<sid>.jsonl`, object
    `<slug>/<sid>.jsonl.zst`. The subagent tier passes `tier_key=(slug, rel)`, `rel` being the path under
    the slug dir: object `<slug>/<rel>.zst`, `latest` the tier's own manifest (D-1182).
    A file over the per-file ceiling is REPORTED and skipped, never silently archived."""
    st = src.stat()
    if max_bytes is not None and st.st_size > max_bytes:
        print(
            f"  OVER-CEILING {src.name}: {st.st_size} bytes > {max_bytes} — reported, NOT archived"
        )
        return None
    if tier_key is None:
        name_key = main_key(src)
        if name_key is None:
            raise ArchiveError(f"{src} is not a MAIN transcript name")  # main_transcripts never yields one
        slug, session_id = src.parent.name, name_key[0]
        key = (slug, session_id)
        dest = archive_root / slug / f"{session_id}.jsonl.zst"
    else:
        (slug, rel), key = tier_key, tier_key
        session_id = rel.split("/", 1)[0]  # the session dir: `<uuid>` or `<uuid>.superseded-<ms>`
        dest = archive_root / slug / f"{rel}.zst"
    prev = latest.get(key)
    if tier_key is None:
        # a hard-linked twin's row lives under its primary slug (`also_slugs`)
        archived = bool(prev) and (archive_root / prev["project_slug"] / dest.name).exists()
    else:
        archived = bool(prev) and dest.exists()
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
        # Compressed and tested beside the snapshot, then renamed into place (same filesystem): a
        # compress or test that fails never leaves a partial `.zst` at `dest` for `ship()` to upload
        # over the key's last good version (review W-62d2ce7d pass 1, A-haiku-1).
        out = Path(tmp) / "object.jsonl.zst"
        subprocess.run(  # noqa: S603
            ["zstd", "-12", "-q", "-f", str(snap), "-o", str(out)], check=True, timeout=1800
        )
        # A manifest row is a PROMISE that the bytes exist and are readable.
        subprocess.run(["zstd", "-t", "-q", str(out)], check=True, timeout=600)  # noqa: S603
        os.replace(out, dest)
    row = {
        "project_slug": slug,
        "session_id": session_id,
        "sha256": digest,
        "bytes": size,
        "mtime_ns": mtime_ns,
        "archived_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if tier_key is None:
        row["also_slugs"] = also_slugs
    else:
        row["rel"] = tier_key[1]
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
        f"/{SUBAGENT_MANIFEST_NAME}",
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
    # The MAIN manifest first, then the subagent tier's (D-1182) when it exists.
    for name in (MANIFEST_NAME, SUBAGENT_MANIFEST_NAME):
        if (archive_root / name).exists():
            _rclone(
                "copyto",
                "--no-check-dest",
                str(archive_root / name),
                f"{_remote_base()}/{name}",
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
(docs/workstation/session-history-retention.md in /opt/fabrik) — the subagents/ transcripts
too (D-1182). The ONLY thing that prunes them is scripts/sysadmin/prune_transcripts.py (D-736):
after a 3-day window, never an open session, never a project's or an agent's newest, never a
file the archive and the bucket cannot prove byte-for-byte — and every deletion is listed in
~/.claude/archive/pruned.jsonl, which `prune_transcripts.py --restore <session_id>` (or
`--restore agent-<id>` for a subagent transcript) puts back. If disk is short, ask before
removing anything by hand.
"""


def _ensure_marker(projects: Path) -> None:
    """A.6 — the README aimed at the failure that actually happened: a human freeing disk. A README
    carrying an older MARKER text is rewritten, so it never says 'nothing prunes' once something does."""
    readme = projects / "README"
    try:
        current = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        current = None
    if current != MARKER:
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
    subs = subagent_transcripts(projects, after_days)
    print(f"archive_transcripts: {len(todo)} MAIN transcript(s) eligible (idle > {after_days}d)")
    print(f"archive_transcripts: {len(subs)} subagent transcript(s) eligible (idle > {after_days}d)")
    if args.dry_run:
        for p in [*todo, *subs]:
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
            base = (main_key(src) or ("", src.stem, False))[1]  # a set-aside's agent is its session's
            try:
                row = archive_one(src, archive_root, max_bytes, latest, also, agents.get(base))
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

        # The subagent tier (D-1182): a per-file failure is reported and the night goes on — the
        # pruner deletes nothing this manifest does not vouch for, so a skipped file is only kept.
        sub_manifest = archive_root / SUBAGENT_MANIFEST_NAME
        sub_latest = _latest_subagent_rows(sub_manifest)
        sub_rows, sub_failed = [], 0
        for src in subs:
            slug = src.relative_to(projects).parts[0]
            tier_key = (slug, src.relative_to(projects / slug).as_posix())
            try:
                row = archive_one(src, archive_root, max_bytes, sub_latest, [], tier_key=tier_key)
            except FileNotFoundError:
                if not src.exists():
                    print(f"  vanished {src} (removed since the scan) — skipped")
                    continue
                sub_failed += 1
                print(f"  FAILED {src}: missing file or binary — not archived; the pruner keeps it")
                continue
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                sub_failed += 1
                print(f"  FAILED {src}: {exc} — not archived; the pruner keeps it")
                continue
            if row:
                sub_rows.append(row)

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
        if sub_rows:
            with sub_manifest.open("a", encoding="utf-8") as fh:
                for row in sub_rows:
                    fh.write(json.dumps(row, sort_keys=True) + "\n")
        print(
            f"archive_transcripts: {len(rows)} new manifest row(s), {len(sub_rows)} subagent row(s), "
            f"{sub_failed} subagent failure(s); archive at {archive_root}"
        )
        if env is not None:
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
            others = [
                f
                for f, v in (
                    ("--fetch", args.fetch),
                    ("--remote-count", args.remote_count),
                    ("--no-ship", args.no_ship),
                    ("--dry-run", args.dry_run),
                    ("--version-at", args.version_at),
                )
                if v
            ]
            if others:  # a read-only listing never doubles as another verb (archiver-S4)
                ap.error(f"--agent takes no other verb or flag; given: {' '.join(others)}")
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
