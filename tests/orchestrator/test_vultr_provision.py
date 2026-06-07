"""Unit tests for fabrik.orchestrator.vultr_provision (Phase 5).

No live infra: VultrClient is a mock; bootstrap script run is patched; state -> tmp.
"""

from unittest.mock import MagicMock

import pytest

from fabrik.drivers.vultr import VultrError
from fabrik.orchestrator import vultr_provision as prov
from fabrik.orchestrator import vultr_state


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(vultr_state, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(prov, "_wg0_used_numbers", lambda: set())  # no real ssh in units
    yield


def _client():
    c = MagicMock()
    c.list_instances.return_value = []
    c.create_instance.return_value = ("instance", {"id": "i-9"})
    c.wait_for_active.return_value = {"main_ip": "9.9.9.9", "status": "active"}
    return c


def test_spoke_number_and_mesh_ip():
    assert prov.spoke_number("vps4") == 4
    assert prov.mesh_ip_for("vps4") == "10.99.0.4"
    with pytest.raises(VultrError):
        prov.spoke_number("vps-drill")     # bad format
    with pytest.raises(VultrError):
        prov.spoke_number("vps1")          # hub reserved (n<2)


def test_next_free_spoke_skips_used():
    vultr_state.upsert_instance("vps2", {"spoke_name": "vps2", "mode": "permanent"})
    c = _client()
    c.list_instances.return_value = [{"label": "vps3"}]
    assert prov.next_free_spoke(c) == "vps4"   # 2 (state) + 3 (live) used -> 4


def test_next_free_spoke_consults_wg0(monkeypatch):
    # existing real spokes on vps1 wg0 (predating state) must be skipped
    monkeypatch.setattr(prov, "_wg0_used_numbers", lambda: {2, 3})
    assert prov.next_free_spoke(_client()) == "vps4"


def test_dry_run_creates_nothing():
    c = _client()
    rep = prov.provision("vps4", sshkey_ids=["k"], region="lhr", dry_run=True, client=c)
    assert rep["dry_run"] and rep["mesh_ip"] == "10.99.0.4"
    c.create_instance.assert_not_called()


def test_provision_requires_confirm():
    c = _client()
    with pytest.raises(VultrError, match="requires explicit confirm"):
        prov.provision("vps4", sshkey_ids=["k"], region="lhr", confirm=False, client=c)
    c.create_instance.assert_not_called()


def test_provision_collision_local_state():
    vultr_state.upsert_instance("vps4", {"mode": "permanent", "spoke_name": "vps4"})
    with pytest.raises(VultrError, match="already tracked"):
        prov.provision("vps4", sshkey_ids=["k"], region="lhr", confirm=True, client=_client())


def test_provision_happy_path_runs_bootstrap_and_records(monkeypatch):
    monkeypatch.setattr(prov, "_run_script", lambda *a, **k: 0)
    c = _client()
    rep = prov.provision("vps4", sshkey_ids=["k"], region="lhr", confirm=True, client=c)
    assert rep["success"] is True and rep["ip"] == "9.9.9.9"
    rec = vultr_state.get_instance("vps4")
    assert rec["mode"] == "permanent" and rec["mesh_ip"] == "10.99.0.4"
    assert rec["bootstrap_completed_at"] is not None


def test_provision_bootstrap_failure_leaves_instance(monkeypatch):
    monkeypatch.setattr(prov, "_run_script", lambda *a, **k: 1)
    c = _client()
    rep = prov.provision("vps4", sshkey_ids=["k"], region="lhr", confirm=True, client=c)
    assert rep["success"] is False
    c.destroy.assert_not_called()                       # permanent: left for inspection
    assert vultr_state.get_instance("vps4")["bootstrap_completed_at"] is None


def test_reverse_fleet_destroy_dry_run_lists_steps():
    vultr_state.upsert_instance("vps4", {"mode": "permanent", "mesh_ip": "10.99.0.4", "vultr_id": "i-9"})
    rep = prov.reverse_fleet_destroy("vps4", dry_run=True, client=_client())
    assert rep["dry_run"]
    joined = " ".join(rep["steps"]).lower()
    assert "gatus" in joined and "wg0" in joined and "instance: destroy" in joined
