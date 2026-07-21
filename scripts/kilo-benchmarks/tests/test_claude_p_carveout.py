"""Behavior Contract — Phase C: gate carve-out + ②/③ doc-emit preamble + parser safety. Fixtures only."""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_task_baselines as b  # noqa: E402
import rank_task_subagents as r  # noqa: E402


def _seed_review(
    db, model, *, cost_per_1k, cost_usd=0.001, p50=2.0, score5=5.0, recall=0.9, precision=1.0
):
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS model_review_metrics (model_id TEXT, grade TEXT, score5 REAL, recall REAL,"
        " precision REAL, cost_per_1k REAL, p50_latency_s REAL, cost_usd REAL, built_at TEXT)"
    )
    conn.execute(
        "INSERT INTO model_review_metrics VALUES (?,?,?,?,?,?,?,?,?)",
        (model, "A", score5, recall, precision, cost_per_1k, p50, cost_usd, "2026-07-20"),
    )
    conn.commit()
    conn.close()


def _seed_code(db, model, *, cost_per_1k, p50=2.0, pass_at_1=0.95, n_err=0, score5=4.75):
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS model_coding_metrics (model_id TEXT, grade TEXT, pass_at_1 REAL, score5 REAL,"
        " cost_per_1k REAL, p50_latency_s REAL, n_err INTEGER, built_at TEXT)"
    )
    conn.execute(
        "INSERT INTO model_coding_metrics VALUES (?,?,?,?,?,?,?,?)",
        (model, "A", pass_at_1, score5, cost_per_1k, p50, n_err, "2026-07-20"),
    )
    conn.commit()
    conn.close()


def test_review_carveout_keeps_claude_past_gate(tmp_path):
    db = tmp_path / "kilo_agents.db"
    _seed_review(
        db, "claude-code/opus", cost_per_1k=5.0, cost_usd=0.5, p50=30.0
    )  # expensive+slow → would fail
    _seed_review(
        db, "expensive/x", cost_per_1k=5.0, cost_usd=0.5, p50=30.0
    )  # non-claude, equally bad
    _seed_review(db, "good/y", cost_per_1k=0.1)  # clean pass
    elig = b.review_eligible(db)
    assert "claude-code/opus" in elig  # carve-out keeps it despite failing $/1k + $/run + p50
    assert "expensive/x" not in elig  # the gate STILL bites a non-claude
    assert "good/y" in elig


def test_code_carveout_keeps_claude_past_gate(tmp_path):
    db = tmp_path / "kilo_agents.db"
    _seed_code(
        db, "claude-code/opus", cost_per_1k=10.0, p50=30.0
    )  # > CODE_MAX_COST_PER_1K (3.5) + slow
    _seed_code(db, "expensive/x", cost_per_1k=10.0, p50=30.0)  # non-claude, equally bad
    _seed_code(db, "good/y", cost_per_1k=0.5)  # clean pass
    elig = b.code_eligible(db)
    assert "claude-code/opus" in elig  # carve-out
    assert "expensive/x" not in elig  # gate still bites
    assert "good/y" in elig


def test_review_carveout_still_excludes_low_quality_claude(tmp_path):
    db = tmp_path / "kilo_agents.db"
    # a do-nothing claude reviewer (recall 0) is NEVER eligible — the carve-out bypasses cost/latency only.
    _seed_review(db, "claude-code/haiku", cost_per_1k=0.1, recall=0.0)
    _seed_review(db, "good/y", cost_per_1k=0.1)
    elig = b.review_eligible(db)
    assert "claude-code/haiku" not in elig  # quality floor (recall > 0) still bites a claude tier
    assert "good/y" in elig


def test_code_carveout_still_excludes_low_quality_claude(tmp_path):
    db = tmp_path / "kilo_agents.db"
    _seed_code(db, "claude-code/haiku", cost_per_1k=0.5, pass_at_1=0.5)  # < 0.90 quality floor
    elig = b.code_eligible(db)
    assert "claude-code/haiku" not in elig  # pass@1 ≥ 0.90 still bites a claude tier


