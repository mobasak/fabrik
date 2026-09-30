# T05b — The hub contract: the same finish duty

## Scope
Implements spec § The delta 3 for the hub. The hub `CLAUDE.md` § EXIT (`CLAUDE.md:250`) carries T05a's finish duty, and its ad-hoc merge default (`CLAUDE.md:263`) is scoped to the main checkout — the hub's worktree agents (fleet, intel) send requests to infra. Every UNIVERSAL marker anchor stays verbatim.

Depends: T05a
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_governance_template_split.py -q
Docs: CLAUDE.md

## Touches
- CLAUDE.md — PRIMARY PATH

## Behavior Contract
- **Given** the hub `CLAUDE.md`, **When** § EXIT is read, **Then** it names `merge_request.py request` for a linked worktree, scopes the merge-to-base default to the main checkout, and every UNIVERSAL anchor is still present verbatim (spec § The delta 3)

## Context Files
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
- CLAUDE.md
