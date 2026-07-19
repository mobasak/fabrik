"""Phase B Behavior Contract — one test per behavior, generation MOCKED (no spend, no .lcb-venv).

Covers: errored-not-zero + is_measured gate; --cost-cap dispatch gate; pass@1->grade mapping;
cost_per_1k / tokens_per_s; extract_code fence-stripping; the resolved-model-count log + shortfall warn.
Grade-path correctness (real sandbox) lives in test_lcb_smoke.py (skipped without .lcb-venv).
"""

import sqlite3
import sys
import types
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import microbench_coding_direct as m  # noqa: E402


# ── pass@1 -> grade maps on the review scale (score5 = pass@1 * 5) ────────────────────────────
@pytest.mark.parametrize(
    "pass_at_1,expected",
    [(1.0, "A+"), (0.90, "A+"), (0.85, "A"), (0.70, "B+"), (0.60, "B"), (0.50, "C+"), (0.40, "C"), (0.20, "D"), (0.0, "F")],
)
def test_pass_at_1_maps_to_review_letter(pass_at_1, expected):
    s = m.CodingScore("x", pass_at_1, n_problems=10, n_graded=10, n_err=0, cost_usd=0.0)
    assert s.grade == expected
    assert s.score5 == round(pass_at_1 * 5, 3)


# ── errored/empty gens are n_err, never scored 0; is_measured gated at MIN_MEASURED graded ────
def test_errored_gens_counted_and_gate_measured():
    s = m.CodingScore("x", pass_at_1=0.5, n_problems=5, n_graded=2, n_err=3, cost_usd=0.1)
    assert not s.is_measured  # only 2 graded (< MIN_MEASURED=3)
    ok = m.CodingScore("y", pass_at_1=0.5, n_problems=5, n_graded=3, n_err=2, cost_usd=0.1)
    assert ok.is_measured
    unreached = m.CodingScore("z", pass_at_1=None, n_problems=5, n_graded=0, n_err=5, cost_usd=0.0)
    assert not unreached.is_measured  # pass_at_1 None -> never measured (not scored 0)


def test_cost_per_1k_and_tokens_per_s():
    s = m.CodingScore("x", 0.5, n_problems=4, n_graded=4, n_err=0, cost_usd=0.2,
                      latencies=[1.0, 1.0], out_tokens=100)
    assert s.cost_per_1k == round(0.2 / 4 * 1000, 4)  # $ per 1000 problems
    assert s.tokens_per_s == 50.0  # 100 tokens / 2.0s


# ── extract_code strips a fenced block; falls back to raw text ────────────────────────────────
def test_extract_code_prefers_python_fence():
    assert m.extract_code("blah\n```python\nprint(1)\n```\nend") == "print(1)"
    assert m.extract_code("```\nx=2\n```") == "x=2"
    assert m.extract_code("no fence just code") == "no fence just code"
    assert m.extract_code("") == ""


# ── --cost-cap is a running-total DISPATCH GATE — cap-stopped slots become n_err, not pass=0 ──
def test_cost_cap_stops_dispatch_and_marks_n_err(monkeypatch):
    def fake_run(model, messages, *, body=None, max_cost_usd=None):
        return types.SimpleNamespace(
            error=None, text="```python\nprint(1)\n```", cost_usd=1.0,
            usage={"completion_tokens": 5},
        )

    monkeypatch.setattr(m, "_or_run", fake_run)
    corpus = [m.Problem(f"q{i}", "p", "", {"input_output": "{}"}) for i in range(20)]
    gens = m.generate(["mdl"], corpus, cost_cap=1.5, max_concurrency=2)
    non_none = sum(1 for g in gens["mdl"] if g.code is not None)
    assert non_none < 20  # the cap stopped new dispatches before all 20 ran
    n_err = sum(1 for g in gens["mdl"] if g.code is None)
    assert n_err > 0  # cap-stopped slots are errors, NOT graded as pass=0


def test_generate_bounds_output_and_per_call_cost(monkeypatch):
    """F1+F3: the request body carries max_tokens (bounds output/cost); the per-call cap is the fixed
    ceiling _PER_CALL_COST_CAP, NOT the whole batch budget (one call can't drain the run)."""
    seen = {}

    def fake_run(model, messages, *, body=None, max_cost_usd=None):
        seen["body"] = body
        seen["cap"] = max_cost_usd
        return types.SimpleNamespace(error=None, text="```python\nx=1\n```", cost_usd=0.01,
                                     usage={"completion_tokens": 3})

    monkeypatch.setattr(m, "_or_run", fake_run)
    m.generate(["mdl"], [m.Problem("q", "p", "", {"input_output": "{}"})],
               cost_cap=20.0, max_tokens=1234, max_concurrency=1)
    assert seen["body"]["max_tokens"] == 1234  # F1: output length bounded
    assert seen["cap"] == m._PER_CALL_COST_CAP and m._PER_CALL_COST_CAP < 20.0  # F3: per-call ceiling


def test_unknown_cost_still_counts_toward_cap(monkeypatch):
    """F2: a provider returning NO billed cost must not blind the running cap — a conservative token
    estimate keeps the gate engaged so the account can't drain silently."""
    def fake_run(model, messages, *, body=None, max_cost_usd=None):
        return types.SimpleNamespace(error=None, text="```python\nx=1\n```", cost_usd=None,
                                     usage={"completion_tokens": 1_000_000})  # 1M tok, cost UNKNOWN

    monkeypatch.setattr(m, "_or_run", fake_run)
    corpus = [m.Problem(f"q{i}", "p", "", {"input_output": "{}"}) for i in range(10)]
    gens = m.generate(["mdl"], corpus, cost_cap=1.0, max_concurrency=1)
    # estimate per call = 1e6 * _FALLBACK_COST_PER_MTOK / 1e6 = $5 > $1 cap -> gate engages, rest cancel
    assert sum(1 for g in gens["mdl"] if g.code is not None) < 10


def test_generation_error_is_slot_error_not_fatal(monkeypatch):
    def boom(model, messages, *, body=None, max_cost_usd=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(m, "_or_run", boom)
    corpus = [m.Problem("q1", "p", "", {"input_output": "{}"})]
    gens = m.generate(["mdl"], corpus, cost_cap=10.0, max_concurrency=1)
    assert gens["mdl"][0].code is None and gens["mdl"][0].error  # errored, not a crash


# ── default model set = the models the review table measured; shortfall is visible ────────────
def test_resolve_models_defaults_to_review_set(tmp_path):
    db = tmp_path / "k.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE model_review_metrics (model_id TEXT, built_at TEXT)")
    conn.executemany("INSERT INTO model_review_metrics VALUES (?,?)",
                     [("a", "2026-07-19"), ("b", "2026-07-19"), ("a", "2026-07-18")])
    conn.commit()
    conn.close()
    assert m._resolve_models(None, db_path=db) == ["a", "b"]  # DISTINCT, sorted
    assert m._resolve_models(["z"], db_path=db) == ["z"]  # explicit override
    assert m._resolve_models(None, db_path=tmp_path / "absent.db") == []  # fail-soft
