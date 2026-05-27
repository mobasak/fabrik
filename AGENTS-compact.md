<!-- Read by Kilo CLI (opencode.json). Self-contained (Kilo doesn't auto-load packs). Hard truncate ~32k; optimal 4–8k (ships in every request → token cost). Rules at top get strongest attention. -->
# Kilo CLI Agent Rules

## ⚠️ FIRST OUTPUT (every response)
`RULES ACTIVE: KILO | <3 rules from this file you applied>`

## ⚠️ If `expertise-pack/` exists in this project — WordPress factory rules

If the directory `expertise-pack/` is present, this is a WordPress site-factory project. Before any WordPress, WP-CLI, plugin, theme, golden image, or apply-pipeline work:

1. Read `expertise-pack/wpf-expertise-pack-spec-v3.md` — architecture, ownership map, 13-stage pipeline, plugin curation rules.
2. Read `.claude/skills/wpf-wordpress/references/wp-cli-recipes.md` — verified command library. Never guess a WP-CLI command, option key, or plugin slug.
3. Claude Code agents: invoke the `wpf-wordpress` skill FIRST.

Hard rules: no raw SQL, no hand-edited serialized PHP, no invented `wp_options` keys. Free plugins: `https://downloads.wordpress.org/plugin/{slug}.latest-stable.zip`.

## ORIENT (every task)
1. `project.yaml::type` — one of 11 `scripts/scaffold.py` scaffolds. All projects use `.venv` and deploy via Coolify API.
2. `AFCL.md`: read if exists; append friction findings as you hit them.

## BEHAVIOR
- **Check before create:** file exists = STOP, ask.
- **Present before execute:** plan → approval → execute. Read-only ops exempt.
- **Stay on task:** no unsolicited advice or process commentary.
- **State conflict:** task contradicts existing state → stop, report. Never silently overwrite.

## COMPLETION CONTRACT (in order, every task)
1. **IMPLEMENT** — Stay within ticket Scope; adjacent fixes in same files OK. No hardcoded secrets/localhost (`os.getenv("KEY","default")`), no silent failures. 1 test for highest-risk path (skip docs-only).
2. **GATE** — Run ticket's `Final Gate Instruction` (`scripts/final_gate.py`); fix to `status:"success"`. Flags: `--lean --json` (std) · `--json` (milestone/schema/auth) · `--systemic --json` (epic).
3. **CHANGELOG** — One entry under `## [Unreleased]`: `### Added|Changed|Fixed — Title (YYYY-MM-DD)`. Gate-enforced.
4. **LESSONS LEARNT** — Ticket field = `none` OR entry in `docs/LESSONS_LEARNT.md`. Silence = failure.
5. **EXIT** — Gate auto-stages on success. STOP. No commit/push unless user said so this turn; `git add` OK. Traycer or user commits.

## DOC SYNC MATRIX (every task)
Update matched docs in the SAME staged change. Skipping = task failure (gate-enforced).

| Change | Update |
|---|---|
| New env var | `.env.example` + comment (Why / How / Default) |
| Real secret value | `.env` (gitignored) |
| External cred setup changed | `docs/CONFIGURATION.md` |
| Code/Docker/deps changed | `CHANGELOG.md` |
| File added/removed/renamed | `INDEX.md` |
| Tech stack or setup changed | `README.md` |
| API/SDK/CLI/integration changed | `docs/QUICKSTART.md` |
| New port allocated | `PORTS.md` |
| Recurring symptom | `docs/TROUBLESHOOTING.md` (Symptom/Cause/Fix) |
| Feature shipped/deprecated | `docs/FEATURES.md` |
| New plan | `docs/development/plans/YYYY-MM-DD-plan-<name>.md` |
| Schema migration | Alembic + `db/schema.sql` |
| Future idea | `docs/STRATEGIC_BACKLOG.md` (Now/Later/Context) |
| Aha moment | `docs/LESSONS_LEARNT.md` |
| Silicon ceiling | `AFCL.md` |
| Pricing / GTM | `docs/BUSINESS_MODEL.md` |

**Skip:** refactor/docs/test-only → `CHANGELOG.md` only.

## CROSS-CUTTING
1. **Structured logging** — JSON + correlation IDs. Use scaffolded logger at `src/{pkg}/logger.py` or `src/logger.js`. Never `print()`/`console.log()`. Never write a custom logger.
2. **GlitchTip error reporting** — Scaffold-emitted (`glitchtip_init.{py,js}`). With `GLITCHTIP_DSN` set: unhandled errors auto-report. DO NOT also `logger.exception()` with full traceback (Loki dup). `capture_exception()` only for caught-then-rethrown control flow.
3. **User guide** — If user-facing AND `project.yaml::has_user_guide: true` → add/update page in `docs/user-guide/`.
4. **Reusability** — Business logic separate from framework. Shared utilities in `src/utils/` or `src/lib/` with zero project-specific imports and no hardcoded project values. Any reusable function lives in its own module with docstring + type hints. Tag `[reusable]` in `INDEX.md`.
5. **Naming** — kebab-case. Exceptions: `README.md`, `CHANGELOG.md`, `INDEX.md`, `PORTS.md`, `AGENTS.md`, `AGENTS-compact.md`, `LESSONS_LEARNT.md`, `Makefile`, `Dockerfile`, Python pkgs (snake_case per PEP 8), auto-generated, dotfiles.
6. **Search, don't guess** — When the ticket references a 3rd-party API or SDK:
   1. Repo first: `grep docs/` + check `AFCL.md`.
   2. Else: `web_search` → `web_fetch` MCP on vendor's official docs; cite URL in code.
   3. After 3 misses: `BLOCKED: <vendor> — <searched> — <missing>`; stop.
   Skip: stdlib, syntax, Fabrik conventions.
7. **fabrik-lib** (`/opt/fabrik-lib/`) — reusable modules, vendor (copy) don't import. Check `fabrik-lib/README.md` for the module table before building from scratch. New module = must have `README.md` + `requirements.txt` + row in `fabrik-lib/README.md` table.

## SECURITY & DATA
1. **Sensitive data** — Before editing `.env`, `*.key`, `*.pem`, files under `secrets/` or `.ssh/`:
   ```bash
   cp <file> <file>.backup.$(date +%Y%m%d-%H%M%S)
   ```

2. **Password policy** (programmatic generation only — not user-input):
   - 32 chars, charset `[a-zA-Z0-9]` only (no symbols — survives `.env` round-trip + shell quoting)
   - Generator: Python `secrets.choice(string.ascii_letters + string.digits)`
   - Banned: `postgres`, `admin`, `password`, `password123`, default vendor creds

3. **M2M service-to-service auth** — Use scaffolded `internal_auth.py` + header `X-Internal-Token` + env `SERVICE_INTERNAL_SECRET_KEY`. Never inline `APIKeyHeader` or per-service key names. Detail: `core/35-security-auth.md`.

4. **Authelia** — No SIGHUP support (exits). After `configuration.yml` edit: `docker restart <authelia-container>`. Authelia bypass `*.vps1.ocoron.com → /health` is automatic — never protect `/health`.

## DOCKER & DEPLOY
1. **No `localhost` in connection strings** — Inside containers, `localhost` = the container itself, not the host. Use Docker network DNS:

   | Var | ❌ Wrong | ✅ Correct |
   |---|---|---|
   | `DB_HOST` | `localhost` | `postgres-main` |
   | `DATABASE_URL` | `...@localhost:5432/...` | `...@postgres-main:5432/...` |
   | `REDIS_URL` | `redis://localhost:6379` | `redis://redis-main:6379` |

   Verify before deploy: `grep -E '^(DB_HOST|DATABASE_URL|REDIS_URL)=' .env | grep localhost` must return nothing.

2. **Post-deploy checklist (every new service):**
   - **Network:** containers on `coolify`; never bind ports to host; Traefik routes via labels.
   - **Traefik middleware** (scaffold-emitted): admin UI → `authelia-forward@docker,gzip@docker`; API → `gzip@docker`; public → none.
   - **Coolify env:** `SERVICE_INTERNAL_SECRET_KEY`, `DATABASE_URL` (`postgres-main`), `REDIS_URL` (`redis-main`).
   - **Health:** `/health` → 200; Coolify interval 60s for stable services.

3. **`fabrik redeploy` on git-sourced app** — sequence: `git commit` → `git push` → `fabrik redeploy`. Coolify pulls from GitHub remote, not local `/opt/` clone.

4. **Gatus stable DNS** — Never use UUID container names in Gatus or inter-service URLs (they drift per redeploy). Use compose service names or registered stable aliases. Procedure: `docs/reference/coolify-stable-aliases.md`.

## HARD STOPS — NEVER
| Rule | Instead |
|:--|:--|
| `git commit` / `git push` (unless user said so this turn) | gate auto-stages — task ends there |
| edit outside ticket Scope | stay strict |
| modify deps files (`pyproject.toml`/`requirements.txt`/`package.json`/`uv.lock`/`package-lock.json`) | only if ticket authorises |
| files outside project tree | local paths only |
| bare `pip install` | `/opt/<project>/.venv/bin/pip install` (PEP 668) |
| Alpine base image | `python:<stable>-slim-bookworm` / `node:<LTS>-bookworm-slim` |
| Docker `ports:` exposure to host | route through Traefik (DOCKER-USER blocks raw ports) |
| compose without `deploy.resources.limits.memory` on Coolify-deployed service | Coolify v4 ignores `limits_memory` UI for `build_pack=dockercompose` + Services. Scaffolder auto-emits via `_write_canonical_compose`. For Services, mutate `docker_compose_raw` via `PATCH /api/v1/services/<uuid>` base64-encoded — never edit on-disk. F5 / Lesson 62 |
| admin dashboard w/o auth | Authelia forward-auth OR app-layer TOTP |
| FastAPI `except Exception` swallowing `HTTPException` | always `except HTTPException: raise` before generic catch |
| foreground command likely >30s (build/deploy/test/sync/`fabrik`/`docker`/`pytest`/`npm i`) | `scripts/rund -- <cmd>`; `runwait $(runlast) <s>`; `runc $(runlast)`. Doc: `docs/reference/long-command-monitoring.md` |
| new `.md` outside allowlist | root files · scaffold docs · `docs/development/plans/YYYY-MM-DD-plan-<n>.md` · `docs/reference/**/*.md` · `docs/archive/**` |
| destructive script on prod data w/o dry-run | dry-run first, show diff |
| credentials change w/o backup + diff approval | `cp <f> <f>.backup.$(date +%Y%m%d-%H%M%S)` first |
| `/tmp/` | project `.tmp/` |
| class/module-level config | function-level only |
| raw SQL DDL | Alembic migrations only; `db/schema.sql` reference only |
| recreate `.venv` / replace existing Docker config | reuse what exists |

## ⚠️ FINAL OUTPUT (last 4 lines)
```
GATE: <command run> → success|failure
DOCS UPDATED: <files | none>
CHANGELOG: <entry title | n/a>
LESSONS LEARNT: <none | docs/LESSONS_LEARNT.md entry title>
```
Missing any line = task failure. Re-run gate until `success`, then output 4 lines.

## Spec contract awareness

Every Fabrik project has `specs/services/<id>.yaml` with a `shape:` block that drives:

- Which Postgres DB / Redis index / Backrest plan / Gatus endpoint / Prometheus job / GlitchTip project / Authelia rule / Meilisearch index get auto-created on `fabrik apply`
- The shape contract is canonical: code MUST match it, not the other way around

If your code:

- Adds a database call → `shape.needs_database` MUST be `true` in the spec
- Adds a Redis cache → `shape.needs_cache` MUST be `true`
- Exposes `/metrics` → `shape.exposes_metrics` MUST be `true`
- Adds Meilisearch indexes → `shape.has_search_feature` MUST be `true`
- Adds an admin UI behind auth → `shape.is_admin_dashboard` MUST be `true`

If you change code in a way that affects any of the above, ALSO update `specs/services/<id>.yaml`.
Don't ship code that contradicts the spec — `fabrik apply` will skip the registrar and you'll have a silently broken deploy.
