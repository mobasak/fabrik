---
description: Ocoron house identity — the Ocoron BRAND that fills core/design-system-template.md's slots: brand story, verbal identity, logo, colour tokens for both modes with a computed contrast table, typography, radius, icons, sound. Applies ONLY to a project whose docs/design-system.md declares "House identity: ocoron — chosen, not defaulted" (D-051); every other GUI takes its brand from brand-identiy-creator. The structure (components, states, tables, forms, motion, density, accessibility, responsive) is the template's, not this file's.
currency_pass: 2026-09-24
---
<!-- CONSUMER: coding agents on an Ocoron-declared project; /fabrik-ui-design when a project adopts the house identity; tojlo-design-system.md (inherits these values)
     GOAL: the Ocoron brand's values and voice — one fill of the design-system template
     AGENT USAGE: build with the template's slot names; take the values below. Never invent colours or fonts. -->

# Ocoron Design System v3.0

> The Ocoron BRAND. ⚠️ **A HOUSE identity, chosen — never defaulted** (operator ruling 2026-08-29,
> D-051): a project uses it only when its `docs/design-system.md` header declares it explicitly;
> every other UI project gets its identity from brand-identiy-creator (the resolution ladder in
> `saas/60-saas-ui.md`). Everything structural — components, states, tables, forms, motion, density,
> accessibility, responsive layout — is `core/design-system-template.md`, which every project
> inherits whatever its brand. This file fills that template's slots and adds the Ocoron voice.
>
> **Contract sections → this file** (template § The design-system.md contract): 2 → § Colour tokens ·
> 3 → § Contrast table · 4 → § Typography · 5 and 6 → § Radius, icons and data visualisation ·
> 7 → § Logo · 8 → § Verbal Identity · 9 → § Ocoron on each scaffold (theme mode, light-mode shadow) ·
> 10 → § Sound. An Ocoron-declared project's own `docs/design-system.md` is
> the header line plus any § Structural overrides.

---

## Brand Story

**Ocoron** — inspired by the Ouroboros, the ancient symbol of the self-consuming serpent. An infinite loop. In modern terms: self-sustaining systems, continuous automation, and platforms that generate compounding value without constant human intervention.

The name splits naturally into two forces:
- **Oco** — the infinite cycle. Continuous integration, seamless loops, systems that feed themselves.
- **Ron** — the fundamental unit of power (electron, iron). Structure, execution, reliability.

**Ocoron = The Infinite Engine.**

---

## Verbal Identity

### Positioning

**Statement:** Ocoron builds AI-powered digital infrastructure engineered to deploy fast, run autonomously, and compound value over time.

**Tagline:** *Engineered to compound.*

- "Engineered" signals precision, intent, and technical depth — not hacked together.
- "Compound" bridges two meanings: compounding value (financial) and compounding capability (systems that get better with each iteration).
- 3 words. Ownable. Passes the swap test — no other company can claim this exact positioning.

### Brand Name Usage

- **Standard text:** "Ocoron" — capital O, lowercase rest. Always.
- **Never:** "OCORON" in body text, "ocoron" in body text, "OcoRon," or any other variation.
- **All-caps:** Only in the logo wordmark itself.
- **Lowercase:** Only in URLs, CLI commands, package names, code references (`ocoron.com`, `ocoron deploy`).
- **Possessive:** "Ocoron's" is acceptable. "Ocoron's infrastructure" not "the infrastructure of Ocoron."

### Voice: The Engineer Who Ships

Ocoron sounds like a senior engineer who's built production systems and has no patience for theater. Someone who respects your time, says what they mean, and backs claims with evidence. Not a salesperson. Not a consultant. A builder.

#### Core Traits

| Trait | What it means | What it's NOT |
|---|---|---|
| **Precise** | Every word earns its place. Specific numbers over vague adjectives. Show, don't tell. | Not cold. Not robotic. Precision is respect for the reader's time. |
| **Confident** | We state what we do and what we've built. No hedging, no "we believe," no "we strive to." | Not arrogant. Never put down competitors. Never overclaim. |
| **Grounded** | We speak from experience, not theory. Real architecture, real constraints, real outcomes. | Not academic. Not abstract. No thought-leadership fluff. |

#### Tone Spectrum

The voice is constant. The tone adjusts by context:

