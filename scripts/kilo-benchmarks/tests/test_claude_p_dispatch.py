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
    # raw per-type tokens carried through — needed for ② (real amortized $), distinct from ① above
    assert res.in_tokens == _USAGE["input_tokens"]
    assert res.cache_read_tokens == _USAGE["cache_read_input_tokens"]
    assert res.cache_creation_tokens == _USAGE["cache_creation_input_tokens"]
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
    monkeypatch.setattr(
        mr, "record_agent_run", lambda spec, res, **k: (recorded.append(spec.model), True)[1]
    )
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
        )  # keep the worker busy so a cap-breach WOULD cancel not-yet-started futures (observable);
        # all 6 futures are submitted upfront regardless of max_workers, so this holds at conc=1 too.
        return ("```python\nx=1\n```", big)

    monkeypatch.setattr("claude_p.claude_p_call", slow)
    probs = [
        mc.Problem(question_id=f"q{i}", prompt="s", starter_code="", sample={}) for i in range(6)
    ]
    # ① for this usage ≈ $30/call; cost_cap=0.01, concurrency capped to 1. A BROKEN build (claude counted
    # toward $) trips the cap after the 1st result and cancels the 5 not-yet-started futures → some code=None.
    # FIXED → the $ cap never trips on claude spend → all 6 complete.
    out = mc.generate(["claude-code/opus"], probs, cost_cap=0.01)
    assert sum(1 for g in out["claude-code/opus"] if g.code is not None) == 6


def test_all_batch_loop_still_measures_claude_after_or_budget_exhausted(monkeypatch):
    """The outer `--all` batch loop must not `break` the whole run once OR $ is exhausted — a LATER
    batch containing only claude-code/* models costs $0 real OR spend (same carve-out `generate()`
    already enforces per-call) and must still be measured, not silently dropped."""
    import microbench_coding_direct as mc

    class _Score:
        def __init__(self, cost_usd):
            self.cost_usd = cost_usd
            self.is_measured = True

    monkeypatch.setattr(mc, "BATCH_SIZE", 1)  # one model per batch: isolates the OR batch from the claude one
    monkeypatch.setattr(mc, "_openrouter_balance", lambda: None)
    monkeypatch.setattr(
        mc, "load_corpus", lambda window, limit: [mc.Problem("q0", "s", "", {})]
    )
    monkeypatch.setattr(mc, "_resolve_models", lambda explicit, db_path=mc.DB_PATH: explicit or [])
    monkeypatch.setattr(mc, "_measured_models", lambda window: set())
    monkeypatch.setattr(mc, "persist_metrics", lambda *a, **k: None)
    monkeypatch.setattr(mc, "persist_baseline", lambda *a, **k: None)
    monkeypatch.setattr(mc, "report", lambda *a, **k: None)

    dispatched = []

    def fake_generate(batch, corpus, cost_cap, max_tokens, max_concurrency):
        dispatched.append(list(batch))
        return {m: [] for m in batch}

    def fake_grade(gens, corpus):
        return {m: _Score(cost_usd=100.0 if not m.startswith("claude-code/") else 0.0) for m in gens}

    monkeypatch.setattr(mc, "generate", fake_generate)
    monkeypatch.setattr(mc, "grade", fake_grade)

    # eff_cap=1.0; the OR batch's $100 "spend" blows straight past it, leaving rem deeply negative for
    # every later batch. A BROKEN build (bare `break`) stops here — the claude batch never dispatches.
    # FIXED → the claude-only batch still runs (it can't cost anything regardless of `rem`).
    rc = mc.main(
        [
            "--all",
            "--cost-cap",
            "1.0",
            "--models",
            "openrouter/some-model",
            "claude-code/opus",
        ]
    )
    assert rc == 0
    assert dispatched == [["openrouter/some-model"], ["claude-code/opus"]]


