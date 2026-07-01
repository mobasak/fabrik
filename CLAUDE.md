<!-- Read by: Claude Code ≤6,000 chars. -->
# Contract

Solo dev WSL Ubuntu. **Fast but pro. Ship, iterate, no over-engineering.** Read fully before non-trivial work.

## ⚠️ FIRST OUTPUT (every task-completing response; skip on read-only / clarifying turns)
`RULES ACTIVE: CLAUDE-CODE | <3 rules from this file you applied or will apply>`

## Orient (every task)
1. `project.yaml::type` tells you which of 11 `fabrik scaffold` scaffolds this is. All projects use `.venv` for local WSL development and deploy as Docker containers via `fabrik apply` (SSH + Docker Compose to VPS).
2. `AFCL.md`: read if exists; append friction findings as you hit them.
3. Packs in `.windsurf/rules/` activate via frontmatter globs when you touch matching files. If a ticket lists specific packs in Context Files, read those too.
4. **Only when PLANNING** (producing/revising a plan): (a) read `AGENTS.md` (the canonical infra + codebase map); (b) run `python scripts/select_rules.py` and **read every ACTIVE pack + any AVAILABLE pack whose description matches the work** — binding; (c) ground every step in real `path:line`. Same awareness Traycer plans with. **Not planning** (routine implementation)? Skip this — the applicable `.windsurf/rules` auto-activate by glob when you edit matching files.
5. **When executing a plan** (`/execute-plan`): read the plan + its spec + `AGENTS.md` + all ACTIVE rule packs (via `python scripts/select_rules.py`) before starting. Those, plus `.windsurf/rules/`, `docs/`, `AFCL.md`, and codebase `Grep`, are self-service sources — exhaust them all before escalating to a human.

## Behavior
- **Check before create:** verify file does not exist before write. Exists = STOP, ask.
- **Present before execute:** plan → approval → execute. Read-only calls (`Read`, `Grep`, `Glob`, `LS`) exempt.
- **Plan-execution override:** when executing a pre-approved plan dispatched via `/execute-plan`, *present-before-execute* and *no-commit-unless-user-said-so* are **suspended for the plan's scope** — the plan IS the approval. Commit per phase (explicit paths only, never `git add -A`), run `/fabrik-review` at phase boundaries, fix autonomously, and obey all other HARD STOPS. Stop only on: 3 consecutive same-test failures, missing infra, or an unresolvable spec contradiction — format: `BLOCKED: <what> — searched: <sources> — missing: <need>`.
- **Stay on task:** no unsolicited advice or process commentary.
- **Conflict resolution:** rule pack > ticket (for *how* to write). `spec.shape` is canonical for *what* the code must match — orthogonal axis, never up for negotiation. Surface any conflict before proceeding.
- **State conflict:** task contradicts existing state → stop, report. Never silently overwrite.

