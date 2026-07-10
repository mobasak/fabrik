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
1. **IMPLEMENT** — Stay within ticket Scope; adjacent fixes in same files OK. No hardcoded secrets/localhost (`os.getenv("KEY","default")`), no silent failures. **Behavior Contract:** cover every distinct user-observable behavior / acceptance criterion with a test (one per behavior, risk-ordered, TDD for the risky ones); skip trivia (getters / framework glue / config) — lean-but-complete, NOT 100%-coverage dogma (skip docs-only).
1a. **SELF-REVIEW (iterate to a fixed point)** — Don't ship first-draft code. Re-read your own diff for bugs, unhandled edge cases, and deviations from the plan (if any) and the applicable `.windsurf/rules`; fix; re-run the gate. Repeat until the gate is green AND a fresh review surfaces nothing new.
2. **GATE** — Run ticket's `Final Gate Instruction` (`scripts/final_gate.py`); fix to `status:"success"`. Flags: **`--json` (std — the FULL Tier‑2 gate: mypy + bandit + semgrep + schema/plan/docs checks)** · `--lean --json` (quick Tier‑1 subset, for fast self-review DURING iteration only — not the completion gate) · `--systemic --json` (epic). Add **`--check`** for a READ-ONLY run that never mutates the tree; a bare run auto-fixes + auto-stages **only the files your change touched** (never a whole-tree sweep — the gate scopes every fixer + `ruff` to the diff, incl. your committed-but-unpushed commits). Full tier/mode + per-check reference: `/opt/fabrik/docs/workflows/FINAL_GATE_WORKFLOW.md` (fabrik-upstream; not synced to projects).
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
| create/edit/**commit** files in a repo OTHER than the one you were launched in (cross-repo) | HALT — needs the user's **explicit approval THIS turn**. A `/opt/fabrik` agent reaching into `/opt/fabrik-lib` (or vice-versa) is the #1 cause of shared-tree commit collisions; each repo has its own gate that never sees the other's commits. Stay in your own project tree; to change another repo, tell the user which repo + why and let *its* agent do it. |
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
| DB field / enum / model changed | re-freeze `docs/data-contract.md` (via `/fabrik-data-contract`) — gate-WARN'd by `check_schema_sync.py` |
| Screen / flow / UI changed (GUI projects) | re-freeze `docs/ui-design.md` (via `/fabrik-ui-design`) |
| Recurring symptom | `docs/TROUBLESHOOTING.md` |
| Compose service added/removed | `docs/SERVICES.md` + `docs/OPERATIONS.md` |
| Resilience pattern changed | `docs/RESILIENCE.md` |
| Deploy config changed (deployed types) | `docs/DEPLOYMENT.md` |
| Doc added/removed in `docs/` | `docs/README.md` (docs index) |
| End of ticket/run | `docs/LESSONS_LEARNT.md` (canonical name; lowercase `lessons-learnt.md` is legacy-tolerated) |
| Brand / design-token change (GUI) | re-freeze `docs/design-system.md` (via `/fabrik-ui-design`) |
| Pricing / positioning change (SaaS) | `docs/BUSINESS_MODEL.md` |
| Kilo-session findings (SaaS) | `docs/STRATEGIC_BACKLOG.md` |

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
- **Authoring a prompt** (system prompt · subagent brief · skill · tool/function description · `AGENTS.md`): follow `docs/reference/MD/ai-prompt-templates.md` — the template (Part A) + the agentic patterns you MUST enforce (Part B: termination contract · evidence-before-assertion · path:line grounding · question bar · untrusted-input) + the markdown rules (Part C). Distil, don't dump.
- **Same code in 2 envs:** WSL dev (PG localhost, `.env`) · VPS Docker (`postgres-main`, `compose.yaml`). Must run unmodified. (Supabase retired as a runtime target — self-host by default; see `AGENTS.md` § Supabase.)
- **Health endpoint:** test real deps (`await db.execute("SELECT 1")`).
- **Before new scripts:** `Grep` `scripts/` + `enforcement/`. Extend, don't duplicate.
- **Script coupling header:** every `scripts/**/*.py` carries a `# AFTER-EDIT: <files to update when this script changes | none>` line in its first ~25 lines. Gate-enforced (WARN) by `check_script_headers.py` — touch-on-change: warns on a missing header or a listed coupled file you didn't also stage.
- **fabrik-lib** (`/opt/fabrik-lib/`): reusable modules — vendor (copy), don't import. Check `fabrik-lib/README.md` for the module table before building from scratch. New module = must have `README.md` + `requirements.txt` + row in `fabrik-lib/README.md` table.
- **Subagent fan-out** (detail: `.windsurf/rules/core/62-using-subagents.md`): **pool-default for gradeable fan-out** — the OpenRouter pool (`run_agents`, ≤$1.5/Mtok via `pick_models(task_type)`) is the DEFAULT worker for review finders / research grounders / doc reconcilers / rules auditors / implementers; it records + feeds the flywheel. **Native Claude Task subagents** are for GUI (`fabrik-gui`), the authoritative/high-risk pass (auth/schema/migrations/concurrency), and the decide/refute/merge you own. **BOTH, never either/or:** a *substantial* review runs the pool breadth layer (finders that record) AND native on top for the high-risk slices — native is **added**, never a replacement; going all-native lands zero flywheel rows (advisory-WARN'd). A single-shot (`tools_enabled=False`) repo-grounded pool worker (`review`/`docs`/`plan`) must set `allow_ungrounded=True` (or use `tools_enabled=True`) — the module refuses ungrounded single-shot verification (it hallucinates). **Parallelism has exactly two shapes (per `62` § Parallelism) or it SILENTLY SERIALIZES:** read-only fan-out → `tools_enabled=False` (the parallelism trigger — each its own group → parallel; `allow_ungrounded=True`+inline is a *separate* anti-refusal need for grounded `review`/`docs`/`plan`, not a parallelism condition); tools-enabled fan-out → `tools_enabled=True` + **disjoint `owned_paths`** (empty/overlapping `owned_paths` + `tools_enabled=True` = one serial group, the #1 trap). Pass `n` to `pick_models` (default `n=1`); `max_concurrency` default 4. **Flywheel rule:** a **pool** dispatch owes both a `results_table` and a `record_agent_run(spec, result)` per unit (one 0–5 verdict in both), enforced by `scripts/enforcement/check_subagent_flywheel.py`. A **native** Task subagent produces no `AgentResult` — it does **not** record. `record_run(result, …)` silently no-ops — always `record_agent_run(spec, result, …)`.

## Pipeline — next-command chaining (every `/fabrik-*` command ends by pointing to the next)

**The flow:** idea → **/fabrik-spec** → /fabrik-spec-review → *(data-shaped)* **/fabrik-data-contract** → *(GUI only)* **/fabrik-ui-design** → /fabrik-ui-design-review → **/fabrik-plan-after-chat** → /fabrik-plan-review → **/fabrik-execute-plan** (which per phase interleaves /fabrik-review + /fabrik-generate-tests + /fabrik-docs-review).

Every `/fabrik-*` command, at the end of its run, applies these three (lean — one line, not a section):
1. **Name the NEXT command** in the flow (+ the one-line why) so the operator chains without re-deriving it.
2. **Skip the GUI commands** (`/fabrik-ui-design`, `/fabrik-ui-design-review`, `/design-review`) when the project has **no user-facing UI** — the headless API/worker `SCAFFOLD_TYPES` `project.yaml::type` ∈ {`python-api`, `python-api-gpu`, `node-api`, `file-api`, `file-worker`} (and `wordpress`, which is deploy-only). The UI-bearing types run them: {`saas-skeleton`, `chrome-extension`, `mobile-app`, `desktop-app`, `static-site`, `docusaurus`}. Non-UI → go straight from the data contract (or spec) to `/fabrik-plan-after-chat`; never suggest a GUI command there.
3. **Re-freeze the data contract** — if the work changed a DB **field / enum / model** (Doc Sync Matrix), the next step is **/fabrik-data-contract** to re-freeze `docs/data-contract.md` before any plan/build consumes a stale contract.

## ⚠️ FINAL OUTPUT (last 4 lines of every task-completing response)

```
GATE: <command run> → success|failure
DOCS UPDATED: <files | none>
CHANGELOG: <entry title | n/a>
LESSONS LEARNT: <none | docs/LESSONS_LEARNT.md entry title>
```

Missing any line on a task-completing response = failure. Re-run gate until `success`, then output the 4 lines. Pure-conversational / clarifying / read-only turns are exempt — no gate, no entry, no block.

**Freshness — evidence before assertions.** The `GATE:` line must report a run made **in THIS turn**; never cite an earlier run's result. If ANY file changed since your last gate run — yours OR a sibling's on shared `master` — re-run before you claim. "Should pass" / "passed earlier" is not evidence, and a stale green is exactly how a turn claims done while the tree is red. The same rule binds every "fixed / passing / converged / reviewed" claim anywhere in a response: run the proving command in the **same message** you make the claim, read its actual output, then claim. A subagent's "success" is a claim, not proof — verify it yourself (its diff + re-run its tests).

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

To preview what the spec will trigger, **hub-side** (from `/opt/fabrik`): `fabrik plan specs/services/<id>.yaml`. `fabrik` is not on a project's PATH — from a project, ground it by **reading the spec's `shape:` block** and the flag→registrar mapping above (inspection, not a shell-out).
