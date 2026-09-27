"""rent() and rented() share one lifecycle; reconcile, reaper and metrics stay provider-true.

Graders for mail 01M34A4F (ten defects found grading core/76-gpu-workers.md against the code).
The provider client is a MagicMock; state, audit log and usage DB are redirected to tmp_path.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from fabrik.orchestrator import gpu_metrics, gpu_reaper, gpu_rent, gpu_state


class VastLikeError(Exception):
    """A provider error that is NOT a RunPodError (VastError / ModalError shape)."""


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(gpu_state, "STATE_FILE", tmp_path / "gpu-rent-state.json")
    monkeypatch.setattr(gpu_rent, "GPU_RENT_LOG", tmp_path / "gpu-rent-history.jsonl")
    from fabrik.ai import tracker as tracker_mod

    original_init = tracker_mod.UsageTracker.__init__

    def patched_init(self, database_path=None):
        original_init(self, database_path or str(tmp_path / "ai_usage.db"))

    monkeypatch.setattr(tracker_mod.UsageTracker, "__init__", patched_init)
    monkeypatch.delenv("MAX_DAILY_GPU_COST", raising=False)


def _client(pod_id: str = "pod-1") -> MagicMock:
    c = MagicMock()
    c.create_pod.return_value = {"id": pod_id}
    c.wait_for_running.return_value = {"id": pod_id}
    c.list_pods.return_value = []
    c.list_endpoints.return_value = []
    c.create_endpoint.return_value = {"id": "ep-1"}
    return c


def _history(tmp_path) -> list[dict]:
    log = tmp_path / "gpu-rent-history.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def _via_rent(client, **kw):
    return gpu_rent.rent("pod-rtx-4090", workload="t", client=client, **kw)


def _via_rented(client, **kw):
    try:
        with gpu_rent.rented("pod-rtx-4090", workload="t", client=client, **kw):
            pass
    except Exception:  # noqa: BLE001 — rented() re-raises; the finalize side effects are the subject
        pass


ENTRY_POINTS = pytest.mark.parametrize("enter", [_via_rent, _via_rented], ids=["rent", "rented"])


@ENTRY_POINTS
def test_a_wait_failure_destroys_the_recorded_pod(enter):
    client = _client()
    client.wait_for_running.side_effect = TimeoutError("slow host")

    enter(client)

    client.destroy_pod.assert_called_once_with("pod-1")


@ENTRY_POINTS
def test_a_non_runpod_destroy_error_is_logged_and_left_pending(enter, tmp_path):
    client = _client()
    client.destroy_pod.side_effect = VastLikeError("vast said no")

    enter(client)

    [line] = _history(tmp_path)
    assert line["checks"]["destroyed"] is False
    assert "vast said no" in line["checks"]["destroy_error"]
    [rec] = gpu_state.load_state()["sessions"].values()
    assert rec["destroy_pending"] is True


@pytest.mark.parametrize("enter", ["rent", "rented"])
def test_the_budget_guard_prices_the_chosen_provider(enter):
    """Modal's pod-h100 is $3.95/h: a $3 cap must refuse on both entry points."""
    client = _client()
    with pytest.raises(gpu_rent.GPUBudgetExceededError):
        if enter == "rent":
            gpu_rent.rent(
                "pod-h100", workload="t", provider="modal", max_cost_usd=3.0, client=client
            )
        else:
            with gpu_rent.rented(
                "pod-h100", workload="t", provider="modal", max_cost_usd=3.0, client=client
            ):
                pass
    client.create_pod.assert_not_called()


@pytest.mark.parametrize("enter", ["rent", "rented"])
def test_keep_warm_on_a_modal_pod_is_refused_before_any_create(enter):
    """A Modal pod is an ephemeral app.run() context: it cannot outlive the process."""
    client = _client()
    with pytest.raises(ValueError, match="keep_warm_after_use"):
        if enter == "rent":
            gpu_rent.rent(
                "pod-rtx-4090",
                workload="t",
                provider="modal",
                keep_warm_after_use=True,
                client=client,
            )
        else:
            with gpu_rent.rented(
                "pod-rtx-4090",
                workload="t",
                provider="modal",
                keep_warm_after_use=True,
                client=client,
            ):
                pass
    client.create_pod.assert_not_called()


def test_actual_cost_uses_the_providers_rate():
    two_hours = 7200.0
    assert gpu_rent._compute_actual_cost("pod-h100", two_hours, provider="modal") == pytest.approx(
        2 * gpu_rent.HOURLY_USD_BY_PROVIDER["modal"]["pod-h100"]
    )


