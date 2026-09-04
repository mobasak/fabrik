# T14d — review_rubric's dead checklist path, and the ~/.traycer install step

## Scope
Split out of T14b by READ BUDGET (the combined functional sweep measured 594,710 B against 262,144). These are the references the author-blind review proved are FUNCTIONAL rather than prose: left in place they do not merely read stale, they resolve to paths and command names this plan deletes, and T14b's zero-references gate could never pass. **This ticket owns two.** (1) `scripts/review_rubric.py:103` points the rubric at `docs/orchestrator/epic-to-ticket-workflow/EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md`, a file **T11 moves** to `_retired/`. **The decision is made here, not left to the coder: DROP the `ettw` key.** Grounded — `CHECKLISTS` is consumed only internally (`:240` `CHECKLISTS[workflow]`, `:267` `choices=sorted(CHECKLISTS)`), so removing the key raises no `KeyError` and simply removes `--workflow ettw` from the CLI's choices; re-pointing it at the surviving mega checklist would instead make `ettw` a silent alias of `mega`, which is worse than removing it. Severity note, corrected from the first draft: the failure is SOFT, not a crash — `:249-250` prints `- (checklist missing at {path})` and the checklist is read only under `--workflow`, not on every run. The `ettw` mentions in the module docstring (`:6`, `:17-18`) name the workflow and the bare filename WITHOUT a directory, so they survive a path-only grep and must be removed too. (2) The spec's § Chain consolidation (b) retires "the `~/.traycer` install step", which had NO ticket in the first draft: `README.md` carries seven live references including `:152` ("Traycer runs as a Windsurf IDE extension, connecting to WSL via `~/.traycer/cli-agents/`") and `:445` (the configure-CLI-agents step), and `INDEX.md` two more (INDEX is orchestrator-applied). Rewrite the README sections; the Traycer layer is gone. DO-NOT: touch `check_review_coverage.py` (T14e) or `command_run.py` (T14f).

Depends: T09, T11
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_review_rubric.py tests/test_review_rubric_edges.py -q
Gate: test -z "$(git grep -nE 'epic-to-ticket-workflow|EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS|\bettw\b' -- scripts/review_rubric.py)" && test -z "$(git grep -n '\.traycer' -- README.md)"   # the docstring names ettw without a directory; a path-only grep passes over it
# ⚠️ SCOPE NOTE: this ticket's Touches also hold tests/test_review_rubric.py:61 and tests/test_review_rubric_edges.py:60, which each BUILD the string `epic-to-ticket-workflow`. Dropping the ettw key forces edits at :144/:163, but a coder can delete those assertions and leave the dead fixture line — green here, red at T16. The pytest gate plus T16's tree-wide sweep are what close it.
Docs: INDEX.md (the two ~/.traycer rows) · CHANGELOG.md — orchestrator-applied

## Touches
- scripts/review_rubric.py — PRIMARY PATH
- tests/test_review_rubric.py
- tests/test_review_rubric_edges.py
- README.md

## Behavior Contract
- **Given** the retired ettw checklist has moved, **When** `review_rubric.py` runs, **Then** the `ettw` key is gone from `CHECKLISTS`, `--workflow` offers only `mega`, and neither the code nor the module docstring names the retired checklist (scripts/review_rubric.py:103)
- **Given** the README after this ticket, **When** grepped for `.traycer`, **Then** the count is 0 and no section instructs the reader to configure a Traycer CLI agent (README.md:152)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
