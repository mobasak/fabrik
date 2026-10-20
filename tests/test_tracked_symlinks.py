"""Every symlink the hub tracks points inside the repo (W-36c2607c).

A tracked link that leaves the repo rides every `git archive` — review pins, seat archives, clones — and a copy that
follows links (`shutil.copytree`'s default) then copies whatever it names. The hub once tracked `vault` ->
/mnt/c/ObsidianVault/OneNote and a seat copied 946 MB of the operator's private notes into review scratch.
"""

from __future__ import annotations

import posixpath
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True
    ).stdout


def test_every_tracked_symlink_stays_inside_the_repo() -> None:
    links = [
        (line.split()[1], line.split("\t", 1)[1])
        for line in _git("ls-files", "-s", "-z").split("\0")
        if line.startswith("120000 ")
    ]
    assert links, "the hub tracks at least one in-repo link (scripts/verify_prod_parity.py)"
    leaving = []
    for blob, path in links:
        target = _git("cat-file", "-p", blob)
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
        if posixpath.isabs(target) or resolved == ".." or resolved.startswith("../"):
            leaving.append(f"{path} -> {target}")
    assert not leaving, f"tracked symlinks leave the repo (untrack and ignore them): {leaving}"
