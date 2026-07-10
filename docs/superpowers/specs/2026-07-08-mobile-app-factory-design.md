# Mobile App Factory — Design Spec

**Status:** CONVERGED (via `/fabrik-spec-review` 2026-07-10 — round 3: fabrik-lib re-grounding after the fabrik-lib AI shipped `mobile-config`/`revenuecat-entitlements`/`payments`/`expo-push` → the `GET /app-config` "build" verdict flipped to **vendor `mobile-config`**, billing backend → vendor `revenuecat-entitlements`+`payments`; Pass-2 no-op. Round 2 kept Uniwind; round 1 converged. The derived plan is separately converged via `/fabrik-plan-review`)
**Date:** 2026-07-09 · **Author:** fabrik AI (from the fabrik-lib AI proposal + live grounding)
**Derived plan:** `docs/development/plans/2026-07-10-plan-1-mobile-app-factory.md` (the reserved `2026-07-09-plan-1` slot was taken by an archived plan)
**Binding rules:** `.windsurf/rules/mobile-app/80-mobile.md` (updated `fce2f3c9`), `81-mobile-billing.md`, `89-mobile-launch-checklist.md`, `ocoron-mobile-design-system.md`

---

## 1. Goal

Turn the existing `fabrik scaffold mobile-app` type into a **mobile app factory**: `fabrik scaffold mobile-app <name>` produces a deployable, rules-conformant Expo app **plus its Pattern-A FastAPI backend**, using **Obytes** (`react-native-template-obytes`) as the client base with the fabrik integration shell ported into it, and clean seams for the future `fabrik-lib/rn-*` kits.

This is an **upgrade of the existing scaffold**, not a greenfield build. The current `templates/mobile-app/` client stack predates the `80-mobile.md` rules update (`fce2f3c9`) and now violates them.

## 2. Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `80-mobile.md` (ACTIVE) | expo-router · styling: **Uniwind** default / raw `react-native-unistyles` for hard zero-re-render · `@hey-api/openapi-ts` · Expo SDK 57 · mmkv v4 · FastAPI **Pattern A** (client talks only to FastAPI) · Argon2 · IAP/RevenueCat · HITL transparency | `.windsurf/rules/mobile-app/80-mobile.md` (styling + expo-router mechanism corrected 2026-07-10) |
| Existing scaffolder | `SCAFFOLD_TYPES`⊃`mobile-app`, `_scaffold_mobile_app()`, `MOBILE_APP_TEMPLATE_DIR`, `I18N_ENABLED_TYPES["mobile-app"]="rn"`, `.j2` templating | `src/fabrik/scaffold.py:148,175,190,273` |
| Existing template | 29-file Expo SDK-55 scaffold + fabrik shell (`compose.yaml.j2`, `Dockerfile.j2`, `defaults.yaml`, `AGENTS.md.j2`, `eas.json`, `app.json`, `.env.example`) | `templates/mobile-app/` |
| `defaults.yaml` shape | `kind: service` (companion backend deploys to VPS) — flags drive `fabrik apply` registrars | `templates/mobile-app/defaults.yaml` |
| `fabrik-lib/i18n/` | i18n SoT kit (client JS loader + `validate_i18n.py` + `translate_i18n.py`); currently **Mobile column = "–"** in the module table | `/opt/fabrik-lib/i18n/README.md`, `/opt/fabrik-lib/README.md:113` |
| Obytes template (live 2026-07-10, `package.json` `obytesapp` v9.0.0) | expo-router `~6.0.22`, **Uniwind `^1.2.4` + Tailwind v4** (migrated off NativeWind), React Query `^5.90` + axios, **TanStack Form** `^1.27` +Zod, Zustand `^5`, mmkv `~4.1.1`, i18next `^25`, 13 GH Actions, Maestro, env-zod, Jest+RTL — **on Expo SDK `~54.0.32`**, **MIT license** (Copyright 2021 Obytes), default branch `master` | raw.githubusercontent.com/obytes/react-native-template-obytes/master/{package.json,LICENSE} (fetched 2026-07-10) |

## 3. Grounded external facts (re-verified live 2026-07-10)

