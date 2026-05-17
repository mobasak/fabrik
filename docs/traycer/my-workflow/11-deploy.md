# Deploy

## Role

Deployment operator who executes `fabrik apply`, verifies the live service on VPS, and confirms all registrars are present. This is the FINAL command in the workflow — bridges Stage 3 (registration) and Stage 4 (verification) of the Fabrik lifecycle.

## Applicability by Scaffold Type

| Scaffold | Deploy path | What `fabrik apply` does |
|---|---|---|
| `python-api`, `node-api`, `file-api`, `file-worker` | VPS via Coolify (compose + Dockerfile) | Full registrar set |
| `saas-skeleton`, `static-site`, `docusaurus` | VPS via Coolify (compose or static serve) | Lean registrar set (typically no postgres/redis) |
| `wordpress` | VPS via Coolify (multi-container: php-fpm + nginx + db + redis + backup) | WordPress-specific registrar flow |
| `chrome-extension` | **Two-faced:** FastAPI backend → Coolify. Extension → Chrome Web Store (manual upload). | Backend gets registrars; extension is browser-side |
| `mobile-app` | **Two-faced:** Backend → VPS/Supabase. Client → App Store/Play Store (manual). | Backend gets registrars; client built locally |
| `desktop-app` | **Two-faced:** Download server → Coolify. App → Electron build (local). | Download server gets registrars; installer built locally |

