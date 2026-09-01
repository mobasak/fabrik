# AFTER-EDIT: scripts/governance_sync_postcommit.sh
"""The post-commit governance-sync wrapper must FAIL LOUDLY.

CLAUDE.md § Sync-consciousness promises "a sync failure prints loudly with the manual re-run
command", and the same paragraph now names this wrapper as the ENFORCER of the trigger set. Both
claims were false: the script ran `python … | tail -3 || { echo "SYNC FAILED"; exit 1; }` under
`set -u` with no `pipefail`, so the `||` tested TAIL's exit status — always 0. A sync that died
partway through 48 repos exited 0 with no warning, and the operator had no signal that a governance
change had not distributed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "governance_sync_postcommit.sh"


def _run(snippet: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", snippet], capture_output=True, text=True, timeout=30)


def test_the_script_enables_pipefail() -> None:
    """Read the real file — the guard is one option and it is easy to drop in a later edit.

    ⚠️ Anchored on the `set` LINE, not on the substring. `"pipefail" in src` passed against a file
    whose option had been removed, because the comment ABOVE it explains why pipefail matters —
    the test graded its own documentation. Caught by red-on-revert on 2026-09-01, which is the
    whole reason the mutation must be asserted on disk and the test watched to fail.
    """
    lines = SCRIPT.read_text(encoding="utf-8").splitlines()
    set_lines = [ln.strip() for ln in lines if ln.strip().startswith("set ")]
    assert set_lines, "the script declares no `set` options at all"
    assert any("pipefail" in ln for ln in set_lines), (
        f"no `set` line enables pipefail — the SYNC FAILED branch is unreachable. set lines: {set_lines}"
    )


def test_a_failing_sync_actually_takes_the_failure_branch() -> None:
    """The behaviour, not the flag: prove the `|| { … }` fires when the LEFT side of the pipe dies.

    Written red-first against the shipped shape (`set -u`, no pipefail), which printed nothing.
    """
    without = _run('set -u; (exit 3) 2>&1 | tail -3 || echo "FAILURE BRANCH TAKEN"; exit 0')
    assert "FAILURE BRANCH TAKEN" not in without.stdout, (
        "this fixture is meant to demonstrate the BROKEN shape; it now passes, so the "
        "demonstration is stale"
    )
    with_pf = _run('set -uo pipefail; (exit 3) 2>&1 | tail -3 || echo "FAILURE BRANCH TAKEN"; exit 0')
    assert "FAILURE BRANCH TAKEN" in with_pf.stdout, "pipefail must surface the left side's failure"


def test_the_wrapper_still_no_ops_outside_the_hub_checkout() -> None:
    """`pipefail` must not disturb the worktree guard — a bare render from a worktree PRUNES."""
    r = subprocess.run(["bash", str(SCRIPT)], cwd="/tmp", capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"the wrapper must exit 0 outside /opt/fabrik: {r.stderr}"
