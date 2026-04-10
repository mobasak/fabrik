"""Spec generation and project context extraction for scaffold-to-deploy automation."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from fabrik.spec_loader import (
    Expose,
    Health,
    Kind,
    Resources,
    SecretsPolicy,
    Spec,
    create_spec,
    save_spec,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

SPEC_ENABLED_TYPES: frozenset[str] = frozenset(
    {
        "python-api",
        "saas-skeleton",
        "node-api",
        "file-api",
        "file-worker",
        "chrome-extension",
        "static-site",
    }
)

SECRET_PATTERNS: tuple[str, ...] = (
    "PASSWORD",
    "SECRET",
    "KEY",
    "TOKEN",
    "CREDENTIAL",
    "PRIVATE",
)

_TYPE_DEFAULTS: dict[str, dict] = {
    "python-api": {"memory": "512M", "cpu": "0.5", "health_path": "/health"},
    "node-api": {"memory": "256M", "cpu": "0.5", "health_path": "/api/health"},
    "saas-skeleton": {"memory": "256M", "cpu": "0.5", "health_path": "/api/health"},
    "static-site": {"memory": "256M", "cpu": "0.5", "health_path": "/api/health"},
    "chrome-extension": {"memory": "256M", "cpu": "0.5", "health_path": "/api/health"},
    "file-api": {"memory": "256M", "cpu": "0.5", "health_path": "/api/health"},
    "file-worker": {"memory": "256M", "cpu": "0.5", "health_path": None},
}

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_secret(key: str) -> bool:
    """Return True if *key* matches any pattern in SECRET_PATTERNS (case-insensitive)."""
    upper = key.upper()
    return any(pattern in upper for pattern in SECRET_PATTERNS)


def _parse_compose_env(compose_path: Path) -> dict[str, str]:
    """Parse environment variables from the first service in a compose.yaml.

    Handles both list format (``["KEY=VALUE"]``) and dict format
    (``{KEY: VALUE}``).  Returns ``{}`` on any error.
    """
    try:
        with open(compose_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        if data is None:
            return {}

        services = data.get("services", {})
        if not services:
            return {}

        first_service = next(iter(services.values()))
        env_raw = first_service.get("environment")
        if env_raw is None:
            return {}

        result: dict[str, str] = {}

        if isinstance(env_raw, list):
            for item in env_raw:
                item_str = str(item)
                if "=" in item_str:
                    k, v = item_str.split("=", 1)
                    result[k.strip()] = v.strip()
                else:
                    result[item_str.strip()] = ""
        elif isinstance(env_raw, dict):
            for k, v in env_raw.items():
                result[str(k)] = str(v) if v is not None else ""

        return result
    except Exception:
        logger.debug("Failed to parse compose env from %s", compose_path, exc_info=True)
        return {}


def _parse_env_example(env_example_path: Path) -> list[str]:
    """Return secret key names found in ``.env.example``.

    Lines starting with ``#`` and blank lines are skipped.  Only keys that
    match :func:`_is_secret` are returned.  Returns ``[]`` if the file does
    not exist.
    """
    if not env_example_path.exists():
        return []

    secrets: list[str] = []
    try:
        with open(env_example_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key = line.split("=", 1)[0].strip()
                if key and _is_secret(key):
                    secrets.append(key)
    except Exception:
        logger.debug("Failed to parse .env.example at %s", env_example_path, exc_info=True)
        return []

    return secrets


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def extract_project_context(project_path: Path) -> dict:
    """Extract environment, secrets, and dependency info from a scaffolded project.

    Returns a dict with keys ``env``, ``secrets``, ``depends_postgres``,
    ``depends_redis``, ``project_type``.
    """
    # Read project type from project.yaml
    project_type = None
    project_yaml_path = project_path / "project.yaml"
    if project_yaml_path.exists():
        try:
            project_yaml = yaml.safe_load(project_yaml_path.read_text())
            project_type = project_yaml.get("type")
        except Exception:
            pass  # Fall through to None

    compose_env = _parse_compose_env(project_path / "compose.yaml")
    secret_keys = _parse_env_example(project_path / ".env.example")

    env: dict[str, str] = {}
    secrets: list[str] = list(secret_keys)  # from .env.example

    for k, v in compose_env.items():
        if _is_secret(k):
            if k not in secrets:
                secrets.append(k)
        else:
            env[k] = v

    # Dependency detection — scan both keys and values (case-insensitive)
    all_text = " ".join(
        [k.lower() for k in compose_env] + [v.lower() for v in compose_env.values()]
    )

    depends_postgres = "database_url" in all_text or "postgres" in all_text
    depends_redis = "redis_url" in all_text or "redis" in all_text

    return {
        "env": env,
        "secrets": secrets,
        "depends_postgres": depends_postgres,
        "depends_redis": depends_redis,
        "project_type": project_type,
    }


def generate_spec(
    name: str,
    project_type: str,
    domain: str | None,
    context: dict | None = None,
) -> Spec:
    """Build a :class:`Spec` for a scaffolded project.

    Raises:
        ValueError: If *project_type* is not in :data:`SPEC_ENABLED_TYPES`.
    """
    if project_type not in SPEC_ENABLED_TYPES:
        raise ValueError(
            f"Unsupported project type for spec generation: {project_type!r}. "
            f"Supported types: {sorted(SPEC_ENABLED_TYPES)}"
        )

    ctx = context or {}
    defaults = _TYPE_DEFAULTS[project_type]

    # Kind & expose
    if project_type == "file-worker":
        kind = Kind.WORKER
        expose = Expose(http=False)
        domain = None  # workers have no domain
    else:
        kind = Kind.SERVICE
        expose = Expose()

    # Resources
    resources = Resources(memory=defaults["memory"], cpu=defaults["cpu"])

    # Health
    health_path = defaults["health_path"]
    health = Health(path=health_path) if health_path is not None else None

    # Dependencies
    from fabrik.spec_loader import Depends

    depends = Depends(
        postgres="main" if ctx.get("depends_postgres") else None,
        redis="main" if ctx.get("depends_redis") else None,
    )

    # Secrets
    secrets_policy = SecretsPolicy(required=ctx.get("secrets", []))

    return create_spec(
        id=name,
        template=project_type,
        domain=domain,
        kind=kind,
        expose=expose,
        resources=resources,
        health=health,
        depends=depends,
        secrets=secrets_policy,
        env=ctx.get("env", {}),
    )


def generate_and_save_spec(
    name: str,
    project_type: str,
    project_path: Path,
    specs_dir: Path,
) -> Path:
    """Extract project context, generate a spec, and save it.

    Returns the path to the saved spec file.

    Raises:
        RuntimeError: If spec generation or saving fails.
    """
    try:
        context = extract_project_context(project_path)
        spec = generate_spec(
            name=name,
            project_type=project_type,
            domain=f"{name}.vps1.ocoron.com",
            context=context,
        )
        spec_path = specs_dir / f"{name}.yaml"
        save_spec(spec, spec_path)
        logger.info("Spec saved to %s", spec_path)
        return spec_path
    except Exception as exc:
        raise RuntimeError(f"Spec generation failed: {exc}") from exc
