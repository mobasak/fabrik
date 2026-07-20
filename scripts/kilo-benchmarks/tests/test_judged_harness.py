"""Phase A Behavior Contract — the judged-benchmark shared harness (microbench_judged.py).

Covers: record_flywheel writes one subagent_runs row per SUCCESS with quality_score=score5 and the
right task_type [TDD]; persist_metrics round-trip + grade cut; persist_baseline writes the task_type
prior with the right source; an unmeasured (<3 graded) model is NOT persisted; _measured_models
drives the window-scoped resume-skip. All against a TEMP sqlite — no real db, no network, no spend.
"""

import json
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import microbench_judged as mj  # noqa: E402


def _measured_gen(model: str, i: int, task_type: str = "research", text: str = "answer") -> mj._Gen:
    """A successful generation with its synthetic (spec, result) flywheel pair attached."""
    g = mj._Gen(text=text, cost_usd=0.01, latency_s=1.0, out_tokens=5, error=None)
    mj._synth_pair(model, task_type, "prompt", i, g, "2026-07-19")
    return g


def _score(model: str, score5: float, n: int = 3) -> mj.TaskScore:
    return mj.TaskScore(
        model=model,
        score5=score5,
        n_graded=n,
        n_err=0,
        cost_usd=0.03,
        latencies=[1.0] * n,
        out_tokens=15,
    )


# ── (a) record_flywheel — the surface-a-cold-model fix [TDD, highest risk] ─────────────────────
def test_record_flywheel_writes_one_row_per_success_with_score5(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        mj,
        "record_agent_run",
        lambda spec, res, **kw: calls.append(
            {
                "model": spec.model,
                "task_type": spec.task_type,
                "status": res.status,
                "quality_score": kw.get("quality_score"),
                "project": kw.get("project"),
            }
        )
        or True,
    )
    gens = {"m/x": [_measured_gen("m/x", i) for i in range(3)]}
    scores = {"m/x": _score("m/x", 4.2)}
    n = mj.record_flywheel(gens, scores, project="microbench")
    assert n == 3
    assert len(calls) == 3
    assert all(c["quality_score"] == 4.2 for c in calls)  # quality_score == score5
    assert all(c["task_type"] == "research" for c in calls)  # task_type carried on the SPEC
    assert all(c["status"] == "done" for c in calls)  # else record_run nulls the score
    assert all(c["project"] == "microbench" for c in calls)


def test_record_flywheel_skips_errored_calls(monkeypatch):
    calls: list = []
    monkeypatch.setattr(mj, "record_agent_run", lambda spec, res, **kw: calls.append(spec) or True)
    good = [_measured_gen("m/x", i) for i in range(3)]
    errored = mj._Gen(text=None, cost_usd=0.0, latency_s=None, out_tokens=0, error="404")
    gens = {"m/x": [*good, errored]}
    n = mj.record_flywheel(gens, {"m/x": _score("m/x", 5.0, n=3)}, project="microbench")
    assert n == 3  # the errored slot (text=None, no spec/result) is skipped


def test_record_flywheel_skips_unmeasured_model(monkeypatch):
    calls: list = []
    monkeypatch.setattr(mj, "record_agent_run", lambda spec, res, **kw: calls.append(spec) or True)
    gens = {"m/x": [_measured_gen("m/x", 0)]}  # only 1 graded
    n = mj.record_flywheel(gens, {"m/x": _score("m/x", 5.0, n=1)}, project="microbench")
    assert n == 0 and calls == []  # <3 graded → not measured → no flywheel rows


# ── (b) persist_metrics round-trip + grade cut ─────────────────────────────────────────────────
def test_persist_metrics_roundtrips_with_grade_cut(tmp_path):
    db = tmp_path / "k.db"
    scores = {"m/a": _score("m/a", 4.6), "m/b": _score("m/b", 2.1)}
    mj.persist_metrics(scores, "research", "v1", db)
    conn = sqlite3.connect(db)
    rows = {
        r[0]: r
        for r in conn.execute(
            "SELECT model_id, task_type, score5, grade, n_graded FROM model_judged_metrics"
        ).fetchall()
    }
    conn.close()
    assert rows["m/a"][1] == "research" and rows["m/a"][3] == "A+"  # 4.6 → A+
    assert rows["m/b"][3] == "C"  # 2.1 → C


