#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_stage_artifacts.py | none
"""Stage-skip artifact gate — run by final_gate via run_optional_check, Tier-2 ONLY
(non-zero = fail).

The pipeline has one MECHANICAL gate per stage's output artifact where it exists
(spec/plan "CONVERGED" claims -> check_convergence.py; whole-plan review
adjudication -> check_review_coverage.py, which ALSO already disposition-gates
5-certify user-test/service-test reports via its `check_cert_dispositions` — see
the audit note below). Two REAL stage-skip holes remain past both: a plan can
flip CONVERGED while the design spec it was built from is still DRAFT (stage 1
was never actually finished, only skipped past), and a data-contract/ui-design
artifact can flip `Status: FROZEN` without the header fields + freeze-rule
sentence its OWN command mandates — nothing on the enforcement side checks that
the freeze actually wrote what `/fabrik-data-contract` / `/fabrik-ui-design`
require, so a truncated or hand-edited FROZEN flip sails through and every
downstream build agent trusts a header that never promised what it claims to.
This script closes those two, and only those two (scope discipline — see the
plan ticket).

  docs/development/plans/*.md   NEWLY claims '**Status:** CONVERGED' this commit
      (via check_convergence._converged_targets — new-transition-only, so a
      pre-existing settled CONVERGED plan is never re-punished for a stale
      citation nobody is touching)
      -> if it cites a docs/superpowers/specs/*.md design spec (path appearing
         in the fence-stripped body — the markdown-link-label form the fleet
         already uses, e.g. "[docs/superpowers/specs/X.md](../../superpowers/specs/X.md)"),
         that spec must EXIST on disk and itself claim CONVERGED (reusing
         check_convergence._claims_converged so both call sites read "CONVERGED"
         identically). A spec under specs/archived/ is settled history and exempt.
         Missing file or a non-CONVERGED (DRAFT/PLANNED/absent) spec = a stage
         1->3 skip: the plan is trusting design work that was never finished.

  docs/data-contract.md
  docs/ui-design.md             NEWLY claims 'Status: FROZEN' this commit
      (HEAD-diff new-transition-only, mirroring check_convergence._converged_targets
      exactly: a file already FROZEN at HEAD is settled and never re-punished for
      a header gap nobody is touching)
      -> must carry the header fields its OWN freezing command mandates
         (commands/_sources/fabrik-data-contract.md:157 /
         commands/_sources/fabrik-ui-design.md:121): `Status: FROZEN`,
         `Version: v<N>`, a `Date:` line, the file-specific field
         (data-contract: `Mode: A|B|C`; ui-design: `Surface:` AND
         `Design system:`) — these FIELD checks are header-scoped (see
         _header_block) — AND the freeze-rule sentence naming its own
         re-freeze command verbatim ("re-freeze via `/fabrik-data-contract`" /
         "re-freeze via `/fabrik-ui-design`"), scanned over the WHOLE document,
         never header-scoped: both freezing commands' own Phase 4/7 issue "Set
         the header: ..." and "Add the freeze rule verbatim: ..." as TWO
         SEPARATE bullets, and 6 of 24 real fleet FROZEN artifacts (e.g.
         /opt/tryton-crm/docs/data-contract.md:85) keep the sentence as a
         FOOTER paragraph the header-block cap would otherwise miss.

AUDIT NOTE (why this is NOT the plan-ticket's pre-analysis candidate (b)):
the pre-analysis candidate — "a certification report claimed by a release
precondition without gate-side existence/shape checking" — is PARTIALLY true,
not FALSE as an earlier pass of this note claimed. scripts/enforcement/
check_review_coverage.py:185-231 (`check_cert_dispositions`) disposition-gates
the SHAPE of every docs/development/reviews/*-{user,service}-test-*.md report
that is ALREADY changed/staged (HANDOFF row grammar, repro: existence,
CLOSED-needs-proof:, OPEN-forces-NOT-QUIET, NOT-QUIET-needs-##-RESUME) and is
registered in final_gate.py for EVERY tier (scripts/final_gate.py:711-727,
ahead of the tier switch). What it does NOT do: mechanically require the
report to EXIST at all — `/fabrik-release`'s Gate-2 handoff is an ephemeral
console print, never a committed file (see the "Two gaps" note below), so
nothing forces a certification report into existence for a release
precondition to be checked against in the first place. Correct framing: SHAPE
is covered, EXISTENCE is not mechanizable — never "fully gated". Re-implementing
the SHAPE check here would still violate the ticket's own DO-NOT (never re-gate
what an existing check already owns) — its own `continue  # a certification
report is disposition-gated, not checklist-gated` marks that boundary — so this
script does NOT touch certification reports at all; the EXISTENCE gap is
recorded, not closed (no persisted artifact for a git-diff-driven script to
inspect). The FROZEN-header gap above is the confirmed top-2 replacement — see
the SPINE's `## Evidence` section at
docs/development/plans/2026-08-07-plan-1-autotrigger-and-commands/ for the full
stage->artifact->existing-gate audit table (the dispatcher applies that table
there at merge; it exists at HEAD once merged).

DRAFT/PLANNED downgrade (context-severity precedent, matching the plan-gates'
treatment of a mid-authoring set): a plan only enters the spec-freshness check
when it is NEWLY claiming CONVERGED (the same gate check_convergence.py already
applies) -- a DRAFT/PLANNED plan is never a target, exactly like check_convergence
never holds a non-claiming plan to its own evidence bar. Same for the FROZEN
header check: a DRAFT data-contract/ui-design file is never a target.

Ceiling (by design, matching check_convergence.py's own): this enforces artifact
*shape and cross-reference existence*, never truth -- a header field's VALUE is
trusted verbatim once it is present (e.g. `Mode: A` is accepted without
verifying Mode A's actual reconciliation happened); whether the freeze / design
convergence is actually correct is the human reviewer's job.

Two gaps NOT covered here (recorded, out of THIS ticket's scope -- see the
SPINE's `## Evidence` section at
docs/development/plans/2026-08-07-plan-1-autotrigger-and-commands/ for the full
T08 stage->artifact->existing-gate audit table): (1) a design spec's OWN
evidence shape when it claims CONVERGED (docs/superpowers/specs/*.md never
enters check_convergence.py at all -- PLANS_DIR only watches
docs/development/plans/; NOT implemented here either -- real fleet specs vary
widely in whether they cite an evidence trail in the Status line at all, so a
mechanical bar would be under-grounded, unlike the FROZEN header fields which
are verbatim-mandated by their own command source); (2) release receipts
(6-release) have no persisted artifact at all -- `fabrik-release.md`'s "Gate-2
handoff" is an ephemeral console print, never a committed file, so there is
nothing for a git-diff-driven enforcement script to inspect.

LIFECYCLE CAVEAT (F10, noted for a future ticket): both gates here fire on the
FIRST DRAFT/PLANNED/absent -> CONVERGED or -> FROZEN transition only
(new-transition-only, mirroring check_convergence._converged_targets' own
precedent). A later RE-freeze of an already-FROZEN data-contract/ui-design file
(mandated by the Doc Sync Matrix whenever a DB field/enum/model or screen/flow
changes) is UN-gated by design here — same precedent as check_convergence's own
EXECUTED/CONVERGED transitions, which never re-punish a settled artifact that
is merely re-touched. Closing that (enforcing header completeness on every
re-freeze, not just the first) is future scope, not this ticket's.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

try:
    from . import check_convergence as cc  # package context (python -m ...)
except ImportError:  # pragma: no cover - direct script invocation
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.enforcement import check_convergence as cc

# Markdown-link-label OR bare-path citation of a design spec, fence-stripped body
# only (a DRAFT plan quoting an example citation in a fence must not trip this --
# same fence policy as check_convergence.py). Archived specs are settled history.
SPEC_CITE = re.compile(r"docs/superpowers/specs/(?!archived/)[\w./-]+\.md")
# F6: "its spec" must be scoped to ONE designated citation, never a free
# body-wide scan -- a supersedes/rejected/see-also aside anywhere in the body
# must not become a blocking dependency. A `Spec:` / `Design spec:` header
# field is the designated source when present.
_SPEC_FIELD_LINE = re.compile(
    r"^\s*(?:[-*>]\s+)?\*{0,2}(?:Design spec|Spec)\*{0,2}[^\S\n]*:[^\S\n]*(?P<val>[^\n]*)$",
    re.I | re.M,
)
# The archived-specs dir, keyed off a spec citation's own basename (F5) -- a
# plan that still cites the pre-archive path (real fleet case:
# 2026-06-29-plan-empire-operating-model.md cites
# docs/superpowers/specs/2026-07-12-empire-operating-model-design.md, which now
# lives ONLY under specs/archived/) must not be flagged: archived = settled
# post-lifecycle history under a new home, not a missing citation.
ARCHIVED_SPECS_DIR = "docs/superpowers/specs/archived"


# --- Gap (a): plan CONVERGED citing a still-DRAFT design spec (stage 1->3 skip) ---


def _designated_spec_citations(text: str) -> list[str]:
    """Scope 'its spec' to ONE designated citation source (F6): (1) a
    Spec:/Design spec: header field, if present -- ONLY what IT cites counts,
    even if that citation set is empty (a Spec: field naming something else is
    NOT a fallback trigger for (2)); (2) else any PROSE citation within the
    plan's first 40 lines (header + Context section) -- NEW-5: a markdown
    TABLE ROW (line starting with '|') is excluded from this fallback scan, so
    a Context-Ledger "see-also" table citing a sibling spec for orientation
    never becomes a blocking dependency, matching the existing body-only-
    mention exemption's intent; (3) else no spec dependency at all -- a
    body-only mention (supersedes/rejected/see-also) never blocks."""
    m = _SPEC_FIELD_LINE.search(text)
    if m:
        return list(dict.fromkeys(SPEC_CITE.findall(m.group("val"))))
    lines = text.splitlines()[:40]
    head = "\n".join(ln for ln in lines if not ln.lstrip().startswith("|"))
    return list(dict.fromkeys(SPEC_CITE.findall(head)))


def _check_plan_spec_freshness(root: Path, path: Path) -> list[str]:
    """A plan that NEWLY claims CONVERGED must have a CONVERGED design spec behind
    it, if it cites one at all -- scoped to its ONE designated citation (F6),
    never a free body-wide spec mention. Only invoked on check_convergence's own
    new-transition targets -- a DRAFT/PLANNED plan, or one already CONVERGED at
    HEAD, is never a candidate here (matches check_convergence's own claim
    gate)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    scan = cc.FENCE_STRIP.sub("", text)
    rel = path.relative_to(root)
    fails: list[str] = []
    for spec_rel in _designated_spec_citations(scan):
        spec_path = root / spec_rel
        if not spec_path.is_file():
            # F5: the citation may still point at the pre-archive path -- check
            # the archived home (by basename) before failing.
            archived = root / ARCHIVED_SPECS_DIR / Path(spec_rel).name
            if archived.is_file():
                continue  # archived = post-lifecycle, settled under a new home
            fails.append(
                f"{rel}: claims CONVERGED but cites design spec {spec_rel} which does not "
                f"exist on disk (checked {ARCHIVED_SPECS_DIR}/ too) -- cannot verify the "
                "design stage actually converged (stage 1->3 skip); fix the citation or "
                "run /fabrik-spec first"
            )
            continue
        spec_text = spec_path.read_text(encoding="utf-8", errors="replace")
        if not cc._claims_converged(cc.FENCE_STRIP.sub("", spec_text)):
            fails.append(
                f"{rel}: claims CONVERGED but its cited design spec {spec_rel} is not "
                "itself CONVERGED (stage 1->3 skip) -- run /fabrik-spec-review on the spec "
                "to convergence first, or drop the citation if the plan no longer depends on it"
            )
    return fails


