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


# --- W-d5d1d394: the queue landed nothing on 2026-10-27 (two hub runs) --------------------------------
# Two 4-shard legs at once doubled each leg's wall against the unchanged per-leg limit; the wall left no
# landing after a wave that used its limit; legs forked for later requests held the queue lock 30 min
# after it stopped; and a later leg ran beside a locked merge running its own leg.


def _kind_log(world, fail_queue_on: str = "") -> Path:
    """A leg that appends `<request head> <queue|locked> <start> <stop>`: `queue` when it runs in a
    queue child (FABRIK_MERGE_TESTS_RECORDS is set by `_run_leg` and by `request --pretest`, never
    by the locked merge). With ``fail_queue_on``, a queue leg
    whose merge adds that file exits 124 — a leg that "timed out", leaving no record."""
    log = world.tmp / "kinds.log"
    script = (
        "python3 - <<'PY'\n"
        "import os, subprocess, sys, time\n"
        "t0 = time.time()\n"
        "time.sleep(0.5)\n"
        "head = subprocess.run(['git', 'rev-parse', 'HEAD^2'], capture_output=True, text=True).stdout.strip()\n"
        "kind = 'queue' if os.environ.get('FABRIK_MERGE_TESTS_RECORDS') else 'locked'\n"
        f"open({str(log)!r}, 'a').write(f'{{head}} {{kind}} {{t0}} {{time.time()}}\\n')\n"
        "added = subprocess.run(['git', 'diff', '--name-only', 'HEAD^1', 'HEAD'], capture_output=True, text=True).stdout.split()\n"
        f"sys.exit(124 if kind == 'queue' and {fail_queue_on!r} in added else 0)\n"
        "PY\n"
    )
    _owner_tests(world, script)
    return log


def _kinds(log: Path) -> list[tuple[str, str, float, float]]:
    if not log.exists():
        return []
    rows = [line.split(" ") for line in log.read_text().splitlines()]
    return [(h, k, float(t0), float(t1)) for h, k, t0, t1 in rows]


def test_queue_child_keeps_the_selector_width(world, monkeypatch):
    """A queue child runs the owner script with the caller's FABRIK_MERGE_SHARDS, or none: no
    halving of the leg's width against a limit sized for a full-width leg."""
    log = world.tmp / "shards.log"
    _owner_tests(world, f'echo "${{FABRIK_MERGE_SHARDS:-unset}}" >> {log}\n')
    h1, b1 = _new_branch(world, "one", {"a.txt": "a\n"})
    m1 = world.send(h1, branch=b1)
    monkeypatch.delenv("FABRIK_MERGE_SHARDS", raising=False)

    assert _queue(world) == 0

    assert log.read_text().split() == ["unset"]  # one leg, the queue child's; the landing skipped
    assert _skipped(world, m1)
    h2, b2 = _new_branch(world, "two", {"b.txt": "b\n"})
    world.send(h2, branch=b2)
    monkeypatch.setenv("FABRIK_MERGE_SHARDS", "3")

    assert _queue(world) == 0

    assert log.read_text().split() == ["unset", "3"]


def test_queue_default_runs_one_leg_at_a_time(world):
    log = _leg_log(world, sleep=1.0)
    sends = []
    for i in range(3):
        h, b = _new_branch(world, f"r{i}", {f"f{i}.txt": f"{i}\n"})
        sends.append(world.send(h, branch=b))

    assert _queue(world) == 0

    legs = sorted((t0, t1) for _, t0, t1 in _legs(log))
    assert len(legs) == 3
    # never two at once
    assert all(a[1] <= b[0] for a, b in zip(legs, legs[1:], strict=False)), legs
    assert all(_record(world, m)["outcome"] == "merged" for m in sends)


