"""
Fabrik WordPress Manifest Generators

Pure functions that generate deployment manifests from ResolvedSpec.

Each generator:
- Takes (resolved_spec, build_dir)
- Writes JSON to build_dir/manifests/<name>.json
- Returns the written path

No network I/O, no subprocess calls.
"""

from __future__ import annotations

from pathlib import Path

from fabrik.wordpress.resolved_spec import ResolvedSpec


def generate_manifests(resolved_spec: ResolvedSpec, build_dir: Path) -> None:
    """
    Generate all deployment manifests.

    Args:
        resolved_spec: Resolved site specification
        build_dir: Build directory (e.g., build/sites/ocoron.com)

    Creates:
        - manifests/plugins.json
        - manifests/pages.json
        - manifests/menus.json
        - manifests/checks.json
    """
    from fabrik.wordpress.manifests import checks, menus, pages, plugins

    plugins.generate(resolved_spec, build_dir)
    pages.generate(resolved_spec, build_dir)
    menus.generate(resolved_spec, build_dir)
    checks.generate(resolved_spec, build_dir)
