# Claude Code Rules — fabrik-claim-validator

Solo dev (Özgür). WSL Ubuntu, Linux paths only. `python-api`, port **8002**, Coolify-deployed. `has_user_guide: false`. **Fast but good. Ship, iterate, no over-engineering.**

## Completion Contract (every task)

1. **IMPLEMENT** — Stay in scope. No hardcoded secrets/localhost (`os.getenv("KEY", "default")`). No silent failures. Write **1** test for the highest-risk path (skip docs-only). Adjacent fixes allowed inside files already in scope; never broaden scope.
2. **QUALITY GATE** — Run literal command from ticket; fix until `status: "success"`:
   - Standard: `python scripts/final_gate.py --lean --json`
   - Milestone / multi-component / schema / auth: `python scripts/final_gate.py --json`
   - Epic closure: `python scripts/final_gate.py --systemic --json`
3. **CHANGELOG** — One entry under `## [Unreleased]`, format `### Added|Changed|Fixed — Title (YYYY-MM-DD)`. Gate-enforced.
4. **EXIT** — Gate auto-stages. **Never** `git add` / `git commit` myself.

## Cross-Cutting (every task)

- **Doc currency:** update `INDEX.md`, `CHANGELOG.md`, `README.md` on file/feature change. `.env.example` + `docs/CONFIGURATION.md` on env-var change. (User-guide gate **inactive** for this project.)
- **README features table:** every new feature listed with ✅ / 🚧 / ❌ status.
- **`.env.example` is authoritative** for env vars; `docs/CONFIGURATION.md` is a guide only.
- **Logging:** scaffolded logger only (`src/{package}/logger.py`). No `print()` in prod. Don't create custom logging modules.
- **Reusable code:** `src/utils/` or `src/lib/`, zero project-specific imports, `[reusable]` tag in `INDEX.md`, docstrings + types.
- **Lessons Learnt:** fill ticket's `Lessons Learnt:` line — `none` or structured entry in `docs/LESSONS_LEARNT.md`. Silence = failure.

## Hard Stops — NEVER

| Rule | Instead |
| :-- | :-- |
| `git commit` / `git add` | gate auto-stages on success |
| bare `pip install` | `/opt/fabrik-claim-validator/.venv/bin/pip install` (PEP 668) |
| Alpine base | `python:<stable>-slim-bookworm` / `node:<LTS>-bookworm-slim` |
| edit outside scope | stay strictly in ticket scope |
| modify `pyproject.toml` / `requirements.txt` | only if ticket explicitly requires deps change |
| files outside project tree | local paths only |
| Docker `ports:` exposure | route through Traefik (DOCKER-USER iptables blocks raw ports) |
| admin dashboard w/o auth boundary | Authelia forward-auth OR app-layer TOTP (see `LESSONS_LEARNT §8.13`) |
| API service w/o `X-Internal-Token` | validate `SERVICE_INTERNAL_SECRET_KEY` header |
| `/tmp/` | project `.tmp/` |
| class/module-level config | function-level only |
| raw SQL DDL | Alembic migrations only; `db/schema.sql` reference only |
| recreate `.venv` / replace existing Docker config | reuse what exists |
| overwrite existing file silently | check first; existence = STOP, ask |
| new `.md` outside allowlist | allowed: root files · scaffold docs · `docs/development/plans/YYYY-MM-DD-plan-<n>.md` · `docs/reference/**/*.md` · `docs/archive/**` |
| destructive script on prod data w/o dry-run | dry-run first, show diff |
| credentials change w/o backup + diff approval | `cp <f> <f>.backup.$(date +%Y%m%d-%H%M%S)` first |
| reorganize/flatten scaffold | follow scaffold structure verbatim |

## Essential Invariants

- **Naming:** kebab-case. Exceptions: `README.md`, `CHANGELOG.md`, `INDEX.md`, `PORTS.md`, `AGENTS.md`, `AGENTS-compact.md`, `LESSONS_LEARNT.md`, `CLAUDE.md`, `Makefile`, `Dockerfile`, Python pkgs (snake_case), auto-generated, dotfiles.
- **Ports:** Python 8000–8099, frontend 3000–3099. Register in `PORTS.md` before use. (This project owns 8002.)
- **Compose:** `platform: linux/amd64` on every build service. Service names not localhost (e.g. `DB_HOST=postgres-main`).
- **Health endpoint:** test real deps (`await db.execute("SELECT 1")`).
- **Three envs same code:** WSL dev (PG localhost, `.env`) · VPS Docker (`postgres-main`, compose) · Supabase (env vars).
- **Password policy:** 32 chars `[a-zA-Z0-9]`, `secrets.choice()`. Never `postgres`, `admin`, `password123`.
- **Before new scripts:** grep `scripts/` and `scripts/enforcement/` first. Extend, don't duplicate.

## Orientation (do first on any non-trivial task)

Scan: `README.md`, `INDEX.md`, `PORTS.md`, `compose.yaml`, `Dockerfile`, `.env.example`, `pyproject.toml`, `project.yaml`, relevant `.windsurf/rules/*.md`. When writing a plan in `docs/development/plans/`, include **Key Invariants**, **Failure Modes**, **5–10 testable Acceptance Criteria**.

## Rule Packs (`.windsurf/rules/`)

This project (`python-api`): **`10-python.md` always**. Add overlays by ticket scope:

| Task involves | Open |
| :-- | :-- |
| API endpoints/schemas | `15-api-contracts.md` |
| PostgreSQL/migrations | `25-data-postgres.md` |
| Docker/compose/ops | `30-ops.md` |
| Auth/sessions/secrets | `35-security-auth.md` |
| Doc generation | `40-documentation.md` |
| Testing / One-Test Rule | `45-testing-strategy.md` |
| Code review/gates | `50-code-review.md` |
| Logging/health/monitoring | `55-observability.md` |
| RAG/vector search | `65-rag-search.md` |
| Background workers | `75-workers-jobs.md` |
| Multi-tenant/RLS | `95-multi-tenant-saas.md` |
| TypeScript / Next.js / mobile / Chrome / WP / Docusaurus / Paddle / n8n | `20`, `42`, `60`, `62`, `70`, `80`, `85`, `90`, `ocoron-design-system.md` (only if scope expands) |

**Always apply** (cross-cutting): `CROSS_CUTTING_REQUIREMENTS.md`.
**Conflict rule:** rule pack wins over task spec — surface conflict before proceeding.

## Before Reporting Done (decision-grade audit)

- Silent / misleading / brittle failure modes handled?
- Any "debugging footgun" 6 months from now?
- **One-Test Rule:** state which test (Why + Given/When/Then + mocked vs real) in plan or commit msg.

## Boundaries

- Task contradicts project state → **stop and report**, never silently overwrite.
- File already exists → **stop**, ask before overwrite.
- No unsolicited advice or commentary outside the task.
- Risky / hard-to-reverse / shared-state actions → confirm before executing (per system policy).
