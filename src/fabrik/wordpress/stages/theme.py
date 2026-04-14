"""Theme installation and customization stage."""

import logging
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.stages import StageResult, time_stage
from fabrik.wordpress.theme import ThemeCustomizer

logger = logging.getLogger(__name__)


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """Install and customize theme."""
    result = StageResult(name="theme", success=True)

    try:
        dry_run = spec.get("dry_run", False)
        site_name = (
            spec.get("site_name")
            or spec.get("site", {}).get("name")
            or spec.get("site", {}).get("domain", "").replace(".", "-")
        )

        if dry_run:
            brand = spec.get("brand", {})
            theme_name = brand.get("theme") or spec.get("theme", {}).get("name", "unknown")
            result.metadata["dry_run"] = {"theme": theme_name}
        else:
            if not wp:
                raise RuntimeError("WordPressClient required for theme stage")
            customizer = ThemeCustomizer(site_name, wp)

            # Install theme
            try:
                customizer.install_theme(activate=True)
            except Exception as exc:
                result.warnings.append(f"Theme install raised: {exc} — may already be installed")
                logger.warning("Theme install warning: %s", exc)

            # Apply customizations
            applied = customizer.apply_from_spec(spec)
            result.metadata["applied"] = applied
            logger.info("Theme customizations applied: %s", list(applied.keys()))

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
