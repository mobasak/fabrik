#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_script_headers.py
"""Enforce the `# AFTER-EDIT:` coupling header on staged scripts.

Every script self-declares which files must be updated when *it* changes, via a header
line in its first lines:

    # AFTER-EDIT: scripts/fabrik_synced_manifest.py, .gitignore     (or `none`)

This gate mirrors check_doc_sync (touch-on-change, WARN-tier — never blocks):
- WARN if a staged `scripts/**/*.py` has no `# AFTER-EDIT:` header.
- WARN if the header names a coupled file that was NOT also staged in this change.

Touch-on-change by design: only *staged* scripts are inspected, so there is no mass
backfill — a script gains its header the next time it is edited. WARN-only (always
exit 0); promote to an ERROR gate once the active scripts are headered.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HEADER_RE = re.compile(r"#\s*AFTER-EDIT:\s*(.+)", re.IGNORECASE)
# Both separators the corpus actually uses: `a.py, b.md` AND `a.py | b.md`. The pipe form is the
# majority style in scripts/sysadmin/ and was parsed as FILENAMES — every pipe became a coupled
# file named "|" that was obviously never staged, so those scripts warned on every edit. Invisible
# until 2026-08-16, because the check was registered without `advisory`/`warn_only` and
# `run_optional_check` discarded its stdout on exit 0.
SEPARATORS = re.compile(r"[,|\s]+")
NONE_VALUES = {"none", "n/a", "na", "-", ""}
SKIP_PATTERNS = ("tests/", "test_", "_test.py", "__pycache__/", "/__init__.py")
HEADER_SCAN_LINES = 25


def _git(args: list[str]) -> list[str]:
    out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=20).stdout.strip()
    return out.split("\n") if out else []


def _skip(f: str) -> bool:
    return any(p in f for p in SKIP_PATTERNS)


def main() -> int:
    # ⚠️ `--quiet` exists ONLY for the gate, and the gate passes it (final_gate.py). Read why
    # before removing it: the denominator lines below were first shipped unconditionally, and
    # that put a content-free row in EVERY green gate run across the fleet — in human mode under
    # the `[ADVISORY] Script Coupling Header` row, AND in `--json`, because this check is
    # registered `warn_only=True` and the `advisory` array (final_gate.py, built from
    # WARN_ONLY_CHECKS) applies NO ⚠ filter — only the `warnings` array does. The sibling
    # advisory rows stay silent when clean; this one must too. The corpus already paid for this
    # lesson once: tests/enforcement/test_plan_lock_release.py asserts `out == ""` because "a
    # foreign-only corpus is not worth two lines on every gate run there, forever".
    # A BARE run (an agent or human invoking this directly) passes no flag and stays informative,
    # which is the whole point of 01M1E6S1EAK7DNP74C1K9YHP3Z.
    quiet = "--quiet" in sys.argv[1:]
    staged = _git(["diff", "--cached", "--name-only"])
    if not staged:
        # "Nothing staged" is a REASON, not a silent pass. This early return is the shape the
        # bare run in 01M1E6S1EAK7DNP74C1K9YHP3Z actually hit (the reporter's scripts were
        # modified-UNSTAGED, and this check is staged-scoped by design).
        if not quiet:
            # Same "N staged script(s) inspected" wording as the clean path — one phrasing for one
            # concept, so a reader (and a test) is not matching two substrings for the same fact.
            print("OK — nothing staged; this check is staged-scoped (0 staged script(s) inspected).")
        return 0
    staged_set = set(staged)
    scripts = [f for f in staged if f.startswith("scripts/") and f.endswith(".py") and not _skip(f)]

    warnings: list[str] = []
    for f in scripts:
        p = Path(f)
        if not p.exists():  # staged deletion — nothing to check
            continue
        head = "\n".join(
            p.read_text(encoding="utf-8", errors="replace").splitlines()[:HEADER_SCAN_LINES]
        )
        m = HEADER_RE.search(head)
        if not m:
            warnings.append(
                f"{f}: no `# AFTER-EDIT:` header — declare the files to update when this "
                "script changes (or `# AFTER-EDIT: none`)."
            )
            continue
        listed = m.group(1).strip()
        if listed.lower() in NONE_VALUES:
            continue
        coupled = [c for c in SEPARATORS.split(listed) if c]
        missing = [c for c in coupled if c not in staged_set]
        if missing:
            warnings.append(
                f"{f}: `# AFTER-EDIT:` lists coupled file(s) not updated in this change: "
                f"{', '.join(missing)}."
            )

    for w in warnings:
        print(f"WARNING: {w}")
    if not warnings and not quiet:
        # ⚠️ State the DENOMINATOR on the clean path. Until 2026-09-01 this check printed
        # NOTHING on every silent outcome — no staged files, no staged scripts, and all-clean
        # were three different states that looked identical, and identical to the check never
        # having run (web-ecommerce-factory, 01M1E6S1EAK7DNP74C1K9YHP3Z: "pass and no-op are
        # indistinguishable"). A "0 findings" verdict that cannot say how many subjects it
        # examined is indistinguishable from having looked at nothing — the same law the
        # governance contract applies to agents, applied to the checker itself.
        # The `not quiet` guard is what keeps this out of every green fleet gate — see the
        # note in main()'s head for the mechanism (it is NOT the ⚠ filter, which guards only
        # the `warnings` array; warn_only stdout ships unfiltered in `advisory`).
        print(f"OK — {len(scripts)} staged script(s) inspected ({len(staged)} staged file(s)).")
    return 0  # WARN-only — never blocks the gate


if __name__ == "__main__":
    sys.exit(main())
