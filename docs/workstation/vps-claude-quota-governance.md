# VPS single-key Claude quota governance (ob@)

Box-local runbook for the machinery that keeps the VPS fleet's single system-wide Claude account
(`ob@ocoron.com`) under its Claude Max caps **without ever capping the sysadmin fix loop**. Built by
`docs/development/plans/archived/2026-08-29-plan-1-vps-quota-governance.md`.

## The model

One system-wide `claude` per VPS, authenticated as **ob@**, is the sole Claude entrypoint for every
consumer — host crons AND Docker containers. Two currencies are conserved: ob@'s **subscription
quota** (the binding constraint), never `ANTHROPIC_API_KEY`, never a per-call `$` cap. The design has
three cooperating parts plus a gate.

## Components

| Part | File | What it does |
|---|---|---|
| **Governor** | `scripts/sysadmin/quota_governor.py` | The router. `QuotaGovernor.route("routine"\|"incident", caller=)` reads `claude_rotate.py --probe-current --json` (live-or-cached single-key headroom) and returns `ob@` \| `pool` \| `pool-diagnose`. |
| **Broker** | `scripts/sysadmin/claude_broker.py` | Loopback service giving CONTAINERS completion-only claude (`claude -p --tools "" -- <prompt>`) with no host tools / no creds. Token auth, per-caller budgets, FAIL-CLOSED. |
| **Marshaller** | `scripts/sysadmin/incident_context.py` | When ob@ is capped, assembles an incident bundle (webhook + bounded log tails + host state) and INLINES it into a read-only pool worker for a diagnosis — operator-gated, never auto-applied. |
| **Gate** | `scripts/sysadmin/claude-run.sh` | The shared entrypoint now consults the governor before every ob@ call. |

## Routing rules (single-key bootstrap semantics, canary-corrected 2026-08-30)

- **routine** → `pool` ONLY on affirmative evidence: the account is capped (`cap_walled` or the
  reactive cap) **OR** a KNOWN `max(<every utilization window: five_hour, seven_day,
  model_windows>) ≥ RESERVE_PCT` (default 80); else `ob@` — **including unknown headroom**
  (probe failure / expired cache). Why: on the single-key VPS only a real claude call ever
  refreshes the token that produces telemetry, so "unknown → shed" wedges the whole loop (proven
  live on vps1 and rolled back). The `max` covers per-model weekly walls by construction.
- **incident** → `ob@` when not capped AND the single-flight `flock` is free; else `pool-diagnose`.
  A capped account or a fix already in flight routes to `pool-diagnose` — the fix is escalated,
  **never blocked or dropped**.
- **The reactive cap is the over-cap backstop** (file state — works with dark telemetry): when a
  claude call's FINAL result still carries a usage-limit, `run_claude` pipes it to
  `quota_governor.py mark-capped` → routine sheds until the window reset (or a bounded `CAP_TTL_S`,
  default 6h, when the epoch is missing — never `now ≥ None`).

## Headroom telemetry (how the governor SEES usage on a single-key host)

