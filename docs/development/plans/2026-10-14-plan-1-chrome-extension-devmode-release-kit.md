# Plan — chrome-extension scaffold emits the developer-mode release kit (W-e2af3303)

Status: DRAFT
Profile: small
**Owner:** —
**Surface:** `git rev-parse HEAD` = 12333be10 at authoring; `src/fabrik/scaffold.py::_scaffold_chrome_extension` (`:5075-6136`)

Spec: `docs/superpowers/specs/2026-10-14-chrome-extension-devmode-release-kit-design.md` (DRAFT at 12333be10, `Size: small`,
`Profile: delta`). `/fabrik-plan-review` grades its sections together with this plan and flips both. Source: fleet mail 01M3WQXZ3Y → work
item W-e2af3303. Estimated diff: ≈260 code lines in TWO code files, tests excluded — in `src/fabrik/scaffold.py`:
keygen script ≈45, `wxt.config.ts` key/permissions ≈20, package scripts ≈2, update checker ≈65, background wiring ≈8,
popup banner ≈20, INSTALL.md ≈45 (emitted doc text), onboarding link ≈3, Makefile `release-ext` ≈14, `.gitignore` ≈2,
server endpoint ≈25, exact CORS ≈12, Traefik label ≈3, `.env.example` ≈6 (sum ≈270); `templates/chrome-extension/defaults.yaml`
≈2. Tests ≈330 lines in `tests/test_scaffold.py`.

## What this plan is

Three inline phases the orchestrator codes itself in the worktree; no coder is dispatched:

- **A — the extension and the release**: the keygen script, the manifest key and permissions, the update checker, the
  popup banner, the INSTALL guide, the onboarding link, `.gitignore`, the Makefile `release-ext` target (spec § Chosen
  approach items 1-3, 6, 7).
- **B — the backend**: `GET /extension/latest`, exact-origin CORS in FastAPI and Traefik, `defaults.yaml`, `.env.example`
  (spec § Chosen approach items 4-5).