def test_queue_wall_fits_a_full_leg_then_a_landing(world):
    """The first wave may run the longest leg any base can declare and still be followed by a
    worst-case landing: a wall with no room after it lands nothing (02:48:18, elapsed ~1818 s)."""
    mod = world.mod
    longest = "# merge-test-timeout: 999999\n"
    assert mod._declared_leg(longest) == mod.MERGE_TEST_BUDGET_S
    assert hasattr(mod, "_leg_fits"), "no leg-fit guard"
    now = mod.time.monotonic()
    assert mod._leg_fits(now, longest)  # at the start: the longest leg, then a landing
    edge = mod.QUEUE_BUILD_S - mod.LEG_OVERHEAD_S  # what is left for the chain build
    assert edge > 0
    assert mod._leg_fits(now - edge + 1, longest)
    assert not mod._leg_fits(now - edge - 1, longest)


def test_queue_starts_no_leg_past_its_wall(world, monkeypatch):
    """A leg that could not finish AND be followed by a landing never forks; while a landing still
    fits, each request lands through its locked merge, which runs its own leg (the pre-queue path)."""
    log = _kind_log(world)
    h1, b1 = _new_branch(world, "one", {"a.txt": "a\n"})
    h2, b2 = _new_branch(world, "two", {"b.txt": "b\n"})
    m1, m2 = world.send(h1, branch=b1), world.send(h2, branch=b2)
    # a landing fits for 600 s; no default-limit leg ever does
    monkeypatch.setattr(world.mod, "QUEUE_WALL_S", world.mod.LANDING_WORST_S + 600)

    assert _queue(world) == 0

    assert [(h, k) for h, k, _, _ in _kinds(log)] == [(h1, "locked"), (h2, "locked")]
    assert _record(world, m1)["outcome"] == "merged" and _record(world, m2)["outcome"] == "merged"
    assert not _skipped(world, m1) and not _skipped(world, m2)


def test_queue_forks_no_leg_beside_a_locked_leg(world):
    """The first request's queue leg leaves no record (it "timed out"), so its locked merge runs its
    own leg: no later queue leg runs beside it (16 processes on 24 CPUs tonight)."""
    log = _kind_log(world, fail_queue_on="slow.txt")
    h1, b1 = _new_branch(world, "one", {"slow.txt": "x\n"})
    h2, b2 = _new_branch(world, "two", {"b.txt": "b\n"})
    m1, m2 = world.send(h1, branch=b1), world.send(h2, branch=b2)

    assert _queue(world) == 0

    rows = _kinds(log)
    locked1 = [r for r in rows if r[0] == h1 and r[1] == "locked"]
    queue2 = [r for r in rows if r[0] == h2 and r[1] == "queue"]
    assert len(locked1) == 1 and queue2, rows
    assert all(q[2] >= locked1[0][3] for q in queue2), rows  # two's leg forked after one's ended
    assert _record(world, m1)["outcome"] == "merged" and _record(world, m2)["outcome"] == "merged"
    assert _skipped(world, m2)


# W-1fb11ec8 slice 3: a later leg's USEFULNESS is budgeted on the longest green leg this run timed
# (697 s live on 2026-10-30), its SAFETY still on the declared limit — the old rule closed the fork
# window at 1080 s of the hub's 11100 s wall, so the third request on ran its leg inside the lock.
HUB = "# merge-test-timeout: 2700\n"


def test_leg_fits_budgets_the_longest_timed_leg(world):
    mod = world.mod
    now = mod.time.monotonic()
    old_edge = mod.QUEUE_WALL_S - mod.LANDING_WORST_S - mod._declared_leg(HUB) - mod.LEG_OVERHEAD_S
    assert old_edge == 1080  # the window measured on the hub tonight
    late = old_edge + 600  # past the old window
    assert not mod._leg_fits(now - late, HUB)  # nothing timed: today's rule
    assert mod._leg_fits(now - late, HUB, 697.0)  # a 697 s green leg leaves a landing after it
    # budgeted at 1.5 x the timed leg: hub legs under load spread ~30 % (D-1312)
    timed_edge = mod.QUEUE_WALL_S - mod.LANDING_WORST_S - 1.5 * 697 - mod.LEG_OVERHEAD_S
    assert mod._leg_fits(now - timed_edge + 5, HUB, 697.0)  # 5 s slack: a stall never flips it
    assert not mod._leg_fits(now - timed_edge - 5, HUB, 697.0)  # no landing could follow it
    # never budgeted above the declared limit, however long a timed leg was
    assert mod._leg_fits(now, HUB, 2600.0) == mod._leg_fits(now, HUB)


