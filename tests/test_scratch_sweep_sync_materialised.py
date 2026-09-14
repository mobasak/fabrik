"""A worktree the governance sync wrote into is not "dirty" (T12.23, 01M23JK2R — reported by wef3).

The sync MATERIALISES manifest-owned files into every registered worktree, so a worktree nobody
has touched reads `git status --porcelain` non-empty and is classified `wt-dirty` — never
removable, forever. Those paths are not uncommitted work by any session; nothing authored them.

⚠️ The exemption is NARROW and these tests are mostly about its edges: a manifest-owned path counts
only when it is byte-identical to the hub's copy. A hand-edited synced file keeps the worktree
dirty, because removing a worktree is destructive and a destructive verdict does not get to assume
which side of that line an edit falls on.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path("/opt/fabrik")
SWEEP = REPO / "scripts" / "scratch_sweep.py"


@pytest.fixture
def sweep():
    name = "scratch_sweep_t1223"
    spec = importlib.util.spec_from_file_location(name, SWEEP)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    yield mod
    sys.modules.pop(name, None)


def _a_synced_path() -> str:
    """One real manifest-owned FILE path, taken from the manifest rather than hardcoded."""
    sys.path.insert(0, str(REPO / "scripts"))
    import fabrik_synced_manifest as fsm

    for group in fsm.gitignore_dest_paths().values():
        for dest in group:
            if not dest.endswith("/") and (REPO / dest).is_file():
                return dest
    pytest.skip("no manifest-owned file present in the hub")


def test_an_unmodified_synced_file_is_recognised_as_the_syncs_own_output(
    sweep, tmp_path: Path
) -> None:
    rel = _a_synced_path()
    dest = tmp_path / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes((REPO / rel).read_bytes())
    assert sweep._is_sync_materialised(tmp_path, rel) is True


def test_a_hand_edited_synced_file_is_not(sweep, tmp_path: Path) -> None:
    """The load-bearing edge: one appended byte and the worktree stays dirty."""
    rel = _a_synced_path()
    dest = tmp_path / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes((REPO / rel).read_bytes() + b"\n# a hand edit\n")
    assert sweep._is_sync_materialised(tmp_path, rel) is False


def test_a_path_the_manifest_does_not_own_is_never_exempt(sweep, tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mine.py").write_text("x = 1\n")
    assert sweep._is_sync_materialised(tmp_path, "src/mine.py") is False


def test_a_missing_file_keeps_the_worktree_dirty(sweep, tmp_path: Path) -> None:
    """Any failure to answer must fail toward KEEPING the work — the verdict it feeds is
    destructive."""
    rel = _a_synced_path()
    assert sweep._is_sync_materialised(tmp_path, rel) is False


def test_quoted_status_paths_are_unwrapped(sweep, tmp_path: Path) -> None:
    """`git status --porcelain` quotes a path containing unusual characters; the membership test
    reads the NAME, so an unstripped quote would make every such path look unowned — safe, but it
    would silently re-open the very class this closes for any repo that has one."""
    rel = _a_synced_path()
    dest = tmp_path / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes((REPO / rel).read_bytes())
    assert sweep._is_sync_materialised(tmp_path, f'"{rel}"') is True