- **C — Finish**: the whole-plan `/fabrik-review`, CHANGELOG, the decision row, the pack-sentence request, the gate.

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish: one heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor) and one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I13 (11 IN, 2 OUT-OF-SCOPE) | IN as dispositioned there | Phases A and B, per the spec rows |
| I2 | *"Plan it as Profile: small"* (this run's brief) | IN | this header |
| I3 | *"Open for the plan: the backend-origin variable the emitted extension already uses (src/lib/api/config.ts — grep the emitter)"* | IN — resolved: `VITE_PUBLIC_API_URL`, read as `API_BASE_URL` at `src/fabrik/scaffold.py:5532`; the spec's placeholder corrected in this run | Phase A step 2; spec § Chosen approach item 2 |
| I4 | *"graders in tests/test_scaffold.py (chrome-extension class from :296) each watched red first"* | IN | Phases A and B Behaviour Contract; Global Constraints |
| I5 | *"The plan-review flips spec + plan to CONVERGED and holds the approval gate (Opus + Fable panel, D-613)"* | IN | the `/fabrik-plan-review` run this command invokes last |

## What we already agreed (citations, not restatement)

- Goal, personas and step budget, lifecycle: `spec § Goal`, `spec § Personas`, `spec § Lifecycle`; why: `spec § Why this exists`.
- Today's emitter: `spec § What exists today`; executed facts: `spec § Grounding`; external facts: `spec § External dependencies`
  and the ledger `docs/reference/research/2026-10-14-chrome-ext-devmode-release-kit-ledger.md`.
- The delta 1-7: `spec § Chosen approach`; cost: `spec § Cost`; validation: `spec § Validation`.
- Chosen approach A (judge panel 3-0) and the folded dissent: `spec § Chosen approach`; rejected alternatives:
  `spec § Rejected alternatives`; decisions: `spec § Decisions taken`. The approval row is minted by `/fabrik-plan-review`
  at its gate (a `Size: small` spec is approved there, not here).

## Global Constraints (every phase inherits these)

- **Scaffold output only.** Every change is text `_scaffold_chrome_extension` writes; no other scaffold type and no hub
  runtime path changes. Projects already scaffolded are untouched (spec I8).
- **No new dependency** in fabrik or in the emitted project: the keygen uses `node:crypto` (`spec § Grounding`), the
  checker uses `browser.*` APIs WXT already ships; no dependency file is touched (`core/10-python.md:30`).
- **The private key never enters a tracked path**: the emitted `.gitignore` ignores `extension/.keys/` and `*.pem`
  (`src/fabrik/scaffold.py:673`); the keygen writes the PEM with mode 0600 and never overwrites an existing key.
- **No agent publishes** (`89-extension-launch-checklist.md:136`): `release-ext` builds, zips and checksums only.
- **The store build carries no `key`**: `STORE_BUILD=1` omits it (`spec § Chosen approach` item 2).
- Tests: one per behaviour, watched-fail-first (`core/45-testing-strategy.md:20`, `:22`). Each grader scaffolds a project
  with `create_project(..., project_type="chrome-extension")` into `tmp_path` in offline mode, the existing class's pattern
  (`tests/test_scaffold.py:296-340`), and asserts on emitted files and on behaviour that runs without network: the keygen
  under `node` in `tmp_path`, the server under FastAPI's `TestClient`. Every grader is seen red against today's emitter
  first; red-on-revert runs in a throwaway worktree (`git worktree add --detach <scratch>/probe HEAD`), never the shared
  checkout.
- Seats never mutate git state; never read `~/.claude*`; never run `uv` or `pip`; a seat runs Python as `.venv/bin/python
  …`; seat scratch paths are absolute; a seat never executes a script it has not read, nor one that deletes, deploys,
  provisions, writes outside its scratch or contacts a non-local host.
- **Execution discipline (native seats only, D-181):** every phase ends with `/fabrik-review-scoped` on its surface (the
  floor of three native seats, stamped with `command_run.py dispatch`), not handing on until its closing pass confirms
  zero defects. The Finish `/fabrik-review` partitions the whole-plan diff by file into a Sonnet and a Haiku finder per
  slice (D-344), the orchestrator executing every refutation.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (MATCHED — scaffold.py) | no deps-file edit | `core/10-python.md:30` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED — tests/test_scaffold.py) | one test per behaviour; watched-fail-first | `core/45-testing-strategy.md:20`, `:22` |
| `.windsurf/rules/chrome-ext/70-chrome-ext.md` (by description) | key, update checker, install guide, exact CORS | `70-chrome-ext.md:59-63`, `:179`, `:252-254` |
| `.windsurf/rules/chrome-ext/89-extension-launch-checklist.md` (by description) | § 7 gates: key, checksum, no agent publishes | `89-extension-launch-checklist.md:122-136` |
| `fabrik-lib` | none covers extension keys — BUILD in the emitter | `spec § fabrik-lib verdict` |
| `specs/services/*.yaml` `shape:` | unchanged; a project serving `/extension/latest` publicly flips `is_public` itself | `spec § Shape / infra implications` |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source | Rule |
|---|---|---|
| "Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it." | .windsurf/rules/core/10-python.md:30 | Deps |
| "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | .windsurf/rules/core/45-testing-strategy.md:20 | Behaviour Contract |
| "**Watched-fail-first** (for tests this change adds or modifies" | .windsurf/rules/core/45-testing-strategy.md:22 | Red first |
| "Keep the private key out of the repo (secret)." | .windsurf/rules/chrome-ext/70-chrome-ext.md:252 | Secret |
| "Gate 2: the operator publishes the zip, its checksum, the guide and the version-manifest bump; no agent publishes." | .windsurf/rules/chrome-ext/89-extension-launch-checklist.md:136 | Gate 2 |

