"""T05 — every scaffold type emits the app-audit-log its type owes (spec § 3, D-390).

A Python backend WITH a database (saas-skeleton, static-site, office-extension,
python-api, python-api-gpu, file-worker, and the ``server/`` of chrome-extension and
mobile-app) gets the vendored module, the table + no-window revokes folded into its
schema file, the jobs module and both DSNs in ``.env.example``; node-api and file-api
with a database get the table and revokes only; desktop-app, docusaurus and a
database-less file-worker get nothing.

The real-PostgreSQL rows (no window, the concurrent writer) import T02's
``scratch_pg()`` (spine § Interfaces T02 → T05); run them with
``FABRIK_REQUIRE_REAL_PG=1`` so a skip cannot read as green.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import re
import secrets
import string
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
import yaml

import fabrik.drivers.postgres as pg
import fabrik.scaffold as scaffold
from fabrik.scaffold import create_project
from tests.test_app_role_real_pg import ScratchPg, scratch_pg

requires_fabrik_env = pytest.mark.skipif(
    not Path("/opt/fabrik-lib/app-audit-log/audit_log.py").exists() or os.getenv("CI") == "true",
    reason="Requires /opt/fabrik-lib/app-audit-log (the vendored module's source)",
)

# type -> (backend dir, jobs module relative to the project, the schema file the audit block folds into)
_PY_BACKENDS: dict[str, tuple[str, str, str]] = {
    "saas-skeleton": ("server", "server/src/{pkg}/audit_jobs.py", "server/db/schema.sql"),
    "static-site": ("server", "server/src/{pkg}/audit_jobs.py", "server/db/schema.sql"),
    "office-extension": ("server", "server/src/{pkg}/audit_jobs.py", "server/db/schema.sql"),
    "python-api": ("", "src/{pkg}/audit_jobs.py", "db/schema.sql"),
    "python-api-gpu": ("", "src/{pkg}/audit_jobs.py", "db/schema.sql"),
    "file-worker": ("", "worker/audit_jobs.py", "db/schema.sql"),
    "chrome-extension": ("server", "server/src/{pkg}/audit_jobs.py", "db/schema.sql"),
    "mobile-app": ("server", "server/src/app/audit_jobs.py", "db/schema.sql"),
}
_SAAS_FAMILY = ("saas-skeleton", "static-site", "office-extension")
_NODE_DB = ("node-api", "file-api")
_NOTHING = ("desktop-app", "docusaurus", "file-worker-nodb")

_HEADER = 'psql -1 -v ON_ERROR_STOP=1 "$DATABASE_URL_OWNER" -f db/schema.sql'


def _name(kind: str) -> str:
    return f"al-{kind}"[:40]


def _pkg(kind: str) -> str:
    return _name(kind).replace("-", "_")


@pytest.fixture(scope="module")
def projects(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Path]]:
    """Scaffold every type once. The dev-env side effects (venv, pip, the local
    ``sudo -u postgres`` database) and the hub hooks are stubbed; everything the
    scaffolder WRITES is real."""
    base = tmp_path_factory.mktemp("audit")
    real_run = subprocess.run

    def _no_env_setup(cmd, *a, **kw):  # type: ignore[no-untyped-def]
        argv = [str(c) for c in cmd] if isinstance(cmd, list | tuple) else [str(cmd)]
        if (
            argv[:1] == ["sudo"]
            or argv[1:3] == ["-m", "venv"]
            or (argv and Path(argv[0]).name.startswith("pip"))
        ):
            return subprocess.CompletedProcess(argv, 0, "", "")
        return real_run(cmd, *a, **kw)

    out: dict[str, Path] = {}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(scaffold.subprocess, "run", _no_env_setup)
        mp.setattr(scaffold, "_post_scaffold_sync", lambda *_a, **_k: None)
        mp.setattr(scaffold, "_emit_mcp_config", lambda *_a, **_k: None)
        mp.setattr(scaffold, "_install_pre_commit", lambda *_a, **_k: True)
        kinds = [*_PY_BACKENDS, *_NODE_DB, *_NOTHING]
        for kind in kinds:
            ptype = "file-worker" if kind == "file-worker-nodb" else kind
            use_db = kind not in _NOTHING
            create_project(
                name=_name(kind),
                project_type=ptype,
                description=f"audit-log scaffold test ({kind})",
                base=base,
                generate_spec=(kind == "python-api"),
                use_database=use_db,
            )
            out[kind] = base / _name(kind)
    out["_base"] = base
    yield out


def _strip_dollar_quoted(sql: str) -> str:
    """Drop every dollar-quoted body (function / DO bodies), leaving top-level SQL."""
    return re.sub(r"\$(\w*)\$.*?\$\1\$", "", sql, flags=re.DOTALL)


def _py_files(root: Path) -> list[Path]:
    skip = {"node_modules", ".venv", ".git", "fastapi_user_auth", "docs-site"}
    return [p for p in root.rglob("*.py") if not skip.intersection(p.relative_to(root).parts)]


# ── Row 1: each Python-backed type with a database ──────────────────────────


@requires_fabrik_env
@pytest.mark.parametrize("kind", list(_PY_BACKENDS))
def test_python_backend_gets_module_table_revokes_header_env(
    projects: dict[str, Path], kind: str
) -> None:
    project = projects[kind]
    backend, jobs_rel, schema_rel = _PY_BACKENDS[kind]
    vendored = project / backend / "libs" / "audit_log"
    assert (vendored / "audit_log.py").is_file()
    assert (vendored / "schema.sql").is_file() and (vendored / "data_retention.sql").is_file()
    leftovers = [
        p.name
        for p in vendored.rglob("*")
        if p.name in {"__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
        or p.name.startswith("test_")
        or p.name == "UPSTREAM_FEEDBACK.md"
        or p.suffix == ".pyc"
    ]
    assert leftovers == [], f"dev artefacts vendored: {leftovers}"

    sql = (project / schema_rel).read_text()
    assert _HEADER in sql
    table_at = sql.index("CREATE TABLE IF NOT EXISTS audit_log")
    for needle in (
        "current_database() || '_app'",
        "current_database() || '_wd_rw'",
        "'anon'",
        "'authenticated'",
        "'service_role'",
        "pg_roles",
        "REVOKE UPDATE, DELETE, TRUNCATE",
    ):
        assert needle in sql[table_at:], f"{needle!r} missing after the audit_log table"
    top_level = _strip_dollar_quoted(sql)
    assert not re.search(
        r"^\s*(BEGIN|COMMIT|START\s+TRANSACTION|END|ROLLBACK)\s*;",
        top_level,
        flags=re.MULTILINE | re.IGNORECASE,
    ), "the file carries its own transaction control, which would break psql -1"

    assert (project / jobs_rel.format(pkg=_pkg(kind))).is_file()
    assert not [p for p in _py_files(project) if "_LogAuditLogger" in p.read_text()]

    env = (project / ".env.example").read_text()
    assert re.search(r"^DATABASE_URL=\s*$", env, flags=re.MULTILINE), env
    assert re.search(r"^DATABASE_URL_OWNER=\s*$", env, flags=re.MULTILINE), env

    reqs = project / ("server/requirements.txt" if kind in _SAAS_FAMILY else "requirements.txt")
    assert "psycopg[binary]" in reqs.read_text()


# ── Row 2: node types get the table and revokes only; the rest nothing ─────


@requires_fabrik_env
@pytest.mark.parametrize("kind", _NODE_DB)
def test_node_type_gets_table_and_revokes_only(projects: dict[str, Path], kind: str) -> None:
    project = projects[kind]
    sql = (project / "db" / "schema.sql").read_text()
    assert _HEADER in sql
    table_at = sql.index("CREATE TABLE IF NOT EXISTS audit_log")
    assert "current_database() || '_app'" in sql[table_at:]
    assert not (project / "libs" / "audit_log").exists()
    assert not [p for p in _py_files(project) if p.name == "audit_jobs.py"]


@requires_fabrik_env
@pytest.mark.parametrize("kind", _NOTHING)
def test_type_without_backend_or_database_gets_nothing(
    projects: dict[str, Path], kind: str
) -> None:
    project = projects[kind]
    assert "audit_log" not in (project / "db" / "schema.sql").read_text()
    assert not list(project.rglob("libs/audit_log"))
    assert not [p for p in _py_files(project) if p.name == "audit_jobs.py"]


# ── Row 3: the saas beat loop schedules both jobs ──────────────────────────


@requires_fabrik_env
def test_saas_beat_loop_schedules_retention_and_verify(projects: dict[str, Path]) -> None:
    pkg_dir = projects["saas-skeleton"] / "server" / "src" / _pkg("saas-skeleton")
    worker = (pkg_dir / "worker.py").read_text()
    beat = worker[worker.index("async def _beat_loop") : worker.index("async def _heartbeat_loop")]
    assert "audit_jobs.run_due" in beat
    jobs = _load(pkg_dir / "audit_jobs.py", "saas_audit_jobs")
    now = jobs.datetime(2026, 9, 24, tzinfo=jobs.UTC)
    # Never run → both due; ran just now → neither; a day / a week later → each in turn.
    assert jobs.due_jobs(None, None, now) == ["retention", "verify"]
    assert jobs.due_jobs(now, now, now) == []
    assert jobs.due_jobs(now - jobs.timedelta(days=1), now, now) == ["retention"]
    assert jobs.due_jobs(now, now - jobs.timedelta(days=7), now) == ["verify"]


# ── Row 4: the companion in the generated spec and the rendered compose ─────


@requires_fabrik_env
def test_python_api_spec_declares_audit_jobs_companion(
    projects: dict[str, Path], tmp_path: Path
) -> None:
    from fabrik.spec_loader import load_spec
    from fabrik.template_renderer import TemplateRenderer

    name = _name("python-api")
    spec_path = projects["_base"] / "specs" / "services" / f"{name}.yaml"
    raw = yaml.safe_load(spec_path.read_text())
    assert raw["shape"]["database_url_app_role"] is True  # T01 → T05 seam
    (companion,) = raw["companion_services"]
    assert companion["id"] == f"{name}-audit-jobs"
    assert companion["command"] == ["python", "-m", f"{_pkg('python-api')}.audit_jobs"]
    assert re.fullmatch(r"\d+[MG]", companion["memory"])
    assert "env_overrides" not in companion

    rendered = TemplateRenderer(output_dir=tmp_path).render(load_spec(spec_path), dry_run=True)
    services = yaml.safe_load(rendered["compose.yaml"])["services"]
    app, jobs = services[name], services[f"{name}-audit-jobs"]
    assert jobs["command"] == companion["command"]
    assert jobs["deploy"]["resources"]["limits"]["memory"] == companion["memory"]
    assert set(jobs["environment"]) <= set(app["environment"]), "companion env must not diverge"
    # The jobs read DATABASE_URL_OWNER, which only the project .env carries (r1 item 1a).
    assert ".env" in jobs["env_file"]
    assert jobs["healthcheck"] == {"disable": True}  # a scheduler serves no /health


# ── Row 5: absent owner DSN → log and idle, never exit ──────────────────────


@requires_fabrik_env
def test_audit_jobs_idles_when_owner_dsn_is_unset(projects: dict[str, Path]) -> None:
    project = projects["python-api"]
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL_OWNER"}
    env.update(PYTHONPATH=str(project / "src"), AUDIT_JOBS_TICK_SEC="1", PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(
        [sys.executable, "-m", f"{_pkg('python-api')}.audit_jobs"],
        cwd=project,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        time.sleep(4)
        alive = proc.poll() is None
    finally:
        proc.terminate()
        out, _ = proc.communicate(timeout=30)
    assert alive, f"audit_jobs exited on a missing DATABASE_URL_OWNER:\n{out}"
    assert "audit_jobs: not_configured" in out, out


# ── Real PostgreSQL helpers ────────────────────────────────────────────────


def _pw() -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _new_project_db(s: ScratchPg, db: str) -> str:
    """The registrar's shape for a NEW project: an owner role owning ``db``, the app and
    watchdog roles minted BEFORE the schema exists (T02's driver, run verbatim)."""
    owner_pw = _pw()
    s.run_sql(
        "\\set ON_ERROR_STOP on\n"
        f"CREATE ROLE {db} WITH LOGIN PASSWORD '{owner_pw}';\n"
        f"CREATE DATABASE {db} OWNER {db};\n"
    )
    return owner_pw


def _roles(s: ScratchPg, db: str) -> tuple[str, str]:
    with s.as_driver():
        wd = pg.create_watchdog_roles(db)
        app = pg.ensure_app_role(db)
    return app["password"], wd["rw"]["password"]


def _apply_as_header_says(
    s: ScratchPg, schema: Path, db: str, owner_pw: str
) -> subprocess.CompletedProcess:
    """``psql -1 -v ON_ERROR_STOP=1 "$DATABASE_URL_OWNER" -f db/schema.sql`` as the owner."""
    subprocess.run(
        ["docker", "cp", str(schema), f"{s.container}:/schema.sql"], check=True, timeout=60
    )
    return subprocess.run(
        [
            "docker", "exec", "-e", "PGPASSWORD", s.container,
            "psql", "-1", "-v", "ON_ERROR_STOP=1",
            f"postgresql://{db}@127.0.0.1:5432/{db}",
            "-f", "/schema.sql",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "PGPASSWORD": owner_pw},
    )  # fmt: skip


def _refused(fn) -> str:  # type: ignore[no-untyped-def]
    with pytest.raises(RuntimeError) as exc:
        fn()
    return str(exc.value)


# ── Row 6: no window between CREATE TABLE and the revokes ───────────────────


@requires_fabrik_env
def test_no_window_app_role_refused_update_right_after_apply(
    projects: dict[str, Path], tmp_path: Path
) -> None:
    schemas = {
        "saas": projects["saas-skeleton"] / "server" / "db" / "schema.sql",
        "pyapi": projects["python-api"] / "db" / "schema.sql",
    }
    with scratch_pg() as s:
        for tag, schema in schemas.items():
            db = f"nw_{tag}"
            owner_pw = _new_project_db(s, db)
            app_pw, rw_pw = _roles(s, db)
            res = _apply_as_header_says(s, schema, db, owner_pw)
            assert res.returncode == 0, res.stderr
            app = lambda sql, db=db, pw=app_pw: s.login_sql(f"{db}_app", pw, sql, db=db)  # noqa: E731
            rw = lambda sql, db=db, pw=rw_pw: s.login_sql(f"{db}_wd_rw", pw, sql, db=db)  # noqa: E731
            app(
                "INSERT INTO audit_log (id, actor, action, current_hash) "
                "VALUES (gen_random_uuid(), 'system', 'test.inserted', repeat('a', 64));"
            )
            for stmt in (
                "UPDATE audit_log SET action = 'x';",
                "DELETE FROM audit_log;",
                "TRUNCATE audit_log;",
            ):
                for as_role in (app, rw):
                    refusal = _refused(lambda st=stmt, f=as_role: f(st))
                    assert "permission denied" in refusal, (tag, stmt)

        # A failing statement AFTER the audit block aborts the whole file: no table at all.
        broken = tmp_path / "schema.sql"
        broken.write_text(schemas["saas"].read_text() + "\nSELECT 1/0;\n")
        owner_pw = _new_project_db(s, "nw_broken")
        res = _apply_as_header_says(s, broken, "nw_broken", owner_pw)
        assert res.returncode != 0
        out = s.run_sql("\\c nw_broken\nSELECT to_regclass('audit_log') IS NULL;")
        assert out.splitlines()[-1] == "t", out


# ── Row 7: the async writer under concurrency; the jobs against real data ───


def _container_ip(s: ScratchPg) -> str:
    return subprocess.run(
        [
            "docker", "inspect", "-f",
            "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", s.container,
        ],
        capture_output=True, text=True, check=True, timeout=60,
    ).stdout.strip()  # fmt: skip


@requires_fabrik_env
def test_writer_concurrent_writes_keep_the_chain_strict(
    projects: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    import psycopg
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    pkg_dir = projects["saas-skeleton"] / "server" / "src" / _pkg("saas-skeleton")
    writer = _load(pkg_dir / "audit.py", "saas_audit_writer")
    jobs = _load(pkg_dir / "audit_jobs.py", "saas_audit_jobs_pg")
    al = writer.al  # the vendored module the writer hashes with
    db = "wr_saas"
    with scratch_pg() as s:
        owner_pw = _new_project_db(s, db)
        app_pw, _ = _roles(s, db)
        schema = projects["saas-skeleton"] / "server" / "db" / "schema.sql"
        res = _apply_as_header_says(s, schema, db, owner_pw)
        assert res.returncode == 0, res.stderr
        ip = _container_ip(s)

        async def _write_concurrently(n: int) -> None:
            engine = create_async_engine(
                f"postgresql+psycopg://{db}_app:{app_pw}@{ip}:5432/{db}", pool_size=n
            )
            try:
                sm = async_sessionmaker(engine, expire_on_commit=False)
                logger = writer.ChainAuditLogger(sm)
                await asyncio.gather(
                    *(
                        logger.log(
                            actor=f"user:{i}", action="auth.login_success", target_type="user",
                            target_id=i, details={"ip": "10.0.0.1", "n": i},
                        )
                        for i in range(n)
                    )
                )  # fmt: skip
            finally:
                await engine.dispose()

        asyncio.run(_write_concurrently(8))

        # A clock that steps BACK (an NTP correction) must not fork the chain either:
        # the writer clamps ts strictly past the tip.
        class _StepBack(writer.datetime):  # type: ignore[name-defined,misc]
            @classmethod
            def now(cls, tz=None):  # type: ignore[no-untyped-def,override]
                return super().now(tz) - writer.timedelta(hours=1)

        monkeypatch.setattr(writer, "datetime", _StepBack)
        asyncio.run(_write_concurrently(2))
        monkeypatch.undo()

        owner_dsn = f"postgresql://{db}:{owner_pw}@{ip}:5432/{db}"
        with psycopg.connect(owner_dsn) as conn:
            assert conn.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 10
            assert al.verify_chain(conn, strict=True) == []

        # The jobs, as the owner: verification is clean and advances the cursor;
        # retention runs the vendored data_retention.sql.
        monkeypatch.setenv("DATABASE_URL_OWNER", owner_dsn)
        assert jobs.run_verify() == []
        assert jobs.run_retention() is True
        with psycopg.connect(owner_dsn) as conn:
            state = conn.execute(
                "SELECT verified_through, last_verify_at, last_retention_at FROM audit_jobs_state"
            ).fetchone()
            tip = conn.execute("SELECT max(ts) FROM audit_log").fetchone()[0]
        assert state[0] == tip and state[1] is not None and state[2] is not None


# ── Fixups r1 ───────────────────────────────────────────────────────────────


def _companion_types() -> list[str]:
    from fabrik.spec_generator import AUDIT_JOBS_MODULES

    return sorted(AUDIT_JOBS_MODULES)


@requires_fabrik_env
@pytest.mark.parametrize("kind", _companion_types())
def test_committed_compose_carries_the_audit_jobs_companion(
    projects: dict[str, Path], kind: str
) -> None:
    """r1 item 1b: a git-sourced deploy runs the COMMITTED compose, so the companion the
    spec declares must be in it — with the project .env, the jobs command, a memory limit."""
    from fabrik.orchestrator.deployer_ssh import _validate_compose
    from fabrik.spec_generator import audit_jobs_companion

    name = _name(kind)
    raw = (projects[kind] / "compose.yaml").read_text()
    services = yaml.safe_load(raw)["services"]
    companion = audit_jobs_companion(name, kind)
    assert companion is not None
    svc = services[companion.id]
    assert svc["command"] == companion.command
    assert svc["env_file"] == [".env"]
    assert svc["deploy"]["resources"]["limits"]["memory"] == companion.memory
    assert svc["networks"] == ["fabrik"] and svc["restart"] == "unless-stopped"
    assert svc["container_name"] == companion.id
    assert "ports" not in svc and "labels" not in svc
    assert svc["healthcheck"] == {"disable": True}  # the image's HTTP/process probe is the app's
    assert _validate_compose(raw) == []


@requires_fabrik_env
@pytest.mark.parametrize("ptype", ["chrome-extension", "file-worker"])
def test_rendered_template_carries_the_audit_jobs_companion(ptype: str, tmp_path: Path) -> None:
    """r1 item 1b: every companion type that HAS a compose .j2 renders the companion."""
    from fabrik.spec_generator import generate_spec
    from fabrik.template_renderer import TemplateRenderer

    name = f"rt-{ptype}"
    spec = generate_spec(name, ptype, f"{name}.vps1.ocoron.com", use_database=True)
    rendered = TemplateRenderer(output_dir=tmp_path).render(spec, dry_run=True)
    svc = yaml.safe_load(rendered["compose.yaml"])["services"][f"{name}-audit-jobs"]
    assert svc["command"] == spec.companion_services[0].command
    assert ".env" in svc["env_file"]


@requires_fabrik_env
def test_companion_follows_the_resolved_shape_not_the_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """r1 item 5: the companion (and the module it runs) follow the RESOLVED
    shape.needs_database, not the raw --db flag."""
    import fabrik.spec_generator as sg

    real = sg._build_shape_for_type
    assert sg.generate_spec("sh-fw", "file-worker", None).companion_services == []

    def db_default(ptype: str):  # type: ignore[no-untyped-def]
        return sg._validated_shape_overlay(real(ptype), needs_database=True)

    monkeypatch.setattr(sg, "_build_shape_for_type", db_default)
    spec = sg.generate_spec("sh-fw", "file-worker", None, use_database=False)
    assert [c.id for c in spec.companion_services] == ["sh-fw-audit-jobs"]

    monkeypatch.setattr(scaffold, "_post_scaffold_sync", lambda *_a, **_k: None)
    monkeypatch.setattr(scaffold, "_emit_mcp_config", lambda *_a, **_k: None)
    monkeypatch.setattr(scaffold, "_install_pre_commit", lambda *_a, **_k: True)
    create_project(
        name="sh-fw",
        project_type="file-worker",
        description="shape-resolved database",
        base=tmp_path,
        generate_spec=False,
    )
    project = tmp_path / "sh-fw"
    assert (project / "worker" / "audit_jobs.py").is_file()
    assert "sh-fw-audit-jobs" in yaml.safe_load((project / "compose.yaml").read_text())["services"]


@requires_fabrik_env
def test_reapply_keeps_the_cursor_row_unwritable(projects: dict[str, Path]) -> None:
    """r1 item 2: a later apply (watchdog step, then the app-role step, T04's order) must
    not hand the app or the watchdog rw role write access to audit_jobs_state again."""
    schema = projects["saas-skeleton"] / "server" / "db" / "schema.sql"
    with scratch_pg() as s:
        db = "ra_saas"
        owner_pw = _new_project_db(s, db)
        app_pw, rw_pw = _roles(s, db)
        res = _apply_as_header_says(s, schema, db, owner_pw)
        assert res.returncode == 0, res.stderr
        with s.as_driver():
            pg.create_watchdog_roles(db)
            assert pg.ensure_app_role(db)["status"] == "exists"
        for role, pw in ((f"{db}_app", app_pw), (f"{db}_wd_rw", rw_pw)):
            for stmt in (
                "UPDATE audit_jobs_state SET verified_through = now();",
                "DELETE FROM audit_jobs_state;",
                "TRUNCATE audit_jobs_state;",
            ):
                refusal = _refused(lambda st=stmt, r=role, p=pw: s.login_sql(r, p, st, db=db))
                assert "permission denied" in refusal, (role, stmt)


@requires_fabrik_env
def test_run_due_against_the_emitted_schema_and_a_cursor_grant_is_an_incident(
    projects: dict[str, Path], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """r1 items 6 and 4: the emitted jobs' run_due runs both jobs clean against a real
    database carrying the emitted schema and advances the cursor; a write privilege on
    the cursor table is then reported by the weekly verify."""
    import logging

    import psycopg

    pkg_dir = projects["saas-skeleton"] / "server" / "src" / _pkg("saas-skeleton")
    jobs = _load(pkg_dir / "audit_jobs.py", "saas_audit_jobs_due")
    db = "rd_saas"
    with scratch_pg() as s:
        owner_pw = _new_project_db(s, db)
        _roles(s, db)
        schema = projects["saas-skeleton"] / "server" / "db" / "schema.sql"
        res = _apply_as_header_says(s, schema, db, owner_pw)
        assert res.returncode == 0, res.stderr
        owner_dsn = f"postgresql://{db}:{owner_pw}@{_container_ip(s)}:5432/{db}"
        with psycopg.connect(owner_dsn, autocommit=True) as conn:
            for i in range(5):
                with conn.transaction():
                    conn.execute(
                        "SELECT pg_advisory_xact_lock(%s)", (jobs.al.AUDIT_CHAIN_LOCK_KEY,)
                    )
                    jobs.al.record_event(
                        conn, actor="system", action="admin.data_exported", target_id=i
                    )
        monkeypatch.setenv("DATABASE_URL_OWNER", owner_dsn)
        caplog.set_level(logging.INFO, logger="audit_jobs")
        assert jobs.run_due() == ["retention", "verify"]
        assert "audit_jobs: verify_done incidents=0" in caplog.text
        with psycopg.connect(owner_dsn) as conn:
            cursor, verified_at, retained_at = conn.execute(
                "SELECT verified_through, last_verify_at, last_retention_at FROM audit_jobs_state"
            ).fetchone()
            tip = conn.execute("SELECT max(ts) FROM audit_log").fetchone()[0]
        assert cursor == tip and verified_at is not None and retained_at is not None
        assert jobs.run_due() == []  # neither is due again right after

        s.run_sql(f"\\c {db}\nGRANT UPDATE ON audit_jobs_state TO {db}_app;")
        incidents = jobs.run_verify()
        assert f"{db}_app holds UPDATE on audit_jobs_state" in incidents, incidents
