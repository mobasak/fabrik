"""Tests for scripts/sysadmin/fabrik_deck.py — the Deck's code-server as a systemd user service (W-e89a9b5b, D-1106).

Every test drives the script as a subprocess against a temporary HOME. `systemctl` and `loginctl` are fake executables
on PATH that record their argv; `code-server` is a fake at <HOME>/.local/bin/code-server (the script execs it by that
absolute path). `systemd-analyze` is the real tool, skipped where it is absent.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "fabrik_deck.py"
UNIT = "fabrik-deck-code.service"

# The fakes run under this interpreter by absolute path, so a test may drop /usr/bin from PATH.
FAKE = (
    f"""#!{sys.executable}
"""
    + """import json, os, sys
log = os.environ["FAKE_LOG"]
with open(log, "a") as f:
    f.write(json.dumps({{"tool": {tool!r}, "argv": sys.argv[1:]}}) + "\\n")
out = os.environ.get("FAKE_{upper}_STDOUT", "")
if out:
    print(out)
err = os.environ.get("FAKE_{upper}_STDERR", "")
if err:
    print(err, file=sys.stderr)
if os.environ.get("FAKE_{upper}_FAIL_VERB") in sys.argv[1:3]:
    sys.exit(1)
sys.exit(int(os.environ.get("FAKE_{upper}_RC", "0")))
"""
)

FAKE_CODE_SERVER = (
    f"""#!{sys.executable}
"""
    + """
import json, os, sys
with open(os.path.join(os.environ["HOME"], "..", "cs.json"), "w") as f:  # HOME survives the keep-list
    json.dump({"argv": sys.argv[1:], "env": dict(os.environ)}, f)
