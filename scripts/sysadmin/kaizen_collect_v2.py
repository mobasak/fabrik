#!/usr/bin/env python3
# AFTER-EDIT: tests/test_kaizen_collect_v2.py, tests/fixtures/kaizen-golden/ | none
"""Kaizen M1 collector v2 — derived facts, versioned metrics, paired-counter registry.

WHY THIS REPLACES kaizen_collect.py / kaizen_metrics.py
--------------------------------------------------------
v1 read prose (transcripts, ledger tables) and produced two instrument bugs on its first
run — parsing artifacts of treating prose as data. v2 reads the TYPED event stream the
M1 sensors write (docs/workstation/kaizen-event-stream.md) and proves itself before its
numbers are believed (spec 2026-08-16-kaizen-closed-loop-v2-design.md:82-111):

- **Derived-facts law**: each session is parsed ONCE into a compact one-row JSONL store
  (``derived-facts.jsonl``); history recomputes from rows, never a re-parse. A session is
  re-derived only at a ``FACTS_VERSION`` bump — the store is append-only, so the old
  rows stay alongside the new. **The growth carve-out**: "re-derived ONLY at version
  bump" governs COMPLETED sessions, whose files never change. A file that GROWS onto a
  later day — the ``unknown.jsonl`` accumulator (which grows forever) and any resumed
  session — is re-derived on that later day into a NEW appended row (the row key is
  ``(sid, facts_version, day)``), so growth is reflected instead of frozen at the first
  derivation; ``read_rows`` serves the latest row per sid while history stays verbatim.
  A same-version, same-day re-run remains a byte-identical no-op.
- **Versioned definitions**: every metric carries a version + definition hash; a
  definition change writes a NEW series file (``series/<metric>@v<N>.jsonl``) — a
  published series is never overwritten.
- **Paired counters as a schema constraint**: a metric definition without a
  ``counter_metric`` naming another registered metric REFUSES to load (raises).
- **Golden corpus before publish**: the collector derives the hand-labelled corpus in
  ``tests/fixtures/kaizen-golden/`` and asserts the expected counts BEFORE publishing
  anything. On mismatch it exits non-zero, emits an ``instrument_alarm`` event,
  publishes NOTHING, and the daily kaizen-log row renders ``—`` (reason
  ``instrument red: golden mismatch`` on stderr + the hand-off mail). Instrument health
  is metric zero.

THE HONESTY RULE (inherited, binding)
-------------------------------------
An unmeasurable metric renders ``—`` with its reason — never a fabricated 0. A torn or
malformed event line is counted in the unclassified rate WITH a reason code — never a
crash, never a silent skip. A line whose ``sid_source`` is ``none`` but whose ``sid`` is
not ``unknown`` (or vice versa) is a provenance anomaly and lands there too — the
collector never guesses. The concurrency flag is DEFINED as: two sessions overlap iff
their [first-event-ts, last-event-ts] windows intersect AND their ``exposure.project``
values are equal; a session missing ``project`` is EXCLUDED from the computation and
counted in the unclassified rate.

Config via env (all state dirs created lazily; tests point every one at tmp):
``KAIZEN_EVENTS_DIR`` (default ``~/.claude/state/events``), ``KAIZEN_STATE_DIR``
(default ``~/.claude/state/kaizen``), ``KAIZEN_GOLDEN_DIR`` (default this repo's
``tests/fixtures/kaizen-golden``). Box-local, stdlib only.
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import dataclasses
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import kaizen_events  # T01 emitter — same directory; used only for the alarm event
except Exception:  # pragma: no cover - a box mid-sync
    kaizen_events = None  # type: ignore[assignment]

REPO = Path(__file__).resolve().parents[2]
#: v2 (review fix-wave 2026-08-21): death_classes list (every death kept), truncated
#: lines counted envelope-only, malformed-field reason codes, events_unattributed on
#: the unknown row. v3 (fix-wave 2, same day): the gate dict splits the NON-check side
#: out (``runs_noncheck`` / ``failed_checks_noncheck``) so the failure taxonomy can
#: exclude diagnostic --check runs (W2-F1, the L5 rationale). The derived-row shape
#: changed, so the version bumps and the golden corpus is re-labelled — the
#: derived-facts law.
FACTS_VERSION = 3
SCHEMA = 1
DASH = "—"
UNKNOWN = "unknown"
#: :func:`_windowed_unattributed`'s unknowable CAUSES (W5-2) — the verdict rides back as
#: ``(None, cause)`` so every consumer prints the TRUE cause, never a blanket claim.
UNATTR_SHRUNK = "shrunk"
UNATTR_PRE_V3 = "pre-v3-absent"
UNATTR_BUMP_GAP = "bump-day-gap"
UNATTR_BOOTSTRAP = "bootstrap"
GOLDEN_MISMATCH_REASON = "instrument red: golden mismatch"
#: The era this collector's metrics are DEFINED over. T08's backfill appends
#: ``era: "transcript"`` rows to the SAME store (dash-string fields — honest ``—``,
#: not dicts); every metric input read in :func:`daily` excludes them, or
#: :func:`compute_metrics` crashes on the dashes. ``read_rows`` itself stays
#: era-blind — T08's noise-floor report needs both eras from it.
ERA_EVENT = "event"

#: Sanctioned run_close verdicts (docs/workstation/kaizen-event-stream.md § vocabulary).
RUN_CLOSE_VERDICTS = frozenset({"done", "blocked"})
#: stop_block causes that are premature-stop shaped: the agent tried to end the turn
#: while a run record was still live, or while promising undispatched work.
PREMATURE_CAUSES = frozenset({"run-record", "promise-stall"})

# The kaizen-log table columns, verbatim from kaizen_metrics.py — the daily upsert must
# not reshape the shipped tables. Cells 1..5 are mechanical; 6..7 are the analyst's.
COLUMNS = (
    "Date",
    "Gate first-pass rate",
    "Death-classes /wk",
    "Lesson-class recurrence",
    "Review rounds /plan",
    "Missed crons",
    "Top friction fixed",
    "Filed (spec/mail)",
)
_ANALYST_CELLS = (6, 7)


def _warn(msg: str) -> None:
    """stderr only — event/series files are data stores, never this module's log."""
    try:
        print(f"kaizen_collect_v2: {msg}", file=sys.stderr)
    except Exception:  # pragma: no cover - stderr itself is gone
        pass


# ── store roots (env-overridable; created lazily) ─────────────────────────────────────


def events_dir() -> Path:
    return Path(os.getenv("KAIZEN_EVENTS_DIR", "") or (Path.home() / ".claude/state/events"))


def state_dir() -> Path:
    return Path(os.getenv("KAIZEN_STATE_DIR", "") or (Path.home() / ".claude/state/kaizen"))


def golden_dir() -> Path:
    return Path(os.getenv("KAIZEN_GOLDEN_DIR", "") or (REPO / "tests/fixtures/kaizen-golden"))


def facts_path(state: Path | None = None) -> Path:
    return (state or state_dir()) / "derived-facts.jsonl"


def series_path(metric: str, version: int, state: Path | None = None) -> Path:
    return (state or state_dir()) / "series" / f"{metric}@v{version}.jsonl"


# ── line-level parsing — every predicate lands a malformed line in the unclassified
#    rate with a reason code, never a crash, never a silent skip ──────────────────────


def parse_line(raw: str, file_stem: str) -> tuple[dict | None, str | None]:
    """``(event_row, None)`` for a good line, ``(None, reason_code)`` otherwise —
    with ONE dual case: a clipped line (``truncated``/``fields_dropped``) returns
    ``(row, "truncated")``, both non-None, so the caller can count its intact
    ENVELOPE while refusing its partial payload (M1)."""
    if not raw.strip():
        return None, "blank-line"
    try:
        row = json.loads(raw)
    except ValueError:
        return None, "unparseable-json"
    if not isinstance(row, dict):
        return None, "not-an-object"
    if file_stem == UNKNOWN:
        # The unknown bucket is many sessions' unattributable lines merged by design —
        # deriving session facts from it would fabricate a session that never existed.
        return None, "unattributable-sid"
    if row.get("schema") != SCHEMA:
        return None, "unsupported-schema"
    event = row.get("event")
    if not isinstance(event, str) or not event:
        return None, "missing-event"
    sid = row.get("sid")
    if not isinstance(sid, str) or not sid:
        return None, "missing-sid"
    if sid != file_stem:
        return None, "sid-file-mismatch"
    sid_source = row.get("sid_source")
    if not isinstance(sid_source, str):
        return None, "missing-sid-source"
    # Consumer-side provenance honesty: `none` means "no id was resolvable", so it and
    # the literal `unknown` sid must travel together — a split is an anomaly, never a
    # guess (T03/T05 review forward note).
    if (sid_source == "none") != (sid == UNKNOWN):
        return None, "provenance-anomaly"
    ts = row.get("ts")
    if not isinstance(ts, str):
        return None, "invalid-ts"
    try:
        dt.datetime.fromisoformat(ts)
    except ValueError:
        return None, "invalid-ts"
    if row.get("truncated") or row.get("fields_dropped"):
        # M1: a clipped line parses, but its caller-field payload is PARTIAL — feeding
        # it into a distribution metric would count a fragment as the whole (a clipped
        # 120-check gate_run would land as a 50-check taxonomy). The envelope
        # (event/ts/exposure) is intact and still counts; the payload never does. The
        # ROW rides back with the reason so the caller can do envelope-only counting.
        return row, "truncated"
    reason = _check_typed(event, row)
    if reason:
        return None, reason
    return row, None


def _check_typed(event: str, row: dict) -> str | None:
    """Type-specific duplex predicates — each has a good and a malformed fixture."""
    if event == "gate_run":
        checks = row.get("checks")
        if not isinstance(row.get("status"), str) or not isinstance(checks, list):
            return "malformed-gate_run"
        for c in checks:
            if not (
                isinstance(c, dict)
                and isinstance(c.get("name"), str)
                and isinstance(c.get("outcome"), str)
            ):
                return "malformed-gate_run"
    elif event == "run_close":
        if row.get("verdict") not in RUN_CLOSE_VERDICTS:
            return "unknown-run_close-verdict"
    elif event == "death":
        cls = row.get("class")
        if not isinstance(cls, str) or not cls:
            return "malformed-death"
    elif event == "round":
        n = row.get("n")
        if isinstance(n, bool) or not isinstance(n, int):
            return "malformed-round"
    return None


# ── session derivation — one compact row per session ─────────────────────────────────


def _project_of(row: dict) -> str | None:
    exp = row.get("exposure")
    if isinstance(exp, dict):
        proj = exp.get("project")
        if isinstance(proj, str) and proj and proj != UNKNOWN:
            return proj
    return None