| Context | Tone | Example |
|---|---|---|
| **Product UI** | Minimal, functional | Button: "Deploy" — not "Launch your amazing project!" |
| **Marketing site** | Confident, benefit-first | "Your infrastructure. Deployed in 90 seconds. Monitored 24/7. No ops team required." |
| **Documentation** | Clear, instructional | "Run `ocoron deploy --env production`. The service starts on port 3000 by default." |
| **Error states** | Honest, helpful, no blame | "Build failed: missing environment variable `DATABASE_URL`. Add it in Settings → Environment and redeploy." |
| **Email / B2B outreach** | Respectful, direct | "Here's what we built. Here's what it costs. Here's the timeline. Questions?" |
| **Social media** | Sharp, occasionally dry | "New: auto-rollback on failed health checks. Your deploys recover without you waking up." |
| **Turkish B2B (initial contact)** | Slightly more formal, still direct | Open with professional courtesy, move quickly to substance. No excessive pleasantries, but honor the norm of formal first contact in Turkish business culture. |

### Writing Rules

1. **Lead with the outcome.** "Deploys in 90 seconds" — not "Our advanced deployment pipeline leverages..."
2. **Active voice.** "Ocoron monitors your services" — not "Your services are monitored."
3. **Short paragraphs.** 1–3 sentences in marketing. 1–5 in docs. Never a wall of text.
4. **Specifics over adjectives.** "4ms response time" beats "blazing fast." "99.9% uptime" beats "highly reliable."
5. **Address the reader.** "You" in marketing and docs. "We" when speaking as Ocoron. Never "one" or "the user."
6. **No rhetorical questions.** State the answer instead. "Your systems run themselves" — not "What if your systems could run themselves?"
7. **Talk about AI honestly.** Describe what the AI actually does. "AI reviews your code against 47 convention rules" — not "AI-powered code review." We don't use "AI-powered" as a marketing adjective.

### Forbidden Language

Never use these in any Ocoron communication:

| Forbidden | Why | Use Instead |
|---|---|---|
| "Leverage" | Corporate filler | "Use" |
| "Synergy" | Meaningless | Cut entirely |
| "Disruptive" / "Game-changer" | Startup cliche | Describe what actually changed |
| "Ecosystem" | Vague tech buzzword | "Platform," "stack," or be specific |
| "Best-in-class" | Unsubstantiated superlative | Cite the specific metric |
| "Seamless" | Everyone says it | "Works without configuration" or describe the actual UX |
| "Cutting-edge" | Says nothing | Name the specific technology |
| "End-to-end" | Vague | List what's actually included |
| "Solutions" (alone) | Empty noun | "Systems," "tools," "platforms," or the actual product name |
| "We believe" / "We strive to" | Hedging | State the fact directly |
| "Empower" | Patronizing | "Give you" or "let you" |
| "Holistic" | Academic filler | Be specific about what's covered |
| "Innovative" | Self-praise | Let the work speak |
| "Revolutionary" | Overclaim | Describe the improvement with numbers |

### Voice in Action: Before / After

**Landing page headline:**
- ❌ "Empowering Businesses with Cutting-Edge, End-to-End Digital Solutions"
- ✅ "Your infrastructure. Deployed, monitored, and maintained. Without an ops team."

**Feature description:**
- ❌ "Our innovative platform leverages AI to seamlessly deliver best-in-class deployment experiences."
- ✅ "Push code. Ocoron builds, deploys, and monitors it. Average deploy time: 90 seconds."

**B2B email:**
- ❌ "We'd love to explore synergies and discuss how our holistic solutions can empower your digital transformation journey."
- ✅ "We build the systems you described. Here's a spec, a timeline, and a fixed price. Want to move forward?"

**Error message:**
- ❌ "Oops! Something went wrong. Please try again later."
- ✅ "Build failed: port 8080 is in use. Stop the existing process or use `--port` to pick another."

**Social media:**
- ❌ "We're thrilled to announce our game-changing new feature! 🚀🎉"
- ✅ "New: auto-rollback on failed health checks. Your deploys recover without you waking up."

**About page (opening paragraph):**
- ❌ "Ocoron is a cutting-edge, innovative technology company striving to empower businesses through holistic digital transformation solutions."
- ✅ "Ocoron builds digital systems that run themselves. We design, deploy, and maintain infrastructure — from SaaS platforms to automation workflows — so you invest once and compound the returns."

