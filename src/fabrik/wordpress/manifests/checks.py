"""
Checks Manifest Generator

Generates checks.json from resolved spec health check configuration.
"""

from __future__ import annotations

import json
from pathlib import Path

from fabrik.wordpress.resolved_spec import ResolvedSpec


def generate(resolved_spec: ResolvedSpec, build_dir: Path) -> Path:
    """
    Generate checks.json manifest.

    Args:
        resolved_spec: Resolved site specification
        build_dir: Build directory

    Returns:
        Path to written manifest

    Output format:
        {
            "require_ssl": true,
            "require_sitemap": true,
            "urls": [
                {"url": "/", "expected_status": 200},
                {"url": "/contact", "expected_status": 200}
            ]
        }
    """
    # Get checks config
    checks_config = resolved_spec.data.get("checks", {})

    # Extract URL list (default from schema: ["/", "/contact"])
    urls = checks_config.get("urls", ["/", "/contact"])

    # Build URL check list
    url_checks = [{"url": url, "expected_status": 200} for url in urls]

    # Extract SSL and sitemap flags
    require_ssl = checks_config.get("require_ssl", True)
    require_sitemap = checks_config.get("require_sitemap", True)

    # Build manifest
    manifest = {
        "require_ssl": require_ssl,
        "require_sitemap": require_sitemap,
        "urls": url_checks,
    }

    # Write manifest
    manifest_path = build_dir / "manifests" / "checks.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    return manifest_path
