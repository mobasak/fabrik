"""Unit tests for fabrik.orchestrator.vultr_state (Phase 2).

State file is redirected to a tmp path; no real /opt/fabrik/data writes.
"""

from datetime import UTC, datetime, timedelta

import pytest

from fabrik.orchestrator import vultr_state


@pytest.fixture(autouse=True)
def _tmp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(vultr_state, "STATE_FILE", tmp_path / "vultr-instances.json")
    yield


def test_load_empty_when_missing():
    s = vultr_state.load_state()
    assert s["schema_version"] == 1
    assert s["instances"] == {}
    assert s["last_reconciled"] is None


def test_upsert_and_get_roundtrip():
    vultr_state.upsert_instance("vps4", {"vultr_id": "v-1", "mode": "permanent", "ip": "1.2.3.4"})
    rec = vultr_state.get_instance("vps4")
    assert rec["vultr_id"] == "v-1"
    assert rec["mode"] == "permanent"
    # merge (not overwrite) on second upsert
    vultr_state.upsert_instance("vps4", {"mesh_ip": "10.99.0.4"})
    rec = vultr_state.get_instance("vps4")
    assert rec["vultr_id"] == "v-1" and rec["mesh_ip"] == "10.99.0.4"


def test_atomic_write_produces_valid_json():
    vultr_state.upsert_instance("a", {"vultr_id": "v-a"})
    # reload from disk (fresh read) must parse
    s = vultr_state.load_state()
    assert s["instances"]["a"]["vultr_id"] == "v-a"
    assert vultr_state.STATE_FILE.exists()


def test_mark_destroyed_keeps_record():
    vultr_state.upsert_instance("d1", {"vultr_id": "v-d1", "mode": "disposable"})
    vultr_state.mark_destroyed("d1")
    rec = vultr_state.get_instance("d1")
    assert rec["destroyed_at"] is not None
    assert "d1" not in vultr_state.active_instances()  # excluded from active


def test_gc_old_disposables_drops_only_old_destroyed():
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    recent = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    vultr_state.upsert_instance("old", {"mode": "disposable", "destroyed_at": old})
    vultr_state.upsert_instance("recent", {"mode": "disposable", "destroyed_at": recent})
    vultr_state.upsert_instance("perm", {"mode": "permanent", "destroyed_at": old})  # never gc'd
    removed = vultr_state.gc_old_disposables(retention_days=30)
    assert removed == ["old"]
    names = set(vultr_state.load_state()["instances"])
    assert names == {"recent", "perm"}


class _FakeClient:
    def __init__(self, instances, bare_metals):
        self._i = instances
        self._b = bare_metals

    def list_instances(self):
        return self._i

    def list_bare_metals(self):
        return self._b


def test_reconcile_detects_both_drift_directions():
    # tracked locally: vps4 (live), vps5 (deleted out-of-band)
    vultr_state.upsert_instance("vps4", {"vultr_id": "live-1"})
    vultr_state.upsert_instance("vps5", {"vultr_id": "gone-1"})
    # live: live-1 (matches vps4) + orphan-1 (created out-of-band, untracked)
    client = _FakeClient(
        instances=[{"id": "live-1"}, {"id": "orphan-1"}],
        bare_metals=[],
    )
    rep = vultr_state.reconcile(client)
    assert rep["matched"] == ["vps4"]
    assert rep["in_state_not_live"] == ["vps5"]      # stale local record
    assert rep["in_live_not_state"] == ["orphan-1"]  # untracked live instance
    assert rep["live_count"] == 2
    # last_reconciled stamped
    assert vultr_state.load_state()["last_reconciled"] is not None


def test_reconcile_ignores_destroyed_records():
    vultr_state.upsert_instance("dead", {"vultr_id": "x", "destroyed_at": "2026-01-01T00:00:00+00:00"})
    rep = vultr_state.reconcile(_FakeClient(instances=[], bare_metals=[]))
    assert rep["in_state_not_live"] == []  # destroyed records aren't "drift"
