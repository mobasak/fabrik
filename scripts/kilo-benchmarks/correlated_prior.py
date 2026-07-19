# AFTER-EDIT: scripts/kilo-benchmarks/microbench_judged.py scripts/kilo-benchmarks/build_task_baselines.py
"""Correlated cold-start prior for the plan / spec judged task types (no paid generation).

plan/spec have no cheap ground-truth benchmark of their own, so a fresh model has no `plan`/`spec`
prior to shrink against until the flywheel warms up. We bridge that gap by CORRELATING off tasks we
DO measure:

    plan  prior  <-  mean(code, review)   # a good coder + reviewer tends to plan well
    spec  prior  <-  mean(docs, plan)      # a good doc-writer + planner tends to spec well

Each row lands in `model_task_baseline` with `source='correlated:<from>'` (so its provenance is never
confused with a real benchmark or a measured `microbench_judged:*` prior), `n_tasks=n_trials=0` (it is
a correlation, not observed trials). The PK is (model_id, task_type), so this is IDEMPOTENT /
re-runnable — a later MEASURED prior (INSERT OR REPLACE, same PK) cleanly supersedes the correlated one.

⚠️ INVOKED AT PHASE E, not now: the spec prior reads `docs` metrics that Phase C produces
concurrently — running this during Phase D would race C and seed spec off missing docs scores. Build
the module here; call `build()` from the Phase-E wiring once docs metrics exist.

    python correlated_prior.py            # seed the correlated plan+spec priors
    python correlated_prior.py --report   # print the correlated rows, seed nothing
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(
    0, str(SCRIPT_DIR)
)  # sibling-module imports (build_task_baselines, microbench_judged)

from build_task_baselines import DB_PATH  # noqa: E402 — needs the sys.path insert above


def _score_map(metrics: dict[str, dict]) -> dict[str, float]:
    """model_id -> score5 (0-5), dropping models without a numeric score5."""
    return {m: float(d["score5"]) for m, d in metrics.items() if d.get("score5") is not None}


def _mean_prior(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    """Per-model mean over whichever of the two sources has a score (≥1 required). The `source` tag
    (`correlated:X+Y`) names the correlation BASIS — the sources a prior MAY draw from — not a promise
    that both contributed for every model (a model present in only one source uses that one; reviewer S7)."""
    out: dict[str, float] = {}
    for model in set(a) | set(b):
        vals = [v for v in (a.get(model), b.get(model)) if v is not None]
        if vals:
            out[model] = round(sum(vals) / len(vals), 3)
    return out


def _write_priors(
    db_path: Path, task_type: str, priors: dict[str, float], source: str, scale: float
) -> int:
    """INSERT OR REPLACE one baseline row per model (idempotent on PK model_id,task_type)."""
    today = date.today().isoformat()
    conn = sqlite3.connect(db_path)
    n = 0
    try:
        for model, baseline in priors.items():
            conn.execute(
                "INSERT OR REPLACE INTO model_task_baseline "
                "(model_id, task_type, baseline, pass_rate, n_tasks, n_trials, source, built_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    model,
                    task_type,
                    round(baseline, 3),
                    round(baseline / scale, 4),
                    0,
                    0,
                    source,
                    today,
                ),
            )
            n += 1
        conn.commit()
    finally:
        conn.close()
    return n


def build(db_path: Path = DB_PATH) -> int:
    """Seed the correlated plan+spec priors from already-measured task metrics. Returns rows written.

    plan  <- mean(code, review)   source='correlated:code+review'
    spec  <- mean(docs, plan)     source='correlated:docs+plan'  (plan = measured if present, else the
                                   correlated plan just computed; a MEASURED plan wins the mean)

    Idempotent — safe to re-run; a missing source table fails soft to {} (fewer rows, never a crash)."""
    from build_task_baselines import ensure_table, load_coding_metrics, load_review_metrics
    from microbench_judged import SCALE, load_judged_metrics

    ensure_table(db_path)

    code = _score_map(load_coding_metrics(db_path))
    review = _score_map(load_review_metrics(db_path))
    docs = _score_map(load_judged_metrics("docs", db_path))

    plan_prior = _mean_prior(code, review)
    n = _write_priors(db_path, "plan", plan_prior, "correlated:code+review", SCALE)

    # SPEC prior is derived from docs+plan, so only seed it once DOCS metrics actually exist — else the
    # "mean" is just the plan values under a misleading `docs+plan` tag (reviewer S6; this is the exact
    # Phase-D-vs-C race the module warns about). A later run with docs present overwrites (idempotent).
    if docs:
        # A real MEASURED plan score (once microbench_judged --task plan has run) supersedes the
        # correlated plan when feeding the spec prior — measured beats correlated.
        plan_measured = _score_map(load_judged_metrics("plan", db_path))
        plan_for_spec = {**plan_prior, **plan_measured}
        spec_prior = _mean_prior(docs, plan_for_spec)
        n += _write_priors(db_path, "spec", spec_prior, "correlated:docs+plan", SCALE)
    else:
        print(
            "[correlated] docs metrics absent — skipping the spec prior (run --task docs first)",
            file=sys.stderr,
        )
    return n


def report(db_path: Path = DB_PATH) -> None:
    if not Path(db_path).exists():
        print("no db — run the review/coding/docs benchmarks first")
        return
    conn = sqlite3.connect(db_path)
    try:
        if not conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='model_task_baseline'"
        ).fetchone():
            print("no model_task_baseline table — nothing correlated yet")
            return
        rows = conn.execute(
            "SELECT model_id, task_type, baseline, source, built_at FROM model_task_baseline "
            "WHERE source LIKE 'correlated:%' ORDER BY task_type, baseline DESC"
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        print("no correlated priors yet — run `python correlated_prior.py`")
        return
    print(f"\n{'model':<34}{'task':<6}{'prior/5':>8}  source")
    print("-" * 72)
    for m, t, b, src, _built in rows:
        print(f"  {m[:32]:<34}{t:<6}{b:>8.2f}  {src}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="correlated_prior",
        description="Correlated cold-start plan/spec priors (INVOKED at Phase E — reads docs metrics).",
    )
    p.add_argument("--report", action="store_true", help="print correlated rows; seed nothing")
    args = p.parse_args(argv)
    if args.report:
        report()
        return 0
    n = build()
    print(f"[correlated] seeded {n} plan+spec prior rows (source=correlated:*)", file=sys.stderr)
    report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
