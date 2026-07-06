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

# Query timeout — 300s covers real fleet scale on the indexed `ts` column
# even at millions of rows. Bumped from 30s per /fabrik-review A7 (silent
# TimeoutExpired at scale was indistinguishable from "no data yet").
# Override via env for exceptional cases: SUBAGENT_RANK_TIMEOUT=600.
QUERY_TIMEOUT_SECONDS = int(os.environ.get("SUBAGENT_RANK_TIMEOUT", "300"))

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


def _query_rows() -> tuple[str, list[tuple[str, str, int, float, float, float]]]:
    """Query the DB. Returns (state, rows) where state ∈ {"ok", "error"}.

    "ok" means the query ran cleanly (rows may be empty if there's genuinely no data).
    "error" means subprocess/psql failed — data is UNKNOWN. Caller uses the state to
    emit a distinct stub and set exit code (per /fabrik-review A6 fix — the old
    fail-soft returned `[]` for both cases and the "Last refresh" date advanced daily
    on the stub, making broken indistinguishable from healthy-but-empty).
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
            timeout=QUERY_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        # Broadened from (TimeoutExpired, FileNotFoundError) → (TimeoutExpired, OSError)
        # per convergence-pass Finder B#2. The docstring says "never raises" but a
        # generic OSError (PermissionError, EMFILE, ENOMEM, broken sudo executable)
        # would otherwise propagate up and crash main() before the AGGREGATION FAILED
        # stub is written. OSError covers FileNotFoundError + everything similar.
        print(f"[rank_task_subagents] DB query failed: {exc}", file=sys.stderr)
        return ("error", [])
    if result.returncode != 0:
        print(f"[rank_task_subagents] psql non-zero exit: {result.stderr.strip()}", file=sys.stderr)
        return ("error", [])
    rows = []
    # delimiter must match the psql `-F` we passed (verified above).
    # quoting=csv.QUOTE_NONE — psql `-A` mode never emits CSV-style quoting, so a
    # value starting with `"` would otherwise collapse subsequent tab-separated
    # columns into one field (Finder B#3). QUOTE_NONE treats `"` as literal.
    #
    # Per-row parse (Finder B#4): iterate the reader lazily instead of materializing
    # with list(). A mid-iteration csv.Error would otherwise abort ALL data — 99
    # good rows + 1 bad row would collapse to state="error" and rows=[]. Per-row
    # handling drops the one bad row while preserving the rest.
    reader = csv.reader(
        io.StringIO(result.stdout), delimiter=PSQL_FIELD_SEP, quoting=csv.QUOTE_NONE
    )
    while True:
        try:
            line = next(reader)
        except StopIteration:
            break
        except csv.Error as exc:
            print(f"[rank_task_subagents] skip malformed line: {exc}", file=sys.stderr)
            continue
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
    return ("ok", rows)


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


CODING_FALLBACK_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "reference"
    / "kilo"
    / "CODING_SUBAGENT_SELECTION.md"
)
CODING_FALLBACK_MAX = 10  # how many CODING models to blend when the fleet has no `code` data


def _load_coding_fallback(path: Path = CODING_FALLBACK_PATH) -> list[str]:
    """Parse `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md` and return the top-N
    model IDs from its `### code` section.

    We use this as a FALLBACK when the fleet has no empirical `code` runs yet — the
    vendored subagents module's reader accepts ONE file (not comma-separated), so
    to give projects benchmark-based rankings for the `code` task_type before real
    fleet data accumulates, we blend CODING's ranked models into TASK_SUBAGENT_
    SELECTION.md's emitted `### code` section here at doc-emit time.

    Never raises. Returns [] on any parse/read failure — the caller then just
    omits the `### code` section and pick_models falls through to _TABLE."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    # The CODING file has ONE `### code` section followed by a markdown table.
    # Extract rows: `| N | \`model\` | ... |`. Rank cell isdecimal, model cell
    # is backticked. This mirrors the parse logic in the subagents module's
    # `load_task_ranking()` at select.py so what we blend WILL be readable by
    # the same reader that eventually consumes TASK_SUBAGENT_SELECTION.md.
    in_code = False
    models: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("###"):
            head = stripped.lower()
            in_code = head.startswith("### code")
            continue
        if not in_code or not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2 or not cells[0].isdecimal():
            continue
        model = cells[1].strip("`")
        if "/" not in model:
            continue
        if model not in models:  # dedup, preserve rank order
            models.append(model)
        if len(models) >= CODING_FALLBACK_MAX:
            break
    return models


