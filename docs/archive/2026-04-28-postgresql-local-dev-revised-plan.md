# PostgreSQL Local Dev - REVISED Implementation Plan

**Date:** 2026-04-12
**Status:** FACTUAL CORRECTIONS APPLIED
**Version:** 2.0 (post-review)

---

## Revisions Applied

| # | Issue | Fix | Status |
|---|-------|-----|--------|
| 1 | subprocess import | Verified already imported in scaffold.py | ✅ Confirmed |
| 2 | Unconditional DB creation | Add `--db` flag to scaffold command | ✅ Specified |
| 3 | `set -e` + grep conflict | Remove `set -e`, use `grep -qx`, explicit errors | ✅ Implemented |
| 4 | Missing Alembic auto-run | Add to python-api compose template NOW | ✅ Specified |
| 5 | "Optional" backfill | Change to REQUIRED, do same session | ✅ Updated |

---

## REVISED: Files to Modify

### 1. `/opt/fabrik/src/fabrik/cli.py` **(NEW CHANGE)**

**Add `--db` flag to scaffold command** (after line 787):

```python
@cli.command()
@click.argument("name")
@click.option("--description", "-d", default="A new project", help="Project description")
@click.option(
    "--type",
    "project_type",
    type=click.Choice(sorted(SCAFFOLD_TYPES)),
    default="python-api",
    show_default=True,
    help="Project type to scaffold",
)
@click.option(
    "--preset",
    type=click.Choice(["saas", "company", "content", "landing", "ecommerce"]),
    default=None,
    help="Preset variant (only used for --type wordpress)",
)
@click.option("--no-spec", is_flag=True, default=False, help="Skip automatic spec file generation")
@click.option(
    "--dev-port",
    default="8080",
    show_default=True,
    help="Local dev port for WordPress (WSL only)",
)
@click.option(
    "--db",
    is_flag=True,
    default=False,
    help="Enable PostgreSQL database (creates DB, adds DATABASE_URL to .env.local)",
)
def scaffold(
    name: str,
    description: str,
    project_type: str,
    preset: str | None,
    no_spec: bool,
    dev_port: str,
    db: bool,  # NEW PARAMETER
) -> None:
```

**Pass `db` flag to create_project:**

```python
# In scaffold() function body, update create_project call:
result = create_project(
    name=name,
    description=description,
    project_type=project_type,
    preset=preset,
    dev_port=dev_port,
    use_database=db,  # NEW ARGUMENT
)
```

---

### 2. `/opt/fabrik/src/fabrik/scaffold.py`

**Confirmed:** `import subprocess` already present at top of file ✅

#### A. Update `create_project()` signature (around line 2522):

```python
def create_project(
    name: str,
    description: str,
    project_type: str,
    preset: str | None = None,
    dev_port: str = "8080",
    use_database: bool = False,  # NEW PARAMETER
) -> int:
```

#### B. Pass `use_database` to scaffolder functions:

```python
# Around line 2543
scaffolder(project_dir, name, description, preset=preset, use_database=use_database)
```

#### C. Update `_scaffold_python_api()` signature (around line 641):

```python
def _scaffold_python_api(
    project_dir: Path,
    name: str,
    description: str,
    preset: object = None,
    use_database: bool = False,  # NEW PARAMETER
) -> None:
```

#### D. Conditional .env.local generation in `_scaffold_python_api()`:

