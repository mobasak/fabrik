# T10 — Retire ettw 00–05 → _retired/ (the first half of the 13-doc chain)

## Scope
Pure `git mv` of 7 canonical docs into the single tombstone root `docs/orchestrator/_retired/` (per-file destination paths, `.RETIRED.md` suffix — the pattern mega 05 set), each gaining a two-line tombstone header naming the corpus twin that replaced it (spec § Chain consolidation (a)/(c)). No content rewrite. Both halves of a `git mv` go in the commit pathspec (CLAUDE.md § Shared repo) and `git diff --cached --numstat` must show only renames.  DO-NOT: edit the text beyond the header; touch the assembler, the checks or the sources.

Depends: T07
Parallel: ⛓️
Complexity: simple
Gate: git diff --cached --numstat | grep -vc '^0\t0\|=>' ; test "$(git ls-files docs/orchestrator/epic-to-ticket-workflow | wc -l)" = "0" || true
Gate: python3 scripts/enforcement/check_doc_links.py
Docs: INDEX.md (moved files) · docs/README.md · CHANGELOG.md — orchestrator-applied

## Touches
- docs/orchestrator/epic-to-ticket-workflow/00-trigger-fabrik.md — PRIMARY PATH
- docs/orchestrator/epic-to-ticket-workflow/01-decisions-lock-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/01R-decisions-review-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/02-core-flows-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/03-tech-plan-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/04-deploy-plan-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/05-ticket-outline-fabrik.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/00-trigger-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/01-decisions-lock-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/01R-decisions-review-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/02-core-flows-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/03-tech-plan-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/04-deploy-plan-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/05-ticket-outline-fabrik.RETIRED.md

## Behavior Contract
- **Given** the move commit, **When** `git ls-files docs/orchestrator/epic-to-ticket-workflow/00-trigger-fabrik.md` runs, **Then** it prints nothing and `docs/orchestrator/_retired/epic-to-ticket-workflow/00-trigger-fabrik.RETIRED.md` exists byte-identical to the moved text plus its tombstone header (docs/orchestrator/epic-to-ticket-workflow/00-trigger-fabrik.md:1)
- **Given** the moved files, **When** `git log --follow` is run on any of them, **Then** history is preserved through the rename (docs/orchestrator/epic-to-ticket-workflow/05-ticket-outline-fabrik.md:1)
- **Given** the tree after the move, **When** `python3 scripts/enforcement/check_doc_links.py` runs, **Then** no link into the moved paths is reported broken from a non-archived, non-ledger doc (scripts/enforcement/check_traycer_chain.py:28)

## Context Files
