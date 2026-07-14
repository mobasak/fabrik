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
import sqlite3
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

# ─── Ranking policy — fabrik-lib 2026-07-11 contract ──────────────────────────
# The doc's rank ORDER is the contract. `pick_models` takes top-N in doc order.
# So the ranking here must be quality-safe AND cost-honest.
#
# Formula: shrink real-run avg_quality toward the capability tier prior
# (Bayesian shrinkage, K runs' worth of prior weight), then quality-gate, then
# order surviving rows cheapest-first, with top-2 slots requiring more runs
# so a lucky n=3 can't head a section on thin evidence.
#
#     shrunk_q = (n · avg_quality + K · tier_baseline) / (n + K)
#
# TIER_BASELINE maps quality_tier (1/2/3) to a 0-5 quality prior. Rows with no
# tier fall through to their raw avg_quality (no shrinkage applied).
SHRINKAGE_K = 10  # ~10 runs of prior weight — flips only when real data is thick
TIER_BASELINE = {1: 1.0, 2: 2.5, 3: 4.0}  # 0-5 scale; T2 baseline = QUALITY_GATE_MIN
QUALITY_GATE_MIN = 2.5  # drop anything below the T2-tier baseline after shrinkage
MIN_RUNS_TOP2 = 10  # slots #1-#2 require n≥10; lower-n rows sort below


def load_task_baselines(db_path: str | Path | None = None) -> dict[tuple[str, str], float]:
    """(model_id, task_type) -> benchmark-derived prior, from `model_task_baseline`.

    Built by `build_task_baselines.py` from Terminal-Bench's per-category results. Empty dict
    if the table does not exist yet — this must degrade to the old behaviour, never crash the
    ranker.
    """
    path = db_path or (Path(__file__).resolve().parent / "kilo_agents.db")
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            return {
                (m, t): float(b)
                for m, t, b in conn.execute(
                    "SELECT model_id, task_type, baseline FROM model_task_baseline"
                )
            }
    except (sqlite3.Error, OSError):
        return {}


def _tier_baseline(
    quality_tier: int | None,
    model_id: str | None = None,
    task_type: str | None = None,
    task_baselines: dict[tuple[str, str], float] | None = None,
) -> float | None:
    """The prior for the shrinkage formula — task-specific when we have real evidence.

    Precedence:
      1. **A benchmark that measures THIS task for THIS model** (`model_task_baseline`).
         Ground truth beats a guess: a model can be strong at code and weak at ops, and the
         old single `quality_tier` could not express that. Today only `ops` and `code` have
         such a benchmark (Terminal-Bench categories); the honest set, not the convenient one.
      2. The general `quality_tier` prior — the status quo, for every (model, task) pair with
         no benchmark. Left deliberately in place rather than back-filled with a proxy score:
         an imported number from a benchmark that never tested this model is a fabrication.
      3. None -> the caller falls back to raw avg_quality (no shrinkage).
    """
    if task_baselines and model_id and task_type:
        specific = task_baselines.get((model_id, task_type))
        if specific is not None:
            return specific
    if quality_tier is None:
        return None
    return TIER_BASELINE.get(int(quality_tier))


def _shrunk_quality(
    n: int,
    avg_quality: float,
    quality_tier: int | None,
    model_id: str | None = None,
    task_type: str | None = None,
    task_baselines: dict[tuple[str, str], float] | None = None,
) -> float:
    """Blended prior + real-run signal: shrink avg_quality toward the tier
    baseline with K runs of prior weight. Rows without a tier get raw
    avg_quality (nothing to shrink toward — pick_models is on its own).

    Concrete example (fabrik-lib 2026-07-11): glm-4.5-air (T2, avg_q=1.0 on
    16 review runs) → (16·1.0 + 10·2.5) / (16+10) = 1.58 → below the 2.5
    gate → excluded, exactly as intended (the flywheel says T2 was too kind).
    """
    prior = _tier_baseline(quality_tier, model_id, task_type, task_baselines)
    if prior is None:
        return float(avg_quality)
    return (n * avg_quality + SHRINKAGE_K * prior) / (n + SHRINKAGE_K)


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
            # NULL avg_quality is treated as NEUTRAL (1.0) — not 0. Under the
            # current contract (fabrik-lib update landing after run_agents shipped)
            # the module no longer silently auto-writes rows; every row now lands
            # via an explicit record_run(..., quality_score=) call the orchestrator
            # makes AFTER judging the output, so NULL quality is defensive tolerance
            # (hand-written INSERT, legacy row, orchestrator that still passes None)
            # rather than the norm. Treating that residual NULL as 0.0 would
            # collapse `success × quality / cost` to 0 for every such row and
            # destroy the ranking, so we degrade the formula to `success / cost`
            # instead.
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

