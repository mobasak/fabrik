# Fabrik WordPress Plugin Stack

> **Curated from 7,079 plugins** — Optimized for Docker multi-site deployment
>
> Architecture: **BASE + PROFILES + OPTIONAL**
> - Minimal base image = faster deploys, fewer conflicts
> - Profile add-ons per site type
> - Optional plugins activated per-site as needed
>
> Legend:
> - ✅ **PLACED** — In `/opt/fabrik/templates/wordpress/plugins/premium/`
> - ⬜ **AVAILABLE** — In plugins_latest.json
> - 🆓 **FREE** — From wordpress.org

---

# BASE (Every Site)

> Truly minimal. Always installed. No overlap.

| Plugin | Status | Purpose |
|--------|--------|---------|
| GeneratePress | 🆓 FREE | Theme foundation |
| **GP Premium** | ✅ PLACED | Full customization, blocks, hooks |
| **Rank Math Pro** | ✅ PLACED | SEO, Schema, TOC, redirects, 404 monitor |
| **FlyingPress** | ✅ PLACED | Performance (works with Cloudflare APO) |
| **WP Mail SMTP Pro** | ✅ PLACED | Email delivery via Resend/SES (Pro for logging, alerts) |
| **WP Staging Pro** | ✅ PLACED | Staging, backup, migration |

### Security Baseline (Outside WP)

| Layer | Tool | Notes |
|-------|------|-------|
| Edge | Cloudflare WAF | Rate limiting, bot protection, DDoS |
| Edge | Cloudflare APO | Full page caching at edge |
| App | WP Hardening | Disable XML-RPC, limit login attempts, strong passwords |
| App | Turnstile | Add only when forms exist (free, 20 widgets/account) |

> **Wordfence** is NOT in base — moved to OPTIONAL for high-risk sites

---

# PROFILES

> Each profile adds specific plugins to BASE. Pick one profile per site.

## Company Profile

> Corporate/business sites, brochure sites, service businesses

| Plugin | Status | Purpose |
|--------|--------|------|
| **Fluent Forms Pro** | ✅ PLACED | Contact forms, lead capture |
| **Thrive Leads** | ✅ PLACED | Opt-ins, popups, lead capture |
| **FluentCRM Pro** | ✅ PLACED | CRM, email sequences |
| **Complianz Pro** | ✅ PLACED | GDPR, cookie consent |
| **AutomatorWP** | ✅ PLACED | Form→CRM automation |
| **AutomatorWP FluentCRM** | ✅ PLACED | FluentCRM integration |
| **Thrive Automator** | ✅ PLACED | Thrive automation |
| Cloudflare Turnstile | 🆓 FREE | Spam protection |
| **WPML CMS** | ✅ PLACED | Multilingual |
| **WPML String Translation** | ✅ PLACED | Multilingual strings |
| **Thrive Architect** | ✅ PLACED | Page building |
| **Thrive Ovation** | ✅ PLACED | Testimonials |
| **Essential Grid** | ✅ PLACED | Portfolio/gallery |
| **Link Whisper Pro** | ✅ PLACED | Internal linking |
| **SearchWP** | ✅ PLACED | Site search |
| **SearchWP WPML** | ✅ PLACED | Multilingual search |
| **SearchWP Metrics** | ✅ PLACED | Search analytics |
| **Novashare** | ✅ PLACED | Social sharing |
| **Thrive Headline Optimizer** | ✅ PLACED | A/B testing titles |
| **Thrive Clever Widgets** | ✅ PLACED | Conditional widgets |
| **WP Table Builder Pro** | ✅ PLACED | Tables |
| **PixelYourSite Pro** | ✅ PLACED | Conversion tracking |
| **PixelYourSite Social Connect** | ✅ PLACED | Social login tracking |
| **Chaty Pro** | ✅ PLACED | Multi-channel chat (WhatsApp, FB, etc.) |

## SaaS Profile

> SaaS product sites, lead generation, conversion-focused

| Plugin | Status | Purpose |
|--------|--------|------|
| **Fluent Forms Pro** | ✅ PLACED | Forms, lead capture |
| **Thrive Leads** | ✅ PLACED | Opt-ins, popups |
| **FluentCRM Pro** | ✅ PLACED | CRM, email sequences |
| **Complianz Pro** | ✅ PLACED | GDPR, cookie consent |
| **AutomatorWP** | ✅ PLACED | Cross-plugin/webhook automation |
| **AutomatorWP FluentCRM** | ✅ PLACED | FluentCRM integration |
| **Thrive Automator** | ✅ PLACED | Thrive automation |
| Cloudflare Turnstile | 🆓 FREE | Spam protection |
| **WPML CMS** | ✅ PLACED | Multilingual |
| **WPML String Translation** | ✅ PLACED | Multilingual strings |
| **Thrive Architect** | ✅ PLACED | Page building |
| **Thrive Ovation** | ✅ PLACED | Testimonials |
| **Thrive Ultimatum** | ✅ PLACED | Countdown/scarcity |
| **Go Pricing** | ✅ PLACED | Pricing tables |
| **Essential Grid** | ✅ PLACED | Portfolio/gallery |
| **Link Whisper Pro** | ✅ PLACED | Internal linking |
| **SearchWP** | ✅ PLACED | Site search |
| **SearchWP WPML** | ✅ PLACED | Multilingual search |
| **SearchWP Metrics** | ✅ PLACED | Search analytics |
| **Novashare** | ✅ PLACED | Social sharing |
| **Thrive Headline Optimizer** | ✅ PLACED | A/B testing titles |
| **Thrive Clever Widgets** | ✅ PLACED | Conditional widgets |
| **WP Table Builder Pro** | ✅ PLACED | Tables |
| **PixelYourSite Pro** | ✅ PLACED | Conversion tracking |
| **PixelYourSite Social Connect** | ✅ PLACED | Social login tracking |
| **Chaty Pro** | ✅ PLACED | Multi-channel chat |
| **AffiliateWP** | ⬜ AVAILABLE | Affiliate program |

