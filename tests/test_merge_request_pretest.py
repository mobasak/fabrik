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
        ("# merge-test-timeout: 9999999999999999\n", 3600),
        ("# merge-test-timeout: " + "9" * 5000 + "\n", 3600),  # past int()'s digit limit
        ("# merge-test-timeout: 0000000000600\n", 600),  # leading zeros are still a number
    ],
)
def test_the_declared_leg_grammar(world, script, expected):
    assert world.mod._declared_leg(script) == expected


def test_the_hub_declares_its_own_longer_leg(world):
    # W-418c9d9f, D-1310: the hub leg outgrew TEST_TIMEOUT_S (exit 124 on the base copy, 2026-10-28; one file,
    # tests/test_assemble_dispatch_step.py, cannot be split across shards — the duration record read 1,466 s
    # and later 1,248 s that day, since every leg rewrites it)
    script = (Path(__file__).resolve().parents[1] / ".fabrik" / "merge-tests").read_text(
        encoding="utf-8"
    )
    assert world.mod._declared_leg(script) == 2700


# --- a repo-declared leg memory ceiling (W-e64a7b8e: fleet-docker-cpu's 244-file leg died at 137) --------
@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ("pytest\n", None),  # no declaration: capped_run's own default, argv unchanged
        ("# merge-test-mem: 8G\npytest\n", "8192M"),
        ("#merge-test-mem:6144M\n", "6144M"),
        ("# merge-test-mem: 8G\r\nexit 0\r\n", "8192M"),  # a CRLF file
        ("# merge-test-mem: 6G\n# merge-test-mem: 2G\n", "6144M"),  # the first one
        ("  # merge-test-mem: 8G\n", None),  # not at line start: not a declaration
        ("# merge-test-mem: 8g\n", None),  # not the grammar (capped_run's units are upper-case)
        ("# merge-test-mem: 8GB\n", None),
        ("# merge-test-mem: 8\n", None),  # a unit is required: bytes are never meant
        ("# merge-test-mem: 1.5G\n", None),
        ("# merge-test-mem: 99G\n", "MAX"),  # clamped to the leg's share of the shared slice
        pytest.param("# merge-test-mem: " + "9" * 5000 + "G\n", "MAX", id="past-int-digit-limit"),
        ("# merge-test-mem: 0G\n", "FLOOR"),  # a zero ceiling would kill everything: the floor
        ("# merge-test-mem: 1M\n", "FLOOR"),
        ("# merge-test-mem: 0008G\n", "8192M"),  # leading zeros are still a number
    ],
)
def test_the_declared_mem_grammar(world, script, expected):
    mod = world.mod
    want = {"MAX": f"{mod.LEG_MEM_MAX_MIB}M", "FLOOR": f"{mod.LEG_MEM_FLOOR_MIB}M"}.get(
        expected, expected
    )
    assert mod._declared_mem(script) == want


def test_the_mem_max_is_the_slice_less_one_default_run(world):
    """LEG_MEM_MAX_MIB is derived from capped_run.sh's own defaults (slice total less one run at its
    default), read from the runner itself — a MAX past that share, or a default moved without it,
    is red here (W-e64a7b8e review: a 12288 mutant passed every grammar row)."""
    import re as _re

    runner = (Path(__file__).resolve().parents[1] / "scripts" / "capped_run.sh").read_text()
    mib = {"M": 1, "G": 1024}

    def default(var: str) -> int:
        m = _re.search(r"\$\{" + var + r":-([0-9]+)([MG])\}", runner)
        assert m, var
        return int(m.group(1)) * mib[m.group(2)]

    want = default("FABRIK_TEST_SLICE_MAX") - default("FABRIK_TEST_MEM_MAX")
    assert world.mod.LEG_MEM_MAX_MIB == want == 8192


@pytest.mark.parametrize(
    ("script", "noted"),
    [
        ("# merge-test-mem: 8G  # measured 6 GiB\nexit 0\n", True),  # a reason on its line
        ("# merge-test-mem: 8GB\n# merge-test-mem: 2G\nexit 0\n", True),  # bad before a valid one
        ("#merge-test-memory: 8G\nexit 0\n", False),  # another header: not this one's shape
        ("# see merge-test-mem in D-1328\nexit 0\n", False),  # prose naming the header
        ("# merge-test-mem: 8G\nexit 0\n", False),
    ],
)
def test_which_mem_lines_are_named_as_ignored(world, script, noted):
    assert world.mod._mem_lines_ignored(script) is noted


