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

- User-facing documentation (README feature descriptions, API docs, product landing copy) follows the Ocoron Verbal Identity in `docs/reference/ocoron-design-system.md`.
- Lead with outcomes. Use specifics over adjectives. No forbidden language (see design system Forbidden Language table).
- Internal plans, changelogs, and developer notes are exempt from brand voice — clarity and speed matter more than tone.
