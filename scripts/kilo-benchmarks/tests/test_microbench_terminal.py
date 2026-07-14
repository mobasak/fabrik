#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/microbench_terminal.py
"""Behavior tests for microbench_terminal.py (Terminal-Bench runner).

Covers the plan's Behavior Contract 1-7. The risky paths (injection guard,
cost-cap abort) are exercised first.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import microbench_terminal as mt  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "tb_output.json"


@pytest.fixture(autouse=True)
def _clear_task_meta_cache():
    """load_task_meta memoizes into a module-global dict. Without this, one test's
    dataset fixture leaks into another that reuses the same dataset string — the suite
    would pass or fail on test ORDER, and a stale-meta bug would hide behind the cache."""
    mt._TASK_META_CACHE.clear()
    yield
    mt._TASK_META_CACHE.clear()


def _mkdb(tmp_path: Path) -> sqlite3.Connection:
    """Minimal agents table with the columns the runner reads/writes."""
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute(
        "CREATE TABLE agents ("
        "id TEXT PRIMARY KEY, via_openrouter INTEGER, status TEXT, "
        "has_tools INTEGER, tbench_accuracy REAL, last_verified TEXT, "
        "arena_elo INTEGER)"
    )
    conn.commit()
    return conn


# --- Behavior 1: shell-out injection blocked (highest risk) ------------------
@pytest.mark.parametrize(
    "bad",
    ["m; rm -rf /", "../etc/passwd", "-x-flag", "a b", "a`whoami`", "a|b", "a$(x)", "a&b"],
)
def test_validate_model_id_rejects_metachars(bad):
    with pytest.raises(ValueError):
        mt._validate_model_id(bad)


@pytest.mark.parametrize("good", ["minimax/minimax-m3", "z-ai/glm-5.2", "deepseek/deepseek-v4-pro"])
def test_validate_model_id_accepts_real_ids(good):
    assert mt._validate_model_id(good) == good


def test_run_one_validates_before_dispatch(monkeypatch, tmp_path):
    called = {"ran": False}
    monkeypatch.setattr(mt.subprocess, "run", lambda *a, **k: called.__setitem__("ran", True))
    with pytest.raises(ValueError):
        mt.run_one("bad; id", tmp_path)
    assert called["ran"] is False  # never reached subprocess


def _seed_main_db(tmp_path, ids):
    seed = _mkdb(tmp_path)
    seed.executemany(
        "INSERT INTO agents (id, via_openrouter, status, has_tools) VALUES (?,1,'active',1)",
        [(i,) for i in ids],
    )
    seed.commit()
    seed.close()


# --- Behavior 2: run (cohort) budget — main measures spend, counts it even on failure -
def test_cohort_budget_stops_run_before_next_model(monkeypatch, tmp_path):
    """main accumulates each model's measured spend and stops before the next model
    once the tally reaches the cap. A budget stop AFTER a model scored is a partial
    SUCCESS → exit 0 (not a false failure)."""
    _seed_main_db(tmp_path, ["vendor/m1", "vendor/m2"])
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mt.shutil, "which", lambda x: "/usr/bin/tb")
    benched = []
    monkeypatch.setattr(mt, "bench_model", lambda conn, m, **k: benched.append(m) or 55.0)
    # m1 scores; before=100, after=97 → spent 3 >= cap 2 → STOP before m2.
    balances = iter([100.0, 97.0])
    monkeypatch.setattr(mt, "openrouter_balance", lambda: next(balances))
    rc = mt.main(
        ["--models", "vendor/m1,vendor/m2", "--cost-cap", "2", "--n-tasks", "1", "--force"]
    )
    assert rc == 0  # m1 scored → partial success, NOT a false failure exit
    assert benched == ["vendor/m1"]  # m2 never dispatched — budget stopped the run


def test_malformed_cohort_id_returns_2(monkeypatch, tmp_path):
    """A malformed DB-sourced model id surfaces as a config error (exit 2), not a
    silent per-model 'FAILED' skip masked by the MODEL_FAILURE(ValueError) catch."""
    seed = _mkdb(tmp_path)
    seed.execute(
        "INSERT INTO agents (id, via_openrouter, status, has_tools) VALUES ('foo bar',1,'active',1)"
    )
    seed.commit()
    seed.close()
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mt.shutil, "which", lambda x: "/usr/bin/tb")
    called = {"bench": False}
    monkeypatch.setattr(mt, "bench_model", lambda *a, **k: called.__setitem__("bench", True))
    rc = mt.main(["--models", "all", "--n-tasks", "1", "--force"])
    assert rc == 2  # surfaced up front
    assert called["bench"] is False  # never started benching


def test_spend_counted_even_when_model_fails(monkeypatch, tmp_path):
    """Finding (pass-3): a model that FAILS after spending credit must still have
    that spend counted toward the run budget — main brackets the call, so the
    failed model's $spend blocks the next model."""
    import subprocess as _sp

    _seed_main_db(tmp_path, ["vendor/bad", "vendor/m2"])
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mt.shutil, "which", lambda x: "/usr/bin/tb")
    benched = []

    def fake_bench(conn, m, **k):
        if m == "vendor/bad":
            raise _sp.CalledProcessError(1, ["tb"])  # fails AFTER spending
        benched.append(m)
        return 60.0

    monkeypatch.setattr(mt, "bench_model", fake_bench)
    # bad: before=100, after=96 → spent 4 counted DESPITE the failure → 4 >= cap 3 → STOP before m2
    balances = iter([100.0, 96.0])
    monkeypatch.setattr(mt, "openrouter_balance", lambda: next(balances))
    rc = mt.main(
        ["--models", "vendor/bad,vendor/m2", "--cost-cap", "3", "--n-tasks", "1", "--force"]
    )
    assert rc == 1
    assert benched == []  # m2 blocked by the FAILED model's counted spend


def test_cohort_budget_survives_unknown_spend(monkeypatch, tmp_path):
    """Unknown spend (balance unreadable) doesn't add to the tally and doesn't crash."""
    _seed_main_db(tmp_path, ["vendor/m1", "vendor/m2"])
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mt.shutil, "which", lambda x: "/usr/bin/tb")
    benched = []
    monkeypatch.setattr(mt, "bench_model", lambda conn, m, **k: benched.append(m) or 50.0)
    monkeypatch.setattr(
        mt, "openrouter_balance", lambda: (_ for _ in ()).throw(mt.httpx.HTTPError("down"))
    )
    rc = mt.main(
        ["--models", "vendor/m1,vendor/m2", "--cost-cap", "2", "--n-tasks", "1", "--force"]
    )
    assert rc == 0
    assert benched == ["vendor/m1", "vendor/m2"]  # no cap trip, no crash


