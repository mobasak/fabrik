# T10 — Retire ettw 00–05 → _retired/ (the first half of the 13-doc chain)

## Scope
Pure `git mv` of 7 canonical docs into the single tombstone root `docs/orchestrator/_retired/` (per-file destination paths, `.RETIRED.md` suffix — the pattern mega 05 set), each gaining a two-line tombstone header naming the corpus twin that replaced it (spec § Chain consolidation (a)/(c)). No content rewrite. Both halves of a `git mv` go in the commit pathspec (CLAUDE.md § Shared repo) and `git diff --cached --numstat` must show only renames.  DO-NOT: edit the text beyond the header; touch the assembler, the checks or the sources.

Depends: T07a, T07b
Parallel: ⛓️
Complexity: simple
Gate: test "$(git ls-files docs/orchestrator/epic-to-ticket-workflow | wc -l)" = 7 && test "$(git ls-files docs/orchestrator/_retired/epic-to-ticket-workflow | wc -l)" = 7
Gate: bash -c 'R=$(git log -1 --format=%H --diff-filter=R -- docs/orchestrator/_retired/epic-to-ticket-workflow/); test -n "$R" && test -z "$(git show --numstat --format= -M $R | awk '"'"'$2 > 0'"'"')"'   # pinned to the RENAME COMMIT, not HEAD. HEAD is a shared moving ref on a three-session tree, and this ticket's own Docs: repair lands in a LATER commit — asserting against HEAD would then read that commit and fail on a content edit the plan requires. --diff-filter=R finds the move itself; test -n proves it exists.
Docs: INDEX.md (moved files) · docs/README.md · CHANGELOG.md — orchestrator-applied

⚠️ **`check_doc_links.py` is deliberately NOT a gate on this ticket.** It is a BLOCKING Tier-2 check inside `final_gate.py:1518`, so T16's Gate 1 already enforces it at Merge Order 33 — the first position where it CAN be true. Here it cannot: a move made at this position breaks bare-path refs in files owned by LATER tickets (T11's `EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md` is cited by `docs/reference/command-evaluation-checklist.md:8`, which is T14g's at 30; T12a's `00-trigger-mega-epic-fabrik.md` is cited by `agents-fabrik.md`, which is T14b's at 25). Gating it here would hand the coder an exit-1 whose only fix is a file their own DO-NOT forbids. The referrers this ticket's move breaks are listed on its `Docs:` line instead, applied by the orchestrator at move time.

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
- docs/orchestrator/mega-epic-breakdown/_retired/05-dispatch-epic-tickets-fabrik.RETIRED.md
