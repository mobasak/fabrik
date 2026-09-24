# T02 — `status`, `sync --check`, gate readings and the derived drift classes

## Scope

Extends `scripts/work.py` with the `status` and `sync --check` rows of spec § The CLI and all of spec
§ Spec and plan state is derived, never copied: the plan-status normalisation, drift classes 1–8 each as
a named predicate listed by path, one `readings.jsonl` line per `sync --check` run, and the blocking
rule (classes 2–6 exit non-zero only once the repo's `config.json` carries `migrated_at` AND
`readings.jsonl` holds 7 consecutive calendar days of readings after it, each clean for classes 2–6;
the rule is re-derived from the readings on every run, so it needs no stored flag).

Readers to reuse by import rather than re-implement, all fleet-synced under `scripts/enforcement/`
(their signatures are quoted here, so the two large files need not be read):
- `_STATUS_LINE = re.compile(r"^\s*\**Status:\**\s*([A-Za-z][A-Za-z -]*)", re.M)`
  (`scripts/enforcement/check_convergence.py:792`) — the spine `Status:` value.
- `_board_states(spine_text: str) -> dict[str, str]` — Board-row ticket ID → its State cell,
  header-aware; `{}` when there is no `## Ticket Board` (`scripts/enforcement/check_plan_tickets.py:991`,
  its section regex `BOARD_SECTION_RE` at `:208`).
- `_designated_spec_citations(text: str) -> list[str]` — the spec paths a plan designates through its
  `Spec:` / `Design spec:` header (`scripts/enforcement/check_stage_artifacts.py:157`).
Import them by file path (`importlib.util.spec_from_file_location`) from the repo's own
`scripts/enforcement/`. If an import fails (a project whose enforcement copy is older), fall back to a
local regex copy of the one grammar that failed, and say so on stderr. Plan locks: `.fabrik/plan-locks/*.json` with
`plan` and `status` (`active` counts as a lock; `released`, `executed`, `complete` do not).

`status` also lists every item file under `.fabrik/work/` that `git status --porcelain` shows untracked
or modified, so an item a verb or the Stop harvest wrote is never left uncommitted unnoticed (T01b:
the writer commits it). This is a listing, not a drift class.

`sync --check` on a repo with no `.fabrik/work/` prints one line and exits 0. It never writes an
item. It exits 0 while not blocking, whatever it finds.

DO-NOT: `render`/`migrate-backlog` (T03); the gate row (T06).

Depends: T01b
Parallel: ⛓️
Complexity: complex
Gate: .venv/bin/python -m pytest tests/test_work_sync.py -q
Docs: none here — the reference doc is T09's

## Touches
- scripts/work.py — PRIMARY PATH
- tests/test_work_sync.py (new)

## Behavior Contract
- **Given** a fixture repo with one spec and one plan per drift class 1–8 plus one clean spec and plan, **When** `status` runs, **Then** each class lists exactly its fixture paths and the clean ones appear in none (spec § Spec and plan state is derived, never copied)
- **Given** plan spines with `Status: IN_PROGRESS`, `COMPLETE`, `PLANNED` and `WEIRD`, **When** `status` runs, **Then** the first three are read as `IN-PROGRESS`, `EXECUTED` and `DRAFT`, and only `WEIRD` is listed under class 8 (spec § Spec and plan state is derived, never copied)
- **Given** a `done` item from the last 14 days whose evidence SHA does not name it, a `legacy` one, and a closed marker older than 14 days whose item is still open, **When** `status` runs, **Then** the first and the marker are class 6 and the legacy item is not (spec § Spec and plan state is derived, never copied)
- **Given** an initialised repo with class-3 drift and no `migrated_at`, **When** `sync --check` runs, **Then** it exits 0, prints the drift, and appends one reading line holding the per-class counts (spec § Spec and plan state is derived, never copied)
- **Given** `migrated_at` and readings clean for classes 2–6 on 7 consecutive days after it, **When** `sync --check` runs on class-3 drift, **Then** it exits non-zero; with only 6 such days it exits 0 (spec § Lifecycle)
- **Given** a repo with no `.fabrik/work/`, **When** `sync --check` runs, **Then** it prints one line, exits 0 and creates nothing (spec § The CLI)
- **Given** one committed item and one untracked item file, **When** `status` runs, **Then** only the untracked one is listed as uncommitted (spec § Constraints — shared tree)

## Context Files
- docs/superpowers/specs/2026-09-24-work-tracking-design.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/enforcement/check_stage_artifacts.py — `_designated_spec_citations` (scripts/enforcement/check_stage_artifacts.py:157)
