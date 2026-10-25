"""W-0c8c43f1: `merge --queue` runs the owner tests of the waiting requests OUTSIDE the merge lock.

Measured in the hub 2026-10-24: once the merge-test leg switched on, a queue of requests waited one
~940 s leg after another (36-129 min) because `merge` held the lock for its whole run. `--queue` builds
the waiting requests as a STACKED chain in merge order (S0 = the base, Sk = request k onto S(k-1)),
runs each leg in a forked child at most `--jobs` at once, records each green tree exactly as
`request --pretest` does, then lands each request through the unchanged locked `merge`, whose
`_pretested` skips the leg on a matching tree. The same file's worktree add/remove/prune now
serialise under one lock (Fable's probe: 317 add failures in 2387 beside a prune loop).
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_merge_request_merge import World, _git  # noqa: E402 — the merge tests' World


@pytest.fixture()
def world(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    monkeypatch.setattr(w.mod, "PRETEST_FLOOR_S", 0)  # a fixture leg takes milliseconds
    monkeypatch.setattr(w.mod, "QUEUE_POLL_S", 0.05)
    return w


def _owner_tests(world, body: str) -> None:
    world.write(".fabrik/merge-tests", body)
    world.commit_main("owner tests", ".fabrik/merge-tests")
    _git(world.main, "push", "-q", "origin", "master")


def _leg_log(world, sleep: float = 0.3) -> Path:
    """A merge-tests leg that appends `<request head> <start> <stop> <subject of HEAD^1>` per run,
    so a test reads how many legs ran, on which chain element, and whether they overlapped."""
    log = world.tmp / "legs.log"
    script = (
        "python3 - <<'PY'\n"
        "import subprocess, time\n"
        "t0 = time.time()\n"
        f"time.sleep({sleep})\n"
        "def out(*a):\n"
        "    return subprocess.run(a, capture_output=True, text=True).stdout.strip()\n"
        "head = out('git', 'rev-parse', 'HEAD^2')\n"
        "on = out('git', 'log', '-1', '--format=%s', 'HEAD^1')\n"
        f"open({str(log)!r}, 'a').write(f'{{head}} {{t0}} {{time.time()}} {{on}}\\n')\n"
        "PY\n"
    )
    _owner_tests(world, script)
    return log


def _legs_on(log: Path) -> list[tuple[str, float, float, str]]:
    if not log.exists():
        return []
    out = []
    for line in log.read_text().splitlines():
        head, t0, t1, on = line.split(" ", 3)
        out.append((head, float(t0), float(t1), on))
    return out


def _legs(log: Path) -> list[tuple[str, float, float]]:
    return [(head, t0, t1) for head, t0, t1, _ in _legs_on(log)]


def _new_branch(world, name: str, files: dict[str, str]) -> tuple[str, str]:
    """A second requester worktree on ``name`` from the current base; returns (head, branch)."""
    wt = world.tmp / f"wt-{name}"
    _git(world.main, "worktree", "add", "-q", "-b", name, str(wt), "master")
    for rel, text in files.items():
        world.write(rel, text, root=wt)
        _git(wt, "add", "--", rel)
    _git(wt, "commit", "-q", "-m", f"{name} work")
    _git(wt, "push", "-q", "origin", name)
    return _git(wt, "rev-parse", "HEAD"), name


def _decision_row(world, n: int, text: str) -> str:
    """docs/DECISIONS.md with one row appended at the end of the base's table."""
    return (
        world.read("docs/DECISIONS.md").rstrip("\n")
        + f"\n| D-{n} | 2026-10-25 | t | {text} | w | x |\n"
    )


def _queue(world, *extra: str) -> int:
    return world.run("merge", "--queue", *extra)


# `_pretested`'s own summary when the locked merge SKIPS its leg on a record; a record it read and
# rejected is appended as "; pretest record ignored (...)" to a leg that ran, so "pretest" alone
# matches both (review pass 1, slice B)
SKIPPED = ".fabrik/merge-tests (base copy): green on the requester's pretest"