def test_a_serverless_session_is_booked_at_its_budget_rate():
    one_hour = 3600.0
    for provider in ("runpod", "modal", "vast"):
        cost = gpu_rent._compute_actual_cost("serverless", one_hour, provider=provider)
        assert cost == pytest.approx(gpu_rent.HOURLY_USD_BY_PROVIDER[provider]["serverless"])
        assert cost > 0


def _expired_session(sid: str, provider: str, *, pending: bool = False) -> None:
    gpu_state.upsert(
        sid,
        provider=provider,
        kind="pod-rtx-4090",
        workload="t",
        resource_type="pod",
        resource_id=f"{provider}-pod",
        gpu_type_id=None,
        max_lifetime_hours=1,
        cost_estimate_usd=1.0,
    )
    state = gpu_state.load_state()
    state["sessions"][sid]["expires_at"] = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    state["sessions"][sid]["destroy_pending"] = pending
    gpu_state.save_state(state)


def test_reconcile_scopes_lifetime_and_pending_to_its_provider():
    _expired_session("s-vast", "vast", pending=True)
    _expired_session("s-runpod", "runpod", pending=True)

    report = gpu_state.reconcile(_client(), provider="runpod")

    assert [e["session_id"] for e in report["lifetime_exceeded"]] == ["s-runpod"]
    assert [e["session_id"] for e in report["destroy_pending"]] == ["s-runpod"]


def test_the_reaper_never_destroys_another_providers_session():
    _expired_session("s-vast", "vast")
    client = _client()

    gpu_reaper.reap(client, auto_destroy=True, provider_label="runpod")

    client.destroy_pod.assert_not_called()
    assert gpu_state.get_session("s-vast")["destroyed_at"] is None


def test_a_non_runpod_destroy_error_does_not_stop_the_reaper(tmp_path):
    _expired_session("s-a", "vast")
    state = gpu_state.load_state()
    state["sessions"]["s-a"]["resource_id"] = "pod-a"
    gpu_state.save_state(state)
    _expired_session("s-b", "vast")
    client = _client()
    client.destroy_pod.side_effect = [VastLikeError("boom"), None]

    report = gpu_reaper.reap(client, auto_destroy=True, provider_label="vast")

    assert client.destroy_pod.call_count == 2
    assert len(report["errors"]) == 1 and len(report["destroyed"]) == 1
    assert _history(tmp_path)[-1]["provider"] == "vast"


def test_a_runpod_endpoint_is_recognised_by_its_fabrik_name(monkeypatch):
    from fabrik.drivers import runpod

    client = runpod.RunPodClient.__new__(runpod.RunPodClient)
    monkeypatch.setattr(
        client,
        "_request",
        lambda *_a, **_k: [
            {"id": "ep-ours", "name": "fabrik-gpu-train-a1b2c3"},
            {"id": "ep-theirs", "name": "someone-else"},
        ],
        raising=False,
    )
    tracker = _client()
    tracker.list_endpoints.return_value = client.list_endpoints()

    report = gpu_state.reconcile(tracker, provider="runpod")

    assert [e["resource_id"] for e in report["orphan_endpoints"]] == ["ep-ours"]
    assert report["foreign_count"] == 1


def test_never_reconciled_renders_an_age_the_alert_can_fire_on():
    metrics = {
        "sessions_total": {},
        "cost_total": {},
        "active_per_provider": {},
        "destroy_pending_per_provider": {},
        "last_reconcile_age_seconds": math.inf,
    }
    assert "gpu_rent_last_reconcile_age_seconds +Inf" in gpu_metrics.render(metrics)
    assert gpu_metrics.collect()["last_reconcile_age_seconds"] == math.inf


@pytest.mark.parametrize(
    ("name", "tagged"),
    [
        ("fabrik-gpu-train-a1b2c3", True),
        ("fabrik-gpu-", False),
        ("fabrik-gpu-experiment", False),
        ("fabrik-gpu-x-A1B2C3", False),
        ("someone-else", False),
    ],
)
def test_only_a_real_session_suffix_marks_an_endpoint_as_fabrik(name, tagged):
    """A session id ends in six lowercase hex digits; a hand-named `fabrik-gpu-*` endpoint must
    stay foreign, never become a reapable orphan (C4)."""
    from fabrik.drivers.runpod import fabrik_endpoint_tag

    assert bool(fabrik_endpoint_tag(name)) is tagged
    if tagged:
        assert fabrik_endpoint_tag(name) == {"FABRIK_SESSION_ID": "a1b2c3"}


