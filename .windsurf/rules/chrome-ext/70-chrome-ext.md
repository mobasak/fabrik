---
activation: glob
globs: ["**/extension/**", "**/content-script*.{js,ts}", "**/background.{js,ts}", "**/popup.{js,ts,html}", "**/sidepanel.{js,ts,html}"]
description: Chrome extension discipline — MV3, two-faced architecture, surfaces, distribution, auth, observability, design system
trigger: glob
---
<!-- CONSUMER: Coding agents building Chrome extensions
     GOAL: MV3 constraints, two-faced architecture, distribution, auth, observability, permissions
     TRAYCER USAGE: Injects as Context File for chrome-extension scaffold tickets.
     AGENT USAGE: Follow verbatim. Backend rules from 10-python/30-ops apply to the backend lane. -->

# Chrome Extension Rules

Apply when working on Chrome extension code (MV3). This is a **two-faced scaffold**: the extension (browser-side) and its backend (python-api on VPS) are separate build/deploy units with different rules.

---

## Two-Faced Architecture

| Lane | Code | Deploy | Rules |
|---|---|---|---|
| **Extension (client)** | TypeScript + framework (Preact/Svelte/React) | Chrome Web Store or direct install | This file |
| **Backend (server)** | Python (FastAPI) | VPS via `fabrik apply` (full registrar set) | `10-python.md`, `30-ops.md`, `55-observability.md` |

- The extension calls the backend via HTTPS. The backend is a standard `python-api` scaffold — same Dockerfile, compose.yaml, Traefik labels, `/health`, `/metrics` as any other Fabrik service.
- The extension binary is NOT deployed via `fabrik apply` — it goes through Chrome Web Store or direct CRX/ZIP distribution.
- The API contract between extension and backend is the bridge. Define versioned endpoints in the backend; the extension consumes them.

---

## Distribution Model

Pick the channel by audience — CWS for reach, developer-mode for control. Both are legitimate.

### Chrome Web Store

Public/consumer products: broad reach, zero install friction, automatic updates.

- **Costs:** review (1-3 business days), one-time $5 developer fee, permission scrutiny, single-purpose rule. Permissions CWS rejects (`debugger`, broad host access for scraping, etc.) are unavailable here.
- **Listing assets:** 128px icon, 1280x800 screenshots (1-5), 440x280 tile, 132-char short description, privacy policy URL matching declared permissions.
- **Auto-update:** CWS handles updates automatically. Users get the new version within hours of approval.

### Developer-mode install (unpacked) — user-installed, off-store

The user enables Developer mode at `chrome://extensions` and clicks **Load unpacked** on the extension folder. Available to any user on any desktop OS. Bypasses CWS entirely: no review, no fee, instant iteration, and **any permission you want** — including the ones CWS would reject.

**Best for:** your own tools, a technical user base, internal/team use, private beta, or scraping/automation extensions needing permissions CWS won't approve.

**Trade-offs (real, but not blockers):**

- **One-time manual setup** — enable dev mode → Load unpacked → pick folder. Ship a short GIF/README; fine for any willing or technical user.
- **No auto-update** — dev-mode extensions don't update themselves. Ship new versions as a downloadable `.zip` the user re-loads, or build an in-extension "update available" check that pings your backend and links to the new download.
- **Startup nag** — Chrome shows a "Disable developer-mode extensions" balloon on launch. Dismissible; suppressed entirely under enterprise policy.

**Distribution:** host the unpacked folder as a `.zip` on your VPS (static site / B2) with install instructions.

### Enterprise force-install — managed fleets

For a client's org or your own managed devices: `ExtensionInstallForcelist` Chrome Enterprise policy + hosted `updates.xml` (`update_url` in manifest). Auto-update, no nag, no user action. The packed `.crx` path works here because it's policy-pushed rather than user-clicked.

### What does NOT work

One-click install of a self-hosted **packed `.crx`** by clicking a download link — blocked on consumer Windows/Mac (`CRX_REQUIRED_PROOF_MISSING`). Do not build a "download our `.crx` and click to install" flow. Use developer-mode unpacked or enterprise force-install instead.