## Completion Contract
1. **IMPLEMENT** — Stay within ticket Scope; adjacent fixes in same files OK. No hardcoded secrets/localhost (`os.getenv("KEY","default")`), no silent failures. 1 test for highest-risk path (skip docs-only).
1a. **SELF-REVIEW (iterate to a fixed point)** — Don't ship first-draft code. Re-read your own diff for bugs, unhandled edge cases, and deviations from the plan (if any) and the applicable `.windsurf/rules`; fix; re-run the gate. Repeat until the gate is green AND a fresh review surfaces nothing new.
2. **GATE** — Run ticket's `Final Gate Instruction` (`scripts/final_gate.py`); fix to `status:"success"`. Flags: `--lean --json` (std) · `--json` (milestone/schema/auth) · `--systemic --json` (epic). Full tier/mode + per-check reference: `/opt/fabrik/docs/workflows/FINAL_GATE_WORKFLOW.md` (fabrik-upstream; not synced to projects).
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
| `git commit` / `git push` (unless user said so this turn) | gate auto-stages — task ends there; any AI commit MUST carry Agent Provenance Trailers (§ Agent Provenance Trailers) |
| `git add -A` / `git add .` / `git commit -a` · overwriting `CHANGELOG.md` `[Unreleased]` | Shared tree — multiple agents + the daily pipeline commit to one `master`. Stage explicit paths only (`git add <file>…`); `git diff --cached --name-only` before commit; never bundle files you didn't author. Append your entry atop `[Unreleased]` (don't reset the section). After the gate auto-stages on success, `git reset` then re-add only your files. |
| edit outside ticket Scope | stay strict |
| modify deps files (`pyproject.toml`/`requirements.txt`/`package.json`/`uv.lock`/`package-lock.json`) | only if ticket authorises |
| files outside project tree | local paths only |
| foreground command likely >30s (build/deploy/test/sync/`fabrik`/`docker`/`pytest`/`npm i`) | Bash `run_in_background=true`, OR `rund -- <cmd>`; `runwait $(runlast) <s>`; `runc $(runlast)`. Doc: `docs/reference/long-command-monitoring.md` |
| `fabrik redeploy` on git-sourced app without `git push` first | commit → push → redeploy; the VPS runs `git pull` from the GitHub remote, not from your local `/opt/` |
| compose without `deploy.resources.limits.memory` | Memory limit required per service to prevent OOM on the shared VPS (Fabrik invariant; enforced by `deployer_ssh._validate_compose()`). Scaffolder auto-emits via `_write_canonical_compose`; manual composes MUST declare |
| `DB_HOST=localhost` / `DATABASE_URL=...@localhost:` | use `postgres-main:5432`, `redis-main:6379` — `localhost` = the container, not the shared DB |
| Authelia config reload via SIGHUP | exits, doesn't reload — `docker restart <authelia-container>` after edits |
| New Gatus endpoint using UUID container name | stable Docker DNS only: compose service name (Service stacks) or registered alias (single-image Apps). UUID drifts per redeploy. Pairs in `vps_apply_limits.sh` |
| Health check `/health` behind auth | Authelia bypass is **resource-based, not domain-bound** — `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on every domain routed through Authelia (hub + spokes via `authelia-vps1@file`). Never protect these paths. |
| Container ports bound to host directly | all on `fabrik` net (renamed from `coolify` 2026-05-31; `fabrik apply` rejects `coolify`); Traefik routes. Middleware (scaffold-emitted): admin `authelia-forward@docker,gzip@docker`; API `gzip@docker`; public none |
| new `.md` outside allowlist | root files · scaffold docs · `docs/development/plans/YYYY-MM-DD-plan-<n>.md` · `docs/reference/**/*.md` · `docs/archive/**` · `docs/superpowers/plans/**` · `docs/superpowers/specs/**` |
| destructive script on prod data w/o dry-run | dry-run first, show diff |
| credentials change w/o backup + diff approval | `cp <f> backups/<f>.backup.$(date +%Y%m%d-%H%M%S)` first |
| edit a **Fabrik-synced** file (canonical list: `/opt/fabrik/scripts/fabrik_synced_manifest.py` — the `.gitignore` "Fabrik-synced" block is generated from it) | these are centrally distributed from `/opt/fabrik` and **overwritten on every sync** (gate-enforced by `scripts/enforcement/check_synced_unmodified.py`). Never edit locally. If the change is correct for **ALL** projects, make it in `/opt/fabrik/<path>` + re-sync; otherwise propose it upstream — don't fork it here |
| claim "converged"/"reviewed"/"in-sync"/"100%"/"zero unknowns" without embedded proof + the matching gate green | **PLAN** → `## Evidence` per Phase (≥1 `path:line` AND ≥1 fenced command-output block) + a `## Self-audit`; set `Status: CONVERGED` only after `final_gate.py --check`. **CODE REVIEW** → `docs/development/reviews/<plan>-review.md` embedding the verbatim `final_gate.py --json` `"status":"success"` + a per-Phase verdict. **DOCS** → `docs_updater.py --check` + `check_docs.py` green + a per-file claim→proof line. A column *name* ≠ its values (read them); subagent summaries ≠ proof. `scripts/enforcement/check_convergence.py` fails the gate otherwise. Prompt templates: `docs/reference/convergence-prompts.md` |

## Doc Sync Matrix (update matched docs in same change — gate-enforced)
| Change | Update |
|---|---|
| New env var | `.env.example` + `docs/CONFIGURATION.md` |
| Code/Docker/deps changed | `CHANGELOG.md` |
| File added/removed/renamed | `INDEX.md` |
| API/SDK/CLI changed | `docs/QUICKSTART.md` |
| New port allocated | `PORTS.md` |
| Feature shipped | `docs/FEATURES.md` |
| Schema migration | Alembic + `db/schema.sql` |
| Recurring symptom | `docs/TROUBLESHOOTING.md` |
| Compose service added/removed | `docs/SERVICES.md` + `docs/OPERATIONS.md` |
| Resilience pattern changed | `docs/RESILIENCE.md` |

## Agent Provenance Trailers (required on all AI-authored commits)
Git can't distinguish AI agents — every commit is authored by the same user. Trailers are the metadata layer for post-hoc attribution (`git log --format='%h %s %(trailers:key=Agent-Role)'`).

| Trailer | Values | When |
|---|---|---|
| `Agent-Role` | `primary` · `orchestrator` · `subagent` · `review-fix` | every AI commit |
| `Agent-Phase` | `A`, `B`, `C`, … | plan execution only |
| `Agent-Task` | task number | subagent commits only |
| `Agent-Context` | short description of what the agent did | every AI commit |
| `Merged-From` | comma-separated branch list | orchestrator squash commits |
| `Conflicts-Resolved` | count | orchestrator squash commits |

Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go in the commit **body** (blank line before them), above `Co-Authored-By`. Example:
```
fix(worker): handle OOM exit code -9 in poll_worker

Agent-Role: primary
Agent-Context: added OOM detection to _handle_crashed_job, triggers alert

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```
Query: `git log --grep='Agent-Role: subagent'` · `git log --format='%h %(trailers:key=Conflicts-Resolved)'`. Plan execution extends this with `orchestrator`/`subagent`/`review-fix` roles + `Agent-Phase`/`Agent-Task`/`Merged-From` (see the execute-plan skill).

## Pointers (detail in packs)
- **Backup secrets before edit** (`.env`, `*.key`, `*.pem`, `secrets/`, `.ssh/`) → `backups/` dir (gitignored).
- **Password policy** (32-char `[a-zA-Z0-9]` via `secrets.choice()`).
- **Naming:** kebab-case. Exceptions: `README.md`, `CHANGELOG.md`, `INDEX.md`, `PORTS.md`, `AGENTS.md`, `AGENTS-compact.md`, `LESSONS_LEARNT.md`, `CLAUDE.md`, `Makefile`, `Dockerfile`, Python pkgs (snake_case), auto-generated, dotfiles.
- **Same code in 3 envs:** WSL dev (PG localhost, `.env`) · VPS Docker (`postgres-main`, `compose.yaml`) · Supabase (env vars). Must run unmodified.
- **Health endpoint:** test real deps (`await db.execute("SELECT 1")`).
- **Before new scripts:** `Grep` `scripts/` + `enforcement/`. Extend, don't duplicate.
- **fabrik-lib** (`/opt/fabrik-lib/`): reusable modules — vendor (copy), don't import. Check `fabrik-lib/README.md` for the module table before building from scratch. New module = must have `README.md` + `requirements.txt` + row in `fabrik-lib/README.md` table.

## ⚠️ FINAL OUTPUT (last 4 lines of every task-completing response)

```
GATE: <command run> → success|failure
DOCS UPDATED: <files | none>
CHANGELOG: <entry title | n/a>
LESSONS LEARNT: <none | docs/LESSONS_LEARNT.md entry title>
```

Missing any line on a task-completing response = failure. Re-run gate until `success`, then output the 4 lines. Pure-conversational / clarifying / read-only turns are exempt — no gate, no entry, no block.

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
