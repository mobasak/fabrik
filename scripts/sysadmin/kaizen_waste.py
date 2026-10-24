#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/kaizen-waste-define.md, docs/workstation/kaizen.md, tests/test_kaizen_waste.py
"""Kaizen token-waste series — Lean Six Sigma MEASURE for the fleet's token burn (W-02472911, D-1118).

The operator ruled that token burn is run as a process, not bought away: "we must measure it as like
lean six sigma and kaizen and our kaizen agent should adress the issues." This module computes six
waste categories per LOCAL day from ledgers that already exist and publishes them into the kaizen
series store (``kaizen_collect_v2.publish_series``) beside a per-agent / per-command breakdown;
``kaizen_digest.py`` judges each series on a frozen XmR control chart. The categories, formulas and
their limits are DEFINEd in ``docs/reference/kaizen-waste-define.md`` — that page is the contract,
this docstring only maps it to code.

Sources (all read-only; each env-overridable so a test never reads live state):
- ``command-feedback.jsonl`` beside the run-record dir (``$COMMAND_RUN_DIR``'s parent, as
  ``command_run.py`` resolves it) — one row per closed run with ``tok_*`` fields;
- ``$AGENT_IDENTITY_FILE`` (``agent-identity.jsonl``) — every session binding;
- transcripts under ``$KAIZEN_TRANSCRIPT_ROOTS`` (``os.pathsep``-separated; default
  ``~/.claude/projects`` and ``~/.claude-fleet/*/projects``) — the context a new session rebuilt;
- ``git log`` of ``$KAIZEN_WASTE_GIT_REPO`` (default this repo) at ``$KAIZEN_WASTE_GIT_REF``
  (default ``origin/master``) — the one bounded read-only git call the daily tier makes.

Honesty (the kaizen rule): a day a source had not yet recorded its field publishes NOTHING, never 0;
a git failure is unmeasurable with its reason, never 0. Ledger rows are TOP-LEVEL closes only — a
nested run's window overlaps its parent's (``command_run.py``'s token-window note).

Cobra (D-253): every metric is paired with the counter that rises when it is gamed
(``WASTE_METRIC_DEFS``' ``counter_metric``, enforced reciprocal by ``validate_registry``); the
cheapest way to satisfy each is written beside it on the DEFINE page.

Usage:
    kaizen_waste.py --day 2026-10-21            # print one day's six readings
    kaizen_waste.py --publish --day 2026-10-21  # publish one day (never today or later)
    kaizen_waste.py --backfill [--since D]      # every publishable day, oldest first, idempotent
    kaizen_waste.py --rebaseline METRIC --from D --reason "kaizen closed W-…"
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kaizen_collect_v2 as kc  # noqa: E402 - same directory (registry, store, publish)
from kaizen_collect_v2 import DASH, MetricResult  # noqa: E402 - the shared result shape

REPO = Path(__file__).resolve().parents[2]
GIT_TIMEOUT_S = 20
MIN_CLOSES = 20  # a ratio day with fewer top-level closes is plotted, never judged (digest)
BREAKDOWN_VERSION = 1

_RED = re.compile(
    r"\b(?:red master|master (?:is |went |turned )?red|red on master(?!['’]s)|master red)\b", re.I
)
# A phrase is a hypothetical, not a red master, when a modal sits among the six words before it
# in its own clause ("it would turn master red", "would read red on master without this"). The
# clause ends at , . ; : ! ? ( ) but never at a newline: commit bodies wrap mid-clause.
# Cobra (D-253): the cheap way to lower the count is a modal in front of a real phrase ("it would
# seem master went red") — the same move as not writing the phrase at all, which the define doc
# already names; measured on origin/master 2026-10-24 the rule dropped 3 of 32 hits, all three
# not-rework (2edc9545f, 0e8aacd73, 30ffaabe2), and added none.
_MODAL = re.compile(r"^(?:would|could|should|might|may|will|can)(?:n['’]t)?$", re.I)
_CLAUSE_BREAK = re.compile(r"[,.;:!?()]")
_FIX_SUBJECT = re.compile(r"^(?:fix|test|revert)\b", re.I)
_AGENT_NAME = re.compile(
    r"^Agent-Name:[ \t]*(\S+)", re.M
)  # [ \t]: a bare key never takes the next line
_QUOTA = re.compile(r"quota", re.I)
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")

WASTE_METRIC_DEFS: tuple[dict, ...] = (
    {
        "id": "waste_context_per_call",
        "version": 1,
        "counter_metric": "waste_rotation_rebuild",
        "formula": "sum tok_cache_read / sum tok_msgs over the day's top-level closes with tok_msgs > 0",
    },
    {
        "id": "waste_rotation_rebuild",
        "version": 1,
        "counter_metric": "waste_context_per_call",
        "formula": (
            "sum of the first assistant message's input + cache_creation + cache_read tokens over the "
            "day's rotations (a new session_id for a name already bound before); 0 when none"
        ),
    },
    {
        "id": "waste_seat_share",
        "version": 1,
        "counter_metric": "waste_red_master_rework",
        "formula": "100 * sum of the four tok_seat_* / sum of lead + seat tokens over top-level closes",
    },
    {
        "id": "waste_red_master_rework",
        # v2 (W-d633d5f5): a phrase with a modal among the six words before it in its clause
        # ("would turn master red") and the possessive "red on master's" no longer count
        "version": 2,
        "counter_metric": "waste_seat_share",
        "formula": (
            "non-merge commits that reached the ref that day (first-parent committer date) with a "
            "fix-shaped subject and a word-bounded red-master phrase that is neither a hypothetical "
            "(a modal among the six words before it in its clause) nor the possessive "
            "'red on master's'"
        ),
    },
    {
        "id": "waste_wall_rate",
        "version": 1,
        "counter_metric": "waste_output_per_call",
        "formula": "100 * closes blocked at a quota wall (wall == quota) / top-level closes",
    },
    {
        "id": "waste_output_per_call",
        "version": 1,
        "counter_metric": "waste_wall_rate",
        "formula": "sum tok_out / sum tok_msgs over the day's top-level closes with tok_msgs > 0",
    },
)
_SEAT_FIELDS = ("tok_seat_in", "tok_seat_out", "tok_seat_cache_read", "tok_seat_cache_create")
_LEAD_FIELDS = ("tok_in", "tok_out", "tok_cache_read", "tok_cache_create")


def registry() -> dict[str, dict]:
    """The waste set alone — its three pairs are internal, so it validates standalone."""
    return kc.validate_registry(WASTE_METRIC_DEFS)


# ── sources ──────────────────────────────────────────────────────────────────────────


def feedback_path() -> Path:
    raw = os.environ.get("COMMAND_RUN_DIR")
    runs = Path(raw) if raw else Path.home() / ".claude" / "state" / "command-runs"
    return runs.parent / "command-feedback.jsonl"


def identity_path() -> Path:
    raw = os.environ.get("AGENT_IDENTITY_FILE")
    return Path(raw) if raw else Path.home() / ".claude" / "state" / "agent-identity.jsonl"


def transcript_roots() -> list[Path]:
    raw = os.environ.get("KAIZEN_TRANSCRIPT_ROOTS")
    if raw:
        return [Path(p) for p in raw.split(os.pathsep) if p]
    home = Path.home()
    return [
        home / ".claude" / "projects",
        *map(Path, sorted(glob.glob(str(home / ".claude-fleet/*/projects")))),
    ]


def _jsonl(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return []
    rows = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def local_day(ts: object) -> str | None:
    try:
        return dt.datetime.fromtimestamp(float(ts)).date().isoformat()  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _num(v: object) -> float | None:
    """A finite number, else None — a torn or hand-edited ledger value (a string, NaN, a bool)
    is absent, never a crash that costs the whole day's publish."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        f = float(v)
    except OverflowError:  # an int past the float range (a hand-edited row)
        return None
    return f if math.isfinite(f) else None


