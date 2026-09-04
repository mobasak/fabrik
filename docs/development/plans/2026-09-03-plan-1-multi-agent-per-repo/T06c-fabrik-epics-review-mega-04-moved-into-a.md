# T06c — /fabrik-epics-review — mega 04 moved into a corpus source; Step 1.5 runs --check → --assign → --check

## Scope
Create `commands/_sources/fabrik-epics-review.md` from `04-cross-epic-validation-fabrik.md` (285 lines) — already the review twin. Insert Step 1.5, after the integrity gate and before any lens: `python3 scripts/epic_order.py --check` → `--assign <alpha,beta,gamma>` (the names the operator gives the run; T03's CLI) → `--check --owners <the same names>` — so the owner row can never fail on a first pass (audit R9: the r7 placement AFTER 04 was circular). The mermaid phase graph (`04:141`) and the shared-`owned_paths` re-cut (`04:89`) stay. ⚠️ **The report's filename and H1 are a CONTRACT, not a style choice, and must be carried over verbatim:** `docs/development/reviews/YYYY-MM-DD-mega-<vision-slug>-validation-review.md` (`04:204`) and the H1 `# Cross-Epic Validation Report` (`04:225`). `scripts/enforcement/check_review_coverage.py` routes a cross-epic report by exactly those two — `MEGA_REPORT_H1` (`:604`) and the reserved filename regex (`:606`), via `_is_mega_report` (`:610`). Rename either and the report silently falls through to the ordinary review grammar, the fail-open that file documents at `:599-602`. T14e depends on this pin. The command's close names the next step for EVERY window — `/fabrik-spec docs/development/epics/<its epic>.md` per agent, with the launch form `CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>` for agents 2..N and the main checkout for agent-1 — and records the owner set order (agent-1 = first name). DO-NOT: touch `epic_order.py`; delete `04-cross-epic-validation-fabrik.md` (T12b).

⚠️ **The renderer auto-appends only ONE fragment.** `commands/assemble_commands.py:774` appends `close-feedback` and nothing else; every other fragment is substituted from an explicit `{{include:<name>}}` line (`:760`), which is why 30 of the 33 existing sources carry `{{include:run-record}}` themselves (e.g. `commands/_sources/fabrik-spec.md:8`). So this source MUST carry, verbatim on their own lines: `{{include:run-record}}`, `{{include:questionbar}}`, `{{include:grounding-rules}}` and `{{include:subagents-core}}`. Omit them and the command renders with no run record — no pinned `RUN:` line, and `check_command_corpus` (BLOCKING) flags the missing close sites. NEXT is not a fragment at all: `_emit_skill` (`:288`) injects it into the SKILL description from the assembler's NEXT map, which is T07a's edit.

Depends: T03
Parallel: ⛓️
Complexity: native
Gate: python3 commands/assemble_commands.py --check
Gate: python3 scripts/enforcement/check_traycer_chain.py
Docs: CHANGELOG.md · INDEX.md (new source) — orchestrator-applied

## Touches
- commands/_sources/fabrik-epics-review.md — PRIMARY PATH

## Behavior Contract
- **Given** epics with integrity PASS and no owners, **When** Step 1.5 runs with `--assign alpha,beta,gamma`, **Then** every epic carries one owner from the set and the follow-up `--check --owners alpha,beta,gamma` passes before any lens runs (scripts/epic_order.py:127)
- **Given** integrity FAIL, **When** Step 1.5 runs, **Then** `--assign` is never invoked and the command stops on the integrity findings (scripts/epic_order.py:83)
- **Given** the review converges, **When** the close prints NEXT, **Then** it names `/fabrik-spec <epic file>` per window with the exact launch form per agent (docs/orchestrator/mega-epic-breakdown/04-cross-epic-validation-fabrik.md:141)
- **Given** `/fabrik-epics-review` writes its report, **When** the path and first heading are read, **Then** they match `…-mega-<slug>-validation-review.md` and `# Cross-Epic Validation Report` exactly, so `_is_mega_report` still routes it (scripts/enforcement/check_review_coverage.py:610)
- **Given** the source, **When** `check_traycer_chain.py` scans it, **Then** it reports 0 findings (scripts/enforcement/check_traycer_chain.py:89)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- docs/orchestrator/mega-epic-breakdown/04-cross-epic-validation-fabrik.md
- scripts/epic_order.py
- docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md