## Phase A — the extension and the release

Appetite: 120

**Interfaces — Produces** (emitted by `src/fabrik/scaffold.py::_scaffold_chrome_extension`):
- `extension/scripts/keygen.mjs` — `node:crypto` only. No key on disk → writes `extension/.keys/extension-key.pem` (PKCS#8,
  mode 0600, `mkdir -p` 0700) and `extension/extension-key.pub` (one line, base64 SPKI DER), prints `extension id: <id>`
  and `EXTENSION_ID=<id>`. Key present → prints the same two lines from the existing `.pub`, writes nothing. A `.pub`
  without its `.pem` → prints the ID and a warning that the private key is missing (the enterprise and store-migration
  paths need it), exit 0.
- `wxt.config.ts` (`:5109-5134`) — reads `extension-key.pub` when it exists and `process.env.STORE_BUILD !== '1'`, and sets
  `manifest.key`; adds `'alarms'` to `permissions`; sets `host_permissions` to `[<origin of VITE_PUBLIC_API_URL>/*]` when
  that variable is set (the origin `src/lib/api/config.ts` already reads, `:5532`), else omits it.
- `extension/package.json` scripts (`:5145-5156`) gain `"keygen": "node scripts/keygen.mjs"`.
- `extension/src/lib/update-check.ts` — `checkForUpdate()`: GET `${API_BASE_URL}/extension/latest`, `credentials:
  'omit'`, `AbortSignal.timeout(10000)`; a non-2xx (404 = nothing published) or a body failing validation (version matches
  `^\d{1,5}(\.\d{1,5}){0,3}$`, `download_url` starts with `https://`) does nothing. `isNewer(a, b)` compares integer by
  integer, a missing integer counting 0. Newer → `browser.storage.local.set({updateNotice: {version, download_url}})` and
  `browser.action.setBadgeText({text: '↑'})`; not newer → clears both. `scheduleUpdateChecks()` re-creates the
  `update-check` alarm (`periodInMinutes: 360`) and runs one check.
- background (`:5268-5288`) — `scheduleUpdateChecks()` from `runtime.onStartup` and `runtime.onInstalled`;
  `alarms.onAlarm` for `update-check` runs `checkForUpdate()`.
- popup `main.tsx` (`:5353`) — reads `updateNotice` from `storage.local` and shows "Update available — v<version>" with the
  download link, through the existing i18n locale (`en` and `tr` strings added to `src/locales`).
- `extension/INSTALL.md` — spec § Chosen approach item 7 verbatim in content; `extension/public/onboarding.html` (`:5675`)
  gains one line linking to it.
- `Makefile` (`:6000-6056`) — `release-ext`: `cd extension && pnpm keygen && pnpm zip`, then `sha256sum` of the newest
  `.output/*-chrome.zip` into `<zip>.sha256`, then prints the three `EXTENSION_LATEST_*` lines with the version from
  `package.json`, a `<download-url>` placeholder and the checksum. Publishes nothing.
- `.gitignore` (`:6071-6088`) gains `extension/.keys/`.

**Steps** (sequential):
1. Write the Phase A graders (Behaviour Contract below) in `tests/test_scaffold.py`'s chrome-extension class; run them and
   see each red against today's emitter.
2. Emit the keygen script, the `wxt.config.ts` change and the package script.
3. Emit the update checker, the background wiring and the popup banner with its locale strings.
4. Emit `INSTALL.md`, the onboarding link, the Makefile target and the `.gitignore` line.
5. Run the Phase A graders green, then the whole chrome-extension class (`tests/test_scaffold.py -k chrome`), green.
6. `/fabrik-review-scoped` on Phase A's surface; fix what it finds.

**Behaviour Contract (Phase A)**

