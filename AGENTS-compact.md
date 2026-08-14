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
0. **Task→skill routing:** at run start (not mid-run), classify the request against the pipeline stages — `1-design`(spec/spec-review) · `2-contract`(data/UI) · `3-plan`(plan-after-chat/plan-review) · `4-build`(execute-plan) · `5-certify`(user-test/service-test/features) · `6-release`(release) · `gate`(code/repo/rules/workflow/rendered-UI; loops to no-op) · `utility`(anytime, no fixed slot) — Claude Code agents: invoke the matching skill; other agents: state the stage, follow its workflow. Chain: 1→2→3→4→5→6 (gate/utility apply throughout). Fork: data-shaped→2-contract; GUI→also ui-design; headless skips GUI. Escape: mismatch→say so, proceed; no match→proceed silently.
1. `project.yaml::type` — one of 11 `fabrik scaffold` scaffolds. All projects use `.venv` and deploy via `fabrik apply` (SSH + Docker Compose to the VPS).
2. `AFCL.md`: read if exists; append friction findings as you hit them.
3. **Only when PLANNING** (producing/revising a plan): read `AGENTS.md` (canonical infra + codebase map); run `python scripts/select_rules.py` and read every ACTIVE pack + any AVAILABLE pack whose description matches the work (binding); ground every step in real `path:line`. Same awareness Traycer plans with. **Not planning** (routine implementation)? Skip this — the applicable `.windsurf/rules` auto-activate by glob when you edit matching files.
4. **Executing a plan:** read the plan + its spec + `AGENTS.md` + all ACTIVE packs (`python scripts/select_rules.py`) first. Those + `.windsurf/rules/`, `docs/`, `AFCL.md`, codebase grep are self-service sources — exhaust them all before escalating to a human.

## BEHAVIOR
- **Check before create:** file exists = STOP, ask.
- **Present before execute:** plan → approval → execute. Read-only ops exempt.
- **Plan-execution override:** executing a pre-approved plan suspends *present-before-execute* **for the plan's scope** — the plan IS approval (task-end commits are ALWAYS required per § EXIT; the plan additionally mandates them per phase). Commit per phase (explicit paths only, never `git add -A`), run the code-review workflow at phase boundaries, fix autonomously, obey all other HARD STOPS. Stop only on: 3 consecutive same-test failures, missing infra, or an unresolvable spec contradiction — `BLOCKED: <what> — searched: <sources> — missing: <need>`.
- **Stay on task:** no unsolicited advice or process commentary.
- **State conflict:** task contradicts existing state → stop, report. Never silently overwrite.

