"""Run-bound scratch: the ONE classifier and the marker (scratch lifecycle plan, Phase A).

`classify_run_folder` is the only function that answers ACTIVE or CONSUMED for a `run-*` folder
(plan P2). These tests pin the operator's bar — "do not cause active scrathcpads to be removed but be
sure the ones consumed will be done so" — as a partition: every marker state is exactly one of the
two, and no INV-1 condition ever reads CONSUMED.
"""

from __future__ import annotations

import importlib.util
import io
import itertools
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "scratch_sweep.py"


def _load():
    spec = importlib.util.spec_from_file_location("scratch_sweep_runfolders_ut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(mod)
    return mod


sw = _load()

NOW = 1_800_000_000.0
MIN = 60
HOUR = 3600
DAY = 86400

# A CONSUMED baseline: a `done` run closed 40 h ago, nothing holding it.
BASE = sw.RunFacts(
    state="done",
    closed_at=NOW - 40 * HOUR,
    heartbeat_age_s=40 * HOUR,
    session_dead=False,
    held=False,
    gaps=False,
    probe_ok=True,
    worktree=False,
    keep=False,
    sid_matches=True,
    seat_write_after_close=False,
)

# Each spec § Invariants INV-1 condition ALONE (on top of a baseline that would otherwise be CONSUMED).
ACTIVE_CASES = {
    "running, live session": replace(BASE, state="running", closed_at=None, session_dead=False),
    "running, dead signal but fresh heartbeat": replace(
        BASE, state="running", closed_at=None, session_dead=True, heartbeat_age_s=DAY
    ),
    "resumable": replace(BASE, state="resumable"),
    "done 10 min ago, no seat write": replace(BASE, closed_at=NOW - 10 * MIN),
    "done 2 h ago, a seat wrote after the close": replace(
        BASE, closed_at=NOW - 2 * HOUR, seat_write_after_close=True
    ),
    "done 2 h ago, the seat check unreadable": replace(
        BASE, closed_at=NOW - 2 * HOUR, seat_write_after_close=None
    ),
    "a holder (fd or cwd) inside": replace(BASE, held=True),
    "a non-empty proc gaps list": replace(BASE, gaps=True),
    "the holder probe did not complete": replace(BASE, probe_ok=False),
    "a registered worktree inside": replace(BASE, worktree=True),
    "a top-level .keep": replace(BASE, keep=True),
    "no marker": replace(BASE, state=None),
    "an unknown state string": replace(BASE, state="paused"),
    "done with closed_at missing": replace(BASE, closed_at=None),
    "D3: marker sid differs from its directory": replace(BASE, sid_matches=False),
}

CONSUMED_CASES = {
    "done 40 min ago, no seat write": replace(BASE, closed_at=NOW - 40 * MIN),
    "done 37 h ago, a seat wrote after the close": replace(
        BASE, closed_at=NOW - 37 * HOUR, seat_write_after_close=True
    ),
    "running, dead session, heartbeat 8 days old": replace(
        BASE, state="running", closed_at=None, session_dead=True, heartbeat_age_s=8 * DAY
    ),
}


@pytest.mark.parametrize("name", sorted(ACTIVE_CASES))
def test_each_active_condition_alone_reads_active(name: str) -> None:
    verdict, reason = sw.classify_run_folder(ACTIVE_CASES[name], NOW)
    assert verdict == "active", (name, reason)
    assert reason, name


@pytest.mark.parametrize("name", sorted(CONSUMED_CASES))
def test_consumed_cases_read_consumed(name: str) -> None:
    verdict, reason = sw.classify_run_folder(CONSUMED_CASES[name], NOW)
    assert verdict == "consumed", (name, reason)


def _inv1_holds(f) -> bool:
    """Spec INV-1, restated independently of the implementation (the oracle)."""
    if f.state not in ("running", "done", "resumable"):
        return True
    if f.state == "resumable":
        return True
    if f.state == "running" and not (f.session_dead and f.heartbeat_age_s > 7 * DAY):
        return True
    if f.state == "done":
        if f.closed_at is None:
            return True
        grace = 30 * MIN if f.seat_write_after_close is False else 36 * HOUR
        if NOW - f.closed_at < grace:
            return True
    return f.held or f.gaps or not f.probe_ok or f.worktree or f.keep or not f.sid_matches


def test_classifier_partitions_the_state_space() -> None:
    """Every combination reads exactly one verdict, `consumed` never coexists with an INV-1
    condition, and every non-INV-1 state with a `done` or dead-`running` marker is `consumed`."""
    states = ["running", "done", "resumable", None, "weird"]
    closed = [None, NOW - 10 * MIN, NOW - 2 * HOUR, NOW - 40 * HOUR]
    seat = [False, True, None]
    hb = [DAY, 8 * DAY]
    flags = list(itertools.product([False, True], repeat=7))
    seen = 0
    for st, ca, sw_after, hb_age in itertools.product(states, closed, seat, hb):
        for dead, held, gaps, probe, wt, keep, sidm in flags:
            f = sw.RunFacts(
                state=st,
                closed_at=ca,
                heartbeat_age_s=hb_age,
                session_dead=dead,
                held=held,
                gaps=gaps,
                probe_ok=probe,
                worktree=wt,
                keep=keep,
                sid_matches=sidm,
                seat_write_after_close=sw_after,
            )
            verdict, _ = sw.classify_run_folder(f, NOW)
            assert verdict in ("active", "consumed"), f
            assert (verdict == "active") == _inv1_holds(f), f
            seen += 1
    assert seen == 5 * 4 * 3 * 2 * 128


@pytest.mark.parametrize(
    ("facts", "want"),
    [
        # spec INV-1: ACTIVE while the close is LESS than the grace old → exactly at it, consumed
        (replace(BASE, closed_at=NOW - 30 * MIN), "consumed"),
        (replace(BASE, closed_at=NOW - 30 * MIN + 1), "active"),
        (replace(BASE, closed_at=NOW - 36 * HOUR, seat_write_after_close=True), "consumed"),
        (replace(BASE, closed_at=NOW - 36 * HOUR + 1, seat_write_after_close=True), "active"),
        # DEAD only on a heartbeat OLDER than 7 days → exactly 7 days is still active
        (
            replace(
                BASE, state="running", closed_at=None, session_dead=True, heartbeat_age_s=7 * DAY
            ),
            "active",
        ),
        (
            replace(
                BASE,
                state="running",
                closed_at=None,
                session_dead=True,
                heartbeat_age_s=7 * DAY + 1,
            ),
            "consumed",
        ),
    ],
)
def test_threshold_boundaries(facts, want: str) -> None:
    """The comparison operators themselves, pinned at each threshold (a `<` turned `<=` reads red)."""
    assert sw.classify_run_folder(facts, NOW)[0] == want


def test_the_threshold_seams_move_the_thresholds(monkeypatch) -> None:
    """P1: SCRATCH_RUN_GRACE_S and SCRATCH_RUN_HEARTBEAT_S really move the 36 h ceiling and the 7 d
    heartbeat (they are test seams; conftest unsets them for every other test)."""
    seat = replace(BASE, closed_at=NOW - 2 * HOUR, seat_write_after_close=True)
    dead = replace(
        BASE, state="running", closed_at=None, session_dead=True, heartbeat_age_s=2 * DAY
    )
    assert sw.classify_run_folder(seat, NOW)[0] == "active"
    assert sw.classify_run_folder(dead, NOW)[0] == "active"
    monkeypatch.setenv("SCRATCH_RUN_GRACE_S", str(HOUR))
    monkeypatch.setenv("SCRATCH_RUN_HEARTBEAT_S", str(DAY))
    assert sw.classify_run_folder(seat, NOW)[0] == "consumed"
    assert sw.classify_run_folder(dead, NOW)[0] == "consumed"


def test_read_owner_tolerates_missing_and_corrupt_markers(tmp_path: Path) -> None:
    folder = tmp_path / "run-x"
    folder.mkdir()
    assert sw.read_owner(folder) is None
    (folder / sw.OWNER_NAME).write_text("{not json", encoding="utf-8")
    assert sw.read_owner(folder) is None
    (folder / sw.OWNER_NAME).write_text("[1, 2]", encoding="utf-8")
    assert sw.read_owner(folder) is None
    (folder / sw.OWNER_NAME).write_text(json.dumps({"state": "done"}), encoding="utf-8")
    assert sw.read_owner(folder) == {"state": "done"}


# ── Phase B: removal by marker (D3 `--run-folders`, D4 in `--dead`) ──────────────────────────────
SID_A = "aaaaaaaa-0000-4000-8000-00000000000a"
SID_B = "bbbbbbbb-0000-4000-8000-00000000000b"
SLUG = "-opt-fixture"


def _age(path: Path, seconds_old: float) -> None:
    os.utime(path, (NOW - seconds_old, NOW - seconds_old))


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A private harness root plus every seam the sweep reads, pointed at tmp — never live state."""
    root = tmp_path / "claude-1000"
    root.mkdir()
    (tmp_path / "tx").mkdir()
    (tmp_path / "sessions").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SCRATCH_SWEEP_ROOT", str(root))
    monkeypatch.setenv("SCRATCH_SWEEP_NOW", str(NOW))
    monkeypatch.setenv("SCRATCH_SWEEP_TRANSCRIPT_DIRS", str(tmp_path / "tx"))
    monkeypatch.setenv("SCRATCH_SWEEP_SESSIONS_DIRS", str(tmp_path / "sessions"))
    monkeypatch.setenv("SCRATCH_SWEEP_JANITOR_REPO", "")
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(tmp_path / "no-locks"))
    # a quiet one-pid /proc: the live one carries transient same-uid gaps (2 of 8 probes), and a gap
    # that starts after a folder was made keeps it — a test that wants a real holder opts back in
    # with `_live_proc`
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(_one_pid_proc(tmp_path)))
    monkeypatch.delenv(_LIVE_OPT_IN, raising=False)  # an exported or leaked opt-in never carries in
    monkeypatch.setenv(_HARNESS_ON, "1")  # the harness got this far: the teardown check applies
    return root


_LIVE_OPT_IN = "SCRATCH_SWEEP_TEST_LIVE_PROC"  # set by _live_proc, cleared by the harness
_HARNESS_ON = "SCRATCH_SWEEP_TEST_HARNESS"  # set once the harness has pointed at its fake /proc


def _live_proc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Read the real /proc — only for a case whose holder or liveness is a real process."""
    monkeypatch.delenv("FABRIK_PROC_ROOT", raising=False)
    monkeypatch.setenv(_LIVE_OPT_IN, "1")


@pytest.fixture(autouse=True)
def _no_live_proc_unless_opted_in(monkeypatch: pytest.MonkeyPatch):
    """A box process the sweep cannot read, started after a folder was made, keeps that folder:
    a harness on the live /proc made the write-after-close grader fail on a busy box (2 in 40
    runs on master). So a harness test must END on a fake /proc unless it opted in with
    `_live_proc`: the check reads, at teardown, the /proc `_proc_root` resolves to (teardown runs
    before `monkeypatch` undoes, so the env is the test's). It catches an accidental revert — a
    `delenv`, `setenv` to "/proc" or "", a link to /proc — and skips a test whose harness never
    finished setup. Cobra (D-253): it is a snapshot of the end state, so the cheap ways past it are
    deliberate ones — a live /proc only inside `monkeypatch.context()`, a directory of links to
    /proc's entries, an explicit `proc_root=` argument, or setting the opt-in env by hand; none of
    those is a revert, and a test written that way is visible in review."""
    yield
    if os.environ.get(_HARNESS_ON) != "1" or os.environ.get(_LIVE_OPT_IN) == "1":
        return
    root = sw._proc_root().resolve()  # a link to the live /proc is the live /proc
    assert root != Path("/proc").resolve(), "a harness test read the live /proc without _live_proc"


def test_the_harness_reads_a_one_pid_fake_proc(harness: Path) -> None:
    """The default the teardown check enforces, and the opt-in set it allows."""
    root = sw._proc_root().resolve()
    assert root.is_relative_to(harness.parent.resolve())
    assert sorted(os.listdir(root)) == ["1"]  # the one-pid fake, not a copy of a real /proc
    assert {
        "running-live",
        "fd-inside",
        "cwd-inside",
    } == LIVE_PROC_CASES  # widen it on purpose only


def _session(root: Path, sid: str = SID_A) -> Path:
    d = root / SLUG / sid
    (d / "scratchpad").mkdir(parents=True, exist_ok=True)
    tx = root.parent / "tx" / SLUG  # the session's transcript: the seat-write check can read it
    tx.mkdir(parents=True, exist_ok=True)
    (tx / f"{sid}.jsonl").touch()
    return d


def _run_folder(
    sdir: Path,
    name: str,
    state: str | None = "done",
    *,
    closed_ago: float | None = 40 * HOUR,
    sid: str | None = None,
    repo: str = "",
    heartbeat_ago: float = 40 * HOUR,
    files: int = 1,
) -> Path:
    folder = (
        sdir / "scratchpad" / f"run-{name}-2026-10-15T05-40-42-0300-0a1b2c"
    )  # the mint's key: <started_at>-<6 hex>
    folder.mkdir(parents=True)
    for i in range(files):
        (folder / f"f{i}").write_text("x", encoding="utf-8")
    if state is not None:
        owner = {
            "sid": sid or sdir.name,
            "key": name,
            "command": "fabrik-probe",
            "repo": repo,
            "created": NOW - 50 * HOUR,
            "state": state,
            "closed_at": None if closed_ago is None else NOW - closed_ago,
        }
        (folder / ".owner").write_text(json.dumps(owner), encoding="utf-8")
        _age(folder / ".owner", heartbeat_ago)
    # the folder's own mtime is a write-after-close signal (W-9f3f097c): a fixture leaves it at its
    # close, or the real clock passing the seam's NOW would read every fixture as written into since
    _age(folder, max(closed_ago or 0.0, heartbeat_ago))
    return folder


def _main(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    rc = sw.main(list(argv))
    return rc, capsys.readouterr().out


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=30, check=False
    ).stdout


def _repo(tmp_path: Path) -> Path:
    main = tmp_path / "repo"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    _git(main, "config", "user.email", "t@t")
    _git(main, "config", "user.name", "t")
    (main / "a.txt").write_text("base", encoding="utf-8")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "base")
    return main


