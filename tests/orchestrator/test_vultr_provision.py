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
    monkeypatch.setattr(prov, "_wait_for_ssh", lambda *a, **k: True)
    # `_register_observability` SSHes to vps1 to read/write prometheus.yml +
    # writes a gatus YAML — block at the orchestrator boundary so unit tests
    # stay hermetic. (Caught live 2026-06-08 when an earlier draft side-
    # effected vps1: a real aro-wake-vps4 endpoint file got created and the
    # aro-wake job got a vps4 static_config entry, which then took manual
    # cleanup on the hub. Direct prom/gatus driver tests cover the real path.)
    monkeypatch.setattr(prov, "_register_observability", lambda *a, **k: None)
    c = _client()
    rep = prov.provision("vps4", sshkey_ids=["k"], region="lhr", confirm=True, client=c)
    assert rep["success"] is True and rep["ip"] == "9.9.9.9"
    rec = vultr_state.get_instance("vps4")
    assert rec["mode"] == "permanent" and rec["mesh_ip"] == "10.99.0.4"
    assert rec["bootstrap_completed_at"] is not None


def test_provision_registers_observability_after_bootstrap_success(monkeypatch):
    """Happy path: provision wires the spoke into Prometheus + Gatus.

    Mocks the driver-level registrars (they SSH to vps1 in production).
    What we assert is the wiring: both registrars get called with the
    right (spoke, mesh_ip) pair AFTER bootstrap succeeds, and the report
    surfaces what happened under `observability`.
    """
    monkeypatch.setattr(prov, "_run_script", lambda *a, **k: 0)
    monkeypatch.setattr(prov, "_wait_for_ssh", lambda *a, **k: True)

    prom_calls: list[tuple[str, str]] = []
    gatus_calls: list[tuple[str, str]] = []
    import sys
    import types

    fake_prom = types.ModuleType("fabrik.drivers.prometheus")

    def _fake_add_aro_wake_target(name, mesh_ip, *, dry_run=False):
        prom_calls.append((name, mesh_ip))
        return {"status": "created", "target": f"{mesh_ip}:8201"}

    fake_prom.add_aro_wake_target = _fake_add_aro_wake_target  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.prometheus", fake_prom)

    fake_gatus = types.ModuleType("fabrik.drivers.gatus")

    def _fake_add_aro_wake_endpoint(name, mesh_ip, *, dry_run=False):
        gatus_calls.append((name, mesh_ip))
        return {"status": "created", "endpoint": f"aro-wake-{name}"}

    fake_gatus.add_aro_wake_endpoint = _fake_add_aro_wake_endpoint  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.gatus", fake_gatus)

    rep = prov.provision("vps4", sshkey_ids=["k"], region="lhr", confirm=True, client=_client())
    assert rep["success"] is True
    assert prom_calls == [("vps4", "10.99.0.4")]
    assert gatus_calls == [("vps4", "10.99.0.4")]
    assert rep["observability"]["prometheus"] == "created"
    assert rep["observability"]["gatus"] == "created"


def test_provision_observability_errors_are_logged_not_fatal(monkeypatch):
    """If Prometheus or Gatus registration raises, provision still reports success.

    The instance + bootstrap are live; missing observability is a
    re-drivable post-deploy concern, not a reason to mark the whole
    provision a failure (the operator can re-register after).
    """
    monkeypatch.setattr(prov, "_run_script", lambda *a, **k: 0)
    monkeypatch.setattr(prov, "_wait_for_ssh", lambda *a, **k: True)
    import sys
    import types

    fake_prom = types.ModuleType("fabrik.drivers.prometheus")

    def _boom(*a, **k):
        raise RuntimeError("aro-wake job not present in prometheus.yml")

    fake_prom.add_aro_wake_target = _boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.prometheus", fake_prom)

    fake_gatus = types.ModuleType("fabrik.drivers.gatus")
    fake_gatus.add_aro_wake_endpoint = lambda *a, **k: {"status": "created"}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.gatus", fake_gatus)

    rep = prov.provision("vps4", sshkey_ids=["k"], region="lhr", confirm=True, client=_client())
    assert rep["success"] is True
    assert "error" in rep["observability"]["prometheus"]
    assert "aro-wake job not present" in rep["observability"]["prometheus"]


def test_provision_bootstrap_failure_leaves_instance(monkeypatch):
    monkeypatch.setattr(prov, "_run_script", lambda *a, **k: 1)
    monkeypatch.setattr(prov, "_wait_for_ssh", lambda *a, **k: True)
    c = _client()
    rep = prov.provision("vps4", sshkey_ids=["k"], region="lhr", confirm=True, client=c)
    assert rep["success"] is False
    c.destroy.assert_not_called()                       # permanent: left for inspection
    assert vultr_state.get_instance("vps4")["bootstrap_completed_at"] is None


def test_provision_ssh_never_comes_up_leaves_instance(monkeypatch):
    """When sshd never binds within the timeout, leave the instance + return error.

    Regression for the 2026-06-08 live failure: Vultr API returned active
    before cloud-init had finished binding sshd, so bootstrap-vps.sh's
    preflight hit "cannot SSH" on the first try (BatchMode=yes, no retries).
    `_wait_for_ssh()` polls between active and bootstrap. When the poll
    times out, provision must abort cleanly (instance LEFT for inspection,
    no bootstrap attempted) rather than fall through to the bootstrap with
    a known-unreachable host.
    """
    bootstrap_called: list[bool] = []
    monkeypatch.setattr(prov, "_run_script", lambda *a, **k: bootstrap_called.append(True) or 0)
    monkeypatch.setattr(prov, "_wait_for_ssh", lambda *a, **k: False)
    c = _client()
    rep = prov.provision("vps4", sshkey_ids=["k"], region="lhr", confirm=True, client=c)
    assert rep["success"] is False
    assert "sshd never came up" in (rep.get("error") or "")
    assert bootstrap_called == []                         # bootstrap MUST NOT run
    c.destroy.assert_not_called()                         # permanent: left for inspection


