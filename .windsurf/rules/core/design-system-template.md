---
activation: glob
globs: ["**/docs/design-system.md", "**/*.tsx", "**/*.jsx", "**/tailwind.config.*", "**/globals.css", "**/global.css", "**/custom.css"]
description: The brand-neutral design-system TEMPLATE every Fabrik GUI inherits — the token slots a brand must fill (both modes), the computed-contrast contract, and the structure (components, states, tables, forms, motion, density, accessibility, responsive layout). A project's docs/design-system.md fills the slots; brand-identiy-creator emits that file in this shape; ocoron-design-system.md is one brand that fills it.
trigger: glob
currency_pass: 2026-09-24
---
<!-- CONSUMER: coding agents building any GUI surface; /fabrik-ui-design (freezes docs/design-system.md against § The design-system.md contract); brand-identiy-creator (emits For-Your-Developer/design-system.md in that shape)
     GOAL: one structure for every Fabrik GUI, whatever its brand — the brand supplies VALUES for named slots; this file supplies everything else
     AGENT USAGE: build against the slot NAMES (var(--color-danger), --font-heading) — never a brand's raw hex or font name. The values come from the project's docs/design-system.md. -->

# Design System Template

> **What this is.** The structure every Fabrik GUI inherits — components, states, tables, forms,
> motion, density, accessibility, responsive layout — written against named token SLOTS instead of
> brand values. A brand is a set of values for those slots plus its voice and logo. Where a project's
> brand comes from is the resolution ladder in `saas/60-saas-ui.md` (operator ruling 2026-08-29,
> D-051): its own `docs/design-system.md` from a brand-identiy-creator identity, or an explicitly
> declared house identity (`ocoron-design-system.md` for web, `tojlo-design-system.md` for Tojlo).
> Either way the project's `docs/design-system.md` has the shape § The design-system.md contract
> defines, and everything below applies unchanged.
>
> **Slot defaults.** Spacing, density, motion and interaction values are given here as DEFAULTS; a
> brand may override one only by restating it in its `docs/design-system.md` § Structural overrides.
> Pixel sizes and radii written into the component specs below are structural defaults too — a
> brand's type scale or radius roles replace them only through that same section. Breakpoints are
> fixed (§ Responsive Layout). The icon library defaults to Lucide (§ Iconography). Colour, typography,
> radius, logo and voice have NO default — a missing one is a missing brand, and the ladder's step 2
> applies.

---

## The design-system.md contract

A project's `docs/design-system.md` — frozen by `/fabrik-ui-design`, and emitted ready-made by
brand-identiy-creator as `For-Your-Developer/design-system.md` — contains exactly these sections, in
this order. Taking on an identity is one copy of that file; `/fabrik-ui-design` then checks it
against this list.

| # | Section | Contents | Required |
|---|---|---|---|
| 1 | Header | Identity source, one line: `Identity: brand-identiy-creator kit <id>`, or `House identity: <name> — chosen, not defaulted` where the name is ocoron or tojlo; the date it was frozen (`YYYY-MM-DD`) | yes |
| 2 | § Colour tokens | A table `Slot · Dark · Light · Role` valuing every slot in § Token slots → Colour for BOTH modes — `--color-ai-*` only when the product has AI surfaces; `--viz-*` belong to row 6 | yes |
| 3 | § Contrast table | A table `Foreground · Background · Dark · Light · Needs`, one row per pair § Contrast contract requires. Background names a surface set (`surface-0…2`, reported as its lowest ratio), one surface, a tint (`its -muted tint over surface-1`) or a fill slot; each ratio computed; `Needs` the contract's threshold for that pair. The brand's forbidden pairs are listed below the table | yes |
| 4 | § Typography | The three font roles (family, weights, source, licence) and the type-scale values — size, weight, line-height, font role and letter-spacing per level | yes |
| 5 | § Radius and icon style | The radius roles; the icon library (Lucide unless another is named), its stroke width and style | yes |
| 6 | § Data-visualisation palette | `--viz-1` … `--viz-6`, both modes | yes when the product has charts |
| 7 | § Logo | Variants (on light, on dark), clear space, minimum size, the repo-relative asset paths | yes |
| 8 | § Voice | Positioning line, voice traits, forbidden words, and the register-by-surface table — word budgets per surface (button, page title, empty state, tooltip, toast, error, dialog, onboarding step, email) | yes |
| 9 | § Theme and elevation | The mode a first visit shows when the OS states no preference; the light-mode shadow (dark mode elevates with borders) | yes |
| 10 | § Sound | The success, error and notification cues | only when the product enables sound |
| 11 | § Structural overrides | Any spacing, density, motion or interaction default, or a component's pixel size or radius, the brand changes — restated with its new value (breakpoints are fixed) | only if any |

The § names in this table are headings of the PROJECT's `docs/design-system.md`, not of this template.

A **house identity** is referenced, not copied: a declared project's `docs/design-system.md` is the header line plus any § Structural overrides, and the house pack itself supplies sections 2–10 under its own headings (`ocoron-design-system.md` names which of its sections answers which row). Nothing else belongs in it: the structure is inherited from this file by reference, never copied
(a copied structure drifts from the canonical one on the next change here). A machine-readable copy
of the tokens may ride beside it in the W3C Design Tokens Community Group format (stable since
October 2025: `$value` / `$type` / `$description` per token, media type `application/design-tokens+json`,
extension `.tokens` or `.tokens.json`) — the markdown file stays the contract a reviewer checks.

