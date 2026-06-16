# QUICKSTART.md — {PROJECT_NAME}

**Last Updated:** YYYY-MM-DD

> **Purpose:** INTEGRATION CONTRACT — ENDPOINTS, SDKS, DOCKER WIRING. START HERE FOR INTEGRATION AND SETUP.
> **One-liner:** {What this project does in one sentence — who it's for and what problem it solves.}
> **Type:** {python-api | node-api | saas-skeleton | chrome-extension | mobile-app | desktop-app | static-site}
> **Owner:** {Team or person responsible.}
> **Last verified:** {YYYY-MM-DD}

---

## Project Identity

| Key | Value |
|-----|-------|
| **Project** | `{project-name}` |
| **Port** | `[PORT]` |
| **Production URL** | `https://{project}.vps1.ocoron.com` |
| **Local dev URL** | `http://localhost:[PORT]` |
| **Health endpoint** | `GET /health` |
| **Depends on** | `{postgres, redis, minio, external-api-name, none}` |

<!-- For services called by other services, add these rows: -->
<!-- | **Docker-internal URL** | `http://{project-name}:[PORT]` | -->
<!-- | **OpenAPI docs** | `{BASE_URL}/docs` | -->
<!-- | **Called by** | `{list of consuming services}` | -->

---

## Prerequisites

<!-- What must be installed/configured before this project can run. Delete items that don't apply. -->

- [ ] Docker + Docker Compose
- [ ] Python 3.12+ with project venv at `/opt/{project}/.venv`
- [ ] Node 22+ (for frontend/extension projects)
- [ ] `.env` file configured (copy from `.env.example`)
- [ ] Access to required services: {postgres-main, redis, etc.}

---

## Local Development (WSL)

<!-- This section applies if project uses PostgreSQL. Delete if stateless/API-only. -->

### Database Setup

This project uses PostgreSQL for local development. The database was auto-created during scaffold if `--db` flag was used.

**Database name:** `{project_name}_dev`
**Connection:** `postgresql://postgres@localhost:5432/{project_name}_dev`

**If database was not auto-created:**
```bash
sudo -u postgres psql -c "CREATE DATABASE {project_name}_dev;"
```

### Running Locally

```bash
cd /opt/{project-name}

# Use local development config
cp .env.local .env

# Run migrations (if using Alembic)
.venv/bin/alembic upgrade head

# Start development server
.venv/bin/uvicorn src.{package}.main:app --reload --port [PORT]
```

### Database Access

```bash
# Connect with psql
psql -U postgres -d {project_name}_dev

# Useful commands
\dt              # List tables
\d table_name    # Describe table
\q               # Quit
```

---

## Quick Start (Docker - VPS Deployment)

```bash
# Clone and configure
git clone {repo_url} && cd {project-name}
cp .env.example .env
# Edit .env — fill required values (see Environment Variables below)

# Start
docker compose up -d

# Verify
curl http://localhost:[PORT]/health
```

<!-- For non-Docker projects, replace with the appropriate start command: -->
<!-- Python API: /opt/{project}/.venv/bin/uvicorn src.{package}.main:app --reload --port [PORT] -->
<!-- Node: npm install && npm run dev -->
<!-- Static site: npm install && npm run build && npm run preview -->
<!-- Chrome extension: npm install && npm run build → load dist/ in chrome://extensions -->

---

## Health & Readiness

**Healthy:**
```bash
curl -sf http://localhost:[PORT]/health
# → 200
```
```json
{
  "status": "ok",
  "version": "0.1.0",
  "dependencies": {
    "postgres": "connected"
  }
}
```

**Unhealthy:**
```
→ 503 — one or more dependencies unreachable. Check response body for details.
```

---

## Primary Workflows

<!-- 3–5 most important things a user or caller does with this project.
     Adapt to project type:
     - API/service: curl examples with full request/response bodies
     - SaaS: user flows (signup → configure → use core feature)
     - Chrome extension: install → configure → usage
     - Static site: content editing → build → deploy

     Each workflow MUST include enough detail that someone can execute it without opening another doc. -->

### 1. {Primary workflow — the #1 thing users/callers do}

<!-- For APIs: full curl with request body, field table, response -->
<!-- For apps: step-by-step user flow -->

```bash
curl -X POST http://localhost:[PORT]/api/v1/{resource} \
  -H "Content-Type: application/json" \
  -d '{
    "field_1": "value",
    "field_2": 123
  }'
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `field_1` | string | Yes | — | {Description} |
| `field_2` | int | No | `100` | {Description} |

**Response (200):**
```json
{
  "success": true,
  "id": "abc-123",
  "result": "..."
}
```

> **Idempotent:** {Yes / No}

### 2. {Second workflow}

```bash
# Example workflow 2
curl -X GET http://localhost:[PORT]/api/v1/{resource}
```

### 3. {Third workflow}

```bash
# Example workflow 3
curl -X DELETE http://localhost:[PORT]/api/v1/{resource}/:id
```

### 4. {Optional fourth workflow}

### 5. {Optional fifth workflow}

<!-- Delete unused slots. -->

---

## API Reference (Compact)

<!-- For API/service projects: list every endpoint with inline request body shapes.
     For non-API projects: replace this section with "Key Commands" or "Feature Reference"
     or delete entirely if not applicable. -->

### {Domain Group 1}

| Method | Path | Request Body | Purpose |
|--------|------|-------------|---------|
| `GET` | `/api/v1/{resource}` | — | List all |
| `POST` | `/api/v1/{resource}` | `{"field_1","field_2"}` | Create (see Workflow 1) |
| `GET` | `/api/v1/{resource}/:id` | — | Get by ID |
| `DELETE` | `/api/v1/{resource}/:id` | — | Delete |

### Health & Diagnostics

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Service health (200 / 503) |

<!-- For full request/response shapes: see docs/reference/REST_API_REFERENCE.md -->

---

## Integration

<!-- How other services, agents, or automations connect to this project.
     Delete this entire section for user-facing-only projects (chrome extension, static site, desktop app)
     that are never called by other services. -->

### Authentication

<!-- State explicitly even if "none". -->

```text
No authentication required. Internal Docker network trust.
```
<!-- Or: X-API-Key: ${PROJECT_NAME_API_KEY} -->
<!-- Or: Authorization: Bearer ${TOKEN} -->

### Language Integration (copy-paste)

**Python:**

```python
import httpx, os

{PROJECT}_URL = os.getenv("{PROJECT_NAME}_URL", "http://{project-name}:[PORT]")

class {Project}Client:
    def __init__(self, base_url: str = {PROJECT}_URL):
        self.c = httpx.Client(base_url=base_url, timeout=30.0)

    def health(self) -> bool:
        return self.c.get("/health").status_code == 200

    def {primary_action}(self, payload: dict) -> dict:
        r = self.c.post("/api/v1/{resource}", json=payload)
        r.raise_for_status()
        return r.json()
```

**TypeScript:**

```typescript
const {PROJECT}_URL = process.env.{PROJECT_NAME}_URL ?? "http://{project-name}:[PORT]";

export const {project} = {
  health: async () => (await fetch(`${{{PROJECT}_URL}}/health`)).ok,
  {primaryAction}: async (payload: Record<string, unknown>) => {
    const r = await fetch(`${{{PROJECT}_URL}}/api/v1/{resource}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(`{project-name} ${r.status}: ${await r.text()}`);
    return r.json();
  },
};
```

**cURL:**

```bash
curl -sf http://{project-name}:[PORT]/health | jq .

curl -X POST http://{project-name}:[PORT]/api/v1/{resource} \
  -H "Content-Type: application/json" \
  -d '{"field_1": "value"}'
```

### Docker Compose — Caller Wiring

**Same compose stack:**

```yaml
services:
  your-service:
    environment:
      - {PROJECT_NAME}_URL=http://{project-name}:[PORT]
    depends_on:
      {project-name}:
        condition: service_healthy
    networks:
      - fabrik
```

**Cross-stack (external network):**

```yaml
services:
  your-service:
    environment:
      - {PROJECT_NAME}_URL=http://{project-name}:[PORT]
    networks:
      - fabrik

networks:
  fabrik:
    external: true
```

### Rate Limits

<!-- State explicitly. "None" is valid. -->

| Scope | Limit | Behavior |
|-------|-------|----------|
| None | — | No rate limiting applied |

### Request Tracing

<!-- Delete if not supported. -->
Every response includes `X-Request-ID`. Pass it in requests to correlate across logs.

---

## Automation

<!-- Delete patterns that don't apply. Delete entire section for non-service projects. -->

### n8n

```text
HTTP Request node:
  Method: POST
  URL: http://{project-name}:[PORT]/api/v1/{resource}
  Body (JSON): { "field_1": "{{ $json.input }}" }
  → Route: 200 → continue | 429 → Wait 60s → Retry | 5xx → Error workflow
```

### Cron

```bash
0 2 * * * curl -sf -X POST http://{project-name}:[PORT]/api/v1/maintenance/cleanup
```

---

## Error Handling

| Status | Meaning | Recovery |
|--------|---------|----------|
| `400` | Validation failed | Check `error.details` in response |
| `404` | Not found | Verify resource exists |
| `429` | Rate limited | Retry after `Retry-After` header |
| `500` | Internal error | Retry once after 5s |
| `503` | Dependency down | Check `/health` for details |

<!-- Delete codes your project never returns. Add project-specific codes. -->

**Error response shape:**
```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Human-readable description",
    "details": {}
  }
}
```

**Retry pattern:**

```python
import time, httpx

def call_with_retry(fn, max_retries=3):
    for attempt in range(max_retries):
        try:
            return fn()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 500, 503) and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
```

---

## Environment Variables

### Project config

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PORT` | No | `[PORT]` | Service port |
| `DATABASE_URL` | {Yes/No} | — | PostgreSQL connection string |
| `LOG_LEVEL` | No | `info` | Logging level |

<!-- Add all project-specific variables. -->

### For callers (if this is a service)

```env
{PROJECT_NAME}_URL=http://{project-name}:[PORT]
```

---

## Agent Context Block

<!-- Copy-paste into Cascade / Kilo sessions that need to work WITH this project (not inside it).
     Must be fully self-contained — an agent reading only this block can make correct calls.
     Delete this section for projects that are never called by other services or agents. -->

```text
## {PROJECT_NAME}
- URL: http://{project-name}:[PORT] (Docker) | https://{project}.vps1.ocoron.com (external)
- Auth: {None / X-API-Key header}
- Health: GET /health → 200 = ready, 503 = stop

Primary operations:
  - POST /api/v1/{resource} → {"field_1": "value", "field_2": 123}
  - GET /api/v1/{resource}/:id
  - DELETE /api/v1/{resource}/:id

Error shape: {"error": {"code": "...", "message": "...", "details": {...}}}
Env for callers: {PROJECT_NAME}_URL=http://{project-name}:[PORT]
```

## Agent Gotchas

| Gotcha | Why it fails | Correct approach |
|--------|-------------|------------------|
| Calling without checking `/health` | 503 during cold start | Poll `/health` first |
| Missing `Content-Type: application/json` | 400 on POST/PUT | Always include header |

<!-- Add project-specific gotchas as they surface. -->

---

## Local Development

→ Full setup: [`README.md`](../README.md)

```bash
git clone {repo_url} && cd {project-name}
cp .env.example .env
docker compose up -d
curl http://localhost:[PORT]/health
```

---

## Reference Links

<!-- Only link docs that exist. Delete unused rows. -->

| Document | Path |
|----------|------|
| Features | `./docs/FEATURES.md` |
| Configuration | `./docs/CONFIGURATION.md` |
| API reference | `./docs/reference/REST_API_REFERENCE.md` |
| Troubleshooting | `./docs/TROUBLESHOOTING.md` |
| Changelog | `./CHANGELOG.md` |