"""
)


def _exe(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture()
def box(tmp_path: Path):
    """A temp HOME with fakes; returns a helper that runs the script there."""
    home = tmp_path / "home"
    fakebin = tmp_path / "fakebin"
    hub = tmp_path / "hub"
    (hub / "scripts" / "sysadmin").mkdir(parents=True)
    (hub / "scripts" / "sysadmin" / "fabrik_deck.py").write_text("# stand-in for the hub copy\n")
    _exe(home / ".local" / "bin" / "code-server", FAKE_CODE_SERVER)
    for tool in ("systemctl", "loginctl"):
        _exe(fakebin / tool, FAKE.format(tool=tool, upper=tool.upper()))
    analyze = shutil.which("systemd-analyze")
    if analyze:
        os.symlink(analyze, fakebin / "systemd-analyze")
    log = tmp_path / "calls.jsonl"
    log.touch()

    class Box:
        pass

    b = Box()
    b.home, b.hub, b.log, b.tmp, b.fakebin = home, hub, log, tmp_path, fakebin
    b.has_analyze = analyze is not None
    b.env = {
        "HOME": str(home),
        "PATH": f"{fakebin}:/usr/bin:/bin",
        "FAKE_LOG": str(log),
        "FAKE_LOGINCTL_STDOUT": "Linger=yes",
        "LANG": "C.UTF-8",
    }
    if os.environ.get("XDG_RUNTIME_DIR"):
        b.env["XDG_RUNTIME_DIR"] = os.environ["XDG_RUNTIME_DIR"]

    def run(*args: str, input: str | None = None, **extra: str) -> subprocess.CompletedProcess:
        env = dict(b.env)
        env.update(extra)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            env=env,
            input=input,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def calls(tool: str) -> list[list[str]]:
        return [
            c["argv"] for c in map(json.loads, log.read_text().splitlines()) if c["tool"] == tool
        ]

    b.run, b.calls = run, calls
    b.unit_path = home / ".config" / "systemd" / "user" / UNIT
    b.env_file = home / ".config" / "fabrik-deck" / "env"
    return b


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# 1 ---------------------------------------------------------------------------------------------------------------
def test_code_server_env_is_the_keep_list(box):
    r = box.run(
        "code-server",
        CLAUDE_AGENT="fleet",
        CLAUDE_CODE_SESSION_ID="abc",
        CLAUDE_CONFIG_DIR="/x/active",
        CLAUDE_QUOTA_HOME="/x/active",
        FABRIK_DECK="1",
        SHELL="/bin/bash",
        DISPLAY=":0",
    )
    assert r.returncode == 0, r.stderr
    got = json.loads((box.tmp / "cs.json").read_text())["env"]
    assert (
        "CLAUDE_AGENT" not in got and "CLAUDE_CODE_SESSION_ID" not in got and "FAKE_LOG" not in got
    )
    for key in (
        "HOME",
        "PATH",
        "LANG",
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_QUOTA_HOME",
        "FABRIK_DECK",
        "SHELL",
        "DISPLAY",
    ):
        assert key in got, key
    assert set(got) <= {
        "HOME",
        "USER",
        "LOGNAME",
        "SHELL",
        "PATH",
        "LANG",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XDG_RUNTIME_DIR",
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_QUOTA_HOME",
        "FABRIK_DECK",
    } | {"LC_CTYPE"}  # the interpreter may add LC_CTYPE under a C locale


# 2 ---------------------------------------------------------------------------------------------------------------
def test_code_server_bind_addr_and_bad_port(box):
    r = box.run("code-server")
    assert r.returncode == 0, r.stderr
    assert json.loads((box.tmp / "cs.json").read_text())["argv"] == [
        "--bind-addr",
        "127.0.0.1:8443",
    ]
    r = box.run("code-server", FABRIK_DECK_CODE_PORT="9123")
    assert json.loads((box.tmp / "cs.json").read_text())["argv"] == [
        "--bind-addr",
        "127.0.0.1:9123",
    ]
    for bad in ("0", "65536", "84x3", ""):
        (box.tmp / "cs.json").unlink(missing_ok=True)
        r = box.run("code-server", FABRIK_DECK_CODE_PORT=bad)
        assert r.returncode == 2, (bad, r.returncode, r.stderr)
        assert "FABRIK_DECK_CODE_PORT" in r.stderr
        assert not (box.tmp / "cs.json").exists()


# 3 ---------------------------------------------------------------------------------------------------------------
def test_unit_verifies_and_carries_policy(box):
    if not box.has_analyze:
        pytest.skip("systemd-analyze not installed")
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 0, r.stderr
    text = box.unit_path.read_text()
    sections: dict[str, list[str]] = {}
    current = ""
    for line in text.splitlines():
        if line.startswith("["):
            current = line
        elif "=" in line and not line.startswith("#"):
            sections.setdefault(current, []).append(line)
    assert "StartLimitIntervalSec=0" in sections["[Unit]"]
    svc = sections["[Service]"]
    assert "Restart=always" in svc and "RestartSec=10" in svc
    assert f"EnvironmentFile={box.env_file}" in svc
    assert (
        f"ExecStart=/usr/bin/python3 {box.hub}/scripts/sysadmin/fabrik_deck.py code-server" in svc
    )
    assert "WantedBy=default.target" in sections["[Install]"]
    v = subprocess.run(
        ["systemd-analyze", "--user", "verify", str(box.unit_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert v.returncode == 0 and v.stderr.strip() == "", v.stderr


# 4 ---------------------------------------------------------------------------------------------------------------
def test_install_env_file_keeps_lines_appends_missing(box):
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 0, r.stderr
    first = box.env_file.read_text()
    assert "FABRIK_DECK_CODE_PORT=8443\n" in first and "FABRIK_DECK=1\n" in first
    assert f"CLAUDE_CONFIG_DIR={box.home}/.claude-fleet/active\n" in first
    # an operator override and a removed key: the override stays, the removed key comes back, and is named
    edited = first.replace("FABRIK_DECK_CODE_PORT=8443", "FABRIK_DECK_CODE_PORT=9000").replace(
        "FABRIK_DECK=1\n", ""
    )
    edited += "# operator note\n"
    box.env_file.write_text(edited)
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 0, r.stderr
    after = box.env_file.read_text()
    assert after.startswith(edited)
    assert after[len(edited) :] == "FABRIK_DECK=1\n"
    assert "FABRIK_DECK" in r.stderr and "FABRIK_DECK_CODE_PORT" not in r.stderr.replace(
        "FABRIK_DECK=", ""
    )
    # all keys present: byte-identical
    r = box.run("install", "--hub", str(box.hub))
    assert box.env_file.read_text() == after


# 5 ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("case", ["linger-no", "linger-silent", "no-hub-script", "no-code-server"])
def test_install_hard_stops(box, case):
    extra = {}
    hub = box.hub
    if case == "linger-no":
        extra["FAKE_LOGINCTL_STDOUT"] = "Linger=no"
    elif case == "linger-silent":
        extra["FAKE_LOGINCTL_STDOUT"] = ""
        extra["FAKE_LOGINCTL_RC"] = "1"
    elif case == "no-hub-script":
        hub = box.tmp / "missing-hub"
    else:
        (box.home / ".local" / "bin" / "code-server").unlink()
    r = box.run("install", "--hub", str(hub), **extra)
    assert r.returncode == 1, (case, r.stdout, r.stderr)
    assert not box.unit_path.exists()
    assert box.calls("systemctl") == []


# 6 ---------------------------------------------------------------------------------------------------------------
def test_install_refuses_foreign_unit(box):
    box.unit_path.parent.mkdir(parents=True)
    box.unit_path.write_text("[Unit]\nDescription=someone else's\n")
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 1
    assert box.unit_path.read_text() == "[Unit]\nDescription=someone else's\n"
    assert box.calls("systemctl") == []


# 7 ---------------------------------------------------------------------------------------------------------------
def test_install_enables_starts_only_when_asked_and_free(box):
    port = _free_port()
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text(f"FABRIK_DECK_CODE_PORT={port}\n")
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 0, r.stderr
    verbs = [a[1] for a in box.calls("systemctl")]
    assert verbs[:2] == ["daemon-reload", "enable"] and "start" not in verbs
    box.log.write_text("")
    r = box.run("install", "--hub", str(box.hub), "--start")
    assert r.returncode == 0, r.stderr
    assert "start" in [a[1] for a in box.calls("systemctl")]
    # port held: refused before start
    box.log.write_text("")
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))
        s.listen()
        r = box.run("install", "--hub", str(box.hub), "--start")
    assert r.returncode == 1 and str(port) in r.stderr
    assert "start" not in [a[1] for a in box.calls("systemctl")]
    # a failing systemctl is a hard stop
    box.log.write_text("")
    r = box.run("install", "--hub", str(box.hub), FAKE_SYSTEMCTL_RC="1")
    assert r.returncode == 1


# Review pass 1 (W-e89a9b5b): the guards the first tests did not reach -------------------------------------------
def test_code_server_env_keeps_every_listed_key(box):
    keep = {
        "USER": "u",
        "LOGNAME": "u",
        "SHELL": "/bin/bash",
        "DISPLAY": ":0",
        "WAYLAND_DISPLAY": "w",
        "XDG_RUNTIME_DIR": "/run/user/1",
        "CLAUDE_CONFIG_DIR": "/a",
        "CLAUDE_QUOTA_HOME": "/a",
        "FABRIK_DECK": "1",
    }
    r = box.run("code-server", **keep)
    assert r.returncode == 0, r.stderr
    got = json.loads((box.tmp / "cs.json").read_text())["env"]
    for key, value in keep.items():
        assert got.get(key) == value, key


def test_code_server_startup_failures_exit_2(box):
    r = box.run("code-server", FABRIK_DECK_CODE_PORT="\u00b2")  # "²".isdigit() is True
    assert r.returncode == 2 and "Traceback" not in r.stderr, r.stderr
    (box.home / ".local" / "bin" / "code-server").unlink()
    r = box.run("code-server")
    assert r.returncode == 2 and "Traceback" not in r.stderr, r.stderr


def test_unit_stops_on_a_startup_failure(box):
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 0, r.stderr
    service = box.unit_path.read_text().split("[Service]")[1].split("[Install]")[0]
    assert "RestartPreventExitStatus=2" in service


@pytest.mark.parametrize(
    "case", ["verify-warns", "verify-stdout", "hub-space", "bad-port", "no-systemd-analyze"]
)
def test_install_refuses_before_any_write(box, case):
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text("FABRIK_DECK=1\n")
    extra = {}
    hub = box.hub
    if case in ("verify-warns", "verify-stdout"):
        (box.fakebin / "systemd-analyze").unlink(missing_ok=True)
        _exe(box.fakebin / "systemd-analyze", FAKE.format(tool="systemd-analyze", upper="ANALYZE"))
        stream = "STDERR" if case == "verify-warns" else "STDOUT"
        extra[f"FAKE_ANALYZE_{stream}"] = "Unknown key name 'X' in section 'Service', ignoring."
    elif case == "hub-space":
        hub = box.tmp / "my hub"
        (hub / "scripts" / "sysadmin").mkdir(parents=True)
        (hub / "scripts" / "sysadmin" / "fabrik_deck.py").write_text("#\n")
    elif case == "bad-port":
        box.env_file.write_text("FABRIK_DECK=1\nFABRIK_DECK_CODE_PORT=9000 # mine\n")
    else:
        (box.fakebin / "systemd-analyze").unlink(missing_ok=True)
        extra["PATH"] = str(box.fakebin)
    before = box.env_file.read_text()
    r = box.run("install", "--hub", str(hub), **extra)
    assert r.returncode == 1, (case, r.stderr)
    assert "Traceback" not in r.stderr, r.stderr
    if case == "no-systemd-analyze":
        assert "systemd-analyze is not installed" in r.stderr
    assert box.env_file.read_text() == before
    assert not box.unit_path.exists()
    assert box.calls("systemctl") == []


def test_install_env_file_reads_like_systemd(box):
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text(
        'FABRIK_DECK_CODE_PORT="9000"\nexport FABRIK_DECK=1\n; note\nPATH=/x'
    )  # no final newline
    box.env_file.chmod(0o600)
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 0, r.stderr
    after = box.env_file.read_text()
    assert after.startswith('FABRIK_DECK_CODE_PORT="9000"\nexport FABRIK_DECK=1\n; note\nPATH=/x\n')
    appended = after.splitlines()[4:]
    assert [line.split("=")[0] for line in appended] == [
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_QUOTA_HOME",
        "FABRIK_DECK",
        "DISPLAY",
        "WAYLAND_DISPLAY",
    ]
    assert r.stderr.count("ignoring 'export FABRIK_DECK=1'") == 1, r.stderr
    assert (
        "appending missing keys CLAUDE_CONFIG_DIR, CLAUDE_QUOTA_HOME, FABRIK_DECK, DISPLAY, WAYLAND_DISPLAY"
        in r.stderr
    )
    assert stat.S_IMODE(box.env_file.stat().st_mode) == 0o600


@pytest.mark.parametrize("verb", ["daemon-reload", "enable", "start"])
def test_install_stops_on_each_failing_systemctl_verb(box, verb):
    port = _free_port()
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text(f"FABRIK_DECK_CODE_PORT={port}\n")
    r = box.run("install", "--hub", str(box.hub), "--start", FAKE_SYSTEMCTL_FAIL_VERB=verb)
    assert r.returncode == 1 and verb in r.stderr, r.stderr
    verbs = [a[1] for a in box.calls("systemctl")]
    assert verbs[-1] == verb and "is-enabled" not in verbs


def test_install_accepts_a_single_quoted_port(box):
    port = _free_port()
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text(f"FABRIK_DECK_CODE_PORT='{port}'\n")
    r = box.run("install", "--hub", str(box.hub), "--start")
    assert r.returncode == 0, r.stderr


# --- the attention hook (plan 2026-10-22-plan-1-fabrik-deck, Phase A; spec § Tests 1-2) ---------------------------
SID = "0f1e2d3c-aaaa-bbbb-cccc-123456789abc"


def _hook(box, event: str, state: Path, sid: str = SID, cwd: str = "/opt/youtube", **extra):
    payload = {"hook_event_name": event, "session_id": sid, "cwd": cwd}
    payload.update(extra.pop("payload", {}))
    env = {"FABRIK_DECK_STATE": str(state)}
    env.update(extra)
    return box.run("hook", input=json.dumps(payload), **env)


def _att(state: Path, sid: str = SID) -> Path:
    return state / "attention" / f"{sid}.json"


@pytest.mark.parametrize("ntype", ["permission_prompt", "idle_prompt", "elicitation_dialog"])
def test_hook_notification_waiting_types_write_the_file(box, tmp_path, ntype):
    state = tmp_path / "state"
    r = _hook(box, "Notification", state, payload={"notification_type": ntype})
    assert r.returncode == 0 and r.stdout == ""
    data = json.loads(_att(state).read_text())
    assert data["type"] == ntype and data["cwd"] == "/opt/youtube" and isinstance(data["at"], float)


def test_hook_ignores_other_notification_types(box, tmp_path):
    state = tmp_path / "state"
    for ntype in ("auth_success", "elicitation_url_dialog", "", None):
        r = _hook(box, "Notification", state, payload={"notification_type": ntype})
        assert r.returncode == 0 and r.stdout == ""
    assert not _att(state).exists()


@pytest.mark.parametrize("clearer", ["UserPromptSubmit", "SessionEnd"])
def test_hook_stop_marks_turn_ended_and_prompt_or_end_clears(box, tmp_path, clearer):
    state = tmp_path / "state"
    _hook(box, "Stop", state)
    assert json.loads(_att(state).read_text())["type"] == "turn_ended"
    r = _hook(box, clearer, state)
    assert r.returncode == 0 and r.stdout == ""
    assert not _att(state).exists()


def test_hook_post_tool_use_clears_only_a_permission_prompt(box, tmp_path):
    state = tmp_path / "state"
    _hook(box, "Notification", state, payload={"notification_type": "idle_prompt"})
    _hook(box, "PostToolUse", state)
    assert json.loads(_att(state).read_text())["type"] == "idle_prompt"
    _hook(box, "Notification", state, payload={"notification_type": "permission_prompt"})
    _hook(box, "PostToolUse", state)
    assert not _att(state).exists()


def test_hook_origin_tmux_wins_then_deck_then_other(box, tmp_path):
    state = tmp_path / "state"
    _hook(box, "Stop", state, TMUX="/tmp/tmux-1000/default,1,0", FABRIK_DECK="1")
    assert json.loads(_att(state).read_text())["origin"] == "tmux"
    _hook(box, "Stop", state, FABRIK_DECK="1")
    assert json.loads(_att(state).read_text())["origin"] == "deck"
    _hook(box, "Stop", state)
    assert json.loads(_att(state).read_text())["origin"] == "other"


def test_hook_bad_input_exits_zero_with_empty_stdout(box, tmp_path):
    state = tmp_path / "state"
    for raw in ("not json", "[1, 2]", ""):
        r = box.run("hook", input=raw, FABRIK_DECK_STATE=str(state))
        assert r.returncode == 0 and r.stdout == ""
    r = _hook(box, "Stop", state, sid="../escape")
    assert r.returncode == 0 and r.stdout == ""
    assert not (tmp_path / "escape.json").exists() and not (state / "escape.json").exists()
    blocked = tmp_path / "file-not-dir"
    blocked.write_text("x")
    r = _hook(box, "Stop", blocked / "state")
    assert r.returncode == 0 and r.stdout == ""


def test_hook_reads_state_dir_from_the_env_file(box, tmp_path):
    state = tmp_path / "from-file"
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text(f"FABRIK_DECK_STATE={state}\n")
    payload = {"hook_event_name": "Stop", "session_id": SID, "cwd": "/opt/youtube"}
    r = box.run("hook", input=json.dumps(payload))
    assert r.returncode == 0 and r.stdout == ""
    assert _att(state).exists()


def test_hook_runs_without_pyyaml(box, tmp_path):
    shadow = tmp_path / "noyaml"
    shadow.mkdir()
    (shadow / "yaml.py").write_text("raise ImportError('no yaml here')\n")
    state = tmp_path / "state"
    r = _hook(box, "Stop", state, PYTHONPATH=str(shadow))
    assert r.returncode == 0 and r.stdout == ""
    assert _att(state).exists()


def test_hook_exits_zero_with_stderr_closed(box, tmp_path):
    """Review pass 1: the failure handler's own print must not break the exit-0 contract when fd 2 is closed."""
    blocked = tmp_path / "file-not-dir"
    blocked.write_text("x")
    env = dict(box.env, FABRIK_DECK_STATE=str(blocked / "state"))
    payload = json.dumps({"hook_event_name": "Stop", "session_id": SID, "cwd": "/opt/youtube"})
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "hook"],
        input=payload,
        env=env,
        stdout=subprocess.PIPE,
        text=True,
        timeout=60,
        preexec_fn=lambda: os.close(2),
    )
    assert r.returncode == 0 and r.stdout == ""


