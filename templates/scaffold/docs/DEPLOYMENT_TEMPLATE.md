# Deployment — [Project Name]

**Last Updated:** YYYY-MM-DD

---

## Deployment Target

<!-- Fill in during project setup with Traycer. Delete targets that don't apply. -->

| Component | Target | URL |
|-----------|--------|-----|
| **Application** | {VPS (Coolify) / Vercel / Static host} | `https://{project}.vps1.ocoron.com` |
| **Database** | {VPS postgres-main / Supabase / SQLite} | {connection info in .env} |
| **Cache** | {VPS redis / none} | {connection info in .env} |
| **DNS** | Cloudflare (via dns-manager) | Automatic |
| **SSL** | {Let's Encrypt (Coolify) / Vercel / Cloudflare} | Automatic |
| **Monitoring** | Uptime Kuma | `https://status.vps1.ocoron.com` |

---

## Deploy

### Automated (default)

```bash
fabrik apply [project-name]
# DNS → Coolify app → env vars → domain + SSL → health check → deploy
```

### Manual (Coolify UI)

1. Create app in Coolify (`coolify.vps1.ocoron.com`) → Docker Compose build
2. Connect GitHub repo
3. Set env vars from `.env.example`
4. Add domain → SSL auto-configures
5. Deploy

### Vercel (if applicable)

```bash
vercel --prod
# Or: push to main → auto-deploys via GitHub integration
```

### Updates

```bash
git push origin main
# Auto-deploys if webhook configured, otherwise manual deploy via Coolify/Vercel UI
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
| Prod (VPS) | `postgresql://[project]:$DB_PASSWORD@postgres-main:5432/[project]` | Coolify-managed |
| Supabase | `postgresql://postgres.$REF:$PASSWORD@pooler.supabase.com:6543/postgres` | Connection pooler |
| SQLite | `sqlite:///data/[project].db` | File-based, no server |

<!-- Delete rows that don't apply. Connection strings are in .env, not hardcoded here. -->

---

## Infrastructure Rules

- **Base images:** `python:3.12-slim-bookworm` or `node:22-bookworm-slim` — never Alpine
- **Architecture:** `linux/amd64` required — VPS is x86_64
- **Networking:** Docker service names (`postgres-main`, `redis`), never `localhost` in production
- **Health checks:** Every service must have `/health` that tests actual dependencies
- **Ports:** Registered in `PORTS.md` — Coolify/Traefik handles external 80/443 routing

---

## Rollback

```bash
# Coolify: select previous deployment → redeploy
# Vercel: vercel rollback
# Database: apply rollback migration from db/schema.sql
```

---

## Monitoring

| Check | Endpoint | Expected |
|-------|----------|----------|
| Health | `/health` | `{"status": "ok", "dependencies": {...}}` |

Uptime Kuma auto-configured by `fabrik apply`. Manual setup: add HTTP check at `https://{project}.vps1.ocoron.com/health`.
