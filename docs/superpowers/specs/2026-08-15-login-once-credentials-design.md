# Design spec — login-once credential architecture (per-window `CLAUDE_CONFIG_DIR` isolation)

Status: CONVERGED (two review cycles 2026-08-15 — 7-pass initial + 4-pass operator-invoked re-review with an Opus edge-case adversary; both closed on md5-verified no-op passes)
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

Upstream status (live-verified via GitHub API + CHANGELOG, 2026-08-15): the race was tracked as
anthropics/claude-code #24317 and **partially mitigated** — a lockfile in the refresh path
(~2.1.81), a parallel-session wake-from-sleep logout fix (2.1.211), and a concurrent-refresh
fix (2.1.221). #24317 was closed as *completed* 2026-05-07 with no maintainer explanation;
#25609/#27933/#43392/#48786/#56339 are closed as duplicates; the only open tracker, #54443, is
labeled *stale*. **The field disagrees with the close**: users report reproduction through
2.1.195 post-close, and this box reproduced the full class on **2.1.232 the same morning this
spec was written**. Net: upstream considers it done, the failure persists here, and no open
tracked fix path exists — self-help isolation is the only route that doesn't wait on a closed
issue.

**The load-bearing fact:** an account that is *used* never needs a login — the CLI rolls its
chain on every real turn. Every relogin traces to sharing, swapping, or stranding a chain, never
to OAuth itself. Existence proof on this box: `~/.claude-youtube-headless` — one login, weeks of
unattended multi-process (`claude -p`, concurrency 5) operation, zero relogins, because its
chain has no foreign owners.

## Chosen approach — one refresh chain per long-lived session, via per-project config dirs

### Mechanism (proven live, 2026-08-15, this session)

A project-level `.claude/settings.local.json`:

```json
{"env": {"CLAUDE_CONFIG_DIR": "/home/ozgur/.claude-fleet/<slug>",
         "CLAUDE_QUOTA_HOME": "/home/ozgur/.claude-fleet/<slug>"}}
```

`CLAUDE_QUOTA_HOME` rides along because the wall/resume layer (`~/.claude/bin/claude-quota.py:37`)
resolves its home from that variable, not from `CLAUDE_CONFIG_DIR` — without it, all windows
would share one `~/.claude/.claude-manager/wall-state.json` and sleep on each other's walls
(adversary finding B4). With it, wall state is per-dir: a wall recorded by a `seo/` session is
read only by `seo/` sessions. Hub per-window env carries both variables likewise.

**Empirically verified twice (2026-08-15, this session):** `claude -p` runs in fixture projects
carrying exactly this file — once as `settings.json`, once as `settings.local.json` — both
ignored the healthy shared `~/.claude` credentials ("Not logged in") and scaffolded the target
dir. The `env` map redirects the config dir with **no PATH shim, no wrapper, no VS Code
setting**, and it survives CLI updates. `settings.local.json` is the required carrier, not just
the polite one: `.claude/settings.json` in project repos is a **governance-synced surface**
(`scripts/fabrik_synced_manifest.py:106`) and would be overwritten fleet-wide.

Extension coverage: the redirect is applied by the **CLI itself** when it loads project
settings, so it binds any spawner — extension or terminal — that runs the CLI in the project
cwd. Probes above used `-p` mode; migration step M3 verifies the first interactive extension
window before scaling (a stale July citation to the extension's `acp-agent.js` was dropped —
that file is not present in the currently installed extension, and the CLI-side probe is the
stronger ground).

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
- Hub exception: 3 windows share `/opt/fabrik` as cwd, so cwd-keyed settings cannot split them —
  and a settings `env` entry would *override* any per-window value (the docs' documented
  precedence), so **the hub gets NO `settings.local.json` entry**: each hub window's own
  environment carries `CLAUDE_CONFIG_DIR=~/.claude-fleet/fabrik-<role>` directly (set wherever
  the operator already sets `CLAUDE_AGENT` per window). A hub terminal opened WITHOUT the
  per-window env lands on `~/.claude` (the M5 ad-hoc default) — visible in `--status`'s
  carrier/occupancy check, never a corruption. **Fallback** (if per-window env proves
  impractical): one shared `fabrik` dir — a 3-process residual race, recoverable by window
  reload (never a login), a fifth of today's blast radius. Resolution: migration step M2 probes it.