| # | Given | When | Then |
|---|---|---|---|
| A1 | a fresh chrome-extension scaffold | `node extension/scripts/keygen.mjs` runs in it | `.keys/extension-key.pem` exists with mode 0600, `extension-key.pub` holds 392 base64 chars, and the printed ID equals the SHA-256-first-16-bytes a–p derivation of the decoded `.pub` |
| A2 | a key already present | keygen runs again | both files are byte-identical and the same ID prints |
| A3 | the emitted `wxt.config.ts` | read | it sets `manifest.key` from `extension-key.pub` only when the file exists and `STORE_BUILD` is not `1`, lists `alarms`, and derives `host_permissions` from `VITE_PUBLIC_API_URL` |
| A4 | the emitted `update-check.ts` | read | it requests `/extension/latest` with a 10 s timeout and no credentials, validates version and https URL, compares integer by integer, and sets the badge only when newer |
| A5 | the emitted background | read | `onStartup` and `onInstalled` schedule checks and `onAlarm` handles `update-check` |
| A6 | the emitted `INSTALL.md` | read | it names `chrome://extensions`, Load unpacked, keep Developer mode on, Reload to update, and `ExtensionDeveloperModeSettings` |
| A7 | the emitted `.gitignore` and Makefile | read | `.gitignore` names `extension/.keys/`; `release-ext` runs keygen and zip, writes a `.sha256`, and contains no upload, `scp`, `rsync` or `curl` |

## Phase B — the backend

Appetite: 60

**Interfaces — Produces:**
- server `main.py` (`:5839-5894`) — `@app.get("/extension/latest")`: 404 `{"detail": "no release published"}` while
  `EXTENSION_LATEST_VERSION` is unset or empty; else 200 `{"version", "download_url", "sha256"}` from
  `EXTENSION_LATEST_VERSION`, `EXTENSION_LATEST_URL`, `EXTENSION_LATEST_SHA256` (`os.getenv`, read per request so a
  redeploy is the only change needed). Public, no auth.
- CORS (`:5867-5876`) — `EXTENSION_ID` set → `allow_origins=[f"chrome-extension://{EXTENSION_ID}"]` and no regex; unset
  → today's `allow_origin_regex` plus one `logger.warning("cors_any_extension_origin")` at startup in `lifespan`.
- Traefik (`:5986-5996`) — the regex label becomes
  `traefik.http.middlewares.{name}-cors.headers.accesscontrolalloworiginlist=chrome-extension://${{EXTENSION_ID}}` (the
  f-string escapes the braces so compose interpolates `EXTENSION_ID`); the plan-review verifies `_write_canonical_compose`
  passes labels through unquoted.
- `templates/chrome-extension/defaults.yaml` — `CORS_ORIGINS: "chrome-extension://*"` replaced by `EXTENSION_ID: ""`
  (Step 1 greps that nothing reads `CORS_ORIGINS`).
- `.env.example` (`:6060-6068`) — names `EXTENSION_ID`, `EXTENSION_LATEST_VERSION`, `EXTENSION_LATEST_URL`,
  `EXTENSION_LATEST_SHA256`, each with a one-line comment.

**Steps** (sequential):
1. `command grep -rn CORS_ORIGINS src/ templates/ tests/` and record the count in Evidence; write the Phase B graders and see
   each red.
2. Emit the endpoint, the CORS branch and the startup warning.
3. Emit the Traefik label, the `defaults.yaml` line and the `.env.example` rows.
4. Phase B graders green; the whole chrome-extension class green; `tests/orchestrator/test_template_defaults.py` green.
5. `/fabrik-review-scoped` on Phase B's surface; fix what it finds.

**Behaviour Contract (Phase B)**

