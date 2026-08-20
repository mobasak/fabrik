#!/usr/bin/env python3
# AFTER-EDIT: tests/test_kaizen_events.py, docs/workstation/kaizen-event-stream.md | none
# CONSUMERS (re-verify on any SCHEMA/envelope change; not coupled to ordinary edits):
#   .claude/hooks/session_orient.py, .claude/hooks/final_gate_stop.py, scripts/command_run.py,
#   scripts/final_gate.py, scripts/select_rules.py, scripts/review_rubric.py,
#   scripts/sysadmin/kaizen_coroner.py, scripts/sysadmin/kaizen_collect_v2.py
"""Kaizen M1 event emitter — the typed append-only stream every sensor writes to.

WHY THIS EXISTS
---------------
v1's meter read prose (transcripts, ledger tables) and produced two instrument bugs on
its first run — a 100% failure rate from a wrong status vocabulary and a 1440-round
ledger from a naive table regex. Every one of those defects is a parsing artifact of
treating prose as data. M1 moves measurement to the SOURCE: the hooks, the run-record
machinery and the gate emit one typed JSON line per event, and the collector reads
events instead of guessing at transcripts
(docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md:54-74).

THE THREE LAWS
--------------
1. **Fail-open, always.** A broken emitter must never break a session. Every public
   function swallows every exception, reports on stderr, and returns a falsy/`unknown`
   value. :func:`emit` returns ``False`` instead of raising, and writes nothing rather
   than half a line — and on the one failure it cannot undo (a short write), it
   terminates the fragment so the damage stays confined to that single line.
2. **One file per session, one atomic append per event.** On Linux, an ``O_APPEND``
   ``write()`` to a regular file takes the inode lock, so a whole-line write cannot
   interleave with a concurrent writer's; ``MAX_LINE_BYTES`` is a defensive bound (and
   keeps lines collector-friendly), not the source of the guarantee — the atomicity is
   NOT guaranteed on NFS. Torn lines would become the unclassified-rate that
   red-instruments the loop. Oversize VALUES are clipped before serialization, so the
   line that lands is always valid JSON.
3. **Honesty over guessing.** An unresolvable session id is the literal ``unknown``
   (the collector's unclassified-rate input) and never a shared bucket merged into a
   neighbour's stream. An unmeasurable exposure field is ``unknown`` (or ``—`` for
   plan era) with no fabrication and no exception. A RECONSTRUCTED id says so:
   ``sid_source: join`` (:data:`SID_SOURCES`) — an inferred id must never be
   indistinguishable from one the session actually carried.

Box-local, stdlib only. Config via env: ``KAIZEN_EVENTS_DIR`` (default
``~/.claude/state/events/``), ``CLAUDE_SESSION_ID``, ``CLAUDE_MODEL`` /
``ANTHROPIC_MODEL``, ``CLAUDE_MESH_HEADLESS``. Event files are a DATA STORE, not a log
— this module's own failures go to stderr only, never to a logfile.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA = 1
UNKNOWN = "unknown"
NOT_MEASURED = "—"

#: How a line's ``sid`` was obtained. ``explicit``/``env``/``none`` are resolved here;
#: ``join`` is passed in by a sensor that RECONSTRUCTED the id (today: command_run.py's
#: `--adopt-sid`, which recovers it from this stream when the shell carries none). A
#: reconstructed id is neither explicit nor env, and without its own label the join would
#: have to misreport its provenance — the collector could not then tell a real session id
#: from an inferred one, which is precisely the honesty this field exists to provide.
SID_SOURCES = frozenset({"explicit", "env", "none", "join"})

#: Default bound on each ``git`` probe in :func:`exposure`. Callers on a hot path (a
#: mutation's post-save tail) pass a smaller ``probe_timeout_s``.
DEFAULT_PROBE_TIMEOUT_S = 10.0

# A defensive bound on one event, not the atomicity mechanism (that is O_APPEND's inode
# lock on a regular file). It also matches PIPE_BUF, keeps a torn-line blast radius
# small, and keeps lines comfortable for the collector to stream.
MAX_LINE_BYTES = 4096

# Bound on each candidate plan read by the exposure probe — one page, never a full file.
PLAN_HEAD_BYTES = 4096

# Default per-probe git timeout. Batch callers keep it; a caller on an interactive hot
# path (the hooks) passes `probe_timeout_s=` something small.
DEFAULT_PROBE_TIMEOUT_S = 10.0

# Progressive shrink passes: (max chars per string, max items per list/dict).
_PASSES = ((512, 200), (128, 50), (32, 10))

_SID_RE = re.compile(r"[^A-Za-z0-9_-]")
_KEY_RE = re.compile(r"[^A-Za-z0-9_]")
# Both status forms the plan corpus actually uses: `Status: IN-PROGRESS` and the bold
# `**Status:** IN-PROGRESS` (plan-set spines write the bold form).
_STATUS_RE = re.compile(r"^\*{0,2}Status:\*{0,2}[\s*`]*IN-PROGRESS", re.M)

#: Envelope keys the collector trusts. A caller field colliding with one is re-keyed —
#: `truncated`/`fields_dropped` included, even though the emitter adds them AFTER the
#: caller's fields, because a sensor claiming `truncated: false` on a clipped line would
#: make the instrument lie about itself.
_RESERVED_KEYS = frozenset(
    {"schema", "ts", "sid", "sid_source", "event", "exposure", "truncated", "fields_dropped"}
)

#: The M1 vocabulary (spec :57-63 + the coroner's `session_end`). An event outside it
#: is still written — losing data is worse than a typo — but warns on stderr so a
#: misspelled sensor is visible the day it ships.
#:
#: `stop_pass` vs `session_end`: the Stop hook fires once per TURN, so its
#: pass-through is `stop_pass` — a session-scoped "end" name would make every turn
#: look like a session ending, and session liveliness is derived from the LAST
#: `stop_pass` timestamp instead. `session_end` stays in the vocabulary for the
#: coroner's genuinely session-scoped, post-hoc close.
EVENT_TYPES = (
    "session_start",
    "stop_pass",
    "session_end",
    "run_open",
    "phase",
    "round",
    "run_close",
    "gate_run",
    "rule_activation",
    "stop_block",
    "final_block_emitted",
    "death",
    "revival",
    "operator_override",
    "fleet_health",
    "instrument_alarm",
)

_exposure_cache: dict | None = None


def _warn(msg: str) -> None:
    """stderr only — an event file is a data store, never this module's logfile."""
    try:
        print(f"kaizen_events: {msg}", file=sys.stderr)
    except Exception:  # pragma: no cover - stderr itself is gone
        pass