## Content Profile

> Blogs, authority sites, affiliate sites, content marketing

| Plugin | Status | Purpose |
|--------|--------|------|
| **Fluent Forms Pro** | ✅ PLACED | Forms, lead capture |
| **Thrive Leads** | ✅ PLACED | Opt-ins, popups |
| **FluentCRM Pro** | ✅ PLACED | CRM, email sequences |
| **Complianz Pro** | ✅ PLACED | GDPR, cookie consent |
| **AutomatorWP** | ✅ PLACED | Automation |
| **AutomatorWP FluentCRM** | ✅ PLACED | FluentCRM integration |
| **Thrive Automator** | ✅ PLACED | Thrive automation |
| Cloudflare Turnstile | 🆓 FREE | Spam protection |
| **WPML CMS** | ✅ PLACED | Multilingual |
| **WPML String Translation** | ✅ PLACED | Multilingual strings |
| **Thrive Architect** | ✅ PLACED | Page building |
| **Thrive Ultimatum** | ✅ PLACED | Countdown/scarcity |
| **Thrive Quiz Builder** | ✅ PLACED | Quiz funnels |
| **Essential Grid** | ✅ PLACED | Gallery |
| **Link Whisper Pro** | ✅ PLACED | Internal linking |
| **SearchWP** | ✅ PLACED | Site search |
| **SearchWP WPML** | ✅ PLACED | Multilingual search |
| **SearchWP Metrics** | ✅ PLACED | Search analytics |
| **Novashare** | ✅ PLACED | Social sharing |
| **Thrive Comments** | ✅ PLACED | Engagement |
| **Thrive Headline Optimizer** | ✅ PLACED | A/B testing titles |
| **Thrive Clever Widgets** | ✅ PLACED | Conditional widgets |
| **WP Table Builder Pro** | ✅ PLACED | Comparison tables |
| **Content Egg Pro** | ✅ PLACED | Affiliate content |
| **PixelYourSite Pro** | ✅ PLACED | Conversion tracking |
| **PixelYourSite Social Connect** | ✅ PLACED | Social login tracking |
| **Chaty Pro** | ✅ PLACED | Multi-channel chat |

## Landing Profile

> Landing pages, single-page sites, campaign pages

| Plugin | Status | Purpose |
|--------|--------|------|
| **Fluent Forms Pro** | ✅ PLACED | Forms, lead capture |
| **Thrive Leads** | ✅ PLACED | Opt-ins, popups |
| **Complianz Pro** | ✅ PLACED | GDPR, cookie consent |
| **AutomatorWP** | ✅ PLACED | Automation |
| **Thrive Automator** | ✅ PLACED | Thrive automation |
| Cloudflare Turnstile | 🆓 FREE | Spam protection |
| **WPML CMS** | ✅ PLACED | Multilingual |
| **WPML String Translation** | ✅ PLACED | Multilingual strings |
| **Thrive Architect** | ✅ PLACED | Page building |
| **Thrive Ultimatum** | ✅ PLACED | Countdown/urgency |
| **Thrive Quiz Builder** | ✅ PLACED | Quiz funnels |
| **Essential Grid** | ✅ PLACED | Gallery |
| **Novashare** | ✅ PLACED | Social sharing |
| **Thrive Headline Optimizer** | ✅ PLACED | A/B testing titles |
| **SeedProd** | ✅ PLACED | Maintenance/coming soon |
| **PixelYourSite Pro** | ✅ PLACED | Conversion tracking |
| **PixelYourSite Social Connect** | ✅ PLACED | Social login tracking |
| **Chaty Pro** | ✅ PLACED | Multi-channel chat |

## Ecommerce Profile

> WooCommerce stores, digital products, subscriptions