---

## MV3 Constraints

- Service workers replace background pages; do not use DOM or `window` APIs in the service worker.
- Service workers terminate on idle (~30s); never rely on in-memory globals for durable state.
- Package all executable code with the extension; never load remote executable code at runtime.
- CSP forbids `unsafe-eval` and inline scripts; keep all JavaScript in versioned files.

---

## Permissions Discipline

Chrome Web Store review is strict on permissions. Over-requesting = rejection or delay.

- **Request minimum permissions.** Justify every permission in a comment in `manifest.json`.
- **Prefer `activeTab` over `<all_urls>`.** `activeTab` grants access only when the user invokes the extension — no blanket host permission needed.
- **Use `optional_permissions`** for features the user may not need. Request at runtime with `chrome.permissions.request()` — just-in-time, with priming (explain why before the prompt). For the runtime-permission UX, use the fregante bloc: **`webext-permission-toggle`** (v6.0.1 — a context-menu toggle for optional host permissions), **`webext-dynamic-content-scripts`** (auto-register content scripts on newly-granted hosts), and **`webext-permissions`** (declared-vs-granted diffing). Don't hand-roll the grant→inject wiring.
- **`host_permissions`:** list only the specific domains the extension needs. Never `"<all_urls>"` unless the extension genuinely operates on every page.
- **`declarativeNetRequest`** is the MV3 API for request modification (blocking, redirecting, header modification). Use this instead of blocking `webRequest`, which MV3 removed for CWS extensions. Observe-only `webRequest` (no blocking) is still available. **Dynamic-rule limits (Chrome 121+):** `MAX_NUMBER_OF_DYNAMIC_RULES = 30000`, `MAX_NUMBER_OF_UNSAFE_DYNAMIC_RULES = 5000` (unsafe rules count toward the 30000). Update rules atomically via a single `updateDynamicRules({ addRules, removeRuleIds })` call — never a remove-then-add pair (leaves a gap).
- **Dangerous permissions** that trigger extra CWS review scrutiny: `debugger`, `proxy`, `vpnProvider`, `management`, `nativeMessaging`. Use only when absolutely required; document the justification. Developer-mode installs bypass CWS scrutiny — all permissions are available.

---

## Surface & Screen Inventory (minimum viable extension)

Every chrome extension ships these surfaces. Traycer derives additional project-specific views during `core-flows`.

### Mandatory Surfaces

| Surface | File | Purpose | Notes |
|---|---|---|---|
| **Popup** | `popup.html` | Single primary action. Closes on focus loss. | 400px width constraint. Never leave system in half-finished state. |
| **Options page** | `options.html` | Full preferences and advanced configuration. | Always link to it from the popup. |

### Optional Surfaces (declare only when needed)

| Surface | File | Purpose | When to use |
|---|---|---|---|
| **Side panel** | `sidepanel.html` | Persistent or multi-step work. | Only when `sidePanel` permission is declared. |
| **Content script overlay** | Injected via content script | UI overlaid on host page. | Mount with WXT `createShadowRootUi` (open shadow root); mind the `rem` caveat below. |

### Popup Screens (within the popup)

| Screen | Purpose |
|---|---|
| **Main view** | Primary action + status summary. Quick access to the extension's core function. |
| **Login / Auth** | Auth flow (if extension requires account). `chrome.storage.session` for tokens. |
| **Results / Output** | Display results of the primary action. |
| **Settings link** | One-tap to options page — not inline settings in the popup. |
| **Error state** | Clear error + retry. Never a blank popup. |

### Options Page Screens (within the options page)

| Screen | Purpose |
|---|---|
| **General settings** | API keys, backend URL, feature toggles. |
| **Account** | Logged-in user info, logout, data export, account deletion. |
| **Notifications** | Per-event notification preferences (if extension sends notifications). |
| **About** | Extension version, changelog link, support link, privacy policy. |

