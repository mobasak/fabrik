# T07 — Orient step-0 task→skill routing rule

Depends: —
Parallel: ⚡
Complexity: never-route
Docs: CHANGELOG entry via Deltas
Gate: python scripts/final_gate.py --lean --check --json

## Scope

Add the routing rule to `CLAUDE.md` § Orient as step 0 and mirror it compactly in
`AGENTS-compact.md`: before starting ANY task, classify it against the pipeline stages and invoke
the matching skill — *"a task that matches a stage and is executed without its skill is a defect,
the sibling of invoked-command-=-loaded-command"* — with the stage table inline (the frozen
taxonomy + one-line stage descriptions + the fork rules: data-shaped→2-contract, GUI→ui-design,
headless skips GUI stages). Include the escape: state in one line why no skill applies when
genuinely none does. DO-NOT: renumber existing Orient items' semantics beyond inserting step 0;
DO-NOT duplicate the full § Pipeline flow (point to it); keep the AGENTS-compact mirror ≤10 lines
(its token budget is load-bearing). AGENTS-compact is the retired-Kilo bootstrap file kept synced
until removed — the operator actively invests in it (last edited 2026-08-07) precisely because it
is the SOLE instruction channel for non-Claude agents; the mirror is deliberate, not an oversight.

## Touches

- CLAUDE.md
- AGENTS-compact.md

## Behavior Contract

- **Given** a fresh session reading CLAUDE.md, **When** Orient runs, **Then** step 0 routes the task to a matching skill BEFORE work starts, with the stage table inline (CLAUDE.md:9).

## Context Files

- CLAUDE.md (§ Orient heading :9, items :10-14 — insert step 0 after :9; § Pipeline; § Behavior "Invoked command = loaded command" — the sibling rule to echo)
- AGENTS-compact.md (:20-40 — the compact structure + token constraints)
- the spine's § Global Constraints (stage taxonomy)
