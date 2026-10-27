"""Secrets management - load from env, .env, or generate."""

import logging
import os
import secrets
import string
from pathlib import Path

from fabrik.env_file import parse_env
from fabrik.orchestrator.exceptions import ValidationError

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
    """Load variables from a .env file, read as compose reads it (``fabrik.env_file``, D-1277).

    Every value is a plain ``str``: a secret is a literal, so a ``$`` in it is never a template.

    Args:
        env_path: Path to .env file

    Returns:
        Dict of key-value pairs; empty when the file does not exist

    Raises:
        ValidationError: the file is not UTF-8 or compose would refuse it (an unterminated quote,
            a quote after the closing quote). Fail closed: an unread key would be minted over the
            real secret. The message names the file, key and line or byte offset, never a value.
    """
    if not env_path.exists():
        return {}
    try:
        parsed = parse_env(env_path.read_text())
    except UnicodeDecodeError as e:
        # The decoder's own message quotes the offending byte, which may sit inside a secret.
        raise ValidationError(f"cannot read {env_path}: not UTF-8 at byte {e.start}") from None
    except ValueError as e:
        raise ValidationError(f"cannot read {env_path}: {e}") from None
    for key, value in parsed.items():
        if "\n" in value:
            # Legal (compose reads it too), but an unterminated quote swallows the next KEY= line
            # the same way, and that key would then be minted in silence — so say which one.
            logger.warning("%s: the value of %s spans lines", env_path, key)
    return {key: str(value) for key, value in parsed.items()}


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
