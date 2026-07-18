"""Tests for the PERMANENT review-eligibility gate and its wiring into both selection docs.

The gate (build_task_baselines.review_eligible) is the single source of truth for the operator's
constraints — precision >= 99% AND real $/1k <= 0.70 AND p50 <= 10s. These tests pin:
  1. the gate maths (each constraint excludes the right model),
  2. rank_task_subagents.render() drops ineligible models from the `review` section, and
  3. rank_coding_subagents prefers the MEASURED review grade over the heuristic.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_task_baselines as btb  # noqa: E402
import rank_task_subagents as rts  # noqa: E402


def _db_with_metrics(tmp_path, rows):
    """rows: list of (model, precision, cost_per_1k, p50, score5, grade)."""
    db = tmp_path / "k.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE model_review_metrics (
        model_id TEXT, score5 REAL, grade TEXT, recall REAL, precision REAL, out_price_mtok REAL,
        cost_usd REAL, cost_per_1k REAL, p50_latency_s REAL, tokens_per_s REAL,
        n_mut INT, n_ctrl INT, built_at TEXT, PRIMARY KEY (model_id, built_at))""")
    for m, prec, c1k, p50, s5, g in rows:
        conn.execute(
            "INSERT INTO model_review_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (m, s5, g, 0.6, prec, 1.0, 0.01, c1k, p50, 50.0, 22, 8, "2026-07-18"),
        )
    conn.commit()
    conn.close()
    return db


def test_gate_passes_only_when_all_three_constraints_met(tmp_path):
    db = _db_with_metrics(
        tmp_path,
        [
            ("good/model", 1.00, 0.50, 5.0, 4.0, "A"),  # passes all
            ("noisy/model", 0.88, 0.50, 5.0, 4.0, "B"),  # fails precision
            ("pricey/model", 1.00, 0.90, 5.0, 4.0, "B"),  # fails $/1k
            ("slow/model", 1.00, 0.50, 19.0, 4.0, "B"),  # fails p50
            ("edge/model", 0.99, 0.70, 10.0, 3.0, "C"),  # exactly on every bound -> passes
        ],
    )
    elig = btb.review_eligible(db)
    assert elig == {"good/model", "edge/model"}


def test_partial_rerun_on_new_date_keeps_other_models(tmp_path):
    """A `--models X` re-run on a LATER date must update only X and keep every other model's
    most-recent metrics — the eligible set must NOT collapse to just the re-run models."""
    db = _db_with_metrics(
        tmp_path,
        [
            ("a/one", 1.00, 0.30, 2.0, 4.0, "A"),
            ("b/two", 1.00, 0.30, 2.0, 4.0, "A"),
        ],
    )
    conn = sqlite3.connect(db)  # partial re-run of only a/one on a NEWER date
    conn.execute(
        "INSERT INTO model_review_metrics VALUES ('a/one',4.1,'A',0.7,1.0,3.0,0.01,0.28,1.8,50,22,8,'2999-01-01')"
    )
    conn.commit()
    conn.close()
    assert btb.review_eligible(db) == {"a/one", "b/two"}, "b/two dropped by a partial re-run"
    assert btb.load_review_metrics(db)["a/one"]["cost_per_1k"] == 0.28, "a/one must use newest row"


