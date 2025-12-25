"""WordPress automation module."""

from fabrik.wordpress.preset_loader import (
    PresetConfig,
    PresetLoader,
    apply_preset,
    list_presets,
)
from fabrik.wordpress.settings import (
    EditorCredentials,
    SettingsApplicator,
    apply_settings,
)
from fabrik.wordpress.theme import (
    BrandColors,
    BrandFonts,
    ThemeCustomizer,
    apply_theme,
)
from fabrik.wordpress.media import (
    MediaUploader,
    UploadedMedia,
    upload_brand_assets,
)
from fabrik.wordpress.pages import (
    CreatedPage,
    PageCreator,
    create_pages,
)
from fabrik.wordpress.menus import (
    CreatedMenu,
    MenuItem,
    MenuCreator,
    create_menus,
)
from fabrik.wordpress.seo import (
    SEOApplicator,
    SEOSettings,
    apply_seo,
)
from fabrik.wordpress.forms import (
    CreatedForm,
    FormCreator,
    create_contact_form,
)
from fabrik.wordpress.analytics import (
    AnalyticsConfig,
    AnalyticsInjector,
    inject_analytics,
)
from fabrik.wordpress.deployer import (
    DeploymentResult,
    SiteDeployer,
    deploy_site,
)
from fabrik.wordpress.spec_loader import (
    SpecLoader,
    load_spec,
)
from fabrik.wordpress.spec_validator import (
    SpecValidator,
    ValidationError,
    validate_spec,
)
from fabrik.wordpress.domain_setup import (
    DomainSetup,
    DomainSetupResult,
    setup_domain,
)

__all__ = [
    # Preset loader
    "PresetConfig",
    "PresetLoader",
    "apply_preset",
    "list_presets",
    # Settings
    "EditorCredentials",
    "SettingsApplicator",
    "apply_settings",
    # Theme
    "BrandColors",
    "BrandFonts",
    "ThemeCustomizer",
    "apply_theme",
    # Media
    "MediaUploader",
    "UploadedMedia",
    "upload_brand_assets",
    # Pages
    "CreatedPage",
    "PageCreator",
    "create_pages",
    # Menus
    "CreatedMenu",
    "MenuItem",
    "MenuCreator",
    "create_menus",
    # SEO
    "SEOApplicator",
    "SEOSettings",
    "apply_seo",
    # Forms
    "CreatedForm",
    "FormCreator",
    "create_contact_form",
    # Analytics
    "AnalyticsConfig",
    "AnalyticsInjector",
    "inject_analytics",
    # Deployer
    "DeploymentResult",
    "SiteDeployer",
    "deploy_site",
    # Spec loader & validator
    "SpecLoader",
    "load_spec",
    "SpecValidator",
    "ValidationError",
    "validate_spec",
    # Domain setup
    "DomainSetup",
    "DomainSetupResult",
    "setup_domain",
]