**Rules:**
- Popup + options page are launch-blocking — every extension ships both.
- Side panel only when the product requires persistent workspace (e.g., research tool, writing assistant).
- Content script overlays only when the extension modifies or augments host pages.
- Every surface follows the Ocoron Design System compact adaptations (see § Ocoron Design System below).
- Core feature views are project-specific — Traycer defines them during `core-flows`.
- Use **Shadow DOM** isolation for content-script overlays to avoid style collisions with the host page. Mount via WXT **`createShadowRootUi`** (returns a managed open shadow root). **`rem` caveat:** a shadow root does **not** reset `<html>` `font-size`, so `rem` units leak the host page's root size — use `px` (or set an explicit font-size on the shadow host) inside overlays. Wait for host elements with **`element-ready`** (v9.0.2, MIT) rather than polling; for SPA route changes, patch the History API (`pushState`/`replaceState`) plus a `MutationObserver` — `popstate` alone misses in-app navigations.

---

## State Management

- Use `chrome.storage` as the cross-context source of truth across service worker, popup, side panel, and content scripts.
- **Typed settings/preferences via `@wxt-dev/storage`** (`defineItem` with types + versioned `migrations`) — the first-party option **on the default WXT build**; don't also pull in `webext-options-sync` there (redundant). On the `@crxjs` alternative build (no WXT), use `webext-options-sync` (or a typed wrapper over `chrome.storage`) for the same job.
- Persist all user-relevant state before the popup closes.
- Add Zustand only for local reactive UI state in React or Preact surfaces.
- Never store durable state in service-worker globals — the worker terminates.
- **Auth tokens** go in `chrome.storage.session` (in-memory, cleared at session end — user must re-auth after browser restart). Never `chrome.storage.local` for tokens. See `35-security-auth.md`. **Access-level gotcha:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read it**. Keep tokens in the SW / extension-page (trusted) context and have content scripts reach them via **SW-mediated messaging** (`chrome.runtime.sendMessage`), not a direct `storage.session` read. Only widen with `setAccessLevel('TRUSTED_AND_UNTRUSTED_CONTEXTS')` if you *intend* content scripts to read it (rarely, for tokens — don't).

### Resilience against service-worker termination

The SW is *ephemeral* — design for termination, never fight it with keepalive-ping hacks (banned).

- **`chrome.offscreen`** (Chrome 109+): when you need a DOM / clipboard / audio API the SW lacks, create a hidden offscreen document (`chrome.offscreen.createDocument({ url, reasons, justification })`) rather than pinning the worker alive. It's the only sanctioned way to run DOM work "from" the SW.
- **`chrome.alarms`** for anything scheduled: the SW dies after ~30s idle, so `setTimeout` past that is lost. Use `chrome.alarms` (min period **30s / `periodInMinutes: 0.5`**, Chrome 120+; ≤500 active alarms, Chrome 117+) so the event fires even after the worker restarts.

---

## Auth (Extension ↔ Backend)

The extension authenticates with the backend per `35-security-auth.md`:

- **Pattern A (FastAPI sole IdP — default):** the extension calls the FastAPI backend (`fabrik-lib/fastapi-user-auth`) at `/auth/login/extension`, receives an app-issued JWT in the JSON body, stores it in `chrome.storage.session`, and sends it via the `Authorization: Bearer` header on every API call. The extension talks to your FastAPI backend, never to a third-party auth SDK.
- **Federated OAuth (social login):** use `chrome.identity.launchWebAuthFlow` with **PKCE** — generate the `code_verifier` via `crypto.subtle`, keep it in `chrome.storage.session`, and use the extension's `https://<ext-id>.chromiumapp.org/` redirect URL. The **backend does the code-for-token exchange** (it holds the client secret) and returns the app JWT. **Preserve the user gesture:** `launchWebAuthFlow({ interactive: true })` must fire from the user's click — do the async PKCE prep (`crypto.subtle.digest`) *before* the click, not between click and call, or Chrome may silently refuse to open the auth window once the gesture context is lost. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`, etc.): they assume DOM / `localStorage` / iframes and break in the MV3 service worker.
- **Pattern B (Supabase Auth) — legacy only, migrate to Pattern A:** older extensions used `supabase-js` with a custom storage adapter wrapping `chrome.storage.session`. New work does NOT use `supabase-js`; the extension calls the FastAPI backend + `fabrik-lib/fastapi-user-auth` (Pattern A) with the JWT in `chrome.storage.session`. See `AGENTS.md § Supabase`.
- **CORS:** backend must include `chrome-extension://<id>` in `allow_origins`. Use `allow_origin_regex` in dev (ID changes per build); exact ID in production (from CWS or crx key).
- **Never** store tokens in `localStorage`, `sessionStorage`, or `chrome.storage.local`. `chrome.storage.session` is the only acceptable location.

---

## Observability (Extension Side)

The backend gets full observability per `55-observability.md` (structlog, `/health`, `/metrics`, GlitchTip). The extension side:

- **Crash reporting:** `@sentry/browser` (v10.65.0) in the popup / options / side-panel (trusted extension pages) — DSN from extension config, not hardcoded. **In content scripts, NEVER call the global `Sentry.init`:** a content script shares the host page's `window`, so global-state integrations hijack the host page's errors. Build an **isolated `BrowserClient` + `Scope`** and drop the global-state integrations (`GlobalHandlers`, `Breadcrumbs`); wrap it with **`makeBrowserOfflineTransport`** so events buffer in IndexedDB and flush when the network returns. **Consequence:** dropping `GlobalHandlers` disables automatic uncaught-exception/rejection capture in the content script — you MUST report errors manually (`scope.captureException(e)` in your catch blocks), or content-script crashes vanish silently.
- **Product analytics (not just crashes):** ship first-party analytics via the **GA4 Measurement Protocol** (MV3-compliant — pure HTTP, no DOM) *or* **PostHog's core / no-external build** (session-replay/rrweb stripped). Either way, events must survive SW death: enqueue to a **`chrome.storage` queue and flush on a `chrome.alarms` tick**, never fire-and-forget from the SW (the request dies with the worker). Analytics stay **opt-out-gated** per the product's consent state.
- **Service worker telemetry:** MV3 service workers are ephemeral. Buffer logs to `chrome.storage.local` or `chrome.storage.session`, flush asynchronously to the backend via `navigator.sendBeacon()` or non-blocking `fetch`. See `55-observability.md` § Chrome Extension Telemetry.
- **No `console.log` in production.** Use the buffer-and-flush pattern. `console.log` is for development only.
- Handle `chrome.runtime.lastError` during I/O to prevent unhandled promise rejections from crashing the worker.

---

## AI & Content Extraction

For extensions that read the page or run LLM features:

- **LLM streaming lives in the side panel / an extension page, NOT the service worker.** The SW can be killed mid-stream and cannot hold a long-lived streaming connection; an extension page is also a *trusted* context, so it can read `chrome.storage.session`. Open the SSE/stream from the side panel.
- **No client-side LLM API keys — ever.** The backend owns provider keys and exposes an SSE streaming endpoint (the ai-kit wraps `ai-consult` / `rag`); the extension calls that, authenticated with the app JWT. A key in the bundle is a key you've shipped to every user.
- **Page → markdown** for LLM context: **`@mozilla/readability`** (v0.6.0, Apache-2.0) to extract the article, then **`turndown`** (v7.2.4, MIT) to convert to markdown. For screenshots, `chrome.tabs.captureVisibleTab`.

---

## Framework Choice

- Use **Preact** for minimal popup UIs where bundle size is the primary constraint.
- Use **Svelte** for medium-complexity extensions spanning popup, options, and content-script overlays.
- Use Shadow DOM with Svelte content-script overlays to isolate extension styles from the page.
- Use **React** only for complex side-panel or application-like flows, and split code aggressively.
- Use **vanilla JavaScript** and native Web APIs for the smallest possible scope.
- The UI framework is orthogonal to the build tool — **WXT works with any of the above** (or none).

---

## Bundle Budgets

- Keep popup initial JavaScript in the single-digit to low-tens KB gzip range.
- Keep the side-panel initial entry well below the typical React baseline by splitting route and feature chunks.
- Lazy-load options sections and heavy side-panel panes with dynamic imports.
- Verify bundle budgets by inspecting emitted build artifacts before shipping.

---

## Build Tooling

- **Default to WXT** (`wxt` — v0.20.27, MIT, actively maintained). It auto-generates the manifest, is cross-browser, and ships first-party `@wxt-dev/storage` (typed settings + migrations) and `@wxt-dev/i18n`. It gives HMR and multi-entrypoint builds without hand-rolling `build.rollupOptions`.
- **Max-control alternative: Vite + `@crxjs/vite-plugin`** (v2.7.1, MIT — actively maintained, **not** dead). Use it when the project needs full control of the Vite/Rollup config; then configure `build.rollupOptions` manual chunks for multi-entrypoint splitting yourself.
- **Do not** reach for Plasmo (Parcel-based, stalled) — not recommended for new work.
- **Build output dir differs by tool** — WXT emits `.output/<target>-mv3` (e.g. `.output/chrome-mv3`); `@crxjs`/Vite emits `dist/`. Point the Playwright `--load-extension` fixture (§ Testing & UI Verification) at whichever your build tool actually produces — the fixture path is not portable between the two.
- Never ship production bundles that depend on `eval`-style development transforms.

---

## Testing & UI Verification

Extension surfaces (popup / options / side-panel / content-script overlay) are **web tech**, so the agent **reuses the web GUI loop** — `frontend-design` skill → shadcn MCP → build → **see** (Playwright MCP) → match the design system → `@axe-core/playwright` + `toHaveScreenshot` gate → `/design-review`, exactly as `docs/reference/gui-toolchain.md` and `saas/60-saas-ui.md` describe. The design system is unchanged: the same Ocoron (Compact) tokens from § Ocoron Design System (below). **MV3 forces exactly three additions** (full rationale + pinned versions: `docs/reference/chrome-ext-gui-research.md`):

- **Load the unpacked build via a Playwright test *fixture* — Playwright MCP alone cannot.** MCP drives an already-running browser; extensions load only through `chromium.launchPersistentContext('', { channel: 'chromium', args: ['--disable-extensions-except=<dist>', '--load-extension=<dist>'] })`. Read the extension ID from the MV3 service worker (`context.serviceWorkers()[0].url()`), then `page.goto('chrome-extension://<id>/popup.html' | 'options.html' | 'sidepanel.html')`. **Stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139)** — always launch Playwright's **bundled Chromium** via `channel: 'chromium'` (never installed stable Chrome), which is exactly what the persistent-context snippet above does. Pin `@playwright/test` **≥1.59** (PR #39476 keeps the same service-worker handle across an MV3 restart — grounded in `docs/reference/chrome-ext-gui-research.md`). Content-script overlays: `goto` the host page, assert the injected Shadow-DOM node by stable `id`/`data-testid`. *(Optional: `vitest-environment-web-ext` when the project is on CRXJS + Vitest.)*
- **Run axe with `bypassCSP: true`, screenshot the popup at a pinned 400px viewport.** Extension CSP (`script-src 'self'`, no `unsafe-eval`) is non-relaxable and makes `@axe-core/playwright` throw on `chrome-extension://` pages unless the context is launched with `bypassCSP: true`. Pin `test.use({ viewport: { width: 400, height: 600 } })` so popup `toHaveScreenshot` baselines match the real popup box (a `goto`-ed popup otherwise renders at the tab viewport). axe pierces **open** shadow roots automatically — use `mode: 'open'` for overlays.
- **Gate bundle budgets with `size-limit` + `@size-limit/preset-app`.** § Bundle Budgets sets the numbers but names no tool: add a `.size-limit.json` entry per surface (popup / side-panel / content-script), each with its own `limit`; `size-limit --json` exits non-zero over budget — the machine-checked form of "verify bundle budgets before shipping."