def _plan_spec_freshness_targets(root: Path) -> list[Path]:
    # Same discovery as check_convergence's own CONVERGED-flip targets -- a plan
    # is only a candidate the moment its CONVERGED claim is NEW this commit.
    return cc._converged_targets(root)


# --- Gap (new-2): data-contract / ui-design FROZEN header completeness ----------

# F2: both freezing commands mandate a ONE-LINE '.'-separated header (often
# blockquoted, bold- or backtick-tokened -- commands/_sources/fabrik-data-
# contract.md:157, commands/_sources/fabrik-ui-design.md:121; verified against
# the live fleet /opt/trade-intelligence/docs/ui-design.md header, e.g.
# "**Status:** FROZEN . **Version:** v4 . **Date:** 2026-08-02 . ..." on ONE
# line). The old ^-anchored per-line regexes never matched that shape (Version/
# Date/etc. sit mid-line, not at line start) -- every FIELD regex below is
# UNANCHORED instead, scoped to a HEADER BLOCK (the text up to the first
# standalone '---' rule, or the first 40 lines if none) so a field mentioned in
# body prose never counts. This header-block scoping is FIELDS-ONLY (NEW-1):
# the freeze-rule sentence is a separate, deliberately-unscoped whole-document
# scan -- see _check_frozen_header.
_HEADER_END = re.compile(r"^-{3,}\s*$", re.M)


