"""scripts/sysadmin/worktree_transcript_link.py — a worktree session stays listed in its repo window (D-467)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "worktree_transcript_link.py"
)
SID = "86cf0e31-98b4-4156-bce7-6b47d64cdc8c"


def _run(root: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "WORKTREE_LINK_PROJECTS_ROOT": str(root)},
    )


def _transcript(root: Path, key: str, sid: str = SID, body: str = '{"type":"user"}\n') -> Path:
    d = root / key
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{sid}.jsonl"
    f.write_text(body)
    return f


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    r = tmp_path / "projects"
    r.mkdir()
    (r / "-opt-web-ecommerce-factory").mkdir()
    return r


def test_the_hook_links_a_worktree_transcript_into_the_repo_root_key(root: Path) -> None:
    src = _transcript(root, "-opt-web-ecommerce-factory--claude-worktrees-wef1")
    payload = {
        "session_id": SID,
        "transcript_path": str(src),
        "cwd": "/opt/web-ecommerce-factory/.claude/worktrees/wef1",
    }
    r = _run(root, stdin=json.dumps(payload))
    assert (r.returncode, r.stdout) == (0, "")
    dst = root / "-opt-web-ecommerce-factory" / f"{SID}.jsonl"
    assert os.path.samefile(src, dst)


def test_a_later_append_is_visible_through_the_repo_root_name(root: Path) -> None:
    src = _transcript(root, "-opt-web-ecommerce-factory--claude-worktrees-wef1")
    _run(root, stdin=json.dumps({"session_id": SID, "transcript_path": str(src)}))
    with src.open("a") as fh:
        fh.write('{"type":"assistant"}\n')
    dst = root / "-opt-web-ecommerce-factory" / f"{SID}.jsonl"
    assert dst.read_text().count("\n") == 2


def test_a_stale_transcript_path_is_resolved_by_session_id(root: Path) -> None:
    """The transcript moves when a session enters a worktree; the hook may be handed the old path."""
    src = _transcript(root, "-opt-web-ecommerce-factory--claude-worktrees-wef3")
    stale = root / "-opt-web-ecommerce-factory" / "gone" / f"{SID}.jsonl"
    _run(root, stdin=json.dumps({"session_id": SID, "transcript_path": str(stale)}))
    assert os.path.samefile(src, root / "-opt-web-ecommerce-factory" / f"{SID}.jsonl")


def test_a_missing_repo_root_key_is_created_for_a_real_repo(root: Path, tmp_path: Path) -> None:
    repo = tmp_path / "new-repo"
    (repo / ".claude" / "worktrees" / "lane").mkdir(parents=True)
    src = _transcript(root, "-opt-new-repo--claude-worktrees-lane")
    cwd = str(repo / ".claude" / "worktrees" / "lane")
    _run(root, stdin=json.dumps({"session_id": SID, "transcript_path": str(src), "cwd": cwd}))
    dst = root / "-opt-new-repo" / f"{SID}.jsonl"
    assert os.path.samefile(src, dst)
    assert (dst.parent.stat().st_mode & 0o777) == 0o700


@pytest.mark.parametrize("cwd", [None, "/nonexistent-repo/.claude/worktrees/lane", "/opt/x"])
def test_no_repo_root_key_is_created_without_a_real_repo_root(root: Path, cwd: str | None) -> None:
    """A throwaway probe repo that no window ever opened gets no new transcript dir."""
    src = _transcript(root, "-tmp-probe--claude-worktrees-agent-alpha")
    payload = {"session_id": SID, "transcript_path": str(src), "cwd": cwd}
    _run(root, stdin=json.dumps(payload))
    assert not (root / "-tmp-probe").exists()
    assert src.stat().st_nlink == 1


def test_a_repo_root_session_is_left_alone(root: Path) -> None:
    src = _transcript(root, "-opt-web-ecommerce-factory")
    _run(root, stdin=json.dumps({"session_id": SID, "transcript_path": str(src)}))
    assert sorted(p.name for p in root.iterdir()) == ["-opt-web-ecommerce-factory"]
    assert src.stat().st_nlink == 1


def test_a_different_file_under_the_root_name_is_never_overwritten(root: Path) -> None:
    src = _transcript(root, "-opt-web-ecommerce-factory--claude-worktrees-wef1")
    other = _transcript(root, "-opt-web-ecommerce-factory", body="someone else's transcript\n")
    _run(root, stdin=json.dumps({"session_id": SID, "transcript_path": str(src)}))
    assert other.read_text() == "someone else's transcript\n"
    r = _run(root, "--sweep")
    assert r.returncode == 1
    assert f"conflict: -opt-web-ecommerce-factory--claude-worktrees-wef1/{SID}.jsonl" in r.stdout


@pytest.mark.parametrize("sid", ["*", "?" * 8, "[ab]*", "a*"])
def test_a_session_id_is_a_literal_name_never_a_glob(root: Path, tmp_path: Path, sid: str) -> None:
    """An unescaped `*` matched every worktree transcript and linked it into another repo's key."""
    (root / "-opt-tryton-crm").mkdir()
    other = _transcript(root, "-opt-tryton-crm--claude-worktrees-agent-3", sid="aaaabbbb")
    mine = _transcript(root, "-opt-web-ecommerce-factory--claude-worktrees-wef1")
    repo = tmp_path / "web-ecommerce-factory"
    (repo / ".claude" / "worktrees" / "wef1").mkdir(parents=True)
    cwd = str(repo / ".claude" / "worktrees" / "wef1")
    r = _run(root, stdin=json.dumps({"session_id": sid, "cwd": cwd}))
    assert (r.returncode, r.stdout) == (0, "")
    assert other.stat().st_nlink == 1 and mine.stat().st_nlink == 1
    assert sorted(p.name for p in (root / "-opt-tryton-crm").iterdir()) == []


