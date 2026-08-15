# Plan — login-once credentials, phase 1: disarm, scaffold, fleet telemetry, runbook

Status: IN-PROGRESS
Date: 2026-08-15 · Owner: infra · Spec: docs/superpowers/specs/2026-08-15-login-once-credentials-design.md (CONVERGED, operator-approved)

**What this plan delivers vs defers.** It builds everything that must exist BEFORE the
operator's staged login rollout (M3, multi-day, operator-executed — it cannot sit inside an
autonomous run): the M-pre disarm, the M1 scaffolder + carrier monitor + fleet gitignore, the
feature-detected fleet-mode `--status`/tick + keepalive, and the operator runbook. The **M4
retirement sweep** (switch/capture/touch code + stores, the sound-system mesh legs as a named
owned step, cost-model repoints, DR exclude-credentials change) is the NAMED SUCCESSOR PLAN,
authored after the rollout completes — retiring machinery while `~/.claude` is still every
window's live path would break the box.

## What we already agreed (from the spec + operator)

- Goal (operator, verbatim): "i want to login once and use it forever" — zero recurring logins.
- One OAuth chain per long-lived window via `CLAUDE_CONFIG_DIR` per-dir isolation; carrier =
  project `.claude/settings.local.json` with `CLAUDE_CONFIG_DIR` + `CLAUDE_QUOTA_HOME` (both
  live-probed 2026-08-15).
- Rotation demoted to telemetry + advisories; credentials never move again; no login
  automation; no direct HTTP refresh (Cloudflare-fenced).
- Hub: per-window env (no settings entry — settings would override it); fallback single shared
  hub dir.
- Rejected: per-account-only dirs, waiting on upstream (tracking closed, failure reproduces),
  script-side refresh daemon, login automation.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
| T01 | Disarm the old world (M-pre) | — | ⛓️ | ✅ | 095942b9 |
| T02a | Fleet-dir scaffolder + carrier monitor | T01 | ⛓️ | ✅ | 398e672d |
| T02b | Fleet gitignore for the carrier file | — | ⚡ | ✅ | 0f7b6401 |
| T03 | Fleet-mode status/tick + keepalive | T02a | ⛓️ | ✅ | ccfd5357 |
| T04 | Rotation doc rewrite + operator runbook | T03 | ⛓️ | ⬜ | |
| T05 | Integration: whole-plan gate + receipt | T04 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T02b
3. T02a
4. T03
5. T04
6. T05

## Interfaces

- **T01 → all**: `_rotate_active_account()` returns `None` + prints `PAUSED` while
  `_switch_paused()` is true — no signature change; every caller (`run_claude` retry,
  keepalive shim, bot/aro-wake vendored copies) inherits the gate. Seam test: T01's marker
  test in `tests/test_claude_rotate_v2.py`.
- **T02a → T03**: `_fleet_root()` — a call-time helper honoring `CLAUDE_FLEET_ROOT` (default
  `~/.claude-fleet`, the `_rotate_state_dir()` env pattern, tmp_path-testable); `assignments.json` schema
  `{<slug>: {"account": <email>, "created": <iso>, "identity": "pending-login"|<email>}}` —
  T02a always writes `"pending-login"`; **T03 flips it to the verified email** on the first
  successful per-dir profile read after the operator's login (the pin moment; never re-probed
  after). The carrier payload (two env vars). Seam test: T03's fleet-mode tests build dirs via
  T02a's `--new-dir` code path in `tests/test_claude_fleet.py` (consumer-owned).
- **T02b → (operator M3)**: the rendered synced-gitignore block ignores the carrier file
  before any project carries one; no code consumer — the governance-sync applies it.
- **T03 → T04**: final CLI surface (`--new-dir`, `--sync-mcp`, `--keepalive`, fleet `--status`
  output shape) that the runbook documents verbatim.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed
  surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass
  green.
- **Dispatch policy** — every work ticket except T04 is `Complexity: native` (T01/T02a/T03:
  auth-class credential surface; T02b: a governance-sync trigger with fleet blast radius; T05:
  the Integration receipt); native worktree coder, Opus for the risky logic. Pool-default still
  applies to the gradeable sub-work: per-behavior test authoring, the doc reconcile
  (`scripts/doc_reconcile.py` for T04), and every `/fabrik-review` finder breadth layer run via
  `fanout(...)` + `set_quality` back-fill — all-native finder rounds land zero flywheel rows
  and are the named defect.
