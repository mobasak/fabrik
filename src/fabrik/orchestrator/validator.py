"""Spec validation for orchestrator.

Security Note:
    Domain validation (validate_domain_security) performs DNS resolution at
    validation time as a pre-flight check. This does NOT guarantee security at
    deployment time due to DNS rebinding attacks (TOCTOU). Callers MUST
    re-validate or pin resolved IPs at connection/deployment time.
"""

import hashlib
import ipaddress
import logging
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

import yaml

from fabrik.config import FABRIK_ROOT
from fabrik.orchestrator.exceptions import ValidationError

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ["name", "template"]
# B34: ``domain`` is only required for HTTP-exposed services. Workers
# (``kind: worker`` or ``expose.http: false``) have no Traefik route and
# therefore no domain — emitting one would just be noise. The check is
# applied conditionally below.
DOMAIN_REQUIRED_FOR_HTTP = True

# DNS resolution timeout for SSRF checks (seconds)
DNS_TIMEOUT = 5

# Blocked hostnames for SSRF prevention
BLOCKED_HOSTNAMES = frozenset(
    [
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
    ]
)

# Valid domain pattern: alphanumeric with hyphens, 2+ parts, valid TLD
DOMAIN_PATTERN = re.compile(r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.[a-zA-Z0-9-]{1,63})*\.[a-zA-Z]{2,}$")


def is_private_ip(hostname: str) -> bool:
    """Check if hostname resolves to a private/reserved IP.

    Args:
        hostname: Hostname or IP address to check

    Returns:
        True if private/reserved IP, False otherwise
    """
    # First, try to parse as a literal IP address
    try:
        ip = ipaddress.ip_address(hostname)
        return (
            ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_multicast
        )
    except ValueError:
        pass  # Not a literal IP, resolve via DNS

    # Resolve hostname via DNS and check all returned addresses
    # Use thread with timeout to prevent blocking on malicious/slow DNS
    def _resolve() -> list:
        return socket.getaddrinfo(hostname, None)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_resolve)
            addr_info = future.result(timeout=DNS_TIMEOUT)
    except FuturesTimeoutError:
        logger.warning(
            "DNS resolution timeout for %s - allowing deployment (domain may not exist yet)",
            hostname,
        )
        return False  # Allow deployment - domain may be provisioned as part of this deployment
    except socket.gaierror:
        logger.info(
            "DNS resolution failed for %s - domain likely doesn't exist yet, allowing deployment",
            hostname,
        )
        return False  # Allow deployment - domain will be created during provisioning

    try:
        for _family, _type, _proto, _canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_reserved
                    or ip.is_link_local
                    or ip.is_multicast
                ):
                    return True
            except ValueError:
                continue  # Skip unparseable addresses
        return False
    except Exception:
        # Unexpected error - fail-safe
        return True


def validate_domain_security(domain: str) -> tuple[str | None, str]:
    """Validate domain for SSRF prevention.

    Warning:
        This is a pre-flight check only. DNS can change between validation
        and use (DNS rebinding). Callers MUST re-validate at deployment time.

    Args:
        domain: Domain to validate

    Returns:
        Tuple of (error_message, normalized_domain). Error is None if valid.
    """
    # Normalize and reject whitespace-padded domains
    domain_stripped = domain.strip()
    if domain_stripped != domain:
        return (f"Domain has leading/trailing whitespace: '{domain}'", domain)

    domain_lower = domain_stripped.lower()

    # Block localhost and variants
    if domain_lower in BLOCKED_HOSTNAMES:
        return (f"Blocked hostname: {domain}", domain_lower)

    # Check for IP address format (block all raw IPs for safety) - check BEFORE DNS
    try:
        ipaddress.ip_address(domain_lower)
        return (f"Raw IP addresses not allowed, use a domain: {domain}", domain_lower)
    except ValueError:
        pass  # Not an IP, continue

    # Validate domain format (cheap check before expensive DNS)
    if not DOMAIN_PATTERN.match(domain_lower):
        return (f"Invalid domain format: {domain}", domain_lower)

    # Block internal TLDs (check before DNS to give specific error message)
    if domain_lower.endswith((".local", ".internal", ".test", ".invalid")):
        return (f"Internal/reserved TLD not allowed: {domain}", domain_lower)

    # Block private/reserved IPs (requires DNS resolution for hostnames)
    # This is the expensive check - run last after all cheap validations pass
    if is_private_ip(domain_lower):
        return (f"Private/reserved IP not allowed: {domain}", domain_lower)

    return (None, domain_lower)


