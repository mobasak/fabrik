# Claude accounts — the pointer-rotation fleet (reference + runbook)

**What it is:** five Claude Max subscriptions (`ob@`, `can@`, `sarp@`, `mob@` — those three are
inbox-aliases of `ob@ocoron.com` — and `ozgurbasak@`, added 2026-09-06), each permanently logged in to its OWN config dir,
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
  ob/ can/ sarp/ mob/ ozgurbasak/   one per ACCOUNT — each holds its own .credentials.json, logged in ONCE
  active -> mob           the pointer every session follows (a relative symlink)
  assignments.json        slug → account, pinned identity
  caps.json               per-account weekly reserves, e.g. {"ob@ocoron.com": 90}
```

Fleet root override: `CLAUDE_FLEET_ROOT` (`_fleet_root`, `claude_rotate.py:1432`). Only
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

The `*/5` tick reads every account dir (five as of 2026-09-06 — it discovers them, nothing enumerates them), then decides (`_fleet_flip_leg`, `claude_rotate.py`):

- **Flip-away trigger:** the active account reaches `ROTATE_THRESHOLD` (default **98** since 2026-09-08 —
  operator rule, D-201: "we can switch a lot faster now so i want to utilize them better — switch as soon as
  it reaches 98%". This SUPERSEDES the 95 of 2026-09-03, which had itself replaced a 98 that lost the same
  day. The burst that beat 98 then is unchanged and still measurable in the last usable sample — 305
  inter-tick gaps, 2026-08-13..15: gap median 5.0 min / p90 5.0 / max 10.0, per-gap RISE median 0 points,
  p90 3, p99 35, so P(rise > 5) = 4.7% against P(rise > 2) = 21.7%, i.e. an account read AT the line walls
  roughly 4.6x more often at 98 than at 95. What changed is the COST of losing that race: the relief wake
  (D-177/D-178/D-180, 2026-09-07) holds a walled session and wakes it when relief lands instead of letting
  it die. ⚠️ Those numbers were unrefreshable when this was decided and are not any more: the FLEET tick never
  wrote the `{"event": "tick", "pct": …}` row the LEGACY tick did, so the samples stop dead on 2026-08-15 — the
  day this box moved to fleet mode. Restored in the same change (one row per tick, ACTIVE account, its SESSION
  window, graded by `test_the_fleet_tick_ledgers_the_active_session_reading`), so the next tuning has evidence
  rather than a three-week-old snapshot. ONE helper
  `_rotate_threshold()` feeds every call site, and `quota_dashboard.TRIGGER_THRESHOLD` is pinned equal to it
  by a grader) on either the 5-hour or the weekly window — **on the PROJECTED reading**
  (2026-09-03 19:50, D-103): each leg trips on reading + the burn since the previous tick, remembered per
  account + window in `~/.claude/state/tick-last-reading.json` (`_tick_burn`; same account, same window by
  reset epoch, memory ≤ 15 min, else 0). The tick had logged ob@ at 89 → 93 → 96 "below 98, no flip" and the
  next tick found the wall: at a 5-minute cadence and a 3–4% inter-tick burn no tick observes [98, 100), so a
  line checked every 5 minutes must be crossed BEFORE the wall. The no-flip line shows `(+N since last
  tick)`; a projected flip says so in its ledger line. **Latency:** the quota dashboard
  server probes every 20s and invokes `--tick` the moment the active account crosses the line (or is
  cap-walled), so a flip lands within ~20s of the crossing; the `*/5` cron tick is the backstop
  (`docs/workstation/quota-dashboard.md` § the rotation trigger). The **weekly** leg is governed by the account's `caps.json` cap when one exists
  (the cap IS the operator's weekly rule — a cap of 99 trips at 99, not at the session threshold) and by
  `ROTATE_THRESHOLD` otherwise; the 5-hour leg is never cap-gated.
- **Drain-band relief flip (D-171, 2026-09-06; hardened 2026-09-07):** a SECOND flip trigger, below the trip
  line. When the active account's hottest window is at/over `ROTATE_DRAIN_THRESHOLD` (default **85**) but not
  tripped, and a live-validated sibling is BELOW 85 on both windows (the strict-both-windows hysteresis that
  stops ping-pong), the tick flips to it — walking down the ranking past in-band candidates, dwell-exempt like
  a trip, ledgered with `kind: relief`. Born of the 23:01–23:17 incident: the hold lifted on ozgurbasak@'s
  reset while the pointer stayed on mob@ (93/97, cap 99) because only a trip moved it. Accepted cost: the
  85→cap weekly band of the account flipped away from is deferred, not spent. The board's fast path mirrors it
  (a `relief` trigger tier + the ghost return row, R6, 2026-09-07), so a weekly-driven relief lands within the
  20 s probe cadence like a trip.
- **URGENT drain at 90 with NO successor (operator rule 2026-09-03, `_urgent_drain_pct`, `ROTATE_URGENT_DRAIN_PCT`):**
  when the ACTIVE account's session is at/over **90** and `_validated_pick` finds no eligible sibling (every
  one session-exhausted, weekly-walled or cap-walled), the wall advisory fires EIGHT POINTS EARLY — five until
  2026-09-08, when D-201 moved the flip line 95 -> 98 and widened the gap; the runway a graceful stop needs, and
  the ordering (90 < the flip line) is the design rather than a coincidence, graded by
  `test_the_no_successor_mail_always_precedes_the_flip_line` — as one Telegram + one broadcast fabrik-mail to every mailbox repo, in the operator's
  words: **STOP YOUR WORK ASAP, GRACEFULLY, and HOOK YOURSELF TO RESUME 1 MINUTE AFTER the next account's
  session resets** — with that instant as local time, UTC and epoch, plus a copy-paste `sleep` line
  (`_next_session_relief`: the soonest 5h reset among siblings blocked only by their session; falls back to the
  soonest weekly reset when every sibling is weekly-blocked; skips stale past resets). Same latch and re-arm as
  the wall tier (one message per episode; re-armed the instant relief arrives). The quota board invokes the
  tick on this tier within one 20 s probe, on a cooldown of its own so it can never delay the flip tier.
- **Target — PERISHABLE-FIRST (operator rule 2026-09-02):** among accounts that are alive, not
  walled, not cap-walled, and not themselves already ≥ threshold on either window, the one whose
  **weekly reset is soonest** wins (quota about to refresh is the cheapest to burn); ties break
  to lower weekly, then lower session utilization; an unknown reset time sorts last. The same
  rule the reactive path (`_pick_successor`) always applied; the tick used to rank by headroom
  instead. The weekly reserves live in `caps.json` — **§ Per-account caps below; read the file
  or `--status`, never this page, for the numbers.** At weekly ≥ cap the account flips away
  whatever its session says.
  **A target must have 5h budget** (operator rule, same day): its session reading must be KNOWN and
  ≤ `ROTATE_TARGET_SESSION_MAX_PCT` (default = `ROTATE_DRAIN_THRESHOLD`, **85** — a target at or over the drain line would be flagged the moment it became active) — a weekly reading alone proves nothing about
  the session window, and a sibling near its own session wall would be flipped to and away from on
  the next tick. A cached standby whose 5h reset time has already passed is read as 0% (an idle
  account cannot burn fleet quota; the window rolled over — the board applies the same rule). A candidate ranked off
  a CACHED reading is live-probed once before it can become the pointer — **and when that probe
  fails, a reading younger than `ROTATE_CACHE_TRUST_S` (default: the refresh line `ROTATE_READING_MAX_AGE_S` **plus one tick of slack**, 3600 + 420 s — it used to EQUAL the refresh line, which left every reading untrusted between crossing the hour and the next tick's refresh; 2026-09-06) on a chain that passes the
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
- **Dwell:** 30 minutes between automatic flips (`ROTATE_DWELL_MIN`) — but **never on a trip** (operator
  directive 2026-09-03, D-104: a session wall stops every running agent at once, so a trip is a wall,
  never churn; on 2026-09-03 mob@ sat cap-walled with `flip to ob within dwell — holding` until the operator
  switched by hand). The tick's trip flips and the missing/dangling-pointer repair are dwell-exempt; churn is
  prevented where it belongs — the candidate predicate never targets a sibling at/over the threshold or
  without 5h budget. The dwell still bounds the legacy (non-fleet) tick.
- **No headroom anywhere:** nothing flips; ONE advisory per wall episode goes to Telegram AND
  broadcasts to every project mailbox ("reach a commit-and-push checkpoint") — it fires ONLY when
  the ACTIVE account is walled and this tick found no successor (`_fleet_active_wall_advisory`;
  a walled active with a headroom sibling is relieved by the same tick since trips are dwell-exempt). The same tick
  writes the `fleet-exhausted` stamp, and the synced PreToolUse hook `quota_stop.py` turns it
  into a GRACEFUL STOP that reaches every session mid-turn: work tools are held with one
  instruction (commit + push, close the run record, end the turn); reads, git, the record
  tools, `Monitor` and `TaskStop` stay open; the hold lifts the moment the tick clears the stamp (an
  unclearable stamp keeps the hold and wakes nobody — `_clear_stamp`) — and since 2026-09-07 (the
  RELIEF WAKE, plan `2026-09-07-plan-1-relief-wake`, D-177/D-178) the same unlink — the relief site and
  the transient-dwell site alike — writes `<lockdir>/<safe-sid>.holdlifted` (the lift epoch) for every
  session whose self-watch is ARMED (`_wake_held_sessions`: a held `selfwatch.lock`, the one decider
  `selfwatch_check.py` uses, vendored lockstep) and appends a `hold-lifted` ledger row with
  `reason` (`relief`/`dwell`; the helper's `no-reading` value is defensive only since D-180 — the tick keeps the stamp instead), `site` (which unlink fired) and `armed/dead/woken/pending/errors`; `pending` = an ARMED watch that never consumed the previous lift — a watch armed before the lift branch shipped (an old script in memory), healed only by ENDING that watch's Monitor (`TaskStop`, allowed under the hold — a plain re-arm exits at once as a duplicate while the old watch still holds the lock) and arming again. ⚠️ Until 2026-09-07 the Stop decider's 2-hour lock-dir prune deleted every self-watch's lock FILE (its mtime never changes), orphaning 25 of 30 watchers on this box — invisible to this census, and each re-arm the nag ordered died the same way two hours later; the prune now skips flock-held files and the watch exits when its lock file vanishes (harness W11); the self-watch consumes the file and prints the RESUME line naming
  the run record and thread anchors. A probe blackout (every window `None`) is NOT relief:
  since D-180 (2026-09-07, the plan's heavy review) the tick KEEPS the stamp and logs `stamp KEPT — no reading`; the
  hold stands until a reading says otherwise, so the one present→absent transition the wake fires on is never
  consumed blind (before D-180 the stamp went and every held session slept until the NEXT episode). A stamp the
  tick cannot unlink also keeps the hold and appends a `hold-stuck` ledger row. A lock the tick cannot probe is
  counted in `errors` and never aborts the census for the others. A session
  whose watch was NOT armed stays idle until the operator restarts it — which is why the hold's own
  denial text orders the arm (Monitor is allowed under the hold). Before 2026-09-02 the four broadcasts of the day
  were the picker bug (§ Target) talking, not real exhaustion. Work resumes
  as windows reset. **The latch has a THIRD re-arm: the promise coming due.** The message names a
  resume instant and tells every repo not to poll before it, so the `fleet-exhausted` stamp's
  CONTENT holds that epoch (`0` when none could be given) and `_promised_resume` re-arms the latch
  once it passes with the wall unbroken — the next message then carries the next time to try.
  Without it the fleet goes silent until the week-long re-arm: on 2026-09-04 one message at 20:55
  UTC named 21:31, nothing switched, and 47 "NO successor has headroom" ticks passed unannounced
  until the operator flipped the pointer by hand at 07:36. For the same reason the message says
  relief is EXPECTED, not promised — the rotation switches only if the named account really has
  headroom when its window turns. A stamp written before this field existed holds its own write
  time, which is never later than its mtime, so it migrates silently to the old behaviour.
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

⚠️ **The live values are the file, and this doc does not restate them** — deliberately, as of
2026-09-06. Read `cat ~/.claude-fleet/caps.json`, or `claude_rotate.py --status`, which prints
`(cap N)` on every account row (`claude_rotate.py:3636`). The caps are the operator's browser
reserve: they are edited by hand, take effect with no restart, and therefore change with no
commit and no reviewer. Both values this page used to name had drifted silently — `sarp` was
raised 90 → 95 on 2026-09-06 (D-150) and `ob` had moved 80 → 90 before that, with the prose left
untouched each time. A number copied out of a live JSON file into prose is stale from the day
after it is written.

At or above the cap the account is **cap-walled**: automated flips exclude it and `--status`
says so, reserving the remainder for the operator's own claude.ai browser use. `--switch` may
still target it deliberately. Keys are matched case-insensitively; a key matching no known
account warns ("cap inactive") rather than failing silently. The file is mirrored off-box by
`scripts/dr_claude_backup.sh` (D-150, 2026-09-06 — until then it had no backup at all, because
that script's fleet loop walks account *directories* and caps.json sits at the fleet root).

## `--status` — the board

**The picture (2026-09-07, operator directive "all agents should be able to reach/query the entire picture"):**
after the per-account lines, `--status` prints four more — `picture:` (the fleet-exhausted HOLD: none, or held
since when and the resume it promised), `queue:` (the rotation order: the active first, then eligible accounts in
the picker's own perishable-first order, then everyone else by when they RETURN — a cap-walled or weekly-exhausted
account at its weekly reset, a session-exhausted one at its 5h reset, the later of the two when both are spent),
`next relief:` (the account and instant the tick's own relief rule would name), `last flip:` (when, from → to, and
its `kind`: trip / relief / repair / dead-chain / switch). `--status --json` carries the same under `picture`
(`accounts[].state` ∈ active · eligible · session-exhausted · weekly-exhausted · cap-walled · over-threshold (under its cap but a window ≥ the picker's target line — kept active, refused as a target until that window resets) · unavailable (its `why` names the picker's reason: no credentialed dir, no reading, …), with
`why`, both percentages, both resets, `returns_at`, `in_drain_band`, `source`, `age_s`; plus `queue`, `next_relief`, `hold`,
`last_flip`, `thresholds`). It is a READ — the same verdict the picker applies, no probe, no side effect — so
any agent in any repo may run it as often as it likes: `python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --status`.

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

### `dispatch_headroom.py` — the seat budget a fan-out is allowed (D-189)

`python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py [--units <N> | --slices opus=<n>,sonnet=<n>,haiku=<n>] [--heavy] [--risky <R>] [--mechanical <M>] [--json]`
turns the `--status` picture into ONE number an agent dispatches: `SEATS = min(wanted, the CLI cap of 20,
box_cap, quota_cap)`. `wanted` sizes TWO ways. **Units-sized** (`--units <N>`, for a spec/plan grounding or
adjudication surface): every unit's angles cost a Sonnet breadth seat plus a Haiku mechanical seat, and every
risky unit costs an Opus authoritative seat too (at least one Opus seat total; D-191 — the box is the
ceiling, the units the partition; a 3-unit surface on an idle box is 7 seats), padded to the D-186/D-188
floor of three REAL seats when the surface has fewer angles than that (a one-unit judgement surface gets a
second breadth reader as its third seat). **Partitioned** (`--slices opus=<n>,sonnet=<n>,haiku=<n>`, the
orchestrator's own disjoint slices for a review loop): `wanted` is the slice counts SUMMED (Σ slices;
`opus=1,sonnet=5` sizes to 6, not "one seat per kind" — the DD2 floor, every non-empty kind keeps at least
its own seat, is satisfied BY CONSTRUCTION, since the partition already IS that seat count), NO floor
padding (the D-186/D-188 "three seats on different angles" floor is RETIRED for a review loop — the third
angle there is the orchestrator's execution of every candidate, not a third reader — and stays live only
for grounding/adjudication surfaces and `/fabrik-review-scoped`'s own one-unit duplicate-brief floor); a
partition with no risky unit still dispatches one Opus seat over its most consequential slice, carved OUT
of the Sonnet count, never added to it (the CLI accepts any partition, including one with no Opus slice at
all — it names the DD2 gap in a reason rather than inventing an Opus seat, since the carve-out is the
orchestrator's judgement call, not the script's). Kinds are exactly `opus`/`sonnet`/`haiku` (Fable is never
a finder, D2), every count must be `>= 0`, and no kind may be given twice (a repeated kind is refused
rather than silently overwritten — the same grammar underlies `--mix`, which refuses a repeated kind the
same way, e.g. `--mix haiku=7,haiku=7`). Any of the three violations refuses `--slices` (exit 2) before
anything runs; on `--mix` the same refusal lands after the box/quota probe (the fleet round-trip pays
before the error prints — the units path stays byte-identical, so this is not moved earlier).
`--slices` wins when both are given; `--units` is then optional and defaults to the slice count, so
`--slices … --units 0` still prints its real seat count rather than the "nothing to partition" message. A
zero-sum partition (`opus=0,sonnet=0`) is not refused — it prints `SEATS: 0` with a NAMED reason, never a
bare number with nothing for "see the reasons above" to point at.
Both modes trim cheapest angle first when a cap binds (Haiku first, then the extra Opus seats, then Sonnet — coverage over cost; D-192); `--mechanical <M>` is the number of
grep-able classes the surface has (units-sized mode only; default one per unit, 0 for a grounding/adjudication surface — a judgement has no mechanical angle; a
negative count is refused), a trimmed Haiku seat sweeps one class across every unit; never below the applicable floor unless a hard cap binds or the fleet HOLD is on (then 0); `--units 0` with no `--slices` is
nothing to partition and prints 0 with the reason. `--json` also carries `box_caps` (read-only + heavy from the one box probe) for callers like the board, plus `slices` (the parsed partition, or `null`) and `mix_by_slice` (the partition TRIMMED to the seat budget, independent of a `--mix` price override — `null` when `--slices` is not given). `quota_cap` drops to the
floor when the active account's hottest window is ≥85% or no standby account is eligible (`eligible` counts standbys; the active account is `state=active`) —
the same bands `core/62` § Dispatch economics names. `--heavy` is for seats whose TOOLS load the box
(pytest, builds, renders): a native seat lives inside its parent `claude` process, so only its
subprocesses count, bounded by `min(MemAvailable, CommitLimit − Committed_AS)` at 2 GB per heavy seat (1 GB read-only) and one core per seat over `load1`, minus the seats OTHER sessions DISPATCHED in the last 25 minutes (`command_run.py dispatch --seats <n>` — stamped before the seats go out, accumulated within the round, released at its close; the caller's own record is never subtracted; measured on 245 seat transcripts: median 550 s, p95 1354 s), never below the floor the box has room for — this box bound is driven by BOX capacity alone and stays live in both modes. Every probe fails
soft and prints its reason with the floor, never a silent 20. It also prices the mix per D-190 — haiku 1× · sonnet 2× · opus 5× · fable 10× — for the mix it chose (`--units 3` → `{opus: 1, sonnet: 3, haiku: 3}`, `COST: 14 haiku-units`; `--slices opus=1,sonnet=1` → `COST: 7 haiku-units`) or one you pass (`--mix opus=1,sonnet=5` → 15), with the Fable adjudicator (10) printed beside the total, never inside it. Tests: `tests/sysadmin/test_dispatch_headroom.py`.

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

## Re-login — the only recurring duty, monthly, per account

A refresh chain runs **~30 days from its `/login` and nothing extends it** — not a claude turn,
not a `claude -p ping`, not the tick's own refresh. Measured 2026-09-12: mob@'s chain was
refreshed at 14:48 and its `refreshTokenExpiresAt` did not move; ob@ lapsed at its stored expiry
(12:28) while it was the ACTIVE account serving a session every ten minutes. When a chain lapses
the tool refuses to `--switch` onto it (`_stale_snapshot_reason`) and the dashboard shows
`Switch failed (502)`; when it is the only account with headroom, the fleet HOLD stays on.

The duty is one `/login` per account per month, in THAT account's dir, with the browser signed in
as that account (or a private window). Each block writes only its own dir; the active pointer is
a symlink to a slug dir, so a login in `ob` cannot touch `sarp`:

```bash
CLAUDE_CONFIG_DIR="$HOME/.claude-fleet/<slug>" CLAUDE_QUOTA_HOME="$HOME/.claude-fleet/<slug>" claude
/login        # as <slug>@ocoron.com
/exit
```

Re-login the ACTIVE account only after switching away (a live session reads that file when it
refreshes). Never `CLAUDE_ROTATE_ALLOW_STALE=1`: it lands the fleet on a token that dies at the
access expiry with nothing to renew it.

**How the tool tells you in time.** `--status` and the tick print the chain warning inside 5 days
of expiry (`_CHAIN_EXPIRY_WARN_S`) WITH the re-login line above, and the tick pushes it once per
chain (mesh-notify) inside 3 days (`_CHAIN_PUSH_S`; stamp `~/.claude/state/fleet-chain-push-<email>`
holds the expiry epoch, so a re-minted chain re-arms by itself). The old `--keepalive` ping is
RETIRED (2026-09-12): its premise was false and, keyed on a credential mtime the tick renews
daily, it pinged nothing in three weeks of runs (`~/.claude/keepalive.log`). The flag is kept as a
no-op that prints why (rc 0), so the cron line below can be deleted at leisure — crontab edits are
the operator's.

## Recovery rules

- **Reload, never login.** A window that lost auth mid-session holds a superseded pair in
  memory while the dir's on-disk chain is current. Reload the window — `/login` is only for a
  dir whose chain itself lapsed (the tick's 5-day warning or 3-day push) or a brand-new dir.
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
20 6 * * 1 python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --keepalive >> $HOME/.claude/keepalive.log 2>&1   # RETIRED 2026-09-12 (a no-op that says why) — delete when convenient
@reboot sleep 20 && /usr/bin/python3 /opt/fabrik/scripts/sysadmin/quota_dashboard.py --ensure >> $HOME/.claude/quota-dashboard.log 2>&1
*/10 * * * * /usr/bin/python3 /opt/fabrik/scripts/sysadmin/quota_dashboard.py --ensure >> $HOME/.claude/quota-dashboard.log 2>&1
```

