# T02b — `--adopt` tags the untagged STRATEGIC_BACKLOG rows in their three real shapes

## Scope
Extend T02a's `--adopt` with step (c′): tag every untagged row of `PROJECT_ROOT/docs/STRATEGIC_BACKLOG.md`, round-robin over the names, in the row's own shape — a TABLE row under a header carrying a `Tag` cell (the hub's `| Effort | Tag | Item | … |` — read ONLY `docs/STRATEGIC_BACKLOG.md:19-40` with `sed -n`, the file is 170 KB and outside the READ budget) gets `` `[<name>]` `` in that cell when it is empty; a table row under a header WITHOUT a `Tag` cell (the projects' `| Effort | Item | Why | Ready when |`) gets `[<name>] ` prefixed to the SECOND cell; a BULLET row (`- `, `* `, `- [ ] `, `- [x] `) gets `[<name>] ` inserted after the list marker and any checkbox. Skipped: rows that already carry `[<a-z0-9-]{1,32}]` anywhere, header/separator rows, the legend table (a header whose first cell is `Tag`), fenced blocks, and rows whose Item is struck through (`~~`). Each change is one `| <row excerpt ≤60 chars> | <name> | backlog-row |` line in the T02a report. Idempotent. A missing STRATEGIC_BACKLOG.md is silently nothing (23 of 41 repos have one). DO-NOT: tag `[x]`/`[ ]` checkboxes as names (the r1 pipeline error); reorder or reflow any row; touch PLANS.md or the ledger (T02a); touch the `--check` path (T03).

Depends: T02a
Parallel: ⛓️
Complexity: simple
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_docs_updater_adopt.py -q
Docs: CHANGELOG (Deltas)

## Touches
- scripts/docs_updater.py — PRIMARY PATH
- tests/test_docs_updater_adopt.py

## Behavior Contract
- **Given** a backlog with a hub-shaped table (`Tag` column, one empty tag cell), a project-shaped table (no `Tag` column, one untagged row), and three bullet rows (`- `, `- [ ] `, `- [x] `), **When** `--adopt alpha,beta --single-window` runs, **Then** the empty tag cell reads `` `[alpha]` ``, the project row's second cell starts with `[beta] `, and the bullets read `- [alpha] …`, `- [ ] [beta] …`, `- [x] [alpha] …` — round-robin across all five in file order (docs/STRATEGIC_BACKLOG.md:19)
- **Given** a row already carrying `[infra]`, the legend table, a header row, and a fenced block containing `- item`, **When** `--adopt` runs, **Then** none of them changes (scripts/docs_updater.py:946)
- **Given** the state after one run, **When** it runs again, **Then** STRATEGIC_BACKLOG.md is byte-identical (scripts/docs_updater.py:1046)
- **Given** no STRATEGIC_BACKLOG.md, **When** `--adopt` runs, **Then** it succeeds with no backlog rows in the report (scripts/docs_updater.py:1550)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/docs_updater.py
- tests/test_docs_updater_adopt.py
- docs/superpowers/specs/2026-09-06-multi-agent-adoption-design.md
