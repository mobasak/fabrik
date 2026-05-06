<!-- MAX 6,000 chars. Current: ~5,396. Read by: Claude Code only. Don't duplicate auto-loaded packs (.windsurf/rules/CROSS_CUTTING_REQUIREMENTS.md always-on). -->
# Claude Code Contract

Solo dev (Özgür). WSL Ubuntu, Linux paths only. **Fast but good. Ship, iterate, no over-engineering.** Read this whole file before acting on any non-trivial task.

## ⚠️ FIRST OUTPUT (every response)
`RULES ACTIVE: CLAUDE-CODE | <3 rules from this file you applied>`

## Orient (every task)
1. Read `project.yaml` (`type`, `ports`, `has_user_guide`), `README.md`, `INDEX.md`, `compose.yaml`, `Dockerfile`, `.env.example`, `pyproject.toml`/`package.json`.
2. If `AFCL.md` exists, append friction findings as encountered.
3. Auto-loaded rule pack: `.windsurf/rules/CROSS_CUTTING_REQUIREMENTS.md` (always-on). Open task-specific packs as scope dictates.
4. Plans in `docs/development/plans/` need: Key Invariants, Failure Modes, 5–10 testable Acceptance Criteria.

## Behavior
- **Check before create:** verify file does not exist before write. Exists = STOP, ask.
- **Present before execute:** plan → approval → execute. Read-only calls (`Read`, `Grep`, `Glob`, `LS`) are exempt.
- **Stay on task:** no unsolicited advice or process commentary.
- **Conflict resolution:** rule pack > ticket. Surface conflict before proceeding.
- **State conflict:** task contradicts existing state → stop, report. Never silently overwrite.

## Completion Contract
1. **IMPLEMENT** — Strict ticket Scope. No hardcoded secrets/localhost (`os.getenv("KEY", "default")`). No silent failures. 1 test for highest-risk path (skip docs-only). Adjacent fixes only inside files already in Scope.
2. **GATE** — Run literal command from ticket's `Final Gate Instruction`; fix until `status: "success"`. Defaults:
   - Standard: `python scripts/final_gate.py --lean --json`
   - Milestone / multi-component / schema / auth: `python scripts/final_gate.py --json`
   - Epic closure: `python scripts/final_gate.py --systemic --json`
3. **CHANGELOG** — One entry under `## [Unreleased]`, format `### Added|Changed|Fixed — Title (YYYY-MM-DD)`. Gate-enforced.
4. **LESSONS LEARNT** — Fill ticket `Lessons Learnt:` line with `none` OR structured entry in `docs/LESSONS_LEARNT.md`. Silence = failure.
5. **EXIT** — Gate auto-stages on success. STOP. Do NOT run `git commit` / `git push` unless user said "commit" or "push" this turn. Manual `git add` is allowed.

## HARD STOPS — NEVER
| Rule | Instead |
|:--|:--|
| `git commit` / `git push` (unless user said so this turn) | gate auto-stages — task ends there |
| edit files outside ticket Scope | strict Scope only |
| modify `pyproject.toml` / `requirements.txt` / `package.json` / `uv.lock` / `package-lock.json` | only if ticket explicitly authorises deps change |
| files outside project tree | local paths only |
| bare `pip install` | `/opt/<project>/.venv/bin/pip install` (PEP 668) |
| Alpine base | `python:<stable>-slim-bookworm` / `node:<LTS>-bookworm-slim` |
| Docker `ports:` exposure | route through Traefik (DOCKER-USER iptables blocks raw ports) |
| admin dashboard w/o auth boundary | Authelia forward-auth OR app-layer TOTP (see `docs/LESSONS_LEARNT.md §8.13`) |
| API service w/o `X-Internal-Token` | validate `SERVICE_INTERNAL_SECRET_KEY` header |
| FastAPI `except Exception` without re-raising `HTTPException` first | always: `except HTTPException: raise` before generic catch — HTTPException is a subclass of Exception; bare catch converts 403/404 → 500 |
| `fabrik redeploy` on git-sourced app without `git push` first | sequence is `git commit` → `git push` → `fabrik redeploy`; Coolify pulls from GitHub remote, not local `/opt/` clone |
| `DB_HOST=localhost` or `DATABASE_URL=...@localhost:` in any env | always `postgres-main:5432` and `redis-main:6379` — `localhost` resolves to the container itself, not the shared DB |
| `/tmp/` | project `.tmp/` |
| class/module-level config | function-level only |
| raw SQL DDL | Alembic migrations only; `db/schema.sql` reference only |
| recreate `.venv` / replace existing Docker config | reuse what exists |
| new `.md` outside allowlist | allowed: root files · scaffold docs · `docs/development/plans/YYYY-MM-DD-plan-<n>.md` · `docs/reference/**/*.md` · `docs/archive/**` |
| destructive script on prod data w/o dry-run | dry-run first, show diff |
| credentials change w/o backup + diff approval | `cp <f> <f>.backup.$(date +%Y%m%d-%H%M%S)` first |
| reorganize/flatten scaffold | follow scaffold structure verbatim |

## Environment
WSL Ubuntu only. Linux paths, never Windows tooling. Code must work in all 3 envs (above) without modification.

## Pointers (content lives in linked packs)
- **Backup secrets before edit** (`.env`, `*.key`, `*.pem`, `secrets/`, `.ssh/`) → `CROSS_CUTTING_REQUIREMENTS.md` § Sensitive Data Protection.
- **Password policy** (32 chars, `[a-zA-Z0-9]`, `secrets.choice()`, banned: `postgres`/`admin`/`password123`) → `CROSS_CUTTING_REQUIREMENTS.md` § Password Policy.
- **Naming:** kebab-case. Exceptions: `README.md`, `CHANGELOG.md`, `INDEX.md`, `PORTS.md`, `AGENTS.md`, `AGENTS-compact.md`, `LESSONS_LEARNT.md`, `CLAUDE.md`, `Makefile`, `Dockerfile`, Python pkgs (snake_case), auto-generated, dotfiles.
- **Ports:** Python 8000–8099, frontend 3000–3099. Register in `PORTS.md` before use.
- **Three envs same code:** WSL dev (PG localhost, `.env`) · VPS Docker (`postgres-main`, `compose.yaml`) · Supabase (env vars).
- **Health endpoint:** test real deps (`await db.execute("SELECT 1")`).
- **Before new scripts:** `Grep` `scripts/` and `scripts/enforcement/`. Extend, don't duplicate.

## ⚠️ FINAL OUTPUT (last 4 lines, every response)
```
GATE: <command run> → success|failure
DOCS UPDATED: <files | none>
CHANGELOG: <entry title | n/a>
LESSONS LEARNT: <none | docs/LESSONS_LEARNT.md entry title>
```
Missing any line = task failure. Run gate; if `failure`, fix and re-run until `success`, then output the 4 lines.
