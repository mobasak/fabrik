"""Behavior Contract — the coordinator's builder-pane watcher (W-c814836f, D-1396 duty 3).

`scripts/sysadmin/watch_builders.py <sid> <repo>` is a ONE-WAKE background watch: it reads every builder pane of the
repo's agents_up grid (`rotate_session.builder_panes`, the PANE WAITING scan's own filter) and the repo's mailbox, and
exits with one line when a builder finished a turn, went from busy to not busy, or mail for the coordinator landed.
Its state persists beside its lock, so a finish that happens while the coordinator handles a wake is still named by
the next arm. `rotate_session.pane_state` decides busy from the screen: a spinner above the input box, or a seat row /
monitor count below it; a `· done` turn end is idle whatever shells note follows (measured 2026-10-31: counting
leftover shells as busy hid an idle builder for 2 h). tmux is a scripted fake (`ROTATE_TMUX`), so no test reads a
real pane.
"""

from __future__ import annotations

import fcntl
import importlib.util as _ilu
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WATCH = REPO / "scripts" / "sysadmin" / "watch_builders.py"
_spec = _ilu.spec_from_file_location(
    "_wb_rotate_session", REPO / "scripts" / "sysadmin" / "rotate_session.py"
)
rs = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(rs)

SID = "11111111-2222-3333-4444-555555555555"

# ── screens, copied from live captures (2026-10-31) ─────────────────────────────────────────────────────────────────


def _screen(above: list[str], typed: str = "", below: tuple[str, ...] = ()) -> str:
    """A Claude Code pane: transcript rows, the framed input box (the top rule carries the agent name), the footer."""
    return "\n".join(
        [
            *above,
            "─────────────────────────────────────── infra ─",
            f"❯ {typed}",
            "───────────────────────────────────────────────",
            "  Opus 5.5  ·  ctx 61%  ·  7d 96%",
            *(below or ("  ⏵⏵ bypass permissions on · 1 shell",)),
        ]
    )


IDLE_SHELLS = _screen(
    [
        "● Told the coordinator.",
        "",
        "✻ Sautéed for 3m 45s · done 11:27 AM · 1 shell still running",
        "  new task? /clear to save 669.2k t… · ✘ Auto-update failed · Run claude doctor",
    ]
)
IDLE_WRAPPED = _screen(
    ["● Done.", "", "✻ Brewed for 3m 39s · done 11:39 AM · 1", "  shell still running"]
)
BUSY = _screen(
    [
        "✻ Churned for 49s · done 12:31 PM · 3 shells still running",  # an OLD turn end above the live spinner
        "● Bash(pytest -q)",
        "  ⎿  --… (1m",  # tool output that also reads `word… (`
        "✽ Reticulating… (3m 33s · ↓ 2.5k tokens)",
    ]
)
BUSY_TWO_WORDS = _screen(["✻ Compacting conversation… (12s)"])
BUSY_BARE = _screen(["✢ Thinking…"])
BUSY_WAITING = _screen(["✻ Waiting for 2 background agents to finish"])
BUSY_SEATS = _screen(
    ["✻ Sautéed for 20s · done 1:57 PM"],
    below=(
        "  ⏵⏵ bypass permissions on · 4 shells",
        "",
        "  ● main",
        "  ◯ fabrik-reviewer  Running merge_test… 21m 16s · ↓ 69.7k tokens",
    ),
)
BUSY_MONITOR = _screen(
    ["✻ Sautéed for 20s · done 1:57 PM"], below=("  ⏵⏵ bypass permissions on · 2 monitors",)
)
IDLE_SEAT_TEXT_ABOVE = _screen(
    [
        "● I armed 2 monitors and listed:",
        "  ◯ fabrik-reviewer  Running x… 1m",
        "",
        "✻ Baked for 9s · done 2:01 PM",
    ]
)
IDLE_TYPED = _screen(["✻ Baked for 9s · done 2:01 PM"], typed="Done… (see the review)")
DIALOG = "\n".join(
    [
        "● Bash(rm -rf build)",
        "",
        " Do you want to proceed?",
        " ❯ 1. Yes",
        "   2. No, and tell Claude what to do differently (esc)",
        "",
        " Esc to cancel",
    ]
)


