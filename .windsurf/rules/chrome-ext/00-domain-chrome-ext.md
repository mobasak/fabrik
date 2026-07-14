---
activation: manual
description: Chrome-extension domain — PLANNING layer. Vision-intake dimensions (ICP, the permission-ceiling fork, monetization with ZERO platform tax, browser scope, platform-dependency risk, kill criteria) + epic-decomposition directives. Business formation, not code discipline — 70-chrome-ext.md owns every code-time fact.
trigger: manual
---
<!-- CONSUMER: the mega-epic planner (vision intake + epic decomposition). Loaded BY PATH from
     docs/traycer/mega-epic-breakdown/00-trigger-*.md and 02-epic-decomposition-*.md.
     ⚠️ NOT glob-activated ON PURPOSE — "who is the ICP?" and "what is the kill criteria?" are vision-intake
        questions, not something to inject into an agent mid-edit in a content script.
     ⚠️ THE ONE RULE: this file FORCES A DECISION; it NEVER states an implementation. No value (listing-asset
        sizes, permission names, manifest keys, bundle budgets, review times) may be copied in from
        70-chrome-ext.md — a second copy drifts, and that is exactly why docs/traycer/**/domain-modules/ was
        deleted 2026-07-13. Cite 70; never restate it. -->

# Chrome Extension Domain — Planning Layer (vision intake + epic decomposition)

## Completeness Test (apply per dimension)

A dimension belongs at intake **only if** getting it wrong is **irreversible** or **kills the product before build**. Everything else is downstream. Resolve each or log as an Open Question. **No "TBD" survives confirmation.**

---

## The 3 Forks (do NOT inherit SaaS or mobile defaults here)

**1. Monetization is the INVERSE of mobile — there is no store billing at all, and no platform tax.**
Google **shut down Chrome Web Store Payments on 1 Feb 2021**; paid extensions, in-store IAP and CWS free trials no longer exist. An extension therefore **cannot** bill through its store — external billing is not a choice, it is the only path. The upside is large and easy to miss: **the store takes 0%.** You keep 100% of revenue minus your payment processor's fee — where a mobile app would surrender a double-digit cut off the top. **Do not plan an extension's economics off mobile's assumptions, and never wait for a store-billing feature that is not coming back.**
→ Provider choice is owned by `core/85-payments-billing.md`; card routing by `saas/88-saas-launch-checklist.md` § Payment Routing.
→ **The paywall lives in the BACKEND, never in the client.** A client-side entitlement check in an extension is trivially bypassed — the browser hands the user your source. Gate on the server, per `core/35-security-auth.md`.

**2. The distribution channel sets a PERMISSION CEILING, and that ceiling constrains the PRODUCT.**
This is not a launch detail — it is a product decision made at intake. The Chrome Web Store rejects broad host access and `debugger`-class permissions; developer-mode install accepts anything. So **an extension whose core value requires a permission the store won't approve cannot be a store product at all** — its audience is capped at users willing to install unpacked, or an enterprise fleet. Decide the channel **before** you scope the feature, or you will build a product you cannot ship to the audience you costed.
→ Channels, their exact costs, permission ceilings, listing assets and auto-update behaviour are owned by **`70-chrome-ext.md` § Distribution Model**. Read them there; do not restate them here.

**3. Platform dependency is existential — and there is no appeal you control.**
Google can reject, delist, or remove the extension, and a store rejection can invalidate the whole distribution assumption *after* the build. Treat this as a top-line risk with a named fallback channel (§8), not a footnote.

---

## Vision Intake Dimensions

### 1. Market & Positioning

**Force:** named ICP · the one painful in-browser workflow · 3–5 named competitors (search the store — competitors are *visible* here in a way they are not in SaaS) · one-sentence moat.
**Default:** a wedge into a workflow the user already performs in the browser. Moat = the backend and its data, **never the extension UI** — the UI is trivially cloned; anyone can unpack your extension and read it.
**Why now:** positioning drives permissions, channel, and pricing. Wrong here = incoherent everywhere.

### 2. Monetization Model

**Force:** free / freemium / paid / license-key-for-teams · where the paywall sits · what the free tier may do.
**Default:** freemium with a **backend-enforced** entitlement. Zero platform tax means pricing has more room than mobile — but the processor fee and your infra COGS are still real.
**Why now:** the entitlement check shapes the auth model and the backend schema (Epic 1). Retrofitting a paywall onto an extension that shipped with no user identity is a rewrite.

### 3. Distribution Channel + Permission Ceiling

**Force:** which channel (see Fork 2), and — the actual question — **does the product's core value survive that channel's permission ceiling?**
**Default:** Chrome Web Store for anything consumer. If the core feature needs a permission the store rejects, that is a **product** decision to escalate at intake, not a packaging problem to solve at launch.
**Why now:** the ceiling constrains the feature set. Discovering it at submission means rebuilding or re-audiencing.

### 4. Browser Scope

