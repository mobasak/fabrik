"""Behavior Contract — W-36687f76: the nightly chat backup (session-archive.service) must never fail silently.

`session_archive_alert.py` runs over its production transport: a subprocess, with fake `systemctl`,
`journalctl` and `mail.py` EXECUTABLES (the ARCHIVE_ALERT_* seams) so nothing reaches the live user
manager or a real mailbox. The `systemctl show` rows are systemd 255's verbatim grammar (measured on
this box, design measure 2c); the archiver's summary lines come from running the REAL archiver.
"""

from __future__ import annotations

import contextlib
import fcntl
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "session_archive_alert.py"
UNITS = REPO / "scripts" / "sysadmin" / "systemd"
INSTALLER = REPO / "scripts" / "sysadmin" / "install_session_archive_timer.sh"
INV = "5fa6bde35f504b5c8d598b7dedbb6394"
PY = "/opt/fabrik/.venv/bin/python"


def _row(key: str, argv: str, ign: str, code: str = "exited", status: str = "0") -> str:
    path = argv.split(" ", 1)[0]
    return (
        f"{key}={{ path={path} ; argv[]={argv} ; ignore_errors={ign} ; "
        "start_time=[Sat 2026-10-24 00:05:02 +03] ; stop_time=[Sat 2026-10-24 00:09:23 +03] ; "
        f"pid=3666530 ; code={code} ; status={status} }}"
    )


SAMPLER = "/opt/fabrik/scripts/sysadmin/sample_transcript_growth.sh"
ARCHIVER = f"{PY} /opt/fabrik/scripts/sysadmin/archive_transcripts.py"
PRUNER = f"{PY} /opt/fabrik/scripts/sysadmin/prune_transcripts.py --apply --nightly"
ROTATION = f"{PY} /opt/fabrik/scripts/sysadmin/rotate_session.py due --mb-only --mail"


def _show(pruner_code: str = "exited", pruner_status: str = "0", **over: tuple[str, str]) -> str:
    rows = {
        "pre": ("exited", "0"),
        "archiver": ("exited", "0"),
        "pruner": (pruner_code, pruner_status),
        "rotation": ("exited", "0"),
        **over,
    }
    return "\n".join(
        [
            _row("ExecStartPre", SAMPLER, "yes", *rows["pre"]),
            _row("ExecStart", ARCHIVER, "no", *rows["archiver"]),
            _row("ExecStart", PRUNER, "yes", *rows["pruner"]),
            _row("ExecStart", ROTATION, "yes", *rows["rotation"]),
        ]
    ) + "\n"


SUMMARY_OK = (
    "archive_transcripts: 3879 MAIN transcript(s) eligible (idle > 0.0d)\n"
    "archive_transcripts: 2205 subagent transcript(s) eligible (idle > 0.0d)\n"
    "archive_transcripts: 86 new manifest row(s), 547 subagent row(s), 0 subagent failure(s); "
    "archive at /home/x/.claude/archive\n"
)


