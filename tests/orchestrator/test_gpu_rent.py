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