- **Parallelism + merge** — the rotate-file tickets are SERIAL (T01→T02a→T03 share
  `scripts/sysadmin/claude_rotate.py`; the Depends chain is the barrier); **T02b fans out
  concurrently** (disjoint Touches: the manifest) and merges independently in Merge-Order
  position 2. Fan-out also lives INSIDE tickets: parallel pool finders per review round,
  parallel test authoring; results merge in the dispatching session before the ticket's gate.

## Behavior Contract

- **Given** the switch-paused marker exists, **When** `run_claude` hits a usage-limit or 401 rotation trigger, **Then** `_rotate_active_account` installs nothing and prints a PAUSED line (scripts/sysadmin/claude_rotate.py:403)
- **Given** the switch-paused marker is absent, **When** the same trigger fires, **Then** rotation behaves exactly as before (regression guard) (scripts/sysadmin/claude_rotate.py:649)
- **Given** the switch-paused marker exists, **When** the operator runs `--next`, **Then** it refuses with the PAUSED line and installs nothing (scripts/sysadmin/claude_rotate.py:766)
- **Given** the switch-paused marker exists, **When** a 401 leaves rotation withheld, **Then** the "all credentials are dead" Telegram does NOT fire (scripts/sysadmin/claude_rotate.py:670)
- **Given** `--new-dir seo sarp@ocoron.com` with a repo path, **When** it runs, **Then** the dir carries a seeded `.claude.json`, the five symlinks, an assignments row, the two-variable carrier file, and zero credential bytes (scripts/sysadmin/claude_rotate.py:1599)
- **Given** an existing fleet dir, **When** `--new-dir` targets the same slug, **Then** it refuses and exits non-zero (check-before-create; never overwrite)
- **Given** a mapped project whose carrier file is missing, **When** `--status` runs, **Then** the output WARNs naming that project (scripts/sysadmin/claude_rotate.py:985)
- **Given** the manifest's gitignore groups, **When** the synced block text renders, **Then** it contains `.claude/settings.local.json` (scripts/fabrik_synced_manifest.py:208)
- **Given** `--sync-mcp` after an MCP roster edit in `~/.claude.json`, **When** it runs, **Then** every fleet dir's `.claude.json` carries the new roster and its OAuth section is untouched
- **Given** a tmp fixture with a file symlink for `settings.json`, **When** a tmp+rename write-through is probed, **Then** the outcome (symlink survives vs forks) is asserted and on fork the seeded-copy fallback is applied (tests/test_claude_fleet.py:1)
- **Given** `~/.claude/.credentials.json` with an open-handle count above the threshold, **When** `--status` runs, **Then** an occupancy WARN names the shared file (scripts/sysadmin/claude_rotate.py:985)
- **Given** a fleet root with dirs on two accounts, **When** `--status` runs, **Then** rows group by account with live quota from the freshest token and never print "parked — quota unknown" (scripts/sysadmin/claude_rotate.py:985)
- **Given** an account none of whose dirs was used in the last 8h, **When** `--status` runs, **Then** its row shows the cached last-known values with their age, marked stale
- **Given** a fleet dir whose credentials mtime is 8 days old, **When** `--keepalive` runs, **Then** exactly one ping executes with that dir's own env and a failing ping produces a mesh-notify alert
- **Given** an empty fleet root, **When** `--status` runs, **Then** the legacy manager-accounts view renders unchanged (regression guard)
- **Given** a fleet dir whose assignments row is `pending-login` and whose own token answers the profile probe, **When** `--status` runs, **Then** the verified email is written back once and never re-probed (scripts/sysadmin/claude_rotate.py:985)
- **Given** fleet mode with an account at 96% utilization, **When** the tick runs, **Then** it emits the per-account advisory and installs nothing — the fleet branch contains no successor or switch call (scripts/sysadmin/claude_rotate.py:1381)
- **Given** the rewritten rotation doc, **When** its claims are checked against the shipped T01–T03 behavior, **Then** every named command, path, and env var exists as documented (docs/workstation/claude-account-rotation.md:1)
- **Given** all work tickets merged, **When** the full Tier-2 gate and convergence check run, **Then** both are green and the receipt embeds the verbatim success JSON (docs/development/reviews/2026-08-15-plan-1-login-once-credentials-review.md:1)

## Global Constraints

