# Chrome-extension scaffold — developer-mode release kit (design)

Status: CONVERGED
Size: small (≈320 lines across scaffold.py, two templates and two test files)
Profile: delta
Work item: W-e2af3303 · seed: mail 01M3WQXZ3Y (fleet) · rule: D-486 (`chrome-ext/70-chrome-ext.md` § Distribution Model), D-493 (`chrome-ext/89-extension-launch-checklist.md` § 7)

## Personas

- **PRIMARY — the operator who ships an extension the store will not approve.** In the operator's own words (D-486):
  *"we should be able to develop chrome extensions which can be installed via developer options for the ones which cant be
  approved by chrome store."* In practice the operator plus the agent that scaffolds and builds the project.
- **The end user** who installs the unpacked build (the RECEIVER of every release): turns on Developer mode, loads the
  folder, later updates in place.
- **The managed-browser user**, whose admin forbids developer mode (`ExtensionDeveloperModeSettings` = 1): cannot use this
  channel at all; the guide sends them to enterprise force-install.
- **Automated consumers:**
  - the scaffolding agent running `create_project(..., project_type="chrome-extension")`, which holds the duty to emit the
    kit;
  - the extension's service worker, which holds the duty to check for updates;
  - the backend (`server/`), which holds the duty to serve the latest version and to admit only the extension's exact
    origin;
  - the release agent (`/fabrik-release`'s unlistable ring, `89` § 7), which holds the duty to build the zip and its
    checksum. It never publishes: Gate 2, "no agent publishes" (`89-extension-launch-checklist.md:136`).

**Primary loop, counted (the step budget): releasing version N+1 = 4 operator steps.**

1. Raise `version` in `extension/package.json`.
2. Run `make release-ext`. It builds, zips, writes the SHA-256 and copies `INSTALL.md` beside the zip. It refuses until
   the key exists and is committed (step 0, once: `pnpm keygen`, back up the `.pem`, commit the `.pub`).
3. Publish the zip, its checksum and `INSTALL.md` beside it (Gate 2, the operator's act).
4. Set the four printed values (`EXTENSION_ID` and the three `EXTENSION_LATEST_*`) in the backend's environment and
   redeploy, only after the zip is reachable
   (`89-extension-launch-checklist.md:125`).

**The end user's update, counted = 4 steps:** see the badge or the popup banner → download the zip → replace the folder's
contents with the new zip's → click **Reload** on the extension's card.

Every piece below traces to one of these personas: the key and exact CORS serve the backend and the update-in-place loop,
the endpoint and the checker serve the end user's update loop, and the INSTALL guide serves the end user and the
managed-browser user.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "a pinned manifest `key`… keep the private key out of the repo (gitignored secrets path)" (01M3WQXZ3Y HOW 1) | IN | § Chosen approach — the key |
| I2 | "tighten CORS to the exact ID" (01M3WQXZ3Y HOW 1; `CORS_ORIGINS: "chrome-extension://*"` named as the workaround) | IN | § Chosen approach — exact-origin CORS |
| I3 | "`GET /extension/latest` returning `{version, download_url}` (public, no auth; config from env)" (01M3WQXZ3Y HOW 2) | IN | § Chosen approach — the endpoint |
| I4 | "`extension/src/lib/update-check.ts`: on startup and on a `chrome.alarms` tick… show 'update available' in the popup with the download link" (01M3WQXZ3Y HOW 3) | IN | § Chosen approach — the update checker |
| I5 | "An `INSTALL.md`… the four steps, the 'keep Developer mode on' note, and the managed-browser caveat" (01M3WQXZ3Y HOW 4) | IN | § Chosen approach — the INSTALL guide |
| I6 | "the `zip` script (`wxt zip`) exists and is enough for the release artifact — no change needed there" (01M3WQXZ3Y WHERE) | IN | § Chosen approach — release target wraps `wxt zip` unchanged |
| I7 | "Generate a keypair at scaffold time (or on first `release`)" — the trade-off named in W-e2af3303 | IN | § Chosen approach (the judge panel's ranking) and § Rejected alternatives |
| I8 | "Today two repos are chrome-extension projects (job-agent, whatsapp-agent)" (01M3WQXZ3Y WHEN) | OUT-OF-SCOPE | the scaffold emits for NEW projects; a backport to those two repos is each repo's own change — named in the reply to fleet on 01M3WQXZ3Y's thread, which each repo's agent receives as a request |
| I9 | "the zip is hosted… with its SHA-256 published beside it" (`89-extension-launch-checklist.md:129`) | IN | § Chosen approach — release target writes the checksum; endpoint serves it |
| I10 | "that value is bumped only after the new zip is reachable" (`89-extension-launch-checklist.md:125`) | IN | § Personas primary loop step 4; § Lifecycle |
| I11 | "the backend still serves the previous extension version" (`89-extension-launch-checklist.md:127`) | IN | § Constraints — the endpoint is additive, no existing route changes |
| I12 | "Gate 2: the operator publishes the zip, its checksum, the guide and the version-manifest bump; no agent publishes" (`89-extension-launch-checklist.md:136`) | IN | § Personas — the release agent builds, never publishes |
| I13 | "Enterprise force-install variant… a `.crx` packed with the pinned key" (`89-extension-launch-checklist.md:133`) | OUT-OF-SCOPE | the kit keeps the private key that variant needs; packing a `.crx` and hosting `updates.xml` stays a per-project step under `89` § 7, not scaffold output |

`Intake: 13 items — 11 IN, 2 OUT-OF-SCOPE (I8, I13, each named above), 0 ASK`

## Goal

A project scaffolded as `chrome-extension` can ship a developer-mode release by default. That release has:
- a stable extension ID;
- a backend that admits only that ID's origin;
- a version endpoint, with an update checker in the extension reading it;
- an INSTALL guide.

This makes the Done-When of `89-extension-launch-checklist.md` § 7 true out of the box instead of per project.

## Why this exists

Today the scaffold emits no manifest `key`: `scaffold.py:5115-5133` writes `manifest:` without one. So every unpacked
install gets a path-derived ID (chromium `ComputeExtensionID` falls back to `GenerateIdForPath`, ledger key-2). Because
the ID changes:
- the backend can only allow every extension by regex (`allow_origin_regex=r"chrome-extension://.*"` at `scaffold.py:5871`;
  `accesscontrolalloworiginlistregex=^chrome-extension://.*$` at `scaffold.py:5991`), which admits any extension's origin;
- an in-place update would change the ID and lose the extension's local state.

Chrome never auto-updates an unpacked extension (`70-chrome-ext.md:61`) and the scaffold ships no checker, so users stay
on old builds. The emitted onboarding page only says to open the popup (01M3WQXZ3Y). The channel the operator ruled
first-class is unusable as shipped.

## What exists today (grounded)

- `wxt.config.ts` with `manifest: { name, description, default_locale, permissions: ['storage','activeTab','contextMenus'], commands, icons }` and no `key` — `src/fabrik/scaffold.py:5115-5133`.
- `extension/package.json` scripts include `"zip": "wxt zip"` — `src/fabrik/scaffold.py:5148`.
- The background service worker registers only `runtime.onInstalled` (onboarding tab, context menu) — `src/fabrik/scaffold.py:5268-5288`.
- The server's CORS is a regex over every extension origin — `src/fabrik/scaffold.py:5867-5876`; its routes are `/health` and `/` — `src/fabrik/scaffold.py:5879-5893`.
- The Traefik CORS middleware is a regex over every extension origin — `src/fabrik/scaffold.py:5991`.
- `templates/chrome-extension/compose.yaml.j2` (rendered by `src/fabrik/template_renderer.py:156`) carries its own
  Traefik CORS labels (`accesscontrolalloworigin=chrome-extension://*`, its lines 17-22) and
  `CORS_ORIGINS=${CORS_ORIGINS:-chrome-extension://*}` (its line 27).
- `.env.example` names `PORT`, `NODE_ENV`, `SERVICE_NAME` only — `src/fabrik/scaffold.py:6060-6068`.
- `.gitignore` already ignores `*.key` and `*.pem` through `_COMMON_GITIGNORE_PATTERNS` — `src/fabrik/scaffold.py:668-673`, written at `src/fabrik/scaffold.py:6071-6088`.
- `templates/chrome-extension/defaults.yaml` sets `CORS_ORIGINS: "chrome-extension://*"`.
- Existing graders for this type are in `tests/test_scaffold.py` (the chrome-extension class from `tests/test_scaffold.py:296`).

## Grounding (executed this session, 2026-10-14)

- **Node built-in crypto mints the key and the ID.** Probe `keygen_probe.mjs` on Node v24.18.0 printed
  `{"keyLen":392,"keyPrefix":"MIIBIjANBgkq","id":"dadgdkoglfgidllpojoilgagpjdkjcli","idValid":true,"privatePemHeader":"(the PKCS#8 PEM header)","roundTrip":true}`:
  `generateKeyPairSync('rsa', {modulusLength: 2048})`, SPKI DER base64 for `key`, SHA-256 first 16 bytes mapped to a–p for
  the ID. No npm package needed.
- **WXT accepts and keeps `manifest.key`.** In WXT 0.21.4 (installed at `/opt/job-agent/extension/node_modules/wxt`),
  `@wxt-dev/browser` 0.2.7 `ManifestBase` declares `key?: string | undefined` ("Specifies your extension's ID for various
  development use cases."). `stripKeys` in `dist/core/utils/manifest.mjs` removes only the `mv2OnlyKeys`, `mv3OnlyKeys`,
  `chromeMv2OnlyKeys` and `firefoxMv3OnlyKeys` lists, none of which names `key`.
- **`cryptography` is not a fabrik dependency.** It is absent from `pyproject.toml` `dependencies`; `uv.lock` pulls it only
  through `google-auth` and `pyjwt`.

## External dependencies (fetched 2026-10-14; every returned fact is a row in the ledger)

Ledger: `docs/reference/research/2026-10-14-chrome-ext-devmode-release-kit-ledger.md` (43 rows).

- **Manifest `key` and the ID** — https://developer.chrome.com/docs/extensions/reference/manifest/key: "This value
  maintains the unique ID of an extension, or theme when it is loaded during development." ID = first 16 bytes of SHA-256
  of the decoded key, hex mapped to a–p (https://chromium.googlesource.com/chromium/src/+/main/components/crx_file/id_util.cc).
- **The private key** — https://developer.chrome.com/docs/extensions/how-to/distribute/host-on-linux: "Do not lose the
  private key!… it will be needed to update the extension" (a `.crx` must be re-signed with it); unpacked loads read only
  the public key.
- **Alarms** — https://developer.chrome.com/docs/extensions/reference/api/alarms: at most once every 30 seconds; the
  `"alarms"` permission is required; persistence across restarts is guaranteed only from Chrome 150, so the alarm is
  re-created on every service-worker start.
- **Startup events** — https://developer.chrome.com/docs/extensions/reference/api/runtime: `onStartup` fires on profile
  start; `onInstalled` on install, update, Chrome update and every reload of an unpacked extension.
- **Backend fetch** — https://developer.chrome.com/docs/extensions/develop/concepts/network-requests: the service worker
  may call its backend cross-origin "as long as the extension requests host permissions".
- **Version format** — https://developer.chrome.com/docs/extensions/reference/manifest/version: one to four dot-separated
  integers, a missing integer equals zero.
- **Developer mode** — Chrome 134+ disables unpacked extensions while the toggle is off
  (https://groups.google.com/a/chromium.org/g/chromium-extensions/c/cTdMVtxxooY); `ExtensionDeveloperModeSettings` 0 allow
  / 1 disallow, and when unset `DeveloperToolsAvailability` = 2 also blocks it
  (https://chromeenterprise.google/policies/extension-developer-mode-settings/).
- **The store and `key`** — the store rejects a first upload carrying `key` (https://github.com/testomatio/browser-extension/issues/391,
  2026-09-25; https://groups.google.com/a/chromium.org/g/chromium-extensions/c/Su50pbNzRms); no official statement exists.

## Constraints Digest

| Quote | Source |
|---|---|
| It runs only while Developer mode stays on. Chrome disables unpacked extensions whenever the toggle is off — say so in the install guide. | `.windsurf/rules/chrome-ext/70-chrome-ext.md:59` |
| A stable ID needs a manifest key. Without it every install gets a different ID and the backend's chrome-extension://<id> CORS allow-list breaks (§ Versioning & Updates). | `.windsurf/rules/chrome-ext/70-chrome-ext.md:62` |
| One-time manual setup. Ship an install guide (enable Developer mode → unzip → Load unpacked → pick the folder), with a short GIF. | `.windsurf/rules/chrome-ext/70-chrome-ext.md:63` |
| Keep the private key out of the repo (secret). | `.windsurf/rules/chrome-ext/70-chrome-ext.md:252` |
| Backend backward-compat: the backend must support the current and previous extension version simultaneously. | `.windsurf/rules/chrome-ext/70-chrome-ext.md:254` |
| Stable ID: the manifest key is pinned, its private key kept out of the repo, and the backend's CORS allow-list carries | `.windsurf/rules/chrome-ext/89-extension-launch-checklist.md:122` |
| Release artifact: the zip is hosted (VPS static site or B2) with its SHA-256 published beside it. | `.windsurf/rules/chrome-ext/89-extension-launch-checklist.md:129` |
| Gate 2: the operator publishes the zip, its checksum, the guide and the version-manifest bump; no agent publishes. | `.windsurf/rules/chrome-ext/89-extension-launch-checklist.md:136` |

## Chosen approach — A: the key is created in the project, on first need, with Node's built-in crypto

The judge panel (three Sonnet seats, approaches given alphabetically with no recommendation, 2026-10-14) ranked **A first
unanimously** and killed B in all three verdicts:
- B needs `cryptography` declared as a new dependency, which is a dependency-file change, or a duplicate shell-out.
- B also mints a private key for store-only projects that will never use one.

One seat's dissent is folded below: before the first release, dev builds have a path-derived ID. Another seat's flip fact
(that WXT might strip `key`) is refuted by the executed `stripKeys` read in § Grounding.

**The delta** (every change is a string `_scaffold_chrome_extension` emits; `path:line` marks the existing touchpoint):

1. **The key.**
   - A new `extension/scripts/keygen.mjs`, emitted beside `wxt.config.ts` (`src/fabrik/scaffold.py:5098`), uses
     `node:crypto` only, as executed in § Grounding (RSA-2048).
   - With no key present, it writes the private key to `extension/.keys/extension-key.pem` (PKCS#8, mode 0600) and the
     base64 SPKI public key to `extension/extension-key.pub`. It then prints the derived extension ID, the
     `EXTENSION_ID=<id>` line for the backend, and a warning to back the `.pem` up now (the enterprise `.crx` and
     store-migration paths need it, § Lifecycle).
   - With a key present, it prints the existing ID and changes nothing: it never overwrites a key, since a new key would
     change the ID under every installed copy.
   - `extension/package.json` scripts (`src/fabrik/scaffold.py:5145-5156`) gain `"keygen": "node scripts/keygen.mjs"`.
   - `.gitignore` (`src/fabrik/scaffold.py:6071-6088`) gains `extension/.keys/`. The `.pem` is already covered by `*.pem`
     at `src/fabrik/scaffold.py:673`; the directory line makes the intent explicit.
   - Keygen is a deliberate one-time step (step 0 of the primary loop), never a side effect of a release (item 3).
   - **Dissent fold:** `pnpm keygen` can run at any time; its header comment and `release-ext`'s refusal say to run it once, early. Until
     then dev builds keep a path-derived ID, which also changes the `https://<id>.chromiumapp.org/` OAuth redirect a
     project registers for `chrome.identity.launchWebAuthFlow` (`70-chrome-ext.md` § Auth); a project that registers
     one runs keygen first (§ Decisions taken).
2. **The build reads the key.**
   - `wxt.config.ts` (`src/fabrik/scaffold.py:5109-5134`) reads `extension-key.pub` when it exists and sets
     `manifest.key` from it. It omits the key when the file is absent, or when the build sets `STORE_BUILD=1`.
   - The store rejects a first upload carrying `key` (§ External dependencies), so a store build leaves it out.
   - `manifest.permissions` gains `alarms`. No `host_permissions` are added (the manifest has none today): the
     extension calls its backend at `VITE_PUBLIC_API_URL`, read as `API_BASE_URL` (`src/fabrik/scaffold.py:5532`),
     as an ordinary CORS request, which the backend's exact-origin CORS (item 5) admits. The existing `authedFetch`
     already refuses any other origin (`src/fabrik/scaffold.py:5544-5561`).
3. **The release target.**
   - The `Makefile` (`src/fabrik/scaffold.py:6000-6056`) gains `release-ext`, which refuses (exit 1, with the next steps
     printed) unless three things hold: `extension/extension-key.pub` exists and is tracked by git, the working tree is
     clean, and `VITE_PUBLIC_API_URL` is an `https://` URL in the environment or in `extension/.env.production` /
     `extension/.env`. So every released zip is a `wxt zip` from a committed tree (`89-extension-launch-checklist.md:120-121`)
     whose key is in that tree, and every released checker has a backend to ask.
   - It then runs `pnpm zip`, which keeps `wxt zip` unchanged (I6), and, in the same shell inside `extension/.output/`,
     writes `<zip>.sha256` beside the zip (the bare file name, so `sha256sum -c` verifies in the download folder) and
     copies `INSTALL.md` there.
   - It prints the four backend values to set: `EXTENSION_ID`, the version, a download-URL placeholder and the SHA-256.
   - It publishes nothing: Gate 2 is the operator's (`89-extension-launch-checklist.md:136`).
4. **The endpoint.**
   - `server/src/<pkg>/main.py` (`src/fabrik/scaffold.py:5879-5893`) gains a public `GET /extension/latest` returning
     `{"version", "download_url", "sha256"}`, read from `EXTENSION_LATEST_VERSION`, `EXTENSION_LATEST_URL` and
     `EXTENSION_LATEST_SHA256`.
   - It returns 404 unless all three are set and non-empty, so a checker treats "no release published" (or a
     half-configured one) as "nothing to do". No auth, as the mail asks; it carries no secret.
   - The route is additive: no existing route changes (I11, `70-chrome-ext.md:254`).
5. **Exact-origin CORS, closed by default.**
   - The server's `CORSMiddleware` (`src/fabrik/scaffold.py:5867-5876`) reads `EXTENSION_ID`, stripped of whitespace:
     - a valid ID (32 characters `a`–`p`) → `allow_origins=[f"chrome-extension://{EXTENSION_ID}"]`;
     - otherwise, with `CORS_ALLOW_ANY_EXTENSION=1` (a local-development opt-in, never deployed) → today's dev regex and a
       structured `cors_any_extension_origin` warning at startup;
     - otherwise → an empty allow-list and a structured `cors_no_extension_id` warning; a non-empty value that is not a
       valid ID also logs a structured `cors_extension_id_invalid` error. The app still starts: `/health` is not a CORS
       request.
   - Local development reads these values from the project's `.env`: the `Makefile`'s `dev` and `dev-server` targets
     pass `--env-file .env` to uvicorn when `.env` exists (the emitted server loads no `.env` itself).
   - So a deploy that forgets the ID admits no extension rather than every extension, and no origin is hardcoded in a
     deployed configuration (`core/35-security-auth.md` "never hardcode origins").
   - The Traefik CORS middleware (`src/fabrik/scaffold.py:5986-5996`: the five `{name}-cors` header labels and the
     router's `middlewares={name}-cors`) is removed from the emitted `compose.yaml`. Preflights then reach FastAPI, and its
     `CORSMiddleware` is the single CORS authority. `templates/chrome-extension/compose.yaml.j2` drops the same labels
     (its lines 17-22) and replaces its `CORS_ORIGINS=${CORS_ORIGINS:-chrome-extension://*}` line (line 27) with the four
     `- VAR=${VAR:-}` lines below.
   - The four env names (`EXTENSION_ID` and the three `EXTENSION_LATEST_*`) reach the container on both compose paths as
     `${VAR:-}` lines that compose fills from the deploy's `.env`: `_write_canonical_compose`'s `extra_env_lines` (it has
     no `env_file`, `src/fabrik/scaffold.py:1094-1102`) and the template's own environment block. "Not set" reaches the
     container as an empty string, which item 5's first rule treats as invalid.
   - `templates/chrome-extension/defaults.yaml` drops `CORS_ORIGINS: "chrome-extension://*"` and adds no entry. The emitted
     chrome-extension server never read `CORS_ORIGINS` (the saas emitter reads its own).
   - With no `host_permissions` (item 2), the service worker's fetch is an ordinary CORS request (the host-permission
     bypass of ledger upd-5 is not requested), so the exact origin is the real gate.
6. **The update checker.**
   - A new `extension/src/lib/update-check.ts` fetches `<base>/extension/latest` with a 10-second timeout and no
     credentials. `<base>` is the backend the app already uses: the Options page's stored `settings.apiUrl`
     (`src/fabrik/scaffold.py:5386-5395`), else `API_BASE_URL`. With no base it returns at once.
   - It does nothing when the manifest has an `update_url` (`browser.runtime.getManifest()`): store and policy installs
     update through Chrome, so they never show this notice.
   - It compares the response's `version` with `chrome.runtime.getManifest().version` integer by integer, a missing
     integer counting as 0 (ledger upd-6, prac-13).
   - When newer, it stores `{version, download_url}` in `storage.local` and sets a badge (`action.setBadgeText`). The
     popup shows an "Update available" banner with the download link.
   - The response is untrusted input: only a valid 1–4-integer version string and an https URL are accepted, and anything
     else is ignored (ledger prac-9).
   - The checks run from `runtime.onStartup`, `runtime.onInstalled` and a `chrome.alarms` alarm every 360 minutes. The
     alarm is created only when `alarms.get('update-check')` finds none: re-creating an alarm replaces it and restarts its
     period, and the service worker restarts on every event (ledger upd-2). The background worker
     (`src/fabrik/scaffold.py:5268-5288`) calls the checker; the popup reads the stored notice.
7. **The INSTALL guide.**
   - A new `extension/INSTALL.md`, which `release-ext` copies beside the zip, gives the end user:
     - the four steps: turn on Developer mode at `chrome://extensions`, unzip, Load unpacked, pick the folder that directly
       contains `manifest.json`;
     - "keep Developer mode on" (Chrome 134+ disables unpacked extensions while it is off);
     - "keep the folder" (Chrome loads from it);
     - updating: replace the folder's contents with the new version's, then click Reload on the card (the pinned key
       keeps the same ID);
     - the managed-browser caveat: `ExtensionDeveloperModeSettings` = 1 forbids it, so ask the admin for enterprise
       force-install;
     - one line each for Edge (same steps) and Brave (an extra "not listed" warning).
   - The packaged onboarding page gains no link: the guide's hosted URL does not exist at scaffold time, and the operator
     publishes the guide beside the zip.

## Rejected alternatives

- **B — keygen in the scaffolder at create time.** Python would need `cryptography` declared (it is only transitive today),
  or a shell-out to `node`/`openssl` that duplicates what the project already has. It also mints and must custody a private
  key for store-only projects. Killed by all three panel seats.
- **C — bring your own key through an env var (Plasmo's `CRX_PUBLIC_KEY`).** It ships the requirement unmet by default and
  repeats a manual step per project (panel: last or killed).
- **Dashboard-first key** (upload a draft to the store and copy "View public key", the official doc's method, ledger key-4).
  It only exists for projects that go to the store, which this channel's projects by definition do not.
- **Key in an env var injected at build time** (per-machine). Every build machine and CI would need it; a committed public
  key is not a secret (ledger key-8), so committing it is simpler and safe.
- **Serve the version from a static `release.json` beside the zip** instead of the backend. It needs a second hosted
  origin the backend's CORS would not cover. The backend already exists, is public and is deployed, and the mail asks for env config.
- **A system notification** (`chrome.notifications`) instead of a badge. The field practice is badge plus popup banner
  (ledger prac-8, prac-9), and notifications would add a permission and nag.
- **Startup-only checks** without an alarm. A long-running browser would never see a release; every off-store example
  uses a periodic alarm.
- **Refuse to start when `EXTENSION_ID` is not a valid ID.** A brand-new project before its first key would refuse to run
  in dev. The chosen default (item 5) closes CORS instead and keeps the app up.
- **Fall back to the any-extension regex when `EXTENSION_ID` is unset** (the first draft). A deploy that forgot one
  variable would admit every extension, credentialed, behind only a log line; the regex now needs a local opt-in.
- **An exact-origin Traefik label with compose interpolation** (`accesscontrolalloworiginlist=chrome-extension://${EXTENSION_ID}`).
  `_write_canonical_compose` writes literal Traefik label values (its invariant 4,
  `src/fabrik/scaffold.py:1029-1031`: such a label once reached Traefik verbatim). Two CORS layers would also have to
  agree, where FastAPI alone, fed by `EXTENSION_ID`, is one source.

## Contract deltas

None. The project's data contract and UI contract are not frozen artifacts of the scaffold. The emitted
`server/` gains one route and the extension gains one popup banner.

## Lifecycle

- **Adoption / first run:** a new project builds exactly as today, with no key and a path ID. The first `pnpm keygen`
  (step 0, run by hand) pins the ID for good; `make release-ext` refuses until it has run and its `.pub` is committed. Projects scaffolded before this change are untouched (I8).
- **Growth:**
  - The endpoint serves one small JSON per check. At one check per user per 6 hours, 10,000 installs cost about 40,000
    requests a day, trivial for the existing FastAPI service.
  - The trigger to revisit is a project serving more than 100,000 installs. At that size the checker's interval or a CDN
    copy of the version payload is the knob.
- **Degradation:**
  - Backend down or slow: the checker times out after 10 seconds, keeps the last stored notice and retries at the next
    alarm. The extension works either way.
  - Bad payload: ignored.
  - Lost private key: unpacked installs are unaffected, since they need only the committed public key (ledger key-2). The
    enterprise `.crx` path is then blocked until a new key, which means a new ID. That is why keygen tells the
    operator to back the key up the moment it creates one.
  - A rotated key: a deliberate act that changes the ID under every installed copy. Users re-install and lose
    `storage.local` (ledger prac-6).
- **Retirement / migration:**
  - A project that later wins store approval builds with `STORE_BUILD=1`, so no `key` is uploaded; the store adds an
    `update_url`, so the checker stays silent there (item 6).
  - Keeping the same ID on the store requires the first upload to carry the private key as `key.pem` at the zip root
    (ledger prac-5). That is why the private key is kept, never discarded.

## fabrik-lib verdict

| Capability | Verdict | Module / why |
|---|---|---|
| Keypair + ID derivation | BUILD (project-local, ~40 lines) | No fabrik-lib module covers browser-extension keys (`/opt/fabrik-lib/README.md` module table); Node built-in `crypto` does it. Not a fabrik-lib candidate: one project type uses it. |
| Version endpoint | BUILD (one FastAPI route) | Too small for a module; lives in the emitted `server/`. |
| Update checker | BUILD (one TS module) | Extension-only; no module. |

## Shape / infra implications

- Scaffold type `chrome-extension` only (`scaffold.py::SCAFFOLD_TYPES`).
- The backend's `shape:` is unchanged (`templates/chrome-extension/defaults.yaml`: `kind: service`, `is_public: false`).
  Reachability comes from the emitted Traefik router and the project's domain; `is_public: true` only turns on Gatus
  uptime monitoring (`src/fabrik/spec_loader.py:269-274`), which a project serving installed copies may want. `89` § 7
  already requires the backend to be reachable.
- New env names on the emitted project (in its `.env.example`):
  - `EXTENSION_ID`
  - `EXTENSION_LATEST_VERSION`
  - `EXTENSION_LATEST_URL`
  - `EXTENSION_LATEST_SHA256`
  - `CORS_ALLOW_ANY_EXTENSION` (local development only; never set in a deploy)
  - The extension reuses its existing `VITE_PUBLIC_API_URL` (`src/fabrik/scaffold.py:5532`); no new client variable.

## Documentation landing sites

- The emitted project documents itself:
  - `extension/INSTALL.md` (end user);
  - the `Makefile` `release-ext` target's comment and the keygen script's header (developer);
  - `.env.example` rows for the new variables.
- In the hub:
  - `CHANGELOG.md` (one entry);
  - `docs/DECISIONS.md` (the approach row, minted with the spec's approval);
  - `.windsurf/rules/chrome-ext/70-chrome-ext.md` § Distribution Model gains one sentence saying the scaffold ships the
    kit (kaizen's wording beat, sent as a request; the facts there are unchanged).

## Cost

About 300 emitted lines in `src/fabrik/scaffold.py`, a few lines in `templates/chrome-extension/defaults.yaml` and
`compose.yaml.j2`, and graders in `tests/test_scaffold.py` and `tests/test_scaffold_chrome_ext_wxt.py`. No new dependency in fabrik or in the emitted project. Runtime cost per project: one
small route and one 6-hour alarm.

## Validation

Graders in `tests/test_scaffold.py`, each watched red first:

- **The emitted scripts:**
  1. The scaffold emits `extension/scripts/keygen.mjs`.
  2. Running it under Node in a temp dir writes a 0600 PEM and a `.pub` whose ID matches the derivation in § Grounding.
  3. A second run changes nothing.
- **The build config:**
  4. `wxt.config.ts` reads `extension-key.pub` and honours `STORE_BUILD`.
  5. The manifest permissions include `alarms`.
- **The server:**
  6. The emitted server answers `GET /extension/latest` with 404 unless all three values are set and non-empty, and with the three fields when they are (FastAPI
     `TestClient`).
  7. With a valid `EXTENSION_ID`, a preflight from another extension origin is refused; with none, no extension origin
     is admitted unless `CORS_ALLOW_ANY_EXTENSION=1`.
- **The rest of the emitted tree:**
  8. `.gitignore` names `extension/.keys/`.
  9. `INSTALL.md` carries the four steps, the keep-Developer-mode-on note and the `ExtensionDeveloperModeSettings` caveat.
  10. The Makefile's `release-ext` refuses without a committed key or an https backend URL, writes a `.sha256`, copies
      `INSTALL.md`, and never publishes.
  11. The emitted `compose.yaml` and the `compose.yaml.j2` template carry no `-cors` Traefik label and no `CORS_ORIGINS`,
      and both pass the four env names through.
  12. The checker returns early with no backend URL or when the manifest has an `update_url`, and creates its alarm only
      when none exists.
  13. The Makefile's `dev` and `dev-server` pass `--env-file .env` to uvicorn when `.env` exists.

## Decisions taken

- **The key's origin and timing:** approach A (in-project, on first need, Node built-in crypto), ranked first unanimously
  by the judge panel. The ledger row is minted at the approval gate (`/fabrik-plan-review`, this spec being `Size: small`).
- **CORS without a valid `EXTENSION_ID`:** closed (an empty allow-list) and warned; the any-extension regex only behind
  the local `CORS_ALLOW_ANY_EXTENSION=1` opt-in (approval panel, 2026-10-15). No exception to `core/35` remains.
- **Release discipline:** `release-ext` builds only from a committed tree whose `.pub` is tracked, with an https backend
  URL; keygen is a separate, deliberate step that tells the operator to back the key up.
- **OAuth redirects:** a project that registers a `chromiumapp.org` redirect runs keygen before registering it, since
  the redirect's host is the extension ID.
- **No `host_permissions`:** the backend call is an ordinary CORS request, so the exact origin binds it.
- **A store build strips `key`** (`STORE_BUILD=1`).

## Open / blocking unknowns

- **Resolved:**
  - WXT's handling of `key`: executed in § Grounding.
  - The store's first-upload rejection: community-confirmed, and the design strips it either way.
- **Open, non-blocking:**
  - Whether the store also rejects `key` on later updates (reports conflict, ledger key-9 and prac-7). The design never
    uploads one, so either answer changes nothing.
  - Resolution step: none needed. Recorded so a later store-migration spec does not re-litigate it.
- **Resolved by the plan's grounding:**
  - The backend-origin variable is `VITE_PUBLIC_API_URL` (`src/fabrik/scaffold.py:5532`).
