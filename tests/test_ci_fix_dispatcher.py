"""Behavior tests for scripts/ci_fix_dispatcher.py guard logic.

One test per unattended-safety behavior: dedup, attempt cap, dirty-worktree
skip, branch gate, age gate. These guards are what make the dispatcher safe
to run from cron — a regression in any of them means fix-loop storms or
collisions with sibling agents' working trees.
"""

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "ci_fix_dispatcher", REPO / "scripts" / "ci_fix_dispatcher.py"
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_branch_gate_only_master_main(monkeypatch):
    """Failures on feature branches must be ignored (WIP is not ours to fix)."""
    now = datetime.now(UTC)
    runs = [
        {"databaseId": 1, "workflowName": "CI", "headBranch": "master", "createdAt": _iso(now)},
        {"databaseId": 2, "workflowName": "CI", "headBranch": "feat/x", "createdAt": _iso(now)},
        {"databaseId": 3, "workflowName": "CI", "headBranch": "main", "createdAt": _iso(now)},
    ]
    monkeypatch.setattr(mod, "sh", lambda *a, **k: (0, json.dumps(runs)))
    picked = mod.recent_failures("o/r", max_age_hours=48)
    assert [r["databaseId"] for r in picked] == [1, 3]


def test_local_active_branch_is_eligible(monkeypatch):
    """A failure on the branch the local tree tracks is ours to fix, even when
    that branch has a nonstandard name (real case: mobasak/trading-intelligence)."""
    now = datetime.now(UTC)
    runs = [
        {
            "databaseId": 7,
            "workflowName": "CI",
            "headBranch": "mobasak/trading-intelligence",
            "createdAt": _iso(now),
        },
        {
            "databaseId": 8,
            "workflowName": "CI",
            "headBranch": "some/other-branch",
            "createdAt": _iso(now),
        },
    ]
    monkeypatch.setattr(mod, "sh", lambda *a, **k: (0, json.dumps(runs)))
    picked = mod.recent_failures("o/r", 48, extra_branch="mobasak/trading-intelligence")
    assert [r["databaseId"] for r in picked] == [7]


def test_age_gate_drops_old_failures(monkeypatch):
    """Failures older than the window are stale — never dispatched."""
    now = datetime.now(UTC)
    runs = [
        {
            "databaseId": 1,
            "workflowName": "CI",
            "headBranch": "master",
            "createdAt": _iso(now - timedelta(hours=72)),
        },
        {
            "databaseId": 2,
            "workflowName": "CI",
            "headBranch": "master",
            "createdAt": _iso(now - timedelta(hours=1)),
        },
    ]
    monkeypatch.setattr(mod, "sh", lambda *a, **k: (0, json.dumps(runs)))
    picked = mod.recent_failures("o/r", max_age_hours=48)
    assert [r["databaseId"] for r in picked] == [2]


def test_dirty_worktree_detected(tmp_path, monkeypatch):
    """A dirty tree (sibling agent mid-work) must be detected -> skipped."""
    monkeypatch.setattr(mod, "sh", lambda *a, **k: (0, " M some/file.py\n"))
    assert mod.worktree_dirty(tmp_path) is True
    monkeypatch.setattr(mod, "sh", lambda *a, **k: (0, ""))
    assert mod.worktree_dirty(tmp_path) is False


def test_state_roundtrip_dedup_and_attempt_cap(tmp_path, monkeypatch):
    """State persists run ids (dedup) and attempt counts (cap at 2)."""
    monkeypatch.setattr(mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(mod, "STATE_FILE", tmp_path / "state.json")
    state = mod.load_state()
    assert state == {"runs": {}, "attempts": {}}
    state["runs"]["123"] = {"outcome": "worker-exit-0"}
    state["attempts"]["o/r:CI"] = 2
    mod.save_state(state)
    reloaded = mod.load_state()
    assert "123" in reloaded["runs"]  # dedup source of truth survives restart
    assert reloaded["attempts"]["o/r:CI"] >= mod.MAX_ATTEMPTS  # cap enforceable


def test_corrupt_state_resets_not_crashes(tmp_path, monkeypatch):
    """A corrupt state file must reset cleanly, not crash the cron run."""
    monkeypatch.setattr(mod, "STATE_DIR", tmp_path)
    state_file = tmp_path / "state.json"
    state_file.write_text("{not json")
    monkeypatch.setattr(mod, "STATE_FILE", state_file)
    assert mod.load_state() == {"runs": {}, "attempts": {}}