def _skipped(world, msg_id: str) -> bool:
    tests = [e for e in _record(world, msg_id).get("evidence", []) if e.startswith("tests: ")]
    return (
        len(tests) == 1 and tests[0].startswith(f"tests: {SKIPPED}") and "ignored" not in tests[0]
    )


def _record(world, msg_id: str) -> dict:
    return json.loads((world.main / ".git" / "fabrik-merge" / f"{msg_id}.json").read_text())


def _pretest_record(world, head: str) -> Path:
    return world.main / ".git" / "fabrik-merge" / "pretest" / f"{head}.json"


def test_queue_lands_stacked_requests_skipping_legs(world):
    log = _leg_log(world)
    h1, b1 = _new_branch(
        world, "one", {"a.txt": "a\n", "docs/DECISIONS.md": _decision_row(world, 900, "one")}
    )
    h2, b2 = _new_branch(
        world, "two", {"b.txt": "b\n", "docs/DECISIONS.md": _decision_row(world, 901, "two")}
    )
    m1 = world.send(h1, branch=b1)
    m2 = world.send(h2, branch=b2)

    assert _queue(world) == 0

    assert _record(world, m1)["outcome"] == "merged"
    assert _record(world, m2)["outcome"] == "merged"
    ran = [head for head, _, _ in _legs(log)]
    assert sorted(ran) == sorted([h1, h2]), ran  # one leg each, both run by the queue's children
    assert _skipped(world, m1) and _skipped(world, m2)  # each locked merge skipped its own leg
    decisions = world.read("docs/DECISIONS.md")
    assert "| D-900 |" in decisions and "| D-901 |" in decisions


def test_queue_skips_conflicting_request_and_rechains(world):
    log = _leg_log(world)
    h1, b1 = _new_branch(world, "one", {"notes.txt": "one\n"})
    h2, b2 = _new_branch(world, "two", {"notes.txt": "two\n"})  # conflicts with one
    h3, b3 = _new_branch(world, "three", {"c.txt": "c\n"})
    m1, m2, m3 = world.send(h1, branch=b1), world.send(h2, branch=b2), world.send(h3, branch=b3)

    assert _queue(world) != 0  # one request was refused

    assert _record(world, m1)["outcome"] == "merged"
    assert _record(world, m2)["outcome"] == "refused"
    assert _record(world, m3)["outcome"] == "merged"
    ran = [head for head, _, _ in _legs(log)]
    assert h2 not in ran, ran  # a request whose build conflicts gets no leg
    on3 = [on for head, _, _, on in _legs_on(log) if head == h3]
    # three was chained past the conflict onto one's STACKED element in the first wave, not
    # tested only after one landed
    assert on3 == ["queue pretest one"], on3
    assert _skipped(world, m3)  # three was chained onto one, so its record matched


def test_queue_red_leg_rechains_later_requests(world):
    log = world.tmp / "legs.log"
    script = (
        "python3 - <<'PY'\n"
        "import pathlib, subprocess, sys\n"
        "head = subprocess.run(['git', 'rev-parse', 'HEAD^2'], capture_output=True, text=True).stdout.strip()\n"
        f"open({str(log)!r}, 'a').write(head + '\\n')\n"
        "sys.exit(1 if pathlib.Path('red.txt').exists() else 0)\n"
        "PY\n"
    )
    _owner_tests(world, script)
    h1, b1 = _new_branch(world, "one", {"red.txt": "red\n"})
    h2, b2 = _new_branch(world, "two", {"b.txt": "b\n"})
    m1, m2 = world.send(h1, branch=b1), world.send(h2, branch=b2)

    assert _queue(world) != 0

    assert _record(world, m1)["outcome"] == "refused"
    assert _record(world, m2)["outcome"] == "merged"
    assert "red.txt" not in _git(world.main, "ls-tree", "-r", "--name-only", "master")
    assert not _pretest_record(world, h1).exists()  # a red leg leaves no record to trust
    assert not _skipped(world, m1)  # one's locked merge ran its own leg and refused
    # the first chain built two onto one's tree; after one's refusal two was re-chained onto the
    # base and re-tested there, so its locked merge still skipped
    assert _skipped(world, m2)


