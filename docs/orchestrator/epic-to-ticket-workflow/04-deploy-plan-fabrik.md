<!-- ⚠️ FABRIK FACTORY WORKFLOW — DEPLOY PLAN (our own, tool-capable twin of 04-deploy-plan-command)
     Run DIRECTLY by our orchestrator agent (Claude Code CLI, in VS Code) — never pasted into a planner GUI.
     TOOL-CAPABLE: it READS the Tech Plan + INFRA-CHECK from disk and verifies the planned deploy against the
     REAL `fabrik apply` invariants in code (deployer_ssh._validate_compose, the registrars). A pre-flight —
     it VERIFIES; it never writes compose or runs apply.

     Reads (open NOTHING else to act — every other citation below is `[canonical: …]` provenance you act on
     from the inline decision, or `(deeper, optional: …)` you may skip):
       · the Tech Plan (`03-tech-plan-fabrik` output — Shape Block, deployment constraints, resilience table)
       · the `00-trigger-fabrik` INFRA-CHECK · the Decisions Lock Metadata (`01-decisions-lock-fabrik`) for Path B
       · `docs/operations/fabrik-lifecycle.md` (registrar mechanics — what each creates + tears down)
       · `.windsurf/rules/core/35-security-auth.md` (M2M / bearer `^/api/` auth; the resource-based health-endpoint bypass is inline at Step 8, canonical in `core/30-ops.md`)
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). No hard-coded item count here. -->

# Deploy Plan

> Coolify decommissioned (2026-05-30); deploy is SSH + Docker Compose via `fabrik apply` `[canonical: src/fabrik/orchestrator/deployer_ssh.py]`. `networks: fabrik: external: true` is kept (Docker network name only).

## Role

Deployment engineer who confirms the service is ready for `fabrik apply` — verifying the spec shape block, compose contract, registrar surface, and the `fabrik apply` SSH+Compose invariants BEFORE any code is written. Bridges Stage 2 (planning) → Stage 3 (registration).

## Core Philosophy

Runs AFTER `03-tech-plan-fabrik`, BEFORE `05-ticket-outline-command`. A pre-flight that catches deploy-blocking issues before tickets are designed — cheap now, expensive after 20 tickets. Consume upstream; do not redo work. Only proceed when the user explicitly confirms — silence ≠ confirmation.

## Processing User Request

### Step 1: Consume Upstream

1. **Tech Plan** (`03-tech-plan-fabrik`) — Shape Block Declaration (Step 7), Component Architecture deployment **constraints**, resilience table.
2. **INFRA-CHECK** — **Path A**: capture `Shape`, `Concurrency`, `Port`, **`target_vps`**, `Scaffold`, `Rule Packs`, `User Guide`, `i18n`, `Responsive`, `Dark+Light`, `Abuse Detection`, `Email`, `FINANCIALS`. ⚠️ **`target_vps` decides the deploy host AND the DB/cache host** — a spoke (`vps2`/`vps3`) reaches shared infra at `10.99.0.1`, never by Docker DNS. **Path B**: also `Registrars`, `Universal categories`, `Epic Flavor` (Delta-feature | Retrofit) `[canonical: 00-trigger-fabrik § Entry Points → Multi-epic]`.
   - **`Registrars` cross-check (Path B):** the Step-4 Registrar Surface Map MUST match the Metadata `Registrars` list. Tech Plan says "fires authelia" but the list omits it → mismatch; route back to `mega-epic-breakdown/02-epic-decomposition-command`.
   - **`Universal categories` scope (Path B):** own category #3 (Persistence) but NOT #4 (Workers) → the Surface Map must NOT include worker-related registrars; sibling-owned categories' registrars are out-of-scope.
   - **`Epic Flavor: Retrofit` skip rule (Path B):** a code-only retrofit that changes no shape/compose/registrar/env (e.g. `Retrofit: i18n`, `Retrofit: Resilience` on existing calls, `Retrofit: Auth hardening`) may **skip this command entirely** — state "Skipped per Retrofit Epic Flavor; existing compose unchanged." Run it ONLY when the retrofit adds a registrar / shape flag / external dep / env var (e.g. `Retrofit: search` → `has_search_feature` + meilisearch → Steps 2+4+5; `Retrofit: backup` → `has_persistent_data` + backrest → Steps 2+4). State which Steps run.
3. `docs/operations/fabrik-lifecycle.md` — registrar mechanics (what each creates and removes).

### Step 2: Confirm Shape Block

Verify the Tech-Plan shape block against the architecture — **all 8 flags** `[canonical: spec_loader.py — Shape (:205)]`:

