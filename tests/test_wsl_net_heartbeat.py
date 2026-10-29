"""Graders for the WSL network heartbeat (W-960d68a8, docs/workstation/wsl-net-heartbeat.md).

The script is driven for real: real curl against a local HTTP server, real touch on a tmp directory.
The units are verified by the real ``systemd-analyze``; the installer runs against stub
``loginctl``/``systemctl``/``systemd-analyze`` on PATH, the way tests/test_session_archive_alert.py
drives the session-archive installer.
"""

from __future__ import annotations

import http.server
import os
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "wsl_net_heartbeat.sh"
UNITS = REPO / "scripts" / "sysadmin" / "systemd"
INSTALLER = REPO / "scripts" / "sysadmin" / "install_wsl_net_heartbeat_timer.sh"
OLD = 1_000_000_000  # an mtime far in the past, so any touch is visible as a change


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 — the stdlib's name
        if self.path == "/ok":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Microsoft Connect Test")
        elif self.path == "/redir":  # a captive portal's answer: curl -f passes any status < 400
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/portal")
            self.end_headers()
        elif self.path == "/slow":
            time.sleep(8)  # past the script's curl -m 5
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    # WSL's loopback can refuse a connect for a few ms after listen() on port 0: wait until it accepts
    deadline = time.monotonic() + 5
    while True:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            break
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.02)
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def _closed_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _run(beat: Path, url: str) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(beat.parent),
        "WSL_NET_HEARTBEAT_DIR": str(beat),
        "WSL_NET_HEARTBEAT_URL": url,
    }
    return subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60
    )


def _aged(beat: Path) -> None:
    beat.mkdir(parents=True, exist_ok=True)
    for name in ("wsl-net-ran", "wsl-net-ok"):
        (beat / name).touch()
        os.utime(beat / name, (OLD, OLD))


@pytest.mark.parametrize("path", ["/ok", "/redir"])
def test_a_reachable_probe_refreshes_both_files(tmp_path: Path, server: str, path: str) -> None:
    beat = tmp_path / "beat"
    beat.mkdir()
    r = _run(beat, server + path)
    assert r.returncode == 0, r.stderr
    assert (beat / "wsl-net-ran").is_file() and (beat / "wsl-net-ok").is_file(), (
        "an absent file is created"
    )

    _aged(beat)
    r = _run(beat, server + path)
    assert r.returncode == 0, r.stderr
    for name in ("wsl-net-ran", "wsl-net-ok"):
        assert (beat / name).stat().st_mtime > OLD, (
            f"{name} must change on a reachable probe ({path})"
        )


@pytest.mark.parametrize("case", ["refused", "http-404", "timeout"])
def test_an_unreachable_probe_refreshes_only_the_ran_file(
    tmp_path: Path, server: str, case: str
) -> None:
    url = {
        "refused": f"http://127.0.0.1:{_closed_port()}/",
        "http-404": server + "/missing",
        "timeout": server + "/slow",
    }[case]
    beat = tmp_path / "beat"
    _aged(beat)
    r = _run(beat, url)
    assert r.returncode == 0, "a probe failure is an outage, not a broken heartbeat: " + r.stderr
    assert (beat / "wsl-net-ran").stat().st_mtime > OLD, (
        "the ran file proves the heartbeat itself is alive"
    )
    assert (beat / "wsl-net-ok").stat().st_mtime == OLD, (
        "the ok file must not move when WSL cannot fetch"
    )
    assert "curl: (" in r.stderr, "curl's own reason reaches the journal: " + r.stderr


def test_an_unwritable_heartbeat_dir_fails_the_run(tmp_path: Path, server: str) -> None:
    r = _run(tmp_path / "no" / "such" / "dir", server + "/ok")
    assert r.returncode != 0, "a heartbeat that cannot be written is a real fault"

    beat = tmp_path / "ro"
    _aged(beat)
    (beat / "wsl-net-ran").unlink()
    (beat / "wsl-net-ok").unlink()
    beat.chmod(0o500)
    try:
        r = _run(beat, server + "/ok")
    finally:
        beat.chmod(0o700)
    assert r.returncode != 0, "a read-only heartbeat dir fails the run"
    assert not (beat / "wsl-net-ok").exists()