The `flock -n $HOME/.claude/state/rotate.lock` wrapper is load-bearing, not tidiness: the relief wake fires on the stamp's exists→unlink TRANSITION, and that is single-fire only because two ticks never overlap — a hand-run `--tick` must use the same wrapper (`flock -n ~/.claude/state/rotate.lock python3 scripts/sysadmin/claude_rotate.py --tick`), or a hand tick racing the cron one can wake every pane twice.

The hourly `--drift-check` cron and the SessionStart drift-check hook are gone — a settings
symlink would have run the drift-check from every fleet dir against its hardcoded `~/.claude`
paths, re-creating the capture/retarget hazard this design retires.

**The refresh-ping budget is spent on the STALEST reading, never by alphabet (`_ping_slots`).**
A reading that falls behind `ROTATE_READING_MAX_AGE_S` (1h) is refreshed by one `claude -p ping`
against that account's own dir, capped at `ROTATE_REFRESH_MAX_PER_RUN` (3) per tick. That budget
used to be spent inside `for email in sorted(groups)`, so a fleet with MORE stale accounts than
budget starved whichever account sorted last — deterministically, every run, for ever. Measured on
the 2026-09-04 freeze: four accounts, budget 3, and `sarp@` (last in sort) reached a 405-minute
reading while the other three were re-pinged each tick. `_validated_pick` refuses any cache past
`ROTATE_CACHE_TRUST_S` (60m), so the one account that HAD headroom — 30% on its first live reading after the operator switched
to it by hand — was structurally invisible to the picker, and the fleet sat walled for 10h41m. The
slots are therefore allocated once per run, oldest reading first, which cannot starve: an account
dropped this run is the stalest next run and outranks the ones just served. The same three gates
still bind (a credentialed chain too old to answer a live probe, a reading at/past the age line, its
own per-account stamp elapsed), so no ping is issued that the old code would not have issued — only
the ORDER of spending changed. Guarded by `tests/test_claude_fleet.py::test_the_ping_budget_serves_*`
and `::test_a_skipped_account_is_served_on_the_next_run_*`.

