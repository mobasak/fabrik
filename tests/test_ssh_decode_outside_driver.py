"""Package code that runs ssh itself decodes the answer as the driver does (W-7ac62afc, D-1286).

Each test runs the real function in a child Python with a fake `ssh` first on PATH (the pattern of
tests/drivers/test_ssh.py::test_utf8_output_decodes_under_an_ascii_locale), so the real subprocess call reads
real bytes: a byte that is not valid UTF-8 never raises UnicodeDecodeError, and the exit code is always read.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).resolve().parents[1] / "src")

_CHILD = """
import json, sys
sys.path.insert(0, sys.argv[1])
from fabrik import audit
from fabrik.orchestrator import vultr_drill
vultr_drill.time.sleep = lambda _s: None
try:
    if sys.argv[2] == "audit":
        result = list(audit._ssh_check("sudo docker ps"))
    elif sys.argv[2] == "probe":
        result = vultr_drill._ssh_probe("192.0.2.1", attempts=1, interval=0)
    elif sys.argv[2] == "drill":
        r = vultr_drill._ssh_ozgur_drill("192.0.2.1", "claude -p ok; echo RC=$?")
        result = [r.returncode, next(int(t[3:]) for t in r.stdout.split() if t.startswith("RC="))]
    elif sys.argv[2] == "smoke":
        result = vultr_drill._g0_creds_smoke("192.0.2.1")
    else:
        import logging
        from fabrik.drivers import preflight
        seen = []
        handler = logging.Handler()
        handler.emit = lambda record: seen.append(record.getMessage())
        preflight.logger.addHandler(handler)
        preflight._advise_if_direct_back("vps", "FABRIK_SSH_JUMP_VPS")
        result = any("answers again" in m for m in seen)
except Exception as exc:
    result = ["RAISED", type(exc).__name__]
print(json.dumps(result))
"""


def _fake(tmp_path: Path, name: str, stdout: bytes, stderr: bytes, rc: int) -> None:
    (tmp_path / f"{name}.out").write_bytes(stdout)
    (tmp_path / f"{name}.err").write_bytes(stderr)
    fake = tmp_path / name
    fake.write_text(
        f'#!/bin/sh\ncat "{tmp_path}/{name}.out"\ncat "{tmp_path}/{name}.err" >&2\nexit {rc}\n'
    )
    fake.chmod(0o755)


def _run(
    tmp_path: Path,
    which: str,
    stdout: bytes,
    stderr: bytes = b"",
    rc: int = 0,
    lc: str = "C.UTF-8",
    scp: tuple[bytes, int] = (b"", 0),
):
    _fake(tmp_path, "ssh", stdout, stderr, rc)
    _fake(tmp_path, "scp", b"", *scp)
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / ".credentials.json").write_text("{}")
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("LC_", "LANG", "PYTHONUTF8", "FABRIK_SSH_JUMP", "FABRIK_AUDIT_VPS"))
    }
    env.update(LC_ALL=lc, HOME=str(home), PATH=f"{tmp_path}{os.pathsep}{env.get('PATH', '')}")
    utf8_mode = []
    if (
        lc == "C"
    ):  # a real ASCII locale codec: Python's UTF-8 mode would otherwise switch on under C
        env.update(PYTHONCOERCECLOCALE="0", PYTHONUTF8="0")
        utf8_mode = ["-X", "utf8=0"]
    run = subprocess.run(
        [sys.executable, *utf8_mode, "-c", _CHILD, _SRC, which],
        env=env,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr.decode("utf-8", "replace")[-800:]
    return json.loads(run.stdout)


def test_audit_refuses_an_undecodable_answer(tmp_path) -> None:
    assert _run(tmp_path, "audit", b"web-1\ncaf\xff\n") == [
        False,
        "answered (rc 0) but the answer is not valid UTF-8",
    ]


def test_audit_reads_a_valid_answer(tmp_path) -> None:
    assert _run(tmp_path, "audit", "web-1\ncafé\n".encode()) == [True, "web-1\ncafé"]


def test_audit_reads_a_valid_answer_under_an_ascii_locale(tmp_path) -> None:
    assert _run(tmp_path, "audit", "café\n".encode(), lc="C") == [True, "café"]


def test_audit_shows_an_undecodable_failure(tmp_path) -> None:
    assert _run(tmp_path, "audit", b"", b"denied \xff here\n", rc=1) == [False, "denied \\xff here"]


def test_drill_probe_never_raises_on_an_undecodable_answer(tmp_path) -> None:
    assert _run(tmp_path, "probe", b"ok \xff\n") is True


def test_drill_command_reads_rc_past_an_undecodable_byte(tmp_path) -> None:
    assert _run(tmp_path, "drill", b"claude said \xff\nRC=3\n") == [0, 3]


def test_drill_scp_reads_rc_past_an_undecodable_stderr(tmp_path) -> None:
    result = _run(tmp_path, "smoke", b"", scp=(b"lost connection \xff\n", 1))
    assert result == {"attempted": True, "pass": False, "reason": "scp failed (rc=1)"}


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(b"RC=0\xff", id="glued-byte"),
        pytest.param("RC=²".encode(), id="superscript"),  # isdigit() True, int() refuses
        pytest.param("RC=０".encode(), id="fullwidth-zero"),  # int() would read 0: a false pass
    ],
)
def test_drill_rc_token_that_is_not_ascii_digits_reads_as_absent(tmp_path, token) -> None:
    result = _run(tmp_path, "smoke", token + b"\n")
    assert isinstance(result, dict), result
    assert (result["claude_p_rc"], result["pass"]) == (127, False)


def test_audit_reads_the_stdout_error_behind_a_blank_stderr(tmp_path) -> None:
    assert _run(tmp_path, "audit", b"real \xff error\n", b"\n", rc=255) == [
        False,
        "real \\xff error",
    ]


def test_preflight_advice_survives_an_undecodable_answer(tmp_path) -> None:
    assert _run(tmp_path, "advise", b"", b"banner \xff\n") is True
