"""Unit tests for fabrik.orchestrator.gpu_rent + gpu_state + gpu_reaper.

Mirrors tests/orchestrator/test_vultr_drill.py. RunPodClient is a mock;
state file + audit log are redirected to tmp_path. Critical invariant
under test: resources are ALWAYS destroyed unless keep_warm_after_use
(on success) or keep_on_failure (on error).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from fabrik.drivers.runpod import GPU_TYPE_IDS, RunPodError
from fabrik.orchestrator import gpu_rent, gpu_reaper, gpu_state


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Redirect state file + audit log to tmp_path; clear MAX_DAILY_GPU_COST."""
    monkeypatch.setattr(gpu_state, "STATE_FILE", tmp_path / "gpu-rent-state.json")
    monkeypatch.setattr(gpu_rent, "GPU_RENT_LOG", tmp_path / "gpu-rent-history.jsonl")
    # Redirect the AI UsageTracker SQLite DB to tmp_path so we don't pollute
    # the operator's real ~/.fabrik/ai_usage.db during tests.
    from fabrik.ai import tracker as tracker_mod
    original_init = tracker_mod.UsageTracker.__init__
    def patched_init(self, database_path=None):
        original_init(self, database_path or str(tmp_path / "ai_usage.db"))
    monkeypatch.setattr(tracker_mod.UsageTracker, "__init__", patched_init)
    # Remove MAX_DAILY_GPU_COST so tests get the $50 default unless they override.
    monkeypatch.delenv("MAX_DAILY_GPU_COST", raising=False)
    yield


def _mock_client(*, pod_id: str = "pod-abc", endpoint_id: str = "ep-xyz") -> MagicMock:
    """Build a RunPodClient mock with sensible defaults."""
    c = MagicMock()
    c.create_pod.return_value = {"id": pod_id, "desiredStatus": "RUNNING",
                                  "publicIp": "1.2.3.4", "costPerHr": 0.69}
    c.wait_for_running.return_value = {"id": pod_id, "desiredStatus": "RUNNING",
                                        "publicIp": "1.2.3.4", "costPerHr": 0.69}
    c.get_pod.return_value = {"id": pod_id, "desiredStatus": "RUNNING"}
    c.list_pods.return_value = []
    c.create_endpoint.return_value = {"id": endpoint_id, "templateId": "tpl",
                                       "workersMin": 0, "flashboot": True}
    c.get_endpoint.return_value = {"id": endpoint_id, "workersMin": 0, "flashboot": True}
    c.list_endpoints.return_value = []
    return c


# ============================================================================
# Test 1 — cost estimation rounds up to whole hour
# ============================================================================
def test_estimate_cost_uses_kind_pricing():
    # pod-rtx-4090 = $0.69/hr (RunPod). Half hour rounds up to 1 hour.
    assert gpu_rent.estimate_cost("pod-rtx-4090", 0.5) == 0.69
    # 1.5 hours rounds up to 2 hours
    assert gpu_rent.estimate_cost("pod-rtx-4090", 1.5) == round(0.69 * 2, 4)
    # 1 hour pod-h100 = $2.89 (RunPod Secure Cloud, verified 2026-06-16)
    assert gpu_rent.estimate_cost("pod-h100", 1) == 2.89


def test_estimate_cost_provider_aware():
    # Same kind, different providers — different prices
    runpod_h100 = gpu_rent.estimate_cost("pod-h100", 1, provider="runpod")
    modal_h100 = gpu_rent.estimate_cost("pod-h100", 1, provider="modal")
    vast_h100 = gpu_rent.estimate_cost("pod-h100", 1, provider="vast")
    assert runpod_h100 == 2.89
    assert modal_h100 == 3.95
    assert vast_h100 == 2.00
    # Vast cheapest, Modal most expensive
    assert vast_h100 < runpod_h100 < modal_h100


def test_selection_advice_high_utilization_picks_runpod():
    r = gpu_rent.selection_advice("pod-h100", hours=4, utilization_rate=1.0)
    # Without checkpointing flag, Vast.ai veto kicks in → RunPod wins
    assert r["recommendation"]["provider"] == "runpod"


def test_selection_advice_low_utilization_picks_modal():
    r = gpu_rent.selection_advice("pod-h100", hours=4, utilization_rate=0.1)
    assert r["recommendation"]["provider"] == "modal"
    # Modal cost should be very low at 10% utilization
    assert r["recommendation"]["estimated_cost_usd"] < 2.0


def test_selection_advice_with_checkpointing_picks_vast():
    r = gpu_rent.selection_advice("pod-h100", hours=4, utilization_rate=1.0,
                                    needs_checkpointing=True)
    assert r["recommendation"]["provider"] == "vast"


# ============================================================================
# Test 2 — serverless aliases to no GPU type lookup
# ============================================================================
def test_kind_serverless_resolves_to_no_gpu_type():
    # serverless is in HOURLY_USD but NOT in GPU_TYPE_IDS
    assert "serverless" not in GPU_TYPE_IDS
    assert "serverless" in gpu_rent.HOURLY_USD


# ============================================================================
# Test 3 — pod-h100 friendly alias resolves to a real RunPod GPU ID string
# ============================================================================
def test_kind_pod_h100_resolves_to_real_runpod_id():
    assert GPU_TYPE_IDS["pod-h100"] == "NVIDIA H100 80GB HBM3"
    assert GPU_TYPE_IDS["pod-rtx-4090"] == "NVIDIA GeForce RTX 4090"
    # All 8 pod-* aliases resolve
    pod_aliases = [k for k in gpu_rent.ALL_KINDS if k.startswith("pod-")]
    assert len(pod_aliases) == 8
    for alias in pod_aliases:
        assert alias in GPU_TYPE_IDS


