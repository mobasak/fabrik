"""Behavior Contract — scripts/sysadmin/rotate_session.py (W-f975fee0 slice 2, D-1123, D-1135).

The coordinator's verb (`request`) resolves an agent's pane, claude process and session, runs six checks that each fail
CLOSED, and writes ONE data-only request; the user unit's `execute` claims it, re-runs every check, types fixed templates,
verifies through the registry and the identity store, and rows every outcome. Everything runs against a fake world: a
scripted tmux, a fake /proc tree, a registry, an identity store, a transcript and the run records.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "rotate_session.py"
spec = importlib.util.spec_from_file_location("rotate_session", SCRIPT)
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)
_REAL_SLEEP = time.sleep  # captured before any test patches anything (W-1e0f4229)


class _RsTime:
    """rotate_session's OWN `time` (W-1e0f4229). A fake clock set on the global `time` module also drives
    subprocess.Popen._wait, which polls a child's exit with time.sleep: every fake-tmux call then moved the fake clock
    by however long the child took to exit — up to ~1,700 fake s for a 50 ms tail — so a timed test failed under load.
    Overrides live here; every other name is the real module's."""

    def __getattr__(self, name):
        return getattr(time, name)


def _rs_time(monkeypatch, **overrides) -> None:
    """Fake `time.<name>` for rotate_session only; repeated calls in one test add to the same proxy."""
    proxy = rs.time if isinstance(rs.time, _RsTime) else _RsTime()
    vars(proxy).update(overrides)
    monkeypatch.setattr(rs, "time", proxy)


SID = "11111111-1111-4111-8111-111111111111"
NEW = "22222222-2222-4222-8222-222222222222"
IDLE_SCREEN = (
    "some output\n────────────\n❯\u00a0\n────────────\n  Opus · ctx 41%\n  ⏵⏵ auto mode on\n"
)
FAKE_TMUX = """#!/usr/bin/env python3
import json, os, re, sys
st = json.load(open(os.environ["FAKE_TMUX_STATE"]))
a = sys.argv[1:]
if a[0] == "list-panes":
    print("\\n".join(st["panes"]))
elif a[0] == "respawn-pane":
    # W-e38f8ee7: logged; `on_respawn` plays what the respawned pane does (the old claude exits, the new one registers)
    with open(os.environ["FAKE_TMUX_STATE"] + ".respawn", "a") as fh:
        fh.write(json.dumps(a[1:]) + "\\n")
    if st.get("on_respawn"):
        exec(st["on_respawn"], {"a": a, "os": os, "json": json, "re": re})
elif a[0] == "capture-pane":
    # the input line, as Claude Code renders a paste (W-b92aa5cf): `stream` shows the head first, `pre_placeholder`
    # shows the fresh box's hint for two captures first; each capture showing the full text counts toward the settle
    st["caps"] = st.get("caps", 0) + 1
    if st.get("drift_at") and st["caps"] >= st["drift_at"]:  # someone types in the pane meanwhile (W-ee19169d)
        st["screen"] = st["screen"].replace("❯ go on", "❯ go on, and also", 1)
    if st.get("empty_at") and st["caps"] >= st["empty_at"]:  # the box was cleared by hand meanwhile (r2)
        st["screen"], st["stuck"] = st["idle"], False
    if st.get("blank_at") and st["caps"] == st["blank_at"]:  # one redraw frame with no box drawn (W-ee19169d r1)
        json.dump(st, open(os.environ["FAKE_TMUX_STATE"], "w"))
        sys.stdout.write("redrawing\\n")
        sys.exit(0)
    full = st.get("pending")
    if full is not None:
        caps = st["caps"]
        shown = full
        if st.get("stream") and caps == 1:
            shown = full[:30]
        if st.get("pre_placeholder") and caps <= 2:
            shown = 'Try "x"'
        st["full_seen"] = st.get("full_seen", 0) + (shown == full)
        st["screen"] = "\\n".join(
            "❯ " + shown if ln.startswith("❯") else ln for ln in st["screen"].split("\\n"))
    json.dump(st, open(os.environ["FAKE_TMUX_STATE"], "w"))
    sys.stdout.write(st["screen"] + ("  clock %d\\n" % st["caps"] if st.get("tick") else ""))
elif a[0] == "send-keys":
    with open(os.environ["FAKE_TMUX_STATE"] + ".keys", "a") as fh:
        fh.write(json.dumps(a[1:]) + "\\n")
    hook = st.get("on_send")
    if hook and "-l" in a:
        exec(hook, {"text": a[-1], "os": os, "json": json})
    st = json.load(open(os.environ["FAKE_TMUX_STATE"]))  # the hook may have rewritten the state
    # a C-m is swallowed until two captures showed the full paste — the paste is still settling (the incident's race:
    # a C-m right behind the paste); after that it submits, leaving an empty box or a placeholder
    if "-l" in a:
        st["caps"], st["full_seen"] = 0, 0
        st["pending"] = None if st.get("no_echo") else a[-1][:60]
    elif a[-1] in ("C-m", "Enter") and st.get("full_seen", 0) >= 2 and not st.get("swallow_submit"):
        st["pending"] = None
        box = "❯ Try \\"refactor this\\"" if st.get("placeholder") else "❯\\u00a0"
        st["screen"] = "\\n".join(box if ln.startswith("❯") else ln for ln in st["screen"].split("\\n"))
    # W-ee19169d, as measured on a live Claude Code: a FAST double Escape clears a non-empty box; on an empty box it
    # opens the Rewind menu, which one Escape closes
    if a[-2:] == ["Escape", "Escape"]:
        if st.get("esc_rewind") or not st.get("stuck"):
            st["screen"], st["rewind"] = "Rewind\\nNothing to rewind to yet.\\nEsc to cancel\\n", True
        elif not st.get("esc_noop"):
            st["screen"], st["stuck"] = st["idle"], False
    elif a[-1] == "Escape" and st.get("rewind"):
        st["screen"], st["rewind"] = st["idle"], False
    if a[-1] == "C-m" and st.get("fail_cm"):
        json.dump(st, open(os.environ["FAKE_TMUX_STATE"], "w"))
        sys.exit(1)
    json.dump(st, open(os.environ["FAKE_TMUX_STATE"], "w"))
sys.exit(st.get("rc", 0))
"""


def _proc_entry(
    proc: Path, pid: int, name: str, ppid: int, start: int = 777, env: dict | None = None
) -> None:
    d = proc / str(pid)
    d.mkdir(parents=True)
    (d / "status").write_text(f"Name:\t{name}\nPPid:\t{ppid}\n")
    fields = ["S", str(ppid)] + ["0"] * 17 + [str(start)]
    (d / "stat").write_text(f"{pid} ({name}) " + " ".join(fields) + "\n")
    (d / "comm").write_text(name + "\n")
    (d / "environ").write_bytes(b"\0".join(f"{k}={v}".encode() for k, v in (env or {}).items()))


@pytest.fixture
def world(tmp_path, monkeypatch):
    home, proc = tmp_path / "home", tmp_path / "proc"
    config = home / ".claude-fleet" / "active"
    (config / "sessions").mkdir(parents=True)
    _proc_entry(proc, 100, "bash", 1)
    _proc_entry(proc, 101, "bash", 100)
    _proc_entry(proc, 102, "claude", 101, env={"CLAUDE_CONFIG_DIR": str(config)})
    reg = {
        "pid": 102,
        "sessionId": SID,
        "procStart": "777",
        "cwd": str(tmp_path / "wt"),
        "status": "idle",
        "statusUpdatedAt": (time.time() - 120) * 1000,
        "entrypoint": "cli",
    }
    (config / "sessions" / "102.json").write_text(json.dumps(reg))
    transcript = config / "projects" / "-opt-x" / f"{SID}.jsonl"
    transcript.parent.mkdir(parents=True)
    rows = [
        {
            "type": "assistant",
            "timestamp": "2026-10-23T00:00:00Z",
            "message": {"model": "m", "usage": {"cache_read_input_tokens": 450000}},
        },
        {"type": "system", "subtype": "turn_duration", "timestamp": "2026-10-23T00:00:01Z"},
    ]
    transcript.write_text("".join(json.dumps(r) + "\n" for r in rows))
    identity = home / ".claude" / "state" / "agent-identity.jsonl"
    identity.parent.mkdir(parents=True)
    identity.write_text(
        json.dumps({"session_id": SID, "name": "dev1", "pid": 102, "toplevel": "/opt/x", "at": 1})
        + "\n"
    )
    state = tmp_path / "tmux.json"
    state.write_text(
        json.dumps(
            {
                "panes": ["%5\tx\tdev1\t100", "%5\tx-2\tdev1\t100", "%6\tx\tother\t200"],
                "screen": IDLE_SCREEN,
            }
        )
    )
    tmux = tmp_path / "tmux"
    tmux.write_text(FAKE_TMUX)
    tmux.chmod(0o755)
    for k, v in {
        "ROTATE_HOME": home,
        "ROTATE_PROC_ROOT": proc,
        "ROTATE_TMUX": tmux,
        "FAKE_TMUX_STATE": state,
        "ROTATE_REQUEST_DIR": tmp_path / "req",
        "ROTATIONS_LOG": tmp_path / "rotations.jsonl",
        "AGENT_IDENTITY_FILE": identity,
        "ROTATE_WAIT_S": "3",
    }.items():
        monkeypatch.setenv(k, str(v))
    monkeypatch.setattr(rs.hib, "worktree_state", lambda path: (False, "clean, pushed"))
    monkeypatch.setattr(rs.hib, "live_sessions", lambda home, proc, opt="/opt": [])
    _rs_time(monkeypatch, sleep=lambda s: None)
    # W-e38f8ee7: a --move reaps the old claude by pid; never let a test signal a real process
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(rs, "_signal", lambda pid, sig: signals.append((pid, sig)))
    monkeypatch.setattr(
        rs, "IDLE_S", 0
    )  # the fixture's transcript was just written; the quiet test sets 30 itself
    return {
        "home": home,
        "proc": proc,
        "config": config,
        "reg": reg,
        "transcript": transcript,
        "identity": identity,
        "state": state,
        "req": tmp_path / "req",
        "log": tmp_path / "rotations.jsonl",
        "tmp": tmp_path,
        "signals": signals,
    }


def _set(world, **kw):
    st = json.loads(world["state"].read_text())
    st.update(kw)
    world["state"].write_text(json.dumps(st))


def _rows(world):
    return (
        [json.loads(ln) for ln in world["log"].read_text().splitlines()]
        if world["log"].exists()
        else []
    )


def _keys(world):
    p = Path(str(world["state"]) + ".keys")
    return [json.loads(ln) for ln in p.read_text().splitlines()] if p.exists() else []


def test_resolve_pane_claude_and_session(world):
    t = rs.resolve("dev1", "/opt/x")
    assert (t["pane"], t["pid"], t["sid"]) == (
        "%5",
        102,
        SID,
    )  # grouped sessions deduped, claude found two levels down
    with pytest.raises(rs.CheckFailedError, match="0 panes"):
        rs.resolve("ghost", "/opt/x")
    _set(world, panes=["%5\tx\tdev1\t100", "%7\tx\tdev1\t100"])
    with pytest.raises(rs.CheckFailedError, match="2 panes"):
        rs.resolve("dev1", "/opt/x")
    _set(world, panes=["%5\tx\tdev1\t100"])
    with world["identity"].open(
        "a"
    ) as fh:  # a newer binding of dev1 in the same toplevel names another session
        fh.write(
            json.dumps({"session_id": NEW, "name": "dev1", "pid": 9, "toplevel": "/opt/x", "at": 2})
            + "\n"
        )
    with pytest.raises(rs.CheckFailedError, match="bound to another window"):
        rs.resolve("dev1", "/opt/x")


@pytest.mark.parametrize(
    "spoil, check, rc",  # W-05021a03: 75 = transient (clears by itself), 1 = permanent (an act first)
    [
        ("fresh", "status", 75),
        ("midturn", "idle", 75),
        ("slash", "idle", 1),
        ("record", "record", 75),
        ("seat", "seat", 75),
        ("worktree", "worktree", 1),
        ("typed", "screen", 1),
        ("dialog", "screen", 1),
    ],
)
def test_request_aborts_on_each_check_in_order(world, monkeypatch, capsys, spoil, check, rc):
    reg = dict(world["reg"])
    rows = world["transcript"].read_text()
    if spoil == "fresh":  # the transcript changed less than IDLE_S ago (it was just written)
        monkeypatch.setattr(rs, "IDLE_S", 30)
    elif spoil == "midturn":
        world["transcript"].write_text(
            rows + json.dumps({"type": "assistant", "timestamp": "2026-10-23T00:00:02Z"}) + "\n"
        )
    elif spoil == "slash":
        row = {
            "type": "user",
            "timestamp": "2026-10-23T00:00:02Z",
            "message": {"content": "<command-name>/cost</command-name>"},
        }
        world["transcript"].write_text(rows + json.dumps(row) + "\n")
    elif spoil == "record":
        rec = (
            rs.hib._runs_dir(world["home"]) / f"{SID}.json"
        )  # $COMMAND_RUN_DIR first, as the reader
        rec.parent.mkdir(parents=True, exist_ok=True)
        rec.write_text(json.dumps({"command": "fabrik-task", "state": "running"}))
    elif spoil == "seat":
        launch = {
            "type": "user",
            "timestamp": "2026-10-23T00:00:00Z",
            "toolUseResult": {"status": "async_launched", "agentId": "abc"},
        }
        world["transcript"].write_text(json.dumps(launch) + "\n" + rows)
    elif spoil == "worktree":
        monkeypatch.setattr(
            rs.hib, "worktree_state", lambda path: (True, "2 uncommitted change(s)")
        )
    elif spoil == "typed":
        _set(world, screen=IDLE_SCREEN.replace("❯\u00a0", "❯ half typed"))
    elif spoil == "dialog":
        _set(world, screen="Allow?\n❯ 1. Yes\n  2. No\n")
    (world["config"] / "sessions" / "102.json").write_text(json.dumps(reg))
    assert rs.request("dev1", "/opt/x", None, "manual") == rc
    assert not list(world["req"].glob("*.json"))
    assert _rows(world)[-1]["outcome"] == f"aborted:{check}", _rows(world)
    assert ("(transient" if rc == rs.EXIT_RETRY else "(permanent") in capsys.readouterr().err