def test_one_model_failure_does_not_kill_cohort(monkeypatch, tmp_path):
    """A single model's failure (tb error / malformed output) is skipped; others run."""
    _seed_main_db(tmp_path, ["vendor/bad", "vendor/good"])
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mt.shutil, "which", lambda x: "/usr/bin/tb")
    monkeypatch.setattr(mt, "openrouter_balance", lambda: 100.0)  # spent 0
    benched = []

    def fake_bench(conn, m, **k):
        if m == "vendor/bad":
            raise ValueError("malformed results.json")  # parse-error class
        benched.append(m)
        return 60.0

    monkeypatch.setattr(mt, "bench_model", fake_bench)
    rc = mt.main(
        ["--models", "vendor/bad,vendor/good", "--cost-cap", "9", "--n-tasks", "1", "--force"]
    )
    assert rc == 0
    assert benched == ["vendor/good"]


def test_all_models_fail_returns_nonzero(monkeypatch, tmp_path):
    """If a non-empty cohort produces 0 scores, the run reports failure (exit 1),
    not a misleading success."""
    import subprocess as _sp

    _seed_main_db(tmp_path, ["vendor/a", "vendor/b"])
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mt.shutil, "which", lambda x: "/usr/bin/tb")
    monkeypatch.setattr(mt, "openrouter_balance", lambda: 100.0)
    monkeypatch.setattr(
        mt,
        "bench_model",
        lambda conn, m, **k: (_ for _ in ()).throw(_sp.CalledProcessError(1, ["tb"])),
    )
    rc = mt.main(["--models", "vendor/a,vendor/b", "--cost-cap", "9", "--n-tasks", "1", "--force"])
    assert rc == 1


@pytest.mark.parametrize(
    "args",
    [
        ["--cost-cap", "0"],
        ["--cost-cap", "-1"],
        ["--agent-timeout", "0"],
        ["--agent-timeout", "-5"],
        ["--run-timeout", "0"],
        ["--run-timeout", "-2"],
    ],
)
def test_nonpositive_numeric_flags_return_2(args, tmp_path, monkeypatch):
    """Invalid numeric caps/timeouts surface as a clean config error (exit 2) up front,
    not masked as 'all models failed' (a bad timeout makes every tb run TimeoutExpired)."""
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")  # unused — guard fires before DB open
    called = {"bench": False}
    monkeypatch.setattr(mt, "bench_model", lambda *a, **k: called.__setitem__("bench", True))
    rc = mt.main(["--models", "vendor/m1", *args])
    assert rc == 2
    assert called["bench"] is False


def test_missing_tb_binary_returns_2(monkeypatch, tmp_path):
    """A missing tb binary is an infra error (exit 2), not masked as benign skips."""
    _seed_main_db(tmp_path, ["vendor/m1"])
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mt.shutil, "which", lambda x: None)  # tb not installed
    rc = mt.main(["--models", "vendor/m1", "--n-tasks", "1", "--force"])
    assert rc == 2


def test_bench_model_returns_score_and_writes(monkeypatch, tmp_path):
    """A FULL run (task_ids AND n_tasks both None) runs → parses → writes the
    aggregate → returns the float score (cost is the caller's concern now, so
    bench_model no longer reads the balance). run_one returns the run-id string;
    parse + persist are scoped to it."""
    conn = _mkdb(tmp_path)
    conn.execute("INSERT INTO agents (id, status) VALUES ('vendor/m1','active')")
    conn.commit()
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(mt, "run_one", lambda *a, **k: "RID")
    monkeypatch.setattr(mt, "parse_tbench_output", lambda *a, **k: 42.0)
    monkeypatch.setattr(mt, "persist_task_results", lambda *a, **k: 0)  # own tests cover it
    score = mt.bench_model(
        conn,
        "vendor/m1",
        dataset=mt.TB_DATASET,
        n_tasks=None,
        task_ids=None,
        n_concurrent=1,
        n_attempts=1,
    )
    assert score == 42.0
    assert (
        conn.execute("SELECT tbench_accuracy FROM agents WHERE id='vendor/m1'").fetchone()[0]
        == 42.0
    )


def test_bench_model_subset_does_not_write_aggregate(monkeypatch, tmp_path):
    """A SUBSET run (n_tasks set, or a --category task_ids list) must NOT overwrite
    the aggregate tbench_accuracy — a partial pass-rate is not the overall score.
    It still returns the score (for the caller) and persists per-task detail."""
    conn = _mkdb(tmp_path)
    conn.execute(
        "INSERT INTO agents (id, status, tbench_accuracy) VALUES ('vendor/m1','active', 88.0)"
    )
    conn.commit()
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(mt, "run_one", lambda *a, **k: "RID")
    monkeypatch.setattr(mt, "parse_tbench_output", lambda *a, **k: 12.0)
    persisted = {"called": False}
    monkeypatch.setattr(
        mt, "persist_task_results", lambda *a, **k: persisted.__setitem__("called", True) or 0
    )
    score = mt.bench_model(
        conn,
        "vendor/m1",
        dataset=mt.TB_DATASET,
        n_tasks=5,  # subset → aggregate must stay untouched
        task_ids=None,
        n_concurrent=1,
        n_attempts=1,
    )
    assert score == 12.0  # returned to the caller
    assert persisted["called"] is True  # per-task detail still persisted
    # aggregate column UNTOUCHED — still the prior full-run score, not the subset's 12.0
    assert (
        conn.execute("SELECT tbench_accuracy FROM agents WHERE id='vendor/m1'").fetchone()[0]
        == 88.0
    )


