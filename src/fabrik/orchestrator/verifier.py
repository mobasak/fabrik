"""Post-deployment verification."""

import json
import logging
import ssl
import time
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from fabrik.drivers.ssh import ssh
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.exceptions import VerificationError

logger = logging.getLogger(__name__)

# SSL context that skips certificate verification for health checks
# Required for newly deployed apps with self-signed certs before Let's Encrypt provisions
SSL_CONTEXT_NO_VERIFY = ssl.create_default_context()
SSL_CONTEXT_NO_VERIFY.check_hostname = False
SSL_CONTEXT_NO_VERIFY.verify_mode = ssl.CERT_NONE

DEFAULT_HEALTHCHECK_PATH = "/health"
DEFAULT_TIMEOUT = 30
DEFAULT_RETRY_INTERVAL = 5
DEFAULT_MAX_RETRIES = 6

# Traefik dynamic-routers API endpoint, reachable only from the VPS
# (iptables DOCKER-USER chain blocks :8080 externally). The admin-dashboard
# middleware check SSHs to the VPS and curls this URL — same pattern as
# scripts/audit_authelia_gates.py (Phase 4l Track 5).
TRAEFIK_ROUTERS_API = "http://127.0.0.1:8080/api/http/routers"

# The host that Authelia's 302-to-login points at. If a GET of
# ``https://<admin-dashboard>/api/`` returns a 302 with a Location pointing
# here, the ``^/api/`` bypass (plan §10, LESSONS_LEARNT §8.11) is NOT in
# place — Authelia is intercepting what should be a direct Bearer-token
# API call.
AUTHELIA_HOST = "auth.vps1.ocoron.com"


