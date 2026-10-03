---
activation: glob
globs: ["**/electron/**", "**/renderer/**", "**/electron-builder*", "**/forge.config*", "**/preload.{js,ts}"]
description: Electron desktop app — supported-major policy, process model, IPC zero-trust, fuses, encrypted local storage, code signing and notarization, auto-update from your own domain, native integrations, KVKK/GDPR
trigger: glob
currency_pass: 2026-10-03
---
<!-- CONSUMER: Coding agents (Claude Code + dispatched subagents) on the `desktop-app` scaffold.
     GOAL: Electron desktop application patterns — process isolation, IPC validation, distribution, code signing,
     auto-update, local storage, OS integrations. Composes with 12-node.md (main process is Node) + 20-typescript.md.
     The planning layer (standalone vs connected, unit economics, kill criteria) is 00-domain-desktop-app.md.
     Research basis: docs/reference/research/2026-10-03-desktop-app-currency-ledger.md (every fact here, with its
     source) and docs/reference/research/Electron Desktop App Best Practices.md (the original survey). -->

# Electron Desktop App Rules

**Activation:** the frontmatter globs — `**/electron/**`, `**/renderer/**`, `**/electron-builder*`, `**/forge.config*`,
`**/preload.{js,ts}`.
**Purpose:** production patterns for Electron desktop applications, both standalone and as a client of a
Fabrik-deployed backend.
**Scope:** `desktop-app` scaffold. Composes with `12-node.md` (main-process runtime), `20-typescript.md` (renderer
TS), `35-security-auth.md` (sign-in, tokens), `55-observability.md` (Sentry/GlitchTip in main + renderer),
`design-system-template.md`.

---

## The fleet today

- The `desktop-app` scaffold (`templates/desktop-app/`) emits an Electron app packaged with **electron-builder**
  (Windows NSIS target), `electron-updater`, and a `BrowserWindow` that sets `nodeIntegration: false`,
  `contextIsolation: true` and `sandbox: true`. It ships no preload file and no update feed yet (fleet finding
  filed 2026-10-03); a project scaffolded from it adds both from the sections below before its first build.
- No fleet project builds a desktop app today: the one repo declared `desktop-app` is an Obsidian plugin with no
  Electron code, so nothing in the fleet activates this pack's globs. The rules below are what the first real one
  must meet.

## Framework Choice — Why Electron

| Framework | Rendering engine | Shipped size | Native language | Cross-platform parity |
| --- | --- | --- | --- | --- |
| **Electron** | Bundled Chromium | ~100–200 MB | JavaScript / Node | **Excellent** — the same engine on every OS |
| Tauri | The OS webview (WebView2 on Windows, WKWebView on macOS, webkitgtk on Linux) | a few MB | Rust | Variable — WKWebView updates only with macOS, webkitgtk varies by distro |
| Wails | The OS webview | a few MB | Go | Variable, as Tauri |

**Pick Electron.** For a solo developer prioritising feature velocity and cross-platform parity, one engine on
every OS is the pragmatic default; Tauri and Wails ship far smaller bundles (third-party measurements put Tauri at
a few percent of Electron's size and well under its idle memory) but add Rust or Go, and per-OS webview bugs that
only reproduce on that OS. Re-weigh only when bundle size or memory is the product's selling point.

**Version policy.** Electron ships a new major every eight weeks and supports only the **three newest stable
majors**, each on its latest minor. Stay inside that window: an app on an unsupported major gets no security
fixes, and Chromium vulnerabilities are the main reason Electron releases at all. Pin the major in `package.json`
and move to the next major before yours leaves the window.

**Packaging tool.** Electron's own docs recommend **Electron Forge**; **electron-builder** is maintained by the
community, not the Electron project, and replaces some official modules (its own `electron-updater`). The fleet
uses electron-builder because the scaffold does and because it carries code signing, fuses and the update
manifests in one config. Keep one tool per project; do not mix.

## Process Model — Rigid Security Posture

Electron's multi-process model is the security boundary.

- **Main process** — full Node.js privileges. All OS native APIs, filesystem, SQLite, `safeStorage`, child
  processes. Treat it as the trusted server.
- **Renderer process** — hosts the React UI. **Treat it as untrusted** (XSS-susceptible). No Node, no `require`, no
  filesystem.
- **Preload script** — the ONLY bridge. Use `contextBridge.exposeInMainWorld(...)` to expose a narrow, typed
  surface.

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

All three are Electron's defaults; declare them anyway, because turning context isolation off also turns the
sandbox off, and an explicit `true` makes that regression visible in review. `nodeIntegration: true` plus one XSS
is remote code execution.

### Lock down what the renderer can reach

- **Permissions:** Electron approves every permission request (camera, microphone, notifications, geolocation)
  unless you install a handler. Call `session.defaultSession.setPermissionRequestHandler(...)` and allow only what
  the app uses.
- **Navigation:** deny it by default — `contents.on('will-navigate', (e, url) => { ... e.preventDefault() })` —
  and compare with Node's URL parser, never a string prefix (`startsWith('https://example.com')` lets
  `https://example.com.attacker.com` through).
- **New windows:** `contents.setWindowOpenHandler(() => ({ action: 'deny' }))`; hand a vetted URL to
  `shell.openExternal`, and never pass it untrusted content (it can run arbitrary commands).
- **Content Security Policy:** send it as a response header (`session.webRequest.onHeadersReceived`) with
  `script-src 'self'`; a `<meta>` tag is the fallback for pages loaded from disk.
