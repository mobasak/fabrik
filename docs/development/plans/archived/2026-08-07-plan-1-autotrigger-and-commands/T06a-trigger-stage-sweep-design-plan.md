# T06a — TRIGGER + Stage sweep: design/contract/plan skills (7)

Depends: —
Parallel: ⚡
Complexity: native
Docs: CHANGELOG entry via Deltas (shared with T06b — orchestrator dedupes)
Gate: python commands/assemble_commands.py --check

## Scope

Rewrite the frontmatter `description:` of the SEVEN design/contract/plan-stage command sources to
carry: (1) a **TRIGGER clause** — concrete bare-prose phrasings, EN + TR, that should fire the
skill without the slash command (the proven style: an explicit `TRIGGER —` sentence listing real
user phrasings, e.g. spec: "I have an idea for…", "yeni bir proje/özellik fikrim var"; plan:
"let's plan this", "planlayalım"), plus the negative boundary where confusable (spec-review vs
plan-review); (2) exactly one **`Stage:`** line from the frozen taxonomy — spec + spec-review =
`1-design`; data-contract + ui-design + ui-design-review = `2-contract`; plan-after-chat +
plan-review = `3-plan`. DO-NOT: change any command BODY (frontmatter description only); DO-NOT
touch T06b's files or the four new sources; keep each description within its current length band
(descriptions ship in every session — tighten while adding). Style exemplar: the `claude-api`
skill's TRIGGER clause (out-of-repo at ~/.claude/skills/claude-api — read at execution).

## Touches

- commands/_sources/fabrik-spec.md
- commands/_sources/fabrik-spec-review.md
- commands/_sources/fabrik-data-contract.md
- commands/_sources/fabrik-ui-design.md
- commands/_sources/fabrik-ui-design-review.md
- commands/_sources/fabrik-plan-after-chat.md
- commands/_sources/fabrik-plan-review.md

## Behavior Contract

- **Given** the 7 design/contract/plan skill descriptions, **When** T06a lands, **Then** each carries a TRIGGER clause with concrete bare-prose phrasings and exactly one Stage: value (commands/_sources/fabrik-spec.md:2).

## Context Files

- docs/reference/MD/ai-prompt-templates.md (Part C — distil, don't dump)
