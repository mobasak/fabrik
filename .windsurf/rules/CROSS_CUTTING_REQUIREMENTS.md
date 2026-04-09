---
activation: always
description: Cross-cutting requirements — doc currency, observability, user guide, reusability
trigger: always_on
---
# Cross-Cutting Requirements (Auto-enforced)

## 1. Documentation Currency

Every ticket that adds, removes, or modifies functionality MUST update:

- `INDEX.md` — add/remove file entries
- `README.md` — update overview if scope changed
- `CHANGELOG.md` — append entry under [Unreleased]
- `docs/FEATURES.md` — update if user-facing feature changed
- `docs/CONFIGURATION.md` — update if new env var or config added
- `docs/QUICKSTART.md` — update if API endpoints, SDK modules, or integration surface changed

Acceptance criteria for ANY ticket implicitly includes:
"All scaffold docs reflect the changes made in this ticket."

## 2. Observability (ref: .windsurf/rules/55-observability.md)

Every service MUST implement:

- Structured logging (JSON format, correlation IDs)
- Health endpoint (`/health` or equivalent)
- Error classification (transient vs permanent)
- Log levels: DEBUG for dev, INFO for prod, ERROR for failures
- No print() — use logger exclusively
- Pre-scaffolded logger exists at `src/{package}/logger.py` (Python) or `src/logger.js` (Node)
- DO NOT create custom logging modules — import the existing one
- DO NOT use `print()` or `console.log()` — use the scaffolded logger

## 3. Docusaurus User Guide

Projects with user-facing features (APIs, UIs, CLIs) MUST include:
- `docs/user-guide/` directory with Docusaurus-compatible .md files
- Sidebar config (`sidebars.js` fragment or `_category_.json`)
- At minimum: Getting Started, Core Concepts, API Reference
- Guide pages written for END USERS, not developers
- Decision: Traycer determines in trigger_workflow whether
  this project needs a user guide (set `HAS_USER_GUIDE: true/false`
  in the project's epic brief)

## 4. Reusability & Modularity
Code MUST be structured for cross-project extraction:
- Business logic separated from framework/transport layer
- Shared utilities go in `src/utils/` or `src/lib/` with zero
  project-specific imports
- Any function that could serve another Fabrik project MUST
  be in its own module with its own docstring and type hints
- No hardcoded project-specific values in utility modules
- Tag reusable modules in INDEX.md with `[reusable]` marker
