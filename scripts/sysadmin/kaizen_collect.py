#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/kaizen.md, scripts/sysadmin/kaizen_metrics.py | none
"""Kaizen collector — measure how agents ACTUALLY behave, fleet-wide, daily.

WHY THIS REPLACES THE OLD DATA LAYER
------------------------------------
``kaizen_metrics.py`` reads exactly one directory: this repo's
``docs/development/reviews/*.md`` (grep ``/opt/`` in it → zero hits). It scored 49
files while the real evidence sat untouched:

    5,317 session transcripts · 8.2 GB · 98 projects   (2,281 in the last 7d)
    3,292 subagent runs with cost/latency/model/status/turns/errors
    237 review ledgers fleet-wide (49 hub + 188 in other projects)

A measurement system that reads the hub's own paperwork cannot see a rule pack that
agents silently violate in trade-intelligence, or a scaffold that births every new
project with a defect. This reads the execution record instead.

SCOPE — the whole coding infrastructure, not the review commands
----------------------------------------------------------------
203 artifacts are in the mandate: 27 command sources + 13 fragments, 56 rule packs,
57 gate checks, 5 hooks, 12 scaffold types, 12 fleet-synced core scripts, 21 crons.
Findings are attributed to whichever of those surfaces the evidence implicates.

THE HONESTY RULE (inherited from kaizen_metrics.py, and non-negotiable)
-----------------------------------------------------------------------
A metric that cannot be measured prints ``—`` WITH ITS REASON. It never prints a
number it did not compute, and it never prints 0 for "no data" — an empty universe
and a clean result are indistinguishable otherwise, which is exactly how
``check_reusable_modules`` scored a meaningless 0 fleet-wide.

DENOMINATORS ARE THE HARD PART
------------------------------
"20 of 91 sessions contained RULES ACTIVE" is NOT 71 violations: conversational and
read-only turns do not owe the line. The governance ties both markers to a
TASK-COMPLETING response, so the denominator here is responses carrying the final
block (``DONE:`` + ``NEXT:``), and the numerator is those that also opened with
``RULES ACTIVE``. Measuring against the wrong denominator manufactures outrage and
gets the metric ignored — worse than not measuring it.

Read-only: opens transcripts and ledgers, writes only its own JSON report.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRANSCRIPTS = Path.home() / ".claude" / "projects"
SUBAGENT_LEDGER = REPO / ".tmp" / "subagents" / "ledger.jsonl"
RUN_RECORDS = Path.home() / ".claude" / "state" / "command-runs"

_FINAL_BLOCK = re.compile(r"^DONE:\s*\S", re.M)
_NEXT_LINE = re.compile(r"^NEXT:\s*\S", re.M)
_RULES_ACTIVE = re.compile(r"^RULES ACTIVE:", re.M)
_BLOCKED = re.compile(r"^BLOCKED:\s*\S", re.M)
_DATED_LEDGER = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-")

# Round parsing is NOT re-implemented here. A naive "table row starting with a number"
# regex scored a tryton-crm user-test ledger at 1440 rounds by matching a data table,
# which would have made the fleet mean meaningless. kaizen_metrics.ledger_rounds is
# header-aware (the table's first column must actually be Round/Pass) and handles both
# shipped dialects.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kaizen_metrics import ledger_rounds  # noqa: E402


@dataclass
class Metric:
    """A measured value, or an explicit non-measurement with its reason."""

    value: str
    detail: str = ""
    measurable: bool = True

    @classmethod
    def unavailable(cls, reason: str) -> Metric:
        return cls(value="—", detail=reason, measurable=False)


@dataclass
class Report:
    day: str
    metrics: dict[str, Metric] = field(default_factory=dict)
    per_project: dict[str, dict] = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)


def _project_label(dirname: str) -> str:
    """`-opt-trade-intelligence` → `trade-intelligence`; keep anything else verbatim."""
    return dirname[5:] if dirname.startswith("-opt-") else dirname.lstrip("-")


def _iter_sessions(day: dt.date, root: Path = TRANSCRIPTS):
    """Yield (project, path) for transcripts touched on `day`.

    mtime is the selector, not a timestamp inside the file: a session spans hours and
    its rows carry their own timestamps, but the file is only complete once the session
    stops writing. Selecting by mtime measures finished work; selecting by first-row
    timestamp would keep re-counting a long-running session every day it stays open.
    """
    if not root.is_dir():
        return
    lo = dt.datetime.combine(day, dt.time.min).timestamp()
    hi = lo + 86400
    for proj_dir in sorted(root.iterdir()):
        if not proj_dir.is_dir():
            continue
        for f in proj_dir.glob("*.jsonl"):
            try:
                if lo <= f.stat().st_mtime < hi:
                    yield _project_label(proj_dir.name), f
            except OSError:
                continue


def _assistant_texts(path: Path) -> list[str]:
    """Every assistant text block in one transcript, in order."""
    out: list[str] = []
    try:
        with path.open(errors="replace") as fh:
            for line in fh:
                if '"assistant"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("type") != "assistant":
                    continue
                for c in d.get("message", {}).get("content", []) or []:
                    if isinstance(c, dict) and c.get("type") == "text":
                        out.append(c.get("text", ""))
    except OSError:
        pass
    return out


def measure_day(day: dt.date, root: Path = TRANSCRIPTS) -> Report:
    """Walk one day of sessions and compute the behaviour metrics."""
    rep = Report(day=day.isoformat())
    sessions = 0
    per_project: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    completing = 0
    complying = 0
    blocked = 0

    for project, path in _iter_sessions(day, root):
        sessions += 1
        per_project[project]["sessions"] += 1
        for text in _assistant_texts(path):
            # A task-completing response is the ONLY one that owes both markers.
            if _FINAL_BLOCK.search(text) and _NEXT_LINE.search(text):
                completing += 1
                per_project[project]["completing"] += 1
                if _RULES_ACTIVE.search(text):
                    complying += 1
                    per_project[project]["complying"] += 1
            if _BLOCKED.search(text):
                blocked += 1
                per_project[project]["blocked"] += 1

    if not sessions:
        rep.metrics["sessions"] = Metric.unavailable(
            f"no transcripts with an mtime on {day} under {root}"
        )
        rep.metrics["rules_compliance"] = Metric.unavailable("no sessions to measure")
        return rep

    rep.metrics["sessions"] = Metric(value=str(sessions), detail=f"{len(per_project)} project(s)")
    if completing:
        pct = 100 * complying / completing
        rep.metrics["rules_compliance"] = Metric(
            value=f"{pct:.0f}% ({complying}/{completing})",
            detail=(
                "share of TASK-COMPLETING responses (those carrying the DONE:/NEXT: final "
                "block) that also opened with RULES ACTIVE — conversational and read-only "
                "turns are excluded, they do not owe the line"
            ),
        )
    else:
        rep.metrics["rules_compliance"] = Metric.unavailable(
            f"{sessions} session(s) on {day} but none carried a DONE:/NEXT: final block — "
            "no task-completing response to hold to the rule"
        )
    rep.metrics["blocked_declarations"] = Metric(
        value=str(blocked), detail="responses declaring a sanctioned BLOCKED halt"
    )

    rep.per_project = {
        p: {
            "sessions": c["sessions"],
            "completing": c["completing"],
            "complying": c["complying"],
            "blocked": c["blocked"],
        }
        for p, c in sorted(per_project.items(), key=lambda kv: -kv[1]["sessions"])
    }
    return rep


def measure_subagents(day: dt.date, ledger: Path = SUBAGENT_LEDGER) -> dict[str, Metric]:
    """Cost, latency and failure rate of pool dispatches — the economics of fan-out."""
    if not ledger.exists():
        return {
            "subagent_runs": Metric.unavailable(f"no subagent ledger at {ledger}"),
        }
    runs = 0
    failed = 0
    capped = 0
    cost = 0.0
    lat: list[float] = []
    by_type: collections.Counter = collections.Counter()
    stamp = day.isoformat()
    with ledger.open(errors="replace") as fh:
        for line in fh:
            if stamp not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if not str(d.get("ts", "")).startswith(stamp):
                continue
            runs += 1
            by_type[d.get("task_type") or "?"] += 1
            status = d.get("status")
            if status == "error" or d.get("error"):
                failed += 1
            elif status == "capped":
                capped += 1
            try:
                cost += float(d.get("cost_usd") or 0)
            except (TypeError, ValueError):
                pass
            try:
                lat.append(float(d["latency_s"]))
            except (KeyError, TypeError, ValueError):
                pass
    if not runs:
        return {
            "subagent_runs": Metric.unavailable(
                f"no subagent runs stamped {stamp} in {ledger.name}"
            )
        }
    out = {
        "subagent_runs": Metric(
            value=str(runs),
            detail=f"by task_type: {dict(by_type.most_common())}",
        ),
        "subagent_failure_rate": Metric(
            value=f"{100 * failed / runs:.0f}% ({failed}/{runs})",
            detail=(
                "status=='error' or an error field. The ledger's vocabulary is "
                "done/error/capped/out_of_scope — 'ok' never appears, and treating "
                f"!= 'ok' as failure reports 100% on a healthy pool. capped={capped} "
                "(hit a limit — wasted spend, tracked separately, not a failure)"
            ),
        ),
        "subagent_cost": Metric(value=f"${cost:.2f}", detail="pool spend for the day"),
    }
    if lat:
        lat.sort()
        out["subagent_p50_latency"] = Metric(
            value=f"{lat[len(lat) // 2]:.0f}s", detail=f"n={len(lat)}, max={lat[-1]:.0f}s"
        )
    return out


def measure_review_rounds_fleetwide(day: dt.date, window_days: int = 30) -> Metric:
    """Rounds-per-plan across ALL /opt projects, not just the hub's 49 ledgers."""
    start = day - dt.timedelta(days=window_days)
    scored: list[int] = []
    unmarked = 0
    projects: set[str] = set()
    for reviews in sorted(Path("/opt").glob("*/docs/development/reviews")):
        if not reviews.is_dir():
            continue
        for path in sorted(reviews.glob("*.md")):
            m = _DATED_LEDGER.match(path.name)
            if not m:
                continue
            try:
                when = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
            if not (start <= when <= day):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # Two dialects in the wild: `## Round 3` headings and `| Round | 3 |` tables.
            # Reading only the first undercounted a 16-round ledger to zero.
            rounds = ledger_rounds(text)
            projects.add(path.parents[3].name)
            if rounds:
                scored.append(max(rounds))
            else:
                unmarked += 1
    total = len(scored) + unmarked
    if not scored:
        return Metric.unavailable(
            f"no review ledger in the last {window_days}d carries a machine-readable round "
            f"marker ({total} ledger(s) seen across {len(projects)} project(s))"
        )
    mean = sum(scored) / len(scored)
    return Metric(
        value=f"{mean:.1f} (n={len(scored)}/{total})",
        detail=(
            f"across {len(projects)} project(s), last {window_days}d; "
            f"worst: {sorted(scored, reverse=True)[:5]}; {unmarked} ledger(s) carry no "
            "machine-readable round marker and are EXCLUDED (never counted as zero)"
        ),
    )


