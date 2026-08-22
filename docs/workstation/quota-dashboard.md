# Claude quota dashboard (box-local, `localhost:5051`)

**What it is:** the account-quota board rendered for a browser tab you leave open — every
Claude account's session (5h) and weekly headroom, reset times, the active pointer, caps and
warnings. It is a VIEW over `claude_rotate.py --status --json`; it owns no state, decides
nothing, and never touches a credential file.

**Open it:** <http://localhost:5051/> (works from Windows too — WSL forwards loopback).

Tool: `scripts/sysadmin/quota_dashboard.py` · Output: `~/.claude/quota-dashboard/`
(`index.html` + `quota.json`) · Log: `~/.claude/quota-dashboard.log`

## How it stays current — and why there is no regeneration cron

The page carries `<meta http-equiv="refresh">` (60s), and the server regenerates the data
**on view, at most once per `QUOTA_DASH_MAX_AGE_S` (default 240s)**. That bound is the whole
design:

- `--status --json` makes **live API probes** for fresh-token dirs. A `*/5` regeneration cron
  would probe forever whether or not anyone is looking; a self-refreshing tab would probe on
  every reload. On-demand + a floor gives a current page for a viewer, **zero** probe cost
  when the tab is closed, and refresh-spamming cannot multiply probe volume.
- The rendered page always states the age of its own data and, per account, whether the
  reading is live or `cached Nh ago` — a stale render is visible, never silent.
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
| `model weeklies: …` sub-line | per-**model** weekly limits, read from the usage payload's `limits` array (each `weekly_scoped` entry carries its own `scope.model.display_name`, e.g. **Fable**). Shown whenever present, at any % — a named per-model limit is meaningful at 0% (full headroom for that model). This is where Fable-5's separate weekly quota lives; it has **no** top-level window key (the reason an earlier top-level-only scan missed it, 2026-08-22). The undocumented always-0 top-level codename windows (`nimbus_quill`, …) are deliberately not surfaced |
| Warnings section | the same `fleet_warnings` the CLI prints (carrier/occupancy/cap/identity-mismatch) |

Rows sort by weekly headroom, so the fleet's next flip target is the top eligible row.

## Endpoints

| Path | Serves |
|---|---|
| `/` | the dashboard (regenerates if the render is older than the floor) |
| `/quota.json` | the raw `--status --json` payload behind the page |
| `/health` | `ok` — liveness for the keepalive |

## Lifecycle

Self-healing, no systemd (WSL has no user bus). Two crontab lines:

```cron
@reboot sleep 20 && /usr/bin/python3 /opt/fabrik/scripts/sysadmin/quota_dashboard.py --ensure >> $HOME/.claude/quota-dashboard.log 2>&1
*/10 * * * * /usr/bin/python3 /opt/fabrik/scripts/sysadmin/quota_dashboard.py --ensure >> $HOME/.claude/quota-dashboard.log 2>&1
```

`--ensure` connects to the port first and returns immediately if something answers, so the
10-minute line is a no-op while healthy and a restart within 10 minutes of any crash.

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

## Boundaries

- **Read-only over rotation.** It shells `--status --json`; it never flips the pointer, never
  writes `caps.json`, never reads or writes a credential file. Rotation decisions stay in
  `claude_rotate.py` (see `docs/workstation/claude-account-rotation.md`).
- **Loopback only.** No auth, because nothing off-box can reach it; do not rebind it to
  `0.0.0.0` without putting auth in front.
- **Stdlib only.** No dependencies to keep current.

## Related

- `docs/workstation/claude-account-rotation.md` — the rotation system this displays
- `PORTS.md` — port 5051 allocation
