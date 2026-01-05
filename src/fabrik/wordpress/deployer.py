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
from fabrik.wordpress.analytics import AnalyticsInjector
from fabrik.wordpress.domain_setup import DomainSetup
from fabrik.wordpress.forms import FormCreator
from fabrik.wordpress.menus import MenuCreator
from fabrik.wordpress.page_generator import generate_pages
from fabrik.wordpress.pages import CreatedPage, PageCreator
from fabrik.wordpress.seo import SEOApplicator
from fabrik.wordpress.settings import SettingsApplicator
from fabrik.wordpress.spec_loader import load_spec
from fabrik.wordpress.spec_validator import SpecValidator, ValidationError
from fabrik.wordpress.theme import ThemeCustomizer


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

        try:
            # Step 1: Domain & DNS Setup
            self._step_dns()

            # Step 3: Settings & Cleanup
            self._step_settings()

            # Step 4-5: Theme
            self._step_theme()

            # Step 6: Plugins (handled by preset loader, skipped here)
            self.result.steps_completed.append("plugins")

            # Step 7-8: Pages
            self._step_pages()

            # Step 9: Navigation
            self._step_menus()

            # Step 11: Forms
            self._step_forms()

            # Step 12: SEO
            self._step_seo()

            # Step 14: Analytics
            self._step_analytics()

            # Step 17: Final touches
            self._step_finalize()

            self.result.success = len(self.result.steps_failed) == 0

        except Exception as e:
            self.log(f"Deployment failed: {e}", "error")
            self.result.success = False

        # Summary
        self._print_summary()

        return self.result

    def _step_dns(self):
        """Configure DNS for the domain (Step 1)."""
        step = "dns"
        self.log(f"Step: {step}")

        try:
            # Get VPS IP from spec or use default
            deployment = self.spec.get("deployment", {})
            vps_ip = deployment.get("vps_ip", "172.93.160.197")
            proxied = deployment.get("cloudflare_proxy", True)

            if self.dry_run:
                self.log(f"  Would configure DNS: {self.domain} → {vps_ip}")
                self.log(f"  Cloudflare proxy: {proxied}")
            else:
                setup = DomainSetup(self.domain, vps_ip=vps_ip, proxied=proxied, dry_run=False)
                dns_result = setup.configure_dns()
                setup.close()

                if dns_result.a_record_created:
                    self.log(f"  A record: {self.domain} → {vps_ip}")
                else:
                    self.log("  A record already exists")

                if dns_result.dns_resolving:
                    self.log(f"  DNS resolving: {dns_result.resolved_ips}")

                if dns_result.https_working:
                    self.log(f"  HTTPS: working (status {dns_result.https_status_code})")

                for warning in dns_result.warnings:
                    self.result.warnings.append(warning)

                if not dns_result.success:
                    raise Exception("; ".join(dns_result.errors))

            self.result.steps_completed.append(step)
            self.log("  DNS configured", "success")

        except Exception as e:
            self.log(f"  DNS setup failed: {e}", "error")
            self.result.steps_failed.append(step)

    def _step_settings(self):
        """Apply WordPress settings and cleanup defaults."""
        step = "settings"
        self.log(f"Step: {step}")

        try:
            if self.dry_run:
                self.log("  Would cleanup defaults and apply settings")
            else:
                applicator = SettingsApplicator(self.site_name, self.wp)
                applicator.cleanup_defaults()
                applicator.apply_settings(self.spec)

            self.result.steps_completed.append(step)
            self.log("  Settings applied", "success")

        except Exception as e:
            self.log(f"  Settings failed: {e}", "error")
            self.result.steps_failed.append(step)

    def _step_theme(self):
        """Install and customize theme."""
        step = "theme"
        self.log(f"Step: {step}")

        try:
            theme_config = self.spec.get("theme", {})
            theme_name = theme_config.get("name", "generatepress")

            if self.dry_run:
                self.log(f"  Would install and customize {theme_name}")
            else:
                customizer = ThemeCustomizer(self.site_name, self.wp)

                # Install theme
                try:
                    customizer.install_theme(activate=True)
                except Exception:
                    pass  # May already be installed

                # Apply customizations
                customizer.apply_from_spec(self.spec)

            self.result.steps_completed.append(step)
            self.log("  Theme configured", "success")

        except Exception as e:
            self.log(f"  Theme failed: {e}", "error")
            self.result.steps_failed.append(step)

    def _step_pages(self):
        """Create site pages from generated page specs."""
        step = "pages"
        self.log(f"Step: {step}")

        try:
            # Generate pages from spec (templates + entities)
            primary_locale = self.spec.get("languages", {}).get("primary", "en_US")
            page_specs = generate_pages(self.spec, locale=primary_locale)

            if not page_specs:
                self.log("  No pages to create", "warning")
                return

            if self.dry_run:
                self.log(f"  Would create {len(page_specs)} pages")
                for page in page_specs[:5]:  # Show first 5
                    slug = page.get("slug", "(home)")
                    title = page.get("title", "")
                    self.log(f"    - /{slug}: {title}")
            elif self.api:
                creator = PageCreator(
                    self.site_name,
                    wp_client=self.wp,
                    api_client=self.api,
                )

                # Build hierarchical page structure for PageCreator
                # First pass: group children by parent_slug (entity pages)
                pages_by_parent = {}
                top_level_specs = []

                for page_spec in page_specs:
                    parent_slug = page_spec.get("parent_slug")

                    if parent_slug:
                        # Entity child page - group by parent
                        if parent_slug not in pages_by_parent:
                            pages_by_parent[parent_slug] = []

                        pages_by_parent[parent_slug].append(
                            {
                                "slug": page_spec.get("slug", ""),
                                "title": page_spec.get("title", ""),
                                "content": page_spec.get("content", ""),
                                "status": page_spec.get("status", "publish"),
                                "template": page_spec.get("template", ""),
                            }
                        )
                    else:
                        # Top-level page
                        top_level_specs.append(page_spec)

                # Second pass: build top-level pages with children
                top_level_pages = []
                for page_spec in top_level_specs:
                    slug = page_spec.get("slug", "")
                    page_dict = {
                        "slug": slug,
                        "title": page_spec.get("title", ""),
                        "content": page_spec.get("content", ""),
                        "status": page_spec.get("status", "publish"),
                        "template": page_spec.get("template", ""),
                    }

                    # Attach children if any
                    if slug in pages_by_parent:
                        page_dict["children"] = pages_by_parent[slug]

                    top_level_pages.append(page_dict)

                # Create all pages (idempotent, path-based keys)
                self.result.pages_created = creator.create_all(top_level_pages)

                # Set homepage if defined
                homepage = self.result.pages_created.get("")
                if homepage:
                    creator.set_homepage(homepage.id)
                    self.log(f"  Homepage set to page ID {homepage.id}")

                # Set blog page if defined
                blog_page = self.result.pages_created.get(
                    "insights"
                ) or self.result.pages_created.get("blog")
                if blog_page:
                    creator.set_blog_page(blog_page.id)
            else:
                self.log("  REST API not available, skipping page creation", "warning")
                return

            self.result.steps_completed.append(step)
            self.log(f"  Created {len(self.result.pages_created)} pages", "success")

        except Exception as e:
            self.log(f"  Pages failed: {e}", "error")
            self.result.steps_failed.append(step)

    def _step_menus(self):
        """Create navigation menus."""
        step = "menus"
        self.log(f"Step: {step}")

        try:
            navigation = self.spec.get("navigation") or self.spec.get("menus", {})

            if not navigation:
                self.log("  No navigation defined in spec", "warning")
                return

            if self.dry_run:
                self.log(f"  Would create menus: {list(navigation.keys())}")
            else:
                creator = MenuCreator(self.site_name, self.wp)
                menus = creator.create_all(navigation)
                self.log(f"  Created {len(menus)} menus")

            self.result.steps_completed.append(step)
            self.log("  Menus configured", "success")

        except Exception as e:
            self.log(f"  Menus failed: {e}", "error")
            self.result.steps_failed.append(step)

    def _step_forms(self):
        """Create contact forms."""
        step = "forms"
        self.log(f"Step: {step}")

        try:
            contact = self.spec.get("contact", {})

            if not contact:
                self.log("  No contact info defined", "warning")
                return

            if self.dry_run:
                self.log("  Would create contact form")
            else:
                creator = FormCreator(self.site_name, self.wp)

                # Check if form plugin is available
                plugin = creator.detect_form_plugin()
                if plugin:
                    form = creator.create_contact_form(
                        title="Contact Form",
                        recipient=contact.get("email", ""),
                        fields=contact.get("form_fields", ["name", "email", "message"]),
                    )
                    self.log(f"  Created form: {form.shortcode}")
                else:
                    self.log("  No form plugin installed (WPForms or CF7)", "warning")
                    return

            self.result.steps_completed.append(step)
            self.log("  Forms configured", "success")

        except Exception as e:
            self.log(f"  Forms failed: {e}", "error")
            self.result.steps_failed.append(step)

    def _step_seo(self):
        """Apply SEO settings."""
        step = "seo"
        self.log(f"Step: {step}")

        try:
            seo = self.spec.get("seo", {})

            if not seo:
                self.log("  No SEO settings defined", "warning")
                return

            if self.dry_run:
                self.log("  Would apply SEO settings")
            else:
                applicator = SEOApplicator(self.site_name, self.wp)

                # Check if SEO plugin available
                plugin = applicator.detect_seo_plugin()
                if plugin:
                    applicator.apply_site_seo(seo)
                    self.log(f"  Applied SEO via {plugin}")
                else:
                    self.log("  No SEO plugin installed (Yoast or RankMath)", "warning")

            self.result.steps_completed.append(step)
            self.log("  SEO configured", "success")

        except Exception as e:
            self.log(f"  SEO failed: {e}", "error")
            self.result.steps_failed.append(step)

    def _step_analytics(self):
        """Inject analytics codes."""
        step = "analytics"
        self.log(f"Step: {step}")

        try:
            seo = self.spec.get("seo", {})
            analytics = seo.get("analytics", {})

            ga4 = analytics.get("ga4") or analytics.get("google_analytics") or seo.get("ga4_id")
            gtm = analytics.get("gtm") or analytics.get("google_tag_manager") or seo.get("gtm_id")

            if not ga4 and not gtm:
                self.log("  No analytics IDs defined", "warning")
                return

            if self.dry_run:
                self.log(f"  Would inject GA4={ga4}, GTM={gtm}")
            else:
                injector = AnalyticsInjector(self.site_name, self.wp)
                injector.apply_from_spec(seo)

            self.result.steps_completed.append(step)
            self.log("  Analytics configured", "success")

        except Exception as e:
            self.log(f"  Analytics failed: {e}", "error")
            self.result.steps_failed.append(step)

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
