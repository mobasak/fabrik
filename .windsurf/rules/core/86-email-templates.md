---
activation: glob
globs: ["**/emails/**", "**/*.mjml", "**/templates/*email*", "**/templates/*notification*", "**/push/**", "**/notifications/**", "**/email*", "**/mailer*", "**/notify*", "**/notification*"]
description: Email & template creation — MJML+Jinja2 pipeline, Resend/SES transport, push/in-app, deliverability, cross-cutting across SaaS/mobile/WordPress
trigger: glob
currency_pass: 2026-09-23
---
<!-- CONSUMER: Coding agents creating email/push/notification templates
     GOAL: MJML+Jinja2 pipeline, Resend/SES transport, deliverability, per-scaffold adapters
     TRAYCER USAGE: Injects as Context File for any ticket creating email/push templates.
     AGENT USAGE: Vendor the fabrik-lib modules first; follow the 5-step workflow. Author in MJML, compile, commit dist/, render at runtime. -->

# Email & Template Creation Rules (cross-cutting)

Apply to every ticket that creates or edits an **email, push notification, or in-app message template** in any saas / mobile / wordpress project. Follow verbatim; do not re-decide the stack per ticket.

---

## Reference Implementation — vendor, don't build

**Do not build email or push plumbing from scratch.** No scaffold type emits it (a `saas-skeleton`, `python-api` or `mobile-app` project gets no `emails/` tree), so every project vendors from fabrik-lib:

| Module | Vendor | What it gives you |
|---|---|---|
| `email-templates` | `cp -r /opt/fabrik-lib/email-templates <project>/libs/email_templates` (underscore — the hyphenated directory the module README shows cannot be imported) | The MJML → compiled-HTML pipeline (`build.py`), a zero-Node runtime renderer (`email_renderer.py`), ten transactional templates — `verification`, `passwordless`, `password_reset`, `password_reset_confirmation`, `welcome`, `email_changed`, `account_deleted`, and the DSAR/erasure notices `dsar_ack`, `dsar_extension`, `dsar_erasure_confirmation` — en i18n plus a `tr.json` scaffold whose strings are still `[TR]`-prefixed placeholders (translate before the first Turkish send), and an automatic plain-text part |
| `email-transport` | `cp -r /opt/fabrik-lib/email-transport <project>/libs/email_transport` | Two interchangeable `send_email(to_email, subject, html, plain_text=…, idempotency_key=…, to_name=…, tags=…)` transports: `resend_transport.py` (the default: simplest setup, native dedup) and `ses_transport.py` (stdlib-only SMTP, many verified identities) |
| `expo-push` | `cp -r /opt/fabrik-lib/expo-push/expo_push <project>/libs/expo_push` | Expo push-token registry + sender with receipt handling and dead-token pruning |

The module READMEs' **Gotchas are binding**. The ones that bite:
- **`build.py` compiles only its hardcoded `TEMPLATES` list** — a new `<name>.mjml` is skipped while the build still prints OK, and the render then raises `TemplateNotFound`. Add every new template's name to that list.
- **The renderer and `build.py` resolve `emails/` beside their own file** — the tree lives inside the vendored module (`libs/email_templates/emails/`), never at the repo root.
- **`dist/` is gitignored repo-wide** — force-add the compiled HTML (`git add -f libs/email_templates/emails/dist/*.html`) or every render raises jinja2 `TemplateNotFound`.
- **The build pins the MJML major the sources are written in.** The next MJML major is a breaking change — `mj-include` is ignored unless explicitly allowed, the minifiers changed, and the Node floor rose — so never compile these sources with a globally installed newer major.
- **Core renderers return `(html, text)`; the DSAR renderers return `(subject, html, text)`.** Get the interpolated subject with `render_subject()`, never the raw i18n JSON.
- **A DSAR `body=` override is compiled as a non-sandboxed Jinja2 template** — pass static reviewed copy only; user input there is SSTI/RCE.
- **URL variables must be built server-side** — Jinja escapes an `href` but does not validate its scheme; the verification/passwordless/reset renderers refuse a non-`http(s)` URL.
- **Brand values (`APP_NAME`, `APP_BASE_URL`, `APP_TAGLINE`) are read at import time** — set them before the first import.
- **The renderer stamps whatever locale you pass into `lang`, even when it falls back to `en` copy** — resolve the locale to a shipped one (`en`, or `tr` once translated) before calling it.
- **No RTL:** one compiled HTML per template, built `dir="auto"`, with no per-direction variant — see § Localized Email Rendering.
- **`send_email` never raises, and it is synchronous** — it returns `{"success": False, "error": …}` with no retry of its own, and it blocks for its socket timeout on each network step (10 s by default; SES reads `SES_SMTP_TIMEOUT`), so a call can take several multiples of it. Send from the job queue (`75-workers-jobs.md`) — never inline in an async route — and let the queue's retry budget be the ONE retry layer (`58-resilience.md`). The return carries no status code (filed upstream), so classify by the error text. **Terminal** — log it and dead-letter it: an error naming a missing setting (`… not configured`), the transport's own input refusal (`to_email must be exactly one address`), `SMTPRecipientsRefused`, `SMTPSenderRefused`, `SMTPAuthenticationError`, and any other SES error whose SMTP reply code is 5xx (`SMTPDataError: (554, …)`). A Resend error carries no code, so a permanent Resend 400/401/403/422 looks transient: it is retried to the job's budget and then dead-lettered — a stated exception to `58-resilience.md`'s no-retry-4xx rule until upstream returns the status. **Everything else is transient** — raise so the job retries with the same idempotency key, bounded by the job's retry budget. The transport also drops `Retry-After`, so a 429 retries on the queue's jittered backoff rather than the server's window — a stated exception to `58-resilience.md`'s Retry-After rule until upstream returns it. Only a send outside the queue (`asyncio.to_thread`) retries itself, with the same rules. Never edit the vendored file to add retries.
- **Vendored as a package, the transports' `.env` autoload is inert** — the flat `from _dotenv_email_transport import …` fails inside `libs.email_transport` and is swallowed, so a key held only in `.env` reads as unset. Put `RESEND_API_KEY`, `EMAIL_FROM_*` and `SES_SMTP_*` in the real process environment.
- **`ses_transport` speaks implicit TLS only** (`smtplib.SMTP_SSL`) — keep `SES_SMTP_PORT` at 465; 587 is for clients that STARTTLS, such as Listmonk.
- **Resend dedupes on the idempotency key; SES does not** (the SES key is a client-side correlation id only). An at-most-once send on SES needs a caller-side sent-ledger keyed on the business id.

