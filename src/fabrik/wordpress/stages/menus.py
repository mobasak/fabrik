"""Navigation menu creation stage."""

import logging
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.menus import MenuCreator
from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)


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
            result.skipped = True
            result.metadata["skipped_reason"] = "no navigation defined in spec"
        elif dry_run:
            result.metadata["dry_run"] = {"menus": list(navigation.keys()) if isinstance(navigation, dict) else []}
        else:
            if not wp:
                raise RuntimeError("WordPressClient required for menus stage")
            creator = MenuCreator(site_name, wp)
            created = creator.create_all(navigation)
            result.metadata["menus_created"] = {
                name: {"id": m.id, "items": len(m.items)} for name, m in created.items()
            }
            logger.info("Menus created: %s", list(created.keys()))

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