# ============================================================================
# Test 4 — dry-run creates nothing
# ============================================================================
def test_dry_run_creates_nothing():
    c = _mock_client()
    r = gpu_rent.rent("pod-rtx-4090", workload="smoke", dry_run=True, client=c)
    assert r["dry_run"] is True
    assert r["kind"] == "pod-rtx-4090"
    assert r["cost_estimate_usd"] == 0.69
    c.create_pod.assert_not_called()
    c.create_endpoint.assert_not_called()


# ============================================================================
# Test 5 — happy path: create → run work_fn → destroy
# ============================================================================
def test_happy_path_creates_then_destroys():
    c = _mock_client()
    workfn_called = {"count": 0}
    def wf(pod):
        workfn_called["count"] += 1
        assert pod["id"] == "pod-abc"
    r = gpu_rent.rent("pod-rtx-4090", workload="smoke", work_fn=wf,
                       client=c, max_cost_usd=5.0)
    assert r["success"] is True
    assert r["checks"]["created"] is True
    assert r["checks"]["work_fn"] == "ok"
    assert r["checks"]["destroyed"] is True
    assert workfn_called["count"] == 1
    c.create_pod.assert_called_once()
    c.destroy_pod.assert_called_once_with("pod-abc")
    # State file has the session marked destroyed
    sess = gpu_state.get_session(r["session_id"])
    assert sess is not None
    assert sess["destroyed_at"] is not None


# ============================================================================
# Test 6 — work_fn is invoked between create and destroy
# ============================================================================
def test_work_fn_runs_between_create_and_destroy():
    c = _mock_client()
    events = []
    c.create_pod.side_effect = lambda **kw: (events.append("create"),
                                             {"id": "pod-abc", "desiredStatus": "RUNNING"})[1]
    c.wait_for_running.side_effect = lambda *a, **kw: (events.append("wait"),
                                                        {"id": "pod-abc"})[1]
    c.destroy_pod.side_effect = lambda pid: events.append(f"destroy:{pid}")
    def wf(pod):
        events.append("work")
    gpu_rent.rent("pod-rtx-4090", workload="smoke", work_fn=wf,
                   client=c, max_cost_usd=5.0)
    assert events == ["create", "wait", "work", "destroy:pod-abc"]


# ============================================================================
# Test 7 — failure in work_fn still destroys (no orphan!)
# ============================================================================
def test_failure_in_work_fn_still_destroys():
    c = _mock_client()
    def wf(pod):
        raise RuntimeError("boom")
    r = gpu_rent.rent("pod-rtx-4090", workload="smoke", work_fn=wf,
                       client=c, max_cost_usd=5.0)
    assert r["success"] is False
    assert "boom" in r["error"]
    assert r["checks"]["destroyed"] is True
    c.destroy_pod.assert_called_once_with("pod-abc")


# ============================================================================
# Test 8 — keep_on_failure leaves the pod alive
# ============================================================================
def test_keep_on_failure_leaves_pod():
    c = _mock_client()
    def wf(pod):
        raise RuntimeError("boom")
    r = gpu_rent.rent("pod-rtx-4090", workload="smoke", work_fn=wf,
                       keep_on_failure=True, client=c, max_cost_usd=5.0)
    assert r["success"] is False
    c.destroy_pod.assert_not_called()
    assert r["checks"]["kept_for_inspection"] is True


# ============================================================================
# Test 9 — keep_warm_after_use leaves the pod alive on success
# ============================================================================
def test_keep_warm_after_use_leaves_pod_on_success():
    c = _mock_client()
    r = gpu_rent.rent("pod-rtx-4090", workload="smoke",
                       keep_warm_after_use=True, client=c, max_cost_usd=5.0)
    assert r["success"] is True
    c.destroy_pod.assert_not_called()
    assert r["checks"]["kept_for_inspection"] is True


# ============================================================================
# Test 10 — max-cost guard refuses BEFORE provider create call
# ============================================================================
def test_max_cost_guard_refuses_before_create():
    c = _mock_client()
    with pytest.raises(gpu_rent.GPUBudgetExceededError, match="exceeds --max-cost"):
        gpu_rent.rent("pod-h100", workload="smoke",
                       max_cost_usd=0.01, client=c, max_lifetime_hours=1)
    c.create_pod.assert_not_called()
    c.create_endpoint.assert_not_called()


# ============================================================================
# Test 11 — daily envelope guard refuses BEFORE provider create call
# ============================================================================
def test_daily_budget_guard_refuses_before_create(monkeypatch):
    monkeypatch.setenv("MAX_DAILY_GPU_COST", "0.01")
    c = _mock_client()
    with pytest.raises(gpu_rent.GPUBudgetExceededError, match="MAX_DAILY_GPU_COST"):
        gpu_rent.rent("pod-h100", workload="smoke",
                       max_cost_usd=50, client=c, max_lifetime_hours=1)
    c.create_pod.assert_not_called()


# ============================================================================
# Test 12 — unknown kind raises NotImplementedError before any client call
# ============================================================================
def test_unknown_kind_raises():
    with pytest.raises(NotImplementedError, match="unknown gpu kind"):
        gpu_rent.rent("pod-fictional", workload="smoke", client=_mock_client())


# ============================================================================
# Test 13 — unknown provider raises NotImplementedError
# ============================================================================
def test_unknown_provider_raises():
    with pytest.raises(NotImplementedError, match="unknown gpu provider"):
        gpu_rent.rent("pod-rtx-4090", workload="smoke", provider="fakecloud",
                       client=_mock_client())


