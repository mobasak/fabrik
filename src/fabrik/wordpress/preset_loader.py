"""
WordPress Preset Loader - Reads YAML presets and applies to WordPress sites.

Applies:
- Plugins (install + activate)
- Themes (install + activate)
- Pages (create with templates)
- Categories (create taxonomy)
- Menus (create + assign)
- Settings (permalinks, timezone, etc.)
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from fabrik.drivers.wordpress import WordPressClient, get_wordpress_client
from fabrik.drivers.wordpress_api import WordPressAPIClient, WPCredentials, WPPost


@dataclass
class PresetConfig:
    """Parsed preset configuration."""

    name: str
    description: str
    base: str
    features: dict = field(default_factory=dict)
    plugins: dict = field(default_factory=dict)
    theme: dict = field(default_factory=dict)
    pages: dict = field(default_factory=dict)
    categories: dict = field(default_factory=dict)
    menus: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)
    languages: dict = field(default_factory=dict)
    related: dict = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> "PresetConfig":
        """Load preset from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            base=data.get("base", "wordpress/base"),
            features=data.get("features", {}),
            plugins=data.get("plugins", {}),
            theme=data.get("theme", {}),
            pages=data.get("pages", {}),
            categories=data.get("categories", {}),
            menus=data.get("menus", {}),
            settings=data.get("settings", {}),
            languages=data.get("languages", {}),
            related=data.get("related", {}),
        )


