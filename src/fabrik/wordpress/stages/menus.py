"""Navigation menu creation stage."""

from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.menus import MenuCreator
from fabrik.wordpress.stages import StageResult, time_stage


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """Create navigation menus."""
    result = StageResult(name="menus", success=True)

    try:
        dry_run = spec.get("dry_run", False)
        site_name = (
            spec.get("site_name")
            or spec.get("site", {}).get("name")
            or spec.get("site", {}).get("domain", "").replace(".", "-")
        )
        navigation = spec.get("navigation") or spec.get("menus", {})

        if not navigation:
            # No navigation defined: not an error
            pass
        elif dry_run:
            # Dry-run: just log intent
            pass
        else:
            if not wp:
                raise RuntimeError("WordPressClient required for menus stage")
            creator = MenuCreator(site_name, wp)
            creator.create_all(navigation)

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