# ============================================================================
# Test 14 — destroy failure marks destroy_pending (try/finally invariant)
# ============================================================================
def test_state_marks_destroy_pending_when_destroy_fails():
    c = _mock_client()
    c.destroy_pod.side_effect = RunPodError("transient 500", status=500)
    r = gpu_rent.rent("pod-rtx-4090", workload="smoke", client=c, max_cost_usd=5.0)
    assert r["success"] is True            # work_fn succeeded
    assert r["checks"]["destroyed"] is False
    assert "destroy_error" in r["checks"]
    sess = gpu_state.get_session(r["session_id"])
    assert sess["destroy_pending"] is True
    assert sess["destroyed_at"] is None


# ============================================================================
# Test 15 — missing RUNPOD_API_KEY raises at client init
# ============================================================================
def test_runpod_api_key_missing_raises_at_client_init(monkeypatch, tmp_path):
    from fabrik.drivers import runpod as runpod_mod
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    monkeypatch.setattr(runpod_mod, "SYSADMIN_ENV", tmp_path / "nonexistent")
    with pytest.raises(RunPodError, match="RUNPOD_API_KEY is required"):
        runpod_mod.RunPodClient()


# ============================================================================
# Test 16 — JSONL audit-log shape locked
# ============================================================================
def test_report_appended_to_history_log_as_jsonl():
    c = _mock_client()
    gpu_rent.rent("pod-rtx-4090", workload="smoke", client=c, max_cost_usd=5.0)
    assert gpu_rent.GPU_RENT_LOG.exists()
    lines = gpu_rent.GPU_RENT_LOG.read_text().strip().split("\n")
    assert len(lines) == 1
    rec = json.loads(lines[0])
    for field in ("ts", "ts_iso", "session_id", "kind", "workload", "provider",
                   "success", "cost_estimate_usd", "wall_clock_seconds", "checks"):
        assert field in rec, f"missing audit field: {field}"


# ============================================================================
# Test 17 — reaper detects orphans (alive on RunPod with FABRIK_SESSION_ID, no state)
# ============================================================================
def test_reconcile_detects_orphan_pods():
    c = _mock_client()
    c.list_pods.return_value = [
        {"id": "pod-orphan", "env": {"FABRIK_SESSION_ID": "gpu-pod-h100-fake"}},
        {"id": "pod-foreign", "env": {"SOMETHING": "else"}},  # NO fabrik tag
    ]
    c.list_endpoints.return_value = []
    report = gpu_reaper.reap(c, auto_destroy=False)
    assert len(report["orphan_pods"]) == 1
    assert report["orphan_pods"][0]["resource_id"] == "pod-orphan"
    assert report["foreign_count"] == 1   # the untagged one
    # Critical safety: reaper did NOT destroy anything in report mode
    c.destroy_pod.assert_not_called()


# ============================================================================
# Test 18 — reaper detects lifetime-exceeded sessions
# ============================================================================
def test_reconcile_detects_lifetime_exceeded():
    c = _mock_client()
    # Inject a session whose expires_at is in the past
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    state = gpu_state.load_state()
    state["sessions"]["gpu-pod-h100-old"] = {
        "provider": "runpod",
        "kind": "pod-h100",
        "workload": "expired",
        "resource_type": "pod",
        "resource_id": "pod-abc",
        "created_at": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
        "expires_at": past,
        "destroyed_at": None,
        "destroy_pending": False,
        "max_lifetime_hours": 1,
        "cost_estimate_usd": 3.29,
        "cost_actual_usd": None,
        "gpu_type_id": "NVIDIA H100 80GB HBM3",
    }
    gpu_state.save_state(state)
    c.list_pods.return_value = [{"id": "pod-abc"}]
    c.list_endpoints.return_value = []
    report = gpu_reaper.reap(c, auto_destroy=False)
    assert len(report["lifetime_exceeded"]) == 1
    assert report["lifetime_exceeded"][0]["session_id"] == "gpu-pod-h100-old"
    # Auto-destroy=False: nothing destroyed yet
    c.destroy_pod.assert_not_called()


# ============================================================================
# Bonus test — auto_destroy=True actually destroys lifetime-exceeded
# ============================================================================
def test_reaper_auto_destroy_kills_lifetime_exceeded():
    c = _mock_client()
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    state = gpu_state.load_state()
    state["sessions"]["gpu-pod-rtx-4090-old"] = {
        "provider": "runpod",
        "kind": "pod-rtx-4090",
        "workload": "expired",
        "resource_type": "pod",
        "resource_id": "pod-killme",
        "created_at": past,
        "expires_at": past,
        "destroyed_at": None,
        "destroy_pending": False,
        "max_lifetime_hours": 1,
        "cost_estimate_usd": 0.69,
        "cost_actual_usd": None,
        "gpu_type_id": "NVIDIA GeForce RTX 4090",
    }
    gpu_state.save_state(state)
    c.list_pods.return_value = [{"id": "pod-killme"}]
    c.list_endpoints.return_value = []
    report = gpu_reaper.reap(c, auto_destroy=True)
    assert len(report["destroyed"]) == 1
    c.destroy_pod.assert_called_once_with("pod-killme")
    # State is now marked destroyed
    assert gpu_state.get_session("gpu-pod-rtx-4090-old")["destroyed_at"] is not None


