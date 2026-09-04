# Claude quota dashboard (box-local, `localhost:5051`)

**What it is:** the account-quota board rendered for a browser tab you leave open — every
Claude account's session (5h) and weekly headroom, reset times, the active pointer, caps and
warnings. It is a VIEW over `claude_rotate.py --status --json`; it owns no state, decides
nothing, and never touches a credential file.

**Open it:** <http://localhost:5051/> (works from Windows too — WSL forwards loopback).

Tool: `scripts/sysadmin/quota_dashboard.py` · Output: `~/.claude/quota-dashboard/`
(`index.html` + `quota.json`) · Log: `~/.claude/quota-dashboard.log`

## How it stays current — the server probes on its own cadence (operator rule 2026-09-03)

**The server probes every `QUOTA_DASH_PROBE_INTERVAL_S` (default 20s) whether or not a page is open**, on a
thread `serve()` starts (`_start_probe_loop`), and after every probe hands the fresh payload to the
rotation trigger (below). The page's health-gated reloader re-fetches every `QUOTA_DASH_REFRESH_S`
(default 20s), so what you see is at most ~20s old. The on-view floor (`QUOTA_DASH_MAX_AGE_S`, now 20s)
remains only as the fallback for a view that lands before the first loop iteration. This supersedes the
2026-08-18 "probe only when someone is looking" design: the operator wants the board — and the rotation
decision it feeds — current at 20s granularity, and four usage probes every 20s is the price.