def test_request_writes_data_only_and_one_at_a_time(world):
    assert rs.request("dev1", "/opt/x", None, "ctx") == 0
    files = list(world["req"].glob("*.json"))
    assert [f.name for f in files] == ["x--dev1.json"]
    data = json.loads(files[0].read_text())
    assert set(data) == rs.FIELDS and data["mode"] == "clear" and data["trigger"] == "ctx"
    assert data["ctx_pre"] == 450000 and data["window"] == 1_000_000 and data["sid"] == SID
    assert not any(
        "clear" in str(v) and "/" in str(v) for v in data.values() if isinstance(v, str)
    ), data  # no keys
    # one at a time; the pending abort is transient
    assert rs.request("dev1", "/opt/x", "finish the parser", "compact") == 75
    assert _rows(world)[-1]["outcome"] == "aborted:pending"
    files[0].unlink()
    assert rs.request("dev1", "/opt/x", "finish the parser", "compact") == 0
    assert json.loads(next(world["req"].glob("*.json")).read_text())["focus"] == "finish the parser"
    for bad in ("two\nlines", "", "x" * 301, "bell\x07"):
        next(world["req"].glob("*.json")).unlink() if list(world["req"].glob("*.json")) else None
        assert rs.request("dev1", "/opt/x", bad, "compact") == 1
    assert rs.request("dev1", "/opt/x", None, "bogus") == 1


def _write_request(world, **over):
    world["req"].mkdir(exist_ok=True)
    data = {
        "name": "dev1",
        "repo": "/opt/x",
        "pane": "%5",
        "pid": 102,
        "proc_start": "777",
        "sid": SID,
        "mode": "clear",
        "focus": "",
        "trigger": "manual",
        "created_at": time.time(),
        "ctx_pre": 450000,
        "window": 1_000_000,
        "mb_pre": 0,
        "last_compact_age_s": None,
    }
    data.update(over)
    (world["req"] / "x--dev1.json").write_text(json.dumps(data))


def test_execute_validates_rechecks_and_always_cleans_up(world):
    cases = [
        ({"keys": "rm -rf /"}, "refused:request"),  # an unknown field: the file never carries keys
        ({"focus": "a\nb", "mode": "compact"}, "refused:request"),
        ({"created_at": time.time() - 61}, "stale"),
        ({"pid": 999}, "refused:resolve"),
    ]
    for over, outcome in cases:
        _write_request(world, **over)
        if "keys" in over:
            p = world["req"] / "x--dev1.json"
            d = json.loads(p.read_text())
            d["keys"] = "rm -rf /"
            p.write_text(json.dumps(d))
        assert rs.execute() == 0
        assert _rows(world)[-1]["outcome"] == outcome, (over, _rows(world)[-1])
        assert not list(world["req"].glob("*.json")) and not list(world["req"].glob("*.claimed"))
    _write_request(world)
    _set(
        world, screen=IDLE_SCREEN.replace("❯\u00a0", "❯ typed")
    )  # the re-check runs before any key
    rs.execute()
    assert _rows(world)[-1]["outcome"] == "refused:screen" and _keys(world) == []
    (world["req"] / "orphan.claimed").write_text("{}")
    rs.execute()
    assert _rows(world)[-1]["outcome"] == "refused:orphan" and not list(
        world["req"].glob("*.claimed")
    )


def test_execute_rotates_and_records(world, monkeypatch):
    reg_path = world["config"] / "sessions" / "102.json"
    hook = (
        "p = os.environ['REG']\n"
        "if text.startswith('/clear'):\n"
        "    d = json.load(open(p)); d['sessionId'] = os.environ['NEW']; json.dump(d, open(p, 'w'))\n"
        "if text.startswith('You were rotated'):\n"
        "    open(os.environ['AGENT_IDENTITY_FILE'], 'a').write(json.dumps({'session_id': os.environ['NEW'], 'name': 'dev1',"
        " 'predecessor': os.environ['OLD']}) + '\\n')\n"
    )
    for k, v in {"REG": str(reg_path), "NEW": NEW, "OLD": SID}.items():
        monkeypatch.setenv(k, v)
    _set(world, on_send=hook)
    _write_request(world, trigger="ctx")
    rs.execute()
    row = _rows(world)[-1]
    assert (
        row["outcome"] == "ok"
        and row["new_sid"] == NEW
        and row["old_sid"] == SID
        and row["predecessor_row"] is True
    )
    # W-b72231b8 review r2: /opt/x is no checkout the old session's binding names, so nothing is written
    assert row["registry"] == "refused:repo", row
    assert row["trigger"] == "ctx" and row["ctx_pre"] == 450000
    keys = _keys(world)
    assert (
        keys[0][:4] == ["-t", "%5", "-l", "--"]
        and keys[0][4].startswith("/clear dev1-")
        and keys[1]
        == ["-t", "%5", "C-m"]  # W-b92aa5cf: its own call, after the paste settled — never "Enter"
    )
    assert keys[3] == ["-t", "%5", "C-m"] and all(k[-1] != "Enter" for k in keys)
    assert (
        keys[2][4].startswith("You were rotated")
        and "whoami_agent.py --as dev1 --force" in keys[2][4]
    )
    assert "selfwatch_arm.sh" in keys[2][4] and "never the previous transcript" in keys[2][4]


def test_execute_partials_are_recorded_never_retried(world, monkeypatch):
    _write_request(world)  # no hook: the session id never changes
    rs.execute()
    assert _rows(world)[-1]["outcome"] == "partial:queued"
    assert (
        len(_keys(world)) == 2
        and not list(world["req"].glob("*.json"))
        and not list(world["req"].glob("*.claimed"))
    )
    reg_path = world["config"] / "sessions" / "102.json"
    for k, v in {"REG": str(reg_path), "NEW": NEW}.items():
        monkeypatch.setenv(k, v)
    _set(
        world,
        on_send="p = os.environ['REG']\nif text.startswith('/clear'):\n    d = json.load(open(p)); d['sessionId'] = os.environ['NEW']; json.dump(d, open(p, 'w'))\n",
    )
    reg = json.loads(reg_path.read_text())
    reg["sessionId"] = SID
    reg_path.write_text(json.dumps(reg))
    _write_request(world)
    rs.execute()
    row = _rows(world)[-1]
    assert (
        row["outcome"] == "partial:rebind" and row["predecessor_row"] is False
    )  # the resume prompt was still sent
    assert any(k[-1].startswith("You were rotated") for k in _keys(world))


def test_seat_reader_parity_and_agents_up_dispatch(world, tmp_path):
    t = world["transcript"]
    launch = {
        "type": "user",
        "timestamp": "x",
        "toolUseResult": {"status": "async_launched", "agentId": "a1"},
    }
    wf = {
        "type": "user",
        "timestamp": "x",
        "toolUseResult": {"status": "async_launched", "taskId": "w1", "taskType": "local_workflow"},
    }
    bash = {
        "type": "user",
        "timestamp": "x",
        "toolUseResult": {"status": "async_launched", "taskId": "b1", "taskType": "local_bash"},
    }
    done_q = {
        "type": "queue-operation",
        "operation": "enqueue",
        "content": "<task-notification><task-id>a1</task-id><status>completed</status></task-notification>",
    }
    quoted = {
        "type": "assistant",
        "message": {
            "content": "<task-notification><task-id>w1</task-id><status>completed</status>"
        },
    }
    t.write_text("".join(json.dumps(r) + "\n" for r in (launch, wf, bash, quoted)))
    assert rs.seats_running(t) == {
        "a1",
        "w1",
    }  # a background Bash is no seat; a quoted notice closes nothing
    t.write_text("".join(json.dumps(r) + "\n" for r in (launch, wf, done_q)))
    assert rs.seats_running(t) == {"w1"}
    att = {
        "type": "attachment",
        "attachment": {
            "commandMode": "task-notification",
            "prompt": "<task-id>w1</task-id> <status>failed</status>",
        },
    }
    t.write_text("".join(json.dumps(r) + "\n" for r in (wf, att)))
    assert rs.seats_running(t) == set()
    t.unlink()
    with pytest.raises(OSError):
        rs.seats_running(t)
    # agents_up.sh rotate-session dispatches to `request` before its own argument parsing
    fake_py = tmp_path / "bin"
    fake_py.mkdir()
    (fake_py / "python3").write_text('#!/bin/sh\necho "ARGS $*"\n')
    (fake_py / "python3").chmod(0o755)
    out = subprocess.run(
        [
            "bash",
            str(REPO / "scripts" / "sysadmin" / "agents_up.sh"),
            "rotate-session",
            "dev1",
            "--compact",
            "f",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{fake_py}:/usr/bin:/bin", "HOME": str(tmp_path)},
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().endswith("rotate_session.py request dev1 --compact f"), out.stdout


def test_review_round_one_failures_are_rowed_never_crash(world, monkeypatch):
    """Round 1 of the W-f975fee0 slice-2 review: each case below crashed execute or lost a row."""
    for over in (
        {"name": 5},
        {"repo": 5},
        {"pid": True},
        {"created_at": float("inf")},
        {"created_at": "now"},
        {"created_at": time.time() + 3600},
    ):
        _write_request(world, **over)
        assert rs.execute() == 0
        assert _rows(world)[-1]["outcome"] == "refused:request", (over, _rows(world)[-1])
        assert not list(world["req"].glob("*.json")) and not list(world["req"].glob("*.claimed"))

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("tmux", 10)

    _write_request(world)
    real_tmux = rs._tmux
    monkeypatch.setattr(rs, "_tmux", boom)
    rs.execute()
    assert _rows(world)[-1]["outcome"] == "refused:error"
    monkeypatch.setattr(
        rs, "_tmux", real_tmux
    )  # never monkeypatch.undo(): it would drop the fixture's sandbox env
    # a dangling symlink and an unclaimable file are removed and rowed, and the valid request beside them still runs
    world["req"].mkdir(exist_ok=True)
    (world["req"] / "a--dead.json").symlink_to(world["tmp"] / "nowhere")
    _write_request(world)
    rs.execute()
    outcomes = [r["outcome"] for r in _rows(world)[-2:]]
    assert "refused:claim" in outcomes and not list(world["req"].glob("*.json")), outcomes
    # a lone stale .claimed (an execute killed mid-run) no longer blocks request forever
    stray = world["req"] / "x--dev1.claimed"
    stray.write_text("{}")
    old = time.time() - 2 * rs.ORPHAN_S
    os.utime(stray, (old, old))
    assert rs.request("dev1", "/opt/x", None, "manual") == 0
    assert any(r["outcome"] == "refused:orphan" for r in _rows(world))
    # a log that cannot be written never aborts the run
    next(world["req"].glob("*.json")).unlink()
    monkeypatch.setenv("ROTATIONS_LOG", str(world["tmp"]))  # a directory
    _write_request(world, created_at=time.time() + 3600)
    assert rs.execute() == 0
    monkeypatch.setenv("ROTATE_WAIT_S", "inf")
    assert rs._wait_s(60) == 60


def test_compact_execute_and_untimed_rows_and_user_notification(world, monkeypatch):
    t = world["transcript"]
    base = t.read_text()
    t.write_text(
        base
        + json.dumps({"type": "last-prompt"})
        + "\n"
        + json.dumps(
            {"type": "system", "subtype": "away_summary", "timestamp": "2026-10-23T00:00:05Z"}
        )
        + "\n"
    )
    rs.run_checks(
        rs.resolve("dev1", "/opt/x")
    )  # untimed and away_summary rows after the turn end are idle
    hook = (
        "import time\nif text.startswith('/compact'):\n    open(os.environ['TR'], 'a').write(json.dumps("
        "{'type': 'system', 'subtype': 'compact_boundary', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + 2))}) + '\\n')\n"
    )
    monkeypatch.setenv("TR", str(t))
    _set(world, on_send=hook)
    _write_request(world, mode="compact", focus="finish the parser", trigger="compact")
    rs.execute()
    assert _rows(world)[-1]["outcome"] == "ok", _rows(world)[-1]
    assert _keys(world)[0][-1] == "/compact finish the parser"
    _set(world, on_send="")
    t.write_text(base)  # a fresh turn end: the first compact left its boundary row last
    _write_request(world, mode="compact", focus="x", trigger="compact")
    rs.execute()
    assert _rows(world)[-1]["outcome"] == "partial:queued"
    launch = {
        "type": "user",
        "timestamp": "x",
        "toolUseResult": {"status": "async_launched", "agentId": "a9"},
    }
    note = {
        "type": "user",
        "origin": {"kind": "task-notification"},
        "message": {"content": "<task-id>a9</task-id><status>completed</status>"},
    }
    t.write_text("".join(json.dumps(r) + "\n" for r in (launch, note)))
    assert rs.seats_running(t) == set()


def test_review_round_two_a_stale_tmp_and_a_json_directory_never_wedge(world):
    """Round 2: a `.tmp` left by a killed request blocked every later request; a directory named `*.json` re-fired the unit."""
    world["req"].mkdir(exist_ok=True)
    tmp = world["req"] / ".x--dev1.tmp"
    tmp.write_text("{}")
    old = time.time() - 2 * rs.STALE_S
    os.utime(tmp, (old, old))
    assert rs.request("dev1", "/opt/x", None, "manual") == 0
    assert not tmp.exists() and any(r["outcome"] == "refused:orphan" for r in _rows(world))
    next(world["req"].glob("*.json")).unlink()
    for _ in range(
        2
    ):  # round 3: a second directory of the same name, an earlier one already moved aside
        (world["req"] / "evil.json").mkdir()
        (world["req"] / "evil.json" / "inner").write_text("x")
        assert rs.execute() == 0
        assert (
            not list(world["req"].glob("*.json")) and _rows(world)[-1]["outcome"] == "refused:claim"
        )


def test_w477d751a_hardlinked_transcript_names_are_one(world):
    """W-477d751a: a worktree builder's transcript has two hard-linked names (one inode), and the name count refused
    every such rotation; a dangling name or a distinct second file still refuses."""
    other = world["config"] / "projects" / "-opt-x--claude-worktrees-dev1"
    other.mkdir()
    os.link(world["transcript"], other / f"{SID}.jsonl")
    assert rs._transcript(world["proc"], world["home"], 102, SID) == world["transcript"]
    assert rs.request("dev1", "/opt/x", None, "manual") == 0, _rows(world)
    (other / f"{SID}.jsonl").unlink()
    (other / f"{SID}.jsonl").symlink_to(world["tmp"] / "nowhere")
    with pytest.raises(rs.CheckFailedError, match="unreadable"):
        rs._transcript(world["proc"], world["home"], 102, SID)
    (other / f"{SID}.jsonl").unlink()
    (other / f"{SID}.jsonl").write_text(world["transcript"].read_text())
    with pytest.raises(rs.CheckFailedError, match="2 transcripts"):
        rs._transcript(world["proc"], world["home"], 102, SID)


def test_w477d751a_a_stale_busy_registry_never_blocks_a_quiet_turn_end(world, monkeypatch):
    """W-477d751a: the registry's status did not track turns (infra-2 ended 13 turns after its record last read busy),
    so check 0 is the transcript's quiet time: a turn end 30 s quiet passes whatever the registry says."""
    monkeypatch.setattr(rs, "IDLE_S", 30)
    old = time.time() - 60
    os.utime(world["transcript"], (old, old))
    turn_end = rs._ts(
        "2026-10-23T00:00:01Z"
    )  # the fixture transcript's turn end; the record is older than it
    reg = dict(world["reg"], status="busy", statusUpdatedAt=(turn_end - 60) * 1000)
    (world["config"] / "sessions" / "102.json").write_text(json.dumps(reg))
    assert rs.request("dev1", "/opt/x", None, "manual") == 0, _rows(world)


def test_w477d751a_production_quiet_time_and_executes_recheck(world, monkeypatch):
    """The module's own IDLE_S is 30 (the fixture zeroes it); execute re-runs the quiet check; an unstat-able
    transcript after resolution fails closed, never open."""
    fresh = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("rotate_session_fresh", SCRIPT)
    )
    fresh.__spec__.loader.exec_module(fresh)
    assert fresh.IDLE_S == 30
    assert rs.request("dev1", "/opt/x", None, "manual") == 0
    monkeypatch.setattr(
        rs, "IDLE_S", 30
    )  # the transcript was written moments ago: execute must refuse to type
    rs.execute()
    assert _rows(world)[-1]["outcome"] == "refused:status" and not _keys(world), _rows(world)
    real_stat = Path.stat

    def flaky(self, *a, **k):
        if self == world["transcript"] and flaky.calls:
            raise PermissionError("gone")
        flaky.calls += self == world["transcript"]
        return real_stat(self, *a, **k)

    flaky.calls = 0
    monkeypatch.setattr(Path, "stat", flaky)
    t = rs.resolve("dev1", "/opt/x")
    with pytest.raises(rs.CheckFailedError, match="status"):
        rs.run_checks(t)


def test_w477d751a_resume_metadata_rows_and_the_registry_veto(world):
    """A resume writes pr-link / frame-link / system informational rows after the turn end: still idle. The registry
    vetoes only when it changed AFTER the last turn end (a turn started since); shell, idle or no time never veto."""
    base = world["transcript"].read_text()
    extra = [
        {"type": "pr-link", "timestamp": "2026-10-23T00:00:05Z"},
        {"type": "frame-link", "timestamp": "2026-10-23T00:00:06Z"},
        {"type": "system", "subtype": "informational", "timestamp": "2026-10-23T00:00:07Z"},
    ]
    world["transcript"].write_text(base + "".join(json.dumps(r) + "\n" for r in extra))
    t = rs.resolve("dev1", "/opt/x")
    assert rs.run_checks(t) == world["transcript"]
    turn_end = rs._ts("2026-10-23T00:00:01Z")
    recent = time.time() - 60  # a flip one minute ago, after the turn end: a turn started since
    for reg_over, vetoed in (
        ({"status": "busy", "statusUpdatedAt": recent * 1000}, True),
        (
            {"status": "busy", "statusUpdatedAt": (turn_end + 5) * 1000},
            False,
        ),  # past VETO_S: expired
        ({"status": "busy", "statusUpdatedAt": True}, False),  # a bool is no time
        ({"status": "busy", "statusUpdatedAt": (turn_end - 5) * 1000}, False),
        ({"status": "shell", "statusUpdatedAt": (turn_end + 5) * 1000}, False),
        ({"status": "busy", "statusUpdatedAt": None}, False),
    ):
        t = dict(t, reg=dict(world["reg"], **reg_over))
        if vetoed:
            with pytest.raises(rs.CheckFailedError, match="after the last turn end"):
                rs.run_checks(t)
        else:
            assert rs.run_checks(t) == world["transcript"], reg_over


def test_w477d751a_an_unreadable_turn_end_time_refuses(world):
    """A turn end whose timestamp `_ts` cannot read is refused as such, never compared as 0."""
    for bad in ("garbage", 1792727000):
        rows = [{"type": "system", "subtype": "turn_duration", "timestamp": bad}]
        with pytest.raises(rs.CheckFailedError, match="no readable time"):
            rs._idle_row_check(rows)


# ── slice 3 (W-f975fee0): `due`, the lift offer, the nightly mail, the private request dir ──────────────────────────


def _hermetic(monkeypatch, tmp_path):
    monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(tmp_path / "no-hub.env"))
    monkeypatch.delenv("ROTATE_ADVISE_MB", raising=False)
    monkeypatch.delenv("ROTATE_CONTEXT_WINDOW", raising=False)


