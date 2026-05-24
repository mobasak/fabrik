<!-- Chrome Extension Domain Module — loaded by 02-epic-decomposition-command
     when Vision Summary scaffold types include chrome-extension.
     Consumer: Traycer planning LLM (NOT coding agents).
     Coding agents use .windsurf/rules/chrome-ext/70-chrome-ext.md instead. -->

# Chrome Extension Domain Module

## The 3 Forks (do NOT inherit SaaS or mobile defaults here)

1. **Two-faced scaffold** — the extension (browser-side TS) and its backend (python-api on VPS) are separate build/deploy units. The backend follows the full 4-stage Fabrik lifecycle. The extension deploys via Chrome Web Store or direct CRX distribution — NOT Coolify.
2. **Distribution is gated** — Chrome Web Store review (1-3 business days), single-purpose rule, permission scrutiny. Or direct install (no review, no auto-update, limited to developer-mode users).
3. **400px fixed width** — popup/sidepanel is constrained to 400px. No responsive breakpoints. No RWD. The design system applies with tighter spacing.

## Mandatory Epic Patterns

When decomposing a chrome extension project into epics:

### Epic 1: Backend API + Auth (always first)
- FastAPI backend on VPS — standard python-api scaffold
- Auth: Supabase Auth (user-facing) or API key (internal tool)
- Shape block, registrars, health/metrics — full lifecycle
- The extension is useless without its backend

### Epic 2: Extension Core (depends on Epic 1)
- MV3 manifest, service worker, content scripts
- Popup/sidepanel UI (400px, Ocoron design tokens, tighter spacing)
- Communication with backend via HTTPS (API contract defined in Epic 1)
- Permissions strategy (least-privilege — CWS rejects over-broad permissions)

### Epic 3: Distribution + Polish
- Chrome Web Store listing assets (128px icon, 1280x800 screenshots, privacy policy)
- Or direct CRX packaging for internal tools
- Onboarding flow within extension
- Settings/preferences sync

## Technology Decisions (chrome-extension specific)

- **Auth:** Supabase Auth with `chrome.identity` API for OAuth flows, or shared API key for internal tools
- **Storage:** `chrome.storage.sync` for user preferences (synced across devices), backend PostgreSQL for application data
- **Billing:** Chrome Web Store payments (if CWS) OR Paddle web checkout opened in new tab (extension cannot embed payment forms). RevenueCat does NOT apply.
- **UI framework:** Preact (smallest bundle) or React (if shared with SaaS). Never full Next.js inside an extension.
- **Backend:** Standard python-api scaffold — same as any Fabrik service
- **Observability:** Backend gets full stack (Sentry, /health, /metrics). Extension gets Sentry browser SDK only.

## Constraints Specific to Chrome Extensions

- **Manifest V3 only** — V2 is dead. Service workers replace persistent background pages.
- **No remote code execution** — cannot `eval()` or load remote scripts. All code must be bundled.
- **Single-purpose rule (CWS)** — extension must do one stated thing. Feature bloat = rejection.
- **Permission justification** — every permission in manifest must be justified in CWS submission. Over-request = rejection.
- **Content Security Policy** — strict CSP enforced by MV3. No inline scripts, no external script loading.
- **5MB package limit** — extension ZIP must be under 5MB for CWS. Bundle size matters.