def test_queue_reuses_matching_record(world, monkeypatch):
    monkeypatch.delenv("FABRIK_MERGE_SHARDS", raising=False)
    log = _leg_log(world)
    h1, b1 = _new_branch(world, "one", {"a.txt": "a\n"})
    h2, b2 = _new_branch(world, "two", {"b.txt": "b\n"})
    m1 = world.send(h1, branch=b1)
    m2 = world.send(h2, branch=b2)
    ctx = world.mod._context(world.main)
    entries = world.mod._queue_entries(ctx, 4)
    chain = world.mod._build_chain(ctx, entries, world.base())
    assert [e["head"] for e in chain] == [h1, h2]
    for el in chain:
        assert world.mod._run_leg(ctx, el, world.mod._runner_sha()) == 0
    assert "FABRIK_MERGE_SHARDS" not in os.environ  # the child's default is restored
    assert len(_legs(log)) == 2

    assert _queue(world) == 0

    assert len(_legs(log)) == 2  # no leg re-ran: both records already named these trees
    assert _skipped(world, m1) and _skipped(world, m2)
    assert _record(world, m1)["outcome"] == "merged" and _record(world, m2)["outcome"] == "merged"


def test_queue_lock_refuses_second(world, capsys):
    _leg_log(world)
    h1, b1 = _new_branch(world, "one", {"a.txt": "a\n"})
    m1 = world.send(h1, branch=b1)
    ctx = world.mod._context(world.main)
    with world.mod._queue_lock(ctx):
        assert _queue(world) == 1
    assert "another merge --queue" in capsys.readouterr().err
    assert m1 in world.inbox()  # nothing was claimed


def test_queue_jobs_bounds_overlap(world):
    log = _leg_log(world, sleep=1.5)  # long enough that two children started apart still overlap
    sends = []
    for i in range(4):
        h, b = _new_branch(world, f"r{i}", {f"f{i}.txt": f"{i}\n"})
        sends.append(world.send(h, branch=b))

    assert _queue(world, "--jobs", "2") == 0

    legs = _legs(log)
    assert len(legs) == 4
    events = sorted([(t0, 1) for _, t0, _ in legs] + [(t1, -1) for _, _, t1 in legs])
    live = peak = 0
    for _, step in events:
        live += step
        peak = max(peak, live)
    assert peak == 2, legs  # two legs did overlap, never three
    assert all(_record(world, m)["outcome"] == "merged" for m in sends)


def test_throwaway_add_survives_concurrent_prune(world):
    ctx = world.mod._context(world.main)
    stop = threading.Event()

    def prune():
        while not stop.is_set():
            world.mod._sweep_throwaways(ctx)

    t = threading.Thread(target=prune)
    t.start()
    failures = []
    try:
        for _ in range(60):
            rec = {"id": "probe"}
            try:
                with world.mod._throwaway(ctx, rec, world.base(), world.mod._PRETEST_PREFIX):
                    pass
            except world.mod.RefusedError as exc:
                failures.append(str(exc))
    finally:
        stop.set()
        t.join()
    assert failures == []


def test_plain_merge_names_the_queue_when_two_wait(world, capsys):
    h1, b1 = _new_branch(world, "one", {"a.txt": "a\n"})
    h2, b2 = _new_branch(world, "two", {"b.txt": "b\n"})
    world.send(h1, branch=b1)
    world.send(h2, branch=b2)

    assert world.run("merge") == 0

    assert "merge --queue" in capsys.readouterr().err