def _session(agent, entrypoint="cli", sid=SID, repo="/opt/x", pid=102):
    return {
        "pid": pid,
        "ppid": 1,
        "sid": sid,
        "cwd": repo,
        "peer": agent,
        "entrypoint": entrypoint,
        "agent": agent,
        "repo": repo,
    }


def test_due_rows_and_actions(world, monkeypatch):
    _hermetic(monkeypatch, world["tmp"])
    sessions = [
        _session("dev1"),
        _session("coordinator", "claude-vscode"),
        _session("seat", "sdk-cli"),
        _session(""),
        _session("dev2", sid=NEW),
        _session(
            "", sid="a\ud800b", repo="/opt/\ud800"
        ),  # review B1: a lone surrogate from registry JSON
        _session("x\ud800"),  # review C1 (r2): the agent field too, past the line and nameless
    ]
    monkeypatch.setattr(rs.hib, "live_sessions", lambda home, proc, opt="/opt": sessions)
    rows = rs.due(world["home"], world["proc"])
    by = {r["agent"]: r for r in rows}
    assert set(by) == {"dev1", "coordinator", "", "dev2", "x\ud800"}, (
        rows
    )  # the pool seat is never a row
    assert all(rs._line(r).encode("utf-8") for r in rows)  # every row prints and mails as UTF-8
    assert (by["dev1"]["state"], by["dev1"]["trigger"], by["dev1"]["ctx"]) == ("due", "ctx", 45)
    assert (
        rs.offer(by["dev1"])
        == "/opt/fabrik/scripts/sysadmin/agents_up.sh rotate-session dev1 --repo /opt/x --trigger ctx"
    )
    assert "operator types `/clear coordinator-" in rs.offer(by["coordinator"])
    nameless = next(r for r in rows if r["agent"] == "" and r["sid"] == SID)
    assert nameless["state"] == "unread" and "agent" in nameless["reason"]
    assert by["dev2"]["state"] == "unread" and "0 transcripts" in by["dev2"]["reason"]
    odd = [r for r in rows if "ud800" in str(r["sid"])]
    assert len(odd) == 1 and rs._line(odd[0]).encode("utf-8") and odd[0]["repo"].encode("utf-8")
    # --mb-only reads no context: a 45% session under the MB line is not due
    monkeypatch.setattr(
        rs.tsc, "_context_tokens", lambda p: (_ for _ in ()).throw(AssertionError("ctx read"))
    )
    assert {r["agent"] for r in rs.due(world["home"], world["proc"], mb_only=True)} == {"", "dev2"}
    monkeypatch.setenv(
        "ROTATE_ADVISE_MB", "1"
    )  # the hook's own threshold reader decides the MB line
    with world["transcript"].open("a") as fh:
        fh.write(json.dumps({"type": "pad", "x": "y" * (1024 * 1024)}) + "\n")
    mb = {r["agent"]: r for r in rs.due(world["home"], world["proc"], mb_only=True)}
    assert (mb["dev1"]["state"], mb["dev1"]["trigger"], mb["dev1"]["ctx"]) == ("due", "mb", None)


def test_due_mail_per_repo(world, monkeypatch):
    root = Path(
        os.environ["FABRIK_MAIL_ROOT"]
    )  # conftest's tmp mail root: nothing reaches a live mailbox
    rows = [
        dict(_session("fleet", repo="/opt/fabrik"), state="due", trigger="mb", mb=210, ctx=None),
        dict(
            _session("coordinator", "claude-vscode", repo="/opt/fabrik"),
            state="due",
            trigger="mb",
            mb=425,
            ctx=None,
        ),
        dict(
            _session("dev1", repo="/opt/fabrik-lib"),
            state="unread",
            reason="transcript: 0 transcripts",
        ),
        dict(_session("x", repo=""), state="due", trigger="mb", mb=300, ctx=None),
    ]
    assert rs.mail_due([]) == 0 and not list(root.glob("*/inbox/*.md"))
    assert rs.mail_due(rows) == 0
    hub = list((root / "fabrik" / "inbox").glob("*.md"))
    lib = list((root / "fabrik-lib" / "inbox").glob("*.md"))
    assert len(hub) == 1 and len(lib) == 1, (hub, lib)
    text = hub[0].read_text()
    assert "agent: coordinator" in text and "ack: no" in text and "rotate-session fleet" in text
    assert "operator types" in text and "never typed for you" in text
    assert "unread" in lib[0].read_text()
    bad = [
        dict(
            _session("y", repo="/opt/no-such-repo-zz"), state="due", trigger="mb", mb=300, ctx=None
        )
    ] + rows[:1]
    assert rs.mail_due(bad) == 1  # the refused repo fails the run, after the hub was still tried
    assert len(list((root / "fabrik" / "inbox").glob("*.md"))) == 2


def test_request_dir_is_private(world):
    d = world["req"]
    rs.request("dev1", "/opt/x", None, "manual")
    assert d.is_dir() and (d.stat().st_mode & 0o777) == 0o700
    d.chmod(0o755)
    rs.execute()
    assert (d.stat().st_mode & 0o777) == 0o700
    for f in d.iterdir():
        f.unlink() if f.is_file() else None
    d.rmdir()
    real = world["tmp"] / "elsewhere"
    real.mkdir()
    d.symlink_to(real)
    assert rs.request("dev1", "/opt/x", None, "manual") == 1
    assert _rows(world)[-1]["outcome"] == "aborted:request"
    assert rs.execute() == 1


def test_units_nightly_line_and_no_makedirectory():
    svc = (REPO / "scripts" / "sysadmin" / "systemd" / "session-archive.service").read_text()
    starts = [ln for ln in svc.splitlines() if ln.startswith("ExecStart=")]
    assert starts[-1] == (
        "ExecStart=-/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sysadmin/rotate_session.py "
        "due --mb-only --mail"
    )
    assert "prune_transcripts.py" in starts[-2]
    path = (REPO / "scripts" / "sysadmin" / "fabrik-rotate.path").read_text()
    assert "MakeDirectory" not in path and "DirectoryMode" not in path
    assert (
        "install -d -m 0700"
        in (REPO / "scripts" / "sysadmin" / "install_rotate_unit.sh").read_text()
    )


