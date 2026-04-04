# Audit: Rule Packs vs Ocoron Design System v2.0

## Summary

Checking each rule pack for:
1. Direct conflicts with the design system
2. Missing references to design system tokens/patterns
3. Opportunities to enforce Ocoron-specific standards

---

## 60-saas-ui.md — NEEDS UPDATES

### Issues:
1. **No reference to Ocoron design tokens.** The pack says "components consume design tokens, never raw values" but doesn't specify WHICH tokens. Should reference the Ocoron Design System as the authoritative token source.

2. **No font rules.** The SaaS UI pack has zero typography guidance. The design system specifies Space Grotesk / Inter / JetBrains Mono with strict role assignments. This is the most likely place agents will deviate.

3. **No color references.** The pack talks about "required states" (error, success, disabled) but doesn't map them to Ocoron semantic colors (`--color-danger`, `--color-success`, etc.).

4. **No dark mode directive.** The design system says dark mode is default. The SaaS UI pack is mode-agnostic — it should enforce dark-first.

5. **No shadow/border rule.** Design system says "no shadows in dark mode, use 1px borders." The SaaS UI pack doesn't address this.

6. **Microcopy section lacks verbal identity link.** The microcopy rules (error messages, empty states) should reference the Ocoron Verbal Identity — especially the forbidden language list, the "lead with outcome" rule, and the before/after examples.

7. **Missing component patterns.** The design system defines cards, tags, pills, buttons, tabs, progress bars. The SaaS UI pack should reference these as canonical.

### Recommended additions to 60-saas-ui.md:
```
## Ocoron Design System

- All SaaS UI projects must follow the Ocoron Design System (`docs/reference/ocoron-design-system.md`).
- Design tokens: use CSS custom properties (`--color-*`, `--surface-*`, `--text-*`) or their Tailwind equivalents. Never use raw hex values.
- Typography: Space Grotesk for headings, Inter for body/UI, JetBrains Mono for code/data. No substitutions.
- Dark mode is the default theme. Light mode is opt-in via `[data-theme="light"]` override.
- No box-shadows in dark mode. Use `1px solid var(--border)` for elevation. Subtle shadows allowed in light mode only.
- Component patterns (cards, tags, pills, buttons, tabs) follow the canonical specs in the design system. Do not reinvent.
- Microcopy follows the Ocoron Verbal Identity: lead with outcomes, specific over vague, no forbidden language.
```

---

## 20-typescript.md — ALIGNED (minor addition)

### Issues:
1. **No design system reference needed** — this is language-level discipline, not UI. ✅
2. **Environment variable pattern is correct** and compatible. ✅
3. **Port range (3000-3099) is compatible** with PORTS.md. ✅

### Minor addition:
- Could add a note that UI-facing TypeScript projects must also follow the Ocoron Design System for all visual output. But this is probably better handled by the SaaS UI pack cross-reference.

**Verdict: No changes needed.**

---

## 40-documentation.md — ALIGNED (minor addition)

### Issues:
1. **No writing style reference.** The doc rules cover file structure but not tone. Should link to Ocoron Verbal Identity for any user-facing documentation (not internal plans, but README descriptions, feature docs, etc.).

### Recommended addition:
```
## Writing Style
- User-facing documentation (README feature descriptions, API docs, landing copy) follows the Ocoron Verbal Identity in `docs/reference/ocoron-design-system.md`.
- Internal plans and changelogs are exempt from brand voice rules — clarity and speed matter more than tone.
```

**Verdict: Minor addition.**

---

## 42-docusaurus.md — NEEDS UPDATES

### Issues:
1. **Styling section is vague.** It says "Override Infima CSS variables in `custom.css`" but doesn't specify that those overrides must map to Ocoron Design System tokens. An agent could set arbitrary colors.

2. **No font directive.** Docusaurus has its own font stack. The design system specifies Space Grotesk + Inter + JetBrains Mono. The Docusaurus pack should mandate loading these and overriding Infima's defaults.

3. **No dark mode directive.** Design system says dark mode default. Docusaurus defaults to... whatever the theme sets. Should explicitly set dark mode as default via `colorMode.defaultMode: 'dark'`.

4. **The scaffold adaptation matrix in the design system already covers Docusaurus** — but the rule pack itself doesn't reference it.

### Recommended additions to 42-docusaurus.md:
```
## Ocoron Theme

- Override Infima CSS variables in `custom.css` with Ocoron Design System tokens. Map `--ifm-color-primary` → `#00D4AA`, surfaces, text hierarchy, etc.
- Load Space Grotesk (headings), Inter (body), JetBrains Mono (code) via Google Fonts or self-hosted. Override Infima's default font stack.
- Set `colorMode.defaultMode: 'dark'` in `docusaurus.config.js`. Dark mode is the Ocoron default.
- Code blocks already use monospace — ensure JetBrains Mono is the configured monospace font.
- Sidebar navigation uses the Ocoron surface hierarchy (`--surface-0` → `--surface-1`).
```

---

## 55-observability.md — ALIGNED

### Issues:
1. **No UI/visual components involved** — this is backend/infrastructure. ✅
2. **Structured logging, health endpoints, alerting** — none of this intersects with the design system. ✅
3. **The `snake_case` event naming convention** is compatible with Ocoron's technical voice. ✅

**Verdict: No changes needed.**

---

## 62-wordpress.md — NEEDS UPDATE

### Issues:
1. **The scaffold adaptation matrix says:** WordPress admin is untouched, but frontend theme gets full Ocoron adoption via Next.js (headless). The WP rule pack already covers headless CMS + Next.js integration via WPGraphQL. ✅

2. **Missing:** The frontend theme section should reference the Ocoron Design System for the Next.js frontend layer. When WordPress is used headlessly, the Next.js frontend is essentially a saas-skeleton/static-site — it should follow Ocoron tokens.

### Recommended addition to 62-wordpress.md:
```
## Frontend Theme (Headless)

