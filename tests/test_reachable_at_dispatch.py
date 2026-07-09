"""Behavior Contract for record_agent_run(..., reachable_at_dispatch=...) — plan-1 Phase C."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.subagents.pg_ledger import _INSERT, record_agent_run, record_run  # noqa: E402


class _FakeCursor:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql, params=None):
        self.calls.append((sql, tuple(params) if params else ()))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self):
        self.cur = _FakeCursor()

    def cursor(self):
        return self.cur

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def close(self):
        pass


def test_C0_insert_string_extends_with_reachable_column():
    """C.0: _INSERT string includes reachable_at_dispatch as the 12th column.

    12 columns total: project, agent_id, task_type, model, provider, status,
    cost_usd, turns, latency_s, quality_score, tool_calls, reachable_at_dispatch.
    Corresponding 12 %s placeholders (one has ::jsonb cast).
    """
    assert "reachable_at_dispatch" in _INSERT
    assert _INSERT.count("%s") == 12


def test_C1_record_agent_run_writes_reachable_at_dispatch(monkeypatch):
    """C.1: reachable_at_dispatch=1 → the value lands in the row tuple's last cell."""
    fake_conn = _FakeConn()
    monkeypatch.setenv("SUBAGENT_RUNS_DSN", "postgresql:///fake")

    class FakeSpec:
        model = "minimax/minimax-m3"
        task_type = "review"

    class FakeResult:
        agent_id = "agent-x"
        text = ""
        diff = ""
        status = "done"
        provider = "test"
        cost_usd = 0.01
        turns = 1
        error = None
        tool_calls: dict = {}
        latency_s = 1.0
        out_tokens = 0

    ok = record_agent_run(
        FakeSpec(),
        FakeResult(),
        quality_score=4,
        project="fabrik-hub",
        connect=lambda dsn: fake_conn,
        reachable_at_dispatch=1,
    )
    assert ok is True, "record_agent_run returned False"
    # Find the _INSERT execute() call
    insert_call = next(
        (c for c in fake_conn.cur.calls if "INSERT INTO subagent_runs" in c[0]), None
    )
    assert insert_call is not None, "no INSERT executed"
    _sql, params = insert_call
    assert params[-1] == 1, (
        f"reachable_at_dispatch should be last param, got: {params[-1]!r}"
    )


def test_C2_record_agent_run_null_reachable_when_kwarg_omitted(monkeypatch):
    """C.2: kwarg omitted → NULL (None) reachable_at_dispatch. Semantic
    'unknown', not 0 — the flywheel scores unknown separately from 0."""
    fake_conn = _FakeConn()
    monkeypatch.setenv("SUBAGENT_RUNS_DSN", "postgresql:///fake")

    class FakeSpec:
        model = "minimax/minimax-m3"
        task_type = "review"

    class FakeResult:
        agent_id = "agent-y"
        text = ""
        diff = ""
        status = "done"
        provider = "test"
        cost_usd = 0.01
        turns = 1
        error = None
        tool_calls: dict = {}
        latency_s = 1.0
        out_tokens = 0

    ok = record_agent_run(
        FakeSpec(),
        FakeResult(),
        quality_score=4,
        project="fabrik-hub",
        connect=lambda dsn: fake_conn,
    )
    assert ok is True
    insert_call = next(
        (c for c in fake_conn.cur.calls if "INSERT INTO subagent_runs" in c[0]), None
    )
    assert insert_call is not None
    _sql, params = insert_call
    assert params[-1] is None, (
        f"reachable_at_dispatch should be None when kwarg omitted; got {params[-1]!r}"
    )


def test_C4_fail_open_on_undefined_column(monkeypatch):
    """C.4: if the DB rejects the INSERT (e.g. UndefinedColumn from a
    pre-migration DB), record_agent_run returns False (fail-open, no raise).
    """

    class RaisingCursor(_FakeCursor):
        def execute(self, sql, params=None):
            if "INSERT" in sql:
                raise RuntimeError("UndefinedColumn: reachable_at_dispatch")
            super().execute(sql, params)

    class RaisingConn(_FakeConn):
        def __init__(self):
            self.cur = RaisingCursor()

    monkeypatch.setenv("SUBAGENT_RUNS_DSN", "postgresql:///fake")

    class FakeSpec:
        model = "x"
        task_type = "review"

    class FakeResult:
        agent_id = "agent-z"
        text = ""
        diff = ""
        status = "done"
        provider = "t"
        cost_usd = 0.0
        turns = 0
        error = None
        tool_calls: dict = {}
        latency_s = 0.0
        out_tokens = 0

    ok = record_agent_run(
        FakeSpec(),
        FakeResult(),
        connect=lambda dsn: RaisingConn(),
        reachable_at_dispatch=1,
    )
    assert ok is False, "must fail-open, not raise"
