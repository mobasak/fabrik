"""Tests for fabrik.state — save/load/archive_destroyed round-trip.

Uses a tmp dir for ``FABRIK_ROOT`` to keep tests hermetic.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

# Imported before the autouse fixture repoints FABRIK_ROOT at a tmp dir: the CLI pulls in
# fabrik.scaffold, which binds FABRIK_ROOT at import to find scripts/fabrik_synced_manifest.py.
import fabrik.cli  # noqa: F401


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
    subprocess.run(["git", "config", "user.name", "test"], cwd=str(fake_root), check=True)
    (fake_root / "README.md").write_text("test")
    subprocess.run(["git", "add", "."], cwd=str(fake_root), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(fake_root), check=True)

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
    # monkeypatch restores the env only after this teardown, and a reloaded module keeps the
    # constants it computed from the fake env — so undo first, then reload back, or every later
    # test in the session sees FABRIK_ROOT/STATE_DIR/LOCK_DIR in a deleted tmp dir (W-019e468b;
    # graded by tests/test_state_restores_modules.py)
    monkeypatch.undo()
    importlib.reload(fabrik.config)
    importlib.reload(fabrik.locks_local)
    importlib.reload(fabrik.state)


def _import():
    from fabrik import state

    return state


def test_save_writes_every_field():
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
        "registrar_failures",
        "registrars_applied",
        "spec_hash",
        "spec_path",
        "target_vps",
    }
    # audit.py and cli.py read target_vps back from this file to find the box (added 0a5a15f84);
    # a spec that names none lands on the hub
    assert payload["target_vps"] == "vps1"
    # always written, so its presence means "recorded" and [] means the apply finished clean
    assert payload["registrar_failures"] == []


def _save_with_failures(state, failures):
    return state.save(
        "svc",
        spec_path="/opt/fabrik/specs/services/svc.yaml",
        spec_hash="h",
        coolify_uuid=None,
        coolify_app_name="svc",
        registrars_applied=[{"type": "redis", "id": "svc", "status": "applied"}],
        registrar_failures=failures,
    )


def test_registrar_failures_round_trip():
    state = _import()
    _save_with_failures(state, [{"registrar": "redis", "error": "REDIS_URL injection failed"}])
    assert state.load("svc")["registrar_failures"] == [
        {"registrar": "redis", "error": "REDIS_URL injection failed"}
    ]


@pytest.mark.parametrize(
    ("raw", "secret"),
    [
        ("env write failed: CONSUMER_TOKENS=abc123def", "abc123def"),
        ("connect redis://:S3cr3t@redis-main:6379/3 refused", "S3cr3t"),
        ("FATAL for postgresql://svc:p%40ssw0rd@postgres-main:5432/db", "p%40ssw0rd"),
        (
            "psql: ERROR: syntax error / LINE 1: ALTER ROLE \"svc\" WITH PASSWORD 'S3cr3t';",
            "S3cr3t",
        ),
        # the 500-char cap cuts this before its "@": capping first would leave "straddle" unmasked
        ("x" * 482 + " redis://:straddle@h", "straddle"),
        ("grafana: 401 for Authorization: Bearer sk-live-ABCDEF123456", "sk-live-ABCDEF123456"),
        (
            'glitchtip: bad body {"username": "admin", "password": "SuperSecret123"}',
            "SuperSecret123",
        ),
        ("docker run -e PGPASSWORD='my secret pass' postgres", "secret pass"),
    ],
)
def test_registrar_failures_are_sanitised(raw, secret):
    """The file is exported by `fabrik export`: secret-shaped text is masked BEFORE the cap."""
    state = _import()
    _save_with_failures(state, [{"registrar": "postgres", "error": raw}])
    error = state.load("svc")["registrar_failures"][0]["error"]
    assert secret not in error
    assert len(error) <= 500


def test_registrar_failures_sanitiser_never_raises():
    """A raise inside _persist_state's except would drop the whole state file."""
    state = _import()
    _save_with_failures(
        state, [{"registrar": "x", "error": 123}, {"registrar": None}, "bare string"]
    )
    assert [f["error"] for f in state.load("svc")["registrar_failures"]] == [
        "123",
        "",
        "bare string",
    ]


