# Kilo Task: Alpine Migration + Healthcheck Compliance

**Dispatched by:** Cascade
**Scope:** Fix 2 Alpine Dockerfiles + add healthchecks to 7 compose.yaml files
**Critical constraint:** DO NOT break existing functionality. Preserve all application logic.
**Audit date:** 2026-03-25

---

## HARD RULES

1. **NEVER change ports, environment variable names, or service names** — existing Coolify deployments depend on them
2. **NEVER modify application logic** — only touch Dockerfiles, compose.yaml, and minimal health endpoints
3. **Run `docker compose config` after every compose.yaml change** to validate YAML syntax
4. **Create backups** before modifying Dockerfiles: `cp Dockerfile Dockerfile.backup.$(date +%Y%m%d)`
5. **Each project is independent** — fix one project fully, verify, then move to next
6. **Read the project's actual source code** before adding healthchecks — find the real endpoint path and port

---

## Already Done (by Cascade — do NOT redo)

- ✅ `sync_enforcement_to_projects.py` — scripts, AGENTS.md, rules synced to all projects
- ✅ INDEX.md AUTO-GENERATED:STRUCTURE markers added to all projects
- ✅ `platform: linux/arm64` added to all 38 compose.yaml files
- ✅ P2–P10 mechanical fixes (PORTS.md, .env.example, directories, .gitignore, etc.)

**Only P0 and P1 remain.**

---

## P0: Alpine → Bookworm-Slim (2 projects)

These Dockerfiles use Alpine which breaks on the ARM64 VPS. Migrate to bookworm-slim.

### emailgateway (/opt/emailgateway)

1. `cp /opt/emailgateway/Dockerfile /opt/emailgateway/Dockerfile.backup.$(date +%Y%m%d)`
2. Read the current Dockerfile carefully
3. Replace ALL `FROM node:20-alpine` → `FROM node:22-bookworm-slim`
4. Replace `apk add --no-cache <pkg>` → `apt-get update && apt-get install -y --no-install-recommends <pkg> && rm -rf /var/lib/apt/lists/*`
5. Replace `apk del <pkg>` → `apt-get purge -y <pkg>` (if present)
6. Keep ALL other instructions (COPY, RUN npm, EXPOSE, CMD, etc.) exactly the same
7. Verify: `cd /opt/emailgateway && docker compose config`

### file-api (/opt/file-api)

1. `cp /opt/file-api/Dockerfile /opt/file-api/Dockerfile.backup.$(date +%Y%m%d)`
2. Same migration as emailgateway
3. Verify: `cd /opt/file-api && docker compose config`

---

## P1: Missing Healthchecks in compose.yaml (7 projects)

For each project below:

1. **Read the app source** to find the actual health endpoint:
   - Look for `@app.get("/health")` or `router.get("/health")` in Python
   - Look for `app.get('/health')` or similar in Node.js
   - If no health endpoint exists, add a minimal one (see templates below)
2. **Read compose.yaml** to find the correct internal port (look at `PORT` env var default)
3. **Add healthcheck block** to compose.yaml at the same indent as `build:` / `environment:`
4. **Verify:** `cd /opt/<project> && docker compose config`

### Projects

| # | Project | Path | Stack | Default Port |
|---|---------|------|-------|-------------|
| 1 | captcha | /opt/captcha | Python/FastAPI | 8000 |
| 2 | dns-manager | /opt/dns-manager | Python/FastAPI | 8001 |
| 3 | emailgateway | /opt/emailgateway | Node.js/Express | 3000 |
| 4 | file-api | /opt/file-api | Node.js | 3000 |
| 5 | file-worker | /opt/file-worker | Python | 8000 |
| 6 | proxy | /opt/proxy | Python/FastAPI | 8000 |
| 7 | translator | /opt/translator | Python/FastAPI | 8000 |

### Healthcheck template for compose.yaml

```yaml
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:<PORT>/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

Replace `<PORT>` with the actual port from each project's compose.yaml.

### Minimal health endpoint (if project has none)

**Python/FastAPI:**
```python
@app.get("/health")
async def health():
    return {"status": "ok", "service": "<project-name>"}
```

**Node.js/Express:**
```javascript
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: '<project-name>' });
});
```

Add health endpoints to the project's existing main entry file — do NOT create new files.

---

## Execution Order

1. emailgateway — P0 (Alpine fix) + P1 (healthcheck)
2. file-api — P0 (Alpine fix) + P1 (healthcheck)
3. captcha — P1 only
4. dns-manager — P1 only
5. file-worker — P1 only
6. proxy — P1 only
7. translator — P1 only

---

## Verification

After ALL fixes:
```bash
for proj in emailgateway file-api captcha dns-manager file-worker proxy translator; do
    echo "=== $proj ==="
    cd /opt/$proj && docker compose config > /dev/null 2>&1 && echo "  compose: OK" || echo "  compose: FAIL"
done
```

---

## What NOT to Touch

- Any file not listed above
- Port numbers, service names, environment variable names
- README.md, CHANGELOG.md, INDEX.md, AGENTS.md, scripts/
- Existing tests or test configurations
- Database schemas
