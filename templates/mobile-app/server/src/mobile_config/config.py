"""Remote mobile app-config — force-update / kill-switch / feature toggles / paywall.

A `GET /app-config` backend serves per-project config to the app on launch. This
module is the framework-agnostic core: load your stored config into :class:`AppConfig`
(``AppConfig.from_dict`` reads a jsonb row), call :func:`evaluate` with the client's
platform + version, and return :meth:`AppConfigResponse.to_dict` as JSON.

Version comparison uses ``packaging.version`` so ``1.10.0 > 1.9.0`` (a plain string
compare gets this wrong — the classic force-update bug). A **malformed client version
never hard-blocks** (we don't brick a user over a bad version string) — it only nudges
an update.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from packaging.version import InvalidVersion, Version


def _try_parse(value: object) -> Version | None:
    """Parse a version string, or ``None`` if empty/non-string/malformed (never raises).

    Guards ``isinstance str`` so a non-string stored value (e.g. a numeric ``1.2`` from
    a bad config row) returns ``None`` instead of raising ``TypeError`` and 500-ing the
    whole endpoint for every client on that platform.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        return Version(value)
    except InvalidVersion:
        return None


def _as_bool(value: object) -> bool:
    """Coerce a stored value to bool WITHOUT Python's ``bool("false") is True`` trap.

    Critical for ``kill_switch``: a JSON round-trip through a form/env/loose admin API
    can store the *string* ``"false"``, and ``bool("false")`` is ``True`` — which would
    black out the whole app. Only genuinely-true values engage; anything else is off.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    if isinstance(value, (int, float)):
        # NaN != 0 is True, which would engage the kill-switch on a garbage numeric
        # (json.loads accepts a bare NaN) — reject it. Fail toward NOT blacking out.
        if isinstance(value, float) and math.isnan(value):
            return False
        return value != 0
    return False


def _as_str_map(value: object) -> dict[str, str]:
    """A ``{str: str}`` map from stored data, or ``{}`` if it isn't a mapping."""
    if not isinstance(value, Mapping):
        return {}
    return {str(k): str(v) for k, v in value.items()}


def _as_bool_map(value: object) -> dict[str, bool]:
    """A ``{str: bool}`` map from stored data (bool-coerced), or ``{}``."""
    if not isinstance(value, Mapping):
        return {}
    return {str(k): _as_bool(v) for k, v in value.items()}


def _lookup(mapping: Mapping[str, str], platform: str) -> str | None:
    """Case-insensitive platform lookup, so ``"iOS"`` config matches an ``"ios"`` client.

    If a map somehow holds two case-variants of one platform (``"ios"`` and ``"iOS"`` —
    an operator error), the first in insertion order wins (deterministic).
    """
    target = platform.lower()
    for key, value in mapping.items():
        if isinstance(key, str) and key.lower() == target:
            return value
    return None


@dataclass(frozen=True)
class AppConfig:
    """The operator-controlled config for one project (per-platform gates + toggles)."""

    min_version: Mapping[str, str] = field(default_factory=dict)  # platform -> min supported
    latest_version: Mapping[str, str] = field(default_factory=dict)  # platform -> latest
    kill_switch: bool = False
    kill_switch_message: str | None = None
    features: Mapping[str, bool] = field(default_factory=dict)  # feature toggles
    paywall_id: str | None = None  # remote paywall pointer

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AppConfig:
        """Build from a stored config row (jsonb / JSON), tolerating missing/bad keys.

        Every field is defensively typed: a non-mapping ``features``/``min_version`` or
        a non-bool ``kill_switch`` from a malformed row degrades to a safe default
        rather than crashing the endpoint or silently corrupting config.
        """
        message = data.get("kill_switch_message")
        paywall = data.get("paywall_id")
        return cls(
            min_version=_as_str_map(data.get("min_version")),
            latest_version=_as_str_map(data.get("latest_version")),
            kill_switch=_as_bool(data.get("kill_switch")),
            kill_switch_message=message if isinstance(message, str) else None,
            features=_as_bool_map(data.get("features")),
            paywall_id=paywall if isinstance(paywall, str) else None,
        )

    def invalid_versions(self) -> list[str]:
        """Configured version strings that fail to parse — a config-lint for operators.

        :func:`evaluate` fails *open* on an unparsable ``min_version`` (a typo silently
        disables that platform's force-update gate — we can't tell a broken gate from an
        absent one inside a pure resolver). Call this from a health check / admin save
        path / test to catch the typo BEFORE it ships a dead gate.
        """
        bad: list[str] = []
        for mapping in (self.min_version, self.latest_version):
            for value in mapping.values():
                # Anything set that evaluate() can't parse — including a non-str value
                # (which evaluate silently treats as "no gate") — is a dead gate.
                if value in (None, "") or _try_parse(value) is not None:
                    continue
                bad.append(str(value))
        return bad


@dataclass(frozen=True)
class AppConfigResponse:
    """What the client receives — drives its update gate, kill-switch, and flags."""

    update_required: bool  # client is below min supported — hard-block / force update
    update_available: bool  # a newer version exists — soft nudge
    kill_switch: bool  # maintenance mode — show the message, halt
    kill_switch_message: str | None
    features: dict[str, bool]
    paywall_id: str | None
    min_version: str | None
    latest_version: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "update_required": self.update_required,
            "update_available": self.update_available,
            "kill_switch": self.kill_switch,
            "kill_switch_message": self.kill_switch_message,
            "features": dict(self.features),
            "paywall_id": self.paywall_id,
            "min_version": self.min_version,
            "latest_version": self.latest_version,
        }


def evaluate(config: AppConfig, *, platform: str, app_version: str) -> AppConfigResponse:
    """Resolve ``config`` for a client on ``platform`` running ``app_version``.

    ``update_required`` when the client is strictly below the platform's min version;
    ``update_available`` when strictly below the latest. Platform lookup is
    case-insensitive. An unknown platform (no gate configured) never blocks.

    Fail directions: a malformed **client** ``app_version`` never sets
    ``update_required`` (don't lock a user out over a bad string) but does set
    ``update_available``. A malformed **operator** ``min_version``/``latest_version``
    also fails open (the gate is treated as unset) — a pure resolver can't distinguish
    a typo from an absent gate, so lint the config with
    :meth:`AppConfig.invalid_versions` before serving it.
    """
    min_raw = _lookup(config.min_version, platform)
    latest_raw = _lookup(config.latest_version, platform)
    current = _try_parse(app_version)
    min_v = _try_parse(min_raw)
    latest_v = _try_parse(latest_raw)

    if current is None:
        update_required = False
        update_available = latest_v is not None
    else:
        update_required = min_v is not None and current < min_v
        update_available = latest_v is not None and current < latest_v

    return AppConfigResponse(
        update_required=update_required,
        update_available=update_available,
        kill_switch=config.kill_switch,
        kill_switch_message=config.kill_switch_message,
        features=dict(config.features),
        paywall_id=config.paywall_id,
        min_version=min_raw,
        latest_version=latest_raw,
    )


def is_feature_enabled(config: AppConfig, key: str) -> bool:
    """Whether feature ``key`` is toggled on (absent ⇒ off — fail-closed)."""
    return bool(config.features.get(key, False))


__all__ = [
    "AppConfig",
    "AppConfigResponse",
    "evaluate",
    "is_feature_enabled",
]
