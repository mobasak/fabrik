---
activation: always_on
description: SaaS UI patterns — navigation, components, performance, accessibility
trigger: always_on
---

# SaaS UI Rules

Apply these rules when working on frontend/UI code (Next.js, TypeScript, React, Tailwind). Skip for Python, Docker, and infrastructure files.

## Ocoron Design System

- All SaaS UI projects must follow the Ocoron Design System (`docs/reference/ocoron-design-system.md`) as the single source of truth for visual and verbal identity.
- **Design tokens:** Use CSS custom properties (`--color-*`, `--surface-*`, `--text-*`) or their Tailwind theme equivalents. Never use raw hex values, arbitrary colors, or hardcoded font names.
- **Typography:** Space Grotesk for headings (600–700 weight), Inter for body/UI (400–500), JetBrains Mono for code/data (300–400). No substitutions. No additional fonts.
- **Dark mode is the default.** Light mode is opt-in via `[data-theme="light"]` CSS override. All components must render correctly in dark mode first.
- **No box-shadows in dark mode.** Use `1px solid var(--border)` for elevation. Subtle shadows (`0 1px 3px rgba(0,0,0,0.08)`) allowed in light mode only.
- **Component patterns** (cards, tags, pills, buttons, tabs, progress bars) follow the canonical specs in the design system. Do not reinvent or create alternative patterns without proposing an addition to the design system first.
- **Spacing** uses the token scale (`xs/sm/md/lg/xl/2xl`). No arbitrary pixel values.
- **Transitions** are `0.15s ease`. No bouncy animations, no spring physics.
- **Microcopy** follows the Ocoron Verbal Identity: lead with outcomes, use specifics over adjectives, no forbidden language (see Forbidden Language table in the design system).

## Navigation

- Use a stable side nav for structural destinations; reserve top nav for global utilities (search, help, profile, notifications).
- Add breadcrumbs when the IA is hierarchical; add recents/starred when task-switching is frequent.
- Never bury primary tasks behind deep nav hierarchies; apply progressive disclosure for secondary pages.

## Component Hierarchy

- Follow the token -> primitive -> component -> pattern -> page layering: components consume design tokens, never raw values.
- Implement each primitive (`Button`, `Text`, `Icon`, `Stack`) once; compose into `FormField`, `Table`, `Modal`, `Toast` - never re-implement behaviors like focus management or error handling at the page level.
- Default to Server Components in Next.js; add `'use client'` only for hooks, browser APIs, or event handlers.

## Required States

Every interactive component must handle all five states before it is considered done:

- **Empty** - explain why empty + offer a primary CTA.
- **Loading** - non-blocking skeleton or spinner; never a blank screen.
- **Error** - inline near the field; plain language; specific and actionable; preserve entered data.
- **Success / Saved** - visible confirmation ("Saved.") near the action; non-blocking.
- **Disabled** - visually distinct; never silently unresponsive.

## Performance Budgets

- Core Web Vitals targets (p75 field): LCP <= 2.5 s, INP <= 200 ms, CLS <= 0.1.
- No render-blocking CSS/JS on the initial route; inline critical CSS, defer the rest.
- Apply route-level code splitting; lazy-load admin-only or rarely used UI (for example, heavy modals).
- Static assets (JS/CSS/fonts) must have explicit `Cache-Control`; user-specific API responses must not be publicly cached.

## Accessibility

- Target WCAG 2.2 AA as the baseline - non-negotiable.
- Every form control must have a programmatic `<label>` association.
- Keyboard focus must remain visible and not be obscured by sticky headers/sidebars/modals (WCAG 2.4.11).
- Interactive touch targets must meet WCAG 2.5.8 minimum size or spacing.
- Modals: trap focus, support Escape, use `role="dialog"` with `aria-modal="true"`.
- Tooltips: use `role="tooltip"` + `aria-describedby` on the trigger; support keyboard dismiss.
- Do not block autofill or password managers (WCAG 3.3.8).
- Never use ARIA incorrectly - no ARIA is better than bad ARIA.

## Optimistic UI

- Apply optimistic updates only where rollback is safe and the failure path is handled.
- Pattern: optimistic update -> show "Saving..." -> confirm "Saved" on server ACK -> on failure, revert state and show a retryable inline error with preserved user intent.
- Never silently swallow mutation failures.

## Microcopy

- All user-facing text follows the Ocoron Verbal Identity (see design system). Key rules:

- Error messages: short, specific, actionable; avoid "invalid" - say what to fix and how (for example, "Enter an email in the format name@company.com").
- Use interaction-neutral verbs: "select" not "click" or "tap".
- Destructive confirmations: state the consequence in the body, not just the title (for example, "Apps using this key will stop working.").
- Empty states: explain why empty + provide a primary CTA + optional secondary doc link.
- Avoid jargon; write for the user's mental model, not the system's internals.

## Done When

A UI component or page is done when all of the following are true:

- [ ] All five required states are implemented (empty, loading, error, success, disabled).
- [ ] Every form control has a programmatic label; errors are identified and suggest a fix.
- [ ] Focus is managed correctly in modals and overlays; keyboard-only flow works end-to-end.
- [ ] Lighthouse CI passes performance budgets (LCP, INP, CLS thresholds).
- [ ] No render-blocking resources on the initial route.
- [ ] Optimistic updates have a rollback path and a visible retry on failure.
- [ ] Microcopy follows plain-language and action-oriented rules above.