---

## Mandated Stack (resolved — do not re-evaluate)

- **Structure/layout: MJML** (build-time, Node CLI). MJML emits the Outlook/Word conditional table layouts and the VML backgrounds itself; this is the entire reason it's mandated — never hand-code email HTML.
- **Variables/logic: Jinja2** placeholders embedded in MJML via `<mj-raw>{% ... %}</mj-raw>` and `{{ var }}`. MJML's own docs name `mj-raw` as the templating pass-through, and warn that minification can choke on template syntax — check the compiled output after any build-flag change. Runtime is **framework-agnostic `jinja2`** (works in FastAPI or Flask). **No Node in the runtime image.**
- **Brand: Ocoron Design System** tokens (colors, fonts) set as `<mj-attributes>` defaults in ONE shared partial (`partials/brand.mjml`). Atelier Rebul brand kept separate, never co-branded.
- **Sending: `email-transport`.** Resend by default (transactional); the SES transport when you need more verified sending domains than your Resend plan includes (the transport README's "one domain" predates Resend's three-domain free plan — reported upstream). Send the compiled HTML — **ignore Resend's React Email/JSX layer** (you use MJML+Jinja2; it's irrelevant). Keep **transactional** and **marketing** on separate streams. Escalate critical auth mail to Postmark only on *measured* deliverability issues.
- **Internal/ops alerts: Apprise** (already deployed) — for system/ops notifications ONLY, never customer email.

---

## The Workflow (fast path — 5 steps)

1. **Author** `<name>.mjml` with Jinja2 placeholders; pull header/footer/brand from shared partials via `<mj-include>`.
2. **Compile** with the module's `build.py` (it flattens the includes and runs the pinned MJML major) to `emails/dist/<name>.html`. Build-time only.
3. **Commit the compiled `dist/` HTML** (`libs/email_templates/emails/dist/`) — force-added, since `dist/` is gitignored (deterministic, keeps runtime Python-only — no build-stage Node required on the VPS).
4. **Render at runtime**: Python loads the compiled HTML, Jinja2 fills variables, the renderer produces the plain-text alternative (`multipart/alternative`), the transport sends it.
5. **Test before ship**: render to test inboxes (Apple Mail / Gmail / classic Outlook for Windows / dark mode) — Litmus/Email-on-Acid if available, manual test inboxes otherwise.

---

## Repo Contract

The tree lives inside the vendored module — its code resolves it relative to itself:

```
libs/email_templates/emails/
  src/         <name>.mjml                # source of truth (committed)
  partials/    header|footer|brand.mjml   # mj-include; brand tokens live here ONLY
  dist/        <name>.html                # compiled, force-added; what runtime loads
  i18n/
    en.json                              # English strings (source of truth)
    tr.json                              # Turkish strings
```

One brand partial governs all templates — no per-template colour/font drift. One i18n JSON per locale governs all localized strings.

---

## Core Rules (MUST — universal)

### Rendering Fidelity

- Classic Outlook for Windows renders with the Word engine — rely on MJML's table+VML output; never assume flexbox/grid. The new Outlook for Windows renders with WebView2 (web engine), so test both while both are in use.
- **CSS placement:** MJML writes each component's styling inline by construction, but an `<mj-style>` block goes to `<head>` unless you mark it `inline="inline"`. Put anything a stripping client must see in `mj-attributes` or an inlined `mj-style`. No external `<link>` stylesheets.
- No layout that depends on CSS `background-image` (classic Outlook drops it) — use solid fills, or MJML's `background-url`, which emits the VML fallback.
- Keep final HTML **under ~102 KB** — Gmail clips beyond it. The figure is measured by ESPs, not published by Google, and counts the HTML/text, not linked image weight.

### Dark Mode

- `<meta name="color-scheme" content="light dark" />` and `<meta name="supported-color-schemes" content="light dark" />` in the shared brand partial — mandatory.
- `@media (prefers-color-scheme: dark)` overrides for background, text, and subtext colors, for the clients that honour it.
- **Never rely on automatic inversion, and never rely on the media query alone for legible contrast** — Gmail, Yahoo and AOL do not apply it, and classic Outlook honours neither mechanism. Choose base colours that stay readable when a client inverts or forces its own palette.
- Test dark mode on Apple Mail (iOS) and on new Outlook / Outlook.com (the client that inverts) before shipping any new template; classic Outlook for Windows is the base-colour legibility check, not a dark-mode test.

**Dark-mode support (source: caniemail.com, `html-meta-color-scheme` and `css-at-media-prefers-color-scheme`):**

| Client | Engine | `color-scheme` meta | `@media (prefers-color-scheme)` |
|---|---|---|---|
| Apple Mail (macOS/iOS) | WebKit | Yes | Yes |
| Gmail (web/Android/iOS) | Custom | Partial — only `light` is honoured | No |
| Outlook for Windows (classic) | Word | No | No |
| Outlook.com / new Outlook / Windows Mail | Web | Yes | No — it exposes proprietary `data-og*` attributes instead, and inverts white/black it was not told about |
| Yahoo! Mail / AOL | Custom | No | No — the query is rewritten to a filtered no-op |
| Samsung Email | WebKit | Yes | Yes |
| Thunderbird | Gecko | Yes | Yes |

### Deliverability (set-and-forget, pro-grade)

