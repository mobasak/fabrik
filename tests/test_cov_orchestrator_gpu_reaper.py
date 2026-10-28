"""Coverage for fabrik.orchestrator.gpu_reaper (hermetic: all state/clients mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fabrik.orchestrator import gpu_reaper


def _report(**over):
    base = {
        "in_state_not_live": [],
        "lifetime_exceeded": [],
        "destroy_pending": [],
        "orphan_pods": [],
        "orphan_endpoints": [],
        "foreign_count": 0,
    }
    base.update(over)
    return base


@pytest.fixture
def env(monkeypatch):
    """Patch reconcile/state/audit-log; return handles."""
    h = MagicMock()
    h.reconcile = MagicMock(return_value=_report())
    h.get_session = MagicMock(return_value=None)
    h.mark_destroyed = MagicMock()
    h.write_report = MagicMock()
    monkeypatch.setattr(gpu_reaper.gpu_state, "reconcile", h.reconcile)
    monkeypatch.setattr(gpu_reaper.gpu_state, "get_session", h.get_session)
    monkeypatch.setattr(gpu_reaper.gpu_state, "mark_destroyed", h.mark_destroyed)
    monkeypatch.setattr(gpu_reaper.gpu_rent, "write_report", h.write_report)
    return h


# ---------------------------------------------------------------- reap


def test_reap_report_only_does_not_destroy_or_audit(env):
    client = MagicMock()
    env.reconcile.return_value = _report(
        orphan_pods=[{"resource_id": "p1", "fabrik_session_id": "s1"}]
    )
    rep = gpu_reaper.reap(client, provider_label="vast")
    client.destroy_pod.assert_not_called()
    env.write_report.assert_not_called()
    assert rep["auto_destroy"] is False
    assert rep["provider"] == "vast"
    assert rep["destroyed"] == [] and rep["errors"] == []
    env.reconcile.assert_called_once_with(client, provider="vast")


def test_reap_default_client_is_runpod(env, monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(gpu_reaper, "RunPodClient", lambda: fake)
    gpu_reaper.reap()
    env.reconcile.assert_called_once_with(fake, provider="runpod")


def test_reap_auto_destroy_orphan_pod_and_endpoint(env):
    client = MagicMock()
    env.reconcile.return_value = _report(
        orphan_pods=[{"resource_id": "p1", "fabrik_session_id": "s1"}],
        orphan_endpoints=[{"resource_id": "e1", "fabrik_session_id": "s2"}],
    )
    rep = gpu_reaper.reap(client, auto_destroy=True)
    client.destroy_pod.assert_called_once_with("p1")
    client.destroy_endpoint.assert_called_once_with("e1")
    assert [d["resource_id"] for d in rep["destroyed"]] == ["p1", "e1"]
    assert rep["destroyed"][0] == {"type": "pod", "resource_id": "p1", "session_id": "s1"}
    assert rep["errors"] == []


def test_reap_lifetime_exceeded_and_destroy_pending_destroyed(env):
    client = MagicMock()
    env.reconcile.return_value = _report(
        lifetime_exceeded=[{"type": "pod", "resource_id": "a", "session_id": "sa"}],
        destroy_pending=[{"type": "endpoint", "resource_id": "b", "session_id": "sb"}],
    )
    rep = gpu_reaper.reap(client, auto_destroy=True)
    client.destroy_pod.assert_called_once_with("a")
    client.destroy_endpoint.assert_called_once_with("b")
    assert len(rep["destroyed"]) == 2


def test_reap_in_state_not_live_is_never_destroyed(env):
    client = MagicMock()
    env.reconcile.return_value = _report(
        in_state_not_live=[{"type": "pod", "resource_id": "gone", "session_id": "s"}]
    )
    rep = gpu_reaper.reap(client, auto_destroy=True)
    client.destroy_pod.assert_not_called()
    client.destroy_endpoint.assert_not_called()
    assert rep["destroyed"] == []


def test_reap_dedups_by_type_and_resource_id(env):
    client = MagicMock()
    env.reconcile.return_value = _report(
        lifetime_exceeded=[{"type": "pod", "resource_id": "p1", "session_id": "s1"}],
        orphan_pods=[{"resource_id": "p1", "fabrik_session_id": "s1"}],
    )
    rep = gpu_reaper.reap(client, auto_destroy=True)
    client.destroy_pod.assert_called_once_with("p1")
    assert len(rep["destroyed"]) == 1


def test_reap_same_id_different_type_not_deduped(env):
    client = MagicMock()
    env.reconcile.return_value = _report(
        lifetime_exceeded=[{"type": "pod", "resource_id": "x", "session_id": "s"}],
        orphan_endpoints=[{"resource_id": "x", "fabrik_session_id": "s"}],
    )
    gpu_reaper.reap(client, auto_destroy=True)
    client.destroy_pod.assert_called_once_with("x")
    client.destroy_endpoint.assert_called_once_with("x")


def test_reap_missing_type_defaults_to_pod(env):
    client = MagicMock()
    env.reconcile.return_value = _report(
        destroy_pending=[{"resource_id": "p9", "session_id": "s9"}]
    )
    gpu_reaper.reap(client, auto_destroy=True)
    client.destroy_pod.assert_called_once_with("p9")


def test_reap_unknown_type_recorded_as_error(env):
    client = MagicMock()
    env.reconcile.return_value = _report(
        lifetime_exceeded=[{"type": "volume", "resource_id": "v1", "session_id": "s"}]
    )
    rep = gpu_reaper.reap(client, auto_destroy=True)
    assert rep["errors"] == [{"resource_id": "v1", "error": "unknown type volume"}]
    assert rep["destroyed"] == []
    env.mark_destroyed.assert_not_called()


def test_reap_destroy_exception_does_not_abort_rest(env):
    client = MagicMock()
    client.destroy_pod.side_effect = [RuntimeError("boom"), None]
    env.reconcile.return_value = _report(
        orphan_pods=[
            {"resource_id": "p1", "fabrik_session_id": "s1"},
            {"resource_id": "p2", "fabrik_session_id": "s2"},
        ]
    )
    rep = gpu_reaper.reap(client, auto_destroy=True)
    assert rep["errors"] == [
        {"resource_id": "p1", "type": "pod", "session_id": "s1", "error": "boom"}
    ]
    assert [d["resource_id"] for d in rep["destroyed"]] == ["p2"]
    env.mark_destroyed.assert_called_once_with("s2")


def test_reap_marks_session_destroyed_when_resource_matches(env):
    client = MagicMock()
    env.get_session.return_value = {"resource_id": "p1"}
    env.reconcile.return_value = _report(
        orphan_pods=[{"resource_id": "p1", "fabrik_session_id": "s1"}]
    )
    gpu_reaper.reap(client, auto_destroy=True)
    env.mark_destroyed.assert_called_once_with("s1")


def test_reap_marks_destroyed_when_session_unrecorded(env):
    client = MagicMock()
    env.get_session.return_value = None
    env.reconcile.return_value = _report(
        orphan_pods=[{"resource_id": "p1", "fabrik_session_id": "s1"}]
    )
    gpu_reaper.reap(client, auto_destroy=True)
    env.mark_destroyed.assert_called_once_with("s1")


def test_reap_does_not_mark_live_session_with_other_resource(env):
    client = MagicMock()
    env.get_session.return_value = {"resource_id": "LIVE-POD"}
    env.reconcile.return_value = _report(
        orphan_pods=[{"resource_id": "dup", "fabrik_session_id": "s1"}]
    )
    rep = gpu_reaper.reap(client, auto_destroy=True)
    client.destroy_pod.assert_called_once_with("dup")
    env.mark_destroyed.assert_not_called()
    assert len(rep["destroyed"]) == 1


def test_reap_no_session_id_skips_state_lookup(env):
    client = MagicMock()
    env.reconcile.return_value = _report(destroy_pending=[{"type": "pod", "resource_id": "p1"}])
    rep = gpu_reaper.reap(client, auto_destroy=True)
    env.get_session.assert_not_called()
    env.mark_destroyed.assert_not_called()
    assert len(rep["destroyed"]) == 1


def test_reap_mark_destroyed_failure_is_swallowed_and_still_counted(env):
    client = MagicMock()
    env.mark_destroyed.side_effect = OSError("disk")
    env.reconcile.return_value = _report(
        orphan_pods=[{"resource_id": "p1", "fabrik_session_id": "s1"}]
    )
    rep = gpu_reaper.reap(client, auto_destroy=True)
    assert len(rep["destroyed"]) == 1
    assert rep["errors"] == []


def test_reap_audit_row_success(env):
    client = MagicMock()
    env.reconcile.return_value = _report(
        orphan_pods=[{"resource_id": "p1", "fabrik_session_id": "s1"}],
        in_state_not_live=[{"resource_id": "z"}],
        foreign_count=4,
    )
    gpu_reaper.reap(client, auto_destroy=True, provider_label="vast")
    env.write_report.assert_called_once()
    row = env.write_report.call_args.args[0]
    assert row["kind"] == "reaper" and row["workload"] == "reconcile"
    assert row["provider"] == "vast"
    assert row["session_id"].startswith("reaper-")
    assert row["success"] is True and row["error"] is None
    assert row["checks"]["orphan_pods"] == 1
    assert row["checks"]["destroyed"] == 1
    assert row["checks"]["in_state_not_live"] == 1
    assert row["checks"]["foreign_count"] == 4
    assert isinstance(row["ts"], int)


def test_reap_audit_row_failure_caps_error_text_at_three(env):
    client = MagicMock()
    client.destroy_pod.side_effect = RuntimeError("bad")
    env.reconcile.return_value = _report(
        orphan_pods=[{"resource_id": f"p{i}", "fabrik_session_id": f"s{i}"} for i in range(5)]
    )
    rep = gpu_reaper.reap(client, auto_destroy=True)
    row = env.write_report.call_args.args[0]
    assert len(rep["errors"]) == 5
    assert row["success"] is False
    assert row["checks"]["errors"] == 5
    assert row["error"] == "p0: bad; p1: bad; p2: bad"


# ------------------------------------------------- reap_all_providers


def test_all_providers_walks_each_in_order_and_merges(env, monkeypatch):
    clients = {n: MagicMock(name=n) for n in gpu_reaper.REAPER_PROVIDERS}
    monkeypatch.setattr(gpu_reaper.gpu_rent, "client_for_provider", lambda p: clients[p])
    seen = []

    def fake_reap(client, *, auto_destroy, provider_label):
        seen.append((provider_label, auto_destroy, client))
        return _report(
            orphan_pods=[{"resource_id": f"{provider_label}-p", "fabrik_session_id": "s"}],
            foreign_count=2,
        ) | {"destroyed": [], "errors": []}

    monkeypatch.setattr(gpu_reaper, "reap", fake_reap)
    rep = gpu_reaper.reap_all_providers(auto_destroy=True)
    assert [s[0] for s in seen] == ["runpod", "modal", "vast"]
    assert all(s[1] is True for s in seen)
    assert rep["foreign_count"] == 6
    assert rep["auto_destroy"] is True
    assert [e["provider"] for e in rep["orphan_pods"]] == ["runpod", "modal", "vast"]
    assert set(rep["providers"]) == {"runpod", "modal", "vast"}
    assert "scanned_at" in rep


def test_all_providers_client_init_failure_is_skipped(env, monkeypatch):
    def cfp(p):
        if p == "modal":
            raise RuntimeError("no token")
        return MagicMock()

    monkeypatch.setattr(gpu_reaper.gpu_rent, "client_for_provider", cfp)
    monkeypatch.setattr(
        gpu_reaper, "reap", lambda c, **kw: _report() | {"destroyed": [], "errors": []}
    )
    rep = gpu_reaper.reap_all_providers()
    assert rep["providers"]["modal"] == {
        "skipped": True,
        "reason": "client init failed: no token",
    }
    assert rep["providers"]["runpod"]["foreign_count"] == 0
    assert rep["errors"] == []


def test_all_providers_reap_failure_recorded_and_continues(env, monkeypatch):
    monkeypatch.setattr(gpu_reaper.gpu_rent, "client_for_provider", lambda p: MagicMock())

    def fake_reap(client, *, auto_destroy, provider_label):
        if provider_label == "runpod":
            raise ValueError("api down")
        return _report() | {"destroyed": [], "errors": []}

    monkeypatch.setattr(gpu_reaper, "reap", fake_reap)
    rep = gpu_reaper.reap_all_providers()
    assert rep["providers"]["runpod"]["skipped"] is False
    assert "api down" in rep["providers"]["runpod"]["error"]
    assert rep["errors"][0]["provider"] == "runpod"
    assert "vast" in rep["providers"] and "modal" in rep["providers"]


def test_all_providers_preserves_existing_provider_key_and_merges_errors(env, monkeypatch):
    monkeypatch.setattr(gpu_reaper.gpu_rent, "client_for_provider", lambda p: MagicMock())

    def fake_reap(client, *, auto_destroy, provider_label):
        r = _report() | {"destroyed": [], "errors": []}
        if provider_label == "vast":
            r["errors"] = [{"resource_id": "x", "error": "e", "provider": "custom"}]
            r["destroyed"] = [{"resource_id": "d"}, "not-a-dict"]
        return r

    monkeypatch.setattr(gpu_reaper, "reap", fake_reap)
    rep = gpu_reaper.reap_all_providers()
    assert rep["errors"][0]["provider"] == "custom"
    assert rep["destroyed"][0]["provider"] == "vast"
    assert rep["destroyed"][1] == "not-a-dict"


def test_reaper_providers_constant():
    assert gpu_reaper.REAPER_PROVIDERS == ("runpod", "modal", "vast")
