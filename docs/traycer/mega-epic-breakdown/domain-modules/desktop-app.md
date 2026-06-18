<!-- Desktop Application Domain Module — loaded by mega-epic-breakdown commands
     when Vision Summary scaffold types include `desktop-app`:
       • 02-epic-decomposition-command — drives desktop-specific epic patterns
         (signing + distribution + standalone-vs-connected fork).
       • 00-trigger-workflow-command Step E4 (EXISTING mode) — drives delta
         decisions when adding a desktop client to an existing project.
     Traycer reads this file from disk based on the Vision Summary's
     Technology Decisions § Scaffold types — no manual paste needed.
     Consumer: Traycer planning LLM (NOT coding agents).
     Coding agents use .windsurf/rules/desktop-app/72-desktop.md instead. -->

# Desktop Application Domain Module

## The 3 Forks (do NOT inherit SaaS or mobile defaults here)

1. **Two-faced (when connected) or one-faced (when standalone)** — a desktop app is EITHER a fully standalone tool OR a desktop frontend to a Fabrik-deployed backend (python-api or node-api). The backend (if any) follows the full 4-stage Fabrik lifecycle. The desktop binary is NOT deployed via `fabrik apply` — it ships via direct download, store submission, or Linux package channels. **Decide standalone-vs-connected at intake; the architecture changes substantially.**
2. **Distribution is signed-or-rejected** — Windows SmartScreen and macOS Gatekeeper actively block unsigned binaries. Code signing is non-optional for any non-internal app. The 2026 cost structure was rewritten by Azure Trusted Signing ($9.99/mo).
3. **No responsive breakpoints** — desktop apps target windowed UI from ~800px to multi-monitor 5K. Ocoron design tokens apply, but RWD breakpoints from the web pack do NOT. Min window 800×600; design for resizable.

## Mandatory Epic Patterns

When decomposing a desktop-app project into epics:

### Epic 1: Decide Mode + Scaffold (always first)

- **Mode declaration** — **standalone** (no backend, offline-first) OR **connected** (Fabrik backend frontend). This is the single biggest architectural decision; nothing else can be planned without it.
- Electron 30+ + TypeScript + React 18 + Tailwind scaffold from `templates/desktop-app/`.
- Ocoron design system tokens wired (`core/ocoron-design-system.md` for visual/verbal identity).
- Process model from day 1: `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true` on every `BrowserWindow`; preload script + `contextBridge`; Zod schemas for every IPC handler.
- Single-instance lock (`app.requestSingleInstanceLock`); second-instance argv routing.
- Local storage: `better-sqlite3` + `better-sqlite3-multiple-ciphers` (SQLCipher).
- Credential storage: `safeStorage` (with explicit Linux fallback).

### Epic 2: Mode-Specific Core

**If standalone:**

- Offline-first state architecture (local SQLite is source of truth; optimistic UI off local reads).
- License management (RSA-SHA256 signed offline license file; embedded public key).
- (Optional) Local LLM: Ollama child process at `localhost:11434`. Document min hardware (e.g., 8 GB VRAM for Llama 3 8B q4). See `core/cost-budget.md` (Ollama replaces OpenRouter API spend for offline use cases).

**If connected (to Fabrik backend):**

- Backend epic — Fabrik python-api or node-api service deployed via `fabrik apply`. Full 4-stage lifecycle; follows `12-node.md` if Node, `10-python.md` if Python.
- OAuth via `shell.openExternal` → system browser → deep-link callback (`myapp://auth?token=...`). Embedded `<webview>` is banned (Google/MS/etc. block it).
- Sync architecture: optimistic UI + local mutation log + queue-and-replay. Conflict resolution: LWW per field (default) or CRDT (real-time multi-device) or OT (collaborative text).
- Real-time backend updates: SSE (default) > WebSockets > polling. Background work via OS push notifications, NOT hidden renderers.

### Epic 3: Distribution + Code Signing + Auto-Update

