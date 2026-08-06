"""Highest-risk path for the watchdog per-project DB roles (fabrik-lib
"product-aware watchdog" contract): the PRIVILEGE BOUNDARY + failure-mode
robustness of the SQL the registrar runs as the postgres superuser.

``create_watchdog_roles`` mints two per-project roles on the app DB:
  {db}_wd_ro : SELECT-only  -> WATCHDOG_DB_URL_RO (sidecar default)
  {db}_wd_rw : DML-only      -> WATCHDOG_DB_URL_RW (Tier-C write lane)

If the RO role ever gained ANY write verb (INSERT/UPDATE/DELETE/TRUNCATE/…), or
RW gained DDL/DROP/ownership, the invariants fabrik-lib builds on would be
silently violated — so these tests pin the exact grants AND guard against a
regression that ADDS a write grant on a separate line. They also pin the
hardening from adversarial review: ``ON_ERROR_STOP`` (no false-success on a
mid-batch failure), password rotation ONLY on fresh create (an existing role is
preserved so a cached-build re-apply never breaks a running sidecar), and a
real-owner lookup for ``ALTER DEFAULT PRIVILEGES`` (omitted, not guessed, when
the owner can't be resolved — works on postgres-owned legacy DBs).

All VPS mutations are mocked at the ``_run_sql`` boundary; hermetic. These
prove the EMITTED SQL only — a live-Postgres execution test is out of scope
(no cluster in unit tests), so assertions are structural, not behavioral.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from fabrik.drivers import postgres as pg
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.infrastructure import InfrastructureProvisioner

DB = "calendar_engine"
RO = f"{DB}_wd_ro"
RW = f"{DB}_wd_rw"
# Every write/DDL verb the RO role must NEVER receive, on ANY line.
_WRITE_VERBS = ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def _capture(
    db: str = DB, *, owner: str | None = None, ro_exists: bool = False, rw_exists: bool = False
):
    """Run create_watchdog_roles with _run_sql/_role_exists/_generate_password
    mocked; return (result, batch_sql). ``owner`` is what the datdba lookup
    returns (default: db_name); ``ro_exists``/``rw_exists`` drive the fresh-vs-
    preserve branch."""
    resolved_owner = db if owner is None else owner
    calls: list[str] = []

    def fake_run_sql(sql, container=pg.POSTGRES_CONTAINER, dry_run=False):
        calls.append(sql)
        if "pg_get_userbyid" in sql:  # the _db_owner lookup
            return resolved_owner
        return ""

    def fake_role_exists(role, *_a, **_k):
        return ro_exists if role.endswith(pg._WD_RO_SUFFIX) else rw_exists

    with (
        mock.patch.object(pg, "_run_sql", side_effect=fake_run_sql),
        mock.patch.object(pg, "_role_exists", side_effect=fake_role_exists),
        mock.patch.object(pg, "_generate_password", side_effect=["RO_PW", "RW_PW"]),
    ):
        result = pg.create_watchdog_roles(db)
    # The batch is the only _run_sql call that carries GRANT CONNECT; the owner
    # lookup is a plain SELECT. Assert the shape so a future extra call can't
    # silently make the assertions inspect the wrong string.
    batch_calls = [c for c in calls if "GRANT CONNECT" in c]
    assert len(batch_calls) == 1, f"expected exactly one grant batch, got {len(batch_calls)}"
    # CREATE ROLE is now a SEPARATE _run_sql call from the GRANT batch (split to
    # avoid orphan-role-with-lost-password on a GRANT failure), so return the UNION
    # of all emitted SQL — tests assert on the total CREATE + GRANT surface.
    return result, "\n".join(calls)


# ── privilege boundary ─────────────────────────────────────────────────────


def test_ro_gets_select_and_no_write_verb_on_any_line():
    _, sql = _capture()
    assert f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{RO}";' in sql
    # A regression that adds e.g. `GRANT UPDATE ... TO "<ro>"` on a NEW line must
    # be caught — check EVERY line that grants to the RO role for any write verb.
    for line in sql.splitlines():
        if f'"{RO}"' in line and line.strip().upper().startswith(("GRANT", "ALTER DEFAULT")):
            for verb in _WRITE_VERBS:
                assert verb not in line.upper(), f"RO granted {verb}: {line!r}"


def test_rw_is_dml_only():
    _, sql = _capture()
    assert f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{RW}";' in sql
    assert f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{RW}";' in sql


def test_no_table_ddl_or_ownership_anywhere():
    _, sql = _capture()
    for forbidden in (
        "CREATE TABLE",
        "DROP ",
        "ALTER TABLE",
        "GRANT ALL",
        "OWNER TO",
        "CREATE DATABASE",
    ):
        assert forbidden not in sql, f"unexpected DDL/ownership token: {forbidden!r}"


def test_grant_connect_and_usage_present_for_both_roles():
    # Drop either and BOTH roles can't connect / see the schema — feature dead.
    _, sql = _capture()
    assert f'GRANT CONNECT ON DATABASE "{DB}" TO "{RO}", "{RW}";' in sql
    assert f'GRANT USAGE ON SCHEMA public TO "{RO}", "{RW}";' in sql


def test_fresh_roles_created_least_privilege():
    result, sql = _capture()  # both roles fresh
    for role in (RO, RW):
        assert (
            f'CREATE ROLE "{role}" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD' in sql
        )
    assert result["ro"]["status"] == "created"
    assert result["rw"]["status"] == "created"


def test_ro_and_rw_get_distinct_passwords():
    result, _ = _capture()
    assert result["ro"]["password"] == "RO_PW"
    assert result["rw"]["password"] == "RW_PW"
    assert result["ro"]["password"] != result["rw"]["password"]


# ── password lifecycle: rotate on create only, preserve on re-apply ────────


def test_existing_roles_preserved_no_create_no_password():
    # The #1 fix: an existing role is NOT recreated or password-rotated, so its
    # DSN in .env stays valid and a cached-build re-apply can't break the sidecar.
    result, sql = _capture(ro_exists=True, rw_exists=True)
    assert "CREATE ROLE" not in sql
    assert result["ro"]["password"] is None
    assert result["rw"]["password"] is None
    assert result["ro"]["status"] == "exists"
    # grants ARE still re-applied (idempotent, covers newly-added tables)
    assert f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{RO}";' in sql


def test_partial_existing_creates_only_the_missing_role():
    # NB: _generate_password side_effect is consumed positionally — with RO
    # preserved, the single call is for RW and yields side_effect[0] ("RO_PW").
    # The value label is positional, not role-bound; we only assert presence.
    result, sql = _capture(ro_exists=True, rw_exists=False)
    assert f'CREATE ROLE "{RO}"' not in sql
    assert f'CREATE ROLE "{RW}"' in sql
    assert result["ro"]["password"] is None  # preserved
    assert result["rw"]["password"] is not None  # freshly minted


# ── hardening from adversarial review ──────────────────────────────────────


def test_on_error_stop_precedes_grants():
    # Without ON_ERROR_STOP a mid-batch GRANT failure exits 0 → false success.
    _, sql = _capture()
    assert "\\set ON_ERROR_STOP on" in sql
    assert sql.index("\\set ON_ERROR_STOP on") < sql.index("GRANT")


def test_switches_into_app_db_before_schema_grants():
    _, sql = _capture()
    assert f"\\c {DB}" in sql
    assert sql.index(f"\\c {DB}") < sql.index("ON ALL TABLES IN SCHEMA public")


def test_default_privileges_target_real_owner_not_assumed_db_name():
    # Legacy / manually-created DB owned by postgres: the lookup must be used so
    # ALTER DEFAULT PRIVILEGES FOR ROLE names a role that actually exists.
    _, sql = _capture(owner="postgres")
    assert 'ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA public' in sql
    assert f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DB}"' not in sql


def test_all_three_default_privilege_statements_emitted_when_owner_known():
    # Loose `in` would still pass if 2 of 3 were dropped — count them.
    _, sql = _capture()
    assert sql.count("ALTER DEFAULT PRIVILEGES FOR ROLE") == 3


@pytest.mark.parametrize("owner", ["", 'evil"; DROP DATABASE x; --'])
def test_unresolvable_owner_omits_default_privileges_never_guesses(owner):
    # #3 fix: empty or injection-laden owner -> _db_owner returns None ->
    # DEFAULT PRIVILEGES omitted entirely (existing tables still granted); no
    # statement referencing a maybe-nonexistent role, no injection reaches SQL.
    _, sql = _capture(owner=owner)
    assert "ALTER DEFAULT PRIVILEGES" not in sql
    assert "DROP DATABASE" not in sql
    assert (
        f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{RO}";' in sql
    )  # existing tables covered


def test_role_exists_parses_pg_roles_row():
    # The real _role_exists (mocked away in _capture) — exercise its parsing.
    for ret, expected in [("1", True), ("1\n", True), ("", False), ("0", False)]:
        with mock.patch.object(pg, "_run_sql", return_value=ret) as m:
            assert pg._role_exists("some_role", pg.POSTGRES_CONTAINER) is expected
            assert "pg_roles" in m.call_args.args[0]


def test_existing_roles_with_unresolvable_owner_still_grant_existing_tables():
    # Combined path: roles preserved AND owner unknown → no CREATE, no default
    # privileges, but existing tables are still granted (feature not silently dead).
    result, sql = _capture(ro_exists=True, rw_exists=True, owner="")
    assert "CREATE ROLE" not in sql
    assert "ALTER DEFAULT PRIVILEGES" not in sql
    assert f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{RO}";' in sql
    assert result["ro"]["password"] is None


def test_drop_database_also_drops_watchdog_roles():
    # drop+recreate must not orphan the wd roles (else a reset .env is left with
    # no DSN because the next apply sees them as existing).
    calls: list[str] = []

    def fake_run_sql(sql, container=pg.POSTGRES_CONTAINER, dry_run=False):
        calls.append(sql)
        return "1" if "pg_database" in sql else ""  # DB exists → proceed to drop

    with (
        mock.patch.object(pg, "_run_sql", side_effect=fake_run_sql),
        mock.patch.object(pg, "unregister_allocation"),
        mock.patch.object(pg, "unregister_postgres_plan"),
    ):
        pg.drop_database(DB)
    drop_sql = next(c for c in calls if "DROP DATABASE" in c)
    assert f'DROP ROLE IF EXISTS "{RO}";' in drop_sql
    assert f'DROP ROLE IF EXISTS "{RW}";' in drop_sql


def test_drop_database_cleans_orphan_wd_roles_when_db_absent():
    # The DB is already gone (not_found) but the wd roles may linger — cleanup
    # must still run so a drop+recreate isn't stuck with orphaned roles.
    calls: list[str] = []

    def fake_run_sql(sql, container=pg.POSTGRES_CONTAINER, dry_run=False):
        calls.append(sql)
        return ""  # pg_database check → "" → DB does NOT exist

    with mock.patch.object(pg, "_run_sql", side_effect=fake_run_sql):
        result = pg.drop_database(DB)
    assert result["status"] == "not_found"
    drop_role_calls = [c for c in calls if "DROP ROLE IF EXISTS" in c]
    assert any(f'"{RO}"' in c and f'"{RW}"' in c for c in drop_role_calls)


# ── dry-run + guards ───────────────────────────────────────────────────────


def test_dry_run_runs_no_sql():
    with (
        mock.patch.object(pg, "_run_sql") as m_run,
        mock.patch.object(pg, "_generate_password", return_value="PWPWPW"),
    ):
        result = pg.create_watchdog_roles(DB, dry_run=True)
    m_run.assert_not_called()  # not even the owner / existence lookups
    assert result["ro"]["password"] is None
    assert result["ro"]["status"] == "dry_run"


@pytest.mark.parametrize(
    "name_len, ok",
    [(57, True), (58, False)],  # role = name + "_wd_ro" (6): 63 ok, 64 rejected
)
def test_role_name_length_boundary(name_len, ok):
    name = "a" * name_len
    if ok:
        assert pg._wd_role_names(name) == (f"{name}_wd_ro", f"{name}_wd_rw")
    else:
        with pytest.raises(ValueError, match="63-char"):
            pg._wd_role_names(name)


# ── registrar wiring (infrastructure.py) ───────────────────────────────────


def _provision(
    provision_watchdog_roles: bool,
    *,
    dry_run: bool = False,
    rename_guard: bool = False,
    fresh_db: bool = False,
    ro_password: str | None = "RO_PW",
):
    """Drive _provision_postgres with the DB drivers mocked; return
    (deployer_mock, create_watchdog_roles_mock)."""
    derived = "calendar_engine"

    def fake_create(db_name, **_kw):
        # fresh_db=True → a password is returned (exercises the DATABASE_URL branch).
        if fresh_db:
            return {"status": "created", "database": db_name, "user": db_name, "password": "APP_PW"}
        return {"status": "exists", "database": db_name}

    def fake_roles(db_name, dry_run=False, **_kw):
        if dry_run:  # respect the real dry-run contract (no passwords)
            return {
                "ro": {"user": f"{db_name}_wd_ro", "password": None, "status": "dry_run"},
                "rw": {"user": f"{db_name}_wd_rw", "password": None, "status": "dry_run"},
            }
        return {
            "ro": {
                "user": f"{db_name}_wd_ro",
                "password": ro_password,
                "status": "created" if ro_password else "exists",
            },
            "rw": {"user": f"{db_name}_wd_rw", "password": "RW_PW", "status": "created"},
        }

    def fake_exists(n, **_kw):
        return rename_guard and n == derived

    spec: dict = {"depends": {"postgres": "pinned_target"}} if rename_guard else {}
    prov = InfrastructureProvisioner(deployer=mock.MagicMock())
    ctx = DeploymentContext(spec_path=Path("specs/services/x.yaml"))
    with (
        mock.patch("fabrik.drivers.postgres.create_database", side_effect=fake_create),
        mock.patch("fabrik.drivers.postgres.database_exists", side_effect=fake_exists),
        mock.patch(
            "fabrik.drivers.postgres.create_watchdog_roles", side_effect=fake_roles
        ) as m_roles,
    ):
        prov._provision_postgres(
            "calendar-engine",
            spec,
            ctx,
            dry_run=dry_run,
            provision_watchdog_roles=provision_watchdog_roles,
        )
    return prov.deployer, m_roles


def _injected(deployer) -> dict:
    merged: dict = {}
    for call in deployer.inject_env.call_args_list:
        merged.update(call.args[1] if len(call.args) > 1 else call.kwargs.get("env_vars", {}))
    return merged


def test_registrar_injects_both_dsns_when_watchdog_on():
    deployer, m_roles = _provision(provision_watchdog_roles=True)
    m_roles.assert_called_once()
    env = _injected(deployer)
    assert (
        env["WATCHDOG_DB_URL_RO"]
        == "postgresql://calendar_engine_wd_ro:RO_PW@postgres-main:5432/calendar_engine"
    )
    assert (
        env["WATCHDOG_DB_URL_RW"]
        == "postgresql://calendar_engine_wd_rw:RW_PW@postgres-main:5432/calendar_engine"
    )


def test_registrar_omits_ro_dsn_when_role_preexisting():
    # Preserve path: RO already existed (password None) → only RW DSN injected,
    # RO's existing .env value is left untouched by inject_env's merge.
    deployer, _ = _provision(provision_watchdog_roles=True, ro_password=None)
    env = _injected(deployer)
    assert "WATCHDOG_DB_URL_RO" not in env
    assert env["WATCHDOG_DB_URL_RW"].endswith("/calendar_engine")


def test_registrar_fresh_db_injects_database_url_and_watchdog_dsns():
    # A fresh create must inject DATABASE_URL AND the watchdog DSNs (no key clash).
    deployer, _ = _provision(provision_watchdog_roles=True, fresh_db=True)
    env = _injected(deployer)
    assert (
        env["DATABASE_URL"]
        == "postgresql://calendar_engine:APP_PW@postgres-main:5432/calendar_engine"
    )
    assert "WATCHDOG_DB_URL_RO" in env and "WATCHDOG_DB_URL_RW" in env


def test_registrar_skips_roles_when_watchdog_off():
    deployer, m_roles = _provision(provision_watchdog_roles=False)
    m_roles.assert_not_called()
    env = _injected(deployer)
    assert "WATCHDOG_DB_URL_RO" not in env
    assert "WATCHDOG_DB_URL_RW" not in env


def test_registrar_dry_run_provisions_but_never_injects():
    deployer, m_roles = _provision(provision_watchdog_roles=True, dry_run=True)
    assert m_roles.call_args.kwargs.get("dry_run") is True
    env = _injected(deployer)
    assert "WATCHDOG_DB_URL_RO" not in env
    assert "WATCHDOG_DB_URL_RW" not in env


def test_registrar_rename_guard_skips_watchdog_roles(monkeypatch):
    monkeypatch.delenv("FABRIK_ALLOW_DB_RENAME", raising=False)  # else the guard is bypassed
    deployer, m_roles = _provision(provision_watchdog_roles=True, rename_guard=True)
    m_roles.assert_not_called()
    assert "WATCHDOG_DB_URL_RO" not in _injected(deployer)


def test_registrar_records_watchdog_roles_resource():
    # Surface the provisioning in the deploy resource summary (not fail-silent).
    def fake_create(db_name, **_kw):
        return {"status": "exists", "database": db_name}

    def fake_roles(db_name, dry_run=False, **_kw):
        return {
            "ro": {"user": f"{db_name}_wd_ro", "password": "RO_PW", "status": "created"},
            "rw": {"user": f"{db_name}_wd_rw", "password": "RW_PW", "status": "created"},
        }

    prov = InfrastructureProvisioner(deployer=mock.MagicMock())
    ctx = DeploymentContext(spec_path=Path("specs/services/x.yaml"))
    with (
        mock.patch("fabrik.drivers.postgres.create_database", side_effect=fake_create),
        mock.patch("fabrik.drivers.postgres.database_exists", side_effect=lambda *a, **k: False),
        mock.patch("fabrik.drivers.postgres.create_watchdog_roles", side_effect=fake_roles),
    ):
        prov._provision_postgres(
            "calendar-engine", {}, ctx, dry_run=False, provision_watchdog_roles=True
        )
    recs = ctx.get_resources_by_type("watchdog-db-roles")
    assert len(recs) == 1
    assert recs[0].metadata.get("status") == "provisioned"


# ── review hardening: injection guard, H1 log redaction, H2 create/grant split ──


def test_injection_shaped_db_name_rejected():
    """Mirror the subagent path: an injection-shaped db_name is rejected BEFORE it
    can reach the role SQL. Delegated to `_validate_identifier` via _wd_role_names."""
    with pytest.raises(ValueError):
        pg._wd_role_names("calendar; DROP TABLE users; --")


def test_ssh_debug_log_redacts_base64_payload():
    """H1: a role PASSWORD ships as `echo <base64> | base64 -d | … psql`; the SSH
    DEBUG log must MASK the base64 so enabling DEBUG can't leak the password."""
    from fabrik.drivers.ssh import _redact

    secret_cmd = (
        "echo Q1JFQVRFIFJPTEUgcm8gUEFTU1dPUkQgJ3N1cGVyc2VjcmV0Jw== "
        "| base64 -d | sudo docker exec -i postgres-main psql -U postgres -tA"
    )
    out = _redact(secret_cmd)
    assert "Q1JFQVRF" not in out  # the base64 blob is gone
    assert "<redacted-base64>" in out
    assert "sudo docker exec" in out  # the non-secret tail is preserved


