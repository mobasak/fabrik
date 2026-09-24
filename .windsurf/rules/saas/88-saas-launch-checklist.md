---
activation: glob
globs: ["**/billing/**", "**/payments/**", "**/subscriptions/**", "**/terms/**", "**/privacy/**", "**/legal/**", "**/onboarding/**"]
applies_to: ["saas-skeleton"]
description: SaaS product completeness — launch-blocking checklist, legal pages, payment routing, KVKK/GDPR, abuse prevention, onboarding, tenant settings, Teknokent tax
trigger: glob
currency_pass: 2026-09-24
---
<!-- CONSUMER: the planning commands (/fabrik-vision's launch gates, /fabrik-spec, /fabrik-epics) + coding agents (verification)
     GOAL: SaaS launch-blocking gates — legal pages, payment routing, data rights, abuse prevention, tax compliance
     AGENT USAGE: map every Phase 1 item to a feature or ticket at planning; verify against § Done When at epic closure. -->

# SaaS Launch Checklist Rules

Apply when planning or building a SaaS product. This pack answers "what must a SaaS product include?", not "how to code it" — each item names the module or pack that owns the how. Skip for pure libraries, CLI tools, or internal services with no end-user billing.

**Sources:** every external fact below was re-grounded on 2026-09-24 (`docs/reference/research/2026-09-24-saas-launch-checklist-currency-ledger.md`); the load-bearing ones are registered in `.windsurf/rules/CLAIMS.yaml` (`pack: saas/88-saas-launch-checklist.md`). Numeric triggers with no source — the 70% CPU, 200-connection, $100K ARR, 6-hour and 1-year-TTL figures, flat USD pricing, the 0.3% alert line — are house heuristics. Legal and tax lines state what the sources say; they are not legal or tax advice — have counsel and the company's accountant (SMMM) confirm before launch.

## Three Phases

- **Phase 1:** Blocks go-live. Must complete before accepting any payment.
- **Phase 2:** First 30 days after launch.
- **Phase 3:** Scale — when paying customers exist.

Every Phase 1 item maps to a feature or ticket during planning; Phase 2 and 3 items land in later epics or a dedicated polish epic.

---

## Phase 1: Blocks Go-Live

### Payment Routing

- **Route by currency and billing model** — `core/85-payments-billing.md` § Payment Providers is canonical for the provider SET and the routing: Paddle for every currency but TRY; TRY subscriptions → iyzico, TRY one-offs → PayTR; neither domestic lane is the other's fallback. The vendored `payments` module implements it (`routing.provider_for(currency, billing_model=…)`); it has no card-BIN lookup and ignores the country hint.
- ⚠️ **Neither TRY lane can go live today** (`core/85` § Payment Providers): iyzico charges every subscription payment as Non3D against the no-Non3D policy and there is no iyzico merchant account; PayTR stays disabled in production until its fulfilment write path exists. A TRY lane at launch is a planning decision recorded in `docs/DECISIONS.md`, never an assumption.
- **Never pick a provider or a price from IP or locale** — VPN users circumvent geographic routing.
- Flat USD pricing at launch. No regional pricing (PPP) until fraud detection exists.
- **Turkish LLC:** confirm the KDV treatment with the SMMM before the first sale (§ Teknokent Tax Compliance) — it blocks go-live even though the section sits in Phase 2.
- **Refund policy (Paddle lane):** Paddle requires the site to show your terms, refund policy and buyer-support contact (email AND phone), and the buyer to accept terms and refund policy before purchase. Paddle's buyer refund policy gives consumers a statutory 14-day withdrawal right in the EU/EEA, UK, Switzerland, Turkey and Israel (waivable once digital content is used, with express consent), 7 or 5 days in a few other markets, and otherwise a discretionary 14-day window — your terms must not promise less than the buyer terms Paddle sells under.

> Provider selection — Paddle alone, a domestic lane alone, or both — is decided at vision intake by target market (`saas/00-domain-saas.md`).

### Documentation Site

Every SaaS ships a documentation site. The `saas-skeleton` scaffold already vendors it into `docs-site/` (source: `/opt/fabrik-lib/docs-site/` — Docusaurus, Scalar API reference, Pagefind search, legal page templates). Customize `docusaurus.config.js` and add the project's content; restyle it to the product's own identity per `saas/60-saas-ui.md`. **Do not build a docs site from scratch.**

It ships Getting Started, User Guide, API Reference, Pricing, FAQ, Changelog, and `legal/terms.md`, `legal/privacy.md`, `legal/cookies.md`.

### Legal Pages (Paddle checks these)

Paddle's account verification requires a pricing page, Terms of Service, Privacy Policy and Refund Policy, and its seller handbook requires the Terms to carry your legal company name and this text: *"Our order process is conducted by our online reseller Paddle.com. Paddle.com is the Merchant of Record for all our orders. Paddle provides all customer service inquiries and handles returns."* The TRY lanes (iyzico, PayTR) additionally require a privacy policy, a distance-sales contract (mesafeli satış sözleşmesi), delivery and return terms, an About page and a Contact page. Ship them before accepting payment, from the vendored templates — never from scratch:

- `legal-pages` — de-branded in-app ToS + Privacy fragments for `/terms` and `/privacy` (Jinja2 placeholders; `payment_processor` + `cooling_off_days` parametrize the refund clause).
- `docs-site/docs/legal/*.md` — the same pages for the docs site. ⚠️ Its `terms.md` still says "5 days … per Paddle's buyer terms" and "no refunds after the 5-day window", and its `cookies.md` says CCPA requires the Do-Not-Sell link unconditionally — correct both per this pack before shipping (filed to fabrik-lib).
- `cookie-consent` — the banner (opt-in, `data-i18n`, honours Global Privacy Control / DNT).

⚠️ Neither template carries the Paddle reseller clause, and none carries the TRY-lane pages (distance-sales contract, delivery and return terms, About, Contact) — add them. The `saas-skeleton` scaffold's own `app/(marketing)/terms` and `privacy` pages are generic placeholders — replace their content from `legal-pages` before launch.

| Page | Route | Required Content |
|------|-------|-----------------|
| Terms of Service | `/terms` | Service description, billing policy, refund policy (above), account termination, liability cap, governing law, legal company name, the Paddle reseller clause (above). The templates are drafted for a Turkish entity (Turkish law; `legal-pages` names Istanbul courts, the docs-site copy leaves the city blank) — wrong for a non-TR entity. The credits proration clause (≤10% of credits used → full refund, above → prorated, balance zeroed) is a HOUSE credits policy, not Paddle's. A TR entity selling to TR consumers owes the 14-day withdrawal right UNLESS the service is performed instantly in electronic form (Mesafeli Sözleşmeler Yönetmeliği md. 15/1-ğ) — and the pre-contract information must say when the right cannot be used (md. 5/1-h) |
| Privacy Policy | `/privacy` | Data collected, data NOT stored, third-party processors named, GDPR lawful basis, user rights, contact email; a statement that you do not sell or share personal information, if true (CCPA row); for a TR entity, the KVKK Art. 10 information notice (aydınlatma metni: controller identity, purposes, recipients and transfer purposes, collection method and legal basis, the Art. 11 rights) — `legal-pages`' privacy template's KVKK section lists only the rights, so it is not that notice; write it |
| Refund Policy | `/terms` section or `/refund`, linked from checkout | The refund windows above; Paddle requires it shown and accepted before purchase |
| Pricing | `/pricing` | What the buyer commits to before purchase (Paddle verification); the scaffold emits a pricing page |
| Distance-sales contract + delivery/return terms | TRY lanes | Required by iyzico and PayTR; the pre-contract information states the withdrawal right and its md. 15/1-ğ exception |
| About + Contact | TRY lanes | Required by iyzico and PayTR |
| Cookie Policy | `/cookies` | Every cookie listed with its purpose; which are strictly necessary |
| Cookie consent | Banner (all locales) | Needed only if you set non-essential cookies or similar storage. Opt-in, never assumed — a pre-ticked box is not valid consent (CJEU C-673/17 *Planet49*); strictly necessary storage is exempt |
| CCPA opt-out | Footer | CCPA applies to a business above the CPI-adjusted revenue threshold ($26,625,000 from 2025), OR one that buys, sells or shares the personal information of 100,000+ consumers or households, OR one earning 50%+ of revenue from selling or sharing it. Even then the "Do Not Sell or Share My Personal Information" link is owed only if you sell or share; say so in the Privacy Policy if you do not. Alternatives: a "Your Privacy Choices" link with the opt-out icon (11 CCR 7015(b)), or processing Global Privacy Control signals frictionlessly |

**Banned:** launching without these pages — Paddle, iyzico and PayTR check them at onboarding.

### Data Protection (GDPR + KVKK)

- **Data retention** — a TTL per class of user data, enforced by a scheduled job: vendor `gdpr-data-rights` (`data_retention.sql`, pg_cron). Audit-log retention follows `core/app-audit-log.md`.
- **Data subject rights, implemented, not documented** — `gdpr-data-rights` ships the access/export (`GET /api/v1/users/export`) and erasure (`DELETE /api/v1/users/me`) endpoints, and `account` a second self-service deletion (`DELETE /account`) — pick ONE erasure path and route the other to it. Consent is recorded with `record_consent()`; withdrawing must be as easy as giving, but the module ships only the `email_preferences.unsubscribe_token` column — build the one-click unsubscribe route and log the withdrawal with `record_consent`. GDPR grants access, erasure and portability (Art. 15, 17, 20); KVKK Art. 11 has no portability right but adds learning whether data is processed, who received it, and objecting to automated decisions — build for the union.
- **DPA** — when you process personal data on behalf of business customers you are their processor, and GDPR Art. 28(3) requires a contract (a DPA) stating the processing and the processor's eight duties. Keep a DPA template ready for B2B customers.
- **KVKK VERBIS registration** — a Turkey-resident controller is exempt with fewer than 50 employees AND an annual balance sheet under 100 million TRY, if its main activity is not processing special-category data (Board decisions 2018/87 → 2023/1154 → 2025/1572); a controller that does not keep balance-sheet books is judged on employee count alone (2025/2393). A controller resident ABROAD registers whatever its size. The balance sheet is read from the completed year's tax return, so re-check after each annual filing; a controller that becomes obliged registers within 30 days.

### Abuse Prevention

Full spec: `saas/87-abuse-detection.md`. Vendor `abuse-prevention` — it implements the items below. At launch (87 Phase 1):

- [ ] Store `registration_ip` (INET) on the users table (`store_registration_metadata`; the same call stores `registration_fingerprint` VARCHAR 64 once you collect one).
- [ ] IP rate limit: max 2 registrations per IP per rolling 24h (`ABUSE_MAX_REG_PER_IP`, default 2). It fails OPEN on a database error — monitor it.
- [ ] Disposable-email blocklist (`data/disposable-email-domains.txt`, ~5,400 domains from the upstream `disposable-email-domains` list; loaded once at import — restart after refreshing it).
- [ ] Email verification before quota/credits activate — never grant on registration alone.

Before public launch (87 Phase 2):

- [ ] Progressive quota unlock: 30% on email verification, 70% after 24h (`progressive_unlock`).
- [ ] Browser fingerprint (FingerprintJS — MIT-licensed again since v5). ⚠️ Fingerprinting is within ePrivacy Art. 5(3) — the same consent rule as cookies (EDPB Guidelines 2/2023) — and whether fraud prevention is "strictly necessary" is decided per member state. For EU users, gate it on consent or get counsel's sign-off on the exemption before collecting it.

### Per-Tenant API Rate Limiting

- Every multi-tenant SaaS implements per-tenant rate limiting to prevent noisy-neighbor resource exhaustion.
- Key rate limit counters by `tenant_id` — not by user, not by IP.
- Apply at API gateway or middleware level — before business logic executes.
- Default limits per plan tier, from the plan catalog (`plans.features` JSONB, `payments` module schema), not hardcoded.

> `saas/95-multi-tenant-saas.md` § Per-Tenant Rate Limiting owns the mandate. This pack ensures it appears in planning.

---

## Phase 2: First 30 Days

### Onboarding & First-Use Experience

- **Empty state is a failure state.** A first-time user landing on an empty dashboard with no guidance churns.
- Minimum viable onboarding: a contextual checklist or 3-step wizard ("Create your first [domain object] → Configure [key setting] → Invite teammate").
- Onboarding is dismissible and does not re-appear after completion.
- Track onboarding completion per user (not per session).

### Organization & User Settings

Every SaaS with tenant isolation ships these. Vendor `tenancy` (orgs, memberships, RBAC, invitations) and `account` (profile, verified email change, avatar, session list/revoke, account deletion); the scaffold emits only a single `/app/settings` placeholder.

| Settings Page | Minimum Fields |
|---------------|----------------|
| Organization settings | Name, slug, logo, default currency, timezone, billing email |
| User profile | Display name, email (change triggers verification), avatar, locale preference |
| Notification preferences | Per event-type × channel toggle (email, in-app, push) |
| Active sessions | List sessions, revoke individual sessions |

**Banned:** shipping a multi-tenant SaaS without organization settings. The org entity exists in the DB from Epic 1 — the settings UI must follow.

### Teknokent Tax Compliance (Turkish LLC)

Planning facts for a Turkish LLC operating in a Teknoloji Geliştirme Bölgesi (TGB). Confirm the treatment with the company's SMMM before the first invoice.

- **KDV Geçici Madde 20/1 is a production exemption, not an export rule.** Deliveries and services of application software (system management, data management, business, sectoral, internet, game, mobile, military command-control) produced EXCLUSIVELY in the TGB are exempt from KDV whoever buys them, domestic buyers included, for as long as the income/corporate-tax exemption runs (4691 Geçici Madde 2: until 31/12/2028).
- **Hosted access is covered:** the exemption also applies when the software's IP stays with the TGB firm and it is sold to different persons at intervals or shared in a virtual environment (KDV Genel Uygulama Tebliği II/G-2).
- ⚠️ **Maintenance and support services other than updates are excluded** (same section), and a ruling has treated financial-content and analysis software services as taxable at the general rate — confirm the product's classification with the SMMM.
- **Service export is a separate exemption** (KDV Kanunu md. 11/1-a with md. 12/2): the customer is abroad, the invoice is in the foreign customer's name, AND the service is used abroad.
- **Outside both exemptions, domestic sales carry the standard 20% KDV** (Presidential Decree 7346, from 10 July 2023). The rule belongs to the sale, not to the processor — it does not change between PayTR and iyzico.
- **Invoice annotation:** cite the article you actually apply — practitioners use "3065 Sayılı KDV nun Geçici 20/1 Maddesi hükümlerine göre KDV hesaplanmamıştır". Never label a Geçici 20 sale "yazılım ihracatı" — that names an export regime Geçici 20 is not.
- **Paddle payouts:** Paddle is the merchant of record and invoices the buyer; the LLC still issues its own invoice for the payout (Paddle's reverse invoices and reports are the evidence, `core/85` § Tax Documentation). Whether that invoice is an export depends on md. 12/2's conditions — no ruling found covers Paddle or a comparable merchant-of-record platform.
- **Domestic buyers:** issue an e-Arşiv Fatura to a buyer not registered for e-Fatura (VUK Genel Tebliği 509).
- **Ledgers:** 600 Yurt İçi Satışlar (domestic) vs 601 Yurt Dışı Satışlar (foreign).

### SEO & Marketing Baseline

- `hreflang` on every localized page: each version lists itself and every other version (unreciprocated tags are ignored), plus `x-default` for the fallback page.
- XML sitemap generated at build/startup (per file: 50,000 URLs or 50 MB uncompressed; split with a sitemap index beyond that).
- Tell Google about the sitemap via Search Console or a `Sitemap:` line in `robots.txt` before launch.

### Observability Baseline

- `/health` exempt from auth; Gatus monitors API health, the frontend (all locales) and database TCP, and alerts on consecutive failures (the fleet's Gatus alerts through Apprise, `configs/gatus/_base.yaml`) — `core/55-observability.md` owns the thresholds.
- A synthetic end-to-end probe (every 6 hours, this pack's rule): submit a known action, verify the expected result.

---

## Phase 3: Scale

### Infrastructure

- When single-VPS CPU is consistently >70%, add a worker node (workers are stateless).
- PgBouncer in transaction pooling once you run multiple workers or background services (`core/25-data-postgres.md` owns the pooler rules; >200 connections is a house heuristic for when). Transaction pooling drops session state — `SET`, `LISTEN`, session-level advisory locks (PgBouncer docs); `core/25` routes `LISTEN` workers around the pooler.
- CDN for static assets (Cloudflare's free plan): Cloudflare does not cache HTML or JSON by default; give content-hashed `/static/*` assets a 1-year TTL.

### Advanced Compliance

- SOC 2 — Type I (controls designed, at a point in time) when enterprise customers demand it, Type II (controls operating over a period) after.
- Annual penetration testing — when handling >$100K ARR.
- Localized Terms of Service — translated by a lawyer, not AI. Until then: English ToS with an "English version governs" clause.

### Business Monitoring

- **Dispute rate:** on the Paddle lane Paddle recovers the chargeback amount from you plus a fee of 20 USD/GBP/EUR or 40 CAD/AUD, and keeps the fee even when the dispute is won (the MSA caps it at "up to" that). Paddle's help centre sets the acceptable rate below 0.65% of monthly transaction VALUE, won disputes included (its seller handbook: 0.1–0.3% average, above 0.75% unacceptable), and may act on an excessive rate. Alert above 0.3%; act long before 0.65%.
- Refund before a dispute lands — a refund costs no chargeback fee.
- Regional pricing (PPP) — only after fraud detection is in place.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Launch without ToS + Privacy + Refund Policy | Ship the vendored legal pages before first payment |
| Route payments or prices by IP/locale | Currency + billing-model routing (`core/85`) |
| Hardcoded rate limits | Plan-tier limits from `plans.features` |
| Empty dashboard as first-use experience | Onboarding wizard or contextual checklist |
| Multi-tenant SaaS without org settings page | Ship org settings alongside tenant creation |
| GDPR "we respect your privacy" without implementation | The access/export/erasure endpoints (`gdpr-data-rights`) |
| Cookie consent assumed (pre-checked) | Opt-in consent with a translated banner (`cookie-consent`) |
| PPP pricing without fraud detection | Flat USD pricing at launch |

---

## Related Rule Packs

- `core/85-payments-billing.md` — providers, routing, webhook security, entitlements, checkout
- `mobile-app/81-mobile-billing.md` — mobile IAP (a different model, if the SaaS has a mobile app)
- `saas/95-multi-tenant-saas.md` — tenant isolation, RLS, per-tenant rate limiting
- `saas/87-abuse-detection.md` — the abuse-prevention spec
- `saas/60-saas-ui.md` — billing UI, tenant UI, onboarding patterns
- `core/35-security-auth.md` — auth patterns, transactional email for auth flows
- `core/86-email-templates.md` — onboarding, dunning and lifecycle emails
- `core/app-audit-log.md` — the audit log every project carries, and its retention
- `core/55-observability.md` — health endpoints, Gatus monitoring
- `saas/00-domain-saas.md` — planning-level SaaS decisions

---

## Done When (planning maps these to features or tickets)

- [ ] Payment routing per `core/85` (Paddle, the domestic lanes, or one provider per target market)
- [ ] Legal pages (ToS with the Paddle reseller clause, Privacy Policy, Refund Policy, Pricing, Cookie Policy + consent where needed; distance-sales contract, delivery/return terms, About and Contact on a TRY lane) — at least one epic includes them
- [ ] GDPR/KVKK data rights (access, export, erasure, consent withdrawal) — implemented, not just documented
- [ ] Data retention policy with TTL enforcement
- [ ] Registration abuse prevention at launch (IP rate limit, disposable email block, email verification); progressive unlock and fingerprint (where lawful) before public launch — full spec: `saas/87-abuse-detection.md`
- [ ] Per-tenant API rate limiting (middleware-level, keyed by tenant_id)
- [ ] Onboarding flow (not an empty dashboard as the first experience)
- [ ] Organization settings page (name, currency, timezone, billing email)
- [ ] User profile settings (email change, avatar, locale, sessions)
- [ ] Health endpoint exempt from auth
- [ ] Observability (synthetic probe + Gatus monitoring)
- [ ] Tax treatment confirmed with the SMMM before the first sale (if Turkish LLC)
- [ ] `docs/FINANCIALS.md` populated with real costs, margins verified profitable at all paid tiers (worst-case check), break-even calculated — `/fabrik-vision`'s pre-launch gate checks that it exists and has content