def test_stale_score_not_written_on_empty_rerun(monkeypatch, tmp_path):
    """A --force re-run that produces NO results.json must not persist a prior score.
    --force wipes out_dir, so the stale 0.99 is gone and parse raises rather than
    silently writing someone else's number over the real 77.0.

    (Without --force a COMPLETED run in this dir is now deliberately REUSED — same model,
    same config, so its score is valid and re-running it would just re-spend credit. That
    path is covered by test_bench_model_reuses_a_completed_run_without_spending.)"""
    conn = _mkdb(tmp_path)
    conn.execute(
        "INSERT INTO agents (id, via_openrouter, status, has_tools, tbench_accuracy) "
        "VALUES ('vendor/m1',1,'active',1, 77.0)"
    )
    conn.commit()
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    out = mt.out_dir_for("vendor/m1", mt.TB_DATASET, None)
    # A STALE prior run WITH a score. --force WIPES out_dir, so this must be unreachable.
    stale = out / "2020-01-01__00-00-00-000000"
    stale.mkdir(parents=True)
    (stale / "results.json").write_text(json.dumps({"accuracy": 0.99}))
    # The forced fresh run yields a run-id whose dir holds no results.json.
    monkeypatch.setattr(mt, "run_one", lambda *a, **k: "FRESH")
    with pytest.raises(FileNotFoundError):
        mt.bench_model(
            conn,
            "vendor/m1",
            dataset=mt.TB_DATASET,
            n_tasks=None,
            task_ids=None,
            n_concurrent=1,
            n_attempts=1,
            force=True,  # wipes → the stale 0.99 cannot be read
        )
    # the stale 0.99 was never read — the real prior aggregate stands
    assert (
        conn.execute("SELECT tbench_accuracy FROM agents WHERE id='vendor/m1'").fetchone()[0]
        == 77.0
    )


# --- Behavior 3: pass-rate parse correct -------------------------------------
def test_parse_tbench_output(tmp_path):
    run = tmp_path / "2026-07-13__run"
    run.mkdir()
    (run / "results.json").write_text(FIXTURE.read_text())
    # fixture accuracy = 1.0 → 100.0
    assert mt.parse_tbench_output(tmp_path) == 100.0


def test_parse_tbench_output_partial(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "results.json").write_text(
        json.dumps({"accuracy": 0.643, "n_resolved": 57, "n_unresolved": 32})
    )
    assert mt.parse_tbench_output(tmp_path) == pytest.approx(64.3)


@pytest.mark.parametrize("bad", [{"data": None}, {"data": {}}, {}, "not-a-dict"])
def test_balance_or_none_degrades_on_schema_drift(bad, monkeypatch):
    """_balance_or_none must NEVER crash the cohort (it runs in main's finally) — any
    OpenRouter schema drift (data:null, missing keys, non-dict) degrades to None."""

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return bad

    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setattr(mt.httpx, "get", lambda *a, **k: _Resp())
    assert mt._balance_or_none() is None  # graceful, no exception


def test_parse_tbench_output_malformed_raises_valueerror(tmp_path):
    """A present-but-malformed results.json → ValueError (a MODEL_FAILURE the
    cohort loop catches), never an uncaught JSONDecodeError/KeyError crash."""
    run = tmp_path / "run"
    run.mkdir()
    (run / "results.json").write_text("{not json")
    with pytest.raises(ValueError):
        mt.parse_tbench_output(tmp_path)
    (run / "results.json").write_text(json.dumps({"no_accuracy_key": 1}))
    with pytest.raises(ValueError):
        mt.parse_tbench_output(tmp_path)


def test_parse_tbench_output_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        mt.parse_tbench_output(tmp_path)


# --- Behavior 4: DB writeback touches only the score column ------------------
def test_write_tbench_score_updates_only_that_column(tmp_path):
    conn = _mkdb(tmp_path)
    conn.execute("INSERT INTO agents (id, arena_elo, status) VALUES ('vendor/m1', 1500, 'active')")
    conn.commit()
    mt.write_tbench_score(conn, "vendor/m1", 64.3)
    row = conn.execute(
        "SELECT tbench_accuracy, last_verified, arena_elo, status FROM agents WHERE id='vendor/m1'"
    ).fetchone()
    assert row[0] == 64.3
    assert row[1] == date.today().isoformat()
    assert row[2] == 1500  # untouched
    assert row[3] == "active"  # untouched


# --- Behavior 5: --dry-run calls no model ------------------------------------
def test_dry_run_calls_no_model(monkeypatch, tmp_path):
    # Use the real DB_PATH (not a monkeypatched singleton connect): main opens its own
    # conn AND the migration opens+closes one — a shared fake conn would be closed under
    # main. _seed_main_db writes a real t.db.
    _seed_main_db(tmp_path, ["vendor/m1"])
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mt.shutil, "which", lambda x: "/usr/bin/tb")
    called = {"run": False, "bal": False}
    monkeypatch.setattr(mt, "run_one", lambda *a, **k: called.__setitem__("run", True))
    monkeypatch.setattr(mt, "openrouter_balance", lambda: called.__setitem__("bal", True) or 100.0)
    rc = mt.main(["--models", "vendor/m1", "--dry-run"])
    assert rc == 0
    assert called["run"] is False
    assert called["bal"] is False


# --- Behavior 6: cohort selection --------------------------------------------
def test_default_cohort_is_tool_capable_or_models(tmp_path):
    conn = _mkdb(tmp_path)
    conn.executemany(
        "INSERT INTO agents (id, via_openrouter, status, has_tools) VALUES (?,?,?,?)",
        [
            ("a/tool-or", 1, "active", 1),  # in
            ("b/no-tools", 1, "active", 0),  # out (no tools)
            ("c/not-or", 0, "active", 1),  # out (not OR)
            ("d/inactive", 1, "discarded", 1),  # out (inactive)
        ],
    )
    conn.commit()
    assert mt.select_cohort(conn, None) == ["a/tool-or"]


def test_models_flag_overrides(tmp_path):
    conn = _mkdb(tmp_path)
    assert mt.select_cohort(conn, ["x/y", "z/w"]) == ["x/y", "z/w"]


def test_explicit_models_bad_id_returns_2_not_traceback(monkeypatch, tmp_path):
    """A malformed --models id surfaces as a clean config error (exit 2) — same as
    the DB path — not an uncaught ValueError traceback. (Validation is unified in
    main; select_cohort no longer validates.)"""
    _seed_main_db(tmp_path, ["vendor/ok"])
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mt.shutil, "which", lambda x: "/usr/bin/tb")
    called = {"bench": False}
    monkeypatch.setattr(mt, "bench_model", lambda *a, **k: called.__setitem__("bench", True))
    rc = mt.main(["--models", "bad; rm", "--n-tasks", "1", "--force"])
    assert rc == 2
    assert called["bench"] is False


