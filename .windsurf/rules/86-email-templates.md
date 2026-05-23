---
activation: glob
globs: ["**/emails/**", "**/*.mjml", "**/templates/*email*", "**/templates/*notification*", "**/push/**", "**/notifications/**"]
description: Email & template creation — MJML+Jinja2 pipeline, Resend ESP, push/in-app, deliverability, cross-cutting across SaaS/mobile/WordPress
trigger: glob
---

# Email & Template Creation Rules (cross-cutting)

Apply to every ticket that creates or edits an **email, push notification, or in-app message template** in any saas / mobile / wordpress project. Follow verbatim; do not re-decide the stack per ticket.

---

## Mandated Stack (resolved — do not re-evaluate)

- **Structure/layout: MJML** (build-time, Node CLI). MJML auto-emits Outlook/Word table layouts + VML; this is the entire reason it's mandated — never hand-code email HTML.
- **Variables/logic: Jinja2** placeholders embedded in MJML via `<mj-raw>{% ... %}</mj-raw>` and `{{ var }}`. Runtime is **framework-agnostic `jinja2`** (works in FastAPI or Flask). **No Node in the runtime image.**
- **Brand: Ocoron Design System** tokens (colors, fonts) set as `<mj-attributes>` defaults in ONE shared partial. Atelier Rebul brand kept separate, never co-branded.
- **Sending: Resend** (transactional). Send the compiled HTML via the API — **ignore Resend's React Email/JSX layer** (you use MJML+Jinja2; it's irrelevant). Keep **transactional** and **marketing** on separate streams. Escalate critical auth mail to Postmark only on *measured* deliverability issues.
- **Internal/ops alerts: Apprise** (already deployed) — for system/ops notifications ONLY, never customer email.

---

## The Workflow (fast path — 5 steps)

1. **Author** `<name>.mjml` with Jinja2 placeholders; pull header/footer/brand from shared partials via `<mj-include>`.
2. **Compile** with local MJML CLI watcher to `emails/dist/<name>.html`. Build-time only.
3. **Commit the compiled `dist/` HTML** to the repo (deterministic, keeps runtime Python-only — no build-stage Node required on Coolify).
4. **Render at runtime**: Python loads the compiled HTML, Jinja2 fills variables, attaches the plain-text alternative (`multipart/alternative`), hands to ESP.
5. **Test before ship**: render to test inboxes (Apple Mail / Gmail / Outlook-Windows / dark mode) — Litmus/Email-on-Acid if available, manual test inboxes otherwise.

---

## Repo Contract

```
emails/
  src/         <name>.mjml                # source of truth (committed)
  partials/    header|footer|brand.mjml   # mj-include; brand tokens live here ONLY
  dist/        <name>.html                # compiled, committed; what runtime loads
```

One brand partial governs all templates — no per-template colour/font drift.

---

## Core Rules (MUST — universal)

### Rendering Fidelity

- Outlook-Windows uses the Word engine — rely on MJML's table+VML output; never assume flexbox/grid.
- All CSS inlined at build (MJML does this); no external `<link>` stylesheets.
- No layout that depends on `background-image` (Outlook drops it) — use solid fills or VML via MJML.
- Keep final HTML **< 102 KB** (Gmail clips beyond it).

### Deliverability (set-and-forget, pro-grade)

- Sending domain has **SPF + DKIM + DMARC** (configure via Cloudflare DNS).
- Send from a **dedicated subdomain** (e.g. `mail.<domain>`), never the root domain — protects primary reputation.
- **`List-Unsubscribe` + one-click (RFC 8058)** on all bulk/marketing mail — mandatory under Gmail/Yahoo bulk-sender rules.
- ESP bounce/complaint webhooks to auto-suppress. No sending to suppressed addresses.

### Accessibility & Content

- Mandatory **plain-text alternative** for every email (deliverability + a11y).
- `lang` set; layout tables `role="presentation"`; every image has `alt`; AA contrast.
- **Preheader** text on every email; descriptive subject.
- Absolute `https://` image URLs (Backblaze B2 / Cloudflare CDN); retina-ready.

### 12-Factor / Docker

- Compilation is build-time; **runtime image stays `python:*-slim-bookworm`, linux/amd64, zero Node**.
- ESP keys via env, never committed. Templates are code — versioned in the repo.

