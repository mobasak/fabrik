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


def test_non_role_file_is_not_injectable() -> None:
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


# --- round-2 closer findings ------------------------------------------------------------------


def test_roles_allowlist_matches_claude_md_row() -> None:
    """The _ROLES tuple and CLAUDE.md's Agent-Name row must never drift (the extension trap:
    a 4th role added everywhere except _ROLES would silently no-op its charter)."""
    import re

    claude_md = (REPO / "CLAUDE.md").read_text()
    m = re.search(r"^\| `Agent-Name` \| (.+?) \|", claude_md, re.M)
    assert m, "Agent-Name row missing from CLAUDE.md provenance table"
    row_roles = set(re.findall(r"`([a-z-]+)`", m.group(1)))
    hook_src = HOOK.read_text()
    hm = re.search(r"_ROLES = \(([^)]*)\)", hook_src)
    assert hm
    hook_roles = set(re.findall(r'"([a-z-]+)"', hm.group(1)))
    assert hook_roles == row_roles, (hook_roles, row_roles)


def test_symlinked_agents_directory_is_contained(tmp_path: Path) -> None:
    """A symlinked agents/ DIRECTORY resolving outside the repo root is never read."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "infra.md").write_text("SECRET-DIR-BODY\n")
    repo = tmp_path / "repo"
    (repo / "docs" / "reference").mkdir(parents=True)
    (repo / "docs" / "reference" / "agents").symlink_to(outside, target_is_directory=True)
    r = _run("infra", cwd=repo)
    assert r.returncode == 0
    assert "SECRET-DIR-BODY" not in r.stdout


def test_truncation_binds_in_bytes_for_multibyte(tmp_path: Path) -> None:
    """A CJK charter must be capped in BYTES (the old char-read emitted 3x the cap)."""
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / "infra.md").write_text("世" * 40_000, encoding="utf-8")  # 3 bytes/char
    r = _run("infra", cwd=tmp_path)
    assert r.returncode == 0
    assert "TRUNCATED" in r.stdout
    assert len(r.stdout.encode()) < 33_500  # cap + banner/fence margin only