# ── session identity ─────────────────────────────────────────────────────────────────


def resolve_sid(explicit: str | None = None) -> str:
    """Explicit -> ``$CLAUDE_SESSION_ID`` -> ``$CLAUDE_CODE_SESSION_ID`` -> ``unknown``.

    Never a shared bucket name: an event that cannot be attributed is counted in the
    collector's unclassified-rate, not silently merged into another session's stream.
    Sanitized to the same class every mesh script uses (``[A-Za-z0-9_-]``, first 64) so
    the value in the line and the file it lands in can never diverge.
    """
    return resolve_sid_with_source(explicit)[0]


def resolve_sid_with_source(explicit: str | None = None) -> tuple[str, str]:
    """``(sid, source)`` where source is ``explicit`` | ``env`` | ``none``.

    The source is emitted with every event so residual unattributed events stay
    measurable. Bash-tool shells carry an empty ``CLAUDE_SESSION_ID`` but the harness
    exports ``CLAUDE_CODE_SESSION_ID`` (the real session uuid) — the missing second
    candidate was why every Bash-side event landed in the shared ``unknown`` bucket
    while the hooks' payload-sourced events were attributed.
    """
    try:
        for candidate, source in (
            (explicit, "explicit"),
            (os.getenv("CLAUDE_SESSION_ID", ""), "env"),
            (os.getenv("CLAUDE_CODE_SESSION_ID", ""), "env"),
        ):
            if candidate is None or not str(candidate).strip():
                continue
            sid = _safe_sid(candidate)
            # The literal `unknown` is the ABSENCE of an id, not an id: counting it as
            # an attributed source would launder unclassified events into classified.
            return (sid, "none") if sid == UNKNOWN else (sid, source)
    except Exception as exc:  # pragma: no cover - env access cannot normally fail
        _warn(f"resolve_sid failed ({exc!r}) -> {UNKNOWN}")
    return UNKNOWN, "none"


