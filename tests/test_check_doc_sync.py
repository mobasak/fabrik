"""Tests for the unified Doc Sync Matrix gate (scripts/enforcement/check_doc_sync.py).

Drives the real script over a throwaway git repo with staged changes — it reads
`git diff --cached`, so staging is how we exercise each rule. ERROR rows must fail
(exit 1); WARN rows must pass (exit 0) while printing a warning.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CHECK = Path(__file__).resolve().parents[1] / "scripts" / "enforcement" / "check_doc_sync.py"
CHANGELOG_OK = "# Changelog\n\n## [Unreleased]\n\n### Added\n- a real entry\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=15)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    return tmp_path


def _write(repo: Path, rel: str, content: str = "x\n") -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _stage(repo: Path, *rels: str) -> None:
    subprocess.run(["git", "add", "--", *rels], cwd=repo, check=True, timeout=15)


def _run(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK)], cwd=repo, capture_output=True, text=True, timeout=30
    )


def test_significant_code_without_changelog_fails(repo: Path) -> None:
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _stage(repo, "src/app/handler.py")
    r = _run(repo)
    assert r.returncode == 1 and "CHANGELOG.md not updated" in r.stdout


def test_significant_code_with_changelog_passes(repo: Path) -> None:
    _write(repo, "src/app/handler.py", "def f():\n    return 1\n")
    _write(repo, "CHANGELOG.md", CHANGELOG_OK)
    _stage(repo, "src/app/handler.py", "CHANGELOG.md")
    r = _run(repo)
    assert r.returncode == 0, r.stdout


def test_tests_only_change_needs_no_changelog(repo: Path) -> None:
    _write(repo, "tests/test_x.py", "def test_x():\n    assert True\n")
    _stage(repo, "tests/test_x.py")
    assert _run(repo).returncode == 0


def test_env_example_without_configuration_fails(repo: Path) -> None:
    _write(repo, ".env.example", "FOO=bar\n")
    _stage(repo, ".env.example")
    r = _run(repo)
    assert r.returncode == 1 and "CONFIGURATION.md" in r.stdout


def test_new_file_without_index_warns_not_blocks(repo: Path) -> None:
    # A brand-new doc file with no INDEX update → WARN (not block): exit 0 + warning.
    _write(repo, "docs/guides/new-guide.md", "# guide\n")
    _stage(repo, "docs/guides/new-guide.md")
    r = _run(repo)
    assert r.returncode == 0, r.stdout
    assert "INDEX.md not updated" in r.stdout


def test_compose_change_is_warn_only(repo: Path) -> None:
    # PORTS is a fuzzy row → WARN, never blocks. (Also touches INDEX+CHANGELOG to
    # isolate the PORTS rule: stage them so only the PORTS warning can surface.)
    _write(repo, "compose.yaml", "services: {}\n")
    _write(repo, "CHANGELOG.md", CHANGELOG_OK)
    _write(repo, "INDEX.md", "# idx\n")
    _stage(repo, "compose.yaml", "CHANGELOG.md", "INDEX.md")
    r = _run(repo)
    assert r.returncode == 0, r.stdout
    assert "PORTS.md" in r.stdout  # warning surfaced, but not blocking


def test_docs_only_change_passes(repo: Path) -> None:
    _write(repo, "docs/QUICKSTART.md", "# qs\n")
    _stage(repo, "docs/QUICKSTART.md")
    assert _run(repo).returncode == 0
