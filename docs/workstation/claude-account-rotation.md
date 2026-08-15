# Claude accounts — the login-once fleet (reference + rollout runbook)

**What it is:** four Claude Max subscriptions (`ob@`, `can@`, `sarp@`, `mob@` — the latter three
are inbox-aliases of `ob@ocoron.com`) each stay permanently logged in, one OAuth chain per
long-lived Claude window. Tool: `scripts/sysadmin/claude_rotate.py` (+ its AFTER-EDIT twin
`scripts/aro-wake/claude_rotate.py` — byte-identical, every edit lands in both).

**The load-bearing rule:** OAuth refresh tokens are single-use. A chain that is *used* never
needs a login — the CLI rolls it on every real turn; every relogin traces to sharing, swapping,
or stranding a chain. So every long-lived window gets its OWN config dir: **one dir = one chain
= one `/login`, ever**. Credential files never move between owners again.

## The per-window dir model

Fleet root: `~/.claude-fleet/` (override: `CLAUDE_FLEET_ROOT`). One kebab-case slug dir per
long-lived window (`seo/`, `youtube/`, `fabrik-infra/`, `cron-ci-fix/`, …), plus
`assignments.json` — the routing table (slug → account, pinned identity, bound project). Only
`--new-dir` ever creates the root; readers (`--status`, `--sync-mcp`, `--keepalive`) never
mkdir it. On an absent/empty root, `--status` and the tick keep the legacy behavior below
live; `--sync-mcp`/`--sync-shared` and `--keepalive` have no legacy equivalent —
`--keepalive` prints "nothing to do" and exits 0 either way, while the sync commands exit 1
with "nothing to sync" on an ABSENT root (a loud misconfiguration signal) and exit 0
silently on an empty one.

A window is bound to its dir by TWO environment variables — both, or the binding is a no-op:

- `CLAUDE_CONFIG_DIR` — relocates the CLI's config dir (credentials, `.claude.json`, sessions).
- `CLAUDE_QUOTA_HOME` — the wall/resume layer (`claude-quota.py`) resolves its home from THIS
  variable, not from `CLAUDE_CONFIG_DIR`; without it every window sleeps on every other
  window's quota wall.

The dir's `.credentials.json` has exactly one WRITER: that window (plus its own headless
callers and its own keepalive ping) — nothing else ever writes, copies, or relocates it.
Two sanctioned in-memory READS exist: `--status`/`--tick` extract the dir's access token for
the identity-pin and quota-usage probes (never logged, never persisted).

## The two-variable carrier

For a project repo the binding rides `<project>/.claude/settings.local.json`:

```json
{"env": {"CLAUDE_CONFIG_DIR": "/home/ozgur/.claude-fleet/<slug>",
         "CLAUDE_QUOTA_HOME": "/home/ozgur/.claude-fleet/<slug>"}}
```

- `settings.local.json`, never `settings.json` — the latter is a governance-synced surface
  (`scripts/fabrik_synced_manifest.py`) and would be overwritten fleet-wide.
- `--new-dir --project` MERGES the two keys into an existing carrier, preserving every other
  key (three projects keep Claude Code permissions state in this file) and the file's mode; an
  unparseable carrier is refused loudly, never overwritten.
- The carrier is gitignored (the fleet-synced gitignore block lists
  `.claude/settings.local.json` — per-project, machine-specific, never committed), so a fresh
  git worktree checkout does NOT carry it and falls back to the shared `~/.claude`; copy the
  parent checkout's carrier into a worktree you intend to run Claude in, and rely on the
  carrier monitor (below) to name any silent fallback.

## Scaffolding a dir — `--new-dir` (the seeding contract)

```bash
python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py \
  --new-dir <slug> <account-email> [--project /opt/<repo>] [--from <slug|path>]
```

Creates `<fleet-root>/<slug>/` at 0700, seeds it, records the assignments row, writes the
project's carrier when `--project` is given — and **never reads or writes a credential byte**:
the dir is created empty of credentials and filled by ONE operator `/login`.

What lands where:

