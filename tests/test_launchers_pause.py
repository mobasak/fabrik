# AFTER-EDIT: scripts/sysadmin/weekly_catchup.sh, scripts/ci_fix_dispatcher.py, scripts/audit_all_registrars.py, scripts/enforcement/check_mutation.py
"""Cron launchers skip while a hibernate pause is marked (T03a, seam P: `hibernate.py paused`).

Exit 0 skips (stamp untouched, one log line); exit 1, >=2, a timeout or a missing script proceeds.
The fake `hibernate.py` is injected through FABRIK_HIBERNATE_PY; nothing touches a live marker.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _fake_hibernate(tmp_path: Path, rc: int) -> Path:
    p = tmp_path / f"hibernate_rc{rc}.py"
    p.write_text(f"import sys\nsys.exit({rc})\n")
    return p


def _slow_hibernate(tmp_path: Path) -> Path:
    p = tmp_path / "hibernate_slow.py"
    p.write_text("import time\ntime.sleep(60)\n")
    return p


def _hib_lines(text: str) -> int:
    return len([ln for ln in text.splitlines() if "hibernate.py" in ln])


def _boom(*a, **k):
    raise AssertionError("must stop before this call")


# -- weekly_catchup.sh ----------------------------------------------------------


def _catchup(tmp_path: Path, hib: str | None) -> tuple[subprocess.CompletedProcess, Path]:
    for sub in ("locks", "events", "runs"):
        (tmp_path / sub).mkdir(exist_ok=True)
    root = tmp_path / "root"
    root.mkdir(exist_ok=True)
    for sub in ("scripts", "src"):
        if not (root / sub).exists():
            (root / sub).symlink_to(REPO_ROOT / sub, target_is_directory=True)
    env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "TMPDIR") if k in os.environ}
    env.update(
        HOME=str(tmp_path),
        FABRIK_ROOT=str(root),
        FABRIK_PY=sys.executable,
        FABRIK_NO_AUTOLOAD="1",
        ALERT_ENABLED="0",
        CLAUDE_SOUND_LOCKDIR=str(tmp_path / "locks"),
        KAIZEN_EVENTS_DIR=str(tmp_path / "events"),
        COMMAND_RUN_DIR=str(tmp_path / "runs"),
    )
    if hib is not None:
        env["FABRIK_HIBERNATE_PY"] = hib
    script = root / "scripts" / "sysadmin" / "weekly_catchup.sh"
    proc = subprocess.run(
        ["bash", str(script), "kaizen_coroner.py"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    return proc, tmp_path / ".claude" / "state" / "daily-kaizen_coroner.py.stamp"


def test_weekly_catchup_starts_nothing_while_paused(tmp_path: Path) -> None:
    proc, stamp = _catchup(tmp_path, str(_fake_hibernate(tmp_path, 0)))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not stamp.exists(), "a skipped run leaves its stamp untouched"
    assert "running" not in proc.stdout
    assert len(proc.stdout.strip().splitlines()) == 1 and "hibernate pause" in proc.stdout


@pytest.mark.parametrize("rc", [1, 2])
def test_weekly_catchup_proceeds_on_not_paused_or_error(tmp_path: Path, rc: int) -> None:
    proc, stamp = _catchup(tmp_path, str(_fake_hibernate(tmp_path, rc)))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert stamp.is_file(), "fail-open: the job ran and stamped"
    assert _hib_lines(proc.stderr) == (0 if rc == 1 else 1), proc.stderr


def test_weekly_catchup_proceeds_when_the_script_is_absent(tmp_path: Path) -> None:
    proc, stamp = _catchup(tmp_path, str(tmp_path / "nope.py"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert stamp.is_file()
    assert _hib_lines(proc.stderr) == 1, proc.stderr


def test_weekly_catchup_proceeds_on_a_timeout(tmp_path: Path) -> None:
    # the 10 s bound is the launcher's; the fake sleeps 60 s
    proc, stamp = _catchup(tmp_path, str(_slow_hibernate(tmp_path)))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert stamp.is_file()
    assert _hib_lines(proc.stderr) == 1, proc.stderr


# -- ci_fix_dispatcher.py -------------------------------------------------------


@pytest.fixture
def cfd():
    return _load("ci_fix_dispatcher_t03a", "scripts/ci_fix_dispatcher.py")


def test_ci_fix_main_skips_while_paused(cfd, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FABRIK_HIBERNATE_PY", str(_fake_hibernate(tmp_path, 0)))
    monkeypatch.setattr(cfd, "sh", _boom)
    monkeypatch.setattr(sys, "argv", ["ci_fix_dispatcher.py"])
    assert cfd.main() == 0
    assert "hibernate pause" in capsys.readouterr().out


@pytest.mark.parametrize("mode", ["rc2", "absent", "timeout"])
def test_ci_fix_main_proceeds_when_paused_cannot_answer(cfd, monkeypatch, tmp_path, capsys, mode):
    hib = {
        "rc2": _fake_hibernate(tmp_path, 2),
        "absent": tmp_path / "nope.py",
        "timeout": _slow_hibernate(tmp_path),
    }[mode]
    monkeypatch.setenv("FABRIK_HIBERNATE_PY", str(hib))
    reached = []
    monkeypatch.setattr(cfd, "sh", lambda *a, **k: (reached.append(a) or (1, "")))
    monkeypatch.setattr(sys, "argv", ["ci_fix_dispatcher.py"])
    assert cfd.main() == 1  # the gh-auth stub failed: main() went past the pause check
    assert reached
    assert len(capsys.readouterr().out.strip().splitlines()) == 1  # the one log line


def test_ci_fix_worker_env_and_oom_score(cfd, monkeypatch, tmp_path):
    fake = tmp_path / "bin"
    fake.mkdir()
    claude = fake / "claude"
    claude.write_text(
        "#!/bin/sh\necho WATCHDOG=$CLAUDE_CODE_RETRY_WATCHDOG\ncat /proc/self/oom_score_adj\n"
    )
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{fake}:{os.environ['PATH']}")
    monkeypatch.setattr(cfd, "LOG_DIR", tmp_path)
    log = tmp_path / "w.log"
    assert cfd.dispatch(tmp_path, "brief", log, dry_run=False) == 0
    text = log.read_text()
    assert "WATCHDOG=1" in text
    assert "\n500\n" in text


# -- audit_all_registrars.py ----------------------------------------------------


def _audit(monkeypatch, tmp_path, name: str, rc: int, hib: Path | None = None) -> dict:
    aar = _load(name, "scripts/audit_all_registrars.py")
    seen: dict = {}
    monkeypatch.setenv("FABRIK_REGISTRY_RECONCILE", "apply")
    monkeypatch.setenv("FABRIK_HIBERNATE_PY", str(hib or _fake_hibernate(tmp_path, rc)))
    monkeypatch.setattr(aar.registry_reconcile, "claims", lambda specs: ({}, []))

    def rec(results, claim_map, claims_complete, dry_run):
        seen["dry"] = dry_run
        return []

    monkeypatch.setattr(aar.registry_reconcile, "reconcile_postgres", rec)
    aar._reconcile([], {}, 0)
    return seen


def test_audit_reconcile_is_report_only_while_paused(monkeypatch, tmp_path):
    assert _audit(monkeypatch, tmp_path, "aar_t03a_paused", 0)["dry"] is True


def test_audit_reconcile_applies_when_not_paused(monkeypatch, tmp_path):
    assert _audit(monkeypatch, tmp_path, "aar_t03a_free", 2)["dry"] is False


@pytest.mark.parametrize("mode", ["rc2", "absent", "timeout"])
def test_audit_proceeds_and_logs_one_line_when_paused_cannot_answer(
    monkeypatch, tmp_path, caplog, mode
):
    hib = {
        "rc2": _fake_hibernate(tmp_path, 2),
        "absent": tmp_path / "nope.py",
        "timeout": _slow_hibernate(tmp_path),
    }[mode]
    with caplog.at_level("INFO"):
        seen = _audit(monkeypatch, tmp_path, f"aar_t03a_{mode}", 2, hib)
    assert seen["dry"] is False  # fail-open: apply proceeds
    assert len([r for r in caplog.records if "hibernate.py" in r.getMessage()]) == 1


def test_audit_probe_survives_any_exception(monkeypatch, tmp_path, caplog):
    # the probe must never kill the audit push: not just OSError/Timeout
    aar = _load("aar_t03a_anyexc", "scripts/audit_all_registrars.py")
    monkeypatch.setenv("FABRIK_HIBERNATE_PY", str(_fake_hibernate(tmp_path, 0)))

    def boom_run(cmd, *, stdin, **_kw):  # the signature a sibling suite's fake_run has
        raise AssertionError("unexpected call shape")

    monkeypatch.setattr(aar.subprocess, "run", boom_run)
    with caplog.at_level("INFO"):
        assert aar._hibernate_paused() is False
    assert len([r for r in caplog.records if "hibernate.py" in r.getMessage()]) == 1


# -- check_mutation.py ----------------------------------------------------------


def test_check_mutation_skips_while_paused_and_exits_zero(monkeypatch, tmp_path, capsys):
    cm = _load("check_mutation_t03a", "scripts/enforcement/check_mutation.py")
    monkeypatch.setenv("FABRIK_MUTMUT", "1")
    monkeypatch.setenv("FABRIK_HIBERNATE_PY", str(_fake_hibernate(tmp_path, 0)))
    monkeypatch.setattr(cm, "mutmut_bin", lambda: "/usr/bin/mutmut")
    monkeypatch.setattr(cm, "changed_python", _boom)
    assert cm.main() == 0
    assert "hibernate pause" in capsys.readouterr().out


def _cm_run(monkeypatch, cm, hib: Path):
    monkeypatch.setenv("FABRIK_MUTMUT", "1")
    monkeypatch.setenv("FABRIK_HIBERNATE_PY", str(hib))
    monkeypatch.setattr(cm, "mutmut_bin", lambda: "/usr/bin/mutmut")
    ran = []
    monkeypatch.setattr(cm, "changed_python", lambda base=None: ran.append(1) or [])
    return ran


@pytest.mark.parametrize("mode", ["rc1", "rc2", "absent", "timeout"])
def test_check_mutation_proceeds_when_not_paused_or_unanswerable(
    monkeypatch, tmp_path, capsys, mode
):
    cm = _load(f"check_mutation_t03a_{mode}", "scripts/enforcement/check_mutation.py")
    hib = {
        "rc1": _fake_hibernate(tmp_path, 1),
        "rc2": _fake_hibernate(tmp_path, 2),
        "absent": tmp_path / "nope.py",
        "timeout": _slow_hibernate(tmp_path),
    }[mode]
    ran = _cm_run(monkeypatch, cm, hib)
    assert cm.main() == 0
    assert ran, "fail-open: the runner went on to its work"
    cap = capsys.readouterr()
    logged = [ln for ln in (cap.out + cap.err).splitlines() if "hibernate.py" in ln]
    assert len(logged) == (0 if mode == "rc1" else 1), cap
