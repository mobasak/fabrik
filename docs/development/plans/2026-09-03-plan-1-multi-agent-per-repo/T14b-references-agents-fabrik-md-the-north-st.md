# T14b — References — agents-fabrik.md, the north-star, command-corpus-check.md: zero references to the retired chains outside archives and ledgers

## Scope
The link sweep, re-derived 2026-09-04 with THIS ticket's own gate exclusions: 28 files reference `epic-to-ticket-workflow`, 8 `_traycer-skills`, 8 `fab-mega-0`, 6 `fab-ettw-`, 10 `traycer_mirror`, 2 `traycer-command-wiring`. After T06–T12 the live references left are in three docs this ticket owns: `agents-fabrik.md` (9 hits — § Front door / MANDATORY ORCHESTRATOR PRE-FLIGHT `:344` names the chains; rewrite to `/fabrik-vision` → `/fabrik-epics` → `/fabrik-epics-review` → per-window `/fabrik-spec <epic>`), `docs/orchestrator/00-autonomous-factory-north-star.md` (9 hits — the north-star's chain references become the assembled commands; its history paragraphs stay, marked as history), `docs/reference/command-corpus-check.md` (`:55,67,80` — the wrapper-audit paragraphs are removed; the three sources are audited like any source). Also `agents-fabrik-core.md` § Front door line (it names the two trigger docs) — verify with the grep; it is a sync trigger, so the edit must hold for every project (it does: the paths are gone box-wide). The gate line's `git grep` is the denominator: 0 files outside the excluded set. DO-NOT: touch `CLAUDE.md`/template/packs (T14a) or `src/fabrik/cli.py` (T14c).

Depends: T09
Parallel: ⛓️
Complexity: complex
Gate: git grep -l 'epic-to-ticket-workflow\|_traycer-skills\|fab-mega-0\|fab-ettw-\|traycer_mirror\|traycer-command-wiring' -- ':!docs/orchestrator/_retired/' ':!docs/DECISIONS.md' ':!CHANGELOG.md' ':!docs/LESSONS_LEARNT.md' ':!docs/development/reviews/' ':!docs/superpowers/' ':!docs/archive/' ':!docs/development/plans/' ':!.fabrik/' | wc -l | grep -x 0
Gate: python3 scripts/enforcement/check_doc_links.py
Docs: agents-fabrik.md (the canonical map — front door names /fabrik-vision) · docs/reference/command-corpus-check.md · CHANGELOG.md — orchestrator-applied

## Touches
- agents-fabrik.md — PRIMARY PATH
- agents-fabrik-core.md
- docs/orchestrator/00-autonomous-factory-north-star.md
- docs/reference/command-corpus-check.md

## Behavior Contract
- **Given** the four docs, **When** the gate's `git grep` runs with the stated exclusions, **Then** it lists 0 files (agents-fabrik.md:344)
- **Given** `agents-fabrik-core.md` § Front door, **When** read, **Then** the epic tier names `/fabrik-vision` and the multi-epic tier `/fabrik-vision` → `/fabrik-epics` → `/fabrik-epics-review`, with no `docs/orchestrator/...00-trigger` path (agents-fabrik-core.md:1)
- **Given** `docs/reference/command-corpus-check.md`, **When** grepped for `_traycer-skills`, **Then** the count is 0 and the audit denominator paragraph counts sources only (docs/reference/command-corpus-check.md:55)
- **Given** the tree, **When** `check_doc_links.py` runs, **Then** it reports no broken link into `docs/orchestrator/` (docs/orchestrator/00-autonomous-factory-north-star.md:1)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- docs/development/reviews/2026-09-03-orchestrator-chains-corpus-review.md
