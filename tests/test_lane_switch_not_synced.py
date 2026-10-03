"""T08 (plan 2026-10-02-plan-1) — row 7: what the lane ships and what it keeps.

`scripts/task_lane.py` is imported by the fleet-synced `command_run.py`, so it rides the same
manifest list AND the governance-sync trigger regex; `.fabrik/lane.json` is the REPO's own switch
(spec § The delta D12) and neither ships nor triggers a sync — and the hub's enable commit carries
that path alone, so turning the lane on distributes nothing.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fabrik_synced_manifest as m  # noqa: E402

LANE = ".fabrik/lane.json"


def _sync_regex() -> re.Pattern[str]:
    cfg = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = [h for repo in cfg["repos"] for h in repo.get("hooks", [])]
    (hook,) = [h for h in hooks if h.get("id") == "governance-sync"]
    return re.compile(hook["files"])


def test_task_lane_ships_with_command_run_and_triggers_the_sync() -> None:
    assert "task_lane.py" in m.CORE_SCRIPTS
    assert "command_run.py" in m.CORE_SCRIPTS
    rx = _sync_regex()
    assert rx.search("scripts/task_lane.py")
    assert rx.search("scripts/command_run.py")


def test_the_lane_switch_is_neither_synced_nor_a_sync_trigger(tmp_path: Path) -> None:
    assert not _sync_regex().search(LANE)
    dests = {str(dst.relative_to(tmp_path)) for _src, dst in m.iter_synced_pairs(tmp_path, ROOT)}
    assert LANE not in dests
    assert LANE not in m.synced_project_paths(ROOT)


def test_the_hub_enable_commit_carries_the_switch_alone() -> None:
    """Once the hub has opted in, the commit that ADDED the switch touches no other path."""
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", LANE],
        capture_output=True,
        timeout=30,
    )
    if tracked.returncode != 0:
        pytest.skip("this checkout has not committed the lane switch")
    first = subprocess.run(
        ["git", "-C", str(ROOT), "log", "--diff-filter=A", "--format=%H", "--", LANE],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    ).stdout.split()[-1]
    paths = subprocess.run(
        ["git", "-C", str(ROOT), "show", "--name-only", "--format=", first],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    ).stdout.split()
    assert paths == [LANE]
