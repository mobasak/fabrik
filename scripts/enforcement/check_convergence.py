#!/usr/bin/env python3
# AFTER-EDIT: tests/test_check_convergence.py, commands/_sources/fabrik-execute-plan.md, commands/_sources/fabrik-plan-review.md | none
"""Convergence-evidence gate — run by final_gate via run_optional_check (non-zero = fail).

A markdown artifact that CLAIMS convergence must PROVE it. Inspects only
changed/untracked files under the plans/ and reviews/ dirs (cheap — git status
+ regex; safe to run every tier).

  docs/development/plans/*.md   '**Status:** CONVERGED' (or 'zero unknowns')
      -> requires a '## Evidence' section, a self-audit / convergence-floor
         block, >=1 `path:line` citation per Phase/Step, and >=1 non-trivial
         fenced command-output block.
  docs/development/plans/*.md   '**Status:** EXECUTED'  (incl. plans/archived/)
      -> must CITE a persisted whole-plan review artifact
         (docs/development/reviews/*.md) that EXISTS on disk and shows a
         coverage-adjudicated exit (a 'Coverage Checklist' + a final 'found: 0'
         pass). Closes the hole where an agent flips Status: EXECUTED (and
         archives) without the whole-plan /fabrik-review the execute-plan Finish
         mandates ever having run — check_review_coverage.py is INERT when no
         review file exists, so this is what forces one to exist.
  docs/development/reviews/*.md 'reviewed' / 'converged' / 'sign-off'
      -> requires an embedded fenced block containing '"status": "success"'
         (a real `final_gate --json` run) and >=1 per-phase verdict.

Ceiling (by design): this enforces evidence *presence* and mechanical green —
never truth. It makes an unproven convergence claim fail the gate and leaves an
audit trail; whether the cited evidence is *correct* still rests with the
reviewer. The DEPTH of a cited review's checklist adjudication (no UNCHECKED
rows, every class CLEAN/FIXED/REFUTED) is check_review_coverage.py's job when
that review is staged; here we require the review to EXIST and to carry the
adjudicated-exit signature. Direct edits that ship no plan/review artifact are
not covered here — they rely on the rest of final_gate.

Docs convergence is enforced separately by check_doc_sync.py ("Doc Sync Matrix")
+ docs_updater.py --check ("Documentation Drift").
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PLANS_DIR = "docs/development/plans/"
REVIEWS_DIR = "docs/development/reviews/"

# CONVERGED on the Status line — bold-or-plain, colon inside OR outside the bold
# (`Status:`, `**Status:**`, `**Status**:`), and — matching the PRE-tolerance
# behavior exactly — "converged"/"zero unknowns" ANYWHERE on the Status line (a
# `Status: COMPLETE — converged after 3 passes` claim is a convergence claim).
# Enforcement is NEW-TRANSITION-ONLY via _converged_targets (the _executed_targets
# precedent): a file already CONVERGED at HEAD is settled — pre-existing
# CONVERGED plans fleet-wide keep passing unchanged when merely re-touched.
# A convergence CLAIM = a Status line (colon mandatory) whose remainder contains
# "converged" or "zero unknowns" — UNLESS the status VALUE itself is a
# pre-convergence state (DRAFT/PLANNED/IN-PROGRESS): "Status: DRAFT — will be
# converged after review" is not a claim, while "Status: CLEAN-CONVERGED",
# "Status: IMPLEMENTATION-CONVERGED", "Status: 🟢 CONVERGED" and
# "Status: COMPLETE — converged after 3 passes" all are (live operator
# vocabulary). The two-step (line regex + _claims_converged) is what regex alone
# cannot express.
CONVERGED_LINE = re.compile(
    r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*(?P<val>[^\n]*)$",
    re.I | re.M,
)
# Pre-convergence status VALUES (EXACT token match — a prefix test swallowed
# UNBLOCKED/UNIFIED-CONVERGED/NOTED as non-claims, fail-open) + a NEGATION regex
# for disclaimers anywhere on the line ("NOT CONVERGED", "COMPLETE — not
# converged", "never converged", "un-converged").
_NON_CLAIM_TOKENS = frozenset(
    ("draft", "planned", "in-progress", "in_progress", "blocked", "reverted")
)
_NEGATED_CONVERGED = re.compile(
    r"\b(?:not|never|isn'?t|un)\W{0,2}(?:converged|zero unknowns)", re.I
)


def _claims_converged(text: str) -> bool:
    for m in CONVERGED_LINE.finditer(text):
        val = m.group("val").strip().strip("*").strip()
        low = val.lower()
        if not low:
            continue
        stripped = low.lstrip("✅🟢⚠️❌ ")
        first = stripped.split()[0].rstrip(":*—–-") if stripped.split() else ""
        # PRECEDENCE (review round 10): a leading affirmative VALUE wins —
        # `CONVERGED (2 items not converged, deferred)` IS a claim; later-prose
        # negations must not disarm it (fail-open). Then the pre-convergence
        # value tokens, then disclaimers anywhere ("COMPLETE — not converged"),
        # and the SAME guards cover "zero unknowns" (a DRAFT aiming for zero
        # unknowns is not a claim).
        if "converged" in first and not _NEGATED_CONVERGED.search(first):
            return True
        if first in _NON_CLAIM_TOKENS:
            continue
        if _NEGATED_CONVERGED.search(low):
            continue
        if "converged" in low or "zero unknowns" in low:
            return True
    return False


class _ConvergedSearch:
    """CONVERGED.search(text) facade so existing call sites/tests keep working.
    Fence-stripped: a DRAFT plan QUOTING `Status: CONVERGED` in an example block
    is not claiming convergence."""

    @staticmethod
    def search(text: str):
        return _claims_converged(FENCE_STRIP.sub("", text)) or None


CONVERGED = _ConvergedSearch()

# A Pass/Round-labelled ledger line carrying the re-derivation method token. Deliberately
# loose on separators (dash/pipe/colon tables all in the wild) and tight on the two anchors:
# a pass/round label and `re-deriv` within one line.
# D-053: 160-char cap removed — a mandated dispatched/returned manifest before the method cell
# pushed `re-derivation` out of the window (measured: 179-char gap on a compliant row).
_REDERIVATION_ROW = re.compile(r"\b(?:pass|round)\b[^\n]*\bre-?deriv", re.I)
# EXECUTED must be the status VALUE (right after `Status:`), not the word
# "executed" appearing in prose — else a `Status: CLOSED … never executed
# directly` / `Status: Done … was executed unauthorized` line false-positives.
# An optional leading list/quote marker tolerates `- **Status:** EXECUTED`.
# Colon MANDATORY + same-line whitespace only — consistent with every sibling
# status regex in this wave ("Status executed manually" prose must not claim).
EXECUTED = re.compile(
    r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*(?:✅[^\S\n]*)?"
    r"\*{0,2}[^\S\n]*EXECUTED\b",
    re.I | re.M,
)
REVIEW_CITE = re.compile(r"docs/development/reviews/[\w./-]+\.md")
# D4 per-ticket review files (<plan>-T##[a-z]?-review.md): cited by spines
# routinely, but they prove one ticket — never the whole-plan D7 validation.
# Naming-convention-scoped BY DESIGN (this module's ceiling: evidence presence,
# never truth): a MISNAMED per-ticket review evades it, and no false-skip is
# possible — _is_spine requires a lowercase-only dir name ([a-z0-9-]+), so a
# whole-plan review's stem can never contain the uppercase -T## this demands.
_TICKET_REVIEW_RE = re.compile(r"-T\d{2}[a-z]?-review\.md$")
# The /fabrik-review termination signature (term-coverage): a quiet round
# ``found: 0 … fixed: 0``. We require this PAIR to appear *somewhere* — a
# deliberately ZERO-FALSE-POSITIVE signal: a genuinely-converged review ALWAYS
# has one, so this never cries wolf (the failure mode that gets a fleet gate
# ``# noqa``'d — worse than a false-accept). It rejects a prose-only "found:0"
# (no adjacent ``fixed:0``) and a cited review with no quiet round at all. It does
# NOT try to prove the quiet round was the FINAL one — that DEPTH (no UNCHECKED
# rows, every class adjudicated, the loop truly converged) is
# check_review_coverage.py's job when the review is staged. This gate's ceiling
# is evidence PRESENCE, not truth (see module docstring).
# D-053 re-grounding (2026-08-31): the 40-char window made row ORDERING load-bearing — a
# finder manifest between the counters failed an honest quiet round (13-round review proof).
# Same-LINE is the constraint; the gap is not.
QUIET_PASS = re.compile(r"found:\s*0\b[^\n]*?fixed:\s*0\b", re.I)
REVIEWED = re.compile(r"\b(reviewed|converged|sign[- ]?off)\b", re.I)
PHASE = re.compile(r"^#{2,}\s*(Phase|Step)\b", re.I | re.M)
PROOF = re.compile(r"[\w./-]+\.(?:py|ts|tsx|js|sql|md|csv|ya?ml|sh|json):\d+")
EVIDENCE = re.compile(r"^#{2,}\s*Evidence\b", re.I | re.M)
AUDIT = re.compile(r"self[- ]?audit|convergence floor", re.I)
GATE_OK = re.compile(r'"status"\s*:\s*"success"')
# PARSING CONTRACT (recorded, review round 9): fences are BALANCED backtick
# fences — a 3+-backtick opener closed by an EQUAL-length line-start closer —
# plus inline single-line ```…``` quotes. Out of contract (documented, not
# chased): tilde fences, over-long closers, and unpaired line-start fence
# PAIRS — the emitting commands write balanced 3-backtick fences and quote
# templates with 4-backtick outers, both in-contract; no live fleet file
# violates this (verified 2026-08-05).
# Strip-purpose fence regex — newline NOT required (a single-line ```Status: X```
# is still a quote). FENCE_BLOCK below stays as-is for _nontrivial_fences COUNTING.
FENCE_STRIP = re.compile(
    # Line-anchored blocks + inline single-line fences (never bare ```.*?``` —
    # an unpaired backtick in prose swallows real body; see check_plan_tickets).
    r"(?:^[ \t]*(`{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$|```[^`\n]+```)",
    re.M | re.S,
)
# Fenced code blocks — capture inner content so we can demand non-trivial output
# (an empty ``` ``` pair must not satisfy the "show the command output" rule).
FENCE_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.S)
# Fence-CONTENT extraction under the same contract as FENCE_STRIP: balanced
# line-anchored blocks (equal-length backreferenced closer) + inline
# single-line quotes. Group 2 = block body, group 3 = inline body.
_FENCED_CONTENTS = re.compile(
    r"^[ \t]*(`{3,})[^\n]*\n(.*?)^[ \t]*\1[ \t]*$|```([^`\n]+)```",
    re.M | re.S,
)
# Spine+ticket plan-set shape (canonical grammar — single definitions live in the
# 2026-08-04 spine-ticket plan; keep these byte-identical with check_plan_tickets).
PLAN_DIR_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+$")
# Bold-tolerant ID cell (| **T01** | …) — keep in lockstep with check_plan_tickets.
BOARD_ROW = re.compile(r"^\|\s*\**\s*(T\d{2}[a-z]?)\b", re.M)
BOARD_SECTION = re.compile(r"^##\s+Ticket Board\b(.*?)(?=^##\s|\Z)", re.I | re.M | re.S)
TICKET_FILE = re.compile(r"^T\d{2}[a-z]?-[a-z0-9-]+\.md$")
# Colon mandatory + same-line value — prose about statuses (and a bare "Status:"
# label above an indented list) must not trip the ticket Status ban.
ANY_STATUS_LINE = re.compile(r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\S", re.M)


def _is_spine(path: Path) -> bool:
    """A spine = same-stem .md inside a dated plan directory."""
    return bool(PLAN_DIR_NAME.match(path.parent.name)) and path.stem == path.parent.name


def _check_spine_set(root: Path, spine: Path, text: str) -> list[str]:
    """Spine-CONVERGED plan-set checks: Board rows ↔ ticket files (orphans), no
    ticket carries a Status: line, and the full spine↔ticket contract via an
    in-process check_plan_tickets run at FULL severity (a hand-flipped Status must
    fail here, before dispatch). Fail-safe: the in-process import degrades to the
    native checks alone."""
    rel = spine.relative_to(root)
    if "archived" in rel.parts:
        return []  # settled history — never re-enforced
    fails: list[str] = []
    text = FENCE_STRIP.sub("", text)  # fences are quotes — same policy as check_plan_dir
    section = BOARD_SECTION.search(text)
    rows = BOARD_ROW.findall(section.group(1)) if section else []
    ticket_ids_on_disk = {
        f.name.split("-", 1)[0] for f in spine.parent.glob("*.md") if TICKET_FILE.match(f.name)
    }
    for row_id in rows:
        if row_id not in ticket_ids_on_disk:
            fails.append(f"{rel}: Board row {row_id} has no ticket file on disk (orphan row)")
    for f in sorted(spine.parent.glob("*.md")):
        if not TICKET_FILE.match(f.name):
            continue
        if ANY_STATUS_LINE.search(
            FENCE_STRIP.sub("", f.read_text(encoding="utf-8", errors="replace"))
        ):
            fails.append(
                f"{rel}: ticket {f.name} carries a Status: line — ticket state lives ONLY "
                "in the spine Board"
            )
    try:
        try:
            from .check_plan_tickets import check_plan_dir  # package context
        except ImportError:
            import sys as _sys

            _sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from scripts.enforcement.check_plan_tickets import check_plan_dir
        for r in check_plan_dir(spine.parent, context="flip"):
            if r.severity.value == "error" and "orphan row" not in r.message:
                # (orphan rows already reported by the native loop above — no dupes)
                fails.append(f"{rel}: plan-set contract: {r.message}")
    except Exception as e:  # noqa: BLE001 — fail-safe, but observable
        print(f"NOTE: in-process check_plan_tickets skipped at the flip ({e!r})")
    return fails


def _nontrivial_fences(text: str) -> int:
    """Count fenced blocks whose inner content carries real output (>=20 non-ws chars)."""
    return sum(1 for inner in FENCE_BLOCK.findall(text) if len(inner.strip()) >= 20)


# A probe is a fence whose command line starts `$ `; probe duty says re-run it and diff the
# output. A line reading `$ ...` cannot be re-run — the command itself was elided — so it is a
# probe-shaped placeholder that reads as evidence and proves nothing. This check already demanded
# a NON-TRIVIAL fence, which such a block satisfies easily: the elided command sits above real
# pasted output. Filed by tryton-crm 2026-08-28 after three probe defects survived a plan that was
# Status: CONVERGED with check_plan_quality, check_plans, check_convergence and final_gate all
# green. Blast radius, measured CORRECTLY on the second try (tryton-crm corrected the first):
# **0** live hits fleet-wide. The first measurement grepped DOCUMENT TEXT and reported 3 — a PROXY
# for what this check actually SELECTS, which is the mistake this corpus exists to catch, made
# while justifying a change to a BLOCKING check. The 3 all sit in one file that `_changed_md`
# skips (`archived/`) and that `_check_plan` early-returns on (no `CONVERGED` claim). To measure a
# check's blast radius, run its own selection — never grep for the pattern it looks for.
ELIDED_PROBE = re.compile(r"^[ \t]*\$[ \t]+\.\.\.", re.M)


# An EXCERPT must declare itself. A fence body carrying a bare `...` line has been TRIMMED, and
# today that is indistinguishable from complete output — a reader cannot tell "this is everything"
# from "I kept the load-bearing lines", which is the whole defect. Convention proposed by tryton-crm
# (2026-08-28) after I declined to ship their defect 3 for want of a decidable test; theirs is
# decidable from the text alone, fails in the safe direction (a forgotten marker is a finding; a
# spurious one is harmless), and cannot fire on a fence that does not already contain a bare `...`.
# ONE CHANGE to their proposal, forced by the hub's own violation: the marker is a TOKEN in the
# info string, not the whole of it — the first trimmed fence found here was ```python, and
# demanding the info string BE "excerpt" would have traded a language tag for a marker. ```python
# excerpt keeps both.
BARE_ELLIPSIS = re.compile(r"^[ \t]*\.\.\.[ \t]*$", re.M)
_INFO_FENCE = re.compile(r"^[ \t]*(`{3,})([^\n]*)\n(.*?)^[ \t]*\1[ \t]*$", re.M | re.S)


def _unmarked_excerpts(text: str) -> int:
    """Count trimmed fences (a bare `...` line) whose info string is not ``excerpt``."""
    return sum(
        1
        for _, info, body in _INFO_FENCE.findall(text)
        if BARE_ELLIPSIS.search(body) and "excerpt" not in info.split()
    )


def _elided_probes(text: str) -> int:
    """Count `$ ...` command lines inside fenced blocks — probe-shaped, unrunnable."""
    return sum(len(ELIDED_PROBE.findall(inner)) for inner in FENCE_BLOCK.findall(text))


def _changed_md(root: Path, prefix: str) -> list[Path]:
    """Changed/untracked .md files under ``prefix`` (per git status), excluding archived/."""

    def _keep(p: str) -> bool:
        return p.startswith(prefix) and p.endswith(".md") and "archived/" not in p

    try:
        # --untracked-files=all lists individual files even when the parent dir
        # is itself untracked (a fresh/sparse repo collapses to "?? docs/"
        # otherwise, hiding the artifact).
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", prefix],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except Exception:
        return []
    paths: list[Path] = []
    for line in out.splitlines():
        # Shared-master: '??' = untracked AND unstaged — another agent's (or a
        # not-yet-staged) in-flight draft. Convergence proof is enforced at the
        # staging/commit moment (the gate stages your files; the doc rides the
        # phase commit) — never against a sibling session's mid-write scratch.
        # Precedent family: specs/*.yaml.draft; check_synced_unmodified→HEAD.
        if line[:2] == "??":
            p = line[3:].strip()
            if _keep(p):
                print(f"NOTE: skip untracked in-flight draft (checked at staging): {p}")
            continue
        p = line[3:].strip()
        if " -> " in p:  # renamed: "old -> new"
            p = p.split(" -> ", 1)[1]
        if _keep(p):
            paths.append(root / p)
    return paths


def _checklist_fails(text: str, scan: str) -> list[str]:
    """A CONVERGED plan must carry an adjudicated Coverage Checklist derived from the rubric.

    `/fabrik-plan-review` had axes but no CLASS LEDGER to sweep and no RUBRIC to sweep
    against, so its convergence meant "nothing further occurred to the reviewer" rather
    than "every known failure class was swept" — while the plan is precisely where a
    12-Factor violation gets WRITTEN AS A TASK, and the pipeline
    (plan-after-chat -> plan-review -> execute-plan) has no `/fabrik-review` step on the
    plan artifact at all. Measured cost of leaving it unarmed (transdoc, 2026-08-23): an
    out-of-band review of an already-CONVERGED 10-ticket set found 5 further real defects,
    4 of them named EXPLICITLY in the rubric that was never injected.

    Parsing is DELEGATED to check_review_coverage — the same extraction the review branch
    uses, hardened over ~90 rounds against fence seams, 2-cell separator rows and
    verdict-vocabulary headers. A second parser here would drift from it silently, and a
    checklist gate that mis-parses is exactly the fail-silent-green class this row exists
    to close.

    Scope: NEW convergence transitions only, via `_converged_targets` — a plan already
    CONVERGED at HEAD is settled, so pre-existing converged plans fleet-wide keep passing
    unchanged and re-touching one never demands a checklist it was authored without.
    """
    try:
        from .check_review_coverage import (  # noqa: PLC0415 — local: avoids a hard dep
            RUBRIC_RUN,
            UNCHECKED,
            VERDICT,
            _blocked_ok,
            _checklist_section,
            _table_rows,
        )
    except ImportError:  # direct-script invocation
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from scripts.enforcement.check_review_coverage import (  # noqa: PLC0415
            RUBRIC_RUN,
            UNCHECKED,
            VERDICT,
            _blocked_ok,
            _checklist_section,
            _table_rows,
        )

    section = _checklist_section(text)
    if section is None:
        return [
            "claims CONVERGED but has no 'Coverage Checklist' — convergence must mean "
            "every known failure class was swept, not that nothing further occurred to "
            "the reviewer (derive rows from review_rubric.py + the four standing "
            "recurrence classes)"
        ]
    fails: list[str] = []
    # RAW `text`, not the fence-stripped `scan`: fence-stripping exists so a heading's PRESENCE
    # cannot be satisfied from a quoted example — correct for headings, wrong for a command
    # INVOCATION, whose natural home is a fenced block. Searching `scan` demanded evidence that a
    # command had been RUN while being structurally blind to the one place a command and its output
    # go, producing a genuinely circular state: put it where it belongs and it is invisible
    # (job-agent, 2026-08-28 — 4 round-trips before reading the source). This is a BLOCKING check,
    # so failing a CORRECT plan is the more expensive direction.
    if not RUBRIC_RUN.search(text):
        fails.append(
            "Coverage Checklist with no pasted review_rubric.py OUTPUT (its generated "
            "`# REVIEW RUBRIC` header) — run it on the real changed paths and paste the "
            "verbatim output; a prose mention or an unexpanded placeholder is not an "
            "invocation (trade-intelligence 01M17Z7Q)"
        )
    rows = _table_rows(section)
    if not rows:
        return [*fails, "Coverage Checklist has no table rows"]
    unchecked = [r.strip() for r in rows if UNCHECKED.search(r)]
    if unchecked and not _blocked_ok(text):
        fails.append(
            f"{len(unchecked)} UNCHECKED Coverage Checklist row(s) with no ## BLOCKED "
            f"escalation: {unchecked[:3]}"
        )
    noverdict = [r.strip() for r in rows if not UNCHECKED.search(r) and not VERDICT.search(r)]
    if noverdict:
        fails.append(
            f"{len(noverdict)} Coverage Checklist row(s) without a CLEAN/FIXED/REFUTED "
            f"verdict: {noverdict[:3]}"
        )
    return fails


def _check_plan(root: Path, path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    if not CONVERGED.search(text):
        return []  # only artifacts that CLAIM convergence are held to proof
    rel = path.relative_to(root)
    fails: list[str] = []
    scan = FENCE_STRIP.sub("", text)  # heading PRESENCE must not be satisfied from quotes
    if not EVIDENCE.search(scan):
        fails.append("claims CONVERGED but has no '## Evidence' section")
    if not AUDIT.search(scan):
        fails.append("no self-audit / convergence-floor block")
    fails += _checklist_fails(text, scan)
    phases = len(PHASE.findall(scan)) or 1  # headings, not evidence — quoted templates don't count
    if len(set(PROOF.findall(text))) < phases:
        fails.append(f"fewer than 1 `file:line` citation per phase (need >= {phases})")
    if _nontrivial_fences(text) < 1:
        fails.append("no non-trivial fenced command-output block (a column name != its values)")
    unmarked = _unmarked_excerpts(text)
    if unmarked:
        fails.append(
            f"{unmarked} fence(s) TRIMMED (a bare `...` line) without declaring it — open them "
            "```excerpt so a reader can tell a kept-the-load-bearing-lines excerpt from complete "
            "output; today the two are indistinguishable"
        )
    elided = _elided_probes(text)
    if elided:
        fails.append(
            f"{elided} probe fence(s) whose command is ELIDED (`$ ...`) — probe duty says re-run "
            "the command and diff its output, which an elided command makes impossible; paste the "
            "command you actually ran"
        )
    # Re-derivation ledger row (tryton-crm 01M17KHT, 2026-08-29): a plan-review ran ELEVEN
    # rounds with the factual-pass rule IN its command and applied in ZERO — six defects
    # survived the CONVERGED stamp, because the ledger had no METHOD notion and eleven
    # citation rounds are indistinguishable from a loop that re-derived. Scope inherits the
    # settled-at-HEAD carve-out via _converged_targets (this fn's only caller). Fence-stripped
    # `scan` so a quoted example table cannot pre-satisfy. Form is machine-checked; writing
    # the token without running the pass is the same declarative honesty boundary as BLOCKED
    # evidence (check_review_coverage._blocked_sections' adjudicated limit) — the backstop is
    # the operator reading the ledger, not a deeper parser.
    if not _REDERIVATION_ROW.search(scan):
        fails.append(
            "claims CONVERGED with no re-derivation Pass-Ledger row — the CLOSING pass must "
            "RE-DERIVE every count/enumeration/anchor from its primary source (a row naming "
            "`method: re-derivation`), not re-verify citations; run it, then record it"
        )
    out = [f"{rel}: {x}" for x in fails]
    if _is_spine(path):
        # Runs on BOTH claim paths (a dual CONVERGED+EXECUTED claim would double
        # up, but a skip-if-EXECUTED here opened a hole: an already-EXECUTED-at-
        # HEAD spine gaining a NEW CONVERGED claim ran the contract on NEITHER
        # path). main() dedupes identical finding lines instead. When EXECUTED
        # ALSO claims, its semantics win for the READ budget (end-of-run growth
        # is SIZING-DEFECT calibration data, not a flip blocker — BC 9).
        spine_fails = _check_spine_set(root, path, text)
        if EXECUTED.search(FENCE_STRIP.sub("", text)):
            spine_fails = [f for f in spine_fails if "READ budget" not in f]
        out += spine_fails
    return out


def _head_text(root: Path, relpath: str) -> str:
    """Content of ``relpath`` at HEAD, or "" if it did not exist there."""
    try:
        r = subprocess.run(
            ["git", "show", f"HEAD:{relpath}"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


# Archiving a plan IS the "nothing is left" act, so an archived plan whose own Status still says
# work continues is a contradiction no other check can see: `_check_plan` early-returns unless the
# text claims CONVERGED, and the EXECUTED contract only binds plans that CLAIM EXECUTED — so a plan
# stranded at IN-PROGRESS is out of scope for both, and the gate stays green while the archive lies.
# Filed by tryton-crm (2026-08-28) after `git mv` carried the INDEXED bytes and left their
# `Status: EXECUTED` flip unstaged; the commit said `rename … (100%)` and nothing caught it.
#
# NARROWED from the filed proposal ("flag any archived plan not EXECUTED"), which measured 348 of
# 553 archived docs fleet-wide — legacy shapes and status-less T## tickets, i.e. a gate that cries
# wolf on landing. Restricted to a dated PLAN file carrying an EXPLICIT mid-flight status, it
# measures 6 of 265, one of them the reported instance.
_ARCHIVED_PLAN = re.compile(r"/archived/\d{4}-\d{2}-\d{2}-plan-[^/]*\.md$")
_STATUS_LINE = re.compile(r"^\s*\**Status:\**\s*([A-Za-z][A-Za-z -]*)", re.M)
_MIDFLIGHT = {"IN-PROGRESS", "IN PROGRESS", "DRAFT", "ACTIVE", "OPEN", "PLANNING"}


def _archived_midflight(root: Path) -> list[str]:
    """Archived PLAN files whose own Status still claims work is in flight."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", PLANS_DIR],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except Exception:
        return []
    fails: list[str] = []
    for line in out.splitlines():
        if line[:2] == "??":
            continue
        rest = line[3:].strip()
        dst = (rest.split(" -> ", 1)[1] if " -> " in rest else rest).strip().strip('"')
        if not _ARCHIVED_PLAN.search("/" + dst.lstrip("/")):
            continue
        f = root / dst
        if not f.is_file():
            continue
        m = _STATUS_LINE.search(
            FENCE_STRIP.sub("", f.read_text(encoding="utf-8", errors="replace"))[:4000]
        )
        if m and m.group(1).strip().upper() in _MIDFLIGHT:
            fails.append(
                f"{dst}: archived while its own Status reads {m.group(1).strip()!r}. Archiving is "
                "the 'nothing is left' act. If the EXECUTED flip was lost by `git mv` (it moves "
                "INDEXED content, not your working tree), re-stage: `git add <the archived path>`"
            )
    return fails


