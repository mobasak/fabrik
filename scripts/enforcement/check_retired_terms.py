#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_retired_terms.py docs/workflows/FINAL_GATE_WORKFLOW.md
"""Retired-tech tripwire — WARN-only, ALWAYS exits 0 (docs-truth convergence 2026-07-20).

Flags retired-stack tokens (Kilo CLI, Windsurf Cascade, Coolify, Supabase) appearing
in a LIVE doc line whose surrounding context (±2 lines) carries no retirement marker.
This catches the dominant docs-truth defect class — a retired tool framed as live —
at commit time instead of at the next convergence sweep.

Never blocks: findings go to stdout as WARN lines and the script exits 0 regardless
(register with ``advisory=True`` — ``final_gate.run_optional_check`` fails on ANY
non-zero exit whatever the advisory flag says, so WARN-only semantics MUST come from
the exit code here; the ``check_lint_ratchet.py``/``check_mutation.py`` pattern).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

TERMS = re.compile(r"Kilo CLI|Windsurf Cascade|Coolify|Supabase")
MARKERS = re.compile(
    r"retired|RETIRED|legacy|Legacy|historical|Historical|decommission|"
    r"pre-migration|archive|Archive|no longer|superseded|removed|renamed from|"
    r"was |former|dead code|residue|not a default|exception only|keep-alive|"
    r"migrat|Prior|vintage|era\b|-compatible|Sentry-compatible",
)

SKIP_PREFIXES = (
    "docs/archive/",
    "docs/reference/research/",  # operator deep-research source material
    "docs/infrastructure/archive/",
    "docs/development/",
    "docs/superpowers/",
)
SKIP_EXACT = {
    "docs/LESSONS_LEARNT.md",  # dated ledger
    "docs/reference/LOCAL_LLM_INFRASTRUCTURE.md",  # operator-excluded 2026-07-20
}
# Directory/file NAMES containing 'kilo' are the live flywheel store, not the CLI.
_NAME_ONLY = re.compile(r"kilo[-_/]|/kilo|kilo_")


def main() -> int:
    warns: list[str] = []
    tracked = subprocess.run(
        ["git", "ls-files", "docs/**/*.md", "docs/*.md"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()
    for p in tracked:
        if p.startswith(SKIP_PREFIXES) or p in SKIP_EXACT:
            continue
        try:
            lines = (REPO / p).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        # Doc-level banner rule: a retirement banner in the file head marks the
        # WHOLE doc's mentions as documented-historical (the traycer-README pattern).
        head = " ".join(lines[:30])
        if re.search(r"[Rr]etired 2026|RETIRED 2026|retirement banner|[Pp]re-migration vintage|[Pp]re-migration context|decommission|Coolify-era|Coolify-API era|Coolify-flavored historical", head):
            continue
        for i, line in enumerate(lines):
            if not TERMS.search(line):
                continue
            ctx = " ".join(lines[max(0, i - 2) : i + 3])
            if MARKERS.search(ctx):
                continue
            warns.append(f"{p}:{i + 1}: unmarked retired-tech mention: {line.strip()[:120]}")
    for w in warns:
        print(f"WARN: {w}")
    if not warns:
        print("check_retired_terms: OK — no unmarked retired-tech framing in live docs")
    else:
        print(f"check_retired_terms: {len(warns)} WARN(s) — advisory only, not blocking")
    return 0  # ALWAYS — WARN-only by contract


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — WARN-only contract: never block the gate
        print(f"check_retired_terms: internal error ({exc}) — advisory check, not blocking")
        sys.exit(0)
