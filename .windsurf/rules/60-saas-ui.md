---
activation: glob
globs: ["**/*.tsx", "**/*.jsx", "**/components/**", "**/app/**", "**/pages/**", "**/tailwind.config.*"]
description: SaaS UI patterns — navigation, components, dashboards, performance, billing UI, tenant UI, i18n
trigger: glob
---
<!-- CONSUMER: Coding agents building SaaS frontend (Next.js/React)
     GOAL: SaaS UI patterns — navigation, dashboards, billing UI, tenant UI, performance, i18n
     TRAYCER USAGE: Injects as Context File for frontend tickets in SaaS projects.
     AGENT USAGE: Follow verbatim when building SaaS UI components and pages. -->

# SaaS UI Rules

Apply when working on frontend/UI code (Next.js, React, Tailwind). Skip for Python backend logic, Docker, infrastructure files, and email templates (see `86-email-templates.md`).

---

## Ocoron Design System

All SaaS UI projects follow `ocoron-design-system.md` as the single source of truth. Key points for agents:

- **Design tokens:** CSS custom properties (`--color-*`, `--surface-*`, `--text-*`) or Tailwind theme equivalents. Never raw hex values, arbitrary colors, or hardcoded font names.
- **Typography:** Space Grotesk (headings), Inter (body/UI), JetBrains Mono (code/data). No substitutions.
- **Dark mode is the default.** Light mode via `[data-theme="light"]`.
- **No box-shadows in dark mode.** Use `1px solid var(--border)`.
- **Component patterns** (cards, tags, pills, buttons, tabs, progress bars, KPI cards, data tables, forms) follow the canonical specs. Do not reinvent.
- **Motion** follows the duration scale (`--motion-fast` through `--motion-deliberate`) and easing tokens. No bounce, no spring physics outside celebrations. See design system § Motion Language.
- **Spacing** uses the token scale (`xs/sm/md/lg/xl/2xl`). No arbitrary pixel values.
- **Density modes** (Comfortable/Compact/Spacious) apply to data-heavy views. See design system § Density Modes.
- **States** — every interactive component handles all enriched states (loading, empty, error, permission denied, success, partial success, disabled). See design system § States.
- **Microcopy** follows the Ocoron Verbal Identity and Voice Across Surfaces table.

### Font Loading (Next.js)

```typescript
// app/layout.tsx
import { Space_Grotesk, Inter, JetBrains_Mono } from 'next/font/google';
import { detectLanguage } from '@/lib/i18n/server';

const spaceGrotesk = Space_Grotesk({ subsets: ['latin'], variable: '--font-heading', display: 'swap' });
const inter = Inter({ subsets: ['latin'], variable: '--font-body', display: 'swap' });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono', display: 'swap' });

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const lang = await detectLanguage();
  return (
    <html lang={lang} className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrainsMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
```

`next/font` self-hosts the fonts at build time — no external CDN requests, no GDPR concern, optimal loading. Never use `<link>` to Google Fonts CDN.

---

## Navigation

- Use a stable side nav for structural destinations; reserve top nav for global utilities (search, help, profile, notifications).
- Add breadcrumbs when the IA is hierarchical; add recents/starred when task-switching is frequent.
- Never bury primary tasks behind deep nav hierarchies; apply progressive disclosure for secondary pages.

---

## Authenticated vs Public Homepage

- Never show marketing content to authenticated users. Logged-in homepage = actionable dashboard. Non-logged-in homepage = value proposition + CTA.
- Logged-in dashboard shows: active work status, recent completions, quick actions, and system health relevant to the user's role. Not a hero banner, not a feature list.
- If the marketing site and app share the same route (`/`), gate on auth state — do not render the landing page inside the app shell.

---

## Dashboard Design

- **Dashboards answer questions, not display data.** Every metric card must answer a specific question: "How many jobs failed today?", "What needs my attention?", "Am I within budget?" If you can't state the question, don't add the card.
- **Show what matters right now.** Active jobs, failures needing retry, next action required. Push historical trends and analytics behind a "View details" link.
- **No data vomit.** Cap visible stat cards at 6-8 per viewport. Group related metrics. Use progressive disclosure for secondary data.
- **Role-based content.** Admin dashboard shows system health. Regular user dashboard shows their content. Never expose infrastructure metrics to regular users.
- **KPI cards** follow the design system KPI Card pattern (micro-label + large numeric + delta).

---

## Quick Actions

- Every dashboard must have at least one quick-action widget that lets the user start their primary workflow without navigating away.
- Quick actions: 1-2 inputs max, inline on the dashboard (sidebar, card, or pinned input), with immediate toast feedback on submit.
- Examples: "Add URL + Go", "Create project", "Invite member", "Upload file". Complete the action without a page transition.

---

## Real-Time Updates

