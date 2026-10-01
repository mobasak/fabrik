"""The hub's version registry, read by code.

`.windsurf/rules/versions.yaml` is the machine-owned version source for the rules corpus (D-062):
`rules_currency_watch.py` refreshes it and `rules_render_versions.py` injects it into the packs.
This module lets the scaffold and the template renderer read the same values, so an emitted base
image follows the registry instead of a literal (D-472, D-476).
"""

# AFTER-EDIT: none

from __future__ import annotations

from pathlib import Path

import yaml

from fabrik.config import PROJECT_ROOT

# The code's own tree, not the CWD-following FABRIK_ROOT: the registry is data the code ships with,
# read beside the templates TemplateRenderer finds the same way (D-476). A module attribute read at
# call time, so a test can monkeypatch it and the patch reaches every importer of load_versions.
VERSIONS_FILE: Path = PROJECT_ROOT / ".windsurf" / "rules" / "versions.yaml"

# The keys the emitters render. A missing or empty one fails loudly by name: Jinja's default
# Undefined would otherwise render `FROM node:--slim` and the image would build from nonsense.
REQUIRED_KEYS: tuple[str, ...] = ("node_lts", "debian_codename", "node_engines_floor")


class VersionRegistryError(ValueError):
    """The registry is missing, unreadable, malformed, or lacks a required key."""


def load_versions(path: Path | None = None) -> dict[str, str]:
    """Return the registry's `versions` map, every value a non-empty string.

    Raises VersionRegistryError naming the file when it is missing, unparseable or its `versions`
    is not a mapping, and naming the key when a required key is absent, null or blank.
    """
    source = path if path is not None else VERSIONS_FILE
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise VersionRegistryError(f"version registry not found: {source}") from exc
    except (OSError, yaml.YAMLError) as exc:
        raise VersionRegistryError(f"version registry unreadable: {source}: {exc}") from exc
    versions = raw.get("versions") if isinstance(raw, dict) else None
    if not isinstance(versions, dict):
        raise VersionRegistryError(f"version registry has no `versions` mapping: {source}")
    out = {str(k): str(v).strip() for k, v in versions.items() if v is not None and str(v).strip()}
    for key in REQUIRED_KEYS:
        if not out.get(key):
            raise VersionRegistryError(f"version registry {source} lacks a value for `{key}`")
    return out
