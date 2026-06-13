"""Tests for the aro-wake target helpers in drivers/prometheus.py.

Added 2026-06-08 after the live vps4 drill surfaced that `fabrik vultr
provision` left the new spoke invisible to Prometheus. The helpers below
graft the spoke into the SHARED `aro-wake` job's `static_configs` list
(NOT a new `fabrik-<spoke>` job).
"""

from __future__ import annotations

import pytest

from fabrik.drivers import prometheus as prom


def _base_config_with_aro_wake() -> dict:
    """Mirror the live shape verified 2026-06-08 on vps1's prometheus.yml."""
    return {
        "scrape_configs": [
            {
                "job_name": "aro-wake",
                "metrics_path": "/metrics",
                "scheme": "http",
                "static_configs": [
                    {"targets": ["10.0.1.1:8201"], "labels": {"host": "vps1", "role": "hub"}},
                    {"targets": ["10.99.0.2:8201"], "labels": {"host": "vps2", "role": "spoke"}},
                    {"targets": ["10.99.0.3:8201"], "labels": {"host": "vps3", "role": "spoke"}},
                ],
            },
            {"job_name": "cadvisor", "static_configs": [{"targets": ["cadvisor:8080"]}]},
        ]
    }


def test_add_aro_wake_target_appends_spoke_entry(monkeypatch):
    cfg = _base_config_with_aro_wake()
    written: list[dict] = []
    reload_called: list[bool] = []

    monkeypatch.setattr(prom, "_read_config", lambda: cfg)
    monkeypatch.setattr(prom, "_write_config", lambda d: written.append(d))
    monkeypatch.setattr(prom, "_reload_prometheus", lambda: reload_called.append(True) or True)

    r = prom.add_aro_wake_target("vps4", "10.99.0.4")
    assert r["status"] == "created"
    assert r["target"] == "10.99.0.4:8201"
    assert reload_called == [True]
    # Last static_configs entry should be the new spoke
    job = next(j for j in written[0]["scrape_configs"] if j["job_name"] == "aro-wake")
    last = job["static_configs"][-1]
    assert last["targets"] == ["10.99.0.4:8201"]
    assert last["labels"] == {"host": "vps4", "role": "spoke"}


def test_add_aro_wake_target_idempotent(monkeypatch):
    """If the spoke target is already in static_configs, no rewrite + no reload."""
    cfg = _base_config_with_aro_wake()
    cfg["scrape_configs"][0]["static_configs"].append(
        {"targets": ["10.99.0.4:8201"], "labels": {"host": "vps4", "role": "spoke"}}
    )
    write_count: list[bool] = []
    reload_count: list[bool] = []
    monkeypatch.setattr(prom, "_read_config", lambda: cfg)
    monkeypatch.setattr(prom, "_write_config", lambda d: write_count.append(True))
    monkeypatch.setattr(prom, "_reload_prometheus", lambda: reload_count.append(True) or True)

    r = prom.add_aro_wake_target("vps4", "10.99.0.4")
    assert r["status"] == "exists"
    assert write_count == []
    assert reload_count == []


def test_add_aro_wake_target_dry_run_does_not_read_config(monkeypatch):
    """Dry run is purely a log + return; must NOT touch the VPS."""
    read_count: list[bool] = []

    def _no_read():
        read_count.append(True)
        return {}

    monkeypatch.setattr(prom, "_read_config", _no_read)
    monkeypatch.setattr(prom, "_write_config", lambda d: pytest.fail("must not write in dry-run"))
    r = prom.add_aro_wake_target("vps4", "10.99.0.4", dry_run=True)
    assert r["status"] == "dry_run"
    assert read_count == []


def test_add_aro_wake_target_raises_when_job_missing(monkeypatch):
    """No `aro-wake` job in scrape_configs -> caller-visible error,
    not a silent append-as-new-job."""
    monkeypatch.setattr(prom, "_read_config", lambda: {"scrape_configs": []})
    with pytest.raises(RuntimeError, match="aro-wake job not present"):
        prom.add_aro_wake_target("vps4", "10.99.0.4")


def test_remove_aro_wake_target_by_host_label(monkeypatch):
    """Removal matches on labels.host (not target IP) so a mid-life IP
    rotation between provision and destroy still cleans correctly."""
    cfg = _base_config_with_aro_wake()
    # Pretend vps4 was added but with a different IP than mesh_ip_for() would compute
    cfg["scrape_configs"][0]["static_configs"].append(
        {"targets": ["10.99.0.99:8201"], "labels": {"host": "vps4", "role": "spoke"}}
    )
    written: list[dict] = []
    monkeypatch.setattr(prom, "_read_config", lambda: cfg)
    monkeypatch.setattr(prom, "_write_config", lambda d: written.append(d))
    monkeypatch.setattr(prom, "_reload_prometheus", lambda: True)

    assert prom.remove_aro_wake_target("vps4") is True
    job = next(j for j in written[0]["scrape_configs"] if j["job_name"] == "aro-wake")
    hosts = [(sc.get("labels") or {}).get("host") for sc in job["static_configs"]]
    assert hosts == ["vps1", "vps2", "vps3"]                  # vps4 stripped