@pytest.mark.parametrize(
    ("rc", "stderr", "expected"),
    [
        # capped_run prints its own line LAST: an earlier one (a nested run) is not the leg's verdict
        (
            137,
            "capped_run: killed at the memory ceiling (1G per run, 12G for x.slice) — inner\n"
            "capped_run: killed at the memory ceiling (8192M per run, 12G for x.slice) — sh -e -c a\n",
            "capped_run: killed at the memory ceiling (8192M per run, 12G for x.slice)",
        ),
        (
            124,
            "x\ncapped_run: stopped at the 2700s time limit — sh -e -c # a\n",
            "capped_run: stopped at the 2700s time limit",
        ),
        (124, "no verdict line\n", ""),  # the caller keeps its tail
        (
            137,
            "no verdict line\n",
            "exit 137 (a SIGKILL inside the leg; capped_run reported no memory-ceiling kill)",
        ),
        (1, "capped_run: killed at the memory ceiling (4G per run, 12G for x) — y\n", ""),
    ],
)
def test_the_capped_verdict_is_the_runners_last_line(world, rc, stderr, expected):
    assert world.mod._capped_verdict(rc, stderr) == expected


def test_the_hub_declares_its_own_leg_ceiling(world):
    # W-e64a7b8e: the hub leg runs 8 pytest shards in ONE capped scope; a 244-file selection died at 4G
    script = (Path(__file__).resolve().parents[1] / ".fabrik" / "merge-tests").read_text(
        encoding="utf-8"
    )
    assert world.mod._declared_mem(script) == "8192M"


def _mem_runner(world, rc: int = 0, ceiling_kill: bool = True) -> Path:
    """A stand-in for capped_run.sh that logs its argv's first line, then runs the command, or exits
    ``rc``. At 137 with ``ceiling_kill`` it first prints capped_run's own verdict line
    (capped_run.sh:160), which ends with the whole argv — the multi-line ``sh -c`` script, as in the
    incident; without it the 137 is a SIGKILL inside the leg, which capped_run passes through."""
    log = world.tmp / "mem-runner.log"
    runner = world.tmp / "mem-runner.sh"
    head = f'printf "%s\\n" "$*" | head -n1 >> {log}\nmem=4G\n'
    head += 'case "$3" in --mem) mem=$4 ;; esac\n'
    if not rc:
        tail = 'while [ "$1" != "--" ]; do shift; done\nshift\nexec "$@"'
    elif rc == 137 and ceiling_kill:
        tail = (
            'while [ "$1" != "--" ]; do shift; done\nshift\n'
            'echo "capped_run: killed at the memory ceiling ($mem per run, 12G for '
            'fabrik-agents-tests.slice) — $*" >&2\nexit 137'
        )
    else:
        tail = f"exit {rc}"
    runner.write_text(f"#!/bin/sh\n{head}{tail}\n", encoding="utf-8")
    runner.chmod(0o755)
    world.mp.setenv("FABRIK_CAPPED_RUN", str(runner))
    return log


def _runner_flags(log: Path) -> list[str]:
    """Each runner call's flags: everything before the first ``--``."""
    return [ln.split(" -- ")[0] for ln in log.read_text().splitlines()]


def test_the_bases_declared_mem_is_the_legs_ceiling(world):
    log = _mem_runner(world)
    _counting_tests(world, "# merge-test-mem: 8G\nexit 0\n")
    world.send(_branch(world))

    assert world.run("merge") == 0

    assert _runner_flags(log) == ["--timeout 1800 --mem 8192M"]


def test_no_declaration_passes_no_mem(world):
    log = _mem_runner(world)
    _counting_tests(world, "exit 0\n")
    world.send(_branch(world))

    assert world.run("merge") == 0

    assert _runner_flags(log) == ["--timeout 1800"]


def test_a_branch_cannot_raise_its_own_leg_ceiling(world):
    log = _mem_runner(world)
    _counting_tests(world, "exit 0\n")
    _git(world.wt, "merge", "-q", "--ff-only", "master")
    world.send(world.branch({".fabrik/merge-tests": "# merge-test-mem: 8G\nexit 0\n"}))

    assert world.run("merge") == 0

    assert _runner_flags(log) == ["--timeout 1800"]


_KILL = "capped_run: killed at the memory ceiling ({} per run, 12G for fabrik-agents-tests.slice)"
# the incident's script: comment lines last, so a 3-line tail of the kill line is shell comments
_SCRIPT_TAIL = "exit 0\n# a comment line\n# another comment line\n"


