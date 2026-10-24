"""Behavior Contract — scripts/sysadmin/rotate_session.py (W-f975fee0 slice 2, D-1123, D-1135).

The coordinator's verb (`request`) resolves an agent's pane, claude process and session, runs six checks that each fail
CLOSED, and writes ONE data-only request; the user unit's `execute` claims it, re-runs every check, types fixed templates,
verifies through the registry and the identity store, and rows every outcome. Everything runs against a fake world: a
scripted tmux, a fake /proc tree, a registry, an identity store, a transcript and the run records.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "rotate_session.py"
spec = importlib.util.spec_from_file_location("rotate_session", SCRIPT)
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)

SID = "11111111-1111-4111-8111-111111111111"
NEW = "22222222-2222-4222-8222-222222222222"
IDLE_SCREEN = (
    "some output\n────────────\n❯\u00a0\n────────────\n  Opus · ctx 41%\n  ⏵⏵ auto mode on\n"
)
FAKE_TMUX = """#!/usr/bin/env python3
import json, os, sys
st = json.load(open(os.environ["FAKE_TMUX_STATE"]))
a = sys.argv[1:]
if a[0] == "list-panes":
    print("\\n".join(st["panes"]))
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
    monkeypatch.setattr(rs.time, "sleep", lambda s: None)
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
    with pytest.raises(rs.CheckFailedError, match="stale"):
        rs.resolve("dev1", "/opt/x")


@pytest.mark.parametrize(
    "spoil, check",
    [
        ("fresh", "status"),
        ("midturn", "idle"),
        ("slash", "idle"),
        ("record", "record"),
        ("seat", "seat"),
        ("worktree", "worktree"),
        ("typed", "screen"),
        ("dialog", "screen"),
    ],
)
def test_request_aborts_on_each_check_in_order(world, monkeypatch, spoil, check):
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
        rec = world["home"] / ".claude" / "state" / "command-runs" / f"{SID}.json"
        rec.parent.mkdir(parents=True)
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
    assert rs.request("dev1", "/opt/x", None, "manual") == 1
    assert not list(world["req"].glob("*.json"))
    assert _rows(world)[-1]["outcome"] == f"aborted:{check}", _rows(world)


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
    assert rs.request("dev1", "/opt/x", "finish the parser", "compact") == 1  # one at a time
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
    monkeypatch.setattr(rs.time, "sleep", lambda s: sleeps.append(s))
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


def test_wb72231b8_registry_is_repointed(world, monkeypatch, tmp_path):
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


def test_wb72231b8_an_unsent_resume_still_repoints(world, monkeypatch, tmp_path):
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


def test_wb72231b8_registry_os_errors_are_a_recorded_state(tmp_path):
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


def test_wb72231b8_registry_over_the_readers_cap_is_refused(tmp_path, monkeypatch):
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
def test_wb72231b8_registry_states_never_write_a_bad_file(tmp_path, content, state):
    """W-b72231b8: every registry state other than a re-pointable entry is recorded and leaves the file
    byte-identical; nothing the writer emits is a shape agents_up.sh refuses."""
    regf = tmp_path / "session-agents.json"
    if content is not None:
        regf.write_text(content if isinstance(content, str) else json.dumps(content))
    before = regf.read_bytes() if regf.exists() else None
    assert rs._repoint_registry(regf, SID, NEW, "dev1") == state
    assert (regf.read_bytes() if regf.exists() else None) == before


def test_wb72231b8_registry_refuses_a_symlink_and_a_bad_new_id(tmp_path):
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
    tmp_path, monkeypatch
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


def _late_bind(world, monkeypatch, bind_after: float | None) -> dict:
    """A fake clock that moves only when the script sleeps, with ROTATE_WAIT_S unset so each wait runs at its
    production length (the fake panes settle at once, so the waits before the re-bind end early). The identity store
    gains the re-bind `bind_after` s after the resume prompt, or never when None. Returns the times seen."""
    monkeypatch.delenv("ROTATE_WAIT_S")
    clock = {"now": time.time()}
    monkeypatch.setattr(rs.time, "time", lambda: clock["now"])
    monkeypatch.setattr(rs.time, "sleep", lambda s: clock.__setitem__("now", clock["now"] + s))
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
    monkeypatch.setattr(rs.time, "monotonic", lambda: mono["now"])
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
    one integer TimeoutStartSec and no TimeoutSec that could override it."""
    unit = (REPO / "scripts" / "sysadmin" / "fabrik-rotate.service").read_text().splitlines()
    starts = [ln.strip() for ln in unit if ln.strip().startswith("TimeoutStartSec")]
    assert len(starts) == 1 and re.fullmatch(r"TimeoutStartSec=\d+", starts[0]), starts
    assert not [ln for ln in unit if ln.strip().startswith("TimeoutSec")]
    timeout = int(starts[0].split("=", 1)[1])
    assert rs.REQUEST_WORST_S == (
        2
        + rs.DISCARD_WAIT_S
        + 2 * (rs.SEND_SETTLE_S + rs.SEND_SUBMIT_S)
        + rs.CLEAR_WAIT_S
        + rs.REBIND_GRACE_S
        + 17 * rs.TMUX_TIMEOUT_S
    )
    assert timeout >= rs.CLAIM_CUTOFF_S + rs.REQUEST_WORST_S + 60, (rs.REQUEST_WORST_S, timeout)
    assert rs.REBIND_GRACE_S >= 98
    src = SCRIPT.read_text()
    assert not re.findall(r"_wait_s\(\s*\d", src), (
        "a wait passed as a literal escapes REQUEST_WORST_S"
    )
    tmux_src = inspect.getsource(rs._tmux)
    assert "timeout=TMUX_TIMEOUT_S" in tmux_src and not re.findall(r"timeout=\d", tmux_src)