def _skip_frontmatter(text: str) -> str:
    """NEW-3: a leading YAML frontmatter block's OPENING '---' (line 1) is not
    the header's own closing rule -- _HEADER_END's ^--- search hits that line
    FIRST and empties the whole header block (``text[:0]``), silently skipping
    the FROZEN-header gate for every field. Skip past the frontmatter's CLOSING
    '---' (the next standalone '---' line) before the real header-end search
    runs; a doc with no line-1 '---' is returned unchanged."""
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for i, ln in enumerate(lines[1:], start=1):
            if ln.strip() == "---":
                return "".join(lines[i + 1 :])
    return text


def _header_block(text: str, max_lines: int = 40) -> str:
    """The header region used for FIELD regexes only (Version/Date/Mode/
    Surface/Design-system) -- the freeze-rule sentence is scanned elsewhere,
    over the whole document (NEW-1). Skips a leading YAML frontmatter block
    first (NEW-3). Both caps apply TOGETHER, not either/or (despite older
    wording implying a fallback): the block is cut at the first standalone
    '---' rule if one exists, THEN capped to the first ``max_lines`` lines of
    whatever remains -- a '---' beyond max_lines never grows the block past
    max_lines, and a doc with no '---' at all just uses the max_lines cap."""
    text = _skip_frontmatter(text)
    m = _HEADER_END.search(text)
    block = text[: m.start()] if m else text
    return "\n".join(block.splitlines()[:max_lines])


