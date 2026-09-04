---
activation: glob
globs: ["**/emails/**", "**/*.mjml", "**/templates/*email*", "**/templates/*notification*", "**/push/**", "**/notifications/**", "**/email*", "**/mailer*", "**/notify*", "**/notification*"]
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
3. **Commit the compiled `dist/` HTML** to the repo (deterministic, keeps runtime Python-only — no build-stage Node required on the VPS).
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

### Dark Mode

- `<meta name="color-scheme" content="light dark" />` and `<meta name="supported-color-schemes" content="light dark" />` in the shared brand partial — mandatory.
- `@media (prefers-color-scheme: dark)` overrides for background, text, and subtext colors — prevents Apple Mail / Outlook from auto-inverting white cards to unreadable dark-on-dark.
- Never rely on automatic dark mode inversion — always define explicit dark palette in the brand partial.
- Test dark mode rendering on Apple Mail (iOS) + Outlook (Windows) before shipping any new template.

**Email client compatibility matrix:**

| Client | Rendering Engine | MJML Compatible? | Dark Mode Support |
|---|---|---|---|
| Apple Mail (Mac/iOS) | WebKit | Yes (MJML tables) | Yes (`color-scheme` meta) |
| Gmail (Web/Android/iOS) | Custom (strips `<style>`) | Yes (MJML inlines all CSS) | Partial (ignores `@media prefers-color-scheme` but respects `color-scheme` meta) |
| Outlook 2016-2026 (Windows) | Word engine | Yes (MJML VML conditionals) | Yes (`color-scheme` meta since 2021) |
| Outlook.com / New Outlook | Web | Yes | Yes |
| Windows Mail | Same as Outlook.com | Yes | Yes |
| Spark Mail | WebKit | Yes | Yes |
| eM Client | Chromium | Yes | Yes |
| Thunderbird | Gecko | Yes | Yes (`@media` support) |
| Samsung Mail | WebKit | Yes | Yes |

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

- Compilation is build-time; **runtime image stays `python:*-slim-<debian_codename>` (the codename from `versions.yaml`), linux/amd64, zero Node**.
- ESP keys via env, never committed. Templates are code — versioned in the repo.

---

## Localized Email Rendering

Every email must be sent in the **recipient's preferred language**. The template stays the same (MJML structure); only the variable values change per locale.

### Language Detection (source of truth)

| Project type | Where locale lives | How it's set |
|---|---|---|
| SaaS (Pattern A) | `users.locale` column in `postgres-main` | Set at signup from `Accept-Language` header; user changes via profile settings |
| Mobile | `users.locale` synced from device | `expo-localization` device locale, synced to the FastAPI backend on first launch |
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
| **Marketing** | Newsletters, product updates, lifecycle (onboarding, nurture, win-back, expansion) | Resend Broadcasts → self-hosted Listmonk + SES at scale | **Mandatory** (RFC 8058 one-click) | `news.<domain>` (dedicated marketing subdomain) |

**Why separate streams:** mixing transactional and marketing on the same sending identity lets marketing complaints (spam reports) degrade transactional deliverability (password resets landing in spam). Separate streams isolate reputation.

### Transactional Email Template Inventory

Every project must ship these transactional templates before go-live. Check the column that matches your project type.

#### Auth & Account (all project types)

**Pattern A (default) — the app owns auth email natively.** With `fabrik-lib/fastapi-user-auth` (Pattern A, the default per `agents-fabrik.md § Supabase`), FastAPI issues its own JWTs and triggers verify-email and password-reset emails directly through **this MJML+Jinja2 pipeline** — no third-party auth mailer, no Auth Hooks, no built-in emails to disable. Every auth email is brand-correct, localized, and version-controlled in the repo by construction. Send via Resend on your authenticated subdomain like any other transactional mail.

**Legacy — migrating off Supabase Auth (Pattern B):** a project still on Supabase Auth sends verify-email and password-reset by default using Supabase's generic template — wrong brand, wrong fonts, no i18n, no version control. **Disable Supabase's built-in emails** and route all auth emails through your MJML pipeline instead (via Supabase Auth Hooks or custom SMTP pointing to your Resend-authenticated subdomain) until the project migrates to Pattern A, after which the app owns these emails natively.