**Cron PATH — why the pings resolve `claude` without a `PATH=` line.** Cron runs with a minimal
`PATH` (`/usr/bin:/bin`) that excludes `~/.local/bin`, where the `claude` CLI installs. Every
`claude -p ping` (the tick's stale-reading refresh) therefore prepends
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
`OAUTH_GET_TIMEOUT_S` (default **8s**) and `OAUTH_GET_ATTEMPTS` (default **2**) — PER HOST, and there
are two hosts. ONE call is inside the 60s cap; the AGGREGATE is not: the live fleet path makes
`usage` + an hourly `profile` call per fresh account with no budget across the loop, so any
sustained slowness breaches the cap. The derived figures live in one place — the STRATEGIC_BACKLOG
row `claude_rotate.py --status --json can exceed …` (2026-09-05); this sentence used to claim two
attempts fit the budget. A sustained outage still falls soft to the last-good
reading (the dashboard's red banner) — no retry conjures a working network. Regression-guarded
in `tests/test_claude_fleet.py` (`test_oauth_get_*`).

## Runbook

### The logins (chains run ~30 days from each /login — § Re-login is the monthly duty)

Every account is logged in once and never again. The fifth, `ozgurbasak` (2026-09-06), was
scaffolded with `--new-dir ozgurbasak ozgurbasak@ocoron.com --from ob` — **`--from` matters**:
with no source the seed falls back to `~/.claude.json`, the stale post-migration leftover, and
the new dir would inherit neither the current MCP roster nor the 58 trusted repos (a `claude -p`
coder there would refuse every command). Adding or re-homing an account is:

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
- Legacy tick — `ROTATE_THRESHOLD` (98) switching with a 30-minute dwell, graceful-drain mail
  + one Telegram (24h suppress), keep-warm for parked snapshots.
- `--capture-current` · `--drift-check` — snapshot the live chain (identity-gated); the cron
  and hook triggers are removed, the flags remain invocable by hand until the sweep.
- `--touch [<account>]` — the temp-dir-copy refresh; superseded by `--keepalive`'s in-place path, itself retired 2026-09-12 (a ping never extends a chain — § Re-login). ⚠️ Never refresh on a COPY of a credential file: refresh tokens are single-use, so the copy consumes the live token and the real dir dies on its next refresh (mob@, 2026-09-12).
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

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/aro-wake/claude_rotate.py`
- `scripts/sysadmin/claude_rotate.py`
- `scripts/sysadmin/dispatch_headroom.py`
- `scripts/sysadmin/quota_dashboard.py`
<!-- END related-scripts -->