---

## Stack Adapters (only the deltas)

### SaaS (FastAPI + Jinja2)

- Full pipeline as above. Transactional (signup, reset, receipts, alerts) + lifecycle (onboarding, nurture, dunning, win-back, expansion).
- **ESP:** transactional: **Resend** (3k/mo free, $20/50k, clean API; escalate critical auth mail — reset, receipts — to **Postmark** only on *measured* deliverability issues). Marketing/lifecycle: Loops or Resend Broadcasts (separate stream). SES only if cost-scaling forces it.
- Dunning/entitlement emails are driven by Paddle webhooks (tie to SaaS module dim 5).

### Mobile (python-api backend + push + in-app)

- **Email = the SAME backend pipeline** (the app's transactional mail comes from python-api — reuse, don't rebuild).
- **Push templates** are a separate surface: single FCM payload for both platforms (via Expo Push / OneSignal). Rules: title+body **localized (en+tr)**, `data` payload carries the **deep link** (Universal/App Link via ChottuLink — ties to mobile attribution stack), **no PII in payload**, respect opt-in.
- **In-app messages** templated + localized; prefer RevenueCat paywalls/messages over a custom system (set-and-forget).
- Push copy is short; email carries the detail.

### WordPress (Woo / ESP — NOT Jinja2)

- **MJML stays the design source of truth**, but output is consumed differently — **no Jinja2 at runtime**.
- Compiled HTML feeds either **WooCommerce email template overrides** (in a child theme or mu-plugin) or the **ESP/newsletter tool**; variables via **WP/Woo merge tags or ESP merge tags**, not `{{ }}`.
- **Marketing/newsletter default:** FluentCRM (self-hosted, no per-contact fee, set-and-forget). Transactional WP mail via a reputable SMTP plugin pointed at the **same ESP + same authenticated subdomain**.
- Same SPF/DKIM/DMARC + List-Unsubscribe rules apply.

---

## Acceptance Criteria (gates)

- [ ] Template authored in MJML; no hand-coded email HTML.
- [ ] Brand pulled from the shared partial; no inline brand values.
- [ ] Compiled `dist/` HTML committed; runtime loads compiled output (or Woo/ESP consumes it).
- [ ] Plain-text alternative present.
- [ ] Preheader, `alt` text, AA contrast, `lang` set.
- [ ] HTML < 102 KB.
- [ ] Sending domain has SPF + DKIM + DMARC on a dedicated subdomain.
- [ ] `List-Unsubscribe` one-click on bulk mail.
- [ ] Rendered/tested on Apple Mail + Gmail + Outlook-Windows + dark mode.
- [ ] Runtime image contains no Node; keys via env.
- [ ] (Mobile) push payload localized, deep-linked, PII-free.
- [ ] (WP) consumed via Woo override / ESP with correct merge tags.

---

## Anti-Patterns (MUST NOT)

- Node in the runtime image
- Hand-coded HTML tables
- External `<link>` stylesheets
- Background-image-dependent layout
- Customer email through Apprise
- Missing plain-text part
- Sending from the root domain
- Secrets/PII in push payloads
- Per-template brand drift
- Uncompiled MJML shipped to runtime

---

## ESP Decision Log (why Resend — traceable)

Decision: **Resend** as transactional default; **Postmark** as escalation-only. Rationale (verified 2026):

- **Free tier decisive at this stage:** Resend 3,000 emails/mo free vs Postmark 100 (dev-only, pay from day one).
- **Cheaper as it scales:** Postmark $15/mo for 10k vs Resend $20/mo for 50k — Resend pulls ahead past ~10k.
- **DX/ops:** clean API + solid Python SDK = AI-agent-friendly, set-and-forget.
- **Known trade-off (bounded):** Postmark = deliverability champion since 2010 (near-zero spam); Resend newer, may lose 1-3 pts inbox placement in sensitive categories — sufficient for most transactional mail.
- **Escalation rule (Fabrik "escalate on proven limit"):** move only mission-critical streams (reset, receipts) to Postmark *if and when* a deliverability problem is measured. Do not pre-pay. 2026 solo-dev consensus: Resend early-stage, Postmark when deliverability becomes mission-critical.
