"""Coverage sweep for fabrik.drivers.modal_provider — hermetic (no network, no SDK, no CLI)."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from fabrik.drivers import modal_provider as mp
from fabrik.drivers.modal_provider import ModalClient, ModalError


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("MODAL_TOKEN_ID", raising=False)
    monkeypatch.delenv("MODAL_TOKEN_SECRET", raising=False)
    monkeypatch.setattr(mp, "SYSADMIN_ENV", tmp_path / "absent.env")


@pytest.fixture
def fake_modal(monkeypatch):
    m = MagicMock(name="modal")
    monkeypatch.setitem(sys.modules, "modal", m)
    return m


@pytest.fixture
def client(fake_modal):
    return ModalClient(token_id="id", token_secret="sec")


def _run_result(rc=0, out="", err=""):
    return subprocess.CompletedProcess([], rc, stdout=out, stderr=err)


# --- constants / errors ------------------------------------------------------
def test_gpu_type_map_values():
    assert mp.MODAL_GPU_TYPES["pod-h100"] == "H100"
    assert mp.MODAL_GPU_TYPES["pod-h100-pcie"] == "H100"
    assert mp.MODAL_GPU_TYPES["pod-rtx-4090"] == "L4"


def test_modal_error_carries_cause():
    cause = ValueError("x")
    e = ModalError("boom", cause=cause)
    assert str(e) == "boom" and e.cause is cause
    assert isinstance(e, RuntimeError)
    assert ModalError("y").cause is None


# --- __init__ ----------------------------------------------------------------
def test_init_missing_tokens_raises(fake_modal):
    with pytest.raises(ModalError, match="MODAL_TOKEN_ID"):
        ModalClient()


def test_init_missing_secret_only_raises(fake_modal):
    with pytest.raises(ModalError):
        ModalClient(token_id="id")


def test_init_reads_env(fake_modal, monkeypatch):
    monkeypatch.setenv("MODAL_TOKEN_ID", "eid")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "esec")
    c = ModalClient(timeout=5.0)
    assert (c.token_id, c.token_secret, c.timeout) == ("eid", "esec", 5.0)
    assert c._modal is fake_modal
    assert c._active_app_ctx is None and c._active_fc_id is None


def test_init_loads_sysadmin_env_file(fake_modal, monkeypatch, tmp_path):
    f = tmp_path / "sys.env"
    f.write_text("MODAL_TOKEN_ID=fid\nMODAL_TOKEN_SECRET=fsec\n")
    monkeypatch.setattr(mp, "SYSADMIN_ENV", f)
    seen = []
    monkeypatch.setattr(
        mp,
        "load_dotenv",
        lambda p: seen.append(p)
        or monkeypatch.setenv("MODAL_TOKEN_ID", "fid")
        or monkeypatch.setenv("MODAL_TOKEN_SECRET", "fsec"),
    )
    c = ModalClient()
    assert seen == [f]
    assert c.token_id == "fid"


def test_init_skips_dotenv_when_token_passed(fake_modal, monkeypatch, tmp_path):
    f = tmp_path / "sys.env"
    f.write_text("x=1")
    monkeypatch.setattr(mp, "SYSADMIN_ENV", f)
    monkeypatch.setattr(mp, "load_dotenv", lambda p: pytest.fail("should not load"))
    ModalClient(token_id="a", token_secret="b")


def test_init_without_sdk_raises(monkeypatch):
    monkeypatch.setitem(sys.modules, "modal", None)  # import raises ImportError
    with pytest.raises(ModalError, match="not installed") as ei:
        ModalClient(token_id="a", token_secret="b")
    assert isinstance(ei.value.cause, ImportError)


# --- lifecycle ---------------------------------------------------------------
def test_context_manager_returns_self(client):
    with client as c:
        assert c is client


def test_list_pods_empty(client):
    assert client.list_pods() == []


def test_billing_stubs(client):
    assert client.billing_pods()["pods"] == []
    assert client.billing_endpoints("a", "b")["endpoints"] == []
    assert "_note" in client.billing_pods()


def test_pause_resume_not_supported(client):
    with pytest.raises(NotImplementedError, match="pause"):
        client.pause_pod("x")
    with pytest.raises(NotImplementedError):
        client.resume_pod("x")
    with pytest.raises(NotImplementedError, match="async"):
        client.run_endpoint_async("x", {})


def test_wait_for_running_returns_running(client):
    r = client.wait_for_running("fc-1", timeout=1, interval=1)
    assert r == {"id": "fc-1", "desiredStatus": "RUNNING", "_provider": "modal"}


# --- get_pod -----------------------------------------------------------------
def test_get_pod_completed(client, fake_modal):
    fake_modal.FunctionCall.from_id.return_value.get.return_value = "ok"
    r = client.get_pod("fc-1")
    fake_modal.FunctionCall.from_id.assert_called_once_with("fc-1")
    fake_modal.FunctionCall.from_id.return_value.get.assert_called_once_with(timeout=0)
    assert r["desiredStatus"] == "EXITED" and r["_provider"] == "modal" and r["id"] == "fc-1"
    assert r["costPerHr"] is None and r["adjustedCostPerHr"] is None


@pytest.mark.parametrize(
    "exc,expected",
    [
        (type("FunctionCallCancelled", (Exception,), {})("c"), "EXITED"),
        (type("SomethingCancelledError", (Exception,), {})("c"), "EXITED"),
        (TimeoutError("t"), "RUNNING"),
        (type("PendingError", (Exception,), {})("p"), "RUNNING"),
        (RuntimeError("Call is Still Pending"), "RUNNING"),
        (RuntimeError("weird"), "RUNNING"),
    ],
)
def test_get_pod_exception_mapping(client, fake_modal, exc, expected):
    fake_modal.FunctionCall.from_id.return_value.get.side_effect = exc
    assert client.get_pod("fc")["desiredStatus"] == expected


def test_get_pod_resolve_failure(client, fake_modal):
    boom = KeyError("nope")
    fake_modal.FunctionCall.from_id.side_effect = boom
    with pytest.raises(ModalError, match="could not resolve Modal call fc") as ei:
        client.get_pod("fc")
    assert ei.value.cause is boom


# --- create_pod --------------------------------------------------------------
def _wire_app(fake_modal, fc_id="fc-123"):
    app = fake_modal.App.return_value
    holder = app.function.return_value.return_value
    holder.spawn.return_value = MagicMock(object_id=fc_id)
    ctx = app.run.return_value
    ctx.__enter__.return_value = "running-app"
    return app, holder, ctx


def test_create_pod_success(client, fake_modal):
    app, holder, ctx = _wire_app(fake_modal)
    r = client.create_pod(gpu_type_id="H100", image_name="img", name="myapp")
    fake_modal.App.assert_called_once_with("myapp")
    app.function.assert_called_once()
    assert app.function.call_args.kwargs["gpu"] == "H100"
    assert app.function.call_args.kwargs["timeout"] == 86400
    app.function.return_value.assert_called_once_with(mp._modal_gpu_session_holder)
    assert r == {
        "id": "fc-123",
        "desiredStatus": "RUNNING",
        "publicIp": None,
        "costPerHr": None,
        "_app_name": "myapp",
        "_provider": "modal",
    }
    assert client._active_app_ctx is ctx
    assert client._active_app == "running-app"
    assert client._active_fc_id == "fc-123"


def test_create_pod_generates_unique_app_name(client, fake_modal):
    _wire_app(fake_modal)
    r = client.create_pod(gpu_type_id="L4", image_name="i")
    assert r["_app_name"].startswith("fabrik-gpu-rent-")
    assert len(r["_app_name"]) == len("fabrik-gpu-rent-") + 8


def test_create_pod_twice_refused(client, fake_modal):
    _wire_app(fake_modal)
    client.create_pod(gpu_type_id="L4", image_name="i")
    with pytest.raises(ModalError, match="already has an active app context"):
        client.create_pod(gpu_type_id="L4", image_name="i")


def test_create_pod_spawn_failure_exits_context_and_reraises(client, fake_modal):
    _, holder, ctx = _wire_app(fake_modal)
    holder.spawn.side_effect = RuntimeError("no capacity")
    with pytest.raises(RuntimeError, match="no capacity"):
        client.create_pod(gpu_type_id="L4", image_name="i")
    ctx.__exit__.assert_called_once_with(None, None, None)
    assert client._active_app_ctx is None
    assert client._active_fc_id is None


# --- destroy_pod -------------------------------------------------------------
def test_destroy_pod_cancels_and_exits(client, fake_modal):
    _, holder, ctx = _wire_app(fake_modal)
    client.create_pod(gpu_type_id="L4", image_name="i")
    fc = client._active_fc
    client.destroy_pod("fc-123")
    fc.cancel.assert_called_once()
    ctx.__exit__.assert_called_once_with(None, None, None)
    assert (
        client._active_app_ctx,
        client._active_app,
        client._active_fc,
        client._active_fc_id,
    ) == (None,) * 4


def test_destroy_pod_without_active_uses_from_id(client, fake_modal):
    client.destroy_pod("fc-x")
    fake_modal.FunctionCall.from_id.assert_called_once_with("fc-x")
    fake_modal.FunctionCall.from_id.return_value.cancel.assert_called_once()


def test_destroy_pod_cancel_failure_non_fatal(client, fake_modal, caplog):
    fake_modal.FunctionCall.from_id.return_value.cancel.side_effect = RuntimeError("gone")
    with caplog.at_level(logging.WARNING, logger=mp.logger.name):
        client.destroy_pod("fc-x")
    assert "failed (non-fatal)" in caplog.text


def test_destroy_pod_mismatched_id_warns(client, fake_modal, caplog):
    _wire_app(fake_modal)
    client.create_pod(gpu_type_id="L4", image_name="i")
    with caplog.at_level(logging.WARNING, logger=mp.logger.name):
        client.destroy_pod("other")
    assert "active session is fc-123" in caplog.text


def test_destroy_pod_exit_failure_raises_and_resets_state(client, fake_modal):
    _, _, ctx = _wire_app(fake_modal)
    client.create_pod(gpu_type_id="L4", image_name="i")
    boom = RuntimeError("exit fail")
    ctx.__exit__.side_effect = boom
    with pytest.raises(ModalError, match="failed to exit modal app context") as ei:
        client.destroy_pod("fc-123")
    assert ei.value.cause is boom
    assert client._active_app_ctx is None and client._active_fc is None


# --- list_endpoints ----------------------------------------------------------
def test_list_endpoints_filters_stopped_and_passes_env(client, monkeypatch):
    calls = {}

    def fake_run(cmd, **kw):
        calls["cmd"], calls["kw"] = cmd, kw
        return _run_result(
            out='[{"app_id":"ap-1","state":"deployed","description":"fabrik-gpu-a"},'
            '{"app_id":"ap-2","state":"stopped","description":"old"},'
            '{"app_id":"ap-3","state":"ephemeral"}]'
        )

    monkeypatch.setattr(mp.subprocess, "run", fake_run)
    monkeypatch.setattr(mp, "fabrik_endpoint_tag", lambda d: f"tag:{d}")
    eps = client.list_endpoints()
    assert calls["cmd"] == ["modal", "app", "list", "--json"]
    assert calls["kw"]["env"]["MODAL_TOKEN_ID"] == "id"
    assert calls["kw"]["env"]["MODAL_TOKEN_SECRET"] == "sec"
    assert calls["kw"]["timeout"] == 30
    assert [e["id"] for e in eps] == ["ap-1", "ap-3"]
    assert eps[0] == {
        "id": "ap-1",
        "_provider": "modal",
        "_app_name": "fabrik-gpu-a",
        "_state": "deployed",
        "env": "tag:fabrik-gpu-a",
    }
    assert eps[1]["_app_name"] == ""


def test_list_endpoints_cli_failure(client, monkeypatch):
    monkeypatch.setattr(mp.subprocess, "run", lambda *a, **k: _run_result(2, "", " bad auth \n"))
    with pytest.raises(ModalError, match="modal app list failed: bad auth"):
        client.list_endpoints()


def test_list_endpoints_non_json(client, monkeypatch):
    monkeypatch.setattr(mp.subprocess, "run", lambda *a, **k: _run_result(0, "not json"))
    with pytest.raises(ModalError, match="non-JSON"):
        client.list_endpoints()


# --- get_endpoint ------------------------------------------------------------
def test_get_endpoint_cached(client, monkeypatch):
    client._endpoint_cache = {"n": {"id": "n", "_endpoint_url": "u"}}
    monkeypatch.setattr(client, "list_endpoints", lambda: pytest.fail("no listing"))
    assert client.get_endpoint("n")["_endpoint_url"] == "u"


def test_get_endpoint_by_id_or_name_and_fallback(client, monkeypatch):
    monkeypatch.setattr(
        client,
        "list_endpoints",
        lambda: [{"id": "ap-1", "_app_name": "alpha"}, {"id": "ap-2", "_app_name": "beta"}],
    )
    assert client.get_endpoint("ap-1")["_app_name"] == "alpha"
    assert client.get_endpoint("beta")["id"] == "ap-2"
    assert client.get_endpoint("zzz") == {"id": "zzz", "_provider": "modal"}


# --- destroy_endpoint --------------------------------------------------------
def test_destroy_endpoint_success_cleans_cache_and_tmpfile(client, monkeypatch, tmp_path):
    rendered = tmp_path / "r.py"
    rendered.write_text("x")
    client._endpoint_cache = {"app": {"_rendered_path": str(rendered)}}
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return _run_result(0)

    monkeypatch.setattr(mp.subprocess, "run", fake_run)
    client.destroy_endpoint("app")
    assert seen["cmd"] == ["modal", "app", "stop", "--yes", "app"]
    assert "app" not in client._endpoint_cache
    assert not rendered.exists()


def test_destroy_endpoint_no_cache_attr_ok(client, monkeypatch):
    monkeypatch.setattr(mp.subprocess, "run", lambda *a, **k: _run_result(0))
    client.destroy_endpoint("never-cached")


@pytest.mark.parametrize("msg", ["App is Already Stopped.", "App not found", "No such app: x"])
def test_destroy_endpoint_idempotent_messages(client, monkeypatch, msg):
    monkeypatch.setattr(mp.subprocess, "run", lambda *a, **k: _run_result(1, "", msg))
    client.destroy_endpoint("app")


def test_destroy_endpoint_idempotent_message_on_stdout(client, monkeypatch):
    monkeypatch.setattr(mp.subprocess, "run", lambda *a, **k: _run_result(1, "app not found", ""))
    client.destroy_endpoint("app")


def test_destroy_endpoint_real_failure(client, monkeypatch):
    monkeypatch.setattr(
        mp.subprocess, "run", lambda *a, **k: _run_result(1, "", "permission denied")
    )
    with pytest.raises(ModalError, match="modal app stop app failed: permission denied"):
        client.destroy_endpoint("app")


# --- run_endpoint_sync -------------------------------------------------------
def test_run_endpoint_sync_posts_json(client, monkeypatch):
    client._endpoint_cache = {"n": {"id": "n", "_endpoint_url": "https://x.modal.run"}}
    resp = MagicMock()
    resp.json.return_value = {"out": 1}
    post = MagicMock(return_value=resp)
    import httpx

    monkeypatch.setattr(httpx, "post", post)
    assert client.run_endpoint_sync("n", {"a": 1}, timeout=7.0) == {"out": 1}
    post.assert_called_once_with("https://x.modal.run", json={"a": 1}, timeout=7.0)
    resp.raise_for_status.assert_called_once()


def test_run_endpoint_sync_http_error_propagates(client, monkeypatch):
    client._endpoint_cache = {"n": {"id": "n", "_endpoint_url": "https://x"}}
    resp = MagicMock()
    resp.raise_for_status.side_effect = RuntimeError("500")
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: resp)
    with pytest.raises(RuntimeError, match="500"):
        client.run_endpoint_sync("n", {})


def test_run_endpoint_sync_without_url(client):
    client._endpoint_cache = {"n": {"id": "n", "_endpoint_url": None}}
    # cached entry is truthy, so get_endpoint returns it and the URL is missing
    with pytest.raises(ModalError, match="no _endpoint_url"):
        client.run_endpoint_sync("n", {})


# --- _render_modal_template --------------------------------------------------
class _RedirectPath(type(Path())):
    """Path that redirects the hard-coded /opt/fabrik/templates/modal into a tmp dir."""

    # Not ``root``: that name shadows ``PurePath.root`` and corrupts str().
    redirect_to: Path = Path()

    # Python >= 3.12 takes the segments in __init__; a __new__ rewrite is ignored.
    def __init__(self, *parts):
        if parts and str(parts[0]) == "/opt/fabrik/templates/modal":
            parts = (str(type(self).redirect_to),) + parts[1:]
        super().__init__(*parts)


@pytest.fixture
def tpl_dir(monkeypatch, tmp_path):
    d = tmp_path / "tpls"
    d.mkdir()
    monkeypatch.setattr(_RedirectPath, "redirect_to", d)
    monkeypatch.setattr(mp, "Path", _RedirectPath)
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(mp.tempfile, "gettempdir", lambda: str(out))
    return d


def test_render_template_writes_rendered_file(client, tpl_dir, tmp_path):
    (tpl_dir / "echo.py.j2").write_text(
        "N={{ name }} G={{ gpu }} M={{ model }} lo={{ workers_min }} hi={{ workers_max }} t={{ idle_timeout }}"
    )
    p = client._render_modal_template(
        "echo", name="svc", gpu="L4", model="m", workers_min=0, workers_max=2, idle_timeout=30
    )
    assert p == str(tmp_path / "out" / "fabrik-modal-svc.py")
    assert Path(p).read_text() == "N=svc G=L4 M=m lo=0 hi=2 t=30"


def test_render_template_missing_lists_available(client, tpl_dir):
    (tpl_dir / "alpha.py.j2").write_text("x")
    with pytest.raises(ModalError, match=r"not found.*Available: \['alpha'\]"):
        client._render_modal_template(
            "nope", name="n", gpu="L4", model="", workers_min=0, workers_max=1, idle_timeout=1
        )


def test_render_template_requires_jinja2(client, monkeypatch):
    monkeypatch.setitem(sys.modules, "jinja2", None)
    with pytest.raises(ModalError, match="jinja2 is required"):
        client._render_modal_template(
            "x", name="n", gpu="L4", model="", workers_min=0, workers_max=1, idle_timeout=1
        )


# --- create_endpoint ---------------------------------------------------------
def _write_app_module(tmp_path, body):
    p = tmp_path / "rendered.py"
    p.write_text(body)
    return str(p)


def _patch_render(client, monkeypatch, path, captured=None):
    def fake(template_id, **kw):
        if captured is not None:
            captured.update(kw, template_id=template_id)
        return path

    monkeypatch.setattr(client, "_render_modal_template", fake)


APP_OK = """
class _Fn:
    def __init__(self, url): self.url = url
    def get_web_url(self): return self.url
