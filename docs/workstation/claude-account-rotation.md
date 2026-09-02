# Claude accounts — the pointer-rotation fleet (reference + runbook)

**What it is:** four Claude Max subscriptions (`ob@`, `can@`, `sarp@`, `mob@` — the latter
three are inbox-aliases of `ob@ocoron.com`), each permanently logged in to its OWN config dir,
and **one pointer that selects which account every project uses right now**. The `*/5` cron
tick moves that pointer toward quota headroom. Tool: `scripts/sysadmin/claude_rotate.py`
(+ its AFTER-EDIT twin `scripts/aro-wake/claude_rotate.py` — byte-identical, every edit lands
in both). Live view: `docs/workstation/quota-dashboard.md` (<http://localhost:5051/>).

**The load-bearing rule:** OAuth refresh tokens are single-use, so a chain that is SHARED
between processes gets invalidated out from under one of them — that was the morning relogin
wave. Each account therefore owns one dir and one chain forever; **rotation moves a symlink,
never a credential byte**. A flip cannot destroy a login, which is exactly what the retired
file-swap rotation used to do.

## Layout

```
~/.claude-fleet/
  ob/ can/ sarp/ mob/     one per ACCOUNT — each holds its own .credentials.json, logged in ONCE
  active -> mob           the pointer every session follows (a relative symlink)
  assignments.json        slug → account, pinned identity
  caps.json               per-account weekly reserves, e.g. {"ob@ocoron.com": 90}
```

Fleet root override: `CLAUDE_FLEET_ROOT` (`_fleet_root`, `claude_rotate.py:1327`). Only
`--new-dir` creates the root; readers never mkdir it.

## How a session binds to the pointer

Two environment variables — both, or the binding is a no-op:

- `CLAUDE_CONFIG_DIR` → `~/.claude-fleet/active` (the CLI's config dir: credentials,
  `.claude.json`, sessions)
- `CLAUDE_QUOTA_HOME` → the same path; the wall/resume layer (`claude-quota.py`) resolves its
  home from THIS variable, not from `CLAUDE_CONFIG_DIR`.

They are exported from **two** places, and both are required:

| File | Covers | Why both |
|---|---|---|
| `~/.bashrc` | terminals, login shells | interactive shells only |
| `~/.vscode-server/server-env-setup` | **the VS Code extension host** | `.bashrc` returns early for non-interactive shells, so extension windows never read it — they silently fell back to the shared `~/.claude` and ignored the pointer entirely (2026-08-15; 15 sessions, caught by the occupancy monitor) |

⚠️ The server-env file takes effect only after the VS Code **server** restarts:
`wsl --shutdown` from Windows, then reopen. "Reload Window" is NOT enough — the server
survives it.

## Rotation — when the pointer moves, and where

The `*/5` tick reads all four accounts, then decides (`_fleet_flip_leg`, `claude_rotate.py`):

- **Flip-away trigger:** the active account reaches `ROTATE_THRESHOLD` (default **98** — operator rule
  2026-09-03, "as soon as session limits hit 98% for the 5h window"; was 95; ONE helper `_rotate_threshold()`
  feeds every call site) on either the 5-hour or the weekly window. **Latency:** the quota dashboard
  server probes every 20s and invokes `--tick` the moment the active account crosses the line (or is
  cap-walled), so a flip lands within ~20s of the crossing; the `*/5` cron tick is the backstop
  (`docs/workstation/quota-dashboard.md` § the rotation trigger). The **weekly** leg is governed by the account's `caps.json` cap when one exists
  (the cap IS the operator's weekly rule — a cap of 99 trips at 99, not at the session threshold) and by
  `ROTATE_THRESHOLD` otherwise; the 5-hour leg is never cap-gated.
- **Target — PERISHABLE-FIRST (operator rule 2026-09-02):** among accounts that are alive, not
  walled, not cap-walled, and not themselves already ≥ threshold on either window, the one whose
  **weekly reset is soonest** wins (quota about to refresh is the cheapest to burn); ties break
  to lower weekly, then lower session utilization; an unknown reset time sorts last. The same
  rule the reactive path (`_pick_successor`) always applied; the tick used to rank by headroom
  instead. The weekly reserves are `caps.json`: `can` 99 · `mob` 99 · `sarp` 90 (10% kept) ·
  `ob` 80 (20% kept) — at weekly ≥ cap the account flips away whatever its session says.
  **A target must have 5h budget** (operator rule, same day): its session reading must be KNOWN and
  ≤ `ROTATE_TARGET_SESSION_MAX_PCT` (default = `ROTATE_DRAIN_THRESHOLD`, **85** — a target at or over the drain line would be flagged the moment it became active) — a weekly reading alone proves nothing about
  the session window, and a sibling near its own session wall would be flipped to and away from on
  the next tick. A cached standby whose 5h reset time has already passed is read as 0% (an idle
  account cannot burn fleet quota; the window rolled over — the board applies the same rule). A candidate ranked off
  a CACHED reading is live-probed once before it can become the pointer — **and when that probe
  fails, a reading younger than `ROTATE_CACHE_TRUST_S` (default 3600s) on a chain that passes the
  liveness gate is accepted anyway.** The probe runs with the standby's OWN access token, which is
  expired by construction for an idle account (only the active chain self-refreshes; the CLI rolls
  it on first use), so before 2026-09-02 every idle sibling read as "unverifiable" and the tick
  logged `NO successor has headroom` while `can@` sat at 12%/12% — a flip only ever worked when
  the successor happened to be live that tick. An OLDER cache still never becomes the pointer.
- **No successor ⇒ the tick says why, per sibling** (`walled` · `weekly N% ≥ cap` · `a window
  ≥ threshold` · `no quota reading` · `chain stale or no credentials` · `cached Nm ago and the
  live re-verify failed…`) — read `~/.claude/rotate-tick.log` before touching anything.
- **Never a dead chain:** the target's refresh token must pass the liveness gate
  (`_chain_stale_reason`) — a dir whose chain expired can never become the fleet's pointer.
- **Dwell:** 30 minutes between automatic flips (`ROTATE_DWELL_MIN`), so a noisy boundary
  cannot thrash. A missing/dangling pointer is repaired immediately, dwell-exempt.
- **No headroom anywhere:** nothing flips; ONE advisory per wall episode goes to Telegram AND
  broadcasts to every project mailbox ("reach a commit-and-push checkpoint") — it fires ONLY when
  the ACTIVE account is walled and this tick found no successor (`_fleet_active_wall_advisory`;
  a walled active with a headroom sibling merely held by the dwell is silent). The same tick
  writes the `fleet-exhausted` stamp, and the synced PreToolUse hook `quota_stop.py` turns it
  into a GRACEFUL STOP that reaches every session mid-turn: work tools are held with one
  instruction (commit + push, close the run record, end the turn); reads, git and the record
  tools stay open; the hold lifts the moment the tick clears the stamp; a session that ended is
  restarted by the operator or the resume mesh. Before 2026-09-02 the four broadcasts of the day
  were the picker bug (§ Target) talking, not real exhaustion. Work resumes
  as windows reset.
- **Manual:** `--switch <account>` flips now — pause- and dwell-exempt, the deliberate
  override. It warns if the target carries a cap.

Sessions ride through a flip: a running session keeps its in-memory token (up to 8h) and lands
on the new account at its next renewal. No login is ever triggered.

## Per-account caps — reserving quota for yourself

`~/.claude-fleet/caps.json` maps an account email to a weekly percentage the FLEET may not
exceed:

```json
{"ob@ocoron.com": 90}
```

At or above the cap the account is **cap-walled**: automated flips exclude it and `--status`
says so, reserving the remainder for the operator's own claude.ai browser use. `--switch` may
still target it deliberately. Keys are matched case-insensitively; a key matching no known
account warns ("cap inactive") rather than failing silently.

## `--status` — the board

```bash
python3 scripts/sysadmin/claude_rotate.py --status [--json]
```

- **Per-account grouping by pinned identity.** A `pending-login` row gets ONE
  `api/oauth/profile` probe with that dir's own token; success pins the verified email
  permanently.
- **Quota: live or cached-with-age, never blind.** A reading is live while the dir's
  credential mtime is under 8h (`_FLEET_TOKEN_FRESH_S`); otherwise the last-known row rides
  with its age (`STALE — cached Nh ago`).
- **Warnings, by name:** cap-walled accounts · a chain within 5 days of its refresh-token
  lapse (`_CHAIN_EXPIRY_WARN_S`) · carrier problems · occupancy · identity mismatch.
- `--json` carries `active`, `weekly_cap`/`cap_walled` per row, `pause`, and `fleet_warnings`.

### The occupancy monitor

Counts LIVE Claude CLI processes (argv-basename match, never a substring) whose
`/proc/<pid>/environ` carries **no non-empty `CLAUDE_CONFIG_DIR`** — those are on the shared
`~/.claude` chain, ignoring the pointer. Above `CLAUDE_FLEET_OCCUPANCY_MAX` (default 3) it
warns by name. This is the detector that caught the extension-host gap above; a count near
zero is the healthy state.

### The identity-mismatch net

A flip landing inside the CLI's ~1–2s credential-renewal window can write account A's rolled
chain into account B's dir. Prevention is impossible from this side, so it is DETECTED: once
per hour per account (`_IDENTITY_PROBE_INTERVAL_S`) the freshest dir's token is asked who it
is; a mismatch against the pinned identity warns loudly, names the dir and both emails, and
the verdict is sticky until a later probe clears it. **Recovery is ONE `/login` in that dir —
never a credential-file copy.**

## Keepalive — the only recurring duty, automated

```bash
python3 scripts/sysadmin/claude_rotate.py --keepalive
```

A chain idle ~30 days lapses. The weekly cron pings every fleet dir whose `.credentials.json`
**mtime** (never content) is older than 7 days (`_KEEPALIVE_MAX_IDLE_S`): one in-place
`claude -p ping` bound to that dir, so the CLI rolls THAT dir's own chain. A future-skewed
mtime counts as DUE. rc 0 when every stale dir refreshed; rc 1 + a Telegram alert on any
failed ping. Per-ping timeout `KEEPALIVE_TIMEOUT` (default 150s).

## Recovery rules

- **Reload, never login.** A window that lost auth mid-session holds a superseded pair in
  memory while the dir's on-disk chain is current. Reload the window — `/login` is only for a
  dir whose chain itself lapsed (keepalive alert) or a brand-new dir.
- **DR: a fleet-dir restore = ONE `/login` in that dir, never a credentials-file restore.** A
  stored chain is consumed the moment the live one rolls, so restoring bytes installs a spent
  single-use token. Backups exclude `.credentials.json` by design.

## Pause semantics — `--pause-switch` / `--resume-switch`

The `switch-paused` marker (`~/.claude/state/switch-paused`) gates automated installs:

- The tick prints the withheld successor instead of flipping; telemetry, keep-warm and drain
  warnings stay armed.
- `--switch <name>` does NOT route through the gate — the deliberate manual escape hatch.
- Tri-state: absent (running) · `marker` (operator pause) · `error` (state dir unreadable →
  **fail closed**, nothing installs, but an all-credentials-dead 401 alert still fires).
- A broken state dir makes `--pause-switch`/`--resume-switch` exit 1 rather than pretend.
- `--status --json` reports it in `"pause"`.

**In fleet mode the marker is no longer the only barrier:** with ≥1 fleet dir present,
`_rotate_active_account` refuses structurally (first statement, before the pause check), so no
straggler `~/.claude`-bound caller can trigger a legacy snapshot swap. Rotation is the pointer
flip; nothing installs into `~/.claude`.

## Cron — the installed lines

```cron
*/5 * * * * flock -n $HOME/.claude/state/rotate.lock python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --tick >> $HOME/.claude/rotate-tick.log 2>&1
20 6 * * 1 python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --keepalive >> $HOME/.claude/keepalive.log 2>&1
@reboot sleep 20 && /usr/bin/python3 /opt/fabrik/scripts/sysadmin/quota_dashboard.py --ensure >> $HOME/.claude/quota-dashboard.log 2>&1
*/10 * * * * /usr/bin/python3 /opt/fabrik/scripts/sysadmin/quota_dashboard.py --ensure >> $HOME/.claude/quota-dashboard.log 2>&1
```

The hourly `--drift-check` cron and the SessionStart drift-check hook are gone — a settings
symlink would have run the drift-check from every fleet dir against its hardcoded `~/.claude`
paths, re-creating the capture/retarget hazard this design retires.

**Cron PATH — why the pings resolve `claude` without a `PATH=` line.** Cron runs with a minimal
`PATH` (`/usr/bin:/bin`) that excludes `~/.local/bin`, where the `claude` CLI installs. Every
`claude -p ping` (the tick's stale-reading refresh **and** the keepalive) therefore prepends
`~/.local/bin` to its own subprocess env via `_with_claude_on_path(env)` before spawning, so the
CLI resolves under cron exactly as in a login shell — no crontab `PATH=` line is required, on
this host or the vendored `aro-wake` copy. Without it the spawn raises `FileNotFoundError`,
caught silently: idle readings never refresh (the dashboard cache ages unbounded) and idle
chains are never warmed. Regression-guarded in `tests/test_claude_fleet.py`
(`test_with_claude_on_path_*`).

**Transient-blip resilience — `_oauth_get` retries.** The telemetry reads (`usage`, the
identity `profile` probe) go through `_oauth_get`, which retries **transient** failures
(timeout / connection reset / 5xx) with a short per-attempt timeout and backoff, so one stalled
`urlopen` under a flaky link (VPN drop) no longer blanks the quota dashboard — its ping-free
`--status` probe runs behind a 60s cap that a single 15s stall used to trip ("Live probe failed
— TimeoutExpired after 60s", 2026-08-22). A **4xx (esp. 401/403) is definitive auth and is never
retried** — retrying a dead/wrong token only burns the budget. Both knobs are env-tunable:
`OAUTH_GET_TIMEOUT_S` (default **8s**) and `OAUTH_GET_ATTEMPTS` (default **2**), sized so two
attempts stay inside a caller's budget. A sustained outage still falls soft to the last-good
reading (the dashboard's red banner) — no retry conjures a working network. Regression-guarded
in `tests/test_claude_fleet.py` (`test_oauth_get_*`).

## Runbook

### The logins (done — chains date from 2026-08-15, which is when their idle clocks start)

All four accounts are logged in, one login each, and no further login is expected. For
reference, adding or re-homing an account is:

```bash
python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --new-dir <account-slug> <account-email>
CLAUDE_CONFIG_DIR="$HOME/.claude-fleet/<slug>" CLAUDE_QUOTA_HOME="$HOME/.claude-fleet/<slug>" claude
# then /login as that account, and /exit
```

The dir is created empty of credentials and filled by that ONE `/login`. Nothing copies a
credential byte.

**Moving a slug to a different account:** reset that row's `identity` to `"pending-login"` in
`assignments.json`, then one `/login` in the dir. `identity` is the field that matters —
grouping, telemetry and flips all key on it, and it is never re-probed once pinned. The row's
`account` field is bookkeeping read only by `--new-dir`'s ownership guard (and the caps
known-account check), so a stale value changes no fleet behaviour; update it in the same edit
anyway, or a later `--new-dir <slug> <new-email>` will be refused by the stale claim.

### Everyday operation

| Want | Do |
|---|---|
| See the board | <http://localhost:5051/> or `--status` |
| Move the fleet now | `--switch <account>`, or the `switch →` button on the board row (same flip, confirmed in-page) |
| Reserve quota for browser use | edit `caps.json`, no restart needed |
| Freeze automated flips | `--pause-switch` (`--resume-switch` to release) |
| A window ignores the pointer | check the occupancy warning; it needs the env — for extension windows, `wsl --shutdown` + reopen |

## Legacy: the shared-file rotation pool — live until retirement

The modes coexist, keyed on the fleet root: with it empty, the machinery below is the live
behavior; with dirs present, `--status`/`--tick` run the fleet view and this governs only
`~/.claude` itself, which stays the ad-hoc default for unmapped one-off runs until the M5
thinning. It operates ONE `~/.claude/.credentials.json` swapped between per-account snapshot
stores (`~/.claude/manager-accounts/<name>/`). It retires at the M4 sweep — do not build on it.

- `--list` · `--switch <name>` · `--next` — snapshot management (in fleet mode `--switch`
  routes to the pointer flip instead).
- Legacy `--status` — per-store quota table; parked stores whose access token aged out show
  "parked — quota unknown until used (refresh token valid)" — the blindness the fleet view retires.
- Legacy tick — `ROTATE_THRESHOLD` (95) switching with a 30-minute dwell, graceful-drain mail
  + one Telegram (24h suppress), keep-warm for parked snapshots.
- `--capture-current` · `--drift-check` — snapshot the live chain (identity-gated); the cron
  and hook triggers are removed, the flags remain invocable by hand until the sweep.
- `--touch [<account>]` — the temp-dir-copy refresh; superseded by `--keepalive`'s in-place path.
- Safety invariants: atomic credential writes under the rotation flock with a `.prev` backup;
  nothing filed without positive identity verification; the tick never signals processes.
- Audit trail: `~/.claude/state/rotate-ledger.jsonl` (size-capped), which now also records
  every pointer `flip`.

## Successor plan (named, NOT done)

- **M4 retirement sweep** — retire the switch/capture/touch/drift machinery + the
  `manager-accounts` stores (archived to the DR store first), sweeping every consumer:
  `capture-watch.sh` (box-local, `~/.claude/state/`), the removed drift-check triggers'
  remnants, `claude-mesh-test.sh` (box-local, `~/.claude/bin/`)
  fixtures asserting retired argv, the cost-model repoints (`claude_p_cost.py` /
  `derive_cost.py` read `_MANAGER_ACCOUNTS` — repoint before archiving),
  `export_claude_state.sh`, `bootstrap-vps.sh`, and the aro-wake twin. The
  `claude-sound.sh` `--switch`/`--next` mesh legs are a **named, owned step** — the sound
  system is never edited as a side effect. DR: `dr_claude_backup.sh` gains the fleet-root
  backup **excluding `.credentials.json`**.
- **M5 thinning** — move the remaining unmapped `~/.claude` occupants onto fleet dirs until
  the shared chain has no routine users left.
- **VPS follow-up** (separate spec, hard deadline **M4+30d**) — per-box dedicated logins,
  retiring the hourly snapshot shipping. Until it lands the VPSes work off the sync of the
  still-live `~/.claude`; the archived sibling stores stop rolling at M4 and lapse ~30 days
  later.

## Related

- `docs/workstation/quota-dashboard.md` — the localhost:5051 board over this system
- `docs/superpowers/specs/2026-08-15-login-once-credentials-design.md` — the design +
  rejected alternatives (no login automation, no HTTP refresh)
- `docs/development/reviews/2026-08-15-pointer-rotation-review.md` — the 4-round review that
  caught dead-chain flips and vanishing mismatch warnings
- `docs/workstation/hooks-index.md` §2c (the cron tick row)