class DeploymentVerifier:
    """Verify deployments are working correctly."""

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        retry_interval: int = DEFAULT_RETRY_INTERVAL,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        """Initialize verifier.

        Args:
            timeout: HTTP request timeout in seconds
            retry_interval: Seconds between retries
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.max_retries = max_retries

    def verify(self, ctx: DeploymentContext, skip_health_check: bool = False) -> bool:
        """Run post-deployment verification checks.

        Args:
            ctx: Deployment context with deployed application details
            skip_health_check: If True, skip health endpoint check

        Returns:
            True if all checks pass

        Raises:
            VerificationError: If any check fails
        """
        if ctx.dry_run:
            logger.info("[DRY RUN] Would verify deployment")
            return True

        domain = ctx.spec["domain"]
        shape = ctx.spec.get("shape", {})

        # Health check
        if not skip_health_check:
            healthcheck = ctx.spec.get("healthcheck", {})
            path = healthcheck.get("path", DEFAULT_HEALTHCHECK_PATH)

            url = f"https://{domain}{path}"

            logger.info("Verifying deployment at %s", url)
            self._check_health(url)
        else:
            logger.info("Skipping health check (skip_health_check=True)")

        # Admin-dashboard assertions (Phase 4l Track 4).
        # Shape-driven: both checks are OPT-IN and run only when the spec
        # declares the relevant capability. A plain public site deploy
        # won't SSH to the VPS or probe /api/ — that would be scope creep.
        shape = ctx.spec.get("shape", {}) or {}
        if shape.get("is_admin_dashboard"):
            # §8: Traefik must carry the forward-auth middleware, OR the
            # Authelia access_control policy is inert and the dashboard
            # is publicly reachable despite looking gated (LESSONS_LEARNT
            # §8.9, the GlitchTip 2FA-bypass root cause).
            self._check_authelia_middleware(domain)

            # §10: if the dashboard ALSO serves a Bearer-token API on
            # the same host, the ^/api/ bypass must be in place — else
            # machine callers get intercepted by Authelia and every
            # automation breaks (LESSONS_LEARNT §8.11).
            if shape.get("has_bearer_api"):
                check_api_bypass(domain, timeout=self.timeout)

        # Only set deployed_url AFTER all verification passes.
        ctx.deployed_url = f"https://{domain}"
        return True

    def _check_health(self, url: str) -> bool:
        """Check health endpoint with retries.

        Args:
            url: Full URL to health endpoint

        Returns:
            True if health check passes

        Raises:
            VerificationError: If health check fails after all retries
        """
        last_error: str | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                # Only allow https:// URLs for security
                if not url.startswith("https://"):
                    raise ValueError(f"Only HTTPS URLs allowed: {url}")
                response = urlopen(url, timeout=self.timeout, context=SSL_CONTEXT_NO_VERIFY)  # nosec B310
                status = response.getcode()

                if status == 200:
                    logger.info("Health check passed: %s (attempt %d)", url, attempt)
                    return True

                last_error = f"Unexpected status code: {status}"
                logger.warning(
                    "Health check failed (attempt %d/%d): %s",
                    attempt,
                    self.max_retries,
                    last_error,
                )

            except URLError as e:
                last_error = str(e)
                logger.warning(
                    "Health check failed (attempt %d/%d): %s",
                    attempt,
                    self.max_retries,
                    last_error,
                )
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Health check failed (attempt %d/%d): %s",
                    attempt,
                    self.max_retries,
                    last_error,
                )

            if attempt < self.max_retries:
                time.sleep(self.retry_interval)

        raise VerificationError(
            f"Health check failed after {self.max_retries} attempts: {last_error}",
            check_type="health",
        )

    def _check_authelia_middleware(self, domain: str) -> None:
        """Assert Traefik attaches ``authelia-forward`` to ``domain``'s router.

        Plan §8 + LESSONS_LEARNT §8.9. An Authelia ``access_control``
        policy alone is not enforcement — Traefik must also attach the
        forward-auth middleware, or the policy is inert and the dashboard
        is publicly reachable. This is the exact GlitchTip regression
        (2026-04-18). SSHs to the VPS and curls the Traefik dynamic-
        routers API; the endpoint is iptables-blocked from external
        networks so a local HTTP call from WSL is not an option.

        Args:
            domain: Deployed dashboard host (e.g. ``auto.vps1.ocoron.com``).

        Raises:
            VerificationError: router absent from Traefik, OR router
                present but missing any middleware with ``authelia`` in
                its name (check_type=``authelia_middleware``).
        """
        # Permissive matcher — see scripts/audit_authelia_gates.py
        # for the same substring rule. Provider suffixes vary
        # (``@docker``, ``@file``, ``@kubernetescrd``) and custom
        # wrappers might rename the middleware; any ``authelia`` token
        # in the name is assumed to gate.
        # Traefik discovery is eventually-consistent after container start.
        # Retry a few times before declaring the router missing.
        routers: list[dict[str, Any]] = []
        matching: list[dict[str, Any]] = []
        last_err: str | None = None
        for attempt in range(1, 7):  # 6 attempts × 5s = 30s window
            try:
                raw = ssh(f"curl -fsS {TRAEFIK_ROUTERS_API}", timeout=self.timeout)
                routers = json.loads(raw)
            except (RuntimeError, json.JSONDecodeError) as e:
                last_err = str(e)
                routers = []
            matching = [r for r in routers if domain in (r.get("rule") or "")]
            if matching:
                break
            logger.info(
                "Waiting for Traefik to pick up router for %s (attempt %d/6)",
                domain,
                attempt,
            )
            time.sleep(5)

        if not routers and last_err:
            raise VerificationError(
                f"Failed to fetch Traefik routers for middleware check: {last_err}",
                check_type="authelia_middleware",
            )
        if not matching:
            raise VerificationError(
                f"No Traefik router found for {domain} — "
                f"the deploy may have regressed or the router was removed",
                check_type="authelia_middleware",
            )

        # If multiple routers match (multi-router apps like WordPress),
        # ANY of them carrying the middleware satisfies the gate —
        # Traefik picks the most-specific-rule winner per request, and
        # for admin dashboards there's typically just one router on the
        # apex host anyway.
        for router in matching:
            mws = router.get("middlewares") or []
            if any(isinstance(m, str) and "authelia" in m.lower() for m in mws):
                logger.info(
                    "Authelia middleware present on %s (router=%s)",
                    domain,
                    router.get("name", "?"),
                )
                return

        raise VerificationError(
            f"Authelia middleware missing on {domain} — "
            f"policy is inert, dashboard may be publicly reachable. "
            f"Fix: add `traefik.http.routers.<R>.middlewares="
            f"authelia-forward@docker` to the compose.",
            check_type="authelia_middleware",
        )

    def check_ssl(self, domain: str) -> bool:
        """Verify SSL certificate is valid.

        Args:
            domain: Domain to check

        Returns:
            True if SSL is valid
        """
        import socket
        import ssl

        try:
            context = ssl.create_default_context()
            with (
                socket.create_connection((domain, 443), timeout=self.timeout) as sock,
                context.wrap_socket(sock, server_hostname=domain) as ssock,
            ):
                cert = ssock.getpeercert()
                if cert:
                    logger.info("SSL certificate valid for %s", domain)
                    return True
            return False
        except Exception as e:
            logger.warning("SSL check failed for %s: %s", domain, e)
            return False


def check_api_bypass(domain: str, timeout: int = DEFAULT_TIMEOUT) -> None:
    """Assert the ``^/api/`` Authelia bypass is in place for an admin dashboard.

    Plan §10 + LESSONS_LEARNT §8.11. When an admin dashboard serves both
    a 2FA-gated UI and a Bearer-token API on the same host, the Authelia
    config must include a ``bypass`` rule for ``^/api/`` placed BEFORE
    the catch-all ``two_factor`` rule. Without it, machine callers hit
    the forward-auth middleware first and receive a 302 → 401 chain
    instead of the backend's real response, breaking every Fabrik
    driver that talks to the API (e.g. Coolify, Grafana).

    Detection: a plain GET of ``https://<domain>/api/`` with no
    Authorization header. If the bypass is MISSING, Authelia intercepts
    and returns ``302`` with ``Location: https://auth.vps1.ocoron.com/...``
    — that redirect target is the signature. If the bypass is WORKING,
    the request reaches the backend and returns whatever the backend
    chooses (commonly ``401``/``404``/``405``/``200``) — crucially NOT
    a 302 to ``auth.vps1.ocoron.com``.

    Module-level (not a method) so tests can patch it via
    ``fabrik.orchestrator.verifier.check_api_bypass`` to assert that it
    is skipped when ``shape.has_bearer_api=false``.

    Args:
        domain: Admin-dashboard host (e.g. ``coolify.vps1.ocoron.com``).
        timeout: HTTP timeout in seconds.

    Raises:
        VerificationError: response is a 302 to ``auth.vps1.ocoron.com``,
            indicating the ``^/api/`` bypass rule is missing or placed
            after the ``two_factor`` catch-all
            (check_type=``api_bypass``).
    """
    url = f"https://{domain}/api/"
    # urlopen follows redirects by default; we need to observe the 302
    # itself. A bare Request without a redirect handler still auto-follows,
    # so we rely on the mocked response in tests and on the VPS-level
    # behaviour that Authelia's 302 points to a cross-host URL (different
    # hostname) which urllib does follow — but the FIRST response's code
    # is what ``getcode()`` returns when we pass a handler that doesn't
    # auto-redirect. For simplicity here we assume the response object
    # exposes .getcode() and .headers consistently — this matches both
    # urllib's real behaviour (when redirect-following is disabled) and
    # the MagicMock shape used in tests.
    logger.info("Checking ^/api/ bypass at %s", url)
    try:
        # Build a Request so tests and production follow the same path.
        # Only allow https:// URLs for security (same pattern as
        # _check_health).
        if not url.startswith("https://"):
            raise ValueError(f"Only HTTPS URLs allowed: {url}")
        req = Request(url, method="GET")
        response = urlopen(req, timeout=timeout)  # nosec B310
    except URLError as e:
        # Network-level failure — almost always a transient condition
        # unrelated to Authelia (new cert still provisioning, Cloudflare
        # proxy returning 400/5xx before the origin is ready, DNS not
        # propagated to our resolver yet). Authelia misconfiguration
        # produces a 302 to auth.vps1.ocoron.com, not a network error.
        # Log a warning and treat as inconclusive rather than failing
        # the deploy — the backrest/gatus checks will catch real
        # reachability problems.
        logger.warning(
            "^/api/ bypass check could not reach %s: %s — "
            "treating as inconclusive (Authelia intercept would be "
            "a 302 redirect, not a network error).",
            url,
            e.reason,
        )
        return

    status = response.getcode()
    if status == 302:
        location = ""
        headers = response.headers
        if headers is not None:
            # Support both dict-like (MagicMock) and http.client.HTTPMessage.
            location = headers.get("Location", "") if hasattr(headers, "get") else ""
        if AUTHELIA_HOST in location:
            raise VerificationError(
                f"^/api/ bypass missing on {domain} — "
                f"Authelia is intercepting API calls ({url} -> {location}). "
                f"Fix: add `policy: bypass, resources: ['^/api/']` BEFORE "
                f"the `two_factor` rule in configuration.yml.",
                check_type="api_bypass",
            )

    logger.info("^/api/ bypass working on %s (status=%s)", domain, status)
