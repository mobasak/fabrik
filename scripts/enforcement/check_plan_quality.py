# AFTER-EDIT: tests/enforcement/test_plan_shape_gates.py | commands/_sources/fabrik-plan-after-chat.md
"""Check plan document quality — shape-classified required sections.

Classification precedence (ordered — a file matching an earlier shape is never
reclassified by a later rule):

0. A file ``check_plans`` would ERROR (invalid name / loose ticket) is SKIPPED here —
   the naming error stands alone.
1. **Ticket file** (canonical ``T\\d{2}[a-z]?-<slug>.md`` inside a dated plan dir):
   requires the ticket field contract; any ``Status:`` line is an ERROR (ticket state
   lives ONLY in the spine's Ticket Board). While the sibling spine is
   ``Status: DRAFT``, ticket findings downgrade to WARN (an in-flight draft set must
   not red sibling sessions' gates on shared master).
2. **Modern monolith or spine** (a modern-vocabulary ``Status:`` line — DRAFT |
   CONVERGED | IN-PROGRESS | EXECUTED | BLOCKED, bold-or-plain): requires
   ``## Context Ledger`` + ``## File Scope`` + ``## Evidence``; a spine (detected by
   ``## Ticket Board``) additionally requires ``## Merge Order`` + ``## Interfaces`` +
   ``## Global Constraints`` + ``## Behavior Contract``.
3. **Grandfather fallback** (no ``Status:`` line, or the legacy vocabulary): a single
   WARN — pre-pipeline plans keep passing unchanged (content-based: staging state is
   NOT a guard; validate_conventions checks unstaged+staged+untracked alike).

``plans/archived/**`` is exempt entirely.
"""

import re
from pathlib import Path

from .check_plans import PLAN_DIR_NAME_RE, TICKET_NAME_RE
from .check_plans import check_file as _check_plans_naming
from .validate_conventions import CheckResult, Severity

# Check project's own plans directory
PLAN_DIR = Path.cwd() / "docs" / "development" / "plans"