def test_installer_refuses_a_symlinked_request_dir(tmp_path):
    """Review B2: `install -d` follows a symlink and chmods its target; the installer refuses one before installing."""
    home = tmp_path / "home"
    (home / ".claude" / "state").mkdir(parents=True)
    target = tmp_path / "elsewhere"
    target.mkdir()
    target.chmod(0o755)
    (home / ".claude" / "state" / "rotate-requests").symlink_to(target)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(home), "XDG_CONFIG_HOME": str(tmp_path / "cfg")}
    out = subprocess.run(
        ["bash", str(REPO / "scripts" / "sysadmin" / "install_rotate_unit.sh")],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert out.returncode == 1 and "not a plain directory" in out.stderr, (out.stdout, out.stderr)
    assert (target.stat().st_mode & 0o777) == 0o755 and not (tmp_path / "cfg").exists()


def test_review_round_one_slice_a(world, monkeypatch):
    """Review A1-A7: the ctx line is inclusive at 40 and exclusive at 39; an infinite MB setting falls back to the
    default; a nameless session under the line is no row; a repo-less row offers no broken command; a foreign-uid
    request dir refuses in request AND execute (rowed); a failed body file fails that repo only."""
    _hermetic(monkeypatch, world["tmp"])
    sessions = [_session("dev1"), _session("")]
    monkeypatch.setattr(rs.hib, "live_sessions", lambda home, proc, opt="/opt": sessions)
    for tokens, want in ((400_000, {"dev1", ""}), (399_999, set())):
        monkeypatch.setattr(rs.tsc, "_context_tokens", lambda p, t=tokens: t)
        rows = rs.due(world["home"], world["proc"])
        assert {r["agent"] for r in rows} == want, (tokens, rows)
    monkeypatch.setenv("ROTATE_ADVISE_MB", "inf")
    assert rs.tsc._threshold_mb() == rs.tsc.DEFAULT_THRESHOLD_MB
    assert rs.due(world["home"], world["proc"]) == []
    assert "--repo" not in rs.offer(dict(_session("dev1", repo=""), state="due", trigger="mb"))
    with monkeypatch.context() as m:
        m.setattr(rs.os, "getuid", lambda: 4_000_000)
        assert rs.request("dev1", "/opt/x", None, "manual") == 1
        last = _rows(world)[-1]
        assert last["outcome"] == "aborted:request" and "owned by uid" in last["reason"], last
        assert rs.execute() == 1 and _rows(world)[-1]["outcome"] == "refused:request"
    root = Path(os.environ["FABRIK_MAIL_ROOT"])
    real, calls = rs.tempfile.NamedTemporaryFile, []

    def flaky(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("no space left")
        return real(*a, **k)

    monkeypatch.setattr(rs.tempfile, "NamedTemporaryFile", flaky)
    rows = [  # repos are sent sorted: /opt/fabrik first (its body file fails), then /opt/fabrik-lib
        dict(_session("a", repo="/opt/fabrik-lib"), state="due", trigger="mb", mb=300, ctx=None),
        dict(_session("b", repo="/opt/fabrik"), state="due", trigger="mb", mb=300, ctx=None),
    ]

    def count(box):
        return len(list((root / box / "inbox").glob("*.md")))

    hub0, lib0 = count("fabrik"), count("fabrik-lib")
    assert rs.mail_due(rows) == 1
    assert (count("fabrik"), count("fabrik-lib")) == (hub0, lib0 + 1)


def test_w_b92aa5cf_a_swallowed_submit_is_rowed_typed_unsent(world):
    """W-b92aa5cf: the resume prompt sat unsent in every rotated pane. A paste that never shows, or a C-m the pane
    swallows, is rowed `typed-unsent:<step>` and nothing is retried; a submitted one leaves the input line empty."""
    for flag, enters in (("swallow_submit", 1), ("no_echo", 0)):
        _set(world, **{flag: True, "screen": IDLE_SCREEN, "pending": None})
        _write_request(world, trigger="ctx")
        rs.execute()
        row = _rows(world)[-1]
        assert row["outcome"] == "typed-unsent:send", (flag, row)
        assert sum(k[-1] == "C-m" for k in _keys(world)) == enters, _keys(world)
        Path(str(world["state"]) + ".keys").unlink()
        _set(world, **{flag: False})


def test_w_b92aa5cf_review_r1_settle_on_the_input_line_and_map_only_unsent(world):
    """Review r1: a status line ticking every capture must not stall the settle (it reads the input line only); a
    placeholder the fresh box shows after /clear is a submit, not unsent text; a refused C-m is `partial:send`, never
    `typed-unsent`. Past the send, no new session id appears in this fixture, so a submitted /clear rows
    `partial:queued`."""
    for flags, want in (
        ({"tick": True}, "partial:queued"),
        ({"placeholder": True}, "partial:queued"),
        ({"fail_cm": True}, "partial:send"),
        (
            {"stream": True},
            "partial:queued",
        ),  # review r2: C-m waits for two captures of the FULL text
        (
            {"pre_placeholder": True},
            "partial:queued",
        ),  # review r2: a hint before the echo is not the paste
    ):
        _set(world, screen=IDLE_SCREEN, pending=None, **flags)
        _write_request(world, trigger="ctx")
        rs.execute()
        assert _rows(world)[-1]["outcome"] == want, (flags, _rows(world)[-1])
        if (
            want == "partial:queued"
        ):  # the pane actually TOOK the submit — not a later echo mistaken for one
            assert json.loads(world["state"].read_text())["pending"] is None, flags
        _set(world, **dict.fromkeys(flags, False))


# ── W-ee19169d: --stale-input discard, and check 5 reading the whole input box ─────────────────────────────────────

RULE = "────────────"
STATUS = "  Opus · ctx 41%\n  ⏵⏵ auto mode on\n"


def _boxed(*rows: str) -> str:
    return f"some output\n{RULE}\n" + "\n".join(rows) + f"\n{RULE}\n{STATUS}"


def _stuck(world, text: str = "go on", **more) -> None:
    _set(world, screen=_boxed(f"❯ {text}"), idle=IDLE_SCREEN, stuck=True, pending=None, **more)


def test_w_ee19169d_check_5_reads_the_whole_box(world):
    """A second row under an empty ❯ row, or a typed row, refuses; the dim placeholder of a fresh box is empty."""
    assert rs._box(IDLE_SCREEN) == ""
    assert rs._box(_boxed('❯ \x1b[2mTry "how do I log an error?"\x1b[0m')) == ""
    assert (
        rs._box(_boxed("❯ first line of a", "  wrapped input")) == "first line of a wrapped input"
    )
    assert rs._box(_boxed("❯ ", "  second line here")) == "second line here"
    assert rs._box("no prompt here\n") is None and rs._box("❯ go on\n") is None  # no framed box
    for screen in (_boxed("❯ ", "  second line here"), _boxed("❯ go on")):
        _set(world, screen=screen)
        assert rs.request("dev1", "/opt/x", None, "manual") == 1
        assert _rows(world)[-1]["outcome"] == "aborted:screen", screen
    _set(world, screen=_boxed('❯ \x1b[2mTry "x"\x1b[0m'))
    assert rs.request("dev1", "/opt/x", None, "manual") == 0


def test_w_ee19169d_discard_clears_the_seen_text_then_rotates(world):
    """The words are required both ways; the box text rides the request; the unit sends ONE fast double Escape, then
    the normal rotation, and the row keeps the discarded text."""
    _stuck(world)
    for stale, words in ((True, ""), (False, "operator: drop it")):
        assert rs.request("dev1", "/opt/x", None, "manual", stale, words) == 1
        assert _rows(world)[-1]["outcome"] == "aborted:args"
    assert rs.request("dev1", "/opt/x", None, "manual", True, "operator 17:50: clear them") == 0
    req = json.loads(next(world["req"].glob("*.json")).read_text())
    assert (req["stale_text"], req["operator_ok"]) == ("go on", "operator 17:50: clear them")
    rs.execute()
    row = _rows(world)[-1]
    assert row["outcome"] == "partial:queued" and row["stale_text"] == "go on", (
        row
    )  # no new sid here
    keys = _keys(world)
    esc = keys.index(["-t", "%5", "Escape", "Escape"])
    assert esc < next(i for i, k in enumerate(keys) if "-l" in k)  # cleared BEFORE the /clear


def test_w_ee19169d_discard_refuses_a_changed_box_or_a_rewind(world):
    """A box that changed since the request types nothing; a Rewind menu is closed and refused; text left after the
    double Escape is refused — and no /clear follows any of them."""
    for case in ("changed", "typing", "rewind", "noop"):
        Path(str(world["state"]) + ".keys").unlink(missing_ok=True)
        _stuck(world, esc_rewind=case == "rewind", esc_noop=case == "noop", rewind=False)
        _set(world, drift_at=0)
        assert rs.request("dev1", "/opt/x", None, "manual", True, "operator: clear") == 0
        if case == "changed":
            _set(world, screen=_boxed("❯ go on, and also"))
        if (
            case == "typing"
        ):  # execute's captures: check 5, the pre-discard read, then the discard's own three
            _set(world, caps=0, drift_at=3)
        rs.execute()
        row = _rows(world)[-1]
        # a box that changed is refused at the re-check (check 5) before any key; the others at the discard itself
        want = "refused:screen" if case == "changed" else "refused:stale-input"
        assert row["outcome"] == want and row["stale_text"] == "go on", (case, row)
        keys = _keys(world)
        assert not any("-l" in k for k in keys), (case, keys)
        if case in ("changed", "typing"):
            assert keys == [], (case, keys)  # nothing typed into a box someone is still writing in
        if case == "rewind":
            assert keys[-1] == ["-t", "%5", "Escape"]


def test_w_ee19169d_review_r1_sgr_walk_rule_above_and_the_pre_key_rechecks(world, monkeypatch):
    """Review r1: dim ends only on 0/22/empty (a combined `0;7m` cursor ends it, `2;3m` starts it); OSC links are
    stripped; a `❯` row needs a rule directly above; the box is read twice 2 s apart and every check re-runs right
    before the key; a box emptied meanwhile rotates without a key; a blank frame at the decision refuses; both 1000-
    character caps and bad operator words refuse."""
    assert rs._box(_boxed("❯ \x1b[2mTry\x1b[0;7mT\x1b[0m typed")) == "T typed"
    assert rs._box(_boxed('❯ \x1b[2;3mTry "x"\x1b[0m')) == ""
    assert rs._box(_boxed("❯ \x1b[2mTry\x1b[22m real")) == "real"
    assert rs._box(_boxed("❯ \x1b]8;;file:///x\x1b\\go on\x1b]8;;\x1b\\")) == "go on"
    assert rs._box(_boxed("❯ a", "  ❯ quoted")) == "a ❯ quoted"
    assert rs._box(f"❯ go on\n{RULE}\n") is None
    sleeps: list[float] = []
    _rs_time(monkeypatch, sleep=lambda s: sleeps.append(s))
    # execute's captures: check 5 (1), the pre-discard read (2), the discard's two reads (3, 4), run_checks again (5)
    for drift, want in ((4, "refused:stale-input"), (5, "refused:screen")):
        Path(str(world["state"]) + ".keys").unlink(missing_ok=True)
        _stuck(world, drift_at=0, rewind=False)
        assert rs.request("dev1", "/opt/x", None, "manual", True, "operator: clear") == 0
        _set(world, caps=0, drift_at=drift)
        rs.execute()
        assert _rows(world)[-1]["outcome"] == want and _keys(world) == [], drift
    assert 2.0 in sleeps
    # the box was emptied before execute: an ordinary rotation, no Escape; a blank frame at the decision: refused
    for case in ("emptied", "blank"):
        Path(str(world["state"]) + ".keys").unlink(missing_ok=True)
        _stuck(world, drift_at=0, blank_at=0)
        assert rs.request("dev1", "/opt/x", None, "manual", True, "operator: clear") == 0
        if case == "emptied":
            _set(world, screen=IDLE_SCREEN, stuck=False)
        else:
            _set(world, caps=0, blank_at=2)
        rs.execute()
        row, keys = _rows(world)[-1], _keys(world)
        assert ["-t", "%5", "Escape", "Escape"] not in keys, (case, keys)
        assert row["outcome"] == ("partial:queued" if case == "emptied" else "refused:screen"), (
            case,
            row,
        )
    _set(world, blank_at=0)
    _stuck(world, text="x" * 1001)
    assert rs.request("dev1", "/opt/x", None, "manual", True, "operator: clear") == 1
    assert _rows(world)[-1]["outcome"] == "aborted:stale-input"
    _write_request(world)
    base = json.loads((world["req"] / "x--dev1.json").read_text())
    for bad in (
        {"stale_text": "x" * 1001, "operator_ok": "op"},
        {"stale_text": "go on", "operator_ok": "a\nb"},
    ):
        with pytest.raises(rs.CheckFailedError, match="stale_text"):
            rs._validate(dict(base, **bad))


def test_w_ee19169d_request_fields_are_optional(world):
    """An older verb's request (no stale fields) is valid; half of the pair, or an empty text, is refused."""
    _write_request(world)
    base = json.loads((world["req"] / "x--dev1.json").read_text())
    assert rs._validate(dict(base)) is not None
    assert (
        rs._validate(dict(base, stale_text="go on", operator_ok="op: ok"))["stale_text"] == "go on"
    )
    for bad in (
        {"stale_text": "go on"},
        {"stale_text": "", "operator_ok": "op"},
        {"operator_ok": "op"},
    ):
        with pytest.raises(rs.CheckFailedError, match="malformed|stale_text"):
            rs._validate(dict(base, **bad))


def test_w_ee19169d_review_r2_exact_box_at_the_key_and_rewind_only_without_a_box(world):
    """Review r2: a box emptied after the pre-key re-check (check 5 passes an empty box) is refused with NO key — the
    pair on an empty box opens Rewind; and the word "Rewind" in transcript text above a box that kept its text is not
    the Rewind menu: refused for the text left, with no extra Escape."""
    # execute's captures: check 5, the decision read, the discard's two reads, run_checks (5), the exact re-read (6)
    _stuck(world, drift_at=0, blank_at=0, empty_at=0, rewind=False)
    assert rs.request("dev1", "/opt/x", None, "manual", True, "operator: clear") == 0
    _set(world, caps=0, empty_at=5)
    rs.execute()
    assert _rows(world)[-1]["outcome"] == "refused:stale-input" and _keys(world) == [], _keys(world)
    Path(str(world["state"]) + ".keys").unlink(missing_ok=True)
    _set(world, empty_at=0)
    _stuck(world, esc_noop=True, rewind=False)
    _set(world, screen="see the Rewind docs\n" + json.loads(world["state"].read_text())["screen"])
    assert rs.request("dev1", "/opt/x", None, "manual", True, "operator: clear") == 0
    rs.execute()
    row = _rows(world)[-1]
    assert row["outcome"] == "refused:stale-input" and "did not read empty" in row["reason"], row
    assert _keys(world) == [["-t", "%5", "Escape", "Escape"]], _keys(world)


def test_w1783a9fe_resume_prompt_steers_off_the_isolation_prompt():
    """W-1783a9fe: a rotated builder's first turn prints 40-47 KB, the harness saves it to a file, and paging that file
    with `sed` on a shell variable stops Claude Code's worktree-isolation check for a person. The resume prompt sends the
    notes and any saved output to the Read tool and every command to a plain call of its own; its prefix and re-bind
    command stay as `_send` and the fake tmux match them."""
    text = rs.resume_prompt("dev1")
    assert text.startswith("You were rotated"), text
    assert "/opt/fabrik/scripts/whoami_agent.py --as dev1 --force" in text, text
    assert "and carry on. Read your memory notes and seed with the Read tool, not cat" in text, text
    assert (
        "run each command, git included, as a separate Bash call (the self-watch arm stays in the background)"
        in text
    )
    assert "saved to a file with the Read tool" in text, text
    # review r1: the measured case put the variable in sed's EXPRESSION (`sed -n "${n}p"`), not the file name
    assert (
        "never give sed, awk or head a shell variable or $( ), in the file name or the expression"
        in text
    ), text
    for kept in ("selfwatch_arm.sh", "never the previous transcript"):
        assert kept in text, kept


def _clear_hook(world, monkeypatch, bind: bool):
    """The fake tmux moves the registry record to NEW on `/clear`, and (when `bind`) appends the re-bind row on the
    resume prompt."""
    reg_path = world["config"] / "sessions" / "102.json"
    hook = (
        "p = os.environ['REG']\n"
        "if text.startswith('/clear'):\n"
        "    d = json.load(open(p)); d['sessionId'] = os.environ['NEW']; json.dump(d, open(p, 'w'))\n"
    )
    if bind:
        hook += (
            "if text.startswith('You were rotated'):\n"
            "    open(os.environ['AGENT_IDENTITY_FILE'], 'a').write(json.dumps({'session_id': os.environ['NEW'],"
            " 'name': 'dev1', 'predecessor': os.environ['OLD'], 'at': int(os.environ['BIND_AT'])}) + '\\n')\n"
        )
    for k, v in {
        "REG": str(reg_path),
        "NEW": NEW,
        "OLD": SID,
        "BIND_AT": str(int(time.time()) + 50),
    }.items():
        monkeypatch.setenv(k, v)
    _set(world, on_send=hook)


@pytest.fixture
def free_lock(tmp_path, monkeypatch):
    """T07: the registry tests below predate the agents lock and write registries outside any git repo — the lock is
    resolved to a free scratch file, so they keep grading the re-point itself (the lock has its own rows, T07 below)."""
    lock = tmp_path / "fabrik-agents.lock"
    monkeypatch.setattr(rs, "_agents_lock_file", lambda registry: str(lock))
    return lock


def test_wb72231b8_registry_is_repointed(world, monkeypatch, tmp_path, free_lock):
    """W-b72231b8: the verb re-points the repo's session registry from the old session id to the new one itself —
    key order kept, every other entry untouched — so nobody re-points it by hand."""
    other, third = "33333333-3333-4333-8333-333333333333", "44444444-4444-4444-8444-444444444444"
    regf = tmp_path / "repo" / ".fabrik" / "session-agents.json"
    regf.parent.mkdir(parents=True)
    regf.write_text(json.dumps({other: "dev2", SID: "dev1", third: "dev3"}, indent=2))
    monkeypatch.setattr(rs, "_session_registry", lambda repo, sid: regf)
    _clear_hook(world, monkeypatch, bind=True)
    _write_request(world)
    rs.execute()
    row = _rows(world)[-1]
    assert row["outcome"] == "ok" and row["registry"] == "repointed", row
    # the bind's own `at` (50 s after the hook was armed), never the moment the loop saw it
    assert isinstance(row["resume_sent_at"], int) and 45 <= row["rebind_s"] <= 51, row
    got = json.loads(regf.read_text())
    assert list(got.items()) == [(other, "dev2"), (NEW, "dev1"), (third, "dev3")]
    assert regf.read_text().endswith("}\n") and not list(regf.parent.glob(".session-agents.*"))


def test_wb72231b8_an_unsent_resume_still_repoints(world, monkeypatch, tmp_path, free_lock):
    """Critique r1: the re-point runs as soon as the new session is seen, before the resume prompt, so a resume that
    never submits still leaves the registry naming the session the pane now runs."""
    regf = tmp_path / "repo" / ".fabrik" / "session-agents.json"
    regf.parent.mkdir(parents=True)
    regf.write_text(json.dumps({SID: "dev1"}))
    monkeypatch.setattr(rs, "_session_registry", lambda repo, sid: regf)
    _clear_hook(world, monkeypatch, bind=False)
    real_send = rs._send

    def send(pane, text):
        if text.startswith("You were rotated"):
            raise rs.CheckFailedError("unsent", "the text is still in the input line after C-m")
        real_send(pane, text)

    monkeypatch.setattr(rs, "_send", send)
    _write_request(world)
    rs.execute()
    row = _rows(world)[-1]
    assert row["outcome"] == "typed-unsent:resume" and row["registry"] == "repointed", row
    assert json.loads(regf.read_text()) == {NEW: "dev1"}


def test_wb72231b8_registry_path_needs_a_real_checkout(tmp_path, monkeypatch):
    """Review r1: `resolve` matches a pane by the repo's folder name alone, so the registry is written only for the
    checkout whose `.git` the rotated session's newest binding names — never another checkout of the same name, a
    symlinked repo or `.fabrik`, or a path that cannot be resolved."""
    repo, clone = tmp_path / "repo", tmp_path / "elsewhere" / "repo"
    for r in (repo, clone):
        (r / ".git").mkdir(parents=True)
    rows = [{"session_id": SID, "name": "dev1", "toplevel": str(repo / ".git")}]
    monkeypatch.setattr(rs, "_bindings", lambda: rows)
    assert rs._session_registry(str(repo), SID) == repo / ".fabrik" / "session-agents.json"
    assert rs._session_registry(str(clone), SID) is None  # same folder name, another checkout
    assert rs._session_registry(str(repo), NEW) is None  # no binding for that session
    assert rs._session_registry("relative/repo", SID) is None
    assert rs._session_registry(str(repo) + "\0x", SID) is None
    link = tmp_path / "link"
    link.symlink_to(repo)
    assert rs._session_registry(str(link), SID) is None  # not its own realpath
    (repo / ".fabrik").symlink_to(clone)
    assert rs._session_registry(str(repo), SID) is None  # `.fabrik` points elsewhere


def test_wb72231b8_a_damaged_identity_store_never_raises(world):
    """Review r2: the registry path reads the identity store after the /clear; a non-UTF-8 byte or a deep nest in it
    skips that line instead of raising into the rotation outcome."""
    good = json.dumps({"session_id": SID, "name": "dev1", "toplevel": "/x/.git"})
    world["identity"].write_bytes(b"\xff\xfe\n" + b"[" * 200_000 + b"\n" + good.encode() + b"\n")
    rows = rs._bindings()
    assert rows[-1]["session_id"] == SID  # the good line after the bad ones is still read
    assert rs._session_registry("/x", SID) == Path("/x/.fabrik/session-agents.json")


def test_wb72231b8_registry_os_errors_are_a_recorded_state(tmp_path, free_lock):
    """Review r2: an OSError on the write (a read-only folder) is the `error:<name>` state, never a raise."""
    d = tmp_path / "ro"
    d.mkdir()
    regf = d / "session-agents.json"
    regf.write_text(json.dumps({SID: "dev1"}))
    d.chmod(0o500)
    try:
        assert rs._repoint_registry(regf, SID, NEW, "dev1") == "error:PermissionError"
    finally:
        d.chmod(0o700)
    assert json.loads(regf.read_text()) == {SID: "dev1"}


def test_wb72231b8_registry_over_the_readers_cap_is_refused(tmp_path, monkeypatch, free_lock):
    """Review r1: the readers stop at REGISTRY_MAX bytes, so neither an input over it nor an output that indentation
    grows past it is written."""
    regf = tmp_path / "session-agents.json"
    regf.write_text(json.dumps({SID: "dev1"}))
    monkeypatch.setattr(rs, "REGISTRY_MAX", 10)
    before = regf.read_bytes()
    assert rs._repoint_registry(regf, SID, NEW, "dev1") == "refused:over 1 MiB"
    monkeypatch.setattr(
        rs, "REGISTRY_MAX", len(before) + 2
    )  # the input fits; the indented output does not
    assert rs._repoint_registry(regf, SID, NEW, "dev1") == "refused:over 1 MiB"
    assert regf.read_bytes() == before and not list(tmp_path.glob(".session-agents.*"))


@pytest.mark.parametrize(
    ("content", "state"),
    [
        (None, "absent"),
        ({"33333333-3333-4333-8333-333333333333": "dev2"}, "no-entry"),
        ({SID: "dev9"}, "no-entry"),  # the old id names another agent: never re-pointed
        ({NEW: "dev1"}, "current"),
        ({SID: "dev1", NEW: "dev2"}, "refused:the new id already names another agent"),
        ("[1, 2]", "refused:not an object of session id -> agent name"),
        ("{not json", "refused:not valid JSON"),
        (f'{{"{SID}": "dev1", "{SID}": "dev1"}}', "refused:a session id appears twice"),
        ({"NOT-A-UUID": "dev2", SID: "dev1"}, "refused:a key is not a session id"),
        ({SID: {"nested": 1}}, "refused:not an object of session id -> agent name"),
        (
            {SID: "dev1", "33333333-3333-4333-8333-333333333333": "Bad Name"},
            "refused:a value is not an agent name",
        ),
    ],
)
def test_wb72231b8_registry_states_never_write_a_bad_file(tmp_path, content, state, free_lock):
    """W-b72231b8: every registry state other than a re-pointable entry is recorded and leaves the file
    byte-identical; nothing the writer emits is a shape agents_up.sh refuses."""
    regf = tmp_path / "session-agents.json"
    if content is not None:
        regf.write_text(content if isinstance(content, str) else json.dumps(content))
    before = regf.read_bytes() if regf.exists() else None
    assert rs._repoint_registry(regf, SID, NEW, "dev1") == state
    assert (regf.read_bytes() if regf.exists() else None) == before


def test_wb72231b8_registry_refuses_a_symlink_and_a_bad_new_id(tmp_path, free_lock):
    target = tmp_path / "real.json"
    target.write_text(json.dumps({SID: "dev1"}))
    link = tmp_path / "session-agents.json"
    link.symlink_to(target)
    assert rs._repoint_registry(link, SID, NEW, "dev1") == "refused:not a regular file"
    assert json.loads(target.read_text()) == {SID: "dev1"}
    plain = tmp_path / "plain.json"
    plain.write_text(json.dumps({SID: "dev1"}))
    assert (
        rs._repoint_registry(plain, SID, "NOT-A-UUID", "dev1")
        == "refused:the new id is not a session id"
    )


def test_wb72231b8_repoint_keeps_the_mode_drops_a_doubled_name_and_never_overwrites_a_hand_edit(
    tmp_path, monkeypatch, free_lock
):
    regf = tmp_path / "session-agents.json"
    regf.write_text(json.dumps({SID: "dev1"}))
    regf.chmod(0o644)
    assert rs._repoint_registry(regf, SID, NEW, "dev1") == "repointed"
    assert regf.stat().st_mode & 0o777 == 0o644 and json.loads(regf.read_text()) == {NEW: "dev1"}
    regf.write_text(
        json.dumps({SID: "dev1", NEW: "dev1"})
    )  # already current, the old key left behind
    assert rs._repoint_registry(regf, SID, NEW, "dev1") == "repointed"
    assert json.loads(regf.read_text()) == {NEW: "dev1"}
    regf.write_text(json.dumps({SID: "dev1"}))
    real_chmod = rs.os.chmod

    def chmod_then_hand_edit(p, mode):  # a hand edit lands between the read and the replace
        real_chmod(p, mode)
        regf.write_text(json.dumps({SID: "dev1", "33333333-3333-4333-8333-333333333333": "dev2"}))

    monkeypatch.setattr(rs.os, "chmod", chmod_then_hand_edit)
    assert rs._repoint_registry(regf, SID, NEW, "dev1") == "refused:changed on disk"
    assert NEW not in json.loads(regf.read_text()) and not list(tmp_path.glob(".session-agents.*"))


# ── T07: the re-point runs under the repo's agents lock (W-14219e6f point 3; plan-review A4, A5, A14; panel PF3) ──────

_AS_SPEC = importlib.util.spec_from_file_location(
    "_t07_agents_spawn", REPO / "scripts" / "sysadmin" / "agents_spawn.py"
)
AS = importlib.util.module_from_spec(_AS_SPEC)
sys.modules["_t07_agents_spawn"] = (
    AS  # its @dataclass classes resolve their module through sys.modules
)
_AS_SPEC.loader.exec_module(AS)
OTHER = "33333333-3333-4333-8333-333333333333"


def _git(*args: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", *args], check=True, capture_output=True, env=env)


def _git_repo(repo: Path, registry: dict | None) -> Path:
    """A real `git init` repo (so `lock_path` resolves its git common dir) with `.fabrik/session-agents.json`."""
    _git("init", "-q", str(repo))
    (repo / ".fabrik").mkdir()
    regf = repo / ".fabrik" / "session-agents.json"
    if registry is not None:
        regf.write_text(json.dumps(registry, indent=2) + "\n")
    return regf


def test_t07_a_rotation_waits_for_an_add_holding_the_lock_and_both_changes_hold(tmp_path):
    """W-14219e6f point 3: an `add` holds the agents lock across its registry read and write; a rotation landing
    inside it waits, so the file afterwards holds the added row AND the re-pointed one."""
    repo = tmp_path / "repo"
    regf = _git_repo(repo, {SID: "dev1"})
    held = threading.Event()

    def add() -> None:
        with AS.agents_lock(str(repo)):
            reg = json.loads(regf.read_text())
            held.set()
            time.sleep(0.6)  # the add's work between its read and its write
            reg[OTHER] = "dev2"
            regf.write_text(json.dumps(reg, indent=2) + "\n")

    t = threading.Thread(target=add)
    t.start()
    assert held.wait(5)
    started = time.monotonic()
    out = rs._repoint_registry(regf, SID, NEW, "dev1")
    waited = time.monotonic() - started
    t.join(5)
    assert out == "repointed"
    assert json.loads(regf.read_text()) == {NEW: "dev1", OTHER: "dev2"}
    assert waited >= 0.3, waited


def test_t07_the_lock_precedes_the_first_lstat_and_read(tmp_path, monkeypatch):
    """A4: a writer that takes the lock and rewrites the registry after the rotation's first read WOULD have happened
    (the rotation already waiting) loses nothing — the rotation reads only once it holds the lock."""
    repo = tmp_path / "repo"
    regf = _git_repo(repo, {SID: "dev1"})
    real_sleep = time.sleep
    waiting = threading.Event()

    def sleep(s: float) -> None:
        if threading.current_thread() is not threading.main_thread():
            waiting.set()
        real_sleep(s)

    _rs_time(monkeypatch, sleep=sleep)
    out: list[str] = []
    with AS.agents_lock(str(repo)):
        t = threading.Thread(
            target=lambda: out.append(rs._repoint_registry(regf, SID, NEW, "dev1"))
        )
        t.start()
        assert waiting.wait(5), "the rotation never waited for the agents lock"
        reg = json.loads(regf.read_text())
        reg[OTHER] = "dev2"
        regf.write_text(json.dumps(reg, indent=2) + "\n")
    t.join(5)
    assert out == ["repointed"]
    assert json.loads(regf.read_text()) == {NEW: "dev1", OTHER: "dev2"}


def test_t07_a_lock_held_past_the_bound_is_refused_busy(tmp_path, monkeypatch):
    """A14: the wait is bounded by `_wait_s(AGENTS_LOCK_WAIT_S)`; never obtained, nothing is written."""
    monkeypatch.setenv("ROTATE_WAIT_S", "1")
    repo = tmp_path / "repo"
    regf = _git_repo(repo, {SID: "dev1"})
    before = regf.read_bytes()
    with AS.agents_lock(str(repo)):
        started = time.monotonic()
        out = rs._repoint_registry(regf, SID, NEW, "dev1")
        waited = time.monotonic() - started
    assert out == "refused:agents lock busy"
    assert regf.read_bytes() == before and not list(regf.parent.glob(".session-agents.*"))
    assert 0.9 <= waited < 3, waited


def _rotate_copy(tmp_path: Path, agents_spawn: str | None) -> object:
    """rotate_session.py loaded from a directory of its own, beside the two scripts it loads at import and, when
    given, an `agents_spawn.py` with that text."""
    d = tmp_path / "copy"
    d.mkdir()
    for name in ("rotate_session.py", "hibernate.py", "transcript_size_check.py"):
        (d / name).write_bytes((SCRIPT.parent / name).read_bytes())
    if agents_spawn is not None:
        (d / "agents_spawn.py").write_text(agents_spawn)
    sp = importlib.util.spec_from_file_location("_t07_rotate_copy", d / "rotate_session.py")
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    return mod


def _boom(root: str) -> str:
    raise RuntimeError("git failed")


@pytest.mark.parametrize(
    "shape",
    [
        "agents_spawn.py missing",
        "agents_spawn.py fails to import",
        "agents_spawn.py exits at import",
        "agents_spawn.py has no lock_path",
        "lock_path raises",
        "not a git repository",
        "the lock file cannot be opened",
        "registry missing and not a git repository",
    ],
)
def test_t07_an_unresolvable_lock_is_refused_unavailable(tmp_path, monkeypatch, shape):
    """A5 (and pass 2, record-only): every way the lock cannot be had is the returned state `refused:agents lock
    unavailable` — never an exception, never a write; the lock comes first, so a missing registry in a repo whose lock
    cannot be resolved is not `absent`."""
    mod = rs
    regf = _git_repo(tmp_path / "repo", {SID: "dev1"})
    if shape == "agents_spawn.py missing":
        mod = _rotate_copy(tmp_path, None)
    elif shape == "agents_spawn.py fails to import":
        mod = _rotate_copy(tmp_path, "def lock_path(root:\n")
    elif (
        shape == "agents_spawn.py exits at import"
    ):  # review pass 1, F1: SystemExit is no Exception
        mod = _rotate_copy(tmp_path, "import sys\nsys.exit(3)\n")
    elif shape == "agents_spawn.py has no lock_path":
        mod = _rotate_copy(tmp_path, "X = 1\n")
    elif shape == "lock_path raises":
        monkeypatch.setattr(rs._agents_spawn(), "lock_path", _boom)
    elif shape == "the lock file cannot be opened":
        monkeypatch.setattr(
            rs._agents_spawn(), "lock_path", lambda root: str(tmp_path / "no-such-dir" / "lock")
        )
    else:
        plain = tmp_path / "plain" / ".fabrik"
        plain.mkdir(parents=True)
        regf = plain / "session-agents.json"
        if shape == "not a git repository":
            regf.write_text(json.dumps({SID: "dev1"}))
    before = regf.read_bytes() if regf.exists() else None
    assert mod._repoint_registry(regf, SID, NEW, "dev1") == "refused:agents lock unavailable"
    assert (regf.read_bytes() if regf.exists() else None) == before
    assert not list(regf.parent.glob(".session-agents.*"))


def test_t07_pf3_a_busy_refusal_is_healed_by_the_next_add(tmp_path, monkeypatch):
    """PF3 seam with T08b: a rotation refused `agents lock busy` leaves the row on the old id while the pane's claude
    already runs the new session (its argv still names the old one — a /clear keeps the process); the next `add`'s
    heal, under the same lock, re-points the row from the claude's live session record."""
    monkeypatch.setenv("ROTATE_WAIT_S", "1")
    repo = tmp_path / "repo"
    regf = _git_repo(repo, {SID: "dev1", OTHER: "dev2"})
    with AS.agents_lock(str(repo)):
        assert rs._repoint_registry(regf, SID, NEW, "dev1") == "refused:agents lock busy"
    assert json.loads(regf.read_text()) == {SID: "dev1", OTHER: "dev2"}
    proc, home = tmp_path / "proc", tmp_path / "home"
    for pid, kids, argv in ((500, "501 ", ["sh"]), (501, "", ["claude", "--resume", SID])):
        (proc / str(pid) / "task" / str(pid)).mkdir(parents=True)
        (proc / str(pid) / "task" / str(pid) / "children").write_text(kids)
        (proc / str(pid) / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    fields = ["S"] + ["1"] * 18 + ["777"] + ["0"] * 6
    (proc / "501" / "stat").write_text(f"501 (claude) {' '.join(fields)}\n")
    (home / ".claude" / "sessions").mkdir(parents=True)
    (home / ".claude" / "sessions" / "501.json").write_text(
        json.dumps({"pid": 501, "procStart": "777", "sessionId": NEW})
    )
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(proc))
    monkeypatch.setenv("HOME", str(home))
    with AS.agents_lock(str(repo)):
        AS.heal_registry(str(repo), [AS._Pane("@1", "agents", "%1", 500, "dev1")])
    assert json.loads(regf.read_text()) == {OTHER: "dev2", NEW: "dev1"}


def test_t07_rotate_and_agents_spawn_resolve_the_same_lock(tmp_path):
    """Spec D2 seam: the lock rotate_session resolves from `<repo>/.fabrik/session-agents.json` is the very file
    `agents_spawn.lock_path(<repo>)` names — for the main checkout and for a linked worktree (one common dir)."""
    repo = tmp_path / "repo"
    regf = _git_repo(repo, {SID: "dev1"})
    _git(
        "-C",
        str(repo),
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "x",
    )
    wt = tmp_path / "wt"
    _git("-C", str(repo), "worktree", "add", "-q", str(wt))
    (wt / ".fabrik").mkdir()
    want = AS.lock_path(str(repo))
    assert want == str(Path(want))  # an absolute path inside the common dir
    assert rs._agents_lock_file(regf) == want
    assert rs._agents_lock_file(wt / ".fabrik" / "session-agents.json") == want
    assert AS.lock_path(str(wt)) == want


def _late_bind(world, monkeypatch, bind_after: float | None) -> dict:
    """A fake clock that moves only when the script sleeps, with ROTATE_WAIT_S unset so each wait runs at its
    production length (the fake panes settle at once, so the waits before the re-bind end early). The identity store
    gains the re-bind `bind_after` s after the resume prompt, or never when None. Returns the times seen."""
    monkeypatch.delenv("ROTATE_WAIT_S")
    clock = {"now": time.time()}
    _rs_time(
        monkeypatch,
        time=lambda: clock["now"],
        sleep=lambda s: clock.__setitem__("now", clock["now"] + s),
    )
    _clear_hook(world, monkeypatch, bind=False)
    seen: dict = {}
    real_send = rs._send

    def send(pane, text):
        real_send(pane, text)
        if text.startswith("You were rotated"):
            seen["sent"] = clock["now"]

    monkeypatch.setattr(rs, "_send", send)
    real_bindings = rs._bindings

    def bindings():
        if "sent" in seen:
            seen["last_read"] = clock["now"]
            if bind_after is not None and clock["now"] >= seen["sent"] + bind_after:
                at = int(seen["sent"] + bind_after)
                return [{"session_id": NEW, "name": "dev1", "predecessor": SID, "at": at}]
        return real_bindings()

    monkeypatch.setattr(rs, "_bindings", bindings)
    _write_request(world)
    rs.execute()
    return seen


def test_wb72231b8_a_late_bind_inside_the_grace_rows_ok(world, monkeypatch):
    """W-b72231b8 slice 2: a re-bind landing 98 s after the resume prompt (the one late bind measured since W-b92aa5cf)
    rows `ok` with its own `rebind_s`, not `partial:rebind`."""
    _late_bind(world, monkeypatch, 98)
    row = _rows(world)[-1]
    assert row["outcome"] == "ok" and row["predecessor_row"] is True, row
    assert 97 <= row["rebind_s"] <= 99, row


def test_w1e0f4229_a_slow_exiting_tmux_never_moves_the_fake_clock(world, monkeypatch, tmp_path):
    """W-1e0f4229: the late-bind test failed 12 in 16 under load (`typed-unsent:*`, or rebind_s 259 for 98) because its
    fake clock sat on the GLOBAL time module, where subprocess polls a child's exit with time.sleep. The clock is now
    rotate_session's own, so a tmux that lingers after closing its pipes costs the fake clock nothing."""
    clock = {"now": 1000.0}
    _rs_time(
        monkeypatch,
        time=lambda: clock["now"],
        sleep=lambda s: clock.__setitem__("now", clock["now"] + s),
    )
    slow = tmp_path / "slow-tmux"
    slow.write_text(
        "#!/usr/bin/env python3\nimport os, time\nos.close(1)\nos.close(2)\ntime.sleep(0.05)\n"
    )
    slow.chmod(0o755)
    monkeypatch.setenv("ROTATE_TMUX", str(slow))
    for _ in range(3):
        rs._tmux("capture-pane", "-p", "-t", "%5")
    assert clock["now"] == 1000.0, clock
    # the identity half, independent of how subprocess waits: rotate_session's `time` is the proxy, the global
    # module keeps its real sleep
    assert rs.time is not time and time.sleep is _REAL_SLEEP


def _clock_patches(src: str) -> list[int]:
    """The lines of `src` that patch the `time` module (W-1e0f4229 review). Read as a syntax tree, so a call ruff
    wraps is still one call and a comment quoting one is none. The clock is `time`, a name bound to it (`import time
    as t`, `t = time`), any `<module>.time` attribute (`rs.time`, `rs.hib.time`, `subprocess.time` — each loaded
    module's `time` IS the global module), `sys.modules["time"]` or a `"time.<name>"` string. Refused: a `setattr`,
    `patch` or `patch.object` whose target (first argument, `target=` or `obj=`) is the clock, and an assignment to
    an attribute of it. Out of scope by design: other files, and swapping `rs.time` itself (`setattr(rs, "time", …)`
    or `rs.time = …`), which is `_rs_time`'s own move."""
    tree = ast.parse(src)
    names = {"time"} | {
        a.asname
        for n in ast.walk(tree)
        if isinstance(n, ast.Import)
        for a in n.names
        if a.name == "time" and a.asname
    }

    def clock(node) -> bool:
        if isinstance(node, ast.Name):
            return node.id in names
        if isinstance(node, ast.Attribute):
            return node.attr == "time"
        if isinstance(node, ast.Subscript):  # sys.modules["time"], nothing else keyed "time"
            return (
                isinstance(node.slice, ast.Constant)
                and node.slice.value == "time"
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "modules"
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "sys"
            )
        return (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.startswith("time.")
        )

    grew = True
    while grew:  # `t = time`, then `u = t`: a name assigned from the clock is the clock
        before = len(names)
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and clock(n.value):
                names |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        grew = len(names) > before

    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            targets = list(node.args[:1]) + [
                k.value for k in node.keywords if k.arg in ("target", "obj")
            ]
            if name in ("setattr", "patch", "object") and any(clock(t) for t in targets):
                hits.append(node.lineno)
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Attribute) and clock(t.value) for t in targets):
                hits.append(node.lineno)
    return sorted(hits)


@pytest.mark.parametrize(
    "line, refused",
    [
        ('monkeypatch.setattr(time, "sleep", f)', True),
        ('monkeypatch.setattr(rs.time, "sleep", f)', True),
        ('monkeypatch.setattr(\n    time, "sleep", lambda s: None\n)', True),  # ruff-wrapped
        ('monkeypatch.setattr(target=time, name="sleep", value=f)', True),
        ('monkeypatch.setattr("time.sleep", f)', True),
        ('import time as _clock\nmonkeypatch.setattr(_clock, "sleep", f)', True),
        ('monkeypatch.setattr(sys.modules["time"], "sleep", f)', True),
        ('mock.patch("time.sleep")', True),
        ('mock.patch.object(time, "sleep")', True),
        ("time.sleep = f", True),
        ("rs.time.sleep = f", True),
        ('monkeypatch.setattr(rs.hib.time, "sleep", f)', True),  # hibernate's `time` is the global
        ('monkeypatch.setattr(AS.time, "sleep", f)', True),
        ('clock_mod = time\nmonkeypatch.setattr(clock_mod, "sleep", f)', True),
        ('a = time\nb = a\nmonkeypatch.setattr(b, "sleep", f)', True),
        ('monkeypatch.setattr(rs, "time", proxy)', False),  # _rs_time's own line
        ("rs.time = proxy", False),  # the same swap, written as an assignment
        ('monkeypatch.setattr(d["time"], "sleep", f)', False),  # only sys.modules["time"]
        ('# never monkeypatch.setattr(time, "sleep", f) here', False),
        ('"""a docstring quoting monkeypatch.setattr(time, "sleep", f)"""', False),
        ('monkeypatch.setattr(rs, "IDLE_S", 0)', False),
        ("time.sleep(0.5)", False),
    ],
)
def test_w1e0f4229_the_clock_patch_scan_sees_every_shape(line, refused):
    """The scan's probe list, both directions (W-1e0f4229 review pass 2: a line regex missed a wrapped call, an alias,
    a keyword, `sys.modules`, `mock.patch` and a direct assignment, and refused a comment)."""
    assert bool(_clock_patches(line)) is refused, line


def test_w1e0f4229_no_test_patches_the_global_time_module():
    """W-1e0f4229 review: the drift test above grades `_rs_time` only, so a later test patching `time` around it would
    bring the drift back with that test green. `_rs_time` is the one patch site this file may hold."""
    hits = _clock_patches(Path(__file__).read_text(encoding="utf-8"))
    assert hits == [], (
        f"patch rotate_session's clock through _rs_time, never the global module: lines {hits}"
    )


def test_wb72231b8_no_bind_waits_the_whole_grace_then_rows_partial(world, monkeypatch):
    """W-b72231b8 slice 2: with no re-bind the row is `partial:rebind`, never a false `ok`, and only after the identity
    store was read for the whole REBIND_GRACE_S."""
    seen = _late_bind(world, monkeypatch, None)
    row = _rows(world)[-1]
    assert row["outcome"] == "partial:rebind" and row["predecessor_row"] is False, row
    waited = seen["last_read"] - seen["sent"]
    assert rs.REBIND_GRACE_S - 2 <= waited <= rs.REBIND_GRACE_S, waited


def test_wb72231b8_execute_claims_nothing_new_after_the_cutoff(world, monkeypatch):
    """W-b72231b8 slice 2: two requests can meet in one run only by racing past `_pending` (request checks it seconds
    before it writes its file). A request still waiting once the run has gone CLAIM_CUTOFF_S is left for the path unit's
    next start — never started where the unit's timeout could kill it with no row."""
    mono = {"now": 1000.0}
    _rs_time(monkeypatch, monotonic=lambda: mono["now"])
    rows: list = []
    monkeypatch.setattr(rs, "append_row", lambda row: rows.append(row))

    def one(claimed):
        mono["now"] += rs.CLAIM_CUTOFF_S + 1  # this rotation took past the cutoff
        return {"outcome": "ok", "claimed": claimed.name}

    monkeypatch.setattr(rs, "_one", one)
    world["req"].mkdir(exist_ok=True)
    first, second = world["req"] / "a--dev1.json", world["req"] / "b--dev2.json"
    first.write_text("{}")
    second.write_text("{}")
    os.utime(first, (1, 1))  # claimed oldest-first
    assert rs.execute() == 0
    assert [r["claimed"] for r in rows] == ["a--dev1.claimed"], rows
    assert second.exists() and not first.exists() and not list(world["req"].glob("*.claimed"))


def test_wb72231b8_the_worst_request_fits_the_units_timeout():
    """W-b72231b8 slice 2: the last request `execute` may start (at CLAIM_CUTOFF_S) ends, at its worst, with 60 s of the
    oneshot's TimeoutStartSec to spare, so the timeout never kills a rotation before its row; the grace covers the
    measured 98 s; every wait is a named constant (a literal wait would escape the derivation); the unit sets exactly
    one integer TimeoutStartSec and no TimeoutSec that could override it. Model boundary (review r2): waits passed to
    `_wait_s`, the discard's re-check sleep and `_tmux`'s timeout. Outside it, by design: the count of 17 tmux calls is
    restated here, not counted from the call sites; a wait that bypasses `_wait_s`; a subprocess other than `_tmux`
    (run_checks' git calls are W-b728822f); a systemd drop-in or a unit Environment= on the installed copy."""
    unit = (REPO / "scripts" / "sysadmin" / "fabrik-rotate.service").read_text().splitlines()
    starts = [ln.strip() for ln in unit if ln.strip().startswith("TimeoutStartSec")]
    assert len(starts) == 1 and re.fullmatch(r"TimeoutStartSec=\d+", starts[0]), starts
    assert not [ln for ln in unit if ln.strip().startswith("TimeoutSec")]
    timeout = int(starts[0].split("=", 1)[1])
    assert rs.REQUEST_WORST_S == (
        rs.DISCARD_RECHECK_S
        + rs.DISCARD_WAIT_S
        + 2 * (rs.SEND_SETTLE_S + rs.SEND_SUBMIT_S)
        + rs.CLEAR_WAIT_S
        + rs.AGENTS_LOCK_WAIT_S  # T07: the registry re-point's wait for the agents lock
        + rs.REBIND_GRACE_S
        + 5  # the loops' sleeps after their last check: 5 x 0.5 + 2 x 1 + 0.2 = 4.7, rounded up
        + 17 * rs.TMUX_TIMEOUT_S
    )
    assert timeout >= rs.CLAIM_CUTOFF_S + rs.REQUEST_WORST_S + 60, (rs.REQUEST_WORST_S, timeout)
    assert rs.REBIND_GRACE_S >= 98
    assert rs.AGENTS_LOCK_POLL_S <= 0.2  # the rounded-up 5 above holds it
    src = SCRIPT.read_text()
    assert not re.findall(r"_wait_s\(\s*[-+.\d]", src), (
        "a wait passed as a literal escapes REQUEST_WORST_S"
    )
    assert "for wait in (0.0, DISCARD_RECHECK_S):" in src
    tmux_src = inspect.getsource(rs._tmux)
    assert "timeout=TMUX_TIMEOUT_S" in tmux_src and not re.findall(r"timeout=\d", tmux_src)


# ── W-05021a03: the exit names transient (75) vs permanent (1) ────────────────────────────────────────────────────

_MIDTURN = {"type": "assistant", "timestamp": "2026-10-23T00:00:02Z"}


def test_w05021a03_tmux_timeout_is_transient(world, monkeypatch, capsys):
    def slow(*args):
        raise subprocess.TimeoutExpired(["tmux", *args], rs.TMUX_TIMEOUT_S)

    monkeypatch.setattr(rs, "_tmux", slow)
    assert rs.request("dev1", "/opt/x", None, "manual") == rs.EXIT_RETRY == 75
    assert _rows(world)[-1]["outcome"] == "aborted:tmux"
    assert "(transient" in capsys.readouterr().err


def test_w05021a03_worktree_probe_timeout_is_transient(world, monkeypatch):
    monkeypatch.setattr(
        rs.hib, "worktree_state", lambda path: (True, "not a git checkout (git timed out)")
    )
    assert rs.request("dev1", "/opt/x", None, "manual") == 75
    assert _rows(world)[-1]["outcome"] == "aborted:worktree"


def test_w05021a03_stale_unclaimed_request_is_permanent(world, capsys):
    rs._ensure_req_dir()
    left = world["req"] / "x--other.json"
    left.write_text("{}")
    assert rs.request("dev1", "/opt/x", None, "manual") == 75  # a live request: wait for its row
    # past one rotation's worst case but inside the unit's timeout: a slow unit, still claiming (review r1)
    slow = time.time() - rs.REQUEST_WORST_S - rs.STALE_S - 60
    os.utime(left, (slow, slow))
    assert rs.request("dev1", "/opt/x", None, "manual") == 75
    old = time.time() - rs.ORPHAN_S - 1
    os.utime(left, (old, old))
    capsys.readouterr()
    assert rs.request("dev1", "/opt/x", None, "manual") == 1  # nobody is claiming: the unit is down
    last = _rows(world)[-1]
    assert (
        last["outcome"] == "aborted:pending" and "install_rotate_unit.sh --check" in last["reason"]
    )
    assert "(permanent" in capsys.readouterr().err


def test_w05021a03_no_binding_yet_names_the_rebind(world, capsys):
    world["identity"].write_text("")  # the fresh session after a /clear has not re-bound yet
    assert rs.request("dev1", "/opt/x", None, "manual") == 1
    last = _rows(world)[-1]
    assert last["outcome"] == "aborted:resolve", last
    assert "no identity binding yet" in last["reason"]
    assert "whoami_agent.py --as dev1 --force" in last["reason"]
    assert "(permanent" in capsys.readouterr().err
    with world["identity"].open("a") as fh:  # bound, then the name moved to another window
        for sid, at in ((SID, 1), (NEW, 2)):
            row = {"session_id": sid, "name": "dev1", "toplevel": "/opt/x", "at": at}
            fh.write(json.dumps(row) + "\n")
    assert rs.request("dev1", "/opt/x", None, "manual") == 1
    assert "another window" in _rows(world)[-1]["reason"]


def test_w05021a03_midturn_dialog_is_permanent(world, monkeypatch, capsys):
    world["transcript"].write_text(world["transcript"].read_text() + json.dumps(_MIDTURN) + "\n")
    # a permission prompt in place of the input box
    _set(world, screen="Allow?\n❯ 1. Yes\n  2. No\n")
    assert rs.request("dev1", "/opt/x", None, "manual") == 1
    last = _rows(world)[-1]
    assert last["outcome"] == "aborted:screen" and "dialog" in last["reason"], last
    assert "(permanent" in capsys.readouterr().err
    _set(world, screen=IDLE_SCREEN)  # mid-turn with the input box drawn: still working
    assert rs.request("dev1", "/opt/x", None, "manual") == 75
    assert _rows(world)[-1]["outcome"] == "aborted:idle"
    # tmux could not capture: unknown, so transient
    monkeypatch.setattr(rs, "_box_now", lambda pane: (None, ""))
    assert rs.request("dev1", "/opt/x", None, "manual") == 75
    assert _rows(world)[-1]["outcome"] == "aborted:idle"


def test_w05021a03_every_request_check_is_classified():
    import ast

    reach = {
        "request",
        "_ensure_req_dir",
        "_pending",
        "resolve",
        "_registry",
        "_transcript",
        "run_checks",
        "_idle_row_check",
        "_bound",
    }
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for fn in (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in reach):
        for call in ast.walk(fn):
            if (
                isinstance(call, ast.Call)
                and getattr(call.func, "id", None) == "CheckFailedError"
                and call.args
                and isinstance(call.args[0], ast.Constant)
            ):
                names.add(call.args[0].value)
    assert len(names) >= 12, names  # the walk found the raises at all
    assert not rs.TRANSIENT_CHECKS & rs.PERMANENT_CHECKS
    unclassified = names - rs.TRANSIENT_CHECKS - rs.PERMANENT_CHECKS
    assert not unclassified, unclassified
    # the fail direction: an unclassified check retries, never stops
    assert rs.CheckFailedError("never-classified", "x").transient is True
    assert rs.CheckFailedError("args", "x").transient is False
    assert rs.CheckFailedError("args", "x", transient=True).transient is True


def test_w05021a03_a_restarting_pane_is_transient(world, monkeypatch):
    (
        world["config"] / "sessions" / "102.json"
    ).unlink()  # a claude seconds old has not written its record yet
    assert rs.request("dev1", "/opt/x", None, "manual") == 75
    assert "no registry record" in _rows(world)[-1]["reason"]
    monkeypatch.setattr(rs, "_tmux", lambda *a: subprocess.CompletedProcess(a, 1, "", "no server"))
    assert rs.request("dev1", "/opt/x", None, "manual") == 75
    assert _rows(world)[-1]["reason"] == "tmux is not answering"


def test_w05021a03_an_empty_capture_and_a_pending_rotation_say_wait(world, monkeypatch, capsys):
    with monkeypatch.context() as m:  # at a turn end, but tmux returned nothing
        m.setattr(rs, "_box_now", lambda pane: (None, ""))
        assert rs.request("dev1", "/opt/x", None, "manual") == 75
    last = _rows(world)[-1]
    assert (last["outcome"], last["reason"]) == (
        "aborted:screen",
        "no input box is drawn (a redraw, a scrolled or restarting pane)",
    )
    capsys.readouterr()
    assert rs.request("dev1", "/opt/x", None, "manual") == 0
    assert rs.request("dev1", "/opt/x", None, "manual") == 75
    assert "once the pending rotation's row lands" in capsys.readouterr().err


# W-05021a03 review r1: permanent only on POSITIVE evidence that an act is needed


@pytest.mark.parametrize(
    "screen, rc",
    [
        ("\n\n\n", 75),  # a blank frame
        ("redrawing\n", 75),  # a frame with no box drawn
        ("scrolled history\n❯ old prompt\nmore output\n", 75),  # copy-mode: a ❯ with no rules
        (
            "more output\n❯ 2. fix the parser\nthe answer\n",
            75,
        ),  # one numbered prompt left in scrollback
        (
            "Do you want to proceed?\n❯ 2. Yes, and don't ask again\n  3. No\n",
            1,
        ),  # cursor on option 2
    ],
)
def test_w05021a03_only_a_dialog_or_typed_text_is_a_permanent_screen(world, screen, rc):
    _set(world, screen=screen)
    assert rs.request("dev1", "/opt/x", None, "manual") == rc
    assert _rows(world)[-1]["outcome"] == "aborted:screen"


def test_w05021a03_a_second_claude_or_a_missing_pane_is_transient(world, monkeypatch):
    monkeypatch.setattr(rs, "_claude_under", lambda proc, root: [102, 140])  # a pool seat's claude
    assert rs.request("dev1", "/opt/x", None, "manual") == 75
    assert "2 claude processes" in _rows(world)[-1]["reason"]
    monkeypatch.setattr(rs, "_claude_under", lambda proc, root: [])  # claude respawning
    assert rs.request("dev1", "/opt/x", None, "manual") == 75
    _set(world, panes=["%6\tx\tother\t200"])  # the pane itself is being recreated
    assert rs.request("dev1", "/opt/x", None, "manual") == 75


@pytest.mark.parametrize(
    "why, rc",
    [
        ("detached HEAD", 75),  # what a timed-out symbolic-ref reads as
        ("no upstream and HEAD is on no remote branch", 75),
        ("2 uncommitted change(s)", 1),
        ("1 commit(s) not pushed", 1),
    ],
)
def test_w05021a03_only_unfinished_work_is_a_permanent_worktree(world, monkeypatch, why, rc):
    monkeypatch.setattr(rs.hib, "worktree_state", lambda path: (True, why))
    assert rs.request("dev1", "/opt/x", None, "manual") == rc


def test_w05021a03_an_unreadable_identity_store_is_transient(world, monkeypatch):
    blocker = world["tmp"] / "a-file"
    blocker.write_text("")
    monkeypatch.setenv(
        "AGENT_IDENTITY_FILE", str(blocker / "agent-identity.jsonl")
    )  # NotADirectoryError
    assert rs.request("dev1", "/opt/x", None, "manual") == 75
    assert "identity store is unreadable" in _rows(world)[-1]["reason"]


def test_w05021a03_the_transient_line_fits_the_cause(world, monkeypatch, capsys):
    def slow(*args):
        raise subprocess.TimeoutExpired(["tmux", *args], rs.TMUX_TIMEOUT_S)

    with monkeypatch.context() as m:
        m.setattr(rs, "_tmux", slow)
        rs.request("dev1", "/opt/x", None, "manual")
    assert "ask again in a few seconds" in capsys.readouterr().err
    world["transcript"].write_text(world["transcript"].read_text() + json.dumps(_MIDTURN) + "\n")
    rs.request("dev1", "/opt/x", None, "manual")
    assert "once dev1 ends its turn" in capsys.readouterr().err


def test_w05021a03_a_dangling_request_ages_out(world):
    rs._ensure_req_dir()
    (world["req"] / "x--gone.json").symlink_to(world["tmp"] / "nowhere")
    old = time.time() - rs.ORPHAN_S - 1
    os.utime(world["req"] / "x--gone.json", (old, old), follow_symlinks=False)
    assert rs.request("dev1", "/opt/x", None, "manual") == 1
    assert "unclaimed" in _rows(world)[-1]["reason"]


def test_w05021a03_a_tmux_timeout_keeps_the_stale_input_fields(world, monkeypatch):
    _stuck(world)

    def slow(t, seen=""):
        raise subprocess.TimeoutExpired(["tmux"], rs.TMUX_TIMEOUT_S)

    monkeypatch.setattr(rs, "run_checks", slow)
    assert rs.request("dev1", "/opt/x", None, "manual", True, "operator: clear") == 75
    last = _rows(world)[-1]
    assert last["outcome"] == "aborted:tmux"
    assert (last["stale_text"], last["operator_ok"]) == ("go on", "operator: clear")


def test_w05021a03_no_transcript_yet_waits_two_is_permanent(world):
    world["transcript"].unlink()  # a session that has not written its first row
    assert rs.request("dev1", "/opt/x", None, "manual") == 75
    assert "0 transcripts" in _rows(world)[-1]["reason"]
    twin = world["config"] / "projects" / "-opt-y" / f"{SID}.jsonl"
    twin.parent.mkdir(parents=True)
    twin.write_text("{}\n")
    (world["config"] / "projects" / "-opt-x" / f"{SID}.jsonl").write_text("{}\n")
    assert rs.request("dev1", "/opt/x", None, "manual") == 1
    assert "2 transcripts" in _rows(world)[-1]["reason"]


def test_w05021a03_a_typed_numbered_line_is_text_and_discardable(world, capsys):
    _stuck(world, "1. fix the parser")  # the box holds a numbered line, which is no dialog
    assert rs._dialog(_boxed("❯ 1. fix the parser")) is False
    assert rs.request("dev1", "/opt/x", None, "manual") == 1
    assert "text is in the input box" in _rows(world)[-1]["reason"]
    assert "(permanent" in capsys.readouterr().err
    # its remedy works
    assert rs.request("dev1", "/opt/x", None, "manual", True, "operator: clear") == 0
    # a typed list: two numbered rows, still the box's
    listed = _boxed("❯ 1. fix the parser", "  2. then the tests")
    assert rs._dialog(listed) is False
    for f in world["req"].glob("*.json"):
        f.unlink()
    _set(world, screen=listed)
    assert rs.request("dev1", "/opt/x", None, "manual") == 1
    assert "text is in the input box" in _rows(world)[-1]["reason"]


@pytest.mark.parametrize("kind", ["unreadable", "directory"])
def test_w05021a03_a_store_stat_sees_but_cannot_read_is_transient(world, monkeypatch, kind):
    store = world["tmp"] / "identity-store"
    if kind == "directory":
        store.mkdir()
    else:
        store.write_text("")
        store.chmod(0)
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(store))
    try:
        assert rs.request("dev1", "/opt/x", None, "manual") == 75
        assert "identity store is unreadable" in _rows(world)[-1]["reason"]
    finally:
        store.chmod(0o700)


