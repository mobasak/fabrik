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
at/over `ROTATE_THRESHOLD` (default **98**, the tick's own default) or the account is cap-walled, the
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
  "live probe failed" banner (`quota.json` is the fallback store). Transient network blips are
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

| `switch →` button | on every row that is NOT the active pointer: one click flips the fleet to that account NOW — the same manual flip as `--switch <slug>` (pause-, dwell- and cap-exempt), confirmed in-page first; every session bound to the pointer (`CLAUDE_CONFIG_DIR` → the `active` symlink, § How a session binds to the pointer in `claude-account-rotation.md`) follows it without a restart. The active row carries no button (nothing to rotate to) |

Rows sort by weekly headroom, so the fleet's next flip target is the top eligible row.

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
| `QUOTA_DASH_MAX_AGE_S` | `240` | regeneration floor (probe-volume bound) |
| `QUOTA_DASH_REFRESH_S` | `60` | the page's own meta-refresh interval |
| `QUOTA_DASH_OUT_DIR` | `~/.claude/quota-dashboard` | render output |
| `QUOTA_DASH_ROTATE_CLI` | `/opt/fabrik/scripts/sysadmin/claude_rotate.py` | the CLI it shells |
| `QUOTA_DASH_PROBE_TIMEOUT_S` | `60` | per-probe subprocess timeout |
| `QUOTA_DASH_SWITCH_TIMEOUT_S` | `90` | `POST /switch` subprocess timeout (the CLI probes the target before flipping) |
| `QUOTA_DASH_SOCKET_TIMEOUT_S` | `15` | per-connection socket timeout — a client that under-sends its declared body is dropped, never parked |
| `QUOTA_DASH_POINTER` | `~/.claude-fleet/active` | the fleet pointer symlink the board compares against its last render — a flip regenerates the page on the next view, floor or no floor |

## Boundaries

- **One write path, and it is a relay.** It shells `--status --json` to read, and — only on
  the operator's click — `--switch <slug>` to flip. It never decides a rotation, never writes
  `caps.json`, never reads or writes a credential file; the CLI owns every one of those
  contracts (see `docs/workstation/claude-account-rotation.md`). The tick's own automation is
  unchanged: it still flips at 98% / the cap — and since 2026-09-03 the board itself invokes the tick within ~20s of the crossing, which is why the
  button exists: a fast burn (94% → 100% inside one tick, seen 2026-09-02) reaches the wall
  before the tick does, and the operator can see it coming on this board.
- **Loopback only.** No auth, because nothing off-box can reach it; do not rebind it to
  `0.0.0.0` without putting auth in front.
- **Stdlib only.** No dependencies to keep current.

## Related

- `docs/workstation/claude-account-rotation.md` — the rotation system this displays
- `PORTS.md` — port 5051 allocation
