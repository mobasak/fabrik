"""
Configuration loading for Fabrik.

Loads settings from:
1. Environment variables (.env)
2. Config files (config/platform.yaml)
3. Command-line arguments (override)
"""

import os
import subprocess
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# FABRIK_NO_AUTOLOAD=1 opts out of the import-time .env load — the same switch libs/alerting
# honours, and the one the root conftest.py sets so a test process never absorbs the hub's real
# secrets: without it, any test importing fabrik.config (spec_loader does) loaded the WHOLE .env
# into pytest (W-f2d483a6).
if os.environ.get("FABRIK_NO_AUTOLOAD") != "1":
    load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent

# The hub's own checkout — spec docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
# § The delta D3. Kept as a bare module-level constant (not a default arg, not inlined) so a test
# can `monkeypatch.setattr(config, "_HUB_PATH", tmp_hub)` and get a resolution that never reads or
# writes the real /opt/fabrik — `_resolve_fabrik_root` looks it up fresh on every call.
_HUB_PATH = Path("/opt/fabrik")


def _resolve_fabrik_root() -> Path:
    """Tracked-output write root: `$FABRIK_ROOT` if set; else, when the cwd is inside a linked
    worktree whose git common dir's parent is `_HUB_PATH`, that worktree's toplevel; else
    `_HUB_PATH`. Every hub script that writes a tracked file resolves its root this way (spec
    § D3) instead of a hard-coded `/opt/fabrik` or a caller-pinned cwd, so a worktree agent's
    commit lands on its own branch rather than the main checkout's.

    Fails OPEN on any git error (no git binary, not a git repo, timeout) — the degraded case is
    `_HUB_PATH`, the same value this replaced.
    """
    env_root = os.environ.get("FABRIK_ROOT")
    if env_root:
        return Path(env_root)
    hub_path = _HUB_PATH.resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return hub_path
    if result.returncode != 0:
        return hub_path
    lines = result.stdout.strip().splitlines()
    if len(lines) != 2:
        return hub_path
    toplevel, common_dir = Path(lines[0]), Path(lines[1])
    if common_dir.parent.resolve() == hub_path:
        return toplevel.resolve()
    return hub_path


FABRIK_ROOT = _resolve_fabrik_root()
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

        # Coolify — DISABLED 2026-06-17 (Coolify decommissioned 2026-05-30; deploy is
        # SSH + Docker Compose via deployer_ssh.py). Commented out, not removed, to
        # preserve history. These `required=True` fields used to force dead COOLIFY_API_*
        # creds on every Config() init; nothing in the live path reads them.
        # self.coolify_url = get_env("COOLIFY_API_URL", required=True)
        # self.coolify_token = get_env("COOLIFY_API_TOKEN", required=True)
        # self.coolify_server_uuid = get_env("COOLIFY_SERVER_UUID")  # VPS to deploy to
        # self.coolify_project_uuid = get_env("COOLIFY_PROJECT_UUID")  # Default project

        # DNS (Site Provisioner service API)
        self.dns_provider = get_env("DNS_PROVIDER", "site-provisioner")
        self.dns_manager_url = get_env(
            "SITE_PROVISIONER_URL", get_env("DNS_MANAGER_URL", "https://provision.vps1.ocoron.com")
        )

        # Logging
        self.log_level = get_env("LOG_LEVEL", "INFO")
        self.log_format = get_env("LOG_FORMAT", "json")

    def to_dict(self) -> dict[str, Any]:
        """Return configuration as dictionary."""
        return {
            "vps_host": self.vps_host,
            "vps_user": self.vps_user,
            # "coolify_url": self.coolify_url,  # DISABLED 2026-06-17 (Coolify decommissioned)
            "dns_provider": self.dns_provider,
            "log_level": self.log_level,
        }