| Surface | Disposition | Why |
|---|---|---|
| `.credentials.json` | never touched — created by the operator's `/login` | one chain, one owner |
| `.claude.json` | seeded COPY from the roster source (`--from`, a slug or path; default `~/.claude.json`) | MCP roster + per-project trust + onboarding carried over; the login replaces only its OAuth section |
| `agents/`, `commands/`, `skills/`, `projects/` | symlink → canonical `~/.claude/…` | roster/governance/transcripts stay single-source; writes inside a symlinked DIR resolve to the canonical inode |
| `settings.json` | COPY, never a symlink | the CLI writes config via tmp+rename, and `os.replace` onto a FILE symlink replaces the link — a symlink would silently fork off the canonical copy on the first settings write. The copy is re-pushed by `--sync-shared` |
| `assignments.json` | one row: account, created stamp, `identity: pending-login`, optional `project` | the routing table `--status`, the tick and the drain mail all read |
| `<project>/.claude/settings.local.json` | two-variable merge (with `--project`) | the carrier above |

**Resumable, row-is-truth.** Every step is idempotent: a dir that exists but holds no
credentials is an unfinished scaffold, and re-running COMPLETES it (seeds what is absent, links
what is absent, finishes the carrier) — every partial failure converts to "fix the cause,
re-run". For an existing slug the assignments ROW is truth; with `--project` omitted, a resume
completes the binding the row already records. The whole body runs under the assignments flock,
so concurrent runs serialize instead of losing each other's row.

**The five refusal states** (rc 1 — exactly the cases where re-running would destroy or
duplicate something):

1. The dir holds a `.credentials.json` — a LIVE chain, never re-seeded.
2. The row names a DIFFERENT account — rebalancing is a deliberate re-login, not a
   re-scaffold (to move a slug: edit the row's `account` AND reset its `identity` to
   `"pending-login"` — grouping keys on the pinned identity, which is never re-probed
   otherwise — then `/login` the new account in that dir).
3. The row has no usable `account` value — corrupt, never claimed.
4. The row is already bound to a DIFFERENT project — moving a binding is an operator action
   (remove the old carrier, edit the row), never a scaffold side effect.
5. The routing table cannot be parsed — never append to bytes that could not be read back.

(`--project /opt/fabrik` is also refused — see the hub recipe below — and a malformed
slug/email exits 2 with usage. Plain I/O failures — scaffold step, carrier write, row
write, and the `--project` carrier-parse pre-flight — also exit 1 with one clean line;
those are re-runnable, not refusals.)

## Roster re-push — `--sync-mcp` / `--sync-shared`

```bash
python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --sync-mcp   [--from <slug|path>]
python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --sync-shared [--from <slug|path>]
```

- `--sync-mcp` pushes the MCP roster into every fleet dir; `--sync-shared` additionally
  re-pushes the `settings.json` copy.
- The roster push is a section-level MERGE, never a file copy: each dir's own OAuth account and
  per-project trust are preserved; a dir whose `.claude.json` cannot be parsed is SKIPPED, and
  a `/login` landing mid-merge is detected (mtime re-check) and re-merged rather than clobbered.
- ⚠️ **Default-source revert hazard:** with no `--from`, the source is `~/.claude.json` — the
  shared ad-hoc dir. Once windows are migrated that file stops being the live roster, and a
  default-source push would REVERT every dir to a stale one; the command prints a loud warning
  when it takes the fallback while fleet dirs exist. Pass `--from <slug>` (a migrated dir) or
  `--from <path>` to name the real source.

## Fleet `--status` and the tick

Both are feature-detected: **≥1 scaffolded fleet dir flips them into fleet mode**; on an
empty-fleet box the legacy behavior below runs unchanged until the fleet root is populated.

```bash
python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --status [--json]
```

- **Per-account grouping, pinned identity.** Dirs group by the identity in `assignments.json`.
  A `pending-login` row gets one `api/oauth/profile` probe with that dir's OWN access token at
  status/tick time; success pins the verified email permanently (never re-probed — the
  dead-token identity gate that once lost a chain is not reintroduced), failure leaves it
  pending and excluded from grouping.
