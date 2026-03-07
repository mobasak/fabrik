"""
Menus Manifest Generator

Generates menus.json from resolved spec navigation configuration.
"""

from __future__ import annotations

import json
from pathlib import Path

from fabrik.wordpress.resolved_spec import ResolvedSpec


def generate(resolved_spec: ResolvedSpec, build_dir: Path) -> Path:
    """
    Generate menus.json manifest.

    Args:
        resolved_spec: Resolved site specification
        build_dir: Build directory

    Returns:
        Path to written manifest

    Output format:
        {
            "primary": [
                {"label": "Home", "url": "/"},
                {"label": "About", "url": "/about"}
            ],
            "footer": [...]
        }
    """
    # Get navigation config (try both keys for compatibility)
    navigation = resolved_spec.data.get("navigation")
    if navigation is None:
        navigation = resolved_spec.data.get("menus", {})

    # Ensure serializable (already a dict from spec_loader)
    if navigation is None:
        navigation = {}

    # Write manifest
    manifest_path = build_dir / "manifests" / "menus.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(navigation, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return manifest_path
