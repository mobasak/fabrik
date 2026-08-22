# [Project Name] — Features

**Last Updated:** YYYY-MM-DD

> **Purpose:** FEATURE INVENTORY — and the CERTIFICATION COVERAGE DENOMINATOR.
> Complete feature reference for [Project Name]: internal inventory + public-facing feature docs.
> ⚠️ `/fabrik-user-test` and `/fabrik-service-test` build their journey/contract coverage FROM this
> file — a capability missing here is silently never tested, and a row nobody can exercise can't be
> certified. `/fabrik-features` converges this file to the complete, testable truth of the codebase.
> An EARLY run (right after `/fabrik-spec-review` approval) pins the PLANNED inventory — rows marked
> `(Planned)` in the Description; the certify-time REFRESH flips them to shipped or surfaces the gap.

---

## Core Features

<!-- Group features by what the user/customer cares about, not by technical module.
     Each feature: what it does, why it matters, and how to use it.
     This section doubles as marketing copy — write for the customer, not the codebase. -->

### {Feature Category 1 — e.g., "Website Provisioning"}

<!-- One paragraph: what this capability is and why it matters. -->

| Feature        | Description                                     | Endpoint / Module                              |
|----------------|-------------------------------------------------|------------------------------------------------|
| {Feature name} | {What it does — one sentence, benefit-oriented} | `POST /api/v1/{resource}` · `src/feature_x.py` |
| {Feature name} | {What it does}                                  | `src/feature_y.py`                             |

<!-- The "Endpoint / Module" column is REQUIRED on every row — it is what makes the row
     EXERCISABLE: the endpoint/module + how to invoke it is the seed the certification
     gauntlets test from, and it lets any agent jump from "what does this do?" to the
     source without spelunking. A row with no exercisable target is either not shipped
     (move to Planned) or not a feature (delete). -->

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
