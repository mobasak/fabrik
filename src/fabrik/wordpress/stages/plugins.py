<<<<<<< Updated upstream
"""Plugins stage: idempotent plugin install and activation."""

import json
import logging
=======
"""WordPress plugins installation stage."""

import json
import logging
import re
>>>>>>> Stashed changes
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)

<<<<<<< Updated upstream
=======

def _lookup_slug(entry: dict) -> str:
    """
    Extract the canonical WP-CLI slug from a manifest entry.

    Handles legacy manifests where ZIP-source entries may still have the ZIP
    filename or path in ``slug`` instead of the canonical plugin slug.

    Args:
        entry: Plugin manifest entry dict

    Returns:
        Canonical plugin slug for WP-CLI lookup
    """
    slug = entry["slug"]
    is_legacy_zip = entry.get("source") == "zip" and (
        slug.endswith(".zip") or "/" in slug or "\\" in slug
    )
    if is_legacy_zip:
        # Legacy format: slug is still a ZIP filename/path
        name = slug.replace("\\", "/").rsplit("/", 1)[-1]
        if name.endswith(".zip"):
            name = name[:-4]
        name = re.sub(r"-v?\d+\.\d+(\.\d+)?$", "", name)
        return name.lower()
    return slug

>>>>>>> Stashed changes

@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
<<<<<<< Updated upstream
    """Apply plugin installs and activations idempotently."""
=======
    """
    Install and activate plugins declared in the plugins manifest.

    Reads build_dir/manifests/plugins.json and idempotently installs/activates
    each plugin based on its current status in WordPress.
    """
>>>>>>> Stashed changes
    result = StageResult(name="plugins", success=True)

    try:
        dry_run = spec.get("dry_run", False)

        if dry_run:
<<<<<<< Updated upstream
            manifest_path = build_dir / "manifests" / "plugins.json"
            if manifest_path.exists():
                manifest_preview: list[dict] = json.loads(manifest_path.read_text(encoding="utf-8"))
            else:
                manifest_preview = []
            result.metadata["dry_run"] = {
                "would_install": [e["slug"] for e in manifest_preview],
                "total": len(manifest_preview),
            }
=======
>>>>>>> Stashed changes
            return result

        if wp is None:
            result.success = False
            result.errors.append("WordPressClient required for plugins stage")
            return result

<<<<<<< Updated upstream
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

        # --- Wordfence whitelist for VPS IP to prevent 429 in Verify stage ---
        # Wordfence stores its config in its own DB table (not wp_options),
        # accessible only via its PHP class wfConfig.  Use `wp eval` to call
        # the native API so the value is written to the correct table.
        if "wordfence" in installed and installed["wordfence"] == "active":
            try:
                vps_ip = spec.get("deployment", {}).get("vps_ip", "172.93.160.197")
                php_code = (
                    "if(class_exists('wfConfig')){"
                    f"$ip='{vps_ip}';"
                    "$cur=wfConfig::get('whitelistedIPs','');"
                    "if(strpos($cur,$ip)===false){"
                    '$new=$cur?$cur."\\n".$ip:$ip;'
                    "wfConfig::set('whitelistedIPs',$new);"
                    "echo 'added';"
                    "}else{echo 'exists';}"
                    "}else{echo 'no_wfConfig';}"
                )
                wf_result = wp.run(f"eval {json.dumps(php_code)}")
                if "added" in wf_result:
                    logger.info("VPS IP %s added to Wordfence whitelist via wfConfig API", vps_ip)
                elif "exists" in wf_result:
                    logger.info("VPS IP %s already in Wordfence whitelist", vps_ip)
                else:
                    logger.warning("Wordfence whitelist result: %s", wf_result)
            except Exception as e:
                logger.warning("Failed to whitelist VPS IP in Wordfence: %s", e)

        counts = {"installed": 0, "activated": 0, "skipped": 0, "failed": 0}

        for entry in manifest:
            slug = entry["slug"]
=======
        # Load manifest (empty list if file does not exist)
        manifest_path = build_dir / "manifests" / "plugins.json"
        if manifest_path.exists():
            plugins_manifest: list[dict] = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            plugins_manifest = []

        # Build installed plugins map: slug -> status
        plugin_list_result = wp.plugin_list()
        if isinstance(plugin_list_result, str):
            plugin_list_result = json.loads(plugin_list_result) if plugin_list_result else []
        installed: dict[str, str] = {entry["name"]: entry["status"] for entry in plugin_list_result}

        for entry in plugins_manifest:
            slug = _lookup_slug(entry)
>>>>>>> Stashed changes

            # Fail-fast on missing zip_path for zip-sourced plugins
            if entry["source"] == "zip" and not entry.get("zip_path"):
                result.success = False
                result.errors.append(f"Plugin {slug}: source=zip but zip_path is missing")
                break

            install_target = entry["zip_path"] if entry["source"] == "zip" else slug
<<<<<<< Updated upstream

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
                counts["skipped"] += 1
                continue
            elif status == "inactive":
                # Activate using the real installed slug, not the zip path
                wp.plugin_activate(lookup_key)
                counts["activated"] += 1
                logger.info("Plugin activated: %s", lookup_key)
            else:
                # Not installed — install and activate
                try:
                    wp.plugin_install(install_target, activate=True)
                    counts["installed"] += 1
                    logger.info("Plugin installed: %s", install_target)
                except Exception as install_exc:
                    counts["failed"] += 1
                    msg = f"Plugin {slug}: install failed — {install_exc}"
                    result.errors.append(msg)
                    logger.error(msg)

        result.metadata["counts"] = counts
        result.metadata["total"] = len(manifest)
        if counts["failed"] > 0:
            result.success = False
        logger.info(
            "Plugins: %d installed, %d activated, %d skipped, %d failed (total=%d)",
            counts["installed"],
            counts["activated"],
            counts["skipped"],
            counts["failed"],
            len(manifest),
        )
=======
            status = installed.get(slug)

            if status == "active":
                # Already active — nothing to do
                logger.debug("Plugin %s is already active, skipping", slug)
            elif status == "inactive":
                # Installed but inactive — activate only
                logger.info("Activating plugin %s", slug)
                wp.plugin_activate(slug)
            else:
                # Not installed — install and activate
                logger.info("Installing plugin %s from %s", slug, install_target)
                wp.plugin_install(install_target, activate=True)
>>>>>>> Stashed changes

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
