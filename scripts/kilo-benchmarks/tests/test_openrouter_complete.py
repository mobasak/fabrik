"""Behavior tests for openrouter_complete.py (the completions shim).

Phase B behaviors from plan-3:
- B4: generate_samples returns (Path, float=sum(Result.cost_usd))
- B5: per-problem exception writes empty solution + [error] stderr, doesn't abort batch
- B6: finish_reason="length" logs [warn] but writes the (truncated) text

Plan: docs/development/plans/2026-07-10-plan-3-coding-microbench-completions-shim.md
"""
# AFTER-EDIT: none

from __future__ import annotations

import io
import json
import pathlib
import sys
from contextlib import redirect_stderr
from dataclasses import dataclass

import pytest

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str((SCRIPT_DIR / "libs").resolve()))

import openrouter_complete  # noqa: E402


@dataclass
class _FakeResult:
    """Mirror libs.subagents._transport.Result's shape for the fields the shim reads."""

    text: str = ""
    cost_usd: float | None = None
    finish_reason: str | None = None


# ─── B4: generate_samples returns (Path, float=sum(cost_usd)) ──────────────────
def test_generate_samples_returns_path_and_total_cost(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B4: 3 problems with mocked _run returning cost_usd=[0.01, 0.02, 0.03] →
    generate_samples returns (path, 0.06). Verifies sum semantics."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")

    calls = {"i": 0}
    costs = [0.01, 0.02, 0.03]

    def _fake_run(model, prompt, *, client, max_cost_usd):
        i = calls["i"]
        calls["i"] += 1
        return _FakeResult(text=f"# solution for task {i}", cost_usd=costs[i])

    monkeypatch.setattr(openrouter_complete, "_run", _fake_run)

    out_path = tmp_path / "samples.jsonl"
    result_path, total_cost = openrouter_complete.generate_samples(
        model="test/model",
        problems={"T/0": "prompt0", "T/1": "prompt1", "T/2": "prompt2"},
        out_path=out_path,
    )
    assert result_path == out_path
    assert abs(total_cost - 0.06) < 1e-9, total_cost
    # And the JSONL has 3 lines with correct task_ids in input order
    lines = out_path.read_text().strip().split("\n")
    assert len(lines) == 3
    parsed = [json.loads(line) for line in lines]
    assert [row["task_id"] for row in parsed] == ["T/0", "T/1", "T/2"]


def test_generate_samples_preserves_input_order(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B4 extension: ThreadPoolExecutor.map preserves input order → deterministic JSONL."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")

    def _fake_run(model, prompt, *, client, max_cost_usd):
        return _FakeResult(text=f"sol({prompt})", cost_usd=0.001)

    monkeypatch.setattr(openrouter_complete, "_run", _fake_run)

    # Non-sorted keys — order-preservation is the property under test
    task_ids = ["T/9", "T/1", "T/5", "T/3"]
    problems = {tid: f"p{tid}" for tid in task_ids}
    out_path = tmp_path / "samples.jsonl"
    openrouter_complete.generate_samples(model="test/model", problems=problems, out_path=out_path)
    parsed = [json.loads(line) for line in out_path.read_text().strip().split("\n")]
    assert [row["task_id"] for row in parsed] == task_ids


# ─── B5: per-problem exception writes empty solution + [error] stderr ──────────
def test_generate_samples_per_problem_exception_writes_empty_and_logs(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B5: if _run raises on problem #2, the batch DOES NOT abort — that problem
    gets an empty solution + [error] logged to stderr. Systemic breaks are VISIBLE
    (not silently zero-scored)."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")

    def _fake_run(model, prompt, *, client, max_cost_usd):
        if prompt == "boom":
            raise RuntimeError("simulated provider failure")
        return _FakeResult(text=f"sol({prompt})", cost_usd=0.01)

    monkeypatch.setattr(openrouter_complete, "_run", _fake_run)

    out_path = tmp_path / "samples.jsonl"
    stderr = io.StringIO()
    with redirect_stderr(stderr):
        result_path, total_cost = openrouter_complete.generate_samples(
            model="test/model",
            problems={"T/0": "p0", "T/1": "boom", "T/2": "p2"},
            out_path=out_path,
        )
    # 3 lines, middle one empty
    lines = out_path.read_text().strip().split("\n")
    assert len(lines) == 3
    rows = [json.loads(line) for line in lines]
    assert rows[0]["solution"] == "sol(p0)"
    assert rows[1]["solution"] == "", "failed problem must write empty solution"
    assert rows[2]["solution"] == "sol(p2)"
    # cost = 0.01 + 0 + 0.01 = 0.02 (failed attempt contributes no cost per single-attempt guarantee)
    assert abs(total_cost - 0.02) < 1e-9
    # And stderr got the [error] log line
    err_out = stderr.getvalue()
    assert "[error] T/1" in err_out, f"missing [error] in stderr: {err_out!r}"
    assert "simulated provider failure" in err_out


# ─── B6: finish_reason="length" logs [warn] and writes the (truncated) text ────
def test_generate_samples_length_truncation_logs_warn(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B6: hitting max_tokens (finish_reason='length') means the solution may falsely
    fail eval — the shim MUST log [warn] but still write the truncated text."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")

    def _fake_run(model, prompt, *, client, max_cost_usd):
        return _FakeResult(text="partial_solution_here", cost_usd=0.02, finish_reason="length")

    monkeypatch.setattr(openrouter_complete, "_run", _fake_run)

    out_path = tmp_path / "samples.jsonl"
    stderr = io.StringIO()
    with redirect_stderr(stderr):
        openrouter_complete.generate_samples(
            model="test/model",
            problems={"T/0": "prompt"},
            out_path=out_path,
        )
    rows = [json.loads(line) for line in out_path.read_text().strip().split("\n")]
    assert rows[0]["solution"] == "partial_solution_here", "truncated text must still land in JSONL"
    err_out = stderr.getvalue()
    assert "[warn] T/0" in err_out, f"missing [warn] in stderr: {err_out!r}"
    assert "max_tokens" in err_out


# ─── _resolve_client env handling ──────────────────────────────────────────────
def test_resolve_client_raises_when_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RuntimeError with a clear message if OPENROUTER_API_KEY is neither in env
    NOR loadable by _dotenv.load_env. We mock load_env to a no-op so we don't
    accidentally pick up the fleet-wide fallback (~/.config/fabrik/subagents.env)
    which does carry the real key on the dev machine."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    def _noop_load_env(*a, **kw):
        return []

    monkeypatch.setattr(
        "libs.subagents._dotenv.load_env", _noop_load_env, raising=False
    )
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        openrouter_complete._resolve_client(env_path="/does-not-exist")


def test_complete_returns_empty_string_on_zero_token_stall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """complete() returns '' when Result.text is None (zero-token stall)."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")

    def _fake_run(model, prompt, *, client, max_cost_usd):
        return _FakeResult(text="", cost_usd=0.0)

    monkeypatch.setattr(openrouter_complete, "_run", _fake_run)

    # complete() needs a client — build one from the fake env
    client = openrouter_complete._resolve_client(env_path=None)
    assert openrouter_complete.complete("test/model", "prompt", client=client) == ""