# --- W-e38f8ee7: `rotate-session <name> --move` — a fresh session in the worktree the builder works in ---------------

FAKE_AGENTS_UP = """#!/bin/sh
printf '%s\\n' "ARGV $*" "PATH=$PATH" "AGENT_IDENTITY_FILE=${AGENT_IDENTITY_FILE:-unset}" >> "$FAKE_UP_LOG"
[ -f "$FAKE_UP_LOG.refuse" ] && { echo "agents_up: the pane changed since the request" >&2; exit 2; }
echo "claude -n $3 --session-id $4 'You were moved'"
"""

# the respawned pane: the old claude (pid 102) exits — its stat start changes — and the new one registers its session
RESPAWN_OK = (
    "sid = re.search(r'--session-id (\\S+)', a[-1]).group(1)\n"
    "p = os.environ['ROTATE_PROC_ROOT'] + '/102/stat'\n"
    "open(p, 'w').write('102 (claude) S 101' + ' 0' * 17 + ' 999\\n')\n"
    "if os.environ.get('MOVE_REGISTERS', '1') == '1':\n"
    "    reg = os.environ['MOVE_SESSIONS'] + '/103.json'\n"
    "    json.dump({'pid': 103, 'sessionId': sid, 'procStart': '5', 'cwd': a[a.index('-c') + 1]}, open(reg, 'w'))\n"
    "if os.environ.get('MOVE_BINDS', '1') == '1':\n"
    "    open(os.environ['AGENT_IDENTITY_FILE'], 'a').write(json.dumps({'session_id': sid, 'name': 'dev1',"
    " 'toplevel': '/opt/x', 'at': 9}) + '\\n')\n"
)


