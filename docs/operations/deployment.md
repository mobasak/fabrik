# Deployment Procedures

**Last reviewed:** 2026-05-08
**VPS:** vps1.ocoron.com (172.93.160.197)
**Coolify:** v4.0.0-beta.459 (web UI: `https://coolify.vps1.ocoron.com`)
**Deploy method:** Coolify API only — no manual `docker compose up` on VPS

---

## Golden Rules

1. **`fabrik redeploy` triggers Coolify, which pulls from GitHub.** Always `git commit && git push` BEFORE redeploying — Coolify reads the GitHub remote, not your local `/opt/`.
2. **Never `docker compose up -d` directly on the VPS.** Coolify owns lifecycle. Manual `up`/`down` strips Traefik labels and breaks routing on next redeploy.
3. **DB connection strings must use container DNS names**, never `localhost`: `postgres-main:5432`, `redis-main:6379`. Inside a container, `localhost` is the container itself.
4. **Never SIGHUP Authelia** — it exits. Always `docker restart authelia-hks48k8sg8o4co4co08co00o` after editing `/opt/authelia/configuration.yml`.
5. **No `ports:` in compose.yaml** — Docker bypasses UFW. Route everything through Traefik labels.

---

## Standard Deploy Workflow (existing service)

```bash
# 1. Edit code locally in WSL (/opt/fabrik or /opt/<service>)
# 2. Commit + push
cd /opt/<service>
git add -A
git commit -m "feat: <change>"
git push

# 3. Trigger Coolify redeploy
fabrik redeploy <service-name>

# 4. Watch logs (Loki via fabrik logs, or Coolify UI)
fabrik logs <service-name> --tail 100 --follow

# 5. Verify health
curl -sS https://<service>.vps1.ocoron.com/health
```

---

## New Service Deploy Workflow

```bash
# 1. Scaffold (creates /opt/<name>/ with full structure)
cd /opt
fabrik scaffold <name> --type python-api --description "<what it does>"
# Scaffold auto-emits: logger.py, internal_auth.py, metrics.py,
# glitchtip_init.py, /metrics endpoint, /health, structlog wiring,
# Dockerfile, compose.yaml, project.yaml, .env.example, AGENTS.md

# 2. Implement business logic in src/<package>/
cd /opt/<name>
# ... edit files ...

# 3. Validate against Fabrik standards
fabrik validate <name>

# 4. Plan (dry-run — shows what Coolify resources will be created)
fabrik plan <name>

# 5. Provision GlitchTip project + push DSN to Coolify env (optional)
bash /opt/fabrik/scripts/provision_glitchtip_project.sh <name>
# For Node services: add --platform javascript-node

# 6. Apply (creates Coolify Application/Service via API)
fabrik apply <name>

# 7. Coolify pulls from GitHub, builds, deploys. Watch:
fabrik status <name>
```

`fabrik apply` is idempotent — re-running on an existing service updates env vars and redeploys.

---

## Updating an Existing Service to Match New Scaffold Standards

When the scaffold gains new emitted files (e.g. the GlitchTip integration added 2026-05-08), bring older services up to date:

```bash
fabrik fix <service-name>
# Adds missing required files. Reference docs (4 files) always overwrite.
# AFCL.md is preserved if it exists (per-project friction log).
```

After `fabrik fix`: review the diff, commit, push, redeploy.

---

## Rollback

Coolify keeps the last known-good image. To revert:

```bash
# Option A — revert the commit, push, redeploy
cd /opt/<service>
git revert HEAD
git push
fabrik redeploy <service-name>

# Option B — Coolify UI: Application → Deployments → click previous deployment → "Redeploy"
```

`DeploymentRollback` class in `src/fabrik/deploy.py` runs reverse-order handlers automatically when `fabrik apply` fails partway through.

---

## Post-Reboot Recovery

After a VPS reboot, memory limits and Gatus DNS aliases need re-applying:

```bash
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"
```

