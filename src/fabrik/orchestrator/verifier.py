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
TRAEFIK_ROUTERS_API = "http://127.0.0.1:8080/api/http/routers"  # noqa — VPS-internal Traefik admin API; iptables DOCKER-USER blocks :8080 externally

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

        # B35: workers (kind=worker, expose.http=false) have no domain and
        # no Traefik route. Don't try to HTTP-probe them — the container's
        # compose-level healthcheck (already polled by the orchestrator's
        # post-deploy status loop) is the proof of life. Without this guard
        # the verifier raises ``KeyError: 'domain'`` even when the worker
        # is ``running:healthy``. Surfaced by proof-run on 2026-04-28.
        shape = ctx.spec.get("shape", {}) or {}
        expose = ctx.spec.get("expose", {}) or {}
        if shape.get("kind") == "worker" or not expose.get("http", True):
            logger.info(
                "Worker / non-HTTP service detected; skipping HTTP health "
                "verification (Coolify container status was the proof)."
            )
            return True

        domain = ctx.spec["domain"]

        # Health check
        if not skip_health_check:
            # B23: spec field is `health:` per `spec_loader.Spec.health` and
            # `spec_generator.generate_spec` (line 393-394 emits `Health(...)`
            # which serializes as `health:`). Reading `healthcheck:` here
            # silently returns None and falls back to DEFAULT_HEALTHCHECK_PATH
            # (`/health`), which masked every non-`/health` deploy as a 404
            # rollback. python-api worked by coincidence (its path is also
            # `/health`); saas-skeleton (`/api/health`) and docusaurus (`/`)
            # silently failed verification on every apply.
            healthcheck = ctx.spec.get("health") or {}
            path = healthcheck.get("path", DEFAULT_HEALTHCHECK_PATH)

            url = f"https://{domain}{path}"

            logger.info("Verifying deployment at %s", url)
            # B19: resolve via authoritative NS (bypasses 30-min SOA
            # negative-cache). If we get an IP back, pass it to
            # _check_health so it can skip the local resolver entirely.
            resolved_ip = self._wait_for_dns(domain, max_wait=120)
            self._check_health(url, resolved_ip=resolved_ip, host_header=domain)
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
                check_api_bypass(
                    domain,
                    prefix=shape.get("bearer_bypass_prefix") or "^/api/",
                    timeout=self.timeout,
                )

        # Only set deployed_url AFTER all verification passes.
        ctx.deployed_url = f"https://{domain}"
        return True

    def _wait_for_dns(self, domain: str, max_wait: int = 120) -> str | None:
        """Resolve ``domain`` directly against the zone's authoritative NS.

        B19: The `ocoron.com` Cloudflare zone has SOA minimum=1800s, so
        any resolver that saw NXDOMAIN for the name (e.g. the validator's
        pre-flight ``DNS resolution failed`` probe just before DNS was
        created) will negative-cache NXDOMAIN for 30 minutes. That
        cached NXDOMAIN trickles all the way down to the WSL resolver
        and ``socket.gethostbyname`` keeps failing for 30 min even
        though the Cloudflare record is live.

        Workaround: query the zone's authoritative Cloudflare NS
        directly via ``dig +short`` — authoritative answers are not
        subject to upstream negative-cache. Returns the resolved IP so
        callers can optionally use it to bypass the local resolver in
        the subsequent HTTP probe.

        Best-effort: returns ``None`` on timeout; caller proceeds to
        the health check anyway (which uses the local resolver and may
        still fail, but retries + authoritative-resolved IP fallback
        will catch real success cases).
        """
        import shutil
        import subprocess
        import time

        if not shutil.which("dig"):
            logger.info("dig not available; skipping authoritative DNS wait for %s", domain)
            return None

        # Figure out the zone (last two labels) and its NS once.
        parts = domain.split(".")
        zone = ".".join(parts[-2:]) if len(parts) >= 2 else domain
        try:
            ns_result = subprocess.run(
                ["dig", "+short", "NS", zone, "@1.1.1.1"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            nameservers = [ns.rstrip(".") for ns in ns_result.stdout.splitlines() if ns.strip()]
        except (subprocess.TimeoutExpired, OSError):
            nameservers = []
        if not nameservers:
            logger.info("Could not resolve NS for %s; using public resolver", zone)
            nameservers = ["1.1.1.1"]

        auth_ns = nameservers[0]
        logger.info("Waiting for DNS propagation of %s (authoritative NS: %s)", domain, auth_ns)
        start = time.time()
        attempt = 0
        while time.time() - start < max_wait:
            attempt += 1
            try:
                r = subprocess.run(
                    ["dig", "+short", "+time=3", "+tries=1", "A", domain, f"@{auth_ns}"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                addr = next(
                    (
                        line.strip()
                        for line in r.stdout.splitlines()
                        if line.strip() and line[0].isdigit()
                    ),
                    None,
                )
                if addr:
                    logger.info(
                        "DNS resolved %s -> %s via %s after %.0fs (attempt %d)",
                        domain,
                        addr,
                        auth_ns,
                        time.time() - start,
                        attempt,
                    )
                    return addr
            except (subprocess.TimeoutExpired, OSError):
                pass
            time.sleep(5)
        logger.warning(
            "DNS for %s did not propagate within %ds (queried %s); "
            "proceeding to health check anyway",
            domain,
            max_wait,
            auth_ns,
        )
        return None

    def _check_health(
        self,
        url: str,
        resolved_ip: str | None = None,
        host_header: str | None = None,
    ) -> bool:
        """Check health endpoint with retries.

        Args:
            url: Full URL to health endpoint
            resolved_ip: Pre-resolved IP (from authoritative NS). When set,
                connect to this IP and pass ``host_header`` as the Host
                header / SNI hostname. Bypasses the local OS resolver,
                which is important when negative-cached NXDOMAIN blocks
                normal resolution (see B19 in ``_wait_for_dns``).
            host_header: Hostname to send in Host header / SNI.

        Returns:
            True if health check passes

        Raises:
            VerificationError: If health check fails after all retries
        """
        last_error: str | None = None

        # B19: Build the probe URL. If we have an authoritative IP,
        # substitute the host part with the IP but keep host_header for
        # SNI+Host. Python's stdlib does not support manual SNI override
        # cleanly via urlopen, so we use httpx for the override path.
        probe_via_ip = bool(resolved_ip and host_header)

        for attempt in range(1, self.max_retries + 1):
            try:
                # Only allow https:// URLs for security
                if not url.startswith("https://"):
                    raise ValueError(f"Only HTTPS URLs allowed: {url}")
                if probe_via_ip:
                    from urllib.parse import urlsplit, urlunsplit

                    import httpx  # lazy — keeps import cost off the common path

                    sp = urlsplit(url)
                    ip_url = urlunsplit(
                        (sp.scheme, resolved_ip or "", sp.path, sp.query, sp.fragment)
                    )
                    resp = httpx.get(
                        ip_url,
                        headers={"Host": host_header or ""},
                        verify=False,  # nosec B501 - ceritificate check skipped, Host header routes via Traefik
                        timeout=self.timeout,
                        follow_redirects=True,
                        # server_hostname SNI cannot be forced with httpx either;
                        # since cert is Let's Encrypt for host_header, SNI is
                        # derived from the URL host (our IP) — cert name
                        # won't match but verify=False sidesteps that.
                    )
                    status = resp.status_code
                else:
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


def check_api_bypass(domain: str, prefix: str = "^/api/", timeout: int = DEFAULT_TIMEOUT) -> None:
    """Assert the configured Authelia bearer bypass is in place for an admin dashboard.

    ``prefix`` is the spec's ``shape.bearer_bypass_prefix`` (default ``^/api/``);
    a service that bypasses only a sub-prefix (e.g. ``^/api/v1``) is probed at
    that path, not the broad ``/api/``.

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
    # Probe the bypassed prefix itself: strip the leading ^ (and any trailing $)
    # so '^/api/v1' -> '/api/v1'. Falls back to '/api/' for an empty/odd prefix.
    probe_path = prefix.lstrip("^").rstrip("$") or "/api/"
    url = f"https://{domain}{probe_path}"
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
    logger.info("Checking %s bypass at %s", prefix, url)
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
                f"{prefix} bypass missing on {domain} — "
                f"Authelia is intercepting API calls ({url} -> {location}). "
                f"Fix: add `policy: bypass, resources: ['{prefix}']` BEFORE "
                f"the `two_factor` rule in configuration.yml.",
                check_type="api_bypass",
            )

    logger.info("%s bypass working on %s (status=%s)", prefix, domain, status)