| Plugin | Status | Purpose |
|--------|--------|------|
| WooCommerce | 🆓 FREE | E-commerce core |
| **Fluent Forms Pro** | ✅ PLACED | Forms, lead capture |
| **Thrive Leads** | ✅ PLACED | Opt-ins, popups |
| **FluentCRM Pro** | ✅ PLACED | CRM, email sequences |
| **Complianz Pro** | ✅ PLACED | GDPR, cookie consent |
| **WooCommerce AutomateWoo** | ⬜ AVAILABLE | Cart recovery, follow-ups, automation |
| **AutomateWoo – Refer A Friend** | ⬜ AVAILABLE | Customer referral program |
| **WooCommerce Abandoned Cart Recovery** | ⬜ AVAILABLE | Abandoned cart emails |
| Cloudflare Turnstile | 🆓 FREE | Spam protection |
| **WPML CMS** | ✅ PLACED | Multilingual |
| **WPML String Translation** | ✅ PLACED | Multilingual strings |
| **Thrive Architect** | ✅ PLACED | Page building |
| **Thrive Ultimatum** | ✅ PLACED | Countdown/scarcity |
| **Essential Grid** | ✅ PLACED | Gallery |
| **Link Whisper Pro** | ✅ PLACED | Internal linking |
| **SearchWP** | ✅ PLACED | Product search |
| **SearchWP WPML** | ✅ PLACED | Multilingual search |
| **SearchWP WooCommerce** | ✅ PLACED | Product search integration |
| **SearchWP Metrics** | ✅ PLACED | Search analytics |
| **Novashare** | ✅ PLACED | Social sharing |
| **Thrive Headline Optimizer** | ✅ PLACED | A/B testing titles |
| **PixelYourSite Pro** | ✅ PLACED | Conversion tracking |
| **PixelYourSite Social Connect** | ✅ PLACED | Social login tracking |
| GTM4WP | 🆓 FREE | Google Tag Manager integration |
| **Chaty Pro** | ✅ PLACED | Multi-channel chat (WhatsApp, FB, etc.) |
| **WhatsApp Chat for WooCommerce** | ⬜ AVAILABLE | WhatsApp sales chat |
| **Order Notifications on WhatsApp** | ⬜ AVAILABLE | Order updates via WhatsApp |
| **WooCommerce Photo Reviews** | ⬜ AVAILABLE | Reviews with photos/videos (alt: Product Reviews Pro) |
| **WooCommerce Table Rate Shipping** | ⬜ AVAILABLE | Flexible shipping rules |
| **WooCommerce FedEx Shipping** | ⬜ AVAILABLE | Real-time FedEx rates |
| **WooCommerce Advanced Shipping** | ⬜ AVAILABLE | Custom shipping conditions |
| **Redis Object Cache Pro** | ⬜ AVAILABLE | Performance (recommended) |
| **Wordfence Premium** | ⬜ AVAILABLE | Security |
| **WooCommerce Subscriptions** | ✅ PLACED | Subscriptions |
| WooCommerce Memberships | ⬜ AVAILABLE | Memberships |
| Variation Swatches Pro | ⬜ AVAILABLE | Product variations |
| **AffiliateWP** | ⬜ AVAILABLE | Full affiliate program (optional) |

> **Note:** For complex international shipping (duties, dangerous goods), consider **Easyship** ($29/month SaaS) instead of plugin-based shipping.
>
> **Automation Note:** AutomateWoo replaces AutomatorWP + Thrive Automator for ecommerce — it's purpose-built for WooCommerce workflows.

## Digital Products Profile (EDD)

> Easy Digital Downloads for selling digital products, software, licenses

| Plugin | Status | Purpose |
|--------|--------|------|
| **Easy Digital Downloads (Pro)** | ⬜ AVAILABLE | Core EDD for digital products |
| **Fluent Forms Pro** | ✅ PLACED | Forms, lead capture |
| **Thrive Leads** | ✅ PLACED | Opt-ins, popups |
| **FluentCRM Pro** | ✅ PLACED | CRM, email sequences |
| **Complianz Pro** | ✅ PLACED | GDPR, cookie consent |
| **AutomatorWP** | ✅ PLACED | Automation |
| **AutomatorWP FluentCRM** | ✅ PLACED | FluentCRM integration |
| Cloudflare Turnstile | 🆓 FREE | Spam protection |
| **WPML CMS** | ✅ PLACED | Multilingual |
| **WPML String Translation** | ✅ PLACED | Multilingual strings |
| **Thrive Architect** | ✅ PLACED | Page building |
| **Essential Grid** | ✅ PLACED | Gallery |
| **PixelYourSite Pro** | ✅ PLACED | Conversion tracking |
| **PixelYourSite Social Connect** | ✅ PLACED | Social login tracking |
| **Chaty Pro** | ✅ PLACED | Multi-channel chat |

### EDD Essential (Always Install)

| Plugin | Status | Purpose |
|--------|--------|------|
| **EDD Pro** | ⬜ AVAILABLE | Core - required |
| **EDD PayPal Commerce** | ⬜ AVAILABLE | Primary payment (multi-currency) |
| **EDD Multi-Currency** | ⬜ AVAILABLE | International sales |
| **EDD Content Restriction** | ⬜ AVAILABLE | Restrict downloads to buyers |
| **EDD Amazon S3** | ⬜ AVAILABLE | Secure file delivery from S3 |

