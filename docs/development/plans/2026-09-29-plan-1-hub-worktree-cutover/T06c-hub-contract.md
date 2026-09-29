# T06c — The hub contract: the mint line, and § Shared repo scoped to the main checkout

## Scope
Implements spec § The delta D7 (the hub's mint line names `--reserve-id`, `CLAUDE.md:140`) and D6 step 5 (the hub `CLAUDE.md` § Shared repo — the `- **Shared repo` list item, `CLAUDE.md:199-212` — states that it binds the main checkout's writers, agent-1 and the automated pipeline, and that fleet and intel work in their own worktrees; clauses that only a multi-writer checkout needs are cut with a loss-check per the lean-without-loss rule, D-331). The hub row of the cross-repo and every other rule stays. DO-NOT: edit the template (T06a) or any UNIVERSAL governance marker anchor (`CLAUDE.md` § UNIVERSAL governance markers — anchors stay verbatim).

Depends: T06a
Parallel: ⛓️
Complexity: native
Gate: python -m pytest tests/test_governance_template_split.py tests/test_work_contract_rule.py -q
Docs: none (CLAUDE.md is the contract)

## Touches
- CLAUDE.md — PRIMARY PATH

## Behavior Contract
- **Given** the hub `CLAUDE.md`, **When** grepped, **Then** its mint sentence names `decisions.py --reserve-id`, § Shared repo opens by naming the main checkout's writers, and every UNIVERSAL marker anchor is still present verbatim (spec § The delta D6)

## Context Files
- .windsurf/rules/core/40-documentation.md
- docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
- CLAUDE.md
