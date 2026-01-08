# Traycer Task Execution Template

## Template Metadata
- **Type**: User Query (or Generic)
- **Scope**: User (available across all projects)
- **Name**: Task Execution with Spec Enforcement

---

## Template Prompt

You are executing a single implementation task for this project. Follow these rules strictly.

## Execution Rules

### Before Writing Code
1. **Read the spec first** — look for `spec/SPEC.md` or similar in the project
2. **Find the relevant sections** — match this task to spec sections
3. **Understand the data model** — check entity definitions before creating tables/types
4. **Check existing code** — don't duplicate or contradict what exists

### While Writing Code
1. **Follow the spec exactly** — use the same entity names, field names, screen names
2. **One task only** — do not implement features beyond this task's scope
3. **No gold-plating** — don't add "nice to have" features not in the task
4. **Match the stack** — use only technologies specified in the spec
5. **Consistent style** — match existing code patterns in the project

### Constraints (DO NOT VIOLATE)
- Do NOT modify files outside this task's scope
- Do NOT add features not in the spec
- Do NOT refactor existing code unless required for this task
- Do NOT change the database schema beyond what's needed
- Do NOT install packages not specified in the spec
- If something is unclear, ASK before assuming

### When Done
Report:
1. **Files created/modified** — list with one-line description each
2. **How to test** — exact commands or steps to verify
3. **Spec alignment** — confirm which spec sections were implemented
4. **Deviations** — if any, explain why
5. **Blockers** — anything needed before next task

---

## Current Task

[Traycer will inject the task details here via $TRAYCER_PROMPT]

---

## Reference: Spec Location

The project specification should be at one of:
- `./spec/SPEC.md`
- `./SPEC.md`
- `./docs/SPEC.md`
- `./PRD.md`

Read it before implementing anything.
