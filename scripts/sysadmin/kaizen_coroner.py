#!/usr/bin/env python3
# AFTER-EDIT: tests/test_kaizen_coroner.py, docs/workstation/kaizen-event-stream.md | none
"""Kaizen M1 coroner — reconstructs `death`/`revival`/`session_end` events post-hoc and
closes the run records of sessions that can no longer close their own.

WHY THIS EXISTS
---------------
Hooks go silent exactly when things get interesting: a mid-stream death fires no Stop
hook and writes no closing event, so a hook-only meter has survivorship bias built in
(docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md:113-130). The coroner
closes the hole from SECOND sources written by machinery outside the dead session's
process: the resume mesh's `.errparked` death records + notify log, and transcript
tails carrying the mesh's own detection keys.

THE AUTHORITY on the mesh is docs/workstation/hooks-index.md — line 31 documents the
five mid-stream death texts (`isApiErrorMessage` + one of the family) and the
STRUCTURAL `api_error` key (`retryAttempt == maxRetries` with a connection code — never
a string allowlist of codes); line 36 documents the `.errparked` death record
(`<class> <epoch>` in the mesh lock dir). A still-retrying `api_error`
(attempt < max) is NOT a death — the CLI may recover on its own. The detection walk
mirrors the mesh's own (`~/.claude/bin/claude-stop-decider.py::_tail_is_stalled`),
including its recovery discrimination: a newer non-error assistant record or genuine
operator input outranks an older stall.

WHAT ONE SWEEP DOES — and nothing else
--------------------------------------
For each session with death evidence and no `session_end` event in its stream:

1. Append a reconstructed ``death`` event (``class`` from the marker/tail key;
   ``exposure`` joined from THAT session's own last trusted events via
   ``emit(..., exposure_override=...)`` — the coroner is the ONE sanctioned
   `exposure_override` producer; unjoinable fields are the literal ``unknown``;
   marked ``reconstructed: true``) to THAT session's event file.
2. Append a matching ``revival`` event where the mesh log shows one
   (an ``autoresume-spawned`` line for that sid; the pane self-watch prints its wake
   into the pane, not the log — honest limit: those revivals are not visible here).
3. Append a ``session_end`` for the coroner's post-hoc close.

Record closure — via the load/save API under the record lock
(`scripts/command_run.py:154-174` + `_record_lock` at `:115`, held across the whole
re-load→mutate→save exactly like every mutating subcommand), NEVER any other record
mutation:

- a ``state: "running"`` record attributed to a death → ``state: "died"``,
  ``closed_by: "coroner"`` (platform-stamped, never the agent);
- a ``state: "running"`` record older than ``KAIZEN_RUN_TTL_H`` (default 12, matching
  the Stop hook's stale-fail-open horizon) with NO death evidence →
  ``state: "expired"``, ``closed_by: "ttl"``.

The Stop hook blocks ONLY on ``state == "running"``
(.claude/hooks/final_gate_stop.py:482,1029,1263 — verified on the merged file
2026-08-20), so a coroner-closed record never pins its project.

The hole metric: ``holes = transcripts-with-activity − sessions-with-session_end`` per
day — :func:`holes` returns the NUMBER for T06 to consume as a first-class
instrument-health input.

HARD BOUNDARIES
---------------
- The sound system is READ-ONLY, always: markers, lock dir and log are opened for
  reading only — never written, deleted, truncated, or fired.
- Fail-open like every sensor: :func:`sweep` never raises into its caller; a malformed
  marker or transcript line is SKIPPED, never guessed at.
- Every read is ``errors="replace"`` and byte-bounded where the source can be large
  (transcript tails read the LAST ``TAIL_BYTES``, never the whole file).

Box-local, stdlib only. Config via env: ``KAIZEN_RUN_TTL_H`` (default 12),
``KAIZEN_CORONER_LOOKBACK_H`` (default 48 — how far back transcript activity is
scanned), plus the injectable ``Sources`` defaults (``CLAUDE_SOUND_LOCKDIR``,
``KAIZEN_EVENTS_DIR``, ``COMMAND_RUN_DIR``).
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import json
import os
import re
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import kaizen_events  # T01 emitter — same directory
except Exception:  # pragma: no cover - a box mid-sync
    kaizen_events = None  # type: ignore[assignment]

try:
    import command_run  # scripts/command_run.py — the record load/save API
except Exception:  # pragma: no cover - a box mid-sync
    command_run = None  # type: ignore[assignment]

UNKNOWN = "unknown"
EXPOSURE_KEYS = ("commit", "account", "model", "project", "headless", "plan_era")

#: The five mid-stream death texts — docs/workstation/hooks-index.md:31 (the authority;
#: one construction site in the CLI 2.1.219 string table). Substring match, like the
#: mesh's own detector.
MID_STREAM_DEATH_TEXTS = (
    "Response stalled mid-stream",
    "Server error mid-response",
    "Connection closed mid-response",
    "Response stalled while thinking",
    "Connection closed while thinking",
)

#: The class name the mesh itself parks tail-detected deaths under
#: (claude-stop-decider.py writes `api_error_stalled` into the `.errparked` record).
TAIL_DEATH_CLASS = "api_error_stalled"

#: Harness user-turn wrappers — a user record STARTING with one is a machine append,
#: not operator recovery (mirrored from the mesh's `_MACHINE_APPEND_MARKS`).
MACHINE_APPEND_MARKS = (
    "<task-notification>",
    "<system-reminder>",
    "Stop hook feedback:",
    "[SYSTEM NOTIFICATION",
    "[SCHEDULED TASK",
    "[MESSAGE FROM NON-USER SOURCE",
)

DEFAULT_TTL_H = 12.0
DEFAULT_LOOKBACK_H = 48.0
TAIL_BYTES = 256 * 1024  # transcript tail window (same bound the mesh decider uses)
TAIL_MAX_BYTES = 4 * 1024 * 1024  # geometric-growth hard cap for oversized last lines
LOG_TAIL_BYTES = 1024 * 1024  # mesh notify-log tail window
EVENTS_SCAN_BYTES = 8 * 1024 * 1024  # per-session event files are line-capped and small

_CLASS_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _warn(msg: str) -> None:
    """stderr only — the coroner logs its own failures like every other sensor."""
    try:
        print(f"kaizen_coroner: {msg}", file=sys.stderr)
    except Exception:  # pragma: no cover - stderr itself is gone
        pass


def _mesh_safe(sid: str) -> str:
    """The mesh's own sid sanitization (`tr -c 'A-Za-z0-9_-' '_' | head -c 64`) —
    marker filenames and record matching must use the SAME mapping the writers used."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(sid))[:64]