# ============================================================================
# Bonus test — reaper NEVER destroys foreign (non-tagged) pods
# ============================================================================
def test_reaper_never_destroys_foreign_pods():
    c = _mock_client()
    # A foreign pod (no FABRIK_SESSION_ID), even with --auto-destroy
    c.list_pods.return_value = [{"id": "pod-foreign", "env": {}}]
    c.list_endpoints.return_value = []
    report = gpu_reaper.reap(c, auto_destroy=True)
    assert report["foreign_count"] == 1
    c.destroy_pod.assert_not_called()
    assert len(report["destroyed"]) == 0


# ============================================================================
# Provider-aware GPU type resolution (G-LIVE-5 caught this 2026-06-16)
# ============================================================================
def test_resolve_gpu_type_id_runpod():
    """RunPod uses full marketing name."""
    assert gpu_rent._resolve_gpu_type_id("pod-rtx-4090", "runpod") == "NVIDIA GeForce RTX 4090"


def test_resolve_gpu_type_id_vast():
    """Vast uses short marketplace name ('RTX 4090')."""
    assert gpu_rent._resolve_gpu_type_id("pod-rtx-4090", "vast") == "RTX 4090"


def test_resolve_gpu_type_id_modal():
    """Modal maps RTX 4090 to its closest analog 'L4'."""
    assert gpu_rent._resolve_gpu_type_id("pod-rtx-4090", "modal") == "L4"


def test_resolve_gpu_type_id_unknown_provider_raises():
    with pytest.raises(NotImplementedError, match="unknown provider"):
        gpu_rent._resolve_gpu_type_id("pod-rtx-4090", "azure")


def test_resolve_gpu_type_id_vast_unsupported_kind_raises():
    """Vast doesn't carry every kind (e.g. ``serverless`` is N/A)."""
    with pytest.raises(NotImplementedError, match="Vast.ai does not have a mapping"):
        gpu_rent._resolve_gpu_type_id("serverless", "vast")


# ============================================================================
# selection_advice auto-routing — the heart of --provider auto
# ============================================================================
def test_selection_advice_high_util_favors_runpod():
    """Continuous training → RunPod (cheapest at 100% utilization)."""
    advice = gpu_rent.selection_advice("pod-h100", hours=4, utilization_rate=1.0)
    assert advice["recommendation"]["provider"] == "runpod"


def test_selection_advice_low_util_favors_modal():
    """Bursty inference (20% util) → Modal per-second wins."""
    advice = gpu_rent.selection_advice("pod-h100", hours=4, utilization_rate=0.2)
    assert advice["recommendation"]["provider"] == "modal"
    assert "low utilization" in advice["recommendation"]["rationale"].lower()


def test_selection_advice_checkpointing_unlocks_vast():
    """needs_checkpointing=True opens Vast.ai spot to recommendation."""
    advice = gpu_rent.selection_advice(
        "pod-h100", hours=4, utilization_rate=1.0, needs_checkpointing=True
    )
    assert advice["recommendation"]["provider"] == "vast"


def test_selection_advice_serverless_includes_vast_phase_35():
    """Phase 3.5 (2026-06-17): Vast serverless is wired (POST /endptjobs/ +
    /workergroups/). The historical needs_serverless Vast exclusion is dropped.
    All three providers must be eligible for serverless workloads.
    """
    advice = gpu_rent.selection_advice(
        "serverless", hours=4, utilization_rate=0.5, needs_serverless=True
    )
    # All three providers must support serverless after Phase 3.5
    assert advice["providers"]["runpod"].get("supported") is True
    assert advice["providers"]["modal"].get("supported") is True
    assert advice["providers"]["vast"].get("supported") is True
    # Recommendation may be any of the three (route depends on cost calc)
    assert advice["recommendation"]["provider"] in ("runpod", "modal", "vast")


# ============================================================================
# client_for_provider factory — used by cross-provider CLI commands
# ============================================================================
def test_client_for_provider_runpod_returns_runpod_client(monkeypatch):
    """Factory returns a RunPodClient for 'runpod'."""
    monkeypatch.setenv("RUNPOD_API_KEY", "rpa_test")
    c = gpu_rent.client_for_provider("runpod")
    from fabrik.drivers.runpod import RunPodClient
    assert isinstance(c, RunPodClient)


def test_client_for_provider_unknown_raises():
    """Factory raises NotImplementedError for unknown providers."""
    with pytest.raises(NotImplementedError, match="unknown gpu provider"):
        gpu_rent.client_for_provider("azure")


# ============================================================================
# Multi-provider reaper — reap_all_providers iterates RunPod + Modal + Vast
# ============================================================================
def test_reap_all_providers_skips_unconfigured_gracefully(monkeypatch):
    """When a provider client can't be constructed (no token), the reaper
    records it as skipped without aborting the other providers' reconcile."""
    from fabrik.orchestrator import gpu_reaper

    # Force every provider's client_for_provider() to raise
    def _bad_factory(name):
        raise RuntimeError(f"no token for {name}")

    monkeypatch.setattr(gpu_rent, "client_for_provider", _bad_factory)
    report = gpu_reaper.reap_all_providers(auto_destroy=False)
    assert "providers" in report
    for name in ("runpod", "modal", "vast"):
        assert report["providers"][name]["skipped"] is True
        assert "no token" in report["providers"][name]["reason"]
    # Top-level merge is still valid (no destroys, no errors)
    assert report["destroyed"] == []
    assert report["foreign_count"] == 0


