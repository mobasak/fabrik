# Design spec — login-once credential architecture (per-window `CLAUDE_CONFIG_DIR` isolation)

Status: DRAFT
Date: 2026-08-15 · Owner: infra

## Goal

**"I want to login once and use it forever."** (operator, 2026-08-15). Zero recurring logins for
the ~15 concurrent Claude Code windows (plus headless crons) on this box, across the 4 Claude Max
accounts — while keeping per-account quota visible at all times and never moving a credential
file under a running session again.

## The problem being designed away (all grounded live this session)

One shared `~/.claude/.credentials.json` serves every window. OAuth refresh tokens are
**single-use**; access tokens live ~8h; refresh-token chains live ~30 days idle and roll forever
on use. Sharing one chain among N long-lived processes therefore guarantees:

1. **The morning relogin wave** — any refresh by any process invalidates every other window's
   in-memory pair; idle windows wake, try their consumed token, and demand `/login`.
2. **Rotation kills sessions** — the daemon's file swap (02:45, 2026-08-15, sarp→can at 95%)
   put an account under windows that still held the old one in memory.
3. **Chain loss** — can@'s chain rolled all night ONLY in the live file (the drift-check's
   identity gate skipped through the whole live period), and the operator's 11:15 `/login`
   overwrote it: account unrecoverable without a manual login. The store/capture/touch machinery
   exists solely to fight this, and `--touch` is already dead on CLI ≥2.1.231 (writes a blanked
   pair; liveness gate refuses it).
4. **Parked-quota blindness** — a parked store's access token dies ~8h after capture, so
   `--status` cannot read a parked account's quota (operator complaint, 2026-08-15).

