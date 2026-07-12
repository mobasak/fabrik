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
2. **INFRA-CHECK** — Path A (single-epic): capture `Shape`, `Concurrency`, `Port`, `Scaffold`, `Internal APIs`, `Rule Packs`, `User Guide`, `i18n`, `Responsive`, `Dark+Light`, `Abuse Detection`, `Email`, `FINANCIALS` (the 12 fields propagated by `01-epic-brief-command` Path A). Path B (multi-epic 14-field block per `00-trigger-workflow-command` § Entry Points → Multi-epic (consume mode) post-`5a48017`+`1eaf22a`): ALSO capture `Registrars`, `Universal categories`, `Epic Flavor` (Delta-feature | Retrofit).

   **Path B-specific deploy-plan rules:**
   - **`Registrars` cross-check (Path B only):** Step 4 Registrar Surface Map MUST match the `Registrars` list from Epic Brief Metadata. If Tech Plan says "fires authelia" but the Registrars list omits authelia → mismatch; route back to `mega-epic-breakdown/02-epic-decomposition-command` to update the spec.
   - **`Universal categories` scope constraint (Path B only):** if the epic owns category #3 (Persistence) but NOT #4 (Workers), Step 4 MUST NOT include worker-related registrars in the Surface Map. Categories owned by sibling epics → registrars they fire are out-of-scope.
   - **`Epic Flavor: Retrofit` skip rule (Path B only):** for code-only retrofits that don't change shape/compose/registrars/env (e.g., `Retrofit: i18n`, `Retrofit: Resilience` on existing external calls, `Retrofit: Auth hardening`), ettw/04 may be **skipped entirely** — the upstream project's compose is unchanged. State explicitly in conversation: "Skipped per Retrofit Epic Flavor; existing project compose unchanged." Run ettw/04 ONLY when the retrofit adds a new registrar / shape flag / external dep / env var. Examples: `Retrofit: search` (adds `has_search_feature` + meilisearch registrar) requires Steps 2 + 4 + 5; `Retrofit: backup` (adds `has_persistent_data` + backrest) requires Steps 2 + 4. State which Steps run for the specific Retrofit subtype.
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
- Health/observability endpoints MUST be excluded from Authelia protection — Authelia bypass is **resource-based, not domain-bound** per `core/35-security-auth.md`: `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on EVERY domain routed through Authelia (hub direct + spokes via `authelia-vps1@file`). Confirm no Traefik label or compose override re-protects these resources.
- M2M auth pattern confirmed for every Internal API consumed.

### Step 9: Present and Confirm

Present the deploy plan. User confirms shape + compose + registrars + env vars + destroy path are correct. Silence ≠ confirmation.

If any mismatch found (e.g. code needs Redis but `shape.needs_cache: false`) → flag as a correction that must be resolved before `ticket-outline` begins.

**Downstream doc feeds:** Deploy Plan output directly informs `docs/DEPLOYMENT_ARCHITECTURE.md` (compose contract, env vars, registrar surface). The Documentation Sync Matrix in `ticket-breakdown` assigns which ticket fills this.

## Does NOT

- Does NOT design Component Architecture / Data Model / resilience table — that is `03-tech-plan-command` Step 6.
- Does NOT decompose into tickets — that is `05-ticket-outline-command`.
- Does NOT write the actual `compose.yaml` file content — Step 3 names the contract; literal file content is `06-ticket-breakdown` per-ticket.
- Does NOT execute `fabrik apply` — that is `11-deploy-command` (Stage 3 of the Fabrik lifecycle); ettw/04 is the pre-flight verification.
- Does NOT redeclare the Shape Block — Step 2 VERIFIES the declaration from `03-tech-plan-command` Step 7; the declaration is upstream's responsibility.
- Does NOT re-derive INFRA-CHECK fields — consume from Epic Brief Metadata verbatim per Step 1. Path B fields (`Registrars`, `Universal categories`, `Epic Flavor`) MUST flow through; missing routes back to `00-trigger-workflow-command`.
- Does NOT write env values (secrets, API keys) — Step 5 names the env vars CHECKLIST; values are populated at `fabrik apply` time per `core/35-security-auth.md` (M2M tokens, registrar-injected vars).
- Does NOT run Steps 2-8 for code-only Retrofit epics that don't change shape/compose/registrars/env — per Step 1 Path B Epic Flavor skip rule, ettw/04 may be skipped entirely (state which Steps run for the specific Retrofit subtype).
- Does NOT validate the Deploy Plan against downstream commands — that is `08-implementation-validation` + `10-cross-artifact-validation`.
- Does NOT propose `revise-requirements` mid-draft — Step 9 iteration cycle handles scope changes; mid-draft proposals confuse the owner.

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
