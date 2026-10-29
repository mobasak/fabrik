"""A worktree the governance sync wrote into is not "dirty" (T12.23, 01M23JK2R — reported by wef3).

The sync MATERIALISES manifest-owned files into every registered worktree, so a worktree nobody
has touched reads `git status --porcelain -z` non-empty and is classified `wt-dirty` — never
removable, forever. Those paths are not uncommitted work by any session; nothing authored them.

⚠️ The exemption is NARROW and these tests are mostly about its edges: a manifest-owned path counts
only when it is byte-identical to the hub's copy. A hand-edited synced file keeps the worktree
dirty, because removing a worktree is destructive and a destructive verdict does not get to assume
which side of that line an edit falls on.
"""

from __future__ import annotations

import importlib.util
import subprocess
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


def _hub_source_for(rel: str) -> Path:
    """The hub file the manifest maps to `rel` — NOT `FABRIK_ROOT / rel` (15 pairs differ)."""
    sys.path.insert(0, str(REPO / "scripts"))
    import fabrik_synced_manifest as fsm

    for src, dest in fsm.iter_synced_pairs(Path("/nonexistent-project")):
        if dest == Path("/nonexistent-project") / rel:
            return src
    pytest.skip(f"the manifest maps no source to {rel}")


def _hub_head_bytes(src: Path) -> bytes:
    """What the sync would WRITE for this source: HEAD's blob for a tracked file, else the tree."""
    rel = src.resolve().relative_to(REPO.resolve()).as_posix()
    proc = subprocess.run(
        ["git", "show", f"HEAD:{rel}"], cwd=REPO, capture_output=True, check=False
    )
    return proc.stdout if proc.returncode == 0 else src.read_bytes()


def _a_synced_path() -> str:
    """One real manifest-owned FILE path, taken from the manifest rather than hardcoded."""
    sys.path.insert(0, str(REPO / "scripts"))
    import fabrik_synced_manifest as fsm

    # Prefer a NESTED dest: two graders below expand a directory entry, and a root-level file
    # leaves them skipped — a skipped grader is not a grader.
    flat: list[str] = []
    for group in fsm.gitignore_dest_paths().values():
        for dest in group:
            if dest.endswith("/") or not (REPO / dest).is_file():
                continue
            if "/" in dest:
                return dest
            flat.append(dest)
    if flat:
        return flat[0]
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


def test_status_paths_are_taken_verbatim(sweep, tmp_path: Path) -> None:
    """The caller reads `git status --porcelain -z` (W-fe6e0ed3), which never C-quotes a path, so
    `_sync_materialised_paths` takes each name verbatim: stripping quotes without unescaping resolved
    the wrong path. A plain rel is recognised; a quoted one is not unwrapped into it."""
    rel = _a_synced_path()
    src = _hub_source_for(rel)
    dest = tmp_path / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_hub_head_bytes(src))
    assert sweep._sync_materialised_paths(tmp_path, [rel]) == {rel}
    assert sweep._sync_materialised_paths(tmp_path, [f'"{rel}"']) == set()


def test_a_z_listing_with_a_git_warning_is_unreadable(sweep, monkeypatch) -> None:
    """`_git` merged stderr into stdout, so on rc 0 a warning such as "could not open directory"
    became a fake NUL-separated status entry — and the listing it rode on is INCOMPLETE (the
    unreadable directory's files are missing from it). A machine-parsed `-z` call takes stdout
    alone and reads a warning as unreadable, so the verdict fails toward keeping the worktree."""
    import subprocess

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(
            cmd, 0, stdout="?? a.txt\0", stderr="warning: could not open directory 'locked/'\n"
        )

    monkeypatch.setattr(sweep.subprocess, "run", fake_run)
    rc, entries = sweep._status_z(Path("/nonexistent"))
    assert rc != 0 and entries == []


def test_an_unreadable_ignored_listing_keeps_the_worktree(sweep, monkeypatch) -> None:
    """`_ignored_data` read an unreadable `--ignored` listing as "no ignored data" — fail-OPEN on the
    one check that guards NEVER-delete data from `worktree remove --force` (W-d81efab9 review A-O5).
    It now reports the unreadable listing as a hit, so both callers keep the worktree."""
    import subprocess

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(
            cmd, 0, stdout="!! data/x.db\0", stderr="warning: could not open directory 'x/'\n"
        )

    monkeypatch.setattr(sweep.subprocess, "run", fake_run)
    assert sweep._ignored_data(Path("/nonexistent"), None)


