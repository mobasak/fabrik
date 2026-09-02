---
activation: glob
globs: ["**/*.md", "docs/**/*"]
description: Documentation rules — scaffolded doc templates, Documentation Sync Matrix, plan documents, writing style
---
<!-- CONSUMER: Coding agents (all) + the planning layer (Traycer plans; the hub's epic-to-ticket workflow injects this file's matrix into ticket ACs)
     GOAL: Scaffolded doc templates, Documentation Sync Matrix, changelog, INDEX.md, writing style
     AGENT USAGE: Check which doc triggers fire for each code change. Update docs accordingly. -->

# Documentation Rules

---

## Doc ownership — who maintains what

The canonical doc set is the **type-aware registry** (`scripts/enforcement/_doc_registry.py` → `PROJECT_DOCS`), the SSOT the scaffold seed + the `check_structure` allowlist + this matrix all derive from. Two ownership layers:

### A. Coder-AI-owned — YOU write/update these as you code (per-project)

🔴 = the gate **hard-blocks the commit** if it's stale (`check_doc_sync` ERROR-tier).

**Universal (every scaffold type):**
`AGENTS.md` (scaffold seeds it; keep current on infra/topology change — and note it is now the cross-tool OPEN CONVENTION read by any agent tooling pointed at the repo, so its content bar is agent operating instructions: setup/build/test/conventions, not just a topology snapshot) · `README.md` · `INDEX.md` · `docs/README.md` · `CHANGELOG.md` 🔴 · `AFCL.md` · `docs/QUICKSTART.md` (API/SDK/CLI change) · `docs/CONFIGURATION.md` 🔴 **+ `.env.example`** 🔴 (new env var) · `docs/TROUBLESHOOTING.md` · `docs/FEATURES.md` · `docs/LESSONS_LEARNT.md` · `docs/DECISIONS.md` (the decision ledger — a decision made or received gets its row in the SAME change; rows immutable, supersede-by-new-row) · `docs/flows.md` (journeys — re-frozen via `/fabrik-flows`) · `docs/STRATEGIC_BACKLOG.md` (deferred/parked work — UNIVERSAL, every project, operator rule 2026-08-27)

**Deployed types (`python-api*` / `node-api` / `file-api` / `file-worker` / `saas-skeleton` / `wordpress`):**
`docs/SERVICES.md` · `docs/OPERATIONS.md` (compose service change) · `docs/RESILIENCE.md` · `docs/DEPLOYMENT.md` · `PORTS.md`

> **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
> Projects cannot self-deploy — the HUB's deploy agent learns from these two files what and how to
> deploy and which VPS services to set up (workers, systemd units, cron/Beat jobs, companions).
> Keep them FULLY current and machine-consumable (concrete service lists, commands, env
> requirements — not prose about intentions); a stale or vague one silently misdeploys.

**Data (`shape.needs_database`):** `db/schema.sql` 🔴 (migration) · `docs/data-contract.md` (via `/fabrik-data-contract`)

**GUI types:** `docs/ui-design.md` · `docs/design-system.md` (via `/fabrik-ui-design`)

