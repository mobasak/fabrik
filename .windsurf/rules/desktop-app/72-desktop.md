---
activation: glob
globs: ["**/electron/**", "**/renderer/**", "**/electron-builder*", "**/forge.config*", "**/preload.{js,ts}"]
description: Electron 30+ desktop app — process model, IPC zero-trust, code signing (Azure Trusted Signing / Apple notarization), R2 auto-update, native integrations, KVKK
trigger: glob
---
<!-- CONSUMER: Coding agents (Claude Code, Windsurf Cascade, Kilo CLI)
     GOAL: Electron 30+ desktop application patterns — process isolation, IPC validation, distribution, code signing, auto-update, local storage, OS integrations
     TRAYCER USAGE: Injects as Context File for desktop-app scaffold tickets. Composes with 12-node.md (main process is Node) + 20-typescript.md.
     AGENT USAGE: Follow verbatim. Research basis: docs/reference/research-files/Electron Desktop App Best Practices.md (cited). -->

# Electron Desktop App Rules (2026)

**Activation:** Glob `**/electron/**`, `**/main/**`, `**/renderer/**`, `**/preload*`, `**/electron-builder*`, `**/forge.config*`, `main.{js,ts}`, `preload.{js,ts}`
**Purpose:** Production patterns for Electron 30+ desktop applications, both standalone and as frontend to a Fabrik-deployed backend.
**Scope:** `desktop-app` scaffold. Composes with `12-node.md` (main-process runtime), `20-typescript.md` (renderer TS), `35-security-auth.md` (OAuth/M2M tokens), `55-observability.md` (Sentry/GlitchTip in main + renderer), `ocoron-design-system.md`.
**Research basis:** [`docs/reference/research-files/Electron Desktop App Best Practices.md`](../../../docs/reference/research-files/Electron%20Desktop%20App%20Best%20Practices.md)

---

## Framework Choice — Why Electron

Three viable frameworks in 2026:

| Framework | Bundle (baseline) | Idle RAM | Native lang | Cross-platform parity |
| --- | --- | --- | --- | --- |
| **Electron 30+** | ~150 MB | 150–200 MB | JavaScript / Node | **Excellent** (bundled Chromium) |
| Tauri 2.0 | 5–15 MB | < 80 MB | Rust | Variable (host webviews — WebView2 on Win, WebKit on Mac) |
| Wails | 10–20 MB | < 80 MB | Go | Variable |

**Pick Electron.** For a solo developer prioritizing feature velocity + cross-platform parity, Electron is the pragmatic default. Tauri/Wails give smaller bundles but introduce Rust/Go context-switching that bleeds solo dev velocity. The 150 MB baseline is acceptable for professional/productivity tools provided you ASAR-pack + Bytenode-compile (below).

Bundle-size mitigations (mandatory for >50 MB shipped builds):

- **ASAR packing with integrity validation** — `electron-builder` enables this by default with `asarUnpack` for native modules. Verifies the bundle against tampering and accelerates disk reads.
- **Bytenode compilation (optional)** — transforms JS to V8 bytecode. Reduces cold-start parser overhead AND obscures proprietary business logic. Adopt when bundle obfuscation matters.

## Process Model — Rigid Security Posture

Electron's multi-process model is the security boundary.

- **Main process** — full Node.js privileges. All OS native APIs, filesystem, SQLite, `safeStorage`, child processes (Ollama). Treat as the trusted server.
- **Renderer process** — hosts React UI. **Treat as untrusted** (XSS-susceptible). No Node, no `require`, no filesystem.
- **Preload script** — the ONLY allowed bridge. Use `contextBridge.exposeInMainWorld(...)` to expose a narrow, typed surface.

### Mandatory `BrowserWindow` settings

Every `new BrowserWindow({ webPreferences })` MUST declare:

```js
new BrowserWindow({
  webPreferences: {
    contextIsolation: true,        // MUST — isolates window globals from main
    nodeIntegration: false,        // MUST — denies require() in renderer
    sandbox: true,                 // MUST — Chromium-level sandbox
    preload: path.join(__dirname, 'preload.js'),
  },
});
```

