"""The 2026-08-28 transdoc score-contamination batch never reaches the ranking (W-40a0370e).

A transdoc session called ``set_quality`` over its repo's whole ledger history and wrote 238
``status='scored'`` rows (235 runs, 226 of them other sessions') in one minute. The ranker reconciles
quality LATEST-wins, so those rows shadowed real verdicts. The exclusion lives in the ranker's own
``QUERY``; this runs that exact SQL against a TEMP table that shadows ``subagent_runs`` inside one
psql session — no production row is read or written.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "rank_contam", _ROOT / "scripts" / "kilo-benchmarks" / "rank_task_subagents.py"
)
rank = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rank)

# One agent per case, all in ONE (task_type, model) group so it clears MIN_RUNS.
_ROWS = """
INSERT INTO subagent_runs (ts, project, agent_id, task_type, model, status, cost_usd, quality_score) VALUES
 -- A: foreign, scored 2.0 by its own session BEFORE the batch -> must read 2.0 again
 ('2026-08-22 10:00+00','p','A','review','m/x','done',0.01,NULL),
 ('2026-08-23 10:00+00','p','A','review','m/x','scored',NULL,2.0),
 ('2026-08-28 21:32:20+00','transdoc','A','review','m/x','scored',NULL,4.0),
 -- B: foreign, never scored -> must read unscored
 ('2026-08-22 11:00+00','p','B','review','m/x','done',0.01,NULL),
 ('2026-08-28 21:32:21+00','transdoc','B','review','m/x','scored',NULL,4.0),
 -- C: transdoc's OWN run, dispatched in its session -> keeps its 4.0
 ('2026-08-28 21:25:00+00','transdoc','C','review','m/x','done',0.01,NULL),
 ('2026-08-28 21:32:30+00','transdoc','C','review','m/x','scored',NULL,4.0),
 -- D: foreign, re-scored 1.0 AFTER the batch -> 1.0 either way
 ('2026-08-22 12:00+00','p','D','review','m/x','done',0.01,NULL),
 ('2026-08-28 21:32:22+00','transdoc','D','review','m/x','scored',NULL,4.0),
 ('2026-09-01 10:00+00','p','D','review','m/x','scored',NULL,1.0),
 -- E: transdoc's run from an EARLIER session (before 21:15) -> foreign to the batch, unscored
 ('2026-08-25 10:00+00','transdoc','E','review','m/x','done',0.01,NULL),
 ('2026-08-28 21:32:23+00','transdoc','E','review','m/x','scored',NULL,4.0);
"""


def _dsn() -> str:
    dsn = os.getenv("SUBAGENT_RUNS_DSN", "")
    env = _ROOT / ".env"
    if not dsn and env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("SUBAGENT_RUNS_DSN="):
                dsn = line.split("=", 1)[1].strip().strip("\"'")
    return dsn


def _run_ranker_query(query: str) -> list[list[str]]:
    dsn = _dsn()
    if not dsn or not shutil.which("psql"):
        pytest.skip("no SUBAGENT_RUNS_DSN / psql on this box — the ranker's DB is hub-local")
    # The fixture's timestamps are fixed history; widen ONLY the rolling window so the case
    # cannot age out of it (and prove the clause is still there to widen).
    window = f"INTERVAL '{rank.WINDOW_DAYS} days'"
    assert query.count(window) == 1, "the ranker's window clause moved — update this grader"
    sql = (
        "CREATE TEMP TABLE subagent_runs (id bigserial, ts timestamptz, project text, "
        "agent_id text, task_type text, model text, status text, cost_usd double precision, "
        "quality_score real);\n"
        + _ROWS
        + "\\pset tuples_only on\n\\pset format unaligned\n\\pset fieldsep '\\t'\n"
        + query.replace(window, "INTERVAL '100000 days'")
        + ";\n"
    )
    r = subprocess.run(
        ["psql", dsn, "-X", "-q", "-v", "ON_ERROR_STOP=1"],
        input=sql,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if r.returncode != 0 and "could not connect" in r.stderr:
        pytest.skip(f"ranker DB unreachable: {r.stderr.strip()[:120]}")
    assert r.returncode == 0, r.stderr
    return [ln.split("\t") for ln in r.stdout.splitlines() if ln.strip()]


def test_the_contamination_batch_is_excluded_from_the_quality_reconcile():
    rows = _run_ranker_query(rank.QUERY)
    assert len(rows) == 1, rows
    task_type, model, n, _cost, avg_quality, _success = rows[0]
    assert (task_type, model, int(n)) == ("review", "m/x", 5)
    # A 2.0 (its own earlier verdict) · B unscored · C 4.0 (transdoc's own) · D 1.0 · E unscored
    # -> 7/3. With the batch counted: A 4, B 4, C 4, D 1, E 4 -> 3.4; with the carve-out's 21:15
    # bound dropped, E keeps 4.0 -> 11/4 (42 real runs are E-shaped).
    assert float(avg_quality) == pytest.approx(7 / 3, abs=1e-6), avg_quality
