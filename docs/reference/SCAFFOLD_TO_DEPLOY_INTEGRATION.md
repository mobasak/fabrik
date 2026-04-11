# Scaffold → Deploy Integration Analysis

**Date:** 2026-04-10
**Purpose:** Gap analysis and recommendations for AI agents creating deploy-ready projects

---

## Executive Summary

**Current State:** `fabrik scaffold` and `fabrik apply` are **disconnected workflows**.

- **Scaffold** creates project structure at `/opt/project-name/` with its own `compose.yaml`
- **Deploy** renders a separate `compose.yaml` from templates and deploys to Coolify
- **Gap:** No automatic spec file generation, no bridge between the two systems

**Impact on AI Agents:**
- Must manually create spec files after scaffolding
- Must duplicate env vars between project `compose.yaml` and spec `env:` block
- Must understand two separate template systems
- No validation that scaffolded projects are deployment-ready

---

## Type Alignment Audit

### Scaffold Types (11)

From `/opt/fabrik/src/fabrik/scaffold.py`:

```python
SCAFFOLD_TYPES = {
    "python-api",
    "saas-skeleton",
    "node-api",
    "file-api",
    "file-worker",
    "wordpress",
    "docusaurus",
    "chrome-extension",
    "mobile-app",
    "desktop-app",
    "static-site",
}
```

### Deploy Templates (9)

From `/opt/fabrik/templates/` (directories with `compose.yaml.j2`):

```
✅ desktop-app/compose.yaml.j2
✅ docusaurus/compose.yaml.j2
✅ file-api/compose.yaml.j2
✅ file-worker/compose.yaml.j2
✅ mobile-app/compose.yaml.j2
✅ next-tailwind/compose.yaml.j2  ← alias for saas-skeleton?
✅ node-api/compose.yaml.j2
✅ wordpress/base/compose.yaml.j2
✅ saas-skeleton/ (needs verification)
```

### **✅ ALL Deploy Templates Implemented (2026-04-10)**

| Scaffold Type | Deploy Template | Status | Port | Notes |
|---------------|-----------------|--------|------|-------|
| `python-api` | ✅ Created | **COMPLETE** | 8000 | FastAPI/Uvicorn, PostgreSQL/Redis support |
| `saas-skeleton` | ✅ Created | **COMPLETE** | 3000 | Next.js, Supabase auth support |
| `chrome-extension` | ✅ Created | **COMPLETE** | 8000 | Backend service with CORS for extensions |
| `static-site` | ✅ Created | **COMPLETE** | 3000 | Next.js static generation |
| `node-api` | ✅ Existing | **COMPLETE** | 3000 | Express/Fastify |
| `file-api` | ✅ Existing | **COMPLETE** | 3000 | Node file operations |
| `file-worker` | ✅ Existing | **COMPLETE** | N/A | Background worker |
| `wordpress` | ✅ Existing | **COMPLETE** | 80 | WordPress + MySQL |
| `docusaurus` | ✅ Existing | **COMPLETE** | 3000 | Documentation site |
| `mobile-app` | ✅ Existing | **COMPLETE** | 3000 | React Native backend |
| `desktop-app` | ✅ Existing | **COMPLETE** | 3000 | Electron backend |

**✅ 100% Coverage:** All 11 scaffold types now have corresponding deploy templates.

---

## Current Workflow (Manual)

### Step 1: Scaffold Project

```bash
cd /opt/fabrik
fabrik scaffold my-api --type python-api --description "My API service"
```

**Output:**
- `/opt/my-api/` with full project structure
- `compose.yaml` hardcoded for local dev
- `project.yaml` with metadata
- Port allocated from `PORTS.md`

### Step 2: Create Spec File

AI agent must:
1. Create spec file using `fabrik new` or manually
2. Copy env vars from `/opt/my-api/compose.yaml`
3. Add secrets policy
4. Configure resources, health checks
5. Set domain

**Option A: Use fabrik new (creates spec file skeleton)**
```bash
fabrik new my-api --template python-api --domain api.vps1.ocoron.com --output specs/services
```