def test_reap_all_providers_tags_entries_with_provider(monkeypatch):
    """Drift entries from each provider's reconcile should be tagged with
    the provider so the operator can see WHO owns each orphan."""
    from fabrik.orchestrator import gpu_reaper

    def _factory(name):
        c = MagicMock()
        c.list_pods.return_value = [
            {"id": f"pod-{name}-orphan", "env": {"FABRIK_SESSION_ID": f"sess-{name}"}}
        ]
        c.list_endpoints.return_value = []
        return c

    monkeypatch.setattr(gpu_rent, "client_for_provider", _factory)
    report = gpu_reaper.reap_all_providers(auto_destroy=False)
    # Each provider contributed one orphan_pod tagged with its name
    by_provider = {e["provider"] for e in report["orphan_pods"]}
    assert by_provider == {"runpod", "modal", "vast"}


# ============================================================================
# Provider-scoped reconcile — Modal session NOT flagged when scanning RunPod
# ============================================================================
def test_reconcile_provider_scope_doesnt_falsely_flag_other_providers_sessions():
    """Bug fix 2026-06-16: gpu_state.reconcile() iterates ALL sessions but
    checks them against ONE provider's live_pods. Without provider scoping,
    a Modal-recorded session shows up as 'in_state_not_live' when reconcile
    runs against RunPod.
    """
    # Create a Modal-provider session in state
    gpu_state.upsert(
        session_id="modal-sess-1",
        provider="modal",
        kind="pod-rtx-4090",
        workload="multi-test",
        resource_type="pod",
        resource_id="fc-modal-1",
        gpu_type_id="L4",
        max_lifetime_hours=1,
        cost_estimate_usd=0.8,
    )
    # Reconcile against a RunPod-shaped client (no Modal IDs in live_pods)
    runpod_client = MagicMock()
    runpod_client.list_pods.return_value = []
    runpod_client.list_endpoints.return_value = []

    report = gpu_state.reconcile(runpod_client, provider="runpod")
    # Modal session must NOT appear in RunPod's in_state_not_live report
    flagged_ids = {e["resource_id"] for e in report["in_state_not_live"]}
    assert "fc-modal-1" not in flagged_ids


# ============================================================================
# Orphan-cleanup invariant — pod_id recorded BEFORE wait_for_running
# ============================================================================
def test_create_pod_records_resource_id_before_wait(monkeypatch):
    """G-LIVE-5 bug: if wait_for_running raises, the pod is orphaned + bills
    until manually destroyed. Fix: report['resource_id'] is set the moment
    create_pod returns, so the finally block can destroy it.
    """
    c = MagicMock()
    c.create_pod.return_value = {"id": "pod-orphan-test", "actual_status": "loading"}
    c.wait_for_running.side_effect = RuntimeError("simulated stuck-in-loading")

    report = {}
    with pytest.raises(RuntimeError, match="simulated stuck"):
        gpu_rent._create_pod(
            c,
            session_id="test-session",
            kind="pod-rtx-4090",
            workload="orphan-test",
            max_lifetime_hours=1,
            image_name="test-image",
            cloud_type="SECURE",
            interruptible=False,
            provider="runpod",
            report=report,
        )

    # Critical: resource_id was recorded BEFORE wait_for_running raised
    assert report.get("resource_id") == "pod-orphan-test"


# ============================================================================
# Phase 3.5 — Serverless dispatch across all 3 providers
# ============================================================================
def test_create_serverless_endpoint_dispatches_runpod(monkeypatch):
    """RunPod serverless: uses RUNPOD_SERVERLESS_TEMPLATE_ID path when no
    pinned endpoint env var is set."""
    # Clear pinned endpoint so we exercise the create path, not reuse
    monkeypatch.delenv("RUNPOD_SERVERLESS_ENDPOINT_ID", raising=False)
    c = MagicMock()
    c.create_endpoint.return_value = {"id": "ep-rp-1", "_provider": "runpod"}
    ep = gpu_rent._create_serverless_endpoint(
        c, session_id="sess-001", workload="t1", max_lifetime_hours=1,
        template_id="rp-template", workers_min=0, workers_max=1,
        idle_timeout=60, flashboot=True, provider="runpod",
    )
    assert ep["id"] == "ep-rp-1"
    assert c.create_endpoint.called
    # Verify the endpoint name carries Fabrik tag prefix (C4 invariant)
    call_kwargs = c.create_endpoint.call_args.kwargs
    assert call_kwargs["name"].startswith("fabrik-gpu-t1-")


def test_create_serverless_endpoint_runpod_reuses_pinned(monkeypatch):
    """When RUNPOD_SERVERLESS_ENDPOINT_ID is set, reuse path returns
    get_endpoint result — does NOT call create_endpoint."""
    monkeypatch.setenv("RUNPOD_SERVERLESS_ENDPOINT_ID", "ep-pinned-xyz")
    c = MagicMock()
    c.get_endpoint.return_value = {"id": "ep-pinned-xyz", "workersMin": 0}
    ep = gpu_rent._create_serverless_endpoint(
        c, session_id="sess-r1", workload="reuse", max_lifetime_hours=1,
        template_id=None, workers_min=0, workers_max=1,
        idle_timeout=60, flashboot=True, provider="runpod",
    )
    assert ep["_fabrik_reuse"] is True
    assert ep["id"] == "ep-pinned-xyz"
    assert not c.create_endpoint.called


