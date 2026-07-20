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

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_task_baselines as btb  # noqa: E402
import rank_task_subagents as rts  # noqa: E402


def _db_with_metrics(tmp_path, rows):
    """rows: list of (model, precision, cost_per_1k, p50, score5, grade[, cost_usd]).

    cost_usd (the per-review $ gated by REVIEW_MAX_RUN_COST) defaults to 0.005 — under the 0.007
    ceiling — so a row passes the run-cost constraint unless it explicitly sets a higher value.
    """
    db = tmp_path / "k.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE model_review_metrics (
        model_id TEXT, score5 REAL, grade TEXT, recall REAL, precision REAL, out_price_mtok REAL,
        cost_usd REAL, cost_per_1k REAL, p50_latency_s REAL, tokens_per_s REAL,
        n_mut INT, n_ctrl INT, built_at TEXT, PRIMARY KEY (model_id, built_at))""")
    for r in rows:
        m, prec, c1k, p50, s5, g = r[:6]
        cusd = r[6] if len(r) > 6 else 0.005
        conn.execute(
            "INSERT INTO model_review_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (m, s5, g, 0.6, prec, 1.0, cusd, c1k, p50, 50.0, 22, 8, "2026-07-18"),
        )
    conn.commit()
    conn.close()
    return db


def test_gate_passes_only_when_all_five_constraints_met(tmp_path):
    db = _db_with_metrics(
        tmp_path,
        [
            ("good/model", 1.00, 0.50, 5.0, 4.0, "A"),  # passes all 5
            ("noisy/model", 0.88, 0.50, 5.0, 4.0, "B"),  # fails precision
            ("pricey/model", 1.00, 0.90, 5.0, 4.0, "B"),  # fails $/1k
            ("slow/model", 1.00, 0.50, 19.0, 4.0, "B"),  # fails p50
            ("weak/model", 1.00, 0.50, 5.0, 3.0, "C"),  # fails score5 floor (3.0 < 3.5)
            ("costly-run/model", 1.00, 0.50, 5.0, 4.0, "A", 0.01),  # fails $/run (0.01 ≥ 0.007)
            ("edge/model", 0.99, 0.70, 10.0, 3.5, "B+", 0.0069),  # exactly on every bound -> passes
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
        "INSERT INTO model_review_metrics VALUES ('a/one',4.1,'A',0.7,1.0,3.0,0.005,0.28,1.8,50,22,8,'2999-01-01')"
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
        "INSERT INTO model_review_metrics VALUES ('real/reviewer',4.0,'A',0.7,1.0,1.0,0.005,0.3,2.0,50,22,8,'2026-07-18')"
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
    assert btb.REVIEW_MAX_RUN_COST == 0.007
    assert btb.REVIEW_TRUST_FLOOR_SCORE5 == 3.5


def test_render_review_section_drops_ineligible(monkeypatch):
    # benchmark ran, gate allows only qwen3-max; kimi must be dropped from the review section
    monkeypatch.setattr(rts, "_review_benchmark_models", lambda: ["qwen/qwen3-max"])
    monkeypatch.setattr(rts, "_review_bench_ran", lambda: True)
    rows = [
        ("review", "qwen/qwen3-max", 6, 0.001, 4.0, 1.0),  # eligible fleet row
        ("review", "moonshotai/kimi-k2.5", 6, 0.006, 4.0, 1.0),  # ineligible -> dropped
    ]
    md = rts.render(rows, state="ok", include_full_results=False)
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
    md = rts.render(rows, state="ok", include_full_results=False)
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


# ── Coding-eligibility gate (parallel to the review gate) ───────────────────────────────────────
def _coding_db(tmp_path, rows):
    """rows: (model, pass_at_1, cost_per_1k, p50, n_err[, grade]). Builds a temp model_coding_metrics."""
    db = tmp_path / "c.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE model_coding_metrics (model_id TEXT, pass_at_1 REAL, score5 REAL,
        grade TEXT, cost_usd REAL, cost_per_1k REAL, p50_latency_s REAL, tokens_per_s REAL,
        n_problems INT, n_graded INT, n_err INT, window TEXT, built_at TEXT,
        PRIMARY KEY(model_id, built_at))""")
    for r in rows:
        m, p1, c1k, p50, nerr = r[:5]
        g = r[5] if len(r) > 5 else ("A+" if p1 >= 0.9 else "A")
        conn.execute(
            "INSERT INTO model_coding_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (m, p1, p1 * 5, g, 0.05, c1k, p50, 50.0, 50, 50 - nerr, nerr, "release_v5", "2026-07-19"),
        )
    conn.commit()
    conn.close()
    return db


