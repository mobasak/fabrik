# AFTER-EDIT: scripts/governance_sync_postcommit.sh
"""The post-commit governance-sync wrapper must FAIL LOUDLY and must not SKIP.

CLAUDE.md § Sync-consciousness promises "a sync failure prints loudly with the manual re-run
command", and names this wrapper as the ENFORCER of the trigger set. Two separate defects made both
claims false, and each was found only after the previous "fix" shipped:

1. `python … | tail -3 || { echo "SYNC FAILED"; exit 1; }` under `set -u` with no `pipefail` tested
   TAIL's status — always 0 — so the failure branch was UNREACHABLE and a sync dying partway through
   48 repos exited 0 silently.
2. Adding `pipefail` then broke the DETECTION pipeline: `git log … | grep -qE` is a SIGPIPE trap,
   because `grep -q` exits at the first match and closes the pipe, so git dies with 141 and the
   pipeline reports 141 — the `if` went FALSE and the sync SKIPPED on exactly the commits that
   touched a trigger path. Measured: 10/10 misses at 5000 changed files, safe below ~1000.

⚠️ These tests drive the REAL script. An earlier version of this file asserted against synthetic
`bash -c` snippets that never referenced the script at all — it would have passed with the fix fully
reverted, and it is precisely why defect 2 shipped. A test that does not name its subject under test
is not a guard.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "governance_sync_postcommit.sh"


def _hub_clone(tmp_path: Path, changed: list[str]) -> Path:
    """A throwaway git repo whose HEAD touches `changed`, with the script's pwd-guard satisfied.

    The script hard-guards `pwd == /opt/fabrik`, so we run it with cwd spoofed via a wrapper that
    the test controls; the guard itself is covered separately below.
    """
    repo = tmp_path / "hub"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for cfg in (("user.email", "t@fabrik.local"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(repo), "config", *cfg], check=True)
    for rel in changed:
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "t"], check=True)
    return repo


def _detection_shape() -> str:
    """The script's own trigger-detection lines, lifted verbatim so the test cannot drift from it."""
    src = SCRIPT.read_text(encoding="utf-8")
    assert 'NAMES="$(git log -1 --format= --name-only)"' in src, (
        "the detection shape changed — update this test to match the script"
    )
    assert 'grep -qE "$FILTER" <<<"$NAMES"' in src, (
        "detection is a PIPELINE again — `git log | grep -q` SIGPIPEs under pipefail and silently "
        "skips the sync on large commits"
    )
    return src


def test_the_script_enables_pipefail() -> None:
    """Anchored on the `set` LINE, not the substring.

    ⚠️ `"pipefail" in src` passed against a file whose option had been removed, because the comment
    above it explains why pipefail matters — the test graded its own documentation.
    """
    lines = SCRIPT.read_text(encoding="utf-8").splitlines()
    set_lines = [ln.strip() for ln in lines if ln.strip().startswith("set ")]
    assert set_lines, "the script declares no `set` options at all"
    assert any("pipefail" in ln for ln in set_lines), (
        f"no `set` line enables pipefail — the SYNC FAILED branch is unreachable. set: {set_lines}"
    )


def test_detection_survives_a_large_commit_under_pipefail(tmp_path: Path) -> None:
    """The SIGPIPE regression, driven through the script's REAL detection shape.

    A pipeline form misses ~10/10 at this size; the here-string form must match every time.
    """
    _detection_shape()
    repo = _hub_clone(tmp_path, [".windsurf/rules/core/00-x.md"] + [f"docs/f{i}.md" for i in range(3000)])
    snippet = (
        'set -uo pipefail\n'
        'FILTER="^\\.windsurf/rules/"\n'
        'NAMES="$(git log -1 --format= --name-only)"\n'
        'if grep -qE "$FILTER" <<<"$NAMES"; then echo TRIGGERED; else echo SKIPPED; fi\n'
    )
    for _ in range(5):
        r = subprocess.run(["bash", "-c", snippet], cwd=repo, capture_output=True, text=True, timeout=60)
        assert "TRIGGERED" in r.stdout, f"the sync was SKIPPED on a trigger commit: {r.stdout!r}"


def test_a_failing_sync_prints_loudly_and_exits_nonzero(tmp_path: Path) -> None:
    """Drive the REAL script with an injected failing sync via SYNC_CMD.

    This is the branch that was unreachable for as long as the script had no pipefail. It must fire.
    """
    if not shutil.which("bash"):  # pragma: no cover
        pytest.skip("bash unavailable")
    src = SCRIPT.read_text(encoding="utf-8")
    assert "SYNC_CMD" in src, "the sync command must be injectable or this branch cannot be tested"

    # Neutralise the pwd guard by pointing it at the tmp repo, keeping everything else verbatim.
    repo = _hub_clone(tmp_path, [".windsurf/rules/core/00-x.md"])
    patched = src.replace('[ "$(pwd)" = "/opt/fabrik" ]', f'[ "$(pwd)" = "{repo}" ]')
    shim = tmp_path / "wrapper.sh"
    shim.write_text(patched, encoding="utf-8")

    env = {**os.environ, "SYNC_CMD": "bash -c 'echo boom >&2; exit 3'"}
    r = subprocess.run(
        ["bash", str(shim)], cwd=repo, capture_output=True, text=True, timeout=120, env=env
    )
    assert "SYNC FAILED" in r.stdout, (
        f"a failing sync must print loudly with the re-run command; got stdout={r.stdout!r} "
        f"stderr={r.stderr!r} rc={r.returncode}"
    )
    assert r.returncode == 1, f"a failing sync must exit non-zero, got {r.returncode}"


def test_an_empty_filter_is_refused_rather_than_matching_everything() -> None:
    """`grep -qE ""` matches every line — an empty filter would sync on EVERY commit, silently."""
    src = SCRIPT.read_text(encoding="utf-8")
    assert '[ -n "$FILTER" ]' in src, (
        "no guard on an empty filter — a governance-sync hook that lost its `files:` key would "
        "yield FILTER='' and treat every commit as a trigger"
    )


def test_the_wrapper_still_no_ops_outside_the_hub_checkout() -> None:
    """`pipefail` must not disturb the worktree guard — a bare render from a worktree PRUNES.

    ⚠️ Narrow by construction: this exercises ONLY the early-exit at the top of the script and
    provides no coverage of detection or sync. Stated so it is never mistaken for broader proof —
    the previous version of this file offered exactly this as its behavioural test.
    """
    r = subprocess.run(["bash", str(SCRIPT)], cwd="/tmp", capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"the wrapper must exit 0 outside /opt/fabrik: {r.stderr}"
