"""
Fabrik WordPress Planner

Orchestrates build directory creation and artifact generation:
- plan.json (execution metadata)
- blueprint.resolved.yaml (full merged spec)
- manifests/ (plugins, pages, menus, checks)
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from fabrik.wordpress.resolved_spec import ResolvedSpec

BUILD_ROOT = Path(__file__).parent.parent.parent.parent / "build" / "sites"

# Maps each stage name to the top-level spec keys that affect it
STAGE_KEYS: dict[str, list[str]] = {
    "dns": ["site", "deployment"],
    "settings": ["site", "brand", "languages"],
    "theme": ["brand", "theme"],
    "plugins": ["plugins", "preset"],
    "pages": ["pages", "brand", "languages"],
    "menus": ["navigation", "pages"],
    "forms": ["contact", "forms"],
    "seo": ["seo", "site", "pages"],
    "analytics": ["seo", "site", "site_name", "dry_run"],
}


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

    def compute_stage_input_hash(self, stage_name: str, spec_data: dict[str, Any]) -> str:
        """
        Compute hash of spec inputs relevant to a stage.

        Args:
            stage_name: Name of the stage (e.g., "dns", "plugins")
            spec_data: Full spec dict

        Returns:
            SHA-256 hex digest of the relevant spec subset
        """
        relevant_keys = STAGE_KEYS.get(stage_name, [])
        subset = {k: spec_data.get(k) for k in relevant_keys if k in spec_data}
        canonical_json = json.dumps(subset, sort_keys=True)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def compute_stage_plan(
        self, resolved_spec: ResolvedSpec, existing_plan: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Compute per-stage plan with input hashes and skip flags.

        Args:
            resolved_spec: Current resolved spec
            existing_plan: Previously saved plan.json (if any)

        Returns:
            List of stage dicts with structure:
            {
                "name": str,
                "input_hash": str,
                "last_success_hash": str | None,
                "last_run_at": str | None,
                "skip_if_unchanged": bool
            }
        """
        # Build dict of existing stage entries keyed by name
        existing_stages = {
            s["name"]: s for s in existing_plan.get("stages", []) if isinstance(s, dict)
        }

        # Compute new stage plan
        spec_dict = resolved_spec.data
        stage_names = list(STAGE_KEYS.keys())
        stage_plan = []

        for stage_name in stage_names:
            input_hash = self.compute_stage_input_hash(stage_name, spec_dict)
            existing_entry = existing_stages.get(stage_name, {})
            last_success_hash = existing_entry.get("last_success_hash")
            last_run_at = existing_entry.get("last_run_at")

            # Skip if input unchanged since last success
            skip_if_unchanged = input_hash == last_success_hash if last_success_hash else False

            stage_plan.append(
                {
                    "name": stage_name,
                    "input_hash": input_hash,
                    "last_success_hash": last_success_hash,
                    "last_run_at": last_run_at,
                    "skip_if_unchanged": skip_if_unchanged,
                }
            )

        return stage_plan

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
        needs_rewrite = not is_unchanged

        # Compute per-stage plan with input hashes
        stage_plan = self.compute_stage_plan(resolved, existing_plan)

        if is_unchanged:
            # Check for migration/backfill needs
            existing_stages = existing_plan.get("stages", [])
            expected_stage_names = set(STAGE_KEYS.keys())
            existing_stage_names = {s.get("name") for s in existing_stages if isinstance(s, dict)}

            if expected_stage_names != existing_stage_names:
                needs_rewrite = True
            else:
                for s in existing_stages:
                    if (
                        not isinstance(s, dict)
                        or "input_hash" not in s
                        or "skip_if_unchanged" not in s
                    ):
                        needs_rewrite = True
                        break

            if needs_rewrite:
                plan = existing_plan.copy()
                plan["stages"] = stage_plan
            else:
                plan = existing_plan
        else:
            # Build plan dict
            plan = {
                "site_id": self.site_id,
                "spec_hash": resolved.spec_hash,
                "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "container_name": existing_plan.get("container_name"),
                "stages": stage_plan,
            }

        if needs_rewrite:
            # Write plan.json atomically
            with tempfile.NamedTemporaryFile(
                mode="w", dir=self.build_dir, suffix=".tmp", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(json.dumps(plan, indent=2, sort_keys=True) + "\n")
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_name = tmp.name

            os.replace(tmp_name, self.plan_path)

        # Write blueprint.resolved.yaml
        with self.blueprint_path.open("w", encoding="utf-8") as f:
            yaml.dump(resolved.data, f, allow_unicode=True, sort_keys=True)

        # Generate manifests
        from fabrik.wordpress.manifests import generate_manifests

        generate_manifests(resolved, self.build_dir)

        return self.build_dir