### EDD High Value (Likely Need)

| Plugin | Status | Purpose |
|--------|--------|------|
| **EDD Variable Pricing Switcher** | ⬜ AVAILABLE | Tiered pricing (Basic/Pro/Enterprise) |
| **EDD Reviews** | ⬜ AVAILABLE | Social proof |
| **EDD Free Downloads** | ⬜ AVAILABLE | Lead magnets with email capture |
| **EDD Recommended Products** | ⬜ AVAILABLE | Cross-sell recommendations |
| **EDD Fraud Monitor** | ⬜ AVAILABLE | Reduce chargebacks |
| **EDD Recently Viewed Items** | ⬜ AVAILABLE | Increase conversions |

### EDD Situational (Only If Needed)

| Plugin | Status | When |
|--------|--------|------|
| **EDD 2Checkout** | ⬜ AVAILABLE | Alternative payment method |
| **EDD Braintree** | ⬜ AVAILABLE | Credit card processing |
| **EDD Zapier** | ⬜ AVAILABLE | External app integrations |
| **EDD Slack** | ⬜ AVAILABLE | Sales alerts to Slack |
| **EDD Xero** | ⬜ AVAILABLE | Invoice/accounting |
| **EDD Custom Prices** | ⬜ AVAILABLE | Pay-what-you-want pricing |
| **EDD Points and Rewards** | ⬜ AVAILABLE | Loyalty program |
| **EDD Wallet** | ⬜ AVAILABLE | Store credit system |
| **EDD Discount Code Generator** | ⬜ AVAILABLE | Bulk coupon generation |
| **EDD Manual Purchases** | ⬜ AVAILABLE | Record offline orders |
| **EDD Upload File** | ⬜ AVAILABLE | Customer file uploads |
| **EDD Custom Deliverables** | ⬜ AVAILABLE | Custom files per purchase |
| **EDD Purchase Limit** | ⬜ AVAILABLE | Per-product limits |
| **EDD Dropbox File Store** | ⬜ AVAILABLE | Alternative to S3 |

> **Skip:** EDD email marketing plugins (MailChimp, ConvertKit, AWeber, etc.) — use FluentCRM instead.
> **Skip:** EDD ClickBank, Check Payment, Payza, Mad Mimi — niche/low value.
> **Skip:** EDD Simple Shipping, Widgets Pack — not needed for digital products.

> **Note:** EDD is lighter than WooCommerce for pure digital products. Use EDD for software, licenses, downloads. Use WooCommerce for physical products or mixed catalogs.

## Membership Profile (MemberPress)

> Memberships, subscriptions, online courses, protected content

| Plugin | Status | Purpose |
|--------|--------|------|
| **MemberPress Basic (Core)** | ⬜ AVAILABLE | Core membership plugin |
| **Fluent Forms Pro** | ✅ PLACED | Forms, lead capture |
| **Thrive Leads** | ✅ PLACED | Opt-ins, popups |
| **FluentCRM Pro** | ✅ PLACED | CRM, email sequences |
| **Complianz Pro** | ✅ PLACED | GDPR, cookie consent |
| **AutomatorWP** | ✅ PLACED | Automation |
| **AutomatorWP FluentCRM** | ✅ PLACED | FluentCRM integration |
| **AutomatorWP – MemberPress** | ⬜ AVAILABLE | Membership workflow automation |
| Cloudflare Turnstile | 🆓 FREE | Spam protection |
| **WPML CMS** | ✅ PLACED | Multilingual |
| **WPML String Translation** | ✅ PLACED | Multilingual strings |
| **Thrive Architect** | ✅ PLACED | Page building |
| **Essential Grid** | ✅ PLACED | Gallery |
| **PixelYourSite Pro** | ✅ PLACED | Conversion tracking |
| **PixelYourSite Social Connect** | ✅ PLACED | Social login tracking |
| **Chaty Pro** | ✅ PLACED | Multi-channel chat |

### MemberPress Essential (Always Install)

| Plugin | Status | Purpose |
|--------|--------|------|
| **MemberPress Basic** | ⬜ AVAILABLE | Core - required |
| **MemberPress Courses** | ⬜ AVAILABLE | Course builder |
| **MemberPress Downloads** | ⬜ AVAILABLE | Protected member downloads |
| **MemberPress Developer Tools** | ⬜ AVAILABLE | REST API + webhooks |

### MemberPress High Value (Likely Need)

| Plugin | Status | Purpose |
|--------|--------|------|
| **MemberPress Social Login** | ⬜ AVAILABLE | Google/FB login (reduce friction) |
| **MemberPress Order Bumps** | ⬜ AVAILABLE | Increase order value |
| **MemberPress PDF Invoice** | ⬜ AVAILABLE | Professional invoices |
| **MemberPress Importer** | ⬜ AVAILABLE | Bulk import users |
| **MemberPress Amazon Web Services** | ⬜ AVAILABLE | Secure S3 file delivery |
| **MemberPress Gifting** | ⬜ AVAILABLE | Gift memberships |