def test_all_batch_loop_reaches_claude_past_an_intervening_all_or_batch(monkeypatch):
    """A budget-exhausted batch that is ENTIRELY OR-priced (nothing claude-code/* to keep) must not
    `break` the whole scan — a LATER batch can still hold a free claude-code/* model. The sorted default
    doesn't guarantee every claude id is contiguous with the first exhausted batch, so an intervening
    all-OR batch must be skipped with `continue`, not treated as the end of the run."""
    import microbench_coding_direct as mc

    class _Score:
        def __init__(self, cost_usd):
            self.cost_usd = cost_usd
            self.is_measured = True

    monkeypatch.setattr(mc, "BATCH_SIZE", 1)  # one model per batch: isolates all three
    monkeypatch.setattr(mc, "_openrouter_balance", lambda: None)
    monkeypatch.setattr(mc, "load_corpus", lambda window, limit: [mc.Problem("q0", "s", "", {})])
    monkeypatch.setattr(mc, "_resolve_models", lambda explicit, db_path=mc.DB_PATH: explicit or [])
    monkeypatch.setattr(mc, "_measured_models", lambda window: set())
    monkeypatch.setattr(mc, "persist_metrics", lambda *a, **k: None)
    monkeypatch.setattr(mc, "persist_baseline", lambda *a, **k: None)
    monkeypatch.setattr(mc, "report", lambda *a, **k: None)

    dispatched = []

    def fake_generate(batch, corpus, cost_cap, max_tokens, max_concurrency):
        dispatched.append(list(batch))
        return {m: [] for m in batch}

    def fake_grade(gens, corpus):
        return {m: _Score(cost_usd=100.0 if not m.startswith("claude-code/") else 0.0) for m in gens}

    monkeypatch.setattr(mc, "generate", fake_generate)
    monkeypatch.setattr(mc, "grade", fake_grade)

    # eff_cap=1.0: batch 1 (or-1) blows past it. Batch 2 (or-2) is ALSO pure-OR — a BROKEN build (bare
    # `break` on an empty post-filter batch) stops the scan HERE, and claude-code/opus in batch 3 is never
    # reached. FIXED → batch 2 is skipped (`continue`), batch 3 still dispatches.
    rc = mc.main(
        [
            "--all",
            "--cost-cap",
            "1.0",
            "--models",
            "openrouter/or-1",
            "openrouter/or-2",
            "claude-code/opus",
        ]
    )
    assert rc == 0
    assert dispatched == [["openrouter/or-1"], ["claude-code/opus"]]  # or-2's batch never dispatches


def test_all_batch_loop_survives_a_grading_crash(monkeypatch):
    """`grade()` shells out to the LiveCodeBench sandbox subprocess (`check=True` — CAN raise). A crash
    grading ONE batch must not lose the chance to measure every LATER batch — and the batch's already-
    spent real OR $ (from `generate()`, sunk regardless of grading outcome) must still count against the
    cost-cap, or a repeat grader failure would let real spend silently exceed `eff_cap`."""
    import microbench_coding_direct as mc

    class _Gen:
        def __init__(self, cost_usd):
            self.cost_usd = cost_usd

    class _Score:
        def __init__(self, cost_usd=0.0):
            self.cost_usd = cost_usd

        is_measured = True

    monkeypatch.setattr(mc, "BATCH_SIZE", 1)
    monkeypatch.setattr(mc, "_openrouter_balance", lambda: None)
    monkeypatch.setattr(mc, "load_corpus", lambda window, limit: [mc.Problem("q0", "s", "", {})])
    monkeypatch.setattr(mc, "_resolve_models", lambda explicit, db_path=mc.DB_PATH: explicit or [])
    monkeypatch.setattr(mc, "_measured_models", lambda window: set())
    monkeypatch.setattr(mc, "persist_metrics", lambda *a, **k: None)
    monkeypatch.setattr(mc, "persist_baseline", lambda *a, **k: None)
    monkeypatch.setattr(mc, "report", lambda *a, **k: None)

    generate_calls = []

    def fake_generate(batch, corpus, cost_cap, **kw):
        generate_calls.append((list(batch), cost_cap))
        return {m: [_Gen(2.5)] for m in batch}

    monkeypatch.setattr(mc, "generate", fake_generate)

    graded_batches = []

    def flaky_grade(gens, corpus):
        graded_batches.append(list(gens))
        if list(gens) == ["crashy-model"]:
            raise RuntimeError("LCB sandbox subprocess timed out")
        return {m: _Score(cost_usd=2.5) for m in gens}

    monkeypatch.setattr(mc, "grade", flaky_grade)

    rc = mc.main(["--all", "--cost-cap", "3.0", "--models", "crashy-model", "healthy-model"])
    assert rc == 0
    # BOTH batches were attempted — the crash on batch 1 did not stop batch 2 from being graded.
    assert graded_batches == [["crashy-model"], ["healthy-model"]]
    # batch 2's cost_cap must reflect batch 1's $2.5 already counted against the $3.0 total — a
    # regression that forgets to count a crashed batch's spend would pass the FULL $3.0 through instead.
    assert generate_calls[1][1] == pytest.approx(3.0 - 2.5)


