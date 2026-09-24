"""T02 — the ``<db>_app`` role against a REAL PostgreSQL 16 (throwaway container).

The driver's SQL runs verbatim (``_run_sql`` redirected into the container's
``psql -U postgres -tA``, the same flags the VPS path uses), and every refusal is
asserted from a real LOGIN session as the role under test (``psql -h 127.0.0.1
-U <role>`` with its password, TCP + scram inside the container). A superuser
``SET ROLE`` chain is checked against the SESSION user and proves nothing about
the app's membership, so it is never used for an assertion here.

``scratch_pg()`` is the shared helper (spine § Interfaces T02 → T05).
"""

from __future__ import annotations

import contextlib
import os
import secrets
import shutil
import string
import subprocess
import time
import uuid
from collections.abc import Callable, Iterator
from unittest.mock import patch

import pytest

import fabrik.drivers.postgres as pg

_IMAGE = "postgres:16"
_READY_TIMEOUT_S = 90


class ScratchPg:
    """Handles yielded by :func:`scratch_pg`."""

    def __init__(self, container: str) -> None:
        self.container = container

    def run_sql(self, sql: str) -> str:
        """Run ``sql`` as the superuser (``psql -U postgres -tA`` over stdin)."""
        res = subprocess.run(
            ["docker", "exec", "-i", self.container, "psql", "-U", "postgres", "-tA"],
            input=sql,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"superuser psql failed (rc={res.returncode}): {res.stderr.strip()}")
        return res.stdout.strip()

    def login_sql(self, role: str, password: str, sql: str, db: str = "postgres") -> str:
        """Run ``sql`` in a real LOGIN session as ``role`` (TCP, password auth).

        Raises RuntimeError carrying psql's stderr on any error (ON_ERROR_STOP).
        The password travels in the environment only; it is never printed.
        """
        env = {**os.environ, "PGPASSWORD": password}
        res = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                "-e",
                "PGPASSWORD",
                self.container,
                "psql",
                "-h",
                "127.0.0.1",
                "-U",
                role,
                "-d",
                db,
                "-v",
                "ON_ERROR_STOP=1",
                "-tA",
            ],
            input=sql,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=env,
        )
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip())
        return res.stdout.strip()

    def as_driver(self) -> contextlib.AbstractContextManager:
        """Patch ``pg._run_sql`` so the driver's own SQL runs in this container."""

        def _fake(sql: str, container: str = pg.POSTGRES_CONTAINER, dry_run: bool = False) -> str:
            return "" if dry_run else self.run_sql(sql)

        return patch.object(pg, "_run_sql", side_effect=_fake)


@contextlib.contextmanager
def scratch_pg() -> Iterator[ScratchPg]:
    """Start a throwaway ``postgres:16`` container; yield ``run_sql`` / ``login_sql``.

    Skips (with the reason) ONLY when docker itself is unavailable, and fails instead
    when ``FABRIK_REQUIRE_REAL_PG=1``. A missing image is pulled; a failed pull or
    container start is a failure, never a silent skip. The container is removed on
    exit, whatever happened.
    """

    def _docker_unavailable(reason: str) -> None:
        if os.environ.get("FABRIK_REQUIRE_REAL_PG") == "1":
            pytest.fail(f"FABRIK_REQUIRE_REAL_PG=1 but {reason}")
        pytest.skip(reason)

    if shutil.which("docker") is None:
        _docker_unavailable("docker is not installed")
    info = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if info.returncode != 0:
        _docker_unavailable(f"docker daemon unavailable: {info.stderr.strip()}")
    probe = subprocess.run(
        ["docker", "image", "inspect", _IMAGE], capture_output=True, text=True, check=False
    )
    if probe.returncode != 0:
        pulled = subprocess.run(
            ["docker", "pull", _IMAGE], capture_output=True, text=True, timeout=300, check=False
        )
        if pulled.returncode != 0:
            pytest.fail(f"docker pull {_IMAGE} failed: {pulled.stderr.strip()}")
    name = f"fabrik-t02-pg-{uuid.uuid4().hex[:10]}"
    su_pw = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    started = subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", name, "-e", "POSTGRES_PASSWORD", _IMAGE],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={**os.environ, "POSTGRES_PASSWORD": su_pw},
    )
    if started.returncode != 0:
        pytest.fail(f"docker run {_IMAGE} failed: {started.stderr.strip()}")
    try:
        deadline = time.monotonic() + _READY_TIMEOUT_S
        while True:
            # -h 127.0.0.1: the init-phase server listens on the socket only, so a
            # TCP answer means the FINAL server is up.
            ok = subprocess.run(
                ["docker", "exec", name, "pg_isready", "-U", "postgres", "-h", "127.0.0.1"],
                capture_output=True,
                text=True,
                check=False,
            )
            if ok.returncode == 0:
                break
            if time.monotonic() > deadline:
                raise RuntimeError(f"{name} not ready after {_READY_TIMEOUT_S}s")
            time.sleep(0.5)
        yield ScratchPg(name)
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False, timeout=120)


