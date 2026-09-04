# T14a — Governance texts — the template's line (d), the hub's messaging clause, 40-documentation's ticket-format pointer

## Scope
Three synced/hub governance texts, one line each — lean and enforceful (spec § Constraints, I14). (1) `templates/governance/CLAUDE.md:45-48` § Orient session-start gains line **(d)** after (c): *if you are not agent-1, you are in a worktree — launch with `CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>`; never edit the main checkout; commit heredocs use a QUOTED delimiter (`<<'EOF'`); the dev database is shared — the single-migration-owner rule is the only guard.* One line, no new section (READ BEFORE YOU EDIT: the block exists, the line joins it). (2) Hub `CLAUDE.md:173` — the "the flag may not be rolled out … it is a rollout wait" clause is replaced by the availability rule the doc states (on at ≥2.1.224 on WSL 2; ≥2.1.248 on third-party providers or with flag-fetching off) — hub-local, not a sync trigger, and today's `ListAgents` on this box showed 16 peers (the channel is live). (3) `.windsurf/rules/core/40-documentation.md:149` points ticket format at the retired `epic-to-ticket-workflow/06-ticket-breakdown-fabrik.md § Step 8` → point it at `/fabrik-plan-after-chat`'s ticket grammar (`commands/_sources/fabrik-plan-after-chat.md` § Phase 2, the worked ticket skeleton). The rules pack is a governance-sync trigger; the edit is correct for all ~46 projects because the ettw path no longer exists anywhere. DO-NOT: add any section; edit `agents-fabrik.md` (T14b).

Depends: T09
Parallel: ⛓️
Complexity: native
Gate: python3 scripts/enforcement/check_governance_texts.py 2>/dev/null || python scripts/final_gate.py --check --json | grep -c '"status": "success"'
Gate: git grep -c 'epic-to-ticket-workflow' -- templates/governance/CLAUDE.md CLAUDE.md .windsurf/rules/core/40-documentation.md ; test $? = 1
Docs: templates/governance/CLAUDE.md distributes to 47 repos via the post-commit governance sync · CHANGELOG.md — orchestrator-applied

## Touches
- templates/governance/CLAUDE.md — PRIMARY PATH
- CLAUDE.md
- .windsurf/rules/core/40-documentation.md

## Behavior Contract
- **Given** the template, **When** its § Orient session-start block is read, **Then** it carries exactly one new line (d) naming the `--worktree` launch form, the never-edit-main rule, the quoted heredoc rule and the shared-DB caveat, and no other line changed (templates/governance/CLAUDE.md:45)
- **Given** the hub `CLAUDE.md`, **When** grepped for `rollout wait`, **Then** the count is 0 and the availability rule names 2.1.224 and 2.1.248 (CLAUDE.md:173)
- **Given** `40-documentation.md`, **When** grepped for `epic-to-ticket-workflow`, **Then** the count is 0 and the ticket-format pointer names `/fabrik-plan-after-chat` (.windsurf/rules/core/40-documentation.md:149)
- **Given** the governance-sync trigger filter, **When** the commit lands, **Then** the post-commit sync distributes the template and the pack (the filter matches `^templates/governance/` and `^\.windsurf/rules/`) (scripts/enforcement/check_sync_trigger_coverage.py:142)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- .windsurf/rules/core/40-documentation.md
