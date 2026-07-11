# Plan — chrome-extension scaffold: WXT rebuild (Part B)

**Status:** CONVERGED
**Spec:** `docs/superpowers/specs/2026-07-11-chrome-ext-wxt-scaffold-design.md` (CONVERGED, md5 `431ed0d4`) — the grounded source of truth; inherit its vendor verdict + external facts, do not re-derive.
**Scope:** hub-side scaffolder work in `/opt/fabrik` — rebuild the `chrome-extension` scaffold's **extension-client lane** from Vite+`@crxjs` onto **WXT**. Backend lane (`server/`) unchanged.

## What we already agreed (from the spec + this chat)
- **Goal:** `fabrik scaffold <name> --type chrome-extension` emits a **WXT** MV3 extension that **builds green (`wxt build`) out of the box**, matching the canonical `70-chrome-ext.md` § Build Tooling (WXT default). Backend `server/` untouched.
- **UI framework = Preact** (rule-grounded: § Framework Choice + § Bundle Budgets; React reserved for complex flows) via **`@preact/preset-vite`** (auto-aliases `react`→`preact/compat` + JSX/HMR — WXT has no `@wxt-dev/module-preact`). `preact/compat` is MANDATORY (kits ship React-API components). React escape hatch = swap to `@wxt-dev/module-react`.
- **Rejected:** keep `@crxjs` (contradicts the rule); dual-tool flag (YAGNI); React default (rule reserves it for complex flows).
- **fabrik-lib verdict:** no `chrome-ext-*` kits exist → scaffold vendors NONE; `SEAMS.md` marks binding points.
- **Gate discipline (Lesson 89):** the **bundler build IS the gate** — `wxt build` (pure Node, runs in WSL) + `size-limit`, not just test/type-check/lint. Run the build BEFORE lint so codegen files are in scope.
- **No `shape:` change** — extension is client-side; backend lane unchanged.

**Branch: RICH** (spec pins goal + approach). Skipped brainstorming.

## Global Constraints (every phase inherits)
- Emitted extension is **WXT** (`wxt` v0.20.27) + **Preact** via `@preact/preset-vite`; TS/ESM (`12-node.md`).
- Build output `.output/chrome-mv3/` (WXT default); manifest **auto-generated** (never a hand-written `manifest.json`).
- Deps (extension `package.json`): `wxt`, `preact`, `@wxt-dev/storage` (1.2.8), `@wxt-dev/i18n` (0.2.6), `@hey-api/openapi-ts` (0.99.x), `@sentry/browser` (10.65.0), `webext-bridge` (6.0.1), `webext-permission-toggle` (**6.0.1**, NOT v7), `webext-dynamic-content-scripts`, `webext-permissions`, `element-ready` (9.0.2), `zustand`, `@webext-pegasus/store-zustand` (0.3.6), tailwind; devDeps `@preact/preset-vite`, `size-limit`+`@size-limit/preset-app`, `@playwright/test` (≥1.59), `@axe-core/playwright` (MPL-2.0, dev-only). Scripts: `dev:wxt`, `build:wxt build`, `zip:wxt zip`, `postinstall:wxt prepare`, `size-limit`.
- `scaffold.py` is Python (`10-python.md`): typed, no hardcoded paths, ESM output for the extension.
- **Shared-master:** `scaffold.py`/CHANGELOG are sibling-touched — pathspec commits only, never `git add -A`.

