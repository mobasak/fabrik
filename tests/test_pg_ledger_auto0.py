"""Behavior-Contract tests — flywheel auto-0 for mechanically-failed pool runs.

Plan C4, GROUNDED NARROWER at execution: record_run ALREADY nulls error/capped scores by
design ("an infra/provider failure can't teach pick_models a false 0" — pg_ledger.py:167-171)
and the ranker's success_rate term already punishes those statuses. The one failure that slips
BOTH nets is status=="done" with EMPTY output — the model "succeeded" and returned nothing
gradeable (the class behind today's four misread dispatches). Auto-0 covers exactly that;
error/capped stay NULL (module invariant); healthy unscored stays NULL (unscored ≠ bad).
Asserted at the injectable ``connect`` seam.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.subagents.pg_ledger import record_agent_run  # noqa: E402


@dataclass
class _Spec:
    task: str = "review x"
    task_type: str = "review"
    model: str = "test/model-1"


@dataclass
class _Result:
    agent_id: str = "agent-test-0001"
    text: str = "a real finding"
    diff: str = ""
    status: str = "done"
    provider: str = "test"
    cost_usd: float = 0.001
    turns: int = 1
    error: str | None = None
    tool_calls: dict = field(default_factory=dict)
    latency_s: float = 1.0
    out_tokens: int = 10
    model: str = "test/model-1"


class _Cursor:
    def __init__(self, sink):
        self.sink = sink

    def execute(self, sql, params=None):
        self.sink.append((sql, params))

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def __init__(self, sink):
        self.sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return _Cursor(self.sink)

    def commit(self):
        pass

    def close(self):
        pass


def _recorded_quality(result, sink):
    ok = record_agent_run(
        _Spec(), result, quality_score=None, project="auto0-test",
        dsn="postgresql://fake", connect=lambda dsn: _Conn(sink),
        receipt_dir=None, outbox_dir=None,
    )
    assert ok, "the fake-connection insert must be treated as confirmed"
    assert sink, "no INSERT captured"
    _sql, params = sink[-1]
    return [p for p in (params or [])]


def test_errored_run_stays_null_module_invariant(tmp_path):
    """error → NULL (record_run's own coercion: infra failure must not teach a false 0)."""
    sink = []
    params = _recorded_quality(_Result(status="error", error="boom", text=""), sink)
    assert 0.0 not in params, params


def test_capped_run_stays_null_module_invariant(tmp_path):
    sink = []
    params = _recorded_quality(_Result(status="capped", text="partial"), sink)
    assert 0.0 not in params, params


def test_done_but_empty_output_auto_scores_zero(tmp_path):
    """status=done + blank text = the model returned nothing gradeable — a TRUE 0 the
    success_rate term cannot see. THE auto-0 case."""
    sink = []
    params = _recorded_quality(_Result(status="done", text="   \n"), sink)
    assert 0.0 in params, params


def test_healthy_unscored_stays_null(tmp_path):
    sink = []
    params = _recorded_quality(_Result(status="done", text="a real finding"), sink)
    assert 0.0 not in params, ("healthy unscored must stay NULL — unscored != bad", params)


def test_write_unit_with_diff_but_empty_text_stays_null(tmp_path):
    """A mode='write' coder's value IS its diff — empty text with a real diff is HEALTHY,
    never auto-0 (self-caught during the Phase C review round)."""
    sink = []
    params = _recorded_quality(_Result(status="done", text="", diff="+ real change\n"), sink)
    assert 0.0 not in params, params
