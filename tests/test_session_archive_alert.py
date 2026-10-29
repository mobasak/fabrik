"""Behavior Contract — W-36687f76: the nightly chat backup (session-archive.service) must never fail silently.

`session_archive_alert.py` runs over its production transport: a subprocess, with fake `systemctl`,
`journalctl` and `mail.py` EXECUTABLES (the ARCHIVE_ALERT_* seams) so nothing reaches the live user
manager or a real mailbox. The `systemctl show` rows are systemd 255's verbatim grammar (measured on
this box, design measure 2c); the archiver's summary lines come from running the REAL archiver.
"""

from __future__ import annotations

import ast
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
    return (
        "\n".join(
            [
                _row("ExecStartPre", SAMPLER, "yes", *rows["pre"]),
                _row("ExecStart", ARCHIVER, "no", *rows["archiver"]),
                _row("ExecStart", PRUNER, "yes", *rows["pruner"]),
                _row("ExecStart", ROTATION, "yes", *rows["rotation"]),
            ]
        )
        + "\n"
    )


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
    # journalctl: a `-u <unit>` query prints state/journal.unit, an invocation query state/journal (raw bytes) —
    # they differ in production: a run that ends at the start limit hands OnFailure= a FRESH invocation id that
    # holds no lines, while the unit's lines sit under the attempts' ids (measured on systemd 255)
    exe(
        "journalctl",
        "#!/bin/sh\n"
        f'echo "$*" >> "{state}/journal.args"\n'
        'case " $* " in\n'
        f'  *" -u "*) [ -f "{state}/journal.unit" ] && cat "{state}/journal.unit" ;;\n'
        f'  *) [ -f "{state}/journal" ] && cat "{state}/journal" ;;\n'
        "esac\n"
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
    world.set(
        "journal.unit",
        "".join(f"line {i}\n" for i in range(40))
        + "archive_transcripts: TRANSPORT FAILED (rclone copy failed (rc 1))\n"
        + "session-archive.service: Start request repeated too quickly.\n",
    )
    r = world.run(
        "failed",
        MONITOR_SERVICE_RESULT="exit-code",
        MONITOR_EXIT_CODE="exited",
        MONITOR_EXIT_STATUS="1",
        MONITOR_INVOCATION_ID="39e4b61f8ccb46e8bb252e01c1aa93ca",  # the refused start's own, lineless id
        MONITOR_UNIT="session-archive.service",
    )
    assert r.returncode == 0, r.stderr
    mails = world.mails()
    assert _addressed(mails) == {"infra": "required", "coordinator": "no"}
    body = mails[0]["body"]
    assert "ended exit-code (code exited, status 1)" in body
    assert "TRANSPORT FAILED" in body, "the failing line reaches the reader"
    assert "line 22" in body and "line 21" not in body, "the tail is the last 20 lines"
    args = (world.state / "journal.args").read_text()
    assert "-u session-archive.service" in args and " -n 20 " in f" {args} "
    assert "did not finish" in body and "If the tail shows the archiver failed" in body, (
        "the tail, not the alert, says whether the archiver itself failed"
    )
    for field in ("WHAT:", "WHERE:", "WHEN:", "WHO:", "WHY:", "HOW:", "SYSTEMIC:"):
        assert field in body, field
    reset, start = (
        "systemctl --user reset-failed session-archive.service",
        "systemctl --user start session-archive.service",
    )
    assert reset in body and start in body, "the recovery names both commands"
    assert body.index(reset) < body.index(start), (
        "after the retries the start limit refuses a bare `start` until reset-failed clears its counter"
    )


def test_failed_still_mails_when_systemd_passes_no_monitor_env(world):
    r = world.run("failed")
    assert r.returncode == 0, r.stderr
    mails = world.mails()
    assert len(mails) == 2 and "unknown" in mails[0]["body"]
    assert "-u session-archive.service" in (world.state / "journal.args").read_text(), (
        "the default unit"
    )
    assert "(no journal lines for session-archive.service)" in mails[0]["body"], (
        "an empty tail is said, not dropped"
    )


def test_failed_says_when_the_journal_cannot_be_read(world):
    world.set("journal.rc", "1")
    r = world.run("failed", MONITOR_SERVICE_RESULT="exit-code")
    assert r.returncode == 0, r.stderr
    assert "journalctl could not read the unit's journal: rc 1" in world.mails()[0]["body"]


def test_failed_never_queries_a_hostile_unit_name(world):
    r = world.run("failed", MONITOR_UNIT="x.service; rm -rf ~", MONITOR_SERVICE_RESULT="exit-code")
    assert r.returncode == 0, r.stderr
    args = (world.state / "journal.args").read_text()
    assert "rm -rf" not in args and "-u session-archive.service" in args
    assert "rm -rf" not in world.mails()[0]["body"]


def test_failed_caps_the_tail_in_characters(world):
    world.set("journal.unit", "".join(f"{i:03d}" + "x" * 497 + "\n" for i in range(20)))
    world.run("failed", MONITOR_SERVICE_RESULT="exit-code")
    body = world.mails()[0]["body"]
    block = body.split("```")[1]
    assert len(block.strip("\n")) <= 4000 and "019" in block


# ── 2. every step that did not exit 0 ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "show, named",
    [
        (_show("exited", "3"), "prune_transcripts.py"),  # the pruner's refusal exit
        (_show(rotation=("exited", "1")), "rotate_session.py due"),  # the rotation mail failed
        (_show(pre=("exited", "2")), "sample_transcript_growth.sh"),
        (_show("killed", "15/TERM"), "prune_transcripts.py"),
        (
            _show("(null)", "0/0"),
            "prune_transcripts.py",
        ),  # on success every step ran: a lost status
    ],
    ids=[
        "pruner-refused",
        "rotation-mail-failed",
        "sampler-failed",
        "pruner-killed",
        "status-lost",
    ],
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
    # a COMPLETE fake tail: only the `$` anchor and the greedy argv keep a lazy match off it
    sneaky = (
        f"{PY} /x.py a ; b ; ignore_errors=yes ; start_time=[x] ; stop_time=[x] ; pid=9 ; "
        "code=exited ; status=0 }"
    )
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
    monkeypatch.setattr(
        at, "_run_rclone", lambda argv, env: subprocess.CompletedProcess(argv, 0, "", "")
    )
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


def test_check_reports_an_unreadable_journal(world):
    world.set("show", _show())
    world.set("journal", SUMMARY_OK)
    world.set("journal.rc", "1")
    world.run("check", **CHECK_ENV)
    assert "journal could not be read" in world.mails()[0]["body"]


@pytest.mark.parametrize("inv", ["", "not-hex"])
def test_check_reports_a_missing_invocation_id_without_polling(world, inv):
    world.set("show", _show())
    world.set("journal", SUMMARY_OK)
    world.run("check", SERVICE_RESULT="success", INVOCATION_ID=inv)
    assert "INVOCATION_ID unset or malformed" in world.mails()[0]["body"]
    assert not (world.state / "journal.args").exists(), "no id, no journal query"


def test_check_reads_the_last_summary_and_reports_zero_eligible_with_a_held_lock(world):
    world.set("show", _show())
    world.set(
        "journal",
        SUMMARY_OK.replace("0 subagent failure(s)", "2 subagent failure(s)") + SUMMARY_OK,
    )
    world.run("check", **CHECK_ENV)
    assert world.mails() == [], "only the last summary line counts"
    world.set(
        "journal",
        "archive_transcripts: 0 MAIN transcript(s) eligible (idle > 0.0d)\n"
        "archive_transcripts: another run holds the archive lock; skipping\n",
    )
    world.run("check", **CHECK_ENV)
    body = world.mails()[0]["body"]
    assert "0 MAIN transcript(s) eligible" in body and "archive lock" in body


def test_check_reads_a_crlf_show_and_flags_a_non_numeric_status(world):
    world.set("journal", SUMMARY_OK)
    world.set("show", _show().replace("\n", "\r\n"))
    world.run("check", **CHECK_ENV)
    assert world.mails() == [], "a CRLF row is the same row"
    world.set("show", _show("exited", "abc"))
    world.run("check", **CHECK_ENV)
    assert "status unreadable (status=abc)" in world.mails()[0]["body"]


@pytest.mark.parametrize("archiver", [("killed", "15/TERM"), ("exited", "abc")])
def test_check_says_stopped_when_the_archiver_row_did_not_exit_zero(world, archiver):
    """A stop mid-run still ends SERVICE_RESULT=success (A-opus-5)."""
    world.set("show", _show(archiver=archiver))
    world.set("journal", SUMMARY_OK)
    world.run("check", **CHECK_ENV)
    body = world.mails()[0]["body"]
    assert "STOPPED" in body.splitlines()[0] and "the archive did not complete" in body


@pytest.mark.parametrize(
    "show", ["ExecStartPre=\nExecStart=\n", _row("ExecStartPre", SAMPLER, "yes") + "\nExecStart=\n"]
)
def test_check_reports_a_run_with_no_step_record(world, show):
    """An ExecStartPre row alone is not a run: no ExecStart row means the archiver's status is unknown."""
    world.set("show", show)
    world.set("journal", SUMMARY_OK)
    world.run("check", **CHECK_ENV)
    assert "no step record" in world.mails()[0]["body"]


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    sa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sa)
    return sa