### Voice Across Surfaces

The voice is constant. The register adjusts by surface and stakes:

| Surface | Register | Word budget | Example |
|---|---|---|---|
| **Button label** | Imperative, 1-2 words | ≤ 2 | "Send draft" |
| **Page title** | Noun phrase, no verbs | ≤ 4 | "Service overview" |
| **Section heading** | Noun phrase or short clause | ≤ 6 | "Pending deployments" |
| **Empty state headline** | Outcome-led sentence | ≤ 8 | "No services yet. Deploy one to start." |
| **Tooltip** | One sentence, action-oriented | ≤ 12 | "Approve this change and [product] will deploy it now." |
| **Inline form helper** | One short sentence; what to enter, why it matters | ≤ 14 | "We'll email this address when builds complete." |
| **Toast / snackbar** | What happened + (optional) one undo or follow-up | ≤ 14 | "Deployed. Undo." |
| **Error toast** | What broke + what to do | ≤ 18 | "API token expired. Reconnect in Settings → Integrations." |
| **Confirmation dialog body** | Plain statement of consequence + revert path | ≤ 30 | "This will permanently delete 12 records. You cannot undo this. Type DELETE to confirm." |
| **Onboarding step** | One sentence outcome + one sentence action | ≤ 24 | "Connect your repository. [Product] will start deploying within 5 minutes." |
| **Email subject** | Specific, scannable, no clickbait | ≤ 60 chars | "3 new alerts from your infrastructure need review" |
| **Email body** | Direct, structured, signed | ≤ 120 words | (see Email Templates if applicable) |
| **Marketing hero** | Category claim + proof | ≤ 30 | "Your infrastructure. Deployed in 90 seconds. Monitored 24/7. No ops team required." |
| **Marketing body** | Outcome → mechanism → evidence | varies | "Deploy in 90 seconds. Ocoron builds, configures, and monitors your services. Average response time: 4ms." |
| **Documentation page intro** | What this page covers, in one sentence | ≤ 20 | "This page lists every available configuration option for the deployment pipeline." |
| **API reference** | Function signature first, prose second | n/a | (auto-generated; voice rules apply to descriptions) |
| **Customer support reply** | Acknowledge → diagnose → fix → confirm | ≤ 100 words | "Got it. The token expired at 14:02. I've extended the refresh window to 7 days. The service is back online — confirm at your end?" |
| **Legal / contractual** | Formal, complete, unambiguous | as needed | (see contract templates) |
| **Status-page incident** | What's degraded → impact → ETA → next update | ≤ 60 words | "Deployment pipeline is running with delay. Builds complete in 5-7 min instead of < 90 sec. Estimated recovery 14:30 UTC. Next update at 14:15." |

A voice that reads the same on a button and in a contract is broken. Same voice. Different register.

### Naming and Capitalization Rules

- **Sentence case** for headings, button labels, menu items, page titles. Title Case is forbidden in product UI.
- **Numerals over words** for any number ≥ 10, and for any number that's a count, ID, money, time, or measurement (use "3 services" not "three services"; "page 2" not "page two").
- **No exclamation marks** anywhere in product UI. Save them for marketing copy, and even there use sparingly.
- **No emoji in product UI** by default. Emoji are allowed in: user-authored content (email subjects, chat messages), and in the optional Celebrations setting (one emoji per milestone, never more).
- **Oxford comma** in English. Always.
- **Single quotes inside double quotes** when nesting in English copy. Don't mix.
- **Em-dashes**, not hyphens, for parenthetical breaks. With spaces around them in marketing, no spaces in compact UI strings.
- **Numerals format** with thin-space thousands separators where the locale supports it.

### Messaging Framework

#### Core Narrative

Most businesses hire teams to build and maintain digital systems. Those teams are expensive, slow, and hard to keep. Ocoron replaces that overhead with AI-powered infrastructure that deploys, monitors, and maintains itself — so you build once and compound the returns.

#### Message Pillars

**1. Build Once**
You shouldn't rebuild the same thing for every project. Ocoron's architecture is modular — standardized scaffolds, shared components, proven patterns. Every new project starts further ahead than the last.

