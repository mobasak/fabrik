#!/usr/bin/env python3
# AFTER-EDIT: scripts/select_rules.py tests/test_review_rubric.py
"""Armed-review rubric extractor — turns Tier-3 reviews from "reviewer reads the packs"
into "the matched rule rubric is INJECTED into every finder prompt" (spec G5/G6; plan-2 WS-B).

    python scripts/review_rubric.py --changed <path> [<path> …] [--workflow {mega,ettw}]

Emits, on stdout, the rubric a review dispatcher pastes into each finder's prompt:

  · FLOOR (always, regardless of glob — spec L3): the high-blast-radius packs
    `core/35-security-auth.md` + `core/25-data-postgres.md` + `core/30-ops.md`, plus a fixed
    12-Factor axis list. "Independent selection" of the same glob function isn't independence —
    the floor is what guarantees a review is never un-armed on the rules that hurt most.
  · MATCHED (per changed path): every pack whose frontmatter glob matches a changed path —
    mandate lines only (lines carrying MUST / ⚠️ / never / BANNED / HARD STOP).
  · WORKFLOW CHECKLIST (only with --workflow): the command-authoring QA items — `mega` reads
    EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md, `ettw` reads
    EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md. Item = a numbered line ("N. …") — the
    checklists' own format. NEVER emitted without --workflow: they are command-file QA,
    not a code rubric.
  · promote-to-check_* (byproduct): injected mandates that look deterministically greppable
    (a backticked literal inside a mandate line) — candidates for Tier-1 promotion, feeding
    the spec's drain-Tier-3-into-Tier-1 standing direction.

Honesty (spec L1/L2): this arms the reviewer; it raises compliance probability — it does not
guarantee it. Stdlib-only: this file is fleet-synced (fabrik_synced_manifest) and must run in
every project venv with no extra deps. Reuses select_rules' frontmatter parser + tail-match.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

import select_rules  # noqa: E402 - the shared frontmatter parser + glob tail-matching

# ⚠️ LOCKSTEP CONTRACT: this file uses select_rules' PRIVATE symbols (_FM, _parse_frontmatter,
# _tail_matches, _expand_braces). Both files are co-synced fleet-wide (fabrik_synced_manifest
# CORE_SCRIPTS) — renaming those symbols breaks armed reviews in every project. Rename together.

# The mandatory-core floor (spec L3) — always injected, regardless of glob match.
FLOOR_PACKS = (
    "core/35-security-auth.md",
    "core/25-data-postgres.md",
    "core/30-ops.md",
)

# Fixed 12-Factor axis list (always injected with the floor). The matched packs carry the
# full per-domain mandates; this is the axis map a finder hunts against even when no pack
# glob fires (mirrors /fabrik-review's static hunt table — belt-and-suspenders by design).
TWELVE_FACTOR = (
    "I codebase: shared code → fabrik-lib, never two apps in one repo",
    "II deps: every shelled-out binary installed + pinned in the Dockerfile",
    "III config: granular env vars; no secrets in code; no grouped env sets",
    "IV backing services: swappable by DSN/config change only",
    "V build/release/run: releases immutable; never hot-patch a container",
    "VI processes: stateless; session state → redis-main; no sticky sessions",
    "VII port binding: bind in-container; Traefik routes; no host ports:",
    "VIII concurrency: scale out; never daemonize or write PID files",
    "IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent",
    "X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres",
    "XI logs: unbuffered stdout only; the app never writes/rotates a logfile",
    "XII admin: migrations/one-offs run against the deployed release, never startup",
)

_MANDATE = re.compile(
    r"MUST|⚠️|\bnever\b|\bNever\b|\bNEVER\b|\bDo not\b|\bdo NOT\b|BANNED|HARD STOP"
)
_CHECK_ITEM = re.compile(r"^\s*\d+[a-z]?\.\s+\S")  # 84a.-style sub-items count too
_GREPPABLE = re.compile(r"`[^`]+`")

CHECKLISTS = {
    "mega": Path(
        "docs/orchestrator/mega-epic-breakdown/EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md"
    ),
    "ettw": Path(
        "docs/orchestrator/epic-to-ticket-workflow/EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md"
    ),
}


_CONDITIONAL_HEADING = re.compile(r"(?<!non-)\b(legacy|migration-only|deprecated|retired)\b", re.IGNORECASE)


def _mandate_lines(body: str) -> list[str]:
    """The pack's enforceable lines — what a finder hunts against (not the whole doc).

    Section-aware: content under a heading marked CONDITIONAL (`legacy` / `migration-only` /
    `deprecated` / `retired`) is SKIPPED — a dual-pattern pack (e.g. 35-security-auth's Pattern B)
    would otherwise inject retired mandates as always-on floor rules, producing confident false
    positives against the DEFAULT path (the "gate that cries wolf" failure). Convention: packs
    MUST mark conditional sections in the heading itself; unmarked content is treated as core.
    """
    out = []
    skipping = False
    skip_level = 0
    in_fence = False
    fence_char = ""
    fence_len = 0
    for line in body.splitlines():
        s = line.strip()
        if not in_fence:
            # fenced code blocks (backtick OR tilde — CommonMark allows both) are EXAMPLES,
            # not prose: their `#` comments are not headings (they'd close a conditional skip
            # early) and their MUST/BANNED lines are not mandates (live noise: the ❌-Banned
            # code samples were being injected verbatim)
            if s.startswith(("```", "~~~")):
                in_fence = True
                fence_char = s[0]
                fence_len = len(s) - len(s.lstrip(fence_char))
                continue
        else:
            # CommonMark closing rule: a run of the SAME char, at least as LONG as the opener
            # — so a literal ``` inside a ````-opened block (the standard way to show fence
            # syntax in an example) is content, and ~~~ inside a ```-fence is content too
            run = len(s) - len(s.lstrip(fence_char))
            if run >= fence_len:
                in_fence = False
            continue
        if s.startswith("#"):
            level = len(s) - len(s.lstrip("#"))
            if skipping and level <= skip_level:
                skipping = False
            if _CONDITIONAL_HEADING.search(s) and not skipping:
                # only the OUTERMOST conditional heading sets the skip boundary — a nested
                # conditional heading must not deepen skip_level, or a later mid-level heading
                # would end the outer skip early and leak its mandates
                skipping = True
                skip_level = level
            continue
        if skipping:
            continue
        if s and _MANDATE.search(s):
            out.append(s if s.startswith(("-", "*", "|")) else f"- {s}")
    if in_fence:
        # an unclosed fence would have silently swallowed every mandate after it — surface
        # the anomaly IN the rubric so the armed reviewer sees the gap instead of nothing
        out.append(
            "- ⚠ MALFORMED PACK: an unclosed code fence truncated this pack's mandate scan — "
            "read the pack directly; report the missing closing fence upstream"
        )
    return out


def _packs(root: Path) -> list[tuple[str, list[str], str]]:
    """[(relative pack path, globs, body)] for every pack under root/.windsurf/rules."""
    rules_dir = root / ".windsurf" / "rules"
    packs = []
    if rules_dir.exists():
        for pack in sorted(rules_dir.rglob("*.md")):
            text = pack.read_text(encoding="utf-8", errors="replace")
            globs, _desc = select_rules._parse_frontmatter(text)
            # Strip the YAML frontmatter before mandate-scanning: a description like
            # "tokens MUST rotate" is metadata, not a mandate — scanning it injects noise.
            body = select_rules._FM.sub("", text, count=1)
            packs.append((pack.relative_to(rules_dir).as_posix(), globs, body))
    return packs


def _glob_matches_path(changed: str, glob: str) -> bool:
    """Does this changed path match this pack glob? (select_rules' tail-match semantics,
    applied to a single path instead of the whole tree.)"""
    pat = glob.strip().lstrip("/")
    if pat.startswith("**/"):
        pat = pat[3:]
    if pat.endswith("/**"):
        pat = pat[:-3]
    if not pat:
        # a wildcard-only glob (`**/`, `/**`) means match-everything; arming errs SAFE
        # (deliberate divergence from select_rules, where empty = not-ACTIVE)
        return True
    rel = changed.strip().lstrip("/")
    return any(
        select_rules._tail_matches(prefix, expanded)
        for expanded in select_rules._expand_braces(pat)
        # a dir-glob like uploads/** must match a PARENT segment too, not just the full path
        for prefix in _prefixes(rel)
    )


def _prefixes(rel: str) -> list[str]:
    segs = rel.split("/")
    return ["/".join(segs[: i + 1]) for i in range(len(segs))]


def build_rubric(changed: list[str], workflow: str | None, root: Path) -> str:
    packs = _packs(root)
    by_rel = {rel: (globs, body) for rel, globs, body in packs}
    out: list[str] = [
        "# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)"
    ]
    out.append(
        "# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it."
    )
    promote: list[str] = []

    emitted: set[str] = set()
    out.append("\n## FLOOR — always injected, regardless of glob (spec L3)")
    for rel in FLOOR_PACKS:
        out.append(f"\n### {rel}")
        if rel in by_rel:
            lines = _mandate_lines(by_rel[rel][1])
            out.extend(lines)
            promote.extend(line for line in lines if _GREPPABLE.search(line))
        else:
            out.append(
                f"- (pack missing at {root}/.windsurf/rules/{rel} — arm from the matched set)"
            )
        emitted.add(rel)

    out.append("\n### 12-FACTOR (all twelve axes)")
    out.extend(f"- {axis}" for axis in TWELVE_FACTOR)

    matched_any = False
    for rel, globs, body in packs:
        if rel in emitted:
            continue
        hits = [c for c in changed if any(_glob_matches_path(c, g) for g in globs)]
        if hits:
            if not matched_any:
                out.append("\n## MATCHED — packs whose globs hit the changed paths")
                matched_any = True
            out.append(f"\n### {rel}  (hit: {', '.join(sorted(set(hits))[:3])})")
            lines = _mandate_lines(body)
            out.extend(lines)
            promote.extend(line for line in lines if _GREPPABLE.search(line))
    if not matched_any:
        out.append(
            "\n## MATCHED — none (no pack glob hits the changed paths; the FLOOR still arms you)"
        )

    if workflow:
        path = root / CHECKLISTS[workflow]
        out.append(f"\n## WORKFLOW CHECKLIST ({workflow}) — command-authoring QA items")
        if path.exists():
            items = [
                line.strip()
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                if _CHECK_ITEM.match(line)
            ]
            out.extend(f"- {i}" for i in items)
        else:
            out.append(f"- (checklist missing at {path})")

    if promote:
        uniq = list(dict.fromkeys(promote))
        out.append(
            f"\n# promote-to-check_*: {len(uniq)} injected mandate(s) look deterministically greppable"
        )
        out.extend(uniq[:20])
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit the injectable review rubric for changed paths.")
    ap.add_argument(
        "--changed", nargs="+", required=True, help="changed file paths (repo-relative)"
    )
    ap.add_argument(
        "--workflow", choices=sorted(CHECKLISTS), help="ALSO inject this command-chain checklist"
    )
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    args = ap.parse_args()
    try:
        print(build_rubric(args.changed, args.workflow, args.project_root.resolve()), end="")
    except BrokenPipeError:  # `| head` closing the pipe is fine for a CLI emitter
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
