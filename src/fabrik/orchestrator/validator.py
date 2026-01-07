"""Spec validation for orchestrator."""

import hashlib
import ipaddress
import logging
import re
from pathlib import Path
from typing import Any

import yaml

from fabrik.orchestrator.exceptions import ValidationError

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ["name", "template", "domain"]
OPTIONAL_FIELDS = ["server", "env", "secrets", "healthcheck"]

# Blocked hostnames for SSRF prevention
BLOCKED_HOSTNAMES = frozenset([
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
])

# Valid domain pattern: alphanumeric with hyphens, 2+ parts, valid TLD
DOMAIN_PATTERN = re.compile(
    r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.[a-zA-Z0-9-]{1,63})*\.[a-zA-Z]{2,}$"
)


def is_private_ip(hostname: str) -> bool:
    """Check if hostname resolves to a private/reserved IP.

    Args:
        hostname: Hostname or IP address to check

    Returns:
        True if private/reserved IP, False otherwise
    """
    try:
        ip = ipaddress.ip_address(hostname)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_reserved
            or ip.is_link_local
            or ip.is_multicast
        )
    except ValueError:
        # Not an IP address, check if it's a blocked hostname
        return False


def validate_domain_security(domain: str) -> str | None:
    """Validate domain for SSRF prevention.

    Args:
        domain: Domain to validate

    Returns:
        Error message if invalid, None if valid
    """
    domain_lower = domain.lower().strip()

    # Block localhost and variants
    if domain_lower in BLOCKED_HOSTNAMES:
        return f"Blocked hostname: {domain}"

    # Block raw IP addresses (private ranges)
    if is_private_ip(domain_lower):
        return f"Private/reserved IP not allowed: {domain}"

    # Check for IP address format (block all raw IPs for safety)
    try:
        ipaddress.ip_address(domain_lower)
        return f"Raw IP addresses not allowed, use a domain: {domain}"
    except ValueError:
        pass  # Not an IP, continue

    # Validate domain format
    if not DOMAIN_PATTERN.match(domain_lower):
        return f"Invalid domain format: {domain}"

    # Block internal TLDs
    if domain_lower.endswith((".local", ".internal", ".test", ".invalid")):
        return f"Internal/reserved TLD not allowed: {domain}"

    return None


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
        self.templates_dir = templates_dir or Path("/opt/fabrik/templates")

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
            with open(spec_path) as f:
                spec = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML: {e}", field="syntax")

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

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in spec:
                raise ValidationError(f"Missing required field: {field}", field=field)

        # Validate name format
        name = spec["name"]
        if not isinstance(name, str) or not name.replace("-", "").replace("_", "").isalnum():
            raise ValidationError(
                "Name must be alphanumeric with hyphens/underscores", field="name"
            )

        # Validate template exists
        template = spec["template"]
        template_path = self.templates_dir / template
        if not template_path.exists():
            warnings.append(f"Template not found: {template}")

        # Validate domain format and security (SSRF prevention)
        domain = spec["domain"]
        if not isinstance(domain, str):
            raise ValidationError("Domain must be a string", field="domain")

        domain_error = validate_domain_security(domain)
        if domain_error:
            raise ValidationError(domain_error, field="domain")

        # Validate secrets is a list
        if "secrets" in spec and not isinstance(spec["secrets"], list):
            raise ValidationError("Secrets must be a list", field="secrets")

        # Validate healthcheck
        if "healthcheck" in spec:
            hc = spec["healthcheck"]
            if not isinstance(hc, dict):
                raise ValidationError("Healthcheck must be a mapping", field="healthcheck")
            if "path" not in hc:
                warnings.append("Healthcheck missing 'path', using /health")

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
