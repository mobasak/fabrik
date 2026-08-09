# Hooks Index — every hook on this box, in one place

Freshness is GATE-ENFORCED in the ADD direction: `scripts/enforcement/check_hooks_index.py`
(hub-side, Tier 2) fails the gate when a hook script OR event registration exists in the live configs
but is missing from this page. Removals are NOT mechanically caught — retiring a hook obliges you to
delete its row here (honest limit, not a promise).

## 1. Claude Code — fleet-synced project hooks

Distributed to every `/opt` project + the hub via `AGENT_HOOK_FILES` (`scripts/fabrik_synced_manifest.py`);
wired in the synced `.claude/settings.json`.

| Event | Hook | What it does |
|---|---|---|
| SessionStart | `final_gate_stop.py --baseline` | Snapshots the failing gate-check set at session open (runs the LEAN gate `--lean --check` — the same Tier-1 check set the Stop verdict uses, so attribution compares like with like) |
| SessionStart | `session_orient.py` | The binding ORIENT block: governing CLAUDE.md (hub-contract vs synced-template text branches on content-based repo identity), MEMORY.md state (bounded 256KB read), session-recall tools + mandatory-use cases, the enforcement mesh. Fail-open |
| UserPromptSubmit | `skill_router.py` | Bare-prose EN/TR routing to the owning `/fabrik-*` skill ("invoke it, or say in one line why not"); regex tier always, Haiku tier opt-in (`FABRIK_ROUTER_HAIKU=1`); never blocks or rewrites |
| Stop | `final_gate_stop.py` | Definition-of-done enforcer, four blocking causes: gate red on session-authored files (path-token attribution) · session's own work uncommitted · committed-but-UNPUSHED (branch ahead of upstream; the task-end push law — indeterminate/no-upstream never blocks) · checkpoint-stall (promises, plan-answered permission questions, passive obligations). Quote-span/negation/deadline exemptions; `BLOCKED:` exempts globally, human-gate wording line-scoped; 3-attempt warn-through per cause |

## 2. Claude Code — user-level hooks (box-wide)

`~/.claude/settings.json` — apply to every session in every project; not in any repo (DR-protected by
`dr_claude_backup.sh`).

| Event | Hook | What it does |
|---|---|---|
| SessionStart | `session-start-tap.js` | claude-manager session tap (account/quota rotation layer) |
| SessionStart | `session_context.py` (/opt/session-recall) | Injects recent-context: last sessions for this project, closing context, recently-active sibling projects |
| Stop | `claude-sound.sh done` | Task-finished sound (state-based park decider — rings only at true final rest) |
| Notification | `claude-sound.sh attention` | Attention/input-needed sound (matcher `permission_prompt`) |
| PreToolUse | `claude-sound.sh attention` | Question-popup ring (matcher `AskUserQuestion` — that popup emits no other hook event) |
| PreCompact | `claude-sound.sh compact-start` | Writes the `compacting` marker so the decider reads compaction as busy (transcript shows nothing mid-compact) |
| PostCompact | `claude-sound.sh compact-end` | Clears the `compacting` marker |
| StopFailure | `claude-sound.sh failure` | Failure pipeline + the **resume mesh**: writes the `errparked` death record, can trigger account rotation for auth/rate classes (OPT-IN `CLAUDE_SOUND_AUTOROTATE=1`, default OFF — blind rotation churned accounts while two were weekly-walled; stays off until the health-aware design ships; 10-min limiter when on), spawns the opt-in headless reviver (`claude-autoresume.sh`, `CLAUDE_SOUND_AUTORESUME=1`), and on a truly-dead `/opt` ring escalates to Telegram (`mesh-notify`, 30-min suppress). Pane runs arm `claude-selfwatch.sh` via a persistent Monitor — **long autonomous runs arm the self-watch** (run discipline). Fixture harness: `claude-mesh-test.sh`. The decider also bridges WAKER LOSS (operator-observed: "Connection closed mid-response" stranding a pending task/subagent → permanent busy-silence): every busy-waker verdict arms a detached zero-API sleeper that re-evaluates after the staleness bound — a lost waker then rings "(waker lost)", writes a `waker_lost` death record (armed self-watches wake the pane), and Telegrams for `/opt` sessions |

## 3. Cascade hooks — DORMANT

`.windsurf/hooks.json` (fleet-synced): `post_write_code` → `validate_conventions` + `check_secrets`;
`post_cascade_response` → `final_gate --lean --check`. **No live runtime consumes this file** — Windsurf
Cascade is retired; the file stays synced as a template for a future non-Claude tool. Do not count it as
active enforcement.

## 4. Git pre-commit hooks

`.pre-commit-config.yaml` (hub; projects carry their own stack-specific configs — not synced).

| Hook | What it does |
|---|---|
| pre-commit-hooks (large files · merge conflicts · private keys · forbidden `.env`/keys/certs) | Standard commit safety |
| `command-corpus-check` | Installed `~/.claude/commands` + skills must match the rendered `_sources/` (hand-edits die on re-render) |
| `governance-sync` | A commit touching a trigger surface auto-distributes governance to all `/opt` projects (trigger set = its `files:` filter — the filter is the truth, not memory) |

## Deeper documentation

- Behavioral view (what agents experience): `agent-command-routing-and-gates.md` §1, §5
- Config-surface view: `claude-configuration-inventory.md` §5
- Distribution mechanics: `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md`
- Fullest single reference per hook: the hook file's own module docstring
- Sound hooks: `~/.claude/bin/claude-sound.sh` + its review receipt in `docs/development/reviews/`
