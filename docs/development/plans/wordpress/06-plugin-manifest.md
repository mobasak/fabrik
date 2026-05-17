# Plugin Manifest — Complete List Per Profile

**Principle:** Every plugin has a reason. If you can't state why in one line, it doesn't belong. This is the SINGLE SOURCE OF TRUTH for what gets installed where.

**Supersedes:** `docs/reference/wordpress/plugin-stack.md` (will be updated to match this during Phase 2).

---

## AutoPoly Translation Providers (built-in, no middleware)

AutoPoly Pro has built-in clients for:
- **DeepL** — API key in WP settings. Best quality for en↔tr. Recommended.
- **Google Translate** — Google Cloud Translation API key. Cheaper for bulk.
- **OpenAI/ChatGPT** — OpenAI API key. Best for creative/marketing content.

No Fabrik Translator microservice needed for WordPress. AutoPoly calls providers directly.

---

## GOLDEN BASE (11 plugins — every site)

| # | Plugin | Why it's in base (not profile) | Folder |
|---|---|---|---|
| 1 | GeneratePress + GP Premium | Theme. Lightweight, block-based, full Customizer. All sites need a theme. | `Base/` |
| 2 | RankMath Pro | SEO is non-negotiable. Schema, sitemap, IndexNow, redirects, 404 monitor, breadcrumbs, OG. | `Base/` |
| 3 | FlyingPress | Performance. Page cache + CSS/JS optimization. Every site must be fast. | `Base/` |
| 4 | WP Mail SMTP Pro | Email delivery. PHP mail() is unreliable/banned. Every site sends email (forms, notifications). | `Base/` |
| 5 | WP Staging Pro | Safe plugin updates. Watchdog AI uses this for test-before-apply. Every site needs staging. | `Base/` |
| 6 | Object Cache Pro | Redis caching. Every site on shared redis-main needs object cache. | `Base/` |
| 7 | Complianz Pro | Legal requirement. GDPR/CCPA everywhere. Can't launch without cookie consent. | `Base/` |
| 8 | Cloudflare Turnstile | Spam protection. Every form needs anti-bot. Free, lightweight. | Free (wp.org) |
| 9 | Polylang Pro | Multilingual is default (en+tr). URL routing, hreflang, menu/string translation. | `Polylang/` |
| 10 | AutoPoly Pro | Auto-translate on publish. Calls DeepL/Google/OpenAI directly. Zero manual work. | `Polylang/` |
| 11 | SearchWP Polylang | Search must respect language. Can't show Turkish results to English user. | `Polylang/` |

---

## COMPANY PROFILE (22 additional plugins)

For: service businesses, agencies, consultancies (like ocoron.com).