def _int(row: dict, key: str) -> int:
    """A token count. None means the writer summed nothing — measured on the live ledger, every
    `tok_seat_in: None` row has no seat seen or skipped and every `tok_cache_read: None` row has
    no turns — so 0 is that row's true value, not an unknown."""
    v = _num(row.get(key))
    return int(v) if v is not None else 0


def _first_day(rows: list[dict], field: str) -> str | None:
    days = [d for r in rows if field in r and (d := local_day(r.get("ts")))]
    return min(days) if days else None


def _agent(row: dict) -> str:
    return str(row.get("agent") or "") or "unattributed"


# ── the six metrics ──────────────────────────────────────────────────────────────────


def _bd(by: str, key: str, num: float, den: float, value: float | None) -> dict:
    return {"by": by, "key": key, "numerator": num, "denominator": den, "value": value}


def _ratio(
    mid: str,
    rows: list[dict],
    num_of,
    den_of,
    *,
    closes: int,
    scale: float = 1.0,
    unit: str,
    detail: str,
) -> tuple[MetricResult, list[dict]]:
    """One ratio metric over the day's rows, with its per-agent and per-command cut. ``closes``
    is the day's TOP-LEVEL close count — the digest's 20-close judging floor reads it."""
    num = sum(num_of(r) for r in rows)
    den = sum(den_of(r) for r in rows)
    if den <= 0:
        return MetricResult.unavailable(
            mid, f"no top-level close with a denominator ({detail})"
        ), []
    value = scale * num / den
    cut: list[dict] = [_bd("total", "closes", closes, closes, closes)]
    for by, key_of in (("agent", _agent), ("command", lambda r: str(r.get("command") or "?"))):
        groups: dict[str, list[dict]] = collections.defaultdict(list)
        for r in rows:
            groups[key_of(r)].append(r)
        for key, rs in sorted(groups.items()):
            n, d = sum(num_of(r) for r in rs), sum(den_of(r) for r in rs)
            cut.append(_bd(by, key, n, d, (scale * n / d) if d > 0 else None))
    cell = f"{value:,.1f}{unit} (n={len(rows)})"
    return MetricResult(mid, cell, detail, True, value, int(num), int(den)), cut


