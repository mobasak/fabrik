# VPS Infrastructure Audit — 2026-05-27

**Source:** Full VPS SSH audit (82 tool calls) + `fabrik audit-registrars` cross-check  
**Scope:** All VPS infrastructure — 30 containers, 9 registrars, network security, monitoring stack, backups, crons, LLM agents, AI Sysadmin  
**Method:** SSH probe of every layer + cross-reference against `fabrik-lifecycle.md`, `infrastructure.py`, `AGENTS.md`, `PORTS.md`, `LOCAL_LLM_INFRASTRUCTURE.md` + best practices  
**Iteration:** Two passes — per-service registrar audit first, then full infra sweep. No further gaps found after second pass.

---

## All-Clear (27 items verified ✓)

UFW 14 rules · DOCKER-USER 9 rules · All 30 expected services running · Backrest 3 plans (all ran today) · Authelia rules correct for all services except image-broker · Postgres 2 DBs match allocations registry · Redis v7.4.7 DB3+DB4 in use per assignments · Prometheus 13 active jobs all healthy · Alertmanager Telegram configured, no active alerts · Docker coolify network, all services present · 4 stable aliases confirmed (site-provisioner, image-broker, meilisearch, glitchtip-web, gotenberg, browserless) · Gatus 35 endpoints all UP · Meilisearch healthy, 0 indexes (expected) · Coolify alias watcher running 6 days · WSL crons: hourly drift, weekly Authelia, Supabase keep-alive all present · Ollama 4 fabrik agents present · VPS AI Sysadmin (`vps-sysadmin-bot.service`) running 6 days · site-provisioner `/health` + DB + `GLITCHTIP_DSN` · image-broker `/health` + memory + aliases

---

## Issues

### Issue #1 — Authelia: image-broker fully bypassed — CRITICAL / SECURITY

**What is wrong**

`images.vps1.ocoron.com` is in the blanket public-services bypass list in `/opt/authelia/config/configuration.yml` with no resource restriction:

```yaml
# CURRENT (WRONG)
- domain:
    - pdf.vps1.ocoron.com
    - images.vps1.ocoron.com   # ← should NOT be here
    - ...
  policy: bypass               # no resources filter — entire domain bypassed
```

The catch-all `*.vps1.ocoron.com -> two_factor` never fires for `images.vps1.ocoron.com` because bypass matches first. The image-broker admin UI is **open to the internet with zero authentication**.

**What spec says**

`image-broker.yaml`: `shape.is_admin_dashboard: true` + `shape.has_bearer_api: true`. Per `infrastructure.py`: paired-pattern — bypass `/api/` (M2M) + two_factor all other paths.

**Fix**

1. `cp /opt/authelia/config/configuration.yml /opt/authelia/config/configuration.yml.backup.$(date +%Y%m%d-%H%M%S)`
2. Remove `images.vps1.ocoron.com` from the blanket bypass domain list
3. Insert two rules BEFORE the `*.vps1.ocoron.com -> two_factor` catch-all:

```yaml
- domain: images.vps1.ocoron.com
  policy: bypass
  resources:
    - '^/api/'
    - '^/health$'
    - '^/metrics$'

- domain: images.vps1.ocoron.com
  policy: two_factor
```

4. `sudo docker restart authelia-hks48k8sg8o4co4co08co00o` (SIGHUP exits — must restart, not reload)
5. Verify: `curl -sv https://images.vps1.ocoron.com/` → 302 to Authelia login; `curl -sv https://images.vps1.ocoron.com/api/v1/health` → 200 no redirect

**Prevention**

- Never manually add a domain to Authelia config — always `fabrik apply` so the registrar owns the rules
- `audit_authelia_gates.py` weekly cron already runs — expand it to detect `is_admin_dashboard` domains that appear in bypass instead of two_factor
- Upgrade `fabrik audit-registrars` authelia check: `✓` means "domain present with correct policy", not just "domain present" — bypass-only should report `drift`

---

### Issue #2 — Prometheus: fabrik-services job targets null — MEDIUM

**What is wrong**

`/opt/monitoring/configs/prometheus/prometheus.yml` `fabrik-services` job has `targets: null`. Both `site-provisioner` and `image-broker` have `exposes_metrics: true` (python-api template default). Neither is scraped — their `/metrics` are dark in Grafana for 12 days.

**Fix**

Resolved by Issue #5 fix (`fabrik apply --skip-deploy`) — the Prometheus registrar will write the targets. If needed manually:

1. Edit `/opt/monitoring/configs/prometheus/prometheus.yml`, replace `targets: null` with:

```yaml
  static_configs:
  - targets:
    - provision.vps1.ocoron.com
    - images.vps1.ocoron.com
```

2. `sudo docker exec prometheus kill -HUP 1` (Prometheus supports SIGHUP reload)
3. Verify: targets appear in `https://monitor.vps1.ocoron.com/targets` as `up`

**Prevention**

- `fabrik audit-registrars` already catches `prometheus: ✗` — close the loop: run `fabrik reconcile-all` when drift alert fires (AGENTS.md Gap 3)

---

### Issue #3 — Gatus: image-broker has no spec-driven HTTPS endpoint — MEDIUM

**What is wrong**

`fabrik audit-registrars` shows `image-broker gatus: ✗`. Existing monitoring is in `fabrik-microservices.yaml` via internal Docker hostname (`http://image-broker:8000/health`) — does not check TLS, DNS, or Traefik routing. `site-provisioner` passes audit (`gatus: ✓`) but also uses internal hostname — lower-severity quality gap.

**Fix**

Resolved by Issue #5 fix (`fabrik apply --skip-deploy`) — the Gatus registrar writes the HTTPS endpoint. Manual fallback:

Create `/opt/monitoring/configs/gatus/apps/image-broker.yaml`:

```yaml
endpoints:
  - name: image-broker
    group: apps
    url: "https://images.vps1.ocoron.com/health"
    interval: 60s
    conditions:
      - "[STATUS] == 200"
    alerts:
      - type: custom
        failure-threshold: 2
        send-on-resolved: true
```

Update `gatus/apps/dns-manager.yaml` to use public domain `https://provision.vps1.ocoron.com/health`. Remove duplicate internal entries from `fabrik-microservices.yaml` after confirming the above.

Gatus hot-reloads — no restart needed.

**Prevention**

- `fabrik-microservices.yaml` is for infrastructure services without fabrik specs (Gotenberg, Browserless, GlitchTip-web). Services with specs must go through `fabrik apply`

---

### Issue #4 — image-broker spec port wrong — LOW (spec is wrong, not the service)

**What is wrong**

`specs/services/image-broker.yaml` declares `env.PORT: "18016"` and `health.port: 18016`. Running container:
- Binds `8000/tcp`, Traefik routes to 8000, healthcheck hits `:8000/api/v1/health`
- `PORT=18016` env var is set in Coolify but the app hardcodes 8000

**Fix**

Edit `specs/services/image-broker.yaml` (local repo):
- `env.PORT: "18016"` → `env.PORT: "8000"`
- `health.port: 18016` → `health.port: 8000`

**Prevention**

- After first successful deploy, verify `docker inspect <container>` port bindings match `spec.health.port`
- Add to `my-workflow/04-deploy-plan-command`: confirm Traefik `loadbalancer.server.port` in compose.yaml matches `spec.health.port`

---

### Issue #5 — Missing state files for deployed services — MEDIUM

**What is wrong**

`.fabrik/state/` contains only a pytest artifact. No state files for `site-provisioner` or `image-broker`. Both predate the G-F3 state manifest (T2-01, 2026-05-15). Consequences: `fabrik destroy --use-state` fails; `glitchtip: ?` in audit; `last_apply_status: never` in `data/projects.yaml`.

**Fix**

After fixing #1 (Authelia) and #4 (spec port):

```bash
cd /opt/fabrik
.venv/bin/fabrik apply specs/services/site-provisioner.yaml --skip-deploy
.venv/bin/fabrik apply specs/services/image-broker.yaml --skip-deploy
```

This single operation also fixes Issues #2 (Prometheus targets) and #3 (Gatus endpoint) — the registrars re-run and write correct config.

Expected: GlitchTip registrar detects existing projects and skips (idempotent). Verify project count before and after is still 5.

**Prevention**

- `fabrik apply` always writes the state file — use it for every deploy, never bypass
- For any service predating 2026-05-15: run `fabrik apply --skip-deploy` once to backfill

---

### Issue #6 — site-provisioner `SENTRY_DSN` uses localhost — LOW

**What is wrong**

Container env has two DSN vars:
- `GLITCHTIP_DSN=http://5a1a3c14...@glitchtip-web:8000/24` ✓ (correct internal hostname)
- `SENTRY_DSN=http://5a1a3c14...@localhost:8000/24` ✗ (localhost fails inside the container)