@dataclasses.dataclass(frozen=True)
class Sources:
    """Every source the coroner reads (and the two stores it writes) — injectable so
    fixtures SIMULATE the marker/lock-dir/transcript shapes in tmp dirs; the live paths
    are only ever DEFAULTS, never hardcoded into the logic."""

    lock_dir: Path  # mesh lock dir: `<safe_sid>.errparked` markers — READ-ONLY
    mesh_log: Path  # the mesh notify log (claude-sound.sh's LOG) — READ-ONLY
    transcripts_dir: Path  # ~/.claude/projects — READ-ONLY
    events_dir: Path  # kaizen event stream — the coroner APPENDS here (via emit)
    runs_dir: Path  # command-run records — the coroner CLOSES here (via load/save)

    @classmethod
    def default(cls) -> Sources:
        lock = os.getenv("CLAUDE_SOUND_LOCKDIR", "") or f"/tmp/claude-sound-locks-{os.getuid()}"
        events = (
            kaizen_events.events_dir()
            if kaizen_events
            else Path(os.getenv("KAIZEN_EVENTS_DIR", str(Path.home() / ".claude/state/events")))
        )
        runs = os.getenv("COMMAND_RUN_DIR", "") or str(
            Path.home() / ".claude" / "state" / "command-runs"
        )
        return cls(
            lock_dir=Path(lock),
            mesh_log=Path.home() / ".claude" / "sound-debug.log",
            transcripts_dir=Path.home() / ".claude" / "projects",
            events_dir=Path(events),
            runs_dir=Path(runs),
        )


