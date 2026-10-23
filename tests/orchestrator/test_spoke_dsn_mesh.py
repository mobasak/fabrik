"""Spoke DSN mesh-IP rewrite — a spoke-targeted app must connect to vps1's
shared data plane by its WireGuard mesh IP, not by a ``*-main`` Docker-DNS name.

Root cause (fixed here): the infra registrars injected ``postgres-main`` /
``redis-main`` / ``glitchtip-web`` Docker-DNS hosts into EVERY app's connection
strings unconditionally. A vps1 container resolves those over the local
``fabrik`` bridge, but a spoke (vps2/vps3) container cannot — WireGuard routes
IP packets and carries no DNS, so the name SERVFAILs. The ports are published
mesh-only on vps1's ``10.99.0.1``; the fix swaps the host to that mesh IP when
``ctx.target_vps != "vps1"``. Source of truth: ``docs/infrastructure/vps-urls.md``
§ Mesh URLs.

Each wiring test below FAILS against the pre-fix code (the injected host is the
Docker-DNS name, not the mesh IP) — that is what proves the defect was real.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.infrastructure import (
    _HUB_MESH_IP,
    DsnInjectionError,
    InfrastructureProvisioner,
    _rewrite_shared_infra_host,
)


def _spec(**shape):
    base = {
        "name": "spoke-app",
        "domain": "spoke-app.vps2.ocoron.com",
        "shape": {"kind": "service", "needs_database": True},
        "infra": {},
    }
    base["shape"].update(shape)
    return base


def _ctx(target_vps="vps2"):
    c = DeploymentContext(spec_path=Path("/tmp/unused.yaml"))
    c.spec = _spec()
    c.dry_run = False
    c.target_vps = target_vps
    c.app_name = "spoke-app"
    return c


def _ok(status="created", **extra):
    return {"status": status, **extra}


def _injected(mock_deployer):
    """Flatten every {var: value} dict passed to inject_env into one dict."""
    merged = {}
    for call in mock_deployer.inject_env.call_args_list:
        merged.update(call.args[1])
    return merged


# --------------------------------------------------------------------------- #
# _rewrite_shared_infra_host — the core logic                                  #
# --------------------------------------------------------------------------- #


class TestRewriteHelper:
    def test_spoke_rewrites_postgres_dsn_userinfo_form(self):
        out = _rewrite_shared_infra_host("postgresql://u:p@postgres-main:5432/db", "vps2")
        assert out == f"postgresql://u:p@{_HUB_MESH_IP}:5432/db"

    def test_spoke_rewrites_redis_no_userinfo_form(self):
        out = _rewrite_shared_infra_host("redis://redis-main:6379/3", "vps3")
        assert out == f"redis://{_HUB_MESH_IP}:6379/3"

    def test_spoke_rewrites_glitchtip_dsn(self):
        out = _rewrite_shared_infra_host("http://key@glitchtip-web:8000/7", "vps2")
        assert out == f"http://key@{_HUB_MESH_IP}:8000/7"

    def test_hub_is_a_noop(self):
        url = "postgresql://u:p@postgres-main:5432/db"
        assert _rewrite_shared_infra_host(url, "vps1") == url

    def test_default_none_target_is_hub_noop(self):
        url = "redis://redis-main:6379/0"
        assert _rewrite_shared_infra_host(url, None) == url

    def test_empty_url_is_safe(self):
        assert _rewrite_shared_infra_host(None, "vps2") is None
        assert _rewrite_shared_infra_host("", "vps2") == ""

    def test_unknown_host_untouched_on_spoke(self):
        # A non-shared host (e.g. an external managed DB) must be left alone.
        url = "postgresql://u:p@db.example.com:5432/db"
        assert _rewrite_shared_infra_host(url, "vps2") == url

    def test_port_and_db_path_preserved(self):
        # The db name in the path must never be rewritten even if it echoes a host.
        out = _rewrite_shared_infra_host(
            "postgresql://u:p@postgres-main:5432/fabrik_analytics", "vps2"
        )
        assert out == f"postgresql://u:p@{_HUB_MESH_IP}:5432/fabrik_analytics"


# --------------------------------------------------------------------------- #
# Wiring — each registrar injects the mesh IP on a spoke (RED before the fix)  #
# --------------------------------------------------------------------------- #


class TestPostgresSpokeWiring:
    def test_database_url_uses_mesh_ip_on_spoke(self):
        mock_deployer = MagicMock()
        prov = InfrastructureProvisioner(deployer=mock_deployer)
        ctx = _ctx("vps2")
        with (
            patch(
                "fabrik.drivers.postgres.create_database",
                return_value=_ok(password="pw"),
            ),
            patch("fabrik.drivers.postgres.database_exists", return_value=False),
        ):
            prov._provision_postgres("spoke-app", ctx.spec, ctx, dry_run=False)
        dsn = _injected(mock_deployer)["DATABASE_URL"]
        assert f"@{_HUB_MESH_IP}:5432/" in dsn
        assert "postgres-main" not in dsn

    def test_database_url_keeps_docker_dns_on_hub(self):
        # Regression guard: a vps1 deploy MUST still use the Docker-DNS name.
        mock_deployer = MagicMock()
        prov = InfrastructureProvisioner(deployer=mock_deployer)
        ctx = _ctx("vps1")
        with (
            patch(
                "fabrik.drivers.postgres.create_database",
                return_value=_ok(password="pw"),
            ),
            patch("fabrik.drivers.postgres.database_exists", return_value=False),
        ):
            prov._provision_postgres("spoke-app", ctx.spec, ctx, dry_run=False)
        dsn = _injected(mock_deployer)["DATABASE_URL"]
        assert "@postgres-main:5432/" in dsn
        assert _HUB_MESH_IP not in dsn

    def test_watchdog_and_subagent_dsns_use_mesh_ip_on_spoke(self):
        mock_deployer = MagicMock()
        prov = InfrastructureProvisioner(deployer=mock_deployer)
        ctx = _ctx("vps2")
        with (
            patch(
                "fabrik.drivers.postgres.create_database",
                return_value=_ok(password="pw"),
            ),
            patch("fabrik.drivers.postgres.database_exists", return_value=False),
            patch(
                "fabrik.drivers.postgres.create_watchdog_roles",
                return_value={
                    "ro": {"user": "spoke_app_ro", "password": "ro"},
                    "rw": {"user": "spoke_app_rw", "password": "rw"},
                },
            ),
            patch(
                "fabrik.drivers.postgres.create_subagent_ins_role",
                return_value={"ins": {"user": "spoke_app_ins", "password": "ins"}},
            ),
        ):
            prov._provision_postgres(
                "spoke-app", ctx.spec, ctx, dry_run=False, provision_watchdog_roles=True
            )
        env = _injected(mock_deployer)
        for var in ("WATCHDOG_DB_URL_RO", "WATCHDOG_DB_URL_RW", "SUBAGENT_RUNS_DSN"):
            assert f"@{_HUB_MESH_IP}:5432/" in env[var], var
            assert "postgres-main" not in env[var], var


class TestRedisSpokeWiring:
    def test_redis_url_uses_mesh_ip_on_spoke(self):
        mock_deployer = MagicMock()
        prov = InfrastructureProvisioner(deployer=mock_deployer)
        ctx = _ctx("vps2")
        with patch(
            "fabrik.drivers.redis.acquire_db_index",
            return_value=_ok(redis_url="redis://redis-main:6379/4", db_index=4),
        ):
            prov._provision_redis("spoke-app", ctx, dry_run=False)
        url = _injected(mock_deployer)["REDIS_URL"]
        assert url == f"redis://{_HUB_MESH_IP}:6379/4"


class TestGlitchtipSpokeWiring:
    def test_sentry_dsn_uses_mesh_ip_on_spoke(self):
        mock_deployer = MagicMock()
        prov = InfrastructureProvisioner(deployer=mock_deployer)
        ctx = _ctx("vps2")
        with (
            patch(
                "fabrik.drivers.glitchtip.create_project",
                return_value=_ok(dsn="http://key@glitchtip-web:8000/9"),
            ),
            patch("fabrik.drivers.glitchtip.verify_dsn_injection", return_value=True),
            patch("fabrik.drivers.glitchtip.delete_project"),
        ):
            prov._provision_glitchtip("spoke-app", ctx, dry_run=False)
        env = _injected(mock_deployer)
        assert env["SENTRY_DSN"] == f"http://key@{_HUB_MESH_IP}:8000/9"
        assert env["GLITCHTIP_DSN"] == f"http://key@{_HUB_MESH_IP}:8000/9"

    def test_dsn_verify_inspects_the_spoke_container_and_the_api_stays_on_the_hub(
        self, monkeypatch
    ):
        """The container lives on the spoke, so the docker-inspect verify must ssh there;
        the GlitchTip API calls (create, delete) are hub-side and must not be swapped."""
        monkeypatch.delenv("FABRIK_VPS_SSH_HOST", raising=False)
        seen: dict[str, str | None] = {}

        def _host(label):
            def record(*_a, **_k):
                seen[label] = os.environ.get("FABRIK_VPS_SSH_HOST")
                return _ok(dsn="http://key@glitchtip-web:8000/9") if label == "create" else True

            return record

        prov = InfrastructureProvisioner(deployer=MagicMock())
        with (
            patch("fabrik.drivers.glitchtip.create_project", side_effect=_host("create")),
            patch("fabrik.drivers.glitchtip.verify_dsn_injection", side_effect=_host("verify")),
            patch("fabrik.drivers.glitchtip.delete_project"),
        ):
            prov._provision_glitchtip("spoke-app", _ctx("vps2"), dry_run=False)

        assert seen == {"create": None, "verify": "vps2"}
        assert os.environ.get("FABRIK_VPS_SSH_HOST") is None

    def test_a_failed_verify_rolls_back_on_the_hub_and_restores_the_host(self, monkeypatch):
        """verify False → delete_project runs unswapped, DsnInjectionError raises, the env is restored."""
        monkeypatch.delenv("FABRIK_VPS_SSH_HOST", raising=False)
        hosts: list[str | None] = []
        prov = InfrastructureProvisioner(deployer=MagicMock())
        with (
            patch(
                "fabrik.drivers.glitchtip.create_project",
                return_value=_ok(dsn="http://key@glitchtip-web:8000/9"),
            ),
            patch("fabrik.drivers.glitchtip.verify_dsn_injection", return_value=False),
            patch(
                "fabrik.drivers.glitchtip.delete_project",
                side_effect=lambda *_a, **_k: hosts.append(os.environ.get("FABRIK_VPS_SSH_HOST")),
            ),
            pytest.raises(DsnInjectionError, match="Project rolled back"),
        ):
            prov._provision_glitchtip("spoke-app", _ctx("vps2"), dry_run=False)

        assert hosts == [None]
        assert os.environ.get("FABRIK_VPS_SSH_HOST") is None

    def test_a_failed_verify_never_deletes_a_project_that_already_existed(self):
        """On a refresh (or re-apply) create_project finds the project (`exists`); a failed verify
        still fails the run but must not delete the live project."""
        prov = InfrastructureProvisioner(deployer=MagicMock())
        with (
            patch(
                "fabrik.drivers.glitchtip.create_project",
                return_value=_ok(status="exists", dsn="http://key@glitchtip-web:8000/9"),
            ),
            patch("fabrik.drivers.glitchtip.verify_dsn_injection", return_value=False),
            patch("fabrik.drivers.glitchtip.delete_project") as rm,
            pytest.raises(DsnInjectionError, match="Existing project kept"),
        ):
            prov._provision_glitchtip("spoke-app", _ctx("vps1"), dry_run=False)
        rm.assert_not_called()


class TestWatchdogSpokeRouting:
    def test_a_spoke_watchdog_is_refused_before_the_driver_and_vps1_runs_unswapped(
        self, monkeypatch
    ):
        """W-37dda1e1: a spoke watchdog could not alert (apprise is vps1-only), so the registrar refuses it
        before the driver; vps1 still provisions, with no host swap."""
        monkeypatch.delenv("FABRIK_VPS_SSH_HOST", raising=False)
        seen: list[str | None] = []

        def record(self, ctx, *, dry_run=False):
            seen.append(os.environ.get("FABRIK_VPS_SSH_HOST"))
            return {"status": "provisioned"}

        prov = InfrastructureProvisioner(deployer=MagicMock())
        with patch("fabrik.drivers.watchdog.WatchdogDriver.provision", record):
            prov._provision_watchdog("spoke-app", _ctx("vps2"), dry_run=False)
            prov._provision_watchdog("spoke-app", _ctx("vps1"), dry_run=False)

        assert seen == [None]
        assert os.environ.get("FABRIK_VPS_SSH_HOST") is None
