---
activation: glob
globs: ["**/extension/**", "**/content-script*.{js,ts}", "**/background.{js,ts}", "**/popup.{js,ts,html}", "**/sidepanel.{js,ts,html}"]
description: Chrome extension discipline — MV3, two-faced architecture, surfaces, distribution, auth, observability, design system
trigger: glob
currency_pass: 2026-10-02
---
<!-- CONSUMER: coding agents in a chrome-extension repo (the globs fire on its extension/ tree).
     GOAL: MV3 constraints, the two lanes, the three distribution channels, auth, observability, permissions.
     The planning layer is 00-domain-chrome-ext.md; launch steps are 89-extension-launch-checklist.md. -->

# Chrome Extension Rules

Apply when working on Chrome extension code (MV3). This is a **two-faced scaffold**: one repo holds the extension (`extension/`, browser-side) and its backend (`server/`, a FastAPI service on the VPS) — separate build and deploy units with different rules.

---

## Two-Faced Architecture

| Lane | Code | Deploy | Rules |
|---|---|---|---|
| **Extension (client)** | TypeScript + framework (Preact/Svelte/React), built with WXT | Chrome Web Store, developer-mode install, or enterprise force-install (§ Distribution Model) | This file |
| **Backend (server)** | Python (FastAPI) | VPS via `fabrik apply` (the registrars its spec's `shape:` declares) | `10-python.md`, `30-ops.md`, `55-observability.md` |

- The extension calls the backend via HTTPS. The backend is the scaffold's own `server/` service — Dockerfile, compose.yaml, Traefik labels and `/health` like any other Fabrik service; it ships with no database, no auth routes and no `/metrics` until the spec's `shape:` turns them on.
- The extension is NOT deployed via `fabrik apply` — it ships through one of the channels in § Distribution Model.
- The API contract between extension and backend is the bridge. Define versioned endpoints in the backend; the extension consumes them.

---

## Distribution Model

Pick the channel by audience **and by the permissions the product needs**. The Chrome Web Store is the default for reach. **Developer-mode install is a supported, first-class channel for an extension the store will not approve** (D-486): decide it at intake (`00-domain-chrome-ext.md` Fork 2) and build for it on purpose — it is not a fallback improvised after a rejection.

### Chrome Web Store

Public/consumer products: broad reach, zero install friction, automatic updates.

- **Permission rule:** the store admits only the narrowest permissions that serve the extension's single stated purpose. Broad host access (`<all_urls>`, `*://*/*`) and sensitive permissions (`debugger`, `tabs`, `cookies`, `webRequest`, …) are not banned, but each needs a justification and triggers a longer in-depth review — and a permission the stated purpose does not need is rejected.
- **Costs and assets:** a one-time developer fee, review that usually takes a few days and can take weeks, and the listing assets — all owned by `89-extension-launch-checklist.md` § 1. Developer account (one-time), § 3. Store listing assets and § 5. Review expectations & traps.
- **Auto-update:** the store updates installed copies automatically after each approved version.

### Developer-mode install (unpacked) — user-installed, off-store

The user turns on **Developer mode** at `chrome://extensions` and clicks **Load unpacked** on the unzipped build folder. It works on any desktop OS, with no review and no fee.

**Best for:** your own tools, a technical or internal audience, a private beta, or a product whose permissions the store will not admit for its purpose.

**What it lifts:** store review. Any permission the platform grants — `debugger`, broad host access, `nativeMessaging`, `proxy`, and the rest — is available without a store justification.

**What it does NOT lift — the MV3 platform rules apply to every channel:**

- Blocking `webRequest` (`webRequestBlocking`) is available only to policy-installed extensions; an unpacked one uses `declarativeNetRequest` like any other.
- Remotely hosted code is refused by the extension CSP itself, not by review (§ MV3 Constraints); the `userScripts` API is the sanctioned route, and it needs the per-extension "Allow User Scripts" toggle on the extension's details page.
- Manifest V2 no longer runs in current Chrome.

**What the channel costs, and what the build must do about it:**

- **It runs only while Developer mode stays on.** Chrome disables unpacked extensions whenever the toggle is off — say so in the install guide.
- **A managed browser can forbid it.** The `ExtensionDeveloperModeSettings` policy (and, when it is unset, `DeveloperToolsAvailability`) lets an admin turn developer mode off, so users on a company-managed Chrome may be unable to install. For them, use enterprise force-install.
- **No auto-update.** Chrome never auto-updates an unpacked extension, whatever `update_url` says. Ship the in-extension update checker (§ Versioning & Updates).
- **A stable ID needs a manifest `key`.** Without it every install gets a different ID and the backend's `chrome-extension://<id>` CORS allow-list breaks (§ Versioning & Updates).
- **One-time manual setup.** Ship an install guide (enable Developer mode → unzip → Load unpacked → pick the folder), with a short GIF.

**Distribution:** `wxt zip` builds the release zip (`.output/<name>-<version>-chrome.zip`); host it on your VPS (static site or B2) beside the install guide and a version manifest the update checker reads.

### Enterprise force-install — managed fleets

For a client's organisation or your own managed devices: the `ExtensionInstallForcelist` policy plus a hosted `updates.xml` (`update_url` in the manifest) and a packed `.crx`. It auto-updates, needs no user action, and a policy-installed extension may use blocking `webRequest`. The browser must be managed: on Windows, joined to Active Directory or Azure AD, or enrolled in Chrome Enterprise Core; on macOS, MDM-managed, joined to a domain via MCX, or enrolled in Chrome Enterprise Core.

### What does NOT work

One-click install of a self-hosted **packed `.crx`** from a download link — Chrome on Windows and macOS refuses off-store installs (Linux is the only platform that allows them). Do not build a "download our `.crx` and click to install" flow; use developer-mode install or enterprise force-install.

---

## MV3 Constraints

- Service workers replace background pages; do not use DOM or `window` APIs in the service worker.
- Service workers terminate on idle (~30s); never rely on in-memory globals for durable state.
- Package all executable code with the extension; never load remote executable code at runtime.
- CSP forbids `unsafe-eval` and inline scripts; keep all JavaScript in versioned files.

---

## Permissions Discipline

Request the narrowest permissions the extension's single purpose needs — the store requires it (§ Distribution Model), and a smaller grant is a smaller attack surface on every channel.

- **Request minimum permissions.** Justify every permission in a comment in `manifest.json`.
- **Prefer `activeTab` over `<all_urls>`.** `activeTab` grants access only when the user invokes the extension — no blanket host permission needed.
- **Use `optional_permissions`** for features the user may not need. Request at runtime with `chrome.permissions.request()` — just-in-time, with priming (explain why before the prompt). For the runtime-permission UX, use the fregante bloc: **`webext-permission-toggle`** (a context-menu toggle for optional host permissions), **`webext-dynamic-content-scripts`** (auto-register content scripts on newly-granted hosts), and **`webext-permissions`** (declared-vs-granted diffing). Don't hand-roll the grant→inject wiring.
- **`host_permissions`:** list only the specific domains the extension needs. Never `"<all_urls>"` unless the extension genuinely operates on every page.
- **`declarativeNetRequest`** is the MV3 API for request modification (blocking, redirecting, header modification). Use this instead of blocking `webRequest`, which MV3 keeps only for policy-installed extensions. Observe-only `webRequest` (no blocking) is still available. **Dynamic-rule limits:** `MAX_NUMBER_OF_DYNAMIC_RULES = 30000`, `MAX_NUMBER_OF_UNSAFE_DYNAMIC_RULES = 5000` (unsafe rules count toward the 30000). Update rules atomically via a single `updateDynamicRules({ addRules, removeRuleIds })` call — never a remove-then-add pair (leaves a gap).
- **Dangerous permissions** that trigger extra CWS review scrutiny: `debugger`, `proxy`, `vpnProvider`, `management`, `nativeMessaging`. Use only when absolutely required; document the justification. Developer-mode installs skip the review, not the MV3 platform rules (§ Distribution Model).

---

## Surface & Screen Inventory (minimum viable extension)

Every chrome extension ships these surfaces; the project-specific views come from its journeys (`/fabrik-flows`, `docs/flows.md`).

### Mandatory Surfaces

| Surface | File | Purpose | Notes |
|---|---|---|---|
| **Popup** | `entrypoints/popup/` | Single primary action. Closes on focus loss. | 400px width constraint. Never leave system in half-finished state. |
| **Options page** | `entrypoints/options/` | Full preferences and advanced configuration. | Always link to it from the popup. |

### Optional Surfaces (declare only when needed)

| Surface | File | Purpose | When to use |
|---|---|---|---|
| **Side panel** | `entrypoints/sidepanel/` | Persistent or multi-step work. | Only when `sidePanel` permission is declared. |
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
- Every surface follows the design system's compact adaptations (§ Design System (Compact) below).
- Core feature views are project-specific — `/fabrik-flows` defines them in `docs/flows.md`.
- Use **Shadow DOM** isolation for content-script overlays to avoid style collisions with the host page. Mount via WXT **`createShadowRootUi`** (returns a managed open shadow root). **`rem` caveat:** a shadow root does **not** reset `<html>` `font-size`, so `rem` units leak the host page's root size — use `px` (or set an explicit font-size on the shadow host) inside overlays. Wait for host elements with **`element-ready`** (MIT) rather than polling; for SPA route changes, patch the History API (`pushState`/`replaceState`) plus a `MutationObserver` — `popstate` alone misses in-app navigations.

---

## State Management

- Use `chrome.storage` as the cross-context source of truth across service worker, popup, side panel, and content scripts.
- **Typed settings/preferences via `@wxt-dev/storage`** (`defineItem` with types + versioned `migrations`) — the first-party option **on the default WXT build**; don't also pull in `webext-options-sync` there (redundant). On the `@crxjs` alternative build (no WXT), use `webext-options-sync` (or a typed wrapper over `chrome.storage`) for the same job.
- Persist all user-relevant state before the popup closes.
- Add Zustand only for local reactive UI state in React or Preact surfaces.
- Never store durable state in service-worker globals — the worker terminates.
- **Auth tokens** go in `chrome.storage.session` (in memory, cleared when the extension is disabled, reloaded or updated and when the browser restarts — the user re-authenticates after a restart). Never `chrome.storage.local` for tokens. See `35-security-auth.md`. **Access-level gotcha:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read it**. Keep tokens in the SW / extension-page (trusted) context and have content scripts reach them via **SW-mediated messaging** (`chrome.runtime.sendMessage`), not a direct `storage.session` read. Only widen with `setAccessLevel('TRUSTED_AND_UNTRUSTED_CONTEXTS')` if you *intend* content scripts to read it (rarely, for tokens — don't).

### Resilience against service-worker termination

The SW is *ephemeral* — design for termination, never fight it with keepalive-ping hacks (banned).

- **`chrome.offscreen`**: when you need a DOM / clipboard / audio API the SW lacks, create a hidden offscreen document (`chrome.offscreen.createDocument({ url, reasons, justification })`) rather than pinning the worker alive. It's the only sanctioned way to run DOM work "from" the SW.
- **`chrome.alarms`** for anything scheduled: the SW dies after ~30s idle, so `setTimeout` past that is lost. Use `chrome.alarms` (minimum period **30s / `periodInMinutes: 0.5`** for a packed extension; at most 500 active alarms) so the event fires even after the worker restarts.

---

## Auth (Extension ↔ Backend)

The extension authenticates with the backend per `35-security-auth.md`:

- **Pattern A (FastAPI sole IdP — default):** the extension calls the FastAPI backend (`fabrik-lib/fastapi-user-auth`) at `/auth/login` — the body-token shape; `/auth/login/web` is the cookie shape and is wrong here — receives an app-issued JWT in the JSON body, stores it in `chrome.storage.session`, and sends it via the `Authorization: Bearer` header on every API call. The extension talks to your FastAPI backend, never to a third-party auth SDK.
- **Passwordless sign-in (the DEFAULT — `35-security-auth.md` § Passwordless): use the OTP CODE path.**
  The user types the 6-digit code into the popup / side panel; the SW posts it to
  `/auth/passwordless/verify` and keeps the returned JWT in `chrome.storage.session` (content scripts
  read it via SW messaging, never directly). ⚠️ **A bare mailed magic LINK does not work here** — it
  opens in an ordinary tab that has no access to `chrome.storage.session`, so the session is minted
  somewhere the extension cannot see. If a link flow is genuinely wanted, it MUST go through
  `chrome.identity.launchWebAuthFlow` with the `https://<ext-id>.chromiumapp.org/` redirect below —
  same mechanism as social login, same user-gesture rule.
- **Federated OAuth (social login):** use `chrome.identity.launchWebAuthFlow` with **PKCE** — generate the `code_verifier` via `crypto.subtle`, keep it in `chrome.storage.session`, and use the extension's `https://<ext-id>.chromiumapp.org/` redirect URL. The **backend does the code-for-token exchange** (it holds the client secret) and returns the app JWT. **Start it from the user's click:** run `launchWebAuthFlow({ interactive: true })` from UI that explains what the sign-in is for, never at startup, and do the async PKCE prep (`crypto.subtle.digest`) *before* the click so nothing awaits between the click and the call. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`, etc.): they assume DOM / `localStorage` / iframes and break in the MV3 service worker.
- **Pattern B (Supabase Auth) — legacy only, migrate to Pattern A:** older extensions used `supabase-js` with a custom storage adapter wrapping `chrome.storage.session`. New work does NOT use `supabase-js`; the extension calls the FastAPI backend + `fabrik-lib/fastapi-user-auth` (Pattern A) with the JWT in `chrome.storage.session`. See `agents-fabrik.md § Supabase`.
- **CORS:** backend must include `chrome-extension://<id>` in `allow_origins`. Use `allow_origin_regex` in dev (ID changes per build); exact ID in production (from the store, or from the manifest `key` on the other two channels).
- **Never** store tokens in `localStorage`, `sessionStorage`, or `chrome.storage.local`. `chrome.storage.session` is the only acceptable location.

---

## Observability (Extension Side)

The backend gets observability per `55-observability.md` (structlog, `/health`, GlitchTip; `/metrics` when the spec sets `exposes_metrics`). The extension side:

- **Crash reporting:** `@sentry/browser` reporting to GlitchTip in the popup / options / side-panel (trusted extension pages) — the DSN is injected at build (`VITE_PUBLIC_SENTRY_DSN`), never hardcoded; remove `browserSessionIntegration` (the SDK's default session tracking), because GlitchTip does not support sessions. **In content scripts, NEVER call the global `Sentry.init`:** a content script shares the host page's `window`, so global-state integrations hijack the host page's errors. Build an **isolated `BrowserClient` + `Scope`** and drop the global-state integrations (`GlobalHandlers`, `Breadcrumbs`, `BrowserApiErrors`, `BrowserSession`, `ConversationId`, `FunctionToString`); wrap it with **`makeBrowserOfflineTransport`** so events buffer in IndexedDB and flush when the network returns. **Consequence:** dropping `GlobalHandlers` disables automatic uncaught-exception/rejection capture in the content script — you MUST report errors manually (`scope.captureException(e)` in your catch blocks), or content-script crashes vanish silently.
- **Product analytics (not just crashes):** ship first-party analytics via the **GA4 Measurement Protocol** (MV3-compliant — pure HTTP, no DOM) *or* **PostHog's core / no-external build** (session-replay/rrweb stripped). Either way, events must survive SW death: enqueue to a **`chrome.storage` queue and flush on a `chrome.alarms` tick**, never fire-and-forget from the SW (the request dies with the worker). Analytics stay **opt-out-gated** per the product's consent state.
- **Service worker telemetry:** MV3 service workers are ephemeral. Buffer logs to `chrome.storage.local` or `chrome.storage.session`, flush asynchronously to the backend via `navigator.sendBeacon()` or non-blocking `fetch`. See `55-observability.md` § Chrome Extension Telemetry.
- **No `console.log` in production.** Use the buffer-and-flush pattern. `console.log` is for development only.
- Handle `chrome.runtime.lastError` during I/O to prevent unhandled promise rejections from crashing the worker.

---

## AI & Content Extraction

For extensions that read the page or run LLM features:

- **LLM streaming lives in the side panel / an extension page, NOT the service worker.** The SW can be killed mid-stream and cannot hold a long-lived streaming connection; an extension page is also a *trusted* context, so it can read `chrome.storage.session`. Open the SSE/stream from the side panel.
- **No client-side LLM API keys — ever.** The backend owns provider keys and exposes an SSE streaming endpoint (the ai-kit wraps `ai-consult` / `rag`); the extension calls that, authenticated with the app JWT. A key in the bundle is a key you've shipped to every user.
- **Page → markdown** for LLM context: **`@mozilla/readability`** (Apache-2.0) to extract the article, then **`turndown`** (MIT) to convert to markdown. For screenshots, `chrome.tabs.captureVisibleTab`.

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

- **Default to WXT** (`wxt` — MIT, actively maintained; the scaffold uses it). It auto-generates the manifest, is cross-browser, `wxt zip` builds the release zip for every channel, and it ships first-party `@wxt-dev/storage` (typed settings + migrations) and `@wxt-dev/i18n`. It gives HMR and multi-entrypoint builds without hand-rolling `build.rollupOptions`.
- **Max-control alternative: Vite + `@crxjs/vite-plugin`** (MIT — actively maintained, **not** dead). Use it when the project needs full control of the Vite/Rollup config; then configure `build.rollupOptions` manual chunks for multi-entrypoint splitting yourself.
- **Do not** reach for Plasmo (Parcel-based, stalled) — not recommended for new work.
- **Build output dir differs by tool** — WXT emits `.output/<target>-mv3` for Chromium targets (e.g. `.output/chrome-mv3` from `wxt build`; a dev serve writes `chrome-mv3-dev`; Firefox and Safari default to `-mv2`); `@crxjs`/Vite emits `dist/`. Point the Playwright `--load-extension` fixture (§ Testing & UI Verification) at whichever your build tool actually produces — the fixture path is not portable between the two.
- Never ship production bundles that depend on `eval`-style development transforms.

---

## Testing & UI Verification

Extension surfaces (popup / options / side-panel / content-script overlay) are **web tech**, so the agent **reuses the web GUI loop** — `frontend-design` skill → shadcn MCP → build → **see** (Playwright MCP) → match the design system → `@axe-core/playwright` + `toHaveScreenshot` gate → `/design-review`, exactly as `docs/reference/gui-toolchain.md` and `saas/60-saas-ui.md` describe. The design system is unchanged: the same tokens as § Design System (Compact) (below). **MV3 forces exactly three additions** (full rationale + pinned versions: `docs/reference/research/chrome-ext-gui-research.md`):

- **Load the unpacked build via a Playwright test *fixture* — Playwright MCP alone cannot.** MCP drives an already-running browser; extensions load only through `chromium.launchPersistentContext('', { channel: 'chromium', args: ['--disable-extensions-except=<dist>', '--load-extension=<dist>'] })`. Read the extension ID from the MV3 service worker (`context.serviceWorkers()[0].url()`), then `page.goto('chrome-extension://<id>/popup.html' | 'options.html' | 'sidepanel.html')`. **Branded Chrome and Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags** — always launch Playwright's **bundled Chromium** via `channel: 'chromium'` (never installed stable Chrome), which is exactly what the persistent-context snippet above does. Keep `@playwright/test` current — recent releases keep the same service-worker handle across an MV3 restart (grounded in `docs/reference/research/chrome-ext-gui-research.md`). Content-script overlays: `goto` the host page, assert the injected Shadow-DOM node by stable `id`/`data-testid`. *(Optional: `vitest-environment-web-ext` when the project is on CRXJS + Vitest.)*
- **Run axe with `bypassCSP: true`, screenshot the popup at a pinned 400px viewport.** Extension CSP (`script-src 'self'`, no `unsafe-eval`) is non-relaxable and makes `@axe-core/playwright` throw on `chrome-extension://` pages unless the context is launched with `bypassCSP: true`. Pin `test.use({ viewport: { width: 400, height: 600 } })` so popup `toHaveScreenshot` baselines match the real popup box (a `goto`-ed popup otherwise renders at the tab viewport). axe pierces **open** shadow roots automatically — use `mode: 'open'` for overlays.
- **Gate bundle budgets with `size-limit` + `@size-limit/preset-app`.** § Bundle Budgets sets the numbers but names no tool: add a `.size-limit.json` entry per surface (popup / side-panel / content-script), each with its own `limit`; `size-limit --json` exits non-zero over budget — the machine-checked form of "verify bundle budgets before shipping."

**Nice-to-have (interactive debug, not the gate):** Chrome DevTools MCP `--category-extensions` (already user-global) — `install_extension` / `reload_extension` / `trigger_extension_action` + live service-worker console/perf, pointed at Chrome-for-Testing. Everything above is free / self-hostable; skip paid visual-diff SaaS (`toHaveScreenshot` covers it). GUI extension phases in a plan carry this loop per-surface, iterated to `found: 0, fixed: 0`, exactly as `/fabrik-ui-design` and `/fabrik-plan-review` require.

---

## Versioning & Updates

- **Chrome Web Store:** the manifest version follows semver; increment it on every submission. The store auto-updates users.
- **Enterprise force-install:** the manifest version + `update_url` pointing to your hosted `updates.xml`. Chrome checks periodically and auto-updates policy-installed copies.
- **Stable extension ID (developer-mode and enterprise channels):** pin a manifest **`key`** (the public key of a generated keypair) so the extension ID is identical across machines and rebuilds — otherwise the ID drifts and the backend's `chrome-extension://<id>` CORS allow-list breaks per install. Keep the private key out of the repo (secret).
- **In-extension update checker (dev-mode unpacked):** dev-mode / unpacked installs get **no auto-update**. Ship a checker that pings the backend for the latest version and surfaces an "update available" affordance linking to the new `.zip` — Chrome never auto-updates an unpacked extension — `update_url` is honoured only for store and policy installs.
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

## Design System (Compact)

Extension UI follows `core/design-system-template.md` — its slots and rules, with the brand values from the project's `docs/design-system.md` (Ocoron's only when the project declares it, D-051). The compact adaptations (tighter spacing, the single-column popup, popup navigation, pills, the 11px floor) are the chrome-extension row of template § Scaffold Adaptation Matrix; read them there. Both modes are mandatory and the brand decides the first-visit mode (template § Visual Rules). Extension-specific on top of the template:

- The popup's fixed 400px width makes every surface single-column; never a horizontal scroll.
- Content-script overlays respect `prefers-reduced-motion` and carry the design system's tokens inside their shadow root (`px`, never `rem` — § Surface & Screen Inventory).

---

## i18n

- The scaffold wires `@wxt-dev/i18n`: user-visible strings live in `extension/src/locales/<lang>.json`, and WXT generates `_locales/<lang>/messages.json` from them at build — edit the source files, never the generated ones.
- Read strings with `i18n.t('key')` in every surface; manifest strings use `__MSG_key__`, and a nested `a.b` key is `__MSG_a_b__` there.
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
| One-click self-hosted `.crx` download for consumer install | Developer-mode unpacked (`.zip` + install guide), enterprise force-install, or the store — off-store `.crx` install is refused on Windows and macOS |
| An unpacked or self-hosted build with no manifest `key` | Pin the `key` so the ID — and the backend's CORS allow-list — is stable on every machine |
| Blocking `webRequest` outside a policy install (MV3 keeps it only for policy-installed extensions) | `declarativeNetRequest` for request modification; observe-only `webRequest` is fine |
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
- `design-system-template.md` — token slots, component patterns, motion, accessibility
- `ocoron-design-system.md` — the house brand's values, for a project that declares it

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
- [ ] Every user-visible string is in `extension/src/locales/en.json` and `tr.json` (WXT generates `_locales/`).
- [ ] Permissions are minimal; each justified in manifest comments.
- [ ] Backend deploys via `fabrik apply` with the registrars its spec's `shape:` declares (`/health` always; `/metrics` only when `exposes_metrics`).
- [ ] Distribution path decided: **store** (listing assets ready, `89-extension-launch-checklist.md`), **developer-mode unpacked** (`wxt zip` release + install guide + version manifest hosted, manifest `key` pinned, in-extension update checker live), or **enterprise force-install** (`ExtensionInstallForcelist` + `updates.xml`, managed browsers only).
- [ ] Backend supports current and previous extension version simultaneously.

---

## Epic Decomposition → `00-domain-chrome-ext.md`

The PLANNING layer — vision intake (ICP, monetization, the permission-ceiling fork, unit economics, risk,
kill criteria) and the epic-decomposition directives — lives in **`.windsurf/rules/chrome-ext/00-domain-chrome-ext.md`**.
It is loaded by path by /fabrik-vision and /fabrik-epics, not by glob.

**This pack owns the code-time facts** (surfaces, MV3, permissions, build, testing, and § Distribution Model
above). The planner cites them; it never restates them. Keep it that way — the duplicate that used to live
here had already drifted into contradicting § Distribution Model.

## Draft Persistence — nothing typed or AI-generated is EVER lost (fleet mandate 2026-08-13)

Every form/wizard/editor/AI-populated surface persists its full working state **continuously on
change** (debounce ≤1s + flush on blur/hide/background) to `chrome.storage.local` (NEVER `storage.session` — it dies with the browser); **restore is automatic and
silent** on every return path (refresh, Back, reopened tab/app, crash, days-old session) — the
user continues down to the last letter typed. The draft clears on exactly ONE event: successful
creation/submission of the entity (or explicit user discard). Canonical detail:
`core/design-system-template.md` § Save Behavior.