# SQLite store that carries `agents.quality_tier` (1/2/3). Same file
# `rank_coding_subagents.py` opens — plain read-only join.
KILO_AGENTS_DB = Path(__file__).resolve().parent / "kilo_agents.db"


def _load_quality_tiers(path: Path = KILO_AGENTS_DB) -> dict[str, int]:
    """Return `{model_id: quality_tier}` from `kilo_agents.db.agents` (SQLite).

    Read-only, single query. Rows without a tier are omitted (caller will emit
    a blank column value). Never raises — the docstring on the caller side is
    that a missing DB or a schema drift just yields an empty dict, which then
    surfaces as blank tier cells. Failing loud here would take out the daily
    doc regeneration for a purely-cosmetic column.
    """
    import sqlite3

    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            rows = conn.execute(
                "SELECT id, quality_tier FROM agents WHERE quality_tier IS NOT NULL"
            ).fetchall()
    except (sqlite3.Error, OSError):
        return {}
    # `int(tier)` guarded — schema is INTEGER today, but sqlite is dynamically
    # typed and a future schema drift could store text ("high"), which would
    # crash the daily doc regen otherwise. Skip malformed rows silently.
    result: dict[str, int] = {}
    for mid, tier in rows:
        if tier is None:
            continue
        try:
            result[mid] = int(tier)
        except (ValueError, TypeError):
            continue
    return result