def test_noncatalog_model_id_returns_2_before_spending(monkeypatch, tmp_path):
    """A --models id not present in the agents catalog fails up front (exit 2) —
    never benches (write_tbench_score would silently no-op + waste credit)."""
    _seed_main_db(tmp_path, ["vendor/real"])
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mt.shutil, "which", lambda x: "/usr/bin/tb")
    called = {"bench": False}
    monkeypatch.setattr(mt, "bench_model", lambda *a, **k: called.__setitem__("bench", True))
    rc = mt.main(["--models", "vendor/not-in-catalog", "--n-tasks", "1", "--force"])
    assert rc == 2
    assert called["bench"] is False  # failed before spending any credit


def test_dry_run_rejects_malformed_id(monkeypatch, tmp_path):
    """Validation runs BEFORE the dry-run block, so even a preview refuses a bad id
    (exit 2) rather than printing it and exiting 0."""
    _seed_main_db(tmp_path, ["vendor/ok"])
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    rc = mt.main(["--models", "bad|id", "--dry-run"])
    assert rc == 2


def test_cohort_deduped(monkeypatch, tmp_path):
    """`--models m,m` benches m ONCE (dedup) — never double-runs + double-charges."""
    _seed_main_db(tmp_path, ["vendor/m1"])
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mt.shutil, "which", lambda x: "/usr/bin/tb")
    monkeypatch.setattr(mt, "openrouter_balance", lambda: 100.0)
    benched = []
    monkeypatch.setattr(mt, "bench_model", lambda conn, m, **k: benched.append(m) or 50.0)
    rc = mt.main(
        ["--models", "vendor/m1,vendor/m1", "--cost-cap", "9", "--n-tasks", "1", "--force"]
    )
    assert rc == 0
    assert benched == ["vendor/m1"]  # deduped — benched once, not twice


def test_all_keyword_any_case_or_mixed_selects_full_cohort(monkeypatch, tmp_path):
    """'all' (any case, or mixed with explicit ids) means the full tool-capable
    OR cohort — never a literal model named 'all'/'All'."""
    seed = _mkdb(tmp_path)  # creates tmp_path/t.db
    seed.executemany(
        "INSERT INTO agents (id, via_openrouter, status, has_tools) VALUES (?,1,'active',1)",
        [("a/x",), ("b/y",)],
    )
    seed.commit()
    seed.close()
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")  # main() opens/closes this real file
    monkeypatch.setattr(mt.shutil, "which", lambda x: "/usr/bin/tb")
    seen = {}
    monkeypatch.setattr(
        mt, "bench_model", lambda conn, m, **k: seen.setdefault("models", []).append(m) or 1.0
    )
    monkeypatch.setattr(mt, "openrouter_balance", lambda: 100.0)
    for arg in ("all", "All", "a/x,ALL"):
        seen["models"] = []
        mt.main(["--models", arg, "--n-tasks", "1", "--force", "--cost-cap", "99"])
        assert set(seen["models"]) == {"a/x", "b/y"}, f"{arg!r} should select full cohort"


# --- Behavior 7: freshness gate (tbench_accuracy presence, NOT last_verified) -
def test_is_fresh_uses_tbench_not_last_verified(tmp_path):
    conn = _mkdb(tmp_path)
    today = date.today().isoformat()
    # benched: has a tbench score → fresh (skip)
    conn.execute(
        "INSERT INTO agents (id, tbench_accuracy, last_verified) VALUES ('benched/m', 64.3, ?)",
        (today,),
    )
    # never benched but recent last_verified (the price-scraper overload case) → NOT fresh
    conn.execute(
        "INSERT INTO agents (id, tbench_accuracy, last_verified) VALUES ('unbenched/m', NULL, ?)",
        (today,),
    )
    conn.commit()
    assert mt.is_fresh(conn, "benched/m") is True
    assert mt.is_fresh(conn, "unbenched/m") is False  # recent last_verified must NOT mark it fresh
    assert mt.is_fresh(conn, "absent/m") is False


# ============================================================================
# Granular features: category subset · resume · per-task persistence · report
# ============================================================================
import add_tbench_task_results_table as mig  # noqa: E402


def _mkdb_full(tmp_path):
    """agents table + the per-task results table (for the granular tests)."""
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute(
        "CREATE TABLE agents (id TEXT PRIMARY KEY, via_openrouter INTEGER, status TEXT, "
        "has_tools INTEGER, tbench_accuracy REAL, last_verified TEXT)"
    )
    conn.commit()
    mig.ensure_tbench_task_results_table(tmp_path / "t.db")
    return conn


def _fake_dataset(tmp_path, monkeypatch, tasks):
    """Build a fake tb dataset dir (task_id → {category,difficulty}) + point the
    runner's _dataset_dir at it. tasks = {tid: (category, difficulty)}."""
    ds = tmp_path / "ds"
    for tid, (cat, diff) in tasks.items():
        d = ds / tid
        d.mkdir(parents=True)
        (d / "task.yaml").write_text(f"instruction: x\ncategory: {cat}\ndifficulty: {diff}\n")
    monkeypatch.setattr(mt, "_dataset_dir", lambda dataset: ds)
    return ds


