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

import re
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


def test_every_hook_invoked_entry_is_still_referenced_by_a_real_caller() -> None:
    """Guard the LIST, from the callers that actually exist — not from one config that has none.

    The per-script guard is parameterised over `HOOK_INVOKED`, so deleting an entry shrinks
    coverage silently (proven by mutation: removing `scripts/distribute_subagents.sh` left every
    test green). The first attempt at this guard derived its subjects from `.pre-commit-config.yaml`
    alone — which today executes NOTHING directly, every entry going through `bash`. So it computed
    an empty set, `missing` was empty by construction, and it could not fail: a vacuous guard
    written to close a vacuity finding, caught by the closing seat.

    The real callers are two, and both are read-only here: the pre-commit config, and fabrik-lib's
    `post-commit` hook, which does `[ -x … ]` then EXECUTES `distribute_subagents.sh` — that is the
    caller for which the exec bit is fully load-bearing, and it is why the entry exists at all.
    Deleting an entry from the tuple now reds, because the reference in a caller outlives it.
    """
    # The callers are the config, the external git hook, AND the wrapper scripts the config
    # invokes — one hop, because `sync_enforcement_to_projects.py` is named by
    # `governance_sync_postcommit.sh`, not by the config directly. The first version of this
    # guard stopped at the config and reported the sync script as unreferenced, which was a true
    # statement about an incomplete enumeration rather than about the tuple.
    config = REPO / ".pre-commit-config.yaml"
    callers = [config, Path("/opt/fabrik-lib/.git/hooks/post-commit")]
    for m in re.finditer(r"^\s*entry:\s*(.+)$", config.read_text(encoding="utf-8"), re.M):
        for raw in m.group(1).split():
            token = raw.strip("\"'")
            if token.endswith(".sh"):
                rel = token[len("/opt/fabrik/") :] if token.startswith("/opt/fabrik/") else token
                if (REPO / rel).is_file():
                    callers.append(REPO / rel)
    text = ""
    read: list[str] = []
    for c in callers:
        try:
            text += c.read_text(encoding="utf-8")
            read.append(str(c))
        except OSError:
            continue  # a caller this checkout cannot see cannot testify either way
    assert read, f"no caller readable of {callers} — this guard graded nothing"

    # DIRECTION MATTERS: caller → tuple, never tuple → caller. Checking "every entry is
    # referenced" cannot fail on a DELETION, because deleting shrinks the set being checked —
    # the first version of this guard did exactly that and stayed green under its own motivating
    # mutation (removing `distribute_subagents.sh`). What must hold is the converse: every script
    # a caller EXECUTES with its exec bit load-bearing has to be in the tuple.
    exec_tested = {m.group(1) for m in re.finditer(r"\[\s*-x\s+(/opt/fabrik/\S+?)\s*\]", text)}
    required = {
        p[len("/opt/fabrik/") :] for p in exec_tested if (REPO / p[len("/opt/fabrik/") :]).is_file()
    }
    missing = sorted(required - set(HOOK_INVOKED))
    assert not missing, (
        f"{missing} is `[ -x ]`-tested and executed by a caller ({read}) but is absent from "
        "HOOK_INVOKED, so nothing checks its exec bit in HEAD — a lost bit makes that caller a "
        "silent no-op on every fresh clone."
    )
    if not required:
        # SKIP, not fail. The only `[ -x /opt/fabrik/… ]` caller on this box lives in
        # /opt/fabrik-lib/.git/hooks/post-commit, which `git -C /opt/fabrik-lib ls-files` shows is
        # UNTRACKED — so on a fresh clone of the hub alone, or in CI, or after a DR restore, this
        # would hard-fail with a diagnosis ("the enumeration or the callers changed") that is
        # false. A guard that reds on a legitimate environment is how a guard gets waived.
        pytest.skip(
            f"no `[ -x /opt/fabrik/…]` caller readable in {read} — nothing to derive from here"
        )

    # and the converse: a caller that EXECUTES a .sh directly must be listed. Empty today, and
    # that is stated rather than asserted away — `assert invoked` would pin an accident.
    direct: set[str] = set()
    for m in re.finditer(
        r"^\s*entry:\s*(.+)$", (REPO / ".pre-commit-config.yaml").read_text(), re.M
    ):
        tokens = [tok.strip("\"'") for tok in m.group(1).split()]
        if tokens and Path(tokens[0]).name in {"bash", "sh", "zsh", "python", "python3"}:
            continue
        for token in tokens:
            if token.endswith(".sh"):
                rel = token[len("/opt/fabrik/") :] if token.startswith("/opt/fabrik/") else token
                if (REPO / rel).is_file():
                    direct.add(rel)
    assert not (direct - set(HOOK_INVOKED)), (
        f"{sorted(direct - set(HOOK_INVOKED))} is executed directly by a pre-commit hook but is "
        "absent from HOOK_INVOKED, so nothing checks its exec bit in HEAD"
    )
