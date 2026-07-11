# Design Spec — chrome-extension scaffold: WXT rebuild (Part B)

**Status:** CONVERGED
**Date:** 2026-07-11
**Author lane:** fabrik AI (the `chrome-extension` scaffold + `.windsurf/rules`; the 8 kits + TS gate stay in fabrik-lib per the chrome-ext-factory handoff Part D)
**Source of truth:** `/opt/fabrik-lib/docs/reference/chrome-ext-factory-fabrik-ai-handoff.md` Part B + the reconciled `.windsurf/rules/chrome-ext/70-chrome-ext.md` (WXT default, shipped this session in eb8c4c2d/db1aacbb/c6c0e1cb).

---

## Goal

Rebuild the `chrome-extension` scaffold's **extension-client lane** (`_scaffold_chrome_extension` in `src/fabrik/scaffold.py`) from **Vite + `@crxjs/vite-plugin`** onto **WXT** — so `fabrik scaffold <name> --type chrome-extension` emits a WXT MV3 extension that **builds green (`wxt build`) out of the box**, matching the now-canonical `70-chrome-ext.md` § Build Tooling. The bundled FastAPI **backend lane (`server/`) is unchanged**. Success = a fresh scaffold `pnpm install` → `wxt build` (exit 0, `.output/chrome-mv3/manifest.json` emitted) → `size-limit` per surface, with the reconciled rule's MV3 disciplines (auth/observability/resilience) present as working seams.

**Why now:** the rule already declares WXT the default fleet-wide, but the scaffold still emits `@crxjs` (`scaffold.py` has 5 `@crxjs` refs, 0 WXT) — the code contradicts the canonical rule. This is the Lesson-89 discipline applied ahead of time: the scaffold isn't done until the **bundler build** (`wxt build`, pure Node → runs in WSL) is green, not just static gates.

---

## Chosen approach — WXT-native rebuild, faithful port (Approach A)

Replace the extension lane; keep the two-faced split. `extension/` becomes a WXT project; `server/` stays a Pattern-A FastAPI backend.

**Grounded WXT facts** (context7 `/wxt-dev/wxt`, fetched 2026-07-11):
- **File-based `entrypoints/`** — `background.ts`, `popup/`, `options/`, `content.ts` — WXT bundles each. (`docs/guide/essentials/project-structure.md`)
- **`wxt.config.ts`** is the main config; **the manifest is auto-generated** (never hand-written) into `.output/{target}/manifest.json` from `wxt.config.ts` + entrypoint options + modules. (`docs/guide/essentials/config/manifest.md`)
- **Default build output `.output/chrome-mv3/`** (overridable via `outDir`); scripts `dev: wxt`, `build: wxt build`, `zip: wxt zip`, `postinstall: wxt prepare`. (`docs/guide/installation.md`)
- **`srcDir` overridable** — we set `srcDir: 'src'` to match Fabrik convention (entrypoints under `extension/src/`).
- **Vite plugins integrate** via `wxt.config.ts` `vite: () => ({ plugins: [...] })` — so the existing **Ocoron Tailwind/Uniwind + `@hey-api/openapi-ts`** toolchain carries over unchanged. (`docs/guide/essentials/config/vite.md`)
- **`@wxt-dev/i18n`** via `modules: ['@wxt-dev/i18n']` + manifest `name: '__MSG_extName__'` + `default_locale: 'en'`. (`packages/i18n/README.md`)
- **`@wxt-dev/storage`** needs the `storage` permission; typed `storage.defineItem`. (`docs/storage.md`)
- **`createShadowRootUi`** for content overlays: `defineContentScript({ cssInjectionMode: 'ui', async main(ctx){ const ui = await createShadowRootUi(ctx,{name,position,anchor,onMount,onRemove}); ui.mount() } })` — Preact mounts via the framework `onMount`. (`docs/guide/essentials/content-scripts.md`)

**UI framework = Preact** — resolved from the rule, not preference: `70-chrome-ext.md` § Framework Choice prescribes "Preact for minimal popup UIs where bundle size is the primary constraint"; § Bundle Budgets demands single-digit-KB popups; React is explicitly reserved "only for complex side-panel or application-like flows" — a base scaffold (popup + options + one content overlay) is the minimal, bundle-constrained case. Preact keeps JSX/hooks (Ocoron components + the design-review loop still apply) at a ~3KB runtime. This matches the fabrik-lib handoff **§ B.3** independently.

