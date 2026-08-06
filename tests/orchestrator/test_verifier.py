"""Tests for deployment verification."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.exceptions import VerificationError
from fabrik.orchestrator.verifier import DeploymentVerifier


class TestDeploymentVerifier:
    """Test DeploymentVerifier class."""

    def test_verify_dry_run(self):
        """Dry run should skip actual verification."""
        verifier = DeploymentVerifier()
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test", "domain": "test.com"},
            dry_run=True,
        )

        result = verifier.verify(ctx)
        assert result is True

    def test_verify_uses_healthcheck_path(self):
        """Should use custom healthcheck path from spec."""
        verifier = DeploymentVerifier(max_retries=1)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={
                "name": "test",
                "domain": "test.com",
                "health": {"path": "/api/health"},
            },
        )

        with patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response

            result = verifier.verify(ctx)

            assert result is True
            mock_urlopen.assert_called_once()
            call_url = mock_urlopen.call_args[0][0]
            assert "/api/health" in call_url

    def test_verify_sets_deployed_url(self):
        """Should set deployed_url on context."""
        verifier = DeploymentVerifier(max_retries=1)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test", "domain": "example.com"},
        )

        # Force the stdlib-urlopen branch (no IP returned from DNS wait)
        # so the test's ``urlopen`` mock is the one that's exercised.
        with (
            patch.object(verifier, "_wait_for_dns", return_value=None),
            patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen,
        ):
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response

            verifier.verify(ctx)

            assert ctx.deployed_url == "https://example.com"

    def test_health_check_retries(self):
        """Should retry on failure."""
        verifier = DeploymentVerifier(max_retries=3, retry_interval=0)

        with patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200

            # Fail twice, succeed on third
            mock_urlopen.side_effect = [
                Exception("Connection refused"),
                Exception("Timeout"),
                mock_response,
            ]

            result = verifier._check_health("https://test.com/health")
            assert result is True
            assert mock_urlopen.call_count == 3

    def test_health_check_fails_after_max_retries(self):
        """Should raise VerificationError after max retries."""
        verifier = DeploymentVerifier(max_retries=2, retry_interval=0)

        with patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection refused")

            with pytest.raises(VerificationError) as exc:
                verifier._check_health("https://test.com/health")

            assert "2 attempts" in str(exc.value)
            assert exc.value.check_type == "health"

    def test_failed_verification_does_not_set_deployed_url(self):
        """Failed verification should NOT set deployed_url."""
        verifier = DeploymentVerifier(max_retries=1, retry_interval=0)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test", "domain": "test.example.com"},
        )

        with patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection refused")

            with pytest.raises(VerificationError):
                verifier.verify(ctx)

            # CRITICAL: deployed_url should NOT be set on failure
            assert ctx.deployed_url is None


# --------------------------------------------------------------------------- #
# Phase 4l Track 4: admin-dashboard Authelia + API bypass post-deploy checks
# --------------------------------------------------------------------------- #
#
# Plan acceptance criteria (docs/development/plans/2026-04-18-zero-touch-
# deployment.md:2087 and :2090):
#
#   For every project with shape.is_admin_dashboard=true: post-deploy verify
#   queries http://127.0.0.1:8080/api/http/routers and asserts
#   authelia-forward is in the router's middlewares list. Fails the deploy
#   on mismatch (§8).
#
#   Admin-dashboard API bypass (§10): verify checks both flows:
#   UI path 302s to Authelia; Bearer-token API path returns 200.
#
# Design note — shape gating:
#   * shape.is_admin_dashboard=false → both checks MUST be skipped (a public
#     site has no business being asserted against Authelia)
#   * shape.is_admin_dashboard=true AND has_bearer_api=false → only the
#     middleware check runs (§8); the bypass check is skipped because
#     there's no API path to bypass
#   * both true → both checks run (§8 + §10)
#
# Design note — SSH-based middleware check:
#   The check uses the same fabrik.drivers.ssh.ssh helper as
#   scripts/audit_authelia_gates.py (Track 5) to curl the Traefik API from
#   the VPS. SSH, not direct HTTP, because the Traefik API endpoint
#   (:8080) is deliberately iptables-blocked from external networks per the
#   4-layer security model (docs/infrastructure/vps-complete-inventory.md
#   §Security).
#
# Design note — bypass check uses status-code heuristic, not auth token:
#   If the ^/api/ bypass is MISSING, a plain GET of https://host/api/
#   returns 302 to auth.vps1.ocoron.com (Authelia intercepts). If the
#   bypass is WORKING, the request reaches the backend and returns
#   whatever the backend chooses (usually 401/404/405/200, but crucially
#   NOT a 302-to-Authelia). The check asserts absence of the 302-to-
#   Authelia signature — no bearer token required, no secrets in tests.


def _admin_spec(
    *,
    is_admin_dashboard: bool,
    has_bearer_api: bool = False,
    domain: str = "auto.vps1.ocoron.com",
) -> dict:
    """Build a minimal deployment spec with the shape flags relevant to
    Track 4. Omits unrelated fields — the verifier only reads ``domain``,
    ``healthcheck``, and ``shape``."""
    return {
        "name": "test-app",
        "domain": domain,
        "health": {"path": "/"},
        "shape": {
            "is_admin_dashboard": is_admin_dashboard,
            "has_bearer_api": has_bearer_api,
        },
    }


def _traefik_routers_with_authelia(domain: str) -> str:
    """Serialized Traefik /api/http/routers payload where ``domain``'s
    router correctly carries ``authelia-forward@docker``."""
    return json.dumps(
        [
            {
                "name": "test-app@docker",
                "rule": f"Host(`{domain}`)",
                "middlewares": ["authelia-forward@docker"],
            },
            {
                "name": "unrelated@docker",
                "rule": "Host(`public.example.com`)",
                "middlewares": [],
            },
        ]
    )


def _traefik_routers_without_authelia(domain: str) -> str:
    """Same shape, but the router is missing the authelia middleware —
    this is the exact drift §8 is designed to catch."""
    return json.dumps(
        [
            {
                "name": "test-app@docker",
                "rule": f"Host(`{domain}`)",
                "middlewares": [],
            },
        ]
    )


class TestAdminDashboardAutheliaMiddleware:
    """§8: post-deploy middleware assertion for admin dashboards.

    These tests mock two dependencies: the existing urlopen (for the
    health check that runs unconditionally) and the new ssh helper (for
    the Traefik API call). The health check always returns 200 so that
    the middleware check is the interesting failure surface."""

    def test_non_admin_dashboard_skips_middleware_check(self):
        """A deploy of a non-admin dashboard must not SSH to the VPS —
        the check is opt-in via shape.is_admin_dashboard=true. If the
        check ran unconditionally, every public-site deploy would need
        VPS SSH credentials, which is exactly the coupling the shape
        model is designed to avoid."""
        verifier = DeploymentVerifier(max_retries=1, retry_interval=0)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec=_admin_spec(is_admin_dashboard=False),
        )

        with (
            patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen,
            patch("fabrik.orchestrator.verifier.ssh") as mock_ssh,
        ):
            mock_urlopen.return_value = MagicMock(getcode=lambda: 200)

            result = verifier.verify(ctx)

            assert result is True
            mock_ssh.assert_not_called()

    def test_admin_dashboard_with_authelia_middleware_passes(self):
        verifier = DeploymentVerifier(max_retries=1, retry_interval=0)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec=_admin_spec(is_admin_dashboard=True),
        )

        with (
            patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen,
            patch(
                "fabrik.orchestrator.verifier.ssh",
                return_value=_traefik_routers_with_authelia("auto.vps1.ocoron.com"),
            ) as mock_ssh,
        ):
            mock_urlopen.return_value = MagicMock(getcode=lambda: 200)

            result = verifier.verify(ctx)

            assert result is True
            mock_ssh.assert_called_once()
            # The command must curl the Traefik routers API — confirm the
            # wiring so a future refactor doesn't silently drop the check.
            cmd = mock_ssh.call_args[0][0]
            assert "127.0.0.1:8080" in cmd
            assert "/api/http/routers" in cmd

    def test_admin_dashboard_without_middleware_raises(self):
        """This is the exact GlitchTip 2FA-bypass scenario from
        LESSONS_LEARNT §8.9 / §8.7: Authelia policy says the host is
        gated, but Traefik forgot to attach the middleware, so traffic
        reaches the backend unauthenticated. Must fail the deploy."""
        verifier = DeploymentVerifier(max_retries=1, retry_interval=0)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec=_admin_spec(is_admin_dashboard=True),
        )

        with (
            patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen,
            patch(
                "fabrik.orchestrator.verifier.ssh",
                return_value=_traefik_routers_without_authelia("auto.vps1.ocoron.com"),
            ),
        ):
            mock_urlopen.return_value = MagicMock(getcode=lambda: 200)

            with pytest.raises(VerificationError) as exc:
                verifier.verify(ctx)

            assert "authelia" in str(exc.value).lower()
            assert exc.value.check_type == "authelia_middleware"

    def test_admin_dashboard_host_not_in_traefik_raises(self):
        """If Traefik has no router for the deployed host, the deploy
        regressed (router removal, wrong entrypoint, name mismatch).
        Must fail — silence is not OK here."""
        verifier = DeploymentVerifier(max_retries=1, retry_interval=0)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec=_admin_spec(is_admin_dashboard=True, domain="missing.vps1.ocoron.com"),
        )

        with (
            patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen,
            patch(
                "fabrik.orchestrator.verifier.ssh",
                return_value=_traefik_routers_with_authelia("other.vps1.ocoron.com"),
            ),
        ):
            mock_urlopen.return_value = MagicMock(getcode=lambda: 200)

            with pytest.raises(VerificationError) as exc:
                verifier.verify(ctx)

            assert "router" in str(exc.value).lower() or "not found" in str(exc.value).lower()

    def test_failed_middleware_check_does_not_set_deployed_url(self):
        """Mirrors the existing health-check invariant (line 102-117):
        any verification failure must leave ctx.deployed_url unset so
        downstream code doesn't act on a broken deploy."""
        verifier = DeploymentVerifier(max_retries=1, retry_interval=0)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec=_admin_spec(is_admin_dashboard=True),
        )

        with (
            patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen,
            patch(
                "fabrik.orchestrator.verifier.ssh",
                return_value=_traefik_routers_without_authelia("auto.vps1.ocoron.com"),
            ),
        ):
            mock_urlopen.return_value = MagicMock(getcode=lambda: 200)

            with pytest.raises(VerificationError):
                verifier.verify(ctx)

            assert ctx.deployed_url is None

    def test_dry_run_skips_middleware_check(self):
        verifier = DeploymentVerifier()
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec=_admin_spec(is_admin_dashboard=True),
            dry_run=True,
        )

        with patch("fabrik.orchestrator.verifier.ssh") as mock_ssh:
            assert verifier.verify(ctx) is True
            mock_ssh.assert_not_called()


