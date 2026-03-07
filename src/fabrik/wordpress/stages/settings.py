"""WordPress settings configuration stage."""

from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.settings import SettingsApplicator
from fabrik.wordpress.stages import StageResult, time_stage


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """Apply WordPress settings and cleanup defaults."""
    result = StageResult(name="settings", success=True)

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
                raise RuntimeError("WordPressClient required for settings stage")
            applicator = SettingsApplicator(site_name, wp)
            applicator.cleanup_defaults()
            applicator.apply_settings(spec)

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
