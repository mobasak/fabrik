"""Behavior Contract — scripts/sysadmin/rotate_session.py (W-f975fee0 slice 2, D-1123, D-1135).

The coordinator's verb (`request`) resolves an agent's pane, claude process and session, runs six checks that each fail
CLOSED, and writes ONE data-only request; the user unit's `execute` claims it, re-runs every check, types fixed templates,
verifies through the registry and the identity store, and rows every outcome. Everything runs against a fake world: a
scripted tmux, a fake /proc tree, a registry, an identity store, a transcript and the run records.
"""

from __future__ import annotations

import importlib.util
import json
import os
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
    sys.stdout.write(st["screen"])
elif a[0] == "send-keys":
    with open(os.environ["FAKE_TMUX_STATE"] + ".keys", "a") as fh:
        fh.write(json.dumps(a[1:]) + "\\n")
    hook = st.get("on_send")
    if hook and "-l" in a:
        exec(hook, {"text": a[-1], "os": os, "json": json})
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
        "STATUSLINE_CACHE_FILE": tmp_path / "none.json",
    }.items():
        monkeypatch.setenv(k, str(v))
    monkeypatch.setattr(rs.hib, "worktree_state", lambda path: (False, "clean, pushed"))
    monkeypatch.setattr(rs.hib, "live_sessions", lambda home, proc, opt="/opt": [])
    monkeypatch.setattr(rs.time, "sleep", lambda s: None)
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
        ("status", "status"),
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
    if spoil == "status":
        reg["status"] = "busy"
    elif spoil == "fresh":
        reg["statusUpdatedAt"] = time.time() * 1000
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
    assert row["trigger"] == "ctx" and row["ctx_pre"] == 450000
    keys = _keys(world)
    assert (
        keys[0][:4] == ["-t", "%5", "-l", "--"]
        and keys[0][4].startswith("/clear dev1-")
        and keys[1] == ["-t", "%5", "Enter"]
    )
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


# ── slice 3 (W-f975fee0): `due`, the lift offer, the nightly mail, the private request dir ──────────────────────────


def _hermetic(monkeypatch, tmp_path):
    monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(tmp_path / "no-hub.env"))
    monkeypatch.delenv("ROTATE_ADVISE_MB", raising=False)
    monkeypatch.delenv("ROTATE_CONTEXT_WINDOW", raising=False)


def test_transcript_hardlinked_names_are_one(world):
    """Every tmux session's transcript has two hard-linked names (one inode); a dangling or a distinct second refuses."""
    other = world["config"] / "projects" / "-opt-x--claude-worktrees-dev1"
    other.mkdir()
    os.link(world["transcript"], other / f"{SID}.jsonl")
    assert rs._transcript(world["proc"], world["home"], 102, SID) == world["transcript"]
    (other / f"{SID}.jsonl").unlink()
    (other / f"{SID}.jsonl").symlink_to(world["tmp"] / "nowhere")
    with pytest.raises(rs.CheckFailedError, match="unreadable"):
        rs._transcript(world["proc"], world["home"], 102, SID)
    (other / f"{SID}.jsonl").unlink()
    (other / f"{SID}.jsonl").write_text(world["transcript"].read_text())
    with pytest.raises(rs.CheckFailedError, match="2 transcripts"):
        rs._transcript(world["proc"], world["home"], 102, SID)


def _session(agent, entrypoint="cli", sid=SID, repo="/opt/x", pid=102):
    return {"pid": pid, "ppid": 1, "sid": sid, "cwd": repo, "peer": agent, "entrypoint": entrypoint,
            "agent": agent, "repo": repo}


def test_due_rows_and_actions(world, monkeypatch):
    _hermetic(monkeypatch, world["tmp"])
    sessions = [_session("dev1"), _session("coordinator", "claude-vscode"), _session("seat", "sdk-cli"),
                _session(""), _session("dev2", sid=NEW)]
    monkeypatch.setattr(rs.hib, "live_sessions", lambda home, proc, opt="/opt": sessions)
    rows = rs.due(world["home"], world["proc"])
    by = {r["agent"]: r for r in rows}
    assert set(by) == {"dev1", "coordinator", "", "dev2"}, rows  # the pool seat is never a row
    assert (by["dev1"]["state"], by["dev1"]["trigger"], by["dev1"]["ctx"]) == ("due", "ctx", 45)
    assert rs.offer(by["dev1"]) == "/opt/fabrik/scripts/sysadmin/agents_up.sh rotate-session dev1 --repo /opt/x --trigger ctx"
    assert "operator types `/clear coordinator-" in rs.offer(by["coordinator"])
    assert by[""]["state"] == "unread" and "agent" in by[""]["reason"]
    assert by["dev2"]["state"] == "unread" and "0 transcripts" in by["dev2"]["reason"]
    # --mb-only reads no context: a 45% session under the MB line is not due
    monkeypatch.setattr(rs.tsc, "_context_tokens", lambda p: (_ for _ in ()).throw(AssertionError("ctx read")))
    assert {r["agent"] for r in rs.due(world["home"], world["proc"], mb_only=True)} == {"", "dev2"}
    monkeypatch.setenv("ROTATE_ADVISE_MB", "1")  # the hook's own threshold reader decides the MB line
    with world["transcript"].open("a") as fh:
        fh.write(json.dumps({"type": "pad", "x": "y" * (1024 * 1024)}) + "\n")
    mb = {r["agent"]: r for r in rs.due(world["home"], world["proc"], mb_only=True)}
    assert (mb["dev1"]["state"], mb["dev1"]["trigger"], mb["dev1"]["ctx"]) == ("due", "mb", None)


def test_due_mail_per_repo(world, monkeypatch):
    root = Path(os.environ["FABRIK_MAIL_ROOT"])  # conftest's tmp mail root: nothing reaches a live mailbox
    rows = [dict(_session("fleet", repo="/opt/fabrik"), state="due", trigger="mb", mb=210, ctx=None),
            dict(_session("coordinator", "claude-vscode", repo="/opt/fabrik"), state="due", trigger="mb", mb=425, ctx=None),
            dict(_session("dev1", repo="/opt/fabrik-lib"), state="unread", reason="transcript: 0 transcripts"),
            dict(_session("x", repo=""), state="due", trigger="mb", mb=300, ctx=None)]
    assert rs.mail_due([]) == 0 and not list(root.glob("*/inbox/*.md"))
    assert rs.mail_due(rows) == 0
    hub = list((root / "fabrik" / "inbox").glob("*.md"))
    lib = list((root / "fabrik-lib" / "inbox").glob("*.md"))
    assert len(hub) == 1 and len(lib) == 1, (hub, lib)
    text = hub[0].read_text()
    assert "agent: coordinator" in text and "ack: no" in text and "rotate-session fleet" in text
    assert "operator types" in text and "never typed for you" in text
    assert "unread" in lib[0].read_text()
    bad = [dict(_session("y", repo="/opt/no-such-repo-zz"), state="due", trigger="mb", mb=300, ctx=None)] + rows[:1]
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
    assert starts[-1] == ("ExecStart=-/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sysadmin/rotate_session.py "
                          "due --mb-only --mail")
    assert "prune_transcripts.py" in starts[-2]
    path = (REPO / "scripts" / "sysadmin" / "fabrik-rotate.path").read_text()
    assert "MakeDirectory" not in path and "DirectoryMode" not in path
    assert "install -d -m 0700" in (REPO / "scripts" / "sysadmin" / "install_rotate_unit.sh").read_text()
