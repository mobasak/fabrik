# AGENTS.md — Fabrik Identity & Knowledge (Traycer Only)

**Last Updated:** 2026-03-28
**Read by:** Traycer only (auto-loaded every interaction)
**Coding agents:** Read `AGENTS-compact.md` via `opencode.json`

> For all development work, use the **Fabrik Development Workflow**.
> Owner drops pre-research at `docs/development/plans/00-research.md` after external research with ChatGPT/Claude/Gemini.

---

## Owner & Working Style

- **Solo developer** — Özgür Başak, 46, Turkish electronics engineer & entrepreneur
- **Capacity:** ~50 focused hours/week
- **Budget:** Limited — prefer free/cheap but good, fast tools, maximize ROI
- **Philosophy:** Fast but good. Ship fast, iterate, automate. No over-engineering.
- **Full profile:** `docs/owner_ozgur_basak.md`

## Development Environment

- **Dev machine:** WSL (Ubuntu 24.04) on Windows
- **IDE:** Windsurf (Cascade AI agents for interactive work)
- **Coding agents:** Windsurf Cascade (manual/interactive) · Kilo CLI (YOLO) · Local LLM agents
- **VPS:** ARM64 (aarch64) Ubuntu at 172.93.160.197 — all builds must be ARM-compatible
- **Deployment:** Coolify on VPS (Docker Compose) — `fabrik apply` automates DNS + Coolify + monitoring
- **Database:** PostgreSQL on VPS (default) · Supabase (when managed auth/realtime/pgvector needed)
- **Reverse proxy:** Traefik (managed by Coolify) — HTTPS/SSL via Let's Encrypt
- **Domains:** `*.vps1.ocoron.com` — managed by dns-manager (supports Namecheap, Cloudflare, auto-purchase) and others
- **Monitoring:** Uptime Kuma · Netdata · Grafana + Prometheus + Loki (on vps)

### Local LLM Agents

| Agent | Hardware | Memory Usage | Speed | Stability |
|-------|----------|--------------|-------|-----------|
| fabrik-coder | hybrid-cpu | ~19GB (8GB VRAM + 11GB RAM) | Moderate (~15-25 tok/s) | Stable |
| fabrik-reviewer | cpu | ~42GB RAM | Slow (~8-12 tok/s) | High memory pressure ⚠️ |
| fabrik-fixer | hybrid-gpu | ~9GB (8GB VRAM + 1GB RAM) | Fast (~40-60 tok/s) | Stable |
| fabrik-docs | gpu | ~5GB VRAM | Instant (~80-100 tok/s) | Rock solid |

## Tech Stack Defaults

| Layer | Default | Deviate When |
|-------|---------|-------------|
| Backend | Python + FastAPI + Uvicorn | Node.js for web-adjacent workers |
| Frontend | Next.js 14 + TypeScript + Tailwind | — always use this |
| Database | PostgreSQL 16 (VPS, Coolify-managed) | Supabase for managed auth/realtime/pgvector |
| Background jobs | PostgreSQL jobs table + worker | Redis queue for high throughput |
| AI/LLM | Kilo CLI free tiers → OpenAI/Anthropic APIs | Local Ollama for offline/free |
| Local LLM | Ollama (localhost:11434) | See `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` |
| Base images | `python:<current-stable>-slim-bookworm`, `node:<current-LTS>-bookworm-slim` | Never Alpine |
| PDF | Gotenberg (self-hosted) | WeasyPrint for simple cases |
| Search | MeiliSearch (self-hosted) | PostgreSQL FTS for simple cases |
| Notifications | Apprise (self-hosted) | Direct API for single-channel |
| Object storage | MinIO (self-hosted, S3-compatible) | Backblaze B2 for cold storage |

## Infrastructure Services (Deployed on VPS)