**Option B: Manual creation**
```yaml
id: my-api
kind: service
template: python-api
domain: api.vps1.ocoron.com

env:
  LOG_LEVEL: INFO
  # ... copy from project compose.yaml

secrets:
  required:
    - DATABASE_PASSWORD
  from_env:
    - API_KEY
  from_file:
    GOOGLE_CREDENTIALS: /path/to/credentials.json

resources:
  memory: 512M
  cpu: "1"

health:
  path: /health
  interval: 30s
```

### Step 3: Deploy

```bash
fabrik apply specs/services/my-api.yaml -s DATABASE_PASSWORD=xxx -s API_KEY=yyy
```

---

## Root Cause Issues

### 1. **Manual Spec File Creation**

- Scaffold type: `python-api`
- Deploy template: ✅ exists
- Gap: Scaffold doesn't auto-generate spec file
- Workaround: Use `fabrik new` or create spec manually

### 2. **Compose.yaml Duplication**

Scaffolded project has:
```yaml
# /opt/my-api/compose.yaml
services:
  my-api:
    environment:
      - DATABASE_URL=postgresql://...
      - LOG_LEVEL=INFO
```

Spec must duplicate all env vars:
```yaml
# /opt/fabrik/specs/services/my-api.yaml
env:
  DATABASE_URL: postgresql://...  # ← Manual copy
  LOG_LEVEL: INFO
```

### 3. **No Spec Auto-Generation**

`fabrik scaffold` doesn't create a spec file. AI agents must:
- Manually create spec file
- Know the spec schema (17 fields, 14 nested models)
- Map scaffold type → deploy template name (error-prone)

### 4. **Port Allocation Disconnect**

- Scaffold allocates port → writes to `project.yaml`
- Spec doesn't reference `project.yaml` port
- Deploy template doesn't use scaffolded port
- Result: AI must manually copy port to spec or compose.yaml

---

## Recommended Changes

### **Priority 1: Create ALL Missing Deploy Templates**

**Goal:** Complete 1:1 coverage - every scaffold type MUST have a corresponding deploy template.

**Action:** Create the 3 missing templates.

#### 1. python-api Template (CRITICAL - 2 hours) ✅ DONE

```bash
mkdir -p /opt/fabrik/templates/python-api
```

**Status:** ✅ Completed 2026-04-10 - template now exists at `/opt/fabrik/templates/python-api/compose.yaml.j2`

**`compose.yaml.j2`:**
```yaml
services:
  {{ spec.id }}:
    build:
      context: .
      dockerfile: Dockerfile
    platform: linux/amd64
    container_name: {{ spec.id }}
    restart: unless-stopped
    {% if spec.expose.http and not spec.expose.internal_only %}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.{{ spec.id }}.rule=Host(`{{ domain }}`)"
      - "traefik.http.routers.{{ spec.id }}.entrypoints=websecure"
      - "traefik.http.routers.{{ spec.id }}.tls.certresolver=letsencrypt"
      - "traefik.http.services.{{ spec.id }}.loadbalancer.server.port=8000"
    {% endif %}
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      {% for key, value in env.items() %}
      - {{ key }}={{ value | env_escape }}
      {% endfor %}
      {% if depends.postgres %}
      - DATABASE_URL=${DATABASE_URL:-postgresql://postgres:${POSTGRES_PASSWORD}@postgres-main:5432/{{ depends.postgres }}}
      {% endif %}
      {% if depends.redis %}
      - REDIS_URL=${REDIS_URL:-redis://redis-main:6379/0}
      {% endif %}
    {% if volumes %}
    volumes:
      {% for vol in volumes %}
      - {{ vol.name }}:{{ vol.path }}
      {% endfor %}
    {% endif %}
    deploy:
      resources:
        limits:
          memory: {{ resources.memory }}
          cpus: '{{ resources.cpu }}'
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000{{ health.path if health else '/health' }}"]
      interval: {{ health.interval if health else '30s' }}
      timeout: {{ health.timeout if health else '10s' }}
      retries: {{ health.retries if health else 3 }}
    networks:
      - coolify

{% if volumes %}
volumes:
  {% for vol in volumes %}
  {{ vol.name }}:
  {% endfor %}
{% endif %}

networks:
  coolify:
    external: true
```