# Modern status vocabulary. Colon MANDATORY, bold-or-plain with the colon inside
# OR outside the bold (`Status:`, `**Status:**`, `**Status**:`) — never bare prose
# like `- Status page` (the colon requirement is what keeps ordinary sentences
# from matching). Keep the token shape in lockstep with check_convergence.py /
# check_plan_tickets.py / docs_updater.py.
MODERN_STATUS_RE = re.compile(
    r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*(?:✅[^\S\n]*)?"
    r"\*{0,2}[^\S\n]*(DRAFT|PLANNED|CONVERGED|IN-PROGRESS|EXECUTED|BLOCKED)\b",
    re.I | re.M,
)
# Any Status: line at all (the ticket ban) — colon mandatory AND same-line value
# ([^\S\n], never \s — \s crosses the newline and matches a bare "Status:" label
# above an indented list), so prose about statuses never trips it.
ANY_STATUS_RE = re.compile(r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\S", re.M)

# Required sections: modern monolith or spine (case-insensitive — the pre-rewrite
# gate tolerated any heading case; keep that tolerance).
PILLAR_SECTIONS = [
    ("Context Ledger", re.compile(r"^##\s+Context Ledger\b", re.I | re.M)),
    ("File Scope", re.compile(r"^##\s+File Scope\b", re.I | re.M)),
    ("Evidence", re.compile(r"^##\s+Evidence\b", re.I | re.M)),
]
# The spine sections whose contents BIND execution. `/fabrik-plan-after-chat` mandates
# `## Execution Discipline`; `## Global Constraints` is accepted as the sibling that predates it.
_BINDING_SECTION_RE = re.compile(
    r"^##\s+(?:Execution Discipline|Global Constraints)\b.*?(?=^##\s|\Z)", re.I | re.M | re.S
)
SPINE_MARKER_RE = re.compile(r"^##\s+Ticket Board\b", re.I | re.M)
SPINE_SECTIONS = [
    ("Merge Order", re.compile(r"^##\s+Merge Order\b", re.I | re.M)),
    ("Interfaces", re.compile(r"^##\s+Interfaces\b", re.I | re.M)),
    ("Global Constraints", re.compile(r"^##\s+Global Constraints\b", re.I | re.M)),
    ("Behavior Contract", re.compile(r"^##\s+Behavior Contract\b", re.I | re.M)),
]

# Ticket field contract (the ettw-06 fields, per the spine+ticket plan grammar).
# Field lines tolerate a bullet prefix (the same tolerance the Board/Order/
# Serialized/Given regexes carry — bulleted metadata is natural markdown).
# NO `>` tolerance — blockquotes are quoted content (parity with check_plan_tickets._F).
_F = r"^\s*(?:[-*]\s+)?"
# Blockquoted lines are QUOTED content for spine-status DETERMINATION only:
# there, parsing more Status lines produces FEWER findings (the DRAFT/PLANNED
# downgrade — fail-open), so a `> Status: DRAFT` example must be invisible.
# The ticket-Status BAN keeps the full scan — a quoted ticket Status still
# draws the ban (fail-closed). Parity with check_plan_tickets._BLOCKQUOTE_RE.
_BLOCKQUOTE_RE = re.compile(r"^[ \t]*>.*$", re.M)
TICKET_FIELDS = [
    ("Scope", re.compile(r"^##\s+Scope\b", re.I | re.M)),
    ("Scope DO-NOT", re.compile(r"\bDO[- ]?NOT\b", re.I)),
    ("Depends", re.compile(_F + r"\*{0,2}Depends\*{0,2}[^\S\n]*:", re.I | re.M)),
    ("Parallel", re.compile(_F + r"\*{0,2}Parallel\*{0,2}[^\S\n]*:", re.I | re.M)),
    ("Complexity", re.compile(_F + r"\*{0,2}Complexity\*{0,2}[^\S\n]*:", re.I | re.M)),
    ("Docs", re.compile(_F + r"\*{0,2}Docs\*{0,2}[^\S\n]*:", re.I | re.M)),
    ("Touches", re.compile(r"^##\s+Touches\b", re.I | re.M)),
    ("Behavior Contract", re.compile(r"^##\s+Behavior Contract\b", re.I | re.M)),
    ("Context Files", re.compile(r"^##\s+Context Files\b", re.I | re.M)),
    ("Gate", re.compile(_F + r"\*{0,2}Gate\*{0,2}[^\S\n]*:", re.I | re.M)),
]

# Fenced code blocks are QUOTED content — a ticket citing `Status: 200 OK` in an
# API example must not trip the Status ban.
_FENCE_RE = re.compile(
    # PARSING CONTRACT (recorded, review round 9): fences are BALANCED backtick
    # fences — a 3+-backtick opener closed by an EQUAL-length line-start closer —
    # plus inline single-line ```…``` quotes. Out of contract (documented, not
    # chased): tilde fences, over-long closers, and unpaired line-start fence
    # PAIRS — the emitting commands write balanced 3-backtick fences and quote
    # templates with 4-backtick outers, both in-contract; no live fleet file
    # violates this (verified 2026-08-05).
    # Line-anchored BLOCK fences + inline single-line fences. NEVER a bare
    # ```.*?``` — an unpaired backtick in prose would pair with the NEXT
    # block's opener and swallow real document body (live fleet regression:
    # calendar-orchestration-engine 2026-07-25 plan lost ## File Scope).
    r"(?:^[ \t]*(`{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$|```[^`\n]+```)",
    re.M | re.S,
)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text)


def _is_archived(file_path: Path) -> bool:
    try:
        return "archived" in file_path.relative_to(PLAN_DIR).parts
    except ValueError:
        return False