@dataclasses.dataclass
class CoronerReport:
    deaths_reconstructed: list[str] = dataclasses.field(default_factory=list)
    revivals: list[str] = dataclasses.field(default_factory=list)
    session_ends: list[str] = dataclasses.field(default_factory=list)
    records_died: list[str] = dataclasses.field(default_factory=list)
    records_expired: list[str] = dataclasses.field(default_factory=list)
    holes_today: int = 0
    errors: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class _Death:
    sid: str  # as the evidence names it (marker stem, or transcript uuid)
    cls: str  # the death class, from the marker/tail key
    key: str  # WHICH detector fired — errparked | mid_stream_text:… | retries_exhausted:…
    died_at: str  # joined timestamp, or the literal "unknown"


# ── bounded, replace-decoded reads (the sound system is READ-ONLY, always) ───────────


def _tail_lines(path: Path, bound: int) -> list[str]:
    """The LAST ``bound`` bytes of ``path`` as text lines — never a whole-file slurp.

    Opened read-only; a partial first line (we landed mid-line) is dropped. Any error
    is an empty answer, never an exception.
    """
    return _tail_lines_bounded(path, bound)[0]


def _tail_lines_bounded(path: Path, bound: int) -> tuple[list[str], bool]:
    """``(lines, whole_file)`` — ``whole_file`` True when the window covered the file,
    so every returned line is complete (nothing left to widen into)."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            offset = max(0, size - bound)
            fh.seek(offset)
            text = fh.read(bound).decode("utf-8", "replace")
        lines = text.splitlines()
        if offset > 0 and lines:
            lines = lines[1:]  # the first line is a fragment of a longer one
        return lines, offset == 0
    except OSError:
        return [], False


def _ttl_s() -> float:
    raw = os.getenv("KAIZEN_RUN_TTL_H", "")
    try:
        hours = float(raw) if raw.strip() else DEFAULT_TTL_H
    except ValueError:
        hours = DEFAULT_TTL_H
    if not (0 < hours < 24 * 365):  # non-finite and non-positive both fail this
        hours = DEFAULT_TTL_H
    return hours * 3600


def _lookback_s() -> float:
    raw = os.getenv("KAIZEN_CORONER_LOOKBACK_H", "")
    try:
        hours = float(raw) if raw.strip() else DEFAULT_LOOKBACK_H
    except ValueError:
        hours = DEFAULT_LOOKBACK_H
    if not (0 < hours < 24 * 365):
        hours = DEFAULT_LOOKBACK_H
    return hours * 3600


# ── death evidence: the mesh's .errparked markers (hooks-index.md:36) ────────────────


def _errparked_markers(lock_dir: Path) -> dict[str, tuple[str, float | None]]:
    """``{safe_sid: (class, epoch|None)}`` from the lock dir's ``.errparked`` records.

    Content shape is ``<class> <epoch>`` (claude-sound.sh:146). A marker whose class
    token does not look like a class is SKIPPED, never guessed at. Read-only.
    """
    out: dict[str, tuple[str, float | None]] = {}
    try:
        entries = list(lock_dir.iterdir())
    except OSError:
        return out
    for path in entries:
        if not path.name.endswith(".errparked"):
            continue
        try:
            with open(path, "rb") as fh:
                head = fh.read(256).decode("utf-8", "replace")
        except OSError:
            continue
        parts = head.split()
        if not parts or not _CLASS_RE.match(parts[0]):
            continue  # malformed marker → skipped, never guessed at
        epoch: float | None = None
        if len(parts) > 1 and parts[1].isdigit():
            epoch = float(parts[1])
        out[path.name[: -len(".errparked")]] = (parts[0], epoch)
    return out


# ── death evidence: transcript tails (hooks-index.md:31) ─────────────────────────────


def _row_text(content: object) -> str:
    """The typed text of a message content — bare string or text-block list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                parts.append(text if isinstance(text, str) else "")
        return " ".join(parts)
    return ""


def _retries_exhausted(attempt: object, mx: object) -> bool:
    """The STRUCTURAL exhausted-retries key: both genuine ints (bool is an int —
    excluded), equal, and ≥ 1 — never a string allowlist of connection codes."""
    if isinstance(attempt, bool) or isinstance(mx, bool):
        return False
    if not (isinstance(attempt, int) and isinstance(mx, int)):
        return False
    return attempt == mx and mx >= 1


