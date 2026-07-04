<!-- SaaS Domain Module — loaded by mega-epic-breakdown commands
     when Vision Summary scaffold types include `saas-skeleton`:
       • 02-epic-decomposition-command — drives SaaS-specific epic patterns
         (tenant + auth foundation, billing + gating, marketing site, etc.).
       • 00-trigger-workflow-command Step E4 (EXISTING mode) — drives delta
         decisions when adding a SaaS capability (e.g., billing) to an
         existing project.
     Traycer reads this file from disk based on the Vision Summary's
     Technology Decisions § Scaffold types — no manual paste needed.
     Consumer: Traycer planning LLM (NOT coding agents).
     Coding agents use .windsurf/rules/saas/88-saas-launch-checklist.md,
     saas/95-multi-tenant-saas.md, saas/60-saas-ui.md instead. -->

# SaaS Domain Module (17 dimensions)

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
- **Billing+gating:** plan-to-feature gating matrix exists *before* features. **Provider picked by target market** per `.windsurf/rules/core/85-payments-billing.md` § Payment Providers: **Paddle Billing v2 (MoR)** for international, **iyzico** for Turkish domestic, **both** when serving both markets (BIN-based card routing). Stripe is unavailable to a Turkey-resident entity — do NOT plan around it.
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

Reference `.windsurf/rules/saas/88-saas-launch-checklist.md` § Reliability. At intake, force:

**Force:** SLA commitment? public status page (Gatus)? incident comms? DR target (RPO/RTO).

**Default:** public Gatus status page; `/health`+`/metrics` mandatory; Backrest backups with stated RPO.

**Why now:** B2B buyers check the trust/status page before paying; observability is pro-grade table-stakes.

#### 13. Legal, Compliance & Trust

Reference `.windsurf/rules/saas/88-saas-launch-checklist.md` § Legal. At intake, force:

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

## Part 2 — Per-Epic Implementation Guidance

*Reserved for future per-epic loading by `epic-to-ticket-workflow` command files (`01-epic-brief`, `02-core-flows`, `03-tech-plan`, `04-deploy-plan`, `05-ticket-outline`, `06-ticket-breakdown`). Not currently auto-wired — those command files do not yet `read domain-modules/saas.md`. Surfaced here so the patterns are co-located with Part 1; load order can be wired later.*

These directives apply throughout all epic-to-ticket-workflow steps when the epic belongs to a SaaS project. Traycer carries them from epic-brief through ticket-breakdown and into execution plans.

### 2A. Epic Brief (epic-to-ticket-workflow/01)

When creating the epic brief for a SaaS epic:

- State which of the 17 dimensions this epic addresses (by number).
- Carry forward the resolved decisions from the Vision Summary — do not re-decide.
- If this epic is the foundation epic (§4), the brief must include: tenancy model, auth provider, org/role model, billing provider, gating matrix shape. These are not "tech plan" decisions — they are epic-level constraints inherited from the mega-epic Vision Summary.
- If this epic touches billing (§4/§7), the brief must include: pricing tiers, gating matrix, trial type, expansion triggers. The coding agent cannot design billing — it implements a decided design.
- Success Criteria must include at least one criterion per dimension this epic addresses.

### 2B. Core Flows (epic-to-ticket-workflow/02)

When mapping core flows for a SaaS epic, include these SaaS-specific flows if the epic touches them:

- **Signup-to-activation flow:** signup, email verification, org creation, onboarding wizard, activation event. Map the exact click path. Name the activation event.
- **Billing lifecycle flow:** plan selection, payment, subscription active, upgrade/downgrade, cancellation, dunning (failed payment), win-back. Reference Paddle webhook events.
- **Tenant management flow:** invite team member, assign role, remove member, transfer ownership, tenant settings.
- **Data import flow:** select source, map fields, preview, confirm, progress, completion/rollback.
- **Integration setup flow:** connect external service, authorize (OAuth/API key), configure sync, test connection, disconnect.

Each flow must identify the `[PRIMARY PATH]` — the happy path a new user takes. These become integration test targets.

**Page inventory:** `.windsurf/rules/saas/60-saas-ui.md` § Page Inventory lists the 20 mandatory pages every SaaS ships (one — `[Core feature pages]` — is a project-specific placeholder). Core-flows must map to these pages + derive any project-specific pages not in the inventory.

### 2C. Tech Plan (epic-to-ticket-workflow/03)

When creating the tech plan for a SaaS epic, enforce:

- **Multi-tenancy architecture:** `tenant_id` on every tenant-scoped table. RLS policies per table. Tenant context propagation (middleware sets `current_tenant_id()`). Reference `.windsurf/rules/saas/95-multi-tenant-saas.md` for full patterns.
- **Billing integration:** Paddle webhook endpoint, subscription state machine, plan-to-feature gating middleware, metering counters (Redis + postgres reconciliation). BIN-based card routing if dual-processor (reference `.windsurf/rules/saas/88-saas-launch-checklist.md` § Payment Routing).
- **Org/role model:** organizations table, memberships table (user + org + role), invite flow, role-based access control middleware.
- **Audit logging:** every tenant-data mutation writes to audit log (who, what, when, tenant_id). Soft-delete default on tenant-scoped tables.
- **Analytics instrumentation:** product events to structured log (activation, feature usage, conversion). UTM/source capture at signup. AARRR stage tags on each event.
- **Data isolation:** tenant-scoped queries enforced at the ORM/repository layer (not just RLS). Cross-tenant data access = security incident.

