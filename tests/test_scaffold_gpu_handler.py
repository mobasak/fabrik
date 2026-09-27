"""python-api-gpu's gpu_handler.py runs inside the deployed container (mail 01M348TJ).

The handler used to import fabrik.orchestrator.gpu_rent, which the container does not have and
which is hub-local by construction. It is now a client for a pinned RunPod serverless endpoint.
Each test emits the scaffold into tmp_path and imports the emitted module the way the service
would; HTTP goes through an httpx.MockTransport, never the network.
"""

from __future__ import annotations

import ast
import importlib.util
import json

import httpx
import pytest

import fabrik.scaffold as scaffold


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    base = tmp_path_factory.mktemp("gpu")
    scaffold.create_project(
        name="gpu-probe",
        description="d",
        base=base,
        project_type="python-api-gpu",
        generate_spec=False,
    )
    return base / "gpu-probe"


@pytest.fixture
def handler(project, monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "test-key")
    monkeypatch.setenv("RUNPOD_SERVERLESS_ENDPOINT_ID", "ep123")
    path = project / "src" / "gpu_probe" / "gpu_handler.py"
    spec = importlib.util.spec_from_file_location("emitted_gpu_handler", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_handler_never_imports_fabrik(project):
    tree = ast.parse((project / "src" / "gpu_probe" / "gpu_handler.py").read_text())
    imported = {
        (n.module or "") if isinstance(n, ast.ImportFrom) else a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.Import | ast.ImportFrom)
        for a in (n.names if isinstance(n, ast.Import) else [None])
    }
    assert not {m for m in imported if m.split(".")[0] == "fabrik"}, imported


def test_the_env_example_names_both_variables(project):
    env = (project / ".env.example").read_text()
    assert "RUNPOD_API_KEY=" in env
    assert "RUNPOD_SERVERLESS_ENDPOINT_ID=" in env


def _client(responses):
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=responses.pop(0))

    return httpx.Client(transport=httpx.MockTransport(handle)), seen


def test_a_completed_job_returns_its_output(handler):
    client, seen = _client([{"id": "j1", "status": "COMPLETED", "output": {"ok": 1}}])

    assert handler.run_on_gpu({"prompt": "hi"}, client=client) == {"ok": 1}
    [req] = seen
    assert str(req.url) == "https://api.runpod.ai/v2/ep123/run"
    assert req.headers["authorization"] == "Bearer test-key"
    assert json.loads(req.content) == {"input": {"prompt": "hi"}}


def test_an_unfinished_job_is_polled_until_done(handler):
    client, seen = _client(
        [
            {"id": "j2", "status": "IN_QUEUE"},
            {"id": "j2", "status": "IN_PROGRESS"},
            {"id": "j2", "status": "COMPLETED", "output": "done"},
        ]
    )

    assert handler.run_on_gpu({}, client=client, poll_interval_s=0) == "done"
    assert [str(r.url) for r in seen[1:]] == ["https://api.runpod.ai/v2/ep123/status/j2"] * 2


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "TIMED_OUT"])
def test_a_failed_job_raises(handler, status):
    client, _ = _client([{"id": "j3", "status": status, "error": "boom"}])

    # The failure branch carries RunPod's own error text; the unknown-status branch does not.
    with pytest.raises(handler.GpuJobError, match=f"{status}: boom"):
        handler.run_on_gpu({}, client=client)


def test_a_job_still_running_at_the_deadline_raises(handler):
    client, _ = _client(
        [{"id": "j4", "status": "IN_PROGRESS"}] + [{"id": "j4", "status": "RUNNING"}] * 5
    )

    with pytest.raises(handler.GpuJobError, match="deadline"):
        handler.run_on_gpu({}, client=client, timeout_s=0, poll_interval_s=0)