**`preact/compat` is MANDATORY, not optional (handoff § B.3).** The scaffold adds **`@preact/preset-vite`** to `wxt.config.ts` (`vite: () => ({ plugins: [preact()] })`) — the preset **auto-aliases `react`/`react-dom` → `preact/compat`** (its `reactAliasesEnabled` default) and wires Preact JSX + HMR (prefresh). WXT has **no** official Preact module (`@wxt-dev/module-preact` does not exist — verified 404); Preact is configured via the Vite plugin per WXT's "any framework with a Vite plugin" guidance (grounded against `haroonwaves/idb-crud/wxt.config.ts` + WXT frontend-frameworks docs, 2026-07-11). This is the load-bearing seam: the fabrik-lib **UI-bearing kits ship React-API (JSX + hooks) components**, and the `preact/compat` alias is what lets them (and shadcn/Radix) render on the Preact default without pulling React's runtime. Without it, every future kit UI breaks on the scaffold. **React escape hatch:** a project with a genuinely complex side-panel app may override the scaffold to real React — swap `@preact/preset-vite` for the official **`@wxt-dev/module-react`** (`modules: ['@wxt-dev/module-react']`) + `react`/`react-dom` — the scaffold documents this override path in `extension/README` so a heavy side-panel isn't stuck on Preact. **Validate-early (a plan step, not a scaffold file):** smoke-test shadcn/Radix + the `@axe-core/playwright` design-review loop under `preact/compat` on the first kit UI (auth-kit login) — if rough, take the React override for that surface.

### Rejected alternatives
- **B — keep `@crxjs`, just modernize** (bump beta→2.7.1, add the deps/snippets, stay on Vite+CRXJS). Rejected: contradicts the canonical "WXT default" rule; `@crxjs` is the documented *max-control alternative*, not the scaffold default. Would leave code disagreeing with the fleet rule.
- **C — dual-tool scaffold** (`--build-tool wxt|crxjs` flag, two code paths). Rejected: YAGNI + double maintenance; the rule makes WXT the one default and `@crxjs` a documented manual swap, not a scaffold option. One default, one code path.
- **React as the UI default.** Rejected: the rule reserves React for complex app-like flows; a base scaffold's popup is exactly the bundle-constrained case the rule assigns to Preact.

---

## fabrik-lib vendor→enhance→build verdict

fabrik-lib has **no `chrome-ext-*` kits yet** (verified: no `chrome-ext-*` dirs, no extension rows in `fabrik-lib/README.md` — they are Part D, per-kit spec→build cycles not yet run). **Consequence: the scaffold vendors NO kits** — it ships the WXT base + base libs, and `docs/reference/SEAMS.md` (already in the scaffold) documents where a project vendors each kit once it exists. This keeps the scaffold buildable today and avoids importing modules that don't exist.