# --- migration idempotency ---------------------------------------------------
def test_migration_idempotent(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.close()
    assert mig.ensure_tbench_task_results_table(tmp_path / "t.db") is True  # created
    assert mig.ensure_tbench_task_results_table(tmp_path / "t.db") is False  # already present


# --- category → task ids -----------------------------------------------------
def test_tasks_in_categories(tmp_path, monkeypatch):
    _fake_dataset(
        tmp_path,
        monkeypatch,
        {
            "fix-perms": ("system-administration", "easy"),
            "crack-hash": ("security", "medium"),
            "train-net": ("model-training", "hard"),
        },
    )
    assert mt.tasks_in_categories("ds", ["system-administration", "security"]) == [
        "crack-hash",
        "fix-perms",
    ]
    assert mt.tasks_in_categories("ds", ["model-training"]) == ["train-net"]
    assert mt.tasks_in_categories("ds", ["nonexistent"]) == []


def test_load_task_meta_missing_dataset_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(mt, "_dataset_dir", lambda d: tmp_path / "does-not-exist")
    assert mt.load_task_meta("x") == {}


# --- resume detection --------------------------------------------------------
def test_find_resumable_run(tmp_path):
    out = tmp_path / "tb_run_x"
    assert mt._find_resumable_run(out) is None  # no dir
    (out / "2026-01-01__run").mkdir(parents=True)
    assert mt._find_resumable_run(out) is None  # dir but no tb.lock
    (out / "2026-01-01__run" / "tb.lock").write_text("{}")
    (out / "2026-01-02__run").mkdir()
    (out / "2026-01-02__run" / "tb.lock").write_text("{}")
    assert mt._find_resumable_run(out) == "2026-01-02__run"  # newest with a lock


def _fake_tb(out: Path, captured: dict, *, creates_run_dir: bool = True):
    """Stand-in for the `tb` binary: records argv and — like real tb — creates
    <out>/<run-id> for the --run-id it was handed (harness.py:182)."""

    def _run(argv, **kwargs):
        captured["argv"] = argv
        if creates_run_dir and "--run-id" in argv:
            rid = argv[argv.index("--run-id") + 1]
            (out / rid).mkdir(parents=True, exist_ok=True)

    return _run


def test_run_one_resumes_and_returns_the_prior_run_id(monkeypatch, tmp_path):
    out = tmp_path / "tb_run_x"
    (out / "R1").mkdir(parents=True)
    (out / "R1" / "tb.lock").write_text("{}")
    captured = {}
    monkeypatch.setattr(mt.subprocess, "run", _fake_tb(out, captured))
    run_id = mt.run_one("vendor/m", out, resume=True)
    assert captured["argv"][:3] == ["tb", "runs", "resume"]
    assert "R1" in captured["argv"]
    assert run_id == "R1"  # the caller scopes parse/persist to the RESUMED run


def test_run_one_fresh_returns_the_run_id_it_handed_tb(monkeypatch, tmp_path):
    """A fresh run HANDS tb an explicit --run-id and returns exactly that id, so
    parse/persist scope to this run by construction — no dir guessing."""
    out = tmp_path / "tb_run_x"
    captured = {}
    monkeypatch.setattr(mt.subprocess, "run", _fake_tb(out, captured))
    run_id = mt.run_one("vendor/m", out, resume=True, task_ids=["fix-perms"])
    argv = captured["argv"]
    assert argv[:2] == ["tb", "run"]
    assert "-t" in argv and "fix-perms" in argv
    assert argv[argv.index("--run-id") + 1] == run_id  # returned id IS the one tb got
    assert (out / run_id).is_dir()


def test_fresh_run_never_attributes_a_stale_sibling_run(monkeypatch, tmp_path):
    """An out_dir holding an OLD run's dir must never have that old id returned for a
    fresh run. The pre-fix newest-by-mtime guess could; the run-id is an INPUT now."""
    out = tmp_path / "tb_run_x"
    stale = out / "2020-01-01__00-00-00-000000"
    stale.mkdir(parents=True)
    (stale / "results.json").write_text(json.dumps({"accuracy": 0.99}))
    captured = {}
    monkeypatch.setattr(mt.subprocess, "run", _fake_tb(out, captured))
    run_id = mt.run_one("vendor/m", out, resume=False)
    assert run_id != stale.name
    assert (out / run_id).is_dir()


def test_run_one_returns_none_when_tb_creates_no_run_dir(monkeypatch, tmp_path):
    """tb exiting 0 without creating its run dir produced nothing → None, which
    bench_model turns into a per-model failure instead of reading another run."""
    out = tmp_path / "tb_run_x"
    captured = {}
    monkeypatch.setattr(mt.subprocess, "run", _fake_tb(out, captured, creates_run_dir=False))
    assert mt.run_one("vendor/m", out, resume=True) is None


def test_run_one_force_never_resumes(monkeypatch, tmp_path):
    out = tmp_path / "tb_run_x"
    (out / "R1").mkdir(parents=True)
    (out / "R1" / "tb.lock").write_text("{}")
    captured = {}
    monkeypatch.setattr(mt.subprocess, "run", lambda argv, **k: captured.update(argv=argv))
    mt.run_one("vendor/m", out, resume=False)  # force path
    assert captured["argv"][:2] == ["tb", "run"]  # fresh despite the prior run


# --- per-task persistence ----------------------------------------------------
def _write_task_result(out_dir, run_id, tid, resolved, failure_mode="unset"):
    d = out_dir / run_id / tid / f"{tid}.1-of-1.{run_id}"
    d.mkdir(parents=True)
    (out_dir / run_id).mkdir(exist_ok=True)
    (out_dir / run_id / "results.json").write_text(json.dumps({"accuracy": 0.5}))
    (d / "results.json").write_text(
        json.dumps(
            {
                "task_id": tid,
                "is_resolved": resolved,
                "failure_mode": failure_mode,
                "trial_started_at": "2026-07-13T10:00:00+00:00",
                "trial_ended_at": "2026-07-13T10:05:00+00:00",
            }
        )
    )


def test_persist_task_results_joins_category(tmp_path, monkeypatch):
    conn = _mkdb_full(tmp_path)
    out = tmp_path / "tb_run_vendor_m"
    _write_task_result(out, "RID", "fix-perms", True)
    _write_task_result(out, "RID", "crack-hash", False, "agent_timeout")
    meta = {
        "fix-perms": {"category": "system-administration", "difficulty": "easy"},
        "crack-hash": {"category": "security", "difficulty": "medium"},
    }
    n = mt.persist_task_results(conn, "vendor/m", out, "ds==1", "RID", meta)
    assert n == 2
    rows = dict(
        conn.execute(
            "SELECT task_id, category||'/'||is_resolved||'/'||COALESCE(failure_mode,'') "
            "FROM tbench_task_results WHERE model_id='vendor/m'"
        ).fetchall()
    )
    assert rows["fix-perms"] == "system-administration/1/unset"
    assert rows["crack-hash"] == "security/0/agent_timeout"
    # duration computed (5 min = 300s)
    dur = conn.execute(
        "SELECT duration_s FROM tbench_task_results WHERE task_id='fix-perms'"
    ).fetchone()[0]
    assert dur == 300.0


def test_persist_task_results_idempotent(tmp_path):
    conn = _mkdb_full(tmp_path)
    out = tmp_path / "tb_run_vendor_m"
    _write_task_result(out, "RID", "fix-perms", True)
    mt.persist_task_results(conn, "vendor/m", out, "ds==1", "RID", {})
    mt.persist_task_results(conn, "vendor/m", out, "ds==1", "RID", {})  # re-run
    cnt = conn.execute(
        "SELECT COUNT(*) FROM tbench_task_results WHERE task_id='fix-perms'"
    ).fetchone()[0]
    assert cnt == 1  # INSERT OR REPLACE — no dup


# --- report ------------------------------------------------------------------
def test_report_matrix(tmp_path, capsys):
    conn = _mkdb_full(tmp_path)
    conn.executemany(
        "INSERT INTO tbench_task_results (model_id, task_id, dataset, category, is_resolved) "
        "VALUES (?,?,?,?,?)",
        [
            ("vendor/m", "t1", "d", "system-administration", 1),
            ("vendor/m", "t2", "d", "system-administration", 0),
            ("vendor/m", "t3", "d", "security", 1),
        ],
    )
    conn.commit()
    mt.report_matrix(conn, "vendor/m")
    out = capsys.readouterr().out
    assert "system-administration" in out and "security" in out
    assert "50%" in out  # 1/2 sysadmin
    assert "OVERALL: 2/3" in out


def test_report_empty(tmp_path, capsys):
    conn = _mkdb_full(tmp_path)
    mt.report_matrix(conn)
    assert "no per-task results" in capsys.readouterr().out


# --- Scope key: a resume is only safe across the SAME (model, dataset, task-set) ---
def test_out_dir_isolates_datasets(monkeypatch, tmp_path):
    """`tb runs resume` reads the dataset from the ORIGINAL tb.lock and ignores
    --dataset. If the out_dir key omitted the dataset, re-running the same model on a
    NEW dataset would resume the OLD one while persisting rows labelled with the new
    dataset name — rows attributed to a dataset that was never benched. Different
    dataset ⇒ different dir ⇒ fresh run."""
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    a = mt.out_dir_for("vendor/m", "terminal-bench-core==0.1.1", None)
    b = mt.out_dir_for("vendor/m", "terminal-bench-core==0.2.0", None)
    assert a != b
    # ...and the same (model, dataset, scope) is STABLE, or nothing could ever resume
    assert a == mt.out_dir_for("vendor/m", "terminal-bench-core==0.1.1", None)


def test_out_dir_isolates_subset_from_full_run(monkeypatch, tmp_path):
    """A --category subset must not resume (and thus re-run) the full set's dir."""
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    full = mt.out_dir_for("vendor/m", mt.TB_DATASET, None)
    subset = mt.out_dir_for("vendor/m", mt.TB_DATASET, ["fix-perms", "crack-hash"])
    assert full != subset
    # order-independent: the same task SET is the same scope
    assert subset == mt.out_dir_for("vendor/m", mt.TB_DATASET, ["crack-hash", "fix-perms"])


def test_empty_task_ids_is_the_same_scope_as_a_full_run(monkeypatch, tmp_path):
    """`[]` means 'no task filter' — it must not be a THIRD scope distinct from None,
    or a caller passing [] would run the full set into its own orphan dir."""
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    assert mt.out_dir_for("vendor/m", mt.TB_DATASET, []) == mt.out_dir_for(
        "vendor/m", mt.TB_DATASET, None
    )


def test_empty_task_ids_still_writes_the_aggregate(monkeypatch, tmp_path):
    """bench_model normalizes [] → None, so an empty list behaves as the FULL run it
    dispatches (rather than building a full-set argv but skipping the aggregate write
    because `[] is None` is False)."""
    conn = _mkdb(tmp_path)
    conn.execute("INSERT INTO agents (id, status) VALUES ('vendor/m1','active')")
    conn.commit()
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(mt, "run_one", lambda *a, **k: "RID")
    monkeypatch.setattr(mt, "parse_tbench_output", lambda *a, **k: 42.0)
    monkeypatch.setattr(mt, "persist_task_results", lambda *a, **k: 0)
    mt.bench_model(
        conn,
        "vendor/m1",
        dataset=mt.TB_DATASET,
        n_tasks=None,
        task_ids=[],  # empty == no filter == a full run
        n_concurrent=1,
        n_attempts=1,
    )
    assert (
        conn.execute("SELECT tbench_accuracy FROM agents WHERE id='vendor/m1'").fetchone()[0]
        == 42.0
    )


def test_n_tasks_bounds_a_category_subset(monkeypatch, tmp_path):
    """--n-tasks is documented as the per-model spend bound, but tb only honours it
    when no -t list is passed — so `--category X --n-tasks 5` silently ran the WHOLE
    category (an uncapped spend the operator believed was bounded). main must bound
    the subset itself."""
    _seed_main_db(tmp_path, ["vendor/m1"])
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mt.shutil, "which", lambda x: "/usr/bin/tb")
    monkeypatch.setattr(mt, "openrouter_balance", lambda: 100.0)
    monkeypatch.setattr(
        mt, "tasks_in_categories", lambda ds, cats: ["t1", "t2", "t3", "t4", "t5", "t6"]
    )
    seen = {}
    monkeypatch.setattr(
        mt, "bench_model", lambda conn, m, **k: seen.update(task_ids=k["task_ids"]) or 50.0
    )
    rc = mt.main(
        ["--models", "vendor/m1", "--category", "security", "--n-tasks", "2", "--cost-cap", "5"]
    )
    assert rc == 0
    assert seen["task_ids"] == ["t1", "t2"]  # bounded to 2, not all 6


