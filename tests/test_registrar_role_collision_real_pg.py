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


# --- W-98debf05: a payments role escalated out of band is refused on re-apply, never stripped (D-1105) ---------
PAY = f"{DB}_payments_ingest"


def _mint(s: ScratchPg):
    with s.as_driver():
        return pg.mint_payments_role(DB, "ingest")


def _mint_clean(s: ScratchPg) -> None:
    s.run_sql(f'CREATE DATABASE "{DB}";')
    assert _mint(s)["status"] == "created"
    s.run_sql(f'ALTER ROLE "{PAY}" CREATEDB;')  # the attribute the narrowing ALTER would strip


def test_a_payments_role_made_a_member_of_another_role_is_refused_untouched() -> None:
    with scratch_pg() as s:
        _mint_clean(s)
        s.run_sql(f'GRANT pg_write_all_data TO "{PAY}";')
        with pytest.raises(RuntimeError, match="is a member of pg_write_all_data"):
            _mint(s)
        # left as it is (D-1105): the membership stays and the ALTER never ran
        member = (
            "SELECT count(*) FROM pg_auth_members m JOIN pg_roles g ON g.oid = m.roleid "
            f"WHERE g.rolname = 'pg_write_all_data' AND m.member = (SELECT oid FROM pg_roles WHERE rolname = '{PAY}')"
        )
        assert _one(s, member) == "1"
        assert _one(s, f"SELECT rolcreatedb FROM pg_roles WHERE rolname = '{PAY}'") == "t"


def test_a_payments_role_owning_a_table_in_its_own_database_is_refused_untouched() -> None:
    with scratch_pg() as s:
        _mint_clean(s)
        s.run_sql(f'\\c {DB}\nCREATE TABLE mine (id int);\nALTER TABLE mine OWNER TO "{PAY}";')
        with pytest.raises(RuntimeError, match=f"in its own database {DB}"):
            _mint(s)
        owner = f"\\c {DB}\nSELECT tableowner FROM pg_tables WHERE tablename = 'mine';"
        assert _one(s, owner).splitlines()[-1] == PAY
        assert _one(s, f"SELECT rolcreatedb FROM pg_roles WHERE rolname = '{PAY}'") == "t"


def test_a_payments_role_holding_a_live_temp_table_is_re_applied() -> None:
    """A live session of the role may hold a temp table and a temp function in its own database; neither is an
    escalation (the function has no pg_class row, so only the pg_temp exclusion keeps it out)."""
    import subprocess
    import time

    with scratch_pg() as s:
        _mint_clean(s)
        s.run_sql(f'GRANT TEMP ON DATABASE "{DB}" TO "{PAY}";')
        # a second session holds the temp table open while the re-apply's guard runs
        holder = subprocess.Popen(
            ["docker", "exec", "-i", s.container, "psql", "-U", "postgres", "-tA"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        try:
            holder.stdin.write(
                f'\\c {DB}\nSET ROLE "{PAY}";\nCREATE TEMP TABLE t1 (x int);\n'
                "CREATE FUNCTION pg_temp.tf() RETURNS int LANGUAGE sql AS 'SELECT 1';\n"
                "SELECT pg_sleep(60);\n"
            )
            holder.stdin.flush()
            live = (
                "SELECT count(*) FROM pg_shdepend WHERE deptype = 'o' "
                f"AND refobjid = (SELECT oid FROM pg_roles WHERE rolname = '{PAY}')"
            )
            deadline = time.time() + 20
            while _one(s, live) != "2":
                assert time.time() < deadline, "the temp table never appeared"
                time.sleep(0.2)
            assert _mint(s)["status"] == "exists"
        finally:
            holder.kill()
            holder.wait(timeout=10)
        assert _one(s, f"SELECT rolcreatedb FROM pg_roles WHERE rolname = '{PAY}'") == "f"


def test_a_payments_role_re_applied_after_its_own_grants_is_not_refused() -> None:
    with scratch_pg() as s:
        _mint_clean(s)
        with s.as_driver():
            pg.grant_payments_role(DB, "ingest")
        assert _mint(s)["status"] == "exists"
        assert _one(s, f"SELECT rolcreatedb FROM pg_roles WHERE rolname = '{PAY}'") == "f"


def test_a_superuser_payments_role_is_refused_and_left_a_superuser() -> None:
    with scratch_pg() as s:
        _mint_clean(s)
        s.run_sql(f'ALTER ROLE "{PAY}" SUPERUSER;')
        with pytest.raises(RuntimeError, match="is a superuser"):
            _mint(s)
        assert _one(s, f"SELECT rolsuper FROM pg_roles WHERE rolname = '{PAY}'") == "t"


def test_a_payments_role_granted_to_another_role_is_refused_untouched() -> None:
    """`GRANT <payments role> TO attacker` hands the money tables to another login (lateral escalation)."""
    with scratch_pg() as s:
        _mint_clean(s)
        s.run_sql('CREATE ROLE "attacker" LOGIN;')
        s.run_sql(f'GRANT "{PAY}" TO "attacker";')
        with pytest.raises(RuntimeError, match="is granted to attacker"):
            _mint(s)
        granted = (
            "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid "
            f"WHERE r.rolname = '{PAY}'"
        )
        assert _one(s, granted) == "1"
        assert _one(s, f"SELECT rolcreatedb FROM pg_roles WHERE rolname = '{PAY}'") == "t"


def test_a_payments_role_holding_a_grant_in_another_database_is_refused() -> None:
    with scratch_pg() as s:
        _mint_clean(s)
        s.run_sql('CREATE DATABASE "other";')
        s.run_sql(f'\\c other\nCREATE TABLE secret (id int);\nGRANT ALL ON secret TO "{PAY}";')
        with pytest.raises(
            RuntimeError, match="grant\\(s\\) or policy row\\(s\\) in database other"
        ):
            _mint(s)
        assert _one(s, f"SELECT rolcreatedb FROM pg_roles WHERE rolname = '{PAY}'") == "t"


def test_a_payments_role_owning_a_function_in_its_own_database_is_refused() -> None:
    """A non-relation object: the LEFT JOIN to pg_class finds no row, and it must still count."""
    with scratch_pg() as s:
        _mint_clean(s)
        s.run_sql(
            f"\\c {DB}\nCREATE FUNCTION handed() RETURNS int LANGUAGE sql AS 'SELECT 1';\n"
            f'ALTER FUNCTION handed() OWNER TO "{PAY}";'
        )
        with pytest.raises(RuntimeError, match=f"1 object\\(s\\) in its own database {DB}"):
            _mint(s)
        assert _one(s, f"SELECT rolcreatedb FROM pg_roles WHERE rolname = '{PAY}'") == "t"


@pytest.mark.parametrize(
    "grant",
    [
        'GRANT CONNECT ON DATABASE "other" TO "{role}";',
        'GRANT CREATE ON TABLESPACE pg_default TO "{role}";',
        'GRANT SET ON PARAMETER work_mem TO "{role}";',
    ],
)
def test_a_payments_role_holding_a_grant_on_a_shared_object_is_refused(grant: str) -> None:
    """Grants on shared objects carry no database (dbid 0); a join to pg_database alone never sees them."""
    with scratch_pg() as s:
        _mint_clean(s)
        s.run_sql('CREATE DATABASE "other";')
        s.run_sql(grant.format(role=PAY))
        with pytest.raises(
            RuntimeError, match="grant\\(s\\) on shared object\\(s\\) outside its own database"
        ):
            _mint(s)
        assert _one(s, f"SELECT rolcreatedb FROM pg_roles WHERE rolname = '{PAY}'") == "t"