```python
# After SERVICE_NAME append to .env.example (around line 870)

if use_database:
    # .env.local — WSL local development with PostgreSQL
    db_name_dev = name.replace("-", "_") + "_dev"
    (project_dir / ".env.local").write_text(
        f"# {name} Local Development (WSL)\n"
        f"LOG_LEVEL=DEBUG\n"
        f"SERVICE_NAME={name}\n\n"
        f"# Native PostgreSQL on WSL\n"
        f"DATABASE_URL=postgresql://postgres@localhost:5432/{db_name_dev}\n"
    )

    # Auto-create development database
    try:
        # Check if database exists (exact match)
        check_result = subprocess.run(
            ["sudo", "-u", "postgres", "psql", "-lqt"],
            capture_output=True,
            timeout=5,
            text=True
        )

        db_exists = False
        if check_result.returncode == 0:
            # Parse database list, exact match only
            for line in check_result.stdout.split('\n'):
                if '|' in line:
                    db_in_line = line.split('|')[0].strip()
                    if db_in_line == db_name_dev:
                        db_exists = True
                        break

        if not db_exists:
            # Create database
            create_result = subprocess.run(
                ["sudo", "-u", "postgres", "psql", "-c", f"CREATE DATABASE {db_name_dev};"],
                capture_output=True,
                timeout=5
            )
            if create_result.returncode == 0:
                click.echo(f"✅ Created PostgreSQL database: {db_name_dev}")
            else:
                click.echo(f"⚠️  Could not create database. Run manually:")
                click.echo(f"    sudo -u postgres psql -c 'CREATE DATABASE {db_name_dev};'")
        else:
            click.echo(f"✅ PostgreSQL database exists: {db_name_dev}")

    except Exception:
        click.echo(f"⚠️  Database auto-creation failed. Create manually:")
        click.echo(f"    sudo -u postgres psql -c 'CREATE DATABASE {db_name_dev};'")

    # Update .env.example to uncomment DATABASE_URL
    env_example_path = project_dir / ".env.example"
    env_content = env_example_path.read_text()
    # Replace commented DB line with uncommented VPS version
    env_content = env_content.replace(
        "# Optional - uncomment if using database\n# DATABASE_URL=postgresql://user:pass@localhost:5432/{name}_dev\n",
        f"# Database (managed by Coolify on VPS)\n# Set via Coolify secrets: POSTGRES_PASSWORD\nDATABASE_URL=postgresql://postgres:${{POSTGRES_PASSWORD}}@postgres-main:5432/{name}\n"
    )
    env_example_path.write_text(env_content)
```

#### E. Same changes for `_scaffold_chrome_extension()` (around line 2030):

```python
# Add use_database parameter to function signature
def _scaffold_chrome_extension(
    project_dir: Path,
    name: str,
    description: str,
    preset: object = None,
    use_database: bool = False,  # NEW PARAMETER
) -> None:

# ... then same conditional .env.local + DB creation logic after .env.example write
```

---

### 3. `/opt/fabrik/templates/python-api/compose.yaml.j2` **(NEW FILE - CRITICAL)**

**Create this file NOW for Alembic auto-run on deploy:**

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
    # Run migrations before starting server
    command: sh -c "alembic upgrade head && uvicorn src.{{ spec.id.replace('-', '_') }}.main:app --host 0.0.0.0 --port 8000"
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

**Also create:** `/opt/fabrik/templates/python-api/defaults.yaml`

```yaml
env:
  LOG_LEVEL: INFO
  PYTHONUNBUFFERED: "1"
```

---

### 4. `/opt/fabrik/scripts/create_pg_dev_db.sh`

✅ **Already fixed** - removed `set -e`, added exact match grep, explicit error handling

---

### 5. Documentation Updates (same as before)

- `templates/scaffold/docs/QUICKSTART_TEMPLATE.md` - Add local dev section
- `.windsurf/rules/25-data-postgres.md` - Add local setup section

---

## REVISED: Implementation Checklist

### Phase 1: Core Changes (REQUIRED, same session)
- [ ] Add `--db` flag to `cli.py` scaffold command
- [ ] Update `create_project()` signature in `scaffold.py`
- [ ] Update `_scaffold_python_api()` signature + conditional DB logic
- [ ] Update `_scaffold_chrome_extension()` signature + conditional DB logic
- [ ] Create `/opt/fabrik/templates/python-api/compose.yaml.j2` with Alembic auto-run
- [ ] Create `/opt/fabrik/templates/python-api/defaults.yaml`
- [ ] Verify `create_pg_dev_db.sh` is executable

### Phase 2: Documentation (REQUIRED, same session)
- [ ] Update `QUICKSTART_TEMPLATE.md` with local dev section
- [ ] Update `25-data-postgres.md` with local setup section
- [ ] Update `CHANGELOG.md` with all changes

### Phase 3: Testing (REQUIRED, same session)
- [ ] Test: `fabrik scaffold test-api --type python-api --db`
  - [ ] Verify .env.local created with localhost DB
  - [ ] Verify .env.example has postgres-main
  - [ ] Verify database auto-created
  - [ ] Verify `cp .env.local .env && uvicorn` works
- [ ] Test: `fabrik scaffold test-no-db --type python-api` (without --db)
  - [ ] Verify .env.local NOT created
  - [ ] Verify .env.example has commented DB line
  - [ ] Verify no database created
- [ ] Cleanup test projects

### Phase 4: Backfill Existing Projects (REQUIRED, same session ~5 min)

**These 6 projects need .env.local immediately:**

