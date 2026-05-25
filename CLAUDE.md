<!-- Read by: Claude Code ≤6,000 chars. -->
# Contract

Solo dev WSL Ubuntu. **Fast but pro. Ship, iterate, no over-engineering.** Read fully before non-trivial work.

## ⚠️ FIRST OUTPUT (every response)
`RULES ACTIVE: CLAUDE-CODE | <3 rules from this file you applied>`

## Orient (every task)
1. `project.yaml::type` tells you which of 11 `scripts/scaffold.py` scaffolds this is. All projects use `.venv` and deploy via Coolify API. Per-task files-to-read: see the ticket's Pre-flight checklist.
2. `AFCL.md`: read if exists; append friction findings as you hit them.
3. Open scope-relevant topic packs in `.windsurf/rules/`: `10-python` `15-api` `20-typescript` `25-data-postgres` `30-ops` `35-security-auth` `40-docs` `45-testing` `50-code-review` `55-observability`.
4. Plans: see `fabrik_workflow.md`.

## Behavior
- **Check before create:** verify file does not exist before write. Exists = STOP, ask.
- **Present before execute:** plan → approval → execute. Read-only calls (`Read`, `Grep`, `Glob`, `LS`) exempt.
- **Stay on task:** no unsolicited advice or process commentary.
- **Conflict resolution:** rule pack > ticket. Surface conflict before proceeding.
- **State conflict:** task contradicts existing state → stop, report. Never silently overwrite.

## Completion Contract
1. **IMPLEMENT** — Stay within ticket Scope; adjacent fixes in same files OK. No hardcoded secrets/localhost (`os.getenv("KEY","default")`), no silent failures. 1 test for highest-risk path (skip docs-only).
2. **GATE** — Run ticket's `Final Gate Instruction` (`scripts/final_gate.py`); fix to `status:"success"`. Flags: `--lean --json` (std) · `--json` (milestone/schema/auth) · `--systemic --json` (epic).
3. **CHANGELOG** — One entry under `## [Unreleased]`: `### Added|Changed|Fixed — Title (YYYY-MM-DD)`. Gate-enforced.
4. **LESSONS LEARNT** — Ticket field = `none` OR entry in `docs/LESSONS_LEARNT.md`. Silence = failure.
5. **EXIT** — Gate auto-stages on success. STOP. No commit/push unless user said so this turn; `git add` OK.

## External Knowledge — Search, Don't Guess
When the ticket references a 3rd-party API or SDK:
1. Repo first: `Grep docs/` + check `AFCL.md`.
2. Else: `WebSearch` → `WebFetch` official docs; cite URL in code.
3. After 3 misses: `BLOCKED: <vendor> — <searched> — <missing>`; stop.

Skip: stdlib, syntax, Fabrik conventions.

## HARD STOPS — NEVER
| Rule | Instead |
|:--|:--|
| `git commit` / `git push` (unless user said so this turn) | gate auto-stages — task ends there |
| edit outside ticket Scope | stay strict |
| modify deps files (`pyproject.toml`/`requirements.txt`/`package.json`/`uv.lock`/`package-lock.json`) | only if ticket authorises |
| files outside project tree | local paths only |
| foreground command likely >30s (build/deploy/test/sync/`fabrik`/`docker`/`pytest`/`npm i`) | Bash `run_in_background=true`, OR `rund -- <cmd>`; `runwait $(runlast) <s>`; `runc $(runlast)`. Doc: `docs/reference/long-command-monitoring.md` |
| `fabrik redeploy` on git-sourced app without `git push` first | commit → push → redeploy; Coolify pulls from GitHub, not `/opt/` |
| compose without `deploy.resources.limits.memory` on a Coolify-deployed service | Coolify v4 ignores its `limits_memory` UI field for `build_pack=dockercompose` and Services. Scaffolder auto-emits via `_write_canonical_compose`; manual composes MUST declare. For Services, mutate `docker_compose_raw` via `PATCH /api/v1/services/<uuid>` (base64-encoded) — never edit the on-disk file. See F5 + Lesson 62 |
| `DB_HOST=localhost` / `DATABASE_URL=...@localhost:` | use `postgres-main:5432`, `redis-main:6379` — `localhost` = the container, not the shared DB |
| Authelia config reload via SIGHUP | exits, doesn't reload — `docker restart <authelia-container>` after edits |
| New Gatus endpoint using UUID container name | stable Docker DNS only: compose service name (Service stacks) or registered alias (single-image Apps). UUID drifts per redeploy. Pairs in `vps_apply_limits.sh` |
| Coolify single-image App needs stable alias install | (1) `networks.coolify.aliases` in app compose (2) `docker network disconnect coolify <uuid>` then `connect --alias <stable> --alias <uuid> coolify <uuid>` (3) update Gatus config (4) persist via `vps_apply_limits.sh` |
| Health check `/health` behind auth | Authelia bypass `*.vps1.ocoron.com → /health` covers it — never protect |
| Container ports bound to host directly | all on `coolify` net; Traefik routes. Middleware (scaffold-emitted): admin `authelia-forward@docker,gzip@docker`; API `gzip@docker`; public none |
| new `.md` outside allowlist | root files · scaffold docs · `docs/development/plans/YYYY-MM-DD-plan-<n>.md` · `docs/reference/**/*.md` · `docs/archive/**` |
| destructive script on prod data w/o dry-run | dry-run first, show diff |
| credentials change w/o backup + diff approval | `cp <f> backups/<f>.backup.$(date +%Y%m%d-%H%M%S)` first |

In packs: Alpine, raw `pip`, `/tmp/`, FastAPI `except Exception` swallow `HTTPException`, dup `logger.exception()` w/ GlitchTip, inline M2M auth, module-level config, raw SQL DDL, `.venv` recreate, scaffold reorganize.

## Pointers (detail in packs)
- **Backup secrets before edit** (`.env`, `*.key`, `*.pem`, `secrets/`, `.ssh/`) → target: `backups/` dir (gitignored). See `35-security-auth.md`.
- **Password policy** (32-char `[a-zA-Z0-9]` via `secrets.choice()`, banned: `postgres`/`admin`/`password123`).
- **Naming:** kebab-case. Exceptions: `README.md`, `CHANGELOG.md`, `INDEX.md`, `PORTS.md`, `AGENTS.md`, `AGENTS-compact.md`, `LESSONS_LEARNT.md`, `CLAUDE.md`, `Makefile`, `Dockerfile`, Python pkgs (snake_case), auto-generated, dotfiles.
- **Ports:** Python 8000–8099, frontend 3000–3099. Register in `PORTS.md` before use.
- **Same code in 3 envs:** WSL dev (PG localhost, `.env`) · VPS Docker (`postgres-main`, `compose.yaml`) · Supabase (env vars). Must run unmodified.
- **Health endpoint:** test real deps (`await db.execute("SELECT 1")`).
- **Before new scripts:** `Grep` `scripts/` + `enforcement/`. Extend, don't duplicate.

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

To preview what the spec will trigger: `fabrik plan specs/services/<id>.yaml`
