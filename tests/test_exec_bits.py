"""The exec bit in HEAD is what a fresh clone gets — and a lost one fails SILENTLY.

Regression guard for 09292508 (2026-09-08), which stripped `100755 -> 100644` from two
hook-invoked scripts. The working tree kept 755, so nothing looked wrong locally; the
damage only appears when the file is materialised from HEAD (fresh clone, DR restore,
`git checkout`, a merge that touches it).

Why silent: fabrik-lib's `post-commit` hook runs

    if [ -x /opt/fabrik/scripts/distribute_subagents.sh ]; then ... fi

so a non-executable file makes the whole fabrik-lib -> hub re-vendor path a no-op that
exits 0 with no message and no log line. And `scripts/sync_enforcement_to_projects.py`
is named as a bare command in CLAUDE.md and in `governance_sync_postcommit.sh`, which is
`Permission denied` on a fresh checkout.

Why it slipped: the commit was built through a private index with
`git update-index --cacheinfo 100644,<sha>,<path>` — a hardcoded mode applied to every
path. ⚠️ It is invisible to the stale-blob guard CLAUDE.md mandates: a mode-only change
prints `0 0` under `git diff --numstat`, exactly like an unchanged file. Only
`git diff --summary` (`mode change 100644 => 100755`) or `git show --raw` reveals it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Scripts whose CALLER tests executability (or invokes them as a bare command), so a lost
# exec bit is a silent no-op rather than a loud error.
HOOK_INVOKED = (
    "scripts/distribute_subagents.sh",
    "scripts/sync_enforcement_to_projects.py",
)


def _head_mode(rel: str) -> str:
    out = subprocess.run(
        ["git", "ls-tree", "HEAD", "--", rel],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert out.strip(), f"{rel} is not tracked in HEAD"
    return out.split()[0]


@pytest.mark.parametrize("rel", HOOK_INVOKED)
def test_hook_invoked_script_keeps_its_exec_bit_in_head(rel: str) -> None:
    assert _head_mode(rel) == "100755", (
        f"{rel} lost its exec bit IN HEAD. A fresh clone gets a non-executable file, and its "
        "caller guards with `[ -x ]` — the path dies silently. The working tree's mode does "
        "not matter here; fix the mode in HEAD."
    )


def test_the_working_tree_agrees_with_head() -> None:
    """A 755 working tree over a 644 HEAD is precisely what hid 09292508 for a whole round."""
    for rel in HOOK_INVOKED:
        on_disk = "100755" if (REPO / rel).stat().st_mode & 0o111 else "100644"
        assert on_disk == _head_mode(rel), (
            f"{rel}: working tree is {on_disk} but HEAD is {_head_mode(rel)} — the local file "
            "hides a mode regression that ships to every fresh checkout."
        )
