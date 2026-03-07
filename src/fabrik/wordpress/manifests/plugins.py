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
                "zip_path": "path/to/plugin.zip" | null
            }
        ]
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

        manifest.append(
            {
                "slug": slug,
                "version": version,
                "source": source,
                "zip_path": zip_path,
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