def _safe_sid(raw: object) -> str:
    """Sanitize to ``[A-Za-z0-9_-]``, INJECTIVELY.

    Sanitization alone is many-to-one — ``a/b`` and ``a.b`` both become ``a_b``, and any
    two ids sharing a 64-char prefix collapse to one stem. That would merge two live
    sessions into a single stream, exactly the honesty failure ``unknown`` exists to
    prevent. So whenever the mapping actually changed the value, a digest of the RAW id
    is appended; a clean id (the normal case) passes through untouched.
    """
    text = str(raw).strip()
    safe = _SID_RE.sub("_", text)
    if safe == text and len(safe) <= 64:
        return safe or UNKNOWN
    digest = hashlib.sha1(text.encode("utf-8", "replace"), usedforsecurity=False).hexdigest()[:8]
    return f"{safe[:55]}-{digest}"


# ── exposure ─────────────────────────────────────────────────────────────────────────


def reset_cache() -> None:
    """Drop the memoized exposure (tests, and any long-lived process that moves cwd)."""
    global _exposure_cache
    _exposure_cache = None


def exposure(
    refresh: bool = False,
    cwd: str | None = None,
    probe_timeout_s: float = DEFAULT_PROBE_TIMEOUT_S,
) -> dict:
    """Stratification metadata stamped on every event — each probe independently guarded.

    Unstamped events cannot be attributed after the fact: three accounts rotate every
    ~2 days, so the model mix changes intrinsically through the week and that drift
    would otherwise be attributed to whatever merged that day (spec :97-104).

    Fields: ``commit`` (git HEAD of the repo *cwd* resolves into), ``account`` (the
    ``~/.claude-fleet/active`` symlink target), ``model`` (env; the collector backfills
    from transcripts), ``project`` (cwd-derived ``/opt/<name>``), ``headless`` (bool),
    ``plan_era`` (newest ``IN-PROGRESS`` plan stem, else ``—``). Unmeasurable is
    ``unknown``/``—``, never a guess, never an exception.

    ``cwd`` pins the three cwd-derived probes (``commit``/``project``/``plan_era``) to a
    directory the CALLER names, via ``git -C``. A sensor that runs in a subprocess (every
    hook) has no guarantee its own process cwd is the session's project — without this it
    stamps events for project A with project B's commit, silently. ``None`` keeps the
    historical behaviour (the process cwd).

    ``probe_timeout_s`` bounds each git probe. The 10 s default suits batch callers; a
    caller sitting on an interactive hot path (the hooks, whose SessionStart budget is
    10 s TOTAL) passes something small — a hung git must cost the session milliseconds,
    not its whole budget. A non-positive or non-finite value falls back to the default.

    Memoized per process for the ``cwd=None`` call only — a cwd-pinned probe is a
    caller-specific answer that must never be served from, or poison, the shared cache.
    A later ``cwd=None`` call served from the cache runs NO probes at all, so its
    ``probe_timeout_s`` is moot — the bound applies to probes actually run, and a sensor
    that fires after a state mutation is already durable (``command_run.py``'s post-save
    flush) passes a small value and takes ``unknown`` over a stall.

    The concurrency flag is COLLECTOR-side (overlapping session windows), not here.
    """
    global _exposure_cache
    if cwd is None and _exposure_cache is not None and not refresh:
        return dict(_exposure_cache)
    timeout = _probe_timeout(probe_timeout_s)
    root = _git_toplevel(cwd, timeout)
    data = {
        "commit": _git_head(cwd, timeout),
        "account": _fleet_account(),
        "model": _model(),
        "project": _project(cwd),
        "headless": _headless(),
        "plan_era": _plan_era(root),
    }
    if cwd is None:
        _exposure_cache = data
    return dict(data)


def _probe_timeout(value: object) -> float:
    """A usable positive, finite timeout — anything else is the default.

    ``nan`` fails every comparison and ``inf`` fails the upper bound, so both fall
    through without a `math` import; a bool is an int and would silently mean 1 s.
    """
    try:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return DEFAULT_PROBE_TIMEOUT_S
        return float(value) if 0 < float(value) <= 3600 else DEFAULT_PROBE_TIMEOUT_S
    except (TypeError, ValueError):  # pragma: no cover - defence in depth
        return DEFAULT_PROBE_TIMEOUT_S


