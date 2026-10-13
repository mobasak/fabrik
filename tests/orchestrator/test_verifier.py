"""Tests for deployment verification."""

import itertools
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from fabrik.orchestrator import verifier as verifier_module
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.exceptions import VerificationError
from fabrik.orchestrator.verifier import DeploymentVerifier

# the REAL method, captured at import — the autouse stub below replaces it on the class for every test, so the
# tests OF _wait_for_dns (W-2178bedc) call this binding with their own instance
_ORIGINAL_WAIT_FOR_DNS = DeploymentVerifier._wait_for_dns


@pytest.fixture(autouse=True)
def _no_live_dns_or_sleep(monkeypatch):
    # verify() runs real `dig` against 1.1.1.1 for up to 120 s (_wait_for_dns) and sleeps 5 s per Traefik
    # router poll (six polls); a unit test must reach neither — five tests here took 30-120 s each (W-1996f86b).
    # A test that patches _wait_for_dns on its own instance still wins.
    monkeypatch.setattr(
        DeploymentVerifier, "_wait_for_dns", lambda self, domain, max_wait=120: None
    )
    monkeypatch.setattr(verifier_module.time, "sleep", lambda seconds: None)


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

    def test_health_disabled_skips_inband_probe_and_succeeds(self):
        """A ``health.disabled`` service must NOT gate the deploy on an in-band
        HTTP probe — liveness is owned by external Gatus + the deployer's
        readiness poll. Verify: no ``_check_health`` / ``_wait_for_dns`` call,
        ``verify()`` returns True, and ``deployed_url`` is set.

        Regression: Zitadel deploy RUN 3 (2026-08-28) — the container served
        /debug/ready 200 in-network, but the verifier's external probe raced
        DNS/cert propagation, raised VerificationError, and rolled back the
        whole healthy deploy (incl. the just-created DNS record).
        """
        verifier = DeploymentVerifier(max_retries=1)
        ctx = DeploymentContext(
            spec_path=Path("zitadel.yaml"),
            spec={
                "name": "zitadel",
                "domain": "auth.ocoron.com",
                "health": {"disabled": True, "path": "/debug/ready"},
            },
        )

        with (
            patch.object(verifier, "_check_health") as mock_health,
            patch.object(verifier, "_wait_for_dns") as mock_dns,
        ):
            result = verifier.verify(ctx)

        assert result is True
        mock_health.assert_not_called()
        mock_dns.assert_not_called()
        assert ctx.deployed_url == "https://auth.ocoron.com"

    def test_health_enabled_still_probes(self):
        """The complement: a service WITHOUT health.disabled must still run the
        in-band probe — the skip is gated strictly on the flag."""
        verifier = DeploymentVerifier(max_retries=1)
        ctx = DeploymentContext(
            spec_path=Path("api.yaml"),
            spec={"name": "api", "domain": "api.example.com", "health": {"path": "/health"}},
        )

        with (
            patch.object(verifier, "_wait_for_dns", return_value=None),
            patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen,
        ):
            mock_urlopen.return_value = MagicMock(getcode=lambda: 200)
            result = verifier.verify(ctx)

        assert result is True
        mock_urlopen.assert_called_once()

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


_DIG_TIMEOUT = object()  # a queued `dig` answer that raises TimeoutExpired instead
_DIG_OSERROR = object()  # … or OSError (dig found by which() but failing to exec)
# every `dig` runs with exactly these — captured output, text mode, a 10 s cap, no raise on a nonzero exit
# (a `check=True` would turn dig's exit 9 into a CalledProcessError nothing catches; review O1)
_DIG_KWARGS = {"capture_output": True, "text": True, "timeout": 10, "check": False}


class _FakeDig:
    """`subprocess.run` stand-in for `_wait_for_dns`: records every argv; the NS lookup answers `ns_stdout` (or
    times out), each A poll pops the next queued stdout (`_DIG_TIMEOUT` raises; an empty queue answers nothing)."""

    def __init__(self, ns_stdout: str = "", a_stdouts=(), ns_raises=None):
        self.calls: list[list[str]] = []
        self.ns_stdout = ns_stdout
        self.a_stdouts = list(a_stdouts)
        self.ns_raises = ns_raises  # None, _DIG_TIMEOUT or _DIG_OSERROR

    @staticmethod
    def _raise(kind, argv):
        if kind is _DIG_TIMEOUT:
            raise subprocess.TimeoutExpired(argv, 10)
        raise OSError(13, "Permission denied", "/usr/bin/dig")

    def __call__(self, argv, **kw):
        argv = list(argv)
        self.calls.append(argv)
        assert argv[0] == "dig", (
            argv
        )  # a fixed argv (a `shell=` kwarg would fail the equality below)
        assert kw == _DIG_KWARGS, kw
        if "NS" in argv:
            if self.ns_raises is not None:
                self._raise(self.ns_raises, argv)
            return SimpleNamespace(stdout=self.ns_stdout, returncode=0)
        out = self.a_stdouts.pop(0) if self.a_stdouts else ""
        if out is _DIG_TIMEOUT or out is _DIG_OSERROR:
            self._raise(out, argv)
        return SimpleNamespace(stdout=out, returncode=0)


