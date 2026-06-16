---
activation: glob
globs: ["**/*.md", "docs/**/*"]
description: Documentation rules — scaffolded doc templates, Documentation Sync Matrix, plan documents, writing style
---
<!-- CONSUMER: Coding agents (all) + Traycer (ticket-breakdown Documentation Sync Matrix)
     GOAL: Scaffolded doc templates, Documentation Sync Matrix, changelog, INDEX.md, writing style
     TRAYCER USAGE: Ticket-breakdown injects doc sync triggers into ticket ACs from this file's matrix.
     AGENT USAGE: Check which doc triggers fire for each code change. Update docs accordingly. -->

# Documentation Rules

---

## Scaffolded Doc Templates

Every `fabrik scaffold` project emits these doc templates. They are **empty stubs** — tickets fill them during implementation. An empty template at epic end = governance failure.

| Template | Purpose | Filled by (typical ticket) |
|----------|---------|---------------------------|
| `README.md` | Primary entry point — overview, tech stack, requirements | Foundation ticket |
| `CHANGELOG.md` | All notable changes under `## [Unreleased]` | Every code-shipping ticket |
| `INDEX.md` | Single source of truth for all file purposes | Every ticket that adds/removes files |
| `docs/CONFIGURATION.md` | Environment variables and settings | Ticket that adds env vars |
| `docs/FEATURES.md` | Feature documentation with status | Feature implementation tickets |
| `docs/QUICKSTART.md` | Integration contract — endpoints, SDKs, Docker wiring | API / integration ticket |
| `docs/API_REFERENCE.md` | Detailed API documentation | API endpoint tickets |
| `docs/DEPLOYMENT.md` | Deploy instructions, `fabrik apply` config, compose | Deploy / ops ticket |
| `docs/RESILIENCE.md` | Resilience contract — deps, failure modes, recovery | Resilience ticket |
| `docs/DATABASE_SCHEMA.md` | Schema docs — tables, columns, relationships, indexes | Schema / migration ticket |
| `docs/TROUBLESHOOTING.md` | Common issues and fixes | Integration / closure ticket |
| `docs/BUSINESS_MODEL.md` | Monetization and positioning (commercial projects only) | Epic brief / planning ticket |
| `docs/LESSONS_LEARNT.md` | Lessons from incidents, auth changes, external integrations | Any ticket with a lessons trigger |
| `docs/STRATEGIC_BACKLOG.md` | Issue prevention from Kilo CLI sessions | Kilo consult tickets |
| `docs/DOCS_INDEX.md` | Documentation table of contents | Closure ticket |

**Not all templates apply to every scaffold type.** A `file-worker` has no `API_REFERENCE.md`. Mark N/A in the ticket-outline's Documentation Assignment Matrix when a template doesn't apply.

---

## Documentation Sync Matrix (trigger-based)

When a ticket changes code, check which triggers fire and inject the corresponding doc update into Acceptance Criteria:

| Trigger | Doc update required |
|---------|---------------------|
| Source, config, or Docker file changed | `CHANGELOG.md` entry under `## [Unreleased]`; `INDEX.md` reflects change |
| New environment variable added | `docs/CONFIGURATION.md` + `.env.example` updated |
| User-facing feature added | `docs/FEATURES.md` updated |
| API endpoint added or changed | `docs/QUICKSTART.md` updated; OpenAPI synced; `docs/API_REFERENCE.md` if detailed |
| User-facing copy added | Verbal Identity applied (see `ocoron-design-system.md`) |
| `compose.yaml` modified | Docker: amd64, no Alpine, HEALTHCHECK, resource limits, coolify network |
| Database schema changed | Alembic migration (no raw DDL); `db/schema.sql` reference; `docs/DATABASE_SCHEMA.md` |
| Sensitive file edited | Backup at `<file>.backup.<timestamp>` exists |
| Logging code added | Pre-scaffolded structured logger; no `print()` / `console.log()`; correlation IDs |
| Health endpoint modified | Tests real deps: `SELECT 1`, Redis `PING`, API connectivity |
| Utility module created | `src/utils/`; `[reusable]` in `INDEX.md`; zero project-specific imports |
| `AGENTS.md` modified | `Last Updated:` line bumped |
| New enforcement script | Registered in `final_gate.py` at correct tier |
| HAS_USER_GUIDE = true | `docs/user-guide/<feature>.md` exists |

This matrix is the canonical source. `my-workflow/06-ticket-breakdown-command` injects these rows per ticket.

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

**Format:** See `my-workflow/06-ticket-breakdown-command` § Step 8 for the canonical entry structure (Lesson N, Context, Problem, Root Cause, Solution, Integration, Triggered By).

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
- Scaffolded doc templates: `docs/CONFIGURATION.md`, `docs/FEATURES.md`, `docs/QUICKSTART.md`, `docs/API_REFERENCE.md`, `docs/DEPLOYMENT.md`, `docs/RESILIENCE.md`, `docs/DATABASE_SCHEMA.md`, `docs/TROUBLESHOOTING.md`, `docs/BUSINESS_MODEL.md`, `docs/LESSONS_LEARNT.md`, `docs/STRATEGIC_BACKLOG.md`, `docs/DOCS_INDEX.md`
- Plans: `docs/development/plans/YYYY-MM-DD-*.md`
- Reference: `docs/reference/**/*.md`
- Archive: `docs/archive/**/*.md`
- Traycer: `docs/traycer/**/*.md`
- User guides: `docs/user-guide/**/*.md` (when HAS_USER_GUIDE = true)

**Blocked:** All other new .md files

**If blocked:** STOP and ask user

---

## Writing Style

- User-facing documentation (README feature descriptions, API docs, product landing copy) follows the Ocoron Verbal Identity in `ocoron-design-system.md`.
- Lead with outcomes. Use specifics over adjectives. No forbidden language (see design system Forbidden Language table).
- Internal plans, changelogs, and developer notes are exempt from brand voice — clarity and speed matter more than tone.

---

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
