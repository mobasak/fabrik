# T12a — Retire mega 00 + 02 → _retired/ (their text now lives in /fabrik-vision and /fabrik-epics)

## Scope
Pure `git mv` of 2 canonical docs into the single tombstone root `docs/orchestrator/_retired/` (per-file destination paths, `.RETIRED.md` suffix — the pattern mega 05 set), each gaining a two-line tombstone header naming the corpus twin that replaced it (spec § Chain consolidation (a)/(c)). No content rewrite. Both halves of a `git mv` go in the commit pathspec (CLAUDE.md § Shared repo) and `git diff --cached --numstat` must show only renames.  DO-NOT: edit the text beyond the header; touch the assembler, the checks or the sources.

Depends: T06a, T06b, T07a, T07b
Parallel: ⛓️
Complexity: simple
Gate: test "$(git ls-files 'docs/orchestrator/mega-epic-breakdown/*-fabrik.md' | wc -l)" = 2 && test "$(git ls-files docs/orchestrator/_retired/mega-epic-breakdown | wc -l)" = 2
Gate: test -z "$(git diff --cached -M --numstat | awk '$2 > 0')"   # every staged change is a rename (+header only), zero deletions
Gate: python3 scripts/enforcement/check_doc_links.py
Docs: INDEX.md (moved files) · docs/README.md · CHANGELOG.md — orchestrator-applied

## Touches
- docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md — PRIMARY PATH
- docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md
- docs/orchestrator/_retired/mega-epic-breakdown/00-trigger-mega-epic-fabrik.RETIRED.md
- docs/orchestrator/_retired/mega-epic-breakdown/02-epic-decomposition-fabrik.RETIRED.md

## Behavior Contract
- **Given** the move commit, **When** `git ls-files docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md` runs, **Then** it prints nothing and `docs/orchestrator/_retired/mega-epic-breakdown/00-trigger-mega-epic-fabrik.RETIRED.md` exists byte-identical to the moved text plus its tombstone header (docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md:1)
- **Given** the moved files, **When** `git log --follow` is run on any of them, **Then** history is preserved through the rename (docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md:1)
- **Given** the tree after the move, **When** `python3 scripts/enforcement/check_doc_links.py` runs, **Then** no link into the moved paths is reported broken from a non-archived, non-ledger doc (scripts/enforcement/check_traycer_chain.py:28)

## Context Files
- docs/orchestrator/mega-epic-breakdown/_retired/05-dispatch-epic-tickets-fabrik.RETIRED.md