def test_code_gate_passes_only_when_all_four_met(tmp_path):
    db = _coding_db(
        tmp_path,
        [
            ("good/model", 0.95, 1.0, 5.0, 0),  # passes all 4
            ("flaky/model", 0.95, 1.0, 5.0, 5),  # fails n_err (5 > 1)
            ("weak/model", 0.88, 1.0, 5.0, 0),  # fails pass@1 (0.88 < 0.90)
            ("pricey/model", 0.95, 5.0, 5.0, 0),  # fails $/1k (5.0 > 3.5)
            ("slow/model", 0.95, 1.0, 15.0, 0),  # fails p50 (15 > 10)
            ("edge/model", 0.90, 3.5, 10.0, 1),  # exactly on every bound -> passes
        ],
    )
    assert btb.code_eligible(db) == {"good/model", "edge/model"}


def test_code_gate_empty_when_benchmark_absent(tmp_path):
    db = tmp_path / "empty.db"
    sqlite3.connect(db).close()  # no model_coding_metrics table
    assert btb.code_eligible(db) == set()  # fail-soft: gate inactive


def test_code_constants_and_tiers():
    assert btb.CODE_MAX_ERRORS == 1
    assert btb.CODE_MIN_PASS_AT_1 == 0.90
    assert btb.CODE_MAX_COST_PER_1K == 3.5
    assert btb.CODE_MAX_P50_S == 10.0
    assert set(btb.CODE_TIERS) == {"daily-driver", "premium"}
    all_tiered = [m for models in btb.CODE_TIERS.values() for m in models]
    assert len(all_tiered) == len(set(all_tiered)), "a model appears in two tiers"


def test_code_tier_lookup():
    assert btb.code_tier("google/gemini-3-flash-preview") == "daily-driver"
    assert btb.code_tier("openai/gpt-5.6-luna") == "premium"
    assert btb.code_tier("nonexistent/model") is None


def test_render_code_section_gated_by_code_eligible(monkeypatch):
    """The CODE gate (parallel to the review gate): when the coding benchmark ran, only
    code_eligible() ids survive the `### code` section. Without this, pick_models('code') would leak
    ineligible models. Re-enables the gate that test_rank_task_subagents' autouse fixture pins off."""
    monkeypatch.setattr(rts, "_code_bench_ran", lambda *_a, **_k: True)
    monkeypatch.setattr(rts, "_code_benchmark_models", lambda *_a, **_k: ["good/coder"])
    monkeypatch.setattr(rts, "_review_benchmark_models", lambda *_a, **_k: [])
    monkeypatch.setattr(rts, "_review_bench_ran", lambda *_a, **_k: False)
    rows = [
        ("code", "good/coder", 6, 0.001, 4.0, 1.0),  # in the gate -> kept
        ("code", "bad/ineligible", 6, 0.001, 4.0, 1.0),  # NOT in the gate -> dropped
    ]
    md = rts.render(rows, state="ok", include_full_results=False)
    code = md.split("### code")[1] if "### code" in md else ""
    assert "good/coder" in code
    assert "bad/ineligible" not in code, "ineligible coder leaked into ### code (gate not applied)"


def test_render_code_gate_inactive_when_benchmark_absent(monkeypatch):
    """Benchmark never ran => code gate inactive (fall back to the CODING auto-tier fallback), so an
    otherwise-ineligible fleet code row survives — mirrors the review gate's inactive path."""
    monkeypatch.setattr(rts, "_code_bench_ran", lambda *_a, **_k: False)
    monkeypatch.setattr(rts, "_code_benchmark_models", lambda *_a, **_k: [])
    monkeypatch.setattr(rts, "_load_coding_fallback", lambda *_a, **_k: [])
    monkeypatch.setattr(rts, "_review_benchmark_models", lambda *_a, **_k: [])
    monkeypatch.setattr(rts, "_review_bench_ran", lambda *_a, **_k: False)
    rows = [("code", "some/coder", 6, 0.001, 4.0, 1.0)]
    md = rts.render(rows, state="ok", include_full_results=False)
    assert "some/coder" in md, "gate wrongly active with no benchmark data"


def test_render_code_fallback_uses_eligible_set_when_gate_active(monkeypatch):
    """With the benchmark run and NO fleet code rows, the `### code` fallback is built from
    code_benchmark (the eligible set), NOT the old _load_coding_fallback — so a benchmark-only
    eligible coder still reaches pick_models('code'). Covers the `coding_fallback_models` override."""
    monkeypatch.setattr(rts, "_code_bench_ran", lambda *_a, **_k: True)
    monkeypatch.setattr(rts, "_code_benchmark_models", lambda *_a, **_k: ["bench/eligible"])
    monkeypatch.setattr(rts, "_load_coding_fallback", lambda *_a, **_k: ["old/fallback"])  # must NOT win
    monkeypatch.setattr(rts, "_review_benchmark_models", lambda *_a, **_k: [])
    monkeypatch.setattr(rts, "_review_bench_ran", lambda *_a, **_k: False)
    rows = [("review", "x/y", 6, 0.001, 4.0, 1.0)]  # a non-code row so render doesn't emit the empty stub
    md = rts.render(rows, state="ok", include_full_results=False)
    assert "bench/eligible" in md, "benchmark-only eligible coder did not surface via the fallback"
    assert "old/fallback" not in md, "old _load_coding_fallback used instead of code_benchmark when gate active"