def _fmt_tier(tiers: dict[str, int], model: str) -> str:
    """Format the quality_tier cell — value 1/2/3 or blank per fabrik-lib contract."""
    t = tiers.get(model)
    return str(t) if t is not None else ""


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
            # EXACT match on `### code`. `startswith("### code")` would ALSO
            # match `### code-onrequest` (the pricey-tier header the ranker
            # emits under the Auto/On-request split), which would silently
            # re-admit glm-5/kimi/grok into the fleet-synced TASK doc —
            # exactly the failure mode .windsurf/rules/core/62-using-subagents.md
            # § Approved pool models warns against. Match by EXACT header, not by prefix.
            in_code = head == "### code"
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
    # NOTE (2026-07-09 canonical alignment): the `<!-- reachable-set: ... -->`
    # emit was reverted after fabrik-lib's source-of-truth AI ruled the
    # mechanism wrong-layer. Canonical seam is `pick_models(task_type,
    # exclude=unreachable_ids)`; callers build the set from
    # `agents.reachable_with_existing_keys=0` at dispatch time.
    header = (
        f"Last refresh: {today}\n"
        f"Formula: shrunk_q = (n·avg_q + {SHRINKAGE_K}·tier_baseline) / (n+{SHRINKAGE_K}); "
        f"quality-gate at shrunk_q ≥ {QUALITY_GATE_MIN}; then cost-asc among survivors; "
        f"top-2 slots require n ≥ {MIN_RUNS_TOP2} | "
        f"tier_baseline T1={TIER_BASELINE[1]}, T2={TIER_BASELINE[2]}, T3={TIER_BASELINE[3]} | "
        f"Window: {WINDOW_DAYS} days | Min runs: {MIN_RUNS}\n\n"
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

    # Quality-tier join (fabrik-lib ask 2026-07-11): read `agents.quality_tier`
    # from kilo_agents.db and emit a `quality_tier` column per row. Fabrik-lib's
    # `pick_models` uses it as a blended prior (shrink real-run quality toward
    # the tier — handles small-n gracefully) and optionally as a hard floor via
    # SUBAGENT_MIN_TIER. Empty dict on failure → blank tier cells (never blocks
    # doc regen).
    tiers = _load_quality_tiers()
    # Benchmark priors, per (model, task_type). Empty dict if build_task_baselines.py has
    # not run — the ranker then behaves exactly as before (quality_tier prior).
    task_baselines = load_task_baselines()

    # CODING supplement: ALWAYS load the top benchmark-ranked models from
    # CODING_SUBAGENT_SELECTION.md — they're appended below any fleet rows in
    # `### code` (deduped) so `pick_models("code", n=N)` gets fleet-first-then-
    # benched, and models we've benched but haven't fleet-used yet aren't
    # invisible to the router. Only applies to `code` — other task_types have
    # no benchmark analog.
    coding_fallback_models: list[str] = _load_coding_fallback()

    if not kept and not coding_fallback_models:
        return header + (
            "No aggregated runs yet — `pick_models` continues to use vendored `_TABLE` default at "
            "`/opt/fabrik-lib/subagents/subagents/select.py:58`.\n"
        )
    out = [header]
    # Track which task_types actually emitted a section — the CODING
    # supplement below emits its own `### code` header when no fleet code
    # section was produced.
    emitted_task_types: set[str] = set()
    for task_type in sorted(by_task):
        task_rows = by_task[task_type]
        n_total = sum(r[2] for r in task_rows)
        # Fabrik-lib 2026-07-11 contract — the doc's rank order IS the
        # contract. Compute shrunk_q per row, apply the quality gate, then
        # sort survivors by (top-2-eligible desc, cost asc, model asc). Model
        # is the deterministic tie-breaker so daily runs don't shuffle.
        scored: list[tuple[tuple, float]] = []
        for r in task_rows:
            _tt, model, n, avg_cost, avg_quality, _success = r
            tier = tiers.get(model)
            # Pass the model + task so a BENCHMARK prior (model_task_baseline) can override
            # the task-blind quality_tier where one exists. Today that is `ops` and `code`.
            shrunk_q = _shrunk_quality(n, avg_quality, tier, model, _tt, task_baselines)
            if shrunk_q < QUALITY_GATE_MIN:
                continue  # quality gate — a bad model is never in the usable top slots
            scored.append((r, shrunk_q))
        # Top-2 eligibility: n < MIN_RUNS_TOP2 sorts BELOW top-2-eligible rows.
        # False (n ≥ MIN_RUNS_TOP2) sorts before True (n < MIN_RUNS_TOP2).
        scored.sort(key=lambda x: (x[0][2] < MIN_RUNS_TOP2, x[0][3], x[0][1]))
        # Skip the whole section if the gate excluded every row — pick_models
        # will fall through to its _TABLE default for this task_type. That's
        # correct: better no signal than misleading signal.
        if not scored:
            continue
        out.append(f"### {task_type} (n_total={n_total})")
        # `quality_tier` sits SECOND-TO-LAST so `cells[-1]` stays `n` — that's
        # what fabrik-lib's `load_task_ranking()` reader parses as the run
        # count (`libs/subagents/select.py:280`). Column position matters.
        # `shrunk_q` replaces the old `value` column (formula changed — the
        # score no longer drives rank order; cost does, among gate-survivors).
        out.append(
            "| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |"
        )
        out.append("|---:|---|---:|---:|---:|---:|:-:|---:|")
        emitted_code_models: set[str] = set()
        code_last_rank = 0
        for rank, (r, shrunk_q) in enumerate(scored, start=1):
            out.append(
                f"| {rank} | `{r[1]}` | {shrunk_q:.2f} | {r[5]:.2f} | ${r[3]:.4f} | {r[4]:.2f} | "
                f"{_fmt_tier(tiers, r[1])} | {r[2]} |"
            )
            if task_type == "code":
                emitted_code_models.add(r[1])
                code_last_rank = rank

        # CODING supplement (inline mode a): append benchmark-ranked models
        # from CODING_SUBAGENT_SELECTION.md below the fleet rows in this
        # SAME `### code` table so a model we've benched but haven't
        # fleet-used yet is still visible to `pick_models("code")`. Same
        # 8-column shape so the reader treats them uniformly under one
        # `### code` header. `[benchmark]` in the shrunk_q slot, `—` for
        # per-run fields, tier populated from _load_quality_tiers, n=0
        # (reader parses cells[-1] as int; n=0 with default min_n=0 is
        # admitted; a caller passing min_n≥1 correctly filters benchmark
        # rows out).
        if task_type == "code" and coding_fallback_models:
            for i, model in enumerate(
                [m for m in coding_fallback_models if m not in emitted_code_models],
                start=code_last_rank + 1,
            ):
                out.append(
                    f"| {i} | `{model}` | [benchmark] | — | — | — | {_fmt_tier(tiers, model)} | 0 |"
                )
        out.append("")
        emitted_task_types.add(task_type)

    # CODING supplement — mode (b): if the fleet had zero `code` rows above
    # the quality gate, no `### code` header was emitted in the loop above.
    # Fall back to a dedicated section so `pick_models("code")` still has a
    # benchmark-ranked list. Same 8-column shape as fleet sections.
    if "code" not in emitted_task_types and coding_fallback_models:
        out.append("### code (n_total=0, fallback from CODING_SUBAGENT_SELECTION.md)")
        out.append(
            "| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |"
        )
        out.append("|---:|---|---:|---:|---:|---:|:-:|---:|")
        for rank, model in enumerate(coding_fallback_models, start=1):
            out.append(
                f"| {rank} | `{model}` | [benchmark] | — | — | — | {_fmt_tier(tiers, model)} | 0 |"
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
    state, rows = _query_rows()
    md = render(rows, state=state)
    _atomic_write(OUTPUT_PATH, md)
    print(f"wrote {OUTPUT_PATH} (state={state}, {len(rows)} rows aggregated)")
    # Exit non-zero on real aggregation failure so daily_refresh.sh's `|| echo "failed"`
    # logs it. Empty-pool (state="ok", 0 rows) is a healthy outcome and exits 0.
    return 1 if state == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
