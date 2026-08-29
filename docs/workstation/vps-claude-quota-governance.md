# VPS single-key Claude quota governance (ob@)

Box-local runbook for the machinery that keeps the VPS fleet's single system-wide Claude account
(`ob@ocoron.com`) under its Claude Max caps **without ever capping the sysadmin fix loop**. Built by
`docs/development/plans/2026-08-29-plan-1-vps-quota-governance.md`.

## The model

One system-wide `claude` per VPS, authenticated as **ob@**, is the sole Claude entrypoint for every
consumer — host crons AND Docker containers. Two currencies are conserved: ob@'s **subscription
quota** (the binding constraint), never `ANTHROPIC_API_KEY`, never a per-call `$` cap. The design has
three cooperating parts plus a gate.

## Components

| Part | File | What it does |
|---|---|---|
| **Governor** | `scripts/sysadmin/quota_governor.py` | The router. `QuotaGovernor.route("routine"\|"incident", caller=)` reads the LIVE `claude_rotate.py --status --json` fleet payload and returns `ob@` \| `pool` \| `pool-diagnose`. |
| **Broker** | `scripts/sysadmin/claude_broker.py` | Loopback service giving CONTAINERS completion-only claude (`claude -p --tools "" -- <prompt>`) with no host tools / no creds. Token auth, per-caller budgets, FAIL-CLOSED. |
| **Marshaller** | `scripts/sysadmin/incident_context.py` | When ob@ is capped, assembles an incident bundle (webhook + bounded log tails + host state) and INLINES it into a read-only pool worker for a diagnosis — operator-gated, never auto-applied. |
| **Gate** | `scripts/sysadmin/claude-run.sh` | The shared entrypoint now consults the governor before every ob@ call. |

## Routing rules

- **routine** → `pool` when the account is `cap_walled` (the operator's authoritative `caps.json`
  weekly cap) **OR** `max(<every utilization window: five_hour, seven_day, model_windows>) ≥
  RESERVE_PCT` (default 80); else `ob@`. The `max` covers per-model weekly walls (Fable today; Opus if
  its weekly sub-limit appears) by construction.
- **incident** → `ob@` when there is headroom AND the single-flight `flock` is free; else
  `pool-diagnose`. A `cap_walled` account, a reactive `is_usage_limit` signal, or a fix already in
  flight all route to `pool-diagnose` — the fix is escalated, **never blocked or dropped**.
- **Fail-SAFE:** a `--status` failure / unparseable row → routine sheds to `pool`, an incident still
  runs on `ob@`. A `None`/past reset epoch is bounded by `CAP_TTL_S` (default 6h), never `now ≥ None`.

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
auth/quota health signal now comes from the FREE `--status --json` profile probe (no completion).

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
| `QUOTA_RESERVE_PCT` | `80` | routine sheds to the pool at/above this utilization on any window |
| `QUOTA_CAP_TTL_S` | `21600` (6h) | bounded reactive-cap hold when a reset epoch is missing/None |
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

## Invariants (do not break)

- The fix is NEVER dropped — capped ob@ → pool-diagnose + operator gate, never silence.
- Containers hold NO ob@ creds and reach only the completion-only broker.
- No `ANTHROPIC_API_KEY` on the operational path; no per-call `$` cap; no new python dependency.
- `claude_rotate.py` and `libs/subagents` are consumed, never modified, by this layer.
