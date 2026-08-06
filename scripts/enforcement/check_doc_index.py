#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_doc_index.py docs/workflows/FINAL_GATE_WORKFLOW.md
"""INDEX.md ↔ docs/ tree drift gate (docs-truth convergence, 2026-07-20).

Two directions:

(a) every ``docs/``-prefixed markdown link target named in INDEX.md exists on disk
    (directories allowed);
(b) every tracked live doc under ``docs/`` appears in INDEX.md by full path or
    basename — excluding archives, the plan/epic/review/spec pipeline content,
    and the daily-regenerated selection set (``docs/reference/kilo/*_SELECTION.md``
    plus KILO_MODEL_CAPABILITIES.md / KILO_AGENT_SELECTION_GUIDE.md and
    ``docs/traycer/kilo_selected_agents.md`` — sourced from daily_refresh.sh's
    git-add block, verified 2026-07-20).

Exit 0 clean; exit 1 on drift (Tier-2 blocking).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

EXCLUDE_PREFIXES = (
    "docs/archive/",
    "docs/infrastructure/archive/",
    "docs/development/plans/",
    "docs/development/epics/",
    "docs/development/reviews/",
    "docs/superpowers/",
)
EXCLUDE_EXACT = {
    "docs/.doc-policy.md",  # scaffold dot-stub, deliberately unindexed
    "docs/reference/kilo/KILO_MODEL_CAPABILITIES.md",
    "docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md",
    "docs/traycer/kilo_selected_agents.md",
}
_SELECTION_RE = re.compile(r"^docs/reference/kilo/[A-Z_]*_?SELECTION\.md$")


def main() -> int:
    as_json = "--json" in sys.argv
    index_text = (REPO / "INDEX.md").read_text(encoding="utf-8", errors="replace")
    problems: list[str] = []

    # (a) INDEX targets exist
    for m in re.finditer(r"\]\((docs/[^)#\s]+?)(?:#[^)]*)?\)", index_text):
        t = m.group(1).replace("%20", " ").rstrip("/")
        if not (REPO / t).exists():
            problems.append(f"INDEX.md names missing path: {t}")

    # (b) live docs are indexed (path or basename)
    # quotePath=false: git escapes non-ASCII paths by default ("\342\200\223" for
    # an en dash) and wraps them in quotes — the escaped form never matches
    # INDEX.md's real text, false-flagging an indexed doc as missing
    # (trade-intelligence upstream, 2026-08-05).
    tracked = subprocess.run(
        ["git", "-c", "core.quotePath=false", "ls-files", "docs/**/*.md", "docs/*.md"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()
    for p in tracked:
        if p.startswith(EXCLUDE_PREFIXES) or p in EXCLUDE_EXACT or _SELECTION_RE.match(p):
            continue
        base = Path(p).name
        if p not in index_text and base not in index_text:
            problems.append(f"live doc not in INDEX.md: {p}")

    if as_json:
        print(json.dumps({"status": "success" if not problems else "failure", "drift": problems}))
    else:
        for x in problems:
            print(f"ERROR: {x}")
        if not problems:
            print("check_doc_index: OK — INDEX.md and the live docs tree agree")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