- **Local content:** serve the app's pages through a custom protocol (`protocol.handle`) rather than `file://`,
  and register the scheme as privileged **before `app` is ready** — an unregistered scheme behaves like `file://` and
  has no real origin, so the IPC origin check below would never match:

  ```js
  protocol.registerSchemesAsPrivileged([
    { scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true } },
  ]);
  app.whenReady().then(() => protocol.handle('app', (req) => serveFromBundle(req)));
  ```
- **Load only secure content** (HTTPS for anything remote), and never set `webSecurity: false`,
  `allowRunningInsecureContent: true`, `experimentalFeatures` or `enableBlinkFeatures`; `<webview>` gets no
  `allowpopups`.

### Fuses — flip them at package time

Fuses are build-time switches that code signing then protects. Set them through electron-builder's `electronFuses`
config (or `@electron/fuses` in an `afterPack` hook):

| Fuse | Set to | Why |
| --- | --- | --- |
| `runAsNode` | off | stops `ELECTRON_RUN_AS_NODE` turning the app into a plain Node binary; use Utility Processes instead of `child_process.fork` |
| `enableNodeOptionsEnvironmentVariable` | off | `NODE_OPTIONS` can inject code |
| `enableNodeCliInspectArguments` | off in release builds | `--inspect` attaches a debugger; Playwright needs it on, so test a build that keeps it (§ Testing) |
| `enableCookieEncryption` | on | encrypts the cookie store with the OS keychain |
| `enableEmbeddedAsarIntegrityValidation` + `onlyLoadAppFromAsar` | on | together they refuse to load any code that is not the validated ASAR (macOS and Windows only) |
| `grantFileProtocolExtraPrivileges` | off | unless the app still serves pages from `file://` |

**Bytenode** (compiling JS to JavaScript-engine bytecode) obscures logic; it is not a security control. Its bytecode must be
compiled by the exact Electron build and in the same process type that loads it, and recent majors crash on
bytecode compiled the old way. Adopt it only with a test on the major you ship.

### Preload + `contextBridge`

```js
// preload.ts — runs in an isolated world; bridges renderer ↔ main
import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('api', {
  files: {
    save: (payload: unknown) => ipcRenderer.invoke('files:save', payload),
    list: () => ipcRenderer.invoke('files:list'),
  },
  onProgress: (cb: (pct: number) => void) =>
    ipcRenderer.on('files:progress', (_event, pct) => cb(pct)),   // never pass cb itself: it leaks event.sender
    // ⚠ NEVER: send: ipcRenderer.send / on: ipcRenderer.on — a generic channel lets the renderer reach any handler
});
```

- Expose only the specific named methods you need.
- Never expose `ipcRenderer`'s generic `send` / `invoke` / `on`, `ipcMain`, `webFrame`, or any module reference
  (the whole `ipcRenderer` module now arrives as an empty object over `contextBridge`; exposing its methods one by
  one is the live risk), and never hand a renderer callback straight to `ipcRenderer.on` (the event object carries
  the sender).
- The renderer calls `window.api.files.save(...)`.

### Zero-trust IPC validation

Every `ipcMain.handle` receiver MUST check **who sent it** and **what was sent** before doing anything privileged:

```js
import { z } from 'zod';

const SaveFilePayload = z.object({
  filename: z.string().min(1).max(255),
  contents: z.string().max(10 * 1024 * 1024),  // 10 MB max
  encoding: z.enum(['utf8', 'base64']),
});

const TRUSTED_ORIGINS = new Set(['app://bundle']);  // the custom protocol the app serves itself from

ipcMain.handle('files:save', async (event, payload) => {
  if (!event.senderFrame || !TRUSTED_ORIGINS.has(event.senderFrame.origin)) {
    return { success: false, error: 'untrusted sender' };
  }
  const parsed = SaveFilePayload.safeParse(payload);
  if (!parsed.success) return { success: false, error: 'invalid payload' };
  try {
    return { success: true, data: await saveFile(parsed.data) };
  } catch (e) {
    return { success: false, error: (e as Error).message };
  }
});
```

Check the frame's **origin**, not its URL (`about:blank`, `blob:` and sandboxed documents carry URLs that do not
say who controls them), and treat a missing frame as untrusted.

### Error serialization across IPC

`Error` objects do not cross the IPC boundary intact. Every IPC handler returns the same wrapper shape:

```ts
type IpcResult<T> = { success: true; data: T } | { success: false; error: string };
```

Throwing across IPC is banned — always return the wrapper. Renderer code:

```js
const r = await window.api.files.save(payload);
if (!r.success) showError(r.error);
else applyResult(r.data);
```

## Local Persistence — `better-sqlite3`, encrypted

For local relational data (offline-first or local cache):

- **`better-sqlite3`** is the engine. Its synchronous API matches SQLite's serialized access model, and it now
  builds on Node-API, so one prebuilt binary serves several Node and Electron versions.
- **NOT `IndexedDB`** (renderer-only, async overhead, no real query language).
- **NOT `leveldb`** (no relational support).
- **NOT cloud-stored** — a local-first application keeps the canonical store local.

### Encryption at rest — `better-sqlite3-multiple-ciphers`

Production builds MUST encrypt the local SQLite file. The key is a random 32-byte value generated on first launch
and kept in `safeStorage` (below); a random key needs no slow key derivation, so pass it **raw**:

