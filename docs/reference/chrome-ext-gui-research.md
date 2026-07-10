# Chrome extension (MV3) GUI toolchain — full research

**Status:** Research reference (the *findings*; the *ruling* lives in `.windsurf/rules/chrome-ext/70-chrome-ext.md` — the authority — and the summary in `docs/reference/gui-toolchain.md` § Chrome extension).
**Live-verified:** 2026-07-07 (every claim sourced below; nothing from training memory).
**Scope:** how an agent BUILDS + VERIFIES an MV3 extension GUI. Context: TS + Preact/Svelte/React; **build tool = WXT** (v0.20.27, MIT — the default per `70-chrome-ext.md` § Build Tooling; auto-manifest, first-party `@wxt-dev/storage`/`@wxt-dev/i18n`), with **Vite + `@crxjs/vite-plugin`** (v2.7.1, healthy — see § tooling health below) as the documented max-control alternative; Ocoron Design System (Compact); surfaces = popup / options / side-panel / content-script overlay (Shadow DOM).

> **Bottom line:** a Chrome extension is *web tech*, so the agent **reuses the web loop** (Playwright MCP + `@axe-core/playwright` + `toHaveScreenshot` + `frontend-design` skill + shadcn MCP) — the design system is the same Ocoron (Compact) `70-chrome-ext.md` already mandates. Only **three** extension-specific additions are needed. Where this doc and `70-chrome-ext.md` differ, the pack wins.

---

## The 2026 fact that reshapes everything

**Chrome removed the `--load-extension` / `--disable-extensions-except` flags from *stable* Chrome as of Chrome 137 (June 2025)** (anti-malware). You can no longer side-load an unpacked extension into a normal installed Chrome — you must drive **Playwright's bundled Chromium** or **Chrome for Testing**. Playwright's docs now say so explicitly. Source: https://developer.chrome.com/blog/extension-news-june-2025 · https://playwright.dev/docs/chrome-extensions (2026-07-07)

## 1. Playwright ↔ MV3 — needs a test FIXTURE, not Playwright MCP

Extensions load only via `chromium.launchPersistentContext()` with a persistent user-data dir + the two extension flags. **Playwright MCP drives an already-running browser and can't inject those args or read `context.serviceWorkers()`, so it cannot bootstrap the extension** — the agent must write/run a `@playwright/test` fixture, and may *additionally* use Playwright MCP for exploratory clicking once loaded.

```ts
// canonical fixture (playwright.dev/docs/chrome-extensions)
export const test = base.extend<{ context: BrowserContext; extensionId: string }>({
  context: async ({}, use) => {
    const pathToExtension = path.join(__dirname, '../dist'); // absolute
    const context = await chromium.launchPersistentContext('', {
      channel: 'chromium',            // 2026: enables HEADLESS extension support
      args: [`--disable-extensions-except=${pathToExtension}`, `--load-extension=${pathToExtension}`],
    });
    await use(context); await context.close();
  },
  extensionId: async ({ context }, use) => {
    let [sw] = context.serviceWorkers();
    if (!sw) sw = await context.waitForEvent('serviceworker');
    await use(sw.url().split('/')[2]); // chrome-extension://<ID>/...
  },
});
```

