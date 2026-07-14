---
activation: manual
description: SaaS domain — PLANNING layer. Vision-intake dimensions (ICP, moat, pricing axis, GTM, COGS-per-tenant vs the single-VPS ceiling, risk register, dated kill criteria) + epic-decomposition directives. Business formation, not code discipline — 60/85/87/88/95 own every code-time fact.
trigger: manual
---
<!-- ⚠️ NOT glob-activated ON PURPOSE. Its questions ("who is the ICP?", "what is the kill criteria?")
     belong at VISION INTAKE, not to an agent mid-edit in billing code. Its real consumers load it BY PATH:
     docs/traycer/mega-epic-breakdown/00-trigger-*.md and 02-epic-decomposition-*.md. A glob on
     **/billing/** would inject 187 lines of business-formation questions into every coding session that
     touches a billing file — noise at exactly the wrong moment. Do not re-add one. -->

<!-- CONSUMER: the mega-epic planner (vision intake + epic decomposition), and any agent scoping SaaS work.
     GOAL: settle the IRREVERSIBLE, business-shaping decisions BEFORE epics exist.
     ⚠️ THE ONE RULE: this file FORCES A DECISION; it NEVER states an implementation. Zero values
        (thresholds, column names, provider configs, page routes) may be copied in from a pack — a second
        copy drifts, and that is exactly why docs/traycer/**/domain-modules/ was deleted 2026-07-13.
        Cite the pack; never restate it. Every line here must be a question no pack answers.
     OWNERS of the code-time facts: 95-multi-tenant-saas (tenancy/RLS/metering) · 35-security-auth (auth)
        · 85-payments-billing (providers) · 88-saas-launch-checklist (payment routing, legal pages,
        launch phases) · 87-abuse-detection (free-tier gating) · 60-saas-ui (UI). -->

# SaaS Domain — Planning Layer (vision intake + epic decomposition)

## Operating Lens (solo + AI fleet)

- **Build cost is cheap** — agents implement. Scope-heavy is fine *if* it stays low-maintenance.
- **Your time is the scarce resource** — optimize every default for **set-and-forget ops**, not minimal scope.
- **Pro-grade is non-negotiable** — automate to remove yourself, never to cut quality.

## Completeness Test (apply per dimension)

A dimension belongs at intake **only if** getting it wrong is **irreversible** or **kills the business before build**. Everything else is downstream (`02`/`05`). Resolve each or log as an Open Question. **No "TBD" survives confirmation.**

---

## 1A. Vision Intake Dimensions

*Consumed by `02-epic-decomposition-command` and `00-trigger-workflow-command` Step E4 (EXISTING mode).*

### 1. Market & Positioning

**Force:** named ICP · the one painful workflow · 3–5 named competitors · positioning statement (`For [ICP] who [pain], X is a [category] that [benefit], unlike [alt]`) · one-sentence moat.
**Default:** vertical wedge with unfair depth. Moat = domain depth + proprietary data, **never features**.
**Why now:** positioning drives every word of pricing, marketing, onboarding. Wrong here = incoherent everywhere.

### 2. Geographic Market

**Force:** Turkey-first vs international-first — sets language, currency, compliance, channel.
**Default:** build **international-grade (en-first), anchor in TR**.
**Why now:** retrofitting i18n, currency, and EN content onto a TR-only product is a rebuild.

### 3. B2B Buying Process

**Force:** economic buyer vs champion vs end-user · security-review/procurement friction · sales-cycle length.
**Default:** target a buyer who is also the user (PLG-compatible). Procurement-heavy ⇒ PLG breaks ⇒ reconsider.
**Why now:** the buying committee decides whether self-serve works at all — i.e. whether you stay low-maintenance.

### 4. Product & Architecture (the irreversibles)

⚠️ **Decisions only.** Each row is a question intake must answer; the pack owns the answer. Do **not** copy values back into this file.

