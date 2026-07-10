# CLAUDE.md — mobile-app project

Always-on bootstrap for AI coding agents in this repo. **Read `AGENTS.md` first** — it is the
stack + structure map. This file is the behavioural contract.

## What this project is

An Expo/React-Native **client** (`src/`, expo-router) + a bundled Pattern-A **FastAPI backend**
(`server/`) that deploys to the VPS via `fabrik apply`. The client talks only to that backend over
`EXPO_PUBLIC_API_URL`. Rules: `.windsurf/rules/mobile-app/80-mobile.md` (+ `81-mobile-billing.md`)
for the client; `10-python.md` / `30-ops.md` / `55-observability.md` for the backend.

## Hard conformance rules (do not violate)

- **Routing = expo-router** (`src/app/`). NEVER add `@react-navigation/*` to app code.
- **Styling = Uniwind** `@theme` tokens in `src/global.css` (dark-first, Ocoron palette). No raw hex,
  no `react-native-unistyles`/NativeWind.
- **API = generated hey-api client** (`src/lib/api/generated/`, `pnpm generate-api`). Never
  hand-roll `axios`; never fetch from a screen — use the typed hooks.
- **JWTs = `expo-secure-store`** (`src/lib/auth/utils.tsx`), NEVER MMKV/AsyncStorage. Non-sensitive
  KV = `react-native-mmkv` v4 (`createMMKV()`, never `new MMKV()`).
- **Analytics opt-out by default** — no PostHog capture before `optIn()` (`src/lib/consent/`).
- **Force-update / kill-switch:** the server owns the semver (`GET /app-config` via the vendored
  `mobile_config`). The client only consumes `update_required` / `kill_switch` — never re-implement
  version math client-side.
- **Backend `/health`** is real (probes deps when a DB is enabled) and NEVER behind auth.
- **No hardcoded secrets** — `EXPO_PUBLIC_*` is client-safe config only; server secrets via env, never
  in the bundle.
- **Seam contracts** the `rn-*` kits bind to are frozen in `docs/reference/SEAMS.md` — don't diverge.

## Before every commit

```bash
python scripts/final_gate.py        # must be status: success
# backend tests: PYTHONPATH=server/src pytest server/tests
```

Production binaries build via **cloud EAS only** (`eas build`); run `eas init` first (the scaffold
ships a blank EAS project id + Expo owner in `app.config.ts`).
