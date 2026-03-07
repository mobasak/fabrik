"""
WordPress Site Deployer - Orchestrate complete site deployment.

This is the main entry point for deploying a WordPress site from spec.
Coordinates all automation modules to deploy a fully configured site.

v2: Uses new spec system with loader, validator, page generator.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient, get_wordpress_client
from fabrik.drivers.wordpress_api import WordPressAPIClient, WPCredentials
from fabrik.wordpress.pages import CreatedPage
from fabrik.wordpress.planner import BUILD_ROOT
from fabrik.wordpress.spec_loader import load_spec
from fabrik.wordpress.spec_validator import SpecValidator, ValidationError
from fabrik.wordpress.stages import (
    analytics,
    dns,
    forms,
    menus,
    pages,
    plugins,
    seo,
    settings,
    theme,
)


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
    ):
        """
        Initialize site deployer.

        Args:
            site_id: Site identifier (domain, e.g., ocoron.com)
            dry_run: If True, print actions without executing
            skip_content: If True, skip AI content generation
        """
        self.site_id = site_id
        self.dry_run = dry_run
        self.skip_content = skip_content

        # Load and merge spec (defaults → preset → site)
        self.log(f"Deploying {site_id}")
        self.spec = load_spec(site_id)
        self.spec_path = f"specs/sites/{site_id}.yaml"  # For logging

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

        try:
            # Inject dry_run into spec for stage runners
            self.spec["dry_run"] = self.dry_run
            self.spec["site_name"] = self.site_name

            # Stage registry - ordered execution
            stages = (dns, settings, theme, plugins, pages, menus, forms, seo, analytics)

            # Initialize local clients once for reuse, preserving lazy behavior in dry-run mode
            wp_client = None if self.dry_run else self.wp
            api_client = None if self.dry_run else self.api

            # Execute each stage
            for stage in stages:
                self.log(f"Step: {stage.__name__.split('.')[-1]}")
                stage_result = stage.apply(self.spec, wp_client, api_client, build_dir)

                if hasattr(stage_result, "warnings") and stage_result.warnings:
                    for w in stage_result.warnings:
                        self.log(w, "warning")

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

            # Step 17: Final touches
            self._step_finalize()

            self.result.success = len(self.result.steps_failed) == 0

        except Exception as e:
            self.log(f"Deployment failed: {e}", "error")
            self.result.success = False

        # Summary
        self._print_summary()

        return self.result

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