def test_all_batch_loop_survives_a_persist_crash(monkeypatch):
    """`persist_metrics`/`persist_baseline` do a raw `sqlite3.connect` with no exception handling — on a
    shared box (the daily pipeline + concurrent agents write the same DB) a transient `database is locked`
    must not crash the whole `--all` run, and the batch's real spend (already grading-succeeded) must
    still count against the cost-cap."""
    import microbench_coding_direct as mc

    class _Gen:
        def __init__(self, cost_usd):
            self.cost_usd = cost_usd

    class _Score:
        def __init__(self, cost_usd=0.0):
            self.cost_usd = cost_usd

        is_measured = True

    monkeypatch.setattr(mc, "BATCH_SIZE", 1)
    monkeypatch.setattr(mc, "_openrouter_balance", lambda: None)
    monkeypatch.setattr(mc, "load_corpus", lambda window, limit: [mc.Problem("q0", "s", "", {})])
    monkeypatch.setattr(mc, "_resolve_models", lambda explicit, db_path=mc.DB_PATH: explicit or [])
    monkeypatch.setattr(mc, "_measured_models", lambda window: set())
    monkeypatch.setattr(mc, "report", lambda *a, **k: None)

    generate_calls = []
    monkeypatch.setattr(
        mc,
        "generate",
        lambda batch, corpus, cost_cap, **kw: generate_calls.append((list(batch), cost_cap))
        or {m: [_Gen(2.5)] for m in batch},
    )
    monkeypatch.setattr(mc, "grade", lambda gens, corpus: {m: _Score(cost_usd=2.5) for m in gens})

    def locked_persist(scores, window, db_path=mc.DB_PATH):
        if "crashy-model" in scores:
            import sqlite3

            raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(mc, "persist_metrics", locked_persist)
    monkeypatch.setattr(mc, "persist_baseline", lambda *a, **k: None)

    rc = mc.main(["--all", "--cost-cap", "3.0", "--models", "crashy-model", "healthy-model"])
    assert rc == 0
    # both batches were attempted — a locked-DB write on batch 1 did not stop batch 2.
    assert [c[0] for c in generate_calls] == [["crashy-model"], ["healthy-model"]]
    # batch 2's cost_cap reflects batch 1's $2.5 already counted, even though it was never persisted.
    assert generate_calls[1][1] == pytest.approx(3.0 - 2.5)


# ---------------- ② real amortized cost — token accumulation + persist migration ----------------


def test_grade_accumulates_raw_tokens_for_amortized_cost():
    import microbench_review as mr

    class _Res:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    class _Item:
        def __init__(self, truth_line):
            self.truth_line = truth_line

    def _res():
        return _Res(
            error=None,
            text="[]",
            latency_s=1.0,
            out_tokens=10,
            cost_usd=0.01,
            out_price_mtok=25.0,
            in_tokens=5,
            cache_read_tokens=100,
            cache_creation_tokens=200,
        )

    specs = [object(), object()]
    meta = [("claude-code/opus", _Item(None)), ("claude-code/opus", _Item(None))]
    scores, _rows = mr.grade(specs, meta, [_res(), _res()])
    s = scores["claude-code/opus"]
    assert s.in_tokens == 10  # 5 + 5 across both calls
    assert s.cache_read_tokens == 200
    assert s.cache_creation_tokens == 400


def test_persist_metrics_migration_adds_token_columns(tmp_path, monkeypatch):
    import sqlite3

    import microbench_review as mr

    db = tmp_path / "kilo_agents.db"
    monkeypatch.setattr(mr, "DB_PATH", db)
    s = mr.ModelScore("claude-code/haiku", 9, 7, 2, 0, [1.0, 2.0], 142, 5.6833)
    s.in_tokens, s.cache_read_tokens, s.cache_creation_tokens = 9, 20215, 26030
    mr.persist_metrics({"claude-code/haiku": s})
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT in_tokens, out_tokens_total, cache_read_tokens, cache_creation_tokens "
        "FROM model_review_metrics WHERE model_id='claude-code/haiku'"
    ).fetchone()
    conn.close()
    assert row == (9, 142, 20215, 26030)


def test_amortized_cost_for_computes_positive_from_modelscore():
    import microbench_review as mr

    s = mr.ModelScore("claude-code/haiku", 9, 7, 2, 0, [1.0], 142, 5.6833)
    s.in_tokens, s.cache_read_tokens, s.cache_creation_tokens = 9, 20215, 26030
    assert mr._amortized_cost_for(s) > 0


