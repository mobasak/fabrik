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
    else:
        r = vultr_drill._ssh_ozgur_drill("192.0.2.1", "claude -p ok; echo RC=$?")
        result = [r.returncode, next(int(t[3:]) for t in r.stdout.split() if t.startswith("RC="))]
except Exception as exc:
    result = ["RAISED", type(exc).__name__]
print(json.dumps(result))
"""


def _run(tmp_path: Path, which: str, stdout: bytes, stderr: bytes = b"", rc: int = 0, lc: str = "C.UTF-8"):
    (tmp_path / "out").write_bytes(stdout)
    (tmp_path / "err").write_bytes(stderr)
    fake = tmp_path / "ssh"
    fake.write_text(f'#!/bin/sh\ncat "{tmp_path}/out"\ncat "{tmp_path}/err" >&2\nexit {rc}\n')
    fake.chmod(0o755)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("LC_", "LANG", "PYTHONUTF8", "FABRIK_SSH_JUMP", "FABRIK_AUDIT_VPS"))
    }
    env.update(LC_ALL=lc, PATH=f"{tmp_path}{os.pathsep}{env.get('PATH', '')}")
    run = subprocess.run(
        [sys.executable, "-c", _CHILD, _SRC, which],
        env=env,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr.decode("utf-8", "replace")[-800:]
    return json.loads(run.stdout)


def test_audit_refuses_an_undecodable_answer(tmp_path) -> None:
    assert _run(tmp_path, "audit", b"web-1\ncaf\xff\n") == [False, "the answer is not valid UTF-8"]


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
