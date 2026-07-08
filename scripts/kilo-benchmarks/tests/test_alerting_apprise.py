"""Behavior Contract for scripts/kilo-benchmarks/alerting/apprise.py.

Phase A of the 2026-07-08 pipeline-health-coverage-closure plan.

Root cause fixed: apprise container is on the `fabrik` docker network with no
host-port binding and no host-side DNS. SSH-then-host-curl couldn't resolve or
reach it, so 100% of alerts hit HTTP 000. Fix adopts the canonical Fabrik
pattern already used at `provision_grafana.sh:30`, `sysadmin/daily-digest.sh:285`,
`sysadmin/system-prompt.txt:37`: `sudo docker run --rm --network fabrik
curlimages/curl:latest -X POST …`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ALERTING = Path(__file__).resolve().parent.parent / "alerting"
if str(_ALERTING) not in sys.path:
    sys.path.insert(0, str(_ALERTING))


def test_send_uses_docker_run_fabrik_pattern(monkeypatch):
    """B1: happy path — argv contains the Fabrik docker-run pattern AND the
    function returns True on subprocess returncode=0.
    """
    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    import apprise

    assert apprise.send("t", "b") is True
    argv = captured["argv"]
    assert argv[0] == "ssh", f"expected SSH prefix, got argv[0]={argv[0]!r}"
    remote = " ".join(argv)
    assert "docker" in remote and "run" in remote, "docker-run pattern missing"
    assert "--rm" in remote, "--rm missing"
    assert "--network" in remote and "fabrik" in remote, "--network fabrik missing"
    assert "curlimages/curl:latest" in remote, "curlimages/curl image missing"
    assert "POST" in remote
    assert "/notify" in remote, "notify URL missing"


def test_send_returns_false_on_nonzero_exit(monkeypatch):
    """B2: fail-soft — SSH non-zero exit → False, no raise."""

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, returncode=1, stdout=b"", stderr=b"boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    import apprise

    assert apprise.send("t", "b") is False


def test_send_returns_false_on_timeout(monkeypatch):
    """B3: fail-soft — TimeoutExpired → False, no raise."""

    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=12)

    monkeypatch.setattr(subprocess, "run", fake_run)
    import apprise

    assert apprise.send("t", "b") is False