- Box-local workstation system: no scaffold type, no `specs/services` yaml, no shape flags, no
  compose/Traefik surface. The 12-Factor non-negotiables still bind the code written: logs =
  unbuffered stdout only, never a logfile (XI) · no daemonizing / PID files (VIII) · config via
  env vars, no secrets in code (III) · no grouped env sets (III) · shelled-out binaries must
  exist (`claude` CLI probed in-step) (II) · releases immutable — the twin is re-copied, never
  hot-patched (V) · same behavior dev/test via tmp_path-isolated tests (X) · migrations/jobs
  N/A (XII/IX) · sticky sessions/port binding N/A (VI/VII).
- Never-route (built-in set applies): `scripts/enforcement/` edits limited to none in this
  plan; `scripts/fabrik_synced_manifest.py` is a governance-sync trigger — fleet blast radius,
  correct-for-all-46 required (the gitignore line qualifies).
- No login automation; no direct HTTP token refresh; never log token bytes; `--new-dir` writes
  ZERO credential bytes; backup before mutating any credential-adjacent box file
  (`cp <f> backups/<f>.backup.$(date +%Y%m%d-%H%M%S)`).
- Twin invariant: `scripts/sysadmin/claude_rotate.py` and `scripts/aro-wake/claude_rotate.py`
  are byte-identical at every ticket's commit (md5 check is part of each gate).
- The `claude` CLI is the only token-refresh agent; keepalive runs in-place per-dir env, never
  a temp-dir copy.
- Operator hard rule: `~/.claude/bin/claude-sound.sh` is untouched by this plan.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | behavior-contract tests, red-first for risky paths | pack read 2026-08-15 |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | doc rewrite rules, Doc Sync Matrix | pack read 2026-08-15 |
| `.windsurf/rules/core/62-using-subagents.md` (ACTIVE) | pool-default dispatch + flywheel recording | pack read 2026-08-15 |
| `.windsurf/rules/core/35-security-auth.md` (ACTIVE) | secret handling, sensitive-file backup | pack read 2026-08-15 |
| fabrik-lib | spec verdict: extend `claude_rotate.py`; NO module fits (workstation-specific) | spec § fabrik-lib verdict table |
| `agents-fabrik.md` | no infra invariant touched (box-local; no compose/ports/DB) | read at spec stage 2026-08-15 |
| Spec (CONVERGED) | the whole design: mechanism, seeding contract, monitors, migration order | docs/superpowers/specs/2026-08-15-login-once-credentials-design.md |
| governance-sync filter | manifest edit distributes fleet-wide on commit | `.pre-commit-config.yaml` governance-sync files-filter |

## File Scope (owned paths)

- scripts/sysadmin/claude_rotate.py
- scripts/aro-wake/claude_rotate.py
- tests/test_claude_rotate_v2.py
- tests/test_claude_fleet.py
- scripts/fabrik_synced_manifest.py
- docs/workstation/claude-account-rotation.md
- docs/workstation/hooks-index.md
- docs/development/reviews/2026-08-15-plan-1-login-once-credentials-review.md

## Execution Evidence (run log — orchestrator-appended)

- 2026-08-15: operator ruling — "send a message to intel agent and proceed your work" →
  run started WITHOUT T02b dispatch; `scripts/fabrik_synced_manifest.py` is DEFERRED in the
  lock until intel's `2026-07-26-plan-1-ai-model-catalog-extraction` lock releases (mail
  01M02J7XM9XCWZ19Q5GE78SG3N, ack-required, asks intel for release/path-drop). T02b dispatches
  the moment the overlap clears; if the Board otherwise completes first, T02b ends 🔴 for a
  later resume — never a silent skip.
- Baseline: HEAD 6250ada3, lean gate success with ZERO reds (clean attribution reference).
- 2026-08-15 (later): intel RELEASED `scripts/fabrik_synced_manifest.py` from their lock (mail
  01M02K4G3S, verified in the lock file) — path reclaimed into this plan's lock, T02b ungated
  and dispatched; intel's remaining Phase E touches `CORE_SCRIPTS` ~:27-32, disjoint from
  T02b's tail edit (~:208-210).
- Isolation note: intel's active lock has no path overlap with this run's locked set; both
  runs follow the shared-master + disjoint-locks precedent (coder isolation is per-ticket
  worktrees, per D2).

## Evidence

- `scripts/sysadmin/claude_rotate.py:403` `_rotate_active_account` — the single rotation choke
  point behind the retry at `:649` and `_cmd_next` at `:766`; `_switch_paused` at `:1072`;
  `main()` CLI dispatch at `:1599`; `_collect_statuses` at `:985` (all re-read this session,
  post-edit).
