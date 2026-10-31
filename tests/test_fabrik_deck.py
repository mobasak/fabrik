"""Tests for scripts/sysadmin/fabrik_deck.py — the Deck's code-server as a systemd user service (W-e89a9b5b, D-1106).

Every test drives the script as a subprocess against a temporary HOME. `systemctl`, `loginctl`, `sudo` and
`systemd-tmpfiles` are fake executables on PATH that record their argv; `code-server` is a fake at <HOME>/.local/bin/code-server (the script execs it by that
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
TMP_STOCK = (
    "D /tmp 1777 root root 30d"  # Ubuntu's /usr/lib/tmpfiles.d/tmp.conf: wipe /tmp at boot (D-1389)
)
TMP_OFF = "d /tmp 1777 root root 30d"  # the installer's override: age only
DECK_UNIT = "fabrik-deck.service"

# The fakes run under this interpreter by absolute path, so a test may drop /usr/bin from PATH.
FAKE = (
    f"""#!{sys.executable}
"""
    + """import json, os, sys
log = os.environ["FAKE_LOG"]
with open(log, "a") as f:
    f.write(json.dumps({{"tool": {tool!r}, "argv": sys.argv[1:], "xdg": os.environ.get("XDG_RUNTIME_DIR"),
                        "systemd_env": {{k: os.environ.get(k) for k in ("SYSTEMD_COLORS", "SYSTEMD_URLIFY", "SYSTEMD_PAGER")}}}}) + "\\n")
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
    for tool, upper in (
        ("systemctl", "SYSTEMCTL"),
        ("loginctl", "LOGINCTL"),
        ("sudo", "SUDO"),
        ("systemd-tmpfiles", "TMPFILES"),
    ):
        _exe(fakebin / tool, FAKE.format(tool=tool, upper=upper))
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
        # the box as the 2026-10-31 fix left it: the boot wipe already off, so install owes no sudo write
        "FAKE_TMPFILES_STDOUT": f"# /etc/tmpfiles.d/tmp.conf\n{TMP_OFF}",
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
    b.deck_unit_path = home / ".config" / "systemd" / "user" / DECK_UNIT
    b.settings = home / ".local" / "share" / "code-server" / "User" / "settings.json"
    b.backups = home / ".local" / "share" / "code-server" / "User" / "backups"
    b.config_yaml = home / ".config" / "code-server" / "config.yaml"
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
    deck = box.deck_unit_path.read_text()
    assert f"ExecStart=/usr/bin/python3 {box.hub}/scripts/sysadmin/fabrik_deck.py serve" in deck
    assert f"EnvironmentFile={box.env_file}" in deck and "RestartPreventExitStatus=2" in deck
    assert box.env_file.is_absolute()
    for unit in (box.unit_path, box.deck_unit_path):
        v = subprocess.run(
            ["systemd-analyze", "--user", "verify", str(unit)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert v.returncode == 0 and v.stderr.strip() == "" and v.stdout.strip() == "", v.stderr


# 4 ---------------------------------------------------------------------------------------------------------------
def test_install_env_file_keeps_lines_appends_missing(box):
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 0, r.stderr
    first = box.env_file.read_text()
    assert "FABRIK_DECK_CODE_PORT=8443\n" in first and "FABRIK_DECK=1\n" in first
    assert f"CLAUDE_CONFIG_DIR={box.home}/.claude-fleet/active\n" in first
    assert "FABRIK_DECK_PORT=8445\n" in first
    assert f"FABRIK_DECK_STATE={box.home}/.local/state/fabrik-deck\n" in first
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
    assert not box.unit_path.exists() and not box.deck_unit_path.exists()
    assert box.calls("systemctl") == []


# 6 ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("which", ["code", "deck"])
def test_install_refuses_foreign_unit(box, which):
    foreign, other = (
        (box.unit_path, box.deck_unit_path)
        if which == "code"
        else (box.deck_unit_path, box.unit_path)
    )
    foreign.parent.mkdir(parents=True)
    foreign.write_text("[Unit]\nDescription=someone else's\n")
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 1
    assert foreign.read_text() == "[Unit]\nDescription=someone else's\n"
    assert not other.exists() and not box.env_file.exists() and not box.settings.exists()
    assert box.calls("systemctl") == []


# 7 ---------------------------------------------------------------------------------------------------------------
def test_install_enables_starts_only_when_asked_and_free(box):
    port = _free_port()
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text(f"FABRIK_DECK_CODE_PORT={port}\nFABRIK_DECK_PORT={_free_port()}\n")
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 0, r.stderr
    verbs = [a[1] for a in box.calls("systemctl")]
    assert verbs[:2] == ["daemon-reload", "enable"] and "start" not in verbs
    box.log.write_text("")
    r = box.run("install", "--hub", str(box.hub), "--start")
    assert r.returncode == 0, r.stderr
    assert "start" in [a[1] for a in box.calls("systemctl")]
    # port held by something else while the unit is inactive: refused before start
    box.log.write_text("")
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))
        s.listen()
        r = box.run(
            "install", "--hub", str(box.hub), "--start", FAKE_SYSTEMCTL_FAIL_VERB="is-active"
        )
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
    "case",
    [
        "verify-warns",
        "verify-stdout",
        "hub-space",
        "bad-port",
        "bad-deck-port",
        "no-systemd-analyze",
    ],
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
    elif case == "bad-deck-port":
        box.env_file.write_text("FABRIK_DECK=1\nFABRIK_DECK_PORT=84x5\n")
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
    assert not box.unit_path.exists() and not box.deck_unit_path.exists()
    assert not box.settings.exists() and not box.config_yaml.exists()
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
        "FABRIK_DECK_PORT",
        "FABRIK_DECK_STATE",
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_QUOTA_HOME",
        "FABRIK_DECK",
        "DISPLAY",
        "WAYLAND_DISPLAY",
    ]
    assert r.stderr.count("ignoring 'export FABRIK_DECK=1'") == 1, r.stderr
    assert (
        "appending missing keys FABRIK_DECK_PORT, FABRIK_DECK_STATE, CLAUDE_CONFIG_DIR, CLAUDE_QUOTA_HOME, "
        "FABRIK_DECK, DISPLAY, WAYLAND_DISPLAY" in r.stderr
    )
    assert stat.S_IMODE(box.env_file.stat().st_mode) == 0o600


# W-0c208792 (D-1389): install turns Ubuntu's boot-time /tmp wipe off ------------------------------------------------
# A fake systemd-tmpfiles that reads the stock `D` line until the fake sudo has "installed" the override, then our `d`
# line under the override's path — the real --cat-config's shape (a `# <file>` comment before each file's lines).
FAKE_TMPFILES_FLIP = (
    f"""#!{sys.executable}
"""
    + """import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"tool": "systemd-tmpfiles", "argv": sys.argv[1:], "xdg": None,
                        "systemd_env": {k: os.environ.get(k) for k in ("SYSTEMD_COLORS", "SYSTEMD_URLIFY", "SYSTEMD_PAGER")}}) + "\\n")
if os.path.exists(os.environ["FLIP_MARKER"]):
    print("# /etc/tmpfiles.d/tmp.conf")
    print(open(os.environ["FLIP_MARKER"]).read(), end="")
else:
    print("# /usr/lib/tmpfiles.d/tmp.conf")
    print(os.environ.get("FLIP_STOCK", "D /tmp 1777 root root 30d"))
"""
)
FAKE_SUDO_INSTALL = (
    f"""#!{sys.executable}
"""
    + """import json, os, shutil, sys
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"tool": "sudo", "argv": sys.argv[1:], "xdg": None}) + "\\n")
if os.environ.get("FAKE_SUDO_RC", "0") != "0":
    sys.exit(int(os.environ["FAKE_SUDO_RC"]))
if os.environ.get("SUDO_INSTALLS", "1") == "1":
    shutil.copyfile(sys.argv[-2], os.environ["FLIP_MARKER"])  # the staged file, as `install SRC DST` would
"""
)


def _tmpfiles_box(box, stock: str = TMP_STOCK) -> dict[str, str]:
    for tool, text in (("systemd-tmpfiles", FAKE_TMPFILES_FLIP), ("sudo", FAKE_SUDO_INSTALL)):
        (box.fakebin / tool).unlink()
        _exe(box.fakebin / tool, text)
    return {"FLIP_MARKER": str(box.tmp / "etc-tmp.conf"), "FLIP_STOCK": stock}


def _tools_in_order(box) -> list[str]:
    return [json.loads(line)["tool"] for line in box.log.read_text().splitlines()]