**Nice-to-have (interactive debug, not the gate):** Chrome DevTools MCP `--category-extensions` (already user-global) — `install_extension` / `reload_extension` / `trigger_extension_action` + live service-worker console/perf, pointed at Chrome-for-Testing. Everything above is free / self-hostable; skip paid visual-diff SaaS (`toHaveScreenshot` covers it). GUI extension phases in a plan carry this loop per-surface, iterated to `found: 0, fixed: 0`, exactly as `/fabrik-ui-design` and `/fabrik-plan-review` require.

---

## Versioning & Updates

- **CWS distribution:** version in `manifest.json` follows semver. Increment on every CWS submission. CWS auto-updates users.
- **Direct install:** version in `manifest.json` + `update_url` pointing to your hosted `updates.xml`. Chrome checks periodically and auto-updates.
- **Stable extension ID (self-host branch):** pin a manifest **`key`** (the public key of a generated keypair) so the extension ID is identical across machines and rebuilds — otherwise the ID drifts and the backend's `chrome-extension://<id>` CORS allow-list breaks per install. Keep the private key out of the repo (secret).
- **In-extension update checker (dev-mode unpacked):** dev-mode / unpacked installs get **no auto-update**. Ship a checker that pings the backend for the latest version and surfaces an "update available" affordance linking to the new `.zip` — the `updates.xml` path only auto-updates CWS / enterprise-forcelist installs, not unpacked ones.
- **Backend backward-compat:** the backend must support the current and previous extension version simultaneously. Old extensions live on users' machines until they update. Never break an endpoint that a released extension calls.