def test_queue_without_owner_tests_lands_in_order(world):
    """A fleet repo with no `.fabrik/merge-tests`: nothing runs outside the lock, both still land."""
    h1, b1 = _new_branch(world, "one", {"a.txt": "a\n"})
    h2, b2 = _new_branch(world, "two", {"b.txt": "b\n"})
    m1, m2 = world.send(h1, branch=b1), world.send(h2, branch=b2)

    assert _queue(world) == 0

    assert _record(world, m1)["outcome"] == "merged" and _record(world, m2)["outcome"] == "merged"
    pretest = world.main / ".git" / "fabrik-merge" / "pretest"
    assert not pretest.is_dir() or not list(pretest.glob("*.json"))  # no leg ran outside the lock


def test_queue_refuses_jobs_under_one(world):
    with pytest.raises(SystemExit) as exc:
        world.run("merge", "--queue", "--jobs", "0")
    assert exc.value.code == 2


def test_queue_starts_no_landing_past_its_wall(world, monkeypatch, capsys):
    _leg_log(world)
    h1, b1 = _new_branch(world, "one", {"a.txt": "a\n"})
    m1 = world.send(h1, branch=b1)
    monkeypatch.setattr(world.mod, "QUEUE_WALL_S", world.mod.LANDING_WORST_S - 1)

    assert _queue(world) == 0

    assert "run `merge_request.py merge --queue` again" in capsys.readouterr().err
    assert m1 in world.inbox()  # nothing was claimed


def test_queue_wall_counts_the_lock_wait(world, monkeypatch, capsys):
    """A landing may first wait QUEUE_WAIT_S for the merge lock (`_land`): a wall that fits one locked
    merge but not that wait as well starts no landing (review pass 2, slice A)."""
    _leg_log(world)
    h1, b1 = _new_branch(world, "one", {"a.txt": "a\n"})
    m1 = world.send(h1, branch=b1)
    mod = world.mod
    one_merge = mod.MERGE_TEST_BUDGET_S + mod.PUSH_TIMEOUT_S + mod.SYNC_TIMEOUT_S + 300
    monkeypatch.setattr(mod, "QUEUE_WALL_S", one_merge + 60)

    assert _queue(world) == 0

    assert "again" in capsys.readouterr().err and m1 in world.inbox()


def test_worktree_lock_that_cannot_open_refuses(world, monkeypatch):
    ctx = world.mod._context(world.main)

    def refuse(*_a, **_k):
        raise PermissionError("read-only common dir")

    monkeypatch.setattr(world.mod.os, "open", refuse)
    with pytest.raises(world.mod.RefusedError, match="cannot open the worktree lock"):
        with world.mod._worktree_lock(ctx):
            pass


def test_land_passes_a_request_another_run_took(world, capsys):
    assert world.mod._land("01NOSUCHREQUEST0000000000") == 0
    assert "was taken by another run" in capsys.readouterr().err


def test_live_merge_never_waits_on_this_process(world):
    ctx = world.mod._context(world.main)
    rec = {"id": "01OWNRECORD", "phase": "claimed", **world.mod._claimer()}
    world.mod._save(ctx, rec)
    assert world.mod._live_merge(ctx, set()) is None  # a record this process drives
    world.mod._save(ctx, {**rec, "pid": 1, "start": world.mod._proc_start(1)})
    assert world.mod._live_merge(ctx, set()) == "01OWNRECORD"  # another live process's record


def test_queue_window_skips_landed_requests_before_the_limit(world):
    h1, b1 = _new_branch(world, "one", {"a.txt": "a\n"})
    h2, b2 = _new_branch(world, "two", {"b.txt": "b\n"})
    m1, m2 = world.send(h1, branch=b1), world.send(h2, branch=b2)
    ctx = world.mod._context(world.main)
    assert [e["id"] for e in world.mod._queue_entries(ctx, 1, {m1})] == [m2]
