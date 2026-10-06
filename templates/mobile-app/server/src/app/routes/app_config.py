"""Remote app-config endpoint — force-update / kill-switch / feature toggles.

Resolution logic is owned entirely by the vendored `mobile_config` module (never
hand-rolled — see its docstring for the `1.10.0 > 1.9.0` string-compare footgun it
avoids). This route's only job is: read the operator-configured gate from env
(minimal default — no DB, see `defaults.yaml::shape.needs_database`), read the
client's platform + version from the query string, call `evaluate`, and add the
app-store URLs (which `mobile_config` doesn't model — it's config/gate-only).

Minimal default reads a single `APP_MIN_VERSION` / `APP_LATEST_VERSION` pair
applied to both platforms. If a project needs per-platform gating, replace the
`_load_config` mapping below with `APP_MIN_VERSION_IOS` / `APP_MIN_VERSION_ANDROID`
etc. — `mobile_config.AppConfig.min_version` already supports a per-platform map.
"""

from __future__ import annotations

import json
import os

from fastapi import APIRouter, Query

from mobile_config import AppConfig, evaluate

router = APIRouter()


def _version_map(value: str) -> dict[str, str]:
    """Both platforms share one env-configured version, omitted (not `""`) when unset.

    An empty string stored as the map value would still round-trip through
    `evaluate()` as a present-but-unparsable gate, surfacing a misleading
    `"min_version": ""` in the response instead of `null`. Omitting the key
    entirely makes `mobile_config._lookup` return `None`, which is the correct
    "no gate configured" signal.
    """
    return {"ios": value, "android": value} if value else {}


def _load_config() -> AppConfig:
    try:
        features = json.loads(os.getenv("APP_FEATURE_FLAGS", "{}"))
    except json.JSONDecodeError:
        # A malformed operator-set env value degrades to "no flags" rather than
        # 500-ing the whole endpoint — same fail-open posture mobile_config uses
        # for a malformed min_version/latest_version.
        features = {}

    return AppConfig.from_dict(
        {
            "min_version": _version_map(os.getenv("APP_MIN_VERSION", "")),
            "latest_version": _version_map(os.getenv("APP_LATEST_VERSION", "")),
            "kill_switch": os.getenv("APP_KILL_SWITCH", "false"),
            "kill_switch_message": os.getenv("APP_KILL_SWITCH_MESSAGE") or None,
            "features": features,
            "paywall_id": os.getenv("APP_PAYWALL_ID") or None,
        }
    )


def _store_urls() -> dict[str, str]:
    return {
        "android": os.getenv("STORE_URL_ANDROID", ""),
        "ios": os.getenv("STORE_URL_IOS", ""),
    }


@router.get("/app-config")
async def get_app_config(
    platform: str = Query(..., description="'ios' or 'android'"),
    version: str = Query(..., description="client app version, e.g. '1.2.0'"),
) -> dict[str, object]:
    config = _load_config()
    result = evaluate(config, platform=platform, app_version=version)
    payload = result.to_dict()
    payload["store_urls"] = _store_urls()
    return payload
