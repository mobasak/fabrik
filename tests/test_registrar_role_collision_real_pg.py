"""Registrar role names cannot capture another project's role (W-f599a88c), on real PostgreSQL.

Every per-project role is ``<db>_<suffix>`` and every database's owner role carries the database's own name,
so a database named ``ti_wd_rw`` has an owner role with exactly project ``ti``'s watchdog name. Both directions
are refused before anything is created, altered or granted:

* the registrar meets a role of its name that owns a database (or objects outside its own database) — the
  watchdog, subagent and payments paths raise and grant it nothing;
* ``create_database`` meets an existing role named like the new database that holds grants or memberships —
  a live registrar role, never a leftover owner of a dropped database — and raises before the database
  exists, leaving that role's password and ownership untouched.

Opt-in like the sibling real-PG suites: skipped without docker unless ``FABRIK_REQUIRE_REAL_PG=1``.
"""

from __future__ import annotations

from unittest import mock

import pytest

import fabrik.drivers.postgres as pg
from tests.test_app_role_real_pg import ScratchPg, scratch_pg

DB = "ti"


def _create_database(s: ScratchPg, name: str):
    with (
        s.as_driver(),
        mock.patch.object(pg, "register_allocation"),
        mock.patch.object(pg, "register_postgres_plan"),
    ):
        return pg.create_database(name, name)


def _watchdog(s: ScratchPg, db: str = DB):
    with s.as_driver():
        return pg.create_watchdog_roles(db)


def _one(s: ScratchPg, sql: str) -> str:
    return s.run_sql(sql).strip()


def test_a_clean_registrar_role_is_not_foreign() -> None:
    with scratch_pg() as s:
        s.run_sql(f'CREATE DATABASE "{DB}";')
        _watchdog(s)
        with s.as_driver():
            assert pg._foreign_role_reasons(f"{DB}_wd_rw", own_db=DB) == []


def test_a_database_owner_role_is_foreign_and_the_watchdog_grants_it_nothing() -> None:
    """DB-first: a database named `ti_wd_rw` exists (its owner role is `ti_wd_rw`); project `ti`'s watchdog
    must refuse to treat that owner as its RW role and give it nothing of `ti`."""
    with scratch_pg() as s:
        s.run_sql(f'CREATE DATABASE "{DB}";')
        _create_database(s, f"{DB}_wd_rw")
        with s.as_driver():
            reasons = pg._foreign_role_reasons(f"{DB}_wd_rw", own_db=DB)
        assert any(r.startswith(f"owns database {DB}_wd_rw") for r in reasons), reasons
        with pytest.raises(RuntimeError, match="not this registrar's"):
            _watchdog(s)
        # nothing of `ti` reached the foreign owner, and the RO sibling was not created either
        assert f"{DB}_wd_rw" not in _one(
            s, f"SELECT coalesce(datacl::text, '') FROM pg_database WHERE datname = '{DB}'"
        )
        assert _one(s, f"SELECT count(*) FROM pg_roles WHERE rolname = '{DB}_wd_ro'") == "0"


def test_create_database_refuses_to_capture_a_live_registrar_role() -> None:
    """Role-first: project `ti`'s watchdog roles exist; a new database named `ti_wd_ro` must not reset that
    role's password, make it an owner, or hand the new project a credential that can read `ti`."""
    with scratch_pg() as s:
        s.run_sql(f'CREATE DATABASE "{DB}";')
        minted = _watchdog(s)
        ro_pw = minted["ro"]["password"]
        with pytest.raises(RuntimeError, match="not this registrar's"):
            _create_database(s, f"{DB}_wd_ro")
        assert _one(s, f"SELECT count(*) FROM pg_database WHERE datname = '{DB}_wd_ro'") == "0"
        # the victim role still logs in with its own password and owns nothing
        assert s.login_sql(f"{DB}_wd_ro", ro_pw, "SELECT 1;", db=DB) == "1"
        assert (
            _one(
                s,
                f"SELECT count(*) FROM pg_database d JOIN pg_roles r ON r.oid = d.datdba WHERE r.rolname = '{DB}_wd_ro'",
            )
            == "0"
        )


