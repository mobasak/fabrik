<!-- KILO CLI INJECTION LIMITS: hard cap 40,000 chars (silent truncation from bottom). Verbatim sweet spot <15,000 chars / <150 lines. Current: ~5,200 chars / ~84 lines. Use Markdown headers + tables + If-Then logic; avoid dense prose. Read by Kilo CLI only (via opencode.json). Cascade reads .windsurfrules; Claude Code reads CLAUDE.md; Traycer reads AGENTS.md. -->
# Kilo CLI Agent Rules

## ⚠️ FIRST OUTPUT (every response)
`RULES ACTIVE: KILO | <3 rules from this file you applied>`

## COMPLETION CONTRACT (Execute in order, every task)

1. **ORIENT** — Before non-trivial work, read `project.yaml` (`type`, `ports`, `has_user_guide`), `README.md`, `INDEX.md`, `compose.yaml`, relevant `src/` files. If `AFCL.md` exists, append friction findings as encountered.

2. **IMPLEMENT** — Changes scoped to current task only. Before finishing, internal audit:
   - All task requirements fully met
   - No hardcoded secrets/localhost (use `os.getenv()`)
   - No logic gaps or silent failure modes
   - Write exactly 1 test file covering the core logic path (skip for documentation-only tasks that change no code)
   - **Adjacent fixes allowed**: fix directly adjacent, low-risk issues in the same touched files/subsystem if it prevents obvious breakage

3. **QUALITY GATE** — Run and fix findings until `status: "success"`:
   - **Standard Tasks**: `python scripts/final_gate.py --lean --json`
   - **Milestone / Batch Closer**: `python scripts/final_gate.py --json`

4. **CHANGELOG** — Add one entry under `## [Unreleased]` (gate-enforced).

5. **LESSONS LEARNT** — Fill ticket `Lessons Learnt:` line with `none` OR structured entry in `docs/LESSONS_LEARNT.md`. Silence = failure.

6. **EXIT** — Gate auto-stages on success. STOP. Do NOT run `git commit` / `git push` unless user said "commit" or "push" this turn. Manual `git add` is allowed. Traycer or the user commits.

---

## CROSS-CUTTING (Every task)

1. **Doc Sync Matrix** — Update matched docs in the SAME staged change. Skipping = task failure.

| Change | Update |
|---|---|
| `src/**` file added/removed | `INDEX.md` |
| API route / CLI command added/removed/changed | `docs/QUICKSTART.md`, `docs/FEATURES.md`, `README.md` Features table |
| New `os.getenv()` var | `.env.example` (with comment: Why / How to get / Default) |
| External service credential setup changed | `docs/CONFIGURATION.md` |
| Code, Docker, deps changed | `CHANGELOG.md` (gate-enforced) |
| New port allocated | `PORTS.md` |
| Bug fix | `CHANGELOG.md ### Fixed`; if non-obvious add to `docs/TROUBLESHOOTING.md` |
| Feature shipped/deprecated/removed | `docs/FEATURES.md` |
| Future feature/refactor idea surfaces | `docs/STRATEGIC_BACKLOG.md` |
| Aha moment — struggled then solved | `docs/LESSONS_LEARNT.md` (full template) |
| Silicon ceiling — context drift, model limit, repeated mistake | `AFCL.md` |
| New plan started | `docs/development/plans/YYYY-MM-DD-plan-<name>.md` |
| Schema migration | Alembic file + `db/schema.sql` |

Skip: refactor-only / docs-only / test-only → `CHANGELOG.md` only.

2. **Structured logging** — No `print()` / `console.log()` in production code; use the project's structured logger.
3. **User guide** — If the change is user-facing AND `project.yaml` has `has_user_guide: true`, add/update a page in `docs/user-guide/`.
4. **Reusable modules** — Utility code in `src/utils/` or `src/lib/` with zero project-specific imports; tag `[reusable]` in `INDEX.md`.
5. **Naming** — kebab-case. Exceptions: `README.md`, `CHANGELOG.md`, `INDEX.md`, `PORTS.md`, `AGENTS.md`, `AGENTS-compact.md`, `LESSONS_LEARNT.md`, `Makefile`, `Dockerfile`, Python packages (snake_case per PEP 8), auto-generated, dotfiles.
6. **Search, don't guess** — For any 3rd-party API/SDK/vendor (Coolify, Paddle, Traefik, Authelia, Stripe, Supabase, Cloudflare, n8n), training data is stale. Use `web_search` / `web_fetch` MCPs to verify current docs. Cite source URL in code comment. If 3 calls don't resolve it, output `BLOCKED: <vendor> — <missing>` and stop. Skip for stdlib and language syntax.

---

## HARD STOPS — NEVER do these

| Rule | Instead |
| :--- | :--- |
| `git commit` / `git push` (unless user said so this turn) | gate auto-stages — task ends there |
| bare `pip install` | `/opt/<project>/.venv/bin/pip install` |
| Alpine base image | `python:<current-stable>-slim-bookworm` or `node:<current-LTS>-bookworm-slim` |
| edit files outside task scope | strict task boundaries |
| modify `pyproject.toml` / `requirements.txt` / `package.json` / lock files | only if task explicitly authorises deps change |
| create files outside project tree | local project paths only |
| expose Docker ports via `ports:` | route through Traefik; Docker bypasses UFW |
| admin dashboard w/o auth boundary | Authelia forward-auth (no native TOTP) OR app-layer TOTP (has one). See `docs/LESSONS_LEARNT.md §8.13` |
| FastAPI `except Exception` without re-raising `HTTPException` first | always: `except HTTPException: raise` before generic catch — bare catch silently converts 403/404 → 500 |
| `fabrik redeploy` on git-sourced app without `git push` first | sequence: `git commit` → `git push` → `fabrik redeploy`; Coolify pulls from GitHub remote, not local `/opt/` clone |
| API service w/o `X-Internal-Token` | validate `SERVICE_INTERNAL_SECRET_KEY` header |
| `/tmp/` | project `.tmp/` |

---

## ⚠️ FINAL OUTPUT (last 4 lines, every response)
```
GATE: <command run> → success|failure
DOCS UPDATED: <files | none>
CHANGELOG: <entry title | n/a>
LESSONS LEARNT: <none | docs/LESSONS_LEARNT.md entry title>
```
Missing any line = task failure. Run gate; if `failure`, fix and re-run until `success`, then output the 4 lines.
