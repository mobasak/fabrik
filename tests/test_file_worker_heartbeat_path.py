"""The file-worker template runs outside a container (W-2a2c5a08).

`templates/file-worker/worker/main.py` created `/app/.tmp` at import, so `python -m worker.main`
(`make dev`) on any host that is not the container died with `PermissionError: '/app'` before
the first line of the worker ran. The heartbeat now lives in the project's own `.tmp/` next to the
`worker/` package — `/app/.tmp/worker_heartbeat` inside the image (WORKDIR /app, COPY . .), so the
Docker HEALTHCHECK path is unchanged — and the directory is made when the first beat is written,
never at import.

A scaffolded project's real `worker/main.py` is imported in a subprocess (dummy credentials, no
network: the Supabase and S3 clients are only constructed at import).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from fabrik.scaffold import create_project

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


def test_the_worker_imports_outside_a_container_and_beats_into_its_own_tmp(tmp_path):
    create_project(
        name="fw-heartbeat", project_type="file-worker", description="heartbeat path", base=tmp_path
    )
    project = tmp_path / "fw-heartbeat"
    shutil.rmtree(
        project / ".tmp", ignore_errors=True
    )  # the scaffold seeds one; prove import makes none
    r = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=project,
        env={**_ENV, "HOME": str(tmp_path), "TMPDIR": str(tmp_path)},
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


def test_the_healthcheck_still_reads_the_path_the_worker_writes_in_the_image():
    """WORKDIR /app + `COPY . .` puts worker/ at /app/worker, so the project's .tmp is /app/.tmp."""
    template = Path(__file__).resolve().parent.parent / "templates" / "file-worker"
    dockerfile = (template / "Dockerfile.j2").read_text()
    compose = (template / "compose.yaml.j2").read_text()
    assert "WORKDIR /app" in dockerfile and "COPY . ." in dockerfile
    assert "/app/.tmp/worker_heartbeat" in dockerfile
    assert "/app/.tmp/worker_heartbeat" in compose