# Status label tolerant of a leading backtick OR bold wrapper (`Status: FROZEN`
# is the command-verbatim form; **Status:** FROZEN is the fleet-live form). The
# VALUE is bounded at the next '.' field separator / closing backtick / newline
# so it never slurps the header's OTHER '.'-joined fields.
_STATUS_LINE = re.compile(r"[`*]{0,2}Status[`*]{0,2}[^\S\n]*:[^\S\n]*(?P<val>[^\n·`]*)", re.I)
_NEGATED_FROZEN = re.compile(r"\b(?:not|never|isn'?t|un)\W{0,2}frozen", re.I)
# F1/F3 CRITICAL, tightened (NEW-2): a "DRAFT | FROZEN" scaffold-stub
# placeholder (e.g. templates/scaffold/docs/data-contract-template.md:3
# "> **Status:** DRAFT | FROZEN . ...") is a template SLOT, never a live claim --
# regardless of which side "frozen" lands on. Checked before the non-claim-token
# test below (belt + suspenders: the template's own first token is "draft",
# which already lands in cc._NON_CLAIM_TOKENS, but a differently-ordered
# placeholder must not slip past either).
#
# The OLD form (`^\S+\s*\|\s*\S+`) matched ANY two tokens around a bare '|' --
# a real header that uses '|' as its own FIELD separator (a live claim, e.g.
# "**Status:** FROZEN | **Version:** v2") tripped it too and got silently
# skipped, gate-evading the whole file (NEW-2 gap). Anchor to the known status
# vocabulary instead: a placeholder is TWO-OR-MORE pipe-separated tokens that
# are ALL status words, nothing else.
_STATUS_TOKENS = frozenset({"frozen"}) | cc._NON_CLAIM_TOKENS


def _is_placeholder_pair(low: str) -> bool:
    """True only when every '|'-separated segment of `low` (already the
    Status-line value, lowercased) is itself a bare known status token (e.g.
    "draft | frozen" or "frozen | draft") -- never for a value where a pipe
    merely happens to separate the Status field from the NEXT header field
    ("frozen | **version:** v2" has a segment that is not a status token, so
    it is a real claim, not a placeholder)."""
    parts = [p.strip().strip("`*").rstrip(":*") for p in low.split("|")]
    return len(parts) >= 2 and all(p in _STATUS_TOKENS for p in parts)


