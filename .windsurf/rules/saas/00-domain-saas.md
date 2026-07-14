---
activation: glob
globs: ["**/tenants/**", "**/billing/**", "**/plans/**", "**/subscription*/**", "**/pricing/**"]
description: SaaS domain — PLANNING layer. The 17 vision-intake dimensions (ICP, pricing axis, GTM, COGS-per-tenant vs the single-VPS ceiling, risk register, dated kill criteria) and the epic-decomposition directives. Consumed by the mega-epic planner; the sibling packs (60/87/88/95) own the code-time discipline.
trigger: glob
---
<!-- CONSUMER: the mega-epic planner (vision intake + epic decomposition), and any agent scoping SaaS work.
     GOAL: settle the IRREVERSIBLE, business-shaping decisions BEFORE epics exist. This is business formation,
           not code discipline — 60-saas-ui.md, 87-abuse-detection.md, 88-saas-launch-checklist.md and
           95-multi-tenant-saas.md own every code-time fact. Cite them; NEVER restate them.
     PROVENANCE: promoted from docs/traycer/mega-epic-breakdown/domain-modules/saas.md (2026-07-13). That
           module's Part 2 (per-epic implementation guidance) was ~90% a duplicate of the packs above AND
           provably unwired — zero `domain-modules` references exist anywhere in epic-to-ticket-workflow/ —
           so it was dropped, not migrated.
     ⚠️ The 17 dimensions below have ZERO pack coverage and are the reason this file exists. -->

# SaaS Domain — Planning Layer (vision intake + epic decomposition)

## Operating Lens (solo + AI fleet)

- **Build cost is cheap** — agents implement. Scope-heavy is fine *if* it stays low-maintenance.
- **Your time is the scarce resource** — optimize every default for **set-and-forget ops**, not minimal scope.
- **Pro-grade is non-negotiable** — automate to remove yourself, never to cut quality.

## Completeness Test (apply per dimension)

A dimension belongs at intake **only if** getting it wrong is **irreversible** or **kills the business before build**. Everything else is downstream (`02`/`05`). Resolve each or log as Open Question. **No "TBD" survives confirmation.**

---

## Part 1 — Mega-Epic Decomposition Guidance

*Consumed by `02-epic-decomposition-command` (and `00-trigger-workflow-command` Step E4 in EXISTING mode) to drive SaaS-specific epic patterns.*

### 1A. Vision Intake Dimensions

#### 1. Market & Positioning

**Force:** named ICP, the one painful workflow, 3-5 named competitors, positioning statement (`For [ICP] who [pain], X is a [category] that [benefit], unlike [alt]`), one-sentence moat.

**Default:** vertical wedge with unfair depth (D2C beauty intel). Moat = domain depth + proprietary data, never features.

**Why now:** positioning drives every word of pricing, marketing, onboarding. Wrong here = incoherent everywhere.

#### 2. Geographic Market

**Force:** Turkey-first vs international-first. Sets language, currency, compliance, channel.

**Default:** **build international-grade (en-first), anchor in TR.** Rebul = anchor reference + Teknokent KDV billing; scale ICP/channel target the larger EN market.

**Why now:** retrofitting i18n, currency, and EN content onto a TR-only product is a rebuild.

#### 3. B2B Buying Process

**Force:** economic buyer vs champion vs end-user; security-review/procurement friction; sales-cycle length.

**Default:** target a buyer who is also the user (PLG-compatible). If procurement-heavy, PLG breaks, reconsider.

**Why now:** the buying committee decides whether self-serve even works — i.e. whether you stay low-maintenance.

#### 4. Product & Architecture (6 irreversibles)

Reference `.windsurf/rules/saas/95-multi-tenant-saas.md` for implementation detail. At intake, force:

