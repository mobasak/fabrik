# [Project Name] — Services

<!--
  CANONICAL SERVICE REGISTRY for this project. Two jobs:
    1. Document every service THIS project runs (compose services + ports).
    2. Catalog every EXTERNAL service / API it depends on, with the operational
       nuance an operator or AI agent needs (cost, limits, why-this-vendor, status).

  This is the single place to answer "what does this project talk to, and is it healthy?"

  Enforcement: scripts/enforcement/check_compose_services.py requires every compose
  service to be documented here (or in README); check_structure.py recognises this file.

  HOW TO USE: fill the placeholders, delete example rows that don't apply, and keep
  the per-dependency block format for each external service so the catalog stays scannable.
-->

## Services This Project Runs

| Service | Port | Health Endpoint | Purpose |
|---------|------|-----------------|---------|
| [Project Name] API | [PORT] | `/health` | [Brief description] |
<!-- One row per compose service: api, worker, beat, dashboard, … -->

> **Scheduled jobs (Beat/cron):** the beat/scheduler appears above as a service row ONLY. The canonical
> inventory of jobs, intervals, and TTLs is **`RESILIENCE.md` §7 (Proactive Monitoring Schedule)** —
> never list individual jobs here.

Deployed via **SSH + Docker Compose** direct to the VPS (no intermediary platform).
Traefik handles external HTTPS; container ports are **not** exposed publicly. DB and
cache use Docker DNS — `postgres-main:5432`, `redis-main:6379` — never `localhost`. (Spoke-deployed
projects — spec `target_vps: vps2/vps3` — reach hub infra at the registrar-injected mesh IP
`10.99.0.1:<port>` instead: Docker DNS does not cross the WireGuard mesh.)

## External Dependencies

<!--
  List every third-party API/service the project calls. Use the summary table for
  simple key→purpose mappings; use the rich per-service block below for anything with
  real operational nuance (rate limits, cost tiers, vendor trade-offs, partial status).
-->

### Core Infrastructure Services

| Service | Env Var | Endpoints | Purpose |
|---------|---------|-----------|---------|
| **[Vendor]** | `VENDOR_API_KEY` | N endpoints | [What it does; why it's the primary choice] |
<!-- e.g. Cloudflare · Resend · OpenRouter · Anthropic (claude -p subscription) — one row each.
     AI dependencies belong here TOO: OpenRouter models (env key, $/Mtok, rate limits) and
     `claude -p` CLI calls (no API key — subscription OAuth; cost = weekly quota, not dollars;
     failure signature: weekly-limit exhaustion vs transient stream stall; fallback: account
     rotation / pause-until-reset). If the project calls it to function, it gets a block. -->

### [Service Group] — [What this group of dependencies is for]

<!--
  Repeat this block per dependency that has real nuance. Delete fields that don't apply.
  The Status emoji is the at-a-glance health signal; keep it accurate.
-->

**[Service Name]** — [one-line role]
- Env: `ENV_VAR_1`, `ENV_VAR_2`  (or "None needed")
- Cost: [free · $X/mo (quota) · PAYG $Y per call]
- Rate limit / quota: [X req/min, Y/month, Z concurrent — be explicit; "see docs" is a smell]
- Capabilities: [what it can do — include the numbers that matter]
- Limitations: [coverage gaps, gotchas, undocumented quirks discovered in production]
- Failure signature: [HTTP code / exception class / error message text that distinguishes "ban", "throttle", "quota exhausted", "transient" — these map to pause keys in RESILIENCE.md §2]
- Fallback: [retry + backoff · degrade to cached/last-good · switch to vendor B · error to caller · pause-state TTL N]
- Used in: [where in the pipeline / which feature]
- Why it exists: [why this vendor over the alternatives]
- Status: ✅ Working | ⚠️ Partial | ⏳ Pending | ❌ Blocked

**Evaluated and eliminated:**
- *[Alternative]* ($price) — [why rejected]
<!-- Capture "why not X" decisions so they are not re-litigated later. -->

### Service Status Summary (YYYY-MM-DD)

| Service | Status | Notes |
|---------|--------|-------|
| [Service] | ✅ Working | [key config / quota] |

## Service Details

### [Project Name] API

- **Port:** [PORT]
- **Health Check:** `curl http://localhost:[PORT]/health`
- **API Docs:** `http://localhost:[PORT]/docs`
- **Logs:** `/opt/[Project Name]/logs/` (local) · Loki → Grafana (VPS)
- **Project Path:** `/opt/[Project Name]`

## Service Management (Docker)

```bash
# Container status
sudo docker ps | grep [Project Name]

# Restart (on VPS — all docker commands require sudo)
cd /opt/[Project Name] && sudo docker compose restart

# Tail logs
sudo docker compose logs -f
```

## Quick Verification

```bash
# Service health — must test real deps (DB SELECT 1, Redis PING), not a static 200
curl -sS https://[Project Name].vps1.ocoron.com/health | jq .

# All Gatus monitors (fleet-wide)
curl -sS https://status.vps1.ocoron.com/api/v1/endpoints/statuses | jq '.[] | {name, ok: .results[-1].success}'
```

## Troubleshooting

### Service Returns 503
Health check failed — a dependency or config is missing. Hit `/health` to see which
check failed (e.g. `database`, `redis`, or a vendor token).

### Dependency / Auth Errors
Check the env var for the failing service. On the VPS, secrets live in the root-owned
`/opt/[Project Name]/.env` — update via `fabrik apply` / `fabrik redeploy --refresh-infra`,
never by hand-editing (direct edits are overwritten on next deploy). Never hardcode
secrets or `localhost`.

### Port Already In Use
Check `PORTS.md` for the allocation, change the port, and redeploy.