def test_gate_excludes_zero_recall_do_nothing_model(tmp_path):
    """B#2: a model that always answers `[]` scores recall=0 AND precision=1.0 (never flags a
    control) — it must NOT clear the gate despite passing precision/cost/p50 (it catches nothing)."""
    db = tmp_path / "r.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE model_review_metrics (model_id TEXT, score5 REAL, grade TEXT,
        recall REAL, precision REAL, out_price_mtok REAL, cost_usd REAL, cost_per_1k REAL,
        p50_latency_s REAL, tokens_per_s REAL, n_mut INT, n_ctrl INT, built_at TEXT,
        PRIMARY KEY(model_id,built_at))""")
    # recall 0.0, precision 1.0, cheap, fast — passes every OTHER constraint
    conn.execute(
        "INSERT INTO model_review_metrics VALUES ('do/nothing',0.0,'F',0.0,1.0,1.0,0.0,0.1,1.0,50,0,8,'2026-07-18')"
    )
    conn.execute(
        "INSERT INTO model_review_metrics VALUES ('real/reviewer',4.0,'A',0.7,1.0,1.0,0.01,0.3,2.0,50,22,8,'2026-07-18')"
    )
    conn.commit()
    conn.close()
    assert btb.review_eligible(db) == {"real/reviewer"}, (
        "recall=0 do-nothing model cleared the gate"
    )


def test_gate_empty_when_benchmark_absent(tmp_path):
    db = tmp_path / "empty.db"
    sqlite3.connect(db).close()  # no model_review_metrics table
    assert btb.review_eligible(db) == set()  # fail-soft: gate inactive, not "nothing eligible"


def test_constants_are_the_operator_values():
    assert btb.REVIEW_MIN_PRECISION == 0.99
    assert btb.REVIEW_MAX_COST_PER_1K == 0.70
    assert btb.REVIEW_MAX_P50_S == 10.0


def test_render_review_section_drops_ineligible(monkeypatch):
    # benchmark ran, gate allows only qwen3-max; kimi must be dropped from the review section
    monkeypatch.setattr(rts, "_review_benchmark_models", lambda: ["qwen/qwen3-max"])
    monkeypatch.setattr(rts, "_review_bench_ran", lambda: True)
    rows = [
        ("review", "qwen/qwen3-max", 6, 0.001, 4.0, 1.0),  # eligible fleet row
        ("review", "moonshotai/kimi-k2.5", 6, 0.006, 4.0, 1.0),  # ineligible -> dropped
    ]
    md = rts.render(rows, state="ok")
    review = md.split("### review")[1] if "### review" in md else ""
    assert "qwen/qwen3-max" in review
    assert "moonshotai/kimi-k2.5" not in review, "ineligible model leaked into review section"


def test_render_review_gate_inactive_when_no_benchmark(monkeypatch):
    # benchmark never ran => do NOT filter (fall back to prior behaviour), so kimi survives
    monkeypatch.setattr(rts, "_review_benchmark_models", lambda: [])
    monkeypatch.setattr(rts, "_review_bench_ran", lambda: False)
    rows = [("review", "moonshotai/kimi-k2.5", 6, 0.006, 4.0, 1.0)]
    md = rts.render(rows, state="ok")
    assert "moonshotai/kimi-k2.5" in md


def test_render_review_gate_fail_closed_when_ran_but_none_eligible(monkeypatch):
    """B#2: benchmark RAN but nobody cleared the gate → gate is ACTIVE (fail-closed): ineligible
    fleet review rows are dropped, NOT passed through."""
    monkeypatch.setattr(rts, "_review_benchmark_models", lambda: [])  # zero eligible
    monkeypatch.setattr(rts, "_review_bench_ran", lambda: True)  # but the benchmark DID run
    rows = [("review", "moonshotai/kimi-k2.5", 6, 0.006, 4.0, 1.0)]
    md = rts.render(rows, state="ok")
    assert "moonshotai/kimi-k2.5" not in md, "fail-open: ineligible model survived an active gate"


def test_render_review_fallback_section_when_all_fleet_gated_out(monkeypatch):
    """B#7: no fleet review row survives the gate, but review_benchmark is non-empty → the dedicated
    `### review (n_eligible_fleet=0, gated benchmark ...)` fallback section is emitted."""
    monkeypatch.setattr(rts, "_review_benchmark_models", lambda: ["qwen/qwen3-max"])
    monkeypatch.setattr(rts, "_review_bench_ran", lambda: True)
    monkeypatch.setattr(rts, "_load_coding_fallback", lambda *_a, **_k: [])
    # a review fleet row for an INELIGIBLE model → gated out → no fleet review section
    rows = [("review", "some/ineligible", 6, 0.006, 4.0, 1.0)]
    md = rts.render(rows, state="ok")
    assert "gated benchmark from model_review_metrics" in md
    assert "qwen/qwen3-max" in md


def test_coding_doc_prefers_measured_review_grade(tmp_path, monkeypatch):
    """Exercise the ACTUAL override in _rows_from_db: a model whose MEASURED review grade is F must
    show F (not the heuristic 'A') in the coding Doc↔Code column, marked as measured."""
    import rank_coding_subagents as rcs

    db = _db_with_metrics(tmp_path, [("z-ai/glm-review-victim", 1.0, 0.5, 5.0, 0.0, "F")])
    # give _rows_from_db one in-scope (z-ai/glm-) agent row to rank
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE agents (
        id TEXT, input_cost_per_m REAL, output_cost_per_m REAL, output_tokens_per_sec REAL,
        swe_bench_verified_pct REAL, aider_polyglot_pct REAL, coding_score REAL, humaneval_score REAL,
        aa_intelligence_index REAL, arena_elo REAL, context_window_k REAL, quality_tier INT,
        has_reasoning INT, via_openrouter INT, cheapest_provider TEXT, status TEXT,
        service_type TEXT, reachable_with_existing_keys INT)""")
    conn.execute(
        "INSERT INTO agents VALUES ('z-ai/glm-review-victim',0.1,0.4,50,80,80,90,90,50,1400,200,3,1,1,'x','active','llm',1)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(rcs, "_grade_doc_review", lambda *a, **k: "A")  # heuristic says A
    rows = rcs._rows_from_db(db_path=db)
    victim = next(r for r in rows if r["id"] == "z-ai/glm-review-victim")
    assert victim["doc_grade"] == "F", "measured F must override the heuristic A"
    assert victim["doc_grade_measured"] is True