def _git(
    args: list[str], cwd: str | None = None, timeout: float = DEFAULT_PROBE_TIMEOUT_S
) -> str | None:
    """One git probe, fully guarded. ``None`` means "not measurable", never a guess.

    ``cwd`` is applied as ``git -C <dir>`` rather than a subprocess cwd: it needs no
    chdir-able parent and it survives a caller whose own cwd was deleted under it.
    """
    try:
        prefix = ["git"] if cwd is None else ["git", "-C", str(cwd)]
        out = subprocess.run(
            [*prefix, *args],
            cwd=os.getcwd() if cwd is None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        return out.stdout.strip() or None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError):
        return None
    except Exception as exc:  # pragma: no cover - defence in depth
        _warn(f"git {' '.join(args)} failed ({exc!r})")
        return None


def _git_head(cwd: str | None = None, timeout: float = DEFAULT_PROBE_TIMEOUT_S) -> str:
    return _git(["rev-parse", "HEAD"], cwd, timeout) or UNKNOWN


def _git_toplevel(cwd: str | None = None, timeout: float = DEFAULT_PROBE_TIMEOUT_S) -> Path:
    top = _git(["rev-parse", "--show-toplevel"], cwd, timeout)
    if top:
        return Path(top)
    try:
        return Path(cwd) if cwd else Path(os.getcwd())
    except OSError:  # pragma: no cover - cwd deleted under us
        return Path("/")


def _fleet_account() -> str:
    """The active account = the ``~/.claude-fleet/active`` symlink target's NAME."""
    try:
        link = Path.home() / ".claude-fleet" / "active"
        target = os.readlink(link)
        return Path(target).name or UNKNOWN
    except (OSError, ValueError):
        return UNKNOWN
    except Exception as exc:  # pragma: no cover - defence in depth
        _warn(f"account probe failed ({exc!r})")
        return UNKNOWN


def _model() -> str:
    try:
        for key in ("CLAUDE_MODEL", "ANTHROPIC_MODEL"):
            val = os.getenv(key, "").strip()
            if val:
                return val
    except Exception as exc:  # pragma: no cover - defence in depth
        _warn(f"model probe failed ({exc!r})")
    return UNKNOWN


def _project(cwd: str | None = None) -> str:
    """cwd-derived ``/opt/<name>`` — worktrees under it resolve to the same project."""
    try:
        parts = Path(cwd or os.getcwd()).resolve().parts
        if len(parts) >= 3 and parts[1] == "opt":
            return parts[2]
    except (OSError, ValueError):
        return UNKNOWN
    except Exception as exc:  # pragma: no cover - defence in depth
        _warn(f"project probe failed ({exc!r})")
    return UNKNOWN


def _headless() -> bool:
    """The mesh contract, and ONLY the mesh contract: every headless dispatch exports
    ``CLAUDE_MESH_HEADLESS``, so its absence means a human-driven session.

    There is deliberately no ``isatty()`` fallback. Hooks, cron jobs and every
    subprocess sensor read a pipe, so stdin is never a TTY there and the flag would be
    constant-true — which pools the two distributions this field exists to separate
    (spec :99-101: pooled, the loop can "improve" any metric by shifting the mix).
    """
    try:
        return bool(os.getenv("CLAUDE_MESH_HEADLESS"))
    except Exception as exc:  # pragma: no cover - env access cannot normally fail
        _warn(f"headless probe failed ({exc!r})")
        return False


def _read_head(path: Path) -> str:
    """First ``PLAN_HEAD_BYTES`` of a file, or ``""`` — a bounded read, never a slurp."""
    try:
        with open(path, "rb") as fh:
            return fh.read(PLAN_HEAD_BYTES).decode("utf-8", "replace")
    except (OSError, ValueError):
        return ""