def test_report_prints_amortized_column_for_claude_not_for_or(capsys):
    import microbench_review as mr

    claude = mr.ModelScore("claude-code/haiku", 9, 7, 2, 0, [1.0], 142, 5.6833)
    claude.in_tokens, claude.cache_read_tokens, claude.cache_creation_tokens = 9, 20215, 26030
    claude.out_price_mtok = 5.0
    orm = mr.ModelScore("openrouter/x", 9, 7, 2, 0, [1.0], 100, 0.05)
    orm.out_price_mtok = 3.0
    mr.report({"claude-code/haiku": claude, "openrouter/x": orm})
    out = capsys.readouterr().out
    assert "②total$" in out  # the new column header renders
    claude_line = next(line for line in out.splitlines() if "claude-code/haiku" in line)
    or_line = next(line for line in out.splitlines() if "openrouter/x" in line)
    assert f"${mr._amortized_cost_for(claude):.6f}" in claude_line  # real ② for the claude row
    assert "—" in or_line and "$0.000" not in or_line  # OR row shows the dash, never a number


# ---------------- review-harness resume (_measured_review_models + main --fresh) ----------------


def test_measured_review_models_filters_by_today(tmp_path):
    import sqlite3

    import microbench_review as mr

    db = tmp_path / "kilo_agents.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE model_review_metrics (model_id TEXT, score5 REAL, grade TEXT, recall REAL, "
        "precision REAL, out_price_mtok REAL, cost_usd REAL, cost_per_1k REAL, p50_latency_s REAL, "
        "tokens_per_s REAL, n_mut INTEGER, n_ctrl INTEGER, built_at TEXT, PRIMARY KEY (model_id, built_at))"
    )
    today = datetime.date.today().isoformat()
    conn.execute(
        "INSERT INTO model_review_metrics VALUES ('claude-code/opus',4,'A',1,1,1,1,1,1,1,1,1,?)",
        (today,),
    )
    conn.execute(  # a STALE row (not today) must NOT count as "already measured"
        "INSERT INTO model_review_metrics VALUES "
        "('claude-code/haiku',4,'A',1,1,1,1,1,1,1,1,1,'2020-01-01')"
    )
    conn.commit()
    conn.close()
    assert mr._measured_review_models(db) == {"claude-code/opus"}


def test_measured_review_models_missing_table_is_empty(tmp_path):
    import microbench_review as mr

    assert mr._measured_review_models(tmp_path / "nope.db") == set()


def test_main_resume_skips_already_measured_model(monkeypatch):
    import microbench_review as mr

    monkeypatch.setattr(mr, "_measured_review_models", lambda *a, **k: {"claude-code/opus"})
    dispatched = {}

    def fake_run_direct(models, corpus, max_tokens, concurrency):
        dispatched["models"] = list(models)
        return [], [], []

    monkeypatch.setattr(mr, "run_direct", fake_run_direct)
    rc = mr.main(["--smoke", "--direct", "--models", "claude-code/opus", "claude-code/haiku"])
    assert rc == 0
    assert dispatched["models"] == ["claude-code/haiku"]  # opus skipped (already measured today)


def test_main_fresh_bypasses_resume_skip(monkeypatch):
    import microbench_review as mr

    monkeypatch.setattr(mr, "_measured_review_models", lambda *a, **k: {"claude-code/opus"})
    dispatched = {}

    def fake_run_direct(models, corpus, max_tokens, concurrency):
        dispatched["models"] = list(models)
        return [], [], []

    monkeypatch.setattr(mr, "run_direct", fake_run_direct)
    mr.main(["--smoke", "--direct", "--fresh", "--models", "claude-code/opus", "claude-code/haiku"])
    assert dispatched["models"] == [
        "claude-code/opus",
        "claude-code/haiku",
    ]  # --fresh re-measures all


def test_main_all_models_already_measured_skips_dispatch_entirely(monkeypatch):
    import microbench_review as mr

    monkeypatch.setattr(
        mr, "_measured_review_models", lambda *a, **k: {"claude-code/opus", "claude-code/haiku"}
    )
    called = []
    monkeypatch.setattr(mr, "run_direct", lambda *a, **k: called.append(1) or ([], [], []))
    rc = mr.main(["--smoke", "--direct", "--models", "claude-code/opus", "claude-code/haiku"])
    assert rc == 0
    assert not called  # nothing left to dispatch → run_direct never called


def test_write_cost_sidecar_three_keys(tmp_path):
    p = tmp_path / "claude_p_cost.json"
    data = derive_cost.write_cost_sidecar(
        10.0, 42.0, p, when=datetime.datetime(2026, 7, 20, 12, 0, 0)
    )
    assert set(data) == {"amortized_per_mtok", "quota_draw_pct", "built_at"}
    assert data["quota_draw_pct"] == pytest.approx(32.0)  # ③ = after - before
    assert json.loads(p.read_text())["quota_draw_pct"] == pytest.approx(32.0)