| Force at intake | Default | Pack that OWNS the implementation |
|---|---|---|
| **Tenancy** — shared-DB + `tenant_id` + RLS, or DB-per-tenant? | shared `postgres-main` + RLS. DB-per-tenant **only** if contractually required. | `saas/95-multi-tenant-saas.md` |
| **Identity/org** — auth pattern + org/role/invite model | **Pattern A** (app issues its own JWTs). Authelia is back-office only. | `core/35-security-auth.md` |
| **Billing + gating** — which provider(s)? does a plan→feature matrix exist *before* features? | Picked **by target market**. Stripe is unavailable to a Turkey-resident entity — do NOT plan around it. | providers → `core/85-payments-billing.md` · **card routing → `saas/88-saas-launch-checklist.md` § Payment Routing** (⚠️ routing is in **88**, not 85) |
| **Metering** — what counts as billing-grade truth? | Redis counters **reconciled to Postgres**. Never bill off Redis alone. | `saas/95-multi-tenant-saas.md` |
| **Isolation + audit** — one enforcement point; audit log, soft-delete, per-tenant export | enforced in exactly one place | `saas/95-multi-tenant-saas.md` |
| **Activation event** — the one action that means "got value" | instrumented from commit #1 | *intake-owned; no pack* |
| **Abuse prevention** — free-tier gating. **LAUNCH-BLOCKING.** | Adopt the pack's Phase-1 layers **in full**; they are non-negotiable at launch. Plus per-tenant (not per-user/IP) API rate limiting. | **`saas/87-abuse-detection.md`** · launch gate → `saas/88` § Abuse Prevention |

**Why now:** each is irreversible at the schema/auth level — retrofit = rewrite. Abuse columns and rate-limit middleware especially: bolting them on post-launch means rewriting registration *and* migrating a quota audit over real users.

### 5. Integrations / Ecosystem

**Force:** table-stakes integrations (where your data already lives) vs the one integration that is a *distribution wedge*.
**Default:** ship the wedge integration first — it doubles as a channel (marketplace listing).
**Why now:** in B2B the data lives elsewhere. No integration = no adoption. Affects scope *and* channel.

### 6. Data Import / Migration

**Force:** can a new user bring existing data in on day 1?
**Default:** automated importer for the top source; CSV fallback.
**Why now:** import is the #1 conversion lever and a switching-cost moat. Missing = empty-state churn.

### 7. Pricing & Packaging

**Force:** pricing axis (seat/usage/flat/hybrid) · 2–3 tiers + gating matrix · trial type · **expansion path** (what triggers the upgrade) · annual discount.
**Default:** B2B $50–500/mo band; hard-quota free tier or card-required trial; annual = 2 months free.
**Why now:** packaging shapes the data model *and* the funnel. You cannot market an undesigned price.

### 8. Distribution & GTM Motion

**Force the motion first:** PLG / sales-led / hybrid. Then force **ONE primary channel**.
**Default:** **PLG + content/programmatic SEO** — compounding, set-and-forget, leverages AI tooling + domain depth. Outbound/paid = post-PMF only (high manual load or cash burn).
**Channels to pick from:** marketplaces where the ICP already is (Shopify, Chrome Web Store, Zapier, Slack, AWS, AppExchange) · review/discovery sites (G2, Capterra, Product Hunt) · reseller/white-label (scale-phase only).
**Affiliate/partner program:** **not a launch channel** — affiliates only promote a funnel that already converts. **But design-for-now, activate-later:** the data model must carry a `referral_source` from day 1; attribution cannot be retrofitted onto signups that already happened. Platform/commission/payout are scale-phase switches.
**Why now:** "no channel decision" is the #1 SaaS killer.

### 9. Marketing Engine

**Force:** content/SEO **+ GEO/AI-answer optimization** (mandatory pairing — never SEO alone) · topic clusters + cadence · video as a repurposing channel · community/owned space · lifecycle email (onboarding/nurture/dunning/win-back/expansion) · social proof · **one** growth loop (invite/content/integration) · launch plan.
**Default:** lifecycle fully automated.
**Why now:** a growth loop and a content moat are designed at intake or absent forever.

### 10. Onboarding, Retention & Support

**Force:** time-to-activation target · fully self-serve onboarding · low-touch support model · churn-prevention triggers · NRR target.
**Default:** automate onboarding end-to-end; human only for high-value accounts; churn-cause logged from commit #1.
**Why now:** retention kills SaaS faster than slow growth, and support must stay near-zero against your hour budget.

### 11. Full-Funnel Analytics (AARRR)

**Force:** instrument Acquisition-source · Activation · Retention-cohorts · Revenue (MRR/churn) · Referral — with attribution.
**Default:** product + business events to Prometheus/dashboard; UTM/source captured at signup.
**Why now:** you cannot optimize an untagged channel or fix uncohorted churn.

### 12. Reliability & Status

> Intake-owned — **no pack covers this.** `88 § Observability Baseline` is Phase 2 and carries only a synthetic probe + Gatus + alerting: **no SLA, no RPO/RTO, no backup target.**