---

## Accessibility

- Prefer native `<button>`, `<input>`, and `<select>` controls for built-in keyboard and screen-reader support.
- Keep keyboard focus visible on every surface, including popup, side panel, options, and overlays.
- Make custom widgets follow WAI-ARIA APG keyboard interaction patterns exactly.
- Ensure content-script overlays are keyboard reachable, dismissible, and return focus logically to the page.
- Animate only `transform` and `opacity`, and respect `prefers-reduced-motion`.
- Touch targets: 44px minimum in popup/side-panel surfaces.

---

## Ocoron Design System (Compact)

Chrome extension UI follows `ocoron-design-system.md` with compact adaptations:

- Tighter spacing: `--space-md: 12px`, `--space-sm: 6px`.
- Font size floor: 11px. No text smaller than this on any surface.
- 400px popup width constraint → single-column card layout.
- Tab bar maps to popup navigation (Inter 500, 11px, uppercase, accent underline for active).
- Pill pattern for tags/statuses.
- Load all three Ocoron fonts: Space Grotesk (headings), Inter (body/UI), JetBrains Mono (data displays only).
- Colors, surfaces, borders follow the standard Ocoron token set. Dark mode is the default.
- Component patterns (cards, tags, pills, buttons) follow canonical specs — scaled down in padding, not redesigned.
- Microcopy follows the Ocoron Verbal Identity: minimal, functional, outcome-first.
- Motion follows the design system motion tokens. Content-script overlays respect `prefers-reduced-motion`.

