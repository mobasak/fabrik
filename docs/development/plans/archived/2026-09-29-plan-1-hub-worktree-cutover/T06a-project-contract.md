# T06a — The project contract: the model unconditional, ids reserved

## Scope
Implements spec § The delta D1 (the template's § Orient (d) loses its condition) and D7 (the mint line names `--reserve-id`), and V7's template half. `templates/governance/CLAUDE.md:48` "(d) MORE THAN ONE AGENT in this repo?" becomes an unconditional rule: agent-1 alone in the main checkout, agents 2..N in worktrees, a running window moves with `EnterWorktree` (the conversation follows), the merge owner recorded once by `--adopt`; the hub-only model doc cited as `/opt/fabrik/docs/reference/multi-agent-operating-model.md`. The template's decision-ledger mint sentence and `commands/_sources/fabrik-epics-review.md:210` name `decisions.py --reserve-id` instead of `--next-id`. `tests/test_governance_template_split.py` pins the unconditional sentence and the `--reserve-id` mint in the template. DO-NOT: edit the hub `CLAUDE.md` (T06c) or render the corpus (the orchestrator renders from the main checkout at merge).

Depends: T04a, T04b, T05
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_governance_template_split.py -q
Docs: none (the template IS the contract)

## Touches
- templates/governance/CLAUDE.md — PRIMARY PATH
- commands/_sources/fabrik-epics-review.md
- tests/test_governance_template_split.py

## Behavior Contract
- **Given** the rendered project template, **When** § Orient (d) is read, **Then** it carries no "MORE THAN ONE AGENT" condition and names `EnterWorktree` for a running window (spec § Validation V7)
- **Given** the template and `commands/_sources/fabrik-epics-review.md`, **When** grepped for the mint command, **Then** each names `decisions.py --reserve-id` and neither tells an agent to mint with `--next-id` (spec § Validation V5)

## Context Files
- .windsurf/rules/core/40-documentation.md
- docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
- templates/governance/CLAUDE.md
- tests/test_governance_template_split.py
