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
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_merge_request_merge import World, _dead_pid, _git  # noqa: E402 — the merge tests' World


@pytest.fixture()
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


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
    monkeypatch.setattr(world.mod, "PRETEST_FLOOR_S", 0)  # a fixture leg takes milliseconds
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


def test_the_pretest_throwaway_is_never_the_owners_and_is_removed(world, monkeypatch):
    """The owner's sweep removes every `fabrik-merge-*` throwaway at the start of a merge, so a
    pretest that ran in one would be killed by any merge starting beside it."""
    where = world.tmp / "pretest-cwd"
    _counting_tests(world, f"pwd > {where}\n")
    _branch(world)
    before = _git(world.main, "worktree", "list", "--porcelain")

    assert _pretest(world, monkeypatch) == 0

    parent = Path(where.read_text().strip()).parent.name
    assert world.mod._PRETEST_DIR_RE.fullmatch(parent), parent
    assert not world.mod._THROWAWAY_DIR_RE.fullmatch(parent)
    assert _git(world.main, "worktree", "list", "--porcelain") == before  # removed after the leg


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


@pytest.mark.parametrize("tamper", ["script", "tree", "green", "head", "runner_sha256", "garbage"])
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
        rec[tamper] = {
            "tree": "-R",  # an option, not a tree id: `git diff -R HEAD^{tree}` would succeed
            "green": "yes",
            "head": "f" * 40,
            "runner_sha256": "0" * 64,
        }[tamper]
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


def test_a_base_move_on_index_md_runs_the_leg(world, monkeypatch):
    """INDEX.md is a test input in web-ecommerce-factory (test_cross_repo_cites), so it re-tests."""
    counter = _counting_tests(world)
    _branch(world)
    assert _pretest(world, monkeypatch) == 0
    world.write("INDEX.md", "# Index\n")
    world.commit_main("index", "INDEX.md")
    _git(world.main, "push", "-q", "origin", "master")

    assert world.run("merge") == 0

    assert counter.read_text() == "xx"


def test_the_owners_sweep_leaves_a_live_pretest_throwaway_alone(world):
    """A pretest runs outside the merge lock, so a merge's start-of-run sweep must not remove it."""
    parent = Path(tempfile.mkdtemp(prefix=world.mod._PRETEST_PREFIX))
    live = parent / world.main.name
    _git(world.main, "worktree", "add", "--detach", "-q", str(live), "master")
    head = world.branch({"x.txt": "x\n"})
    world.send(head)

    assert world.run("merge") == 0

    assert live.is_dir()
    assert str(live) in _git(world.main, "worktree", "list", "--porcelain")


def test_a_leg_under_the_floor_is_not_trusted(world, monkeypatch):
    counter = _counting_tests(world)
    _branch(world)
    assert _pretest(world, monkeypatch) == 0
    msg_id = _owner_request(world)
    monkeypatch.setattr(world.mod, "PRETEST_FLOOR_S", 60)

    assert world.run("merge") == 0

    assert counter.read_text() == "xx"
    assert "under 60s" in world.replies(msg_id)["fleet"]


def test_a_pretest_never_skips_its_own_leg_on_an_old_record(world, monkeypatch):
    counter = _counting_tests(world)
    head = _branch(world)
    assert _pretest(world, monkeypatch) == 0

    assert _pretest(world, monkeypatch) == 0  # the first run's green record is on disk

    assert counter.read_text() == "xx"
    assert json.loads(_record(world, head).read_text())["green"] is True


def test_a_killed_pretest_leg_is_not_called_a_red(world, monkeypatch, capsys):
    _counting_tests(world, "exit 124\n")
    head = _branch(world)

    assert _pretest(world, monkeypatch) != 0

    err = capsys.readouterr().err
    assert "timed out or was killed" in err and "not a test verdict" in err
    assert not _record(world, head).exists() and world.inbox() == []


def test_the_pretest_leg_writes_its_selector_records_privately(world, monkeypatch):
    seen = world.tmp / "records-dir"
    _counting_tests(world, f'echo "$FABRIK_MERGE_TESTS_RECORDS" > {seen}\n')
    _branch(world)

    assert _pretest(world, monkeypatch) == 0

    where = seen.read_text().strip()
    assert where and ".git" not in where and not Path(where).exists()  # private, and removed
    assert "FABRIK_MERGE_TESTS_RECORDS" not in os.environ