def _executed_targets(root: Path) -> list[Path]:
    """Plans whose EXECUTED claim is NEW this commit — those must carry the review citation.

    A plan is enforced when its staged/working content claims EXECUTED **and that claim is
    not already present at HEAD for the same path** — i.e. the EXECUTED transition is
    happening now. This catches the flip in ``plans/``, the flip-and-archive (whether git
    records the move as a rename OR as delete+add on a large body rewrite), and a plan
    freshly added as EXECUTED — while SKIPPING a settled plan (already EXECUTED at HEAD)
    that is merely re-touched (a bulk reformat / reorg must not re-fail dozens of archived
    plans — the 'cries wolf' failure that gets a gate ``# noqa``'d). Robust to git rename
    detection being off (``status.renames=false``): it compares content at HEAD, never
    rename similarity — closing the delete+add / renames-off escape.
    """
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", PLANS_DIR],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except Exception:
        return []
    seen: set[str] = set()
    targets: list[Path] = []
    for line in out.splitlines():
        if line[:2] == "??":
            continue  # untracked in-flight draft — checked at staging (see _changed_md)
        rest = line[3:].strip()
        if " -> " in rest:  # rename: "old -> new"
            src, dst = (s.strip().strip('"') for s in rest.split(" -> ", 1))
        else:
            src = dst = rest.strip().strip('"')
        if dst in seen or not (dst.startswith(PLANS_DIR) and dst.endswith(".md")):
            continue
        seen.add(dst)
        p = root / dst
        if not p.is_file():
            continue
        if not EXECUTED.search(
            FENCE_STRIP.sub("", p.read_text(encoding="utf-8", errors="replace"))
        ):
            continue  # not an EXECUTED claim now → nothing to enforce
        # SETTLED (skip) if the plan was ALREADY EXECUTED at HEAD — at the new path
        # (in-place re-touch) OR at the rename SOURCE (a relocation / dir reorg). Only
        # a genuinely NEW EXECUTED transition is enforced, so a bulk archive reorg that
        # *moves* pre-citation EXECUTED plans doesn't re-fail every one of them.
        if EXECUTED.search(FENCE_STRIP.sub("", _head_text(root, dst))) or EXECUTED.search(
            FENCE_STRIP.sub("", _head_text(root, src))
        ):
            continue
        targets.append(p)
    return targets