There is no quota-free way to refresh a stale token (`/v1/oauth/token` is Cloudflare-403'd), so:

- **Post-call capture:** after every real claude call — the one moment the token is guaranteed
  fresh — `run_claude` captures the account's usage (quota-free `api/oauth/usage` GET) into
  `~/.claude/state/current-usage-cache.json`. The 15-min proactive-check keeps it minutes old.
  Kill-switch: `CLAUDE_ROTATE_NO_USAGE_CAPTURE=1`.
- **`claude_rotate.py --probe-current --json`** (the governor's source): LIVE when the stored token
  works, else the cache within `PROBE_CACHE_MAX_AGE_S` (default 7200s), else
  `source:"unavailable"` (→ bootstrap-run). The keepalive health probe reads the same command.

## How consumers are wired

Gating the ONE chokepoint `claude-run.sh` wires every shell consumer at once — `morning-report.sh`,
`weekly-security.sh`, `proactive-check.sh`, `monthly-backup-verify.sh` all reach ob@ through it. The
gate:

- `CLAUDE_GOVERNOR_KIND` (default `routine`) — a routine call the governor sheds → `claude-run.sh`
  exits `75` (EX_TEMPFAIL) without running claude, so the best-effort caller skips this run.
- `CLAUDE_GOVERNOR_CALLER` — a label for the audit/budget (`morning-report`, etc.).
- `CLAUDE_GOVERNOR_KIND=bypass` — skip the gate. The **broker** sets this (it has already routed).
- The gate **fails OPEN**: if the governor errors or times out, claude runs — a broken governor never
  blocks the sysadmin loop.

`bot.py` (the interactive operator bot, full tools) consults the governor's lock-free `capped()`
check: it runs on ob@ when there is headroom and tells the operator when ob@ is at its wall (rather
than burn a capped call or degrade to a tool-less pool answer).

The keepalive (`claude-keepalive-rotate.sh`) **no longer issues a `claude -p ping`** — a
regularly-used ob@ needs no warmth ping, and the ping burned the quota being conserved. Its
auth/quota health signal now comes from the FREE `--probe-current --json` probe (no completion):
OK on a `live` reading or a recently-refreshed cache; FAIL when neither exists (a dead account
stops both, so its cache ages past the bound and the alarm fires).

## The broker (containers)

`POST` a JSON `{prompt, model?}` with an `X-Broker-Token` header to the loopback broker.

- **Tokens:** `~/.claude/broker-tokens.json` (mode 600) = `{ "<token>": {"caller": "<name>",
  "five_hour_limit": N, "seven_day_limit": N} }`. A missing/invalid token → 401.
- **Budgets:** `~/.claude/state/broker-budgets.json` — per-caller per-window counters, reset from the
  live `--status` window epoch; over-budget → 429 (a FAILED completion counts too, so error spam
  can't burn quota under-budget).
- **Confused-deputy defenses:** every claude run pins `--tools ""` (disable all tools) + `--` before
  the prompt (a container prompt can never be read as a flag) + a strict model-name charset; the
  broker FAILS CLOSED (503) if the tool-disable form isn't the pinned `--tools ""`.

## Configuration (env, all optional)

| Var | Default | Effect |
|---|---|---|
| `QUOTA_RESERVE_PCT` | `80` | routine sheds to the pool at/above this KNOWN utilization on any window |
| `QUOTA_CAP_TTL_S` | `21600` (6h) | bounded reactive-cap hold when a reset epoch is missing/None |
| `PROBE_CACHE_MAX_AGE_S` | `7200` (2h) | how old a cached usage reading may drive a reserve decision |
| `CLAUDE_ROTATE_NO_USAGE_CAPTURE` | unset | `1` disables the post-call capture + cap-signal hooks |
| `CLAUDE_SYSADMIN_MODEL` | `opus` | model for the diagnosis consumers (proactive-check, weekly-security, monthly-backup-verify); set in `/opt/fabrik/.env.sysadmin` on the host |
| `CLAUDE_MORNING_MODEL` | `sonnet` | model for the morning report (a formatting task); `opus` restores the old behavior; set in `.env.sysadmin` |
| `INCIDENT_LOG_TAIL_LINES` | `200` | `docker logs --tail` bound for the inlined incident bundle |
| `CLAUDE_GOVERNOR_KIND` | `routine` | `incident` \| `bypass` per call |
| `CLAUDE_GOVERNOR_CALLER` | `claude-run` | caller label |

## Operating

- **See the routing verdict:** the quota dashboard (`quota_dashboard.py`) shows a "Quota governor"
  panel — the active account's max window utilization, `cap_walled`, and the current routine/incident
  destinations.
- **CLI check:** `python3 scripts/sysadmin/quota_governor.py route --kind routine --caller test`
  prints `ob@` \| `pool` \| `pool-diagnose`.
- **Incident bundles** land at `~/.claude/state/incidents/<id>.json` for inspection; the pool
  diagnosis is mesh-notify'd to the operator and is **never auto-applied** — the operator applies it.
- **Wiring the incident source (integration step):** the marshaller's terminal entry is
  `IncidentMarshaller.run_incident(webhook, containers=)` and its CLI:

  ```
  echo '<glitchtip webhook json>' | python3 scripts/sysadmin/incident_context.py diagnose --containers <a,b>
  ```

  It routes the incident through the governor (`route("incident")`): headroom → `{"action":
  "run_on_obat"}` (the caller runs the autonomous fix on ob@, then `governor.release_incident()`);
  capped → `{"action": "pool_diagnosed", …}` (a read-only pool diagnosis, operator-gated). The
  **:8889 GlitchTip error-webhook watchdog** is the production caller — point it at this CLI so a
  capped incident is diagnosed instead of dropped. Until the watchdog is pointed at it, the entry is
  operator-invocable by hand (the command above).

## Deployed state + known caveats (2026-08-30 fleet validation)

- **Validated live on all 3 hosts** (vps1/vps2/vps3): real completions through the gated
  entrypoint; live probes (5h 2% / weekly 90% / Fable 48% at validation time); the governor
  CONSERVING for real — `routine → pool` at 90% weekly ≥ the 80% reserve while `incident → ob@`
  everywhere; keepalive OK; post-call cache persisted.
- **✅ Per-host OAuth grants (RESOLVED 2026-08-30 evening):** every VPS now owns its OWN ob@
  refresh chain (a `claude /login` per host, driven via tmux with the operator authorizing in the
  browser) — the earlier shared-chain state (one chain pushed to 3 hosts to heal a dead hub chain +
  a lapsed-payment outage) is gone, and with it the refresh-race 401 class. Each host's snapshot
  was re-captured (`--capture-current`) and live-verified (probe + keepalive OK ×3). If a chain
  ever dies again: keepalive pages via Telegram; heal = re-`/login` on that host (or the snapshot
  re-push as the stopgap).
- **Operator caps (set 2026-08-30):** `QUOTA_RESERVE_PCT=80` is pinned in
  `/opt/fabrik/.env.sysadmin` on all 3 hosts (the governor sheds routine at ≥80% on EVERY window —
  5h, weekly, per-model), and WSL `~/.claude-fleet/caps.json` carries `ob@ocoron.com: 80` so the
  WSL rotation never flips onto ob@ past 80% weekly (caps.json is weekly-only by design; there is
  no 5h knob in WSL rotation — the 5h 80% is enforced by the governor where ob@ actually works).
- **The morning heartbeat never dies:** on a governor shed the morning report sends the
  already-collected context as a RAW report (zero Claude cost — only the prose is skipped);
  live-proven with a forced shed. Model policy: diagnosis surfaces run `opus` (Opus 5), the
  morning report runs `sonnet` (Sonnet 5) — see the config table.
- **Datacenter vantage:** `api.anthropic.com/api/oauth/usage` 429s VPS IPs; `_oauth_get` falls back
  to `platform.claude.com` with a named User-Agent (Cloudflare 403s python's default UA). Both
  measured live on vps1; without the fallback the governor's telemetry silently blanks on a VPS.
- **Broker tokens are NOT yet minted** — the container half is idle until the operator writes
  `~/.claude/broker-tokens.json` per host.

## Invariants (do not break)

- The fix is NEVER dropped — capped ob@ → pool-diagnose + operator gate, never silence.
- Containers hold NO ob@ creds and reach only the completion-only broker.
- No `ANTHROPIC_API_KEY` on the operational path; no per-call `$` cap; no new python dependency.
- `claude_rotate.py` and `libs/subagents` are consumed, never modified, by this layer.