# ── (c) persist_baseline writes the task_type prior with the right source ───────────────────────
def test_persist_baseline_writes_task_prior_with_source(tmp_path):
    db = tmp_path / "k.db"
    n = mj.persist_baseline({"m/a": _score("m/a", 3.5)}, "docs", "v1", db)
    assert n == 1
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT task_type, baseline, source, pass_rate FROM model_task_baseline WHERE model_id='m/a'"
    ).fetchone()
    conn.close()
    assert row[0] == "docs" and row[1] == 3.5 and row[2] == "microbench_judged:docs"
    assert row[3] == 0.7  # pass_rate = score5 / 5


# ── (d) an unmeasured (<3 graded) model is NOT persisted ───────────────────────────────────────
def test_unmeasured_model_not_persisted(tmp_path):
    db = tmp_path / "k.db"
    cold = mj.TaskScore(model="m/cold", score5=5.0, n_graded=2, n_err=0)  # only 2 graded
    assert mj.persist_baseline({"m/cold": cold}, "research", "v1", db) == 0
    mj.persist_metrics({"m/cold": cold}, "research", "v1", db)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM model_judged_metrics").fetchone()[0] == 0
    conn.close()


# ── (e) _measured_models drives the window-scoped resume-skip ──────────────────────────────────
def test_measured_models_resume_skip_is_window_scoped(tmp_path):
    db = tmp_path / "k.db"
    mj.persist_metrics({"m/a": _score("m/a", 4.0)}, "research", "v1", db)
    mj.persist_metrics({"m/b": _score("m/b", 4.0)}, "research", "v2", db)  # different window
    assert mj._measured_models("research", "v1", db) == {"m/a"}
    assert mj._measured_models("research", "v2", db) == {"m/b"}
    assert mj._measured_models("docs", "v1", db) == set()  # different task → empty


# ── spine: the stub grader + smoke run end-to-end ($0) ─────────────────────────────────────────
def test_stub_grader_and_smoke_end_to_end(tmp_path, monkeypatch):
    recorded: list = []
    monkeypatch.setattr(
        mj, "record_agent_run", lambda spec, res, **kw: recorded.append(spec) or True
    )
    db = tmp_path / "k.db"
    scores = mj.run_smoke("research", db)
    s = scores["smoke/echo-model"]
    assert s.is_measured and s.n_graded >= mj.MIN_MEASURED  # ≥3 items → measured
    assert len(recorded) >= mj.MIN_MEASURED  # ≥3 flywheel rows → clears HAVING COUNT>=3
    conn = sqlite3.connect(db)
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM model_task_baseline WHERE task_type='research'"
        ).fetchone()[0]
        == 1
    )
    conn.close()


# ── review-fix regressions ─────────────────────────────────────────────────────────────────────
def test_finalize_scores_overrides_grader_omitted_cost():
    """The harness owns cost/latency/tokens/n_err from gens — a grader that forgets to thread them
    (returns cost_usd=0) must NOT zero the cross-batch cost gate (reviewer finding #1)."""
    gens = {
        "m/x": [
            mj._Gen(text="a", cost_usd=0.04, latency_s=2.0, out_tokens=10, error=None),
            mj._Gen(text="b", cost_usd=0.06, latency_s=1.0, out_tokens=5, error=None),
            mj._Gen(text=None, cost_usd=0.0, latency_s=None, out_tokens=0, error="404"),
        ]
    }
    grader_out = {"m/x": mj.TaskScore(model="m/x", score5=4.0, n_graded=2, n_err=0, cost_usd=0.0)}
    fin = mj._finalize_scores(grader_out, gens)["m/x"]
    assert fin.cost_usd == 0.1  # real billed cost from gens, not the grader's 0.0
    assert fin.out_tokens == 15 and fin.n_err == 1
    assert fin.median_latency > 0