- **Expo SDK 57** current stable (2026-06-30, RN 0.86); `create-expo-app` default still lags to **54**, so pin `--template default@sdk-57`. (expo.dev/changelog/sdk-57, docs.expo.dev/more/create-expo — fetched 2026-07-10)
- **expo-router** — Expo's default router (ships preconfigured in the default template since ~SDK 50 — "since SDK 50" is not stated verbatim in current docs); **forked from React Navigation in SDK 56**. `@react-navigation/*` imports in **app code** now trigger a **Metro/Expo CLI bundler ERROR** (not an `expo-doctor` warning; disable via `EXPO_ROUTER_DISABLE_RN_NAVIGATION_CHECK=1`); the SDK-55→56 migration codemod repoints imports. (docs.expo.dev/router/migrate/sdk-55-to-56, expo.dev/blog/expo-router-v56-decoupling-from-react-navigation — fetched 2026-07-10)
- **react-native-mmkv v4** (v4.3.2) — Nitro rewrite, New-Arch-only, **RN ≥ 0.76** (README Limitations: "V4 requires react-native 0.76 or higher"); `createMMKV()`/`.remove()`/`AppGroupIdentifier`. (github.com/mrousavy/react-native-mmkv — fetched 2026-07-10)
- **@hey-api/openapi-ts** — FastAPI's own docs name Hey API for TS clients; `@tanstack/react-query` + `zod` plugins; **validation via `validator: true` on the `@hey-api/sdk` plugin (plugin-scoped, NOT `sdk.validator`)**; and the `@hey-api/sdk` plugin must be listed **explicitly** when `zod` is added (issue #2720, closed not-planned — explicit-plugin listing is the practical workaround). (fastapi.tiangolo.com/advanced/generate-clients, heyapi.dev/openapi-ts/plugins/sdk — fetched 2026-07-10)
- **react-native-unistyles v3** (v3.2.5, npm) — C++/JSI **synchronous** theming (theme changes patch the ShadowTree from C++, **no component re-render**; Nitro-powered). New-Arch mandatory, **RN ≥ 0.78 / Expo SDK ≥ 53** (SDK 57 exceeds the floor); needs the `react-native-unistyles/plugin` Babel plugin + `expo prebuild` (not Expo Go); adaptive dark+light via `StyleSheet.configure({ themes })`. Docs: **unistyl.es**. This is the rule's literal **zero-re-render engine — kept as the FALLBACK** for a hard zero-re-render requirement, **not the factory default** (see Uniwind). (unistyl.es/v3/start/getting-started — fetched 2026-07-10)
- **Uniwind** (`uniwind`, current **v1.10.0**; Obytes pins `~1.2.4`) — a **build-time Tailwind-v4 Metro compiler** by the **Unistyles team** (`uni-stack/uniwind`, "from the creators of Unistyles"). `className` DX, **no runtime style parsing** (deps `@tailwindcss/oxide`/`lightningcss`/Metro — **no `react-native-unistyles` dependency**). It is **NOT** on the unistyles C++/JSI engine and **re-renders on theme change** (`useUniwind`); the zero-re-render synchronous C++ tier is the **unreleased "Uniwind Pro"**. Custom tokens via Tailwind-v4 CSS `@theme`/`@variant` + the Metro plugin (no `tailwind.config.js`). RN ≥ 0.81, Expo-OK (incl. Expo Go), MIT, production-stable (~238K weekly dl). → **Factory-default styling**: Obytes ships it, it meets the rule's build-time-perf intent, and the theme-toggle re-render is non-hot-path. (npmjs.com/package/uniwind, docs.uniwind.dev, github.com/uni-stack/uniwind — fetched 2026-07-10)
- **Obytes** — SDK 54, Expo Router 6, **TanStack Form** (migrated off react-hook-form), **Uniwind + Tailwind v4** (migrated off NativeWind), axios, mmkv ~4.1.1, 13 Actions, Maestro; **MIT-licensed** (fork is legal). (github.com/obytes/react-native-template-obytes — `package.json`/`LICENSE` fetched 2026-07-10)

## 4. Discrepancies found vs the fabrik-lib AI proposal (flagged; resolved below)