def _still_retrying(attempt: object, mx: object) -> bool:
    """A GENUINE still-retrying record: both real ints (not bool) and attempt < max."""
    if isinstance(attempt, bool) or isinstance(mx, bool):
        return False
    if not (isinstance(attempt, int) and isinstance(mx, int)):
        return False
    return 0 <= attempt < mx


def _tail_verdict(transcript: Path) -> _Death | str | None:
    """Transcript verdict: a :class:`_Death`, ``"alive"``, or None (inconclusive).

    The tail window grows GEOMETRICALLY (``TAIL_BYTES`` doubling to ``TAIL_MAX_BYTES``)
    until at least one complete line lands — a last line bigger than one window must
    not empty it and vanish a recovery message. At the cap with still no complete line
    the evidence is unreadable, and unreadable fails toward ALIVE: no death without
    readable evidence.
    """
    bound = TAIL_BYTES
    while True:
        lines, whole = _tail_lines_bounded(transcript, bound)
        if lines or whole:
            return _walk_rows(transcript.stem, lines)
        if bound >= TAIL_MAX_BYTES:
            return "alive"  # UNKNOWN at the cap — no death without readable evidence
        bound = min(bound * 2, TAIL_MAX_BYTES)


def _walk_rows(sid: str, lines: list[str]) -> _Death | str | None:
    """Walk newest-first and STOP at the FIRST conclusive record.

    Mirrors the mesh's own detector (claude-stop-decider.py::_tail_is_stalled):
    - a non-error assistant record → the model spoke again → ``"alive"``;
    - genuine operator input (not a machine append) → attended → ``"alive"``;
    - ``isApiErrorMessage`` + one of the five texts → death; outside the family →
      stop inconclusive (the marker's own class may still rule);
    - ``type=system``/``subtype=api_error``: retries exhausted with a connection code →
      death; STILL RETRYING → stop, not-dead — a newer retrying record proves the
      session was alive after any older episode, so the walk NEVER continues past it;
    - anything malformed → skipped, never guessed at.
    """
    for raw in reversed(lines):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except ValueError:
            continue  # malformed line → skip, never guess
        if not isinstance(row, dict):
            continue
        msg = row.get("message")
        msg = msg if isinstance(msg, dict) else {}
        role = msg.get("role")
        if role == "user":
            if row.get("isMeta") or row.get("isCompactSummary"):
                continue
            text = _row_text(msg.get("content"))
            if text.strip() and not any(
                text.lstrip().startswith(m) for m in MACHINE_APPEND_MARKS
            ):
                return "alive"  # genuine operator input — the session is attended
            continue  # tool_results / harness notifications — machine appends
        if role == "assistant":
            if not row.get("isApiErrorMessage"):
                return "alive"  # the model spoke again — recovered
            text = _row_text(msg.get("content"))
            for pattern in MID_STREAM_DEATH_TEXTS:
                if pattern in text:
                    return _Death(
                        sid=sid,
                        cls=TAIL_DEATH_CLASS,
                        key=f"mid_stream_text:{pattern}",
                        died_at=str(row.get("timestamp") or UNKNOWN),
                    )
            # An api-error record OUTSIDE the death family is still a conclusive
            # newest record — stop; the marker's own class may rule, the tail won't.
            return None
        if row.get("type") == "system" and row.get("subtype") == "api_error":
            err = row.get("error")
            err = err if isinstance(err, dict) else {}
            conn = err.get("connection")
            conn = conn if isinstance(conn, dict) else {}
            code = conn.get("code")
            if (
                isinstance(code, str)
                and code
                and _retries_exhausted(row.get("retryAttempt"), row.get("maxRetries"))
            ):
                return _Death(
                    sid=sid,
                    cls=TAIL_DEATH_CLASS,
                    key=f"retries_exhausted:{code}",
                    died_at=str(row.get("timestamp") or UNKNOWN),
                )
            if _still_retrying(row.get("retryAttempt"), row.get("maxRetries")):
                return "alive"  # the CLI was alive here and may recover — never walk past
            continue  # malformed api_error → skip, never guess
    return None  # window exhausted without a conclusive record


