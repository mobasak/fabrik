"""Plugins stage (no-op - plugins handled by preset loader)."""

from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.stages import StageResult, time_stage


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """
    Plugins stage (no-op).

    Plugins are managed by the preset loader at spec-load time.
    This stage exists for consistency in the pipeline.
    """
    result = StageResult(name="plugins", success=True)
    return result