**The rotation trigger — the fast path to a flip.** After each probe, if the ACTIVE account's 5h window is
at/over `ROTATE_THRESHOLD` (default **95**, the tick's own default) or the account is cap-walled — or, on the
URGENT-DRAIN tier, at/over `ROTATE_URGENT_DRAIN_PCT` (default **90**: the tick then sends the operator's
"stop gracefully, hook to the next reset" mail if NO successor exists; this tier has its OWN cooldown so a drain
tick at 90 can never delay the flip tick at 95) — or, while
the probe is BLIND (the payload carries `probe_failed`), at/over the drain line (`BLIND_TRIGGER_THRESHOLD`,
`ROTATE_DRAIN_THRESHOLD` = 85; 2026-09-03 20:10: seven 60 s probe timeouts in a row hid ob@'s 96 → 100 and
the trigger only ever saw the last good 96) — the
server invokes `claude_rotate.py --tick` at once (`_maybe_trigger_rotation`; once per
`QUOTA_DASH_TRIGGER_COOLDOWN_S`, default 120s) — on its own thread (a slow tick never stalls the probes)
and under the cron's own lock (`flock -n ~/.claude/state/rotate.lock`, `QUOTA_DASH_ROTATE_LOCK`), so the
board's tick and a cron tick never decide at once; while a cron tick holds the lock the board's is skipped.
`generate()` is serialized: the loop, a view and a switch can never run two probes concurrently. The tick keeps every safety it has — dwell, pause,
successor validation, its own state lock — so this shortens the latency from ≤5 minutes (the `*/5` cron
tick, which stays as the backstop) to ≤ the probe interval. The invocation and the tick's exit line are
written to the dashboard log.

**Row order = rotation order (operator rule 2026-09-03).** The active account is the first row; then the
standby the tick would pick NEXT, then the one after, for any number of accounts (`_display_order`, the
read-only mirror of the tick's `_pick_flip_target`: eligible = not cap-walled, no window ≥100, a known 5h
reading ≤ the target budget and below the flip threshold; ranked soonest weekly reset first, then lower
weekly, then lower session). Ineligible accounts (cap-walled, walled, no reading, no 5h budget) follow by
the same key. Each row carries its rank badge — `ACTIVE`, `NEXT`, `#3 in line`, … or `not eligible`.

The older design's reasoning, kept for the record:

- `--status --json` makes **live API probes** for fresh-token dirs. A `*/5` regeneration cron
  would probe forever whether or not anyone is looking; a self-refreshing tab would probe on
  every reload. On-demand + a floor gives a current page for a viewer, **zero** probe cost
  when the tab is closed, and refresh-spamming cannot multiply probe volume.
- The rendered page always states the age of its own data and, per account, whether the
  reading is live or `cached Nh ago` — a stale render is visible, never silent.
- **A pointer flip beats the floor.** Every view compares the live `active` symlink with the
  `active` of the last render; when they differ, the page regenerates synchronously ONCE (bounded
  by the probe timeout) so the very next view shows the new account. Measured 2026-09-02 before
  this: a `--switch` at 14:36 left the board saying the OLD account for up to floor + reload.
- A failed probe does **not** blank the page: it renders the last good payload behind a red
  "live probe failed" banner (`quota.json` is the fallback store, and the fallback carries `probe_failed`
  so the rotation trigger lowers its bar — see above). Transient network blips are
  first **retried at the HTTP layer** (`_oauth_get`, `OAUTH_GET_ATTEMPTS`/`OAUTH_GET_TIMEOUT_S`
  — see `claude-account-rotation.md` § Transient-blip resilience) before this fallback triggers,
  so a single stalled call under a flaky VPN no longer trips the 60s cap
  (`QUOTA_DASH_PROBE_TIMEOUT_S`).
- **Idle accounts show `cached Nh ago` by design** — `--status` (what this shells) is a fast,
  ping-free read; only the *active* dir's fresh token is probed live. **Idle-cache freshness is
  the `*/5` rotation tick's job**, not the dashboard's. So if idle ages climb without bound
  (e.g. past 85h — observed 2026-08-22), the tick is either not running (check `crontab -l`) or
  its refresh-ping is failing to resolve `claude` under cron's PATH — see
  `claude-account-rotation.md` § Cron PATH.

## Reading the board

| Element | Meaning |
|---|---|
| `ACTIVE` badge + highlighted row | the account `~/.claude-fleet/active` points at — what every session uses |
| `N% left` + bar | **remaining** headroom (the CLI prints *used*; this prints what is left) |
| green / amber / red | >25% · 6–25% · ≤5% remaining |
| `cap N%` badge | a `caps.json` reserve exists for this account |
| `RESERVED — fleet excluded` | weekly ≥ its cap: automated flips skip it, the remainder is the operator's (browser use). `--switch` may still target it, deliberately |
| `WALLED` | weekly ≥ 100%: unusable until its reset |
| `cached Nh ago` | the account is idle, so its token is stale; the reading is the last known one with its age |
| `idle` in the session cell | the account is NOT the active pointer, so no session can be burning its quota — its 5-hour window is empty by construction, not by measurement. Shown when the cached reading is older than the window itself, **or when the reading's own reset time has already passed** (e.g. a ~47h cache of a 7-day window whose weekly reset date is now in the past — the window has rolled over even though the cache is younger than the full window). On a capped account it adds "browser use is not visible here", because that usage is the one thing no probe of ours can see |
| `unknown` in the session cell | the ACTIVE account with a reading older than its 5-hour window — it CAN be burning quota, so nothing is derivable and no number is shown; it re-reads on next use |
| `Fable 5 weekly remaining` column | Fable-5's separate weekly limit, its own 4th column with the same remaining-framing as Weekly (`N% left` + bar + `used% · resets`). Read from the usage payload's `limits` array — a `weekly_scoped` entry whose `scope.model.display_name == "Fable"` (it has **no** top-level window key, the reason an earlier top-level-only scan missed it, 2026-08-22). An account with no Fable reading yet (idle, access token unrefreshed) shows `no reading` until the tick re-probes it. Undocumented always-0 codename windows (`nimbus_quill`, …) are not surfaced |
| Warnings section | the same `fleet_warnings` the CLI prints (carrier/occupancy/cap/identity-mismatch) |
| `OpenRouter pool` banner | the metered pool's balance — **the fleet's other quota**, and until 2026-09-04 nothing on this box watched it. Shown on the **Quota** tab AND the **External services** tab, because OpenRouter is an external service before it is a quota and that page already lists it as a paid provider with an unfilled `credit` field — the operator looked for it there first, correctly. Green above `POOL_CREDITS_WARN_USD`, amber at or below it, red at zero with what the operator will actually see (`every fanout() returns HTTP 402 with no output and no spend`). Absent entirely when no key is configured. A balance served past its TTL says `endpoint unreachable` with its age rather than blanking — the same stale-beats-blank rule as the account rows |

| `switch →` button | on every row that is NOT the active pointer: one click flips the fleet to that account NOW — the same manual flip as `--switch <slug>` (pause-, dwell- and cap-exempt), confirmed in-page first; every session bound to the pointer (`CLAUDE_CONFIG_DIR` → the `active` symlink, § How a session binds to the pointer in `claude-account-rotation.md`) follows it without a restart. The active row carries no button (nothing to rotate to) |

Rows sort by weekly headroom, so the fleet's next flip target is the top eligible row.

### The OpenRouter pool banner (2026-09-04)

The board watches Claude account quota. It did not watch the **metered pool** — and on 2026-09-04
the pool ran to **-$0.0015 of $225** with nothing on the box aware of it. Three repos found out by
hitting HTTP 402 mid-run: one lost 24 grounder units, another's closing review sweep fell back to a
lane that records nothing to the flywheel, and the operator learned of it from a mail rather than a
screen. The board already polls every 20s and the key was already on disk, so the balance was one
GET away.

It is a **level, not a projection**. HTTP 402 "Insufficient credits" is issued on balance, so the
number is the direct signal rather than a proxy for one. No runway is estimated here: the burn RATE
lives in the flywheel's Postgres rows (intel's beat), and a days-remaining figure this file cannot
defend is worse than none.