- When using WordPress as headless CMS with a Next.js frontend, the frontend follows the Ocoron Design System in full — tokens, fonts, component patterns.
- Non-headless WordPress themes (if any) should use Ocoron colors and fonts where technically feasible via child theme CSS, but WordPress admin is never themed.
```

---

## 70-chrome-ext.md — NEEDS UPDATES

### Issues:
1. **No design system reference.** The pack covers MV3 constraints, state management, accessibility — but zero visual direction. An agent building a Chrome extension popup would have no guidance on colors, fonts, or component patterns.

2. **The design system scaffold matrix specifies:** tighter spacing (`--space-md: 12px`), 400px constraint, pill pattern, font floor 11px. None of this is in the rule pack.

3. **Framework choice (Preact/Svelte/React)** — all fine, but whichever is used must apply Ocoron tokens.

### Recommended addition to 70-chrome-ext.md:
```
## Ocoron Design System (Compact)

- Chrome extension UI follows the Ocoron Design System with compact adaptations:
  - Tighter spacing: `--space-md: 12px`, `--space-sm: 6px`.
  - Font size floor: 11px.
  - 400px popup width constraint → single-column card layout.
  - Tab bar maps to popup navigation.
  - Pill pattern for tags/statuses.
- All three fonts loaded (Space Grotesk, Inter, JetBrains Mono) but JetBrains Mono only for data displays.
- Colors, surfaces, borders follow the standard Ocoron token set.
```

---

## 80-mobile.md — NEEDS UPDATES

### Issues:
1. **Styling section contradicts design system.** The mobile pack says "NativeWind / Tailwind for React Native is not recommended" and recommends `StyleSheet.create()` or `react-native-unistyles`. The design system scaffold matrix says "Same color system mapped to NativeWind tokens." This is a **direct conflict**.

   **Resolution:** The mobile rule pack is correct — NativeWind has real performance overhead on mobile. The design system scaffold matrix should be updated to say `react-native-unistyles` instead of NativeWind. The color values stay the same; only the implementation mechanism changes.

2. **No Ocoron token reference.** The mobile pack has zero color, font, or spacing guidance. An agent would use arbitrary values.

3. **The design system says** Space Grotesk as custom font, Inter as custom font, cards become touchable list items with press feedback. None of this is in the rule pack.

### Recommended addition to 80-mobile.md:
```
## Ocoron Design System (Mobile)

- Apply Ocoron Design System color tokens via `react-native-unistyles` theme configuration. Same hex values, mapped to the unistyles theme object.
- Load Space Grotesk and Inter as custom fonts. JetBrains Mono for data/metrics displays.
- Cards → `Pressable` list items with `translateY(1)` + `scale(0.98)` press feedback (0.15s duration).
- Tab bar → bottom navigation using Ocoron accent color for active state.
- Touch targets: 44pt minimum (iOS) / 48dp minimum (Android) per accessibility rules.
- Font size floor: 13px.
- Dark mode is the default. Light mode uses Ocoron light surface token set.
```

### Design system update needed:
Change scaffold matrix mobile section from "NativeWind token mapping" to "`react-native-unistyles` token mapping" to align with the mobile rule pack's ban on NativeWind.

---

## 95-multi-tenant-saas.md — ALIGNED

### Issues:
1. **No UI/visual components** — this is database/backend architecture. ✅
2. **RLS, tenant context, caching** — none of this intersects with the design system. ✅

**Verdict: No changes needed.**

---

## DESIGN SYSTEM UPDATE NEEDED

The mobile scaffold section references NativeWind, but the mobile rule pack bans it. Fix in design system:

Current: "Same color system mapped to NativeWind tokens."
Should be: "Same color system mapped to `react-native-unistyles` theme tokens."

Current: "Inter loaded as custom font (or system sans-serif fallback where needed)."
This is fine — no change needed.

---

## SUMMARY TABLE

| Rule Pack | Status | Action |
|---|---|---|
| 60-saas-ui.md | ⚠️ NEEDS UPDATE | Add Ocoron design system section (tokens, fonts, dark mode, component patterns, verbal identity link) |
| 20-typescript.md | ✅ ALIGNED | No changes |
| 40-documentation.md | ✅ MINOR | Add writing style reference to verbal identity |
| 42-docusaurus.md | ⚠️ NEEDS UPDATE | Add Ocoron theme section (Infima overrides, fonts, dark mode default) |
| 55-observability.md | ✅ ALIGNED | No changes |
| 62-wordpress.md | ⚠️ MINOR UPDATE | Add frontend theme note for headless Next.js |
| 70-chrome-ext.md | ⚠️ NEEDS UPDATE | Add compact design system section |
| 80-mobile.md | ⚠️ NEEDS UPDATE + CONFLICT | Add mobile design system section; fix NativeWind conflict |
| 95-multi-tenant-saas.md | ✅ ALIGNED | No changes |

**Design system itself:** Fix NativeWind → `react-native-unistyles` in mobile scaffold section.
