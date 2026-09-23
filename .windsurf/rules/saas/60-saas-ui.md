---
activation: glob
globs: ["**/*.tsx", "**/*.jsx", "**/tailwind.config.*", "**/app/globals.css"]
description: SaaS UI patterns — navigation, components, dashboards, performance, billing UI, tenant UI, i18n
trigger: glob
currency_pass: 2026-09-23
---
<!-- CONSUMER: Coding agents building SaaS frontend (Next.js/React)
     GOAL: SaaS UI patterns — navigation, dashboards, billing UI, tenant UI, performance, i18n
     AGENT USAGE: Follow verbatim when building SaaS UI components and pages. -->

# SaaS UI Rules

Apply when working on frontend/UI code (Next.js, React, Tailwind). Skip for Python backend logic, Docker, infrastructure files, and email templates (see `86-email-templates.md`).

---

## Design-first workflow + verification (the pipeline this pack plugs into)

UI is **designed and its truth frozen BEFORE it is built**, then **verified against that truth** — not improvised per ticket:

1. **Freeze the fields** — `/fabrik-data-contract` → `docs/data-contract.md` (every GUI field ↔ its DB column). A screen never shows a field absent from this file.
2. **Freeze the screens** — `/fabrik-ui-design` → `docs/ui-design.md` (design-system-FIRST, then screen inventory + **minimal-click flows with a click budget** + IA + per-screen components/states/field-mapping). Build every screen against it verbatim; invent no screen/flow/component not listed.
3. **Build with the toolchain** — see `docs/reference/gui-toolchain.md` (hub) for the verified stack: **shadcn MCP** (install real components, don't hand-write markup), the **`frontend-design`** skill (anti-slop: tokens + signature element + self-critique before CSS), and this design system for tokens/components.
4. **Verify each built screen — a blocking loop to a no-op** (the UI analogue of `/fabrik-review`): **Playwright MCP** (open the running screen, read the a11y tree, click the flow, screenshot 375/768/1440) → the a11y/visual/token gate (`@axe-core/playwright` + `toHaveScreenshot` + design-token lint) → **`/design-review`**. Every finding FIXED or REFUTED; iterate until `found: 0, fixed: 0`. The scaffold emits none of this gate's devDeps (`@playwright/test`, `@axe-core/playwright`, `@lhci/cli`) or its configs — installing them is a named first ticket in the plan, since a deps-file edit needs a ticket's authority.

The rules below are the *standards* the frozen design and the verification enforce.

---

## The design system — a resolution LADDER, never a silent default (operator ruling 2026-08-29)

House brands are not forced on every SaaS — brand gravity is scaffold gravity's twin (a product
that looks like the house because nobody chose otherwise). Resolve, in order:

1. **The project's own `docs/design-system.md`, sourced from a brand-identiy-creator full identity**
   — the mandate for every UI-bearing project. The kit's `For-Your-Developer/Design-Tokens/`
   (tokens.css + tokens.json, dual-mode) seeds it; the SaaS-app extension set (semantic/state
   colors, component patterns, contrast table, density, data-viz) comes from BIC as it ships or is
   authored in the project's `design-system.md` against the BIC brand tokens.
2. **Missing → a NAMED BLOCKING step at 2-contract**: "generate the identity via
   brand-identiy-creator" — the pipeline stops there by name; never fall through silently.
3. **`ocoron-design-system.md` (web) / `tojlo-design-system.md` (mobile) are HOUSE identities a
   project EXPLICITLY declares** — one header line in its `docs/design-system.md` ("House identity:
   ocoron — chosen, not defaulted"). Interim hybrid while BIC's app-extension set matures: BIC
   brand tokens + ocoron's STRUCTURAL scale (spacing/density/motion patterns as framework), declared
   as interim — brand from BIC, skeleton from the house, never the house BRAND by accident.

**Component toolchain (the skin/structure split):** **shadcn** (via the wired MCP) is STRUCTURE and
behavior — install real components, never hand-write markup; the project's design system is the
SKIN — tokens restyle everything, which is exactly why per-project brands and shadcn compose.
**magicui** (wired MCP) is motion/marketing accents, inside the motion-token budget. ⚠️ **Both are
for the SaaS's OWN UI only — never for artifacts the product GENERATES for its customers** (produced
sites, exported pages): those carry the CUSTOMER's brand and their own weight budget, and inheriting
our component stack couples every customer artifact to our toolchain.

