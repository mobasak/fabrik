"""W-1fb11ec8 (proposal B): the owner merge tests run ONCE per change.

Measured on web-ecommerce-factory 2026-10-24: a merge held the serial merge lock 18-28 min running
`.fabrik/merge-tests`, and its builder had already run the same suite for 19-29 min before
requesting. `request --pretest` runs the leg on the merge the owner would build and records the
merged tree; the merge skips its own leg when its merged tree matches that record modulo the
ledgers and work-item files, and runs it otherwise.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_merge_request_merge import _git, world  # noqa: E402,F401 — the merge tests' own fixture


def _counting_tests(world, script: str = "") -> Path:
    counter = world.tmp / "test-runs"
    body = script or f"python3 -c \"open({str(counter)!r}, 'a').write('x')\"\n"
    world.write(".fabrik/merge-tests", body)
    world.commit_main("owner tests", ".fabrik/merge-tests")
    _git(world.main, "push", "-q", "origin", "master")
    return counter


def _pretest(world, monkeypatch) -> int:
    """`request --pretest` from the requester's worktree, as the requester."""
    review = world.tmp / "review.md"
    review.write_text("# receipt\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_AGENT", "fleet")
    monkeypatch.chdir(world.wt)
    try:
        return world.mod.main(["request", "--review", str(review), "--pretest"])
    finally:
        monkeypatch.setenv("CLAUDE_AGENT", "infra")
        monkeypatch.chdir(world.main)


def _record(world, head: str) -> Path:
    return world.main / ".git" / "fabrik-merge" / "pretest" / f"{head}.json"


def _branch(world) -> str:
    _git(world.wt, "merge", "-q", "--ff-only", "master")  # the branch starts on the current base
    return world.branch({"x.txt": "x\n"})


def _owner_request(world) -> str:
    box = world.tmp / "mail" / "proj" / "inbox"
    ids = [
        p.stem
        for p in sorted(box.glob("*.md"))
        if "kind: merge-request" in p.read_text() and "agent: infra" in p.read_text()
    ]
    assert len(ids) == 1, ids
    return ids[0]


def test_a_green_pretest_records_the_merged_tree(world, monkeypatch):
    counter = _counting_tests(world)
    head = _branch(world)

    assert _pretest(world, monkeypatch) == 0

    rec = json.loads(_record(world, head).read_text())
    assert counter.read_text() == "x"
    assert rec["green"] is True and rec["head"] == head and rec["base_old"] == world.base()
    expected = _git(world.main, "merge-tree", "--write-tree", "master", head)
    assert rec["tree"] == expected
    script = (world.main / ".fabrik" / "merge-tests").read_bytes()
    assert rec["script_sha256"] == hashlib.sha256(script).hexdigest()
    assert _owner_request(world)  # the request went out after the green run


def test_a_red_pretest_sends_nothing_and_records_nothing(world, monkeypatch, capsys):
    _counting_tests(world, "exit 1\n")
    head = _branch(world)

    assert _pretest(world, monkeypatch) != 0

    assert not _record(world, head).exists()
    assert world.inbox() == []
    assert "owner tests red" in capsys.readouterr().err


def test_the_merge_skips_its_leg_on_the_pretested_tree(world, monkeypatch, capsys):
    counter = _counting_tests(world)
    head = _branch(world)
    assert _pretest(world, monkeypatch) == 0
    msg_id = _owner_request(world)

    assert world.run("merge") == 0

    assert counter.read_text() == "x"  # one run: the pretest's
    assert _git(world.main, "rev-parse", "master^2") == head
    reply = world.replies(msg_id)["fleet"]
    assert "green on the requester's pretest" in reply
    assert "WARNING" not in capsys.readouterr().err  # the record is no merge record


def test_a_ledger_only_base_move_still_skips(world, monkeypatch):
    counter = _counting_tests(world)
    _branch(world)
    assert _pretest(world, monkeypatch) == 0
    msg_id = _owner_request(world)
    world.write("CHANGELOG.md", world.read("CHANGELOG.md") + "- a sibling's entry\n")
    world.commit_main("ledger", "CHANGELOG.md")
    _git(world.main, "push", "-q", "origin", "master")

    assert world.run("merge") == 0

    assert counter.read_text() == "x"
    assert "1 ledger path(s) differ" in world.replies(msg_id)["fleet"]


def test_a_code_base_move_runs_the_leg(world, monkeypatch):
    counter = _counting_tests(world)
    _branch(world)
    assert _pretest(world, monkeypatch) == 0
    msg_id = _owner_request(world)
    world.write("notes.txt", "moved\n")
    world.commit_main("code", "notes.txt")
    _git(world.main, "push", "-q", "origin", "master")

    assert world.run("merge") == 0

    assert counter.read_text() == "xx"
    assert "requester's pretest" not in world.replies(msg_id)["fleet"]


@pytest.mark.parametrize("tamper", ["script", "tree", "green", "head", "garbage"])
def test_a_record_failing_a_check_runs_the_leg_and_says_why(world, monkeypatch, tamper):
    counter = _counting_tests(world)
    head = _branch(world)
    assert _pretest(world, monkeypatch) == 0
    msg_id = _owner_request(world)
    path = _record(world, head)
    rec = json.loads(path.read_text())
    if tamper == "script":
        world.write(".fabrik/merge-tests", (world.main / ".fabrik/merge-tests").read_text() + "\n")
        world.commit_main("owner tests changed", ".fabrik/merge-tests")
        _git(world.main, "push", "-q", "origin", "master")
    elif tamper == "garbage":
        path.write_text("{not json", encoding="utf-8")
    else:
        rec[tamper] = {"tree": "0" * 40, "green": "yes", "head": "f" * 40}[tamper]
        path.write_text(json.dumps(rec), encoding="utf-8")

    assert world.run("merge") == 0

    assert counter.read_text() == "xx"
    assert "pretest record ignored" in world.replies(msg_id)["fleet"]


def test_no_base_merge_tests_sends_with_a_note_and_runs_nothing(world, monkeypatch, capsys):
    head = _branch(world)

    assert _pretest(world, monkeypatch) == 0

    assert not _record(world, head).exists()
    assert _owner_request(world)
    assert "nothing to pretest" in capsys.readouterr().err