def test_n_tasks_run_never_resumes_the_full_runs_dir(monkeypatch, tmp_path):
    """`tb runs resume` re-runs the ORIGINAL run's task set and ignores the resuming
    invocation's flags. So `--n-tasks 5` (task_ids is None) MUST NOT land in the full
    run's dir — it would find the full run's lock, resume it, and re-run the ENTIRE
    task set: the operator asked for a bounded 5-task check and paid for a full run."""
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    full = mt.out_dir_for("vendor/m", mt.TB_DATASET, None, None)
    bounded = mt.out_dir_for("vendor/m", mt.TB_DATASET, None, 5)
    assert full != bounded
    # a different bound is again its own scope; the same bound is stable (resumable)
    assert bounded != mt.out_dir_for("vendor/m", mt.TB_DATASET, None, 10)
    assert bounded == mt.out_dir_for("vendor/m", mt.TB_DATASET, None, 5)


def test_bench_model_n_tasks_gets_its_own_dir(monkeypatch, tmp_path):
    """End-to-end: bench_model threads n_tasks into the scope, so a bounded run and a
    full run of the same model never share an out_dir (and so never resume each other)."""
    conn = _mkdb(tmp_path)
    conn.execute("INSERT INTO agents (id, status) VALUES ('vendor/m1','active')")
    conn.commit()
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(mt, "parse_tbench_output", lambda *a, **k: 1.0)
    monkeypatch.setattr(mt, "persist_task_results", lambda *a, **k: 0)
    seen = []
    monkeypatch.setattr(mt, "run_one", lambda mid, out, **k: seen.append(out) or "RID")
    for n in (None, 5):
        mt.bench_model(
            conn,
            "vendor/m1",
            dataset=mt.TB_DATASET,
            n_tasks=n,
            task_ids=None,
            n_concurrent=1,
            n_attempts=1,
        )
    assert seen[0] != seen[1]  # full run and the 5-task run are different dirs


