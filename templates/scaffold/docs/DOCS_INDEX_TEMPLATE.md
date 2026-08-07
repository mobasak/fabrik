# Documentation — [Project Name]

**Last Updated:** YYYY-MM-DD

> **Purpose:** DOCUMENTATION INDEX — the table of contents for everything under `docs/`.
> Start with [QUICKSTART.md](QUICKSTART.md) for integration and setup.
> See [INDEX.md](../INDEX.md) for the master file index (whole repo, not just docs).

<!--
  HOW TO FILL: one row per doc that EXISTS in this project — delete rows for docs
  your project type doesn't carry (headless types have no ui-design; non-SaaS has
  no BUSINESS_MODEL/STRATEGIC_BACKLOG; no-DB types have no data-contract).
  The Doc Sync Matrix enforces the reverse direction: adding/removing a doc in
  docs/ means updating THIS index in the same change.
-->

## Core Docs (all projects)

| Document | Purpose |
|----------|---------|
| [QUICKSTART.md](QUICKSTART.md) | Integration contract — endpoints, SDKs, Docker wiring, 5-minute setup |
| [CONFIGURATION.md](CONFIGURATION.md) | Environment variables and settings (paired with `.env.example`) |
| [FEATURES.md](FEATURES.md) | Feature inventory — the certification coverage denominator |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Recurring symptoms and their fixes |
| [LESSONS_LEARNT.md](LESSONS_LEARNT.md) | Durable lessons — technical hurdles, AI quirks, architecture decisions |

## Deployed-Service Docs (delete section if this type doesn't deploy)

| Document | Purpose |
|----------|---------|
| [SERVICES.md](SERVICES.md) | Canonical service registry — compose services + every external dependency |
| [OPERATIONS.md](OPERATIONS.md) | Operate-it runbooks + manual fallbacks |
| [RESILIENCE.md](RESILIENCE.md) | Failure modes + §7 canonical scheduled-jobs inventory |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Deploy configuration and environments |

## Shape-Conditional Docs (keep only what applies)

| Document | Purpose |
|----------|---------|
| [data-contract.md](data-contract.md) | FROZEN field-naming truth (DB projects; via `/fabrik-data-contract`) |
| [ui-design.md](ui-design.md) | FROZEN screen/flow contract (GUI projects; via `/fabrik-ui-design`) |
| [design-system.md](design-system.md) | Brand/design tokens (GUI projects) |
| [BUSINESS_MODEL.md](BUSINESS_MODEL.md) | Monetization and positioning (SaaS) |
| [STRATEGIC_BACKLOG.md](STRATEGIC_BACKLOG.md) | Deferred-work ledger (SaaS) |
| [FINANCIALS.md](FINANCIALS.md) | Cost/revenue model — NOT scaffold-seeded; created by the epic pipeline's pre-launch gate (SaaS) |

**Subdirectories present:** [reference/](reference/) · [development/](development/) · [archive/](archive/)
<!-- List only dirs that exist. Valid set (check_structure's VALID_DOCS_SUBDIRS — all six):
     reference/ · guides/ · operations/ · development/ · superpowers/ · archive/.
     archive/ holds dated obsolete docs; superpowers/ holds spec/plan pipeline artifacts. -->