def test_missing_configuration_is_named(handler, monkeypatch):
    monkeypatch.delenv("RUNPOD_SERVERLESS_ENDPOINT_ID")

    with pytest.raises(handler.GpuJobError, match="RUNPOD_SERVERLESS_ENDPOINT_ID"):
        handler.run_on_gpu({})


def _raw_client(handle):
    return httpx.Client(transport=httpx.MockTransport(handle))


def test_an_unknown_status_raises(handler):
    client, seen = _client([{"id": "j5", "status": "PAUSED"}, {}])

    with pytest.raises(handler.GpuJobError, match="unknown status"):
        handler.run_on_gpu({}, client=client)
    # a job the handler stops tracking is cancelled so it cannot bill on
    assert str(seen[-1].url) == "https://api.runpod.ai/v2/ep123/cancel/j5"


def test_the_poll_is_an_authenticated_get(handler):
    client, seen = _client(
        [{"id": "j6", "status": "IN_QUEUE"}, {"id": "j6", "status": "COMPLETED", "output": 1}]
    )

    handler.run_on_gpu({}, client=client, poll_interval_s=0)
    poll = seen[1]
    assert poll.method == "GET"
    assert poll.headers["authorization"] == "Bearer test-key"


@pytest.mark.parametrize(
    "reply",
    [
        httpx.Response(500, text="upstream error"),
        # a 500 whose body looks like a finished job: only the status check can refuse it
        httpx.Response(500, json={"id": "j", "status": "COMPLETED", "output": 1}),
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json=["not", "an", "object"]),
        httpx.Response(200, json={"status": "IN_QUEUE"}),
    ],
    ids=["http-500", "http-500-json", "not-json", "not-an-object", "pending-without-id"],
)
def test_a_malformed_reply_raises_the_handlers_own_error(handler, reply):
    client = _raw_client(lambda _req: reply)

    with pytest.raises(handler.GpuJobError):
        handler.run_on_gpu({}, client=client, poll_interval_s=0)


def test_a_closed_client_raises_the_handlers_own_error(handler):
    client, _ = _client([{"id": "j7", "status": "COMPLETED", "output": 1}])
    client.close()

    with pytest.raises(handler.GpuJobError):
        handler.run_on_gpu({}, client=client)


def test_a_completed_job_carrying_an_error_raises(handler):
    client, _ = _client([{"id": "j8", "status": "COMPLETED", "output": None, "error": "OOM"}])

    with pytest.raises(handler.GpuJobError, match="OOM"):
        handler.run_on_gpu({}, client=client)


def test_a_job_polled_past_the_deadline_is_cancelled(handler, monkeypatch):
    clock = iter(range(0, 1000, 5))
    monkeypatch.setattr(handler.time, "monotonic", lambda: float(next(clock)))
    monkeypatch.setattr(handler.time, "sleep", lambda _s: None)
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(200, json={"id": "j9", "status": "RUNNING"})

    with pytest.raises(handler.GpuJobError, match="deadline"):
        handler.run_on_gpu({}, client=_raw_client(handle), timeout_s=12, poll_interval_s=0)
    polls = [r for r in seen if "/status/" in str(r.url)]
    assert polls, "the job must be polled at least once before the deadline"
    assert seen[-1].method == "POST"
    assert str(seen[-1].url) == "https://api.runpod.ai/v2/ep123/cancel/j9"
    assert seen[-1].headers["authorization"] == "Bearer test-key"


def test_a_poll_that_fails_after_the_id_is_known_cancels_the_job(handler):
    seen = []

    def handle(request):
        seen.append(request)
        if "/status/" in str(request.url):
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json={"id": "j10", "status": "IN_QUEUE"})

    with pytest.raises(handler.GpuJobError, match="ReadTimeout"):
        handler.run_on_gpu({}, client=_raw_client(handle), poll_interval_s=0)
    assert seen[-1].method == "POST"
    assert str(seen[-1].url) == "https://api.runpod.ai/v2/ep123/cancel/j10"