- **Quota: live or cached-with-age, never blind.** Usage is read once per account with the
  freshest dir's token — live only while that credential file's mtime is <8h old (the CLI
  rewrites it on every refresh, so mtime IS last-use). Otherwise the cached last-known row
  rides with its age (`STALE — cached Nh ago`), else an honest "no quota reading yet".
- `--status --json` carries a `"pause"` field (`null` running · `"marker"` operator-paused ·
  `"error"` pause state unreadable) plus `fleet_warnings` — machine consumers must not read a
  healthy-looking payload while switching is withheld or a carrier is missing.

The `*/5` cron tick in fleet mode is telemetry + advisories ONLY — there is **structurally no
successor logic** (no pick, no switch, no install — not paused, ABSENT):

- ≥`ROTATE_DRAIN_THRESHOLD` (default 85) on either window fires ONE advisory Telegram per
  account per 24h (dedupe stamp; a future-dated stamp is invalid and fires now — the clock-skew
  clamp), plus graceful-drain fabrik-mail routed to the repos mapped to that account's slugs
  (slug → `/opt/<slug>`; hub role slugs `fabrik-*` → the `fabrik` mailbox; slugs with no repo
  are skipped).
- A walled account's windows pause until their reset and resume on it; the other accounts'
  windows are untouched.

### The carrier-presence + occupancy monitor

The binding fails OPEN and invisibly — a session whose carrier went missing just quietly
rejoins the shared `~/.claude` chain. `--status` (text and JSON) therefore WARNs, by name:

- Every mapped project (rows with a `project` binding) is checked for its
  `settings.local.json` carrier: missing, unreadable, or lacking either variable → a named
  warning. Hub role dirs and headless callers carry the env on the launch line, not a file, so
  they are not carrier-checked.
- **Occupancy:** the monitor counts LIVE Claude CLI processes (keyed on argv basename —
  `claude`, or a `node`/`bun` launcher of it, never a substring match) whose
  `/proc/<pid>/environ` carries **no non-empty `CLAUDE_CONFIG_DIR`** — those processes ARE on
  the shared chain. Above `CLAUDE_FLEET_OCCUPANCY_MAX` (default 3: the operator's ad-hoc runs
  plus a straggler) it warns that windows have silently rejoined. Fail-soft: when no process
  can be inspected the count reads as unknown, never as a false all-clear. (An open-handle
  count could not work: the CLI
  opens and closes the credential file per read, so handle counts sit at 0.)

## Keepalive — the only recurring duty, automated

```bash
python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --keepalive
```

A chain idle ~30 days lapses. The weekly cron pings every fleet dir whose `.credentials.json`
**mtime** (never content — the keepalive path reads no credential bytes) is >7 days old: one
in-place `claude -p ping` bound to that dir's own env (`CLAUDE_CONFIG_DIR` +
`CLAUDE_QUOTA_HOME` → the dir itself), so the CLI rolls THIS dir's own chain — the sole-owner
path, not the retired temp-dir-copy `--touch` pattern. A future-skewed mtime counts as DUE
(a spurious ping is harmless; a missed one risks the lapse); dirs with no credentials yet are
skipped as pending-login. rc 0 when every stale dir refreshed, rc 1 + a Telegram alert (via the
sound mesh's `mesh-notify`) on any failed ping. Per-ping timeout: `KEEPALIVE_TIMEOUT`
(default 150s).

## Recovery rules

- **Reload, never login.** A window that lost auth mid-session holds a superseded pair in
  memory; the dir's on-disk chain is current. Reload the window (VS Code "Developer: Reload
  Window" / reopen the terminal session) — it re-reads the dir. `/login` is only ever for a dir
  whose chain itself lapsed (keepalive alert) or a brand-new dir.
- **DR rule: a fleet-dir restore = ONE `/login` in that dir, never a credentials-file
  restore.** A stored chain is consumed the moment the live one rolls — restoring credential
  bytes installs a spent single-use refresh token. Backups of fleet dirs exclude
  `.credentials.json` by design (the successor plan's DR step); everything else (`.claude.json`,
  links) restores normally, then one login re-creates the chain.

## Pause semantics — `--pause-switch` / `--resume-switch`

The `switch-paused` marker (`~/.claude/state/switch-paused`) gates
`_rotate_active_account` — the single choke point behind every automated credential swap on
this box:

- `run_claude`'s usage-limit/401 rotation retry (the CLI passthrough used by the keepalive shim
  and sysadmin callers) and `--next` both route through it, so both inherit the gate.
