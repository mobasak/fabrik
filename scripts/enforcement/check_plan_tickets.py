#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_plan_tickets.py, tests/enforcement/test_plan_tickets_epic_scope.py, commands/_sources/fabrik-plan-after-chat.md, commands/_sources/fabrik-plan-review.md, commands/_sources/fabrik-execute-plan.md, scripts/final_gate.py | none
"""Spine↔ticket plan-set contract gate (the spine+ticket plan shape).

Fires ONLY for files inside a dated plan directory
(``docs/development/plans/YYYY-MM-DD-plan-<slug>/``); monolith plans never enter it;
``plans/archived/<dated-dir>/`` is exempt (the whole-directory archive move must
never re-enter this gate — detected structurally as ``…/plans/archived/<dir>``,
NEVER by scanning absolute-path parts, so a repo living under a directory named
``archived`` is unaffected).

Checks (per the 2026-08-04 spine-ticket plan, the canonical grammar):

- **Structure:** a same-stem spine exists; Ticket-Board rows ↔ ticket files 1:1
  (join key: the ``T\\d{2}[a-z]?`` ID from the filename prefix vs the Board-row ID
  token, Board-section-scoped); every ``Depends:`` target exists; the graph is
  acyclic; ``## Merge Order`` is a topological sort of Depends; exactly one
  ``Integration: true`` ticket, last in Merge Order; the spine
  ``## Behavior Contract`` roll-up equals the union of ticket G/W/T rows; a
  duplicate Board row for one ID is an ERROR (the last row would silently mask
  the real state).
- **Ownership:** Touches are the WRITE set — two tickets whose Touches entries
  OVERLAP (same path, or a directory entry covering another ticket's path) is an
  ERROR unless a Depends path connects them or a ``Serialized:`` row names the
  path; union(Touches) ⊆ spine File Scope. Per-plan territory: own-stem REVIEW
  receipts are the only metadata Touches a ticket may own — the whole
  ``docs/development/plans/`` tree (own spine/tickets included) and the plan
  lock are the ORCHESTRATOR's write surface (dedicated ERRORs); governance
  surfaces (five files + the legacy lowercase lessons alias) never in Touches
  AND never in File Scope (dedicated ERROR — File Scope builds the lock); glob,
  out-of-repo (absolute/~/..), repo-root ``.`` and RESIDUE tokens (quote/
  backtick/separator/colon leftovers; ``path:NN`` citations collapse to the
  path first) are ERRORs on both surfaces; a ticket with no parseable
  ``Complexity:`` is an ERROR at cli/flip.
- **Epic containment** (only when the spine carries an ``Epic:
  docs/development/epics/<file>`` header — an epic-born plan): every ticket's Touches AND
  every spine File Scope entry must lie inside that epic's frontmatter ``owned_paths``
  (spec § Chain consolidation (e): Touches ⊆ File Scope ⊆ ``owned_paths``; the File-Scope
  link is what stops a spine widening past its epic and minting a wider lock). The epic
  side is GLOB-aware (``_glob_covers``, never the literal ``_covered_by``); an
  unresolvable header, or an epic with no ``owned_paths``, is an ERROR naming the path.
  A spine with no ``Epic:`` line is untouched.
- **Routing cross-check:** a pool-tier ticket (Complexity simple/complex) whose
  Touches match the never-route set is an ERROR (``.env.example`` is exempt — a
  routine Doc-Sync file, not a secret); an Integration ticket on a bare-token
  pool tier is an ERROR (receipts run native).
- **Grounding floor:** every non-Integration ticket carries ≥1 ``path:line``.
- **Sizing:** READ budget ≤ READ_BUDGET_BYTES; ≤8 behaviors and ≤3 Gate lines are
  ALWAYS WARN; ``Integration: true`` exempt from all three. Only the READ budget
  takes the invocation-context severity: cli/flip = ERROR; the gate path = WARN
  while the spine is DRAFT, IN-PROGRESS or EXECUTED (a merged set cannot be re-split). (validate_conventions exempts this
  check's WARNs from --strict promotion — they are designed advisories.)
- **Board-staleness:** only when this plan's lock carries ``baseline_commit``.
  One bulk ``git log --first-parent -m --name-only`` over the window (merge
  commits diffed vs their first parent — orchestrator squash/merge commits are
  exactly the ones that must not escape): a commit touching a ticket's Touches
  without that ticket's own ``Agent-Task: T<id>`` trailer is a WARN
  (sibling-tolerant — the acceptance review enforces it); a trailer
  commit whose Board row is still ⬜ (never flipped) is an ERROR. Sanctioned
  back-flips (✅→🔵/🔴) are compliant states. Any git error → NOTE + skip.

Deliberate design decisions (do not re-raise): enforcement is claim-transition
-scoped via check_convergence (a post-settlement evidence strip is out of the
single-operator threat model); a leading-pipe-less GFM Board table is out of
scope (the emitting command always writes leading pipes).

Calibration: READ_BUDGET_BYTES ships at 262144; the next plan touching this file
processes accumulated SIZING DEFECT Evidence rows and adjusts the constant.

Exit codes (CLI): 0 = pass/warn, 1 = any ERROR (or an invalid --plan-dir).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import cast

try:
    from .check_convergence import PROOF
    from .validate_conventions import CheckResult, Severity
except ImportError:  # direct-script invocation (python scripts/enforcement/…py)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.enforcement.check_convergence import PROOF
    from scripts.enforcement.validate_conventions import CheckResult, Severity

READ_BUDGET_BYTES = 262144  # recalibrated from orchestrator-logged SIZING DEFECT rows
# The FROZEN 2-contract artifacts are MANDATORY reading for any ticket that touches their surface —
# the commands require citing them, and /fabrik-flows, /fabrik-ui-design and /fabrik-data-contract
# all push them toward completeness. Counting them against a TICKET's budget measures the contract's
# size, not the ticket's scope, and the two move in opposite directions: the better the contracts
# get, the smaller every ticket is allowed to be. Measured 2026-08-28 (transdoc): ui-design 163292 +
# flows 65312 + data-contract 81827 = 310431 = 118% of the whole budget, so a GUI ticket citing its
# own spec was over before naming a single source file — and Status: EXECUTED became unreachable for
# a 14-ticket plan that was fully merged, reviewed and green. Exempting can only LOWER a reported
# total, so this never reddens a plan that passes today.
BUDGET_EXEMPT_READS = frozenset(
    {"docs/ui-design.md", "docs/flows.md", "docs/data-contract.md", "docs/design-system.md"}
)

# GENERATED BUILD ARTIFACTS — a WRITE, not a read. The budget asks "how many bytes must a
# coder hold in context"; a file produced by a command and committed answers a different
# question. Measured 2026-08-28 (transdoc 01M14A49ZN): openapi.json was 161,606 B = 62% of
# one ticket's entire measured read-set, and `uv.lock` at 288,726 B exceeds the WHOLE
# 262,144 budget on its own — while no agent reads either.
#
# ⚠️ WHY A SIGNATURE AND NOT THE GENERIC DETECTOR transdoc also offered. Their alternative
# was "a Touches entry not cited in Context Files", and they explicitly asked to be told if
# it was another wallpaper case. It is worse than that. Measured across 266 real tickets in
# 15 repos: it would exempt 1045 of 1315 Touches entries (79.5%) — 100% in one repo —
# because Touches ("files this ticket CHANGES") and Context Files ("files it READS") are
# near-disjoint BY CONSTRUCTION. That does not narrow the budget, it deletes it. The same
# sweep measured this signature at 6 entries. Narrow by measurement, not by intuition.
#
# Keep this list to artifacts whose name IS the proof of generation. An authored file that
# merely happens to be large is exactly what the budget exists to catch.
_GENERATED_NAMES = frozenset(
    {
        "openapi.json",  # FastAPI wire contract, regenerated from the app
        "package-lock.json",
        "uv.lock",
        "poetry.lock",
        "yarn.lock",
        "pnpm-lock.yaml",
    }
)


def _is_generated_artifact(path: str) -> bool:
    """True for a committed build output — regenerated by a command, never read by hand."""
    p = PurePosixPath(path.rstrip("/"))
    if p.name in _GENERATED_NAMES:
        return True
    # Compiled/minified outputs: the extension is the proof, and no author edits them.
    return p.name.endswith((".pyc", ".min.js", ".min.css")) or "__pycache__" in p.parts


MAX_BEHAVIORS = 8
MAX_GATES = 3

# Canonical grammar regexes — keep byte-identical with check_convergence.py /
# check_plans.py / check_plan_quality.py / check_test_proposal.py / docs_updater.py
# (single-definition rule; a future consolidation imports from ONE module).
PLAN_DIR_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+$")
TICKET_FILE_RE = re.compile(r"^(T\d{2}[a-z]?)-[a-z0-9-]+\.md$")
BOARD_SECTION_RE = re.compile(r"^##\s+Ticket Board\b(.*?)(?=^##\s|\Z)", re.I | re.M | re.S)
# Board rows tolerate a bold-wrapped ID cell (| **T01** | …).
BOARD_ROW_RE = re.compile(r"^\|\s*\**\s*(T\d{2}[a-z]?)\b", re.M)
MERGE_ORDER_SECTION_RE = re.compile(r"^##\s+Merge Order\b(.*?)(?=^##\s|\Z)", re.I | re.M | re.S)
# Order lines tolerate `1.`/`1)`/bullets and a bold-wrapped ID (same tolerance
# family as the Board/Serialized/Given regexes — silent format intolerance
# disables the topological + Integration-last checks with zero signal).
ORDER_LINE_RE = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+\**\s*(T\d{2}[a-z]?)\**\s*$", re.M)
# Path — IDs separator tolerates em-dash, en-dash, or 1-2 hyphens; indentable.
# Bold-, bullet- AND number-tolerant like ORDER_LINE_RE — a `**Serialized:**`
# label, a `- ` bullet or a `3. ` numbered prefix must not silently void the
# licence row. NO `>` blockquote tolerance (family doctrine — quoted examples
# never parse; here a quoted parse would DISABLE the collision guard), and
# case-insensitive like every sibling.
SERIALIZED_LINE_RE = re.compile(
    r"^\s*(?:(?:\d+[.)]|[-*])\s+)?\*{0,2}Serialized\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*"
    r"(\S+)\s*[—–-]{1,2}\s*(.+)$",
    re.I | re.M,
)
# Status token: colon MANDATORY + same-line value ([^\S\n], never \s — \s crosses
# the newline). Bold-or-plain, colon inside or outside the bold.
STATUS_RE = re.compile(
    r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*(?:✅[^\S\n]*)?"
    r"\*{0,2}[^\S\n]*(DRAFT|PLANNED|CONVERGED|IN-PROGRESS|EXECUTED|BLOCKED)\b",
    re.I | re.M,
)
# PLANNED is DRAFT's sanctioned synonym (fabrik-plan-after-chat Phase 4).
_DRAFT_LIKE = ("DRAFT", "PLANNED", "")
# G/W/T rows: indentable bullets, case-insensitive, bold optional (aligned with
# check_test_proposal's counter). Scoped to the Behavior Contract SECTION by the
# callers — a Given quoted in ## Scope must not become a phantom roll-up row.
GIVEN_ROW_RE = re.compile(r"^\s*[-*]\s+(.*\*{0,2}Given\*{0,2}\b.*)$", re.I | re.M)
AGENT_TASK_RE = re.compile(r"^Agent-Task:\s*(T\d{2}[a-z]?)\b", re.I | re.M)
# Field lines tolerate a bullet prefix (bulleted metadata is natural markdown).
# Blockquote (`>`) tolerance follows FAIL DIRECTION, deliberately split (this
# note covers the NAMED members only — regexes outside it, e.g. ORDER_LINE_RE /
# GIVEN_ROW_RE / BOARD_ROW_RE / _list_paths bullets, simply never took `>`):
# - this _F family + SERIALIZED_LINE_RE never parse a quoted line — a quoted
#   `Depends:`/`Integration:`/`Serialized:` example parsing live would silently
#   license overlaps or mint a phantom Integration ticket (a non-parse of
#   Complexity is NOT silent — it fails loud via the missing-Complexity
#   finding; Parallel is Phase-D dispatch metadata, parsed but unchecked here);
# - STATUS_RE keeps `>` for byte-parity with check_convergence /
#   check_plan_quality / docs_updater, where a quoted Status draws the
#   ticket-Status ban / claim checks (fail-closed). The one fail-OPEN consumer
#   — spine-status determination, where parsing more downgrades severity —
#   strips blockquoted lines from its scan instead (see _BLOCKQUOTE_RE);
# - the Never-Route label DOES parse quoted forms — a quoted Never-Route line
#   ADDS coverage (silence was the hazard), and its hygiene WARN arms
#   (multi-token / void / residue) follow the parse by design.
# Numbered field lines (`1. Complexity:`) don't parse — fails loud via the
# missing-field/missing-Complexity findings.
_F = r"^\s*(?:[-*]\s+)?"
GATE_LINE_RE = re.compile(_F + r"\*{0,2}Gate\*{0,2}[^\S\n]*:", re.I | re.M)
# A Gate: whose pipeline ENDS in a pure DISPLAY filter throws its exit status away. The shell
# reports the LAST stage, and `tail`/`head`/`cat`/`less` always succeed — so
# `pytest server/tests -q | tail -5` is green while pytest exits 4 on a directory that does not
# exist. Measured live (transdoc, 2026-08-28): pipeline $?=0 while PIPESTATUS(pytest)=4, "no tests
# ran in 0.00s", against a repo whose real suite is 472 passed. That is the same "44 skipped, exit
# 0" hole the ${TEST_DATABASE_URL:?} guard exists to close — the guard shut the unset-variable
# door and the pipe opened a wider one beside it.
#
# DISPLAY-only by design. `grep -q`, `grep -c` and `jq` as a final stage ARE the assertion, and
# flagging them would be wrong: measured fleet-wide, 16 of 805 gates end in some filter but only
# 2 end in a display filter. The narrow rule is the true one.
GATE_DISPLAY_TAIL = frozenset({"tail", "head", "cat", "less", "more"})
GATE_CMD_RE = re.compile(_F + r"\*{0,2}Gate\*{0,2}[^\S\n]*:[^\S\n]*(?P<cmd>[^\n]+)", re.I | re.M)


def _gate_masks_exit_status(text: str) -> list[str]:
    """Gate commands whose final pipeline stage discards the exit status of the thing under test."""
    bad: list[str] = []
    for m in GATE_CMD_RE.finditer(_strip_fences(text)):
        cmd = m.group("cmd").strip().strip("`").strip()
        if not cmd or "|" not in cmd or len(cmd) > 400:
            continue
        tail_seg = cmd.split("|")[-1].strip().strip("`").strip()
        first = tail_seg.split()[0] if tail_seg.split() else ""
        if first in GATE_DISPLAY_TAIL:
            bad.append(cmd[:160])
    return bad


INTEGRATION_RE = re.compile(
    _F + r"\*{0,2}Integration\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*true\b", re.I | re.M
)
# Bold-tolerant like STATUS_RE — a `**Complexity:** simple` label must not
# silently disable the whole routing layer.
COMPLEXITY_RE = re.compile(
    _F + r"\*{0,2}Complexity\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*(\S+)", re.I | re.M
)
# Bold-tolerant like COMPLEXITY_RE — a `**Depends:** T01` label must not
# silently drop a graph edge (false-red overlap + a fail-open topological
# check); the whole field family shares the STATUS_RE label shape.
DEPENDS_RE = re.compile(
    _F + r"\*{0,2}Depends\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*(.+)$", re.I | re.M
)
PARALLEL_RE = re.compile(
    _F + r"\*{0,2}Parallel\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*(\S+)", re.I | re.M
)
# The epic-born plan's header line: exactly one `Epic: docs/development/epics/<file>` on
# the SPINE (written by fabrik-plan-after-chat Phase 4). Same label family as the fields
# above — bold/bullet tolerant, no `>` blockquote.
#
# ⚠️ ITS PREFIX IS NOT `_F` — deliberately, and this is the ONE place in the file where a
# `>` blockquote MUST parse. The `_F` family (Depends/Integration/Serialized) refuses
# blockquotes because parsing a quoted example LICENSES an overlap: fail-open. Here the
# direction is inverted — a header that does not parse means containment silently never
# runs, which is the precise fail-open `_epic_containment` exists to close — so `>` is
# accepted, as STATUS_RE accepts it for the same reason. The marker group REPEATS and
# MIXES: `>> Epic:`, `> > Epic:`, `>Epic:` (no space), `- > Epic:` and `> - Epic:` are all
# ordinary quoting/bulleting, and each earlier form of this prefix matched some and not
# others — every miss parsing to nothing, i.e. containment silently skipped, which is the
# exact hole this prefix exists to close. A bullet still REQUIRES its whitespace
# (`[-*]\s+`), so a `--- ` rule or a bold `**Epic:` is untouched.
#
# WHOLE-LINE emphasis (`**Epic: <path>**`, `*Epic: <path>*`) closes on the VALUE side: the
# opening run is eaten before `Epic`, but a closing one stayed glued to the path
# (`…1-x.md**`) and tripped the glob arm of the unusable-path guard — a hard red on an
# ordinary markdown line. The tail is peeled SYMMETRICALLY: the opening run is captured as
# `em` and the tail is `(?:(?P=em))?`, so a run is removed only when one OPENED the line.
# Emphasis is paired, and that is the whole rule.
#
# Two rejected alternatives, both measured over the 22 header forms this file tests or has
# met (0 mismatches for the shipped form):
#   - an END-ANCHOR (`(\S*?)\*{0,2}[^\S\n]*$`) stops matching the ONE live header on the box
#     (an archived spine whose line carries trailing prose — `… .md (epic_n 2, depends_on
#     [1])`) and the prose form, turning both into SILENT non-parses — the fail-open every
#     widening here has closed;
#   - an UNPAIRED lookahead peel (`(\S*?)\*{0,2}(?=[^\S\n]|$)`, shipped briefly) eats a
#     trailing `*`/`**` that BELONGS to the value: `Epic: epics/*` captured `epics/` and
#     `Epic: docs/x/**` captured `docs/x/`, so the glob arm never fired and the refusal came
#     back with the wrong reason ("no such file"); worse, `Epic: <real-file>.md*` captured a
#     path that EXISTS, silently accepting a malformed header and reading that epic.
#
# The value group is `(\S*?)`, not `(\S+)`, ON PURPOSE: a header with no value at all
# (`Epic:`, `Epic: `, `Epic:\t`, `> Epic:`, or the path wrapped onto the NEXT line) used to
# match nothing, and matching nothing is containment silently not running — the same
# fail-open every widening above closed. It now parses to an empty token and takes the
# unusable-path ERROR, which is the loud half of the same rule. (Fire rate for the
# valueless form box-wide: 0 of 995; no emitter writes it.)
#
# WHAT THE FENCE STRIP ACTUALLY COVERS (`_strip_fences`, whose parsing contract is stated
# at _FENCE_RE): BACKTICK fences only — a balanced 3+-backtick block and an inline
# single-line ```…```. NOT stripped, and each therefore PARSED as a real header: a `~~~`
# tilde fence, a 4-space-indented code block, a `>` blockquote (by the choice above), and
# ordinary prose starting a line with "Epic:" (`Epic: this plan…` yields the token
# `this`). Every one fails CLOSED — an unresolvable path is an ERROR that hard-reds the
# set, never a silent skip — so the cost is a loud false red on a spine that quoted the
# word in an unsupported form, and the fix is to fence it with backticks.
# Measured before shipping, with the bound named because the ratio moves with it: ONE
# line matches this regex box-wide at the bound "*.md one level under
# docs/development/plans/" (1 of 509) and recursively (1 of 994) — and that one file is
# ARCHIVED, so this gate never reads it. Inside the directories the gate actually walks
# there are ZERO: 0 of 477 files in dated set dirs, 0 of 173 in non-archived ones
# (2026-09-05; the population grows as plans land, the hit count has not). The rule
# therefore fires only where a header is deliberately written.
EPIC_HEADER_RE = re.compile(
    r"^\s*(?:[-*]\s+|>[^\S\n]*)*(?P<em>\*{0,2})Epic\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*"
    r"(?P<path>\S*?)(?:(?P=em))?(?=[^\S\n]|$)",
    re.I | re.M,
)
TICKET_ID_RE = re.compile(r"T\d{2}[a-z]?")
# Characters never legal in a repo path token: emphasis/quote/backtick residue,
# list separators, and colons (a `path:NN` citation suffix is stripped by the
# fixpoint first — anything colon-like that remains is opaque). A token carrying
# one after fixpoint normalization is invisible to every prefix/exact
# predicate — fail CLOSED, not silent.
_RESIDUE_RE = re.compile(r"[`\"',;:]")
# Blockquoted lines (`> …`) are QUOTED content for spine-status DETERMINATION
# (stripped alongside fences at that one consumer — see the doctrine note above
# _F). Applied nowhere else: the ticket-Status ban and Never-Route label parse
# quoted forms on purpose (both fail closed).
_BLOCKQUOTE_RE = re.compile(r"^[ \t]*>.*$", re.M)
# Fenced blocks are QUOTED content — never counted (a `Gate:`/`Status:` inside an
# example must not trip the field counters).
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


# CLAUDE.md's four orchestrator-applied governance files, plus LESSONS_LEARNT —
# the fifth shared-append surface (Completion Contract §4: every run either
# appends it or records `none`, so any run MAY append — the same
# BLOCK-on-overlap collision class as CHANGELOG if a lock owned it) — plus
# DECISIONS.md, the sixth (close-out decision line: every run either appends a
# row or states `no decisions this run` — same collision class, and CLAUDE.md
# § the decision ledger additionally forbids a coder subagent holding the pen:
# a ticket listing it in Touches hands exactly that pen) — plus STRATEGIC_BACKLOG,
# the seventh (Doc Sync Matrix: every project's deferred-work append surface; repo-review
# and upstream mandate per-run appends — same collision class). Retro-impact of the 5->7
# expansion measured 2026-08-31: 31 plan SETS fleet-wide, 24 archived (exempt via _is_archived
# — note that skip inflates any naive denominator), 7 LIVE graded: 0 -> 0 governance errors.
GOVERNANCE_FILES = (
    "CHANGELOG.md",
    "INDEX.md",
    "docs/README.md",
    "docs/FEATURES.md",
    "docs/LESSONS_LEARNT.md",
    "docs/DECISIONS.md",
    "docs/STRATEGIC_BACKLOG.md",
)
# The legacy-tolerated lowercase alias (CLAUDE.md Doc Sync Matrix) is the same
# surface — ban/tolerate it identically or the carve-out is bypassable.
_GOV_SURFACES = GOVERNANCE_FILES + ("docs/lessons-learnt.md",)
NEVER_ROUTE_PREFIXES = (
    "scripts/enforcement/",
    "scripts/final_gate.py",
    "alembic/",
    "db/migrations/",
    "secrets/",
)
# `.env` and `.env.*` are secret material — EXCEPT `.env.example` (a routine
# Doc-Sync-Matrix file every env-var change touches).
_ENV_EXEMPT = ".env.example"
# The spine-metadata territory: per-plan review/lock artifacts. Used by the
# Touches ownership ERROR (foreign-stem = ERROR), the containment skip, and the
# File-Scope orphan exemption (own-stem only). `~/` is deliberately NOT here —
# rendered ~/.claude outputs are the orchestrator's render step, never ownable.
# Governance surfaces are handled separately — a listed/covering entry is a
# DEDICATED ERROR (File Scope builds the lock; locking a shared-append surface
# would make every pair of concurrent plans BLOCK on scope overlap).
_SPINE_METADATA_PREFIXES = (
    "docs/development/reviews/",
    ".fabrik/plan-locks/",
    # The dir holding every OTHER plan set — sibling spines/tickets are never
    # another plan's write territory.
    "docs/development/plans/",
)


def _stem_scoped(token: str, plan_dir: Path) -> bool:
    # Component-bounded stem test for the plan's OWN metadata artifacts: the
    # dir itself, its lock (`<stem>.json`), or a review doc
    # (`<stem>[-T##…]-review….md`). A generic `<stem>-anything` is NOT accepted
    # (a sibling lock `<stem>-v2.json` must never ride this exemption).
    # Residual, recorded: a sibling plan literally NAMED `<stem>-v2` could
    # alias this plan's review shape — but same-day plans must take the next
    # unused <n> (naming rule), so such a sibling is already out of contract.
    stem = plan_dir.name
    for seg in token.split("/"):
        if seg == stem or seg == stem + ".json":
            return True
        if seg.startswith(stem + "-") and seg.endswith(".md") and "-review" in seg[len(stem) :]:
            return True
    return False


# Adapter dedupe: one dir-level validation per process run, attached to the FIRST
# file seen from that dir (spine-only attachment would silently drop everything
# when only a ticket is staged).
_SEEN_DIRS: set[Path] = set()


def _section(text: str, title: str) -> str:
    # No trailing \b — a title ending in a non-word char (e.g. ')') would make the
    # boundary unmatchable. Prefix semantics: "File Scope" also matches
    # "File Scope (owned paths)".
    m = re.search(rf"^##\s+{re.escape(title)}(.*?)(?=^##\s|\Z)", text, re.I | re.M | re.S)
    return m.group(1) if m else ""


def _norm_path(p: str) -> str:
    # FIXPOINT normalization (one contract for Touches / File Scope /
    # Never-Route): strips edge backticks, SYMMETRIC emphasis wraps, balanced
    # QUOTE wraps (never parens — legal path chars), a trailing `:NN` citation
    # suffix and trailing colons, a RUN of trailing sentence dots (whole-dot
    # segments survive for the repo-root/out-of-repo arms; `dir/.` collapses),
    # interior `/./` self-references, and a `./` prefix. Iterated so mixed
    # forms (`` `vendor/`. ``) resolve fully. Commas/semicolons are NOT
    # stripped — they reach the LOUD residue arms. A lone edge star is a GLOB
    # (`docs/*`) and must survive so the glob ERROR catches it.
    while True:
        before = p
        p = p.strip().strip("`")
        while len(p) >= 4 and p.startswith("**") and p.endswith("**"):
            p = p[2:-2].strip()
        while len(p) >= 2 and p.startswith("*") and p.endswith("*"):
            p = p[1:-1].strip()
        # Balanced QUOTE wraps only — quotes are never legal in repo paths.
        # Parens are NOT stripped: they are legal path chars (Next.js/Expo
        # route groups like `app/(marketing)` / a literal `(build)/`), and an
        # edge-anchored strip would destroy a bare `(marketing)` token.
        for quote in ('"', "'"):
            if len(p) >= 2 and p.startswith(quote) and p.endswith(quote):
                p = p[1:-1].strip()
        # A `path:NN` citation suffix collapses to the path (author intent —
        # the file is what's owned/protected); bare trailing colons strip too.
        p = re.sub(r":\d+$", "", p).rstrip(":")
        # Interior `/./` self-references collapse (POSIX identity).
        while "/./" in p:
            p = p.replace("/./", "/")
        # A RUN of trailing sentence dots — segment-aware: a final segment that
        # is ENTIRELY dots must survive for the repo-root/out-of-repo arms —
        # except the POSIX self-reference `dir/.`, which IS the dir.
        if p.endswith("/.") and not p.endswith("/.."):
            p = p[:-1]
        core = p.rstrip(".")
        if core and core != p and not core.endswith("/"):
            if p.rsplit("/", 1)[-1].strip("."):
                p = core
        if p.startswith("./"):
            p = p[2:]
        if p == before:
            return p


def _list_paths(section_body: str) -> list[str]:
    """Bullet OR numbered lines → first token as a repo-relative path (markers
    after it ignored). Tolerates tab-indented bullets and bold-wrapped entries —
    a silently-empty parse would disable overlap/containment/never-route/budget
    checks with zero signal."""
    out: list[str] = []
    for line in section_body.splitlines():
        m = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(\S+)", line)
        if m:
            token = _norm_path(m.group(1))
            if token:
                out.append(token)
    return out


def _covered_by(entry: str, path: str) -> bool:
    """DIRECTIONAL containment: `entry` covers `path`. Trailing slashes are
    insignificant on BOTH sides (`src/app` ≡ `src/app/`, as an entry AND as the
    covered path)."""
    return path.rstrip("/") == entry.rstrip("/") or path.startswith(entry.rstrip("/") + "/")


def _path_covers(entry: str, path: str) -> bool:
    """SYMMETRIC overlap (either side may be the covering dir) — for collision
    detection only; containment tests use the directional _covered_by."""
    return _covered_by(entry, path) or _covered_by(path, entry)


def _never_route(p: str) -> bool:
    """Bidirectional: a Touches entry that IS, is UNDER, or COVERS a never-route
    path is never-route (a `scripts/` or slash-less `scripts` dir entry owns
    scripts/enforcement/ too)."""
    if p == _ENV_EXEMPT:
        return False
    if p == ".env" or p.startswith(".env."):
        return True
    return any(_covered_by(n, p) or _covered_by(p, n) for n in NEVER_ROUTE_PREFIXES)


# --- Epic containment: the GLOB-aware half of path coverage ---------------------------
# `_covered_by` stays literal-vs-literal — the ownership, never-route and File-Scope
# layers all depend on its prefix semantics, and widening it would change every one of
# them. An EPIC's `owned_paths` are GLOBS by schema (`src/a/**`,
# `libs/**/product_entitlements_bridge/**`, `app/(admin)/**` — the live shapes across the
# two repos that have an epics dir, read 2026-09-05), so the ticket/File-Scope ⊆ epic
# comparison gets its own predicate beside it. `/`-AWARE by construction: bare `fnmatch`
# is separator-blind (`fnmatch("src/a/b/deep.py", "src/a/*")` is True), which would admit
# a path the epic deliberately scoped OUT and silently void the guarantee that a window
# cannot plan or build outside its epic.
_GLOB_PROBE = "\x00fabrik-subtree-probe\x00"  # never a real path segment


def _seg_matches(seg: str, s: str) -> bool:
    """Does ONE segment's wildcard pattern match this ONE path segment?

    `*` = any run of non-`/` characters, `?` = exactly one non-`/` character, and every
    other character is a LITERAL — no regex, so parens, dots, `+` and brackets are just
    characters (`app/(admin)/**` and `alembic/versions/(deploy)**` are live epic shapes,
    and the regex form had to `re.escape` them for exactly this reason).

    ITERATIVE two-pointer with a single backtrack point (the classic wildcard matcher):
    O(len(seg) x len(s)), never exponential. The `[^/]*`-per-`*` regex it replaces
    backtracked CATASTROPHICALLY on a non-match inside one segment — measured on this box
    2026-09-05 against a 41-character name, `src/a*a*a…b/**` took 0.80 s at 8 stars, 9.8 s
    at 10 and 74.7 s at 12 (74 s through the real CLI, rc 1), on a pattern read from an
    epic file with no timeout in the call path; 5 of 45 live `owned_paths` values already
    carry multi-`*` segments.

    OUT OF CONTRACT, deliberately: the `[seq]` bracket class. `[` is a LITERAL here, so
    `src/[ab]/**` matches the directory literally named `src/[ab]/` and nothing else —
    the right reading for this fleet's paths (all 8 bracket tokens among the 1,007
    Touches/File-Scope tokens in the 15 live non-archived plan sets are Next.js
    dynamic-route dirs, `[id]`/`[token]`; none is an alternation set), and the wrong one
    for a glob author. `_epic_containment` therefore REFUSES a bracket in an epic's
    `owned_paths` (loudly, rather than false-redding every ticket beneath it); 0 of 45
    live `owned_paths` values carry one.
    """
    i = j = 0
    star = -1  # index in `seg` of the last `*` seen
    mark = 0  # how far in `s` that `*` has consumed
    while i < len(s):
        # The `*` branch is tested FIRST, and the order is load-bearing: with the literal
        # comparison first, a pattern `*` aligned with a literal `*` IN THE NAME was
        # consumed as an equal literal and no backtrack point was recorded, so
        # `_seg_matches("*", "**")` answered False — against this function's own
        # contract, and 62 of 130,049 differential-fuzz pairs, every one that shape.
        if j < len(seg) and seg[j] == "*":
            star, mark = j, i
            j += 1
        elif j < len(seg) and (seg[j] == s[i] or (seg[j] == "?" and s[i] != "/")):
            i += 1
            j += 1
        elif star >= 0:
            # the `*` swallows one more character — never a separator
            if s[mark] == "/":
                return False
            mark += 1
            i, j = mark, star + 1
        else:
            return False
    while j < len(seg) and seg[j] == "*":
        j += 1
    return j == len(seg)


def _glob_matches(pattern: str, path: str) -> bool:
    """Does the glob `pattern` match this whole path? SEGMENT-WISE, never one big regex.

    Semantics: a whole-segment ``**`` spans any number of segments — zero included in the
    MIDDLE (`libs/**/x/**` matches `libs/x/y.py`), at least one when TRAILING (`src/a/**`
    matches `src/a/x.py`, and the bare `src/a` is answered by `_glob_covers`'s subtree
    probe instead). ``*`` / ``?`` never cross a separator, by construction: they are only
    ever matched against ONE segment.

    `reach` is the frontier of path-segment indices the pattern's prefix can consume to,
    so the segment level costs O(pattern segments x path segments) and never backtracks
    ACROSS segments; WITHIN a segment, `_seg_matches` is a two-pointer matcher with one
    backtrack point, bounded at O(seg x segment). Neither level has an exponential case —
    both had one before: the single-regex form (`(?:[^/]+/)*` per mid-``**``) took 3.7 s
    at 10 chained ``**`` on a 22-segment path, 11.2 s at 11 and 32.2 s at 12, and the
    `[^/]*`-per-`*` segment regex took 74.7 s on 12 stars inside ONE segment. Both were
    reachable from an epic file a project agent writes, with no timeout in the call path.
    (Possessive/atomic quantifiers would fix both and need Python 3.11+; these two
    matchers need no version floor at all on a fleet-synced file.)
    """
    psegs = pattern.rstrip("/").split("/")
    ssegs = path.split("/")
    m = len(ssegs)
    reach = {0}
    for i, seg in enumerate(psegs):
        if seg == "**":
            # Only the SMALLEST reachable index matters, and not because `reach` is
            # upward-closed — it is not in general (`**/a/**/b` can leave `{3, 7}` after a
            # literal segment). It is because `**` from index j reaches every index ≥ j
            # (≥ j+1 when trailing), so the union of those rays over any `reach` IS the
            # single ray from min(reach).
            first = min(reach)
            reach = set(range(first + 1 if i == len(psegs) - 1 else first, m + 1))
        else:
            reach = {j + 1 for j in reach if j < m and _seg_matches(seg, ssegs[j])}
        if not reach:
            return False
    return m in reach


def _glob_covers(pattern: str, entry: str) -> bool:
    """DIRECTIONAL containment with a GLOB on the `pattern` side: does an epic
    `owned_paths` entry cover this literal Touches / File-Scope entry?

    A glob-free pattern falls back to `_covered_by` (literal file/dir prefix semantics —
    an epic may own `db/schema.sql` or a bare dir). A DIRECTORY entry (`docs/x/`) is
    covered only when its WHOLE subtree is, probed at two depths: `docs/x/` lies inside
    `docs/**` and NOT inside `docs/*` (one probe would not separate them — `docs/PROBE`
    matches `docs/*`).

    The one AMBIGUOUS shape, resolved deliberately: a slash-less token (`src/a`) may name
    a file or a directory and the grammar does not say which, so it is tested as a file
    first and as a directory second — `_glob_covers("src/a/**", "src/a")` is True. That
    is right for the directory reading and PERMISSIVE for the file one. The permissive
    direction is chosen on purpose: the strict one would false-RED a legitimate
    `Touches: src/a` under a globbed epic (a red the author cannot fix without renaming
    their own scope), while this fails open only for a FILE whose name is exactly a
    directory the epic owns — and that file is inside the epic's tree either way.
    """
    pattern = pattern.strip()
    if not pattern:
        return False
    if not any(ch in pattern for ch in "*?"):
        return _covered_by(pattern, entry)
    bare = entry.rstrip("/")
    if not entry.endswith("/") and _glob_matches(pattern, bare):
        return True
    return _glob_matches(pattern, f"{bare}/{_GLOB_PROBE}") and _glob_matches(
        pattern, f"{bare}/{_GLOB_PROBE}/{_GLOB_PROBE}"
    )


def _norm_glob(entry: str) -> str:
    """Path-normalise ONE epic `owned_paths` entry — glob-safely.

    Touches and File-Scope tokens run through `_norm_path`; epic entries were only
    `.strip()`ed, so `./src/a/**` matched nothing and LOUDLY accused every ticket the epic
    really owns. `_norm_path` itself cannot be reused here: its symmetric-emphasis strip
    eats `**/x/**` down to the absolute `/x/` (a documented behaviour there — a recursive
    glob is not a legal Touches token), which matches nothing and reintroduces the same
    false red from the other side. So this does the two normalisations a glob shares with
    a path — a `./` prefix and interior `/./` self-references, plus edge quotes/backticks —
    and NOTHING else.
    """
    g = entry.strip().strip("`").strip()
    for quote in ('"', "'"):
        if len(g) >= 2 and g.startswith(quote) and g.endswith(quote):
            g = g[1:-1].strip()
    while "/./" in g:
        g = g.replace("/./", "/")
    while g.startswith("./"):
        g = g[2:]
    return g


def _unusable_owned(entry: str) -> str | None:
    """Why this epic `owned_paths` entry can never match anything — or None if it can.

    Every shape here is one `_glob_covers` answers False to for EVERY path, which turns
    the containment loops into an accusation of every ticket the epic owns. Naming the
    entry once is the fail direction the `[seq]` refusal already chose; this is that
    doctrine applied to the whole class. Measured before shipping: 0 of the 45 live
    `owned_paths` values carry any of these shapes.
    """
    if not entry.strip():
        # Reached via `_norm_glob`: `"./"` and `"."`-only entries normalise to nothing.
        # Dropping them silently made the epic report "carries no owned_paths" against a
        # file that declares one — a true statement about the parsed value and a false one
        # about the epic, which sends the author to the wrong line.
        return "an empty path once normalised (a blank entry, or `./` and friends, cover nothing)"
    if "[" in entry or "]" in entry:
        # Out of contract by DESIGN: `_seg_matches` compares `[` as an ordinary
        # character, because on the ticket side `[id]`/`[token]` are literal route dirs.
        return "a `[seq]` bracket class (brackets are matched LITERALLY here, as Next.js `[id]` route dirs)"
    if entry.startswith("/"):
        return "an absolute path (owned_paths are repo-relative)"
    if entry.startswith("~"):
        return "a `~`-rooted path (owned_paths are repo-relative)"
    if ".." in entry.split("/"):
        return "a `..` traversal (owned_paths never leave the repo)"
    if "\\" in entry:
        return "a `\\` separator (paths are `/`-separated)"
    if "//" in entry:
        return "an empty path segment (`//`)"
    if entry.rstrip("/") == ".":
        return "the repo-root token `.` (it covers nothing in the matcher)"
    return None


def _carved_out(p: str) -> bool:
    """Tokens the epic-containment loops SKIP — the same carve-out the File-Scope
    containment applies: opaque tokens (glob / out-of-repo / repo-root / residue), which
    already drew their own dedicated ERROR and are invisible to every path predicate, and
    the off-contract surfaces (governance files, plan-metadata territory), which no epic
    ever owns — a CHANGELOG append or a stem-scoped review receipt is not epic scope."""
    return (
        any(ch in p for ch in "*?")
        or p.startswith(("/", "~"))
        or ".." in Path(p).parts
        or p.rstrip("/") == "."
        or bool(_RESIDUE_RE.search(p))
        or any(_covered_by(p, g) for g in _GOV_SURFACES)
        or any(_covered_by(p, x) or _covered_by(x, p) for x in _SPINE_METADATA_PREFIXES)
    )


_ROW_MARKER_TAIL = re.compile(r"\s*\(\d+\)\s*\.?$")  # trailing (N) row markers — house style
# A trailing `(path:line)` — or a comma/semicolon-separated run of them — is GROUNDING,
# not identity. Built from check_convergence.PROOF so this forgives exactly the extension
# set the rest of the gate treats as a citation, and cannot drift from it. Anything else
# in parentheses (`(idempotently)`) is prose and stays part of the compared sentence.
_CITATION_TAIL = re.compile(rf"\s*\(\s*{PROOF.pattern}(?:\s*[,;]\s*{PROOF.pattern})*\s*\)\s*\.?$")


def _norm_behavior(line: str) -> str:
    """Normalize a Given/When/Then row to its comparable identity.

    The roll-up is set equality between spine rows and ticket rows, so anything left in
    here is load-bearing: a difference the normalizer does not absorb costs TWO errors
    (missing-row on one side, matches-no-ticket on the other). The plan skeleton
    (`fabrik-plan-after-chat.md`) teaches `**Then** <observable> (src/app/x.py:12)`, and
    a ticket legitimately cites its own line where the spine cites the primary path — so
    scoring the citation as identity punished the exact grounding habit the skeleton
    teaches (transdoc, 2026-08-22: ~30 errors on a 16-ticket set; they stripped every
    citation to get green). Markers and citations may appear in either order, and either
    may carry the sentence period, so peel until stable.
    """
    line = line.strip().lstrip("-*").strip().rstrip(".")
    while True:
        peeled = _CITATION_TAIL.sub("", _ROW_MARKER_TAIL.sub("", line)).rstrip().rstrip(".")
        if peeled == line:
            break
        line = peeled
    return re.sub(r"\s+", " ", line.replace("**", "")).lower().rstrip(".")


@dataclass
class Ticket:
    tid: str
    path: Path
    text: str
    touches: list[str] = field(default_factory=list)
    context_files: list[str] = field(default_factory=list)
    depends: list[str] = field(default_factory=list)
    parallel: str = ""
    complexity: str = ""
    integration: bool = False
    behaviors: list[str] = field(default_factory=list)


def _err(
    msg: str, path: Path, severity: Severity = Severity.ERROR, hint: str | None = None
) -> CheckResult:
    return CheckResult(
        check_name="plan_tickets",
        severity=severity,
        message=msg,
        file_path=str(path),
        fix_hint=hint,
    )


def _parse_ticket(path: Path) -> Ticket:
    text = path.read_text(encoding="utf-8", errors="replace")
    # ONE policy: every semantic scan runs on FENCE-STRIPPED text (a fenced
    # `Depends: T05` / `Integration: true` example must neither false-red nor
    # quietly eat the integration role). Only the PROOF citation scan stays raw —
    # evidence legitimately lives inside fenced output blocks.
    scan = _strip_fences(text)
    tid = TICKET_FILE_RE.match(path.name).group(1)  # type: ignore[union-attr]
    dep_m = DEPENDS_RE.search(scan)
    depends = TICKET_ID_RE.findall(dep_m.group(1)) if dep_m else []
    par_m = PARALLEL_RE.search(scan)
    cpx_m = COMPLEXITY_RE.search(scan)
    return Ticket(
        tid=tid,
        path=path,
        text=text,
        touches=_list_paths(_section(scan, "Touches")),
        context_files=_list_paths(_section(scan, "Context Files")),
        depends=depends,
        parallel=par_m.group(1) if par_m else "",
        complexity=(cpx_m.group(1).strip("*").lower() if cpx_m else ""),
        integration=bool(INTEGRATION_RE.search(scan)),
        # Section-scoped — a Given-row quoted elsewhere in the ticket must not
        # become a phantom entry in the roll-up equality check.
        behaviors=[
            _norm_behavior(m) for m in GIVEN_ROW_RE.findall(_section(scan, "Behavior Contract"))
        ],
    )


def _depends_connected(a: str, b: str, edges: dict[str, list[str]]) -> bool:
    """True when a transitive Depends path connects a↔b (either direction)."""

    def _reaches(src: str, dst: str) -> bool:
        stack, seen = [src], set()
        while stack:
            cur = stack.pop()
            if cur == dst:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(edges.get(cur, []))
        return False

    return _reaches(a, b) or _reaches(b, a)


def _find_cycle(edges: dict[str, list[str]]) -> bool:
    white, gray, black = 0, 1, 2
    color = dict.fromkeys(edges, white)

    def _visit(n: str) -> bool:
        color[n] = gray
        for m in edges.get(n, []):
            if color.get(m, white) == gray:
                return True
            if color.get(m, white) == white and _visit(m):
                return True
        color[n] = black
        return False

    return any(color[n] == white and _visit(n) for n in list(edges))


def _sizing_severity(context: str, spine_status: str) -> Severity:
    if context in ("cli", "flip"):
        return Severity.ERROR
    # validate_conventions gate path: sibling-session / mid-run protection — and a
    # merged set cannot be re-split: the READ budget is a DISPATCH-time constraint,
    # and a ticket that grows its own file measures over budget on the post-merge
    # tree forever (plan 2026-09-06-plan-2: docs_updater.py 59 → 90 KB through its
    # own tickets turned every sibling's gate red at the EXECUTED flip). EXECUTED is
    # advisory here; the author's CLI and the flips keep the ERROR.
    if spine_status in (*_DRAFT_LIKE, "IN-PROGRESS", "EXECUTED"):
        return Severity.WARN
    return Severity.ERROR


def _is_plans_layout(plan_dir: Path) -> bool:
    """True when plan_dir sits at <root>/docs/development/plans/<name>."""
    parts = plan_dir.parts
    return len(parts) >= 4 and parts[-4:-1] == ("docs", "development", "plans")


def _is_archived(plan_dir: Path) -> bool:
    """plans/archived/<dated-dir> — structural, never an absolute-path parts scan."""
    parts = plan_dir.parts
    return len(parts) >= 5 and parts[-5:-1] == ("docs", "development", "plans", "archived")


def _repo_root(plan_dir: Path) -> Path | None:
    if not _is_plans_layout(plan_dir):
        return None
    return plan_dir.resolve().parents[3]


def _norm_cell(c: str) -> str:
    """Board-cell normalization: edge backticks then `.strip("*")` (asymmetric and
    multi-layer bold collapse — DIFFERENT from `_norm_path`, which keeps
    asymmetric stars so globs survive to the glob ERROR); only the
    bold-outside-backtick double-wrap survives, as documented."""
    return c.strip().strip("`").strip("*").strip()


def _board_states(spine_text: str) -> dict[str, str]:
    """Board-row ID → state cell, header-aware (a reordered/extra column must not
    silently read the wrong cell; falls back to index 5 when no header names State)."""
    board = BOARD_SECTION_RE.search(spine_text)
    if not board:
        return {}
    state_idx = 5
    lines = board.group(1).splitlines()
    for line in lines:
        # Header recognition: a |-line with a `State` cell, ≥3 content cells,
        # and no T## ID cell (IDs tested on fully-stripped cells so a
        # double-wrapped `**`T01`**` still vetoes). The LAST candidate before
        # the first data row wins — so a wide legend ABOVE the board loses to
        # the real header, a narrow `| State | Meaning |` legend is too narrow,
        # a `| Ticket | Owner |` roster has no State, and a data row (T## cell)
        # can never hijack the index. Cells are normalized like paths
        # (backticks, then bold) so a decorated header keeps header-awareness;
        # an unrecognizable header (bold-outside-backtick double-wrap) →
        # documented fallback 5.
        if BOARD_ROW_RE.match(line):
            break  # first data row — the header scan is over
        if line.strip().startswith("|"):
            cells = [_norm_cell(c) for c in line.split("|")]
            content = [c for c in cells if c]
            state_cols = [i for i, c in enumerate(cells) if c.lower() == "state"]
            if (
                state_cols
                and len(content) >= 3  # rejects a 2-cell `| State | Meaning |` legend;
                # a 3-column `| Ticket | State | Commit |` board stays parseable
                and not any(
                    TICKET_ID_RE.search(c.replace("`", "").replace("*", "")) for c in content
                )
            ):
                state_idx = state_cols[0]
    states: dict[str, str] = {}
    for m in BOARD_ROW_RE.finditer(board.group(1)):
        # Data cells get the same normalization — a `**⬜**` state cell must not
        # silently disable the ⬜-never-flipped check.
        cells = [_norm_cell(c) for c in m.string[m.start() :].split("\n", 1)[0].split("|")]
        # Strip the emoji variation selector (U+FE0F) — editors emit ⬜️ freely,
        # and exact-glyph equality would silently disable the never-flipped check.
        states[m.group(1).upper()] = (
            (cells[state_idx] if len(cells) > state_idx else "").replace("️", "").strip()
        )
    return states


def _staleness(
    plan_dir: Path,
    spine_text: str,
    tickets: dict[str, Ticket],
    external_root: Path | None = None,
) -> list[CheckResult]:
    """Execution-window board-currency checks — fail-safe (NOTE + skip) on git errors."""
    # a scratch copy resolves its lock + git baseline against the caller's root, as sizing does —
    # this call site was missed by the external_root change and silently skipped the whole
    # execution-window staleness class under --allow-external (review pass 1, native finder).
    root = external_root if external_root is not None else _repo_root(plan_dir)
    if root is None:
        return []
    lock = root / ".fabrik" / "plan-locks" / f"{plan_dir.name}.json"
    try:
        baseline = json.loads(lock.read_text(encoding="utf-8")).get("baseline_commit")
    except (OSError, ValueError):
        return []  # no lock/baseline → execution has not started → skip entirely
    if not baseline:
        return []
    results: list[CheckResult] = []
    states = _board_states(spine_text)
    try:
        # ONE bulk call: merge commits diffed vs their FIRST parent (-m + --first-parent)
        # — orchestrator squash/merge commits are exactly the ones that must not escape.
        out = subprocess.run(
            [
                "git",
                "log",
                "--first-parent",
                "-m",
                "--name-only",
                "--format=%x01%H%x02%B%x02",
                f"{baseline}..HEAD",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        ).stdout
    except Exception as e:  # noqa: BLE001 — fail-safe by convention, but observable
        print(f"NOTE: plan_tickets staleness skipped (git error: {e!r})")
        return results
    for record in out.split("\x01"):
        if not record.strip():
            continue
        try:
            sha, body, files_blob = record.split("\x02", 2)
        except ValueError:
            continue
        files = [f.strip() for f in files_blob.splitlines() if f.strip()]
        # Keyed UPPERCASE to join the Board (whose row ids are uppercased too), valued
        # with the trailer's ORIGINAL text: the message quotes a string an operator greps
        # for, and `Agent-Task: T05A` appears in no commit and no spine — the id is
        # `T05a`. Uppercasing the key is matching; uppercasing the QUOTE is a wrong quote.
        trailers = {t.upper(): t for t in AGENT_TASK_RE.findall(body)}
        # Trailer IDs are PER-PLAN (every plan set has a T01). Plan identity =
        # the commit touches THIS plan's directory — the same-commit Board-flip
        # discipline means every legitimate ticket commit stages the spine, and
        # Touches-overlap is NOT identity (two plans may legally reference the
        # same shared path; alpha's 'Agent-Task: T01' must never red beta).
        plan_prefix = f"docs/development/plans/{plan_dir.name}/"
        # Identity = the commit touches this plan's DIR (the flip discipline) OR
        # any of its tickets' Touches (the forgot-to-flip case MUST still be
        # caught — an identity that only exists when the discipline held would
        # be blind to its own violation). Cross-plan caveat: two active locks
        # with overlapping Touches is an excluded state (lock acquisition BLOCKs
        # on overlap), so the Touches key does not re-open the alpha/beta hole.
        touched_any = any(
            _covered_by(entry, f) for tk in tickets.values() for entry in tk.touches for f in files
        )
        commit_in_plan = any(f.startswith(plan_prefix) for f in files) or touched_any
        for t in tickets.values():
            touched = any(_covered_by(entry, f) for entry in t.touches for f in files)
            if touched and t.tid.upper() not in trailers:
                # WARN, not ERROR: on shared master this commit may be a SIBLING
                # agent's or the daily pipeline's — an unfixable hard-block would
                # red the gate for the plan's whole duration. The acceptance
                # review enforces the discipline; this line keeps it observable.
                results.append(
                    _err(
                        f"commit {sha[:8]} touches {t.tid}'s Touches without an "
                        f"'Agent-Task: {t.tid}' trailer",
                        t.path,
                        severity=Severity.WARN,
                        hint="Ticket work lands with its own Agent-Task trailer "
                        "(the same-commit Board-flip discipline)",
                    )
                )
        for tid, trailer_text in trailers.items():
            if not commit_in_plan:
                break
            if states.get(tid, "").startswith("⬜"):
                results.append(
                    _err(
                        f"commit {sha[:8]} carries 'Agent-Task: {trailer_text}' but the "
                        f"Board row is still ⬜ (never flipped)",
                        plan_dir / f"{plan_dir.name}.md",
                        hint="Flip the Board row in the SAME commit as the ticket's merge",
                    )
                )
    return results


# --- Epic frontmatter: a VERBATIM port of T03a's parser closure ----------------------
# Ported byte-for-byte from `scripts/epic_order.py` @ 2bd530fe — same names, same bodies,
# same docstrings, so a future divergence is a plain diff (the parity test compares the
# two symbol by symbol whenever the hub copy is current). NOT an import: this file is
# synced to every project (`scripts/fabrik_synced_manifest.py::ENFORCEMENT_DIR`) and
# `epic_order.py` is not, so an import would break the fleet copy at load time.
#
# THE PORTED SET IS `_parse_frontmatter`'s CLOSURE, read from the source rather than
# recalled: _parse_frontmatter -> _find_fences, _line_content, _classify_fm_line,
# _collect_block_items, _LIST_KEYS · _find_fences -> _classify_fm_line, _line_content ·
# _line_content -> _line_terminator -> _LINE_TERMINATORS · _classify_fm_line ->
# _strip_unquoted_comment. `_line_terminator`/`_line_content` were writer-only at
# 544cf2ab and are IN the closure now that fence-finding is shared — which is exactly why
# the closure is re-enumerated on every re-port instead of carried over.
#
# What 2bd530fe changed, and why it matters HERE: fence detection moved into the shared
# classifier (`raw.rstrip() == "---"`), replacing a `startswith`/`find` prefix match. The
# prefix form accepted `----` as an opening fence and closed on the first line merely
# STARTING with `---`, so an epic with an interior `--- note` line lost every field below
# it — `owned_paths` among them — and this check would then ERROR "carries no owned_paths"
# against an epic that declares them (fixtures F18 and F20).
#
# The docstrings' references to `_write_owner` / `check_integrity` are the source
# module's, kept verbatim on purpose; here the single consumer is `_epic_containment`
# (which reads `owned_paths` and `_dup_keys`).
# fmt: off — the ported block keeps the SOURCE MODULE's formatting so a future
# divergence is a byte comparison, not a diff of two formatters' opinions.
# ruff format would rewrap `_LINE_TERMINATORS` and `_find_fences`'s generator;
# `ruff check` still lints this region (line-length 100 holds).
# fmt: off
def _strip_unquoted_comment(s: str) -> str:
    """Cuts a trailing " #comment" that is NOT inside a quoted value — a `#`
    reached while inside a quote is part of the value, never a comment start.
    The `#` must be at position 0 or preceded by whitespace (the YAML "a bare
    # only starts a comment after a space" convention) so an unquoted value
    that happens to contain a bare `#` mid-token is left alone.

    A quote character only OPENS a quoted value at position 0 of `s` — this
    flat parser's convention is "the whole value is quoted, or none of it
    is." An apostrophe or double-quote appearing mid-value in an unquoted
    string (`Bob's API`) is a literal character, never a quote-open; treating
    it as one used to trap the scanner in "still inside a quote" for the
    rest of the string, so a genuinely unquoted value's trailing comment
    never got cut."""
    in_quote: str | None = None
    for idx, ch in enumerate(s):
        if in_quote:
            if ch == in_quote:
                in_quote = None
        elif idx == 0 and ch in ("'", '"'):
            in_quote = ch
        elif ch == "#" and (idx == 0 or s[idx - 1].isspace()):
            return s[:idx]
    return s

# The three frontmatter fields the schema actually declares as LISTS. A
# multi-line YAML block ("key:" then "  - item" lines) is only ever a real
# value for one of these — the same shape under a SCALAR key (title, owner,
# slug, kind, status, scaffold, port, target_vps) is a malformed frontmatter,
# never silently promoted to a list (every consumer of those fields assumes
# a string: `re.match` on `title`, `owner in a set`, an f-string with `slug`
# — a list there is a crash or a silent wrong-typed value, not a clean
# integrity finding).
_LIST_KEYS = frozenset({"depends_on", "parallel_with", "owned_paths"})

# Every boundary str.splitlines() itself splits on (checked in this order so
# the 2-char "\r\n" is recognised before its own bare "\r"/"\n" suffixes
# would otherwise match first): CR+LF, CR, LF, vertical tab, form feed, the
# three C1 separators, NEL, and the two Unicode line/paragraph separators.
_LINE_TERMINATORS = (
    "\r\n", "\r", "\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029",
)

def _line_terminator(line: str) -> str:
    """The line-ending substring of ONE element from `str.splitlines(keepends=True)`
    — any of `_LINE_TERMINATORS`, or "" (only the text's last line, if it has
    no trailing terminator at all). Recognising only the ASCII \r\n/\r/\n
    trio here — while `splitlines()` itself (used by both `_parse_frontmatter`
    and `_write_owner` to cut lines in the first place) splits on the full
    set below — meant a line ending in, say, "\x0c" read as terminator-less:
    the writer's replacement/insertion then glued it directly onto the next
    physical line with no separator at all, destroying data at rc 0."""
    for term in _LINE_TERMINATORS:
        if line.endswith(term):
            return term
    return ""

def _line_content(line: str) -> str:
    """`line` (from `splitlines(keepends=True)`) with its own terminator
    removed — never a blind `.rstrip()`, which would also eat trailing
    whitespace that is part of the line's actual content."""
    term = _line_terminator(line)
    return line[: len(line) - len(term)] if term else line

def _classify_fm_line(raw: str) -> tuple:
    """Classifies ONE frontmatter line (its terminator already stripped) —
    the SINGLE place that answers "what kind of line is this", used by BOTH
    `_parse_frontmatter`'s block collector and `_write_owner`'s placement
    and replacement. Before this existed, the parser and the writer each
    answered the question independently (a hand-rolled loop vs. a pair of
    regexes) and disagreed on real fixtures: a whitespace-only interior line
    inside a block (the parser's `not raw.strip()` calls it blank; a regex
    anchored on a byte-empty line did not, so `owner:` landed INSIDE the
    block and an item was lost); `owner : x` or an indented `  owner: x`
    (the parser's `key.strip()` reads the key fine; `^owner:` anchored at
    column 0 with no space before the colon did not, so a SECOND owner:
    line got written at rc 0, breaking idempotency and pre-write dup
    detection alike).

    Returns one of:
      ("fence",)               — the line, once trailing whitespace is
                                   trimmed, is exactly "---" (no leading
                                   whitespace tolerated: an indented
                                   "  ---" is NOT a fence, nor is "----"
                                   four dashes, nor "--- trailing text" —
                                   see `_find_fences`)
      ("blank",)                — empty or all-whitespace
      ("comment",)               — a full-line comment: optional leading
                                   whitespace, then "#"
      ("item", text)             — an indented "- item" list-continuation
                                   line; `text` has its own trailing comment
                                   cut and surrounding quotes stripped
      ("key", key, value)        — a "key: value" line; `key` is
                                   whitespace-tolerant on both sides of the
                                   colon (`owner : x`, `  owner: x`, and
                                   `owner: x` all normalise to key="owner"
                                   — the EXACT normalisation
                                   `_parse_frontmatter` applies); `value`
                                   has its trailing comment cut and is
                                   stripped, and — unless it is an inline
                                   `[a, b]` list — has its surrounding
                                   quotes stripped too
      ("other",)                 — none of the above (no ":" and not
                                   blank/comment/item) — never raises on a
                                   line that doesn't fit any known shape
    """
    if raw.rstrip() == "---":
        return ("fence",)
    if not raw.strip():
        return ("blank",)
    stripped = raw.lstrip()
    if stripped.startswith("#"):
        return ("comment",)
    if stripped.startswith("- "):
        text = _strip_unquoted_comment(stripped[2:].strip()).strip()
        return ("item", text.strip("\"'"))
    if ":" in raw:
        key, _, val = raw.partition(":")
        key = key.strip()
        val = _strip_unquoted_comment(val.strip()).strip()
        if not (val.startswith("[") and val.endswith("]")):
            val = val.strip("\"'")
        return ("key", key, val)
    return ("other",)

def _find_fences(lines: list[str]) -> tuple[int, int] | None:
    """Given `lines` (from `text.splitlines(keepends=True)`), locates the
    frontmatter's opening and closing fence lines by classifying each one
    with `_classify_fm_line` — THE ONE place both `_parse_frontmatter` and
    `_write_owner` decide where the frontmatter starts and ends, so a line
    that is a fence to one is a fence to the other, always (previously the
    parser used `text.startswith("---")` + `text.find("\n---", 3)` — a
    PREFIX match that accepted "----" as an opening fence and closed on the
    first line merely STARTING with "---" — while the writer's classifier
    required the whole trimmed line to equal "---"; the two could locate
    different boundaries in the same file).

    Returns `(open_idx, close_idx)`, or `None` if the file doesn't open
    with a fence or has no matching close. A line the classifier does not
    accept as a fence — "----" (four dashes), an indented "  ---", or
    "--- trailing text" — is not a fence for EITHER consumer: a file that
    OPENS with one has no frontmatter at all (both `--check` and `--assign`
    now refuse it, matching what `load_epics` already reports), and an
    INTERIOR one is ordinary content, never a premature close."""
    if not lines or _classify_fm_line(_line_content(lines[0]))[0] != "fence":
        return None
    close_idx = next(
        (idx for idx in range(1, len(lines))
         if _classify_fm_line(_line_content(lines[idx]))[0] == "fence"),
        None,
    )
    if close_idx is None:
        return None
    return 0, close_idx

def _collect_block_items(lines: list[str], start: int) -> tuple[list[str], int]:
    """From `lines[start]` (one line PAST a `key:` with an empty value),
    collects "  - item" continuation lines via `_classify_fm_line` —
    tolerating interior blank lines and full-line comments (indented or
    not), which are skipped rather than treated as block-enders. The block
    ends at the first line that classifies as anything other than blank,
    comment, or item. Returns `([], start)` when there is no such block."""
    items: list[str] = []
    j = start
    while j < len(lines):
        kind, *rest = _classify_fm_line(lines[j])
        if kind == "item":
            items.append(rest[0])
            j += 1
            continue
        if kind in ("blank", "comment"):
            j += 1
            continue
        break
    return items, j

def _parse_frontmatter(text: str) -> dict | None:
    """Minimal flat-YAML frontmatter parser (scalars + inline [a, b] lists, PLUS
    multi-line block lists — `key:` on its own line followed by `  - item`
    lines, blank lines and full-line comments tolerated between items).
    Every physical line is classified once by `_classify_fm_line` — the
    SAME classifier `_write_owner` uses for placement/replacement, and the
    frontmatter's own boundary is found by the SAME `_find_fences` the
    writer uses too — so the two can never disagree about what a given
    line IS, or where the frontmatter starts and ends. Avoids a PyYAML
    dependency — the schema is intentionally flat.

    Last-wins on a DUPLICATE key — a second `owner:` line overwrites the
    first. `_write_owner` disagrees (it only ever updates the FIRST such
    line), so a duplicate key is recorded under `_dup_keys` (a list) rather
    than silently resolved one way or the other; the caller
    (`check_integrity`) turns `"owner" in fm["_dup_keys"]` into a finding
    that makes `--assign`/`--check --owners` refuse instead of the writer
    and reader each acting on a different one of the two values."""
    lines_with_ends = text.splitlines(keepends=True)
    fences = _find_fences(lines_with_ends)
    if fences is None:
        return None
    open_idx, close_idx = fences
    fm: dict = {}
    dup_keys: list[str] = []
    lines = [_line_content(ln) for ln in lines_with_ends[open_idx + 1 : close_idx]]
    i = 0
    while i < len(lines):
        kind, *rest = _classify_fm_line(lines[i])
        if kind != "key":
            i += 1
            continue
        key, val = rest
        if key in fm and key not in dup_keys:
            dup_keys.append(key)
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            items = [x.strip().strip("\"'") for x in inner.split(",")] if inner else []
            fm[key] = [x for x in items if x != ""]
            i += 1
        elif val == "":
            # A block-style YAML list: "key:" alone, then indented "  - item"
            # continuation lines — valid ONLY for the three declared list
            # fields (_LIST_KEYS). The same shape under any other key is
            # recorded as `_malformed_keys` (never silently promoted to a
            # list) and the field falls back to "", matching what an
            # ordinary empty scalar already does.
            items, j = _collect_block_items(lines, i + 1)
            if key in _LIST_KEYS:
                if items:
                    fm[key] = items
                    i = j
                else:
                    fm[key] = ""
                    i += 1
            else:
                fm[key] = ""
                if items:
                    fm.setdefault("_malformed_keys", []).append(key)
                    i = j
                else:
                    i += 1
        else:
            fm[key] = val
            i += 1
    if dup_keys:
        fm["_dup_keys"] = dup_keys
    return fm
# fmt: on


def _epic_containment(
    raw_headers: list[str],
    plan_dir: Path,
    spine: Path,
    tickets: dict[str, Ticket],
    scope_paths: list[str],
    external_root: Path | None,
) -> list[CheckResult]:
    """BOTH links of the epic contract (spec § Chain consolidation (e)): every ticket's
    Touches ⊆ the spine's File Scope ⊆ the epic's ``owned_paths``.

    The File-Scope link is not optional: with only the ticket link a spine can widen past
    its epic and still pass — and the spine's File Scope is exactly what MINTS the plan
    lock's `owned_paths`, so the widened scope would then be locked. An unresolvable
    header or an epic with no `owned_paths` is an ERROR naming the path, never silence: a
    header the check cannot read is containment that never ran, the fail-open this rule
    exists to close.
    """
    results: list[CheckResult] = []
    # ONE epic per plan (the hint below promises it). First-wins on two headers is a
    # silent fail-open: the second epic's scope is never enforced, and a ticket outside it
    # dispatches clean. Distinct TOKENS, so a repeated identical line is not an error —
    # and `X` / `X/` are the SAME file, so the trailing slash is off before the set (as
    # backticks and `./` already are, via `_norm_path`).
    tokens = list(dict.fromkeys(_norm_path(h).rstrip("/") for h in raw_headers))
    # An EMPTY token is not an epic: since a valueless `Epic:` line parses (deliberately —
    # see EPIC_HEADER_RE), any `Epic:`-shaped prose bullet beside a correct header would
    # otherwise read as a SECOND epic, take the early return, and skip containment
    # entirely — a clean spine hard-redding while the rule stops running. The valueless
    # line still fails closed when it is the only one: `real` is empty, `epic_rel` is "",
    # and the unusable-path arm below fires.
    real = [t for t in tokens if t]
    if len(real) > 1:
        return [
            _err(
                f"spine carries {len(real)} different Epic: headers "
                f"({', '.join(real)}) — one epic per plan",
                spine,
                hint="Split the plan, or name the single epic it was fed — containment "
                "cannot enforce two scopes at once",
            )
        ]
    epic_rel = real[0] if real else ""  # "" -> the unusable-path ERROR below
    if (
        not epic_rel
        or epic_rel.startswith(("/", "~"))
        or ".." in Path(epic_rel).parts
        or _RESIDUE_RE.search(epic_rel)
        or any(ch in epic_rel for ch in "*?")
    ):
        return [
            _err(
                # The ADJUDICATED token, not the first line: with a valueless line FIRST
                # and the offending header second, `raw_headers[0]` is "" and the message
                # sent the author to the wrong line while still hard-redding. Same class as
                # `_unusable_owned`'s empty-entry arm.
                f"Epic: header path '{(epic_rel or raw_headers[0]).strip()}' is unusable — one "
                "repo-relative `docs/development/epics/<file>` path per spine",
                spine,
                hint="An epic header the check cannot resolve is epic containment "
                "silently not running",
            )
        ]
    # The root is resolvable here BY CONSTRUCTION: `_repo_root` returns None only for a
    # dir outside the plans layout, and `check_plan_dir` already returned early for such a
    # dir unless an `external_root` was passed. Narrowed with `cast` rather than a runtime
    # `if root is None:` arm — that arm could never fire, and unreachable defensive code on
    # a fleet-synced surface reads as a real branch to every future editor.
    root = cast(Path, external_root if external_root is not None else _repo_root(plan_dir))
    epic_file = root / epic_rel
    if not epic_file.is_file():
        return [
            _err(
                f"Epic: header names '{epic_rel}' — no such file under {root} (epic "
                "containment cannot run)",
                spine,
                hint="Name the epic file the plan was fed, or drop the header if this "
                "plan is not epic-born",
            )
        ]
    try:
        fm = _parse_frontmatter(epic_file.read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        return [_err(f"epic '{epic_rel}' is unreadable ({e!r}) — containment cannot run", spine)]
    if "owned_paths" in (fm or {}).get("_dup_keys", []):
        # The ported parser RECORDS the duplicate instead of resolving it. Last-wins would
        # accuse every ticket the FIRST list covers — a believable false accusation.
        return [
            _err(
                f"epic '{epic_rel}' declares owned_paths twice — containment cannot pick "
                "one (last-wins would accuse every ticket the first list covers)",
                spine,
                hint="Merge the two declarations into a single owned_paths line",
            )
        ]
    raw_owned = (fm or {}).get("owned_paths", [])
    if isinstance(raw_owned, str):
        # A scalar `owned_paths: "src/a/**"` is ONE entry; a scalar that is blank is no
        # declaration at all (`owned_paths:` with nothing after it, or `""`), and must keep
        # reading as "carries no owned_paths" rather than as one malformed entry.
        raw_owned = [raw_owned] if raw_owned.strip() else []
    # Normalised but NOT filtered: an entry that is blank, or that normalises to nothing,
    # is a MALFORMED entry and `_unusable_owned` names it. Dropping it here reported the
    # epic as declaring no owned_paths at all — which is what the `if str(o).strip()` this
    # replaces did to a BLANK BLOCK-LIST ITEM (`- ` on its own line, which the block parser
    # preserves and the inline splitter never produces, so it hid behind the inline path).
    owned = [_norm_glob(str(o)) for o in raw_owned]
    if not owned:
        return [
            _err(
                f"epic '{epic_rel}' carries no owned_paths frontmatter — epic containment "
                "cannot run",
                spine,
                hint='EPIC-ARTIFACT-SCHEMA.md: `owned_paths: ["src/x/**"]` is the '
                "concurrency contract every epic declares",
            )
        ]
    unusable = [(o, why) for o in owned if (why := _unusable_owned(o))]
    if unusable:
        # A `[seq]` class, an absolute or `~`-rooted path, a `..` traversal, a `\`
        # separator, an empty `//` segment, a bare `.` — each matches NOTHING here, and a
        # matcher that matches nothing accuses EVERY ticket the epic owns. That is the
        # fail direction this file already rejected for `[seq]`, applied to the whole
        # class: name the malformed entry once instead of four believable accusations.
        # Refusing is safe because none of these is a live shape: 0 of the 45 live
        # `owned_paths` values carries one (the same denominator that justified
        # normalising `./`), while the TICKET side keeps reading `[id]` as the literal
        # Next.js/Expo route dir it is (all 8 bracket tokens among the 1,007
        # Touches/File-Scope tokens in the 15 live non-archived plan sets, 7 repos).
        return [
            _err(
                f"epic '{epic_rel}' owned_paths entry "
                + "; ".join(f"'{o}' is unusable — {why}" for o, why in unusable[:3])
                + (f" (+{len(unusable) - 3} more)" if len(unusable) > 3 else "")
                + " — containment cannot run",
                spine,
                hint="owned_paths are repo-relative `/`-separated globs "
                '(`["src/x/**", "db/schema.sql"]`); spell alternatives as separate '
                "entries rather than a bracket class",
            )
        ]
    shown = ", ".join(owned[:5]) + (f", +{len(owned) - 5} more" if len(owned) > 5 else "")
    for t in sorted(tickets.values(), key=lambda t: t.tid):
        for p in t.touches:
            if _carved_out(p):
                continue
            if not any(_glob_covers(o, p) for o in owned):
                results.append(
                    _err(
                        f"{t.tid}: Touches path '{p}' is outside the epic's owned_paths "
                        f"({epic_rel}: {shown})",
                        t.path,
                        hint="Narrow the ticket to the epic's paths — widening "
                        "owned_paths is an epic-contract change (it breaks the "
                        "disjointness the parallel epics were assigned on), never a "
                        "build addendum",
                    )
                )
    for s in scope_paths:
        if _carved_out(s):
            continue
        if not any(_glob_covers(o, s) for o in owned):
            results.append(
                _err(
                    f"File Scope entry '{s}' is outside the epic's owned_paths "
                    f"({epic_rel}: {shown})",
                    spine,
                    hint="File Scope MINTS the plan lock's owned_paths — an entry the "
                    "epic does not own locks paths outside this window's epic",
                )
            )
    return results


def check_plan_dir(
    plan_dir: Path, context: str = "cli", external_root: Path | None = None
) -> list[CheckResult]:
    """Dir-level plan-set validation. context ∈ {'cli','gate','flip'} (severity).

    `external_root` is the repo the set's Touches/Context-Files paths resolve against when the
    set is NOT under `docs/development/plans/` — a scratch copy, checked with `--allow-external`.
    Without it this function returned `[]` for any such dir, so the flag its own error message
    recommends ("checking a scratch copy? pass --allow-external") turned off EVERY check here,
    not merely the containment one. Measured 2026-09-05 on a copy of the live 33-ticket set with
    its spine DELETED: exit 0, zero bytes of output, where the same set in place ERRORs. Intel
    reported the read-budget half (01M1Q1FNBKYW4BM1F2H5Q8HWV0); the early return is the whole of it.
    """
    plan_dir = plan_dir.resolve()
    if _is_archived(plan_dir):
        return []
    if not PLAN_DIR_NAME_RE.match(plan_dir.name):
        return []
    if external_root is None and not _is_plans_layout(plan_dir):
        return []
    results: list[CheckResult] = []
    spine = plan_dir / f"{plan_dir.name}.md"
    if not spine.is_file():
        # Gate path: a ticket-first set mid-authoring is the most draft-like state
        # there is (check_plan_quality documents the same) — advisory, never a
        # hard red on a sibling's in-flight work. Full ERROR at cli/flip.
        return [
            _err(
                f"dated plan directory has no same-stem spine ({spine.name})",
                plan_dir,
                severity=Severity.WARN if context == "gate" else Severity.ERROR,
                hint="The spine file name must equal the directory name — four gates key on it",
            )
        ]
    spine_text = spine.read_text(encoding="utf-8", errors="replace")
    # Fence-stripped for ALL semantic scans (a spine documenting its own emitted
    # ticket template must not read the template's `Status: DRAFT` as its own —
    # that would silently downgrade the whole contract to advisory).
    spine_scan = _strip_fences(spine_text)
    # Spine-status DETERMINATION reads a blockquote-stripped scan on top of the
    # fence strip: quoted content — fenced OR `>`-blockquoted — must never be
    # the spine's own status. STATUS_RE itself keeps `>` (byte-parity with
    # check_convergence/check_plan_quality/docs_updater, where parsing a quoted
    # Status fails CLOSED); but HERE parsing more Status lines produces FEWER
    # findings (the DRAFT/PLANNED downgrade), so a blockquoted `> Status: DRAFT`
    # example above the real line would silently make the whole contract
    # advisory — the strip closes that fail-open direction at the consumer,
    # not the regex.
    status_scan = _BLOCKQUOTE_RE.sub("", spine_scan)
    status_m = STATUS_RE.search(status_scan)
    spine_status = status_m.group(1).upper() if status_m else ""
    # A PRESENT-but-unrecognized Status (`Status: COMPLETE`, `Status: Done ✅`, a
    # typo) must FAIL CLOSED — inheriting the absent-status DRAFT protection
    # would let one bad token silence the whole contract at the gate.
    _any_status = re.search(
        r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\S", status_scan, re.M
    )
    if _any_status and not status_m:
        spine_status = "UNRECOGNIZED"  # not in any downgrade set → full severity

    tickets: dict[str, Ticket] = {}
    for f in sorted(plan_dir.glob("*.md")):
        m = TICKET_FILE_RE.match(f.name)
        if m:
            if m.group(1) in tickets:
                results.append(
                    _err(
                        f"duplicate ticket ID {m.group(1)}: {tickets[m.group(1)].path.name} "
                        f"and {f.name} — the later file would silently shadow the earlier",
                        f,
                    )
                )
                continue
            tickets[m.group(1)] = _parse_ticket(f)
    if spine_status == "UNRECOGNIZED":
        results.append(
            _err(
                "spine Status is not a pipeline value "
                "(DRAFT|PLANNED|CONVERGED|IN-PROGRESS|EXECUTED|BLOCKED)",
                spine,
                hint="Fix the Status: line — an unrecognized value fails closed",
            )
        )

    # --- Structure: Board rows ↔ ticket files 1:1 (Board-section-scoped) -------
    board = BOARD_SECTION_RE.search(spine_scan)
    row_ids = [m.group(1) for m in BOARD_ROW_RE.finditer(board.group(1))] if board else []
    if len(row_ids) != len(set(row_ids)):
        dupes = sorted({r for r in row_ids if row_ids.count(r) > 1})
        results.append(
            _err(
                f"duplicate Ticket Board row(s): {', '.join(dupes)}",
                spine,
                hint="The LAST row wins in the state map — a stale duplicate silently "
                "masks the real state and disables the never-flipped staleness check",
            )
        )
    for rid in dict.fromkeys(row_ids):
        if rid not in tickets:
            results.append(_err(f"Board row {rid} has no ticket file on disk (orphan row)", spine))
    for tid in tickets:
        if tid not in row_ids:
            results.append(_err(f"ticket file {tid} has no Ticket Board row", spine))

    # --- Depends graph + Merge Order -------------------------------------------
    for t in tickets.values():
        for d in t.depends:
            if d not in tickets:
                results.append(
                    _err(
                        f"{t.tid}: Depends on unknown ticket {d} (no such ticket file)",
                        t.path,
                    )
                )
    edges = {t.tid: [d for d in t.depends if d in tickets] for t in tickets.values()}
    if _find_cycle(edges):
        results.append(_err("Depends: graph has a cycle", spine))
    mo_match = MERGE_ORDER_SECTION_RE.search(spine_scan)
    order = ORDER_LINE_RE.findall(mo_match.group(1)) if mo_match else []
    if len(order) != len(set(order)):
        dupes = sorted({o for o in order if order.count(o) > 1})
        results.append(
            _err(
                f"duplicate Merge Order entry(ies): {', '.join(dupes)}",
                spine,
                hint="Last-wins positions would silently defeat the topological "
                "and Integration-last checks (same class as a duplicate Board row)",
            )
        )
    # FIRST occurrence wins — a stale duplicate must not shift positions.
    pos: dict[str, int] = {}
    for i, tid in enumerate(order):
        pos.setdefault(tid, i)
    if set(order) != set(tickets):
        results.append(
            _err(
                "Merge Order does not list exactly the ticket set "
                f"(order={order}, tickets={sorted(tickets)})",
                spine,
            )
        )
    else:
        for t in tickets.values():
            for d in t.depends:
                if d in pos and pos[d] > pos[t.tid]:
                    results.append(
                        _err(f"Merge Order is not topological: {t.tid} depends on {d}", spine)
                    )

    # --- Integration cardinality + position -------------------------------------
    integrations = [t.tid for t in tickets.values() if t.integration]
    if len(integrations) != 1:
        results.append(
            _err(
                f"exactly one 'Integration: true' ticket required (found {len(integrations)})",
                spine,
            )
        )
    elif order and order[-1] != integrations[0]:
        results.append(
            _err(f"Integration ticket {integrations[0]} must be LAST in Merge Order", spine)
        )

    # --- Ownership (OVERLAP-aware: dir-vs-file covered, not just exact match) ----
    # Each row is ONE licence (list of sets) — unioning rows would silently
    # license cross pairs the author never serialized together.
    serialized: dict[str, list[set[str]]] = {}
    if mo_match:
        for pm in SERIALIZED_LINE_RE.finditer(mo_match.group(1)):
            ser_key = _norm_path(pm.group(1).strip("*"))
            if (
                _RESIDUE_RE.search(ser_key)
                or any(ch in ser_key for ch in "*?")
                or ser_key.rstrip("/") == "."
            ):
                results.append(
                    _err(
                        f"Serialized row path '{ser_key}' carries residue — the row is "
                        "VOID (it can never match a Touches path)",
                        spine,
                        severity=Severity.WARN,
                    )
                )
                continue
            # Each row appended as its OWN licence — never unioned (that would
            # license cross pairs) and never last-wins-dropped.
            serialized.setdefault(ser_key, []).append(set(TICKET_ID_RE.findall(pm.group(2))))
    ticket_list = sorted(tickets.values(), key=lambda t: t.tid)
    for i, ta in enumerate(ticket_list):
        for tb in ticket_list[i + 1 :]:
            if _depends_connected(ta.tid, tb.tid, edges):
                continue
            pair_overlaps: list[str] = []
            for pa in ta.touches:
                for pb in tb.touches:
                    if not _path_covers(pa, pb):
                        continue
                    # Serialized licence: the PAIR must sit inside ONE row whose
                    # path covers (or is covered by) either overlap side —
                    # covering-aware like every other path predicate here, and
                    # never a union across rows (that would license cross pairs
                    # the author never serialized together).
                    # DIRECTIONAL: the row's path must COVER an overlap side —
                    # symmetric matching would let a single-file row disable
                    # the collision guard for a whole dir Touches entry.
                    lic_rows = [
                        s
                        for key, rows in serialized.items()
                        for s in rows
                        if _covered_by(key, pa) or _covered_by(key, pb)
                    ]
                    if any({ta.tid, tb.tid} <= s for s in lic_rows):
                        continue
                    pair_overlaps.append(pa if pa == pb else f"{pa} ~ {pb}")
            if pair_overlaps:
                # ONE finding per ticket pair (a dir-vs-many-files overlap must
                # not emit 20 identical-cause lines).
                sample = ", ".join(pair_overlaps[:3])
                more = f" (+{len(pair_overlaps) - 3} more)" if len(pair_overlaps) > 3 else ""
                results.append(
                    _err(
                        f"Touches overlap between {ta.tid} and {tb.tid} with no Depends "
                        f"path and no Serialized: row — {sample}{more}",
                        spine,
                        hint="Serialize the pair (Serialized: <path> — <ids>) or connect "
                        "them with a Depends edge",
                    )
                )
    for t in tickets.values():
        for p in t.touches:
            if p.rstrip("/") == ".":
                results.append(
                    _err(
                        f"{t.tid}: repo-root token '{p}' in Touches — not a literal "
                        "ownership path (it covers nothing in the ownership predicates)",
                        t.path,
                    )
                )
                continue
            # Opaque tokens (glob metachars, incl. asymmetric-emphasis residue
            # like `**secrets/x` — _norm_path strips symmetric wraps only) are
            # invisible to the never-route, governance and overlap predicates.
            # That makes them an ERROR, not advice: a WARN here would let a
            # secrets path ride to the pool on an ignorable line. `[` is NOT a
            # metachar: Next.js/Expo dynamic-route dirs (`[id]`) are literal.
            if any(ch in p for ch in "*?"):
                results.append(
                    _err(
                        f"{t.tid}: glob '{p}' in Touches — literal paths / dir/ entries only",
                        t.path,
                        hint="An opaque token disables the never-route, governance and "
                        "overlap checks for that path — spell it literally",
                    )
                )
                continue
            if _RESIDUE_RE.search(p):
                results.append(
                    _err(
                        f"{t.tid}: unparseable token '{p}' in Touches — quote/backtick/"
                        "separator residue survives normalization and matches nothing "
                        "in the ownership predicates",
                        t.path,
                        hint="One bare path per bullet — a comma list drops every path "
                        "after the first from ALL checks",
                    )
                )
                continue
            # A recursive glob like `**/secrets/**` is SYMMETRIC bold to the
            # normalizer and collapses to the absolute `/secrets/` — absolute
            # tokens are an ERROR (they also evade never-route's relative
            # prefixes and would let the sizing walker escape the repo root).
            # `~` and `..` tokens are the same class: a ticket's WRITE set can
            # never legitimately leave the repo.
            if p.startswith("/") or p.startswith("~") or ".." in Path(p).parts:
                results.append(
                    _err(
                        f"{t.tid}: out-of-repo path '{p}' in Touches — repo-relative only "
                        "(absolute/~/.. tokens escape every ownership predicate; a "
                        "`**/x/**` recursive glob normalizes to the absolute shape)",
                        t.path,
                    )
                )
                continue
            if any(_covered_by(p, g) for g in _GOV_SURFACES):
                results.append(
                    _err(
                        f"{t.tid}: governance file '{p}' in Touches — it is "
                        "orchestrator-applied via the Deltas block",
                        t.path,
                        hint="A file: list it in Context Files (reads are unrestricted) — "
                        "the orchestrator applies the entry at merge. A directory entry "
                        "covering a governance file: enumerate the doc paths instead",
                    )
                )
                continue
            # The whole plan-set territory is the ORCHESTRATOR's write surface —
            # the spine/Board is flipped by the orchestrator (same-commit
            # discipline) and sibling tickets are never a coder's to edit.
            # Own-stem included, deliberately.
            if _covered_by("docs/development/plans/", p) or _covered_by(
                p, "docs/development/plans/"
            ):
                results.append(
                    _err(
                        f"{t.tid}: plan-set territory '{p}' in Touches — the spine, Board "
                        "and ticket files are the orchestrator's write surface, never a "
                        "ticket's",
                        t.path,
                    )
                )
                continue
            # The plan's OWN lock is the ORCHESTRATOR's write surface — a ticket
            # racing the lock writer is never legal, own-stem or not.
            if p.startswith(".fabrik/plan-locks/") and p.rstrip("/").endswith(
                "/" + plan_dir.name + ".json"
            ):
                results.append(
                    _err(
                        f"{t.tid}: the plan lock '{p}' in Touches — the lock is "
                        "orchestrator-owned, never a ticket's write set",
                        t.path,
                    )
                )
                continue
            # Metadata prefixes are per-plan territory: a ticket may own ONLY
            # its own plan's artifacts there (else it writes every sibling's
            # lock or another plan's review). Bidirectional _covered_by — a
            # slash-less `.fabrik/plan-locks` or an ancestor `docs/development/`
            # must not slip past a raw startswith.
            if not _stem_scoped(p, plan_dir) and any(
                _covered_by(p, x) or _covered_by(x, p) for x in _SPINE_METADATA_PREFIXES
            ):
                results.append(
                    _err(
                        f"{t.tid}: metadata path '{p}' outside this plan's stem — a ticket "
                        "owns only its OWN plan's review/lock artifacts",
                        t.path,
                        hint="An ancestor dir (docs/development/) COVERS the metadata "
                        "territory — name the specific non-metadata subpaths instead",
                    )
                )

    scope_section = _section(spine_scan, "File Scope")
    scope_paths = _list_paths(scope_section)
    if scope_section.strip() and not scope_paths:
        results.append(
            _err(
                "File Scope section is not parseable as a path list (use bullets or "
                "numbered entries) — containment checks are OFF until it parses",
                spine,
                severity=Severity.WARN,
            )
        )
    if scope_paths:
        for t in tickets.values():
            for p in t.touches:
                # A governance-banned, glob, absolute or metadata-prefixed path
                # already got its dedicated ERROR above (or its stem-scoped
                # skip) — a containment ERROR on top would prescribe a fix that
                # is itself an ERROR ("add it to File Scope"). ONE predicate,
                # shared with the epic-containment loops: this block and
                # `_carved_out` were verbatim twins on a fleet-synced file.
                if _carved_out(p):
                    continue
                # DIRECTIONAL: a scope entry must cover the Touches path. The
                # symmetric test would let `Touches: src/` pass against a
                # one-file scope (the subset invariant inverted).
                if not any(_covered_by(s, p) for s in scope_paths):
                    results.append(
                        _err(f"{t.tid}: Touches path '{p}' is outside the spine File Scope", t.path)
                    )
        all_touches = [p for t in tickets.values() for p in t.touches]
        for s in scope_paths:
            if s.rstrip("/") == ".":
                results.append(
                    _err(f"repo-root token '{s}' in File Scope — not a literal path", spine)
                )
                continue
            if any(ch in s for ch in "*?"):
                results.append(
                    _err(
                        f"glob '{s}' in File Scope — literal paths / dir/ entries only "
                        "(a glob is opaque to containment, the lock, and this check)",
                        spine,
                    )
                )
                continue
            if _RESIDUE_RE.search(s):
                results.append(
                    _err(
                        f"unparseable token '{s}' in File Scope — quote/backtick/"
                        "separator residue matches nothing in containment or the lock",
                        spine,
                    )
                )
                continue
            if s.startswith(("/", "~")) or ".." in Path(s).parts:
                results.append(
                    _err(
                        f"out-of-repo path '{s}' in File Scope — repo-relative only "
                        "(absolute/~/.. tokens cannot feed the lock; a `**/x/**` "
                        "recursive glob normalizes to the absolute shape)",
                        spine,
                    )
                )
                continue
            # Governance surfaces are dir-aware here too: `docs/` covers the
            # three docs/ surfaces (four tuple members incl. the lowercase
            # alias); next() names only the FIRST hit. A DEDICATED ERROR (not
            # silence, not the misleading orphan message) — these stay OUT of
            # File Scope, or the lock re-creates the BLOCK-on-overlap the
            # carve-out prevents. `projects/foo/CHANGELOG.md` is ownable.
            # ERROR, not WARN: File Scope is what BUILDS the lock's owned_paths —
            # a governance surface here re-creates the exact BLOCK-on-overlap
            # collision the carve-out prevents, and the emit gate is the only
            # place it surfaces (Tier-2 discards non-error stdout).
            gov_hit = next((g for g in _GOV_SURFACES if _covered_by(s, g)), None)
            if gov_hit:
                results.append(
                    _err(
                        f"governance surface '{gov_hit}' inside File Scope entry '{s}' — "
                        "governance files stay OUT of File Scope (outside the lock by design)",
                        spine,
                        hint="An exact entry: delete the line. A directory entry "
                        "covering a governance file: enumerate the non-governance "
                        "doc paths instead",
                    )
                )
                continue
            # Same lock-feeding rationale as governance: metadata territory in
            # File Scope (foreign-stem or over-broad) would put every sibling's
            # plan/review/lock into owned_paths.
            if not _stem_scoped(s, plan_dir) and any(
                _covered_by(s, x) or _covered_by(x, s) for x in _SPINE_METADATA_PREFIXES
            ):
                results.append(
                    _err(
                        f"metadata territory '{s}' in File Scope — only this plan's OWN "
                        "stem-named artifacts belong here (the lock would own every "
                        "sibling plan)",
                        spine,
                    )
                )
                continue
            if any(_covered_by(x, s) for x in _SPINE_METADATA_PREFIXES) and _stem_scoped(
                s, plan_dir
            ):
                continue  # the plan's OWN metadata artifacts, stem-bounded
            if not any(_path_covers(s, p) or _path_covers(p, s) for p in all_touches):
                results.append(
                    _err(
                        f"File Scope path '{s}' is owned by no ticket",
                        spine,
                        severity=Severity.WARN,
                    )
                )

    # --- Epic containment: Touches ⊆ File Scope ⊆ the epic's owned_paths ---------------
    # Only for an epic-born plan — a spine with no `Epic:` header is untouched by this
    # block, and the File-Scope containment above is unchanged either way. Runs even when
    # File Scope is missing or unparseable: the ticket link is independent of it.
    # `finditer` + the NAMED group, never `findall`: the symmetric peel needs a capturing
    # `em` group for its backreference, and `findall` would hand back (em, path) TUPLES.
    _epic_headers = [m.group("path") for m in EPIC_HEADER_RE.finditer(spine_scan)]
    if _epic_headers:
        results.extend(
            _epic_containment(_epic_headers, plan_dir, spine, tickets, scope_paths, external_root)
        )

    # --- Routing cross-check ------------------------------------------------------
    # The spine's Global Constraints may EXTEND the never-route set:
    # `Never-Route: <path>` lines (concrete prefixes only).
    # Never-Route lines: whole-remainder capture, ONE coherent parse. A line
    # yields a usable prefix ONLY when it holds exactly one clean repo-relative
    # token; every rejected line draws its dedicated WARN (never silence — this
    # is the routing layer's user extension).
    extra_never_route_list: list[str] = []
    for rest in re.findall(
        r"^\s*(?:[-*>]\s+)?\*{0,2}Never-Route\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*(.*)$",
        _section(spine_scan, "Global Constraints"),
        re.I | re.M,
    ):
        parts = [x for x in re.split(r"[,\s;]+", rest.strip()) if x]
        if not parts:
            results.append(
                _err(
                    "Never-Route line has no path after the label — the line is void",
                    spine,
                    severity=Severity.WARN,
                )
            )
            continue
        if len(parts) != 1:
            results.append(
                _err(
                    f"Never-Route line '{rest.strip()}' is not a single token — one "
                    "concrete prefix per line (the ENTIRE line was dropped; a prose "
                    "sentence after the label counts as multiple tokens)",
                    spine,
                    severity=Severity.WARN,
                )
            )
            continue
        # .strip("*") BEFORE _norm_path: the bold-tolerant label regex can eat a
        # bolded value's LEADING stars; a lone edge-star glob degenerates to its
        # dir prefix here (coverage EXTENDS — fail-closed).
        nr = _norm_path(parts[0].strip("*"))
        if not nr or nr.rstrip("/") == ".":
            results.append(
                _err(
                    "Never-Route line has no usable path after the label — the line is "
                    "void (a repo-root `.` token covers nothing in the matcher)",
                    spine,
                    severity=Severity.WARN,
                )
            )
            continue
        if nr.startswith(("/", "~")) or ".." in Path(nr).parts:
            results.append(
                _err(
                    f"out-of-repo Never-Route token '{nr}' — matches nothing "
                    "(repo-relative prefixes only; `**/x/**` degenerates to this shape)",
                    spine,
                    severity=Severity.WARN,
                )
            )
            continue
        # (Sentence punctuation, balanced quote wraps and backtick residue are
        # resolved by _norm_path's fixpoint above — the arms below see the
        # final token. Paren-WRAPPED single tokens are the recorded residual:
        # parens are legal path chars, so `(vendor/)` is indistinguishable
        # from a literal and silently matches nothing.)
        if _RESIDUE_RE.search(nr):
            results.append(
                _err(
                    f"unparseable Never-Route token '{nr}' — residue survives "
                    "normalization and matches nothing",
                    spine,
                    severity=Severity.WARN,
                )
            )
            continue
        if any(ch in nr for ch in "*?"):
            results.append(
                _err(
                    f"Never-Route entry '{nr}' contains an interior glob — files UNDER "
                    "it are NOT covered (only the exact token, tokens under it, or an "
                    "ancestor-prefix token still match); use the concrete prefix",
                    spine,
                    severity=Severity.WARN,
                )
            )
        extra_never_route_list.append(nr)
    extra_never_route = tuple(extra_never_route_list)
    for t in tickets.values():
        if not t.complexity:
            results.append(
                _err(
                    f"{t.tid}: no parseable Complexity: line — the routing cross-check "
                    "is OFF for this ticket",
                    t.path,
                    # The routing layer's own fail-closed floor: hard at the
                    # emit gate and the flip, advisory on the shared gate path.
                    severity=(Severity.ERROR if context in ("cli", "flip") else Severity.WARN),
                    hint="Write the field bare: `Complexity: simple|complex|native|never-route`",
                )
            )
        if t.complexity and t.complexity not in ("simple", "complex", "native", "never-route"):
            results.append(
                _err(
                    f"{t.tid}: unrecognized Complexity value '{t.complexity}' "
                    "(simple|complex|native|never-route)",
                    t.path,
                    hint="An unknown tier would silently skip the never-route routing check",
                )
            )
        if t.integration and t.complexity in ("simple", "complex"):
            results.append(
                _err(
                    f"{t.tid}: Integration ticket routed to a pool tier "
                    f"(Complexity: {t.complexity}) — receipts run native",
                    t.path,
                    hint="The Integration ticket owns whole-plan gates and reviews; "
                    "set Complexity: native",
                )
            )
        if t.complexity in ("simple", "complex"):
            for p in t.touches:
                if _never_route(p) or any(
                    _covered_by(n, p) or _covered_by(p, n) for n in extra_never_route
                ):
                    results.append(
                        _err(
                            f"{t.tid}: pool-tier ticket (Complexity: {t.complexity}) touches "
                            f"never-route path '{p}' — route it native",
                            t.path,
                            hint="Set the ticket's Complexity to the never-route tier "
                            "(native worktree coder), per 62-using-subagents.md:118-120",
                        )
                    )

    # --- Grounding floor -----------------------------------------------------------
    for t in tickets.values():
        if not t.integration and not PROOF.search(t.text):
            results.append(
                _err(f"{t.tid}: no path:line citation (per-ticket grounding floor)", t.path)
            )

    # --- Sizing ---------------------------------------------------------------------
    # A scratch copy has no plans-layout above it, so `_repo_root` is None and the whole READ
    # budget below silently measured 0 bytes. The caller's --project-root is the honest answer:
    # a copied ticket's Touches paths still name the REAL repo's files.
    root = external_root if external_root is not None else _repo_root(plan_dir)
    sev = _sizing_severity(context, spine_status)
    for t in tickets.values():
        # Context-Files glob WARN binds EVERY ticket (Integration included —
        # its exemption covers budget/citation/caps, not token hygiene).
        for cf in t.context_files:
            if any(ch in cf for ch in "*?"):
                results.append(
                    _err(
                        f"{t.tid}: glob '{cf}' in Context Files — counts 0 bytes toward "
                        "the READ budget (list the real files)",
                        t.path,
                        severity=Severity.WARN,
                    )
                )
            elif _RESIDUE_RE.search(cf):
                results.append(
                    _err(
                        f"{t.tid}: unparseable token '{cf}' in Context Files — counts 0 "
                        "bytes toward the READ budget (a comma list drops EVERY path in "
                        "the bullet)",
                        t.path,
                        severity=Severity.WARN,
                    )
                )
            elif cf.startswith(("/", "~")) or ".." in Path(cf).parts:
                results.append(
                    _err(
                        f"{t.tid}: out-of-repo path '{cf}' in Context Files — counts 0 "
                        "bytes toward the READ budget (use a repo-relative path)",
                        t.path,
                        severity=Severity.WARN,
                    )
                )
        if t.integration:
            continue
        # Per-ENTRY tallies, not just the total: the total says a ticket is too big
        # but not WHICH entry made it so, and the usual culprit is one directory
        # entry silently owning a large subtree. Naming the top entries turns a
        # debugging loop into a read (transdoc, 2026-08-22: a 102KB surprise from
        # `public/i18n/` counted as a subtree).
        per_entry: dict[str, int] = {}
        if root is not None:
            for p in dict.fromkeys(t.touches + t.context_files):
                # Out-of-repo tokens already ERRORed — and `root / "/etc"` would
                # REPLACE root (pathlib absolute-RHS) while `../` climbs out;
                # never walk either.
                if p.startswith(("/", "~")) or ".." in Path(p).parts:
                    continue
                _norm = p.strip().lstrip("./")
                if _norm in BUDGET_EXEMPT_READS:
                    continue  # mandatory shared contract — not this ticket's scope
                if _is_generated_artifact(_norm):
                    continue  # a committed build output is a WRITE, not a read
                fp = root / p.rstrip("/")
                if fp.is_file():
                    per_entry[p] = per_entry.get(p, 0) + fp.stat().st_size
                elif fp.is_dir():
                    # A directory entry owns its subtree — count it (else the
                    # LARGEST tickets score 0 bytes and the budget fails open).
                    for i, sub in enumerate(fp.rglob("*")):
                        if i > 2000:
                            per_entry[p] = (
                                per_entry.get(p, 0) + READ_BUDGET_BYTES + 1
                            )  # runaway dir = OVER budget, decisively
                            break
                        if sub.is_file():
                            per_entry[p] = per_entry.get(p, 0) + sub.stat().st_size
        read_bytes = sum(per_entry.values())
        if read_bytes > READ_BUDGET_BYTES:
            top = sorted(per_entry.items(), key=lambda kv: -kv[1])[:5]
            breakdown = ", ".join(f"{p}={b}" for p, b in top if b)
            omitted = len([b for b in per_entry.values() if b]) - len([b for _, b in top if b])
            if omitted > 0:
                breakdown += f", +{omitted} smaller"
            results.append(
                _err(
                    f"{t.tid}: READ budget {read_bytes} bytes exceeds "
                    f"READ_BUDGET_BYTES={READ_BUDGET_BYTES}"
                    + (f" — largest: {breakdown}" if breakdown else ""),
                    t.path,
                    severity=sev,
                    hint="Split the ticket (author-split T##a/T##b) — a coder cannot hold "
                    "this read set in one context. If ONE file alone exceeds the budget, "
                    "splitting is futile (it divides the ticket, not the file): give that "
                    "file to the set's single `Integration: true` ticket — exempt from this "
                    "budget by design, last in Merge Order — and keep the SET shape "
                    "(youtube 01M1QBPW, 2026-09-05: dashboard/app.py at 1.66x the budget)",
                )
            )
        if len(t.behaviors) > MAX_BEHAVIORS:
            results.append(
                _err(
                    f"{t.tid}: {len(t.behaviors)} behaviors > {MAX_BEHAVIORS}",
                    t.path,
                    severity=Severity.WARN,
                )
            )
        for masked in _gate_masks_exit_status(t.text):
            results.append(
                _err(
                    f"{t.tid}: Gate pipes into a display filter, discarding the exit status of the "
                    f"command under test — {masked!r}. The shell reports the LAST stage and "
                    "tail/head always succeed, so a failing command reads GREEN. Drop the filter, "
                    "or put the assertion last.",
                    t.path,
                )
            )
        if len(GATE_LINE_RE.findall(_strip_fences(t.text))) > MAX_GATES:
            results.append(
                _err(f"{t.tid}: more than {MAX_GATES} Gate: lines", t.path, severity=Severity.WARN)
            )

    # --- Behavior-Contract roll-up equality ------------------------------------------
    spine_rows = {
        _norm_behavior(m) for m in GIVEN_ROW_RE.findall(_section(spine_scan, "Behavior Contract"))
    }
    ticket_rows = {b for t in tickets.values() for b in t.behaviors}
    for missing in sorted(ticket_rows - spine_rows):
        results.append(
            _err(f"spine Behavior Contract roll-up missing a ticket row: {missing[:80]}", spine)
        )
    for extra in sorted(spine_rows - ticket_rows):
        results.append(
            _err(f"spine Behavior Contract roll-up row matches no ticket: {extra[:80]}", spine)
        )

    # --- Board staleness (execution window) --------------------------------------------
    results.extend(_staleness(plan_dir, spine_scan, tickets, external_root=external_root))

    # --- What was graded, and against what -------------------------------------------
    # A clean run used to print ZERO BYTES and exit 0, so "the gate graded 33 tickets and found
    # nothing" was byte-identical to "the gate resolved the wrong directory and did nothing" —
    # and two commands instruct agents to CITE that silence as sizing evidence, which is the
    # un-denominated claim CLAUDE.md § bounded search forbids (intel, 01M1PYS0Y7AZ9W2WS8PPYHT0WK
    # #3 and 01M1KYMG27FMEQXA89A2A4B2ZD #1, after ~20 runs needing `echo $?` to read).
    # PASS rows carry no exit weight and the Tier-2 gate discards stdout on exit 0, so this is
    # visible exactly where it is needed: a pasted --plan-dir result in a convergence artifact.
    # Scoped to the explicit-`--plan-dir` author path ("cli"), which is where the silence is read
    # as evidence. The gate and per-file adapter paths are unchanged: they run over EVERY plan dir
    # in the tree, so a row each would be noise, and final_gate discards their stdout on exit 0.
    if context == "cli":
        _budget = (
            f"READ budget measured against {root}"
            if root is not None
            else "READ budget NOT MEASURED — no repo root resolvable (pass --project-root)"
        )
        results.append(
            _err(
                f"graded {len(tickets)} ticket(s), "
                f"{sum(len(t.touches) for t in tickets.values())} Touches path(s), "
                f"{sum(len(t.context_files) for t in tickets.values())} Context-Files entry(ies); "
                f"{_budget}; "
                f"{len([r for r in results if r.severity is not Severity.PASS])} finding(s)",
                plan_dir,
                severity=Severity.PASS,
            )
        )

    # --- Gate-context DRAFT downgrade (ALL findings, structural included) ---------------
    # DRAFT/PLANNED (or absent-status) = someone's mid-AUTHORING set on shared
    # master → all advisory in the gate path. IN-PROGRESS is deliberately NOT
    # here (plan Behavior 9 scopes its downgrade to SIZING only, via
    # _sizing_severity): mid-EXECUTION structural breakage is the owner's to fix,
    # and the ⬜-with-trailer staleness ERROR only exists in that window — a
    # blanket downgrade would make it unreachable. Sibling protection for
    # IN-PROGRESS sets comes from the lock_only/advisory paths in main()/check_file.
    if context == "gate" and spine_status in _DRAFT_LIKE:
        results = [
            CheckResult(
                check_name=r.check_name,
                severity=Severity.WARN if r.severity.value == "error" else r.severity,
                message=r.message,
                file_path=r.file_path,
                line_number=r.line_number,
                fix_hint=r.fix_hint,
            )
            for r in results
        ]
    return results


def check_file(file_path: Path) -> list[CheckResult]:
    """validate_conventions per-file adapter: dir-level validation ONCE per dir per
    run, attached to the FIRST file seen from that dir; empty for the rest."""
    if file_path.suffix != ".md":
        return []
    plan_dir = file_path.resolve().parent
    if not PLAN_DIR_NAME_RE.match(plan_dir.name):
        return []
    if _is_archived(plan_dir) or not _is_plans_layout(plan_dir):
        return []
    if plan_dir in _SEEN_DIRS:
        return []
    _SEEN_DIRS.add(plan_dir)
    try:
        found = check_plan_dir(plan_dir, context="gate")
    except Exception as e:  # noqa: BLE001 — fail-safe by convention, but observable
        print(f"NOTE: plan_tickets adapter suppressed: {e!r}")
        return []
    # This per-file adapter (the Tier-3 validate_conventions path) sees UNTRACKED
    # files and cannot tell whose plan a dir is — it is ALWAYS advisory. The
    # enforcing paths are the author's CLI, the CONVERGED/EXECUTED flips, and the
    # Tier-2 no-arg CLI (which carries the lock_only sibling logic).
    return [
        CheckResult(
            check_name=r.check_name,
            severity=Severity.WARN if r.severity.value == "error" else r.severity,
            message=r.message,
            file_path=r.file_path,
            line_number=r.line_number,
            fix_hint=r.fix_hint,
        )
        for r in found
    ]


def _discover_dirs(root: Path) -> tuple[list[Path], set[Path]]:
    """No-arg CLI discovery. Returns (dirs, lock_only) where dirs = dated plan dirs
    containing any changed file PLUS plan dirs whose ACTIVE lock's owned paths
    intersect the changed set, and lock_only = the subset selected ONLY via a lock
    (someone ELSE's plan — its findings are downgraded to advisory WARN by the
    caller: a sibling's mid-execution state must never hard-red this session's
    gate on files this session is forbidden to touch)."""
    changed: set[str] = set()
    wt_changed: set[str] = set()  # working-tree/staged only — MY session's edits
    try:
        # Tracked changes only — UNTRACKED files are a sibling's in-flight draft,
        # checked at staging (the check_convergence `??` policy). The change set
        # includes COMMITTED-BUT-UNPUSHED work (upstream..HEAD) — execute-plan
        # commits per phase and THEN runs the gate, so working-tree-only discovery
        # would go blind in the dominant real-world state.
        wt_cmds = [["diff", "--name-only"], ["diff", "--staged", "--name-only"]]
        cmds = list(wt_cmds)
        up = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "@{upstream}"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if up.returncode == 0 and up.stdout.strip():
            cmds.append(["diff", "--name-only", f"{up.stdout.strip()}..HEAD"])
        for args in cmds:
            proc = subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True, timeout=15
            )
            if proc.returncode != 0:
                # Skip THIS command, keep the others (a stale upstream ref must
                # not throw away the working-tree diff results).
                print(
                    f"NOTE: plan_tickets discovery: `git {' '.join(args)}` exit {proc.returncode} — skipped"
                )
                continue
            found_paths = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
            changed.update(found_paths)
            if args in wt_cmds:
                wt_changed.update(found_paths)
    except Exception as e:  # noqa: BLE001
        print(f"NOTE: plan_tickets discovery skipped (git error: {e!r})")
        return [], set()
    # OWN = discovered via MY working-tree/staged edits. A dir seen ONLY via
    # upstream..HEAD is a sibling's committed-but-unpushed work on shared master
    # (the normal state here) — advisory, same as lock-only selection.
    own_dirs: set[Path] = set()
    for c in wt_changed:
        p = Path(c)
        if len(p.parts) >= 4 and p.parts[:3] == ("docs", "development", "plans"):
            if PLAN_DIR_NAME_RE.match(p.parts[3]):
                own_dirs.add(root / "docs" / "development" / "plans" / p.parts[3])
    upstream_dirs: set[Path] = set()
    for c in changed - wt_changed:
        p = Path(c)
        if len(p.parts) >= 4 and p.parts[:3] == ("docs", "development", "plans"):
            if PLAN_DIR_NAME_RE.match(p.parts[3]):
                upstream_dirs.add(root / "docs" / "development" / "plans" / p.parts[3])
    lock_dirs: set[Path] = set()
    locks = root / ".fabrik" / "plan-locks"
    if locks.is_dir():
        for lf in locks.glob("*.json"):
            try:
                data = json.loads(lf.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if data.get("status") != "active":
                continue
            owned = data.get("owned_paths", [])
            if any(any(_path_covers(o, c) for o in owned) for c in changed):
                cand = root / "docs" / "development" / "plans" / lf.stem
                if cand.is_dir():
                    lock_dirs.add(cand)
    dirs = sorted(d for d in own_dirs | lock_dirs | upstream_dirs if d.is_dir())
    advisory = {d for d in (lock_dirs | upstream_dirs) if d not in own_dirs}
    return dirs, advisory


def main() -> int:
    parser = argparse.ArgumentParser(description="Spine↔ticket plan-set contract gate.")
    parser.add_argument("--plan-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--allow-external",
        action="store_true",
        help="With --plan-dir: skip the docs/development/plans/ containment check so a "
        "SCRATCH COPY of a plan set can be checked (gate-liveness red-on-mutation proofs "
        "previously required mutating the real plan file — 01M1DMBS minor). The dated-dir "
        "naming rule still applies; discovery mode ignores this flag.",
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    if args.plan_dir:
        target = args.plan_dir.resolve()
        if target.is_file():
            print(
                f"✗ --plan-dir {args.plan_dir} is a FILE — pass the plan set's DIRECTORY "
                "(monolith .md plans are not checked by this gate)"
            )
            return 1
        if not target.is_dir():
            print(f"✗ --plan-dir {args.plan_dir} does not exist")
            return 1
        if not PLAN_DIR_NAME_RE.match(target.name):
            print(
                f"✗ --plan-dir {args.plan_dir} is not a dated plan directory "
                "(YYYY-MM-DD-plan-<slug>/)"
            )
            return 1
        if not args.allow_external and not _is_plans_layout(target):
            print(
                f"✗ --plan-dir {args.plan_dir} is not under docs/development/plans/ "
                "(checking a scratch copy? pass --allow-external)"
            )
            return 1
        dirs = [target]
        lock_only: set[Path] = set()
        # An external set's paths resolve against --project-root (default: cwd), so the READ
        # budget and every other check actually run on a scratch copy instead of being skipped
        # wholesale by the plans-layout guard.
        external_root = root if not _is_plans_layout(target) else None
        if external_root is not None and root == Path.cwd().resolve():
            # compare RESOLVED paths: `--project-root .` and a symlinked `$(pwd)` both equal the
            # cwd default and must warn the same way (review pass 3, native finder — the raw
            # comparison let both through silently)
            # cwd is the default, and a scratch copy checked from the wrong directory measures
            # every Touches path against the wrong tree — 0 bytes each, the exact silent zero
            # this flag's fix removed, reached by another door (review pass 1, native finder).
            print(
                f"NOTE: --allow-external is resolving Touches/Context-Files against {root} "
                "(the cwd default) — pass --project-root <repo> if that is not the repo the "
                "tickets name"
            )
    else:
        _SEEN_DIRS.clear()  # in-process reuse safety (one logical run per main())
        dirs, lock_only = _discover_dirs(root)
        external_root = None  # discovery only ever yields in-layout dirs
    if not dirs:
        print("no plan directories in scope")
        return 0
    # Explicit --plan-dir = the author's own emit gate → full severity ("cli").
    # No-arg discovery = the shared Tier-2 gate path → "gate" (DRAFT downgrade
    # applies). A dir selected ONLY via a sibling's active lock is that sibling's
    # plan — ALL its findings become advisory WARNs (this session cannot fix them).
    run_context = "cli" if args.plan_dir else "gate"
    all_results: list[CheckResult] = []
    for d in dirs:
        found = check_plan_dir(d, context=run_context, external_root=external_root)
        if d in lock_only:
            found = [
                CheckResult(
                    check_name=r.check_name,
                    severity=Severity.WARN if r.severity.value == "error" else r.severity,
                    message=f"[sibling plan] {r.message}",
                    file_path=r.file_path,
                    line_number=r.line_number,
                    fix_hint=r.fix_hint,
                )
                for r in found
            ]
        all_results.extend(found)
    if args.json:
        print(json.dumps([r.to_dict() for r in all_results], indent=2))
    else:
        for r in all_results:
            icon = {"pass": "✓", "warn": "⚠", "error": "✗"}[r.severity.value]
            print(f"{icon} [{r.check_name}] {r.file_path}: {r.message}")
            if r.fix_hint:
                print(f"  → Fix: {r.fix_hint}")
    return 1 if any(r.severity.value == "error" for r in all_results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
