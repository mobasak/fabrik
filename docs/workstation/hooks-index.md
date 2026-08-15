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
| SessionStart | `session_orient.py` | The binding ORIENT block: governing CLAUDE.md (hub-contract vs synced-template text branches on content-based repo identity), MEMORY.md state (bounded 256KB read), session-recall tools + mandatory-use cases, the enforcement mesh. Fail-open. Autonomous marker (2026-08-13): with `CLAUDE_MESH_AUTONOMOUS=1` it drops the sweep-eligibility marker into the PERSISTENT `~/.claude/state/autonomous/` (`MESH_STATE_DIR`) — never the /tmp lock dir, which dies with the VM (the Modern Standby cut) |
| SessionStart | `agent_role.py` | Injects the named agent's role charter (`CLAUDE_AGENT=infra\|fleet\|intel` → `docs/reference/agents/<name>.md`) — hub-agent-roles spec r2; fleet-safe silent no-op when the env is unset or no charter exists (every project) |
| UserPromptSubmit | `skill_router.py` | Bare-prose EN/TR routing to the owning `/fabrik-*` skill ("invoke it, or say in one line why not"); regex tier always, Haiku tier opt-in (`FABRIK_ROUTER_HAIKU=1`); never blocks or rewrites |
| SessionStart + UserPromptSubmit | `mail_notify.py` | Surfaces the repo's unread fabrik-mail (`/opt/fabrik-mail/<repo>/inbox`, override `FABRIK_MAIL_ROOT`) as a bounded, sanitized, untrusted-data-delimited summary (≤10 msgs, subject capped 120); repo identity from the git main checkout; whole body catch-all fail-open (a broken mailbox must never block a prompt) |
| Stop | `final_gate_stop.py` | Definition-of-done enforcer, four blocking causes: gate red on session-authored files (path-token attribution) · session's own work uncommitted · committed-but-UNPUSHED (branch ahead of upstream; the task-end push law — indeterminate/no-upstream never blocks) · checkpoint-stall (promises, plan-answered permission questions, passive obligations, assertive continuation claims — "Continuing autonomously." / terminal "Continuing." — and numbered `NEXT: round/pass N` footers naming undispatched own-loop work). Quote-span/negation/deadline exemptions; `BLOCKED:` exempts globally, human-gate wording line-scoped; 3-attempt warn-through per cause |

## 2. Claude Code — user-level hooks (box-wide)

`~/.claude/settings.json` — apply to every session in every project; not in any repo (DR-protected by
`dr_claude_backup.sh`).