class _App:
    registered_web_endpoints = ["h"]
    registered_functions = {"bad": _Fn(None), "h": _Fn("https://h.modal.run")}
    deployed = None
    def deploy(self, name): _App.deployed = name
app = _App()
"""


def test_create_endpoint_resolves_url_and_caches(client, monkeypatch, tmp_path):
    path = _write_app_module(tmp_path, APP_OK)
    cap = {}
    _patch_render(client, monkeypatch, path, cap)
    r = client.create_endpoint(
        template_id="echo", name="svc", gpu_type_ids=["A100", "L4"], workers_max=5, model="mm"
    )
    assert cap["gpu"] == "A100" and cap["model"] == "mm" and cap["template_id"] == "echo"
    assert r["_endpoint_url"] == "https://h.modal.run"
    assert r["id"] == "svc" and r["_app_name"] == "svc" and r["_provider"] == "modal"
    assert r["workersMin"] == 0 and r["workersMax"] == 5 and r["idleTimeout"] == 60
    assert r["flashboot"] is True and r["_rendered_path"] == path
    assert client._endpoint_cache["svc"] is r
    assert Path(path).exists()


def test_create_endpoint_defaults_gpu_and_model(client, monkeypatch, tmp_path):
    path = _write_app_module(tmp_path, APP_OK)
    cap = {}
    _patch_render(client, monkeypatch, path, cap)
    client.create_endpoint(template_id="t", name="svc")
    assert cap["gpu"] == "L4" and cap["model"] == ""


def test_create_endpoint_deploy_failure_cleans_tmpfile(client, monkeypatch, tmp_path):
    path = _write_app_module(
        tmp_path, "class A:\n    def deploy(self, name): raise RuntimeError('quota')\napp = A()\n"
    )
    _patch_render(client, monkeypatch, path)
    with pytest.raises(ModalError, match=r"app.deploy\(svc\) failed: quota") as ei:
        client.create_endpoint(template_id="t", name="svc")
    assert isinstance(ei.value.cause, RuntimeError)
    assert not Path(path).exists()


def test_create_endpoint_missing_app_variable(client, monkeypatch, tmp_path):
    path = _write_app_module(tmp_path, "x = 1\n")
    _patch_render(client, monkeypatch, path)
    with pytest.raises(ModalError, match="no `app` module-level variable"):
        client.create_endpoint(template_id="t", name="svc")
    assert not Path(path).exists()


def test_create_endpoint_template_exec_error_cleans_tmpfile(client, monkeypatch, tmp_path):
    path = _write_app_module(tmp_path, "raise ValueError('bad template')\n")
    _patch_render(client, monkeypatch, path)
    with pytest.raises(ValueError, match="bad template"):
        client.create_endpoint(template_id="t", name="svc")
    assert not Path(path).exists()


def test_create_endpoint_unloadable_spec(client, monkeypatch, tmp_path):
    path = _write_app_module(tmp_path, "app = 1\n")
    _patch_render(client, monkeypatch, path)
    monkeypatch.setattr(mp.importlib.util, "spec_from_file_location", lambda *a, **k: None)
    with pytest.raises(ModalError, match="could not load rendered template"):
        client.create_endpoint(template_id="t", name="svc")
    assert not Path(path).exists()


APP_CLS = """
class _App:
    registered_web_endpoints = ["Other.x", "K.nomethod", "K.gen"]
    registered_functions = {}
    registered_classes = ["Broken", "K"]
    def deploy(self, name): pass