def test_pane_state_reads_live_screens():
    assert rs.pane_state(IDLE_SHELLS) == (False, "✻ Sautéed for 3m 45s · done 11:27 AM")
    assert rs.pane_state(IDLE_WRAPPED) == (False, "✻ Brewed for 3m 39s · done 11:39 AM")
    for screen in (BUSY, BUSY_TWO_WORDS, BUSY_BARE, BUSY_WAITING, BUSY_SEATS, BUSY_MONITOR):
        assert rs.pane_state(screen)[0] is True, screen
    # the seat row and monitor count count only in the footer below the box; typed box text is never a spinner
    assert rs.pane_state(IDLE_SEAT_TEXT_ABOVE) == (False, "✻ Baked for 9s · done 2:01 PM")
    assert rs.pane_state(IDLE_TYPED) == (False, "✻ Baked for 9s · done 2:01 PM")
    # a dialog: no box, no spinner, no turn end — not busy, so a busy→dialog edge wakes the coordinator
    # a notice or a reply bullet truncated with `…` is not a spinner — only the spinner's own glyphs are (review C-1/C-2)
    for row in (
        "      ✘ Auto-update fail…",
        "  ✔ Update installed · Restart to…",
        "  ⚠ Context low · Run /compact…",
        "  - Checking files…",
        "  • Reading the log…",
    ):
        screen = _screen(["✻ Worked for 20s · done 1:59 PM", row])
        assert rs.pane_state(screen) == (False, "✻ Worked for 20s · done 1:59 PM"), row
    # the waiting-for row counts only as a spinner row, never as text quoted in a reply (review Ch-5)
    quoted = _screen(
        ["✻ Baked for 9s · done 2:01 PM", "● It said: Waiting for 2 background agents to finish"]
    )
    assert rs.pane_state(quoted) == (False, "✻ Baked for 9s · done 2:01 PM")
    # every spinner frame measured on live panes reads busy
    for glyph in "·✢✳✶✻✽*":
        assert rs.pane_state(_screen([f"{glyph} Pondering… (4s · ↓ 12 tokens)"]))[0] is True, glyph
    assert rs.pane_state(DIALOG) == (False, "")
    assert rs.pane_state("") == (False, "")


# ── the grid filter ─────────────────────────────────────────────────────────────────────────────────────────────────

FAKE_TMUX = """#!/usr/bin/env python3
import json, os, sys, time
st = json.load(open(os.environ["FAKE_TMUX_STATE"]))
a = sys.argv[1:]
if st.get("sleep"):
    time.sleep(st["sleep"])
if st.get("rc"):
    sys.stderr.write(st.get("err", "") + "\\n")
    sys.exit(st["rc"])
if a[0] == "list-panes":
    print("\\n".join(st["panes"]))
elif a[0] == "capture-pane":
    if "-e" in a:
        sys.stderr.write("watch must capture without -e\\n")
        sys.exit(9)
    if a[-1] in st.get("gone", []):  # listed, but closed before its capture
        sys.stderr.write("can't find pane: " + a[-1] + "\\n")
        sys.exit(1)
    sys.stdout.write(st["screens"].get(a[-1], ""))
"""


@pytest.fixture
def tmux(tmp_path, monkeypatch):
    exe = tmp_path / "tmux"
    exe.write_text(FAKE_TMUX, encoding="utf-8")
    exe.chmod(0o755)
    state = tmp_path / "tmux.json"
    monkeypatch.setenv("ROTATE_TMUX", str(exe))
    monkeypatch.setenv("FAKE_TMUX_STATE", str(state))

    def put(**st):
        tmp = state.with_suffix(".tmp")
        tmp.write_text(json.dumps(st), encoding="utf-8")
        os.replace(tmp, state)  # the watcher reads it on every tick: never a half-written file

    return put


def _row(pane: str, session: str, group: str, agent: str, path: str) -> str:
    return "\t".join((pane, session, group, agent, path))


def test_builder_panes_is_the_waiting_filter(tmux, tmp_path):
    main = tmp_path / "fabrik"
    main.mkdir()
    tmux(
        panes=[
            _row("%5", "fabrik", "fabrik", "infra-2", "/x/wt/infra-2"),
            _row(
                "%5", "fabrik-2", "fabrik", "infra-2", "/x/wt/infra-2"
            ),  # the grouped twin: same pane
            _row("%7", "fabrik-2", "fabrik", "intel", "/x/wt/intel"),
            _row("%8", "other", "", "dev1", "/x/other"),  # another repo's grid
            _row("%9", "fabrik", "fabrik", "", "/x/shell"),  # untagged
            _row("%10", "fabrik", "fabrik", "coord", "/x/elsewhere"),  # the caller by name
            _row(
                "%11", "fabrik", "fabrik", "wef4", str(main)
            ),  # a pane in the main checkout: the caller's own
        ],
        screens={},
    )
    assert rs.builder_panes(str(main), exclude="coord") == {"%5": "infra-2", "%7": "intel"}
    assert rs.builder_panes(str(main)) == {"%5": "infra-2", "%7": "intel", "%10": "coord"}
    tmux(rc=1, err="no server running on /tmp/tmux-1000/default")
    assert rs.builder_panes(str(main)) == {}  # no grid
    tmux(rc=1, err="server exited unexpectedly")
    with pytest.raises(RuntimeError):
        rs.builder_panes(str(main))


