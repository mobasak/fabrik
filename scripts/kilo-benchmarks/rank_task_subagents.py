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
     ⚠️ LOCAL-ONLY IS DELIBERATE — do not "fix" this to also read postgres-main. `fabrik apply`
     provisions a SECOND `fabrik_analytics.subagent_runs` on postgres-main and injects a per-project
     writer DSN into every deployed project (`infrastructure.py:734-755`), which looks like a
     split brain. Measured 2026-09-02: that table is EMPTY — `ssh vps "sudo docker exec postgres-main
     psql -U postgres -d fabrik_analytics -tAc 'SELECT count(*), count(DISTINCT agent_id), min(ts),
     max(ts), count(DISTINCT project) FROM subagent_runs'"` → `0|0|||0`. No deployed service has ever
     written a row, so the LOCAL database is the whole population and a union read would add nothing
     but a second failure mode. The registrar provisioning a sink with no writer AND no reader is a
     real defect, but it is FLEET's beat and is filed (`01M1H2XGV09Y78W9TGVG3G92TH`) — not this
     script's to work around. Re-measure before changing this; if that table ever holds rows, the
     ranking's input has become incomplete and THAT is the moment to widen it.
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
# One discriminating corpus item ≈ 0.2 of score5 (1/22 of recall, ×5 through F1); rounded up to 0.25.
# Reviewer candidates whose score5 falls in the same band are indistinguishable to the instrument and
# are therefore ordered by COST. Widening this band trades measured quality for measured price —
# do it only with a corpus that can resolve the difference you are giving up.
_SCORE5_NOISE_BAND = 0.25

# ── G2: provider-stall rate, gated on INCIDENT independence rather than sampling breadth ──────────
# `capped` conflates two failures with opposite dispositions: a provider that accepted the request
# and streamed NOTHING (0 turns, $0 — theirs), and a run that worked and hit OUR max_turns ceiling
# (ours). Only the first says anything about a model, and it is the one genuine model-side signal
# inside `capped`.
#
# ⚠️ THE FLOOR IS INCIDENTS, NOT DAYS — an earlier design had this exactly backwards. It proposed a
# "minimum distinct DISPATCH days" floor on the reading that a rate from 2 days could be one bad
# afternoon. Measured, those two days are **46 days apart** (2026-07-18 and 2026-09-02): a signal
# REPRODUCED across two independent incidents six weeks apart is STRONGER evidence, not weaker. A
# days-floor would have suppressed exactly that while admitting a model swept on ten consecutive days
# of a single outage. Sampling breadth is not incident independence.
_STALL_MIN_DAYS = 2  # at least two days on which stalls occurred
_STALL_MIN_SPAN_DAYS = 7  # …separated by at least a week, so one outage cannot qualify alone


def stall_signal(stalls: int, total: int, stall_days: int, span_days: int) -> tuple[float, bool]:
    """(rate, routable). A rate is DISPLAYED always and ROUTED on only when reproduced.

    Live data this separates correctly (as of 2026-09-02):
      stepfun/step-3.5-flash 33.3% · 2 days · 46 apart -> routable (two incidents)
      xiaomi/mimo-v2.5       26.7% · 2 days · 46 apart -> routable
      poolside/laguna-m.1    19.3% · 1 day  ·  0 apart -> DISPLAY ONLY (one incident)
      minimax/minimax-m3      6.4% · 5 days · 56 apart -> routable
    """
    rate = (100.0 * stalls / total) if total else 0.0
    routable = stalls > 0 and stall_days >= _STALL_MIN_DAYS and span_days >= _STALL_MIN_SPAN_DAYS
    return rate, routable


# ⚠️ The denominator is stated, not implied: stalls are counted over rows whose status is a real
# dispatch outcome (`status <> '' AND status <> 'scored'`). 2,727 rows carry a BLANK status and
# `scored` rows are quality deltas, not runs — including either would silently change every rate.
STALL_QUERY = """
WITH s AS (
  SELECT model, ts::date AS d,
         count(*) FILTER (WHERE status = 'capped' AND coalesce(turns, 0) = 0) AS stalls,
         count(*) AS n
  FROM subagent_runs
  WHERE status <> '' AND status <> 'scored'
  GROUP BY 1, 2
)
SELECT model, sum(stalls), sum(n), count(*) FILTER (WHERE stalls > 0),
       coalesce(max(d) FILTER (WHERE stalls > 0) - min(d) FILTER (WHERE stalls > 0), 0)
FROM s GROUP BY model HAVING sum(stalls) > 0
"""


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

# Two-level aggregation per set_quality's contract (libs/subagents/pg_ledger.py:500-530):
# a back-filled score is an APPENDED delta row (status='scored', objective metrics NULL), so
# n counts OBJECTIVE rows only, success_rate is per-AGENT, and effective quality is the
# non-NULL max per agent_id (the delta wins over the NULL dispatch row). Canary probe rows
# (project='canary-grounding') are deliberate 0/5 grounding probes — they feed CANARY_QUERY
# below, never the organic ranking. The inner HAVING drops orphan deltas (a scored row whose
# dispatch row was never written — known incident class, FanoutBatch docstring).
# eff_q = the LATEST non-NULL score, not MAX — the contract's own word (pg_ledger.py:651-654);
# MAX resurrects human-downgraded verdicts (live: two glm-4.5-air research agents re-scored
# 4->1 and 4->2 crossed the quality gate under MAX and took rank 1). Orphan scored deltas
# (dispatch row never landed) keep their verdict in avg_quality per pg_ledger.py:665-667 but
# add nothing to n and never touch success_rate (no objective run to succeed or fail); a model
# with ONLY orphans still drops at the outer HAVING. success/cost collapse per-agent — today
# every agent has exactly one objective row (verified 0/6259 multi-row agents), so both are
# numerically identical to the old per-row form on real data.
QUERY = f"""
SELECT task_type, model,
       SUM(n_obj) AS n,
       AVG(cost) AS avg_cost,
       AVG(eff_q) AS avg_quality,
       AVG(done_i) FILTER (WHERE n_obj > 0) AS success_rate
FROM (
    SELECT task_type, model, agent_id,
           COUNT(*) FILTER (WHERE status <> 'scored') AS n_obj,
           (array_agg(quality_score ORDER BY ts DESC, id DESC)
              FILTER (WHERE quality_score IS NOT NULL))[1] AS eff_q,
           MAX(CASE WHEN status='done' THEN 1.0 ELSE 0.0 END) AS done_i,
           MAX(cost_usd) AS cost
    FROM {TABLE}
    WHERE ts > NOW() - INTERVAL '{WINDOW_DAYS} days'
      AND project <> 'canary-grounding'
    GROUP BY task_type, model, agent_id
) per_agent
GROUP BY task_type, model
HAVING SUM(n_obj) >= {MIN_RUNS}
""".strip()

