"""The hourly scratch-janitor timer and its installer (W-d1a4a8f5).

The units are verified by the real ``systemd-analyze``; the installer runs against stub ``loginctl``,
``systemctl``, ``systemd-analyze`` and ``crontab`` in a throwaway HOME, so no test touches the live
manager or the live crontab. The contract: the timer is the primary scheduler and cron's 04:20 line
stays as the fallback — the installer never reads or writes the crontab.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UNITS = REPO / "scripts" / "sysadmin" / "systemd"
INSTALLER = REPO / "scripts" / "sysadmin" / "install_scratch_sweep_timer.sh"
UNDO = "systemctl --user disable --now scratch-sweep.timer"


def _sections(name: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur = ""
    for raw in (UNITS / name).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            cur = line
            out[cur] = []
        else:
            out[cur].append(line)
    return out


def test_the_units_run_the_janitor_hourly_and_verify() -> None:
    svc = _sections("scratch-sweep.service")["[Service]"]
    assert "Type=oneshot" in svc
    assert [v for v in svc if v.startswith("ExecStart=")] == [
        "ExecStart=/usr/bin/python3 /opt/fabrik/scripts/scratch_sweep.py --dead --apply"
    ]
    # the sweep takes its own lock: a flock wrapper would make it sweep nothing
    assert not any("flock" in v for v in svc), svc
    # a run is capped inside the hourly period (the timer never starts a second instance anyway)
    assert "TimeoutStartSec=55min" in svc, svc
    timer = _sections("scratch-sweep.timer")
    t = timer["[Timer]"]
    assert "OnCalendar=*-*-* *:20:00" in t and "Persistent=true" in t, t
    assert "Unit=scratch-sweep.service" in t
    assert timer["[Install]"] == ["WantedBy=timers.target"]

    analyze = shutil.which("systemd-analyze")
    if analyze is None:
        pytest.skip("systemd-analyze not installed")
    r = subprocess.run(
        [
            analyze,
            "--user",
            "verify",
            str(UNITS / "scratch-sweep.service"),
            str(UNITS / "scratch-sweep.timer"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0 and (r.stdout + r.stderr).strip() == "", r.stdout + r.stderr


def _world(
    tmp_path: Path,
    *,
    linger: str = "Linger=yes",
    verify_says: str = "",
    verify_rc: int = 0,
    active: str = "active",
    fails: str = "",
) -> tuple[Path, dict[str, str], Path]:
    """A copy of the installer and units, a fake janitor, and stub commands logging to calls.log.
    The stub crontab exits 99 so a call to it can never pass unseen."""
    root = tmp_path / "inst"
    (root / "systemd").mkdir(parents=True)
    shutil.copy2(INSTALLER, root / INSTALLER.name)
    for f in UNITS.glob("scratch-sweep.*"):
        shutil.copy2(f, root / "systemd" / f.name)
    janitor = tmp_path / "scratch_sweep.py"
    janitor.write_text("# stand-in\n")
    svc = root / "systemd" / "scratch-sweep.service"
    svc.write_text(svc.read_text().replace("/opt/fabrik/scripts/scratch_sweep.py", str(janitor)))
    log = tmp_path / "calls.log"
    bin_ = tmp_path / "ibin"
    bin_.mkdir()
    stubs = {
        "loginctl": f"echo {linger}",
        "systemctl": (
            f'echo "systemctl $*" >> "{log}"\n'
            + (f'case "$*" in *"{fails}"*) exit 1;; esac\n' if fails else "")
            + f'case "$*" in *is-active*) echo {active};; esac'
        ),
        "systemd-analyze": f'echo "verify $*" >> "{log}"\nprintf "%s" "{verify_says}"\nexit {verify_rc}',
        "crontab": f'echo "crontab $*" >> "{log}"\nexit 99',
    }
    for name, body in stubs.items():
        p = bin_ / name
        p.write_text(f"#!/bin/sh\n{body}\n")
        p.chmod(0o755)
    env = {
        "PATH": f"{bin_}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
    }
    return root, env, log


def _install(root: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(root / INSTALLER.name)], env=env, capture_output=True, text=True, timeout=60
    )


def _calls(log: Path) -> list[str]:
    return log.read_text().splitlines() if log.exists() else []


def _installed(tmp_path: Path) -> bool:
    return (tmp_path / "cfg" / "systemd" / "user" / "scratch-sweep.service").exists()


def test_the_installer_enables_the_timer_and_never_touches_the_crontab(tmp_path: Path) -> None:
    root, env, log = _world(tmp_path)
    r = _install(root, env)
    assert r.returncode == 0, r.stderr
    dest = tmp_path / "cfg" / "systemd" / "user"
    for name in ("scratch-sweep.service", "scratch-sweep.timer"):
        assert (dest / name).read_bytes() == (root / "systemd" / name).read_bytes(), name
    calls = _calls(log)
    order = [
        "systemctl --user daemon-reload",
        "systemctl --user enable scratch-sweep.timer",
        "systemctl --user restart scratch-sweep.timer",
        "systemctl --user is-active scratch-sweep.timer",
    ]
    assert [calls.index(c) for c in order] == sorted(calls.index(c) for c in order), calls
    # cron's 04:20 line is the fallback for a dead user manager: the installer never reads or edits it
    assert not any(c.startswith("crontab") for c in calls), calls
    assert f"To undo, run: {UNDO}" in r.stdout, r.stdout
    assert UNDO not in calls


@pytest.mark.parametrize(
    ("kw", "says"),
    [
        ({"linger": "Linger=no"}, "linger"),
        (
            {"verify_says": "x.timer:3: Unknown key name 'Bogus' in section 'Timer', ignoring."},
            "Unknown key",
        ),
        # a verify that fails silently: its exit code alone must refuse
        ({"verify_rc": 1}, "verify exited 1"),
    ],
    ids=["linger", "verify-warning", "verify-exit"],
)
def test_a_refused_install_makes_no_systemctl_call(
    tmp_path: Path, kw: dict[str, str | int], says: str
) -> None:
    root, env, log = _world(tmp_path, **kw)  # type: ignore[arg-type]
    r = _install(root, env)
    assert r.returncode == 1
    assert says in r.stderr, r.stderr
    assert not _installed(tmp_path)
    assert not any(c.startswith("systemctl") for c in _calls(log))


def test_a_missing_janitor_refuses_before_any_systemctl_call(tmp_path: Path) -> None:
    root, env, log = _world(tmp_path)
    (tmp_path / "scratch_sweep.py").unlink()
    r = _install(root, env)
    assert r.returncode == 1 and "does not exist" in r.stderr, r.stderr
    assert not _installed(tmp_path)
    assert not any(c.startswith("systemctl") for c in _calls(log))


def test_a_timer_that_is_not_active_is_disabled_again(tmp_path: Path) -> None:
    root, env, log = _world(tmp_path, active="failed")
    r = _install(root, env)
    assert r.returncode == 1
    assert "not active" in r.stderr and "cron's 04:20 line still runs" in r.stderr, r.stderr
    assert UNDO in _calls(log)
    assert not any(c.startswith("crontab") for c in _calls(log))


def test_a_failing_information_step_does_not_fail_the_install(tmp_path: Path) -> None:
    root, env, log = _world(tmp_path, fails="list-timers")
    r = _install(root, env)
    assert r.returncode == 0, r.stderr
    assert UNDO not in _calls(log)