## COMPLETION CONTRACT (in order, every task)
1. **IMPLEMENT** — Stay within ticket Scope; adjacent fixes in same files OK. No hardcoded secrets/localhost (`os.getenv("KEY","default")`), no silent failures. 1 test for highest-risk path (skip docs-only); a test you add/modify must be SEEN RED once (fail-first, or neuter→red→restore→green).
1a. **SELF-REVIEW (iterate to a fixed point)** — Don't ship first-draft code. Re-read your diff for bugs, edge cases, and deviations from the plan (if any) and the applicable `.windsurf/rules`; fix; re-run the gate. Repeat until green AND a fresh review finds nothing new.
2. **GATE** — Run ticket's `Final Gate Instruction` (`scripts/final_gate.py`); fix to `status:"success"`. Flags: **`--json` (std — FULL Tier 2: mypy+bandit+semgrep+schema/plan/docs)** · `--lean --json` (fast Tier‑1 subset for in-iteration self-review, NOT the completion gate) · `--systemic --json` (epic). Add **`--check`** for a read-only run (never mutates); a bare run auto-fixes + auto-stages **only your changed files** (the gate scopes every fixer + `ruff` to the diff, incl. committed-unpushed; Fabrik-synced files are excluded in projects). Full tier/mode ref: `docs/workflows/FINAL_GATE_WORKFLOW.md`.
3. **CHANGELOG** — One entry under `## [Unreleased]`: `### Added|Changed|Fixed — Title (YYYY-MM-DD)`. Gate-enforced.
4. **LESSONS LEARNT** — Ticket field = `none` OR entry in `docs/LESSONS_LEARNT.md`. Silence = failure.
5. **EXIT** — Gate green → COMMIT your own work NOW (explicit pathspecs — `git commit -- <your files>` — with Agent Provenance Trailers; never bundle files you didn't author), then PUSH it (`git push`; rejected → dirty tree: defer, wip-net protects · clean tree: `git pull --rebase=merges` then push · conflict: abort + report · NEVER --force). An uncommitted or unpushed task is an UNFINISHED task. Ad-hoc NON-plan branch work: DEFAULT = merge to base then push base; present keep/discard only when genuinely arguable (merge → verify merged result → then cleanup).

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
| Compose service added/removed | `docs/SERVICES.md` + `docs/OPERATIONS.md` |
| Resilience pattern changed | `docs/RESILIENCE.md` |
| Feature shipped/deprecated | `docs/FEATURES.md` |
| New plan | `docs/development/plans/YYYY-MM-DD-plan-<name>.md` |
| Schema migration | Alembic + `db/schema.sql` |
| Future idea | `docs/STRATEGIC_BACKLOG.md` (Now/Later/Context) |
| Aha moment | `docs/LESSONS_LEARNT.md` |
| Silicon ceiling | `AFCL.md` |
| Pricing / GTM | `docs/BUSINESS_MODEL.md` |

**Skip:** refactor/docs/test-only → `CHANGELOG.md` only.

## AGENT PROVENANCE TRAILERS (every AI commit)
Git can't tell agents apart — every commit shows the same user. Add trailers to the commit **body** as ONE paragraph — blank line before the block, **no blank line inside it** (a blank line before `Co-Authored-By:` makes git ignore every `Agent-*` line above it) for attribution.

| Trailer | Values | When |
|---|---|---|
| `Agent-Role` | `primary`/`orchestrator`/`subagent`/`review-fix` | every AI commit |
| `Agent-Phase` | `A`,`B`,`C`… | plan execution |
| `Agent-Task` | task # | subagent commits |
| `Agent-Context` | what the agent did | every AI commit |
| `Merged-From` / `Conflicts-Resolved` | branch list / count | orchestrator squash |

Standalone (non-plan) work → `Agent-Role: primary` + `Agent-Context: <what you did>`. Plan execution roles + phase/task/merge trailers: `.claude/commands/execute-plan.md`. Query: `git log --grep='Agent-Role: subagent'`.

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
8. **Subagent dispatch** (full rule: `.windsurf/rules/core/62-using-subagents.md` § Dispatch policy + § Parallelism) — gradeable fan-out (review finders / grounders / reconcilers / auditors / implementers) → **pool-default** (OpenRouter pool `run_agents`/`pick_models`, ≤$1.5/Mtok, records to the `subagent_runs` flywheel via `record_agent_run` — ⚠️ NOT `record_run`, which no-ops); native Claude subagents added **on top** for GUI / authoritative-high-risk / decide-merge. **Two-shape parallelism — a fan-out that is neither SILENTLY SERIALIZES:** read-only → `tools_enabled=False` (the trigger — each its own group → parallel; `allow_ungrounded=True`+inline is a *separate* anti-refusal need for grounded `review`/`docs`/`plan`); tools-enabled → `tools_enabled=True` + **disjoint `owned_paths`** (empty/overlapping = one serial group, the #1 trap). Pass `n` to `pick_models` (default `n=1`); `max_concurrency` default 4.

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

4. **Authelia** — No SIGHUP support (exits). After `configuration.yml` edit: `docker restart <authelia-container>`. Bypass is **resource-based, not domain-bound** — `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on every domain routed through Authelia (hub services direct + spoke services via `authelia-vps1@file` middleware). Never protect these paths.

## DOCKER & DEPLOY
1. **No `localhost` in connection strings** — Inside containers, `localhost` = the container itself, not the host. Use Docker network DNS:

   | Var | ❌ Wrong | ✅ Correct |
   |---|---|---|
   | `DB_HOST` | `localhost` | `postgres-main` |
   | `DATABASE_URL` | `...@localhost:5432/...` | `...@postgres-main:5432/...` |
   | `REDIS_URL` | `redis://localhost:6379` | `redis://redis-main:6379` |

   Verify before deploy: `grep -E '^(DB_HOST|DATABASE_URL|REDIS_URL)=' .env | grep localhost` must return nothing.

2. **Post-deploy checklist (every new service):**
   - **Network:** containers on the `fabrik` Docker network (renamed from `coolify` 2026-05-31; `fabrik apply` rejects a compose declaring `coolify`); never bind ports to host; Traefik routes via labels.
   - **Traefik middleware** (scaffold-emitted): admin UI → `authelia-forward@docker,gzip@docker`; API → `gzip@docker`; public → none.
   - **.env / service env:** `SERVICE_INTERNAL_SECRET_KEY`, `DATABASE_URL` (`postgres-main`), `REDIS_URL` (`redis-main`) — written to `/opt/<name>/.env` by `deployer_ssh`.
   - **Health:** `/health` → 200; brought up via `docker compose up -d --wait` + monitored by Gatus.

3. **`fabrik redeploy` on git-sourced app** — sequence: `git commit` → `git push` → `fabrik redeploy`. The VPS runs `git pull` from the GitHub remote (not your local `/opt/` clone).

4. **Gatus stable DNS** — Never use UUID container names in Gatus or inter-service URLs (they drift per redeploy). Use a stable `container_name` / compose service name.

## HARD STOPS — NEVER
| Rule | Instead |
|:--|:--|
| `git push --force`/`-f` to ANY shared branch · pushing a branch you don't own · a commit WITHOUT Agent Provenance Trailers · bundling files you didn't author into a commit | committing AND PUSHING your own work at task end is REQUIRED (§ EXIT); the only sanctioned force-push is `wip_backup.sh`'s `refs/wip/*` backup refs |
| `git add -A` / `git add .` / `git commit -a` · overwriting `CHANGELOG.md` `[Unreleased]` | Shared tree — multiple agents + the daily pipeline commit to one `master`. Stage explicit paths only (`git add <file>…`); `git diff --cached --name-only` before commit; never bundle files you didn't author. Append your entry atop `[Unreleased]` (don't reset the section). After the gate auto-stages on success, `git reset` then re-add only your files. |
| edit outside ticket Scope | stay strict |
| modify deps files (`pyproject.toml`/`requirements.txt`/`package.json`/`uv.lock`/`package-lock.json`) | only if ticket authorises |
| files outside project tree | local paths only — EXCEPT `/opt/fabrik-mail/` (operator-sanctioned fabrik-mail store: `mail.py`/`mail_notify.py` read+write the durable `<repo>/{inbox,archive}` mailboxes there) |
| bare `pip install` | `/opt/<project>/.venv/bin/pip install` (PEP 668) |
| Alpine base image | `python:<stable>-slim-bookworm` / `node:<LTS>-bookworm-slim` |
| Docker `ports:` exposure to host | route through Traefik (DOCKER-USER blocks raw ports) |
| compose without `deploy.resources.limits.memory` | memory limit is REQUIRED per service — enforced fatally by `deployer_ssh._validate_compose()`. Scaffolder auto-emits via `_write_canonical_compose` |
| admin dashboard w/o auth | Authelia forward-auth OR app-layer TOTP |
| FastAPI `except Exception` swallowing `HTTPException` | always `except HTTPException: raise` before generic catch |
| foreground command likely >30s (build/deploy/test/sync/`fabrik`/`docker`/`pytest`/`npm i`) | `scripts/rund -- <cmd>`; `runwait $(runlast) <s>`; `runc $(runlast)`. Doc: `docs/reference/long-command-monitoring.md` |
| new `.md` outside allowlist | root files · scaffold docs · `docs/development/plans/YYYY-MM-DD-plan-<n>.md` · `docs/reference/**/*.md` · `docs/archive/**` · `docs/superpowers/plans/**` · `docs/superpowers/specs/**` |
| destructive script on prod data w/o dry-run | dry-run first, show diff |
| credentials change w/o backup + diff approval | `cp <f> <f>.backup.$(date +%Y%m%d-%H%M%S)` first |
| `/tmp/` | project `.tmp/` |
| class/module-level config | function-level only |
| raw SQL DDL | Alembic migrations only; `db/schema.sql` reference only |
| recreate `.venv` / replace existing Docker config | reuse what exists |

## ⚠️ FINAL OUTPUT (last 6 lines)
```
GATE: <command run> → success|failure
DOCS UPDATED: <files | none>
CHANGELOG: <entry title | n/a>
LESSONS LEARNT: <none | docs/LESSONS_LEARNT.md entry title>
DONE: <one line — what this run delivered: commits/artifacts, not intentions>
NEXT: <named successor — /fabrik-<x> <args> | operator decision: <what> | none — terminal>
```
Missing any line = task failure. Re-run gate until `success`, then output 6 lines. `NEXT:` must be runnable without re-derivation; a vague NEXT ("continue") is a missing line; own-session work named in NEXT is dispatched, not narrated.

**EVERY OTHER response ends with the two-line STATE footer** (operator mandate 2026-08-10 — no
exempt turns: conversational, clarifying, read-only, mid-plan status all carry it):
```
STATE: <where things stand — stage/board/loop position, one line>
NEXT: <successor command · operator decision awaited · "awaiting your reply" · none — terminal>
```
It never replaces the 6-line block on a task-completing response; a footer `NEXT:` naming
undispatched own-session work is the same checkpoint-stall the Stop hook blocks.

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
