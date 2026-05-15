# Preplans — Stage 1 of the Fabrik Lifecycle

This folder holds **preplan documents**: the captured intent for a new project, written before `fabrik scaffold` runs.

## Filename convention

```text
<YYYY-MM-DD>-<slug>.md
```

- `<YYYY-MM-DD>` — UTC date the preplan was authored
- `<slug>` — kebab-case project identifier (matches the eventual `fabrik scaffold <slug>` argument)

Example: `2026-05-15-citation-verifier.md`

## Lifecycle

1. **Author** — `fabrik preplan new <slug>` creates `docs/preplans/<YYYY-MM-DD>-<slug>.md` from the template at `templates/preplan/preplan.md.j2`. Fill in the 9 sections (Idea / Project type / Shape preview / External deps / Domain / Success criteria / Out of scope / Open questions / Notes).
2. **Refine** — iterate on the preplan with Opus / ChatGPT / Claude. The point is to **harden the intent** before any code lands.
3. **Hand off** — `fabrik scaffold <name> --from-preplan docs/preplans/<file>` ingests the preplan. The scaffold pre-fills:
   - `project.yaml.type` from the preplan's `## 2. Project type` section
   - `specs/services/<name>.yaml` shape block from `## 3. Shape preview`
   - service domain from `## 5. Domain`
   - secrets list from `## 4. External deps`
   - copies the preplan into `<project>/docs/preplan.md` and adds a `Preplan:` reference line into all 4 AI guardrail files (`AGENTS.md` for Traycer, `CLAUDE.md` for Claude Code, `AGENTS-compact.md` for Kilo, `.windsurfrules` for Windsurf) so every agent that picks up the project knows the original intent.
4. **Archive** — once the project is shipped, the preplan stays in `docs/preplans/` as historical record. Append a `## Status` block at the bottom marking the delivery date and the spec file that resulted.

## Why preplan first?

The Fabrik lifecycle is:

```text
Intent (preplan)
    ↓
Scaffolding (fabrik scaffold — context injection)
    ↓
Agentic Implementation (Traycer plan → Claude Code / Kilo / Windsurf code)
    ↓
Proper Registration (fabrik apply → 9 registrars + Coolify)
    ↓
Verification (fabrik verify + audit-registrars)
```

Skipping Stage 1 (intent capture) means every downstream agent has to **re-derive** intent from incomplete context — leading to "what was the project supposed to do again?" drift and the hallucinations the VPS1-inventory-aware guardrails are designed to prevent. The preplan is the single source of truth that the scaffold consumes once and the AI guardrails reference forever.

## See also

- `templates/preplan/preplan.md.j2` — the canonical 9-section template
- `src/fabrik/preplan.py` — parser + creator helpers
- `docs/traycer/fabrik-workflow.md` Step 2.5 — Traycer's preplan-ingestion logic
- `AGENTS.md` § Scaffold Types — the canonical project-type catalog the preplan's `## 2.` references
