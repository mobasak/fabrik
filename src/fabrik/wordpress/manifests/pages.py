"""
Pages Manifest Generator

Generates pages.json from resolved spec using page_generator module.
"""

from __future__ import annotations

import json
from pathlib import Path

from fabrik.wordpress.page_generator import generate_pages
from fabrik.wordpress.resolved_spec import ResolvedSpec


def generate(resolved_spec: ResolvedSpec, build_dir: Path) -> Path:
    """
    Generate pages.json manifest.

    Args:
        resolved_spec: Resolved site specification
        build_dir: Build directory

    Returns:
        Path to written manifest

    Output format:
        [
            {
                "title": "Contact Us",
                "slug": "contact",
                "content": "...",
                "parent": null | "parent-slug",
                "sections": [...],
                "seo": {...}
            }
        ]
    """
    # Get primary locale
    locale = resolved_spec.data.get("languages", {}).get("primary", "en_US")

    # Generate pages
    pages = generate_pages(resolved_spec.data, locale=locale)

    # Write manifest
    manifest_path = build_dir / "manifests" / "pages.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(pages, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return manifest_path