def _recent_transcripts(transcripts_dir: Path, now: float) -> dict[str, Path]:
    """Main transcripts with activity inside the lookback window, keyed by sid.

    ``agent-*`` sidecars are subagent sidechains, never sessions. One directory level
    (`<munged-cwd>/<sid>.jsonl`), matching the live layout.
    """
    cutoff = now - _lookback_s()
    out: dict[str, Path] = {}
    try:
        project_dirs = [d for d in transcripts_dir.iterdir() if d.is_dir()]
    except OSError:
        return out
    for pdir in project_dirs:
        try:
            files = list(pdir.glob("*.jsonl"))
        except OSError:
            continue
        for path in files:
            if path.stem.startswith("agent-"):
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    continue
            except OSError:
                continue
            out.setdefault(path.stem, path)
    return out


# ── the session's own event stream: session_end presence + last trusted exposure ─────


def _stream_state(events_dir: Path, sid: str) -> tuple[bool, bool, dict | None]:
    """``(has_session_end, has_reconstructed_death, last_trusted_exposure)``.

    "Trusted" = a parseable event this session emitted itself (not coroner-
    reconstructed) carrying an exposure dict — the newest one wins the join.
    """
    path = events_dir / f"{sid}.jsonl"
    has_end = False
    has_recon_death = False
    last_exposure: dict | None = None
    for raw in _tail_lines(path, EVENTS_SCAN_BYTES):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        if row.get("event") == "session_end":
            has_end = True
        if row.get("event") == "death" and row.get("reconstructed"):
            has_recon_death = True
        exp = row.get("exposure")
        if isinstance(exp, dict) and not row.get("reconstructed"):
            last_exposure = exp
    return has_end, has_recon_death, last_exposure


def _join_exposure(last: dict | None) -> dict:
    """The dead session's own exposure, unjoinable fields the literal ``unknown``."""
    src = last if isinstance(last, dict) else {}
    out: dict[str, object] = {}
    for key in EXPOSURE_KEYS:
        val = src.get(key)
        out[key] = val if val is not None and key in src else UNKNOWN
    return out


# ── revival evidence: the mesh notify log ────────────────────────────────────────────


def _log_revival(mesh_log: Path, sid: str) -> str | None:
    """The timestamp of an ``autoresume-spawned`` line for this sid, or None.

    The log records ``sess=`` as the sid's first 8 chars (claude-sound.sh's log_line);
    the pane self-watch prints its wake into the PANE, not this log — those revivals
    are honestly invisible here.
    """
    token = f"sess={sid[:8]}"
    for line in reversed(_tail_lines(mesh_log, LOG_TAIL_BYTES)):
        if "autoresume-spawned" in line and token in line:
            stamp = line[:19]
            try:
                time.strptime(stamp, "%Y-%m-%d %H:%M:%S")
                return stamp
            except ValueError:
                return UNKNOWN
    return None


# ── record closure — via the load/save API, never any other mutation ─────────────────


@contextlib.contextmanager
def _pinned_env(pairs: dict[str, str]) -> Iterator[None]:
    """Pin env vars for the duration (and RESTORE) — command_run and kaizen_events
    resolve their stores from env, and an injected ``Sources`` must be authoritative."""
    saved = {k: os.environ.get(k) for k in pairs}
    try:
        os.environ.update(pairs)
        yield
    finally:
        for key, val in saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


def _command_run_save(sid: str, rec: dict) -> bool:
    """Test seam over command_run.save — the ONE sanctioned record writer."""
    if command_run is None:  # pragma: no cover - a box mid-sync
        return False
    return bool(command_run.save(sid, rec))