---

## i18n

- `_locales/en/messages.json` exists for all user-visible strings.
- For popup/options HTML, use `@wxt-dev/i18n`'s `t()` / `i18n.t()` — not a hand-rolled `data-i18n` loader.
- The adapter converts nested dot-path keys (e.g. `nav.home`) to Chrome's flat underscore format (`nav_home`).
- In extension code use `chrome.i18n.getMessage('nav_home')`.
- For popup/options HTML, the scaffolded `i18n.js` in `extension/src/` works with `data-i18n` attributes.
- Supported languages from day 1: **en** + **tr**. Add languages as markets require.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| DOM / `window` APIs in service worker | Chrome extension APIs (`chrome.storage`, `chrome.runtime`) |
| In-memory globals for durable state in service worker | `chrome.storage` (persists across worker restarts) |
| Remote code loading at runtime | Bundle all code with the extension |
| `eval` or `unsafe-eval` | Pre-compiled code in versioned files |
| `localStorage` / `sessionStorage` for auth tokens | `chrome.storage.session` |
| `<all_urls>` host permission when not needed | `activeTab` or specific domains |
| `console.log` in production | Buffer + flush to backend (see Observability) |
| Inline scripts in HTML pages | External `.js` files referenced via `<script src>` |
| Hardcoded backend URLs | Backend URL from `chrome.storage` config or env-injected at build |
| Breaking backend API endpoints after extension release | Support N and N-1 extension versions |
| One-click self-hosted `.crx` download for consumer install | Developer-mode unpacked (`.zip` + instructions), enterprise force-install, or CWS — consumer `.crx` click-install is blocked on Win/Mac |
| Blocking `webRequest` in CWS extensions (MV3 removed it) | `declarativeNetRequest` for request modification; observe-only `webRequest` is fine |
| Vendoring `ExtensionPay` / `ExtPay` (AGPL-3.0-or-later) for billing | Backend-enforced entitlements — a thin client that checks the app JWT's entitlement claim (never a copyleft billing lib in the shipped bundle) |
| Bundling `@axe-core/playwright` (MPL-2.0) into the shipped artifact | Dev-dependency only — a11y testing never ships in the production extension |
| Global `Sentry.init` in a content script (hijacks host-page errors) | Isolated `BrowserClient` + `Scope` + `makeBrowserOfflineTransport` (see § Observability) |
| Client-side LLM API keys in the bundle | Backend-owned keys; the extension calls the backend SSE endpoint with its app JWT |