def test_sweep_reports_one_unlinkable_file_and_links_the_rest(root: Path) -> None:
    (root / "-opt-locked").mkdir()
    blocked = _transcript(root, "-opt-locked--claude-worktrees-a", sid="1" * 8)
    fine = _transcript(root, "-opt-web-ecommerce-factory--claude-worktrees-wef1", sid="2" * 8)
    (root / "-opt-locked").chmod(0o500)
    try:
        r = _run(root, "--sweep")
    finally:
        (root / "-opt-locked").chmod(0o700)
    assert r.returncode == 1
    assert "Traceback" not in r.stderr
    assert f"error: -opt-locked--claude-worktrees-a/{blocked.name}" in r.stdout
    assert "error 1" in r.stdout and "linked 1" in r.stdout
    assert os.path.samefile(fine, root / "-opt-web-ecommerce-factory" / fine.name)


def test_dry_run_survives_a_transcript_removed_mid_sweep(root: Path) -> None:
    """A dangling glob hit (here a symlink to nothing) is a per-file verdict, not a traceback."""
    d = root / "-opt-web-ecommerce-factory--claude-worktrees-wef1"
    d.mkdir()
    (d / "gone.jsonl").symlink_to(d / "nowhere.jsonl")
    # the repo-root name exists, so a check that skips the transcript's own existence reaches
    # samefile() on a file that is not there (FileNotFoundError, the round-1 crash)
    (root / "-opt-web-ecommerce-factory" / "gone.jsonl").write_text("{}\n")
    r = _run(root, "--sweep", "--dry-run")
    assert r.returncode == 0
    assert "Traceback" not in r.stderr
    assert "missing 1" in r.stdout


@pytest.mark.parametrize(
    "stdin", ["", "not json", "[]", '{"session_id": "../../etc"}', '{"transcript_path": 7}']
)
def test_the_hook_fails_open_and_silent(root: Path, stdin: str) -> None:
    r = _run(root, stdin=stdin)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_sweep_links_every_worktree_transcript_and_dry_run_links_none(root: Path) -> None:
    (root / "-opt-tryton-crm").mkdir()
    a = _transcript(root, "-opt-web-ecommerce-factory--claude-worktrees-wef1", sid="a" * 8)
    b = _transcript(root, "-opt-tryton-crm--claude-worktrees-agent-3", sid="b" * 8)
    probe = _transcript(root, "-tmp-probe--claude-worktrees-agent-alpha", sid="c" * 8)
    dry = _run(root, "--sweep", "--dry-run")
    assert dry.returncode == 0
    assert "no-root-key 1" in dry.stdout and "would-link 2" in dry.stdout
    assert a.stat().st_nlink == 1 and b.stat().st_nlink == 1
    real = _run(root, "--sweep")
    assert real.returncode == 0
    assert "examined: 3" in real.stdout and "linked 2" in real.stdout
    assert os.path.samefile(a, root / "-opt-web-ecommerce-factory" / a.name)
    assert os.path.samefile(b, root / "-opt-tryton-crm" / b.name)
    assert probe.stat().st_nlink == 1 and not (root / "-tmp-probe").exists()
    again = _run(root, "--sweep")
    assert "already 2" in again.stdout
