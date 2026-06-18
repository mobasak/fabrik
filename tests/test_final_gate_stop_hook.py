"""Tests for the Claude Code SessionStart/Stop hook (.claude/hooks/final_gate_stop.py).

Highest-risk paths:
- ``decide()`` loop-guard (block red, never trap, skip when clean).
- baseline diffing: the Stop hook must block ONLY on failures the session introduced,
  never on inherited project debt (the real bug this design fixes).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "final_gate_stop.py"
_spec = importlib.util.spec_from_file_location("final_gate_stop", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

# --- pure decide() loop-guard -------------------------------------------------


def test_clean_tree_allows() -> None:
    assert hook.decide(git_dirty=False, has_new_failures=True, attempts=5) == ("allow", 0)


def test_no_new_failures_allows() -> None:
    assert hook.decide(git_dirty=True, has_new_failures=False, attempts=2) == ("allow", 0)


def test_new_failures_block_and_increment() -> None:
    assert hook.decide(git_dirty=True, has_new_failures=True, attempts=0) == ("block", 1)
    assert hook.decide(git_dirty=True, has_new_failures=True, attempts=1) == ("block", 2)


def test_new_failures_block_up_to_cap() -> None:
    assert hook.decide(git_dirty=True, has_new_failures=True, attempts=2) == ("block", 3)


def test_over_cap_allows_with_warning() -> None:
    assert hook.decide(git_dirty=True, has_new_failures=True, attempts=3) == ("allow_warn", 0)


# --- integration: baseline diffing (the real bug) -----------------------------

_FAKE_GATE = """#!/usr/bin/env python3
import json, os, sys
fails = [f for f in os.environ.get("FAKE_FAILS", "").split(",") if f]
if not fails:
    print(json.dumps({"status": "success", "failures": []})); sys.exit(0)
print(json.dumps({"status": "failure", "failures": [{"check": c} for c in fails]}))
sys.exit(1)
"""


@pytest.fixture
def fake_project(tmp_path: Path) -> Path:
    p = tmp_path / "proj"
    (p / "scripts").mkdir(parents=True)
    (p / "scripts" / "final_gate.py").write_text(_FAKE_GATE)
    subprocess.run(["git", "init", "-q"], cwd=p, check=True, timeout=15)
    (p / "work.txt").write_text("uncommitted")  # dirty worktree
    return p


def _run_stop(project: Path, sid: str, fake_fails: str, *, baseline: list[str] | None) -> str:
    """Run the Stop hook; return stdout (block JSON or empty=allow)."""
    bl = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-baseline-{sid}.json"
    ctr = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.attempts"
    ctr.unlink(missing_ok=True)
    if baseline is None:
        bl.unlink(missing_ok=True)
    else:
        bl.write_text(json.dumps(baseline))
    env = {**os.environ, "FAKE_FAILS": fake_fails}
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps({"session_id": sid, "cwd": str(project), "hook_event_name": "Stop"}),
        capture_output=True, text=True, timeout=60, env=env,
    )
    bl.unlink(missing_ok=True)
    ctr.unlink(missing_ok=True)
    return proc.stdout.strip()


def test_inherited_failure_does_not_block(fake_project: Path) -> None:
    # Baseline already has check A; gate still fails only on A → no NEW failure → allow.
    out = _run_stop(fake_project, "s_inherit", "A", baseline=["A"])
    assert out == "", f"should allow (inherited debt), got: {out}"


def test_session_introduced_failure_blocks(fake_project: Path) -> None:
    # Baseline has A; gate now fails A AND B → B is new → block, naming only B.
    out = _run_stop(fake_project, "s_new", "A,B", baseline=["A"])
    assert out, "should block on the new failure"
    payload = json.loads(out)
    assert payload["decision"] == "block"
    assert "B" in payload["reason"] and "A" not in payload["reason"].split("New failing checks:")[1]


def test_missing_baseline_fails_open(fake_project: Path) -> None:
    # No baseline snapshot (SessionStart didn't run) → can't attribute → allow.
    out = _run_stop(fake_project, "s_nobaseline", "A,B", baseline=None)
    assert out == "", f"should fail-open without a baseline, got: {out}"


def test_green_gate_allows(fake_project: Path) -> None:
    out = _run_stop(fake_project, "s_green", "", baseline=["A"])
    assert out == "", f"green gate should allow, got: {out}"


def test_baseline_mode_writes_snapshot(fake_project: Path) -> None:
    sid = "s_baseline_mode"
    bl = Path(hook.tempfile.gettempdir()) / f"fabrik-gate-baseline-{sid}.json"
    bl.unlink(missing_ok=True)
    env = {**os.environ, "FAKE_FAILS": "A,C"}
    subprocess.run(
        [sys.executable, str(_HOOK), "--baseline"],
        input=json.dumps({"session_id": sid, "cwd": str(fake_project)}),
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert bl.exists(), "baseline mode must write a snapshot"
    assert set(json.loads(bl.read_text())) == {"A", "C"}
    bl.unlink(missing_ok=True)
