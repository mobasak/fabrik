#!/usr/bin/env python3
# AFTER-EDIT: none
"""Gate check: Fabrik-synced files must not be modified locally.

Files listed in ``scripts/fabrik_synced_manifest.py`` are centrally distributed from
``/opt/fabrik`` by ``sync_enforcement_to_projects.py``. Editing a copy inside a project is
futile — the next sync overwrites it. This check fails the gate when a project's copy of a
synced file has been LOCALLY EDITED, so the agent is told to make the change upstream.

**Compares against the per-project lock (``.fabrik/synced.lock``), NOT live /opt/fabrik.**
The sync writes that lock at distribution time: the md5 of every synced file AS GIVEN to
THIS project. So a project merely BEHIND the advancing hub (its rules/scripts are an
older-but-unmodified published version, pending the next sync) matches its own lock and is
never flagged — which permanently kills the recurring false positive where updating a
governance file on the hub red-flagged every project that hadn't re-synced yet. Only a
genuine local edit — a file differing from the hash it was distributed with — fails.

No lock yet (a project not re-synced since the lock was introduced) → skip gracefully; the
next sync writes it and the check activates. Self-exempt inside ``/opt/fabrik`` (the source).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

FABRIK_ROOT = Path("/opt/fabrik")
LOCK_REL = ".fabrik/synced.lock"


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _seeded_not_enforced() -> set[str]:
    """Files distributed once but allowed to diverge (never flagged). Empty if the manifest
    isn't importable (e.g. /opt/fabrik absent) — a rare, acceptable degradation."""
    if not FABRIK_ROOT.exists():
        return set()
    sys.path.insert(0, str(FABRIK_ROOT / "scripts"))
    try:
        from fabrik_synced_manifest import SEEDED_NOT_ENFORCED

        return set(SEEDED_NOT_ENFORCED)
    except ImportError:
        return set()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Fabrik-synced files are unmodified.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    project_root = args.project_root.resolve()

    # Self-exemption: this IS the canonical source.
    if project_root == FABRIK_ROOT.resolve():
        print("(source repo — synced-files check skipped)")
        return 0

    lock_path = project_root / LOCK_REL
    if not lock_path.exists():
        # Not re-synced since the lock was introduced. Comparing against anything else
        # (live hub / git HEAD) re-introduces the version-skew false positive, so skip.
        print(f"(no {LOCK_REL} — project not yet re-synced; synced-files check skipped)")
        return 0
    try:
        lock: dict[str, str] = json.loads(lock_path.read_text())
    except Exception as e:  # pragma: no cover - defensive
        print(f"({LOCK_REL} unreadable: {e} — skipped)")
        return 0

    seeded = _seeded_not_enforced()
    drifted: list[str] = []
    for rel, distributed_hash in lock.items():
        if rel in seeded:
            continue
        dest = project_root / rel
        if not dest.exists():
            drifted.append(f"{rel} — DELETED locally (a Fabrik-synced file must exist)")
        elif _md5(dest) != distributed_hash:
            drifted.append(rel)

    if drifted:
        print(
            "❌ Fabrik-synced files modified locally — these are CENTRALLY MANAGED and are "
            "overwritten on every sync:"
        )
        for rel in sorted(drifted):
            print(f"   - {rel}")
        print()
        print("You edited a synced copy (it differs from what was distributed to this")
        print("project). Revert it (the next sync restores it), or make the change in")
        print("/opt/fabrik/<path> + re-sync if it's correct for ALL projects. Never fork here.")
        return 1

    print(f"✓ all {len(lock)} Fabrik-synced files match what was distributed ({LOCK_REL})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
