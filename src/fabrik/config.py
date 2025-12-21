"""
Configuration loading for Fabrik.

Loads settings from:
1. Environment variables (.env)
2. Config files (config/platform.yaml)
3. Command-line arguments (override)
"""

import os
from pathlib import Path
from typing import Any

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
SPECS_DIR = PROJECT_ROOT / "specs"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
LOGS_DIR = PROJECT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data"
TMP_DIR = PROJECT_ROOT / ".tmp"
CACHE_DIR = PROJECT_ROOT / ".cache"


def get_env(key: str, default: str | None = None, required: bool = False) -> str | None:
    """Get environment variable with optional default and required check."""
    value = os.environ.get(key, default)
    if required and value is None:
        raise ValueError(f"Required environment variable {key} is not set")
    return value


def ensure_directories() -> None:
    """Ensure all required directories exist."""
    for dir_path in [LOGS_DIR, DATA_DIR, TMP_DIR, CACHE_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)


class Config:
    """Fabrik configuration container."""

    def __init__(self) -> None:
        """Initialize configuration from environment."""
        # VPS
        self.vps_host = get_env("VPS_HOST", required=True)
        self.vps_user = get_env("VPS_USER", "deploy")
        self.vps_ssh_key = get_env("VPS_SSH_KEY", "~/.ssh/id_rsa")

        # Coolify
        self.coolify_url = get_env("COOLIFY_API_URL", required=True)
        self.coolify_token = get_env("COOLIFY_API_TOKEN", required=True)

        # DNS
        self.dns_provider = get_env("DNS_PROVIDER", "namecheap")

        # Logging
        self.log_level = get_env("LOG_LEVEL", "INFO")
        self.log_format = get_env("LOG_FORMAT", "json")

    def to_dict(self) -> dict[str, Any]:
        """Return configuration as dictionary."""
        return {
            "vps_host": self.vps_host,
            "vps_user": self.vps_user,
            "coolify_url": self.coolify_url,
            "dns_provider": self.dns_provider,
            "log_level": self.log_level,
        }