- Headless crons in project cwds (`ci_fix_dispatcher` dispatches `claude -p` inside
  `/opt/<project>`, `cwd=repo_dir` at `scripts/ci_fix_dispatcher.py:203`) inherit that
  project's dir automatically — no per-cron work.
- **Third carrier — headless callers without a project cwd** (root crons via `claude-run.sh`,
  the hourly keepalive shim, anything using `cron-ci-fix/`): the launch line itself sets
  `CLAUDE_CONFIG_DIR`/`CLAUDE_QUOTA_HOME` (a cron env prefix; `claude-run.sh`'s `sudo env`
  whitelist gains the two variables). Without this, those callers silently stay on `~/.claude`
  (adversary findings R1/R6).
- ⚠️ **Git worktrees don't carry the mapping**: `settings.local.json` is untracked, so a fresh
  `claude` session started inside a worktree checkout falls back to shared `~/.claude`.
  In-session worktree moves and Task subagents are unaffected (the env is already applied to
  the running process). Mitigation at build time: worktree-creating flows copy the parent
  checkout's `.claude/settings.local.json` into the worktree (one `cp` in the helper), and the
  **carrier-presence monitor** (below) catches any silent fallback the copy misses.
- **Carrier-presence monitor** — the load-bearing invariant must not fail open invisibly
  (adversary finding B3): `--status` (and the tick) checks every mapped project for its
  `settings.local.json` carrier and WARNs when one is missing or when an unexpected process
  count appears on `~/.claude`; a missing carrier is a named alert, never a silent rejoin of
  the shared chain.

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
- `claude_rotate.py --status` walks `~/.claude-fleet/*/` and groups dirs by account. **Identity
  is pinned once, at dir creation** (the login's `api/oauth/profile` answer, cached in
  assignments.json) — never re-probed per status, so the dead-token identity gate that lost
  can@ is not reintroduced (adversary finding R4). Usage is queried once per account per tick
  (the freshest dir's token, ~4 calls) — **live whenever any of the account's dirs was used in
  the last ~8h** (during work, effectively always), else **last-known + age**, which for an
  idle account is an upper bound (utilization only decays while unused). Closes the
  parked-telemetry gap: today a parked account is unreadable at all.
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

A chain idle >~30 days lapses. Weekly cron: for each dir whose `.credentials.json` mtime is
older than 7 days (the CLI rewrites it on every refresh, so mtime IS the last-use signal),
run one `claude -p ping` **in that dir's own context** (its env, its chain — the sole-owner
in-place path youtube proved for weeks). This is NOT `--touch` (which copied a chain into a
temp dir — the fragile pattern that blanked pairs; it retires). Failure alerts via mesh-notify.

### Migration — the last login round

**M-pre. Disarm the old world FIRST** (adversary findings B1/B2 — the pause marker gates only
the tick; these stay armed without explicit action):
  - `claude-sound.sh` autorotate: **already disarmed** (`CLAUDE_SOUND_AUTOROTATE=0` in the
    settings env, verified live 2026-08-15) — keep it that way.
  - `run_claude()`'s rotation-retry (the WSL keepalive shim's swap path): gate it with the same
    `switch-paused` marker the tick honors.
  - `--drift-check`: disable BOTH the hourly cron and the **SessionStart hook**
    (`~/.claude/settings.json:37`) before any fleet dir exists — the settings symlink would
    otherwise run it from every new dir against its hardcoded `~/.claude` paths, re-creating
    the exact capture/retarget hazard this design retires.
  - Stop the `capture-watch.sh` poller; leave the hourly VPS fleet-sync (it feeds the VPS from
    `~/.claude`, which stays live as the ad-hoc account — reviewed in the VPS follow-up spec).
M0. ~~Probe `settings.local.json` env merge~~ **DONE 2026-08-15** (probe passed; see Mechanism).
M1. Build dir scaffolder (`claude_rotate.py --new-dir <slug> <account>`): mkdir, seed
    `.claude.json`, symlinks, assignments.json row (+ a `--sync-mcp` helper — the per-dir
    `.claude.json` copies fork the MCP roster ~15×, adversary finding R7; the durable de-fork
    is the planned global/per-project `.mcp.json` split, intel finding 01KZX92Q). Acceptance
    includes probing that symlinked `projects/`/`agents/`/`commands/`/`skills/` behave under a
    redirected dir (only `.claude.json` relocation is live-proven today). Also at M1: add
    `.claude/settings.local.json` to the fleet-synced gitignore block
    (`templates/scaffold/gitignore-synced-block.txt` + scaffolder) — **no ignore rule exists
    anywhere today** (verified: zero hits across src/templates/scripts), so without this every
    project would commit a hardcoded absolute path (adversary finding B3).
