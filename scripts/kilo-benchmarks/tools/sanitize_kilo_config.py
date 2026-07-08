"""Remove known-stale Kilo CLI opencode.json keys that newer Kilo (v7.0.33+) rejects.

Root cause (diagnosed 2026-07-08 in plan-4): `kilo models --verbose` exits 0
with stderr `Error: Configuration is invalid ... Unrecognized keys:
"subagent_model", "subagent_variant_overrides"`. `kilo_agents_db.fetch_kilo_models`
then sees empty stdout and returns [] — the dual-routing verification chain
has been silently dead since the Kilo CLI upgrade.

Idempotent: unknown keys already absent → zero file change. Backs up before
mutating. Safe to run on cron.
"""

# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_sanitize_kilo_config.py

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

STALE_KEYS = ("subagent_model", "subagent_variant_overrides")
CONFIG = Path.home() / ".config" / "kilo" / "opencode.json"


def sanitize(config_path: Path = CONFIG) -> list[str]:
    """Remove stale keys from opencode.json; return the list of keys removed.

    Empty list = no change written (idempotent no-op).
    """
    if not config_path.exists():
        return []
    original = config_path.read_text(encoding="utf-8")
    data = json.loads(original)
    removed = [k for k in STALE_KEYS if k in data]
    if not removed:
        return []
    for k in removed:
        del data[k]
    backup = config_path.with_suffix(".json.bak")
    shutil.copy2(config_path, backup)
    config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return removed


def main() -> int:
    removed = sanitize()
    if not removed:
        print("already clean — no stale keys present")
    else:
        print(f"removed {removed}; backup at {CONFIG.with_suffix('.json.bak')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
