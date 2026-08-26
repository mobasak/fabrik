#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_pack_reachability.py
"""Rule-pack reachability gate — ADVISORY wrapper around `pack_layout_audit.audit_layout()`
for `final_gate.py`.

WHY THIS EXISTS (and why the obvious check does not work): the obvious design is
"assert every pack `select_rules.py` marks ACTIVE matches >=1 emitted path" — that check
is CIRCULAR and can never fire, because `select_rules.py` derives its ACTIVE set from
the very same globs under test:

    if any(rules_match.any_path_matches(root, g, empty_matches_all=False) for g in globs):
        active.append(entry)
    else:
        available.append(entry)

A pack with broken globs silently drops to AVAILABLE, so the set (ACTIVE AND
matches-zero) is empty by construction — measured live: `core/75-workers-jobs.md` and
`core/app-audit-log.md` sat in AVAILABLE, indistinguishable from packs correctly deemed
irrelevant. The fix is an INDEPENDENT declared expectation: `applies_to:` frontmatter
(see `pack_layout_audit.py`'s module docstring for the full story, and
`docs/reference/rule-pack-reachability.md` for the subsystem writeup).

WHAT THIS SCRIPT ADDS ON TOP OF THE ENGINE: `pack_layout_audit.audit_layout()` IS the
shared engine (imported here, never reimplemented — a second glob matcher or a second
frontmatter parser would let this check and the engine silently disagree). This script
only adds the gate-facing contract:

  1. An ADVISORY (`warn_only=True`) exit — always 0 on a completed run, findings are
     printed, never block. Landing this BLOCKING on day one would red 56 packs across
     ~46 repos in one commit; promoting it later is a deliberate OPERATOR decision made
     once the corpus is clean, not something this script decides for itself.
  2. THE EXAMINED COUNT. A pack with no `applies_to:` passes silently BY DESIGN (the
     field lands incrementally across the corpus without turning the fleet red before
     anyone has annotated anything) — but that same silence is exactly how a check
     "reports SUCCESS when it cannot ask its question" becomes invisible. Printing how
     many packs actually declared a reachable `applies_to` (not the whole corpus size)
     is what turns "0 findings because nobody declared anything" into a visibly
     different outcome from "0 findings because every declared claim was verified".

Exit code: always 0 once the run completes (advisory) — a non-zero exit here means the
check itself broke (e.g. the scaffolder registry could not be resolved), never that a
pack was found inert.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ENFORCEMENT_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _ENFORCEMENT_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_ENFORCEMENT_DIR) not in sys.path:
    sys.path.insert(0, str(_ENFORCEMENT_DIR))
import pack_layout_audit as pla  # noqa: E402 - the shared engine, not reimplemented


def _examined_packs(root: Path, types: list[str]) -> list[str]:
    """Packs this run actually asked a question about: glob-activated (non-manual)
    packs whose `applies_to` names at least one of `types`.

    ⚠️ This counts PACKS, not (pack, type) PAIRS — and an earlier version of this docstring
    claimed it "mirrors the exact condition `audit_layout` evaluates per (pack, type) pair",
    which is FALSE and was the FIFTH false claim in this change. `audit_layout` loops per
    type and evaluates `scaffold_type in applies_to`; this uses `any(...)` across all types.
    They coincide for a single-type pack, and DIVERGE when a pack claims two types and only
    one is evaluable: examined says 1 pack while 2 pairs were considered and 1 skipped. The
    pair count is reported separately (`claim_pairs`) precisely so the denominator is not
    this number pretending to be that one. `pla._packs_with_meta` is the same
    frontmatter reader the engine uses, reused here (not reparsed) purely to COUNT what
    was examined, distinct from the engine's own findings computation."""
    types_set = set(types)
    return [
        rel
        for rel, _globs, activation, applies_to in pla._packs_with_meta(root)
        if activation != "manual" and any(t in types_set for t in applies_to)
    ]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Advisory gate: report .windsurf/rules packs whose applies_to claims a "
            "scaffold type their globs cannot reach. Consumes pack_layout_audit's "
            "shared engine; never derives applicability from select_rules' ACTIVE set."
        )
    )
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    ap.add_argument(
        "--types",
        nargs="+",
        default=None,
        help="scaffold types to check (default: all types from the live SCAFFOLD_TYPES registry)",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = args.project_root.resolve()

    # DEDUPE at the input boundary. `--types file-worker file-worker` made audit_layout
    # iterate the type twice and emit the SAME Finding twice, while `known = set(types)`
    # counted the claim once — content and count disagreeing, which is the denominator
    # integrity this check exists to enforce, one level further out. Fixing it here rather
    # than at each consumer means a future call site cannot reintroduce it. (D7 round 13.)
    types = list(dict.fromkeys(args.types)) if args.types else args.types
    if types is None:
        try:
            pla._import_create_project()  # ensures the hub's `src.fabrik` is on sys.path
            from src.fabrik.scaffold import SCAFFOLD_TYPES  # type: ignore[import-not-found]

            types = sorted(SCAFFOLD_TYPES)
        except (RuntimeError, ImportError) as e:
            # This file is governance-synced to ~46 repos but the scaffolder is HUB-ONLY.
            # Where it is unreachable this check cannot ask its question — so it says so and
            # exits 0. It must NOT return 1: `run_optional_check(..., warn_only=True)` fails
            # the gate on ANY non-zero exit ("a broken contract is a louder finding than a
            # quiet one"), so returning 1 here would turn an ADVISORY row RED on every repo
            # that cannot see the hub. Verified by simulating the unreachable scaffolder:
            # the old path returned 1 → gate red (D7 whole-plan validation, 2026-08-25).
            #
            # Exiting 0 with an explicit "0 examined" is this plan's OWN doctrine applied to
            # itself: a silent pass is only honest when it states its denominator. "0 examined
            # — scaffolder unavailable" can never be mistaken for "every pack is reachable".
            print(
                "0 pack(s) examined — the fabrik scaffolder is unavailable here, so pack "
                f"reachability cannot be evaluated ({e}). This check is HUB-ONLY; on a synced "
                "project it is a no-op, not a pass.",
            )
            return 0

    examined = _examined_packs(root, types)

    # ⚠️ An `applies_to` item that is not a REAL scaffold type is silently unexamined and
    # reads as a pass — a pack with `applies_to: ["saas_skeleton"]` (underscore typo) printed
    # "no pack in this corpus declares applies_to yet", which is flatly false: it DID declare
    # one. The doc tells the author to run this check "to confirm", so a typo yielded a
    # confident green. Surface unknown types explicitly. (D7 finding, 2026-08-25.)
    known = set(types)
    unknown: list[tuple[str, str]] = []
    # ONE parse, reused below. Two independent _packs_with_meta() calls re-read and re-parse
    # every pack, and could in principle observe different snapshots if the corpus changed
    # between them. (D7 round 8.)
    packs_meta = pla._packs_with_meta(root)
    # dict.fromkeys DEDUPES while preserving order: `applies_to: [file-worker, file-worker]`
    # is ONE distinct claim, not two. Counting raw entries over-stated claim_pairs (and
    # double-listed the pack in `cleared`) — a denominator over-count in the denominator
    # added one round earlier to fix a denominator under-count. (D7 round 10.)
    claim_pairs = sum(
        1
        for _r, _g, act, ap in packs_meta
        if act != "manual"
        for c in dict.fromkeys(ap)
        if c in known
    )
    for rel, _globs, activation, applies_to in packs_meta:
        if activation == "manual":
            continue
        for claimed in dict.fromkeys(applies_to):
            if claimed not in known:
                unknown.append((rel, claimed))
    findings = pla.audit_layout(root, types)

    # Show WHICH path cleared each examined pack. The denominator over-states reachability
    # (a fresh scaffold carries copied hub boilerplate), so a bare "OK" can hide a pack that
    # cleared only on Dockerfile or libs/subagents rather than on any type-specific source.
    # Printing the evidence makes a boilerplate-only clear visible instead of silent — the
    # same doctrine as the examined-count. (D7 finding, 2026-08-25.)
    cleared: list[tuple[str, str, str]] = []
    flagged = {(f.pack, f.scaffold_type) for f in findings}
    for rel, globs, activation, applies_to in packs_meta:
        if activation == "manual":
            continue
        for claimed in dict.fromkeys(applies_to):  # dedupe — one entry per distinct claim
            if claimed in known and (rel, claimed) not in flagged:
                emitted = pla._emitted_paths_for_type(claimed)
                if emitted is None:
                    # cannot evaluate this type here (no scaffolder) — not a clear, not a
                    # finding; audit_layout skipped it for the same reason.
                    continue
                hit = pla._satisfying_path(emitted, globs)
                if hit:
                    cleared.append((rel, claimed, hit))

    # Which claimed types could not be evaluated at all? Skipping them avoids FALSE
    # unreachable findings — but a bare "OK — every pack reaches" after evaluating NOTHING
    # is this plan's own fail-silent-green, committed by the fix for it. State it.
    unevaluable = sorted(
        {c for _r, _g, act, ap in pla._packs_with_meta(root) if act != "manual"
         for c in ap if c in known and pla._emitted_paths_for_type(c) is None}
    )

    if not args.json:
        for claimed in unevaluable:
            reason = pla._UNEVALUABLE_REASONS.get(claimed)
            print(
                f"NOT EVALUATED: scaffold type {claimed!r} cannot be built here, so packs "
                "claiming it were neither cleared nor flagged"
                + (f" [{reason}]" if reason else "")
            )
        for rel, claimed, hit in cleared:
            print(f"  reachable: {rel} @ {claimed} — via {hit}")
        for rel, claimed in unknown:
            print(
                f"UNKNOWN TYPE: {rel} declares applies_to: {claimed!r}, which is not a "
                "scaffold type"
            )

    if args.json:
        print(
            json.dumps(
                {
                    "examined_count": len(examined),
                    "claim_pairs": claim_pairs,
                    "unevaluable_types": unevaluable,
                    "unknown_types": [
                        {"pack": r, "declared": c} for r, c in unknown
                    ],
                    "examined_packs": examined,
                    "types_checked": types,
                    "findings": [
                        {
                            "pack": f.pack,
                            "scaffold_type": f.scaffold_type,
                            "globs": list(f.globs),
                        }
                        for f in findings
                    ],
                },
                indent=2,
            )
        )
    else:
        print(
            f"Examined {len(examined)} pack(s) / {claim_pairs} claim-pair(s) declaring "
            f"applies_to for a checked type (of {len(types)} scaffold type(s) checked)."
        )
        if not examined:
            print(
            "NOTHING TO CHECK — no pack in this corpus declares a usable applies_to yet"
            + (
                f" ({len(unknown)} pack(s) DID declare one, but named a type that is not a "
                "scaffold type — see UNKNOWN TYPE above; that is a typo to fix, not a pass)"
                if unknown
                else ""
            )
            + ". This is NOT a pass on the packs; it is an unasked question. See "
            "docs/reference/rule-pack-reachability.md for how to add applies_to."
        )
        elif not findings:
            if cleared:
                print(
                    # "every EXAMINED pack" was false whenever a type could not be
                    # evaluated: 2 examined, 1 verified, and the sentence claimed both.
                    # Say what was actually checked. (D7 round 6, finding 14's tail.)
                    "OK — every VERIFIABLE applies_to claim reaches at least one emitted "
                    f"path ({len(cleared)} of {len(examined)} examined pack(s) verified"
                    + (f"; {len(unevaluable)} type(s) NOT EVALUATED" if unevaluable else "")
                    + ")."
                )
            else:
                # 0 verified is NOT "OK". Saying "every pack reaches" after evaluating
                # nothing is exactly the fail-silent-green this plan closes — and the fix
                # for finding 13 briefly reintroduced it.
                print(
                    "NOTHING VERIFIED — 0 claim(s) could be evaluated"
                    + (f" ({len(unevaluable)} type(s) not buildable here)" if unevaluable else "")
                    + ". This is an unasked question, NOT a pass."
                )
        else:
            for f in findings:
                print(
                    f"  UNREACHABLE: {f.pack} claims applies_to includes {f.scaffold_type!r} "
                    f"but globs {list(f.globs)} match ZERO paths that type emits"
                )

    # Advisory by contract (see module docstring / final_gate.py's warn_only=True call
    # site): findings are surfaced above, never fail the gate. A non-zero exit reaching
    # here would mean the script itself is broken, not that a pack was found inert.
    return 0


if __name__ == "__main__":
    sys.exit(main())