1. **Existing backend lane is Node — and broken.** `Dockerfile.j2` is `FROM node:22` + `npm run build`, healthchecking the **Metro dev bundler** on `:8081` — nonsensical as a deployed API, and it violates Pattern A. → **RESOLVED: replace with a bundled minimal FastAPI backend** (§7, operator decision "full scaffold").
2. **The `rn-*` *client* kits don't exist yet** (`rn-auth/compliance/analytics/media/billing-kit`) → **kit-SEAMS** (contracts to target). **BUT `mobile-config` NOW EXISTS** as a fabrik-lib backend module (shipped 2026-07-10) → the `GET /app-config` route **vendors `fabrik-lib/mobile-config/`**, it is NOT hand-rolled (§6). (The spec's original "doesn't exist" was true at authoring; the fabrik-lib AI has since shipped `mobile-config` + `revenuecat-entitlements` + `payments` + `expo-push`.)
3. **Obytes is on SDK 54, not 57** → the SDK-57 bump is explicit factory work atop the fork.
4. **Obytes uses TanStack Form, not react-hook-form** (its `claude.md` says so explicitly) → **RESOLVED: keep Obytes' TanStack Form + Zod** (avoid swapping away from the base; the AI's "react-hook-form" was stale; `80-mobile.md` mandates no specific form lib). Operator may override.
5. **The existing template is already on mmkv V4 in the rules but v3.1.0 in `package.json`** — the Obytes/new stack supplies v4; the stale v3 client is discarded (§5).
6. **Obytes' styling base is Uniwind, not NativeWind — and Uniwind is NOT the react-native-unistyles engine** (grounded 2026-07-10: `uniwind` is a build-time Tailwind-v4 Metro compiler by the Unistyles team, **no `react-native-unistyles` dependency**, re-renders on theme change; the unistyles C++ engine is the unreleased "Uniwind Pro"). The fabrik-lib AI's "runs on the unistyles engine" premise was **disproven** (it corrected its own spec, `8f65f98`). → **RESOLVED (operator decision 2026-07-10): KEEP Uniwind** as the factory-default styling — **zero rewrite** (Obytes ships it), build-time compiled (no runtime parsing → meets the rule's actual perf intent), theme-toggle re-render is non-hot-path, MIT, Unistyles-team. Raw `react-native-unistyles` stays the documented fallback for a hard zero-re-render requirement; `80-mobile.md` now lists Uniwind as an accepted option. The earlier "rewrite Uniwind→unistyles" swap is **dropped**.
7. **License = MIT** (Obytes `LICENSE`, Copyright 2021 Obytes) → **RESOLVED**: forking Obytes files into the fabrik repo is legally clear (retain the copyright+license notice).

## 5. Chosen approach

**Fork Obytes as the client base; port the fabrik shell into it; swap its stack to the rules; add the factory layers; bundle a FastAPI backend; leave kit-seams.** Structured exactly as the fabrik-lib AI's 7-part plan, refined by grounding:

### 5.1 DISCARD (stale client — obsoleted by `fce2f3c9`, would be rewritten anyway)

`src/App.tsx`, `src/navigation/AppNavigator.tsx`+`types.ts` (React Navigation), `src/features/files/*` (hand-fetch demo → becomes an `rn-media-kit` consumer), `src/lib/{storage.ts (mmkv v3), i18n.ts, queryClient.ts}` — the Obytes base + new stack supply the equivalents.

### 5.2 KEEP + PORT (fabrik-specific value Obytes has none of)

- Scaffolder plumbing **unchanged**: `SCAFFOLD_TYPES` entry, `MOBILE_APP_TEMPLATE_DIR`, `_scaffold_mobile_app()`, `I18N_ENABLED_TYPES["mobile-app"]="rn"`, `.j2` templating.
- The integration shell: `compose.yaml.j2`, `Dockerfile.j2`, `defaults.yaml` (shape), `AGENTS.md.j2`, `eas.json`/`app.json`, `.env.example`, the fabrik gate wiring — **rewritten for the FastAPI backend** (§7), not Node.
- Ocoron tokens (`src/theme/tokens.ts`) → fed into **Uniwind** as its Tailwind-v4 CSS `@theme`/`@variant` theme (dark-first + light) — kept, **not** rewritten to raw unistyles.
- `src/locales/{en,tr}.json` + the "rn" i18n adapter → **vendor** the fabrik-lib i18n SoT into the project (`libs/i18n`), using the canonical RN adapter **`templates/i18n-kit/adapters/sync_rn_locales.py`** (grounded: the scaffolder's `I18N_KIT_DIR`, `src/fabrik/scaffold.py:178`; `templates/scaffold/i18n-kit/` has no `adapters/`). The **Mobile-column flip is fabrik-lib's action** — the fabrik-lib AI vendors that RN adapter into `/opt/fabrik-lib/i18n/` first, then flips the column (it correctly stays `–` until then). Do **not** edit `/opt/fabrik-lib` from this repo (cross-repo HARD STOP).

### 5.3 ADOPT from Obytes (fabrik-ize into the template)

expo-router `app/`, the auth flow, forms (**TanStack Form + Zod** — Obytes current, not react-hook-form), the 10+ GitHub Actions, Maestro, env-Zod validation, Jest+RTL testing. Turn Obytes' repo structure into the scaffold template (add `.j2` project-name substitution, keep the fabrik dir conventions).

### 5.4 SWAP on the Obytes base

- **Styling — NO swap: KEEP Uniwind** (Obytes' Tailwind-v4 build-time compiler by the Unistyles team; feed the Ocoron tokens as its CSS `@theme`/`@variant`). Grounded 2026-07-10: Uniwind is build-time compiled (no runtime parsing → meets the rule's perf intent) and re-renders only on the rare theme toggle. Raw `react-native-unistyles` remains the documented fallback for a hard zero-re-render requirement; "Uniwind Pro" (C++/JSI) is the future zero-re-render upgrade. **The earlier Uniwind→unistyles rewrite (the "largest single swap") is dropped.**
- **axios → `@hey-api/openapi-ts`** (+ explicit `@hey-api/sdk`, `validator: true` — plugin-scoped, #2720) + a **CI OpenAPI-drift gate**.
- **Expo SDK → 57 explicit** (`--template default@sdk-57`); **mmkv → v4** (`createMMKV`/`.remove`/`AppGroupIdentifier`).

### 5.5 ADD (the factory layers)

- **PostHog behind the consent gate** (`posthog-react-native`; init with `defaults.defaultOptIn: false` so nothing — autocapture included — fires until `optIn()` runs after the consent gate). (posthog.com/docs/libraries/react-native — fetched 2026-07-10)
- **Offline resilience** — `onlineManager.setEventListener` wired to `@react-native-community/netinfo` + `PersistQueryClientProvider` + `createSyncStoragePersister` (all TanStack-documented) over an **MMKV**-backed sync storage (**community pattern — MMKV is not named in TanStack docs**; MMKV is synchronous so it satisfies the `createSyncStoragePersister` interface) + an Offline screen. (tanstack.com/query/latest/docs/framework/react/react-native — fetched 2026-07-10)
- **UX primitives** (`expo-haptics`, `expo-local-authentication`, `expo-store-review`, `expo-image-picker`/camera, QR via camera).
- **Force-update shell** (client) calling the backend's `GET /app-config` (the backend vendors `fabrik-lib/mobile-config/`).
- Ship the **mobile rule packs** + a project `CLAUDE.md` for AI-agent conformance.

### 5.6 KIT-SEAMS (contracts so the future `fabrik-lib/rn-*` kits drop in)

Define + document the seam contracts — **the hey-api client location, the styling theme shape (Uniwind Tailwind `@theme`), the consent-state provider** — so `rn-auth-kit` (over `fastapi-user-auth`/`oauth-login`), `rn-compliance-kit` (the consent gate that gates PostHog), `rn-analytics-kit`, `rn-media-kit` (replaces the files demo), `rn-billing-kit` target them when they land.

## 6. fabrik-lib vendor→enhance→build verdict

| Capability | Verdict |
|---|---|
| i18n | **Vendor** `fabrik-lib/i18n/` into the project (`libs/i18n`) using the canonical RN adapter `templates/i18n-kit/adapters/sync_rn_locales.py` (`scaffold.py:178`). The **Mobile-column flip is fabrik-lib's**: the fabrik-lib AI vendors that RN adapter into `/opt/fabrik-lib/i18n/` first, then flips the column (stays `–` until then). Cross-repo edits from this repo are a HARD STOP. |
| Auth | Seam only now (`rn-auth-kit` future) — backend uses `fastapi-user-auth` (Pattern A). |
| Consent / analytics / media | **Seams** — the `rn-*` *client* kits don't exist yet; define contracts, don't build them here. |
| billing (backend/entitlements) | **Vendor `revenuecat-entitlements/`** (+ `payments/` for Paddle/iyzico) for server-side entitlement derivation — both now EXIST (grounded 2026-07-10). The client-side RevenueCat SDK stays the `rn-billing-kit` seam. |
| `mobile-config` / app-config | **Vendor `fabrik-lib/mobile-config/`** — the module now EXISTS (grounded 2026-07-10: `from mobile_config import AppConfig, evaluate`). Wire it into the backend's `GET /app-config` route; **do NOT hand-roll** the semver force-update (the module encodes the `1.10.0 > 1.9.0` footgun + fail-safe malformed-version + kill-switch + feature toggles + remote-paywall pointer; one dep `packaging`, DB-agnostic). |

**Backend vendor-ladder (audited against `/opt/fabrik-lib/README.md` 2026-07-10 — don't re-build what exists):** the bundled FastAPI's own capabilities are **vendor**, not build — auth ⇒ `fastapi-user-auth` (Pattern A JWTs) + `account` (profile CRUD) + `oauth-login` (federated sign-in) if needed; any data-subject-rights ⇒ `gdpr-data-rights`; outbound HTTP ⇒ `async-http-client`; **`GET /app-config` ⇒ `mobile-config`** (force-update/kill-switch/toggles/paywall); **billing/entitlements ⇒ `revenuecat-entitlements` + `payments`**; **push ⇒ `expo-push`** (if push is added later — out of this spec's scope). The `rn-*` **client** kits remain seams (client-side RN; the fabrik-lib modules above are backend/web — a different layer, so this is not a missed-module reuse, it's the correct build-the-seam call).

## 7. Backend lane (RESOLVED — operator decision: "full scaffold")

The scaffold ships a **minimal bundled FastAPI backend** (Pattern A) alongside the Expo client, in one repo:
- It is the sole data layer the app's hey-api client talks to; **hey-api's OpenAPI source = the bundled backend's `/openapi.json`**.
- It hosts the force-update `GET /app-config` — **vendoring `fabrik-lib/mobile-config/`** (`AppConfig`+`evaluate`), not a hand-rolled semver check.
- It deploys to the VPS via a **rewritten `compose.yaml.j2` + `Dockerfile.j2`** (Python/FastAPI, real `/health`, memory limit, `fabrik` network — replacing the broken Node/Metro lane), `defaults.yaml` shape stays `kind: service`.
- Reuses the fabrik FastAPI conventions (`fastapi-user-auth`, `postgres-main` when `needs_database`, GlitchTip).

*Rejected:* (a) Node backend — violates Pattern A + is broken; (b) client-only + separate `python-api` — two repos to wire, and the operator chose a full self-contained scaffold.

## 8. Shape / infra implications

- `defaults.yaml` shape: `kind: service`; set `needs_database: true` + `has_bearer_api: true` **iff** the bundled backend uses `postgres-main` + issues JWTs (Pattern A auth) — the plan decides per the minimal-backend surface. Any code that adds a DB call / cache / metrics MUST flip the matching `shape.*` flag.
- The Expo **client** ships via EAS to stores (no VPS container); only the **backend** is a `fabrik apply` service.
- Doc Sync: new env vars → `.env.example` + `docs/CONFIGURATION.md`; new compose service → `docs/SERVICES.md`; the i18n Mobile-column flip → **proposed** to `fabrik-lib/README.md` (a fabrik-lib-side change, not a direct edit from this repo).

## 9. DONE criteria

`fabrik scaffold mobile-app <name>` produces a deployable app where:
1. `python scripts/final_gate.py --check --json` → `"status":"success"`.
2. The client conforms to `80-mobile.md` (expo-router / **Uniwind** styling / hey-api / SDK 57 / mmkv v4).
3. A **Maestro** smoke flow (launch → consent gate blocks pre-consent → home) is green.
4. The **bundled FastAPI backend** deploys via `fabrik apply` (compose + `/health` + memory limit + `fabrik` net).
5. The **kit-seams** (hey-api client location, styling theme shape — Uniwind Tailwind `@theme`, consent-state provider) are documented for the `fabrik-lib/rn-*` kits.

## 10. Residuals / open items

- All execution-blocking decisions are **resolved or self-service**: backend lane (RESOLVED, §7), form lib (RESOLVED → TanStack Form, §4.4, operator-overridable), SDK/mmkv/router (rule-mandated), kits (seams).
- **Licensing (RESOLVED):** Obytes `LICENSE` is **MIT** (Copyright 2021 Obytes, fetched 2026-07-10) → forking its files into the fabrik repo is legally clear; retain the copyright+license notice. No longer a blocker.
- **rn-* *client* kits** are future fabrik-lib work — this spec defines their seams. (**`mobile-config`, `revenuecat-entitlements`, `payments`, `expo-push` now EXIST** as fabrik-lib backend modules → vendored per §6, no longer "future".)
- **Styling (RESOLVED):** KEEP Uniwind as the factory default — grounded 2026-07-10 that it is build-time compiled (meets the rule's perf intent) though **not** the unistyles C++ engine; **zero rewrite** (the earlier "largest single swap" is dropped). Raw `react-native-unistyles` is the documented fallback for a hard zero-re-render requirement; "Uniwind Pro" (C++/JSI) is the future upgrade when it ships.
- **Raw-unistyles fallback caveat (only if a project opts out of Uniwind):** raw `react-native-unistyles` SDK-57 compat is inferential (docs state RN ≥ 0.78 / SDK ≥ 53, which SDK 57/RN 0.86 exceeds) and it needs the `react-native-unistyles/plugin` Babel plugin + `expo prebuild` — smoke-run to confirm. Not on the Uniwind default path.
