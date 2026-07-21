"""Behavior Contract — Phase B namespace-branch dispatch (review + code). Mocked shim, no real Claude call."""

import datetime
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import derive_cost  # noqa: E402

_USAGE = {
    "input_tokens": 10,
    "output_tokens": 20,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0,
}


# ---------------- review branch (_claude_p_direct) ----------------


def test_review_branch_builds_directresult(monkeypatch):
    import microbench_review as mr

    monkeypatch.setattr(
        "claude_p.claude_p_call", lambda model, prompt, *, system, timeout: ("[]", _USAGE)
    )
    res = mr._claude_p_direct("claude-code/opus", "METHOD + code", timeout=10)
    assert res.model == "claude-code/opus"
    assert res.text == "[]"
    assert res.out_tokens == 20
    assert res.cost_usd == pytest.approx(derive_cost.api_equiv(_USAGE, "claude-code/opus"))  # ①
    assert res.error is None


def test_review_branch_transport_parity(monkeypatch):
    import microbench_review as mr

    cap = {}

    def fake(model, prompt, *, system, timeout):
        cap["prompt"], cap["system"] = prompt, system
        return ("x", _USAGE)

    monkeypatch.setattr("claude_p.claude_p_call", fake)
    mr._claude_p_direct("claude-code/haiku", "FULL METHODOLOGY + CODE", timeout=10)
    assert cap["prompt"] == "FULL METHODOLOGY + CODE"  # methodology rides in the prompt
    assert cap["system"] == ""  # NOT split into --system-prompt


def test_review_branch_error_on_shim_failure(monkeypatch):
    import microbench_review as mr

    def boom(*a, **k):
        raise RuntimeError("no usable completion")

    monkeypatch.setattr("claude_p.claude_p_call", boom)
    res = mr._claude_p_direct("claude-code/opus", "task", timeout=10)
    assert res.error and "RuntimeError" in res.error


def test_review_branch_pricing_error_becomes_error_result(monkeypatch):
    import microbench_review as mr

    monkeypatch.setattr(
        "claude_p.claude_p_call", lambda model, prompt, *, system, timeout: ("ok", _USAGE)
    )

    def boom(*a, **k):
        raise KeyError("unpriced")

    monkeypatch.setattr(derive_cost, "api_equiv", boom)  # a pricing miss must NOT crash the run
    res = mr._claude_p_direct("claude-code/opus", "task", timeout=10)
    assert res.error and "KeyError" in res.error  # → error result, not an uncaught crash


def test_record_flywheel_skips_claude_code(monkeypatch):
    # claude-code/* are spawn-native — they must NEVER be recorded to the shared subagent_runs flywheel
    # (the pool routing source), or pick_models would surface them and the pool would 404.
    import microbench_review as mr

    recorded = []
    monkeypatch.setattr(mr, "record_agent_run", lambda spec, res, **k: (recorded.append(spec.model), True)[1])
    monkeypatch.setattr(mr, "cited_lines", lambda text: [])

    def _row(model):
        spec = type("S", (), {"model": model})()
        res = type("R", (), {"error": None, "text": "[]"})()
        item = type("I", (), {"truth_line": None})()  # control item → correct = (not flagged)
        return (spec, res, item)

    mr.record_flywheel([_row("claude-code/opus"), _row("openrouter/x")])
    assert "claude-code/opus" not in recorded  # spawn-native → never in the flywheel/routing table
    assert "openrouter/x" in recorded  # pool workers still recorded


def test_run_direct_routes_openrouter_to_direct_call_not_shim(monkeypatch):
    import microbench_review as mr

    hits = {"claudep": 0}
    monkeypatch.setattr(mr, "_or_pricing", lambda: {})
    monkeypatch.setattr(
        mr, "_direct_call", lambda model, *a, **k: mr._DirectResult(model, text="ok", out_tokens=1)
    )
    monkeypatch.setattr(
        "claude_p.claude_p_call", lambda *a, **k: (hits.__setitem__("claudep", 1), ("x", _USAGE))[1]
    )

    class Item:
        numbered_code = "1: x"

    _specs, _meta, results = mr.run_direct(["openrouter/x"], [Item()], max_tokens=50, concurrency=1)
    assert (
        results[0].model == "openrouter/x" and hits["claudep"] == 0
    )  # shim NOT called for an OR model


# ---------------- code branch (_one via generate) ----------------


def _prob(mc):
    return mc.Problem(question_id="q1", prompt="solve", starter_code="", sample={})


def test_code_branch_builds_gen(monkeypatch):
    import microbench_coding_direct as mc

    monkeypatch.setattr(
        "claude_p.claude_p_call",
        lambda model, prompt, *, system, timeout: ("```python\nx=1\n```", _USAGE),
    )
    out = mc.generate(["claude-code/opus"], [_prob(mc)], cost_cap=100.0)
    gen = out["claude-code/opus"][0]
    assert gen.error is None
    assert gen.code == mc.extract_code("```python\nx=1\n```")
    assert gen.cost_usd == pytest.approx(derive_cost.api_equiv(_USAGE, "claude-code/opus"))  # ①
    assert gen.out_tokens == 20


def test_code_branch_shim_error_is_nerr(monkeypatch):
    import microbench_coding_direct as mc

    def boom(*a, **k):
        raise RuntimeError("empty/zero usage")

    monkeypatch.setattr("claude_p.claude_p_call", boom)
    out = mc.generate(["claude-code/opus"], [_prob(mc)], cost_cap=100.0)
    gen = out["claude-code/opus"][0]
    assert gen.code is None and gen.error is not None  # → counted as n_err, never scored $0-success


# ---------------- ②/③ sidecar ----------------


def test_code_cost_cap_ignores_claude_spend(monkeypatch):
    import time as _t

    import microbench_coding_direct as mc

    big = {
        "input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }

    def slow(model, prompt, *, system, timeout):
        _t.sleep(
            0.03
        )  # keep the 2 workers busy so a cap-breach WOULD cancel not-yet-started futures (observable)
        return ("```python\nx=1\n```", big)

    monkeypatch.setattr("claude_p.claude_p_call", slow)
    probs = [
        mc.Problem(question_id=f"q{i}", prompt="s", starter_code="", sample={}) for i in range(6)
    ]
    # ① for this usage ≈ $30/call; cost_cap=0.01, concurrency capped to 2. A BROKEN build (claude counted
    # toward $) trips the cap after the 1st result and cancels the 4 not-yet-started futures → some code=None.
    # FIXED → the $ cap never trips on claude spend → all 6 complete.
    out = mc.generate(["claude-code/opus"], probs, cost_cap=0.01)
    assert sum(1 for g in out["claude-code/opus"] if g.code is not None) == 6


def test_write_cost_sidecar_three_keys(tmp_path):
    p = tmp_path / "claude_p_cost.json"
    data = derive_cost.write_cost_sidecar(
        10.0, 42.0, p, when=datetime.datetime(2026, 7, 20, 12, 0, 0)
    )
    assert set(data) == {"amortized_per_mtok", "quota_draw_pct", "built_at"}
    assert data["quota_draw_pct"] == pytest.approx(32.0)  # ③ = after - before
    assert json.loads(p.read_text())["quota_draw_pct"] == pytest.approx(32.0)
