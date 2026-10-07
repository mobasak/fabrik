# T14a — Governance texts — the template's line (d), the hub's messaging clause, 40-documentation's ticket-format pointer

## Scope
THREE synced/hub governance edits, one line each. ⚠️ **Shares `CLAUDE.md` with T02b** (which carries the relaxed `Agent-Name` row into the HUB contract ONLY — `templates/governance/CLAUDE.md` has no `Agent-Name` row at all, verified 0 hits, which is why T02b's gate names one file) — the Depends edge above serialises the pair; rebase onto T02b's merge, then commit with an explicit pathspec naming only your own lines. **(4) VOID at spec r11** — this was the template's lock-path sentence (`templates/governance/CLAUDE.md:132`) naming `.fabrik/plan-locks/`; r11 withdrew the relocation (D-117), so the sentence is CORRECT as it stands and must not be touched. Back to three edits. DO-NOT: add any section; edit `agents-fabrik.md` (T14b).

Depends: T02a, T02b, T09
Parallel: ⛓️
Complexity: native
Gate: python scripts/final_gate.py --check --json
Gate: test -z "$(git grep -l 'epic-to-ticket-workflow' -- templates/governance/CLAUDE.md CLAUDE.md .windsurf/rules/core/40-documentation.md)"   # git grep -l prints nothing when no file matches; -c would print per-file zeros
Gate: bash -c 'grep -q "never edit the main checkout" templates/governance/CLAUDE.md && test "$(grep -c "rollout wait" CLAUDE.md)" = 0'   # BOTH edits, one gate line: without the second half a coder doing two of the three edits gets a fully green gate
Docs: templates/governance/CLAUDE.md distributes to 47 repos via the post-commit governance sync · CHANGELOG.md — orchestrator-applied

## Touches
- templates/governance/CLAUDE.md — PRIMARY PATH
- CLAUDE.md
- .windsurf/rules/core/40-documentation.md

## Behavior Contract
- **Given** the template, **When** its § Orient session-start block is read, **Then** it carries exactly one new line (d) naming the `--worktree` launch form, the never-edit-main rule, the quoted heredoc rule and the shared-DB caveat, and no other line changed (templates/governance/CLAUDE.md:45)
- **Given** the hub `CLAUDE.md`, **When** grepped for `rollout wait`, **Then** the count is 0 and the availability rule names 2.1.224 and 2.1.248 (CLAUDE.md:178)
- **Given** `40-documentation.md`, **When** grepped for `epic-to-ticket-workflow`, **Then** the count is 0 and the ticket-format pointer names `/fabrik-plan-after-chat` (.windsurf/rules/core/40-documentation.md:149)
- **Given** the governance-sync trigger filter, **When** the commit lands, **Then** the post-commit sync distributes the template and the pack (the filter matches `^templates/governance/` and `^\.windsurf/rules/`) (scripts/enforcement/check_sync_trigger_coverage.py:142)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- .windsurf/rules/core/40-documentation.md
