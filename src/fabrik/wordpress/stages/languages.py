"""Languages stage - install and activate WordPress core translations."""

import logging
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)

WPML_SLUG = "sitepress-multilingual-cms"

# Maps schema plugin names to WordPress plugin slugs
MULTILINGUAL_PLUGIN_SLUGS: dict[str, str] = {
    "wpml": "sitepress-multilingual-cms",
    "polylang": "polylang",
    "translatepress": "translatepress-multilingual",
}


def _resolve_multilingual_slug(lang_config: dict) -> str:
    """Return the WordPress plugin slug for the configured multilingual plugin."""
    plugin_name: str = lang_config.get("plugin", "polylang")
    slug = MULTILINGUAL_PLUGIN_SLUGS.get(plugin_name)
    return slug if slug is not None else plugin_name


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """
    Install and activate WordPress core translations.

    Reads ``spec["languages"]`` to determine which locales to install.
    If the key is absent or empty, this stage is a no-op.

    For multilingual setups (``additional`` non-empty), the configured
    multilingual plugin (``languages.plugin``, default ``polylang``) must already
    be installed.  The stage fails fast if it is missing.  When WPML *is*
    present a warning is appended reminding the operator to replace it with Polylang
    (WPML is banned per 62-wordpress.md).
    """
    result = StageResult(name="languages", success=True)

    lang_config = spec.get("languages", {})
    if not lang_config:
        return result

    dry_run = spec.get("dry_run", False)

    primary: str = lang_config.get("primary", "en_US")
    additional: list[str] = lang_config.get("additional", [])

    if dry_run:
        result.metadata["dry_run"] = {
            "primary": primary,
            "additional": additional,
            "multilingual_plugin": _resolve_multilingual_slug(lang_config) if additional else None,
        }
        logger.info("[dry-run] languages: would install %s and activate primary=%s", additional, primary)
        return result

    try:
        if not wp:
            raise RuntimeError("WordPressClient required for languages stage")

        # Build set of installed plugin slugs (single WP-CLI call)
        raw_plugin_list = wp.plugin_list()
        plugin_list: list[dict] = raw_plugin_list if isinstance(raw_plugin_list, list) else []
        installed_slugs = {p["name"] for p in plugin_list}

        # Resolve which multilingual plugin is required from spec
        required_slug = _resolve_multilingual_slug(lang_config)

        # Fail fast when additional locales require the multilingual plugin but it is absent
        if additional and required_slug not in installed_slugs:
            result.success = False
            result.errors.append(
                f"languages.additional is set but {required_slug} is not installed"
            )
            return result

        # Install each additional locale
        for locale in additional:
            wp.language_install(locale)

        # Activate primary locale (en_US is WordPress default; skip the WP-CLI call)
        if primary != "en_US":
            wp.language_activate(primary)

        # Warn operator that WPML is banned and should be replaced
        if WPML_SLUG in installed_slugs:
            result.warnings.append(
                "WPML (sitepress-multilingual-cms) is installed but is banned per 62-wordpress.md."
                " Switch to Polylang: deactivate WPML, install polylang, update languages.plugin to 'polylang'."
            )

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
