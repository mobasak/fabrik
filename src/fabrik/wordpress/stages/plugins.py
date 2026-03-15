"""Plugins stage: idempotent plugin install and activation."""

import json
import logging
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """Apply plugin installs and activations idempotently."""
    result = StageResult(name="plugins", success=True)

    try:
        dry_run = spec.get("dry_run", False)

        if dry_run:
            return result

        if wp is None:
            result.success = False
            result.errors.append("WordPressClient required for plugins stage")
            return result

        # Load manifest (empty list if missing)
        manifest_path = build_dir / "manifests" / "plugins.json"
        if manifest_path.exists():
            manifest: list[dict] = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = []

        # Build installed-plugin index: slug → status
        plugin_list_result = wp.plugin_list()
        raw_list: list[dict] = plugin_list_result if isinstance(plugin_list_result, list) else []
        installed: dict[str, str] = {entry["name"]: entry["status"] for entry in raw_list}

        for entry in manifest:
            slug = entry["slug"]

            # Fail-fast on missing zip_path for zip-sourced plugins
            if entry["source"] == "zip" and not entry.get("zip_path"):
                result.success = False
                result.errors.append(f"Plugin {slug}: source=zip but zip_path is missing")
                break

            install_target = entry["zip_path"] if entry["source"] == "zip" else slug

            # Use the installed-plugin slug for the status lookup.  For ZIP
            # plugins this is the normalized directory name WordPress creates
            # (stored as ``installed_slug`` in the manifest), NOT the raw zip
            # path stored in ``slug``.  Falling back to ``slug`` keeps the
            # stage backwards-compatible with manifests that pre-date this
            # field.
            lookup_key = entry.get("installed_slug") or slug
            status = installed.get(lookup_key)

            if status == "active":
                # Already active — nothing to do
                continue
            elif status == "inactive":
                # Activate using the real installed slug, not the zip path
                wp.plugin_activate(lookup_key)
            else:
                # Not installed — install and activate
                wp.plugin_install(install_target, activate=True)

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