### MemberPress Courses (If Selling Courses)

| Plugin | Status | Purpose |
|--------|--------|------|
| **MemberPress Course Quizzes** | ⬜ AVAILABLE | Quizzes with auto-grading |
| **MemberPress Course Gradebook** | ⬜ AVAILABLE | Track student performance |
| **MemberPress Course Assignments** | ⬜ AVAILABLE | Tasks and submissions |

### MemberPress Situational (Only If Needed)

| Plugin | Status | When |
|--------|--------|------|
| **MemberPress Quaderno** | ⬜ AVAILABLE | EU VAT/tax automation |
| **MemberPress Corporate Accounts** | ⬜ AVAILABLE | B2B team memberships |
| **MemberPress Registration Restrictions** | ⬜ AVAILABLE | Invite-only signups |
| **MemberPress BuddyPress** | ⬜ AVAILABLE | Community integration |
| **MemberPress Help Scout** | ⬜ AVAILABLE | Support ticket integration |
| **MemberPress Account Nav Tabs** | ⬜ AVAILABLE | Custom account pages |
| **MemberPress Cancel Override** | ⬜ AVAILABLE | Retention flows |
| **MemberPress Limit Signups** | ⬜ AVAILABLE | Limited availability |
| **MemberPress Manual Approval** | ⬜ AVAILABLE | Vetted memberships |

### MemberPress Content Protection (Pick Based on Builder)

| Plugin | Status | For |
|--------|--------|-----|
| **MemberPress Elementor** | ⬜ AVAILABLE | Elementor users |
| **MemberPress Divi** | ⬜ AVAILABLE | Divi users |
| **MemberPress Beaver Builder** | ⬜ AVAILABLE | Beaver Builder users |
| **MemberPress WPBakery** | ⬜ AVAILABLE | WPBakery users |

> **Skip:** MemberPress email plugins (MailChimp, ConvertKit, AWeber, etc.) — use FluentCRM instead.
> **Skip:** MemberPress Math CAPTCHA — use Turnstile.
> **Skip:** LearnDash Integration — use MemberPress Courses instead.

> **Note:** MemberPress is ideal for subscription-based content, online courses, and membership communities. For one-time digital product sales, use EDD instead.

## Appointments Profile (Bookly)

> Appointment booking, scheduling, service businesses

| Plugin | Status | Purpose |
|--------|--------|------|
| **Bookly PRO** | ⬜ AVAILABLE | Core booking/scheduling plugin |
| **Fluent Forms Pro** | ✅ PLACED | Forms, lead capture |
| **Thrive Leads** | ✅ PLACED | Opt-ins, popups |
| **FluentCRM Pro** | ✅ PLACED | CRM, email sequences |
| **Complianz Pro** | ✅ PLACED | GDPR, cookie consent |
| **AutomatorWP** | ✅ PLACED | Automation |
| **AutomatorWP FluentCRM** | ✅ PLACED | FluentCRM integration |
| Cloudflare Turnstile | 🆓 FREE | Spam protection |
| **WPML CMS** | ✅ PLACED | Multilingual |
| **WPML String Translation** | ✅ PLACED | Multilingual strings |
| **Thrive Architect** | ✅ PLACED | Page building |
| **Essential Grid** | ✅ PLACED | Gallery |
| **PixelYourSite Pro** | ✅ PLACED | Conversion tracking |
| **PixelYourSite Social Connect** | ✅ PLACED | Social login tracking |
| **Chaty Pro** | ✅ PLACED | Multi-channel chat |

### Bookly Essential (Always Install)

| Plugin | Status | Purpose |
|--------|--------|------|
| **Bookly PRO** | ⬜ AVAILABLE | Core - required |
| **Bookly Advanced Google Calendar** | ⬜ AVAILABLE | Two-way calendar sync |
| **Bookly Stripe** | ⬜ AVAILABLE | Primary payment |
| **Bookly PayPal Checkout** | ⬜ AVAILABLE | Alternative payment |
| **Bookly Customer Cabinet** | ⬜ AVAILABLE | Customer portal |

### Bookly High Value (Likely Need)

| Plugin | Status | Purpose |
|--------|--------|------|
| **Bookly Staff Cabinet** | ⬜ AVAILABLE | Staff manages schedules |
| **Bookly Recurring Appointments** | ⬜ AVAILABLE | Repeat bookings |
| **Bookly Deposit Payments** | ⬜ AVAILABLE | Reduce no-shows |
| **Bookly Waiting List** | ⬜ AVAILABLE | Fill cancellations |
| **Bookly Cart** | ⬜ AVAILABLE | Multiple services checkout |
| **Bookly Custom Fields** | ⬜ AVAILABLE | Collect extra info |
| **Bookly Invoices** | ⬜ AVAILABLE | Professional invoices |
| **Bookly Taxes** | ⬜ AVAILABLE | Tax compliance |
| **Bookly Coupons** | ⬜ AVAILABLE | Promotions |