def test_persist_loads_meta_itself_when_not_given(tmp_path, monkeypatch):
    """meta=None must lazy-load from disk. This is the whole point of loading AFTER the
    run (tb downloads the dataset DURING the first run), and nothing covered it — the
    bench_model tests monkeypatch persist away entirely."""
    conn = _mkdb_full(tmp_path)
    out = tmp_path / "tb_run_vendor_m"
    _write_task_result(out, "RID", "fix-perms", True)
    monkeypatch.setattr(
        mt,
        "load_task_meta",
        lambda ds: {"fix-perms": {"category": "system-administration", "difficulty": "easy"}},
    )
    n = mt.persist_task_results(conn, "vendor/m", out, "ds==1", "RID")  # no meta arg
    assert n == 1
    row = conn.execute(
        "SELECT category, difficulty FROM tbench_task_results WHERE task_id='fix-perms'"
    ).fetchone()
    assert row == ("system-administration", "easy")  # the lazy-loaded meta was joined


def test_earned_score_survives_a_persist_blowup(monkeypatch, tmp_path):
    """The score cost real credit. A failure in the OPTIONAL per-task detail write —
    including a non-sqlite one from load_task_meta reading the dataset off disk — must
    not discard it or abort the cohort."""
    conn = _mkdb(tmp_path)
    conn.execute("INSERT INTO agents (id, status) VALUES ('vendor/m1','active')")
    conn.commit()
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(mt, "run_one", lambda *a, **k: "RID")
    monkeypatch.setattr(mt, "parse_tbench_output", lambda *a, **k: 42.0)
    monkeypatch.setattr(
        mt,
        "persist_task_results",
        lambda *a, **k: (_ for _ in ()).throw(OSError("dataset dir vanished mid-glob")),
    )
    score = mt.bench_model(
        conn,
        "vendor/m1",
        dataset=mt.TB_DATASET,
        n_tasks=None,
        task_ids=None,
        n_concurrent=1,
        n_attempts=1,
    )
    assert score == 42.0  # returned, not lost
    assert (
        conn.execute("SELECT tbench_accuracy FROM agents WHERE id='vendor/m1'").fetchone()[0]
        == 42.0  # and the aggregate is persisted
    )


def test_n_attempts_and_agent_timeout_are_in_the_resume_scope(monkeypatch, tmp_path):
    """`tb runs resume` rebuilds the harness from tb.lock and discards EVERY flag of the
    resuming invocation (cli/tb/runs.py:793-804). So any knob that changes RESULTS must
    key the dir, or asking for it silently gets the locked-in old value:
      --n-attempts 3 over a locked n_attempts=1 run benches ONE attempt;
      --agent-timeout 1200 does not retry the timed-out tasks (they already wrote a
      results.json with failure_mode=agent_timeout, so resume counts them DONE).
    n_concurrent is NOT in the key — it changes speed, never results, so bumping it must
    still resume."""
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    base = mt.out_dir_for("vendor/m", mt.TB_DATASET, None, None, 1, 600.0)
    assert mt.out_dir_for("vendor/m", mt.TB_DATASET, None, None, 3, 600.0) != base  # n_attempts
    assert mt.out_dir_for("vendor/m", mt.TB_DATASET, None, None, 1, 1200.0) != base  # timeout
    assert mt.out_dir_for("vendor/m", mt.TB_DATASET, None, None, 1, 600.0) == base  # stable


# --- --n-tasks must be a REAL bound: a bad one must never WIDEN the run ---------
@pytest.mark.parametrize("bad", ["0", "-1"])
def test_nonpositive_n_tasks_returns_2(monkeypatch, tmp_path, bad):
    """Both bad values failed SILENTLY toward a BIGGER run, which is the dangerous
    direction (it spends credit):
      --n-tasks 0  → a --category set truncates to [], which bench_model reads as
                     'no task filter' → the FULL dataset runs;
      --n-tasks -1 → Python slice semantics ([:-1]) quietly keep len-1 tasks.
    Neither may reach a model — surface as a config error, like the other bounds."""
    _seed_main_db(tmp_path, ["vendor/m1"])
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(mt.shutil, "which", lambda x: "/usr/bin/tb")
    called = {"bench": False}
    monkeypatch.setattr(mt, "bench_model", lambda *a, **k: called.__setitem__("bench", True))
    rc = mt.main(["--models", "vendor/m1", "--category", "security", "--n-tasks", bad])
    assert rc == 2
    assert called["bench"] is False  # never dispatched, never spent


def test_task_meta_cache_does_not_pin_an_empty_read(monkeypatch, tmp_path):
    """{} means 'tb has not downloaded the dataset yet' (it fetches DURING the first
    run) — caching that would pin every later persist to a NULL category. Only a
    non-empty read is memoized, so the empty one stays retryable."""
    monkeypatch.setattr(mt, "_dataset_dir", lambda ds: tmp_path / "missing")
    assert mt.load_task_meta("ds==1") == {}
    assert "ds==1" not in mt._TASK_META_CACHE  # NOT pinned

    # dataset now on disk (as after tb's first-run download) → real read, and memoized
    d = tmp_path / "there" / "fix-perms"
    d.mkdir(parents=True)
    (d / "task.yaml").write_text("category: system-administration\ndifficulty: easy\n")
    monkeypatch.setattr(mt, "_dataset_dir", lambda ds: tmp_path / "there")
    assert mt.load_task_meta("ds==1")["fix-perms"]["category"] == "system-administration"
    assert "ds==1" in mt._TASK_META_CACHE  # now memoized


def test_inert_n_tasks_does_not_block_a_legitimate_resume(monkeypatch, tmp_path):
    """n_tasks only reaches tb when there is NO -t list, and on a subset run main has
    already folded the bound into task_ids. So with a task set the tb argv is identical
    regardless of n_tasks — and the dir must be too, or a legitimate resume is refused
    and the completed tasks are re-billed. (The mirror of letting a run resume into a
    DIFFERENT config: here we'd refuse to resume the SAME one.)"""
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    tasks = ["t1", "t2", "t3"]
    # a non-binding bound (50 and 100 both exceed the 3-task set) → same run → same dir
    a = mt.out_dir_for("vendor/m", mt.TB_DATASET, tasks, 50)
    b = mt.out_dir_for("vendor/m", mt.TB_DATASET, tasks, 100)
    c = mt.out_dir_for("vendor/m", mt.TB_DATASET, tasks, None)
    assert a == b == c
    # a FULL run (no task set) still keys on n_tasks — there it DOES reach tb
    assert mt.out_dir_for("vendor/m", mt.TB_DATASET, None, 5) != mt.out_dir_for(
        "vendor/m", mt.TB_DATASET, None, 10
    )


