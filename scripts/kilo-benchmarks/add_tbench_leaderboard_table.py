#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/scrape_tbench_task_results.py
"""Idempotent schema addition: per-(submission, task) results SCRAPED from the public
Terminal-Bench 2.x leaderboard.

Deliberately a SEPARATE table from ``tbench_task_results`` (which holds OUR OWN runs):

- **Different key.** A leaderboard row is a *submission* = (agent + model). The same model
  appears under several agents/harnesses, and each task is run k times (k=5 is the
  submission requirement) — so the natural unit is a per-task PASS-RATE over k trials, not
  our single boolean ``is_resolved``.
- **Different provenance.** These are third-party measurements under someone else's
  harness. Folding them into the table that holds our measurements would make one table
  mean two things, and no gate would ever compare them — the exact "second source of
  truth" decay Lesson 92 is about. Keep them adjacent and clearly labelled instead.

Why scrape at all: the aggregate leaderboard score hides the category profile, which is the
only thing that matters when hiring a model for a ROLE. minimax-m3 scored 34% overall and
15% at system-administration. Joining the public per-task results against each task's
``task.toml`` category gives that profile for every leaderboard entry — for $0, instead of
paying to re-measure what is already published.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "kilo_agents.db"

_DDL = """
CREATE TABLE IF NOT EXISTS tbench_leaderboard_results (
    submission   TEXT NOT NULL,   -- '<agent>__<model>' — the leaderboard's own unit
    agent        TEXT,            -- the harness (vix, LemonHarness, ClaudeCode, ...)
    model_id     TEXT,            -- normalized to agents.id where we can map it
    model_raw    TEXT,            -- the model string exactly as the submission declared it
    task_id      TEXT NOT NULL,   -- e.g. 'configure-git-webserver'
    dataset      TEXT NOT NULL,   -- e.g. 'terminal-bench/terminal-bench-2-1'
    category     TEXT,            -- joined from the task's task.toml
    difficulty   TEXT,
    n_trials     INTEGER,         -- k (submissions must run >= 5)
    n_passed     INTEGER,         -- reward == 1.0
    n_errored    INTEGER,         -- verifier never ran (docker/infra died) — NOT a failure
    pass_rate    REAL,            -- n_passed / (n_trials - n_errored); NULL if all errored
    avg_cost_usd REAL,            -- measured, from agent_result.cost_usd
    scraped_at   TEXT,
    PRIMARY KEY (submission, task_id, dataset)
);
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_tblb_model ON tbench_leaderboard_results(model_id)",
    "CREATE INDEX IF NOT EXISTS idx_tblb_category ON tbench_leaderboard_results(category)",
    # the query this table exists for: per-(model, category) capability
    "CREATE INDEX IF NOT EXISTS idx_tblb_model_cat ON tbench_leaderboard_results(model_id, category)",
]


def ensure_tbench_leaderboard_table(db_path: Path = DB_PATH) -> bool:
    """Return True if the table was created, False if it already existed."""
    conn = sqlite3.connect(db_path)
    try:
        existed = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tbench_leaderboard_results'"
        ).fetchone()
        conn.execute(_DDL)
        for idx in _INDEXES:
            conn.execute(idx)
        conn.commit()
    finally:
        conn.close()
    return existed is None


if __name__ == "__main__":
    created = ensure_tbench_leaderboard_table()
    print(f"tbench_leaderboard_results table: {'created' if created else 'already present'}")
