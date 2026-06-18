<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > (select matching step)
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md (131 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Deploy Plan

> **Note:** Coolify decommissioned (2026-05-30); deploy is SSH + Docker Compose
> via `fabrik apply` → `src/fabrik/orchestrator/deployer_ssh.py`. `networks:
> fabrik: external: true` is kept (Docker network name only).

## Role

You are a deployment engineer who confirms the service is ready for `fabrik apply` — verifying the spec shape block, compose contract, registrar surface, and compose/deploy readiness (the `fabrik apply` SSH+Compose invariants) before any code is written. You bridge Stage 2 (planning) and Stage 3 (registration) of the Fabrik lifecycle.

## Core Philosophy

Deploy Plan runs AFTER tech-plan, BEFORE ticket-outline. It's a pre-flight that catches deploy-blocking issues before tickets are designed. Cheap to fix now; expensive after 20 tickets are implemented.

- Consume what upstream commands produced. Do not redo work.
- Only proceed when user explicitly confirms. Silence ≠ confirmation.

## Processing User Request

### Step 1: Consume Upstream

1. **Tech Plan** — Shape Block Declaration (Step 7), Component Architecture deployment config, resilience table.
2. **INFRA-CHECK** — Shape, Concurrency, Port, Scaffold, Internal APIs.
3. `docs/operations/fabrik-lifecycle.md` — deploy/runtime behavior & data safety (registrar mechanics — confirm understanding of what each registrar creates and removes).

### Step 2: Confirm Shape Block

Verify the shape block from Tech Plan against the architecture:

```yaml
shape:
  needs_database: <true/false>
  needs_cache: <true/false>
  is_public: <true/false>
  is_admin_dashboard: <true/false>
  exposes_metrics: <true/false>
  has_search_feature: <true/false>
  has_persistent_data: <true/false>
```

For each `true` field, confirm the code WILL satisfy the registrar's expectations:
- `needs_database` → code uses `DATABASE_URL` env var pointing at `postgres-main:5432`
- `needs_cache` → code uses `REDIS_URL` env var pointing at `redis-main:6379`
- `is_public` → compose has Traefik labels for `<id>.vps1.ocoron.com`; `/health` endpoint exists
- `is_admin_dashboard` → Authelia forward-auth middleware in compose labels
- `exposes_metrics` → `/metrics` endpoint using prometheus-client / prom-client
- `has_search_feature` → Meilisearch client connecting to `search.vps1.ocoron.com:7700`

### Step 3: Compose Contract

Verify the planned `compose.yaml` will have:

- [ ] `deploy.resources.limits.memory` + `cpus` (required per service — enforced fatally by `deployer_ssh._validate_compose()`)
- [ ] `platform: linux/amd64`
- [ ] `container_name: <id>`
- [ ] `healthcheck` with `start_period: 60s` (grace for container boot + migrations before the healthcheck marks it unhealthy)
- [ ] `networks: fabrik: external: true`
- [ ] Traefik labels (if `is_public`): `Host`, `websecure`, `letsencrypt`, hardcoded port
- [ ] `restart: unless-stopped`
- [ ] No `ports:` binding to host (all routing via Traefik)

### Step 4: Registrar Surface Map

List which registrars will fire and what they'll create:

| Registrar | Fires? | Creates |
|---|---|---|
| postgres | ? | DB `<id_underscores>` on postgres-main |
| redis | ? | DB index N from redis-assignments.json |
| gatus | ? | Health monitor at `status.vps1.ocoron.com` |
| backrest | ? | Backup plan → Backblaze B2 |
| glitchtip | ? | Error tracking project + SENTRY_DSN env |
| grafana | ? | Deploy annotation (always) |
| authelia | ? | Access control rule for domain |
| meilisearch | ? | Search index `<id_underscores>` |
| prometheus | ? | Scrape target in prometheus.yml |

### Step 5: Environment Variables Checklist

List ALL env vars the service needs at deploy time:

| Var | Source | Required? |
|---|---|---|
| `PORT` | compose.yaml | Yes (default in compose) |
| `LOG_LEVEL` | service `.env` (deployer-written) | Yes (default: INFO) |
| `DATABASE_URL` | service `.env` (if needs_database) | Conditional |
| `REDIS_URL` | service `.env` (if needs_cache) | Conditional |
| `SENTRY_DSN` | Injected by glitchtip registrar | Auto |
| `SERVICE_INTERNAL_SECRET_KEY` | service `.env` (M2M auth) | Yes for API services |
| (project-specific vars) | ... | ... |

Cross-check: every external dependency in Tech Plan's resilience table must have a corresponding env var for its connection string/key.

### Step 6: Deploy invariants (SSH + Docker Compose)

Confirm the deployment satisfies the `fabrik apply` SSH+Compose invariants:

- [ ] Memory limit required: every compose service declares `deploy.resources.limits.memory` — validated fatally by `deployer_ssh._validate_compose()` (refuses any service without it, prevents OOM on the shared VPS)
- [ ] `.env`: the SSH deployer writes `/opt/<svc>/.env` to the VPS as part of `fabrik apply`
- [ ] No host-port binding: Traefik routes via labels (`web`/`websecure` entrypoints) — no `ports:` mapping to the host
- [ ] Stable `container_name: <id>` (no UUID/timestamp drift)

### Step 7: Destroy Path Verification

Confirm `fabrik destroy --use-state` will cleanly reverse everything `fabrik apply` creates:

- Every registrar that fires has a corresponding teardown path (DB drop, Gatus removal, Backrest plan delete, etc.).
- No orphan containers, DNS entries, or config fragments after destroy.
- Data-bearing registrars (postgres, backrest) require `--drop-data` flag — confirm this is documented.

### Step 8: Authelia & Security Confirmation

- If `is_admin_dashboard: true` or `is_public: false` (internal-only): confirm Authelia forward-auth rule will be created.
- `/health` endpoint MUST be excluded from Authelia protection (Authelia bypass rule `*.vps1.ocoron.com → /health` covers this — confirm no override).
- M2M auth pattern confirmed for every Internal API consumed.

### Step 9: Present and Confirm

Present the deploy plan. User confirms shape + compose + registrars + env vars + destroy path are correct. Silence ≠ confirmation.

If any mismatch found (e.g. code needs Redis but `shape.needs_cache: false`) → flag as a correction that must be resolved before `ticket-outline` begins.

**Downstream doc feeds:** Deploy Plan output directly informs `docs/DEPLOYMENT_ARCHITECTURE.md` (compose contract, env vars, registrar surface). The Documentation Sync Matrix in `ticket-breakdown` assigns which ticket fills this.

## Acceptance Criteria

- Upstream consumed: Tech Plan (shape, deployment config, resilience table), INFRA-CHECK, `fabrik-lifecycle.md`.
- Shape block confirmed against architecture. Every `true` field maps to concrete code expectations.
- Compose contract verified (all 8 mandatory elements).
- Registrar surface map complete (9 registrars, each yes/no with "Creates" column).
- Env vars checklist complete. Cross-checked against resilience table.
- Deploy invariants confirmed (memory limits in compose, `.env` deployer-written, no host ports, stable `container_name`).
- Destroy path verified: `fabrik destroy --use-state` reverses all registrations cleanly.
- Authelia / security confirmation complete. `/health` not behind auth.
- No shape ↔ architecture mismatches at handoff.
- Downstream doc feed identified (DEPLOYMENT_ARCHITECTURE.md).
- User explicitly confirms. Silence ≠ confirmation.
