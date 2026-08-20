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
import hashlib
import json
import os
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
FACTS_VERSION = 1
SCHEMA = 1
DASH = "—"
UNKNOWN = "unknown"
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
    """``(event_row, None)`` for a good line, ``(None, reason_code)`` otherwise."""
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
    reasons: collections.Counter[str] = collections.Counter()
    projects: collections.Counter[str] = collections.Counter()
    stop_causes: collections.Counter[str] = collections.Counter()
    failed_checks: collections.Counter[str] = collections.Counter()
    gate_runs = 0
    gate_pass = 0
    gate_fail = 0
    first_status: str | None = None
    opened = 0
    done = 0
    done_evidenced = 0
    blocked = 0
    rounds_max = 0
    death_class: str | None = None
    first_dt: dt.datetime | None = None
    last_dt: dt.datetime | None = None

    for raw in lines:
        row, reason = parse_line(raw, path.stem)
        if row is None:
            reasons[reason or "unclassified"] += 1
            continue
        event = str(row["event"])
        events[event] += 1
        when = dt.datetime.fromisoformat(str(row["ts"]))
        first_dt = when if first_dt is None or when < first_dt else first_dt
        last_dt = when if last_dt is None or when > last_dt else last_dt
        proj = _project_of(row)
        if proj:
            projects[proj] += 1
        if event == "gate_run":
            gate_runs += 1
            status = str(row.get("status"))
            if first_status is None:
                first_status = status
            if status == "success":
                gate_pass += 1
            else:
                gate_fail += 1
            for c in row.get("checks") or []:
                if c.get("outcome") == "fail":
                    failed_checks[str(c.get("name"))] += 1
        elif event == "run_open":
            opened += 1
        elif event == "run_close":
            if row.get("verdict") == "done":
                done += 1
                ev = row.get("evidence_hash")
                if isinstance(ev, str) and ev:
                    done_evidenced += 1
            else:
                blocked += 1
        elif event == "round":
            rounds_max = max(rounds_max, int(row["n"]))
        elif event == "stop_block":
            cause = row.get("cause")
            if isinstance(cause, str) and cause:
                stop_causes[cause] += 1
        elif event == "death":
            death_class = str(row["class"])

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
        "gate": {
            "runs": gate_runs,
            "first_status": first_status,
            "pass": gate_pass,
            "fail": gate_fail,
            "failed_checks": dict(failed_checks),
        },
        "runs": {
            "opened": opened,
            "done": done,
            "done_evidenced": done_evidenced,
            "blocked": blocked,
            "rounds_max": rounds_max,
        },
        "stop_causes": dict(stop_causes),
        "death_class": death_class,
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


def known_fact_keys(state: Path | None = None) -> set[tuple[str, int, str | None]]:
    """``(sid, facts_version, derived day)`` triples already in the store.

    The day is part of the key (the growth carve-out): a completed session's file
    never grows, so it is derived once — but a file that DOES grow onto a later day
    (the ``unknown`` accumulator, a resumed session) derives AGAIN on that day into a
    NEW appended row. A same-version, same-day re-run stays a no-op."""
    st = state or state_dir()
    out: set[tuple[str, int, str | None]] = set()
    for row in _iter_facts(st):
        sid, ver = row.get("sid"), row.get("facts_version")
        day = row.get("day")
        if isinstance(sid, str) and isinstance(ver, int):
            out.add((sid, ver, day if isinstance(day, str) else None))
    return out


def _fact_key(row: dict) -> tuple[str, int, str | None]:
    day = row.get("day")
    return (
        str(row.get("sid")),
        int(row.get("facts_version", 0)),
        day if isinstance(day, str) else None,
    )


def append_facts(rows: list[dict], state: Path | None = None) -> int:
    """Append rows not already present at their (sid, facts_version, day). Append-only:
    nothing is ever rewritten; a version bump — or a later derivation day for a file
    that grew — appends NEW rows alongside the old. The key is enforced against the
    call's OWN batch too: a duplicate inside one call appends exactly once."""
    st = state or state_dir()
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