This script:
- Reapplies Docker memory limits to all infra containers (Coolify strips them on restart)
- Re-attaches stable DNS aliases on the `coolify` network for single-image Applications (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`)
- Restarts Authelia if its config drifted

---

## Secrets Management

**Never commit secrets to git.** All secrets live in Coolify env (per service) or `/opt/fabrik/.env` (for CLI scripts).

| Secret | Storage | Rotation |
|---|---|---|
| `SERVICE_INTERNAL_SECRET_KEY` (M2M auth) | `/opt/fabrik/.env` + every service's Coolify env | Manual; rotate quarterly |
| `COOLIFY_API_TOKEN` | `/opt/fabrik/.env` only | Coolify UI → Profile → API Tokens |
| `GLITCHTIP_AUTH_TOKEN` | `/opt/fabrik/.env` only | GlitchTip UI → Settings → Auth Tokens |
| `GLITCHTIP_DSN` | per-service Coolify env (provisioner pushes via API) | Re-run `provision_glitchtip_project.sh` |
| Service-specific (Webshare, Apify, Cloudflare, etc.) | per-service Coolify env | Vendor dashboards |

**Pre-commit hook** (`scripts/sync_enforcement_to_projects.py`) blocks `.env`, `*.key`, `*.pem`, `*.crt` from being committed. GitHub push protection is the second line of defense.

---

## Health Check Commands

```bash
# Per-service health
curl -sS https://<service>.vps1.ocoron.com/health | jq .

# All Gatus monitors at once
curl -sS https://status.vps1.ocoron.com/api/v1/endpoints/statuses | jq '.[] | {name, status: .results[-1].success}'

# Container status from VPS
ssh vps 'sudo docker ps --format "{{.Names}}\t{{.Status}}"'

# Resource usage
ssh vps 'sudo docker stats --no-stream --format "{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}"'
```

---

## Observability Per Deploy

When a deploy happens, errors flow to two places:

| Where | What | Auth |
|---|---|---|
| Loki (via Grafana `https://grafana.vps1.ocoron.com`) | Structured logs with correlation IDs | Authelia |
| GlitchTip (`https://errors.vps1.ocoron.com`) | Stacktraces, release tags, environment | Authelia |
| Prometheus (via Grafana) | RED metrics (rate, errors, duration) per service | Authelia |
| Alertmanager → Telegram | Critical alerts (down, OOM, cert expiry) | n/a |

The release tag in GlitchTip events comes from `GIT_SHA` env var — set this in CI or via Coolify env to enable per-commit error filtering.

---

## Troubleshooting

**Symptom: `fabrik redeploy` returns success but no new code in production.**
You forgot `git push`. Coolify pulled the OLD GitHub state. Fix: `git push && fabrik redeploy <service>`.

**Symptom: service can't reach `postgres-main`.**
Container is on the wrong Docker network, or compose.yaml uses `localhost` instead of `postgres-main`. Check: `sudo docker inspect <container> | grep -A 5 Networks`.

**Symptom: 401 from a service that should be public.**
Authelia caught it. Check `/opt/authelia/configuration.yml` access rules; reload via `docker restart authelia-...` (NOT SIGHUP).

**Symptom: Traefik 502 / 504.**
`/health` endpoint timing out, or container exited. `sudo docker logs --tail 100 <container>`.

**Symptom: Gatus shows alias as `unknown` / 0.0.0.0.**
Single-image Application lost its alias on Coolify redeploy. Run `bash /opt/fabrik/scripts/vps_apply_limits.sh apply_alias <service>` (see `CROSS_CUTTING_REQUIREMENTS.md §9`).

---

## Related Runbooks

- `docs/infrastructure/glitchtip-sdk-integration-setup.md` — error reporting setup
- `docs/infrastructure/grafana-provisioning-setup.md` — Grafana datasources via file provisioning
- `docs/infrastructure/promtail-noise-filter-setup.md` — Loki ingestion filtering
- `docs/operations/coolify-migration.md` — moving services between hosts
- `docs/operations/disaster-recovery.md` — restore from backup
- `docs/operations/backup-strategy.md` — Backrest/Restic strategy

---

## Change Log

| Date | Change |
|---|---|
| 2026-05-08 | GlitchTip SDK integration baked into scaffold; provisioner script added; runbook published |
| 2026-05-08 | 5 leaked secrets redacted from HEAD (`apps/fabrik-proxy/compose.yaml`, archive doc) |
| 2026-05-07 | Grafana datasource file-provisioning live; Promtail noise filter deployed |
| 2026-05-06 | Gatus stable DNS alias architecture (single-image fix) codified across 4 governance docs |