# ── The legacy fixture both rows share ─────────────────────────────────────


DB = "ti"
APP = "ti_app"
RW = "ti_wd_rw"


def _legacy_database(s: ScratchPg) -> None:
    """Owner ``ti`` (a member of ``authenticated``), its ``audit_log`` and a sequence-
    backed table, the three Pattern A roles, and the legacy PUBLIC grants a pre-15
    database carries (``GRANT ALL ON audit_log TO PUBLIC``, PUBLIC ``CREATE`` on public).
    """
    owner_pw = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    s.run_sql(
        "\\set ON_ERROR_STOP on\n"
        f"CREATE ROLE {DB} WITH LOGIN PASSWORD '{owner_pw}';\n"
        f"CREATE DATABASE {DB} OWNER {DB};\n"
        "CREATE ROLE anon NOLOGIN NOINHERIT;\n"
        "CREATE ROLE authenticated NOLOGIN NOINHERIT;\n"
        "CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;\n"
        f"GRANT authenticated TO {DB};\n"
        f"\\c {DB}\n"
        f"SET ROLE {DB};\n"
        "CREATE TABLE audit_log (id bigserial PRIMARY KEY, action text NOT NULL);\n"
        "CREATE TABLE widgets (id bigserial PRIMARY KEY, name text);\n"
        # Supabase-shaped grants to the group role, and the legacy PUBLIC grants.
        "GRANT ALL ON audit_log TO authenticated;\n"
        "GRANT ALL ON audit_log TO PUBLIC;\n"
        "RESET ROLE;\n"
        "GRANT CREATE ON SCHEMA public TO PUBLIC;\n"
    )


def _refused(fn: Callable[[], str]) -> str:
    with pytest.raises(RuntimeError) as exc:
        fn()
    return str(exc.value)


def test_app_role_is_append_only_from_a_real_login_session() -> None:
    with scratch_pg() as s:
        _legacy_database(s)
        with s.as_driver():
            wd = pg.create_watchdog_roles(DB)
            res = pg.ensure_app_role(DB)
        assert res["status"] == "created" and res["owner"] == DB and res["password"]
        pw = res["password"]
        app = lambda sql: s.login_sql(APP, pw, sql, db=DB)  # noqa: E731

        # INSERT / SELECT on audit_log succeed.
        app("INSERT INTO audit_log (action) VALUES ('login');")
        assert app("SELECT count(*) FROM audit_log;") == "1"
        # UPDATE / DELETE / TRUNCATE refused directly …
        for stmt in (
            "UPDATE audit_log SET action = 'x';",
            "DELETE FROM audit_log;",
            "TRUNCATE audit_log;",
        ):
            assert "permission denied" in _refused(lambda st=stmt: app(st))
            # … and after SET ROLE authenticated (a membership the app does hold).
            assert "permission denied" in _refused(
                lambda st=stmt: app(f"SET ROLE authenticated;\n{st}")
            )
        # The membership is real: SET ROLE authenticated itself succeeds.
        app("SET ROLE authenticated;\nSELECT 1;")
        # No CREATE in public, and no way to become the owner.
        assert "permission denied" in _refused(lambda: app("CREATE TABLE evil (id int);"))
        assert "permission denied" in _refused(lambda: app(f"SET ROLE {DB};"))
        # The ordinary table keeps full DML.
        app("INSERT INTO widgets (name) VALUES ('a'); UPDATE widgets SET name = 'b';")

        # The watchdog RW role: the same three refused.
        rw = lambda sql: s.login_sql(RW, wd["rw"]["password"], sql, db=DB)  # noqa: E731
        for stmt in (
            "UPDATE audit_log SET action = 'x';",
            "DELETE FROM audit_log;",
            "TRUNCATE audit_log;",
        ):
            assert "permission denied" in _refused(lambda st=stmt: rw(st))