**`defaults.yaml`:**
```yaml
env:
  LOG_LEVEL: INFO
  PYTHONUNBUFFERED: "1"
```

#### 2. chrome-extension Template (HIGH - 1.5 hours) ✅ DONE

```bash
mkdir -p /opt/fabrik/templates/chrome-extension
```

**Status:** ✅ Completed 2026-04-10 - template now exists at `/opt/fabrik/templates/chrome-extension/compose.yaml.j2`

**Implementation:** Uses Traefik middleware labels for CORS (accesscontrolallowmethods, accesscontrolalloworigin, accesscontrolallowheaders, accesscontrolmaxage) and shell syntax `${CORS_ORIGINS:-chrome-extension://*}` for env var defaults.

**Note:** Extension frontend is deployed separately via Chrome Web Store.

#### 3. static-site Template (MEDIUM - 0.5 hours) ✅ DONE

```bash
mkdir -p /opt/fabrik/templates/static-site
```

**Status:** ✅ Completed 2026-04-10 - template now exists at `/opt/fabrik/templates/static-site/compose.yaml.j2`

**Impact:**
- ✅ All 11 scaffold types have deploy templates
- ✅ AI agents can deploy ANY scaffolded project
- ✅ No more template name mismatches

---

### **Priority 2: Auto-Generate Spec Files During Scaffold**

**Action:** Modify `create_project()` in `scaffold.py` to generate spec file.

**Implementation:**

```python
def create_project(...):
    # ... existing scaffold logic ...

    # NEW: Auto-generate spec file
    if should_generate_spec(project_type):
        spec_file = FABRIK_ROOT / "specs" / "services" / f"{name}.yaml"
        spec_content = _generate_spec_from_project(
            project_id=name,
            project_type=project_type,
            domain=f"{name}.vps1.ocoron.com",
            port=host_port,
            env_vars=_extract_env_from_compose(project_dir / "compose.yaml"),
        )
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        spec_file.write_text(spec_content)
        click.echo(f"✅ Generated deployment spec: {spec_file}")
```

**Benefit:** AI agents get a ready-to-deploy spec file automatically.

---

### **Priority 3: Enhance fabrik new to Auto-Read Env Vars**

**Status:** ✅ Implemented (2026-04-11)

`fabrik scaffold` now automatically:
- Detects secrets from `.env.example` using pattern matching
- Populates `from_env` field in generated specs
- Avoids duplication by not populating `required` when `from_env` is used

**Secret detection patterns:**
- Includes: `_KEY`, `_SECRET`, `_PASSWORD`, `_TOKEN`, `_CREDENTIALS`, `_API_KEY`, `_API_TOKEN`, `_PRIVATE_KEY`
- Excludes: `PORT`, `HOST`, `LOG_LEVEL`, `DEBUG`, `ENV`, `NODE_ENV`, `PYTHON_ENV`, `DATABASE_URL`, `REDIS_URL`

**Current behavior:**
```bash
fabrik scaffold my-api --type python-api
# Output: specs/services/my-api.yaml with from_env auto-populated from .env.example
```

**Deployment workflow:**
```bash
# Scaffold project (auto-detects secrets from .env.example)
fabrik scaffold my-api --type python-api

# Develop project in /opt/my-api/
# Set secrets in /opt/my-api/.env
# Deploy - secrets auto-loaded from .env file
fabrik apply /opt/fabrik/specs/services/my-api.yaml
```

**Secret loading precedence:**
1. Command-line `-s` flags (highest)
2. Project `.env` file
3. Environment variables (lowest)

**Result:** All new projects are deployment-ready with automatic secret loading from project `.env` files. No manual environment variable setting required.

---

### **Priority 4: Validate Scaffold → Deploy Compatibility**

**Action:** Add validation step to ensure scaffolded projects can deploy.

