# AFTER-EDIT: scripts/enforcement/check_doc_sprawl.py
"""Behavior contract for the sprawl gate's new-file detection (docs-truth plan Phase F).

The defect this closes: ``is_tracked()`` used ``git ls-files --error-unmatch`` — an
INDEX lookup — so any brand-new .md that was merely ``git add``-ed bypassed the
default-deny allowlist entirely. The fix: a path counts as "existing" only if it is
present in HEAD, or its staged status is a rename (R*) from a tracked path; otherwise
the allowlist runs even when the file is staged.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path("/opt/fabrik")
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))


def _git(tmp_repo, *args):
    return subprocess.run(
        ["git", *args], cwd=tmp_repo, capture_output=True, text=True, check=False
    )


@pytest.fixture()
def tmp_repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "docs" / "operations").mkdir(parents=True)
    (tmp_path / "docs" / "archive").mkdir(parents=True)
    seed = tmp_path / "docs" / "operations" / "seed.md"
    seed.write_text("# seed\n")
    _git(tmp_path, "add", "docs/operations/seed.md")
    _git(tmp_path, "commit", "-qm", "seed")
    return tmp_path


def _exists_for_gate(tmp_repo, rel):
    """Mirror of the gate's fixed existing-file test, run against a scratch repo."""
    from check_doc_sprawl import path_is_existing  # the fixed helper

    return path_is_existing(Path(rel), tmp_repo)


def test_staged_new_md_in_blocked_dir_is_treated_as_new(tmp_repo):
    """(a) A brand-new staged .md must NOT count as existing — allowlist must run."""
    p = tmp_repo / "docs" / "operations" / "brand-new.md"
    p.write_text("# new\n")
    _git(tmp_repo, "add", "docs/operations/brand-new.md")
    assert _exists_for_gate(tmp_repo, "docs/operations/brand-new.md") is False


def test_git_mv_into_blocked_dir_is_allowed(tmp_repo):
    """(b) A git mv of a tracked file counts as existing (rename, content pre-existed)."""
    _git(tmp_repo, "mv", "docs/operations/seed.md", "docs/operations/moved.md")
    assert _exists_for_gate(tmp_repo, "docs/operations/moved.md") is True


def test_tracked_edit_is_allowed(tmp_repo):
    """(c) An edit to a file already in HEAD counts as existing."""
    p = tmp_repo / "docs" / "operations" / "seed.md"
    p.write_text("# seed edited\n")
    assert _exists_for_gate(tmp_repo, "docs/operations/seed.md") is True


def test_untracked_new_file_is_new(tmp_repo):
    """(d) An untracked brand-new file is (still) new — regression guard."""
    p = tmp_repo / "docs" / "operations" / "untracked.md"
    p.write_text("# u\n")
    assert _exists_for_gate(tmp_repo, "docs/operations/untracked.md") is False