@pytest.mark.parametrize(
    ("script", "ceiling"),
    [
        ("# merge-test-mem: 6G\n" + _SCRIPT_TAIL, "6144M"),
        (_SCRIPT_TAIL, "4G"),  # no declaration: capped_run's own default, which its line states
    ],
)
def test_a_137_refusal_names_the_memory_ceiling(world, script, ceiling):
    _mem_runner(world, rc=137)
    _counting_tests(world, script)
    msg_id = world.send(_branch(world))

    assert world.run("merge") != 0

    reason = world.record(msg_id)["reason"]
    # the verdict ends where capped_run's " — <argv>" begins: no script text follows it
    assert f"exit 137): {_KILL.format(ceiling)};" in reason, reason
    assert "a comment line" not in reason and " — sh " not in reason, reason


def test_a_bare_137_is_not_called_a_ceiling_kill(world):
    _mem_runner(world, rc=137, ceiling_kill=False)
    _counting_tests(world, "# merge-test-mem: 6G\nexit 0\n")
    msg_id = world.send(_branch(world))

    assert world.run("merge") != 0

    reason = world.record(msg_id)["reason"]
    assert "a SIGKILL inside the leg; capped_run reported no memory-ceiling kill" in reason, reason
    assert "killed at the memory ceiling (" not in reason, reason


def test_a_pretest_137_names_the_memory_ceiling(world, monkeypatch, capsys):
    _mem_runner(world, rc=137)
    _counting_tests(world, "# merge-test-mem: 6G\n" + _SCRIPT_TAIL)
    _branch(world)

    assert _pretest(world, monkeypatch) != 0

    err = capsys.readouterr().err
    assert _KILL.format("6144M") in err, err


_IGNORED = "merge-test-mem line outside the grammar"


def test_an_ignored_mem_line_is_named(world):
    """A reason on the declaration's own line falls outside the grammar: the leg's own verdict says
    so, so the merge reply carries it rather than the leg silently keeping 4G."""
    log = _mem_runner(world)
    _counting_tests(world, "# merge-test-mem: 8G  # measured 6 GiB\nexit 0\n")
    msg_id = world.send(_branch(world))

    assert world.run("merge") == 0

    reply = world.replies(msg_id)["fleet"]
    assert _IGNORED in reply and "ignored" in reply, reply
    assert _runner_flags(log) == ["--timeout 1800"]


def test_a_pretest_names_an_ignored_mem_line(world, monkeypatch, capsys):
    """`request --pretest` (and so a `merge --queue` child, through the same `_pretest_leg`) prints
    the leg's verdict, which carries the note."""
    _mem_runner(world)
    _counting_tests(world, "# merge-test-mem: 8GB\nexit 0\n")
    _branch(world)

    assert _pretest(world, monkeypatch) == 0

    err = capsys.readouterr().err
    assert _IGNORED in err, err


def _limits(world, monkeypatch) -> list[int]:
    seen: list[int] = []
    real = world.mod._capped

    def capped(argv, timeout, mem=None):
        seen.append(int(timeout))
        return real(argv, timeout, mem)

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


def test_a_124_after_the_whole_declared_leg_is_a_red_not_a_spent_budget(world, monkeypatch):
    """The leg's own exit 124 after its WHOLE declared limit is a test verdict (the owner's `timeout`
    or the runner): "budget spent" is only a leg the budget cut short."""
    import subprocess as sp
    import time as real_time

    _counting_tests(world, "# merge-test-timeout: 600\nexit 0\n")
    head = _branch(world)
    msg_id = world.send(head)
    mod = world.mod
    skew = {"s": 0.0}

    class Clock:  # the module's `time`, with the leg's 600 s passing instantly
        def __getattr__(self, name):
            return getattr(real_time, name)

        def monotonic(self):
            return real_time.monotonic() + skew["s"]

    monkeypatch.setattr(mod, "time", Clock())

    def leg(ctx, wt, script, touched):
        ctx.leg_limit = mod._leg_timeout(ctx)
        skew["s"] += ctx.leg_limit + 1
        return sp.CompletedProcess(
            ["sh"], 124, "", "timed out\n"
        ), ".fabrik/merge-tests (base copy)"

    monkeypatch.setattr(mod, "_run_owner_leg", leg)

    assert world.run("merge") != 0

    reply = world.replies(msg_id)["fleet"]
    assert "owner tests red" in reply and "ran out during the leg" not in reply
