# T05a — The project contract: finished work is a request

## Scope
Implements spec § The delta 3 and § Contract deltas (the template duty). `templates/governance/CLAUDE.md` § EXIT (`templates/governance/CLAUDE.md:229`) gains the finish duty — *in a linked worktree, when the branch's work is finished, run `python3 scripts/merge_request.py request` and send the `SendMessage` lines it prints* — and its ad-hoc "DEFAULT is merge to base locally" clause (`templates/governance/CLAUDE.md:242`) is scoped to the MAIN checkout, so a worktree agent never merges. Every UNIVERSAL marker anchor stays verbatim; the test pins the verb name.

Depends: T02
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_governance_template_split.py -q
Docs: templates/governance/CLAUDE.md

## Touches
- templates/governance/CLAUDE.md — PRIMARY PATH
- tests/test_governance_template_split.py

## Behavior Contract
- **Given** the rendered template, **When** § EXIT is read, **Then** it names `merge_request.py request` as the finish step for a linked worktree and scopes the merge-to-base default to the main checkout (spec § The delta 3)
- **Given** the template, **When** the UNIVERSAL marker anchors are grepped, **Then** every anchor is present verbatim (spec § Constraints)

## Context Files
- .windsurf/rules/core/40-documentation.md
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
- templates/governance/CLAUDE.md
