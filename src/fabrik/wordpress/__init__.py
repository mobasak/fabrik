"""WordPress automation module."""

from fabrik.wordpress.preset_loader import (
    PresetConfig,
    PresetLoader,
    apply_preset,
    list_presets,
)

__all__ = [
    "PresetConfig",
    "PresetLoader",
    "apply_preset",
    "list_presets",
]
