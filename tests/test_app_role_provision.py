"""T04 (audit-log-everywhere) — the registrar's `<db>_app` step inside `_provision_postgres`.

Every driver the step reaches is patched: `ensure_app_role`, `run_check`, the watchdog /
payments / subagent role drivers and `create_database`. The deployer is a recorder with a
fake `.env`. Passwords here are fake literals, asserted by the SHAPE of the DSN (user, host,
scheme), never printed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest import mock
from urllib.parse import urlsplit

import pytest

from fabrik.app_role_check import CheckResult
from fabrik.drivers.postgres import AppRoleError
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.infrastructure import InfrastructureProvisioner

# conftest stubs `_provision_app_role` for every other module; this one drives it for real.
LIVE_APP_ROLE_STEP = True

DB = "shop"
APP = "shop_app"
OWNER_DSN = "postgresql://shop:ownerpw@postgres-main:5432/shop"
APP_DSN = "postgresql://shop_app:apppw@postgres-main:5432/shop"


class _Deployer:
    """Records `read_env` / `inject_env` into the shared event list; `.env` is a dict."""

    def __init__(self, env: dict[str, str], events: list[tuple], read_error: Exception | None):
        self.env = dict(env)
        self.events = events
        self.read_error = read_error
        self.injects: list[dict[str, str]] = []

    def read_env(self, ctx: DeploymentContext) -> dict[str, str]:
        self.events.append(("read_env",))
        if self.read_error:
            raise self.read_error
        return dict(self.env)

    def inject_env(self, ctx: DeploymentContext, env_vars: dict[str, str]) -> None:
        self.events.append(("inject_env", tuple(sorted(env_vars))))
        # Only the DATABASE_URL* injections are this step's; the subagent-runs env is
        # injected unconditionally by the block after it.
        if any(k.startswith("DATABASE_URL") for k in env_vars):
            self.injects.append(dict(env_vars))
        self.env.update(env_vars)


def _run(
    tmp_path: Path,
    *,
    flag: bool | None = None,
    env: dict[str, str] | None = None,
    created_password: str | None = None,
    ensure_error: Exception | None = None,
    check: CheckResult | None = None,
    siblings: dict[str, dict] | None = None,
    dry_run: bool = False,
    target_vps: str = "vps1",
    read_error: Exception | None = None,
) -> tuple[_Deployer, DeploymentContext, list[tuple], dict[str, mock.MagicMock]]:
    events: list[tuple] = []
    specs = tmp_path / "specs" / "services"
    specs.mkdir(parents=True, exist_ok=True)
    shape: dict[str, Any] = {"needs_database": True}
    if flag is not None:
        shape["database_url_app_role"] = flag
    spec = {"name": DB, "shape": shape}
    spec_path = specs / f"{DB}.yaml"
    spec_path.write_text(f"name: {DB}\nshape:\n  needs_database: true\n")
    for fname, body in (siblings or {}).items():
        import yaml

        (specs / fname).write_text(yaml.safe_dump(body))

    deployer = _Deployer(env or {}, events, read_error)
    prov = InfrastructureProvisioner(deployer=deployer)
    ctx = DeploymentContext(spec_path=spec_path, dry_run=dry_run)
    ctx.spec = spec
    ctx.app_name = DB
    ctx.target_vps = target_vps

    def fake_create(db, **kw):
        return {"status": "created" if created_password else "exists", "password": created_password}

    def fake_ensure(db, container="postgres-main", dry_run=False, reset_password=False):
        events.append(("ensure_app_role", reset_password))
        if ensure_error:
            raise ensure_error
        return {
            "user": f"{db}_app",
            "owner": db,
            "password": "newapppw" if reset_password else None,
            "status": "reset" if reset_password else "exists",
        }

    def fake_watchdog(db, dry_run=False, **kw):
        events.append(("watchdog",))
        return {"ro": {"user": f"{db}_wd_ro"}, "rw": {"user": f"{db}_wd_rw"}}

    def fake_payments(db, dry_run=False, **kw):
        events.append(("payments",))
        return {"user": f"{db}_payments_ingest", "password": None, "status": "exists"}

    def fake_check(db, repo_dir, container="postgres-main"):
        events.append(("run_check", db, str(repo_dir)))
        return check if check is not None else CheckResult(ok=True, failures=[])

    mocks: dict[str, mock.MagicMock] = {}
    with (
        mock.patch("fabrik.drivers.postgres.create_database", side_effect=fake_create),
        mock.patch("fabrik.drivers.postgres.database_exists", return_value=False),
        mock.patch("fabrik.drivers.postgres.create_watchdog_roles", side_effect=fake_watchdog),
        mock.patch(
            "fabrik.drivers.postgres.create_payments_ingest_role", side_effect=fake_payments
        ),
        mock.patch(
            "fabrik.drivers.postgres.create_subagent_ins_role",
            return_value={"ins": {"user": "x", "password": None}},
        ),
        mock.patch("fabrik.drivers.postgres.ensure_app_role", side_effect=fake_ensure) as ens,
        mock.patch("fabrik.app_role_check.run_check", side_effect=fake_check) as chk,
        mock.patch("fabrik.drivers.postgres._run_sql") as run_sql,
        mock.patch("fabrik.drivers.ssh.ssh") as ssh,
    ):
        mocks.update(ensure=ens, check=chk, run_sql=run_sql, ssh=ssh)
        prov._provision_postgres(
            DB,
            spec,
            ctx,
            dry_run=dry_run,
            provision_watchdog_roles=True,
            provision_payments_ingest=True,
        )
    return deployer, ctx, events, mocks


def _app_role_failures(ctx: DeploymentContext) -> list[str]:
    return [f for f in ctx.registrar_failures if f.startswith("app-role:")]


def _status(ctx: DeploymentContext) -> str | None:
    recs = ctx.get_resources_by_type("app-role")
    return recs[-1].metadata.get("status") if recs else None


# ── Row 1: fresh create — owner first ────────────────────────────────────────── #


def test_fresh_create_injects_owner_dsn_twice_before_ensure_app_role(tmp_path: Path) -> None:
    deployer, ctx, events, _ = _run(
        tmp_path, created_password="ownerpw", target_vps="vps2", flag=False
    )
    first = deployer.injects[0]
    assert set(first) == {"DATABASE_URL", "DATABASE_URL_OWNER"}
    for key in first:
        parts = urlsplit(first[key])
        assert parts.username == DB and parts.hostname == "10.99.0.1"  # spoke rewrite
    assert first["DATABASE_URL"] == first["DATABASE_URL_OWNER"]
    assert events.index(("inject_env", ("DATABASE_URL", "DATABASE_URL_OWNER"))) < events.index(
        ("ensure_app_role", False)
    )
    # converged: owner DSN, flag false, DATABASE_URL_OWNER present → nothing more injected
    assert len(deployer.injects) == 1
    assert _app_role_failures(ctx) == []


def test_fresh_create_owner_injection_survives_ensure_failure(tmp_path: Path) -> None:
    deployer, ctx, _, _ = _run(
        tmp_path, created_password="ownerpw", ensure_error=RuntimeError("psql batch failed")
    )
    assert set(deployer.injects[0]) == {"DATABASE_URL", "DATABASE_URL_OWNER"}
    assert len(_app_role_failures(ctx)) == 1
    assert "psql batch failed" in _app_role_failures(ctx)[0]


# ── Row 2: missing flag key ──────────────────────────────────────────────────── #


def test_missing_flag_reads_false_mints_role_and_runs_no_check(tmp_path: Path) -> None:
    env = {"DATABASE_URL": OWNER_DSN, "DATABASE_URL_OWNER": OWNER_DSN}
    deployer, ctx, events, mocks = _run(tmp_path, env=env)
    assert ("ensure_app_role", False) in events
    mocks["check"].assert_not_called()
    assert deployer.injects == []
    assert _app_role_failures(ctx) == []


def test_missing_flag_legacy_postgres_owner_is_skipped_not_failed(tmp_path: Path) -> None:
    err = AppRoleError("database 'shop' has owner 'postgres': re-own it first")
    deployer, ctx, _, mocks = _run(tmp_path, env={"DATABASE_URL": OWNER_DSN}, ensure_error=err)
    assert _status(ctx) == "skipped"
    assert "postgres" in ctx.get_resources_by_type("app-role")[-1].metadata.get("reason", "")
    assert ctx.registrar_failures == []
    assert deployer.injects == []
    mocks["check"].assert_not_called()


def test_flag_true_app_role_error_is_a_failure(tmp_path: Path) -> None:
    err = AppRoleError("database 'shop' has owner 'postgres'")
    _, ctx, _, _ = _run(tmp_path, flag=True, env={"DATABASE_URL": OWNER_DSN}, ensure_error=err)
    assert len(_app_role_failures(ctx)) == 1


# ── Row 3: cutover ───────────────────────────────────────────────────────────── #

ASYNC_OWNER = "postgresql+asyncpg://shop:ownerpw@10.99.0.1:5432/shop?ssl=require"


def test_cutover_swaps_only_user_and_password(tmp_path: Path) -> None:
    deployer, ctx, events, mocks = _run(tmp_path, flag=True, env={"DATABASE_URL": ASYNC_OWNER})
    assert ("ensure_app_role", True) in events
    assert events.index(("run_check", DB, "/opt/shop")) < events.index(("ensure_app_role", True))
    assert len(deployer.injects) == 1
    injected = deployer.injects[0]
    assert injected["DATABASE_URL_OWNER"] == ASYNC_OWNER
    old, new = urlsplit(ASYNC_OWNER), urlsplit(injected["DATABASE_URL"])
    assert new.username == APP and new.password and new.password != old.password
    assert (new.scheme, new.hostname, new.port, new.path, new.query) == (
        old.scheme,
        old.hostname,
        old.port,
        old.path,
        old.query,
    )
    assert _app_role_failures(ctx) == []
    assert _status(ctx) == "cutover"


def test_cutover_with_failing_check_injects_nothing(tmp_path: Path) -> None:
    check = CheckResult(ok=False, failures=["alembic env.py reads DATABASE_URL", "no upstream"])
    deployer, ctx, events, _ = _run(
        tmp_path, flag=True, env={"DATABASE_URL": ASYNC_OWNER}, check=check
    )
    assert deployer.injects == []
    assert ("ensure_app_role", True) not in events
    failures = _app_role_failures(ctx)
    assert len(failures) == 1
    assert "alembic env.py reads DATABASE_URL" in failures[0] and "no upstream" in failures[0]


# ── Row 4: rollback ──────────────────────────────────────────────────────────── #


def test_rollback_restores_owner_dsn(tmp_path: Path) -> None:
    env = {"DATABASE_URL": APP_DSN, "DATABASE_URL_OWNER": OWNER_DSN}
    deployer, ctx, events, mocks = _run(tmp_path, flag=False, env=env)
    assert deployer.injects == [{"DATABASE_URL": OWNER_DSN}]
    assert ("ensure_app_role", True) not in events
    mocks["check"].assert_not_called()
    assert _app_role_failures(ctx) == []
    assert _status(ctx) == "rolled_back"


def test_rollback_without_owner_dsn_fails(tmp_path: Path) -> None:
    deployer, ctx, _, _ = _run(tmp_path, flag=False, env={"DATABASE_URL": APP_DSN})
    assert deployer.injects == []
    failures = _app_role_failures(ctx)
    assert len(failures) == 1 and "DATABASE_URL_OWNER" in failures[0]
    assert "apppw" not in failures[0]


# ── Row 5: fail closed ───────────────────────────────────────────────────────── #


@pytest.mark.parametrize(
    ("env", "named"),
    [
        ({}, "no DATABASE_URL"),
        ({"DATABASE_URL": "postgresql://postgres:superpw@postgres-main:5432/shop"}, "'postgres'"),
    ],
)
def test_flag_true_unmanaged_dsn_fails_closed(tmp_path: Path, env, named) -> None:
    deployer, ctx, events, mocks = _run(tmp_path, flag=True, env=env)
    assert deployer.injects == []
    assert ("ensure_app_role", True) not in events
    mocks["check"].assert_not_called()
    failures = _app_role_failures(ctx)
    assert len(failures) == 1 and named in failures[0]
    assert "superpw" not in failures[0] and "postgresql://" not in failures[0]


def test_flag_true_shared_database_refuses(tmp_path: Path) -> None:
    siblings = {
        "other.yaml": {
            "name": "other",
            "shape": {"needs_database": True},
            "depends": {"postgres": DB},
        },
        "nodb.yaml": {
            "name": "nodb",
            "shape": {"needs_database": False},
            "depends": {"postgres": DB},
        },
        "unrelated.yaml": {"name": "unrelated", "shape": {"needs_database": True}},
    }
    deployer, ctx, events, mocks = _run(
        tmp_path, flag=True, env={"DATABASE_URL": OWNER_DSN}, siblings=siblings
    )
    assert deployer.injects == []
    assert ("ensure_app_role", True) not in events
    mocks["check"].assert_not_called()
    failures = _app_role_failures(ctx)
    assert len(failures) == 1
    assert "other.yaml" in failures[0]
    assert "nodb.yaml" not in failures[0] and "unrelated.yaml" not in failures[0]
    assert "ownerpw" not in failures[0]


def test_unreadable_env_fails_closed(tmp_path: Path) -> None:
    from fabrik.orchestrator.exceptions import DeployError

    deployer, ctx, _, _ = _run(tmp_path, flag=True, read_error=DeployError("cannot read .env"))
    assert deployer.injects == []
    assert len(_app_role_failures(ctx)) == 1


# ── Row 6: converged re-apply ────────────────────────────────────────────────── #


@pytest.mark.parametrize(
    ("flag", "url"), [(True, APP_DSN), (False, OWNER_DSN)], ids=["app-on", "owner-off"]
)
def test_converged_reapply_injects_nothing(tmp_path: Path, flag, url) -> None:
    env = {"DATABASE_URL": url, "DATABASE_URL_OWNER": OWNER_DSN}
    deployer, ctx, events, mocks = _run(tmp_path, flag=flag, env=env)
    ensures = [e for e in events if e[0] == "ensure_app_role"]
    assert ensures == [("ensure_app_role", False)]
    assert events.index(("watchdog",)) < events.index(ensures[0])
    assert events.index(("payments",)) < events.index(ensures[0])
    assert deployer.injects == []
    mocks["check"].assert_not_called()
    assert _app_role_failures(ctx) == []
    assert _status(ctx) == "converged"


def test_converged_owner_backfills_missing_owner_key(tmp_path: Path) -> None:
    deployer, ctx, _, _ = _run(tmp_path, flag=False, env={"DATABASE_URL": OWNER_DSN})
    assert deployer.injects == [{"DATABASE_URL_OWNER": OWNER_DSN}]
    assert _app_role_failures(ctx) == []


def test_converged_app_without_owner_key_fails(tmp_path: Path) -> None:
    deployer, ctx, _, _ = _run(tmp_path, flag=True, env={"DATABASE_URL": APP_DSN})
    assert deployer.injects == []
    failures = _app_role_failures(ctx)
    assert len(failures) == 1 and "rollback" in failures[0]


# ── Row 8: dry-run ───────────────────────────────────────────────────────────── #


def test_dry_run_touches_nothing(tmp_path: Path) -> None:
    deployer, ctx, events, mocks = _run(tmp_path, flag=True, dry_run=True)
    assert not [e for e in events if e[0] in ("ensure_app_role", "read_env", "run_check")]
    mocks["run_sql"].assert_not_called()
    mocks["ssh"].assert_not_called()
    assert _status(ctx) == "dry_run"
