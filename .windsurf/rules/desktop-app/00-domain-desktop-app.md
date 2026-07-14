---
activation: manual
description: Desktop-app domain — PLANNING layer. Vision-intake dimensions (ICP, the standalone-vs-connected fork that decides whether revenue can be gated at all, zero-intermediary economics vs the OS gatekeeper, unit economics, risk, kill criteria) + epic-decomposition directives. Business formation, not code discipline — 72-desktop.md owns every code-time fact.
trigger: manual
---
<!-- CONSUMER: the mega-epic planner (vision intake + epic decomposition). Loaded BY PATH from
     docs/traycer/mega-epic-breakdown/00-trigger-*.md and 02-epic-decomposition-*.md.
     ⚠️ NOT glob-activated ON PURPOSE — "who is the ICP?" and "what is the kill criteria?" are vision-intake
        questions, not something to inject into an agent mid-edit in main.ts.
     ⚠️ THE ONE RULE: this file FORCES A DECISION; it NEVER states an implementation. No value (signing costs,
        certificate prices, store fees, SDK names, window sizes, crypto algorithms) may be copied in from
        72-desktop.md — a second copy drifts, and that is exactly why docs/traycer/**/domain-modules/ was
        deleted 2026-07-13. Cite 72; never restate it. -->

# Desktop App Domain — Planning Layer (vision intake + epic decomposition)

## Completeness Test (apply per dimension)

A dimension belongs at intake **only if** getting it wrong is **irreversible** or **kills the product before build**. Everything else is downstream. Resolve each or log as an Open Question. **No "TBD" survives confirmation.**

---

## The 3 Forks (do NOT inherit SaaS, mobile or extension defaults here)

**1. STANDALONE vs CONNECTED decides whether you can gate revenue AT ALL. This is the Epic-1 gate.**
Every other product type in Fabrik can enforce entitlement on a server: the SaaS checks a row, the extension calls its backend, the mobile app validates a receipt. **A standalone desktop app cannot.** If it runs offline, the entitlement check runs *on the user's machine, inside a binary you handed them* — so it must be an offline-verifiable licence, and it is **crackable by definition**. That is not a bug to fix; it is the deal. Price and position accordingly.

- **Connected** ⇒ server-side entitlement, real auth, sync — but you now own a backend, its uptime, and its COGS.
- **Standalone** ⇒ no backend, no COGS, no uptime — but no revocation, no usage telemetry, and no way to cut off a non-payer.

**Decide at intake.** Retrofitting a backend onto a shipped offline app is a rewrite; retrofitting offline licensing onto a connected app is a second product.
→ Implementations owned by `72` § License Management (Standalone, no backend) · § Authentication (Connected mode) · § Sync Architecture (Connected mode).

**2. Desktop is the ONLY type with NO mandatory intermediary — but the OS is still a gatekeeper.**
Mobile is forced into store billing. An extension cannot bill in-store at all. Desktop can do **either** — and the default, direct download from your own domain, means **no store, no review, no commission: you keep 100%**. If you *do* choose a store, the cut is real and asymmetric, and this is the number nobody else in the repo states:

- **Mac App Store** — Apple takes a commission on sales (reduced for subscriptions and Small-Business-Program members; in 2026 Apple moved to a layered fee shaped by payment path and user type). ([App Store fee changes, 2026](https://blog.funnelfox.com/apple-app-store-fees-2026-eu-dma/))
- **Microsoft Store** — **you may use your own commerce system and keep 100%** for non-gaming apps; Microsoft's cut applies only if you opt into *its* commerce. Publishing is free. ([Microsoft Store revenue share](https://appetiser.com.au/blog/microsoft-store-revenue-now-gives-developers-a-95-cut-on-one-condition/), [free publishing](https://techcrunch.com/2025/05/19/itll-soon-be-free-to-publish-apps-to-the-microsoft-store/))

**The catch that kills launch dates:** with no store, **the OS becomes the gatekeeper — and the tax it charges is paid in conversion, not in commission.** Be precise about what actually happens to an unsigned build, because the two platforms differ:

- **macOS** — since Sequoia (15) the Control-click bypass is **gone**. A user must open System Settings → Privacy & Security → *Open Anyway* → and enter an admin password. ([Apple removed the Control-click override](https://www.idownloadblog.com/2024/08/07/apple-macos-sequoia-gatekeeper-change-install-unsigned-apps-mac/))
- **Windows** — SmartScreen **warns** ("Windows protected your PC") and permits *More info → Run anyway*; it is friction, not a wall. But **Smart App Control blocks unsigned executables outright** unless they carry positive reputation. ([Microsoft: SmartScreen reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation))

So the honest statement is not "unsigned is impossible" — it is **"unsigned converts at near zero."** A prospect who downloads your app and is told the OS protected them from it does not go hunting through System Settings; they close the window. Code signing is therefore a **launch-blocking prerequisite carrying a recurring cost AND an identity-verification lead time** — a paperwork queue, not a packaging step.
→ Channels, costs and the signing matrix are owned by `72` § Distribution Channels + § Code Signing. **Read the numbers there; never copy them here.**

**3. YOU own the update channel — so you own the long tail of old versions.**
No store pushes your update. A user can sit on a two-year-old build forever, and it will keep calling your API. **Every backend contract must be back-compatible or version-gated from day 1**, and the app needs a "you must update" floor. Architecture decision, not an ops chore.
→ Implementation owned by `72` § Auto-Update.

---

## Vision Intake Dimensions

### 1. Market & Positioning

**Force:** named ICP · the one workflow that is *better on the desktop than in a browser* · 3–5 named competitors · one-sentence moat.
**Default:** a wedge that **needs** the desktop — local filesystem access, OS integration, offline capability, heavy local compute, or data that must never leave the machine. **If the product works fine as a web app, it should BE a web app** — otherwise you pay the signing, updating and cross-platform tax for nothing.
**Why now:** "why is this not a website?" is the first question a buyer asks and the last one a planner asks. Answer it at intake, or the scaffold choice itself is wrong.

### 2. Monetization Model

**Force:** one-time licence / subscription / freemium · **and (from Fork 1) whether entitlement is enforceable at all**.
**Default:** direct sale, own commerce, zero intermediary. A standalone app's licence is offline-verifiable and therefore **crackable** — pick a price and a market where that is acceptable, or pick connected.
**Why now:** the entitlement mechanism is Epic-1 architecture. It cannot be bolted on.

### 3. Platform Scope

**Force:** Windows / macOS / Linux — which, at v1?
**Default:** ship only the platforms your ICP actually uses. Every added OS multiplies signing identity, notarization, testing and support. **macOS is the expensive one** (identity + notarization + entitlements); Linux is the cheap one.
**Why now:** each platform is a distinct signing identity with its own lead time, and "we'll add Mac later" means re-testing everything.

### 4. Trust & Signing Readiness

**Force:** who is the **legal identity** that will hold the signing certificate (individual vs company), and **when does verification start**?
**Default:** **start identity verification before you need it.** It is a paperwork process with a queue, not a purchase.
**Why now:** unsigned ⇒ the OS blocks the app ⇒ there is no launch. A signing identity cannot be conjured in the final week.

### 5. Data Residency & Local Storage

**Force:** what lives **only** on the user's machine · what syncs · what must be encrypted at rest.
**Default:** local-first; encrypt anything sensitive at rest. In **standalone** mode the user's data never reaches you — which is a **selling point** (say it out loud in positioning) *and* means no telemetry, no backup of their work, and no way to help when their disk dies.
**Why now:** it drives the schema, the sync design, the compliance surface and the marketing claim — all irreversible.
→ Implementation owned by `72` § Local Persistence · § KVKK / GDPR Compliance.

### 6. Onboarding & Activation

**Force:** the activation event · what the user must install/grant/configure before it can happen · time-to-activation.
**Default:** the app must be **useful before it is licensed** (trial or free tier). Desktop install is a high-friction commitment — a user who downloads, installs, dismisses an OS warning and *then* hits a paywall does not come back.
**Why now:** desktop has the highest install friction of any Fabrik type. A paywall at the widest point of the funnel kills it there.

### 7. Unit Economics

**Force:** price · the intermediary cut (**zero on direct download** — bank it; real if you choose a store) · **signing + notarization as a fixed recurring cost** · update-hosting egress · backend COGS **only if connected** · CAC · payback.
**Default:** direct sale, own commerce. **A standalone app's marginal COGS is ≈ zero** — the strongest gross margin of any Fabrik product type. Connected mode trades that margin for enforceability.
**Why now:** the standalone-vs-connected fork *is* an economics fork, not merely an architectural one. Model both before choosing.

### 8. Risk Register

**Force:** top risks + a named mitigation each — **signing identity rejected or delayed** (fallback?) · **OS-level breakage** (an OS release breaking the app; platform deprecations arrive on the vendor's calendar, not yours) · **piracy** (standalone only — accepted, not solved) · store rejection **if** you chose a store · key-person.
**Default:** treat OS platform risk as recurring and calendared, not as an incident.
**Why now:** an OS release can break a shipped app for every user at once — and unlike a web app, **you cannot fix it for them.** They must download the fix, which means Fork 3 is a risk-register problem too.

### 9. GTM

**Force:** ONE primary channel — content/SEO to a download page · power-user package channels · community · a store listing purely for reach.
**Default:** own landing page + direct download. **The download page IS the funnel**; a store listing is an acquisition channel, not a distribution requirement.
**Why now:** with no store you have no store-search to fall back on. The channel decision carries more weight here, not less.

### 10. Sequencing & Kill Criteria

**Force:** v1 = one workflow, one platform · explicit kill/pivot criteria **with a date** · what evidence would prove this should have been a web app.
**Default:** ship the wedge to one OS, validate, then expand.
**Why now:** the only structural defense against building past the point of disproof — and desktop's cross-platform tax makes over-scoping unusually expensive.

### Vision Summary Gate

Confirm the Vision Summary **only when every dimension above is resolved or logged as an Open Question**, and **standalone-vs-connected is decided** (Fork 1 — nothing downstream can proceed without it). Decisions → `Technology Decisions` + `Value Streams`. Unresolved → `Open Questions` (blocks confirmation). Scaffold signal: `desktop-app` alone (standalone) **or** `desktop-app` + `python-api`/`node-api` (connected) = multi-epic.

---

## Epic Decomposition Directives

### Mandatory Epic Coverage

| Epic | Always required? | Boundary rule |
|---|---|---|
| **Epic 1: Mode + Scaffold** | **Yes** | The standalone-vs-connected decision (Fork 1) is settled HERE; everything downstream forks on it. Process-model security from day 1 — not a hardening pass later. |
| Epic 2a: Standalone core | If standalone | Offline-first local storage, offline licence validation, optional local LLM. **Skip entirely if connected.** |
| Epic 2b: Connected core | If connected | Backend + auth + sync + real-time. **Skip entirely if standalone.** The backend is its own Fabrik service with the full 4-stage lifecycle. |
| **Epic 3: Distribution + Signing + Auto-Update** | **Yes** | **Never a "polish" epic.** Signing is launch-blocking and has an external identity lead time (§4) — start it EARLY and in PARALLEL, not after the code is done. |
| Epic 4: Native integrations | If the product needs them | Deep-links, tray, autostart, dock badges. Cheap once Epic 1 exists. |
| Epic 5: Compliance | Yes if submitting to a store; always if KVKK/GDPR applies | Privacy manifests, consent flows, store declarations. |
| Epic 6: Testing | **Yes** | E2E + unit. |

**Single-epic desktop visions are rare** — Epic 1 and Epic 3 are nearly always separate, precisely because signing has a lead time that must run in parallel with the build.

### Parallel Lane Opportunities

After Epic 1: **core product** · **signing + distribution + update channel** (fully independent — and **start it first**, it has an external queue) · **backend** (connected mode only — independent behind the API contract) · **landing/download page** (fully independent; different scaffold).

### Anti-Patterns

- Do **NOT** defer the standalone-vs-connected decision. It is Epic 1's reason to exist, and every later epic forks on it.
- Do **NOT** schedule signing as a launch-week task. It is a **paperwork queue with a lead time**, and unsigned means unrunnable.
- Do **NOT** assume you can revoke a standalone licence, or see how a standalone app is used. You cannot. Plan for it.
- Do **NOT** assume users are on the latest version (Fork 3). Version-gate the API from day 1.
- Do **NOT** build a desktop app whose value would survive intact as a web app. Answer "why not a website?" at intake.
- Do **NOT** copy signing costs, store fees, or window sizes into this file. They live in `72`.

### Code-time facts live in `72-desktop.md`

Framework choice, the process model and IPC posture, local persistence + encryption, credential storage, **§ Distribution Channels**, **§ Code Signing**, **§ Auto-Update**, native integrations, licence verification, authentication, sync, compliance manifests, testing and banned patterns are **owned by `72-desktop.md`**. Cite it; never restate it here.