| Service | URL | Purpose |
|---------|-----|---------|
| Coolify | coolify.vps1.ocoron.com | Deployment control plane |
| PostgreSQL | (internal) | Shared database |
| Redis | (internal) | Shared cache |
| Uptime Kuma | status.vps1.ocoron.com | Uptime monitoring |
| Netdata | netdata.vps1.ocoron.com | Server metrics |
| Grafana | monitor.vps1.ocoron.com | Dashboards |
| Duplicati | backup.vps1.ocoron.com | PostgreSQL backup to B2 |
| Browserless | browser.vps1.ocoron.com | Headless Chrome farm |
| Gotenberg | pdf.vps1.ocoron.com | PDF generation API |
| MinIO | s3.vps1.ocoron.com | Object storage |
| MeiliSearch | search.vps1.ocoron.com | Full-text search |
| Apprise | notify.vps1.ocoron.com | Multi-channel notifications |
| n8n | auto.vps1.ocoron.com | Workflow automation |

## Fabrik Microservices (Custom-Built, on VPS)

| Service | Port | Purpose |
|---------|------|---------|
| Translator | 8000 | DeepL + Azure translation |
| Captcha | 8000 | Anti-Captcha solving |
| Proxy | 8000 | Webshare.io proxy management |
| DNS Manager | 8001 | Namecheap DNS API |
| File API | 8004 | File operations |
| Image Broker | 8010 | AI image generation (FLUX) |
| Email Gateway | 3000 | Resend + SES email sending |

### Microservice URL Patterns

| Environment | Pattern |
|-------------|---------|
| WSL dev | `http://localhost:PORT` |
| VPS internal | `http://service-name:PORT` |
| VPS external | `https://service.vps1.ocoron.com` |

## Active Projects

Full auto-generated project list (39 projects) in `docs/BUSINESS_MODEL.md` under ``.

## Planning Constraints

Before creating any plan, verify:

1. **Solo developer** — no team handoff, one person executes everything
2. **ARM64 VPS** — all Docker images must support `linux/arm64`
3. **Budget-conscious** — prefer free Kilo models, free-tier APIs, self-hosted over SaaS
4. **Existing services** — check if a Fabrik microservice already solves the need before building
5. **Prebuilt containers** — check `prebuilt-app-containers.md` before writing custom code
6. **Port conflicts** — check `PORTS.md` before assigning ports
7. **Coolify deployment** — all services deploy as Docker Compose apps via Coolify
8. **No Alpine** — use `-slim-bookworm` base images only
9. **Module dependencies** — if a project needs an incomplete Fabrik module, plan module completion first. Check module status in `docs/BUSINESS_MODEL.md` before planning dependent work
10. **DNS** — dns-manager handles Namecheap + Cloudflare + domain purchasing automatically

## Environment Constraints

- **Runtime:** WSL (Ubuntu). Linux paths and commands only. Never Windows tooling.
- **Scaffold:** Fixed structure — do not reorganize, flatten, or add top-level directories.
- **pip:** Never bare `pip install`. Always `/opt/<project>/.venv/bin/pip install`
- **Env vars:** Never hardcode. Always `os.getenv('KEY', 'default')`
- **Base images:** `python:<current-stable>-slim-bookworm` / `node:<current-LTS>-bookworm-slim`. Never Alpine.
- **Deployment:** Linux VPS via Coolify. ARM-compatible builds required.
- **Ports:** Python 8000–8099 / Frontend 3000–3099. Register new ports in `PORTS.md`.
- **Conflicts:** If task contradicts project state — stop and return to Traycer. Do not silently overwrite.

## Code Patterns

### Python / FastAPI
```python
# Config — always function-level, never class/module-level
def get_db_url() -> str:
    return f"postgresql://{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}/db"

# Health — always test real dependencies
@app.get("/health")
async def health():
    await db.execute("SELECT 1")
    return {"status": "ok", "db": "connected"}

# Temp files — never /tmp/
TEMP_DIR = Path(__file__).parent.parent / ".tmp"
```