def read_rows(since: str | None = None, state: Path | None = None) -> list[dict]:
    """Rows for T07/T08: the LATEST appended row per sid at its newest
    ``facts_version`` (a grown file's later-day re-derivation supersedes the earlier
    row; history stays verbatim in the store), optionally filtered to
    ``last_ts >= since``.

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
    ("gate", ("runs", "pass", "fail")),
    ("runs", ("opened", "done", "done_evidenced", "blocked")),
)
#: (container key or None, counter-map field name) — additive {name: count} maps.
_DELTA_MAPS: tuple[tuple[str | None, str], ...] = (
    (None, "events"),
    (None, "unclassified_reasons"),
    (None, "stop_causes"),
    ("gate", "failed_checks"),
)


def _get_in(row: dict, container: str | None, field: str) -> object:
    src = row.get(container) or {} if container else row
    return src.get(field) if isinstance(src, dict) else None


def _int_in(row: dict, container: str | None, field: str) -> int:
    val = _get_in(row, container, field)
    if isinstance(val, bool) or not isinstance(val, int):
        return 0
    return val


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

    Non-additive fields are point-in-time, not deltas: ``gate.first_status`` is kept
    only when the predecessor had no gate runs (a session's first attempt counts once,
    on the day it appeared); ``rounds_max``/``death_class``/``concurrent``/window
    timestamps carry the current row's values.
    """
    if prev is None:
        out = dict(cur)  # the store row is never mutated
        out["delta_of"] = None  # the key is part of the shape — null on a first-ever row
        return out
    out = json.loads(json.dumps(cur))  # deep copy — the store row is never mutated
    for container, fields in _DELTA_SCALARS:
        for field in fields:
            diff = _int_in(cur, container, field) - _int_in(prev, container, field)
            if diff < 0:
                _warn(
                    f"delta_row: {cur.get('sid')!r} shrank ({container or 'row'}.{field} "
                    f"went backwards) — publishing NOTHING for it this day"
                )
                return None
            dst = out[container] if container else out
            dst[field] = diff
    for container, field in _DELTA_MAPS:
        diff_map = _sub_map(_get_in(cur, container, field), _get_in(prev, container, field))
        if diff_map is None:
            _warn(
                f"delta_row: {cur.get('sid')!r} shrank ({field} lost entries) — "
                "publishing NOTHING for it this day"
            )
            return None
        dst = out[container] if container else out
        dst[field] = diff_map
    prev_gate = prev.get("gate") or {}
    if int(prev_gate.get("runs", 0) or 0) > 0:
        out["gate"]["first_status"] = None
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


# ── the metric registry — paired counters are a SCHEMA constraint ─────────────────────

