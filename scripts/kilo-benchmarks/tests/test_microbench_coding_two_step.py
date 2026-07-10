"""Phase B integration tests: 2-step (shim → evalplus offline) dispatch flow.

Behaviors from plan-3:
- B1 (TDD): _run_one populates results dir + returns 4-tuple with real cost from shim
- B2: main accumulates real spend across units → TOTAL_SPEND_USD emission
- B3: outer ThreadPoolExecutor is max_workers=1 (serial across units)
- B7: mocked-happy-path writes correct humaneval_score end-to-end

Plan: docs/development/plans/2026-07-10-plan-3-coding-microbench-completions-shim.md
"""
# AFTER-EDIT: none

from __future__ import annotations

import concurrent.futures
import io
import json
import math
import pathlib
import sqlite3
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout

import pytest

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str((SCRIPT_DIR / "libs").resolve()))

import microbench_coding  # noqa: E402
from microbench_coding import main  # noqa: E402


def _make_agents_db(tmp_path: pathlib.Path) -> pathlib.Path:
    """Minimal agents table matching Phase C's schema expectations."""
    db = tmp_path / "agents.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE agents ("
        "id TEXT PRIMARY KEY, "
        "humaneval_score REAL, "
        "coding_score REAL, "
        "weighted_coding REAL, "
        "last_verified DATE)"
    )
    conn.execute(
        "INSERT INTO agents (id) VALUES (?)", ("bytedance-seed/seed-2.0-lite",)
    )
    conn.commit()
    conn.close()
    return db


def _fake_evalplus_writes_results(
    fixture_shape: dict,
):
    """Factory for a subprocess.run mock that writes eval_results.json into cwd/results/."""

    def _run(cmd, **kw):
        cwd = pathlib.Path(kw.get("cwd", "."))
        results_dir = cwd / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "eval_results.json").write_text(json.dumps(fixture_shape))
        return subprocess.CompletedProcess(cmd, 0, b"stdout", b"")

    return _run


# ─── B7 (end-to-end): mocked happy path writes correct humaneval_score ─────────
def test_two_step_happy_path_writes_correct_scores(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B7: full happy path — mocked generate_samples returns (path, cost); mocked
    subprocess.run writes real-shape eval_results.json with 2/3 base-pass → DB row
    gets humaneval_score ≈ 66.67."""
    db = _make_agents_db(tmp_path)
    monkeypatch.setattr(microbench_coding, "DB_PATH", db)
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")

    fixture = {
        "date": "2026-07-10",
        "hash": "test",
        "eval": {
            "HumanEval/0": [{"base_status": "pass", "plus_status": "pass"}],
            "HumanEval/1": [{"base_status": "pass", "plus_status": "fail"}],
            "HumanEval/2": [{"base_status": "fail", "plus_status": "fail"}],
        },
    }

    def _fake_generate_samples(model, problems, out_path, **kw):
        p = pathlib.Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "\n".join(json.dumps({"task_id": tid, "solution": "pass\n"}) for tid in problems)
            + "\n"
        )
        return p, 0.11

    monkeypatch.setattr(
        microbench_coding.openrouter_complete, "generate_samples", _fake_generate_samples
    )
    monkeypatch.setattr(
        microbench_coding.subprocess, "run", _fake_evalplus_writes_results(fixture)
    )

    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        rc = main(
            [
                "--models",
                "bytedance-seed/seed-2.0-lite",
                "--datasets",
                "humaneval,mbpp",
            ]
        )
    assert rc == 0, stderr.getvalue()

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT humaneval_score, coding_score FROM agents WHERE id = ?",
        ("bytedance-seed/seed-2.0-lite",),
    ).fetchone()
    conn.close()
    assert row is not None
    he, cs = row
    # Fixture: 2/3 base-pass → humaneval_score = 66.67
    assert he is not None, "humaneval_score is NULL — write path broken"
    assert math.isclose(he, 66.67, abs_tol=0.5), he
    assert cs is not None

    out = stdout.getvalue()
    assert "WROTE bytedance-seed/seed-2.0-lite:" in out


# ─── B2: main accumulates real spend from shim ────────────────────────────────
def test_main_accumulates_real_spend_from_shim(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B2: 2 units × mocked cost 0.15 each → TOTAL_SPEND_USD: 0.30."""
    db = _make_agents_db(tmp_path)
    monkeypatch.setattr(microbench_coding, "DB_PATH", db)
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")

    fixture = {
        "date": "2026-07-10",
        "hash": "test",
        "eval": {"HumanEval/0": [{"base_status": "pass", "plus_status": "pass"}]},
    }

    def _fake_generate_samples(model, problems, out_path, **kw):
        p = pathlib.Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"task_id": "HumanEval/0", "solution": "pass\n"}) + "\n")
        return p, 0.15

    monkeypatch.setattr(
        microbench_coding.openrouter_complete, "generate_samples", _fake_generate_samples
    )
    monkeypatch.setattr(
        microbench_coding.subprocess, "run", _fake_evalplus_writes_results(fixture)
    )

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        rc = main(
            [
                "--models",
                "bytedance-seed/seed-2.0-lite",
                "--datasets",
                "humaneval,mbpp",
            ]
        )
    assert rc == 0
    last_line = stdout.getvalue().rstrip().splitlines()[-1]
    import re as _re

    assert _re.match(r"^TOTAL_SPEND_USD: 0\.30$", last_line), last_line