def render(rows: list, state: str = "ok") -> str:
    """Emit the ranked markdown from aggregated rows.

    Rows shape: (task_type, model, n, avg_cost, avg_quality, success_rate).
    `state` distinguishes a healthy empty pool ("ok" + no rows) from an aggregation
    failure ("error") so the emitted stub tells the operator which one it is —
    otherwise the daily-regenerated "Last refresh" date makes broken indistinguishable
    from healthy-but-empty (per /fabrik-review A6 fix).
    """
    # Truthy check (not `is None`) so an empty _TEST_FIXED_DATE="" env-var doesn't
    # produce `Last refresh: \n` — Finder B#6. Empty string falls through to today.
    today = os.environ.get("_TEST_FIXED_DATE") or date.today().isoformat()
    header = (
        f"Last refresh: {today}\n"
        f"Formula: success × quality / cost | Window: {WINDOW_DAYS} days | Min runs: {MIN_RUNS}\n\n"
    )
    if state == "error":
        return header + (
            "⚠️ AGGREGATION FAILED — the daily query against `subagent_runs` did not "
            "complete. Check `daily_refresh.sh` logs at `scripts/kilo-benchmarks/cache/update.log` "
            "for the stderr from `rank_task_subagents.py` (common causes: postgres down, "
            "`sudo -n` NOPASSWD not configured, query timeout). `pick_models` continues to use "
            "vendored `_TABLE` default at `/opt/fabrik-lib/subagents/subagents/select.py:58` — "
            "no functional regression, but the ranking is stale until this is fixed.\n"
        )
    kept = filter_min_runs(rows)
    # Group by task_type — start early so the CODING fallback can check whether
    # `code` has real fleet data before we decide whether to blend.
    by_task: dict[str, list] = {}
    for r in kept:
        by_task.setdefault(r[0], []).append(r)

    # CODING fallback (Finder C fix): when the fleet has NO empirical `code` data,
    # seed the `### code` section from CODING_SUBAGENT_SELECTION.md so
    # pick_models("code") returns benchmark-ranked models instead of falling
    # through to the vendored `_TABLE`. Only applies to `code` — other task
    # types have no benchmark analog and correctly fall through when empty.
    coding_fallback_models: list[str] = []
    if not by_task.get("code"):
        coding_fallback_models = _load_coding_fallback()

    if not kept and not coding_fallback_models:
        return header + (
            "No aggregated runs yet — `pick_models` continues to use vendored `_TABLE` default at "
            "`/opt/fabrik-lib/subagents/subagents/select.py:58`.\n"
        )
    out = [header]
    for task_type in sorted(by_task):
        task_rows = by_task[task_type]
        n_total = sum(r[2] for r in task_rows)
        # Score + sort desc. Model-id is the tie-breaker so ties don't shuffle
        # non-deterministically between daily runs (Finder B#8). Postgres doesn't
        # guarantee stable GROUP BY output order, so we sort by (value desc, model asc).
        scored = [(r, _value(r[3], r[4], r[5])) for r in task_rows]
        scored.sort(key=lambda x: (-x[1], x[0][1]))
        out.append(f"### {task_type} (n_total={n_total})")
        out.append("| rank | model | value | success | avg_cost | avg_quality | n |")
        out.append("|---:|---|---:|---:|---:|---:|---:|")
        for rank, (r, val) in enumerate(scored, start=1):
            out.append(
                f"| {rank} | `{r[1]}` | {val:.2f} | {r[5]:.2f} | ${r[3]:.4f} | {r[4]:.2f} | {r[2]} |"
            )
        out.append("")

    # Blended `### code` section from CODING_SUBAGENT_SELECTION.md — emitted only
    # when the fleet has no empirical `code` runs yet. Reader-compatible table
    # rows (rank in first cell, backticked model in second) so the module's
    # load_task_ranking() parses them just like fleet rows. Marker `[benchmark]`
    # in the source column tells human readers these came from public benchmarks,
    # not from live fleet invocations.
    if coding_fallback_models:
        out.append("### code (n_total=0, fallback from CODING_SUBAGENT_SELECTION.md)")
        out.append("| rank | model | source |")
        out.append("|---:|---|:-:|")
        for rank, model in enumerate(coding_fallback_models, start=1):
            out.append(f"| {rank} | `{model}` | [benchmark] |")
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
    state, rows = _query_rows()
    md = render(rows, state=state)
    _atomic_write(OUTPUT_PATH, md)
    print(f"wrote {OUTPUT_PATH} (state={state}, {len(rows)} rows aggregated)")
    # Exit non-zero on real aggregation failure so daily_refresh.sh's `|| echo "failed"`
    # logs it. Empty-pool (state="ok", 0 rows) is a healthy outcome and exits 0.
    return 1 if state == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
