# Frequently Asked Questions

**Last Updated:** 2026-01-04

---

## General

### What is Fabrik?

Fabrik is an infrastructure automation platform for deploying and managing web services. It provides:
- Automated WordPress site deployment
- DNS management via Cloudflare
- Docker-based service orchestration via Coolify
- AI-powered coding automation via droid exec

### What's the difference between WSL, VPS, and Supabase environments?

| Environment | Purpose | Database | Config Source |
|-------------|---------|----------|---------------|
| **WSL** | Local development | PostgreSQL localhost | `.env` file |
| **VPS** | Production (Docker) | postgres-main container | compose.yaml |
| **Supabase** | Cloud database | Supabase PostgreSQL | env vars |

All Fabrik code must work in all three environments without modification.

### Where do I find credentials?

Two locations:
1. **Project `.env`** — Project-specific credentials
2. **`/opt/fabrik/.env`** — Master credentials repository (backup)

---

## Development

### How do I start a new project?

```bash
cd /opt/fabrik && source .venv/bin/activate
python -c "from fabrik.scaffold import create_project; create_project('my-project', 'Description')"
```

For SaaS/web apps:
```bash
cp -r /opt/fabrik/templates/saas-skeleton /opt/my-project
```

### Why can't I use `/tmp/` for temporary files?

Data in `/tmp/` is:
- Shared across all projects
- Deleted on WSL restart
- Potentially cleared by other processes

Use project-local `.tmp/` instead:
```python
from pathlib import Path
TEMP_DIR = Path(__file__).parent.parent / ".tmp"
TEMP_DIR.mkdir(exist_ok=True)
```

### How do I run droid exec?

```bash
# Read-only analysis (safe)
droid exec "Analyze this code"

# With file edits
droid exec --auto low "Add comments"

# Full autonomy (CI/CD)
droid exec --auto high "Fix, test, commit"
```

See [droid-exec-usage.md](reference/droid-exec-usage.md) for complete reference.

---

## Deployment

### How do I deploy to Coolify?

1. Ensure `compose.yaml` exists in project root
2. Push to GitHub (Coolify auto-deploys via webhook)
3. Or manual deploy via Coolify UI

### What ports should I use?

| Range | Purpose |
|-------|---------|
| 3000-3099 | Frontend (Node.js) |
| 8000-8099 | Python APIs |
| 8100-8199 | Workers |

See [PORTS.md](../PORTS.md) for current allocations.

### Why isn't my service accessible externally?

Check:
1. Traefik labels in `compose.yaml`
2. DNS record exists (via dns-manager)
3. Service is healthy: `curl https://your-service.vps1.ocoron.com/health`

---

## WordPress

### How do I deploy a WordPress site?

```bash
cd /opt/fabrik && source .venv/bin/activate
fabrik wp deploy specs/my-site.yaml
```

### What's in a WordPress site spec?

```yaml
id: my-site
domain: example.com
preset: company
plugins:
  - wordpress-seo
  - contact-form-7
content:
  pages:
    - title: Home
      template: home
```

See [site-specification.md](reference/wordpress/site-specification.md) for full schema.

### How do I add a new WordPress plugin?

1. Add to preset in `templates/wordpress/presets/`
2. Or add to site spec under `plugins:`
3. Plugin must exist in `templates/wordpress/plugins/`

---

## Troubleshooting

### "Connection refused" errors

1. Check service is running: `docker ps`
2. Check correct port: `docker logs <container>`
3. Check firewall: `sudo ufw status`

### "Module not found" errors

```bash
cd /opt/fabrik
source .venv/bin/activate
pip install -e .
```

### droid exec stuck or hanging

1. Check process monitor output for diagnostics
2. Look for stdin-waiting (commands expecting input)
3. Use `--auto high` if running from Cascade

### Health check failing

Ensure health endpoint tests actual dependencies:
```python
@app.get("/health")
async def health():
    await db.execute("SELECT 1")  # Test DB
    return {"status": "ok"}
```

---

## Configuration

### How do I add a new environment variable?

1. Add to project `.env`
2. Add to `/opt/fabrik/.env` (master backup)
3. Add to `.env.example` (without real value)
4. Document in `docs/CONFIGURATION.md`

### Why isn't my env var working in Docker?

Env vars in Docker come from `compose.yaml`, not `.env`:
```yaml
services:
  api:
    environment:
      - DB_HOST=postgres-main
```

### How do I change the default model for droid exec?

Edit `~/.factory/settings.json`:
```json
{
  "defaultModel": "claude-sonnet-4-5-20250929"
}
```

---

## Services

### How do I check service status?

```bash
# All services
curl https://status.vps1.ocoron.com

# Specific service
curl https://translator.vps1.ocoron.com/health
```

### How do I restart a service?

Via Coolify UI, or:
```bash
ssh vps "docker restart <container-name>"
```

### How do I view service logs?

```bash
ssh vps "docker logs -f <container-name>"
```

---

## Related Documentation

- [QUICKSTART.md](QUICKSTART.md) — Getting started
- [CONFIGURATION.md](CONFIGURATION.md) — All settings
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Common issues
- [SERVICES.md](SERVICES.md) — Service catalog
