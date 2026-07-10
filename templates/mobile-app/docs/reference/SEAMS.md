# SEAMS.md — kit-seam contracts (Phase A6)

This file documents the **precise seam contracts** the 5 CONVERGED `fabrik-lib` `rn-*` kits
(`rn-auth-kit`, `rn-compliance-kit`, `rn-analytics-kit`, `rn-media-kit`, `rn-billing-kit`) bind
to. The scaffold ships the *seam* (state/shape/location); the kits fill the gate
screen/geo/ATT/UI on top. Do not change these names/shapes without updating every kit that
binds to them.

## (1) Consent-state seam

Already created by A5(a) — `src/lib/consent/` is the provider. It exposes:

- `hasAnalyticsConsent(): boolean`
- `useConsent()`
- PostHog initialized with `defaults: { defaultOptIn: false }` — `optIn()` is only called
  post-consent.

The scaffold ships the *state* seam; `rn-compliance-kit` + `rn-analytics-kit` bind to these
exact names.

## (2) hey-api client location seam

`src/lib/api/generated` — the `@hey-api/openapi-ts` generated client + Zod validators (Phase
B4 populates it; Phase A ships the config + a stub so imports resolve). `src/lib/api/provider.tsx`
(QueryClient/APIProvider) is the stable entry point kits import.

## (3) Uniwind `@theme` shape seam

`src/global.css` — Tailwind-v4 `@theme` + dark `@variant`/`@media` block carrying the Ocoron
Design System tokens (`--color-background/-card/-border/-primary/...`, font, spacing). Kits
that render UI (`rn-compliance-kit` consent screens, `rn-billing-kit` paywall, etc.) style
against these tokens — never introduce `react-native-unistyles` or NativeWind.

## (4) auth-token store seam

`expo-secure-store` (Keychain/Keystore) — set in A5(e). `src/lib/auth/utils.tsx` exposes
`getToken`/`setToken`/`removeToken`. JWTs MUST NOT sit in MMKV (security rule
`80-mobile.md:117,328,374`). `rn-auth-kit` binds to this store, never to `src/lib/storage.tsx`.

## (5) Backend route seams

Documented extension points the client binds to (same opt-in-vendor pattern as auth) — these
are backend routes, not client code; the client's job is to call them with the shapes below.

- **`GET /app-config`** — **IMPLEMENTED (Phase B, `server/src/app/routes/app_config.py`).** The
  force-update / kill-switch / feature-toggle gate, computed server-side by the vendored
  `mobile_config.evaluate` (the client never re-implements semver). **Request (both query params
  REQUIRED — the backend 422s without them):** `?platform=<ios|android>&version=<installed app version>`.
  **Response:**

  ```
  {
    update_required: boolean   // authoritative gate — client blocks entry when true
    update_available: boolean
    min_version: string | null
    latest_version: string | null
    kill_switch: boolean
    kill_switch_message: string | null
    features: { <key>: boolean }
    paywall_id: string | null
    store_urls: { android: string, ios: string }   // added by the route (mobile_config doesn't model it)
  }
  ```

  Operator config is env-driven (`APP_MIN_VERSION`, `APP_LATEST_VERSION`, `STORE_URL_{ANDROID,IOS}`,
  `APP_KILL_SWITCH*`, `APP_FEATURE_FLAGS`, `APP_PAYWALL_ID` — see `.env.example`). Fails open: a
  malformed operator gate or a bad client version never wrongly blocks. Client binder: `src/lib/update/`.

- **`GET /entitlements`** (over `revenuecat-entitlements.Subscriber`) — **pinned contract**
  (fabrik-lib 2026-07-10, grounded on `revenuecat_entitlements/state.py`):

  ```
  {
    active: string[]         // sorted; the authoritative gate — client does active.includes("premium")
    entitlements: {
      <id>: {
        is_entitled: boolean // is_entitled = status ∈ {active, grace}
        status: "none" | "active" | "grace" | "paused" | "canceled"
      }
    }
  }
  ```

  Reads the webhook-derived Subscriber, not the client SDK cache; omits `plan_id`/`occurred_at`.
  This is the exact hey-api/Zod shape `rn-billing-kit` binds to.

- **`POST /support`** (`email-templates` + `email-transport`).

- **Presigned-upload URL endpoint**, over `storage.presigned_put_url(key, *, content_type,
  expiry_s=900) -> str` (LANDED `743fc85`, grounded `fabrik-lib/storage/storage.py:139`; B2
  S3-compatible SigV4, env `B2_S3_REGION` + a non-master B2 app key as S3 creds). The client
  PUTs the **raw body** with the exact signed `Content-Type` — no `FormData`/multipart. This is
  the seam `rn-media-kit` binds to (see `src/lib/media/` stub).

- **Mobile-OAuth routes** (deep-link + one-time-code exchange + native-Apple-verify), composing
  `oauth-login`'s seams — no core change required.

- **`record_consent`** (`gdpr-data-rights`).

## (6) Client push seam (future)

`expo-notifications` → device push token → the `expo-push` backend delivery path. **Out of
this spec's scope** — documented here only so a future kit knows where to land.

---

## Connectivity (A5)

`EXPO_PUBLIC_API_URL` is documented in `.env.example` with per-target guidance — a mobile
device/emulator/simulator cannot reach `localhost`/Docker DNS the way a browser on the host
can:

| Target | Value |
|---|---|
| Physical device | host machine's LAN IP (e.g. `http://192.168.1.50:8000`) |
| Android emulator | `http://10.0.2.2:8000` |
| iOS simulator | `http://localhost:8000` |
| Production | the deployed backend domain (e.g. `https://api.your-vps.com`) |

## Stub directories (this task)

- `src/lib/media/` — `rn-media-kit` seam stub (`export {}` placeholder; binds to the
  presigned-upload route above).
- `src/lib/billing/` — `rn-billing-kit` seam stub (`export {}` placeholder; binds to
  `GET /entitlements` above).

`src/lib/analytics/` (owned by Task 2, alongside `src/lib/consent/`) is the `rn-analytics-kit`
seam and is not re-stubbed here.
