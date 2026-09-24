"""T02 — the ``<db>_app`` role driver (ensure_app_role / probe_app_role / drop).

Fake-``_run_sql`` unit tests over the generated SQL and control flow — the repo's
driver-test pattern (``test_payments_ingest_role.py``). The PostgreSQL BEHAVIOUR
(a real LOGIN session as the app role being refused) is proven in
``tests/test_app_role_real_pg.py``.
"""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest

import fabrik.drivers.postgres as pg

DB = "ti"
APP = "ti_app"


def _capture(
    *, owner: str | None = DB, exists: bool = False, reset: bool = False
) -> tuple[dict, list[str]]:
    calls: list[str] = []

    def fake_run_sql(sql: str, container: str = pg.POSTGRES_CONTAINER, dry_run: bool = False):
        calls.append(sql)
        return ""

    with (
        patch.object(pg, "_db_owner", return_value=owner),
        patch.object(pg, "_role_exists", return_value=exists),
        patch.object(pg, "_run_sql", side_effect=fake_run_sql),
    ):
        res = pg.ensure_app_role(DB, reset_password=reset)
    return res, calls


def test_app_role_name_and_63_char_guard() -> None:
    assert pg.app_role_name("ti") == "ti_app"
    assert len(pg.app_role_name("x" * 59)) == 63
    with pytest.raises(ValueError, match="63-char"):
        pg.app_role_name("x" * 60)
    with pytest.raises(ValueError):
        pg.app_role_name("ti; DROP ROLE postgres")


def test_fresh_role_created_alone_then_grants_batch() -> None:
    res, calls = _capture()
    assert len(calls) == 2
    create_sql, grants = calls
    # CREATE ROLE in its OWN call, least privilege, CSPRNG password, no grant inside.
    assert (
        f'CREATE ROLE "{APP}" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS'
        in create_sql
    )
    assert create_sql.startswith("\\set ON_ERROR_STOP on\n")
    m = re.search(r"PASSWORD '([^']*)'", create_sql)
    assert m and re.fullmatch(r"[a-zA-Z0-9]{32}", m.group(1))
    assert "GRANT" not in create_sql
    # The grants batch: ON_ERROR_STOP, then \c into the app DB before any statement.
    lines = grants.splitlines()
    assert lines[0] == "\\set ON_ERROR_STOP on"
    assert lines[1] == f"\\c {DB}"
    assert f'GRANT CONNECT ON DATABASE "{DB}" TO "{APP}";' in grants
    # Every owner schema: USAGE (never CREATE), DML, sequences, default privileges for both.
    assert "n.nspname = 'public'" in grants  # public always, plus the schemas the owner owns
    assert f"nspowner = (SELECT oid FROM pg_roles WHERE rolname = '{DB}')" in grants
    assert f'GRANT USAGE ON SCHEMA %I TO "{APP}"' in grants
    assert f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO "{APP}"' in grants
    assert f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO "{APP}"' in grants
    assert (
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DB}" IN SCHEMA %I '
        f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{APP}"'
    ) in grants
    assert (
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DB}" IN SCHEMA %I '
        f'GRANT USAGE, SELECT ON SEQUENCES TO "{APP}"'
    ) in grants
    assert not re.search(rf'GRANT[^;\']*\bCREATE\b[^;\']*TO "{APP}"', grants)
    assert res == {"user": APP, "owner": DB, "password": m.group(1), "status": "created"}


def test_existing_role_no_create_no_password_reset_alters_alone() -> None:
    res, calls = _capture(exists=True)
    assert not any("CREATE ROLE" in c or "PASSWORD" in c for c in calls)
    assert len(calls) == 1 and f'GRANT CONNECT ON DATABASE "{DB}" TO "{APP}";' in calls[0]
    assert res == {"user": APP, "owner": DB, "password": None, "status": "exists"}

    res, calls = _capture(exists=True, reset=True)
    assert len(calls) == 2
    alter_sql, grants = calls
    assert f'ALTER ROLE "{APP}" WITH PASSWORD' in alter_sql
    assert "GRANT" not in alter_sql and "CREATE ROLE" not in alter_sql
    assert "PASSWORD" not in grants
    pw = re.search(r"PASSWORD '([^']*)'", alter_sql).group(1)
    assert re.fullmatch(r"[a-zA-Z0-9]{32}", pw)
    assert res == {"user": APP, "owner": DB, "password": pw, "status": "reset"}


@pytest.mark.parametrize("owner", [None, "postgres"])
def test_unusable_owner_raises_before_any_sql(owner) -> None:
    for fn in (pg.ensure_app_role, pg.probe_app_role):
        with (
            patch.object(pg, "_db_owner", return_value=owner),
            patch.object(pg, "_role_exists", return_value=False) as exists,
            patch.object(pg, "_run_sql") as run,
        ):
            with pytest.raises(pg.AppRoleError) as exc:
                fn(DB)
        assert DB in str(exc.value) and str(owner) in str(exc.value)
        run.assert_not_called()
        exists.assert_not_called()
    assert issubclass(pg.AppRoleError, RuntimeError)


