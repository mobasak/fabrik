# AFTER-EDIT: ../reclassify_cap_rows.py | ../rank_task_subagents.py
"""C1 — the default-cap reclassification, and C3 — blank-status tolerance.

Real Postgres, real rows. The migration's whole risk is selecting the WRONG population: the cause
(an HTTP 404 about `max price`) exists only in the JSONL ledger, never in the table, so selection is
by an enumerated `(model, date)` set and these tests are what stop that set drifting.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS = TESTS_DIR.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent.parent))


TEST_DSN = os.getenv("TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not TEST_DSN, reason="TEST_DATABASE_URL unset")


@pytest.fixture()
def db():
    if "test" not in TEST_DSN.rstrip("/").rsplit("/", 1)[-1]:
        pytest.fail("TEST_DATABASE_URL is not a throwaway database")
    import psycopg
    from libs.subagents.pg_ledger import SUBAGENT_RUNS_DDL

    with psycopg.connect(TEST_DSN) as c:
        c.execute(SUBAGENT_RUNS_DDL)
        c.execute("TRUNCATE subagent_runs")
        c.commit()
    return TEST_DSN


def _ins(dsn: str, model: str, day: str, status: str, n: int = 1, project: str = "review") -> None:
    import psycopg

    with psycopg.connect(dsn) as c:
        for i in range(n):
            c.execute(
                "INSERT INTO subagent_runs (ts, project, agent_id, task_type, model, status) "
                "VALUES (%s::date, %s, %s, 'review', %s, %s)",
                (day, project, f"{model}-{day}-{status}-{i}-{os.urandom(3).hex()}", model, status),
            )
        c.commit()


def _status_counts(dsn: str) -> dict[str, int]:
    import psycopg

    with psycopg.connect(dsn) as c:
        return dict(c.execute("SELECT status, count(*) FROM subagent_runs GROUP BY 1").fetchall())


def _run(dsn: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "reclassify_cap_rows.py"), "--dsn", dsn, *extra],
        capture_output=True, text=True,
    )


@needs_db
def test_a_dry_run_writes_nothing(db):
    _ins(db, "moonshotai/kimi-k2.5", "2026-07-18", "error", 5)
    p = _run(db)
    assert "DRY RUN" in p.stdout, p.stdout + p.stderr
    assert _status_counts(db) == {"error": 5}, "a dry run must not mutate a single row"


@needs_db
def test_only_the_enumerated_model_and_date_are_touched(db):
    """The blast radius IS the candidate set. A neighbouring model, a neighbouring DATE, and a
    non-error status must all survive untouched — this is what stops the set drifting into a
    date-only sweep, which would erase a caller's deliberate `max_cost_per_mtok` rejections."""
    _ins(db, "moonshotai/kimi-k2.5", "2026-07-18", "error", 3)   # in scope
    _ins(db, "moonshotai/kimi-k2.5", "2026-07-19", "error", 2)   # AFTER the cap came off
    _ins(db, "deepseek/deepseek-v4-pro", "2026-07-18", "error", 4)  # not a priced-out model
    _ins(db, "z-ai/glm-5", "2026-07-18", "done", 2)              # not an error
    p = _run(db, "--apply")
    assert "APPLIED: 3 row(s)" in p.stdout, p.stdout + p.stderr
    c = _status_counts(db)
    assert c["skipped"] == 3
    assert c["error"] == 6, "a neighbouring model or date was swept in"
    assert c["done"] == 2


@needs_db
def test_the_reclassified_rows_stop_counting_against_the_model(db):
    """The point of the whole migration: a run that never happened must not read as a failure."""
    import psycopg

    _ins(db, "z-ai/glm-5", "2026-07-18", "error", 8)
    _ins(db, "z-ai/glm-5", "2026-08-01", "done", 2)
    _run(db, "--apply")
    with psycopg.connect(db) as c:
        rows = c.execute(
            "WITH r AS (SELECT agent_id, max(model) m, bool_or(status='done') ok FROM subagent_runs "
            "WHERE status IN ('done','error','capped') GROUP BY agent_id) "
            "SELECT count(*), count(*) FILTER (WHERE ok) FROM r WHERE m='z-ai/glm-5'"
        ).fetchone()
    assert rows == (2, 2), f"success rate did not recompute on the real runs only: {rows}"


@needs_db
def test_it_is_idempotent(db):
    """A one-off that is run twice must not widen its own blast radius."""
    _ins(db, "qwen/qwen3.7-max", "2026-07-18", "error", 4)
    _run(db, "--apply")
    p = _run(db, "--apply")
    assert "APPLIED: 0 row(s)" in p.stdout, p.stdout
    assert _status_counts(db)["skipped"] == 4


# ── C3 ─────────────────────────────────────────────────────────────────────────────────────────
@needs_db
def test_blank_status_rows_are_tolerated_by_the_aggregation(db):
    """C3 — 2,727 rows dated 2026-07-18 carry `status=''`. Any status-reading aggregation must treat
    blank as UNKNOWN: never a success, never a failure. Injecting them must not move the numbers."""
    import psycopg

    _ins(db, "deepseek/deepseek-v3.2-exp", "2026-08-01", "done", 6)
    _ins(db, "deepseek/deepseek-v3.2-exp", "2026-08-01", "error", 2)
    q = ("WITH r AS (SELECT agent_id, max(model) m, bool_or(status='done') ok FROM subagent_runs "
         "WHERE status IN ('done','error','capped') GROUP BY agent_id) "
         "SELECT count(*), count(*) FILTER (WHERE ok) FROM r")
    with psycopg.connect(db) as c:
        before = c.execute(q).fetchone()
    _ins(db, "deepseek/deepseek-v3.2-exp", "2026-07-18", "", 100)
    with psycopg.connect(db) as c:
        after = c.execute(q).fetchone()
    assert before == after == (8, 6), f"blank-status rows moved the aggregation: {before} -> {after}"