@pytest.fixture
def world(tmp_path):
    """Fake executables + a clean env; `world.run(verb)` runs the script as systemd would."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    state = tmp_path / "state"
    state.mkdir()

    def exe(name: str, body: str) -> Path:
        p = bin_ / name
        p.write_text(body)
        p.chmod(0o755)
        return p

    # systemctl: prints state/show; exits with state/show.rc (default 0); counts its calls
    exe(
        "systemctl",
        "#!/bin/sh\n"
        f'echo x >> "{state}/show.calls"\n'
        f'[ -f "{state}/show" ] && cat "{state}/show"\n'
        f'rc=$(cat "{state}/show.rc" 2>/dev/null || echo 0)\n'
        'echo "systemctl said no" >&2\n'
        "exit $rc\n",
    )
    # journalctl: refuses any query but this invocation's, then prints state/journal raw (bytes)
    exe(
        "journalctl",
        "#!/bin/sh\n"
        f'echo "$*" >> "{state}/journal.args"\n'
        f'[ -f "{state}/journal" ] && cat "{state}/journal"\n'
        f'exit $(cat "{state}/journal.rc" 2>/dev/null || echo 0)\n',
    )
    mail = exe(
        "mail.py",
        "import json, sys\n"
        "a = sys.argv[1:]\n"
        "body = open(a[a.index('--body-file') + 1], encoding='utf-8').read()\n"
        f"open({str(state / 'mails.jsonl')!r}, 'a').write(json.dumps({{'argv': a, 'body': body}}) + '\\n')\n"
        f"rc = open({str(state / 'mail.rc')!r}).read().strip() if __import__('os').path.exists({str(state / 'mail.rc')!r}) else '0'\n"
        "if rc != '0':\n"
        "    print('mail store is read-only', file=sys.stderr)\n"
        "sys.exit(int(rc))\n",
    )

    class World:
        def __init__(self):
            self.state = state
            self.env = {
                "PATH": f"{bin_}:/usr/bin:/bin",
                "HOME": str(tmp_path),
                "ARCHIVE_ALERT_SYSTEMCTL": str(bin_ / "systemctl"),
                "ARCHIVE_ALERT_JOURNALCTL": str(bin_ / "journalctl"),
                "ARCHIVE_ALERT_MAIL": str(mail),
                "ARCHIVE_ALERT_POLL_S": "1",
                "ARCHIVE_ALERT_RETRY_S": "0",
            }

        def set(self, name: str, data: str | bytes) -> None:
            p = state / name
            p.write_bytes(data if isinstance(data, bytes) else data.encode())

        def run(self, verb: str, **env: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                [sys.executable, str(SCRIPT), verb],
                env={**self.env, **env},
                capture_output=True,
                text=True,
                timeout=120,
            )

        def mails(self) -> list[dict]:
            p = state / "mails.jsonl"
            return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    return World()


def _arg(argv: list[str], flag: str) -> str:
    return argv[argv.index(flag) + 1]


def _addressed(mails: list[dict]) -> dict[str, str]:
    """to-agent -> ack, for every mail sent."""
    for m in mails:
        assert _arg(m["argv"], "--to") == "fabrik" and _arg(m["argv"], "--from") == "fabrik"
        assert _arg(m["argv"], "--kind") == "finding"
    return {_arg(m["argv"], "--to-agent"): _arg(m["argv"], "--ack") for m in mails}


CHECK_ENV = {"SERVICE_RESULT": "success", "INVOCATION_ID": INV}


# ── 1. the final failure ─────────────────────────────────────────────────────────────────────


def test_failed_mails_infra_and_the_coordinator_with_the_result_and_journal_tail(world):
    world.set("journal", "".join(f"line {i}\n" for i in range(40)) + "archive_transcripts: TRANSPORT FAILED (rclone copy failed (rc 1))\n")
    r = world.run(
        "failed",
        MONITOR_SERVICE_RESULT="exit-code",
        MONITOR_EXIT_CODE="exited",
        MONITOR_EXIT_STATUS="1",
        MONITOR_INVOCATION_ID=INV,
    )
    assert r.returncode == 0, r.stderr
    mails = world.mails()
    assert _addressed(mails) == {"infra": "required", "coordinator": "no"}
    body = mails[0]["body"]
    assert "exit-code" in body and "status 1" in body
    assert "TRANSPORT FAILED" in body, "the failing line reaches the reader"
    assert "line 21" in body and "line 20" not in body, "the tail is the last 20 lines"
    assert f"_SYSTEMD_INVOCATION_ID={INV}" in (world.state / "journal.args").read_text()
    for field in ("WHAT:", "WHERE:", "WHEN:", "WHO:", "WHY:", "HOW:", "SYSTEMIC:"):
        assert field in body, field


def test_failed_still_mails_when_systemd_passes_no_monitor_env(world):
    r = world.run("failed")
    assert r.returncode == 0, r.stderr
    mails = world.mails()
    assert len(mails) == 2 and "unknown" in mails[0]["body"]
    assert not (world.state / "journal.args").exists(), "no invocation id, no journal query"


# ── 2. every step that did not exit 0 ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "show, named",
    [
        (_show("exited", "3"), "prune_transcripts.py"),  # the pruner's refusal exit
        (_show(rotation=("exited", "1")), "rotate_session.py due"),  # the rotation mail failed
        (_show(pre=("exited", "2")), "sample_transcript_growth.sh"),
        (_show("killed", "15/TERM"), "prune_transcripts.py"),
        (_show("(null)", "0/0"), "prune_transcripts.py"),  # on success every step ran: a lost status
    ],
    ids=["pruner-refused", "rotation-mail-failed", "sampler-failed", "pruner-killed", "status-lost"],
)
def test_check_reports_every_step_that_did_not_exit_zero(world, show, named):
    world.set("show", show)
    world.set("journal", SUMMARY_OK)
    r = world.run("check", **CHECK_ENV)
    assert r.returncode == 0, r.stderr
    mails = world.mails()
    assert _addressed(mails) == {"infra": "required", "coordinator": "no"}
    body = mails[0]["body"]
    assert named in body
    assert body.count("- ") >= 1 and "PARTIAL" in body


def test_an_argv_holding_the_separator_or_a_fake_tail_parses_to_its_real_tail(world):
    """Greedy argv, tail-anchored grammar (both design critiques executed it)."""
    sneaky = f"{PY} /x.py a ; b ; ignore_errors=yes ; pid=9 ; code=exited ; status=0 }}"
    world.set("show", _show() + _row("ExecStart", sneaky, "yes", "exited", "4") + "\n")
    world.set("journal", SUMMARY_OK)
    world.run("check", **CHECK_ENV)
    bodies = [m["body"] for m in world.mails()]
    assert bodies and "status=4" in bodies[0]


# ── 3. the archiver's own summary, from the REAL archiver ────────────────────────────────────


def _archiver_stdout(tmp_path: Path, monkeypatch, case: str) -> str:
    spec = importlib.util.spec_from_file_location(
        "archive_transcripts_for_alert", REPO / "scripts" / "sysadmin" / "archive_transcripts.py"
    )
    at = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(at)
    projects, archive = tmp_path / "projects", tmp_path / "archive"
    (projects / "-opt-alpha").mkdir(parents=True)
    if case != "zero-eligible":
        (projects / "-opt-alpha" / "sid.jsonl").write_bytes(b'{"a":1}\n' * 50)
        subs = projects / "-opt-alpha" / "sid" / "subagents"
        subs.mkdir(parents=True)
        (subs / "agent-x.jsonl").write_bytes(b"S" * 5000)
    for k in [k for k in os.environ if k.startswith(("RCLONE_", "SESSION_ARCHIVE_"))]:
        monkeypatch.delenv(k)
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", str(projects))
    monkeypatch.setenv("ARCHIVE_ROOT", str(archive))
    monkeypatch.setenv("ARCHIVE_AFTER_DAYS", "0")
    monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(tmp_path / "no-such.env"))
    monkeypatch.setenv("SESSION_ARCHIVE_B2_KEY_ID", "kid-test")
    monkeypatch.setenv("SESSION_ARCHIVE_B2_APPLICATION_KEY", "SECRET-test-value")
    monkeypatch.setattr(at, "_run_rclone", lambda argv, env: subprocess.CompletedProcess(argv, 0, "", ""))
    if case == "subagent-failure":
        real = shutil.copyfile

        def denied(src, dst):
            if "/subagents/" in str(src):
                raise PermissionError(13, "Permission denied")
            return real(src, dst)

        monkeypatch.setattr(at.shutil, "copyfile", denied)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        if case == "lock-held":
            archive.mkdir(parents=True)
            with (archive / at.LOCK_NAME).open("a") as fh:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                assert at.run([]) == 0
        else:
            assert at.run([]) == 0
    return out.getvalue()


@pytest.mark.skipif(shutil.which("zstd") is None, reason="zstd not installed")
@pytest.mark.parametrize(
    "case, says",
    [
        ("subagent-failure", "1 subagent transcript(s) failed"),
        ("zero-eligible", "0 MAIN transcript(s) eligible"),
        ("lock-held", "lock"),
    ],
)
def test_check_reads_the_archivers_real_summary(world, tmp_path, monkeypatch, case, says):
    stdout = _archiver_stdout(tmp_path / "arch", monkeypatch, case)
    world.set("show", _show())
    # journald hands the unit's stdout back as-is; a stray non-UTF-8 byte must not cost the night its check
    world.set("journal", b"\xff\xfe garbage before\n" + stdout.encode())
    r = world.run("check", **CHECK_ENV)
    assert r.returncode == 0, r.stderr
    mails = world.mails()
    assert len(mails) == 2, (case, stdout)
    assert says in mails[0]["body"], mails[0]["body"]


@pytest.mark.skipif(shutil.which("zstd") is None, reason="zstd not installed")
def test_a_real_clean_archiver_night_is_silent(world, tmp_path, monkeypatch):
    stdout = _archiver_stdout(tmp_path / "arch", monkeypatch, "clean")
    assert "0 subagent failure(s)" in stdout
    world.set("show", _show())
    world.set("journal", stdout)
    r = world.run("check", **CHECK_ENV)
    assert r.returncode == 0, r.stderr
    assert world.mails() == []


def test_check_reports_a_journal_with_no_archiver_summary(world):
    world.set("show", _show())
    world.set("journal", "archive_transcripts: 3879 MAIN transcript(s) eligible (idle > 0.0d)\n")
    r = world.run("check", **CHECK_ENV)
    assert r.returncode == 0, r.stderr
    assert "summary line was not found" in world.mails()[0]["body"]
    polls = (world.state / "journal.args").read_text().splitlines()
    assert len(polls) >= 2, "a late journal is polled again before it is called missing"


# ── 4. silence where silence is right ────────────────────────────────────────────────────────


def test_check_is_silent_on_a_clean_night_and_on_a_failed_attempt(world):
    world.set("show", _show())
    world.set("journal", SUMMARY_OK)
    assert world.run("check", **CHECK_ENV).returncode == 0
    assert world.mails() == [], "a clean night mails nobody"
    world.set("show", _show("exited", "3"))
    for result in ("exit-code", "timeout", "signal", "start-limit-hit"):
        r = world.run("check", SERVICE_RESULT=result, INVOCATION_ID=INV)
        assert r.returncode == 0 and world.mails() == [], result
    r = world.run("check", INVOCATION_ID=INV)
    assert r.returncode == 2 and "SERVICE_RESULT" in r.stderr, "a hand run is not a quiet night"
    assert world.mails() == []


# ── 5. what check cannot read, and its own crash ─────────────────────────────────────────────


def test_check_reports_what_it_cannot_read_and_its_own_crash(world):
    world.set("journal", SUMMARY_OK)
    world.set("show.rc", "1")
    r = world.run("check", **CHECK_ENV)
    assert r.returncode == 0, r.stderr
    assert len((world.state / "show.calls").read_text().splitlines()) == 2, "one retry before unreadable"
    assert "unreadable" in world.mails()[0]["body"] and "systemctl said no" in world.mails()[0]["body"]

    (world.state / "mails.jsonl").unlink()
    world.set("show.rc", "0")
    world.set("show", _show() + "ExecStart=something systemd never printed\n")
    world.run("check", **CHECK_ENV)
    assert "unreadable" in world.mails()[0]["body"]

    (world.state / "mails.jsonl").unlink()
    world.set("show", "ExecStartPre=\nExecStart=\n")  # empty lists: nothing ran, nothing to flag
    world.run("check", **CHECK_ENV)
    assert world.mails() == []


def test_a_crash_inside_check_still_sends_one_mail(world, monkeypatch):
    spec = importlib.util.spec_from_file_location("session_archive_alert_crash", SCRIPT)
    sa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sa)
    for k, v in {**world.env, **CHECK_ENV}.items():
        monkeypatch.setenv(k, v)

    def boom(_show_text):
        raise RuntimeError("parser exploded")

    monkeypatch.setattr(sa, "step_findings", boom)
    world.set("show", _show())
    assert sa.main(["check"]) == 1
    mails = world.mails()
    assert _addressed(mails) == {"infra": "required", "coordinator": "no"}
    assert "crashed" in mails[0]["body"] and "parser exploded" in mails[0]["body"]


# ── 6. the units wire it ─────────────────────────────────────────────────────────────────────


def _sections(name: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    sec = ""
    for ln in (UNITS / name).read_text().splitlines():
        s = ln.strip()
        if not s or s.startswith(("#", ";")):
            continue
        if s.startswith("[") and s.endswith("]"):
            sec = s
            continue
        out.setdefault(sec, []).append(s)
    return out


def _seconds(v: str) -> float:
    units = {"s": 1, "min": 60, "h": 3600}
    for u in ("min", "h", "s"):
        if v.endswith(u):
            return float(v[: -len(u)]) * units[u]
    return float(v)


def test_the_units_wire_the_alert_and_verify():
    svc = _sections("session-archive.service")
    assert "OnFailure=session-archive-alert.service" in svc["[Unit]"], "OnFailure= is a [Unit] key"
    service = svc["[Service]"]
    assert "RestartMode=direct" in service, "without it OnFailure= fires on every retried attempt"
    assert "Restart=on-failure" in service
    assert f"ExecStopPost=-{PY} /opt/fabrik/scripts/sysadmin/session_archive_alert.py check" in service
    start = [v for v in service if v.startswith("TimeoutStartSec=")]
    stop = [v for v in service if v.startswith("TimeoutStopSec=")]
    assert len(start) == 1 and len(stop) == 1
    assert _seconds(start[0].split("=", 1)[1]) >= 3600, "a hung archiver must still end"

    spec = importlib.util.spec_from_file_location("session_archive_alert_budget", SCRIPT)
    sa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sa)
    assert sa.CHECK_BUDGET_S < _seconds(stop[0].split("=", 1)[1]), (
        "a check slower than TimeoutStopSec turns a good night into `timeout` and re-runs the archiver"
    )

    alert = _sections("session-archive-alert.service")
    assert not any(v.startswith("OnFailure=") for vs in alert.values() for v in vs), "no alert loop"
    assert "Type=oneshot" in alert["[Service]"]
    assert f"ExecStart={PY} /opt/fabrik/scripts/sysadmin/session_archive_alert.py failed" in alert["[Service]"]

    analyze = shutil.which("systemd-analyze")
    if analyze is None:
        pytest.skip("systemd-analyze not installed")
    r = subprocess.run(
        [analyze, "--user", "verify", str(UNITS / "session-archive.service"), str(UNITS / "session-archive-alert.service")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0 and (r.stdout + r.stderr).strip() == "", (
        "a misplaced key is only a warning at rc 0: " + r.stdout + r.stderr
    )


def _installer_world(tmp_path: Path, verify_says: str = "") -> tuple[Path, dict[str, str]]:
    root = tmp_path / "inst"
    (root / "systemd").mkdir(parents=True)
    shutil.copy2(INSTALLER, root / INSTALLER.name)
    for f in UNITS.glob("session-archive*"):
        shutil.copy2(f, root / "systemd" / f.name)
    bin_ = tmp_path / "ibin"
    bin_.mkdir()
    log = tmp_path / "calls.log"
    for name, body in {
        "loginctl": "echo Linger=yes",
        "systemctl": f'echo "systemctl $*" >> "{log}"',
        "systemd-analyze": f'echo "verify $*" >> "{log}"; printf "%s" "{verify_says}"',
    }.items():
        p = bin_ / name
        p.write_text(f"#!/bin/sh\n{body}\n")
        p.chmod(0o755)
    env = {"PATH": f"{bin_}:/usr/bin:/bin", "HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "cfg")}
    return root, env


def test_the_installer_installs_and_verifies_the_alert_unit(tmp_path):
    root, env = _installer_world(tmp_path)
    r = subprocess.run(["bash", str(root / INSTALLER.name)], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    dest = tmp_path / "cfg" / "systemd" / "user"
    assert (dest / "session-archive-alert.service").read_bytes() == (UNITS / "session-archive-alert.service").read_bytes()
    assert (dest / "session-archive.service").is_file()
    assert "session-archive-alert.service" in (tmp_path / "calls.log").read_text(), "the alert unit is verified"


def test_the_installer_refuses_a_verify_warning_and_a_missing_alert_unit(tmp_path):
    root, env = _installer_world(tmp_path, verify_says="x.service:7: Unknown key name 'OnFailure' in section 'Service', ignoring.")
    r = subprocess.run(["bash", str(root / INSTALLER.name)], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "Unknown key" in r.stderr
    assert not (tmp_path / "cfg" / "systemd" / "user" / "session-archive.service").exists()

    root2, env2 = _installer_world(tmp_path / "b")
    (root2 / "systemd" / "session-archive-alert.service").unlink()
    r = subprocess.run(["bash", str(root2 / INSTALLER.name)], env=env2, capture_output=True, text=True, timeout=60)
    assert r.returncode != 0
    assert not (tmp_path / "b" / "cfg" / "systemd" / "user" / "session-archive.service").exists()


# ── 7. a send that fails ─────────────────────────────────────────────────────────────────────


def test_a_failed_send_exits_nonzero_and_says_why(world):
    world.set("mail.rc", "1")
    world.set("show", _show("exited", "3"))
    world.set("journal", SUMMARY_OK)
    r = world.run("check", **CHECK_ENV)
    assert r.returncode == 1
    assert "mail to infra failed" in r.stderr and "read-only" in r.stderr
    assert "mail to coordinator failed" in r.stderr, "one failed send never skips the other"
    r = world.run("failed", MONITOR_SERVICE_RESULT="exit-code")
    assert r.returncode == 1 and "mail to infra failed" in r.stderr
