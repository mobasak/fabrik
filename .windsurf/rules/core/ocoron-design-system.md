---
description: Ocoron design system — the visual identity every Ocoron-branded GUI inherits: colour tokens, typography, motion, component patterns, states, accessibility. Read for ANY screen, component or design-token work on a saas-skeleton, static-site, docusaurus, chrome-extension or desktop-app surface; the design-system ladder in saas/60-saas-ui.md points here.
---
<!-- CONSUMER: Coding agents building UI + Traycer (epic-brief for visual decisions)
     GOAL: Single source of truth for visual identity — colors, typography, motion, components, states, accessibility
     TRAYCER USAGE: Referenced in all UI tickets. Shapes visual decisions during epic-brief.
     AGENT USAGE: Use design tokens, follow component patterns, apply motion language. Never invent colors/fonts. -->

# Ocoron Design System v2.0

> Single source of truth for OCORON-FAMILY products and surfaces. ⚠️ **A HOUSE identity, chosen — never defaulted** (operator ruling 2026-08-29): a SaaS uses this system only when its `docs/design-system.md` header declares it explicitly; every other UI project gets its own identity from brand-identiy-creator (the resolution ladder in `saas/60-saas-ui.md`). This file's STRUCTURAL scales (spacing, density, motion patterns, component patterns) may serve as the interim framework under a BIC brand — the brand tokens themselves must never arrive by default.
> Every new project references this file. No ad-hoc styling, messaging, or naming decisions.

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

## Color System

### Core Palette

