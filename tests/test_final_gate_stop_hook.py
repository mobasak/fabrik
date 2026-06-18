"""Tests for the Claude Code Stop hook decision logic (.claude/hooks/final_gate_stop.py).

Highest-risk path: the ``decide()`` loop-guard — it must block a red gate but never
trap the session, and must skip when nothing changed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "final_gate_stop.py"
_spec = importlib.util.spec_from_file_location("final_gate_stop", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def test_clean_tree_allows() -> None:
    # No uncommitted changes → never gate, never block.
    assert hook.decide(git_dirty=False, gate_passed=False, attempts=5) == ("allow", 0)


def test_green_gate_allows_and_resets() -> None:
    assert hook.decide(git_dirty=True, gate_passed=True, attempts=2) == ("allow", 0)


def test_red_gate_blocks_and_increments() -> None:
    assert hook.decide(git_dirty=True, gate_passed=False, attempts=0) == ("block", 1)
    assert hook.decide(git_dirty=True, gate_passed=False, attempts=1) == ("block", 2)


def test_red_gate_blocks_up_to_cap() -> None:
    # CAP defaults to 3 → attempts 2 → 3 still blocks.
    assert hook.decide(git_dirty=True, gate_passed=False, attempts=2) == ("block", 3)


def test_red_gate_over_cap_allows_with_warning() -> None:
    # Past the cap → allow_warn so the session is never trapped.
    assert hook.decide(git_dirty=True, gate_passed=False, attempts=3) == ("allow_warn", 0)
    assert hook.decide(git_dirty=True, gate_passed=False, attempts=9) == ("allow_warn", 0)
