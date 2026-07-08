"""Behavior Contract for scripts/kilo-benchmarks/tools/sanitize_kilo_config.py.

Phase B of plan-4 (pipeline-health coverage closure).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


def test_sanitize_removes_known_stale_keys(tmp_path):
    """B1: given a config with stale keys, sanitize removes them + backs up."""
    from sanitize_kilo_config import sanitize

    cfg = tmp_path / "opencode.json"
    cfg.write_text(
        json.dumps(
            {
                "model": "claude-sonnet-5",
                "subagent_model": "should-be-removed",
                "subagent_variant_overrides": {"foo": "bar"},
            }
        ),
        encoding="utf-8",
    )
    removed = sanitize(cfg)
    assert set(removed) == {"subagent_model", "subagent_variant_overrides"}
    remaining = json.loads(cfg.read_text(encoding="utf-8"))
    assert "subagent_model" not in remaining
    assert "subagent_variant_overrides" not in remaining
    assert remaining["model"] == "claude-sonnet-5"
    backup = cfg.with_suffix(".json.bak")
    assert backup.exists(), "backup not created"


def test_sanitize_idempotent_on_clean_config(tmp_path):
    """B3: running twice on an already-clean config = no change."""
    from sanitize_kilo_config import sanitize

    cfg = tmp_path / "opencode.json"
    cfg.write_text(json.dumps({"model": "claude-sonnet-5"}), encoding="utf-8")
    original = cfg.read_text(encoding="utf-8")
    assert sanitize(cfg) == []
    assert sanitize(cfg) == []
    assert cfg.read_text(encoding="utf-8") == original


def test_sanitize_missing_config_returns_empty(tmp_path):
    """Config file absent → no-op, no crash."""
    from sanitize_kilo_config import sanitize

    cfg = tmp_path / "does-not-exist.json"
    assert sanitize(cfg) == []
    assert not cfg.exists()
