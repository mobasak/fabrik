---
activation: glob
globs: ["**/billing/**", "**/payments/**", "**/subscriptions/**", "**/terms/**", "**/privacy/**", "**/legal/**", "**/onboarding/**"]
description: SaaS product completeness — launch-blocking checklist, legal compliance, payment routing, KVKK/GDPR, abuse prevention, onboarding, tenant settings
trigger: glob
---
<!-- CONSUMER: Traycer (primary) + coding agents (verification)
     GOAL: SaaS launch-blocking gates — legal pages, payment routing, abuse prevention, tax compliance
     TRAYCER USAGE: PRIMARY CONSUMER. Reads during epic decomposition to ensure every gate maps to a ticket.
     AGENT USAGE: Verify completeness at epic closure. Check items against Done When list. -->

# SaaS Launch Checklist Rules

Apply when planning or building a SaaS product — especially during epic decomposition, epic-brief, and ticket creation. This pack answers "what must a SaaS product include?" not "how to code it." Skip for pure libraries, CLI tools, or internal services with no end-user billing.

**Source:** Gemini Deep Research (2026-05-20), validated against production experience. Generalized from project-specific checklist to universal SaaS rules.

## Three Phases

- **Phase 1:** Blocks go-live. Must complete before accepting any payment.
- **Phase 2:** First 30 days after launch.
- **Phase 3:** Scale — when paying customers exist.

Traycer must ensure every Phase 1 item maps to a feature or ticket during planning. Phase 2 and 3 items should appear in later epics or a dedicated polish/deferred epic.

---

## Phase 1: Blocks Go-Live

### Payment Routing

- **BIN-based card routing** — Turkish-issued cards (BIN lookup) → the DOMESTIC rail (**PayTR** since 2026-09-03, with iyzico as its configured fallback — `core/85-payments-billing.md` § Payment Providers is canonical). All other cards → Paddle.
- Do NOT route by IP or locale — VPN users circumvent geographic routing.
- Flat USD pricing at launch. No regional pricing (PPP) until fraud detection exists.
- Paddle's **5-day unconditional refund policy** must be in Terms of Service — Paddle suspends vendors who omit it.

> Provider selection — Paddle alone, the domestic rail alone (PayTR, iyzico as its fallback), or both — is decided during vision intake based on target market. `85-payments-billing.md` § Payment Providers is canonical for the SET; this line read "Paddle vs iyzico vs both" for a day after PayTR became the domestic rail (D-120).

### Documentation Site

Every SaaS must ship a documentation site. Vendor the template from `/opt/fabrik-lib/docs-site/` — it includes all required sections pre-configured with Ocoron design tokens, Scalar API reference, Pagefind search, and legal page templates compliant with Paddle/iyzico/GDPR/KVKK.

**Do not build a docs site from scratch.** Copy the template, customize `docusaurus.config.js`, add project-specific content.

The template ships with: Getting Started, User Guide, API Reference (Scalar), Pricing, FAQ, Changelog, Terms of Service (Paddle 5-day prorated refund, Turkish governing law), Privacy Policy (GDPR/KVKK), Cookie Policy (EU ePrivacy, CCPA "Do Not Sell").

### Legal Pages (Payment Processors Check These)

Every SaaS must ship these pages before accepting payment. The `/opt/fabrik-lib/docs-site/` template provides all of them — customize, don't write from scratch:

| Page | Route | Required Content |
|------|-------|-----------------|
| Terms of Service | `/terms` | Service description, billing policy, account termination, liability cap (12 months fees), governing law (Republic of Turkey), Paddle 5-day prorated refund (usage > 10% = prorated, credits zeroed) |
| Privacy Policy | `/privacy` | Data collected, data NOT stored, third-party processors named, GDPR lawful basis, user rights (access/delete/export), contact email |
| Cookie Policy | `/cookies` | Essential cookies listed, no tracking cookies, EU ePrivacy compliant |
| Cookie Consent | Banner (all locales) | Opt-in (not assumed), translated, EU ePrivacy + CCPA compliant |
| CCPA Link | Footer | "Do Not Sell or Share My Personal Information" — required if processing 100K+ California residents/year |

**Banned:** launching without legal pages. Payment processors (Paddle, iyzico) review your website during onboarding. Missing pages = account rejection or suspension.

### Data Protection (GDPR + KVKK)

- **Data retention policy** — define TTL for user-generated data. Implement as PostgreSQL scheduled job or application-level TTL.
- **User data rights** — access, delete, export, withdraw consent. Must be implementable (not just documented).
- **DPA template** — required for enterprise/agency customers. Paddle provides one for their scope; you need one for yours.
- **KVKK VERBIS registration** — exempt if: annual balance < 100M TRY AND < 50 employees AND no sensitive data processing. Solo operator LLC qualifies for exemption. Re-evaluate annually.

### Abuse Prevention

Full implementation spec: `saas/87-abuse-detection.md`. Phase 1 items are launch-blocking:

- [ ] Store `registration_ip` (INET) and `registration_fingerprint` (VARCHAR 64) in users table.
- [ ] IP rate limit: max 2 registrations per IP per 24h. Reject with "Too many accounts from this network."
- [ ] Disposable email domain blocklist (~5,000 domains from `data/disposable-email-domains.txt`). Reject on registration.
- [ ] Email verification required before quota/credits activate — never grant on registration alone.
- [ ] Progressive quota unlock: 30% immediate after email verification, 70% after 24h delay (defeats bot farm automation).
- [ ] Browser fingerprint hash collected on registration (client-side FingerprintJS open-source, stored server-side).

### Per-Tenant API Rate Limiting