**Force:** Chrome-only, or Chrome + Firefox/Edge?
**Default:** build Chrome-first but keep the toolchain cross-browser-capable (the pack's default build tool already is — see `70` § Build Tooling). Ship other browsers only when a real audience is proven.
**Why now:** cross-browser is cheap if assumed from commit #1 and expensive as a retrofit; but shipping to empty stores is waste. Decide, don't drift.

### 5. Backend Dependency

**Force:** what the backend must own — auth, entitlement, AI/LLM calls, any API key.
**Default:** **the backend is always Epic 1.** The extension is useless without it, and every secret must live there: an extension bundle is **readable by anyone who installs it**, so an API key shipped in the client is a published API key.
**Why now:** it is the dependency root of every other epic.

### 6. Onboarding & Activation

**Force:** the activation event (the one action that means "got value") · what the user must grant/configure before it can happen · time-to-activation target.
**Default:** activation must be reachable **without** a settings trip. Instrument it from commit #1.
**Why now:** extensions are uninstalled in minutes. An extension that needs configuration before its first win is an extension that gets removed.

### 7. Unit Economics

**Force:** price · **zero store cut** (bank it — see Fork 1) · processor fee · backend COGS per active user (LLM calls dominate if the product is AI-shaped) · CAC · payback.
**Default:** price above per-user COGS with margin. If the extension makes an LLM call per user action, model that cost **per DAU**, not per install — installs are cheap, active users are not.
**Why now:** an AI-shaped extension with a generous free tier is a metered cost with no ceiling.

### 8. Risk Register

**Force:** top risks + a named mitigation each — **store rejection/delisting** (what is the fallback channel?) · a Chrome API deprecation breaking the extension · single-channel dependency · key-person.
**Default:** a named fallback distribution channel **before** launch, not after a rejection.
**Why now:** the platform can remove you, and a rejection *after* build invalidates the distribution assumption you costed the business on.

### 9. GTM

**Force:** ONE primary channel — store search/SEO (the listing is the funnel) · content/SEO to a landing page · community · Product Hunt.
**Default:** store listing SEO + a landing page. The store is a search engine; the listing copy is the acquisition surface, not decoration.
**Why now:** "no channel decision" kills extensions the same way it kills SaaS.

### 10. Sequencing & Kill Criteria

**Force:** v1 = one workflow · explicit kill/pivot criteria **with a date** · what evidence would prove this is not worth building.
**Default:** ship the wedge to the narrowest real audience, validate, then expand.
**Why now:** the only structural defense against building past the point of disproof.

### Vision Summary Gate

Confirm the Vision Summary **only when every dimension above is resolved or logged as an Open Question.** Decisions → `Technology Decisions` + `Value Streams`. Unresolved → `Open Questions` (blocks confirmation). Scaffold signal: `chrome-extension` (client) **+** `python-api` (backend) = multi-epic.

---

## Epic Decomposition Directives

### Mandatory Epic Coverage

| Dimension | Epic boundary rule |
|---|---|
| §5 Backend + Auth | **Foundation epic (Epic 1) — ALWAYS FIRST.** FastAPI + auth + entitlement + shape/registrars/health. The extension is useless without it, and every secret lives here. |
| §2 Monetization | Own epic, or explicitly assigned. **Backend-enforced entitlement must exist before any paywalled feature** — a client-side gate is not a gate. |
| §3 Distribution + permissions | **Not a "polish" epic.** The permission strategy is designed in Epic 1–2 (the ceiling constrains the feature set); the listing/packaging work is its own epic. |
| §6 Onboarding | Belongs to the epic that owns the first-run surface. **Never deferred past v1** — extensions get uninstalled in minutes. |
| §7 Analytics | Instrumentation rides in each epic's tickets, not a separate epic. |

### Parallel Lane Opportunities

After the backend epic: **extension core** (surfaces + messaging) · **monetization/paywall** (independent once auth exists) · **landing page + store listing** (fully independent — different scaffold) · **AI/extraction pipeline** (independent behind the API contract).

### Anti-Patterns

- Do **NOT** build the extension before its backend — it is the dependency root, not a "nice to have later."
- Do **NOT** gate a paid feature client-side. The user can read your bundle.
- Do **NOT** defer the permission decision to submission — it constrains the product, not the packaging.
- Do **NOT** plan store billing or in-store IAP. **It does not exist** (Fork 1). Anyone who says otherwise is quoting pre-2021 documentation.
- Do **NOT** treat store rejection as an edge case with no fallback channel.

### Code-time facts live in `70-chrome-ext.md`

Surfaces, MV3 constraints, permissions discipline, state management, auth storage, framework/build tooling, bundle budgets, testing, i18n, the design system, banned patterns, and the full **§ Distribution Model** (channel costs, listing assets, permission ceilings, auto-update, what Chrome blocks) are **owned by `70-chrome-ext.md`**. Cite it; never restate it here.
