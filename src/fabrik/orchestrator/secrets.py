"""Secrets management - load from env, .env, or generate."""

import logging
import os
import secrets
import string
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_secret(length: int = 32) -> str:
    """Generate a cryptographically secure random secret.

    Args:
        length: Length of secret (default 32)

    Returns:
        Alphanumeric secret string
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def load_dotenv(env_path: Path) -> dict[str, str]:
    """Load variables from a .env file.

    Args:
        env_path: Path to .env file

    Returns:
        Dict of key-value pairs
    """
    result: dict[str, str] = {}
    if not env_path.exists():
        return result

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("\"'")
                result[key] = value
    return result


class SecretsManager:
    """Load secrets from env vars, .env files, or generate them.

    Priority order:
    1. Environment variables (for CI/CD)
    2. Project .env file (for local dev)
    3. Auto-generate (CSPRNG, 32 char alphanumeric)
    """

    def __init__(self, project_dir: Path | None = None):
        """Initialize secrets manager.

        Args:
            project_dir: Project directory containing .env file
        """
        self.project_dir = project_dir or Path.cwd()
        self._dotenv_cache: dict[str, str] | None = None

    @property
    def dotenv(self) -> dict[str, str]:
        """Lazy-load .env file."""
        if self._dotenv_cache is None:
            env_path = self.project_dir / ".env"
            self._dotenv_cache = load_dotenv(env_path)
        return self._dotenv_cache

    def get(self, key: str, generate_if_missing: bool = True) -> str | None:
        """Get a secret by key.

        Args:
            key: Secret name
            generate_if_missing: If True, generate a new secret if not found

        Returns:
            Secret value or None
        """
        # 1. Check environment variables first (CI/CD)
        value = os.environ.get(key)
        if value:
            logger.debug("Secret %s loaded from environment", key)
            return value

        # 2. Check .env file (local dev)
        value = self.dotenv.get(key)
        if value:
            logger.debug("Secret %s loaded from .env", key)
            return value

        # 3. Generate if allowed
        if generate_if_missing:
            value = generate_secret()
            logger.info("Secret %s auto-generated", key)
            return value

        return None

    def load_all(self, keys: list[str], generate_if_missing: bool = True) -> dict[str, str]:
        """Load multiple secrets.

        Args:
            keys: List of secret names
            generate_if_missing: If True, generate missing secrets

        Returns:
            Dict of secret name to value
        """
        result: dict[str, str] = {}
        for key in keys:
            value = self.get(key, generate_if_missing=generate_if_missing)
            if value:
                result[key] = value
        return result

    def get_missing(self, keys: list[str]) -> list[str]:
        """Check which secrets are missing (not in env or .env).

        Args:
            keys: List of secret names to check

        Returns:
            List of missing secret names
        """
        missing = []
        for key in keys:
            if key not in os.environ and key not in self.dotenv:
                missing.append(key)
        return missing
