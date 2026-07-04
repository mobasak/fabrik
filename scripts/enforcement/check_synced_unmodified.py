#!/usr/bin/env python3
# AFTER-EDIT: none
"""Gate check: Fabrik-synced files must not be modified locally.

Files listed in ``scripts/fabrik_synced_manifest.py`` are centrally distributed
from ``/opt/fabrik`` by ``sync_enforcement_to_projects.py``. Editing a copy inside
a project is futile — the next sync overwrites it. This check fails the gate when
a project's copy of a synced file has been LOCALLY EDITED, so the agent is told to
make the change upstream instead.

The comparison is against canonical's git HEAD (the last-PUBLISHED version), not its live
working tree. Projects are synced at commit time, so HEAD is what they were last given.
This is what stops the recurring false positive: while a maintainer is mid-editing a
governance/enforcement file in ``/opt/fabrik`` (uncommitted, working-tree ahead), every
project still legitimately holds the last-published version and must NOT be flagged for
it. A genuine local edit still differs from HEAD and is caught.

Self-exempt inside ``/opt/fabrik`` (the source). Skips gracefully when
``/opt/fabrik`` is not present (e.g. deployed on a VPS) — nothing to compare.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

FABRIK_ROOT = Path("/opt/fabrik")


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _fabrik_head_md5(rel: str) -> str | None:
    """md5 of the LAST-COMMITTED (git HEAD) canonical version of a synced file — NOT the
    working tree. The sync distributes canonical at commit time (the pre-commit hook), so
    HEAD is what projects were last given. Comparing against HEAD (not the live working
    tree) is what stops the recurring false positive: while a maintainer is mid-editing a
    governance/enforcement file in /opt/fabrik (uncommitted, working-tree ahead), every
    project still legitimately holds the last-PUBLISHED version and must NOT be flagged.
    Returns None if the file isn't in HEAD yet (brand-new, uncommitted upstream) so the
    caller falls back to the working tree safely."""
    try:
        out = subprocess.run(
            ["git", "-C", str(FABRIK_ROOT), "show", f"HEAD:{rel}"],
            capture_output=True,
            timeout=15,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return hashlib.md5(out.stdout).hexdigest()


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
        if not src.exists():
            continue  # removed upstream — no longer synced into projects, OK
        if not dest.exists():
            # A synced file DELETED locally must be flagged — a deleted enforcement
            # script leaves the gate blind until the next sync restores it.
            drifted.append(f"{rel} — DELETED locally (a Fabrik-synced file must exist)")
            continue
        # Compare against canonical's git HEAD (last-published), not its working tree, so
        # uncommitted governance edits in /opt/fabrik never flag a project holding the
        # published version. A genuine local edit still differs from HEAD and is caught.
        canonical = _fabrik_head_md5(src.relative_to(FABRIK_ROOT).as_posix())
        if canonical is None:
            canonical = _md5(src)  # not yet committed upstream — fall back to working tree
        if canonical != _md5(dest):
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