def _dead_record(tmp_path: Path, sid: str) -> None:
    (tmp_path / "sessions" / f"{sid[:4]}.json").write_text(
        json.dumps({"pid": 999_999, "sessionId": sid, "procStart": "1"}), encoding="utf-8"
    )


def _live_record(tmp_path: Path, sid: str) -> None:
    """A sessions record the sweep reads as LIVE: this test process's own pid and its real start."""
    start = sw._proc_start_ticks(Path("/proc"), os.getpid())
    assert start is not None, "this box exposes no /proc start for the test process"
    (tmp_path / "sessions" / f"{sid[:4]}.json").write_text(
        json.dumps({"pid": os.getpid(), "sessionId": sid, "procStart": str(start)}),
        encoding="utf-8",
    )


def _age_tree(path: Path, seconds: float) -> None:
    for p in sorted(path.rglob("*"), reverse=True):
        if p.name != ".owner":
            _age(p, seconds)
    _age(path, seconds)


def _guard_run_walks(monkeypatch: pytest.MonkeyPatch) -> None:
    """`newest_mtime` raises on any path inside a run folder — "removed with no walk" — and so does
    any walk that DESCENDS into one from above: the dead-session idleness walk is handed the
    session directory, so a guard on the path it is handed alone could never see it (W-c0a1d324 F9)."""
    real = sw.newest_mtime
    real_walk = sw.os.walk

    def _no_walk(entry: Path, budget: object, **kw: object) -> tuple[float, bool]:
        if "/run-" in str(entry):
            raise AssertionError(f"a run folder was walked: {entry}")
        return real(entry, budget, **kw)

    def _no_descent(top, *a, **kw):
        for dirpath, dirnames, filenames in real_walk(top, *a, **kw):
            if "/run-" in str(dirpath) and "/run-" not in str(top):
                raise AssertionError(f"a walk descended into a run folder: {dirpath}")
            yield dirpath, dirnames, filenames

    monkeypatch.setattr(sw, "newest_mtime", _no_walk)
    monkeypatch.setattr(sw.os, "walk", _no_descent)


