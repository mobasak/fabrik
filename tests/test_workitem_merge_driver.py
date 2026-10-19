"""W-c230cb2e: a builder's HAND `git merge master` merges `.fabrik/work/W-*.json` key-wise.

`merge_request.py` resolves item conflicts itself (W-5f3617e6, D-988); a hand merge on a worktree
branch got git's line conflict whenever the two sides changed disjoint keys that the store's sorted
one-per-line layout puts side by side. The hub's `.gitattributes` maps the item files to the
`workitem` driver; `scripts/install_post_commit_hook.sh` registers the driver in the shared git
config and copies the mapping into `<common>/info/attributes`, because git reads `.gitattributes`
from the tree as it was BEFORE the merge. Any non-zero exit of the verb falls back to git's own text
merge, so a conflict still carries markers and never a silently picked side.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]
INSTALLER = HUB / "scripts" / "install_post_commit_hook.sh"
ITEM = ".fabrik/work/W-27a0dc32.json"
# the W-27a0dc32 shape (tests/test_merge_request_work_items.py): master scores, the branch closes
BASE = {
    "id": "W-27a0dc32",
    "status": "open",
    "evidence": "",
    "effort": "",
    "owner": "",
    "priority": 2,
    "score_reason": "",
}
SCORED = {**BASE, "effort": "low", "owner": "kaizen", "priority": 1, "score_reason": "HIGH"}
CLOSED = {**BASE, "evidence": "165fed26f", "status": "done"}

# git exports these to hooks, and this suite may run inside one; a leaked GIT_DIR or a developer's
# own merge.workitem.* would point the merges below at the wrong config
_SCRUB = (
    "GOVERNANCE_SYNC_TEST",
    "GOVERNANCE_SYNC_ROOT",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
)


def _env(**extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _SCRUB}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, **extra)
    return env


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
        + ["-c", "commit.gpgsign=false", *args],
        capture_output=True,
        text=True,
        env=_env(),
        check=check,
        timeout=120,
    )


def _dump(data: dict) -> str:
    """`work.py::_dump` — the store's own byte format."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _install(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(INSTALLER)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        env=_env(GOVERNANCE_SYNC_TEST="1", GOVERNANCE_SYNC_ROOT=str(repo)),
    )


def _commit_item(repo: Path, data: dict, msg: str) -> None:
    (repo / ITEM).write_text(_dump(data), encoding="utf-8")
    _git(repo, "commit", "-qam", msg)


def _repo(tmp_path: Path, branch_side: dict, *, attributes_in_base: bool = True) -> Path:
    """A hub-shaped repo: the real `work.py`, the item in the base, `feat` changed to
    ``branch_side``, master scored and carrying the hub's real `.gitattributes`, the installer run
    on master. With ``attributes_in_base=False`` `.gitattributes` lands on master only, after
    `feat` was cut — the rollout case."""
    repo = tmp_path / "hub"
    (repo / ".fabrik" / "work").mkdir(parents=True)
    (repo / "scripts").mkdir()
    _git(tmp_path, "init", "-q", "-b", "master", str(repo))
    shutil.copy(HUB / "scripts" / "work.py", repo / "scripts" / "work.py")
    if attributes_in_base:
        shutil.copy(HUB / ".gitattributes", repo / ".gitattributes")
    (repo / ITEM).write_text(_dump(BASE), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", "feat")
    _commit_item(repo, branch_side, "branch")
    _git(repo, "checkout", "-q", "master")
    if not attributes_in_base:
        shutil.copy(HUB / ".gitattributes", repo / ".gitattributes")
        _git(repo, "add", ".gitattributes")
    _commit_item(repo, SCORED, "score")
    out = _install(repo)
    assert out.returncode == 0, out.stderr
    return repo


def _driver_values(repo: Path) -> list[str]:
    res = _git(repo, "config", "--get-all", "merge.workitem.driver", check=False)
    return res.stdout.splitlines()


def test_the_hub_maps_item_files_to_the_driver():
    out = _git(HUB, "check-attr", "merge", "--", ITEM).stdout
    assert out.strip().endswith("merge: workitem"), out


def test_the_installer_registers_the_driver_without_rewriting_an_unchanged_config(tmp_path):
    repo = tmp_path / "hub"
    _git(tmp_path, "init", "-q", str(repo))
    shutil.copy(HUB / ".gitattributes", repo / ".gitattributes")
    assert _install(repo).returncode == 0
    assert len(_driver_values(repo)) == 1
    assert "scripts/work.py merge-item %O %A %B" in _driver_values(repo)[0]
    info = repo / ".git" / "info" / "attributes"
    assert info.read_text().count("merge=workitem") == 1, info.read_text()
    config = repo / ".git" / "config"
    before = (os.stat(config).st_ino, os.stat(config).st_mtime_ns, info.read_bytes())
    assert _install(repo).returncode == 0
    # a same-value `git config` replaces the shared file and takes config.lock on every shell
    after = (os.stat(config).st_ino, os.stat(config).st_mtime_ns, info.read_bytes())
    assert after == before


def test_a_hand_merge_of_disjoint_item_keys_merges_clean(tmp_path):
    repo = _repo(tmp_path, CLOSED)
    _git(repo, "checkout", "-q", "feat")
    res = _git(repo, "merge", "--no-edit", "master", check=False)
    assert res.returncode == 0, res.stdout + res.stderr
    merged = {**SCORED, "evidence": "165fed26f", "status": "done"}
    assert json.loads((repo / ITEM).read_text()) == merged


def test_a_branch_cut_before_the_attribute_merges_clean(tmp_path):
    """git reads `.gitattributes` from the pre-merge tree, so the merge that brings the file in
    would get no driver; the installer's `info/attributes` copy covers it."""
    repo = _repo(tmp_path, CLOSED, attributes_in_base=False)
    _git(repo, "checkout", "-q", "feat")
    assert not (repo / ".gitattributes").exists()
    res = _git(repo, "merge", "--no-edit", "master", check=False)
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads((repo / ITEM).read_text())["status"] == "done"


def test_a_key_conflict_falls_back_to_conflict_markers(tmp_path):
    """The verb RUNS (it names the key — a broken driver string would also leave markers), then
    git's text merge leaves markers and three index stages; `-X theirs` no longer picks a side."""
    repo = _repo(tmp_path, {**CLOSED, "owner": "fleet"})
    _git(repo, "checkout", "-q", "feat")
    for extra in ((), ("-X", "theirs")):
        res = _git(repo, "merge", "--no-edit", *extra, "master", check=False)
        assert res.returncode != 0, extra
        assert "merge-item: both sides changed owner" in res.stderr, res.stderr
        assert "<<<<<<< ours" in (repo / ITEM).read_text()
        assert _git(repo, "ls-files", "-u", "--", ITEM).stdout.count("\n") == 3
        _git(repo, "merge", "--abort")
