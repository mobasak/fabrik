# T04a — epic-file intake for /fabrik-spec

## Scope
`commands/_sources/fabrik-spec.md` gains ONE intake path (spec § Chain consolidation (d)): `/fabrik-spec docs/development/epics/<n>-<slug>.md` seeds the Intake Inventory from the epic's `### Scope` (In/Out), `### Success Criteria` and the 15-field `### Metadata` — every field becomes a row, and the four that were INFRA-CHECK-only in the retired ettw 00 (`target_vps`, `Registrars`, the Watchdog accept/raise/opt-out, the LLM gateway) become NAMED rows so nothing drops silently; it inherits the Vision's `## fabrik-lib Verdict` and `## Rejected Alternatives` verbatim (never re-runs the ladder), treats the epic's `Out of Scope` as OUT rows, and carries the Vision's rivals-dossier reference through. Phase 6's auto-invoke of `/fabrik-spec-review` (`commands/_sources/fabrik-spec.md:311`) is untouched. SPLIT NOTE: this was half of T04 until the emit gate measured its read set at 293,629 bytes against `READ_BUDGET_BYTES` 262144; T04b carries the plan/execute half. DO-NOT: touch `fabrik-plan-after-chat.md` or `fabrik-execute-plan.md` (T04b); write the three new sources (T06a–c).

Depends: —
Parallel: ⚡
Complexity: native
Gate: python3 commands/assemble_commands.py --check
Gate: python3 scripts/enforcement/check_command_corpus.py
Docs: CHANGELOG.md — orchestrator-applied; the rendered command is the merge-time render step

## Touches
- commands/_sources/fabrik-spec.md — PRIMARY PATH

## Behavior Contract
- **Given** `/fabrik-spec docs/development/epics/3-billing.md`, **When** Phase 0 runs, **Then** the Intake Inventory carries one row per Scope / Success Criteria / Metadata item, including named rows for `target_vps`, `Registrars`, Watchdog and the LLM gateway (commands/_sources/fabrik-spec.md:10)
- **Given** the same invocation, **When** the fabrik-lib ladder would run, **Then** it is skipped and the Vision's `## fabrik-lib Verdict` + `## Rejected Alternatives` are inherited verbatim (commands/_sources/fabrik-spec.md:21)
- **Given** an epic whose `Out of Scope` names an item, **When** the inventory is emitted, **Then** that item appears as an OUT-OF-SCOPE row with the epic as its source (commands/_sources/fabrik-spec.md:10)
- **Given** a chat brief with no epic file, **When** the command runs, **Then** its behaviour is unchanged from today (commands/_sources/fabrik-spec.md:311)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md