def test_the_hub_source_is_resolved_through_the_manifest_not_assumed(sweep, tmp_path: Path) -> None:
    """Phase E review: 15 of the manifest's 208 `(src, dest)` pairs have `src != dest`. The first
    cut compared `FABRIK_ROOT / rel`, so `.worktreeinclude` — which has no hub file at its dest path
    at all — could never be recognised, and it blocked 90 of 118 dirty worktrees by itself."""
    src = sweep._sync_source_for(tmp_path, ".worktreeinclude")
    assert src is not None, "the manifest maps .worktreeinclude; the dest path does not exist"
    assert src != Path("/opt/fabrik/.worktreeinclude")


def test_an_all_untracked_directory_entry_is_expanded(sweep, tmp_path: Path) -> None:
    """`git status --porcelain` collapses an all-untracked directory to `dir/`. `read_bytes` on a
    directory raises `IsADirectoryError`, so the first cut answered "not sync output" for it —
    measured, `libs/health_probe/` blocked 62 of 118 worktrees that way."""
    rel = _a_synced_path()
    src = _hub_source_for(rel)
    parent = rel.rsplit("/", 1)[0] + "/" if "/" in rel else None
    if parent is None:
        pytest.skip("the sampled synced file is at the root; no directory entry to expand")
    dest = tmp_path / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_hub_head_bytes(src))
    got = sweep._sync_materialised_paths(tmp_path, [parent])
    assert got == {parent}, f"the directory entry was not expanded: {got}"


def test_a_directory_holding_one_authored_file_is_not_sync_only(sweep, tmp_path: Path) -> None:
    """The mirror: expanding a directory must not launder an authored file sitting inside it."""
    rel = _a_synced_path()
    src = _hub_source_for(rel)
    parent = rel.rsplit("/", 1)[0] + "/" if "/" in rel else None
    if parent is None:
        pytest.skip("the sampled synced file is at the root")
    dest = tmp_path / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_hub_head_bytes(src))
    (dest.parent / "mine.py").write_text("x = 1\n")
    assert sweep._sync_materialised_paths(tmp_path, [parent]) == set()


def test_the_comparison_reads_the_hubs_committed_bytes(sweep, tmp_path: Path) -> None:
    """`sync_enforcement_to_projects.py` ships `git show HEAD:<src>` for a tracked file. Comparing
    against the hub's WORKING TREE made the verdict depend on whether a sibling happened to have
    that file dirty — measured live: `PORTS.md` is manifest-owned and uncommitted-dirty today."""
    rel = _a_synced_path()
    src = _hub_source_for(rel)
    dest = tmp_path / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_hub_head_bytes(src))
    assert sweep._is_sync_materialised(tmp_path, rel) is True
    dest.write_bytes(_hub_head_bytes(src) + b"\n# an edit\n")
    assert sweep._is_sync_materialised(tmp_path, rel) is False


def test_a_sync_only_worktree_is_removable_only_under_include_unmerged(sweep) -> None:
    """`git worktree remove` REFUSES while any untracked file is present, so a sync-only tree is
    never in the DEFAULT removable set — a wrong row plus a runtime refusal. `--include-unmerged`
    opts in: the tree is then force-removed after its state is re-read at removal time (the branch
    is never deleted unless git's own `-d` finds it merged)."""
    import types

    assert "wt-sync-only" not in sweep.REMOVABLE
    off = types.SimpleNamespace(
        include_harness=False, include_backups=False, unowned_older_than=None
    )
    on = types.SimpleNamespace(**vars(off), include_unmerged=True)
    assert "wt-sync-only" not in sweep._allowed_classes(off)
    assert "wt-sync-only" in sweep._allowed_classes(on)


def test_the_manifest_import_can_actually_resolve(sweep, tmp_path: Path) -> None:
    """The defect that hid every other defect: `_sync_source_for` imported `fabrik_synced_manifest`
    with no `sys.path` insert. From any cwd but the hub's `scripts/` that raises
    ModuleNotFoundError, the broad `except` swallows it, and EVERY path answers "not sync-owned" —
    so the whole feature was a no-op that looked correct and cleared **0 of 118** dirty worktrees.

    With the insert it clears 4 of 119 on the live fleet. Graded on the SOURCE because a test
    process that already has the hub's scripts/ on sys.path cannot observe the difference."""
    src = Path(sweep.__file__).read_text(encoding="utf-8")
    block = src.split("def _sync_source_for")[1].split("\ndef ")[0]
    assert "sys.path.insert" in block, (
        "the manifest import needs its path insert, or every path silently answers False"
    )
    # and it really resolves a known core script
    assert sweep._sync_source_for(tmp_path, "scripts/review_receipt.py") is not None