- **Tenancy:** shared postgres-main + `tenant_id` + Postgres RLS (`fabrik-lib/fastapi-user-auth` owns the `auth` schema natively — `auth.uid()` over the `request.jwt.claims` GUC). DB-per-tenant only if contractually required.
- **Identity/org:** `fabrik-lib/fastapi-user-auth` (Pattern A — the app issues its own JWTs: Argon2, refresh-token rotation, `jti` denylist, tenant-isolation RLS) for users + org/role/invite model; Authelia for back-office only. Pattern A is THE default per `core/35-security-auth.md`; Supabase Auth is legacy/migration-only (see `AGENTS.md § Supabase`).
- **Billing+gating:** plan-to-feature gating matrix exists *before* features. **Provider picked by target market** per `.windsurf/rules/core/85-payments-billing.md` (providers) + `.windsurf/rules/saas/88-saas-launch-checklist.md` § Payment Routing (⚠️ **BIN-based card routing lives in 88, NOT 85** — 85 contains no routing rules) § Payment Providers: **Paddle Billing v2 (MoR)** for international, **iyzico** for Turkish domestic, **both** when serving both markets (BIN-based card routing). Stripe is unavailable to a Turkey-resident entity — do NOT plan around it.
- **Metering:** redis-main counters reconciled to postgres-main for billing-grade truth. Never bill off Redis alone.
- **Isolation+audit:** RLS/tenant-scope enforced in one place; audit log + soft-delete + per-tenant export.
- **Activation event:** the one action = "got value," instrumented from commit #1.
- **Abuse prevention (LAUNCH-BLOCKING per `.windsurf/rules/saas/88-saas-launch-checklist.md` § Abuse Prevention + the full spec in `saas/87-abuse-detection.md`).** Free tiers attract abuse — without these, the free tier bleeds revenue. Phase 1 items are non-negotiable at launch: (1) store `registration_ip` (INET) + `registration_fingerprint` (VARCHAR 64) on the users table; (2) IP rate limit — max **2 registrations per IP / 24h**; (3) disposable-email blocklist (~5,000 domains, `data/disposable-email-domains.txt`) rejected on registration; (4) email verification required **before quota/credits activate** — never grant on signup alone; (5) progressive quota unlock (**30% immediate, 70% after 24h delay**) — defeats bot-farm automation; (6) client-side FingerprintJS open-source on registration, hash stored server-side. PLUS **per-tenant API rate limiting** (key by `tenant_id`, NOT user/IP; default limits in `plan_features` table; applied at middleware before business logic) — required to prevent noisy-neighbor.

**Why now:** each is irreversible at the schema/auth level — retrofit = rewrite. Abuse columns + rate-limit middleware in particular are launch-blocking; bolting them on after launch means rewriting registration and a quota-audit migration.

#### 5. Integrations / Ecosystem

**Force:** table-stakes integrations (the tool your data already lives in) vs the one integration that is a *distribution wedge*.

**Default:** ship the wedge integration first; it doubles as a channel (marketplace listing).

**Why now:** for B2B the data lives elsewhere — no integration = no adoption. Affects scope + channel.

#### 6. Data Import / Migration

**Force:** can a new user bring existing data in on day 1?

**Default:** automated importer for the top source; CSV fallback. Export already covered (GDPR/KVKK).

**Why now:** import is the #1 conversion lever and a switching-cost moat. Missing = empty-state churn.

#### 7. Pricing & Packaging

**Force:** pricing axis (seat/usage/flat/hybrid), 2-3 tiers + gating matrix, trial type, **expansion path** (what triggers upgrade), annual discount.

**Default:** B2B $50-500/mo band; hard-quota free tier or card-required trial; annual = 2 months free.

**Why now:** packaging shapes the data model *and* the funnel; can't market an undesigned price.

#### 8. Distribution & GTM Motion

**Force the motion first:** PLG / sales-led / hybrid. Then force **ONE primary channel.**

**Default:** **PLG + content/programmatic SEO** — compounding, set-and-forget, leverages your AI tooling + scraping + domain depth. Outbound/paid social (LinkedIn for B2B) + retargeting = post-PMF only; high manual load or cash burn, deprioritize pre-PMF.

