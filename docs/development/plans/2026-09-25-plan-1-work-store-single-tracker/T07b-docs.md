# T07b — The landing docs

## Scope

Implements spec § Documentation landing sites, every sentence written against the merged code of
T01–T06 (each claim executed, never recalled):

1. `docs/reference/work-tracking.md` — § The item (`:33-52`): the kinds `mail`, `feedback` (and when
   each is created), the link keys `mail`, `command`, `session`, `next_at` on `next` items,
   `alt_block_digests`/`alt_ids` on awaiting items; the CLI table (`:86-113`): `ready` (the new default)
   and `ready --all`, `drop <id> --duplicate-of <keep>`, `add` refusing `mail`/`feedback`, `done`
   refusing them by hand; § NEXT, DECISION blocks and the register (`:135-168`): the four D3 rules in
   order replace the one bullet at `:163-164`, plus the session's one `next` item and the 7-day close;
   a new § The view (D1, D4, D6: the obligation lines, `on it:` lines, the `status` lines, the
   unnamed-window line); § Validation reading: `python3 scripts/sysadmin/next_census.py --since 7 --repo .`.
   `tests/test_work_doc_verbs.py:38-60` keeps the verb set equal to the CLI.
2. `docs/reference/thread-anchors.md` — the "**The work-store item.**" paragraph (`:87-97`) gains one
   sentence: in a repo with a store, a free-text NEXT the register accepts also becomes the session's
   one `next` item, and a NEXT naming an item claims it; the register itself is unchanged (D-392).
3. `docs/reference/fabrik-mail.md` — the "**Claim/ack = atomic-by-rename.**" bullet (`:61-84`) and the
   "**Requeue crash recovery.**" bullet (`:126-129`): `claim` creates the mail item in the repo whose
   mailbox it is, `ack` closes it `done`, `requeue` closes it `dropped`; a cross-repo `--repo` creates
   nothing.
4. `docs/workstation/hooks-index.md` — the one `thread_anchor.py` row (`:23`): the Stop harvest now
   claims the item a NEXT names and keeps the session's `next` item; the prompt block now carries the
   obligation lines, every other session's claims and the unnamed-window line.
5. `docs/reference/command-run-protocol.md` — the improve-loop close-out (`:314-330`) and the CLI line
   (`:408-409`): `--take <command>` and the item `--mark-answered` closes.
6. The D3 section states the classifier (`classify_next`, T05a) once — hold / names-item / free-text — and that the census uses the same function.

DO-NOT: `CLAUDE.md`, `templates/governance/CLAUDE.md` (T07a); the `## Related scripts` blocks (rendered from `# AFTER-EDIT:` headers by `scripts/render_doc_script_links.py` — never hand-edited).

Depends: T02b, T03, T04, T05b, T06
Parallel: ⚡
Complexity: simple
Gate: .venv/bin/python -m pytest tests/test_work_doc_verbs.py -q && python3 scripts/enforcement/check_citations_resolve.py --changed
Docs: the five docs above; `INDEX.md` (the census row) and `docs/README.md` need no change beyond T06's Deltas row

## Touches
- docs/reference/work-tracking.md — PRIMARY PATH
- docs/reference/thread-anchors.md
- docs/reference/fabrik-mail.md
- docs/workstation/hooks-index.md
- docs/reference/command-run-protocol.md

## Behavior Contract
- **Given** the merged CLI, **When** `tests/test_work_doc_verbs.py` runs, **Then** the reference doc's verb table equals the parser's verbs, `--duplicate-of` and `--all` included (spec § Documentation landing sites)
- **Given** the five edited docs, **When** `python3 scripts/enforcement/check_citations_resolve.py --changed` runs, **Then** it reports every `path:line` citation in the changed `docs/reference/` files as landing, with the examined count stated (spec § Documentation landing sites)

## Context Files
- .windsurf/rules/core/40-documentation.md
- docs/reference/work-tracking.md
- docs/reference/thread-anchors.md
- docs/reference/fabrik-mail.md
- docs/workstation/hooks-index.md
- docs/reference/command-run-protocol.md
- tests/test_work_doc_verbs.py