```yaml
shape:
  needs_database: <bool>      # → postgres
  needs_cache: <bool>         # → redis
  is_public: <bool>           # → gatus + Traefik (needs spec.domain)
  is_admin_dashboard: <bool>  # → authelia forward-auth (needs spec.domain)
  has_bearer_api: <bool>      # → Authelia ^/api/ bypass (only with is_admin_dashboard + domain)
  exposes_metrics: <bool>     # → prometheus (needs spec.domain)
  has_search_feature: <bool>  # → meilisearch
  has_persistent_data: <bool> # → backrest
```

For each `true` flag, confirm the code WILL satisfy the registrar's expectation: `needs_database` → `DATABASE_URL` env pointing at `postgres-main:5432` (spoke: `10.99.0.1:5432`); `needs_cache` → `REDIS_URL` at `redis-main:6379` (spoke: `10.99.0.1:6379`); `is_public` → Traefik labels for `<id>.vps1.ocoron.com` + a real-dep `/health`; `is_admin_dashboard` → Authelia forward-auth middleware; `has_bearer_api` → the `^/api/` bypass is installed inside the Authelia rule (fires nothing without `is_admin_dashboard` + domain); `exposes_metrics` → a `/metrics` endpoint (prometheus-client / prom-client); `has_search_feature` → a Meilisearch client using the registrar-injected URL (`https://search.vps1.ocoron.com` via Traefik→443; `:7700` is the internal container port, NOT exposed).

### Step 3: Compose Contract

Verify the planned `compose.yaml` will have: `deploy.resources.limits.memory` (**required per service — FATALLY enforced** `[canonical: deployer_ssh._validate_compose() — refuses any service without a memory limit]`) + `cpus` (recommended, not fatal) · `platform: linux/amd64` · `container_name: <id>` (stable — no UUID/timestamp drift) · a `healthcheck` with a `start_period` (the scaffold/deployer emit ~10–20s — grace for boot + migrations before it marks unhealthy; `_validate_compose` does not check this value) · `networks: fabrik: external: true` · Traefik labels if `is_public` (`Host`, `websecure`, `letsencrypt`, hardcoded port) · `restart: unless-stopped` · **no `ports:` host binding** (all routing via Traefik).

### Step 4: Registrar Surface Map

List which of the **10** registrars fire and what each creates (the `Registrars` list cross-check, Path B):

| Registrar | Fires? | Creates |
|---|---|---|
| postgres | ? (`needs_database`) | DB `<id_underscores>` on postgres-main |
| redis | ? (`needs_cache`) | DB index N from the registry (registrar-allocated) |
| gatus | ? (`is_public` + domain) | Health monitor at `status.vps1.ocoron.com` |
| backrest | ? (`has_persistent_data`) | Backup plan → Backblaze B2 |
| glitchtip | ? (`shape.kind`) | Error-tracking project + `SENTRY_DSN` env |
| grafana | **always** | Deploy annotation |
| authelia | ? (`is_admin_dashboard` + domain) | Access-control rule for the domain |
| meilisearch | ? (`has_search_feature`) | Search index `<id_underscores>` |
| prometheus | ? (`exposes_metrics` + domain) | Scrape target in prometheus.yml |
| watchdog | **opt-OUT (fires unless `watchdog: {enabled: false}`)** | Watchdog sidecar (cost/error monitor) + `compose.watchdog.yaml` overlay |

### Step 5: Environment Variables Checklist

List ALL deploy-time env vars: `PORT` (compose default, Yes) · `LOG_LEVEL` (service `.env`, Yes, default INFO) · `DATABASE_URL` (service `.env` if `needs_database`, conditional) · `REDIS_URL` (if `needs_cache`, conditional) · `SENTRY_DSN` (glitchtip-injected, auto) · `SERVICE_INTERNAL_SECRET_KEY` (M2M auth, Yes for API services) · project-specific vars. **Cross-check:** every external dependency in the Tech Plan's resilience table has a corresponding env var for its connection string/key.

### Step 6: Deploy Invariants (SSH + Docker Compose)

Confirm: **memory limit per service** (`deploy.resources.limits.memory` — fatally enforced `[canonical: deployer_ssh._validate_compose()]`, prevents OOM on the shared VPS) · the SSH deployer writes `/opt/<svc>/.env` to the VPS as part of `fabrik apply` · **no host-port binding** (Traefik `web`/`websecure` entrypoints route via labels) · stable `container_name: <id>` (no UUID/timestamp drift).

### Step 7: Destroy Path Verification

