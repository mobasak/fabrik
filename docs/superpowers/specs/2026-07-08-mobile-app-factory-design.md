# Mobile App Factory — Design Spec

**Status:** DRAFT (to be converged via `/fabrik-plan-review` on the derived plan)
**Date:** 2026-07-09 · **Author:** fabrik AI (from the fabrik-lib AI proposal + live grounding)
**Derived plan:** `docs/development/plans/2026-07-09-plan-1-mobile-app-factory.md`
**Binding rules:** `.windsurf/rules/mobile-app/80-mobile.md` (updated `fce2f3c9`), `81-mobile-billing.md`, `89-mobile-launch-checklist.md`, `ocoron-mobile-design-system.md`

---

## 1. Goal

Turn the existing `fabrik scaffold mobile-app` type into a **mobile app factory**: `fabrik scaffold mobile-app <name>` produces a deployable, rules-conformant Expo app **plus its Pattern-A FastAPI backend**, using **Obytes** (`react-native-template-obytes`) as the client base with the fabrik integration shell ported into it, and clean seams for the future `fabrik-lib/rn-*` kits.

This is an **upgrade of the existing scaffold**, not a greenfield build. The current `templates/mobile-app/` client stack predates the `80-mobile.md` rules update (`fce2f3c9`) and now violates them.

## 2. Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `80-mobile.md` (ACTIVE) | expo-router · unistyles-for-dynamic · `@hey-api/openapi-ts` · Expo SDK 57 · mmkv v4 · FastAPI **Pattern A** (client talks only to FastAPI) · Argon2 · IAP/RevenueCat · HITL transparency | `.windsurf/rules/mobile-app/80-mobile.md:81,90,103,106` |
| Existing scaffolder | `SCAFFOLD_TYPES`⊃`mobile-app`, `_scaffold_mobile_app()`, `MOBILE_APP_TEMPLATE_DIR`, `I18N_ENABLED_TYPES["mobile-app"]="rn"`, `.j2` templating | `src/fabrik/scaffold.py:148,175,190,273` |
| Existing template | 29-file Expo SDK-55 scaffold + fabrik shell (`compose.yaml.j2`, `Dockerfile.j2`, `defaults.yaml`, `AGENTS.md.j2`, `eas.json`, `app.json`, `.env.example`) | `templates/mobile-app/` |
| `defaults.yaml` shape | `kind: service` (companion backend deploys to VPS) — flags drive `fabrik apply` registrars | `templates/mobile-app/defaults.yaml` |
| `fabrik-lib/i18n/` | i18n SoT kit (client JS loader + `validate_i18n.py` + `translate_i18n.py`); currently **Mobile column = "–"** in the module table | `/opt/fabrik-lib/i18n/README.md`, `/opt/fabrik-lib/README.md:113` |
| Obytes template (live 2026-07-09) | expo-router 6, NativeWind, React Query+axios, TanStack Form+Zod, Zustand, MMKV, i18next, 10+ GH Actions, Maestro, env-zod, Jest+RTL — **on Expo SDK 54** | github.com/obytes/react-native-template-obytes (`claude.md`: "SDK 54 / RN 0.81.5 / Expo Router 6 / TanStack Form (not react-hook-form)") |

## 3. Grounded external facts (verified live 2026-07-09)

- **Expo SDK 57** current stable (2026-06-30, RN 0.86); `create-expo-app` default still lags to **54**, so pin `--template default@sdk-57`. (expo.dev/changelog/sdk-57)
- **expo-router** — Expo's default since SDK 50; **forked from React Navigation in SDK 56** (`@react-navigation/*` imports fail in app code; `expo-doctor` warns if both installed; codemod repoints). (docs.expo.dev/router)
- **react-native-mmkv v4** (v4.3.2) — Nitro rewrite, New-Arch-only, RN ≥ 0.75; `createMMKV()`/`.remove()`/`AppGroupIdentifier`. (github.com/mrousavy/react-native-mmkv)
- **@hey-api/openapi-ts** — FastAPI's own docs name Hey API for TS clients; `@tanstack/react-query` + `zod` plugins; **validation via `validator: true` on the `@hey-api/sdk` plugin (plugin-scoped, NOT `sdk.validator`)**; and the `@hey-api/sdk` plugin must be listed **explicitly** when `zod` is added (issue #2720). (fastapi.tiangolo.com/advanced/generate-clients, heyapi.dev)
- **react-native-unistyles v3** — C++/JSI synchronous theming; carries the Ocoron token theme (dark-first + light). (grounded during plan Phase 1)
- **Obytes** — SDK 54, Expo Router 6, **TanStack Form** (migrated off react-hook-form), NativeWind, axios, 10+ Actions, Maestro. (github.com/obytes/react-native-template-obytes)