- `--switch <name>` does NOT route through the gate — it is the deliberate manual escape hatch.
- The gate is checked once, at entry: **an install already past the gate completes** — the
  marker gates NEW installs, it never aborts one in flight.
- The pause state is tri-state: absent (running) · `marker` (operator pause; the tick prints
  the withheld successor instead of installing, telemetry/keep-warm/drain warnings stay armed)
  · `error` (the state dir cannot be READ → **fail closed**, nothing installs, but alerting
  stays armed: an all-credentials-dead 401 alert still fires and names the fail-closed refusal.
  With the operator's marker set, that all-dead alert is suppressed — the operator is at the
  keyboard and owns the pool).
- **A broken state dir → rc 1:** `--pause-switch` / `--resume-switch` report the unwritable
  state dir and exit 1 rather than pretending; rotation is already refusing fail-closed while
  the dir is unreadable.
- `--status --json` reports the state in its `"pause"` field; the legacy text view shows a `⏸`
  banner while paused.

## Cron — the installed lines

```cron
*/5 * * * * flock -n $HOME/.claude/state/rotate.lock python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --tick >> $HOME/.claude/rotate-tick.log 2>&1
20 6 * * 1 python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --keepalive >> $HOME/.claude/keepalive.log 2>&1
```

The hourly `--drift-check` cron and the SessionStart drift-check hook are gone — a settings
symlink would have run the drift-check from every fleet dir against its hardcoded `~/.claude`
paths, re-creating the exact capture/retarget hazard this design retires.

## Rollout runbook

### M2 — the hub's per-window env recipe

The hub's 3 role windows share `/opt/fabrik` as cwd, so a cwd-keyed carrier cannot split them —
and a settings `env` entry OVERRIDES each window's own environment, which would collapse all
three onto ONE dir and ONE chain. **The hub gets NO carrier; `--new-dir` refuses
`--project /opt/fabrik`.** Create the role dirs without `--project`:

```bash
python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --new-dir fabrik-infra <account-email>
python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --new-dir fabrik-fleet <account-email>
python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --new-dir fabrik-intel <account-email>
```

Then each hub window carries the two variables in its own environment, set beside the existing
per-window `CLAUDE_AGENT`:

```bash
export CLAUDE_CONFIG_DIR="$HOME/.claude-fleet/fabrik-infra"
export CLAUDE_QUOTA_HOME="$HOME/.claude-fleet/fabrik-infra"
export CLAUDE_AGENT=infra
```

Set them where the window already gets its `CLAUDE_AGENT` — the per-window launch profile /
rc file, not a one-off terminal `export`, which dies with the session and silently lands the
next session back on `~/.claude`. A hub terminal opened WITHOUT the env lands on `~/.claude`
(the ad-hoc default) — visible in the occupancy monitor, never a corruption.

### M3 — the staged login round (the last logins ever)

Batches of **3–4 dirs per account per day**, ~15 dirs total, so an upstream concurrent-grant
cap surfaces on a small batch instead of the whole fleet:

1. Scaffold the day's dirs: `--new-dir <slug> <account-email> --project /opt/<repo>` for
   project windows (hub role dirs per M2; headless dirs without `--project`).
2. ONE `/login` in each new dir's context: for a project window, open Claude in that repo (the
   carrier routes it — it prompts because the dir is empty) and log in as the dir's account.
   For a dir with no carrier:

   ```bash
   CLAUDE_CONFIG_DIR="$HOME/.claude-fleet/<slug>" CLAUDE_QUOTA_HOME="$HOME/.claude-fleet/<slug>" claude
   ```

3. Verify: `--status` lists the new dirs (`pending-login` until first use pins the identity,
   then grouped under their verified account).