Upstream this is a confirmed open bug family — the CLI does read→refresh→write on the shared
file with no locking and no re-read-on-failure (anthropics/claude-code issues #24317, #25609,
#27933, #43392, #48786, #54443, #56339; surveyed 2026-08-15, none fixed as of 2.1.232).

**The load-bearing fact:** an account that is *used* never needs a login — the CLI rolls its
chain on every real turn. Every relogin traces to sharing, swapping, or stranding a chain, never
to OAuth itself. Existence proof on this box: `~/.claude-youtube-headless` — one login, weeks of
unattended multi-process (`claude -p`, concurrency 5) operation, zero relogins, because its
chain has no foreign owners.

## Chosen approach — one refresh chain per long-lived session, via per-project config dirs

### Mechanism (proven live, 2026-08-15, this session)

A project-level `.claude/settings.local.json`:

```json
{"env": {"CLAUDE_CONFIG_DIR": "/home/ozgur/.claude-fleet/<slug>"}}
```

**Empirically verified:** a `claude -p` run in a fixture project with exactly this file ignored
the healthy shared `~/.claude` credentials ("Not logged in") and scaffolded the target dir —
i.e. the project-settings `env` map redirects the config dir for every session started in that
project, extension and terminal alike, with **no PATH shim, no wrapper, no VS Code setting**,
and it survives CLI updates. (The extension honors `CLAUDE_CONFIG_DIR` — confirmed at
`acp-agent.js:14`, session 92c3df30, 2026-07-15. The verified probe used `settings.json`; the
migration's first step re-runs it for `settings.local.json`, expected identical merge
semantics.)

### Dir layout

```
~/.claude-fleet/
  assignments.json          # slug → account email (the routing table; advisor + status read it)
  seo/                      # one dir per project window …
  youtube/
  fabrik-infra/             # … hub gets per-ROLE dirs (3 concurrent windows, same cwd)
  fabrik-fleet/
  fabrik-intel/
  cron-ci-fix/              # headless callers that run outside mapped projects
  ...
```

- Kebab-case slugs; one dir = one OAuth chain = one login, ever.
- Hub exception: 3 windows share `/opt/fabrik` as cwd, so cwd-keyed settings cannot split them.
  Design: per-role dirs selected by the `CLAUDE_AGENT` env the operator already sets per hub
  window; **fallback** (if per-window env proves impractical): one shared `fabrik` dir — a
  3-process residual race, recoverable by window reload (never a login), ¼ of today's blast
  radius. Resolution: migration step M2 probes it.
- Headless crons in project cwds (`ci_fix_dispatcher` dispatches `claude -p` inside
  `/opt/<project>`) inherit that project's dir automatically — no per-cron work.

### What is per-dir vs shared (the seeding contract)

| State | Disposition | Why |
|---|---|---|
| `.credentials.json` | **per-dir** (the whole point) | one chain, one owner |
| `.claude.json` (MCP user scope, per-project trust, onboarding) | **seeded copy** from `~/.claude.json` at dir creation, then per-dir | login replaces its OAuth section; trust/MCP carried over so no re-onboarding |
| `settings.json`, `agents/`, `commands/`, `skills/` | **symlink** → canonical `~/.claude/…` | hooks/roster/governance stay single-source; one edit propagates |
| `projects/` (transcripts + memory) | **symlink** → `~/.claude/projects` | session-recall indexing and per-project memory must not fragment across 15 dirs |
| `sessions/`, caches, `statsig/` | per-dir private | ephemeral |

### Rotation demoted: credentials never move again

- **All 4 accounts stay permanently logged in** in their dirs. No swap, no capture, no parked
  stores, no `--touch`. Today's `--pause-switch` posture (f8eebd84) becomes permanent; the
  switch/install path and the store/capture/drift machinery retire with their tests (the
  drift-check blind spot that lost can@ is rendered moot, not patched).
- `claude_rotate.py --status` walks `~/.claude-fleet/*/`, groups dirs by account
  (assignments.json, verified against `api/oauth/profile` per dir), and reads **live quota for
  every account all the time** — every dir's access token is fresh by use. Closes the
  parked-telemetry gap by construction.
- The 5-min tick keeps telemetry + advisories only: "account X at ≥85% (resets HH:MM)" Telegram
  + graceful-drain fabrik-mail to the repos **mapped to that account** (assignments.json is the
  routing table). A walled account's windows pause until the 5h reset — the wall-resume
  machinery (quota-health spec, 2026-08-10) already schedules the resume; the other ~3 accounts'
  windows are untouched.
- Rebalancing = moving a *project* to another account = one deliberate login in that project's
  dir. The advisor (`--advise`) proposes moves from observed weekly burn; the operator decides.

### Quota spreading (why availability improves)

Today all windows serially burn one account (sarp hit 95% alone at 02:45 while three accounts
idled at 0%). Spread over 4 accounts, each 5h window fills ~4× slower, weekly burn per account
drops from "exhausted in ~2.x days" toward "under the weekly reset line", and a wall pauses only
that account's ~quarter of the fleet.

### Idle-dir keepalive (the only recurring duty, automated)

A chain idle >~30 days lapses. Weekly cron: for each dir whose ledger shows no use in 7 days,
run one `claude -p ping` **in that dir's own context** (its env, its chain — the sole-owner
in-place path youtube proved for weeks). This is NOT `--touch` (which copied a chain into a
temp dir — the fragile pattern that blanked pairs; it retires). Failure alerts via mesh-notify.

### Migration — the last login round

M0. Probe `settings.local.json` env merge (repeat of the proven `settings.json` probe).
M1. Build dir scaffolder (`claude_rotate.py --new-dir <slug> <account>`): mkdir, seed
    `.claude.json`, symlinks, assignments.json row.
M2. Hub role-dir probe (`CLAUDE_AGENT`-keyed selection); fall back to single hub dir if needed.
M3. **Staged rollout, 3–4 dirs per account per day**: create dirs, operator does ONE `/login`
    each (~15 total, the last ever), watch 24h for upstream grant evictions (see Unknowns)
    before the next batch.
M4. Flip `--status`/tick to fleet-dir mode; retire switch/capture/touch code + stores
    (stores archived to the DR store first); update `dr_claude_backup.sh` to back up
    `~/.claude-fleet/` (config-DR contract: extend the list when a new config surface appears).
M5. `~/.claude` remains the default for anything unmapped (operator ad-hoc runs) on one
    designated account.

## Rejected alternatives

- **Per-account dirs only (4 dirs)** — fewer logins, but every account's windows still share
  one chain: the overnight-refresh → morning-relogin class survives at ~¼ scale. Rejected: the
  operator's requirement is zero, not fewer.
