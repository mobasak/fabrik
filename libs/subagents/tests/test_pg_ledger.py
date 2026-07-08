"""pg_ledger.py — the centralized run-metrics sink (shared subagent_runs on postgres-main).

All offline: an injected fake connection stands in for psycopg. Proves the row shape, the
FAIL-OPEN contract (never raises on connect/insert failure), env-DSN resolution, and that
`Ledger` dual-writes only when a DSN is configured.
"""

from __future__ import annotations

import json

from subagents import ledger as ledger_mod
from subagents.pg_ledger import SUBAGENT_RUNS_DDL, record_run


class _FakeCursor:
    def __init__(self, sink: list) -> None:
        self._sink = sink

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *a: object) -> bool:
        return False

    def execute(self, sql: str, params: tuple | None = None) -> None:
        # mirror psycopg: params is optional (the SET LOCAL statement_timeout passes none)
        self._sink.append((sql, params))


class _FakeConn:
    def __init__(
        self, sink: list, *, fail_enter: bool = False, fail_exec: bool = False
    ) -> None:
        self._sink = sink
        self._fail_enter = fail_enter
        self._fail_exec = fail_exec
        self.closed = False

    def __enter__(self) -> "_FakeConn":
        if self._fail_enter:
            raise RuntimeError("tx begin failed")
        return self

    def __exit__(self, *a: object) -> bool:
        return False

    def cursor(self) -> _FakeCursor:
        if self._fail_exec:
            raise RuntimeError("cursor failed")
        return _FakeCursor(self._sink)

    def close(self) -> None:
        self.closed = True


def _rec(**kw: object) -> dict:
    base = {
        "agent_id": "agent-000-abc",
        "task_type": "spec",
        "model": "z-ai/glm-5",
        "provider": "DeepInfra",
        "status": "done",
        "cost_usd": 0.009,
        "turns": 1,
        "latency_s": 34.0,
        "tool_calls": {"web_search": 2},
    }
    base.update(kw)
    return base


def test_no_dsn_is_a_noop(monkeypatch) -> None:
    monkeypatch.delenv("SUBAGENT_RUNS_DSN", raising=False)
    assert record_run(_rec()) is False  # nothing to write to → no-op, not an error


def test_injected_connect_inserts_expected_row() -> None:
    sink: list = []
    ok = record_run(
        _rec(),
        dsn="postgresql://x",
        project="myproj",
        quality_score=4.5,
        connect=lambda dsn: _FakeConn(sink),
    )
    assert ok is True
    assert any("statement_timeout" in c[0] for c in sink)  # the INSERT is time-bounded
    insert = [c for c in sink if "INSERT INTO subagent_runs" in c[0]]
    assert len(insert) == 1
    _, params = insert[0]
    # ALL 11 positions pinned in column order — a cost_usd/turns (or any) swap must fail here,
    # since the DB maps by the _INSERT column names, so tuple-order == column-order is the invariant.
    assert params[:10] == (
        "myproj",
        "agent-000-abc",
        "spec",
        "z-ai/glm-5",
        "DeepInfra",
        "done",
        0.009,
        1,
        34.0,
        4.5,
    )
    assert json.loads(params[10]) == {"web_search": 2}  # tool_calls jsonb payload


def test_fail_open_on_connect_error() -> None:
    def boom(dsn: str) -> _FakeConn:
        raise RuntimeError("db down")

    assert record_run(_rec(), dsn="postgresql://x", connect=boom) is False


def test_fail_open_on_execute_error() -> None:
    assert (
        record_run(
            _rec(),
            dsn="postgresql://x",
            connect=lambda dsn: _FakeConn([], fail_exec=True),
        )
        is False
    )


def test_fail_open_on_transaction_enter_error() -> None:
    # `with conn:` (psycopg tx begin) raising must be caught → False, never propagated
    assert (
        record_run(
            _rec(),
            dsn="postgresql://x",
            connect=lambda dsn: _FakeConn([], fail_enter=True),
        )
        is False
    )


def test_fail_open_on_non_dict_record() -> None:
    # `record` is a public exported symbol; a non-dict must not crash the "never raises" contract
    assert (
        record_run(
            "not-a-dict", dsn="postgresql://x", connect=lambda dsn: _FakeConn([])
        )  # type: ignore[arg-type]
        is False
    )


def test_unserializable_tool_calls_does_not_raise() -> None:
    # a non-JSON-native value in tool_calls (a set) is stringified via default=str, not raised
    sink: list = []
    rec = _rec(tool_calls={"s": {1, 2, 3}})
    assert (
        record_run(rec, dsn="postgresql://x", connect=lambda dsn: _FakeConn(sink))
        is True
    )
    insert = [c for c in sink if "INSERT INTO" in c[0]][0]
    assert json.loads(insert[1][10]) == {"s": "{1, 2, 3}"}


def test_dsn_and_project_from_env(monkeypatch) -> None:
    monkeypatch.setenv("SUBAGENT_RUNS_DSN", "postgresql://env")
    monkeypatch.setenv("SUBAGENT_PROJECT", "proj-from-env")
    sink: list = []
    seen: dict = {}

    def cap(dsn: str) -> _FakeConn:
        seen["dsn"] = dsn
        return _FakeConn(sink)

    assert record_run(_rec(), connect=cap) is True
    assert seen["dsn"] == "postgresql://env"
    insert = [c for c in sink if "INSERT INTO" in c[0]][0]
    assert insert[1][0] == "proj-from-env"


def test_ledger_writes_jsonl_only_never_auto_writes_pg(monkeypatch, tmp_path) -> None:
    """The ledger is the LOCAL JSONL audit copy ONLY — it must NOT auto-write to Postgres,
    even with SUBAGENT_RUNS_DSN set. A runtime auto-write could only carry a NULL quality
    and would DUPLICATE the orchestrator's quality-bearing ``record_run`` row (the table is
    INSERT-only, so they can't be merged). One run → one flywheel row, via ``record_run``."""
    import inspect

    import subagents.pg_ledger as pgl

    monkeypatch.setenv("SUBAGENT_RUNS_DSN", "postgresql://x")
    called: list = []
    monkeypatch.setattr(pgl, "record_run", lambda *a, **k: called.append(1) or True)

    lg = ledger_mod.Ledger(str(tmp_path / "l.jsonl"))
    lg.append({"agent_id": "a", "task_type": "spec", "model": "m"})

    assert called == []  # NEVER auto-writes to PG, even with the DSN set
    assert (tmp_path / "l.jsonl").exists()  # the JSONL audit copy IS written
    # and the removed footgun stays removed: no pg_dsn constructor param
    assert "pg_dsn" not in inspect.signature(ledger_mod.Ledger.__init__).parameters


def test_ddl_has_table_and_key_columns() -> None:
    for tok in (
        "subagent_runs",
        "task_type",
        "model",
        "cost_usd",
        "quality_score",
        "tool_calls",
    ):
        assert tok in SUBAGENT_RUNS_DDL
