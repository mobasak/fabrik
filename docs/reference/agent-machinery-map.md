# Agent machinery map — everything that acts on a repo's coding agent

**Purpose:** one page naming every mechanism on this box that touches a Claude session working in
a project repo, grouped by WHEN it acts. The operator asked for the inventory twice (2026-09-07);
each row names the surface, its touchpoint in a project and the doc that owns the detail.
Measured against a synced project (transdoc) on 2026-09-07: 13 CORE_SCRIPTS, 9 hook files, 29 core
rule packs, 70 enforcement checks, 35 rendered commands, 10 MCP servers.

## Loaded into the agent's context (what it believes)

| Mechanism | Touchpoint in a project | Detail |
|---|---|---|
| `CLAUDE.md` | the synced project contract (hub and fabrik-lib keep their own; the drift check keys on the UNIVERSAL anchors) | `templates/governance/CLAUDE.md`, hub `CLAUDE.md` § UNIVERSAL governance markers |
| `.windsurf/rules` packs | activated by file globs on edit; read wholesale at plan time via `select_rules.py` | `docs/reference/rules/` (pack index), `scripts/select_rules.py` |
| The command corpus | 35 `/fabrik-*` commands rendered box-wide into `~/.claude/commands`; `skill_router.py` steers prompts to them | `commands/_sources/`, `commands/assemble_commands.py`, `docs/reference/command-run-protocol.md` |
| MCP servers | the user-level set plus the per-repo `.mcp.json` — the tool universe | `docs/workstation/mcp-roster.md` |
| Auto-memory + session-recall | per-project memory files and the indexed chat history | `docs/workstation/hooks-index.md` (recall), the memory contract in the system prompt |
| The ledgers | DECISIONS, PLANS, STRATEGIC_BACKLOG, FEATURES, LESSONS_LEARNT — read first, written in the same change | CLAUDE.md § Doc Sync Matrix, `docs/reference/decision-ledger.md` |

## Fired on the agent's turns (what stops it)

| Mechanism | Touchpoint | Detail |
|---|---|---|
| Hooks (9 synced files) | SessionStart orients; UserPromptSubmit routes skills, surfaces mail and threads, watches MCPs; PreToolUse holds under a quota exhaustion; Stop is the definition of done | `docs/workstation/hooks-index.md` |
| The Stop hook's causes | gate red on your files · uncommitted · unpushed · promise/permission stall · a running run record · unreviewed code · an incomplete FINAL OUTPUT block | `.claude/hooks/final_gate_stop.py`, D-173 |
| `final_gate.py` + the enforcement checks | 70 checks in `scripts/enforcement/`, 66 wired into the gate; the Stop hook runs it | `docs/workflows/FINAL_GATE_WORKFLOW.md` |
| The run record | every `/fabrik-*` command opens one; rounds, classes, the structured close-out usage feedback | `docs/reference/command-run-protocol.md` |
| Git-level guards | pre-commit (corpus check, script headers), pre-push (duplicate check), the post-commit governance sync, `check_synced_unmodified.py` | `.pre-commit-config.yaml`, `scripts/governance_sync_postcommit.sh` |

## Present before the agent arrives (what it inherits)

| Mechanism | Touchpoint | Detail |
|---|---|---|
| Scaffolding | the repo's shape at birth: docs the gate expects, PLANS markers, `.worktreeinclude`, the spec, compose, type packs | `src/fabrik/scaffold.py`, `docs/reference/multi-agent-operating-model.md` |
| Governance sync | what makes the above identical across the 45 synced repos; fabrik-lib pulls by hand | `scripts/fabrik_synced_manifest.py`, `scripts/sync_enforcement_to_projects.py` |
| Plan-locks, cert-locks, the worktree model | scope ownership between concurrent agents; one merge owner per repo (D-154) | `docs/reference/multi-agent-operating-model.md` |
| Agent charters + `CLAUDE_AGENT` | the role's charter injected by `agent_role.py`; provenance trailers | `docs/reference/agents/` |

## Around the agent (what it spends, delegates and talks through)

| Mechanism | Touchpoint | Detail |
|---|---|---|
| The subagent pool + flywheel | which model a fan-out gets, what it records; pool coders OFF for code tickets (D-170) | `.windsurf/rules/core/62-using-subagents.md`, `libs/subagents/` |
| Account rotation + the quota hold | whether the agent runs at all; `quota_stop.py` is its only in-repo touch | `docs/workstation/claude-account-rotation.md` |
| fabrik-mail, thread anchors, native cross-session messaging | the three channels an agent must read and answer | `docs/reference/fabrik-mail.md`, `scripts/thread_anchor.py` |
| The resume mesh + the wip-net | self-watch, death/revival, the off-box copy of uncommitted work | `docs/workstation/hooks-index.md`, `scripts/wip_backup.sh` |
| Kaizen + the coroner | records every hook event, reaps abandoned records, digests that change the rules later | `scripts/sysadmin/kaizen_*.py` |
| Outer loops | the daily pipeline, CI + the CI fix dispatcher, the watchdog — they commit into repos without a human | `scripts/kilo-benchmarks/daily_refresh.sh`, `scripts/ci_fix_dispatcher.py`, `docs/reference/watchdog.md` |
| Skills and subagent types | the superpowers plugin; the four rendered agent definitions | `~/.claude/agents/`, `commands/assemble_commands.py` |

The levers with the most leverage, in order: `CLAUDE.md`, the hooks, the gate checks, the rule packs,
the commands. The least measured today are the outer loops, which can commit into a repo while an
agent is mid-flight without the agent's contract saying so.
