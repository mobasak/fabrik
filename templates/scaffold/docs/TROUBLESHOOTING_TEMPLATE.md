# Troubleshooting — [Project Name]

**Last Updated:** YYYY-MM-DD

> **Purpose:** COMMON ISSUES AND FIXES.

---

## Quick Diagnostics

```bash
# Health check
curl http://localhost:$PORT/health

# Logs
docker compose logs -f --tail=50

# Run tests
/opt/[project]/.venv/bin/pytest tests/ -v
```

---

## Common Issues

### Service won't start

| Symptom | Cause | Fix |
|---------|-------|-----|
| Port already in use | Another service on same port | `lsof -i :$PORT` → kill or change port in `.env` |
| Import errors | Missing dependencies or wrong venv | `/opt/[project]/.venv/bin/pip install -r requirements.txt` |
| `externally-managed-environment` | Bare `pip install` on WSL/Debian | Always use `/opt/[project]/.venv/bin/pip`, never bare `pip` |
| Container won't start | Docker image issue | `docker compose build --no-cache && docker compose up -d` |

### Health check returns 503

Dependencies unreachable. Check the response body — it tells you which dependency failed:

```bash
curl -s http://localhost:$PORT/health | jq .
```

| Failing dependency | Fix |
|--------------------|-----|
| `postgres: timeout` | Verify `DATABASE_URL` in `.env`. Test: `u=$(pgurl "$DATABASE_URL") && psql "$u"` (define `pgurl` first: Debug Commands) |
| `redis: timeout` | Verify `REDIS_URL` in `.env`. Is Redis running? `docker compose ps` |
| All dependencies down | Service started before dependencies. Restart: `docker compose restart` |

### Import errors in tests

```text
ModuleNotFoundError: No module named 'src'
```

Tests must import from the package name, not `src`:
```python
# Correct
from <package_name>.main import app

# Wrong
from src.main import app
```

### Docker / Compose issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `localhost` connection refused inside container | Using `localhost` instead of service name | Replace `localhost` with `postgres-main`, `redis-main`, etc. in `.env` |
| Image architecture mismatch | Missing platform spec | Add `platform: linux/amd64` in `compose.yaml` |
| Stale container | Old image cached | `docker compose down && docker compose up -d --build` |
| Volume permission errors | UID mismatch | Check Dockerfile `USER` directive matches volume owner |

---

## Error Messages

| Error | Meaning | Fix |
|-------|---------|-----|
| `Address already in use` | Port conflict | `lsof -i :$PORT` → kill process or change port |
| `No module named 'fastapi'` | Venv not activated or deps missing | `source /opt/[project]/.venv/bin/activate && pip install -r requirements.txt` |
| `Connection refused` to database | DB not running or wrong URL | Check `DATABASE_URL`, test with `psql` |
| `ECONNREFUSED` in container | Using `localhost` in Docker | Use Docker service names, not `localhost` |

---

## Debug Commands

```bash
# Service health (verbose)
curl -v http://localhost:$PORT/health

# Docker status
docker compose ps
docker compose logs <service-name> --tail=100

# Database connection test
# psql reads libpq URIs only: pgurl drops a lowercase SQLAlchemy driver (+asyncpg, +psycopg) and maps ?ssl= to
# ?sslmode= (a boolean ssl=true/false is not a libpq sslmode: write require/disable)
# (other asyncpg-only query keys, e.g. prepared_statement_cache_size, still need removing by hand).
# Define it first; `u=$(pgurl ...) &&` stops on an empty or unset variable instead of psql falling back
# to the local default database — and on a DSN carrying whitespace, a quote or a backslash (a hand-edited or
# still-quoted .env line fails CLOSED here instead of reaching psql mangled), on a value that does not rewrite to a
# postgres:// or postgresql:// URI (a `-o/<file>` would reach root's psql as an option; an upper-case or malformed
# +driver would reach it un-rewritten — fabrik-lib 01M4TP1W), on more than one ssl/sslmode/requiressl key (libpq keeps the LAST
# silently: `?sslmode=require&ssl=disable` would drop TLS), on a percent-encoded query KEY (libpq decodes keys, so
# `%73slmode=disable` is a second sslmode) and on a raw `?` in the user:password part (libpq reads the text before
# the first `@` as credentials, so a `?` there would hide the real query from these checks — encode it as %3F).
pgurl() ( [ -n "$1" ] || { echo "pgurl: empty DSN" >&2; exit 1; }; set -f; case $1 in *[[:space:]]*|*\"*|*\'*|*\\*) echo "pgurl: DSN carries whitespace, a quote or a backslash — fix the .env line, never psql it" >&2; exit 1;; esac; a=${1#*://}; case ${a%%/*} in *@*) case ${a%%@*} in *\?*) echo "pgurl: a ? in the user:password part — percent-encode it as %3F, or libpq and this check split the DSN differently" >&2; exit 1;; esac;; esac; b=${1%%\?*}; q=${1#"$b"}; n=0; IFS=" "; for kv in $(printf %s "${q#\?}" | tr '&' ' '); do case ${kv%%=*} in *%*) echo "pgurl: a percent-encoded query KEY ($kv) — libpq decodes keys, so it could hide a second sslmode; write keys plain" >&2; exit 1;; ssl|sslmode|requiressl) n=$((n+1));; esac; done; [ "$n" -le 1 ] || { echo "pgurl: more than one ssl/sslmode/requiressl key — libpq keeps the LAST one silently (requiressl rewrites sslmode); keep exactly one" >&2; exit 1; }; s=$(printf %s "$b" | sed 's#^\(postgres[a-z]*\)+[a-z0-9_][a-z0-9_]*://#\1://#'); case $s in postgres://*|postgresql://*) ;; *) echo "pgurl: not a postgres DSN (postgres://, postgresql:// or a lowercase +driver form such as postgresql+asyncpg://) — fix the .env line, never psql it" >&2; exit 1;; esac; printf '%s%s\n' "$s" "$(printf %s "$q" | sed 's/\([?&]\)ssl=/\1sslmode=/g')" )
u=$(pgurl "$DATABASE_URL") && psql "$u" -c "SELECT 1"

# Port check
lsof -i :$PORT

# Python environment
/opt/[project]/.venv/bin/python --version
/opt/[project]/.venv/bin/pip list

# Disk space (common VPS issue)
df -h /
```

---

## Project-Specific Issues

<!-- Add issues specific to this project as they surface.
     Format: symptom → cause → fix. Keep it scannable. -->

| Symptom | Cause | Fix |
|---------|-------|-----|
| *(none yet)* | — | — |
