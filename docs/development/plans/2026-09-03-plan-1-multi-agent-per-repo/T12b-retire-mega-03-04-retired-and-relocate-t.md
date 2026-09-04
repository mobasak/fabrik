# T12b — Retire mega 03 + 04 → _retired/ and relocate the 05 tombstone; the mega dir keeps only the schema + checklist

## Scope
Pure `git mv` of 2 canonical docs into the single tombstone root `docs/orchestrator/_retired/` (per-file destination paths, `.RETIRED.md` suffix — the pattern mega 05 set), each gaining a two-line tombstone header naming the corpus twin that replaced it (spec § Chain consolidation (a)/(c)). No content rewrite. Both halves of a `git mv` go in the commit pathspec (CLAUDE.md § Shared repo) and `git diff --cached --numstat` must show only renames. Also `git mv docs/orchestrator/mega-epic-breakdown/_retired/05-dispatch-epic-tickets-fabrik.RETIRED.md docs/orchestrator/_retired/mega-epic-breakdown/05-dispatch-epic-tickets-fabrik.RETIRED.md` so one `_retired/` root holds every tombstone; `docs/orchestrator/mega-epic-breakdown/` then holds `EPIC-ARTIFACT-SCHEMA.md` and `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` only. DO-NOT: edit the text beyond the header; touch the assembler, the checks or the sources.

Depends: T06b, T06c, T07a, T07b
Parallel: ⛓️
Complexity: simple
Gate: test "$(git ls-files 'docs/orchestrator/mega-epic-breakdown/*-fabrik.md' | wc -l)" = 0 && test "$(git ls-files docs/orchestrator/_retired/mega-epic-breakdown | wc -l)" = 5
Gate: test -z "$(git diff --cached -M --numstat | awk '$2 > 0')"   # every staged change is a rename (+header only), zero deletions
Gate: python3 scripts/enforcement/check_doc_links.py
Docs: INDEX.md (moved files) · docs/README.md · CHANGELOG.md — orchestrator-applied

## Touches
- docs/orchestrator/mega-epic-breakdown/03-expand-epic-files-fabrik.md — PRIMARY PATH
- docs/orchestrator/mega-epic-breakdown/04-cross-epic-validation-fabrik.md
- docs/orchestrator/_retired/mega-epic-breakdown/03-expand-epic-files-fabrik.RETIRED.md
- docs/orchestrator/_retired/mega-epic-breakdown/04-cross-epic-validation-fabrik.RETIRED.md
- docs/orchestrator/mega-epic-breakdown/_retired/05-dispatch-epic-tickets-fabrik.RETIRED.md
- docs/orchestrator/_retired/mega-epic-breakdown/05-dispatch-epic-tickets-fabrik.RETIRED.md

## Behavior Contract
- **Given** the move commit, **When** `git ls-files docs/orchestrator/mega-epic-breakdown/03-expand-epic-files-fabrik.md` runs, **Then** it prints nothing and `docs/orchestrator/_retired/mega-epic-breakdown/03-expand-epic-files-fabrik.RETIRED.md` exists byte-identical to the moved text plus its tombstone header (docs/orchestrator/mega-epic-breakdown/03-expand-epic-files-fabrik.md:1)
- **Given** the moved files, **When** `git log --follow` is run on any of them, **Then** history is preserved through the rename (docs/orchestrator/mega-epic-breakdown/04-cross-epic-validation-fabrik.md:1)
- **Given** the tree after the move, **When** `python3 scripts/enforcement/check_doc_links.py` runs, **Then** no link into the moved paths is reported broken from a non-archived, non-ledger doc (scripts/enforcement/check_traycer_chain.py:28)

## Context Files
- docs/orchestrator/mega-epic-breakdown/_retired/05-dispatch-epic-tickets-fabrik.RETIRED.md
