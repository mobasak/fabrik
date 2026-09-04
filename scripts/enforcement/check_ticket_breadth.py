#!/usr/bin/env python3
# AFTER-EDIT: tests/test_check_ticket_breadth.py, docs/reference/ticket-breadth.md, scripts/final_gate.py, commands/_sources/fabrik-plan-review.md | none
"""Ticket-breadth advisory — predict a ticket's review cost BEFORE it is executed.

WHY THIS IS A CHECK AND NOT A RULE
----------------------------------
"Keep tickets narrow" is prose, and prose does not bind an agent that read it
hours ago (Lesson 116). This runs at the moment the plan set is still editable —
at ``/fabrik-plan-review`` convergence and on the gate — so breadth is SEEN
before execution rather than paid for after.

THE MEASURED BASIS (provisional — see CALIBRATION)
--------------------------------------------------
From this repo's own review ledgers (``docs/development/reviews/*.md``, the same
corpus ``docs/workstation/kaizen.md`` reads for its ``Review rounds /plan``
column): review rounds per plan average **4.2 (n=14/22)** with maxima of **16**
and **13**. The rounds track how many INDEPENDENT RISK CLASSES one ticket
exposes, not its line count. The worked pair, 2026-08-15:

- ``T01-disarm-old-world`` — thread-safety + alert suppression + clock skew +
  fail-direction + ledger integrity (5 classes) → **8 rounds**, 34 fixups
  (``docs/development/reviews/2026-08-15-plan-1-login-once-credentials-T01-review.md``)
- ``T02b-fleet-gitignore`` — one gitignore line → **1 round**
  (``…-T02b-review.md``)

Roughly **1–2 rounds per risk class**, each fix opening the next round's surface.

THE SIGNAL
----------
Risk classes are not directly countable from a ticket, so this scores three
*declared* proxies, read from the ticket's own real fields:

1. ``areas``     — distinct top-level source areas in ``## Touches``
                   (``scripts/``, ``libs/``, ``src/``, ``docs/``, ``.claude/``…).
                   A ticket spanning many is broad. **Companion TEST surfaces
                   are excluded** — tests ship WITH the behaviour they prove
                   (the Behavior Contract requires a test per behaviour in the
                   SAME ticket, and watched-fail-first needs both in one
                   changeset), so a test surface is never an independent risk
                   class and never a split target. Counting them produced the
                   actively harmful advice "keep scripts/ and peel off tests/".
2. ``behaviors`` — ``## Behavior Contract`` Given/When/Then bullet count. Each
                   is a distinct user-observable behaviour = a review class.
3. ``mix``       — the ticket declares BOTH ordinary code AND a
                   governance/fleet-synced surface. A ~46-repo blast radius
                   mixed into local work is its own risk class.

``score = areas + behaviors + (1 if mix else 0)`` — an ESTIMATE of independent
risk classes. Components are always printed; a bare number would be
unfalsifiable.

Predicted rounds use the **measured** ratio, not the hand-counted one. The
operator's hand-counted classes cost 1–2 rounds each (T01: 5 classes → 8
rounds), but this score is a *proxy* for classes with a different scale.
Retroactively over the 14 tickets in this repo that carry real per-ticket round
receipts, ``rounds ≈ 1.0 × score`` (median 1.0, spread 0.3×–1.6×), so the
predicted range printed is ``0.5 × score`` to ``1.5 × score``. Using 1–2× here
would over-predict every ticket by roughly double — the retroactive table said
so, and the constants follow the data rather than the prose.

FAIL DIRECTION — ADVISORY
-------------------------
Default is warn + **exit 0**. This is a heuristic over declared fields; a
hard-fail would block planning on a guess, and a blocked plan is worse than a
broad one. ``--strict`` flips the exit code for opt-in use (a plan author who
wants the ratchet). Parse errors are swallowed with a NOTE — a malformed ticket
never reds a gate. A repo with no plan sets exits clean and SILENT (most of the
~46 fleet repos have none).

CALIBRATION — HONEST STATUS
---------------------------
``BREADTH_THRESHOLD`` is **5, re-derived from the data** after test surfaces
stopped counting (they had been inflating every score by 1). It is
**provisional**. The corpus is the 14 tickets with real per-ticket round
receipts (2026-08-15 T01/T02a/T02b/T03/T04 + 2026-08-07 T01–T08); corpus mean is
3.07 rounds, so "genuinely expensive" is taken as ``>= 4``:

===========  =====  =====  ========  =========
threshold    flags  hits   recall    precision
===========  =====  =====  ========  =========
3                8      3       3/3       0.38
**5**            4      2       2/3       0.50
6                2      0       0/3       0.00
===========  =====  =====  ========  =========

5 is the LARGEST threshold that still catches the 8-round ticket: at 6 the check
catches nothing expensive at all (recall 0/3) — a cliff, not a gradient. But the
margin is thin and must be stated: after the test-surface fix, 2026-08-15 T01
scores **exactly 5**, sitting ON the boundary rather than above it. Honest
weaknesses, recorded rather than tuned away:

- **It misses one.** 2026-08-07 T01 scores 3 and ran 4 rounds. Recall 2/3.
- **It over-flags.** 2026-08-15 T02a (score 7) cost 3 rounds and T03 (score 7)
  cost 2 — the two HIGHEST-scoring tickets with receipts are among the cheapest.
  Precision 0.50.
- **The correlation is weak-to-moderate, not strong:** Spearman ρ = 0.45,
  Pearson 0.31 (n=14). This is a screen, not a predictor.
- 9 further flagged tickets come from the 2026-08-12 catalog-extraction set,
  which was **abandoned unexecuted** (Board entirely ⬜). They contribute zero
  validation either way.

``docs/reference/ticket-breadth.md`` carries the full retroactive table.
kaizen's weekly ``Review rounds /plan`` column is what refines the number — when
that mean moves, re-derive the threshold rather than tuning it to taste.

Exit codes: 0 always, except ``--strict`` with ≥1 flagged ticket → 1.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Calibration constants (provisional — see the CALIBRATION section above) ──
BREADTH_THRESHOLD = 5  # score ≥ this → flagged; RE-DERIVED, see CALIBRATION
# Rounds-per-score-point, MEASURED (not the 1-2 hand-counted class ratio — this
# score over-counts classes; see the docstring). Median 1.0 over n=14 tickets.
ROUNDS_RATIO_LOW = 0.5
ROUNDS_RATIO_HIGH = 1.5
MEASURED_BASIS = (
    "this repo's review ledgers — 4.2 rounds/plan (n=14/22, max 16); "
    "per-ticket receipts n=14 give rounds ~= 1.0 x score (spread 0.3x-1.6x)"
)
# Calibration honesty, printed in the advisory footer so a reader can weigh a
# flag at the point of use. An advisory that overstates itself gets ignored
# wholesale, which is worse than not warning at all.
CALIBRATION_N = 14  # tickets with real per-ticket round receipts
EXPENSIVE_ROUNDS = 4  # "genuinely expensive" (corpus mean is 3.07 rounds)
FLAGS_WITH_RECEIPTS = 4  # flagged tickets whose actual round count is known
FLAG_HITS = 2  # ...of which this many really ran >= EXPENSIVE_ROUNDS
SPEARMAN_RHO = 0.45  # score vs actual rounds, n=14 (Pearson 0.31)

# ── Grammar (kept compatible with check_plan_tickets.py's canonical regexes) ──
PLAN_DIR_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+$")
TICKET_FILE_RE = re.compile(r"^(T\d{2}[a-z]?)-[a-z0-9-]+\.md$")
GIVEN_ROW_RE = re.compile(r"^\s*[-*]\s+(.*\*{0,2}Given\*{0,2}\b.*)$", re.I | re.M)
_FENCE_RE = re.compile(
    r"(?:^[ \t]*(`{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$|```[^`\n]+```)",
    re.M | re.S,
)
_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(\S+)")

# TEST SURFACES — deliberately NOT an independent risk area, and never a split
# target. Tests ship WITH the behaviour they prove: the Behavior Contract
# requires a test per behaviour in the SAME ticket, and watched-fail-first needs
# the test and its code in one changeset. A ticket whose tests live in a
# different ticket cannot be red-on-revert proven, and its Gate would pass while
# proving nothing. Counting `tests/` as a risk area produced exactly that advice
# ("keep scripts/ and peel off tests/") — harmful in every repo this syncs to.
_TEST_DIR_SEGMENTS = frozenset({"tests", "test", "spec", "specs", "__tests__", "testing"})
_TEST_FILE_RE = re.compile(
    r"(?:^|/)(?:test_[^/]+|[^/]+_test|[^/]+\.(?:test|spec)|conftest)\.[a-z0-9]+$", re.I
)

# Governance / fleet-synced surfaces. Mirrors the `governance-sync` files-filter
# in .pre-commit-config.yaml (the hub's real distribution trigger) — kept as a
# literal tuple so this check stays stdlib-only and works in a project repo that
# has no hub tooling. Prefixes end with "/"; exact files do not.
GOVERNANCE_PREFIXES = (
    ".windsurf/rules/",
    ".claude/hooks/",
    "scripts/enforcement/",
    "templates/governance/",
)
GOVERNANCE_FILES = (
    "AGENTS.md",
    "AGENTS-compact.md",
    "CLAUDE.md",
    "agents-fabrik.md",
    "agents-fabrik-core.md",
    "opencode.json",
    ".windsurfrules",
    ".claude/settings.json",
    ".windsurf/hooks.json",
    "scripts/final_gate.py",
    "scripts/fabrik_synced_manifest.py",
    "scripts/sync_enforcement_to_projects.py",
    "scripts/docs_updater.py",
    "scripts/select_rules.py",
    "scripts/review_rubric.py",
)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text)


def _section(text: str, title: str) -> str:
    m = re.search(rf"^##\s+{re.escape(title)}(.*?)(?=^##\s|\Z)", text, re.I | re.M | re.S)
    return m.group(1) if m else ""


def _norm_path(p: str) -> str:
    """Lean normalization: edge backticks, symmetric bold/quote wraps, a trailing
    ``:NN`` citation suffix, a ``./`` prefix. Enough for area attribution — this
    check never uses paths as an ownership predicate, so residue only costs it
    one area, never correctness elsewhere."""
    p = p.strip().strip("`")
    while len(p) >= 4 and p.startswith("**") and p.endswith("**"):
        p = p[2:-2].strip()
    for quote in ('"', "'"):
        if len(p) >= 2 and p.startswith(quote) and p.endswith(quote):
            p = p[1:-1].strip()
    p = re.sub(r":\d+$", "", p).rstrip(":").rstrip(",")
    if p.startswith("./"):
        p = p[2:]
    return p


def _list_paths(section_body: str) -> list[str]:
    out: list[str] = []
    for line in section_body.splitlines():
        m = _BULLET_RE.match(line)
        if m:
            token = _norm_path(m.group(1))
            if token:
                out.append(token)
    return out


_DOCSYNC_ROOT_FILES = {"CHANGELOG.md", "INDEX.md", "PORTS.md", ".env.example"}


def _is_docsync_path(path: str) -> bool:
    """A companion DOC-SYNC surface — the docs the Doc Sync Matrix REQUIRES to
    travel in the same change as the code that invalidates them (CLAUDE.md:
    "any doc a change makes stale ... must be brought current in the SAME
    change"). Counting them as a risk area produced the remedy "peel docs/
    into a separate ticket" — advice that contradicts a HARD governance rule,
    and following it RAISED the flag count 3->4 (01M1DMBS, measured). Same
    treatment as tests: not an area, never a peel target."""
    p = path.removeprefix("./")
    segs = [x for x in p.split("/") if x and x != "."]
    if segs and segs[0] == "docs":
        return True
    return len(segs) == 1 and segs[0] in _DOCSYNC_ROOT_FILES


def _is_test_path(path: str) -> bool:
    """A companion TEST surface — excluded from the risk-class count and never a
    split target (see _TEST_DIR_SEGMENTS). Matches a test directory anywhere in
    the path, or a test-named file anywhere."""
    p = path.removeprefix("./")
    segs = [x for x in p.split("/") if x and x != "."]
    if any(s.lower() in _TEST_DIR_SEGMENTS for s in segs[:-1] or segs):
        return True
    if segs and segs[-1].lower() in _TEST_DIR_SEGMENTS:
        return True
    return bool(_TEST_FILE_RE.search(p))


def _area(path: str) -> str:
    """Top-level source area of a repo-relative path. A root-level file is its
    own area (``<root>``) — a ticket touching CHANGELOG.md plus src/ genuinely
    spans two surfaces."""
    parts = [x for x in path.split("/") if x and x != "."]
    if not parts:
        return "<root>"
    return parts[0] if len(parts) > 1 else "<root>"


def _is_governance(path: str) -> bool:
    # removeprefix, NEVER lstrip("./") — lstrip strips a CHARACTER SET, so
    # `.claude/hooks/x` lost its leading dot and matched nothing. Every dotfile
    # governance surface (.claude/, .windsurf/, .windsurfrules) was invisible.
    p = path.removeprefix("./")
    if p in GOVERNANCE_FILES:
        return True
    return any(p == g.rstrip("/") or p.startswith(g) for g in GOVERNANCE_PREFIXES)


@dataclass
class Breadth:
    tid: str
    path: Path
    areas: list[str] = field(default_factory=list)
    behaviors: int = 0
    mix: bool = False
    gov_paths: list[str] = field(default_factory=list)
    test_areas: int = 0  # companion test surfaces seen but deliberately NOT counted
    docsync_areas: int = 0  # Doc-Sync companion surfaces — travel with the code, never counted
    parse_note: str = ""

    @property
    def score(self) -> int:
        return len(self.areas) + self.behaviors + (1 if self.mix else 0)

    @property
    def flagged(self) -> bool:
        return self.score >= BREADTH_THRESHOLD

    def components(self) -> str:
        areas = ", ".join(self.areas) if self.areas else "none declared"
        tail = f" [+{self.test_areas} test surface(s), not counted]" if self.test_areas else ""
        if self.docsync_areas:
            tail += f" [+{self.docsync_areas} doc-sync surface(s), travel with the code]"
        return (
            f"areas={len(self.areas)} ({areas}){tail} · "
            f"behaviors={self.behaviors} · "
            f"code+governance mix={'yes' if self.mix else 'no'}"
        )

    def split_hint(self) -> str:
        """Concrete surfaces to peel off — never generic advice. A hint that does
        not name a path is a rule, and rules are what this check exists to
        replace. TEST surfaces are never peel targets: they ship with the
        behaviour they prove, or the split destroys red-on-revert provability."""
        bits: list[str] = []
        if len(self.areas) > 1:
            # Keep the FIRST area as the ticket's spine; peel the rest. `docs/`
            # is a legitimate peel (a doc rewrite reviews on its own axis);
            # tests never reach here — they are excluded from `areas` upstream.
            keep, peel = self.areas[0], self.areas[1:]
            bits.append(
                f"keep {keep}/ and peel off {', '.join(f'{a}/' for a in peel)} "
                "into separate tickets (their tests move WITH them — never split "
                "a test from the behaviour it proves)"
            )
        if self.behaviors > 2:
            bits.append(
                f"split the {self.behaviors} Behavior-Contract rows into tickets of <=2 "
                "behaviours each (one review class apiece)"
            )
        if self.mix and self.gov_paths:
            shown = ", ".join(self.gov_paths[:3])
            more = f" (+{len(self.gov_paths) - 3} more)" if len(self.gov_paths) > 3 else ""
            bits.append(
                f"separate the fleet-synced surface ({shown}{more}) from the local code — "
                "a ~46-repo blast radius reviews on its own axis"
            )
        return "; ".join(bits) if bits else "no mechanical split suggestion — review by hand"


def measure_ticket(path: Path) -> Breadth:
    """Parse ONE ticket file into its breadth components. Fails soft: any parse
    problem yields a zero-score Breadth carrying a parse_note, never an
    exception."""
    tid_m = TICKET_FILE_RE.match(path.name)
    tid = tid_m.group(1) if tid_m else path.stem
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        scan = _strip_fences(text)
        touches = _list_paths(_section(scan, "Touches"))
        # Companion TEST and DOC-SYNC surfaces are excluded from EVERY signal:
        # not an area, not the "code" half of the governance mix, never a split
        # target (tests ship with the behaviour they prove; doc-sync rows travel
        # with the code that invalidates them — the Matrix mandates it).
        prod = [p for p in touches if not _is_test_path(p) and not _is_docsync_path(p)]
        test_areas = len({_area(p) for p in touches if _is_test_path(p)})
        docsync_areas = len({_area(p) for p in touches if not _is_test_path(p) and _is_docsync_path(p)})
        areas: list[str] = []
        for p in prod:
            a = _area(p)
            if a not in areas:
                areas.append(a)
        gov_paths = [p for p in prod if _is_governance(p)]
        # Doc-sync companions stay out of AREAS but still count as "local work"
        # for the governance-mix signal — excluding them dropped mix on a
        # governance+docs ticket, the exact blast-radius pairing the signal
        # exists for (review round 1, measured mix=True -> False).
        has_code = any(
            not _is_governance(p)
            for p in touches
            if not _is_test_path(p)
        )
        # A companions-ONLY ticket still touches something — score it as one
        # area rather than zero, but never as a multi-area ticket; label by
        # what it actually holds (a docs-only ticket read "<tests-only>",
        # review round 1).
        if not areas and touches:
            areas = ["<docs-only>"] if docsync_areas and not test_areas else ["<tests-only>"]
        return Breadth(
            tid=tid,
            path=path,
            areas=areas,
            behaviors=len(GIVEN_ROW_RE.findall(_section(scan, "Behavior Contract"))),
            mix=bool(gov_paths) and has_code,
            gov_paths=gov_paths,
            test_areas=test_areas,
            docsync_areas=docsync_areas,
        )
    except Exception as e:  # noqa: BLE001 — fail SOFT by contract; never red a gate
        return Breadth(tid=tid, path=path, parse_note=f"unparseable ({e!r}) — skipped")


def measure_plan_dir(plan_dir: Path) -> list[Breadth]:
    """Every ticket file in a dated plan-set directory, ID-sorted."""
    out: list[Breadth] = []
    try:
        files = sorted(plan_dir.glob("*.md"))
    except OSError as e:
        print(f"NOTE: ticket_breadth skipped {plan_dir} ({e!r})")
        return out
    for f in files:
        if TICKET_FILE_RE.match(f.name):
            out.append(measure_ticket(f))
    return out


def _is_plans_layout(plan_dir: Path) -> bool:
    parts = plan_dir.parts
    return len(parts) >= 4 and parts[-4:-1] == ("docs", "development", "plans")


def _is_archived(plan_dir: Path) -> bool:
    parts = plan_dir.parts
    return len(parts) >= 5 and parts[-5:-1] == ("docs", "development", "plans", "archived")


def _plan_dirs_from_paths(root: Path, paths: set[str]) -> set[Path]:
    dirs: set[Path] = set()
    for c in paths:
        p = Path(c)
        if len(p.parts) >= 4 and p.parts[:3] == ("docs", "development", "plans"):
            if PLAN_DIR_NAME_RE.match(p.parts[3]):
                dirs.add(root / "docs" / "development" / "plans" / p.parts[3])
    return dirs


def discover_dirs(root: Path, rev_range: str | None = None) -> list[Path]:
    """Plan sets touched in the working tree (default) or in ``rev_range``.
    Any git failure → NOTE + empty (fail soft, never a red gate)."""
    cmds: list[list[str]] = []
    if rev_range:
        cmds.append(["diff", "--name-only", rev_range])
    else:
        cmds.append(["diff", "--name-only"])
        cmds.append(["diff", "--name-only", "--cached"])
        cmds.append(["ls-files", "--others", "--exclude-standard"])
    changed: set[str] = set()
    for args in cmds:
        try:
            proc = subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True, timeout=15
            )
        except Exception as e:  # noqa: BLE001 — fail soft
            print(f"NOTE: ticket_breadth discovery skipped (git error: {e!r})")
            return []
        if proc.returncode != 0:
            print(f"NOTE: ticket_breadth discovery: `git {' '.join(args)}` exit {proc.returncode}")
            continue
        changed.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
    return sorted(d for d in _plan_dirs_from_paths(root, changed) if d.is_dir())


def all_plan_dirs(root: Path, include_archived: bool = True) -> list[Path]:
    """Every dated plan-set directory in the repo — the retroactive-calibration
    sweep. Archived sets included by default (they are the measured history)."""
    base = root / "docs" / "development" / "plans"
    if not base.is_dir():
        return []
    found: list[Path] = []
    for d in sorted(base.iterdir()):
        if d.is_dir() and PLAN_DIR_NAME_RE.match(d.name):
            found.append(d)
    archived = base / "archived"
    if include_archived and archived.is_dir():
        for d in sorted(archived.iterdir()):
            if d.is_dir() and PLAN_DIR_NAME_RE.match(d.name):
                found.append(d)
    return found


def render(results: list[Breadth]) -> list[str]:
    """Actionable warning lines for the flagged tickets. Empty when none —
    silence IS the pass state."""
    lines: list[str] = []
    for b in results:
        if b.parse_note:
            lines.append(f"NOTE: ticket_breadth {b.path}: {b.parse_note}")
    flagged = [b for b in results if not b.parse_note and b.flagged]
    if not flagged:
        return lines
    graded = [b for b in results if not b.parse_note]
    unparsed = len(results) - len(graded)
    # The count AND its population, at BOTH ends. This block used to open with the numerator
    # alone and close with per-ticket detail, so `check_ticket_breadth.py | tail -60` showed
    # findings with no denominator — the exact bound CLAUDE.md's denominator-honesty rule warns
    # about, built into the output ORDER. It already produced a wrong number in a real review
    # artifact: a reviewer read "16 of 24" off a tailed run when the figure was 20 of 33
    # (intel, 01M1PYS0Y7AZ9W2WS8PPYHT0WK #1, corrected at e6f284e6).
    headline = (
        f"TICKET BREADTH — {len(flagged)} of {len(graded)} ticket(s) graded score "
        f"≥ {BREADTH_THRESHOLD} independent risk classes (advisory)"
        + (f"; {unparsed} unparseable, NOT graded" if unparsed else "")
    )
    lines.append(f"⚠ {headline}")
    for b in sorted(flagged, key=lambda x: (-x.score, x.tid)):
        low = max(1, round(b.score * ROUNDS_RATIO_LOW))
        high = max(low, round(b.score * ROUNDS_RATIO_HIGH))
        lines.append(f"  {b.tid} ({b.path}): score {b.score}")
        lines.append(f"    components: {b.components()}")
        lines.append(f"    predicted review cost: ~{low}-{high} rounds (basis: {MEASURED_BASIS})")
        lines.append(f"    split: {b.split_hint()}")
    lines.append(
        f"  Calibration honesty: in the n={CALIBRATION_N} retroactive set, {FLAG_HITS} of "
        f"{FLAGS_WITH_RECEIPTS} flags with round receipts matched a ticket that actually ran "
        f">={EXPENSIVE_ROUNDS} rounds (score-vs-rounds Spearman rho={SPEARMAN_RHO}). "
        "Treat a flag as a prompt to LOOK, not a verdict."
    )
    lines.append(
        "  Advisory only — the threshold is provisional (docs/reference/ticket-breadth.md). "
        "Narrowing is the operator's call."
    )
    lines.append(f"⚠ {headline}")  # repeated LAST so a tailed read carries its own denominator
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ticket-breadth advisory (see module docstring).")
    parser.add_argument("--plan-dir", type=Path, default=None, help="one plan-set directory")
    parser.add_argument("--range", dest="rev_range", default=None, help="git range, e.g. A..B")
    parser.add_argument("--all", action="store_true", help="every plan set (calibration sweep)")
    parser.add_argument("--strict", action="store_true", help="exit 1 when any ticket is flagged")
    parser.add_argument("--table", action="store_true", help="one row per ticket, flagged or not")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    root = args.project_root.resolve()

    if args.plan_dir:
        target = args.plan_dir.resolve()
        if not target.is_dir() or not PLAN_DIR_NAME_RE.match(target.name):
            # Fail SOFT even here: a bad path is never worth reding a gate.
            print(f"NOTE: ticket_breadth: {args.plan_dir} is not a dated plan-set directory")
            return 0
        dirs = [target]
    elif args.all:
        dirs = all_plan_dirs(root)
    else:
        dirs = [d for d in discover_dirs(root, args.rev_range) if not _is_archived(d)]

    if not dirs:
        return 0  # silent — the fleet-wide inert case

    results: list[Breadth] = []
    for d in dirs:
        results.extend(measure_plan_dir(d))
    if not results:
        return 0

    if args.table:
        print(
            f"| Ticket | Plan set | areas | behaviors | mix | score | flagged (≥{BREADTH_THRESHOLD}) |"
        )
        print("|---|---|---:|---:|:--:|---:|:--:|")
        for b in results:
            if b.parse_note:
                print(f"| {b.tid} | {b.path.parent.name} | — | — | — | — | parse error |")
                continue
            print(
                f"| {b.tid} | {b.path.parent.name} | {len(b.areas)} | {b.behaviors} | "
                f"{'yes' if b.mix else 'no'} | {b.score} | {'YES' if b.flagged else 'no'} |"
            )

    for line in render(results):
        print(line)

    if args.strict and any(b.flagged for b in results if not b.parse_note):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
