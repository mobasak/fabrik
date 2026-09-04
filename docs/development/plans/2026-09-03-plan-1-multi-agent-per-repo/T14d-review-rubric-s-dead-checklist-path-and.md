# T14d — review_rubric's dead checklist path, and the ~/.traycer install step

## Scope
Split out of T14b by READ BUDGET (the combined functional sweep measured 594,710 B against 262,144). These are the references the author-blind review proved are FUNCTIONAL rather than prose: left in place they do not merely read stale, they resolve to paths and command names this plan deletes, and T14b's zero-references gate could never pass. **This ticket owns two.** (1) `scripts/review_rubric.py:103` points the rubric at `docs/orchestrator/epic-to-ticket-workflow/EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md`, a file **T11 moves** to `_retired/` — after which the rubric resolves a dead path on every run, in the hub and in every project it is synced to. Re-point it at the surviving mega checklist, or drop the leg if the ettw checklist has no successor (state which, in the commit). (2) The spec's § Chain consolidation (b) retires "the `~/.traycer` install step", which had NO ticket in the first draft: `README.md` carries seven live references including `:152` ("Traycer runs as a Windsurf IDE extension, connecting to WSL via `~/.traycer/cli-agents/`") and `:445` (the configure-CLI-agents step), and `INDEX.md` two more (INDEX is orchestrator-applied). Rewrite the README sections; the Traycer layer is gone. DO-NOT: touch `check_review_coverage.py` (T14e) or `command_run.py` (T14f).

Depends: T09, T11
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_review_rubric.py tests/test_review_rubric_edges.py -q
Gate: test -z "$(git grep -n 'epic-to-ticket-workflow' -- scripts/review_rubric.py)" && test -z "$(git grep -n '\.traycer' -- README.md)"
Docs: INDEX.md (the two ~/.traycer rows) · CHANGELOG.md — orchestrator-applied

## Touches
- scripts/review_rubric.py — PRIMARY PATH
- tests/test_review_rubric.py
- tests/test_review_rubric_edges.py
- README.md

## Behavior Contract
- **Given** the retired ettw checklist has moved, **When** `review_rubric.py` runs, **Then** every path it reads resolves and no leg points into `docs/orchestrator/epic-to-ticket-workflow/` (scripts/review_rubric.py:103)
- **Given** the README after this ticket, **When** grepped for `.traycer`, **Then** the count is 0 and no section instructs the reader to configure a Traycer CLI agent (README.md:152)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