### Bookly Service Business (Common Needs)

| Plugin | Status | Purpose |
|--------|--------|------|
| **Bookly Locations** | ⬜ AVAILABLE | Multi-location |
| **Bookly Service Extras** | ⬜ AVAILABLE | Upsell add-ons |
| **Bookly Group Booking** | ⬜ AVAILABLE | Classes, workshops |
| **Bookly Special Days** | ⬜ AVAILABLE | Holiday hours |
| **Bookly Service Schedule** | ⬜ AVAILABLE | Per-service availability |
| **Bookly Ratings** | ⬜ AVAILABLE | Social proof |

### Bookly Situational (Only If Needed)

| Plugin | Status | When |
|--------|--------|------|
| **Bookly Chain Appointments** | ⬜ AVAILABLE | Sequential services (spa day) |
| **Bookly Compound Services** | ⬜ AVAILABLE | Bundled services |
| **Bookly Collaborative Services** | ⬜ AVAILABLE | Multiple staff per booking |
| **Bookly Packages** | ⬜ AVAILABLE | Prepaid service bundles |
| **Bookly Multiply Appointments** | ⬜ AVAILABLE | Multiple bookings per order |
| **Bookly Custom Duration** | ⬜ AVAILABLE | Variable length appointments |
| **Bookly Tasks** | ⬜ AVAILABLE | Unscheduled tasks |
| **Bookly Google Maps** | ⬜ AVAILABLE | Location selection |
| **Bookly Files** | ⬜ AVAILABLE | Document uploads |
| **Bookly Customer Groups** | ⬜ AVAILABLE | VIP tiers |
| **Bookly Special Hours** | ⬜ AVAILABLE | Time-based pricing |
| **Bookly Customer Information** | ⬜ AVAILABLE | Detailed profiles |
| **Bookly PRO Discounts** | ⬜ AVAILABLE | Discount features |
| **GDPR Bookly Cabinet** | ⬜ AVAILABLE | EU GDPR compliance |

### Bookly Payment Gateways (Pick Based on Region)

| Plugin | Status | For |
|--------|--------|-----|
| **Bookly Stripe** | ⬜ AVAILABLE | Primary (global) |
| **Bookly PayPal Checkout** | ⬜ AVAILABLE | Alternative (global) |
| **Bookly 2Checkout** | ⬜ AVAILABLE | Alternative |
| **Bookly Mollie** | ⬜ AVAILABLE | EU payments |
| **Bookly PayU Latam** | ⬜ AVAILABLE | Latin America |
| **Bookly Payson** | ⬜ AVAILABLE | Sweden |

> **Skip:** Bookly Multisite — only for WordPress multisite installs.
> **Skip:** Bookly PayPal Standard — use PayPal Checkout instead.

> **Note:** Bookly is ideal for service businesses (salons, clinics, consultants, gyms). For event ticketing, consider different solutions.

---

# OPTIONAL (Per-Site Activation)

> Install only when specific need exists. Not in any default profile.

## GDPR & Privacy

| Plugin | Status | Activation Criteria |
|--------|--------|---------------------|
| **Complianz Pro** | ⬜ AVAILABLE | EU-facing sites with cookies/tracking |

## Security (High-Risk Sites)

| Plugin | Status | Activation Criteria |
|--------|--------|---------------------|
| **Wordfence Premium** | ⬜ AVAILABLE | WooCommerce, membership, login-heavy, many editors, high traffic |

> If installed, enforce: single config template, scheduled scans, no learning mode drift

## Performance (Bloated Sites)

| Plugin | Status | Activation Criteria |
|--------|--------|---------------------|
| **Asset CleanUp Pro** | ⬜ AVAILABLE | Heavy plugin/page-builder bloat, WITH QA time |

> Can cause breakage. Requires per-template testing.

## Automation: AutomatorWP

| Plugin | Status | Activation Criteria |
|--------|--------|---------------------|
| **AutomatorWP** | ✅ PLACED | Cross-plugin automation (core required) |
| **AutomatorWP – FluentCRM** | ✅ PLACED | FluentCRM integration |
| **AutomatorWP – WhatsApp** | ✅ PLACED | WhatsApp notifications/automation |
| **AutomatorWP – OpenAI** | ✅ PLACED | AI content generation, responses |
| **AutomatorWP – Advanced Custom Fields** | ✅ PLACED | ACF field-based automation |
| **AutomatorWP – CSV** | ✅ PLACED | Bulk data import/export |
| **AutomatorWP – Thrive Apprentice** | ✅ PLACED | Course enrollment automation |
| **AutomatorWP – Webhooks** | ⬜ AVAILABLE | External system integration |
| **AutomatorWP – Google Sheets** | ⬜ AVAILABLE | Data sync, reporting automation |
| **AutomatorWP – Fluent Support** | ⬜ AVAILABLE | Support ticket automation |
| **AutomatorWP – FluentCommunity** | ⬜ AVAILABLE | Community interaction automation |
| **AutomatorWP – Zoom** | ⬜ AVAILABLE | Webinar/meeting automation |
| **AutomatorWP – Formatter** | ⬜ AVAILABLE | Data transformation |
| **AutomatorWP – Button** | ⬜ AVAILABLE | User-triggered actions |
| **AutomatorWP – Link** | ⬜ AVAILABLE | Link click triggers |
| **AutomatorWP – Calculator** | ⬜ AVAILABLE | Dynamic calculations |
| **AutomatorWP – QR Code** | ⬜ AVAILABLE | QR-based automation |
| **AutomatorWP – Google Calendar** | ⬜ AVAILABLE | Event scheduling automation |

