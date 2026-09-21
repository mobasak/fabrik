"""Red-first graders for scripts/private_index_commit.py — the executable form of the shared-append
commit recipe. Each test is one of the incidents the prose recipe's pins encode, simulated in a
scratch repo: a sibling commit inside the CAS window, a sibling's blob staged in the shared index,
a lost exec bit, a missing anchor, a message without trailers, a sync-trigger path."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
pic = __import__("private_index_commit")

MSG = "test: land\n\nAgent-Role: primary\nAgent-Context: grader\nCo-Authored-By: x <x@x>\n"
UNREL = r"^## \[Unreleased\]$"
DELIM = r"^\|---\|---\|$"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        check=True,
    ).stdout


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q", "-b", "master")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n### old entry\n\n## [1.0]\n")
    (r / "docs").mkdir()
    (r / "docs" / "DECISIONS.md").write_text("| id | what |\n|---|---|\n| D-1 | first |\n")
    (r / "own.txt").write_text("v1\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "seed")
    return r


def _msg(tmp_path: Path, text: str = MSG) -> Path:
    p = tmp_path / "msg"
    p.write_text(text)
    return p


def test_basic_append_and_own_land_and_carry(tmp_path: Path) -> None:
    r = _repo(tmp_path)
    base = _git(r, "rev-parse", "HEAD").strip()
    (r / "own.txt").write_text("v2\n")
    res = pic.run(
        r,
        _msg(tmp_path),
        appends=[
            ("CHANGELOG.md", "### mine\n\n", UNREL),
            ("docs/DECISIONS.md", "| D-2 | mine |\n", DELIM),
        ],
        owns=["own.txt"],
    )
    head = _git(r, "rev-parse", "HEAD").strip()
    assert head == res.new and res.base == base
    assert _git(r, "rev-parse", "HEAD~1").strip() == base
    cl = _git(r, "show", "HEAD:CHANGELOG.md")
    assert cl.index("## [Unreleased]") < cl.index("### mine") < cl.index("### old entry")
    dec = _git(r, "show", "HEAD:docs/DECISIONS.md")
    assert dec.splitlines()[2] == "| D-2 | mine |" and "| D-1 | first |" in dec
    assert _git(r, "show", "HEAD:own.txt") == "v2\n"
    # step 7: the working files carry the hunk, once, in place
    assert (r / "CHANGELOG.md").read_text().count("### mine") == 1
    assert (r / "docs" / "DECISIONS.md").read_text().count("| D-2 | mine |") == 1
    assert _git(r, "diff", "HEAD", "--", "CHANGELOG.md", "docs/DECISIONS.md", "own.txt") == ""
    # step 6: the shared index is aligned to HEAD for those paths
    assert _git(r, "diff", "--cached", "--name-only") == ""


def test_sibling_commit_in_the_cas_window_is_kept_and_ours_lands_on_top(tmp_path: Path) -> None:
    r = _repo(tmp_path)
    base = _git(r, "rev-parse", "HEAD").strip()
    fired: list[str] = []

    def sibling_commits() -> None:
        # a sibling appends its OWN row to the same shared file through the same recipe
        fired.append("x")
        idx = tmp_path / "sib-idx"
        env = {**os.environ, "GIT_INDEX_FILE": str(idx)}
        subprocess.run(
            ["git", "read-tree", base], cwd=r, env=env, check=True, stdin=subprocess.DEVNULL
        )
        content = _git(r, "show", f"{base}:docs/DECISIONS.md") + "| D-9 | sibling |\n"
        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=r,
            input=content,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "update-index", "--add", "--cacheinfo", f"100644,{blob},docs/DECISIONS.md"],
            cwd=r,
            env=env,
            check=True,
            stdin=subprocess.DEVNULL,
        )
        tree = subprocess.run(
            ["git", "write-tree"],
            cwd=r,
            env=env,
            capture_output=True,
            text=True,
            check=True,
            stdin=subprocess.DEVNULL,
        ).stdout.strip()
        sib = subprocess.run(
            ["git", "commit-tree", tree, "-p", base, "-m", "sibling"],
            cwd=r,
            capture_output=True,
            text=True,
            check=True,
            stdin=subprocess.DEVNULL,
        ).stdout.strip()
        _git(r, "update-ref", "refs/heads/master", sib, base)

    res = pic.run(
        r,
        _msg(tmp_path),
        appends=[("docs/DECISIONS.md", "| D-2 | mine |\n", DELIM)],
        owns=[],
        before_update_ref=sibling_commits,
    )
    assert fired == ["x"], "the seam fires once, on the first attempt only"
    assert res.attempts == 2
    dec = _git(r, "show", "HEAD:docs/DECISIONS.md")
    assert "| D-9 | sibling |" in dec and "| D-2 | mine |" in dec, dec
    assert _git(r, "log", "--format=%s", "-3").splitlines() == ["test: land", "sibling", "seed"]
    # the working file carries BOTH rows after the carry — the sibling's landed row must not be
    # a pending deletion (step 5b's second trap)
    assert _git(r, "diff", "HEAD", "--", "docs/DECISIONS.md") == ""


def test_a_siblings_staged_blob_in_the_shared_index_is_neither_shipped_nor_lost(
    tmp_path: Path,
) -> None:
    r = _repo(tmp_path)
    # sibling has STAGED a different hunk on the same shared file (dirty shared index)
    wt = (
        (r / "CHANGELOG.md")
        .read_text()
        .replace("## [Unreleased]\n\n", "## [Unreleased]\n\n### sibling wip\n\n")
    )
    (r / "CHANGELOG.md").write_text(wt)
    _git(r, "add", "CHANGELOG.md")
    pic.run(r, _msg(tmp_path), appends=[("CHANGELOG.md", "### mine\n\n", UNREL)], owns=[])
    committed = _git(r, "show", "HEAD:CHANGELOG.md")
    assert "### mine" in committed and "### sibling wip" not in committed, committed
    working = (r / "CHANGELOG.md").read_text()
    assert "### sibling wip" in working and working.count("### mine") == 1
    assert _git(r, "diff", "--cached", "--name-only") == "", "step 6 aligned the shared index"


def test_an_executable_own_file_keeps_its_bit(tmp_path: Path) -> None:
    r = _repo(tmp_path)
    s = r / "tool.sh"
    s.write_text("#!/bin/sh\n")
    s.chmod(s.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    res = pic.run(r, _msg(tmp_path), appends=[], owns=["tool.sh"])
    assert _git(r, "ls-tree", res.new, "--", "tool.sh").startswith("100755 blob ")


def test_missing_anchor_refuses_before_any_write(tmp_path: Path) -> None:
    r = _repo(tmp_path)
    base = _git(r, "rev-parse", "HEAD").strip()
    with pytest.raises(pic.RefusedError, match="anchor"):
        pic.run(r, _msg(tmp_path), appends=[("CHANGELOG.md", "x\n", r"^## \[Nope\]$")], owns=[])
    assert _git(r, "rev-parse", "HEAD").strip() == base
    assert "x\n" not in (r / "CHANGELOG.md").read_text()


def test_a_message_without_trailers_refuses_before_any_write(tmp_path: Path) -> None:
    r = _repo(tmp_path)
    base = _git(r, "rev-parse", "HEAD").strip()
    with pytest.raises(pic.RefusedError, match="Agent-Role"):
        pic.run(
            r, _msg(tmp_path, "no trailers\n"), appends=[("CHANGELOG.md", "x\n", UNREL)], owns=[]
        )
    assert _git(r, "rev-parse", "HEAD").strip() == base


def test_a_shared_append_file_passed_as_own_is_refused(tmp_path: Path) -> None:
    r = _repo(tmp_path)
    with pytest.raises(pic.RefusedError, match="shared-append"):
        pic.run(r, _msg(tmp_path), appends=[], owns=["CHANGELOG.md"])


def test_a_sync_trigger_path_prints_the_force_notice(tmp_path: Path, capsys) -> None:
    r = _repo(tmp_path)
    (r / ".pre-commit-config.yaml").write_text(
        "repos:\n- repo: local\n  hooks:\n  - id: governance-sync\n    files: '(^templates/governance/)'\n"
    )
    (r / "templates" / "governance").mkdir(parents=True)
    (r / "templates" / "governance" / "CLAUDE.md").write_text("x\n")
    _git(r, "add", ".pre-commit-config.yaml", "templates/governance/CLAUDE.md")
    _git(r, "commit", "-q", "-m", "seed2")
    (r / "templates" / "governance" / "CLAUDE.md").write_text("y\n")
    res = pic.run(r, _msg(tmp_path), appends=[], owns=["templates/governance/CLAUDE.md"])
    assert res.sync_trigger == ["templates/governance/CLAUDE.md"]
    assert "sync_enforcement_to_projects.py --force" in capsys.readouterr().out


def test_the_cli_lands_a_commit(tmp_path: Path) -> None:
    r = _repo(tmp_path)
    hunk = tmp_path / "hunk"
    hunk.write_text("### via cli\n\n")
    p = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "private_index_commit.py"),
            "--repo",
            str(r),
            "--msg-file",
            str(_msg(tmp_path)),
            "--append",
            "CHANGELOG.md",
            str(hunk),
            UNREL,
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert p.returncode == 0, p.stdout + p.stderr
    assert "### via cli" in _git(r, "show", "HEAD:CHANGELOG.md")