def _ledger_metrics(day: str) -> dict[str, tuple[MetricResult, list[dict]]]:
    allrows = _jsonl(feedback_path())
    todays = [r for r in allrows if local_day(r.get("ts")) == day]
    top = [r for r in todays if not r.get("parent")]
    nested = len(todays) - len(top)
    with_msgs = [r for r in top if _int(r, "tok_msgs") > 0]
    zero = len(top) - len(with_msgs)
    partial = sum(1 for r in top if r.get("tok_partial"))
    note = f"{nested} nested excluded · {zero} zero-turn · {partial} partial"
    out: dict[str, tuple[MetricResult, list[dict]]] = {}

    def gated(mid: str, field: str, build):
        first = _first_day(allrows, field)
        if first is None or day < first:
            out[mid] = (MetricResult.unavailable(mid, f"{field} not yet recorded on {day}"), [])
        else:
            out[mid] = build()

    gated(
        "waste_context_per_call",
        "tok_msgs",
        lambda: _ratio(
            "waste_context_per_call",
            with_msgs,
            lambda r: _int(r, "tok_cache_read"),
            lambda r: _int(r, "tok_msgs"),
            closes=len(top),
            unit=" tok/call",
            detail=note,
        ),
    )
    gated(
        "waste_output_per_call",
        "tok_msgs",
        lambda: _ratio(
            "waste_output_per_call",
            with_msgs,
            lambda r: _int(r, "tok_out"),
            lambda r: _int(r, "tok_msgs"),
            closes=len(top),
            unit=" tok/call",
            detail=note,
        ),
    )
    rounds = [_int(r, "rounds") for r in top if _int(r, "rounds") > 0]
    rounds_note = f"mean rounds {sum(rounds) / len(rounds):.1f}" if rounds else "no rounds"
    gated(
        "waste_seat_share",
        "tok_seat_in",
        lambda: _ratio(
            "waste_seat_share",
            [r for r in top if "tok_seat_in" in r],
            lambda r: sum(_int(r, f) for f in _SEAT_FIELDS),
            lambda r: sum(_int(r, f) for f in (*_SEAT_FIELDS, *_LEAD_FIELDS)),
            closes=len(top),
            scale=100.0,
            unit="%",
            detail=f"{rounds_note} · {note}",
        ),
    )
    waited = sum(
        _num(r.get("gap_s")) or 0.0
        for r in top
        if isinstance(r.get("resumed_from"), dict)
        and _QUOTA.search(str(r["resumed_from"].get("reason") or ""))
    )
    gated(
        "waste_wall_rate",
        "wall",
        lambda: _ratio(
            "waste_wall_rate",
            top,
            lambda r: 1 if r.get("state") == "blocked" and r.get("wall") == "quota" else 0,
            lambda r: 1,
            closes=len(top),
            scale=100.0,
            unit="%",
            detail=f"{waited / 3600:.1f} h waited after quota walls (resumed closes) · {note}",
        ),
    )
    return out