def _move_world(world, monkeypatch, *, registers: bool = True, binds: bool = True):
    """A repo `x` whose builder dev1 works in its linked worktree `dev1-work` (the session record's cwd is inside it), a
    fake agents_up.sh logging its argv and env, and a respawn that plays the new pane. Returns (repo, worktree)."""
    repo = (world["tmp"] / "x").resolve()
    wt = repo / ".claude" / "worktrees" / "dev1-work"
    (wt / "src").mkdir(parents=True)
    (wt / ".git").write_text("gitdir: x\n")
    reg = dict(world["reg"], cwd=str(wt / "src"))
    (world["config"] / "sessions" / "102.json").write_text(json.dumps(reg))
    # the pane's own environment (the env-i set agents_up gave it), which the move carries over
    (world["proc"] / "102" / "environ").write_bytes(
        b"\0".join(
            [
                f"CLAUDE_CONFIG_DIR={world['config']}".encode(),
                b"PATH=/pane/bin:/usr/bin",
                b"AGENT_IDENTITY_FILE=/pane/identity.jsonl",
            ]
        )
    )
    up = world["tmp"] / "agents_up_fake"
    up.write_text(FAKE_AGENTS_UP)
    up.chmod(0o755)
    for k, v in {
        "FABRIK_AGENTS_UP": up,
        "FAKE_UP_LOG": world["tmp"] / "up.log",
        "MOVE_SESSIONS": world["config"] / "sessions",
        "MOVE_REGISTERS": "1" if registers else "0",
        "MOVE_BINDS": "1" if binds else "0",
    }.items():
        monkeypatch.setenv(k, str(v))
    _set(world, on_respawn=RESPAWN_OK)
    return repo, wt


