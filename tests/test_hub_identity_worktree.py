"""A linked worktree of the hub is the hub to the gate (spec 2026-09-29 hub-worktree cut-over § D4/H4, V8).

Hub identity = `scripts/fabrik_synced_manifest.py` present in the tree AND the git common dir's
parent is the hub path. Each file keeps ONE hub-path constant (`check_vendored_drift.HUB`,
`final_gate._FABRIK_ROOT`), which these tests point at a scratch repo — no worktree is ever
added to the real /opt/fabrik. The mirror is pinned too: a project repo (no manifest, or a
manifest under a common dir whose parent is not the hub) stays a project.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_vendored_drift as cvd  # noqa: E402
from scripts import final_gate  # noqa: E402

MANIFEST = "scripts/fabrik_synced_manifest.py"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _tree(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)


def _repo(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True)
    _tree(root, files)
    _git(root, "init", "-q", "-b", "master")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _worktree(main: Path, wt: Path) -> Path:
    _git(main, "worktree", "add", "-q", "-b", "wt-branch", str(wt))
    return wt


@pytest.fixture
def hub_and_worktree(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A scratch hub (with the manifest), a linked worktree of it, and a vendoring repo."""
    hub = _repo(
        tmp_path / "fabrik",
        {
            MANIFEST: "# manifest\n",
            "scripts/enforcement/check_a.py": "HUB-A\n",
            "scripts/enforcement/check_b.py": "HUB-B\n",
        },
    )
    wt = _worktree(hub, tmp_path / "wt")
    # The worktree carries its OWN edit of the governance set — the grade must use it.
    (wt / "scripts" / "enforcement" / "check_a.py").write_text("WORKTREE-A\n")
    opt = tmp_path / "opt"
    # check_b differs everywhere, so the report always prints the vendorer's count line.
    _tree(
        opt / "vendorer",
        {
            "scripts/enforcement/check_a.py": "WORKTREE-A\n",
            "scripts/enforcement/check_b.py": "V-B\n",
        },
    )
    return hub, wt, opt


# --- check_vendored_drift.py ------------------------------------------------------------------


def test_vendored_drift_grades_in_a_hub_worktree(hub_and_worktree, monkeypatch, capsys):
    hub, wt, opt = hub_and_worktree
    monkeypatch.setattr(cvd, "HUB", hub)
    monkeypatch.setattr(cvd, "OPT", opt)
    monkeypatch.chdir(wt)
    assert cvd.main() == 0
    out = capsys.readouterr().out
    # It graded (no vacuous return 0) AND against the worktree's own set, not the main checkout's.
    assert "vendorer: 1 identical" in out, out


def test_vendored_drift_main_checkout_still_grades(hub_and_worktree, monkeypatch, capsys):
    hub, _wt, opt = hub_and_worktree
    monkeypatch.setattr(cvd, "HUB", hub)
    monkeypatch.setattr(cvd, "OPT", opt)
    monkeypatch.chdir(hub)
    cvd.main()
    assert "vendorer: 0 identical" in capsys.readouterr().out


@pytest.mark.parametrize("with_manifest", [False, True])
def test_vendored_drift_stays_silent_in_a_project_repo(
    tmp_path, monkeypatch, capsys, with_manifest
):
    hub = _repo(tmp_path / "fabrik", {MANIFEST: "# m\n"})
    files = {"scripts/enforcement/check_a.py": "P\n"}
    if with_manifest:
        files[MANIFEST] = "# not the hub\n"
    proj = _repo(tmp_path / "proj", files)
    proj_wt = _worktree(proj, tmp_path / "proj-wt")
    monkeypatch.setattr(cvd, "HUB", hub)
    monkeypatch.setattr(cvd, "OPT", tmp_path)
    for where in (proj, proj_wt):
        monkeypatch.chdir(where)
        assert cvd.main() == 0
        assert capsys.readouterr().out == ""


# --- final_gate.py ----------------------------------------------------------------------------


def test_final_gate_treats_a_hub_worktree_as_the_hub(hub_and_worktree, monkeypatch):
    hub, wt, _opt = hub_and_worktree
    (wt / ".fabrik").mkdir()
    (wt / ".fabrik" / "synced.lock").write_text('{"scripts/x.py": "h"}')
    monkeypatch.setattr(final_gate, "_FABRIK_ROOT", hub)
    for root in (hub, wt):
        monkeypatch.setattr(final_gate, "PROJECT_ROOT", root)
        assert final_gate._synced_paths() == set(), root
        ok, msg = final_gate.check_symlinks()
        assert ok and "source repo" in msg, (root, msg)


@pytest.mark.parametrize("with_manifest", [False, True])
def test_final_gate_project_repo_is_still_a_project(tmp_path, monkeypatch, with_manifest):
    hub = _repo(tmp_path / "fabrik", {MANIFEST: "# m\n"})
    files = {".fabrik/synced.lock": '{"scripts/x.py": "h"}', "AGENTS.md": "a\n"}
    if with_manifest:
        files[MANIFEST] = "# not the hub\n"
    proj = _repo(tmp_path / "proj", files)
    proj_wt = _worktree(proj, tmp_path / "proj-wt")
    monkeypatch.setattr(final_gate, "_FABRIK_ROOT", hub)
    for root in (proj, proj_wt):
        monkeypatch.setattr(final_gate, "PROJECT_ROOT", root)
        assert final_gate._synced_paths() == {"scripts/x.py"}, root
        _ok, msg = final_gate.check_symlinks()
        assert "source repo" not in msg, (root, msg)
