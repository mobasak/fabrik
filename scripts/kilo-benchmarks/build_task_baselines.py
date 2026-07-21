#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/rank_task_subagents.py scripts/kilo-benchmarks/rank_coding_subagents.py libs/subagents/select.py
"""Per-(model, task_type) quality PRIOR, derived from benchmarks that actually measure the task.

The pool's ranking is `shrunk_q = (n·avg_q + K·tier_baseline) / (n + K)` — a blend of the
flywheel (`avg_q`, per-task-type, from our own `set_quality` verdicts) and a **prior**
(`tier_baseline`). The flywheel half is already task-aware. The prior half was **not**:
it came from a single `agents.quality_tier` column, so a model carried the *same* prior
whether it was being picked for `code`, `review` or `ops`. Since the prior dominates until
n≈K(=10), a task type with few runs — `code` had **16** — was effectively being selected by
a task-blind guess.

This fills that gap, and ONLY where a benchmark genuinely measures the task:

    ops   <- Terminal-Bench 2.x  system-administration + security   (17 tasks)
    code  <- Terminal-Bench 2.x  software-engineering               (26 tasks)

Everything else (`review`, `spec`, `plan`, `docs`, `docs-review`, `research`) gets **no row**.
That is deliberate. The benchmarks that measure those tasks exist — SWE-PRBench (code review),
SpecBench (design critique), CodeWiki (documentation) — but their published leaderboards score
frontier models and cover only ~30-40% of the cheap OpenRouter pool we actually dispatch. A
prior imported from models that were never tested is a fabricated number wearing a citation, and
importing one is exactly the mistake that had us hire a model on an aggregate that hid its
profile. Absent a row, `rank_task_subagents` falls back to the general `quality_tier` — the
honest status quo — and the flywheel does the work.

Coverage is REPORTED, never assumed: a model absent from the benchmark simply has no row.

Source table: `tbench_leaderboard_results` (scraped by scrape_tbench_task_results.py).
Scale: benchmark pass-rate (0-1) -> the 0-5 quality scale the shrinkage formula speaks.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).parent / "kilo_agents.db"

# task_type -> the Terminal-Bench categories that actually measure it.
# Only these two are honest; see the module docstring for why the rest are absent.
TASK_CATEGORIES: dict[str, tuple[str, ...]] = {
    "ops": ("system-administration", "security"),
    "code": ("software-engineering",),
}

# A benchmark pass-rate is 0-1; the shrinkage prior is 0-5. Map linearly.
# The quality gate sits at 2.5/5, i.e. a 50% pass-rate — a model that fails half the tasks
# a benchmark says define its job does not deserve a passing prior.
SCALE = 5.0

# A k=1 submission over the 17-task sysadmin set is 17 trials — a real signal. Set the floor
# below that, or every k=1 submission is silently discarded.
MIN_TRIALS = 15

_DDL = """
CREATE TABLE IF NOT EXISTS model_task_baseline (
    model_id   TEXT NOT NULL,
    task_type  TEXT NOT NULL,
    baseline   REAL NOT NULL,   -- 0-5, feeds shrunk_q's prior term
    pass_rate  REAL NOT NULL,   -- 0-1, the raw benchmark number it came from
    n_tasks    INTEGER,
    n_trials   INTEGER,
    source     TEXT NOT NULL,   -- exactly WHICH benchmark+categories produced this
    built_at   TEXT,
    PRIMARY KEY (model_id, task_type)
);
"""


def ensure_table(db_path: Path = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_DDL)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mtb_task ON model_task_baseline(task_type)")
        conn.commit()
    finally:
        conn.close()


# =================================================================================================
# REVIEW-subagent eligibility gate — the OPERATOR'S PERMANENT constraints.
#
# A model may be dispatched as a REVIEW subagent only if the ground-truth benchmark
# (microbench_review -> model_review_metrics) shows it clears ALL FIVE (precision · $/1k · p50 · $/run ·
# score5-floor). This is the single source
# of truth consumed by BOTH rank_task_subagents (gates the `review` task_type) and
# rank_coding_subagents (feeds the measured Doc↔Code grade). Change a threshold HERE, once.
# =================================================================================================
REVIEW_MIN_PRECISION = (
    0.99  # never flags correct code (100% precision in practice); trust its flags
)
REVIEW_MAX_COST_PER_1K = (
    0.70  # real OpenRouter-billed $ per 1000 reviews (usage.cost, not estimate)
)
REVIEW_MAX_P50_S = (
    10.0  # median call latency; consistently-slow models excluded (coarse — see the note)
)
# A reviewer must catch at least ONE planted defect. Without this, a model that always answers `[]`
# ("no bugs") scores recall=0 AND precision=1.0 (it never flags a control either) and would clear
# the precision/cost/p50 gate — an "eligible" reviewer that catches nothing. This is the floor, not a
# quality bar; the operator may raise it (recall differentiation among survivors is the ranking's job).
REVIEW_MIN_RECALL = 0.0  # strict `>`: recall must exceed this (catch ≥1 defect)
# Operator value tightening (2026-07-19): a reviewer must also be cheap-PER-REVIEW and trustworthy.
REVIEW_MAX_RUN_COST = 0.007  # real $ for ONE review pass (usage.cost); strict `<`
REVIEW_TRUST_FLOOR_SCORE5 = 3.5  # grade ≥ B+; below this recall < 0.55 → misses too many defects


def load_review_metrics(db_path: Path = DB_PATH) -> dict[str, dict]:
    """model_id -> the LATEST-build review metrics, or {} if the table isn't populated yet.

    Fail-soft: a missing table (benchmark never run) returns {} so the ranker falls back to its
    prior behaviour rather than crashing the daily pipeline.
    """
    conn = sqlite3.connect(db_path)
    try:
        if not conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='model_review_metrics'"
        ).fetchone():
            return {}
        # LATEST-PER-MODEL, not the latest GLOBAL build: a partial re-run (`--models X` on a new
        # date) must update only X and keep every other model's most-recent metrics — else the
        # eligible set silently collapses to just the re-run models and the fleet review doc drops
        # everyone else. (Correlated MAX per model_id.)
        rows = conn.execute(
            "SELECT m.model_id, m.grade, m.score5, m.recall, m.precision, m.cost_per_1k, "
            "m.p50_latency_s, m.cost_usd FROM model_review_metrics m "
            "JOIN (SELECT model_id, MAX(built_at) AS mb FROM model_review_metrics GROUP BY model_id) t "
            "ON m.model_id=t.model_id AND m.built_at=t.mb"
        ).fetchall()
    finally:
        conn.close()
    return {
        r[0]: {
            "grade": r[1],
            "score5": r[2],
            "recall": r[3],
            "precision": r[4],
            "cost_per_1k": r[5],
            "p50_latency_s": r[6],
            "cost_usd": r[7],
        }
        for r in rows
    }


def review_eligible(db_path: Path = DB_PATH) -> set[str]:
    """Models that clear the permanent review gate: precision ≥ 0.99 · $/1k ≤ 0.70 · p50 ≤ 10s ·
    $/run < 0.007 · score5 ≥ 3.5 (all five — the operator's constants above).

    Empty set if the benchmark hasn't run — callers treat "no benchmark data" as "gate not active"
    (fall back to prior behaviour) rather than "nothing eligible".
    """
    return {
        m
        for m, d in load_review_metrics(db_path).items()
        # carve-out: a claude-code/* native tier stays shortlist-visible past the gates — its ① API-equivalent
        # cost can exceed $/1k + $/run and npx cold-start exceeds p50; the value sort still ranks it by ① cost.
        if m.startswith("claude-code/")
        or (
            (d["precision"] or 0) >= REVIEW_MIN_PRECISION
            and (d["recall"] or 0) > REVIEW_MIN_RECALL  # must catch ≥1 defect (not a do-nothing model)
            and (d["cost_per_1k"] if d["cost_per_1k"] is not None else 1e9) <= REVIEW_MAX_COST_PER_1K
            and (d["p50_latency_s"] if d["p50_latency_s"] is not None else 1e9) <= REVIEW_MAX_P50_S
            and (d["cost_usd"] if d["cost_usd"] is not None else 1e9) < REVIEW_MAX_RUN_COST
            and (d["score5"] or 0) >= REVIEW_TRUST_FLOOR_SCORE5
        )
    }


def load_coding_metrics(db_path: Path = DB_PATH) -> dict[str, dict]:
    """model_id -> the LATEST-build coding metrics, or {} if the table isn't populated yet.

    Parallel to load_review_metrics (measured by microbench_coding_direct -> model_coding_metrics).
    Fail-soft: a missing table returns {} so the daily build/rankers fall back to prior behaviour
    rather than crashing. Latest-PER-MODEL (correlated MAX), not the latest GLOBAL build, so a
    partial re-run keeps every other model's most-recent coding metrics.
    """
    conn = sqlite3.connect(db_path)
    try:
        if not conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='model_coding_metrics'"
        ).fetchone():
            return {}
        rows = conn.execute(
            "SELECT m.model_id, m.grade, m.pass_at_1, m.score5, m.cost_per_1k, m.p50_latency_s, m.n_err "
            "FROM model_coding_metrics m "
            "JOIN (SELECT model_id, MAX(built_at) AS mb FROM model_coding_metrics GROUP BY model_id) t "
            "ON m.model_id=t.model_id AND m.built_at=t.mb"
        ).fetchall()
    finally:
        conn.close()
    return {
        r[0]: {
            "grade": r[1],
            "pass_at_1": r[2],
            "score5": r[3],
            "cost_per_1k": r[4],
            "p50_latency_s": r[5],
            "n_err": r[6],
        }
        for r in rows
    }


# =================================================================================================
# CODE-subagent eligibility gate + curated use-case tiers — the OPERATOR'S coding constraints.
# Mirrors the REVIEW gate above; consumed by rank_task_subagents (the `### Full coding` table).
# Coding is GENERATION not detection, so there is no `precision` analog — the trust axis is
# RELIABILITY (`n_err`: does it reliably PRODUCE an answer) plus `pass_at_1` (is it correct).
# Change a threshold HERE, once.
# =================================================================================================
CODE_MAX_ERRORS = 1  # n_err ≤ : reliability — ≤1 of 50 problems errored (the coding "trust" axis)
CODE_MIN_PASS_AT_1 = 0.90  # pass@1 ≥ : quality floor (grade A+); cuts the grade-A 0.88 tail
CODE_MAX_COST_PER_1K = 3.5  # $/1k ≤ : affordable
CODE_MAX_P50_S = 10.0  # p50 ≤ : responsive

# Curated use-case tiers over the eligible set. NOT pure thresholds — a judgment on how
# pick_models("code") dispatches at different stakes. RE-CURATE when the benchmark re-runs
# (a model absent here but still eligible has tier=None). No "specialized" tier: the aggregate
# LiveCodeBench pass@1 measures no sub-topic strength, so we don't label one.
CODE_TIERS: dict[str, tuple[str, ...]] = {
    "daily-driver": (  # A+, cheap (≤$1.33/1k), fast — the everyday workhorses
        "google/gemini-3-flash-preview",
        "deepseek/deepseek-v3.2-exp",
        "qwen/qwen3-coder-next",
        "openai/gpt-5.4-mini",
    ),
    "premium": (  # highest quality (0.98/0.94) but 2-3x the cost — for hard / high-stakes code
        "openai/gpt-5.6-luna",
        "writer/palmyra-x5",
    ),
}


def code_eligible(db_path: Path = DB_PATH) -> set[str]:
    """Models that clear the permanent coding gate: n_err ≤ 1 · pass@1 ≥ 0.90 · $/1k ≤ 3.5 · p50 ≤ 10s.

    Empty set if the benchmark hasn't run — callers treat "no benchmark data" as "gate not active"
    (fall back to prior behaviour) rather than "nothing eligible". A missing metric fails CLOSED.
    """
    return {
        m
        for m, d in load_coding_metrics(db_path).items()
        # carve-out (see review_eligible) — a claude-code/* native tier stays past the gates; value sort ranks by ①.
        if m.startswith("claude-code/")
        or (
            (d["n_err"] if d.get("n_err") is not None else 999) <= CODE_MAX_ERRORS
            and (d["pass_at_1"] or 0) >= CODE_MIN_PASS_AT_1
            and (d["cost_per_1k"] if d["cost_per_1k"] is not None else 1e9) <= CODE_MAX_COST_PER_1K
            and (d["p50_latency_s"] if d["p50_latency_s"] is not None else 1e9) <= CODE_MAX_P50_S
        )
    }


def code_tier(model_id: str) -> str | None:
    """The curated use-case tier for a coding model, or None if untiered. Display-only."""
    for tier, models in CODE_TIERS.items():
        if model_id in models:
            return tier
    return None


# =================================================================================================
# JUDGED-task eligibility gates (research / docs / plan / spec) — mirrors review/code above.
# Data is written by microbench_judged.py → model_judged_metrics (task_type-discriminated). Until the
# operator runs the paid `--all` benchmark, every reader returns {} → the gate is INACTIVE (fail-soft
# prior behaviour), never "nothing eligible". THRESHOLDS ARE PROVISIONAL — RE-CALIBRATE after the first
# real run (exactly as review/code were tuned from measured results). Change a threshold HERE, once.
#   research/docs (GENERATION-based): quality + cost + latency.
#   plan/spec     (STRUCTURAL, no generation): quality only (score5 already = structural-fraction × 5).
# =================================================================================================
JUDGED_TRUST_FLOOR_SCORE5 = 3.5  # score5 ≥ : quality floor for every judged task (≈ B+; trust)
JUDGED_MAX_COST_PER_1K = (
    5.0  # $/1k ≤ : research/docs affordability (generation cost per 1000 items)
)
JUDGED_MAX_P50_S = 15.0  # p50 ≤ : research/docs responsiveness (seconds)
_JUDGED_COST_TASKS = ("research", "docs")  # the cost/latency-gated (generation) judged tasks


def load_judged_metrics(task_type: str, db_path: Path = DB_PATH) -> dict[str, dict]:
    """model_id -> the LATEST-build judged metrics for ONE task_type, or {} if unpopulated.

    Reads the single `model_judged_metrics` table (task_type-discriminated) that microbench_judged
    writes — NOT a per-task `model_<task>_metrics` table (there is none). Latest-PER-MODEL (correlated
    MAX), fail-soft to {} on a missing table so the ranker falls back to prior behaviour."""
    conn = sqlite3.connect(db_path)
    try:
        if not conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='model_judged_metrics'"
        ).fetchone():
            return {}
        rows = conn.execute(
            "SELECT m.model_id, m.grade, m.score5, m.recall, m.precision, m.structural, "
            "m.cost_per_1k, m.p50_latency_s, m.n_err FROM model_judged_metrics m "
            "JOIN (SELECT model_id, MAX(built_at) AS mb FROM model_judged_metrics "
            "WHERE task_type=? GROUP BY model_id) t ON m.model_id=t.model_id AND m.built_at=t.mb "
            "WHERE m.task_type=? ORDER BY m.built_at, m.window",  # (built_at,window) → deterministic
            (
                task_type,
                task_type,
            ),  # last-wins on a same-day two-window tie (window ∈ PK, unlike the
        ).fetchall()  # review/coding metrics tables — the MAX-join alone would return BOTH window rows
    finally:
        conn.close()
    return {
        r[0]: {
            "grade": r[1],
            "score5": r[2],
            "recall": r[3],
            "precision": r[4],
            "structural": r[5],
            "cost_per_1k": r[6],
            "p50_latency_s": r[7],
            "n_err": r[8],
        }
        for r in rows
    }


def judged_eligible(task_type: str, db_path: Path = DB_PATH) -> set[str]:
    """Models that clear the gate for a judged task. research/docs gate on quality+cost+latency;
    plan/spec gate on quality only (structural — no generation, so no cost/latency). Empty set when the
    benchmark hasn't run (gate inactive). A missing metric fails CLOSED (excluded)."""
    metrics = load_judged_metrics(task_type, db_path)
    cost_gated = task_type in _JUDGED_COST_TASKS
    out: set[str] = set()
    for m, d in metrics.items():
        if (d["score5"] or 0) < JUDGED_TRUST_FLOOR_SCORE5:
            continue
        if cost_gated:
            if (d["cost_per_1k"] if d["cost_per_1k"] is not None else 1e9) > JUDGED_MAX_COST_PER_1K:
                continue
            if (d["p50_latency_s"] if d["p50_latency_s"] is not None else 1e9) > JUDGED_MAX_P50_S:
                continue
        out.add(m)
    return out


def build(conn, task_type: str, categories: tuple[str, ...]) -> list[dict]:
    """One row per model with enough benchmark trials in `categories` to be a real prior.

    Aggregated as passed / trials-that-RAN — errored trials (the sandbox died before the
    verifier ran) are excluded from the denominator, never scored 0. Counting infra flakes as
    model failures would deflate every model unlucky enough to hit them.

    A model with several leaderboard submissions (different agent scaffolds) is taken at its
    BEST: the prior should reflect what the model can do when driven competently, not the
    average of everyone's harness quality.
    """
    ph = ",".join("?" * len(categories))
    rows = conn.execute(
        f"""
        SELECT model_id, submission,
               1.0*SUM(n_passed) / NULLIF(SUM(n_trials - n_errored), 0) AS pass_rate,
               COUNT(*)          AS n_tasks,
               SUM(n_trials)     AS total_trials
        FROM tbench_leaderboard_results
        WHERE model_id IS NOT NULL AND category IN ({ph})
        GROUP BY model_id, submission
        -- `total_trials`, NOT `n_trials`: the SUM alias would collide with the raw column and
        -- SQLite's HAVING binds the COLUMN (always 1-5), silently filtering out every group.
        HAVING pass_rate IS NOT NULL AND total_trials >= ?
        """,  # noqa: S608 — ph is a fixed count of bound placeholders
        (*categories, MIN_TRIALS),
    ).fetchall()

    best: dict[str, dict] = {}
    for model_id, _sub, pr, n_tasks, n_trials in rows:
        if model_id not in best or pr > best[model_id]["pass_rate"]:
            best[model_id] = {
                "model_id": model_id,
                "task_type": task_type,
                "baseline": round(pr * SCALE, 3),
                "pass_rate": round(pr, 4),
                "n_tasks": n_tasks,
                "n_trials": n_trials,
                "source": f"terminal-bench-2.x:{'+'.join(categories)}",
            }
    return list(best.values())


def persist(conn, rows: list[dict]) -> int:
    today = date.today().isoformat()
    for r in rows:
        conn.execute(
            "INSERT OR REPLACE INTO model_task_baseline "
            "(model_id, task_type, baseline, pass_rate, n_tasks, n_trials, source, built_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                r["model_id"],
                r["task_type"],
                r["baseline"],
                r["pass_rate"],
                r["n_tasks"],
                r["n_trials"],
                r["source"],
                today,
            ),
        )
    conn.commit()
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="build_task_baselines",
        description="Per-(model, task_type) benchmark prior for the subagent pool.",
    )
    p.add_argument("--report", action="store_true", help="Print the table; build nothing.")
    args = p.parse_args(argv)

    ensure_table(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    try:
        if not args.report:
            total = 0
            for task_type, cats in TASK_CATEGORIES.items():
                rows = build(conn, task_type, cats)
                if task_type == "code":
                    # PRECEDENCE: a measured LiveCodeBench pass@1 (model_coding_metrics, written by
                    # microbench_coding_direct with source='livecodebench:…') beats the terminal-bench
                    # scraped 'code' baseline. Drop measured models from the scraped set so persist
                    # (INSERT OR REPLACE on PK model_id,task_type) never clobbers the measured prior.
                    measured = set(load_coding_metrics())
                    kept = [r for r in rows if r["model_id"] not in measured]
                    if len(kept) != len(rows):
                        print(
                            f"[baselines] code: preserved {len(rows) - len(kept)} measured "
                            "livecodebench prior(s) over terminal-bench",
                            file=sys.stderr,
                        )
                    rows = kept
                total += persist(conn, rows)
                print(
                    f"[baselines] {task_type:<6} <- {'+'.join(cats)}: {len(rows)} models",
                    file=sys.stderr,
                )
            if not total:
                print(
                    "error: 0 baselines built — is tbench_leaderboard_results populated? "
                    "run scrape_tbench_task_results.py first",
                    file=sys.stderr,
                )
                return 1

        print(f"\n{'model':<32}{'task':<7}{'prior/5':>8}{'pass':>7}{'trials':>8}")
        print("-" * 64)
        for m, t, b, pr, n in conn.execute(
            "SELECT model_id, task_type, baseline, pass_rate, n_trials "
            "FROM model_task_baseline ORDER BY task_type, baseline DESC"
        ):
            print(f"  {m[:30]:<32}{t:<7}{b:>8.2f}{pr * 100:>6.0f}%{n:>8}")

        covered = conn.execute(
            "SELECT COUNT(DISTINCT model_id) FROM model_task_baseline"
        ).fetchone()[0]
        pool = conn.execute(
            "SELECT COUNT(*) FROM agents WHERE status='active' AND via_openrouter=1 AND has_tools=1"
        ).fetchone()[0]
        print(
            f"\n  coverage: {covered} models have a benchmark prior, of {pool} tool-capable "
            f"OR models. The rest keep the general quality_tier prior — reported, not faked."
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