def test_a_finished_job_is_never_cancelled(handler):
    client, seen = _client(
        [{"id": "j11", "status": "IN_QUEUE"}, {"id": "j11", "status": "FAILED", "error": "boom"}]
    )

    with pytest.raises(handler.GpuJobError):
        handler.run_on_gpu({}, client=client, poll_interval_s=0)
    assert [r.url.path for r in seen] == ["/v2/ep123/run", "/v2/ep123/status/j11"]


def test_every_request_and_wait_is_bounded_by_the_deadline(handler, monkeypatch):
    slept = []
    monkeypatch.setattr(handler.time, "sleep", slept.append)
    client, seen = _client(
        [{"id": "j12", "status": "IN_QUEUE"}, {"id": "j12", "status": "COMPLETED", "output": 1}]
    )

    handler.run_on_gpu({}, client=client, timeout_s=5, poll_interval_s=100)
    assert slept and max(slept) <= 5
    assert all(r.extensions["timeout"]["read"] <= 5 for r in seen)


@pytest.mark.parametrize("job_id", ["../../x", "..", ".", "a/b", "j 1"])
def test_a_job_id_that_could_change_the_request_path_is_refused(handler, job_id):
    client, seen = _client([{"id": job_id, "status": "IN_QUEUE"}])

    with pytest.raises(handler.GpuJobError, match="without a job id"):
        handler.run_on_gpu({}, client=client, poll_interval_s=0)
    assert len(seen) == 1


@pytest.mark.parametrize("endpoint", ["  ", "../x", "ep/1"])
def test_a_malformed_endpoint_id_is_refused(handler, monkeypatch, endpoint):
    monkeypatch.setenv("RUNPOD_SERVERLESS_ENDPOINT_ID", endpoint)

    with pytest.raises(handler.GpuJobError, match="RUNPOD_SERVERLESS_ENDPOINT_ID"):
        handler.run_on_gpu({})


def test_a_client_the_handler_opens_is_closed(handler, monkeypatch):
    opened = []

    class Recording(httpx.Client):
        def __init__(self, **kw):
            kw.pop("timeout", None)
            super().__init__(
                transport=httpx.MockTransport(
                    lambda _r: httpx.Response(
                        200, json={"id": "j", "status": "COMPLETED", "output": 1}
                    )
                ),
                **kw,
            )
            opened.append(self)

    monkeypatch.setattr(handler.httpx, "Client", Recording)
    handler.run_on_gpu({})
    assert opened and opened[0].is_closed


def test_the_variables_reach_the_container_and_the_spec(tmp_path):
    """The deployer writes the app's .env, but compose passes only what `environment:` lists."""
    import yaml

    scaffold.create_project(
        name="gpu-spec", description="d", base=tmp_path, project_type="python-api-gpu"
    )
    compose = (tmp_path / "gpu-spec" / "compose.yaml").read_text()
    assert "RUNPOD_API_KEY=${RUNPOD_API_KEY" in compose
    assert "RUNPOD_SERVERLESS_ENDPOINT_ID=${RUNPOD_SERVERLESS_ENDPOINT_ID" in compose
    spec = yaml.safe_load((tmp_path / "specs" / "services" / "gpu-spec.yaml").read_text())
    assert "RUNPOD_SERVERLESS_ENDPOINT_ID" in spec["env"]
    assert "RUNPOD_API_KEY" in spec["secrets"]["from_env"]


def test_a_second_gpu_pass_adds_no_duplicate_lines(tmp_path):
    scaffold.create_project(
        name="gpu-twice",
        description="d",
        base=tmp_path,
        project_type="python-api-gpu",
        generate_spec=False,
    )
    project = tmp_path / "gpu-twice"
    scaffold._scaffold_python_api_gpu(project, "gpu-twice", "d")
    for name in (".env.example", "compose.yaml"):
        assert (project / name).read_text().count("RUNPOD_SERVERLESS_ENDPOINT_ID=") == 1, name