### Docker
```dockerfile
FROM python:<current-stable>-slim-bookworm
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1
```

### compose.yaml
```yaml
networks:
  coolify:
    external: true
environment:
  - DB_HOST=postgres-main   # service name, never localhost
```

## Documentation Rules

- **CHANGELOG.md:** Entry required for every code change. Format: `### Added/Changed/Fixed — Title (YYYY-MM-DD)`
- **README.md features table:** Every new feature added with ✅/🚧/❌ status
- **New `.md` files:** Blocked outside allowlist. Allowed: root files, scaffold docs, `docs/development/plans/YYYY-MM-DD-plan-<n>.md`, `docs/archive/**`
- **`.env.example`:** Authoritative variable reference. `docs/CONFIGURATION.md` is a guide only.

## Sensitive Data Protection

Before modifying any credentials file (`.env`, `*.key`, `*.pem`, `secrets/`, `.ssh/`):

```bash
cp <file> <file>.backup.$(date +%Y%m%d-%H%M%S)
```

**Forbidden without dry-run:** Destructive scripts on production data.
**Forbidden without full diff approval:** Any credentials change.

## Quality Gates

| Gate | Script | Purpose |
|------|--------|---------|
| Kilo Review | `scripts/kilo_code_review.py` | AI-powered code review, reports BLOCKER/MAJOR/MINOR findings |
| Documentator | `scripts/kilo_docs_enforcer.py` | AI documentation enforcement, auto-generates CHANGELOG/README |
| Final Gate (Tier 1 — lean) | `scripts/final_gate.py --lean` | Showstoppers only: syntax, secrets, schema sync |
| Final Gate (Tier 2 — full) | `scripts/final_gate.py` | Full quality: static analysis + consistency checks |
| Final Gate (Tier 3 — systemic) | `scripts/final_gate.py --systemic` | Repo health: docker, ports, docs sprawl, deps sync |

## Scaffold Types

| Type | Template | Stack |
|------|----------|-------|
| python-api | templates/scaffold/ | FastAPI + Uvicorn + Docker |
| saas-skeleton | templates/saas-skeleton/ | Next.js 14 + TypeScript + Tailwind |
| node-api | templates/node-api/ | Node.js API + Docker |
| file-api | templates/file-api/ | File operations API |
| file-worker | templates/file-worker/ | Background file worker |
| wordpress | templates/wordpress/ | WordPress + WP-CLI |
| docusaurus | templates/docusaurus/ | Documentation site |
| chrome-extension | templates/chrome-extension/ | Chrome extension |
| mobile-app | templates/mobile-app/ | React Native app |
| desktop-app | templates/desktop-app/ | Electron app |

## Reference Documents

| Document | Path | Use When |
|----------|------|----------|
| Project Portfolio | docs/BUSINESS_MODEL.md | Full project list with statuses |
| AI Taxonomy | docs/reference/AI_TAXONOMY.md | Selecting AI tools/models |
| Local LLM | docs/reference/LOCAL_LLM_INFRASTRUCTURE.md | Ollama setup, model assignments |
| Stack Decision Guide | docs/reference/technology-stack-decision-guide.md | Choosing tech stack for new project |
| Prebuilt Containers | docs/reference/prebuilt-app-containers.md | Ready-made Docker solutions |
| Database Strategy | docs/reference/DATABASE_STRATEGY.md | Database, migration, vector storage |
| Owner Profile | docs/owner_ozgur_basak.md | Owner background, goals |
| Port Allocations | PORTS.md | Assigning ports to new services |
| SaaS UI Patterns | docs/reference/Modern GUI Approaches for a Lean, Fast, Effective, Low-Confusion SaaS Web App.md | Planning SaaS frontend |
| Chrome Extension UI | docs/reference/Modern GUI Approaches for Chrome Extensionst.md | Planning Chrome extensions |
| Mobile UI | docs/reference/Modern Mobile GUI Approaches for Android and iOS.md | Planning mobile apps |
