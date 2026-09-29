# T06b — The landing docs and the hub's worktree include set

## Scope
Implements spec § Documentation landing sites and D2 (the hub's `.worktreeinclude`). `docs/reference/multi-agent-operating-model.md` § Hub vs project (`docs/reference/multi-agent-operating-model.md:201`) is rewritten: the hub runs the model — infra agent-1, fleet and intel in `.claude/worktrees/<name>`, intel the distributor, the main-checkout-only acts (render, distribution), the write-root rule; § Launch recipe gains the mid-session move with `EnterWorktree`; § Ownership surfaces names `--reserve-id` and the ledger rule (each agent writes its rows, agent-1 resolves at merge, D-448). `docs/workstation/hooks-index.md` gains the post-merge hook, the Stop hook's worktree push rule, the SessionStart move/adopt/bindings lines and the commit-msg advisory. `docs/workstation/agent-identity.md` names the live-binding line. A new root `.worktreeinclude` lists `.env` (the hub's `.venv` is already a symlinked directory, `.claude/settings.json`). DO-NOT: restate the spec; cite it.

Depends: T01, T02a, T02b, T03a, T03b, T04a, T04b, T05
Parallel: ⚡
Complexity: simple
Gate: python scripts/enforcement/check_doc_links.py
Docs: docs/reference/multi-agent-operating-model.md · docs/workstation/hooks-index.md · docs/workstation/agent-identity.md

## Touches
- docs/reference/multi-agent-operating-model.md — PRIMARY PATH
- docs/workstation/hooks-index.md
- docs/workstation/agent-identity.md
- .worktreeinclude

## Behavior Contract
- **Given** the model doc, **When** § Hub vs project is read, **Then** it states the hub runs the model with infra as agent-1 and no longer says the hub is deferred (spec § The delta D2)
- **Given** a fresh hub worktree created by `claude --worktree`, **When** its root is listed, **Then** `.env` is present (spec § The delta D2)

## Context Files
- .windsurf/rules/core/40-documentation.md
- docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
- docs/reference/multi-agent-operating-model.md
- docs/workstation/hooks-index.md
- docs/workstation/agent-identity.md
