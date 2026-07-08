#!/usr/bin/env python3
# AFTER-EDIT: none
"""
Check that the latest plan carries a Behavior Contract (the STRUCTURE gate).

The plan MUST enumerate a behavior (Given/When/Then triple) per acceptance criterion — NOT a single
One-Test Rule. If the plan states N acceptance criteria (a `## Success criteria` section) and the
Behavior Contract enumerates fewer than N behaviors → FAIL. A plan with no parseable criteria section
passes on structure alone (a Behavior Contract with >=1 enumerated behavior). No plans dir / no plans
→ skip. (Substance — is every behavior *actually* tested — is the /fabrik-review job, not this gate.)

Exit codes:
    0: Behavior Contract present (>= criteria), or no plan/dir
    1: latest plan missing or short of its Behavior Contract
"""

import re
import sys
from pathlib import Path

_HEADING = re.compile(r"^#{1,6}\s", re.MULTILINE)


def _section(content: str, title_substr: str) -> str | None:
    """Body of the FIRST *section* heading (level 2+, so the H1 plan title is skipped — its text can
    also contain the substring) whose text contains ``title_substr`` (case-insensitive), up to the
    next heading. ``None`` if no such heading exists."""
    m = re.search(
        rf"^#{{2,6}}\s+.*{re.escape(title_substr)}.*$", content, re.IGNORECASE | re.MULTILINE
    )
    if not m:
        return None
    rest = content[m.end() :]
    nxt = _HEADING.search(rest)
    return rest[: nxt.start()] if nxt else rest


def _count_behaviors(content: str) -> int:
    """Behaviors = Given/When/Then triples in the Behavior Contract section (proxy: `Given` markers,
    scoped to the section so prose 'given' elsewhere can't inflate the count)."""
    section = _section(content, "behavior contract") or ""
    return len(re.findall(r"\bgiven\b", section, re.IGNORECASE))


def _count_criteria(content: str) -> int:
    """Acceptance criteria = top-level list items under a Success/Acceptance-criteria heading. 0 if
    there is no such section (→ the count comparison is skipped; structure-only)."""
    section = _section(content, "success criteria") or _section(content, "acceptance criteria")
    if not section:
        return 0
    return len(re.findall(r"^\s*(?:\d+\.|[-*])\s+\S", section, re.MULTILINE))


def evaluate_plan(content: str) -> tuple[bool, str]:
    """Return ``(ok, message)`` for one plan's Behavior Contract."""
    if "behavior contract" not in content.lower():
        return False, (
            "missing a '## Behavior Contract' section — enumerate a test per user-observable "
            "behavior, not a single One-Test Rule"
        )
    missing = [k for k in ("Given", "When", "Then") if k.lower() not in content.lower()]
    if missing:
        return (
            False,
            f"Behavior Contract missing the Given/When/Then structure: {', '.join(missing)}",
        )
    behaviors = _count_behaviors(content)
    if behaviors < 1:
        return False, "Behavior Contract enumerates no behavior (a Given/When/Then triple)"
    criteria = _count_criteria(content)
    if criteria and behaviors < criteria:
        return False, (
            f"Behavior Contract enumerates {behaviors} behavior(s) but the plan states {criteria} "
            "acceptance criteria — add a Given/When/Then behavior per criterion (or trim the criteria)"
        )
    detail = f"{behaviors} behavior(s)" + (
        f" >= {criteria} criteria" if criteria else " (structure-only — no criteria section)"
    )
    return True, f"Behavior Contract OK — {detail}"


def check_proposal() -> bool:
    plans_dir = Path("docs/development/plans/")
    if not plans_dir.exists():
        print("INFO: No plans directory found - skipping Behavior Contract check")
        return True
    plans = list(plans_dir.glob("*.md"))
    if not plans:
        print("INFO: No plan files found - skipping Behavior Contract check")
        return True
    # Latest by filename date prefix (`YYYY-MM-DD-…`), NOT mtime: mtime makes any edit to an OLD plan
    # (even a one-line link fix) the check target — a shared-master false-positive.
    latest_plan = max(plans, key=lambda p: p.name)
    ok, msg = evaluate_plan(latest_plan.read_text())
    if not ok:
        print(f"FAIL: Plan {latest_plan.name}: {msg}")
        print("\nBehavior Contract format:")
        print("  ## Behavior Contract")
        print("  - **Given** <state>, **When** <action>, **Then** <result>.   # one per behavior")
        print("  - **Mocked:** [what is mocked vs. real]")
        return False
    print(f"PASS: {latest_plan.name}: {msg}")
    return True


if __name__ == "__main__":
    sys.exit(0 if check_proposal() else 1)