def test_claude_code_excluded_from_pool_routing(tmp_path, monkeypatch):
    from libs.subagents.select import load_task_ranking

    # the review benchmark set contains a claude tier + an OR model; only the OR model may be pool-routable
    # (claude-code/* = spawn-native, the pool would 404 dispatching it).
    monkeypatch.setattr(r, "_review_benchmark_models", lambda *a, **k: ["claude-code/opus", "openrouter/x"])
    monkeypatch.setattr(r, "_review_bench_ran", lambda *a, **k: True)
    monkeypatch.setattr(r, "_code_bench_ran", lambda *a, **k: False)
    monkeypatch.setattr(r, "_code_benchmark_models", lambda *a, **k: [])
    monkeypatch.setattr(r, "_judged_bench_ran", lambda *a, **k: False)
    monkeypatch.setattr(r, "_judged_benchmark_models", lambda *a, **k: [])
    monkeypatch.setattr(r, "_load_coding_fallback", lambda *a, **k: [])
    md = r.render([], include_full_results=False)
    doc = tmp_path / "sel.md"
    doc.write_text(md)
    out = load_task_ranking(str(doc))
    assert "openrouter/x" in out.get("review", [])  # OR model IS pool-routable
    assert "claude-code/opus" not in out.get("review", [])  # claude excluded from pool routing


def test_claude_only_benchmark_not_suppressed_by_stub_guard(monkeypatch):
    # a review benchmark RAN but its only eligible tiers are claude-code/* → review_benchmark is [] after
    # FIX-2's routing filter; the doc must NOT return the "No aggregated runs yet" stub (which would hide
    # the ✅ Selected shortlist that displays those claude reviewers).
    monkeypatch.setattr(r, "_review_benchmark_models", lambda *a, **k: [])  # claude-only → routing-filtered empty
    monkeypatch.setattr(r, "_review_bench_ran", lambda *a, **k: True)  # but the benchmark DID run
    monkeypatch.setattr(r, "_code_bench_ran", lambda *a, **k: False)
    monkeypatch.setattr(r, "_code_benchmark_models", lambda *a, **k: [])
    monkeypatch.setattr(r, "_judged_bench_ran", lambda *a, **k: False)
    monkeypatch.setattr(r, "_judged_benchmark_models", lambda *a, **k: [])
    monkeypatch.setattr(r, "_load_coding_fallback", lambda *a, **k: [])
    md = r.render([], include_full_results=False)
    assert "No aggregated runs yet" not in md  # not stubbed — a benchmark ran (display would show claude)


def test_preamble_renders_from_sidecar(tmp_path, monkeypatch):
    (tmp_path / "claude_p_cost.json").write_text(
        json.dumps({"amortized_per_mtok": 0.093, "quota_draw_pct": 12.5, "built_at": "x"})
    )
    monkeypatch.setattr(
        r, "__file__", str(tmp_path / "rank_task_subagents.py")
    )  # Path(__file__).parent = tmp_path
    lines = r._claude_p_preamble()
    assert lines and "API-equivalent" in lines[0]
    assert "0.093" in lines[0] and "12.5" in lines[0]  # ② + ③ surfaced


def test_preamble_omits_when_sidecar_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(
        r, "__file__", str(tmp_path / "rank_task_subagents.py")
    )  # tmp_path has no sidecar
    assert r._claude_p_preamble() == []  # omitted, no raise


def test_preamble_omits_on_malformed_sidecar(tmp_path, monkeypatch):
    (tmp_path / "claude_p_cost.json").write_text("[]")  # non-object → fail-soft to omission
    monkeypatch.setattr(r, "__file__", str(tmp_path / "rank_task_subagents.py"))
    assert r._claude_p_preamble() == []


def test_claude_code_full_table_row_is_parser_safe(tmp_path):
    from libs.subagents.select import load_task_ranking

    doc = tmp_path / "sel.md"
    doc.write_text(
        "## Full review benchmark results\n"
        "_`claude-code/*` rows: `$/1k` = ① API-equivalent._\n"
        "| model | grade | eligible |\n|---|:-:|:-:|\n"
        "| `claude-code/opus` | A | ✅ |\n"  # model_id-led → NOT a routing entry
        "\n### review\n\n| rank | model | n |\n|--|--|--|\n| 1 | `openrouter/x` | 5 |\n"
    )
    out = load_task_ranking(str(doc))
    assert isinstance(out, dict)  # no crash on the preamble line or the model_id-led full-table row
    assert "claude-code/opus" not in out.get(
        "review", []
    )  # the full-table row is not parsed as routing