4. **Watch 24h before the next batch.** ⚠️ **ABORT signal — grant eviction:** a relogin prompt
   appearing in an UNTOUCHED dir (one that was already working and is not part of today's
   batch) means the provider evicted an existing grant when a new one was added. Stop the
   batch, regroup to FEWER dirs per account (per-account dirs still beat today's single shared
   file), and re-plan the remainder.

## Legacy: the shared-file rotation pool — live until retirement

The modes coexist, keyed on the fleet root: with it empty, EVERYTHING below is the live
behavior; once it holds dirs, `--status`/`--tick` flip to the fleet view and this machinery
governs only `~/.claude` itself — which stays the ad-hoc default for unmapped one-off runs
until the M5 thinning. The shared-file machinery operates
ONE `~/.claude/.credentials.json` swapped between per-account snapshot stores
(`~/.claude/manager-accounts/<name>/`). It retires at the M4 sweep — do not build on it.

- `--list` · `--switch <name>` · `--next` — snapshot management; `--switch` swaps the live file
  in place (running sessions lazily re-read on 401/expiry; never `pkill`, never `/logout`).
- Legacy `--status` — per-store quota table; parked stores whose access token aged out show
  "parked — quota unknown until used (refresh token valid)" (the fleet view retires exactly
  this blindness).
- Legacy tick — at `ROTATE_THRESHOLD` (default 95) on either window it switches to the
  perishable-first successor (soonest weekly reset) under a 30-minute dwell; with no
  installable sibling at the drain threshold it broadcasts the graceful-drain fabrik-mail +
  one Telegram (24h suppress); keeps parked snapshots warm (expiry-keyed refresh).
- `--capture-current` · `--drift-check` — snapshot the live chain into the active store
  (identity-gated). The drift-check's cron/hook triggers are removed; the flag remains
  invocable by hand until the sweep.
- `--touch [<account>]` — the temp-dir-copy refresh for parked stores; superseded by
  `--keepalive`'s in-place path.
- Safety invariants: every credential write is atomic (tmp + rename) under the shared rotation
  flock with a `.prev` rolling backup; nothing is filed without positive identity
  verification; the tick never sends process signals.
- Audit trail: `~/.claude/state/rotate-ledger.jsonl` (size-capped rotation).

## Successor plan (named, NOT done)

The retirement is a follow-up plan, not shipped state:

- **M4 retirement sweep** — retire the switch/capture/touch/drift machinery + the
  `manager-accounts` stores (archived to the DR store first), sweeping every consumer:
  `capture-watch.sh`, the removed drift-check triggers' remnants, `claude-mesh-test.sh`
  fixtures asserting retired argv, the cost-model repoints (`claude_p_cost.py` /
  `derive_cost.py` read `_MANAGER_ACCOUNTS` — repoint before archiving),
  `export_claude_state.sh`, `bootstrap-vps.sh`, and the aro-wake twin. The
  `claude-sound.sh` `--switch`/`--next` mesh legs are a **named, owned step** in that sweep —
  the sound system is never edited as a side effect. DR: `dr_claude_backup.sh` gains the
  fleet-root backup **excluding `.credentials.json`** (the DR rule above).
- **M5 thinning** — after M4, move the remaining unmapped `~/.claude` occupants (one-off
  runs, stragglers the occupancy monitor names) onto fleet dirs until the shared chain has no
  routine users left.
- **VPS follow-up** (separate spec, hard deadline **M4+30d**) — per-box dedicated logins,
  retiring the hourly snapshot shipping. Until it lands the VPSes keep working off the sync of
  the still-live `~/.claude`; the archived sibling stores stop rolling at M4 and lapse ~30
  days later — the follow-up lands inside that window or those accounts need one login each on
  the VPS side.

## Related

- `docs/superpowers/specs/2026-08-15-login-once-credentials-design.md` (the design + adversary
  findings + rejected alternatives: no login automation, no HTTP refresh, no per-account-only
  dirs)
- `docs/workstation/hooks-index.md` §2c (the cron tick row)
- `docs/reference/fabrik-mail.md` (the drain/advisory mail channel)
