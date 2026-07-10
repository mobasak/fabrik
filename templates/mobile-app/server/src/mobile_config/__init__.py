"""mobile-config — remote app-config / force-update / kill-switch / feature toggles.

    from mobile_config import AppConfig, evaluate

    # GET /app-config?platform=ios&version=1.2.0
    def app_config(request):
        config = AppConfig.from_dict(load_project_config(request))   # jsonb row
        result = evaluate(
            config,
            platform=request.query["platform"],
            app_version=request.query["version"],
        )
        return result.to_dict()      # {"update_required": ..., "kill_switch": ..., "features": {...}}
"""

from __future__ import annotations

from .config import (
    AppConfig,
    AppConfigResponse,
    evaluate,
    is_feature_enabled,
)

__all__ = [
    "AppConfig",
    "AppConfigResponse",
    "evaluate",
    "is_feature_enabled",
]
