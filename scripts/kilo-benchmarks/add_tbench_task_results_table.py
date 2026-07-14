#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/microbench_terminal.py
"""Idempotent schema addition: the per-task Terminal-Bench results table.

`agents.tbench_accuracy` stores only the AGGREGATE pass-rate. That hides the
category profile — e.g. minimax-m3 scored ~36% overall but 10% at
system-administration. This table persists the per-task detail (category,
difficulty, failure_mode) so capability can be sliced per category/difficulty
and compared across models.

Runs safely N times. Called by microbench_terminal.py on entry (same pattern as
add_perf_seconds_column). One row per (model_id, task_id, dataset).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "kilo_agents.db"

_DDL = """
CREATE TABLE IF NOT EXISTS tbench_task_results (
    model_id     TEXT NOT NULL,          -- agents.id (openrouter model, without the openrouter/ prefix)
    task_id      TEXT NOT NULL,          -- terminal-bench task id, e.g. 'configure-git-webserver'
    dataset      TEXT NOT NULL,          -- e.g. 'terminal-bench-core==0.1.1'
    category     TEXT,                   -- from task.yaml: system-administration/security/...
    difficulty   TEXT,                   -- from task.yaml: easy/medium/hard
    is_resolved  INTEGER,                -- 1 = passed, 0 = failed
    failure_mode TEXT,                   -- agent_timeout / parse_error / test_timeout / unset / NULL
    duration_s   REAL,                   -- trial wall-clock seconds
    run_id       TEXT,                   -- the tb run-id the result came from
    benched_at   TEXT,                   -- ISO date the row was written
    PRIMARY KEY (model_id, task_id, dataset)
);
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_tbench_task_model ON tbench_task_results(model_id)",
    "CREATE INDEX IF NOT EXISTS idx_tbench_task_category ON tbench_task_results(category)",
    # report_matrix does GROUP BY model_id, category — covering index.
    "CREATE INDEX IF NOT EXISTS idx_tbench_task_model_cat ON tbench_task_results(model_id, category)",
]


def ensure_tbench_task_results_table(db_path: Path = DB_PATH) -> bool:
    """Return True if the table was created, False if it already existed."""
    conn = sqlite3.connect(db_path)
    try:
        existed = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tbench_task_results'"
        ).fetchone()
        conn.execute(_DDL)
        for idx in _INDEXES:
            conn.execute(idx)
        conn.commit()
    finally:
        conn.close()
    return existed is None


if __name__ == "__main__":
    created = ensure_tbench_task_results_table()
    print(f"tbench_task_results table: {'created' if created else 'already present'}")
