# Quota-health for the resume mesh — reset-clock revival, health-aware rotation, token re-capture, reboot sweep

Status: DRAFT
Date: 2026-08-10
Scope: workstation mesh layer (`~/.claude/bin` + `~/.claude/.claude-manager` + one fleet-synced hook touch) — same scope class as `2026-08-09-stopfailure-resume-mesh-design.md`. No `specs/services/*.yaml`, no scaffold type, no deploy: this is box opsware, DR-versioned not fleet-deployed.

## Goal

When a quota wall (5-hour window or weekly cap) kills sessions, the box must do what the operator
confirmed on 2026-08-09 (recorded in memory) instead of today's behavior (one blind 90s-cool-off
retry, then silence until a human types — live-demonstrated at the 2026-08-10 01:10 reset, when
nothing resumed):

1. **Know the wall**: parse the reset clock + wall type per account at death time.
2. **Switch when a sibling is healthy**: another account has quota → rotate to it now and revive.
3. **Schedule when alone**: the only live account is walled → revive AT the reset clock (+jitter),
   not on a fixed cool-off.
4. **Never churn logins**: after any manual interactive login, re-capture the fresh tokens into the
   rotation store so a later rotation can't restore a stale snapshot (the 2026-08-09 relogin churn).
5. **Survive reboots**: autonomous sessions self-mark; an @reboot sweep resumes the marked,
   mid-work ones headlessly, staggered. Interactive panes stay manual (two-writer ban).

Out of scope: fleet/VPS quota handling (workstation first; the fleet healer runs its own account),
any Anthropic-API-key path (operational stack is Claude Code CLI + subscription OAuth only —
recorded constraint), UI/dashboard surfaces.

## External dependencies — grounded THIS session (primary vendor artifacts + live probes, 2026-08-10)

| Fact | Grounding | Source |
|---|---|---|
| StopFailure hook payload carries `error`, **`error_details`** (the raw provider message, e.g. the 429 text), `last_assistant_message` | binary string extraction: `hook_event_name:"StopFailure",error:s,error_details:e.errorDetails,last_assistant_message:i`; 429 path sets `errorDetails: e.message` (`c=e.message.replace(/^429\s+/,"")`) | shipped CLI ELF `~/.local/share/claude/versions/2.1.219` (inspected 2026-08-10 ~06:00) |
| The API reports structured unified rate-limit state: **`resetsAt` epoch-seconds**, `rateLimitType`, `overageStatus`, grace/fallback flags via `anthropic-ratelimit-unified-*` headers | binary: `resetsAt=Math.round(Number(o));if(t)n.rateLimitType=t;if(r)n.overageStatus=r` + header-name strings (`…unified-grace-status`, `…unified-overage-disabled-reason`) | same binary inspection |
| Wall taxonomy: `rateLimitType ∈ {five_hour, seven_day, seven_day_opus, seven_day_sonnet, seven_day_overage_included}`; five_hour `windowSeconds:18000` | binary enum + threshold table | same binary inspection |
| The claude-manager statusline tap ALREADY maps per-window reset state to disk: `statusline.json → rateLimits.{fiveHour,sevenDay} = {usedPercent…, resetsAt}` (populated from the CLI's `resets_at`; `None` when no wall data) | `statusline-tap.js`: `fiveHour:w(p?.five_hour)…` with `resetsAt:l(n.resets_at)`; live file shows the `rateLimits` keys | `~/.claude/.claude-manager/statusline-tap.js` + `statusline.json` (read 2026-08-10) |
| Rotation CLI exists: `claude_rotate.py` `--list/--next/--switch`, 3 accounts in `manager-accounts/` | fleet-synced script + memory (can@ capture DONE 2026-07-10) | `/opt/fabrik/scripts/sysadmin/claude_rotate.py` (plan grounds internals at path:line) |
| Scheduling substrates on this box: `at` ABSENT; systemd `--user` bus **running** (live probe — supersedes the older "no user bus in WSL" memory note); cron live (68 lines incl. @reboot entries); the mesh's detached-sleeper pattern is production-proven (71-fixture harness) | `command -v at` → none; `systemctl --user is-system-running` → `running`; `crontab -l` | live probes 2026-08-10 ~06:00 |

Secondary (not fetched, deliberately): docs.anthropic.com's rate-limit-headers page — the shipped
binary outranks documentation for what THIS CLI actually emits; the binary was inspected directly.

## Chosen approach (A): teach the EXISTING mesh the reset clock

The 48-fix, 71-fixture-guarded mesh already owns death records, revival, wake, dedup, storm
serialization, and observability. Quota-health is a **data upgrade** to it, not a new system:

1. **`claude-quota.py`** (new, `~/.claude/bin`, stdlib-only like the decider): given the StopFailure
   payload + the active account, resolve `(rateLimitType, resetsAt)`:
   a) parse `error_details` (best-effort regex: epoch fields, "resets"/hour phrases);
   b) else read `statusline.json rateLimits.*.resetsAt` (structured, freshest wall the CLI saw);
   c) else UNKNOWN → callers keep today's transient-throttle behavior (90s), unchanged.
   Writes/updates **`~/.claude/.claude-manager/wall-state.json`**: per-account
   `{rateLimitType, resetsAt, recordedAt}`; entries self-expire when `resetsAt` passes.
   Also answers `--healthy-sibling` (any account with no live wall) from wall-state + snapshots.
