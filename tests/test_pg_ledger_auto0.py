"""Behavior-Contract tests — the flywheel records NO auto-0: a failed or empty pool run stays NULL.

Plan C4, GROUNDED NARROWER at execution: record_run ALREADY nulls error/capped scores by
design ("an infra/provider failure can't teach pick_models a false 0" — `record_run`)
and the ranker's success_rate term already punishes those statuses. The one failure that slips
BOTH nets is status=="done" with EMPTY output — the model "succeeded" and returned nothing
gradeable (the class behind today's four misread dispatches). That auto-0 was REVERSED
upstream on 2026-08-29 (fabrik-lib 97d2cf72, intel's policy call): an empty `done` run is left
UNSCORED (NULL), because an empty completion is usually the caller's output budget, not a bad
model; the `empty_output` marker carries the visibility instead. So every case here stays NULL:
error/capped (module invariant), empty `done`, and healthy unscored (unscored ≠ bad).
Asserted at the injectable ``connect`` seam.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

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


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    """The module's fallback paths are CWD-relative; from the repo root that is the REAL receipts
    ledger. Every test runs in its own empty dir, so no argument can reach the repo (W-b951a71d)."""
    monkeypatch.chdir(tmp_path)


def _recorded_quality(result, sink, receipt_dir, quality_score=None):
    if not receipt_dir:  # None, "": the module falls back to .tmp/subagents under the CWD
        raise TypeError("receipt_dir is required — a falsy value writes receipts under the CWD")
    ok = record_agent_run(
        _Spec(),
        result,
        quality_score=quality_score,
        project="auto0-test",
        dsn="postgresql://fake",
        connect=lambda dsn: _Conn(sink),
        receipt_dir=str(receipt_dir),  # never None: that writes the REAL repo receipts
        outbox_dir=None,
    )
    assert ok, "the fake-connection insert must be treated as confirmed"
    assert sink, "no INSERT captured"
    sql, params = sink[-1]
    # The recorded SCORE itself, by its column: a whole-row "no 0.0" check also passed a 5.0.
    cols = [c.strip() for c in sql.split("(", 1)[1].split(")", 1)[0].split(",")]
    return list(params)[cols.index("quality_score")]


def test_errored_run_stays_null_module_invariant(tmp_path):
    """error → NULL even when a score IS offered: record_run's own coercion (an infra failure must
    not teach pick_models a verdict). Offering None here would pass with the coercion deleted."""
    sink = []
    score = _recorded_quality(
        _Result(status="error", error="boom", text=""), sink, tmp_path, quality_score=4.0
    )
    assert score is None, score


def test_capped_run_stays_null_module_invariant(tmp_path):
    """capped → NULL even when a score IS offered (the same record_run coercion)."""
    sink = []
    score = _recorded_quality(
        _Result(status="capped", text="partial"), sink, tmp_path, quality_score=4.0
    )
    assert score is None, score


def test_done_but_empty_output_stays_unscored(tmp_path):
    """status=done + blank text stays NULL — the auto-0 was reversed upstream (97d2cf72): a 0
    would permanently tank a good model for the caller's too-small output budget."""
    sink = []
    score = _recorded_quality(_Result(status="done", text="   \n"), sink, tmp_path)
    assert score is None, score


def test_healthy_unscored_stays_null(tmp_path):
    sink = []
    score = _recorded_quality(_Result(status="done", text="a real finding"), sink, tmp_path)
    assert score is None, ("healthy unscored must stay NULL — unscored != bad", score)


def test_write_unit_with_diff_but_empty_text_stays_null(tmp_path):
    """A mode='write' coder's value IS its diff — empty text with a real diff is HEALTHY,
    never auto-0 (self-caught during the Phase C review round)."""
    sink = []
    score = _recorded_quality(
        _Result(status="done", text="", diff="+ real change\n"), sink, tmp_path
    )
    assert score is None, score


def test_recording_never_writes_receipts_outside_its_own_dir(tmp_path, monkeypatch):
    """W-b951a71d: with receipt_dir=None the module appends to `.tmp/subagents/receipts.jsonl`
    under the CWD — from the repo root that is the REAL ledger (127 fake rows found there)."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    receipts = tmp_path / "receipts"
    _recorded_quality(_Result(status="done", text="a real finding"), [], receipts)
    assert not any(cwd.iterdir()), ("a file was written under the CWD", sorted(cwd.rglob("*")))
    assert any(receipts.iterdir()), "the receipt did not land in the dir it was given"
