"""Coverage for fabrik.orchestrator.gpu_state (hermetic: tmp_path state file, no-op lock)."""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime, timedelta

import pytest

from fabrik.orchestrator import gpu_state


@pytest.fixture(autouse=True)
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "data" / "gpu-rent-state.json"
    monkeypatch.setattr(gpu_state, "STATE_FILE", path)

    @contextlib.contextmanager
    def _noop_lock(name, timeout_seconds=0.0):
        yield

    monkeypatch.setattr(gpu_state, "file_lock", _noop_lock)
    return path


def _mk(sid="s1", **kw):
    args = dict(
        provider="runpod",
        kind="pod-h100",
        workload="w",
        resource_type="pod",
        resource_id="pod-1",
        gpu_type_id="H100",
        max_lifetime_hours=4,
        cost_estimate_usd=12.0,
    )
    args.update(kw)
    return gpu_state.upsert(sid, **args)


class FakeClient:
    def __init__(self, pods=(), endpoints=()):
        self._pods = list(pods)
        self._eps = list(endpoints)

    def list_pods(self):
        return self._pods

    def list_endpoints(self):
        return self._eps


# ---- load / save ----------------------------------------------------------


def test_load_missing_returns_empty(state_file):
    st = gpu_state.load_state()
    assert st == {"schema_version": 1, "last_reconciled": None, "sessions": {}}


def test_load_corrupt_returns_empty_and_warns(state_file, caplog):
    state_file.parent.mkdir(parents=True)
    state_file.write_text("{not json")
    with caplog.at_level(logging.WARNING):
        st = gpu_state.load_state()
    assert st["sessions"] == {}
    assert "corrupt" in caplog.text


def test_load_unreadable_returns_empty(state_file):
    state_file.parent.mkdir(parents=True)
    state_file.mkdir()  # a directory in place of the file -> OSError on read
    assert gpu_state.load_state()["sessions"] == {}


def test_load_fills_missing_keys(state_file):
    state_file.parent.mkdir(parents=True)
    state_file.write_text(json.dumps({}))
    st = gpu_state.load_state()
    assert st == {"schema_version": 1, "last_reconciled": None, "sessions": {}}


def test_load_preserves_newer_schema(state_file):
    state_file.parent.mkdir(parents=True)
    state_file.write_text(json.dumps({"schema_version": 9, "sessions": {"a": {}}}))
    st = gpu_state.load_state()
    assert st["schema_version"] == 9
    assert "a" in st["sessions"]


@pytest.mark.xfail(strict=True, reason="gpu_state.py:81-82 non-dict JSON (list) raises TypeError instead of falling back to empty")
def test_load_non_dict_json_is_treated_as_corrupt(state_file):
    state_file.parent.mkdir(parents=True)
    state_file.write_text("[1, 2]")
    assert gpu_state.load_state()["sessions"] == {}


def test_save_state_roundtrip_and_creates_parent(state_file):
    st = {"schema_version": 1, "last_reconciled": None, "sessions": {"x": {"a": 1}}}
    assert gpu_state.save_state(st) == state_file
    assert json.loads(state_file.read_text()) == st
    # no temp files left behind
    assert [p.name for p in state_file.parent.iterdir()] == [state_file.name]