```python
def validate_deployment_ready(project_path: Path) -> list[str]:
    """Check if project is ready for fabrik apply."""
    issues = []

    # Check 1: Deploy template exists
    project_yaml = yaml.safe_load((project_path / "project.yaml").read_text())
    project_type = project_yaml.get("type")
    if not template_exists(project_type):
        issues.append(f"No deploy template for type: {project_type}")

    # Check 2: Required env vars present
    if not (project_path / ".env.example").exists():
        issues.append("Missing .env.example")

    # Check 3: Health endpoint exists
    # ... check src/ for /health route

    return issues
```

**Add to scaffold completion:**

```python
# After scaffold completes
issues = validate_deployment_ready(project_dir)
if issues:
    click.echo("⚠️  Deployment readiness issues:")
    for issue in issues:
        click.echo(f"  - {issue}")
```

---

### **Priority 5: Unified Template System**

**Action:** Merge scaffold templates and deploy templates into single source.

**Current:**
- Scaffold templates: `/opt/fabrik/templates/scaffold/` (markdown, base files)
- Deploy templates: `/opt/fabrik/templates/{type}/compose.yaml.j2`

**Proposed:**
```
/opt/fabrik/templates/
├── python-api/
│   ├── scaffold/           # Files for `fabrik scaffold`
│   │   ├── README.md.j2
│   │   ├── pyproject.toml.j2
│   │   └── ...
│   ├── deploy/             # Files for `fabrik apply`
│   │   ├── compose.yaml.j2
│   │   ├── Dockerfile.j2
│   │   └── defaults.yaml
│   └── spec.yaml.j2        # Spec template
```

**Benefit:** One template directory per type, clearer for AI agents.

**⚠️ Risk Assessment:** This is an 8-hour refactor that touches:
- Scaffold engine (`scaffold.py`)
- All 11 type-specific scaffolders
- Template renderer
- All existing template paths

For a solo developer, this is **high-risk for low immediate gain**. Recommend deferring until after P2+P3 automation is complete and validated.

---

## AI Agent Guidance (Interim)

Until P2 (auto-generate specs) is implemented, AI agents should:

### When Creating New Projects

1. **Use `fabrik scaffold`** for project creation
2. **Create spec file** using `fabrik new` or manually at `/opt/fabrik/specs/services/{name}.yaml`
3. **Use 1:1 template mapping** (no workarounds needed - all templates exist):

| Scaffold Type | Deploy Template |
|---------------|----------------|
| `python-api` | `python-api` ✅ |
| `chrome-extension` | `chrome-extension` ✅ |
| `static-site` | `static-site` ✅ |
| `saas-skeleton` | `saas-skeleton` ✅ |
| All others | Same name ✅ |

4. **Copy env vars** from project `compose.yaml` to spec `env:` block
5. **Extract secrets** from `.env.example` to spec `secrets.required:` list
6. **Test with `fabrik plan`** before deploying

**Special Case: file-worker**
- Requires Supabase (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) and Cloudflare R2 (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_ENDPOINT) - not generic PostgreSQL/Redis
- These are hardcoded as required (${VAR:?}) in the template
- Not suitable for generic worker scaffolding without modification

### Spec File Example

For `python-api`:

```yaml
id: my-api
kind: service
template: python-api
domain: api.vps1.ocoron.com

env:
  # Copy from /opt/my-api/compose.yaml
  LOG_LEVEL: INFO
  DEBUG: "false"

secrets:
  required:
    - DATABASE_PASSWORD  # From .env.example
    - API_KEY

resources:
  memory: 512M
  cpu: "1"

health:
  path: /health
  interval: 30s

depends:
  postgres: main  # If project uses database
```

---

## Implementation Roadmap

| Priority | Change | Effort | Status | Completed |
|----------|--------|--------|--------|-----------|
| **P1a** | Create `python-api` deploy template | 2 hours | ✅ **DONE** | 2026-04-10 |
| **P1b** | Create `chrome-extension` deploy template | 1.5 hours | ✅ **DONE** | 2026-04-10 |
| **P1c** | Create `static-site` deploy template | 0.5 hours | ✅ **DONE** | 2026-04-10 |
| **P1d** | Create `saas-skeleton` deploy template | 0.5 hours | ✅ **DONE** | 2026-04-10 |
| **P2** | Auto-generate spec in `scaffold.py` for docusaurus, mobile-app, desktop-app | 4 hours | ✅ **DONE** | 2026-04-10 |
| **P3** | Enhance fabrik new to auto-read env vars | 3 hours | ⏳ **TODO** | Pending |
| **P4** | Add deployment validation | 2 hours | ⏳ **TODO** | Pending |
| **P5** | Unify template system | 8 hours | ⏳ **TODO** | Pending |

