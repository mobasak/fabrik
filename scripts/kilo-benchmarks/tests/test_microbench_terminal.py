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


# --- Behavior 2: run (cohort) budget stops the run BEFORE the next model ------
def test_cohort_budget_stops_run_before_next_model(monkeypatch, tmp_path):
    """--cost-cap is a run budget: main ACCUMULATES each model's measured spend and,
    before each model, stops once the tally reaches the cap. (Honestly NOT a
    per-model mid-flight interrupt — see the docstring.) Budget tracking uses the
    per-model spend bench_model returns, NOT a fragile global-balance re-read."""
    seed = _mkdb(tmp_path)
    seed.executemany(
        "INSERT INTO agents (id, via_openrouter, status, has_tools) VALUES (?,1,'active',1)",
        [("vendor/m1",), ("vendor/m2",)],
    )
    seed.commit()
    seed.close()
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    benched = []
    # m1 costs $3 → cohort_spent=3 >= cap 2 → m2 never dispatched.
    monkeypatch.setattr(mt, "bench_model", lambda conn, m, **k: benched.append(m) or (55.0, 3.0))
    rc = mt.main(["--models", "vendor/m1,vendor/m2", "--cost-cap", "2", "--n-tasks", "1", "--force"])
    assert rc == 1  # stopped
    assert benched == ["vendor/m1"]  # m2 never dispatched — accumulated spend stopped the run


def test_cohort_budget_survives_unknown_spend(monkeypatch, tmp_path):
    """A model whose spend is unknown (None) does not add to the tally and does NOT
    crash the accumulation — the run continues, bounded by known spends + --n-tasks."""
    seed = _mkdb(tmp_path)
    seed.executemany(
        "INSERT INTO agents (id, via_openrouter, status, has_tools) VALUES (?,1,'active',1)",
        [("vendor/m1",), ("vendor/m2",)],
    )
    seed.commit()
    seed.close()
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    benched = []
    monkeypatch.setattr(mt, "bench_model", lambda conn, m, **k: benched.append(m) or (50.0, None))
    rc = mt.main(["--models", "vendor/m1,vendor/m2", "--cost-cap", "2", "--n-tasks", "1", "--force"])
    assert rc == 0
    assert benched == ["vendor/m1", "vendor/m2"]  # unknown spend never trips the cap, no crash


def test_one_model_failure_does_not_kill_cohort(monkeypatch, tmp_path):
    """A single model's tb failure (CalledProcessError) is logged and skipped;
    the remaining models still run."""
    import subprocess as _sp

    seed = _mkdb(tmp_path)
    seed.executemany(
        "INSERT INTO agents (id, via_openrouter, status, has_tools) VALUES (?,1,'active',1)",
        [("vendor/bad",), ("vendor/good",)],
    )
    seed.commit()
    seed.close()
    monkeypatch.setattr(mt, "DB_PATH", tmp_path / "t.db")
    benched = []

    def fake_bench(conn, m, **k):
        if m == "vendor/bad":
            raise _sp.CalledProcessError(1, ["tb"])
        benched.append(m)
        return (60.0, 0.1)

    monkeypatch.setattr(mt, "bench_model", fake_bench)
    rc = mt.main(["--models", "vendor/bad,vendor/good", "--cost-cap", "9", "--n-tasks", "1", "--force"])
    assert rc == 0
    assert benched == ["vendor/good"]  # bad skipped, good still benched