def _orchestrator():
    from unittest.mock import MagicMock

    from fabrik.orchestrator import DeploymentOrchestrator

    orch = DeploymentOrchestrator()
    orch.validator = MagicMock()
    orch.validator.load_and_validate.return_value = (
        {"name": "svc", "id": "svc", "domain": "svc.example.com"},
        "spec-hash",
        [],
    )
    orch.deployer = MagicMock()
    orch.deployer.find_existing.return_value = {"name": "svc", "status": "", "path": "/opt/svc"}
    return orch


def test_persist_state_records_failures_and_skips_dry_run(tmp_path):
    from fabrik.orchestrator.context import DeploymentContext

    state = _import()
    orch = _orchestrator()
    spec = {"id": "svc", "name": "svc"}
    ctx = DeploymentContext(spec_path=tmp_path / "svc.yaml")
    ctx.registrar_failures.extend(
        ["redis: REDIS_URL injection failed: boom", "app-role: no", 42, "label-only"]
    )
    orch._persist_state(ctx, spec)
    recorded = state.load("svc")["registrar_failures"]
    assert recorded == [
        {"registrar": "redis", "error": "REDIS_URL injection failed: boom"},
        {"registrar": "app-role", "error": "no"},
        {"registrar": "42", "error": ""},
        {"registrar": "label-only", "error": ""},
    ]
    # a dry run never touches the file, so the recorded failure survives it
    dry = DeploymentContext(spec_path=tmp_path / "svc.yaml", dry_run=True)
    orch._persist_state(dry, spec)
    assert state.load("svc")["registrar_failures"] == recorded


def test_refresh_persists_a_nonfatal_failure(tmp_path):
    from fabrik.orchestrator.infrastructure import InfrastructureProvisioner

    state = _import()
    orch = _orchestrator()

    class _Provisioner:
        def provision(self, ctx):
            InfrastructureProvisioner._nonfatal(
                ctx, "redis", RuntimeError("REDIS_URL injection failed")
            )

    orch.infrastructure_provisioner = _Provisioner()
    spec_path = tmp_path / "svc.yaml"
    spec_path.write_text("name: svc\n")
    orch.refresh_infrastructure(spec_path=spec_path)
    assert state.load("svc")["registrar_failures"] == [
        {"registrar": "redis", "error": "REDIS_URL injection failed"}
    ]


def test_old_state_file_without_failures_still_loads():
    state = _import()
    state.STATE_DIR.mkdir(parents=True, exist_ok=True)
    (state.STATE_DIR / "old.json").write_text(
        json.dumps({"applied_at": "2026-05-01T00:00:00+00:00", "registrars_applied": []})
    )
    payload = state.load("old")
    assert payload is not None
    assert payload.get("registrar_failures") is None


def test_audit_registrars_reports_recorded_failures(monkeypatch):
    from types import SimpleNamespace

    from click.testing import CliRunner

    import fabrik.audit
    import fabrik.cli

    state = _import()
    _save_with_failures(state, [{"registrar": "redis", "error": "REDIS_URL injection failed"}])
    monkeypatch.setattr(fabrik.cli, "load_spec", lambda _p: SimpleNamespace(id="svc"))
    monkeypatch.setattr(fabrik.audit, "audit_all", lambda _s: {})
    result = CliRunner().invoke(fabrik.cli.cli, ["audit-registrars", "--spec", __file__])
    assert result.exit_code == 2, result.output
    assert "svc: last apply" in result.output
    assert "redis" in result.output
    # a hand-edited file whose entries are not records is skipped, never a crash
    (state.STATE_DIR / "svc.json").write_text(
        json.dumps({"applied_at": "x", "registrar_failures": ["oops", 3]})
    )
    result = CliRunner().invoke(fabrik.cli.cli, ["audit-registrars", "--spec", __file__])
    assert result.exception is None or isinstance(result.exception, SystemExit), result.output
    assert "svc: last apply" not in result.output


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
    data_bearing_types = {r["type"] for r in payload["registrars_applied"] if r["data_bearing"]}
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
