# Deployment — [Project Name]

**Last Updated:** YYYY-MM-DD

---

## Deployment Target

<!-- Fill in during project setup with Traycer. Delete targets that don't apply. -->

| Component | Target | URL |
|-----------|--------|-----|
| **Application** | {VPS (Docker Compose via `fabrik apply`) / Vercel / Static host} | `https://{project}.vps1.ocoron.com` |
| **Database** | {VPS postgres-main / Supabase / SQLite} | {connection info in .env} |
| **Cache** | {VPS redis-main / none} | {connection info in .env} |
| **DNS** | Cloudflare (via site-provisioner) | Automatic |
| **SSL** | {Let's Encrypt (Traefik) / Vercel / Cloudflare} | Automatic |
| **Monitoring** | Gatus | `https://status.vps1.ocoron.com` |

---

## Deploy

### Automated (default)

```bash
fabrik apply [project-name]
# DNS → env vars → SSH to VPS → docker compose up -d → domain + SSL (Traefik) → health check
```

### Manual (SSH + Docker Compose)

1. SSH to the VPS, `cd` into the project's deploy dir
2. Pull the GitHub repo (`git pull`)
3. Set env vars from `.env.example` in `.env`
4. `docker compose up -d` — Traefik picks up the labels and provisions the domain + SSL
5. Verify `GET /health`

### Vercel (if applicable)

```bash
vercel --prod
# Or: push to main → auto-deploys via GitHub integration
```

### Updates

```bash
git push origin main
fabrik redeploy [project-name]
# The VPS runs `git pull` from the GitHub remote, then `docker compose up -d`.
# (Vercel projects auto-deploy on push.)
```

---

## Services

| Service | Port | Health | Purpose |
|---------|------|--------|---------|
| {web} | {see project.yaml} | `GET /health` | {Main API} |
| {worker} | — | — | {Background jobs} |

<!-- Delete worker row if no background services. -->

---

## Database

| Environment | Connection | Notes |
|-------------|------------|-------|
| Dev (WSL) | `postgresql://localhost:5432/[project]_dev` | Local PostgreSQL |
| Prod (VPS) | `postgresql://[project]:$DB_PASSWORD@postgres-main:5432/[project]` | Shared `postgres-main` container |
| Supabase | `postgresql://postgres.$REF:$PASSWORD@pooler.supabase.com:6543/postgres` | Connection pooler |
| SQLite | `sqlite:///data/[project].db` | File-based, no server |

<!-- Delete rows that don't apply. Connection strings are in .env, not hardcoded here. -->

---

## Infrastructure Rules

- **Base images:** `python:3.12-slim-bookworm` or `node:22-bookworm-slim` — never Alpine
- **Architecture:** `linux/amd64` required — VPS is x86_64
- **Networking:** Docker service names (`postgres-main`, `redis-main`), never `localhost` in production
- **Health checks:** Every service must have `/health` that tests actual dependencies
- **Ports:** Registered in `PORTS.md` — Traefik handles external 80/443 routing

---

## Rollback

```bash
# VPS: a failed `fabrik redeploy` auto-reverts to the last-known-good commit
#      (SSH deployer captures a rollback point before mutating). To roll back a
#      healthy deploy manually: git checkout <previous-sha> on the VPS → fabrik redeploy
# Vercel: vercel rollback
# Database: apply rollback migration from db/schema.sql
```

---

## Monitoring

| Check | Endpoint | Expected |
|-------|----------|----------|
| Health | `/health` | `{"status": "ok", "dependencies": {...}}` |

Gatus endpoint auto-configured by `fabrik apply` (from the spec's `health` block). Manual setup: add an HTTP check at `https://{project}.vps1.ocoron.com/health`.