- Use 30s `setInterval` + `fetch` polling for dashboard status updates. This is what production SaaS tools use.
- Do NOT use WebSocket for dashboards — the complexity is not justified for data that changes every few seconds.
- Reserve WebSocket for: real-time chat, collaborative editing, live notifications that must appear within 1s. If the data can be 30s stale, poll.
- Auto-refresh endpoints return JSON; the client patches React state. Never reload the full page.

---

## Component Hierarchy

- Follow the token -> primitive -> component -> pattern -> page layering: components consume design tokens, never raw values.
- Implement each primitive (`Button`, `Text`, `Icon`, `Stack`) once; compose into `FormField`, `Table`, `Modal`, `Toast` — never re-implement behaviors like focus management or error handling at the page level.
- Default to Server Components in Next.js; add `'use client'` only for hooks, browser APIs, or event handlers.

---

## Billing & Subscription UI

For SaaS products with paid tiers (reference `88-saas-launch-checklist.md` and SaaS domain module §4/§7):

### Plan-to-Feature Gating

- Every paywalled feature checks the gating matrix before rendering. If the user's plan doesn't include the feature, show a gate:
  - **Soft gate:** feature visible but locked. Show a brief value statement + "Upgrade to [plan]" CTA. Never hide the feature entirely — discovery drives upgrades.
  - **Hard gate:** feature completely unavailable (e.g., API-only tiers). Show "Available on [plan]" with a link to the pricing page.
- Gate checks happen both client-side (for UX) and server-side (for security). See `35-security-auth.md`.

### Pricing Page

- Show all tiers side-by-side with a feature comparison matrix.
- Highlight the recommended tier. Annual/monthly toggle with savings callout.
- Current plan marked clearly. Upgrade path obvious. Downgrade path accessible but not prominent.

### Usage Display

- Show current usage vs plan limits: "47 / 100 projects used" with a progress bar.
- Usage approaching limit (>80%): show a subtle upgrade nudge — not a blocking modal.
- Usage at limit: feature disabled with clear explanation + upgrade CTA.

### Billing Settings

- Current plan, next billing date, payment method summary.
- Invoice history with download links.
- Cancel flow: state the consequence clearly, offer alternatives (downgrade, pause), require confirmation.

---

## Multi-Tenant UI

For SaaS products with tenant isolation (reference `95-multi-tenant-saas.md`):

### Org/Workspace Switcher

- If users can belong to multiple orgs, show an org switcher in the top nav or side nav header.
- Current org name + logo visible at all times. Switching orgs reloads data — never mix tenant data across contexts.

### Team Management

- Invite flow: email input + role selector → sends invite → shows pending invites.
- Member list: name, email, role, last active, actions (change role, remove).
- Role display follows the design system Permissions UX patterns.

### Tenant-Scoped Navigation

- Nav items that are tenant-scoped show the org context. Items that are user-scoped (profile, personal settings) do not.
- Admin-only nav items visible only to Admin/Owner roles. See `35-security-auth.md` Pattern B for role definitions.

---

## Optimistic UI

- Apply optimistic updates only where rollback is safe and the failure path is handled.
- Pattern: optimistic update → show "Saving..." → confirm "Saved" on server ACK → on failure, revert state and show a retryable inline error with preserved user intent.
- Never silently swallow mutation failures.

---

## Performance Budgets

- Core Web Vitals targets (p75 field): LCP <= 2.5s, INP <= 200ms, CLS <= 0.1.
- No render-blocking CSS/JS on the initial route; inline critical CSS, defer the rest.
- Apply route-level code splitting; lazy-load admin-only or rarely used UI.
- Static assets (JS/CSS/fonts) must have explicit `Cache-Control`; user-specific API responses must not be publicly cached.

---

## Accessibility

Target WCAG 2.2 AA as the baseline — non-negotiable. For detailed rules see `ocoron-design-system.md` § Accessibility (ACC1-ACC8). Key points for SaaS UI:

- Every form control must have a programmatic `<label>` association.
- Keyboard focus must remain visible and not be obscured by sticky headers/sidebars/modals (WCAG 2.4.11).
- Interactive touch targets must meet WCAG 2.5.8 minimum size or spacing.
- Modals: trap focus, support Escape, use `role="dialog"` with `aria-modal="true"`.
- Tooltips: use `role="tooltip"` + `aria-describedby` on the trigger; support keyboard dismiss.
- Do not block autofill or password managers (WCAG 3.3.8).
- Never use ARIA incorrectly — no ARIA is better than bad ARIA.

---

## Microcopy

All user-facing text follows the Ocoron Verbal Identity (see design system § Voice Across Surfaces for word budgets per surface type):

- Error messages: short, specific, actionable; avoid "invalid" — say what to fix and how.
- Use interaction-neutral verbs: "select" not "click" or "tap".
- Destructive confirmations: state the consequence in the body, not just the title.
- Empty states: explain why empty + provide a primary CTA + optional secondary doc link.
- Avoid jargon; write for the user's mental model, not the system's internals.

---

## Internationalization (i18n)