def _find_transcript(sid: str, roots: list[Path]) -> Path | None:
    for root in roots:
        hits = sorted(root.glob(f"*/{sid}.jsonl"))
        if hits:
            return hits[0]
    return None


def _birth_context(path: Path) -> int | None:
    """input + cache_creation + cache_read of the session's FIRST assistant message, or None
    (unknown) when the file cannot be read or holds no usage yet. An agent binds its name through
    a tool call — a model call — so a rotated session always has a usage line once flushed: no
    usage means not yet written, never "rebuilt nothing", and a 0 here would be published for good."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"assistant"' not in line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                msg = row.get("message") if isinstance(row, dict) else None
                usage = (
                    msg.get("usage")
                    if isinstance(msg, dict) and row.get("type") == "assistant"
                    else None
                )
                if isinstance(usage, dict):
                    return sum(
                        _int(usage, k)
                        for k in (
                            "input_tokens",
                            "cache_creation_input_tokens",
                            "cache_read_input_tokens",
                        )
                    )
    except OSError:
        return None
    return None


def rotation_rebuild(day: str) -> tuple[MetricResult, list[dict]]:
    mid = "waste_rotation_rebuild"
    rows = sorted(_jsonl(identity_path()), key=lambda r: _num(r.get("at")) or 0.0)
    if not rows:
        return MetricResult.unavailable(mid, "agent-identity store empty or absent"), []
    first = local_day(rows[0].get("at"))
    if first is None or day < first:
        return MetricResult.unavailable(mid, f"identity store not yet recorded on {day}"), []
    seen: set[tuple[str, str]] = set()
    names: set[str] = set()
    rotations: list[tuple[str, str]] = []
    for r in rows:
        name, sid = str(r.get("name") or ""), str(r.get("session_id") or "")
        if not name or not sid or (name, sid) in seen:
            continue
        seen.add((name, sid))
        if name in names and local_day(r.get("at")) == day:
            rotations.append((name, sid))
        names.add(name)
    if not rotations:
        return MetricResult(mid, "0 (no rotation)", "", True, 0, 0, 0), [
            _bd("total", "rotations", 0, 0, 0)
        ]
    roots = transcript_roots()
    per_agent: dict[str, int] = collections.Counter()
    found, unfound, total = 0, 0, 0
    for name, sid in rotations:
        path = _find_transcript(sid, roots)
        size = _birth_context(path) if path else None
        if size is None:
            unfound += 1
            continue
        found += 1
        total += size
        per_agent[name] += size
    if unfound:
        # a partial total published as the day's value would be frozen low for good (the
        # publish is idempotent per day): the day stays unmeasured until every transcript reads
        return MetricResult.unavailable(
            mid,
            f"{unfound} of {len(rotations)} rotation transcript(s) unfound or without usage yet",
        ), []
    cut = [_bd("total", "rotations", found, found, found)]
    cut += [_bd("agent", k, v, 1, v) for k, v in sorted(per_agent.items())]
    return MetricResult(
        mid, f"{total:,} tok (n={found} rotations)", "", True, total, total, found
    ), cut


def _git(args: list[str]) -> str:
    repo = os.environ.get("KAIZEN_WASTE_GIT_REPO") or str(REPO)
    r = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, timeout=GIT_TIMEOUT_S
    )
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} rc={r.returncode}: {r.stderr.strip()[:200]}")
    return r.stdout


def _refreshed_at(ref: str) -> float:
    """When ``ref`` last learned the remote's state: the newest of its tip's commit time, its newest
    reflog entry (a push or a fetch that moved it) and FETCH_HEAD's mtime when its last fetch carried
    the ref's branch (such a fetch counts even when it changed nothing). A quiet day on master has no
    commit after it, but the ref still refreshes."""
    stamps = [float(_git(["log", "-1", "--format=%ct", ref]).strip() or 0)]
    try:
        last = _git(["reflog", "show", "--date=unix", "-1", ref])
        m = re.search(r"@\{(\d+)\}", last)
        if m:
            stamps.append(float(m.group(1)))
    except RuntimeError:
        pass  # no reflog for the ref: the other stamps decide
    try:
        fetch_head = Path(_git(["rev-parse", "--git-common-dir"]).strip()) / "FETCH_HEAD"
        if not fetch_head.is_absolute():
            fetch_head = Path(os.environ.get("KAIZEN_WASTE_GIT_REPO") or str(REPO)) / fetch_head
        # FETCH_HEAD vouches only when its last fetch carried this ref's branch: a fetch of another
        # branch rewrites the file too and would pass a stale ref off as a quiet day
        branch = ref.rsplit("/", 1)[-1]
        if f"branch '{branch}' of" in fetch_head.read_text(encoding="utf-8", errors="replace"):
            stamps.append(fetch_head.stat().st_mtime)
    except (OSError, RuntimeError):
        pass
    return max(stamps)


def _is_red_master_rework(msg: str) -> bool:
    """A fix-shaped message carrying at least one red-master phrase that is not a hypothetical."""
    if not _FIX_SUBJECT.match(msg):
        return False
    for m in _RED.finditer(msg):
        clause = _CLAUSE_BREAK.split(msg[max(0, m.start() - 80) : m.start()])[-1]
        if not any(_MODAL.match(w) for w in clause.split()[-6:]):
            return True
    return False


def red_master_rework(day: str) -> tuple[MetricResult, list[dict]]:
    mid = "waste_red_master_rework"
    ref = os.environ.get("KAIZEN_WASTE_GIT_REF") or "origin/master"
    d = dt.date.fromisoformat(day)
    # each bound is its own local midnight (a DST day is 23 or 25 hours), and the window is
    # half-open in Python: git's --since/--until are both inclusive, so a commit stamped exactly
    # at midnight would count on two days
    start = dt.datetime.combine(d, dt.time()).astimezone().timestamp()
    end = dt.datetime.combine(d + dt.timedelta(days=1), dt.time()).astimezone().timestamp()
    try:
        if _refreshed_at(ref) < end:
            # a ref not refreshed since the day ended reads as a quiet day — an unknown, never a 0
            return MetricResult.unavailable(
                mid, f"{ref} not refreshed since {day} ended (stale ref)"
            ), []
        arrivals = _git(
            [
                "log",
                ref,
                "--first-parent",
                f"--since=@{int(start) - 1}",
                f"--until=@{int(end) + 1}",
                "--format=%H %ct %P",
            ]
        )
        shas: list[str] = []
        for line in arrivals.splitlines():
            sha, ct, *parents = line.split()
            if not start <= float(ct) < end:
                continue
            if len(parents) > 1:
                shas += _git(["log", "--no-merges", "--format=%H", f"{parents[0]}..{sha}"]).split()
            else:
                shas.append(sha)
        messages = _git(["show", "-s", "--format=%x1e%B", *shas]).split("\x1e") if shas else []
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        return MetricResult.unavailable(mid, f"git read failed: {exc}"), []
    per_agent: dict[str, int] = collections.Counter()
    for msg in messages:
        msg = msg.strip()
        if not msg or not _is_red_master_rework(msg):
            continue
        m = _AGENT_NAME.search(msg)
        per_agent[m.group(1) if m else "unattributed"] += 1
    n = sum(per_agent.values())
    cut = [_bd("total", "arrivals", len(shas), len(shas), len(shas))]
    cut += [_bd("agent", k, v, 1, v) for k, v in sorted(per_agent.items())]
    return MetricResult(mid, f"{n} (of {len(shas)} arrivals)", "", True, n, n, len(shas)), cut


def compute_day(day: str) -> dict[str, tuple[MetricResult, list[dict]]]:
    out = _ledger_metrics(day)
    out["waste_rotation_rebuild"] = rotation_rebuild(day)
    out["waste_red_master_rework"] = red_master_rework(day)
    return out


# ── publish, backfill, rebaseline ────────────────────────────────────────────────────


def breakdown_path(state: Path | None = None) -> Path:
    return (state or kc.state_dir()) / f"waste-breakdown@v{BREAKDOWN_VERSION}.jsonl"


def baselines_path(state: Path | None = None) -> Path:
    return (state or kc.state_dir()) / "waste-baselines.jsonl"


def publish_bound(today: str, state: Path | None = None) -> str:
    """min(yesterday, the newest NON-waste series day): a waste file must never move the
    collector's newest-day guard (``kaizen_collect_v2._latest_series_day`` reads every series)."""
    yesterday = (dt.date.fromisoformat(today) - dt.timedelta(days=1)).isoformat()
    sdir = (state or kc.state_dir()) / "series"
    days: set[str] = set()
    for p in sorted(sdir.glob("*.jsonl")) if sdir.is_dir() else []:
        if not p.name.startswith("waste_"):
            days |= kc._series_days(p)
    return min(yesterday, max(days)) if days else yesterday