def test_scope_key_is_unambiguous_under_delimiter_bearing_inputs(monkeypatch, tmp_path):
    """The key's fields are operator-supplied. A raw delimiter-join could let a value
    containing the delimiter shift field boundaries and alias two DIFFERENT configs onto
    one dir (→ one run resuming the other's). The encoding must keep them distinct."""
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    assert mt.out_dir_for("vendor/m", "ds|x==1", None, None) != mt.out_dir_for(
        "vendor/m", "ds", None, None
    )
    # task ids that embed the list separator must not collide with the 2-element list
    assert mt.out_dir_for("vendor/m", mt.TB_DATASET, ["a,b"], None) != mt.out_dir_for(
        "vendor/m", mt.TB_DATASET, ["a", "b"], None
    )


# --- A FINISHED run is READ, never re-run (this bug cost real money) ------------
def test_completed_run_is_not_resumable(tmp_path):
    """tb.lock is a PERSISTENT manifest — a finished run still has one. Keying
    resumability on the lock alone is what re-dispatched a finished run's tasks and
    re-spent credit. Resumable must mean 'has work left', i.e. no top-level results.json."""
    out = tmp_path / "tb_run_x"
    done = out / "2026-07-13__16-47-35"
    done.mkdir(parents=True)
    (done / "tb.lock").write_text("{}")
    (done / "results.json").write_text(json.dumps({"accuracy": 0.338}))  # run COMPLETE
    assert mt._find_resumable_run(out) is None  # nothing to resume
    assert mt._find_complete_run(out) == "2026-07-13__16-47-35"  # but it IS readable

    # a partial run (lock, no results.json) is still resumable
    part = out / "2026-07-14__01-00-00"
    part.mkdir()
    (part / "tb.lock").write_text("{}")
    assert mt._find_resumable_run(out) == "2026-07-14__01-00-00"


def test_bench_model_reuses_a_completed_run_without_spending(monkeypatch, tmp_path):
    """The real incident: tb FINISHED the run, but the runner process was killed before
    it could write the score — so tbench_accuracy stayed NULL, the freshness guard did
    not skip the model, and the next invocation resumed a finished run and burned ~3h of
    credit for zero new results. A completed run must be parsed + persisted for $0, and
    tb must never be invoked."""
    conn = _mkdb_full(tmp_path)
    conn.execute("INSERT INTO agents (id, status) VALUES ('vendor/m1','active')")  # NULL score
    conn.commit()
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    out = mt.out_dir_for("vendor/m1", "ds==1", None, None)
    _write_task_result(out, "2026-07-13__16-47-35", "fix-perms", True)
    run = out / "2026-07-13__16-47-35"
    (run / "tb.lock").write_text("{}")
    # AFTER the helper (which writes its own top-level results.json) — this is the
    # run-complete marker carrying the real aggregate.
    (run / "results.json").write_text(json.dumps({"accuracy": 0.338}))

    spent = {"tb": False}
    monkeypatch.setattr(mt, "run_one", lambda *a, **k: spent.__setitem__("tb", True) or "NEW")

    score = mt.bench_model(
        conn,
        "vendor/m1",
        dataset="ds==1",
        n_tasks=None,
        task_ids=None,
        n_concurrent=1,
        n_attempts=1,
    )
    assert spent["tb"] is False  # tb NEVER invoked → no credit spent
    assert score == pytest.approx(33.8)
    # the score the killed process failed to write is now persisted
    assert conn.execute("SELECT tbench_accuracy FROM agents WHERE id='vendor/m1'").fetchone()[
        0
    ] == pytest.approx(33.8)
    # and so is the per-task detail
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM tbench_task_results WHERE model_id='vendor/m1'"
        ).fetchone()[0]
        == 1
    )


def test_force_still_re_benches_a_completed_run(monkeypatch, tmp_path):
    """--force must still wipe and re-run — reuse is the DEFAULT, not a trap."""
    conn = _mkdb_full(tmp_path)
    conn.execute("INSERT INTO agents (id, status) VALUES ('vendor/m1','active')")
    conn.commit()
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    out = mt.out_dir_for("vendor/m1", "ds==1", None, None)
    run = out / "OLD"
    run.mkdir(parents=True)
    (run / "tb.lock").write_text("{}")
    (run / "results.json").write_text(json.dumps({"accuracy": 0.99}))

    spent = {"tb": False}
    monkeypatch.setattr(mt, "run_one", lambda *a, **k: spent.__setitem__("tb", True) or "NEW")
    monkeypatch.setattr(mt, "parse_tbench_output", lambda *a, **k: 50.0)
    monkeypatch.setattr(mt, "persist_task_results", lambda *a, **k: 0)
    score = mt.bench_model(
        conn,
        "vendor/m1",
        dataset="ds==1",
        n_tasks=None,
        task_ids=None,
        n_concurrent=1,
        n_attempts=1,
        force=True,
    )
    assert spent["tb"] is True  # re-benched, as asked
    assert score == 50.0


def test_parse_is_scoped_to_its_run_id_not_the_newest(tmp_path):
    """Direct proof of run-id scoping: with several runs in one dir, parse(run_id) reads
    EXACTLY that run — never the newest-by-mtime, which is how a stale score used to be
    attributed to a fresh run."""
    for rid, acc in (("2020-01-01__00-00-00-000000", 0.99), ("2026-07-13__16-47-35", 0.338)):
        (tmp_path / rid).mkdir()
        (tmp_path / rid / "results.json").write_text(json.dumps({"accuracy": acc}))
    assert mt.parse_tbench_output(tmp_path, "2026-07-13__16-47-35") == pytest.approx(33.8)
    assert mt.parse_tbench_output(tmp_path, "2020-01-01__00-00-00-000000") == pytest.approx(99.0)
    with pytest.raises(FileNotFoundError):
        mt.parse_tbench_output(tmp_path, "NEVER-RAN")
