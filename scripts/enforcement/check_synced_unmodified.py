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
import shlex
import subprocess
import sys
from pathlib import Path

FABRIK_ROOT = Path("/opt/fabrik")
LOCK_REL = ".fabrik/synced.lock"


def _md5(path: Path) -> str:
    h = hashlib.md5(usedforsecurity=False)  # drift detection, never crypto
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


def _retired_vendored_dirs() -> tuple[str, ...]:
    """Vendored dirs the fleet has RETIRED — deleting them locally is the sanctioned action.

    Same degradation as `_seeded_not_enforced`: empty when the manifest is not importable.

    Why this exists (found 2026-09-08 by the independent closing pass of the D-196 retirement):
    this check iterates the project's `.fabrik/synced.lock`, which is a FROZEN SNAPSHOT rewritten
    only by a sync. `RETIRED_VENDORED_DIRS` tells projects they "may delete it at their own pace",
    but a lock row whose file is absent is a hard failure here — so in any target the sync no
    longer reaches, following that instruction reds `final_gate` forever with no way to clear it.
    Measured: 2 of 47 locks under /opt still carry the 26 `libs/subagents` rows, both in
    worktree-shaped repos that the SYNC skips by design (`sync_enforcement_to_projects.py:2269`,
    `.git` is a file — this `main()` has no such check and processes them, which is exactly why
    their frozen locks matter here), both frozen since
    2026-09-03 — and both belong to fabrik-lib, the repo that REQUESTED the retirement.
    """
    if not FABRIK_ROOT.exists():
        return ()
    sys.path.insert(0, str(FABRIK_ROOT / "scripts"))
    try:
        from fabrik_synced_manifest import RETIRED_VENDORED_DIRS

        return tuple(RETIRED_VENDORED_DIRS)
    except ImportError:
        return ()


def _main_checkout(project_root: Path) -> Path | None:
    """The main checkout when `project_root` is a LINKED worktree (its git-dir differs from the
    shared git-common-dir), else None. A submodule has a `.git` FILE too, so the file's shape is
    never the test. Any git failure reads as "not a linked worktree"."""
    try:
        out = subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "rev-parse",
                "--path-format=absolute",
                "--git-dir",
                "--git-common-dir",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = out.stdout.splitlines()
    if out.returncode != 0 or len(lines) < 2:
        return None
    git_dir, common = Path(lines[0]).resolve(), Path(lines[1]).resolve()
    return None if git_dir == common else common.parent


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
    # `item[0] if tuple` mirrors check_sync_trigger_coverage.py:247 — these manifest lists accept
    # a tuple entry by convention, and an uncaught AttributeError here would fire in ~46 repos.
    retired = tuple(
        (d[0] if isinstance(d, tuple) else d).rstrip("/") + "/" for d in _retired_vendored_dirs()
    )
    drifted: list[str] = []
    changed: list[str] = []  # differs or deleted — the stale-worktree remedy's subjects
    for rel, distributed_hash in lock.items():
        if rel in seeded:
            continue
        dest = project_root / rel
        # A retired dir is the PROJECT'S now — deleting it AND editing it are both sanctioned,
        # and neither can ever be cleared by a sync that no longer reaches it. The first version
        # skipped only the deletion, so a project that kept the dir and changed one line reds
        # `final_gate` forever, under a remedy text ("the next sync restores it") that is false
        # for a retired path. `startswith(())` is False, so an empty tuple (manifest unimportable)
        # degrades to the old behaviour with no special case — verified, not assumed.
        if rel.startswith(retired):
            continue
        if not dest.exists():
            drifted.append(f"{rel} — DELETED locally (a Fabrik-synced file must exist)")
            changed.append(rel)
        elif _md5(dest) != distributed_hash:
            drifted.append(rel)
            changed.append(rel)

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
        main_checkout = _main_checkout(project_root)
        if main_checkout is not None and changed:
            # W-800579be: in a linked worktree the copy may be STALE instead — the sync never
            # overwrites a worktree file it cannot prove it wrote, while the main checkout's
            # fresh lock lands here. The gate stays red (a stale rule is still a stale rule);
            # only the remedy is named honestly.
            print()
            print("This is a linked worktree: if you edited nothing, a copy may be STALE (the hub")
            print("re-synced the main checkout after this worktree was made). Re-copy it:")
            for rel in sorted(changed):
                src = main_checkout / rel
                if src.is_file() and _md5(src) == lock[rel]:
                    print(f"   cp {shlex.quote(str(src))} {shlex.quote(rel)}")
                else:
                    print(
                        f"   {rel}: the main checkout does not match the lock either — re-run the sync"
                    )
        return 1

    print(f"✓ all {len(lock)} Fabrik-synced files match what was distributed ({LOCK_REL})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
