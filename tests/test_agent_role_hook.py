"""Behavior-Contract tests for the SessionStart agent-role hook (.claude/hooks/agent_role.py).

The hook distributes fleet-wide (governance-sync trigger surface), so its fleet-safety
behaviors (b)-(d) are load-bearing: a project with no charters must see a silent no-op.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / ".claude" / "hooks" / "agent_role.py"


def _run(env_val: str | None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_AGENT"}
    if env_val is not None:
        env["CLAUDE_AGENT"] = env_val
    env["CLAUDE_PROJECT_DIR"] = str(cwd or REPO)
    return subprocess.run(
        [sys.executable, str(HOOK)], capture_output=True, text=True, timeout=30, env=env
    )


def test_named_role_injects_charter() -> None:
    r = _run("infra")
    assert r.returncode == 0
    assert "AGENT ROLE: infra" in r.stdout
    assert "Mandate" in r.stdout  # charter body actually included


def test_unset_is_silent_noop() -> None:
    r = _run(None)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_bogus_value_is_silent_noop() -> None:
    r = _run("xyz-not-a-role")
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_missing_charter_file_is_silent_noop(tmp_path: Path) -> None:
    # a project tree with the hook but no charters (the fleet case)
    r = _run("infra", cwd=tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == ""
