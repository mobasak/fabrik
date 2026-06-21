"""Structural contract for the saas-skeleton multi-tenant FastAPI backend.

Asserts ``fabrik scaffold --type saas-skeleton`` emits a conforming backend
under ``server/``: multi-tenant RLS schema + PostgreSQL jobs queue, tenant
context propagation, Supabase-JWT auth (Pattern B) + security headers, an
RFC 9457 / ``/api/v1`` API, a three-service compose (web + api + worker), and
the shape flags that drive the ``fabrik apply`` deploy registrars.

Grounded in ``docs/development/plans/2026-06-21-saas-skeleton-backend.md``;
each test maps to a plan phase.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from fabrik.scaffold import TYPE_REQUIRED_FILES, create_project

FABRIK_ROOT = Path("/opt/fabrik")
requires_fabrik_env = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik",
)

NAME = "saas-backend-test"
PKG = "saas_backend_test"


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Scaffold one saas-skeleton project for the whole module (hermetic)."""
    base = tmp_path_factory.mktemp("saas")
    create_project(
        name=NAME,
        project_type="saas-skeleton",
        description="Structural test for the saas-skeleton backend",
        base=base,
        generate_spec=False,
    )
    return base / NAME


def _pkg(project: Path) -> Path:
    return project / "server" / "src" / PKG


# Phase 1 — saas emits the backend under server/ ----------------------------
@requires_fabrik_env
def test_emits_server(project: Path) -> None:
    server = project / "server"
    assert (server / "requirements.txt").exists()
    assert (server / "Dockerfile").exists()
    pkg = _pkg(project)
    for fname in (
        "__init__.py",
        "main.py",
        "auth.py",
        "tenant.py",
        "worker.py",
        "internal_auth.py",
        "metrics.py",
    ):
        assert (pkg / fname).exists(), f"missing server package file {fname}"
    # asyncpg + pyjwt are the saas-only deps layered on the base backend.
    reqs = (server / "requirements.txt").read_text()
    assert "asyncpg" in reqs and "pyjwt" in reqs


# Phase 2 — multi-tenant RLS schema + jobs queue ----------------------------
@requires_fabrik_env
def test_rls_schema(project: Path) -> None:
    sql = (project / "server" / "db" / "schema.sql").read_text()
    assert "current_tenant_id" in sql
    assert "FORCE  ROW LEVEL SECURITY" in sql or "FORCE ROW LEVEL SECURITY" in sql
    assert "tenant_isolation" in sql
    assert "NULLIF(current_setting('app.tenant_id'" in sql  # fail-closed resolver