def _sections(name: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur = ""
    for raw in (UNITS / name).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            cur = line
            out.setdefault(cur, [])
        else:
            out[cur].append(line)
    return out


def test_the_units_verify_and_run_the_script_every_minute() -> None:
    svc = _sections("wsl-net-heartbeat.service")["[Service]"]
    assert "Type=oneshot" in svc
    # bash-wrapped: verify refuses a direct ExecStart= of a script the main checkout lacks before merge
    assert [v for v in svc if v.startswith("ExecStart=")] == [
        "ExecStart=/usr/bin/bash /opt/fabrik/scripts/sysadmin/wsl_net_heartbeat.sh"
    ]
    timer = _sections("wsl-net-heartbeat.timer")
    t = timer["[Timer]"]
    assert "OnUnitActiveSec=60s" in t and "AccuracySec=5s" in t and "OnBootSec=30s" in t, t
    assert "Unit=wsl-net-heartbeat.service" in t
    assert timer["[Install]"] == ["WantedBy=timers.target"]

    analyze = shutil.which("systemd-analyze")
    if analyze is None:
        pytest.skip("systemd-analyze not installed")
    r = subprocess.run(
        [
            analyze,
            "--user",
            "verify",
            str(UNITS / "wsl-net-heartbeat.service"),
            str(UNITS / "wsl-net-heartbeat.timer"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0 and (r.stdout + r.stderr).strip() == "", (
        "a misplaced key is only a warning at rc 0: " + r.stdout + r.stderr
    )


def _installer_world(
    tmp_path: Path, *, linger: str = "Linger=yes", verify_says: str = "", verify_rc: int = 0
) -> tuple[Path, dict[str, str], Path]:
    root = tmp_path / "inst"
    (root / "systemd").mkdir(parents=True)
    shutil.copy2(INSTALLER, root / INSTALLER.name)
    for f in UNITS.glob("wsl-net-heartbeat.*"):
        shutil.copy2(f, root / "systemd" / f.name)
    script = tmp_path / "wsl_net_heartbeat.sh"
    script.write_text("#!/usr/bin/env bash\n")
    bin_ = tmp_path / "ibin"
    bin_.mkdir()
    log = tmp_path / "calls.log"
    for name, body in {
        "loginctl": f"echo {linger}",
        "systemctl": f'echo "systemctl $*" >> "{log}"',
        "systemd-analyze": f'echo "verify $*" >> "{log}"\nprintf "%s" "{verify_says}"\nexit {verify_rc}',
    }.items():
        p = bin_ / name
        p.write_text(f"#!/bin/sh\n{body}\n")
        p.chmod(0o755)
    env = {
        "PATH": f"{bin_}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
        "WSL_NET_HEARTBEAT_SCRIPT": str(script),
    }
    return root, env, log


def _install(root: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(root / INSTALLER.name)], env=env, capture_output=True, text=True, timeout=60
    )


def test_the_installer_installs_and_enables_the_timer(tmp_path: Path) -> None:
    root, env, log = _installer_world(tmp_path)
    r = _install(root, env)
    assert r.returncode == 0, r.stderr
    dest = tmp_path / "cfg" / "systemd" / "user"
    for name in ("wsl-net-heartbeat.service", "wsl-net-heartbeat.timer"):
        assert (dest / name).read_bytes() == (UNITS / name).read_bytes(), name
    calls = log.read_text().splitlines()
    reload_at = calls.index("systemctl --user daemon-reload")
    enable_at = calls.index("systemctl --user enable --now wsl-net-heartbeat.timer")
    assert reload_at < enable_at, calls


def test_the_installer_refuses_without_linger_script_or_a_clean_verify(tmp_path: Path) -> None:
    dest_svc = Path("cfg") / "systemd" / "user" / "wsl-net-heartbeat.service"
    cases: dict[str, tuple[dict[str, object], str]] = {
        "linger": ({"linger": "Linger=no"}, "linger"),
        "warning": (
            {"verify_says": "x.timer:3: Unknown key name 'Bogus' in section 'Timer', ignoring."},
            "Unknown key",
        ),
        "rc": ({"verify_rc": 1}, "verify exited 1"),
        "script": ({}, "wsl_net_heartbeat.sh"),
    }
    for case, (kw, says) in cases.items():
        base = tmp_path / case
        root, env, log = _installer_world(base, **kw)  # type: ignore[arg-type]
        if case == "script":
            Path(env["WSL_NET_HEARTBEAT_SCRIPT"]).unlink()
        r = _install(root, env)
        assert r.returncode != 0, case
        assert says in r.stderr, (case, r.stderr)
        assert not (base / dest_svc).exists(), f"{case}: nothing is installed on a refusal"
        assert "enable" not in (log.read_text() if log.exists() else ""), case