def measure_run_records(records: Path = RUN_RECORDS) -> Metric:
    """Commands opened vs closed — abandonment, measurable only since all 27 open one."""
    if not records.is_dir():
        return Metric.unavailable(f"no run-record dir at {records}")
    opened = 0
    running = 0
    for f in records.glob("*.json"):
        try:
            d = json.loads(f.read_text(errors="replace"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        opened += 1
        if d.get("status") == "running":
            running += 1
    if not opened:
        return Metric.unavailable(
            f"no run records in {records} — all 27 commands were wired to open one on "
            "2026-08-16, so this fills in from the next invocations onward"
        )
    return Metric(
        value=f"{opened - running}/{opened} closed",
        detail=f"{running} still marked running (abandoned or in flight)",
    )


def collect(day: dt.date) -> Report:
    rep = measure_day(day)
    rep.metrics.update(measure_subagents(day))
    rep.metrics["review_rounds_fleetwide"] = measure_review_rounds_fleetwide(day)
    rep.metrics["run_records"] = measure_run_records()
    return rep


def render(rep: Report) -> str:
    lines = [f"# Kaizen collection — {rep.day}", ""]
    for name, m in rep.metrics.items():
        mark = "" if m.measurable else "  [NOT MEASURED]"
        lines.append(f"{name:26} {m.value}{mark}")
        if m.detail:
            lines.append(f"{'':26} └─ {m.detail}")
    if rep.per_project:
        lines += ["", "per project (sessions · task-completing · rules-compliant · blocked):"]
        for p, c in rep.per_project.items():
            lines.append(
                f"  {p:34} {c['sessions']:4}  {c['completing']:4}  "
                f"{c['complying']:4}  {c['blocked']:4}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kaizen collector (see module docstring).")
    ap.add_argument("--day", help="YYYY-MM-DD (default: yesterday)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a report")
    args = ap.parse_args(argv)

    day = dt.date.fromisoformat(args.day) if args.day else dt.date.today() - dt.timedelta(days=1)
    rep = collect(day)
    if args.json:
        print(
            json.dumps(
                {
                    "day": rep.day,
                    "metrics": {
                        k: {"value": v.value, "detail": v.detail, "measurable": v.measurable}
                        for k, v in rep.metrics.items()
                    },
                    "per_project": rep.per_project,
                },
                indent=2,
            )
        )
    else:
        print(render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