def _converged_targets(root: Path) -> list[Path]:
    """Plans whose CONVERGED claim is NEW this commit — only those enter _check_plan.

    Mirrors _executed_targets: a file already CONVERGED at HEAD (in-place re-touch OR
    at the rename source of a reorg/archive move) is settled and skipped — this is
    what keeps pre-existing CONVERGED plans fleet-wide passing unchanged after the
    tolerant CONVERGED regex (a bold-only regex previously never matched them)."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", PLANS_DIR],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except Exception:
        return []
    seen: set[str] = set()
    targets: list[Path] = []
    for line in out.splitlines():
        if line[:2] == "??":
            continue  # untracked in-flight draft — checked at staging
        rest = line[3:].strip()
        if " -> " in rest:
            src, dst = (s.strip().strip('"') for s in rest.split(" -> ", 1))
        else:
            src = dst = rest.strip().strip('"')
        if dst in seen or not (dst.startswith(PLANS_DIR) and dst.endswith(".md")):
            continue
        if dst.startswith(PLANS_DIR + "archived/"):
            # An archive landing (rename OR delete+add body-rewrite) is settled
            # history — matching _changed_md's exclusion; a genuinely-new claim
            # is enforced at its pre-archive location.
            continue
        seen.add(dst)
        p = root / dst
        if not p.is_file():
            continue
        if not CONVERGED.search(p.read_text(encoding="utf-8", errors="replace")):
            continue
        if CONVERGED.search(_head_text(root, dst)) or CONVERGED.search(_head_text(root, src)):
            continue  # settled — already CONVERGED at HEAD
        targets.append(p)
    return targets


def _check_executed_plan(root: Path, path: Path) -> list[str]:
    """A plan claiming EXECUTED must cite a persisted whole-plan review artifact
    that EXISTS on disk and carries a coverage-adjudicated exit signature.

    This is the enforcement backstop for /fabrik-execute-plan's Finish step,
    which mandates a whole-plan /fabrik-review run to a coverage-adjudicated exit
    before the status flip. check_review_coverage.py can only validate a review
    that EXISTS; if the agent skips the skill entirely it produces no artifact
    and that gate stays silent. This makes the artifact's existence a hard
    precondition of the EXECUTED claim itself.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    if not EXECUTED.search(FENCE_STRIP.sub("", text)):
        return []  # only plans that CLAIM EXECUTED are held to the review proof (fences = quotes)
    rel = path.relative_to(root)
    fails: list[str] = []
    spine = _is_spine(path)
    if spine:
        # The plan-set contract enforces at BOTH flips (CONVERGED and EXECUTED) —
        # a DRAFT→EXECUTED jump must not skip it. APPEND (never early-return: the
        # review-citation findings below must surface in the SAME round, not a
        # second one). READ-budget findings are dropped here — end-of-execution
        # growth is SIZING-DEFECT calibration data, not a flip blocker (BC 9).
        fails += [f for f in _check_spine_set(root, path, text) if "READ budget" not in f]
    cited = REVIEW_CITE.findall(text)
    if not cited:
        return fails + [
            f"{rel}: claims EXECUTED but cites no whole-plan review artifact "
            "(docs/development/reviews/*.md) — run /fabrik-review over the whole-plan diff "
            "to its coverage-adjudicated exit, cite it here, or revert Status"
        ]
    eligible = [c for c in dict.fromkeys(cited) if not (spine and _TICKET_REVIEW_RE.search(c))]
    plan_stem = Path(rel).stem  # e.g. 2026-01-01-plan-9-widget
    for c in eligible:
        # A spine cites its D4 per-ticket reviews (<plan>-T##-review.md) routinely —
        # those prove single tickets, never the WHOLE-plan validation (filtered above).
        # ACCIDENTAL SATISFACTION guard: a plan often cites OTHER reviews as evidence
        # (a sibling incident, a prior wave); a quiet round in an UNRELATED review must
        # not certify THIS plan. The quiet pass counts only from a review whose
        # filename references this plan's stem — unconditionally (round-2: a single
        # unrelated citation is the same hole; every archived EXECUTED plan
        # stem-matches its citation, so this is retro-safe).
        if plan_stem not in Path(c).name:
            continue
        rp = root / c
        if not rp.is_file():
            continue
        rtext = rp.read_text(encoding="utf-8", errors="replace")
        # A quiet round (found: 0 … fixed: 0) appears somewhere → the cited review
        # ran the loop to (at least one) quiet pass. Zero-false-positive by design
        # (see QUIET_PASS); DEPTH is check_review_coverage.py's at staging time.
        if QUIET_PASS.search(rtext):
            return fails  # citation satisfied; spine-set findings (if any) still surface
    return fails + [
        f"{rel}: claims EXECUTED but its cited whole-plan review is missing on disk or not "
        "coverage-adjudicated (needs a quiet final pass — a 'found: 0, fixed: 0' round) — "
        "finish the /fabrik-review loop to a quiet round, or revert Status"
        + (
            " (for a plan SET the citation must be the WHOLE-PLAN validation review — "
            "per-ticket -T##-review.md files never satisfy it)"
            if spine
            else ""
        )
    ]