- **Headless 2026:** `channel: 'chromium'` "allows to run extensions in headless mode" (supersedes the old "extensions can't run headless" rule). Independent guides still find **headed-under-`xvfb`** (`xvfb-run -a npx playwright test`) more reliable in CI — default to headless `chromium`, keep an `xvfb` fallback. Sources: https://playwright.dev/docs/chrome-extensions · https://qaskills.sh/blog/playwright-chrome-extension-testing-manifest-v3-2026 · https://helpmetest.com/blog/playwright-browser-extension-testing/ (2026-07-07)
- **Extension ID / SW:** MV3 uses `context.serviceWorkers()` (MV2 `backgroundPages()` is **no longer loaded by Playwright in 2026**). ID = 3rd path segment of the SW URL.
- **Popup/options/sidepanel:** ordinary extension-origin pages — `page.goto('chrome-extension://<id>/popup.html' | 'options.html' | 'sidepanel.html')`. Navigate directly; don't click the toolbar icon. (Sidepanel had no special support — issue #26693 — but the URL works.)
- **Content-script overlay:** `page.goto('https://host')`, assert your injected DOM via a stable `id`/`data-testid` + auto-waiting `toBeVisible()`. Seed state via `sw.evaluate(() => chrome.storage.local.set(...))`.
- **MV3 SW-restart flake:** workers suspend ~30s idle; **pin Playwright ≥ 1.59** (PR #39476, Mar 2026 keeps the same `Worker` handle across restart). Open flaky-attach bug under CPU load: #39075 (stop/restart-SW workaround).
- **Parallelism:** unique temp user-data dir per worker (`crypto.randomUUID()`), or `''` for auto temp.
- Sources: https://github.com/microsoft/playwright/blob/5790370e/tests/extension/extension-fixtures.ts · https://github.com/microsoft/playwright/pull/39476 · https://github.com/microsoft/playwright/issues/39075 (2026-07-07)

Maturity: high/official. Free, self-hostable.

## 2. A11y (`@axe-core/playwright`) — the one real caveat: CSP

Extension pages enforce a **strict, non-relaxable CSP** (`script-src 'self'`, no `unsafe-eval`/inline). axe historically trips strict CSP via `eval`/`new Function`. **Fix: launch the extension context with `bypassCSP: true`** (Playwright's context option) whenever scanning a `chrome-extension://` page with axe — else false axe failures / `EvalError` on popup/options/sidepanel. Shadow DOM: axe **pierces open shadow roots automatically**; use `fromShadowDom` to scope into a shadow tree; prefer `mode:'open'` shadow roots for testability (closed roots are opaque to everything). Sources: https://github.com/googlechrome/modern-web-guidance/blob/main/skills/chrome-extensions/references/extensions/csp-sandbox.md · https://github.com/dequelabs/axe-core/issues/3301 · https://github.com/dequelabs/axe-core/blob/master/doc/context.md (2026-07-07). Free.

## 3. Visual regression (`toHaveScreenshot`) — pin the surface viewport

Works unchanged (extension pages are real rendered pages). Gotcha: a popup is a fixed ~400px chrome UI, but `goto()`-ing it in a tab renders at the tab viewport — **pin `test.use({ viewport: { width: 400, height: 600 } })`** so the snapshot matches the real popup box. Generate baselines in the same Playwright Docker container as CI. Sources: https://playwright.dev/docs/test-snapshots · https://bug0.com/knowledge-base/playwright-visual-regression-testing (2026-07-07). Free, no SaaS.

## 4. Extension-specific tools worth adding (both free)

- **Chrome DevTools MCP** (Google, Apache-2.0, 46k★, v1.5.0 2026-07-03) now has an **Extensions tool category (5 tools):** `install_extension`, `list_extensions`, `reload_extension`, `trigger_extension_action`, `uninstall_extension` — the piece Playwright MCP lacks (load/reload the unpacked build, *fire the toolbar action*), plus console/perf/heap of the live SW. **Constraints:** off by default (`--category-extensions`); currently **pipe-connection only** (no autoConnect/browserUrl until Chrome 149); point at **Chrome-for-Testing** via `--executablePath` + `--chromeArg=--load-extension=…`. We already have it added user-global. Best use = interactive debug, not the automated gate. Sources: https://github.com/ChromeDevTools/chrome-devtools-mcp · https://github.com/ChromeDevTools/chrome-devtools-mcp/issues/265 (2026-07-07)
- **`vitest-environment-web-ext`** (CRXJS's recommended path) — a Vitest env that spins up Chromium via Playwright and exposes `browser.getPopupPage()`, `browser.getSidePanelPage()`, `browser.loadExtension()` with `compiler:'npm run build'`. Lower-boilerplate than the hand-rolled fixture **if the project is on CRXJS + Vitest**. Source: https://extensionbooster.net/blog/260610-crxjs-chrome-extension-vite-guide-2026/ (2026-07-07)
- CRXJS is healthy: `@crxjs/vite-plugin` v2.7.1 (2026-07-01), ~370k weekly dl, tested Vite 3–8. https://www.npmjs.com/package/@crxjs/vite-plugin (2026-07-07)
- **Verdict:** no bespoke extension MCP needed. Playwright fixture = load+assert backbone; Chrome DevTools MCP = interactive add-on; `vitest-environment-web-ext` = optional ergonomic wrapper on CRXJS+Vitest.

## 5. Bundle-budget gating (the pack sets budgets but names no tool)

**`size-limit` + `@size-limit/preset-app`** (MIT, v12.1.0 Apr 2026, 140k weekly dl): a `.size-limit.json` entry per surface (popup / sidepanel / content-script) with its own `limit`; `size-limit --json` exits non-zero over budget — a clean CI gate. Add `andresz1/size-limit-action` for PR-comment deltas. `preset-app` measures real gzip/brotli size. `vite-bundle-visualizer` is a *diagnostic* treemap (can't gate). Avoid `bundlesize` (unmaintained). Sources: https://github.com/ai/size-limit · https://www.npmjs.com/package/@size-limit/preset-app · https://github.com/andresz1/size-limit-action (2026-07-07). Free/self-hosted.

## 6. MV3 gotchas that change verification

- **Ephemeral SW** — never assume it's alive; re-acquire via `context.waitForEvent('serviceworker')`; seed state via `sw.evaluate(chrome.storage…)` not UI clicks; pin Playwright ≥ 1.59.
- **Strict non-relaxable CSP** — run axe with `bypassCSP:true`; eval-needing code must use a manifest `sandbox` page (relaxed CSP, no `chrome.*`) and talk via `postMessage` (direct `iframe.contentDocument` throws `SecurityError`).
- **Content-script isolated world** — verify overlay behaviour through DOM effects, not shared page globals.
- **Stable Chrome ≥137 can't sideload** — always target bundled Chromium / Chrome-for-Testing in every harness + MCP config.

---

## Verdict — reuse the web loop + exactly these three additions

For chrome-extension GUIs: **web loop (Playwright + `@axe-core/playwright` + `toHaveScreenshot` + `frontend-design` + shadcn MCP) PLUS:**
1. **A Playwright test *fixture* that loads the unpacked build** (`launchPersistentContext('', { channel:'chromium', args:['--disable-extensions-except=…','--load-extension=…'] })`, read ID from the MV3 SW, `goto('chrome-extension://<id>/…')`). Playwright MCP can't load an extension; stable Chrome ≥137 can't sideload. Pin Playwright ≥ 1.59. *(Optional: `vitest-environment-web-ext` if on CRXJS+Vitest.)*
2. **`bypassCSP: true` on the extension context for axe** + a **pinned 400px viewport** for popup screenshots.
3. **`size-limit` + `@size-limit/preset-app`** per-surface budget gate in CI.

**Nice-to-have:** Chrome DevTools MCP `--category-extensions` (already user-global) for interactive load/reload/`trigger_extension_action` + SW console/perf. Everything is **free/self-hostable**; skip Percy/Chromatic/BrowserStack (paid) — `toHaveScreenshot` covers visual diffing.

---

*Sources accessed 2026-07-07. Binding rules: `chrome-ext/70-chrome-ext.md`; cross-surface decision summary: `docs/reference/gui-toolchain.md`.*
