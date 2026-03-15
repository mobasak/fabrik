"""
Plugin Manifest Generator

Generates plugins.json from resolved spec with version enrichment.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fabrik.wordpress.resolved_spec import ResolvedSpec
from fabrik.wordpress.spec_loader import SpecLoader


def _normalize_plugin_name(plugin: str) -> str:
    """
    Normalize plugin name for comparison.

    Removes:
    - .zip extension
    - Version numbers (-1.2.3, -v1.2.3)
    - Hash prefixes (7aaUOmxu84su-)

    Args:
        plugin: Raw plugin slug

    Returns:
        Normalized name
    """
    name = plugin.replace(".zip", "")

    # Remove version numbers
    name = re.sub(r"-v?\d+\.\d+(\.\d+)?", "", name)

    # Remove hash prefixes
    name = re.sub(r"^[a-zA-Z0-9]+-", "", name)

    return name.lower()


def _zip_installed_slug(zip_path: str) -> str:
    """
    Derive the WordPress-installed plugin slug from a ZIP path.

    WordPress installs a ZIP plugin into a directory whose name is the
    base name of the ZIP without the extension, version suffix, and any
    leading hash prefix.  This matches what ``wp plugin list`` reports in
    the ``name`` column, which is what the plugins stage uses for its
    ``installed`` lookup.

    Examples::

        "premium-plugin.zip"              -> "premium-plugin"
        "path/to/custom-plugin.zip"       -> "custom-plugin"
        "7aaUOmxu84su-my-plugin-1.2.3.zip" -> "my-plugin"

    Args:
        zip_path: Raw ZIP path or filename from the spec.

    Returns:
        Normalized installed plugin slug (lower-case, no version/hash).
    """
    # Use only the basename so that directory paths are ignored
    basename = Path(zip_path).stem  # strips .zip extension

    # Remove version numbers (e.g. -1.2.3 or -v1.2.3)
    slug = re.sub(r"-v?\d+\.\d+(\.\d+)*", "", basename)

    # Remove leading hash prefixes (e.g. "7aaUOmxu84su-").
    # Require at least 8 characters to avoid stripping legitimate first words
    # from hyphenated slugs like "premium-plugin".
    slug = re.sub(r"^[a-zA-Z0-9]{8,}-", "", slug)

    return slug.lower()


def generate(resolved_spec: ResolvedSpec, build_dir: Path) -> Path:
    """
    Generate plugins.json manifest.

    Args:
        resolved_spec: Resolved site specification
        build_dir: Build directory

    Returns:
        Path to written manifest

    Output format:
        [
            {
                "slug": "contact-form-7",
                "version": "5.8.4" | null,
                "source": "wordpress.org" | "zip",
                "zip_path": "path/to/plugin.zip" | null,
                "installed_slug": "contact-form-7"
            }
        ]

    For ZIP plugins ``installed_slug`` is the normalized directory name that
    WordPress creates when the ZIP is installed (no path, no ``.zip``, no
    version suffix, no hash prefix).  For ``wordpress.org`` plugins it equals
    ``slug``.
    """
    # Apply plugin rules to get final list
    loader = SpecLoader(resolved_spec.site_id)
    final_plugins = loader.apply_plugin_rules(resolved_spec.data)

    # Load version lookup
    plugins_db_path = SpecLoader.TEMPLATES_DIR / "plugins_latest.json"
    version_lookup: dict[str, dict[str, Any]] = {}

    if plugins_db_path.exists():
        try:
            plugins_db = json.loads(plugins_db_path.read_text(encoding="utf-8"))
            for entry in plugins_db.get("plugins", []):
                name = entry.get("name", "")
                normalized = _normalize_plugin_name(name)
                version_lookup[normalized] = {
                    "version": entry.get("version"),
                    "url": entry.get("url"),
                }
        except (json.JSONDecodeError, OSError):
            # Lookup file missing or corrupt, proceed without enrichment
            pass

    # Build manifest
    manifest = []
    for slug in final_plugins:
        normalized = _normalize_plugin_name(slug)

        # Determine source type
        is_zip = slug.endswith(".zip")
        source = "zip" if is_zip else "wordpress.org"
        zip_path = slug if is_zip else None

        # Lookup version
        version = None
        if not is_zip and normalized in version_lookup:
            version = version_lookup[normalized].get("version")

        # Derive the slug that WordPress uses when the plugin is listed
        # via `wp plugin list`.  For ZIP plugins the installed directory
        # name is the base filename stripped of version/hash, which may
        # differ from `slug` (the raw zip path).
        installed_slug = _zip_installed_slug(slug) if is_zip else slug

        manifest.append(
            {
                "slug": slug,
                "version": version,
                "source": source,
                "zip_path": zip_path,
                "installed_slug": installed_slug,
            }
        )

    # Write manifest
    manifest_path = build_dir / "manifests" / "plugins.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    return manifest_path