*Evidence:* One design system across 7 product types. Shared authentication, deployment, and monitoring. Each new product ships in days, not months.

**2. Run Autonomously**
After deployment, your systems shouldn't need babysitting. Ocoron infrastructure monitors itself, heals itself, and alerts you only when human judgment is required.

*Evidence:* AI agents handle code review, deployment verification, and documentation. Automated health checks with self-recovery. Zero-touch operation as the default.

**3. Compound Over Time**
Every system Ocoron builds makes the next one faster, cheaper, and more reliable. Shared infrastructure, reusable components, and accumulated operational data create compounding returns on your initial investment.

*Evidence:* Standardized deployment pipeline reused across all products. Design system tokens enforced automatically. Each project inherits every improvement made to the platform.

#### Audience Messaging

| Audience | Key Message | Emphasis |
|---|---|---|
| **B2B buyers (enterprise)** | "Production-grade systems, delivered on spec, built to run without ongoing engineering overhead." | Reliability, fixed-price, autonomy, no vendor lock-in |
| **Technical partners** | "Production standards from the first commit. Type-safe, containerized, documented, reviewed by AI — every time." | Code quality, architecture, tooling, zero tech debt |
| **Grant bodies / investors** | "AI-native infrastructure company producing reusable, exportable digital assets with Teknokent-compliant IP." | R&D depth, AI/NLP integration, export potential, tax efficiency |

### Brand Architecture

#### Model: Branded House

Ocoron is the master brand. All digital products and services live under it.

#### Naming Convention

Format: **Ocoron [Name]** — product name is 1-2 words, lowercase-friendly, technical-sounding.

#### Naming Rules

1. Every digital product carries the Ocoron name.
2. Sub-brands do NOT get their own logos. They use: Ocoron wordmark + product name set in Inter 500.
3. Don't create a sub-brand until the product has paying users or is in active B2B presales. Until then, it's just "Ocoron."
4. Physical product brands (Atelier Rebul) are completely separate — no Ocoron branding on physical goods.
5. Ocoron is registered as a Teknokent LLC. The legal entity name appears on invoices and contracts; all product surfaces and marketing use "Ocoron" only.
6. Internally, sub-products can be referred to by their short name ("Fabrik"). Externally, always "Ocoron Fabrik."

#### Brand Map

| Entity | Brand Treatment | Customer-Facing? |
|---|---|---|
| Self-hosted PaaS / orchestration | **Ocoron Fabrik** | Only if externalized as a product |
| SaaS products | **Ocoron [TBD]** | Named when product reaches presale |
| B2B system design services | **Ocoron** (no sub-brand) | Yes — the company does the work |
| Candle manufacturing | **Atelier Rebul** | Independent brand, never co-branded |
| Teknokent LLC (Ocoron) | Legal entity name | Invoices and contracts only |

#### Co-Branding Rules

- Ocoron products may display "Powered by Ocoron" on client-facing deployments if contractually agreed.
- Third-party integrations use the partner's mark alongside Ocoron's, with equal sizing and clear separation.
- The Ocoron wordmark is never placed inside another company's logo, modified, or recolored to match their brand.

---

## Logo

- **Format:** Stencil-cut geometric wordmark with broken letterforms and rounded terminals.
- **Usage:** Always as SVG or image asset. Never recreate in a text font.
- **Variants:** Black on light, white on dark. No colored logo versions.
- **Clear space:** Minimum 1× the height of the "O" character on all sides.
- **Minimum size:** 80px width for digital, 20mm for print.

---

## Colour tokens

Every slot `core/design-system-template.md` § Token slots names, for both modes. **Dark is the
default mode.** In dark mode the state fills are light enough to read as text, so text ON them is
near-black (`#0A0A0A`); in light mode they are dark enough to read as text, so text on them is white.
The accent is the one fill that is never text in either mode — that is what `--color-accent-text` is for.