def test_leg_fits_keeps_the_declared_wall_bound(world):
    """However short the timed legs, a leg forked at the last moment `_leg_fits` allows and running
    its whole DECLARED limit still ends inside the wall, so the capped_run wrapper never kills a leg
    the queue then joins: a landing's worst case outweighs the longest leg any base may declare."""
    mod = world.mod
    longest = "# merge-test-timeout: 999999\n"
    declared = mod._declared_leg(longest) + mod.LEG_OVERHEAD_S
    assert declared < mod.LANDING_WORST_S
    now = mod.time.monotonic()
    for timed in (0.0, 1.0, 697.0):
        last = max(  # the latest elapsed second at which it still forks
            s for s in range(0, mod.QUEUE_WALL_S + 1, 5) if mod._leg_fits(now - s, longest, timed)
        )
        assert last + declared <= mod.QUEUE_WALL_S, (timed, last)


def _spy_fits(world, monkeypatch) -> list[float]:
    """Wrap `_leg_fits` so a test reads the `timed` budget `_queue` passed at every call."""
    seen: list[float] = []
    real = world.mod._leg_fits

    def spy(started, script, timed=0.0):
        seen.append(timed)
        return real(started, script, timed)

    monkeypatch.setattr(world.mod, "_leg_fits", spy)
    return seen


def test_queue_times_only_green_legs(world, monkeypatch):
    """A queue leg that ends on a matching record raises the budget to its own recorded seconds; one that leaves
    no record (red, killed, timed out) never does, so a fast failure cannot open the window."""
    _leg_log(world, sleep=1.2)  # a record keeps whole seconds: 1
    sends, heads = [], []
    for i in range(3):
        h, b = _new_branch(world, f"g{i}", {f"g{i}.txt": f"{i}\n"})
        sends.append(world.send(h, branch=b))
        heads.append(h)
    seen = _spy_fits(world, monkeypatch)
    recorded: list[float] = []
    real_matches = world.mod._record_matches

    def keep(ctx, el, script, runner):
        ok = real_matches(ctx, el, script, runner)
        if ok:  # the seconds the matching record holds, as `_queue` reads them
            recorded.append(json.loads(_pretest_record(world, el["head"]).read_text())["seconds"])
        return ok

    monkeypatch.setattr(world.mod, "_record_matches", keep)

    assert _queue(world) == 0

    assert seen and seen[0] == 0.0  # the first fork is budgeted on the declared limit
    assert recorded and max(seen) in recorded, (
        seen,
        recorded,
    )  # the leg's own seconds, not a clock
    assert all(_record(world, m)["outcome"] == "merged" for m in sends)


def test_queue_keeps_the_longest_timed_leg(world, monkeypatch):
    """A slow green leg then faster ones: the budget stays at the SLOW leg's recorded seconds, so a
    later quick leg never shrinks it below what this run already saw (review r1 B1)."""
    script = (  # keyed on the REQUEST's own subject: a stacked tree carries every earlier file
        "python3 - <<'PY'\n"
        "import subprocess, time\n"
        "s = subprocess.run(['git', 'log', '-1', '--format=%s', 'HEAD^2'], capture_output=True, text=True).stdout\n"
        "time.sleep(4.5 if s.startswith('slow') else 1.2)\n"  # whole seconds: a gap no load closes
        "PY\n"
    )
    _owner_tests(world, script)
    sends = []
    for name, files in (
        ("slow", {"slow.txt": "x\n"}),
        ("fast", {"f.txt": "f\n"}),
        ("last", {"l.txt": "l\n"}),
    ):
        h, b = _new_branch(world, name, files)
        sends.append(world.send(h, branch=b))
    seen = _spy_fits(world, monkeypatch)
    timed: list[float] = []  # each green queue leg's seconds, in the order the queue read them
    real_seconds = world.mod._leg_seconds

    def keep(*a):
        s = real_seconds(*a)
        if s:
            timed.append(s)
        return s

    monkeypatch.setattr(world.mod, "_leg_seconds", keep)

    assert _queue(world) == 0

    assert len(timed) >= 2 and timed[0] > min(timed), timed  # a faster leg came after the slow one
    assert seen[-1] == max(timed), (seen, timed)  # the budget kept the slow one
    assert all(_record(world, m)["outcome"] == "merged" for m in sends)