# ── the watch ───────────────────────────────────────────────────────────────────────────────────────────────────────


def _repo(tmp_path: Path, distributor: str = "coord") -> Path:
    main = tmp_path / "proj"
    (main / ".git").mkdir(parents=True)
    (main / ".fabrik" / "work").mkdir(parents=True)
    (main / ".fabrik" / "work" / "config.json").write_text(json.dumps({"distributor": distributor}))
    (tmp_path / "mail" / "proj" / "inbox").mkdir(parents=True)
    return main


def _env(tmp_path: Path) -> dict[str, str]:
    e = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_AGENT", "CLAUDE_PROJECT_DIR")}
    e.update(
        CLAUDE_SOUND_LOCKDIR=str(tmp_path / "locks"),
        FABRIK_MAIL_ROOT=str(tmp_path / "mail"),
        BUILDER_WATCH_POLL="0.2",
    )
    return e


def _start(tmp_path: Path, main: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(WATCH), SID, str(main)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_env(tmp_path),
    )


def _state(tmp_path: Path) -> Path:
    return tmp_path / "locks" / f"{SID}.builderwatch.state.json"


def _wait_for(pred, what: str, timeout: float = 15.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {what}")


def _ticked(tmp_path: Path, after: float) -> bool:
    p = _state(tmp_path)
    return p.exists() and p.stat().st_mtime > after


def _finish(proc: subprocess.Popen, timeout: float = 15.0) -> tuple[int, str, str]:
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        raise AssertionError(f"the watch never woke: {out!r} {err!r}") from None
    return proc.returncode, out, err


PANES = [
    _row("%1", "proj", "proj", "dev1", "/x/wt/dev1"),
    _row("%2", "proj", "proj", "dev2", "/x/wt/dev2"),
]
IDLE_LATER = IDLE_SHELLS.replace("3m 45s · done 11:27 AM", "1m 2s · done 2:30 PM")


def test_wakes_on_finished_turns_across_arms(tmux, tmp_path):
    main = _repo(tmp_path)
    # dev1 busy, dev2 idle from the start: the first tick is a baseline and wakes nobody
    tmux(panes=PANES, screens={"%1": BUSY, "%2": IDLE_SHELLS})
    t0 = time.time()
    proc = _start(tmp_path, main)
    try:
        _wait_for(lambda: _ticked(tmp_path, t0), "the baseline tick")
        t1 = time.time()
        _wait_for(lambda: _ticked(tmp_path, t1), "a second tick")
        assert proc.poll() is None, "an unchanged grid must not wake"
        tmux(panes=PANES, screens={"%1": IDLE_SHELLS, "%2": IDLE_SHELLS})  # dev1 finished
        rc, out, _ = _finish(proc)
    finally:
        proc.kill()
    assert rc == 0, out
    assert "dev1 (%1)" in out and "dev2" not in out.splitlines()[0], out
    assert f"watch_builders.py {SID} {main}" in out, "the wake line carries the re-arm order"
    # dev2 finishes a short turn while nobody watches; the next arm names it from the saved state, at once
    tmux(panes=PANES, screens={"%1": IDLE_SHELLS, "%2": IDLE_LATER})
    rc, out, _ = _finish(_start(tmp_path, main))
    assert rc == 0 and "dev2 (%2)" in out and "dev1" not in out.splitlines()[0], out


def _mail(main: Path, tmp_path: Path, name: str, **fm: str) -> Path:
    head = {"id": name, "from": "proj", "to": "proj", "kind": "request", **fm}
    body = "---\n" + "".join(f"{k}: {v}\n" for k, v in head.items()) + "---\nWHAT: x\n"
    p = tmp_path / "mail" / "proj" / "inbox" / f"{name}.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_wakes_on_coordinator_mail_only(tmux, tmp_path):
    main = _repo(tmp_path)
    tmux(panes=PANES, screens={"%1": IDLE_SHELLS, "%2": IDLE_SHELLS})
    _mail(main, tmp_path, "OLD1", agent="coord")  # already there at the baseline: never a wake
    t0 = time.time()
    proc = _start(tmp_path, main)
    try:
        _wait_for(lambda: _ticked(tmp_path, t0), "the baseline tick")
        _mail(main, tmp_path, "B1", agent="dev2", **{"from-agent": "dev1"})  # a builder's mail
        _mail(
            main, tmp_path, "OWN1", agent="coordinator", **{"from-agent": "coord"}
        )  # our own (from: proj)
        t1 = time.time()
        _wait_for(lambda: _ticked(tmp_path, t1), "a tick over the non-wakes")
        assert proc.poll() is None, "a builder's mail and our own must not wake"
        _mail(
            main,
            tmp_path,
            "W1",
            **{"from": "other-repo", "agent": "coordinator", "from-agent": "coord"},
        )
        _mail(
            main, tmp_path, "W2", **{"from-agent": "dev1"}
        )  # no agent line: unaddressed, the coordinator's
        rc, out, _ = _finish(proc)
    finally:
        proc.kill()
    assert (
        rc == 0 and "W1" in out and "OLD1" not in out and "B1" not in out and "OWN1" not in out
    ), out
    # a re-route in place (same name, new mtime) to the coordinator is news too
    p = tmp_path / "mail" / "proj" / "inbox" / "B1.md"
    p.write_text(p.read_text().replace("agent: dev2", "agent: coord"))
    os.utime(p, ns=(time.time_ns() + 10**9, time.time_ns() + 10**9))
    rc, out, _ = _finish(_start(tmp_path, main))
    assert rc == 0 and "B1" in out, out


def test_lock_and_blind_exits(tmux, tmp_path):
    main = _repo(tmp_path)
    tmux(panes=PANES, screens={"%1": BUSY, "%2": BUSY})
    locks = tmp_path / "locks"
    locks.mkdir()
    fd = os.open(str(locks / f"{SID}.builderwatch.lock"), os.O_WRONLY | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        rc, out, _ = _finish(_start(tmp_path, main))
        assert rc == 0 and "already armed" in out, out
    finally:
        os.close(fd)
    # the lock file vanishes under a running watch (a /tmp wipe): it says so and exits
    t0 = time.time()
    proc = _start(tmp_path, main)
    try:
        _wait_for(lambda: _ticked(tmp_path, t0), "the baseline tick")
        (locks / f"{SID}.builderwatch.lock").unlink()
        rc, out, _ = _finish(proc)
    finally:
        proc.kill()
    assert rc == 0 and "lock" in out and "re-arm" in out, out
    # a scan that fails three ticks running is a BLIND wake, never a silent watch
    tmux(rc=1, err="server exited unexpectedly")
    rc, out, _ = _finish(_start(tmp_path, main))
    assert rc == 0 and "BLIND" in out and "re-arm" in out, out


def test_a_vanished_pane_or_grid_wakes(tmux, tmp_path):
    """A builder pane that disappears (a crash, a dead tmux server) is a wake, never silence — review A-1."""
    main = _repo(tmp_path)
    tmux(panes=PANES, screens={"%1": BUSY, "%2": IDLE_SHELLS})
    t0 = time.time()
    proc = _start(tmp_path, main)
    try:
        _wait_for(lambda: _ticked(tmp_path, t0), "the baseline tick")
        tmux(panes=PANES[1:], screens={"%2": IDLE_SHELLS})  # %1 is gone from the grid
        rc, out, _ = _finish(proc)
    finally:
        proc.kill()
    assert rc == 0 and "GONE: dev1 (%1)" in out and "dev2" not in out.splitlines()[0], out
    # the whole tmux server gone: every pane it saw is named
    tmux(panes=PANES, screens={"%1": BUSY, "%2": BUSY})
    _state(tmp_path).unlink()
    t1 = time.time()
    proc = _start(tmp_path, main)
    try:
        _wait_for(lambda: _ticked(tmp_path, t1), "the baseline tick")
        tmux(rc=1, err="no server running on /tmp/tmux-1000/default")
        rc, out, _ = _finish(proc)
    finally:
        proc.kill()
    assert rc == 0 and "GONE: dev1 (%1)" in out and "GONE: dev2 (%2)" in out, out


def test_any_failure_after_the_lock_still_prints_a_rearm_line(tmux, tmp_path):
    """Every exit prints its line: an exception after the lock is taken is a FAILED line with the re-arm order, never
    a bare traceback the coordinator reads as nothing — review A-2."""
    main = _repo(tmp_path)
    tmux(panes=PANES, screens={"%1": BUSY, "%2": BUSY})
    env = {**_env(tmp_path), "BUILDER_WATCH_POLL": "abc"}
    proc = subprocess.run(
        [sys.executable, str(WATCH), SID, str(main)],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 1, proc
    assert "BUILDER WATCH FAILED" in proc.stdout and "re-arm" in proc.stdout, proc.stdout


def test_the_wake_reaches_the_pipe_before_the_state_is_saved(tmux, tmp_path):
    """Review A-X1: the wake is FLUSHED before the state is saved — a background task's stdout is a pipe, which Python
    block-buffers, so a kill between the save and the interpreter's exit would lose a wake the saved state no longer
    repeats. The stub dies, without flushing, inside the save that follows the wake."""
    main = _repo(tmp_path)
    tmux(panes=PANES, screens={"%1": BUSY, "%2": IDLE_SHELLS})
    prog = (
        "import os, sys, runpy\n"
        f"sys.argv = ['watch_builders.py', {SID!r}, {str(main)!r}]\n"
        f"mod = runpy.run_path({str(WATCH)!r}, run_name='watch_builders_under_test')\n"
        "calls = []\n"
        "real = mod['_save']\n"
        "def dying_save(path, state):\n"
        "    calls.append(1)\n"
        "    if len(calls) > 1 and state['panes'].get('%1', {}).get('busy') is False:\n"
        "        os._exit(0)  # the save that follows dev1's wake: no exit flush\n"
        "    real(path, state)\n"
        "mod['_save'] = dying_save\n"
        "mod['_watch'].__globals__['_save'] = dying_save\n"
        "sys.exit(mod['main'](sys.argv[1:]))\n"
    )
    t0 = time.time()
    proc = subprocess.Popen(
        [sys.executable, "-c", prog],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_env(tmp_path),
    )
    try:
        _wait_for(lambda: _ticked(tmp_path, t0), "the baseline tick")
        tmux(panes=PANES, screens={"%1": IDLE_SHELLS, "%2": IDLE_SHELLS})
        rc, out, _ = _finish(proc)
    finally:
        proc.kill()
    assert "BUILDER WAKE: IDLE: dev1 (%1)" in out, out


def test_a_failed_capture_keeps_the_panes_last_look(tmux, tmp_path):
    """A pane listed but whose capture fails keeps its last state, so its finish on the next look still wakes — the
    retention clause of review A-1 (without it the pane reads first-seen and its finish is lost)."""
    main = _repo(tmp_path)
    tmux(panes=PANES, screens={"%1": BUSY, "%2": IDLE_SHELLS})
    t0 = time.time()
    proc = _start(tmp_path, main)
    try:
        _wait_for(lambda: _ticked(tmp_path, t0), "the baseline tick")
        t1 = time.time()
        tmux(panes=PANES, screens={"%2": IDLE_SHELLS}, gone=["%1"])
        _wait_for(lambda: _ticked(tmp_path, t1), "a look whose capture of %1 fails")
        assert proc.poll() is None, "a failed capture of a listed pane is no wake"
        tmux(panes=PANES, screens={"%1": IDLE_SHELLS, "%2": IDLE_SHELLS})
        rc, out, _ = _finish(proc)
    finally:
        proc.kill()
    assert rc == 0 and "IDLE: dev1 (%1)" in out, out


def test_a_transient_shared_probe_never_turns_an_arm_away(tmux, tmp_path):
    """The per-prompt check probes the lock with a SHARED lock for an instant; a watch starting inside that instant
    retries and arms, never prints "already armed" — review Bh-4."""
    import threading

    main = _repo(tmp_path)
    tmux(panes=PANES, screens={"%1": BUSY, "%2": BUSY})
    locks = tmp_path / "locks"
    locks.mkdir()
    fd = os.open(str(locks / f"{SID}.builderwatch.lock"), os.O_RDONLY | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_SH)
    timer = threading.Timer(0.12, lambda: fcntl.flock(fd, fcntl.LOCK_UN))
    timer.start()
    t0 = time.time()
    proc = _start(tmp_path, main)
    try:
        _wait_for(lambda: _ticked(tmp_path, t0) or proc.poll() is not None, "the arm")
        assert proc.poll() is None, proc.communicate()[0]
    finally:
        proc.kill()
        timer.cancel()
        os.close(fd)
