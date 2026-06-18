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
- **Use `optional_permissions`** for features the user may not need. Request at runtime with `chrome.permissions.request()` — just-in-time, with priming (explain why before the prompt).
- **`host_permissions`:** list only the specific domains the extension needs. Never `"<all_urls>"` unless the extension genuinely operates on every page.
- **`declarativeNetRequest`** is the MV3 API for request modification (blocking, redirecting, header modification). Use this instead of blocking `webRequest`, which MV3 removed for CWS extensions. Observe-only `webRequest` (no blocking) is still available.
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
| **Content script overlay** | Injected via content script | UI overlaid on host page. | Use Shadow DOM isolation for style safety. |

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
- Use **Shadow DOM** isolation for content-script overlays to avoid style collisions with the host page.

---

## State Management

- Use `chrome.storage` as the cross-context source of truth across service worker, popup, side panel, and content scripts.
- Persist all user-relevant state before the popup closes.
- Add Zustand only for local reactive UI state in React or Preact surfaces.
- Never store durable state in service-worker globals — the worker terminates.
- **Auth tokens** go in `chrome.storage.session` (in-memory, cleared at session end — user must re-auth after browser restart). Never `chrome.storage.local` for tokens. See `35-security-auth.md`.

---

## Auth (Extension ↔ Backend)

The extension authenticates with the backend per `35-security-auth.md`:

- **Pattern A (FastAPI sole IdP):** extension calls `/auth/login/extension`, receives JWT in JSON body, stores in `chrome.storage.session`, sends via `Authorization: Bearer` header on every API call.
- **Pattern B (Supabase Auth):** extension uses `supabase-js` with a custom storage adapter wrapping `chrome.storage.session`. Token refresh handled by the SDK.
- **CORS:** backend must include `chrome-extension://<id>` in `allow_origins`. Use `allow_origin_regex` in dev (ID changes per build); exact ID in production (from CWS or crx key).
- **Never** store tokens in `localStorage`, `sessionStorage`, or `chrome.storage.local`. `chrome.storage.session` is the only acceptable location.

---

## Observability (Extension Side)

The backend gets full observability per `55-observability.md` (structlog, `/health`, `/metrics`, GlitchTip). The extension side:

- **Crash reporting:** `@sentry/browser` in popup and content scripts. DSN from extension config, not hardcoded.
- **Service worker telemetry:** MV3 service workers are ephemeral. Buffer logs to `chrome.storage.local` or `chrome.storage.session`, flush asynchronously to the backend via `navigator.sendBeacon()` or non-blocking `fetch`. See `55-observability.md` § Chrome Extension Telemetry.
- **No `console.log` in production.** Use the buffer-and-flush pattern. `console.log` is for development only.
- Handle `chrome.runtime.lastError` during I/O to prevent unhandled promise rejections from crashing the worker.

---

## Framework Choice

- Use **Preact** for minimal popup UIs where bundle size is the primary constraint.
- Use **Svelte** for medium-complexity extensions spanning popup, options, and content-script overlays.
- Use Shadow DOM with Svelte content-script overlays to isolate extension styles from the page.
- Use **React** only for complex side-panel or application-like flows, and split code aggressively.
- Use **vanilla JavaScript** and native Web APIs for the smallest possible scope.

---

## Bundle Budgets

- Keep popup initial JavaScript in the single-digit to low-tens KB gzip range.
- Keep the side-panel initial entry well below the typical React baseline by splitting route and feature chunks.
- Lazy-load options sections and heavy side-panel panes with dynamic imports.
- Verify bundle budgets by inspecting emitted build artifacts before shipping.

---

## Build Tooling

- Default to **Vite** with `@crxjs/vite-plugin` for MV3-aware builds, HMR, and multi-entrypoint support.
- Use WXT or Plasmo only when the project already depends on them or their abstractions are required.
- Configure `build.rollupOptions` manual chunks for multi-entrypoint bundle splitting.
- Never ship production bundles that depend on `eval`-style development transforms.

---

## Versioning & Updates

- **CWS distribution:** version in `manifest.json` follows semver. Increment on every CWS submission. CWS auto-updates users.
- **Direct install:** version in `manifest.json` + `update_url` pointing to your hosted `updates.xml`. Chrome checks periodically and auto-updates.
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
- i18n source JSON at `static/i18n/en.json` is in sync with `_locales/` — run `python scripts/chrome_messages.py` after every translation update.
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
- [ ] `@sentry/browser` initialized in popup/content scripts for crash reporting.
- [ ] Service worker telemetry uses buffer + flush pattern (not `console.log`).
- [ ] All interactive controls are keyboard accessible and show visible focus.
- [ ] Bundle sizes checked against popup and side-panel budgets.
- [ ] `_locales/en/messages.json` exists and synced with `static/i18n/en.json`.
- [ ] Permissions are minimal; each justified in manifest comments.
- [ ] Backend deploys via `fabrik apply` with full registrar set (`/health`, `/metrics`, GlitchTip).
- [ ] Distribution path decided: **CWS** (listing assets ready), **developer-mode unpacked** (`.zip` + install instructions hosted), or **enterprise force-install** (`ExtensionInstallForcelist` + `updates.xml`).
- [ ] Backend supports current and previous extension version simultaneously.