# Review-branch claim escapes (parity with the plan branch's _NEGATED_CONVERGED /
# FENCE_STRIP treatment — the raw REVIEWED regex false-failed an honest de-claimed
# doc "sign-off is withheld / not yet reviewed"). Same precedence as the plan
# branch: ONE unnegated affirmative anywhere claims (fail-open); only a claim word
# ITSELF directly negated is a disclosure.
_NEG_BEFORE_CLAIM = re.compile(
    r"(?:\b(?:not|never|no|isn'?t|cannot|can'?t|without|withhold\w*|withheld|awaiting|pending"
    r"|until|before|un)"
    r"(?:\W+(?:yet|been|be|fully|formally|properly|merged|closed))*\W{0,2}$)",
    re.I,
)
_NEG_AFTER_CLAIM = re.compile(
    r"^[^.\n]{0,32}?\b(?:withheld|withhold|pending|deferred|denied)\b", re.I
)


def _inline_code_spans(text: str) -> list[tuple[int, int]]:
    """Byte ranges covered by INLINE code spans (`like this`).

    Fenced blocks are already removed upstream by FENCE_STRIP; inline spans were not, and a claim
    word QUOTED as data is not a claim about the document. transdoc (2026-08-27) ships a control
    whose label is the past tense of "to review", so their certification report could not name the
    button it drove — nor write the note explaining the false positive — and was contorted into
    "mark-as-complete" wording purely to pass. A gate that forces an artifact to misdescribe reality
    is worse than one that misses a case.

    An UNTERMINATED backtick yields NO span: fail-open. A stray tick must never silently exempt
    every claim after it, which would turn one typo into a laundering device.
    """
    ticks = [m.start() for m in re.finditer(r"`", text)]
    # Pair them off; a trailing UNPAIRED tick is dropped by the step-2 walk, which is the fail-open
    # behaviour the docstring promises.
    return [(ticks[i], ticks[i + 1]) for i in range(0, len(ticks) - 1, 2)]