app = _App()
"""


def test_create_endpoint_class_based_url(client, fake_modal, monkeypatch, tmp_path):
    path = _write_app_module(tmp_path, APP_CLS)
    _patch_render(client, monkeypatch, path)
    method = SimpleNamespace(get_web_url=lambda: "https://cls.modal.run")
    inst = SimpleNamespace(gen=method)

    def from_name(app_name, cls_name):
        if cls_name == "Broken":
            raise RuntimeError("no such cls")
        assert app_name == "svc"
        return lambda: inst

    fake_modal.Cls.from_name.side_effect = from_name
    r = client.create_endpoint(template_id="t", name="svc")
    assert r["_endpoint_url"] == "https://cls.modal.run"


def test_create_endpoint_fallback_function_names(client, fake_modal, monkeypatch, tmp_path):
    path = _write_app_module(
        tmp_path,
        "class _App:\n    registered_functions = {}\n    def deploy(self, name): pass\napp=_App()\n",
    )
    _patch_render(client, monkeypatch, path)
    tried = []

    def from_name(app, fn):
        tried.append(fn)
        if fn != "FabrikVLLM.generate":
            raise RuntimeError("nope")
        return SimpleNamespace(get_web_url=lambda: "https://fb.modal.run")

    fake_modal.Function.from_name.side_effect = from_name
    r = client.create_endpoint(template_id="t", name="svc")
    assert tried == ["_fabrik_handler", "FabrikVLLM.generate"]
    assert r["_endpoint_url"] == "https://fb.modal.run"


def test_create_endpoint_unresolvable_url_warns(client, fake_modal, monkeypatch, tmp_path, caplog):
    path = _write_app_module(
        tmp_path, "class _App:\n    def deploy(self, name): pass\napp=_App()\n"
    )
    _patch_render(client, monkeypatch, path)
    fake_modal.Function.from_name.side_effect = RuntimeError("nope")
    with caplog.at_level(logging.WARNING, logger=mp.logger.name):
        r = client.create_endpoint(template_id="t", name="svc")
    assert r["_endpoint_url"] is None
    assert "could not resolve web URL for svc" in caplog.text
    assert client._endpoint_cache["svc"]["_endpoint_url"] is None


def test_create_endpoint_registry_lookup_failure_is_nonfatal(
    client, fake_modal, monkeypatch, tmp_path
):
    body = (
        "class _App:\n"
        "    @property\n"
        "    def registered_functions(self): raise RuntimeError('registry down')\n"
        "    def deploy(self, name): pass\n"
        "app=_App()\n"
    )
    path = _write_app_module(tmp_path, body)
    _patch_render(client, monkeypatch, path)
    fake_modal.Function.from_name.return_value = SimpleNamespace(get_web_url=lambda: "https://z")
    assert client.create_endpoint(template_id="t", name="svc")["_endpoint_url"] == "https://z"


# --- module-level holder -----------------------------------------------------
def test_holder_sleeps_24h_then_returns(monkeypatch):
    import time

    slept = []
    monkeypatch.setattr(time, "sleep", slept.append)
    assert mp._modal_gpu_session_holder() == {"status": "sleep_timeout"}
    assert slept == [86400]
