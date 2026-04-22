"""
Fabrik WordPress Spec Loader

Loads and merges site specifications from multiple layers:
- defaults.yaml (global)
- presets/<preset>.yaml (industry-specific)
- sites/<domain>.yaml (site-specific)

Implements merge rules from schema/MERGE_RULES.md
"""

import copy
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class SpecLoader:
    """Load and merge WordPress site specifications."""

    TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates" / "wordpress"
    SPECS_DIR = Path(__file__).parent.parent.parent.parent / "specs" / "sites"

    def __init__(self, domain: str, site_path: Path | None = None):
        """
        Initialize spec loader.

        Args:
            domain: Site domain (e.g., ocoron.com)
            site_path: Optional explicit path to site spec YAML. If provided,
                       skips the default SPECS_DIR lookup.
        """
        self.domain = domain
        self.defaults_path = self.TEMPLATES_DIR / "defaults.yaml"
        self.presets_dir = self.TEMPLATES_DIR / "presets"

        if site_path is not None:
            self.site_path = site_path
        else:
            self.site_path = self.SPECS_DIR / f"{domain}.yaml"

            # Check for v2 spec
            v2_path = self.SPECS_DIR / f"{domain}.v2.yaml"
            if v2_path.exists():
                self.site_path = v2_path

    def load(self) -> dict:
        """
        Load and merge all spec layers.

        Returns:
            Merged spec dict
        """
        # Load layers
        defaults = self._load_yaml(self.defaults_path)

        # Load site to get preset
        site = self._load_yaml(self.site_path)
        preset_name = site.get("preset", "company")

        preset_path = self.presets_dir / f"{preset_name}.yaml"
        preset = self._load_yaml(preset_path)

        # Merge: defaults → preset → site
        merged = self._deep_merge(defaults, preset)
        merged = self._deep_merge(merged, site)

        # Apply secrets from environment
        merged = self._apply_secrets(merged)

        # Normalize (top-level entities → entities.*)
        merged = self._normalize(merged)

        # Auto-inject polylang for multilingual sites (before plugin rules for manifest gen)
        if merged.get("languages", {}).get("additional"):
            plugins = merged.get("plugins", {})
            base_plugins = plugins.get("base", [])
            if not any(self._normalize_plugin_name(p) == "polylang" for p in base_plugins):
                base_plugins.append("polylang")
                merged["plugins"] = merged.get("plugins", {})
                merged["plugins"]["base"] = base_plugins

        # Apply plugin layering rules (e.g., deduplication, skip list)
        plugins_final = self.apply_plugin_rules(merged)
        merged["plugins"] = merged.get("plugins", {})
        merged["plugins"]["final"] = plugins_final

        # Apply canonical sort for deterministic hashing
        merged = json.loads(json.dumps(merged, sort_keys=True))

        return merged

    def _load_yaml(self, path: Path) -> dict:
        """Load YAML file."""
        if not path.exists():
            return {}

        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """
        Deep merge two dicts with right-side precedence.

        Rules:
        - Maps: deep merge
        - Arrays: replace (no append unless marked)
        - Primitives: replace
        """
        result = copy.deepcopy(base)

        for key, value in override.items():
            if key not in result:
                # New key, just add it
                result[key] = copy.deepcopy(value)
            elif isinstance(value, dict) and isinstance(result[key], dict):
                # Both are dicts, deep merge
                result[key] = self._deep_merge(result[key], value)
            elif isinstance(value, list) and isinstance(result[key], list):
                # Both are lists, check for merge directive
                if self._should_append(override, key):
                    # Append mode
                    result[key] = result[key] + value
                else:
                    # Replace mode (default)
                    result[key] = copy.deepcopy(value)
            else:
                # Primitive or type mismatch, replace
                result[key] = copy.deepcopy(value)

        return result

    def _should_append(self, parent: dict, key: str) -> bool:
        """Check if array should be appended instead of replaced."""
        # Look for _merge directive
        merge_key = f"{key}_merge"
        if merge_key in parent:
            return parent[merge_key] == "append"

        # Special cases: plugins.add always appends
        # Check for 'base' key presence to identify a plugins section dict safely
        return bool(key == "add" and isinstance(parent, dict) and "base" in parent)

    def _apply_secrets(self, spec: dict) -> dict:
        """Replace ${VAR} references with environment variables."""

        def replace_secrets(obj: Any) -> Any:
            if isinstance(obj, str):
                # Replace ${VAR} with os.getenv('VAR')
                pattern = r"\$\{([A-Z0-9_]+)\}"
                matches = re.findall(pattern, obj)
                for var in matches:
                    value = os.getenv(var)
                    if value is None:
                        logger.warning(
                            "spec references env var ${%s} which is not set — substituting empty string",
                            var,
                        )
                        value = ""
                    obj = obj.replace(f"${{{var}}}", value)
                return obj
            elif isinstance(obj, dict):
                return {k: replace_secrets(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_secrets(item) for item in obj]
            else:
                return obj

        return replace_secrets(spec)

    def _normalize(self, spec: dict) -> dict:
        """
        Normalize spec structure.

        - Top-level entities (services, features, products) → entities.*
        - Ensure entities namespace exists
        - Preserve preset entity config (parent_page, page_template, etc.)
        """
        if "entities" not in spec:
            spec["entities"] = {}

        # Move top-level entity keys to entities namespace
        entity_keys = ["services", "features", "products", "locations"]
        for key in entity_keys:
            if key in spec and key != "entities":
                # Check if entities[key] exists and is a dict (preset config)
                if key in spec["entities"] and isinstance(spec["entities"][key], dict):
                    # Preset has config dict (enabled, parent_page, page_template, etc.)
                    # Site has data list
                    # Preserve config, add data as 'items'
                    if isinstance(spec[key], list):
                        preset_config = spec["entities"][key].copy()
                        preset_config["items"] = spec[key]
                        spec["entities"][key] = preset_config
                    else:
                        # Site also has dict, merge it
                        spec["entities"][key] = self._deep_merge(spec["entities"][key], spec[key])
                else:
                    # No preset config, just move the data
                    # Wrap list in dict with 'items' key for consistency
                    if isinstance(spec[key], list):
                        spec["entities"][key] = {"items": spec[key]}
                    else:
                        spec["entities"][key] = spec[key]

                # Remove from top level
                del spec[key]

        return spec

    def apply_plugin_rules(self, spec: dict) -> list[str]:
        """
        Apply plugin layering rules.

        Returns:
            Final list of plugins to install
        """
        plugins = []

        # Get base plugins from defaults
        base = spec.get("plugins", {}).get("base", [])
        plugins.extend(base)

        # Add plugins from preset and site
        add = spec.get("plugins", {}).get("add", [])
        plugins.extend(add)

        # Remove skipped plugins
        skip = spec.get("plugins", {}).get("skip", [])
        skip_normalized = {self._normalize_plugin_name(p) for p in skip}

        plugins = [p for p in plugins if self._normalize_plugin_name(p) not in skip_normalized]

        # Auto-inject polylang when multilingual is configured (Gap 19)
        if spec.get("languages", {}).get("additional"):
            if not any(self._normalize_plugin_name(p) == "polylang" for p in plugins):
                plugins.append("polylang")

        # Deduplicate (last occurrence wins)
        seen = {}
        for plugin in plugins:
            name = self._normalize_plugin_name(plugin)
            seen[name] = plugin

        return list(seen.values())

    def _normalize_plugin_name(self, plugin: str) -> str:
        """
        Normalize plugin name for comparison.

        Removes:
        - .zip extension
        - Version numbers (-1.2.3, -v1.2.3)
        - Hash prefixes (7aaUOmxu84su-)
        """
        name = plugin.replace(".zip", "")

        # Remove version numbers (e.g. -1.2.3 or -v1.2.3.4)
        name = re.sub(r"-v?\d+\.\d+(\.\d+)*", "", name)

        # Remove hash prefixes (min 8 chars to avoid stripping real plugin name words)
        name = re.sub(r"^[a-zA-Z0-9]{8,}-", "", name)

        return name.lower()


def load_spec(domain: str) -> dict:
    """
    Convenience function to load a site spec.

    Args:
        domain: Site domain (e.g., ocoron.com)

    Returns:
        Merged and normalized spec
    """
    loader = SpecLoader(domain)
    return loader.load()


def resolve_spec_path(site_id: str, project_path: str | None = None) -> tuple[Path, bool]:
    """
    Resolve the site spec YAML path using a three-priority strategy.

    Priority order:
        1. --project <path> → <path>/site.yaml
        2. CWD contains site.yaml AND CWD/project.yaml has type: wordpress → ./site.yaml
        3. Legacy fallback → specs/sites/<site_id>.yaml (is_legacy=True)

    Args:
        site_id: Site identifier (domain or project name)
        project_path: Optional explicit project directory path

    Returns:
        Tuple of (resolved_path, is_legacy) where is_legacy=True
        triggers a deprecation warning in the caller.

    Raises:
        FileNotFoundError: If no spec file can be resolved from any path.
    """
    # Priority 1: Explicit --project path
    if project_path is not None:
        spec_path = Path(project_path).resolve() / "site.yaml"
        if spec_path.exists():
            return spec_path, False
        raise FileNotFoundError(
            f"No site.yaml found at {spec_path}. Ensure the project folder contains a site.yaml."
        )

    # Priority 2: CWD auto-detection
    cwd = Path.cwd()
    cwd_site_yaml = cwd / "site.yaml"
    cwd_project_yaml = cwd / "project.yaml"

    if cwd_site_yaml.exists() and cwd_project_yaml.exists():
        try:
            with open(cwd_project_yaml, encoding="utf-8") as f:
                project_data = yaml.safe_load(f) or {}
            if project_data.get("type") == "wordpress":
                return cwd_site_yaml, False
        except (yaml.YAMLError, OSError) as exc:
            logger.warning("Could not read %s for CWD auto-detection: %s", cwd_project_yaml, exc)

    # Priority 3: Legacy fallback (specs/sites/<site_id>.yaml)
    specs_dir = SpecLoader.SPECS_DIR
    v2_path = specs_dir / f"{site_id}.v2.yaml"
    if v2_path.exists():
        return v2_path, True

    legacy_path = specs_dir / f"{site_id}.yaml"
    if legacy_path.exists():
        return legacy_path, True

    raise FileNotFoundError(
        "No site.yaml found. Use --project <path>, cd into a WordPress "
        "project folder, or ensure specs/sites/<site_id>.yaml exists."
    )


def load_spec_from_path(site_id: str, site_path: Path) -> dict:
    """
    Load a merged site spec from an explicit file path.

    Instantiates SpecLoader with the given site_path override, bypassing
    the default SPECS_DIR lookup.

    Args:
        site_id: Site identifier (used as domain in the merge pipeline)
        site_path: Explicit path to the site spec YAML file

    Returns:
        Fully merged and normalized spec dict
    """
    loader = SpecLoader(site_id, site_path=site_path)
    return loader.load()