```js
import Database from 'better-sqlite3-multiple-ciphers';

const hexKey = await getMasterKeyFromSafeStorage();      // 64 hex characters = 32 random bytes
const db = new Database(path.join(app.getPath('userData'), 'app.db'));
db.pragma(`cipher = 'sqlcipher'`);                         // choose the cipher before the key
db.pragma(`key = "x'${hexKey}'"`);                         // raw key: skips the passphrase KDF
```

- A raw key (`x'…'`, exactly 64 hex characters) is used as the encryption key directly.
- Only when the key comes from **something the user types** does key derivation matter: keep SQLCipher's default
  (PBKDF2 with HMAC-SHA512, 256,000 iterations — above OWASP's floor for that hash) or derive with Argon2id (OWASP
  minimum: 19 MiB memory, two iterations).

## Sign-in — passwordless, OTP code path

Per `35-security-auth.md` § Passwordless (the fleet default): sign-in is `fastapi-user-auth`'s
passwordless flow, and on desktop **use the OTP CODE path** — the user types the 6-digit code in the
renderer, the MAIN process posts it to `/auth/passwordless/verify`, and the returned JWT goes to
`safeStorage` (below), never to renderer-accessible storage. A magic LINK requires a registered
custom protocol handler and OS-level deep-link wiring; that is a real option but it is extra
machinery for no gain over a code the user is already reading in the same mail.

## Credential Storage — `safeStorage`

`safeStorage` is Electron's credential API. **It replaces `keytar`**, which was archived in 2022. Prefer the
asynchronous calls (`encryptStringAsync` / `decryptStringAsync`): they support key rotation, and Electron says the
synchronous ones may be deprecated.

```js
import { safeStorage } from 'electron';

async function storeSecret(key: string, value: string) {
  const linuxPlaintext =
    process.platform === 'linux' && safeStorage.getSelectedStorageBackend() === 'basic_text';
  if (!(await safeStorage.isAsyncEncryptionAvailable()) || linuxPlaintext) {
    throw new Error('OS keychain unavailable; refusing to store secret with a hardcoded key');
  }
  fs.writeFileSync(secretsPath(key), await safeStorage.encryptStringAsync(value));
}

async function loadSecret(key: string): Promise<string> {
  const { result, shouldReEncrypt } = await safeStorage.decryptStringAsync(fs.readFileSync(secretsPath(key)));
  if (shouldReEncrypt) await storeSecret(key, result);   // the key rotated: write it back under the new key
  return result;
}
```

Call both only after `app` is `ready`; `decryptStringAsync` resolves to `{ result, shouldReEncrypt }`, not a
string. **Platform mapping:**

- **macOS** — Keychain: protected from other users and from other apps of the same user.
- **Windows** — DPAPI: protected from other users, **not** from other apps running as the same user.
- **Linux** — the Secret Service (GNOME libsecret, KWallet), or the `org.freedesktop.portal.Secret` portal under
  Flatpak (asynchronous API only).

**Linux fallback — explicit check required:** with no secret store, `safeStorage` falls back to the `basic_text`
backend, which encrypts with a **hardcoded password** — effectively plaintext. Detect it with
`getSelectedStorageBackend() === 'basic_text'`. **Do not store secrets that way.** Either refuse and tell the user,
or have the user type a passphrase that derives the key (Argon2id). State the OS-keyring requirement in the
app's README and first-run check.

## Distribution Channels

| Channel | When | Cost to you | Trade-offs |
| --- | --- | --- | --- |
| **Direct download (your own domain)** | Default for a solo developer | Hosting only; no commission | Full control of the update lifecycle; signing (below) is on you |
| Microsoft Store | Reach, no SmartScreen warning | Free registration for individual and company accounts (companies wait days for verification); MSIX packages are re-signed by Microsoft for free | With your own commerce you keep all revenue on non-game apps; Microsoft's commerce takes 15% on apps (12% games). An MSI/EXE you submit must already be signed by a trusted CA |
| Mac App Store | iCloud, in-app purchase, family sharing | the Apple Developer Program ($99/year — the same membership as Developer ID) | A 30% commission, 15% in the Small Business Program (up to $1M proceeds a year) and on subscriptions after a subscriber's first year; app sandbox limits filesystem and network; review |
| Homebrew Cask / winget / Chocolatey | Power-user discovery | Free | Community manifests pointing at signed binaries you host |
| AppImage (Linux) | Universal Linux | Free | No OS trust; embed a GPG signature (`appimagetool --sign`) and publish the key |
| Flatpak (Flathub) / Snap | Distro integration | Free | Flathub builds from source with no network and wants XDG portals over broad permissions; snaps auto-update (snapd checks four times a day) |

**Default: direct download + Homebrew Cask / winget + a signed AppImage.** Add a store only when its reach justifies
its sandbox and commission.

## Code Signing

Unsigned builds convert at near zero (`00-domain-desktop-app.md` Fork 2), so signing is part of the build, not a
release chore.

### Windows

