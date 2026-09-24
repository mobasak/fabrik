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

    Skips (with the reason) when docker or the image is unavailable. The container
    is removed on exit, whatever happened.
    """
    if shutil.which("docker") is None:
        pytest.skip("docker is not installed")
    probe = subprocess.run(
        ["docker", "image", "inspect", _IMAGE], capture_output=True, text=True, check=False
    )
    if probe.returncode != 0:
        pytest.skip(f"docker unavailable or image {_IMAGE} not present: {probe.stderr.strip()}")
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
        pytest.skip(f"docker run {_IMAGE} failed: {started.stderr.strip()}")
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
