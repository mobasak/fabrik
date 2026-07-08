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


def test_sanitize_backup_mode_is_0600_from_creation(tmp_path):
    """PF4 regression: the .bak MUST be 0600 from the moment it's created
    (os.open with mode + umask 0o077), so a SIGKILL between create and any
    later chmod can't leave the operator's Kilo apiKey world-readable.
    """
    import os as _os

    from sanitize_kilo_config import sanitize

    cfg = tmp_path / "opencode.json"
    cfg.write_text(
        json.dumps(
            {
                "apiKey": "sk-real-looking-secret-do-not-leak",
                "subagent_model": "trigger-sanitize",
            }
        ),
        encoding="utf-8",
    )
    sanitize(cfg)
    backup = cfg.with_suffix(".json.bak")
    assert backup.exists()
    mode = _os.stat(backup).st_mode & 0o777
    assert mode == 0o600, (
        f"backup mode is {mode:o} (want 0o600) — a SIGKILL/OOM between create "
        "and chmod would have left the apiKey world-readable"
    )
    # And the backup does contain the original secret (guards against "we
    # protected the mode but wrote empty content" false green).
    assert "sk-real-looking-secret-do-not-leak" in backup.read_text(encoding="utf-8")


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