Missing ANY of these three is a CVE waiting to happen — `nodeIntegration: true` + XSS = instant RCE.

### Preload + `contextBridge`

```js
// preload.ts — runs in an isolated world; bridges renderer ↔ main
import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('api', {
  files: {
    save: (payload: unknown) => ipcRenderer.invoke('files:save', payload),
    list: () => ipcRenderer.invoke('files:list'),
  },
  // ⚠ NEVER do this:
  // ipcRenderer: ipcRenderer,   // exposing the raw bridge = renderer compromise = main compromise
});
```

- Expose only the specific named methods you need.
- Never expose `ipcRenderer`, `ipcMain`, `webFrame`, or any module reference directly.
- Renderer accesses these via `window.api.files.save(...)`.

### Zero-trust IPC validation

Every `ipcMain.handle` receiver MUST validate inputs with Zod (or equivalent runtime schema) BEFORE doing anything privileged:

```js
import { z } from 'zod';

const SaveFilePayload = z.object({
  filename: z.string().min(1).max(255),
  contents: z.string().max(10 * 1024 * 1024),  // 10 MB max
  encoding: z.enum(['utf8', 'base64']),
});

ipcMain.handle('files:save', async (event, payload) => {
  const parsed = SaveFilePayload.safeParse(payload);
  if (!parsed.success) {
    return { success: false, error: 'invalid payload' };
  }
  try {
    const result = await saveFile(parsed.data);
    return { success: true, data: result };
  } catch (e) {
    return { success: false, error: (e as Error).message };
  }
});
```

### Error serialization across IPC

Standard `Error` objects do NOT cross the IPC boundary intact (they get flattened to `{message, stack}` strings or lost entirely). Every IPC handler returns the same wrapper shape:

```ts
type IpcResult<T> = { success: true; data: T } | { success: false; error: string };
```

Throwing across IPC is banned — always return the wrapper. Renderer code:

```js
const r = await window.api.files.save(payload);
if (!r.success) showError(r.error);
else applyResult(r.data);
```

## Local Persistence — `better-sqlite3` with SQLCipher

For local relational data (offline-first or local cache):

- **`better-sqlite3`** is the engine. Synchronous API matches SQLite's serialized access model — no mutex thrashing.
- **NOT `IndexedDB`** (renderer-only, async overhead, no real query language).
- **NOT `leveldb`** (no relational support, awkward for joins/filters).
- **NOT cloud-stored** — local-first applications keep the canonical store local.

### Encryption at rest — `better-sqlite3-multiple-ciphers` (SQLCipher)

Production builds MUST encrypt the local SQLite file:

```js
import Database from 'better-sqlite3-multiple-ciphers';

const masterKey = await getMasterKeyFromSafeStorage();  // see below
const db = new Database(path.join(app.getPath('userData'), 'app.db'));
db.pragma(`key = '${masterKey}'`);
db.pragma('cipher = sqlcipher');
db.pragma('kdf_iter = 256000');                          // OWASP 2026 floor
```

- Master key is a high-entropy random value generated on first launch + stored via `safeStorage` (below).
- `kdf_iter = 256000` matches current OWASP recommendations for PBKDF2 iterations.

## Credential Storage — `safeStorage`

`safeStorage` is the canonical 2026 credential API. **Replaces `keytar`** (which is unmaintained / native-build flaky).

```js
import { safeStorage } from 'electron';

function storeSecret(key: string, value: string) {
  if (!safeStorage.isEncryptionAvailable()) {
    // Linux without a Secret Service daemon (rare) — must handle explicitly
    throw new Error('OS keychain unavailable; refusing to store secret in plaintext');
  }
  const ciphertext = safeStorage.encryptString(value);
  fs.writeFileSync(secretsPath(key), ciphertext);
}

function loadSecret(key: string): string {
  const ciphertext = fs.readFileSync(secretsPath(key));
  return safeStorage.decryptString(ciphertext);
}
```