| Identity | Cost (vendor figures) | Who can get it | SmartScreen |
| --- | --- | --- | --- |
| **Azure Artifact Signing** (formerly Trusted Signing) | $9.99/month Basic (5,000 signatures), $99.99/month Premium; needs a paid Azure subscription | Organisations in the US, Canada, the EU, the UK, Australia, New Zealand, Japan, South Korea, Singapore, Switzerland, Norway and Israel; individuals in the US and Canada only — **not Türkiye** | Reputation builds over releases signed with the same identity — **not instant** |
| **OV code-signing certificate** | about $150–300/year (Microsoft's estimate; reseller prices run higher), plus the hardware token or cloud-HSM signing fee | Any verified organisation | Equivalent to Artifact Signing for SmartScreen |
| EV certificate | $400+/year | Verified organisations | No longer skips SmartScreen (since 2024) — not worth the premium for that |

- **Fabrik default:** Artifact Signing when the legal entity is eligible; otherwise an **OV certificate held in a
  cloud signing service** — the route for an entity registered in Türkiye, which Artifact Signing does not serve. The CA/Browser Forum has required code-signing keys to live in a hardware security
  module since 2023-06-01, and caps certificate validity at 460 days from 2026-03-01 — plan a renewal every year.
  Identity validation takes from one to twenty business days and cannot be expedited: start it at Epic 1.
- **electron-builder:** Artifact Signing is `win.sign` with `type: "azure"` (endpoint, account name, certificate
  profile, publisher name; credentials from `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET`); the
  integration is marked beta. A token- or HSM-held OV certificate signs through `win.sign` with `type: "hsm"` or
  `"pkcs11"`, or a custom sign hook.
- **Timestamp every Windows signature** (RFC 3161; electron-builder sets a timestamp server by default) so the
  signature stays valid after the certificate expires.
- Electron's own code-signing tutorial still says Windows needs an EV certificate; Microsoft's SmartScreen page
  (learn.microsoft.com/windows/apps/package-and-deploy/smartscreen-reputation) says otherwise, and this pack follows
  Microsoft.
- **SmartScreen reputation** accrues to a consistent publisher identity over weeks and hundreds of clean installs;
  an unsigned file starts from zero on every update. **Smart App Control**, where it is on, blocks
  unsigned code outright and lets CA-signed code through when it cannot judge it.

### macOS

- **Apple Developer ID + Hardened Runtime + secure timestamp + notarization**, $99/year (the Apple Developer
  Program).
    - Hardened Runtime: electron-builder `mac.sign.hardenedRuntime: true`.
  - Notarize with `xcrun notarytool` (Apple stopped accepting `altool` uploads in 2023); electron-builder does it
    with `mac.notarize: true` plus App Store Connect API key credentials in the environment (`APPLE_API_KEY`,
    `APPLE_API_KEY_ID`, `APPLE_API_ISSUER`), and staples automatically.
  - **Entitlements:** under the Hardened Runtime, Electron needs at least
    `com.apple.security.cs.allow-jit` and `com.apple.security.cs.allow-unsigned-executable-memory` (in the
    entitlements and the inherited entitlements), or the notarized app does not launch. App-sandbox entitlements
    (`com.apple.security.network.client`, `com.apple.security.files.user-selected.read-write`) apply only with
    `com.apple.security.app-sandbox` — that is, a Mac App Store build. Request only what the app uses.
- **Staple** the ticket so Gatekeeper can verify offline; without it, the first launch needs a network lookup. A
  `.app`, `.dmg` or `.pkg` can be stapled; a ZIP cannot — staple the `.app` inside before zipping.

```bash
electron-builder --mac --publish never        # signs + notarizes + staples
spctl --assess --type execute -vv dist/mac/MyApp.app
codesign --verify --deep --strict --verbose=2 dist/mac/MyApp.app
xcrun stapler validate dist/mac/MyApp.app
```

### Linux

Embed a GPG signature in the AppImage (`appimagetool --sign`) and publish the public key on the download page;
`--appimage-signature` only displays a signature, so users verify with an external tool.

## Auto-Update — your own domain in front of object storage

**Default architecture: `electron-updater` with a `generic` provider** pointing at your own update host — a
**custom domain** in front of a Cloudflare R2 bucket.

```yaml
# electron-builder.yml
publish:
  provider: generic
  url: https://updates.<your-domain>/${os}
```

- **Cloudflare R2** charges no egress, so a large installer downloaded thousands of times costs storage only.
  Serve it through a custom domain: Cloudflare rate-limits the public `r2.dev` URL and says it is for development
  only.
- electron-builder publishes the artifacts and the manifests `electron-updater` reads — `latest.yml` (Windows),
  `latest-mac.yml` (macOS), `latest-linux.yml` (Linux).
- **Updatable targets:** NSIS on Windows (not Squirrel.Windows), DMG plus the **zip** target on macOS (Squirrel.Mac
  needs the zip, and the app must be signed or it will not update), AppImage, DEB and RPM on Linux.
- **Differential updates** use blockmaps (NSIS, AppImage, the macOS zip), so a client downloads only changed
  blocks.
- **Channels:** publish `stable` and `beta` under separate prefixes and point a beta build at its prefix.
- **Update verification:** on Windows, electron-updater checks each downloaded update against the signing
  certificate's publisher name (`win.verifyUpdateCodeSignature`, on by default) and refuses a mismatch. Before a
  certificate change that alters the subject (a new legal name, OV to Artifact Signing), ship a release whose
  `publisherName` lists **both** names — otherwise every installed copy refuses the next update.

```text
client launches → electron-updater fetches https://updates.<your-domain>/win/latest.yml
                → new version: downloads the blockmap difference
                → installs on quit-and-relaunch
```

**Banned:**

- **GitHub Releases on a private repo.** It needs a `GH_TOKEN` inside the app binary (readable with `strings`),
  and electron-builder itself calls that provider "not suitable for all users".
- **Production updates from `r2.dev`** (rate-limited) or from object storage that bills egress, for installers
  over 50 MB.

The update channel is yours alone, so old builds live forever: version-gate the backend and keep a minimum-version
floor (`00-domain-desktop-app.md` Fork 3).

## Native Integrations

### Cross-platform menus

Define the menu in the main process with `Menu.buildFromTemplate` and role-based items (`copy`, `paste`,
`selectAll`) — they get the right platform shortcuts automatically (⌘C on Mac, Ctrl+C elsewhere).

### System tray + dock badges

- Tray icons: `new Tray(iconPath)` — an ICO on Windows; on macOS a Template image at 16x16 plus a 32x32 `@2x`
  file; Linux varies by desktop. Bundle several sizes.
- Dock badge (macOS): `app.dock.setBadge('3')`.
- Windows taskbar overlay icon: `win.setOverlayIcon(icon, description)` on the window instance.

### Deep-link protocol handlers

Register a protocol (`myapp://`) at install time — electron-builder's `protocols:` config — and catch incoming
URLs in the main process:

```js
app.setAsDefaultProtocolClient('myapp');

// macOS: open-url event
app.on('open-url', (event, url) => {
  event.preventDefault();
  handleDeepLink(url);
});

// Windows/Linux: second-instance event (the deep link arrives in argv)
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', (_, argv) => {
    const url = argv.find(a => a.startsWith('myapp://'));
    if (url) handleDeepLink(new URL(url).toString());
  });
}
```

On Windows and Linux a **cold start** delivers the URL in the first instance's own `process.argv` — check it at
startup too. In development (`process.defaultApp`), register with
`app.setAsDefaultProtocolClient('myapp', process.execPath, [path.resolve(process.argv[1])])`.

Use it for links from your website or mail into the app, and for file-type associations (`open with MyApp`). Treat
every deep link as untrusted input. **OAuth callbacks do not use it** (§ Authentication).

### Autostart at login

On macOS and Windows use Electron's API — never poke the registry or LaunchAgents directly:

```js
app.setLoginItemSettings({
  openAtLogin: true,
  args: ['--hidden'],           // Windows only: start in the tray and detect the flag
});
```

It has no Linux implementation: write an XDG autostart `.desktop` entry there. On macOS the app must be signed and
notarized for login items to work reliably.

### Single-instance lock

Mandatory for any app where a deep link or a file double-click should reach the existing window instead of
spawning a second instance:

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

- **Defer heavy `require()`** — load native modules lazily when their subsystem is first used; cold start gets
  faster.
- **`app.requestSingleInstanceLock()`** — see above; it prevents a memory-heavy second Chromium.
- **Renderer process-per-window vs shared** — Electron's defaults are sensible; do not override without measuring.
- **Background work belongs in Utility Processes or workers, not hidden renderers** — § Background Execution.

## Crash Reporting — Sentry / GlitchTip in every process

Application JS errors need the SDK; Electron's built-in `crashReporter` covers native (Chromium) crashes only.

```js
// main process — as early as possible, before any window opens
import * as Sentry from '@sentry/electron/main';
Sentry.init({ dsn: process.env.GLITCHTIP_DSN });

// renderer (and the preload too: with context isolation, preload errors are not captured otherwise)
import * as Sentry from '@sentry/electron/renderer';
Sentry.init({});
```

- Renderer events travel through the main process, which holds the DSN.
- **Native crashes:** the SDK collects minidumps from any Electron process and uploads them on the next start
  (immediately after a renderer crash). Upload debug symbols, or enable the Electron symbol server. Native crash
  handling is off in Mac App Store builds.
- GlitchTip speaks the Sentry protocol — same SDK, its own DSN.
- **Consent first:** nothing is sent until the user opts in (§ KVKK / GDPR).

## Authentication (Connected mode)

**OAuth runs in the system browser, never an embedded webview, and always with PKCE.**

```js
import { shell } from 'electron';
import http from 'node:http';
import crypto from 'node:crypto';

async function login() {
    const verifier = generatePkceVerifier();
  const state = crypto.randomBytes(32).toString('base64url');      // reject a callback whose state differs
  const challenge = await pkceChallenge(verifier);                 // S256
  const server = http.createServer();                              // loopback redirect listener
  await new Promise<void>(r => server.listen(0, '127.0.0.1', r));
  const { port } = server.address() as { port: number };
  const redirect = `http://127.0.0.1:${port}/callback`;
  await shell.openExternal(
    `https://auth.example.com/authorize?client_id=...&code_challenge=${challenge}` +
    `&code_challenge_method=S256&state=${state}&redirect_uri=${encodeURIComponent(redirect)}`
  );
  // wait for GET /callback?code=...&state=... on `server`; check state, then exchange code + verifier
}
```

**Why:**

- The OAuth standard for native apps forbids embedded user-agents and requires PKCE for public clients
  (RFC 8252).
- **Loopback is the redirect that works everywhere:** Google documents only the loopback redirect for desktop
  clients, has withdrawn custom URI schemes for Android and Chrome apps, and blocks embedded webviews
  (`disallowed_useragent`); Microsoft's identity platform also prefers `127.0.0.1` over `localhost`, ignores the
  port when matching, and does not support the IPv6 loopback yet. Use `127.0.0.1` with any port the OS assigns.
- **Send a random `state`** and reject any callback whose `state` does not match (RFC 8252's CSRF defence).
- The system browser has the user's session, 2FA and password manager.
- The `<webview>` tag and an embedded `BrowserWindow` for sign-in are banned.

The fleet's own sign-in uses the OTP code path above and needs no redirect at all. Token storage: `safeStorage`.
Never write tokens to plain disk or environment.

## Sync Architecture (Connected mode)

Optimistic UI + local mutation log + queue-and-replay:

```text
user action → INSERT INTO mutations_pending (action, payload, ts) → UI updates immediately
network up → background sync reads mutations_pending
           → POST batched mutations to the Fabrik backend (app-issued Bearer JWT from fabrik-lib/fastapi-user-auth)
           → on success: DELETE FROM mutations_pending; APPLY canonical state from response
           → on conflict: invoke the conflict resolver (CRDT or last-write-wins per field)