| Token | Hex | Role |
|---|---|---|
| `--color-accent` | `#5B5BF7` | Brand accent as FILL/BORDER/FOCUS-RING only (buttons, progress bars, focus rings — non-text; 3.25–4.90:1 vs every surface clears WCAG 1.4.11's 3:1) |
| `--color-accent-hover` | `#5151E8` | Accent fill hover — DARKENS (white-on = 5.69:1; a lighten-on-hover is unsatisfiable with a white foreground) |
| `--color-accent-text` | `#8A8AFF` dark mode / `#4A4AE0` light mode | Accent used AS TEXT (links, accent labels) — MODE-AWARE by necessity: no single hex can be AA body text on both a dark and a white surface (see § Color Contrast) |
| `--color-accent-muted` | `rgba(91,91,247,0.12)` | Accent backgrounds (tags, badges, subtle highlights) |
| `--color-secondary` | `#F5A623` | Warnings, highlights, premium/upgrade nudges |
| `--color-danger` | `#FF4444` | Errors, destructive actions, critical alerts |
| `--color-success` | `#27AE60` | Confirmations, completed states, positive deltas |
| `--color-info` | `#2980B9` | Informational badges, tooltips, neutral status |
| `--color-purple` | `#9B59B6` | Category coding, tags, auxiliary status |

### Surface Hierarchy (Dark Mode — Default)

| Token | Hex | Role |
|---|---|---|
| `--surface-0` | `#0A0A0A` | Page/app background |
| `--surface-1` | `#141414` | Card backgrounds, panels |
| `--surface-2` | `#1A1A1A` | Elevated surfaces, modals, popovers |
| `--surface-3` | `#222222` | Hover states on cards, active list items |
| `--border` | `#2A2A2A` | All borders, dividers — always 1px solid |

### Surface Hierarchy (Light Mode — Mandatory)

| Token | Hex | Role |
|---|---|---|
| `--surface-0` | `#FAFAFA` | Page/app background |
| `--surface-1` | `#FFFFFF` | Card backgrounds, panels |
| `--surface-2` | `#F5F5F5` | Elevated surfaces, modals |
| `--surface-3` | `#EEEEEE` | Hover states |
| `--border` | `#E0E0E0` | All borders, dividers |

### Text Hierarchy

| Token | Dark Mode | Light Mode | Role |
|---|---|---|---|
| `--text-primary` | `#FFFFFF` | `#111111` | Headings, key data, primary labels |
| `--text-body` | `#E0E0E0` | `#333333` | Body copy, descriptions |
| `--text-muted` | `#888888` | `#999999` | Meta info, timestamps, placeholders |

### Color Contrast (Verified Pairs)

Verified contrast ratios for the canonical token pairings:

| Foreground | Background | Ratio | Level | Use |
|---|---|---|---|---|
| `--text-primary` `#FFFFFF` | `--surface-0` `#0A0A0A` | 19.80:1 | AAA | Body text on page |
| `--text-primary` `#FFFFFF` | `--surface-1` `#141414` | 18.42:1 | AAA | Body text on cards |
| `--text-body` `#E0E0E0` | `--surface-0` `#0A0A0A` | 15.00:1 | AAA | Default body |
| `--text-muted` `#888888` | `--surface-0` `#0A0A0A` | 5.58:1 | AA | Meta, timestamps |
| `--text-muted` `#888888` | `--surface-1` `#141414` | 5.20:1 | AA | Meta on cards |
| `--color-accent-text` `#8A8AFF` | `--surface-0` `#0A0A0A` | 6.75:1 | AA | Links, accent text (dark mode; `#4A4AE0` on white = 6.27:1 for light mode) |
| `#FFFFFF` | `--color-accent` `#5B5BF7` | 4.90:1 | AA | Primary button text — white, at body size |
| `#FFFFFF` | `--color-accent-hover` `#5151E8` | 5.69:1 | AA | Primary button text on hover |
| `--color-success` `#27AE60` | `--surface-0` `#0A0A0A` | 6.89:1 | AA | Success text |
| `--color-danger` `#FF4444` | `--surface-0` `#0A0A0A` | 5.81:1 | AA | Error text |
| `--color-secondary` `#F5A623` | `--surface-0` `#0A0A0A` | 9.77:1 | AAA | Warning text |

**Light mode pairs** must be re-validated per project; track in an accessibility audit file.

**Forbidden pairs (do not use):**
- `--text-muted` on `--surface-3` (4.49:1 — passes AA numerically but too risky for body text; forbidden stands)
- `--color-accent` `#5B5BF7` text on `--color-accent-muted` background (insufficient)
- `#0A0A0A` dark text on `--color-accent` `#5B5BF7` (4.04:1 — FAILS AA; use `#FFFFFF`, 4.90:1)
- `--color-accent` `#5B5BF7` as TEXT on any surface (4.04:1 on `--surface-0`, 3.76:1 on `--surface-1` — FAILS AA; accent-as-text is what `--color-accent-text` exists for)

**Standing rule — dual-role color tokens need TWO values.** A color used both as a fill-background
and as foreground text has two independent constraints: the fill needs a foreground clearing 4.5:1
against IT, and the text needs 4.5:1 against the surfaces it sits on. On a dark-and-light product
those constraints are frequently disjoint, so the text value must be mode-aware. This applies to
EVERY semantic color (success/info/warning/destructive), not just the accent — verify each with the
WCAG formula, never from memory (this pack shipped 9 wrong ratios in 11 rows, 3 inverted, before
the 2026-08-06 audit).

---

## Typography

### Font Stack

| Role | Font | Weights | Source |
|---|---|---|---|
| **Headings** | Space Grotesk | 600, 700 | Google Fonts (free) |
| **Body / UI** | Inter | 400, 500 | Google Fonts (free, variable) |
| **Code / Data** | JetBrains Mono | 300, 400 | Google Fonts (free) |

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
- Micro-labels: Inter 500, uppercase, letter-spacing 1.5px, 9-10px.
- Line-height: 1.5 for body, 1.2 for headings, 1.4 for code.

---

## Iconography

Ocoron uses **Lucide** as the primary icon library.

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
| Toolbar | 18px | 1.5px |
| Button (with label) | 16px | 1.5px |
| Floating action / icon-only button | 20px | 1.5px |
| Empty state hero | 48px | 2px |
| Onboarding hero | 64px | 2px |

### Custom Icons

When a Lucide icon doesn't exist for a needed concept, add a custom icon to the project icon library. Custom icons must match Lucide's style:

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
I6. The Lucide library is the source of truth. If you need an icon, search Lucide first. Only after confirming Lucide does not have the concept (or does not have it in the right metaphor) may you commission a custom icon.
I7. Icons must remain legible at minimum size (16px). Detail beyond what reads at 16px is forbidden — it adds noise without adding meaning.
I8. Icon-only buttons require `aria-label` for accessibility. No exceptions.

---

## Motion Language

Motion is functional, never decorative. Every animation communicates one of: state change, attention direction, system status, or progress. Motion that does none of those is removed.

### Decorative motion (carve-out)

Purely ambient motion — particle backgrounds, animated/gradient backdrops, text/cursor effects (e.g. components from [reactbits.dev](https://reactbits.dev)) — is exempt from the "functional only" rule above, but ONLY:

1. **On marketing / landing surfaces only.** Never on product/app surfaces — those stay bound by the functional-motion scale below (interaction feedback tops out at `--motion-default: 150ms`).
2. **Re-tokenized first.** No hardcoded colors, durations, or easings: the imported component must consume Ocoron design tokens — this is the existing "never invent colors/fonts" rule, restated for imported components.
3. **`prefers-reduced-motion` honored.** A static or near-static fallback renders when the user requests reduced motion.
4. **Gate-clean.** It passes the existing a11y/visual/token gate with no new contrast, focus, or motion-safety regressions.

ReactBits is **copy-and-own** (like shadcn/ui): take the single component you need at point of use, paste it in, and re-tokenize it — it is NOT a dependency and NOT a fabrik-lib module (never add it to `package.json` or `fabrik-lib`).

### Duration Scale

| Token | Value | Use |
|---|---|---|
| `--motion-instant` | `0ms` | State swaps where motion would distract (toggle states, immediate value updates) |
| `--motion-fast` | `100ms` | Hover, focus, small surface transitions |
| `--motion-default` | `150ms` | Default. Most transitions. Matches the base `0.15s ease` interaction token. |
| `--motion-slow` | `250ms` | Modal, drawer, sheet enters and exits |
| `--motion-deliberate` | `400ms` | Onboarding step transitions, hero animations on first viewport entry |
| `--motion-celebration` | `600ms` | Single-shot success animations (milestone reached, major action completed) |

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

**Route change:** instant content swap, with 80ms skeleton flash if data is still loading. No fade-on-route.

**Skeleton shimmer:** `linear-gradient` translated `-100% → 100%` over `1500ms linear`, infinite. Only on initial load, never as a permanent state.

**AI-thinking indicator:** three dots, each `opacity 0.3 → 1 → 0.3` staggered by 150ms, `--ease-default`. Used only while AI is actively processing a user-initiated action.

**Success celebration:** check-mark stroke draw-on over `--motion-celebration` with `--ease-spring`, no confetti, no sound (sound is opt-in per user, see Sound and Haptics).

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
- AI-thinking indicator becomes a single static `...` glyph.
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

## Component Patterns

### Cards

```
Background: var(--surface-1)
Border: 1px solid var(--border)
Border-radius: 8px
Padding: 16px
Shadow: none (dark mode kills shadows — use borders)
Hover: background var(--surface-3), translateY(-1px), transition 0.15s
```

### Tags / Badges

```
Font: Inter 500, 9px, uppercase, letter-spacing 1.5px
Padding: 3px 8px
Border-radius: 3px
Background: color-specific muted variant (e.g., rgba(91,91,247,0.12) for accent)
Text: the color's TEXT variant (e.g., var(--color-accent-text) — never the raw fill hex as text)
```

### Pills

```
Font: Inter 400, 12px
Padding: 4px 12px
Border-radius: 20px
Border: 1px solid var(--border)
Background: transparent
Hover: background var(--surface-3)
```

### Buttons

```
Primary:
  Background: var(--color-accent)
  Text: #FFFFFF (4.90:1 — AA at body size)
  Font: Inter 500, 13px
  Padding: 8px 16px
  Border-radius: 6px
  Hover: var(--color-accent-hover), translateY(-1px)

Secondary:
  Background: transparent
  Border: 1px solid var(--border)
  Text: var(--text-primary)
  Hover: background var(--surface-3)

Danger:
  Background: var(--color-danger)
  Text: #FFFFFF
```

### Tab Bar

```
Position: sticky top
Font: Inter 500, 11px, uppercase, letter-spacing 1px
Active: text var(--color-accent), border-bottom 2px solid var(--color-accent)
Inactive: text var(--text-muted)
Layout: equal-width flex items
```

### Progress Bars

```
Track: var(--surface-3)
Fill: var(--color-accent)
Height: 4px
Border-radius: 2px
```

### Collapsible Blocks

```
Toggle: minimal +/- icon, no accordion animation bloat
Header: Space Grotesk 600, 14px
Border: 1px solid var(--border) on container
Transition: max-height 0.15s ease
```

### Data Hierarchy Pattern

```
Headline: var(--text-primary), Space Grotesk 600
Body: var(--text-body), Inter 400
Meta: var(--text-muted), Inter 400, 12px
Numeric: JetBrains Mono 300-400
```

### KPI Card

Used on dashboards for key performance indicators.

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

Used on dashboard activity rails and inside [module] views.

```
Layout: 24px icon + content + timestamp
Icon: monochrome, --text-muted by default
Source label (above content): Inter 500, uppercase, 10px, letter-spacing 1.5px, --text-muted
Content: Inter 400, 14px, --text-body
Timestamp: Inter 400, 12px, --text-muted
Always name the source that produced the event ("[Module] completed weekly report generation").
Hover: --surface-3, no lift
```
## Density Modes

Ocoron supports three density modes. Users select their preference in workspace settings; the choice persists per-device.

### Token Tables

#### Comfortable (Default)

| Token | Value |
|---|---|
| `--density-row-height` | 48px |
| `--density-cell-padding` | 12px 16px |
| `--density-card-padding` | 16px |
| `--density-section-gap` | 24px |
| `--density-input-height` | 40px |
| `--density-font-body` | 14px |
| `--density-font-meta` | 12px |

#### Compact (Power User)

| Token | Value |
|---|---|
| `--density-row-height` | 32px |
| `--density-cell-padding` | 4px 8px |
| `--density-card-padding` | 8px |
| `--density-section-gap` | 12px |
| `--density-input-height` | 28px |
| `--density-font-body` | 13px |
| `--density-font-meta` | 10px |

#### Spacious (Accessibility)

| Token | Value |
|---|---|
| `--density-row-height` | 56px |
| `--density-cell-padding` | 16px 20px |
| `--density-card-padding` | 24px |
| `--density-section-gap` | 32px |
| `--density-input-height` | 48px |
| `--density-font-body` | 16px |
| `--density-font-meta` | 14px |

### Density Rules

- **D1:** The density toggle applies to data-heavy views (tables, lists, kanban) and settings panels. Marketing pages, onboarding, and landing pages always use Comfortable.
- **D2:** All touch targets must remain >= 44px in height regardless of density mode. If Compact would shrink a button or link below 44px on a touch device, override to 44px.
- **D3:** Switching density never causes data loss or triggers a page reload. Apply density tokens via CSS custom properties on the `<body>` or root container.
- **D4:** Density persists per-device in `localStorage`. Default is Comfortable. The setting is independent of dark/light mode.
- **D5:** Embedded third-party modules (iframes, embedded widgets) are exempt from density tokens — they manage their own internal spacing. The host container still respects density for surrounding chrome.

---

## Data Tables

### Anatomy

```
┌────────────────────────────────────────────────────────┐
│ [Toolbar]  Filters ▼  Search ░░░░░░  Export ⬇  ⋮ More │
├──┬────────────┬──────────┬──────────┬─────────┬────────┤
│☐ │ Column A ▲ │ Column B │ Column C │ Col D   │ Actions│  ← Header row
├──┼────────────┼──────────┼──────────┼─────────┼────────┤
│☐ │ Data       │ Data     │ Data     │ Data    │ ⋮      │  ← Body row
│☐ │ Data       │ Data     │ Data     │ Data    │ ⋮      │
│☐ │ Data       │ Data     │ Data     │ Data    │ ⋮      │
├──┴────────────┴──────────┴──────────┴─────────┴────────┤
│  ◀ 1 2 3 … 12 ▶       Showing 1–25 of 293             │  ← Pagination
└────────────────────────────────────────────────────────┘
```

### Header Row

- Font: Inter 500, `--density-font-meta`, uppercase, letter-spacing 1px.
- Background: `var(--surface-1)`.
- Sticky top when scrolling the table body.
- Sort indicator: `▲` ascending, `▼` descending. Only one column sorted at a time unless the product explicitly supports multi-sort.
- Resizable columns via drag handle (cursor: `col-resize`).

### Body Rows

- Font: Inter 400, `--density-font-body`.
- Alternate row striping: odd rows `var(--surface-1)`, even rows `var(--surface-0)`. Subtle — never high-contrast zebra.
- Hover: `var(--surface-3)`.
- Selected: `var(--color-accent-muted)` background, left border 2px solid `var(--color-accent)`.
- Row height: `var(--density-row-height)`.
- Cell padding: `var(--density-cell-padding)`.

### Selection

- Checkbox column is always the first column, 40px wide.
- Header checkbox toggles select-all for the current page (not all pages).
- Bulk action bar appears above the table when >= 1 row selected, listing available actions (e.g., Delete, Export, Assign).
- The bar shows count: "3 selected" with a "Clear selection" link.

### Row Actions

- Overflow menu (`⋮`) in the last column. Opens a dropdown with contextual actions.
- Maximum 5 actions in the menu. More than 5 → group under sub-menus.
- Primary action (e.g., "Open") can also be triggered by clicking the row itself (not the checkbox column).
- Destructive actions (Delete) are always last, styled with `var(--color-danger)`.

### Filtering

- Filter bar sits above the table, below the toolbar.
- Active filters shown as pills with `×` dismiss buttons.
- Filter dropdown uses the standard popover pattern: `var(--surface-2)` background, `var(--border)` border.
- Common filter types: text search, single-select, multi-select, date range, numeric range.
- Filters apply immediately (no "Apply" button) with a 300ms debounce on text inputs.

### Pagination and Loading

- Default page size: 25 rows. Options: 10 / 25 / 50 / 100.
- Pagination controls at bottom-right: page numbers with ellipsis for large ranges.
- "Showing X–Y of Z" label at bottom-left.
- Loading state: skeleton rows (3–5 rows of pulsing `var(--surface-3)` blocks) replace the body. Header and pagination remain visible.
- Infinite scroll alternative: allowed for feeds/timelines, never for data management tables.

### Empty and Error States

- **No data yet:** Centered illustration (optional) + heading + description + primary CTA. Example: "No invoices yet — Create your first invoice."
- **Filtered to zero:** "No results match your filters" + "Clear all filters" link. No illustration.
- **Error loading:** "Failed to load data" + "Retry" button. Red accent on the message using `var(--color-danger)`.

### Export

- Export button in toolbar. Formats: CSV (default), XLSX, PDF.
- Export respects current filters and sort order.
- Filename pattern: `{product}-{resource}-{YYYY-MM-DD}.{ext}` (e.g., `{product}-invoices-2026-05-23.csv`).
- For large datasets (>1000 rows), export runs in background with a toast notification on completion.

### Density Mapping

| Density | Row height | Cell padding | Font |
|---|---|---|---|
| Comfortable | 48px | 12px 16px | 14px |
| Compact | 32px | 4px 8px | 13px |
| Spacious | 56px | 16px 20px | 16px |

### Table Rules

- **TBL1:** Every table must support keyboard navigation: `Tab` to move between interactive cells, `Arrow` keys to move between rows, `Space` to toggle selection, `Enter` to open row.
- **TBL2:** Sortable columns must show a sort indicator in the header. Default sort order is defined per-resource and documented in the API.
- **TBL3:** Column widths are user-resizable and persist per-user. Provide sensible defaults based on content type (dates get ~120px, names get ~200px, statuses get ~100px).
- **TBL4:** Tables with >5 columns must support column visibility toggling via a "Columns" dropdown in the toolbar.
- **TBL5:** Numeric columns are right-aligned. Text columns are left-aligned. Status/badge columns are center-aligned.
- **TBL6:** Date columns render in the user's locale format (see Formatting section). Always show relative time on hover tooltip.
- **TBL7:** Row actions must be accessible without hovering — the overflow menu (`⋮`) is always visible, not hidden-until-hover.
- **TBL8:** Empty and error states must never show a blank white/black void. Always provide context, guidance, and a CTA.
- **TBL9:** Selection state persists across pagination within a single session. Navigating away clears selection.
- **TBL10:** Export must never include columns the user has hidden. Export filename follows the `{product}-{resource}-{date}.{ext}` pattern.

---

## Forms and Inline Editing

### Form Layout

- Forms use a single-column layout by default. Two-column layout allowed only for wide viewports (>1024px) with logically grouped fields.
- Section grouping: related fields grouped under a section heading (H3, Space Grotesk 600) with `var(--space-lg)` gap between sections.
- Card container: each form section wrapped in a card (`var(--surface-1)`, `var(--border)`, `border-radius: 8px`, padding `var(--space-md)`).

### Labels

- Position: above the input (never floating, never beside).
- Font: Inter 500, 13px, `var(--text-body)`.
- Required indicator: red asterisk `*` after the label text, colored `var(--color-danger)`.
- Optional fields: append "(optional)" in `var(--text-muted)` after the label. Prefer marking optional fields when most fields are required; mark required fields when most are optional.

### Inputs

- Height: `var(--density-input-height)`.
- Background: `var(--surface-0)`.
- Border: 1px solid `var(--border)`.
- Border-radius: `var(--radius-button)` (6px).
- Focus: border color `var(--color-accent)`, box-shadow `0 0 0 2px var(--color-accent-muted)`.
- Placeholder text: `var(--text-muted)`, Inter 400.
- Disabled: opacity 0.5, cursor `not-allowed`.

### Validation

- Validate on blur for individual fields. Validate on submit for the full form.
- Error message appears below the input, Inter 400, 12px, `var(--color-danger)`.
- Error border: `var(--color-danger)` replaces `var(--border)`.
- Success indicator: green checkmark icon inline (right side of input) after correction. Do not turn the entire border green — it is too noisy.
- Summary of errors: if >2 errors on submit, show a dismissible banner at the top of the form listing all errors with anchor links to each field.

### Save Behavior — draft persistence is CONTINUOUS and restore is AUTOMATIC (every GUI type)

- **Nothing the user typed — and nothing the AI generated for them — is ever lost.** Every form,
  wizard, editor, and AI-populated surface persists its full working state to durable browser
  storage (`localStorage`/IndexedDB) **continuously on change** (debounce ≤1s per keystroke, and
  flush on `blur`/`visibilitychange`/`pagehide`) — never on a fixed 30s timer, which loses up to
  30s of work on a crash.
- **Restore is automatic and silent** on ANY return path — refresh, Back/Forward, reopened tab,
  a tab left open for days, browser or laptop crash: the user continues exactly where they left
  off, down to the last letter in the last field. No "Restore draft?" prompt — the draft simply
  IS the page state.
- **The draft clears on exactly one event: the entity is successfully created/submitted** (or
  the user explicitly discards it via a labeled control). Navigation, timeouts, and errors never
  clear it. Key drafts per entity+user (e.g. `draft:<entity>:<id|new>`) so parallel drafts don't
  collide, and version the schema so a stale draft from an older shape degrades to a partial
  restore, never a crash.
- Explicit save: primary button at the bottom-right of the form. Label: "Save" (not "Submit" unless it's a submission workflow).
- Optimistic save: show success immediately, revert on server error with a toast.
- Dirty state: with continuous persistence a navigate-away confirm is unnecessary for DRAFT
  safety (the state survives regardless); use a browser-level confirm only where leaving has a
  side effect beyond the draft (e.g. abandoning a payment in flight).

### Wizards (Multi-Step Forms)

- Step indicator at the top: horizontal stepper with numbered circles connected by lines.
- Active step: `var(--color-accent)` fill. Completed: `var(--color-success)` fill with checkmark. Upcoming: `var(--border)` outline.
- Navigation: "Back" (secondary button, left) and "Continue" (primary button, right). Final step: "Continue" becomes "Finish" or the domain-specific action label.
- Validation per-step: block "Continue" until the current step is valid. Show inline errors.
- Step count: 2–5 steps maximum. More than 5 → reconsider the UX.

### Inline Editing

- Triggered by clicking on editable text or an "Edit" icon.
- The text transforms into an input pre-filled with the current value. Same input styling as forms.
- Save: `Enter` key or blur. Cancel: `Escape` key.
- Show a subtle pencil icon on hover to indicate editability. Icon: 14px, `var(--text-muted)`.
- Inline editing is for single-field updates. Multi-field edits → open a modal or navigate to a form.

### Form Rules

- **F1:** Every form field must have a visible label. Placeholder text is not a substitute for a label.
- **F2:** Validation messages must be specific. "Invalid input" is forbidden — say what is wrong and what is expected (e.g., "Email must include @ and a domain").
- **F3:** Destructive form actions (delete account, remove member) require a confirmation step — either a modal or a type-to-confirm input.
- **F4:** Forms must be fully navigable by keyboard: `Tab` between fields, `Enter` to submit, `Escape` to cancel/close.
- **F5:** File upload fields show accepted formats and max size before the user selects a file. Progress bar during upload.
- **F6:** Auto-save must never silently overwrite server data. If the server version is newer, prompt the user to choose which version to keep.
- **F7:** Select/dropdown fields with >10 options must include a search/filter input inside the dropdown.
- **F8:** Date pickers must respect the user's locale for format and first-day-of-week. Always allow manual text entry as an alternative to the calendar widget.

---

## Search and Command Palette

### Trigger

- Keyboard shortcut: `Cmd+K` (macOS) / `Ctrl+K` (Windows/Linux).
- Also accessible via a search icon in the top navigation bar.
- Opens a centered modal overlay with a blurred backdrop (`backdrop-filter: blur(8px)`).

### Layout

```
┌─────────────────────────────────────────────┐
│ 🔍 Search or type a command…                │
├─────────────────────────────────────────────┤
│ Recent                                      │
│   Invoice #1042               ↵ to open     │
│   Customer: Acme Corp         ↵ to open     │
│ ───────────────────────────────────────────  │
│ Commands                                    │
│   Create new invoice          ↵ to run      │
│   Go to Settings              ↵ to run      │
│ ───────────────────────────────────────────  │
│ Ask AI                                      │
│   "Summarize overdue invoices" ↵ to ask     │
└─────────────────────────────────────────────┘
```

- Width: 560px, max-height: 420px.
- Background: `var(--surface-2)`.
- Border: 1px solid `var(--border)`.
- Border-radius: 12px.
- Shadow: `0 16px 48px rgba(0,0,0,0.4)` (this is the one exception where shadow is used in dark mode — modal overlays).

### Result Categories

Results are grouped by type, in this order:

1. **Recent** — last 5 items the user interacted with, matching the query.
2. **Navigation** — pages and views (e.g., "Go to Settings", "Go to Invoices").
3. **Records** — matching entities from the database (contacts, invoices, projects, etc.).
4. **Commands** — actions the user can trigger (e.g., "Create invoice", "Export CSV").
5. **Ask AI** — freeform natural-language queries sent to the AI assistant.

Each category has a muted label header (Inter 500, 10px, uppercase, `var(--text-muted)`).

### Result Row

- Height: 40px.
- Icon (16px) + label (Inter 400, 14px) + meta text (Inter 400, 12px, `var(--text-muted)`, right-aligned).
- Active/highlighted row: `var(--surface-3)` background.
- No images or avatars in search results — icons only for speed.

### Keyboard Navigation

- `↑` / `↓` to navigate results.
- `Enter` to select/execute.
- `Escape` to close.
- `Tab` to jump between category sections.
- Typing immediately filters results — no "Search" button.

### AI Search Section

- When the user's query does not match any record, navigation, or command, the palette shows an "Ask [product]" option at the bottom.
- Selecting it sends the query to the AI assistant and transitions the palette into a conversational panel (see AI Interaction Patterns).
- AI results stream inline within the palette. The user can press `Escape` to dismiss or `Enter` to act on the AI suggestion.

### Palette Rules

- **M1:** The palette must open in <100ms. Pre-load recent items and navigation targets on app boot.
- **M2:** Search is fuzzy — typos and partial matches must return results. Use a client-side fuzzy search library (e.g., Fuse.js) for instant results, backed by a server search for records.
- **M3:** Results update as the user types with <50ms perceived latency for local results and <300ms for server results.
- **M4:** The palette never shows more than 10 results per category. If more exist, show a "View all X results" link at the bottom of the category.
- **M5:** Command names are human-readable verbs: "Create invoice", "Export CSV", "Invite member". Never internal IDs or technical slugs.
- **M6:** The palette must be fully functional via keyboard. Mouse interaction is optional, not required.
- **M7:** Closing the palette clears the search input. Re-opening shows recent items by default.
- **M8:** The palette respects permissions — users only see records and commands they have access to.

---

## Charts and Data Visualization

### Chart Library

Recharts (React) is the standard chart library for all Ocoron products. It renders SVG, supports responsive containers, and integrates with the Ocoron token system.

### Color Rules

- Primary data series: `var(--color-accent)` (`#5B5BF7`).
- Secondary series: `var(--color-info)` (`#2980B9`).
- Tertiary series: `var(--color-purple)` (`#9B59B6`).
- Warning/alert series: `var(--color-secondary)` (`#F5A623`).
- Danger/negative series: `var(--color-danger)` (`#FF4444`).
- Success/positive series: `var(--color-success)` (`#27AE60`).
- If more than 6 series are needed, use opacity variants (80%, 60%) of the above colors. Never invent new colors.

### Chart Types — When to Use

| Chart Type | Use When | Never Use When |
|---|---|---|
| **Line** | Showing trends over time (revenue, signups, response time) | Fewer than 3 data points |
| **Bar** | Comparing discrete categories (revenue by product, count by status) | More than 12 categories |
| **Stacked Bar** | Showing composition within categories | More than 5 sub-categories |
| **Area** | Emphasizing volume over time (cumulative revenue, usage) | Comparing multiple independent series (they overlap) |
| **Pie / Donut** | Part-of-whole with 2–5 slices | More than 5 slices. Use a horizontal bar chart instead |
| **Sparkline** | Inline trend indicator in a table cell or KPI card | When the user needs to read exact values |
| **Scatter** | Correlation between two numeric variables | Fewer than 15 data points |

### Grid and Axes

- Grid lines: `var(--border)`, 1px, dashed. Horizontal grid only (no vertical grid lines unless it's a scatter plot).
- Axis labels: Inter 400, 11px, `var(--text-muted)`.
- Axis lines: `var(--border)`, 1px solid.
- Y-axis: always start at 0 for bar charts. Line/area charts may use a non-zero baseline if the variance is small relative to the absolute values — but add a visual break indicator.
- X-axis: rotate labels 45deg if they overlap. Truncate long labels with ellipsis.

### Interactivity

- Tooltip on hover: `var(--surface-2)` background, `var(--border)` border, border-radius 6px. Shows the exact value, formatted per locale.
- Click on data point: optional drill-down. If supported, show a cursor pointer and navigate to the detail view.
- Legend: positioned below the chart, horizontal layout. Click to toggle series visibility.
- Responsive: charts fill their container width. Minimum height: 200px. Aspect ratio is not fixed.

### Chart Rules

- **C1:** Every chart must have a title (H3, Space Grotesk 600) and an optional subtitle explaining the time range or filter context.
- **C2:** Never use 3D effects, gradients on bars, or decorative elements. Flat, clean, data-first.
- **C3:** All charts must include an accessible data table alternative (expandable, hidden by default) for screen reader users.
- **C4:** Loading state: show a skeleton chart (pulsing gray rectangle matching the chart dimensions). Never show a spinner overlaid on a half-rendered chart.
- **C5:** Empty state: "No data for this period" + suggestion to adjust the date range. Never show an empty axis grid with no data.
- **C6:** Use JetBrains Mono for all numeric values in tooltips and axis labels.
- **C7:** Animations: data points animate in on first render (0.3s ease). Subsequent updates animate transitions (0.15s). No looping animations.

---

## States (Enriched)

### Loading

#### Skeleton Loading

- Used for initial page/component loads where the layout is known.
- Render placeholder blocks matching the shape of the content: rectangles for text lines, circles for avatars, rounded rectangles for cards.
- Skeleton color: `var(--surface-3)` with a shimmer animation (left-to-right gradient pulse, 1.5s, infinite).
- Never mix skeleton and real content in the same component — the entire component is either skeleton or rendered.

#### Indefinite Loads (>3 seconds)

- If a load exceeds 3 seconds, show a message below the skeleton: "Still loading..." in `var(--text-muted)`.
- If a load exceeds 10 seconds, add a "Retry" link below the message.
- If a load exceeds 30 seconds, transition to an error state: "This is taking too long. Please try again."

### Empty — No Data Yet

- Full-component centered layout.
- Optional illustration (monochrome, line-art style, max 120px height).
- Heading: Inter 500, 16px, `var(--text-primary)`. Example: "No invoices yet."
- Description: Inter 400, 14px, `var(--text-body)`. Example: "Create your first invoice to get started."
- CTA: primary button below the description.

### Empty — Filtered to Zero

- Same layout as "No Data Yet" but without illustration.
- Heading: "No results match your filters."
- CTA: "Clear all filters" link (not a button — it's a low-commitment action).
- Never suggest creating a new record in this state — the user is looking for existing data.

### Error

- Red accent: left border 3px solid `var(--color-danger)` on the error container.
- Heading: Inter 500, 16px, `var(--text-primary)`. Example: "Failed to load invoices."
- Description: Inter 400, 14px, `var(--text-body)`. Explain what went wrong if known.
- CTA: "Retry" primary button + optional "Contact support" secondary link.
- Never show raw error codes or stack traces to the user. Log them to the console and error tracker.

### Permission Denied

- Heading: "You don't have access to this resource."
- Description: explain which permission is needed and who can grant it.
- CTA: "Request access" button (if the product supports access requests) or "Go back" link.
- Never show the content behind a blurred overlay — either show the permission message or redirect.

### Success (Rare and Discrete)

- Success states should be brief and non-blocking.
- Preferred: toast notification (see Notification System) that auto-dismisses after 4 seconds.
- Only use a full-page success state for significant milestones (e.g., completing onboarding, first payment processed).
- Full-page success: green checkmark icon (48px), heading, description, and a "Continue" button.

### Partial Success / Warnings

- Used when an action partially completed (e.g., "3 of 5 emails sent successfully").
- Yellow accent: left border 3px solid `var(--color-secondary)` on the container.
- List the successful and failed items separately.
- CTA: "Retry failed items" button.

---

## Notification System

### Taxonomy

| Level | Color | Persistence | Auto-Dismiss | Example |
|---|---|---|---|---|
| **Critical** | `var(--color-danger)` | Persistent banner, top of page | No | "Payment failed. Update your billing info." |
| **Actionable** | `var(--color-accent)` | Toast, bottom-right | 8s | "New comment on Invoice #1042 — Reply" |
| **Informational** | `var(--color-info)` | Toast, bottom-right | 4s | "Export complete. Download ready." |
| **AI Suggestion** | `var(--color-purple)` | Inline card, contextual | No | "AI detected a duplicate contact — Merge?" |
| **Digest** | `var(--text-muted)` | Activity feed only | N/A | "12 invoices were auto-sent yesterday." |

### Throttling and Aggregation

- If >3 notifications arrive within 10 seconds, aggregate into a single toast: "5 new notifications" with a link to the activity feed.
- Critical notifications are never aggregated — each one is shown individually.
- Rate limit: maximum 1 toast per 3 seconds. Queue excess notifications.

### Channels

| Channel | When |
|---|---|
| **In-app toast** | User is active in the app. Default for Actionable and Informational. |
| **In-app banner** | Critical alerts. Persists until dismissed or resolved. |
| **Browser push** | User has granted permission. Used for Actionable when the user is on another tab. |
| **Email** | User is offline for >1 hour. Used for Critical and Actionable. Digest emails for Informational (daily summary). |
| **Activity feed** | All notification types are logged here. Serves as the permanent record. |

### Activity Feed

- Accessible via a bell icon in the top navigation bar.
- Badge: unread count, `var(--color-accent)` background, white text, max display "99+".
- Feed panel: slides in from the right, 360px wide, full height.
- Each entry: icon + title + timestamp (relative) + optional action button.
- Mark all as read: link at the top of the feed.

### Notification Rules

- **N1:** Never use notifications for marketing, upselling, or feature announcements. Use a dedicated changelog or "What's new" section instead.
- **N2:** Every notification must link to the relevant record or page. No dead-end notifications.
- **N3:** Users must be able to configure notification preferences per-channel and per-type from Settings. Default all channels to ON for Critical and Actionable, OFF for email on Informational.
- **N4:** Toast notifications stack vertically (bottom-right). Maximum 3 visible at a time. Older toasts collapse into "and X more."
- **N5:** Critical banners are dismissible only after the user has taken the required action (e.g., updated billing) or explicitly acknowledged the issue.
- **N6:** [module] notifications must include the module name as a prefix in the toast title for disambiguation. Example: "[module]: New order received."

---

## Activity and Audit UX

### Activity Log (Per Record)

- Every record (invoice, contact, project, etc.) has an activity tab showing its history.
- Entries: chronological, newest first.
- Each entry: avatar (24px circle) + actor name + action verb + timestamp (relative, absolute on hover).
- Example: "Jane Doe created this invoice — 2 hours ago."
- System actions (automated) use a robot icon instead of an avatar.
- Expand entry: click to see field-level diffs (old value → new value).

### Audit Log (Workspace-Wide)

- Accessible to admins from Settings → Audit Log.
- Searchable by actor, action type, resource type, date range.
- Columns: Timestamp | Actor | Action | Resource | IP Address | Details.
- Exports to CSV.
- Retention: minimum 1 year. Configurable per workspace.

### Activity Rules

- **A1:** Every create, update, delete, and permission change must be logged. No silent mutations.
- **A2:** Audit log entries are immutable. They cannot be edited or deleted by any user, including admins.
- **A3:** Bulk actions log one entry per affected record, not one entry for the entire bulk operation. This ensures the per-record activity log is complete.
- **A4:** Activity log entries must load via pagination (25 per page). Never load the entire history on mount.

---

## Permissions UX

### Roles Table

| Role | Capabilities |
|---|---|
| **Owner** | Full access. Billing, danger zone (delete workspace), manage all roles. |
| **Admin** | Full access except billing and workspace deletion. Can manage Members and Viewers. |
| **Member** | Create, read, update records. Cannot delete records created by others. Cannot manage roles. |
| **Viewer** | Read-only. Can comment (if commenting is enabled). Cannot create, edit, or delete. |
| **Custom** | Per-resource permission matrix. Only available on plans that support custom roles. |

### Surfacing Permissions

- Disabled controls: if a user lacks permission for an action, the button/link is visible but disabled (opacity 0.5, cursor `not-allowed`).
- Tooltip on disabled control: "You need [Role] access to do this. Contact your admin."
- Never hide controls based on permissions unless the entire section is irrelevant to the user's role. Hiding creates confusion ("Where did that button go?").
- Permission boundary: when a user navigates to a page they cannot access, show the Permission Denied state (see States section).

### Permission Rules

- **PR1:** Permission checks happen server-side. Client-side disabling is a UX convenience, not a security measure.
- **PR2:** Role changes take effect immediately — no "save" step. Show a confirmation toast: "Jane Doe is now an Admin."
- **PR3:** The last Owner cannot be downgraded or removed. Show an error: "Transfer ownership before changing your role."
- **PR4:** Viewer role must not see any pricing, billing, or cost data unless explicitly granted. Financial data is a separate permission layer.

---

## Onboarding

### First-Run Experience

When a user signs up and enters the product for the first time:

1. **Welcome screen** — Heading: "Welcome to [product]." Subheading: brief value prop (one sentence). CTA: "Get started."
2. **Workspace setup** — Name the workspace, invite team members (skippable), select timezone and locale.
3. **First record creation** — Guided creation of the first domain object (e.g., first project, first contact, first invoice). Pre-filled with example data the user can edit.
4. **Tour highlights** — 3–5 tooltip callouts pointing to key UI areas (navigation, command palette, settings). Dismissible, non-blocking.
5. **Completion** — "You're all set" screen with links to documentation, support, and the main dashboard.

### Subsequent-Run Hints

- Feature discovery tooltips: shown once per feature, per user. Triggered by the user approaching a feature for the first time (e.g., first time viewing a table → show "Tip: Press Cmd+K to search").
- Dismissible: "Got it" link. Once dismissed, never shown again.
- Storage: track seen hints in user preferences (server-side).

### Empty Workspace

- After onboarding, if the workspace has no data, every section shows its "No Data Yet" empty state (see States section) with a CTA to create the first record.
- Sidebar navigation highlights the recommended starting point with a subtle `var(--color-accent)` dot indicator.

### Onboarding Rules

- **O1:** Onboarding must be completable in under 2 minutes. If it takes longer, cut steps.
- **O2:** Every onboarding step must be skippable except account creation itself.
- **O3:** Never ask for information you can infer (timezone from browser, locale from `Accept-Language`, company name from email domain).
- **O4:** Onboarding progress is saved — if the user closes the tab and returns, resume from where they left off.
- **O5:** Post-onboarding, show a persistent (but dismissible) checklist card on the dashboard: "Getting started: 2 of 4 complete." Items link to the relevant feature.

---

## AI Interaction Patterns

### Core Principles

1. **AI is a tool, not a persona.** Do not give the AI a name, avatar, or personality. It is a capability within the product.
2. **Explicit, never implicit.** AI actions must be visible and reversible. The user always knows when AI is acting.
3. **Confidence over mystery.** When the AI is uncertain, it says so. Never present a guess as a fact.
4. **User retains control.** AI suggests, the user decides. Auto-actions (if any) require prior opt-in.
5. **Errors are recoverable.** Every AI action has an undo path. If AI generates content, the previous state is preserved.
6. **Speed over perfection.** A fast 80%-accurate suggestion that the user can edit beats a slow 95%-accurate one. Latency kills trust.

### AI Surface Patterns

#### A1 — Inline Suggestion

- Appears as a ghost-text overlay within an input field or text editor.
- Styled: Inter 400, `var(--text-muted)`, italic.
- Accept: `Tab` key. Dismiss: continue typing or `Escape`.
- Use for: auto-complete, sentence completion, field suggestions.

#### A2 — Generated Block

- A distinct block of AI-generated content inserted into the page.
- Bordered container: left border 2px solid `var(--color-purple)`, background `rgba(155,89,182,0.05)`.
- Header: "AI Generated" badge (micro-label style, `var(--color-purple)`).
- Actions: "Accept" (primary button), "Edit" (secondary), "Discard" (text link, `var(--color-danger)`).
- Use for: generated summaries, draft emails, suggested descriptions.

#### A3 — Action Confirmation

- When AI proposes to take an action (e.g., merge duplicates, send a message), show a confirmation card.
- Card contains: description of the action, preview of the outcome, "Confirm" (primary) and "Cancel" (secondary) buttons.
- Destructive AI actions require an additional warning: "This cannot be undone" in `var(--color-danger)`.
- Use for: AI-triggered workflows, data modifications, outbound communications.

#### A4 — Conversational Panel

- Side panel (right-aligned, 400px wide) for multi-turn AI interaction.
- Chat bubbles: user messages right-aligned (`var(--color-accent-muted)` background), AI messages left-aligned (`var(--surface-2)` background).
- Input at the bottom: text input with "Send" button and `Ctrl+Enter` shortcut.
- Context indicator at the top: "Discussing: Invoice #1042" — shows what record the AI has context on.
- Use for: complex queries, analysis, multi-step tasks.

#### A5 — Background AI

- AI runs tasks in the background (e.g., classification, summarization, anomaly detection).
- No UI during processing. Results surface as Informational or AI Suggestion notifications.
- Activity log entry: "AI classified 42 transactions — Review."
- Use for: batch processing, periodic analysis, monitoring.

### Confidence and Citation

Three-state confidence indicator for AI-generated content:

| State | Indicator | Meaning |
|---|---|---|
| **High confidence** | Solid `var(--color-success)` dot | AI found strong evidence in the data. |
| **Medium confidence** | Solid `var(--color-secondary)` dot | AI inferred this with partial data. User should verify. |
| **Low confidence** | Outline `var(--color-danger)` dot | AI is guessing. Treat as a starting point, not an answer. |

- When AI references specific records, link to them. Example: "Based on Invoice #1042 and Invoice #1089."
- When AI uses external knowledge (not from the user's data), disclose: "Based on general knowledge, not your data."

### Streaming and Latency

- AI responses stream token-by-token. Show a blinking cursor (`var(--color-accent)`) at the insertion point.
- If the first token takes >1 second, show "Thinking..." in `var(--text-muted)` below the input.
- If the response takes >10 seconds, show a progress indicator (indeterminate bar, `var(--color-accent)`).
- Streaming must be interruptible: the user can press "Stop" to halt generation and keep what has been produced so far.

### Recovery and Override

- Every AI-generated output has an "Undo" action available for 30 seconds after acceptance.
- "Regenerate" button: re-runs the AI with the same input. Available on all generated blocks and conversational responses.
- Manual override: the user can always edit AI-generated content directly. Edits are never overwritten by subsequent AI runs.

### Multimodal

- If the product supports image or file input to AI, show a drag-and-drop zone or attachment button in the conversational panel.
- Accepted formats: images (PNG, JPG, WebP), PDFs, CSV. Max file size: 10MB per file.
- Preview attached files as thumbnails (80px) before sending.

### AI Enforcement

- AI features must degrade gracefully. If the AI service is unavailable, hide AI-specific UI elements and show a toast: "AI features temporarily unavailable."
- AI-generated content must be distinguishable from human-authored content at all times. The "AI Generated" badge is mandatory, even after acceptance (it can be made subtle — smaller, muted — but never removed).
- Never auto-send AI-generated outbound communications (emails, messages) without explicit user confirmation.

---

## Multilingual and RTL

### Languages Table

| Code | Language | Script | Direction | Status |
|---|---|---|---|---|
| `tr` | Turkish | Latin | LTR | Primary |
| `en` | English | Latin | LTR | Primary |
| `ar` | Arabic | Arabic | RTL | Secondary |
| `ru` | Russian | Cyrillic | LTR | Secondary |
| `fa` | Persian | Arabic | RTL | Secondary |

### RTL Rules

- When the user selects an RTL language (`ar`, `fa`), the entire layout mirrors: sidebar moves to the right, text aligns right, icons flip horizontally (except symmetrical icons and brand marks).
- Use `dir="rtl"` on the `<html>` element. Use logical CSS properties (`margin-inline-start` not `margin-left`, `padding-inline-end` not `padding-right`).
- Bidirectional content (e.g., an Arabic sentence containing an English product name) must use `<bdi>` tags to isolate the embedded text direction.
- Numbers, dates, and currency symbols follow the locale format — Arabic numerals in `ar`, Western numerals in `fa` (standard Iranian practice).
- Charts: mirror the X-axis direction in RTL (time flows right-to-left). Y-axis remains on the inline-start side.

### Translation Workflow

1. English is the source language for all strings.
2. Strings are extracted to JSON locale files (`/locales/{code}.json`).
3. AI-translate as first draft, then validate via `scripts/validate_i18n.py`:
   - Level 1 (free, instant): structural checks — missing keys, placeholder mismatches, empty values, completeness drift.
   - Level 2 (Kilo CLI): back-translation — translate back to English, compare semantic overlap. Catches meaning loss.
   - Level 3 (Kilo CLI): native-speaker critique — tone, register, grammar, technical terms. Auto-applies fixes.
   - Run: `python scripts/validate_i18n.py --validate <lang>` (all 3 levels).
4. **Agent workflow:** AI-translate → run `validate_i18n.py --validate <lang>` → apply fixes from output → re-run validation until Level 1 passes clean. Translation is not done until the script passes.
5. New features ship in English first. Translations must be validated within one release cycle.
6. Interpolation syntax: `{variable}` placeholders. Never concatenate translated fragments — word order varies by language.
7. Full i18n kit (validate script, `_context.json` for product/tone/register config, JS loader, HTML snippets): `templates/scaffold/i18n-kit/`. Applies to all GUI scaffolds (SaaS, mobile, chrome, wordpress, docusaurus).

### Localization Quality Bar

- All user-facing strings must be externalized — no hardcoded text in components.
- Pluralization: use ICU MessageFormat syntax (e.g., `{count, plural, one {# item} other {# items}}`). Turkish has no grammatical plural for counted nouns — handle this explicitly.
- Gender-neutral language in English. In Turkish, gender-neutrality is natural; in Arabic and Russian, follow standard grammatical conventions.
- Locale-specific formatting: see Date, Time, Currency, and Number Formatting section.

### Multilingual Rules

- **ML1:** The `lang` attribute on `<html>` must match the user's selected language. This affects screen readers and browser behavior.
- **ML2:** Font stack must support all target scripts. Inter covers Latin and Cyrillic. Add an Arabic-script font (e.g., Noto Sans Arabic) for `ar` and `fa` locales.
- **ML3:** UI layout must not break with 40% text expansion (German, Russian) or 30% contraction (Chinese, Japanese). Test with pseudo-localization.
- **ML4:** RTL layout must be tested on every page. Use browser DevTools `dir="rtl"` toggle during development.
- **ML5:** Translated strings must never be split across multiple HTML elements. One element = one translatable string.
- **ML6:** Date and number formatting must use `Intl.DateTimeFormat` and `Intl.NumberFormat` — never manual string construction.
- **ML7:** Language selector must show language names in their native script: "Türkçe", "English", "العربية", "Русский", "فارسی".
- **ML8:** Content entered by users (e.g., invoice descriptions, contact names) is stored in the original language. The UI chrome translates; user data does not.

---

## Date, Time, Currency, and Number Formatting

### Dates

- Display format follows the user's locale setting:
  - `tr`: 23.05.2026
  - `en`: May 23, 2026
  - `ar`: ٢٣/٠٥/٢٠٢٦
- Relative dates for recent items: "2 hours ago", "Yesterday", "3 days ago". Switch to absolute after 7 days.
- Hover tooltip on relative dates always shows the full absolute date+time.
- Use `Intl.DateTimeFormat` — never construct date strings manually.

### Times

- 24-hour format by default for `tr`, `ar`, `fa`, `ru`. 12-hour format (AM/PM) for `en`.
- Override available in user settings.
- Always show timezone abbreviation when displaying times that could be ambiguous (e.g., "14:30 UTC+3").

### Numbers

- Decimal separator: `.` for `en`, `,` for `tr`, `ru`, `fa`. Arabic uses `٫`.
- Thousands separator: `,` for `en`, `.` for `tr`, ` ` (thin space) for `ru`, none in standard `ar`.
- Use `Intl.NumberFormat` — never manual formatting.

### Currency

- Default currency follows workspace settings, not user locale.
- Symbol placement follows locale convention: `$100` (en), `100 ₺` (tr), `١٠٠ ر.س` (ar).
- Always show 2 decimal places for monetary values. Show 0 decimal places for whole-number currencies (JPY, KRW).
- Color coding: positive amounts in `var(--text-primary)`, negative in `var(--color-danger)`. Never use green for positive currency — it implies "good" which is context-dependent.

### Phone Numbers

- Store in E.164 format (`+905551234567`).
- Display formatted per locale: `+90 555 123 45 67` (tr), `+90 555-123-4567` (en).
- Input: accept any format, normalize on save. Show the formatted preview below the input.

### Address

- Address field order follows locale convention (Turkey: street → district → city → postal code; US: street → city → state → zip).
- Country selector at the top of the address form — it determines the field layout.

### Formatting Rules

- **FMT1:** All date/time/number formatting must use `Intl` APIs. No hardcoded format strings, no manual string construction.
- **FMT2:** Dates in API responses must be ISO 8601 (`2026-05-23T14:30:00Z`). Formatting is a presentation concern — never format in the API layer.
- **FMT3:** Currency formatting must respect the workspace's currency setting, not the user's locale. A Turkish user viewing a USD workspace sees `$1,234.56`, not `1.234,56 $`.
- **FMT4:** Relative dates ("2 hours ago") must update live in the UI. Recalculate every 60 seconds for items <24 hours old.
- **FMT5:** Tables with numeric columns must right-align and use monospace (`JetBrains Mono`) for visual alignment.
- **FMT6:** Phone number inputs must validate format and show the country flag emoji next to the country code.
- **FMT7:** When displaying a range (date range, price range), use an en-dash `–` with spaces: "May 1 – May 31", "$100 – $500". Never a hyphen.
- **FMT8:** Percentages: always show 1 decimal place (`42.7%`). Use `Intl.NumberFormat` with `style: 'percent'`.

---

## Print and Export

### Print Stylesheet

- Every data-heavy page must have a print stylesheet (`@media print`).
- Hide: navigation, sidebar, toasts, modals, tooltips, action buttons.
- Show: content area at full width, page title, data tables, charts (rendered as static images).
- Font: use system fonts for print (no web font loading). Body: 11pt, headings: 14pt.
- Colors: force light mode colors for print regardless of the user's theme. `var(--text-primary)` → `#111111`, backgrounds → `#FFFFFF`.
- Page breaks: avoid breaking inside table rows, cards, or chart containers (`break-inside: avoid`).

### PDF Export

- Generated server-side using a headless browser (Puppeteer/Playwright) rendering the print stylesheet.
- Header: product name + report title + date. Footer: page number + "Generated by [product]".
- Page size: A4 by default. Letter for `en-US` locale.
- Filename: `{product}-{report}-{YYYY-MM-DD}.pdf`.

### Export Rules

- **EX1:** Every table and report must support at least CSV export. PDF and XLSX are optional based on the product.
- **EX2:** Exported data must match what the user sees — same filters, same sort order, same visible columns. No surprise extra columns.
- **EX3:** Export filenames follow the pattern `{product}-{resource}-{YYYY-MM-DD}.{ext}`. No spaces, no special characters.
- **EX4:** Large exports (>5 seconds) must run in the background with a toast notification and download link on completion.
- **EX5:** Print preview (`Cmd+P`) must produce a clean, professional document. Test every printable page with the print stylesheet.

---

## Accessibility (Enriched)

### Color Contrast

Refer to the Color System section (part 1) for the full palette. All text-background combinations must meet WCAG 2.1 AA contrast ratios:

| Combination | Ratio (dark) | Meets AA? |
|---|---|---|
| `--text-primary` (#FFF) on `--surface-0` (#0A0A0A) | 19.83:1 | AAA |
| `--text-body` (#E0E0E0) on `--surface-0` (#0A0A0A) | 16.04:1 | AAA |
| `--text-muted` (#888) on `--surface-0` (#0A0A0A) | 5.58:1 | AA |
| `--color-accent-text` (#8A8AFF) on `--surface-0` (#0A0A0A) | 6.75:1 | AA |
| `--color-accent-text` (#8A8AFF) on `--surface-1` (#141414) | 6.27:1 | AA |

Light mode pairs must be re-validated per project. See § Color Contrast (Verified Pairs) for the full table including forbidden pairs.

### Keyboard Navigation

- All interactive elements must be reachable via `Tab` key in a logical order.
- Focus ring: 2px solid `var(--color-accent)`, offset 2px. Never remove the focus outline.
- Skip-to-content link: first focusable element on every page, visible only on focus.
- Modal trap: when a modal is open, focus is trapped within it. `Tab` cycles through modal controls. `Escape` closes the modal and returns focus to the trigger element.
- Custom components (dropdowns, date pickers, command palette) must implement ARIA roles and keyboard patterns per WAI-ARIA Authoring Practices.

### Screen Reader

- All images must have `alt` text. Decorative images: `alt=""` and `aria-hidden="true"`.
- Icon-only buttons must have `aria-label`. Example: `<button aria-label="Close"><XIcon /></button>`.
- Live regions: use `aria-live="polite"` for toast notifications and search results. `aria-live="assertive"` for critical errors only.
- Page title (`<title>`) must update on navigation to reflect the current view.
- Form errors must be associated with inputs via `aria-describedby`.

### Motion and Cognition

- Respect `prefers-reduced-motion` media query. When active:
  - Disable all CSS transitions and animations.
  - Replace skeleton shimmer with a static placeholder.
  - Disable chart entry animations.
- No content should depend solely on animation to convey meaning.
- No flashing content (>3 flashes per second) — WCAG 2.3.1.

### Forms (Accessibility)

- Every input must be associated with a `<label>` via `for`/`id` or wrapping.
- Error messages linked to inputs via `aria-describedby`.
- Required fields indicated via `aria-required="true"` in addition to the visual asterisk.
- Fieldsets with `<legend>` for grouped controls (radio buttons, checkboxes).

### Accessibility Rules

- **ACC1:** Every page must be navigable by keyboard alone. No mouse-only interactions.
- **ACC2:** Color must never be the only indicator of state. Always pair color with an icon, label, or pattern. Example: error state = red border + error icon + text message.
- **ACC3:** Touch targets must be at least 44x44px. This applies to all buttons, links, and interactive elements on touch devices.
- **ACC4:** All dynamic content changes (toasts, search results, live data) must be announced to screen readers via ARIA live regions.
- **ACC5:** The product must be fully functional at 200% browser zoom without horizontal scrolling.
- **ACC6:** Video and audio content must include captions (video) and transcripts (audio). Auto-generated captions must be reviewed for accuracy.
- **ACC7:** Heading hierarchy must be sequential: H1 → H2 → H3. Never skip levels. Each page has exactly one H1.
- **ACC8:** Automated accessibility tests (axe-core) must run in CI. Zero violations at the "critical" and "serious" levels.

---

## Spacing System

| Token | Value | Usage |
|---|---|---|
| `--space-xs` | 4px | Icon gaps, tight inline elements |
| `--space-sm` | 8px | Card gaps, tag margins, compact padding |
| `--space-md` | 16px | Default card padding, section spacing |
| `--space-lg` | 24px | Section margins, modal padding |
| `--space-xl` | 32px | Page-level section gaps |
| `--space-2xl` | 48px | Hero sections, major separators |

---

## Responsive Layout

**RWD is mandatory for every web scaffold — no exceptions.** Every page, component, and layout must render correctly from 375px (iPhone SE — smallest current phone) to 2560px (ultrawide). This is not optional; Traycer tickets assume it; coding agents must implement it.

### Breakpoint Tokens

| Token | Width | Target |
|---|---|---|
| `--bp-sm` | 640px | Large phones (landscape), small tablets |
| `--bp-md` | 768px | Tablets (portrait) |
| `--bp-lg` | 1024px | Tablets (landscape), small laptops |
| `--bp-xl` | 1280px | Laptops, desktops |
| `--bp-2xl` | 1536px | Large desktops, ultrawide |

These map directly to Tailwind's default breakpoints (`sm:`, `md:`, `lg:`, `xl:`, `2xl:`). Use them verbatim — never invent custom breakpoints.

### Approach: Mobile-First

All CSS is authored **mobile-first** — base styles target the smallest viewport, `min-width` media queries layer up complexity:

```css
/* Base: mobile (< 640px) */
.grid { grid-template-columns: 1fr; }

/* sm: 640px+ */
@media (min-width: 640px) { .grid { grid-template-columns: repeat(2, 1fr); } }

/* lg: 1024px+ */
@media (min-width: 1024px) { .grid { grid-template-columns: repeat(3, 1fr); } }
```

In Tailwind: write base classes first, then add `sm:`, `md:`, `lg:` prefixes. Never write `max-width` queries (desktop-first).

### Layout Grid

| Viewport | Columns | Gutter | Container max-width | Side padding |
|---|---|---|---|---|
| < 640px | 4 | 16px | 100% | 16px |
| 640px – 1023px | 8 | 16px | 100% | 24px |
| 1024px – 1279px | 12 | 24px | 1024px | 32px |
| 1280px+ | 12 | 24px | 1280px | auto (centered) |

### Responsive Behavior by Component

| Component | < 640px | 640px – 1023px | 1024px+ |
|---|---|---|---|
| **Sidebar nav** | Hidden; hamburger menu or bottom tab bar (< 768px) | Collapsed icon rail (56px) (768px – 1023px) | Full sidebar (240px) |
| **Data tables** | Card list (one card per row) OR horizontal scroll with sticky first column | Horizontal scroll with sticky first column | Full table |
| **Dashboard grid** | 1 column, stacked cards | 2 columns | 3-4 columns |
| **Forms** | Single column, full width | Single column, max-width 560px centered | Two-column for wide viewports (>1024px) with grouped fields |
| **Modal/dialog** | Full-screen sheet (bottom sheet pattern) | Centered modal, max-width 480px | Centered modal, max-width 560px |
| **Hero section** | Stack vertically, image below text | Stack vertically | Side-by-side (text left, visual right) |
| **Top navigation** | Logo + hamburger | Logo + condensed nav | Logo + full nav + actions |

### Sidebar Responsive Pattern (SaaS)

```
Mobile (< 640px):
┌──────────────────────┐
│ [hamburger] Title    │  ← top bar
├──────────────────────┤
│                      │
│  [Full-width content]│
│                      │
├──────────────────────┤
│ [tab] [tab] [tab]   │  ← optional bottom tabs
└──────────────────────┘

Tablet (768px – 1023px):
┌──┬───────────────────┐
│  │                   │
│56│  Content area     │  ← icon rail (collapsed sidebar)
│px│                   │
└──┴───────────────────┘

Desktop (1024px+):
┌─────┬────────────────┐
│     │                │
│240px│  Content area  │  ← full sidebar
│     │                │
└─────┴────────────────┘
```

### Data Tables on Small Viewports

Tables with 4+ columns are unreadable on mobile. Two approved patterns:

**Pattern A — Card transformation:**
Each table row becomes a card. Column headers become inline labels. Use when: rows represent distinct entities (contacts, invoices, orders).

```
Desktop:                          Mobile:
┌────┬──────┬────────┬───────┐   ┌─────────────────────┐
│Name│Email │Status  │Actions│   │ John Doe             │
├────┼──────┼────────┼───────┤   │ john@acme.com        │
│John│j@a.co│Active  │  ⋮   │   │ Status: Active    ⋮  │
└────┴──────┴────────┴───────┘   └─────────────────────┘
```

**Pattern B — Horizontal scroll with sticky column:**
First column (identifier) sticks; remaining columns scroll. Use when: comparing values across columns matters (pricing tables, feature matrices, analytics).

### Per-Scaffold Responsive Strategy

| Scaffold | Responsive strategy |
|---|---|
| **saas-skeleton** | Full RWD. Sidebar collapses. Tables transform. Dashboard stacks. Touch targets enforced on mobile viewports. |
| **static-site** | Full RWD, mobile-first. Every marketing page must pass Google Mobile-Friendly Test. Images use `srcset` + `sizes`. |
| **docusaurus** | Default theme is responsive. Custom components MUST be responsive — test at 375px before merge. |
| **chrome-extension** | Fixed 400px width. No breakpoints. Not applicable. |
| **desktop-app** | Minimum window 800×600. Internal layout uses the grid system from 1024px+ column. No mobile breakpoints. |

### Image Responsiveness

- All content images use `<Image>` with `srcset` and `sizes` attributes (or Next.js `<Image>` component which handles this automatically).
- Maximum rendered width: never exceed `container max-width` at any breakpoint.
- Art direction: use `<picture>` with `<source media="...">` when the crop must change between mobile and desktop (hero images, feature illustrations).
- Lazy-load all images below the fold (`loading="lazy"`). Eager-load the LCP image.

### Responsive Testing

For the full testing process (Playwright automation, screenshot workflow, diagnosis table, fix patterns by framework, interactive state captures, common mistakes), see `docs/reference/mobile-responsive-testing-guide.md`.

**Quick viewport checklist** — every UI PR must pass at these widths before merge:

- [ ] 375px (iPhone SE — design floor)
- [ ] 768px (iPad portrait)
- [ ] 1024px (iPad landscape / small laptop)
- [ ] 1440px (standard desktop)
- [ ] 1920px+ (verify no stretched/empty layouts on ultrawide)

### Responsive Rules (Enforced)

- **RWD1:** Every web page must be functional and readable at 375px. No horizontal scrollbar on the page body at any viewport. (Exception: data tables using Pattern B.)
- **RWD2:** Touch targets must be >= 44px on viewports < 1024px, even in web browsers. Mobile users access web apps on phone browsers.
- **RWD3:** Text must remain readable without horizontal scrolling or zoom at any viewport. No fixed-width containers that overflow.
- **RWD4:** Navigation must be accessible at every breakpoint. Hidden nav requires a visible toggle (hamburger or bottom tabs).
- **RWD5:** Images and media must never overflow their container. Use `max-width: 100%; height: auto;` as baseline.
- **RWD6:** No `display: none` to hide critical content on mobile. Content that exists at desktop must be accessible on mobile — reorganize, don't remove.
- **RWD7:** Font sizes must be readable on mobile without zoom. Minimum 14px body text on all viewports (matches the Body type scale).
- **RWD8:** Modals become full-screen sheets on viewports < 640px. Never show a floating modal on a phone — it's unusable.
- **RWD9:** Sidebar navigation MUST collapse on viewports < 1024px. A persistent 240px sidebar on tablet/mobile is banned.
- **RWD10:** Test every page at 375px, 768px, 1440px before merge. Untested responsive = broken responsive.

---

## Interaction Tokens

| Property | Value |
|---|---|
| Transition duration | `0.15s` |
| Transition easing | `ease` |
| Hover lift | `translateY(-1px)` |
| Press feedback (mobile) | `translateY(1px)` + `scale(0.98)` |
| Focus ring | `2px solid var(--color-accent)`, offset 2px |

---

## Scaffold Adaptation Matrix

### saas-skeleton (Next.js + shadcn/ui)

- **Full adoption.** Dark theme default.
- All three fonts loaded. Space Grotesk headings, Inter body/UI, JetBrains Mono data/code.
- shadcn/ui components themed with Ocoron tokens via CSS variables in `globals.css`.
- Side nav uses surface hierarchy (`--surface-0` → `--surface-1`).
- Tables, forms, dashboards use card pattern.
- Both dark and light mode mandatory. OS `prefers-color-scheme` detected on load; manual toggle in Settings; preference persists in `localStorage`.
- Tailwind config extends with all Ocoron tokens.

### static-site (Landing pages, marketing)

- Space Grotesk + Inter only. Drop JetBrains Mono (no code/data on marketing pages).
- Same dark background, accent system.
- Hero sections, feature cards follow the card pattern.
- **Light variant required** for public-facing marketing pages — use light surface tokens.
- Accent FILL stays `#5B5BF7` in both modes; accent TEXT is mode-aware (`--color-accent-text`:
  `#8A8AFF` dark / `#4A4AE0` light) — provably necessary: AA body text needs relative luminance
  ≥ 0.18866 on `#0A0A0A` but ≤ 0.18333 on white, a disjoint range no single hex satisfies
  (`#5B5BF7` sits at 0.16422).

### chrome-extension (Manifest V3)

- Same tokens, **tighter spacing**: `--space-md: 12px`, `--space-sm: 6px`.
- 400px width constraint → single-column card layout.
- Tab bar maps to popup navigation.
- Pill pattern for tags/statuses.
- Font size floor: 11px.
- All three fonts loaded but JetBrains Mono only for data displays.

### mobile-app (React Native + react-native-unistyles)

- Same color system mapped to `react-native-unistyles` theme tokens.
- Both dark and light mode mandatory. Detect via `Appearance.getColorScheme()`, listen for changes, manual override in Settings, persist in MMKV.
- Space Grotesk loaded as custom font.
- Inter loaded as custom font (or system sans-serif fallback where needed).
- Cards → touchable list items with `translateY(1px)` + `scale(0.98)` press feedback.
- Tab bar → bottom navigation.
- Touch targets: 44px minimum height.
- Font size floor: 13px.

### desktop-app (Electron / Tauri)

- Same as saas-skeleton with title bar integration.
- System tray uses `--color-accent` for notification badges.
- Both dark and light mode mandatory. Respect OS preference, manual toggle in title bar, persist per-device.
- Minimum window size: 800×600.

### wordpress (Headless WP + Next.js frontend)

- WordPress admin: untouched (it's WordPress).
- **Frontend theme**: full Ocoron adoption via Next.js.
- Custom Gutenberg blocks styled with card/tag/pill patterns.
- Headless WP + Next.js frontend gets the same treatment as saas-skeleton.

### docusaurus (Documentation sites)

- Custom theme with dark tokens as default.
- CSS variable overrides in `custom.css` mapped to Ocoron tokens.
- Code blocks: JetBrains Mono (already matches).
- Sidebar navigation uses surface hierarchy.
- Search bar, breadcrumbs, TOC styled with Ocoron text hierarchy.

---

## Tailwind Theme Extension (Reference)

```js
// tailwind.config.ts — extend section
{
  colors: {
    accent: { DEFAULT: '#5B5BF7', hover: '#5151E8', muted: 'rgba(91,91,247,0.12)', text: 'var(--color-accent-text)' },
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
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    '2xl': '48px',
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

## CSS Custom Properties (Reference)

```css
/* globals.css or :root */
:root {
  --color-accent: #5B5BF7;
  --color-accent-hover: #5151E8;
  --color-accent-text: #8A8AFF; /* dark mode; light mode overrides to #4A4AE0 */
  --color-accent-muted: rgba(91, 91, 247, 0.12);
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

/* Light mode override */
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

## Rules for AI Agents (Kilo / Windsurf / Traycer)

### Visual Rules

1. **Never invent colors.** Use only the tokens above. If a new semantic color is needed, propose an addition to this doc first.
2. **Never use inline styles** in production code. Use Tailwind classes mapped to these tokens.
3. **Font assignment is strict.** Headings = Space Grotesk. Body = Inter. Code/data = JetBrains Mono. No exceptions.
4. **Both dark and light mode are mandatory.** Dark is the default. Detect OS `prefers-color-scheme` on first load, provide a manual toggle in Settings, persist preference per-device. No scaffold ships dark-only or light-only.
5. **No shadows in dark mode.** Use 1px borders for elevation. Shadows are allowed in light mode only, and must be subtle (`0 1px 3px rgba(0,0,0,0.08)`).
6. **Component patterns are canonical.** Cards, tags, pills, buttons, tabs — use the specs above. Don't reinvent.
7. **Spacing uses the token scale.** No arbitrary pixel values. Use `xs/sm/md/lg/xl/2xl`.
8. **Transitions are 0.15s ease.** No bouncy animations, no spring physics, no delays > 0.3s.
9. **Accent color for interactivity only.** Don't use `--color-accent` for decorative elements, backgrounds, or large surfaces.
10. **Logo is always an asset.** Never render the Ocoron wordmark in a text font.

### Responsive Rules

11. **Every web component must be responsive.** Author mobile-first, layer up with `sm:`, `md:`, `lg:` breakpoints. No fixed-width layouts. No desktop-only components. No exceptions.
12. **Test at 375px before delivering.** If a component overflows or becomes unusable at 375px viewport width, it is not done. This is a gate, not a guideline.
13. **Sidebar collapses below 1024px.** Icon rail at 768-1023px (`md:`), hidden (hamburger/bottom tabs) below 768px. A persistent full sidebar on mobile/tablet is banned.
14. **Tables transform on mobile.** Use card transformation (Pattern A) or horizontal scroll with sticky first column (Pattern B). Unmodified desktop tables on phone viewports are banned.
15. **Modals become full-screen sheets below 640px.** Floating modals on phone viewports are banned.

### Verbal Rules

16. **Never use forbidden language.** Check the Forbidden Language table before writing any user-facing copy. No exceptions.
17. **Brand name is "Ocoron."** Capital O, lowercase rest. No all-caps in text, no all-lowercase in text. Lowercase only in code/URLs.
18. **Lead with outcomes in all UI copy.** Button labels, tooltips, descriptions — state what happens, not how it works.
19. **Error messages must be actionable.** State what failed, why, and what the user should do next. Never "Something went wrong."
20. **No rhetorical questions** in any generated copy — headlines, descriptions, tooltips, onboarding flows. State the answer.
21. **Describe AI specifically.** When referencing AI capabilities, name the action: "AI reviews," "AI generates," "AI monitors." Never use "AI-powered" as a standalone adjective.
22. **Sub-brand naming requires approval.** Never generate a new product name or sub-brand. Use "Ocoron" until the human operator assigns a name.