def test_consumed_folder_removed_without_a_walk(
    harness: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """B1: a 100 000-file folder of a run closed past its grace goes by marker alone."""
    folder = _run_folder(_session(harness), "big", files=100_000)

    def _no_walk(*_a: object, **_k: object) -> None:
        raise AssertionError("a run folder was walked")

    monkeypatch.setattr(sw, "newest_mtime", _no_walk)
    monkeypatch.setattr(sw, "_du_kb", _no_walk)
    monkeypatch.setattr(sw, "_entry_newest", _no_walk)
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert not folder.exists(), out
    # the rename target is `.trash-<key>` — the full key, never `.trash-big` — so the check is every
    # `.trash-*` entry: the old literal held whether or not the removal ran (W-c0a1d324 F1)
    assert not list(folder.parent.glob(".trash-*")), out
    assert "REMOVED" in out, out


def _fake_gap_proc(tmp_path: Path) -> Path:
    proc_root = tmp_path / "proc"
    pid = proc_root / "4793"
    (pid / "fd").mkdir(parents=True)
    (pid / "comm").write_text("x\n", encoding="utf-8")
    uid = os.getuid()
    (pid / "status").write_text(f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\n", encoding="utf-8")
    os.chmod(pid / "fd", 0o000)
    return proc_root


# the B2 cases whose holder or liveness is a real process: the only ones on the live /proc
LIVE_PROC_CASES = frozenset({"running-live", "fd-inside", "cwd-inside"})

ACTIVE_FOLDERS = [
    "running-live",
    "running-fresh-heartbeat",
    "resumable",
    "done-10-min-no-seat",
    "done-2-h-seat-wrote",
    "fd-inside",
    "cwd-inside",
    "proc-gap",
    "probe-dead",
    "dirty-worktree",
    "keep",
    "unresolvable-repo-git-depth-3",
    "no-marker",
    "corrupt-marker",
    "list-marker",
    "running-no-signal-stale-heartbeat",
    "worktree-list-fails",
]


def _build_active(case: str, sdir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """`(folder, children to kill, also try --dead)` for one B2 case."""
    children: list[subprocess.Popen[bytes]] = []
    if case == "running-live":
        # the session must be PROVABLY live, and `--dead` is the mode whose dead rule reads it:
        # `--run-folders` passes no liveness test, so this row once passed on another condition
        # without the session's liveness ever being consulted (W-c0a1d324 F3)
        _live_proc(monkeypatch)  # the live record names this process: liveness reads the real /proc
        _live_record(tmp_path, SID_A)
        return (
            _run_folder(sdir, case, "running", closed_ago=None, heartbeat_ago=30 * DAY),
            [],
            True,
        )
    if case == "running-fresh-heartbeat":
        _dead_record(tmp_path, SID_A)
        return _run_folder(sdir, case, "running", closed_ago=None, heartbeat_ago=DAY), [], True
    if case == "running-no-signal-stale-heartbeat":
        tx = sdir.parent.parent.parent / "tx" / SLUG / f"{SID_A}.jsonl"
        _age(tx, 0)  # a transcript written just now: no death signal
        return _run_folder(sdir, case, "running", closed_ago=None, heartbeat_ago=30 * DAY), [], True
    if case == "resumable":
        return _run_folder(sdir, case, "resumable"), [], False
    if case == "done-10-min-no-seat":
        return _run_folder(sdir, case, closed_ago=10 * 60), [], False
    if case == "done-2-h-seat-wrote":
        folder = _run_folder(sdir, case, closed_ago=2 * HOUR)
        seat = tmp_path / "tx" / SLUG / SID_A / "subagents" / "agent-x.jsonl"
        seat.parent.mkdir(parents=True)
        seat.write_text("{}", encoding="utf-8")
        _age(seat, HOUR)
        return folder, [], False
    folder = _run_folder(sdir, case)
    if case in LIVE_PROC_CASES - {"running-live"}:
        _live_proc(monkeypatch)  # the holder is a real child process
    if case == "fd-inside":
        code = f"import time; f = open({str(folder / 'f0')!r}); print('ok', flush=True); time.sleep(60)"
        child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE)
        assert child.stdout is not None and child.stdout.readline().strip() == b"ok"
        children.append(child)
    elif case == "cwd-inside":
        code = "print('ok', flush=True); import time; time.sleep(60)"
        child = subprocess.Popen([sys.executable, "-c", code], cwd=folder, stdout=subprocess.PIPE)
        assert child.stdout is not None and child.stdout.readline().strip() == b"ok"
        children.append(child)
    elif case == "proc-gap":
        monkeypatch.setenv("FABRIK_PROC_ROOT", str(_fake_gap_proc(tmp_path)))
    elif case == "probe-dead":
        (tmp_path / "empty-proc").mkdir()
        monkeypatch.setenv("FABRIK_PROC_ROOT", str(tmp_path / "empty-proc"))
    elif case == "dirty-worktree":
        main = _repo(tmp_path)
        _rewrite_repo(folder, str(main / ".git"))
        tree = folder / "seat-1" / "tree"
        _git(main, "worktree", "add", "-q", str(tree), "-b", "feat-dirty")
        (tree / "wip.txt").write_text("in flight", encoding="utf-8")
    elif case == "keep":
        (folder / ".keep").write_text("", encoding="utf-8")
    elif case == "unresolvable-repo-git-depth-3":
        _rewrite_repo(folder, "/nonexistent/repo/.git")
        (folder / "seat-1" / "tree" / "sub").mkdir(parents=True)
        (folder / "seat-1" / "tree" / "sub" / ".git").write_text("gitdir: /gone", encoding="utf-8")
    elif case == "no-marker":
        (folder / ".owner").unlink()
    elif case == "corrupt-marker":
        (folder / ".owner").write_text("{not json", encoding="utf-8")
    elif case == "list-marker":
        (folder / ".owner").write_text("[1, 2]", encoding="utf-8")
    elif case == "worktree-list-fails":
        not_git = tmp_path / "not-a-git-dir"
        not_git.mkdir()
        _rewrite_repo(folder, str(not_git))
    else:  # pragma: no cover — every case is named above
        raise AssertionError(case)
    return folder, children, False


def _rewrite_repo(folder: Path, repo: str) -> None:
    owner = json.loads((folder / ".owner").read_text(encoding="utf-8"))
    owner["repo"] = repo
    (folder / ".owner").write_text(json.dumps(owner), encoding="utf-8")
    _age(folder / ".owner", 40 * HOUR)


@pytest.mark.parametrize("case", ACTIVE_FOLDERS)
def test_active_condition_keeps(
    case: str,
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """B2: one ACTIVE condition alone keeps the folder through `--run-folders --apply` and, for
    the dead-session cases, through `--dead --apply` too (spec INV-1)."""
    sdir = _session(harness)
    folder, children, dead_mode = _build_active(case, sdir, tmp_path, monkeypatch)
    on_live = sw._proc_root().resolve() == Path("/proc").resolve()
    assert on_live == (case in LIVE_PROC_CASES), case  # live /proc gaps keep folders by themselves
    try:
        rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
        assert rc == 0, out
        assert folder.exists(), out
        if dead_mode:
            rc, out = _main(capsys, "--dead", "--apply")
            assert rc == 0, out
            assert folder.exists(), out
    finally:
        for c in children:
            c.kill()
            c.wait()
        for fd in tmp_path.glob("proc/*/fd"):
            os.chmod(fd, 0o700)  # or pytest cannot clean its tmp


def test_the_dead_rule_consumes_a_stale_running_folder_the_own_session_keeps(
    harness: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """B2's mirror: the SAME `running` folder that `--run-folders` keeps is consumed by `--dead`
    once its session has a death signal and its heartbeat is past 7 days — the keep above is the
    condition, not a remover that never removes."""
    sdir = _session(harness)
    folder = _run_folder(sdir, "stuck", "running", closed_ago=None, heartbeat_ago=8 * DAY)
    _age_tree(sdir, HOUR)  # touched an hour ago: the session itself is never removed whole
    _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert folder.exists()
    _dead_record(tmp_path, SID_A)
    rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0, out
    assert not folder.exists(), out
    assert sdir.exists(), out  # the run pass alone removed it


@pytest.mark.parametrize("death", ["record", "transcript"])
@pytest.mark.parametrize("holder", ["fd-file", "fd-dir", "cwd"])
@pytest.mark.parametrize("root_via", ["real", "symlink"])
def test_a_held_session_dir_is_not_dead_for_its_run_folders(
    root_via: str,
    holder: str,
    death: str,
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """W-d8592740: `--dead` must not call a session dead for its run folders while a live process
    holds something in its session directory outside those folders. SID_A has that holder and keeps
    its stale `running` folder, for the reason the live signal gives; SID_B has the same folder and
    death signal with no holder and loses it, so a rule that keeps every folder whenever ANY holder
    exists goes red too. Each axis closes an escape the review measured: a scratch root reached
    through a symlink (a guard comparing only the resolved path misses there, because the probe
    keys a holder by the path as passed), three holder shapes (a file, the directory itself, a
    working directory) and both death signals (a gone-pid sessions record, a stale transcript)."""
    real_root = harness
    if root_via == "symlink":
        link = tmp_path / "rootlink"
        os.symlink(str(real_root), link)
        monkeypatch.setenv("SCRATCH_SWEEP_ROOT", str(link))
    held_dir, bare_dir = _session(real_root, SID_A), _session(real_root, SID_B)
    held = _run_folder(held_dir, "stuck", "running", closed_ago=None, heartbeat_ago=8 * DAY)
    bare = _run_folder(bare_dir, "stuck", "running", closed_ago=None, heartbeat_ago=8 * DAY)
    notes = held_dir / "scratchpad" / "notes.txt"
    notes.write_text("open in a live pane", encoding="utf-8")
    for sdir in (held_dir, bare_dir):
        _age_tree(sdir, HOUR)
    proc_root = _one_pid_proc(tmp_path)
    if holder == "fd-file":
        os.symlink(str(notes.resolve()), proc_root / "1" / "fd" / "3")
    elif holder == "fd-dir":
        os.symlink(str(held_dir.resolve()), proc_root / "1" / "fd" / "3")
    else:
        os.symlink(str((held_dir / "scratchpad").resolve()), proc_root / "1" / "cwd")
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(proc_root))
    for sid in (SID_A, SID_B):
        transcript = tmp_path / "tx" / SLUG / f"{sid}.jsonl"
        if death == "record":
            _dead_record(tmp_path, sid)
            _age(transcript, 0)  # fresh on the test clock: the record is the only death signal
        else:
            _age(transcript, 8 * DAY)
    rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0, out
    assert held.exists(), out
    kept = [ln for ln in out.splitlines() if SID_A in ln and held.name in ln]
    assert any("running in a session with a live signal" in ln for ln in kept), out
    assert not bare.exists(), out


def test_a_closed_folder_written_into_after_its_close_keeps_the_long_grace(
    harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W-9f3f097c (kaizen 01M4ZVBX96, measured): an agent kept writing into the folder of a run it
    had CLOSED (a `start | head -1` hid the new run's RUN-SCRATCH line); 41 min after the close, with
    no seat transcript written since, the fast 30-min grace consumed it with the files just made. An
    entry created after the close (the folder's own mtime past it) is a folder still in use: the
    long grace. The control — the same close with nothing made since — still goes."""
    sdir = _session(harness)
    used = _run_folder(sdir, "used", closed_ago=41 * 60, heartbeat_ago=41 * 60)
    (used / "ep-audit.md").write_text("brief", encoding="utf-8")
    _age(used / "ep-audit.md", 60)
    _age(used, 60)  # the new entry moved the folder's mtime to a minute ago
    idle = _run_folder(sdir, "idle", closed_ago=41 * 60, heartbeat_ago=41 * 60)
    _age(idle / "f0", 41 * 60 + 5)
    _age(idle, 41 * 60)  # nothing made since the close
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert used.exists() and (used / "ep-audit.md").exists(), out
    assert not idle.exists(), out


def test_the_write_after_close_margin_and_the_removal_recheck(
    harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The signal's edges: an entry just past the margin keeps and the close's own marker write alone
    does not; the long grace runs from the LAST top-level change, not the close; an entry made between
    classification and removal keeps the folder."""
    margin = sw.WRITE_AFTER_CLOSE_MARGIN_S
    assert 0 < margin <= 5  # never the 300-s clock margin: a write 2 min after a close must count
    sdir = _session(harness)
    past = _run_folder(sdir, "past", closed_ago=41 * 60, heartbeat_ago=41 * 60)
    _age(past, 41 * 60 - margin - 1)  # one second past the margin
    within = _run_folder(sdir, "within", closed_ago=41 * 60, heartbeat_ago=41 * 60)
    _age(within, 41 * 60 - margin + 1)  # the close's own write lands inside the margin
    recent = _run_folder(sdir, "recent", closed_ago=40 * HOUR, heartbeat_ago=40 * HOUR)
    _age(recent, 35 * HOUR)  # written 5 h after a close 40 h ago: 35 h < 36 h from that write
    stale = _run_folder(sdir, "stale", closed_ago=40 * HOUR, heartbeat_ago=40 * HOUR)
    _age(stale, 37 * HOUR)  # its last write is itself past the long grace
    edge = _run_folder(sdir, "edge", closed_ago=41 * 60, heartbeat_ago=41 * 60)
    _age(edge, 41 * 60 - margin)  # exactly at the margin: not past it
    later = _run_folder(sdir, "later", closed_ago=41 * 60, heartbeat_ago=41 * 60)
    _age(later, 39 * 60)  # an entry made two minutes after the close counts
    planned = {Path(r.path).name.split("-2026")[0]: r.cls for r in sw.plan_run_folders([sdir], NOW)}
    assert planned["run-recent"] == "kept"  # the judge itself counts the grace from the last write
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert past.exists() and recent.exists() and later.exists(), out
    assert not within.exists() and not stale.exists() and not edge.exists(), out
    late = _run_folder(sdir, "late", closed_ago=41 * 60, heartbeat_ago=41 * 60)
    rows = sw.plan_run_folders([sdir], NOW)
    assert [r.cls for r in rows if r.path == str(late)] == ["consumed"]
    _age(late, 30)  # an entry made after the sweep judged it, before the removal
    sw.apply_run_rows(rows, out=io.StringIO())
    assert late.exists()


def test_the_write_after_close_signal_stays_bounded(
    harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Review round 1: a folder mtime far in the future is doubt counted from the CLOSE (never a keep
    until that date); a `.trash-*` leftover the judge consumed by name is never re-kept at removal; an
    unreadable stat is doubt; only a `done` marker takes the re-check; the reason says "last written"
    when the grace ran from a write."""
    sdir = _session(harness)
    future = _run_folder(sdir, "future", closed_ago=40 * HOUR, heartbeat_ago=40 * HOUR)
    os.utime(future, (NOW + 10 * 365 * 86400, NOW + 10 * 365 * 86400))
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0 and not future.exists(), out  # 40 h past its close: the bounded doubt has ended
    trash = sdir / "scratchpad" / ".trash-run-gone-2026-10-15T05-40-42-0300-0a1b2c"
    trash.mkdir()
    (trash / ".owner").write_text(
        json.dumps({"state": "done", "closed_at": NOW - 40 * HOUR}), encoding="utf-8"
    )
    _age(trash, 10)  # an interrupted removal just unlinked entries
    rows = sw.plan_run_folders([sdir], NOW)
    assert [r.cls for r in rows if r.path == str(trash)] == ["consumed"]
    sw.apply_run_rows(rows, out=io.StringIO())
    assert not trash.exists()
    assert sw._written_after_close(sdir / "no-such-folder", NOW - 100, NOW) == NOW - 100
    used = _run_folder(sdir, "used", closed_ago=41 * 60, heartbeat_ago=41 * 60)
    _age(used, 60)
    assert not sw._in_use_since_close(used, {"state": "running", "closed_at": NOW - 41 * 60}, NOW)
    assert sw._in_use_since_close(used, {"state": "done", "closed_at": NOW - 41 * 60}, NOW)
    row = sw.judge_run_folder(used, SID_A, NOW, session_dead=False, held={}, gaps=[], probe_ok=True)
    assert row.cls == "kept" and row.reason.startswith("last written 60s ago"), row.reason


def test_only_own_session(harness: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """B3: `--run-folders --session A` touches A's directory and nothing under B's."""
    mine = _run_folder(_session(harness, SID_A), "mine")
    theirs = _run_folder(_session(harness, SID_B), "theirs")
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert not mine.exists(), out
    assert theirs.exists(), out


def test_sid_mismatch_kept(harness: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """B3 / P6: a marker naming another session is kept by the own-session remover (spec V3)."""
    folder = _run_folder(_session(harness, SID_A), "moved", sid=SID_B)
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert folder.exists(), out
    assert "differs from its directory" in out, out


def test_trash_left_by_a_crash(
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """B4 (first half): a `.trash-<key>` an interrupted removal left goes on the next sweep."""
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(_one_pid_proc(tmp_path)))
    trash = _session(harness) / "scratchpad" / ".trash-crashed-2026-10-15T05-40-42-0300-0a1b2c"
    trash.mkdir()
    (trash / "f").write_text("x", encoding="utf-8")
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert not trash.exists(), out


def test_dead_session_keeps_active_run_folder(
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """B5: consumed run folders of every session go first; a dead session holding an ACTIVE one
    keeps its directory and that folder, and loses every other entry; a dry run removes nothing."""
    dead = _session(harness, SID_A)
    # resumable: the ACTIVE condition a session can still hold once it is idle past 7 days — a
    # just-closed marker would make the session read recently touched, and it is left alone
    active = _run_folder(dead, "active", "resumable", heartbeat_ago=30 * DAY)
    junk = dead / "scratchpad" / "junk"
    junk.mkdir()
    (junk / "f").write_text("x", encoding="utf-8")
    (dead / "tasks").mkdir()
    (dead / sw.RUN_LOCK_NAME).write_text("", encoding="utf-8")
    other = _session(harness, SID_B)
    consumed = _run_folder(other, "consumed", closed_ago=40 * HOUR)
    for d in (dead, other):
        _dead_record(tmp_path, d.name)
        _age_tree(d, 30 * DAY)

    rc, out = _main(capsys, "--dead")
    assert rc == 0, out
    assert consumed.exists() and junk.exists(), "a dry --dead removed something"
    listed = {ln.split(" · ")[0]: ln for ln in out.splitlines() if " · " in ln}
    assert str(dead / sw.RUN_LOCK_NAME) in listed, out
    assert " · dead · " not in listed.get(str(active), ""), out

    _guard_run_walks(monkeypatch)
    rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0, out
    assert not consumed.exists(), out
    assert active.exists() and dead.exists(), out
    assert not junk.exists() and not (dead / "tasks").exists(), out
    assert not (dead / sw.RUN_LOCK_NAME).exists(), out
    assert "holds an active run folder" in out, out


def test_dead_session_without_active_removed_whole(
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """B5 / spec V1: a dead session's `running` folder with a 7-day-stale heartbeat is consumed
    walk-free, and the session with no ACTIVE folder left is removed whole, as today."""
    dead = _session(harness, SID_A)
    running = _run_folder(dead, "stuck", "running", closed_ago=None, heartbeat_ago=8 * DAY)
    _dead_record(tmp_path, SID_A)
    _age_tree(dead, 30 * DAY)
    _guard_run_walks(monkeypatch)
    rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0, out
    assert not running.exists() and not dead.exists(), out


def test_the_run_pass_waits_for_the_unreadable_root_refusal(
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """P9: an unreadable sessions root refuses the whole night — the run pass included."""
    consumed = _run_folder(_session(harness), "consumed")
    locked = tmp_path / "locked-sessions"
    locked.mkdir()
    os.chmod(locked, 0)
    monkeypatch.setenv("SCRATCH_SWEEP_SESSIONS_DIRS", f"{tmp_path / 'sessions'}:{locked}")
    try:
        rc, out = _main(capsys, "--dead", "--apply")
    finally:
        os.chmod(locked, 0o700)
    assert rc == sw.RC_REFUSED, out
    assert consumed.exists(), out


def test_strict_proc_holds_a_consumed_run_folder_in_every_mode(
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """F5 (W-c0a1d324): `--strict-proc` turns every removable row into `probe-error` when a
    same-uid `/proc` gap exists — a consumed run folder included. It never reached them: session
    mode's downgrade skipped the `consumed` class, and `--dead` downgraded before the run rows were
    planned. The same folders without the flag are removed (the control)."""
    sdir = _session(harness)
    past = _run_folder(sdir, "past", closed_ago=40 * HOUR)
    _age_tree(past, 7 * HOUR)
    _age(past, 40 * HOUR)
    monkeypatch.setenv("CLAUDE_SESSION_ID", SID_A)
    # a gap process that started LONG before every marker: the run-folder rule does not keep for
    # it (it cannot own the folder), so only `--strict-proc` can hold the folder back
    monkeypatch.setenv(
        "FABRIK_PROC_ROOT", str(_gap_proc(tmp_path, started_ago=60 * DAY, zombie=False))
    )
    monkeypatch.setenv("SCRATCH_SWEEP_BTIME", str(NOW - 100 * DAY))
    try:
        rc, out = _main(capsys, "--session", SID_A, "--strict-proc", "--apply")
        assert rc == 0, out
        assert past.exists(), "--strict-proc removed a consumed run folder in session mode: " + out
        dead = _session(harness, SID_B)
        stuck = _run_folder(dead, "stuck", "running", closed_ago=None, heartbeat_ago=8 * DAY)
        _dead_record(tmp_path, SID_B)
        _age_tree(dead, 30 * DAY)
        rc, out = _main(capsys, "--dead", "--strict-proc", "--apply")
        assert rc == 0, out
        assert stuck.exists(), "--strict-proc removed a consumed run folder in --dead: " + out
        rc, out = _main(capsys, "--dead", "--apply")  # the control: without the flag it goes
        assert rc == 0, out
        assert not stuck.exists(), out
        rc, out = _main(capsys, "--session", SID_A, "--apply")  # the session-mode control
        assert rc == 0, out
        assert not past.exists(), out
    finally:
        os.chmod(tmp_path / "gproc" / "4242" / "fd", 0o700)


def test_session_mode_governs_run_folders_by_marker(
    harness: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """B8 / P8: session mode never judges a run folder by age; `--hook` leaves run folders out."""
    sdir = _session(harness)
    graced = _run_folder(sdir, "graced", closed_ago=10 * 60)
    resumable = _run_folder(sdir, "resumable", "resumable")
    past = _run_folder(sdir, "past", closed_ago=40 * HOUR)
    for f in (graced, resumable, past):
        _age_tree(f, 7 * HOUR)
    _age(
        past, 40 * HOUR
    )  # the folder's own mtime stays at its close: nothing made in it since (W-9f3f097c)
    monkeypatch.setenv("CLAUDE_SESSION_ID", SID_A)
    rc, out = _main(capsys, "--session", SID_A, "--apply")
    assert rc == 0, out
    assert graced.exists() and resumable.exists(), out
    assert not past.exists(), out
    assert "run folder, marker-governed" in out, out

    stale = sdir / "scratchpad" / "plain-stale"
    stale.mkdir()
    _age_tree(stale, 7 * HOUR)
    payload = json.dumps({"session_id": SID_A, "cwd": "/opt/fabrik"})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    rc, out = _main(capsys, "--hook")
    assert rc == 0
    assert "1 stale entries" in out, out  # the two kept run folders are not counted


def test_a_backup_inside_an_active_run_folder_does_not_shield_a_dead_session(
    harness: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """B8 / P8: a dead session whose only backup shape sits inside an ACTIVE run folder is split
    per entry, never `dead-holds-backups`."""
    dead = _session(harness)
    active = _run_folder(dead, "active", "resumable", heartbeat_ago=30 * DAY)
    (active / "main.py.bak").write_text("the only copy", encoding="utf-8")
    junk = dead / "scratchpad" / "junk"
    junk.mkdir()
    _dead_record(tmp_path, SID_A)
    _age_tree(dead, 30 * DAY)
    rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0, out
    assert "dead-holds-backups" not in out, out
    assert active.exists() and not junk.exists(), out


def test_a_backup_inside_a_consumed_run_folder_is_disposable(
    harness: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """P10: inside a CONSUMED run folder a backup shape is disposable by contract — the dead
    session holding only that is removed whole the same night, never `dead-holds-backups`."""
    dead = _session(harness)
    consumed = _run_folder(dead, "spent", heartbeat_ago=30 * DAY)
    (consumed / "main.py.bak").write_text("a seat's revert baseline", encoding="utf-8")
    _dead_record(tmp_path, SID_A)
    _age_tree(dead, 30 * DAY)
    rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0, out
    assert "dead-holds-backups" not in out, out
    assert not dead.exists(), out


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_marker_time_is_doubt_never_consumed(
    value: float, harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F10 (W-6cdc86f3): a clobbered `.owner` whose time is NaN or ±Infinity (JSON `json.loads`
    accepts) reads as NO marker — INV-1 doubt, kept — never as a past close that makes it consumed."""
    sdir = _session(harness)
    folder = _run_folder(sdir, "clobbered")
    owner = json.loads((folder / ".owner").read_text(encoding="utf-8"))
    owner["closed_at"] = value
    owner["created"] = value
    (folder / ".owner").write_text(json.dumps(owner), encoding="utf-8")
    _age(folder / ".owner", 40 * HOUR)
    assert sw.read_owner(folder) is None
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert folder.exists(), out


@pytest.mark.parametrize(
    ("change", "kept"),
    [
        ({}, False),  # control: a sane marker past its grace is still consumed
        ({"closed_at": 0}, True),  # a close before the run was created
        ({"closed_at": -1e308}, True),
        ({"created": None}, True),  # no creation time to judge the close against
        ({"created": "yesterday"}, True),
        ({"created": True}, True),
        ({"created": NOW + 2 * DAY}, True),  # created in the future
        ({"closed_at": NOW - 50 * HOUR - 300}, False),  # exactly the clock margin before created
        ({"closed_at": NOW - 50 * HOUR - 301}, True),  # one second past it
    ],
    ids=[
        "control",
        "closed-zero",
        "closed-huge-negative",
        "created-missing",
        "created-text",
        "created-bool",
        "created-future",
        "margin-edge-vouched",
        "margin-edge-past",
    ],
)
def test_a_close_time_the_marker_cannot_vouch_for_is_doubt(
    change: dict,
    kept: bool,
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """D-900 (W-de2c34c1, F13): a `done` marker's close is believed only against a sane creation time.
    With `created` missing, non-numeric, a bool or in the future, or with `closed_at` before
    `created` minus the clock margin, the close is unknown — ACTIVE (INV-1), never consumed.
    A gap-free /proc on purpose: on the live box a same-uid daemon's gap already keeps an unknown
    `created` (gap_keeps), which would make these cases pass with the rule absent."""
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(_one_pid_proc(tmp_path)))
    sdir = _session(harness)
    folder = _run_folder(sdir, "suspect")
    owner = json.loads((folder / ".owner").read_text(encoding="utf-8"))
    owner.update(change)
    if owner.get("created") is None:
        del owner["created"]
    (folder / ".owner").write_text(json.dumps(owner), encoding="utf-8")
    _age(folder / ".owner", 40 * HOUR)
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert folder.exists() is kept, out


@pytest.mark.parametrize("raw", ["-1e999", "1e999", "-1e400", "9" * 400, "-" + "9" * 400])
def test_an_overflowing_marker_time_is_doubt_never_consumed(
    raw: str, harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F10, review round 1: a number literal that overflows (`-1e999`) parses to ±inf WITHOUT
    passing `parse_constant`, and -inf read as a past close made the folder consumed. Written as
    raw text, the way a clobbered file carries it; the folder stays."""
    sdir = _session(harness)
    folder = _run_folder(sdir, "overflow")
    owner = json.loads((folder / ".owner").read_text(encoding="utf-8"))
    owner["closed_at"] = "@@T@@"
    (folder / ".owner").write_text(json.dumps(owner).replace('"@@T@@"', raw), encoding="utf-8")
    _age(folder / ".owner", 40 * HOUR)
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert folder.exists(), out


def test_a_deeply_nested_marker_is_doubt_never_a_crash(
    harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Review round 1: a clobbered `.owner` nested past the recursion limit raised RecursionError out
    of `read_owner` and aborted the whole sweep; it now reads as no marker, and the run completes."""
    sdir = _session(harness)
    folder = _run_folder(sdir, "deep")
    (folder / ".owner").write_text("[" * 200_000 + "]" * 200_000, encoding="utf-8")
    assert sw.read_owner(folder) is None
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert folder.exists(), out


def test_a_backup_under_a_nested_scratchpad_keeps_its_dead_session(
    harness: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F11, review round 1: only the session's OWN pad holds marker-governed run folders. A keyed
    name under a nested `…/scratchpad/` (a project copied into scratch) is ordinary scratch, so its
    backup keeps the dead session — the prune fired at ANY directory named `scratchpad`."""
    dead = _session(harness)
    nested = dead / "scratchpad" / "proj" / "scratchpad" / "run-x-2026-10-15T05-40-42-0300-0a1b2c"
    nested.mkdir(parents=True)
    (nested / "main.py.bak").write_text("the only copy", encoding="utf-8")
    _dead_record(tmp_path, SID_A)
    _age_tree(dead, 30 * DAY)
    rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0, out
    assert "dead-holds-backups" in out, out
    assert (nested / "main.py.bak").exists(), out


@pytest.mark.parametrize("name", ["run-tests", ".trash-old"])
def test_a_backup_inside_an_unminted_run_named_folder_keeps_its_dead_session(
    name: str, harness: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F11 (W-9f3dad31): only the mint's KEYED name is marker-governed (`is_run_entry`, P8). An
    agent's own `run-tests/` or `.trash-old/` is ordinary scratch, so a backup inside it is the
    dead session's backup: `dead-holds-backups`, kept whole — never pruned from the walk by name."""
    dead = _session(harness)
    own = dead / "scratchpad" / name
    own.mkdir(parents=True)
    (own / "main.py.bak").write_text("the only copy", encoding="utf-8")
    _dead_record(tmp_path, SID_A)
    _age_tree(dead, 30 * DAY)
    rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0, out
    assert "dead-holds-backups" in out, out
    assert (own / "main.py.bak").exists(), out


def test_run_folders_respects_the_lock(harness: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """B9: a held per-session lock is one line, nothing removed, rc 0."""
    sdir = _session(harness)
    folder = _run_folder(sdir, "consumed")
    code = (
        "import fcntl, sys, time; f = open(sys.argv[1], 'w'); "
        "fcntl.flock(f, fcntl.LOCK_EX); print('ok', flush=True); time.sleep(60)"
    )
    holder = subprocess.Popen(
        [sys.executable, "-c", code, str(sdir / sw.RUN_LOCK_NAME)], stdout=subprocess.PIPE
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == b"ok"
        rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    finally:
        holder.kill()
        holder.wait()
    assert rc == 0, out
    assert "holds this session's lock" in out, out
    assert folder.exists(), out


def test_nightly_runs_while_a_session_lock_is_held(
    harness: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """B9 / P3: a D3 child holding only its per-session lock never makes `--dead --apply` skip."""
    sdir = _session(harness)
    folder = _run_folder(sdir, "consumed")
    _dead_record(tmp_path, SID_A)
    _age_tree(sdir, 30 * DAY)
    with sw._Lock(sdir / sw.RUN_LOCK_NAME) as got:
        assert got
        rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0, out
    assert "another sweep holds the lock" not in out, out
    # the night ran: its run pass removed the consumed folder. The held lock fd is invisible on the
    # fake /proc; the session reads `unclassified` because its run folder's `.owner` was written 40 h
    # ago, so the run pass decides and the session dir stays
    assert not folder.exists(), out
    assert sdir.exists(), out  # the run pass took the folder, never the whole session


def test_vanished_folder_is_skipped(harness: Path) -> None:
    """B9: a CONSUMED folder renamed away between classification and action is `gone — skipped`
    and the run carries on to the next one."""
    sdir = _session(harness)
    first = _run_folder(sdir, "first")
    second = _run_folder(sdir, "second")
    rows = sw.plan_run_folders([sdir], NOW)
    assert {r.cls for r in rows} == {"consumed"}, rows
    first.rename(sdir / "elsewhere")
    out = io.StringIO()
    sw.apply_run_rows(rows, out=out)
    assert "gone — skipped" in out.getvalue(), out.getvalue()
    assert not second.exists(), out.getvalue()


def test_a_folder_lost_to_a_racing_remover_is_skipped(
    harness: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P3: a D3 and the nightly D4 on one folder — the rename that loses the race (ENOENT) is
    `gone — skipped`, never FAILED, and the run carries on."""
    sdir = _session(harness)
    first = _run_folder(sdir, "first")
    second = _run_folder(sdir, "second")
    rows = sw.plan_run_folders([sdir], NOW)
    real_rename = os.rename

    def _racing(src: object, dst: object) -> None:
        if str(src) == str(first):
            raise FileNotFoundError(2, "No such file or directory", str(src))
        real_rename(src, dst)

    monkeypatch.setattr(sw.os, "rename", _racing)
    out = io.StringIO()
    sw.apply_run_rows(rows, out=out)
    assert f"gone — skipped {first}" in out.getvalue(), out.getvalue()
    assert "FAILED" not in out.getvalue(), out.getvalue()
    assert not second.exists(), out.getvalue()


def test_refusal_set_names_the_run_folder_rule() -> None:
    """B10 / P10: `--help` states the marker rule and the run-folder carve-out."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0
    flat = " ".join(proc.stdout.split())
    assert (
        "inside a CONSUMED run folder (scratchpad/run-<key>/) backup shapes are disposable" in flat
    )
    assert "judged only by its .owner marker and the holder probe" in flat


@pytest.mark.parametrize("created", [None, NOW + 400 * DAY])
def test_retire_tells_the_truth_about_an_unvouchable_folder(
    created: float | None, harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """D-900 review: `--retire` used to print "removed after its grace" for a marker whose missing or
    future `created` makes every sweep keep it. It invents no creation time (a `now` would strip
    `gap_keeps`' protection from the run's writers) — it says the folder is kept and how to remove it."""
    folder = _run_folder(_session(harness), "nocreated", "resumable")
    owner = json.loads((folder / ".owner").read_text(encoding="utf-8"))
    if created is None:
        owner.pop("created")
    else:
        owner["created"] = created
    (folder / ".owner").write_text(json.dumps(owner), encoding="utf-8")
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--retire", folder.name)
    assert rc == 0, out
    after = json.loads((folder / ".owner").read_text(encoding="utf-8"))
    assert after.get("created") == created and after["state"] == "done", after
    assert "every sweep keeps it" in out and "removed after its grace" not in out, out


def test_retire_marks_one_folder_done(harness: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """B11 / P12: `--retire` turns one resumable marker `done` (closed now) and changes nothing
    else; another session's folder, or a missing one, is refused."""
    folder = _run_folder(_session(harness), "wall", "resumable")
    before = json.loads((folder / ".owner").read_text(encoding="utf-8"))
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--retire", folder.name)
    assert rc == 0, out
    after = json.loads((folder / ".owner").read_text(encoding="utf-8"))
    assert after == {**before, "state": "done", "closed_at": NOW}
    theirs = _run_folder(_session(harness, SID_B), "theirs", "resumable")
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--retire", theirs.name)
    assert rc == sw.RC_REFUSED, out
    assert json.loads((theirs / ".owner").read_text(encoding="utf-8"))["state"] == "resumable"
    rc, out = _main(
        capsys,
        "--run-folders",
        "--session",
        SID_A,
        "--retire",
        "run-missing-2026-10-15T05-40-42-0300-0a1b2c",
    )
    assert rc == sw.RC_REFUSED, out


@pytest.mark.parametrize("shape", ["merged-branch", "detached-contained"])
def test_removable_worktree_is_removed_then_consumed(
    shape: str, harness: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """B12 / P14: a merged clean branch worktree, or a clean detached one whose HEAD a ref
    contains, is removed with `git worktree remove` and its folder consumed."""
    main = _repo(tmp_path)
    folder = _run_folder(_session(harness), shape, repo=str(main / ".git"))
    tree = folder / "seat-1" / "tree"
    if shape == "merged-branch":
        _git(main, "worktree", "add", "-q", str(tree), "-b", "feat-merged")
    else:
        _git(main, "worktree", "add", "-q", "--detach", str(tree), "HEAD")
    _age(folder / ".owner", 40 * HOUR)
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert not folder.exists(), out
    assert str(tree) not in _git(main, "worktree", "list", "--porcelain"), out


@pytest.mark.parametrize("shape", ["dirty", "locked", "unmerged", "detached-orphan"])
def test_dirty_worktree_keeps_the_folder(
    shape: str, harness: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """B12 / P14: a dirty, locked, unmerged or ref-orphaned detached worktree keeps the folder."""
    main = _repo(tmp_path)
    folder = _run_folder(_session(harness), shape, repo=str(main / ".git"))
    tree = folder / "seat-1" / "tree"
    ident = ("-c", "user.email=t@t", "-c", "user.name=t")
    if shape == "detached-orphan":
        _git(main, "worktree", "add", "-q", "--detach", str(tree), "HEAD")
        (tree / "n.txt").write_text("n", encoding="utf-8")
        _git(tree, "add", "-A")
        _git(tree, *ident, "commit", "-qm", "orphan")
    else:
        _git(main, "worktree", "add", "-q", str(tree), "-b", f"feat-{shape}")
        if shape == "dirty":
            (tree / "wip.txt").write_text("in flight", encoding="utf-8")
        elif shape == "locked":
            _git(main, "worktree", "lock", str(tree))
        else:
            (tree / "u.txt").write_text("u", encoding="utf-8")
            _git(tree, "add", "-A")
            _git(tree, *ident, "commit", "-qm", "unmerged")
    _age(folder / ".owner", 40 * HOUR)
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert folder.exists() and tree.exists(), out
    assert "holds a registered worktree" in out, out


def _gap_proc(tmp_path: Path, *, started_ago: float | None, zombie: bool = False) -> Path:
    """A `/proc` holding one same-uid pid whose `/fd` is unreadable, started `started_ago` seconds
    before NOW (None: its `stat` is missing). Boot is pinned through `SCRATCH_SWEEP_BTIME`."""
    proc_root = tmp_path / "gproc"
    pid = proc_root / "4242"
    (pid / "fd").mkdir(parents=True)
    (pid / "comm").write_text("gpg-agent\n", encoding="utf-8")
    uid = os.getuid()
    state = "Z (zombie)" if zombie else "S (sleeping)"
    (pid / "status").write_text(
        f"Name:\tgpg-agent\nState:\t{state}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n", encoding="utf-8"
    )
    if started_ago is not None:
        hz = os.sysconf("SC_CLK_TCK")
        ticks = int((100 * DAY - started_ago) * hz)  # boot is 100 days before NOW (see the seam)
        fields = ["S"] + ["0"] * 18 + [str(ticks)]
        (pid / "stat").write_text(f"4242 (gpg-agent) {' '.join(fields)}\n", encoding="utf-8")
    os.chmod(pid / "fd", 0o000)
    return proc_root


@pytest.mark.parametrize(
    ("started_ago", "created_ago", "zombie", "kept"),
    [
        (90 * DAY, 50 * HOUR, False, False),  # a daemon running before the run began
        (45 * HOUR, 50 * HOUR, False, True),  # born during the run (it closed 40 h ago)
        # W-d1a4a8f5: born 39 h AFTER the run closed — the document portal's fusermount3 shape. It
        # kept 152 folders (77 GB) on 2026-10-29 because the rule had no end; both the classifier
        # and the --apply re-check must let it go, or the re-check re-keeps what the judge consumed
        (HOUR, 50 * HOUR, False, False),
        (None, 50 * HOUR, False, True),  # its start cannot be read
        (90 * DAY, None, False, True),  # the marker carries no `created`
        (HOUR, 50 * HOUR, True, False),  # a zombie holds nothing
    ],
    ids=[
        "pre-run-daemon",
        "born-during-run",
        "born-after-run",
        "start-unknown",
        "created-missing",
        "zombie",
    ],
)
def test_a_proc_gap_keeps_only_a_process_the_run_could_own(
    started_ago: float | None,
    created_ago: float | None,
    zombie: bool,
    kept: bool,
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The gaps rule (panel 2026-10-15, split; interim rule C): this box carries three same-uid
    daemons whose `/fd` no one can read, so "any gap keeps" kept every folder for ever. A gap now
    keeps only when its process started after the run's marker was written, or when either time is
    unknown; a zombie is no gap at all."""
    folder = _run_folder(_session(harness), "g")
    owner = json.loads((folder / ".owner").read_text(encoding="utf-8"))
    if created_ago is None:
        owner.pop("created")
    else:
        owner["created"] = NOW - created_ago
    (folder / ".owner").write_text(json.dumps(owner), encoding="utf-8")
    _age(folder / ".owner", 40 * HOUR)
    monkeypatch.setenv(
        "FABRIK_PROC_ROOT", str(_gap_proc(tmp_path, started_ago=started_ago, zombie=zombie))
    )
    monkeypatch.setenv("SCRATCH_SWEEP_BTIME", str(NOW - 100 * DAY))
    try:
        rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    finally:
        os.chmod(tmp_path / "gproc" / "4242" / "fd", 0o700)
    assert rc == 0, out
    assert folder.exists() is kept, out


@pytest.mark.parametrize("created", [float("nan"), float("inf"), float("-inf"), True, None, "1000"])
def test_an_unusable_created_always_keeps_through_a_gap(created: object) -> None:
    """W-a39d4c86 (fleet 01M505J6KG): `gap_keeps` keeps on ANY unusable `created` (D-878's
    keep-on-doubt). NaN passed the type guard and every `s >= NaN - margin` read False, so a NaN
    kept nothing — the one unusable value that failed open."""
    assert sw.gap_keeps([NOW - 100_000], created, NOW) is True


def test_gap_keeps_is_defeated_by_a_later_created_not_an_earlier_one() -> None:
    """The Cobra direction the docstring names (fleet 01M505J6KG; review of 46b409cc9): an EARLIER
    `created` makes every gap read newer and KEEPS; any `created` LATER than the run's true start —
    the present, or forward inside the margin — drops a real gap. Pinned as the residual."""
    assert sw.gap_keeps([NOW - 100], 0, NOW) is True  # backdated: keeps
    assert sw.gap_keeps([NOW - 100_000], NOW + 200, NOW) is False  # forward-dated inside the margin
    assert sw.gap_keeps([NOW - 3600], NOW, NOW) is False  # re-stamped to now: the residual


def test_a_bool_created_keeps_even_against_an_old_start() -> None:
    """Review of 46b409cc9 (haiku T3): `True` reads as 1, so against a recent start a missing bool
    guard still kept by accident; against a start older than 1 the guard is the only thing keeping."""
    assert sw.gap_keeps([-1000.0], True, NOW) is True


def test_a_nan_start_is_an_unknown_start_that_keeps() -> None:
    """Review of 46b409cc9 (haiku C1): a gap whose start is NaN (a NaN `SCRATCH_SWEEP_BTIME` makes
    every start NaN) is an unknown start like `None` — INV-1 doubt keeps — never a dropped gap."""
    assert sw.gap_keeps([float("nan")], NOW - 100_000, NOW) is True


def test_a_gap_started_after_the_runs_window_keeps_nothing() -> None:
    """W-d1a4a8f5 (supersedes D-878 in part): a gap keeps only a process that started inside the
    run's own window [created - 300 s, end + 300 s]. Without an end the setuid document portal
    (fusermount3, started mid-uptime) kept every older run folder; /tmp is NOT cleared at boot here
    (74 of 652 sid dirs predated btime), so "until the next boot" was never a bound."""
    created, end = NOW - 50 * HOUR, NOW - 40 * HOUR
    assert sw.gap_keeps([NOW - HOUR], created, NOW, end=end) is False  # born after the window
    assert sw.gap_keeps([NOW - 45 * HOUR], created, NOW, end=end) is True  # born inside it
    assert sw.gap_keeps([end + 299], created, NOW, end=end) is True  # the margin is inclusive
    assert sw.gap_keeps([end + 301], created, NOW, end=end) is False
    assert sw.gap_keeps([NOW - 90 * DAY], created, NOW, end=end) is False  # before it, as today
    # doubt still keeps: an unusable start, an unusable created, and no end at all (today's rule)
    assert sw.gap_keeps([None], created, NOW, end=end) is True
    assert sw.gap_keeps([float("nan")], created, NOW, end=end) is True
    assert sw.gap_keeps([NOW - HOUR], None, NOW, end=end) is True
    assert sw.gap_keeps([NOW - HOUR], created, NOW) is True
    assert sw.gap_keeps([NOW - HOUR], created, NOW, end=None) is True
    for bad in (float("nan"), float("inf"), True, "x"):
        assert sw.gap_keeps([NOW - HOUR], created, NOW, end=bad) is True, bad
    # one gap inside the window keeps, whatever the others say
    assert sw.gap_keeps([NOW - HOUR, NOW - 45 * HOUR], created, NOW, end=end) is True


def test_the_run_window_ends_at_its_last_activity_seats_included(harness: Path) -> None:
    """W-d1a4a8f5: the window's end is the run's last activity — the close, a top-level write after
    it, or the newest seat transcript (a seat that acts moves its own transcript, which the folder's
    mtime does not see when it writes in place); a running/resumable marker's heartbeat; a trash
    folder's rename. Anything the marker cannot vouch for is None, which keeps as today — and so is
    an end before the run's own `created` (an inverted window), a future end, and a close no float
    holds (review pass 1 of W-d1a4a8f5: Opus C1-C4, Sonnet C2/C5, Haiku 2-3)."""
    sdir = _session(harness)
    tx_root = harness.parent / "tx"
    sids = (SID_A,)
    done = _run_folder(sdir, "d", closed_ago=40 * HOUR)
    owner = json.loads((done / ".owner").read_text(encoding="utf-8"))
    assert sw.run_window_end(done, owner, sids, [tx_root], NOW) == pytest.approx(NOW - 40 * HOUR)

    def seat(root: Path, sid: str, ago: float) -> Path:
        p = root / SLUG / sid / "subagents" / "agent-a1.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}\n", encoding="utf-8")
        _age(p, ago)
        return p

    s = seat(tx_root, SID_A, 10 * HOUR)
    got = sw.run_window_end(done, owner, sids, [tx_root], NOW)
    assert got == pytest.approx(NOW - 10 * HOUR), "a seat acting after the close extends the window"
    _age(s, -HOUR)  # a seat transcript dated an hour AHEAD of now: a clock jump, no answer
    assert sw.run_window_end(done, owner, sids, [tx_root], NOW) is None
    s.unlink()

    # a glob metacharacter in a root or a sid is a literal, never a pattern that hides the seat
    odd_root = harness.parent / "tx[1]"
    seat(odd_root, SID_A, 10 * HOUR)
    got = sw.run_window_end(done, owner, sids, [odd_root], NOW)
    assert got == pytest.approx(NOW - 10 * HOUR), "a bracketed transcript root hid the seat"

    # the seats of EITHER sid count: the marker's, and the directory's (D4 judges a mismatch)
    seat(tx_root, SID_B, 12 * HOUR)
    other = dict(owner, sid=SID_B)
    got = sw.run_window_end(done, other, (SID_B, SID_A), [tx_root], NOW)
    assert got == pytest.approx(NOW - 12 * HOUR), got
    assert sw._run_sids(other, SID_A) == (SID_B, SID_A)
    assert sw._run_sids({}, SID_A) == (SID_A,)
    assert sw._run_sids({"sid": 7}, SID_A) == (SID_A,)

    # a top-level write after the close raises the end (W-9f3f097c's own signal)
    wrote = _run_folder(sdir, "w", closed_ago=40 * HOUR)
    _age(wrote, 20 * HOUR)
    w_owner = json.loads((wrote / ".owner").read_text(encoding="utf-8"))
    assert sw.run_window_end(wrote, w_owner, ("none",), [tx_root], NOW) == pytest.approx(
        NOW - 20 * HOUR
    )

    running = _run_folder(sdir, "r", "running", closed_ago=None, heartbeat_ago=30 * HOUR)
    r_owner = json.loads((running / ".owner").read_text(encoding="utf-8"))
    assert sw.run_window_end(running, r_owner, ("none",), [tx_root], NOW) == pytest.approx(
        NOW - 30 * HOUR
    )
    # a running run's seats count too — its heartbeat moves only at events, not while a seat works
    assert sw.run_window_end(running, r_owner, sids, [tx_root], NOW) == pytest.approx(
        NOW - 30 * HOUR
    )
    seat(tx_root, SID_A, 5 * HOUR)
    assert sw.run_window_end(running, r_owner, sids, [tx_root], NOW) == pytest.approx(
        NOW - 5 * HOUR
    )
    resumable = dict(r_owner, state="resumable")
    assert sw.run_window_end(running, resumable, ("none",), [tx_root], NOW) == pytest.approx(
        NOW - 30 * HOUR
    )
    # an end BEFORE the run's own created is an inverted window: doubt, never a narrow keep
    inverted = dict(r_owner, created=NOW - 10 * HOUR)
    assert sw.run_window_end(running, inverted, ("none",), [tx_root], NOW) is None

    unvouched = dict(owner, closed_at=owner["created"] - DAY)  # a close before its own start
    assert sw.run_window_end(done, unvouched, sids, [tx_root], NOW) is None
    assert sw.run_window_end(done, None, sids, [tx_root], NOW) is None
    assert sw.run_window_end(done, dict(owner, state="weird"), sids, [tx_root], NOW) is None
    huge = dict(owner, created=10**400 - 1, closed_at=10**400)  # vouched, but no float holds it
    assert sw.run_window_end(done, huge, sids, [tx_root], NOW) is None

    trash = sdir / "scratchpad" / ".trash-t-2026-10-15T05-40-42-0300-0a1b2c"
    trash.mkdir()
    ctime = trash.lstat().st_ctime
    t_owner = dict(owner, created=ctime - DAY)
    assert sw.run_window_end(trash, t_owner, ("none",), [tx_root], NOW) == ctime


@pytest.mark.parametrize("created", [10**400, -(10**400)])
def test_a_huge_integer_created_is_compared_never_a_crash(created: int) -> None:
    """Review of 46b409cc9: `math.isfinite` raises OverflowError on an int no float can hold; an int
    always compares exactly, so it is usable — never a crash (both keep: one is future, one is old).
    The D-900 vouch reads the same `created` and compares it the same way."""
    assert sw.gap_keeps([NOW - 100_000], created, NOW) is True
    assert sw._close_is_vouched(created, NOW - 100_000, NOW) is (created < 0)


@pytest.mark.parametrize("created", [True, False, float("nan"), None, "x"])
def test_a_trash_folder_with_an_unusable_created_falls_back_to_its_rename_time(
    created: object, tmp_path: Path
) -> None:
    """W-a39d4c86 (fleet 01M505VVEJ): a `.trash-*` marker whose `created` is not a usable time falls
    back to the folder's ctime (the rename that made it). A bool passed `isinstance(int | float)`
    and skipped the fallback, so the folder was kept by every permanent same-uid daemon's gap."""
    trash = tmp_path / f".trash-x{KEY}"
    trash.mkdir()
    got = sw._created_for(trash, {"created": created})
    assert got == trash.lstat().st_ctime, got


def _one_pid_proc(tmp_path: Path) -> Path:
    """A /proc with one readable pid — no holders, no gaps, a probe that completes."""
    proc_root = tmp_path / "proc1"
    (proc_root / "1" / "fd").mkdir(parents=True, exist_ok=True)
    (proc_root / "1" / "comm").write_text("init\n", encoding="utf-8")
    return proc_root


def test_an_exited_gap_pid_is_dropped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A gap pid gone by the time its start is read held nothing — dropped, never an unknown that
    keeps (transient same-uid gaps showed in 2 of 8 live probes)."""
    proc_root = _gap_proc(tmp_path, started_ago=HOUR)
    monkeypatch.setenv("SCRATCH_SWEEP_BTIME", str(NOW - 100 * DAY))
    assert sw.gap_starts(["9999 (gone)"], proc_root) == []
    assert sw.gap_starts(["4242 (gpg-agent)"], proc_root) == [pytest.approx(NOW - HOUR, abs=1)]
    os.chmod(proc_root / "4242" / "fd", 0o700)


def test_a_markerless_trash_falls_back_to_its_rename_time(tmp_path: Path) -> None:
    """A `.trash-*` whose marker an interrupted rmtree took is judged against its own ctime (the
    rename): a gap process older than that never owned it; an unknown start still keeps."""
    trash = tmp_path / "scratchpad" / ".trash-x-2026-10-15T05-40-42-0300-0a1b2c"
    trash.mkdir(parents=True)
    ctime = trash.lstat().st_ctime
    common = {"session_dead": False, "held": {}, "probe_ok": True}
    older = sw.judge_run_folder(trash, "s", ctime + 60, gaps=[ctime - DAY], **common)
    unknown = sw.judge_run_folder(trash, "s", ctime + 60, gaps=[None], **common)
    assert older.cls == "consumed", older
    assert unknown.cls == "kept", unknown


# ── review round 1 (Phase B): graders for the confirmed candidates ────────────────────────────────
def test_a_worktree_of_another_repo_keeps_the_folder(
    harness: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R1-1: a worktree registered by a repo OTHER than the marker's is still a registered worktree —
    removing the folder would orphan that repo's registration (and its uncommitted file)."""
    repo_a = _repo(tmp_path)
    repo_b = tmp_path / "repo-b"
    repo_b.mkdir()
    _git(repo_b, "init", "-q", "-b", "main")
    (repo_b / "b.txt").write_text("b", encoding="utf-8")
    _git(repo_b, "add", "-A")
    _git(repo_b, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "b")
    folder = _run_folder(_session(harness), "foreign", repo=str(repo_a / ".git"))
    tree = folder / "seat-1" / "b-tree"
    _git(repo_b, "worktree", "add", "-q", str(tree), "-b", "wip")
    (tree / "wip.txt").write_text("uncommitted", encoding="utf-8")
    _age(folder / ".owner", 40 * HOUR)
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert folder.exists() and (tree / "wip.txt").exists(), out
    assert "no longer resolves" not in out and "does not list" in out, out  # the true reason


@pytest.mark.parametrize("where", ["dot-dir", "the-folder-itself"])
def test_a_worktree_pointer_anywhere_in_reach_keeps_the_folder(where: str, tmp_path: Path) -> None:
    """R1-2: the `.git` scan reaches depth 0 and hidden directories — a `.git` pointer FILE whose
    gitdir lies outside the folder is a registered worktree's, whatever its parent's name."""
    folder = tmp_path / "scratchpad" / "run-p-2026-10-15T05-40-42-0300-0a1b2c"
    pointer_dir = folder / ".hidden" / "tree" if where == "dot-dir" else folder
    pointer_dir.mkdir(parents=True)
    (pointer_dir / ".git").write_text("gitdir: /elsewhere/.git/worktrees/x\n", encoding="utf-8")
    assert sw.git_pointer_files(folder) == [pointer_dir / ".git"]


def test_the_idleness_walk_skips_only_marker_governed_run_folders(tmp_path: Path) -> None:
    """F9 review (W-c0a1d324): the walk skips a run folder that is a direct child of
    `<sid>/scratchpad/` — never a run-NAMED directory elsewhere, whose deep activity is the
    session's sign of life. Skipping that too read a live, pidless session dead."""
    sdir = tmp_path / "sid"
    nested = sdir / "scratchpad" / "work" / "run-x-2026-10-15T05-40-42-0300-0a1b2c" / "deep"
    nested.mkdir(parents=True)
    (nested / "f").write_text("fresh", encoding="utf-8")
    governed = sdir / "scratchpad" / "run-y-2026-10-15T05-40-42-0300-0a1b2c" / "deep"
    governed.mkdir(parents=True)
    (governed / "g").write_text("fresh too, but marker-governed", encoding="utf-8")
    for p in sorted(sdir.rglob("*"), reverse=True):
        _age(p, 30 * DAY)
    _age(sdir, 30 * DAY)
    _age(nested / "f", HOUR)  # the one fresh write, an hour before the seam's NOW
    budget = sw.WalkBudget(stats=10**6, deadline_s=30.0)
    newest, complete = sw.newest_mtime(sdir, budget, skip_run_folders=True)
    assert complete and newest > NOW - DAY, "the nested run-named dir's fresh file was skipped"
    _age(nested / "f", 30 * DAY)
    _age(governed / "g", HOUR)  # the governed folder's deep file is fresh: it is NOT read
    newest, complete = sw.newest_mtime(
        sdir, sw.WalkBudget(stats=10**6, deadline_s=30.0), skip_run_folders=True
    )
    assert complete and newest < NOW - 20 * DAY, "the walk entered a marker-governed run folder"


def test_a_scan_budget_keep_is_reported_with_its_own_remedy(
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """F2 review: a consumed folder too wide to scan is kept every night, so the size report names
    it — with the scan's reason and a remedy, never as a folder "a worktree keeps"."""
    sdir = _session(harness)
    wide = _run_folder(sdir, "wide", files=50)
    _age(wide / ".owner", 40 * HOUR)
    monkeypatch.setenv("SCRATCH_SWEEP_GIT_SCAN_BUDGET", "10")
    rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0 and wide.exists(), out
    report = json.loads(_report_path(tmp_path).read_text(encoding="utf-8"))
    flagged = {Path(r["path"]).name: r for r in report["run_folders"]}
    assert wide.name in flagged, flagged
    assert "scan stopped at its budget" in flagged[wide.name]["why"], flagged
    assert "worktree" not in flagged[wide.name]["why"].split("kept:")[0], flagged
    assert "SCRATCH_SWEEP_GIT_SCAN_BUDGET" in flagged[wide.name]["action"], flagged


def test_the_git_pointer_scan_is_bounded_and_keeps_past_its_budget(
    harness: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F2 (W-c0a1d324): the `.git` pointer scan read every entry at depths 0-3 with no breadth
    bound. It now stops at `SCRATCH_SWEEP_GIT_SCAN_BUDGET` and, incomplete, KEEPS the folder (an
    unseen worktree pointer may exist) with that reason; the list form `command_run.py` reads
    answers non-empty, so a resume never moves it. Under the default budget the same folder goes."""
    folder = _run_folder(_session(harness), "wide", files=50)
    _age(folder / ".owner", 40 * HOUR)
    monkeypatch.setenv("SCRATCH_SWEEP_GIT_SCAN_BUDGET", "10")
    found, complete = sw.git_pointer_scan(folder)
    assert found == [] and complete is False
    assert sw.git_pointer_files(folder) == [folder / ".git-scan-incomplete"]
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert folder.exists() and "stopped at its budget" in out, out
    monkeypatch.delenv("SCRATCH_SWEEP_GIT_SCAN_BUDGET")
    assert sw.git_pointer_scan(folder) == ([], True)
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert not folder.exists(), out


def test_a_self_contained_clone_is_scratch(
    harness: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R1-2's boundary: a plain clone (a `.git` DIRECTORY) and a submodule pointer into it are
    self-contained — nothing outside the folder refers to them — so a consumed folder holding them
    is still removed (a seat's clone is scratch, never a registration)."""
    folder = _run_folder(_session(harness), "clone")
    (folder / "seat-1" / "clone" / ".git" / "modules" / "sub").mkdir(parents=True)
    (folder / "seat-1" / "clone" / "sub").mkdir()
    (folder / "seat-1" / "clone" / "sub" / ".git").write_text(
        "gitdir: ../.git/modules/sub\n", encoding="utf-8"
    )
    _age(folder / ".owner", 40 * HOUR)
    assert sw.git_pointer_files(folder) == []
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert not folder.exists(), out


@pytest.mark.parametrize("change", ["reclosed", "heartbeat", "keep"])
def test_a_folder_that_changed_since_classification_is_kept(change: str, harness: Path) -> None:
    """R1-3: between `plan_run_folders` and `apply_run_rows` the marker is re-closed, its heartbeat
    refreshed, or a `.keep` dropped in — each is re-checked at removal time and keeps the folder."""
    sdir = _session(harness)
    folder = _run_folder(sdir, "moving")
    rows = sw.plan_run_folders([sdir], NOW)
    assert [r.cls for r in rows] == ["consumed"], rows
    if change == "reclosed":
        owner = json.loads((folder / ".owner").read_text(encoding="utf-8"))
        owner["closed_at"] = NOW - 60
        (folder / ".owner").write_text(json.dumps(owner), encoding="utf-8")
    elif change == "heartbeat":
        os.utime(folder / ".owner", (NOW, NOW))
    else:
        (folder / ".keep").write_text("", encoding="utf-8")
    out = io.StringIO()
    sw.apply_run_rows(rows, out=out)
    assert folder.exists(), out.getvalue()
    assert "KEPT" in out.getvalue(), out.getvalue()


def test_retire_refuses_a_folder_that_is_not_resumable(
    harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R1-4: `--retire` ends a RESUME — on a `running` (or `done`) folder it is refused, never a
    back door around the refusal set's "a running … one is never removed"."""
    folder = _run_folder(_session(harness), "live", "running", closed_ago=None)
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--retire", folder.name)
    assert rc == sw.RC_REFUSED, out
    assert json.loads((folder / ".owner").read_text(encoding="utf-8"))["state"] == "running"


def test_no_session_transcript_means_the_seat_check_cannot_tell(tmp_path: Path) -> None:
    """R1-5: with no transcript of the session in any listed root, "no seat wrote" is unknowable —
    None (the 36 h ceiling), never False (the 30-minute fast path)."""
    (tmp_path / "tx" / SLUG).mkdir(parents=True)
    assert sw._seat_write_after_close(SID_A, NOW - HOUR, [tmp_path / "tx"]) is None
    (tmp_path / "tx" / SLUG / f"{SID_A}.jsonl").write_text("{}", encoding="utf-8")
    assert sw._seat_write_after_close(SID_A, NOW - HOUR, [tmp_path / "tx"]) is False


def test_a_stale_registration_never_strands_a_consumed_folder(
    harness: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R1-6: a worktree whose directory is already gone leaves only a stale registration — nothing
    on disk to lose — so the consumed folder is removed (no repo-wide prune is run)."""
    main = _repo(tmp_path)
    folder = _run_folder(_session(harness), "stale", repo=str(main / ".git"))
    tree = folder / "seat-1" / "tree"
    _git(main, "worktree", "add", "-q", str(tree), "-b", "feat-gone")
    import shutil as _sh

    _sh.rmtree(tree)
    _age(folder / ".owner", 40 * HOUR)
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert not folder.exists(), out


def test_only_a_keyed_name_is_marker_governed(
    harness: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """R1-7/8: `run-<key>` and `.trash-<key>` carry the mint's 6-hex suffix; an agent's own
    `run-tests/` or `.trash-old/` is an untagged entry — judged by age as before, never removed by
    name by the run pass, never kept for ever as a markerless run folder."""
    pad = _session(harness) / "scratchpad"
    for name in ("run-tests", ".trash-old"):
        (pad / name).mkdir()
        (pad / name / "f").write_text("x", encoding="utf-8")
        _age_tree(pad / name, 7 * HOUR)
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(_one_pid_proc(harness.parent)))
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert (pad / "run-tests").exists() and (pad / ".trash-old").exists(), out
    monkeypatch.setenv("CLAUDE_SESSION_ID", SID_A)
    rc, out = _main(capsys, "--session", SID_A)
    assert rc == 0, out
    rows = {
        Path(ln.split(" · ")[0]).name: ln.split(" · ")[2] for ln in out.splitlines() if " · " in ln
    }
    assert rows.get("run-tests") == "stale" and rows.get(".trash-old") == "stale", out


@pytest.mark.parametrize("mode", [["--dead"], ["--hook"], ["--worktrees", "."]])
def test_run_folder_flags_refuse_another_mode(
    mode: list[str], harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R1-9: `--run-folders`/`--retire` beside another mode is a usage error, never silently dropped."""
    rc = sw.main(
        [
            *mode,
            "--run-folders",
            "--session",
            SID_A,
            "--retire",
            "run-x-2026-10-15T05-40-42-0300-0a1b2c",
        ]
    )
    assert rc == sw.RC_USAGE, capsys.readouterr()


def test_a_prunable_registration_with_its_directory_left_is_consumed(
    harness: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R2-1: a registration git calls `prunable` while its directory still exists (the tree's `.git`
    file deleted) cannot be `git worktree remove`d — trying would keep the folder every night.
    It is a broken tree inside a consumed folder: the folder is removed, no git call attempted."""
    main = _repo(tmp_path)
    folder = _run_folder(_session(harness), "broken", repo=str(main / ".git"))
    tree = folder / "seat-1" / "tree"
    _git(main, "worktree", "add", "-q", str(tree), "-b", "feat-broken")
    (tree / ".git").unlink()
    assert "prunable" in _git(main, "worktree", "list", "--porcelain")
    _age(folder / ".owner", 40 * HOUR)
    rc, out = _main(capsys, "--run-folders", "--session", SID_A, "--apply")
    assert rc == 0, out
    assert not folder.exists(), out


@pytest.mark.parametrize(
    ("name", "keyed"),
    [
        ("run-ui-facade", False),
        (".trash-build-c0ffee", False),
        ("run-tests-cafe12", False),
        ("run-fabrik-review-2026-10-15T05-40-42-0300-0a1b2c", True),
        (".trash-fabrik-review-2026-10-15T05-40-42-0000-0a1b2c", True),
    ],
)
def test_a_run_key_needs_the_started_at_segment(name: str, keyed: bool, tmp_path: Path) -> None:
    """R2-2: the mint's key is `<command>-<started_at>-<6 hex>`; a name merely ending in a hex-only
    word (`facade`, `c0ffee`) is an agent's own entry, never marker-governed."""
    (tmp_path / name).mkdir()
    assert sw.is_run_entry(tmp_path / name) is keyed


# ── Phase C: advisory measures (D5 seat size at round lives in test_command_run_scratch; D6) ──────
def _report_path(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".claude" / "state" / "scratch-size-report.json"


def _set_created(folder: Path, hours_ago: float) -> None:
    owner = json.loads((folder / ".owner").read_text(encoding="utf-8"))
    owner["created"] = NOW - hours_ago * HOUR
    (folder / ".owner").write_text(json.dumps(owner), encoding="utf-8")
    _age(folder / ".owner", 40 * HOUR)


def test_size_report(harness: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C2 / D6: `--dead --apply` writes `scratch-size-report.json` atomically — per-session apparent
    bytes outside running run folders, every run folder older than 72 h not `done` (an adopted-then-
    dead `resumable` one included) and every `done` folder past its grace a worktree keeps; a dry
    `--dead` writes nothing (P10)."""
    sdir = _session(harness)
    (sdir / "scratchpad" / "big.bin").write_bytes(b"x" * 1_000_000)
    running = _run_folder(sdir, "live", "running", closed_ago=None, heartbeat_ago=HOUR)
    (running / "huge.bin").write_bytes(b"y" * 3_000_000)
    old = _run_folder(sdir, "wall", "resumable")
    _set_created(old, 80)
    main = _repo(tmp_path)
    kept = _run_folder(sdir, "wt", repo=str(main / ".git"))
    _git(main, "worktree", "add", "-q", str(kept / "seat-1" / "tree"), "-b", "feat-dirty")
    (kept / "seat-1" / "tree" / "wip.txt").write_text("in flight", encoding="utf-8")
    _age(kept / ".owner", 40 * HOUR)

    rc, out = _main(capsys, "--dead")
    assert rc == 0 and not _report_path(tmp_path).exists(), "a dry --dead wrote the report"
    rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0, out
    report = json.loads(_report_path(tmp_path).read_text(encoding="utf-8"))
    sess = report["sessions"][SID_A]
    assert 1_000_000 <= sess["bytes"] < 3_000_000, sess  # the running folder is not counted
    flagged = {Path(r["path"]).name: r for r in report["run_folders"]}
    assert old.name in flagged and "--retire" in flagged[old.name]["action"], flagged
    assert kept.name in flagged and "worktree" in flagged[kept.name]["why"], flagged
    assert running.name not in flagged, flagged
    assert not list(_report_path(tmp_path).parent.glob("*.tmp")), "a temp file was left behind"


def _hook(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> str:
    payload = json.dumps({"session_id": SID_A, "cwd": "/opt/fabrik"})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    rc = sw.main(["--hook"])
    assert rc == 0
    return capsys.readouterr().out


def _write_report(tmp_path: Path, **over: object) -> None:
    report: dict = {"generated": NOW, "sessions": {SID_A: {"bytes": 1000}}, "run_folders": []}
    report.update(over)
    path = _report_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report), encoding="utf-8")


@pytest.mark.parametrize("trigger", ["disk", "session-bytes", "old-resumable", "none"])
def test_hook_alarm_line(
    trigger: str,
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C3 / D6: at SessionStart one alarm line when disk use passes 85 %, the session holds more
    than 5 GB outside running run folders, or it owns a run folder older than 72 h not `done` — the
    line for a `resumable` one names `--retire`; otherwise nothing; it removes nothing, rc 0."""
    _session(harness)
    monkeypatch.setenv("SCRATCH_SWEEP_DISK_USED_PCT", "90" if trigger == "disk" else "40")
    if trigger == "session-bytes":
        _write_report(tmp_path, sessions={SID_A: {"bytes": 6 * 1024**3}})
    elif trigger == "old-resumable":
        _write_report(
            tmp_path,
            run_folders=[
                {
                    "path": "/x/run-w",
                    "sid": SID_A,
                    "state": "resumable",
                    "why": "older than 72 h and not done",
                    "action": f"scratch_sweep.py --run-folders --session {SID_A} --retire run-w",
                }
            ],
        )
    else:
        _write_report(tmp_path)
    out = _hook(capsys, monkeypatch)
    alarm = [ln for ln in out.splitlines() if "SCRATCH ALARM" in ln]
    if trigger == "none":
        assert alarm == [], out
        return
    assert len(alarm) == 1, out
    if trigger == "old-resumable":
        assert "--retire run-w" in alarm[0], alarm


def test_refusal_set_and_nag_name_the_report(
    harness: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C4 / P10: `--help` and the hook's nag line both name `scratch-size-report.json` beside the
    lock as the only files written under `~/.claude/state`."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, timeout=30
    )
    assert "scratch-size-report.json" in " ".join(proc.stdout.split())
    stale = _session(harness) / "scratchpad" / "old-dir"
    stale.mkdir()
    (stale / "f").write_text("x", encoding="utf-8")
    _age_tree(stale, 7 * HOUR)
    monkeypatch.setenv("SCRATCH_SWEEP_DISK_USED_PCT", "10")
    out = _hook(capsys, monkeypatch)
    nag = [ln for ln in out.splitlines() if "stale entries" in ln]
    assert nag and "scratch-size-report.json" in nag[0], out


# ── Phase C review round 1: graders for the confirmed candidates ──────────────────────────────────
KEY = "-2026-10-15T05-40-42-0300-0a1b2c"  # the mint's key suffix: <started_at>-<6 hex>


def test_a_session_under_two_slugs_is_summed(harness: Path) -> None:
    """RC-A: a sid with a directory under two slugs (main checkout + worktree) is ONE session — its
    bytes are summed, never the last directory's alone."""
    a = _session(harness)
    b = harness / "-opt-other-slug" / SID_A
    (b / "scratchpad").mkdir(parents=True)
    (a / "scratchpad" / "a.bin").write_bytes(b"x" * 600_000)
    (b / "scratchpad" / "b.bin").write_bytes(b"y" * 600_000)
    sw.write_size_report([a, b], [], NOW)
    report = json.loads(Path(os.path.expanduser(sw.SIZE_REPORT_PATH)).read_text(encoding="utf-8"))
    assert report["sessions"][SID_A]["bytes"] >= 1_200_000, report


@pytest.mark.parametrize(
    "bad", [{"sessions": [1]}, {"sessions": "x"}, {"run_folders": 5}, {"sessions": {SID_A: 3}}]
)
def test_a_malformed_report_never_breaks_the_hook(
    bad: dict,
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """RC-B: a dict of the wrong shape raises nothing — the alarm says nothing about it and the
    stale-entries nag still prints."""
    stale = _session(harness) / "scratchpad" / "old-dir"
    stale.mkdir()
    (stale / "f").write_text("x", encoding="utf-8")
    _age_tree(stale, 7 * HOUR)
    monkeypatch.setenv("SCRATCH_SWEEP_DISK_USED_PCT", "10")
    _write_report(tmp_path, **bad)
    out = _hook(capsys, monkeypatch)
    assert "stale entries" in out, out
    assert "SCRATCH ALARM" not in out, out


def test_a_stale_report_is_named_never_read(
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """RC-C: a report older than 48 h is not evidence about today — its rows are ignored and the
    alarm says the nightly run has stopped writing it."""
    _session(harness)
    monkeypatch.setenv("SCRATCH_SWEEP_DISK_USED_PCT", "10")
    _write_report(tmp_path, generated=NOW - 5 * DAY, sessions={SID_A: {"bytes": 9 * 1024**3}})
    out = _hook(capsys, monkeypatch)
    alarm = [ln for ln in out.splitlines() if "SCRATCH ALARM" in ln]
    assert len(alarm) == 1 and "9.0 GB" not in alarm[0] and "old" in alarm[0], out


def test_disk_percent_is_dfs_use_percent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """RC-D: `used / (used + free-to-users)` — df's Use%, never `used / total`, which hides the
    reserved blocks and fires several points late."""
    from collections import namedtuple

    du = namedtuple("du", "total used free")
    monkeypatch.delenv("SCRATCH_SWEEP_DISK_USED_PCT", raising=False)
    monkeypatch.setattr(sw.shutil, "disk_usage", lambda _p: du(100, 80, 14))
    assert sw._disk_used_pct(tmp_path) == pytest.approx(80 / 94 * 100)


def test_an_unmeasured_session_alarms(
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """RC-E: a session whose `du` missed its deadline is the large one the alarm exists for — it
    says so, never silence."""
    _session(harness)
    monkeypatch.setenv("SCRATCH_SWEEP_DISK_USED_PCT", "10")
    _write_report(tmp_path, sessions={SID_A: {"bytes": None, "unmeasured": True}})
    out = _hook(capsys, monkeypatch)
    alarm = [ln for ln in out.splitlines() if "SCRATCH ALARM" in ln]
    assert len(alarm) == 1 and "could not be measured" in alarm[0], out


def test_the_report_is_measured_outside_the_global_lock(
    harness: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """RC-F: the report's `du` runs after the global lock is released — a manual `--apply` is never
    told "another sweep holds the lock" for up to the report's 600 s budget."""
    _session(harness)
    seen: list[bool] = []

    def _probe(*_a: object, **_k: object) -> None:
        with sw._Lock() as got:
            seen.append(got)

    monkeypatch.setattr(sw, "write_size_report", _probe)
    rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0 and seen == [True], out


def test_the_report_names_no_trash_and_flags_a_markerless_age(harness: Path) -> None:
    """RC-G / RC-I: a `.trash-<key>` leftover is not a run folder to advise on, and a `running`
    marker with no `created` is flagged (an unknown age is never "young")."""
    sdir = _session(harness)
    trash = sdir / "scratchpad" / f".trash-x{KEY}"
    trash.mkdir()
    (trash / ".owner").write_text(
        json.dumps({"state": "resumable", "created": NOW - 90 * HOUR}), encoding="utf-8"
    )
    nocreated = _run_folder(sdir, "nc", "running", closed_ago=None, heartbeat_ago=HOUR)
    owner = json.loads((nocreated / ".owner").read_text(encoding="utf-8"))
    owner.pop("created")
    (nocreated / ".owner").write_text(json.dumps(owner), encoding="utf-8")
    sw.write_size_report([sdir], [], NOW)
    report = json.loads(Path(os.path.expanduser(sw.SIZE_REPORT_PATH)).read_text(encoding="utf-8"))
    named = {Path(r["path"]).name for r in report["run_folders"]}
    assert trash.name not in named and nocreated.name in named, report


def test_a_zero_close_time_reads_as_a_time_in_the_reason() -> None:
    """Review of 2dd7ac9e6: a `closed_at` of 0.0 is a (very old) time, not a missing one — the old
    `f.closed_at or now` read it as `now` and wrote "closed 0s ago" into a removal reason."""
    facts = sw.RunFacts("done", 0.0, 0.0, False, False, False, True, False, False)
    verdict, reason = sw.classify_run_folder(facts, NOW)
    assert verdict == "consumed", reason
    assert "closed 0s ago" not in reason, reason


def test_the_report_names_a_done_folder_whose_close_cannot_be_vouched_for(harness: Path) -> None:
    """D-900's cost made visible (review of b5c1abd69): a `done` folder whose close the marker
    cannot vouch for is kept by every sweep, so the size report names it with its remedy; a sane
    `done` folder past its grace is the sweep's to remove, not advice."""
    sdir = _session(harness)
    unvouched = _run_folder(sdir, "unvouched")
    owner = json.loads((unvouched / ".owner").read_text(encoding="utf-8"))
    owner["closed_at"] = 0
    (unvouched / ".owner").write_text(json.dumps(owner), encoding="utf-8")
    future = _run_folder(sdir, "future")
    owner = json.loads((future / ".owner").read_text(encoding="utf-8"))
    owner["closed_at"] = NOW + 400 * DAY  # inside its grace for ever, so kept — silently, before
    (future / ".owner").write_text(json.dumps(owner), encoding="utf-8")
    sane = _run_folder(sdir, "sane")
    sw.write_size_report([sdir], [], NOW)
    report = json.loads(Path(os.path.expanduser(sw.SIZE_REPORT_PATH)).read_text(encoding="utf-8"))
    flagged = {Path(r["path"]).name: r for r in report["run_folders"]}
    assert unvouched.name in flagged and "vouch" in flagged[unvouched.name]["why"], report
    assert future.name in flagged and "vouch" in flagged[future.name]["why"], report
    assert sane.name not in flagged, report


@pytest.mark.parametrize("generated", [NOW + 1e9, float("nan"), "yesterday"])
def test_a_future_or_undated_report_is_never_fresh(
    generated: object,
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """RC-C2: freshness is `0 <= age <= 48 h` on a finite number — a report dated in the future
    (clock skew, a test clock left set) or NaN is not evidence, and the line never claims an age
    it cannot know."""
    _session(harness)
    monkeypatch.setenv("SCRATCH_SWEEP_DISK_USED_PCT", "10")
    _write_report(tmp_path, generated=generated, sessions={SID_A: {"bytes": 9 * 1024**3}})
    out = _hook(capsys, monkeypatch)
    alarm = [ln for ln in out.splitlines() if "SCRATCH ALARM" in ln]
    assert len(alarm) == 1 and "9.0 GB" not in alarm[0], out
    assert "0s old" not in alarm[0], out


def test_no_report_shape_costs_the_disk_reason(
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """RC-B2: whatever the report holds — here an integer too large for a float — the report's
    reasons are dropped and the disk reason, read live, still prints (the class RC-B began)."""
    _session(harness)
    monkeypatch.setenv("SCRATCH_SWEEP_DISK_USED_PCT", "90")
    path = _report_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"generated": 1' + "0" * 400 + "}", encoding="utf-8")
    out = _hook(capsys, monkeypatch)
    alarm = [ln for ln in out.splitlines() if "SCRATCH ALARM" in ln]
    assert len(alarm) == 1 and "disk 90% used" in alarm[0], out


def test_holders_are_re_probed_after_a_worktree_is_removed(
    harness: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-B1: `git worktree remove` can take seconds — a holder that appears inside the folder in
    that window keeps it (the folder is re-probed after the removal, before the rename)."""
    main = _repo(tmp_path)
    folder = _run_folder(_session(harness), "wtheld", repo=str(main / ".git"))
    _git(main, "worktree", "add", "-q", str(folder / "seat-1" / "tree"), "-b", "feat-merged")
    _age(folder / ".owner", 40 * HOUR)
    rows = sw.plan_run_folders([folder.parent.parent], NOW)
    assert [r.cls for r in rows] == ["consumed"], rows
    real = sw.probe_holders
    calls: list[int] = []

    def _probe(targets, proc_root=None):
        calls.append(1)
        held, gaps, ok = real(targets, proc_root)
        if len(calls) > 1:  # after the worktree removal: a process opened a file inside
            held = {**held, str(folder): "pid 1 appeared"}
        return held, gaps, ok

    monkeypatch.setattr(sw, "probe_holders", _probe)
    out = io.StringIO()
    sw.apply_run_rows(rows, out=out)
    assert folder.exists(), out.getvalue()
    assert "KEPT" in out.getvalue(), out.getvalue()


def test_a_boolean_created_stays_an_unknown_age_beside_an_adopted_time(harness: Path) -> None:
    """F-B2: a corrupted `created: true` never becomes a "known" age just because an `adopted`
    time sits beside it — the same bool guard the age test itself applies."""
    sdir = _session(harness)
    folder = _run_folder(sdir, "boolc", "running", closed_ago=None, heartbeat_ago=HOUR)
    owner = json.loads((folder / ".owner").read_text(encoding="utf-8"))
    owner["created"] = True
    owner["adopted"] = NOW - HOUR
    (folder / ".owner").write_text(json.dumps(owner), encoding="utf-8")
    sw.write_size_report([sdir], [], NOW)
    report = json.loads(Path(os.path.expanduser(sw.SIZE_REPORT_PATH)).read_text(encoding="utf-8"))
    flagged = {Path(r["path"]).name: r for r in report["run_folders"]}
    assert folder.name in flagged and "unknown" in flagged[folder.name]["why"], report


def test_a_folder_kept_at_removal_time_keeps_its_dead_session(
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """INV-1 (docs review, D-1): a consumed folder the apply-time re-check KEEPS (its marker rewritten
    after classification) leaves its dead session split, never removed whole with the folder in it."""
    dead = _session(harness, SID_A)
    folder = _run_folder(dead, "late", closed_ago=40 * HOUR, heartbeat_ago=30 * DAY)
    junk = dead / "scratchpad" / "junk"
    junk.mkdir()
    (junk / "f").write_text("x", encoding="utf-8")
    _dead_record(tmp_path, SID_A)
    _age_tree(dead, 30 * DAY)
    real = sw.apply_run_rows

    def _late_keep(rows, *a, **k):  # the marker changes between the plan and the removal
        owner = json.loads((folder / ".owner").read_text(encoding="utf-8"))
        owner["state"] = "running"
        (folder / ".owner").write_text(json.dumps(owner), encoding="utf-8")
        return real(rows, *a, **k)

    monkeypatch.setattr(sw, "apply_run_rows", _late_keep)
    rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0, out
    assert folder.exists() and dead.exists(), out
    assert not junk.exists(), out


def test_a_split_dead_session_removes_an_untagged_run_named_entry(
    harness: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """P8 (docs review, D-4): only the mint's keyed name is marker-governed — an agent's own
    `run-tests/` in a split dead session goes with the other entries, never kept for ever."""
    dead = _session(harness, SID_A)
    active = _run_folder(dead, "active", "resumable", heartbeat_ago=30 * DAY)
    own = dead / "scratchpad" / "run-tests"
    own.mkdir()
    (own / "f").write_text("x", encoding="utf-8")
    _dead_record(tmp_path, SID_A)
    _age_tree(dead, 30 * DAY)
    rc, out = _main(capsys, "--dead", "--apply")
    assert rc == 0, out
    assert active.exists() and not own.exists(), out