def test_probe_flags_legacy_public_grants_then_passes_after_ensure() -> None:
    with scratch_pg() as s:
        _legacy_database(s)
        with s.as_driver():
            pg.create_watchdog_roles(DB)
            before = pg.probe_app_role(DB)
            assert "PUBLIC holds UPDATE on audit_log" in before, before
            assert "PUBLIC holds CREATE on schema public" in before, before

            first = pg.ensure_app_role(DB)
            assert pg.probe_app_role(DB) == []
            # Re-apply is idempotent: no new password, grants re-applied, still clean.
            again = pg.ensure_app_role(DB)
            assert again["status"] == "exists" and again["password"] is None
            assert pg.probe_app_role(DB) == []
        assert first["status"] == "created"
        # The first password still logs in after the re-apply.
        assert s.login_sql(APP, first["password"], "SELECT 1;", db=DB) == "1"


# ── Acceptance-review fixups (r1): each row seeds the bad state on a real PG16 ──


def _pw() -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))


def _in_db(sql: str) -> str:
    return f"\\c {DB}\n{sql}"


def test_o1_colliding_role_that_owns_a_database_or_the_owner_is_refused() -> None:
    with scratch_pg() as s:
        _legacy_database(s)
        # A pre-existing `ti_app` that is NOT our app role: it owns another database.
        s.run_sql(
            f"CREATE ROLE {APP} LOGIN PASSWORD '{_pw()}';\nCREATE DATABASE other OWNER {APP};\n"
        )
        with s.as_driver():
            with pytest.raises(pg.AppRoleError, match="owns database other"):
                pg.ensure_app_role(DB)
            assert any("owns database other" in f for f in pg.probe_app_role(DB))
        # Nothing was granted to it.
        got = s.run_sql(_in_db(f"SELECT has_table_privilege('{APP}', 'widgets', 'UPDATE');"))
        assert got.endswith("f"), got
        # Second shape: it is a member of the owner role.
        s.run_sql(f"DROP DATABASE other;\nGRANT {DB} TO {APP};\n")
        with s.as_driver():
            with pytest.raises(pg.AppRoleError, match="member of the owner role"):
                pg.ensure_app_role(DB, reset_password=True)
            assert any(f"membership in {DB}" in f for f in pg.probe_app_role(DB))


def test_o2_stale_role_attributes_are_reasserted_on_reapply() -> None:
    with scratch_pg() as s:
        _legacy_database(s)
        s.run_sql(
            f"CREATE ROLE {APP} WITH LOGIN SUPERUSER CREATEDB CREATEROLE BYPASSRLS REPLICATION "
            f"PASSWORD '{_pw()}';\n"
        )
        with s.as_driver():
            before = pg.probe_app_role(DB)
            for attr in ("SUPERUSER", "CREATEDB", "CREATEROLE", "BYPASSRLS", "REPLICATION"):
                assert f"{APP} has {attr}" in before, before
            res = pg.ensure_app_role(DB)
            assert res["status"] == "exists"
            assert pg.probe_app_role(DB) == []
        row = s.run_sql(
            "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls, rolreplication "
            f"FROM pg_roles WHERE rolname = '{APP}';"
        )
        assert row == "t|f|f|f|f|f", row