```

**Conflict resolution:**

- **Default: last-write-wins per field** with a server timestamp. Simplest, correct for most apps.
- **CRDT (e.g. Yjs / Automerge)** for real-time multi-device editing of structured documents.
- **Operational Transformation** for intent-preserving edits to ordered text (a collaborative editor).

Per `58-resilience.md`: wrap sync calls with timeout + retry + circuit breaker. On circuit-open, sync pauses and the
local mutation log stays intact.

## Real-Time Backend Updates

For server-pushed updates: **SSE > WebSockets > polling**.

- **Polling** burns battery (Windows Battery Saver and macOS Low Power Mode throttle it).
- **WebSockets** hold a TCP connection — fine for an active window; close it when the window is minimised.
- **SSE** is the simplest server push over HTTPS; it reconnects with `Last-Event-ID`.

Per `12-node.md`: a Node backend serves SSE with Fastify's SSE plugin or a plain streamed response.

## Background Execution — DON'T

Persistent hidden renderer processes for background sync are **banned**: power-saving modes throttle or kill them,
and each keeps a full renderer's memory resident while "doing nothing".

**Instead:** sync on launch and on window focus, and let the backend wake the app with a push notification:

- **Windows:** Windows App SDK push notifications (WNS) with an Azure app registration. Background delivery needs
  package identity (MSIX, or packaging with an external location); an NSIS-installed app is unpackaged and gets
  limited support. They may not work for a
  self-contained or elevated app — check `PushNotificationManager.IsSupported()` and fall back to sync-on-launch.
- **macOS:** APNs is available to Developer ID apps outside the App Store.
- **Linux:** no canonical push; degrade to a tray "Sync now" action.

## Local LLM (Standalone AI mode)

For offline AI features: Ollama as a child process.

```js
import { spawn } from 'node:child_process';