| Slot | Dark | Light | Role |
|---|---|---|---|
| `--surface-0` | `#0A0A0A` | `#FAFAFA` | Page/app background |
| `--surface-1` | `#141414` | `#FFFFFF` | Cards, panels |
| `--surface-2` | `#1A1A1A` | `#F5F5F5` | Elevated: modals, popovers |
| `--surface-3` | `#222222` | `#EEEEEE` | Hover, active list items |
| `--border` | `#2A2A2A` | `#E0E0E0` | Dividers, card edges — always 1px solid |
| `--border-control` | `#707070` | `#8A8A8A` | Input, select, checkbox and toggle boundaries |
| `--text-primary` | `#FFFFFF` | `#111111` | Headings, key data, primary labels |
| `--text-body` | `#E0E0E0` | `#333333` | Body copy, descriptions |
| `--text-muted` | `#888888` | `#6B6B6B` | Meta, timestamps, placeholders |
| `--color-accent` | `#5B5BF7` | `#5B5BF7` | Accent FILL, border, focus ring — never text |
| `--color-accent-hover` | `#5151E8` | `#5151E8` | Accent fill hover — darkens (a lighter hover cannot keep white text) |
| `--color-accent-fg` | `#FFFFFF` | `#FFFFFF` | Text on the accent fill |
| `--color-accent-text` | `#8A8AFF` | `#4A4AE0` | Accent AS TEXT (links, accent labels) |
| `--color-accent-muted` | `rgba(91,91,247,0.12)` | `rgba(91,91,247,0.12)` | Tags, selected rows, chat bubbles |
| `--color-success` · `-text` | `#27AE60` | `#196E3C` | Confirmations, completed states, positive deltas — fill and text are the same value in each mode |
| `--color-success-fg` | `#0A0A0A` | `#FFFFFF` | Text on the success fill |
| `--color-success-muted` | `rgba(39,174,96,0.12)` | `rgba(25,110,60,0.12)` | The subtle success tint |
| `--color-warning` · `-text` | `#F5A623` | `#855606` | Warnings, highlights, upgrade nudges — fill and text are the same value in each mode |
| `--color-warning-fg` | `#0A0A0A` | `#FFFFFF` | Text on the warning fill |
| `--color-warning-muted` | `rgba(245,166,35,0.12)` | `rgba(133,86,6,0.12)` | The subtle warning tint |
| `--color-danger` · `-text` | `#FF4444` | `#C30000` | Errors, destructive actions, critical alerts — fill and text are the same value in each mode |
| `--color-danger-fg` | `#0A0A0A` | `#FFFFFF` | Text on the danger fill |
| `--color-danger-muted` | `rgba(255,68,68,0.12)` | `rgba(195,0,0,0.12)` | The subtle danger tint |
| `--color-info` · `-text` | `#459DD6` | `#206591` | Informational badges, neutral status — fill and text are the same value in each mode |
| `--color-info-fg` | `#0A0A0A` | `#FFFFFF` | Text on the info fill |
| `--color-info-muted` | `rgba(69,157,214,0.12)` | `rgba(32,101,145,0.12)` | The subtle info tint |
| `--color-ai` · `-text` | `#B483C8` | `#83459D` | AI-generated content and suggestions; category coding — fill and text are the same value in each mode |
| `--color-ai-fg` | `#0A0A0A` | `#FFFFFF` | Text on the ai fill |
| `--color-ai-muted` | `rgba(180,131,200,0.12)` | `rgba(131,69,157,0.12)` | The subtle ai tint |
| `--focus-ring` | `var(--color-accent)` | `var(--color-accent)` | 2px solid, offset 2px |

`--color-secondary` and `--color-purple` are the retired names of `--color-warning` and `--color-ai`;
keep them only as aliases in existing code (`--color-secondary: var(--color-warning)`).

## Contrast table

Computed with the WCAG 2.2 formula from the values above — the lowest ratio of each pair across
`--surface-0`, `--surface-1` and `--surface-2` (`tests/test_ocoron_contrast_table.py` recomputes every
row from the table above and fails on drift). A changed value is not done until this table is
recomputed.

