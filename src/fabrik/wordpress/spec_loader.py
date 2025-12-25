"""
Fabrik WordPress Spec Loader

Loads and merges site specifications from multiple layers:
- defaults.yaml (global)
- presets/<preset>.yaml (industry-specific)
- sites/<domain>.yaml (site-specific)

Implements merge rules from schema/MERGE_RULES.md
"""

import os
from pathlib import Path
from typing import Any, Optional
import yaml
import copy
import re


class SpecLoader:
    """Load and merge WordPress site specifications."""
    
    TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates" / "wordpress"
    SPECS_DIR = Path(__file__).parent.parent.parent.parent / "specs" / "sites"
    
    def __init__(self, domain: str):
        """
        Initialize spec loader.
        
        Args:
            domain: Site domain (e.g., ocoron.com)
        """
        self.domain = domain
        self.defaults_path = self.TEMPLATES_DIR / "defaults.yaml"
        self.presets_dir = self.TEMPLATES_DIR / "presets"
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
        
        return merged
    
    def _load_yaml(self, path: Path) -> dict:
        """Load YAML file."""
        if not path.exists():
            return {}
        
        with open(path, 'r', encoding='utf-8') as f:
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
        if key == "add" and "plugins" in str(parent):
            return True
        
        return False
    
    def _apply_secrets(self, spec: dict) -> dict:
        """Replace ${VAR} references with environment variables."""
        def replace_secrets(obj: Any) -> Any:
            if isinstance(obj, str):
                # Replace ${VAR} with os.getenv('VAR')
                pattern = r'\$\{([A-Z0-9_]+)\}'
                matches = re.findall(pattern, obj)
                for var in matches:
                    value = os.getenv(var, '')
                    obj = obj.replace(f'${{{var}}}', value)
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
        - Handle preset entity config vs site entity data
        """
        if "entities" not in spec:
            spec["entities"] = {}
        
        # Move top-level entity keys to entities namespace
        entity_keys = ["services", "features", "products", "locations"]
        for key in entity_keys:
            if key in spec and key != "entities":
                # Check if entities[key] exists and is a dict (preset config)
                if key in spec["entities"] and isinstance(spec["entities"][key], dict):
                    # Preset has config (enabled, parent_page, etc)
                    # Site has data (list of items)
                    # Keep config, add data as 'items' or replace with data
                    if isinstance(spec[key], list):
                        # Site provides list, use it as the data
                        spec["entities"][key] = spec[key]
                else:
                    # No preset config, just move the data
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
        
        plugins = [
            p for p in plugins
            if self._normalize_plugin_name(p) not in skip_normalized
        ]
        
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
        name = plugin.replace('.zip', '')
        
        # Remove version numbers
        name = re.sub(r'-v?\d+\.\d+(\.\d+)?', '', name)
        
        # Remove hash prefixes
        name = re.sub(r'^[a-zA-Z0-9]+-', '', name)
        
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