### 2D. Ticket Outline (epic-to-ticket-workflow/05)

When creating the ticket outline for a SaaS epic, verify coverage:

- If this epic owns auth/tenancy: tickets for schema + RLS + middleware + org model + invite flow + activation event.
- If this epic owns billing: tickets for Paddle integration + webhook handler + gating middleware + metering + subscription UI.
- If this epic owns onboarding: tickets for signup flow + onboarding wizard + activation tracking + churn-cause logging.
- If this epic owns data import: tickets for importer + field mapping + preview + progress + rollback.
- If this epic owns integrations: tickets for OAuth/API key flow + sync config + webhook receiver + marketplace listing prep.
- Every ticket that touches tenant data must have `95-multi-tenant-saas.md` in its Rule Packs.
- Analytics instrumentation is NOT a separate ticket — it belongs inside each feature ticket as an AC.
- The closure ticket must include AARRR dashboard verification.

### 2E. Ticket Breakdown (epic-to-ticket-workflow/06)

When Traycer creates full ticket specs and agent execution plans for a SaaS epic:

#### Per-Ticket Injection Rules

For every ticket, check which dimensions apply and inject into Acceptance Criteria and Context Files:

| If ticket touches... | Inject |
| --- | --- |
| Database schema | `tenant_id` on every tenant-scoped table; RLS policy; reference `95-multi-tenant-saas.md` |
| Auth / signup / registration | `fastapi-user-auth` (Pattern A) config; org/role/invite model; activation event instrumentation; **abuse-prevention Phase 1 (LAUNCH-BLOCKING)** — `registration_ip` + `registration_fingerprint` columns, IP rate limit (2/IP/24h), disposable-email blocklist, email verification before quota grant, progressive unlock (30% / 70% @ 24h), FingerprintJS open-source. Reference `87-abuse-detection.md` |
| Any API endpoint | Tenant-scoped queries only (never cross-tenant); correlation IDs; **per-tenant** rate limiting (key by `tenant_id`, NOT user/IP; default limits in `plan_features`) |
| Billing / subscription | Plan-to-feature gating check; Paddle webhook handler; BIN-based card routing (reference `88-saas-launch-checklist.md`) |
| Usage metering | Redis counter + postgres-main reconciliation; never bill off Redis alone |
| User-facing UI | 5 UI states; i18n (en + tr); Ocoron Design System; reference `60-saas-ui.md` |
| Onboarding flow | Time-to-activation target in AC; self-serve end-to-end; churn-cause logging |
| Data import | Importer for top source + CSV fallback; progress feedback; rollback on failure |
| Analytics event | UTM/source capture; AARRR stage tag; Prometheus metric or structured log event |
| Integration endpoint | Webhook signature verification; idempotency key; retry/backoff; marketplace listing prep |
| Settings / admin | Per-tenant config isolation; soft-delete; audit log entry; export endpoint |
| Legal / compliance | ToS acceptance gate; KVKK/GDPR consent capture; data deletion endpoint |
| Email / push / notification template | MJML + Jinja2 pipeline; Ocoron brand partial; Resend ESP; reference `core/86-email-templates.md` |

#### Agent Context Files

Every SaaS ticket's Context Files section must include (in addition to category-specific rule packs):

```text
.windsurf/rules/saas/95-multi-tenant-saas.md    — tenant isolation patterns
.windsurf/rules/saas/88-saas-launch-checklist.md — launch-blocking checks
.windsurf/rules/saas/60-saas-ui.md              — UI patterns (if frontend ticket)
.windsurf/rules/saas/87-abuse-detection.md      — 4-layer anti-abuse playbook (if ticket touches registration, auth, signup, or quota)
.windsurf/rules/core/85-payments-billing.md     — Paddle/iyzico provider rules (if billing ticket)
.windsurf/rules/core/86-email-templates.md      — email/push/notification templates (if ticket creates or edits templates)
```

#### Plan Directives for Coding Agents

When Traycer creates the execution plan (the plan the coding agent follows), embed these constraints:

1. **Every query is tenant-scoped.** No `SELECT * FROM table` without `WHERE tenant_id = current_tenant()`. RLS is the safety net, not the primary filter.
2. **Every mutation is audited.** `INSERT`/`UPDATE`/`DELETE` on tenant data writes to the audit log.
3. **Every feature checks the gating matrix.** Before exposing functionality, check `plan.features[feature_key]`. No ungated features in paid tiers.
4. **Every external call has resilience.** Timeout + retry + circuit-breaker + graceful fallback. Reference `.windsurf/rules/core/58-resilience.md`.
5. **Every user-facing string is in locale files.** No hardcoded text. `en.json` + `tr.json` minimum.
6. **Every signup captures attribution.** UTM params, referral source, activation timestamp.