def _plan_era(root: Path) -> str:
    """Newest ``IN-PROGRESS`` plan stem under ``docs/development/plans/``, else ``—``.

    Stems are date-prefixed, so the lexical MAX over the matching stems is the newest —
    never the first match in directory order. Candidates are plain plans and plan-SET
    SPINES only (``<dir>/<same-stem>.md``, the gate-enforced shape) — never a set's
    ``T##`` ticket files, whose stems sort ABOVE every dated stem and would otherwise
    hijack the era. ``archived/`` never counts. Both ``Status:`` and ``**Status:**``
    count. Each candidate costs ONE bounded read (``PLAN_HEAD_BYTES``) — this probe sits
    on every session's cold path, so a 100 KiB plan must never cost a full read.
    """
    try:
        plans = root / "docs" / "development" / "plans"
        if not plans.is_dir():
            return NOT_MEASURED
        candidates = list(plans.glob("*.md"))
        candidates += [d / f"{d.name}.md" for d in plans.iterdir() if d.is_dir()]
        best = ""
        for path in candidates:
            if "archived" in path.parts or path.stem <= best:
                continue
            head = _read_head(path)
            if head and _STATUS_RE.search(head):
                best = path.stem
        return best or NOT_MEASURED
    except (OSError, ValueError):
        return NOT_MEASURED
    except Exception as exc:  # pragma: no cover - defence in depth
        _warn(f"plan_era probe failed ({exc!r})")
        return NOT_MEASURED


# ── line assembly ────────────────────────────────────────────────────────────────────


class _Clipper:
    """Clips VALUES (never the serialized line) so the JSON is always well-formed."""

    def __init__(self, chars: int, items: int) -> None:
        self.chars = chars
        self.items = items
        self.hit = False

    def val(self, v: object, depth: int = 0) -> object:
        if v is None or isinstance(v, (bool, int, float)):
            return v
        if isinstance(v, str):
            return self._clip(v)
        if depth >= 4:
            return self._clip(str(v))
        if isinstance(v, dict):
            items = list(v.items())
            if len(items) > self.items:
                self.hit = True
                items = items[: self.items]
            return {self._clip(str(k)): self.val(x, depth + 1) for k, x in items}
        if isinstance(v, (list, tuple, set)):
            items = list(v)
            if len(items) > self.items:
                self.hit = True
                items = items[: self.items]
            return [self.val(x, depth + 1) for x in items]
        return self._clip(str(v))

    def _clip(self, s: str) -> str:
        if len(s) > self.chars:
            self.hit = True
            return s[: self.chars]
        return s


def _free_key(key: str, payload: dict) -> str:
    """Rescue a caller key that collides with the envelope by prefixing ``f_``.

    The prefix LOOPS: a caller sending both ``schema`` and ``f_schema`` must lose
    neither, and a single-shot prefix would silently overwrite whichever was placed
    first. Bounded so a pathological payload cannot spin.
    """
    for _ in range(8):
        if key not in payload and key not in _RESERVED_KEYS:
            return key
        key = f"f_{key}"
    return f"{key}_{len(payload)}"


def build_line(event: str, sid: str, sid_source: str, fields: dict, exp: dict) -> str:
    """The exact bytes one event appends (without its newline).

    Guaranteed: valid JSON, ASCII-only (so ``len(str) == len(bytes)``), and
    ``len(line) + 1 <= MAX_LINE_BYTES``. Caller fields never shadow the envelope — a
    ``schema=``/``event=`` kwarg is re-keyed with an ``f_`` prefix, so a sensor can
    never forge the fields the collector trusts.
    """
    core = {
        "schema": SCHEMA,
        "ts": dt.datetime.now(dt.UTC).isoformat(timespec="milliseconds"),
        "sid": sid,
        "sid_source": sid_source,
        "event": str(event)[:64],
    }
    for chars, items in _PASSES:
        clip = _Clipper(chars, items)
        payload = dict(core)
        payload["exposure"] = clip.val(exp)
        for raw_key, value in fields.items():
            payload[_free_key(_KEY_RE.sub("_", str(raw_key))[:64] or "field", payload)] = clip.val(
                value
            )
        if clip.hit:
            payload["truncated"] = True
        line = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str)
        if len(line) + 1 <= MAX_LINE_BYTES:
            return line
    # Last resort: the envelope alone, honestly labelled. An event whose fields cannot
    # be made to fit is still worth its timestamp, type and exposure. Exposure is kept
    # REAL (hard-clipped) and degrades to the literal `unknown` only if even that
    # overflows — a fabricated exposure dict would be a lie the collector cannot see.
    minimal = dict(core)
    minimal["exposure"] = _Clipper(64, 8).val(exp)
    minimal["truncated"] = True
    minimal["fields_dropped"] = True
    line = json.dumps(minimal, ensure_ascii=True, separators=(",", ":"), default=str)
    if len(line) + 1 <= MAX_LINE_BYTES:
        return line
    minimal["exposure"] = UNKNOWN
    return json.dumps(minimal, ensure_ascii=True, separators=(",", ":"), default=str)