- Sending domain has **SPF + DKIM + DMARC** (configure via Cloudflare DNS). Gmail, Yahoo and Outlook.com all require all three once a domain sends more than about **5,000 messages a day** to them, with DMARC at least `p=none` and the `From:` domain aligned with SPF **or** DKIM; below that threshold SPF or DKIM is the floor. Non-compliant bulk mail is rejected or junked (Outlook.com junks first).
- Keep the spam rate Google and Yahoo report **below 0.3%**; valid forward and reverse DNS (PTR) and TLS on the sending path are required of every sender.
- Send from a **dedicated subdomain** (e.g. `mail.<domain>`), never the root domain — house practice for reputation isolation, not a mailbox-provider mandate. A subdomain does not escape the bulk threshold: its volume counts toward the organisational domain.
- **One-click unsubscribe (RFC 8058) on all marketing mail** — an `https` `List-Unsubscribe` URI plus `List-Unsubscribe-Post: List-Unsubscribe=One-Click`, both covered by the DKIM signature, plus a visible unsubscribe link in the body. Honour an unsubscribe within **48 hours**. Gmail and Yahoo require it of bulk senders; Outlook.com recommends a working unsubscribe without mandating RFC 8058 — send it everywhere. Transactional mail is exempt.
- ESP bounce/complaint webhooks to auto-suppress. No sending to suppressed addresses.

### Accessibility & Content

