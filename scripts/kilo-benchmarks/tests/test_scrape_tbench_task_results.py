#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/scrape_tbench_task_results.py
"""Behavior tests for the per-task Terminal-Bench leaderboard scraper.

The shapes here are copied from REAL records fetched from the live HF dataset on
2026-07-14 — including the errored trial that a naive parser would have miscounted.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import scrape_tbench_task_results as st  # noqa: E402
from add_tbench_leaderboard_table import ensure_tbench_leaderboard_table  # noqa: E402


def _db(tmp_path):
    ensure_tbench_leaderboard_table(tmp_path / "t.db")
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("CREATE TABLE agents (id TEXT PRIMARY KEY)")
    conn.commit()
    return conn


# --- The trap the live grounding exposed: an ERROR is not a FAILURE -------------
def test_errored_trial_is_not_counted_as_a_failure():
    """A trial whose verifier never ran (docker died) has verifier_result: null. It
    measured NOTHING about the model. Counting it as a failure would silently deflate
    every model unlucky enough to hit flaky infra."""
    errored = {
        "task_name": "terminal-bench/adaptive-rejection-sampler",
        "verifier_result": None,  # <- real shape from the live dataset
        "agent_result": None,
        "exception_info": {"exception_type": "RuntimeError"},
    }
    t = st.parse_trial(errored)
    assert t["errored"] is True
    assert t["passed"] is False  # not a pass...
    # ...and the aggregation must EXCLUDE it from the denominator, not score it 0.


def test_pass_rate_excludes_errored_trials_from_the_denominator(tmp_path):
    """3 trials: 1 pass, 1 fail, 1 errored → pass_rate is 1/2 (50%), NOT 1/3 (33%)."""
    meta = {"fix-perms": {"category": "system-administration", "difficulty": "easy"}}
    sub = tmp_path / "submissions" / "terminal-bench" / "2.0" / "Agent__Model"
    (sub / "job").mkdir(parents=True)
    (sub / "metadata.yaml").write_text(
        'agent_display_name: "Agent"\nmodels:\n  - model_name: "vendor/m1"\n'
    )
    for i, vr in enumerate(
        [{"rewards": {"reward": 1.0}}, {"rewards": {"reward": 0.0}}, None]  # pass, fail, ERROR
    ):
        d = sub / "job" / f"fix-perms__{i}"
        d.mkdir()
        (d / "result.json").write_text(
            json.dumps(
                {
                    "task_name": "terminal-bench/fix-perms",
                    "source": "terminal-bench/terminal-bench-2-1",
                    "verifier_result": vr,
                    "agent_result": {"cost_usd": 1.0} if vr else None,
                }
            )
        )
    rows = st.collect(tmp_path, meta)
    assert len(rows) == 1
    r = rows[0]
    assert (r["n_trials"], r["n_passed"], r["n_errored"]) == (3, 1, 1)
    assert r["pass_rate"] == pytest.approx(0.5)  # 1 of the 2 that actually RAN
    assert r["category"] == "system-administration"  # the join that makes it a capability


def test_all_errored_yields_null_pass_rate_not_zero(tmp_path):
    """If every trial errored we learned NOTHING — that must be NULL (unknown), never 0%
    (which reads as 'the model failed')."""
    sub = tmp_path / "submissions" / "terminal-bench" / "2.0" / "A__M"
    (sub / "job" / "t__0").mkdir(parents=True)
    (sub / "metadata.yaml").write_text('agent_display_name: "A"\nmodels:\n  - model_name: "v/m"\n')
    (sub / "job" / "t__0" / "result.json").write_text(
        json.dumps({"task_name": "terminal-bench/t", "verifier_result": None})
    )
    rows = st.collect(tmp_path, {})
    assert rows[0]["pass_rate"] is None
    assert rows[0]["n_errored"] == 1


# --- Reward is NESTED (verifier_result.rewards.reward) --------------------------
def test_reward_is_read_from_the_nested_rewards_object():
    passed = st.parse_trial(
        {"task_name": "terminal-bench/x", "verifier_result": {"rewards": {"reward": 1.0}}}
    )
    failed = st.parse_trial(
        {"task_name": "terminal-bench/x", "verifier_result": {"rewards": {"reward": 0.0}}}
    )
    assert passed["passed"] is True
    assert failed["passed"] is False and failed["errored"] is False


def test_task_name_is_stripped_of_its_org_prefix():
    """'terminal-bench/configure-git-webserver' must key on 'configure-git-webserver' —
    that is what the local task.toml dirs are named, and the category join depends on it."""
    t = st.parse_trial(
        {
            "task_name": "terminal-bench/configure-git-webserver",
            "verifier_result": {"rewards": {"reward": 1.0}},
        }
    )
    assert t["task_id"] == "configure-git-webserver"


def test_cost_is_captured_from_the_agent_result():
    t = st.parse_trial(
        {
            "task_name": "terminal-bench/x",
            "verifier_result": {"rewards": {"reward": 1.0}},
            "agent_result": {"cost_usd": 1.742},
        }
    )
    assert t["cost_usd"] == pytest.approx(1.742)


# --- Mapping leaderboard model strings onto agents.id --------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("z-ai/glm-5.1", "z-ai/glm-5.1"),  # exact
        ("zai-org/GLM-5.1", "z-ai/glm-5.1"),  # different org prefix + case
        ("anthropic/claude-opus-4-7", None),  # we don't carry it → None, not a wrong guess
    ],
)
def test_model_mapping(raw, expected):
    catalog = ["z-ai/glm-5.1", "deepseek/deepseek-v4-pro"]
    assert st.map_model_id(raw, catalog) == expected


def test_unmappable_model_still_stores_its_raw_label(tmp_path):
    """A closed frontier model has no agents row. It must still be PERSISTED (model_id
    NULL, model_raw kept) — dropping it would silently shrink the leaderboard, and
    guessing a model_id would poison the per-model matrix."""
    conn = _db(tmp_path)
    rows = [
        {
            "submission": "Capy__GPT-5.5",
            "agent": "Capy",
            "model_raw": "gpt-5.5",
            "task_id": "t",
            "dataset": "d",
            "category": "security",
            "difficulty": "hard",
            "n_trials": 5,
            "n_passed": 4,
            "n_errored": 0,
            "pass_rate": 0.8,
            "avg_cost_usd": 1.2,
        }
    ]
    st.persist(conn, rows, catalog=["z-ai/glm-5.1"])
    got = conn.execute(
        "SELECT model_id, model_raw, pass_rate FROM tbench_leaderboard_results"
    ).fetchone()
    assert got == (None, "gpt-5.5", 0.8)


def test_multi_model_submission_is_not_guessed(tmp_path):
    """A submission declaring several models ('Multiple' on the real leaderboard) cannot
    have its trials attributed to one of them — recording a guess would poison the matrix."""
    sub = tmp_path / "submissions" / "terminal-bench" / "2.0" / "JJ__Multiple"
    (sub / "job" / "t__0").mkdir(parents=True)
    (sub / "metadata.yaml").write_text(
        'agent_display_name: "JJ"\nmodels:\n  - model_name: "a/x"\n  - model_name: "b/y"\n'
    )
    (sub / "job" / "t__0" / "result.json").write_text(
        json.dumps(
            {"task_name": "terminal-bench/t", "verifier_result": {"rewards": {"reward": 1.0}}}
        )
    )
    rows = st.collect(tmp_path, {})
    assert rows[0]["model_raw"] == "Multiple"


def test_persist_is_idempotent(tmp_path):
    conn = _db(tmp_path)
    row = {
        "submission": "A__M",
        "agent": "A",
        "model_raw": "v/m",
        "task_id": "t",
        "dataset": "d",
        "category": "security",
        "difficulty": "hard",
        "n_trials": 5,
        "n_passed": 3,
        "n_errored": 0,
        "pass_rate": 0.6,
        "avg_cost_usd": 0.5,
    }
    st.persist(conn, [row], ["v/m"])
    st.persist(conn, [row], ["v/m"])  # re-scrape
    assert conn.execute("SELECT COUNT(*) FROM tbench_leaderboard_results").fetchone()[0] == 1


def test_load_task_meta_reads_toml_not_yaml(tmp_path):
    """TB 2.x ships task.toml (the legacy 1.x set used task.yaml) — reading the wrong
    format would leave every category NULL, which is the whole value of this scraper."""
    d = tmp_path / "configure-git-webserver"
    d.mkdir()
    (d / "task.toml").write_text(
        '[metadata]\ncategory = "system-administration"\ndifficulty = "hard"\n'
    )
    meta = st.load_task_meta(tmp_path)
    assert meta["configure-git-webserver"] == {
        "category": "system-administration",
        "difficulty": "hard",
    }