def events_dir() -> Path:
    return Path(os.getenv("KAIZEN_EVENTS_DIR", str(Path.home() / ".claude" / "state" / "events")))


def emit(
    event: str,
    sid: str | None = None,
    *,
    exposure_override: dict | None = None,
    sid_source: str | None = None,
    probe_timeout_s: float | None = None,
    **fields: object,
) -> bool:
    """Append ONE JSON line to ``$KAIZEN_EVENTS_DIR/<sid>.jsonl``. Never raises.

    Returns ``True`` when the line landed, ``False`` on ANY failure — a caller must be
    able to write ``kaizen_events.emit(...)`` on its hot path with no try/except and no
    behaviour change when the whole stream is broken.

    ``exposure_override`` is keyword-only (a dict passed positionally is a caller field
    mistake, never an override) and **producer-restricted**: a post-hoc producer (the coroner,
    reconstructing a `death` from a session that is already gone) passes the exposure it
    joined from that session's own last trusted events, and it REPLACES the resolved
    one verbatim rather than stamping the coroner's own process. It is a parameter, not
    a caller field, so it is never ``f_``-re-keyed; anything that is not a dict is
    ignored in favour of the live exposure.

    ``sid_source`` is keyword-only and provenance-restricted the same way: a sensor that
    RECONSTRUCTED the id (``command_run.py``'s ``--adopt-sid`` join) passes ``"join"`` so
    the line does not claim the id was handed to it. It is validated against
    :data:`SID_SOURCES`; anything else warns and keeps the RESOLVED source, because an
    unvetted label would silently open a new bucket in every collector query.

    ``probe_timeout_s`` bounds the exposure probe's ``git`` calls for a caller on a hot
    path; ``None`` keeps :data:`DEFAULT_PROBE_TIMEOUT_S`. Both are parameters, so neither
    can reach the payload as a caller field.
    """
    try:
        if event not in EVENT_TYPES:
            _warn(f"unknown event type {event!r} (emitted anyway)")
        resolved, source = resolve_sid_with_source(sid)
        if sid_source is not None:
            if sid_source in SID_SOURCES:
                source = sid_source
            else:
                _warn(f"invalid sid_source {sid_source!r} — keeping the resolved {source!r}")
        if isinstance(exposure_override, dict):
            exp = exposure_override
        elif probe_timeout_s is None:
            exp = exposure()
        else:
            exp = exposure(probe_timeout_s=probe_timeout_s)
        line = build_line(event, resolved, source, fields, exp)
        directory = events_dir()
        directory.mkdir(parents=True, exist_ok=True)
        payload = line.encode("ascii", "replace") + b"\n"
        # O_APPEND: the whole-line write is atomic against concurrent appenders.
        # O_NOFOLLOW: an event file is a data store the collector trusts — a symlink
        # planted at that path would redirect appends anywhere this process can write,
        # so the open fails and the emit fails open like any other error.
        fd = os.open(
            directory / f"{resolved}.jsonl",
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
            0o600,
        )
        try:
            written = os.write(fd, payload)
            if written != len(payload):
                _terminate_torn_line(fd, written, len(payload), event)
                return False
        finally:
            os.close(fd)
        return True
    except Exception as exc:
        _warn(f"emit({event!r}) failed, session unharmed: {exc!r}")
        return False


def _terminate_torn_line(fd: int, written: int, total: int, event: str) -> None:
    """Close a short write with a newline so the damage stays ONE line.

    A short write cannot be undone: every byte past ours belongs to concurrent
    appenders, so truncating would eat THEIR events. Terminating the fragment turns it
    into a single unclassified line the collector drops, instead of a fragment the next
    event is glued onto — which would cost two events instead of one.
    """
    _warn(f"short write ({written}/{total}) for {event}; terminating the fragment")
    try:
        os.write(fd, b"\n")
    except OSError as exc:
        _warn(f"could not terminate the torn line: {exc!r}")