def test_create_serverless_endpoint_dispatches_modal():
    """Modal serverless: passes template_id + model to client."""
    c = MagicMock()
    c.create_endpoint.return_value = {"id": "fabrik-gpu-t2-abc", "_provider": "modal"}
    ep = gpu_rent._create_serverless_endpoint(
        c, session_id="sess-002", workload="t2", max_lifetime_hours=1,
        template_id="echo-handler", workers_min=0, workers_max=1,
        idle_timeout=60, flashboot=True, provider="modal", model=None,
    )
    assert ep["_fabrik_session_id"] == "sess-002"
    call_kwargs = c.create_endpoint.call_args.kwargs
    assert call_kwargs["template_id"] == "echo-handler"
    assert call_kwargs["name"].startswith("fabrik-gpu-t2-")


def test_create_serverless_endpoint_dispatches_vast():
    """Vast serverless: passes template_id to client (resolves to hash later)."""
    c = MagicMock()
    c.create_endpoint.return_value = {"id": "12345", "_provider": "vast"}
    ep = gpu_rent._create_serverless_endpoint(
        c, session_id="sess-003", workload="t3", max_lifetime_hours=1,
        template_id="vllm-openai", workers_min=0, workers_max=1,
        idle_timeout=60, flashboot=True, provider="vast",
        model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    )
    assert ep["id"] == "12345"
    call_kwargs = c.create_endpoint.call_args.kwargs
    assert call_kwargs["template_id"] == "vllm-openai"
    assert call_kwargs["model"] == "TinyLlama/TinyLlama-1.1B-Chat-v1.0"


def test_create_serverless_endpoint_modal_requires_template():
    """Modal must reject calls without a template — there's no default app."""
    c = MagicMock()
    with pytest.raises(NotImplementedError, match="--template"):
        gpu_rent._create_serverless_endpoint(
            c, session_id="sess-004", workload="t4", max_lifetime_hours=1,
            template_id=None, workers_min=0, workers_max=1,
            idle_timeout=60, flashboot=True, provider="modal",
        )


def test_create_serverless_endpoint_vast_requires_template():
    """Vast must reject calls without a template — workergroup needs one."""
    c = MagicMock()
    with pytest.raises(NotImplementedError, match="--template"):
        gpu_rent._create_serverless_endpoint(
            c, session_id="sess-005", workload="t5", max_lifetime_hours=1,
            template_id=None, workers_min=0, workers_max=1,
            idle_timeout=60, flashboot=True, provider="vast",
        )


def test_create_serverless_endpoint_unknown_provider_raises():
    c = MagicMock()
    with pytest.raises(NotImplementedError, match="not implemented for provider"):
        gpu_rent._create_serverless_endpoint(
            c, session_id="sess-006", workload="t6", max_lifetime_hours=1,
            template_id="x", workers_min=0, workers_max=1,
            idle_timeout=60, flashboot=True, provider="azure",
        )