**P1 Complete:** ✅ All 11 scaffold types now have deploy templates (4 hours actual)
**P2 Complete:** ✅ Auto-spec generation for docusaurus, mobile-app, desktop-app (4 hours actual)
**Remaining:** ~5 hours for high-value automation (P3+P4). P5 is optional high-risk refactor (~13h total including P5)

**Next Priority:** P3 - Enhance `fabrik new` to auto-read env vars from scaffolded projects

---

## Testing Checklist

After implementing changes, verify:

- [ ] `fabrik scaffold my-api --type python-api` creates spec file
- [ ] Spec file has correct template name (`python-api`, not `node-api`)
- [ ] All env vars from `compose.yaml` copied to spec `env:` block
- [ ] Secrets detected from `.env.example` → spec `secrets.required:`
- [ ] Port from `project.yaml` used in spec and deploy
- [ ] `fabrik plan specs/services/my-api.yaml` succeeds
- [ ] `fabrik apply specs/services/my-api.yaml` deploys successfully
- [ ] Deployed service accessible at `https://my-api.vps1.ocoron.com`
- [ ] Health check passes

---

## Conclusion

**✅ Phase 1 COMPLETE (2026-04-10):** All 11 scaffold types now have deploy templates.

### Current State

**Template Coverage:** ✅ **100% Complete**
- All 11 scaffold types have corresponding `compose.yaml.j2` templates
- All templates include `defaults.yaml` for standard env vars
- Port allocation correct for each type (Python: 8000, Node: 3000, etc.)

**What Works Now:**
1. `fabrik scaffold my-api --type python-api` → Creates scaffolded project
2. `fabrik new my-api --template python-api --domain api.vps1.ocoron.com --output specs/services` → Creates spec file
3. `fabrik apply specs/services/my-api.yaml -s API_KEY=xxx` → Deploys to Coolify
4. `fabrik scaffold my-docs --type docusaurus` → Creates scaffold + auto-generates `specs/services/my-docs.yaml`
5. `fabrik scaffold my-mobile --type mobile-app` → Creates scaffold + auto-generates `specs/services/my-mobile.yaml`
6. `fabrik scaffold my-desktop --type desktop-app` → Creates scaffold + auto-generates `specs/services/my-desktop.yaml`

**Remaining Manual Steps:**
- AI agents must manually create spec files (step 2 above) or use `fabrik new` for types not yet in `SPEC_ENABLED_TYPES`
- Env vars must be manually copied from project to spec (P3 will automate)
- Secrets must be identified and passed via `-s` flags (P3 will auto-detect)
- `docusaurus`, `mobile-app`, and `desktop-app` no longer require manual spec creation (auto-generated by P2)
- `wordpress` remains manual — use `fabrik wp plan` + `fabrik wp apply` for WordPress projects

### Next Phase: Automation (P2-P5)

**P2 - ✅ DONE (docusaurus, mobile-app, desktop-app):** `fabrik scaffold` auto-generates spec for these types
**P3 - Enhance fabrik new (3h):** Auto-read env vars from scaffolded project
**P4 - Validation (2h):** Check deployment readiness
**P5 - Unified templates (8h):** Merge scaffold + deploy templates (⚠️ high-risk, defer)

**Total remaining:** ~5 hours for high-value automation (P3+P4). P5 is optional high-risk refactor.

### For AI Agents

**When deploying ANY scaffolded project:**
1. Spec template name = scaffold type name (1:1 mapping - all templates exist)
2. Use correct port: Python=8000, Node/Next/SaaS=3000
3. Use `fabrik new --output specs/services` for correct spec location
4. Check `PORTS.md` before assigning new ports on VPS
5. All templates support PostgreSQL, Redis, volumes, health checks

**No workarounds needed** - every scaffold type is deployable with correct template.