## Context Ledger
| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/chrome-ext/70-chrome-ext.md` (ACTIVE) | the emitted extension must satisfy MV3 disciplines (WXT default, surfaces, auth `storage.session`, isolated Sentry, permissions, Shadow-DOM `rem` caveat, size-limit gate) | the reconciled rule (shipped this session `eb8c4c2d`/`c6c0e1cb`) |
| `.windsurf/rules/core/12-node.md` (ACTIVE) | the extension is TS/ESM, npm hygiene (`--ignore-scripts`) | pack |
| `.windsurf/rules/core/10-python.md` (ACTIVE) | `scaffold.py` typing/patterns | pack |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | Chrome-ext testing = Playwright bundled-Chromium fixture; behavior tests | pack § Chrome Extension |
| `fabrik-lib` (no chrome-ext kits) | vendor NONE — kits don't exist (Part D); SEAMS.md marks binding points | `ls /opt/fabrik-lib/chrome-ext-*` → none |
| WXT (external) | build model: `entrypoints/`, `wxt.config.ts`, auto-manifest → `.output/chrome-mv3`, `srcDir` override, Vite-plugin seam | context7 `/wxt-dev/wxt` (2026-07-11) |
| `@preact/preset-vite` (external) | `plugins:[preact()]` auto-aliases react→preact/compat + JSX/HMR | preactjs/preset-vite README (2026-07-11) |
| `TYPE_REQUIRED_FILES` | chrome-extension required-files set must flip (drop `manifest.json`, `vite.config.ts`→`wxt.config.ts`) | `scaffold.py:338-346` |
| i18n adapter | the `"chrome"` strategy copies `chrome_messages.py` — switch to `@wxt-dev/i18n` | `scaffold.py:190,4881-4886` |
| `shape:` flags | **no change** — extension client-side; backend unchanged | spec § Shape/infra |

💡 **fabrik-lib candidates:** none (all external npm / WXT-first-party / not-yet-built kits).

---

## Phase A — WXT foundation that BUILDS (the load-bearing phase)

**Deliverable:** `_scaffold_chrome_extension`'s extension lane emits a WXT project skeleton + config + deps that `wxt build`s green. Governance flipped. No product UI yet (stub surfaces).

**Files:**
- **Modify** `src/fabrik/scaffold.py` — `_scaffold_chrome_extension` (`:3797-4297`): replace the extension-lane emit (`extension/manifest.json`, `extension/src/popup.html|ts`, `background.ts`, `content.ts`, `extension/vite.config.ts`, `extension/package.json` `:3924-3940`) with the WXT layout: `extension/wxt.config.ts`, `extension/package.json` (Global-Constraints deps), `extension/tsconfig.json` (extends `.wxt/tsconfig`), `extension/.size-limit.json`, `extension/src/entrypoints/{background.ts, popup/index.html+main.tsx, options/index.html+main.tsx, content.ts}` (stubs), `extension/src/locales/{en,tr}.json`, icons → `extension/public/icon{16,48,128}.png` (reuse `_write_placeholder_png` `:3760`). Drop `manifest.json`/`vite.config.ts` emission.
- **Modify** `src/fabrik/scaffold.py:338-346` — `TYPE_REQUIRED_FILES["chrome-extension"]`: remove `"extension/manifest.json"` + `"extension/vite.config.ts"`; add `"extension/wxt.config.ts"`. Keep `extension/package.json`, Dockerfile, compose.yaml, Makefile.
- **Modify** `src/fabrik/scaffold.py:190,4881-4886` — chrome-extension i18n: drop the `"chrome"` `chrome_messages.py` strategy for chrome-ext; `@wxt-dev/i18n` owns locales (`src/locales/*.json`). (Self-service: if other types use `strategy=="chrome"`, leave those; only chrome-extension changes.)
- **Delete/repurpose** `templates/chrome-extension/manifest.json.j2` — WXT auto-generates; manifest fields (`name:'__MSG_extName__'`, `permissions`, `default_locale:'en'`) move into `wxt.config.ts`. Keep `defaults.yaml`, `compose.yaml.j2`.
- **Add** eslint/tsconfig ignores in the emitted extension (`.wxt/`, `.output/`, `src/lib/api/generated/**`) + antfu `markdown:false`/`yaml:false` (Lessons 78/89 — governance files crash the linter; generated files trip it).

**wxt.config.ts (emitted):** `defineConfig({ srcDir:'src', modules:['@wxt-dev/i18n'], vite:()=>({ plugins:[tailwindcss(), preact()] }), manifest:{ name:'__MSG_extName__', description:'__MSG_extDescription__', default_locale:'en', permissions:['storage','activeTab'] } })`. `preact()` (from `@preact/preset-vite`) auto-aliases react→preact/compat.

**Interfaces — Produces:** the emitted `extension/` WXT layout (paths above); `wxt.config.ts` with the preact+i18n+tailwind wiring. **Consumes:** nothing (first phase).

**Behavior Contract (risk-ordered):**
1. **[RISK, TDD]** a fresh `create_project(chrome-extension)` → `pnpm install` (in `extension/`) → `wxt build` exits 0 and writes `.output/chrome-mv3/manifest.json` with `permissions:['storage','activeTab']`. *(TDD: write the build-assert test first; watch it FAIL against the current @crxjs scaffold, then implement.)*
2. `TYPE_REQUIRED_FILES["chrome-extension"]` no longer lists `manifest.json`/`vite.config.ts`; lists `wxt.config.ts`.

**Steps:**
1. **[TDD-red]** Add `tests/test_scaffold_chrome_ext_wxt.py::test_wxt_build_green` — scaffold to a tmp dir, `pnpm install` + `wxt build`, assert exit 0 + `.output/chrome-mv3/manifest.json` exists with the permissions. Run it → **confirm RED** (current scaffold emits @crxjs, no wxt). Gate: `pytest tests/test_scaffold_chrome_ext_wxt.py -k build -x` → fails for the right reason (no `wxt.config.ts`).
2. Rewrite `_scaffold_chrome_extension` extension lane per Files above. Emit `wxt.config.ts`, `package.json` (deps), `tsconfig.json`, `.size-limit.json`, `entrypoints/*` stubs, `locales/*`, icons→`public/`.
3. Flip `TYPE_REQUIRED_FILES` (`:338-346`); switch i18n (`:190,4881-4886`); delete `manifest.json.j2`; add eslint/tsconfig ignores to the emitted config.
4. **[TDD-green]** Re-run step-1 test → **GREEN**.
5. **Gate (build-is-the-gate, run in this order):** `rm -rf /tmp/rncx && .venv/bin/python -c "from pathlib import Path; from fabrik.scaffold import create_project; create_project('cxwxt','x',base=Path('/tmp/rncx'),project_type='chrome-extension',generate_spec=False)"` → `cd /tmp/rncx/cxwxt/extension && pnpm install && npx wxt build` → **exit 0, `.output/chrome-mv3/manifest.json` present** → `pnpm exec tsc --noEmit` (0) → `pnpm exec size-limit` (pass) → `pnpm exec eslint .` (0 errors). Expected: all green.
6. `python scripts/enforcement/check_doc_sync.py` — resolve any WARNING whose trigger file is in this phase's diff (INDEX.md for `manifest.json.j2` removal).
7. **`/fabrik-review`** on the changed surface (`_scaffold_chrome_extension` + `TYPE_REQUIRED_FILES` + the emitted config) — BLOCKING, pool-default finders (`run_agents`, `pick_models("review")`, `record_agent_run`) + native `fabrik-reviewer` (touches scaffolder + shared file), refute → prove-before-fix → re-run finders until a no-op pass (0 CONFIRMED/PLAUSIBLE). Re-run step-5 gate after each fix.
8. Commit (pathspec: `src/fabrik/scaffold.py tests/test_scaffold_chrome_ext_wxt.py templates/chrome-extension/ INDEX.md`; trailers `Agent-Role: orchestrator`, `Agent-Phase: A`). Mark Phase A `✅ EXECUTED <date> (<commit>)` in this file; stage the plan file in the commit.

---

## Phase B — Surfaces + seams + native snippets

**Deliverable:** the WXT skeleton fleshed to a working minimal extension — Preact Ocoron surfaces, the MV3 lib seams, and the 4 native snippets — still `wxt build` green, with the behaviors tested.

**Files (emitted by `_scaffold_chrome_extension`, added in this phase):**
- `entrypoints/background.ts` — onboarding (`onInstalled`→`reason==='install'`), commands/context-menus/omnibox (registered **inside** `onInstalled`).
- `entrypoints/popup/{index.html,main.tsx,app.tsx}`, `entrypoints/options/{...}` (settings auto-save), `entrypoints/content.ts` (`createShadowRootUi`, `cssInjectionMode:'ui'`, Preact overlay, `px` not `rem`).
- `src/lib/{storage.ts (@wxt-dev/storage defineItem), api/client.ts (hey-api base URL), sentry.ts (isolated BrowserClient in content), messaging.ts (webext-bridge), consent.ts}`.
- `src/components/ui/*` — Ocoron (Compact) Preact components + tokens (from `70-chrome-ext.md` § Ocoron Design System).

**Interfaces — Consumes:** Phase-A `wxt.config.ts` + entrypoint stubs. **Produces:** the seam module signatures `SEAMS.md` documents (storage `getItem/setItem`, `sentryInit()`, `sendMessage`), consumed by future kits.

**Behavior Contract (risk-ordered):**
1. **[RISK, TDD]** a React-API component (`import {useState} from 'react'` + JSX) renders under `@preact/preset-vite`'s `preact/compat` alias — proves kit React-API components run. *(TDD: write first, watch fail without the preset, then wire.)*
2. onboarding opens the packaged onboarding page **only** on `reason==='install'` (not `update`).
3. settings auto-save round-trips through `@wxt-dev/storage` `defineItem`.
4. the content overlay mounts in an **open** shadow root and styles with `px` (rem-caveat).
5. tokens live in `storage.session` (trusted); a content script reads via `webext-bridge` SW message, never a direct `storage.session` read.

**Steps:**
1. **[TDD-red]** Add the preact/compat-render test (Playwright load-extension fixture per `70-chrome-ext.md` § Testing — `channel:'chromium'`, `--load-extension=.output/chrome-mv3`); confirm RED without the preset.
2. Emit the surfaces + seams + snippets. Sentry = isolated `BrowserClient`+`Scope` in content (never global `Sentry.init`) per rule.
3. **[TDD-green]** re-run → GREEN. Add tests for behaviors 2–5.
4. **Gate:** rebuild (`wxt build` exit 0) → the behavior tests pass → `size-limit` per surface (popup single-digit-KB) → `tsc` 0 → `eslint` 0.
5. **GUI Build-Verification Loop (BLOCKING, per `/fabrik-ui-design` + `70-chrome-ext.md`):** for popup/options/content — the Playwright load-extension fixture drives the built surface; `@axe-core/playwright` `bypassCSP:true` + `toHaveScreenshot` (400px popup) + `size-limit`; `/design-review` against the Ocoron system; iterate to `found:0, fixed:0`.
6. `check_doc_sync.py` + update `docs/reference/SEAMS.md` (seam signatures) + `docs/FEATURES.md`.
7. **`/fabrik-review`** on the changed surface — BLOCKING, pool finders + native for the auth/Sentry seams (high-risk), looped to a no-op. Re-run gate after each fix.
8. Commit (pathspec; `Agent-Phase: B`). Mark Phase B EXECUTED; stage the plan file.

---

## Phase C — Scaffolder tests + docs convergence

**Deliverable:** the content-asserting scaffolder tests match the WXT structure; docs converged.

**Files:**
- **Modify** `tests/test_scaffold.py`, `tests/test_scaffold_logging.py`, `tests/test_deploy_validator.py`, `tests/orchestrator/test_template_defaults.py` — any assertion on the old chrome-ext `@crxjs`/`vite.config.ts`/`extension/manifest.json` structure → assert the WXT structure (`wxt.config.ts`, no `manifest.json`). (Lesson 78: content-asserting tests drift when the generator changes — update in lockstep.)
- **Modify** `CHANGELOG.md` (atop `[Unreleased]`, append-only — sibling active), `INDEX.md` (files added/removed), `docs/SERVICES.md`/`OPERATIONS.md` only if the backend compose changed (it didn't — skip).

**Interfaces — Consumes:** Phases A+B emitted structure. **Produces:** green scaffolder test suite.

**Behavior Contract:** the scaffolder test suite asserts the WXT structure and passes.

**Steps:**
1. Grep the four test files for `chrome-extension`/`vite.config`/`@crxjs`/`extension/manifest` assertions; update to WXT. Gate: `pytest tests/test_scaffold.py tests/test_scaffold_logging.py tests/test_deploy_validator.py tests/orchestrator/test_template_defaults.py -x` → green.
2. CHANGELOG entry (`### Changed — chrome-extension scaffold rebuilt on WXT`), INDEX.md delta (`manifest.json.j2` removed).
3. **Final gate:** `python scripts/final_gate.py --check --json` → `"status":"success"` (necessary, not sufficient — the real proof is the `wxt build` Evidence) + `python scripts/enforcement/check_convergence.py`.
4. **`/fabrik-docs-review`** on the changed docs surface — converge to a truthful fixed point (SEAMS/FEATURES/INDEX/CHANGELOG vs the emitted scaffold).
5. **`/fabrik-review`** over the whole-plan cumulative diff → no-op.
6. Commit (`Agent-Phase: C`). Mark Phase C EXECUTED + flip `Status: EXECUTED`; stage the plan file.

---

## File Scope (owned paths)
- `src/fabrik/scaffold.py` — **shared-attention** (sibling's plan-4 committed here; no active lock, but pathspec-commit + re-check clean before staging; serialization point if a plan-4 successor re-opens).
- `templates/chrome-extension/**`
- `tests/test_scaffold_chrome_ext_wxt.py` (new), `tests/test_scaffold.py`, `tests/test_scaffold_logging.py`, `tests/test_deploy_validator.py`, `tests/orchestrator/test_template_defaults.py`
- `CHANGELOG.md` (append-only), `INDEX.md`, `docs/reference/SEAMS.md`, `docs/FEATURES.md`
- this plan file.

## Evidence
- **Phase A:** `scaffold.py:3797-4297` (`_scaffold_chrome_extension`, read), `scaffold.py:338-346` (`TYPE_REQUIRED_FILES` chrome-extension, read — requires `manifest.json`+`vite.config.ts`), `scaffold.py:190,4881-4886` (i18n `"chrome"` → `chrome_messages.py`, read).
```
$ ls -d /opt/fabrik-lib/chrome-ext-*   →   (none) — vendor verdict holds
$ grep '@crxjs' src/fabrik/scaffold.py →   5 refs (vite.config.ts:3910, package.json:3933, …) — the surface to replace
```
- **WXT build model (context7 `/wxt-dev/wxt`, 2026-07-11):** `entrypoints/`, `wxt.config.ts`, auto-manifest→`.output/chrome-mv3`, `dev:wxt`/`build:wxt build`/`postinstall:wxt prepare`.
- **Preact (2026-07-11):** `@wxt-dev/module-preact` → npm 404 (doesn't exist); `@preact/preset-vite` `plugins:[preact()]` auto-aliases react→preact/compat (`reactAliasesEnabled` default). Deps grounded live: `@wxt-dev/storage` 1.2.8, `@wxt-dev/i18n` 0.2.6, `webext-bridge` 6.0.1, `@webext-pegasus/store-zustand` 0.3.6, `@hey-api/openapi-ts` 0.99.0, `webext-permission-toggle` 6.0.1 (not v7), `element-ready` 9.0.2 — all MIT.

## Self-audit
- **Grounding passes:** read `_scaffold_chrome_extension` + `TYPE_REQUIRED_FILES` + the i18n adapter (path:line above); confirmed WXT structure + `@preact/preset-vite` live (context7 + npm); confirmed no fabrik-lib kits + no active lock overlap.
- **Coverage:** every "What we agreed" item → a phase: WXT emit+build-green → A; Preact/`preact/compat` → A (config) + B (render test); surfaces/seams/snippets → B; no-kit vendor + SEAMS → B; tests/docs → C; build-is-the-gate → A/B gates; no-shape-change → asserted (no `specs/services` edit).
- **Cross-phase signatures:** A produces `wxt.config.ts` + entrypoint stubs → B consumes/fleshes them; B produces seam signatures → SEAMS.md (C reconciles). No name drift.
- **Toolchain preflight:** `pnpm`/`node` present (mobile-app used them this session); `wxt`/`@preact/preset-vite` are npm deps (installed by `pnpm install` in-phase); **no system toolchain** needed (WXT is pure Node — unlike RN's Android SDK). Playwright bundled-Chromium fixture (Phase B) = `npx playwright install chromium` if absent (probe: `npx playwright --version`).
- Not a fixed point yet — `/fabrik-plan-review` converges it.

## Residual unknowns
- **RESOLVED:** UI framework (Preact + `@preact/preset-vite`); i18n (`@wxt-dev/i18n`, drop `chrome_messages.py` for chrome-ext); no kits vendored; no `shape:` change.
- **SELF-SERVICE — Tailwind-in-WXT plugin exact package:** the executor confirms the Ocoron Tailwind Vite plugin (`@tailwindcss/vite` for Tailwind v4, or the v3 postcss path) against the installed version at build time; the `wxt build` gate verifies it. Probe: `cat extension/package.json | grep tailwind`. No user input.
- **SELF-SERVICE — deploy_validator:** no chrome-ext `manifest.json` assertion found (`grep` empty); if `tests/test_deploy_validator.py` asserts the old extension files, update in Phase C. No user input.
- **No BLOCKING unknowns** — all external facts + the scaffolder edit points are grounded.

## Handoff
`/fabrik-execute-plan docs/development/plans/2026-07-11-plan-1-chrome-ext-wxt-scaffold.md` (user-triggered) after `/fabrik-plan-review` converges this. 💡 fabrik-lib candidates: none.
