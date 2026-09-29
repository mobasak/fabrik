"""The corpus render is refused from a linked worktree (spec 2026-09-29 hub-worktree-cutover § D3 (a), V3).

A render from a worktree PRUNES every installed command/skill absent from that tree's `_sources/`,
box-wide — so `assemble_commands.py` refuses a render into the installed corpus (and `--extract`)
unless the tree it renders FROM is the main checkout. `--check` and a `--dest` preview elsewhere
still run.

Isolation: every run is a SUBPROCESS of a throwaway repo's copy of the script, with HOME pointed
at tmp_path — the real ~/.claude is never the output. The main-checkout row renders into that
throwaway HOME too.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HUB_COMMANDS = Path(__file__).resolve().parents[1] / "commands"
REFUSAL = "refused"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """A throwaway repo holding a copy of commands/, plus one linked worktree of it."""
    base = tmp_path_factory.mktemp("guard")
    main = base / "main"
    (main / "commands").mkdir(parents=True)
    shutil.copy2(HUB_COMMANDS / "assemble_commands.py", main / "commands")
    for sub in ("_fragments", "_sources", "_agents"):
        shutil.copytree(HUB_COMMANDS / sub, main / "commands" / sub)
    _git(main, "init", "-q", "-b", "master")
    _git(main, "add", "commands")
    _git(
        main,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-q",
        "--no-verify",
        "-m",
        "seed",
    )
    wt = base / "wt"
    _git(main, "worktree", "add", "-q", "--detach", str(wt))
    return {"main": main, "wt": wt, "base": base}


def _run(checkout: Path, home: Path, *args: str, cwd: Path | None = None):
    env = {**os.environ, "HOME": str(home)}
    return subprocess.run(
        [sys.executable, str(checkout / "commands" / "assemble_commands.py"), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd or checkout),
        timeout=300,
        check=False,
    )


def _files_under(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file()) if root.exists() else []


def test_worktree_render_is_refused_naming_the_main_checkout(repo, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    # run from an unrelated cwd: the guard keys on the SCRIPT's tree, never the cwd
    r = _run(repo["wt"], home, cwd=tmp_path)
    assert r.returncode != 0, r.stdout + r.stderr
    assert REFUSAL in r.stderr and str(repo["main"]) in r.stderr, r.stderr
    assert _files_under(home) == [], "a refused render wrote under the output dirs"


def test_worktree_render_with_dest_resolving_to_the_corpus_is_refused(repo, tmp_path):
    home = tmp_path / "home"
    (home / ".claude" / "commands").mkdir(parents=True)
    # the installed corpus, spelled through a symlinked parent — `.resolve()` sees through it
    (tmp_path / "alias").symlink_to(home / ".claude")
    r = _run(repo["wt"], home, "--dest", str(tmp_path / "alias" / "commands"))
    assert r.returncode != 0, r.stdout + r.stderr
    assert REFUSAL in r.stderr and str(repo["main"]) in r.stderr, r.stderr
    assert _files_under(home) == [], "a refused render wrote under the output dirs"


def test_worktree_extract_is_refused(repo, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    before = _files_under(repo["wt"] / "commands" / "_sources")
    r = _run(repo["wt"], home, "--extract")
    assert r.returncode != 0, r.stdout + r.stderr
    assert REFUSAL in r.stderr and str(repo["main"]) in r.stderr, r.stderr
    assert _files_under(repo["wt"] / "commands" / "_sources") == before


def test_worktree_dest_preview_elsewhere_still_renders(repo, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    dest = tmp_path / "preview"
    r = _run(repo["wt"], home, "--dest", str(dest))
    assert r.returncode == 0, r.stdout + r.stderr
    assert list(dest.glob("*.md")), "the preview rendered nothing"
    assert _files_under(home) == [], "a preview wrote into the installed corpus"


def test_main_checkout_renders_and_worktree_check_still_runs(repo, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    r = _run(repo["main"], home)
    assert r.returncode == 0, r.stdout + r.stderr
    assert list((home / ".claude" / "commands").glob("*.md")), "main-checkout render wrote nothing"
    assert list((home / ".claude" / "skills").glob("*/SKILL.md"))
    # --check from the worktree is a temp-dir render: not guarded, and in sync with what main rendered
    c = _run(repo["wt"], home, "--check")
    assert c.returncode == 0, c.stdout + c.stderr
    assert REFUSAL not in c.stderr