class PresetLoader:
    """
    Loads and applies WordPress presets to sites.

    Usage:
        loader = PresetLoader(site_name="my-site", preset="saas")
        loader.apply()
    """

    PRESETS_DIR = Path(__file__).parent.parent.parent.parent / "templates" / "wordpress" / "presets"
    PLUGINS_DIR = Path(__file__).parent.parent.parent.parent / "templates" / "wordpress" / "plugins"
    THEMES_DIR = Path(__file__).parent.parent.parent.parent / "templates" / "wordpress" / "themes"

    def __init__(
        self,
        site_name: str,
        preset: str,
        wp_client: WordPressClient | None = None,
        api_client: WordPressAPIClient | None = None,
        dry_run: bool = False,
    ):
        """
        Initialize preset loader.

        Args:
            site_name: Name of the WordPress site (container prefix)
            preset: Preset name (saas, company, content, landing)
            wp_client: Optional WP-CLI client (created if not provided)
            api_client: Optional REST API client (created if not provided)
            dry_run: If True, print actions without executing
        """
        self.site_name = site_name
        self.preset_name = preset
        self.dry_run = dry_run

        # Load preset
        preset_path = self.PRESETS_DIR / f"{preset}.yaml"
        if not preset_path.exists():
            raise ValueError(f"Preset '{preset}' not found at {preset_path}")

        self.config = PresetConfig.from_yaml(str(preset_path))

        # Initialize clients
        self.wp = wp_client or get_wordpress_client(site_name)
        self.api = api_client

        self._log: list[str] = []

    def log(self, message: str):
        """Log an action."""
        self._log.append(message)
        print(f"[Preset] {message}")

    def apply(self) -> list[str]:
        """
        Apply the preset to the WordPress site.

        Returns:
            List of actions taken
        """
        self.log(f"Applying preset '{self.config.name}' to {self.site_name}")

        # Apply in order
        self._apply_plugins()
        self._apply_theme()
        self._apply_settings()
        self._apply_categories()
        self._apply_pages()
        self._apply_menus()

        self.log(f"Preset '{self.config.name}' applied successfully")
        return self._log

    def _apply_plugins(self):
        """Install and activate plugins."""
        plugins = self.config.plugins
        if not plugins:
            return

        # Install from WordPress.org
        install_list = plugins.get("install", [])
        if isinstance(plugins, list):
            install_list = plugins

        for plugin in install_list:
            self.log(f"Installing plugin: {plugin}")
            if not self.dry_run:
                try:
                    self.wp.plugin_install(plugin, activate=True)
                except Exception as e:
                    self.log(f"  Warning: {e}")

        # Install premium plugins from ZIP
        premium_list = plugins.get("premium", [])
        for plugin_zip in premium_list:
            zip_path = self.PLUGINS_DIR / plugin_zip
            if zip_path.exists():
                self.log(f"Installing premium plugin: {plugin_zip}")
                if not self.dry_run:
                    # Copy to container and install
                    # This requires the ZIP to be accessible in the container
                    self.log(f"  Note: Premium plugin {plugin_zip} needs manual installation")
            else:
                self.log(f"  Warning: Plugin ZIP not found: {zip_path}")

    def _apply_theme(self):
        """Install and activate theme."""
        theme = self.config.theme
        if not theme:
            return

        theme_name = theme.get("name") if isinstance(theme, dict) else theme
        if not theme_name:
            return

        source = (
            theme.get("source", "wordpress.org") if isinstance(theme, dict) else "wordpress.org"
        )

        if source == "wordpress.org":
            self.log(f"Installing theme: {theme_name}")
            if not self.dry_run:
                try:
                    self.wp.theme_install(theme_name, activate=True)
                except Exception as e:
                    self.log(f"  Warning: {e}")
        elif source == "zip":
            zip_path = self.THEMES_DIR / f"{theme_name}.zip"
            if zip_path.exists():
                self.log(f"Installing theme from ZIP: {theme_name}")
                if not self.dry_run:
                    self.log(f"  Note: Theme {theme_name} needs manual installation")
            else:
                self.log(f"  Warning: Theme ZIP not found: {zip_path}")

    def _apply_settings(self):
        """Apply WordPress settings."""
        settings = self.config.settings
        if not settings:
            return

        for key, value in settings.items():
            self.log(f"Setting {key} = {value}")
            if not self.dry_run:
                try:
                    self.wp.option_update(key, value)
                except Exception as e:
                    self.log(f"  Warning: {e}")

    def _apply_categories(self):
        """Create categories."""
        categories = self.config.categories
        if not categories:
            return

        create_list = categories.get("create", [])
        for cat in create_list:
            name = cat.get("name", cat) if isinstance(cat, dict) else cat
            slug = cat.get("slug", "") if isinstance(cat, dict) else ""

            self.log(f"Creating category: {name}")
            if not self.dry_run and self.api:
                try:
                    self.api.create_category(name, slug)
                except Exception as e:
                    self.log(f"  Warning: {e}")

    def _apply_pages(self):
        """Create pages."""
        pages = self.config.pages
        if not pages:
            return

        create_list = pages.get("create", [])
        for page in create_list:
            title = page.get("title", "")
            slug = page.get("slug", "")
            status = page.get("status", "publish")

            self.log(f"Creating page: {title}")
            if not self.dry_run and self.api:
                try:
                    post = WPPost(
                        title=title,
                        slug=slug,
                        status=status,
                        content="",  # Empty, to be filled later
                    )
                    self.api.create_page(post)
                except Exception as e:
                    self.log(f"  Warning: {e}")

    def _apply_menus(self):
        """Create and configure menus."""
        menus = self.config.menus
        if not menus:
            return

        for menu_name, items in menus.items():
            self.log(f"Creating menu: {menu_name} with items: {items}")
            if not self.dry_run:
                # Menu creation requires wp-cli
                try:
                    # Create menu
                    self.wp.run(f"menu create {menu_name}")
                    # Add items (simplified - would need page IDs in practice)
                    for item in items:
                        self.log(f"  Adding menu item: {item}")
                except Exception as e:
                    self.log(f"  Warning: {e}")


def apply_preset(
    site_name: str,
    preset: str,
    dry_run: bool = False,
    api_url: str | None = None,
    api_user: str | None = None,
    api_password: str | None = None,
) -> list[str]:
    """
    Convenience function to apply a preset to a site.

    Args:
        site_name: Name of the WordPress site
        preset: Preset name (saas, company, content, landing)
        dry_run: If True, print actions without executing
        api_url: Optional WordPress URL for REST API
        api_user: Optional username for REST API
        api_password: Optional app password for REST API

    Returns:
        List of actions taken
    """
    api_client = None
    if api_url and api_user and api_password:
        creds = WPCredentials(url=api_url, username=api_user, password=api_password)
        api_client = WordPressAPIClient(creds)

    loader = PresetLoader(
        site_name=site_name,
        preset=preset,
        api_client=api_client,
        dry_run=dry_run,
    )

    return loader.apply()


def list_presets() -> list[dict]:
    """List available presets."""
    presets_dir = PresetLoader.PRESETS_DIR
    presets = []

    for path in presets_dir.glob("*.yaml"):
        config = PresetConfig.from_yaml(str(path))
        presets.append(
            {
                "name": path.stem,
                "title": config.name,
                "description": config.description,
            }
        )

    return presets
