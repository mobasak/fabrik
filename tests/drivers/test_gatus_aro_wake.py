"""Tests for `add_aro_wake_endpoint` in drivers/gatus.py.

Added 2026-06-08 alongside the matching Prometheus helper. Writes a
per-spoke `aro-wake-<spoke>.yaml` file under `<GATUS_CONFIG_DIR>/`
matching the live shape verified on vps1.
"""

from __future__ import annotations

import yaml as yaml_lib

from fabrik.drivers import gatus


def test_add_aro_wake_endpoint_writes_per_spoke_file_with_correct_shape(monkeypatch):
    """Endpoint yaml matches the live aro-wake-vps[1-3] entries shape exactly."""
    written_yaml: list[str] = []

    def _fake_ssh(cmd: str, *args, **kwargs) -> str:
        # Idempotency probe -> missing (so write proceeds)
        if "test -f" in cmd:
            return "missing"
        return ""

    def _fake_scp(local_path: str, *args, **kwargs):
        with open(local_path) as f:
            written_yaml.append(f.read())

    monkeypatch.setattr(gatus, "ssh", _fake_ssh)
    monkeypatch.setattr(gatus, "scp_to_vps", _fake_scp)

    r = gatus.add_aro_wake_endpoint("vps4", "10.99.0.4")
    assert r == {"status": "created", "endpoint": "aro-wake-vps4"}

    parsed = yaml_lib.safe_load(written_yaml[0])
    [ep] = parsed["endpoints"]
    assert ep["name"] == "aro-wake-vps4"
    assert ep["group"] == "trio-aro-wake"
    assert ep["url"] == "http://10.99.0.4:8201/health"
    assert ep["interval"] == "60s"
    assert ep["conditions"] == [
        "[STATUS] == 200",
        "[BODY].ok == true",
        "[BODY].host == vps4",
    ]
    assert ep["alerts"][0]["failure-threshold"] == gatus.DEFAULT_FAILURE_THRESHOLD


def test_add_aro_wake_endpoint_idempotent_when_file_exists(monkeypatch):
    """If the spoke's per-spoke file already exists -> exists status, no scp, no restart."""
    scp_calls: list[bool] = []

    def _fake_ssh(cmd: str, *args, **kwargs) -> str:
        if "test -f" in cmd:
            return "exists"
        return ""

    def _fake_scp(*a, **k):
        scp_calls.append(True)

    monkeypatch.setattr(gatus, "ssh", _fake_ssh)
    monkeypatch.setattr(gatus, "scp_to_vps", _fake_scp)

    r = gatus.add_aro_wake_endpoint("vps4", "10.99.0.4")
    assert r["status"] == "exists"
    assert scp_calls == []


def test_add_aro_wake_endpoint_dry_run_does_not_touch_vps(monkeypatch):
    """dry_run=True must not SSH or scp."""

    def _fail(*a, **k):
        raise AssertionError("must not touch the VPS in dry-run")

    monkeypatch.setattr(gatus, "ssh", _fail)
    monkeypatch.setattr(gatus, "scp_to_vps", _fail)
    r = gatus.add_aro_wake_endpoint("vps4", "10.99.0.4", dry_run=True)
    assert r == {"status": "dry_run", "endpoint": "aro-wake-vps4"}


def test_gatus_uses_bare_container_name_pattern_for_restart():
    """Same Coolify-era stale-pattern check as the prom test:
    `^gatus-` was a bare prefix that no-matched the current `gatus` container.
    """
    from inspect import getsource

    src = getsource(gatus)
    # We added 3 call sites that all need the fix.
    assert src.count("'^gatus(-|$)'") + src.count('"^gatus(-|$)"') >= 3
    # No remnant of the broken prefix-only pattern.
    assert "'^gatus-'" not in src and '"^gatus-"' not in src