| Foreground | Background | Dark | Light | Needs |
|---|---|---|---|---|
| `--text-primary` | surface-0…2 | 17.40:1 | 17.32:1 | 4.5:1 |
| `--text-body` | surface-0…2 | 13.18:1 | 11.59:1 | 4.5:1 |
| `--text-muted` | surface-0…2 | 4.91:1 | 4.89:1 | 4.5:1 |
| `--color-accent-text` | surface-0…2 | 5.93:1 | 5.75:1 | 4.5:1 |
| `--color-accent-text` | its `-muted` tint over surface-1 | 5.64:1 | 5.33:1 | 4.5:1 |
| `--color-accent-fg` | `--color-accent` | 4.90:1 | 4.90:1 | 4.5:1 |
| `--color-accent` (as indicator / `--viz`) | surface-0…2 | 3.55:1 | 4.50:1 | 3.0:1 |
| `--color-success-text` | surface-0…2 | 6.06:1 | 5.77:1 | 4.5:1 |
| `--color-success-text` | its `-muted` tint over surface-1 | 5.50:1 | 5.29:1 | 4.5:1 |
| `--color-success-fg` | `--color-success` | 6.89:1 | 6.29:1 | 4.5:1 |
| `--color-success` (as indicator / `--viz`) | surface-0…2 | 6.06:1 | 5.77:1 | 3.0:1 |
| `--color-warning-text` | surface-0…2 | 8.59:1 | 5.78:1 | 4.5:1 |
| `--color-warning-text` | its `-muted` tint over surface-1 | 7.35:1 | 5.31:1 | 4.5:1 |
| `--color-warning-fg` | `--color-warning` | 9.77:1 | 6.30:1 | 4.5:1 |
| `--color-warning` (as indicator / `--viz`) | surface-0…2 | 8.59:1 | 5.78:1 | 3.0:1 |
| `--color-danger-text` | surface-0…2 | 5.11:1 | 5.80:1 | 4.5:1 |
| `--color-danger-text` | its `-muted` tint over surface-1 | 4.78:1 | 5.04:1 | 4.5:1 |
| `--color-danger-fg` | `--color-danger` | 5.81:1 | 6.32:1 | 4.5:1 |
| `--color-danger` (as indicator / `--viz`) | surface-0…2 | 5.11:1 | 5.80:1 | 3.0:1 |
| `--color-info-text` | surface-0…2 | 5.84:1 | 5.78:1 | 4.5:1 |
| `--color-info-text` | its `-muted` tint over surface-1 | 5.29:1 | 5.31:1 | 4.5:1 |
| `--color-info-fg` | `--color-info` | 6.64:1 | 6.30:1 | 4.5:1 |
| `--color-info` (as indicator / `--viz`) | surface-0…2 | 5.84:1 | 5.78:1 | 3.0:1 |
| `--color-ai-text` | surface-0…2 | 5.82:1 | 5.83:1 | 4.5:1 |
| `--color-ai-text` | its `-muted` tint over surface-1 | 5.25:1 | 5.34:1 | 4.5:1 |
| `--color-ai-fg` | `--color-ai` | 6.62:1 | 6.36:1 | 4.5:1 |
| `--color-ai` (as indicator / `--viz`) | surface-0…2 | 5.82:1 | 5.83:1 | 3.0:1 |
| `--color-accent-fg` | `--color-accent-hover` | 5.69:1 | 5.69:1 | 4.5:1 |
| `--border-control` | surface-0…2 | 3.51:1 | 3.17:1 | 3.0:1 |
| `--focus-ring` (= accent) | surface-0…2 | 3.55:1 | 4.50:1 | 3.0:1 |

**Forbidden pairs (whatever they compute to):** `--text-muted` on `--surface-3` (dark 4.49:1 — at the
line, too risky for body text); `--color-accent` as TEXT on any surface (dark 3.76:1 on `--surface-1`;
accent-as-text is `--color-accent-text`'s job); `--color-accent` text on `--color-accent-muted`; near-black text on `--color-accent` (4.04:1 — white
it is, 4.90:1).

**Why the accent text is mode-aware:** AA body text needs relative luminance ≥ 0.18866 on `#0A0A0A`
but ≤ 0.18333 on white — a disjoint range no single hex satisfies (`#5B5BF7` sits at 0.16422).

---

## Typography

### Font Stack

| Role | Font | Weights | Source |
|---|---|---|---|
| **Headings** (`--font-heading`) | Space Grotesk | 600, 700 | Google Fonts, SIL OFL 1.1 |
| **Body / UI** (`--font-body`) | Inter | 400, 500 | Google Fonts (variable), SIL OFL 1.1 |
| **Code / Data** (`--font-mono`) | JetBrains Mono | 300, 400 | Google Fonts, SIL OFL 1.1 |

### Type Scale

