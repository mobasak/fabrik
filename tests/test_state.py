"""Tests for fabrik.state — save/load/archive_destroyed round-trip.

Uses a tmp dir for ``FABRIK_ROOT`` to keep tests hermetic.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_state_dir(tmp_path, monkeypatch):
    fake_root = tmp_path / "fabrik"
    fake_root.mkdir()
    # Initialize a minimal git repo so _git_sha() returns something real
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=str(fake_root), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=str(fake_root), check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "test"], cwd=str(fake_root), check=True
    )
    (fake_root / "README.md").write_text("test")
    subprocess.run(["git", "add", "."], cwd=str(fake_root), check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=str(fake_root), check=True
    )

    monkeypatch.setenv("FABRIK_ROOT", str(fake_root))
    monkeypatch.setenv("FABRIK_LOCK_DIR", str(tmp_path / "locks"))
    # Reload modules so module-level constants pick up env
    import fabrik.config
    import fabrik.locks_local
    import fabrik.state

    importlib.reload(fabrik.config)
    importlib.reload(fabrik.locks_local)
    importlib.reload(fabrik.state)
    yield


def _import():
    from fabrik import state

    return state


def test_save_writes_all_8_fields():
    state = _import()
    path = state.save(
        "translator",
        spec_path="/opt/fabrik/specs/services/translator.yaml",
        spec_hash="abc123",
        coolify_uuid="kgws0s4cscsosw8gg848cwgw",
        coolify_app_name="fabrik-translator",
        registrars_applied=[
            {"type": "postgres", "id": "translator", "status": "applied"},
            {"type": "gatus", "id": "translator", "status": "applied"},
        ],
        domain="translator.vps1.ocoron.com",
    )
    payload = json.loads(path.read_text())
    assert set(payload.keys()) == {
        "applied_at",
        "coolify_app_name",
        "coolify_uuid",
        "domain",
        "git_sha",
        "registrars_applied",
        "spec_hash",
        "spec_path",
    }


def test_data_bearing_auto_stamped_for_postgres_redis_meilisearch():
    state = _import()
    path = state.save(
        "fakeservice",
        spec_path="x",
        spec_hash="x",
        coolify_uuid="u",
        coolify_app_name="x",
        registrars_applied=[
            {"type": "postgres", "id": "x", "status": "applied"},
            {"type": "redis", "id": "x", "status": "applied"},
            {"type": "meilisearch", "id": "x", "status": "applied"},
            {"type": "gatus", "id": "x", "status": "applied"},
            {"type": "grafana", "id": "x", "status": "applied"},
        ],
    )
    payload = json.loads(path.read_text())
    by_type = {r["type"]: r["data_bearing"] for r in payload["registrars_applied"]}
    assert by_type == {
        "postgres": True,
        "redis": True,
        "meilisearch": True,
        "gatus": False,
        "grafana": False,
    }


def test_data_bearing_constant_is_canonical():
    state = _import()
    assert frozenset({"postgres", "redis", "meilisearch"}) == state.DATA_BEARING_REGISTRARS


def test_caller_specified_data_bearing_is_overwritten():
    # Even if caller passes data_bearing=True for grafana, it gets reset.
    state = _import()
    path = state.save(
        "fakesvc",
        spec_path="x",
        spec_hash="x",
        coolify_uuid="u",
        coolify_app_name="x",
        registrars_applied=[
            {"type": "grafana", "id": "x", "status": "applied", "data_bearing": True},
        ],
    )
    payload = json.loads(path.read_text())
    assert payload["registrars_applied"][0]["data_bearing"] is False


def test_atomic_write_no_tmp_left_behind(tmp_path):
    state = _import()
    state.save(
        "atomicsvc",
        spec_path="x",
        spec_hash="x",
        coolify_uuid="u",
        coolify_app_name="x",
        registrars_applied=[],
    )
    state_dir = Path(state.STATE_DIR)
    leftover = list(state_dir.glob("*.tmp.*"))
    assert leftover == [], f"tmp files leaked: {leftover}"


def test_load_returns_none_if_missing():
    state = _import()
    assert state.load("nonexistent-spec") is None


def test_load_round_trips():
    state = _import()
    state.save(
        "roundtrip",
        spec_path="/x",
        spec_hash="abc",
        coolify_uuid="u",
        coolify_app_name="roundtrip",
        registrars_applied=[{"type": "postgres", "id": "x", "status": "applied"}],
        domain="example.com",
    )
    loaded = state.load("roundtrip")
    assert loaded["spec_path"] == "/x"
    assert loaded["spec_hash"] == "abc"
    assert loaded["coolify_uuid"] == "u"
    assert loaded["domain"] == "example.com"
    assert loaded["registrars_applied"][0]["data_bearing"] is True


def test_archive_destroyed_moves_file_with_timestamp():
    state = _import()
    state.save(
        "tobedestroyed",
        spec_path="x",
        spec_hash="x",
        coolify_uuid="u",
        coolify_app_name="x",
        registrars_applied=[],
    )
    src = state.STATE_DIR / "tobedestroyed.json"
    assert src.exists()
    archived = state.archive_destroyed("tobedestroyed")
    assert archived is not None
    assert not src.exists()
    assert archived.parent.name == "_destroyed"
    assert archived.name.startswith("tobedestroyed.json.")


def test_archive_destroyed_returns_none_if_no_file():
    state = _import()
    assert state.archive_destroyed("never-existed") is None


def test_find_by_spec_id():
    state = _import()
    assert state.find_by_spec_id("nope") is None
    state.save(
        "exists",
        spec_path="x",
        spec_hash="x",
        coolify_uuid="u",
        coolify_app_name="x",
        registrars_applied=[],
    )
    found = state.find_by_spec_id("exists")
    assert found is not None
    assert found.name == "exists.json"


def test_apply_persist_destroy_archive_roundtrip():
    """The full lifecycle that ``fabrik audit-registrars`` (T2-02) and
    ``fabrik destroy --use-state`` (T4-02) depend on.
    SC-3 from the Epic Brief."""
    state = _import()
    # 1. Apply phase persists state.
    path = state.save(
        "lifecycle",
        spec_path="/opt/fabrik/specs/services/lifecycle.yaml",
        spec_hash="hash-1",
        coolify_uuid="abc123",
        coolify_app_name="lifecycle",
        registrars_applied=[
            {"type": "postgres", "id": "lifecycle", "status": "applied"},
            {"type": "redis", "id": "lifecycle", "status": "applied"},
            {"type": "gatus", "id": "lifecycle", "status": "applied"},
        ],
        domain="lifecycle.vps1.ocoron.com",
    )
    assert path.exists()
    # 2. Read back (mid-deploy audit step would do this).
    payload = state.load("lifecycle")
    assert payload["spec_hash"] == "hash-1"
    data_bearing_types = {
        r["type"] for r in payload["registrars_applied"] if r["data_bearing"]
    }
    assert data_bearing_types == {"postgres", "redis"}
    # 3. Destroy phase archives the file.
    archived = state.archive_destroyed("lifecycle")
    assert archived is not None
    # 4. After destroy, state.load returns None — service is "gone".
    assert state.load("lifecycle") is None
    # 5. Archive still on disk for forensic / audit purposes.
    assert archived.exists()
    # 6. Archive content equals what was persisted.
    archived_payload = json.loads(archived.read_text())
    assert archived_payload["spec_hash"] == "hash-1"


def test_git_sha_populated_from_real_git_repo():
    # The fixture initialized a real git repo at FABRIK_ROOT — sha should
    # be a non-empty 40-char string.
    state = _import()
    state.save(
        "gitcheck",
        spec_path="x",
        spec_hash="x",
        coolify_uuid="u",
        coolify_app_name="x",
        registrars_applied=[],
    )
    payload = state.load("gitcheck")
    assert len(payload["git_sha"]) == 40
    assert all(c in "0123456789abcdef" for c in payload["git_sha"])


def test_git_sha_falls_back_to_empty_outside_git(monkeypatch, tmp_path):
    # Point FABRIK_ROOT at a non-git dir
    nogit = tmp_path / "nogit"
    nogit.mkdir()
    monkeypatch.setenv("FABRIK_ROOT", str(nogit))
    import fabrik.config
    import fabrik.state

    importlib.reload(fabrik.config)
    importlib.reload(fabrik.state)
    state = fabrik.state
    state.save(
        "no-git-here",
        spec_path="x",
        spec_hash="x",
        coolify_uuid="u",
        coolify_app_name="x",
        registrars_applied=[],
    )
    payload = state.load("no-git-here")
    assert payload["git_sha"] == ""
