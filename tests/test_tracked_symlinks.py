"""Every symlink the hub tracks points inside the repo (W-36c2607c).

A tracked link that leaves the repo rides every `git archive` — review pins, seat archives, clones — and a copy that
follows links (`shutil.copytree`'s default) then copies whatever it names. The hub once tracked `vault` ->
/mnt/c/ObsidianVault/OneNote and a seat copied 946 MB of the operator's private notes into review scratch.

Each link is checked twice: its committed target lexically (an absolute or `..`-escaping target), and its checked-out
path physically (`realpath`, which resolves a chain of links hop by hop, untracked ones included, without reading
any file content).
"""

from __future__ import annotations

import os
import posixpath
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout


def _leaving(root: Path) -> tuple[int, list[str]]:
    """(tracked links seen, the ones that leave `root`)."""
    links = [
        (line.split()[1], line.split("\t", 1)[1])
        for line in _git(root, "ls-files", "-s", "-z").split("\0")
        if line.startswith("120000 ")
    ]
    top = os.path.realpath(root)
    leaving = []
    for blob, path in links:
        target = _git(root, "cat-file", "-p", blob)
        lexical = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
        physical = os.path.realpath(os.path.join(root, path))
        if (
            posixpath.isabs(target)
            or lexical == ".."
            or lexical.startswith("../")
            or os.path.commonpath([top, physical]) != top
        ):
            leaving.append(f"{path} -> {target}")
    return len(links), leaving


def test_every_tracked_symlink_stays_inside_the_repo() -> None:
    seen, leaving = _leaving(ROOT)
    assert seen, "the hub tracks at least one in-repo link (scripts/verify_prod_parity.py)"
    assert not leaving, f"tracked symlinks leave the repo (untrack and ignore them): {leaving}"


def test_a_chain_of_links_that_leaves_is_caught(tmp_path: Path) -> None:
    """Each hop stays inside on its own, the chain does not: `L -> s/../..` with `s` a link to the repo root resolves
    to the repo's parent; and a tracked in-repo link through an UNTRACKED link that leaves (the ignored `vault`
    shape) is caught too. An in-repo link passes."""
    repo = tmp_path / "repo"
    (repo / "a" / "b" / "c").mkdir(parents=True)
    (repo / "top").mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    os.symlink("../../../top", repo / "a" / "b" / "c" / "s")
    os.symlink("../../../top", repo / "a" / "b" / "c" / "ok")
    subprocess.run(["git", "-C", str(repo), "add", "a"], check=True)
    assert _leaving(repo) == (2, [])
    os.symlink("s/../..", repo / "a" / "b" / "c" / "L")
    os.symlink(str(tmp_path), repo / "outside")  # untracked, like the ignored vault link
    os.symlink("outside/x", repo / "via")
    subprocess.run(["git", "-C", str(repo), "add", "a/b/c/L", "via"], check=True)
    seen, leaving = _leaving(repo)
    assert seen == 4
    assert sorted(leaving) == ["a/b/c/L -> s/../..", "via -> outside/x"], leaving