def test_a_killed_pretests_leftovers_are_swept_by_the_next(world, monkeypatch):
    _counting_tests(world)
    parent = Path(tempfile.mkdtemp(prefix=world.mod._PRETEST_PREFIX))
    stale = parent / world.main.name
    _git(world.main, "worktree", "add", "--detach", "-q", str(stale), "master")
    left = world.main / ".git" / "fabrik-merge" / "pretest" / ("e" * 40 + ".json")
    left.parent.mkdir(parents=True)
    rec = {"id": "e" * 40, "worktree": str(stale), "pid": _dead_pid(), "start": "1"}
    left.write_text(json.dumps(rec), encoding="utf-8")
    _branch(world)

    assert _pretest(world, monkeypatch) == 0

    assert not left.exists() and not stale.exists()
    assert str(stale) not in _git(world.main, "worktree", "list", "--porcelain")


# --- a repo-declared leg limit (wef's one leg outgrew TEST_TIMEOUT_S, 2026-10-24) ------------------
@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ("pytest\n", 1800),
        ("# merge-test-timeout: 2700\npytest\n", 2700),
        ("#merge-test-timeout:2700\n", 2700),
        ("# merge-test-timeout: 99999\n", 3600),  # clamped to the per-run budget
        ("# merge-test-timeout: 5\n", 60),  # clamped to the floor
        ("  # merge-test-timeout: 2700\n", 1800),  # not at line start: not a declaration
        ("# merge-test-timeout: 2700s\n", 1800),  # not the grammar
        ("# merge-test-timeout: 2400\n# merge-test-timeout: 3000\n", 2400),  # the first one
        ("# merge-test-timeout: 2700\r\nexit 0\r\n", 2700),  # a CRLF file
        ("# merge-test-timeout: 1234567\n", 3600),  # a long value is clamped, never ignored
    ],
)
def test_the_declared_leg_grammar(world, script, expected):
    assert world.mod._declared_leg(script) == expected


def _limits(world, monkeypatch) -> list[int]:
    seen: list[int] = []
    real = world.mod._capped

    def capped(argv, timeout):
        seen.append(int(timeout))
        return real(argv, timeout)

    monkeypatch.setattr(world.mod, "_capped", capped)
    return seen


def test_the_bases_declared_leg_is_the_merges_limit(world, monkeypatch):
    _counting_tests(world, "# merge-test-timeout: 2700\nexit 0\n")
    head = _branch(world)
    world.send(head)
    seen = _limits(world, monkeypatch)

    assert world.run("merge") == 0

    assert seen == [2700]


def test_a_branch_cannot_raise_its_own_leg_limit(world, monkeypatch):
    _counting_tests(world, "exit 0\n")
    _git(world.wt, "merge", "-q", "--ff-only", "master")
    head = world.branch({".fabrik/merge-tests": "# merge-test-timeout: 3600\nexit 0\n"})
    world.send(head)
    seen = _limits(world, monkeypatch)

    assert world.run("merge") == 0

    assert seen == [1800]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True])
def test_a_non_finite_or_bool_leg_time_is_ignored_never_a_crash(world, monkeypatch, value):
    counter = _counting_tests(world)
    head = _branch(world)
    assert _pretest(world, monkeypatch) == 0
    msg_id = _owner_request(world)
    path = _record(world, head)
    rec = json.loads(path.read_text())
    rec["seconds"] = value
    path.write_text(json.dumps(rec), encoding="utf-8")  # json writes NaN/Infinity, and reads them

    assert world.run("merge") == 0

    assert counter.read_text() == "xx"
    assert "pretest record ignored" in world.replies(msg_id)["fleet"]