def test_remove_aro_wake_target_no_match_is_noop(monkeypatch):
    """No vps4 entry to remove -> True (idempotent) + no write + no reload."""
    cfg = _base_config_with_aro_wake()
    write_count: list[bool] = []
    reload_count: list[bool] = []
    monkeypatch.setattr(prom, "_read_config", lambda: cfg)
    monkeypatch.setattr(prom, "_write_config", lambda d: write_count.append(True))
    monkeypatch.setattr(prom, "_reload_prometheus", lambda: reload_count.append(True) or True)

    assert prom.remove_aro_wake_target("vps4") is True
    assert write_count == []
    assert reload_count == []


def test_reload_prometheus_uses_bare_container_name_pattern():
    """Coolify-era pattern `^alertmanager-` no-matched today's bare container
    names. The fix uses `^alertmanager(-|$)` — both shapes match.
    """
    # Look at the source text so the test fails loudly if a future edit
    # reverts to the broken Coolify-prefix-only regex.
    from inspect import getsource

    src = getsource(prom._reload_prometheus)
    assert "'^alertmanager(-|$)'" in src or '"^alertmanager(-|$)"' in src
    assert "'^prometheus(-|$)'" in src or '"^prometheus(-|$)"' in src
    assert "'^alertmanager-'" not in src                   # no bare prefix-only
    assert "'^prometheus-'" not in src


def test_write_config_mirrors_to_git_after_vps_write(monkeypatch, tmp_path):
    """Dual-write: `_write_config` ships the same body to both vps1 (via scp+ssh)
    AND the local source-controlled mirror at `configs/prometheus/prometheus.yml`.

    Regression for the 2026-06-13 drift audit: until that day, the driver wrote
    to vps1 LIVE only, never to git, so `configs/prometheus/prometheus.yml`
    silently rotted for an unknown number of weeks (md5 mismatch verified live).
    """
    # Point the mirror at a tmpdir so the test doesn't touch the real repo
    fake_mirror = tmp_path / "configs" / "prometheus" / "prometheus.yml"
    monkeypatch.setattr(prom, "_LOCAL_PROMETHEUS_CONFIG_PATH", fake_mirror)

    # Mock the runtime path so no real SSH happens
    scp_calls: list[tuple[str, str]] = []
    ssh_calls: list[str] = []
    monkeypatch.setattr(
        prom,
        "scp_to_vps",
        lambda src, dst, **kw: scp_calls.append((src, dst)),
    )
    monkeypatch.setattr(prom, "ssh", lambda cmd, **kw: ssh_calls.append(cmd) or "")

    cfg = {"scrape_configs": [{"job_name": "demo", "static_configs": [{"targets": ["x:1"]}]}]}
    prom._write_config(cfg)

    # vps1 leg: scp staged + sudo mv into PROMETHEUS_CONFIG_PATH ran
    assert len(scp_calls) == 1
    assert scp_calls[0][1] == "/tmp/prometheus.yml.staged"
    assert any("sudo mv" in c and prom.PROMETHEUS_CONFIG_PATH in c for c in ssh_calls)

    # Git mirror leg: file exists, contains the same YAML body
    assert fake_mirror.exists()
    import yaml as yaml_lib
    parsed = yaml_lib.safe_load(fake_mirror.read_text())
    assert parsed["scrape_configs"][0]["job_name"] == "demo"


def test_write_config_does_not_raise_when_mirror_write_fails(monkeypatch, tmp_path):
    """Git mirror is best-effort: read-only FS, missing dir, etc. must NOT
    break the runtime write — vps1 is the source of truth at runtime."""
    # Point mirror at a path whose parent CAN'T be created (file in the way)
    blocker = tmp_path / "configs"
    blocker.write_text("not a directory")          # parent path is a file
    fake_mirror = blocker / "prometheus.yml"
    monkeypatch.setattr(prom, "_LOCAL_PROMETHEUS_CONFIG_PATH", fake_mirror)
    monkeypatch.setattr(prom, "scp_to_vps", lambda *a, **k: None)
    monkeypatch.setattr(prom, "ssh", lambda *a, **k: "")

    # Must not raise even though the mirror parent is unwriteable
    prom._write_config({"scrape_configs": []})