**SaaS marketplaces / directories:** Shopify App Store, Chrome Web Store, Zapier, Slack, AWS Marketplace, AppExchange — pick the one your ICP lives in; built-in buyers with purchase intent. **Review / discovery sites:** G2, Capterra, Product Hunt — credibility + inbound. **Reseller / white-label:** scale-phase only.

**Affiliate / partner program** (recruit partners to sell your SaaS): platform (Rewardful / Tolt / FirstPromoter / PartnerStack), commission model (recurring vs one-time %), cookie window, attribution, payout, program terms, self-referral/fraud guard. **Default:** not a launch channel — affiliates only promote a funnel that already converts. Wire as a scale-phase channel once PMF + paid conversion are proven. **Design-for-now, activate-later:** the data model must allow a `referral_source` from day 1 — attribution can't be retrofitted onto signups that already happened. Everything else (platform, payouts) is a scale-phase switch you flip after conversion is proven.

**Why now:** "no channel decision" is the #1 SaaS killer and your stated weak point.

#### 9. Marketing Engine

**Force:** content/SEO **+ GEO/AI-answer optimization** (mandatory pairing; never SEO alone) topic clusters + cadence (your unfair advantage — AI-assisted, vertical, scraped); video/YouTube as a content channel (repurpose written content, embed on-page); community/owned-space as a channel (Discord, Slack group, or forum — retention + feedback loop); lifecycle email sequences (onboarding/nurture/dunning/win-back/expansion); social proof (Rebul case study, reviews, PH launch); one growth loop (invite/content/integration); launch plan.

**Default:** Ocoron Design System + "Engineer Who Ships" voice (Rebul never co-branded); lifecycle fully automated.

**Why now:** a growth loop and content moat are designed at intake or absent forever.

#### 10. Onboarding, Retention & Support

**Force:** time-to-activation target, fully self-serve onboarding, low-touch support model (docs + in-app + email), churn-prevention triggers, NRR target.

**Default:** automate onboarding end-to-end; human only for high-value accounts; churn-cause logged from commit #1.

**Why now:** retention kills SaaS faster than slow growth; support must stay near-zero per your hour budget.

#### 11. Full-Funnel Analytics (AARRR)

**Force:** instrument Acquisition-source, Activation, Retention-cohorts, Revenue (MRR/churn), Referral, with attribution.

**Default:** product + business events to Prometheus/dashboard; UTM/source captured at signup.

**Why now:** can't optimize an untagged channel or fix uncohorted churn.

#### 12. Reliability & Status

Reference `.windsurf/rules/saas/88-saas-launch-checklist.md` § Observability Baseline. ⚠️ **There is no `§ Reliability` section in 88** — and Observability Baseline is **Phase 2, not Phase 1**, carrying only a synthetic health probe + Gatus + 3-failure Apprise alerting. **No SLA, no RPO/RTO, no Backrest content exists there** — the items below are intake decisions this pack owns, not launch-checklist mandates. At intake, force:

**Force:** SLA commitment? public status page (Gatus)? incident comms? DR target (RPO/RTO).

**Default:** public Gatus status page; `/health`+`/metrics` mandatory; Backrest backups with stated RPO.

**Why now:** B2B buyers check the trust/status page before paying; observability is pro-grade table-stakes.

#### 13. Legal, Compliance & Trust

Reference `.windsurf/rules/saas/88-saas-launch-checklist.md` § Legal Pages (Payment Processors Check These). At intake, force:

**Force:** ToS, privacy, KVKK/GDPR, DPA + subprocessor list, data residency, security posture. Affiliate-program terms + payout tax handling + self-referral policy (if a program is planned).

**Default:** Paddle handles tax/invoicing; you own data terms; Teknokent KDV 0% on Rebul billing.

**Why now:** missing trust artifacts block enterprise deals and create legal exposure.

#### 14. Finance & Unit Economics