# Grounding canary aggregation (plan 2026-08-28-plan-1-canary-grounding, Phase B): per-model
# average of the binary canary scores, reconciled per agent_id like QUERY. The >=2 floor means
# one stray row can never trigger the ranking penalty (criterion-1 guarantees 2 probes/model);
# >30-day rows decay out, so a dead canary cron degrades to "no signal", never a stale penalty.
CANARY_WINDOW_DAYS = 30
CANARY_MIN_ROWS = 2
# An agent whose DISPATCH row never reached status='done' (provider outage, cap, error) is
# REFUSED outright — an infra failure must never become a grounding penalty (the harness also
# never scores such units; this is defense in depth). eff_q = latest non-NULL, same as QUERY.
CANARY_QUERY = f"""
SELECT model, AVG(eff_q) AS canary_avg
FROM (
    SELECT model, agent_id,
           (array_agg(quality_score ORDER BY ts DESC, id DESC)
              FILTER (WHERE quality_score IS NOT NULL))[1] AS eff_q
    FROM {TABLE}
    WHERE project = 'canary-grounding'
      AND ts > NOW() - INTERVAL '{CANARY_WINDOW_DAYS} days'
    GROUP BY model, agent_id
    HAVING MAX(quality_score) IS NOT NULL
       AND BOOL_OR(status = 'done')
) per_agent
GROUP BY model
HAVING COUNT(*) >= {CANARY_MIN_ROWS}
""".strip()

# psql field separator. Tab picked over comma because a comma in a task_type or model_id
# (however unlikely today — TASK_KINDS is fixed at {spec,plan,code,review,docs,research}
# and OR model IDs are `provider/model` with no `,`) would silently corrupt the fixed
# 6-column unpack: `-A -F,` does NOT emit CSV-style quoting (verified `psql --help`).
# `\t` is guaranteed absent from both column values by convention. Note this must match
# what render() and _query_rows() below use.
PSQL_FIELD_SEP = "\t"


def _grounding_cell(avg: float | None) -> str:
    """Render a model's canary-grounding signal: ``✓`` at/above the 2.5 threshold, ``✗(X.XX)``
    below (TWO decimals — one decimal renders 2.49 as the 2.5 threshold and invites false bug
    reports), ``—`` for no data / below the CANARY_MIN_ROWS floor / decayed past the window."""
    if avg is None:
        return "—"
    return "✓" if avg >= 2.5 else f"✗({avg:.2f})"


def _query_canary_rows() -> tuple[str, dict[str, float]]:
    """Per-model canary averages via the same psql transport as :func:`_query_rows`.

    Returns ("ok", {model: avg}) or ("error", {}) — an error renders every grounding cell as
    ``—`` and NEVER fails the whole doc (the canary is an overlay signal, not a dependency)."""
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
                CANARY_QUERY,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(
                f"[rank_task_subagents] canary query failed: {result.stderr.strip()[:200]}",
                file=sys.stderr,
            )
            return "error", {}
        out: dict[str, float] = {}
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            try:  # one malformed line degrades ONE row to "—", never the whole canary set
                model, avg = line.split(PSQL_FIELD_SEP)
                out[model] = float(avg)
            except (ValueError, TypeError) as exc:
                print(
                    f"[rank_task_subagents] canary line skipped ({exc}): {line[:80]!r}",
                    file=sys.stderr,
                )
        return "ok", out
    except Exception as exc:
        print(f"[rank_task_subagents] canary query errored: {exc}", file=sys.stderr)
        return "error", {}


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