## 4. Discrepancies found vs the fabrik-lib AI proposal (flagged; resolved below)

1. **Existing backend lane is Node — and broken.** `Dockerfile.j2` is `FROM node:22` + `npm run build`, healthchecking the **Metro dev bundler** on `:8081` — nonsensical as a deployed API, and it violates Pattern A. → **RESOLVED: replace with a bundled minimal FastAPI backend** (§7, operator decision "full scaffold").
2. **The `rn-*` kits and `mobile-config` do NOT exist in fabrik-lib yet** (`rn-auth/compliance/analytics/media/billing-kit`, `mobile-config`). → They are **kit-SEAMS** (contracts to target), not dependencies; the force-update `GET /app-config` is hosted by the **bundled FastAPI backend**, not a non-existent `mobile-config` service.
3. **Obytes is on SDK 54, not 57** → the SDK-57 bump is explicit factory work atop the fork.
4. **Obytes uses TanStack Form, not react-hook-form** (its `claude.md` says so explicitly) → **RESOLVED: keep Obytes' TanStack Form + Zod** (avoid swapping away from the base; the AI's "react-hook-form" was stale; `80-mobile.md` mandates no specific form lib). Operator may override.
5. **The existing template is already on mmkv V4 in the rules but v3.1.0 in `package.json`** — the Obytes/new stack supplies v4; the stale v3 client is discarded (§5).

## 5. Chosen approach

**Fork Obytes as the client base; port the fabrik shell into it; swap its stack to the rules; add the factory layers; bundle a FastAPI backend; leave kit-seams.** Structured exactly as the fabrik-lib AI's 7-part plan, refined by grounding:

### 5.1 DISCARD (stale client — obsoleted by `fce2f3c9`, would be rewritten anyway)
`src/App.tsx`, `src/navigation/AppNavigator.tsx`+`types.ts` (React Navigation), `src/features/files/*` (hand-fetch demo → becomes an `rn-media-kit` consumer), `src/lib/{storage.ts (mmkv v3), i18n.ts, queryClient.ts}` — the Obytes base + new stack supply the equivalents.

### 5.2 KEEP + PORT (fabrik-specific value Obytes has none of)
- Scaffolder plumbing **unchanged**: `SCAFFOLD_TYPES` entry, `MOBILE_APP_TEMPLATE_DIR`, `_scaffold_mobile_app()`, `I18N_ENABLED_TYPES["mobile-app"]="rn"`, `.j2` templating.
- The integration shell: `compose.yaml.j2`, `Dockerfile.j2`, `defaults.yaml` (shape), `AGENTS.md.j2`, `eas.json`/`app.json`, `.env.example`, the fabrik gate wiring — **rewritten for the FastAPI backend** (§7), not Node.
- Ocoron tokens (`src/theme/tokens.ts`) → migrate into a **react-native-unistyles v3** theme (dark-first + light).
- `src/locales/{en,tr}.json` + the "rn" i18n adapter → formalize as the **fabrik-lib i18n SoT** (`sync_rn_locales.py`), and flip i18n's **Mobile column to ✓** in the fabrik-lib table.

### 5.3 ADOPT from Obytes (fabrik-ize into the template)
expo-router `app/`, the auth flow, forms (**TanStack Form + Zod** — Obytes current, not react-hook-form), the 10+ GitHub Actions, Maestro, env-Zod validation, Jest+RTL testing. Turn Obytes' repo structure into the scaffold template (add `.j2` project-name substitution, keep the fabrik dir conventions).

