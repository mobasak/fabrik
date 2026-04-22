---
auto_execution_mode: 0
description: Deploy application to VPS via Coolify (fabrik CLI, shape-driven)
---

# Deploy Workflow

Deploy a Fabrik service to production VPS via the `fabrik` CLI. Coolify + Traefik + all shape-gated registrars (Authelia, Gatus, Backrest, GlitchTip, Grafana, MeiliSearch, Postgres) are provisioned automatically per `shape.*` flags in the spec.

**Canonical reference:** `docs/DEPLOYMENT.md` — read first if anything in this file is unclear.

## Prerequisites

- [ ] Project scaffolded under `/opt/<name>/` via `fabrik scaffold <name> --type <template>`
- [ ] Spec file `specs/services/<name>.yaml` exists (check via `ls /opt/fabrik/specs/services/`)
- [ ] `shape.*` flags in spec match what the service actually needs (admin dashboard? DB? search? persistent data?)
- [ ] Domain in spec resolves under `*.vps1.ocoron.com` OR pre-provisioned with `fabrik domain provision`
- [ ] All secrets present in `/opt/fabrik/.env` (Coolify token, Cloudflare, Grafana SA, GlitchTip, Backrest, etc.)
- [ ] Lean gate passes: `python scripts/final_gate.py --lean`

## Steps

1. **Pre-flight** — Confirm scaffold readiness:
```bash
fabrik validate-deploy /opt/<name>
python scripts/final_gate.py --lean
```

2. **Dry-run deploy** — Shows every mutation without executing:
```bash
fabrik apply /opt/fabrik/specs/services/<name>.yaml --dry-run
```

// turbo
3. **Deploy** — Full pipeline: validator → secrets → DNS → template → Coolify → provisioners → verifier:
```bash
fabrik deploy --project /opt/<name>
# Or equivalently: fabrik apply /opt/fabrik/specs/services/<name>.yaml
```

Runs internally (see `docs/DEPLOYMENT.md` §9.2):
- `SpecValidator` → `deploy_validator` → `SecretsManager` → `DNSClient`
- `TemplateRenderer` → `ComposeLinter` → `CoolifyClient.{create,update}_application + deploy(force=true)`
- `InfrastructureProvisioner.provision(ctx)` — shape-gated: postgres · gatus · backrest · glitchtip+DSN · grafana · authelia+bypass · meilisearch
- `DeploymentVerifier.verify()` — HTTP 200, DNS, SSL, SENTRY_DSN via `docker inspect`

Expected wall time: ~60s for a scratch-image service, +30s–3min for a Dockerfile build.

// turbo
4. **Verify health** — Confirm deployment succeeded:
```bash
curl -f https://<name>.vps1.ocoron.com/health      # (or /) for scratch images
ssh vps 'sudo docker ps --format "{{.Names}}\t{{.Status}}" | grep <name>'
```

5. **Re-deploy idempotency check** — Running the same deploy again must be a no-op with all registrars reporting `status: exists`:
```bash
fabrik deploy --project /opt/<name>
```

## Rollback

Any failed step triggers automatic reverse-order cleanup via `RollbackManager` (see `docs/DEPLOYMENT.md` §9.8). DB drops are logged for operator action, never auto-executed.

## Verification

- [ ] `fabrik deploy` exits 0
- [ ] Container shows `Up` in `docker ps`
- [ ] Traefik router for the domain is `enabled`
- [ ] HTTPS endpoint reachable (302 to Authelia OR 200 from app)
- [ ] All shape-gated registrars green (see `docs/DEPLOYMENT.md` §9.6 for per-registrar verification commands)
- [ ] Idempotent re-deploy succeeds

## Related workflows

- `/bug-fix` — regression fix loop
- `/review` — code review before deploy
- `docs/DEPLOYMENT.md` §9.6 — **maximal-shape E2E validation** (run after any change to registrar driver, orchestrator, or compose template)