# ─── B3: outer max_workers=1 (serial) ──────────────────────────────────────────
def test_outer_dispatch_uses_max_workers_1(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B3: verify the outer ThreadPoolExecutor is instantiated with max_workers=1
    (serial across units — plan-3 residual #1 resolution; combined with shim's
    inner max_concurrency=8 this bounds OR-concurrency at 8, not 64)."""
    db = _make_agents_db(tmp_path)
    monkeypatch.setattr(microbench_coding, "DB_PATH", db)
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")

    fixture = {
        "date": "2026-07-10",
        "hash": "test",
        "eval": {"HumanEval/0": [{"base_status": "pass", "plus_status": "pass"}]},
    }

    def _fake_generate_samples(model, problems, out_path, **kw):
        p = pathlib.Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"task_id": "HumanEval/0", "solution": "pass\n"}) + "\n")
        return p, 0.05

    monkeypatch.setattr(
        microbench_coding.openrouter_complete, "generate_samples", _fake_generate_samples
    )
    monkeypatch.setattr(
        microbench_coding.subprocess, "run", _fake_evalplus_writes_results(fixture)
    )

    # Instrument ThreadPoolExecutor to capture max_workers
    seen_max_workers: list[int] = []
    original_tpe = concurrent.futures.ThreadPoolExecutor

    class _CapturingTPE(original_tpe):
        def __init__(self, *a, max_workers=None, **kw):
            seen_max_workers.append(max_workers)
            super().__init__(*a, max_workers=max_workers, **kw)

    monkeypatch.setattr(
        microbench_coding.concurrent.futures, "ThreadPoolExecutor", _CapturingTPE
    )

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        main(
            [
                "--models",
                "bytedance-seed/seed-2.0-lite",
                "--datasets",
                "humaneval,mbpp",
            ]
        )

    # main's outer pool must be max_workers=1
    assert 1 in seen_max_workers, (
        f"outer ThreadPoolExecutor not max_workers=1: got {seen_max_workers}"
    )


# ─── B1 (TDD): _run_one returns 4-tuple with real cost from shim ──────────────
def test_run_one_returns_4_tuple_with_shim_cost(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B1 (TDD-highest-risk): _run_one contract change from 3-tuple to
    (unit, ok, err, cost). Cost is the shim's returned float."""
    # We can't directly call _run_one (it's nested inside main). Instead assert
    # via the observable outcome: main's cost accumulation reflects the shim's
    # returned cost — proving _run_one propagates it.
    db = _make_agents_db(tmp_path)
    monkeypatch.setattr(microbench_coding, "DB_PATH", db)
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")

    fixture = {
        "date": "2026-07-10",
        "hash": "test",
        "eval": {"HumanEval/0": [{"base_status": "pass", "plus_status": "pass"}]},
    }

    def _fake_generate_samples(model, problems, out_path, **kw):
        p = pathlib.Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"task_id": "HumanEval/0", "solution": "pass\n"}) + "\n")
        return p, 0.42  # sentinel value

    monkeypatch.setattr(
        microbench_coding.openrouter_complete, "generate_samples", _fake_generate_samples
    )
    monkeypatch.setattr(
        microbench_coding.subprocess, "run", _fake_evalplus_writes_results(fixture)
    )

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        main(
            [
                "--models",
                "bytedance-seed/seed-2.0-lite",
                "--datasets",
                "humaneval",  # 1 unit
            ]
        )
    out = stdout.getvalue()
    # per-unit line format: `[N/M] OK|FAIL <target>/<ds> cost=$<cost>`
    assert "cost=$0.4200" in out, out
    # TOTAL_SPEND_USD reflects the 4-tuple's cost being summed
    assert "TOTAL_SPEND_USD: 0.42" in out, out
