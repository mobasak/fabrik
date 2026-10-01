"""W-20a8e9f1: the sixth cause stops naming edits that left nothing behind.

A session that edits a file and then restores it, or creates one and deletes it, has no change to
review — yet the transcript still records the edit, so no later review window could ever cover it
and the Stop hook re-blocked on every turn. The MIRROR is pinned too: a file that equals HEAD only
because the session COMMITTED it must still count, or committing would dodge the review.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import time
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "final_gate_stop.py"
_spec = importlib.util.spec_from_file_location("fgs_withdrawn", _HOOK)
hook = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(hook)


_ISOLATED = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def _git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={**(env or os.environ), **_ISOLATED},
    )


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    (root / "kept.py").write_text("x = 1\n")
    (root / "gone.py").write_text("y = 1\n")
    _git(root, "add", "kept.py", "gone.py")
    old = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00",
    }
    _git(root, "commit", "-q", "-m", "base", env=old)  # outside every edit window
    return root


@pytest.fixture(autouse=True)
def _no_user_git_config(monkeypatch) -> None:
    """The hook's own git calls must not read the user's global config either (O8)."""
    for k, v in _ISOLATED.items():
        monkeypatch.setenv(k, v)


def _names(root: Path | None, files: list[str], floor: float) -> list[str]:
    now = int(time.time())
    return hook._unreviewed_spontaneous_files(None, dict.fromkeys(files, now), floor, None, root)


def test_an_edit_restored_to_head_and_a_created_then_deleted_file_are_not_named(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "kept.py").write_text("x = 2\n")
    (root / "kept.py").write_text("x = 1\n")  # restored byte-for-byte
    (root / "scratch.py").write_text("z = 1\n")
    (root / "scratch.py").unlink()  # created, then withdrawn
    floor = time.time() - 3600
    assert _names(root, ["kept.py", "scratch.py"], floor) == []


def test_without_a_root_nothing_is_dropped(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    assert root  # the repo exists; the call simply is not told where it is
    assert _names(None, ["kept.py"], time.time() - 3600) == ["kept.py"]


def test_a_file_still_changed_is_named(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "kept.py").write_text("x = 2\n")
    (root / "new.py").write_text("n = 1\n")
    (root / "gone.py").unlink()  # a deleted TRACKED file is a change
    assert _names(root, ["gone.py", "kept.py", "new.py"], time.time() - 3600) == [
        "gone.py",
        "kept.py",
        "new.py",
    ]


def test_a_file_that_equals_head_because_it_was_committed_is_still_named(tmp_path: Path) -> None:
    """The mirror: committing the work must not be the way past the review."""
    root = _repo(tmp_path)
    floor = time.time() - 3600
    (root / "kept.py").write_text("x = 3\n")
    _git(root, "commit", "-q", "-am", "the session's own work")
    assert _names(root, ["kept.py"], floor) == ["kept.py"]


def test_a_git_failure_drops_nothing(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    assert _names(not_a_repo, ["kept.py"], time.time() - 3600) == ["kept.py"]


def test_a_rename_keeps_both_paths_named(tmp_path: Path) -> None:
    """O6/S1: the origin of a staged rename rides the next -z field, never an entry of its own."""
    root = _repo(tmp_path)
    _git(root, "mv", "kept.py", "moved.py")
    assert _names(root, ["kept.py", "moved.py"], time.time() - 3600) == ["kept.py", "moved.py"]


def test_work_moved_into_a_stash_or_another_branch_is_still_named(tmp_path: Path) -> None:
    """O4: the mirror reads every ref and the reflog, not only HEAD's history."""
    root = _repo(tmp_path)
    floor = time.time() - 3600
    (root / "kept.py").write_text("x = 9\n")
    _git(root, "stash")
    _git(root, "checkout", "-q", "-b", "side")
    (root / "gone.py").write_text("y = 9\n")
    _git(root, "commit", "-q", "-am", "elsewhere")
    _git(root, "checkout", "-q", "master")
    assert _names(root, ["gone.py", "kept.py"], floor) == ["gone.py", "kept.py"]


def test_an_edited_ignored_file_is_still_named(tmp_path: Path) -> None:
    """O7: a gitignored code file that still exists is a change git status hides by default."""
    root = _repo(tmp_path)
    (root / ".gitignore").write_text("local.py\n")
    (root / "local.py").write_text("z = 1\n")
    assert _names(root, ["local.py"], time.time() - 3600) == ["local.py"]


def test_a_committed_non_ascii_file_is_still_named(tmp_path: Path) -> None:
    """O2: `log -z` keeps the path raw, so core.quotePath cannot hide a committed file."""
    root = _repo(tmp_path)
    floor = time.time() - 3600
    (root / "é.py").write_text("e = 1\n")
    _git(root, "add", "é.py")
    _git(root, "commit", "-q", "-m", "unicode")
    assert _names(root, ["é.py"], floor) == ["é.py"]


def test_a_root_below_the_top_level_drops_nothing(tmp_path: Path) -> None:
    """O1/S2: repo-relative names only match git's output at the top level."""
    root = _repo(tmp_path)
    (root / "sub").mkdir()
    (root / "kept.py").write_text("x = 2\n")
    assert _names(root / "sub", ["kept.py", "scratch.py"], time.time() - 3600) == [
        "kept.py",
        "scratch.py",
    ]


def test_one_check_serves_every_name(tmp_path: Path, monkeypatch) -> None:
    """O3: the filter asks once for the whole list, never once per name."""
    root = _repo(tmp_path)
    calls: list[int] = []
    real = hook._withdrawn_edits

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(hook, "_withdrawn_edits", counting)
    _names(root, ["a.py", "b.py", "c.py", "d.py"], time.time() - 3600)
    assert len(calls) == 1


def test_a_file_in_an_ignored_directory_is_still_named(tmp_path: Path) -> None:
    """N1/O10: git reports an ignored directory as `dir/`, so the prefix must cover its files."""
    root = _repo(tmp_path)
    (root / ".gitignore").write_text("build/\n")
    (root / "build").mkdir()
    (root / "build" / "x.py").write_text("b = 1\n")
    assert _names(root, ["build/x.py"], time.time() - 3600) == ["build/x.py"]


def test_a_name_starting_with_a_colon_is_a_path_not_pathspec_magic(tmp_path: Path) -> None:
    """O11: without --literal-pathspecs, ':x.py' matched nothing and was dropped."""
    root = _repo(tmp_path)
    (root / ":x.py").write_text("c = 1\n")
    assert _names(root, [":x.py"], time.time() - 3600) == [":x.py"]
