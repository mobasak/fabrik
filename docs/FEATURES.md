# Fabrik — Features

**Last Updated:** 2026-03-08
**Version:** 0.1.0

> This document serves as both **product documentation** and **marketing source material**.

---

## Quick Reference

| Feature | Status | Audience | Headline |
|---------|--------|----------|----------|
| [Preplan Handoff](#preplan-handoff) | ✅ Shipped | Developer | Capture intent before scaffold; every agent reads the same intent |
| [Project Scaffolding](#project-scaffolding) | ✅ Shipped | Developer | Create production-ready projects in seconds |
| [Documentation Enforcement](#documentation-enforcement) | ✅ Shipped | Developer | Never ship undocumented code again |
| [9-Step Workflow](#9-step-workflow) | ✅ Shipped | Developer | Systematic code quality from plan to commit |
| [Kilo AI Review](#kilo-ai-review) | ✅ Shipped | Developer | AI-powered code review with fix suggestions |
| [Registrar Audit & Reconcile](#registrar-audit--reconcile) | ✅ Shipped | Operator | Spec ↔ live drift detection across the fleet |
| [WordPress Provisioning](#wordpress-provisioning) | 🚧 Beta | Admin | Declarative WordPress site deployment |

**Status Legend:**
- ✅ **Shipped** — Production-ready
- 🚧 **Beta** — Available but may change
- 📋 **Planned** — On roadmap

---

## Preplan Handoff

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.2 (T3-01)

> **Headline:** Capture project intent BEFORE scaffold — every agent reads the same intent without re-deriving it.

### What It Does

The Fabrik lifecycle begins with **intent capture**. Before `fabrik scaffold` creates any files, run `fabrik preplan new <slug>` to author `docs/preplans/<YYYY-MM-DD>-<slug>.md` from a 9-section template (Idea / Project type / Shape preview / External deps / Domain / Success criteria / Out of scope / Open questions / Notes-VPS1-inventory-reminders). Refine the markdown with Opus / Claude / ChatGPT until the intent is hardened. Then `fabrik scaffold <name> --from-preplan <path>` ingests it:

1. Pre-fills `--type` from the preplan's "Project type" section
2. Pre-fills the spec's `shape:` block from the preplan's "Shape preview" yaml
3. Adopts the preplan's "Idea" first line as the project description
4. Copies the preplan to `<project>/docs/preplan.md`
5. **Appends a `Preplan:` reference line to all 4 AI guardrail files** — `AGENTS.md` (Traycer), `CLAUDE.md` (Claude Code), `AGENTS-compact.md` (Kilo), `.windsurfrules` (Windsurf) — so every downstream agent that opens the project reads the same intent

### How To Use

```bash
fabrik preplan new citation-verifier
# Edit docs/preplans/<today>-citation-verifier.md — fill in the 9 sections
fabrik scaffold citation-verifier --from-preplan docs/preplans/<today>-citation-verifier.md
```

Traycer's `docs/traycer/fabrik-workflow.md` Step 2.5 is the planning-side companion: when Traycer detects a fresh project (no scaffold yet), it looks for a matching preplan in `docs/preplans/` BEFORE asking the operator to declare anything from scratch.

### Why This Matters

Without intent capture, every downstream agent (Claude Code writing code, Kilo reviewing, Windsurf editing, Traycer planning) has to **re-derive** what the project does from incomplete context. That re-derivation is where "wait, what was this project supposed to do?" drift comes from. The preplan is the single source of truth; the 4-guardrail injection makes sure every agent reads it.

The template's `## 9. Notes` section also embeds the VPS1-inventory reminders (postgres-main:5432, redis-main:6379, X-Internal-Token pattern, `*.vps1/health` Authelia bypass, /metrics scrape target, GlitchTip DSN convention) — so agents reading the preplan stay grounded in the same VPS1 reality the scaffold-emitted guardrails enforce.

---

## Project Scaffolding

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Create production-ready projects in seconds with built-in best practices

### What It Does

Fabrik scaffold generates a complete project structure with pre-configured tooling, documentation templates, and inherited quality rules. Every scaffolded project starts with the same conventions, reducing onboarding time and ensuring consistency.

### How To Use

```bash
fabrik scaffold my-project --type python-api
```

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "Stop configuring, start building. Fabrik scaffolds production-ready projects with documentation, testing, and deployment ready to go." |
| **Email Subject** | "New project? Fabrik gets you to 'Hello World' in 30 seconds" |
| **Social Media** | "🏗️ fabrik scaffold my-app → Full project with docs, tests, CI/CD in seconds #DevTools" |
| **Sales One-liner** | "Fabrik scaffold eliminates boilerplate so teams ship features, not config." |

### Technical Details

<details>
<summary>Click to expand</summary>

**CLI Command:** `fabrik scaffold <name> [--type TYPE] [--github-create]`

**Generated Structure:**
- `src/` — Source code with `__init__.py`
- `tests/` — Test directory with sample test
- `docs/` — Documentation with FEATURES.md, INDEX.md
- `.env.example` — Environment template
- `AGENTS.md` — file copy of `/opt/fabrik/AGENTS.md` (Traycer)
- `AGENTS-compact.md` — file copy of `/opt/fabrik/AGENTS-compact.md` (Kilo CLI)
- `CLAUDE.md` — file copy of `/opt/fabrik/CLAUDE.md` (Claude Code) — *added T1-02 G-B5*
- `.windsurfrules` — file copy of `/opt/fabrik/.windsurfrules` (Windsurf Cascade)
- `.windsurf/rules/` — file copy of `/opt/fabrik/.windsurf/rules/`

**Optional flags:**

- `--github-create` (T1-02 G-B2): also creates a private GitHub repo at `mobasak/<name>` via `gh repo create … --yes`. Best-effort — missing `gh` binary or unauthenticated state log a warning and continue.

**Output trailer:** Every successful scaffold ends with a `# Next: cd /opt/<name>; open Traycer …` hint pointing at the Traycer-managed workflow (T1-02 G-B4).

**Project Types:** `python-api`, `saas-skeleton`, `node-api`, `file-api`, `file-worker`, `wordpress`, `docusaurus`, `chrome-extension`, `mobile-app`, `desktop-app`, `static-site`

</details>

---

## Documentation Enforcement

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Never ship undocumented code again

### What It Does

Automated checks ensure documentation stays in sync with code. When you add a feature, change a schema, or create an API endpoint, Fabrik reminds you to update the relevant docs.

### Enforcement Scripts

| Script | Trigger | Severity |
|--------|---------|----------|
| `check_changelog.py` | Code changes ≥10 lines | ERROR |
| `check_schema_sync.py` | DB model changes | ERROR |
| `check_readme_md.py` | Missing required sections | ERROR |
| `check_openapi_sync.py` | New API routes | WARNING |
| `check_test_coverage.py` | New public functions | WARNING |
| `check_env_example.py` | New env vars in code | WARNING |
| `check_compose_services.py` | New Docker services | WARNING |

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "Documentation that updates itself. Fabrik catches missing docs before they reach production." |
| **Email Subject** | "Your code review just got smarter: auto-doc enforcement" |
| **Social Media** | "📝 Fabrik now enforces schema.sql sync, API docs, and test coverage automatically #DevOps" |
| **Sales One-liner** | "Fabrik's enforcement scripts catch documentation drift at commit time." |

---

## 9-Step Workflow

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Systematic code quality from plan to commit

### What It Does

A structured workflow that ensures every code change goes through planning, implementation, review, and verification before commit. Token-optimized to run deterministic checks before expensive AI review.

### The Flow

```
PLAN → IMPLEMENT → SELF_REVIEW → FINAL_GATE → KILO → FINAL_GATE → VERIFY → SYNC → COMMIT
```

| Step | Action |
|------|--------|
| 1 | Traycer Plan (spec, edge cases, env vars) |
| 2 | Coder Implements |
| 2.5 | Self-Review (MANDATORY) |
| 3 | Final Gate (pre-Kilo) |
| 4 | Kilo Review Loop |
| 5 | Final Gate (post-Kilo) |
| 6 | Traycer Verification |
| 7 | Sync Only |
| 8 | Commit |

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "From idea to commit in 9 verified steps. No shortcuts, no surprises." |
| **Email Subject** | "The workflow that catches bugs before your users do" |
| **Social Media** | "🔄 9-step workflow: Plan → Code → Review → Gate → Ship. Every time. #QualityFirst" |
| **Sales One-liner** | "Fabrik's 9-step workflow embeds quality gates into every commit." |

---

## Kilo AI Review

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** AI-powered code review with actionable fix suggestions

### What It Does

Kilo is a diff-aware AI code reviewer that analyzes changes against your task spec. It identifies issues, suggests fixes, and validates plan coverage—all with structured JSON output for automation.

### How To Use

```bash
python scripts/kilo_code_review.py review <files> --plan "Task description" --output json
```

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "AI code review that understands your intent. Kilo checks your changes against your plan." |
| **Email Subject** | "Meet Kilo: Your AI code reviewer that actually reads the spec" |
| **Social Media** | "🤖 Kilo AI review: $0.03-0.40 per review, catches issues humans miss #AICodeReview" |
| **Sales One-liner** | "Kilo reviews code against your spec, not just syntax—finding logic errors, not just lint." |

---

## Registrar Audit & Reconcile

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.2 (T2-02)

> **Headline:** Spec ↔ live drift detection across the fleet, surgical destroy, fleet-wide reconcile

### What It Does

Every `fabrik apply` writes a per-spec state file (T2-01) capturing which registrars fired. T2-02 layers four operator commands on top of that foundation:

- **`fabrik audit-registrars`** — Compares each spec's shape-resolved registrars (what SHOULD be live) to the VPS's actual state (postgres `\l`, gatus `apps/<id>.yaml`, authelia config rules, backrest `config.json` plans, glitchtip project API, meilisearch index, prometheus scrape jobs, redis `assignments.json`). Outputs a pivot table or JSON. Exit 2 if any `missing`.
- **`fabrik reconcile-all`** — Walks every deployed spec, holds a per-spec file lock (T2-01 `locks_local.file_lock`), re-runs `DeploymentOrchestrator.refresh_infrastructure` per spec. Dry-run by default; `--yes` to apply. `--filter <substr>` to scope.
- **`fabrik verify <domain> --spec registrars`** — Single-domain postcondition check using the YAML-driven `PostconditionChecker`. Fails on any `missing` registrar.
- **`fabrik destroy --partial <reg>`** — Surgical un-registration without touching DNS, Coolify app, or local files. Repeatable: `--partial gatus --partial backrest`. Backed by module-level `HANDLER_ARGS` / `HANDLER_FUNCS` exports in `orchestrator/destroyer.py` (also consumed by T4-02).

### How To Use

```bash
# Audit the whole fleet
fabrik audit-registrars

# JSON for automation (alerts, dashboards)
fabrik audit-registrars --spec specs/services/translator.yaml --json | jq .

# Re-run registrars across the fleet (dry-run)
fabrik reconcile-all --filter translator

# Single-domain registrar coverage check
fabrik verify translator.vps1.ocoron.com --spec registrars

# Surgical removal of one or more registrars
fabrik destroy specs/services/translator.yaml --partial gatus --dry-run
fabrik destroy specs/services/translator.yaml --partial gatus --partial backrest -y
```

### Status Glyphs

| Glyph | Status  | Meaning                                                          |
|-------|---------|------------------------------------------------------------------|
| `✓`   | present | Shape says yes, live state agrees                                |
| `✗`   | missing | Shape says yes, live state says no                               |
| `·`   | n/a     | Shape says skip (includes `infra:` override case, reason in detail) |
| `?`   | unknown | Probe failed (e.g. SSH error, missing token, container not found)   |

A `drift` status (live exists but in a different shape than expected) is
not yet produced by any auditor — they currently check presence only.
Follow-up auditors will compare config bags.

### Excluded by design

`grafana` is intentionally excluded from destroy handlers and reports `n/a` for audit. Grafana annotations are point-in-time decorative markers, not driftable lifecycle state.

---

## WordPress Provisioning

**Status:** 🚧 Beta | **Audience:** Admin | **Since:** v0.1

> **Headline:** Declarative WordPress site deployment

### What It Does

Define your WordPress site in YAML—pages, menus, plugins, users—and Fabrik provisions it. Reproducible, version-controlled WordPress infrastructure.

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "WordPress as code. Define your site in YAML, deploy with one command." |
| **Email Subject** | "Finally: Version-controlled WordPress deployments" |
| **Social Media** | "📄 WordPress spec → 🚀 Live site. Fabrik provisions WP declaratively #WordPress #IaC" |
| **Sales One-liner** | "Fabrik treats WordPress like infrastructure: defined, versioned, reproducible." |

---

## Appendix: Marketing Asset Extraction

### All Headlines

1. **Scaffolding:** "Create production-ready projects in seconds"
2. **Doc Enforcement:** "Never ship undocumented code again"
3. **9-Step Workflow:** "Systematic code quality from plan to commit"
4. **Kilo AI:** "AI-powered code review with actionable fix suggestions"
5. **WordPress:** "Declarative WordPress site deployment"

### Feature Matrix

| Feature | OSS | Pro |
|---------|-----|-----|
| Project Scaffolding | ✅ | ✅ |
| Documentation Enforcement | ✅ | ✅ |
| 9-Step Workflow | ✅ | ✅ |
| Kilo AI Review | ✅ | ✅ |
| WordPress Provisioning | 🚧 | ✅ |

---

## See Also

- [README.md](../README.md) — Project overview
- [CHANGELOG.md](../CHANGELOG.md) — Version history
- [AGENTS.md](../AGENTS.md) — AI agent briefing