_VERSION_LINE = re.compile(r"[`*]{0,2}Version[`*]{0,2}[^\S\n]*:[^\S\n]*\S", re.I)
# Date/Mode need an EXACT value shape after the colon (digits / a single
# letter) -- unlike the presence-only fields above, \S alone would accept a
# stray closing "**" as the "value". Tolerate a closing bold/backtick wrapper
# sitting BETWEEN the colon and the value (the real fleet header bold-wraps
# "Date:" with the closing "**" landing there, e.g. "**Date:** 2026-08-02").
_DATE_LINE = re.compile(
    r"[`*]{0,2}Date[`*]{0,2}[^\S\n]*:[^\S\n]*[`*]{0,2}[^\S\n]*\d{4}-\d{2}-\d{2}", re.I
)
_MODE_LINE = re.compile(r"[`*]{0,2}Mode[`*]{0,2}[^\S\n]*:[^\S\n]*[`*]{0,2}[^\S\n]*[ABC]\b", re.I)
_SURFACE_LINE = re.compile(r"[`*]{0,2}Surface[`*]{0,2}[^\S\n]*:[^\S\n]*\S", re.I)
_TYPE_LINE = re.compile(r"[`*]{0,2}Type[`*]{0,2}[^\S\n]*:[^\S\n]*\S", re.I)
_JOURNEY_KINDS_LINE = re.compile(r"[`*]{0,2}Journey kinds[`*]{0,2}[^\S\n]*:[^\S\n]*\S", re.I)
_DESIGN_SYSTEM_LINE = re.compile(r"[`*]{0,2}Design system[`*]{0,2}[^\S\n]*:[^\S\n]*\S", re.I)

# The verbatim freeze-rule instruction each command mandates, keyed by the
# re-freeze command it must name (commands/_sources/fabrik-data-contract.md:157,
# commands/_sources/fabrik-ui-design.md:121). Loosely matched: "re-freeze via"
# near the command's own slash-name, tolerant of backtick/markdown noise between.
FROZEN_ARTIFACTS: dict[str, dict] = {
    "docs/data-contract.md": {
        "kind": "data-contract",
        "extra": [("Mode: A|B|C", _MODE_LINE)],
        "freeze_cmd": "/fabrik-data-contract",
    },
    "docs/ui-design.md": {
        "kind": "ui-design",
        "extra": [
            ("Surface: ...", _SURFACE_LINE),
            ("Design system: ...", _DESIGN_SYSTEM_LINE),
        ],
        "freeze_cmd": "/fabrik-ui-design",
    },
    "docs/flows.md": {
        "kind": "flows",
        "extra": [
            ("Type: ...", _TYPE_LINE),
            ("Journey kinds: ...", _JOURNEY_KINDS_LINE),
        ],
        "freeze_cmd": "/fabrik-flows",
    },
}


def _claims_frozen(text: str) -> bool:
    for m in _STATUS_LINE.finditer(text):
        val = m.group("val").strip().strip("`*").strip()
        if not val:
            continue
        low = val.lower()
        if _is_placeholder_pair(low):
            continue  # e.g. "DRAFT | FROZEN" (either order) scaffold-stub placeholder (F1/F3/NEW-2)
        # Port cc._NON_CLAIM_TOKENS semantics (F1/F3): the VALUE's first token
        # decides -- "draft"/"planned"/"in-progress"/etc. is never a claim, even
        # though the word "frozen" appears later in the same line's prose
        # ("Status: DRAFT — will be frozen after review").
        stripped = low.lstrip("✅🟢⚠️❌ ")
        first = stripped.split()[0].rstrip(":*—–-`") if stripped.split() else ""
        if first in cc._NON_CLAIM_TOKENS:
            continue
        if _NEGATED_FROZEN.search(low):
            continue
        if "frozen" in low:
            return True
    return False


def _normalize_header(text: str) -> str:
    """F4: strip leading blockquote markers per line, then join with spaces so a
    freeze-rule sentence WRAPPED across lines (the scaffold template's actual
    "Any change = bump Version + re-freeze\\n> via `/fabrik-data-contract`.")
    still reads as one continuous sentence for the 're-freeze via <cmd>' scan."""
    lines = [re.sub(r"^\s*>+\s?", "", ln) for ln in text.splitlines()]
    return " ".join(lines)