# ============================================================================
# Phase 3.5 — Modal driver subprocess pattern (B1/B2 workarounds)
# ============================================================================
def test_modal_destroy_endpoint_uses_subprocess(monkeypatch):
    """Modal driver MUST use `modal app stop` subprocess (no SDK .stop() in 1.5.0)."""
    from fabrik.drivers.modal_provider import ModalClient

    monkeypatch.setenv("MODAL_TOKEN_ID", "ak-test")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "as-test")
    # Mock the deferred SDK import to bypass real Modal connection
    fake_modal = MagicMock()
    monkeypatch.setattr(
        "fabrik.drivers.modal_provider.ModalClient.__init__",
        lambda self, *a, **kw: setattr(self, "_modal", fake_modal)
        or setattr(self, "token_id", "ak-test")
        or setattr(self, "token_secret", "as-test"),
    )

    c = ModalClient()
    calls = []

    def fake_run(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    monkeypatch.setattr("fabrik.drivers.modal_provider.subprocess.run", fake_run)
    c.destroy_endpoint("ap-test-123")
    # Verify the subprocess invocation includes --yes for non-interactive mode
    # (Modal CLI prompts otherwise; LIVE-12 caught this).
    assert len(calls) == 1
    cmd = calls[0]["args"][0]
    assert cmd == ["modal", "app", "stop", "--yes", "ap-test-123"]


def test_modal_list_endpoints_uses_subprocess_filters_stopped(monkeypatch):
    """list_endpoints calls `modal app list --json` AND filters out stopped apps."""
    from fabrik.drivers.modal_provider import ModalClient

    monkeypatch.setenv("MODAL_TOKEN_ID", "ak-test")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "as-test")
    fake_modal = MagicMock()
    monkeypatch.setattr(
        "fabrik.drivers.modal_provider.ModalClient.__init__",
        lambda self, *a, **kw: setattr(self, "_modal", fake_modal)
        or setattr(self, "token_id", "ak-test")
        or setattr(self, "token_secret", "as-test"),
    )

    c = ModalClient()
    fake_apps = [
        {"app_id": "ap-1", "description": "fabrik-gpu-test-aaa111", "state": "deployed"},
        {"app_id": "ap-2", "description": "fabrik-gpu-test-bbb222", "state": "stopped"},
        {"app_id": "ap-3", "description": "user-app", "state": "deployed"},
    ]

    def fake_run(*args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps(fake_apps)
        result.stderr = ""
        return result

    import json as _stdjson  # local alias so test reads cleanly

    json = _stdjson  # noqa: A001 — only used inside the patched fake_run scope
    monkeypatch.setattr("fabrik.drivers.modal_provider.subprocess.run", fake_run)
    eps = c.list_endpoints()
    # Stopped app filtered out → 2 results
    assert len(eps) == 2
    ids = {e["id"] for e in eps}
    assert ids == {"ap-1", "ap-3"}
    # C4 tag-safety: fabrik-tagged app gets env.FABRIK_SESSION_ID synthesized
    fabrik_ep = next(e for e in eps if e["id"] == "ap-1")
    assert "FABRIK_SESSION_ID" in fabrik_ep["env"]
    # User app gets empty env (foreign — reaper must skip)
    user_ep = next(e for e in eps if e["id"] == "ap-3")
    assert user_ep["env"] == {}


# ============================================================================
# Phase 3.5 — Vast.ai serverless driver
# ============================================================================
def test_vast_create_endpoint_uses_workergroups_not_autogroups(monkeypatch):
    """B4 (plan §0): Vast driver MUST POST to /workergroups/, NEVER /autogroups/."""
    from fabrik.drivers.vast_provider import VastClient

    monkeypatch.setenv("VAST_API_KEY", "test-key-vast")
    requests_made: list[dict] = []

    def fake_request(self, method, path, *, json=None, params=None):
        requests_made.append({"method": method, "path": path, "json": json})
        if path == "/endptjobs/" and method == "POST":
            return {"success": True, "result": 12345}
        if path == "/workergroups/" and method == "POST":
            return {"success": True, "result": 67890}
        if path.startswith("/template/"):
            return []
        return {}

    monkeypatch.setattr(VastClient, "_request", fake_request)
    monkeypatch.setattr(VastClient, "_template_exists", lambda self, h: True)

    c = VastClient()
    ep = c.create_endpoint(
        template_id="vllm-openai",
        name="fabrik-gpu-test-vast-001",
        gpu_type_ids=["RTX 4090"],
        workers_min=0, workers_max=1, idle_timeout=300, flashboot=True,
    )

    paths = [r["path"] for r in requests_made]
    assert "/endptjobs/" in paths
    assert "/workergroups/" in paths
    assert "/autogroups/" not in paths, f"hit dead /autogroups/ path: {paths}"
    assert ep["id"] == "12345"
    assert ep["_workergroup_id"] == 67890


def test_vast_destroy_endpoint_idempotent_on_404(monkeypatch):
    """destroy_endpoint MUST treat 404 as success (idempotent)."""
    from fabrik.drivers.vast_provider import VastClient, VastError

    monkeypatch.setenv("VAST_API_KEY", "test-key-vast")

    def fake_request(self, method, path, *, json=None, params=None):
        err = VastError("Not Found")
        err.status = 404
        raise err

    monkeypatch.setattr(VastClient, "_request", fake_request)
    c = VastClient()
    c.destroy_endpoint("12345")  # MUST NOT raise


def test_vast_resolve_template_hash_pinned():
    """Pinned vllm-openai → top hash f815ac7... (verified live 2026-06-17)."""
    from fabrik.drivers.vast_provider import VastClient
    import unittest.mock
    with unittest.mock.patch.object(VastClient, "__init__", lambda self, *a, **kw: None):
        c = VastClient()
        c.api_key = "test"
        c._template_exists = lambda h: True
        assert c._resolve_template_hash("vllm-openai") == "f815ac7f2bf76828b3c9ec4b71f0af3c"


def test_vast_resolve_template_hash_accepts_raw_hash():
    """A 32-char hex string is returned as-is (no lookup)."""
    from fabrik.drivers.vast_provider import VastClient
    import unittest.mock
    with unittest.mock.patch.object(VastClient, "__init__", lambda self, *a, **kw: None):
        c = VastClient()
        c.api_key = "test"
        raw = "abcdef0123456789abcdef0123456789"
        assert c._resolve_template_hash(raw) == raw


def test_vast_list_endpoints_tags_fabrik_prefixed(monkeypatch):
    """list_endpoints synthesizes FABRIK_SESSION_ID for C4 tag-safety."""
    from fabrik.drivers.vast_provider import VastClient

    monkeypatch.setenv("VAST_API_KEY", "test-key-vast")

    def fake_request(self, method, path, *, json=None, params=None):
        return {"results": [
            {"endpoint_id": 100, "endpoint_name": "fabrik-gpu-test-aaa111"},
            {"endpoint_id": 101, "endpoint_name": "user-endpoint"},
        ]}

    monkeypatch.setattr(VastClient, "_request", fake_request)
    c = VastClient()
    eps = c.list_endpoints()
    assert len(eps) == 2
    fabrik_ep = next(e for e in eps if e["id"] == "100")
    assert "FABRIK_SESSION_ID" in fabrik_ep["env"]
    foreign_ep = next(e for e in eps if e["id"] == "101")
    assert foreign_ep["env"] == {}


# ============================================================================
# Code review iteration 1 fixes — regression guards
# ============================================================================
def test_modal_destroy_endpoint_idempotent_on_already_stopped(monkeypatch):
    """Code review iter-1: Modal destroy must treat 'already stopped' /
    'not found' as success (mirrors Vast's 404 handling)."""
    from fabrik.drivers.modal_provider import ModalClient

    monkeypatch.setenv("MODAL_TOKEN_ID", "ak-test")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "as-test")
    fake_modal = MagicMock()
    monkeypatch.setattr(
        "fabrik.drivers.modal_provider.ModalClient.__init__",
        lambda self, *a, **kw: setattr(self, "_modal", fake_modal)
        or setattr(self, "token_id", "ak-test")
        or setattr(self, "token_secret", "as-test"),
    )

    c = ModalClient()

    # Simulate "already stopped" non-zero exit (live error message from
    # 2026-06-17 reconcile during LIVE-17)
    def fake_run_already_stopped(*args, **kwargs):
        r = MagicMock()
        r.returncode = 1
        r.stdout = ""
        r.stderr = "App is already stopped. (Stopped at 2026-06-17 by 'mobasak')."
        return r

    monkeypatch.setattr(
        "fabrik.drivers.modal_provider.subprocess.run", fake_run_already_stopped
    )
    # Must NOT raise
    c.destroy_endpoint("ap-already-stopped")

    # Simulate "not found"
    def fake_run_not_found(*args, **kwargs):
        r = MagicMock()
        r.returncode = 1
        r.stdout = ""
        r.stderr = "Error: App not found"
        return r

    monkeypatch.setattr(
        "fabrik.drivers.modal_provider.subprocess.run", fake_run_not_found
    )
    c.destroy_endpoint("ap-missing")  # Must NOT raise


