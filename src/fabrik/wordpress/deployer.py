"""
WordPress Site Deployer - Orchestrate complete site deployment.

This is the main entry point for deploying a WordPress site from spec.
Coordinates all automation modules to deploy a fully configured site.

v2: Uses new spec system with loader, validator, page generator.
"""

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient, get_wordpress_client
from fabrik.drivers.wordpress_api import WordPressAPIClient, WPCredentials
from fabrik.wordpress.pages import CreatedPage
from fabrik.wordpress.planner import BUILD_ROOT
from fabrik.wordpress.spec_loader import load_spec_from_path, resolve_spec_path
from fabrik.wordpress.spec_validator import SpecValidator, ValidationError
from fabrik.wordpress.stages import (
    StageResult,
    analytics,
    dns,
    forms,
    languages,
    menus,
    pages,
    plugins,
    seo,
    settings,
    theme,
)

logger = logging.getLogger(__name__)


@dataclass
class DeploymentResult:
    """Result of a site deployment."""

    success: bool
    site_name: str
    domain: str
    steps_completed: list[str] = field(default_factory=list)
    steps_failed: list[str] = field(default_factory=list)
    pages_created: dict[str, CreatedPage] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class SiteDeployer:
    """
    Orchestrate complete WordPress site deployment from spec.

    Usage:
        deployer = SiteDeployer("ocoron.com")
        result = deployer.deploy()
    """

    SPECS_DIR = Path(__file__).parent.parent.parent.parent / "specs" / "sites"

    def __init__(
        self,
        site_id: str,
        dry_run: bool = False,
        skip_content: bool = False,
        force_stage: str | None = None,
        project_path: str | None = None,
    ):
        """
        Initialize site deployer.

        Args:
            site_id: Site identifier (domain, e.g., ocoron.com)
            dry_run: If True, print actions without executing
            skip_content: If True, skip AI content generation
            force_stage: Stage name to force re-run (bypasses skip_if_unchanged)
            project_path: Optional path to WordPress project folder containing site.yaml
        """
        self.site_id = site_id
        self.dry_run = dry_run
        self.skip_content = skip_content
        self.force_stage = force_stage

        # Resolve spec path using three-priority strategy
        self.log(f"Deploying {site_id}")
        resolved_path, is_legacy = resolve_spec_path(site_id, project_path)
        if is_legacy:
            logger.warning(
                "Loading spec from legacy path %s — migrate to project folder",
                resolved_path,
            )
        self.spec = load_spec_from_path(site_id, resolved_path)
        self.spec_path = str(resolved_path)  # For logging

        # Validate spec
        validator = SpecValidator(self.spec)
        errors, warnings = validator.validate()

        if errors:
            raise ValidationError(
                "Spec validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        for warning in warnings:
            self.log(warning, "warning")

        # Extract key config
        self.domain = self.spec.get("site", {}).get("domain", site_id)
        self.site_name = self.spec.get("site", {}).get("name") or site_id.replace(".", "-")
        self.container_name = f"{self.site_name}-wordpress"

        # Initialize clients (lazy)
        self._wp: WordPressClient | None = None
        self._api: WordPressAPIClient | None = None

        # Track results
        self.result = DeploymentResult(
            success=False,
            site_name=self.site_name,
            domain=self.domain,
        )

    @property
    def wp(self) -> WordPressClient:
        """Get WP-CLI client."""
        if self._wp is None:
            self._wp = get_wordpress_client(self.site_name)
        return self._wp

    @property
    def api(self) -> WordPressAPIClient | None:
        """Get REST API client if credentials available."""
        if self._api is None:
            api_url = f"https://{self.domain}"
            api_user = os.getenv("WP_ADMIN_USER", "admin")
            api_password = os.getenv("WP_ADMIN_PASSWORD", "")

            if api_password:
                creds = WPCredentials(url=api_url, username=api_user, password=api_password)
                self._api = WordPressAPIClient(creds)

        return self._api

    def log(self, message: str, level: str = "info"):
        """Log a message."""
        prefix = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "")
        print(f"{prefix} {message}")

        if level == "warning":
            self.result.warnings.append(message)
        elif level == "error":
            self.result.errors.append(message)

    def deploy(self) -> DeploymentResult:
        """
        Execute full site deployment.

        Returns:
            DeploymentResult with status and details
        """
        self.log(f"Deploying {self.domain} from {self.spec_path}")

        if self.dry_run:
            self.log("DRY RUN MODE - no changes will be made", "warning")

        # Build-dir hard gate (non dry-run only)
        build_dir = BUILD_ROOT / self.site_id
        if not self.dry_run and not build_dir.exists():
            raise RuntimeError(
                f"Build directory missing for {self.site_id}. Run 'fabrik wp plan' first."
            )

        # Load plan.json for stage skip checks (non dry-run only)
        stage_entries: dict[str, dict] = {}
        plan_path = build_dir / "plan.json"
        if not self.dry_run and plan_path.exists():
            try:
                plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
                stage_entries = {s["name"]: s for s in plan_data.get("stages", [])}
            except (json.JSONDecodeError, OSError):
                # Corrupt plan file, continue without skip logic
                pass

        # Track stage results for apply-report.json
        stage_results_for_report: list[dict] = []

        try:
            # Inject dry_run into spec for stage runners
            self.spec["dry_run"] = self.dry_run
            self.spec["site_name"] = self.site_name

            # Stage registry - ordered execution
            stages = (dns, settings, theme, plugins, languages, pages, menus, forms, seo, analytics)

            # Initialize local clients once for reuse, preserving lazy behavior in dry-run mode
            wp_client = None if self.dry_run else self.wp
            api_client = None if self.dry_run else self.api

            # Execute each stage
            for stage in stages:
                stage_name = stage.__name__.split(".")[-1]
                self.log(f"Step: {stage_name}")

                # Check if stage should be skipped
                stage_entry = stage_entries.get(stage_name, {})
                should_skip = (
                    stage_entry.get("skip_if_unchanged", False) and self.force_stage != stage_name
                )

                if should_skip:
                    stage_result = StageResult(name=stage_name, success=True, skipped=True)
                    self.log(f"  {stage_name.capitalize()} skipped (unchanged)", "info")
                else:
                    # Run stage
                    stage_result = stage.apply(self.spec, wp_client, api_client, build_dir)

                    # Update plan.json atomically after successful non-skipped stage
                    if stage_result.success and not stage_result.skipped and not self.dry_run:
                        self._update_plan_after_stage(build_dir, stage_name, stage_entry)

                # Log warnings
                if hasattr(stage_result, "warnings") and stage_result.warnings:
                    for w in stage_result.warnings:
                        self.log(w, "warning")

                # Track result
                if stage_result.success:
                    if not getattr(stage_result, "skipped", False):
                        self.result.steps_completed.append(stage_result.name)
                        self.log(f"  {stage_result.name.capitalize()} completed", "success")
                else:
                    self.result.steps_failed.append(stage_result.name)
                    self.result.errors.extend(stage_result.errors)
                    print(f"❌   {stage_result.name.capitalize()} failed")

                # Special handling for pages stage - extract pages_created
                if stage_result.name == "pages" and "pages_created" in stage_result.metadata:
                    self.result.pages_created = stage_result.metadata["pages_created"]

                # Add to report
                stage_results_for_report.append(
                    {
                        "name": stage_result.name,
                        "success": stage_result.success,
                        "skipped": stage_result.skipped,
                        "duration_ms": stage_result.duration_ms,
                        "errors": stage_result.errors,
                    }
                )

            # Step 17: Final touches
            self._step_finalize()

            self.result.success = len(self.result.steps_failed) == 0

        except Exception as e:
            self.log(f"Deployment failed: {e}", "error")
            self.result.success = False

        # Write apply-report.json (non dry-run only)
        if not self.dry_run:
            self._write_apply_report(build_dir, stage_results_for_report)

        # Summary
        self._print_summary()

        return self.result

    def _update_plan_after_stage(self, build_dir: Path, stage_name: str, stage_entry: dict) -> None:
        """
        Update plan.json atomically after a successful stage run.

        Args:
            build_dir: Build directory path
            stage_name: Name of the completed stage
            stage_entry: Current stage entry dict from plan.json
        """
        plan_path = build_dir / "plan.json"

        # Re-read current plan (avoid clobbering concurrent changes)
        try:
            current_plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return  # Can't update, skip

        # Find and update the stage entry
        stages = current_plan.get("stages", [])
        for stage in stages:
            if stage.get("name") == stage_name:
                # Mark as successfully run
                stage["last_success_hash"] = stage.get("input_hash")
                stage["last_run_at"] = datetime.now(UTC).isoformat()
                stage["skip_if_unchanged"] = True
                break

        # Write atomically
        with tempfile.NamedTemporaryFile(
            mode="w", dir=build_dir, suffix=".tmp", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(json.dumps(current_plan, indent=2, sort_keys=True) + "\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name

        os.replace(tmp_name, plan_path)

    def _write_apply_report(self, build_dir: Path, stage_results: list[dict]) -> None:
        """
        Write apply-report.json to the reports/ subdirectory.

        Args:
            build_dir: Build directory path
            stage_results: List of stage result dicts
        """
        reports_dir = build_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        report = {
            "site_id": self.site_id,
            "ran_at": datetime.now(UTC).isoformat(),
            "stages": stage_results,
            "overall_success": self.result.success,
        }

        report_path = reports_dir / "apply-report.json"
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def _step_finalize(self):
        """Final touches - flush caches, set homepage, etc."""
        step = "finalize"
        self.log(f"Step: {step}")

        try:
            if self.dry_run:
                self.log("  Would flush caches and finalize")
            else:
                # Flush rewrite rules
                self.wp.rewrite_flush()

                # Flush object cache
                try:
                    self.wp.cache_flush()
                except Exception:
                    pass  # Cache may not be configured

            self.result.steps_completed.append(step)
            self.log("  Site finalized", "success")

        except Exception as e:
            self.log(f"  Finalize failed: {e}", "error")
            self.result.steps_failed.append(step)

    def _print_summary(self):
        """Print deployment summary."""
        print("\n" + "=" * 50)
        print(f"DEPLOYMENT {'SUCCESS' if self.result.success else 'FAILED'}")
        print("=" * 50)
        print(f"Site: {self.domain}")
        print(f"Steps completed: {len(self.result.steps_completed)}")
        print(f"Steps failed: {len(self.result.steps_failed)}")

        if self.result.pages_created:
            print(f"Pages created: {len(self.result.pages_created)}")

        if self.result.warnings:
            print(f"\nWarnings ({len(self.result.warnings)}):")
            for w in self.result.warnings:
                print(f"  - {w}")

        if self.result.errors:
            print(f"\nErrors ({len(self.result.errors)}):")
            for e in self.result.errors:
                print(f"  - {e}")

        print("=" * 50)


def deploy_site(site_id: str, dry_run: bool = False) -> DeploymentResult:
    """
    Convenience function to deploy a site.

    Args:
        site_id: Site identifier (domain name)
        dry_run: If True, don't execute changes

    Returns:
        DeploymentResult
    """
    deployer = SiteDeployer(site_id, dry_run=dry_run)
    return deployer.deploy()