def test_create_database_still_adopts_a_leftover_owner_of_a_dropped_database() -> None:
    """The legitimate case the existing-role branch exists for: the database was dropped, its owner role
    was left behind with no grants — re-creating the database re-adopts it with a fresh password."""
    with scratch_pg() as s:
        first = _create_database(s, "solo")
        s.run_sql('DROP DATABASE "solo";')
        again = _create_database(s, "solo")
        assert again["status"] == "created" and again["password"] != first["password"]
        assert s.login_sql("solo", again["password"], "SELECT 1;", db="solo") == "1"


def test_a_role_owning_a_table_in_another_database_is_foreign() -> None:
    with scratch_pg() as s:
        s.run_sql(f'CREATE DATABASE "{DB}";')
        s.run_sql('CREATE DATABASE "other";')
        s.run_sql(f'CREATE ROLE "{DB}_wd_rw" LOGIN;')
        s.run_sql(
            f'\\c other\nCREATE TABLE elsewhere (id int);\nALTER TABLE elsewhere OWNER TO "{DB}_wd_rw";'
        )
        with s.as_driver():
            reasons = pg._foreign_role_reasons(f"{DB}_wd_rw", own_db=DB)
        assert any("object(s) in database other" in r for r in reasons), reasons


def test_a_payments_role_owning_a_table_elsewhere_is_refused_untouched() -> None:
    with scratch_pg() as s:
        s.run_sql(f'CREATE DATABASE "{DB}";')
        s.run_sql('CREATE DATABASE "other";')
        role = f"{DB}_payments_ingest"
        s.run_sql(f'CREATE ROLE "{role}" LOGIN CREATEDB;')
        s.run_sql(
            f'\\c other\nCREATE TABLE elsewhere (id int);\nALTER TABLE elsewhere OWNER TO "{role}";'
        )
        with s.as_driver(), pytest.raises(RuntimeError, match="not this registrar's"):
            pg.mint_payments_role(DB, "ingest")
        # refused before the narrowing ALTER: the attribute it would have stripped is still there
        assert _one(s, f"SELECT rolcreatedb FROM pg_roles WHERE rolname = '{role}'") == "t"


def test_an_object_in_the_roles_own_database_is_not_foreign() -> None:
    """The own-database exemption: a live session of the watchdog RW role may own a temp table (or the
    project may hand it an object) in the project's own database — never a reason to refuse re-apply."""
    with scratch_pg() as s:
        s.run_sql(f'CREATE DATABASE "{DB}";')
        _watchdog(s)
        s.run_sql(f'\\c {DB}\nCREATE TABLE mine (id int);\nALTER TABLE mine OWNER TO "{DB}_wd_rw";')
        with s.as_driver():
            assert pg._foreign_role_reasons(f"{DB}_wd_rw", own_db=DB) == []
            # without the exemption the same object would read as foreign
            assert any(
                f"in database {DB}" in r
                for r in pg._foreign_role_reasons(f"{DB}_wd_rw", own_db=None)
            )
        assert _watchdog(s)["rw"]["status"] == "exists"


def test_create_database_refuses_a_role_that_is_a_member_of_another() -> None:
    with scratch_pg() as s:
        s.run_sql('CREATE ROLE "grp" NOLOGIN;')
        s.run_sql('CREATE ROLE "solo" LOGIN;')
        s.run_sql('GRANT "grp" TO "solo";')
        with s.as_driver():
            assert "is a member of grp" in pg._foreign_role_reasons(
                "solo", own_db=None, any_dependency=True
            )
        with pytest.raises(RuntimeError, match="is a member of grp"):
            _create_database(s, "solo")
        assert _one(s, "SELECT count(*) FROM pg_database WHERE datname = 'solo'") == "0"