For two-faced types: this command handles the VPS/backend deploy only. Client-side distribution is manual (documented in project's `docs/DEPLOYMENT.md`).

## Core Philosophy

- Deploy only when ALL gates pass and implementation-validation is clean.
- `fabrik apply` handles everything (registrars, Coolify, health). Trust the automation.
- Verify AFTER deploy — don't assume success because the command returned 0.
- If deploy fails: diagnose, fix, retry. Don't leave orphan registrations.
- Zero residue: what `fabrik apply` creates, `fabrik destroy --use-state` must cleanly reverse.
- Consume deploy-plan (04) findings — shape, compose contract, registrar surface, env vars were already confirmed at planning time. This is execution of that plan.

## Acceptance Criteria

- Deploy-plan (04) consumed: shape, compose contract, registrar surface, env vars cross-checked.
- Scaffold type determines deploy path (VPS-only vs two-faced).
- Pre-deploy checks all pass before `fabrik apply` runs.
- Code pushed to GitHub before deploy (Coolify pulls from remote, not local).
- `fabrik apply` run with correct spec path.
- SSH fallback and .env pre-seed handled automatically by deployer.
- Post-deploy: `fabrik verify` + `fabrik audit-registrars` + `/health` all pass.
- Monitoring confirmed (Gatus active, no alerts, structured logs, metrics if applicable).
- Deploy failure handled with clear diagnosis path (build/health/registrar).
- Two-faced types: VPS backend deployed; client distribution documented in `docs/DEPLOYMENT.md`.
- Redeploy procedure: push → redeploy → verify.
- Zero residue: `fabrik destroy --use-state` can reverse everything.
- All 4 lifecycle stages complete (Intent → Implementation → Registration → Verification).

## Processing User Request

### Step 1: Consume Deploy Plan + Pre-Deploy Verification

Read **deploy-plan (04)** outputs — the deploy contract was already confirmed at planning time:
- Shape block (which registrars will fire)
- Compose contract (8 mandatory elements)
- Registrar surface map (9 registrars, yes/no)
- Env vars checklist (complete list)
- Coolify workaround awareness
- Destroy path verification

**Pre-deploy checks:**

- [ ] All execute batches complete (every ticket gate = success)
- [ ] `implementation-validation` passed (no Blockers remaining)
- [ ] Code pushed to GitHub: `git push origin <default-branch>` (Coolify pulls from GitHub, NOT from `/opt/`)
- [ ] `.env` values configured in Coolify dashboard — cross-check against deploy-plan's env vars checklist
- [ ] Shape block in `specs/services/<id>.yaml` matches code (verified in implementation-validation)
- [ ] Port registered in `PORTS.md`
- [ ] Local dev works: `fabrik dev -d && curl localhost:<PORT>/health` returns 200
- [ ] Compose contract matches deploy-plan's 8 mandatory elements (resource limits, platform, healthcheck, network, Traefik labels, restart, container name, no host ports)
- [ ] Destroy path verified: `fabrik destroy --use-state` will cleanly reverse this deploy (from deploy-plan Step 7)

**If ANY check fails → STOP.** Fix before deploying. Deploying broken code creates registrar state that's expensive to clean up.

### Step 2: Deploy

```bash
fabrik apply specs/services/<id>.yaml
```

What happens (automated by the orchestrator):

1. **Coolify app creation** via API — git-sourced, `build_pack=dockercompose`.
2. **`.env` pre-seed** — deployer touches the file via SSH (Coolify doesn't create it before `docker compose config`).
3. **Build trigger** — Coolify clones from GitHub, builds image.
4. **SSH fallback** — if Coolify's silent build bug (#9161) leaves app at `exited:unhealthy` after 300s, deployer SSHs to VPS, clones repo, builds using Coolify's compose.
5. **9 registrars fire** based on shape block (per deploy-plan Step 4):
   - `needs_database` → postgres DB created on `postgres-main`
   - `needs_cache` → Redis DB index assigned from `redis-assignments.json`
   - `is_public` → Gatus health monitor at `status.vps1.ocoron.com`
   - `has_persistent_data` → Backrest backup plan → Backblaze B2
   - `is_admin_dashboard` → Authelia access-control rule added
   - `has_search_feature` → MeiliSearch index created
   - `exposes_metrics` → Prometheus scrape target in `prometheus.yml`
   - Always: GlitchTip project + SENTRY_DSN injected
   - Always: Grafana deploy annotation
6. **State file written** — `.fabrik/state/<id>.json` (source of truth for destroy).

**Expected time:** 5-7 min first deploy (300s Coolify grace + build). Redeploys faster (image cached).

### Step 3: Post-Deploy Verification

```bash
fabrik verify <domain> --spec registrars     # all registrars present
fabrik audit-registrars --spec specs/services/<id>.yaml  # per-registrar status
curl -fsS https://<id>.vps1.ocoron.com/health  # service alive
```

**All must pass.** Check each:

| Check | Pass | Fail action |
|---|---|---|
| `fabrik verify` | All registrars `present` | Identify which is `missing`. Run `fabrik reconcile-all --filter <id>` to converge. |
| `/health` returns 200 | Service running, deps reachable | Check logs: `fabrik logs <id> --tail 100 --since 10m` |
| Gatus shows green | `status.vps1.ocoron.com` has the endpoint | Check Gatus config was written (SSH to VPS, inspect gatus dir) |
| GlitchTip project exists | `SENTRY_DSN` env var set in Coolify | Re-run glitchtip registrar |
| Grafana annotation | `monitor.vps1.ocoron.com` shows deploy marker | Informational — no action needed if missing |

### Step 4: Monitoring Confirmation

After deploy is verified:

- [ ] Gatus health monitor active at `status.vps1.ocoron.com` — endpoint shows UP
- [ ] No Telegram alert fired (service healthy within alert threshold)
- [ ] `fabrik logs <id> --tail 20` shows structured JSON logs (not raw print output)
- [ ] If `exposes_metrics`: `curl https://<id>.vps1.ocoron.com/metrics` returns prometheus format
- [ ] Service protected by VPS 4-layer security: iptables DOCKER-USER (only 80/443 exposed), Traefik routing, Authelia (if admin), no host port bindings

### Step 5: Handle Deploy Failure

If deploy fails at any stage:

**Build failure (Dockerfile issue):**
- Read build logs from Coolify dashboard or `fabrik logs <id> --tail 100`
- Fix Dockerfile/code locally → `git push` → `fabrik redeploy <id>`

**Health check failure (service crashes):**
- `fabrik logs <id> --since 5m` — look for startup errors
- Common causes: missing env var, wrong DB connection string (`localhost` instead of `postgres-main`), missing dependency
- Fix → push → redeploy

**Registrar failure (one or more missing):**
- `fabrik audit-registrars --spec specs/services/<id>.yaml --json` — identify which
- `fabrik reconcile-all --filter <id>` — attempt automatic fix
- If still missing → manual investigation (SSH to VPS, check registrar state)

**Nuclear option (start over):**
```bash
fabrik destroy specs/services/<id>.yaml --use-state --drop-data
# Fix the issue
fabrik apply specs/services/<id>.yaml
```

### Step 6: Redeploy (for subsequent changes)

After initial deploy, code changes follow:
```bash
git push origin <default-branch>
fabrik redeploy <id>              # Coolify re-pulls + rebuilds
fabrik verify <domain> --spec registrars  # re-verify
```

**Critical:** `git push` MUST precede `fabrik redeploy`. Coolify pulls from GitHub — it does NOT see local `/opt/` changes.

### Step 7: Confirm Deployment Complete

```
✅ Deployed: <id>.vps1.ocoron.com
   Health: 200
   Registrars: all present (postgres, gatus, glitchtip, grafana, prometheus)
   Monitoring: Gatus green, no Telegram alerts
   State: .fabrik/state/<id>.json written

   Epic lifecycle complete: Intent → Implementation → Registration → Verification ✓

   Planned (not yet built):
   - Auto-rollback wire (verify.py:394 → destroy_from_state on failure)
   - VPS watchdog agent (self-healing daemon, triggered on issues)
   - fabrik export/import (cross-VPS portability)
```
