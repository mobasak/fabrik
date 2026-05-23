---
activation: glob
globs: ["**/emails/**", "**/*.mjml", "**/templates/*email*", "**/templates/*notification*", "**/push/**", "**/notifications/**"]
description: Email & template creation — MJML+Jinja2 pipeline, Resend ESP, push/in-app, deliverability, cross-cutting across SaaS/mobile/WordPress
trigger: glob
---
<!-- CONSUMER: Coding agents creating email/push/notification templates
     GOAL: MJML+Jinja2 pipeline, Resend ESP, deliverability, per-scaffold adapters
     TRAYCER USAGE: Injects as Context File for any ticket creating email/push templates.
     AGENT USAGE: Follow the 5-step workflow. Author in MJML, compile, commit dist/, render at runtime. -->

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
  i18n/
    en.json                              # English strings (source of truth)
    tr.json                              # Turkish strings
```

One brand partial governs all templates — no per-template colour/font drift. One i18n JSON per locale governs all localized strings.

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

## Localized Email Rendering

Every email must be sent in the **recipient's preferred language**. The template stays the same (MJML structure); only the variable values change per locale.

### Language Detection (source of truth)

| Project type | Where locale lives | How it's set |
|---|---|---|
| SaaS (Supabase) | `users.locale` column in PostgreSQL | Set at signup from `Accept-Language` header; user changes via profile settings |
| Mobile | `users.locale` synced from device | `expo-localization` device locale, synced to Supabase on first launch |
| WordPress | WP `get_user_locale()` or ESP subscriber tag | WP user profile or FluentCRM subscriber language field |

### Repo Structure

```
emails/
  src/           <name>.mjml           # structure (language-agnostic)
  partials/      header|footer|brand.mjml
  dist/          <name>.html           # compiled (language-agnostic)
  i18n/
    en.json                            # English strings (source of truth)
    tr.json                            # Turkish strings
```

### Rendering Flow

```python
# 1. Load compiled template
template = jinja_env.get_template("dist/welcome.html")

# 2. Load locale strings
locale = user.locale or "en"  # fallback to English
strings = load_json(f"emails/i18n/{locale}.json")

# 3. Render with locale-specific variables
html = template.render(
    user_name=user.name,
    **strings["welcome"],  # subject, heading, body, cta_label, etc.
)