**Force:** SLA commitment? · public status page? · incident comms? · **DR target (RPO/RTO)**.
**Default:** public Gatus status page; `/health` + `/metrics` mandatory; Backrest backups with a **stated** RPO.
**Why now:** B2B buyers check the status/trust page before paying. An unstated RPO is an unbounded loss.

### 13. Legal, Compliance & Trust

> The pages themselves — ToS, privacy, KVKK/GDPR, DPA, their routes and required content — are **fully owned by `saas/88-saas-launch-checklist.md` § Legal Pages**. Ship them from there; do not re-derive.

**Force (the part 88 does NOT decide):** data residency · subprocessor list · security posture you will publicly claim · affiliate-program terms + payout tax handling + self-referral policy (if a program is planned).
**Why now:** missing trust artifacts block enterprise deals and create legal exposure.

### 14. Finance & Unit Economics

**Force:** CAC target · LTV · payback <12mo · LTV:CAC ≥3 · **COGS per tenant** (single-VPS cost = margin **and** capacity ceiling) · MRR milestones. Blended CAC including affiliate commissions; recurring-commission drag on LTV.
**Default:** price above per-tenant COGS with margin; **know the tenant count at which the VPS saturates**.
**Why now:** COGS-per-tenant on one box is a hard ceiling. Underprice it and scale = loss.

### 15. Risk Register

**Force:** top 5 concentration risks + mitigation — payment provider · shared `postgres-main` · single-VPS · single-channel · key-person.
**Default:** a named owner-action per risk; revisit at every epic.
**Why now:** this is where the *build-past-disproof* pattern hides (infra before revenue).

### 16. Ops & Solo-Dev Load

**Force:** what is fully automated (onboarding, billing, dunning, provisioning, alerting) vs what needs *you* · max weekly maintenance hours · incident path.
**Default:** anything recurring-manual gets automated or cut. Set-and-forget bias; managed over self-hosted.
**Why now:** your sustainability *is* the product's survival — manual ops scale to burnout, not revenue.

### 17. Sequencing & Kill Criteria

**Force:** pre-sell gate (≥5 paying commitments before full build) · v1 = one workflow · explicit kill/pivot criteria **with a date**.
**Default:** ship the wedge, validate, then expand.
**Why now:** the only structural defense against building past the point of disproof.

### Vision Summary Gate

Confirm the Vision Summary **only when all 17 are resolved or logged as Open Questions.** Decisions → `Technology Decisions` + `Value Streams`. Unresolved → `Open Questions` (blocks confirmation).

---

## 1B. Epic Decomposition Directives

### Mandatory Epic Coverage

Every SaaS mega-epic MUST have dedicated coverage for:

| Dimension | Epic boundary rule |
|---|---|
| §4 Tenancy + Auth + Org model | **Foundation epic (Epic 1)** — schema, RLS, auth, org/invite. Everything depends on it. |
| §4 Billing + Gating | Own epic, or explicitly assigned. The plan→feature matrix must exist **before** feature epics start. |
| §5 Wedge integration | Own epic if complex; else bundled with the core-workflow epic. |
| §6 Data import | Belongs to the epic that owns the data model it imports into. |
| §9 Marketing engine | Separate epic if a content/SEO site is involved (docusaurus/static-site scaffold); else bundled with onboarding. |
| §10 Onboarding | Belongs to the epic that owns the signup flow. **Never deferred past v1.** |
| §11 Analytics | Instrumentation rides in each epic's tickets (not a separate epic). The AARRR dashboard is one ticket in the closure epic. |

### Parallel Lane Opportunities

After the foundation epic, SaaS splits naturally into: **core workflow** (independent of billing) · **billing + subscription** (independent of core workflow once the schema exists) · **integrations** (independent once API contracts exist) · **marketing site/content** (fully independent — different scaffold) · **admin dashboard** (independent once the tenant model exists).

### Anti-Patterns

- Do **NOT** create a "frontend epic" and a "backend epic" — split by **domain**, not layer.
- Do **NOT** defer billing to "later" — the gating matrix shapes the data model.
- Do **NOT** merge onboarding into a generic "UI epic" — the activation path is its own concern.
- Do **NOT** skip analytics — "we'll add tracking later" = never.

### Phase Mapping

Map epics onto the launch phases defined in `saas/88-saas-launch-checklist.md` (**88 owns the phase contents**): Phase 1 must be covered by epics **before** launch · Phase 2 may be a dedicated post-launch epic · Phase 3 is deferred or out of scope for v1.
