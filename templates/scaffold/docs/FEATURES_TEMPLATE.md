# [Project Name] — Features

**Last Updated:** YYYY-MM-DD

> Complete feature reference for [Project Name]. Serves as both internal inventory and public-facing feature documentation.

---

## Core Features

<!-- Group features by what the user/customer cares about, not by technical module.
     Each feature: what it does, why it matters, and how to use it.
     This section doubles as marketing copy — write for the customer, not the codebase. -->

### {Feature Category 1 — e.g., "Website Provisioning"}

<!-- One paragraph: what this capability is and why it matters. -->

| Feature | Description |
|---------|-------------|
| {Feature name} | {What it does — one sentence, benefit-oriented} |
| {Feature name} | {What it does} |

<!-- For API projects, include endpoint reference per feature: -->
<!-- | Endpoint | `POST /api/v1/{resource}` | -->

### {Feature Category 2 — e.g., "DNS Management"}

| Feature | Description |
|---------|-------------|
| {Feature name} | {What it does} |
| {Feature name} | {What it does} |

### {Feature Category 3}

| Feature | Description |
|---------|-------------|
| {Feature name} | {What it does} |

---

## Technical Capabilities

<!-- Internal reference — what the system supports under the hood.
     Not marketing-facing, but useful for integration docs and agent context. -->

| Capability | Details |
|------------|---------|
| Health monitoring | `GET /health` — dependency-aware status check |
| {e.g., Authentication} | {e.g., API key, JWT, or network trust} |
| {e.g., Rate limiting} | {e.g., 100 req/min per IP} |
| {e.g., Async processing} | {e.g., Job queue with status polling} |
| {e.g., Multi-tenancy} | {e.g., Subdomain-per-customer isolation} |

<!-- Delete rows that don't apply. -->

---

## Feature Status

<!-- Track what's shipped, what's next, and what's been removed.
     Keep this lean — Traycer tracks detailed task status. -->

| Feature | Status | Notes |
|---------|--------|-------|
| {Core feature 1} | ✅ Shipped | — |
| {Core feature 2} | ✅ Shipped | — |
| {Upcoming feature} | 🔜 Planned | {Target date or milestone} |

<!-- Status key: ✅ Shipped | 🔜 Planned | ⚠️ Beta | ❌ Removed -->

---

## Removed / Deprecated

<!-- Log removed features so agents don't try to rebuild them. -->

| Feature | Removed | Reason | Migration |
|---------|---------|--------|-----------|
| (none) | — | — | — |

<!-- Example: -->
<!-- | Namecheap DNS sync | 2026-04-07 | Migrated to Cloudflare | Use `/api/cloudflare/*` endpoints | -->