Key points for agents (token discipline — binding whichever system resolves):

- **Design tokens:** the resolved system's tokens (`tokens.css`) are mapped INTO the scaffold's shadcn semantic variables (`--background`, `--foreground`, `--primary`, `--muted`, `--border`, …) in `app/globals.css` — brand tokens feed shadcn's names; never rename shadcn's variables (every installed component reads them). The scaffold stores them as HSL channel triplets (`221 83% 53%`) read through `hsl(var(--x))`, so convert a brand hex to channels (or switch the Tailwind mapping to `var(--x)` with full colours) — a hex assigned to an `hsl()`-wrapped variable silently renders nothing. Tailwind theme values live in `tailwind.config.*` on the JS-config majors (what the scaffold emits — read `package.json` first) and in `@theme` CSS variables on the CSS-first major, which auto-detects no JS config. Never raw hex values, arbitrary colors, or hardcoded font names in components.
- **Typography, default mode, elevation and voice come from the RESOLVED design system** — never from this pack. Judging a BIC-branded product against the house identity is itself a finding (D-051).
- **Both dark and light mode are mandatory.** Resolve the mode as `localStorage`, else the resolved system's first-visit rule (ocoron: OS `prefers-color-scheme`, dark when the OS states none), with a manual toggle in Settings. Switch with ONE hook on `<html>` — the scaffold's Tailwind `darkMode: ["class"]` + `.dark`, or `data-theme="dark|light"` with `darkMode: ['selector', '[data-theme="dark"]']` (an ocoron project uses `data-theme`, which its CSS keys on) — set BEFORE first paint by an inline pre-hydration script (or `next-themes`), with `<html suppressHydrationWarning>`; a `localStorage` read after hydration flashes the wrong theme.
- **When the resolved system is the house web identity (ocoron):** Space Grotesk (headings), Inter (body/UI), JetBrains Mono (code/data) with no substitutions; dark is the default; no box-shadows in dark mode — a 1px border instead (`border border-border` on the scaffold's shadcn mapping) — except the modal overlay shadow `ocoron-design-system.md` itself specifies.
- **Component patterns** (cards, tags, pills, buttons, tabs, progress bars, KPI cards, data tables, forms) follow the canonical specs. Do not reinvent.
- **Motion, spacing and density** follow the resolved system's scales — the names below are ocoron's, for a project that declares ocoron or the interim hybrid. Motion follows the duration scale (`--motion-fast` through `--motion-deliberate`) and easing tokens; no bounce, no spring physics outside celebrations (ocoron § Motion Language).
- **Spacing** uses the token scale (ocoron: `xs/sm/md/lg/xl/2xl`). No arbitrary pixel values.
- **Density modes** (ocoron: Comfortable/Compact/Spacious) apply to data-heavy views (ocoron § Density Modes).
- **States** — every interactive component handles all enriched states (loading, empty, error, permission denied, success, partial success, disabled). See design system § States.
- **Microcopy** follows the resolved system's verbal identity (ocoron: its Verbal Identity and Voice Across Surfaces table).

### Font Loading (Next.js)

The example loads the house identity's three families; load the resolved system's families the same way.

```typescript
// app/layout.tsx
import { Space_Grotesk, Inter, JetBrains_Mono } from 'next/font/google';
import { detectLanguage, loadTranslations, SUPPORTED } from '@/lib/i18n/server';
import { I18nProvider } from '@/lib/i18n/I18nProvider';

const spaceGrotesk = Space_Grotesk({ subsets: ['latin'], variable: '--font-heading', display: 'swap' });
const inter = Inter({ subsets: ['latin'], variable: '--font-body', display: 'swap' });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono', display: 'swap' });

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const lang = await detectLanguage();
  const { strings, fallback } = loadTranslations(lang);
  return (
    <html lang={lang} suppressHydrationWarning className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrainsMono.variable}`}>
      <body>
        <I18nProvider lang={lang} strings={strings} fallback={fallback} supported={SUPPORTED}>{children}</I18nProvider>
      </body>
    </html>
  );
}
```

The scaffold's own `app/layout.tsx` mounts no `I18nProvider`, and `useI18n()` throws outside one — wiring it is part of the first UI ticket. MERGE the example into that layout rather than replacing it: keep its `./globals.css` import, `metadata` and `<Toaster />`, and map the font variables in `tailwind.config.*` (`fontFamily: { heading: ['var(--font-heading)'], body: ['var(--font-body)'], mono: ['var(--font-mono)'] }`) with `font-body` on `<body>`, or the fonts load and nothing uses them.

`next/font` self-hosts the fonts at build time — no external CDN requests, no GDPR concern, optimal loading. Never use `<link>` to Google Fonts CDN.

---

## Page Inventory (minimum viable SaaS)

Every SaaS project must ship these pages. The plan (`/fabrik-plan-after-chat`) maps each to a ticket.

### Public (unauthenticated)

| Page | Route | Purpose |
|---|---|---|
| **Landing / marketing** | `/` | Value proposition + CTA. Never shown to authenticated users. |
| **Pricing** | `/pricing` | All tiers side-by-side, feature matrix, annual/monthly toggle. |
| **Login** | `/login` | FastAPI login (Pattern A, default — `fabrik-lib/fastapi-user-auth`). Legacy Supabase Auth (Pattern B) only if the project already runs on it. |
| **Signup** | `/signup` | Registration. After email verification the user lands in the app — `/app/onboarding` while onboarding is neither completed nor dismissed, else `/app`. |
| **Verify email** | `/verify-email` | *(password auth only)* "Check your email" — shown after signup. Displays sent-to address, resend button, change email link. User cannot enter the app until verified. Under passwordless: keep as a REDIRECT to `/login`, never a 404. |
| **Forgot password** | `/forgot-password` | *(password auth only)* Email input → triggers reset flow. Under passwordless there is no password to reset — redirect to `/login`. |
| **Reset password** | `/reset-password` | *(password auth only)* Token-validated form. Expires in 1h. Under passwordless: redirect to `/login`. |
| **Magic-link states** | `/login?reason=invalid\|wrong-browser` | *(passwordless only)* The fleet IdP (`fastapi-user-auth`) generates NO link — its email carries a bare token and it has no base-URL setting — and its `GET /auth/passwordless/verify?token=…&mode=web` answers with JSON: `401` for unknown / expired / used (deliberately indistinguishable) and `403` for a browser that did not start the login (`binding_mismatch`, `core/35-security-auth.md`). So the project serves `/auth` from the app's OWN host (a Traefik `PathPrefix(`/auth`)` route to the backend, or a Next.js rewrite — the IdP's `__Host-` session cookies are host-only, so a separate IdP origin can never carry the session to the frontend), builds the link on that host, installs the module's `CsrfOriginMiddleware` (web mode requires it; the scaffold's `main.py` does not add it), and maps the `401`/`403` to these two frontend states — say what happened and offer "request a new link". A mail client is often where a user first arrives, so these states are frequently the FIRST page they see. |

⚠️ **The three *(password auth only)* rows above are NOT launch-blocking for a passwordless project.** The default
IdP this pack names — `fabrik-lib/fastapi-user-auth` (Pattern A in `core/35-security-auth.md`) —
ships `passwordless_enabled: bool = True` (`settings.py:38`), so treating `/forgot-password` as a
required page contradicts the fleet's own default auth module. Read the project's auth mode first;
`/signup` and `/verify-email` stay as REDIRECTS under passwordless rather than 404s, because links
to them survive in old emails and bookmarks (passwordless signs a new user up on their first login, so `/signup`
has no form to show).

### Legal (public, launch-blocking)

| Page | Route | Why |
|---|---|---|
| **Terms of Service** | `/terms` | Required before accepting payment (see `88-saas-launch-checklist.md`). |
| **Privacy Policy** | `/privacy` | Required by GDPR/KVKK + payment processors. |
| **Cookie Policy** | `/cookies` | EU ePrivacy (`88-saas-launch-checklist.md` Phase 1). |
| **Cookie consent** | banner, all locales | Opt-in, never assumed (`88-saas-launch-checklist.md` Phase 1). |

### Authenticated (core app)

Routes follow the saas-skeleton scaffold: the app lives under `/app` (route group `app/(app)/app/`), settings under `/app/settings/`. Never add a parallel `/dashboard`. The scaffold ships ONE `/app/settings` placeholder page — split it into the sub-routes below and replace its in-app "Upgrade to Pro" card with Paddle Overlay Checkout for a first upgrade and the portal session for an existing subscription (`core/85-payments-billing.md`).

| Page | Route | Purpose |
|---|---|---|
| **Dashboard** | `/app` | Actionable overview: KPI cards, quick actions, recent activity. See § Dashboard Design below. |
| **[Core feature pages]** | `/app/[domain]/*` | Project-specific — the product's primary workflow. Defined per epic. |
| **Settings — Profile** | `/app/settings/profile` | Display name, email (change triggers verification), avatar, locale, timezone. |
| **Settings — Organization** | `/app/settings/organization` | Org name, slug, logo, default currency, timezone, billing email. See § Multi-Tenant UI. |
| **Settings — Team** | `/app/settings/team` | Member list, invite, role management. See § Multi-Tenant UI. |
| **Settings — Billing** | `/app/settings/billing` | Current plan, next billing date, usage. Invoices, payment method, cancel and plan changes go to the Paddle-hosted customer portal through a session the backend mints per click (`POST /customers/{customer_id}/portal-sessions`) — never stored, cached or iframed (`core/85-payments-billing.md`). See § Billing & Subscription UI. |
| **Settings — Notifications** | `/app/settings/notifications` | Per event-type × channel toggle (email, in-app, push). |
| **Settings — Sessions** | `/app/settings/sessions` | Active sessions list, revoke individual sessions. |
| **Onboarding** | `/app/onboarding` | A contextual checklist or 3-step wizard (`88-saas-launch-checklist.md`). First-time only, dismissible, tracks completion. See `88-saas-launch-checklist.md`. |

### Admin (admin role only)

| Page | Route | Purpose |
|---|---|---|
| **Admin dashboard** | `/admin` | System health: worker status, queue depth, error rates. Its own hostname with `shape.is_admin_dashboard: true` there (Authelia 2FA); never that registrar on the public app domain — its rule is per-domain, so it would put `/`, `/pricing` and `/login` behind 2FA too. An in-app admin needs a second factor the fleet IdP does not have yet (`fastapi-user-auth` ships none), and any cross-tenant read a scoped role — never BYPASSRLS on the public app (`95-multi-tenant-saas.md`). |
| **Admin — Users** | `/admin/users` | User management, impersonation (if needed). |

**Rules:**
- Every page in the public section must exist before go-live — these are launch-blocking.
- Settings pages ship in Phase 2 (first 30 days) per `88-saas-launch-checklist.md`.
- Admin pages are admin-role gated — regular users see nothing (hidden, not disabled).
- Core feature pages are project-specific — the spec and plan define them (`/fabrik-spec` → `/fabrik-plan-after-chat`), not this pack.

---

## Navigation

- Use a stable side nav for structural destinations; reserve top nav for global utilities (search, help, profile, notifications).
- Add breadcrumbs when the IA is hierarchical; add recents/starred when task-switching is frequent.
- Never bury primary tasks behind deep nav hierarchies; apply progressive disclosure for secondary pages.

---

## Authenticated vs Public Homepage

**Separate routes, not auth-gated same route:**

- `/` is always the public landing page (marketing, value proposition, pricing CTA). May be a separate static deploy.
- `/app` is always the authenticated app entry point. Logged-in users never see `/`.
- **Login redirects to `/app`.** After successful auth (login, signup + verify, magic link, OAuth callback), redirect to `/app` (or `/app/onboarding` while onboarding is neither completed nor dismissed), never to `/`. The fleet IdP's magic-link redirect defaults to `/` (`fastapi-user-auth` `web_login_redirect`) — set `AUTH_WEB_LOGIN_REDIRECT` in the BACKEND's env (the scaffold's root `.env.example` is frontend-only) and `docs/CONFIGURATION.md` — `/app`, which resolves on the app's own host once `/auth` is served there (see § Page Inventory (minimum viable SaaS), the magic-link row).
- **Unauthenticated `/app` access redirects to `/login`.** The request proxy catches this — read the `next` major in `package.json` first: `middleware.ts` on majors before the Proxy rename, `proxy.ts` after it — the scaffold's pin predates the rename (see `core/35-security-auth.md` on a leftover `middleware.ts`), with a matcher that excludes `_next/*` — UX redirect only, not a security gate: every Server Component and Server Function still verifies the session itself (see `35-security-auth.md` § Next.js Defense-in-Depth).
- Never show marketing content to authenticated users. Never render the landing page inside the app shell.

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

- Poll dashboard status every 30s — `router.refresh()` for server-rendered widgets, SWR or `useEffect` + `fetch` for client widgets — and pause while the tab is hidden. This is what production SaaS tools use.
- Do NOT use WebSocket for dashboards — the complexity is not justified for data that changes every few seconds.
- Reserve WebSocket for: real-time chat, collaborative editing, live notifications that must appear within 1s. If the data can be 30s stale, poll.
- Never reload the full page.

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

- Current plan, next billing date and usage, shown in-app.
- Invoices, payment method, plan changes and cancellation go through the Paddle customer portal — a session the backend creates per click; never build custom billing-management UI (`core/85-payments-billing.md`). That is the Paddle lane; TRY lanes follow `core/85` (PayTR one-off payments have no portal).
- Before handing off to cancel, state the consequence clearly, offer the alternatives the plan allows (downgrade, pause), and require explicit confirmation.

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
- Admin-only nav items visible only to Admin/Owner roles. See `35-security-auth.md` (Pattern A default) for role definitions.

---

## Optimistic UI

- Apply optimistic updates only where rollback is safe and the failure path is handled.
- Pattern: optimistic update → show "Saving..." → confirm "Saved" on server ACK → on failure, revert state and show a retryable inline error with preserved user intent.
- Never silently swallow mutation failures.

---

## Responsive Design (Mandatory)

**Every SaaS page must be responsive from 375px to 2560px. No exceptions.** For the full breakpoint system, grid, and component behavior rules, see `ocoron-design-system.md` § Responsive Layout (RWD1–RWD10). Key points for SaaS:

- **Mobile-first CSS.** Base styles target smallest viewport; `sm:`, `md:`, `lg:` layer up. Never write `max-width` queries (`max-*` variants included) as the base layout.
- **Sidebar:** full (240px) at `lg:` (1024px+), icon rail (56px) at `md:` (768px), hidden + hamburger below `md:`. The scaffold's `components/shell/AppShell.tsx` is a placeholder (a persistent 240px column from `md:`, no hamburger) — replace it in the first UI ticket.
- **Data tables:** transform to card list OR horizontal scroll with sticky first column below `md:`. Unmodified desktop tables on phone viewports are banned.
- **Modals:** become full-screen sheets below `sm:` (640px).
- **Dashboard grids:** 1 column below `sm:`, 2 columns at `md:`, 3-4 columns at `lg:`.
- **Test at 375px, 768px, 1440px** before every UI merge. Untested responsive = broken responsive. For the full testing process (Playwright automation, screenshot workflow, fix patterns, common mistakes), see `docs/reference/mobile-responsive-testing-guide.md`.

---

## Performance Budgets

- Core Web Vitals targets (p75 field): LCP <= 2.5s, INP <= 200ms, CLS <= 0.1.
- Initial route: no third-party render-blocking scripts, fonts through `next/font`, and a small route CSS chunk — judged by the LCP budget, not by "zero render-blocking resources" (Next.js emits route CSS as stylesheets; its CSS inlining is experimental).
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
- Login never makes the user solve, recall or transcribe something (WCAG 3.3.8): allow paste, password managers and OTP autofill, with `autocomplete` on auth fields (`email`, `one-time-code`, …; WCAG 1.3.5).
- Never ask for the same information twice in one flow (WCAG 3.3.7, Level A) — onboarding pre-fills what signup collected.
- Never use ARIA incorrectly — no ARIA is better than bad ARIA.

---

## Microcopy

All user-facing text follows the resolved system's verbal identity (for ocoron, § Voice Across Surfaces sets word budgets per surface type):

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
- Every user-visible string must use `t('key')` — no hardcoded English in JSX (`data-i18n` attributes are for static HTML pages served by the i18n kit's JS loader, not React).
- Adding a language: copy `public/i18n/en.json` → `public/i18n/<lang>.json`, AI-translate, then validate:
  - `python scripts/validate_i18n.py` — Level 1: structural checks (missing keys, placeholder mismatches, empty values). Free, instant.
  - `python scripts/validate_i18n.py --validate <lang>` — Level 2 + 3 (back-translation, native-speaker critique) shell out to the Kilo CLI and a `kilo/…` model, a toolchain the fleet has retired (D-364) — never make them a gate; Level 1 is the gate. Review a new locale by hand (or with `claude -p`) until the validator is ported.
  - Full i18n kit (validate script, `_context.json`, snippets, JS loader): `templates/i18n-kit/` (hub — the copy `scaffold.py` seeds; `templates/scaffold/i18n-kit/` is an older, divergent copy).
- Locale-aware formatting: use `formatDate()`, `formatNumber()`, `formatCurrency()` from `useI18n()` — never hardcode date/number formats.
- For RTL support, multilingual rules, and formatting rules see `ocoron-design-system.md` § Multilingual and RTL + § Date/Time/Currency Formatting.
- See `templates/i18n-kit/docs/multilingual-plan.md` (hub — the copy `scaffold.py` actually seeds; landed in projects as `docs/reference/multilingual-plan.md`) for the full architecture, key naming convention, and anti-patterns.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Raw hex values or hardcoded colors | Semantic tokens (the scaffold's shadcn variables, fed by the resolved system) or the Tailwind theme |
| Hardcoded font names in CSS/JSX | Font tokens (`--font-heading`, `--font-body`, `--font-mono`) |
| `<link>` to Google Fonts CDN | `next/font` (self-hosted at build time) |
| Arbitrary pixel spacing | The resolved system's spacing scale (ocoron: `xs/sm/md/lg/xl/2xl`) |
| Box-shadows in dark mode (house identity) | A 1px border (`border border-border`) |
| Bounce/spring animations | The resolved system's motion tokens (ocoron: `--motion-*`, `--ease-default`) |
| `console.log()` in production code | `pino` on the server (Server Components, route handlers); client code surfaces errors through the error boundary and toast, never the console (see `55-observability.md`) |
| Marketing content shown to logged-in users | Gate on auth state; dashboard for authenticated |
| WebSocket for dashboards | 30s polling with `fetch` |
| `localStorage` / `sessionStorage` for auth tokens | HttpOnly cookies (Pattern A default; legacy Supabase SDK) — see `35-security-auth.md` |
| Custom auth components (NextAuth, Clerk) | FastAPI Pattern A (default); legacy Supabase Auth Pattern B only if already on it (see `35-security-auth.md`) |
| Hiding features from higher-tier plans | Soft gate: show locked + upgrade CTA |
| Infrastructure metrics visible to regular users | Admin-only dashboard section |
| Reinventing component primitives per page | Shared primitives composed into patterns |
| `next-intl` / `react-i18next` / third-party i18n | Scaffolded `lib/i18n/` |
| Desktop-only layouts (no responsive breakpoints) | Mobile-first CSS with `sm:`/`md:`/`lg:` breakpoints (see design system § Responsive Layout) |
| Unmodified desktop data tables on mobile viewports | Card transformation (Pattern A) or horizontal scroll with sticky column (Pattern B) |
| Floating modals on viewports < 640px | Full-screen sheet pattern |
| Persistent full sidebar on viewports < 1024px | Collapsed icon rail (768px+) or hamburger (below 768px) |

---

## Related Rule Packs

- `ocoron-design-system.md` — the house web identity (brand, voice, fonts) for a project that DECLARES it (D-051), and the structural reference every project may use for components, motion, density, tables, forms, charts, states, notifications, AI patterns, accessibility, **responsive layout RWD1-RWD10**, multilingual, formatting and print/export
- `35-security-auth.md` — auth patterns (Pattern A / B), CSP, CORS, token storage
- `55-observability.md` — no `console.log`, structured logging, health endpoints
- `86-email-templates.md` — email/notification template patterns (MJML+Jinja2)
- `88-saas-launch-checklist.md` — launch-blocking SaaS checklist (billing, legal, compliance)
- `95-multi-tenant-saas.md` — tenant isolation, RLS, tenant context propagation
- `/opt/fabrik-lib/docs-site/` — vendor this Docusaurus template for the project's documentation site (user guide, API ref, pricing, FAQ, legal pages). Do not build from scratch.

---

## Done When

A UI component or page is done when all of the following are true:

- [ ] All enriched states implemented (loading, empty, error, permission denied, success, partial, disabled) per design system § States.
- [ ] Every form control has a programmatic label; errors are identified and suggest a fix.
- [ ] Focus is managed correctly in modals and overlays; keyboard-only flow works end-to-end.
- [ ] Lighthouse CI passes the lab budgets (LCP, CLS, and TBT as the responsiveness proxy — a navigation run cannot measure INP); INP is confirmed at p75 in field data, or in a Lighthouse user-flow/timespan run before launch.
- [ ] No third-party render-blocking scripts on the initial route; LCP within budget.
- [ ] Optimistic updates have a rollback path and a visible retry on failure.
- [ ] Microcopy follows the resolved system's verbal identity (ocoron: Voice Across Surfaces word budgets) and plain-language rules.
- [ ] Design tokens used throughout — no raw hex values, hardcoded fonts, or arbitrary spacing.
- [ ] Fonts loaded via `next/font` — no external CDN links.
- [ ] Motion follows design system duration/easing tokens — no arbitrary `transition` values.
- [ ] All user-visible strings use `t('key')` — no hardcoded English in JSX or templates.
- [ ] `python scripts/validate_i18n.py` passes clean (Level 1: no MISSING_KEY, no PLACEHOLDER_MISMATCH, no EMPTY_VALUE across all locale files). Run after any ticket that adds or changes UI strings.
- [ ] No `console.log()` in production code paths.
- [ ] Authenticated users never see marketing content on the homepage.
- [ ] Page tested and functional at 375px, 768px, and 1440px — no horizontal overflow, no broken layouts.
- [ ] Sidebar collapses to icon rail at `md:` and hides behind hamburger below `md:`.
- [ ] Data tables use card transformation or sticky-column scroll on mobile viewports.
- [ ] Modals render as full-screen sheets below `sm:` (640px).
- [ ] Both dark and light mode functional. First visit follows the resolved system's rule (ocoron: OS `prefers-color-scheme`, dark when none); manual toggle in Settings; preference persists in `localStorage`; no theme flash on first paint.
- [ ] Dashboard stat cards each answer a stated question; no card exceeds the 6-8 cap without progressive disclosure.
- [ ] Infrastructure metrics (queue depth, worker PIDs, proxy stats) are admin-only.
- [ ] Paywalled features show soft gate (locked + upgrade CTA), not hidden.
- [ ] Tenant context visible in nav; data is tenant-scoped; no cross-tenant leaks in UI.

## Draft Persistence — nothing typed or AI-generated is EVER lost (fleet mandate 2026-08-13)

Every form/wizard/editor/AI-populated surface persists its full working state **continuously on
change** (debounce ≤1s + flush on blur/hide/background) to durable browser storage (`localStorage`/IndexedDB); **restore is automatic and
silent** on every return path (refresh, Back, reopened tab/app, crash, days-old session) — the
user continues down to the last letter typed. The draft clears on exactly ONE event: successful
creation/submission of the entity (or explicit user discard). Key every draft by user, tenant and entity
(`<userId>:<tenantId>:<entity>:<id|new>`), purge a user's drafts on logout and org switch, and never persist
secrets or card fields — a shared browser must never restore someone else's draft. Canonical detail:
`core/ocoron-design-system.md` § Save Behavior — except the key and the purge above, which win until that
section is corrected (backlog FILE 26).
