# T02 — corpus glob audit across all 12 scaffold types

Depends: T04
Parallel: ⛓️
Complexity: native
Docs: docs/reference/rule-pack-reachability.md
Gate: python -m pytest tests/enforcement/test_pack_layout_audit.py -q

## Scope

Build `scripts/enforcement/pack_layout_audit.py::audit_layout(root, types)` — the corpus×type matrix
that answers "which packs match zero paths this scaffold type actually emits". Consume T04's
`pack_matches_path` / `any_path_matches` by those exact names (T04 merges first — do not re-implement
matching); reuse `review_rubric._packs()` as the corpus loader. **Enumerate the 12 types from the LIVE registry,
never from memory and never by reading the 257 KB module** (it does not fit a ticket read budget):

```
$ python -c "from src.fabrik.scaffold import SCAFFOLD_TYPES; print(sorted(SCAFFOLD_TYPES))"
['chrome-extension', 'desktop-app', 'docusaurus', 'file-api', 'file-worker', 'mobile-app',
 'node-api', 'python-api', 'python-api-gpu', 'saas-skeleton', 'static-site', 'wordpress']
```

**Applicability comes from the declared `applies_to:` frontmatter list, never from the globs under
test** — the format is settled in the spine's Global Constraints and restated here so this ticket is
self-contained: `applies_to: [<scaffold type>, …]` sits in pack frontmatter beside the `globs:` it
cross-checks. Correct the two PROVEN-inert GLOB-ACTIVATED packs (`core/75-workers-jobs.md`,
`core/app-audit-log.md`) AND seed each with its `applies_to:` list — without at least one pack
declaring the field, T03's check ships asking nothing (the fail-silent-green class this plan exists
to close).

DO-NOT widen a glob so a pack matches a file it does not govern — a false match trains agents to
ignore the rubric. DO-NOT write a third path matcher — consume `rules_match.py`. DO-NOT report or re-glob an `activation: manual`
pack — all four `00-domain-*` packs are manual on purpose and `saas/00-domain-saas.md:6-11` forbids
adding one. DO-NOT re-touch `core/15-api-contracts.md` (landed in 29194562).

## Touches

- scripts/enforcement/pack_layout_audit.py
- tests/enforcement/test_pack_layout_audit.py
- .windsurf/rules/core/75-workers-jobs.md
- .windsurf/rules/core/app-audit-log.md

## Behavior Contract

- **Given** the 56-pack corpus and the 12 scaffold types, **When** the layout audit runs, **Then** it emits one row per (pack, type) pair the pack's `applies_to` claims and matches zero emitted paths (scripts/enforcement/pack_layout_audit.py:1).
- **Given** the two known-inert glob-activated packs, **When** their globs are corrected and their `applies_to` seeded, **Then** each matches at least one real file in a scaffolded project of its declared type (.windsurf/rules/core/75-workers-jobs.md:3).
- **Given** a pack whose frontmatter says `activation: manual`, **When** the layout audit runs, **Then** it is excluded from the report entirely rather than counted as inert (.windsurf/rules/saas/00-domain-saas.md:6).

## Context Files

- scripts/review_rubric.py
- scripts/rules_match.py
- .windsurf/rules/saas/00-domain-saas.md