def test_queue_never_times_a_leg_without_a_record(world, monkeypatch):
    """One's queue leg exits 124 (no record): every budget the queue reads is zero or a GREEN queue
    leg's own recorded seconds (two's), never anything one's failed leg left."""
    log = _kind_log(world, fail_queue_on="slow.txt")
    h1, b1 = _new_branch(world, "one", {"slow.txt": "x\n"})
    h2, b2 = _new_branch(world, "two", {"b.txt": "b\n"})
    m1, m2 = world.send(h1, branch=b1), world.send(h2, branch=b2)
    seen = _spy_fits(world, monkeypatch)
    green: list[float] = []
    real_seconds = world.mod._leg_seconds

    def keep(ctx, el, script, runner):
        s = real_seconds(ctx, el, script, runner)
        if s:
            assert el["head"] == h2, el  # only two's green leg is ever timed
            green.append(s)
        return s

    monkeypatch.setattr(world.mod, "_leg_seconds", keep)

    assert _queue(world) == 0

    assert any(h == h2 and k == "queue" for h, k, _, _ in _kinds(log))  # two's fork was checked
    assert len(seen) >= 2 and seen[0] == 0.0, seen
    assert set(seen) <= {0.0, *green}, (seen, green)  # nothing but two's own green seconds
    assert _record(world, m1)["outcome"] == "merged" and _record(world, m2)["outcome"] == "merged"


def test_leg_seconds_reads_only_the_queue_legs_own_record(world, monkeypatch):
    """A matching record the requester's own `request --pretest` wrote (no `queued_as` of this
    element) says nothing about the queue leg that just exited: it is never timed."""
    mod = world.mod
    ctx = mod._context(world.main)
    (ctx.records / mod.PRETEST_DIR).mkdir(parents=True, exist_ok=True)
    el = {"id": "01REQUESTID", "head": "a" * 40, "at": "b" * 40}
    path = ctx.records / mod.PRETEST_DIR / f"{el['head']}.json"
    monkeypatch.setattr(mod, "_record_matches", lambda *_a: True)  # only the writer decides
    path.write_text(json.dumps({"head": el["head"], "seconds": 99}))
    assert mod._leg_seconds(ctx, el, "", "") == 0.0  # the requester's record
    path.write_text(json.dumps({"head": el["head"], "seconds": 99, "queued_as": "01OTHER"}))
    assert mod._leg_seconds(ctx, el, "", "") == 0.0  # another element's queue leg
    path.write_text(json.dumps({"head": el["head"], "seconds": 99, "queued_as": el["id"]}))
    assert mod._leg_seconds(ctx, el, "", "") == 99.0
    # a record rewritten between the match and this read never raises in the queue parent (r1 A5)
    for bad in ("99", True, None, -5, float("inf")):
        path.write_text(json.dumps({"head": el["head"], "seconds": bad, "queued_as": el["id"]}))
        assert mod._leg_seconds(ctx, el, "", "") == 0.0, bad
    path.write_text(json.dumps({"head": el["head"], "queued_as": el["id"]}))
    assert mod._leg_seconds(ctx, el, "", "") == 0.0