def _review_benchmark_models() -> list[str]:
    """Review models that cleared the PERMANENT eligibility gate, ranked best-first.

    Source: `microbench_review` -> `model_review_metrics`, gated by
    `build_task_baselines.review_eligible` (precision ≥ 99% · real $/1k ≤ 0.70 · p50 ≤ 10s — the
    operator's constraints, defined once in build_task_baselines). Ordered by measured grade
    (score5 desc) then real cost asc. This is the benchmark analog of `_load_coding_fallback` for
    the `review` task_type: it both GATES the fleet review rows (only these ids survive) and
    SUPPLIES benchmark-ranked review candidates so `pick_models("review")` sees them before any
    fleet review runs accumulate. Empty list if the benchmark hasn't run → the review section
    behaves exactly as before. Never raises."""
    try:
        from build_task_baselines import load_review_metrics, review_eligible

        metrics = load_review_metrics()
        elig = review_eligible()
    except Exception:
        return []

    def _cost(m: str) -> float:
        c = metrics[m]["cost_per_1k"]
        return (
            c if c is not None else 1e9
        )  # NOT `c or 1e9`: a legit free model (0.0) must sort cheap

    # ⚠️ SCORE5 IS BANDED BEFORE COST IS CONSULTED — the corpus cannot resolve finer than this.
    # `TASK_SUBAGENT_SELECTION.md` states its own instrument ceiling: of the 22 mutants, 15 are caught
    # by every strong model and 6 by none, so **exactly ONE item discriminates at the frontier**. One
    # item is 1/22 of recall, and `score5 = F1(recall, precision) × 5`, so a single item moves score5
    # by roughly 0.2. Ordering on raw `score5` therefore let a difference SMALLER THAN ONE CORPUS ITEM
    # outrank a 4.5× cost difference — sorting on noise and paying real money for it.
    #
    # Banding at 0.25 (one item, rounded up) makes the comparison honest: models the instrument cannot
    # tell apart are ordered by COST, and a genuinely larger quality gap still wins because it lands in
    # a different band. This is the plan's own caveat made mechanical — "the defensible claim is the
    # cost, not the quality" (plan 2026-09-02-plan-1-flywheel-recording, Phase E).
    def _band(m: str) -> float:
        s5 = metrics[m]["score5"] or 0
        return -((s5 // _SCORE5_NOISE_BAND) * _SCORE5_NOISE_BAND)

    return sorted(
        (m for m in metrics if m in elig),
        key=lambda m: (_band(m), _cost(m), m),
    )


# Operator-set status for the `claude-code/*` review rows. Rendered into the full review table so the
# caveat travels WITH the numbers (the doc is regenerated daily — a hand-edited note would be wiped).
# Remove/replace this block once the one-by-one re-test is finished and every tier is re-measured.
_CLAUDE_P_RETEST_NOTICE = [
    "_⚠️ **`claude-code/*` review rows — RE-TEST IN PROGRESS (operator call, 2026-07-22).** The initial "
    "full-corpus runs of 2026-07-22 (opus · sonnet · haiku · fable, measured in 2-model batches) are "
    "considered **INVALID** and must not be used for comparison or routing judgement. Each tier is "
    "being re-measured **one model at a time** on the SAME unchanged 22-mutant corpus the OpenRouter "
    "models were scored on._",
    "",
    "_**Re-test status** — ✅ `haiku` (2026-07-22): 4.054→**4.21**, recall 68%→**73%** (15→16 of 22 "
    "caught) · ✅ `sonnet` (2026-07-23): **4.05 unchanged**, recall 68% (15 of 22) — reproduced its "
    "batched score exactly · ✅ `fable` (2026-07-23): **4.05 unchanged**, recall 68% (15 of 22) — also "
    "reproduced exactly · ⏳ `opus` — still carrying its INVALID batched score, to be re-run on operator "
    "instruction (not scheduled; do not auto-run)._",
    "",
    "_Why one-at-a-time: a single 22-item pass carries enough sampling variance to shift a tier by "
    "~5pp of recall (haiku moved 5pp on an identical corpus; repeated-trial probing showed the same "
    "item flipping correct/incorrect across calls on identical input), so a batched run is not a sound "
    "basis for ranking. The corpus itself is UNCHANGED and remains byte-identical to the one all 57 "
    "OpenRouter models were measured against — those rows are unaffected and stay valid._",
    "",
    "_**Resolution caveat (per-item probing, 2026-07-23):** of this corpus's 22 mutants, 15 are "
    "caught by every strong model and 6 by none — exactly 1 item discriminates at the frontier, so "
    "near-identical scores among top models here reflect the INSTRUMENT's ceiling, not equal "
    "capability. For separating frontier models use the HARD corpus (`microbench_review.py --hard` "
    "→ its own table below): 10 hand-planted subtle logic bugs, kill-proven by differential tests, "
    "persisted separately and never touching this baseline or routing._",
]


_SIDECAR_STALE_AFTER_HOURS = 24  # the rebuild cadence: `0 6 * * *` in daily_refresh.sh


def _sidecar_window(d: dict) -> str:
    """The provenance clause for ② — the window it came from, and LOUDLY if that build is stale.

    A rate with no date is typographically identical whether it was built this morning or 26 days ago;
    that is exactly how `claude_p_cost.json` sat at a 17%-low figure while every reader rendered it as
    current. Three states, deliberately distinguishable:

      * DERIVED and fresh   → the window bounds and denominators, stated plainly
      * DERIVED and STALE   → the same, prefixed ⚠️ STALE with the age, because a cron that stopped
                              firing is silent by construction and nothing else here would say so
      * ANCHOR fallback     → no window at all; the rate is a research constant, and saying "over
                              2026-08-07→09-05" beside it would assert a derivation that never happened

    A MISSING sidecar never reaches this function — `_claude_p_preamble` returns `[]` first, which is
    the fail-soft path a project checkout depends on and which must not be confused with staleness.
    """
    import datetime

    start, end = d.get("window_start"), d.get("window_end")
    tokens, accounts = d.get("tokens"), d.get("accounts")
    built = d.get("built_at")

    age = ""
    if isinstance(built, str) and built.strip():
        try:
            stamped = datetime.datetime.fromisoformat(built)
            if stamped.tzinfo is None:
                stamped = stamped.astimezone()
            hours = (datetime.datetime.now().astimezone() - stamped).total_seconds() / 3600.0
            if hours > _SIDECAR_STALE_AFTER_HOURS:
                age = f" ⚠️ **STALE — built {hours / 24:.1f} days ago**, the {_SIDECAR_STALE_AFTER_HOURS}h rebuild has not run"
        except ValueError:
            age = " ⚠️ **built_at unparseable** — treat this rate as undated"
    else:
        age = " ⚠️ **no `built_at`** — this rate carries no date at all"

    if not (start and end):
        return f"(⚠️ **no window** — this is the research ANCHOR, not a measured rate{age})"
    denom = ""
    if isinstance(tokens, int) and tokens > 0:
        # a volume that rounds to 0.0B tells the reader nothing — show the raw count instead
        denom = (
            f", {tokens / 1e9:.1f}B tokens"
            if tokens >= 5e7
            else f", {tokens:,} token" + ("s" if tokens != 1 else "")
        )
        if isinstance(accounts, int) and accounts > 0:
            denom += f" over {accounts} account" + ("s" if accounts != 1 else "")
    return f"(over {start}→{end}{denom}{age})"


def _claude_p_preamble(has_amortized_col: bool = True) -> list[str]:
    """The ②/③ context line for `claude-code/*` rows (reads `claude_p_cost.json` fail-soft). Empty if absent.

    Emits an italic sub-header (like the `_gate: …_` lines) so the reader knows the `$/1k` cell for a
    `claude-code/*` row is ① API-equivalent, and sees ② amortized + ③ quota-draw alongside.

    `has_amortized_col`: the review table has a per-row `②total$` column (raw-token persistence exists
    for `microbench_review.py`); the coding table does NOT (`microbench_coding_direct.py` never captures
    per-row raw tokens) — pass False there so the prose doesn't point at a column that isn't rendered.
    """
    import json

    p = Path(__file__).resolve().parent / "claude_p_cost.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        amort = float(d.get("amortized_per_mtok", 0.0) or 0.0)
        quota = float(d.get("quota_draw_pct", 0.0) or 0.0)
    except (OSError, ValueError, TypeError, AttributeError):
        return []  # MISSING stays fail-soft: a checkout without a sidecar renders no line at all
    window = _sidecar_window(d)
    col_note = (
        " `②total$` is a different unit: the REAL subscription-derived lump SUM for that row's whole "
        "measured run (expect it many orders of magnitude below `$/1k`, NOT a per-1k/per-run rate)."
        if has_amortized_col
        else " (no per-row ② column here — this harness doesn't persist raw tokens per run.)"
    )
    return [
        f"_`claude-code/*` rows: `$/1k` = ① API-equivalent (a list-price valuation of the subscription run's "
        f"tokens, comparable to the pool — a RATE).{col_note} Context — ② amortized ≈${amort:.3f}/M {window} · ③ last "
        f"run's weekly-quota draw ≈{quota:.1f}% (from `claude_p_cost.json`; ③ is a capacity estimate, not a "
        f"precise meter). A `claude-code/*` `✅` reflects the QUALITY floors only — the carve-out bypasses the "
        f"printed cost/latency gate, and these tiers are **spawn-native (display-only, NOT pool-dispatched)**, "
        f"so `pick_models` never returns them._",
    ]


def _full_review_results_table() -> list[str]:
    """Human-readable FULL review-benchmark leaderboard — every measured column, all models, real
    names. Rows lead with the `provider/model` id (NOT a rank int) so `load_task_ranking` SKIPS this
    table (its parser needs cells[0].isdecimal()) — display-only appendix, never a routing source.
    Empty list if the benchmark table isn't populated. Never raises."""
    import sqlite3

    db_path = Path(__file__).resolve().parent / "kilo_agents.db"

    def _n(v: object, spec: str, pre: str = "") -> str:
        try:
            return f"{pre}{format(v, spec)}" if v is not None else "—"
        except Exception:
            return "—"

    try:
        # mode=ro: this may run (e.g. via daily_refresh) while a live benchmark WRITES kilo_agents.db —
        # a read-write connection can hit "database is locked" (matches every other reader in this file).
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            if not conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='model_review_metrics'"
            ).fetchone():
                return []
            # raw per-type tokens (in_tokens/out_tokens_total/cache_read_tokens/cache_creation_tokens)
            # are a later migration (persist_metrics ALTERs them in) — COALESCE so an un-migrated row
            # (or a pre-migration OR row that never populated them) reads as NULL, not a query error.
            cols = {r[1] for r in conn.execute("PRAGMA table_info(model_review_metrics)")}
            token_cols = (
                "in_tokens",
                "out_tokens_total",
                "cache_read_tokens",
                "cache_creation_tokens",
            )
            token_select = ", ".join(f"m.{c}" if c in cols else f"NULL AS {c}" for c in token_cols)
            rows = conn.execute(
                "SELECT m.model_id, m.grade, m.score5, m.recall, m.precision, m.cost_per_1k, "
                f"m.out_price_mtok, m.cost_usd, m.p50_latency_s, m.tokens_per_s, m.n_mut, m.n_ctrl, "
                f"{token_select} "
                "FROM model_review_metrics m JOIN (SELECT model_id, MAX(built_at) mb "
                "FROM model_review_metrics GROUP BY model_id) t "
                "ON m.model_id=t.model_id AND m.built_at=t.mb ORDER BY m.score5 DESC"
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return []
    if not rows:
        return []
    out = [
        "",
        "## Full review benchmark results — all measured columns (display only; not parsed for routing)",
        "_source: `microbench_review.py` → `model_review_metrics`. `eligible` = passes the reviewer gate "
        "(precision ≥ 0.99 · $/1k ≤ 0.70 · $/run < 0.007 · score5 ≥ 3.5 · p50 ≤ 10s). `score5` = F1(recall,precision)×5._",
        *_CLAUDE_P_RETEST_NOTICE,
        *_claude_p_preamble(),
        "| model | grade | score5 | recall | prec | $/1k | $/M-out | $/run | ②total$ | p50 s | tok/s | n_mut | n_ctrl | eligible |",
        "|---|:-:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:-:|",
    ]
    # eligible flag from the SAME gate function → never drifts from the constants
    try:
        from build_task_baselines import review_eligible

        eligible_set = review_eligible()
    except Exception:
        eligible_set = set()
    for (
        model,
        grade,
        s5,
        rec,
        prec,
        c1k,
        opm,
        cusd,
        p50,
        tps,
        nmut,
        nctrl,
        intok,
        outtok,
        crtok,
        cctok,
    ) in rows:
        elig = "✅" if model in eligible_set else "—"
        amort = "—"
        if model.startswith("claude-code/") and None not in (intok, outtok, crtok, cctok):
            try:
                import derive_cost

                usage = {
                    "input_tokens": intok,
                    "output_tokens": outtok,
                    "cache_read_input_tokens": crtok,
                    "cache_creation_input_tokens": cctok,
                }
                amort = f"${derive_cost.amortized_cost(usage):.6f}"
            except Exception:
                amort = "—"
        out.append(
            f"| `{model}` | {grade or '—'} | {_n(s5, '.2f')} | {_n(rec, '.2f')} | {_n(prec, '.2f')} | "
            f"{_n(c1k, '.3f', '$')} | {_n(opm, '.2f', '$')} | {_n(cusd, '.4f', '$')} | {amort} | {_n(p50, '.1f')} | "
            f"{_n(tps, '.0f')} | {nmut if nmut is not None else '—'} | {nctrl if nctrl is not None else '—'} | {elig} |"
        )
    return out


def _full_review_hard_results_table() -> list[str]:
    """HARD-corpus review leaderboard (model_review_hard_metrics) — a DIAGNOSTIC instrument, never
    a routing source. Separate table + section because the hard corpus (10 hand-planted subtle
    logic bugs + 10 clean controls, kill-proven by differential tests) is a different, harder test
    than the operator-flip corpus above: scores are NOT comparable across the two. Exists because
    per-item probing proved the standard corpus ties frontier models (21 of its 22 mutants return
    the identical verdict from every strong model). Empty list until a --hard run persists."""
    import sqlite3

    db_path = Path(__file__).resolve().parent / "kilo_agents.db"

    def _n(v: object, spec: str, pre: str = "") -> str:
        try:
            return f"{pre}{format(v, spec)}" if v is not None else "—"
        except Exception:
            return "—"

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            if not conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='model_review_hard_metrics'"
            ).fetchone():
                return []
            cols = {r[1] for r in conn.execute("PRAGMA table_info(model_review_hard_metrics)")}
            token_cols = (
                "in_tokens",
                "out_tokens_total",
                "cache_read_tokens",
                "cache_creation_tokens",
            )
            token_select = ", ".join(f"m.{c}" if c in cols else f"NULL AS {c}" for c in token_cols)
            rows = conn.execute(
                "SELECT m.model_id, m.grade, m.score5, m.recall, m.precision, m.cost_per_1k, "
                f"m.out_price_mtok, m.cost_usd, m.p50_latency_s, m.tokens_per_s, m.n_mut, m.n_ctrl, "
                f"{token_select} "
                "FROM model_review_hard_metrics m JOIN (SELECT model_id, MAX(built_at) mb "
                "FROM model_review_hard_metrics GROUP BY model_id) t "
                "ON m.model_id=t.model_id AND m.built_at=t.mb ORDER BY m.score5 DESC"
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return []
    if not rows:
        return []
    out = [
        "",
        "## HARD review benchmark — hand-planted subtle logic bugs (diagnostic only; NOT comparable "
        "with the table above, never parsed for routing)",
        "_source: `microbench_review.py --hard` → `model_review_hard_metrics`. 10 hand-planted "
        "single-line logic bugs in realistic functions (stateful traces, stdlib semantics, "
        "contract-vs-code, placement bugs — every bug kill-proven by differential execution, every "
        "ground truth derived from a docstring contract) + 10 clean controls. Built to separate "
        "frontier models the operator-flip corpus ties. No eligibility gate — this table ranks, it "
        "does not route._",
        *_claude_p_preamble(),
        "| model | grade | score5 | recall | prec | $/1k | $/M-out | $/run | ②total$ | p50 s | tok/s | n_mut | n_ctrl |",
        "|---|:-:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for (
        model,
        grade,
        s5,
        rec,
        prec,
        c1k,
        opm,
        cusd,
        p50,
        tps,
        nmut,
        nctrl,
        intok,
        outtok,
        crtok,
        cctok,
    ) in rows:
        amort = "—"
        if model.startswith("claude-code/") and None not in (intok, outtok, crtok, cctok):
            try:
                import derive_cost

                usage = {
                    "input_tokens": intok,
                    "output_tokens": outtok,
                    "cache_read_input_tokens": crtok,
                    "cache_creation_input_tokens": cctok,
                }
                amort = f"${derive_cost.amortized_cost(usage):.6f}"
            except Exception:
                amort = "—"
        out.append(
            f"| `{model}` | {grade or '—'} | {_n(s5, '.2f')} | {_n(rec, '.2f')} | {_n(prec, '.2f')} | "
            f"{_n(c1k, '.3f', '$')} | {_n(opm, '.2f', '$')} | {_n(cusd, '.4f', '$')} | {amort} | {_n(p50, '.1f')} | "
            f"{_n(tps, '.0f')} | {nmut if nmut is not None else '—'} | {nctrl if nctrl is not None else '—'} |"
        )
    return out


def _full_coding_results_table() -> list[str]:
    """Human-readable FULL coding-benchmark leaderboard — LiveCodeBench pass@1 + every measured column,
    all models, real names. Rows lead with the `provider/model` id so `load_task_ranking` SKIPS this
    table (display-only appendix, never a routing source). Empty if the table is unpopulated. Never raises."""
    import sqlite3

    db_path = Path(__file__).resolve().parent / "kilo_agents.db"

    def _n(v: object, spec: str, pre: str = "") -> str:
        try:
            return f"{pre}{format(v, spec)}" if v is not None else "—"
        except Exception:
            return "—"

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            if not conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='model_coding_metrics'"
            ).fetchone():
                return []
            rows = conn.execute(
                "SELECT m.model_id, m.grade, m.pass_at_1, m.score5, m.cost_per_1k, m.cost_usd, "
                "m.p50_latency_s, m.tokens_per_s, m.n_graded, m.n_err "
                "FROM model_coding_metrics m JOIN (SELECT model_id, MAX(built_at) mb "
                "FROM model_coding_metrics GROUP BY model_id) t "
                "ON m.model_id=t.model_id AND m.built_at=t.mb ORDER BY m.pass_at_1 DESC, m.cost_per_1k ASC"
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return []
    if not rows:
        return []
    # eligible flag + tier from the SAME gate/tier source → never drifts from the constants
    try:
        from build_task_baselines import code_eligible, code_tier

        elig_set = code_eligible()
    except Exception:
        elig_set = set()

        def code_tier(_m: str) -> str | None:  # type: ignore[misc]
            return None

    out = [
        "",
        "## Full coding benchmark results — LiveCodeBench pass@1 (display only; not parsed for routing)",
        "_source: `microbench_coding_direct.py` → `model_coding_metrics` (contamination-free LiveCodeBench). "
        "`pass@1` = fraction solved · `score5` = pass@1×5 · `value` = score5÷$/1k · `eligible` = clears the code "
        "gate (n_err ≤ 1 · pass@1 ≥ 0.90 · $/1k ≤ 3.5 · p50 ≤ 10s) · `tier` = curated use-case._",
        *_claude_p_preamble(has_amortized_col=False),
        "| model | grade | pass@1 | score5 | $/1k | $/run | p50 s | tok/s | value | family | n_graded | n_err | eligible | tier |",
        "|---|:-:|--:|--:|--:|--:|--:|--:|--:|:-:|--:|--:|:-:|:-:|",
    ]
    for model, grade, p1, s5, c1k, cusd, p50, tps, ng, nerr in rows:
        value = f"{(s5 / c1k):.1f}" if (s5 is not None and c1k) else "—"
        family = model.split("/", 1)[0]
        elig = "✅" if model in elig_set else "—"
        tier = code_tier(model) or "—"
        out.append(
            f"| `{model}` | {grade or '—'} | {_n(p1, '.3f')} | {_n(s5, '.2f')} | {_n(c1k, '.3f', '$')} | "
            f"{_n(cusd, '.4f', '$')} | {_n(p50, '.1f')} | {_n(tps, '.0f')} | {value} | {family} | "
            f"{ng if ng is not None else '—'} | {nerr if nerr is not None else '—'} | {elig} | {tier} |"
        )
    return out


def _full_judged_results_table(task_type: str) -> list[str]:
    """Full judged-benchmark leaderboard for ONE task (research/docs carry cost+latency columns;
    plan/spec are structural-only — no generation, so no cost/latency). Display-only appendix (rows lead
    with the backticked id → `load_task_ranking` skips them). Empty if the task has no metrics. Never raises."""
    try:
        from build_task_baselines import judged_eligible, load_judged_metrics

        metrics = load_judged_metrics(task_type)
        elig = judged_eligible(task_type)
    except Exception:
        return []
    if not metrics:
        return []

    def _n(v: object, spec: str, pre: str = "") -> str:
        try:
            return f"{pre}{format(v, spec)}" if v is not None else "—"
        except Exception:
            return "—"

    ordered = sorted(
        metrics.items(),
        key=lambda kv: (
            -(kv[1].get("score5") or 0),
            kv[1].get("cost_per_1k") if kv[1].get("cost_per_1k") is not None else 1e9,
            kv[0],
        ),
    )
    out = [
        "",
        f"## Full {task_type} benchmark results — judged (display only; not parsed for routing)",
    ]
    if task_type in ("research", "docs"):
        rp = "`recall`/`prec` bidirectional git-grounded · " if task_type == "docs" else ""
        out.append(
            f"_source: `microbench_judged.py --task {task_type}` → `model_judged_metrics`. {rp}"
            "`value`=score5÷$/1k · `eligible` = score5 ≥ 3.5 · $/1k ≤ 5 · p50 ≤ 15s._"
        )
        if task_type == "docs":
            out.append(
                "| model | grade | score5 | recall | prec | $/1k | p50 s | value | family | eligible |"
            )
            out.append("|---|:-:|--:|--:|--:|--:|--:|--:|:-:|:-:|")
        else:
            out.append("| model | grade | score5 | $/1k | p50 s | value | family | eligible |")
            out.append("|---|:-:|--:|--:|--:|--:|:-:|:-:|")
        for m, d in ordered:
            s5, c1k = d.get("score5"), d.get("cost_per_1k")
            value = f"{(s5 / c1k):.1f}" if (s5 is not None and c1k) else "—"
            flag = "✅" if m in elig else "—"
            fam = m.split("/", 1)[0]
            if task_type == "docs":
                out.append(
                    f"| `{m}` | {d.get('grade') or '—'} | {_n(s5, '.2f')} | {_n(d.get('recall'), '.2f')} | "
                    f"{_n(d.get('precision'), '.2f')} | {_n(c1k, '.3f', '$')} | {_n(d.get('p50_latency_s'), '.1f')} | "
                    f"{value} | {fam} | {flag} |"
                )
            else:
                out.append(
                    f"| `{m}` | {d.get('grade') or '—'} | {_n(s5, '.2f')} | {_n(c1k, '.3f', '$')} | "
                    f"{_n(d.get('p50_latency_s'), '.1f')} | {value} | {fam} | {flag} |"
                )
    else:  # plan / spec — structural filter, no cost/latency
        out.append(
            "_source: `structural_grader` (plan/spec structural filter, no paid generation) → "
            "`model_judged_metrics`. `structural` = checks passed · `eligible` = score5 ≥ 3.5._"
        )
        out.append("| model | grade | score5 | structural | family | eligible |")
        out.append("|---|:-:|--:|:-:|:-:|:-:|")
        for m, d in ordered:
            flag = "✅" if m in elig else "—"
            out.append(
                f"| `{m}` | {d.get('grade') or '—'} | {_n(d.get('score5'), '.2f')} | "
                f"{d.get('structural') or '—'} | {m.split('/', 1)[0]} | {flag} |"
            )
    return out


def _judged_bench_ran(task_type: str) -> bool:
    """Has the judged benchmark produced ANY metrics for this task? Distinguishes 'never ran' (gate
    inactive → prior behaviour) from 'ran' (gate ACTIVE → ineligible fleet rows dropped, fail-closed).
    Monkeypatch point for tests, mirroring `_code_bench_ran`. Never raises."""
    try:
        from build_task_baselines import load_judged_metrics

        return bool(load_judged_metrics(task_type))
    except Exception:
        return False


def _judged_benchmark_models(task_type: str) -> list[str]:
    """The judged-ELIGIBLE set for a task, ranked best-first (score5 desc, then $/1k asc). Empty if the
    benchmark hasn't run. Analog of `_code_benchmark_models`. Never raises."""
    try:
        from build_task_baselines import judged_eligible, load_judged_metrics

        metrics = load_judged_metrics(task_type)
        elig = judged_eligible(task_type)
    except Exception:
        return []

    def _cost(m: str) -> float:
        c = metrics.get(m, {}).get("cost_per_1k")
        return c if c is not None else 1e9

    return sorted(
        (m for m in metrics if m in elig),
        key=lambda m: (-(metrics[m].get("score5") or 0), _cost(m), m),
    )


def _fmt_bench_review_row(
    rank: int,
    model: str,
    review_metrics: dict,
    tiers: object,
    canary: dict[str, float] | None = None,
) -> str:
    """Render a benchmark-measured review row that SHOWS its metrics (previously all `—`).

    Maps `model_review_metrics` into the 8-col table shape so `pick_models` still parses (model at
    col 2, `n` at the last col): shrunk_q=`score5†`, success=recall, avg_cost=`$/1k`,
    avg_quality=precision. `n=0` is preserved — these have no fleet usage, so a caller passing
    `min_n>=1` still filters them out. The `†` marks a benchmark measurement, not fleet usage."""
    d = review_metrics.get(model) or {}
    s5, rec, c1k, prec = d.get("score5"), d.get("recall"), d.get("cost_per_1k"), d.get("precision")
    q = f"{s5:.2f}†" if s5 is not None else "[benchmark]"
    su = f"{rec:.2f}" if rec is not None else "—"
    ac = f"${c1k:.4f}" if c1k is not None else "—"
    aq = f"{prec:.2f}" if prec is not None else "—"
    cell = _grounding_cell((canary or {}).get(model))
    return f"| {rank} | `{model}` | {q} | {su} | {ac} | {aq} | {_fmt_tier(tiers, model)} | {cell} | 0 |"


def _review_bench_ran() -> bool:
    """Has the review benchmark produced ANY metrics? Distinguishes 'benchmark never ran' (gate
    inactive → prior behaviour) from 'benchmark ran but nobody cleared the gate' (gate ACTIVE →
    ineligible fleet review rows are dropped, i.e. fail-CLOSED — never fail-open past the operator's
    permanent constraint). Never raises."""
    try:
        from build_task_baselines import load_review_metrics

        return bool(load_review_metrics())
    except Exception:
        return False


def _selected_shortlists() -> list[str]:
    """The headline: the SELECTED reviewers + coders (gate outputs), shown UPFRONT so the reader
    sees the shortlists without hunting `✅` in the 57-row leaderboards below. Display-only; the
    rows lead with a backticked model id so `load_task_ranking` skips them. Never raises."""
    import sqlite3

    db_path = Path(__file__).resolve().parent / "kilo_agents.db"

    def _n(v: object, spec: str, pre: str = "") -> str:
        try:
            return f"{pre}{format(v, spec)}" if v is not None else "—"
        except Exception:
            return "—"

    try:
        from build_task_baselines import (
            CODE_TIERS,
            code_eligible,
            code_tier,
            judged_eligible,
            load_judged_metrics,
            review_eligible,
        )

        rev_set, cod_set = review_eligible(), code_eligible()
        judged_sets = {jt: judged_eligible(jt) for jt in ("research", "docs", "plan", "spec")}
    except Exception:
        return []
    if not rev_set and not cod_set and not any(judged_sets.values()):
        return []

    def _q(sql: str) -> list:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                return conn.execute(sql).fetchall()
            finally:
                conn.close()
        except Exception:
            return []

    out: list[str] = [
        "",
        "## ✅ Selected subagents — the gate shortlists (`pick_models` picks from these)",
        "",
    ]

    if rev_set:
        rrows = _q(
            "SELECT m.model_id, m.grade, m.score5, m.recall, m.cost_per_1k, m.cost_usd, m.p50_latency_s "
            "FROM model_review_metrics m JOIN (SELECT model_id, MAX(built_at) mb FROM model_review_metrics "
            "GROUP BY model_id) t ON m.model_id=t.model_id AND m.built_at=t.mb "
            # ⚠️ SAME BANDING AS THE ROUTER. This table had its own `ORDER BY m.score5 DESC` while
            # `_load_review_fallback` (the order `pick_models` actually consumes) bands score5 first
            # and then sorts by COST — so the doc a human reads ranked models the router did not.
            # One corpus item ≈ 0.2 of score5 and only ONE item discriminates at the frontier, so a
            # raw-score5 sort here put a $448/1k model above a $0.165/1k one on a difference the
            # instrument cannot resolve. Band, then cost. Keep in step with _SCORE5_NOISE_BAND.
            f"ORDER BY CAST(m.score5 / {_SCORE5_NOISE_BAND} AS INT) DESC, m.cost_per_1k ASC, m.model_id"
        )
        out += [
            f"### Reviewers — {len(rev_set)} selected",
            "_gate: precision ≥ 0.99 · $/1k ≤ 0.70 · $/run < 0.007 · score5 ≥ 3.5 · p50 ≤ 10s · "
            f"ordered by score5 BANDED to {_SCORE5_NOISE_BAND} (one corpus item), then cost asc — the "
            "corpus resolves 1 of 22 items at the frontier, so a finer quality sort is noise_",
            "| model | grade | score5 | recall | $/1k | $/run | p50 s |",
            "|---|:-:|--:|--:|--:|--:|--:|",
        ]
        out += [
            f"| `{mid}` | {g or '—'} | {_n(s5, '.2f')} | {_n(rec, '.2f')} | {_n(c1k, '.3f', '$')} | "
            f"{_n(cusd, '.4f', '$')} | {_n(p50, '.1f')} |"
            for mid, g, s5, rec, c1k, cusd, p50 in rrows
            if mid in rev_set
        ]
        out.append("")

    if cod_set:
        crows = {
            r[0]: r
            for r in _q(
                "SELECT m.model_id, m.grade, m.pass_at_1, m.score5, m.cost_per_1k, m.cost_usd, m.p50_latency_s "
                "FROM model_coding_metrics m JOIN (SELECT model_id, MAX(built_at) mb FROM model_coding_metrics "
                "GROUP BY model_id) t ON m.model_id=t.model_id AND m.built_at=t.mb"
            )
        }
        out += [
            f"### Coders — {len(cod_set)} selected (by tier)",
            "_gate: n_err ≤ 1 · pass@1 ≥ 0.90 · $/1k ≤ 3.5 · p50 ≤ 10s_",
        ]
        # tiered groups first (in CODE_TIERS order), then any eligible-but-untiered model
        groups = [(t, [m for m in ms if m in cod_set]) for t, ms in CODE_TIERS.items()]
        groups.append(("untiered", [m for m in cod_set if code_tier(m) is None]))
        for tier, models in groups:
            if not models:
                continue
            out += [
                f"**{tier}:**",
                "| model | grade | pass@1 | $/1k | $/run | p50 s |",
                "|---|:-:|--:|--:|--:|--:|",
            ]
            for m in models:
                r = crows.get(m)
                if r:
                    out.append(
                        f"| `{m}` | {r[1] or '—'} | {_n(r[2], '.3f')} | {_n(r[4], '.3f', '$')} | "
                        f"{_n(r[5], '.4f', '$')} | {_n(r[6], '.1f')} |"
                    )
            out.append("")

    # Judged-task shortlists (research/docs generation-gated; plan/spec structural-gated) — same headline.
    jgate_desc = {
        "research": "score5 ≥ 3.5 · $/1k ≤ 5 · p50 ≤ 15s",
        "docs": "score5 ≥ 3.5 · $/1k ≤ 5 · p50 ≤ 15s",
        "plan": "score5 ≥ 3.5 (structural filter; flywheel is the primary signal)",
        "spec": "score5 ≥ 3.5 (structural filter; flywheel is the primary signal)",
    }
    for jt in ("research", "docs", "plan", "spec"):
        jset = judged_sets.get(jt) or set()
        if not jset:
            continue
        jm = load_judged_metrics(jt)
        ranked = sorted(jset, key=lambda x: (-(jm.get(x, {}).get("score5") or 0), x))
        out += [f"### {jt.capitalize()} — {len(jset)} selected", f"_gate: {jgate_desc[jt]}_"]
        if jt in ("research", "docs"):
            out += ["| model | grade | score5 | $/1k | p50 s |", "|---|:-:|--:|--:|--:|"]
            for m in ranked:
                d = jm.get(m, {})
                out.append(
                    f"| `{m}` | {d.get('grade') or '—'} | {_n(d.get('score5'), '.2f')} | "
                    f"{_n(d.get('cost_per_1k'), '.3f', '$')} | {_n(d.get('p50_latency_s'), '.1f')} |"
                )
        else:
            out += ["| model | grade | score5 | structural |", "|---|:-:|--:|:-:|"]
            for m in ranked:
                d = jm.get(m, {})
                out.append(
                    f"| `{m}` | {d.get('grade') or '—'} | {_n(d.get('score5'), '.2f')} | "
                    f"{d.get('structural') or '—'} |"
                )
        out.append("")
    return out


def _code_benchmark_models() -> list[str]:
    """The code-ELIGIBLE set ranked best-first (measured pass@1 desc, then real $/1k asc). Empty if
    the coding benchmark hasn't run → the `### code` section keeps its auto-tier CODING fallback.
    This is the coding analog of `_review_benchmark_models`. Never raises."""
    try:
        from build_task_baselines import code_eligible, load_coding_metrics

        metrics = load_coding_metrics()
        elig = code_eligible()
    except Exception:
        return []

    def _cost(m: str) -> float:
        c = metrics.get(m, {}).get("cost_per_1k")
        return c if c is not None else 1e9

    return sorted(
        (m for m in metrics if m in elig),
        key=lambda m: (-(metrics[m].get("pass_at_1") or 0), _cost(m), m),
    )


def _code_bench_ran() -> bool:
    """Has the coding benchmark produced ANY metrics? Distinguishes 'never ran' (code gate inactive
    → prior behaviour) from 'ran' (gate ACTIVE → ineligible fleet code rows dropped, fail-closed).
    Monkeypatch point for tests, mirroring `_review_bench_ran`. Never raises."""
    try:
        from build_task_baselines import load_coding_metrics

        return bool(load_coding_metrics())
    except Exception:
        return False


def render(
    rows: list,
    state: str = "ok",
    include_full_results: bool = True,
    canary: dict[str, float] | None = None,
) -> str:
    """Emit the ranked markdown from aggregated rows.

    Rows shape: (task_type, model, n, avg_cost, avg_quality, success_rate).
    `canary` maps model -> canary-grounding average (CANARY_QUERY); every table row gains a
    `grounding` cell SECOND-TO-LAST (`n` stays last — fabrik-lib's load_task_ranking parses
    cells[-1] as the run count; column position is load-bearing). None/missing -> `—`.
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
        f"top-2 slots require n ≥ {MIN_RUNS_TOP2}; "
        f"grounding: canary avg ≥ 2.5 → ✓, below → ✗(score), no/thin/stale data → — | "
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
    canary = canary or {}
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

    # CODE gate — the operator's coding constraints (n_err ≤ 1 · pass@1 ≥ 0.90 · $/1k ≤ 3.5 · p50 ≤ 10s),
    # mirroring the review gate. When the coding benchmark HAS run, `code_eligible()` supersedes the
    # auto-tier CODING_SUBAGENT_SELECTION fallback for selection, so pick_models("code") returns exactly
    # the eligible set (ranked). Inactive (empty gate) when the benchmark has never run → prior behaviour.
    # claude-code/* are DISPLAY-only (spawn-native per the spec Boundaries — the pool can't dispatch a
    # claude-code/* id, it would 404 in _transport). Keep them OUT of the rank-led routing sections that
    # pick_models parses; they stay visible in the ✅ Selected shortlist (model-id-led) + the full tables.
    code_benchmark: list[str] = [
        m for m in _code_benchmark_models() if not m.startswith("claude-code/")
    ]
    code_gate: set[str] = set(code_benchmark)
    code_bench_ran: bool = _code_bench_ran()
    if code_bench_ran:
        coding_fallback_models = code_benchmark

    # JUDGED gates (research/docs/plan/spec) — mirror the code/review gates. Empty + inactive until the
    # operator runs `microbench_judged --all` (research/docs) / `correlated_prior` (plan/spec); once a
    # task's benchmark has run, its gate filters that task's fleet rows to the eligible set (fail-closed).
    judged_gate: dict[str, set[str]] = {}
    judged_ran: dict[str, bool] = {}
    for _jt in ("research", "docs", "plan", "spec"):
        judged_ran[_jt] = _judged_bench_ran(_jt)
        judged_gate[_jt] = set(_judged_benchmark_models(_jt))

    # REVIEW gate + supplement — the operator's permanent constraints (precision ≥ 99% · real
    # $/1k ≤ 0.70 · p50 ≤ 10s) applied to the `review` task_type. `review_benchmark` is the
    # eligible set ranked best-first; `review_gate` filters fleet review rows to only these ids.
    # Both empty when the benchmark hasn't run → review behaves as before (no gate).
    # claude-code/* excluded from the rank-led routing set (see code_benchmark above — spawn-native, not pool).
    review_benchmark: list[str] = [
        m for m in _review_benchmark_models() if not m.startswith("claude-code/")
    ]
    review_gate: set[str] = set(review_benchmark)
    # measured metrics for the benchmark review rows, so the doc SHOWS score5/recall/$1k/precision
    # instead of `—` placeholders (the data was loaded to RANK these models, then discarded at render).
    try:
        from build_task_baselines import load_review_metrics as _load_rev_metrics

        review_metrics: dict = _load_rev_metrics()
    except Exception:
        review_metrics = {}
    # Gate is active whenever the benchmark RAN — even if zero models cleared it (fail-closed: drop
    # the ineligible fleet review rows rather than pass them through). Inactive only when the
    # benchmark has never run (no data → don't blank the section).
    review_bench_ran: bool = _review_bench_ran()

    # Stub only when there is genuinely NOTHING to show. A benchmark that ran but whose only eligible
    # tiers are claude-code/* leaves the routing lists empty (FIX-2 strips them — they're spawn-native),
    # yet the ✅ Selected shortlist below still DISPLAYS them; don't blank that behind the stub. Routing
    # correctly still falls back to _TABLE (no rank-led sections emitted).
    if (
        not kept
        and not coding_fallback_models
        and not review_benchmark
        and not review_bench_ran
        and not code_bench_ran
    ):
        return header + (
            "No aggregated runs yet — `pick_models` continues to use vendored `_TABLE` default at "
            "`/opt/fabrik-lib/subagents/subagents/select.py:58`.\n"
        )
    out = [header]
    # Headline the SELECTED shortlists at the TOP (gated like the real-DB leaderboards below,
    # so unit tests asserting on synthetic `rows` don't read the real kilo_agents.db).
    if include_full_results:
        out.extend(_selected_shortlists())
    # Track which task_types actually emitted a section — the CODING
    # supplement below emits its own `### code` header when no fleet code
    # section was produced.
    emitted_task_types: set[str] = set()
    for task_type in sorted(by_task):
        task_rows = by_task[task_type]
        # n_total is the FULL fleet total for this task (computed BEFORE the review gate) so it means
        # the same thing in every section — "total observed fleet calls", not "calls among survivors".
        n_total = sum(r[2] for r in task_rows)
        # Permanent review gate: only benchmark-eligible models survive in `review`. Active whenever
        # the benchmark RAN — fail-CLOSED even if zero models cleared it (drop ineligible rows rather
        # than pass them through); inactive only when the benchmark has never run (no data).
        if task_type == "review" and review_bench_ran:
            task_rows = [r for r in task_rows if r[1] in review_gate]
        # Permanent code gate: only code_eligible() models survive in `code` once the coding
        # benchmark has run (fail-closed, mirroring review).
        if task_type == "code" and code_bench_ran:
            task_rows = [r for r in task_rows if r[1] in code_gate]
        # Judged gates (research/docs/plan/spec) — fail-closed once that task's benchmark has run.
        if task_type in judged_gate and judged_ran.get(task_type):
            task_rows = [r for r in task_rows if r[1] in judged_gate[task_type]]
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
        # `grounding` and `quality_tier` sit before `n`, which stays LAST so `cells[-1]`
        # is the run count fabrik-lib's `load_task_ranking()` parses (model is `cells[1]`;
        # the real parse sites are `libs/subagents/select.py:296,303`). Column position matters.
        # `shrunk_q` replaces the old `value` column (formula changed — the
        # score no longer drives rank order; cost does, among gate-survivors).
        out.append(
            "| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | grounding | n |"
        )
        out.append("|---:|---|---:|---:|---:|---:|:-:|:-:|---:|")
        emitted_code_models: set[str] = set()
        emitted_review_models: set[str] = set()
        code_last_rank = 0
        review_last_rank = 0
        for rank, (r, shrunk_q) in enumerate(scored, start=1):
            out.append(
                f"| {rank} | `{r[1]}` | {shrunk_q:.2f} | {r[5]:.2f} | ${r[3]:.4f} | {r[4]:.2f} | "
                f"{_fmt_tier(tiers, r[1])} | {_grounding_cell(canary.get(r[1]))} | {r[2]} |"
            )
            if task_type == "code":
                emitted_code_models.add(r[1])
                code_last_rank = rank
            elif task_type == "review":
                emitted_review_models.add(r[1])
                review_last_rank = rank

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
                    f"| {i} | `{model}` | [benchmark] | — | — | — | {_fmt_tier(tiers, model)} | "
                    f"{_grounding_cell(canary.get(model))} | 0 |"
                )
        # REVIEW supplement — same shape: append gate-eligible benchmark models below the fleet
        # review rows so pick_models("review") sees a benched-but-not-yet-fleet-used reviewer.
        if task_type == "review" and review_benchmark:
            for i, model in enumerate(
                [m for m in review_benchmark if m not in emitted_review_models],
                start=review_last_rank + 1,
            ):
                out.append(_fmt_bench_review_row(i, model, review_metrics, tiers, canary))
        out.append("")
        emitted_task_types.add(task_type)

    # CODING supplement — mode (b): if the fleet had zero `code` rows above
    # the quality gate, no `### code` header was emitted in the loop above.
    # Fall back to a dedicated section so `pick_models("code")` still has a
    # benchmark-ranked list. Same 8-column shape as fleet sections.
    if "code" not in emitted_task_types and coding_fallback_models:
        out.append("### code (n_total=0, fallback from CODING_SUBAGENT_SELECTION.md)")
        out.append(
            "| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | grounding | n |"
        )
        out.append("|---:|---|---:|---:|---:|---:|:-:|:-:|---:|")
        for rank, model in enumerate(coding_fallback_models, start=1):
            out.append(
                f"| {rank} | `{model}` | [benchmark] | — | — | — | {_fmt_tier(tiers, model)} | "
                f"{_grounding_cell(canary.get(model))} | 0 |"
            )
        out.append("")

    # REVIEW fallback — mode (b): no fleet `review` rows cleared the gate above, so emit a
    # dedicated section from the gate-eligible benchmark so pick_models("review") still has a list.
    if "review" not in emitted_task_types and review_benchmark:
        # n_eligible_fleet=0 (not n_total=0): fleet review calls may exist but none cleared the gate;
        # this section lists the gate-eligible benchmark models so pick_models("review") has a list.
        out.append("### review (n_eligible_fleet=0, gated benchmark from model_review_metrics)")
        out.append(
            "_benchmark rows (`†`): shrunk_q=score5 · success=recall · avg_cost=$/1k · avg_quality=precision · n=0 (no fleet usage yet)_"
        )
        out.append(
            "| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | grounding | n |"
        )
        out.append("|---:|---|---:|---:|---:|---:|:-:|:-:|---:|")
        for rank, model in enumerate(review_benchmark, start=1):
            out.append(_fmt_bench_review_row(rank, model, review_metrics, tiers, canary))
        out.append("")

    # Human-readable full leaderboards (all measured columns) appended below the router sections.
    # These read the real kilo_agents.db — gated off in unit tests that assert on synthetic `rows`.
    if include_full_results:
        out.extend(_full_review_results_table())
        out.extend(_full_review_hard_results_table())
        out.extend(_full_coding_results_table())
        for _jt in ("research", "docs", "plan", "spec"):
            out.extend(_full_judged_results_table(_jt))

    return "\n".join(out) + "\n"


def _atomic_write(path: Path, content: str) -> None:
    """Write via temp file + os.replace so a mid-write crash never leaves partial file.
    Cloned from `engine/rank_coding_subagents.py (ai-model-catalog):345`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    state, rows = _query_rows()
    _canary_state, canary = _query_canary_rows()  # "error" -> {} -> every cell renders "—"
    md = render(rows, state=state, canary=canary)
    # ⚠️ DO NOT overwrite a good doc with the broken-read stub (Phase A.0, 2026-08-12).
    # Alerting on a broken read is necessary but NOT sufficient: writing the stub first means
    # daily_refresh.sh then git-commits and pushes it (:552/:576/:584), fleet-syncing a
    # 5-line "AGGREGATION FAILED" placeholder to the 49 vendored pick_models copies, which
    # then fall back to the baked-in _TABLE. The alert would arrive AFTER the poisoning
    # completed — fail-open with a receipt. Yesterday's good doc is strictly better than a
    # stub, so on a BROKEN read we keep it and exit non-zero. First run (no doc yet) still
    # writes the stub, because an absent doc is worse than a labelled one.
    # "Keep the existing doc" is only correct if the existing doc is GOOD. After a first-run
    # failure the stub IS on disk, so every later broken run would preserve the stub forever
    # while the alert claims "the fleet is on yesterday-good, not poisoned" — the opposite of
    # the truth. A stub is not worth protecting: re-write it (same content, honest date).
    # Guarded: an OSError here (permissions, or a race with daily_refresh's git commit) would
    # otherwise raise out of main() BEFORE the keep-guard runs, skipping the very protection
    # this block exists to apply. On an unreadable doc, treat it as NOT a stub — i.e. keep it.
    try:
        existing_is_stub = OUTPUT_PATH.exists() and "AGGREGATION FAILED" in OUTPUT_PATH.read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        existing_is_stub = False
    if state == "error" and OUTPUT_PATH.exists() and not existing_is_stub:
        print(
            f"[rank_task_subagents] read BROKEN — KEEPING the existing {OUTPUT_PATH.name} "
            "rather than publishing the failure stub (it would be fleet-synced)",
            file=sys.stderr,
        )
        return 1
    _atomic_write(OUTPUT_PATH, md)
    print(f"wrote {OUTPUT_PATH} (state={state}, {len(rows)} rows aggregated)")
    # Exit non-zero on real aggregation failure so daily_refresh.sh's `|| echo "failed"`
    # logs it. Empty-pool (state="ok", 0 rows) is a healthy outcome and exits 0.
    return 1 if state == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