**Platform mapping:**

- **macOS** — Keychain
- **Windows** — DPAPI
- **Linux** — Secret Service (GNOME keyring / KWallet)

**Linux fallback handling — explicit check required:**

- `safeStorage.isEncryptionAvailable()` returns `false` on Linux systems without a supported daemon (some headless servers, minimal Wayland setups).
- **DO NOT silently fall back to plaintext.** Either: (a) refuse to store the secret and surface a user-facing warning, or (b) require the user to type a passphrase that derives the encryption key (Argon2id).
- Document the OS-keyring requirement in the app's README / first-run check.

## Distribution Channels

| Channel | When | Cost | Trade-offs |
| --- | --- | --- | --- |
| **Direct download (developer domain)** | Default for solo dev | Hosting only | Full update lifecycle control; you must build everything |
| Microsoft Store | Enterprise reach, no SmartScreen friction | Free dev account | Restrictive sandbox + slow review; not ideal for power-user tools |
| Mac App Store | iCloud sync, IAP, family sharing | $99/yr (covered by Developer ID) | Hardened sandbox limits filesystem + network; review process |
| Homebrew Cask / winget / Chocolatey | Power-user discovery | Free | Community-driven; still need signed binaries hosted by you |
| AppImage (Linux) | Universal Linux | Free | No auto-trust; ship `.AppImage` + GPG signature |
| Flatpak / snap | Linux desktop distro integration | Free | More install friction; auto-update + sandbox via the store |

**Default: direct download + Homebrew Cask / winget / AppImage GPG-signed.** Add stores only when their reach justifies the sandbox cost.

## Code Signing (the 2026 cost matrix)

| OS | Required identity | Annual cost | Hardware token? |
| --- | --- | --- | --- |
| **Windows 10/11** | **Azure Trusted Signing** | **~$120 ($9.99/mo)** | **No** (Cloud HSM via Azure) |
| Windows (legacy) | EV Certificate | $350–700 | Yes (USB token) |
| **macOS 13+** | Apple Developer ID + notarization | $99 | No (Apple ID auth) |
| **Linux** | GPG signature | $0 | No |

**Recommendations:**

- **Windows: Azure Trusted Signing.** Bypasses EV USB tokens, gives **immediate SmartScreen reputation**, integrates with `electron-builder` via the SignTool plugin. The single most important cost reduction for solo desktop dev in 2026.
- **macOS: Apple Developer ID + Hardened Runtime + notarization.**
  - Enable Hardened Runtime: `electron-builder` flag `hardenedRuntime: true`.
  - Notarize with `xcrun notarytool`. `electron-builder` does this automatically when API keys are present.
  - **Entitlements:** declare each capability explicitly. For backend-connected apps: `com.apple.security.network.client`. For file access: `com.apple.security.files.user-selected.read-write`. Over-requesting fails notarization.
- **Linux:** GPG-sign the final `.AppImage` output. Distribute the `.asc` alongside.

### Notarization gotcha

macOS notarization happens AFTER signing AND requires re-stapling. Sequence:

```bash
electron-builder --mac --publish never        # signs + notarizes + staples
# verify:
spctl --assess --type execute -vv dist/MyApp.app
codesign --verify --deep --strict --verbose=2 dist/MyApp.app
```

If you ship without stapling, Gatekeeper requires online lookup on first launch — slow + offline-hostile.

## Auto-Update — Zero-Egress via Cloudflare R2

**Default architecture: `electron-updater` + Cloudflare R2** with a public `pub-*.r2.dev` URL as a generic HTTP provider.

```js
// electron-builder.yml
publish:
  provider: generic
  url: https://pub-<account>.r2.dev/updates/${os}
```

- **Cloudflare R2** has zero egress fees. A 150 MB installer downloaded N thousand times accumulates serious bandwidth charges on AWS S3; R2 makes auto-update economically viable for a solo dev.
- **`electron-builder` publishes** the artifacts AND a `latest.yml` (Windows), `latest-mac.yml` (macOS), `latest-linux.yml` (Linux) — these are the manifest files `electron-updater` reads.
- **Blockmap delta updates** are enabled by default — only the changed blocks of the binary are downloaded, drastically reducing payload.

