#!/usr/bin/env python3
# AFTER-EDIT: scripts/final_gate.py | docs/reference/enforcement-sync.md
"""Vendored-enforcement drift report for sync-EXCLUDED repos — advisory, hub-only.

The class this closes (measured, 2026-08-16, fabrik-lib finding 01M05F4QBR6B0WSNJS2ZXHN80V):
two agents in two days each assumed the governance-sync would deliver an enforcement fix to
fabrik-lib — a repo the sync deliberately EXCLUDES ("vendor, don't depend") — so one fix sat
undelivered and another arrived only by accident. Of fabrik-lib's 30 vendored checks, 14
differed from hub and "differs" vs "stale" was indistinguishable without opening each file.

What this does: for every /opt repo that VENDORS the enforcement set (has scripts/enforcement/
but NO .fabrik/synced.lock — the lock marks a sync-MANAGED project; the hub itself is skipped),
hash-compare each vendored governance file against the hub's copy and report:

  IDENTICAL         — byte-equal to hub
  DESIGN            — differs, and the repo's allowlist declares the divergence deliberate
  UNREVIEWED DIFF   — differs with no declaration: debt or design, NOBODY KNOWS — the class
  LOCAL-ONLY        — exists there, not in hub (theirs; never flagged)

The allowlist is THE REPO'S OWN file — `<repo>/.fabrik/vendored-divergence-allowlist`, one
repo-relative path per line, `#` comments — because deliberate divergence is that repo's
design decision, not the hub's. This check only READS other repos; it never writes them.

POLICY, stated explicitly because its absence was half the finding: **sync-excluded repos
PULL; nothing is pushed to them.** A sender fixing a shared file tells them "re-vendor it
yourself", never "it will reach you on the next sync".

warn_only: this check has no failing exit path — an UNREVIEWED DIFF is a ⚠ advisory line
(the ⚠-first stdout is the gate emitter's opt-in). Hub-only: on any repo that is not
/opt/fabrik it prints nothing and exits 0 (the same self-skip pattern as the command-corpus
audit — the comparison target is the hub's own tree).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HUB = Path("/opt/fabrik")
OPT = Path("/opt")
ALLOWLIST_REL = ".fabrik/vendored-divergence-allowlist"

# The governance set a vendorer copies: the enforcement dir plus the three root drivers.
ROOT_FILES = ("scripts/final_gate.py", "scripts/select_rules.py", "scripts/review_rubric.py")


def _sha(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return ""


def _governance_set(root: Path) -> dict[str, str]:
    """repo-relative path -> sha256 for the vendored governance surface under ``root``."""
    out: dict[str, str] = {}
    enf = root / "scripts" / "enforcement"
    if enf.is_dir():
        for f in sorted(enf.glob("*.py")):
            out[str(f.relative_to(root))] = _sha(f)
    for rel in ROOT_FILES:
        f = root / rel
        if f.is_file():
            out[rel] = _sha(f)
    return out


def _allowlist(root: Path) -> set[str]:
    f = root / ALLOWLIST_REL
    if not f.is_file():
        return set()
    out: set[str] = set()
    try:
        for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                out.add(ln)
    except OSError:
        pass
    return out


def _vendoring_repos() -> list[Path]:
    """Sync-excluded vendorers: scripts/enforcement/ present, no synced.lock, not the hub."""
    found: list[Path] = []
    try:
        entries = sorted(OPT.iterdir())
    except OSError:
        return found
    for d in entries:
        try:
            if not d.is_dir() or d == HUB or d.name.startswith((".", "_")):
                continue
            if not (d / "scripts" / "enforcement").is_dir():
                continue
            if (d / ".fabrik" / "synced.lock").is_file():
                continue  # sync-managed: the governance-sync owns its copies, not this report
            found.append(d)
        except OSError:
            continue
    return found


def main() -> int:
    root = Path.cwd().resolve()
    if root != HUB:
        return 0  # hub-only by design — the comparison target is the hub's own tree

    hub_set = _governance_set(HUB)
    lines: list[str] = []
    for repo in _vendoring_repos():
        theirs = _governance_set(repo)
        allow = _allowlist(repo)
        identical = [r for r in theirs if r in hub_set and theirs[r] == hub_set[r]]
        differing = [r for r in theirs if r in hub_set and theirs[r] != hub_set[r]]
        local_only = [r for r in theirs if r not in hub_set]
        design = [r for r in differing if r in allow]
        unreviewed = [r for r in differing if r not in allow]
        head = (
            f"{repo.name}: {len(identical)} identical · {len(design)} declared-design · "
            f"{len(unreviewed)} UNREVIEWED diff · {len(local_only)} local-only"
        )
        if unreviewed:
            lines.append(f"  ⚠ {head}")
            for r in unreviewed:
                lines.append(
                    f"    ⚠ {repo.name}/{r}: differs from hub with no declaration — debt or "
                    f"design, nobody knows. Re-vendor it, or declare it in {ALLOWLIST_REL}"
                )
        else:
            lines.append(f"    {head}")

    if any(ln.lstrip().startswith("⚠") for ln in lines):
        print(
            "⚠ check_vendored_drift ADVISORY — sync-excluded repos PULL, nothing is pushed "
            "to them; undeclared divergence below is invisible debt until someone opens it:"
        )
        for ln in lines:
            print(ln)
    else:
        print("check_vendored_drift: OK (every vendored governance divergence is declared)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