| Capability | Verdict | Source / why |
|---|---|---|
| Extension build framework | **USE WXT** (`wxt` v0.20.27, MIT) | The framework; rule default. Not a fabrik-lib concern. |
| Typed settings/i18n | **USE `@wxt-dev/storage` + `@wxt-dev/i18n`** | WXT first-party modules (rule § State Management / i18n). |
| Typed API client | **USE `@hey-api/openapi-ts`** (pin 0.99.x) | Same generated-client pattern as the mobile-app scaffold; no fabrik-lib module. |
| Crash reporting | **USE `@sentry/browser`** (v10.65.0) | Isolated `BrowserClient` in content scripts per rule § Observability. No fabrik-lib client-side module. |
| Runtime permissions / dynamic content scripts | **USE fregante bloc** — `webext-permission-toggle@6.0.1`, `webext-dynamic-content-scripts`, `webext-permissions` | rule § Permissions (v6.0.1 per this session's `/fabrik-review` fix — v7.0.0 does not exist). |
| Cross-context messaging | **USE `webext-bridge`** (default; `trpc-chrome` = documented heavier alternative) | Leaner, fewer moving parts (1c lean bias). Overridable per project. |
| UI state | **USE Zustand + `@webext-pegasus/store-zustand`** (cross-context) + `@wxt-dev/storage` (persisted) | rule § State Management. |
| SPA wait-for-element | **USE `element-ready`** (v9.0.2, MIT) | rule § Surfaces. |
| Product analytics (optional) | **USE `posthog-js`** core/no-external build *or* GA4 Measurement Protocol | rule § Observability; behind a `storage`+`alarms` queue. |
| 8 chrome-ext kits (auth/billing/analytics/platform/dist/test/ai/capture) | **DO NOT vendor** — don't exist yet (Part D) | Projects vendor them later; `SEAMS.md` marks the binding points. |
| Backend (`server/`) | **UNCHANGED** — minimal Pattern-A FastAPI | Not in this rebuild's scope. |

**🆕 fabrik-lib candidates:** none — everything is an external npm lib (framework/ecosystem), a WXT-first-party module, or a not-yet-built kit already tracked in Part D. No new generic reusable module surfaces from this scaffold work.

---

## Architecture — scaffold output layout

```
<project>/
├─ extension/                     # WXT project (client lane) — REBUILT
│  ├─ wxt.config.ts               # srcDir:'src', modules:[@wxt-dev/i18n], vite:()=>({plugins:[tailwind, preact()]}) — preact() auto-aliases react→preact/compat + JSX/HMR; manifest{name,permissions,default_locale}
│  ├─ package.json                # WXT deps (below); scripts dev/build/zip/postinstall(wxt prepare)
│  ├─ tsconfig.json               # extends .wxt/tsconfig
│  ├─ .size-limit.json            # per-surface budgets (popup/options/content)
│  ├─ src/
│  │  ├─ entrypoints/
│  │  │  ├─ background.ts          # onInstalled → onboarding + commands/context-menus/omnibox registration
│  │  │  ├─ popup/{index.html,main.tsx,app.tsx}
│  │  │  ├─ options/{index.html,main.tsx,app.tsx}   # settings auto-save over @wxt-dev/storage
│  │  │  └─ content.ts             # createShadowRootUi Preact overlay (cssInjectionMode:'ui')
│  │  ├─ lib/{storage.ts,api/(generated),sentry.ts,messaging.ts,consent.ts}
│  │  ├─ components/ui/            # Ocoron (Compact) Preact components + tokens
│  │  └─ locales/en.json, tr.json # @wxt-dev/i18n
│  └─ public/                      # icons (real placeholder PNGs, existing generator)
├─ server/                        # FastAPI backend (python-api) — UNCHANGED
├─ Dockerfile, compose.yaml       # backend deploy — UNCHANGED
└─ docs/reference/SEAMS.md        # kit binding points — kept
```

**Native snippets** (rule handoff Part B.2, in `entrypoints/background.ts` unless noted):
1. **Onboarding** — `browser.runtime.onInstalled.addListener(({reason}) => { if (reason==='install') browser.tabs.create({url: browser.runtime.getURL('/onboarding.html')}) })`.
2. **Commands / context-menus / omnibox** — register `browser.contextMenus.create(...)` **inside `onInstalled`** (SW is ephemeral); `browser.commands.onCommand`; optional `browser.omnibox`.
3. **Settings auto-save** — a Preact hook over `@wxt-dev/storage` `defineItem` (typed + `migrations`), debounced write.
4. **Shadow-DOM mount** — `createShadowRootUi` with `cssInjectionMode:'ui'`, Preact `onMount`/`onRemove`; mind the `rem` caveat (rule § Surfaces) — overlays use `px`.

**Data flow:** popup/options/content → typed hey-api client (`EXPO_PUBLIC`-style `VITE_PUBLIC_API_URL`) → FastAPI `server/`. Tokens in `chrome.storage.session` (TRUSTED_CONTEXTS; content scripts via SW-mediated messaging per rule § Auth). Manifest auto-generated by WXT.

**Error/failure handling:** `wxt build` failure = scaffold defect (the gate). Sentry isolated `BrowserClient` in content; analytics behind `storage`+`alarms` queue (survive SW death); auth fails closed.

---

## Scaffolder + governance changes (the actual code delta)

1. **`_scaffold_chrome_extension`** — rewrite the extension lane: emit `wxt.config.ts` (incl. `@preact/preset-vite` in `vite().plugins`, which auto-aliases `react`→`preact/compat` per § B.3, so kit React-API components render), `entrypoints/*`, Preact surfaces, `lib/*`, `.size-limit.json`, `locales/*`; **drop** `extension/manifest.json` (auto-generated) + `extension/vite.config.ts`; move icons to `public/`.
2. **`package.json`** (extension) — WXT dep set (Part B.1, minus kit-owned libs): `wxt`, `@wxt-dev/storage`, `@wxt-dev/i18n`, `preact`, `@hey-api/openapi-ts` (0.99.x), `@sentry/browser` (10.65.0), `webext-bridge`, `webext-permission-toggle@6.0.1`, `webext-dynamic-content-scripts`, `webext-permissions`, `element-ready`, `zustand`, `@webext-pegasus/store-zustand`, tailwind; devDeps **`@preact/preset-vite`** (the WXT+Preact mechanism — auto-aliases react→preact/compat), `size-limit`+`@size-limit/preset-app`, `@playwright/test` (≥1.59), `@axe-core/playwright` (MPL-2.0, dev-only). Scripts: `dev:wxt`, `build:wxt build`, `zip`, `postinstall:wxt prepare`, `size-limit`.
3. **`TYPE_REQUIRED_FILES["chrome-extension"]`** — replace `extension/manifest.json` + `extension/vite.config.ts` with `extension/wxt.config.ts` + `extension/package.json`.
4. **`templates/chrome-extension/manifest.json.j2`** — remove/repurpose (WXT auto-generates; manifest fields move into `wxt.config.ts`). Keep `defaults.yaml`/`compose.yaml.j2`.
5. **`deploy_validator.py`** — confirm the chrome-extension path doesn't require `extension/manifest.json` (it validates the backend lane + compose; the extension binary isn't `fabrik apply`-deployed). Adjust if it asserts the old file.
6. **eslint/tsconfig** — apply the mobile-app lessons pre-emptively: ignore generated (`.wxt/`, `.output/`, `src/lib/api/generated/**`) in eslint + tsconfig; antfu `markdown:false`/`yaml:false` (Lesson: governance `.md`/`.yaml` crash the linter).