If the SDK reads `SENTRY_DSN` as fallback when `GLITCHTIP_DSN` is unset, errors would silently drop. Currently the app likely uses `GLITCHTIP_DSN` per Fabrik convention — bug is latent, not actively failing. But violates the CLAUDE.md hard stop ("NEVER `DB_HOST=localhost`" — same principle for all internal service URLs).

**Fix**

In Coolify UI (or via Coolify API PATCH): update `SENTRY_DSN` env var for site-provisioner to `http://5a1a3c14ed1941718f6a4d5f2eb7a013@glitchtip-web:8000/24` (matching `GLITCHTIP_DSN`). Redeploy not required — env var change via Coolify API takes effect on next restart.

**Prevention**

- Never set `localhost` for any internal service reference in container env — always use the Docker service name
- `fabrik audit-registrars` GlitchTip check could validate that `SENTRY_DSN` uses the internal hostname, not localhost or the public URL

---

### Issue #7 — pushgateway has no memory limit — LOW

**What is wrong**

All monitoring stack containers have explicit memory limits except `pushgateway` (0 MB = unlimited). The F5 fix mandate requires all Coolify-deployed containers to declare `deploy.resources.limits.memory`.

**Fix**

Add memory limit to pushgateway's Coolify compose config (via `PATCH /api/v1/services/<uuid>` with updated `docker_compose_raw` — base64 encoded). Target: 64 MB (consistent with other exporters like `redis-exporter` and `postgres-exporter`).

Note: Coolify control-plane containers (coolify, coolify-redis, coolify-db, coolify-realtime, coolify-sentinel) also lack limits — these are managed by Coolify's own installer and cannot be user-edited. Acceptable exception.

**Prevention**

- `scripts/vps_apply_limits.sh` re-applies Docker limits after VPS reboot. Extend it to also verify pushgateway limit is set and alert if it drops to 0

---

### Issue #8 — PORTS.md has stale MinIO entry — LOW / DOC DRIFT

**What is wrong**

PORTS.md lists MinIO at ports 9000/9001 (`s3.vps1.ocoron.com`). No MinIO container is running on VPS. Either MinIO was planned but never deployed, or it was removed and the PORTS.md entry was not cleaned up.

**Fix**

Edit `PORTS.md`: remove or comment out the MinIO (9000/9001) port allocation. If MinIO is planned for future deployment, mark it `[reserved — not yet deployed]`.

**Prevention**

- PORTS.md is in the Doc Sync Matrix: whenever a container is removed from VPS, update PORTS.md in the same operation
- Add PORTS.md to `fabrik audit-registrars` output check: compare allocated ports in PORTS.md against running containers

---

### Issue D1 — AGENTS.md Gatus endpoint count stale — DOC DRIFT

**What is wrong**

AGENTS.md (or lifecycle doc) states "30 Gatus endpoints". Actual live count is 35 — all healthy. Count was not updated when new endpoints were added.

**Fix**

Update the endpoint count reference in AGENTS.md to "35 endpoints" or replace the hardcoded number with "check `status.vps1.ocoron.com`".

**Prevention**

- Avoid hardcoding Gatus endpoint counts in docs — use "see `status.vps1.ocoron.com`" as the live reference instead

---

### Issue D2 — CPU limits missing on most containers — DOC DRIFT / BEST PRACTICE

**What is wrong**

`fabrik-lifecycle.md` mentions `cpus` in `deploy.resources.limits` alongside `memory`. Only 3 containers (meilisearch, browserless, gotenberg) have CPU caps. The other 27 containers have memory limits but no `cpus` cap.

Containers without CPU limits can starve each other during bursts (e.g., Prometheus scrape burst + GlitchTip event flood both peaking simultaneously on a 6-vCPU host).

**Fix**

Phased approach: add `cpus` to the highest-risk containers first:
1. `loki` — log ingestor, can spike on log flood
2. `prometheus` — scrape + rule eval can spike
3. `glitchtip-web` — Python Django, can spike on event flood
4. `n8n` — workflow executor, can spike on complex workflows

Suggested caps: loki 0.5, prometheus 1.0, glitchtip-web 0.5, n8n 1.0

All others: add `cpus: "0.25"` as a conservative default in the next `vps_apply_limits.sh` pass.

**Prevention**

- `_write_canonical_compose` in `scaffold.py` already emits `cpus`. New scaffolded services have it
- Extend `vps_apply_limits.sh` to check and set `cpus` limit alongside memory for all non-Coolify containers

---

## Systemic Gaps (separate tickets)

### Gap A — Authelia audit does not check policy correctness

`fabrik audit-registrars` reports `authelia: ✓` for image-broker despite wrong policy (bypass instead of two_factor). `✓` means "domain present in config" — not "domain present with correct policy". `bypass-only` for an `is_admin_dashboard` service should be `drift`.