### What AutomatorWP Does

Rule-based workflows inside WordPress: **events (triggers) → outcomes (actions)** across plugins and external apps.

**Example workflows:**
- WooCommerce purchase → apply WP Fusion tag
- BuddyPress group join → enroll in LearnDash course
- Form submit → add to FluentCRM → send email → grant access
- Any WP event → webhook to external CRM/warehouse

### Business Value

| Benefit | Impact |
|---------|--------|
| **Less manual ops** | Automates repetitive admin: tagging users, creating accounts, sending onboarding, granting access |
| **Higher conversion** | Immediate follow-up on signup/purchase; no "lead goes cold" gaps |
| **Cross-system integration** | Push WP events to CRM/warehouse via webhooks without custom code |
| **Template once, deploy many** | Reusable recipes across all containers |

### When to Install (Simple Rule)

Install when **at least one** is true:
1. Need automation **beyond Thrive ecosystem** (multiple plugin ecosystems)
2. Need **webhooks** to integrate with external systems / other WP sites
3. Have **repeatable workflows** to reuse across containers

### Site Type Applicability

| Site Type | AutomatorWP Need | Typical Use |
|-----------|------------------|-------------|
| **Ecommerce** | High | Order→tag→access→notify |
| **SaaS** | High | Signup→segment→CRM→onboard |
| **Content** | Medium | Subscriber→segment→sequence |
| **Company** | Medium | Form→CRM→webhook |
| **Landing** | Low | Only if pushing leads to external systems |

> **Rule:** If AutomatorWP installed, keep Thrive Automator workflows minimal (one automation owner per site)

## Content Automation

| Plugin | Status | Activation Criteria |
|--------|--------|---------------------|
| **FS Poster** | ⬜ AVAILABLE | Automated social posting workflow |
| **AIKit** | ⬜ AVAILABLE | AI content generation workflow |

> Adds API keys, quotas, ops overhead. Only for operationalized publishing.

## Social Proof

| Plugin | Status | Activation Criteria |
|--------|--------|---------------------|
| **NotificationX Pro** | ⬜ AVAILABLE | If FOMO/social proof strategy |

## Analytics

| Plugin | Status | Activation Criteria |
|--------|--------|---------------------|
| **MonsterInsights Pro** | ⬜ AVAILABLE | If GA4 dashboard needed |
| **Independent Analytics Pro** | ⬜ AVAILABLE | If privacy-focused (no Google) |

> **Rule:** Pick ONE per site. Never install both.

## Bulk Operations

| Plugin | Status | Activation Criteria |
|--------|--------|---------------------|
| **WP All Import Pro** | ⬜ AVAILABLE | Data migration/import |
| **WP All Export Pro** | ⬜ AVAILABLE | Data export |
| **Smart Manager** | ⬜ AVAILABLE | Bulk editing |

## Developer Tools

| Plugin | Status | Activation Criteria |
|--------|--------|---------------------|
| **Code Snippets Pro** | ⬜ AVAILABLE | Safe PHP additions |
| **Admin Columns Pro** | ⬜ AVAILABLE | Admin UX improvements |
| **FileBird Pro** | ⬜ AVAILABLE | Media library organization |
| **WP Staging Pro** | ⬜ AVAILABLE | Staging environments |

---

# CONFLICT RULES

> Enforce these to prevent overlap and complexity creep.

| Rule | Enforcement |
|------|-------------|
| **ONE page builder** | Thrive Architect OR GP Blocks. SeedProd = maintenance only |
| **ONE popup system** | Thrive Leads only. Convert Pro REMOVED from stack |
| **ONE automation owner** | Thrive Automator OR AutomatorWP primary per site |
| **ONE analytics plugin** | MonsterInsights OR Independent Analytics, never both |
| **ONE Turnstile widget** | Per domain or site-type, avoid widget sprawl |
| **ONE testimonial system** | Thrive Ovation only |
| **ONE comments system** | Thrive Comments only (if used) |

---

# ADDITIONAL PLUGINS IN FOLDER

> Plugins placed but not assigned to specific profiles. Available for use.