def test_queue_times_each_owner_script_apart(world, monkeypatch):
    """One changes `.fabrik/merge-tests`: once it lands, the next fork reads the NEW script, whose
    legs nobody has timed, so it is budgeted at the declared limit (review r1 A2)."""
    _leg_log(world, sleep=1.2)
    old = world.read(".fabrik/merge-tests")
    h1, b1 = _new_branch(world, "one", {".fabrik/merge-tests": old + "# owner tests, revised\n"})
    sends = [world.send(h1, branch=b1)]
    for i in range(2):
        h, b = _new_branch(world, f"s{i}", {f"s{i}.txt": f"{i}\n"})
        sends.append(world.send(h, branch=b))
    calls: list[tuple[str, float]] = []
    real = world.mod._leg_fits

    def spy(started, script, timed=0.0):
        calls.append((script, timed))
        return real(started, script, timed)

    monkeypatch.setattr(world.mod, "_leg_fits", spy)

    assert _queue(world) == 0

    assert any(s == old and t > 0 for s, t in calls), calls  # the old script's legs were timed
    revised = [t for s, t in calls if s != old]
    assert revised, calls  # a fork was checked against the revised script
    assert revised[0] == 0.0, calls  # its first budget carries nothing from the old script
    assert all(_record(world, m)["outcome"] == "merged" for m in sends)


def test_queue_reforks_a_request_restacked_after_a_refusal(world, monkeypatch):
    """One's queue leg is green but its landing is refused: two, tested stacked on one, is rebuilt onto
    the base with a NEW tree and earns a fresh queue leg — never a leg inside the lock (review r1 A1)."""
    log = _kind_log(world)
    h1, b1 = _new_branch(world, "one", {"a.txt": "a\n"})
    h2, b2 = _new_branch(world, "two", {"b.txt": "b\n"})
    m1, m2 = world.send(h1, branch=b1), world.send(h2, branch=b2)
    real_land = world.mod._land

    def refuse_one(msg_id):
        return world.mod.EXIT_REFUSED if msg_id == m1 else real_land(msg_id)

    monkeypatch.setattr(world.mod, "_land", refuse_one)

    assert _queue(world) == world.mod.EXIT_REFUSED

    rows = [(h, k) for h, k, _, _ in _kinds(log)]
    assert rows.count((h2, "queue")) == 2, rows  # once stacked on one, once on the base
    assert (h2, "locked") not in rows, rows
    assert _record(world, m2)["outcome"] == "merged" and _skipped(world, m2)


def test_queue_never_reforks_a_tried_leg(world):
    """Two's queue leg exits 124: after one lands the chain is rebuilt with new elements, and two is
    not forked again — its locked merge runs its leg (Opus critique: three legs for one request)."""
    log = _kind_log(world, fail_queue_on="slow.txt")
    h1, b1 = _new_branch(world, "one", {"a.txt": "a\n"})
    h2, b2 = _new_branch(world, "two", {"slow.txt": "x\n"})
    m1, m2 = world.send(h1, branch=b1), world.send(h2, branch=b2)

    assert _queue(world) == 0

    rows = [(h, k) for h, k, _, _ in _kinds(log)]
    assert rows.count((h2, "queue")) == 1, rows
    assert rows.count((h2, "locked")) == 1, rows
    assert _record(world, m1)["outcome"] == "merged" and _record(world, m2)["outcome"] == "merged"


def test_queue_under_the_after_merge_line_lands_in_order_without_legs(world):
    """D-1186's relief valve (W-3237ba45): a queue leg before landing would undo the speed-up, so the
    queue lands each request at once and each merge owes the after-merge run instead."""
    log = _leg_log(world)
    _owner_tests(world, "# merge-tests-after-merge-above: 0\n" + world.read(".fabrik/merge-tests"))
    (world.main / ".git" / "fabrik-merge").mkdir(parents=True, exist_ok=True)
    (world.main / ".git" / "fabrik-merge" / "01PRIORMERGE000000000000000.json").write_text(
        json.dumps({"id": "01PRIORMERGE000000000000000", "outcome": "merged"})
    )
    world.mp.setattr(world.mod, "_kick_after", lambda ctx: "")
    h1, b1 = _new_branch(world, "one", {"a.txt": "a\n"})
    h2, b2 = _new_branch(world, "two", {"b.txt": "b\n"})
    m1, m2 = world.send(h1, branch=b1), world.send(h2, branch=b2)
    assert _queue(world) == 0
    assert _legs(log) == []  # no leg before landing, in the queue or in the locked merge
    for m in (m1, m2):
        rec = _record(world, m)
        assert rec["outcome"] == "merged" and rec["after_merge_owed"], rec