| Template | Trigger | SaaS | Mobile | WP | Notes |
|---|---|---|---|---|---|
| **Verify email** | Signup / email change | Yes | Yes | Yes | MJML template with verification token link. Expires in 24h. Pattern A: app sends it natively. Legacy Pattern B: disable Supabase's built-in, send via your pipeline. |
| **Welcome** | Email verified | Yes | Yes | Yes | Confirms account is active. Links to first action / onboarding. |
| **Password reset request** | User clicks "forgot password" | Yes | Yes | Yes | MJML template with reset token link. Expires in 1h. Never confirm whether email exists. Pattern A: app sends it natively. Legacy Pattern B: disable Supabase's built-in, send via your pipeline. |
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

Define in the marketing ESP, not in application code:

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

### Marketing ESP — Phased Strategy

The sender is a commodity. Your edge is the content AI, not the sending tool. Don't buy "AI email marketing" SaaS (you'd pay for a worse content engine than the one you already own), and don't build a campaign engine from scratch.

| Phase | Tool | When | Cost model |
|---|---|---|---|
| **Now** | **Resend Broadcasts** | Start here — you already run Resend for transactional | Per-contact / volume pricing |
| **At scale** | **Self-hosted Listmonk + Amazon SES** | When Resend per-contact fee exceeds ~$5-10/mo container + SES per-email rate | Listmonk: flat (Go + Postgres, deploys via `fabrik apply`, zero per-contact fee). SES: ~$0.10 per 1,000 emails |
| **WordPress** | **FluentCRM** | WordPress/Woo projects only | Self-hosted, no per-contact fee |

**Migration triggers** (Resend → Listmonk):
- Per-contact/volume cost exceeds ~$5-10/mo container + SES per-email rate
- Need more than 1 sending domain (Resend free = 1 domain)
- Need more than 1,000 contacts (Resend free tier limit)
- Same "escalate on proven limit" pattern as Resend → Postmark for transactional.

**What you do NOT do:**
- Build your own campaign engine (Forex rabbit hole — good OSS exists)
- Use Mautic (PHP, heavy, maintenance sink for solo dev)
- Send marketing from your own VPS IP (torches domain reputation — delivery always rides SES/Resend)

### Listmonk + SES Architecture (at-scale setup)

When you hit a migration trigger, this is the target architecture:

```
Your VPS (fabrik apply)                   AWS
┌─────────────────────┐                  ┌──────────────┐
│ Listmonk container  │── SMTP relay ──→ │ Amazon SES   │──→ Recipient inbox
│ (Go + Postgres)     │                  │ (shared IPs) │
│                     │← SNS webhooks ──│              │
│ - List management   │                  └──────────────┘
│ - Segments          │
│ - Campaigns         │         DNS (Cloudflare)
│ - Double opt-in     │         ┌───────────────────────────┐
│ - Bounce processing │         │ news.<domain>             │
│ - Analytics         │         │   DKIM → 3 SES CNAMEs    │
└─────────────────────┘         │   DMARC → _dmarc TXT     │
                                │ bounce.news.<domain>      │
                                │   MX → SES feedback SMTP  │
                                │   SPF → amazonses.com     │
                                └───────────────────────────┘
```

**Key architectural points:**