def test_write_failure_cleans_tmp_and_reraises(state_file, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("replace failed")

    monkeypatch.setattr(gpu_state.os, "replace", boom)
    with pytest.raises(RuntimeError):
        gpu_state.save_state(gpu_state._empty())
    assert list(state_file.parent.iterdir()) == []


# ---- upsert ---------------------------------------------------------------


def test_upsert_record_shape_and_persisted():
    rec = _mk(max_lifetime_hours=2)
    assert rec["destroyed_at"] is None
    assert rec["destroy_pending"] is False
    assert rec["cost_actual_usd"] is None
    assert rec["provider"] == "runpod"
    created = datetime.fromisoformat(rec["created_at"])
    expires = datetime.fromisoformat(rec["expires_at"])
    assert expires - created == timedelta(hours=2)
    assert gpu_state.get_session("s1") == rec


def test_upsert_overwrites_same_id_and_keeps_others():
    _mk("a", resource_id="p1")
    _mk("b", resource_id="p2")
    _mk("a", resource_id="p3")
    st = gpu_state.load_state()
    assert st["sessions"]["a"]["resource_id"] == "p3"
    assert st["sessions"]["b"]["resource_id"] == "p2"


def test_upsert_fractional_lifetime_and_null_gpu():
    rec = _mk(max_lifetime_hours=0.5, gpu_type_id=None)
    assert rec["gpu_type_id"] is None
    delta = datetime.fromisoformat(rec["expires_at"]) - datetime.fromisoformat(rec["created_at"])
    assert delta == timedelta(minutes=30)


# ---- mark_* ---------------------------------------------------------------


def test_mark_destroyed_sets_fields_and_clears_pending():
    _mk()
    gpu_state.mark_destroy_pending("s1")
    gpu_state.mark_destroyed("s1", when="2026-01-01T00:00:00+00:00", cost_actual_usd=3.5)
    rec = gpu_state.get_session("s1")
    assert rec["destroyed_at"] == "2026-01-01T00:00:00+00:00"
    assert rec["destroy_pending"] is False
    assert rec["cost_actual_usd"] == 3.5


def test_mark_destroyed_defaults_now_and_keeps_cost():
    _mk()
    gpu_state.mark_destroyed("s1")
    rec = gpu_state.get_session("s1")
    datetime.fromisoformat(rec["destroyed_at"])
    assert rec["cost_actual_usd"] is None


def test_mark_destroyed_zero_cost_is_recorded():
    _mk()
    gpu_state.mark_destroyed("s1", cost_actual_usd=0.0)
    assert gpu_state.get_session("s1")["cost_actual_usd"] == 0.0


@pytest.mark.parametrize(
    "fn,args",
    [
        (gpu_state.mark_destroyed, ()),
        (gpu_state.mark_destroy_pending, ()),
        (gpu_state.mark_paused, ()),
        (gpu_state.mark_resumed, ()),
        (gpu_state.record_actual_cost, (1.0,)),
    ],
)
def test_unknown_session_warns_and_does_not_write(fn, args, state_file, caplog):
    with caplog.at_level(logging.WARNING):
        fn("ghost", *args)
    assert "unknown session ghost" in caplog.text
    assert not state_file.exists()


def test_mark_destroy_pending_sets_flag():
    _mk()
    gpu_state.mark_destroy_pending("s1")
    assert gpu_state.get_session("s1")["destroy_pending"] is True


def test_pause_resume_cycle():
    _mk()
    gpu_state.mark_paused("s1")
    rec = gpu_state.get_session("s1")
    assert "paused_at" in rec and "resumed_at" not in rec
    gpu_state.mark_resumed("s1")
    rec = gpu_state.get_session("s1")
    assert "resumed_at" in rec and "paused_at" not in rec
    gpu_state.mark_paused("s1")
    rec = gpu_state.get_session("s1")
    assert "paused_at" in rec and "resumed_at" not in rec


def test_pause_twice_latest_wins(monkeypatch):
    _mk()
    gpu_state.mark_paused("s1")
    first = gpu_state.get_session("s1")["paused_at"]
    gpu_state.mark_paused("s1")
    assert gpu_state.get_session("s1")["paused_at"] >= first


def test_record_actual_cost():
    _mk()
    gpu_state.record_actual_cost("s1", 7.25)
    assert gpu_state.get_session("s1")["cost_actual_usd"] == 7.25


# ---- queries --------------------------------------------------------------


def test_get_session_missing_is_none():
    assert gpu_state.get_session("nope") is None


def test_active_sessions_excludes_destroyed():
    _mk("a")
    _mk("b", resource_id="p2")
    gpu_state.mark_destroyed("a")
    assert set(gpu_state.active_sessions()) == {"b"}


def test_active_sessions_includes_destroy_pending():
    _mk("a")
    gpu_state.mark_destroy_pending("a")
    assert "a" in gpu_state.active_sessions()


# ---- gc_old ---------------------------------------------------------------


def test_gc_old_removes_only_old_destroyed():
    now = datetime.now(UTC)
    _mk("old", resource_id="1")
    _mk("recent", resource_id="2")
    _mk("live", resource_id="3")
    gpu_state.mark_destroyed("old", when=(now - timedelta(days=31)).isoformat())
    gpu_state.mark_destroyed("recent", when=(now - timedelta(days=5)).isoformat())
    assert gpu_state.gc_old() == ["old"]
    assert set(gpu_state.load_state()["sessions"]) == {"recent", "live"}


def test_gc_old_custom_retention():
    now = datetime.now(UTC)
    _mk("a")
    gpu_state.mark_destroyed("a", when=(now - timedelta(days=2)).isoformat())
    assert gpu_state.gc_old(retention_days=1) == ["a"]


def test_gc_old_skips_bad_timestamp_and_no_write_when_nothing_removed(state_file):
    _mk("bad")
    gpu_state.mark_destroyed("bad", when="not-a-date")
    before = state_file.read_text()
    assert gpu_state.gc_old() == []
    assert state_file.read_text() == before
    assert "bad" in gpu_state.load_state()["sessions"]


# ---- reconcile ------------------------------------------------------------


def _expire(sid):
    st = gpu_state.load_state()
    st["sessions"][sid]["expires_at"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    gpu_state.save_state(st)


def test_reconcile_clean():
    _mk("a", resource_id="p1")
    rep = gpu_state.reconcile(FakeClient(pods=[{"id": "p1"}]))
    assert rep["in_state_not_live"] == []
    assert rep["lifetime_exceeded"] == []
    assert rep["destroy_pending"] == []
    assert rep["orphan_pods"] == []
    assert rep["foreign_count"] == 0


def test_reconcile_in_state_not_live_pod_and_endpoint():
    _mk("a", resource_id="p1")
    _mk("b", resource_type="endpoint", resource_id="e1")
    rep = gpu_state.reconcile(FakeClient())
    assert {"session_id": "a", "resource_id": "p1", "type": "pod"} in rep["in_state_not_live"]
    assert {"session_id": "b", "resource_id": "e1", "type": "endpoint"} in rep["in_state_not_live"]


def test_reconcile_ignores_destroyed():
    _mk("a")
    gpu_state.mark_destroyed("a")
    rep = gpu_state.reconcile(FakeClient())
    assert rep["in_state_not_live"] == []


def test_reconcile_lifetime_exceeded():
    _mk("a", resource_id="p1")
    _expire("a")
    rep = gpu_state.reconcile(FakeClient(pods=[{"id": "p1"}]))
    assert rep["lifetime_exceeded"] == [{"session_id": "a", "resource_id": "p1", "type": "pod"}]


def test_reconcile_bad_expiry_is_skipped():
    _mk("a", resource_id="p1")
    st = gpu_state.load_state()
    st["sessions"]["a"]["expires_at"] = "garbage"
    gpu_state.save_state(st)
    rep = gpu_state.reconcile(FakeClient(pods=[{"id": "p1"}]))
    assert rep["lifetime_exceeded"] == []


def test_reconcile_missing_expiry_key_is_skipped():
    _mk("a", resource_id="p1")
    st = gpu_state.load_state()
    del st["sessions"]["a"]["expires_at"]
    gpu_state.save_state(st)
    rep = gpu_state.reconcile(FakeClient(pods=[{"id": "p1"}]))
    assert rep["lifetime_exceeded"] == []


def test_reconcile_destroy_pending():
    _mk("a", resource_id="p1")
    gpu_state.mark_destroy_pending("a")
    rep = gpu_state.reconcile(FakeClient(pods=[{"id": "p1"}]))
    assert rep["destroy_pending"] == [{"session_id": "a", "resource_id": "p1", "type": "pod"}]


def test_reconcile_orphans_and_foreign():
    rep = gpu_state.reconcile(
        FakeClient(
            pods=[
                {"id": "o1", "env": {"FABRIK_SESSION_ID": "sx"}},
                {"id": "f1", "env": {}},
                {"id": "f2"},
                {"id": "f3", "env": None},
            ],
            endpoints=[
                {"id": "oe", "env": {"FABRIK_SESSION_ID": "sy"}},
                {"id": "fe"},
            ],
        )
    )
    assert rep["orphan_pods"] == [{"resource_id": "o1", "fabrik_session_id": "sx"}]
    assert rep["orphan_endpoints"] == [{"resource_id": "oe", "fabrik_session_id": "sy"}]
    assert rep["foreign_count"] == 4


def test_reconcile_tracked_live_not_orphan_or_foreign():
    _mk("a", resource_id="p1")
    _mk("b", resource_type="endpoint", resource_id="e1")
    rep = gpu_state.reconcile(
        FakeClient(pods=[{"id": "p1"}], endpoints=[{"id": "e1"}])
    )
    assert rep["orphan_pods"] == [] and rep["orphan_endpoints"] == []
    assert rep["foreign_count"] == 0


def test_reconcile_destroyed_session_makes_live_pod_orphan():
    _mk("a", resource_id="p1")
    gpu_state.mark_destroyed("a")
    rep = gpu_state.reconcile(FakeClient(pods=[{"id": "p1", "env": {"FABRIK_SESSION_ID": "a"}}]))
    assert [o["resource_id"] for o in rep["orphan_pods"]] == ["p1"]


def test_reconcile_provider_scoping():
    _mk("rp", provider="runpod", resource_id="p1")
    _mk("md", provider="modal", resource_id="m1")
    _expire("md")
    gpu_state.mark_destroy_pending("md")
    rep = gpu_state.reconcile(FakeClient(), provider="runpod")
    assert [r["session_id"] for r in rep["in_state_not_live"]] == ["rp"]
    assert rep["lifetime_exceeded"] == []
    assert rep["destroy_pending"] == []


def test_reconcile_provider_none_checks_all():
    _mk("rp", provider="runpod", resource_id="p1")
    _mk("md", provider="modal", resource_id="m1")
    rep = gpu_state.reconcile(FakeClient())
    assert {r["session_id"] for r in rep["in_state_not_live"]} == {"rp", "md"}


def test_reconcile_legacy_entry_without_provider_defaults_runpod():
    _mk("a", resource_id="p1")
    st = gpu_state.load_state()
    del st["sessions"]["a"]["provider"]
    gpu_state.save_state(st)
    rep = gpu_state.reconcile(FakeClient(), provider="runpod")
    assert len(rep["in_state_not_live"]) == 1
    rep = gpu_state.reconcile(FakeClient(), provider="modal")
    assert rep["in_state_not_live"] == []


def test_reconcile_other_provider_pod_with_same_id_not_tracked_for_orphans():
    # Modal session tracks p1; a runpod scan sees live p1 with a tag -> orphan for runpod scope.
    _mk("md", provider="modal", resource_id="p1")
    rep = gpu_state.reconcile(
        FakeClient(pods=[{"id": "p1", "env": {"FABRIK_SESSION_ID": "md"}}]), provider="runpod"
    )
    assert [o["resource_id"] for o in rep["orphan_pods"]] == ["p1"]


def test_reconcile_stamps_last_reconciled_and_report_time():
    rep = gpu_state.reconcile(FakeClient())
    st = gpu_state.load_state()
    assert st["last_reconciled"] == rep["scanned_at"]


def test_reconcile_is_read_only_for_sessions():
    _mk("a", resource_id="p1")
    _expire("a")
    before = gpu_state.load_state()["sessions"]
    gpu_state.reconcile(FakeClient())
    assert gpu_state.load_state()["sessions"] == before