def test_install_writes_the_tmpfiles_override_and_proves_it(box):
    extra = _tmpfiles_box(box)
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text(
        f"FABRIK_DECK_CODE_PORT={_free_port()}\nFABRIK_DECK_PORT={_free_port()}\n"
    )
    r = box.run("install", "--hub", str(box.hub), "--start", **extra)
    assert r.returncode == 0, r.stderr
    (sudo,) = box.calls("sudo")
    assert sudo[:9] == ["-n", "install", "-D", "-m", "0644", "-o", "root", "-g", "root"], sudo
    assert sudo[-1] == "/etc/tmpfiles.d/tmp.conf" and not Path(sudo[-2]).exists(), (
        sudo
    )  # staged copy removed
    written = Path(extra["FLIP_MARKER"]).read_text()
    assert written.startswith("# Written by scripts/sysadmin/fabrik_deck.py install")
    assert [line for line in written.splitlines() if not line.startswith("#")] == [TMP_OFF]
    assert "no longer wiped at boot" in r.stdout
    # the root-level step is the LAST act: after daemon-reload, enable, start and the is-enabled report
    tools = _tools_in_order(box)
    assert tools[-1] == "systemd-tmpfiles" and tools[-2] == "sudo", (
        tools
    )  # the write, then the post-write proof
    assert tools.index("sudo") > max(i for i, tool in enumerate(tools) if tool == "systemctl"), (
        tools
    )
    assert [a[1] for a in box.calls("systemctl")][-2:] == ["is-enabled", "is-enabled"]
    # --cat-config is read plain (no pager; the env strips colours), once before any write and once after it
    assert box.calls("systemd-tmpfiles") == [["--cat-config", "--no-pager"]] * 2, box.calls(
        "systemd-tmpfiles"
    )
    envs = [
        json.loads(line)["systemd_env"]
        for line in box.log.read_text().splitlines()
        if json.loads(line)["tool"] == "systemd-tmpfiles"
    ]
    assert envs == [{"SYSTEMD_COLORS": "0", "SYSTEMD_URLIFY": "0", "SYSTEMD_PAGER": ""}] * 2, envs
    # idempotent: the second run reads `d` and owes nothing
    box.log.write_text("")
    r = box.run("install", "--hub", str(box.hub), **extra)
    assert r.returncode == 0 and box.calls("sudo") == [], (r.stderr, box.calls("sudo"))


@pytest.mark.parametrize(
    "case, stdout",
    [
        ("our-d-line", f"# /etc/tmpfiles.d/tmp.conf\n{TMP_OFF}"),
        (
            "another-drop-in-d",
            f"# /etc/tmpfiles.d/00-tmp.conf\n{TMP_OFF}\n\n# /etc/tmpfiles.d/tmp.conf\n{TMP_OFF}",
        ),
        ("masked-empty-file", "# /etc/tmpfiles.d/tmp.conf\n"),
        ("masked-comment-only", "# /etc/tmpfiles.d/tmp.conf\n# D /tmp was here\n"),
        ("no-tmp-line-at-all", "# /usr/lib/tmpfiles.d/x.conf\nd /run/x 0755 root root -\n"),
        ("quoted-d", '# /etc/tmpfiles.d/tmp.conf\nd "/tmp" 1777 root root 30d\n'),
        ("non-D-type", "# /etc/tmpfiles.d/tmp.conf\nq /tmp 1777 root root 30d\n"),
    ],
)
def test_install_owes_no_sudo_when_no_boot_wipe_is_in_effect(box, case, stdout):
    r = box.run("install", "--hub", str(box.hub), FAKE_TMPFILES_STDOUT=stdout)
    assert r.returncode == 0, (case, r.stderr)
    assert box.calls("sudo") == [] and "tmpfiles" not in r.stdout


@pytest.mark.parametrize("case", ["sudo-fails", "override-does-not-take"])
def test_install_exits_1_when_the_override_is_refused_or_does_not_take(box, case):
    extra = _tmpfiles_box(box)
    extra["FAKE_SUDO_RC" if case == "sudo-fails" else "SUDO_INSTALLS"] = (
        "1" if case == "sudo-fails" else "0"
    )
    r = box.run("install", "--hub", str(box.hub), **extra)
    assert r.returncode == 1 and "Traceback" not in r.stderr, r.stderr
    (sudo,) = box.calls("sudo")
    assert not Path(sudo[-2]).exists(), sudo  # the staged copy is removed on the failure path too
    if case == "sudo-fails":
        assert "still wiped at boot" in r.stderr
        assert "sudo tee /etc/tmpfiles.d/tmp.conf" in r.stderr  # the by-hand line
    else:
        assert "still carries a boot-time wipe" in r.stderr and TMP_STOCK in r.stderr
        assert "/usr/lib/tmpfiles.d/tmp.conf" in r.stderr  # the file carrying the D line is named
    # the Deck install itself completed: the one root-level step was last
    assert [a[1] for a in box.calls("systemctl")][-2:] == ["is-enabled", "is-enabled"]
    assert box.unit_path.exists()


@pytest.mark.parametrize(
    "case, stdout",
    [
        ("foreign-at-our-path", f"# /etc/tmpfiles.d/tmp.conf\n{TMP_STOCK}"),
        (
            "our-d-plus-another-D",
            f"# /etc/tmpfiles.d/tmp.conf\n{TMP_OFF}\n\n# /etc/tmpfiles.d/zz.conf\n{TMP_STOCK}",
        ),
        (
            "quoted-D-elsewhere",
            f'# /etc/tmpfiles.d/tmp.conf\n{TMP_OFF}\n\n# /etc/tmpfiles.d/zz.conf\nD "/tmp" 1777 root root 30d',
        ),
        (
            "specifier-D-elsewhere",
            f"# /etc/tmpfiles.d/aa.conf\nD %T 1777 root root -\n\n# /etc/tmpfiles.d/tmp.conf\n{TMP_OFF}",
        ),
        ("cat-config-fails", ""),
        ("no-systemd-tmpfiles", ""),
        ("no-sudo", f"# /usr/lib/tmpfiles.d/tmp.conf\n{TMP_STOCK}"),
    ],
)
def test_install_refuses_a_foreign_override_before_any_write(box, case, stdout):
    extra = {"FAKE_TMPFILES_STDOUT": stdout}
    if case == "cat-config-fails":
        extra["FAKE_TMPFILES_RC"] = "1"
    elif case == "no-sudo":
        (box.fakebin / "sudo").unlink()
        extra["PATH"] = str(box.fakebin)  # the real sudo sits in /usr/bin
    elif case == "no-systemd-tmpfiles":
        if not box.has_analyze:
            pytest.skip("systemd-analyze absent: install refuses on it first")
        (box.fakebin / "systemd-tmpfiles").unlink()
        extra["PATH"] = str(
            box.fakebin
        )  # the real one sits in /usr/bin; fakebin keeps its systemd-analyze link
    r = box.run("install", "--hub", str(box.hub), **extra)
    assert r.returncode == 1 and "Traceback" not in r.stderr, (case, r.stderr)
    if case == "foreign-at-our-path":
        assert (
            "not this script's file to rewrite" in r.stderr
            and "/etc/tmpfiles.d/tmp.conf: D /tmp" in r.stderr
        )
    elif case in ("our-d-plus-another-D", "quoted-D-elsewhere"):
        assert (
            "not this script's file to rewrite" in r.stderr
            and "/etc/tmpfiles.d/zz.conf: D" in r.stderr
        ), r.stderr
    elif case == "specifier-D-elsewhere":
        assert "/etc/tmpfiles.d/aa.conf: D %T" in r.stderr, r.stderr
    elif case == "cat-config-fails":
        assert "--cat-config failed before any write" in r.stderr
    elif case == "no-sudo":
        assert (
            "sudo is not installed" in r.stderr and "sudo tee /etc/tmpfiles.d/tmp.conf" in r.stderr
        )
    else:
        assert "systemd-tmpfiles is not installed" in r.stderr
    assert not box.unit_path.exists() and not box.env_file.exists() and not box.config_yaml.exists()
    assert box.calls("systemctl") == [] and box.calls("sudo") == []