def _check_frozen_header(root: Path, rel: str, cfg: dict, path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    scan = cc.FENCE_STRIP.sub("", text)
    block = _header_block(scan)
    fails: list[str] = []
    if not _VERSION_LINE.search(block):
        fails.append(f"{rel}: claims Status: FROZEN but header is missing a 'Version: v<N>' line")
    if not _DATE_LINE.search(block):
        fails.append(
            f"{rel}: claims Status: FROZEN but header is missing a 'Date: YYYY-MM-DD' line"
        )
    for label, pat in cfg["extra"]:
        if not pat.search(block):
            fails.append(f"{rel}: claims Status: FROZEN but header is missing a '{label}' line")
    cmd = cfg["freeze_cmd"]
    # NEW-1: the freeze-rule sentence is scanned over the WHOLE fence-stripped
    # document, never header-scoped -- both freezing commands' own Phase 4/7
    # issue "Set the header: ..." and "Add the freeze rule verbatim: ..." as
    # TWO SEPARATE bullets (commands/_sources/fabrik-data-contract.md:155-158,
    # fabrik-ui-design.md:120-121), and 6 of 24 real fleet FROZEN artifacts
    # (e.g. /opt/tryton-crm/docs/data-contract.md:85) keep the sentence as a
    # FOOTER paragraph the header-block cap would otherwise miss entirely.
    # F4: case-insensitive ("Re-freeze via" ok) + whitespace-normalized (a wrap
    # must not evade it) + word-boundary on the command token so
    # `/fabrik-ui-design` is never satisfied by `/fabrik-ui-design-review`
    # (the real fleet header cites the -review command TWICE before the actual
    # freeze-rule sentence's bare command mention).
    normalized = _normalize_header(scan)
    cmd_re = re.compile(re.escape(cmd) + r"(?![\w-])")
    if "re-freeze via" not in normalized.lower() or not cmd_re.search(normalized):
        fails.append(
            f"{rel}: claims Status: FROZEN but is missing the freeze-rule sentence naming its "
            f"own re-freeze command ('re-freeze via `{cmd}`') -- the verbatim sentence "
            f"{cfg['kind']}'s own freezing command mandates adding to the document"
        )
    return fails


def _frozen_targets(root: Path) -> list[tuple[str, dict, Path]]:
    """(rel, cfg, path) for each FROZEN_ARTIFACTS file whose FROZEN claim is NEW
    this commit -- a file already FROZEN at HEAD is settled (mirrors
    check_convergence._converged_targets' new-transition-only precedent)."""
    rels = list(FROZEN_ARTIFACTS)
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", *rels],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except Exception:
        return []
    targets: list[tuple[str, dict, Path]] = []
    for line in out.splitlines():
        if line[:2] == "??":
            continue  # untracked in-flight draft -- checked at staging
        rest = line[3:].strip()
        # F12: rename porcelain ("R  old -> new") -- mirror
        # check_convergence._converged_targets:399-403, take the NEW path.
        if " -> " in rest:
            _src, rel = (s.strip().strip('"') for s in rest.split(" -> ", 1))
        else:
            rel = rest.strip().strip('"')
        cfg = FROZEN_ARTIFACTS.get(rel)
        if cfg is None:
            continue
        p = root / rel
        if not p.is_file():
            continue
        block = _header_block(
            cc.FENCE_STRIP.sub("", p.read_text(encoding="utf-8", errors="replace"))
        )
        if not _claims_frozen(block):
            continue  # not a FROZEN claim now -> nothing to enforce
        head_block = _header_block(cc.FENCE_STRIP.sub("", cc._head_text(root, rel)))
        if _claims_frozen(head_block):
            continue  # settled -- already FROZEN at HEAD
        targets.append((rel, cfg, p))
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage-skip artifact gate (spec freshness + FROZEN header shape)."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()

    fails: list[str] = []
    for p in _plan_spec_freshness_targets(root):
        fails += _check_plan_spec_freshness(root, p)
    for rel, cfg, p in _frozen_targets(root):
        fails += _check_frozen_header(root, rel, cfg, p)

    fails = list(dict.fromkeys(fails))
    if fails:
        print("Stage-artifact gate FAILED — a stage-skip artifact gap was found:")
        for x in fails:
            print(f"  - {x}")
        print(
            "Fix: converge the cited design spec, or complete the FROZEN header fields + freeze-rule "
            "sentence your freezing command mandates, or drop the claim that depends on it."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