| # | Given | When | Then |
|---|---|---|---|
| B1 | the emitted server, `EXTENSION_LATEST_VERSION` unset | `GET /extension/latest` (TestClient) | 404 |
| B2 | the three `EXTENSION_LATEST_*` set | `GET /extension/latest` | 200 with exactly those three values |
| B3 | `EXTENSION_ID=abc…` (32 a–p) | a preflight from `chrome-extension://<another id>` | no `access-control-allow-origin` header; from the pinned ID, the header is present |
| B4 | `EXTENSION_ID` unset | the app starts | the `cors_any_extension_origin` warning is logged |
| B5 | the emitted `compose.yaml` and `.env.example`; `defaults.yaml` | read | the exact-origin label with `${EXTENSION_ID}`, no `originlistregex`; the four env names present; no `CORS_ORIGINS` |

## Phase C — Finish

Appetite: 60

**Steps** (sequential):
1. The whole-plan `/fabrik-review` (D7 floor: the whole-plan diff by file, a Sonnet and a Haiku finder per slice, the
   orchestrator executing every candidate), one receipt under `docs/development/reviews/`.
2. `CHANGELOG.md` entry; `docs/DECISIONS.md` row for the built kit (the approval row is `/fabrik-plan-review`'s).
3. A request to kaizen (corpus wording is its beat): one sentence in `70-chrome-ext.md` § Distribution Model saying the
   scaffold ships the kit by default.
4. `python scripts/final_gate.py --check --json` green; commit by pathspec with trailers; push; `merge_request.py
   request`; on merge, infra closes W-e2af3303 in the main store.

## File Scope (owned paths)

- `src/fabrik/scaffold.py` (only `_scaffold_chrome_extension`, `:5075-6136`)
- `templates/chrome-extension/defaults.yaml`
- `tests/test_scaffold.py`
- `docs/superpowers/specs/2026-10-14-chrome-extension-devmode-release-kit-design.md`, this plan, the review receipt,
  `CHANGELOG.md`, `docs/DECISIONS.md`

## Evidence

Grounded at authoring (2026-10-14), executed:

- The backend-origin variable — `src/fabrik/scaffold.py:5532`:

```text
$ command grep -n 'VITE_PUBLIC_API_URL' src/fabrik/scaffold.py | head -2
5532:export const API_BASE_URL = (import.meta.env.VITE_PUBLIC_API_URL as string | undefined) ?? '';
5770:`API_BASE_URL` from `VITE_PUBLIC_API_URL`. `pnpm generate-api` (needs the backend `openapi.json`)
```

- The keygen mechanism (spec § Grounding) — Node v24.18.0:

```text
$ node keygen_probe.mjs
{"node":"v24.18.0","keyLen":392,"keyPrefix":"MIIBIjANBgkq","id":"dadgdkoglfgidllpojoilgagpjdkjcli","idValid":true,"roundTrip":true}
```

- WXT keeps `manifest.key` — `@wxt-dev/browser` 0.2.7 `ManifestBase` (`src/gen/index.d.ts:9595`, `key?: string | undefined`);
  `stripKeys` names only the MV2/MV3-only lists (`wxt/dist/core/utils/manifest.mjs:359-396`).

## Self-audit

- Every behaviour in `spec § Validation` maps to a row: spec 1-3 → A1/A2, 4-5 → A3, 6 → B1/B2, 7 → B3, 8 → A7, 9 → A6,
  10 → A7. A4, A5, B4 and B5 are added for the checker, the wiring, the warning and the compose label.
- Diff estimate ≈270 code lines in 2 files: inside `Profile: small` (≤ ~400, ≤ 5).
- Every touchpoint is a `path:line` in today's emitter; every new file is named by path.

## Residual unknowns

- **R1 — compose interpolation of the Traefik label.** If `_write_canonical_compose` quotes labels so that `${EXTENSION_ID}`
  is not interpolated, Phase B falls back to writing the label only when the scaffold is given an ID, and documents
  `EXTENSION_ID` as compose-interpolated. Resolution: Phase B step 1 reads the function and the plan-review verifies.
- **R2 — WXT's zip name.** `release-ext` takes the newest `.output/*-chrome.zip` rather than assuming the exact name
  (`70-chrome-ext.md:65` states the `<name>-<version>-chrome.zip` shape).
