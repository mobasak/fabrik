"""
WordPress Driver - WP-CLI wrapper for WordPress container operations.

Executes WP-CLI commands inside WordPress Docker containers via SSH.
"""

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any


class ContainerNotFoundError(Exception):
    """Exception raised when a WordPress container cannot be found."""

    pass


def _get_exec_mode() -> str:
    """Resolve FABRIK_EXEC_MODE env var (default 'ssh'; fail-fast on bad value)."""
    mode = os.getenv("FABRIK_EXEC_MODE", "ssh").lower()
    if mode not in ("ssh", "local"):
        raise ValueError(f"FABRIK_EXEC_MODE must be 'ssh' or 'local', got {mode!r}")
    return mode


class ContainerResolver:
    """Resolves a WordPress container name."""

    def __init__(
        self,
        site_name: str,
        ssh_host: str = "vps",
        timeout: int = 10,
        exec_mode: str | None = None,
    ):
        """Initialize resolver."""
        self.site_name = site_name
        self.ssh_host = ssh_host
        self.timeout = timeout
        self.exec_mode = exec_mode or _get_exec_mode()
        self._cached: str | None = None

    def _slug(self) -> str:
        """Derives the environment variable slug."""
        return self.site_name.replace(".", "_").replace("-", "_").upper()

    def resolve(self) -> str:
        """Resolves the container name."""
        env_var = os.getenv(f"WP_CONTAINER_NAME_{self._slug()}")
        if env_var:
            return env_var

        try:
            # Try exact match first (Docker Compose without -1 suffix)
            if self.exec_mode == "local":
                exact_cmd = [
                    "sudo",
                    "docker",
                    "ps",
                    "--filter",
                    f"name={self.site_name}-wordpress",
                    "--format",
                    "{{.Names}}",
                ]
            else:
                exact_cmd = [
                    "ssh",
                    self.ssh_host,
                    f"sudo docker ps --filter name={self.site_name}-wordpress --format '{{{{.Names}}}}'",
                ]
            result = subprocess.run(
                exact_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if lines:
                return lines[0]

            # Try Docker Compose naming convention (with -1 suffix)
            if self.exec_mode == "local":
                prefix_cmd = [
                    "sudo",
                    "docker",
                    "ps",
                    "--filter",
                    f"name={self.site_name}-wordpress-",
                    "--format",
                    "{{.Names}}",
                ]
            else:
                prefix_cmd = [
                    "ssh",
                    self.ssh_host,
                    f"sudo docker ps --filter name={self.site_name}-wordpress- --format '{{{{.Names}}}}'",
                ]
            result = subprocess.run(
                prefix_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if lines:
                return lines[0]
        except subprocess.TimeoutExpired:
            pass

        raise ContainerNotFoundError(f"No container found for site {self.site_name!r}")

    def resolve_cached(self) -> str:
        """Resolves the container name and caches the result."""
        if self._cached is None:
            self._cached = self.resolve()
        return self._cached


@dataclass
class WPSite:
    """WordPress site configuration."""

    name: str
    domain: str
    container: str  # Docker container name

    @classmethod
    def from_name(cls, name: str) -> "WPSite":
        """
        Create WPSite from site name.

        Raises:
            ContainerNotFoundError: If a container cannot be resolved for the site.
        """
        container = ContainerResolver(name).resolve_cached()
        return cls(name=name, domain=f"{name}.vps1.ocoron.com", container=container)


class WordPressClient:
    """
    WP-CLI wrapper for WordPress operations.

    Executes commands inside WordPress containers via SSH to VPS.
    """

    def __init__(self, site: WPSite, ssh_host: str = "vps", exec_mode: str | None = None):
        """
        Initialize WordPress client.

        Args:
            site: WordPress site configuration
            ssh_host: SSH host alias (default: vps)
            exec_mode: Execution mode override ('ssh' | 'local'); defaults to FABRIK_EXEC_MODE env
        """
        self.site = site
        self.ssh_host = ssh_host
        self.exec_mode = exec_mode or _get_exec_mode()

    def _exec(self, wp_command: str, allow_root: bool = True) -> tuple[int, str]:
        """
        Execute WP-CLI command in container.

        Args:
            wp_command: WP-CLI command (without 'wp' prefix)
            allow_root: Add --allow-root flag

        Returns:
            Tuple of (exit_code, output)
        """
        root_flag = "--allow-root" if allow_root else ""
        if self.exec_mode == "local":
            full_cmd = (
                ["sudo", "docker", "exec", self.site.container, "wp"]
                + shlex.split(wp_command)
                + ([root_flag] if root_flag else [])
            )
        else:
            cmd = f"sudo docker exec {shlex.quote(self.site.container)} wp {wp_command} {root_flag}"
            full_cmd = ["ssh", self.ssh_host, cmd]

        result = subprocess.run(full_cmd, capture_output=True, text=True)

        output = result.stdout + result.stderr
        return result.returncode, output.strip()

    def run(self, command: str) -> str:
        """
        Run arbitrary WP-CLI command.

        Args:
            command: Full WP-CLI command (without 'wp' prefix)

        Returns:
            Command output

        Raises:
            RuntimeError: If command fails
        """
        code, output = self._exec(command)
        if code != 0:
            raise RuntimeError(f"WP-CLI failed: {output}")
        return output

    # ========== Core Commands ==========

    def core_version(self) -> str:
        """Get WordPress version."""
        return self.run("core version")

    def core_update(self) -> str:
        """Update WordPress core."""
        return self.run("core update")

    def core_install(
        self,
        url: str,
        title: str,
        admin_user: str,
        admin_password: str,
        admin_email: str,
        locale: str = "en_US",
    ) -> str:
        """Install WordPress."""
        cmd = (
            f"core install "
            f"--url={shlex.quote(url)} "
            f"--title={shlex.quote(title)} "
            f"--admin_user={shlex.quote(admin_user)} "
            f"--admin_password={shlex.quote(admin_password)} "  # noqa: not a hardcoded secret
            f"--admin_email={shlex.quote(admin_email)} "
            f"--locale={shlex.quote(locale)}"
        )
        return self.run(cmd)

    # ========== Plugin Commands ==========

    def plugin_list(self, format: str = "json") -> list[dict[str, Any]] | str:
        """List installed plugins."""
        output = self.run(f"plugin list --format={shlex.quote(format)}")
        if format == "json":
            return json.loads(output)
        return output

    def plugin_install(self, plugin: str, activate: bool = True) -> str:
        """
        Install plugin from WordPress.org or ZIP path.

        Args:
            plugin: Plugin slug or path to ZIP
            activate: Activate after install
        """
        activate_flag = "--activate" if activate else ""
        return self.run(f"plugin install {shlex.quote(plugin)} {activate_flag}")

    def plugin_activate(self, plugin: str) -> str:
        """Activate a plugin."""
        return self.run(f"plugin activate {shlex.quote(plugin)}")

    def plugin_deactivate(self, plugin: str) -> str:
        """Deactivate a plugin."""
        return self.run(f"plugin deactivate {shlex.quote(plugin)}")

    def plugin_delete(self, plugin: str) -> str:
        """Delete a plugin."""
        return self.run(f"plugin delete {shlex.quote(plugin)}")

    def plugin_update(self, plugin: str = "--all") -> str:
        """Update plugin(s)."""
        # Don't quote flag-like arguments (e.g., --all)
        plugin_arg = plugin if plugin.startswith("--") else shlex.quote(plugin)
        return self.run(f"plugin update {plugin_arg}")

    # ========== Theme Commands ==========

    def theme_list(self, format: str = "json") -> list[dict[str, Any]] | str:
        """List installed themes."""
        output = self.run(f"theme list --format={shlex.quote(format)}")
        if format == "json":
            return json.loads(output)
        return output

    def theme_install(self, theme: str, activate: bool = False) -> str:
        """Install theme from WordPress.org or ZIP path."""
        activate_flag = "--activate" if activate else ""
        return self.run(f"theme install {shlex.quote(theme)} {activate_flag}")

    def theme_activate(self, theme: str) -> str:
        """Activate a theme."""
        return self.run(f"theme activate {shlex.quote(theme)}")

    def theme_delete(self, theme: str) -> str:
        """Delete a theme."""
        return self.run(f"theme delete {shlex.quote(theme)}")

    # ========== User Commands ==========

    def user_list(self, format: str = "json") -> list[dict[str, Any]] | str:
        """List users."""
        output = self.run(f"user list --format={shlex.quote(format)}")
        if format == "json":
            return json.loads(output)
        return output

    def user_create(
        self, username: str, email: str, role: str = "subscriber", password: str | None = None
    ) -> str:
        """Create a new user."""
        cmd = f"user create {shlex.quote(username)} {shlex.quote(email)} --role={shlex.quote(role)}"
        if password:
            cmd += f" --user_pass={shlex.quote(password)}"
        return self.run(cmd)

    def user_update(self, user: str, **fields) -> str:
        """Update user fields."""
        field_args = " ".join(f"--{k}={shlex.quote(str(v))}" for k, v in fields.items())
        return self.run(f"user update {shlex.quote(user)} {field_args}")

    def user_delete(self, user: str, reassign: int | None = None) -> str:
        """Delete a user."""
        reassign_flag = f"--reassign={reassign}" if reassign else "--yes"
        return self.run(f"user delete {shlex.quote(user)} {reassign_flag}")

    # ========== Option Commands ==========

    def option_get(self, option: str) -> str:
        """Get an option value."""
        return self.run(f"option get {shlex.quote(option)}")

    def option_update(self, option: str, value: str) -> str:
        """Update an option value."""
        return self.run(f"option update {shlex.quote(option)} {shlex.quote(value)}")

    # ========== Database Commands ==========

    def db_export(self, file: str = "-") -> str:
        """Export database to file or stdout."""
        return self.run(f"db export {shlex.quote(file)}")

    def db_import(self, file: str) -> str:
        """Import database from file."""
        return self.run(f"db import {shlex.quote(file)}")

    def db_search_replace(self, old: str, new: str, dry_run: bool = False) -> str:
        """Search and replace in database."""
        dry_flag = "--dry-run" if dry_run else ""
        return self.run(f"search-replace {shlex.quote(old)} {shlex.quote(new)} {dry_flag}")

    # ========== Cache Commands ==========

    def cache_flush(self) -> str:
        """Flush the object cache."""
        return self.run("cache flush")

    def rewrite_flush(self) -> str:
        """Flush rewrite rules."""
        return self.run("rewrite flush")

    # ========== Language Commands ==========

    def language_list(self, format: str = "json") -> list[dict[str, Any]] | str:
        """List installed languages."""
        output = self.run(f"language core list --format={shlex.quote(format)}")
        if format == "json":
            return json.loads(output)
        return output

    def language_install(self, locale: str, activate: bool = False) -> str:
        """Install a language pack."""
        activate_flag = "--activate" if activate else ""
        return self.run(f"language core install {shlex.quote(locale)} {activate_flag}")

    def language_activate(self, locale: str) -> str:
        """Activate a language."""
        return self.run(f"site switch-language {shlex.quote(locale)}")


def get_wordpress_client(site_name: str) -> WordPressClient:
    """
    Get WordPress client for a site.

    Args:
        site_name: Name of the WordPress site (e.g., 'wp-test')

    Returns:
        Configured WordPressClient
    """
    site = WPSite.from_name(site_name)
    return WordPressClient(site)