**Shape/infra:** scaffold type `chrome-extension` (exists). **No `shape:` flag change** — the extension is client-side (not `fabrik apply`-deployed); the backend lane is unchanged (still deployed, `/health`, `/metrics`, GlitchTip). Backend `shape.*` untouched.

---

## Testing / verification (the gate — build-is-the-gate, Lesson 89)

Fresh `create_project(chrome-extension)` → `pnpm install` (in `extension/`) → **`wxt build`** (exit 0; assert `.output/chrome-mv3/manifest.json` exists) → **`size-limit`** (per-surface budgets pass) → `pnpm exec tsc --noEmit` (0) → `eslint .` (0 errors). The Playwright load-extension fixture (`channel:'chromium'`, `--load-extension=.output/chrome-mv3`, `@axe-core/playwright` `bypassCSP:true`) + `/design-review` are the **GUI build-verification loop** run per-surface at build/plan time (rule § Testing) — the plan wires them; this spec fixes the toolchain. Backend: `PYTHONPATH=server/src pytest server/tests`.

**Behaviors to cover** (for the plan's Behavior Contract): (a) `wxt build` emits a valid MV3 manifest with the declared permissions; (b) onboarding opens only on `reason==='install'`; (c) settings auto-save round-trips through `@wxt-dev/storage`; (d) the content overlay mounts in an open shadow root and uses `px` (not `rem`); (e) tokens never leave the trusted context (content script reads via SW message); (f) a React-API component (JSX + `useState`) renders correctly under the `preact/compat` alias — the smoke test that proves the fabrik-lib kits' React-API components will run on the Preact default.

---

## Constraints (Global)
- WXT is pure Node → `wxt build` runs in WSL (unlike RN native). The **CWS/production ZIP** is `wxt zip` (also WSL-runnable); no cloud-build dependency (unlike EAS). Naming kebab-case. Backend `postgres-main`/`redis-main` (unchanged). No host `ports:`; Traefik; per-service memory limits (backend compose, unchanged).

## Open / blocking unknowns
- **RESOLVED — UI framework:** Preact (from the rule) **with `preact/compat` mandatory** (handoff § B.3 — kit React-API components render on it) + a documented React escape hatch.
- **RESOLVED — messaging lib:** `webext-bridge` default (leaner); `trpc-chrome` documented alternative.
- **RESOLVED — kits:** not vendored (don't exist); SEAMS.md marks binding points.
- **SELF-SERVICE — `deploy_validator` assertion on `extension/manifest.json`:** the executor greps `deploy_validator.py` for a chrome-extension `manifest.json` requirement and removes/relaxes it if present (the file no longer exists under WXT). Probe: `grep -n "manifest.json" src/fabrik/scaffold.py` for the `_NO_*`/required-files sets. No user input needed.
- **SELF-SERVICE — Tailwind-in-WXT plugin exact name:** the executor confirms the Ocoron Tailwind Vite plugin import against the installed version at build time (the `vite:()=>({plugins})` seam is grounded; the specific plugin package is a build-time detail the `wxt build` gate verifies). No user input needed.
- No BLOCKING external unknowns — WXT structure/build, all deps' versions/licenses, and the fabrik-lib kit-absence are grounded this session.

## Handoff
After **CONVERGED** + user approval → **`/fabrik-plan-after-chat <this spec>`** — NOT `/fabrik-data-contract` or `/fabrik-ui-design`. Rationale (pre-empting the "chrome-extension ∈ GUI types → ui-design" default): this work is **hub-side scaffolder tooling** in `/opt/fabrik` (rewriting `_scaffold_chrome_extension` + governance), **not a chrome-extension project**. There is no product data model to freeze (no `docs/data-contract.md`) and no product UI to design (no `docs/ui-design.md`) — the scaffold's surfaces already follow the **frozen Ocoron (Compact) design system** in `70-chrome-ext.md` § Ocoron Design System + § Surface Inventory, which the rule owns. The GUI-contract freezes apply when *building a specific extension*, not when *rebuilding the template that emits them*. The plan does the full `.windsurf/rules`/`AGENTS.md`/scaffold-internals grounding + the build-verified (`wxt build`) phases. **💡 fabrik-lib candidates:** none.