def test_grants_batch_public_create_audit_block_and_memberships() -> None:
    _, calls = _capture(owner="ti_owner")
    grants = calls[-1]
    # Owner keeps CREATE on public BEFORE PUBLIC loses it.
    g = grants.index('GRANT CREATE ON SCHEMA public TO "ti_owner";')
    r = grants.index("REVOKE CREATE ON SCHEMA public FROM PUBLIC;")
    assert g < r
    # The to_regclass-guarded audit_log block.
    assert "IF to_regclass('public.audit_log') IS NOT NULL THEN" in grants
    assert 'ALTER TABLE public.audit_log OWNER TO "ti_owner"' in grants
    assert f'REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_log FROM PUBLIC, "{APP}"' in grants
    assert "rolname = 'ti_wd_rw'" in grants
    assert 'REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_log FROM "ti_wd_rw"' in grants
    for grp in ("anon", "authenticated", "service_role"):
        assert f"rolname = '{grp}'" in grants
        assert f'REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_log FROM "{grp}"' in grants
        assert f'GRANT "{grp}" TO "{APP}" WITH INHERIT FALSE, SET TRUE' in grants
    # The revokes follow the blanket DML grant, and INSERT/SELECT is granted back last.
    assert grants.index("ON ALL TABLES IN SCHEMA") < grants.index("REVOKE UPDATE, DELETE")
    assert f'GRANT INSERT, SELECT ON public.audit_log TO "{APP}"' in grants
    # Memberships only where the OWNER is a member.
    assert "m.member = (SELECT oid FROM pg_roles WHERE rolname = 'ti_owner')" in grants
    # No other role is ever granted TO the app role (a role grant has no ON clause).
    role_grants = re.findall(rf'GRANT\s+("?\w+"?)\s+TO\s+"{APP}"', grants)
    assert sorted(x.strip('"') for x in role_grants) == ["anon", "authenticated", "service_role"]


def test_dry_run_sends_no_sql() -> None:
    with patch.object(pg, "_run_sql") as run, patch.object(pg, "_db_owner") as owner:
        res = pg.ensure_app_role(DB, dry_run=True)
    run.assert_not_called()
    owner.assert_not_called()
    assert res["status"] == "dry_run" and res["password"] is None and res["user"] == APP


def test_drop_database_drops_app_role_after_database() -> None:
    calls: list[str] = []

    def fake_run_sql(sql, container=pg.POSTGRES_CONTAINER, dry_run=False):
        calls.append(sql)
        return "1" if "pg_database" in sql else ""

    with (
        patch.object(pg, "_run_sql", side_effect=fake_run_sql),
        patch.object(pg, "unregister_allocation"),
        patch.object(pg, "unregister_postgres_plan"),
    ):
        pg.drop_database(DB)
    drop_sql = next(c for c in calls if "DROP DATABASE" in c)
    assert drop_sql.index("DROP DATABASE") < drop_sql.index(f'DROP ROLE IF EXISTS "{APP}";')


def test_drop_database_drops_orphan_app_role() -> None:
    calls: list[str] = []

    def fake_run_sql(sql, container=pg.POSTGRES_CONTAINER, dry_run=False):
        calls.append(sql)
        return ""

    with patch.object(pg, "_run_sql", side_effect=fake_run_sql):
        assert pg.drop_database(DB)["status"] == "not_found"
    assert any(f'DROP ROLE IF EXISTS "{APP}";' in c for c in calls)


def _probe(output: str) -> tuple[list[str], list[str]]:
    calls: list[str] = []

    def fake_run_sql(sql, container=pg.POSTGRES_CONTAINER, dry_run=False):
        calls.append(sql)
        return output

    with (
        patch.object(pg, "_db_owner", return_value=DB),
        patch.object(pg, "_run_sql", side_effect=fake_run_sql),
    ):
        return pg.probe_app_role(DB), calls


def test_probe_reports_each_violation_and_ignores_connection_line() -> None:
    out = "\n".join(
        [
            f'You are now connected to database "{DB}" as user "postgres".',
            f"probe|table_owner|public.widgets|{APP}",
            "probe|audit_priv|authenticated|UPDATE",
            "probe|schema_create|PUBLIC",
            "probe|done",
        ]
    )
    failures, calls = _probe(out)
    assert len(failures) == 3, failures
    assert any("public.widgets" in f and APP in f for f in failures)
    assert any("authenticated" in f and "UPDATE" in f and "audit_log" in f for f in failures)
    assert any("PUBLIC" in f and "CREATE" in f for f in failures)
    lines = calls[0].splitlines()
    assert lines[0] == "\\set ON_ERROR_STOP on" and lines[1] == f"\\c {DB}"
    assert calls[0].rstrip().endswith("SELECT 'probe|done';")
    # non-mutating: every statement in the batch (meta-commands aside) is a SELECT
    body = "\n".join(ln for ln in calls[0].splitlines() if not ln.startswith("\\"))
    stmts = [s.strip() for s in body.split(";") if s.strip()]
    assert stmts and all(s.upper().startswith("SELECT") for s in stmts), stmts


def test_probe_all_clear_and_incomplete() -> None:
    failures, _ = _probe(f'You are now connected to database "{DB}".\nprobe|done')
    assert failures == []
    failures, _ = _probe(f'You are now connected to database "{DB}".\n')
    assert len(failures) == 1 and failures[0].startswith("probe incomplete")
    failures, _ = _probe("")
    assert len(failures) == 1 and failures[0].startswith("probe incomplete")


def test_probe_run_sql_error_is_incomplete_not_raise() -> None:
    with (
        patch.object(pg, "_db_owner", return_value=DB),
        patch.object(pg, "_run_sql", side_effect=RuntimeError("SSH failed (rc=3): boom")),
    ):
        failures = pg.probe_app_role(DB)
    assert len(failures) == 1 and failures[0].startswith("probe incomplete")
