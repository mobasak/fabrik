# AFTER-EDIT: ../rank_task_subagents.py | golden/structure.json
"""Phase B tests — canary aggregation + `grounding` column (plan 2026-08-28-plan-1-canary-grounding).

SQL behaviors are REAL-DB tests (zero-mock policy): a throwaway `TEST_DATABASE_URL` database
gets `subagent_runs` from the module's own DDL, fixture rows are inserted, and the module's
ACTUAL query strings are executed via psycopg — a substring assertion on a SQL string stays
green when the clause lands in a comment; executing the query cannot be fooled.
The column-position proof uses fabrik-lib's real parser (`load_task_ranking`) as the oracle,
with `min_n` engaged so the parsed run-count BITES (with min_n=0 a mispositioned column parses
n as 0 and everything still passes vacuously — select.py:303-306).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
KILO_DIR = TESTS_DIR.parent
REPO = KILO_DIR.parent.parent
for p in (str(KILO_DIR), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

import rank_task_subagents as rts  # noqa: E402
from libs.subagents.pg_ledger import SUBAGENT_RUNS_DDL  # noqa: E402
from libs.subagents.select import load_task_ranking  # noqa: E402

TEST_DSN = os.getenv("TEST_DATABASE_URL", "")

needs_db = pytest.mark.skipif(not TEST_DSN, reason="TEST_DATABASE_URL unset")


@pytest.fixture()
def throwaway_db():
    # the fixture itself enforces the throwaway convention: refuse any URL whose db name
    # lacks a test marker BEFORE touching it (the hub has no importable require_throwaway)
    dbname = TEST_DSN.rstrip("/").rsplit("/", 1)[-1]
    if "test" not in dbname:
        pytest.fail(f"TEST_DATABASE_URL points at a non-throwaway db: {dbname!r}")
    import psycopg

    with psycopg.connect(TEST_DSN) as conn:
        conn.execute("DROP TABLE IF EXISTS subagent_runs")
        conn.execute(SUBAGENT_RUNS_DDL)
        conn.commit()
        yield conn
        conn.rollback()
        conn.execute("DROP TABLE IF EXISTS subagent_runs")
        conn.commit()


def _insert(
    conn,
    *,
    project="p",
    agent_id,
    task_type="review",
    model,
    status="done",
    quality=None,
    cost=0.001,
    days_ago=0,
):
    conn.execute(
        "INSERT INTO subagent_runs (ts, project, agent_id, task_type, model, status, cost_usd, quality_score)"
        " VALUES (now() - make_interval(days => %s), %s, %s, %s, %s, %s, %s, %s)",
        (days_ago, project, agent_id, task_type, model, status, cost, quality),
    )


def _run(conn, sql):
    conn.commit()
    return conn.execute(sql).fetchall()


# --- organic QUERY: canary exclusion + the scored-delta reconcile contract ----------------


@needs_db
def test_organic_query_excludes_canary_rows(throwaway_db):
    conn = throwaway_db
    # model M has a healthy organic record…
    for i in range(4):
        _insert(conn, agent_id=f"a{i}", model="prov/m", quality=4.0)
    # …and a 0-scored canary pair that must NOT drag it (dispatch + scored delta)
    _insert(conn, project="canary-grounding", agent_id="c0", model="prov/m", quality=None)
    _insert(
        conn,
        project="canary-grounding",
        agent_id="c0",
        model="prov/m",
        status="scored",
        quality=0.0,
        cost=None,
    )
    rows = _run(conn, rts.QUERY)
    assert len(rows) == 1
    _tt, model, n, _cost, avg_q, success = rows[0]
    assert model == "prov/m"
    assert int(n) == 4  # canary rows contribute NOTHING to organic n
    assert float(avg_q) == 4.0  # …nor to the average the multiplier will act on
    assert float(success) == 1.0


@needs_db
def test_organic_query_honors_scored_delta_contract(throwaway_db):
    conn = throwaway_db
    # 3 fanout dispatch rows (quality NULL at dispatch), one back-filled via a scored delta —
    # per pg_ledger.py:500-530: n counts OBJECTIVE rows only; the delta must not deflate success
    for i in range(3):
        _insert(conn, agent_id=f"a{i}", model="prov/m", quality=None)
    _insert(conn, agent_id="a0", model="prov/m", status="scored", quality=4.0, cost=None)
    rows = _run(conn, rts.QUERY)
    assert len(rows) == 1
    _tt, _model, n, _cost, avg_q, success = rows[0]
    assert int(n) == 3  # the delta never inflates n (was: 4)
    assert float(success) == 1.0  # nor deflates success_rate (was: 0.75)
    assert float(avg_q) == 4.0  # effective quality = the back-filled score


@needs_db
def test_organic_query_latest_score_wins_not_max(throwaway_db):
    conn = throwaway_db
    # the contract says the LATEST non-NULL score wins (pg_ledger.py:651-654) — a human
    # re-scoring 4 -> 1 must stick; MAX would resurrect the 4 (live: flipped research rank 1)
    for i in range(3):
        _insert(conn, agent_id=f"a{i}", model="prov/m", quality=None)
    _insert(
        conn, agent_id="a0", model="prov/m", status="scored", quality=4.0, cost=None, days_ago=2
    )
    _insert(
        conn, agent_id="a0", model="prov/m", status="scored", quality=1.0, cost=None, days_ago=1
    )
    rows = _run(conn, rts.QUERY)
    assert float(rows[0][4]) == 1.0  # latest, never MAX


@needs_db
def test_organic_query_same_ts_tie_breaks_by_insertion_order(throwaway_db):
    conn = throwaway_db
    # two scored deltas sharing one ts (same-txn writes): id BIGSERIAL is the true
    # insertion order, so the LATER insert wins deterministically (ORDER BY ts DESC, id DESC)
    for i in range(3):
        _insert(conn, agent_id=f"a{i}", model="prov/m", quality=None)
    _insert(
        conn, agent_id="a0", model="prov/m", status="scored", quality=4.0, cost=None, days_ago=1
    )
    _insert(
        conn, agent_id="a0", model="prov/m", status="scored", quality=2.0, cost=None, days_ago=1
    )
    rows = _run(conn, rts.QUERY)
    assert float(rows[0][4]) == 2.0  # the later same-ts insert wins


@needs_db
def test_organic_query_preserves_orphan_verdicts_without_counting_them(throwaway_db):
    conn = throwaway_db
    # an orphan scored delta (dispatch row never landed) PRESERVES its verdict
    # (pg_ledger.py:665-667) — it joins avg_quality but adds nothing to n and
    # never deflates success_rate (it has no objective run to succeed or fail)
    for i in range(3):
        _insert(conn, agent_id=f"a{i}", model="prov/m", quality=4.0)
    _insert(conn, agent_id="orphan", model="prov/m", status="scored", quality=0.0, cost=None)
    rows = _run(conn, rts.QUERY)
    _tt, _m, n, _c, avg_q, success = rows[0]
    assert int(n) == 3  # orphan adds no run
    assert float(avg_q) == 3.0  # (4+4+4+0)/4 — the verdict is preserved
    assert float(success) == 1.0  # and success is judged over objective agents only


# --- CANARY_QUERY: >=2-row floor + 30-day staleness decay ---------------------------------


def _canary_pair(conn, agent_id, model, score, days_ago=0):
    _insert(
        conn,
        project="canary-grounding",
        agent_id=agent_id,
        model=model,
        quality=None,
        days_ago=days_ago,
    )
    _insert(
        conn,
        project="canary-grounding",
        agent_id=agent_id,
        model=model,
        status="scored",
        quality=score,
        cost=None,
        days_ago=days_ago,
    )


@needs_db
def test_canary_query_floor_and_staleness(throwaway_db):
    conn = throwaway_db
    # one stray scored row -> BELOW the >=2 floor -> no output row (no penalty from one sample)
    _canary_pair(conn, "c0", "prov/one", 0.0)
    assert _run(conn, rts.CANARY_QUERY) == []
    # two fresh scored rows -> the average
    _canary_pair(conn, "c1", "prov/one", 5.0)
    rows = _run(conn, rts.CANARY_QUERY)
    assert len(rows) == 1
    model, avg = rows[0]
    assert model == "prov/one" and float(avg) == 2.5
    # two rows aged past the 30-day window -> decayed to no data
    _canary_pair(conn, "c2", "prov/old", 0.0, days_ago=31)
    _canary_pair(conn, "c3", "prov/old", 0.0, days_ago=40)
    models = {r[0] for r in _run(conn, rts.CANARY_QUERY)}
    assert "prov/old" not in models


@needs_db
def test_canary_query_ignores_failed_dispatch_units(throwaway_db):
    conn = throwaway_db
    # a provider outage (dispatch status != 'done') must NEVER become a grounding penalty —
    # even if a zero somehow got scored for it, the query refuses the agent (defense in depth;
    # the harness additionally never scores non-done units)
    for aid in ("c0", "c1"):
        _insert(
            conn,
            project="canary-grounding",
            agent_id=aid,
            model="prov/down",
            status="error",
            quality=None,
        )
        _insert(
            conn,
            project="canary-grounding",
            agent_id=aid,
            model="prov/down",
            status="scored",
            quality=0.0,
            cost=None,
        )
    assert _run(conn, rts.CANARY_QUERY) == []


# --- the grounding column: parser-as-oracle + cell rendering ------------------------------

# task type `docs`: ungated (review rows must clear the ACTIVE benchmark-eligibility gate and
# fixture models never can); n=50 so shrunk_q clears the 2.5 quality gate with no tier baseline
FLEET_ROWS = [
    ("docs", "prov/a", 50, 0.001, 4.5, 1.0),
    ("docs", "prov/b", 50, 0.002, 4.0, 1.0),
]


def test_grounding_column_position(tmp_path, monkeypatch):
    """⚠️ Renders with the operator ALLOWLIST DISABLED, via its documented off switch.

    This test is about COLUMN POSITION — that `grounding` sits second-to-last and `n` stays last, the
    law `select.py:296,303` parses on. Its fixtures are arbitrary (`prov/a`, `prov/b`), and D-159's
    allowlist filters every non-allowlisted model out of every routing section, so with the allowlist
    live the `### docs` section holds allowlist rows carrying `n=0` and `min_n=1` drops them —
    turning a column-position assertion into an accidental routing-policy assertion. Emptying
    `OPERATOR_ALLOW` restores exactly the pre-D-159 behaviour (that is what the empty set means) and
    keeps this test measuring what its name says.
    """
    monkeypatch.setattr(rts, "OPERATOR_ALLOW", frozenset())
    text = rts.render(FLEET_ROWS, canary={"prov/a": 4.0, "prov/b": 1.0}, include_full_results=False)
    doc = tmp_path / "TASK_SUBAGENT_SELECTION.md"
    doc.write_text(text, encoding="utf-8")
    # the REAL consumer parses the NEW format: model from cells[1], n from cells[-1]
    ranking = load_task_ranking(str(doc), min_n=1)
    assert ranking.get("docs") == ["prov/a", "prov/b"]
    # …and the parsed n BITES: the fixture rows carry n=50 — they survive min_n=50, die at 51.
    # A mispositioned grounding column (inserted LAST) parses n as 0 and fails BOTH asserts.
    assert load_task_ranking(str(doc), min_n=50).get("docs") == ["prov/a", "prov/b"]
    assert load_task_ranking(str(doc), min_n=51).get("docs") is None
    # header: grounding second-to-last, n LAST (the column-position law, select.py:296,303)
    header = next(ln for ln in text.splitlines() if ln.startswith("| rank | model |"))
    cells = [c.strip() for c in header.strip("|").split("|")]
    assert cells[-1] == "n" and cells[-2] == "grounding"


def test_every_table_row_width_matches_its_header():
    # structural invariant over the WHOLE rendered doc: every |-row under a ### section has
    # exactly its header's cell count — the test that catches a missed (or future sixth) emitter
    text = rts.render(FLEET_ROWS, canary={"prov/a": 4.0}, include_full_results=True)
    # scope the invariant per CONTIGUOUS |-table: any non-table line ends the current table,
    # so every table (router sections AND display leaderboards) is checked against ITS OWN header
    width = None
    for line in text.splitlines():
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            width = None
            continue
        cells = s.strip("|").split("|")
        if width is None:
            width = len(cells)
        assert len(cells) == width, f"row width {len(cells)} != header width {width}: {s[:90]}"


def test_grounding_cell():
    assert rts._grounding_cell(2.5) == "✓"
    assert rts._grounding_cell(2.49) == "✗(2.49)"  # TWO decimals — 2.49 must never render as 2.5
    assert rts._grounding_cell(None) == "—"