M2. Hub per-window env probe: set `CLAUDE_CONFIG_DIR=~/.claude-fleet/fabrik-<role>` in each hub
    window's environment (beside the existing per-window `CLAUDE_AGENT`); fall back to a single
    shared hub dir if per-window env proves impractical.
M3. **Staged rollout, 3–4 dirs per account per day**: create dirs, operator does ONE `/login`
    each (~15 total, the last ever), watch 24h for upstream grant evictions (see Unknowns)
    before the next batch.
M4. Flip `--status`/tick to fleet-dir mode; retire switch/capture/touch code + stores
    (stores archived to the DR store first). **Retirement blast radius — sweep every consumer**
    (adversary finding R2): `capture-watch.sh` (string-coupled to two drift-check messages),
    the SessionStart hook + hourly cron (disabled at M-pre, removed here), `claude-sound.sh`'s
    `--switch`/`--next` mesh legs (⚠️ operator hard rule: the sound system is not edited as a
    side effect — its change is a named, owned step), `claude-mesh-test.sh` fixtures asserting
    the retired argv, `claude_p_cost.py:45` + `derive_cost.py:26` (`_MANAGER_ACCOUNTS` feeds
    the amortized $/Mtok model — repoint before archiving stores), `export_claude_state.sh:27`,
    `bootstrap-vps.sh:1021`, and the byte-identical aro-wake twin. DR: `dr_claude_backup.sh`
    backs up `~/.claude-fleet/` **excluding `.credentials.json`** — a stored chain is consumed
    the moment the live one rolls, so **fleet-dir restore = one `/login`, never a file restore**
    (adversary finding R3; also folds the existing `~/.claude-youtube-headless` special case).
M5. `~/.claude` remains the default for anything unmapped, on one designated account — with its
    occupant list made explicit and thinned: operator ad-hoc runs and worktree stragglers stay;
    the root crons (`claude-run.sh`), the keepalive shim, and `cron-ci-fix` callers move to
    their own dirs via the third carrier (adversary finding R1). What remains on `~/.claude` is
    a handful of occasional processes sharing one chain — an accepted, monitored residual for
    one-off runs, not the overnight fleet.

## Success criteria (testable)

1. **Zero login prompts** across all migrated windows for 30 consecutive days of normal use
   (measured: no `/login` events outside migration itself).
2. **Overnight survival**: a full night with active autonomous sessions ends with every
   migrated window usable without reload or login.
3. `--status` shows session+weekly quota for **all 4 accounts** at any time — live values
   whenever an account had use in the last ~8h, otherwise last-known-with-age (never today's
   "parked — quota unknown").
4. **No credential file is ever written by two unrelated owners**: each
   `~/.claude-fleet/<slug>/.credentials.json` is only ever touched by sessions bound to that
   dir — its project's windows, its headless callers, and its own keepalive ping. (Hub
   fallback case: the 3 hub windows bound to one shared `fabrik` dir count as bound — the
   residual 3-process race there is documented, reload-recoverable, and login-free.)
5. A quota wall on one account leaves the other accounts' windows **fully working**, and the
   walled account's windows resume at the 5h reset without operator action.

## Rejected alternatives

- **Per-account dirs only (4 dirs)** — fewer logins, but every account's windows still share
  one chain: the overnight-refresh → morning-relogin class survives at ~¼ scale. Rejected: the
  operator's requirement is zero, not fewer.
- **Status quo + reload discipline + wait for upstream** — upstream closed the tracking issue
  as completed (2026-05-07) after partial mitigations, yet the class reproduced on this box on
  2.1.232 the day of this spec; the only open tracker is stale. There is nothing tracked to
  wait FOR, and nightly breakage is the live cost. Rejected.
- **Script-side refresh daemon (keep one file, refresh centrally)** — the token grant is
  Cloudflare-fenced to the CLI client (403/1010, live-probed 2026-08-13); defeating that is out
  of bounds. Dead.
- **Login automation (email-code capture)** — operator-settled NO (2026-08-13 memory:
  quota-rotation v2 findings; no login automation). Out of scope by decision.

## External dependencies