def test_modal_destroy_endpoint_raises_on_real_error(monkeypatch):
    """Code review iter-1: non-idempotent errors should still surface."""
    from fabrik.drivers.modal_provider import ModalClient, ModalError

    monkeypatch.setenv("MODAL_TOKEN_ID", "ak-test")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "as-test")
    fake_modal = MagicMock()
    monkeypatch.setattr(
        "fabrik.drivers.modal_provider.ModalClient.__init__",
        lambda self, *a, **kw: setattr(self, "_modal", fake_modal)
        or setattr(self, "token_id", "ak-test")
        or setattr(self, "token_secret", "as-test"),
    )

    c = ModalClient()

    def fake_run_auth_fail(*args, **kwargs):
        r = MagicMock()
        r.returncode = 1
        r.stdout = ""
        r.stderr = "Authentication failed: invalid token"
        return r

    monkeypatch.setattr(
        "fabrik.drivers.modal_provider.subprocess.run", fake_run_auth_fail
    )
    import pytest as _pytest
    with _pytest.raises(ModalError, match="Authentication failed"):
        c.destroy_endpoint("ap-x")


def test_vast_list_endpoints_handles_singular_result_shape(monkeypatch):
    """Code review iter-1: Vast list_endpoints must handle singular `result`
    dict as well as plural `results` list (defensive against API drift)."""
    from fabrik.drivers.vast_provider import VastClient

    monkeypatch.setenv("VAST_API_KEY", "test-key-vast")

    def fake_request_singular(self, method, path, *, json=None, params=None):
        # Singular shape with a single endpoint inside `result`
        return {
            "success": True,
            "result": {"id": 555, "endpoint_name": "fabrik-gpu-singular-aaa"},
        }

    monkeypatch.setattr(VastClient, "_request", fake_request_singular)
    c = VastClient()
    eps = c.list_endpoints()
    assert len(eps) == 1
    assert eps[0]["id"] == "555"
    assert "FABRIK_SESSION_ID" in eps[0]["env"]


def test_history_report_includes_model_and_template_id():
    """Code review iter-1: report must carry model + template_id (per
    55-observability.md per-call structured fields requirement)."""
    c = _mock_client()
    r = gpu_rent.rent(
        "pod-rtx-4090",
        workload="smoke",
        provider="runpod",
        dry_run=True,
        client=c,
        template_id="my-template",
        model="Qwen/Qwen3-1.7B",
    )
    assert r["template_id"] == "my-template"
    assert r["model"] == "Qwen/Qwen3-1.7B"


# ============================================================================
# Code review iteration 2 fixes — regression guards
# ============================================================================
def test_modal_create_endpoint_cleans_rendered_template_on_failure(monkeypatch, tmp_path):
    """Iter-2 fix: if app.deploy fails after rendering, the rendered
    template file MUST be unlinked (else /tmp/ leaks per-call)."""
    from fabrik.drivers.modal_provider import ModalClient, ModalError

    monkeypatch.setenv("MODAL_TOKEN_ID", "ak-test")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "as-test")
    fake_modal = MagicMock()
    monkeypatch.setattr(
        "fabrik.drivers.modal_provider.ModalClient.__init__",
        lambda self, *a, **kw: setattr(self, "_modal", fake_modal)
        or setattr(self, "token_id", "ak-test")
        or setattr(self, "token_secret", "as-test"),
    )

    c = ModalClient()
    # Stub the renderer to write a known temp path
    leaked_path = tmp_path / "fabrik-modal-test-leak.py"
    leaked_path.write_text(
        "import modal\napp = modal.App(name='test')\n"
        "def _explode(): raise RuntimeError('forced')\n"
        "app.deploy = lambda *a, **kw: _explode()\n"
    )
    monkeypatch.setattr(
        ModalClient,
        "_render_modal_template",
        lambda self, *a, **kw: str(leaked_path),
    )

    # Make Modal SDK module loadable but cause app.deploy to fail
    import pytest as _pytest
    with _pytest.raises(ModalError):
        c.create_endpoint(template_id="echo-handler", name="test-fail")
    # CRITICAL: tempfile must be cleaned up after the failure
    assert not leaked_path.exists(), \
        f"rendered template leaked at {leaked_path} after create_endpoint failure"


def test_rented_context_manager_report_includes_model_and_template():
    """Iter-2 regression: rented() context manager's report dict must
    include template_id + model (was missing — iter-1 only patched rent())."""
    c = _mock_client()
    # rented() is a context manager — we just need to peek into the report
    # state once it builds. Using dry-run isn't supported for rented(),
    # so we mock the work + verify by source inspection instead.
    import inspect
    src = inspect.getsource(gpu_rent.rented)
    # Both fields must be present in the report dict construction
    assert '"template_id": template_id' in src, \
        "rented() report dict missing template_id (iter-2 regression)"
    assert '"model": model' in src, \
        "rented() report dict missing model (iter-2 regression)"