# ── duplex selftest ──────────────────────────────────────────────────────────────────


def selftest() -> int:
    """Duplex canary: prove the emitter BOTH lands a good event AND fails open.

    A one-way test cannot tell a working emitter from one that silently writes nothing
    — the M0 lesson (a green predicate that never fired) applied to the emitter itself.
    """
    failures: list[str] = []

    def expect(cond: bool, what: str) -> None:
        if not cond:
            failures.append(what)

    with tempfile.TemporaryDirectory() as tmp:
        # Every env var this canary mutates is saved here and restored in the finally —
        # the selftest is importable, so leaking `CLAUDE_SESSION_ID` out of it would
        # silently re-attribute every later emit in the SAME process.
        prior_env = {
            k: os.environ.get(k)
            for k in ("KAIZEN_EVENTS_DIR", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID")
        }
        os.environ["KAIZEN_EVENTS_DIR"] = tmp
        try:
            # GOOD: the event lands, parses, and carries the envelope + exposure.
            expect(emit("session_start", sid="selftest", probe="ok"), "good emit must return True")
            path = Path(tmp) / "selftest.jsonl"
            expect(path.is_file(), "good emit must create the per-session file")
            raw = path.read_bytes() if path.is_file() else b""
            expect(len(raw.splitlines()) == 1, "good emit must write exactly one line")
            expect(len(raw) <= MAX_LINE_BYTES, "good emit must stay within PIPE_BUF")
            try:
                row = json.loads(raw.decode().splitlines()[0]) if raw else {}
            except (ValueError, IndexError):
                row = {}
            expect(row.get("schema") == SCHEMA, "good emit must carry the schema version")
            expect(row.get("event") == "session_start", "good emit must carry its event type")
            expect(row.get("sid") == "selftest", "good emit must carry its sid")
            expect(isinstance(row.get("exposure"), dict), "good emit must carry exposure")

            # GOOD: an oversize value is clipped, and the line still parses.
            expect(
                emit("round", sid="selftest", note="z" * 40000), "oversize emit must return True"
            )
            lines = path.read_bytes().splitlines()
            expect(len(lines) == 2, "oversize emit must append exactly one line")
            try:
                big = json.loads(lines[-1].decode())
            except ValueError:
                big = {}
            expect(big.get("truncated") is True, "oversize emit must mark itself truncated")
            expect(len(lines[-1]) + 1 <= MAX_LINE_BYTES, "oversize line must fit PIPE_BUF")

            # BAD: an injected write failure returns False and leaves NO partial line.
            before = path.read_bytes()
            real_write = os.write

            def _boom(fd: int, data: bytes) -> int:
                raise OSError(28, "injected: no space left on device")

            os.write = _boom  # type: ignore[assignment]
            try:
                expect(emit("death", sid="selftest") is False, "injected failure must return False")
            finally:
                os.write = real_write  # type: ignore[assignment]
            expect(path.read_bytes() == before, "injected failure must leave no partial line")

            # BAD: an unresolvable sid is `unknown`, in its OWN file.
            os.environ.pop("CLAUDE_SESSION_ID", None)
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
            expect(emit("stop_block", cause="selftest"), "unknown-sid emit must return True")
            unknown_path = Path(tmp) / f"{UNKNOWN}.jsonl"
            expect(unknown_path.is_file(), "unknown sid must land in its own unknown.jsonl")
            expect(path.read_bytes() == before, "unknown sid must not touch another stream")

            # BAD: a symlinked event file is refused rather than followed.
            link = Path(tmp) / "linked.jsonl"
            target = Path(tmp) / "outside.jsonl"
            target.write_bytes(b"")
            link.symlink_to(target)
            expect(emit("phase", sid="linked") is False, "a symlinked event file must be refused")
            expect(target.read_bytes() == b"", "a refused emit must not write through the link")
        finally:
            for key, value in prior_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            reset_cache()

    if failures:
        for f in failures:
            print(f"✗ selftest: {f}")
        return 1
    print("✓ selftest: emitter lands good events, fails open on injected failure, never tears")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true", help="duplex canary (good + injected-bad)")
    ap.add_argument("--exposure", action="store_true", help="print the resolved exposure as JSON")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.exposure:
        print(json.dumps(exposure(), indent=1, ensure_ascii=False))
        return 0
    ap.print_usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