- Mandatory **plain-text alternative** for every email (deliverability + a11y).
- `lang` set (the renderer rewrites MJML's `lang="und"` to the send locale); layout tables `role="presentation"`; every image has `alt`; AA contrast.
- **Preheader** text on every email; descriptive subject.
- Absolute `https://` image URLs (Backblaze B2 / Cloudflare CDN); retina-ready.

### 12-Factor / Docker

- Compilation is build-time; **runtime image stays the Python base image of `30-ops.md` (`python:*-slim-<!--v:debian_codename-->trixie<!--/v-->`), linux/amd64, zero Node**.
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

The `libs/email_templates/emails/i18n/` layout is the Repo Contract above — one JSON per locale, structure language-agnostic.

### Rendering Flow

```python
from libs.email_templates.email_renderer import render_welcome, render_subject
from libs.email_transport.resend_transport import send_email
from app.email_errors import is_terminal, TransientSendError   # yours: the classifier rule above

SHIPPED = {"en"}                                  # add "tr" once tr.json is translated
locale = user.locale if user.locale in SHIPPED else "en"   # the renderer stamps what you pass
subject = render_subject("welcome", {"display_name": user.name}, locale)
html, text = render_welcome(user.name, tier_name=user.plan_name,      # defaults are "Free" / 0
                            credits_per_month=user.credits, locale=locale)
result = send_email(user.email, subject, html, plain_text=text,
                    idempotency_key=f"welcome-{user.id}")
if not result["success"]:
    if is_terminal(result["error"]):                 # missing setting, input refusal, SES 5xx
        log.error("email_send_failed", template="welcome", error=result["error"])
    else:
        raise TransientSendError(result["error"])    # the job queue retries it
```

Run this in a job-queue worker — the raise hands a transient failure to the queue's retry (the one retry layer); `is_terminal` and `TransientSendError` are the project's own few lines implementing the classifier rule in § Reference Implementation — vendor, don't build; no vendored module ships them.

### Rules

- **English is the source-of-truth locale.** All other locales derive from `en.json`.
- **Every user-visible string in the email body comes from the i18n JSON** — never hardcoded in the MJML template. The MJML template uses Jinja2 `{{ variables }}` that resolve to localized strings.
- **Subject lines are localized** — they live in the i18n JSON, not in application code.
- **Fallback:** if the user's locale has no translation file, fall back to `en`. Never send an empty or broken template.
- **Date/time/number formatting:** use `Intl`-style locale-aware formatting in the rendering code (Python `babel` or manual locale dispatch). Never hardcode `MM/DD/YYYY` or `$1,000.00`.
- **RTL support:** the vendored module has none — it compiles one HTML per template with `dir="auto"`, and MJML takes `dir` from the root `<mjml>` tag at build time (`direction="rtl"` on an `<mj-section>` only reorders columns). An `ar`/`fa` locale needs a direction variant wired through the build and `render_email` — file it upstream (fabrik-lib) before shipping such a locale.

---

## Newsletters & Marketing Email

### Two Streams — Never Mix

| Stream | Purpose | ESP | Unsubscribe | Sending domain |
|---|---|---|---|---|
| **Transactional** | Signup, reset, receipts, alerts, dunning | Resend, or the SES transport (escalate to Postmark) | Not required (operational) | `mail.<domain>` |
| **Marketing** | Newsletters, product updates, lifecycle (onboarding, nurture, win-back, expansion) | Resend Broadcasts → self-hosted Listmonk + SES at scale | **Mandatory** (RFC 8058 one-click) | `news.<domain>` (dedicated marketing subdomain) |

**Why separate streams:** mixing transactional and marketing on the same sending identity lets marketing complaints (spam reports) degrade transactional deliverability (password resets landing in spam). Separate streams isolate reputation.

### Transactional Email Template Inventory

Every project must ship these transactional templates before go-live. Check the column that matches your project type. The `email-templates` module already ships the rows marked ★ plus the three DSAR notices.

#### Auth & Account (all project types)

**Pattern A (default) — the app owns auth email natively.** With `fabrik-lib/fastapi-user-auth` (Pattern A, the default per `agents-fabrik.md § Supabase`), FastAPI issues its own JWTs and triggers verify-email, passwordless and password-reset emails directly through **this MJML+Jinja2 pipeline**. Every auth email is brand-correct, localized, and version-controlled in the repo by construction. Send via the transport on your authenticated subdomain like any other transactional mail.

**Legacy — a project still on Supabase Auth (Pattern B)** (an ADR-recorded exception only): disable Supabase's built-in auth emails and route them through this pipeline (Auth Hooks, or custom SMTP pointed at your authenticated subdomain) until it migrates to Pattern A.

| Template | Trigger | SaaS | Mobile | WP | Notes |
|---|---|---|---|---|---|
| **Verify email** ★ | Signup / email change | Yes | Yes | Yes | Verification token link. House target: expires in 24h (your token store enforces it). |
| **Passwordless sign-in** ★ | User asks for a sign-in code | Yes | Yes | — | One-time code + magic link from `fastapi-user-auth`'s `/passwordless/*`; the pending login lives `passwordless_code_ttl_s` (5 min by default). |
| **Welcome** ★ | Email verified | Yes | Yes | Yes | Confirms account is active. Links to first action / onboarding. |
| **Password reset request** ★ | User clicks "forgot password" | Yes | Yes | Yes | Reset token link. House target: expires in 1h. Never confirm whether email exists. |
| **Password reset confirmation** ★ | Password successfully changed | Yes | Yes | Yes | Informational — no action needed. Includes "if this wasn't you" warning. |
| **Email changed** ★ | User updates email in settings | Yes | Yes | — | Sent to OLD email as security alert. |
| **Account deleted** ★ | User deletes account | Yes | Yes | — | Confirms deletion. Notes data retention period if applicable. |

#### Billing & Subscription

| Template | Trigger | SaaS | Mobile | WP | Notes |
|---|---|---|---|---|---|
| **Payment receipt** | Successful payment (payment-provider webhook / RevenueCat) | Yes | Yes | Woo | Amount, plan, next billing date, invoice link. |
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
- Every template has an MJML source in `libs/email_templates/emails/src/`, compiled to `emails/dist/` beside it, localized via `emails/i18n/`.
- Every template has a plain-text alternative.
- Auth-critical emails (verify, reset) should use the Postmark escalation path if deliverability issues are measured.
- Dunning emails are triggered by payment-provider webhooks (the payments module's entitlement events — `85-payments-billing.md`; RevenueCat on mobile), not by application schedulers. #2 and #3 key off the provider's retry fields where it exposes them; where it does not, a grace-period timer started by the `payment_failed` event is the permitted source.
- "If this wasn't you" links go to a session-review or password-reset page, never to a generic support form.

### Newsletter Architecture

- **List management:** users opt-in during signup or via a preference center. Opt-in state stored in PostgreSQL (`email_preferences` table or user profile). Double opt-in required for EU recipients (§ Marketing Consent & Compliance).
- **Preference center:** accessible from user settings AND from the email footer. Users can: toggle per-category (product updates, tips, announcements), change frequency (weekly/monthly digest), or unsubscribe entirely.
- **Unsubscribe:** one-click `List-Unsubscribe` header (RFC 8058) on every marketing email, plus the visible body link (§ Deliverability) — the header is the primary mechanism, the footer link its required companion.
- **Frequency control:** respect user's preference. Default: weekly digest. Never send more than the user chose.
- **Suppression:** honor ESP bounce/complaint webhooks. Auto-suppress bounced and complained addresses. Never re-add a suppressed address without explicit re-opt-in.

### Marketing Email Templates

Same MJML pipeline as transactional — author in MJML, compile, commit, render with Jinja2, localize per user. Additional rules:

- **Preheader is mandatory** — it's the first thing users see in their inbox after the subject.
- **Single CTA per email** — one primary action button. Secondary links as text only.
- **Footer must include:** unsubscribe link, preference center link, company name + address (CAN-SPAM), "why you received this" explanation.
- **No tracking pixels** in operator-facing emails (trust). Tracking pixels acceptable in marketing emails to external subscribers with consent.
- **Send time:** default Tuesday-Thursday, 9-11am in the audience's main timezone. Per-recipient local-time sending needs segmenting by timezone — Listmonk schedules a campaign at one instant for every subscriber.

### Lifecycle Email Sequences

Define in the marketing ESP, not in application code — Resend's automations while you are on Resend. Listmonk has no drip engine: at that scale a worker fires each step through Listmonk's API, with the copy in Listmonk templates and the step schedule in config or the database, never in code. Mail the worker sends adds the one-click unsubscribe headers and checks subscription and İYS status per message, exactly as an app-dispatched send does. Push re-engagement triggers (`00-domain-mobile-app.md`) run in the backend through `expo-push`:

| Sequence | Trigger | Emails | Goal |
|---|---|---|---|
| **Onboarding** | Signup | 3-5 over 7 days | Activation (user completes core action) |
| **Nurture** | Activated but low usage | 2-3 over 14 days | Feature discovery, depth |
| **Win-back** | Churned (cancelled 30+ days) | 1-2 over 30 days | Re-engagement |
| **Expansion** | High usage near plan limit | 1-2 triggered | Upgrade |

- All sequences are **localized** per user locale.
- All sequences **stop** on unsubscribe or successful conversion.
- **Dunning is transactional, not a lifecycle sequence** — it is sent on the transactional stream, driven by the payment provider's retry events (`85-payments-billing.md`; RevenueCat on mobile) or the grace-period timer permitted under § Transactional Email Template Inventory, and never waits on marketing consent or the ESP's scheduler.

### Marketing ESP — Phased Strategy

The sender is a commodity. Your edge is the content AI, not the sending tool. Don't buy "AI email marketing" SaaS (you'd pay for a worse content engine than the one you already own), and don't build a campaign engine from scratch.

| Phase | Tool | When | Cost model |
|---|---|---|---|
| **Now** | **Resend Broadcasts** | Start here — you already run Resend for transactional; it sends the RFC 8058 one-click headers itself | Priced by contacts, not sends: free up to 1,000 contacts, then $40/mo for 5,000 |
| **At scale** | **Self-hosted Listmonk + Amazon SES** | When the Resend contact fee exceeds the container + SES per-email cost | Listmonk: flat (Go + Postgres, AGPL, deploys via `fabrik apply`, zero per-contact fee). SES: per 1,000 emails — see § SES pricing |
| **WordPress** | **FluentCRM** | WordPress/Woo projects only | Self-hosted, no per-contact fee |

**Migration triggers** (Resend → Listmonk):
- Contact fee exceeds the ~$5-10/mo container + SES per-email cost.
- More than 1,000 contacts (the Resend marketing free tier).
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
- **SES** is the delivery layer only — your VPS IP never touches the recipient's mail server. SES sends from **Amazon's shared IP pool** by default. A dedicated IP ($24.95/mo per IP) only when you can keep sending around **1,000 emails a day to each major mailbox provider** — AWS's own figure for holding a dedicated IP's reputation; below that, the shared pool performs better.
- **Listmonk connects to SES via the SMTP interface** (`email-smtp.<region>.amazonaws.com`, STARTTLS on 587 or implicit TLS on 465). Core Listmonk has no SES-API sender; the separately maintained `listmonk-messenger` plugin adds one. The sending rate is one per-account SES quota whichever interface you use — the API is not faster.
- **Bounce/complaint handling:** SES bounce and complaint notifications flow via **SNS → Listmonk webhook**. This is a 4-step setup — without it, you re-send to bounced addresses and SES reviews and then pauses your account:
  1. Create an SNS topic (e.g. `ses-bounces-complaints`) in the same region as SES.
  2. In SES → Verified identity → Notifications tab, assign this SNS topic to **Bounces** and **Complaints** notification types (a configuration-set event destination is the equivalent per-stream alternative).
  3. Create an HTTPS subscription on the SNS topic pointing to Listmonk's bounce webhook endpoint (`https://listmonk.yourdomain/webhooks/service/ses`).
  4. Confirm the subscription (SNS sends a confirmation request to the endpoint — Listmonk confirms it if reachable).

### SES Setup & Domain Authentication

**Domain verification (one-time per sending domain):**

1. Add `news.<domain>` as a verified identity in SES console.
2. SES generates 3 CNAME records (DKIM) — add to Cloudflare DNS.
3. **Custom MAIL FROM subdomain** (required for SPF alignment): set `bounce.news.<domain>` as the MAIL FROM domain in SES. Add two DNS records to Cloudflare:
   - `bounce.news.<domain>` MX → `feedback-smtp.<region>.amazonses.com` (priority 10)
   - `bounce.news.<domain>` TXT → `"v=spf1 include:amazonses.com ~all"`
   Without Custom MAIL FROM, the envelope sender is `amazonses.com` — SPF passes for Amazon's domain, not yours, causing DMARC SPF alignment to fail. DKIM alone can carry DMARC, but both-aligned is best practice.
4. DMARC: add `_dmarc.news.<domain> TXT "v=DMARC1; p=none; rua=mailto:dmarc@<domain>"`. **Start with `p=none`** (monitoring only). Google's rollout guidance: about a week of `p=none` reports, then `p=quarantine` on a small percentage, ramped up, then `p=reject` once the reports show only your own streams failing. `p=none` is a transitional state, not a destination.
5. **Same subdomain works across ESPs.** Switching from Resend to SES = update the DKIM/SPF DNS records. Domain reputation transfers — it's tied to the domain, not the ESP.

**SES Sandbox → Production:**

- New SES accounts start in **sandbox**: at most **200 messages per 24 hours** and **1 message per second**, only to verified addresses and domains. Request production access via the AWS console — provide your use case, expected volume, bounce/complaint handling plan.
- Production access is required before sending to unverified recipients. AWS commits to an initial response within 24 hours; full approval often takes longer.

**SES sending limits:**

- After production access, the daily quota and sending rate depend on your use case (50,000/day is a common starting grant) and grow with your sending history. Read yours with `GetSendQuota`.
- **Review vs pause:** a bounce rate of **5%** or a complaint rate of **0.1%** puts the account under review; **10%** bounces or **0.5%** complaints can pause sending. Treat the review thresholds as your ceiling. Monitor via the SES reputation dashboard.
- Message size: **40 MB** per message through SMTP or the current API, **50 recipients** per message.
- **Virtual Deliverability Manager (VDM):** deliverability insights, ISP-level metrics and DKIM/DMARC recommendations. An add-on under à la carte pricing ($0.07 per 1,000 emails plus a query fee), included on the higher plans. Not required at low volume; consider it at 50k+/month when you need ISP-level visibility.

### SES pricing

AWS moved SES to plans on **21 July 2026**: new accounts, and account/region pairs with no SES activity since 1 June 2025, start on **Essentials at $0.16 per 1,000 emails** (first 10M/month); Pro and Enterprise cost more per email plus a monthly fee. The **à la carte** rate is **$0.10 per 1,000 emails** plus $0.12 per GB of attachments. Check which one your account is on before estimating. **Turkey billing note:** AWS Turkey invoices Turkish accounts in TRY with 20% KDV (VAT) on top — budget accordingly.

### Listmonk Built-in Features

| Feature | Listmonk support | Notes |
|---|---|---|
| Double opt-in | ✅ Native | Configurable per list |
| `List-Unsubscribe` header | ✅ Native RFC 8058 | Settings → Privacy → "Include `List-Unsubscribe` header" sends both `List-Unsubscribe` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click`, and the unsubscribe endpoint accepts the POST. Turn it on — it is the setting, not custom headers. |
| Bounce/complaint processing | ⚠️ Requires SNS wiring | SES → SNS topic → Listmonk webhook endpoint |
| Subscriber segments | ✅ Native | SQL expressions |
| Campaign scheduling | ✅ Native | One send instant per campaign — not per-subscriber local time, and no drip/automation engine |
| Template system | ✅ Native | HTML templates — feed MJML-compiled output |
| Analytics (opens/clicks) | ✅ Native | Driven by tracking tags in the template; Settings → Privacy → individual subscriber tracking decides whether events are tied to a subscriber. Remove the tags to disable tracking entirely. |
| API | ✅ Full REST API | Campaign creation, subscriber management, send triggers, plus a transactional-message endpoint |
| Multiple sending domains | ✅ Named SMTP servers | Pick an SMTP server per campaign |

### Migration Checklist (Resend → Listmonk + SES)

Execute in this order:

1. **Set up SES:**
   - [ ] Verify sending domain (`news.<domain>`) in SES console
   - [ ] Add 3 DKIM CNAME records to Cloudflare DNS
   - [ ] Configure Custom MAIL FROM subdomain (`bounce.news.<domain>`) with MX + SPF TXT records
   - [ ] Add DMARC TXT record (`p=none` to start — monitor before enforcing)
   - [ ] Request production access (provide use case + volume plan)
   - [ ] Create SMTP credentials (IAM user limited to `ses:SendRawEmail`)
   - [ ] Set up SNS topic for bounce/complaint notifications (see 4-step SNS wiring above)

2. **Deploy Listmonk:**
   - [ ] Add Listmonk to `compose.yaml` (Go binary, Postgres DB on `postgres-main`, `fabrik` network)
   - [ ] Configure SMTP relay pointing to SES (`email-smtp.<region>.amazonaws.com`, 587 STARTTLS or 465 TLS)
   - [ ] Configure bounce webhook endpoint to receive SNS notifications
   - [ ] Turn on Settings → Privacy → "Include `List-Unsubscribe` header"
   - [ ] Set up double opt-in for all lists
   - [ ] **Sanitize subscriber list before import:** scrub bounced, inactive (no open in 90+ days), and role-based addresses (`info@`, `admin@`). Importing a dirty list into a fresh SES account triggers early bounces that can put the account under review before you build reputation.
   - [ ] Import cleaned subscriber list from Resend (CSV export → Listmonk import)
   - [ ] Upload MJML-compiled HTML templates

3. **Test before switching:**
   - [ ] Send test campaign to internal addresses
   - [ ] Verify `List-Unsubscribe` AND `List-Unsubscribe-Post` headers present (RFC 8058 one-click), and that the unsubscribe URL accepts a POST
   - [ ] Verify bounce processing works (send to the SES mailbox simulator's bounce address)
   - [ ] Verify DKIM/SPF/DMARC pass (check headers in received test email)
   - [ ] Check spam score (mail-tester.com or similar)

4. **Switch production sending:**
   - [ ] Ramp volume gradually — don't blast full list on day 1
   - [ ] Monitor SES reputation dashboard daily for first 2 weeks
   - [ ] Keep bounce rate under 5% and complaint rate under 0.1% (the review thresholds)
   - [ ] Keep Resend Broadcasts active as fallback for 30 days

5. **Decommission Resend Broadcasts:**
   - [ ] After 30 days stable on Listmonk + SES, cancel Resend Broadcasts
   - [ ] Keep Resend transactional — separate stream, unchanged

### Cost Comparison

Resend Broadcasts is priced by contacts; Listmonk + SES by container plus emails sent. Price the SES side on your account's actual plan (§ SES pricing) and your real send volume — contacts × sends per month × the per-1,000 rate — against Resend's contact tier on the day you decide. **The trigger is more about capability (contacts, domains, control) than pure cost**; the migration costs your time to set it up (~2-4 hours).

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
3. **Review gate:** human approves via a one-click approve/reject interface — AI does the work, you press send. Approve each campaign, and each lifecycle sequence's copy once; the ESP's automated sends of an approved sequence need no per-send approval — the copy is fixed once approved and only its trigger fires, so a per-send gate would approve the same text again.
4. **Send:** on approval, worker calls Resend Broadcasts API (or Listmonk API at scale) to dispatch
5. **Feedback loop:** opens, clicks, conversions flow back from ESP API → stored in PostgreSQL → fed to content AI for next campaign tuning

**Rules:**
- Content generation is a background job (per `75-workers-jobs.md`), not inline in an API handler.
- The human-approve gate is mandatory for every campaign and for every sequence's copy before it goes live. Never auto-send unapproved content.
- The feedback loop (opens/clicks → AI) is the differentiator — invest here, not in the sending tool.
- All guardrails from this pack apply: dedicated `news.<domain>` subdomain, SPF/DKIM/DMARC, one-click `List-Unsubscribe`, suppression, İYS consent gate for TR recipients.

### Marketing Consent & Compliance

**Scope:** applies to marketing / lifecycle email only (newsletters, product updates, onboarding, nurture, win-back, expansion). Transactional email is exempt — operational, not commercial messaging, no marketing consent required. This is another reason the two run on separate streams.

**Principle:** consent obligations follow the **recipient's jurisdiction**, not the sender's location. Operating from Turkey does not exempt mail sent to EU or other recipients.

**Default for all recipients: opt-in.** Require explicit opt-in before any marketing send, regardless of recipient country — the strictest standard, satisfies every regime below with one rule and no jurisdiction branching.

| Recipient jurisdiction | Rule | System of record |
|---|---|---|
| **Turkey** | İYS (İleti Yönetim Sistemi): consent for _ticari elektronik ileti_ must be registered in and checked against İYS before every send; a consent not registered in İYS is invalid. Your own opt-in record is not sufficient. | İYS registry |
| **EU / EEA** | GDPR / ePrivacy: explicit (double) opt-in, documented, withdrawable. | Consent DB (`email_preferences`) |
| **US** | CAN-SPAM: opt-out minimum (honest headers, physical address, working unsubscribe). Opt-in default already exceeds this. | Consent DB |
| **Everywhere else** | Opt-out floor (working unsubscribe + suppression). Opt-in default already exceeds this. | Consent DB |

**Universal — all recipients, all jurisdictions:**

- One-click `List-Unsubscribe` (RFC 8058) on every marketing email.
- Honour an unsubscribe within the 48-hour house window (§ Deliverability) and bounce/complaint suppression at once; never re-add an address suppressed for unsubscribe, bounce or complaint without explicit re-opt-in.
- Footer: unsubscribe link, preference center, company name + address, "why you received this."

**Turkey operational rules (Ticari İletişim ve Ticari Elektronik İletiler Hakkında Yönetmelik):**

- **Register and check:** a consent collected outside İYS is registered there within **3 business days**, and the recipient's İYS status is checked before sending — they can revoke directly in İYS without telling you.
- **Stop within 3 business days** of an opt-out.
- **B2B (tacir/esnaf) recipients** need no prior consent, but their addresses must still be registered in İYS and checked for an opt-out before sending.
- **Transactional exemption:** messages about an ongoing subscription, membership, collection, purchase or delivery need no consent and no İYS check — **only while they promote nothing**. A promotional line inside a receipt makes it commercial.
- **Keep consent records for 3 years** after the consent lapses, and other message records for 3 years from the record date.

**İYS access model:** a service provider with fewer than **250,000** contact addresses reaches the İYS API (İLETİ services) only through an authorised **integrator**. Since the 2024 communiqué, integrators are companies authorised by the Ministry of Trade; partners who were not re-authorised lost that status on 30 June 2025, so choose from İYS's current partner list (`iys.org.tr/is-ortaklari`), not from an older list. The free basic module (manual permission entry and query on the İYS website) exists for tiny senders who don't automate — irrelevant to Fabrik since we build automated, API-driven consent flows.

**The İYS integrator is a separate vendor from your ESP.** Resend, SES, and Listmonk are NOT İYS integrators — none of your sending stack touches İYS. The consent gate is a **standalone pre-send call** from your FastAPI backend to the integrator's API, independent of whichever ESP delivers the mail:

```
FastAPI backend → İYS integrator API (check consent) → if approved → ESP (Resend/SES) sends
```

That per-message call covers app-dispatched sends. A campaign or sequence the ESP dispatches from its own list has no per-message hook, so **before each scheduled send, and at least daily for sequences, a job reconciles every TR contact's İYS status into the ESP**: anyone not currently `ONAY` is excluded under a distinct İYS reason (pending or `RET`) that the job lifts when İYS returns `ONAY`, and the send's segment excludes them. The re-opt-in rule covers unsubscribe, bounce and complaint suppressions, not this İYS exclusion.

**Two cost layers, not one:** (1) İYS's own İLETİ package — an annual fee by address-count tier, quoted KDV-exclusive, with the two smallest tiers free; (2) the integrator's service fee on top. Budget both. <!-- Confirm integrator selection, İLETİ package tier, and both cost layers with your mali müşavir before committing. -->

---

## Stack Adapters (only the deltas)

### SaaS (FastAPI + Jinja2)

- Full pipeline as above. Transactional (signup, reset, receipts, alerts, dunning) + lifecycle (onboarding, nurture, win-back, expansion).
- **ESP:** transactional: **Resend** via `email-transport` (escalate critical auth mail — reset, receipts — to **Postmark** only on *measured* deliverability issues; the SES transport when you need more sending domains). Marketing/lifecycle: **Resend Broadcasts** (start) → **self-hosted Listmonk + SES** (at scale). See § Marketing ESP — Phased Strategy.
- Dunning/entitlement emails are driven by payment-provider webhooks (`85-payments-billing.md`).

### Mobile (python-api backend + push + in-app)

- **Email = the SAME backend pipeline** (the app's transactional mail comes from python-api — reuse, don't rebuild).
- **Push templates** are a separate surface: the vendored `expo-push` module on the **Expo push service** is the push sender (`80-mobile.md` § Push Notifications owns the client side; `00-domain-mobile-app.md` still names OneSignal as an alternative — reconciled at that pack's turn). One Expo call reaches APNs and FCM; Android needs a **Firebase service-account key uploaded to EAS** (the legacy FCM server key no longer works). Rules: title+body **localized (en+tr)**, `data` payload carries the **deep link** (Universal/App Link via ChottuLink — ties to mobile attribution stack), **no PII in payload**, respect opt-in, total payload **at most 4 KiB**.
- **Push failures:** unlike `send_email`, `PushClient.send` raises `PushServerError`, and a send of more than 100 messages is not atomic across its chunks — send from a job, retry at the job layer, and expect duplicates. The module does not enforce the 4 KiB limit: check `len(json.dumps(payload).encode()) <= 4096` before sending.
- **Push limits and hygiene:** at most 100 messages per send request and 600 notifications per second per project; tickets mean "accepted by Expo", receipts (fetched later, at most 1,000 ids per request, cleared after 24 hours) are the delivery truth; delete a token on a `DeviceNotRegistered` error.
- **In-app messages** templated + localized; prefer RevenueCat paywalls/messages over a custom system (set-and-forget).
- Push copy is short; email carries the detail.

### WordPress (Woo / ESP — NOT Jinja2)

- **MJML stays the design source of truth**, but output is consumed differently — **no Jinja2 at runtime**.
- Compiled HTML feeds either **WooCommerce email template overrides** (in a child theme or mu-plugin) or the **ESP/newsletter tool**; variables via **WP/Woo merge tags or ESP merge tags**, not `{{ }}`.
- **Marketing/newsletter default:** FluentCRM (self-hosted, no per-contact fee, set-and-forget). Transactional WP mail via a reputable SMTP plugin pointed at the **same ESP + same authenticated subdomain**.
- Same SPF/DKIM/DMARC + List-Unsubscribe rules apply.

---

## Acceptance Criteria (gates)

- [ ] (non-WP) `email-templates` / `email-transport` (and `expo-push` on mobile) vendored from fabrik-lib, not rebuilt.
- [ ] Template authored in MJML; no hand-coded email HTML.
- [ ] Brand pulled from the shared partial; no inline brand values.
- [ ] Compiled `dist/` HTML committed (force-added); runtime loads compiled output (or Woo/ESP consumes it).
- [ ] (non-WP) Every `send_email` result is checked; a failure is logged and retried from the caller, never dropped; sends run off the request path.
- [ ] Plain-text alternative present.
- [ ] Preheader, `alt` text, AA contrast, `lang` set.
- [ ] HTML under ~102 KB.
- [ ] Sending domain has SPF + DKIM + DMARC on a dedicated subdomain.
- [ ] Rendered/tested on Apple Mail + Gmail + classic Outlook for Windows + dark mode.
- [ ] Dark mode: `color-scheme` meta + `@media (prefers-color-scheme: dark)` overrides in brand partial; base colours legible where neither is honoured; tested on Apple Mail + new Outlook / Outlook.com.
- [ ] Runtime image contains no Node; keys via env.
- [ ] (Mobile) push payload localized, deep-linked, PII-free, under 4 KiB; dead tokens pruned from receipts.
- [ ] (WP) consumed via Woo override / ESP with correct merge tags.
- [ ] All transactional templates from the inventory exist for the project type (auth, billing, team, system).
- [ ] (non-WP) Email i18n: `libs/email_templates/emails/i18n/en.json` exists; before `tr` joins the shipped locales, `tr.json` carries no placeholder (`grep -c '\[TR\]' libs/email_templates/emails/i18n/tr.json` = 0); all user-visible strings come from i18n JSON, not hardcoded in MJML.
- [ ] (WP) Strings localized through WP `.po`/`.mo` files or the ESP's locale fields.
- [ ] Subject lines localized per user locale.
- [ ] Fallback to `en` when user's locale has no translation file.
- [ ] Marketing emails on a separate stream from transactional (separate ESP config or subdomain).
- [ ] One-click `List-Unsubscribe` (RFC 8058) header, DKIM-covered, plus a visible body link on every marketing email; unsubscribes honoured within 48 hours.
- [ ] Preference center accessible from user settings AND email footer.
- [ ] Lifecycle sequences (onboarding, nurture, win-back, expansion) defined in the marketing ESP (Resend automations) or, on Listmonk, fired by a worker whose schedule lives in config or the database; dunning sent on the transactional stream.
- [ ] Marketing send requires opt-in consent for every recipient (universal opt-in default).
- [ ] TR recipients' consent registered/checked in İYS before send (ESP-dispatched sends via the pre-send reconcile); opt-outs honoured within the 48-hour house window — the İYS 3-business-day bound is the legal outer limit.
- [ ] EU recipients use double opt-in; consent documented and withdrawable.
- [ ] Suppression honored for all recipients.
- [ ] Transactional mail excluded from consent gating, and it carries no promotion.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Rebuilding the renderer, transport or push sender | Vendor `email-templates`, `email-transport`, `expo-push` from fabrik-lib |
| Node in the runtime image | Compile MJML at build time; runtime is Python-only |
| Compiling the vendored sources with a different MJML major | The module's `build.py`, which pins the major the sources are written in |
| Ignoring `send_email`'s return value, or retrying inside the vendored file | Check `result["success"]`; retry from the caller at one layer with the same idempotency key |
| Hand-coded HTML tables | MJML auto-emits tables + VML |
| External `<link>` stylesheets | `mj-attributes` or `<mj-style inline="inline">` |
| Background-image-dependent layout | Solid fills, or MJML `background-url` (emits VML) |
| Customer email through Apprise | `email-transport` — Resend or SES (transactional) — or Listmonk+SES (marketing). Apprise = internal/ops only |
| Missing plain-text part | `multipart/alternative` with plain-text always |
| Sending from the root domain | Dedicated subdomain (e.g. `mail.<domain>`) |
| Secrets/PII in push payloads | Deep link only; PII stays server-side |
| Per-template brand drift | ONE shared brand partial governs all templates |
| Uncompiled MJML shipped to runtime | Commit compiled `dist/` HTML; runtime loads compiled output |
| Email template without dark mode overrides | `color-scheme` meta + `@media (prefers-color-scheme: dark)` in shared brand partial |
| Relying on the dark-mode media query for legibility | Base colours that survive inversion; the query is an enhancement |
| Resend React Email / JSX layer | Ignored — we use MJML+Jinja2 |
| Hardcoded strings in email templates | i18n JSON per locale (`libs/email_templates/emails/i18n/{locale}.json`; WP: `.po`/`.mo`) |
| Hardcoded date/number formats in emails | Locale-aware formatting via `babel` or equivalent |
| Mixing transactional + marketing on one stream | Separate streams (separate ESP config or subdomain) |
| Marketing email without `List-Unsubscribe` header | RFC 8058 one-click unsubscribe on every marketing email |
| Custom headers to fake one-click in Listmonk | Listmonk's own "Include `List-Unsubscribe` header" setting |
| Lifecycle email copy and schedules hardcoded in application code | Resend automations; on Listmonk, a worker that fires each step through its API against templates kept in Listmonk and a schedule kept in config or the database |
| "AI email marketing" SaaS (Mailchimp AI, etc.) | Your own content AI + commodity ESP — you own the engine |
| Mautic for campaign management | Listmonk (Go + Postgres, deploys via `fabrik apply`) |
| Sending marketing from VPS IP directly | Always via SES or Resend — protect domain reputation |
| Auto-sending marketing content nobody approved | One-click approve gate before every campaign and before a sequence goes live |
| Sending marketing email without opt-in | Universal opt-in default; double opt-in for EU |
| Re-adding suppressed/bounced addresses | Explicit re-opt-in required |
| Marketing email to a TR recipient without İYS-registered consent | Register + verify consent in İYS before send (own-DB consent is insufficient for TR) |
| Promotion inside a TR transactional message | Keep receipts/notices free of promotion, or treat them as commercial |
| Assuming a Turkey base exempts you from GDPR for EU recipients | Consent follows recipient jurisdiction; universal opt-in covers all |
| Applying marketing-consent gating to transactional mail | Transactional is exempt — operational, separate stream |

---

## Related Rule Packs

- `35-security-auth.md` — transactional email for auth (reset, verification) references this pipeline; its § Transactional Email predates the SES transport and the off-request send rule — reconciled at that pack's turn
- `55-observability.md` — structured logging for email send events
- `58-resilience.md` — one retry layer for sends: the caller of the vendored transport, never the vendored file
- `80-mobile.md` — push notification rules (expo-notifications, FCM)
- `85-payments-billing.md` — the webhook events that drive receipts and dunning
- `ocoron-design-system.md` — brand tokens used in the shared partial

---

## ESP Decision Log (why Resend — traceable)

Decision: **Resend** as transactional default; **Postmark** as escalation-only. Rationale (prices re-checked against both vendors' pricing pages at this pack's `currency_pass` date):

- **Free tier decisive at this stage:** Resend 3,000 emails/mo free (capped at 100 a day, 3 sending domains) vs Postmark 100/mo (a testing tier with no overage).
- **Cheaper as it scales:** Postmark $15/mo for 10k vs Resend $20/mo for 50k — Resend pulls ahead past ~10k. Overage: Resend $0.90 per 1,000 on that plan; Postmark $1.20–$1.80 per 1,000 by tier.
- **DX/ops:** clean API + idempotency keys (24-hour window) + the vendored transport = AI-agent-friendly, set-and-forget.
- **Limits to design around:** Resend accepts 10 requests per second per team by default, a batch call of up to 100 emails (no attachments in a batch), and 40 MB per email including Base64 attachments; Postmark caps a message at 10 MB and a batch payload at 50 MB.
- **Known trade-off (bounded):** Postmark = long-standing deliverability specialist, running since 2010, with transactional and broadcast mail on separate message-stream infrastructure; Resend is newer and may lose a few points of inbox placement in sensitive categories — sufficient for most transactional mail.
- **Escalation rule (Fabrik "escalate on proven limit"):** move only mission-critical streams (reset, receipts) to Postmark *if and when* a deliverability problem is measured. Do not pre-pay.
