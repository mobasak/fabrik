"""
Fabrik WordPress Planner

Orchestrates build directory creation and artifact generation:
- plan.json (execution metadata)
- blueprint.resolved.yaml (full merged spec)
- manifests/ (plugins, pages, menus, checks)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from fabrik.wordpress.resolved_spec import ResolvedSpec

BUILD_ROOT = Path(__file__).parent.parent.parent.parent / "build" / "sites"


class Planner:
    """
    WordPress site build planner.

    Creates build artifacts needed for deployment:
    - plan.json: execution metadata (hash, timestamps, container info)
    - blueprint.resolved.yaml: full merged spec
    - manifests/: deployment manifests (plugins, pages, menus, checks)
    """

    def __init__(self, site_id: str):
        """
        Initialize planner.

        Args:
            site_id: Site domain (e.g., ocoron.com)
        """
        self.site_id = site_id
        self.build_dir = BUILD_ROOT / site_id
        self.plan_path = self.build_dir / "plan.json"
        self.blueprint_path = self.build_dir / "blueprint.resolved.yaml"

    def plan(self) -> Path:
        """
        Generate all build artifacts.

        Returns:
            Path to build directory

        Creates:
            - build/sites/<site_id>/plan.json
            - build/sites/<site_id>/blueprint.resolved.yaml
            - build/sites/<site_id>/manifests/*.json
        """
        # Load resolved spec
        resolved = ResolvedSpec.from_site(self.site_id)

        # Create manifests directory
        manifests_dir = self.build_dir / "manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)

        # Load existing plan if present
        existing_plan: dict[str, Any] = {}
        if self.plan_path.exists():
            try:
                existing_plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                # Corrupt or missing file, start fresh
                existing_plan = {}

        is_unchanged = existing_plan.get("spec_hash") == resolved.spec_hash

        if is_unchanged:
            plan = existing_plan
        else:
            # Build plan dict
            plan = {
                "site_id": self.site_id,
                "spec_hash": resolved.spec_hash,
                "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "container_name": existing_plan.get("container_name"),
                "stages": existing_plan.get("stages", []),
            }

            # Write plan.json
            self.plan_path.write_text(
                json.dumps(plan, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        # Write blueprint.resolved.yaml
        with self.blueprint_path.open("w", encoding="utf-8") as f:
            yaml.dump(resolved.data, f, allow_unicode=True, sort_keys=True)

        # Generate manifests
        from fabrik.wordpress.manifests import generate_manifests

        generate_manifests(resolved, self.build_dir)

        return self.build_dir
