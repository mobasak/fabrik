#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_rank_task_subagents.py
"""Rank models per task_type from the shared subagent_runs table, emit a synced doc.

Consumers: `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` (regenerated daily by
`daily_refresh.sh`), and eventually the subagents module's `pick_models` at
`/opt/fabrik-lib/subagents/subagents/select.py:76` (upstream reader is a follow-up).

Ranking formula: value = success_rate × avg_quality_score / max(avg_cost, 1e-9).
Cost is in the DENOMINATOR (value-per-dollar), matching `select.py:126`
(`rank_weight / price`). The user's original shorthand `"success × cost × quality"`
was interpreted as division of cost (not multiplication) because literal multiplication
would rank costliest models highest — contradicts the module's own "cheapest that
clears the quality bar" mandate at `select.py:5`. To invert, flip the constant.

Data path — hub-side (WSL for now):
  1. Queries `fabrik_analytics.subagent_runs` on local postgres via `sudo -u postgres psql`
     (peer auth on unix socket — TCP requires scram-sha-256 password which we don't
     wire in WSL dev). Rolls up per (task_type, model) over a 90-day window, min 3 runs.
  2. Renders a markdown doc with one `### <task_type>` section per TaskKind. Shape
     matches subagents module's `_TABLE: dict[str, list[str]]` at `select.py:58`
     so the future `pick_models` reader can parse section headers → dict.
  3. Atomic-writes to `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` via
     `_atomic_write` cloned from `rank_coding_subagents.py:345`.

Empty-pool discipline: if no (task_type, model) pair clears the min-runs threshold,
emit a stub with "No aggregated runs yet — pick_models continues to use vendored
_TABLE default." Never crashes; never wedges daily_refresh.
"""

from __future__ import annotations

import csv
import io
import math
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

DB_NAME = "fabrik_analytics"
TABLE = "subagent_runs"

WINDOW_DAYS = 90
MIN_RUNS = 3
VALUE_FORMULA_COST_IN_DENOMINATOR = (
    True  # False → success × quality × cost (literal user shorthand)
)

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "reference"
    / "kilo"
    / "TASK_SUBAGENT_SELECTION.md"
)

QUERY = f"""
SELECT task_type, model,
       COUNT(*) AS n,
       AVG(cost_usd) AS avg_cost,
       AVG(quality_score) AS avg_quality,
       SUM(CASE WHEN status='done' THEN 1.0 ELSE 0.0 END) / COUNT(*) AS success_rate
FROM {TABLE}
WHERE ts > NOW() - INTERVAL '{WINDOW_DAYS} days'
GROUP BY task_type, model
HAVING COUNT(*) >= {MIN_RUNS}
""".strip()

# psql field separator. Tab picked over comma because a comma in a task_type or model_id
# (however unlikely today — TASK_KINDS is fixed at {spec,plan,code,review,docs,research}
# and OR model IDs are `provider/model` with no `,`) would silently corrupt the fixed
# 6-column unpack: `-A -F,` does NOT emit CSV-style quoting (verified `psql --help`).
# `\t` is guaranteed absent from both column values by convention. Note this must match
# what render() and _query_rows() below use.
PSQL_FIELD_SEP = "\t"