def _respawns(world):
    p = Path(str(world["state"]) + ".respawn")
    return [json.loads(ln) for ln in p.read_text().splitlines()] if p.exists() else []


def _up_log(world):
    p = world["tmp"] / "up.log"
    return p.read_text().splitlines() if p.exists() else []


def test_w_e38f8ee7_request_move_derives_validates_and_writes(world, monkeypatch, capsys):
    """B1: `request --move` derives the folder from the session record's cwd (the linked worktree in place under the
    repo's .claude/worktrees/ that holds it) and writes a data-only `mode: move` request carrying `into`. A cwd outside
    such a worktree, a coordinator's tree, a no-op move (the session is already filed under the target, so the grid
    already starts it there) and --move with --compact or --stale-input are permanent `args` refusals."""
    repo, wt = _move_world(world, monkeypatch)
    assert rs.main(["request", "dev1", "--move", "--repo", str(repo)]) == 0
    data = json.loads((world["req"] / "x--dev1.json").read_text())
    assert data["mode"] == "move" and data["into"] == "dev1-work" and data["focus"] == ""
    assert set(data) == rs.FIELDS | {"into"}, data
    (world["req"] / "x--dev1.json").unlink()

    def refused(reason: str, **kw) -> None:
        assert (
            rs.request(
                "dev1", str(repo), kw.get("compact"), "manual", move=True, **kw.get("more", {})
            )
            == 1
        )
        row = _rows(world)[-1]
        assert row["outcome"] == "aborted:args" and reason in row["reason"], row
        assert not list(world["req"].glob("*.json"))
        assert "(permanent" in capsys.readouterr().err

    refused("--move takes neither --compact nor --stale-input", compact="focus")
    refused(
        "--move takes neither --compact nor --stale-input",
        more={"stale": True, "operator_ok": "ok"},
    )
    reg_file = world["config"] / "sessions" / "102.json"
    for cwd, reason in (
        (repo, "is not inside a linked worktree of"),
        (world["tmp"] / "elsewhere", "is not inside a linked worktree of"),
    ):
        reg_file.write_text(json.dumps(dict(world["reg"], cwd=str(cwd))))
        refused(reason)
    plain = repo / ".claude" / "worktrees" / "plain"
    plain.mkdir()
    reg_file.write_text(json.dumps(dict(world["reg"], cwd=str(plain))))
    refused("plain is not a linked git worktree in place")
    coord = repo / ".claude" / "worktrees" / "coordinator"
    coord.mkdir()
    (coord / ".git").write_text("gitdir: x\n")
    reg_file.write_text(json.dumps(dict(world["reg"], cwd=str(coord))))
    refused("coordinator is the coordinator's tree")
    # the session is already filed under the target (a hard link, as Claude Code files it): nothing to move
    reg_file.write_text(json.dumps(dict(world["reg"], cwd=str(wt / "src"))))
    proj = world["config"] / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(wt))
    proj.mkdir(parents=True)
    os.link(world["transcript"], proj / f"{SID}.jsonl")
    refused("already starts in .claude/worktrees/dev1-work")