- Every scaffolded saas-skeleton project ships with `lib/i18n/` (React context provider + Next.js server helpers) and `public/i18n/en.json` (English source-of-truth). **Use these — do not install `next-intl`, `react-i18next`, or any third-party i18n library.**
- In Client Components: `const { t, formatDate } = useI18n();` from `@/lib/i18n/I18nProvider`.
- In Server Components: `const t = await serverT();` from `@/lib/i18n/server`.
- Language detection: `await detectLanguage()` reads cookie → Accept-Language header → defaults to `en`.
- Language switching: `<LanguageSwitcher />` from `@/lib/i18n/LanguageSwitcher` — sets cookie + reloads.
- Every user-visible string must use `t('key')` or `data-i18n` — no hardcoded English in JSX.
- Adding a language: copy `public/i18n/en.json` → `public/i18n/<lang>.json`, AI-translate, run `python scripts/validate_i18n.py --validate <lang>`.
- Locale-aware formatting: use `formatDate()`, `formatNumber()`, `formatCurrency()` from `useI18n()` — never hardcode date/number formats.
- For RTL support, multilingual rules, and formatting rules see `ocoron-design-system.md` § Multilingual and RTL + § Date/Time/Currency Formatting.
- See `docs/reference/multilingual-plan.md` for the full architecture, key naming convention, and anti-patterns.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Raw hex values or hardcoded colors | Design tokens (`--color-*`, `--surface-*`) or Tailwind theme |
| Hardcoded font names in CSS/JSX | Font tokens (`--font-heading`, `--font-body`, `--font-mono`) |
| `<link>` to Google Fonts CDN | `next/font` (self-hosted at build time) |
| Arbitrary pixel spacing | Token scale (`xs/sm/md/lg/xl/2xl`) |
| Box-shadows in dark mode | `1px solid var(--border)` |
| Bounce/spring animations | Design system motion tokens (`--motion-*`, `--ease-default`) |
| `console.log()` in production code | `pino` logger (see `55-observability.md`) |
| Marketing content shown to logged-in users | Gate on auth state; dashboard for authenticated |
| WebSocket for dashboards | 30s polling with `fetch` |
| `localStorage` / `sessionStorage` for auth tokens | HttpOnly cookies or Supabase SDK (see `35-security-auth.md`) |
| Custom auth components (NextAuth, Clerk) | FastAPI Pattern A or Supabase Auth Pattern B (see `35-security-auth.md`) |
| Hiding features from higher-tier plans | Soft gate: show locked + upgrade CTA |
| Infrastructure metrics visible to regular users | Admin-only dashboard section |
| Reinventing component primitives per page | Shared primitives composed into patterns |
| `next-intl` / `react-i18next` / third-party i18n | Scaffolded `lib/i18n/` |

---

## Related Rule Packs

- `ocoron-design-system.md` — single source of truth for all visual and verbal patterns (tokens, components, motion, density, tables, forms, charts, states, notifications, AI patterns, accessibility, multilingual, formatting, print/export)
- `35-security-auth.md` — auth patterns (Pattern A / B), CSP, CORS, token storage
- `55-observability.md` — no `console.log`, structured logging, health endpoints
- `86-email-templates.md` — email/notification template patterns (MJML+Jinja2)
- `88-saas-launch-checklist.md` — launch-blocking SaaS checklist (billing, legal, compliance)
- `95-multi-tenant-saas.md` — tenant isolation, RLS, tenant context propagation

---

## Done When

A UI component or page is done when all of the following are true:

- [ ] All enriched states implemented (loading, empty, error, permission denied, success, partial, disabled) per design system § States.
- [ ] Every form control has a programmatic label; errors are identified and suggest a fix.
- [ ] Focus is managed correctly in modals and overlays; keyboard-only flow works end-to-end.
- [ ] Lighthouse CI passes performance budgets (LCP, INP, CLS thresholds).
- [ ] No render-blocking resources on the initial route.
- [ ] Optimistic updates have a rollback path and a visible retry on failure.
- [ ] Microcopy follows Voice Across Surfaces word budgets and plain-language rules.
- [ ] Design tokens used throughout — no raw hex values, hardcoded fonts, or arbitrary spacing.
- [ ] Fonts loaded via `next/font` — no external CDN links.
- [ ] Motion follows design system duration/easing tokens — no arbitrary `transition` values.
- [ ] All user-visible strings use `t('key')` — no hardcoded English in JSX or templates.
- [ ] No `console.log()` in production code paths.
- [ ] Authenticated users never see marketing content on the homepage.
- [ ] Dashboard stat cards each answer a stated question; no card exceeds the 6-8 cap without progressive disclosure.
- [ ] Infrastructure metrics (queue depth, worker PIDs, proxy stats) are admin-only.
- [ ] Paywalled features show soft gate (locked + upgrade CTA), not hidden.
- [ ] Tenant context visible in nav; data is tenant-scoped; no cross-tenant leaks in UI.