def _sibling_spine_is_draft(file_path: Path) -> bool:
    """True when the ticket's sibling spine is Status: DRAFT — or ABSENT (a set
    being authored ticket-first is the most draft-like state there is; hard-ERRORing
    it would defeat the sibling-session protection this branch exists for)."""
    spine = file_path.parent / f"{file_path.parent.name}.md"
    if not spine.is_file():
        return True
    try:
        scan = _strip_fences(spine.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return True
    scan = _BLOCKQUOTE_RE.sub("", scan)  # quoted Status examples never downgrade
    m = MODERN_STATUS_RE.search(scan)
    if m:
        return m.group(1).upper() in ("DRAFT", "PLANNED")
    # ABSENT Status = mid-authoring (draft-like). PRESENT-but-unrecognized
    # (`Status: COMPLETE`, a typo) FAILS CLOSED — one bad token must not silence
    # the ticket contract (mirrors check_plan_tickets' UNRECOGNIZED branch).
    return not ANY_STATUS_RE.search(scan)


def _check_ticket(file_path: Path, content: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    severity = Severity.WARN if _sibling_spine_is_draft(file_path) else Severity.ERROR
    scan = _strip_fences(content)  # one scan policy — a quoted template is not a contract
    for field_name, pattern in TICKET_FIELDS:
        if not pattern.search(scan):
            results.append(
                CheckResult(
                    check_name="plan_quality",
                    severity=severity,
                    message=f"Ticket missing required field: {field_name}",
                    file_path=str(file_path),
                    fix_hint=f"Add '{field_name}' per the spine+ticket contract",
                )
            )
    if ANY_STATUS_RE.search(_strip_fences(content)):
        results.append(
            CheckResult(
                check_name="plan_quality",
                severity=severity,
                message="Ticket carries a Status: line — ticket state lives ONLY in the spine Board",
                file_path=str(file_path),
                fix_hint="Delete the Status: line; flip the Ticket Board row instead",
            )
        )
    return results


def _check_modern(file_path: Path, content: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    # ONE scan policy: everything on fence-stripped text — a quoted
    # `## Ticket Board` example must not demand spine sections, and quoted
    # pillar headings must not SATISFY the pillar requirement.
    scan = _strip_fences(content)
    # A DRAFT/PLANNED plan is mid-authoring on shared master — missing sections
    # are WARN (sibling-session protection, matching every other downgrade path);
    # full ERROR from CONVERGED onward (the convergence flip enforces regardless).
    m = MODERN_STATUS_RE.search(_BLOCKQUOTE_RE.sub("", scan))  # quoted → never own status
    severity = (
        Severity.WARN if (m and m.group(1).upper() in ("DRAFT", "PLANNED")) else Severity.ERROR
    )
    required = list(PILLAR_SECTIONS)
    if SPINE_MARKER_RE.search(scan):
        required += SPINE_SECTIONS
    for section_name, pattern in required:
        if not pattern.search(scan):
            results.append(
                CheckResult(
                    check_name="plan_quality",
                    severity=severity,
                    message=f"Missing required section: {section_name}",
                    file_path=str(file_path),
                    fix_hint=f"Add '## {section_name}' to the plan document",
                )
            )
    if SPINE_MARKER_RE.search(scan):
        results += _check_spine_execution_pillars(scan, file_path)
    return results


# The three pillars /fabrik-plan-after-chat § Phase 3 mandates. A MONOLITH hangs them on its
# per-phase steps; a SET has no `## Phase` headings, so they have nowhere to live but the spine —
# and the ticket-set path used to map them onto per-ticket `Complexity:`/`Parallel:` fields and
# "the dispatcher owns the review floor at runtime", which deleted them from the artifact
# entirely. Live defect 2026-08-10: a 14-ticket CONVERGED set contained none of the three, so
# neither the operator nor an auditing agent could see that any ticket would be reviewed.
#
# ⚠️ WHAT THIS CAN AND CANNOT PROVE (own review finding, recorded rather than overstated): these are
# KEYWORD-PRESENCE heuristics, not semantic checks. Probed live, a NEGATED mandate ("Do NOT run
# /fabrik-review per ticket") satisfies pattern 1, as does a look-alike command name. So a clean run
# means "the spine talks about all three pillars", NEVER "the spine mandates them correctly". The
# real enforcement is /fabrik-plan-review, whose reviewing agent reads the spine and treats a set
# missing the three as a finding to FIX; this check is only the mechanical floor that catches the
# case that actually happened — a spine that says NOTHING about them at all.
SPINE_PILLAR_PATTERNS = [
    (
        "per-ticket /fabrik-review floor",
        # Line-scoped: a narrative mention ("this set was converged by /fabrik-plan-review") must
        # NOT satisfy the pillar. The mandate names /fabrik-review AND the unit it binds to.
        # `(?![\w-])` stops a longer command name (`/fabrik-review-lite`) from standing in for it.
        re.compile(
            r"^(?=.*/fabrik-review(?![\w-]))(?=.*\b(?:ticket|merge|boundary)\b).*$", re.I | re.M
        ),
        "state on the spine: every ticket runs /fabrik-review on its changed surface to a "
        "coverage-adjudicated exit BEFORE its merge",
    ),
    (
        "pool-default dispatch policy",
        # Deliberately GENEROUS. A gate that cries wolf on a compliant plan gets ignored, and every
        # one of these MISSED before (native review, reproduced): "the OpenRouter pool is the
        # default worker for the gradeable finders", "pool by default (`pick_models`)", "Use
        # `fanout` with task_type='review'" — each a correct statement of the policy.
        re.compile(
            r"\bpool[- ]default\b"
            r"|\bfanout\b"
            r"|\bpick_models\b"
            r"|\bpool\b[^.\n]{0,40}\bdefault\b"
            r"|\bdefault\b[^.\n]{0,40}\bpool\b",
            re.I,
        ),
        "state on the spine: pool-default (fanout(task_type, …)) for gradeable work, native "
        "added on top for GUI / high-risk / decide-merge",
    ),
    (
        "parallelism + where results merge",
        # Same reason: "may run concurrently; findings are deduped at the Integration ticket" and
        # "**Parallel fan-out points:** T01 ‖ T05 ‖ T06 (disjoint trees)" both MISSED, and both
        # state exactly what this pillar asks for.
        re.compile(
            r"\bmerges?/dedupes?\b"
            r"|\bdedupe[sd]?\b"
            # The CONCEPT (a separator is required) — never the `fanout()` function NAME, which is
            # a DISPATCH term: without the separator, a pool-default line satisfied the
            # parallelism pillar too, so a spine stating 2 of 3 looked complete.
            r"|\bfan[- ]out\b"
            r"|\bconcurrent(?:ly)?\b"
            r"|\bin parallel\b"
            r"|\bparallel\b[^.\n]{0,40}\b(?:wave|point|set|track)s?\b"
            r"|\bwhere\b[^.\n]{0,40}\bmerge",
            re.I,
        ),
        "state on the spine: which tickets fan out concurrently and WHERE their results "
        "merge/dedupe (Merge Order gives sequencing, not fan-out semantics)",
    ),
]


def _check_spine_execution_pillars(scan: str, file_path: Path) -> list[CheckResult]:
    """WARN when a spine states none of Phase 3's three execution pillars.

    Advisory on purpose: this landed while live plan sets already existed in sibling repos, and a
    hard ERROR would red another agent's in-flight gate for a rule that did not exist when their
    plan was written. The binding enforcement is /fabrik-plan-after-chat (emits them) and
    /fabrik-plan-review (a set missing them is a finding to FIX); this is the mechanical backstop.
    """
    # Blockquoted lines are QUOTED content, not the spine's own mandate — same convention the
    # ticket-Status determination uses above. Without this, a quoted counter-example
    # ("> Note: this ticket bypasses /fabrik-review due to the boundary of the change") SATISFIES
    # the pillar it contradicts (pool finder, reproduced).
    unquoted = _BLOCKQUOTE_RE.sub("", scan)
    # Scan ONLY the spine's binding execution section(s). Scanning the whole document meant any
    # narrative mention satisfied a pillar — a live spine passed because its header asked the
    # QUESTION "does each ticket get a /fabrik-review to a no-op?" (native review, reproduced).
    # A pillar is a MANDATE, so it has to live where mandates live. No binding section at all ⇒
    # nothing is stated ⇒ all three are missing, which is exactly the defect case.
    binding = "".join(m.group(0) for m in _BINDING_SECTION_RE.finditer(unquoted))
    missing = [
        (name, hint) for name, pattern, hint in SPINE_PILLAR_PATTERNS if not pattern.search(binding)
    ]
    if not missing:
        return []
    return [
        CheckResult(
            check_name="plan_quality",
            severity=Severity.WARN,
            message=(
                "Spine states none of / not all of the execution pillars: "
                + ", ".join(n for n, _ in missing)
                + " — a ticket set has no phase boundaries, so the spine is the only place these "
                "can live; without them nobody reading the plan can see that tickets get reviewed"
            ),
            file_path=str(file_path),
            fix_hint="; ".join(h for _, h in missing),
        )
    ]


def check_file(file_path: Path) -> list[CheckResult]:
    """Validate a plans-dir markdown file per its shape (see module docstring)."""
    if file_path.suffix != ".md":
        return []
    # validate_conventions feeds RELATIVE paths; PLAN_DIR is absolute — resolve or
    # this gate silently no-ops in the production caller (the pre-rewrite bug).
    file_path = file_path.resolve()
    try:
        if not file_path.is_relative_to(PLAN_DIR):
            return []
    except ValueError:
        return []
    if file_path.name.lower() in ("readme.md", "index.md", "plans.md"):
        return []
    if _is_archived(file_path):
        return []
    # Precedence 0: a naming-invalid file is check_plans' finding, not ours.
    if any(r.severity.value == "error" for r in _check_plans_naming(file_path)):
        return []

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [
            CheckResult(
                check_name="plan_quality",
                severity=Severity.ERROR,
                message=f"Cannot read plan file: {e}",
                file_path=str(file_path),
            )
        ]

    # Precedence 1: ticket shape.
    if TICKET_NAME_RE.match(file_path.name) and PLAN_DIR_NAME_RE.match(file_path.parent.name):
        return _check_ticket(file_path, content)

    # Precedence 2: modern monolith or spine. A modern-vocabulary Status ALONE is
    # not enough — pre-pipeline plans that say `Status: CONVERGED`/`EXECUTED` must
    # not be hard-ERRORed for pillars their era never had (June-era plans carry
    # `## Evidence` but predate Context Ledger / File Scope). Classify modern only
    # when the file carries at least one of the PIPELINE-era pillars (Context
    # Ledger or File Scope — what /fabrik-plan-after-chat emits); everything else
    # is grandfathered to a WARN. The CONVERGED/EXECUTED claim gates in
    # check_convergence still enforce evidence on NEW claims regardless.
    scan = _strip_fences(content)  # a fenced Status/section example is quoted, not claimed
    pipeline_pillars = [pat for name, pat in PILLAR_SECTIONS if name != "Evidence"]
    is_spine_shape = bool(SPINE_MARKER_RE.search(scan)) or file_path.stem == file_path.parent.name
    # Deliberately NOT blockquote-stripped: classification is fail-CLOSED — a
    # quoted Status pulls the file INTO the modern contract (more checking);
    # stripping here would let a monolith escape it. Only the severity read
    # inside _check_modern strips (there, parsing more downgrades — fail-open).
    if MODERN_STATUS_RE.search(scan) and (
        any(pat.search(scan) for pat in pipeline_pillars) or is_spine_shape
    ):
        # A SPINE (Ticket Board present, or stem==dir) is ALWAYS held to the
        # modern contract — the worse the spine, the louder the gate, never
        # quieter (a pillar-less CONVERGED spine must not grandfather to WARN).
        return _check_modern(file_path, content)

    # Precedence 3: grandfather.
    return [
        CheckResult(
            check_name="plan_quality",
            severity=Severity.WARN,
            message="Legacy plan (no modern Status: line)",
            file_path=str(file_path),
            fix_hint="Adopt 'Status: DRAFT' + the modern pillars to enter the pipeline",
        )
    ]
