"""Post-deployment verification."""

import logging
import time
from urllib.error import URLError
from urllib.request import urlopen

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.exceptions import VerificationError

logger = logging.getLogger(__name__)

DEFAULT_HEALTHCHECK_PATH = "/health"
DEFAULT_TIMEOUT = 30
DEFAULT_RETRY_INTERVAL = 5
DEFAULT_MAX_RETRIES = 6


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

    def verify(self, ctx: DeploymentContext) -> bool:
        """Run all verification checks.

        Args:
            ctx: Deployment context

        Returns:
            True if all checks pass

        Raises:
            VerificationError: If any check fails
        """
        if ctx.dry_run:
            logger.info("[DRY RUN] Would verify deployment")
            return True

        domain = ctx.spec["domain"]
        healthcheck = ctx.spec.get("healthcheck", {})
        path = healthcheck.get("path", DEFAULT_HEALTHCHECK_PATH)

        url = f"https://{domain}{path}"
        ctx.deployed_url = f"https://{domain}"

        logger.info("Verifying deployment at %s", url)
        return self._check_health(url)

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
                response = urlopen(url, timeout=self.timeout)  # nosec B310
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
                last_error = str(e.reason)
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