**SaaS:** `docs/BUSINESS_MODEL.md` (this project's own monetization)

**Also coder-owned, not in the doc registry:** `specs/services/<id>.yaml` 🔴 — the **`shape:` contract**; update on any DB/cache/metrics/auth/search change or `fabrik apply` ships a broken deploy · `project.yaml` (type/port; mostly scaffold-set).

### B. Fabrik-hub-owned — do NOT edit locally (centrally synced, overwritten every sync)

`CLAUDE.md` · `AGENTS-compact.md` · `.windsurfrules` · `.windsurf/rules/**` · `opencode.json` · `docs/reference/**` — including `docs/reference/opt-project-catalog.md` (the /opt inventory — **read** it to wire to a sibling project instead of rebuilding; Fabrik regenerates it via `sync_projects.py`). These are gate-protected byte-identical by `check_synced_unmodified`.

> Retired (do not create): `docs/API_REFERENCE.md` (→ `QUICKSTART` + the live `/docs` endpoint), `docs/DATABASE_SCHEMA.md` (→ `db/schema.sql` + `docs/data-contract.md`), `docs/DOCS_INDEX.md` (→ `docs/README.md`).

**Not all docs apply to every scaffold type** — the registry buckets decide (a `file-worker` gets no GUI/SaaS docs). An empty *applicable* stub at epic end whose trigger fired = governance failure (`check_doc_stubs` WARNs it).

### How coder docs stay current — the converging doc-maintenance loop

You don't hand-author every doc update from scratch. The system keeps the coder-owned docs current cheaply, in tiers:

- **Tier-0 (deterministic, free):** the computable parts regenerate mechanically — `docs_updater.py` keeps the `INDEX.md` `AUTO-GENERATED:STRUCTURE` tree current (gate-checked); `sync_projects.py` keeps `PORTS.md`/the project catalog current. No model, no drift.
- **Tier-1 (cheap-pool author → verify → converge):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- **Backstop (mechanical, every commit):** `check_doc_sync` (ERROR: CHANGELOG/CONFIGURATION/schema; WARN: the rest) + `check_doc_stubs` (advisory) force touch-on-change; the whole-plan **`--range <base>..HEAD` coverage receipt** at Finish proves every fired-trigger doc was touched across the plan, not just the last commit. Truth still isn't mechanizable — these force the update; `/fabrik-docs-review` converges correctness.

---

## Documentation Sync Matrix (trigger-based)

When a ticket changes code, check which triggers fire and inject the corresponding doc update into Acceptance Criteria:

| Trigger | Doc update required |
|---------|---------------------|
| Source, config, or Docker file changed | `CHANGELOG.md` entry under `## [Unreleased]`; `INDEX.md` reflects change |
| New environment variable added | `docs/CONFIGURATION.md` + `.env.example` updated |
| User-facing feature added | `docs/FEATURES.md` updated |
| API endpoint added or changed | `docs/QUICKSTART.md` updated; OpenAPI synced (the live `/docs` endpoint is the detailed reference) |
| User-facing copy added | Verbal Identity applied (see `ocoron-design-system.md`) |
| `compose.yaml` modified | Docker: amd64, no Alpine, HEALTHCHECK, resource limits, `fabrik` network |
| Compose service added/removed | `docs/SERVICES.md` + `docs/OPERATIONS.md` updated (fleet-AI-consumable per D-065) |
| Deploy config changed (deployed types) | `docs/DEPLOYMENT.md` updated (fleet-AI-consumable per D-065) |
| Scheduled job (Beat/cron/systemd timer) added or changed | `docs/RESILIENCE.md` §7 (the canonical jobs/intervals inventory) + reflected in `docs/OPERATIONS.md` |
| Decision made or received (ruling, approval, retirement/adoption, architecture/scope choice, rejected option) | `docs/DECISIONS.md` row in the SAME change (rows immutable; supersede-by-new-row) |
| Resilience pattern changed (retry/backoff/circuit-breaker/fallback) | `docs/RESILIENCE.md` updated |
| Journey / persona / flow changed | `docs/flows.md` re-frozen (via `/fabrik-flows`) |
| Screen / flow / UI changed (GUI types) | `docs/ui-design.md` re-frozen (via `/fabrik-ui-design`) |
| Brand / design-token changed (GUI types) | `docs/design-system.md` re-frozen (via `/fabrik-ui-design`) |
| DB field / enum / model changed | `docs/data-contract.md` re-frozen (via `/fabrik-data-contract`) |
| Recurring symptom hit | `docs/TROUBLESHOOTING.md` updated |
| Doc added/removed in `docs/` | `docs/README.md` (docs index) updated |
| Work deferred / parked | `docs/STRATEGIC_BACKLOG.md` row |
| Database schema changed | Alembic migration (no raw DDL); `db/schema.sql` reference; `docs/data-contract.md` re-frozen (via `/fabrik-data-contract`) |
| Sensitive file edited | Backup at `<file>.backup.<timestamp>` exists |
| Logging code added | Pre-scaffolded structured logger; no `print()` / `console.log()`; correlation IDs |
| Health endpoint modified | Tests real deps: `SELECT 1`, Redis `PING`, API connectivity |
| Utility module created | `src/utils/`; `[reusable]` in `INDEX.md`; zero project-specific imports |
| `AGENTS.md` modified | `Last Updated:` line bumped |
| New enforcement script | Registered in `final_gate.py` at correct tier |
| HAS_USER_GUIDE = true | `docs/user-guide/<feature>.md` exists |

The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. The hub's epic-to-ticket workflow (`/opt/fabrik/docs/orchestrator/epic-to-ticket-workflow/06-ticket-breakdown-fabrik.md`) injects these rows per ticket.

---

## Agent Provenance Trailers (required on all AI-authored commits)

Git can't distinguish AI agents — every commit is authored by the same user. Trailers in the commit **body** are the attribution layer (`git log --format='%h %s %(trailers:key=Agent-Role)'`).

| Trailer | Values | When |
|---------|--------|------|
| `Agent-Role` | `primary` · `orchestrator` · `subagent` · `review-fix` · `ci-fix` | every AI commit (`ci-fix` = automated dispatcher/cron commits) |
| `Agent-Name` | `infra` · `fleet` · `intel` | hub sessions with `CLAUDE_AGENT` set (hub-side; most projects omit) |
| `Agent-Phase` | `A`, `B`, `C`, … | plan execution only |
| `Agent-Task` | task number | subagent commits only |
| `Agent-Context` | short description of what the agent did | every AI commit |
| `Merged-From` | comma-separated branch list | orchestrator squash commits |
| `Conflicts-Resolved` | count | orchestrator squash commits |

Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.

```
fix(worker): handle OOM exit code -9 in poll_worker

Agent-Role: primary
Agent-Context: added OOM detection to _handle_crashed_job, triggers alert
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

**Verify after committing:** `git log -1 --format='%(trailers:key=Agent-Role,valueonly)'` — empty output means the block did not parse (invisible in `git show`).

Plan execution extends this with `orchestrator`/`subagent`/`review-fix` roles + `Agent-Phase`/`Agent-Task`/`Merged-From`/`Conflicts-Resolved` — the `/fabrik-execute-plan` skill is the canonical source for that — authored at `commands/_sources/fabrik-execute-plan.md` in the hub and rendered to `~/.claude/commands/fabrik-execute-plan.md` (edit the SOURCE; the rendered copy is regenerated and hand-edits are pruned).

---

## CHANGELOG.md

**Update when:** Any change to code (`src/`, `scripts/`, `templates/`) or config (`Dockerfile`, `compose.yaml`, `.env.example`, `pyproject.toml`, `package.json`, `uv.lock`)

**Format:** Entry under `## [Unreleased]` with `### Added|Changed|Fixed — Title (YYYY-MM-DD)`

**Enforced:** Gate-checked, no exceptions. Every code-shipping ticket must produce exactly one entry.

---

## INDEX.md

**Update when:** Any file added, removed, or moved.

**What:** Reflects the current file tree with purpose annotations. Gate-checked.

---

## LESSONS_LEARNT.md

**Update when:** Ticket's Lessons Learnt field has a trigger condition and it fires. Common triggers: auth changes, password/secret rotation, deploy/infra workaround, new registrar interaction, external service integration, high-risk area.

**Format:** See the hub's `docs/orchestrator/epic-to-ticket-workflow/06-ticket-breakdown-fabrik.md` § Step 8 for the canonical entry structure (Lesson N, Context, Problem, Root Cause, Solution, Integration, Triggered By).

**Enforced:** Gate-checked. Ticket field = `none` OR entry exists. Silence = failure.

---

## Plans

**Location:** `docs/development/plans/YYYY-MM-DD-plan-<name>.md`

**When:** Non-trivial work (multi-step features, refactoring, complex bugs)

**Required sections:** Status, Goal, DONE WHEN, Out of Scope, Steps

**Note:** Traycer-managed plans exported to same location

---

## Auto-Generated Files (do not manually edit)

- `PORTS.md` — port allocations, managed by scaffold + registrar system

---

## .env.example

**Update when:** New environment variable added

**What:** Add variable with inline comment. `.env.example` is authoritative for variable documentation — `docs/CONFIGURATION.md` adds context and rationale.

**Enforced:** Gate-checked

---

## New .md Files (DEFAULT-DENY)

**Rule:** Edit existing docs instead of creating new ones.

**Allowed locations:**
- Root docs: `README.md`, `CHANGELOG.md`, `INDEX.md`, `AGENTS.md`, `CLAUDE.md`, `PORTS.md`
- Scaffolded doc templates — the registry (`_doc_registry.py::PROJECT_DOCS`) is the SSOT; the applicable set includes: `docs/CONFIGURATION.md`, `docs/FEATURES.md`, `docs/QUICKSTART.md`, `docs/DEPLOYMENT.md`, `docs/OPERATIONS.md`, `docs/SERVICES.md`, `docs/RESILIENCE.md`, `docs/TROUBLESHOOTING.md`, `docs/BUSINESS_MODEL.md`, `docs/LESSONS_LEARNT.md`, `docs/STRATEGIC_BACKLOG.md`, `docs/DECISIONS.md`, `docs/flows.md`, `docs/data-contract.md`, `docs/ui-design.md`, `docs/design-system.md`, `docs/README.md` (retired — do not create: `docs/API_REFERENCE.md`, `docs/DATABASE_SCHEMA.md`, `docs/DOCS_INDEX.md`)
- Plans: `docs/development/plans/YYYY-MM-DD-*.md` — single file, or a plan-SET directory (`YYYY-MM-DD-plan-<slug>/` spine + `T##-<slug>.md` tickets)
- Reference: `docs/reference/**/*.md`
- Archive: `docs/archive/**/*.md`
- User guides: `docs/user-guide/**/*.md` (when HAS_USER_GUIDE = true)

**Blocked:** All other new .md files

**If blocked:** STOP and ask user

---

## Writing Style

- User-facing documentation (README feature descriptions, API docs, product landing copy) follows the Ocoron Verbal Identity in `ocoron-design-system.md`.
- Lead with outcomes. Use specifics over adjectives. No forbidden language (see design system Forbidden Language table).
- Internal plans, changelogs, and developer notes are exempt from brand voice — clarity and speed matter more than tone.

---


---

## `llms.txt` — for AGENTS, never for "AI visibility"

Decide on the reader you actually have:

- **Not for AI search visibility.** Two independent methods return a null: a ~300k-domain citation
  study found removing the `llms.txt` variable *improved* prediction accuracy (it behaved as noise),
  and a ~137k-domain server-log study found 97% of published files received zero requests, with AI
  retrieval bots ~1% of what little arrived. Google states Search ignores it.
- **Yes for documentation read by CODING AGENTS** — the one measured non-null audience. In that log
  study the agent category was the largest AI consumer, and Claude Code out-fetched every AI
  retrieval bot, assistant and training crawler. Chrome files its `llms.txt` audit under *agentic
  browsing* (experimental) next to WebMCP — agent tooling, not search.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero
  from AI bots — agents never go looking. It follows (inference, not measurement) that a file only
  gets read when something points at it: reference it from the docs index or README.
- **Keep it an INDEX** — what this is, plus links to the pages that matter; not a dump.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed
  daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- Status: a community convention, no standards body, no frontier-lab commitment on the record
  either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which
  are the load-bearing agent interfaces (D-065).


## AI-Friendly Markdown Rules

Follow these when writing ANY `.md` file — they affect AI parsing quality and RAG retrieval:

- **One H1 per document** — semantic root for chunking
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Blank lines around headings, lists, code blocks** — parser boundary signals
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)
- **Always specify code language** — ` ```python `, ` ```bash `, ` ```json `
- **Lists imply constraints or steps** — don't mix narrative paragraphs inside lists
- **Keep tables simple and atomic** — no multiline cells
- **No commented-out content blocks** — dead text confuses AI and pollutes diffs
- **Structure before wording** — headings and lists first, prose second
- **Use `-` for unordered lists** — not `*` or `+` (consistency)

Full cheatsheet: `docs/reference/MD/markdown-cheatsheet.md`
Prompt design templates: `docs/reference/MD/ai-prompt-templates.md`