- `scripts/fabrik_synced_manifest.py:147` `gitignore_dest_paths()` (synced-file name lists —
  NOT the carrier's home); the local-state tail `# Synced-files lock` / `.fabrik/synced.lock`
  at `:208-210` inside `gitignore_block_text()` (render `:186-212`) — the carrier line's
  correct precedent; `scripts/sync_enforcement_to_projects.py:37` "Single source of truth —
  shared with scaffold.py's .gitignore"; `:118` `patched_gitignore` (the fleet application
  path); `src/fabrik/scaffold.py:509-511` imports `gitignore_block_text` — and
  `templates/scaffold/gitignore-synced-block.txt` has ZERO references in src/scripts/templates/
  tests and is stale (adversary-verified): it is DEAD, not hand-maintained.
- `scripts/ci_fix_dispatcher.py:203` `cwd=repo_dir` (project-cwd inheritance for headless
  dispatch).
- `~/.claude/bin/claude-quota.py:37` honors `CLAUDE_QUOTA_HOME` (the second carrier variable).
- Live probes (this session, spec § External dependencies): carrier redirect proven for BOTH
  `settings.json` and `settings.local.json`; `.claude.json` relocation proven at
  `~/.claude-youtube-headless/.claude.json`.

```
$ python3 scripts/sysadmin/claude_rotate.py --pause-switch && python3 scripts/sysadmin/claude_rotate.py --tick
auto-switch PAUSED — ticks keep telemetry + drain warnings; no account is installed until --resume-switch
tick: auto-switch PAUSED (operator marker) — <successor> not installed
```

(The invariant is the two PAUSED lines; the tick also prints a live-account status line whose
account/percent vary by the hour — not part of the probe's expected output. Re-run
2026-08-15 15:5x: both invariant lines matched verbatim.)

Session record (probe run 2026-08-15, fixture project since cleaned — re-runnable by recreating
a fixture dir with a two-line `.claude/settings.local.json` env map):

```
cd <fixture with .claude/settings.local.json env CLAUDE_CONFIG_DIR=<empty dir>> && claude -p "reply pong"
Not logged in · Please run /login          # shared ~/.claude creds were VALID — redirect proven
```

## Self-audit

- (a) Coverage vs "What we already agreed": zero-recurring-logins → T01 (nothing swaps) + T02a
  (isolation machinery) + T02b (carrier never committed) + T03 (keepalive prevents idle lapse)
  + T04 (runbook makes the last login round executable); telemetry-always → T03;
  no-login-automation → constraint carried in T02a scope; hub per-window env → T04 runbook
  (M2 recipe; the probe itself is operator-executed). M4 retirement deliberately deferred to
  the successor plan — stated in the header, not a gap.
- (b) Cross-ticket signatures: `_fleet_root()` + the `assignments.json` schema produced by
  T02a, consumed by T03 (seam test consumer-owned in `tests/test_claude_fleet.py`; the
  identity-pin handoff is stated in Interfaces — T02a writes `pending-login`, T03 flips);
  T01's gate changes no signature; T04 documents T03's final CLI names after T03 merges.
- Grounding passes: all `path:line` cites re-read this session (see Evidence); the
  gitignore-block generation path is the one Phase-1 ambiguity, resolved in-ticket by grounding
  before editing (manifest is canonical per `sync_enforcement_to_projects.py:37`).
- Not yet a fixed point: `/fabrik-plan-review` owes the convergence round.

## Residual unknowns

- **Resolved:** carrier merge semantics (probed both files); `.claude.json` relocation
  (youtube dir); autorotate already disarmed (`CLAUDE_SOUND_AUTOROTATE=0` verified).
- **Open — operator-executed, runbook-carried (not execution blockers):** M2 hub per-window
  env practicality (first-window probe in the runbook); M3 grant-eviction watch (abort signal +
  regroup rule in the runbook); extension interactive-mode env application (first migrated
  window verifies before scaling).
- **Open — successor plan:** M4 retirement sweep (10-consumer inventory incl. sound system),
  M5 occupant thinning, VPS follow-up spec (hard deadline M4+30d), and the **worktree carrier
  copy** — no worktree-creating helper script exists in this repo to patch (adversary-verified:
  zero hits), so the build-time `cp` mitigation has no owner here; until the successor plan
  names the real carrier (the worktree-skill/EnterWorktree path), T02a's occupancy monitor is
  the detection net for worktree sessions rejoining `~/.claude`.
