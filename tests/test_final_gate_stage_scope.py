"""Tests for final_gate.py shared-tree auto-stage scoping.

Regression guard for the 2026-06-29 operational hazard: the gate auto-staged
with a blanket ``git add -A``, so on every success it swept every OTHER agent's
in-progress files (and the daily pipeline's) into whoever's gate ran last on the
shared /opt/fabrik master. The fix re-stages ONLY the files that were already
staged when the gate started. These tests prove the new scoping against a real
git repo.
"""

from __future__ import annotations

import subprocess

import pytest
import scripts.final_gate as gate


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A real, isolated git repo with one committed file.

    Both the process cwd AND ``gate.PROJECT_ROOT`` are pointed at the temp repo,
    because ``gate.run_cmd`` defaults its cwd to ``PROJECT_ROOT`` — without the
    monkeypatch the gate functions would operate on the real /opt/fabrik tree.
    """

    def git(*args):
        subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True
        )

    git("init", "-q")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    (tmp_path / "base.txt").write_text("base\n")
    git("add", "base.txt")
    git("commit", "-q", "-m", "init")

    monkeypatch.setattr(gate, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def _staged() -> set[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", "--cached"], capture_output=True, text=True
    ).stdout
    return {f for f in out.strip().split("\n") if f}


class TestGetStagedFiles:
    def test_empty_when_nothing_staged(self, repo):
        assert gate.get_staged_files() == set()

    def test_reports_staged_paths(self, repo):
        (repo / "mine.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "mine.py"], check=True)
        assert gate.get_staged_files() == {"mine.py"}


class TestStageChangesScoping:
    def test_scoped_ignores_concurrent_files(self, repo):
        """The core hazard: another actor's dirty/untracked files must NOT be
        swept into the index when we re-stage our own snapshot."""
        (repo / "mine.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "mine.py"], check=True)
        snapshot = gate.get_staged_files()  # {"mine.py"}

        # A concurrent actor leaves files behind in the shared tree.
        (repo / "theirs.py").write_text("y = 2\n")  # untracked
        (repo / "base.txt").write_text("base modified by them\n")  # tracked, unstaged

        ok, _ = gate.stage_changes(snapshot)
        assert ok
        assert _staged() == {"mine.py"}, "must not pull in theirs.py / base.txt"

    def test_scoped_picks_up_autofix_to_own_file(self, repo):
        """A gate autofix to an already-staged file is re-captured."""
        (repo / "mine.py").write_text("x=1\n")
        subprocess.run(["git", "add", "mine.py"], check=True)
        snapshot = gate.get_staged_files()
        # Simulate ruff --format rewriting the working tree copy.
        (repo / "mine.py").write_text("x = 1\n")

        ok, _ = gate.stage_changes(snapshot)
        assert ok
        staged_blob = subprocess.run(
            ["git", "show", ":mine.py"], capture_output=True, text=True
        ).stdout
        assert staged_blob == "x = 1\n"

    def test_empty_snapshot_stages_nothing(self, repo):
        (repo / "theirs.py").write_text("y = 2\n")
        ok, _ = gate.stage_changes(set())
        assert ok
        assert _staged() == set()

    def test_scoped_captures_deletion_of_own_file(self, repo):
        (repo / "mine.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "mine.py"], check=True)
        subprocess.run(["git", "commit", "-q", "-m", "add mine"], check=True)
        subprocess.run(["git", "add", "mine.py"], check=True)  # re-stage to snapshot
        snapshot = {"mine.py"}
        (repo / "mine.py").unlink()

        ok, _ = gate.stage_changes(snapshot)
        assert ok
        # Deletion is staged: the path no longer appears as a tree entry.
        tracked = subprocess.run(
            ["git", "diff", "--cached", "--name-status"], capture_output=True, text=True
        ).stdout
        assert "D\tmine.py" in tracked

    def test_legacy_blanket_stages_everything(self, repo):
        """--stage-all path (paths=None) preserves the old blanket behaviour."""
        (repo / "a.py").write_text("a\n")
        (repo / "b.py").write_text("b\n")
        ok, _ = gate.stage_changes(None)
        assert ok
        assert {"a.py", "b.py"} <= _staged()