def _claims_reviewed(stripped: str) -> bool:
    code = _inline_code_spans(stripped)
    for m in REVIEWED.finditer(stripped):
        if any(a < m.start() and m.end() <= b for a, b in code):
            continue  # quoted as data (a label, an identifier), not asserted about this doc
        if _NEG_BEFORE_CLAIM.search(stripped[max(0, m.start() - 24) : m.start()]):
            continue
        if _NEG_AFTER_CLAIM.search(stripped[m.end() : m.end() + 40]):
            continue
        return True
    return False


def _check_review(root: Path, path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    # An in-flight review is not making a convergence claim yet (fabrik-lib 01M180SP):
    # the termination contract MANDATES creating the report before pass 1, and this
    # check redded the fresh skeleton for lacking an embedded green gate it cannot yet
    # have — a chicken-and-egg hit twice in one session. Header-zone IN-PROGRESS is the
    # sanctioned mid-loop state (check_review_coverage._in_progress is the ONE
    # definition, imported so the two graders cannot drift); the flip re-arms this.
    try:
        from .check_review_coverage import _in_progress  # noqa: PLC0415 — local: soft dep
    except ImportError:  # direct-script invocation
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from scripts.enforcement.check_review_coverage import _in_progress  # noqa: PLC0415
    if _in_progress(text):
        return []
    # Claims are read on fence-STRIPPED text — a fenced claim word is a quotation
    # (grammar template, example), not a claim.
    if not _claims_reviewed(FENCE_STRIP.sub("", text)):
        return []
    rel = path.relative_to(root)
    fails: list[str] = []
    # The gate embed must sit INSIDE a fenced block (the verbatim-embed
    # convention): a literal "status": "success" in prose satisfied this check
    # live while the surrounding sentence explained why faking it would be wrong.
    # Extraction uses the SAME fence contract as FENCE_STRIP (backreferenced
    # closer + inline single-line quotes) — the naive FENCE_BLOCK mispairs when
    # an in-contract inline ```…``` quote precedes the real embed, uncapturing a
    # genuine success JSON (fail-closed false-failure, review finding).
    fenced = "\n".join(m.group(2) or m.group(3) or "" for m in _FENCED_CONTENTS.finditer(text))
    if not GATE_OK.search(fenced):
        fails.append('no embedded final_gate run showing "status": "success" inside a fenced block')
    if not PHASE.search(text):
        fails.append("no per-phase verdict (no Phase/Step reference)")
    return [f"{rel}: {x}" for x in fails]


def main() -> int:
    parser = argparse.ArgumentParser(description="Convergence-evidence gate (plans + reviews).")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()

    fails: list[str] = []
    for p in _converged_targets(root):
        fails += _check_plan(root, p)
    for p in _executed_targets(root):
        fails += _check_executed_plan(root, p)
    fails.extend(_archived_midflight(root))
    for p in _changed_md(root, REVIEWS_DIR):
        fails += _check_review(root, p)

    fails = list(dict.fromkeys(fails))  # dual-claim paths may repeat a finding — dedupe
    if fails:
        print("Convergence gate FAILED — a convergence claim lacks its proof:")
        for x in fails:
            print(f"  - {x}")
        print(
            "Fix: supply the required evidence (Evidence section, file:line citations, a"
            " fenced command-output block, an embedded final_gate success), or drop the claim."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
