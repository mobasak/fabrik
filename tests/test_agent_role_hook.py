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


# --- Phase A review findings (native closer) — each pins a fleet-safety contract ---------------


def test_traversal_name_is_silent_noop() -> None:
    """CLAUDE_AGENT='../../CONFIGURATION' must never inject a file outside agents/."""
    r = _run("../../CONFIGURATION")
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_charter_body_is_delimited() -> None:
    """Plan interface: the charter body is fenced by explicit delimiters, so the overlay's
    end is unambiguous next to CLAUDE.md's own sections."""
    r = _run("infra")
    assert "--- charter begin ---" in r.stdout
    assert "--- charter end ---" in r.stdout
    body = r.stdout.split("--- charter begin ---", 1)[1]
    assert "Mandate" in body.split("--- charter end ---", 1)[0]


def test_oversized_charter_truncates_loudly(tmp_path: Path) -> None:
    """A cut charter must SAY it was cut — the safety clauses live at the tail."""
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / "infra.md").write_text("x" * 40_000 + "\nTAIL-MARKER\n")
    r = _run("infra", cwd=tmp_path)
    assert r.returncode == 0
    assert "TRUNCATED" in r.stdout
    assert len(r.stdout.encode()) < 40_000  # byte cap actually binds


def test_non_role_file_is_not_injectable(tmp_path: Path) -> None:
    """Only the pinned roles are charters — a log/stray file in agents/ never injects."""
    r = _run("kaizen-log-infra")
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_symlinked_charter_outside_repo_is_silent(tmp_path: Path) -> None:
    """'Never reads outside the repo' is enforced by construction (realpath containment)."""
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("SECRET-OUTSIDE\n")
    (d / "infra.md").symlink_to(outside)
    r = _run("infra", cwd=tmp_path)
    assert r.returncode == 0
    assert "SECRET-OUTSIDE" not in r.stdout


def test_empty_charter_is_silent(tmp_path: Path) -> None:
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / "infra.md").write_text("   \n")
    r = _run("infra", cwd=tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_cwd_fallback_without_project_dir() -> None:
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_AGENT", "CLAUDE_PROJECT_DIR")}
    env["CLAUDE_AGENT"] = "infra"
    r = subprocess.run([sys.executable, str(HOOK)], capture_output=True, text=True,
                       timeout=30, env=env, cwd=REPO)
    assert r.returncode == 0
    assert "AGENT ROLE: infra" in r.stdout