```bash
# 1. youtube
cd /opt/youtube
cat > .env.local << 'EOF'
LOG_LEVEL=DEBUG
SERVICE_NAME=youtube
DATABASE_URL=postgresql://postgres@localhost:5432/youtube_pipeline
EOF

# 2. proposal-creator
cd /opt/proposal-creator
cat > .env.local << 'EOF'
LOG_LEVEL=DEBUG
SERVICE_NAME=proposal-creator
DATABASE_URL=postgresql://postgres@localhost:5432/proposal_creator_dev
EOF
sudo -u postgres psql -c "CREATE DATABASE proposal_creator_dev;"

# 3. seo (already has seo_dev, just create .env.local)
cd /opt/seo
cat > .env.local << 'EOF'
LOG_LEVEL=DEBUG
SERVICE_NAME=seo
DATABASE_URL=postgresql://postgres@localhost:5432/seo_dev
EOF

# 4. job-agent
cd /opt/job-agent
cat > .env.local << 'EOF'
LOG_LEVEL=DEBUG
SERVICE_NAME=job-agent
DATABASE_URL=postgresql://postgres@localhost:5432/job_agent_dev
EOF
sudo -u postgres psql -c "CREATE DATABASE job_agent_dev;"

# 5. triggered-content-orchestration
cd /opt/triggered-content-orchestration
cat > .env.local << 'EOF'
LOG_LEVEL=DEBUG
SERVICE_NAME=triggered-content-orchestration
DATABASE_URL=postgresql://postgres@localhost:5432/triggered_content_orchestration_dev
EOF
sudo -u postgres psql -c "CREATE DATABASE triggered_content_orchestration_dev;"

# 6. translator (if using DB - verify first)
cd /opt/translator
cat > .env.local << 'EOF'
LOG_LEVEL=DEBUG
SERVICE_NAME=translator
DATABASE_URL=postgresql://postgres@localhost:5432/translator_service
EOF
```

**Total time:** ~5 minutes for all 6 projects

---

## REVISED: Usage Examples

### With Database (explicit opt-in):
```bash
fabrik scaffold my-api --type python-api --db
# ✅ .env.local created with DATABASE_URL
# ✅ my_api_dev database created
# ✅ .env.example uncomments DATABASE_URL for VPS
```

### Without Database (default):
```bash
fabrik scaffold my-stateless-api --type python-api
# ✅ No .env.local created
# ✅ No database created
# ✅ .env.example keeps DATABASE_URL commented
```

---

## Critical Addition: Alembic on Deploy

**Why this matters:**

Current: Deploy to VPS → service starts → **migrations NOT run** → schema mismatch → prod breaks silently

Fixed: Deploy to VPS → Alembic runs migrations → **then** service starts → schema always current

**Implementation:** Added to `templates/python-api/compose.yaml.j2`:

```yaml
command: sh -c "alembic upgrade head && uvicorn ..."
```

**Alternative if Coolify has native release command support:**
- Check Coolify docs for "release" phase
- If exists, use that instead of `sh -c` wrapper
- Cleaner separation but same effect

---

## Revised Effort Estimate

| Phase | Original | Revised | Reason |
|-------|----------|---------|--------|
| Code | 30 min | **45 min** | Added --db flag, conditional logic |
| Templates | 0 min | **15 min** | Created python-api compose template |
| Docs | 15 min | 15 min | Same |
| Testing | 20 min | **30 min** | Test both --db and no-db paths |
| Backfill | "Optional" | **5 min** | REQUIRED, 6 one-liners |
| **TOTAL** | ~1 hour | **~2 hours** | More robust, production-ready |

---

## Success Criteria (Updated)

- [ ] `fabrik scaffold my-api --type python-api --db` creates DB setup
- [ ] `fabrik scaffold my-api --type python-api` (no --db) skips DB setup
- [ ] Database `my_api_dev` auto-created only when --db passed
- [ ] `.env.example` DATABASE_URL uncommented only when --db passed
- [ ] `fabrik apply` runs Alembic migrations before starting service on VPS
- [ ] All 6 existing projects have `.env.local` and can run locally
- [ ] Zero .env drift between WSL and VPS

---

## Rollback Plan

If issues arise:

1. Revert `cli.py` and `scaffold.py` changes
2. Delete `/opt/fabrik/templates/python-api/` directory
3. Remove `.env.local` from 6 backfilled projects
4. No production impact (VPS uses Coolify secrets)

---

## Notes

- `subprocess` already imported ✅ - verified in scaffold.py line 8
- Shell script fixed ✅ - no more `set -e` conflicts
- Alembic auto-run ✅ - prevents silent prod schema drift
- Backfill required ✅ - prevents .env file divergence
- `--db` flag ✅ - opt-in only, no noise for stateless APIs

**This plan is production-ready.**