def _close_records(
    sources: Sources, evidence: set[str], now: float, report: CoronerReport
) -> None:
    """Close what can no longer close itself. The ONLY mutations, ever:

    - ``running`` + attributed to a death → ``state: "died"``, ``closed_by: "coroner"``
    - ``running`` + older than the TTL + NO death evidence → ``state: "expired"``,
      ``closed_by: "ttl"``

    A closed record (``done``/``blocked``/anything not ``running``) is never touched —
    the Stop hook blocks only on ``state == "running"``
    (.claude/hooks/final_gate_stop.py:482,1029,1263), so these closures un-pin without
    resurrecting anything.
    """
    if command_run is None:
        report.errors.append("command_run unavailable — record closure skipped")
        return
    try:
        record_files = sorted(sources.runs_dir.glob("*.json"))
    except OSError:
        return
    ttl = _ttl_s()
    for path in record_files:
        stem = path.stem
        # Pre-lock read is a CANDIDATE FILTER only — never the state the close trusts.
        scan = command_run.load(stem)
        if not scan or scan.get("state") != "running":
            continue
        try:
            # The close is lock-held end to end: re-load and re-check INSIDE
            # command_run._record_lock, exactly like every mutating subcommand —
            # a sibling's flocked `step`/`done` landing after the scan must survive.
            with command_run._record_lock(stem):
                rec = command_run.load(stem)
                if not rec or rec.get("state") != "running":
                    continue  # closed itself between scan and lock — never overwritten
                raw_sid = str(rec.get("session_id") or stem)
                dead = (
                    raw_sid in evidence
                    or _mesh_safe(raw_sid) in evidence
                    or stem in evidence
                )
                if dead:
                    rec["state"] = "died"
                    rec["closed_by"] = "coroner"
                else:
                    ts = rec.get("updated_ts")
                    if isinstance(ts, bool) or not isinstance(ts, (int, float)):
                        continue  # freshness unprovable → never close on it (fail open)
                    if now - float(ts) <= ttl:
                        continue  # a live busy session — untouched
                    rec["state"] = "expired"
                    rec["closed_by"] = "ttl"
                rec["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
                rec["updated_ts"] = int(now)
                if _command_run_save(stem, rec):
                    (report.records_died if dead else report.records_expired).append(raw_sid)
        except Exception as exc:
            _warn(f"record close for {stem} failed open: {exc!r}")
            continue


# ── the hole metric — for T06 ────────────────────────────────────────────────────────


def holes(sources: Sources | None = None, day: dt.date | None = None) -> int:
    """``transcripts-with-activity − sessions-with-session_end`` for one day.

    A first-class instrument-health input (spec :121-123): a transcript that was active
    on ``day`` (mtime date, local time) whose event stream never got a ``session_end``
    is a hole — a session the instrument lost. Returns the NUMBER; T06 consumes it.
    Fail-open: any error inside is a skipped session, and the function never raises.
    """
    try:
        src = sources or Sources.default()
        target = day or dt.date.today()
        active: set[str] = set()
        try:
            project_dirs = [d for d in src.transcripts_dir.iterdir() if d.is_dir()]
        except OSError:
            return 0
        for pdir in project_dirs:
            try:
                files = list(pdir.glob("*.jsonl"))
            except OSError:
                continue
            for path in files:
                if path.stem.startswith("agent-"):
                    continue  # subagent sidecars are not sessions
                try:
                    if dt.date.fromtimestamp(path.stat().st_mtime) == target:
                        active.add(path.stem)
                except (OSError, OverflowError, ValueError):
                    continue
        closed = sum(1 for sid in active if _stream_state(src.events_dir, sid)[0])
        return len(active) - closed
    except Exception as exc:
        _warn(f"holes() failed open ({exc!r}) -> 0")
        return 0


# ── the sweep ────────────────────────────────────────────────────────────────────────


def sweep(sources: Sources | None = None, now: float | None = None) -> CoronerReport:
    """One coroner pass. Never raises — a broken source is a skipped source.

    Idempotent by construction: the ``session_end`` the sweep appends is the very
    marker the next sweep skips on, and closed records are never re-mutated.
    """
    report = CoronerReport()
    try:
        src = sources or Sources.default()
        clock = float(now) if now is not None else time.time()
        with _pinned_env(
            {"KAIZEN_EVENTS_DIR": str(src.events_dir), "COMMAND_RUN_DIR": str(src.runs_dir)}
        ):
            deaths = _gather_deaths(src, clock)
            evidence = set()
            for death in deaths:
                evidence.add(death.sid)
                evidence.add(_mesh_safe(death.sid))
            # The pre-repair reading: computed BEFORE the coroner appends its own
            # session_ends, so a session dying today COUNTS as today's hole (the
            # instrument alarm) even though this very sweep then closes it.
            report.holes_today = holes(src)
            _reconstruct(src, deaths, report)
            _close_records(src, evidence, clock, report)
    except Exception as exc:
        _warn(f"sweep failed open: {exc!r}")
        report.errors.append(repr(exc))
    return report


def _find_transcript(transcripts_dir: Path, sid: str) -> Path | None:
    """Resolve a session's transcript DIRECTLY by sid, at any age — the recovery-
    overrule law must hold even after the transcript left the lookback window."""
    try:
        for pdir in transcripts_dir.iterdir():
            if not pdir.is_dir():
                continue
            candidate = pdir / f"{sid}.jsonl"
            if candidate.is_file():
                return candidate
    except OSError:
        return None
    return None


def _gather_deaths(src: Sources, now: float) -> list[_Death]:
    """Every session with death evidence: markers first, then transcript tails.

    A marker whose transcript positively shows recovery (``"alive"``) is a survivor —
    the decider clears markers on busy verdicts, but a stale one must not kill a
    session the transcript proves came back, HOWEVER OLD the transcript (resolved
    directly by sid, never through the lookback filter). A marker whose own epoch is
    older than the lookback is skipped entirely: a death older than the sweep's
    horizon is not this sweep's business. An inconclusive transcript never overrules
    a marker.
    """
    transcripts = _recent_transcripts(src.transcripts_dir, now)
    lookback = _lookback_s()
    verdicts: dict[str, _Death | str | None] = {}
    deaths: list[_Death] = []
    seen: set[str] = set()

    for safe_sid, (cls, epoch) in sorted(_errparked_markers(src.lock_dir).items()):
        if epoch is not None and now - epoch > lookback:
            continue  # aged out — must not fire forever
        tpath = transcripts.get(safe_sid) or _find_transcript(src.transcripts_dir, safe_sid)
        verdict = verdicts.setdefault(safe_sid, _tail_verdict(tpath) if tpath else None)
        if verdict == "alive":
            continue
        try:
            died_at = (
                dt.datetime.fromtimestamp(epoch).isoformat(timespec="seconds")
                if epoch
                else UNKNOWN
            )
        except (OverflowError, OSError, ValueError):
            died_at = UNKNOWN  # an absurd epoch is skipped-to-unknown, never a crash
        deaths.append(_Death(sid=safe_sid, cls=cls, key="errparked", died_at=died_at))
        seen.add(safe_sid)

    for sid, tpath in sorted(transcripts.items()):
        if sid in seen or _mesh_safe(sid) in seen:
            continue
        verdict = verdicts.get(sid)
        if verdict is None and sid not in verdicts:
            verdict = _tail_verdict(tpath)
        if isinstance(verdict, _Death):
            deaths.append(verdict)
    return deaths


def _reconstruct(src: Sources, deaths: list[_Death], report: CoronerReport) -> None:
    """Append death → (revival) → session_end to each dead session's OWN stream."""
    if kaizen_events is None:
        report.errors.append("kaizen_events unavailable — reconstruction skipped")
        return
    for death in deaths:
        has_end, has_recon, last_exposure = _stream_state(src.events_dir, death.sid)
        if has_end:
            continue  # already closed — idempotence
        joined = _join_exposure(last_exposure)
        if not has_recon:
            # A prior partial pass (crash between death and session_end) must not
            # re-append the death — but it MUST still get its session_end below.
            # sid_source="join": the coroner INFERRED this id from a marker/transcript
            # filename — the line must never claim the id was handed to it.
            ok = kaizen_events.emit(
                "death",
                sid=death.sid,
                exposure_override=joined,
                sid_source="join",
                reconstructed=True,
                key=death.key,
                died_at=death.died_at,
                **{"class": death.cls},
            )
            if not ok:
                report.errors.append(f"death emit failed for {death.sid}")
                continue
            report.deaths_reconstructed.append(death.sid)
            revived_at = _log_revival(src.mesh_log, death.sid)
            if revived_at is not None and kaizen_events.emit(
                "revival",
                sid=death.sid,
                exposure_override=joined,
                sid_source="join",
                reconstructed=True,
                revived_at=revived_at,
                **{"class": death.cls},
            ):
                report.revivals.append(death.sid)
        if kaizen_events.emit(
            "session_end",
            sid=death.sid,
            exposure_override=joined,
            sid_source="join",
            reconstructed=True,
            closed_by="coroner",
        ):
            report.session_ends.append(death.sid)


# ── duplex selftest ──────────────────────────────────────────────────────────────────


def selftest() -> int:
    """Duplex canary: the coroner CAN detect a synthetic death in a tmp fixture AND
    does NOT fire on the live-session control. Everything happens in tmp dirs — the
    real mesh, transcripts and state are never touched.
    """
    failures: list[str] = []

    def expect(cond: bool, what: str) -> None:
        if not cond:
            failures.append(what)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for sub in ("locks", "projects/-opt-x", "events", "runs"):
            (root / sub).mkdir(parents=True)
        (root / "sound.log").write_text("")
        src = Sources(
            lock_dir=root / "locks",
            mesh_log=root / "sound.log",
            transcripts_dir=root / "projects",
            events_dir=root / "events",
            runs_dir=root / "runs",
        )
        now = time.time()

        # ARM 1 — a synthetic death MUST be detected and closed.
        dead = "selftest-dead"
        marker = root / "locks" / f"{dead}.errparked"
        marker.write_text(f"rate_limit {int(now)}\n")
        marker_before = marker.read_bytes()
        (root / "runs" / f"{dead}.json").write_text(
            json.dumps({"session_id": dead, "command": "x", "state": "running",
                        "updated_ts": now - 60})
        )
        # ARM 2 — the live-session control MUST stay untouched.
        live = "selftest-live"
        (root / "projects" / "-opt-x" / f"{live}.jsonl").write_text(
            json.dumps({"type": "assistant",
                        "message": {"role": "assistant",
                                    "content": [{"type": "text", "text": "working"}]}})
            + "\n"
        )
        (root / "runs" / f"{live}.json").write_text(
            json.dumps({"session_id": live, "command": "y", "state": "running",
                        "updated_ts": now - 60})
        )

        report = sweep(src, now=now)

        expect(dead in report.deaths_reconstructed, "synthetic death must be reconstructed")
        expect(dead in report.session_ends, "synthetic death must get its session_end")
        try:
            rows = [
                json.loads(ln)
                for ln in (root / "events" / f"{dead}.jsonl").read_text().splitlines()
                if ln.strip()
            ]
        except (OSError, ValueError):
            rows = []
        expect(
            bool(rows) and all(r.get("sid_source") == "join" for r in rows),
            "every reconstructed event must carry sid_source: join (an inferred id)",
        )
        try:
            dead_rec = json.loads((root / "runs" / f"{dead}.json").read_text())
            live_rec = json.loads((root / "runs" / f"{live}.json").read_text())
        except (OSError, ValueError):
            dead_rec, live_rec = {}, {}
        expect(dead_rec.get("state") == "died", "dead record must close state=died")
        expect(dead_rec.get("closed_by") == "coroner", "dead record must be coroner-stamped")
        expect(live_rec.get("state") == "running", "live control record must stay running")
        expect(
            not (root / "events" / f"{live}.jsonl").exists(),
            "live control must get NO reconstructed events",
        )
        expect(
            marker.is_file() and marker.read_bytes() == marker_before,
            "the marker must survive the sweep BYTE-IDENTICAL (sound system is READ-ONLY)",
        )

    if failures:
        for f in failures:
            print(f"✗ selftest: {f}")
        return 1
    print(
        "✓ selftest: coroner detects the synthetic death (event + record closure) "
        "and leaves the live-session control untouched"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sweep", action="store_true", help="run one coroner pass (live sources)")
    ap.add_argument("--selftest", action="store_true", help="duplex canary in tmp fixtures")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.sweep:
        report = sweep()
        print(json.dumps(dataclasses.asdict(report), indent=1))
        return 0
    ap.print_usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
