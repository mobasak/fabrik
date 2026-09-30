"""W-1f904e4b — the emitted node-api server answers the routes its own contracts declare.

`shape.exposes_metrics: true` (templates/node-api/defaults.yaml) makes `fabrik apply` register a
Prometheus target at /metrics, and the compose healthcheck plus the spec's `health_path` probe
/api/health. The emitted `src/index.js` is RUN here under Node and each path is requested, so a
route that falls through to the welcome response fails the test. `prom-client` and `pino` are
shimmed in the temp project's node_modules (the registry is not reachable from the test box; the
emitted Dockerfile installs the real packages).
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from fabrik.scaffold import create_project

FABRIK_ROOT = Path("/opt/fabrik")
pytestmark = [
    pytest.mark.skipif(
        not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
        reason="Requires full fabrik environment at /opt/fabrik (not available in CI)",
    ),
    pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed"),
]

_PROM_SHIM = """\
const registry = {
  contentType: 'text/plain; version=0.0.4; charset=utf-8',
  async metrics() {
    if (process.env.SHIM_METRICS_FAIL) throw new Error('registry failed');
    return '# HELP shim_up shim\\n# TYPE shim_up gauge\\nshim_up 1\\n';
  },
};
module.exports = { register: registry, collectDefaultMetrics() {} };
"""
_PINO_SHIM = """\
function pino() { const noop = () => {}; return { info: noop, warn: noop, error: noop, debug: noop }; }
pino.stdTimeFunctions = { isoTime: () => '' };
module.exports = pino;
"""


def _shim(project: Path, name: str, body: str) -> None:
    d = project / "node_modules" / name
    d.mkdir(parents=True)
    (d / "package.json").write_text(
        json.dumps({"name": name, "version": "0.0.0", "main": "index.js"})
    )
    (d / "index.js").write_text(body)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(port: int, path: str) -> tuple[int, str, str]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read().decode()


def _raw(port: int, target: str) -> bytes:
    """Send one raw request line (urllib normalises targets like `//a:b` away)."""
    with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
        s.sendall(f"GET {target} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n".encode())
        chunks = []
        while chunk := s.recv(65536):
            chunks.append(chunk)
    return b"".join(chunks)


@pytest.fixture()
def running_node_api(tmp_path, request):
    extra_env = getattr(request, "param", {})
    create_project(name="route-probe", project_type="node-api", description="t", base=tmp_path)
    project = tmp_path / "route-probe"
    _shim(project, "prom-client", _PROM_SHIM)
    _shim(project, "pino", _PINO_SHIM)
    port = _free_port()
    proc = subprocess.Popen(
        ["node", "src/index.js"],
        cwd=project,
        env={**os.environ, "PORT": str(port), "SENTRY_DSN": "", "GLITCHTIP_DSN": "", **extra_env},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                if proc.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(
                        f"node-api did not start: {proc.stderr.read().decode()[-500:]}"
                    )
                time.sleep(0.1)
        yield project, port, proc
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_metrics_route_serves_the_prometheus_registry(running_node_api):
    project, port, _proc = running_node_api
    status, ctype, body = _get(port, "/metrics")
    assert status == 200
    assert ctype.startswith("text/plain"), ctype
    assert "shim_up 1" in body, body[:200]
    deps = json.loads((project / "package.json").read_text())["dependencies"]
    assert deps.get("prom-client", "").startswith("^15"), deps


@pytest.mark.parametrize("path", ["/health", "/api/health", "/api/health?probe=gatus"])
def test_every_declared_health_path_reaches_the_health_handler(running_node_api, path):
    """The compose healthcheck and the spec's health_path probe /api/health; the pack's route is /health."""
    _project, port, _proc = running_node_api
    status, _ctype, body = _get(port, path)
    assert status == 200
    assert json.loads(body) == {"service": "route-probe", "status": "ok"}


def test_other_paths_still_get_the_welcome_response(running_node_api):
    _project, port, _proc = running_node_api
    status, _ctype, body = _get(port, "/anything")
    assert status == 200 and json.loads(body) == {"message": "Welcome to route-probe"}


@pytest.mark.parametrize("target", ["//a:b", "//metrics", "//api/health", "http://[", "/%zz"])
def test_malformed_or_double_slash_targets_neither_crash_nor_misroute(running_node_api, target):
    """A target `new URL` cannot parse used to throw in the listener and kill the process."""
    _project, port, proc = running_node_api
    reply = _raw(port, target)
    assert b"shim_up" not in reply, "a //-prefixed target reached /metrics"
    assert b'"status":"ok"' not in reply, "a //-prefixed target reached the health handler"
    assert proc.poll() is None, "the server process died"
    status, _ctype, _body = _get(port, "/health")
    assert status == 200


@pytest.mark.parametrize(
    ("target", "marker"),
    [
        ("http://x/metrics", b"shim_up"),
        ("HTTPS://x/api/health?probe=1", b'"status":"ok"'),
        ("http://x:3000/health", b'"status":"ok"'),
    ],
)
def test_absolute_form_targets_route_on_their_path(running_node_api, target, marker):
    """RFC 9112 section 3.2.2: a server MUST accept an absolute-form request target."""
    _project, port, _proc = running_node_api
    assert marker in _raw(port, target)


@pytest.mark.parametrize("running_node_api", [{"SHIM_METRICS_FAIL": "1"}], indirect=True)
def test_a_failing_registry_answers_500_and_the_server_stays_up(running_node_api):
    _project, port, proc = running_node_api
    status, _ctype, body = _get(port, "/metrics")
    assert (status, body) == (500, "metrics unavailable")
    assert proc.poll() is None
