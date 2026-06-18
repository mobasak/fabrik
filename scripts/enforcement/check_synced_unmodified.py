#!/usr/bin/env python3
"""Gate check: Fabrik-synced files must not be modified locally.

Files listed in ``scripts/fabrik_synced_manifest.py`` are centrally distributed
from ``/opt/fabrik`` by ``sync_enforcement_to_projects.py``. Editing a copy inside
a project is futile — the next sync overwrites it. This check fails the gate when
a project's copy of a synced file has drifted from the ``/opt/fabrik`` canonical
source, so the agent is told to revert and make the change upstream instead.

Self-exempt inside ``/opt/fabrik`` (the source). Skips gracefully when
``/opt/fabrik`` is not present (e.g. deployed on a VPS) — nothing to compare.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

FABRIK_ROOT = Path("/opt/fabrik")


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Fabrik-synced files are unmodified.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    project_root = args.project_root.resolve()

    # Self-exemption: this IS the canonical source.
    if project_root == FABRIK_ROOT.resolve():
        print("(source repo — synced-files check skipped)")
        return 0

    # Can't compare without the canonical source (e.g. on a VPS).
    if not FABRIK_ROOT.exists():
        print("(/opt/fabrik not present — synced-files check skipped)")
        return 0

    sys.path.insert(0, str(FABRIK_ROOT / "scripts"))
    try:
        from fabrik_synced_manifest import SEEDED_NOT_ENFORCED, iter_synced_pairs
    except ImportError as e:  # pragma: no cover - defensive
        print(f"(synced-files manifest unavailable: {e} — skipped)")
        return 0

    drifted: list[str] = []
    for src, dest in iter_synced_pairs(project_root, FABRIK_ROOT):
        rel = dest.relative_to(project_root).as_posix()
        if rel in SEEDED_NOT_ENFORCED:
            continue
        if not src.exists() or not dest.exists():
            continue  # not synced into this project (or removed upstream)
        if _md5(src) != _md5(dest):
            drifted.append(rel)

    if drifted:
        print(
            "❌ Fabrik-synced files modified locally — these are CENTRALLY MANAGED and "
            "are overwritten on every sync:"
        )
        for rel in sorted(drifted):
            print(f"   - {rel}")
        print()
        print("Fix: revert the local copies to the canonical /opt/fabrik versions —")
        print("   python3 /opt/fabrik/scripts/sync_enforcement_to_projects.py --force")
        print("If the change is correct for ALL projects, make it in /opt/fabrik/<path>")
        print("first, then re-sync. Otherwise propose it upstream — do not fork it here.")
        return 1

    print("✓ all Fabrik-synced files match the /opt/fabrik source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