| Level | Size | Weight | Font | Letter-spacing | Usage |
|---|---|---|---|---|---|
| H1 | 32px | 700 | Space Grotesk | -0.5px | Page titles |
| H2 | 24px | 600 | Space Grotesk | -0.5px | Section titles |
| H3 | 18px | 600 | Space Grotesk | -0.3px | Card titles, subsections |
| Body | 14px | 400 | Inter | 0 | Default body text |
| Body small | 13px | 400 | Inter | 0 | Secondary text, descriptions |
| Micro-label | 10px | 500 | Inter | 1.5px | Uppercase labels, tag text |
| Code | 13px | 400 | JetBrains Mono | 0 | Code blocks, data tables, metrics |
| Data large | 28px | 300 | JetBrains Mono | -0.5px | Dashboard KPIs, big numbers |

### Rules

- Headings: always Space Grotesk. Never Inter or monospace for headings.
- Body text: always Inter. Never monospace for paragraphs or descriptions.
- Data/code: always JetBrains Mono. Tables with numeric data, code snippets, terminal output, metrics.
- Micro-labels: Inter 500, uppercase, letter-spacing 1.5px, 10px.
- Line-height: 1.5 for body, 1.2 for headings, 1.4 for code.
- Script coverage: Inter covers Latin and Cyrillic; add an Arabic-script fallback (e.g. Noto Sans Arabic) for `ar` and `fa` locales.

---

## Radius, icons and data visualisation

| Slot | Value |
|---|---|
| `--radius-card` · `--radius-tag` · `--radius-pill` · `--radius-button` | 8px · 3px · 20px · 6px |
| Icon library and style | Lucide; stroke 1.5px at 16px and 2px at 24px (set `strokeWidth` — Lucide's own default is 2); outline, rounded caps and joins |
| `--viz-1` … `--viz-6` | accent, info, ai, warning, danger, success — each mode's `--color-*` value above. In a chart that also encodes good and bad, stop at `--viz-4`: 5 and 6 are the danger and success hues |

---

## Sound

Ocoron's opt-in cues (the rules around them are the template's § Sound and Haptics):

- Success: 80ms 880Hz soft attack, 120ms decay. Pleasant but unobtrusive.
- Error: 60ms 220Hz, no decay tail. Brief, distinct from success.
- Notification: 100ms two-tone chime (440Hz + 660Hz, simultaneous). Quiet enough to be background.

---

## Ocoron on each scaffold

The template's § Scaffold Adaptation Matrix applies; these are the Ocoron-specific choices on top.

- **Theme mode:** dark is the default; first visit follows OS `prefers-color-scheme`, dark when the OS states none. An Ocoron project switches with `data-theme="dark|light"` on `<html>`, which the CSS below keys on.
- **saas-skeleton, desktop-app:** all three fonts; shadcn's variables filled from the tokens above.
- **static-site:** Space Grotesk and Inter only — drop JetBrains Mono unless the page shows code or data.
- **chrome-extension:** all three fonts, JetBrains Mono only for data displays.
- **mobile-app:** Space Grotesk and Inter loaded as custom fonts (a system sans-serif fallback where needed); the mobile packs map the tokens.
- **docusaurus:** dark tokens by default; code blocks in JetBrains Mono.
- **Light mode shadow:** subtle only — `0 1px 3px rgba(0,0,0,0.08)`.

---

## CSS custom properties

The template's defaults (spacing, density, motion, breakpoints) are not repeated here — Ocoron uses
them unchanged. On a Tailwind CSS-first project declare these in `@theme` (dark mode via
`@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *))`); on the saas-skeleton's
Tailwind config, fill shadcn's variables from them (template § Mapping to the scaffold's variables).