# 4. Set Content-Language header
send_email(to=user.email, subject=strings["welcome"]["subject"], html=html, lang=locale)
```

### Rules

- **English is the source-of-truth locale.** All other locales derive from `en.json`.
- **Every user-visible string in the email body comes from the i18n JSON** — never hardcoded in the MJML template. The MJML template uses Jinja2 `{{ variables }}` that resolve to localized strings.
- **Subject lines are localized** — they live in the i18n JSON, not in application code.
- **Fallback:** if the user's locale has no translation file, fall back to `en`. Never send an empty or broken template.
- **Date/time/number formatting:** use `Intl`-style locale-aware formatting in the rendering code (Python `babel` or manual locale dispatch). Never hardcode `MM/DD/YYYY` or `$1,000.00`.
- **RTL support:** for `ar` and `fa` locales, set `dir="rtl"` on the MJML `<mj-body>`. MJML handles the layout flip. Test RTL rendering before shipping.

---

## Newsletters & Marketing Email

### Two Streams — Never Mix

| Stream | Purpose | ESP | Unsubscribe | Sending domain |
|---|---|---|---|---|
| **Transactional** | Signup, reset, receipts, alerts, dunning | Resend (escalate to Postmark) | Not required (operational) | `mail.<domain>` |
| **Marketing** | Newsletters, product updates, lifecycle (onboarding, nurture, win-back, expansion) | Loops or Resend Broadcasts | **Mandatory** (RFC 8058 one-click) | `news.<domain>` or `mail.<domain>` (separate subdomain recommended) |

**Why separate streams:** mixing transactional and marketing on the same sending identity lets marketing complaints (spam reports) degrade transactional deliverability (password resets landing in spam). Separate streams isolate reputation.

### Transactional Email Template Inventory

Every project must ship these transactional templates before go-live. Check the column that matches your project type.

#### Auth & Account (all project types)

**Pattern B (Supabase Auth) note:** Supabase sends verify-email and password-reset emails by default using its own generic template — wrong brand, wrong fonts, no i18n, no version control. **Disable Supabase's built-in emails** and send all auth emails through your MJML pipeline instead. Configure via Supabase Auth Hooks or custom SMTP pointing to your Resend-authenticated subdomain. This ensures every email the user receives matches your brand, is localized, and is version-controlled in the repo.

| Template | Trigger | SaaS | Mobile | WP | Notes |
|---|---|---|---|---|---|
| **Verify email** | Signup / email change | Yes | Yes | Yes | MJML template with verification token link. Expires in 24h. Pattern B: disable Supabase's built-in, send via your pipeline. |
| **Welcome** | Email verified | Yes | Yes | Yes | Confirms account is active. Links to first action / onboarding. |
| **Password reset request** | User clicks "forgot password" | Yes | Yes | Yes | MJML template with reset token link. Expires in 1h. Never confirm whether email exists. Pattern B: disable Supabase's built-in, send via your pipeline. |
| **Password reset confirmation** | Password successfully changed | Yes | Yes | Yes | Informational — no action needed. Includes "if this wasn't you" warning. |
| **Email changed** | User updates email in settings | Yes | Yes | — | Sent to OLD email as security alert. |
| **Account deleted** | User deletes account | Yes | Yes | — | Confirms deletion. Notes data retention period if applicable. |

#### Billing & Subscription

| Template | Trigger | SaaS | Mobile | WP | Notes |
|---|---|---|---|---|---|
| **Payment receipt** | Successful payment (Paddle webhook / RevenueCat) | Yes | Yes | Woo | Amount, plan, next billing date, invoice link. |
| **Trial starting** | User starts free trial | Yes | Yes | — | Trial length, what happens at end, upgrade CTA. |
| **Trial ending** | 3 days before trial expires | Yes | Yes | — | Convert now or lose access. Single CTA. |
| **Subscription renewed** | Auto-renewal successful | Yes | — | Woo | Confirmation. Next billing date. Mobile: stores/RevenueCat handle renewal notifications. |
| **Payment failed (dunning #1)** | First payment failure (grace period) | Yes | Yes | Woo | "Update your payment method" — urgent but not alarming. |
| **Payment failed (dunning #2)** | Second failure, 3 days later | Yes | Yes | Woo | More urgent. "Access will be suspended in X days." |
| **Payment failed (dunning #3)** | Final warning before cancellation | Yes | Yes | Woo | "Last chance — update payment or lose access today." |
| **Subscription cancelled** | User cancels or final dunning fails | Yes | Yes | Woo | Confirms cancellation. Access-until date. Win-back CTA. |
| **Plan upgraded** | User upgrades plan | Yes | — | — | Confirms new plan, new features available, prorated charge. |
| **Plan downgraded** | User downgrades plan | Yes | — | — | Confirms downgrade. Effective date. Features losing access to. |
| **Invoice** | Monthly/annual billing cycle | Yes | — | Woo | PDF attached or link. Required for B2B. |

#### Team & Collaboration (SaaS only)

| Template | Trigger | SaaS | Mobile | WP | Notes |
|---|---|---|---|---|---|
| **Team invite** | Admin invites team member | Yes | — | — | Invite link + org name. Expires in 7 days. |
| **Invite accepted** | Invited user joins | Yes | — | — | Sent to admin who invited. |
| **Role changed** | Admin changes member role | Yes | — | — | Sent to affected member. |
| **Removed from team** | Admin removes member | Yes | — | — | Sent to removed member. |

#### System & Security

| Template | Trigger | SaaS | Mobile | WP | Notes |
|---|---|---|---|---|---|
| **New device login** | Login from unrecognized device/location | Yes | Yes | — | Device, location, time. "If this wasn't you" link. |
| **Suspicious activity** | Multiple failed logins / unusual pattern | Yes | Yes | — | Security alert. Link to review sessions. |

#### WordPress-Specific (WooCommerce)

| Template | Trigger | SaaS | Mobile | WP | Notes |
|---|---|---|---|---|---|
| **Order confirmation** | Customer places order | — | — | Yes | Order details, shipping estimate, order tracking link. |
| **Order shipped** | Tracking number added | — | — | Yes | Tracking link + estimated delivery. |
| **Order delivered** | Delivery confirmed | — | — | Yes | Review request CTA. |
| **Refund processed** | Admin processes refund | — | — | Yes | Amount, reason, timeline for credit. |

**Rules for all transactional templates:**
- Every template has an MJML source in `emails/src/`, compiled to `emails/dist/`, localized via `emails/i18n/`.
- Every template has a plain-text alternative.
- Auth-critical emails (verify, reset) should use the Postmark escalation path if deliverability issues are measured.
- Dunning emails are triggered by payment provider webhooks (Paddle / RevenueCat), not by application schedulers.
- "If this wasn't you" links go to a session-review or password-reset page, never to a generic support form.

### Newsletter Architecture

- **List management:** users opt-in during signup or via a preference center. Opt-in state stored in PostgreSQL (`email_preferences` table or user profile). Double opt-in recommended for EU (GDPR).
- **Preference center:** accessible from user settings AND from the email footer. Users can: toggle per-category (product updates, tips, announcements), change frequency (weekly/monthly digest), or unsubscribe entirely.
- **Unsubscribe:** one-click `List-Unsubscribe` header (RFC 8058) on every marketing email — mandatory under Gmail/Yahoo bulk-sender rules. The unsubscribe link in the footer is a backup, not the primary mechanism.
- **Frequency control:** respect user's preference. Default: weekly digest. Never send more than the user chose.
- **Suppression:** honor ESP bounce/complaint webhooks. Auto-suppress bounced and complained addresses. Never re-add a suppressed address without explicit re-opt-in.

### Marketing Email Templates

Same MJML pipeline as transactional — author in MJML, compile, commit, render with Jinja2, localize per user. Additional rules:

- **Preheader is mandatory** — it's the first thing users see in their inbox after the subject.
- **Single CTA per email** — one primary action button. Secondary links as text only.
- **Footer must include:** unsubscribe link, preference center link, company name + address (CAN-SPAM), "why you received this" explanation.
- **No tracking pixels** in operator-facing emails (trust). Tracking pixels acceptable in marketing emails to external subscribers with consent.
- **Send time:** respect the user's timezone. Default: Tuesday-Thursday, 9-11am user-local.

### Lifecycle Email Sequences

Define in the marketing ESP (Loops / Resend Broadcasts), not in application code:

| Sequence | Trigger | Emails | Goal |
|---|---|---|---|
| **Onboarding** | Signup | 3-5 over 7 days | Activation (user completes core action) |
| **Nurture** | Activated but low usage | 2-3 over 14 days | Feature discovery, depth |
| **Dunning** | Payment failed (Paddle webhook) | 3 over 7 days | Recover revenue |
| **Win-back** | Churned (cancelled 30+ days) | 1-2 over 30 days | Re-engagement |
| **Expansion** | High usage near plan limit | 1-2 triggered | Upgrade |

- All sequences are **localized** per user locale.
- All sequences **stop** on unsubscribe or successful conversion.
- Dunning emails are triggered by Paddle/RevenueCat webhooks — not by the marketing ESP's scheduler.

### Marketing Consent & Compliance

**Scope:** applies to marketing / lifecycle email only (newsletters, product updates, onboarding, nurture, win-back, expansion). Transactional email is exempt — operational, not commercial messaging, no marketing consent required. This is another reason the two run on separate streams.

**Principle:** consent obligations follow the **recipient's jurisdiction**, not the sender's location. Operating from Turkey does not exempt mail sent to EU or other recipients.

**Default for all recipients: opt-in.** Require explicit opt-in before any marketing send, regardless of recipient country — the strictest standard, satisfies every regime below with one rule and no jurisdiction branching.

| Recipient jurisdiction | Rule | System of record |
|---|---|---|
| **Turkey** | İYS (İleti Yönetim Sistemi): consent for _ticari elektronik ileti_ must be registered in and checked against İYS before every send. Your own opt-in record is not sufficient. | İYS registry |
| **EU / EEA** | GDPR / ePrivacy: explicit (double) opt-in, documented, withdrawable. | Consent DB (`email_preferences`) |
| **US** | CAN-SPAM: opt-out minimum (honest headers, physical address, working unsubscribe). Opt-in default already exceeds this. | Consent DB |
| **Everywhere else** | Opt-out floor (working unsubscribe + suppression). Opt-in default already exceeds this. | Consent DB |

**Universal — all recipients, all jurisdictions:**

- One-click `List-Unsubscribe` (RFC 8058) on every marketing email.
- Honor unsubscribe + bounce/complaint suppression immediately; never re-add a suppressed address without explicit re-opt-in.
- Footer: unsubscribe link, preference center, company name + address, "why you received this."

**Turkey operational note:** İYS is a central registry — recording consent only in your own DB does not make you compliant for TR recipients. You must (a) sync each TR opt-in to İYS and (b) check the recipient's İYS status before sending, since they can revoke directly in İYS without telling you. İYS does not apply to transactional mail. <!-- Confirm the current İYS integration path and any ESP-side support with your mali müşavir — this is the requirement, not legal advice. -->

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
- [ ] All transactional templates from the inventory exist for the project type (auth, billing, team, system).
- [ ] Email i18n: `emails/i18n/en.json` + `tr.json` exist; all user-visible strings come from i18n JSON, not hardcoded in MJML.
- [ ] Subject lines localized per user locale.
- [ ] Fallback to `en` when user's locale has no translation file.
- [ ] Marketing emails on a separate stream from transactional (separate ESP config or subdomain).
- [ ] `List-Unsubscribe` one-click header on every marketing email.
- [ ] Preference center accessible from user settings AND email footer.
- [ ] Lifecycle sequences (onboarding, nurture, dunning, win-back) defined in marketing ESP.
- [ ] Marketing send requires opt-in consent for every recipient (universal opt-in default).
- [ ] TR recipients' consent registered/checked in İYS before send.
- [ ] EU recipients use double opt-in; consent documented and withdrawable.
- [ ] One-click `List-Unsubscribe` + suppression honored for all recipients.
- [ ] Transactional mail excluded from consent gating.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Node in the runtime image | Compile MJML at build time; runtime is Python-only |
| Hand-coded HTML tables | MJML auto-emits tables + VML |
| External `<link>` stylesheets | MJML inlines all CSS at build |
| Background-image-dependent layout | Solid fills or VML via MJML |
| Customer email through Apprise | Resend (transactional) or Loops (marketing). Apprise = internal/ops only |
| Missing plain-text part | `multipart/alternative` with plain-text always |
| Sending from the root domain | Dedicated subdomain (e.g. `mail.<domain>`) |
| Secrets/PII in push payloads | Deep link only; PII stays server-side |
| Per-template brand drift | ONE shared brand partial governs all templates |
| Uncompiled MJML shipped to runtime | Commit compiled `dist/` HTML; runtime loads compiled output |
| Resend React Email / JSX layer | Ignored — we use MJML+Jinja2 |
| Hardcoded strings in email templates | i18n JSON per locale (`emails/i18n/{locale}.json`) |
| Hardcoded date/number formats in emails | Locale-aware formatting via `babel` or equivalent |
| Mixing transactional + marketing on one stream | Separate streams (separate ESP config or subdomain) |
| Marketing email without `List-Unsubscribe` header | RFC 8058 one-click unsubscribe on every marketing email |
| Lifecycle sequences defined in application code | Define in marketing ESP (Loops / Resend Broadcasts) |
| Sending marketing email without opt-in | Universal opt-in default; double opt-in for EU |
| Re-adding suppressed/bounced addresses | Explicit re-opt-in required |
| Marketing email to a TR recipient without İYS-registered consent | Register + verify consent in İYS before send (own-DB consent is insufficient for TR) |
| Assuming a Turkey base exempts you from GDPR for EU recipients | Consent follows recipient jurisdiction; universal opt-in covers all |
| Applying marketing-consent gating to transactional mail | Transactional is exempt — operational, separate stream |

---

## Related Rule Packs

- `35-security-auth.md` — transactional email for auth (reset, verification) references this pipeline
- `55-observability.md` — structured logging for email send events
- `58-resilience.md` — timeout/retry for Resend API calls (applied in the sending code, not this pack)
- `80-mobile.md` — push notification rules (expo-notifications, FCM)
- `ocoron-design-system.md` — brand tokens used in the shared partial

---

## ESP Decision Log (why Resend — traceable)

Decision: **Resend** as transactional default; **Postmark** as escalation-only. Rationale (verified 2026):

- **Free tier decisive at this stage:** Resend 3,000 emails/mo free vs Postmark 100 (dev-only, pay from day one).
- **Cheaper as it scales:** Postmark $15/mo for 10k vs Resend $20/mo for 50k — Resend pulls ahead past ~10k.
- **DX/ops:** clean API + solid Python SDK = AI-agent-friendly, set-and-forget.
- **Known trade-off (bounded):** Postmark = deliverability champion since 2010 (near-zero spam); Resend newer, may lose 1-3 pts inbox placement in sensitive categories — sufficient for most transactional mail.
- **Escalation rule (Fabrik "escalate on proven limit"):** move only mission-critical streams (reset, receipts) to Postmark *if and when* a deliverability problem is measured. Do not pre-pay. 2026 solo-dev consensus: Resend early-stage, Postmark when deliverability becomes mission-critical.
