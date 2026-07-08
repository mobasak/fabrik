"""Phase B — workspace.py: worktree + owned_paths disjointness + diff-scope.

The boundary guarantees (TDD-first): a diff that touches a path outside the
agent's owned globs is out of scope; agents whose owned globs overlap are placed
in the same group (serialized), disjoint ones in separate groups (parallel).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from subagents.workspace import (
    changed_paths,
    create_worktree,
    diff_paths,
    disjoint,
    in_scope,
    paths_in_scope,
    remove_worktree,
    worktree_diff,
)

_HAS_GIT = shutil.which("git") is not None


def test_in_scope_flags_out_of_bounds_path() -> None:
    assert in_scope("+++ b/secret.py\n", ["src/*.py"]) is False
    assert in_scope("+++ b/src/a.py\n", ["src/*.py"]) is True


def test_in_scope_empty_owned_is_unrestricted() -> None:
    assert in_scope("+++ b/anything/at/all.py\n", []) is True


def test_in_scope_flags_out_of_bounds_deletion() -> None:
    # a deletion (path on the --- side, +++ is /dev/null) outside scope is caught
    diff = "--- a/secret.py\n+++ /dev/null\n"
    assert in_scope(diff, ["src/*.py"]) is False


def test_disjoint_serializes_overlap() -> None:
    groups = disjoint([["src/a.py"], ["src/a.py"], ["docs/*"]])
    # 0 and 1 own the identical glob → same group; 2 is disjoint → its own group
    as_frozen = {frozenset(g) for g in groups}
    assert frozenset({0, 1}) in as_frozen
    assert frozenset({2}) in as_frozen
    assert len(groups) == 2


def test_disjoint_all_independent_run_parallel() -> None:
    groups = disjoint([["a/*"], ["b/*"], ["c/*"]])
    assert len(groups) == 3
    assert all(len(g) == 1 for g in groups)


def test_disjoint_glob_vs_literal_overlap_is_conservative() -> None:
    # "src/*" covers "src/a.py" → they must share a group (serialize)
    groups = disjoint([["src/*"], ["src/a.py"]])
    assert len(groups) == 1
    assert groups[0] == {0, 1}


def test_diff_paths_parses_added_and_deleted() -> None:
    diff = (
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/gone.py b/gone.py\n--- a/gone.py\n+++ /dev/null\n"
    )
    paths = set(diff_paths(diff))
    assert "x.py" in paths
    assert "gone.py" in paths
    assert "/dev/null" not in paths


def test_diff_paths_ignores_content_lines_masquerading_as_headers() -> None:
    # an ADDED source line that renders as "+++ b/evil" must NOT be read as a header
    diff = (
        "diff --git a/real.py b/real.py\n"
        "--- a/real.py\n"
        "+++ b/real.py\n"
        "@@ -1 +2 @@\n"
        " context\n"
        "+++ b/evil.py\n"  # this is file CONTENT (a line added starting with '++ b/')
    )
    paths = diff_paths(diff)
    assert paths == ["real.py"], f"content line leaked into paths: {paths}"


def test_paths_in_scope() -> None:
    assert paths_in_scope(["src/a.py"], ["src/*.py"]) is True
    assert paths_in_scope(["src/a.py", "other.py"], ["src/*.py"]) is False
    assert paths_in_scope(["anything"], []) is True  # unrestricted


def test_paths_in_scope_star_does_not_cross_slash(tmp_path: Path) -> None:
    """`*` must not span `/` — a deeper nested path is OUT of a single-level glob,
    so an agent can't widen its lane by nesting under an owned prefix."""
    assert paths_in_scope(["docs/a.md"], ["docs/*.md"]) is True
    assert paths_in_scope(["docs/sub/deep.md"], ["docs/*.md"]) is False
    assert paths_in_scope(["src/a/b/c.py"], ["src/*.py"]) is False
    # ** DOES cross / — recursive ownership is opt-in
    assert paths_in_scope(["docs/sub/deep.md"], ["docs/**"]) is True
    assert paths_in_scope(["src/a/b/c.py"], ["src/**/*.py"]) is True


def test_globstar_matches_zero_directories(tmp_path: Path) -> None:
    """`**/` is gitignore-style — it matches ZERO or more dirs, so `docs/**/x.py`
    matches both `docs/x.py` (zero) and `docs/a/x.py`."""
    assert paths_in_scope(["docs/x.py"], ["docs/**/x.py"]) is True
    assert paths_in_scope(["docs/a/b/x.py"], ["docs/**/x.py"]) is True
    assert paths_in_scope(["docs/x.md"], ["docs/**/x.py"]) is False


def test_glob_character_classes(tmp_path: Path) -> None:
    """`[abc]` / `[!abc]` character classes in owned globs work (match fnmatch)."""
    assert paths_in_scope(["src/a.py"], ["src/[ab].py"]) is True
    assert paths_in_scope(["src/b.py"], ["src/[ab].py"]) is True
    assert paths_in_scope(["src/c.py"], ["src/[ab].py"]) is False
    assert paths_in_scope(["src/c.py"], ["src/[!ab].py"]) is True


def test_invalid_glob_char_class_does_not_crash(tmp_path: Path) -> None:
    """An invalid char-class (reversed range → bad regex) must NOT crash the scope
    check — it falls back to literal matching (fail-closed)."""
    # reversed range [z-a] is invalid regex; must not raise
    assert (
        paths_in_scope(["src/a.py"], ["src/[z-a].py"]) is False
    )  # fail-closed, no crash
    # the literal fallback matches the glob string itself
    assert paths_in_scope(["src/[z-a].py"], ["src/[z-a].py"]) is True
    # a trailing-backslash class is also invalid regex — must not crash
    assert paths_in_scope(["src/a.py"], ["src/[\\].py"]) is False


@pytest.mark.skipif(not _HAS_GIT, reason="git not available")
def test_changed_paths_reports_both_sides_of_a_rename(tmp_path: Path) -> None:
    """changed_paths (authoritative) reports BOTH the old and new path of a rename,
    which the textual diff_paths cannot see (a pure rename has no +++/--- lines)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "old.py").write_text("x" * 80 + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)

    wt = create_worktree(str(repo), "agent-r")
    (Path(wt) / "old.py").rename(Path(wt) / "new.py")

    paths = set(changed_paths(wt))
    assert "old.py" in paths and "new.py" in paths, paths
    remove_worktree(str(repo), wt)


@pytest.mark.skipif(not _HAS_GIT, reason="git not available")
def test_worktree_roundtrip_diff_not_applied(tmp_path: Path) -> None:
    """create → edit in worktree → diff shows it → caller repo UNTOUCHED → remove."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)

    wt = create_worktree(str(repo), "agent-1")
    assert Path(wt).is_dir()
    (Path(wt) / "new.txt").write_text("agent work\n", encoding="utf-8")

    diff = worktree_diff(wt)
    assert "new.txt" in diff
    assert "agent work" in diff

    # the CALLER repo's TRACKED tree must be pristine — nothing was applied to it.
    # The worktree lives under <repo>/.tmp/ (scratch, gitignored in real use), so
    # `?? .tmp/` is the only permitted status line; no tracked file may change.
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    leaked = [
        ln
        for ln in status.stdout.splitlines()
        if ln.strip() and not ln.strip().endswith(".tmp/")
    ]
    assert leaked == [], f"worktree edit leaked into the caller repo: {leaked}"
    assert not (repo / "new.txt").exists()

    remove_worktree(str(repo), wt)
    assert not Path(wt).exists()
