"""
WordPress Driver - WP-CLI wrapper for WordPress container operations.

Executes WP-CLI commands inside WordPress Docker containers via SSH.
"""

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class WPSite:
    """WordPress site configuration."""
    name: str
    domain: str
    container: str  # Docker container name
    
    @classmethod
    def from_name(cls, name: str) -> "WPSite":
        """Create WPSite from site name (assumes standard naming)."""
        return cls(
            name=name,
            domain=f"{name}.vps1.ocoron.com",
            container=f"{name}-wordpress"
        )


class WordPressClient:
    """
    WP-CLI wrapper for WordPress operations.
    
    Executes commands inside WordPress containers via SSH to VPS.
    """
    
    def __init__(self, site: WPSite, ssh_host: str = "vps"):
        """
        Initialize WordPress client.
        
        Args:
            site: WordPress site configuration
            ssh_host: SSH host alias (default: vps)
        """
        self.site = site
        self.ssh_host = ssh_host
    
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
        cmd = f"sudo docker exec {self.site.container} wp {wp_command} {root_flag}"
        
        full_cmd = ["ssh", self.ssh_host, cmd]
        
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True
        )
        
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
        locale: str = "en_US"
    ) -> str:
        """Install WordPress."""
        cmd = (
            f"core install "
            f"--url='{url}' "
            f"--title='{title}' "
            f"--admin_user='{admin_user}' "
            f"--admin_password='{admin_password}' "
            f"--admin_email='{admin_email}' "
            f"--locale='{locale}'"
        )
        return self.run(cmd)
    
    # ========== Plugin Commands ==========
    
    def plugin_list(self, format: str = "json") -> list[dict]:
        """List installed plugins."""
        output = self.run(f"plugin list --format={format}")
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
        return self.run(f"plugin install {plugin} {activate_flag}")
    
    def plugin_activate(self, plugin: str) -> str:
        """Activate a plugin."""
        return self.run(f"plugin activate {plugin}")
    
    def plugin_deactivate(self, plugin: str) -> str:
        """Deactivate a plugin."""
        return self.run(f"plugin deactivate {plugin}")
    
    def plugin_delete(self, plugin: str) -> str:
        """Delete a plugin."""
        return self.run(f"plugin delete {plugin}")
    
    def plugin_update(self, plugin: str = "--all") -> str:
        """Update plugin(s)."""
        return self.run(f"plugin update {plugin}")
    
    # ========== Theme Commands ==========
    
    def theme_list(self, format: str = "json") -> list[dict]:
        """List installed themes."""
        output = self.run(f"theme list --format={format}")
        if format == "json":
            return json.loads(output)
        return output
    
    def theme_install(self, theme: str, activate: bool = False) -> str:
        """Install theme from WordPress.org or ZIP path."""
        activate_flag = "--activate" if activate else ""
        return self.run(f"theme install {theme} {activate_flag}")
    
    def theme_activate(self, theme: str) -> str:
        """Activate a theme."""
        return self.run(f"theme activate {theme}")
    
    def theme_delete(self, theme: str) -> str:
        """Delete a theme."""
        return self.run(f"theme delete {theme}")
    
    # ========== User Commands ==========
    
    def user_list(self, format: str = "json") -> list[dict]:
        """List users."""
        output = self.run(f"user list --format={format}")
        if format == "json":
            return json.loads(output)
        return output
    
    def user_create(
        self,
        username: str,
        email: str,
        role: str = "subscriber",
        password: Optional[str] = None
    ) -> str:
        """Create a new user."""
        cmd = f"user create {username} {email} --role={role}"
        if password:
            cmd += f" --user_pass='{password}'"
        return self.run(cmd)
    
    def user_update(self, user: str, **fields) -> str:
        """Update user fields."""
        field_args = " ".join(f"--{k}='{v}'" for k, v in fields.items())
        return self.run(f"user update {user} {field_args}")
    
    def user_delete(self, user: str, reassign: Optional[int] = None) -> str:
        """Delete a user."""
        reassign_flag = f"--reassign={reassign}" if reassign else "--yes"
        return self.run(f"user delete {user} {reassign_flag}")
    
    # ========== Option Commands ==========
    
    def option_get(self, option: str) -> str:
        """Get an option value."""
        return self.run(f"option get {option}")
    
    def option_update(self, option: str, value: str) -> str:
        """Update an option value."""
        return self.run(f"option update {option} '{value}'")
    
    # ========== Database Commands ==========
    
    def db_export(self, file: str = "-") -> str:
        """Export database to file or stdout."""
        return self.run(f"db export {file}")
    
    def db_import(self, file: str) -> str:
        """Import database from file."""
        return self.run(f"db import {file}")
    
    def db_search_replace(self, old: str, new: str, dry_run: bool = False) -> str:
        """Search and replace in database."""
        dry_flag = "--dry-run" if dry_run else ""
        return self.run(f"search-replace '{old}' '{new}' {dry_flag}")
    
    # ========== Cache Commands ==========
    
    def cache_flush(self) -> str:
        """Flush the object cache."""
        return self.run("cache flush")
    
    def rewrite_flush(self) -> str:
        """Flush rewrite rules."""
        return self.run("rewrite flush")
    
    # ========== Language Commands ==========
    
    def language_list(self, format: str = "json") -> list[dict]:
        """List installed languages."""
        output = self.run(f"language core list --format={format}")
        if format == "json":
            return json.loads(output)
        return output
    
    def language_install(self, locale: str, activate: bool = False) -> str:
        """Install a language pack."""
        activate_flag = "--activate" if activate else ""
        return self.run(f"language core install {locale} {activate_flag}")
    
    def language_activate(self, locale: str) -> str:
        """Activate a language."""
        return self.run(f"site switch-language {locale}")


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