- **Listmonk** is the campaign orchestrator — list management, segments, templates, scheduling, analytics. Deploys via `fabrik apply` like any other Fabrik service (Go binary + Postgres, `compose.yaml`, `fabrik` network).
- **SES** is the delivery layer only — your VPS IP never touches the recipient's mail server. SES sends from **Amazon's shared IP pool** (pre-warmed, high reputation, free). Dedicated IPs ($24.95/mo per IP) only when sending consistently above **1,000 emails/day per major ISP** (Gmail, Yahoo, Outlook) — below that, shared IPs outperform because dedicated IPs lack volume to build reputation.
- **Listmonk connects to SES via SMTP relay** (`email-smtp.<region>.amazonaws.com:587`, TLS). At higher scale, consider **SES API v2** via the [listmonk-messenger](https://github.com/knadh/listmonk/wiki/Messengers) plugin — higher throughput (SES API supports 50/sec vs SMTP 14/sec default) and avoids SMTP connection overhead.
- **Bounce/complaint handling:** SES bounce and complaint notifications flow via **SNS → Listmonk webhook**. This is a 4-step setup — without it, you re-send to bounced addresses and SES suspends your account:
  1. Create an SNS topic (e.g. `ses-bounces-complaints`) in the same region as SES.
  2. In SES → Verified identity → Notifications tab, assign this SNS topic to **Bounces** and **Complaints** notification types.
  3. Create an HTTPS subscription on the SNS topic pointing to Listmonk's bounce webhook endpoint (`https://listmonk.yourdomain/webhooks/service/ses`).
  4. Confirm the subscription (SNS sends a confirmation request to the endpoint — Listmonk auto-confirms if reachable).

### SES Setup & Domain Authentication

**Domain verification (one-time per sending domain):**

1. Add `news.<domain>` as a verified identity in SES console.
2. SES generates 3 CNAME records (DKIM) — add to Cloudflare DNS.
3. **Custom MAIL FROM subdomain** (required for SPF alignment): set `bounce.news.<domain>` as the MAIL FROM domain in SES. Add two DNS records to Cloudflare:
   - `bounce.news.<domain>` MX → `feedback-smtp.<region>.amazonses.com` (priority 10)
   - `bounce.news.<domain>` TXT → `"v=spf1 include:amazonses.com ~all"`
   Without Custom MAIL FROM, the envelope sender is `amazonses.com` — SPF passes for Amazon's domain, not yours, causing DMARC SPF alignment to fail. DKIM alone can carry DMARC, but both-aligned is best practice.
4. DMARC: add `_dmarc.news.<domain> TXT "v=DMARC1; p=none; rua=mailto:dmarc@<domain>"`. **Start with `p=none`** (monitoring only — receive reports, don't enforce). Move to `p=quarantine` after 2-4 weeks of confirming DKIM+SPF alignment in DMARC reports. Then `p=reject` once confident.
5. **Same subdomain works across ESPs.** Switching from Resend to SES = update the DKIM/SPF DNS records. Domain reputation transfers — it's tied to the domain, not the ESP.

**SES Sandbox → Production:**

- New SES accounts start in **sandbox**: limited to **200 emails/day** and **1 email/second**, can only send to verified email addresses. Request production access via AWS console — provide your use case, expected volume, bounce/complaint handling plan.
- Production access is required before sending to unverified recipients. Approval typically takes 24-48h.

**SES sending limits:**

- After production access: SES starts at a **low daily sending quota** (typically 50,000/day) and auto-increases based on your sending patterns and reputation.
- SES auto-suspends if: complaint rate > **0.1%** or bounce rate > **5%**. Monitor via SES reputation dashboard.
- **Virtual Deliverability Manager (VDM):** optional SES add-on ($0.07 per 1,000 emails) that provides deliverability insights, ISP-level metrics, and automatic DKIM/DMARC recommendations. Not required at low volume, but consider when sending 50k+/month and needing ISP-level visibility.

### Listmonk Built-in Features

| Feature | Listmonk support | Notes |
|---|---|---|
| Double opt-in | ✅ Native | Configurable per list |
| `List-Unsubscribe` header | ⚠️ Two-click only | Listmonk emits `List-Unsubscribe` with a URL, but **not** RFC 8058 one-click `List-Unsubscribe-Post`. Gmail/Yahoo require one-click POST. Workaround: inject `List-Unsubscribe-Post: List-Unsubscribe=One-Click` header via Listmonk's custom headers + implement a POST handler at the unsubscribe URL. Track upstream Listmonk issues for native RFC 8058 support. |
| Bounce/complaint processing | ⚠️ Requires SNS wiring | SES → SNS topic → Listmonk webhook endpoint |
| Subscriber segments | ✅ Native | SQL-based, unlimited |
| Campaign scheduling | ✅ Native | Timezone-aware |
| Template system | ✅ Native | HTML templates — feed MJML-compiled output |
| Analytics (opens/clicks) | ✅ Native | Per-campaign, per-subscriber |
| API | ✅ Full REST API | Campaign creation, subscriber management, send triggers |
| Multiple sending domains | ✅ Unlimited | One SMTP config per domain |

### Migration Checklist (Resend → Listmonk + SES)

Execute in this order:

1. **Set up SES:**
   - [ ] Verify sending domain (`news.<domain>`) in SES console
   - [ ] Add 3 DKIM CNAME records to Cloudflare DNS
   - [ ] Configure Custom MAIL FROM subdomain (`bounce.news.<domain>`) with MX + SPF TXT records
   - [ ] Add DMARC TXT record (`p=none` to start — monitor before enforcing)
   - [ ] Request production access (provide use case + volume plan)
   - [ ] Create SMTP credentials (IAM user with `ses:SendRawEmail`)
   - [ ] Set up SNS topic for bounce/complaint notifications (see 4-step SNS wiring above)

2. **Deploy Listmonk:**
   - [ ] Add Listmonk to `compose.yaml` (Go binary, Postgres DB on `postgres-main`, `fabrik` network)
   - [ ] Configure SMTP relay pointing to SES (`email-smtp.<region>.amazonaws.com:587`)
   - [ ] Configure bounce webhook endpoint to receive SNS notifications
   - [ ] Set up double opt-in for all lists
   - [ ] **Sanitize subscriber list before import:** scrub bounced, inactive (no open in 90+ days), and role-based addresses (`info@`, `admin@`). Importing a dirty list into a fresh SES account triggers early bounces that can get your account suspended before you build reputation.
   - [ ] Import cleaned subscriber list from Resend (CSV export → Listmonk import)
   - [ ] Upload MJML-compiled HTML templates

3. **Test before switching:**
   - [ ] Send test campaign to internal addresses
   - [ ] Verify `List-Unsubscribe` AND `List-Unsubscribe-Post` headers present (RFC 8058 one-click)
   - [ ] Verify bounce processing works (send to a known-bad address)
   - [ ] Verify DKIM/SPF/DMARC pass (check headers in received test email)
   - [ ] Check spam score (mail-tester.com or similar)

4. **Switch production sending:**
   - [ ] Ramp volume gradually — don't blast full list on day 1
   - [ ] Monitor SES reputation dashboard daily for first 2 weeks
   - [ ] Monitor bounce rate (< 5%) and complaint rate (< 0.1%)
   - [ ] Keep Resend Broadcasts active as fallback for 30 days

5. **Decommission Resend Broadcasts:**
   - [ ] After 30 days stable on Listmonk + SES, cancel Resend Broadcasts
   - [ ] Keep Resend transactional (3k/mo free) — separate stream, unchanged

### Cost Comparison

| Scenario | Resend Broadcasts | Listmonk + SES |
|---|---|---|
| 1,000 contacts, 1 domain | **$0** (free tier) | ~$5/mo container + ~$0.40/mo SES |
| 5,000 contacts, 2+ domains | **$40/mo** (Pro required) | ~$5/mo container + ~$2/mo SES |
| 20,000 contacts | **$40+/mo** (Pro + overage) | ~$5/mo container + ~$8/mo SES |
| 100,000 contacts | **Custom pricing** | ~$10/mo container + ~$40/mo SES |

**SES cost add-ons** (not in the base $0.10/1k rate): VDM +$0.07/1k if enabled, dedicated IP +$24.95/mo/IP if needed. **Turkey billing note:** AWS invoices in TRY with 20% KDV (VAT) on top — budget accordingly.

**Break-even:** Listmonk + SES is cheaper than Resend Pro ($40/mo) at any scale. The migration cost is your time to set it up (~2-4 hours). The trigger is more about capability (domains, contacts, control) than pure cost.

### AI Content Automation Loop

Your content AI plugs into the marketing pipeline — it generates, you approve:

```
Content AI → copy + segment + subject → MJML render → API push → ESP sends
                                                                      ↓
                                                        opens/clicks/conversions
                                                                      ↓
                                                          feedback to AI (tune next campaign)
```

**The automation flow (worker-based):**

1. **Generate:** content AI produces copy, subject line, preheader, and segment criteria per campaign
2. **Render:** worker loads MJML template + i18n strings, renders with Jinja2, produces localized HTML per recipient locale
3. **Review gate:** human approves via a one-click approve/reject interface — AI does the work, you press send. Keep this gate until trust is established.
4. **Send:** on approval, worker calls Resend Broadcasts API (or Listmonk API at scale) to dispatch
5. **Feedback loop:** opens, clicks, conversions flow back from ESP API → stored in PostgreSQL → fed to content AI for next campaign tuning

**Rules:**
- Content generation is a background job (per `75-workers-jobs.md`), not inline in an API handler.
- The human-approve gate is mandatory for all marketing sends. Never auto-send without approval.
- The feedback loop (opens/clicks → AI) is the differentiator — invest here, not in the sending tool.
- All guardrails from this pack apply: dedicated `news.<domain>` subdomain, SPF/DKIM/DMARC, one-click `List-Unsubscribe`, suppression, İYS consent gate for TR recipients.

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

**Turkey operational note:** İYS is a central registry — recording consent only in your own DB does not make you compliant for TR recipients. You must (a) sync each TR opt-in to İYS and (b) check the recipient's İYS status before sending, since they can revoke directly in İYS without telling you. İYS does not apply to transactional mail.

**İYS access model:** direct İYS API access requires 250,000+ consent records. Below that threshold (all early-stage projects), for API/programmatic access you must use a licensed İYS integrator ([listed at iys.org.tr/entegratorler](https://iys.org.tr/entegratorler)). A basic manual module exists (permission entry/query via the İYS website) for tiny senders who don't automate — irrelevant to Fabrik since we build automated, API-driven consent flows.

**The İYS integrator is a separate vendor from your ESP.** Resend, SES, and Listmonk are NOT İYS integrators — none of your sending stack touches İYS. The consent gate is a **standalone pre-send call** from your FastAPI backend to the integrator's API, independent of whichever ESP delivers the mail:

```
FastAPI backend → İYS integrator API (check consent) → if approved → ESP (Resend/SES) sends
```

**Two cost layers, not one:** (1) İYS's own İLETİ package fee, priced by address count, quoted KDV-exclusive; (2) the integrator's service fee on top. Budget both. <!-- Confirm integrator selection, İLETİ package tier, and both cost layers with your mali müşavir before committing. -->

---

## Stack Adapters (only the deltas)

### SaaS (FastAPI + Jinja2)

- Full pipeline as above. Transactional (signup, reset, receipts, alerts) + lifecycle (onboarding, nurture, dunning, win-back, expansion).
- **ESP:** transactional: **Resend** (3k/mo free, $20/50k, clean API; escalate critical auth mail — reset, receipts — to **Postmark** only on *measured* deliverability issues). Marketing/lifecycle: **Resend Broadcasts** (start) → **self-hosted Listmonk + SES** (at scale). See § Marketing ESP — Phased Strategy.
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
- [ ] Dark mode: `color-scheme` meta + `@media (prefers-color-scheme: dark)` overrides in brand partial; tested on Apple Mail + Outlook dark mode.
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

## Reusable Module

**Do not build email templates from scratch.** Vendor from `/opt/fabrik-lib/email-templates/`:

```bash
cp -r /opt/fabrik-lib/email-templates /opt/my-project/libs/email-templates
```

Ships 6 generic transactional templates (verification, password reset, welcome, email changed, account deleted, password reset confirmation), MJML+Jinja2 pipeline, brand partial with Ocoron tokens, i18n (English, add locales), `email_renderer.py` (framework-agnostic). See its README for env vars and build instructions.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Node in the runtime image | Compile MJML at build time; runtime is Python-only |
| Hand-coded HTML tables | MJML auto-emits tables + VML |
| External `<link>` stylesheets | MJML inlines all CSS at build |
| Background-image-dependent layout | Solid fills or VML via MJML |
| Customer email through Apprise | Resend (transactional) or Listmonk+SES (marketing). Apprise = internal/ops only |
| Missing plain-text part | `multipart/alternative` with plain-text always |
| Sending from the root domain | Dedicated subdomain (e.g. `mail.<domain>`) |
| Secrets/PII in push payloads | Deep link only; PII stays server-side |
| Per-template brand drift | ONE shared brand partial governs all templates |
| Uncompiled MJML shipped to runtime | Commit compiled `dist/` HTML; runtime loads compiled output |
| Email template without dark mode overrides | `color-scheme` meta + `@media (prefers-color-scheme: dark)` in shared brand partial |
| Resend React Email / JSX layer | Ignored — we use MJML+Jinja2 |
| Hardcoded strings in email templates | i18n JSON per locale (`emails/i18n/{locale}.json`) |
| Hardcoded date/number formats in emails | Locale-aware formatting via `babel` or equivalent |
| Mixing transactional + marketing on one stream | Separate streams (separate ESP config or subdomain) |
| Marketing email without `List-Unsubscribe` header | RFC 8058 one-click unsubscribe on every marketing email |
| Lifecycle sequences defined in application code | Define in marketing ESP (Resend Broadcasts or Listmonk) |
| "AI email marketing" SaaS (Mailchimp AI, etc.) | Your own content AI + commodity ESP — you own the engine |
| Mautic for campaign management | Listmonk (Go + Postgres, deploys via `fabrik apply`) |
| Sending marketing from VPS IP directly | Always via SES or Resend — protect domain reputation |
| Auto-sending marketing without human approval | One-click approve gate before every blast |
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