- Every multi-tenant SaaS must implement per-tenant rate limiting to prevent noisy-neighbor resource exhaustion.
- Key rate limit counters by `tenant_id` — not by user, not by IP.
- Apply at API gateway or middleware level — before business logic executes.
- Default limits per plan tier (stored in `plan_features` table, not hardcoded).

> See `95-multi-tenant-saas.md` § Per-Tenant Rate Limiting for the mandate. This pack ensures it appears in planning.

---

## Phase 2: First 30 Days

### Onboarding & First-Use Experience

- **Empty state is a failure state.** First-time user landing on an empty dashboard with no guidance = churn.
- Minimum viable onboarding: a contextual checklist or 3-step wizard ("Create your first [domain object] → Configure [key setting] → Invite teammate").
- Onboarding must be dismissible and not re-appear after completion.
- Track onboarding completion per user (not per session).

### Organization & User Settings

Every SaaS with tenant isolation must ship:

| Settings Page | Minimum Fields |
|---------------|----------------|
| Organization settings | Name, slug, logo, default currency, timezone, billing email |
| User profile | Display name, email (change triggers verification), avatar, locale preference |
| Notification preferences | Per event-type × channel toggle (email, in-app, push) |
| Active sessions | List sessions, revoke individual sessions |

**Banned:** shipping a multi-tenant SaaS without organization settings. The org entity exists in the DB from Epic 1 — the settings UI must follow.

### Teknokent Tax Compliance (Turkish LLC)

- Software exports from Teknokent = 0% KDV under "Geçici 20. Madde."
- Paddle payouts: invoice Paddle's corporate entity as "Yazılım Lisans Bedeli."
- Include exact phrase: "3065 Sayılı KDV Kanunu Geçici 20. Madde Kapsamında Yazılım İhracatı."
- Domestic rail (PayTR, or iyzico as its fallback): issue e-Arşiv Fatura to Turkish customer, **20% KDV** (domestic sales are NOT exports — standard VAT applies). The obligation is the LANE's, not the processor's — it does not change with the vendor.
- Track in separate ledgers: Code 601 (Export) vs Code 600 (Domestic).

### SEO & Marketing Baseline

- `hreflang` tags on all localized pages (include `x-default` pointing to English).
- Dynamic XML sitemap generated at build/startup.
- Submit to Google Search Console before launch.

### Observability Baseline

- Synthetic health probe (every 6 hours): submit a known action, verify expected result.
- Gatus monitoring: API health, frontend (all locales), database TCP.
- Alert on 3 consecutive failures via Apprise.

---

## Phase 3: Scale

### Infrastructure

- When single VPS CPU consistently >70%, add worker node (workers are stateless).
- PgBouncer in transaction mode when connection count exceeds 200.
- CDN for static assets (Cloudflare free tier, 1-year TTL for `/static/*`).

### Advanced Compliance

- SOC 2 Type I — when enterprise customers demand it.
- Annual penetration testing — when handling >$100K ARR.
- Localized Terms of Service — translated by lawyer, not AI. Until then: English ToS with "English version governs" disclaimer.

### Business Monitoring

- Chargeback rate monitoring: target <0.5%, alert at >0.3%.
- Implement refund-before-chargeback flow (cheaper than losing dispute).
- Regional pricing (PPP) — only after fraud detection is in place.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Launch without ToS + Privacy Policy | Ship legal pages before first payment |
| Route payments by IP/locale | BIN-based card routing |
| Hardcoded rate limits | Plan-tier limits from `plan_features` table |
| Empty dashboard as first-use experience | Onboarding wizard or contextual checklist |
| Multi-tenant SaaS without org settings page | Ship org settings alongside tenant creation |
| GDPR "we respect your privacy" without implementation | Implement access/delete/export endpoints |
| Cookie consent assumed (pre-checked) | Opt-in consent with translated banner |
| PPP pricing without fraud detection | Flat USD pricing at launch |

---

## Related Rule Packs

- `85-payments-billing.md` — Paddle/iyzico implementation (webhook security, entitlement model, checkout)
- `81-mobile-billing.md` — mobile IAP (different model — if the SaaS has a mobile app)
- `95-multi-tenant-saas.md` — tenant isolation, RLS, per-tenant rate limiting
- `60-saas-ui.md` — billing UI, tenant UI, onboarding patterns
- `35-security-auth.md` — auth patterns (Pattern A/B), transactional email for auth flows
- `86-email-templates.md` — MJML+Jinja2 pipeline for onboarding/dunning/lifecycle emails
- `55-observability.md` — health endpoints, Gatus monitoring
- `00-domain-saas.md` — planning-level SaaS decisions (17 dimensions)

---

## Done When (Traycer reads this during decomposition)

During epic decomposition or epic-brief, verify these map to features or tickets:

- [ ] Payment routing (BIN-based: domestic rail + Paddle, or a single provider per target market)
- [ ] Legal pages (ToS, Privacy Policy, Cookie consent) — at least one epic includes them
- [ ] GDPR/KVKK data rights (access, delete, export) — implemented, not just documented
- [ ] Data retention policy with TTL enforcement
- [ ] Registration abuse prevention (IP rate limit, disposable email block, email verification, fingerprint, progressive unlock) — full spec: `saas/87-abuse-detection.md`
- [ ] Per-tenant API rate limiting (middleware-level, keyed by tenant_id)
- [ ] Onboarding flow (not empty dashboard as first experience)
- [ ] Organization settings page (name, currency, timezone, billing email)
- [ ] User profile settings (email change, avatar, locale, sessions)
- [ ] Health endpoint exempt from auth
- [ ] Observability (synthetic probe + Gatus monitoring)
- [ ] Teknokent invoicing setup (if Turkish LLC)
- [ ] `docs/FINANCIALS.md` populated with real costs, margins verified profitable at all paid tiers (worst-case check), break-even calculated