| # | Plugin | Why | Folder |
|---|---|---|---|
| 12 | Fluent Forms Pro | Contact forms, lead capture, multi-step. Core business function. | `Fluent/` |
| 13 | FluentCRM Pro | CRM + email sequences. Nurture leads. Same vendor = deep integration with Forms. | `Fluent/` |
| 14 | Thrive Leads | Opt-in popups, slide-ins. Capture email addresses from visitors. | `Thrive/` |
| 15 | Thrive Architect | Visual page builder for service pages, landing pages. Lighter than Elementor. | `Thrive/` |
| 16 | Thrive Ovation | Testimonial collection + display. Social proof = trust = conversions. | `Thrive/` |
| 17 | Thrive Headline Optimizer | A/B test headlines on blog posts. Data-driven, not guessing. | `Thrive/` |
| 18 | Thrive Clever Widgets | Show different sidebar content per page. Contextual CTAs. | `Thrive/` |
| 19 | Thrive Automator | Thrive ecosystem automation (leads → sequences). | `Thrive/` |
| 20 | AutomatorWP | Cross-plugin automation: form → CRM → email → webhook. Beyond Thrive ecosystem. | `AutomatorWP/` |
| 21 | AutomatorWP FluentCRM | AutomatorWP ↔ FluentCRM bridge. Form submissions trigger CRM actions. | `AutomatorWP/` |
| 22 | Link Whisper Pro | Internal linking suggestions. Builds SEO link equity across content. | `ContentSEO/` |
| 23 | SearchWP | Site search that works (fuzzy, synonyms, weighted). Native WP search is terrible. | `SearchWP/` |
| 24 | SearchWP Metrics | Know what users search for. Gaps = content opportunities for watchdog. | `SearchWP/` |
| 25 | Essential Grid | Portfolio/gallery grids. Showcase services visually. | `ContentSEO/` |
| 26 | Novashare | Social sharing buttons. Lightweight (no bloat like AddThis). | `ConversionMarketing/` |
| 27 | WP Table Builder Pro | Comparison/pricing tables in content. Service package comparisons. | `ContentSEO/` |
| 28 | PixelYourSite Pro | Conversion tracking: Facebook Pixel + Google Ads events. Measure ROI. | `ConversionMarketing/` |
| 29 | PixelYourSite Social Connect | Track social login/share events. Attribution data. | `ConversionMarketing/` |
| 30 | Chaty Pro | Multi-channel chat (WhatsApp, Messenger, Telegram). Direct visitor contact. | `ConversionMarketing/` |
| 31 | Go Pricing | Pricing tables for service packages. Visual comparison. | `ContentSEO/` |
| 32 | Content Egg Pro | Affiliate content aggregation. Useful if monetizing via partnerships. | `ContentSEO/` |
| 33 | Testimonial Pro | Additional testimonial display options. | `ContentSEO/` |

**Company total: 11 (base) + 22 = 33 active plugins.**

---

## SAAS PROFILE (Company + 2)

For: SaaS product landing pages, conversion-focused sites.

Everything from Company profile PLUS:

| # | Plugin | Why |
|---|---|---|
| 34 | Thrive Ultimatum | Countdown timers + scarcity. Urgency drives SaaS signups. |
| 35 | Thrive Quiz Builder | Quiz funnels for lead segmentation. "Which plan is right for you?" |

**SaaS total: 33 + 2 = 35 active plugins.**

---

## CONTENT PROFILE (Company base + 2)

For: blogs, magazines, affiliate content sites.

Everything from Company profile PLUS:

| # | Plugin | Why |
|---|---|---|
| 36 | Thrive Comments | Gamified comments (upvotes, featured). Engagement + time-on-site. |
| 37 | Thrive Quiz Builder | Interactive content quizzes. Engagement + email capture. |

**Content total: 33 + 2 = 35 active plugins.**

---

## LANDING PROFILE (subset of Company — minimal)

For: single-page conversion landings, campaign pages.

Uses BASE (11) + selected Company plugins (conversion-focused only):

| # | Plugin | Why |
|---|---|---|
| 12 | Fluent Forms Pro | Lead capture form. |
| 14 | Thrive Leads | Opt-in popup. |
| 15 | Thrive Architect | Page builder for the landing page. |
| 28 | PixelYourSite Pro | Conversion tracking. |
| 29 | PixelYourSite Social Connect | Attribution. |
| 30 | Chaty Pro | Chat widget. |
| 34 | Thrive Ultimatum | Countdown urgency. |
| 35 | Thrive Quiz Builder | Interactive lead capture. |
| 38 | SeedProd Pro | Coming soon / maintenance page (pre-launch). |

**Landing total: 11 (base) + 9 = 20 active plugins.** (Leanest profile.)

---

## ECOMMERCE PROFILE (WooCommerce)

For: physical products, subscription commerce.

Uses BASE (11) + Company CRM/forms core + WooCommerce stack:

| # | Plugin | Why | Folder |
|---|---|---|---|
| 12-21 | Company CRM/automation core | Forms, CRM, automation (same as company) | Various |
| 39 | WooCommerce | E-commerce core. | Free (wp.org) |
| 40 | AutomateWoo | Cart recovery, follow-ups, win-back. Replaces AutomatorWP for WC-specific automation. | `AutomateWoo/` |
| 41 | WooCommerce Subscriptions | Recurring payments. | `WooCommerce/` |
| 42 | WooCommerce Table Rate Shipping | Flexible shipping by region/weight/price. | `WooCommerce/` |
| 43 | WooCommerce Advanced Shipping | Conditional shipping rules. | `WooCommerce/` |
| 44 | SearchWP WooCommerce | Product search (weighted by price/stock/ratings). | `SearchWP/` |
| 45 | Polylang for WooCommerce | Product/cart/checkout/email per language. | `Polylang/` |
| 46 | WooCommerce Photo Reviews | Reviews with photos. Social proof for products. | `WooCommerce/` |
| 47 | Order Notifications on WhatsApp | Order updates to customers via WhatsApp. | `WooCommerce/` |
| 48 | WooCommerce Abandoned Cart Recovery | Recover lost sales. | `WooCommerce/` |

**Ecommerce total: 11 (base) + 10 (company core) + 10 (WC-specific) = ~31 active plugins.**

---

## DIGITAL PRODUCTS PROFILE (EDD)

For: software, downloads, licenses, digital-only sales. Lighter than WooCommerce.

Uses BASE (11) + Fluent CRM/forms + EDD stack:

| # | Plugin | Why | Folder |
|---|---|---|---|
| 12-13 | Fluent Forms + FluentCRM | Lead capture + nurture. | `Fluent/` |
| 49 | Easy Digital Downloads Pro | Digital product sales core. | `EDD/` |
| 50 | EDD PayPal Commerce | Multi-currency payments. | `EDD/` |
| 51 | EDD Content Restriction | Restrict downloads to buyers. | `EDD/` |
| 52 | EDD Free Downloads | Lead magnets with email capture before download. | `EDD/` |
| 53 | EDD Variable Pricing Switcher | Tiered pricing (Basic/Pro/Enterprise). | `EDD/` |
| 54 | EDD Reviews | Product reviews/ratings. Social proof. | `EDD/` |
| 55 | EDD Recommended Products | Cross-sell suggestions. Increase AOV. | `EDD/` |
| 56 | EDD Fraud Monitor | Reduce chargebacks on digital sales. | `EDD/` |

**Digital total: 11 (base) + 2 (Fluent) + 8 (EDD) = ~21 active plugins.**

---

## MEMBERSHIP PROFILE (MemberPress)

For: online courses, subscription content, membership communities.

Uses BASE (11) + Fluent CRM/forms + MemberPress stack:

| # | Plugin | Why | Folder |
|---|---|---|---|
| 12-13 | Fluent Forms + FluentCRM | Member communication + forms. | `Fluent/` |
| 20-21 | AutomatorWP + FluentCRM | Membership → automation triggers. | `AutomatorWP/` |
| 57 | MemberPress | Membership gating, course builder, subscription management. | `MemberPress/` |
| 58 | MemberPress Corporate | B2B team memberships (company buys seats). | `MemberPress/` |
| 59 | AutomatorWP MemberPress | Membership events → automation. | `AutomatorWP/` |

**Membership total: 11 (base) + 4 (Fluent/Automator) + 3 (MP) = ~18 active plugins.**

---

## APPOINTMENTS PROFILE (Bookly)

For: salons, clinics, consultants, gyms, service businesses with scheduling.

Uses BASE (11) + Company CRM/forms core + Bookly stack:

| # | Plugin | Why | Folder |
|---|---|---|---|
| 12-21 | Company CRM/automation core | Client communication + automation. | Various |
| 60 | Bookly PRO | Appointment scheduling core. | `Bookly/` |
| 61 | Bookly Advanced Google Calendar | Two-way Google Calendar sync (staff + client). | `Bookly/` |
| 62 | Bookly Stripe | Online payment at booking time. | `Bookly/` |
| 63 | Bookly PayPal Checkout | Alternative payment method. | `Bookly/` |
| 64 | Bookly Customer Cabinet | Customer portal (view/reschedule/cancel). | `Bookly/` |
| 65 | Bookly Staff Cabinet | Staff manages own availability. | `Bookly/` |
| 66 | Bookly Recurring Appointments | Repeat bookings (weekly therapy, monthly check-up). | `Bookly/` |
| 67 | Bookly Deposit Payments | Reduce no-shows (partial payment upfront). | `Bookly/` |
| 68 | Bookly Waiting List | Fill cancellations automatically. | `Bookly/` |
| 69 | Bookly Cart | Book multiple services in one checkout. | `Bookly/` |
| 70 | Bookly Custom Fields | Collect client info at booking (allergies, preferences). | `Bookly/` |
| 71 | Bookly Invoices | Auto-generate professional invoices. | `Bookly/` |
| 72 | Bookly Locations | Multi-location businesses. | `Bookly/` |

**Appointments total: 11 (base) + 10 (company core) + 13 (Bookly) = ~34 active plugins.**

Additional Bookly addons available (in `Bookly/` folder, activate per-need): Service Extras, Group Booking, Special Days, Service Schedule, Ratings, Chain Appointments, Compound Services, Collaborative Services, Packages, Custom Duration, Tasks, Customer Groups, Special Hours, Customer Information, Discounts, Files, Multiply Appointments, Multisite, Coupons.

---

## OPTIONAL (per-site, not in any profile by default)

| Plugin | When to activate | Folder |
|---|---|---|
| **Wordfence Premium** | WooCommerce/membership + many editors + high traffic. Security 11th layer. | `Security/` |
| **AffiliateWP** + 8 addons | Full affiliate program (SaaS/ecommerce wanting referral revenue). | `AffiliateWP/` |
| **AutomatorWP OpenAI** | AI-powered automation rules (generate content in workflows). | `AutomatorWP/` |
| **AutomatorWP WhatsApp** | WhatsApp notifications in automation flows. | `AutomatorWP/` |
| **AutomatorWP CSV** | Bulk import/export in automation. | `AutomatorWP/` |
| **AutomatorWP ACF** | Advanced Custom Fields triggers/actions. | `AutomatorWP/` |
| **ConvertPro** + Addon | Advanced popup builder (if Thrive Leads insufficient). | `ConversionMarketing/` |
| **Cart Lift Pro** | Abandoned cart recovery (non-WooCommerce sites). | `ConversionMarketing/` |
| **WhatsApp Chat Rotator** | Multi-agent WhatsApp routing. | `ConversionMarketing/` |
| **WP Sheet Editor Polylang** | Bulk edit translations in spreadsheet view. | `Polylang/` |
| **Formidable Polylang** | If switching from Fluent Forms to Formidable (backup). | `Polylang/` |
| **AutomateWoo Referrals** | WooCommerce customer referral program. | `AutomateWoo/` |
| **AutomateWoo Birthdays** | Birthday discount automation. | `AutomateWoo/` |

---

## ARCHIVED (owned but NOT installed — replaced)

| Plugin | Replaced by | Folder |
|---|---|---|
| WPML CMS | Polylang Pro | `WPML/` |
| WPML String Translation | Polylang Pro (built-in string translation) | `WPML/` |
| SearchWP WPML | SearchWP Polylang | `SearchWP/` |

---

## Summary

| Profile | Base | Profile additions | Total active |
|---|---|---|---|
| Company | 11 | 22 | **33** |
| SaaS | 11 | 24 | **35** |
| Content | 11 | 24 | **35** |
| Landing | 11 | 9 | **20** |
| Ecommerce | 11 | 20 | **31** |
| Digital Products | 11 | 10 | **21** |
| Membership | 11 | 7 | **18** |
| Appointments | 11 | 23 | **34** |

Every plugin has a stated reason. If a reason doesn't apply to your site — don't install it.