def derive_session(path: Path, day: str | None = None) -> dict | None:
    """Parse ONE session event file into its derived-facts row. Fail-open per line:
    a torn line is counted in ``unclassified_reasons``, never a crash. Returns ``None``
    only when the FILE itself is unreadable (warned — the hole metric owns lost files).
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        _warn(f"unreadable session file {path.name}: {exc!r} — skipped (rides hole_count)")
        return None

    events: collections.Counter[str] = collections.Counter()
    events_unattr: collections.Counter[str] = collections.Counter()
    reasons: collections.Counter[str] = collections.Counter()
    projects: collections.Counter[str] = collections.Counter()
    stop_causes: collections.Counter[str] = collections.Counter()
    failed_checks: collections.Counter[str] = collections.Counter()
    failed_checks_noncheck: collections.Counter[str] = collections.Counter()
    gate_runs = 0
    gate_runs_noncheck = 0
    gate_pass = 0
    gate_fail = 0
    first_status: str | None = None
    opened = 0
    done = 0
    done_evidenced = 0
    blocked = 0
    rounds_max = 0
    death_classes: list[str] = []
    first_dt: dt.datetime | None = None
    last_dt: dt.datetime | None = None

    def _window(row: dict) -> None:
        nonlocal first_dt, last_dt
        when = dt.datetime.fromisoformat(str(row["ts"]))
        first_dt = when if first_dt is None or when < first_dt else first_dt
        last_dt = when if last_dt is None or when > last_dt else last_dt

    for raw in lines:
        row, reason = parse_line(raw, path.stem)
        if reason is not None:
            reasons[reason] += 1
            if row is not None:
                # A truncated line (M1): the ENVELOPE is intact — the event name,
                # timestamps and exposure count; the partial payload never feeds a
                # metric below.
                events[str(row["event"])] += 1
                _window(row)
                proj = _project_of(row)
                if proj:
                    projects[proj] += 1
            elif reason == "unattributable-sid":
                # H3 input: the unknown bucket cannot make session facts, but its
                # event NAMES are envelope truth — the attribution-honesty guard
                # needs to know which numerator families sit here unattributable.
                with contextlib.suppress(ValueError):
                    obj = json.loads(raw)
                    name = obj.get("event") if isinstance(obj, dict) else None
                    if isinstance(name, str) and name:
                        events_unattr[name] += 1
            continue
        if row is None:  # pragma: no cover - parse_line never returns (None, None)
            continue
        event = str(row["event"])
        events[event] += 1
        _window(row)
        proj = _project_of(row)
        if proj:
            projects[proj] += 1
        if event == "gate_run":
            gate_runs += 1
            status = str(row.get("status"))
            # L5: a --check run (the Stop hook's automatic --lean --check self-review
            # included) is diagnostic, never the session's FIRST ATTEMPT — only a
            # non-check run may define first_status. A missing mode is a pre-mode
            # emitter line and counts (it cannot be proven a check run).
            mode = row.get("mode")
            is_check = isinstance(mode, dict) and bool(mode.get("check"))
            if not is_check:
                gate_runs_noncheck += 1
            if first_status is None and not is_check:
                first_status = status
            if status == "success":
                gate_pass += 1
            else:
                gate_fail += 1
            for c in row.get("checks") or []:
                if c.get("outcome") == "fail":
                    failed_checks[str(c.get("name"))] += 1
                    if not is_check:
                        # W2-F1: the failure taxonomy's population — a --check
                        # run's fails are diagnostic, never taxonomy (L5 rationale).
                        failed_checks_noncheck[str(c.get("name"))] += 1
        elif event == "run_open":
            opened += 1
        elif event == "run_close":
            if row.get("verdict") == "done":
                done += 1
                ev = row.get("evidence_hash")
                if isinstance(ev, str) and ev:
                    done_evidenced += 1
                elif ev is not None:
                    # M8: a present-but-malformed evidence hash is an instrument
                    # defect, counted — never silently "unevidenced".
                    reasons["malformed-evidence_hash"] += 1
            else:
                blocked += 1
        elif event == "round":
            rounds_max = max(rounds_max, int(row["n"]))
        elif event == "stop_block":
            cause = row.get("cause")
            if isinstance(cause, str) and cause:
                stop_causes[cause] += 1
            else:
                # M8: cause is a required field of stop_block — missing or
                # non-string is counted, never a silent drop.
                reasons["malformed-stop_block-cause"] += 1
        elif event == "death":
            death_classes.append(str(row["class"]))

    return {
        "facts_version": FACTS_VERSION,
        "sid": path.stem,
        "day": day,
        "derived_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        # Fixed millisecond width (the emitter's own format) — bare isoformat() drops
        # the fraction at microsecond==0 and equal instants then compare unequal.
        "first_ts": first_dt.isoformat(timespec="milliseconds") if first_dt else None,
        "last_ts": last_dt.isoformat(timespec="milliseconds") if last_dt else None,
        # The MAJORITY label across the session's events; an equal-count tie breaks to
        # the lexicographically first name — deterministic, never insertion order.
        "project": (min(projects.items(), key=lambda kv: (-kv[1], kv[0]))[0] if projects else None),
        "events": dict(events),
        # Envelope event-name counts of the UNKNOWN bucket's lines (empty for every
        # attributed session) — the attribution-honesty guard's input (H3/M5).
        "events_unattributed": dict(events_unattr),
        "gate": {
            "runs": gate_runs,
            "first_status": first_status,
            "pass": gate_pass,
            "fail": gate_fail,
            "failed_checks": dict(failed_checks),
            # The NON-check side (W2-F1): the taxonomy's population. A pre-mode
            # emitter line counts here too (it cannot be proven a check run) — the
            # same disposition first_status takes.
            "runs_noncheck": gate_runs_noncheck,
            "failed_checks_noncheck": dict(failed_checks_noncheck),
        },
        "runs": {
            "opened": opened,
            "done": done,
            "done_evidenced": done_evidenced,
            "blocked": blocked,
            "rounds_max": rounds_max,
        },
        "stop_causes": dict(stop_causes),
        # Every death class, in order of occurrence (M9) — a session can die more
        # than once (death -> revival -> death) and each class is data.
        "death_classes": death_classes,
        "concurrent": None,
        "concurrent_reason": None,
        "lines_total": len(lines),
        "lines_unclassified": sum(reasons.values()),
        "unclassified_reasons": dict(reasons),
    }


def derive_batch(paths: list[Path], day: str | None = None) -> list[dict]:
    """Derive every session in the batch and stamp the concurrency flag.

    Two sessions overlap iff their [first_ts, last_ts] windows intersect AND their
    ``exposure.project`` values are EQUAL (spec :100-102). A session missing project
    (or the unknown bucket, or one with no parseable timestamps) is EXCLUDED — flag
    ``None`` with its reason — and counts in the unclassified rate, never guessed.
    """
    rows = [r for r in (derive_session(p, day) for p in paths) if r is not None]
    eligible: list[tuple[dict, dt.datetime, dt.datetime, str]] = []
    for row in rows:
        if row["sid"] == UNKNOWN:
            row["concurrent_reason"] = "unattributable-sid"
        elif not row["project"]:
            row["concurrent_reason"] = "missing exposure.project"
        elif not row["first_ts"] or not row["last_ts"]:
            row["concurrent_reason"] = "no parseable timestamps"
        else:
            eligible.append(
                (
                    row,
                    dt.datetime.fromisoformat(row["first_ts"]),
                    dt.datetime.fromisoformat(row["last_ts"]),
                    str(row["project"]),
                )
            )
    for row, lo, hi, proj in eligible:
        row["concurrent"] = any(
            other is not row and oproj == proj and olo <= hi and lo <= ohi
            for other, olo, ohi, oproj in eligible
        )
    return rows


# ── the derived-facts store — append-only JSONL, re-derived only at version bump ─────


@contextlib.contextmanager
def _store_lock(target: Path) -> Iterator[None]:
    """EXCLUSIVE inter-process lock over a read-keys→append seam (L6).

    ``O_APPEND`` keeps each individual write atomic, but the DEDUP decision — read
    the known keys, then append what is missing — is two steps: a daily run and a
    backfill racing it both read "absent" and both append. flock on a sibling
    ``.lock`` file serializes the whole seam; closing the fd releases it, and a
    crashed holder's lock dies with its process (flock, not a stale lockfile
    protocol)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(f"{target}.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _iter_facts(state: Path) -> Iterator[dict]:
    path = facts_path(state)
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except ValueError:
                    _warn("torn derived-facts line skipped (append-only store, never repaired)")
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def _row_era(row: dict) -> str:
    """The row's era STRING — a missing/empty ``era`` is the event era (rows the
    collector itself derived predate the field; see :func:`_event_era`)."""
    era = row.get("era")
    return era if isinstance(era, str) and era else ERA_EVENT


def known_fact_keys(state: Path | None = None) -> set[tuple[str, int, str | None, str]]:
    """``(sid, facts_version, derived day, era)`` tuples already in the store.

    The day is part of the key (the growth carve-out): a completed session's file
    never grows, so it is derived once — but a file that DOES grow onto a later day
    (the ``unknown`` accumulator, a resumed session) derives AGAIN on that day into a
    NEW appended row. A same-version, same-day re-run stays a no-op.

    The ERA is part of the key too (W4-3): the eras carry INDEPENDENT version
    constants (``FACTS_VERSION`` here, T08's ``TRANSCRIPT_FACTS_VERSION``), so an
    era-blind key let a live v1 EVENT row at ``(sid, 1, day)`` silently mask the
    transcript derivation at the same triple — two different derivations, one key."""
    st = state or state_dir()
    out: set[tuple[str, int, str | None, str]] = set()
    for row in _iter_facts(st):
        sid, ver = row.get("sid"), row.get("facts_version")
        day = row.get("day")
        if isinstance(sid, str) and isinstance(ver, int):
            out.add((sid, ver, day if isinstance(day, str) else None, _row_era(row)))
    return out


def _fact_key(row: dict) -> tuple[str, int, str | None, str]:
    day = row.get("day")
    return (
        str(row.get("sid")),
        int(row.get("facts_version", 0)),
        day if isinstance(day, str) else None,
        _row_era(row),
    )


def append_facts(rows: list[dict], state: Path | None = None) -> int:
    """Append rows not already present at their (sid, facts_version, day). Append-only:
    nothing is ever rewritten; a version bump — or a later derivation day for a file
    that grew — appends NEW rows alongside the old. The key is enforced against the
    call's OWN batch too: a duplicate inside one call appends exactly once. The whole
    read-keys→append seam runs under :func:`_store_lock` (L6) — two processes racing
    the same key must land it exactly once."""
    st = state or state_dir()
    with _store_lock(facts_path(st)):
        known = known_fact_keys(st)
        fresh: list[dict] = []
        for r in rows:
            key = _fact_key(r)
            if key in known:
                continue
            known.add(key)
            fresh.append(r)
        if not fresh:
            return 0
        st.mkdir(parents=True, exist_ok=True)
        with open(facts_path(st), "a", encoding="utf-8") as fh:
            for row in fresh:
                fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        return len(fresh)


def _event_era(row: dict) -> bool:
    """True for event-era rows — a missing/empty ``era`` IS event era (rows the
    collector itself derived predate the field). T09 era filter (T08's standing
    finding): transcript rows land in the current week for real, and their dash
    strings crash :func:`compute_metrics`."""
    return row.get("era", ERA_EVENT) in (ERA_EVENT, "", None)


def _parse_ts(value: object) -> dt.datetime | None:
    """ISO string → aware datetime (naive assumed UTC); anything else → None."""
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed


def read_rows(
    since: str | None = None, state: Path | None = None, event_era_only: bool = False
) -> list[dict]:
    """Rows for T07/T08: the LATEST appended row per sid at its newest
    ``facts_version`` (a grown file's later-day re-derivation supersedes the earlier
    row; history stays verbatim in the store), optionally filtered to
    ``last_ts >= since``.

    ``event_era_only`` applies the era filter BEFORE the latest-per-sid collapse
    (W2-F7): a transcript-era row (T08 backfill) that outranks its event-era sibling
    must not swallow the sid — filtering the collapsed result loses the event row
    entirely. The default stays era-blind for T08's noise-floor report.

    Timestamps are compared as PARSED datetimes (naive assumed UTC) — string
    comparison misorders equal instants of different fraction widths. Disposition of
    the edge rows under a ``since`` filter, documented: a row whose ``last_ts`` is a
    corrupt/unparseable STRING is INCLUDED with a stderr warn (silent exclusion would
    vanish data invisibly); a row whose ``last_ts`` is None (the session had no
    parseable event timestamps — already a recorded fact in its unclassified reasons)
    is excluded, since it cannot satisfy a time filter and its timelessness is
    visible in the unfiltered read.

    ⚠️ Ranking reconciliation (deliberate divergence from :func:`predecessors` —
    do not "clean up" by aligning them): THIS seam ranks ``(facts_version, day)``
    because it answers "what is the CURRENT state of this sid?" — the newest schema's
    row is the authoritative one even when a backfill gave it an earlier day.
    ``predecessors`` ranks ``(day, facts_version)`` because it answers "what was
    already counted BEFORE day X?" — a chronological baseline. For a sid holding
    A=v1/day-10 and B=v2/day-3 (a backfilled higher-version, earlier-day row), this
    function serves B while ``predecessors("day-11")`` serves A — both correct for
    their consumer; pinned by test_dual_ranking_divergence_is_intentional."""
    st = state or state_dir()

    def rank(r: dict) -> tuple[int, str]:
        # Max facts_version first, then max DAY — append order is only the tie-break
        # within the same (sid, version, day). An out-of-order backfill (an earlier
        # day appended after a later one) must never shadow the later day's row.
        day = r.get("day")
        return (int(r.get("facts_version", 0)), day if isinstance(day, str) else "")

    best: dict[str, dict] = {}
    for row in _iter_facts(st):
        sid = row.get("sid")
        if not isinstance(sid, str):
            continue
        if event_era_only and not _event_era(row):
            continue  # W2-F7: filter BEFORE the collapse — see the docstring
        cur = best.get(sid)
        if cur is None or rank(row) >= rank(cur):
            best[sid] = row
    rows = sorted(best.values(), key=lambda r: str(r.get("sid")))
    if since is None:
        return rows
    bound = _parse_ts(since)
    if bound is None:
        _warn(f"read_rows: unparseable since={since!r} — filter ignored, all rows returned")
        return rows
    out: list[dict] = []
    for r in rows:
        raw = r.get("last_ts")
        if raw is None:
            continue  # timeless row — visible unfiltered, cannot satisfy a time filter
        when = _parse_ts(raw)
        if when is None:
            _warn(
                f"read_rows: row {r.get('sid')!r} has unparseable last_ts={raw!r} — "
                "included under the since filter rather than silently vanished"
            )
            out.append(r)
            continue
        if when >= bound:
            out.append(r)
    return out


# ── the publish seam: per-day deltas over cumulative rows ────────────────────────────
#
# Store rows are CUMULATIVE by design (derive_session re-parses the whole file, and the
# growth carve-out re-derives grown files on later days). The published day series must
# never re-count a line already counted in an earlier published day — so the delta
# happens HERE, at the publish seam, never in the store: a day's metric input is the
# row minus its predecessor (same sid + facts_version, the latest earlier day).

#: (container key, count field names) — every additive count that is delta'd.
_DELTA_SCALARS: tuple[tuple[str | None, tuple[str, ...]], ...] = (
    (None, ("lines_total", "lines_unclassified")),
    ("gate", ("runs", "pass", "fail", "runs_noncheck")),
    ("runs", ("opened", "done", "done_evidenced", "blocked")),
)
#: (container key or None, counter-map field name) — additive {name: count} maps.
_DELTA_MAPS: tuple[tuple[str | None, str], ...] = (
    (None, "events"),
    (None, "events_unattributed"),
    (None, "unclassified_reasons"),
    (None, "stop_causes"),
    ("gate", "failed_checks"),
    ("gate", "failed_checks_noncheck"),
)


def _get_in(row: dict, container: str | None, field: str) -> object:
    src = row.get(container) or {} if container else row
    return src.get(field) if isinstance(src, dict) else None


def _int_in(row: dict, container: str | None, field: str) -> int:
    val = _get_in(row, container, field)
    if isinstance(val, bool) or not isinstance(val, int):
        return 0
    return val


def _measured_int(row: dict, container: str | None, field: str) -> int | None:
    """The field's value when the row MEASURED it — ``None`` when absent, ``None``,
    or non-int. The root law's reading primitive: absence is "not measured",
    never 0 — a v1 row that predates a field did not observe a zero of it."""
    val = _get_in(row, container, field)
    if isinstance(val, bool) or not isinstance(val, int):
        return None
    return val


def _gate_noncheck(row: dict) -> int | None:
    """``gate.runs_noncheck`` when MEASURED and sane — ``None`` otherwise.

    Enforces the non-check ⊆ all invariant (``runs_noncheck <= runs``): a row
    claiming more non-check runs than total runs is instrument-corrupt (the round-3
    probe published mypy=8 over runs_noncheck=30 while runs=4) — warned and treated
    as unmeasurable, never consumed."""
    rn = _measured_int(row, "gate", "runs_noncheck")
    if rn is None:
        return None
    rt = _measured_int(row, "gate", "runs")
    if rt is not None and rn > rt:
        _warn(
            f"invariant violated: {row.get('sid')!r} claims gate.runs_noncheck={rn} > "
            f"gate.runs={rt} (non-check ⊆ all) — the non-check side is treated as "
            "unmeasurable for this row"
        )
        return None
    return rn


def _sub_map(cur: object, prev: object) -> dict | None:
    """Per-key counter subtraction; None on any negative (the file shrank)."""
    cur_d = cur if isinstance(cur, dict) else {}
    prev_d = prev if isinstance(prev, dict) else {}
    out: dict[str, int] = {}
    for name in set(cur_d) | set(prev_d):
        diff = int(cur_d.get(name, 0)) - int(prev_d.get(name, 0))
        if diff < 0:
            return None
        if diff:
            out[str(name)] = diff
    return out


def delta_row(cur: dict, prev: dict | None) -> dict | None:
    """The per-day view of a possibly-cumulative row: ``cur`` minus its predecessor.

    No predecessor → the row IS the day's delta. Any negative difference means the
    file SHRANK (rotation/truncation — growth is monotone by construction): warn and
    return None, so that sid publishes NOTHING that day — never a negative.

    **THE ROOT LAW (fix-wave 3): a delta is only computable against a baseline that
    MEASURED the same field.** A field the predecessor never carried (absent or
    ``None`` — a v1/v2 row across a FACTS_VERSION bump) has NO baseline: treating it
    as 0 published the full cumulative value as "that day's" delta (the round-3
    probe: taxonomy mypy=8 over runs_noncheck=30 while the day's real runs delta was
    4). Such a field is marked ``None`` in the delta row — UNMEASURABLE — and every
    consumer treats a ``None`` field as not-measured for that row (excluded from
    numerator AND denominator, counted as a per-metric bump-day gap). The bump day
    goes honestly quiet per-field instead of lying. A field measured by NEITHER row
    stays absent (neither schema knew it).

    ``death_classes`` IS delta'd (W6-1): the store list is append-ordered ("every
    death class, in order of occurrence"), so the day's NEW classes are the suffix
    beyond the predecessor's length — never the lifetime list (the "0 occ / 2 cls"
    mixed-semantics shape). A shorter current list is a shrink (publish nothing);
    a baseline that never measured the list is a root-law ``None``.

    Non-additive fields are point-in-time, not deltas: ``gate.first_status`` is kept
    only when the predecessor had not already recorded one (a session's first NON-check
    attempt counts once, on the day it appeared — a predecessor whose runs were all
    ``--check`` has ``first_status: None`` and has NOT consumed the first attempt, L5);
    ``rounds_max``/``concurrent``/window timestamps carry the current row's values.
    """
    if prev is None:
        out = dict(cur)  # the store row is never mutated
        out["delta_of"] = None  # the key is part of the shape — null on a first-ever row
        return out
    out = json.loads(json.dumps(cur))  # deep copy — the store row is never mutated

    def _dst(container: str | None) -> dict:
        if container is None:
            return out
        node = out.get(container)
        if not isinstance(node, dict):
            node = {}
            out[container] = node
        return node

    for container, fields in _DELTA_SCALARS:
        for field in fields:
            cur_val = _measured_int(cur, container, field)
            prev_val = _measured_int(prev, container, field)
            if cur_val is None and prev_val is None:
                continue  # neither row's schema measured the field — stays absent
            if cur_val is None or prev_val is None:
                # ROOT LAW: one side measured, the other did not — no baseline, no
                # delta. None, never a 0-baselined cumulative value.
                _dst(container)[field] = None
                continue
            diff = cur_val - prev_val
            if diff < 0:
                _warn(
                    f"delta_row: {cur.get('sid')!r} shrank ({container or 'row'}.{field} "
                    f"went backwards) — publishing NOTHING for it this day"
                )
                return None
            _dst(container)[field] = diff
    for container, field in _DELTA_MAPS:
        cur_map = _get_in(cur, container, field)
        prev_map = _get_in(prev, container, field)
        if not isinstance(cur_map, dict) and not isinstance(prev_map, dict):
            continue  # neither row's schema measured the map — stays absent
        if not isinstance(cur_map, dict) or not isinstance(prev_map, dict):
            _dst(container)[field] = None  # ROOT LAW — same as the scalar case
            continue
        diff_map = _sub_map(cur_map, prev_map)
        if diff_map is None:
            _warn(
                f"delta_row: {cur.get('sid')!r} shrank ({field} lost entries) — "
                "publishing NOTHING for it this day"
            )
            return None
        _dst(container)[field] = diff_map
    cur_dc = cur.get("death_classes")
    prev_dc = prev.get("death_classes")
    if isinstance(cur_dc, list) and isinstance(prev_dc, list):
        if len(cur_dc) < len(prev_dc):
            _warn(
                f"delta_row: {cur.get('sid')!r} shrank (death_classes lost entries) — "
                "publishing NOTHING for it this day"
            )
            return None
        # W6-1: the day's NEW classes — the in-order suffix beyond the baseline.
        out["death_classes"] = cur_dc[len(prev_dc) :]
    elif isinstance(cur_dc, list) or isinstance(prev_dc, list):
        out["death_classes"] = None  # ROOT LAW — one side measured, no baseline
    prev_gate = prev.get("gate") or {}
    if prev_gate.get("first_status") is not None:
        gate_dst = _dst("gate")
        gate_dst["first_status"] = None
        # W5-4: this null means CONSUMED (the predecessor already recorded the
        # session's first attempt — out of the population BY DESIGN), not
        # unmeasured. The marker lets consumers tell the two apart: without it, a
        # consumed row whose non-check split also gapped (runs_noncheck None) was
        # miscounted as a bump-day gap. Root-law-safe: the marker is set only
        # where the suppression provably fired; its absence claims nothing.
        gate_dst["first_status_consumed"] = True
    out["delta_of"] = prev.get("day")
    return out


def predecessors(before_day: str, state: Path | None = None) -> dict[str, dict]:
    """The latest earlier-day row per sid — at ANY facts_version — strictly before
    ``before_day``: the subtraction base for that day's publish.

    Cross-version baseline (the chosen design, option (a)): a FACTS_VERSION bump on a
    still-growing file (the ``unknown`` accumulator is the standing case) must not
    republish the full cumulative row as the bump day's delta — within one published
    series, no line is counted twice. So the predecessor lookup ignores the version
    boundary and subtracts the latest earlier-day row whatever version derived it.
    Why (a) over the conservative blank-the-bump-day (b): the accumulator grows EVERY
    day, so (b) would dark a day of the instrument-health series precisely at every
    schema migration; and the additive COUNT fields are the stable core of the row
    schema — a bump that changes count semantics owes a golden-corpus re-label (the
    pre-publish gate), and at runtime a cross-version subtraction that goes NEGATIVE
    darkens that sid's day AND raises the instrument_alarm event (the darkening alarm
    in daily()) — the visible protections for exactly that case. Caveat, stated:
    bump-day deltas subtract across schema versions.

    Selection per sid: max (day, facts_version).

    ⚠️ Ranking reconciliation (deliberate divergence from :func:`read_rows` — do not
    "clean up" by aligning them): THIS seam is chronological — a day-delta must
    subtract the latest CALENDAR baseline, whatever schema version derived it, or the
    delta re-counts days a differently-versioned row already published. ``read_rows``
    ranks ``(facts_version, day)`` instead, because its question is current state and
    there the newest schema wins. For a sid holding A=v1/day-10 and B=v2/day-3,
    ``read_rows`` serves B while this baseline for day-11 is A — both correct for
    their consumer; pinned by test_dual_ranking_divergence_is_intentional."""
    st = state or state_dir()
    out: dict[str, dict] = {}
    for row in _iter_facts(st):
        if not _event_era(row):
            continue  # a transcript-era row is never a delta baseline (T09 era filter)
        sid, ver, day = row.get("sid"), row.get("facts_version"), row.get("day")
        if not (isinstance(sid, str) and isinstance(ver, int) and isinstance(day, str)):
            continue
        if day >= before_day:
            continue
        cur = out.get(sid)
        if cur is None or (str(cur.get("day") or ""), int(cur.get("facts_version", 0))) <= (
            day,
            ver,
        ):
            out[sid] = row
    return out


def read_week_rows(
    week: tuple[int, int], state: Path | None = None, event_era_only: bool = False
) -> list[dict]:
    """The latest row per sid WITHIN one ISO week — the per-week CUMULATIVE view
    (L1). Since W5-5 the weekly LOG call reads :func:`window_delta_rows` instead
    (a cumulative row leaks lifetime mass into a week-scoped message); this reader
    remains the inspection seam for per-week cumulative state.

    The global latest-per-sid collapse (:func:`read_rows`) answers "current state";
    filtering IT by week drops a sid whose newest row moved to a later week, silently
    vacating that sid's earlier week. The weekly read collapses PER WEEK instead:
    only rows whose ``day`` falls in the week compete, ranked ``(facts_version, day)``
    with append order as the final tie-break, exactly like :func:`read_rows`.
    ``event_era_only`` filters BEFORE the collapse, same rationale (W2-F7)."""
    st = state or state_dir()

    def rank(r: dict) -> tuple[int, str]:
        day = r.get("day")
        return (int(r.get("facts_version", 0)), day if isinstance(day, str) else "")

    best: dict[str, dict] = {}
    for row in _iter_facts(st):
        sid, day = row.get("sid"), row.get("day")
        if not isinstance(sid, str) or not isinstance(day, str):
            continue
        if _iso_week(day) != week:
            continue
        if event_era_only and not _event_era(row):
            continue  # W2-F7: filter BEFORE the collapse
        cur = best.get(sid)
        if cur is None or rank(row) >= rank(cur):
            best[sid] = row
    return sorted(best.values(), key=lambda r: str(r.get("sid")))


# ── the metric registry — paired counters are a SCHEMA constraint ─────────────────────

#: The root-law population sentence shared by every delta-consuming formula (v3
#: bump, fix-wave 3): part of each formula string, so it is def-hashed.
_BUMP_GAP_SENTENCE = (
    " Root law: a row field measured with no same-field baseline in its delta "
    "predecessor (a version-bump day) is unmeasurable — the row leaves numerator "
    "AND denominator and is counted as a bump-day gap."
)

METRIC_DEFS: tuple[dict, ...] = (
    {
        "id": "rules_compliance",
        # v3 (fix-wave 3): root-law population — bump-day-gap rows excluded.
        # v4 (fix-wave 4, W4-4): the gap gate is scoped to CONSUMED fields — an
        # events-map gap this metric never reads no longer drops its row (the
        # population widened, so the version bumps).
        "version": 4,
        "counter_metric": "terminator_spam",
        "formula": (
            "run_close events with verdict done AND a non-empty evidence_hash / all "
            "run_close events (denominator = run-record closures). Coroner/TTL closures "
            "emit no run_close; they ride hole_count. Renders — when attributed "
            "run_close occurrences are below the 20% attribution floor of the family "
            "total (the unknown stream holds the mass) — an attributed sliver is not "
            "the population. Gap gate scoped to consumed fields: this metric reads "
            "runs.* baselines only, so an events-map bump-day gap gaps its counter "
            "(which consumes the events map), never this metric." + _BUMP_GAP_SENTENCE
        ),
    },
    {
        "id": "terminator_spam",
        # v3 (fix-wave 3): root-law population — bump-day-gap rows excluded.
        "version": 3,
        "counter_metric": "rules_compliance",
        "formula": (
            "final_block_emitted events / run-record closures — above 1.0 means task "
            "terminators were emitted without a matching closed run. Renders — under "
            "the same 20% run_close attribution floor as rules_compliance (the pair "
            "dashes together)." + _BUMP_GAP_SENTENCE
        ),
    },
    {
        "id": "premature_stop_rate",
        # v2: the derived-row input population changed under the 2026-08-21 fix wave
        # (malformed stop_block causes counted, truncated lines envelope-only) — the
        # same def_hash must never span differently-populated points in one series.
        # v3 (fix-wave 3): root-law population — bump-day-gap rows excluded.
        "version": 3,
        "counter_metric": "first_attempt_gate_pass",
        "formula": (
            "stop_block events with cause in {run-record, promise-stall} / all stop "
            "verdicts (stop_pass + stop_block)." + _BUMP_GAP_SENTENCE
        ),
        # NOT part of the def hash (versioned-definitions law: _def_hash bases on
        # id/version/formula/counter_metric only) — descriptive cross-reference:
        "cross_reference": (
            "EVENT-level (share of stop VERDICTS premature). Its SESSION-level "
            "sibling is premature_stop (T07, kaizen_outcomes.py): sessions with a "
            "premature-cause stop_block over sessions with any stop verdict. Same "
            "PREMATURE_CAUSES vocabulary, different unit — read them together."
        ),
    },
    {
        "id": "first_attempt_gate_pass",
        # v3 (fix-wave 3): the continuing-sessions annotation keys on MEASURED
        # non-check runs (S8) + root-law population.
        "version": 3,
        "counter_metric": "premature_stop_rate",
        "formula": (
            "sessions whose FIRST attributed NON-check gate_run (mode.check false — "
            "the Stop hook's automatic --lean --check self-review never defines a "
            "first attempt) has status success / sessions whose first such run fell "
            "in the window. Unattributed gate_runs sit in the unknown bucket and "
            "ride unclassified_rate. The '(continuing sessions only)' annotation "
            "keys on measured runs_noncheck, never unsplit gate.runs — a check-only "
            "session is not a continuing one." + _BUMP_GAP_SENTENCE
        ),
    },
    {
        "id": "gate_failure_taxonomy",
        # v3 (fix-wave 3): S7 — the attribution guard's attributed operand is the
        # NON-check occurrence count (same population as the value); the non-check
        # ⊆ all invariant is enforced; root-law population.
        "version": 3,
        "counter_metric": "rule_activation",
        "formula": (
            "per-check fail counts across attributed NON-check gate_run events "
            "(mode.check false — the Stop hook's automatic --lean --check "
            "self-review is diagnostic, never taxonomy population; the L5 "
            "rationale). The value is the {check: count} distribution, not a "
            "scalar. Renders — when attributed NON-check gate_run occurrences (the "
            "guard's operands come from the SAME population as the value) are below "
            "the 20% attribution floor of the family total (the unknown stream "
            "holds the mass) — an attributed sliver is not the population. A row "
            "claiming runs_noncheck > runs violates non-check ⊆ all and is "
            "unmeasured (warned)." + _BUMP_GAP_SENTENCE
        ),
    },
    {
        "id": "rule_activation",
        # v3 (fix-wave 3): root-law population — bump-day-gap rows excluded.
        "version": 3,
        "counter_metric": "gate_failure_taxonomy",
        "formula": (
            "sessions with >=1 attributed rule_activation event / sessions with >=1 "
            "run-record closure. Labelled INVOCATION-TIME activation (select_rules / "
            "rubric runs) — per-edit glob firing is an M2 residual, not measured here. "
            "Renders — when attributed rule_activation occurrences are below the 20% "
            "attribution floor of the family total (sensor events unattributable in "
            "the unknown stream) — never a fabricated 0%." + _BUMP_GAP_SENTENCE
        ),
    },
    {
        "id": "unclassified_rate",
        # v3 (fix-wave 3): root-law population — bump-day-gap rows excluded.
        "version": 3,
        "counter_metric": "hole_count",
        "formula": (
            "unclassified lines (torn/malformed/truncated, PLUS the unknown stream's "
            "lines via their unattributable-sid reason) / total event lines observed. "
            "Sessions missing exposure.project are a STRATIFICATION gap (concurrency-"
            "excluded, visible in concurrent_reason), not instrument unhealth — they "
            "count in neither term. Instrument health, metric zero." + _BUMP_GAP_SENTENCE
        ),
    },
    {
        "id": "hole_count",
        # v3 (fix-wave 3): the W2-F3 population change (a BLIND sweep is None → —,
        # never a measured-looking 0) ships with its owed version bump (S5).
        "version": 3,
        "counter_metric": "unclassified_rate",
        "formula": (
            "kaizen_coroner.holes(): transcripts-with-activity minus sessions with a "
            "stop_pass OR session_end for the day — the documented liveliness "
            "semantics (a normally-ended session's liveliness is its last stop_pass; "
            "session_end is the coroner's post-hoc close). A BLIND probe (missing/"
            "unreadable transcripts dir, crashed sweep) is None → the cell renders "
            "— with the reason, never a measured-looking 0. Instrument health, "
            "metric zero."
        ),
    },
    {
        "id": "death_occurrences",
        # v1 (fix-wave 6, W6-1): the death cell's day series — the weekly log cell
        # aggregates PUBLISHED day points, never a row recompute.
        "version": 1,
        "counter_metric": "death_classes",
        "formula": (
            "attributed death events summed over the day's delta rows (envelope "
            "count — a truncated death line still counts). Measurable only on a day "
            "whose rows carry coroner evidence (a death or session_end event): a 0 "
            "without evidence would fabricate a coroner that never ran (M9, "
            "day-scoped). Attribution-floor guarded like every event-family metric. "
            "The weekly log cell is the SUM of the ISO week's published day values — "
            "the single-source law: weekly cells aggregate the published day series."
            + _BUMP_GAP_SENTENCE
        ),
    },
    {
        "id": "death_classes",
        # v1 (fix-wave 6, W6-1): the class half of the death cell's day series.
        "version": 1,
        "counter_metric": "death_occurrences",
        "formula": (
            "the {class: count} distribution of the day's NEW death classes — the "
            "delta suffix of the session's in-order death_classes list beyond its "
            "predecessor's length, never the lifetime list (a legacy v1 scalar "
            "death_class coerces to a one-element list). Paired with "
            "death_occurrences: occurrence volume must never hide class breadth, "
            "and vice versa. Same coroner-evidence measurability gate and "
            "attribution floor as its pair. The weekly log cell MERGES the ISO "
            "week's published day maps (classes unioned, counts summed) — the "
            "single-source law." + _BUMP_GAP_SENTENCE
        ),
    },
)


def _def_hash(d: dict) -> str:
    basis = {k: d[k] for k in ("id", "version", "formula", "counter_metric")}
    return hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()


def validate_registry(defs: tuple[dict, ...] | list[dict]) -> dict[str, dict]:
    """Load metric definitions. REFUSES (raises ValueError) any definition without a
    ``counter_metric`` naming ANOTHER registered metric — a schema constraint, not a
    convention. Every returned definition carries its ``hash``."""
    by_id: dict[str, dict] = {}
    for d in defs:
        mid = d.get("id")
        if not isinstance(mid, str) or not mid:
            raise ValueError("metric definition without an id")
        if mid in by_id:
            raise ValueError(f"duplicate metric definition: {mid}")
        if not isinstance(d.get("version"), int) or not isinstance(d.get("formula"), str):
            raise ValueError(f"metric {mid}: version (int) and formula (str) are required")
        by_id[mid] = dict(d)
    for mid, d in by_id.items():
        counter = d.get("counter_metric")
        if not isinstance(counter, str) or not counter:
            raise ValueError(
                f"metric {mid} has no counter_metric — unpaired definitions REFUSE to load"
            )
        if counter == mid:
            raise ValueError(f"metric {mid} names itself as its counter — not a pair")
        if counter not in by_id:
            raise ValueError(f"metric {mid} pairs with unregistered counter {counter!r}")
    for mid, d in by_id.items():
        counter = str(d["counter_metric"])
        back = by_id[counter].get("counter_metric")
        if back != mid:
            raise ValueError(
                f"metric {mid} pairs with {counter}, but {counter} pairs with {back!r} — "
                "counter pairs must be reciprocal (a cycle is not a pair)"
            )
        d["hash"] = _def_hash(d)
    return by_id


def registry() -> dict[str, dict]:
    """The validated M1 registry — for T07/T08."""
    return validate_registry(METRIC_DEFS)


# ── metric computation — honesty first ────────────────────────────────────────────────


@dataclasses.dataclass
class MetricResult:
    """One computed metric. ``cell`` is ``—`` (with ``reason``) when unmeasurable."""

    id: str
    cell: str
    detail: str = ""
    measurable: bool = True
    value: object = None
    numerator: int | None = None
    denominator: int | None = None

    @classmethod
    def unavailable(cls, mid: str, reason: str) -> MetricResult:
        return cls(id=mid, cell=DASH, detail=reason, measurable=False)


def _pct(num: int, den: int) -> str:
    return f"{100 * num / den:.0f}% ({num}/{den})"


#: The attribution-honesty floor (H3/M5): when a metric's numerator event family sits
#: mostly in the UNKNOWN stream, the attributed sliver is not the population —
#: publishing it would fabricate precision (a 0% rule_activation while every
#: rule_activation event is unattributable; an n=1 rules_compliance against 38
#: unknown closures). Below this attributed share the metric renders ``—`` with the
#: reason. The floor is part of the affected metrics' formulas (def-hashed, v2).
ATTRIBUTED_MIN_SHARE = 0.2


def _unattributed_count(rows: list[dict], names: tuple[str, ...]) -> int | None:
    """Sum of the unknown-stream envelope counts for ``names`` — or ``None`` when
    ANY row carries an explicit ``events_unattributed: None`` (root law: the field
    was measured by the current row but had no same-field baseline in its
    predecessor — the window's unattributed count is then UNKNOWABLE, a bump-day
    gap, never 0). A row that predates the field entirely (absent) contributes 0 —
    the pre-field era genuinely observed nothing here."""
    total = 0
    for r in rows:
        if "events_unattributed" in r and r["events_unattributed"] is None:
            return None
        ev = r.get("events_unattributed")
        if isinstance(ev, dict):
            total += sum(int(ev.get(n, 0) or 0) for n in names)
    return total


def _attribution_guard(
    rows: list[dict], names: tuple[str, ...], attributed: int, what: str
) -> str | None:
    """``None`` when attribution is trustworthy, else the ``—`` reason (H3/M5)."""
    unattributed = _unattributed_count(rows, names)
    if unattributed is None:
        return (
            f"{what} attribution share unmeasurable this window — bump-day gap: "
            "events_unattributed was measured with no same-field baseline in a "
            "predecessor row"
        )
    if unattributed <= 0:
        return None
    total = attributed + unattributed
    if attributed / total < ATTRIBUTED_MIN_SHARE:
        return (
            f"{what} unattributable — {attributed} attributed vs {unattributed} in "
            f"the unknown stream (below the {ATTRIBUTED_MIN_SHARE:.0%} attribution floor)"
        )
    return None


def _rows_by_sid_day(state: Path | None = None) -> dict[str, dict[str, dict]]:
    """Event-era store rows keyed ``sid → day → row`` (latest ``facts_version`` per
    (sid, day)) — the windowed delta seams' shared index (W5-1). Every sid's rows
    are DAY-KEYED since H1 (the growth carve-out re-derives grown files each day
    they grew), so consecutive rows subtract into per-day deltas exactly like the
    published series."""
    st = state or state_dir()
    out: dict[str, dict[str, dict]] = {}
    for row in _iter_facts(st):
        if not _event_era(row):
            continue
        sid, day = row.get("sid"), row.get("day")
        if not isinstance(sid, str) or not isinstance(day, str):
            continue
        by_day = out.setdefault(sid, {})
        cur = by_day.get(day)
        if cur is None or int(row.get("facts_version", 0) or 0) >= int(
            cur.get("facts_version", 0) or 0
        ):
            by_day[day] = row
    return out


def _unknown_rows_by_day(state: Path | None = None) -> dict[str, dict]:
    """The UNKNOWN accumulator's store rows keyed by day (latest ``facts_version``
    per day, event-era only) — the windowed-attribution seam's input (W4-1)."""
    return _rows_by_sid_day(state).get(UNKNOWN, {})


def window_delta_rows(days: list[str], state: Path | None = None) -> list[dict]:
    """The window's day-scoped DELTA rows for EVERY sid — attributed sessions AND
    the unknown accumulator alike (W5-1: like with like, everywhere).

    For each sid, each store row whose ``day`` falls in ``days`` is delta'd against
    the sid's nearest EARLIER row (any ``facts_version`` — the chronological-
    baseline law :func:`predecessors` states) via :func:`delta_row`, so a lifetime
    session contributes only its in-window GROWTH. The root law rides along:
    absent-field baselines come out ``None`` per field, and a shrink publishes
    nothing for that (sid, day) — warned by delta_row, exactly like the day series.
    A row with no earlier row at all IS its own delta (``delta_of: None``).

    This is the ONE population every windowed consumer measures over — the
    published value and its attribution guard describe the same window, built from
    the same rows with the same semantics. Rows come back sorted (sid, day); a sid
    may contribute several rows (one per in-window derivation day)."""
    window = set(days)
    out: list[dict] = []
    for _sid, by_day in sorted(_rows_by_sid_day(state).items()):
        days_sorted = sorted(by_day)
        for i, day in enumerate(days_sorted):
            if day not in window:
                continue
            prev = by_day[days_sorted[i - 1]] if i > 0 else None
            delta = delta_row(by_day[day], prev)
            if delta is not None:
                out.append(delta)
    return out


def _windowed_unattributed(
    rows_by_day: dict[str, dict], families: tuple[str, ...], window: list[str]
) -> tuple[int | None, str | None]:
    """The WINDOW's unattributed event mass for ``families`` — ``(total, None)``
    when knowable, ``(None, cause)`` when not (W4-1 + W5-2: the cause travels so
    every consumer prints the TRUE reason, never a blanket claim).

    The unknown accumulator's lines are timeless, but its store rows are DAY-KEYED
    (H1), so a windowed count IS computable: the sum of the accumulator's per-day
    DELTAS over the window days — the published-series delta seam, reusing
    :func:`delta_row` (each in-window unknown row minus its nearest earlier unknown
    row; a day with no unknown row published no delta and contributes nothing —
    its growth, if any, rides the next derived row's delta, landing in whatever
    window that row's day falls in, exactly as the series would publish it).

    Unknowable causes — ``(None, cause)``, never a guess:

    - :data:`UNATTR_SHRUNK` — the accumulator went BACKWARDS against its baseline
      (rotation/truncation); the window's mass is unknowable.
    - :data:`UNATTR_PRE_V3` — an in-window row's ``events_unattributed`` is ABSENT
      (a pre-v3 row: the field was never measured; absent ≠ 0, the root law).
    - :data:`UNATTR_BUMP_GAP` — the field came out ``None`` (measured with no
      same-field baseline in its predecessor — the bump-day gap).
    - :data:`UNATTR_BOOTSTRAP` (W5-3) — the accumulator's FIRST-EVER derivation
      lands in-window carrying family mass: its "delta" is the whole cumulative
      row, i.e. pre-window backlog dumped on one day — the split is unknowable,
      so the first window after store bootstrap is expected unmeasurable.
      FAMILY-SCOPED: a bootstrap row whose family mass is 0 dumped nothing for
      that family and contributes a knowable 0.

    A store with no unknown rows at all measured nothing unattributable — a
    knowable ``(0, None)``."""
    if not rows_by_day:
        return 0, None  # fresh store: no unknown stream has ever been derived
    days_sorted = sorted(rows_by_day)
    total = 0
    for day in sorted(window):
        row = rows_by_day.get(day)
        if row is None:
            continue  # no delta published for this day — nothing lands in-window here
        prev_day = None
        for d in days_sorted:
            if d >= day:
                break
            prev_day = d
        delta = delta_row(row, rows_by_day[prev_day] if prev_day is not None else None)
        if delta is None:
            return None, UNATTR_SHRUNK
        if "events_unattributed" not in delta:
            return None, UNATTR_PRE_V3
        ev = delta["events_unattributed"]
        if not isinstance(ev, dict):
            return None, UNATTR_BUMP_GAP
        mass = sum(int(ev.get(n, 0) or 0) for n in families)
        if delta.get("delta_of") is None and mass > 0:
            return None, UNATTR_BOOTSTRAP  # W5-3: first derivation carries backlog
        total += mass
    return total, None


def unattributed_unknowable_reason(cause: str | None, what: str) -> str:
    """The human sentence for a ``(None, cause)`` windowed-unattributed verdict —
    both consumers (the log's rounds cell, the outcome tier's guard) print the
    TRUE cause (W5-2), never a blanket "pre-v3" claim."""
    if cause == UNATTR_SHRUNK:
        return (
            f"window attribution share unmeasurable (unknown accumulator shrank) — "
            f"{what}: an in-window unknown-accumulator row went backwards against "
            "its baseline (rotation/truncation) — the window's unattributed mass "
            "is unknowable"
        )
    if cause == UNATTR_BUMP_GAP:
        return (
            f"window attribution share unmeasurable (bump-day gap) — {what}: an "
            "unknown-accumulator row in the window measured events_unattributed "
            "with no same-field baseline in its predecessor (root law)"
        )
    if cause == UNATTR_BOOTSTRAP:
        return (
            f"window attribution share unmeasurable — bootstrap window: the unknown "
            f"accumulator's first derivation carries pre-window backlog ({what}; "
            "the first window after store bootstrap is expected unmeasurable)"
        )
    return (
        f"window attribution share unmeasurable (pre-v3 rows in window) — {what}: "
        "an unknown-accumulator row in the window lacks a same-field "
        "events_unattributed baseline (absent ≠ 0, root law)"
    )


def compute_metrics(
    rows: list[dict], holes: int | None = None, holes_reason: str = "no hole source provided"
) -> dict[str, MetricResult]:
    """Compute the M1 registered set over derived-facts rows. Every unmeasurable
    metric is ``—`` with its reason — never a fabricated 0.

    ROOT LAW consumption: a ``None`` field on a row (a delta with no same-field
    baseline — see :func:`delta_row`) means that row is NOT MEASURED for any metric
    needing the field: it leaves numerator AND denominator and is counted into the
    metric's per-metric bump-day gap, stated in the detail/reason."""
    out: dict[str, MetricResult] = {}
    gaps: collections.Counter[str] = collections.Counter()

    def _gap_note(mid: str) -> str:
        n = gaps.get(mid, 0)
        if not n:
            return ""
        if mid == "first_attempt_gate_pass":
            # W5-4: these rows were never IN the population, so "excluded" would
            # overclaim — they are simply unmeasurable for this metric this window.
            return f"; {n} row(s) unmeasurable this window — bump-day gap"
        return (
            f"; {n} row(s) excluded — bump-day gap (a field measured with no "
            "same-field baseline is unmeasurable, root law)"
        )

    def esum(name: str) -> int:
        return sum(int((r.get("events") or {}).get(name, 0)) for r in rows)

    def _events_gap(r: dict) -> bool:
        return "events" in r and r["events"] is None

    # ── the run-record pair ──────────────────────────────────────────────────────
    # W4-4: the gap gates are SPLIT per consumed fields — rules_compliance reads
    # runs.* only, so an events-map gap it never consumes must not drop its
    # fully-measured row; terminator_spam additionally reads
    # events.final_block_emitted and keeps the events gate on top of the runs gate.
    closures = 0
    evidenced = 0
    ts_closures = 0
    blocks = 0
    blocks_seen = 0
    for r in rows:
        ev_map = r.get("events")
        if isinstance(ev_map, dict):
            # W4-5: blocks OBSERVED anywhere — the "no closures" message must never
            # fabricate "(0 terminator block(s) seen)" while excluded gap rows saw
            # blocks. The metric population below stays gap-filtered.
            blocks_seen += int(ev_map.get("final_block_emitted", 0) or 0)
        done = _measured_int(r, "runs", "done")
        blocked = _measured_int(r, "runs", "blocked")
        evid = _measured_int(r, "runs", "done_evidenced")
        if done is None or blocked is None or evid is None:
            gaps["rules_compliance"] += 1
            gaps["terminator_spam"] += 1
            continue
        closures += done + blocked
        evidenced += evid
        if _events_gap(r):
            gaps["terminator_spam"] += 1
            continue
        ts_closures += done + blocked
        blocks += int((r.get("events") or {}).get("final_block_emitted", 0) or 0)
    # H3/M5: the run-record pair is guarded by the attribution floor — an n=1
    # attributed closure against an unknown-stream mass publishes NOTHING.
    closure_guard = _attribution_guard(rows, ("run_close",), closures, "run-record events")
    if closures and closure_guard is None:
        out["rules_compliance"] = MetricResult(
            id="rules_compliance",
            cell=_pct(evidenced, closures),
            detail="run_close done-with-evidence over all run-record closures"
            + _gap_note("rules_compliance"),
            value=evidenced / closures,
            numerator=evidenced,
            denominator=closures,
        )
    else:
        out["rules_compliance"] = MetricResult.unavailable(
            "rules_compliance",
            (closure_guard or "no run-record closures in the window")
            + _gap_note("rules_compliance"),
        )
    if ts_closures and closure_guard is None:
        out["terminator_spam"] = MetricResult(
            id="terminator_spam",
            cell=f"{blocks / ts_closures:.2f} ({blocks}/{ts_closures})",
            detail="final_block_emitted per run-record closure (>1.00 = spam)"
            + _gap_note("terminator_spam"),
            value=blocks / ts_closures,
            numerator=blocks,
            denominator=ts_closures,
        )
    else:
        out["terminator_spam"] = MetricResult.unavailable(
            "terminator_spam",
            (
                closure_guard
                or f"no run-record closures to normalize against ({blocks_seen} terminator "
                "block(s) seen)"
            )
            + _gap_note("terminator_spam"),
        )

    # ── premature-stop (event level) ─────────────────────────────────────────────
    stops = 0
    premature = 0
    for r in rows:
        if _events_gap(r) or ("stop_causes" in r and r["stop_causes"] is None):
            gaps["premature_stop_rate"] += 1
            continue
        events = r.get("events") or {}
        stops += int(events.get("stop_pass", 0)) + int(events.get("stop_block", 0))
        premature += sum(int((r.get("stop_causes") or {}).get(c, 0)) for c in PREMATURE_CAUSES)
    if stops:
        out["premature_stop_rate"] = MetricResult(
            id="premature_stop_rate",
            cell=_pct(premature, stops),
            detail="stop_block cause in {run-record, promise-stall} over all stop verdicts"
            + _gap_note("premature_stop_rate"),
            value=premature / stops,
            numerator=premature,
            denominator=stops,
        )
    else:
        out["premature_stop_rate"] = MetricResult.unavailable(
            "premature_stop_rate",
            "no stop verdicts in the window" + _gap_note("premature_stop_rate"),
        )

    # ── first-attempt gate pass ──────────────────────────────────────────────────
    # The first-attempt population is rows whose first_status is PRESENT — i.e. the
    # session's first attributed NON-check gate run happened in THIS window. A
    # continuing session's delta row (first_status nulled, its first attempt already
    # counted an earlier day) stays out of numerator AND denominator — it must not
    # dilute. S8: the "(continuing sessions only)" annotation keys on MEASURED
    # non-check runs — unsplit gate.runs would claim a continuing session where only
    # diagnostic --check runs happened.
    first_rows = [r for r in rows if (r.get("gate") or {}).get("first_status") is not None]
    noncheck_rows = [r for r in rows if (_gate_noncheck(r) or 0) > 0]
    # W4-2: the v3 formula's promised bump-gap accounting, performed. A row OUTSIDE
    # the population (no first_status this window) whose non-check split was
    # measured with no same-field baseline (runs_noncheck: None, root law) cannot
    # say whether any non-check run happened — it is excluded from the
    # continuing-session annotation and COUNTED as this metric's bump-day gap.
    for r in rows:
        raw_first_gate = r.get("gate")
        first_gate: dict = raw_first_gate if isinstance(raw_first_gate, dict) else {}
        if first_gate.get("first_status") is not None:
            continue  # in the population — fully measured for this metric
        if first_gate.get("first_status_consumed") is True:
            # W5-4: the predecessor already recorded this session's first attempt —
            # the row is OUT of the population BY DESIGN (delta_row's suppression
            # marker), never a bump-day gap, whatever its non-check split says.
            continue
        if "runs_noncheck" in first_gate and first_gate["runs_noncheck"] is None:
            gaps["first_attempt_gate_pass"] += 1
    if first_rows:
        first_pass = sum(1 for r in first_rows if r["gate"].get("first_status") == "success")
        out["first_attempt_gate_pass"] = MetricResult(
            id="first_attempt_gate_pass",
            cell=_pct(first_pass, len(first_rows)),
            detail="sessions whose FIRST attributed gate_run happened this window and passed"
            + _gap_note("first_attempt_gate_pass"),
            value=first_pass / len(first_rows),
            numerator=first_pass,
            denominator=len(first_rows),
        )
    else:
        out["first_attempt_gate_pass"] = MetricResult.unavailable(
            "first_attempt_gate_pass",
            "no session had its first attributed gate_run in the window"
            + (" (continuing sessions only)" if noncheck_rows else "")
            + _gap_note("first_attempt_gate_pass"),
        )

    # ── gate-failure taxonomy ────────────────────────────────────────────────────
    # W2-F1: the taxonomy is guarded twice. (a) Attribution floor — S7: the guard's
    # attributed operand is the NON-check occurrence count (the population the value
    # is computed over), never unsplit gate.runs — check-run mass must not vouch for
    # a non-check sliver. (b) Population — only NON-check runs count (the Stop
    # hook's --lean --check self-review is diagnostic; L5 rationale). A legacy row
    # without the non-check split is excluded (the honest under-count direction);
    # a bump-day None split is a gap (root law); runs_noncheck > runs is the
    # violated non-check ⊆ all invariant — warned, unmeasured (_gate_noncheck).
    noncheck_attr = 0
    tax_rows: list[dict] = []
    for r in rows:
        rn = _gate_noncheck(r)
        raw_gate = r.get("gate")
        gate: dict = raw_gate if isinstance(raw_gate, dict) else {}
        fc_gap = "failed_checks_noncheck" in gate and gate["failed_checks_noncheck"] is None
        if rn is None or fc_gap:
            if (_measured_int(r, "gate", "runs") or 0) > 0:
                gaps["gate_failure_taxonomy"] += 1
            continue
        noncheck_attr += rn
        if rn > 0:
            tax_rows.append(r)
    gate_guard = _attribution_guard(
        rows, ("gate_run",), noncheck_attr, "gate_run events (non-check side)"
    )
    if tax_rows and gate_guard is None:
        taxonomy: collections.Counter[str] = collections.Counter()
        gate_total = 0
        for r in tax_rows:
            gate_total += int(r["gate"].get("runs_noncheck", 0))
            for name, count in (r["gate"].get("failed_checks_noncheck") or {}).items():
                taxonomy[str(name)] += int(count)
        top = ", ".join(f"{n}={c}" for n, c in taxonomy.most_common(3))
        out["gate_failure_taxonomy"] = MetricResult(
            id="gate_failure_taxonomy",
            cell=top or f"clean (0 failing checks over {gate_total} non-check runs)",
            detail="per-check fail counts across attributed non-check gate_run events"
            + _gap_note("gate_failure_taxonomy"),
            value=dict(taxonomy),
            numerator=sum(taxonomy.values()),
            denominator=gate_total,
        )
    else:
        out["gate_failure_taxonomy"] = MetricResult.unavailable(
            "gate_failure_taxonomy",
            (
                gate_guard
                or (
                    "no session carries an attributed non-check gate_run "
                    "(check-mode runs are diagnostic, never taxonomy population)"
                )
            )
            + _gap_note("gate_failure_taxonomy"),
        )

    # ── rule activation ──────────────────────────────────────────────────────────
    closure_rows: list[dict] = []
    for r in rows:
        done = _measured_int(r, "runs", "done")
        blocked = _measured_int(r, "runs", "blocked")
        if done is None or blocked is None or _events_gap(r):
            gaps["rule_activation"] += 1
            continue
        if done + blocked > 0:
            closure_rows.append(r)
    # H3: when the rule_activation family lives only in the unknown stream, a 0%
    # over attributed sessions is a fabrication — the sensors fired, unattributably.
    activation_guard = _attribution_guard(
        rows, ("rule_activation",), esum("rule_activation"), "sensor events"
    )
    if closure_rows and activation_guard is None:
        activated = sum(
            1 for r in closure_rows if int((r.get("events") or {}).get("rule_activation", 0)) > 0
        )
        out["rule_activation"] = MetricResult(
            id="rule_activation",
            cell=_pct(activated, len(closure_rows)),
            detail="invocation-time activation: run-closing sessions with a rule_activation event"
            + _gap_note("rule_activation"),
            value=activated / len(closure_rows),
            numerator=activated,
            denominator=len(closure_rows),
        )
    else:
        out["rule_activation"] = MetricResult.unavailable(
            "rule_activation",
            (activation_guard or "no session closed a run record in the window")
            + _gap_note("rule_activation"),
        )

    # ── unclassified rate ────────────────────────────────────────────────────────
    # H2: lines over lines. The unknown stream's lines count in the numerator via
    # their unattributable-sid reason; a session missing exposure.project is a
    # STRATIFICATION gap (visible in concurrent_reason), not instrument unhealth —
    # it inflates neither term.
    total_lines = 0
    uncl_lines = 0
    for r in rows:
        lt = _measured_int(r, None, "lines_total")
        lu = _measured_int(r, None, "lines_unclassified")
        if lt is None or lu is None:
            gaps["unclassified_rate"] += 1
            continue
        total_lines += lt
        uncl_lines += lu
    excluded = sum(1 for r in rows if r.get("concurrent_reason") == "missing exposure.project")
    if total_lines:
        out["unclassified_rate"] = MetricResult(
            id="unclassified_rate",
            cell=_pct(uncl_lines, total_lines),
            detail=(
                f"{uncl_lines} unclassified line(s) (unknown-stream lines included) "
                f"over {total_lines} lines; {excluded} session(s) missing "
                "exposure.project are a stratification gap, counted in neither term"
                + _gap_note("unclassified_rate")
            ),
            value=uncl_lines / total_lines,
            numerator=uncl_lines,
            denominator=total_lines,
        )
    else:
        out["unclassified_rate"] = MetricResult.unavailable(
            "unclassified_rate", "no lines in the window" + _gap_note("unclassified_rate")
        )

    # ── the death pair (W6-1) — the weekly cell's ONLY source is these day points ─
    occ_total = 0
    coroner_evidence = 0
    death_map: collections.Counter[str] = collections.Counter()
    for r in rows:
        if _events_gap(r):
            gaps["death_occurrences"] += 1
        else:
            events = r.get("events") or {}
            occ_total += int(events.get("death", 0) or 0)
            coroner_evidence += int(events.get("death", 0) or 0) + int(
                events.get("session_end", 0) or 0
            )
        dc = r.get("death_classes")
        if "death_classes" in r and dc is None:
            gaps["death_classes"] += 1  # root law — measured with no baseline
        elif isinstance(dc, list):
            death_map.update(str(c) for c in dc if c)
        else:
            # W2-F6 mixed-store compatibility: a FACTS_VERSION-1 row carries a
            # SCALAR death_class — coerce it to a one-element list at read.
            legacy = r.get("death_class")
            if isinstance(legacy, str) and legacy:
                death_map[legacy] += 1
    death_guard = _attribution_guard(rows, ("death",), occ_total, "death events")
    if death_guard is not None:
        out["death_occurrences"] = MetricResult.unavailable(
            "death_occurrences", death_guard + _gap_note("death_occurrences")
        )
        out["death_classes"] = MetricResult.unavailable(
            "death_classes", death_guard + _gap_note("death_classes")
        )
    elif coroner_evidence <= 0:
        no_coroner = (
            "no coroner evidence in the day's rows (no death or session_end event) — "
            "a 0 would fabricate a coroner run (M9, day-scoped)"
        )
        out["death_occurrences"] = MetricResult.unavailable(
            "death_occurrences", no_coroner + _gap_note("death_occurrences")
        )
        out["death_classes"] = MetricResult.unavailable(
            "death_classes", no_coroner + _gap_note("death_classes")
        )
    else:
        out["death_occurrences"] = MetricResult(
            id="death_occurrences",
            cell=str(occ_total),
            detail="attributed death events in the day's delta rows"
            + _gap_note("death_occurrences"),
            value=occ_total,
            numerator=occ_total,
            denominator=None,
        )
        classes_cell = ", ".join(f"{c}={n}" for c, n in death_map.most_common())
        out["death_classes"] = MetricResult(
            id="death_classes",
            cell=classes_cell or "clean (0 classified deaths)",
            detail="the day's NEW death classes (delta suffix)" + _gap_note("death_classes"),
            value=dict(death_map),
            numerator=sum(death_map.values()),
            denominator=None,
        )

    if holes is None:
        out["hole_count"] = MetricResult.unavailable("hole_count", holes_reason)
    else:
        out["hole_count"] = MetricResult(
            id="hole_count",
            cell=str(int(holes)),
            detail=(
                "transcripts with activity but no stop_pass and no session_end "
                "(coroner hole metric)"
            ),
            value=int(holes),
            numerator=int(holes),
            denominator=None,
        )
    return out


# ── series publication — append-only, versioned, idempotent per day ──────────────────


def _latest_series_day(state: Path | None = None) -> str | None:
    """The newest ``day`` across every published series file, or None when nothing
    is published — :func:`daily`'s out-of-order guard reads this (W2-F4)."""
    st = state or state_dir()
    days: set[str] = set()
    try:
        files = list((st / "series").glob("*.jsonl"))
    except OSError:
        return None
    for p in files:
        days |= _series_days(p)
    return max(days) if days else None


def _series_days(path: Path) -> set[str]:
    out: set[str] = set()
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(row, dict) and isinstance(row.get("day"), str):
                    out.add(row["day"])
    except FileNotFoundError:
        # W13-1: a missing file is the NORMAL first-publish / post-bump path —
        # never a warn (a false "unreadable" trains the operator to ignore the
        # real one).
        pass
    except OSError as exc:
        # Fail-open, visibly (W12-3): a silently skipped series file can disable
        # the split-week and disjoint-halves guards.
        _warn(f"series file unreadable: {path.name}: {exc}")
    return out


def publish_series(
    day: str,
    metrics: dict[str, MetricResult],
    reg: dict[str, dict],
    state: Path | None = None,
) -> list[Path]:
    """Append one row per MEASURABLE metric to its versioned series file. Append-only:
    a definition change writes a NEW ``<metric>@v<N>.jsonl``; existing files are never
    rewritten, and a day already published is never re-appended (idempotent)."""
    st = state or state_dir()
    written: list[Path] = []
    for mid, mdef in reg.items():
        m = metrics.get(mid)
        if m is None or not m.measurable:
            continue  # an unmeasurable metric publishes NOTHING — the row renders `—`
        path = series_path(mid, int(mdef["version"]), st)
        # L6: the read-days→append seam is the same two-step race as the facts store
        # — locked per series file so concurrent publishers stay idempotent.
        with _store_lock(path):
            if day in _series_days(path):
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            row = {
                "day": day,
                "metric": mid,
                "version": mdef["version"],
                "def_hash": mdef["hash"],
                "value": m.value,
                "numerator": m.numerator,
                "denominator": m.denominator,
                "cell": m.cell,
            }
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            written.append(path)
    return written


# ── the golden-corpus assertion gate — instrument health is metric zero ──────────────


def golden_check(golden: Path | None = None) -> list[str]:
    """Derive the hand-labelled corpus and compare against expected.json.

    Returns the list of mismatches — empty means the instrument is green. The daily
    collector runs this BEFORE publishing anything and refuses on any mismatch. The
    gate itself fails CLOSED: an unreadable corpus or expectations file IS a mismatch,
    never a free pass.
    """
    root = golden or golden_dir()
    try:
        expected = json.loads((root / "expected.json").read_text(encoding="utf-8"))
        sessions = expected["sessions"]
        totals = expected["totals"]
        assert isinstance(sessions, dict) and isinstance(totals, dict)
    except Exception as exc:
        return [f"expected.json unreadable at {root}: {exc!r} — the gate fails CLOSED"]
    try:
        paths = sorted(root.glob("*.jsonl"))
    except OSError as exc:
        return [f"golden corpus unreadable at {root}: {exc!r}"]
    if not paths:
        return [f"golden corpus at {root} holds no session files"]

    mismatches: list[str] = []
    if expected.get("facts_version") != FACTS_VERSION:
        mismatches.append(
            f"facts_version: expected labels are for {expected.get('facts_version')}, "
            f"collector derives {FACTS_VERSION} — re-label the corpus at the bump"
        )
    rows = {r["sid"]: r for r in derive_batch(paths)}
    for sid in sorted(set(rows) - set(sessions)):
        mismatches.append(f"{sid}: derived but carries no hand label in expected.json")
    for sid, exp in sorted(sessions.items()):
        row = rows.get(sid)
        if row is None:
            mismatches.append(f"{sid}: labelled but not derived")
            continue
        for key, want in exp.items():
            got = row.get(key)
            if got != want:
                mismatches.append(f"{sid}.{key}: expected {want!r}, derived {got!r}")
    derived_totals = {
        "sessions": len(rows),
        "lines_total": sum(int(r.get("lines_total", 0)) for r in rows.values()),
        "lines_unclassified": sum(int(r.get("lines_unclassified", 0)) for r in rows.values()),
        "concurrency_excluded": sum(1 for r in rows.values() if r.get("concurrent") is None),
    }
    for key, want in totals.items():
        got = derived_totals.get(key)
        if got != want:
            mismatches.append(f"totals.{key}: expected {want!r}, derived {got!r}")
    return mismatches


# ── the kaizen-log row — ISO-week idempotence + analyst-cell preservation ─────────────


def _split_row(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _split_row_shaped(row: str, n: int) -> list[str] | None:
    """Split a table row into exactly ``n`` cells, or None when it cannot be done.

    A literal ``|`` inside the LAST cell (an analyst's prose) over-splits a naive
    ``split``; overflow segments re-join into the final cell so the analyst's text
    survives whole. A row with FEWER cells than the table declares is malformed —
    the caller preserves it verbatim, never reshapes it."""
    parts = row.strip().strip("|").split("|")
    if len(parts) > n:
        parts = parts[: n - 1] + ["|".join(parts[n - 1 :])]
    if len(parts) != n:
        return None
    return [c.strip() for c in parts]


def _render_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _iso_week(value: str) -> tuple[int, int] | None:
    try:
        parsed = dt.date.fromisoformat(value.strip())
    except ValueError:
        return None
    year, week, _ = parsed.isocalendar()
    return year, week


def _merge_cells(new: list[str], old: list[str], force_dash: bool) -> list[str]:
    """Mechanical cells ALWAYS take the newly computed value — a dash included: a
    fresh honest ``—`` under an advanced date must never republish the previous
    day's stale number (H6). Only the ANALYST cells keep the yield rule (a ``—``
    yields to whatever the analysis half put there — the script never overwrites a
    human's cell with a dash). ``force_dash`` (golden refusal) stamps the mechanical
    cells ``—`` regardless while the analyst cells still survive."""
    merged = list(new)
    for i in range(1, len(new)):
        if force_dash and i not in _ANALYST_CELLS:
            merged[i] = DASH
            continue
        if i in _ANALYST_CELLS and merged[i] == DASH and i < len(old) and old[i] not in ("", DASH):
            merged[i] = old[i]
    return merged


def upsert_log_row(path: Path, cells: list[str], force_dash: bool = False) -> bool:
    """Upsert one row keyed by the Date cell's ISO week (a second run in the same week
    UPDATES that row). Fail-soft: a missing or tableless log warns and returns False."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        _warn(f"no kaizen log at {path} ({exc!r}) — row skipped")
        return False
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.lstrip().startswith("|")), None)
    if start is None or start + 1 >= len(lines):
        _warn(f"no markdown table in {path} — row skipped")
        return False
    end = start + 2
    while end < len(lines) and lines[end].lstrip().startswith("|"):
        end += 1
    rows = lines[start + 2 : end]
    key = _iso_week(cells[0])
    target: int | None = None
    target_cells: list[str] | None = None
    for i, row in enumerate(rows):
        shaped = _split_row_shaped(row, len(COLUMNS))
        if shaped is None:
            first = _split_row(row)
            if first and key is not None and _iso_week(first[0]) == key:
                _warn(
                    f"malformed row in {path.name} (not {len(COLUMNS)} cells) preserved "
                    "VERBATIM — this week's fresh row is appended alongside it"
                )
            continue  # never a merge target, never reshaped
        if key is not None and _iso_week(shaped[0]) == key:
            target, target_cells = i, shaped
    if target is None or target_cells is None:
        rows.append(_render_row(list(cells)))
    else:
        rows[target] = _render_row(_merge_cells(list(cells), target_cells, force_dash))
    out = lines[: start + 2] + rows + lines[end:]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return True


#: The weekly cells' shared dash reason (W6-1).
NO_WEEK_DAYS = "no published days this week"
#: W7-2 — the dash reason when the week holds ONLY prior-definition day points.
SPLIT_WEEK_NO_CURRENT = (
    "definition changed this week; no days published at the current definition yet"
)
#: W10-2 — both pair halves bumped on DIFFERENT days: no week day carries both
#: halves at the current definition, so any cell would mix disjoint definitions.
SPLIT_WEEK_DISJOINT_HALVES = (
    "definition changed mid-week and the pair's halves share no current-definition "
    "day — an occurrence sum and a class set covering disjoint day sets are never paired"
)
#: W7-3 — the death pair's one-sided dash reason (measurability needs BOTH halves).
DEATH_PAIR_ONE_SIDED = (
    "the death pair is measurable only when BOTH halves publish for the week "
    "(occurrence day points AND class day points)"
)


def _older_version_week_days(
    metric: str, version: int, days: list[str], state: Path | None
) -> set[str]:
    """Week days present in an OLDER registry version's series file for ``metric``
    — the W7-2 mid-week definition-change signal. Versions are never mixed in one
    weekly sum; this only tells the cell which days the current definition is
    missing because they were measured under a previous one. Fail-open: an
    unreadable series dir contributes nothing."""
    window = set(days)
    out: set[str] = set()
    sdir = (state or state_dir()) / "series"
    try:
        # W12-3: LIST inside the guarded region — Path.glob swallows
        # PermissionError internally, so the W11-4 warn never fired for the
        # dominant unreadable-dir cause. Fail-open, but VISIBLY: an empty orphan
        # set silently disables the split-week dash AND the disjoint-halves guard.
        files = [p for p in sdir.iterdir() if p.name.endswith(".jsonl")]
    except FileNotFoundError:
        return out
    except OSError as exc:
        _warn(f"series dir unreadable while probing older versions of {metric}: {exc}")
        return out
    for p in files:
        m = re.match(rf"^{re.escape(metric)}@v(\d+)$", p.stem)
        if m is None or int(m.group(1)) >= version:
            continue
        out |= _series_days(p) & window
    return out


def _coroner_ever(state: Path | None = None) -> bool:
    """The whole-store universe signal (M9, reused by W7-6): has the coroner EVER
    produced evidence — a death or session_end event on ANY store row?"""
    for row in _iter_facts(state or state_dir()):
        ev = row.get("events")
        if isinstance(ev, dict) and (
            int(ev.get("death", 0) or 0) > 0 or int(ev.get("session_end", 0) or 0) > 0
        ):
            return True
    return False


def _week_days(day: dt.date) -> list[str]:
    """The ISO week's ELAPSED day stamps, Monday..``day`` inclusive."""
    week_start = day - dt.timedelta(days=day.isoweekday() - 1)
    return [
        (week_start + dt.timedelta(days=k)).isoformat() for k in range((day - week_start).days + 1)
    ]


def series_points(
    metric: str, version: int, days: list[str], state: Path | None = None
) -> list[dict]:
    """The metric's PUBLISHED day points for ``days``, read from the current
    registry version's series file only — the weekly cells' single source (W6-1).
    A missing file or torn line contributes nothing (the day was never published)."""
    window = set(days)
    out: list[dict] = []
    try:
        with open(series_path(metric, version, state), encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("day") in window:
                    out.append(row)
    except OSError:
        return []
    return out


def _point_int(point: dict, field: str) -> int | None:
    val = point.get(field)
    if isinstance(val, bool) or not isinstance(val, int):
        return None
    return val


def _ratio_cell(points: list[dict], label: str, dash_reason: str = NO_WEEK_DAYS) -> str:
    """SUM the week's published day numerators/denominators — a per-day mean of
    means would re-weight sessions by derivation day (the 33% dilution shape)."""
    num = den = counted = 0
    for p in points:
        n, d = _point_int(p, "numerator"), _point_int(p, "denominator")
        if n is None or d is None or d <= 0:
            continue
        num += n
        den += d
        counted += 1
    if not counted:
        reason = (
            "published day points exist but none carries a summable numerator/denominator "
            "(empty or invalid populations)"
            if points
            else dash_reason
        )
        _warn(f"{label} = {DASH} — {reason}")
        return DASH
    return _pct(num, den)


def _death_cell(
    occ_points: list[dict], cls_points: list[dict], dash_reason: str = NO_WEEK_DAYS
) -> str:
    """The week's REAL occ/cls: occurrences summed from death_occurrences day
    points, classes merged from death_classes day maps — both already
    delta-honest at publish (the day's NEW deaths only).

    W7-3 — the pair contract: measurability requires BOTH halves (occurrence day
    points AND class day points); a one-sided week dashes with the pair-contract
    reason, never a fabricated ``N occ / 0 cls`` (or a class list floating with
    no occurrence volume)."""
    occ = 0
    counted = 0
    for p in occ_points:
        n = _point_int(p, "numerator")
        if n is None:
            continue
        occ += n
        counted += 1
    cls_counted = sum(1 for p in cls_points if isinstance(p.get("value"), dict))
    # W9-3: when the caller measured a split week (one half version-bumped with no
    # current-version days yet), THAT is the cause — the pair-contract claim ("no
    # class day points") would be false while previous-definition points exist.
    if not counted:
        if dash_reason == SPLIT_WEEK_NO_CURRENT:
            reason = dash_reason
        elif cls_counted:
            reason = f"class day points exist but no occurrence day points — {DEATH_PAIR_ONE_SIDED}"
        else:
            reason = dash_reason
        _warn(f"Death-classes /wk = {DASH} — {reason}")
        return DASH
    if not cls_counted:
        if dash_reason == SPLIT_WEEK_NO_CURRENT:
            _warn(f"Death-classes /wk = {DASH} — {dash_reason}")
        else:
            _warn(
                f"Death-classes /wk = {DASH} — {occ} occurrence day value(s) have no class "
                f"day points — {DEATH_PAIR_ONE_SIDED}"
            )
        return DASH
    merged: set[str] = set()
    for p in cls_points:
        val = p.get("value")
        if isinstance(val, dict):
            merged.update(str(k) for k in val)
    return f"{occ} occ / {len(merged)} cls"


def log_cells(day: dt.date, reg: dict[str, dict], state: Path | None = None) -> list[str]:
    """THE SINGLE-SOURCE LAW (W6-1): every mechanical weekly cell aggregates THE
    PUBLISHED DAY SERIES — the one already-delta-honest source — and NEVER
    recomputes from store rows (mixed row semantics fabricated cells: lifetime
    ``rounds_max`` under a growth guard, delta occ against point-in-time death
    classes, per-(sid,day) rows diluting per-session shares into per-row shares).

    Aggregation per metric kind: ratio cells SUM the ISO week's published day
    numerators/denominators; the death cell sums occurrences and merges the day
    class maps. THE ONE CARVE-OUT (W8-1): the rounds cell — rounds_max is a
    point-in-time per-session quantity that anonymous day points cannot
    per-session-deduplicate, so it recomputes latest-per-sid over the week's
    day-scoped delta rows via :func:`kaizen_outcomes.review_rounds` (same
    day-scoped attribution guard as the day publish; one definition for the
    whole week). A day the series lacks contributes nothing — its honesty gates
    (attribution floor, coroner evidence, bump-day gaps) already spoke at publish
    time. A week with NO published days for a metric renders ``—`` with the
    reason (:data:`NO_WEEK_DAYS`). ``reg`` is the CURRENT full registry
    (T06 + outcome tier) — only current-version series files are read.

    W7-2 — the split week, annotated: a mid-week registry version bump leaves the
    earlier days in the PREVIOUS version's file. Versions are never mixed in one
    sum; the cell aggregates current-definition points only and carries a ``*``
    marker with a stderr note stating k of N week days, and when ZERO days exist
    at the current definition the dash reason says so
    (:data:`SPLIT_WEEK_NO_CURRENT`) instead of the generic no-published-days
    claim. W7-6 — a coroner-quiet death cell names WHICH cause via the
    whole-store universe signal (:func:`_coroner_ever`): the coroner has never
    run · series file missing at the current version · every week day
    gapped/unpublished."""
    days = _week_days(day)

    def _pts(mid: str) -> list[dict]:
        mdef = reg.get(mid)
        if mdef is None:
            _warn(f"weekly cell metric {mid} missing from the registry — {DASH}")
            return []
        return series_points(mid, int(mdef["version"]), days, state)

    def _week_versions(
        mids: tuple[str, ...], ptss: list[list[dict]]
    ) -> tuple[set[str], set[str], bool, str]:
        """W7-2 + W8-3 + W10-1 — ``(current-definition week days, week days only
        under an older definition, split_blocked)`` for the cell's metric(s),
        computed PER HALF: a one-sided mid-week bump (classes at v2, occurrences
        still v1) must not let the un-bumped half's current-version days empty
        the bumped half's orphan set — the pair is split-week if EITHER half has
        orphan days, and its current set is the days where EVERY half is
        current. ``split_blocked`` (W10-1) is True only when some half's
        emptiness is BUMP-CAUSED (that half has orphan days AND no current
        days) — a half that simply never published is a pair-contract gap, and
        claiming "no days at the current definition yet" while the other half
        has current days would be false."""
        curs: list[set[str]] = []
        orphans: list[set[str]] = []
        halves: dict[str, set[str]] = {}
        split_blocked = False
        for mid, ps in zip(mids, ptss, strict=True):
            cur = {str(p["day"]) for p in ps if isinstance(p.get("day"), str)}
            mdef = reg.get(mid)
            older = (
                _older_version_week_days(mid, int(mdef["version"]), days, state)
                if mdef is not None
                else set()
            )
            curs.append(cur)
            halves[mid] = cur
            orphans.append(older - cur)
            if not cur and (older - cur):
                split_blocked = True
        cur_all = set.intersection(*curs) if curs else set()
        orphan_any = set.union(*orphans) if orphans else set()
        # W9-5 + W12-4: a pair's split-week disclosures state each half's
        # current-definition day count — "k of N" over the intersection
        # misdescribes which half is truncated beside a sum taken over the
        # wider half.
        halves_text = ""
        if len(mids) > 1:
            halves_text = ", ".join(f"{mid} {len(halves[mid])}/{len(days)}" for mid in mids)
        return cur_all, orphan_any, split_blocked, halves_text

    def _split_dash_reason(split_blocked: bool, fallback: str = NO_WEEK_DAYS) -> str:
        return SPLIT_WEEK_NO_CURRENT if split_blocked else fallback

    def _annotate(
        cell: str, label: str, cur: set[str], orphan: set[str], coverage: str = ""
    ) -> str:
        """W7-2: mark a split-week cell — current-definition days only, stated.
        ``coverage`` (W12-4): a pair's headline states each half's own coverage —
        the intersection count beside a sum taken over a wider half misdescribes
        the published number."""
        if not orphan or cell == DASH:
            return cell
        headline = coverage or f"{len(cur)} of {len(days)} week day(s)"
        _warn(
            f"{label}: * {headline} at the current definition "
            "(definition changed mid-week; each aggregated number covers only its "
            "metric's current-definition days)"
        )
        return cell + "*"

    def _death_quiet_reason() -> str:
        """W7-6: the coroner-quiet week's dash cause, distinguished — never one
        flat no-published-days claim for three different repairs."""
        if not _coroner_ever(state):
            return (
                "the coroner has never run — no death or session_end event anywhere "
                "in the store (a 0 would be fabricated)"
            )
        mdef = reg.get("death_occurrences")
        if (
            mdef is not None
            and not series_path("death_occurrences", int(mdef["version"]), state).is_file()
        ):
            return (
                "death series file missing at the current version — the coroner has "
                "run, but no day point was ever published at this definition"
            )
        return (
            "every week day gapped or unpublished — the coroner has run and the "
            "series exists, but no day point landed in this week"
        )

    gate_pts = _pts("first_attempt_gate_pass")
    g_cur, g_orphan, g_split, _g_halves = _week_versions(("first_attempt_gate_pass",), [gate_pts])
    gate_cell = _ratio_cell(
        gate_pts, "Gate first-pass rate", dash_reason=_split_dash_reason(g_split)
    )
    gate_cell = _annotate(gate_cell, "Gate first-pass rate", g_cur, g_orphan)
    # W15-2: a dash suppresses the annotate line — when the week is version-split
    # the orphan days are actionable context and must still reach the operator.
    if g_orphan and gate_cell == DASH and not g_split:
        _warn(
            f"Gate first-pass rate: {len(g_orphan)} week day(s) under a previous "
            "definition (version split this week; the dash above has a different cause)"
        )

    occ_pts, cls_pts = _pts("death_occurrences"), _pts("death_classes")
    d_cur, d_orphan, d_split, d_halves = _week_versions(
        ("death_occurrences", "death_classes"), [occ_pts, cls_pts]
    )
    death_fallback = (
        NO_WEEK_DAYS
        if any(_point_int(p, "numerator") is not None for p in occ_pts)
        else _death_quiet_reason()
    )
    # W10-2: both halves publishing at the current definition but on DISJOINT day
    # sets (each half bumped on a different day) — any cell would pair numbers
    # from disjoint definitions; dash with the true cause, never publish.
    occ_has = any(_point_int(p, "numerator") is not None for p in occ_pts)
    cls_has = any(isinstance(p.get("value"), dict) for p in cls_pts)
    if occ_has and cls_has and not d_cur and d_orphan:
        _warn(f"Death-classes /wk = {DASH} — {SPLIT_WEEK_DISJOINT_HALVES}")
        deaths = DASH
    else:
        deaths = _death_cell(
            occ_pts, cls_pts, dash_reason=_split_dash_reason(d_split, death_fallback)
        )
        deaths = _annotate(deaths, "Death-classes /wk", d_cur, d_orphan, coverage=d_halves)
    # W13 (round-13 #6): the standalone per-half line rides ONLY the paths whose
    # cell line does not already carry the halves text (a DASH suppresses the
    # annotate line) — never the same string twice per weekly log.
    if d_halves and d_orphan and deaths == DASH:
        _warn("split-week halves at the current definition: " + d_halves)

    # W8-1 — the single-source law's ONE carve-out: rounds_max is a point-in-time
    # per-session quantity, and anonymous day points cannot be per-session-
    # deduplicated (a multi-day session would be counted once per residency day
    # with its partial values summed). The weekly cell recomputes over the ISO
    # week's day-scoped delta rows, latest-per-sid, under the same day-scoped
    # attribution guard the day publish uses — the whole week under ONE (the
    # current) definition, so no version mixing is possible. Fail-open.
    try:
        import kaizen_outcomes as _ko  # noqa: PLC0415 - call-time, avoids the import cycle

        rr = _ko.review_rounds(state=state, days=days)
        if rr.measurable:
            rounds = rr.cell
            # W9-2: the carve-out cell must not be the one bare number — its
            # honesty annotations (attribution share, bootstrap exclusions, the
            # smear) ride to stderr with the row, never silently folded.
            _warn(f"Review rounds /plan detail: {rr.detail}")
        else:
            _warn(f"Review rounds /plan = {DASH} — {rr.detail}")
            rounds = DASH
    except Exception as exc:  # never let the rounds cell kill the whole log row
        _warn(f"Review rounds /plan = {DASH} — weekly recompute unavailable ({exc})")
        rounds = DASH
    _warn(f"Lesson-class recurrence = {DASH} — no class taxonomy on lessons (analysis-half job)")
    _warn(
        f"Missed crons = {DASH} — not an event-stream metric; the liveness audit owns it "
        "(docs/workstation/liveness.md)"
    )
    return [
        day.isoformat(),
        gate_cell,
        deaths,
        DASH,
        rounds,
        DASH,
        DASH,
        DASH,
    ]


# ── hand-off mail (fail-soft, inherited pattern) ──────────────────────────────────────


def send_mail(repo_root: Path, body: str) -> bool:
    mail = repo_root / "scripts" / "mail.py"
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, str(mail), "send", "--to", "fabrik", "--kind", "request"],
            input=body,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - defensive; the row is already on disk
        _warn(f"mail hand-off failed ({exc!r}) — data already recorded")
        return False
    if proc.returncode != 0:
        _warn(f"mail hand-off failed (exit {proc.returncode}) — data already recorded")
        return False
    return True


def _compose_mail(day: dt.date, metrics: dict[str, MetricResult], holes_note: str) -> str:
    lines = [f"# Kaizen daily collection — {day}", ""]
    for mid, m in metrics.items():
        mark = "" if m.measurable else "  [NOT MEASURED]"
        lines.append(f"- {mid}: {m.cell}{mark}")
        if m.detail:
            lines.append(f"  - {m.detail}")
    if holes_note:
        lines += ["", holes_note]
    return "\n".join(lines) + "\n"


def _emit_alarm(reason: str, mismatches: list[str]) -> None:
    """Emit the ``instrument_alarm`` event — fail-open, like every sensor."""
    if kaizen_events is None:
        _warn("kaizen_events unavailable — instrument_alarm not emitted")
        return
    try:
        kaizen_events.emit("instrument_alarm", reason=reason, mismatches=mismatches[:10])
    except Exception as exc:  # pragma: no cover - emit() itself never raises
        _warn(f"instrument_alarm emit failed open: {exc!r}")


# ── daily mode ────────────────────────────────────────────────────────────────────────


def _coroner_holes(day: dt.date, events: Path | None = None) -> tuple[int | None, str]:
    """The coroner hole probe. ``events`` pins the probe's event store to the SAME
    dir this daily pass consumes (L4) — the default-source probe silently counted a
    different store's holes whenever ``daily(events=…)`` was overridden.

    W2-F3: ``holes()`` returns None when it is BLIND (missing/unreadable transcripts
    dir, internal error) — mapped to the honest dash with its reason, never a
    published perfect 0. An empty-but-readable dir stays a measured 0."""
    try:
        import kaizen_coroner  # noqa: PLC0415 - lazy; same directory

        sources = None
        if events is not None:
            sources = dataclasses.replace(kaizen_coroner.Sources.default(), events_dir=events)
        holes = kaizen_coroner.holes(sources, day=day)
        if holes is None:
            return None, "transcripts unreadable"
        return int(holes), ""
    except Exception as exc:
        return None, f"coroner unavailable: {exc!r}"


def _publish_outcome_series(day_stamp: str, st: Path) -> list[Path]:
    """T07's STORE-DERIVED outcome metrics (premature_stop / stop_block_causes /
    review_rounds) ride the same daily publish (M7): the noise floor needs their
    series days and nothing else appends them daily. DAY-SCOPED (W7-1): the
    published day point is computed over ``days=[day_stamp]`` — that day's delta
    rows only — never the trailing CLI window (a windowed value published as a
    day point made the weekly cell sum seven overlapping windows). The
    sweep/rework tiers keep their own runners — a daily pass must never mine git
    or clone worktrees. Guarded + fail-open: a box without kaizen_outcomes costs
    the outcome series only, never the T06 publish."""
    try:
        import kaizen_outcomes  # noqa: PLC0415 - lazy; avoids a module-import cycle

        reg = kaizen_outcomes.registry()
        prem, causes = kaizen_outcomes.premature_stop(state=st, days=[day_stamp])
        rounds = kaizen_outcomes.review_rounds(state=st, days=[day_stamp])
        results = {m.id: m for m in (prem, causes, rounds)}
        sub = {mid: reg[mid] for mid in results if mid in reg}
        return publish_series(day_stamp, results, sub, st)
    except Exception as exc:
        _warn(f"outcome-tier series publish failed open: {exc!r}")
        return []


def daily(
    day: dt.date,
    *,
    repo_root: Path | None = None,
    events: Path | None = None,
    state: Path | None = None,
    golden: Path | None = None,
    log_paths: list[Path] | None = None,
    no_mail: bool = False,
    holes_fn: object = None,
) -> int:
    """One daily pass: golden gate → consolidate yesterday's events into facts →
    series → the kaizen-log row + hand-off mail. Refusal semantics on a golden
    mismatch: exit non-zero, emit ``instrument_alarm``, publish NOTHING, render the
    log row ``—`` (reason on stderr + mail).

    Session files are selected by mtime date >= the target day — anything still
    ALIVE at or after the day (H1: strict equality permanently excluded the
    never-quiescing ``unknown.jsonl`` and deferred every still-active session; the
    keyed dedup and the delta seam keep the later re-derivations honest). The
    concurrency flag is computed within that day's derivation batch: rows are
    immutable once appended (the derived-facts law), so a session late-derived on a
    re-run sees only its own batch's windows. Honest limit, stated here rather than
    papered over.

    **The one-day forward smear (W2-F8, documented not hidden):** the standard cron
    pass consolidates YESTERDAY with the mtime>=day selector, so a file still alive
    when the pass runs is derived with its CURRENT cumulative content — lines
    written TODAY (before the pass) land in yesterday's published day. The smear is
    bounded to one day forward (the pass runs daily, so a line can only ever be
    pulled into the single previous day), and cross-day totals stay honest: the
    delta seam subtracts the predecessor row, so a smeared line is counted ONCE —
    the smear shifts which day it lands in, never how many land.

    **Out-of-order refusal (W2-F4) + the escape hatch (S4):** a ``day`` strictly
    OLDER than the newest day already published in the series store is REFUSED
    (nonzero rc, zero mutation) — under the mtime>=day selector it would derive
    every alive file's current cumulative content under the old day and
    double-publish into the append-only series, unrepairably. Historical backfill
    is ``kaizen_backfill``'s job. BUT a future-dated day in the series (a
    post-resume clock jump published tomorrow's date) would wedge the hourly cron
    PERMANENTLY on this refusal — so (a) when the newest published day is in the
    FUTURE relative to both the requested day and today, the refusal names the
    clock-jump diagnosis explicitly, and (b) ``KAIZEN_ALLOW_BACKPUBLISH=1`` (env,
    default off) downgrades the refusal to a loud warning and proceeds — the
    operator's documented unwedge, accepting the possible double-count it warns
    about.

    The DAY series is published from per-day DELTAS (see delta_row) so a grown file
    never re-counts earlier days. **THE SINGLE-SOURCE LAW (W6-1):** the human-facing
    weekly log cells aggregate THE PUBLISHED DAY SERIES — the one already-delta-honest
    source — and never recompute from store rows (see :func:`log_cells`); the human
    row is thereby provably consistent with the machine series. The machine-consumed
    publication is the series + read_rows."""
    root = repo_root or REPO
    ev = events or events_dir()
    st = state or state_dir()
    # M6: validate the registry BEFORE any state mutation — a broken definition set
    # must refuse loudly (alarm + raise), never after facts were already appended.
    try:
        reg = registry()
    except Exception as exc:
        _emit_alarm(f"metric registry invalid: {exc!r}", [])
        raise
    # W2-F4: REFUSE an out-of-order older day BEFORE anything mutates. Under the
    # mtime>=day selector an older day would derive every alive file's CURRENT
    # cumulative content under that old day and double-publish into the append-only
    # series (unrepairable). Same-day re-runs stay idempotent; newer days proceed.
    day_stamp = day.isoformat()
    newest_published = _latest_series_day(st)
    if newest_published is not None and day_stamp < newest_published:
        # S4: a future-dated day in the series (post-resume clock jump) would wedge
        # the hourly cron PERMANENTLY — every honest day is then "older than the
        # newest". Diagnose the jump explicitly, and offer the documented escape
        # hatch: KAIZEN_ALLOW_BACKPUBLISH=1 downgrades the refusal to a loud
        # warning (default off — the refusal stays the normal safety).
        clock_note = ""
        today_stamp = dt.date.today().isoformat()
        if newest_published > today_stamp:
            clock_note = (
                f" DIAGNOSIS: the newest published day {newest_published} is in the "
                f"FUTURE relative to both the requested day and today ({today_stamp}) "
                "— a clock jump (post-resume/RTC skew) likely published a "
                "future-dated day into the series."
            )
        if os.getenv("KAIZEN_ALLOW_BACKPUBLISH", "") == "1":
            _warn(
                f"KAIZEN_ALLOW_BACKPUBLISH=1 — refusal DOWNGRADED to a warning: "
                f"--day {day_stamp} is OLDER than the newest published series day "
                f"{newest_published}; proceeding anyway. Alive files' CURRENT "
                "cumulative content will be derived under the old day — the "
                "append-only series may double-count this day." + clock_note
            )
        else:
            _warn(
                f"REFUSED: --day {day_stamp} is OLDER than the newest published series "
                f"day {newest_published} — the mtime>=day selector would derive current "
                "cumulative content under the old day and double-publish into the "
                "append-only series. Nothing was written. Historical backfill is "
                "kaizen_backfill's job. Escape hatch: set KAIZEN_ALLOW_BACKPUBLISH=1 "
                "to downgrade this refusal to a loud warning (the sanctioned case: a "
                "cron wedged by a future-dated series day)." + clock_note
            )
            return 1
    logs = (
        log_paths
        if log_paths is not None
        else [
            root / "docs" / "reference" / "agents" / "kaizen-log-infra.md",
            root / "docs" / "reference" / "agents" / "kaizen-log-fleet.md",
        ]
    )

    mismatches = golden_check(golden)
    if mismatches:
        for m in mismatches:
            _warn(f"GOLDEN MISMATCH: {m}")
        _warn(f"{GOLDEN_MISMATCH_REASON} — publication refused, nothing written")
        _emit_alarm(GOLDEN_MISMATCH_REASON, mismatches)
        refusal = [day.isoformat()] + [DASH] * (len(COLUMNS) - 1)
        for lp in logs:
            upsert_log_row(lp, refusal, force_dash=True)
        if not no_mail:
            body = f"# KAIZEN INSTRUMENT ALARM — {GOLDEN_MISMATCH_REASON}\n\n" + "\n".join(
                f"- {m}" for m in mismatches
            )
            send_mail(root, body)
        return 1

    try:
        candidates = sorted(ev.glob("*.jsonl"))
    except OSError:
        candidates = []
    todays: list[Path] = []
    for f in candidates:
        try:
            # H1: anything ALIVE at or after the target day. Strict equality
            # permanently excluded unknown.jsonl (it never quiesces — its mtime is
            # always today) and deferred every still-active session forever. The
            # keyed dedup + delta seam keep later re-derivations honest.
            if dt.date.fromtimestamp(f.stat().st_mtime) >= day:
                todays.append(f)
        except (OSError, OverflowError, ValueError):
            continue
    known = known_fact_keys(st)
    # W4-3: the key carries the era — an event derivation is only masked by an
    # EVENT-era row at the same (sid, version, day), never a transcript sibling.
    fresh_paths = [f for f in todays if (f.stem, FACTS_VERSION, day_stamp, ERA_EVENT) not in known]
    appended = append_facts(derive_batch(fresh_paths, day_stamp), st)

    # T09 era filter: every metric input below is event-era only. T08's backfill
    # shares this store with era:"transcript" rows (dash-string fields) whose days
    # land in the current week for real — unfiltered, compute_metrics crashes on
    # the dashes. read_rows stays era-blind by DEFAULT for T08's report; here the
    # filter runs INSIDE the reader, BEFORE the latest-per-sid collapse (W2-F7) —
    # a transcript row that outranks its event-era sibling must not swallow the sid.
    all_rows = read_rows(state=st, event_era_only=True)
    day_rows = [r for r in all_rows if r.get("day") == day_stamp]
    # The publish seam (see delta_row): store rows stay cumulative; the DAY series
    # gets each row minus its predecessor, so a grown file's earlier days are never
    # re-counted. A shrunk file warns and publishes nothing for that sid this day.
    preds = predecessors(day_stamp, st)
    day_deltas = []
    for r in day_rows:
        prev = preds.get(str(r.get("sid")))
        d = delta_row(r, prev)
        if d is None:
            # A darkening (shrink with a predecessor), not a first-ever absence —
            # raise the SAME alarm channel the golden gate uses: stderr alone is
            # invisible exactly when eyes are needed (a version bump). delta_row
            # only returns None when a predecessor exists; the guard keeps that
            # invariant explicit.
            if prev is not None:
                _emit_alarm(
                    f"delta darkening: sid {r.get('sid')!r} shrank vs its "
                    f"{prev.get('day')} baseline — published nothing for it this day",
                    [],
                )
            continue
        day_deltas.append(d)
    if holes_fn is not None and callable(holes_fn):
        holes, holes_reason = holes_fn(day), ""
    else:
        holes, holes_reason = _coroner_holes(day, ev)
    metrics_day = compute_metrics(day_deltas, holes, holes_reason or "no hole source provided")
    written = publish_series(day_stamp, metrics_day, reg, st)
    # M7: the store-derived outcome tier publishes its series days here too —
    # guarded, fail-open (a warn, never a lost T06 publish).
    written += _publish_outcome_series(day_stamp, st)

    # W6-1 (supersedes W5-5's week recompute): the weekly log cells aggregate THE
    # PUBLISHED DAY SERIES just written above — the single-source law (see
    # log_cells). No store row is re-read for a weekly cell; the full registry
    # (T06 + outcome tier) pins the current series versions.
    try:
        import kaizen_outcomes  # noqa: PLC0415 - lazy; avoids a module-import cycle

        full_reg = kaizen_outcomes.registry()
    except Exception as exc:
        _warn(f"outcome registry unavailable ({exc!r}) — weekly cells use the T06 set only")
        full_reg = reg
    cells = log_cells(day, full_reg, state=st)
    for lp in logs:
        upsert_log_row(lp, cells)

    print(
        f"kaizen_collect_v2: {day_stamp} — {len(todays)} session file(s), "
        f"{appended} new fact row(s), {len(written)} series append(s)"
    )
    if not no_mail:
        note = "" if holes is not None else f"hole_count {DASH} — {holes_reason}"
        send_mail(root, _compose_mail(day, metrics_day, note))
    return 0


# ── selftest — golden + duplex, everything in tmp ─────────────────────────────────────


@contextlib.contextmanager
def _pinned_env(pairs: dict[str, str]) -> Iterator[None]:
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


_SELFTEST_LOG = (
    "# selftest log\n\n| " + " | ".join(COLUMNS) + " |\n|" + "---|" * len(COLUMNS) + "\n"
)


def selftest() -> int:
    """Duplex canary: the committed golden corpus PASSES, a tampered one REFUSES
    (alarm event, nothing published, dashed row), a torn line lands in the
    unclassified rate, the registry refuses an unpaired definition, and a version
    bump leaves the old series byte-identical. Everything writes to tmp only."""
    failures: list[str] = []

    def expect(cond: bool, what: str) -> None:
        if not cond:
            failures.append(what)

    repo_golden = REPO / "tests" / "fixtures" / "kaizen-golden"
    expect(repo_golden.is_dir(), f"golden corpus missing at {repo_golden}")
    expect(golden_check(repo_golden) == [], "committed golden corpus must derive clean")

    expect(len(registry()) == len(METRIC_DEFS), "registry must load the full M1 set")
    try:
        validate_registry([{"id": "lonely", "version": 1, "formula": "x"}])
        expect(False, "an unpaired metric definition must raise")
    except ValueError:
        pass

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ev = root / "events"
        st = root / "state"
        ev.mkdir()
        log = root / "kaizen-log.md"
        log.write_text(_SELFTEST_LOG, encoding="utf-8")

        # Hermetic env: blank the session ids too — run from a live Claude session,
        # ARM 1's instrument_alarm otherwise lands in `<live sid>.jsonl` instead of
        # unknown.jsonl and ARM 2 then derives SIX sessions, not five (pre-existing
        # environmental flake, fixed in fix-wave 2).
        pinned = {
            "KAIZEN_EVENTS_DIR": str(ev),
            "KAIZEN_STATE_DIR": str(st),
            "CLAUDE_CODE_SESSION_ID": "",
            "CLAUDE_SESSION_ID": "",
        }

        # ARM 1 — tampered expectations must REFUSE: alarm, nothing published, dashes.
        tampered = root / "golden"
        shutil.copytree(repo_golden, tampered)
        exp = json.loads((tampered / "expected.json").read_text(encoding="utf-8"))
        exp["totals"]["lines_total"] += 1
        (tampered / "expected.json").write_text(json.dumps(exp), encoding="utf-8")
        with _pinned_env(pinned):
            rc = daily(
                dt.date(2026, 8, 18),
                events=ev,
                state=st,
                golden=tampered,
                log_paths=[log],
                no_mail=True,
                holes_fn=lambda d: 0,
            )
        expect(rc != 0, "a golden mismatch must exit non-zero")
        expect(not (st / "series").exists(), "a refused run must publish NO series")
        expect(not facts_path(st).exists(), "a refused run must derive NO facts")
        alarm = any(
            "instrument_alarm" in p.read_text(encoding="utf-8", errors="replace")
            for p in ev.glob("*.jsonl")
        )
        expect(alarm, "a refused run must emit an instrument_alarm event")
        logged = log.read_text(encoding="utf-8")
        expect(DASH in logged and "2026-08-18" in logged, "the refused row must render dashes")

        # ARM 2 — the good corpus as live events must publish.
        for f in repo_golden.glob("*.jsonl"):
            shutil.copy(f, ev / f.name)  # fresh mtime = today
        with _pinned_env(pinned):
            rc = daily(
                dt.date.today(),
                events=ev,
                state=st,
                golden=repo_golden,
                log_paths=[log],
                no_mail=True,
                holes_fn=lambda d: 2,
            )
        expect(rc == 0, "a green golden gate must publish")
        rows = read_rows(state=st)
        expect(len(rows) == 5, f"5 golden sessions must derive (got {len(rows)})")
        expect((st / "series").is_dir() and any((st / "series").iterdir()), "series must land")

        # ARM 3 — a torn line lands in the unclassified rate with a reason, no crash.
        torn = root / "torn-session.jsonl"
        torn.write_text('{"schema":1,"ts":"2026-08-18T0\n', encoding="utf-8")
        row = derive_session(torn)
        expect(
            row is not None
            and row["lines_unclassified"] == 1
            and row["unclassified_reasons"] == {"unparseable-json": 1},
            "a torn line must count as unclassified with its reason",
        )

        # ARM 4 — a definition version bump leaves the published files byte-identical.
        published = sorted((st / "series").glob("*.jsonl"))
        before = {p: p.read_bytes() for p in published}
        bumped = {
            mid: {
                **d,
                "version": int(d["version"]) + 1,
                "hash": _def_hash({**d, "version": int(d["version"]) + 1}),
            }
            for mid, d in registry().items()
        }
        metrics = compute_metrics(rows, holes=1)
        publish_series(dt.date.today().isoformat(), metrics, bumped, st)
        expect(
            all(p.read_bytes() == before[p] for p in published),
            "recompute at a bumped version must leave every published series byte-identical",
        )
        expect(
            bool(set((st / "series").glob("*.jsonl")) - set(published)),
            "recompute at a bumped version must write NEW versioned series files",
        )

    if failures:
        for msg in failures:
            print(f"✗ selftest: {msg}")
        return 1
    print(
        "✓ selftest: golden corpus green; tampered corpus refused (alarm + nothing "
        "published + dashed row); torn line counted with reason; unpaired registry "
        "definition refused; v1 series byte-identical after v2 recompute"
    )
    return 0


# ── cli ───────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--daily", action="store_true", help="consolidate one day (default: yest.)")
    mode.add_argument("--golden-check", action="store_true", help="run the assertion gate only")
    mode.add_argument("--selftest", action="store_true", help="duplex canary in tmp dirs")
    ap.add_argument("--day", help="YYYY-MM-DD to consolidate (default: yesterday)")
    ap.add_argument("--no-mail", action="store_true", help="skip the hand-off mail")
    ap.add_argument("--repo-root", type=Path, default=REPO)
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.golden_check:
        mismatches = golden_check()
        for m in mismatches:
            _warn(f"GOLDEN MISMATCH: {m}")
        print("golden corpus: " + ("MISMATCH" if mismatches else "green"))
        return 1 if mismatches else 0
    day = dt.date.fromisoformat(args.day) if args.day else dt.date.today() - dt.timedelta(days=1)
    return daily(day, repo_root=args.repo_root.resolve(), no_mail=args.no_mail)


if __name__ == "__main__":
    raise SystemExit(main())
