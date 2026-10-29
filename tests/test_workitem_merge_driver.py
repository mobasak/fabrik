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


def _attr(repo: Path) -> str:
    return _git(repo, "check-attr", "merge", "--", ITEM).stdout.strip().rsplit(": ", 1)[-1]


def _bare_repo(tmp_path: Path, gitattributes: str | None = None) -> Path:
    repo = tmp_path / "hub"
    _git(tmp_path, "init", "-q", str(repo))
    if gitattributes is None:
        shutil.copy(HUB / ".gitattributes", repo / ".gitattributes")
    else:
        (repo / ".gitattributes").write_text(gitattributes, encoding="utf-8")
    return repo


def test_the_hub_maps_item_files_to_the_driver(tmp_path):
    """The TRACKED file alone, in a repo with no info/attributes — the hub's own checkout carries the
    installer's copy, which outranks `.gitattributes` and would pass with the file gone."""
    repo = _bare_repo(tmp_path)
    assert _attr(repo) == "workitem"


def test_the_installer_registers_the_driver_without_rewriting_an_unchanged_config(tmp_path):
    repo = _bare_repo(tmp_path)
    assert _install(repo).returncode == 0
    assert len(_driver_values(repo)) == 1
    assert "scripts/work.py merge-item %O %A %B" in _driver_values(repo)[0]
    info = repo / ".git" / "info" / "attributes"
    assert info.read_text().count("merge=workitem") == 1, info.read_text()
    config = repo / ".git" / "config"

    def state():
        return [(os.stat(p).st_ino, os.stat(p).st_mtime_ns, p.read_bytes()) for p in (config, info)]

    before = state()
    assert _install(repo).returncode == 0
    # a same-value `git config` replaces the shared file and takes config.lock on every shell
    assert state() == before


def test_a_changed_or_multi_valued_driver_is_replaced(tmp_path):
    repo = _bare_repo(tmp_path)
    _git(repo, "config", "merge.workitem.driver", "old")
    _git(repo, "config", "--add", "merge.workitem.driver", "older")
    assert _install(repo).returncode == 0
    assert len(_driver_values(repo)) == 1 and "merge-item" in _driver_values(repo)[0]


def test_the_attributes_copy_keeps_other_lines_and_follows_the_tracked_file(tmp_path):
    """Review pass 1: an info/attributes without a final newline had the mapping glued onto its
    last line (both broken), and a mapping removed from `.gitattributes` stayed in force forever."""
    repo = _bare_repo(tmp_path)
    info = repo / ".git" / "info" / "attributes"
    info.parent.mkdir(exist_ok=True)
    info.write_text("*.bin binary", encoding="utf-8")  # no final newline
    assert _install(repo).returncode == 0
    assert _attr(repo) == "workitem"
    assert info.read_text().splitlines()[0] == "*.bin binary"
    (repo / ".gitattributes").write_text("# the mapping retired\n", encoding="utf-8")
    assert _install(repo).returncode == 0
    assert _attr(repo) == "unspecified"
    assert info.read_text().splitlines() == ["*.bin binary"]


def test_an_unclosed_block_never_deletes_the_lines_after_it(tmp_path):
    """Review pass 2 (executed): a BEGIN marker whose END was hand-trimmed made the strip drop
    every line to the end of the file — a person's attribute lines silently lost."""
    repo = _bare_repo(tmp_path)
    info = repo / ".git" / "info" / "attributes"
    assert _install(repo).returncode == 0
    lines = [ln for ln in info.read_text().splitlines() if not ln.startswith("# END")]
    info.write_text("\n".join(lines + ["*.dat -text"]) + "\n", encoding="utf-8")
    assert _install(repo).returncode == 0
    assert "*.dat -text" in info.read_text().splitlines()
    assert _attr(repo) == "workitem"
    # review pass 3: a second BEGIN while the first is still open discarded what the first held
    begin = next(ln for ln in info.read_text().splitlines() if ln.startswith("# BEGIN"))
    info.write_text(f"{begin}\nuser-inside -text\n{begin}\nstale\n# END work-item merge driver\n", encoding="utf-8")
    assert _install(repo).returncode == 0
    assert "user-inside -text" in info.read_text().splitlines()


def test_an_indented_comment_is_not_copied(tmp_path):
    repo = _bare_repo(tmp_path, "  # .fabrik/work/W-*.json merge=workitem\n")
    assert _install(repo).returncode == 0
    info = repo / ".git" / "info" / "attributes"
    assert not info.exists() or "merge=workitem" not in info.read_text()
    assert _attr(repo) == "unspecified"


def test_a_held_config_lock_still_copies_the_attributes_and_fails_loudly(tmp_path):
    """Review pass 1 (executed): a config.lock held by a sibling — or left stale — aborted the
    installer under `set -e` before the attributes copy; the write fails, the rest still runs, and
    the non-zero exit is what `wsl_startup_hook.sh` reports."""
    repo = _bare_repo(tmp_path)
    (repo / ".git" / "config.lock").write_text("", encoding="utf-8")
    out = _install(repo)
    assert out.returncode != 0
    assert "merge.workitem" in out.stderr, out.stderr
    assert _attr(repo) == "workitem"
    assert (repo / ".git" / "hooks" / "post-merge").exists()


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
