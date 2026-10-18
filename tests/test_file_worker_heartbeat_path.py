"""The file-worker template runs outside a container (W-2a2c5a08).

`templates/file-worker/worker/main.py` created `/app/.tmp` at import, so `python -m worker.main`
(`make dev`) on any host that is not the container died with `PermissionError: '/app'` before
the first line of the worker ran. The heartbeat now lives in the project's own `.tmp/` next to the
`worker/` package — `/app/.tmp/worker_heartbeat` inside the image (WORKDIR /app, COPY . .), the
path every file-worker healthcheck reads (the `templates/file-worker/*.j2` ones `template_renderer.py`
renders and a `fabrik scaffold` project's, all `scaffold.FILE_WORKER_HEARTBEAT_CHECK` —
tests/test_file_worker_heartbeat_healthcheck.py) — and the directory is made when the first beat is
written, never at import.

A scaffolded project's real `worker/main.py` is imported in a subprocess (dummy credentials, no
network: the Supabase and S3 clients are only constructed at import).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fabrik import scaffold
from fabrik.scaffold import create_project

# The scaffold copies worker/main.py from FILE_WORKER_TEMPLATE_DIR, under FABRIK_ROOT ($FABRIK_ROOT,
# else the hub worktree holding the cwd, else /opt/fabrik); pin that one directory to this test file's
# checkout, so the main.py the probe imports is always the one beside this test (the scaffold's other
# files still come from FABRIK_ROOT).
_TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "file-worker"

_PROBE = """
import json, worker.main as m
before = m.HEARTBEAT_FILE.parent.exists()
m._beat()
print(json.dumps({"path": str(m.HEARTBEAT_FILE), "dir_before_beat": before,
                  "beat": m.HEARTBEAT_FILE.exists()}))
"""

_ENV = {
    "PATH": "/usr/bin:/bin",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.c2lnbmF0dXJl",
    "R2_ENDPOINT": "https://example.invalid",
    "R2_ACCESS_KEY_ID": "test",
    "R2_SECRET_ACCESS_KEY": "test",
    "R2_BUCKET": "test",
    "AWS_EC2_METADATA_DISABLED": "true",
}


def test_the_worker_imports_outside_a_container_and_beats_into_its_own_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _TEMPLATE)
    create_project(
        name="fw-heartbeat", project_type="file-worker", description="heartbeat path", base=tmp_path
    )
    project = tmp_path / "fw-heartbeat"
    # the scaffold seeds a .tmp/; remove it to prove the import makes none
    shutil.rmtree(project / ".tmp", ignore_errors=True)
    # a cwd that is not the project: the heartbeat path follows the package, never the cwd
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    r = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=elsewhere,
        env={**_ENV, "HOME": str(tmp_path), "TMPDIR": str(tmp_path), "PYTHONPATH": str(project)},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert Path(out["path"]) == (project / ".tmp" / "worker_heartbeat").resolve()
    assert out["dir_before_beat"] is False  # importing creates nothing
    assert out["beat"] is True  # the first beat makes the directory


def test_the_j2_healthchecks_read_the_path_the_worker_writes_in_the_image():
    """The .j2 Dockerfile and compose (template_renderer's) read /app/.tmp/worker_heartbeat, and
    WORKDIR /app + `COPY . .` makes /app the project root — where the test above proves the worker
    beats (`<project>/.tmp/worker_heartbeat`)."""
    dockerfile = (_TEMPLATE / "Dockerfile.j2").read_text()
    compose = (_TEMPLATE / "compose.yaml.j2").read_text()
    assert "WORKDIR /app" in dockerfile and "COPY . ." in dockerfile
    assert "/app/.tmp/worker_heartbeat" in dockerfile
    assert "/app/.tmp/worker_heartbeat" in compose


# W-807b73fd: `make docker-smoke` runs the image with the project's `.env`, so a smoke run against real credentials
# claimed production jobs and `docker stop` killed them mid-run. WORKER_SMOKE=1 (set only by the recipe) beats, never claims.
_LOOP_PROBE = """
import json, sys, types, worker.main as m
calls = []
class _Rpc:
    def execute(self):
        calls.append(1)
        return types.SimpleNamespace(data=None)
m.supabase = types.SimpleNamespace(rpc=lambda name, args: _Rpc())
polls = {"n": 0}
def _sleep(_s):
    polls["n"] += 1
    if polls["n"] >= 2:
        m.shutdown_requested = True
m.time.sleep = _sleep
m.main()
print(json.dumps({"claims": len(calls), "beat": m.HEARTBEAT_FILE.exists()}))
"""


@pytest.mark.parametrize(
    "smoke, claims",
    [(None, 2), ("0", 2), ("true", 2), ("", 2), ("yes", 2), (" 1", 2), ("1\n", 2), ("1", 0)],
    ids=["unset", "0", "true", "empty", "yes", "space-1", "1-newline", "1"],
)
def test_a_smoke_run_beats_but_never_claims(smoke, claims, tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _TEMPLATE)
    create_project(
        name="fw-smoke-claim", project_type="file-worker", description="smoke", base=tmp_path
    )
    project = tmp_path / "fw-smoke-claim"
    env = {
        **_ENV,
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp_path),
        "PYTHONPATH": str(project),
        "POLL_INTERVAL": "0",
    }
    if smoke is not None:
        env["WORKER_SMOKE"] = smoke
    r = subprocess.run(
        [sys.executable, "-c", _LOOP_PROBE],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out == {"claims": claims, "beat": True}, out  # two polls: a normal worker claims on each
    # exactly "1" is smoke, and only smoke says so in the log (the triage signal for a worker that claims nothing)
    assert ("worker_smoke_mode" in r.stdout + r.stderr) is (smoke == "1"), (
        r.stdout[-2000:] + r.stderr[-2000:]
    )
