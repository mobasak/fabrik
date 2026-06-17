<!-- Chrome Extension Domain Module — loaded by mega-epic-breakdown commands
     when Vision Summary scaffold types include `chrome-extension`:
       • 02-epic-decomposition-command — drives chrome-ext-specific epic patterns
         (backend API first, extension second, distribution channel chosen early).
       • 00-trigger-workflow-command Step E4 (EXISTING mode) — drives delta
         decisions when adding a chrome-extension to an existing project.
     Traycer reads this file from disk based on the Vision Summary's
     Technology Decisions § Scaffold types — no manual paste needed.
     Consumer: Traycer planning LLM (NOT coding agents).
     Coding agents use .windsurf/rules/chrome-ext/70-chrome-ext.md instead. -->

# Chrome Extension Domain Module

## The 3 Forks (do NOT inherit SaaS or mobile defaults here)

1. **Two-faced scaffold** — the extension (browser-side TS) and its backend (python-api on VPS) are separate build/deploy units. The backend follows the full 4-stage Fabrik lifecycle. The extension is distributed via Chrome Web Store, developer-mode unpacked ZIP, or enterprise force-install — NOT the VPS deploy pipeline (`fabrik apply` / SSH + Docker Compose).
2. **Distribution has 3 channels (pick one early)** — see Epic 3. Consumer one-click install of a self-hosted packed `.crx` is BLOCKED on Win/Mac (`CRX_REQUIRED_PROOF_MISSING`); do NOT plan around it.
3. **400px fixed width** — popup is constrained to 400px (sidepanel is wider but still narrow). No responsive breakpoints. No RWD. The design system applies with tighter spacing.

## Mandatory Epic Patterns

When decomposing a chrome extension project into epics:

### Epic 1: Backend API + Auth (always first)
- FastAPI backend on VPS — standard python-api scaffold
- Auth: Supabase Auth (user-facing) or API key (internal tool)
- Shape block, registrars, health/metrics — full lifecycle
- The extension is useless without its backend

### Epic 2: Extension Core (depends on Epic 1)
- MV3 manifest, service worker, content scripts
- **Mandatory surfaces:** popup (400px) + options page. Side panel + content-script overlays only when product needs them.
- Ocoron design tokens with compact adaptations (tighter spacing, 11px font floor)
- Communication with backend via HTTPS (API contract defined in Epic 1)
- Permissions strategy (least-privilege, `activeTab` over `<all_urls>`, `optional_permissions` for opt-in features — CWS rejects over-broad permissions; dev-mode bypasses this)
- Auth tokens stored in `chrome.storage.session` only (never `chrome.storage.local` / `localStorage`)

### Epic 3: Distribution + Polish — pick channel early, it shapes the build

Three legitimate channels; choose by audience:

| Channel | Audience | Auto-update | Permission ceiling | Listing assets needed |
| --- | --- | --- | --- | --- |
| **Chrome Web Store** | Public/consumer | Yes (hours after approval) | CWS-restricted (rejects `debugger`, broad host scraping, etc.) | 128px icon, 1280×800 screenshots (1-5), 440×280 tile, 132-char short description, privacy policy URL matching declared permissions |
| **Developer-mode unpacked ZIP** (host on VPS / B2) | Your own tools, technical users, internal/team, private beta, scraping extensions | No — ship `.zip` + reload instructions, or in-extension "update available" check | **Any permission** | Install GIF/README only |
| **Enterprise force-install** (`ExtensionInstallForcelist` Chrome policy + hosted `updates.xml`) | Managed fleets (client orgs, own devices) | Yes (policy-pushed) | Any permission | `updates.xml` + packed `.crx` hosted |

- **Do NOT** plan a "download `.crx` and click to install" flow for consumers — Chrome blocks it (`CRX_REQUIRED_PROOF_MISSING`).
- Onboarding flow within extension
- Settings/preferences sync

## Technology Decisions (chrome-extension specific)

- **Auth:** Supabase Auth with `chrome.identity` API for OAuth flows, or shared API key for internal tools. Tokens **MUST** live in `chrome.storage.session` (never `chrome.storage.local`, `localStorage`, or `sessionStorage`). Backend CORS must include `chrome-extension://<id>`. See `35-security-auth.md`.
- **Storage:** `chrome.storage.sync` for user preferences (synced across devices, small quota), `chrome.storage.local` for app data that must persist locally, backend PostgreSQL for canonical application data.
- **Billing:** Paddle web checkout opened in a new tab (extension cannot embed payment forms). Chrome Web Store payments API was deprecated by Google (Dec 2020) — do NOT plan around it. RevenueCat does NOT apply.
- **UI framework:** **Preact** (smallest bundle, popup-only), **Svelte** (medium-complexity spanning popup + options + content-script overlays — pair with Shadow DOM for overlay isolation), **React** only when sharing code with a SaaS app or for complex side-panel flows, **vanilla JS** for the absolute smallest scope. Never full Next.js inside an extension.
- **Build tooling:** Vite + `@crxjs/vite-plugin` (default — MV3-aware, HMR, multi-entrypoint). WXT/Plasmo only if the project already depends on them.
- **Backend:** Standard python-api scaffold — same as any Fabrik service.
- **Observability:** Backend gets full stack (Sentry, /health, /metrics, GlitchTip). Extension uses `@sentry/browser` in popup + content scripts; service-worker telemetry uses the buffer-and-flush pattern (logs to `chrome.storage.local`, flushed via `navigator.sendBeacon()` / non-blocking `fetch`) — no `console.log` in production.

## Constraints Specific to Chrome Extensions

- **Manifest V3 only** — V2 is dead. Service workers replace persistent background pages.
- **No remote code execution** — cannot `eval()` or load remote scripts. All code must be bundled.
- **Single-purpose rule (CWS)** — extension must do one stated thing. Feature bloat = rejection.
- **Permission justification** — every permission in manifest must be justified in CWS submission. Over-request = rejection.
- **Content Security Policy** — strict CSP enforced by MV3. No inline scripts, no external script loading.
- **Bundle size matters** — popup initial JS should land in the single-digit to low-tens KB gzip range; lazy-load options sections and heavy side-panel panes. Verify against build artifacts before shipping.
- **i18n from day 1** — `_locales/en/messages.json` + `chrome.i18n.getMessage()`. Day-1 languages: **en + tr**. Run `python scripts/chrome_messages.py` to sync `static/i18n/en.json` → flat `_locales/` format after every translation update.