# ── Phase E: the judged gates (research/docs/plan/spec) drop ineligible rows from their section ──
@pytest.mark.parametrize("jt", ["research", "docs", "plan", "spec"])
def test_render_judged_section_drops_ineligible(monkeypatch, jt):
    """Per new task type: once the judged benchmark RAN, the `### <task>` router section keeps only the
    gate-eligible models — an ineligible fleet row is dropped (mirrors the review/code gate render tests)."""
    monkeypatch.setattr(rts, "_judged_bench_ran", lambda t: t == jt)
    monkeypatch.setattr(rts, "_judged_benchmark_models", lambda t: ["good/model"] if t == jt else [])
    rows = [
        (jt, "good/model", 6, 0.001, 4.0, 1.0),  # eligible fleet row
        (jt, "bad/model", 6, 0.001, 4.0, 1.0),  # ineligible -> dropped
    ]
    md = rts.render(rows, state="ok", include_full_results=False)
    section = md.split(f"### {jt}")[1] if f"### {jt}" in md else ""
    assert "good/model" in section
    assert "bad/model" not in section, f"ineligible model leaked into the {jt} section"


def test_render_judged_gate_inactive_when_no_benchmark(monkeypatch):
    """Benchmark never ran → the judged gate does NOT filter (prior behaviour), so the row survives."""
    monkeypatch.setattr(rts, "_judged_bench_ran", lambda t: False)
    monkeypatch.setattr(rts, "_judged_benchmark_models", lambda t: [])
    rows = [("research", "bad/model", 6, 0.001, 4.0, 1.0)]
    md = rts.render(rows, state="ok", include_full_results=False)
    assert "bad/model" in md


def test_judged_eligible_gate_maths(tmp_path):
    """build_task_baselines.judged_eligible: research/docs gate on score5+cost+latency; plan/spec on
    score5 only; a missing metric fails closed; empty when the benchmark hasn't run."""
    db = tmp_path / "k.db"
    assert btb.judged_eligible("research", db) == set()  # no table yet → inactive
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE model_judged_metrics (model_id TEXT, task_type TEXT, score5 REAL, grade TEXT, "
        "recall REAL, precision REAL, structural TEXT, cost_usd REAL, cost_per_1k REAL, "
        "p50_latency_s REAL, tokens_per_s REAL, n_graded INTEGER, n_err INTEGER, window TEXT, built_at TEXT)"
    )
    rows = [
        ("good/research", "research", 4.0, 2.0, 5.0),  # passes all
        ("pricey/research", "research", 4.0, 9.0, 5.0),  # $/1k too high → out
        ("slow/research", "research", 4.0, 2.0, 30.0),  # p50 too high → out
        ("weak/research", "research", 3.0, 2.0, 5.0),  # score5 below floor → out
        ("good/plan", "plan", 4.0, None, None),  # plan: quality-only → in (no cost/latency)
        ("weak/plan", "plan", 3.0, None, None),  # below floor → out
    ]
    for mid, tt, s5, c1k, p50 in rows:
        conn.execute(
            "INSERT INTO model_judged_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (mid, tt, s5, "A", None, None, "5/5", None, c1k, p50, None, 3, 0, "v1", "2026-07-20"),
        )
    conn.commit()
    conn.close()
    assert btb.judged_eligible("research", db) == {"good/research"}
    assert btb.judged_eligible("plan", db) == {"good/plan"}  # structural: cost/latency ignored


def test_load_judged_metrics_deterministic_on_two_windows_same_day(tmp_path):
    """Whole-plan review #2: model_judged_metrics has `window` in its PK, so two windows the same day
    leave two rows per model that both satisfy MAX(built_at). The loader must be DETERMINISTIC (higher
    window wins via ORDER BY built_at, window), not flip-flop — unlike the review/coding tables which
    have no window in their PK."""
    db = tmp_path / "k.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE model_judged_metrics (model_id TEXT, task_type TEXT, score5 REAL, grade TEXT, "
        "recall REAL, precision REAL, structural TEXT, cost_usd REAL, cost_per_1k REAL, "
        "p50_latency_s REAL, tokens_per_s REAL, n_graded INTEGER, n_err INTEGER, window TEXT, built_at TEXT)"
    )
    for win, s5 in (("v1", 3.6), ("v2", 3.4)):  # same model, same day, two windows
        conn.execute(
            "INSERT INTO model_judged_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("m/x", "research", s5, "B+", None, None, None, None, 1.0, 2.0, None, 3, 0, win, "2026-07-20"),
        )
    conn.commit()
    conn.close()
    got = btb.load_judged_metrics("research", db)
    assert set(got) == {"m/x"} and got["m/x"]["score5"] == 3.4  # v2 (higher window) wins, deterministic
