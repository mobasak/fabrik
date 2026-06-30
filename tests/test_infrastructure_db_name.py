"""Phase 1a (deploy-readiness-gaps): ``_provision_postgres`` must respect
``spec.depends.postgres`` (now load-bearing) with a rename guard that never
silently orphans an existing derived-name DB.

Pre-fix, the DB name was ALWAYS derived from the spec id
(``infrastructure.py:432`` ``name.replace("-", "_")``), so a spec pinning a
different name was ignored — fabrik created/used the wrong name and pointed the
app's ``DATABASE_URL`` at it (calendar: app /health passed on ``SELECT 1`` but
every real endpoint 500'd against the empty/wrong DB).
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.infrastructure import InfrastructureProvisioner


def _run(
    name: str,
    spec: dict,
    *,
    derived_exists: bool = False,
    target_exists: bool = False,
    allow_rename: bool = False,
    monkeypatch,
) -> tuple[str | None, DeploymentContext]:
    """Call ``_provision_postgres`` with the postgres driver mocked.

    Returns ``(db_name_passed_to_create_database | None, ctx)``.
    """
    if allow_rename:
        monkeypatch.setenv("FABRIK_ALLOW_DB_RENAME", "1")
    else:
        monkeypatch.delenv("FABRIK_ALLOW_DB_RENAME", raising=False)

    derived = name.replace("-", "_")
    created: dict[str, str] = {}

    def fake_create(db_name, **_kw):
        created["db"] = db_name
        return {"status": "created", "database": db_name}  # no password → no inject_env

    def fake_exists(n, **_kw):
        return derived_exists if n == derived else target_exists

    prov = InfrastructureProvisioner(deployer=mock.MagicMock())
    ctx = DeploymentContext(spec_path=Path("specs/services/x.yaml"))
    with (
        mock.patch("fabrik.drivers.postgres.create_database", side_effect=fake_create),
        mock.patch("fabrik.drivers.postgres.database_exists", side_effect=fake_exists),
    ):
        prov._provision_postgres(name, spec, ctx, dry_run=False)
    return created.get("db"), ctx


def _blocked(ctx: DeploymentContext) -> bool:
    return any(
        r.metadata.get("status") == "rename_guard_blocked" for r in ctx.created_resources
    )


def test_uses_configured_depends_postgres(monkeypatch):
    db, _ = _run("my-svc", {"depends": {"postgres": "pinned_db"}}, monkeypatch=monkeypatch)
    assert db == "pinned_db"


def test_falls_back_to_derived_when_depends_absent(monkeypatch):
    db, _ = _run("my-svc", {}, monkeypatch=monkeypatch)
    assert db == "my_svc"


def test_falls_back_when_depends_is_null(monkeypatch):
    # `depends:` present but null in YAML → the `or {}` guard must not crash.
    db, _ = _run("my-svc", {"depends": None}, monkeypatch=monkeypatch)
    assert db == "my_svc"


def test_calendar_case_no_guard_when_derived_absent(monkeypatch):
    # Calendar: derived (calendar_orchestration_engine) was never created → guard
    # must NOT trigger; the pinned calendar_engine is used. THE fix for the
    # original deploy-blocker.
    db, ctx = _run(
        "calendar-orchestration-engine",
        {"depends": {"postgres": "calendar_engine"}},
        derived_exists=False,
        monkeypatch=monkeypatch,
    )
    assert db == "calendar_engine"
    assert not _blocked(ctx)


def test_rename_guard_blocks_when_derived_db_exists(monkeypatch):
    # A different spec where the historical derived DB already holds data: switching
    # to the pinned name would orphan it → guard blocks, create_database NOT called.
    db, ctx = _run(
        "trading-core",
        {"depends": {"postgres": "trading"}},
        derived_exists=True,
        target_exists=False,
        monkeypatch=monkeypatch,
    )
    assert db is None
    assert _blocked(ctx)


def test_rename_guard_override_allows(monkeypatch):
    db, ctx = _run(
        "trading-core",
        {"depends": {"postgres": "trading"}},
        derived_exists=True,
        target_exists=False,
        allow_rename=True,
        monkeypatch=monkeypatch,
    )
    assert db == "trading"
    assert not _blocked(ctx)


def test_no_guard_when_target_already_exists(monkeypatch):
    # Re-apply after a successful rename: pinned DB already exists → no orphaning
    # risk, guard must not block (create_database is itself idempotent).
    db, ctx = _run(
        "trading-core",
        {"depends": {"postgres": "trading"}},
        derived_exists=True,
        target_exists=True,
        monkeypatch=monkeypatch,
    )
    assert db == "trading"
    assert not _blocked(ctx)