| Event | Hook | What it does |
|---|---|---|
| SessionStart | `session-start-tap.js` | claude-manager session tap (account/quota rotation layer) |
| SessionStart | `session_context.py` (/opt/session-recall) | Injects recent-context: last sessions for this project, closing context, recently-active sibling projects |
| Stop | `claude-sound.sh done` | Task-finished sound (state-based park decider — rings only at true final rest). Mid-stream death family (2026-08-11, extended 2026-08-12): a tail whose last assistant record carries `isApiErrorMessage` + any of the CLI's five mid-stream death texts (`Response stalled mid-stream` · `Server error mid-response` · `Connection closed mid-response` · `Response stalled while thinking` · `Connection closed while thinking` — the whole family at one construction site in the 2.1.219 string table) is a DEATH, never busy-input — checked BEFORE the pending-waiter probes (they masked the real 25-min freeze); waiters get one 120s `busy-stalled-wait` recheck (a pending wakeup defers — it IS the revival), then `api_error_stalled` `.errparked` + error voice wake the armed self-watch. The loud variants also fire StopFailure (Layer 1 heal-at-death, below) — tail-detection doubles them harmlessly (dup-park guarded) and is the only net for the silent ones. Connection-failure class (2026-08-12): a no-role `type=system`/`subtype=api_error` record whose `error.connection.code` is present AND `retryAttempt == maxRetries` (the CLI's own retries exhausted — the STRUCTURAL key, covering ENOTIMP/ECONNRESET/ECONNREFUSED/ETIMEDOUT/ENOTFOUND, not a string allowlist) is the same `stalled-api-error` death routed into the same `.errparked` revival; a still-retrying `api_error` (attempt < max) is NOT a death; recovery-discrimination (real operator input after the record) suppresses it |
| Notification | `claude-sound.sh attention` | Attention/input-needed sound (matcher `permission_prompt`) |
| PreToolUse | `claude-sound.sh attention` | Question-popup ring (matcher `AskUserQuestion` — that popup emits no other hook event) |
| PreCompact | `claude-sound.sh compact-start` | Writes the `compacting` marker so the decider reads compaction as busy (transcript shows nothing mid-compact) |
| PostCompact | `claude-sound.sh compact-end` | Clears the `compacting` marker |
| SessionStart | `claude_rotate.py --drift-check` | Token re-capture: snapshots the LIVE credentials into the active account's store whenever they diverge, so a later rotation can never restore a superseded refresh token (the 2026-08-10 12:05 login failure). Read-only + silent when in sync; async, 10s |
| StopFailure | `claude-sound.sh failure` | Failure pipeline + the **resume mesh**: writes the `errparked` death record (skipped for sid-less payloads; the decider CLEARS it on a busy turn-death — a live waker makes the death non-terminal), triggers HEALTH-AWARE account rotation for auth/rate classes (**default ON since 2026-08-10** — a switch requires a VERIFIED unwalled sibling and targets it by name via `--switch`, so the blind churn of 2026-08-09 cannot recur; `CLAUDE_SOUND_AUTOROTATE=0` is the wait-only escape hatch; 10-min limiter), spawns the opt-in headless reviver (`claude-autoresume.sh`, `CLAUDE_SOUND_AUTORESUME=1`; its `claude -p` child carries `NO_REVIVE` + `CLAUDE_MESH_HEADLESS` so it never forks a second writer or arms a pane watch), and on a truly-dead `/opt` ring escalates to Telegram (`mesh-notify`, 30-min suppress, every outcome logged). Pane auto-continue: **EVERY interactive session arms `claude-selfwatch.sh` via the ORIENT-ordered persistent Monitor** (operator-mandated, commit 50675991; skipped for headless runs and compact-resume — the armed Monitor survives compaction). The self-watch consumes a pre-arm marker silently and consumes on fire — one wake per death record, network-gated for all classes. Quota-health (plan 2026-08-10-plan-1): a `rate_limit` death is parsed by `claude-quota.py` into a WALL (`rateLimitType` + `resetsAt`, from the manager tap's exhausted window or the payload's `error_details`); both revival layers then wait to that CLOCK in ≤60s slices instead of a blind 90s, and the operator gets a "revival scheduled in Nm" Telegram. Fixture harness: `claude-mesh-test.sh` (135 fixtures). The decider also bridges WAKER LOSS (operator-observed: "Connection closed mid-response" stranding a pending task/subagent → permanent busy-silence): every busy-waker verdict arms a detached zero-API sleeper that re-evaluates after the staleness bound — a **provably** lost waker (dispatched, never completed; persistent Monitors are standing watches, never wakers) rings "(waker lost)" in the error voice, writes a `waker_lost` death record (armed self-watches wake the pane), and Telegrams for `/opt` sessions with the true class |

## 2b. Cron @reboot — the resume sweep (not a hook; documented here as mesh Layer 4)

`claude-reboot-sweep.sh` (crontab `@reboot`, box-side, DR-versioned). Standby-survivable since
2026-08-13: reads persistent `.autonomous` markers (`~/.claude/state/autonomous/` first, legacy
/tmp lock dir second, gather-list union), self-flocks (lock fd closed in resume children),
claims each marker atomically via `mv` before spawning (a failed claim skips, never boot-loops),
widens eligibility to the `stalled-api-error*` death classes, and classifies `vm-cut`. Leg B —
ONLY on a fresh boot (lock dir absent; cron-restart re-fires skip it) — scans pre-boot
transcripts (≤20, 48h window, subagent sidecars excluded) for cut-mid-work sessions
(interactive panes included) and Telegrams one `claude --resume <sid>` per cut session via
`claude-sound.sh mesh-notify` (24h persistent per-sid suppress; sids Leg A just resumed are
excluded; panes are notified, never auto-resumed). A missing `claude` binary skips only the
marker leg — the notify leg still runs. Fixtures: mesh harness §RS (135 total).