```css
:root {
  --surface-0: #0A0A0A;
  --surface-1: #141414;
  --surface-2: #1A1A1A;
  --surface-3: #222222;
  --border: #2A2A2A;
  --border-control: #707070;
  --text-primary: #FFFFFF;
  --text-body: #E0E0E0;
  --text-muted: #888888;
  --color-accent: #5B5BF7;
  --color-accent-hover: #5151E8;
  --color-accent-fg: #FFFFFF;
  --color-accent-text: #8A8AFF;
  --color-accent-muted: rgba(91,91,247,0.12);
  --color-success: #27AE60;
  --color-success-fg: #0A0A0A;
  --color-success-text: #27AE60;
  --color-success-muted: rgba(39,174,96,0.12);
  --color-warning: #F5A623;
  --color-warning-fg: #0A0A0A;
  --color-warning-text: #F5A623;
  --color-warning-muted: rgba(245,166,35,0.12);
  --color-danger: #FF4444;
  --color-danger-fg: #0A0A0A;
  --color-danger-text: #FF4444;
  --color-danger-muted: rgba(255,68,68,0.12);
  --color-info: #459DD6;
  --color-info-fg: #0A0A0A;
  --color-info-text: #459DD6;
  --color-info-muted: rgba(69,157,214,0.12);
  --color-ai: #B483C8;
  --color-ai-fg: #0A0A0A;
  --color-ai-text: #B483C8;
  --color-ai-muted: rgba(180,131,200,0.12);
  --focus-ring: var(--color-accent);
  --viz-1: var(--color-accent);
  --viz-2: var(--color-info);
  --viz-3: var(--color-ai);
  --viz-4: var(--color-warning);
  --viz-5: var(--color-danger);
  --viz-6: var(--color-success);
  --color-secondary: var(--color-warning); /* retired name */
  --color-purple: var(--color-ai); /* retired name */

  --font-heading: 'Space Grotesk', sans-serif;
  --font-body: 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  --radius-card: 8px;
  --radius-tag: 3px;
  --radius-pill: 20px;
  --radius-button: 6px;
}

[data-theme="light"] {
  --surface-0: #FAFAFA;
  --surface-1: #FFFFFF;
  --surface-2: #F5F5F5;
  --surface-3: #EEEEEE;
  --border: #E0E0E0;
  --border-control: #8A8A8A;
  --text-primary: #111111;
  --text-body: #333333;
  --text-muted: #6B6B6B;
  --color-accent: #5B5BF7;
  --color-accent-hover: #5151E8;
  --color-accent-fg: #FFFFFF;
  --color-accent-text: #4A4AE0;
  --color-accent-muted: rgba(91,91,247,0.12);
  --color-success: #196E3C;
  --color-success-fg: #FFFFFF;
  --color-success-text: #196E3C;
  --color-success-muted: rgba(25,110,60,0.12);
  --color-warning: #855606;
  --color-warning-fg: #FFFFFF;
  --color-warning-text: #855606;
  --color-warning-muted: rgba(133,86,6,0.12);
  --color-danger: #C30000;
  --color-danger-fg: #FFFFFF;
  --color-danger-text: #C30000;
  --color-danger-muted: rgba(195,0,0,0.12);
  --color-info: #206591;
  --color-info-fg: #FFFFFF;
  --color-info-text: #206591;
  --color-info-muted: rgba(32,101,145,0.12);
  --color-ai: #83459D;
  --color-ai-fg: #FFFFFF;
  --color-ai-text: #83459D;
  --color-ai-muted: rgba(131,69,157,0.12);
}
```

---

## Rules for coding agents

The template's § Rules for Coding Agents apply; these add Ocoron's own.

### Brand Rules

1. **Font assignment is strict.** Headings = Space Grotesk. Body = Inter. Code/data = JetBrains Mono. No exceptions.
2. **Values come from this file.** Use the tokens above; a new colour is proposed here first, with its contrast rows computed.
3. **Logo is always an asset.** Never render the Ocoron wordmark in a text font.

### Verbal Rules

4. **Never use forbidden language.** Check the Forbidden Language table before writing any user-facing copy. No exceptions.
5. **Brand name is "Ocoron."** Capital O, lowercase rest. No all-caps in text, no all-lowercase in text. Lowercase only in code/URLs.
6. **Lead with outcomes in all UI copy.** Button labels, tooltips, descriptions — state what happens, not how it works.
7. **Error messages must be actionable.** State what failed, why, and what the user should do next. Never "Something went wrong."
8. **No rhetorical questions** in any generated copy — headlines, descriptions, tooltips, onboarding flows. State the answer.
9. **Describe AI specifically.** When referencing AI capabilities, name the action: "AI reviews," "AI generates," "AI monitors." Never use "AI-powered" as a standalone adjective.
10. **Sub-brand naming requires approval.** Never generate a new product name or sub-brand. Use "Ocoron" until the human operator assigns a name.