This epic is ALWAYS required (a desktop app that can't ship is not shipping).

- **Distribution channel(s)** picked from the table below (next section).
- **Code signing:**
  - Windows → **Azure Trusted Signing** ($9.99/mo) via `electron-builder` SignTool plugin.
  - macOS → Apple Developer ID ($99/yr) + Hardened Runtime + notarization via `xcrun notarytool`.
  - Linux → GPG-sign the AppImage.
- **Auto-update** via `electron-updater` with `provider: generic` pointing to **Cloudflare R2** public bucket (`pub-*.r2.dev`). Blockmap delta updates. GitHub Releases banned for private repos.
- **Apple Privacy Manifest** (`PrivacyInfo.xcprivacy`) for any macOS submission or notarized direct download.
- **Microsoft Store privacy declarations** if Store submission.

## Technology Decisions (desktop-app specific)

- **Framework:** **Electron 30+** (decided — do not reopen). Tauri and Wails evaluated and rejected for solo dev velocity reasons (Rust/Go context switching kills throughput; minor bundle savings don't compensate). The 150 MB Electron baseline is acceptable for professional/productivity tools when ASAR-packed.
- **Mode:** **standalone** OR **connected** (declare at Epic 1). Cannot defer.
- **Local storage:** `better-sqlite3` + SQLCipher via `better-sqlite3-multiple-ciphers`. NOT IndexedDB, NOT leveldb.
- **Credential storage:** `safeStorage` (replaces unmaintained `keytar`). Explicit Linux fallback handling required (Secret Service may be absent).
- **Auth (connected mode):** Supabase Auth via OAuth-in-system-browser → deep-link callback. Or M2M `X-Internal-Token` for headless integrations.
- **Backend (connected mode):** standard Fabrik python-api or node-api scaffold; same as any other Fabrik service.
- **Observability:**
  - Backend gets full stack (Sentry/GlitchTip, /health, /metrics, GlitchTip).
  - Desktop side uses `@sentry/electron` in BOTH main and renderer processes (initialised with `GLITCHTIP_DSN`).
  - Telemetry + crash reporting are **opt-in only** per KVKK.
- **UI framework:** React 18 + Tailwind (current scaffold default). Vue/Svelte not standard here.
- **Build tooling:** `electron-builder` (cross-platform packaging + signing + auto-update integration). Electron Forge is acceptable but `electron-builder` is the Fabrik default.
- **Real-time backend updates (connected):** SSE > WebSockets > polling.
- **Local LLM (standalone, optional):** Ollama child process at `localhost:11434`.

## Constraints Specific to Desktop Apps

- **Multi-process security:** `contextIsolation: true` + `nodeIntegration: false` + `sandbox: true` on every `BrowserWindow`. Missing any of these three IS a CVE.
- **IPC is the only main↔renderer bridge.** Validated with Zod schemas. Treat renderer as untrusted XSS-susceptible.
- **Code signing is non-negotiable** on Windows (SmartScreen) and macOS (Gatekeeper). Unsigned binaries are not viable.
- **OAuth via system browser only.** Embedded `<webview>` or `BrowserWindow` for OAuth is BANNED by major IdPs.
- **Encrypted local storage** via SQLCipher (KVKK compliance for sensitive local data).
- **No persistent hidden renderer for background sync** — battery + RAM cost is prohibitive; OS push notifications instead.
- **Apple Privacy Manifest required** for App Store AND notarized direct-download (since 2024).
- **KVKK opt-in telemetry default.** No foreign-cloud egress without consent.
- **Min window 800×600.** Design for resizable.

## Distribution Channel Decision Matrix (Epic 3)

Three legitimate channels; choose by audience. Multiple are common (direct download + Homebrew Cask, for example).

| Channel | Audience | Auto-update | Signing requirement |
| --- | --- | --- | --- |
| **Direct download (your domain)** | Default for solo dev; full control | Yes (electron-updater + R2) | Windows SmartScreen + macOS notarization + Linux GPG |
| **Mac App Store** | iCloud sync / IAP / family sharing apps | Yes (Apple manages) | Mac App Distribution cert + Hardened Runtime; review process |
| **Microsoft Store** | Enterprise / parental-controls reach | Yes (Store manages) | Microsoft Partner Center submission + review |
| **Homebrew Cask** (macOS power users) | Discovery for technical users | No auto; user runs `brew upgrade --cask` | Same signed `.dmg` as direct download |
| **winget** (Windows package manager) | Discovery for Windows power users | No auto; user runs `winget upgrade` | Same signed `.exe`/`.msi` as direct download |
| **Chocolatey** (Windows) | Same | No auto | Same |
| **AppImage** (Linux universal) | Default Linux | electron-updater can handle delta updates | GPG signature |
| **Flatpak** | Linux desktop distros | Flathub manages | Flathub signing |

## Code Signing Cost Matrix (2026)

| OS | Identity | Annual cost | Hardware token? |
| --- | --- | --- | --- |
| **Windows** | **Azure Trusted Signing** | **~$120 ($9.99/mo)** | No (cloud HSM) |
| Windows (legacy) | EV Certificate | $350–700 | Yes (USB token — avoid) |
| **macOS** | Apple Developer ID + notarization | $99 | No |
| **Linux** | GPG (free) | $0 | No |

**Total annual signing cost for a Win+Mac+Linux app: ~$219/yr** (Azure Trusted Signing $120 + Apple $99 + Linux $0). Document this in the Epic 3 budget line.

## Real-Time Architecture (Connected Mode)

For server-pushed updates from the Fabrik backend:

- **Default: SSE.** Simplest server-push over HTTPS; auto-reconnect via `Last-Event-ID`; lower battery than polling.
- **WebSockets** when bidirectional + low-latency. Close on window minimize.
- **Polling** banned for active background sync (Battery Saver / Low Power Mode throttle aggressively).

Backend side (Fastify/Express on `12-node.md`): SSE endpoint with reconnect support.

## Compliance Checklist (per Vision Summary)

Surface these in the Vision Summary's Constraints section:

- KVKK: telemetry opt-in only; no foreign cloud egress without consent; data residency declarations.
- Apple Privacy Manifest (`PrivacyInfo.xcprivacy`) for macOS submissions.
- Microsoft Store privacy declarations if Store submission.
- GDPR: same posture as KVKK (opt-in telemetry; data residency).
- Required Reason APIs (Apple): each native dep that touches them needs a justification code.

## Rule Packs (for coding agents, not Traycer)

- `desktop-app/72-desktop.md` — full Electron implementation discipline (process model, IPC, signing, R2 auto-update, safeStorage, SQLCipher, native integrations)
- `core/12-node.md` — main process is Node; runtime, lifecycle, structured logging
- `core/20-typescript.md` — TS-specific patterns (auto-loads on `.ts`)
- `core/ocoron-design-system.md` — design tokens for React/Tailwind UI
- `core/45-testing-strategy.md` — Playwright at the E2E peak; vitest at the unit base
- `core/55-observability.md` — Sentry/GlitchTip dual-process; KVKK opt-in
- `core/cost-budget.md` — Ollama as offline alternative to OpenRouter API spend
- For connected mode also: `core/10-python.md` OR `core/12-node.md` (backend), `core/35-security-auth.md`, `core/58-resilience.md`

---

## Epic-Decomposition Defaults

When this domain module loads, Traycer's epic decomposition should default to:

| Epic | Always required? | Notes |
| --- | --- | --- |
| Epic 1: Mode + Scaffold | Yes | Includes process-model security from day 1 |
| Epic 2a: Standalone core (offline-first SQLite, license validation, optional Ollama) | If standalone | Skip if connected |
| Epic 2b: Connected core (backend + OAuth + sync + real-time) | If connected | Skip if standalone |
| Epic 3: Distribution + Signing + Auto-Update | Yes | Win + Mac + Linux unless explicitly scoped down |
| Epic 4: Native integrations (deep-links, tray, autostart, dock badges) | If product needs them | Optional but cheap once Epic 1 is done |
| Epic 5: Compliance (Apple Privacy Manifest, KVKK opt-in flows, store privacy declarations) | Yes if submitting to stores | Always if KVKK applies |
| Epic 6: Testing (Playwright E2E + vitest unit) | Yes | Mock OS dialogs via `electronApp.evaluate()` |

Single-epic visions are rare for desktop apps — Epic 1 + Epic 3 are nearly always separate.
