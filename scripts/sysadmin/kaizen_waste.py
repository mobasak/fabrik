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
    r"\b(?:red master|master (?:is |went |turned )?red|red on master|master red)\b", re.I
)
_FIX_SUBJECT = re.compile(r"^(?:fix|test|revert)\b", re.I)
_AGENT_NAME = re.compile(r"^Agent-Name:\s*(\S+)", re.M)
_QUOTA = re.compile(r"quota", re.I)

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
        "version": 1,
        "counter_metric": "waste_seat_share",
        "formula": (
            "non-merge commits that reached the ref that day (first-parent committer date) with a "
            "fix-shaped subject and a word-bounded red-master phrase"
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
RATIO_METRICS = frozenset(
    {"waste_context_per_call", "waste_seat_share", "waste_wall_rate", "waste_output_per_call"}
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
    return [home / ".claude" / "projects", *map(Path, sorted(glob.glob(str(home / ".claude-fleet/*/projects"))))]


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


def _int(row: dict, key: str) -> int:
    v = row.get(key)
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


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
    scale: float = 1.0,
    unit: str,
    detail: str,
) -> tuple[MetricResult, list[dict]]:
    """One ratio metric over the day's rows, with its per-agent and per-command cut."""
    num = sum(num_of(r) for r in rows)
    den = sum(den_of(r) for r in rows)
    if den <= 0:
        return MetricResult.unavailable(mid, f"no top-level close with a denominator ({detail})"), []
    value = scale * num / den
    cut: list[dict] = [_bd("total", "closes", len(rows), len(rows), len(rows))]
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
            scale=100.0,
            unit="%",
            detail=f"{rounds_note} · {note}",
        ),
    )
    waited = sum(
        float(r.get("gap_s") or 0.0)
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
    """input + cache_creation + cache_read of the session's FIRST assistant message."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"assistant"' not in line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                usage = (row.get("message") or {}).get("usage") if row.get("type") == "assistant" else None
                if isinstance(usage, dict):
                    return sum(
                        _int(usage, k)
                        for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
                    )
    except OSError:
        return None
    return None


def rotation_rebuild(day: str) -> tuple[MetricResult, list[dict]]:
    mid = "waste_rotation_rebuild"
    rows = sorted(_jsonl(identity_path()), key=lambda r: float(r.get("at") or 0))
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
        return MetricResult(mid, "0 (no rotation)", "", True, 0, 0, 0), [_bd("total", "rotations", 0, 0, 0)]
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
    if not found:
        return MetricResult.unavailable(mid, f"all {unfound} rotation transcript(s) unfound"), []
    cut = [_bd("total", "rotations", found, found, found)]
    cut += [_bd("agent", k, v, 1, v) for k, v in sorted(per_agent.items())]
    cell = f"{total:,} tok (n={found} rotations" + (f", {unfound} unfound)" if unfound else ")")
    return MetricResult(mid, cell, "", True, total, total, found), cut


def _git(args: list[str]) -> str:
    repo = os.environ.get("KAIZEN_WASTE_GIT_REPO") or str(REPO)
    r = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, timeout=GIT_TIMEOUT_S
    )
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} rc={r.returncode}: {r.stderr.strip()[:200]}")
    return r.stdout


def red_master_rework(day: str) -> tuple[MetricResult, list[dict]]:
    mid = "waste_red_master_rework"
    ref = os.environ.get("KAIZEN_WASTE_GIT_REF") or "origin/master"
    start = dt.datetime.combine(dt.date.fromisoformat(day), dt.time()).astimezone()
    end = start + dt.timedelta(days=1)
    try:
        arrivals = _git(
            ["log", ref, "--first-parent", f"--since={start.isoformat()}", f"--until={end.isoformat()}", "--format=%H %P"]
        )
        shas: list[str] = []
        for line in arrivals.splitlines():
            sha, *parents = line.split()
            if len(parents) > 1:
                shas += _git(["log", "--no-merges", "--format=%H", f"{parents[0]}..{sha}"]).split()
            else:
                shas.append(sha)
        messages = _git(["show", "-s", "--format=%x1e%B", *shas]).split("\x1e") if shas else []
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return MetricResult.unavailable(mid, f"git read failed: {exc}"), []
    per_agent: dict[str, int] = collections.Counter()
    for msg in messages:
        msg = msg.strip()
        if not msg or not _FIX_SUBJECT.match(msg) or not _RED.search(msg):
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
        raise ValueError(f"refusing to publish {day}: only days before today ({today}) are complete")
    computed = compute_day(day)
    results = {mid: m for mid, (m, _) in computed.items()}
    written = kc.publish_series(day, results, registry(), state)
    published = {p.name.split("@", 1)[0] for p in written}
    _write_breakdown(day, {mid: cut for mid, (m, cut) in computed.items() if m.measurable and mid in published}, state)
    return written


def backfill(since: str | None = None, today: str | None = None, state: Path | None = None) -> list[Path]:
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
    dt.date.fromisoformat(from_day)
    if not reason.strip():
        raise ValueError("a rebaseline names its reason (the improvement it follows)")
    path = baselines_path(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"metric": metric, "from": from_day, "reason": reason.strip(), "at": dt.datetime.now().astimezone().isoformat()}
    with kc._store_lock(path), open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


# ── cli ──────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--day")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--since")
    ap.add_argument("--rebaseline", metavar="METRIC")
    ap.add_argument("--from", dest="from_day")
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
            print(f"kaizen_waste: {day} is past the publish bound — the collector has not published it", file=sys.stderr)
            return 2
        for p in publish_day(day):
            print(p)
        return 0
    computed = compute_day(day)
    if a.json:
        print(json.dumps({mid: {"cell": m.cell, "value": m.value, "detail": m.detail, "breakdown": cut} for mid, (m, cut) in computed.items()}, indent=1))
        return 0
    for mid, (m, _) in computed.items():
        print(f"{mid}: {m.cell if m.measurable else DASH} {('— ' + m.detail) if m.detail else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