def test_reverse_fleet_destroy_dry_run_lists_steps():
    vultr_state.upsert_instance("vps4", {"mode": "permanent", "mesh_ip": "10.99.0.4", "vultr_id": "i-9"})
    rep = prov.reverse_fleet_destroy("vps4", dry_run=True, client=_client())
    assert rep["dry_run"]
    joined = " ".join(rep["steps"]).lower()
    assert "gatus" in joined and "wg0" in joined and "instance: destroy" in joined


def test_reverse_fleet_destroy_wg_peer_strips_conf_block_via_marker(monkeypatch):
    """G3: peer cleanup must touch BOTH the runtime kernel state AND
    /etc/wireguard/wg0.conf — keyed on step_06's `# === peer: <name> ` marker.
    Importantly: must NOT use `wg-quick save wg0`, which round-trips through
    `wg showconf` and would strip the hub's wg-quick extensions
    (`[Interface]` `PostUp` MSS-clamp) — verified live on vps1's wg0.conf.
    """
    vultr_state.upsert_instance(
        "vps4", {"mode": "permanent", "mesh_ip": "10.99.0.4", "vultr_id": "i-9"}
    )

    import sys
    import types

    fake_prom = types.ModuleType("fabrik.drivers.prometheus")
    fake_prom.remove_aro_wake_target = lambda *a, **k: True  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.prometheus", fake_prom)
    fake_gatus = types.ModuleType("fabrik.drivers.gatus")
    fake_gatus.remove_endpoint = lambda *a, **k: True  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.gatus", fake_gatus)
    fake_backrest = types.ModuleType("fabrik.drivers.backrest")
    fake_backrest.remove_backup_plan = lambda *a, **k: True  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.backrest", fake_backrest)
    fake_dns_mod = types.ModuleType("fabrik.drivers.dns")

    class _FakeDNSClient:
        def delete_record(self, *a, **k):
            return {"status": "ok"}

    fake_dns_mod.DNSClient = _FakeDNSClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.dns", fake_dns_mod)

    ssh_calls: list[str] = []

    def _fake_ssh(cmd: str, *args, **kwargs) -> str:
        ssh_calls.append(cmd)
        # First call is the pubkey lookup; return a fake pubkey so the
        # runtime-remove path runs too.
        if "wg show wg0 allowed-ips" in cmd:
            return "FAKEPUBKEY=\n"
        return ""

    fake_ssh_mod = types.ModuleType("fabrik.drivers.ssh")
    fake_ssh_mod.ssh = _fake_ssh  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.ssh", fake_ssh_mod)

    prov.reverse_fleet_destroy("vps4", client=_client())

    joined = "\n".join(ssh_calls)
    # MUST: runtime remove + targeted conf edit + marker text
    assert "wg set wg0 peer FAKEPUBKEY= remove" in joined
    assert "/etc/wireguard/wg0.conf" in joined
    assert "# === peer: vps4 " in joined
    # MUST NOT: the conf-stripping `wg-quick save` round-trip
    assert "wg-quick save" not in joined


def test_reverse_fleet_destroy_calls_aro_wake_remover_not_generic_scrape(monkeypatch):
    """G1 wiring: destroy must call `remove_aro_wake_target` (the spoke-shaped
    remover), NOT `remove_scrape_target` (which only matches `fabrik-<name>`
    jobs that this code path never creates). The old wiring was symmetric-
    looking but a no-op: it tried to remove a job that was never added.
    """
    vultr_state.upsert_instance(
        "vps4", {"mode": "permanent", "mesh_ip": "10.99.0.4", "vultr_id": "i-9"}
    )

    import sys
    import types

    aro_wake_calls: list[str] = []
    generic_calls: list[str] = []

    fake_prom = types.ModuleType("fabrik.drivers.prometheus")

    def _fake_remove_aro(name, *, dry_run=False):
        aro_wake_calls.append(name)
        return True

    def _fake_remove_generic(name, *, dry_run=False):
        generic_calls.append(name)
        return True

    fake_prom.remove_aro_wake_target = _fake_remove_aro  # type: ignore[attr-defined]
    fake_prom.remove_scrape_target = _fake_remove_generic  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.prometheus", fake_prom)

    fake_gatus = types.ModuleType("fabrik.drivers.gatus")
    fake_gatus.remove_endpoint = lambda *a, **k: True  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.gatus", fake_gatus)

    fake_backrest = types.ModuleType("fabrik.drivers.backrest")
    fake_backrest.remove_backup_plan = lambda *a, **k: True  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.backrest", fake_backrest)

    fake_dns_mod = types.ModuleType("fabrik.drivers.dns")

    class _FakeDNSClient:
        def delete_record(self, *a, **k):
            return {"status": "ok"}

    fake_dns_mod.DNSClient = _FakeDNSClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.dns", fake_dns_mod)

    fake_ssh_mod = types.ModuleType("fabrik.drivers.ssh")
    fake_ssh_mod.ssh = lambda *a, **k: ""  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.ssh", fake_ssh_mod)

    prov.reverse_fleet_destroy("vps4", client=_client())
    assert aro_wake_calls == ["vps4"]
    assert generic_calls == []                              # NEVER call the generic remover
