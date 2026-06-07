"""Unit tests for fabrik.orchestrator.vultr_drill (Phase 3a, `bare`).

VultrClient is a mock; SSH probe + state + drill-log are redirected to tmp.
The critical invariant under test: the instance is ALWAYS destroyed unless the
drill failed AND keep_on_failure is set.
"""

from unittest.mock import MagicMock

import pytest

from fabrik.drivers.vultr import VultrError
from fabrik.orchestrator import vultr_drill, vultr_state


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(vultr_state, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(vultr_drill, "DRILL_LOG", tmp_path / "drills.jsonl")
    monkeypatch.setattr(vultr_drill, "_ssh_probe", lambda ip, **kw: True)
    yield


def _mock_client(monthly=10.0):
    c = MagicMock()
    c.list_plans.return_value = [
        {"id": "vc2-1c-0.5gb-v6", "monthly_cost": 2.5, "locations": ["lax"]},  # v6 — skipped
        {"id": "vc2-1c-2gb", "monthly_cost": monthly, "locations": ["lax"]},
        {"id": "vc2-2c-4gb", "monthly_cost": monthly + 10.0, "locations": ["lax"]},
        {"id": "vc2-1c-1gb", "monthly_cost": 6.0, "locations": ["ord"]},        # wrong region
    ]
    c.create_instance.return_value = ("instance", {"id": "i-123"})
    c.wait_for_active.return_value = {"main_ip": "1.2.3.4", "status": "active"}
    return c


def test_estimate_cost_rounds_up_to_hour():
    assert vultr_drill.estimate_cost(672.0, 60) == 1.0       # $1/hr, min 1h
    assert vultr_drill.estimate_cost(672.0, 3601) == 2.0     # 2h


def test_cheapest_ipv4_plan_skips_v6_and_wrong_region():
    plan, cost = vultr_drill.cheapest_ipv4_plan(_mock_client(), "lax")
    assert plan == "vc2-1c-2gb" and cost == 10.0  # cheapest non-v6 in lax


def test_dry_run_creates_nothing():
    c = _mock_client()
    rep = vultr_drill.drill("bare", sshkey_ids=["k"], dry_run=True, client=c)
    assert rep["dry_run"] is True and rep["plan"] == "vc2-1c-2gb"
    c.create_instance.assert_not_called()


def test_happy_path_creates_then_destroys():
    c = _mock_client()
    rep = vultr_drill.drill("bare", sshkey_ids=["k"], client=c)
    assert rep["success"] is True
    assert rep["checks"]["destroyed"] is True
    c.create_instance.assert_called_once()
    c.destroy.assert_called_once_with("instance", "i-123")
    # state record marked destroyed
    assert vultr_state.get_instance(rep["name"])["destroyed_at"] is not None


def test_failure_still_destroys_no_orphan():
    c = _mock_client()
    c.wait_for_active.side_effect = VultrError("never came up")
    rep = vultr_drill.drill("bare", sshkey_ids=["k"], client=c)
    assert rep["success"] is False
    assert "never came up" in rep["error"]
    c.destroy.assert_called_once_with("instance", "i-123")   # destroyed despite failure
    assert rep["checks"]["destroyed"] is True


def test_keep_on_failure_leaves_instance():
    c = _mock_client()
    c.wait_for_active.side_effect = VultrError("boom")
    rep = vultr_drill.drill("bare", sshkey_ids=["k"], keep_on_failure=True, client=c)
    assert rep["success"] is False
    c.destroy.assert_not_called()                            # left for operator
    assert rep["checks"]["kept_for_debug"] is True


def test_max_cost_guard_refuses_before_create():
    c = _mock_client(monthly=720.0)  # ~$1.07/hr * 4h ≈ $4.29 est
    with pytest.raises(VultrError, match="exceeds --max-cost"):
        vultr_drill.drill("bare", sshkey_ids=["k"], max_cost=0.50, client=c)
    c.create_instance.assert_not_called()


def test_unknown_kind_raises():
    with pytest.raises(NotImplementedError):
        vultr_drill.drill("wat", sshkey_ids=["k"], client=_mock_client())


def test_spoke_dispatch_runs_validate_then_destroys(monkeypatch):
    c = _mock_client()
    captured = {}

    def fake_validate(ip, name):
        captured["ip"] = ip
        return {"ssh_ready": True, "bootstrap": True, "verify": True, "success": True}

    monkeypatch.setattr(vultr_drill, "_validate_spoke", fake_validate)
    rep = vultr_drill.drill("spoke", sshkey_ids=["k"], client=c)
    assert rep["success"] is True
    assert rep["plan"] == "vc2-1c-2gb"            # fixed spoke plan
    assert captured["ip"] == "1.2.3.4"
    c.destroy.assert_called_once_with("instance", "i-123")  # always destroyed


def test_spoke_failed_verify_still_destroys(monkeypatch):
    c = _mock_client()
    monkeypatch.setattr(
        vultr_drill, "_validate_spoke",
        lambda ip, name: {"bootstrap": True, "verify": False, "success": False},
    )
    rep = vultr_drill.drill("spoke", sshkey_ids=["k"], client=c)
    assert rep["success"] is False
    c.destroy.assert_called_once()                # no orphan even when verify fails