class TestAdminDashboardAPIBypass:
    """§10: post-deploy assertion that the ``^/api/`` Authelia bypass is in
    place for admin dashboards that also serve a Bearer-token API.

    Scenario: ``coolify.vps1.ocoron.com`` carries ``authelia-forward``
    middleware (good, UI is 2FA-gated) AND a ``^/api/`` bypass rule
    (good, Bearer-token API reaches backend). If the bypass regresses,
    machine clients start getting Authelia's 302 → 401 chain instead of
    the Coolify API's normal responses, and every Fabrik driver breaks.

    The check uses the Authelia-302 signature (Location header points at
    ``auth.vps1.ocoron.com``) instead of requiring a bearer token in
    tests — zero secrets, deterministic."""

    def test_bearer_api_false_skips_bypass_check(self):
        """A plain admin dashboard with no API surface (e.g. Netdata,
        Apprise) doesn't need the bypass — check must not run."""
        verifier = DeploymentVerifier(max_retries=1, retry_interval=0)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec=_admin_spec(is_admin_dashboard=True, has_bearer_api=False),
        )

        with (
            patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen,
            patch(
                "fabrik.orchestrator.verifier.ssh",
                return_value=_traefik_routers_with_authelia("auto.vps1.ocoron.com"),
            ),
            patch("fabrik.orchestrator.verifier.check_api_bypass") as mock_bypass,
        ):
            mock_urlopen.return_value = MagicMock(getcode=lambda: 200)

            assert verifier.verify(ctx) is True
            mock_bypass.assert_not_called()

    def test_bypass_working_when_api_does_not_redirect_to_authelia(self):
        """The expected production state for Coolify/Grafana: the ^/api/
        bypass rule in configuration.yml routes the request past
        Authelia, so Traefik forwards to the backend and returns whatever
        the backend says (usually 401 from Coolify's own auth, or 200
        for a public API probe)."""
        verifier = DeploymentVerifier(max_retries=1, retry_interval=0)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec=_admin_spec(
                is_admin_dashboard=True,
                has_bearer_api=True,
                domain="coolify.vps1.ocoron.com",
            ),
        )

        # Build a response that is NOT a 302-to-Authelia — this is what
        # a working bypass looks like end-to-end.
        backend_response = MagicMock()
        backend_response.getcode.return_value = 401  # backend's own auth
        backend_response.headers = {}

        def urlopen_side_effect(url, *args, **kwargs):
            # The health check hits path=/ (from _admin_spec); it must
            # return 200 so the test isolates the bypass check as the
            # failure surface.
            url_str = url if isinstance(url, str) else getattr(url, "full_url", "")
            if "/api/" in url_str:
                return backend_response
            health = MagicMock()
            health.getcode.return_value = 200
            return health

        with (
            patch("fabrik.orchestrator.verifier.urlopen", side_effect=urlopen_side_effect),
            patch(
                "fabrik.orchestrator.verifier.ssh",
                return_value=_traefik_routers_with_authelia("coolify.vps1.ocoron.com"),
            ),
        ):
            assert verifier.verify(ctx) is True

    def test_bypass_missing_when_api_302s_to_authelia_raises(self):
        """The exact §8.11 regression scenario: adding authelia-forward
        to a host that serves a Bearer API, WITHOUT a ^/api/ bypass,
        makes Authelia intercept API calls. The 302's Location header
        points at ``auth.vps1.ocoron.com`` — that's the signature."""
        verifier = DeploymentVerifier(max_retries=1, retry_interval=0)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec=_admin_spec(
                is_admin_dashboard=True,
                has_bearer_api=True,
                domain="coolify.vps1.ocoron.com",
            ),
        )

        # Simulate Authelia-302 on the /api/ path.
        authelia_redirect = MagicMock()
        authelia_redirect.getcode.return_value = 302
        authelia_redirect.headers = {
            "Location": "https://auth.vps1.ocoron.com/?rd=https%3A%2F%2Fcoolify..."
        }

        def urlopen_side_effect(url, *args, **kwargs):
            url_str = url if isinstance(url, str) else getattr(url, "full_url", "")
            if "/api/" in url_str:
                return authelia_redirect
            health = MagicMock()
            health.getcode.return_value = 200
            return health

        with (
            patch("fabrik.orchestrator.verifier.urlopen", side_effect=urlopen_side_effect),
            patch(
                "fabrik.orchestrator.verifier.ssh",
                return_value=_traefik_routers_with_authelia("coolify.vps1.ocoron.com"),
            ),
        ):
            with pytest.raises(VerificationError) as exc:
                verifier.verify(ctx)

            assert "bypass" in str(exc.value).lower() or "authelia" in str(exc.value).lower()
            assert exc.value.check_type == "api_bypass"