def test_a_concurrent_pretest_of_the_same_head_keeps_the_others_bookkeeping(world, monkeypatch):
    """Each run's in-flight bookkeeping is its own file: a second pretest of one head unlinks the
    head's GREEN record path at its start, which must never be where the first run's sweep entry is."""
    seen = world.tmp / "during-leg"
    pretest_dir = world.main / ".git" / "fabrik-merge" / "pretest"
    _counting_tests(world, f"ls {pretest_dir} > {seen}\n")
    head = _branch(world)
    pid = os.getppid()  # a live process that is not this one
    other = pretest_dir / f"{head}.run-{pid}.json"
    other.parent.mkdir(parents=True)
    live = {
        "id": other.stem,
        "worktree": "/nowhere",
        "pid": pid,
        "start": world.mod._proc_start(pid),
    }
    other.write_text(json.dumps(live), encoding="utf-8")

    assert _pretest(world, monkeypatch) == 0

    assert json.loads(other.read_text()) == live
    assert json.loads(_record(world, head).read_text())["green"] is True
    left = sorted(p.name for p in other.parent.glob("*.json"))
    assert left == sorted([other.name, f"{head}.json"])  # this run's bookkeeping is gone
    during = seen.read_text().split()
    assert f"{head}.run-{os.getpid()}.json" in during and f"{head}.json" not in during


def test_an_unreadable_start_time_never_sweeps_a_pretest(world, monkeypatch):
    _counting_tests(world)
    parent = Path(tempfile.mkdtemp(prefix=world.mod._PRETEST_PREFIX))
    kept = parent / world.main.name
    _git(world.main, "worktree", "add", "--detach", "-q", str(kept), "master")
    left = world.main / ".git" / "fabrik-merge" / "pretest" / ("d" * 40 + ".json")
    left.parent.mkdir(parents=True)
    rec = {"id": "d" * 40, "worktree": str(kept), "pid": _dead_pid(), "start": None}
    left.write_text(json.dumps(rec), encoding="utf-8")
    _branch(world)

    assert _pretest(world, monkeypatch) == 0

    assert left.exists() and kept.is_dir()


def test_the_selector_writes_its_records_under_the_override(monkeypatch, tmp_path):
    """merge_test_select._record_path honours FABRIK_MERGE_TESTS_RECORDS and asks git nothing."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "merge_test_select_pretest",
        Path(__file__).resolve().parent.parent / "scripts" / "merge_test_select.py",
    )
    sel = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sel)
    monkeypatch.setenv("FABRIK_MERGE_TESTS_RECORDS", str(tmp_path))
    monkeypatch.setattr(sel, "_git", lambda *a: (_ for _ in ()).throw(AssertionError("git asked")))

    assert sel._record_path("b" * 40) == tmp_path / f"merge-tests-{'b' * 40}.txt"
    assert sel._green_path("c" * 40) == tmp_path / f"merge-tests-green-{'c' * 40}.txt"


def test_a_work_item_only_base_move_still_skips(world, monkeypatch):
    counter = _counting_tests(world)
    _branch(world)
    assert _pretest(world, monkeypatch) == 0
    msg_id = _owner_request(world)
    world.write(".fabrik/work/W-0123abcd.json", "{}\n")
    world.commit_main("item", ".fabrik/work/W-0123abcd.json")
    _git(world.main, "push", "-q", "origin", "master")

    assert world.run("merge") == 0

    assert counter.read_text() == "x"
    assert "green on the requester's pretest" in world.replies(msg_id)["fleet"]


def test_a_timeout_at_the_declared_full_leg_is_a_timeout_not_a_spent_budget(world, monkeypatch):
    """A leg that times out at its whole declared limit is the leg's verdict; only a leg cut short by
    the budget is "budget spent" (W-347cd0c3's split, now keyed on the declared leg)."""
    _counting_tests(world, "# merge-test-timeout: 600\nexit 0\n")
    head = _branch(world)
    msg_id = world.send(head)
    mod = world.mod

    def leg(ctx, wt, script, touched):
        ctx.leg_limit = mod._leg_timeout(ctx)
        assert ctx.leg_limit == 600
        raise mod.TimedOutError("the leg ran its whole limit")

    monkeypatch.setattr(mod, "_run_owner_leg", leg)

    assert world.run("merge") != 0

    reply = world.replies(msg_id)["fleet"]
    assert "ran out during the leg" not in reply and "the leg ran its whole limit" in reply