### 5.4 SWAP on the Obytes base
- **NativeWind → react-native-unistyles v3** (carry the Ocoron tokens).
- **axios → `@hey-api/openapi-ts`** (+ explicit `@hey-api/sdk`, `validator: true` — plugin-scoped, #2720) + a **CI OpenAPI-drift gate**.
- **Expo SDK → 57 explicit** (`--template default@sdk-57`); **mmkv → v4** (`createMMKV`/`.remove`/`AppGroupIdentifier`).

### 5.5 ADD (the factory layers)
- **PostHog behind the consent gate** (no autocapture pre-consent).
- **Offline resilience** (`netinfo → onlineManager` + `PersistQueryClientProvider` + MMKV persister + an Offline screen).
- **UX primitives** (`expo-haptics`, `expo-local-authentication`, `expo-store-review`, `expo-image-picker`/camera, QR via camera).
- **Force-update shell** calling the bundled backend's `GET /app-config`.
- Ship the **mobile rule packs** + a project `CLAUDE.md` for AI-agent conformance.

### 5.6 KIT-SEAMS (contracts so the future `fabrik-lib/rn-*` kits drop in)
Define + document the seam contracts — **the hey-api client location, the unistyles theme shape, the consent-state provider** — so `rn-auth-kit` (over `fastapi-user-auth`/`oauth-login`), `rn-compliance-kit` (the consent gate that gates PostHog), `rn-analytics-kit`, `rn-media-kit` (replaces the files demo), `rn-billing-kit` target them when they land.

## 6. fabrik-lib vendor→enhance→build verdict

| Capability | Verdict |
|---|---|
| i18n | **Vendor + enhance** `fabrik-lib/i18n/` — formalize the RN adapter (`sync_rn_locales.py`), flip Mobile → ✓. |
| Auth | Seam only now (`rn-auth-kit` future) — backend uses `fastapi-user-auth` (Pattern A). |
| Consent / analytics / media / billing | **Seams** — `rn-*` kits don't exist yet; define contracts, don't build the kits in this spec. |
| `mobile-config` / app-config | **Build into the bundled FastAPI backend** (a `GET /app-config`), NOT a separate service (doesn't exist). |

## 7. Backend lane (RESOLVED — operator decision: "full scaffold")

The scaffold ships a **minimal bundled FastAPI backend** (Pattern A) alongside the Expo client, in one repo:
- It is the sole data layer the app's hey-api client talks to; **hey-api's OpenAPI source = the bundled backend's `/openapi.json`**.
- It hosts the force-update `GET /app-config`.
- It deploys to the VPS via a **rewritten `compose.yaml.j2` + `Dockerfile.j2`** (Python/FastAPI, real `/health`, memory limit, `fabrik` network — replacing the broken Node/Metro lane), `defaults.yaml` shape stays `kind: service`.
- Reuses the fabrik FastAPI conventions (`fastapi-user-auth`, `postgres-main` when `needs_database`, GlitchTip).

*Rejected:* (a) Node backend — violates Pattern A + is broken; (b) client-only + separate `python-api` — two repos to wire, and the operator chose a full self-contained scaffold.

## 8. Shape / infra implications

- `defaults.yaml` shape: `kind: service`; set `needs_database: true` + `has_bearer_api: true` **iff** the bundled backend uses `postgres-main` + issues JWTs (Pattern A auth) — the plan decides per the minimal-backend surface. Any code that adds a DB call / cache / metrics MUST flip the matching `shape.*` flag.
- The Expo **client** ships via EAS to stores (no VPS container); only the **backend** is a `fabrik apply` service.
- Doc Sync: new env vars → `.env.example` + `docs/CONFIGURATION.md`; new compose service → `docs/SERVICES.md`; the i18n Mobile-column flip → `fabrik-lib/README.md`.

## 9. DONE criteria

`fabrik scaffold mobile-app <name>` produces a deployable app where:
1. `python scripts/final_gate.py --check --json` → `"status":"success"`.
2. The client conforms to `80-mobile.md` (expo-router / unistyles / hey-api / SDK 57 / mmkv v4).
3. A **Maestro** smoke flow (launch → consent gate blocks pre-consent → home) is green.
4. The **bundled FastAPI backend** deploys via `fabrik apply` (compose + `/health` + memory limit + `fabrik` net).
5. The **kit-seams** (hey-api client location, unistyles theme shape, consent-state provider) are documented for the `fabrik-lib/rn-*` kits.

## 10. Residuals / open items

- All execution-blocking decisions are **resolved or self-service**: backend lane (RESOLVED, §7), form lib (RESOLVED → TanStack Form, §4.4, operator-overridable), SDK/mmkv/router (rule-mandated), kits (seams).
- **Licensing:** Obytes template license — verify MIT-compatibility before forking its files into the fabrik repo (plan Phase 1 gate).
- **rn-* kits + mobile-config** are future fabrik-lib work — this spec only defines their seams.
- **unistyles v3 migration of the Obytes NativeWind UI kit** is the largest single swap — the plan must scope it as its own phase with a per-component checklist.