def test_o3_o4_create_is_revoked_on_every_owner_schema_and_from_group_roles() -> None:
    with scratch_pg() as s:
        _legacy_database(s)
        s.run_sql(
            "\\set ON_ERROR_STOP on\n"
            + _in_db(
                f"CREATE SCHEMA auth AUTHORIZATION {DB};\n"
                "GRANT CREATE ON SCHEMA auth TO PUBLIC;\n"
                "GRANT CREATE ON SCHEMA public TO authenticated;\n"
                "GRANT CREATE ON SCHEMA auth TO authenticated;\n"
            )
        )
        with s.as_driver():
            before = pg.probe_app_role(DB)
            assert "PUBLIC holds CREATE on schema auth" in before, before
            res = pg.ensure_app_role(DB)
            assert pg.probe_app_role(DB) == []
            # Drift after the app exists: a group role it can SET ROLE to regains CREATE.
            s.run_sql(_in_db("GRANT CREATE ON SCHEMA public TO authenticated;"))
            drift = pg.probe_app_role(DB)
            assert "authenticated holds CREATE on schema public" in drift, drift
            pg.ensure_app_role(DB)
            after = pg.probe_app_role(DB)
        assert after == [], after
        app = lambda sql: s.login_sql(APP, res["password"], sql, db=DB)  # noqa: E731
        assert "permission denied" in _refused(lambda: app("CREATE TABLE auth.x (id int);"))
        assert "permission denied" in _refused(
            lambda: app("SET ROLE authenticated;\nCREATE TABLE public.y (id int);")
        )
        assert "permission denied" in _refused(
            lambda: app("SET ROLE authenticated;\nCREATE TABLE auth.z (id int);")
        )
        # The owner keeps its own CREATE on both.
        got = s.run_sql(
            _in_db(
                f"SELECT has_schema_privilege('{DB}', 'public', 'CREATE') "
                f"AND has_schema_privilege('{DB}', 'auth', 'CREATE');"
            )
        )
        assert got.endswith("t"), got


def test_o5_o6_memberships_converge_to_the_owners_three_set_only() -> None:
    with scratch_pg() as s:
        _legacy_database(s)
        with s.as_driver():
            pg.create_watchdog_roles(DB)
            pg.ensure_app_role(DB)
        # Drift: an outside role, a Pattern A role the owner is NOT in, and the owner's
        # own group role re-granted by another grantor WITH INHERIT TRUE.
        s.run_sql(
            "\\set ON_ERROR_STOP on\n"
            f"GRANT {DB}_wd_ro TO {APP};\n"
            f"GRANT anon TO {APP} WITH INHERIT TRUE;\n"
            "CREATE ROLE granter NOLOGIN;\n"
            "GRANT authenticated TO granter WITH ADMIN OPTION;\n"
            f"GRANT authenticated TO {APP} WITH INHERIT TRUE GRANTED BY granter;\n"
        )
        with s.as_driver():
            before = pg.probe_app_role(DB)
            assert any(f"membership in {DB}_wd_ro" in f for f in before), before
            assert any("membership in anon" in f for f in before), before
            assert any("membership in authenticated" in f and "INHERIT" in f for f in before), (
                before
            )
            pg.ensure_app_role(DB)
            assert pg.probe_app_role(DB) == []
        rows = s.run_sql(
            "SELECT g.rolname || ',' || pg_get_userbyid(m.grantor) || ',' || m.inherit_option "
            "|| ',' || m.set_option || ',' || m.admin_option FROM pg_auth_members m "
            f"JOIN pg_roles g ON g.oid = m.roleid WHERE m.member = '{APP}'::regrole ORDER BY 1;"
        )
        assert rows == "authenticated,postgres,false,true,false", rows


def test_o7_a_superuser_owner_is_refused() -> None:
    with scratch_pg() as s:
        s.run_sql(
            f"CREATE ROLE boss WITH LOGIN SUPERUSER PASSWORD '{_pw()}';\n"
            "CREATE DATABASE bossdb OWNER boss;\n"
        )
        with s.as_driver():
            with pytest.raises(pg.AppRoleError, match="superuser"):
                pg.ensure_app_role("bossdb")
            with pytest.raises(pg.AppRoleError, match="superuser"):
                pg.probe_app_role("bossdb")
        assert s.run_sql("SELECT count(*) FROM pg_roles WHERE rolname = 'bossdb_app';") == "0"