def test_record_flywheel_counts_committed_not_attempted(monkeypatch):
    """record_flywheel returns the COMMITTED count; on a no-DSN box record_agent_run outboxes and
    returns False → n==0 with no crash (reviewer finding F-A — the count must not overclaim)."""
    monkeypatch.setattr(
        mj, "record_agent_run", lambda spec, res, **kw: False
    )  # outboxed, not committed
    gens = {"m/x": [_measured_gen("m/x", i) for i in range(3)]}
    n = mj.record_flywheel(gens, {"m/x": _score("m/x", 5.0, n=3)}, project="microbench")
    assert n == 0  # 3 attempted, 0 committed — honest


def test_done_gate_nulls_score_for_non_done_result():
    """END-TO-END through the REAL record_run: a status != 'done' result has its quality_score
    coerced to NULL (pg_ledger:170). Proves WHY _synth_pair must stamp status='done' — the gap the
    fully-mocked flywheel test could not cover (reviewer test-quality finding)."""
    from libs.subagents.agent import AgentResult, AgentSpec
    from libs.subagents.pg_ledger import record_agent_run

    captured: list = []

    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, row=None):
            if row is not None:
                captured.append(row)

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def cursor(self):
            return _Cur()

        def close(self):
            pass

    spec = AgentSpec(task="p", model="m/x", task_type="research")

    def _row_for(status: str):
        captured.clear()
        res = AgentResult(
            agent_id="a1",
            text="t",
            diff="",
            status=status,
            provider=None,
            cost_usd=0.0,
            turns=1,
            latency_s=1.0,
            out_tokens=1,
            model="m/x",
        )
        record_agent_run(
            spec, res, quality_score=4.2, project="t", dsn="fake://x", connect=lambda dsn: _Conn()
        )
        return captured[0]

    assert _row_for("done")[9] == 4.2  # quality_score persists for a done result
    assert _row_for("capped")[9] is None  # …but is NULLed for a non-done result


def test_metrics_pk_includes_window_same_model_two_windows_survive(tmp_path):
    """Same model, two windows, same day → BOTH rows survive (PK includes window). The v2 write must
    not overwrite v1, else _measured_models(v1) goes empty and the model is re-paid (finding F-C)."""
    db = tmp_path / "k.db"
    mj.persist_metrics({"m/a": _score("m/a", 4.0)}, "research", "v1", db)
    mj.persist_metrics({"m/a": _score("m/a", 3.0)}, "research", "v2", db)  # SAME model, new window
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM model_judged_metrics WHERE model_id='m/a'").fetchone()[0]
    conn.close()
    assert n == 2
    assert mj._measured_models("research", "v1", db) == {"m/a"}
    assert mj._measured_models("research", "v2", db) == {"m/a"}


def test_load_judged_metrics_reads_single_table(tmp_path):
    """Phase-E reader returns latest-per-model for ONE task from the single model_judged_metrics table
    (a naive mirror querying model_research_metrics would read an empty non-existent table — finding #2)."""
    db = tmp_path / "k.db"
    assert mj.load_judged_metrics("research", db) == {}  # fail-soft before any run
    mj.persist_metrics({"m/a": _score("m/a", 4.6)}, "research", "v1", db)
    mj.persist_metrics({"m/b": _score("m/b", 2.0)}, "docs", "v1", db)
    got = mj.load_judged_metrics("research", db)
    assert set(got) == {"m/a"} and got["m/a"]["grade"] == "A+"  # docs row excluded


def test_persist_metrics_artifact_merges_across_batches(tmp_path, monkeypatch):
    """The JSON artifact ACCUMULATES all measured models across batches (reviewer C1) — not just the
    last batch's — and carries the window so two windows same day don't clobber."""
    monkeypatch.setattr(mj, "CACHE_DIR", tmp_path / "cache")
    db = tmp_path / "k.db"
    a1 = mj.persist_metrics({"m/a": _score("m/a", 4.0)}, "research", "v1", db)
    a2 = mj.persist_metrics(
        {"m/b": _score("m/b", 3.0)}, "research", "v1", db
    )  # same file, 2nd batch
    assert a1 == a2 and "v1" in a1.name
    art = json.loads(a1.read_text())
    assert set(art) == {"m/a", "m/b"}  # merged, not overwritten