**Ticket:** Upgrade `drivers/authelia.py` audit to verify that `is_admin_dashboard` domains have `two_factor` policy. Report `drift` when policy is wrong.

### Gap B — No auto-reconcile on drift alerts (AGENTS.md Gap 3)

Hourly cron → pushgateway → Prometheus alert `FabrikRegistrarDrift` → Alertmanager → Telegram. Alert fires but no agent acts. The `prometheus: ✗` drift on site-provisioner and image-broker has been active for 12 days with no auto-fix.

**Ticket:** Wire AI Sysadmin (`scripts/sysadmin/bot.py`) to call `fabrik reconcile-all` when `FabrikRegistrarDrift` alert arrives via Telegram. Closes AGENTS.md Gap 3.

### Gap C — `fabrik apply --skip-deploy` not validated before production use

The `--skip-deploy` flag exists in CLI but has no integration test confirming it skips only the Coolify deploy and still writes the state file.

**Pre-fix check:** `cd /opt/fabrik && .venv/bin/fabrik apply specs/services/fabrik-e2e-test.yaml --skip-deploy --dry-run` — confirm registrar plan shown, no Coolify API calls in output.

---

## Execution Order

```
Step 1 — Safe local changes (no VPS risk)
  - Fix #4: correct image-broker spec port 18016 → 8000
  - Fix #8: remove stale MinIO entry from PORTS.md
  - Fix D1: update Gatus endpoint count in AGENTS.md

Step 2 — VPS security fix (requires Authelia restart)
  - Fix #1: remove images.vps1.ocoron.com from blanket bypass
            add paired-pattern rules (bypass /api/ + two_factor)
            docker restart authelia-*
            verify 302 on UI + 200 on /api/

Step 3 — VPS env fix (no restart needed)
  - Fix #6: update SENTRY_DSN for site-provisioner in Coolify env
            replace localhost:8000 with glitchtip-web:8000

Step 4 — Validate --skip-deploy (Gap C pre-check)
  - .venv/bin/fabrik apply specs/services/fabrik-e2e-test.yaml --skip-deploy --dry-run
  - Confirm: registrar plan shown, no Coolify API calls

Step 5 — Backfill registrars + write state files (resolves #2, #3, #5)
  - .venv/bin/fabrik apply specs/services/site-provisioner.yaml --skip-deploy
  - .venv/bin/fabrik apply specs/services/image-broker.yaml --skip-deploy
  - Verify: .fabrik/state/*.json written
            GlitchTip still 5 projects (not duplicated)
            Prometheus fabrik-services targets appear as 'up'
            Gatus image-broker HTTPS endpoint appears and is UP

Step 6 — Resource limits
  - Fix #7: add memory limit to pushgateway (64 MB via Coolify API PATCH)
  - Fix D2: add cpus cap to loki, prometheus, glitchtip-web, n8n (highest risk first)

Step 7 — Systemic tickets (separate work sessions)
  - Gap A: upgrade Authelia audit policy check → drift for wrong policy
  - Gap B: wire AI Sysadmin to auto-reconcile on FabrikRegistrarDrift
  - Gap C: add --skip-deploy integration test
```

---

## Full Issue Summary

| # | Issue | Layer | Severity | Step |
|---|---|---|---|---|
| 1 | image-broker Authelia bypass instead of two_factor | authelia | CRITICAL | 2 |
| 2 | fabrik-services Prometheus targets null | prometheus | MEDIUM | 5 |
| 3 | image-broker Gatus no HTTPS endpoint | gatus | MEDIUM | 5 |
| 4 | image-broker spec port 18016 vs actual 8000 | spec | LOW | 1 |
| 5 | No state files for site-provisioner / image-broker | state | MEDIUM | 5 |
| 6 | site-provisioner SENTRY_DSN uses localhost | env | LOW | 3 |
| 7 | pushgateway has no memory limit | resources | LOW | 6 |
| 8 | PORTS.md stale MinIO entry | docs | LOW | 1 |
| D1 | AGENTS.md Gatus count stale (30 vs 35) | docs | DOC DRIFT | 1 |
| D2 | CPU limits missing on most containers | resources | BEST PRACTICE | 6 |
| A | Authelia audit checks presence not policy correctness | audit | SYSTEMIC | 7 |
| B | No auto-reconcile on drift alerts | automation | SYSTEMIC | 7 |
| C | --skip-deploy untested before production use | risk | SYSTEMIC | 4 |