**Force:** CAC target, LTV, payback <12mo, LTV:CAC >=3, **COGS per tenant** (single-VPS cost = margin + capacity ceiling), MRR milestones toward the $30k+/mo goal. Blended CAC including affiliate commissions; recurring-commission drag on LTV.

**Default:** price above per-tenant COGS with margin; know the tenant count where VPS1 saturates.

**Why now:** COGS-per-tenant on one box is a hard ceiling; underprice it and scale = loss.

#### 15. Risk Register

**Force:** top 5 concentration risks + mitigation — Paddle / shared postgres-main / single-VPS / single-channel / key-person.

**Default:** named owner-actions per risk; revisit at each epic.

**Why now:** this is where the Forex pattern hides (infra before revenue, betting past disproof).

#### 16. Ops & Solo-Dev Load

**Force:** what is fully automated (onboarding, billing, dunning, provisioning, alerting) vs needs you; max weekly maintenance hours; incident path.

**Default:** anything recurring-manual gets automated or cut; set-and-forget bias; managed services over self-hosted.

**Why now:** your sustainability *is* the product's survival — manual ops scale to burnout, not revenue.

#### 17. Sequencing & Kill Criteria

**Force:** pre-sell gate (>=5 paying commitments before full build), v1 = one workflow, explicit kill/pivot criteria **with a date**.

**Default:** ship the wedge, validate, then expand.

**Why now:** the only structural defense against the Forex pattern — building past the point of disproof.

#### Vision Summary Gate

Vision Summary may confirm only when **all 17 are resolved or logged as Open Questions**. Map intake outputs onward:

- Decisions to `Technology Decisions` + `Value Streams` sections.
- Unresolved to `Open Questions` (block confirmation).
- Scaffold signal: `saas-skeleton` (portal) + `python-api` (backend) = multi-epic, route to `02-epic-decomposition-command`.

### 1B. Epic Decomposition Directives

When decomposing a SaaS vision into epics, these dimensions shape boundaries:

#### Mandatory Epic Coverage

Every SaaS mega-epic MUST have dedicated coverage for:

| Dimension | Epic boundary rule |
| --- | --- |
| §4 Tenancy + Auth + Org model | Foundation epic (Epic 1) — schema, RLS, auth, org/invite. Everything else depends on this. |
| §4 Billing + Gating | Own epic or explicitly assigned. Plan-to-feature matrix must exist before feature epics start. |
| §5 Wedge integration | Own epic if complex; otherwise bundled with the core workflow epic. |
| §6 Data import | Belongs in the epic that owns the data model it imports into. |
| §9 Marketing engine | Separate epic if content/SEO site involved (docusaurus/static-site scaffold). Otherwise bundled with onboarding epic. |
| §10 Onboarding | Belongs in the epic that owns signup flow. Never deferred past v1. |
| §11 Analytics | Instrumentation belongs in each epic's tickets (not a separate epic). AARRR dashboard is its own ticket in the closure epic. |

#### Parallel Lane Opportunities

SaaS projects naturally split into these parallel lanes after the foundation epic:

- **Core workflow** (the painful workflow you're solving) — independent of billing
- **Billing + subscription** — independent of core workflow after schema exists
- **Integrations** — independent after API contracts exist
- **Marketing site / content** — fully independent (different scaffold)
- **Admin dashboard** — independent after tenant model exists

#### Anti-Patterns

- Do NOT create a "frontend epic" and "backend epic" — split by domain, not layer.
- Do NOT defer billing to "later" — gating matrix shapes the data model.
- Do NOT merge onboarding into a generic "UI epic" — activation path is its own concern.
- Do NOT skip the analytics dimension — "we'll add tracking later" = never.

#### Phase Mapping

Reference `.windsurf/rules/saas/88-saas-launch-checklist.md` phases:

- **Phase 1 (blocks go-live):** must be covered by epics before launch.
- **Phase 2 (first 30 days):** can be a dedicated post-launch epic.
- **Phase 3 (scale):** deferred epic or out of scope for v1.

---