def test_create_and_grant_are_separate_run_sql_calls():
    """H2: CREATE ROLE and the GRANTs run in SEPARATE _run_sql calls, so a GRANT
    failure can't orphan a just-created role with a lost password inside one batch."""
    calls: list[str] = []

    def fake(sql, container=pg.POSTGRES_CONTAINER, dry_run=False):
        calls.append(sql)
        return DB if "pg_get_userbyid" in sql else ""

    with (
        mock.patch.object(pg, "_run_sql", side_effect=fake),
        mock.patch.object(pg, "_role_exists", return_value=False),
        mock.patch.object(pg, "_generate_password", side_effect=["RO_PW", "RW_PW"]),
    ):
        pg.create_watchdog_roles(DB)

    create_calls = [c for c in calls if "CREATE ROLE" in c]
    grant_calls = [c for c in calls if "GRANT CONNECT" in c]
    assert len(create_calls) == 2  # ro + rw, each its own atomic invocation
    assert all("GRANT CONNECT" not in c for c in create_calls)  # no grants bundled with a CREATE
    # each CREATE must carry ON_ERROR_STOP — else a failed CREATE exits 0 (psql
    # via stdin) and we'd false-succeed into injecting a mismatched password.
    assert all("ON_ERROR_STOP" in c for c in create_calls)
    assert len(grant_calls) == 1
    assert "CREATE ROLE" not in grant_calls[0]  # no CREATE bundled in the grant batch