METRIC_DEFS: tuple[dict, ...] = (
    {
        "id": "rules_compliance",
        "version": 1,
        "counter_metric": "terminator_spam",
        "formula": (
            "run_close events with verdict done AND a non-empty evidence_hash / all "
            "run_close events (denominator = run-record closures). Coroner/TTL closures "
            "emit no run_close; they ride hole_count."
        ),
    },
    {
        "id": "terminator_spam",
        "version": 1,
        "counter_metric": "rules_compliance",
        "formula": (
            "final_block_emitted events / run-record closures — above 1.0 means task "
            "terminators were emitted without a matching closed run."
        ),
    },
    {
        "id": "premature_stop_rate",
        "version": 1,
        "counter_metric": "first_attempt_gate_pass",
        "formula": (
            "stop_block events with cause in {run-record, promise-stall} / all stop "
            "verdicts (stop_pass + stop_block)."
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
        "version": 1,
        "counter_metric": "premature_stop_rate",
        "formula": (
            "sessions whose FIRST attributed gate_run has status success / sessions "
            "with >=1 attributed gate_run. Unattributed gate_runs sit in the unknown "
            "bucket and ride unclassified_rate."
        ),
    },
    {
        "id": "gate_failure_taxonomy",
        "version": 1,
        "counter_metric": "rule_activation",
        "formula": (
            "per-check fail counts across attributed gate_run events — the value is "
            "the {check: count} distribution, not a scalar."
        ),
    },
    {
        "id": "rule_activation",
        "version": 1,
        "counter_metric": "gate_failure_taxonomy",
        "formula": (
            "sessions with >=1 attributed rule_activation event / sessions with >=1 "
            "run-record closure. Labelled INVOCATION-TIME activation (select_rules / "
            "rubric runs) — per-edit glob firing is an M2 residual, not measured here."
        ),
    },
    {
        "id": "unclassified_rate",
        "version": 1,
        "counter_metric": "hole_count",
        "formula": (
            "(unclassified lines + sessions excluded from concurrency for a missing "
            "exposure.project) / (total lines + sessions). Instrument health, metric "
            "zero."
        ),
    },
    {
        "id": "hole_count",
        "version": 1,
        "counter_metric": "unclassified_rate",
        "formula": (
            "kaizen_coroner.holes(): transcripts-with-activity minus sessions-with-"
            "session_end for the day. Instrument health, metric zero."
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


def compute_metrics(
    rows: list[dict], holes: int | None = None, holes_reason: str = "no hole source provided"
) -> dict[str, MetricResult]:
    """Compute the M1 registered set over derived-facts rows. Every unmeasurable
    metric is ``—`` with its reason — never a fabricated 0."""
    out: dict[str, MetricResult] = {}

    def esum(name: str) -> int:
        return sum(int((r.get("events") or {}).get(name, 0)) for r in rows)

    def runs(field: str) -> int:
        return sum(int((r.get("runs") or {}).get(field, 0)) for r in rows)

    closures = runs("done") + runs("blocked")
    evidenced = runs("done_evidenced")
    if closures:
        out["rules_compliance"] = MetricResult(
            id="rules_compliance",
            cell=_pct(evidenced, closures),
            detail="run_close done-with-evidence over all run-record closures",
            value=evidenced / closures,
            numerator=evidenced,
            denominator=closures,
        )
        blocks = esum("final_block_emitted")
        out["terminator_spam"] = MetricResult(
            id="terminator_spam",
            cell=f"{blocks / closures:.2f} ({blocks}/{closures})",
            detail="final_block_emitted per run-record closure (>1.00 = spam)",
            value=blocks / closures,
            numerator=blocks,
            denominator=closures,
        )
    else:
        out["rules_compliance"] = MetricResult.unavailable(
            "rules_compliance", "no run-record closures in the window"
        )
        blocks = esum("final_block_emitted")
        out["terminator_spam"] = MetricResult.unavailable(
            "terminator_spam",
            f"no run-record closures to normalize against ({blocks} terminator block(s) seen)",
        )

    stops = esum("stop_pass") + esum("stop_block")
    if stops:
        premature = sum(
            int((r.get("stop_causes") or {}).get(c, 0)) for r in rows for c in PREMATURE_CAUSES
        )
        out["premature_stop_rate"] = MetricResult(
            id="premature_stop_rate",
            cell=_pct(premature, stops),
            detail="stop_block cause in {run-record, promise-stall} over all stop verdicts",
            value=premature / stops,
            numerator=premature,
            denominator=stops,
        )
    else:
        out["premature_stop_rate"] = MetricResult.unavailable(
            "premature_stop_rate", "no stop verdicts in the window"
        )

    gate_rows = [r for r in rows if int((r.get("gate") or {}).get("runs", 0)) > 0]
    # The first-attempt population is rows whose first_status is PRESENT — i.e. the
    # session's first attributed gate run happened in THIS window. A continuing
    # session's delta row (first_status nulled, its first attempt already counted an
    # earlier day) stays out of numerator AND denominator — it must not dilute.
    first_rows = [r for r in gate_rows if r["gate"].get("first_status") is not None]
    if first_rows:
        first_pass = sum(1 for r in first_rows if r["gate"].get("first_status") == "success")
        out["first_attempt_gate_pass"] = MetricResult(
            id="first_attempt_gate_pass",
            cell=_pct(first_pass, len(first_rows)),
            detail="sessions whose FIRST attributed gate_run happened this window and passed",
            value=first_pass / len(first_rows),
            numerator=first_pass,
            denominator=len(first_rows),
        )
    else:
        out["first_attempt_gate_pass"] = MetricResult.unavailable(
            "first_attempt_gate_pass",
            "no session had its first attributed gate_run in the window"
            + (" (continuing sessions only)" if gate_rows else ""),
        )
    if gate_rows:
        taxonomy: collections.Counter[str] = collections.Counter()
        gate_total = 0
        for r in gate_rows:
            gate_total += int(r["gate"].get("runs", 0))
            for name, count in (r["gate"].get("failed_checks") or {}).items():
                taxonomy[str(name)] += int(count)
        top = ", ".join(f"{n}={c}" for n, c in taxonomy.most_common(3))
        out["gate_failure_taxonomy"] = MetricResult(
            id="gate_failure_taxonomy",
            cell=top or f"clean (0 failing checks over {gate_total} runs)",
            detail="per-check fail counts across attributed gate_run events",
            value=dict(taxonomy),
            numerator=sum(taxonomy.values()),
            denominator=gate_total,
        )
    else:
        out["gate_failure_taxonomy"] = MetricResult.unavailable(
            "gate_failure_taxonomy", "no session carries an attributed gate_run"
        )

    closure_rows = [
        r
        for r in rows
        if int((r.get("runs") or {}).get("done", 0)) + int((r.get("runs") or {}).get("blocked", 0))
        > 0
    ]
    if closure_rows:
        activated = sum(
            1 for r in closure_rows if int((r.get("events") or {}).get("rule_activation", 0)) > 0
        )
        out["rule_activation"] = MetricResult(
            id="rule_activation",
            cell=_pct(activated, len(closure_rows)),
            detail="invocation-time activation: run-closing sessions with a rule_activation event",
            value=activated / len(closure_rows),
            numerator=activated,
            denominator=len(closure_rows),
        )
    else:
        out["rule_activation"] = MetricResult.unavailable(
            "rule_activation", "no session closed a run record in the window"
        )

    total_lines = sum(int(r.get("lines_total", 0)) for r in rows)
    uncl_lines = sum(int(r.get("lines_unclassified", 0)) for r in rows)
    excluded = sum(1 for r in rows if r.get("concurrent_reason") == "missing exposure.project")
    den = total_lines + len(rows)
    if den:
        num = uncl_lines + excluded
        out["unclassified_rate"] = MetricResult(
            id="unclassified_rate",
            cell=_pct(num, den),
            detail=(
                f"{uncl_lines} unclassified line(s) + {excluded} session(s) excluded from "
                f"concurrency (missing exposure.project) over {total_lines} lines + "
                f"{len(rows)} sessions"
            ),
            value=num / den,
            numerator=num,
            denominator=den,
        )
    else:
        out["unclassified_rate"] = MetricResult.unavailable(
            "unclassified_rate", "no lines or sessions in the window"
        )

    if holes is None:
        out["hole_count"] = MetricResult.unavailable("hole_count", holes_reason)
    else:
        out["hole_count"] = MetricResult(
            id="hole_count",
            cell=str(int(holes)),
            detail="transcripts with activity but no session_end (coroner hole metric)",
            value=int(holes),
            numerator=int(holes),
            denominator=None,
        )
    return out


# ── series publication — append-only, versioned, idempotent per day ──────────────────


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
    except OSError:
        pass
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
    """kaizen_metrics semantics, carried over: mechanical cells win, analyst-filled
    cells survive; a mechanical ``—`` yields to whatever a human/agent put there.
    ``force_dash`` (golden refusal) stamps the mechanical cells ``—`` regardless —
    a red instrument publishes no numbers — while the analyst cells still survive."""
    merged = list(new)
    for i in range(1, len(new)):
        if force_dash and i not in _ANALYST_CELLS:
            merged[i] = DASH
            continue
        if merged[i] == DASH and i < len(old) and old[i] not in ("", DASH):
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


def log_cells(day: dt.date, metrics: dict[str, MetricResult], rows: list[dict]) -> list[str]:
    """Map the v2 metrics onto the shipped kaizen-log columns. Unmapped columns stay
    ``—`` with the reason on stderr — never a fabricated value."""
    if rows:
        occ = sum(int((r.get("events") or {}).get("death", 0)) for r in rows)
        classes = {r.get("death_class") for r in rows if r.get("death_class")}
        deaths = f"{occ} occ / {len(classes)} cls"
    else:
        deaths = DASH
        _warn(f"Death-classes /wk = {DASH} — no derived sessions in the window")
    rounded = [
        int((r.get("runs") or {}).get("rounds_max", 0))
        for r in rows
        if int((r.get("runs") or {}).get("rounds_max", 0)) > 0
    ]
    if rounded:
        rounds = f"{sum(rounded) / len(rounded):.1f} (n={len(rounded)})"
    else:
        rounds = DASH
        _warn(f"Review rounds /plan = {DASH} — no session carries a round event")
    _warn(f"Lesson-class recurrence = {DASH} — no class taxonomy on lessons (analysis-half job)")
    _warn(
        f"Missed crons = {DASH} — not an event-stream metric; the liveness audit owns it "
        "(docs/workstation/liveness.md)"
    )
    return [
        day.isoformat(),
        metrics["first_attempt_gate_pass"].cell,
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


def _coroner_holes(day: dt.date) -> tuple[int | None, str]:
    try:
        import kaizen_coroner  # noqa: PLC0415 - lazy; same directory

        return int(kaizen_coroner.holes(day=day)), ""
    except Exception as exc:
        return None, f"coroner unavailable: {exc!r}"


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

    Session files are selected by mtime date (a session is derived on the day it
    stops writing — the day its record is complete), and the concurrency flag is
    computed within that day's derivation batch: rows are immutable once appended
    (the derived-facts law), so a session late-derived on a re-run sees only its own
    batch's windows. Honest limit, stated here rather than papered over.

    The DAY series is published from per-day DELTAS (see delta_row) so a grown file
    never re-counts earlier days. The human-facing weekly log cells, by contrast,
    read the latest row per sid within the ISO week — one row per sid, so no
    within-week double count, but a forever-growing accumulator's pre-week lines are
    visible in its cumulative row there. Honest boundary, stated not hidden; the
    machine-consumed publication is the series + read_rows."""
    root = repo_root or REPO
    ev = events or events_dir()
    st = state or state_dir()
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

    day_stamp = day.isoformat()
    try:
        candidates = sorted(ev.glob("*.jsonl"))
    except OSError:
        candidates = []
    todays: list[Path] = []
    for f in candidates:
        try:
            if dt.date.fromtimestamp(f.stat().st_mtime) == day:
                todays.append(f)
        except (OSError, OverflowError, ValueError):
            continue
    known = known_fact_keys(st)
    fresh_paths = [f for f in todays if (f.stem, FACTS_VERSION, day_stamp) not in known]
    appended = append_facts(derive_batch(fresh_paths, day_stamp), st)

    # T09 era filter: every metric input below is event-era only. T08's backfill
    # shares this store with era:"transcript" rows (dash-string fields) whose days
    # land in the current week for real — unfiltered, compute_metrics crashes on
    # the dashes. read_rows stays era-blind for T08's report; the filter is here,
    # at the consumption seam.
    all_rows = [r for r in read_rows(state=st) if _event_era(r)]
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
        holes, holes_reason = _coroner_holes(day)
    metrics_day = compute_metrics(day_deltas, holes, holes_reason or "no hole source provided")
    reg = registry()
    written = publish_series(day_stamp, metrics_day, reg, st)

    week = day.isocalendar()[:2]
    week_rows = [
        r
        for r in all_rows
        if isinstance(r.get("day"), str)
        and (_iso_week(r["day"]) == week if _iso_week(r["day"]) else False)
    ]
    metrics_week = compute_metrics(week_rows, holes, holes_reason or "no hole source provided")
    cells = log_cells(day, metrics_week, week_rows)
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

        # ARM 1 — tampered expectations must REFUSE: alarm, nothing published, dashes.
        tampered = root / "golden"
        shutil.copytree(repo_golden, tampered)
        exp = json.loads((tampered / "expected.json").read_text(encoding="utf-8"))
        exp["totals"]["lines_total"] += 1
        (tampered / "expected.json").write_text(json.dumps(exp), encoding="utf-8")
        with _pinned_env({"KAIZEN_EVENTS_DIR": str(ev), "KAIZEN_STATE_DIR": str(st)}):
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
        with _pinned_env({"KAIZEN_EVENTS_DIR": str(ev), "KAIZEN_STATE_DIR": str(st)}):
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

        # ARM 4 — a definition version bump leaves the published v-file byte-identical.
        v1_files = sorted((st / "series").glob("*@v1.jsonl"))
        before = {p: p.read_bytes() for p in v1_files}
        bumped = {
            mid: {**d, "version": 2, "hash": _def_hash({**d, "version": 2})}
            for mid, d in registry().items()
        }
        metrics = compute_metrics(rows, holes=1)
        publish_series(dt.date.today().isoformat(), metrics, bumped, st)
        expect(
            all(p.read_bytes() == before[p] for p in v1_files),
            "recompute at v2 must leave every v1 series byte-identical",
        )
        expect(
            any((st / "series").glob("*@v2.jsonl")),
            "recompute at v2 must write NEW versioned series files",
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
