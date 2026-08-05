#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_plan_shape_gates.py, tests/test_check_test_proposal.py | none
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
import subprocess
import sys
from pathlib import Path

_HEADING = re.compile(r"^#{1,6}\s", re.MULTILINE)
# Spine+ticket plan sets: a dated plan directory is one plan unit (its spine).
_PLAN_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+$")


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


# Balanced line-anchored fences + inline single-line quotes — the shared parsing
# contract (keep in step with check_plan_tickets._FENCE_RE): a fenced example
# `Given` row must not count as a behavior.
_FENCE_RE = re.compile(r"(?:^[ \t]*(`{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$|```[^`\n]+```)", re.M | re.S)


def _count_behaviors(content: str) -> int:
    """Behaviors = Given/When/Then triples in the Behavior Contract section (proxy: `Given` markers,
    section extracted AFTER fence-stripping, so quoted content can't hijack or inflate)."""
    stripped = _FENCE_RE.sub("", content)
    section = _section(stripped, "behavior contract") or ""
    return len(re.findall(r"\bgiven\b", section, re.IGNORECASE))


# NOTE: BOTH counters strip fences from the whole text FIRST, then extract —
# the same order as check_plan_tickets (quoted-content semantics: a fenced
# `## Heading` is not a heading, a fenced row is not a row). Symmetric, or a
# one-sided strip fails healthy plans; extract-then-strip would let a fenced
# `## Behavior Contract` template hijack _section's first-heading match and a
# fenced `#` comment truncate a section. (The two PRESENCE gates in
# evaluate_plan stay RAW by design — an all-fenced contract then fails at
# behaviors<1, which is fail-closed.)


def _count_criteria(content: str) -> int:
    """Acceptance criteria = top-level list items under a Success/Acceptance-criteria heading. 0 if
    there is no such section (→ the count comparison is skipped; structure-only)."""
    stripped = _FENCE_RE.sub("", content)
    section = _section(stripped, "success criteria") or _section(stripped, "acceptance criteria")
    if not section:
        return 0
    # Quoted content is NEVER a denominator: an all-fenced criteria section
    # counts 0 and the comparison is skipped (structure-only) — a raw fallback
    # would re-open both the inflation and the fenced-template hijack.
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


def _baseline_ref() -> str | None:
    """The ref to diff against: the pushed upstream if configured, else HEAD. None if not a git repo."""
    up = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "@{upstream}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if up.returncode == 0 and up.stdout.strip():
        return up.stdout.strip()
    head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"], capture_output=True, text=True, check=False
    )
    return "HEAD" if head.returncode == 0 else None


def _new_plans(plans_dir: Path) -> set[str] | None:
    """Plan basenames present NOW but absent at the baseline (upstream, else HEAD) — i.e. the plans
    THIS change introduces. Returns None if git is unavailable (caller falls back to legacy behavior).

    Shared-tree fix: on one `master`, `max(all plans)` targets whatever plan sorts last — often a
    *sibling's* draft the current agent never authored (esp. after archiving an EXECUTED plan exposes
    the next one). Only a plan this change ADDS is this agent's proposal; editing an old plan or a
    sibling's pre-existing plan is not.
    """
    ref = _baseline_ref()
    if ref is None:
        return None
    r = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, "docs/development/plans/"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return None
    # Keys are PLANS-DIR-RELATIVE paths (never bare basenames): a monolith→plan-set
    # migration (plans/X.md → plans/X/X.md) must read as a NEW plan, and a spine
    # whose basename collides with some other pre-existing file must not vanish.
    prefix = "docs/development/plans/"
    baseline = {
        p[len(prefix) :]
        for p in (line.strip().strip('"') for line in r.stdout.splitlines())
        if p.endswith(".md") and p.startswith(prefix) and "/archived/" not in p
    }
    current = {p.name for p in plans_dir.glob("*.md")}  # glob("*.md") excludes archived/ subdir
    # Spine+ticket plan sets: a plan DIRECTORY is one plan unit, represented by its
    # same-stem SPINE (tickets never enter the set — the spine's roll-up section is
    # what carries the Behavior Contract this gate demands). Without this, a plan
    # that is a directory is invisible to the flat glob and the gate goes inert.
    current |= {
        f"{d.name}/{d.name}.md"
        for d in plans_dir.iterdir()
        if d.is_dir() and _PLAN_DIR_RE.match(d.name) and (d / f"{d.name}.md").is_file()
    }
    return current - baseline


def check_proposal() -> bool:
    plans_dir = Path("docs/development/plans/")
    if not plans_dir.exists():
        print("INFO: No plans directory found - skipping Behavior Contract check")
        return True
    plans = list(plans_dir.glob("*.md"))
    # Spine+ticket plan sets: the same-stem spine inside a dated plan dir is a plan
    # (without this, a dir-shaped plan set makes the presence check exit early and
    # the whole gate goes inert).
    plans += [
        d / f"{d.name}.md"
        for d in plans_dir.iterdir()
        if d.is_dir() and _PLAN_DIR_RE.match(d.name) and (d / f"{d.name}.md").is_file()
    ]
    if not plans:
        print("INFO: No plan files found - skipping Behavior Contract check")
        return True

    new_plans = _new_plans(plans_dir)
    if new_plans is not None:
        # DIFF-SCOPED (shared-tree correct): only plans THIS change introduces must carry a Behavior
        # Contract. A sibling's pre-existing plan, and an edit to an old plan, are not this agent's
        # proposal — so they never fail this agent's gate.
        if not new_plans:
            print("INFO: No new plan proposed in this change - skipping Behavior Contract check")
            return True
        all_ok = True
        for name in sorted(new_plans):
            path = plans_dir / name  # relpath keys resolve directly (flat AND nested)
            if not path.exists():
                continue
            ok, msg = evaluate_plan(path.read_text())
            print(f"{'PASS' if ok else 'FAIL'}: {name}: {msg}")
            if not ok:
                all_ok = False
        if not all_ok:
            print("\nBehavior Contract format:")
            print("  ## Behavior Contract")
            print(
                "  - **Given** <state>, **When** <action>, **Then** <result>.   # one per behavior"
            )
            print("  - **Mocked:** [what is mocked vs. real]")
        return all_ok

    # Fallback (git unavailable): legacy latest-by-name behavior. Latest by filename date prefix
    # (`YYYY-MM-DD-…`), NOT mtime, so a one-line edit to an old plan is not the target.
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