def _query_rows() -> list[tuple[str, str, int, float, float, float]]:
    """Query the DB via `sudo -u postgres psql -A -F, --tuples-only`. Parse CSV in-Python.

    Returns list of (task_type, model, n, avg_cost, avg_quality, success_rate).
    Fail-soft: any error (DB down, table missing, permission) → empty list + stderr warning.
    """
    try:
        result = subprocess.run(
            [
                "sudo",
                "-n",
                "-u",
                "postgres",
                "psql",
                "-d",
                DB_NAME,
                "-A",
                "-F",
                PSQL_FIELD_SEP,
                "--tuples-only",
                "-c",
                QUERY,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"[rank_task_subagents] DB query failed: {exc}", file=sys.stderr)
        return []
    if result.returncode != 0:
        print(f"[rank_task_subagents] psql non-zero exit: {result.stderr.strip()}", file=sys.stderr)
        return []
    rows = []
    # delimiter must match the psql `-F` we passed (verified above).
    for line in csv.reader(io.StringIO(result.stdout), delimiter=PSQL_FIELD_SEP):
        if not line or not line[0]:
            continue
        try:
            task_type, model, n, avg_cost, avg_quality, success_rate = line
            # Empty string in `-A` output = NULL in psql. avg_cost=NULL means this
            # (task_type, model) group has NO cost signal — treating as 0.0 then
            # dividing by ~1e-9 inflates value and ranks the row #1 with no evidence.
            # Skip; operator sees the missing model and fixes the instrumentation.
            if avg_cost == "":
                print(
                    f"[rank_task_subagents] skip {task_type}/{model}: no cost signal",
                    file=sys.stderr,
                )
                continue
            # NULL avg_quality is treated as NEUTRAL (1.0) — not 0. Rationale from
            # fabrik-lib AI (UPSTREAM_FEEDBACK.md 2026-07-06): the module's auto-ledger
            # path records only objective metrics; `quality_score` is opt-in via an
            # orchestrator that calls `record_run(..., quality_score=)`. Most rows
            # will have NULL quality until orchestrators start scoring. Treating NULL
            # as 0.0 would collapse `success × quality / cost` to 0 for every un-scored
            # row and destroy the entire ranking. 1.0 gracefully degrades the formula
            # to `success / cost` when no quality signal is present.
            row = (
                task_type,
                model,
                int(n),
                float(avg_cost),
                float(avg_quality) if avg_quality else 1.0,
                float(success_rate) if success_rate else 0.0,
            )
            # Reject non-finite (NaN/inf) or negative avg_cost. `max(nan, 1e-9)` returns
            # nan (Python: NaN comparisons are always False), and `sort()` with a nan key
            # silently mis-orders. A negative avg_cost (e.g. refund credited as -0.02)
            # would clamp to 1e-9 and rank as artificial #1. Skip both explicitly.
            if not math.isfinite(row[3]) or row[3] < 0:
                print(
                    f"[rank_task_subagents] skip {task_type}/{model}: bad avg_cost {row[3]!r}",
                    file=sys.stderr,
                )
                continue
            if any(isinstance(v, float) and not math.isfinite(v) for v in row[4:]):
                print(
                    f"[rank_task_subagents] skip {task_type}/{model}: non-finite value in row {row!r}",
                    file=sys.stderr,
                )
                continue
            rows.append(row)
        except (ValueError, TypeError) as exc:
            print(f"[rank_task_subagents] skip malformed row {line!r}: {exc}", file=sys.stderr)
            continue
    return rows


def filter_min_runs(rows: list, min_n: int = MIN_RUNS) -> list:
    """Drop (task_type, model) pairs with fewer than `min_n` runs. Belt-and-braces
    around the SQL HAVING — the tests exercise the Python filter directly, and
    a fixture query that returns un-filtered data (offline test) still gets sane
    downstream behavior."""
    return [r for r in rows if r[2] >= min_n]


def _value(avg_cost: float, avg_quality: float, success_rate: float) -> float:
    if VALUE_FORMULA_COST_IN_DENOMINATOR:
        return success_rate * avg_quality / max(avg_cost, 1e-9)
    return success_rate * avg_quality * avg_cost


def render(rows: list) -> str:
    """Emit the ranked markdown from aggregated rows.

    Rows shape: (task_type, model, n, avg_cost, avg_quality, success_rate).
    Empty rows → stub with "No aggregated runs yet" line.
    """
    today = (
        date.today().isoformat()
        if os.environ.get("_TEST_FIXED_DATE") is None
        else os.environ["_TEST_FIXED_DATE"]
    )
    header = (
        f"Last refresh: {today}\n"
        f"Formula: success × quality / cost | Window: {WINDOW_DAYS} days | Min runs: {MIN_RUNS}\n\n"
    )
    kept = filter_min_runs(rows)
    if not kept:
        return header + (
            "No aggregated runs yet — `pick_models` continues to use vendored `_TABLE` default at "
            "`/opt/fabrik-lib/subagents/subagents/select.py:58`.\n"
        )
    # Group by task_type
    by_task: dict[str, list] = {}
    for r in kept:
        by_task.setdefault(r[0], []).append(r)
    out = [header]
    for task_type in sorted(by_task):
        task_rows = by_task[task_type]
        n_total = sum(r[2] for r in task_rows)
        # Score + sort desc
        scored = [(r, _value(r[3], r[4], r[5])) for r in task_rows]
        scored.sort(key=lambda x: x[1], reverse=True)
        out.append(f"### {task_type} (n_total={n_total})")
        out.append("| rank | model | value | success | avg_cost | avg_quality | n |")
        out.append("|---:|---|---:|---:|---:|---:|---:|")
        for rank, (r, val) in enumerate(scored, start=1):
            out.append(
                f"| {rank} | `{r[1]}` | {val:.2f} | {r[5]:.2f} | ${r[3]:.4f} | {r[4]:.2f} | {r[2]} |"
            )
        out.append("")
    return "\n".join(out) + "\n"


def _atomic_write(path: Path, content: str) -> None:
    """Write via temp file + os.replace so a mid-write crash never leaves partial file.
    Cloned from `scripts/kilo-benchmarks/rank_coding_subagents.py:345`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    rows = _query_rows()
    md = render(rows)
    _atomic_write(OUTPUT_PATH, md)
    print(f"wrote {OUTPUT_PATH} ({len(rows)} rows aggregated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