It renders in TWO panes — Quota and External services. Not duplication for its own sake: the
external-services page lists OpenRouter as a paid provider whose `credit` column nothing fills, so
"is my third-party spend OK" is a question people take to that tab. The operator went straight to
`#external` looking for this banner on the day it shipped.

Three properties worth knowing:

- **Off the critical path.** The GET runs in its own daemon thread on the probe loop's cadence,
  never inside `_gen_lock` and never on a page load. The first cut fetched inline and this repo's
  own cadence tests caught it — an inline fetch puts a third-party endpoint on the board's critical
  path, the shape of the 2026-08-18 hang where a stalled probe made every page load sit for its full
  timeout and the operator read the dashboard as "not reachable". It also took the dashboard suite
  from 9.9s to 38.6s, which is what surfaced it.
- **The drain advisory is latched.** One mesh-notify per drain episode, re-armed the instant the
  balance recovers — the same rule as the fleet wall advisory, for the same reason: an alert that
  repeats every 20s is an alert everyone filters, and a latch with no re-arm goes silent through the
  next incident.
- **Unknown is silence.** No key, or an unreachable endpoint with no cached balance, renders nothing
  and alerts nothing. A box without the pool configured looks exactly as it did before.

### The Commands tab (2026-09-03)

The page has three tabs. **Quota** (default) is the board above. **Commands** lists every `/fabrik-*`
command in pipeline order — `#`, command, stage badge, purpose, when to use, skip when, next — and
none of it is typed into the dashboard: each row is parsed live from the command's own frontmatter
`description:` under `commands/_sources/` (purpose = the text before `TRIGGER —`; when = the
TRIGGER clause; skip = the `SKIP:` clause; stage = `Stage:`), and the successor comes from the
assembler's `NEXT` map (`commands/assemble_commands.py`). The one hand-held fact is
`PIPELINE_ORDER` in `quota_dashboard.py` (CLAUDE.md § Pipeline: stages, then gates, then
utilities); a test refuses a source with no slot and a slot with no source, so it cannot drift from
the corpus silently. Rows are cached on the sources' mtimes. The chosen tab lives in the URL hash
(`#commands`), so the 20-second reload lands on the same tab.

### The External services tab (2026-09-03)

**External services** embeds the fleet's external-services & credentials inventory — the static
`external-services-dashboard.html` at the repo root that infra's daily chain regenerates
(`scripts/gen_dashboard.py`, run by `scripts/external_services_chain.sh` under the 06:00 cron; see
`docs/reference/external-services-registry.md`). The board only SERVES that file on
`/external-services.html` (byte-for-byte, never cached, 404 while it has not been generated) and shows
it in a same-origin iframe whose `src` is set the first time the tab is opened, so the 20-second reload
of the Quota tab never re-downloads it. The line above the frame stamps the file's age from its mtime —
the chain's liveness contract is "mtime ≤ 30 h", so a stale stamp here is the same signal
`liveness_audit.py` raises. Override the file's location with `QUOTA_DASH_EXT_SERVICES`. Tab hash:
`#external`.

## Endpoints

| Path | Serves |
|---|---|
| `/` | the dashboard (regenerates if the render is older than the floor) |
| `/quota.json` | the raw `--status --json` payload behind the page |
| `/health` | `ok` — liveness for the keepalive |
| `POST /switch` | body `{"account": "<slug>"}` + the `X-Quota-Dash` header → shells `claude_rotate.py --switch <slug>`, re-renders synchronously, answers `{ok, output}` (200); every outcome is one line in `~/.claude/quota-dashboard.log` (`POST /switch 'can' -> 200 in 3.2s: …`) — a click that "did not work" now leaves its trace · `{ok:false, error}` — 403 without the header, 400 for a slug the board's last payload does not list, 502 when the CLI refuses (its stderr is the error). The custom header is the CSRF story: a cross-origin page cannot add one without a preflight this server never answers |

## Lifecycle

Self-healing, no systemd (WSL has no user bus). Two crontab lines:

```cron
@reboot sleep 20 && /usr/bin/python3 /opt/fabrik/scripts/sysadmin/quota_dashboard.py --ensure >> $HOME/.claude/quota-dashboard.log 2>&1
*/10 * * * * /usr/bin/python3 /opt/fabrik/scripts/sysadmin/quota_dashboard.py --ensure >> $HOME/.claude/quota-dashboard.log 2>&1
```

`--ensure` demands a real HTTP `ok` from `/health` (5s, `QUOTA_DASH_ENSURE_TIMEOUT_S`): a healthy
server makes the 10-minute line a no-op; a dead port respawns; and a WEDGED server — one that
accepts connections but never answers — is killed (only the PID holding our port, only after the
probe fails) and respawned. Before 2026-09-02 a connect alone counted as alive, so a wedged server
stayed wedged for as long as the box was up. Worst-case gap is one cron interval; tighten the
`*/10` to `*/2` if a two-minute hole matters to you (crontab is the operator's file).

Modes: `--serve` (foreground server) · `--ensure` (start if down) · `--once` (regenerate the
files and exit — useful for a scripted refresh without a browser).

## Configuration (all env, all defaulted)

| Variable | Default | Purpose |
|---|---|---|
| `QUOTA_DASH_PORT` | `5051` | listen port (PORTS.md: WSL Python range) |
| `QUOTA_DASH_HOST` | `127.0.0.1` | bind address — loopback by design |
| `QUOTA_DASH_MAX_AGE_S` | `20` | regeneration floor (probe-volume bound) |
| `QUOTA_DASH_REFRESH_S` | `20` | the page's own meta-refresh interval |
| `QUOTA_DASH_PROBE_INTERVAL_S` | `20` | the server's own probe cadence, viewer or not — a PERIOD, not a pause after each probe |
| `QUOTA_DASH_OUT_DIR` | `~/.claude/quota-dashboard` | render output |
| `QUOTA_DASH_ROTATE_CLI` | `/opt/fabrik/scripts/sysadmin/claude_rotate.py` | the CLI it shells |
| `QUOTA_DASH_PROBE_TIMEOUT_S` | `60` | per-probe subprocess timeout |
| `QUOTA_DASH_SWITCH_TIMEOUT_S` | `90` | `POST /switch` subprocess timeout (the CLI probes the target before flipping) |
| `QUOTA_DASH_SOCKET_TIMEOUT_S` | `15` | per-connection socket timeout — a client that under-sends its declared body is dropped, never parked |
| `QUOTA_DASH_POINTER` | `~/.claude-fleet/active` | the fleet pointer symlink the board compares against its last render — a flip regenerates the page on the next view, floor or no floor |
| `QUOTA_DASH_CREDITS_KEY_FILE` | `~/.config/fabrik/subagents.env` | where the OpenRouter key is read from (`OPENROUTER_API_KEY` in the environment wins). The key is never rendered, never logged and never written to the cache |
| `QUOTA_DASH_CREDITS_TTL_S` | `300` | how long a balance is reused. Credits move only when something spends; at the 20s refresh an uncached read would be ~4,320 calls a day |
| `QUOTA_DASH_CREDITS_TIMEOUT_S` | `10` | the balance GET's timeout — it runs OFF the render path, so this can never delay a page load |
| `QUOTA_DASH_CREDITS_URL` | `https://openrouter.ai/api/v1/credits` | the balance endpoint |
| `POOL_CREDITS_WARN_USD` | `5` | the drain line. An ABSOLUTE floor, not a percentage: after a top-up the percentage is meaningless ($20 of $245 reads as 8% and is the whole runway) |

## Boundaries

- **One write path, and it is a relay.** It shells `--status --json` to read, and — only on
  the operator's click — `--switch <slug>` to flip. It never decides a rotation, never writes
  `caps.json`, never reads or writes a credential file; the CLI owns every one of those
  contracts (see `docs/workstation/claude-account-rotation.md`). The tick's own automation is
  unchanged: it still flips at 95% / the cap (98 until 2026-09-03; D-104) — and since 2026-09-03 the board itself invokes the tick within ~20s of the crossing, which is why the
  button exists: a fast burn (94% → 100% inside one tick, seen 2026-09-02) reaches the wall
  before the tick does, and the operator can see it coming on this board.
- **Loopback only.** No auth, because nothing off-box can reach it; do not rebind it to
  `0.0.0.0` without putting auth in front.
- **Stdlib only.** No dependencies to keep current.

## Related

- `docs/workstation/claude-account-rotation.md` — the rotation system this displays
- `PORTS.md` — port 5051 allocation