---

## Token slots

A slot is a CSS custom property name. Components below reference slots only. **Colour slots are
MODE-AWARE**: each needs a dark and a light value, because a value that clears contrast on a dark
surface rarely clears it on a white one (§ Contrast contract).

### Colour

| Slot | Role |
|---|---|
| `--surface-0` … `--surface-3` | Page background → cards/panels → elevated (modals, popovers) → hover/active rows |
| `--border` | Dividers and card edges — decorative, exempt from 1.4.11 |
| `--border-control` | The boundary of an input, select, checkbox or toggle — the edge that IDENTIFIES the control, so it needs 3:1 against the surface (WCAG 1.4.11) |
| `--text-primary` · `--text-body` · `--text-muted` | Headings and key data · body copy · meta, timestamps, placeholders |
| `--color-accent` · `--color-accent-hover` | The brand's interactive FILL (primary buttons, progress, selection) and its hover |
| `--color-accent-fg` | Text and icons ON the accent fill |
| `--color-accent-text` | The accent used AS TEXT on surfaces (links, accent labels) |
| `--color-accent-muted` | A subtle tint (tags, selected-row background, chat bubbles) |
| `--color-<state>` · `-fg` · `-text` · `-muted` | The same four for each STATE: `success`, `warning`, `danger`, `info` — fill, text on the fill, the state as text, the subtle tint |
| `--color-ai` · `-fg` · `-text` · `-muted` | AI-generated content and AI suggestions (§ AI Interaction Patterns); required when the product has AI surfaces |
| `--focus-ring` | The focus indicator colour; defaults to `var(--color-accent)` |
| `--viz-1` … `--viz-6` | Categorical chart series (§ Charts and Data Visualization) |

### Typography

| Slot | Role |
|---|---|
| `--font-heading` · `--font-body` · `--font-mono` | Headings · body and UI · code, data tables, metrics |
| Type scale | Values for the levels H1, H2, H3, Body, Body small, Micro-label, Code, Data large — size, weight, line-height, font role, letter-spacing |

Components below say "heading font", "body font" and "mono font" for these three roles.

### Shape, space and motion

| Slot | Default | Role |
|---|---|---|
| `--radius-card` · `--radius-tag` · `--radius-pill` · `--radius-button` | none — the brand sets them | Corner radii (inputs use `--radius-button`) |
| `--space-xs` … `--space-2xl` | § Spacing System | Spacing scale |
| `--density-*` | § Density Modes | Row height, padding, input height per density |
| `--motion-*` · `--ease-*` | § Motion Language | Durations and easings |
| `--bp-sm` … `--bp-2xl` | § Responsive Layout — fixed, never overridden | Breakpoints |

### Mapping to the scaffold's variables

The saas-skeleton emits shadcn/ui's HSL variables in `app/globals.css` (Tailwind's `theme.extend`
reads them as `hsl(var(--x))`); a Tailwind CSS-first project declares the slots in `@theme`, where
only namespaced names generate utilities — keep the slot and alias it there
(`--color-surface-0: var(--surface-0)`) to get `bg-surface-0` without breaking the specs' `var(--surface-0)`. Fill shadcn's names FROM the slots so shadcn components inherit the brand:

| shadcn variable | Slot |
|---|---|
| `--background` · `--foreground` | `--surface-0` · `--text-primary` |
| `--card` · `--popover` | `--surface-1` · `--surface-2` |
| `--primary` · `--primary-foreground` | `--color-accent` · `--color-accent-fg` |
| `--destructive` · `--destructive-foreground` | `--color-danger` · `--color-danger-fg` |
| `--card-foreground` · `--popover-foreground` | `--text-primary` |
| `--secondary` · `--secondary-foreground` | `--surface-2` · `--text-primary` |
| `--muted` · `--muted-foreground` | `--surface-2` · `--text-muted` |
| `--accent` · `--accent-foreground` | `--surface-3` · `--text-primary` |
| `--border` · `--input` · `--ring` | `--border` · `--border-control` · `--focus-ring` |
| `--radius` | `--radius-card` |

⚠️ shadcn's `--accent` is its HOVER surface (menu items, ghost buttons, select options), not the
brand accent — mapping it to `--color-accent` paints every hover in solid brand colour. shadcn's
names stop at `destructive`; `success`, `warning`, `info` and `ai` stay as their slots.

⚠️ The scaffold switches mode with the `.dark` class (`darkMode: ["class"]`): its `:root` block is
LIGHT and its `.dark` block is dark, so fill both — the light values into `:root`, the dark into
`.dark`. A brand that keys its own CSS on `data-theme` switches the scaffold to the selector form
instead (`saas/60-saas-ui.md` § The design system names both hooks); one hook, never two.

⚠️ The saas-skeleton stores shadcn's variables as bare HSL channels (`221 83% 53%`) read through `hsl(var(--x))`: fill each colour with the slot's value CONVERTED to channels (`saas/60-saas-ui.md` § The design system; `--radius` is a length and takes the value as-is), and reference it as `hsl(var(--x))` or through the Tailwind class (`border-border`). `--border` is both a slot name and a shadcn name — on the saas-skeleton the channel form wins, so the component specs' `var(--border)` there means `hsl(var(--border))`; a hex written into it renders nothing.

