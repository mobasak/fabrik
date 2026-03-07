"""Theme installation and customization stage."""

from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.stages import StageResult, time_stage
from fabrik.wordpress.theme import ThemeCustomizer


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
            # Dry-run: just log intent
            pass
        else:
            if not wp:
                raise RuntimeError("WordPressClient required for theme stage")
            customizer = ThemeCustomizer(site_name, wp)

            # Install theme
            try:
                customizer.install_theme(activate=True)
            except Exception:
                pass  # May already be installed

            # Apply customizations
            customizer.apply_from_spec(spec)

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
