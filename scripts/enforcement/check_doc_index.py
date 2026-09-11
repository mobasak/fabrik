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
    # Certification boards are the fourth per-run, dated, machine-generated artifact class, and
    # they arrived (2026-08-27) without this exclusion — so a synced COMMAND mandated the directory
    # while a synced CHECK penalised it, and every project reddened its gate on its first
    # certification (job-agent: 16 ERRORs, worked around by injecting 16 per-run rows into a
    # curated index). Board shape, ticket naming, dispositions and evidence paths already have a
    # dedicated grader in check_certification_coverage.py; INDEX.md maps DURABLE docs, and a cert
    # board is a run record.
    "docs/development/certifications/",
    "docs/superpowers/",
)
EXCLUDE_EXACT = {
    "docs/.doc-policy.md",  # scaffold dot-stub, deliberately unindexed
    "docs/reference/kilo/KILO_MODEL_CAPABILITIES.md",
    "docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md",
    "docs/traycer/kilo_selected_agents.md",
}
_SELECTION_RE = re.compile(r"^docs/reference/kilo/[A-Z_]*_?SELECTION\.md$")

# Hub-SEEDED and project-OWNED — exempt only while UNADOPTED (still untracked).
#
# The governance sync drops docs/DECISIONS.md into every repo ONCE
# (fabrik_synced_manifest.SEED_IF_MISSING) and deliberately keeps it OUT of the generated
# .gitignore block, because an ignored ledger can never be committed and its git history IS
# the who/when corroboration layer. Every OTHER doc the sync writes under docs/ IS gitignored
# and therefore invisible to `ls-files --others --exclude-standard` — so this is the single
# file for which the untracked-counts-as-live rule above rests on a false premise: no session
# in this repo authored it, so "the run that creates a doc owes its INDEX row" has no author
# to bill, and the red lands on whoever next runs a gate. Measured 2026-09-11 across the 45
# git repos under /opt: all 45 carry the file, 35 have no INDEX row, 20 of those have never
# tracked it.
#
# The obligation attaches on ADOPTION, not on arrival: the moment a repo commits its ledger it
# is that project's own durable doc and owes its INDEX row like any other — 9 of the 45 are in
# exactly that state today, and their finding is a TRUE positive this exemption must not eat.
# That is the whole reason the exemption is keyed on tracked-ness rather than added to
# EXCLUDE_EXACT, which would have silenced those 9 too.
SEEDED_UNADOPTED = {"docs/DECISIONS.md"}


def main() -> int:
    as_json = "--json" in sys.argv
    index_path = REPO / "INDEX.md"
    if not index_path.is_file():
        # 5 of the 45 /opt repos carry this synced check and have no INDEX.md (measured
        # 2026-09-11), where the unguarded read raised FileNotFoundError: the gate saw a
        # TRACEBACK, which names no remedy and reads like a broken check rather than a
        # finding. Same exit code, diagnosable cause.
        msg = "INDEX.md is missing — the docs index every Doc Sync Matrix row points at"
        if as_json:
            print(json.dumps({"status": "failure", "drift": [msg]}))
        else:
            print(f"ERROR: {msg}")
        return 1
    index_text = index_path.read_text(encoding="utf-8", errors="replace")
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
    def _ls(*extra: str) -> list[str]:
        return subprocess.run(
            ["git", "-c", "core.quotePath=false", "ls-files", *extra, "docs/**/*.md", "docs/*.md"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.splitlines()

    tracked = _ls()
    # UNTRACKED docs count as live (transdoc 01M17VA9): tracked-only scoping gave the
    # AUTHORING run a false green — the run that creates a doc got success, committed on
    # it, and the missing INDEX row surfaced as the NEXT agent's red (on a shared tree,
    # somebody else's red, with the authoring context already gone). A doc that exists on
    # disk under the INDEX-governed tree is a live doc whether or not it is staged; the
    # per-run pipeline dirs stay excluded, so in-flight drafts there never fire.
    untracked = set(_ls("--others", "--exclude-standard"))
    for p in dict.fromkeys([*tracked, *untracked]):
        if p.startswith(EXCLUDE_PREFIXES) or p in EXCLUDE_EXACT or _SELECTION_RE.match(p):
            continue
        if p in SEEDED_UNADOPTED and p in untracked:
            continue  # seeded by the hub, never adopted here — not this repo's row to owe
        base = Path(p).name
        if p not in index_text and base not in index_text:
            tag = (
                " (untracked — the run that creates a doc owes its INDEX row)"
                if p in untracked
                else ""
            )
            problems.append(f"live doc not in INDEX.md: {p}{tag}")

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