### 2c. Cron */5 — the quota-rotation tick (mesh sibling of §2b)

`claude_rotate.py --tick` (crontab `*/5`, flock'd via `~/.claude/state/rotate.lock`; repo-side
script `scripts/sysadmin/claude_rotate.py` + aro-wake twin). Plan 2026-08-13-plan-2: polls the
LIVE account's `oauth/usage` both windows; at `ROTATE_THRESHOLD` (95) switches to the
PERISHABLE-FIRST successor (soonest weekly reset; picked under the shared switch flock —
TOCTOU-free vs manual `--switch`), Telegrams one line; with no eligible sibling at
`ROTATE_DRAIN_THRESHOLD` (85) broadcasts the graceful-drain fabrik-mail (commit-and-push
checkpoint + revival time; 24h stamp suppress) + one Telegram; keeps parked snapshots warm
(expiry-keyed refresh, identity-gated filing). `--status [--json]` = the operator's live quota
table. Ledger: `~/.claude/state/rotate-ledger.jsonl` (VM-cut-survivable).

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

## 5. Plain git hooks (NOT managed by pre-commit)

| Hook | What it does |
|---|---|
| `.git/hooks/commit-msg` → `scripts/check_commit_trailers.py` | Rejects a commit whose `Agent-Role:` trailer git cannot parse — a blank line inside the block, or prose glued to its top. Runs at commit-msg, the last moment the message is editable: once pushed, an unparseable block needs a force-push (HARD STOP). Delegates to `git interpret-trailers --parse`; passes through commits with no authored `Agent-Role:`, cherry-pick replays (⚠️ **only** `CHERRY_PICK_HEAD` — `MERGE_HEAD` was a real bypass: a conflict-resolution commit is newly AUTHORED), and any state where git is unavailable. **Install: `python3 scripts/check_commit_trailers.py --install`** (idempotent; refuses to clobber a foreign hook — add `--force` to reclaim it from pre-commit; resolves the shared hooks dir via `--git-common-dir` so it works from a worktree; re-run automatically by `wsl_startup_hook.sh` on every interactive shell, **cwd-pinned to $FABRIK_ROOT** — unpinned it installed nothing from `$HOME` and would have written into whatever other repo the shell was in). The shim FAILS OPEN — a missing/unreadable script, no runnable interpreter, or a guard that CRASHES all exit 0. Only the dedicated reject status (9) blocks, so a sibling's half-written edit to the guard cannot make every commit in the repo fail. ⚠️ Never run `pre-commit install --hook-type commit-msg`: it takes this hook over and restores the doubled stash cycle (pinned by a test). ⚠️ Deliberately NOT a pre-commit stage: pre-commit's commit-msg stage runs a SECOND `staged_files_only()` stash/restore per commit on a tree three agents share — where a pre-commit stash has already reverted uncommitted work once — and adds a second site for the "Your pre-commit configuration is unstaged" abort. Both were observed live. Exists because prose provably failed: after CLAUDE.md's malformed example was fixed fleet-wide, the next 50 commits still parsed 0/50. Tests: `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py`. |

## Deeper documentation

- Behavioral view (what agents experience): `agent-command-routing-and-gates.md` §1, §5
- Config-surface view: `claude-configuration-inventory.md` §5
- Distribution mechanics: `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md`
- Fullest single reference per hook: the hook file's own module docstring
- Sound hooks: `~/.claude/bin/claude-sound.sh` + its review receipt in `docs/development/reviews/`