const ollama = spawn('ollama', ['serve'], { stdio: 'inherit' });
// binds 127.0.0.1:11434 by default — native API at /api, OpenAI-compatible at /v1, no key for local calls
```

- Models live on the user's disk at a per-OS default (override with `OLLAMA_MODELS`); Ollama is MIT-licensed.
- Ship Ollama with the app or detect an existing install; bundling adds about 100 MB but removes "install Ollama
  first" friction.
- Keep it on loopback: setting `OLLAMA_HOST` to a public address exposes an unauthenticated API.
- Local inference has no per-token spend (`cost-budget.md`).
- **Constraint:** what runs is bounded by the user's GPU memory. Document the minimum VRAM for the model you ship.

## License Management (Standalone, no backend)

For paid standalone apps with offline licence validation — a signature the app can check without a server:

```js
import crypto from 'node:crypto';

const PUBLIC_KEY = crypto.createPublicKey(`-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----`);

function verifyLicense(licenseFile: Buffer): LicensePayload | null {
  // licenseFile = JSON payload + Ed25519 signature (base64)
  const { payload, signature } = parseLicense(licenseFile);
  const ok = crypto.verify(null, Buffer.from(payload), PUBLIC_KEY, Buffer.from(signature, 'base64'));
  if (!ok) return null;
  const parsed = JSON.parse(payload);
  if (parsed.expires_at < Date.now()) return null;
  return parsed;  // { user_id, tier, features, expires_at }
}
```

- You sign licence files with the private key, kept offline and NEVER in the repo.
- The app ships the public key embedded in code.
- The licence payload carries `user_id`, `tier`, `features`, `expires_at`.
- **Revocation:** ship a blocklist of compromised licence signatures in updates. Limited, and a cracked binary
  skips the check entirely — that is the standalone deal (`00-domain-desktop-app.md` Fork 1).

## KVKK / GDPR Compliance

For a Turkish entity (KVKK) and EU users (GDPR):

- **Telemetry: opt-in only.** Default config = no network egress. The first-run prompt asks; a refusal is silent
  and permanent until the user opts in from Settings. Under GDPR, an installed app that sends telemetry from the
  user's machine falls under ePrivacy Art. 5(3) — the EDPB's guidelines on its technical scope (adopted
  2024-10-07) name laptops and SDK-triggered sends — so it needs consent unless strictly necessary.
- **Crash reporting (Sentry/GlitchTip): opt-in.** Without consent, minidumps stay on the machine.
- **Anonymous IDs** when telemetry is on — no PII in event payloads.
- **Transfers out of Türkiye (KVKK Art. 9, as amended by Law No. 7499 from 2024-06-01):** a transfer needs an
  adequacy decision or an appropriate safeguard — most practically the Board's standard contract, which must be
  notified to the Authority within five business days of signing (binding corporate rules and Board-approved
  commitments are the other safeguards). Explicit consent is now only an exception for incidental transfers, not
  the basis for a routine data flow. A foreign crash-report or telemetry host is a routine transfer: sign and
  notify the standard contract before switching it on.

## Apple Privacy Manifest

- **Mac App Store submissions:** include `PrivacyInfo.xcprivacy` declaring every data category collected; App Store
  Connect enforces the manifest at upload.
- **Required-reason APIs** (boot time, file timestamps, disk space, user defaults) are enforced for Apple's
  iOS-family platforms; Apple's list does not name macOS. Declare them anyway when an SDK you bundle ships its own
  manifest, using codes from Apple's list — never invented ones.
- **Direct download:** Apple states no manifest check for notarization. Write one only if you also ship to the
  Mac App Store.

electron-builder does not generate it — author it by hand from what your native dependencies use.

## Testing — Playwright (Spectron is dead)

```js
// tests/app.spec.ts
import { test, expect, _electron as electron } from '@playwright/test';