---

## Related Rule Packs

- `10-python.md` — backend FastAPI patterns
- `20-typescript.md` — extension TypeScript discipline
- `30-ops.md` — backend Dockerfile, compose, `fabrik apply` deploy
- `35-security-auth.md` — auth patterns (Pattern A/B), CORS for `chrome-extension://` origins
- `55-observability.md` — backend logging + extension telemetry (Sentry, buffer-flush)
- `58-resilience.md` — backend external call resilience
- `ocoron-design-system.md` — visual tokens, component patterns, motion, accessibility

---

## Done When

- [ ] Service worker persists durable state to `chrome.storage` — no in-memory globals.
- [ ] No inline JavaScript or `eval` in any extension page.
- [ ] Popup renders its primary action synchronously.
- [ ] Auth tokens stored in `chrome.storage.session` — never `localStorage` or `chrome.storage.local`.
- [ ] Backend CORS includes the extension's `chrome-extension://<id>` origin.
- [ ] `@sentry/browser` initialized in popup/options/side-panel for crash reporting; content scripts use an isolated `BrowserClient` + `Scope` (never global `Sentry.init`).
- [ ] Service worker telemetry uses buffer + flush pattern (not `console.log`).
- [ ] All interactive controls are keyboard accessible and show visible focus.
- [ ] Bundle sizes checked against popup and side-panel budgets (`size-limit` gate, per surface).
- [ ] Each surface verified through the web loop + MV3 additions (§ Testing & UI Verification): Playwright load-extension fixture, `@axe-core/playwright` with `bypassCSP: true`, `toHaveScreenshot` at the pinned popup viewport.
- [ ] `_locales/en/messages.json` exists and synced with `static/i18n/en.json`.
- [ ] Permissions are minimal; each justified in manifest comments.
- [ ] Backend deploys via `fabrik apply` with full registrar set (`/health`, `/metrics`, GlitchTip).
- [ ] Distribution path decided: **CWS** (listing assets ready), **developer-mode unpacked** (`.zip` + install instructions hosted), or **enterprise force-install** (`ExtensionInstallForcelist` + `updates.xml`).
- [ ] Backend supports current and previous extension version simultaneously.

---

## Epic Decomposition → `00-domain-chrome-ext.md`

The PLANNING layer — vision intake (ICP, monetization, the permission-ceiling fork, unit economics, risk,
kill criteria) and the epic-decomposition directives — lives in **`.windsurf/rules/chrome-ext/00-domain-chrome-ext.md`**.
It is loaded by path from the mega-epic planner, not by glob.

**This pack owns the code-time facts** (surfaces, MV3, permissions, build, testing, and § Distribution Model
above). The planner cites them; it never restates them. Keep it that way — the duplicate that used to live
here had already drifted into contradicting § Distribution Model.