---

## Contrast contract

**Every ratio is COMPUTED, never asserted** — the WCAG 2.2 relative-luminance formula (sRGB
linearisation threshold 0.04045; the older 0.03928 some tools still use changes no result that
matters here). A house system here once shipped 9 wrong ratios in 11 rows, 3 of them inverted; a
project caught it with the formula. The § Contrast table in `docs/design-system.md` lists, for BOTH
modes, the lowest ratio of each pair across `--surface-0`, `--surface-1` and `--surface-2`:

| Pair | Needs | WCAG |
|---|---|---|
| `--text-primary`, `--text-body`, `--text-muted` on surfaces | 4.5:1 | 1.4.3 AA |
| `--color-<x>-text` on surfaces, for accent, every state and ai | 4.5:1 | 1.4.3 AA |
| `--color-<x>-text` on its own `-muted` tint over `--surface-1` | 4.5:1 | 1.4.3 AA |
| `--color-<x>-fg` on `--color-<x>` (the accent's also on `--color-accent-hover`) | 4.5:1 | 1.4.3 AA |
| `--color-<x>` against surfaces, where the fill is the only indicator (progress, status dot, chart mark) or an error border replacing `--border-control` | 3:1 | 1.4.11 AA |
| `--border-control` and `--focus-ring` against surfaces | 3:1 | 1.4.11 AA |
| `--viz-1` … `--viz-6` against `--surface-1` | 3:1 | 1.4.11 AA |

Large-scale text (at least 18pt, or 14pt bold) needs only 3:1; this system does not rely on that
exception — every pair above is held to the body-text threshold. `--surface-3` is a hover surface, outside the
rows above: text keeps its colour there, `--text-muted` on `--surface-3` is forbidden whatever it
computes to, and so is any pair a brand's table marks forbidden.

**Dual-role colours need two values.** A colour used both as a fill and as text has two
independent constraints — its foreground must clear 4.5:1 against the fill, and the text value must
clear 4.5:1 against the surfaces — and on a dark-and-light product those constraints are usually
disjoint. That is why every state has separate `-fg` and `-text` slots, and why `-text` is
mode-aware. A single hex for a state's text in both modes is a finding unless the table proves it.

---

## Iconography

**Lucide** is the default icon library (shadcn/ui's default set; shadcn can also install tabler, hugeicons, phosphor or remixicon). A brand that picks another library names it in its `docs/design-system.md` § Radius and icon style; the rules below apply to whichever library it is.

### Library

- **Lucide React** for product UI (already used by shadcn/ui in the saas-skeleton scaffold).
- **Stroke width:** the brand's value (default 1.5px at 16px, 2px at 24px). Lucide's own default is 2 and SCALES with `size`, so set `strokeWidth` explicitly and use `absoluteStrokeWidth` where the stroke must stay constant across sizes. Consistent across the product.
- **Style:** Outline (no filled icons in core UI). Filled variants only for selected/active states where the outline+fill pair improves scanability (checkboxes, radio buttons, toggle confirmations).
- **Color:** inherit from `currentColor`. Default `--text-body`. Active `--color-accent-text`. Disabled `--text-muted` at 40% opacity.
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
I2. Never place text inside icons. If a label is needed, label the icon externally with micro-label type (body font 500).
I3. Never animate icons for decoration. Animate only when the icon represents an active state (loading spinner, syncing, recording, AI-thinking).
I4. Pair every icon with a text label in the first 3 occurrences a user sees of it. Icon-only is reserved for tab bars and toolbars where the labels would be too dense, and even there a tooltip with the label must appear within `--motion-default` of hover.
I5. Match weight to typography. The default 1.5px stroke pairs with body-font 400 text. Don't pair heavy-stroke icons with light body type or vice versa.
I6. The brand's icon library (Lucide by default) is the source of truth. If you need an icon, search it first. Only after confirming it does not have the concept (or does not have it in the right metaphor) may you commission a custom icon.
I7. Icons must remain legible at minimum size (16px). Detail beyond what reads at 16px is forbidden — it adds noise without adding meaning.
I8. Icon-only buttons require `aria-label` for accessibility. No exceptions.

---

## Motion Language

Motion is functional, never decorative. Every animation communicates one of: state change, attention direction, system status, or progress. Motion that does none of those is removed.

### Decorative motion (carve-out)

Purely ambient motion — particle backgrounds, animated/gradient backdrops, text/cursor effects (e.g. components from [reactbits.dev](https://reactbits.dev)) — is exempt from the "functional only" rule above, but ONLY:

1. **On marketing / landing surfaces only.** Never on product/app surfaces — those stay bound by the functional-motion scale below (interaction feedback tops out at `--motion-default: 150ms`).
2. **Re-tokenized first.** No hardcoded colors, durations, or easings: the imported component must consume the design tokens — this is the existing "never invent colors/fonts" rule, restated for imported components.
3. **`prefers-reduced-motion` honored.** A static or near-static fallback renders when the user requests reduced motion.
4. **Gate-clean.** It passes the existing a11y/visual/token gate with no new contrast, focus, or motion-safety regressions.

ReactBits is **copy-and-own** (like shadcn/ui): take the single component you need at point of use, paste it in, and re-tokenize it — it is NOT a dependency and NOT a fabrik-lib module (never add it to `package.json` or `fabrik-lib`).

### Duration Scale

| Token | Value | Use |
|---|---|---|
| `--motion-instant` | `0ms` | State swaps where motion would distract (toggle states, immediate value updates) |
| `--motion-fast` | `100ms` | Hover, focus, small surface transitions |
| `--motion-default` | `150ms` | Default. Most transitions. The Interaction Tokens' transition duration. |
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

**Focus ring fade-in:** `opacity 0 → 1` `--motion-fast` `--ease-default`. Focus ring is 2px solid `var(--focus-ring)`, offset 2px, never animated beyond opacity.

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

Sound is **opt-in per user**. Default is silent. When enabled, the brand supplies three short cues —
success, error, notification — each brief and distinct from the others;
volume is capped at 30% of system volume and respects system mute. (Ocoron's cues:
`ocoron-design-system.md` § Sound.)

Haptics on mobile (where supported):

- Light impact: button press, toggle.
- Medium impact: confirmation, successful action.
- Heavy impact: warning, destructive confirm.
- Never use haptics for routine state changes — they fatigue.

### Interaction Tokens

| Property | Value |
|---|---|
| Transition duration | `var(--motion-default)` (150ms) |
| Transition easing | `var(--ease-default)` — the plain CSS `ease` keyword is not the house curve |
| Hover lift | `translateY(-1px)` |
| Press feedback (mobile) | `translateY(1px)` + `scale(0.98)` |
| Focus ring | `2px solid var(--focus-ring)`, offset 2px |

---

## Component Patterns

### Cards

```
Background: var(--surface-1)
Border: 1px solid var(--border)
Border-radius: var(--radius-card)
Padding: var(--space-md)
Shadow: none in dark mode — use the border (light mode may add the brand's subtle shadow)
Hover: background var(--surface-3), translateY(-1px), transition var(--motion-default) var(--ease-default)
```

### Tags / Badges

```
Font: micro-label (body font 500, 10px, uppercase, letter-spacing 1.5px)
Padding: 3px 8px
Border-radius: var(--radius-tag)
Background: the colour's muted slot (e.g. var(--color-accent-muted), var(--color-danger-muted))
Text: the colour's TEXT slot (e.g. var(--color-accent-text) — never the fill as text)
```

### Pills

```
Font: body font 400, 12px
Padding: 4px 12px
Border-radius: var(--radius-pill)
Border: 1px solid var(--border)
Background: transparent
Hover: background var(--surface-3)
```

### Buttons

```
Primary:
  Background: var(--color-accent)
  Text: var(--color-accent-fg) (≥4.5:1 on the fill — § Contrast contract)
  Font: body font 500, 13px
  Padding: 8px 16px
  Border-radius: var(--radius-button)
  Hover: var(--color-accent-hover), translateY(-1px)

Secondary:
  Background: transparent
  Border: 1px solid var(--border)
  Text: var(--text-primary)
  Hover: background var(--surface-3)

Danger:
  Background: var(--color-danger)
  Text: var(--color-danger-fg)
```

### Tab Bar

```
Position: sticky top
Font: body font 500, 11px, uppercase, letter-spacing 1px
Active: text var(--color-accent-text), border-bottom 2px solid var(--color-accent)
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
Header: heading font 600, 14px
Border: 1px solid var(--border) on container
Transition: max-height var(--motion-default) var(--ease-default)
```

### Data Hierarchy Pattern

```
Headline: var(--text-primary), heading font 600
Body: var(--text-body), body font 400
Meta: var(--text-muted), body font 400, 12px
Numeric: mono font 300-400
```

### KPI Card

Used on dashboards for key performance indicators.

```
Background: var(--surface-1)
Border: 1px solid var(--border)
Border-radius: var(--radius-card)
Padding: var(--space-md)
Structure:
  Row 1: micro-label (body font 500, uppercase, 10px, --text-muted) — KPI name
  Row 2: large numeric (mono font 300, 28px, --text-primary) — current value
  Row 3: delta (mono font 400, 13px, --color-success-text / --color-danger-text, with an arrow — never colour alone) — period change
Optional: 4px progress bar at bottom for goal-tracked KPIs
```

### Activity Feed Item

Used on dashboard activity rails and inside [module] views.

```
Layout: 24px icon + content + timestamp
Icon: monochrome, --text-muted by default
Source label (above content): body font 500, uppercase, 10px, letter-spacing 1.5px, --text-muted
Content: body font 400, 14px, --text-body
Timestamp: body font 400, 12px, --text-muted
Always name the source that produced the event ("[Module] completed weekly report generation").
Hover: --surface-3, no lift
```

---

## Density Modes

Three density modes. Users select their preference in workspace settings; the choice persists per-device.

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

- Font: body font 500, `--density-font-meta`, uppercase, letter-spacing 1px.
- Background: `var(--surface-1)`.
- Sticky top when scrolling the table body.
- Sort indicator: `▲` ascending, `▼` descending. Only one column sorted at a time unless the product explicitly supports multi-sort.
- Resizable columns via drag handle (cursor: `col-resize`).

### Body Rows

- Font: body font 400, `--density-font-body`.
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
- Destructive actions (Delete) are always last, styled with `var(--color-danger-text)`.

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
- **Error loading:** "Failed to load data" + "Retry" button. Danger accent on the message using `var(--color-danger-text)`.

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
- Section grouping: related fields grouped under a section heading (H3, heading font 600) with `var(--space-lg)` gap between sections.
- Card container: each form section wrapped in a card (`var(--surface-1)`, `var(--border)`, `var(--radius-card)`, padding `var(--space-md)`).

### Labels

- Position: above the input (never floating, never beside).
- Font: body font 500, 13px, `var(--text-body)`.
- Required indicator: red asterisk `*` after the label text, colored `var(--color-danger-text)`.
- Optional fields: append "(optional)" in `var(--text-muted)` after the label. Prefer marking optional fields when most fields are required; mark required fields when most are optional.

### Inputs

- Height: `var(--density-input-height)`.
- Background: `var(--surface-0)`.
- Border: 1px solid `var(--border-control)` — the input's boundary identifies it, so it needs 3:1 against the surface (1.4.11); the decorative `var(--border)` does not.
- Border-radius: `var(--radius-button)`.
- Focus: border color `var(--focus-ring)`, box-shadow `0 0 0 2px var(--color-accent-muted)`.
- Placeholder text: `var(--text-muted)`, body font 400.
- Disabled: opacity 0.5, cursor `not-allowed`.

### Validation

- Validate on blur for individual fields. Validate on submit for the full form.
- Error message appears below the input, body font 400, 12px, `var(--color-danger-text)`, with an error icon (color is never the only signal — ACC2).
- Error border: `var(--color-danger)` replaces `var(--border-control)`.
- Success indicator: a `var(--color-success-text)` checkmark icon inline (right side of input) after correction. Do not turn the entire border green — it is too noisy.
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
- Active step: `var(--color-accent)` fill. Completed: `var(--color-success)` fill with a `var(--color-success-fg)` checkmark. Upcoming: `var(--border)` outline.
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
- Opens a centered modal overlay with a blurred backdrop (`backdrop-filter: blur(8px)`; Baseline only since 2024, so the scrim must stay readable where the blur does not render).

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
- Border-radius: 12px (or the brand's `--radius-card` scaled up).
- Shadow: `0 16px 48px rgba(0,0,0,0.4)` (this is the one exception where shadow is used in dark mode — modal overlays).

### Result Categories

Results are grouped by type, in this order:

1. **Recent** — last 5 items the user interacted with, matching the query.
2. **Navigation** — pages and views (e.g., "Go to Settings", "Go to Invoices").
3. **Records** — matching entities from the database (contacts, invoices, projects, etc.).
4. **Commands** — actions the user can trigger (e.g., "Create invoice", "Export CSV").
5. **Ask AI** — freeform natural-language queries sent to the AI assistant.

Each category has a muted label header (body font 500, 10px, uppercase, `var(--text-muted)`).

### Result Row

- Height: 40px.
- Icon (16px) + label (body font 400, 14px) + meta text (body font 400, 12px, `var(--text-muted)`, right-aligned).
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

Recharts (React) is the standard chart library for every Fabrik GUI — shadcn/ui's chart components are built on it. It renders SVG, supports responsive containers, and reads the token slots.

### Color Rules

- Categorical series use `var(--viz-1)` … `var(--viz-6)` in order. Each needs 3:1 against `--surface-1` in both modes (1.4.11 — a chart mark is a graphical object), computed in the brand's § Contrast table.
- Semantic series keep their meaning: a positive/negative or good/bad series uses `--color-success` / `--color-danger`, and a warning threshold `--color-warning`. Never colour a neutral category red or green on a chart that also shows good and bad.
- Never rely on hue alone — red and green are the pair colour-blind users most often cannot separate. Distinguish series by position, direct labels, line dash or marker shape as well (ACC2).
- More than 6 series: use opacity variants (80%, 60%) of the six, or regroup into "Other". Never invent new colours.

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
- Axis labels: body font 400, 11px, `var(--text-muted)`.
- Axis lines: `var(--border)`, 1px solid.
- Y-axis: always start at 0 for bar charts. Line/area charts may use a non-zero baseline if the variance is small relative to the absolute values — but add a visual break indicator.
- X-axis: rotate labels 45deg if they overlap. Truncate long labels with ellipsis.

### Interactivity

- Tooltip on hover: `var(--surface-2)` background, `var(--border)` border, `var(--radius-button)`. Shows the exact value, formatted per locale.
- Click on data point: optional drill-down. If supported, show a cursor pointer and navigate to the detail view.
- Legend: positioned below the chart, horizontal layout. Click to toggle series visibility.
- Responsive: charts fill their container width. Minimum height: 200px. Aspect ratio is not fixed.

### Chart Rules

- **C1:** Every chart must have a title (H3, heading font 600) and an optional subtitle explaining the time range or filter context.
- **C2:** Never use 3D effects, gradients on bars, or decorative elements. Flat, clean, data-first.
- **C3:** All charts must include an accessible data table alternative (expandable, hidden by default) for screen reader users.
- **C4:** Loading state: show a skeleton chart (pulsing gray rectangle matching the chart dimensions). Never show a spinner overlaid on a half-rendered chart.
- **C5:** Empty state: "No data for this period" + suggestion to adjust the date range. Never show an empty axis grid with no data.
- **C6:** Use the mono font for all numeric values in tooltips and axis labels.
- **C7:** Animations: data points animate in on first render (`--motion-slow`, `--ease-default`). Subsequent updates animate transitions (`--motion-default`). No looping animations; none at all under `prefers-reduced-motion`.

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
- Heading: body font 500, 16px, `var(--text-primary)`. Example: "No invoices yet."
- Description: body font 400, 14px, `var(--text-body)`. Example: "Create your first invoice to get started."
- CTA: primary button below the description.

### Empty — Filtered to Zero

- Same layout as "No Data Yet" but without illustration.
- Heading: "No results match your filters."
- CTA: "Clear all filters" link (not a button — it's a low-commitment action).
- Never suggest creating a new record in this state — the user is looking for existing data.

### Error

- Danger accent: left border 3px solid `var(--color-danger)` on the error container, plus an error icon.
- Heading: body font 500, 16px, `var(--text-primary)`. Example: "Failed to load invoices."
- Description: body font 400, 14px, `var(--text-body)`. Explain what went wrong if known.
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
- Full-page success: a `var(--color-success-text)` checkmark icon (48px), heading, description, and a "Continue" button.

### Partial Success / Warnings

- Used when an action partially completed (e.g., "3 of 5 emails sent successfully").
- Warning accent: left border 3px solid `var(--color-warning)` on the container, plus a warning icon.
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
| **AI Suggestion** | `var(--color-ai)` | Inline card, contextual | No | "AI detected a duplicate contact — Merge?" |
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
- Badge: unread count, `var(--color-accent)` background, `var(--color-accent-fg)` text, max display "99+".
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
- Styled: body font 400, `var(--text-muted)`, italic.
- Accept: `Tab` key. Dismiss: continue typing or `Escape`.
- Use for: auto-complete, sentence completion, field suggestions.

#### A2 — Generated Block

- A distinct block of AI-generated content inserted into the page.
- Bordered container: left border 2px solid `var(--color-ai)`, background `var(--color-ai-muted)`.
- Header: "AI Generated" badge (micro-label style, `var(--color-ai-text)` on `var(--color-ai-muted)`).
- Actions: "Accept" (primary button), "Edit" (secondary), "Discard" (text link, `var(--color-danger-text)`).
- Use for: generated summaries, draft emails, suggested descriptions.

#### A3 — Action Confirmation

- When AI proposes to take an action (e.g., merge duplicates, send a message), show a confirmation card.
- Card contains: description of the action, preview of the outcome, "Confirm" (primary) and "Cancel" (secondary) buttons.
- Destructive AI actions require an additional warning: "This cannot be undone" in `var(--color-danger-text)`.
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
| **High confidence** | Solid `var(--color-success)` dot + "High" label | AI found strong evidence in the data. |
| **Medium confidence** | Solid `var(--color-warning)` dot + "Medium" label | AI inferred this with partial data. User should verify. |
| **Low confidence** | Outline `var(--color-danger)` dot + "Low" label | AI is guessing. Treat as a starting point, not an answer. |

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
- Numbers, dates, and currency symbols follow the locale format through `Intl` — which digits appear depends on the LOCALE TAG, not the language: CLDR gives plain `ar` and `ar-AE` Latin digits (1,234.5) but `ar-EG` and `ar-SA` Arabic-Indic digits (١٬٢٣٤٫٥), and `fa` Persian digits (۱٬۲۳۴٫۵). Store and send the full locale tag (`ar-SA`, not `ar`) so the user gets the digits their region expects.
- Charts: mirror the X-axis direction in RTL (time flows right-to-left). Y-axis remains on the inline-start side.

### Translation Workflow

1. English is the source language for all strings.
2. Strings are extracted to JSON locale files (`/locales/{code}.json`).
3. AI-translate as first draft, then validate with the i18n kit's `scripts/validate_i18n.py`. Its Level 1 structural check (missing keys, placeholder mismatches, empty values, completeness drift — free, instant) is the gate: `python scripts/validate_i18n.py`. ⚠️ The kit's Level 2 (back-translation) and Level 3 (native-speaker critique) still shell out to the Kilo CLI, a toolchain the fleet has retired (D-364), so they are never a gate; until the validator is ported, a meaning-and-tone review of each new locale is a recorded manual step (by hand or with `claude -p`), never skipped silently.
4. **Agent workflow:** AI-translate → run the Level 1 check → fix → re-run until it passes clean → record the Level 2/3 review. Translation is not done until Level 1 passes and the review is recorded.
5. New features ship in English first. Translations must be validated within one release cycle.
6. Interpolation syntax: `{variable}` placeholders. Never concatenate translated fragments — word order varies by language.
7. Full i18n kit (validate script, `_context.json` for product/tone/register config, JS loader, HTML snippets): `templates/i18n-kit/` (the copy `scaffold.py` seeds; `templates/scaffold/i18n-kit/` is an older, divergent copy). Applies to all GUI scaffolds (saas-skeleton, static-site, docusaurus, chrome-extension, office-extension, mobile-app, desktop-app).

### Localization Quality Bar

- All user-facing strings must be externalized — no hardcoded text in components.
- Pluralization: use ICU MessageFormat syntax (e.g., `{count, plural, one {# item} other {# items}}`). Turkish has no grammatical plural for counted nouns — handle this explicitly.
- Gender-neutral language in English. In Turkish, gender-neutrality is natural; in Arabic and Russian, follow standard grammatical conventions.
- Locale-specific formatting: see Date, Time, Currency, and Number Formatting section.

### Multilingual Rules

- **ML1:** The `lang` attribute on `<html>` must match the user's selected language. This affects screen readers and browser behavior.
- **ML2:** The resolved font stack must cover every target script. Check each font role's coverage (Latin, Cyrillic, Arabic) in the brand's § Typography, and add a matching fallback for any script it lacks (e.g. Noto Sans Arabic for `ar` and `fa`).
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
  - `ar-SA` / `ar-EG`: ٢٣/٥/٢٠٢٦ (Arabic-Indic digits); plain `ar`: 23/5/2026
  - `fa`: the Persian (Solar Hijri) calendar and Persian digits by default — ۱۴۰۵/۳/۲ for the same day; pass `calendar: "gregory"` only when the product has decided to show Gregorian dates
- Relative dates for recent items: "2 hours ago", "Yesterday", "3 days ago". Switch to absolute after 7 days.
- Hover tooltip on relative dates always shows the full absolute date+time.
- Use `Intl.DateTimeFormat` — never construct date strings manually.

### Times

- Let `Intl` pick the hour cycle: 24-hour for `tr`, `fa`, `ru`; 12-hour for `en-US` and for `ar` (2:30 م).
- Override available in user settings.
- Always show timezone abbreviation when displaying times that could be ambiguous (e.g., "14:30 UTC+3").

### Numbers

- Decimal separator: `.` for `en`, `,` for `tr` and `ru`, `٫` wherever Arabic-Indic or Persian digits are used (`ar-SA`, `ar-EG`, `fa`).
- Thousands separator: `,` for `en` and plain `ar`, `.` for `tr`, a no-break space (U+00A0) for `ru`, `٬` with Arabic-Indic or Persian digits.
- Use `Intl.NumberFormat` — never manual formatting.

### Currency

- Default currency follows workspace settings, not user locale.
- Symbol placement follows locale convention: `$1,234.50` (en-US), `₺1.234,50` (tr — the symbol comes first), `1 234,50 ₽` (ru), `١٬٢٣٤٫٥٠ ر.س.` (ar-SA).
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
- **FMT5:** Tables with numeric columns must right-align and use the mono font (or tabular figures) for visual alignment.
- **FMT6:** Phone number inputs must validate format and show the country flag emoji next to the country code.
- **FMT7:** When displaying a range (date range, price range), use an en-dash `–` with spaces: "May 1 – May 31", "$100 – $500". Never a hyphen.
- **FMT8:** Percentages: always show 1 decimal place. Use `Intl.NumberFormat` with `style: 'percent'` — it also places the sign (`42.7%` in `en`, `%42,7` in `tr`).

---

## Print and Export

### Print Stylesheet

- Every data-heavy page must have a print stylesheet (`@media print`).
- Hide: navigation, sidebar, toasts, modals, tooltips, action buttons.
- Show: content area at full width, page title, data tables, charts (rendered as static images).
- Font: use system fonts for print (no web font loading). Body: 11pt, headings: 14pt.
- Colors: force the LIGHT-mode token values for print regardless of the user's theme (text from the light `--text-primary`, backgrounds white).
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

WCAG 2.2 AA is the baseline (the current W3C Recommendation; WCAG 3 is still a Working Draft and APCA is not normative). Every text and control pair clears the thresholds in § Contrast contract, computed per brand in its `docs/design-system.md` § Contrast table — both modes, never "re-validate per project" later.

### Keyboard Navigation

- All interactive elements must be reachable via `Tab` key in a logical order.
- Focus ring: 2px solid `var(--focus-ring)`, offset 2px, 3:1 against the adjacent colour (1.4.11). Never remove the focus outline, and never let a sticky header, toast or drawer hide the focused element entirely (2.4.11 Focus Not Obscured, AA).
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
  - Disable all CSS transitions and animations except progress and loading indicators (§ Reduced Motion).
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
- **ACC3:** Touch targets must be at least 44x44px on touch devices — a house rule at WCAG's AAA level (2.5.5); the AA floor, 24x24 CSS px (2.5.8), binds every pointer target everywhere, including dense desktop tables.
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

**RWD is mandatory for every web scaffold — no exceptions.** Every page, component, and layout must render correctly from 375px (iPhone SE — smallest current phone) to 2560px (ultrawide). This is not optional; coding agents must implement it.

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
| **static-site** | Full RWD, mobile-first. Every marketing page must pass a Lighthouse mobile audit (Google retired its Mobile-Friendly Test in December 2023). Images use `srcset` + `sizes`. |
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
- **RWD7:** Font sizes must be readable on mobile without zoom. Minimum 14px body text on all viewports (the Body type-scale level may not go below it).
- **RWD8:** Modals become full-screen sheets on viewports < 640px. Never show a floating modal on a phone — it's unusable.
- **RWD9:** Sidebar navigation MUST collapse on viewports < 1024px. A persistent 240px sidebar on tablet/mobile is banned.
- **RWD10:** Test every page at 375px, 768px, 1440px before merge. Untested responsive = broken responsive.

---

## Scaffold Adaptation Matrix

What each GUI scaffold takes from this template. Brand-specific notes (which fonts load where, a house theme's defaults) live in the brand's own pack.

| Scaffold | Adoption |
|---|---|
| **saas-skeleton** (Next.js + shadcn/ui) | Full. Fill shadcn's variables from the slots (§ Mapping to the scaffold's variables) in `app/globals.css`; tables, forms and dashboards use the card pattern; side nav uses the surface hierarchy (`--surface-0` → `--surface-1`). Both modes mandatory — OS `prefers-color-scheme` on first load, a manual toggle in Settings, the choice persisted in `localStorage`. The bundled `docs-site/` (Docusaurus) maps the same slots to Infima's `--ifm-*` variables. |
| **static-site** | The heading and body roles; the mono role only where the page shows code or data. The card pattern for hero and feature sections. Both modes (the light variant is required on public marketing pages). |
| **docusaurus** | Slots mapped to Infima's `--ifm-*` variables in `src/css/custom.css`; code blocks use the mono role; sidebar uses the surface hierarchy; search bar, breadcrumbs and TOC use the text hierarchy. |
| **chrome-extension** (Manifest V3) | Same slots, tighter spacing (`--space-md: 12px`, `--space-sm: 6px`) declared as a § Structural override; the popup's fixed width means a single-column card layout; the tab bar becomes popup navigation; pills for tags and statuses; a font-size floor of 11px. |
| **mobile-app** (React Native) | The same slots mapped into the mobile theme — how is `mobile-app/80-mobile.md`'s and the mobile design packs' job, not restated here. Cards become touchable list items with the press feedback in § Motion Language; the tab bar becomes bottom navigation; 44px touch targets; a font-size floor of 13px. |
| **desktop-app** (Electron / Tauri) | As saas-skeleton, plus title-bar integration; the system-tray badge uses `--color-accent`; both modes follow the OS with a toggle in the title bar; minimum window 800×600. |

`office-extension` is UI-bearing but has no rules pack yet, so it has no row here (recorded in the backlog); `wordpress` stays registered for deploys, but `create_project` refuses to scaffold it.

---

## Default tokens (CSS)

The structural defaults above as one block — a brand's CSS adds its colour, font and radius values
beside these and restates only what its § Structural overrides change.

```css
:root {
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;

  --motion-instant: 0ms;
  --motion-fast: 100ms;
  --motion-default: 150ms;
  --motion-slow: 250ms;
  --motion-deliberate: 400ms;
  --motion-celebration: 600ms;

  --ease-default: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-linear: linear;
  --ease-spring: cubic-bezier(0.5, 1.5, 0.5, 1);
  --ease-emphasis: cubic-bezier(0.4, 0, 0.2, 1);

  /* retired names — keep only as aliases in existing code */
  --transition-speed: var(--motion-default);
  --transition-ease: var(--ease-default);
}
```

The density tokens are set per mode (§ Density Modes) on `<body>` or the root container; the
breakpoints are Tailwind's defaults (§ Responsive Layout).

---

## Rules for Coding Agents

### Visual Rules

1. **Never invent colours or fonts.** Use only the slots; the values come from the project's `docs/design-system.md`. A new semantic colour is a new slot proposed to this template first.
2. **Never use inline styles** in production code. Use Tailwind classes or CSS mapped to the slots.
3. **Font roles are strict.** Headings use the heading font, body and UI the body font, code and data the mono font.
4. **Both dark and light mode are mandatory.** Detect OS `prefers-color-scheme` on first load (the brand says which mode wins when the OS states none), provide a manual toggle in Settings, persist the choice per device. No scaffold ships dark-only or light-only.
5. **No shadows in dark mode.** Use 1px borders for elevation; the modal-overlay shadow in § Search and Command Palette is the one exception. Light mode may use the brand's subtle shadow.
6. **Component patterns are canonical.** Cards, tags, pills, buttons, tabs — use the specs above. Don't reinvent.
7. **Spacing uses the token scale.** No arbitrary pixel values. Use `xs/sm/md/lg/xl/2xl`.
8. **Motion uses the motion tokens.** `--motion-default` with `--ease-default` for ordinary transitions; nothing longer than `--motion-deliberate` and no `--ease-spring` outside a real celebration (M1, M2).
9. **The accent is for interactivity.** Don't use `--color-accent` for decorative elements, backgrounds, or large surfaces.
10. **Colour is never the only signal.** Every state colour ships with an icon, a label or a pattern (ACC2).
11. **The contrast table is computed.** A new or changed colour value is not done until the brand's § Contrast table is recomputed with the WCAG formula.

### Responsive Rules

12. **Every web component must be responsive.** Author mobile-first, layer up with `sm:`, `md:`, `lg:` breakpoints. No fixed-width layouts. No desktop-only components. No exceptions.
13. **Test at 375px before delivering.** If a component overflows or becomes unusable at 375px viewport width, it is not done. This is a gate, not a guideline.
14. **Sidebar collapses below 1024px.** Icon rail at 768-1023px (`md:`), hidden (hamburger/bottom tabs) below 768px. A persistent full sidebar on mobile/tablet is banned.
15. **Tables transform on mobile.** Use card transformation (Pattern A) or horizontal scroll with sticky first column (Pattern B). Unmodified desktop tables on phone viewports are banned.
16. **Modals become full-screen sheets below 640px.** Floating modals on phone viewports are banned.

Verbal rules — forbidden language, naming, capitalisation, how to write errors and describe AI — belong to the brand's voice (§ Voice in its `docs/design-system.md`; for ocoron, `ocoron-design-system.md` § Verbal Identity).
