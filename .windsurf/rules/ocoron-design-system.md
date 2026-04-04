# Ocoron Design System v2.0

> Single source of truth for all Ocoron products, scaffolds, and surfaces.
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
| "Disruptive" / "Game-changer" | Startup cliché | Describe what actually changed |
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

Format: **Ocoron [Name]** — product name is 1–2 words, lowercase-friendly, technical-sounding.

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
| `--color-accent` | `#00D4AA` | Primary accent — CTAs, active states, links, primary buttons, progress bars |
| `--color-accent-hover` | `#00E8BB` | Accent hover state |
| `--color-accent-muted` | `rgba(0,212,170,0.12)` | Accent backgrounds (tags, badges, subtle highlights) |
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

### Surface Hierarchy (Light Mode — Optional)

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
- Micro-labels: Inter 500, uppercase, letter-spacing 1.5px, 9–10px.
- Line-height: 1.5 for body, 1.2 for headings, 1.4 for code.

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
Background: color-specific muted variant (e.g., rgba(0,212,170,0.12) for accent)
Text: full-saturation color (e.g., #00D4AA)
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
  Text: #0A0A0A (dark text on teal)
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
Toggle: minimal +/− icon, no accordion animation bloat
Header: Space Grotesk 600, 14px
Border: 1px solid var(--border) on container
Transition: max-height 0.15s ease
```

### Data Hierarchy Pattern

```
Headline: var(--text-primary), Space Grotesk 600
Body: var(--text-body), Inter 400
Meta: var(--text-muted), Inter 400, 12px
Numeric: JetBrains Mono 300–400
```

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
- Light mode toggle optional — dark is default.
- Tailwind config extends with all Ocoron tokens.

### static-site (Landing pages, marketing)

- Space Grotesk + Inter only. Drop JetBrains Mono (no code/data on marketing pages).
- Same dark background, accent system.
- Hero sections, feature cards follow the card pattern.
- **Light variant required** for public-facing marketing pages — use light surface tokens.
- Accent color stays `#00D4AA` in both modes.

### chrome-extension (Manifest V3)

- Same tokens, **tighter spacing**: `--space-md: 12px`, `--space-sm: 6px`.
- 400px width constraint → single-column card layout.
- Tab bar maps to popup navigation.
- Pill pattern for tags/statuses.
- Font size floor: 11px.
- All three fonts loaded but JetBrains Mono only for data displays.

### mobile-app (React Native + NativeWind)

- Same color system mapped to `react-native-unistyles` theme tokens.
- Space Grotesk loaded as custom font.
- Inter loaded as custom font (or system sans-serif fallback where needed).
- Cards → touchable list items with `translateY(1px)` + `scale(0.98)` press feedback.
- Tab bar → bottom navigation.
- Touch targets: 44px minimum height.
- Font size floor: 13px.

### desktop-app (Electron / Tauri)

- Same as saas-skeleton with title bar integration.
- System tray uses `--color-accent` for notification badges.
- Respect OS dark/light mode preference — auto-switch surface tokens.
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
    accent: { DEFAULT: '#00D4AA', hover: '#00E8BB', muted: 'rgba(0,212,170,0.12)' },
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
}
```

---

## CSS Custom Properties (Reference)

```css
/* globals.css or :root */
:root {
  --color-accent: #00D4AA;
  --color-accent-hover: #00E8BB;
  --color-accent-muted: rgba(0, 212, 170, 0.12);
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
4. **Dark mode is default.** Light mode is opt-in and uses the light surface token set.
5. **No shadows in dark mode.** Use 1px borders for elevation. Shadows are allowed in light mode only, and must be subtle (`0 1px 3px rgba(0,0,0,0.08)`).
6. **Component patterns are canonical.** Cards, tags, pills, buttons, tabs — use the specs above. Don't reinvent.
7. **Spacing uses the token scale.** No arbitrary pixel values. Use `xs/sm/md/lg/xl/2xl`.
8. **Transitions are 0.15s ease.** No bouncy animations, no spring physics, no delays > 0.3s.
9. **Accent color for interactivity only.** Don't use `--color-accent` for decorative elements, backgrounds, or large surfaces.
10. **Logo is always an asset.** Never render the Ocoron wordmark in a text font.

### Verbal Rules

11. **Never use forbidden language.** Check the Forbidden Language table before writing any user-facing copy. No exceptions.
12. **Brand name is "Ocoron."** Capital O, lowercase rest. No all-caps in text, no all-lowercase in text. Lowercase only in code/URLs.
13. **Lead with outcomes in all UI copy.** Button labels, tooltips, descriptions — state what happens, not how it works.
14. **Error messages must be actionable.** State what failed, why, and what the user should do next. Never "Something went wrong."
15. **No rhetorical questions** in any generated copy — headlines, descriptions, tooltips, onboarding flows. State the answer.
16. **Describe AI specifically.** When referencing AI capabilities, name the action: "AI reviews," "AI generates," "AI monitors." Never use "AI-powered" as a standalone adjective.
17. **Sub-brand naming requires approval.** Never generate a new product name or sub-brand. Use "Ocoron" until the human operator assigns a name.