| Fact | Grounding | Source + date |
|---|---|---|
| Settings `env` map: *"Environment variables passed to Claude Code and its subprocesses"*; applied *"no matter how `claude` was launched"*, **overriding** the inherited shell value and re-applied on file change | official docs, quoted | code.claude.com/docs/en/settings + /docs/en/env-vars, fetched 2026-08-15 |
| `CLAUDE_CONFIG_DIR` relocates the config dir; *"credentials are stored under the configuration directory"* (login prompted when pointed at an empty dir) | official docs, quoted | code.claude.com/docs/en/debug-your-config + /docs/en/server-managed-settings, fetched 2026-08-15 |
| Project-level settings `env` redirects `CLAUDE_CONFIG_DIR` (both `settings.json` and `settings.local.json`) | **live probes this session** (fixture projects; CLI ignored shared creds, scaffolded target dirs) | box, 2026-08-15 |
| Race partially mitigated upstream (lockfile ~2.1.81; 2.1.211; 2.1.221) but tracking closed while field reports persist; only open tracker #54443 is stale; reproduced HERE on 2.1.232 | GitHub API issue states + CHANGELOG quotes + box incident | github.com/anthropics/claude-code #24317 #54443 + CHANGELOG, 2026-08-15 |
| No published cap on concurrent devices/logins per account; sessions 28 days with rolling refresh; *absence of a documented limit is not a guarantee* — subscription acceptable-use terms govern (ordinary use of the official CLI on own accounts is the design here) | support articles surveyed | support.claude.com articles 13124001 + 10310342, fetched 2026-08-15 |
| Refresh tokens single-use, ~30-day idle life, roll on use | live blobs (`refreshTokenExpiresAt` ≈ +28–30d) + incident forensics | box, 2026-08-15 |
| Direct HTTP refresh fenced (Cloudflare 1010) | live probe | box, 2026-08-13 (`_keepwarm_refresh` docstring) |
| ≥2 concurrent grants per account coexist | live: youtube-headless + shared dir, same account, weeks | box, 2026-08-15 |
| `.claude.json` (MCP/trust/onboarding) is kept INSIDE the redirected dir, not at `~` | live: `~/.claude-youtube-headless/.claude.json` exists and is actively maintained (mtime = today) | box, 2026-08-15 |

Pool-grounding note (recorded for the review): a pool researcher's claim that the upstream race
was "fixed Nov 2024 via `claude/auth.py` file locking" was **fabricated** (wrong year — closures
are Feb–May 2026; wrong language — the refresh path is JS with `proper-lockfile`; no such file).
Scored 0 in the flywheel. The native Opus verify then established the accurate picture absorbed
above: partial mitigations DID ship, the tracking is closed, and the failure still reproduces
here — a fabrication's direction being half-right does not make it grounding.

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
- Governance sync: `.claude/settings.local.json` is safe from the manifest sync (file-scoped to
  `settings.json`, `fabrik_synced_manifest.py:106`) but is **not gitignored anywhere today** —
  M1 adds it to the fleet-synced gitignore block before any project carries one.

## Open / blocking unknowns

| # | Unknown | Status | Resolution step |
|---|---|---|---|
| 1 | Concurrent OAuth grant cap per account (need ~4–6; ≥2 proven live; no published cap found in support docs 2026-08-15 — absence of documentation ≠ guarantee) | OPEN | M3 staged rollout watches for grant eviction (a relogin prompt in an untouched dir = abort signal → regroup to fewer dirs/account) |
| 2 | ~~`settings.local.json` env merge~~ | **RESOLVED 2026-08-15** | live probe passed (see Mechanism) |
| 3 | Hub per-window env practicality (`CLAUDE_CONFIG_DIR` set directly in each window's environment, beside `CLAUDE_AGENT`); extension INTERACTIVE session applies project env like `-p` does | OPEN | M2/M3 first-window probes; fallback single hub dir is acceptable (reload-recoverable, no logins) |
| 4 | VPS/aro-wake fleet accounts (today fed by snapshot sync of WSL chains) | OUT OF SCOPE — named follow-up **with a hard deadline** | separate spec: per-box dedicated logins, retiring snapshot shipping. Until it lands the VPS keeps working off the hourly sync of the still-live `~/.claude` (the ad-hoc account); the ARCHIVED sibling stores stop rolling at M4 and lapse ~30 days later (adversary finding R8) — the follow-up must land within **M4+30d** or those accounts need one login each on the VPS side |
