# T02 — corpus glob audit across all 12 scaffold types

Depends: none
Parallel: ⚡
Complexity: native
Docs: docs/reference/rule-pack-reachability.md
Gate: python -m pytest tests/enforcement/test_pack_reachability.py -q

## Scope

Build `scripts/enforcement/pack_layout_audit.py::audit_layout(root, types)` — the corpus×type matrix
that answers "which packs match zero paths this scaffold type actually emits". Reuse T04's matcher;
reuse `review_rubric._packs()` as the corpus loader. Correct the two PROVEN-inert GLOB-ACTIVATED packs
(`core/75-workers-jobs.md`, `core/app-audit-log.md`). DO-NOT widen a glob so
a pack matches a file it does not govern — a false match trains agents to ignore the rubric. DO-NOT
write a third glob parser. DO-NOT report or re-glob an `activation: manual` pack — all four
`00-domain-*` packs are manual on purpose and `saas/00-domain-saas.md:6-11` forbids adding one. DO-NOT re-touch `core/15-api-contracts.md` (landed in 29194562).

## Touches

- scripts/enforcement/pack_layout_audit.py
- .windsurf/rules/core/75-workers-jobs.md
- .windsurf/rules/core/app-audit-log.md

## Behavior Contract

- **Given** the 56-pack corpus and the 12 scaffold types, **When** the layout audit runs, **Then** it emits one row per (pack, type) pair where the pack declares applicability and matches zero emitted paths (scripts/enforcement/pack_layout_audit.py:1).
- **Given** the two known-inert glob-activated packs, **When** their globs are corrected, **Then** each matches at least one real file in a scaffolded project of its declared type (.windsurf/rules/core/75-workers-jobs.md:3).
- **Given** a pack whose frontmatter says `activation: manual`, **When** the layout audit runs, **Then** it is excluded from the report entirely rather than counted as inert (.windsurf/rules/saas/00-domain-saas.md:6).

## Context Files

- scripts/review_rubric.py
