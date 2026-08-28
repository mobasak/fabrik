"""Invariants of the pre-push gate that replaced GitHub Actions (commit `0bd6cf31`).

Both invariants below were BROKEN in the first wiring and found by executing the real hook —
`pre-commit run --hook-stage pre-push` reproduces neither. They are pinned here because the
consequence of either regressing is silent: the gate still "runs", it just stops protecting.

Deliberately a CONFIG test, not an execution test. Running `.git/hooks/pre-push` for real makes
pre-commit stash the working tree, and this tree is shared by three concurrent sessions — a test
that stashes a sibling's uncommitted work to prove a point is a worse defect than the one it checks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / ".pre-commit-config.yaml"

yaml = pytest.importorskip("yaml")


@pytest.fixture(scope="module")
def config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _pre_push_hooks(cfg: dict) -> list[dict]:
    return [
        h
        for repo in cfg.get("repos", [])
        for h in repo.get("hooks", [])
        if "pre-push" in (h.get("stages") or [])
    ]


def test_default_stages_pins_hooks_to_the_commit_stage(config):
    """A hook with no explicit `stages:` runs at EVERY stage, including pre-push.

    Before `default_stages` was set, a push fired the whole commit-blocker set AND
    `governance-sync` — which writes into 47 project trees. Dropping this line silently re-arms
    a fleet-mutating sync on every push by every session.
    """
    assert config.get("default_stages") == ["pre-commit"], (
        "default_stages must pin unmarked hooks to the commit stage; "
        f"got {config.get('default_stages')!r}"
    )


def test_both_hook_types_are_installed_by_default(config):
    """`pre-commit install` must arm pre-push too, or the gate exists in config and nowhere else."""
    assert set(config.get("default_install_hook_types") or []) >= {"pre-commit", "pre-push"}


def test_every_pre_push_hook_is_declared_non_mutating(config):
    """The ratchet. pre-push STASHES the worktree, so a hook that writes into the tree hits
    "Stashed changes conflicted with hook auto-fixes... Rolling back fixes" — the WIP-destruction
    shape that got the trailer guard removed from pre-commit.

    `push-gate` is safe only because `--report /tmp/...` redirects the write that
    `check_duplicates.py` otherwise makes INTO the repo (which pre-commit scores as "files were
    modified by this hook" and fails, redding a push where the check itself printed PASS).

    This test does not — cannot, statically — prove a hook is non-mutating. It pins the SET, so
    adding one fails here and forces someone to make that argument deliberately.
    """
    known_safe = {"push-gate"}
    ids = {h.get("id") for h in _pre_push_hooks(config)}
    assert ids == known_safe, (
        f"pre-push hook set changed: {ids ^ known_safe}. pre-push stashes the worktree — prove the "
        "new hook writes NOTHING into the tree (redirect any report/output to /tmp), then add it here."
    )


def test_the_push_gate_actually_redirects_its_report_out_of_the_tree(config):
    """The specific mutation that broke the first wiring. `check_duplicates.py` defaults to
    `--report duplicate-report.json`, a TRACKED file at the repo root."""
    gate = next(h for h in _pre_push_hooks(config) if h.get("id") == "push-gate")
    entry = gate.get("entry", "")
    assert "--report /tmp/" in entry, (
        f"push-gate must write its report outside the repo; entry is {entry!r}"
    )


def test_no_github_workflows_remain_in_the_hub():
    """The other half of the cutover. If workflows come back, the push gate is no longer the only
    enforcement and the parity argument in the config comment stops being true."""
    wf = REPO / ".github" / "workflows"
    found = sorted(p.name for p in wf.glob("*.y*ml")) if wf.is_dir() else []
    assert not found, f"workflows returned: {found} — reconcile with the push gate's parity claim"