**Banned:**

- **GitHub Releases for private repos.** Requires embedding a GitHub token in the app binary — instant token leak via `strings` or runtime memory dump.
- **AWS S3 with default egress pricing** for installers > 50 MB.

Update channel design:

```text
client launches → electron-updater checks https://pub-xyz.r2.dev/updates/win/latest.yml
                → if new version found, downloads blockmap diff
                → installs on next quit-and-relaunch
```

Channels (`stable` / `beta`): R2 supports prefix routing — `updates/stable/` and `updates/beta/`. App checks via `autoUpdater.setFeedURL({ url, channel: 'stable' })`.

## Native Integrations

### Cross-platform menus

Define menu structure in the main process. Use Electron's `Menu.buildFromTemplate` with role-based items (`copy`, `paste`, `selectAll`) — these get the right platform shortcuts automatically (⌘C on Mac, Ctrl+C elsewhere).

### System tray + dock badges

- Tray icons: `new Tray(path.join(__dirname, 'tray-icon.png'))`. Use the right PNG size per OS (16x16 win, 22x22 mac, varies linux). Bundle multiple sizes.
- Dock badge (macOS): `app.dock.setBadge('3')` for notification counts.
- Windows taskbar overlay icon: `BrowserWindow.setOverlayIcon(...)`.

### Deep-link protocol handlers

Register a protocol (`myapp://`) at install time. `electron-builder` handles registration via `protocols:` in the config. Main process catches incoming URLs:

```js
app.setAsDefaultProtocolClient('myapp');

// macOS: open-url event
app.on('open-url', (event, url) => {
  event.preventDefault();
  handleDeepLink(url);
});

// Windows/Linux: second-instance event (deep-link comes via argv)
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', (_, argv) => {
    const url = argv.find(a => a.startsWith('myapp://'));
    if (url) handleDeepLink(url);
  });
}
```

Mandatory use cases:

- **OAuth callback** (see Auth below)
- **File-type associations** (`open with MyApp`)

### Autostart at login

Use Electron's cross-platform API — never poke registry / LaunchAgents directly:

```js
app.setLoginItemSettings({
  openAtLogin: true,
  openAsHidden: true,           // Mac: start hidden
  args: ['--hidden'],           // Win/Linux: detect flag
});
```

### Single-instance lock

Mandatory for any app where a deep-link or file-double-click should route to the existing window instead of spawning a second instance:

```js
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', (_, argv, cwd) => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
    // handle argv (deep links, file paths)
  });
}
```

## Performance

- **Defer heavy `require()`** — don't synchronously load native modules at the top of `main.ts`. Load them lazily when their subsystem is first invoked. Cold start gets faster.
- **`app.requestSingleInstanceLock()`** — see above; prevents memory-heavy second Chromium spawn.
- **Renderer process-per-window vs shared** — modern Electron defaults are sensible; do not override `affinity:` without measuring.
- **Background work belongs in workers, not hidden renderers** — see "Background Execution" below.

## Crash Reporting — Sentry / GlitchTip in BOTH Processes

Crash reporting in 2026 = third-party SDK in main AND renderer. Electron's built-in `crashReporter` is for native (Chromium) crashes only — application JS errors need the SDK.

```js
// main process — before any window opens
import * as Sentry from '@sentry/electron/main';
Sentry.init({ dsn: process.env.GLITCHTIP_DSN });

// renderer/preload — react component tree wrapped with ErrorBoundary
import * as Sentry from '@sentry/electron/renderer';
Sentry.init({ dsn: process.env.GLITCHTIP_DSN });
```

`@sentry/electron` handles both sides. GlitchTip is Sentry-protocol-compatible — same DSN, same SDK.

**Minidumps for native Chromium crashes** are stored locally in `app.getPath('crashDumps')`. Transmit only with explicit consent (KVKK below).

