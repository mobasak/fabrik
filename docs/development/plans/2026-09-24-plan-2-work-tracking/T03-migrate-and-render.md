# T03 — `migrate-backlog` and `render`: the backlog becomes a view

## Scope

Extends `scripts/work.py` with the `render` and `migrate-backlog` rows of spec § The CLI and all of
spec § The backlog becomes a view.

`migrate-backlog` reads `docs/STRATEGIC_BACKLOG.md` in the shapes the grounding seats counted in the
hub file on 2026-09-24 (4,867 lines, 571 KB — the V2 test copies it into its tmp dir at run time; the
coder reads a sample of each shape, never the whole file): `## [tag]` headings (140), `### ` headings (20, 6 of them untagged
narrative sub-headers), `- **[tag] …**` bullets (35), `- [ ] **[tag] …**` (80), `- [x]` (11, all
resolved), `- ~~**[tag] …**~~` (1), and table rows under a header with a `Tag`/`Owner` cell (6). A row's
body runs to the next line starting `##`, `### `, `- ` or `|` at column 0. Reuse the existing
fence-aware row classifier by import: `classify_backlog_row` and `_BACKLOG_BULLET_RE`
(`scripts/docs_updater.py:1041`, `:990`). Resolved markers: `~~`, `RESOLVED`, `✅`, `SHIPPED`, `[x]`,
plus `CLOSED`, `DONE`, `LANDED`, `MOOT`, `DRILLED` as whole words in the row's title line. Tags map to
owners; a cross-tag (`[infra + fleet]`, `[intel→fabrik-lib]`) keeps its first canonical tag as owner and
the full tag in `note`. Idempotent: a second run creates nothing (each item records its source row's
digest in `note`). Records `migrated_at` in `config.json`.

`render` writes only the `<!-- AUTO-GENERATED:BACKLOG:START -->` … `END` block, through
`replace_block` (`scripts/docs_updater.py:722`) with a `BACKLOG_BLOCK_RE` defined in `work.py`;
output is deterministic (sorted by priority, owner, then id) and carries no timestamp in the body.
When the markers are absent, `render` inserts them once below the file's `---` rule after the header.

⚠️ The spec's "253 open, 36 resolved" (spec § Validation V2) is a 2026-09-24 snapshot that neither
grounding seat could reproduce (287–293 candidate rows depending on how H3 narrative headers count),
and the file grows daily. V2 is therefore re-derived at run time: the test's own independent reader
counts rows and resolved markers, and migration must match it row for row. No frozen number.

DO-NOT: write `docs/STRATEGIC_BACKLOG.md` itself (a governance file — the hub migration and render run
at adoption, T10, through the orchestrator); any other doc.

Depends: T02
Parallel: ⛓️
Complexity: complex
Gate: .venv/bin/python -m pytest tests/test_work_migrate.py -q
Docs: none here — the reference doc is T09's

## Touches
- scripts/work.py — PRIMARY PATH
- tests/test_work_migrate.py (new)

## Behavior Contract
- **Given** a fixture backlog with one row of every shape above, open and resolved, **When** `migrate-backlog` runs, **Then** every row becomes exactly one item, resolved rows are `done` with `legacy: true`, the others `open` with the owner from the tag, and each row's full text is kept (spec § The backlog becomes a view)
- **Given** a row no shape matches, **When** `migrate-backlog` runs, **Then** it becomes an item with an empty owner and the raw text kept, and the run's output lists it for the distributor (spec § The backlog becomes a view)
- **Given** a migrated store, **When** `migrate-backlog` runs again, **Then** it creates no item (spec § The backlog becomes a view)
- **Given** a copy of the hub's `docs/STRATEGIC_BACKLOG.md`, **When** `migrate-backlog` then `render` run, **Then** the item count and the open/done split equal what the test's own independent reader counts in that copy, and every source row's text appears in its item (spec § Validation V2)
- **Given** a rendered backlog, **When** `render` runs again, **Then** the file is byte-identical, and hand-written text above and below the block is untouched (spec § The backlog becomes a view)

## Context Files
- docs/superpowers/specs/2026-09-24-work-tracking-design.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/docs_updater.py — `classify_backlog_row` (scripts/docs_updater.py:1041) and `replace_block` (scripts/docs_updater.py:722)