def _write_breakdown(day: str, cuts: dict[str, list[dict]], state: Path | None) -> None:
    path = breakdown_path(state)
    with kc._store_lock(path):
        have = {(r.get("day"), r.get("metric")) for r in _jsonl(path)}
        fresh = [
            {"day": day, "metric": mid, "version": BREAKDOWN_VERSION, **row}
            for mid, rows in cuts.items()
            if (day, mid) not in have
            for row in rows
        ]
        if fresh:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                for row in fresh:
                    fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def publish_day(day: str, today: str | None = None, state: Path | None = None) -> list[Path]:
    today = today or dt.date.today().isoformat()
    if day >= today:
        raise ValueError(
            f"refusing to publish {day}: only days before today ({today}) are complete"
        )
    if day > publish_bound(today, state):
        # the daily hook calls this directly: a waste-only day would move the collector's
        # newest-day guard and refuse its own catch-up, so it waits for the collector's day
        kc._warn(
            f"waste tier: {day} is past the publish bound — the collector has not published it"
        )
        return []
    computed = compute_day(day)
    # breakdown FIRST (idempotent per day and metric): a crash between the two writes then
    # leaves a breakdown whose series the next run appends, never a series whose breakdown
    # no run will ever write (publish_series skips a day it already holds)
    _write_breakdown(day, {mid: cut for mid, (m, cut) in computed.items() if m.measurable}, state)
    results = {mid: m for mid, (m, _) in computed.items()}
    return kc.publish_series(day, results, registry(), state)