@pytest.mark.skipif(shutil.which("systemd-tmpfiles") is None, reason="systemd-tmpfiles absent")
def test_the_override_shadows_the_stock_line_under_the_real_systemd_tmpfiles(tmp_path):
    """The claim the installer rests on: a `d /tmp` line in /etc/tmpfiles.d/tmp.conf shadows the stock `D /tmp` line
    of /usr/lib/tmpfiles.d/tmp.conf (same file name wins), so --cat-config reads ONE /tmp line, lowercase d."""
    spec = importlib.util.spec_from_file_location("fabrik_deck_tmpfiles_probe", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    root = tmp_path / "root"
    (root / "usr" / "lib" / "tmpfiles.d").mkdir(parents=True)
    (root / "etc" / "tmpfiles.d").mkdir(parents=True)
    (root / "usr" / "lib" / "tmpfiles.d" / "tmp.conf").write_text(
        f"# stock\n{TMP_STOCK}\n#q /var/tmp 1777 root root 30d\n"
    )

    def cat() -> str:
        r = subprocess.run(
            ["systemd-tmpfiles", "--cat-config", f"--root={root}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert r.returncode == 0, r.stderr
        return r.stdout

    stock = cat()
    stock_file = str(root / "usr" / "lib" / "tmpfiles.d" / "tmp.conf")
    ours = str(root / "etc" / "tmpfiles.d" / "tmp.conf")
    assert (
        m._tmp_lines(stock) == [(stock_file, TMP_STOCK, "D", "/tmp")]
        and m._tmpfiles_plan(stock) == "write"
    )
    (root / "etc" / "tmpfiles.d" / "tmp.conf").write_text(m.TMPFILES_TEXT)
    merged = cat()
    assert m._tmp_lines(merged) == [(ours, TMP_OFF, "d", "/tmp")], merged
    assert m._tmp_boot_wipe_off(merged) and m._tmpfiles_plan(merged) == "off"
    # a differently named drop-in does NOT shadow the stock line: the D stays in effect (measured: it wipes)
    (root / "etc" / "tmpfiles.d" / "tmp.conf").rename(root / "etc" / "tmpfiles.d" / "zz-tmp.conf")
    two = cat()
    assert len(m._tmp_lines(two)) == 2 and m._tmp_wipe_lines(two) == [(stock_file, TMP_STOCK)]
    assert not m._tmp_boot_wipe_off(two) and m._tmpfiles_plan(two) == "write"
    # a hand-written file at OUR path that keeps the wipe is foreign, never rewritten
    (root / "etc" / "tmpfiles.d" / "zz-tmp.conf").unlink()
    (root / "etc" / "tmpfiles.d" / "tmp.conf").write_text(f"{TMP_STOCK}\n")
    assert m._tmpfiles_plan(cat()) == "foreign"
    # the stock name masked (an empty file; tmpfiles.d(5)'s /dev/null symlink reads the same): nothing wipes
    (root / "etc" / "tmpfiles.d" / "tmp.conf").write_text("")
    assert m._tmp_lines(cat()) == [] and m._tmpfiles_plan(cat()) == "off"
    # every spelling systemd reads as /tmp is a /tmp line here: quoted, the %T specifier, slashes and dots
    (root / "etc" / "tmpfiles.d" / "tmp.conf").write_text(m.TMPFILES_TEXT)
    zz = root / "etc" / "tmpfiles.d" / "zz.conf"
    for spelling in ('"/tmp"', "%T", "/tmp/", "//tmp", "/tmp/.", "/./tmp"):
        zz.write_text(f"D {spelling} 1777 root root 30d\n")
        out = cat()
        assert m._tmp_wipe_lines(out) == [(str(zz), f"D {spelling} 1777 root root 30d")], (
            spelling,
            out,
        )
        assert m._tmpfiles_plan(out) == "foreign", (
            spelling
        )  # our file is in effect, so the refusal names zz.conf
    zz.unlink()
    # every shape measured to wipe /tmp's contents as a whole at boot: the %T specifier as a prefix, `..` resolving to
    # /tmp or to `/` (D /tmp/.. emptied the whole staged root), D/R on /tmp, r/R on a glob every direct child matches,
    # a quoted type field, C-escaped paths (hex, octal)
    for line in (
        "D %T/ 1777 root root 30d",
        "D %T/. 1777 root root 30d",
        "D /tmp/claude-1000/.. 1777 root root 30d",
        "D /tmp/../tmp 1777 root root 30d",
        "D /tmp/.. 1777 root root 30d",
        "R /tmp - - - -",
        "R /tmp/* - - - -",
        "R /tmp/?* - - - -",
        "r /tmp/* - - - -",
        '"D" /tmp 1777 root root 30d',
        "'D' /tmp 1777 root root 30d",
        "D /t\\x6dp 1777 root root 30d",
        "D \\057tmp 1777 root root 30d",
    ):
        zz.write_text(f"{line}\n")
        assert m._tmp_wipe_lines(cat()) == [(str(zz), line)], line
    # `D /tmp/x/..` with no x is ignored by systemd (measured) yet counted here: a refusal on a dead line, never a
    # wrong write — the lexical `..` resolution is what catches `D /tmp/claude-1000/..` above
    zz.write_text("D /tmp/x/.. 1777 root root 30d\n")
    assert m._tmp_wipe_lines(cat()) == [(str(zz), "D /tmp/x/.. 1777 root root 30d")]
    # NOT wipes of /tmp as a whole: lines systemd rejects (rc 65: a relative path, an unmatched quote early or late, an
    # escape systemd does not take, an unfinished escape), lines systemd drops or that remove nothing (a bad escape in
    # a trailing field, `D` on a glob, `e`, `r /tmp` on a non-empty directory, `R /tmp/.*`), and the stock shapes that
    # clear ONE named entry or a narrower pattern under /tmp — snapd, systemd and x11 ship these on every Ubuntu box
    # (each measured to leave /tmp's other contents)
    for line in (
        "D tmp 1777 root root 30d",
        'D "/tmp 1777 root root 30d',
        'D /tmp 1777 root root "30d',
        "D /t\\qmp 1777 root root 30d",
        "D /tmp\\e 1777 root root 30d",
        "D /t\\777mp 1777 root root 30d",
        'D "/t\\N{LATIN SMALL LETTER M}p" 1777 root root 30d',
        "D /tmp 1777 root root 30d\\",
        "D /tmp 1777 root root 30d \\q",
        "D /tmp/* 1777 root root 30d",
        "e /tmp - - - 0",
        "r /tmp - - - -",
        "R /tmp/.* - - - -",
        "D! /tmp/snap-private-tmp 0700 root root -",
        "R! /tmp/systemd-private-* - - - - -",
        "D! /tmp/.X11-unix 1777 root root 10d",
        "r! /tmp/.X[0-9]*-lock - - - - -",
        "D /tmp/claude-1000 0700 root root -",
        "R /tmp/*.txt - - - -",
        "R /tmp/*/* - - - -",
        "r /tmp/old.txt - - - -",
    ):
        zz.write_text(f"{line}\n")
        assert m._tmp_wipe_lines(cat()) == [], line
    zz.unlink()
    # the LIVE POPULATION: this box's stock files that name /tmp, laid over the staged tree with our shadow — install
    # must read it as off, or no Ubuntu box could ever install (seat-1 pass 4, 2026-10-31)
    stock_dir = Path("/usr/lib/tmpfiles.d")
    shipped = [
        f for f in ("snapd.conf", "systemd-tmp.conf", "x11.conf") if (stock_dir / f).exists()
    ]
    if shipped:
        for f in shipped:
            (root / "usr" / "lib" / "tmpfiles.d" / f).write_text((stock_dir / f).read_text())
        out = cat()
        assert len(m._tmp_lines(out)) > 1, out  # the stock entries under /tmp are read as lines…
        assert m._tmp_wipe_lines(out) == [] and m._tmpfiles_plan(out) == "off", (
            out
        )  # …and none is a wipe
        for f in shipped:
            (root / "usr" / "lib" / "tmpfiles.d" / f).unlink()
    # a `# /x.conf` comment inside a file is not a header, after a blank line or not: the wipe after it stays credited
    # to its real file (a header names a tmpfiles.d directory)
    for body in (f"# /opt/notes.conf\n{TMP_STOCK}\n", f"\n# /opt/notes.conf\n{TMP_STOCK}\n"):
        zz.write_text(body)
        assert m._tmp_wipe_lines(cat()) == [(str(zz), TMP_STOCK)], body
    zz.unlink()
    # a drop-in whose NAME holds a space still gets its lines credited to it (the header is `# <path>.conf`)
    spaced = root / "etc" / "tmpfiles.d" / "my tmp.conf"
    spaced.write_text(f"{TMP_STOCK}\n")
    assert m._tmp_wipe_lines(cat()) == [(str(spaced), TMP_STOCK)]
    spaced.unlink()
    # a non-D type at the stock name does not wipe; a comment naming /tmp is not a line
    (root / "etc" / "tmpfiles.d" / "tmp.conf").write_text(
        "# D /tmp was here\nq /tmp 1777 root root 30d\n"
    )
    assert m._tmp_boot_wipe_off(cat()) and m._tmpfiles_plan(cat()) == "off"
    # SYSTEMD_COLORS=1 wraps the headers in escapes and the parser loses the file names; the installer's own call
    # sets SYSTEMD_COLORS=0 (asserted on the fake's logged env by the write test), and the headers come back
    (root / "etc" / "tmpfiles.d" / "tmp.conf").write_text(m.TMPFILES_TEXT)

    def cat_env(colors: str) -> str:
        r = subprocess.run(
            ["systemd-tmpfiles", "--cat-config", f"--root={root}"],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "SYSTEMD_COLORS": colors, "SYSTEMD_URLIFY": "0"},
        )
        assert r.returncode == 0, r.stderr
        return r.stdout

    coloured = cat_env("1")
    assert "\x1b[" in coloured and [f for f, *_ in m._tmp_lines(coloured)] != [ours], coloured
    assert [f for f, *_ in m._tmp_lines(cat_env("0"))] == [ours]


@pytest.mark.parametrize("verb", ["daemon-reload", "enable", "start"])
def test_install_stops_on_each_failing_systemctl_verb(box, verb):
    port = _free_port()
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text(f"FABRIK_DECK_CODE_PORT={port}\nFABRIK_DECK_PORT={_free_port()}\n")
    r = box.run("install", "--hub", str(box.hub), "--start", FAKE_SYSTEMCTL_FAIL_VERB=verb)
    assert r.returncode == 1 and verb in r.stderr, r.stderr
    verbs = [a[1] for a in box.calls("systemctl")]
    assert verbs[-1] == verb and "is-enabled" not in verbs


def test_install_accepts_a_single_quoted_port(box):
    port = _free_port()
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text(f"FABRIK_DECK_CODE_PORT='{port}'\nFABRIK_DECK_PORT='{_free_port()}'\n")
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


# --- the Deck server, catalog and board (plan 2026-10-22-plan-1-fabrik-deck, Phase B; spec § Tests 3-7) -----------
import http.client  # noqa: E402
import importlib.util  # noqa: E402
import time  # noqa: E402

FAB = "11111111-aaaa-bbbb-cccc-000000000001"
TMX = "22222222-aaaa-bbbb-cccc-000000000002"
DCK = "33333333-aaaa-bbbb-cccc-000000000003"
OTH = "44444444-aaaa-bbbb-cccc-000000000004"


def _git_repo(path: Path, worktree_file: bool = False) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    if worktree_file:
        (path / ".git").write_text("gitdir: /elsewhere\n")
    else:
        (path / ".git").mkdir(exist_ok=True)
    return path


@pytest.fixture()
def deck(box, tmp_path):
    """Start `serve` against a temp /opt and registry; yields a helper that talks HTTP to it."""
    opt = tmp_path / "opt"
    fabrik = _git_repo(opt / "fabrik")
    lib = _git_repo(opt / "fabrik-lib")
    plain = opt / "plain"
    plain.mkdir(parents=True)
    registry = tmp_path / "projects.yaml"
    registry.write_text(
        "projects:\n"
        f"  fabrik-dup:\n    path: {fabrik}\n"
        f"  gone:\n    path: {opt / 'gone'}\n"
        f"  plain:\n    path: {plain}\n"
        "  nopath:\n    type: x\n"
    )
    state = tmp_path / "state"
    procs = []

    class Deck:
        pass

    d = Deck()
    d.opt, d.fabrik, d.lib, d.plain, d.registry, d.state = opt, fabrik, lib, plain, registry, state

    def start(state_in_env: bool = True, **extra):
        port = _free_port()
        env = dict(box.env, FABRIK_DECK_PORT=str(port), FABRIK_DECK_CODE_PORT="18443")
        if state_in_env:
            env["FABRIK_DECK_STATE"] = str(state)
        env.update(extra)
        p = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPT),
                "serve",
                "--registry",
                str(registry),
                "--opt-root",
                str(opt),
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        procs.append(p)
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                if p.poll() is not None:
                    raise AssertionError(f"serve exited early: {p.stderr.read()}")
                time.sleep(0.05)
        d.port, d.proc = port, p
        return d

    def get(path: str, method: str = "GET", host: str | None = None):
        c = http.client.HTTPConnection("127.0.0.1", d.port, timeout=5)
        c.putrequest(method, path, skip_host=True)
        c.putheader("Host", host or f"localhost:{d.port}")
        c.endheaders()
        r = c.getresponse()
        body = r.read()
        c.close()
        return r.status, dict(r.getheaders()), body

    def attend(
        sid: str, cwd: str, kind: str = "turn_ended", origin: str = "other", at: float | None = None
    ):
        (state / "attention").mkdir(parents=True, exist_ok=True)
        rec = {"cwd": cwd, "type": kind, "origin": origin, "at": time.time() if at is None else at}
        (state / "attention" / f"{sid}.json").write_text(json.dumps(rec))

    d.start, d.get, d.attend = start, get, attend
    yield d
    for p in procs:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


def _repos(d) -> dict:
    status, _, body = d.get("/api/repos")
    assert status == 200
    return {r["name"]: r for r in json.loads(body)}


def _attn(d) -> list:
    status, _, body = d.get("/api/attention")
    assert status == 200
    return json.loads(body)


def test_serve_catalog_is_the_registry_and_opt_union(deck):
    deck.start()
    repos = _repos(deck)
    paths = [r["path"] for r in repos.values()]
    assert len(paths) == len(set(paths)), "each repo once"
    assert str(deck.fabrik) in paths and str(deck.lib) in paths
    assert not any(p.endswith("/gone") for p in paths), "a missing path is dropped"
    assert repos["plain"]["git"] is False and repos["fabrik-lib"]["git"] is True


def test_serve_attention_maps_worktree_cwds_and_component_boundaries(deck):
    deck.start()
    deck.attend(FAB, f"{deck.fabrik}/.claude/worktrees/fleet/sub")
    deck.attend(TMX, f"{deck.lib}/x")
    deck.attend(OTH, "/somewhere/else")
    by = {a["session"]: a for a in _attn(deck)}
    assert by[FAB]["repo"] == "fabrik"
    assert by[TMX]["repo"] == "fabrik-lib", (
        "/opt/fabrik-lib must not match /opt/fabrik by string prefix"
    )
    assert by[OTH]["repo"] == "other"


def test_serve_attention_labels(deck):
    agents = deck.fabrik / ".fabrik"
    agents.mkdir()
    (agents / "session-agents.json").write_text(json.dumps({FAB: "fleet"}))
    deck.start()
    deck.attend(FAB, str(deck.fabrik))
    deck.attend(DCK, str(deck.fabrik), origin="deck")
    deck.attend(TMX, str(deck.fabrik), origin="tmux")
    deck.attend(OTH, str(deck.fabrik))
    by = {a["session"]: a["label"] for a in _attn(deck)}
    assert by[FAB] == "fleet"
    assert by[DCK] == "coordinator (fabrik tab)"
    assert by[TMX] == f"session {TMX[:8]} (tmux)"
    assert by[OTH] == f"session {OTH[:8]}"


def test_serve_prunes_attention_older_than_24h(deck):
    deck.start()
    deck.attend(FAB, str(deck.fabrik), at=time.time() - 25 * 3600)
    deck.attend(OTH, str(deck.fabrik), at=time.time() - 23 * 3600)
    sessions = {a["session"] for a in _attn(deck)}
    assert sessions == {OTH}
    assert not (deck.state / "attention" / f"{FAB}.json").exists()
    assert (deck.state / "attention" / f"{OTH}.json").exists()


def test_serve_refuses_a_foreign_host_and_every_method_but_get(deck):
    deck.start()
    assert deck.get("/api/repos", host="evil.example:80")[0] == 421
    assert deck.get("/api/repos", host=f"localhost:{deck.port + 1}")[0] == 421
    for method in ("POST", "PUT", "HEAD", "DELETE"):
        assert deck.get("/api/repos", method=method)[0] == 405, method
    assert deck.get("/api/repos", host=f"127.0.0.1:{deck.port}")[0] == 200


def test_serve_board_is_served_with_frame_ancestors_none(deck):
    deck.start()
    status, headers, body = deck.get("/")
    assert status == 200 and headers["Content-Type"].startswith("text/html")
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    page = body.decode()
    assert "innerHTML" not in page and "encodeURIComponent" in page and "18443" in page


def test_serve_default_port_is_the_deck_port_not_code_server():
    spec = importlib.util.spec_from_file_location("fabrik_deck_under_test", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m._parse_port(None, m.DECK_PORT) == 8445
    assert m._parse_port(None) == 8443


def test_serve_binds_8445_when_the_port_is_unset(monkeypatch, tmp_path):
    import http.server

    spec = importlib.util.spec_from_file_location("fabrik_deck_bind_probe", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    registry = tmp_path / "p.yaml"
    registry.write_text("projects: {}\n")
    monkeypatch.delenv("FABRIK_DECK_PORT", raising=False)
    monkeypatch.setenv("FABRIK_DECK_STATE", str(tmp_path / "state"))
    bound = []

    def fake_server(address, handler):
        bound.append(address)
        raise SystemExit(0)

    monkeypatch.setattr(http.server, "ThreadingHTTPServer", fake_server)
    with pytest.raises(SystemExit):
        m.serve(registry, tmp_path)
    assert bound == [("127.0.0.1", 8445)]


def test_serve_exits_2_on_a_bad_or_bound_port(box, tmp_path):
    registry = tmp_path / "p.yaml"
    registry.write_text("projects: {}\n")
    args = [
        sys.executable,
        str(SCRIPT),
        "serve",
        "--registry",
        str(registry),
        "--opt-root",
        str(tmp_path),
    ]
    r = subprocess.run(
        args, env=dict(box.env, FABRIK_DECK_PORT="abc"), capture_output=True, text=True, timeout=30
    )
    assert r.returncode == 2 and r.stderr.strip() and r.stdout == ""
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen(1)
        port = held.getsockname()[1]
        env = dict(box.env, FABRIK_DECK_PORT=str(port))
        r = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and r.stderr.strip()


def test_serve_and_hook_share_a_state_dir_set_only_in_the_env_file(deck, box):
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text(f"FABRIK_DECK_STATE={deck.state}\n")
    deck.start(state_in_env=False)
    payload = {"hook_event_name": "Stop", "session_id": FAB, "cwd": str(deck.fabrik)}
    r = box.run("hook", input=json.dumps(payload))
    assert r.returncode == 0
    assert FAB in {a["session"] for a in _attn(deck)}


def test_serve_events_stream_a_new_waiting_session(deck):
    deck.start()
    c = http.client.HTTPConnection("127.0.0.1", deck.port, timeout=5)
    c.putrequest("GET", "/api/events", skip_host=True)
    c.putheader("Host", f"localhost:{deck.port}")
    c.endheaders()
    r = c.getresponse()
    assert r.status == 200 and r.getheader("Content-Type").startswith("text/event-stream")
    deck.attend(FAB, str(deck.fabrik))
    deadline = time.time() + 3
    seen = False
    while time.time() < deadline and not seen:
        line = r.fp.readline().decode()
        seen = line.startswith("data:") and FAB in line
    c.close()
    assert seen, "a data frame carrying the new session within 3 s"
    time.sleep(2.5)
    assert deck.get("/api/repos")[0] == 200, "the server keeps serving after the client left"
    deck.proc.terminate()
    _, err = deck.proc.communicate(timeout=5)
    assert "Traceback" not in err


@pytest.mark.parametrize("damage", ["not json", "[1, 2]", "big", "dir"])
def test_serve_tolerates_a_damaged_session_agents_file(deck, damage):
    target = deck.fabrik / ".fabrik" / "session-agents.json"
    target.parent.mkdir()
    if damage == "big":
        target.write_text(json.dumps({FAB: "x" * (1 << 20)}))
    elif damage == "dir":
        target.mkdir()
    else:
        target.write_text(damage)
    deck.start()
    assert _repos(deck)["fabrik"]["agents"] == []
    assert deck.get("/")[0] == 200


@pytest.mark.parametrize("method", ["TRACE", "CONNECT", "FOO"])
def test_serve_refuses_an_unlisted_method_405_and_a_foreign_host_421(deck, method):
    deck.start()
    assert deck.get("/api/repos", method=method)[0] == 405
    assert deck.get("/api/repos", method=method, host="evil.example:80")[0] == 421


def test_serve_host_guard_covers_every_route(deck):
    deck.start()
    for route in ("/", "/api/attention", "/api/events", "/nope"):
        assert deck.get(route, host="evil.example:80")[0] == 421, route


@pytest.mark.parametrize("at", ["NaN", "Infinity", "-Infinity", "1" + "0" * 400, "99999999999"])
def test_serve_a_non_finite_attention_time_is_dropped_and_the_json_stays_valid(deck, at):
    deck.start()
    (deck.state / "attention").mkdir(parents=True)
    bad = deck.state / "attention" / f"{FAB}.json"
    bad.write_text('{"cwd": "/x", "type": "t", "origin": "other", "at": AT}'.replace("AT", at))
    deck.attend(OTH, str(deck.fabrik))
    status, _, body = deck.get("/api/attention")
    assert status == 200
    sessions = {a["session"] for a in json.loads(body, parse_constant=lambda c: pytest.fail(c))}
    assert sessions == {OTH}
    if not at.startswith("1"):  # a time no clock wrote is pruned; an unparsable one is skipped
        assert not bad.exists()


def test_serve_maps_a_cwd_through_a_symlinked_repo(deck, tmp_path):
    real = _git_repo(tmp_path / "real" / "r2")
    (deck.opt / "r2").symlink_to(real)
    deck.start()
    deck.attend(FAB, f"{deck.opt}/r2/x")
    deck.attend(OTH, f"{real}/y")
    by = {a["session"]: a["repo"] for a in _attn(deck)}
    assert by[FAB] == "r2" and by[OTH] == "r2"


def test_serve_an_unremovable_stale_attention_file_does_not_break_the_reader(deck):
    if os.geteuid() == 0:
        pytest.skip("root unlinks through a read-only directory")
    deck.start()
    deck.attend(FAB, str(deck.fabrik), at=time.time() - 25 * 3600)
    deck.attend(OTH, str(deck.fabrik))
    (deck.state / "attention").chmod(0o500)
    try:
        assert {a["session"] for a in _attn(deck)} == {OTH}
    finally:
        (deck.state / "attention").chmod(0o700)


def test_serve_keeps_the_last_good_catalog_when_the_registry_turns_bad():
    # In-process with CATALOG_TTL 0: through the server the 10 s cache would answer before the registry is re-read.
    spec = importlib.util.spec_from_file_location("fabrik_deck_fallback_probe", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.CATALOG_TTL = 0

    def broken(registry, opt_root):
        raise ValueError("the registry is half-written")

    m._catalog = broken
    good = [{"name": "fabrik", "path": "/opt/fabrik", "git": True, "agents": [], "_agents": {}}]
    handler = m._handler(Path("/r"), Path("/o"), Path("/s"), 8443, good)
    assert handler.current() == good


@pytest.mark.parametrize("registry", ["missing", "projects: [unclosed\n"])
def test_serve_exits_2_on_an_unreadable_registry(box, tmp_path, registry):
    path = tmp_path / "p.yaml"
    if registry != "missing":
        path.write_text(registry)
    args = [
        sys.executable,
        str(SCRIPT),
        "serve",
        "--registry",
        str(path),
        "--opt-root",
        str(tmp_path),
    ]
    env = dict(box.env, FABRIK_DECK_PORT=str(_free_port()))
    r = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and "registry" in r.stderr


def test_serve_exits_2_on_a_bad_code_port(box, tmp_path):
    path = tmp_path / "p.yaml"
    path.write_text("projects: {}\n")
    args = [
        sys.executable,
        str(SCRIPT),
        "serve",
        "--registry",
        str(path),
        "--opt-root",
        str(tmp_path),
    ]
    env = dict(box.env, FABRIK_DECK_PORT=str(_free_port()), FABRIK_DECK_CODE_PORT="0")
    r = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and "FABRIK_DECK_CODE_PORT" in r.stderr


def test_serve_catalog_is_cached_between_sse_frames():
    spec = importlib.util.spec_from_file_location("fabrik_deck_cache_probe", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    calls = []
    m._catalog = lambda registry, opt_root: calls.append(1) or []
    handler = m._handler(Path("/r"), Path("/o"), Path("/s"), 8443, [])
    for _ in range(20):
        handler.current()
    assert len(calls) <= 1, "the catalog is rebuilt at most once per CATALOG_TTL"


def test_serve_a_malformed_request_still_carries_the_frame_and_cache_headers(deck):
    deck.start()
    with socket.create_connection(("127.0.0.1", deck.port), timeout=5) as s:
        s.sendall(b"GET / HTTP/1.1\r\nX: " + b"a" * 70000 + b"\r\n\r\n")
        reply = s.recv(65536).decode(errors="replace")
    assert reply.startswith("HTTP/") and " 431 " in reply.splitlines()[0]
    assert "frame-ancestors 'none'" in reply and "no-store" in reply


def test_serve_events_carry_the_repos_so_a_new_repo_shows_without_a_reload(deck):
    deck.start()
    c = http.client.HTTPConnection("127.0.0.1", deck.port, timeout=5)
    c.putrequest("GET", "/api/events", skip_host=True)
    c.putheader("Host", f"localhost:{deck.port}")
    c.endheaders()
    r = c.getresponse()
    line = ""
    while not line.startswith("data:"):
        line = r.fp.readline().decode()
    c.close()
    frame = json.loads(line[5:])
    assert {r["name"] for r in frame["repos"]} >= {"fabrik", "fabrik-lib"}
    assert frame["attention"] == []


def test_serve_attention_carries_the_matched_repo_path(deck):
    deck.start()
    deck.attend(FAB, str(deck.fabrik))
    deck.attend(OTH, "/elsewhere")
    by = {a["session"]: a["path"] for a in _attn(deck)}
    assert by[FAB] == str(deck.fabrik.resolve()) and by[OTH] is None


def test_attention_a_relative_cwd_never_resolves_against_the_server_dir(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("fabrik_deck_relcwd_probe", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    repo = tmp_path / "repo"
    repo.mkdir()
    state = tmp_path / "state"
    (state / "attention").mkdir(parents=True)
    rec = {"cwd": "src", "type": "turn_ended", "origin": "other", "at": time.time()}
    (state / "attention" / f"{FAB}.json").write_text(json.dumps(rec))
    monkeypatch.chdir(repo)
    rows = [{"name": "repo", "path": str(repo.resolve()), "_agents": {}}]
    assert [a["repo"] for a in m.attention(state, rows, time.time())] == ["other"]


# --- install (second unit), profile, launcher, up (plan 2026-10-22-plan-1-fabrik-deck, Phase C; spec § Tests 8-10) --
PROFILE = {
    "workbench.colorTheme": "Dark 2026",
    "window.autoDetectColorScheme": False,
    "claudeCode.preferredLocation": "panel",
    "editor.minimap.enabled": False,
    "breadcrumbs.enabled": False,
    "workbench.startupEditor": "none",
    "workbench.activityBar.location": "top",
    "workbench.statusBar.visible": True,
    "workbench.editor.showTabs": "single",
}
BAT_MARKER = b"rem generated by /opt/fabrik/scripts/sysadmin/fabrik_deck.py launcher"


def test_profile_merges_the_deck_keys_after_a_backup(box):
    box.settings.parent.mkdir(parents=True)
    box.settings.write_text(json.dumps({"editor.fontSize": 15, "workbench.colorTheme": "Light+"}))
    r = box.run("profile")
    assert r.returncode == 0, r.stderr
    got = json.loads(box.settings.read_text())
    assert got == {"editor.fontSize": 15, **PROFILE}
    backups = list(box.backups.glob("settings.json.*"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text())["workbench.colorTheme"] == "Light+"


@pytest.mark.parametrize("text", ["{ // a comment\n}", "[1, 2]", "not json"])
def test_profile_leaves_a_file_that_is_not_a_json_object(box, text):
    box.settings.parent.mkdir(parents=True)
    box.settings.write_text(text)
    r = box.run("profile")
    assert r.returncode == 1 and str(box.settings) in r.stderr and "Traceback" not in r.stderr
    assert box.settings.read_text() == text


def test_profile_creates_a_missing_settings_file(box):
    r = box.run("profile")
    assert r.returncode == 0, r.stderr
    assert json.loads(box.settings.read_text()) == PROFILE


def _bat(box) -> Path:
    return box.tmp / "desk" / "Fabrik Deck.bat"


def test_launcher_writes_crlf_ascii_with_the_marker_on_line_2(box):
    (box.tmp / "desk").mkdir()
    r = box.run(
        "launcher",
        "--desktop",
        str(box.tmp / "desk"),
        "--distro",
        "Ubuntu-24.04",
        "--hub",
        str(box.hub),
    )
    assert r.returncode == 0, r.stderr
    raw = _bat(box).read_bytes()
    raw.decode("ascii")
    lines = raw.split(b"\r\n")
    assert lines[0] == b"@echo off" and lines[1] == BAT_MARKER
    assert b"\n" not in raw.replace(b"\r\n", b"")
    text = raw.decode()
    assert (
        f"wsl.exe --distribution Ubuntu-24.04 --exec /usr/bin/python3 {box.hub}/scripts/sysadmin/fabrik_deck.py up"
        in text
    )
    assert '"%%{http_code}"' in text and "GEQ 30" in text and "timeout /t 1" in text
    assert 'tasklist /FI "IMAGENAME eq vivaldi.exe" /NH | find /I "vivaldi.exe"' in text
    assert r"C:\Users\user\AppData\Local\Vivaldi\Application\vivaldi.exe" in text
    first_run = text.index("Fabrik Deck.first-run")
    assert text.index("findstr 200") < first_run, (
        "the first-run marker is written only after the board answered"
    )


def test_launcher_refuses_a_foreign_bat_and_rewrites_its_own(box):
    (box.tmp / "desk").mkdir()
    _bat(box).write_bytes(b"@echo off\r\nrem mine\r\n")
    args = (
        "launcher",
        "--desktop",
        str(box.tmp / "desk"),
        "--distro",
        "Ubuntu",
        "--hub",
        str(box.hub),
    )
    r = box.run(*args)
    assert r.returncode == 2 and _bat(box).read_bytes() == b"@echo off\r\nrem mine\r\n"
    _bat(box).write_bytes(b"@echo off\r\n" + BAT_MARKER + b"\r\nold\r\n")
    r = box.run(*args)
    assert r.returncode == 0 and b"old" not in _bat(box).read_bytes()


@pytest.mark.parametrize(
    "flag,value",
    [("--distro", "Ubuntu & calc"), ("--browser", 'C:\\x"y.exe'), ("--browser", "C:\\100%.exe")],
)
def test_launcher_refuses_text_cmd_would_split(box, flag, value):
    (box.tmp / "desk").mkdir()
    args = [
        "launcher",
        "--desktop",
        str(box.tmp / "desk"),
        "--distro",
        "Ubuntu",
        "--hub",
        str(box.hub),
        flag,
        value,
    ]
    r = box.run(*args)
    assert r.returncode == 2 and not _bat(box).exists() and "Traceback" not in r.stderr


def test_install_writes_config_yaml_after_a_backup_keeping_other_lines(box):
    box.config_yaml.parent.mkdir(parents=True)
    box.config_yaml.write_text(
        "bind-addr: 127.0.0.1:8080\nauth: password\npassword: s3cret\ncert: true\n"
    )
    box.config_yaml.chmod(0o600)
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 0, r.stderr
    lines = box.config_yaml.read_text().splitlines()
    assert "bind-addr: 127.0.0.1:8443" in lines and "auth: none" in lines and "cert: false" in lines
    assert "password: s3cret" in lines and len(lines) == 4
    assert stat.S_IMODE(box.config_yaml.stat().st_mode) == 0o600
    backups = list(box.backups.glob("config.yaml.*"))
    assert len(backups) == 1 and "auth: password" in backups[0].read_text()


def test_install_creates_config_yaml_0600(box):
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 0, r.stderr
    assert box.config_yaml.read_text().splitlines() == [
        "bind-addr: 127.0.0.1:8443",
        "auth: none",
        "cert: false",
    ]
    assert stat.S_IMODE(box.config_yaml.stat().st_mode) == 0o600


def test_install_applies_the_profile_and_writes_the_bat_only_with_desktop(box):
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 0, r.stderr
    assert json.loads(box.settings.read_text()) == PROFILE
    assert not (box.tmp / "desk").exists()
    (box.tmp / "desk").mkdir()
    r = box.run(
        "install", "--hub", str(box.hub), "--desktop", str(box.tmp / "desk"), "--distro", "Ubuntu"
    )
    assert r.returncode == 0, r.stderr
    assert _bat(box).read_bytes().split(b"\r\n")[1] == BAT_MARKER


def test_install_refuses_a_settings_file_that_is_not_json_before_any_write(box):
    box.settings.parent.mkdir(parents=True)
    box.settings.write_text("{ // jsonc\n}")
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 1 and str(box.settings) in r.stderr
    assert not box.unit_path.exists() and not box.deck_unit_path.exists()
    assert not box.env_file.exists() and not box.config_yaml.exists()
    assert box.calls("systemctl") == []


def test_install_refuses_a_foreign_bat_before_any_write(box):
    (box.tmp / "desk").mkdir()
    _bat(box).write_bytes(b"@echo off\r\nrem mine\r\n")
    r = box.run(
        "install", "--hub", str(box.hub), "--desktop", str(box.tmp / "desk"), "--distro", "Ubuntu"
    )
    assert r.returncode == 1 and not box.unit_path.exists() and not box.settings.exists()
    assert (
        not box.deck_unit_path.exists()
        and not box.env_file.exists()
        and not box.config_yaml.exists()
    )
    assert not box.backups.exists() and box.calls("systemctl") == []


def test_install_start_does_not_refuse_the_port_of_an_active_unit(box):
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        port = held.getsockname()[1]
        box.env_file.parent.mkdir(parents=True)
        box.env_file.write_text(f"FABRIK_DECK_CODE_PORT={port}\nFABRIK_DECK_PORT={_free_port()}\n")
        r = box.run(
            "install", "--hub", str(box.hub), "--start"
        )  # the fake answers is-active with 0: active
    assert r.returncode == 0, r.stderr
    assert "start" in [a[1] for a in box.calls("systemctl")]


def _runtime_dir():
    import tempfile

    d = Path(
        tempfile.mkdtemp(prefix="dk", dir="/tmp")
    )  # a unix socket path must stay under 108 bytes
    (d / str(os.getuid())).mkdir()
    return d


def test_up_exports_the_bus_starts_inactive_free_units_and_prints_the_deck_port(box):
    rt = _runtime_dir()
    bus = socket.socket(socket.AF_UNIX)
    bus.bind(str(rt / str(os.getuid()) / "bus"))
    try:
        with socket.socket() as held:
            held.bind(("127.0.0.1", 0))
            held.listen()
            code_port = held.getsockname()[1]  # a hand-started code-server
            deck_port = _free_port()
            box.env_file.parent.mkdir(parents=True)
            box.env_file.write_text(
                f"FABRIK_DECK_CODE_PORT={code_port}\nFABRIK_DECK_PORT={deck_port}\n"
            )
            r = box.run(
                "up",
                "--runtime-dir",
                str(rt),
                XDG_RUNTIME_DIR="",
                FAKE_SYSTEMCTL_FAIL_VERB="is-active",
            )
        assert r.returncode == 0 and r.stdout.strip() == str(deck_port), (r.stdout, r.stderr)
        starts = [a for a in box.calls("systemctl") if a[1] == "start"]
        assert starts == [["--user", "start", DECK_UNIT]]
        assert UNIT in r.stderr and str(code_port) in r.stderr
        xdgs = {json.loads(line)["xdg"] for line in box.log.read_text().splitlines()}
        assert xdgs == {str(rt / str(os.getuid()))}
    finally:
        bus.close()
        shutil.rmtree(rt)


@pytest.mark.parametrize("bus", ["none", "plain-file"])
def test_up_without_a_bus_socket_says_so_and_starts_nothing(box, bus):
    rt = _runtime_dir()
    if bus == "plain-file":
        (rt / str(os.getuid()) / "bus").write_text("not a socket")
    try:
        r = box.run("up", "--runtime-dir", str(rt), XDG_RUNTIME_DIR="")
        assert r.returncode == 1 and r.stdout.strip() == "8445", (r.stdout, r.stderr)
        assert "no user bus" in r.stderr
        assert box.calls("systemctl") == []
    finally:
        shutil.rmtree(rt)


def test_up_skips_active_units(box):
    r = box.run("up", XDG_RUNTIME_DIR="/run/user/0")  # the fake answers is-active with 0
    assert r.returncode == 0 and r.stdout.strip() == "8445", (r.stdout, r.stderr)
    assert [a for a in box.calls("systemctl") if a[1] == "start"] == []


def test_up_prints_no_port_when_a_foreign_process_holds_the_boards(box):
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        deck_port = held.getsockname()[1]
        box.env_file.parent.mkdir(parents=True)
        box.env_file.write_text(
            f"FABRIK_DECK_CODE_PORT={_free_port()}\nFABRIK_DECK_PORT={deck_port}\n"
        )
        r = box.run("up", XDG_RUNTIME_DIR="/run/user/0", FAKE_SYSTEMCTL_FAIL_VERB="is-active")
    assert r.returncode == 1 and r.stdout == "" and DECK_UNIT in r.stderr


def test_up_reports_a_failed_start_and_still_prints_the_port(box):
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text(
        f"FABRIK_DECK_CODE_PORT={_free_port()}\nFABRIK_DECK_PORT={_free_port()}\n"
    )
    r = box.run("up", XDG_RUNTIME_DIR="/run/user/0", FAKE_SYSTEMCTL_RC="1")
    assert r.returncode == 1 and r.stdout.strip().isdigit() and "start" in r.stderr


# --- Phase C review pass 1 -----------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "hub", ["/opt/a&calc", "/opt/a b", "/opt/x)y", "/opt/f\u00e4brik", "/opt/50%", "relative/hub"]
)
def test_launcher_refuses_a_hub_cmd_or_systemd_would_split(box, hub):
    (box.tmp / "desk").mkdir()
    r = box.run("launcher", "--desktop", str(box.tmp / "desk"), "--distro", "Ubuntu", "--hub", hub)
    assert r.returncode == 2 and not _bat(box).exists() and "Traceback" not in r.stderr, r.stderr


def test_install_refuses_a_non_ascii_hub_before_any_write(box):
    hub = box.tmp / "f\u00e4brik"
    (hub / "scripts" / "sysadmin").mkdir(parents=True)
    (hub / "scripts" / "sysadmin" / "fabrik_deck.py").write_text("#\n")
    (box.tmp / "desk").mkdir()
    r = box.run(
        "install", "--hub", str(hub), "--desktop", str(box.tmp / "desk"), "--distro", "Ubuntu"
    )
    assert r.returncode == 1 and "Traceback" not in r.stderr, r.stderr
    assert not box.env_file.exists() and not box.unit_path.exists() and not _bat(box).exists()


@pytest.mark.parametrize(
    "browser", ["", "/usr/bin/vivaldi", "C:\\x\\vivaldi", "C:\\a|b\\v.exe", "C:\\v\u00e9.exe"]
)
def test_launcher_refuses_a_browser_that_is_not_a_windows_exe(box, browser):
    (box.tmp / "desk").mkdir()
    args = [
        "launcher",
        "--desktop",
        str(box.tmp / "desk"),
        "--distro",
        "Ubuntu",
        "--hub",
        str(box.hub),
    ]
    r = box.run(*args, "--browser", browser)
    assert r.returncode == 2 and not _bat(box).exists() and "Traceback" not in r.stderr, r.stderr


@pytest.mark.parametrize("distro", ["", "-x", "a|b", "a\nb"])
def test_launcher_refuses_a_bad_distro(box, distro):
    (box.tmp / "desk").mkdir()
    args = [
        "launcher",
        "--desktop",
        str(box.tmp / "desk"),
        "--hub",
        str(box.hub),
        "--distro",
        distro,
    ]
    r = box.run(*args)
    assert r.returncode == 2 and not _bat(box).exists()


def test_launcher_a_bat_that_is_a_directory_is_a_clean_refusal(box):
    _bat(box).mkdir(parents=True)
    r = box.run(
        "launcher", "--desktop", str(box.tmp / "desk"), "--distro", "Ubuntu", "--hub", str(box.hub)
    )
    assert r.returncode == 2 and "Traceback" not in r.stderr, r.stderr


def test_launcher_first_run_opens_the_board_even_when_the_browser_runs(box):
    (box.tmp / "desk").mkdir()
    box.run(
        "launcher", "--desktop", str(box.tmp / "desk"), "--distro", "Ubuntu", "--hub", str(box.hub)
    )
    text = _bat(box).read_bytes().decode()
    assert text.index("if not exist") < text.index("tasklist"), (
        "first run is handled before the running check"
    )
    first = text[text.index("if not exist") : text.index("tasklist")]
    assert "http://localhost:%PORT%/" in first and "echo opened>" in first and "exit /b 0" in first
    assert first.index("start ") < first.index("echo opened>")
    assert "curl.exe -s -m 2 " in text


def test_profile_treats_an_empty_settings_file_as_no_settings(box):
    box.settings.parent.mkdir(parents=True)
    box.settings.write_text("  \n")
    r = box.run("profile")
    assert r.returncode == 0, r.stderr
    assert json.loads(box.settings.read_text()) == PROFILE


def test_profile_rerun_takes_no_second_backup_and_keeps_non_ascii(box):
    box.settings.parent.mkdir(parents=True)
    box.settings.write_text(json.dumps({"x.label": "caf\u00e9"}))
    assert box.run("profile").returncode == 0
    assert box.run("profile").returncode == 0
    assert len(list(box.backups.glob("settings.json.*"))) == 1
    assert "caf\u00e9" in box.settings.read_text(encoding="utf-8")


def test_install_refuses_both_units_on_one_port(box):
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_text("FABRIK_DECK_CODE_PORT=9000\nFABRIK_DECK_PORT=9000\n")
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 1 and "9000" in r.stderr
    assert not box.unit_path.exists() and box.calls("systemctl") == []


def test_install_refuses_a_backup_it_cannot_write_before_any_write(box):
    box.config_yaml.parent.mkdir(parents=True)
    box.config_yaml.write_text("auth: password\n")
    box.backups.parent.mkdir(parents=True)
    box.backups.write_text("a file where the backups folder goes")
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 1 and "Traceback" not in r.stderr, r.stderr
    assert box.config_yaml.read_text() == "auth: password\n" and not box.env_file.exists()


def test_install_refuses_a_non_utf8_env_file_cleanly(box):
    box.env_file.parent.mkdir(parents=True)
    box.env_file.write_bytes(b"FABRIK_DECK=1\n\xff\n")
    r = box.run("install", "--hub", str(box.hub))
    assert r.returncode == 1 and "Traceback" not in r.stderr, r.stderr
    assert box.env_file.read_bytes() == b"FABRIK_DECK=1\n\xff\n"


def test_config_yaml_replaces_only_top_level_keys():
    spec = importlib.util.spec_from_file_location("fabrik_deck_yaml_probe", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    old = 'foo:\n  auth: x\n  cert: 1\n"auth": password\n# auth: y\n'
    new = m._config_yaml_text(old, 8443).splitlines()
    assert new[:3] == ["foo:", "  auth: x", "  cert: 1"]
    assert new.count("auth: none") == 1 and not any(line.startswith('"auth"') for line in new)
    assert "# auth: y" in new and "bind-addr: 127.0.0.1:8443" in new and "cert: false" in new


def test_profile_rewrites_a_number_where_the_deck_wants_a_boolean(box):
    box.settings.parent.mkdir(parents=True)
    box.settings.write_text(
        json.dumps({**PROFILE, "window.autoDetectColorScheme": 0, "workbench.statusBar.visible": 1})
    )
    assert box.run("profile").returncode == 0
    got = json.loads(box.settings.read_text())
    assert (
        got["window.autoDetectColorScheme"] is False and got["workbench.statusBar.visible"] is True
    )


# --- W-b364b48d: the default distro when WSL_DISTRO_NAME is unset ------------------------------------------------
def _deck_module():
    spec = importlib.util.spec_from_file_location("fabrik_deck_distro_probe", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _fake_wslpath(tmp_path: Path, out: str, rc: int = 0) -> Path:
    """A wslpath stand-in printing ``out`` for `-w /`, and logging that it ran."""
    exe = tmp_path / "wslpath"
    _exe(
        exe,
        f"#!{sys.executable}\nimport sys\nopen({str(tmp_path / 'wslpath.log')!r}, 'a').write(' '.join(sys.argv[1:]))\n"
        f"sys.stdout.write({out!r})\nsys.exit({rc})\n",
    )
    return exe


@pytest.fixture
def no_env_distro(monkeypatch, tmp_path):
    m = _deck_module()
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    (tmp_path / "desk").mkdir()
    return m


def test_default_distro_prefers_a_non_empty_environment(no_env_distro, monkeypatch, tmp_path):
    m = no_env_distro
    monkeypatch.setenv("WSL_DISTRO_NAME", "Mine")
    monkeypatch.setattr(m, "WSLPATH", str(_fake_wslpath(tmp_path, "\\\\wsl.localhost\\Other\\\n")))
    assert m._default_distro() == "Mine"
    assert not (tmp_path / "wslpath.log").exists()


@pytest.mark.parametrize("env", [None, ""])
@pytest.mark.parametrize(
    "out", ["\\\\wsl.localhost\\Ubuntu-24.04\\\n", "\\\\wsl$\\Ubuntu-24.04\\\n"]
)
def test_default_distro_reads_this_distro_from_wslpath(
    no_env_distro, monkeypatch, tmp_path, env, out
):
    m = no_env_distro
    if env is not None:
        monkeypatch.setenv("WSL_DISTRO_NAME", env)
    monkeypatch.setattr(m, "WSLPATH", str(_fake_wslpath(tmp_path, out)))
    assert m._default_distro() == "Ubuntu-24.04"
    assert (tmp_path / "wslpath.log").read_text() == "-w /"


@pytest.mark.parametrize("case", ["missing", "rc", "not-a-unc"])
def test_default_distro_is_empty_when_wslpath_cannot_name_one(
    no_env_distro, monkeypatch, tmp_path, case
):
    m = no_env_distro
    if case == "missing":
        exe = tmp_path / "absent"
    elif case == "rc":
        exe = _fake_wslpath(tmp_path, "\\\\wsl.localhost\\Ubuntu-24.04\\\n", rc=1)
    else:
        exe = _fake_wslpath(tmp_path, "C:\\\n")
    monkeypatch.setattr(m, "WSLPATH", str(exe))
    assert m._default_distro() == ""


def test_launcher_without_a_distro_refuses_naming_both_remedies(
    no_env_distro, monkeypatch, tmp_path, capsys
):
    m = no_env_distro
    monkeypatch.setattr(m, "WSLPATH", str(tmp_path / "absent"))
    with pytest.raises(SystemExit) as exit_:
        m.main(["launcher", "--desktop", str(tmp_path / "desk"), "--hub", "/opt/fabrik"])
    assert exit_.value.code == 2
    err = capsys.readouterr().err
    assert "WSL_DISTRO_NAME" in err and "--distro" in err and "none derived" in err
    assert not (tmp_path / "desk" / "Fabrik Deck.bat").exists()


def test_launcher_without_a_distro_pins_this_distro(no_env_distro, monkeypatch, tmp_path, capsys):
    m = no_env_distro
    monkeypatch.setattr(
        m, "WSLPATH", str(_fake_wslpath(tmp_path, "\\\\wsl.localhost\\Ubuntu-24.04\\\n"))
    )
    m.main(["launcher", "--desktop", str(tmp_path / "desk"), "--hub", "/opt/fabrik"])
    text = (tmp_path / "desk" / "Fabrik Deck.bat").read_bytes().decode("ascii")
    assert "wsl.exe --distribution Ubuntu-24.04 --exec" in text
    assert "--distro derived as Ubuntu-24.04" in capsys.readouterr().err


def test_an_explicit_distro_wins_and_nothing_is_derived(no_env_distro, monkeypatch, tmp_path):
    m = no_env_distro
    monkeypatch.setenv("WSL_DISTRO_NAME", "FromEnv")
    monkeypatch.setattr(m, "WSLPATH", str(_fake_wslpath(tmp_path, "\\\\wsl.localhost\\Other\\\n")))
    m.main(
        [
            "launcher",
            "--desktop",
            str(tmp_path / "desk"),
            "--hub",
            "/opt/fabrik",
            "--distro",
            "Explicit",
        ]
    )
    text = (tmp_path / "desk" / "Fabrik Deck.bat").read_bytes().decode("ascii")
    assert "--distribution Explicit --exec" in text
    assert not (tmp_path / "wslpath.log").exists()


def test_a_derived_distro_name_cmd_would_split_is_refused(no_env_distro, monkeypatch, tmp_path):
    m = no_env_distro
    monkeypatch.setattr(
        m, "WSLPATH", str(_fake_wslpath(tmp_path, "\\\\wsl.localhost\\Ub&calc\\\n"))
    )
    with pytest.raises(SystemExit) as exit_:
        m.main(["launcher", "--desktop", str(tmp_path / "desk"), "--hub", "/opt/fabrik"])
    assert exit_.value.code == 2
    assert not (tmp_path / "desk" / "Fabrik Deck.bat").exists()


def test_the_derived_notice_is_for_wslpath_only(no_env_distro, monkeypatch, tmp_path, capsys):
    m = no_env_distro
    monkeypatch.setenv("WSL_DISTRO_NAME", "FromEnv")
    m.main(["launcher", "--desktop", str(tmp_path / "desk"), "--hub", "/opt/fabrik"])
    assert "derived" not in capsys.readouterr().err


def test_a_blank_environment_name_falls_back_to_wslpath(no_env_distro, monkeypatch, tmp_path):
    m = no_env_distro
    monkeypatch.setenv("WSL_DISTRO_NAME", "  ")
    monkeypatch.setattr(
        m, "WSLPATH", str(_fake_wslpath(tmp_path, "\\\\wsl.localhost\\Ubuntu-24.04\\\n"))
    )
    assert m._default_distro() == "Ubuntu-24.04"


def test_a_wslpath_timeout_is_no_distro(no_env_distro, monkeypatch):
    m = no_env_distro

    def hang(*a, **k):
        raise subprocess.TimeoutExpired(a[0], k.get("timeout"))

    monkeypatch.setattr(m.subprocess, "run", hang)
    assert m._default_distro() == ""


def test_an_explicit_empty_distro_is_refused_never_derived(
    no_env_distro, monkeypatch, tmp_path, capsys
):
    m = no_env_distro
    monkeypatch.setattr(
        m, "WSLPATH", str(_fake_wslpath(tmp_path, "\\\\wsl.localhost\\Ubuntu-24.04\\\n"))
    )
    with pytest.raises(SystemExit) as exit_:
        m.main(
            [
                "launcher",
                "--desktop",
                str(tmp_path / "desk"),
                "--hub",
                "/opt/fabrik",
                "--distro",
                "",
            ]
        )
    assert exit_.value.code == 2 and "is not a WSL distro name" in capsys.readouterr().err
    assert not (tmp_path / "wslpath.log").exists()


def _record_install(m, monkeypatch) -> list:
    calls: list = []
    monkeypatch.setattr(m.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(m, "install", lambda *a: calls.append(a))
    return calls


def test_install_without_a_desktop_never_probes(no_env_distro, monkeypatch, tmp_path):
    m = no_env_distro
    monkeypatch.setattr(
        m, "WSLPATH", str(_fake_wslpath(tmp_path, "\\\\wsl.localhost\\Ubuntu-24.04\\\n"))
    )
    calls = _record_install(m, monkeypatch)
    m.main(["install", "--hub", str(tmp_path)])
    assert len(calls) == 1 and calls[0][3] == ""
    assert not (tmp_path / "wslpath.log").exists()


def test_install_with_a_desktop_and_no_distro_refuses_exit_1(
    no_env_distro, monkeypatch, tmp_path, capsys
):
    m = no_env_distro
    monkeypatch.setattr(m, "WSLPATH", str(tmp_path / "absent"))
    calls = _record_install(m, monkeypatch)
    with pytest.raises(SystemExit) as exit_:
        m.main(["install", "--hub", str(tmp_path), "--desktop", str(tmp_path / "desk")])
    assert exit_.value.code == 1 and "none derived" in capsys.readouterr().err
    assert calls == []