## Authentication (Connected mode)

**OAuth: system browser, never embedded webview.**

```js
import { shell } from 'electron';

async function login() {
  const verifier = generatePkceVerifier();
  const challenge = await pkceChallenge(verifier);
  const url = `https://auth.example.com/oauth?client_id=...&code_challenge=${challenge}&redirect_uri=myapp://auth`;
  await shell.openExternal(url);
  // wait for myapp://auth?code=... via deep-link handler
}
```

**Why:**

- Google, Microsoft, and most major IdPs **actively ban** embedded webview OAuth flows (phishing surface).
- System browser has the user's existing session + 2FA + password-manager integration.
- `<webview>` tag and embedded `BrowserWindow` for auth are banned.

Token storage: `safeStorage` (above). Never write tokens to plain disk or environment.

## Sync Architecture (Connected mode)

Optimistic-UI + local mutation log + queue-and-replay:

```text
user action → INSERT INTO mutations_pending (action, payload, ts) → UI updates immediately
network up → background sync worker reads mutations_pending
           → POST batched mutations to Fabrik backend (X-Internal-Token or app-issued Bearer JWT from fabrik-lib/fastapi-user-auth)
           → on success: DELETE FROM mutations_pending; APPLY canonical state from response
           → on conflict: invoke conflict resolver (CRDT or last-write-wins per field)
```

**Conflict resolution:**

- **Default: last-write-wins per field** with server timestamp. Simplest, correct for most apps.
- **CRDT (e.g., Yjs / Automerge)** when you need real-time multi-device editing of structured documents.
- **Operational Transformation** when you need preserving-intent edits to ordered text (collaborative editor).

Per `58-resilience.md`: wrap sync calls with timeout + retry + circuit breaker. On circuit-open, sync pauses gracefully; the local mutation log stays intact.

## Real-Time Backend Updates

For server-pushed updates: **SSE > WebSockets > polling**.

- **Polling** burns battery (Windows Battery Saver + macOS Low Power Mode throttle aggressively).
- **WebSockets** maintain a TCP connection — fine for active windows, but close them when the window minimizes.
- **SSE (Server-Sent Events)** is the simplest server-push pattern over HTTPS; no upgrade dance, auto-reconnect with `Last-Event-ID`.

Per `12-node.md`: Node backend uses Fastify's SSE plugin or Express's `EventEmitter` pattern for the server side.

## Background Execution — DON'T

Persistent hidden renderer processes for background sync are **banned**:

- macOS Low Power Mode kills them.
- Windows Battery Saver throttles them.
- They keep ~150 MB RAM resident even when "doing nothing".

**Instead:** rely on OS push notifications to wake the app for sync. For Mac: `node-mac-notifications` or APNs via the backend. For Win: WNS via the backend. For Linux: there's no canonical push; degrade to a tray-based "Click to sync" pattern.

## Local LLM (Standalone AI mode)

For air-gapped AI features: Ollama as a child process.

```js
import { spawn } from 'node:child_process';

const ollama = spawn('ollama', ['serve'], { stdio: 'inherit' });
// Ollama exposes OpenAI-compatible REST API at http://localhost:11434
```

- Models live on the user's disk (`~/.ollama/models/`).
- Fabrik dev workstation already runs Ollama at `localhost:11434` (per `AGENTS.md § Local LLM Agents`).
- App ships Ollama as a bundled dep OR detects an existing install. Bundling adds ~100 MB but eliminates "install Ollama first" friction.
- Per `cost-budget.md`: local inference replaces OpenRouter API spend for offline use cases.
- **Constraint:** Ollama capabilities are bounded by the user's GPU VRAM. Document the minimum hardware (e.g., 8 GB VRAM for Llama 3 8B q4).

## License Management (Standalone, no backend)

For paid standalone apps with offline license validation:

```js
import crypto from 'node:crypto';

const PUBLIC_KEY = `-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----`;