RETRY_DAYS = 3  # a day unmeasured at its first publish (a ref not yet past it, a transcript
# not yet flushed) is retried on the next two daily runs; publishing is idempotent per day


def publish_recent(day: str, today: str | None = None, state: Path | None = None) -> list[Path]:
    """The daily hook's entry: publish ``day`` and the RETRY_DAYS - 1 days before it, oldest
    first, so a day that was unmeasurable once fills when its source catches up."""
    d = dt.date.fromisoformat(day)
    written: list[Path] = []
    for back in range(RETRY_DAYS - 1, -1, -1):
        one = (d - dt.timedelta(days=back)).isoformat()
        try:
            written += publish_day(one, today, state)
        except Exception as exc:  # noqa: BLE001 - fail-open per day, warned
            kc._warn(f"waste tier: {one} failed open: {exc!r}")
    return written


def backfill(
    since: str | None = None, today: str | None = None, state: Path | None = None
) -> list[Path]:
    today = today or dt.date.today().isoformat()
    first = since or _first_day(_jsonl(feedback_path()), "tok_msgs")
    if first is None:
        return []
    bound = publish_bound(today, state)
    written: list[Path] = []
    d = dt.date.fromisoformat(first)
    while d.isoformat() <= bound:
        written += publish_day(d.isoformat(), today, state)
        d += dt.timedelta(days=1)
    return written