def test_all_three_drivers_tag_endpoints_by_the_same_rule(monkeypatch):
    import subprocess

    from fabrik.drivers import modal_provider, runpod, vast_provider

    names = ["fabrik-gpu-train-a1b2c3", "fabrik-gpu-experiment"]
    rp = runpod.RunPodClient.__new__(runpod.RunPodClient)
    monkeypatch.setattr(
        rp, "_request", lambda *_a, **_k: [{"id": n, "name": n} for n in names], raising=False
    )
    vc = vast_provider.VastClient.__new__(vast_provider.VastClient)
    monkeypatch.setattr(
        vc,
        "_request",
        lambda *_a, **_k: {"results": [{"id": n, "endpoint_name": n} for n in names]},
        raising=False,
    )
    mc = modal_provider.ModalClient.__new__(modal_provider.ModalClient)
    mc.token_id = mc.token_secret = ""
    apps = json.dumps([{"app_id": n, "description": n, "state": "deployed"} for n in names])
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_a, **_k: subprocess.CompletedProcess([], 0, stdout=apps, stderr=""),
    )

    for client in (rp, vc, mc):
        tags = [bool(ep.get("env")) for ep in client.list_endpoints()]
        assert tags == [True, False], (type(client).__name__, tags)


@ENTRY_POINTS
def test_the_orphan_path_books_what_the_pod_cost(enter, monkeypatch):
    """A pod created and then lost at the RUNNING wait still billed: book it."""
    readings = []  # the first reading is the session start; every later one is 300 s on

    def fake_monotonic():
        readings.append(None)
        return 1000.0 if len(readings) == 1 else 1300.0

    monkeypatch.setattr(gpu_rent.time, "monotonic", fake_monotonic)
    booked = []
    monkeypatch.setattr(gpu_rent, "_record_actual_cost", lambda _t, **kw: booked.append(kw))
    client = _client()
    client.wait_for_running.side_effect = TimeoutError("slow host")

    enter(client)

    assert [b["cost_actual_usd"] for b in booked] == [
        pytest.approx(gpu_rent.HOURLY_USD_BY_PROVIDER["runpod"]["pod-rtx-4090"] * 300 / 3600)
    ]


@ENTRY_POINTS
def test_keep_on_failure_leaves_the_pod(enter):
    client = _client()
    client.wait_for_running.side_effect = TimeoutError("slow host")

    enter(client, keep_on_failure=True)

    client.destroy_pod.assert_not_called()


def test_keep_warm_after_use_leaves_the_pod_on_both_entry_points():
    for enter in (_via_rent, _via_rented):
        client = _client()
        enter(client, keep_warm_after_use=True)
        client.destroy_pod.assert_not_called()


@pytest.mark.parametrize("enter", ["rent", "rented"])
def test_a_reused_endpoint_is_never_destroyed(enter, monkeypatch):
    monkeypatch.setenv("RUNPOD_SERVERLESS_ENDPOINT_ID", "pinned-ep")
    client = _client()
    client.get_endpoint.return_value = {"id": "pinned-ep"}
    if enter == "rent":
        gpu_rent.rent("serverless", workload="t", client=client)
    else:
        with gpu_rent.rented("serverless", workload="t", client=client):
            pass
    client.destroy_endpoint.assert_not_called()


@pytest.mark.parametrize("workload", ["train", "vllm-openai", "a-b-c"])
def test_the_name_gpu_rent_gives_an_endpoint_is_the_one_the_tag_rule_reads(workload, monkeypatch):
    """If the two ever drift apart, every Fabrik endpoint turns foreign and is never reaped."""
    from fabrik.drivers.runpod import fabrik_endpoint_tag

    monkeypatch.delenv("RUNPOD_SERVERLESS_ENDPOINT_ID", raising=False)  # else the reuse path runs

    client = _client()
    session_id = gpu_rent._make_session_id("serverless")
    gpu_rent._create_serverless_endpoint(
        client,
        session_id=session_id,
        workload=workload,
        max_lifetime_hours=1,
        template_id="tpl",
        workers_min=0,
        workers_max=1,
        idle_timeout=5,
        flashboot=True,
    )
    name = client.create_endpoint.call_args.kwargs["name"]
    assert fabrik_endpoint_tag(name) == {"FABRIK_SESSION_ID": session_id[-6:]}