def test_persist_metrics_artifact_survives_non_object_json(tmp_path, monkeypatch):
    """A pre-existing artifact that is valid JSON but NOT an object (e.g. `[1,2,3]`) must not crash the
    merge — reset to {} then write this batch (reviewer final-pass L1)."""
    from datetime import date

    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(mj, "CACHE_DIR", cache)
    art_name = f"judged_metrics_research_v1_{date.today().isoformat()}.json"
    (cache / art_name).write_text("[1,2,3]")  # valid JSON, wrong type → must not AttributeError
    art = mj.persist_metrics({"m/a": _score("m/a", 4.0)}, "research", "v1", tmp_path / "k.db")
    out = json.loads(art.read_text())
    assert isinstance(out, dict) and set(out) == {"m/a"}


def test_load_judged_metrics_same_day_two_windows_is_deterministic(tmp_path):
    """Same model, two windows, same built_at → the reader returns the higher-window row DETERMINISTICALLY
    (ORDER BY built_at, window; reviewer C3), never a nondeterministic pick."""
    db = tmp_path / "k.db"
    mj.persist_metrics({"m/a": _score("m/a", 4.6)}, "research", "v1", db)
    mj.persist_metrics({"m/a": _score("m/a", 2.0)}, "research", "v2", db)
    got = mj.load_judged_metrics("research", db)["m/a"]
    assert got["score5"] == 2.0 and got["grade"] == "C"  # v2 (higher window) wins, deterministic


def test_report_stored_empty_task_prints_friendly_message(tmp_path, capsys):
    """report_stored on a task with no rows (table present) prints the friendly message, not
    'built None' (reviewer final-pass — closes Guard 2's coverage gap)."""
    db = tmp_path / "k.db"
    mj.persist_metrics(
        {"m/a": _score("m/a", 4.0)}, "research", "v1", db
    )  # creates table, research only
    mj.report_stored("plan", db)  # table exists, zero plan rows → latest is None
    out = capsys.readouterr().out
    assert "no stored plan metrics" in out and "built None" not in out
    mj.report_stored("research", db)  # normal path still works
    assert "m/a" in capsys.readouterr().out


def test_resolve_models_auto_tier_is_task_scoped(monkeypatch):
    """--auto-tier must select THIS task's pool, not always research's (finding #4)."""
    seen: list = []
    monkeypatch.setattr(
        "libs.subagents.select.pick_models", lambda task, n=1, **kw: seen.append(task) or ["x/y"]
    )
    mj._resolve_models(None, auto_tier=True, task_type="docs")
    assert seen == ["docs"]


def test_corpus_files_map_matches_disk():
    """F1 regression: main() resolves the docs corpus to docs_pairs.json (NOT docs_qa.json), and both
    generation corpora exist on disk — else `--task docs --all` fails 'corpus missing'."""
    assert mj._CORPUS_FILES == {"research": "research_qa.json", "docs": "docs_pairs.json"}
    for fn in mj._CORPUS_FILES.values():
        assert (mj.SCRIPT_DIR / "corpora" / fn).exists(), fn


def test_main_routes_structural_tasks_to_correlated_prior(capsys):
    """plan/spec have no generation corpus → main(--all) exits 1 pointing at correlated_prior, not a
    misleading 'corpus missing'. Returns before any model resolution / network."""
    rc = mj.main(["--task", "plan", "--all", "--models", "x/y"])
    assert rc == 1
    assert "correlated_prior" in capsys.readouterr().err


def test_run_smoke_cli_path_is_production_safe(monkeypatch):
    """Whole-plan review A1: run_smoke(write_flywheel=False) writes NO flywheel row and persists to a
    TEMP db (never DB_PATH) — else smoke/echo-model (score5=5) would land in the real gate/tables and
    drop every real fleet model."""
    fly_calls: list = []
    persisted_dbs: list = []
    monkeypatch.setattr(mj, "record_agent_run", lambda *a, **k: fly_calls.append(1) or True)
    real_pm = mj.persist_metrics
    monkeypatch.setattr(
        mj, "persist_metrics",
        lambda scores, t, w, db: persisted_dbs.append(db) or real_pm(scores, t, w, db),
    )
    scores = mj.run_smoke("research", write_flywheel=False)  # the CLI path
    assert fly_calls == []  # NO production flywheel write
    assert scores["smoke/echo-model"].is_measured
    assert persisted_dbs and persisted_dbs[0] != mj.DB_PATH  # a TEMP db, not the real store