def rebaseline(metric: str, from_day: str, reason: str, state: Path | None = None) -> Path:
    if metric not in registry():
        raise ValueError(f"unknown waste metric {metric!r}")
    _day_arg(from_day)
    if not reason.strip():
        raise ValueError("a rebaseline names its reason (the improvement it follows)")
    path = baselines_path(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "metric": metric,
        "from": from_day,
        "reason": reason.strip(),
        "at": dt.datetime.now().astimezone().isoformat(),
    }
    with kc._store_lock(path), open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


# ── cli ──────────────────────────────────────────────────────────────────────────────


def _day_arg(value: str) -> str:
    """YYYY-MM-DD only: ``fromisoformat`` also takes "20261010", which would key a series day in
    a second spelling the string-ordered readers sort apart."""
    if not _DAY.fullmatch(value):
        raise ValueError(f"{value!r} is not YYYY-MM-DD")
    dt.date.fromisoformat(value)
    return value


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--day", type=_day_arg)
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--since", type=_day_arg)
    ap.add_argument("--rebaseline", metavar="METRIC")
    ap.add_argument("--from", dest="from_day", type=_day_arg)
    ap.add_argument("--reason", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.rebaseline:
        if not a.from_day:
            ap.error("--rebaseline needs --from")
        print(rebaseline(a.rebaseline, a.from_day, a.reason))
        return 0
    if a.backfill:
        for p in backfill(a.since):
            print(p)
        return 0
    day = a.day or (dt.date.today() - dt.timedelta(days=1)).isoformat()
    if a.publish:
        if day > publish_bound(dt.date.today().isoformat()):
            print(
                f"kaizen_waste: {day} is past the publish bound — the collector has not published it",
                file=sys.stderr,
            )
            return 2
        for p in publish_day(day):
            print(p)
        return 0
    computed = compute_day(day)
    if a.json:
        print(
            json.dumps(
                {
                    mid: {"cell": m.cell, "value": m.value, "detail": m.detail, "breakdown": cut}
                    for mid, (m, cut) in computed.items()
                },
                indent=1,
            )
        )
        return 0
    for mid, (m, _) in computed.items():
        print(f"{mid}: {m.cell if m.measurable else DASH} {('— ' + m.detail) if m.detail else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