class TestWaitForDnsAuthoritativePoll:
    """W-2178bedc: `_wait_for_dns` (B19 — the zone's authoritative NS is asked directly, so a resolver's negative
    cache cannot hide a live record) had no unit test; it only ever ran as a live `dig`. These run the REAL method
    with `subprocess.run` and `shutil.which` replaced; `time.sleep` is the autouse no-op."""

    def _run(self, monkeypatch, fake, *, domain="app.example.com", max_wait=120, dig_present=True):
        monkeypatch.setattr(
            shutil, "which", lambda name: "/usr/bin/dig" if dig_present and name == "dig" else None
        )
        monkeypatch.setattr(subprocess, "run", fake)
        return _ORIGINAL_WAIT_FOR_DNS(DeploymentVerifier(), domain, max_wait=max_wait)

    def test_without_dig_it_returns_none_and_runs_nothing(self, monkeypatch):
        fake = _FakeDig(ns_stdout="ns1.example-dns.com.\n", a_stdouts=["1.2.3.4\n"])
        assert self._run(monkeypatch, fake, dig_present=False) is None
        assert fake.calls == []

    def test_the_zone_ns_is_asked_once_then_its_first_server_is_polled_for_the_a_record(
        self, monkeypatch
    ):
        fake = _FakeDig(
            ns_stdout="ns1.example-dns.com.\nns2.example-dns.com.\n", a_stdouts=["", "1.2.3.4\n"]
        )
        assert self._run(monkeypatch, fake) == "1.2.3.4"
        # the zone is the last two labels, asked of the public resolver once
        assert fake.calls[0] == ["dig", "+short", "NS", "example.com", "@1.1.1.1"]
        # every A poll goes to the FIRST authoritative server, trailing dot stripped, bounded per query
        polls = fake.calls[1:]
        assert len(polls) == 2
        for argv in polls:
            assert argv == [
                "dig",
                "+short",
                "+time=3",
                "+tries=1",
                "A",
                "app.example.com",
                "@ns1.example-dns.com",
            ]

    def test_a_failed_ns_lookup_falls_back_to_the_public_resolver(self, monkeypatch):
        for failure in (_DIG_TIMEOUT, _DIG_OSERROR):  # both halves of the except clause
            fake = _FakeDig(ns_raises=failure, a_stdouts=["5.6.7.8\n"])
            assert self._run(monkeypatch, fake) == "5.6.7.8"
            assert fake.calls[1][-1] == "@1.1.1.1"
        empty = _FakeDig(ns_stdout="\n", a_stdouts=["5.6.7.8\n"])  # an empty answer, not an error
        assert self._run(monkeypatch, empty) == "5.6.7.8"
        assert empty.calls[1][-1] == "@1.1.1.1"

    def test_the_poll_skips_cname_lines_and_survives_a_timed_out_or_failed_query(self, monkeypatch):
        # a CNAME chain prints the alias first; only a line starting with a digit is an address
        fake = _FakeDig(
            ns_stdout="ns1.example-dns.com.\n",
            a_stdouts=[_DIG_TIMEOUT, _DIG_OSERROR, "alias.example.com.\n9.9.9.9\n"],
        )
        assert self._run(monkeypatch, fake) == "9.9.9.9"
        assert (
            len(fake.calls) == 4
        )  # NS + the timed-out poll + the failed poll + the answering poll

    def test_it_gives_up_after_max_wait_and_returns_none(self, monkeypatch):
        # a fake clock: every read advances one second (unbounded — review S3), so a 3-second budget
        # allows exactly two polls (reads at 1 s and 2 s; the read at 3 s ends the `<` loop); the sleep
        # between polls is recorded, so the 5 s cadence is pinned too (review O4)
        clock = itertools.count()
        monkeypatch.setattr(verifier_module.time, "time", lambda: float(next(clock)))
        sleeps: list[int] = []
        monkeypatch.setattr(verifier_module.time, "sleep", sleeps.append)
        fake = _FakeDig(ns_stdout="ns1.example-dns.com.\n", a_stdouts=[])  # never an answer
        assert self._run(monkeypatch, fake, max_wait=3) is None
        polls = fake.calls[1:]
        assert len(polls) == 2 and sleeps == [5, 5], (polls, sleeps)
        assert all(argv[4:6] == ["A", "app.example.com"] for argv in polls)
        # a zero budget: the NS lookup runs, no poll does (review H4)
        zero = _FakeDig(ns_stdout="ns1.example-dns.com.\n", a_stdouts=["1.2.3.4\n"])
        assert self._run(monkeypatch, zero, max_wait=0) is None
        assert len(zero.calls) == 1