def test_o8_failed_grants_after_create_drop_the_fresh_role() -> None:
    with scratch_pg() as s:
        _legacy_database(s)
        state = {"failed": False}

        def half_then_fail(
            sql: str, container: str = pg.POSTGRES_CONTAINER, dry_run: bool = False
        ) -> str:
            if "GRANT CONNECT ON DATABASE" in sql and not state["failed"]:
                state["failed"] = True
                # Apply the batch up to (and including) the schema-grants block for real,
                # so the role holds CONNECT, table grants and default privileges; then fail.
                cut = sql.index("END $$;") + len("END $$;")
                s.run_sql(sql[:cut] + "\n")
                raise RuntimeError("SSH failed (rc=3): injected mid-batch failure")
            return s.run_sql(sql)

        with patch.object(pg, "_run_sql", side_effect=half_then_fail):
            with pytest.raises(RuntimeError, match="injected"):
                pg.ensure_app_role(DB)
            assert s.run_sql(f"SELECT count(*) FROM pg_roles WHERE rolname = '{APP}';") == "0"
            res = pg.ensure_app_role(DB)
        assert res["status"] == "created" and res["password"]
        assert s.login_sql(APP, res["password"], "SELECT 1;", db=DB) == "1"


def test_o10_grant_option_chain_and_public_trigger_references() -> None:
    with scratch_pg() as s:
        _legacy_database(s)
        s.run_sql(
            "\\set ON_ERROR_STOP on\n"
            + _in_db(
                f"SET ROLE {DB};\n"
                "GRANT UPDATE ON audit_log TO service_role WITH GRANT OPTION;\n"
                "RESET ROLE;\n"
                "SET ROLE service_role;\n"
                "GRANT UPDATE ON audit_log TO authenticated;\n"
                "RESET ROLE;\n"
            )
        )
        with s.as_driver():
            before = pg.probe_app_role(DB)
            assert "PUBLIC holds TRIGGER on audit_log" in before, before
            assert "PUBLIC holds REFERENCES on audit_log" in before, before
            res = pg.ensure_app_role(DB)
            assert pg.probe_app_role(DB) == []
        checks = s.run_sql(
            _in_db(
                "SELECT has_table_privilege('authenticated', 'audit_log', 'UPDATE') "
                "OR has_table_privilege('service_role', 'audit_log', 'UPDATE') "
                "OR has_table_privilege('public', 'audit_log', 'TRIGGER') "
                "OR has_table_privilege('public', 'audit_log', 'REFERENCES');"
            )
        )
        assert checks.endswith("f"), checks
        app = lambda sql: s.login_sql(APP, res["password"], sql, db=DB)  # noqa: E731
        assert "permission denied" in _refused(
            lambda: app("SET ROLE authenticated;\nUPDATE audit_log SET action = 'x';")
        )


def test_s3_a_pipe_in_a_table_name_cannot_desync_the_probe() -> None:
    with scratch_pg() as s:
        _legacy_database(s)
        s.run_sql(
            "\\set ON_ERROR_STOP on\n"
            "CREATE ROLE stranger NOLOGIN;\n"
            + _in_db(
                'CREATE TABLE public."weird|table" (id int);\n'
                'ALTER TABLE public."weird|table" OWNER TO stranger;\n'
            )
        )
        with s.as_driver():
            pg.ensure_app_role(DB)
            failures = pg.probe_app_role(DB)
        assert failures == [
            f'table public."weird|table" is owned by stranger, not the database owner {DB}'
        ], failures


# ── O11: the harness never skips silently ─────────────────────────────────


class _Proc:
    def __init__(self, rc: int) -> None:
        self.returncode, self.stdout, self.stderr = rc, "", ""


def test_o11_missing_image_is_pulled_and_a_failed_pull_fails(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, *a, **kw):
        calls.append(cmd)
        if cmd[:3] == ["docker", "image", "inspect"] or cmd[:2] == ["docker", "pull"]:
            return _Proc(1)
        return _Proc(0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.delenv("FABRIK_REQUIRE_REAL_PG", raising=False)
    with pytest.raises(pytest.fail.Exception, match="pull"):
        with scratch_pg():
            pass
    assert ["docker", "pull", _IMAGE] in calls


def test_o11_docker_unavailable_fails_when_real_pg_is_required(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setenv("FABRIK_REQUIRE_REAL_PG", "1")
    with pytest.raises(pytest.fail.Exception, match="docker"):
        with scratch_pg():
            pass
    monkeypatch.delenv("FABRIK_REQUIRE_REAL_PG")
    with pytest.raises(pytest.skip.Exception, match="docker"):
        with scratch_pg():
            pass
