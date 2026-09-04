# T06c — /fabrik-epics-review — mega 04 moved into a corpus source; Step 1.5 runs --check → --assign → --check

## Scope
Create `commands/_sources/fabrik-epics-review.md` from `04-cross-epic-validation-fabrik.md` (285 lines) — already the review twin. Insert Step 1.5, after the integrity gate and before any lens: `python3 scripts/epic_order.py --check` → `--assign <alpha,beta,gamma>` (the names the operator gives the run; T03's CLI) → `--check --owners <the same names>` — so the owner row can never fail on a first pass (audit R9: the r7 placement AFTER 04 was circular). The mermaid phase graph (`04:141`) and the shared-`owned_paths` re-cut (`04:89`) stay. The command's close names the next step for EVERY window — `/fabrik-spec docs/development/epics/<its epic>.md` per agent, with the launch form `CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>` for agents 2..N and the main checkout for agent-1 — and records the owner set order (agent-1 = first name). DO-NOT: touch `epic_order.py`; delete `04-cross-epic-validation-fabrik.md` (T12b).

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
- **Given** the source, **When** `check_traycer_chain.py` scans it, **Then** it reports 0 findings (scripts/enforcement/check_traycer_chain.py:89)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- docs/orchestrator/mega-epic-breakdown/04-cross-epic-validation-fabrik.md
- scripts/epic_order.py
- docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md