def test_w_e38f8ee7_execute_move_respawns_and_records(world, monkeypatch):
    """B2: execute on a move request fetches the pane command FIRST (agents_up.sh `--pane-cmd … --into … --from <old
    sid> --replacing <old pid>`, run with the pane's own PATH and AGENT_IDENTITY_FILE), THEN runs the checks, then
    `respawn-pane -k -t <pane> -c <worktree> <cmd>`, reaps the old claude, waits for the new session record and rows
    `ok` on the new binding — no key typed, no predecessor (a new process), mode/into/old_exit on the row."""
    repo, wt = _move_world(world, monkeypatch)
    order: list[str] = []
    real_checks = rs.run_checks
    monkeypatch.setattr(
        rs,
        "run_checks",
        lambda t, stale="": order.append(f"checks after {len(_up_log(world))}")
        or real_checks(t, stale),
    )
    _write_request(world, repo=str(repo), mode="move", into="dev1-work")
    assert rs.execute() == 0
    row = _rows(world)[-1]
    new = row.get("new_sid")
    assert row["outcome"] == "ok", row
    assert row["mode"] == "move" and row["into"] == "dev1-work" and row["old_exit"] == "gone", row
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", new
    ), row
    assert new != SID and row["old_sid"] == SID and row["predecessor_row"] is False, row
    log = _up_log(world)
    assert (
        log[0] == f"ARGV --pane-cmd {repo} dev1 {new} --into dev1-work --from {SID} --replacing 102"
    ), log
    assert (
        log[1] == "PATH=/pane/bin:/usr/bin" and log[2] == "AGENT_IDENTITY_FILE=/pane/identity.jsonl"
    ), log
    assert order and all(o == "checks after 3" for o in order), (
        order
    )  # the pane command came before every check
    (respawn,) = _respawns(world)
    assert respawn == [
        "-k",
        "-t",
        "%5",
        "-c",
        str(wt),
        f"claude -n dev1 --session-id {new} 'You were moved'",
    ]
    assert _keys(world) == [] and world["signals"] == []


def test_w_e38f8ee7_move_refusals_and_partials(world, monkeypatch):
    """B3: a pane-command refusal rows `refused:launch` and a failed check `refused:<check>`, with no respawn; a
    transcript written between the last two reads refuses `idle` with no respawn; a session that never registers rows
    `partial:launch`, one that never re-binds `partial:rebind`; an old claude that outlives the respawn gets SIGTERM
    then SIGKILL, by pid, and the row says `survived`."""
    import signal

    repo, wt = _move_world(world, monkeypatch)
    log = Path(os.environ["FAKE_UP_LOG"])
    log.with_name(log.name + ".refuse").write_text("")
    _write_request(world, repo=str(repo), mode="move", into="dev1-work")
    rs.execute()
    row = _rows(world)[-1]
    assert row["outcome"] == "refused:launch" and "the pane changed" in row["reason"], row
    log.with_name(log.name + ".refuse").unlink()
    _set(world, screen=IDLE_SCREEN.replace("❯ ", "❯ typed"))
    _write_request(world, repo=str(repo), mode="move", into="dev1-work")
    rs.execute()
    assert _rows(world)[-1]["outcome"] == "refused:screen"
    _set(world, screen=IDLE_SCREEN)

    def bump(s: float) -> None:  # the session writes during the last re-read
        if s == rs.DISCARD_RECHECK_S:
            st = world["transcript"].stat()
            os.utime(
                world["transcript"], (st.st_atime, st.st_mtime - 5)
            )  # a change, never into the future

    _rs_time(monkeypatch, sleep=bump)
    _write_request(world, repo=str(repo), mode="move", into="dev1-work")
    rs.execute()
    assert _rows(world)[-1]["outcome"] == "refused:idle", _rows(world)[-1]
    assert _respawns(world) == [] and world["signals"] == []
    _rs_time(monkeypatch, sleep=lambda s: None)
    # neither case binds the new id, so dev1 stays bound to SID for the next request
    for registers, binds, outcome in (
        (False, False, "partial:launch"),
        (True, False, "partial:rebind"),
    ):
        monkeypatch.setenv("MOVE_REGISTERS", "1" if registers else "0")
        monkeypatch.setenv("MOVE_BINDS", "1" if binds else "0")
        (world["proc"] / "102" / "stat").write_text("102 (claude) S 101" + " 0" * 17 + " 777\n")
        _write_request(world, repo=str(repo), mode="move", into="dev1-work")
        rs.execute()
        assert _rows(world)[-1]["outcome"] == outcome, _rows(world)[-1]
    # the old claude never exits: TERM, then KILL, to that pid; the row says so and the move still completes
    monkeypatch.setenv("MOVE_REGISTERS", "1")
    monkeypatch.setenv("MOVE_BINDS", "1")
    (world["proc"] / "102" / "stat").write_text("102 (claude) S 101" + " 0" * 17 + " 777\n")
    _set(world, on_respawn=RESPAWN_OK.replace("open(p, 'w')", "0 and open(p, 'w')"))
    _write_request(world, repo=str(repo), mode="move", into="dev1-work")
    rs.execute()
    row = _rows(world)[-1]
    assert row["outcome"] == "ok" and row["old_exit"] == "survived", row
    assert world["signals"] == [(102, signal.SIGTERM), (102, signal.SIGKILL)], world["signals"]


def test_w_e38f8ee7_review_p1_the_last_look_and_a_zombie(world, monkeypatch):
    """Review pass 1 (A-C1, A-C5, A-C2): a turn that STARTED during run_checks' own git calls wrote its first row before
    the last re-read, whose two reads then agree — the re-read still refuses, because the turn end is no longer the
    transcript's last real row; a box that holds text only at the last re-read refuses `screen`; neither respawns. An
    old claude that is a zombie (exited, not yet reaped) is gone, never signalled."""
    import signal

    repo, wt = _move_world(world, monkeypatch)
    real_state = rs.hib.worktree_state

    def turn_starts(path):  # a prompt arrives while the worktree probe runs
        with world["transcript"].open("a") as fh:
            fh.write(json.dumps({"type": "user", "timestamp": "2026-10-23T00:00:05Z"}) + "\n")
        return real_state(path)

    monkeypatch.setattr(rs.hib, "worktree_state", turn_starts)
    _write_request(world, repo=str(repo), mode="move", into="dev1-work")
    rs.execute()
    row = _rows(world)[-1]
    assert row["outcome"] == "refused:idle", row
    monkeypatch.setattr(rs.hib, "worktree_state", lambda path: (False, "clean, pushed"))
    world["transcript"].write_text(
        "".join(
            json.dumps(r) + "\n"
            for r in (
                {"type": "assistant", "timestamp": "2026-10-23T00:00:00Z"},
                {"type": "system", "subtype": "turn_duration", "timestamp": "2026-10-23T00:00:01Z"},
            )
        )
    )
    real_box = rs._box_now
    reads = {"n": 0}

    def typed_late(
        pane,
    ):  # run_checks' read sees an empty box; the last re-read's second read sees text
        reads["n"] += 1
        box, screen = real_box(pane)
        return ("half typed", screen) if reads["n"] >= 3 else (box, screen)

    monkeypatch.setattr(rs, "_box_now", typed_late)
    _write_request(world, repo=str(repo), mode="move", into="dev1-work")
    rs.execute()
    assert _rows(world)[-1]["outcome"] == "refused:screen", _rows(world)[-1]
    assert _respawns(world) == [] and world["signals"] == []
    monkeypatch.setattr(rs, "_box_now", real_box)
    # the old claude is a zombie after the respawn: gone at once, no signal sent
    _set(
        world,
        on_respawn=RESPAWN_OK.replace("(claude) S 101", "(claude) Z 101").replace("' 999", "' 777"),
    )
    _write_request(world, repo=str(repo), mode="move", into="dev1-work")
    rs.execute()
    row = _rows(world)[-1]
    assert row["outcome"] == "ok" and row["old_exit"] == "gone", row
    assert world["signals"] == [], world["signals"]
    assert signal.SIGKILL not in [s for _, s in world["signals"]]


def test_w_e38f8ee7_validate_into_only_with_move(world):
    """B4: `into` rides only on a move request, and a move request needs a valid one; anything else is
    `refused:request`, so an older unit reading a move file refuses it too (fail closed)."""
    for over in (
        {"mode": "move"},
        {"mode": "move", "into": "Bad/x"},
        {"mode": "move", "into": 7},
        {"mode": "clear", "into": "dev1-work"},
        {"mode": "compact", "focus": "f", "into": "dev1-work"},
    ):
        _write_request(world, **over)
        rs.execute()
        assert _rows(world)[-1]["outcome"] == "refused:request", (over, _rows(world)[-1])


def test_w_e38f8ee7_the_move_worst_case_fits():
    """B5: the move path's own waits — the pane command, the last re-read, the respawn, the reap, the launch wait, the
    agents lock and the re-bind grace, with its tmux calls and loop sleeps — stay under REQUEST_WORST_S, so the claim
    cutoff the unit's timeout was derived from still holds."""
    assert rs.MOVE_WORST_S == (
        rs.PANE_CMD_TIMEOUT_S
        + rs.DISCARD_RECHECK_S
        + rs.OLD_EXIT_S
        + rs.OLD_TERM_S
        + rs.OLD_KILL_S
        + rs.CLEAR_WAIT_S
        + rs.AGENTS_LOCK_WAIT_S
        + rs.REBIND_GRACE_S
        + 5
        + 8 * rs.TMUX_TIMEOUT_S
    )
    assert rs.MOVE_WORST_S <= rs.REQUEST_WORST_S
