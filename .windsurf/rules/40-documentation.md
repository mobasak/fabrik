---
activation: glob
globs: ["*.md", "docs/**/*", "specs/**/*"]
description: Documentation rules, plan documents, writing style
---

# Documentation Rules

---

## README.md Features

**Update when:** New feature added (API endpoint, UI capability, infrastructure)
**What:** Add entry to appropriate Features table with status (✅/🚧/❌)
**Enforced:** Gate-checked

---

## CHANGELOG.md

**Update when:** Any change to code (`src/`, `scripts/`, `templates/`) or config (`Dockerfile`, `compose.yaml`, `.env.example`, `pyproject.toml`, `package.json`, `requirements.txt`)
**What:** Add entry under `## [Unreleased]` with `### Added/Changed/Fixed — Title (YYYY-MM-DD)` format
**Enforced:** Gate-checked, no exceptions

---

## Plans

**Location:** `docs/development/plans/YYYY-MM-DD-plan-<name>.md`
**When:** Non-trivial work (multi-step features, refactoring, complex bugs)
**Required sections:** Status, Goal, DONE WHEN, Out of Scope, Steps
**Note:** Traycer-managed plans exported to same location

---

## AUTO-GENERATED Blocks

**Never edit:** `docs/BUSINESS_MODEL.md` (projects), `PORTS.md` (port allocations)

---

## .env.example

**Update when:** New environment variable added
**What:** Add variable with inline comment (`.env.example` is authoritative, not `CONFIGURATION.md`)
**Enforced:** Gate-checked

---

## New .md Files (DEFAULT-DENY)

**Rule:** Edit existing docs instead of creating new ones.
**Allowed:** Root docs (`README.md`, `CHANGELOG.md`), plans (`docs/development/plans/YYYY-MM-DD-*.md`), reference (`docs/reference/**/*.md`), archive (`docs/archive/**/*.md`)
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
- **No skipped heading levels** — `##` → `###`, never `##` → `####`
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