@requires_fabrik_env
def test_jobs_queue_schema(project: Path) -> None:
    sql = (project / "server" / "db" / "schema.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS jobs" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql  # the documented dequeue contract
    assert "idx_jobs_pending" in sql  # mandatory partial index (75 §Schema)
    assert "pg_notify" in sql  # LISTEN/NOTIFY instant wake-up


# Phase 3 — tenant context propagation --------------------------------------
@requires_fabrik_env
def test_tenant_middleware(project: Path) -> None:
    tenant = (_pkg(project) / "tenant.py").read_text()
    assert "ContextVar" in tenant
    assert "TenantMiddleware" in tenant
    assert "set_config('app.tenant_id'" in tenant  # per-txn tenant binding for RLS
    assert "SET LOCAL ROLE" not in tenant  # app connects as the non-superuser owner role
    assert "403" in tenant  # membership validation (fail-closed header path)


# Phase 4 — auth Pattern B + security headers + CORS ------------------------
@requires_fabrik_env
def test_auth_and_headers(project: Path) -> None:
    auth = (_pkg(project) / "auth.py").read_text()
    assert "PyJWKClient" in auth  # validate Supabase JWT via JWKS, no own tokens
    assert "decode_supabase_jwt" in auth
    assert "X-Frame-Options" in auth
    assert "Strict-Transport-Security" in auth
    assert "cors_origins" in auth


# Phase 5 — API contracts (RFC 9457, versioning, casing) --------------------
@requires_fabrik_env
def test_api_contracts(project: Path) -> None:
    main = (_pkg(project) / "main.py").read_text()
    assert "application/problem+json" in main  # RFC 9457
    assert "/api/v1" in main
    assert "to_camel" in main
    assert "/api/health" in main
    assert "X-Idempotency-Key" in main


# Phase 6 — three-service compose + routing ---------------------------------
@requires_fabrik_env
def test_compose_services(project: Path) -> None:
    data = yaml.safe_load((project / "compose.yaml").read_text())
    services = data["services"]
    assert NAME in services  # web service == project name (Coolify routing)
    assert "api" in services
    assert "worker" in services
    for svc in (NAME, "api", "worker"):
        limits = services[svc]["deploy"]["resources"]["limits"]
        assert "memory" in limits, f"{svc} missing memory limit"
    # api routes /api at higher priority than the frontend.
    api_labels = " ".join(services["api"].get("labels", []))
    assert "PathPrefix(`/api`)" in api_labels
    assert "priority=100" in api_labels
    # worker is internal: no traefik labels, no published ports.
    worker = services["worker"]
    assert "ports" not in worker
    assert "traefik" not in " ".join(worker.get("labels", []))
    # worker healthcheck is a python heartbeat probe — NOT pgrep (no procps in slim).
    hc = " ".join(worker["healthcheck"]["test"])
    assert "pgrep" not in hc and "WORKER_HEARTBEAT" in hc
    # DATABASE_URL is delivered only via env_file (registrar-injected), never baked
    # as a ${...} default — a fabricated blank-password URL would fail first boot.
    raw = (project / "compose.yaml").read_text()
    assert "POSTGRES_PASSWORD" not in raw
    for svc in ("api", "worker"):
        assert services[svc].get("env_file") == [".env"]
        assert not any("DATABASE_URL" in e for e in services[svc].get("environment", []))


# Phase 8 — shape flags drive the registrars + worker module ----------------
@requires_fabrik_env
def test_shape_drives_registrars(project: Path) -> None:
    shape = yaml.safe_load(
        (FABRIK_ROOT / "templates/saas-skeleton/defaults.yaml").read_text()
    )["shape"]
    assert shape["exposes_metrics"] is True  # gates prometheus
    assert shape["needs_cache"] is True  # gates redis
    assert shape["has_bearer_api"] is True
    assert shape["is_admin_dashboard"] is False  # no Authelia for end-user saas
    assert shape["needs_database"] is True


@requires_fabrik_env
def test_worker_module_present(project: Path) -> None:
    worker = (_pkg(project) / "worker.py").read_text()
    assert "FOR UPDATE SKIP LOCKED" in worker  # PG-queue dequeue
    assert "_scale_loop" in worker  # adaptive pool on queue depth
    assert "pg_try_advisory_lock" in worker  # single-leader beat scheduler
    assert "WORKER_MIN" in worker and "WORKER_MAX" in worker  # env-tunable bounds
    assert "add_listener" in worker  # LISTEN/NOTIFY wake-up, not a sleep(1) poll
    assert "init_glitchtip" in worker  # GlitchTip init (75 §Observability)
    assert "raise SystemExit" not in worker  # resilient boot — never crash on a missing DB
    assert "_await_pool" in worker  # waits/retries for the registrar-injected DB
    assert "_heartbeat_loop" in worker  # liveness heartbeat (procps-free healthcheck)


# Required-files contract ---------------------------------------------------
@requires_fabrik_env
def test_required_files_include_server() -> None:
    required = TYPE_REQUIRED_FILES["saas-skeleton"]
    assert "server/requirements.txt" in required
    assert "server/Dockerfile" in required
    assert "server/db/schema.sql" in required