def test_hook_reads_an_env_file_holding_a_non_utf8_byte(box, tmp_path):
    state = tmp_path / "from-file"
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_bytes(b"# caf\xe9 note\nFABRIK_DECK_STATE=" + str(state).encode() + b"\n")
    payload = {"hook_event_name": "Stop", "session_id": SID, "cwd": "/opt/youtube"}
    r = box.run("hook", input=json.dumps(payload))
    assert r.returncode == 0 and r.stdout == ""
    assert _att(state).exists()


@pytest.mark.parametrize("value", ["relstate", "~/tilde-state", "~no-such-user-zz9/x"])
def test_hook_never_writes_a_relative_state_dir_into_the_session_cwd(box, tmp_path, value):
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text(f"FABRIK_DECK_STATE={value}\n")
    cwd = tmp_path / "some-repo"
    cwd.mkdir()
    payload = json.dumps({"hook_event_name": "Stop", "session_id": SID, "cwd": str(cwd)})
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "hook"],
        input=payload,
        env=box.env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0 and r.stdout == ""
    assert not any(cwd.iterdir()), "nothing may land in the session's working directory"
    if value == "~/tilde-state":
        expected = box.home / "tilde-state"
    else:
        expected = box.home / ".local" / "state" / "fabrik-deck"
    assert _att(expected).exists()