test('main window renders', async () => {
  const app = await electron.launch({ args: ['main.js'] });
  const window = await app.firstWindow();
  await expect(window).toHaveTitle('MyApp');
  await app.close();
});
```

- **Spectron** has been deprecated since 2022 — never use it.
- **Playwright's Electron support is experimental** and needs the `enableNodeCliInspectArguments` fuse left on;
  run E2E against a test build that keeps it, and ship release builds with it off.
- **WebdriverIO's Electron service** is the supported alternative when you need it (Chromedriver set up for you,
  Electron API mocking).
- **Mock native OS dialogs** (file picker, save dialog) — they block a test otherwise:

  ```js
  await electronApp.evaluate(({ dialog }) => {
    dialog.showOpenDialog = async () => ({ canceled: false, filePaths: ['/tmp/fixture.txt'] });
  });
  ```

Testing Trophy + Behavior Contract (per `45-testing-strategy.md`) — one integration/E2E test per distinct
user-observable behavior, risk-ordered; **NOT** a wide base of business-logic unit tests:

- **Primary: IPC integration tests** — exercise the preload `contextBridge` surface with mock main handlers (the
  main↔renderer contract is where Electron bugs live).
- **Primary: Playwright E2E** — golden-path user flows, one per behavior; small and fast.
- **Unit (`vitest` per `12-node.md`) ONLY for complex pure algorithms / data transformations.**

---

## Banned Patterns

| Pattern | Use Instead | Reason |
| --- | --- | --- |
| An Electron major outside the three newest stable ones | Upgrade before yours leaves the window | Unsupported majors get no Chromium security fixes |
| `nodeIntegration: true` / `contextIsolation: false` / `sandbox: false` | The three declared explicitly, as above | XSS → instant RCE; disabling isolation also disables the sandbox |
| Exposing `ipcRenderer` (or passing a callback straight to `ipcRenderer.on`) via `contextBridge` | Named, typed methods; wrap callbacks | Raw `ipcRenderer` or `event.sender` = renderer-to-main compromise |
| `ipcMain.handle` without a sender-origin check and a schema | Check `event.senderFrame.origin`, then Zod | The renderer and any frame in it are untrusted |
| No permission handler / unrestricted navigation or new windows | `setPermissionRequestHandler`, deny `will-navigate`, `setWindowOpenHandler` deny | Electron approves every permission by default |
| Default fuses in a release build | `electronFuses` as in § Fuses | `runAsNode` and `NODE_OPTIONS` turn the signed app into a code runner |
| `<webview>` or `BrowserWindow` for OAuth, or a custom-scheme OAuth redirect | System browser + PKCE + `state` + loopback redirect | Embedded sign-in is blocked by Google and forbidden by RFC 8252; Google documents only loopback for desktop |
| `webSecurity: false`, `allowRunningInsecureContent`, `experimentalFeatures`, `enableBlinkFeatures` | Electron's defaults | Each one removes a browser security boundary |
| `keytar` | `safeStorage` (async API) | keytar is archived |
| Storing secrets when `safeStorage` reports `basic_text` | Refuse + warn, or a user passphrase via Argon2id | `basic_text` is a hardcoded key — effectively plaintext |
| `IndexedDB` / `leveldb` for relational data | `better-sqlite3` | IndexedDB lacks SQL; leveldb has no relational support |
| Plain `better-sqlite3` (unencrypted) in production | `better-sqlite3-multiple-ciphers`, SQLCipher, raw random key | KVKK + reasonable user expectation for local sensitive data |
| Throwing exceptions across IPC | Return the `{success, data?, error?}` wrapper | Error objects don't serialize over IPC |
| Paying for an EV certificate to skip SmartScreen | Artifact Signing or an OV certificate, signed consistently | EV no longer bypasses SmartScreen; reputation builds per identity |
| Shipping unsigned or un-notarized builds | Signing in the build pipeline (§ Code Signing) | SmartScreen / Smart App Control / Gatekeeper stop the install |
| GitHub Releases for private-repo auto-update | Generic provider on your own domain | Embedding a GitHub token in the binary leaks it |
| Production updates from `r2.dev` | A custom domain on the R2 bucket | `r2.dev` is rate-limited and for development only |
| Hidden persistent renderer for background sync | Push notifications + sync on launch/focus | Power-saving modes kill them; idle memory |
| Aggressive HTTP polling for backend updates | SSE > WebSockets > polling | Polling burns battery and breaks under throttling |
| Telemetry or crash reports without explicit opt-in | First-run opt-in prompt | ePrivacy Art. 5(3) consent; KVKK transfer rules |
| Spectron for E2E tests | Playwright `_electron.launch()` (or WebdriverIO) | Spectron is deprecated |
| Native OS dialogs blocking automated tests | `electronApp.evaluate(({ dialog }) => ...)` mock | Dialogs are modal; tests hang in CI |
| Hardcoded profile paths | `app.getPath('userData')`, `'crashDumps'`, etc. | Hardcoded paths break relocated profiles and portable installs |

---

## Related Rule Packs

- `core/12-node.md` — main process is Node; SIGTERM drain, structured logging, `crypto.timingSafeEqual()`
- `core/20-typescript.md` — TS-specific patterns (auto-loads on `.ts` files)
- `core/15-api-contracts.md` — request/response contracts when connecting to a Fabrik backend
- `core/35-security-auth.md` — passwordless sign-in, app-issued Bearer JWT (`fabrik-lib/fastapi-user-auth`)
- `core/55-observability.md` — `@sentry/electron` in every process; GlitchTip DSN
- `core/58-resilience.md` — sync queue retry + circuit breaker patterns
- `core/45-testing-strategy.md` — Testing Trophy + Behavior Contract
- `core/design-system-template.md` — token slots, spacing, components and states for the React UI
- `core/ocoron-design-system.md` — color and typography values, when the project declares the house identity
- `core/cost-budget.md` — local LLM via Ollama as an alternative to metered API spend
- `desktop-app/00-domain-desktop-app.md` — the planning layer (§ Epic Decomposition below)

---

## Done When

- [ ] Electron is on one of the three newest stable majors, latest minor.
- [ ] The app's custom scheme is registered privileged before `ready`.
- [ ] All `BrowserWindow` instances declare `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`.
- [ ] A permission request handler, `will-navigate` denial and a `setWindowOpenHandler` deny are installed; CSP is
      sent as a header.
- [ ] Release builds set the fuses in § Fuses (incl. ASAR integrity + `onlyLoadAppFromAsar`).
- [ ] The preload uses `contextBridge.exposeInMainWorld` with named typed methods; no raw `ipcRenderer`.
- [ ] Every `ipcMain.handle` checks `event.senderFrame.origin`, then validates input with Zod, before privileged work.
- [ ] All IPC handlers return the `{success: true, data} | {success: false, error: string}` wrapper.
- [ ] Local SQLite uses `better-sqlite3-multiple-ciphers` (SQLCipher) with a raw random 32-byte key.
- [ ] The master key and tokens are stored via `safeStorage` (async API); never plaintext on disk.
- [ ] Linux: `basic_text` detected → refuse or require a passphrase.
- [ ] Windows: signed with Artifact Signing or an OV certificate in a cloud HSM, RFC 3161 timestamped; renewal date
      tracked, and a certificate change ships a release listing both publisher names first.
- [ ] macOS: Developer ID + Hardened Runtime (with `allow-jit` and `allow-unsigned-executable-memory`) +
      notarization via `notarytool` (`mac.notarize: true`); stapled.
- [ ] macOS entitlements: only those actually needed.
- [ ] Linux: AppImage carries an embedded GPG signature; the public key is on the download page.
- [ ] Auto-update via `electron-updater`, `provider: generic`, on a custom domain (not `r2.dev`); macOS ships the
      zip target; blockmap differential updates enabled.
- [ ] GitHub Releases NOT used for private-repo distribution.
- [ ] `app.requestSingleInstanceLock()`; `second-instance` routes argv (deep links, file paths) to the existing window.
- [ ] Deep-link protocol handler registered; `open-url` (Mac), `second-instance` argv and the cold-start
      `process.argv` (Win/Linux) handled as untrusted input.
- [ ] Autostart via `app.setLoginItemSettings` on macOS/Windows (not the registry / LaunchAgents directly) and an
      XDG autostart entry on Linux.
- [ ] OAuth (if any): system browser, PKCE, a checked `state`, loopback redirect; never `<webview>` or `BrowserWindow`.
- [ ] `@sentry/electron` initialised in main, preload and renderer; opt-in only.
- [ ] Telemetry default: NO network egress until the user opts in; anonymous IDs only.
- [ ] A foreign telemetry/crash host has a signed and notified KVKK standard contract.
- [ ] `PrivacyInfo.xcprivacy` filed if the app ships to the Mac App Store.
- [ ] Sync mode: optimistic UI + local mutation log; queue-and-replay; CRDT or LWW conflict resolution.
- [ ] Real-time backend: SSE preferred over WebSockets over polling.
- [ ] No persistent hidden renderer for background sync.
- [ ] Local LLM (if shipped): Ollama on loopback; minimum VRAM documented.
- [ ] Standalone licensing (if applicable): Ed25519 signature verification with an embedded public key.
- [ ] E2E tests: Playwright `_electron.launch()` against a test build; native dialogs mocked.
- [ ] Spectron NOT used.
- [ ] Ocoron design tokens used for ALL color/spacing/typography (no hardcoded hex or raw px).

---

## Epic Decomposition → `00-domain-desktop-app.md`

The PLANNING layer — vision intake (ICP, monetization, the standalone-vs-connected fork, signing readiness,
unit economics, risk, kill criteria) and the epic-decomposition directives — lives in
**`.windsurf/rules/desktop-app/00-domain-desktop-app.md`**. It is loaded by path from the mega-epic planner,
not by glob.

**This pack owns the code-time facts** (process model, IPC, persistence, § Distribution Channels, § Code
Signing, § Auto-Update, licence verification, testing). The planner cites them; it never restates them.

## Draft Persistence — nothing typed or AI-generated is EVER lost (fleet mandate 2026-08-13)

Every form/wizard/editor/AI-populated surface persists its full working state **continuously on
change** (debounce ≤1s + flush on blur/hide/background) to the local SQLite store (the mandated engine); **restore is automatic and
silent** on every return path (refresh, Back, reopened tab/app, crash, days-old session) — the
user continues down to the last letter typed. The draft clears on exactly ONE event: successful
creation/submission of the entity (or explicit user discard). Canonical detail:
`core/design-system-template.md` § Save Behavior.