class TestCheckHealthResolvedIpProbe:
    """W-2178bedc: `_check_health`'s resolved-IP branch (connect to the authoritative IP, send the domain as the
    Host header, bypass the OS resolver — B19) only ever ran as a live httpx call. The resolver branch (`urlopen`)
    has its own tests above; these pin the IP branch's URL, headers and retry contract."""

    def test_the_probe_connects_to_the_ip_with_the_host_header_and_never_touches_urlopen(
        self, monkeypatch
    ):
        verifier = DeploymentVerifier(max_retries=1, retry_interval=0)
        calls: list[tuple[str, dict]] = []

        def fake_get(url, **kw):
            calls.append((url, kw))
            return SimpleNamespace(status_code=200)

        monkeypatch.setattr(httpx, "get", fake_get)
        with patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen:
            assert (
                verifier._check_health(
                    "https://app.example.com:8443/api/health?deep=1#top",
                    resolved_ip="203.0.113.7",
                    host_header="app.example.com",
                )
                is True
            )
            mock_urlopen.assert_not_called()
        assert len(calls) == 1
        url, kw = calls[0]
        # the host swapped for the IP; the port, path, query and fragment kept (the port was dropped
        # before W-2178bedc's review: a health URL on 8443 was probed on 443)
        assert url == "https://203.0.113.7:8443/api/health?deep=1#top"
        assert kw["headers"] == {"Host": "app.example.com"}  # Traefik routes on the Host header
        assert (
            kw["verify"] is False
            and kw["follow_redirects"] is True
            and kw["timeout"] == verifier.timeout
        )

    def test_a_resolved_ip_without_a_host_header_takes_the_resolver_path(self, monkeypatch):
        verifier = DeploymentVerifier(max_retries=1, retry_interval=0)
        monkeypatch.setattr(
            httpx,
            "get",
            lambda *a, **k: pytest.fail("httpx must not be used without a Host header"),
        )
        with patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen:
            mock_urlopen.return_value = MagicMock(getcode=lambda: 200)
            assert (
                verifier._check_health("https://app.example.com/health", resolved_ip="203.0.113.7")
                is True
            )
            assert mock_urlopen.call_count == 1
            assert mock_urlopen.call_args.args[0] == "https://app.example.com/health"

    def test_the_probe_retries_a_non_200_and_raises_with_the_last_status(self, monkeypatch):
        verifier = DeploymentVerifier(max_retries=2, retry_interval=0)
        statuses = iter([503, 502])
        calls: list[str] = []

        def fake_get(url, **kw):
            calls.append(url)
            return SimpleNamespace(status_code=next(statuses))

        monkeypatch.setattr(httpx, "get", fake_get)
        with pytest.raises(VerificationError) as exc:
            verifier._check_health(
                "https://app.example.com/health",
                resolved_ip="203.0.113.7",
                host_header="app.example.com",
            )
        assert len(calls) == 2
        assert "2 attempts" in str(exc.value) and "Unexpected status code: 502" in str(exc.value)
        assert exc.value.check_type == "health"

    def test_a_transport_error_on_the_ip_path_is_retried_then_reported(self, monkeypatch):
        verifier = DeploymentVerifier(max_retries=2, retry_interval=0)
        answers = iter([httpx.ConnectError("connection refused"), SimpleNamespace(status_code=200)])

        def fake_get(url, **kw):
            a = next(answers)
            if isinstance(a, Exception):
                raise a
            return a

        monkeypatch.setattr(httpx, "get", fake_get)
        sleeps: list[int] = []
        monkeypatch.setattr(verifier_module.time, "sleep", sleeps.append)
        assert (
            verifier._check_health(
                "https://app.example.com/health",
                resolved_ip="203.0.113.7",
                host_header="app.example.com",
            )
            is True
        )
        assert sleeps == [0]  # one retry sleep of retry_interval between the two attempts
        with pytest.raises(StopIteration):  # both answers consumed: two calls, no more
            next(answers)

    def test_the_ip_path_still_refuses_a_non_https_url(self, monkeypatch):
        verifier = DeploymentVerifier(max_retries=1, retry_interval=0)
        monkeypatch.setattr(
            httpx, "get", lambda *a, **k: pytest.fail("a non-https URL must never reach httpx")
        )
        with pytest.raises(VerificationError) as exc:
            verifier._check_health(
                "http://app.example.com/health",
                resolved_ip="203.0.113.7",
                host_header="app.example.com",
            )
        assert "Only HTTPS URLs allowed" in str(exc.value)
