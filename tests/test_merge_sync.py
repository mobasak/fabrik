# AFTER-EDIT: scripts/governance_sync_postcommit.sh, scripts/install_post_commit_hook.sh
"""Merges distribute governance (spec 2026-09-29-hub-worktree-cutover-design § The delta D3 (b), § V2).

Once worktree commits sync nothing (the `pwd` guard), a governance-sync path reaches the fleet only
when agent-1 MERGES it into the main checkout — and `git merge` (fast-forward or `--no-ff`) fires no
post-commit hook. These tests drive REAL merges in a scratch repo whose hooks were written by the REAL
installer, so the hook wiring, the post-merge mode and the `ORIG_HEAD..HEAD` read are exercised end to
end. The hooks exec a source-substituted copy of the real script (the same seam
tests/enforcement/test_governance_sync_postcommit.py uses): its `pwd` guard names the scratch repo, its
config is a scratch YAML and its fleet sync is a marker that appends to a log. Nothing here may reach
/opt/fabrik's .git or the project trees.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

HUB = Path(__file__).resolve().parents[1]
SCRIPT = HUB / "scripts" / "governance_sync_postcommit.sh"
INSTALLER = HUB / "scripts" / "install_post_commit_hook.sh"
TRIGGER = ".windsurf/rules/core/00-x.md"

# git exports these to hooks, and this suite may itself run inside one; a leaked GIT_DIR would point
# every call below at a real repo.
_SCRUB = (
    "GOVERNANCE_SYNC_TEST",
    "GOVERNANCE_SYNC_ROOT",
    "SYNC_CMD",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_CONFIG_GLOBAL",
)


def _env(**extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _SCRUB}
    env.update(extra)
    return env


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
        text=True,
        env=_env(),
        timeout=120,
    )


def _commit(cwd: Path, rel: str, msg: str) -> None:
    f = cwd / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"{msg}\n", encoding="utf-8")
    _git(cwd, "add", "--", rel)
    _git(cwd, "commit", "-qm", msg)


class Hub:
    def __init__(self, repo: Path, log: Path) -> None:
        self.repo = repo
        self.log = log

    def syncs(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []


@pytest.fixture
def hub(tmp_path: Path) -> Hub:
    import yaml

    repo = tmp_path / "hub"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=_env())
    resolved = _git(repo, "rev-parse", "--absolute-git-dir").stdout.strip()
    assert Path(resolved).resolve() == (repo / ".git").resolve(), (
        f"REFUSING to run: git resolves to {resolved!r}, not the scratch repo"
    )
    _git(repo, "config", "user.email", "t@fabrik.local")
    _git(repo, "config", "user.name", "t")
    # The substituted script lives in the scratch repo (where the installed hooks exec it) but is
    # never part of its history.
    (repo / ".git" / "info" / "exclude").write_text("scripts/\n", encoding="utf-8")
    _commit(repo, "README.md", "init")

    cfg = tmp_path / "cfg.yaml"
    hook = {"id": "governance-sync", "name": "s", "entry": "true", "language": "system"}
    hook["files"] = r"^\.windsurf/rules/"
    cfg.write_text(
        yaml.safe_dump({"repos": [{"repo": "local", "hooks": [hook]}]}), encoding="utf-8"
    )
    log = tmp_path / "synced.log"
    marker = tmp_path / "sync_marker.sh"
    marker.write_text(f'#!/usr/bin/env bash\necho SYNCED >> "{log}"\n', encoding="utf-8")
    marker.chmod(0o755)

    src = SCRIPT.read_text(encoding="utf-8")
    src = src.replace('[ "$(pwd)" = "/opt/fabrik" ]', f'[ "$(pwd)" = "{repo}" ]')
    src = src.replace("/opt/fabrik/.pre-commit-config.yaml", str(cfg))
    src = src.replace(
        "/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sync_enforcement_to_projects.py --force",
        str(marker),
    )
    assert "/opt/fabrik/scripts/sync_enforcement_to_projects.py" not in src, (
        "the real fleet sync is still reachable from this test — refusing to run it"
    )
    (repo / "scripts").mkdir()
    (repo / "scripts" / "governance_sync_postcommit.sh").write_text(src, encoding="utf-8")

    out = subprocess.run(
        ["bash", str(INSTALLER)],
        capture_output=True,
        text=True,
        env=_env(GOVERNANCE_SYNC_TEST="1", GOVERNANCE_SYNC_ROOT=str(repo)),
        timeout=120,
    )
    assert out.returncode == 0, out.stderr
    return Hub(repo, log)


def _worktree_branch(h: Hub, branch: str, commits: list[str]) -> None:
    """Build `branch` the way an agent does — commits in a LINKED worktree, which sync nothing."""
    wt = h.repo.parent / f"wt-{branch}"
    _git(h.repo, "worktree", "add", "-q", "-b", branch, str(wt))
    for rel in commits:
        _commit(wt, rel, f"{branch} {rel}")
    assert h.syncs() == [], (
        f"worktree commits synced — the scratch hub is not as assumed: {h.syncs()}"
    )


def test_a_fast_forward_merge_distributes_a_non_tip_trigger(hub: Hub) -> None:
    _worktree_branch(hub, "feat", [TRIGGER, "docs/tip.md"])  # the trigger sits BELOW the tip
    _git(hub.repo, "merge", "-q", "--ff-only", "feat")
    assert hub.syncs() == ["SYNCED"], f"a fast-forward merge did not distribute: {hub.syncs()}"


def test_a_no_ff_merge_distributes_a_non_tip_trigger(hub: Hub) -> None:
    _worktree_branch(hub, "feat", [TRIGGER, "docs/tip.md"])
    _git(hub.repo, "merge", "-q", "--no-ff", "feat", "-m", "merge feat")
    assert hub.syncs() == ["SYNCED"], f"a --no-ff merge did not distribute: {hub.syncs()}"


def test_a_merge_that_brings_in_no_trigger_path_does_not_sync(hub: Hub) -> None:
    _worktree_branch(hub, "docs", ["docs/a.md"])
    _git(hub.repo, "merge", "-q", "--no-ff", "docs", "-m", "merge docs")
    assert hub.syncs() == [], f"a non-trigger merge synced: {hub.syncs()}"


def test_a_commit_in_a_linked_worktree_distributes_nothing(hub: Hub, tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    _git(hub.repo, "worktree", "add", "-q", "-b", "wtb", str(wt))
    _commit(wt, TRIGGER, "rules in a worktree")
    assert hub.syncs() == [], f"a worktree commit distributed: {hub.syncs()}"
    # Control: the same kind of commit in the main checkout DOES sync, so the silence above is the
    # guard's, not a dead hook's.
    _commit(hub.repo, TRIGGER, "rules in the main checkout")
    assert hub.syncs() == ["SYNCED"], f"the post-commit hook is not live: {hub.syncs()}"


def test_the_installer_writes_both_hooks_and_each_execs_the_sync_script(hub: Hub) -> None:
    hooks = hub.repo / ".git" / "hooks"
    script = f'exec bash "{hub.repo}/scripts/governance_sync_postcommit.sh"'
    for name in ("post-commit", "post-merge"):
        body = (hooks / name).read_text(encoding="utf-8")
        assert script in body, f"{name} does not exec the sync script:\n{body}"
        assert os.access(hooks / name, os.X_OK), f"{name} is not executable"
    assert f"{script} post-merge" in (hooks / "post-merge").read_text(encoding="utf-8")
