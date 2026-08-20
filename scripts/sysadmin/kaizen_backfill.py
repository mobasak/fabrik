#!/usr/bin/env python3
# AFTER-EDIT: tests/test_kaizen_backfill.py | none
"""Kaizen T08 — noise-floor backfill over the pre-event transcript corpus.

WHY THIS EXISTS
---------------
"You cannot detect a change you cannot distinguish from Tuesday" (spec
2026-08-16-kaizen-closed-loop-v2-design.md:132-134): before M2 adjudicates anything,
per-metric variance must exist. This script (a) walks the HISTORICAL transcript corpus
ONCE and lands one derived-facts row per session — ``era: "transcript"`` — in the SAME
append-only store T06's collector writes (``kaizen_collect_v2.append_facts``, keyed
``(sid, facts_version, day)``), and (b) writes the noise-floor report
(``noise-floor@v1.md`` in the kaizen state dir): per registered metric — weekly mean,
variance, n, definition hash, era split. The variance is what M2's adjudication reads.

THE HONESTY RULE (binding, inherited)
-------------------------------------
Every registered metric is DEFINED over the typed event stream, which the transcript
era predates — so transcript-era rows report ``—`` WITH THE REASON for every metric,
never a proxy wearing the metric's name. What a transcript row DOES carry is what a
transcript honestly yields: line counts (torn/alien lines counted with a reason, never
a crash), first/last timestamps, the project directory, and the two structure-keyed
invocation channels REUSED from the M0 machinery (``kaizen_shrink_audit``:
``_transcript_files`` rglob + ``_typed_names``/``_skill_names``). Every event-only
field is an explicit ``—``.

ERA BOUNDARY (a transcript row must not shadow an event row)
------------------------------------------------------------
A file is event-era-owned — skipped, counted — ONLY on evidence of ownership: its sid
has an event file or an event-era store row. mtime vs the event epoch (earliest
event-file mtime ∪ earliest event-era store day) is a HINT, never an exclusion — a
bumped mtime (backup restore, rsync without ``-a``) must not orphan a pre-event
transcript. ``read_rows`` serves the latest row per sid, so letting a transcript row
in for an event-era sid would corrupt event metrics; the append seam re-checks
ownership right before writing (TOCTOU guard). One transient window survives that
guard by design: an in-flight session derived as transcript BEFORE its first event
lands is served transcript-era until the collector's next append for that sid — the
shadow self-corrects on that append (same-or-later day + later append order win), it
is never permanent. Likewise a still-open, still-unowned session re-derives on later
days under T06's growth carve-out — the "one row per session" shape holds only for
sessions that were already closed when the pass ran.

Bounds: ``KAIZEN_BACKFILL_SINCE`` (ISO date; default the full corpus; unparseable →
warned + ignored, fail-open). Single pass, progress per 500 files, resumable via the
store itself (known ``(sid, facts_version, day)`` keys are skipped) — a re-run at the
same facts_version leaves the store byte-identical. Roots via env
(``KAIZEN_TRANSCRIPTS_DIR``, plus T06's ``KAIZEN_STATE_DIR``/``KAIZEN_EVENTS_DIR``);
box-local, stdlib only.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import statistics
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import kaizen_collect_v2 as kc  # noqa: E402
from kaizen_shrink_audit import (  # noqa: E402  — the reused M0 extraction machinery
    _skill_names,
    _transcript_files,
    _typed_names,
)

DASH = kc.DASH
ERA_TRANSCRIPT = "transcript"
ERA_EVENT = "event"
PROGRESS_EVERY = 500
REPORT_NAME = "noise-floor@v1.md"
#: Hard per-line read bound. Corpus-measured 2026-08-20 (wc -L over every >50MB
#: transcript): largest observed line 3,510,198 bytes — 32 MiB is ~9× headroom.
#: An over-long line is drained and counted (`line-too-long`), never materialized:
#: under a cgroup memory cap the alternative is a SIGKILL, not a catchable error.
MAX_LINE_BYTES = 32 * 1024 * 1024
_CONCURRENT_REASON = "transcript era: concurrency is defined over exposure.project (event-only)"

#: Per-metric transcript-era `—` reasons — each names the missing event source, so the
#: dash is a statement, never a shrug. Metrics registered later fall back to the
#: generic reason and STILL appear in the report.
TRANSCRIPT_REASONS: dict[str, str] = {
    "rules_compliance": "run_close events do not exist pre-event-era",
    "terminator_spam": "final_block_emitted/run_close events do not exist pre-event-era",
    "premature_stop_rate": "stop verdict events do not exist pre-event-era",
    "first_attempt_gate_pass": "gate_run events do not exist pre-event-era",
    "gate_failure_taxonomy": "gate_run events do not exist pre-event-era",
    "rule_activation": "rule_activation events do not exist pre-event-era",
    "unclassified_rate": "defined over typed event lines; transcript lines are not events",
    "hole_count": (
        "defined as transcripts-without-session_end; pre-event-era EVERY transcript "
        "lacks one — it would measure era absence, not holes"
    ),
}
_GENERIC_TRANSCRIPT_REASON = (
    "requires the typed event stream; transcripts predate the sensors (no proxy — honesty rule)"
)


def _warn(msg: str) -> None:
    try:
        print(f"kaizen_backfill: {msg}", file=sys.stderr)
    except Exception:  # pragma: no cover - stderr itself is gone
        pass


# ── roots + bounds (env-overridable; tests point every one at tmp) ───────────────────


def transcripts_dir() -> Path:
    return Path(os.getenv("KAIZEN_TRANSCRIPTS_DIR", "") or (Path.home() / ".claude/projects"))


def backfill_since() -> dt.date | None:
    raw = os.getenv("KAIZEN_BACKFILL_SINCE", "").strip()
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        _warn(f"unparseable KAIZEN_BACKFILL_SINCE={raw!r} — bound ignored, full corpus walked")
        return None


def report_path(state: Path | None = None) -> Path:
    return (state or kc.state_dir()) / REPORT_NAME


def _era_of(row: dict) -> str:
    era = row.get("era")
    return era if isinstance(era, str) and era else ERA_EVENT


# ── the era boundary — event-owned sessions are never transcript-derived ─────────────


def event_epoch(state: Path, events: Path) -> dt.date | None:
    """Earliest event-file mtime date ∪ earliest event-era store day, or None."""
    days: list[dt.date] = []
    try:
        for f in events.glob("*.jsonl"):
            try:
                days.append(dt.date.fromtimestamp(f.stat().st_mtime))
            except (OSError, OverflowError, ValueError):
                continue
    except OSError:
        pass
    for row in kc._iter_facts(state):
        if _era_of(row) != ERA_EVENT:
            continue
        day = row.get("day")
        if isinstance(day, str):
            try:
                days.append(dt.date.fromisoformat(day))
            except ValueError:
                continue
    return min(days) if days else None


def event_owned_sids(state: Path, events: Path) -> set[str]:
    """Sids the event era owns: event-file stems + event-era store rows."""
    owned: set[str] = set()
    try:
        owned.update(p.stem for p in events.glob("*.jsonl"))
    except OSError:
        pass
    for row in kc._iter_facts(state):
        sid = row.get("sid")
        if isinstance(sid, str) and sid and _era_of(row) == ERA_EVENT:
            owned.add(sid)
    return owned


# ── transcript-session derivation — fail-open per line, dashes for event-only ────────


def derive_transcript_session(path: Path, project: str | None, day: str) -> dict | None:
    """One transcript file → one derived-facts row (``era: "transcript"``).

    Fail-open per line: a torn/alien/blank line is counted in
    ``unclassified_reasons`` with its reason — never a crash, never a silent skip.
    Fail-open per FILE too: unreadable OR memory-capped (100MB+ transcripts exist and
    the sanctioned run holds a hard cap — live failure 2026-08-20) → warned None,
    riding the unreadable count, never aborting the corpus walk. Lines are STREAMED,
    never slurped, for the same reason."""
    reasons: collections.Counter[str] = collections.Counter()
    typed: collections.Counter[str] = collections.Counter()
    skill: collections.Counter[str] = collections.Counter()
    first_dt: dt.datetime | None = None
    last_dt: dt.datetime | None = None
    lines_total = 0
    try:
        with open(path, "rb") as fh:  # binary: readline(n) bounds BYTES, not chars
            while True:
                chunk = fh.readline(MAX_LINE_BYTES + 1)
                if not chunk:
                    break
                lines_total += 1
                if len(chunk) > MAX_LINE_BYTES and not chunk.endswith(b"\n"):
                    # Pathological line: count it, drain to its newline WITHOUT
                    # materializing, never parse it.
                    reasons["line-too-long"] += 1
                    while True:
                        more = fh.readline(MAX_LINE_BYTES)
                        if not more or more.endswith(b"\n"):
                            break
                    continue
                # UTF-8 dirt must never skip a line — decode with replace.
                raw = chunk.decode("utf-8", errors="replace").rstrip("\r\n")
                if not raw.strip():
                    reasons["blank-line"] += 1
                    continue
                try:
                    row = json.loads(raw)
                except ValueError:
                    reasons["unparseable-json"] += 1
                    continue
                if not isinstance(row, dict):
                    reasons["not-an-object"] += 1
                    continue
                when = kc._parse_ts(row.get("timestamp"))
                if when is not None:
                    first_dt = when if first_dt is None or when < first_dt else first_dt
                    last_dt = when if last_dt is None or when > last_dt else last_dt
                # The two structure-keyed M0 channels — a quoted marker in prose never
                # counts.
                for name in _typed_names(raw):
                    typed[name] += 1
                for name in _skill_names(raw):
                    skill[name] += 1
    except OSError as exc:
        _warn(f"unreadable transcript {path.name}: {exc!r} — skipped")
        return None
    except MemoryError:
        _warn(f"transcript {path.name} exceeds the memory cap — skipped (fail-open)")
        return None

    return {
        "facts_version": kc.FACTS_VERSION,
        "era": ERA_TRANSCRIPT,
        "sid": path.stem,
        "day": day,
        "derived_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "first_ts": first_dt.isoformat(timespec="milliseconds") if first_dt else None,
        "last_ts": last_dt.isoformat(timespec="milliseconds") if last_dt else None,
        "project": project,
        # Every event-only field is an explicit `—` — the schema slot exists, the
        # event source doesn't; a {} or 0 here would be a fabricated measurement.
        "events": DASH,
        "gate": DASH,
        "runs": DASH,
        "stop_causes": DASH,
        "death_class": DASH,
        "concurrent": None,
        "concurrent_reason": _CONCURRENT_REASON,
        "lines_total": lines_total,
        "lines_unclassified": sum(reasons.values()),
        "unclassified_reasons": dict(reasons),
        "invocations": {"typed": dict(typed), "skill": dict(skill)},
    }


# ── the single-pass walk — bounded, progressed, resumable via the store ──────────────


def _append_batch(batch: list[dict], st: Path, ev: Path, summary: dict[str, object]) -> int:
    """The TOCTOU seam: the owned-sids snapshot ages over a minutes-long walk while
    concurrent sessions keep writing event files. Re-snapshot IMMEDIATELY before the
    append and drop (counted, reasoned) any row whose sid became event-owned
    mid-walk — a transcript row must never shadow an event sid."""
    owned_now = event_owned_sids(st, ev)
    fresh: list[dict] = []
    for row in batch:
        if str(row.get("sid")) in owned_now:
            summary["dropped_became_event_owned"] = int(summary["dropped_became_event_owned"]) + 1  # type: ignore[call-overload]
            _warn(
                f"sid {row.get('sid')!r} became event-owned mid-walk — "
                "transcript row dropped (counted)"
            )
            continue
        fresh.append(row)
    if not fresh:
        return 0
    return kc.append_facts(fresh, st)


def run_backfill(
    transcripts: Path | None = None,
    state: Path | None = None,
    events: Path | None = None,
) -> dict:
    """Walk the corpus once, append missing transcript-era rows, write the report.

    Exclusion law (acceptance round 1): a file is excluded from transcript
    derivation ONLY on evidence of event-era ownership (its sid has an event file or
    an event-era store row) — never on mtime alone. mtime vs the event epoch is a
    HINT (``derived_post_epoch_mtime`` counts derivations where the hint disagreed),
    because backup restores / rsync without ``-a`` / editor touches rewrite mtimes.

    Duplicate store keys (same stem + day in two project dirs): true aliases (same
    resolved real path) collapse to one derivation (``alias_duplicates``);
    genuinely distinct files pick a documented deterministic winner — richer wins by
    ``lines_total``, path asc as tie-break — and every loser is counted
    (``duplicate_key_dropped``), never silently arbitrary-by-sort-order.

    Designed as a ONE-TIME historical pass: concurrent event-era writers only ADD
    ownership while it runs, which the pre-append re-snapshot (:func:`_append_batch`)
    absorbs; nothing else mutates the transcript corpus it reads."""
    t0 = time.monotonic()
    root = (transcripts or transcripts_dir()).resolve()
    st = state or kc.state_dir()
    ev = events or kc.events_dir()
    files = _transcript_files(root)
    if not files:
        _warn(f"no transcript files under {root} — nothing to derive")
    since = backfill_since()
    epoch = event_epoch(st, ev)
    owned = event_owned_sids(st, ev)
    known = kc.known_fact_keys(st)

    summary: dict[str, object] = {
        "files": len(files),
        "appended": 0,
        "skipped_known": 0,
        "skipped_since": 0,
        "skipped_event_owned": 0,
        "skipped_unreadable": 0,
        "derived_post_epoch_mtime": 0,
        "alias_duplicates": 0,
        "duplicate_key_dropped": 0,
        "dropped_became_event_owned": 0,
    }

    def bump(key: str) -> None:
        summary[key] = int(summary[key]) + 1  # type: ignore[call-overload]

    # Phase 1 — cheap filters (stat/ownership/known-key), grouped by store key so a
    # duplicate key is resolved deterministically instead of by walk order.
    groups: dict[tuple[str, int, str], list[Path]] = {}
    for f in files:
        try:
            mday = dt.date.fromtimestamp(f.stat().st_mtime)
        except (OSError, OverflowError, ValueError):
            bump("skipped_unreadable")
            continue
        if since is not None and mday < since:
            bump("skipped_since")
            continue
        if f.stem in owned:
            bump("skipped_event_owned")
            continue
        key = (f.stem, kc.FACTS_VERSION, mday.isoformat())
        if key in known:
            bump("skipped_known")
            continue
        groups.setdefault(key, []).append(f)

    # Phase 2 — derive per key, collapse aliases, pick the documented winner.
    appended = 0
    batch: list[dict] = []
    items = sorted(groups.items())
    for i, (key, cands) in enumerate(items, 1):
        if i % PROGRESS_EVERY == 0:
            print(
                f"kaizen_backfill: {i}/{len(items)} session(s) — "
                f"{appended + len(batch)} new row(s) so far",
                flush=True,
            )
        day = key[2]
        uniq: list[Path] = []
        seen_real: set[Path] = set()
        for f in sorted(cands, key=str):
            try:
                real = f.resolve()
            except OSError:
                real = f
            if real in seen_real:
                bump("alias_duplicates")  # same real file behind a symlink — no loss
                continue
            seen_real.add(real)
            uniq.append(f)
        derived: list[tuple[dict, Path]] = []
        for f in uniq:
            try:
                rel = f.relative_to(root)
                project: str | None = rel.parts[0] if len(rel.parts) > 1 else None
            except ValueError:  # pragma: no cover - files come from root's own walk
                project = None
            row = derive_transcript_session(f, project, day)
            if row is None:
                bump("skipped_unreadable")
                continue
            derived.append((row, f))
        if not derived:
            continue
        if len(derived) > 1:
            derived.sort(key=lambda t: (-int(t[0]["lines_total"]), str(t[1])))
            for _loser_row, loser_path in derived[1:]:
                bump("duplicate_key_dropped")
                _warn(
                    f"duplicate key {key}: dropped {loser_path} "
                    "(richer-wins by lines_total, path asc) — loss counted, visible"
                )
        if epoch is not None and dt.date.fromisoformat(day) >= epoch:
            bump("derived_post_epoch_mtime")  # the hint disagreed; ownership decided
        batch.append(derived[0][0])
        if len(batch) >= PROGRESS_EVERY:
            appended += _append_batch(batch, st, ev, summary)
            batch = []
    if batch:
        appended += _append_batch(batch, st, ev, summary)
    summary["appended"] = appended

    summary["seconds"] = round(time.monotonic() - t0, 1)
    try:
        summary["store_bytes"] = kc.facts_path(st).stat().st_size
    except OSError:
        summary["store_bytes"] = 0
    summary["report"] = str(write_report(st))
    print(
        f"kaizen_backfill: done — {len(files)} file(s) walked, {appended} row(s) appended, "
        f"{summary['skipped_known']} known, {summary['skipped_since']} before since-bound, "
        f"{summary['skipped_event_owned']} event-owned, "
        f"{summary['skipped_unreadable']} unreadable, "
        f"{summary['derived_post_epoch_mtime']} derived-post-epoch, "
        f"{summary['alias_duplicates']} alias dup(s), "
        f"{summary['duplicate_key_dropped']} dup-key dropped, "
        f"{summary['dropped_became_event_owned']} became-owned dropped — "
        f"{summary['seconds']}s, store {summary['store_bytes']} bytes",
        flush=True,
    )
    return summary


# ── the noise-floor report — weekly mean/variance per metric, per era ────────────────


def _iso_week_label(day: str) -> str | None:
    try:
        year, week, _ = dt.date.fromisoformat(day).isocalendar()
    except ValueError:
        return None
    return f"{year}-W{week:02d}"


def _series_rows(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except ValueError:
                    _warn(f"torn series line in {path.name} skipped")
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        pass
    return out


def _event_stats(mid: str, mdef: dict, state: Path) -> tuple[dict | None, str, set[str]]:
    """(stats, reason-when-None, drifted-def-hashes) for one metric's event era.

    Weekly value = Σnumerator/Σdenominator over the week's published series days when
    every day carries both; otherwise the mean of the daily values. Mean + POPULATION
    variance over the weekly values (n = weeks; n=1 ⇒ variance 0.0)."""
    version = int(mdef["version"])
    rows = _series_rows(kc.series_path(mid, version, state))
    drift = {
        str(r["def_hash"])
        for r in rows
        if isinstance(r.get("def_hash"), str) and r["def_hash"] != mdef["hash"]
    }
    if not rows:
        return None, f"no published series days at v{version} — event era too young", drift
    if any(
        isinstance(r.get("value"), bool) or not isinstance(r.get("value"), int | float)
        for r in rows
    ):
        return (
            None,
            "distribution-valued; scalar noise floor undefined — read the day series "
            "for per-check counts",
            drift,
        )
    weeks: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        label = _iso_week_label(str(r.get("day")))
        if label is None:
            _warn(f"series row for {mid} carries an unparseable day {r.get('day')!r} — skipped")
            continue
        weeks[label].append(r)
    values: list[float] = []
    for label in sorted(weeks):
        wrows = weeks[label]
        nums = [r.get("numerator") for r in wrows]
        dens = [r.get("denominator") for r in wrows]
        if (
            all(isinstance(n, int) and not isinstance(n, bool) for n in nums)
            and all(isinstance(d, int) and not isinstance(d, bool) for d in dens)
            and sum(d for d in dens if isinstance(d, int)) > 0
        ):
            values.append(
                sum(n for n in nums if isinstance(n, int))
                / sum(d for d in dens if isinstance(d, int))
            )
        else:
            values.append(statistics.fmean(float(r["value"]) for r in wrows))
    if not values:
        return None, "no series day carries a parseable calendar day", drift
    return (
        {
            "mean": statistics.fmean(values),
            "variance": statistics.pvariance(values),
            "n": len(values),
        },
        "",
        drift,
    )


def _fmt(v: float) -> str:
    return f"{v:.6g}"


def _span(rows: list[dict]) -> str:
    days = sorted(str(r["day"]) for r in rows if isinstance(r.get("day"), str))
    return f"{days[0]}..{days[-1]}" if days else DASH


def render_report(state: Path | None = None) -> str:
    st = state or kc.state_dir()
    reg = kc.registry()
    all_rows = kc.read_rows(state=st)
    tr_rows = [r for r in all_rows if _era_of(r) == ERA_TRANSCRIPT]
    ev_rows = [r for r in all_rows if _era_of(r) == ERA_EVENT]

    lines = [
        "# Kaizen noise floor @v1",
        "",
        f"Generated {dt.date.today().isoformat()} by scripts/sysadmin/kaizen_backfill.py "
        "(T08). M2's adjudication reads the variance column; a change it cannot "
        "distinguish from this floor is Tuesday, not a signal.",
        "",
        "Method: event-era weekly value = Σnumerator/Σdenominator over the week's "
        "published series days (mean of daily values when a metric has no "
        "denominator); mean and POPULATION variance over those weekly values "
        "(n = weeks; n=1 ⇒ variance 0.0). Transcript-era rows carry no typed events, "
        "so every registered metric renders `—` there with its reason — never a proxy "
        "(the honesty rule).",
        "",
        f"Corpus: {len(tr_rows)} transcript-era session(s) ({_span(tr_rows)}) · "
        f"{len(ev_rows)} event-era session(s) ({_span(ev_rows)}).",
        "",
        "| metric | v | def hash | era | weekly mean | variance | n (weeks) |",
        "|---|---|---|---|---|---|---|",
    ]
    reasons: list[str] = []
    drift_notes: list[str] = []
    for mid, mdef in reg.items():
        stats, reason, drift = _event_stats(mid, mdef, st)
        if drift:
            drift_notes.append(
                f"- {mid}: series rows carry def hash(es) {sorted(drift)} ≠ registry "
                f"{mdef['hash']} — definition drift, re-check the series version"
            )
        if stats is not None:
            lines.append(
                f"| {mid} | {mdef['version']} | {mdef['hash']} | {ERA_EVENT} | "
                f"{_fmt(float(stats['mean']))} | {_fmt(float(stats['variance']))} | "
                f"{stats['n']} |"
            )
        else:
            lines.append(
                f"| {mid} | {mdef['version']} | {mdef['hash']} | {ERA_EVENT} | "
                f"{DASH} | {DASH} | 0 |"
            )
            reasons.append(f"- {mid} ({ERA_EVENT}): {reason}")
        lines.append(
            f"| {mid} | {mdef['version']} | {mdef['hash']} | {ERA_TRANSCRIPT} | "
            f"{DASH} | {DASH} | 0 |"
        )
        reasons.append(
            f"- {mid} ({ERA_TRANSCRIPT}): {TRANSCRIPT_REASONS.get(mid, _GENERIC_TRANSCRIPT_REASON)}"
        )
    if reasons:
        lines += ["", "## Reasons for `—`", ""] + reasons
    if drift_notes:
        lines += ["", "## ⚠️ Definition drift", ""] + drift_notes
    return "\n".join(lines) + "\n"


def write_report(state: Path | None = None) -> Path:
    st = state or kc.state_dir()
    st.mkdir(parents=True, exist_ok=True)
    path = report_path(st)
    path.write_text(render_report(st), encoding="utf-8")
    return path


# ── cli ──────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--backfill", action="store_true", help="walk the corpus once + write the report"
    )
    mode.add_argument(
        "--report", action="store_true", help="regenerate the report from the existing store"
    )
    ap.add_argument("--transcripts", type=Path, help="corpus root override")
    args = ap.parse_args(argv)

    if args.report:
        print(f"kaizen_backfill: report written to {write_report()}")
        return 0
    run_backfill(transcripts=args.transcripts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