def compute_spec_hash(spec: dict[str, Any]) -> str:
    """Compute a hash of the spec for change detection.

    Args:
        spec: Parsed spec dictionary

    Returns:
        SHA256 hash of spec content
    """
    content = yaml.dump(spec, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class SpecValidator:
    """Validate deployment specs."""

    def __init__(self, templates_dir: Path | None = None):
        """Initialize validator.

        Args:
            templates_dir: Path to templates directory
        """
        self.templates_dir = templates_dir or FABRIK_ROOT / "templates"

    def load_spec(self, spec_path: Path) -> dict[str, Any]:
        """Load and parse a spec file.

        Args:
            spec_path: Path to YAML spec file

        Returns:
            Parsed spec dictionary

        Raises:
            ValidationError: If file cannot be loaded
        """
        if not spec_path.exists():
            raise ValidationError(f"Spec file not found: {spec_path}", field="path")

        try:
            with open(spec_path, encoding="utf-8") as f:
                spec = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML: {e}", field="syntax") from e

        if not isinstance(spec, dict):
            raise ValidationError("Spec must be a YAML mapping", field="type")

        return spec

    def validate(self, spec: dict[str, Any]) -> list[str]:
        """Validate a spec dictionary.

        Args:
            spec: Parsed spec dictionary

        Returns:
            List of validation warnings (errors raise ValidationError)

        Raises:
            ValidationError: If required fields are missing or invalid
        """
        warnings: list[str] = []

        # Backward-compatible shim: alias 'id' to 'name' for specs from fabrik new
        if "name" not in spec and "id" in spec:
            spec["name"] = spec["id"]
            logger.debug("Using 'id' as 'name' alias: %s", spec["id"])

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in spec:
                raise ValidationError(f"Missing required field: {field}", field=field)

        # Validate name format (must be string, alphanumeric with hyphens/underscores,
        # at least 1 char, and contain at least one letter to avoid conflicts with IDs)
        name = spec["name"]
        name_stripped = name.replace("-", "").replace("_", "") if isinstance(name, str) else ""
        if (
            not isinstance(name, str)
            or not name_stripped
            or not name_stripped.isalnum()
            or not any(c.isalpha() for c in name_stripped)
        ):
            raise ValidationError(
                "Name must be alphanumeric with hyphens/underscores and contain at least one letter",
                field="name",
            )

        # Validate template exists
        template = spec["template"]
        template_path = self.templates_dir / template

        # Path traversal containment check
        try:
            template_path.resolve().relative_to(self.templates_dir.resolve())
        except ValueError:
            raise ValidationError(
                f"Template path escapes templates directory: {template}", field="template"
            ) from None

        if not template_path.exists():
            warnings.append(f"Template not found: {template}")

        # B34: domain is only required when the service exposes HTTP.
        # Workers (``kind: worker`` or ``expose.http: false``) skip this
        # block entirely; they get no Traefik route, so no domain.
        shape = spec.get("shape") or {}
        expose = spec.get("expose") or {}
        is_http_exposed = (
            expose.get("http", True)
            and shape.get("kind", spec.get("kind")) != "worker"
        )
        if is_http_exposed:
            if "domain" not in spec:
                raise ValidationError("Missing required field: domain", field="domain")
            domain = spec["domain"]
            if not isinstance(domain, str):
                raise ValidationError("Domain must be a string", field="domain")

            domain_error, normalized_domain = validate_domain_security(domain)
            if domain_error:
                raise ValidationError(domain_error, field="domain")

            # Store normalized domain back to spec for consistent downstream usage
            spec["domain"] = normalized_domain
        elif "domain" in spec:
            # Worker spec accidentally has a domain — keep it but warn so we
            # don't break anything that already works.
            warnings.append(
                "Worker spec has a 'domain' field but kind=worker / expose.http=false; "
                "it will be ignored by the deployer."
            )

        # Validate secrets - accepts both old list format and new SecretsPolicy dict
        if "secrets" in spec:
            secrets = spec["secrets"]
            if isinstance(secrets, list):
                # Old format: simple list of required secret names
                pass
            elif isinstance(secrets, dict):
                # New format: SecretsPolicy with required, generate, from_env, from_file
                for key in ["required", "generate", "from_env", "from_file"]:
                    if key in secrets and not isinstance(
                        secrets[key], list if key != "from_file" else dict
                    ):
                        raise ValidationError(
                            f"Secrets.{key} must be a {'list' if key != 'from_file' else 'dict'}",
                            field=f"secrets.{key}",
                        )
                if "from_file" in secrets:
                    for env_var, file_path in secrets["from_file"].items():
                        if not isinstance(env_var, str) or not isinstance(file_path, str):
                            raise ValidationError(
                                "Secrets.from_file must be {str: str}", field="secrets.from_file"
                            )
            else:
                raise ValidationError("Secrets must be a list or dict", field="secrets")

        # Validate health (B23: canonical key is `health`, not `healthcheck`.
        # See `spec_loader.Spec.health` and `spec_generator.generate_spec`.
        # Old code read `healthcheck:` which never existed on any spec, so
        # this block was silently a no-op for 100% of deploys.)
        if "health" in spec:
            hc = spec["health"]
            if not isinstance(hc, dict):
                raise ValidationError("Health must be a mapping", field="health")
            if "path" not in hc:
                warnings.append("Health missing 'path', using /health")

        logger.info("Spec validated: %s", spec["name"])
        return warnings

    def load_and_validate(self, spec_path: Path) -> tuple[dict[str, Any], str, list[str]]:
        """Load, validate, and hash a spec.

        Args:
            spec_path: Path to spec file

        Returns:
            Tuple of (spec dict, spec hash, warnings list)
        """
        spec = self.load_spec(spec_path)
        warnings = self.validate(spec)
        spec_hash = compute_spec_hash(spec)
        return spec, spec_hash, warnings