2. **`claude-sound.sh` failure branch** (rate_limit only): call `claude-quota.py --record` (fast,
   detached-safe). With `CLAUDE_SOUND_AUTOROTATE=1` (flips **default ON** when this ships — the
   operator's stated condition): healthy sibling → `claude_rotate.py --next` (existing 10-min
   limiter kept) and revival proceeds immediately on the new account; no sibling → no rotation
   churn (the 2026-08-09 adjudication honored — wait beats switch).
3. **`claude-selfwatch.sh`** (panes): for `rate_limit` with a known `resetsAt`, the armed watch —
   already sitting in the pane at zero cost — sleeps until `resetsAt + jitter` instead of 90s
   (poll-sliced sleep so marker-heal/consume semantics keep working; quota waits are exempt from
   the 30-min offline ceiling, bounded instead by `resetsAt + slack`). Unknown reset → 90s as
   today. This IS "send resume when the clock is reached" for panes, with no second writer.
4. **`claude-autoresume.sh`** (headless): same reset-aware backoff for `rate_limit`; ceiling
   likewise `resetsAt + slack` for quota waits; attempts still capped.
5. **Token re-capture**: `claude_rotate.py --capture-current` (snapshot live `.credentials.json`
   into the active account's `manager-accounts/` entry) + an hourly cron drift-check that
   auto-captures when the live token differs from the stored snapshot (manual logins then can
   never be clobbered by a later rotation restoring a stale snapshot).
6. **Reboot sweep**: launchers of autonomous sessions export `CLAUDE_MESH_AUTONOMOUS=1`; the
   fleet-synced ORIENT hook (env-gated, harmless elsewhere) drops `<sid>.autonomous`
   (sid + cwd + transcript path) in the lock dir; `claude-reboot-sweep.sh` (@reboot cron, after
   the DR entry) walks fresh markers, keeps only sessions the decider reads as interrupted/busy,
   and resumes each with the existing storm serialization (`start.lock`); panes have no marker,
   so they are structurally excluded.
7. **Harness**: new fixtures per component (reset-parse fixtures from captured payload shapes;
   wait-until-reset with `MESH_*` overrides; healthy-sibling switch; capture-drift; sweep
   eligibility) — same sandbox pattern, red-first.

## Rejected alternatives

- **B — build scheduling into the claude-manager Node tap**: the tap is telemetry, not control;
  cross-language control flow, no fixture harness, higher maintenance. Rejected on criteria 2/4.
- **C — systemd `--user` transient timers per revival**: bus IS running (probe), but it adds a
  second scheduling substrate with unproven logout/lingering semantics on WSL, duplicating a
  detached-sleeper pattern that is already production-proven and fixture-covered. Rejected on
  criteria 4/5 (leanest = one substrate). Revisit only if sleepers ever prove insufficient.
- **D — probe-based reset discovery (fire a request against the walled account to read fresh
  headers)**: viable free fallback (walled requests fail without consuming quota) but adds an
  API-touching path for data that `error_details` + statusline already carry. Deferred; noted as
  the fallback if source (b) proves too stale in practice.

## fabrik-lib verdict table

| Capability | Verdict | Why |
|---|---|---|
| reset parse / wall-state / scheduling / sweep | **BUILD** (small, box-local) | no fabrik-lib module covers workstation hook opsware (README table checked: app-level modules only); NOT a fabrik-lib candidate — box-specific, fails generic + ≥2-project-types |
| account switching | **VENDOR as-is** | `claude_rotate.py` exists; `--capture-current` is a seam-level ENHANCE (upstream note: it lives in the hub already — no cross-repo issue) |
| usage/wall telemetry | **VENDOR as-is** | claude-manager statusline tap already persists `resetsAt` per window |
| revival/wake/dedup/storm | **VENDOR as-is** | the reviewed mesh |

## Shape/infra implications

None (no scaffold type, no `shape:` flags, no deploy). Distribution: `~/.claude/bin` +
`.claude-manager` via DR backup; the one repo-synced touch is the ORIENT hook's env-gated
autonomous-marker line (+ its tests). Crontab: +1 hourly drift-check, +1 @reboot sweep.

## Constraints digest (binding rows applied here)

| Rule | Source | Implication |
|---|---|---|
| Operational stack = Claude Code CLI + subscription OAuth; NEVER ANTHROPIC_API_KEY | memory `feedback_claude_code_not_api` | all revival = `claude -p --resume`; no API probes with keys |
| No per-call budget caps on operational loops | memory `feedback_no_budget_caps_sysadmin` | no $ gates in revival paths; caps are attempt-counts only |
| Single-operator threat model | memory `feedback_threat_model_single_operator` | wall-state/marker files are plain 600-mode JSON; no auth theater |
| Config via env; secrets never in code or echoed | `core/35-security-auth` (floor) + III | tokens only touched via file copies; no token ever printed/logged |
| Logs: stdout/bounded; the app never manages logfiles beyond the existing bounded sound-debug.log | `core/55-observability` / XI | new components log through the existing `log_line`/`log_verdict` surfaces |
| Fail-open hooks — never block a session | mesh contract (review receipt) | quota-state calls are best-effort, timeouts, `|| true` |
| DR backup after every `~/.claude` config change; commit+push law | memories | each build phase ends with `dr_claude_backup.sh` + repo push |
| Resilience: every waiter bounded, bounded failure returns to RINGING | mesh contract | quota waits bounded by `resetsAt + slack`; unknown reset keeps old bounds |

## Decisions pinned (operator-confirmed 2026-08-09 unless noted)

- Switch-if-sibling-healthy, schedule-at-reset otherwise, +jitter. AUTOROTATE default flips ON
  with this build (was opt-in-off pending exactly this design).
- Pane revival at reset = the armed self-watch's wake (never headless typing into a pane).
- Reboot sweep resumes ONLY `CLAUDE_MESH_AUTONOMOUS=1`-marked sessions (my default, recorded:
  launcher-env marking; say the word for a different eligibility rule).
- Weekly walls (`seven_day*`) schedule the same way — the watch/sleeper just waits longer (zero
  cost while sleeping); Telegram announces the scheduled revival time at death so the operator
  knows the plan (my default, recorded).

## Open/blocking unknowns

- **Exact `error_details` text shape for each wall type** — not blocking (source (b) is
  structured); resolution: the build adds a one-line payload capture (class+details only, no
  content) on quota deaths so the parser's regexes are tuned on real strings within a day of use.
- **statusline.json staleness when the CLI idles** — resolution: build-phase probe; wall-state
  entries carry `recordedAt` and expire at `resetsAt`; a stale-but-unexpired entry only ever
  delays revival to the recorded clock, never loses it (the ring remains the backstop).
- **`claude_rotate.py` internals for the `--capture-current` seam** — resolution: plan-time
  path:line grounding (standard `/fabrik-plan-after-chat` Phase 0.5).