- **Status quo + reload discipline + wait for upstream** — the race is open upstream with seven
  duplicate issues and no committed fix (surveyed 2026-08-15); nightly breakage is the live
  cost. Rejected.
- **Script-side refresh daemon (keep one file, refresh centrally)** — the token grant is
  Cloudflare-fenced to the CLI client (403/1010, live-probed 2026-08-13); defeating that is out
  of bounds. Dead.
- **Login automation (email-code capture)** — operator-settled NO (2026-08-13 memory:
  quota-rotation v2 findings; no login automation). Out of scope by decision.

## External dependencies

| Fact | Grounding | Source + date |
|---|---|---|
| `settings.json` supports an `env` map applied to sessions | official docs | code.claude.com/docs/en/settings, fetched 2026-08-15 |
| Project-level settings `env` can redirect `CLAUDE_CONFIG_DIR` | **live probe this session** (fixture project; CLI ignored shared creds, scaffolded target dir) | box, 2026-08-15 |
| Extension honors `CLAUDE_CONFIG_DIR` | prior grounded session (`acp-agent.js:14`) | session 92c3df30, 2026-07-15 |
| Refresh race is open upstream, no fix in 2.1.232 | issue survey | github.com/anthropics/claude-code issues #24317 #25609 #27933 #43392 #48786 #54443 #56339, 2026-08-15 |
| Refresh tokens single-use, ~30-day idle life, roll on use | live blobs (`refreshTokenExpiresAt` ≈ +28–30d) + incident forensics | box, 2026-08-15 |
| Direct HTTP refresh fenced (Cloudflare 1010) | live probe | box, 2026-08-13 (`_keepwarm_refresh` docstring) |
| ≥2 concurrent grants per account coexist | live: youtube-headless + shared dir, same account, weeks | box, 2026-08-15 |

## fabrik-lib verdict table

| Capability | Verdict | Why |
|---|---|---|
| Dir scaffold/seed, assignments, advisor, N-dir status | **extend existing** `scripts/sysadmin/claude_rotate.py` (+ twin) | box-local workstation ops; "extend, don't duplicate" |
| Keepalive cron | extend existing cron surface | one entry, calls the same script |
| fabrik-lib module | **none** — not a candidate | workstation-specific, zero reuse across project types |

## Shape/infra implications

None — box-local workstation system. No scaffold type, no `specs/services` yaml, no shape flags.
Docs: `docs/workstation/claude-account-rotation.md` is superseded at build time (rewrite in
place — same file, new architecture; Doc Sync Matrix "extend the existing doc, never a second").

## Constraints

- No login automation; no direct HTTP token refresh (both operator/probe-settled).
- Claude Code CLI + subscription OAuth only — never `ANTHROPIC_API_KEY` in operational paths.
- Credentials are secrets: backup before mutation (`backups/`, DR store), never log token bytes.
- Migration must never orphan a live chain: a dir is created *empty* and logged into fresh —
  the only file-copy is `.claude.json` seeding (no credential bytes).
- Governance sync: `.claude/settings.local.json` in ~15 project repos — verify it is ignored by
  each repo's gate/sync surfaces before M3 (it is Claude-Code-conventional local state).

## Open / blocking unknowns

| # | Unknown | Status | Resolution step |
|---|---|---|---|
| 1 | Concurrent OAuth grant cap per account (need ~4–6; ≥2 proven) | OPEN | M3 staged rollout watches for grant eviction (a relogin prompt in an untouched dir = abort signal → regroup to fewer dirs/account) |
| 2 | `settings.local.json` env merge = `settings.json` env merge | OPEN (expected yes) | M0 probe, 5 minutes, before anything else |
| 3 | Hub per-role dir selection via `CLAUDE_AGENT` | OPEN | M2 probe; fallback single hub dir is acceptable (reload-recoverable, no logins) |
| 4 | VPS/aro-wake fleet accounts (today fed by snapshot sync of WSL chains) | OUT OF SCOPE — named follow-up | separate spec: per-box dedicated logins, retiring snapshot shipping; until then VPS keeps consuming `manager-accounts` snapshots, so stores are archived, not deleted, at M4 |
