# AFTER-EDIT: none
"""Utility helpers for Fabrik scripts."""

from __future__ import annotations

import re


def sanitize_slug(value: str) -> str:
    """Sanitizes a string into a URL-safe slug.

    Args:
        value: The raw input string to sanitize.

    Returns:
        The sanitized slug string containing only lowercase alphanumerics and hyphens.

    Examples:
        >>> sanitize_slug('  Hello  World!_123  ')
        'hello-world-123'
    """
    value = value.strip().lower()
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^a-z0-9-]", "", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")