def test_a_show_that_overruns_its_timeout_is_unreadable(world, monkeypatch, tmp_path):
    slow = tmp_path / "slow-systemctl"
    slow.write_text("#!/bin/sh\nsleep 5\n")
    slow.chmod(0o755)
    for k, v in {**world.env, **CHECK_ENV, "ARCHIVE_ALERT_SYSTEMCTL": str(slow)}.items():
        monkeypatch.setenv(k, v)
    sa = _module("session_archive_alert_slow")
    monkeypatch.setattr(sa, "SHOW_TIMEOUT_S", 0.2)
    world.set("journal", SUMMARY_OK)
    assert sa.main(["check"]) == 0
    assert "step status unreadable: `systemctl show` exited -1" in world.mails()[0]["body"]


def test_a_body_file_that_cannot_be_written_fails_that_send(world, monkeypatch, capsys):
    for k, v in world.env.items():
        monkeypatch.setenv(k, v)
    sa = _module("session_archive_alert_full_tmp")

    def full(*_a, **_k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(sa.tempfile, "NamedTemporaryFile", full)
    assert sa.main(["failed"]) == 1
    err = capsys.readouterr().err
    assert "mail to infra failed" in err and "No space left" in err
    assert "mail to coordinator failed" in err


@pytest.mark.parametrize("bad", ["nan", "inf", "-1", "x"])
def test_env_float_refuses_non_finite_and_negative_values(monkeypatch, bad):
    sa = _module("session_archive_alert_env")
    monkeypatch.setenv("ARCHIVE_ALERT_POLL_S", bad)
    assert sa._env_float("ARCHIVE_ALERT_POLL_S", 10.0) == 10.0


def test_main_refuses_an_unknown_verb(world):
    r = world.run("bogus")
    assert r.returncode == 2 and "usage:" in r.stderr
    assert world.mails() == []


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
    r = world.run("check", SERVICE_RESULT="", INVOCATION_ID=INV)
    assert r.returncode == 2, "an empty SERVICE_RESULT is no result either"
    assert world.mails() == []


# ── 5. what check cannot read, and its own crash ─────────────────────────────────────────────


def test_check_reports_what_it_cannot_read_and_its_own_crash(world):
    world.set("journal", SUMMARY_OK)
    world.set("show.rc", "1")
    r = world.run("check", **CHECK_ENV)
    assert r.returncode == 0, r.stderr
    assert len((world.state / "show.calls").read_text().splitlines()) == 2, (
        "one retry before unreadable"
    )
    assert (
        "unreadable" in world.mails()[0]["body"] and "systemctl said no" in world.mails()[0]["body"]
    )

    (world.state / "mails.jsonl").unlink()
    world.set("show.rc", "0")
    world.set("show", _show() + "ExecStart=something systemd never printed\n")
    world.run("check", **CHECK_ENV)
    assert "unreadable" in world.mails()[0]["body"]


def test_a_crash_inside_check_still_mails_both_recipients(world, monkeypatch):
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
    assert (
        f"ExecStopPost=-{PY} /opt/fabrik/scripts/sysadmin/session_archive_alert.py check" in service
    )
    start = [v for v in service if v.startswith("TimeoutStartSec=")]
    stop = [v for v in service if v.startswith("TimeoutStopSec=")]
    assert len(start) == 1 and len(stop) == 1
    start_s = _seconds(start[0].split("=", 1)[1])
    assert start_s >= 3600, "a hung archiver must still end"

    # the retries must be able to reach the start limit, or a slow failure retries forever and OnFailure= never
    # fires: StartLimitBurst attempts fit inside the interval, each up to TimeoutStartSec PER START COMMAND (systemd
    # re-arms the timer for every ExecStartPre=/ExecStart= of a oneshot — measured on systemd 255), then the five stop
    # stages a timed-out attempt can wait TimeoutStopSec in (stop-sigterm, stop-sigkill, stop-post, final-sigterm,
    # final-sigkill), then RestartSec
    stop_s = _seconds(stop[0].split("=", 1)[1])
    commands = [v for v in service if v.startswith(("ExecStartPre=", "ExecStart="))]
    assert len(commands) == 4, commands
    (interval,) = [v for v in svc["[Unit]"] if v.startswith("StartLimitIntervalSec=")]
    (burst,) = [v for v in svc["[Unit]"] if v.startswith("StartLimitBurst=")]
    (restart,) = [v for v in service if v.startswith("RestartSec=")]
    interval_s = _seconds(interval.split("=", 1)[1])
    assert interval_s >= int(burst.split("=", 1)[1]) * (
        len(commands) * start_s + 5 * stop_s + _seconds(restart.split("=", 1)[1])
    )
    # the shortest gap between two nightly starts: a 23 h day (OnCalendar=daily is local time, so a DST spring-forward
    # night), less the timer's random delay and its accuracy window (systemd.timer: AccuracySec= defaults to 1min,
    # RandomizedDelaySec= to 0) — e.g. 00:15:59 one night, 00:00 the next
    timer = _sections("session-archive.timer")["[Timer]"]
    assert [v for v in timer if v.startswith("OnCalendar=")] == ["OnCalendar=daily"], (
        "the 23 h gap assumes one start a day"
    )

    def _timer_s(key: str, default: str) -> float:
        # systemd 255 ignores an empty value here ("Failed to parse sec value, ignoring"), so the last non-empty one holds
        vals = [v.split("=", 1)[1] for v in timer if v.startswith(f"{key}=") and v.split("=", 1)[1]]
        return _seconds(vals[-1] if vals else default)

    shortest_gap = 23 * 3600 - _timer_s("RandomizedDelaySec", "0") - _timer_s("AccuracySec", "1min")
    assert interval_s < shortest_gap, (
        "a window that outlasts the gap to the next nightly start refuses it even when the nightly timer opened it"
    )

    sa = _module("session_archive_alert_budget")
    assert stop_s > sa.CHECK_BUDGET_S, (
        "a check slower than TimeoutStopSec turns a good night into `timeout` and re-runs the archiver"
    )
    # CHECK_BUDGET_S sums named timeouts; it holds only while every subprocess call passes one of them. A new
    # call site, or one with a literal timeout, changes this list and must re-size the budget.
    tree = ast.parse(SCRIPT.read_text())
    timeouts = sorted(
        ast.unparse(c.args[1])
        if len(c.args) > 1
        else ast.unparse(next(k.value for k in c.keywords if k.arg == "timeout"))
        for c in ast.walk(tree)
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "_run"
    )
    # `check` reads its invocation's journal once (`_journal`); `failed`'s unit tail (`_unit_tail`) is the other read
    assert timeouts == [
        "JOURNAL_TIMEOUT_S",
        "JOURNAL_TIMEOUT_S",
        "SEND_TIMEOUT_S",
        "SHOW_TIMEOUT_S",
    ], timeouts
    direct = [
        c
        for c in ast.walk(tree)
        if isinstance(c, ast.Call)
        and isinstance(c.func, ast.Attribute)
        and isinstance(c.func.value, ast.Name)
        and c.func.value.id == "subprocess"
    ]
    assert len(direct) == 1, "every subprocess call goes through _run, which carries the timeout"
    (inner,) = direct
    assert [ast.unparse(k.value) for k in inner.keywords if k.arg == "timeout"] == ["timeout"], (
        "_run hands its own timeout parameter to subprocess"
    )
    # given those call sites, `check`'s worst case, spelled out here independently of the constant: both shows and the
    # pause between, the poll window plus the sleep that can start before its deadline, one journal read, and four
    # sends (the report's two plus a crash mail's two) — dropping a term from CHECK_BUDGET_S fails here
    worst = (
        sa.SHOW_TRIES * sa.SHOW_TIMEOUT_S
        + sa.RETRY_S
        + sa.POLL_S
        + sa.POLL_SLEEP_S
        + sa.JOURNAL_TIMEOUT_S
        + 4 * sa.SEND_TIMEOUT_S
    )
    assert worst <= sa.CHECK_BUDGET_S

    alert = _sections("session-archive-alert.service")
    assert not any(v.startswith("OnFailure=") for vs in alert.values() for v in vs), "no alert loop"
    assert "Type=oneshot" in alert["[Service]"]
    assert (
        f"ExecStart={PY} /opt/fabrik/scripts/sysadmin/session_archive_alert.py failed"
        in alert["[Service]"]
    )

    analyze = shutil.which("systemd-analyze")
    if analyze is None:
        pytest.skip("systemd-analyze not installed")
    r = subprocess.run(
        [
            analyze,
            "--user",
            "verify",
            str(UNITS / "session-archive.service"),
            str(UNITS / "session-archive-alert.service"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0 and (r.stdout + r.stderr).strip() == "", (
        "a misplaced key is only a warning at rc 0: " + r.stdout + r.stderr
    )


def _installer_world(
    tmp_path: Path, verify_says: str = "", verify_rc: int = 0
) -> tuple[Path, dict[str, str]]:
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
        # like the real one: a unit path that does not exist fails verify at rc 1, naming it
        "systemd-analyze": f'echo "verify $*" >> "{log}"\n'
        'for a in "$@"; do case "$a" in /*) [ -e "$a" ] || '
        '{ echo "Failed to prepare filename $a: No such file or directory" >&2; exit 1; } ;; esac; done\n'
        f'printf "%s" "{verify_says}"\nexit {verify_rc}',
    }.items():
        p = bin_ / name
        p.write_text(f"#!/bin/sh\n{body}\n")
        p.chmod(0o755)
    env = {
        "PATH": f"{bin_}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
    }
    return root, env


def test_the_installer_installs_and_verifies_the_alert_unit(tmp_path):
    root, env = _installer_world(tmp_path)
    r = subprocess.run(
        ["bash", str(root / INSTALLER.name)], env=env, capture_output=True, text=True, timeout=60
    )
    assert r.returncode == 0, r.stderr
    dest = tmp_path / "cfg" / "systemd" / "user"
    assert (dest / "session-archive-alert.service").read_bytes() == (
        UNITS / "session-archive-alert.service"
    ).read_bytes()
    assert (dest / "session-archive.service").is_file()
    assert "session-archive-alert.service" in (tmp_path / "calls.log").read_text(), (
        "the alert unit is verified"
    )


def test_the_installer_refuses_a_verify_warning_and_a_missing_alert_unit(tmp_path):
    root, env = _installer_world(
        tmp_path,
        verify_says="x.service:7: Unknown key name 'OnFailure' in section 'Service', ignoring.",
    )
    r = subprocess.run(
        ["bash", str(root / INSTALLER.name)], env=env, capture_output=True, text=True, timeout=60
    )
    assert r.returncode != 0 and "Unknown key" in r.stderr
    assert not (tmp_path / "cfg" / "systemd" / "user" / "session-archive.service").exists()

    root2, env2 = _installer_world(tmp_path / "b")
    (root2 / "systemd" / "session-archive-alert.service").unlink()
    r = subprocess.run(
        ["bash", str(root2 / INSTALLER.name)], env=env2, capture_output=True, text=True, timeout=60
    )
    assert r.returncode != 0
    assert "session-archive-alert.service: No such file" in r.stderr, "a failed verify says why"
    assert not (tmp_path / "b" / "cfg" / "systemd" / "user" / "session-archive.service").exists()

    # a verify that fails SILENTLY is refused on its rc alone
    root3, env3 = _installer_world(tmp_path / "c", verify_rc=1)
    r = subprocess.run(
        ["bash", str(root3 / INSTALLER.name)], env=env3, capture_output=True, text=True, timeout=60
    )
    assert r.returncode != 0 and "verify exited 1" in r.stderr
    assert not (tmp_path / "c" / "cfg" / "systemd" / "user" / "session-archive.service").exists()


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
