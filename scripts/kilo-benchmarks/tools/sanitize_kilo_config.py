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
import os
import sys
from pathlib import Path

STALE_KEYS = ("subagent_model", "subagent_variant_overrides")
CONFIG = Path.home() / ".config" / "kilo" / "opencode.json"


def sanitize(config_path: Path = CONFIG) -> list[str]:
    """Remove stale keys from opencode.json; return the list of keys removed.

    Empty list = no change written (idempotent no-op).

    Fail-soft on malformed JSON (F5): a corrupted opencode.json (e.g. from a
    crashed prior write) returns [] with a stderr warning instead of raising
    into the cron caller. The daily_refresh path can still proceed with the
    report-on-error branch in `kilo_agents_db.fetch_kilo_models`.

    Backup file (F8): `opencode.json` contains the operator's Kilo `apiKey`.
    The `.bak` is written with mode 0600 (owner-only) so we don't create a
    second world-readable copy of the secret. Prior code used shutil.copy2
    which preserved the source's 0644.
    """
    if not config_path.exists():
        return []
    try:
        original = config_path.read_text(encoding="utf-8")
        data = json.loads(original)
    # UnicodeDecodeError is NOT a subclass of JSONDecodeError or OSError —
    # it must be caught explicitly for a non-UTF-8 config to fail soft.
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        sys.stderr.write(
            f"[sanitize_kilo_config] WARN: cannot parse {config_path}: {exc}. "
            "Skipping — no change written.\n"
        )
        return []
    if not isinstance(data, dict):
        sys.stderr.write(
            f"[sanitize_kilo_config] WARN: {config_path} top-level is "
            f"{type(data).__name__}, not object; skipping.\n"
        )
        return []
    removed = [k for k in STALE_KEYS if k in data]
    if not removed:
        return []
    for k in removed:
        del data[k]
    backup = config_path.with_suffix(".json.bak")
    # PF4 defense: atomic mode-set at CREATE time via os.open(O_WRONLY|
    # O_CREAT|O_TRUNC, 0o600). Previous "write_text then chmod" had a
    # TOCTOU window where a SIGKILL / OOM / power-loss between the two
    # calls left the .bak with the operator's Kilo apiKey at 0644.
    # os.open respects the umask, so we clear it inside a scope guard.
    old_umask = os.umask(0o077)
    try:
        # O_TRUNC in case the .bak already exists from a prior run.
        fd = os.open(
            str(backup),
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(original)
    finally:
        os.umask(old_umask)
    # PF5 defense: also chmod the finished .bak (defense-in-depth in case
    # the FS ignored the create-time mode). Log a warning if that fails —
    # DO NOT silent-swallow, or the operator believes the secret is
    # protected on a FUSE / vfat / network mount that ignored the mode.
    try:
        backup.chmod(0o600)
    except OSError as exc:
        sys.stderr.write(
            f"[sanitize_kilo_config] WARN: chmod 0o600 on {backup} failed "
            f"({type(exc).__name__}: {exc}); filesystem may ignore mode. "
            "Backup MAY be readable by other users on this host — verify "
            "with `stat` and move to a mode-respecting FS if the operator "
            "wants secret isolation.\n"
        )
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