| Plugin | Status | Purpose |
|--------|--------|---------|
| **Convert Pro** | ✅ PLACED | Alternative popup builder (use Thrive Leads instead) |
| **Convert Pro Addon** | ✅ PLACED | Convert Pro extensions |
| **Testimonial Pro** | ✅ PLACED | Alternative testimonials (use Thrive Ovation instead) |
| **Thrive Theme** | ✅ PLACED | Full Thrive theme (alternative to GeneratePress) |
| **Thrive Apprentice** | ✅ PLACED | Course/LMS functionality |
| **Thrive Comments** | ✅ PLACED | Enhanced comments system |
| **Thrive Quiz Builder** | ✅ PLACED | Quiz funnels, lead generation |
| **Content Egg Pro** | ✅ PLACED | Affiliate content, product comparisons |
| **Go Pricing** | ✅ PLACED | Pricing tables |
| **SeedProd Pro** | ✅ PLACED | Coming soon, maintenance pages |
| **SearchWP WPML** | ✅ PLACED | SearchWP multilingual integration |
| **SearchWP WooCommerce** | ✅ PLACED | SearchWP product search |
| **SearchWP Metrics** | ✅ PLACED | Search analytics |
| **PixelYourSite Social Connect** | ✅ PLACED | Social login for tracking |

---

# REMOVED FROM STACK

> Do NOT use these - redundant with preferred alternatives.

| Plugin | Reason |
|--------|--------|
| Convert Pro | Redundant with Thrive Leads |
| Testimonial Pro | Redundant with Thrive Ovation |
| Multiple analytics | Pick one per site |
| Wordfence in base | Moved to optional (overhead concern) |
| Redis in base | Moved to ecommerce profile |
| Asset CleanUp in base | Moved to optional (breakage risk) |

---

# DOWNLOAD PRIORITY

## Phase 1: Core (Get First - ALL PROFILES)
| # | Plugin | Required For |
|---|--------|--------------|
| 1 | **FlyingPress** | All sites (performance) |
| 2 | **Fluent Forms Pro** | All profiles (forms, lead capture) |
| 3 | **FluentCRM Pro** | All profiles (CRM, email sequences) |
| 4 | **Complianz Pro** | All profiles (GDPR, cookie consent) |

## Phase 2: Automation
| # | Plugin | Required For |
|---|--------|--------------|
| 5 | **AutomatorWP** | Form→CRM automation, webhooks |
| 6 | **AutomatorWP Webhooks** | External system integration |

## Phase 3: Content
| # | Plugin | Required For |
|---|--------|--------------|
| 7 | **Link Whisper Pro** | Content sites |
| 8 | **SearchWP** | Content sites |
| 9 | **Novashare** | Content sites |

## Phase 4: Ecommerce
| # | Plugin | Required For |
|---|--------|--------------|
| 9 | **Redis Object Cache Pro** | High-traffic ecom |
| 10 | **Wordfence Premium** | Ecom security |
| 11 | **PixelYourSite Pro** | Paid ads tracking |

## Phase 5: Optional
| # | Plugin | When Needed |
|---|--------|-------------|
| 12 | **MonsterInsights Pro** | GA4 dashboard |
| 13 | **Asset CleanUp Pro** | Bloated sites |
| 14 | **NotificationX Pro** | Social proof |
| 15+ | Developer tools | As needed |

---

# SUMMARY

| Category | Count | Status |
|----------|-------|--------|
| BASE | 5 | All placed (GP Premium, Rank Math, FlyingPress, WP Mail SMTP Pro, WP Staging Pro) |
| THRIVE SUITE | 11 | All placed |
| WPML | 2 | All placed |
| FLUENT STACK | 3 | All placed (Forms, CRM, Complianz) |
| SEARCHWP | 4 | Core + 3 add-ons placed |
| AUTOMATORWP | 7 | Core + 6 add-ons placed |
| PIXELYOURSITE | 2 | Pro + Social Connect placed |
| ADDITIONAL | 14 | Placed but optional |
| TO DOWNLOAD | ~5 | As needed per profile |

**Docker Image Contains:**
- BASE plugins (5)
- All PLACED plugins (46 total)
- Profile/Optional plugins added via deployment config

---

# SITE TYPE QUICK REFERENCE

| Site Type | Profile | Key Plugins |
|-----------|---------|-------------|
| ocoron.com | company | Base + Fluent Stack + AutomatorWP FluentCRM + SearchWP WPML + Thrive + WPML + PYS |
| SaaS product | saas | Base + Fluent Stack + AutomatorWP FluentCRM + SearchWP WPML + Thrive + WPML + PYS |
| Blog/authority | content | Base + Fluent Stack + AutomatorWP FluentCRM + SearchWP WPML + Thrive + Content Egg |
| Campaign page | landing | Base + Fluent Forms + Thrive + WPML + PYS |
| Online store | ecommerce | Base + Fluent Stack + SearchWP WooCommerce + SearchWP WPML + Thrive + PYS |
| Digital products | edd | Base + Fluent Stack + AutomatorWP FluentCRM + PYS |
| Membership | memberpress | Base + Fluent Stack + AutomatorWP FluentCRM + PYS |
| Appointments | bookly | Base + Fluent Stack + AutomatorWP FluentCRM + PYS |