def test_score_survives_balance_check_failure(monkeypatch, tmp_path):
    """core/58-resilience regression: a credits-API blip must NOT lose a
    completed, paid-for bench — the score is still written; spent is None (unknown)."""
    conn = _mkdb(tmp_path)
    conn.execute(
        "INSERT INTO agents (id, via_openrouter, status, has_tools) VALUES (?,1,'active',1)",
        ("vendor/m1",),
    )
    conn.commit()
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)

    def boom():
        raise mt.httpx.HTTPError("credits API down")

    monkeypatch.setattr(mt, "openrouter_balance", boom)
    monkeypatch.setattr(mt, "run_one", lambda *a, **k: tmp_path)
    monkeypatch.setattr(mt, "parse_tbench_output", lambda d: 48.0)
    score, spent = mt.bench_model(
        conn, "vendor/m1", dataset=mt.TB_DATASET, n_tasks=1, task_id=None, n_concurrent=1, n_attempts=1
    )
    assert score == 48.0  # score written despite balance failure
    assert spent is None  # honest "unknown", NOT 0 and NOT -1.0 (no top-up collision)
    row = conn.execute("SELECT tbench_accuracy FROM agents WHERE id='vendor/m1'").fetchone()
    assert row[0] == 48.0


def test_bench_model_reports_spend_delta(monkeypatch, tmp_path):
    conn = _mkdb(tmp_path)
    conn.execute(
        "INSERT INTO agents (id, via_openrouter, status, has_tools) VALUES (?,1,'active',1)",
        ("vendor/m1",),
    )
    conn.commit()
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    balances = iter([100.0, 99.5])  # spent 0.5
    monkeypatch.setattr(mt, "openrouter_balance", lambda: next(balances))
    monkeypatch.setattr(mt, "run_one", lambda *a, **k: tmp_path)
    monkeypatch.setattr(mt, "parse_tbench_output", lambda d: 42.0)
    score, spent = mt.bench_model(
        conn, "vendor/m1", dataset=mt.TB_DATASET, n_tasks=1, task_id=None, n_concurrent=1, n_attempts=1
    )
    assert score == 42.0
    assert round(spent, 2) == 0.5


def test_stale_score_not_written_on_empty_rerun(monkeypatch, tmp_path):
    """A --force re-run where tb writes NO fresh results.json must NOT persist the
    previous run's score — the wiped out_dir makes parse raise FileNotFoundError."""
    conn = _mkdb(tmp_path)
    conn.execute(
        "INSERT INTO agents (id, via_openrouter, status, has_tools, tbench_accuracy) "
        "VALUES ('vendor/m1',1,'active',1, 77.0)"
    )
    conn.commit()
    monkeypatch.setattr(mt, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(mt, "openrouter_balance", lambda: 100.0)  # no real network GET
    # seed a STALE prior run dir under the model's out_dir
    stale = tmp_path / "tb_run_vendor_m1" / "old-run"
    stale.mkdir(parents=True)
    (stale / "results.json").write_text(json.dumps({"accuracy": 0.99}))
    # run_one writes nothing new (simulates all-tasks-errored) — but bench_model wipes out_dir first
    monkeypatch.setattr(mt, "run_one", lambda *a, **k: k.get("out_dir") or a[1])
    with pytest.raises(FileNotFoundError):
        mt.bench_model(
            conn, "vendor/m1", dataset=mt.TB_DATASET, n_tasks=1, task_id=None,
            n_concurrent=1, n_attempts=1,
        )
    # the stale 77.0 was NOT overwritten with the old 99
    row = conn.execute("SELECT tbench_accuracy FROM agents WHERE id='vendor/m1'").fetchone()
    assert row[0] == 77.0


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
    conn = _mkdb(tmp_path)
    conn.execute(
        "INSERT INTO agents (id, via_openrouter, status, has_tools) VALUES ('vendor/m1',1,'active',1)"
    )
    conn.commit()
    monkeypatch.setattr(mt.sqlite3, "connect", lambda *a, **k: conn)
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


def test_cohort_override_validates(tmp_path):
    conn = _mkdb(tmp_path)
    with pytest.raises(ValueError):
        mt.select_cohort(conn, ["bad; rm"])


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
    seen = {}
    monkeypatch.setattr(
        mt, "bench_model", lambda conn, m, **k: seen.setdefault("models", []).append(m) or (1.0, 0.0)
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