function verifyLicense(licenseFile: Buffer): LicensePayload | null {
  // licenseFile = JSON payload + RSA-SHA256 signature
  const { payload, signature } = parseLicense(licenseFile);
  const verifier = crypto.createVerify('RSA-SHA256');
  verifier.update(payload);
  if (!verifier.verify(PUBLIC_KEY, signature, 'base64')) return null;
  const parsed = JSON.parse(payload);
  if (parsed.expires_at < Date.now()) return null;
  return parsed;  // { user_id, tier, features, expires_at }
}
```

- Developer signs license file with private key (kept offline, NEVER in repo).
- App ships public key embedded in code.
- License payload carries `user_id`, `tier`, `features`, `expires_at`.
- **Revocation:** ship a blacklist of compromised license signatures in updates. Limited but workable for low-volume markets.

## KVKK / GDPR Compliance

For Turkish entity (KVKK) and EU users (GDPR):

- **Telemetry: opt-in only.** Default config = no network egress. First-run prompt explicitly asks; refusal is silent + permanent (until user opts in via Settings).
- **Crash reporting (Sentry/GlitchTip): opt-in.** Without consent, minidumps stay local-only.
- **Anonymous IDs locally** when telemetry is enabled — no PII in event payloads.
- **No foreign-cloud egress without consent.** KVKK Article 9: personal data cannot be transferred outside Türkiye without explicit informed consent OR adequacy decision (rare).

## Apple Privacy Manifest

For macOS App Store submissions AND notarized direct-download apps:

- `PrivacyInfo.xcprivacy` is mandatory.
- Declare every data category collected.
- **Required Reason APIs** (boot times, file timestamps, disk space, system uptime, UserDefaults) — each needs a justification code from Apple's approved list. Pick the closest fit; don't invent codes.

`electron-builder` doesn't auto-generate this — author manually based on what your native dependencies use.

## Testing — Playwright (Spectron is dead)

```js
// playwright.config.ts
import { _electron as electron } from '@playwright/test';