Confirm `fabrik destroy --use-state` cleanly reverses everything `fabrik apply` creates: every firing registrar has a teardown path (DB drop, Gatus removal, Backrest plan delete, watchdog sidecar teardown, …); no orphan containers / DNS / config fragments after destroy; data-bearing registrars (postgres, backrest) require the `--drop-data` flag — confirm it's documented.

### Step 8: Authelia & Security Confirmation

- `is_admin_dashboard: true` (or internal-only `is_public: false`) → confirm an Authelia forward-auth rule will be created.
- Health/observability endpoints MUST be excluded from Authelia — the bypass is **resource-based, not domain-bound** `[canonical: core/30-ops.md § the Authelia health-endpoint bypass]`: `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on EVERY domain routed through Authelia (hub direct + spokes via `authelia-vps1@file`). Confirm no Traefik label or compose override re-protects these resources.
- M2M auth (`X-Internal-Token` + `SERVICE_INTERNAL_SECRET_KEY`) confirmed for every Internal API consumed.

### Step 9: Present and Confirm

Present the deploy plan; the user confirms shape + compose + registrars + env vars + destroy path. Silence ≠ confirmation. Any mismatch (e.g. code needs Redis but `shape.needs_cache: false`) → flag as a correction to resolve before `05-ticket-outline-command`.

**Downstream doc feed:** the Deploy Plan informs the project's **`docs/DEPLOYMENT.md`** (from `DEPLOYMENT_TEMPLATE.md` — compose contract, env vars, registrar surface). ⚠️ **`docs/DEPLOYMENT_ARCHITECTURE.md` is a hub-only doc — never a project's.** `05-ticket-outline-command`'s Documentation Assignment Matrix assigns which ticket fills `docs/DEPLOYMENT.md`.

## Does NOT

- Design Component Architecture / Data Model / resilience table — that is `03-tech-plan-fabrik` Step 6.
- Decompose into tickets — that is `05-ticket-outline-command`.
- Write the actual `compose.yaml` content — Step 3 names the contract; literal content is `06-ticket-breakdown-command` per-ticket.
- Execute `fabrik apply` — that is `11-deploy-command` (Stage 3); this command is the pre-flight verification.
- Redeclare the Shape Block — Step 2 VERIFIES the `03-tech-plan-fabrik` Step-7 declaration; declaring is upstream's job.
- Re-derive INFRA-CHECK fields — consume from the Decisions Lock Metadata verbatim (Step 1); a missing Path B field routes back to `00-trigger-fabrik`.
- Write env values (secrets, keys) — Step 5 names the checklist; values are populated at `fabrik apply` time per `core/35-security-auth.md`.
- Run Steps 2–8 for a code-only Retrofit that changes no shape/compose/registrar/env — per the Step-1 skip rule (state which Steps run).
- Validate the Deploy Plan against downstream commands — that is `08-implementation-validation-command` + `10-cross-artifact-validation-command`.

## Acceptance Criteria

- Upstream consumed: Tech Plan (shape, deployment constraints, resilience table), INFRA-CHECK, `fabrik-lifecycle.md`.
- Shape block confirmed against architecture — **all 8 flags**, every `true` field mapped to a concrete code expectation.
- Compose contract verified (all 8 mandatory elements: fatal memory limit (+ recommended cpus), platform, container_name, healthcheck with start_period, network, Traefik-if-public, restart, no host ports).
- Registrar Surface Map complete — **all 10 registrars** (each yes/no + "Creates"), including grafana (always) and watchdog (opt-OUT).
- Env-vars checklist complete, cross-checked against the resilience table.
- Deploy invariants confirmed (fatal memory limit, `.env` deployer-written, no host ports, stable `container_name`).
- Destroy path verified: `fabrik destroy --use-state` reverses all registrations cleanly.
- Authelia/security confirmed; `/health`, `/metrics`, `/healthz`, `/api/health` not behind auth.
- No shape ↔ architecture mismatches at handoff.
- Downstream doc feed identified (`docs/DEPLOYMENT.md` — NOT `DEPLOYMENT_ARCHITECTURE.md`, which is hub-only).
- User explicitly confirms.

---

**Next (CC1 pairing, north star § Command-chain build plan):** converge this Deploy Plan with `/fabrik-workflow-review <spec path> deploy-plan` — it forces the no-op (all 8 shape flags mapped, all 10 registrars in the surface map, compose contract complete, destroy path reversible, `/health` not behind auth, zero hollow citations) before anything consumes it. Then → `05-ticket-outline-command`. *(Downstream ettw twins are built incrementally; refs point to the live Traycer `-command` source and flip to `-fabrik` as each twin lands.)*
