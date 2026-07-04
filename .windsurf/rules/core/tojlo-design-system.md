<!-- CONSUMER: Coding agents building Tojlo-branded UI
     GOAL: Tojlo-specific overrides on top of Ocoron — brand story, module naming, module-specific components
     TRAYCER USAGE: Injects as Context File for Tojlo project tickets only.
     AGENT USAGE: Inherits everything from ocoron-design-system.md. Only accent color + module patterns differ. -->

# Tojlo Design System v1.1

> Single source of truth for the Tojlo brand and all Tojlo product surfaces.
> **Tojlo inherits every engineering and voice foundation from `ocoron-design-system.md`.** This document specifies only overrides, additions, and Tojlo-specific patterns.

---

## Contents

**Foundation**
- [Inheritance Contract](#inheritance-contract)

**Brand**
- [Brand Story](#brand-story) · Manifesto, name origin, anti-positioning, audience, promise
- [Verbal Identity](#verbal-identity) · Positioning, Naming, Voice, Localized Voice, Voice Across Surfaces, Forbidden Language
- [Brand Architecture](#brand-architecture) · Endorsed model, when to use which brand, co-branding

**Visual System**
- [Logo](#logo) · Geometry, monogram, lockups, color, sizing, motion, misuse, assets
- [Color System](#color-system) · Tojlo Indigo override, semantic colors, layer coding
- [Typography](#typography) · Module chrome type, KPI display
- [Iconography](#iconography) · Lucide library, module icons, custom icons
- [Motion Language](#motion-language) · Durations, easings, patterns, sound, haptics, reduced motion
- [Density Modes](#density-modes) · Comfortable, Compact, Spacious

**Components**
- [Component Patterns](#component-patterns) · Module Card, KPI Card, Activity Feed, SSO, Embedded Frame
- [Data Tables](#data-tables)
- [Forms and Inline Editing](#forms-and-inline-editing)
- [Search and Command Palette](#search-and-command-palette)
- [Charts and Data Visualization](#charts-and-data-visualization)
- [States](#states--empty-loading-error-success-partial)
- [Notification System](#notification-system)
- [Activity and Audit UX](#activity-and-audit-ux)
- [Permissions UX](#permissions-ux)
- [Onboarding](#onboarding)

**AI**
- [AI Interaction Patterns](#ai-interaction-patterns) · Principles, A1–A5 surfaces, confidence, citation, recovery

**Localization and Compliance**
- [Multilingual and RTL](#multilingual-and-rtl)
- [Date, Time, Currency, and Number Formatting](#date-time-currency-and-number-formatting)
- [Email Templates](#email-templates)
- [Print and Export](#print-and-export)
- [Accessibility](#accessibility)

**Implementation**
- [Spacing, Interaction, Scaffolds](#spacing-interaction-scaffolds)
- [Tailwind Theme Extension](#tailwind-theme-extension-tojlo)
- [CSS Custom Properties](#css-custom-properties-tojlo)
- [White-Label Theming](#white-label-theming-future)
- [Token Governance](#token-governance-and-contribution-process)
- [Implementation Stack Summary](#implementation-stack-summary)

**Governance**
- [Rules for AI Agents](#rules-for-ai-agents-kilo--windsurf--traycer) · T1–T47
- [Versioning](#versioning)

---

## Inheritance Contract

Tojlo uses Ocoron's design system as its foundation. The following are **inherited unchanged** and must not be re-specified, re-defined, or overridden in Tojlo surfaces:

- **Typography stack:** Space Grotesk (headings), Inter (body/UI), JetBrains Mono (code/data) — identical weights, scale, line-heights, letter-spacing.
- **Spacing tokens:** `--space-xs` through `--space-2xl` — identical.
- **Interaction tokens:** transition durations, easings, hover/press/focus — identical.
- **Motion language:** duration scale, easing curves, canonical patterns, M1-M8 forbidden rules, reduced motion — identical.
- **Surface hierarchy:** `--surface-0` through `--surface-3` and `--border` — identical, both dark (default) and light variants.
- **Text hierarchy:** `--text-primary`, `--text-body`, `--text-muted` — identical.
- **Secondary semantic colors:** `--color-secondary`, `--color-danger`, `--color-success`, `--color-info`, `--color-purple` — identical.
- **Component patterns:** cards, tags, pills, buttons (primary/secondary/danger), tab bar, progress bars, collapsible blocks, data hierarchy, KPI card, activity feed — identical.
- **Iconography:** Lucide library, sizing, rules I1-I8 — identical.
- **Density modes:** Comfortable/Compact/Spacious, rules D1-D5 — identical.
- **Data tables:** anatomy, rules TBL1-TBL10 — identical.
- **Forms:** layout, validation, save behavior, rules F1-F8 — identical.
- **Search and command palette:** layout, keyboard, AI search — identical.
- **Charts:** library, color rules, chart rules C1-C7 — identical.
- **States:** loading, empty, error, permission denied, success, partial — identical.
- **Notification system:** taxonomy, throttling, rules N1-N6 — identical.
- **Activity and audit UX:** rules A1-A4 — identical.
- **Permissions UX:** roles, surfacing, rules PR1-PR4 — identical.
- **Onboarding:** first-run, hints, rules O1-O5 — identical.
- **AI interaction patterns:** A1-A5 surfaces, confidence/citation, streaming, recovery — identical.
- **Multilingual and RTL:** rules ML1-ML8 — identical.
- **Date/time/currency/number formatting:** rules FMT1-FMT8 — identical.
- **Print and export:** rules EX1-EX5 — identical.
- **Accessibility:** rules ACC1-ACC8 — identical.
- **Voice and tone:** "The Engineer Who Ships." Precise, confident, grounded. Identical traits, identical tone spectrum.
- **Writing rules:** lead with outcome, active voice, short paragraphs, specifics over adjectives, no rhetorical questions, describe AI specifically. Identical.
- **Forbidden language table:** identical. The same forbidden words apply.
- **AI-agent visual rules 1–10 and responsive rules 11–15:** identical.
- **Responsive layout:** breakpoints (sm/md/lg/xl/2xl), mobile-first approach, layout grid, component responsive behavior, sidebar collapse, data table mobile patterns, RWD1–RWD10 — identical. Every Tojlo web page must be responsive from 375px to 2560px.
- **Scaffold adaptation matrix** (saas-skeleton, static-site, chrome-extension, mobile-app, desktop-app, wordpress, docusaurus): identical, with only the accent token swapped.

If a rule is not listed in this document, the Ocoron design system rule applies.

---

## Brand Story

**Tojlo** is the operating system for B2B operations.

### Manifesto

Operations are where deals die. Not at the pitch. Not at the contract. In the gap between systems — the email someone forgot to forward, the lead that fell out of the spreadsheet, the customer chat nobody saw because it lived in a tool nobody opened, the invoice that went out three weeks late because two systems didn't talk.

Most companies treat that gap as the cost of doing business: hire more people, buy another tool, add another integration. The gap grows anyway.

Tojlo treats the gap as a design problem. Twelve modules, one platform, AI in every seam. The tools talk because they aren't separate tools — they're one system that happens to be modular. The AI works because it sees the whole flow, not the slice each SaaS app sees alone.

Tojlo doesn't replace your tools. It replaces the *space between* your tools.

The operator's job is judgement. Everything else is the operating system's problem.

### Name Origin

**Tojlo** — short, two-syllable, ownable. The 'j' gives it engineered, central-European phonetics rather than Silicon Valley softness. Pronounced *TOY-lo*. Reads consistently in Latin, Cyrillic transliteration, and Arabic phonetics — which matters for a platform serving multilingual B2B markets.

### What Tojlo Is NOT

Tojlo is **not**:

- **A CRM.** CRMs are about salespeople tracking pipeline. Tojlo is about operators running the business end-to-end.
- **An ERP.** ERPs are systems of record. Tojlo embeds an ERP (ERPNext, as Tojlo OPS) inside it but is broader: ERP + CRM + automation + intelligence + outreach + portal + storage in one platform.
- **An AI assistant.** Assistants chat. Tojlo *operates* — it sends emails, posts WhatsApp messages, files invoices, runs commission cycles. AI is internal to Tojlo's actions, not a separate chatbot bolted onto a SaaS.
- **A marketing-automation tool.** Tools like Mailchimp serve marketers running campaigns. Tojlo serves operators running businesses where marketing is one workflow among many.
- **A vertical SaaS.** Tojlo is industry-agnostic. Trade houses are the first proof point; the platform is built for any B2B operation.
- **A no-code platform.** Tojlo has fewer knobs than a no-code tool by design. Configuration over composition: opinionated, fast, narrow.
- **A consulting service in disguise.** Ocoron *delivers* the deployment. Tojlo *is* the product. Two distinct commercial lines.

When a prospect asks "is Tojlo like X?" the answer is almost always *"no, it's the layer above X"* or *"no, X is one of the modules inside Tojlo."*

### Audience

Tojlo is built for **the operator**: the person inside a B2B business whose job is to make the day-to-day actually work. Sales-operations leaders, COOs and heads of operations, founders of 10–500-person B2B companies, trade-house owners, agency operations leads, B2B services principals.

The operator owns *the whole flow* — from first lead to paid invoice. Tojlo is the operating system for that role. Not for engineers (we don't ship for developers), not for marketers (we don't ship campaign tools), not for finance or HR teams buying point solutions.

### Promise to the Customer

Three promises, backed by the contract:

1. **One login, one platform.** No tab-switching. No copy-paste. No "let me check the other system."
2. **AI that acts, not just talks.** Tojlo does the work — drafts, sends, files, follows up. The operator approves; AI executes.
3. **Compounding value.** Every workflow that runs through Tojlo trains the next. Month 6 is faster than month 1; year 2 is faster than year 1.

Every feature, UI decision, and line of marketing copy must support one of these three. If a proposed feature doesn't, it doesn't ship.

---

## Verbal Identity

### Positioning

**Statement:** Tojlo is the AI-native operating system for B2B sales and operational excellence.

**Tagline (primary):** *The B2B Operating System.*

- Category-defining claim. Plants a flag.
- Doesn't overclaim AI — AI is a feature of the OS, not the product itself.
- 4 words. Ownable. Passes the swap test.

**Tagline (campaign / secondary):** *Operate at the speed of AI.*

- For ads, video, social, sales decks.
- Action-led. Outcome-first.
- Use when the primary tagline has already been established in context.

**One-liner (sales / B2B email):** *Tojlo unifies your B2B sales and operations into one AI-native platform — twelve modules, one login, every workflow in one place.*

### Brand Name Usage

- **Standard text:** "Tojlo" — capital T, lowercase rest. Always.
- **Never:** "TOJLO" in body text, "tojlo" in body text, "ToJlo," "Tojlö," or any other variation.
- **All-caps:** Only in the logo wordmark itself or in module names (`TOJLO MAIL`).
- **Lowercase:** Only in URLs, CLI commands, package names, code references (`tojlo.com`, `tojlo-cli`).
- **Possessive:** "Tojlo's" is acceptable.
- **Product full name:** "Tojlo OS" when referring to the whole platform. "Tojlo" alone is acceptable when context is clear.
- **Endorsement lockup:** "Tojlo, by Ocoron." Use in footers, first-contact materials, legal documents, and trust signals. Never use "Ocoron Tojlo" — that breaks the endorsed-brand model.

### Module Naming

Tojlo modules follow a strict pattern: **`Tojlo [MODULE]`** where `[MODULE]` is a single uppercase word.

Canonical module list (from Unified Architecture v3):

| Layer | Module | Purpose |
|---|---|---|
| Core | **Tojlo Dashboard** | SSO unified surface |
| Core | **Tojlo OPS** | ERPNext-based operations |
| Core | **Tojlo HUB** | n8n workflow orchestration |
| Core | **Tojlo CHAT** | Wati WhatsApp Business |
| Core | **Tojlo MAIL** | M365 + Gemini email automation |
| Core | **Tojlo PORTAL** | External read-only portal |
| Core | **Tojlo VAULT** | Document and data archive |
| Core | **Tojlo AUTH** | Self-hosted SSO (`fabrik-lib/fastapi-user-auth`) |
| Intelligence | **Tojlo TI** | Trade and market intelligence |
| Growth | **Tojlo WEB** | Public site / SEO |
| Growth | **Tojlo MARKETS** | Paid acquisition |
| Growth | **Tojlo REACH** | Outbound prospecting |
| Growth | **Tojlo OUTREACH** | Cold email sequences |

**In UI chrome** (sidebars, tab bars, module switchers): set the module name in **Inter 500, uppercase, letter-spacing 1px, 11–13px**. The word "Tojlo" may be omitted in the chrome itself when the user is already inside the Tojlo Dashboard — display just `MAIL`, `HUB`, etc. Always include "Tojlo" in marketing, documentation, support, and external references.

**In documentation and prose:** "Tojlo MAIL," "Tojlo HUB" — first reference always full. Subsequent references in the same paragraph may shorten to "MAIL" or "HUB" if context is unambiguous.

**Never invent new module names.** New modules require approval and an addition to this list.

### Voice

Tojlo's voice is **identical to Ocoron's** ("The Engineer Who Ships") — a senior operator who's built and run the system, not a salesperson and not a consultant. Direct, precise, grounded.

Two Tojlo-specific shifts from the Ocoron baseline:

- **Slightly warmer in product UI.** Operators aren't engineers. Plain English over jargon: "New customer," not "New entity." Still functional, still minimal.
- **Voice is constant across languages.** When localized into TR, AR, RU, FA, preserve the directness even where local norm allows softening. See *Voice in Localized Markets* below.

### Writing Rules

All Ocoron writing rules apply unchanged. Two Tojlo-specific additions:

1. **Always say what Tojlo did.** "Tojlo logged 3 new leads from WhatsApp." Not "3 new leads were logged." Not "AI logged 3 new leads." Operators want to know which system acted on their data.
2. **Module attribution in notifications, activity feeds, and digests.** "Tojlo HUB completed weekly commission run" — not "Workflow completed." Operators learn the platform faster when they can map cause to source.

### Forbidden Language

The Ocoron forbidden language table applies in full. Tojlo-specific additions:

| Forbidden | Why | Use Instead |
|---|---|---|
| "All-in-one" | SaaS cliché; weakens the operating-system positioning | "The B2B Operating System" or list what's actually unified |
| "AI-powered" (as adjective) | AI claims attract higher scrutiny — name the behavior | "Tojlo MAIL drafts replies in any language" |
| "Smart [feature]" | Vague AI-washing | Describe the behavior: "Tojlo MAIL groups emails by customer," not "Smart inbox" |
| "Magic" / "Magical" | Hides what the AI does — opposes the AI-labeling rule | "Drafted by Tojlo MAIL" |
| "Effortless" / "Painless" | Promises something the operator hasn't experienced yet | State the work removed: "Tojlo HUB files commission invoices automatically; you approve in one click" |
| "Next-generation" / "Modern" | Says nothing | Name the actual capability |
| "Workflow" alone in marketing | Buzzword unless tied to Tojlo HUB | "Tojlo HUB workflow" or describe the sequence |
| "Suite" | Implies disconnected tools — the opposite of the positioning | "Platform" or "operating system" |
| "Enterprise-grade" | Empty superlative | Cite the SLA, audit certification, or deployment scale |
| "Intuitive" | Self-praise | Show the steps; let brevity speak |

### Voice in Localized Markets

Tojlo's voice — direct, precise, confident — is the same in every language. Language norms shift; voice does not. Use this guidance to translate without softening.

#### Turkish (TR)

Default register. Most B2B Turkish business communication opens with formal courtesy ("Merhaba [İsim] Bey/Hanım,"). Honor that opener, then move directly to substance. Do not pile on extra pleasantries — those soften the voice.

- ✅ "Merhaba Hasan Bey, Tojlo MAIL kurulumu tamamlandı. İlk e-posta etiketleme 5 dakika içinde başlar."
- ❌ "Sayın Hasan Bey, umarım bu güzel günde sizleri sağlıklı buluyorumdur. Size çok güzel bir haberimiz var…"

For UI strings, drop honorifics entirely. The product talks to the user, not at them.

- ✅ "Yeni teklif oluştur"
- ❌ "Lütfen yeni bir teklif oluşturmak için tıklayınız"

#### Arabic (AR)

RTL layout. Voice unchanged from baseline. Avoid the formal religious openers in product UI — keep them for first-contact letters where the partner expects them.

- ✅ "تم إعداد Tojlo MAIL. سيبدأ تصنيف البريد خلال ٥ دقائق."
- ❌ "بسم الله الرحمن الرحيم، يسعدنا إبلاغكم…"

Numerics use Arabic-Indic digits (٠١٢٣٤٥٦٧٨٩) where the tenant prefers them; Western digits (0123456789) otherwise. Lock the choice per tenant in tenant settings, never mix in the same surface.

#### Russian (RU)

Direct register. Russian B2B tolerates and expects directness. Do not soften with "уважаемый" in product UI — keep it for letters and contracts only.

- ✅ "Tojlo MAIL подключён. Первая разметка писем — через 5 минут."
- ❌ "Уважаемый пользователь, имеем честь сообщить вам…"

#### Persian / Farsi (FA)

RTL layout. Voice unchanged. Persian B2B prose tends ornate; resist that pull in product UI.

- ✅ "Tojlo MAIL آماده است. برچسب‌گذاری ایمیل‌ها تا ۵ دقیقه شروع می‌شود."
- ❌ "با عرض سلام و احترام خدمت کاربر گرامی، با کمال افتخار به اطلاع می‌رسانیم…"

#### Localization Rules

L1. **Translate the meaning, not the words.** Direct dictionary equivalents that lose voice are wrong. Re-write to preserve voice.
L2. **Numbers, dates, currencies follow the locale** (see *Date / Time / Currency / Number Formatting*). Never localize the number system halfway.
L3. **Module names do not translate.** "Tojlo MAIL" stays "Tojlo MAIL" in every language. They are proper nouns.
L4. **Tagline does not translate verbatim.** Each market gets a localized tagline approved separately and registered in `i18n/taglines.json`. Track them in a tagline registry; never improvise.
L5. **AI-drafted content respects the user's outbound language.** A Turkish operator writing to a Russian customer gets a Russian draft, not a Turkish one auto-translated. The model handles this; the UI exposes the chosen language clearly above the draft.
L6. **RTL mirrors the entire layout, not just the text.** Sidebar moves to the right, directional icons flip, progress bars fill right-to-left. See the *Multilingual and RTL* section.
L7. **Honorifics belong in letters and contracts, never in UI.** UI talks to the user; UI does not greet the user.
L8. **Plurals use the locale's plural rules** (CLDR). English plural ≠ Russian plural ≠ Arabic plural — never assume two forms.

### Voice Across Surfaces

The voice is constant. The register adjusts by surface and stakes:

| Surface | Register | Word budget | Example |
|---|---|---|---|
| **Button label** | Imperative, 1–2 words | ≤ 2 | "Send draft" |
| **Page title** | Noun phrase, no verbs | ≤ 4 | "Customer activity" |
| **Section heading** | Noun phrase or short clause | ≤ 6 | "Pending commission runs" |
| **Empty state headline** | Outcome-led sentence | ≤ 8 | "No leads yet. Connect WhatsApp to start." |
| **Tooltip** | One sentence, action-oriented | ≤ 12 | "Approve this draft and Tojlo will send it now." |
| **Inline form helper** | One short sentence; what to enter, why it matters | ≤ 14 | "We'll email this address when invoices are paid." |
| **Toast / snackbar** | What happened + (optional) one undo or follow-up | ≤ 14 | "Draft sent. Undo." |
| **Error toast** | What broke + what to do | ≤ 18 | "M365 token expired. Reconnect in Settings → Integrations." |
| **Confirmation dialog body** | Plain statement of consequence + revert path | ≤ 30 | "This will permanently delete 12 customer records. You cannot undo this. Type DELETE to confirm." |
| **Onboarding step** | One sentence outcome + one sentence action | ≤ 24 | "Connect your inbox. Tojlo MAIL will start drafting replies within 5 minutes." |
| **Email subject** | Specific, scannable, no clickbait | ≤ 60 chars | "3 new leads from WhatsApp need your review" |
| **Email body** | Direct, structured, signed by Tojlo | ≤ 120 words | (see *Email Templates*) |
| **Marketing hero** | Category claim + proof | ≤ 30 | "The B2B Operating System. Twelve modules. One login. AI in every workflow." |
| **Marketing body** | Outcome → mechanism → evidence | varies | "Cut email time by 80%. Tojlo MAIL drafts replies in your customer's language. BHD's team writes 12 emails a day instead of 60." |
| **Sales-deck slide** | One claim per slide, evidenced | varies | "BHD reduced operations time from 8–11 hrs/day to 1–1.5 hrs/day in 6 months." |
| **Documentation page intro** | What this page covers, in one sentence | ≤ 20 | "Tojlo HUB orchestrates workflows across all twelve modules. This page lists every available trigger and action." |
| **API reference** | Function signature first, prose second | n/a | (auto-generated; voice rules apply to descriptions) |
| **Customer support reply** | Acknowledge → diagnose → fix → confirm | ≤ 100 words | "Got it. The token expired at 14:02. I've extended the refresh window to 7 days. Tojlo MAIL is back online — confirm at your end?" |
| **Legal / contractual** | Formal, complete, unambiguous | as needed | (see Tojlo License Agreement template) |
| **Status-page incident** | What's degraded → impact → ETA → next update | ≤ 60 words | "Tojlo HUB workflows are running with delay. Triggers fire in 5–7 min instead of < 30 sec. Estimated recovery 14:30 UTC. Next update at 14:15." |

A voice that reads the same on a button and in a contract is broken. Same voice. Different register.

### Naming and Capitalization Rules

- **Sentence case** for headings, button labels, menu items, page titles. Title Case is forbidden in product UI.
- **Numerals over words** for any number ≥ 10, and for any number that's a count, ID, money, time, or measurement (use "3 leads" not "three leads"; "page 2" not "page two").
- **No exclamation marks** anywhere in product UI. Save them for marketing copy, and even there use sparingly.
- **No emoji in product UI** by default. Emoji are allowed in: customer-authored content (email subjects, chat messages), and in the optional Celebrations setting (one emoji per milestone, never more).
- **Oxford comma** in English. Always.
- **Single quotes inside double quotes** when nesting in English copy. Don't mix.
- **Em-dashes**, not hyphens, for parenthetical breaks. With spaces around them in marketing, no spaces in compact UI strings.
- **Numerals format** with thin-space thousands separators where the locale supports it (see *Date / Time / Currency / Number Formatting*).

---

## Brand Architecture

### Model: Endorsed Brand under Ocoron

Ocoron is the **parent / endorser**. Tojlo is the **product brand** sold into the market.

- Tojlo carries its own logo, accent color, taglines, and product narrative.
- Tojlo always carries an endorsement attribution where trust matters: "Tojlo, by Ocoron." This appears in footers, first-contact emails, legal pages, and trust panels.
- Inside the Tojlo Dashboard and in marketing, the visual brand is Tojlo. Ocoron is referenced only in the footer / about / legal layer.
- Sub-products *of Tojlo* are modules (`Tojlo MAIL`, `Tojlo HUB`, etc.) — they do not get their own brand identity, only the module-naming convention above.

### When to use which brand

| Situation | Brand |
|---|---|
| Customer-facing product surfaces (dashboard, modules, portal) | **Tojlo** |
| Customer-facing marketing (`tojlo.com`, ads, social) | **Tojlo** (with "by Ocoron" in footer) |
| B2B sales materials (deck, proposal, demo) | **Tojlo** primary, **Ocoron** as the company delivering it |
| Legal and contractual documents | **Ocoron Dış Ticaret Ltd. Şti.** is the legal entity; Tojlo is named as the platform being licensed/operated |
| Engineering, infrastructure, ops blog, R&D communications | **Ocoron** |
| Job posts, recruiting | **Ocoron** (the employer) |
| Investor / grant communications | **Ocoron** (with Tojlo described as the productized output) |
| Partner integrations | **Tojlo** |

### Co-branding Rules

- **Endorsement.** "Tojlo, by Ocoron" carries in product footer, login screen, first-contact materials, and legal pages — never "Ocoron Tojlo." See *Logo → Lockups* for sizing.
- **Co-marketing with clients** (white-label, partnerships): equal optical sizing with the partner mark, clear separation, never inside the partner's logo. See lockup L-4.
- **Third-party integrations** (M365, ERPNext, Wati): show the partner's mark alongside Tojlo's at equal visual weight in integration panels and trust pages.
- **The Tojlo wordmark is never recolored, modified, distorted, or set in a text font.** Full constraints in *Logo → Misuse*.

---

## Logo

The Tojlo wordmark is the brand's primary visual asset. Until the wordmark is finalized, no Tojlo product surface ships externally — the placeholder Inter 600 setting is for internal builds only.

### Geometry

The wordmark is a custom geometric logotype. Construction follows a strict grid so the wordmark renders consistently at every size, in every medium, by any vendor.

- **Construction grid:** 5-unit cap height, 1-unit stroke width. Unit values scale with output size; ratios are fixed.
- **Letterform style:** Geometric, slightly mechanical. Sharper than Ocoron's stencil-cut style. Reads as a *product mark* — a logotype on a piece of equipment — not as a service-firm signature.
- **Distinguishing feature:** The 'j' descender is the brand's hidden hook. Every glance returns to it. It is the one detail that must never be flattened, shortened, or substituted with a standard typeface 'j'.
- **Stem joins:** Hard 90° on stems; counters optically softened by 0.5-unit interior radius.
- **Optical adjustments:** Round letters (O) +2% cap height. The 'j' descender +1.5% length. Sidebearings equal across letters.
- **Wordmark width:** Exactly 5.4× cap height. Locked. Do not condense (compress widths) or extend (expand widths).
- **Tracking:** −20 units of 1000em. Letterforms touch each other optically without merging.

### Monogram (T mark)

For square contexts where the full wordmark won't fit:

- **Glyph:** The 'T' character extracted from the wordmark, geometric center placed in a 1:1 frame, optical center adjusted +1% upward.
- **Background:** solid `#5B5BF7` (Tojlo Indigo). Glyph: `#FFFFFF`.
- **Frame radius:** 22% of edge — matches iOS/Android app-icon mask conventions; renders as a squircle on iOS, a soft-square on Android.
- **Minimum size:** 16px (favicon). Below 16px, do not use the monogram — fall back to a 1-color flat 'T' glyph at the same color contract (white on indigo or indigo on white).

Use the monogram for: favicons, browser tab icons, app icons (iOS/Android/desktop), social-media avatars, embedded-module top-bar marks at compact density, push-notification icons.

Never use the monogram where the full wordmark fits. The wordmark is the primary; the monogram is a fallback.

### Lockups

Five canonical lockups. Use only these.

- **L-1 Standalone wordmark.** Tojlo wordmark only. Use when the brand is already established in context — inside the Tojlo Dashboard chrome, on `tojlo.com` header, on a slide where the brand is already on screen.
- **L-2 Endorsed lockup ("Tojlo, by Ocoron").** Wordmark + "by Ocoron" set in Inter 400, sized at 60–80% of the Tojlo wordmark cap height, baseline-aligned to the bottom of the wordmark, separated horizontally by `--space-sm` (8px at 1× scale) or by a 1px vertical rule. Use in product footer, login screen, first-contact materials, partner directories, legal pages, sales decks (cover slide).
- **L-3 Stacked endorsed.** Wordmark on top, "by Ocoron" below in Inter 400 at 50% cap height, centered. Use only when horizontal space is constrained (mobile splash screens, vertical signage).
- **L-4 Co-marketing lockup.** Tojlo wordmark + partner mark, separated by a vertical 1px rule (`--border` color), equal optical height. Use in integration directories, partner pages, co-branded launch materials. Order: Tojlo on the left in LTR contexts, on the right in RTL contexts.
- **L-5 White-label lockup.** Tenant wordmark + "Powered by Tojlo, by Ocoron" set in `--text-muted` 12px, in the footer. The tenant's mark replaces Tojlo's in the top chrome; Tojlo's attribution survives in the footer. This lockup is required by the white-label addendum to the Tojlo License Agreement.

### Color Variants

| Background | Wordmark color | Notes |
|---|---|---|
| `--surface-0` (dark default) | `#FFFFFF` | Default product UI |
| `--surface-1` (dark cards) | `#FFFFFF` | Embedded modules |
| Light surfaces (`--surface-1` light, white) | `#5B5BF7` (Tojlo Indigo) | Marketing site light hero, light-mode UI |
| Tojlo Indigo `#5B5BF7` (accent surface) | `#FFFFFF` | Marketing accent panels, app-icon background |
| Black `#000000` | `#FFFFFF` | Press kit, formal print |
| Photographic background | `#FFFFFF` over `rgba(0,0,0,0.4)` overlay | Photo overlays only — overlay is mandatory |

For all other prohibited treatments (gradients, shadows, outlines, etc.), see *Misuse* below.

### Clear Space

Minimum clear space on all four sides equals **1× the cap height of the 'T'**. Nothing — including type, image edges, photographic content, UI chrome, partner marks — may enter this space.

For dense product chrome where the operator screen is small (mobile, embedded module headers), reduce clear space to **0.5× cap height** and document the exception in the implementation file. Below 0.5× clear space, use the monogram instead of the wordmark.

### Sizing

- **Minimum size — wordmark:** 64px width digital, 16mm width print. Below 64px width, switch to monogram.
- **Minimum size — monogram:** 16px. Below 16px, use a 1-color flat 'T' glyph.
- **Maximum size — wordmark:** No maximum. On displays >2000px width, switch from the SVG to a higher-poly variant; document the asset path in the implementation file.
- **Recommended sizes:**
  - Product top chrome: 24px height (wordmark) or 24px (monogram)
  - Login screen: 64px width minimum
  - Marketing hero: 96–192px width
  - Footer: 32px width (wordmark) or 24px (monogram)
  - Press kit: vector at any scale

### Motion Behavior

Wordmark animation is functional, never decorative.

- **First dashboard load:** 200ms fade-in from opacity 0 → 1, plus a 4px upward translate. Once per session. Never on subsequent route changes within the same session.
- **Marketing hero (first viewport entry only):** optional 400ms wordmark stroke draw-on, easing `--ease-default`. Reduced-motion users receive a fade only, no stroke draw.
- **Pre-load skeleton:** show the monogram with the skeleton shimmer (see *Motion Language*) until the wordmark asset has loaded. Replace cleanly with no flash.
- **Splash on launch (mobile / desktop apps):** 800ms display, fade out over 200ms. Never longer.
- **Forbidden:** spinning, bouncing, pulsing, parallax, marquee, attention-loops. The mark is not a status indicator.

### Misuse — Forbidden Treatments

Call these out in design review and reject them at merge:

- ❌ Recreating the wordmark in a text font (Helvetica, Arial, Inter, system fonts). The wordmark is **always** an SVG asset.
- ❌ Stretching, condensing, italicizing, oblique-skewing, or 3D-extruding.
- ❌ Recoloring with brand-incompatible colors. Only the variants above are allowed.
- ❌ Placing inside a circle, box, badge, or container shape (unless using the monogram, which has its own frame).
- ❌ Embedding inside another company's logo or visual identity.
- ❌ Cropping. The wordmark is a single unit and must always render in full, including the 'j' descender. The descender is the brand.
- ❌ Adding drop shadows, glows, gradients, embosses, bevels, glassmorphism, or any other layer effect.
- ❌ Animating on every page transition or for ambient decoration.
- ❌ Using the monogram and wordmark together in the same surface (pick one).
- ❌ Pairing with another logotype at unequal optical heights (co-marketing lockups must be optically equal, not pixel-equal).
- ❌ Using the wordmark as a watermark, repeating background, or texture pattern.
- ❌ Placing on a background that fails the WCAG AA contrast requirement against the chosen wordmark color (3:1 minimum for large logo display).

### Asset Naming and Delivery

The Tojlo wordmark and monogram ship as named assets with a fixed path:

```
/brand/tojlo/
├── wordmark/
│   ├── tojlo-wordmark-white.svg          # for dark surfaces
│   ├── tojlo-wordmark-indigo.svg         # for light surfaces
│   ├── tojlo-wordmark-black.svg          # for press / print
│   └── tojlo-wordmark.{1x,2x,3x}.png     # raster fallbacks
├── monogram/
│   ├── tojlo-monogram-indigo-bg.svg      # default app icon
│   ├── tojlo-monogram-white-bg.svg       # alt for light contexts
│   ├── tojlo-monogram.ico                # favicon multi-resolution
│   └── tojlo-monogram.{180,192,512}.png  # iOS/Android/desktop app icon sizes
├── lockups/
│   ├── tojlo-by-ocoron-horizontal-white.svg
│   ├── tojlo-by-ocoron-horizontal-indigo.svg
│   ├── tojlo-by-ocoron-stacked-white.svg
│   └── tojlo-by-ocoron-stacked-indigo.svg
└── press/
    ├── tojlo-press-kit.zip
    └── README.md
```

Never check in alternate, modified, or "experimental" wordmark assets to product code paths. Experimental work lives in `/brand/_drafts/` and is reviewed before promotion.

---

## Color System

### Primary Accent (Tojlo Override)

| Token | Hex | Role |
|---|---|---|
| `--color-accent` | `#5B5BF7` | **Tojlo Indigo** — primary accent, CTAs, active states, links, primary buttons, progress bars, focus rings, brand highlights |
| `--color-accent-hover` | `#7676FF` | Accent hover state |
| `--color-accent-muted` | `rgba(91, 91, 247, 0.12)` | Accent backgrounds (tags, badges, subtle highlights, selected states) |

**Rationale:** Indigo is the shared Ocoron accent (`#5B5BF7`). Tojlo inherits it unchanged. Sits cleanly next to ERPNext blue, Wati green, and M365 blue when modules are embedded.

### Secondary Semantic Colors (Inherited from Ocoron, Unchanged)

| Token | Hex | Role |
|---|---|---|
| `--color-secondary` | `#F5A623` | Warnings, premium/upgrade nudges |
| `--color-danger` | `#FF4444` | Errors, destructive actions, critical alerts |
| `--color-success` | `#27AE60` | Confirmations, completed states, positive deltas |
| `--color-info` | `#2980B9` | Informational badges, tooltips, neutral status |
| `--color-purple` | `#9B59B6` | Category coding, auxiliary status |

### Surface Hierarchy

**Inherited from Ocoron unchanged.** Both dark mode (default) and light mode are mandatory — same enforcement (OS detection + manual toggle + persistence). Do not re-tint surfaces with the Tojlo accent — surfaces stay neutral so the accent earns attention when it appears.

### Module Color Coding (Tojlo-Specific Addition)

Tojlo Dashboard sidebars and module switchers may color-code modules by **layer**, not by individual module. This keeps the color system disciplined:

| Layer | Indicator color | Token |
|---|---|---|
| Core | `#5B5BF7` (accent) | `--color-accent` |
| Intelligence | `#9B59B6` | `--color-purple` |
| Growth | `#F5A623` | `--color-secondary` |

Use these as 3px left-rail indicators on sidebar items or as 9px micro-label dot tags. **Never** color the module icon itself — icons stay monochrome (`--text-primary` for active, `--text-muted` for inactive).

---

## Typography

**Inherited from Ocoron unchanged.** Same fonts, same scale, same rules.

Two Tojlo-specific patterns:

### Module Chrome Type

Module names in chrome (sidebars, tab bars, breadcrumbs):

```
Font: Inter 500
Size: 11px
Case: UPPERCASE
Letter-spacing: 1px
Color: var(--text-primary) when active, var(--text-muted) when inactive
```

This matches Ocoron's existing micro-label pattern, formalized for module display.

### Numeric KPI Display

Operator dashboards lean heavily on numeric KPIs. Use Ocoron's "Data large" type spec without modification:

```
Font: JetBrains Mono 300
Size: 28px
Letter-spacing: -0.5px
```

For supporting deltas next to KPIs:

```
Font: JetBrains Mono 400
Size: 13px
Color: var(--color-success) for positive, var(--color-danger) for negative
Prefix: "+" / "−" / "=" (use proper minus sign U+2212, not hyphen-minus)
```

---

## Iconography

Tojlo uses **Lucide** as the primary icon library, with custom icons reserved for module identity.

### Library

- **Lucide React** for product UI (already used by shadcn/ui in the saas-skeleton scaffold).
- **Stroke width:** 1.5px at 16px viewport, 2px at 24px viewport. Consistent across the product.
- **Style:** Outline (no filled icons in core UI). Filled variants only for selected/active states where the outline+fill pair improves scanability (checkboxes, radio buttons, toggle confirmations).
- **Color:** inherit from `currentColor`. Default `--text-body`. Active `--color-accent`. Disabled `--text-muted` at 40% opacity.
- **Stroke caps and joins:** rounded. No square or beveled caps anywhere.

### Sizing

| Context | Icon size | Stroke |
|---|---|---|
| Inline body text | 16px | 1.5px |
| Sidebar | 20px | 1.5px |
| Tab bar | 18px | 1.5px |
| KPI card header | 20px | 1.5px |
| Module card | 24px | 1.5px |
| Toolbar | 18px | 1.5px |
| Button (with label) | 16px | 1.5px |
| Floating action / icon-only button | 20px | 1.5px |
| Empty state hero | 48px | 2px |
| Onboarding hero | 64px | 2px |

### Module Icons

Each Tojlo module has a custom monochrome icon:

| Module | Icon concept | File |
|---|---|---|
| Tojlo Dashboard | Grid of 4 squares | `dashboard.svg` |
| Tojlo OPS | Box with directional flow arrow | `ops.svg` |
| Tojlo HUB | Central node with 4 spokes | `hub.svg` |
| Tojlo CHAT | Speech bubble with W mark | `chat.svg` |
| Tojlo MAIL | Envelope with M cut-out | `mail.svg` |
| Tojlo PORTAL | Door with arrow-out | `portal.svg` |
| Tojlo VAULT | Locked box | `vault.svg` |
| Tojlo AUTH | Key with cut profile | `auth.svg` |
| Tojlo TI | Magnifying glass with chart | `ti.svg` |
| Tojlo WEB | Globe with anchor | `web.svg` |
| Tojlo MARKETS | Trending arrow upward | `markets.svg` |
| Tojlo REACH | Targeting reticle | `reach.svg` |
| Tojlo OUTREACH | Outbound arrows | `outreach.svg` |

Module icons follow the same 1.5px stroke at 16px viewport for consistency with Lucide. Color rules identical to Lucide icons. Icons live at `/brand/tojlo/icons/modules/`.

### Custom Icons

When a Lucide icon doesn't exist for a needed concept, add a custom icon to the Tojlo icon library. Custom icons must match Lucide's style:

- 24px artboard, 1.5px stroke, rounded line caps, rounded line joins.
- No fills (outline only).
- Single-color, inherits `currentColor`.
- Optical balance, not mathematical centering.
- Reviewed and approved before merge into the library.

Submitting a one-off icon inline is forbidden. Icons live in the library or they don't exist.

### Iconography Rules

I1. Never use multicolor icons in product UI. Color is the accent's job; icons stay monochrome and inherit from context.
I2. Never place text inside icons. If a label is needed, label the icon externally with Inter 500 micro-label type.
I3. Never animate icons for decoration. Animate only when the icon represents an active state (loading spinner, syncing, recording, AI-thinking).
I4. Pair every icon with a text label in the first 3 occurrences a user sees of it. Icon-only is reserved for tab bars and toolbars where the labels would be too dense, and even there a tooltip with the label must appear within `--motion-default` of hover.
I5. Match weight to typography. 1.5px stroke + Inter 400 body. Don't pair heavy-stroke icons with light body type or vice versa.
I6. Module icons stay monochrome. Layer color (Core/Intelligence/Growth) goes on the indicator (left rail or dot), never on the icon glyph itself.
I7. The Lucide library is the source of truth. If you need an icon, search Lucide first. Only after confirming Lucide does not have the concept (or does not have it in the right metaphor) may you commission a custom icon.
I8. Icons must remain legible at minimum size (16px). Detail beyond what reads at 16px is forbidden — it adds noise without adding meaning.

---

## Motion Language

Motion in Tojlo is functional, never decorative. Every animation communicates one of: state change, attention direction, system status, or progress. Motion that does none of those is removed.

### Duration Scale

| Token | Value | Use |
|---|---|---|
| `--motion-instant` | `0ms` | State swaps where motion would distract (toggle states, immediate value updates) |
| `--motion-fast` | `100ms` | Hover, focus, small surface transitions |
| `--motion-default` | `150ms` | Default. Most transitions. Inherited from Ocoron's `0.15s ease`. |
| `--motion-slow` | `250ms` | Modal, drawer, sheet enters and exits |
| `--motion-deliberate` | `400ms` | Onboarding step transitions, hero animations on first viewport entry |
| `--motion-celebration` | `600ms` | Single-shot success animations (commission run completed, milestone reached) |

### Easing

| Token | Curve | Use |
|---|---|---|
| `--ease-default` | `cubic-bezier(0.16, 1, 0.3, 1)` | Almost everything. Soft enter, firm settle. |
| `--ease-linear` | `linear` | Progress bars, indeterminate loaders only |
| `--ease-spring` | `cubic-bezier(0.5, 1.5, 0.5, 1)` | Discrete success cues only (success toast, milestone badge) |
| `--ease-emphasis` | `cubic-bezier(0.4, 0, 0.2, 1)` | When direction matters more than feel (drawer slides, sheet pulls) |

Avoid stacking eases. One animation, one curve.

### Canonical Motion Patterns

**Toast / snackbar enter:** `translateY(8px) → 0`, opacity `0 → 1`, `--motion-default` `--ease-default`. Exit: reverse.

**Modal enter:** scrim opacity `0 → 0.6` in `--motion-fast`, modal `translateY(8px) scale(0.98) → 0 1` in `--motion-default` `--ease-default`. Exit: reverse, both layers in parallel.

**Drawer enter (right):** `translateX(100%) → 0`, `--motion-slow` `--ease-emphasis`. Exit: reverse. RTL: mirror to enter from left.

**Sheet enter (bottom, mobile):** `translateY(100%) → 0`, `--motion-slow` `--ease-emphasis`.

**Tab change:** instant content swap, no transition. Cross-fades on tab content read as lag.

**Route change (within Dashboard):** instant content swap, with 80ms skeleton flash if data is still loading. No fade-on-route.

**Skeleton shimmer:** `linear-gradient` translated `-100% → 100%` over `1500ms linear`, infinite. Only on initial load, never as a permanent state.

**AI-thinking indicator:** three dots, each `opacity 0.3 → 1 → 0.3` staggered by 150ms, `--ease-default`. Used only while AI is actively processing a user-initiated action.

**Success celebration (commission run, milestone):** check-mark stroke draw-on over `--motion-celebration` with `--ease-spring`, no confetti, no sound (sound is opt-in per user, see *Sound and Haptics*).

**Error shake:** `translateX(-4px → 4px → -2px → 0)` over 250ms `--ease-default`. Triggered once per error. Never on inline-validation errors as the user types — only after submit.

**Hover lift:** `translateY(-1px)` `--motion-fast` `--ease-default`. Applies to cards, buttons, list items.

**Press feedback (mobile):** `translateY(1px) scale(0.98)` `--motion-fast` `--ease-default`, with haptic light impact where the device supports it.

**Focus ring fade-in:** `opacity 0 → 1` `--motion-fast` `--ease-default`. Focus ring is 2px solid `--color-accent`, offset 2px, never animated beyond opacity.

### Forbidden Motion (M-Rules)

M1. No bounce on default transitions. `--ease-spring` is reserved for celebration only.
M2. No motion longer than `--motion-deliberate` outside of celebrations.
M3. No infinite animations except progress, loading, and AI-thinking indicators.
M4. No parallax. No marquee scroll. No animated backgrounds.
M5. No motion that delays user input. If the user can act, they can interrupt the animation; animations must not block input.
M6. No fading out before fading in. State changes are direct: previous state out, next state in, in parallel where possible.
M7. No animation triggered solely by scroll position (scroll-linked reveals are forbidden in product UI; allowed sparingly on marketing pages with `prefers-reduced-motion` fallback).
M8. No celebration animation without a real milestone. Don't celebrate "form saved" — that's the system doing its job.

### Reduced Motion

Users with `prefers-reduced-motion: reduce` get:

- All transitions reduced to `--motion-instant` (0ms) except progress and loading indicators (which retain their motion because they communicate active state).
- Translate-based enters become opacity 0/1 swaps.
- Skeleton shimmer becomes a static `--surface-3` block.
- AI-thinking indicator becomes a single static `…` glyph.
- Wordmark animations are replaced with fade only.
- Confirmation: never gate functionality behind motion. The product must be fully usable in reduced-motion mode.

### Sound and Haptics

Sound is **opt-in per user**. Default is silent. When enabled:

- Success: 80ms 880Hz soft attack, 120ms decay. Pleasant but unobtrusive.
- Error: 60ms 220Hz, no decay tail. Brief, distinct from success.
- Notification: 100ms two-tone chime (440Hz + 660Hz, simultaneous). Quiet enough to be background.
- Volume: capped at 30% of system volume. Respects system mute.

Haptics on mobile (where supported):

- Light impact: button press, toggle.
- Medium impact: confirmation, successful action.
- Heavy impact: warning, destructive confirm.
- Never use haptics for routine state changes — they fatigue.

---

## Density Modes

Operators run Tojlo eight hours a day. Density is a real choice, not a power-user toggle. Three modes; the user picks once during onboarding and changes in Settings → Display.

### Comfortable (default)

| Token | Value |
|---|---|
| Card padding | 16px (`--space-md`) |
| List row height | 44px |
| Table row height | 40px |
| Input height | 36px |
| Button height | 36px |
| Body line height | 1.5 |

The default for new users. Matches the Ocoron base spec exactly.

### Compact (power user)

| Token | Value |
|---|---|
| Card padding | 12px |
| List row height | 36px |
| Table row height | 32px |
| Input height | 32px |
| Button height | 32px |
| Body line height | 1.45 |

For operators who scan large datasets daily. Reduces vertical space ~20% without breaking touch targets on desktop.

### Spacious (accessibility / large displays)

| Token | Value |
|---|---|
| Card padding | 20px (`--space-md` + 4) |
| List row height | 52px |
| Table row height | 48px |
| Input height | 40px |
| Button height | 40px |
| Body line height | 1.6 |

For users on large displays, with motor accessibility needs, or who prefer breathing room. Default for tablets in landscape.

### Density Rules

D1. Density toggle changes only spacing and component sizing. **Never** change typography size, color, iconography, motion, or content based on density. Cognitive load must remain identical across modes.
D2. Touch targets stay ≥ 44px on touch devices regardless of density. Compact mode automatically falls back to comfortable on touch devices.
D3. Density preference is per user, not per tenant. Power users in the same workspace may choose differently.
D4. Density preference syncs across the user's devices via Tojlo AUTH so the operator gets a consistent experience whether they're at desktop or mobile.
D5. Embedded modules (Tojlo OPS via ERPNext, Tojlo HUB via n8n) inherit density via injected CSS variables where the embedded vendor allows it; otherwise they retain their native density. Document the integration limit.

---

## Component Patterns

**All Ocoron component patterns apply unchanged.** Tojlo adds the following Tojlo-specific patterns:

### Module Card

Used on the Dashboard home grid and in module switchers.

```
Background: var(--surface-1)
Border: 1px solid var(--border)
Border-radius: 8px
Padding: 16px
Layout: Module icon (24px, monochrome) + module name (Inter 500, uppercase, 11px) + one-line status (Inter 400, 12px, var(--text-muted))
Hover: background var(--surface-3), translateY(-1px), 0.15s ease
Active: 2px left border in --color-accent
```

### KPI Card

Used on operator dashboards.

```
Background: var(--surface-1)
Border: 1px solid var(--border)
Border-radius: 8px
Padding: 16px
Structure:
  Row 1: micro-label (Inter 500, uppercase, 10px, --text-muted) — KPI name
  Row 2: large numeric (JetBrains Mono 300, 28px, --text-primary) — current value
  Row 3: delta (JetBrains Mono 400, 13px, success/danger) — period change
Optional: 4px progress bar at bottom for goal-tracked KPIs
```

### Activity Feed Item

Used on the Dashboard activity rail and inside modules.

```
Layout: 24px module icon + content + timestamp
Module icon: monochrome, --text-muted by default
Module label (above content): Inter 500, uppercase, 10px, letter-spacing 1.5px, color = layer indicator (accent / purple / secondary)
Content: Inter 400, 14px, --text-body
Timestamp: Inter 400, 12px, --text-muted
Always name the module that produced the event ("Tojlo HUB completed weekly commission run").
Hover: --surface-3, no lift
```

### SSO Entry Pattern

Tojlo Dashboard entry surface (`tojlo.com` / `bhd.tojlo.com` / `<tenant>.tojlo.com`):

```
Layout: centered single column, 360px max width, vertical center on viewport
Logo: top, Tojlo wordmark, 64px width minimum
Tagline below logo: "The B2B Operating System." in Inter 400, 14px, --text-muted
Auth control: self-hosted auth UI (Tojlo AUTH / `fabrik-lib/fastapi-user-auth`) themed with Tojlo tokens
Footer: "Tojlo, by Ocoron · v[X.Y]" in Inter 400, 12px, --text-muted
```

### Embedded Module Frame

When Tojlo embeds a third-party module (ERPNext, n8n, Wati inbox), wrap it in this frame:

```
Top bar: 40px height, --surface-1 background, --border bottom border
  Left: module name (Tojlo OPS, Tojlo HUB, etc.) in Inter 500, uppercase, 11px
  Right: status pill (connected / syncing / error) using inherited pill pattern
Body: full-bleed iframe, no padding
Bottom hint (optional, dismissible): "This is Tojlo OPS, powered by ERPNext." in --text-muted, 12px
```

The embedded vendor's chrome (e.g. ERPNext top nav) should be hidden via vendor-specific CSS injection where the vendor allows it. The Tojlo top bar is the source of truth for navigation.

---

## Data Tables

Operators live in tables. Every Tojlo table is built from this spec.

### Anatomy

```
┌────────────────────────────────────────────────────────────────────┐
│ Table toolbar                                                       │
│ [search] [filter chips] [view selector]    [bulk actions] [export] │
├────────────────────────────────────────────────────────────────────┤
│ □ Header — Customer ↑   │ Country │ Last order      │ Status   │ ⋯ │
├────────────────────────────────────────────────────────────────────┤
│ □ Kandil Glass          │ TR      │ 2026-05-12 10:14│ Active   │ ⋯ │
│ □ Pegasus Containers    │ DE      │ 2026-05-09 17:38│ Active   │ ⋯ │
│ □ Atlas Trading         │ AE      │ 2026-04-28 09:02│ Inactive │ ⋯ │
├────────────────────────────────────────────────────────────────────┤
│ Footer — selection summary     │ pagination │ rows per page │ total│
└────────────────────────────────────────────────────────────────────┘
```

### Header Row

- **Background:** `--surface-1`, sticky on scroll.
- **Border:** 1px `--border` bottom.
- **Type:** Inter 500, uppercase, 11px, letter-spacing 0.5px, `--text-muted`.
- **Sort:** click column header to sort. Active sort: column header text becomes `--text-primary`, sort indicator (↑ / ↓) appears in `--color-accent`. Three-state cycle: ascending → descending → unsorted.
- **Resize:** column dividers are draggable on hover (`col-resize` cursor). Width persists per user per table in Tojlo AUTH preferences.
- **Reorder:** columns reorderable via drag-from-header-handle. Order persists per user per table.
- **Sticky columns:** the leftmost column (selection checkbox + first data column) and the rightmost column (row actions) are sticky. Middle columns scroll horizontally on overflow.

### Body Rows

- **Background:** `--surface-0` default. Even-row alternation is **forbidden** — operators read by content, not by stripe. Use whitespace and clear row borders instead.
- **Border:** 1px `--border` between rows.
- **Hover:** `--surface-3`, no lift, no shadow. Cursor `default` unless the row is clickable, then `pointer`.
- **Selected:** `--color-accent-muted` background, 2px left border in `--color-accent`.
- **Type:** Inter 400, 14px (Comfortable density), `--text-body`.
- **Numeric cells:** JetBrains Mono 400, 13px, right-aligned. Decimals align on the decimal point (use `font-variant-numeric: tabular-nums`).
- **Status cells:** use the pill pattern. Color-coded pills only for status that maps to one of the semantic colors (success / danger / info / secondary). Default status: neutral pill in `--surface-2` background, `--text-body` text.
- **Truncation:** long text truncates with ellipsis. Hover reveals full content in a tooltip after 400ms.

### Selection

- **Checkbox column:** leftmost. Always present for multi-select tables. Header checkbox toggles all visible rows; indeterminate state when some-but-not-all are selected.
- **Range select:** Shift+click selects range from last-clicked to current.
- **Selection summary:** appears in the footer when ≥ 1 row is selected. Format: "12 selected · Clear · [Bulk action button] · [Bulk action button]". Bulk actions are also exposed in the toolbar.

### Row Actions

- **Per-row menu:** rightmost column, icon-only button (`MoreHorizontal` Lucide icon, 16px). Click opens a dropdown menu of row-scoped actions.
- **Quick actions on hover:** for high-frequency tables (Tojlo MAIL inbox, Tojlo CHAT thread list), 1–3 quick-action icons appear on row hover, replacing the `⋯` button.
- **Destructive row actions** require a confirmation dialog with the row's primary identifier in the dialog body.

### Filtering

- **Filter chips:** appear in the toolbar above the table. Each chip is an active filter. Click to edit; click ✕ to remove.
- **Add filter:** "+ Add filter" button opens a popover with: column selector → operator → value. Operators depend on column type (text: contains/equals/starts-with; date: before/after/between/in-the-last; number: =/≠/</>/between; status: in/not-in).
- **Saved views:** the combination of filters + sort + visible columns is saveable as a named view. Per user. Tabs at the top of the table show saved views.

### Pagination and Loading

- **Pagination:** server-side. Footer shows `page X of Y · ‹ Prev · Next ›` and `rows per page: 25 / 50 / 100 / 250`.
- **Total:** displayed in the footer as "1,247 rows" (locale-formatted). If the count is expensive to compute, show "… rows" until it resolves.
- **Loading state:** skeleton rows that match the row height of the configured density. Skeleton shimmer per the motion spec. Never an empty `<tbody>` while loading.
- **Virtualization:** required for tables with > 200 rows on screen. Use `@tanstack/react-virtual`. Row height must be fixed in virtualized mode; if rows must vary, use measured-row mode and accept the perf cost.

### Empty and Error States

- **Empty state (no data yet):** see *States — Empty* below. Tables in true-empty state show the full empty-state component, not just a blank tbody.
- **Empty state (filters return zero rows):** in-table message: "No rows match these filters." with a "Clear filters" button. Different from "no data yet."
- **Error state:** if data load fails, replace the tbody with: error icon (28px), one-sentence what-failed, "Retry" button. Toolbar remains active.

### Export

- **Format:** CSV (UTF-8), TSV, or XLSX. JSON for technical users.
- **Scope:** "Export selected" if rows are selected; "Export all" with a confirmation dialog showing row count if > 10,000 rows.
- **Filename pattern:** `tojlo-{module}-{view-name}-{YYYYMMDD-HHmm}.{ext}` (UTC).
- **Locale:** dates and numbers in the exporting user's locale.
- **Audit:** every export is logged in Tojlo AUTH audit log with user, timestamp, table, row count, and filename.

### Density Mapping

Row heights from the *Density Modes* section apply directly. Cell padding scales: `--space-md` Comfortable, 12px Compact, 20px Spacious.

### Table Rules

TBL1. **No striped rows.** Whitespace and borders only.
TBL2. **No row backgrounds carrying status meaning.** Status goes in a status cell with a pill, never on the row's background. (Selected and hover are interaction states, not status.)
TBL3. **Numeric columns are tabular monospace.** Always. Mixing proportional and tabular numerals in the same table is a bug.
TBL4. **Server-side pagination, sort, and filter** for tables backed by databases. Client-side only for already-loaded ≤ 100 rows.
TBL5. **Sticky header.** Always. Operators scroll long tables; losing the header is a usability bug.
TBL6. **Column widths persist** per user per table. Never reset on reload unless the user clicks "Reset columns."
TBL7. **Saved views are scoped to the user** by default; "Share view" promotes a view to workspace-wide and requires write permission on the table.
TBL8. **Bulk actions confirm before executing** when destructive or > 50 rows. Show the count in the confirm dialog.
TBL9. **Row click does not navigate by default.** Row click selects (toggles checkbox). Navigation requires an explicit link in a cell — usually the first data column, styled as a link.
TBL10. **Inline editing** is opt-in per table. When enabled, double-click a cell to edit, Enter to save, Esc to cancel. Save state shown in the cell with a subtle indicator (`--motion-fast` opacity flash on save).

---

## Forms and Inline Editing

Operators fill forms hundreds of times a day. Friction here is the single largest avoidable cost in operator tools.

### Form Layout

- **Single-column** forms by default. Two-column forms are allowed only when paired fields are conceptually inseparable (e.g. "First name / Last name", "City / Postal code", "Start date / End date").
- **Field width:** match content — 280px for short text (names, codes), 480px for longer text (descriptions), 100% for textareas. Do not stretch all fields to container width by default; that breaks scanability.
- **Vertical rhythm:** `--space-lg` (24px) between field groups, `--space-md` (16px) between label and input, `--space-sm` (8px) between input and helper/error.
- **Section headings:** Inter 500, 14px, uppercase, letter-spacing 0.5px, `--text-muted`. Used to group related fields.

### Labels

- **Position:** above the input. Always. Labels-inside-input is forbidden (placeholder-as-label confuses screen readers and breaks autofill).
- **Type:** Inter 500, 13px, `--text-primary`.
- **Required:** trailing red asterisk in `--color-danger`. Optional fields get no marker; "(optional)" is allowed when most fields are required and a few are not.

### Inputs

- **Height:** matches density mode (36 / 32 / 40px).
- **Padding:** `--space-sm --space-md` (8px 16px).
- **Background:** `--surface-1`.
- **Border:** 1px `--border`.
- **Focus:** 2px `--color-accent` ring at 2px offset, no border color change.
- **Error:** 1px `--color-danger` border, no shake-on-focus, helper text replaced by error text in `--color-danger`.
- **Disabled:** background `--surface-0`, text `--text-muted`, cursor `not-allowed`. Never gray out a field without explanation; pair with helper text if disabled state is conditional.
- **Read-only (vs disabled):** read-only fields look like inputs but have no border and `--text-body` color. Used for system-set fields the user can't change but should still see.

### Validation

- **Validation timing:** validate on blur, never on every keystroke. Exception: password-strength meter, which validates live to give feedback as the user types.
- **Submit-time validation:** all fields revalidate on submit. Focus jumps to the first error; subsequent errors are visible inline, not in a top banner.
- **Error text:** one sentence, ≤ 14 words, says what's wrong and what to do. Never "Invalid input."
  - ✅ "Phone must include country code (e.g. +90 532 ...)."
  - ❌ "Invalid phone number."
- **Async validation** (e.g. "is this email already registered?"): debounce 500ms after last keystroke. Show a small spinner inside the input on the right. Result appears as inline helper or error.

### Save Behavior

- **Autosave is the default for inline edits and per-record settings.** Save on blur, after a 500ms debounce. Show a subtle "Saved" pill in `--text-muted` next to the field for 1.5s after save.
- **Explicit save** for multi-step wizards, sensitive operations (creating records, sending emails, signing contracts), and any form where partial data is dangerous.
- **Dirty state warning:** if the user navigates away with unsaved explicit-save data, intercept and confirm: "You have unsaved changes. Discard them?" with `Discard` and `Cancel`. Never auto-discard.
- **Optimistic update:** for autosave, update the UI immediately, then save in the background. On failure, revert the UI and surface a non-blocking error toast.

### Wizards

For multi-step flows (onboarding, large data imports, complex configurations):

- **Stepper:** horizontal at the top, max 5 steps. More than 5 steps means the wizard is doing too much.
- **Progress indicator:** completed steps in `--color-accent`, current step in `--color-accent` filled, future steps in `--text-muted` outlined.
- **Navigation:** "Back" and "Continue" buttons in the footer. "Continue" is disabled until the current step's required fields validate. "Back" never validates — it just navigates.
- **Save and exit:** every step has "Save and exit" as a tertiary action. Wizard state persists per user; resume from the same step on next visit.
- **Skip:** skippable steps have a "Skip for now" link, never a button. Required steps cannot be skipped.

### Inline Editing

Used in tables and detail views where editing one field shouldn't require a modal:

- **Affordance:** double-click cell, or hover to reveal an edit pencil icon, or click directly if the field is a known editable type.
- **Edit mode:** cell becomes an input matching its type (text, number, date, select, etc.). Enter saves; Esc cancels; Tab saves and moves to next cell.
- **Save indicator:** brief `--motion-fast` opacity flash on the cell on save, plus a `Saved` micro-label that fades over `--motion-deliberate`.
- **Conflict detection:** if another user updates the same field while you're editing, show "Updated by [user] [time ago]. Reload to see latest." in the cell as a non-blocking warning.

### Form Rules

F1. **Labels above inputs.** Always.
F2. **Validate on blur, not on keystroke.** Live validation is allowed only when it provides positive feedback (password strength) or prevents data loss (max-length warning).
F3. **One error message per field.** Don't stack a list of validation rules.
F4. **Autosave by default; explicit save when partial data is dangerous.**
F5. **Disabled fields explain themselves.** If a field is disabled, the user should know why without asking support.
F6. **Required fields use the asterisk; optional fields use no marker.** Don't mark every field with "(optional)" — that's noise.
F7. **No reset / clear button** unless the form is for ad-hoc query input. Forms creating records should never offer "reset all."
F8. **Submit button label states the action.** "Send invoice," "Create customer," "Approve commission run." Never "Submit," "OK," or "Save changes" if a more specific verb fits.

---

## Search and Command Palette

The command palette (⌘K / Ctrl+K) is the spine of the operator's day. Global, AI-aware, and capable of running actions — not just navigating.

### Trigger

- **Keyboard:** ⌘K (macOS), Ctrl+K (Windows/Linux), `/` from any non-input focus.
- **Pointer:** persistent search field in the top bar of the Dashboard, 360px wide, with the `⌘K` hint on the right.
- **Focus:** opens with focus on the search input, cursor at end. Esc closes.

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│ 🔍 [Search or run a command…]                          esc │
├──────────────────────────────────────────────────────────────┤
│ Suggestions                                                  │
│ ⏱ Recent: Kandil Glass                                       │
│ ⏱ Recent: Send weekly commission run                          │
│                                                              │
│ ✨ Ask Tojlo                                                  │
│ ✨ "How much commission did we earn from BHD in April?"      │
│                                                              │
│ Customers                                                    │
│ 👤 Kandil Glass                          (TR · last May 12)  │
│ 👤 Pegasus Containers                    (DE · last May 9)   │
│                                                              │
│ Actions                                                      │
│ ⚡ Send draft to Kandil Glass             ⏎                   │
│ ⚡ Run weekly commission report           ⏎                   │
│ ⚡ Export this table                      ⏎                   │
│                                                              │
│ Navigate                                                     │
│ 🧭 Tojlo MAIL                                                │
│ 🧭 Tojlo HUB · Workflows                                     │
└──────────────────────────────────────────────────────────────┘
```

### Result Categories

The palette returns five categories, in order:

1. **Recent** — last 5 user actions and entities. Personal to the user.
2. **Ask Tojlo** — an AI-search affordance. The user's query rephrased as a natural-language ask. Triggers Tojlo TI.
3. **Entities** — customers, suppliers, deals, invoices, leads matching the query. Categorized by type.
4. **Actions** — verbs the user can run from the palette. Highest-frequency: "Send draft," "Run report," "Export," "Add note," "Tag as…".
5. **Navigate** — module and route shortcuts.

### Result Row

```
[icon] [primary label]    [secondary metadata]    [shortcut hint]
```

- **Icon:** 16px, monochrome, `--text-muted`. Active row icon: `--color-accent`.
- **Primary label:** Inter 400, 14px, `--text-primary`.
- **Secondary metadata:** Inter 400, 13px, `--text-muted`. Right-aligned.
- **Shortcut hint:** keyboard shortcut for the row's action, set in `kbd`-styled chips with JetBrains Mono 11px on `--surface-2`.
- **Active row:** `--color-accent-muted` background.

### Keyboard

- **↑ / ↓:** navigate results.
- **⏎:** activate active row.
- **⌘⏎:** open active row in a side panel without leaving the palette (preview mode).
- **Tab:** scope to next category (Recent → Ask Tojlo → Entities → Actions → Navigate).
- **Esc:** close palette. If a search is in progress, first Esc clears the input; second Esc closes.

### AI Search ("Ask Tojlo")

When the user's query is a question (detected by ending with `?` or by NL classifier), the palette surfaces an "Ask Tojlo" suggestion that runs a Tojlo TI query. Result appears in a side panel:

- **Answer:** generated by the model, with inline citations to the records that support it (clickable to open the record).
- **Confidence indicator:** see *AI Interaction Patterns — Confidence and Citation*.
- **Refine:** the user can refine the question; the panel keeps the conversation history.
- **No hallucinations:** if the model can't ground the answer in records, it says so explicitly: "I couldn't find records to answer that. Try refining the question."

### Palette Rules

P1. **Palette is global.** Available from every screen, every module, every embedded surface.
P2. **Palette never closes on result click without action.** Activating a result either runs the action or opens the entity. Never both, never neither.
P3. **Recent is personal.** Never share recent across users in a workspace.
P4. **No paid placement.** Palette results are ranked by recency, exact match, and relevance. Never by promotion.
P5. **Latency budget:** first results visible within 100ms of typing the second character. AI results may take longer; show the AI-thinking indicator until they arrive.

---

## Charts and Data Visualization

Charts in Tojlo are restrained, scannable, and consistent — never decorative.

### Chart Library

- **Recharts** as the default chart library (declarative, React, MIT). Charts use the Tojlo token system via theme overrides.
- **Tremor** allowed for KPI-card-style chartlets that ship pre-themed.
- **Custom D3** allowed only for visualizations that no library provides — and they must follow the rules below as if hand-built.

### Color

- **Single-series:** `--color-accent` (Tojlo Indigo).
- **Two-series comparison:** `--color-accent` and `--color-purple`. (Comparing this period vs last period: this in accent, last in purple at 50% opacity.)
- **Categorical (≤ 6 categories):** in this order, do not skip — `--color-accent`, `--color-success`, `--color-secondary`, `--color-info`, `--color-purple`, `--color-danger`.
- **Categorical (> 6 categories):** group lower-frequency categories as "Other." Do not introduce new colors; if more than 6 lines are needed, the chart is wrong.
- **Semantic:** time-series with positive-vs-negative states use `--color-success` and `--color-danger`. Status pies use the status pill colors.
- **Negative space:** prefer negative space over decorative fills. Bar charts have transparent bars by default with 1px `--color-accent` borders, filled only on hover.

### Type

- **Axis labels:** Inter 400, 11px, `--text-muted`.
- **Tick labels:** JetBrains Mono 400, 11px, `--text-muted`. Tabular numerals.
- **Chart title:** Inter 500, 14px, `--text-primary`.
- **Chart subtitle / context:** Inter 400, 12px, `--text-muted`.
- **Legend:** Inter 400, 12px, `--text-body`.

### Grid and Axes

- **Y-axis grid:** 1px `--border` lines at major ticks. 4–6 ticks total. Never more.
- **X-axis baseline:** 1px `--border`.
- **Y-axis line:** hidden. The grid lines do the work.
- **Zero line:** visible only when the data range crosses zero. 1px `--text-muted`, never `--color-accent`.
- **Axis padding:** include enough whitespace to separate the leftmost / rightmost data point from the chart edge by `--space-md`.

### Interactivity

- **Hover:** crosshair on time-series; bar / point highlight on categorical. Tooltip appears within `--motion-fast` of hover.
- **Tooltip:** 1px `--border` on `--surface-2`, padded `--space-sm --space-md`. Title: time period or category. Body: each series with its color dot, name, and value (JetBrains Mono).
- **Click:** opens the underlying records in a side panel. Charts must always allow drill-down to the raw rows.
- **Brush / zoom:** allowed on time-series longer than 90 days. Brush selection is `--color-accent-muted` with 1px `--color-accent` border.

### Chart Types — When to Use Which

| Use case | Chart type |
|---|---|
| Trend over time, single metric | Line |
| Trend over time, comparing 2 periods | Line, two series |
| Distribution across categories, ≤ 6 categories | Vertical bar |
| Distribution across many categories | Horizontal bar, sorted descending |
| Composition of a whole, ≤ 4 slices | Donut (never pie) |
| Composition of a whole, > 4 slices | Stacked horizontal bar |
| Two-dimensional relationship | Scatter |
| Geographic distribution | Choropleth or marker map (Tojlo TI only) |
| Pipeline / funnel | Funnel chart, top-to-bottom, percentages on each stage |
| Cohort retention | Heatmap, lighter `--color-accent` for low retention, darker for high |

### Chart Rules

C1. **No 3D charts.** Ever.
C2. **No dual y-axes** unless absolutely necessary (and even then, document the necessity in a comment in the chart code). Dual y-axes mislead more often than they inform.
C3. **No animation on initial render** for performance reasons; line draw-ins, bar grows, etc. are forbidden. Reduced-motion forbids them anyway; we apply the same standard to everyone.
C4. **No chart without a title.** Even tiny KPI chartlets need a label.
C5. **No chart without a unit.** "23" means nothing. "23 leads" means something. "23%" means something else.
C6. **No pie charts with more than 4 slices.** Use stacked bar.
C7. **Tooltip values are tabular monospace.** Comparing two numbers in proportional type is unreadable.
C8. **Drill-down is mandatory.** Every chart must let the user click into the underlying rows. A chart with no drill-down is decoration.

---

## States — Empty, Loading, Error, Success, Partial

Every screen has six possible states. Designing only the "happy path" is a bug.

### Loading

- **Skeleton layout** that matches the final UI's structure. Skeleton shimmer per *Motion Language*.
- **Latency budget:** show skeleton if data takes > 80ms. Below 80ms, render directly without skeleton (a flash of skeleton on fast loads reads as a bug).
- **Long loads (> 3 seconds):** add a contextual message under the skeleton: "Loading 12,000 rows from Tojlo OPS. This usually takes 4–6 seconds." Don't apologize; explain.
- **Indefinite loads:** when no ETA is known, show the AI-thinking indicator with a label of what's happening: "Tojlo TI is generating the report…"

### Empty (no data yet)

- **Layout:** centered in the available area. Icon (48px hero), title, one-sentence description, primary CTA.
- **Title:** Inter 500, 18px, `--text-primary`. Outcome-led: "No leads yet. Connect WhatsApp to start."
- **Description:** Inter 400, 14px, `--text-muted`. ≤ 30 words. Tell the user what this surface does and what to do first.
- **CTA:** primary button, single action that sets up the data.
- **Illustration:** none. Icons only. Tojlo doesn't ship marketing illustrations into the product.

### Empty (filtered to zero)

Different from "no data yet." Don't show the onboarding empty state.

- **Layout:** within the table or list, replacing the rows.
- **Title:** "No rows match these filters."
- **Action:** "Clear filters" button (secondary), and inline summary of active filters.
- **No CTA to add data;** the user has data, they've just hidden it.

### Error

- **Layout:** within the failed area, never the whole screen, unless the whole screen failed.
- **Icon:** Lucide `AlertCircle` at 28px, `--color-danger`.
- **Title:** Inter 500, 16px, `--text-primary`. What broke, plain language.
- **Description:** Inter 400, 14px, `--text-muted`. What the user can do. Include error code in monospace at the end if useful for support.
- **Actions:** "Retry" primary button. "Contact support" secondary button if the error is unrecoverable.
- **No stack traces** in production. Send those to Sentry; show users a humane message.

### Permission Denied

- **Layout:** within the area the user lacks access to.
- **Icon:** Lucide `Lock` at 28px, `--text-muted`.
- **Title:** "You don't have access to this." Inter 500, 16px.
- **Description:** "Ask your workspace admin to grant the [permission name] role." with a "Request access" button that drafts a notification to the workspace owner.
- **Never silently hide.** Operators must know what they're missing so they can request it.

### Success

Success states are **rare** and **discrete**. The default after any successful action is for the action to simply complete — a quiet system. Show explicit success only for:

- **Milestones:** "Commission run completed. EUR 4,250 distributed across 6 invoices."
- **Asynchronous results returning:** "Tojlo TI finished the market scan. 14 new prospects ready for review."
- **Multi-step completion:** "Customer onboarded. All 12 records created."

Display: success toast + check-mark celebration animation per *Motion Language*. Toast persists until dismissed for milestones; auto-dismisses in 4s for routine confirmations.

### Partial Success / Warnings

When an operation completes but with caveats: "Sent 11 of 12 emails. Atlas Trading's address bounced; review and retry."

- **Color:** `--color-secondary` accent, not `--color-success` or `--color-danger`.
- **Action:** the actionable items (1 of 12, in this case) are listed inline with a "Resolve" button.
- **No silent partial failures.** If 1 of 100 succeeded, that's a failure with one survivor. State it clearly.

---

## Notification System

Without discipline, notifications drown operators. Tojlo enforces a strict taxonomy.

### Taxonomy

| Class | When | Surface | Persistence |
|---|---|---|---|
| **Critical** | Action required immediately to prevent harm (token expired, payment failed, data sync broken) | Banner at top of Dashboard, push, email | Until user resolves |
| **Actionable** | User decision needed within 24 hours (draft awaiting approval, lead awaiting reply) | Activity feed, bell badge, optional email digest | Until user acts |
| **Informational** | System completed something the user should know about, but no action needed | Toast (4s auto-dismiss), activity feed entry | 30 days in feed |
| **AI Suggestion** | AI proposes an action; user can accept, modify, or dismiss | Inline in module + activity feed | Until user decides |
| **Digest** | Aggregated low-priority items batched into a periodic summary | Daily / weekly email, in-app digest panel | Per digest |

### Throttling and Aggregation

- **Same event class within 60 seconds:** aggregate into one notification ("Tojlo HUB completed 3 workflow runs").
- **Same module repeating:** after 5 notifications in 10 minutes, switch to a digest entry.
- **Quiet hours:** per user, configurable in Settings → Notifications. During quiet hours, suppress everything except Critical.
- **Do not notify the actor.** If the user took the action, don't notify them about the action they took. (Example: user sends an email → no "email sent" notification.)

### Channels

- **In-app:** activity feed, bell badge, banner.
- **Email:** Critical immediately; Actionable in daily digest by default, opt-in for immediate; Informational batched into weekly digest.
- **Push (mobile, opt-in):** Critical and Actionable only.
- **WhatsApp (opt-in via Tojlo CHAT):** Critical only, used as a last-resort channel for urgent items the operator must see.

### Activity Feed

The Dashboard's right rail. Default visible on screens ≥ 1280px; tucked into a slide-over on smaller screens.

- **Grouped by module** with the module's layer indicator dot.
- **Grouped by day** with day separators (Today, Yesterday, then date).
- **Mark as read:** click a row to mark, or "Mark all read" in the header.
- **Filter:** by module, by class (Critical / Actionable / Info / AI Suggestion).
- **Search:** in-feed search filters live.

### Notification Rules

N1. **Every notification names its source module.** "Tojlo HUB completed weekly commission run" — not "Workflow completed."
N2. **Critical class is rare.** If everything is critical, nothing is. Reserve for genuine harm-prevention.
N3. **Actionable notifications surface their action inline.** "Approve draft" button on the notification, not just a link to go find it.
N4. **No notification without a way to silence the source.** Every notification's overflow menu offers "Mute notifications from [module] / [trigger]."
N5. **Digest preference defaults to daily for Actionable, weekly for Informational.** Power users can move to immediate per channel.
N6. **No marketing notifications in product.** Product announcements live in a "What's new" sheet the user opens themselves, never as forced banners or toasts.

---

## Activity and Audit UX

Tojlo records every action that mutates data or triggers external effects. Surfacing it well builds operator trust.

### Activity Log (per record)

Every customer, invoice, deal, lead, workflow has an Activity tab showing its full timeline.

- **Format:** vertical timeline, newest at top.
- **Each entry:** timestamp (relative + absolute on hover), actor (user or module), verb, object, optional diff for record changes.
- **Actors:** users by name + avatar; modules by name + module icon.
- **Diffs:** record changes show "before → after" for the changed fields, in a collapsed-by-default block.
- **System actions** (e.g. autoresponse from Tojlo MAIL) are clearly attributed to the module, not to a user.

### Audit Log (workspace-wide)

Settings → Audit log. Required for compliance.

- **Filterable:** by user, by module, by action class (read / write / delete / export / send / sign), by date range.
- **Exportable:** as CSV / JSONL with filename `tojlo-audit-{tenant}-{from}-{to}.{ext}`.
- **Retention:** 13 months default, configurable per tenant. Cannot be set below the regulatory minimum for the tenant's region (KVKK 2 years for Turkey, GDPR varies, etc.).
- **Immutable:** audit log entries are append-only. No edit, no delete, ever — by anyone, including workspace owners.

### Activity Rules

A1. **Every mutating action lands in the audit log within 5 seconds.** Critical for compliance demos.
A2. **Read access is logged for sensitive entities** (financial records, contracts, audit log itself). Read access on routine entities is not logged to avoid log explosion.
A3. **AI actions are logged with the model and prompt class** (not the full prompt; that lives in the AI execution log accessible to admins only).
A4. **Audit log is read-only by default.** Even tenant owners can only view and export, never edit.

---

## Permissions UX

The permission model is simple and visible. Operators always know what they can and can't do, without trial and error.

### Roles

Default roles per workspace. Custom roles are a paid-tier feature.

| Role | Capability |
|---|---|
| **Owner** | All. One per workspace. Cannot be removed; must transfer to remove. |
| **Admin** | All except billing and owner transfer. |
| **Operator** | Read + write across modules, run workflows, send communications, approve drafts. The default for most users. |
| **Viewer** | Read-only across modules. Can comment but not change records. |
| **Restricted** | Scoped to specific modules or specific record types (e.g. "only see deals tagged Iran"). Configured per assignment. |

### Surfacing Permissions

- **Disabled actions** show a tooltip explaining the missing permission: "Requires Operator role. Ask your admin."
- **Hidden surfaces** (modules the user doesn't have access to) are hidden, not shown-and-disabled. Show-and-disabled is information leakage.
- **Permission requests:** every disabled action has a "Request access" link that drafts a message to the workspace owner.

### Permission Rules

PR1. **Default roles cover 95% of cases.** Custom roles exist for the 5% but are paid because they require setup support.
PR2. **Permission denials never feel like errors.** They are explanations. Tone: "You don't have access. Here's how to get it."
PR3. **Sensitive actions log who approved them.** Approving a commission run > EUR 10,000 logs both the operator who initiated and the admin who confirmed.
PR4. **Permissions are evaluated server-side.** Client-side hiding is for UX only; the server is the source of truth.

---

## Onboarding

The operator's first 30 minutes determine adoption. Onboarding is a first-class product surface, not a one-off flow.

### First-Run Experience

When a workspace owner first signs in:

1. **Welcome.** "Tojlo, by Ocoron. The B2B Operating System." One sentence about what's about to happen.
2. **Workspace setup.** Company name, country, default currency, default language, density preference.
3. **Module selection.** "Pick the modules you want active. You can add more anytime."
4. **First integration.** "Connect your inbox" (Tojlo MAIL) is the most common first integration — a 30-second M365 OAuth.
5. **First milestone.** A specific small win: "Tojlo MAIL just labeled your last 100 emails by customer. See them in Tojlo MAIL → Customer view."
6. **Hand-off.** "You're set. Here's the activity feed; here's the command palette (⌘K). I'll let you know when something needs your attention."

### Subsequent-Run Hints

After the first run, contextual hints appear when the user enters a module for the first time:

- **First entry to Tojlo HUB:** "This is where workflows live. Your first workflow is suggested below — accept it or build your own."
- **First entry to Tojlo TI:** "Ask Tojlo TI any question about your customers, suppliers, or markets. Try: 'Which customers haven't ordered in 60 days?'"

Hints dismiss permanently on the first action in that module. They do not return.

### Empty Workspace

Before the user has data:

- **Sample data toggle:** in Settings → Workspace, "Load sample data (BHD demo dataset)" loads a realistic, fully-populated workspace for evaluation. Sample data is clearly tagged with a banner: "Sample data is active. Your real data is not affected. Disable when ready."
- **Module-by-module empty states:** each module shows its empty state per *States — Empty* with a CTA to the module's first integration.

### Onboarding Rules

O1. **No tooltip carousels.** No "Tour the product in 8 steps." Operators don't read; they do.
O2. **Show, don't tell.** Demonstrate value by completing a real action with the user's real data within the first 5 minutes.
O3. **Skippable.** Every onboarding step has "Skip for now." The product must work for an operator who skips everything.
O4. **No empty dashboards.** If the user has integrated nothing, the Dashboard shows the module activation grid, not a blank slate.
O5. **Onboarding completion is tracked, not gated.** Mark steps complete; never lock features behind unchecked steps.

---

## AI Interaction Patterns

Tojlo's product thesis depends on AI behaving predictably, transparently, and recoverably. Every AI surface follows this section without exception; AI that violates these patterns is a brand bug.

### Core Principles

1. **Always label AI output.** Every piece of AI-generated content carries a visible attribution: "Drafted by Tojlo MAIL," "Suggested by Tojlo TI," "Summarized by Tojlo." No exceptions. Operators must always know what came from a model.
2. **AI proposes; the operator approves.** AI never sends, signs, files, or executes a high-stakes action without explicit user approval. Approval can be a single click, but it must exist.
3. **Show the source.** Every AI claim about data is grounded in records the user can click to verify. Citations are mandatory; if the model can't ground a claim, it says so instead of making one up.
4. **Make it easy to override.** Every AI suggestion has Accept, Modify, and Dismiss as equally weighted actions. Modify is not a hidden affordance.
5. **Recoverable by default.** Anything AI did is undoable for at least 5 minutes. Anything AI sent externally has a "Recall" affordance where technically possible.
6. **No black boxes.** Operators can ask "Why did Tojlo suggest this?" and get an answer drawn from the actual prompt context, not a generated rationalization.

### AI Surface Patterns

#### A1 — Inline Suggestion

Used when AI proposes a value or action inline with existing content (e.g., suggested reply in Tojlo MAIL, suggested customer tag in Tojlo OPS).

```
┌────────────────────────────────────────────────────────────────┐
│ Suggested by Tojlo MAIL                                  ✕      │
│                                                                 │
│ "Thank you for your inquiry about paraffin pricing. Based on   │
│ current market rates, our offer is USD 1,250 per metric ton    │
│ FOB Istanbul. Validity: 7 days. Please confirm to proceed."    │
│                                                                 │
│ ◉ High confidence  ·  Sources: 3 prior emails, current pricing │
│                                                                 │
│ [ Edit and send ]   [ Send as is ]   [ Dismiss ]                │
└────────────────────────────────────────────────────────────────┘
```

- **Container:** 1px `--color-accent-muted` border, `--surface-1` background, `--space-md` padding.
- **Attribution row (top):** "Suggested by Tojlo [MODULE]" in Inter 500 uppercase 11px letter-spacing 1px, color `--color-accent`. Dismiss × button on the right.
- **Generated content:** Inter 400 14px `--text-body`, max 5 lines visible, "Show more" expander if longer.
- **Confidence and source row:** below content. See *Confidence and Citation*.
- **Action row (bottom):** Edit-and-send (primary), Send-as-is (secondary), Dismiss (tertiary). The default action is **Edit-and-send**, never Send-as-is. This is intentional: AI suggestions are starting points.

#### A2 — Generated Block (long-form)

Used when AI produces a longer artifact — a report, a draft contract, a market scan. Tojlo TI uses this most.

```
┌────────────────────────────────────────────────────────────────┐
│ Generated by Tojlo TI · 2026-05-18 14:02 · gpt-class-x          │
│                                                                 │
│ # Q2 Customer Activity Summary                                  │
│                                                                 │
│ Twelve customers placed orders in Q2 2026. Three customers...   │
│ [full content]                                                  │
│                                                                 │
│ ◉ Citations: 47 records · ◐ 2 claims need review                │
│                                                                 │
│ [ Save to VAULT ]  [ Export PDF ]  [ Regenerate ]  [ Refine ]   │
└────────────────────────────────────────────────────────────────┘
```

- **Header strip:** "Generated by Tojlo [MODULE]" + ISO timestamp + model identifier in Inter 400 12px `--text-muted`.
- **Body:** rendered Markdown with Tojlo typography. Citations inline as superscript numbered links, hovering reveals the source record.
- **Footer:** citation count, review-needed count (claims the model marked low-confidence), and action buttons.

#### A3 — AI Action Confirmation

Used when AI proposes to take a multi-step action (run a workflow, send a sequence of emails, file invoices).

```
┌────────────────────────────────────────────────────────────────┐
│ Tojlo HUB wants to run: Weekly Commission Run                   │
│                                                                 │
│ • Calculate commissions for 23 invoices (period 2026-05-12..18) │
│ • Generate 6 commission statements                              │
│ • Email statements to BHD finance team                          │
│ • File records in VAULT                                         │
│                                                                 │
│ Total amount: EUR 4,250.00                                      │
│ Estimated runtime: 2 minutes                                    │
│                                                                 │
│ ◉ This action sends 6 emails and creates 6 records. Undo window:│
│   5 minutes after completion.                                   │
│                                                                 │
│ [ Run now ]   [ Schedule ]   [ Edit steps ]   [ Cancel ]        │
└────────────────────────────────────────────────────────────────┘
```

- **Title:** "Tojlo [MODULE] wants to run: [action name]" — names the actor and the action.
- **Step list:** every concrete action the workflow will take, each starting with a verb.
- **Stakes summary:** counts and totals so the operator sees magnitude at a glance.
- **Reversibility note:** explicitly states the undo window or "This action cannot be undone" if not reversible.
- **Actions:** Run-now is primary; Schedule is secondary; Edit-steps opens Tojlo HUB; Cancel dismisses.

#### A4 — Conversational Panel ("Ask Tojlo")

Used in the command palette's AI search and in any module that exposes an "ask" affordance.

- **Threaded UI** — user query, AI response, user follow-up, etc. No emoji avatars; user is "You", AI is "Tojlo TI" with the module icon.
- **Streaming output** — the AI response renders progressively as the model emits tokens. AI-thinking indicator until first token arrives.
- **Inline citations** — every claim that draws on records gets a numbered superscript link.
- **History persistence** — the panel keeps the conversation for the session; "Clear" resets.
- **Ground-truth fallback** — when the model cannot answer from records, it says: "I couldn't find records to answer that. Try refining the question, or check Tojlo TI directly." Never "I think probably."

#### A5 — Background AI ("Quiet AI")

Used when AI does work in the background without surfacing a suggestion (auto-tagging, auto-categorizing, deduplication, sentiment scoring).

- **No notification** — quiet AI runs silently. Notifications are reserved for actions the user must respond to.
- **Marker on affected records** — every record touched by AI carries a small "AI" pill in `--color-accent-muted` with a tooltip: "Tagged by Tojlo [MODULE] on [date]."
- **Always reversible** — user can override the tag, category, or score with a single click. The override is logged.
- **Auditable** — Settings → AI Activity shows every quiet-AI action with a filter by module, type, and date.

### Confidence and Citation

#### Confidence Indicator

Three-state, never numeric:

| Indicator | Glyph | Meaning |
|---|---|---|
| **High** | ◉ | The model has strong grounding in records and prior similar actions. Recommended for one-click acceptance. |
| **Medium** | ◐ | The model has partial grounding. The operator should review before accepting. |
| **Low** | ◌ | The model is extrapolating. The operator should treat this as a draft idea and rewrite. |

Confidence is determined by a deterministic rubric, not by the model's self-assessment. Document the rubric in the AI execution log so admins can verify it.

We **never** show numeric confidence (e.g. "87%"). Numbers create false precision.

#### Citation

Every AI claim about specific data must cite the record:

- **Inline citation:** superscript number after the claim. `…last quoted price was USD 1,180.¹`
- **Citation list:** at the bottom of the AI output, numbered list of cited records with title, type, and date. Each is clickable to open in a side panel.
- **Coverage indicator:** "47 records · 2 claims need review" — explicit count of citations and any low-confidence claims that the operator should verify before acting.

#### When AI Cannot Cite

- **For data questions:** the model says "I couldn't find records to answer that." It does not improvise.
- **For drafting tasks:** the model proceeds without citations but flags the draft as Medium or Low confidence and prompts the user to add specifics.
- **For decisions:** the model never makes the decision. It surfaces the question with the relevant records attached.

### Streaming and Latency

- **First token latency budget:** ≤ 1 second from action. If exceeded, show the AI-thinking indicator with a label of what's happening.
- **Streaming render:** AI text appears progressively. Operators can read while the model writes; they can also interrupt with Esc.
- **Cancellation:** every AI action can be cancelled mid-stream. Cancelled output is discarded; no partial-state side effects.
- **Timeout:** if the model hasn't produced a full response in 30 seconds, surface an error with a "Retry" action. Never spin forever.

### Recovery and Override

- **Undo window:** every AI action that mutates data has an undo window. Default 5 minutes. Surfaced as a non-blocking toast: "Tojlo MAIL sent draft to Kandil Glass. Undo (4:58)."
- **Recall:** for emails sent to internal recipients, Tojlo MAIL offers a Microsoft Graph recall during the undo window. External emails cannot be recalled but are flagged for follow-up.
- **Override:** every AI tag, category, or suggestion can be overridden in one click. Overrides feed back into the model's tuning data.
- **Audit:** every AI override is logged. If an operator overrides the same AI category 5+ times, the system surfaces a "Want to retrain Tojlo MAIL on this category?" prompt to the workspace admin.

### Multimodal AI

When AI processes images (invoices via OCR, screenshots in customer chats):

- **Show the source.** The original image is always one click away from the AI-extracted output.
- **Highlight extracted regions.** Bounding boxes on the source image show where each extracted field came from.
- **Editable extraction.** All extracted values are editable inputs, not read-only labels.

### Enforcement

AI behavior in Tojlo is governed by the consolidated Tojlo AI rules — see *Rules for AI Agents → Tojlo AI Rules* (T27–T35). Every AI surface in this section must satisfy those rules.

Two additional implementation constraints worth calling out here:

- **Voice consistency.** AI output uses the same voice rules as the rest of the product — direct, precise, grounded. AI does not say "I think" or "It seems"; it states or it abstains.
- **Privacy of execution traces.** Operators see citations and rationale; full prompts and token traces are restricted to workspace admins via Settings → AI Activity.

---

## Multilingual and RTL

Tojlo ships in TR, EN, AR, RU, FA at v1, with EN as canonical reference. Localization is a first-class feature, not an afterthought.

### Languages and Scripts

| Locale | Script | Direction | Plural rules | Numerals | Notes |
|---|---|---|---|---|---|
| en | Latin | LTR | one / other | Western (0–9) | Canonical reference |
| tr | Latin | LTR | one / other | Western (0–9) | Default for BHD and most early customers |
| ar | Arabic | RTL | zero / one / two / few / many / other | Arabic-Indic (٠–٩) per tenant | Iranian portal users overlap |
| ru | Cyrillic | LTR | one / few / many / other | Western (0–9) | |
| fa | Persian | RTL | one / other | Persian (۰–۹) per tenant | Iran read-only portal primary language |

### Right-to-Left (RTL)

RTL is a layout flip, not a translation. Apply uniformly:

- **Reading direction:** entire layout mirrors. Sidebar moves to the right; primary CTA moves to the left of the secondary CTA in dialogs.
- **Directional icons flip:** arrows (back/forward, expand-right, send), chevrons in dropdowns and breadcrumbs, progress indicators.
- **Non-directional icons do not flip:** module icons, status icons, search, settings — they retain their native orientation.
- **Logos and wordmarks do not flip.** "Tojlo" is read left-to-right in every locale because the wordmark is a proper noun.
- **Numerals:** by default, numerals stay LTR even within RTL paragraphs (mixed-direction is the default for most Arabic/Persian readers). Override per tenant if the audience prefers full RTL numerals.
- **Tables:** column order mirrors. The leftmost column in LTR becomes the rightmost in RTL. Sticky-leftmost becomes sticky-rightmost.
- **Charts:** time axes flip; bar charts grow leftward instead of rightward where the convention applies.

Implementation: `dir="rtl"` on the document root for RTL locales, plus a `[dir="rtl"]` selector in CSS for any direction-specific overrides.

### Translation Workflow

- **Source of truth:** EN strings in `i18n/en.json`. Every other locale derives from EN.
- **Translation memory:** track string IDs, not raw text. Rephrasing an English string and not updating its ID breaks every other locale.
- **Reviewer:** every locale has a designated human reviewer (native speaker, B2B familiar). Machine-translated strings ship only after review.
- **Pluralization:** use ICU MessageFormat for plurals. Russian and Arabic both have > 2 forms; English has 2; never assume.
- **Variables:** all interpolated values are typed (`{count, plural, =0 {no leads} =1 {1 lead} other {# leads}}`). String concatenation in code is forbidden.

### Localization Quality Bar

Before a locale ships:

- **String coverage:** 100% of UI strings translated. No EN fallbacks visible to the operator.
- **Voice review:** native B2B reviewer signs off on a sample of 50 strings (buttons, errors, onboarding, AI suggestions).
- **Layout audit:** every screen reviewed at the locale's typical string length (German strings are ~30% longer than English; reserve space).
- **RTL audit (for AR, FA):** every screen reviewed in RTL mode for layout breakage, icon mirroring, numeral handling.

### Multilingual Rules

ML1. **Module names do not translate.** "Tojlo MAIL" stays "Tojlo MAIL" everywhere.
ML2. **Brand name does not translate.** "Tojlo" is "Tojlo" in every script.
ML3. **Tagline translates per market**, registered in `i18n/taglines.json`, never improvised.
ML4. **Voice rules apply uniformly.** Direct, precise, grounded — in every language.
ML5. **No machine translation in production without review.** AI-drafted *content* (emails, summaries) is allowed without review; AI-drafted *UI strings* are not.
ML6. **RTL is a full layout flip, not a text-direction toggle.**
ML7. **Locale switch is per user, not per workspace.** A Turkish operator and a Russian operator can share a workspace and each see their own locale.
ML8. **AI output respects the user's outbound language.** When drafting to a Russian customer, Tojlo MAIL produces Russian, not the operator's UI language.

---

## Date, Time, Currency, and Number Formatting

Mismatched formatting is a trust bug. A "10,000" that means "10.000" in another locale undermines the platform.

### Dates

- **Display format (short):** locale-aware via `Intl.DateTimeFormat`. EN: `2026-05-18` (ISO-like). TR: `18.05.2026`. AR: `١٨/٠٥/٢٠٢٦` (with Arabic-Indic if tenant prefers).
- **Display format (long):** locale-aware. EN: `May 18, 2026`. TR: `18 Mayıs 2026`.
- **Relative dates:** "2 minutes ago," "yesterday at 14:02," "last Wednesday." Falls back to absolute after 7 days.
- **Hover tooltip:** every relative or short date shows the absolute date + time + timezone on hover.
- **Storage:** ISO 8601 in UTC (`2026-05-18T14:02:31Z`). Convert at the display layer only.
- **Calendar:** Gregorian by default. Hijri or Persian calendar available per tenant for AR and FA tenants who request it; both are dual-display (Hijri primary, Gregorian secondary in parens).

### Times

- **Display:** locale-aware. EN: `14:02` (24-hour). TR: `14:02` (24-hour). Some EN-US tenants prefer 12-hour; configurable per user in Settings → Display.
- **Timezone:** every time displays in the user's timezone by default. The user's timezone is set in Settings → Display, defaulting to browser timezone.
- **Timezone clarity:** when displaying times that are not in the user's timezone (e.g., a customer's local time in a deal record), append the timezone abbreviation: `14:02 GMT+3 · Kandil Glass local`.
- **Storage:** UTC. Always. Display layer converts.

### Numbers

- **Thousand separator:** locale-aware via `Intl.NumberFormat`. EN: `12,345.67`. TR: `12.345,67`. AR with Arabic-Indic: `١٢٬٣٤٥٫٦٧`.
- **Decimal separator:** locale-aware (`.` in EN, `,` in TR, `٫` in AR Arabic-Indic).
- **Tabular alignment:** all numbers in tables and KPIs use `font-variant-numeric: tabular-nums` so columns align cleanly.
- **Negative numbers:** minus sign U+2212 (`−`), never hyphen-minus. Color `--color-danger` only for accounting contexts where positive/negative implies good/bad.
- **Percentages:** `{value}%` with no space (EN, TR) or `% {value}` with space (TR for chart axes per Turkish typographic convention; configurable).

### Currency

- **Format:** locale-aware via `Intl.NumberFormat({ style: 'currency' })`. EN-USD: `$1,234.56`. TR-TRY: `₺1.234,56`. EUR universal: `€1.234,56` (locale-formatted).
- **Currency code visible:** in tables and reports, always show the ISO code as a suffix when multiple currencies appear: `1,234.56 USD`. Single-currency contexts may use the symbol alone.
- **Conversion:** never auto-convert in transactional records. If a customer's deal is in USD, store and display USD. Show converted values only as supplementary, with the conversion rate, source, and timestamp visible.
- **Stablecoin / crypto:** future-only; not yet supported in v1. When introduced, follow same rules — show ticker (USDT, USDC), never "$" symbol.

### Phone Numbers

- **Format:** E.164 storage (`+905321234567`), display with national formatting via `libphonenumber-js`.
- **Display per locale:** TR: `+90 (532) 123 45 67`. EN-US: `+1 (415) 123-4567`.
- **Validation:** at input time, validate against E.164 with the country code derived from the input or the default per-tenant country.

### Address

- **Storage:** structured (street, city, postal code, country ISO). Never single-line.
- **Display:** locale-aware ordering. TR: street → mahalle → ilçe → il → posta kodu. EN: street → city, state ZIP. Always end with country if international.

### Formatting Rules

FMT1. **Locale-aware formatting at the display layer.** Storage is always canonical (UTC, ISO, E.164, ISO currency code).
FMT2. **Tabular numerals in tables and KPIs.** No exceptions.
FMT3. **Currency code visible in multi-currency contexts.**
FMT4. **Timezone visible when displaying out-of-timezone times.**
FMT5. **Never auto-convert currencies in transactional records.** Display original; show converted as supplementary only.
FMT6. **Use proper minus sign (U+2212), proper em-dash (U+2014), proper ellipsis (U+2026).** No three-period substitutes.
FMT7. **Numbers > 999 always get a thousand separator.** "1,247 leads" not "1247 leads."
FMT8. **Decimal places match precision** of the underlying value. Money: 2 decimals. Counts: 0. Percentages: 1 decimal unless the value is integer-precise.

---

## Email Templates

Every Tojlo-authored email — notifications, digests, AI drafts, invoices, statements — follows one template family.

### Anatomy

```
┌────────────────────────────────────────┐
│ [Tojlo wordmark · 32px height]         │
├────────────────────────────────────────┤
│                                        │
│ One-line subject restate (Inter 500,   │
│ 18px)                                  │
│                                        │
│ Body — direct, ≤ 120 words, 14–16px    │
│ Inter 400 line-height 1.6.             │
│                                        │
│ [ Primary action button — single CTA ] │
│                                        │
│ Optional: secondary text link.         │
│                                        │
├────────────────────────────────────────┤
│ Tojlo, by Ocoron · Manage notifications│
│ This email was sent to you@company.com │
│ because you're an operator on Tenant.  │
└────────────────────────────────────────┘
```

### Style

- **Width:** 600px, centered. Mobile-responsive at < 480px.
- **Background:** `#FAFAFA` outer, `#FFFFFF` inner panel. Always light (email clients render dark mode unreliably).
- **Header:** Tojlo wordmark (indigo on white), top-aligned, 32px height, 24px padding above and below.
- **Body:** Inter 400, 14–16px, line-height 1.6, max 120 words for transactional emails. Digests can go longer but use sub-headings.
- **CTA:** single primary button, full-width on mobile, `--color-accent` background, white text, 8px radius. Above-the-fold.
- **Footer:** "Tojlo, by Ocoron" + manage-notifications link + recipient explanation. Inter 400 12px `--text-muted` equivalent in email-safe colors.

### Templates

| Template | Trigger | Subject example |
|---|---|---|
| **Critical alert** | A Critical-class notification | `[Action required] M365 token expired — reconnect Tojlo MAIL` |
| **Daily digest** | Scheduled daily, 08:00 user-local | `Your Tojlo digest · 3 leads, 2 drafts pending, 1 invoice due` |
| **Weekly digest** | Scheduled weekly, Monday 08:00 user-local | `This week in Tojlo · 47 actions, 12 customers, 4 commissions paid` |
| **AI draft to customer** | Outbound to external recipient via Tojlo MAIL | (subject the AI drafted; no Tojlo branding in subject) |
| **Invoice / statement** | Tojlo OPS or commission run | `Invoice INV-2026-0481 · Kandil Glass · Due 2026-06-12` |
| **Onboarding step** | First-run experience | `Welcome to Tojlo · One thing to do today` |
| **Permission request** | Operator requests access | `[Access request] Hasan Çelik wants Operator role` |

### Email Rules

E1. **One CTA per transactional email.** Never two primary buttons; if a second action exists, link it as text.
E2. **Subject lines are specific.** "Your weekly Tojlo digest · 47 actions" — not "Your weekly update."
E3. **No clickbait.** No "🔥" "Don't miss this" "Important." Subject lines say what the email is.
E4. **No tracking pixels in operator-facing emails.** Operators trust Tojlo with their data; we don't sneak invisible trackers. Open-rate measurement via authenticated link clicks only.
E5. **AI drafts to customers carry no Tojlo branding** in subject or footer. The customer should not know whether a human or AI wrote the email — that's between Tojlo and the operator.
E6. **Plain-text fallback** for every email. Multipart MIME with both HTML and plain-text bodies.
E7. **Unsubscribe / mute** is one click for digest emails. Required by CAN-SPAM, GDPR, and basic dignity.
E8. **Locale-aware:** dates, times, numbers, currency in the recipient's locale.

---

## Print and Export

Operators print and PDF-export constantly: invoices, contracts, reports, audit logs. Print is a first-class output.

### Print Stylesheet

Every print-relevant route has a `@media print` stylesheet:

- **Background:** white. Dark mode is for screens.
- **Type:** body 11pt Inter, headings Space Grotesk, code JetBrains Mono. Black text.
- **Page margins:** 20mm top and bottom, 18mm left and right.
- **Headers and footers:** Tojlo wordmark in the page header, page-X-of-Y in the footer center, document title in the footer left.
- **Tables:** keep header row visible across page breaks (`thead { display: table-header-group }`).
- **Color charts:** rendered in a 4-color print-safe palette (indigo, neutral gray, success green, danger red) — never relying on pure color where shape or label can do the work.
- **Hide:** navigation chrome, toolbars, action buttons, command palette, activity feed.

### PDF Export

Server-rendered PDFs for invoices, contracts, statements, audit logs. Use Puppeteer or similar:

- **Brand consistency:** PDFs use the same print stylesheet — they're print rendered to a file.
- **Filename:** `tojlo-{type}-{identifier}-{YYYYMMDD}.pdf`. Example: `tojlo-invoice-INV-2026-0481-20260518.pdf`.
- **Metadata:** PDF metadata fields (title, author, subject) populated from the document. Author is always "Tojlo (by Ocoron)."
- **Watermark:** none by default. Draft documents may carry a "DRAFT" watermark in `--color-secondary` at 30% opacity.

### Export Rules

EX1. **Print is functional.** A printed Tojlo screen is a useful artifact, not a screenshot.
EX2. **Color accessibility in print.** Color charts include shape or label fallbacks; status pills include text labels.
EX3. **PDF metadata is populated.** Search and archive depend on it.
EX4. **No dark backgrounds in print or PDF.** Always white.
EX5. **Page numbers on every multi-page output.** "Page 3 of 12."

---

## Accessibility

Tojlo aims for **WCAG 2.2 AA compliance** across all product surfaces, with AAA for critical paths (login, payment, audit log).

### Color Contrast (Tojlo Token Pairs)

Verified contrast ratios for the canonical token pairings:

| Foreground | Background | Ratio | Level | Use |
|---|---|---|---|---|
| `--text-primary` `#FFFFFF` | `--surface-0` `#0A0A0A` | 19.83:1 | AAA | Body text on page |
| `--text-primary` `#FFFFFF` | `--surface-1` `#141414` | 18.13:1 | AAA | Body text on cards |
| `--text-body` `#E0E0E0` | `--surface-0` `#0A0A0A` | 16.04:1 | AAA | Default body |
| `--text-muted` `#888888` | `--surface-0` `#0A0A0A` | 5.74:1 | AA | Meta, timestamps |
| `--text-muted` `#888888` | `--surface-1` `#141414` | 5.25:1 | AA | Meta on cards |
| `--color-accent` `#5B5BF7` | `--surface-0` `#0A0A0A` | 5.41:1 | AA | Links, accent text |
| `#0A0A0A` (dark text) | `--color-accent` `#5B5BF7` | 5.41:1 | AA | Primary button text |
| `#FFFFFF` | `--color-accent` `#5B5BF7` | 4.06:1 | AA Large | Button text alt — only for ≥ 18px or bold ≥ 14px |
| `--color-success` `#27AE60` | `--surface-0` `#0A0A0A` | 4.84:1 | AA | Success text |
| `--color-danger` `#FF4444` | `--surface-0` `#0A0A0A` | 5.21:1 | AA | Error text |
| `--color-secondary` `#F5A623` | `--surface-0` `#0A0A0A` | 9.31:1 | AAA | Warning text |

**Light mode pairs** must be re-validated; the audit lives in `accessibility/contrast-light.md`.

**Forbidden pairs (do not use):**
- `--text-muted` on `--surface-3` (3.94:1 AA Large only — too risky for body text)
- `--color-accent` `#5B5BF7` text on `--color-accent-muted` background (insufficient)

### Keyboard Navigation

- **Tab order:** matches reading order (left-to-right LTR, right-to-left RTL).
- **Focus visible:** 2px `--color-accent` ring at 2px offset on every focusable element. Never disabled.
- **Skip links:** "Skip to main content" available on every page, visible on focus.
- **Modal focus trap:** focus stays within the modal until closed; Esc closes; focus returns to trigger.
- **Keyboard shortcuts:** every primary action has a shortcut, documented in Settings → Keyboard.

### Screen Reader

- **Semantic HTML:** `<button>` for buttons, `<a>` for links, `<table>` for tables. Never `<div onclick>`.
- **ARIA live regions:** for streaming AI output, toasts, and async status updates.
- **ARIA labels:** icon-only buttons carry an `aria-label`. Tab bars, toolbars, and menus follow ARIA Authoring Practices.
- **Alt text:** every meaningful image has alt text; decorative images have empty `alt=""`.
- **Test target:** NVDA + Chrome on Windows, VoiceOver + Safari on macOS, JAWS for enterprise audits.

### Motion and Cognition

- **Reduced motion:** respected per *Motion Language*.
- **Reduced transparency:** scrims at full opacity; no blur effects when `prefers-reduced-transparency: reduce`.
- **Reading order is predictable.** No content reordering on screen size; mobile is a vertical reflow of desktop.

### Forms

- **Every input has a label.** Labels-as-placeholders is forbidden.
- **Error messages reference the field by name** ("Phone must include country code") not by position ("Field 3 is invalid").
- **Required fields announced** to screen readers via `aria-required`.

### Accessibility Rules

ACC1. **WCAG AA minimum for all UI.**
ACC2. **AAA for login, billing, audit log, contracts.**
ACC3. **Focus visible always.**
ACC4. **Keyboard parity:** every mouse-driven action has a keyboard equivalent.
ACC5. **Screen-reader tested per release.** Smoke test on critical paths every release; full audit annually.
ACC6. **Color is never the only signal.** Status icons, labels, or patterns reinforce.
ACC7. **Reduced-motion users get a fully functional product.** No feature gated behind motion.
ACC8. **Touch targets ≥ 44px on touch devices** regardless of density.

---

## Spacing, Interaction, Scaffolds

**Inherited from Ocoron unchanged.** The scaffold adaptation matrix (saas-skeleton, static-site, chrome-extension, mobile-app, desktop-app, wordpress, docusaurus) applies identically. The accent color `--color-accent` is `#5B5BF7` — same as Ocoron.

---

## Tailwind Theme Extension (Tojlo)

```js
// tailwind.config.ts — extend section
{
  colors: {
    accent: { DEFAULT: '#5B5BF7', hover: '#7676FF', muted: 'rgba(91,91,247,0.12)' },
    // Inherited from Ocoron, unchanged:
    secondary: '#F5A623',
    danger: '#FF4444',
    success: '#27AE60',
    info: '#2980B9',
    purple: '#9B59B6',
    surface: { 0: '#0A0A0A', 1: '#141414', 2: '#1A1A1A', 3: '#222222' },
    border: '#2A2A2A',
    text: { primary: '#FFFFFF', body: '#E0E0E0', muted: '#888888' },
  },
  fontFamily: {
    heading: ['Space Grotesk', 'sans-serif'],
    body: ['Inter', 'sans-serif'],
    mono: ['JetBrains Mono', 'monospace'],
  },
  borderRadius: {
    card: '8px',
    tag: '3px',
    pill: '20px',
    button: '6px',
  },
  spacing: {
    xs: '4px', sm: '8px', md: '16px', lg: '24px', xl: '32px', '2xl': '48px',
  },
  transitionDuration: {
    instant: '0ms',
    fast: '100ms',
    default: '150ms',
    slow: '250ms',
    deliberate: '400ms',
    celebration: '600ms',
  },
  transitionTimingFunction: {
    'ease-default': 'cubic-bezier(0.16, 1, 0.3, 1)',
    'ease-linear': 'linear',
    'ease-spring': 'cubic-bezier(0.5, 1.5, 0.5, 1)',
    'ease-emphasis': 'cubic-bezier(0.4, 0, 0.2, 1)',
  },
}
```

---

## CSS Custom Properties (Tojlo)

```css
:root {
  /* Tojlo override — primary accent */
  --color-accent: #5B5BF7;
  --color-accent-hover: #7676FF;
  --color-accent-muted: rgba(91, 91, 247, 0.12);

  /* Inherited from Ocoron, unchanged */
  --color-secondary: #F5A623;
  --color-danger: #FF4444;
  --color-success: #27AE60;
  --color-info: #2980B9;
  --color-purple: #9B59B6;

  --surface-0: #0A0A0A;
  --surface-1: #141414;
  --surface-2: #1A1A1A;
  --surface-3: #222222;
  --border: #2A2A2A;

  --text-primary: #FFFFFF;
  --text-body: #E0E0E0;
  --text-muted: #888888;

  --font-heading: 'Space Grotesk', sans-serif;
  --font-body: 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  --radius-card: 8px;
  --radius-tag: 3px;
  --radius-pill: 20px;
  --radius-button: 6px;

  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;

  --transition-speed: 0.15s;
  --transition-ease: ease;

  /* Motion tokens — canonical values from § Motion Language */
  --motion-instant: 0ms;
  --motion-fast: 100ms;
  --motion-default: 150ms;
  --motion-slow: 250ms;
  --motion-deliberate: 400ms;
  --motion-celebration: 600ms;

  /* Easing tokens — canonical values from § Motion Language */
  --ease-default: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-linear: linear;
  --ease-spring: cubic-bezier(0.5, 1.5, 0.5, 1);
  --ease-emphasis: cubic-bezier(0.4, 0, 0.2, 1);
}

[data-theme="light"] {
  --surface-0: #FAFAFA;
  --surface-1: #FFFFFF;
  --surface-2: #F5F5F5;
  --surface-3: #EEEEEE;
  --border: #E0E0E0;
  --text-primary: #111111;
  --text-body: #333333;
  --text-muted: #999999;
}
```

---

## White-Label Theming (Future)

Tojlo's commercial roadmap includes a white-label tier. When a tenant takes a white-label deployment:

- Replace `--color-accent` with the tenant's accent color (validated for WCAG AA contrast against `--surface-0` and `--surface-1`).
- Replace the Tojlo wordmark with the tenant's wordmark in the top-left of the Dashboard.
- Footer must still display "Powered by Tojlo, by Ocoron" in `--text-muted`, 12px — this is non-negotiable for licensing reasons and documented in the white-label addendum to the Tojlo License Agreement.
- All other tokens (typography, spacing, components, interaction) remain locked to the Tojlo design system. White-label tenants cannot override component patterns.

The white-label theming layer is implemented as a CSS variable override at the `[data-tenant="<id>"]` selector, never as a CSS file replacement.

---

## Token Governance and Contribution Process

Design tokens are the contract between design and engineering. Once a token is in production, changing it requires the same care as a contract amendment.

### Token Lifecycle

1. **Proposal.** A designer or engineer opens a proposal in the design-system repo (`/proposals/{token-name}.md`) describing: the gap, the proposed token, the affected components, the migration path.
2. **Review.** Reviewed by the design system maintainer + one engineer + one product reviewer. Async; 5 business days max.
3. **Acceptance or rejection.** Reasoned. Rejected proposals stay in the repo as `/proposals/_rejected/` so future proposals don't repeat the conversation.
4. **Pre-release.** Approved tokens land in a pre-release branch (`tokens-v{X.Y}-rc1`). Storybook updated. Visual regression suite updated.
5. **Migration window.** Two weeks for downstream consumers to adopt or push back.
6. **Release.** Tokens promoted to `main`. Old tokens deprecated (not deleted) for one major version.
7. **Removal.** Deprecated tokens removed in the next major.

### Versioning Scheme

The design system follows semantic versioning:

- **Major (v1 → v2):** breaking changes — removed tokens, renamed tokens, removed components, changed component APIs, changed module names.
- **Minor (v1.0 → v1.1):** additive — new tokens, new components, new patterns.
- **Patch (v1.0.0 → v1.0.1):** fixes — clarifications, typos, accessibility-pair updates that don't change values.

### Branching

- **`main`** — current released version, always shippable.
- **`v{X}-lts`** — long-term support branches for releases that customers run in production. Patch fixes only; no new features.
- **`tokens-v{X.Y}-rc{N}`** — pre-release candidates for next minor or major.
- **`proposals/{slug}`** — exploration branches for in-progress proposals.

### Inheritance from Ocoron

Tojlo inherits from Ocoron design system at a pinned version. The pinned version lives in `.ocoron-design-system-version` at the repo root. Ocoron version bumps are evaluated quarterly:

- **Compatible Ocoron updates** (additive, non-breaking): adopt within one release.
- **Breaking Ocoron updates:** evaluate impact, plan migration, may delay adoption to next Tojlo major.

### Deprecation Policy

- **Deprecated tokens emit a console warning** in development builds, naming the deprecated token, the version it was deprecated in, and the replacement.
- **Deprecated components** carry a `@deprecated` JSDoc tag with the same metadata.
- **Deprecation period:** 1 minor version minimum, 1 major version preferred.
- **Removal:** in a major version, with the migration path documented in the changelog.

### Contribution Rules

G1. **Every new token has a documented use case.** Tokens proposed without a use case are rejected.
G2. **Every new token uses an existing scale where possible.** Don't introduce a new spacing value if `--space-md` works.
G3. **Every new component is built from existing tokens.** Components that hard-code values are bugs.
G4. **Every new pattern is documented before merge** in this design system file. No undocumented patterns in production.
G5. **Visual regression coverage is mandatory** for new components and components changed in a release.
G6. **Breaking changes require a written migration note** in `/migrations/v{X}-to-v{Y}.md`.
G7. **No silent removals.** Every removal goes through deprecation first.

---

## Implementation Stack Summary

Reference for engineers building Tojlo surfaces:

| Layer | Choice | Notes |
|---|---|---|
| Framework | Next.js 14 App Router | Inherited via Ocoron's saas-skeleton |
| Component library | shadcn/ui | Themed with Tojlo tokens |
| Styling | Tailwind CSS + CSS variables | Tokens defined in `globals.css` |
| Charts | Recharts (default), Tremor (KPI chartlets) | Custom D3 only when nothing else fits |
| Icons | Lucide React + custom module icons | See *Iconography* |
| Animations | Framer Motion | Respects `prefers-reduced-motion` |
| Tables | TanStack Table + TanStack Virtual | Virtualization > 200 rows |
| Forms | React Hook Form + Zod | Validation per *Forms* spec |
| Internationalization | next-intl + ICU MessageFormat | Per *Multilingual and RTL* |
| Date / Time | `date-fns` + `date-fns-tz` + `Intl.DateTimeFormat` | UTC storage |
| Numbers / Currency | `Intl.NumberFormat` | Per *Date, Time, Currency, and Number Formatting* |
| Phone | `libphonenumber-js` | E.164 storage |
| Auth | Self-hosted SSO — `fabrik-lib/fastapi-user-auth` (Tojlo AUTH) | SSO across all modules; app issues its own JWTs |
| Database | `postgres-main` (PG16, shared) | Per Tojlo OPS / VAULT architecture |
| Background jobs | n8n (Tojlo HUB) | For workflow execution |
| Email | M365 + Microsoft Graph (Tojlo MAIL) | Operator's own M365 |
| AI models | Gemini Flash (Tojlo MAIL OCR/translation), Claude / GPT class (Tojlo TI) | Model-agnostic surfaces |
| Analytics | Self-hosted (Plausible or PostHog) | No third-party trackers in operator UI |
| Monitoring | Sentry (errors), Vercel Analytics (perf), Tojlo native (audit) | Three-tier observability |

---

## Rules for AI Agents (Kilo / Windsurf / Traycer)

All 17 Ocoron AI-agent rules apply in full. Tojlo-specific rules below.

### Tojlo Visual Rules

T1. **The accent is `#5B5BF7`.** Inherited from Ocoron. Both brands share the same accent color.
T2. **Module color coding is by layer only.** Core = accent, Intelligence = purple, Growth = secondary. Never invent a module-specific color.
T3. **Module icons stay monochrome.** Color goes on the layer indicator (left rail or dot), never on the icon glyph itself.
T4. **Module chrome type is Inter 500 uppercase 11px letter-spacing 1px.** No exceptions for sidebar / tab bar / breadcrumb.
T5. **Embedded vendor chrome must be hidden** wherever the vendor allows it. The Tojlo top bar is the navigation source of truth for embedded modules.
T6. **Endorsement lockup is mandatory** in product footer, marketing footer, login screen footer, and first-contact email signature. "Tojlo, by Ocoron." Always.
T7. **Wordmark is always an SVG asset, never a text-font rendering.**
T8. **Tables never use stripe rows.** Whitespace and borders only.
T9. **Numeric columns are tabular monospace** (`font-variant-numeric: tabular-nums`). Always.
T10. **Charts have a title and a unit.** A chart without both is a bug.
T11. **No 3D charts. No pie charts > 4 slices. No dual y-axes** (unless documented).
T12. **Empty states use icons, not illustrations.** Tojlo doesn't ship marketing illustrations into the product.
T13. **Confidence indicators are qualitative** (◉ ◐ ◌). Numeric confidence is forbidden.
T14. **Density toggle changes only spacing.** Never change typography, color, motion, or content based on density.
T15. **Focus rings are never disabled.** Every focusable element shows the 2px `--color-accent` ring at 2px offset.

### Tojlo Verbal Rules

T16. **Brand name is "Tojlo."** Capital T, lowercase rest. No all-caps in body text, no all-lowercase in body text. Lowercase only in code/URLs.
T17. **"Tojlo OS" for full-platform reference. "Tojlo" alone is fine when context is clear.** Never "Ocoron Tojlo."
T18. **Module names follow the canonical list.** `Tojlo [UPPERCASE_WORD]`. Do not invent, do not abbreviate to "T-MAIL" or "T-HUB" or any other shortened form.
T19. **Always attribute system actions to the module that performed them.** "Tojlo HUB completed weekly commission run" is correct. "Your weekly commission run is complete" is incomplete and forbidden in notifications, activity feeds, and digests.
T20. **AI suggestions must be labeled.** Any AI-generated draft, suggestion, or summary surfaced to the user must carry an explicit marker ("Drafted by Tojlo MAIL," "Suggested by Tojlo TI"). Operators must always know what the AI did.
T21. **Taglines are locked.** "The B2B Operating System." (primary) and "Operate at the speed of AI." (campaign). Do not generate new taglines without approval.
T22. **No new module names without approval.** Use the canonical list. New modules require an addition to the Module Naming section before they appear in any product surface.
T23. **Sentence case in product UI.** Title Case is forbidden in buttons, page titles, menu items.
T24. **Button labels are imperative verbs** ("Send draft," "Create customer"), never "Submit" / "OK" / "Save changes" if a more specific verb fits.
T25. **Localized voice preserves directness.** Don't soften UI strings with honorifics or formal openers in TR / AR / RU / FA.
T26. **Module names do not translate.** "Tojlo MAIL" stays "Tojlo MAIL" in every locale.

### Tojlo AI Rules

T27. **Every AI surface attributes the module:** "Drafted by Tojlo MAIL," "Generated by Tojlo TI."
T28. **AI never auto-executes external or destructive actions.** Always proposes; user approves.
T29. **Citations are mandatory** for AI claims about specific data.
T30. **AI says "I don't know"** rather than guessing.
T31. **AI confidence is qualitative,** never numeric.
T32. **AI output is always editable.**
T33. **AI inherits the user's outbound language** for content destined for external recipients.
T34. **Quiet AI carries the AI pill** on every record it touches.
T35. **AI suggestions show three actions: Edit, Send, Dismiss.** Edit-and-send is the default action.
T36. **AI execution logs are admin-only.** Operators see citations and rationale; full prompts and token traces are restricted to workspace admins.
T37. **Model identity is admin-visible only.** End operators see "Generated by Tojlo TI"; admins additionally see the model class.

### Tojlo Engineering Rules

T38. **Storage is canonical** (UTC, ISO 8601, E.164, ISO currency code). Display layer formats per locale.
T39. **Server-side pagination** for any table backed by a database with > 100 rows.
T40. **Virtualization** for tables with > 200 visible rows.
T41. **Keyboard shortcuts** for every primary action, documented in Settings → Keyboard.
T42. **Audit log entries within 5 seconds** of any mutating action.
T43. **No tracking pixels** in operator-facing emails.
T44. **No marketing notifications** in product UI.
T45. **No third-party analytics** in operator UI without consent. Anonymous telemetry to self-hosted analytics only.
T46. **No silent partial failures.** "Sent 11 of 12" is a failure with one exception, surfaced explicitly.
T47. **Deprecated tokens emit a console warning** in development builds.

### Tojlo Responsive Rules

T48. **Every Tojlo web page must be responsive from 375px to 2560px.** No desktop-only layouts. No exceptions. Mobile-first CSS: base styles target smallest viewport, breakpoints layer up.
T49. **Sidebar collapses below 1024px.** Icon rail at 768-1023px, hamburger/bottom tabs below 768px. Persistent full sidebar on mobile is banned.
T50. **Data tables transform on mobile.** Card transformation (Pattern A) or horizontal scroll with sticky first column (Pattern B). Unmodified desktop tables on phone viewports are banned.
T51. **Modals become full-screen sheets below 640px.** Floating modals on phone viewports are banned.
T52. **Test at 375px, 768px, 1440px before every UI merge.** Untested responsive = broken responsive. Full testing process: `docs/reference/mobile-responsive-testing-guide.md`.

---

## Versioning

This document is versioned alongside Tojlo platform releases. Breaking changes (token renames, removed components, changed module names) require a major version bump and a written migration note in `/migrations/`.

| Version | Date | Notes |
|---|---|---|
| v1.0 | 2026-05-18 | Initial release. Endorsed-brand model under Ocoron. Tojlo Indigo accent. Twelve-module canonical list. |
| v1.1 | 2026-05-18 | Comprehensive expansion. Brand: Manifesto, anti-positioning, audience, customer promise, localized voice (TR/AR/RU/FA), voice across 22 surfaces, naming and capitalization rules. Visual: full logo construction spec, iconography, motion language, density modes. Components: data tables, forms, command palette, charts, six-state taxonomy, notifications, activity/audit, permissions, onboarding. AI: 5 surface patterns (A1–A5), confidence and citation, recovery and override, multimodal. Localization: multilingual and RTL, date/time/currency/number formatting. Output: email templates, print and export. Compliance: WCAG 2.2 AA matrix. Implementation: token governance, stack summary. Agent rules expanded from 13 to 47 (T1–T47). |
| v1.2 | 2026-05-24 | Added: Responsive layout inherited from Ocoron (RWD1-RWD10). Motion/easing tokens added to CSS and Tailwind references. Responsive rules T48–T52. |