test('main window renders', async () => {
  const app = await electron.launch({ args: ['main.js'] });
  const window = await app.firstWindow();
  await expect(window).toHaveTitle('MyApp');
  await app.close();
});
```

- **Spectron is DEPRECATED** (read: never use).
- Playwright supports Electron natively via `_electron.launch()`.
- **Mock native OS dialogs** (file picker, save dialog) via `electronApp.evaluate()` — they block test execution otherwise:

  ```js
  await electronApp.evaluate(({ dialog }) => {
    dialog.showOpenDialog = async () => ({ canceled: false, filePaths: ['/tmp/fixture.txt'] });
  });
  ```

Testing Trophy + Behavior Contract (per `45-testing-strategy.md`) — one integration/E2E test per distinct user-observable behavior, risk-ordered; **NOT** a wide base of business-logic unit tests:

- **Primary: IPC integration tests** — exercise the preload `contextBridge` surface with mock main handlers (the main↔renderer contract is where Electron bugs live).
- **Primary: Playwright E2E** — golden-path user flows, one per behavior; keep small + fast.
- **Unit (`vitest` per `12-node.md`) ONLY for complex pure algorithms / data transformations** — reserved, not the base.

---

## Banned Patterns

| Pattern | Use Instead | Reason |
| --- | --- | --- |
| `nodeIntegration: true` in `BrowserWindow` | `contextIsolation: true` + `nodeIntegration: false` + `sandbox: true` | XSS → instant RCE if Node is enabled in renderer |
| Exposing `ipcRenderer` directly via `contextBridge` | Expose named, typed methods only | Raw ipcRenderer leak = full renderer-to-main compromise |
| `<webview>` or `BrowserWindow` for OAuth | `shell.openExternal` + deep-link callback | Embedded webview OAuth is banned by Google + most IdPs (phishing) |
| `keytar` | `safeStorage` API | keytar is unmaintained + native-build flaky; safeStorage is canonical |
| `IndexedDB` / `leveldb` for relational data | `better-sqlite3` with SQLCipher | IndexedDB lacks SQL; leveldb has no relational support |
| Plain `better-sqlite3` (unencrypted) for prod | `better-sqlite3-multiple-ciphers` (SQLCipher 256-bit AES) | KVKK + reasonable user expectation for local sensitive data |
| Silently falling back to plaintext on Linux without keyring | Refuse + warn OR require passphrase | "Silent plaintext" defeats the whole credential model |
| Throwing exceptions across IPC | Return `{success, data?, error?}` wrapper | Error objects don't serialize over IPC; throwing loses context |
| Skipping Zod validation on `ipcMain.handle` | Validate every input with Zod | Renderer is untrusted; raw inputs to privileged main code = RCE risk |
| Legacy EV USB-token code signing on Windows | Azure Trusted Signing ($9.99/mo) | USB tokens break CI; Azure Trusted Signing gives same SmartScreen reputation at fraction of cost |
| GitHub Releases for private-repo auto-update | Cloudflare R2 generic HTTP provider | Embedding GH token in binary = token leak; egress costs make S3 unviable |
| Hidden persistent renderer for background sync | OS push notifications + on-launch sync | Battery Saver / Low Power Mode kill them; massive idle RAM |
| Aggressive HTTP polling for backend updates | SSE > WebSockets > polling | Polling burns battery + breaks under throttling |
| Persistent telemetry without explicit opt-in | First-run opt-in prompt + KVKK-aware default | Foreign-cloud egress without consent violates KVKK Art 9 |
| Spectron for E2E tests | Playwright `_electron.launch()` | Spectron is deprecated; Playwright is the 2026 standard |
| Native OS dialogs blocking automated tests | `electronApp.evaluate(({ dialog }) => ...)` mock | Dialogs are modal; uncovered tests hang in CI |
| Skipping notarization on macOS | `xcrun notarytool` (auto via electron-builder) | Gatekeeper warns users; ships unstapled = online check on every launch |
| Manual file paths to `app.getPath(...)` constants | `app.getPath('userData')`, `'crashDumps'`, etc. | Hardcoded paths break under user-relocated profiles + portable installs |

---

## Related Rule Packs

- `core/12-node.md` — main process is Node; SIGTERM drain, structured logging via pino, `crypto.timingSafeEqual()` (for M2M token validation if connecting to Fabrik backend)
- `core/20-typescript.md` — TS-specific patterns (auto-loads on `.ts` files)
- `core/15-api-contracts.md` — when connecting to Fabrik backend, request/response contracts
- `core/35-security-auth.md` — app-issued Bearer JWT (`fabrik-lib/fastapi-user-auth`, Pattern A default), M2M `X-Internal-Token` (backend-side)
- `core/55-observability.md` — `@sentry/electron` for both processes; GlitchTip DSN
- `core/58-resilience.md` — sync queue retry + circuit breaker patterns
- `core/45-testing-strategy.md` — Testing Trophy + Behavior Contract (integration/E2E primary per behavior; unit via vitest only for pure algorithms)
- `core/ocoron-design-system.md` — color tokens, typography, spacing for the React UI
- `core/cost-budget.md` — local LLM via Ollama as alternative to OpenRouter API spend
- Epic decomposition + the standalone-vs-connected mode fork: **§ Epic Decomposition** below (promoted into this pack 2026-07-13; `domain-modules/` is deleted).

---

## Done When

- [ ] All `BrowserWindow` instances declare `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`.
- [ ] Preload script uses `contextBridge.exposeInMainWorld` with named typed methods; no raw `ipcRenderer` exposed.
- [ ] Every `ipcMain.handle` receiver validates input with Zod (or equivalent) BEFORE doing privileged work.
- [ ] All IPC handlers return `{success: true, data} | {success: false, error: string}` wrapper.
- [ ] Local SQLite uses `better-sqlite3-multiple-ciphers` with SQLCipher 256-bit AES; `kdf_iter ≥ 256000`.
- [ ] Master key + OAuth tokens stored via `safeStorage.encryptString`; never plaintext on disk.
- [ ] Linux fallback: `safeStorage.isEncryptionAvailable()` checked; refuse OR require passphrase if false.
- [ ] Windows signing: Azure Trusted Signing via `electron-builder` SignTool plugin; no EV USB tokens.
- [ ] macOS signing: Apple Developer ID + Hardened Runtime + notarization via `xcrun notarytool`; stapled.
- [ ] macOS entitlements: only those actually needed; `com.apple.security.network.client` for backend-connected.
- [ ] Linux: GPG-signed AppImage + `.asc` published alongside.
- [ ] Auto-update via `electron-updater` with `provider: generic` pointing to `pub-*.r2.dev` (Cloudflare R2); blockmap delta updates enabled.
- [ ] GitHub Releases NOT used for private-repo distribution.
- [ ] `app.requestSingleInstanceLock()` mandatory; `second-instance` event routes argv (deep links, file paths) to existing window.
- [ ] Deep-link protocol handler registered (`app.setAsDefaultProtocolClient`); `open-url` (Mac) + `second-instance` argv (Win/Linux) handled.
- [ ] Autostart via `app.setLoginItemSettings` (not registry / LaunchAgents directly).
- [ ] OAuth via `shell.openExternal` to system browser; deep-link callback; never `<webview>` or `BrowserWindow` for auth.
- [ ] `@sentry/electron/main` + `@sentry/electron/renderer` both initialised with `GLITCHTIP_DSN`; opt-in only per KVKK.
- [ ] Telemetry default: NO network egress until user opts in; anonymous IDs only.
- [ ] Apple Privacy Manifest (`PrivacyInfo.xcprivacy`) filed for macOS submissions + notarized direct downloads.
- [ ] Sync mode: optimistic UI + local mutation log; queue-and-replay; CRDT or LWW conflict resolution.
- [ ] Real-time backend: SSE preferred over WebSockets over polling.
- [ ] No persistent hidden renderer for background sync; rely on OS push notifications.
- [ ] Local LLM (if shipped): Ollama child process at `localhost:11434`; minimum hardware documented.
- [ ] Standalone licensing (if applicable): RSA-SHA256 signature verification with embedded public key.
- [ ] E2E tests: Playwright `_electron.launch()`; native dialogs mocked via `electronApp.evaluate()`.
- [ ] Spectron NOT used.
- [ ] ASAR packing enabled with integrity validation; Bytenode adopted IF bundle obfuscation matters.
- [ ] Ocoron design tokens used for ALL color/spacing/typography (no hardcoded hex or raw px).

---

## Epic Decomposition (PLANNING layer — read before any epic exists)

> Promoted from `docs/traycer/mega-epic-breakdown/domain-modules/desktop-app.md` (2026-07-13). The rest of
> that module restated this pack and has been deleted; **this pack is the single source of truth**.
> ⚠️ Every *code-time* fact (process model, IPC, SQLCipher, signing, updater) is owned by the sections above —
> cite them, never restate them. A second copy is exactly how the old module came to claim the scaffold ships
> "React 18 + Tailwind" when `templates/desktop-app/package.json` ships **electron + typescript and nothing else**.

## The 3 Forks (do NOT inherit SaaS or mobile defaults here)

1. **Two-faced (when connected) or one-faced (when standalone)** — a desktop app is EITHER a fully standalone tool OR a desktop frontend to a Fabrik-deployed backend (python-api or node-api). The backend (if any) follows the full 4-stage Fabrik lifecycle. The desktop binary is NOT deployed via `fabrik apply` — it ships via direct download, store submission, or Linux package channels. **Decide standalone-vs-connected at intake; the architecture changes substantially.**
2. **Distribution is signed-or-rejected** — Windows SmartScreen and macOS Gatekeeper actively block unsigned binaries. Code signing is non-optional for any non-internal app. The 2026 cost structure was rewritten by Azure Trusted Signing ($9.99/mo).
3. **No responsive breakpoints** — desktop apps target windowed UI from ~800px to multi-monitor 5K. Ocoron design tokens apply, but RWD breakpoints from the web pack do NOT. Min window 800×600; design for resizable.

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
