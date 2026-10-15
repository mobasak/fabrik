# Plan — chrome-extension scaffold emits the developer-mode release kit (W-e2af3303)

Status: EXECUTED 2026-10-15
Whole-plan review: docs/development/reviews/2026-10-15-plan-1-chrome-extension-devmode-release-kit-review.md
Profile: small
**Owner:** —
**Surface:** `git rev-parse HEAD` = 12333be10 at authoring, 473ed4978 at the approval panel (only the two documents changed between); `src/fabrik/scaffold.py::_scaffold_chrome_extension` (`:5075-6136`)

Spec: `docs/superpowers/specs/2026-10-14-chrome-extension-devmode-release-kit-design.md` (DRAFT at 12333be10, `Size: small`,
`Profile: delta`). `/fabrik-plan-review` grades its sections together with this plan and flips both. Source: fleet mail 01M3WQXZ3Y → work
item W-e2af3303. Estimated diff: ≈335 code lines in one code file and two templates, tests excluded — in `src/fabrik/scaffold.py`:
keygen script ≈50, `wxt.config.ts` key/permissions ≈20, package scripts ≈2, update checker ≈80, background wiring ≈8,
popup banner ≈20, INSTALL.md ≈45 (emitted doc text), Makefile `release-ext` with its refusals ≈30, `.gitignore` ≈2,
server endpoint ≈25, closed-by-default CORS ≈25, Traefik CORS labels removed ≈10, `.env.example` ≈8, dev `--env-file` ≈2
(sum ≈327);
`templates/chrome-extension/defaults.yaml` ≈2; `templates/chrome-extension/compose.yaml.j2` ≈7 lines replaced. Tests
≈380 lines in `tests/test_scaffold.py` and `tests/test_scaffold_chrome_ext_wxt.py`.

## What this plan is

Three inline phases the orchestrator codes itself in the worktree; no coder is dispatched:

- **A — the extension and the release**: the keygen script, the manifest key and permissions, the update checker, the
  popup banner, the INSTALL guide, `.gitignore`, the Makefile `release-ext` target (spec § Chosen
  approach items 1-3, 6, 7).
- **B — the backend**: `GET /extension/latest`, exact-origin CORS in FastAPI with the Traefik CORS labels removed,
  `defaults.yaml`, `compose.yaml.j2`, `.env.example`
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
| `.windsurf/rules/core/40-documentation.md` (MATCHED — CHANGELOG.md, docs/DECISIONS.md, this plan) | one CHANGELOG entry; the decision row in the same change | `core/40-documentation.md:134` |
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
| "**Gate 2:** the operator publishes the zip, its checksum, the guide and the version-manifest bump; no agent publishes." | .windsurf/rules/chrome-ext/89-extension-launch-checklist.md:136 | Gate 2 |
| "**Enforced:** Gate-checked, no exceptions. Every code-shipping ticket must produce exactly one entry." | .windsurf/rules/core/40-documentation.md:134 | CHANGELOG |

## Phase A — the extension and the release — ✅ EXECUTED 2026-10-15 (723674561)

Appetite: 120

**Interfaces — Produces** (emitted by `src/fabrik/scaffold.py::_scaffold_chrome_extension`):
- `extension/scripts/keygen.mjs` — `node:crypto` only, `generateKeyPairSync('rsa', {modulusLength: 2048})` (spec §
  Grounding). No key on disk → writes `extension/.keys/extension-key.pem` (PKCS#8,
  mode 0600, `mkdir -p` 0700) and `extension/extension-key.pub` (one line, base64 SPKI DER), prints `extension id: <id>`
  and `EXTENSION_ID=<id>`. Key present → prints the same two lines from the existing `.pub`, writes nothing. A `.pub`
  without its `.pem` → prints the ID and a warning that the private key is missing (the enterprise and store-migration
  paths need it), exit 0. On creating a key it also prints "back up extension/.keys/extension-key.pem now" and the
  next steps (commit `extension-key.pub`, push).
- `wxt.config.ts` (`:5109-5134`) — reads `extension-key.pub` when it exists and `process.env.STORE_BUILD !== '1'`, and sets
  `manifest.key`; adds `'alarms'` to `permissions`; adds no `host_permissions` (spec § Chosen approach item 2).
- `extension/package.json` scripts (`:5145-5156`) gain `"keygen": "node scripts/keygen.mjs"`.
- `extension/src/lib/update-check.ts` — `checkForUpdate()`: returns at once when `browser.runtime.getManifest()` has an
  `update_url` (store or policy install) or when no base resolves; the base is the stored `settings.apiUrl`
  (`:5386-5395`, the Options page's value) else `API_BASE_URL` (`:5532`). Then GET `<base>/extension/latest`,
  `credentials: 'omit'`, `AbortSignal.timeout(10000)`; a non-2xx (404 = nothing published) or a body failing validation (version matches
  `^\d{1,5}(\.\d{1,5}){0,3}$`, `download_url` starts with `https://`) does nothing. `isNewer(a, b)` compares integer by
  integer, a missing integer counting 0. Newer → `browser.storage.local.set({updateNotice: {version, download_url}})` and
  `browser.action.setBadgeText({text: '↑'})`; not newer → clears both. `scheduleUpdateChecks()` creates the
  `update-check` alarm (`periodInMinutes: 360`) only when `browser.alarms.get('update-check')` finds none (re-creating
  an alarm replaces it and restarts its period) and runs one check.
- background (`:5268-5288`) — `scheduleUpdateChecks()` from `runtime.onStartup` and `runtime.onInstalled`;
  `alarms.onAlarm` for `update-check` runs `checkForUpdate()`.
- popup `main.tsx` (`:5353`) — reads `updateNotice` from `storage.local` and shows "Update available — v<version>" with the
  download link, through the existing i18n locale (`en` and `tr` strings added to `src/locales`).
- `extension/INSTALL.md` — spec § Chosen approach item 7 verbatim in content (updating = replace the folder's
  contents, then Reload). The onboarding page is not changed (spec item 7).
- `Makefile` (`:6000-6056`) — `release-ext`, added to `.PHONY` (`:6001`). Its first recipe line refuses (exit 1, printing
  the next steps) unless `git ls-files --error-unmatch extension/extension-key.pub` succeeds, `git status --porcelain`
  is empty, and `VITE_PUBLIC_API_URL` starts with `https://` in the environment or in `extension/.env.production` /
  `extension/.env`. Its second is ONE line (each make line is its own shell) — `cd extension && pnpm zip && cd .output
  && zip=$$(ls -t *-chrome.zip | head -1) && sha256sum "$$zip" > "$$zip.sha256" && cp ../INSTALL.md .` (the bare name,
  so `sha256sum -c` verifies beside the published zip) — and, still in that line, prints the four backend values:
  `EXTENSION_ID` from the `.pub`, the version from `package.json`, a `<download-url>` placeholder and the checksum.
  It never runs keygen and publishes nothing.
- `.gitignore` (`:6071-6088`) gains `extension/.keys/`.

**Steps** (sequential):
1. Write the Phase A graders (Behaviour Contract below) in `tests/test_scaffold.py`'s chrome-extension class; run them and
   see each red against today's emitter.
2. Emit the keygen script, the `wxt.config.ts` change and the package script; update the two existing tests that pin
   the exact permissions (`tests/test_scaffold_chrome_ext_wxt.py:138` and `:350`) to include `alarms`.
3. Emit the update checker, the background wiring and the popup banner with its locale strings.
4. Emit `INSTALL.md`, the Makefile target and the `.gitignore` line.
5. Run the Phase A graders green, then the whole chrome-extension class (`tests/test_scaffold.py -k chrome`) and
   `tests/test_scaffold_chrome_ext_wxt.py`, green. The build test carries `needs_network`, which `pyproject.toml:106`
   deselects by default, so run it explicitly — `pytest tests/test_scaffold_chrome_ext_wxt.py -m needs_network -k
   builds` — and paste its result in Evidence (it skips without node/pnpm and says so).
6. `/fabrik-review-scoped` on Phase A's surface; fix what it finds.

**Behaviour Contract (Phase A)**

| # | Given | When | Then |
|---|---|---|---|
| A0 | a fresh chrome-extension scaffold | read (never skips) | `extension/scripts/keygen.mjs` exists and `package.json` has the `keygen` script |
| A1 | a fresh chrome-extension scaffold (skips without `node`, saying so) | `node extension/scripts/keygen.mjs` runs in it | `.keys/extension-key.pem` exists with mode 0600, `extension-key.pub` holds 392 base64 chars, the printed ID equals the SHA-256-first-16-bytes a–p derivation of the decoded `.pub`, and the output tells the operator to back the `.pem` up |
| A2 | a key already present (skips without `node`) | keygen runs again | both files are byte-identical and the same ID prints |
| A3 | the emitted `wxt.config.ts`; and a real build (run with `-m needs_network`, where node and pnpm exist) | read; `pnpm keygen` then `wxt build` (the existing `test_wxt_scaffold_builds_and_manifest_has_permissions`, extended) | it sets `manifest.key` from `extension-key.pub` only when the file exists and `STORE_BUILD` is not `1`, lists `alarms`, and has no `host_permissions`; the built `manifest.json` carries `key` equal to the `.pub` and the permissions list with `alarms` |
| A4 | the emitted `update-check.ts` | read | it returns early when the manifest has an `update_url` or no base resolves, prefers the stored `settings.apiUrl` over `API_BASE_URL`, requests `/extension/latest` with a 10 s timeout and no credentials, validates version and https URL, compares integer by integer, and sets the badge only when newer |
| A5 | the emitted background and checker | read | `onStartup` and `onInstalled` schedule checks, the alarm is created only after `alarms.get('update-check')` finds none, and `onAlarm` handles `update-check` |
| A6 | the emitted `INSTALL.md` | read | it names `chrome://extensions`, Load unpacked, keep Developer mode on, replace the folder's contents and Reload to update, and `ExtensionDeveloperModeSettings` |
| A7 | the emitted `.gitignore` and Makefile; and a scaffold in a temp git repo with no committed `.pub` | read; the `release-ext` recipe extracted from its target line to the next target; `make release-ext` run in the temp repo | `.gitignore` names `extension/.keys/`; `.PHONY` lists `release-ext`; the recipe checks the tracked `.pub`, a clean tree and an https `VITE_PUBLIC_API_URL`, never runs keygen, zips, writes a `.sha256` with the bare name, copies `INSTALL.md`, prints the four values, and contains no upload, `scp`, `rsync` or `curl` (the existing `docker-smoke` target's `curl` is outside the extracted recipe); the run exits 1 before zipping and prints the next steps |

## Phase B — the backend — ✅ EXECUTED 2026-10-15 (4f29e9e6a)

Appetite: 60

**Interfaces — Produces:**
- server `main.py` (`:5839-5894`) — `@app.get("/extension/latest")`: 404 `{"detail": "no release published"}` unless
  all three of `EXTENSION_LATEST_VERSION`, `EXTENSION_LATEST_URL`, `EXTENSION_LATEST_SHA256` are set and non-empty;
  else 200 `{"version", "download_url", "sha256"}` from them (`os.getenv`, read per request, so a redeploy with the
  new `.env` values is the only change needed once the compose passes them through, below). Public, no auth.
- CORS (`:5867-5876`) — `EXTENSION_ID`, stripped, matching `^[a-p]{32}$` → `allow_origins=[f"chrome-extension://{EXTENSION_ID}"]`
  and no regex; otherwise `CORS_ALLOW_ANY_EXTENSION=1` → today's `allow_origin_regex` and one
  `logger.warning("cors_any_extension_origin")` at startup in `lifespan`; otherwise `allow_origins=[]` and one
  `logger.warning("cors_no_extension_id")`; a non-empty invalid value also logs `logger.error("cors_extension_id_invalid")`. (The compose's `${EXTENSION_ID:-}` delivers "not set" as `""`.)
- compose (`:5974-5996`) — the `extra_labels` tuple drops all six CORS entries (the five `{name}-cors` header labels and
  `routers.{name}.middlewares={name}-cors`) and its in-tuple comment; the call passes no `extra_labels`, and the comment
  block above the call (`:5975-5978`, "so we add CORS middleware via Traefik") is rewritten to say FastAPI answers CORS.
  An env-interpolated label is not an option: `_write_canonical_compose` invariant 4 (`:1029-1031`). The call gains
  `extra_env_lines=(…)` with `- EXTENSION_ID=${EXTENSION_ID:-}`, `- EXTENSION_LATEST_VERSION=${EXTENSION_LATEST_VERSION:-}`,
  `- EXTENSION_LATEST_URL=${EXTENSION_LATEST_URL:-}`, `- EXTENSION_LATEST_SHA256=${EXTENSION_LATEST_SHA256:-}` —
  the canonical compose has no `env_file` and its environment is otherwise `PORT` and `LOG_LEVEL` only (`:1100-1102`);
  `${VAR:-}` is safe in an env line (no `build.args`, `:1094-1099`).
- `templates/chrome-extension/compose.yaml.j2` — lines 17-22 (the CORS comment and five labels) removed; line 27
  (`CORS_ORIGINS=${CORS_ORIGINS:-chrome-extension://*}`) replaced by the same four `- VAR=${VAR:-}` lines, so both compose
  paths read the deploy's `.env` (the template already passes `${LOG_LEVEL:-INFO}` this way, line 26). A project's
  service spec must not repeat these names in its `env:`, which the template renders after them.
- `templates/chrome-extension/defaults.yaml` — `CORS_ORIGINS: "chrome-extension://*"` removed, nothing added (the
  template's env loop, `compose.yaml.j2:28-30`, merged at `template_renderer.py:127`, would render a default as a
  literal line beside the `${VAR:-}` ones).
- `Makefile` `dev` and `dev-server` (`:6007-6016`) — the uvicorn lines gain `$(if $(wildcard .env),--env-file .env,)`,
  so `EXTENSION_ID` and the local opt-in in `.env` reach the dev server (the emitted server loads no `.env`, and
  uvicorn's `--env-file` refuses a missing file).
- `.env.example` (`:6060-6068`) — names `EXTENSION_ID`, `EXTENSION_LATEST_VERSION`, `EXTENSION_LATEST_URL`,
  `EXTENSION_LATEST_SHA256`, each with a one-line comment, and `CORS_ALLOW_ANY_EXTENSION` commented out with "local
  development only, never in a deploy".

**Steps** (sequential):
1. `command grep -rn CORS_ORIGINS src/ templates/ tests/ scripts/` and record it in Evidence: at authoring, 7 hits —
   `src/fabrik/scaffold.py:2554`, `:2705`, `:2709` (the saas emitter's own `cors_origins()`),
   `templates/saas-skeleton/.env.example:19`, `scripts/gather_envs.py:141` (a name list, harmless) and the two chrome
   lines this phase removes; none in the emitted chrome-extension server. Write the Phase B graders and see each red. B5 replaces `test_compose_traefik_cors_uses_regex_not_glob` (`tests/test_scaffold_chrome_ext_wxt.py:102-114`),
   which pins the regex label this phase removes; its docstring's "Traefik synthesizes the preflight itself" holds only
   while the middleware is attached.
2. Emit the endpoint, the three-way CORS branch and its startup logs.
3. Remove the Traefik CORS labels and rewrite the comment above them; pass the four env lines on both compose paths;
   remove the two chrome `CORS_ORIGINS` lines (template, `defaults.yaml`); emit the `.env.example` rows; add
   `$(if $(wildcard .env),--env-file .env,)` to the `dev` and `dev-server` uvicorn lines (`:6010`, `:6015`).
4. Phase B graders green; the whole chrome-extension class green; `tests/orchestrator/test_template_defaults.py` green.
5. `/fabrik-review-scoped` on Phase B's surface; fix what it finds.

**Behaviour Contract (Phase B)**

B1-B4b run the emitted server in a fresh `.venv/bin/python` subprocess from `server/src`, with the row's env set, so
`main.py` is imported under that env (CORS is fixed at import) and the emitted logger's root-handler swap
(`src/fabrik/scaffold.py:960`) never meets pytest's capture; each opens `with TestClient(app)` so `lifespan` runs, and
B4 and B4b assert on the subprocess's stdout, where structlog writes.

| # | Given | When | Then |
|---|---|---|---|
| B1 | the emitted server with the three `EXTENSION_LATEST_*` (a) all unset, (b) all set to `""`, (c) only VERSION and URL set | `GET /extension/latest` (TestClient) | 404 in each case |
| B2 | the three `EXTENSION_LATEST_*` set | `GET /extension/latest` | 200 with exactly those three values |
| B3 | `EXTENSION_ID=` a valid 32-character a–p ID, (a) as is, (b) with a trailing `\r` | a preflight from `chrome-extension://<another id>`, then from the pinned ID | no `access-control-allow-origin` header for the other ID; the header for the pinned ID in both (a) and (b) |
| B4 | `EXTENSION_ID` (a) unset, (b) `""`, (c) `chrome-extension://<id>` (invalid); no `CORS_ALLOW_ANY_EXTENSION` | the app starts; a preflight from any extension origin | `cors_no_extension_id` logged (and `cors_extension_id_invalid` in (c)); no `access-control-allow-origin` header |
| B4b | `EXTENSION_ID` unset, `CORS_ALLOW_ANY_EXTENSION=1` | the app starts; a preflight from any extension origin | `cors_any_extension_origin` logged and `cors_no_extension_id` not logged; the header is present (the dev regex) |
| B5 | the emitted `compose.yaml` and `.env.example`; `defaults.yaml`; `compose.yaml.j2` | read | no label containing `-cors` in the emitted compose or the template; the emitted compose and the template each carry the four `${VAR:-}` env lines and no `CORS_ORIGINS`; the four env names and the commented opt-in in `.env.example`; no `CORS_ORIGINS` in `defaults.yaml` |
| B6 | the emitted `Makefile` | read the `dev` and `dev-server` recipes | both uvicorn lines carry `$(if $(wildcard .env),--env-file .env,)` |

## Phase C — Finish — ✅ EXECUTED 2026-10-15 (6b0047c27)

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
- `templates/chrome-extension/compose.yaml.j2`
- `tests/test_scaffold.py`
- `tests/test_scaffold_chrome_ext_wxt.py` (only `test_compose_traefik_cors_uses_regex_not_glob`, `:102-114`, replaced by
  B5; `test_wxt_config_declares_mv3_permissions_and_icons`, `:133-142`, whose exact permissions string gains `alarms`;
  and `test_wxt_scaffold_builds_and_manifest_has_permissions`, `:323-355`, whose exact permissions list gains `alarms`
  and which A3 extends)
- `docs/superpowers/specs/2026-10-14-chrome-extension-devmode-release-kit-design.md`, this plan, the review receipt,
  `CHANGELOG.md`, `docs/DECISIONS.md`

## Coverage Checklist

Derived from the `review_rubric.py` run below (FLOOR + MATCHED) plus the four recurrence classes.

| Row | Hunt | Verdict |
|---|---|---|
| FLOOR core/35-security-auth | CORS origins from env, never hardcoded; no secret in code; the public endpoint carries no secret | FIXED — origins come from `EXTENSION_ID` (Phase B CORS); without a valid ID the allow-list is empty, and the dev regex needs the local `CORS_ALLOW_ANY_EXTENSION=1` opt-in, so no deployed origin is hardcoded (approval panel); hunted: Phase B, spec item 5 |
| FLOOR core/25-data-postgres | no DB touch in this change (scaffold text only) | CLEAN — no database path in § File Scope; hunted: File Scope, Phase B |
| FLOOR core/30-ops | health, logs and limits of the emitted server unchanged; the startup logs are structured | CLEAN — `/health` and the compose memory and cpu limits are untouched (`_write_canonical_compose` keeps them); the CORS startup warnings and error are structured events; hunted: Phase B, `src/fabrik/scaffold.py:999-1012` |
| FLOOR 12-FACTOR | config via env only (EXTENSION_ID, EXTENSION_LATEST_*); no grouped config | FIXED — the four env names reach the container through `extra_env_lines` (review O-O1); no grouped config; hunted: Phase B compose, `.env.example` |
| MATCHED core/10-python | no deps-file edit; the emitter's Python stays string emission | CLEAN — no dependency file in § File Scope; hunted: File Scope, Global Constraints |
| MATCHED core/40-documentation | one CHANGELOG entry; the decision row; INDEX untouched (no new hub file) | FIXED — digest row added (review Z4); CHANGELOG and the decision row are Phase C step 2; hunted: Constraints Digest, Phase C |
| MATCHED core/45-testing-strategy | one grader per behaviour, each watched red | FIXED — every behaviour has a row, B1 parametrised, A3 extends the build test, B1-B4 name their mechanism (review O-O9, O-O11, O-O12); hunted: both Behaviour Contracts |
| RECURRENCE fail-open vs fail-closed | CORS without a valid EXTENSION_ID fails closed and warns; update checker ignores bad payloads | FIXED — CORS closes without a valid ID (approval panel); the endpoint 404s unless all three values are set and non-empty (review S2-S3); `defaults.yaml` adds no empty default that would force the open fallback on the template path (review O-O2); hunted: Phase B, spec items 4-5 |
| RECURRENCE cost/quota/limit accounting | check interval, timeout, request volume (spec § Lifecycle) | CLEAN — a 6-hour alarm and a 10-second timeout (Phase A checker; spec § Lifecycle sizes the load); hunted: Phase A, spec § Lifecycle |
| RECURRENCE boundary/sentinel/prefix collisions | version regex, https prefix, isNewer missing-integer, exact-origin match | FIXED — empty and partial env values (review O-O11), the RSA-2048 length (review S1-S2), the version regex and https prefix (A4); hunted: A1, A4, B1 |
| RECURRENCE behaviour-without-a-test | every spec § Validation item maps to an A/B row | FIXED — the built manifest's `key` (A3, review O-O12) and the compose env lines (B5) gained graders; hunted: both Behaviour Contracts, spec § Validation |

Rubric invocation (verbatim output; the File Scope is the changed-path set):

```text
$ python scripts/review_rubric.py --changed src/fabrik/scaffold.py templates/chrome-extension/defaults.yaml templates/chrome-extension/compose.yaml.j2 tests/test_scaffold.py tests/test_scaffold_chrome_ext_wxt.py docs/superpowers/specs/2026-10-14-chrome-extension-devmode-release-kit-design.md docs/development/plans/2026-10-14-plan-1-chrome-extension-devmode-release-kit.md CHANGELOG.md docs/DECISIONS.md
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- A dedicated admin host on its own domain — never the customer-facing app's domain — behind 2FA: set `shape.is_admin_dashboard: true` there. The Authelia registrar adds a per-domain `two_factor` rule on `fabrik apply`, so every path on that domain sits behind 2FA except the standing `/health` and `/metrics` bypasses (D-366, `saas/60-saas-ui.md` § Admin). API services with bearer auth: set `shape.has_bearer_api: true` — the registrar inserts an Authelia **bypass** rule *before* the `two_factor` catch-all so machine/bearer callers aren't hit with interactive 2FA. Don't add Traefik `authelia-forward` middlewares manually — the scaffolder + registrars emit them.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: the plain upstream PostgreSQL Alpine image, `plpgsql` only — `CLAIMS.yaml` row `fleet-postgres-main-no-pgvector`); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (probed 2026-09-01: the plain upstream PostgreSQL Alpine image at the fleet major recorded in `CLAIMS.yaml` row `pg-fleet-major` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- `docker compose run --rm <svc> alembic upgrade head` (against deployed environment) — `<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: src/fabrik/scaffold.py, tests/test_scaffold.py, tests/test_scaffold_chrome_ext_wxt.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

### core/40-documentation.md  (hit: CHANGELOG.md, docs/DECISIONS.md, docs/development/plans/2026-10-14-plan-1-chrome-extension-devmode-release-kit.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_scaffold.py, tests/test_scaffold_chrome_ext_wxt.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.

# promote-to-check_*: 85 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `fabrik-lib/fastapi-user-auth` `DELETE … RETURNING` `jti` `agents-fabrik.md § Supabase`
- `chrome-extension` `chrome.identity.launchWebAuthFlow` `https://<ext-id>.chromiumapp.org/` `chrome.storage.session`
- `desktop-app` `safeStorage` `desktop-app/72-desktop.md`
- `fabrik` `X-Internal-Token` `internal_auth.py` `hmac.compare_digest` `APIKeyHeader`
- `auth.uid()` `current_tenant_id()` `NULL` `EXCEPTION WHEN OTHERS THEN RETURN NULL` `SELECT auth.uid()` `NULL`
- `openssl rand -hex 32`
- `algorithms=["HS256"]` `alg` `alg: none`
- `redis-main`
- `expo-secure-store` `80-mobile.md`
- `localStorage` `sessionStorage`
- `chrome.storage.session` `TRUSTED_CONTEXTS` `chrome.runtime.sendMessage` `chrome.identity.launchWebAuthFlow` `code_verifier` `crypto.subtle` `storage.session`
- `x-middleware-subrequest` `middleware.ts` `proxy.ts` `middleware.ts`
- `CORSMiddleware` `allow_origins`
- `X-Frame-Options: DENY` `frame-ancestors`
- `APIKeyHeader` `require_api_key` `SERVICE_API_KEY` `PROXY_API_KEY` `python-api` `internal_auth.py` `metrics.py` `/metrics` `SERVICE_INTERNAL_SECRET_KEY`
- `os.getenv("KEY", "default")` `config/production.yml` `settings.production`
- `expo-secure-store`
- `shape.is_admin_dashboard: true` `two_factor` `fabrik apply` `/health` `/metrics` `saas/60-saas-ui.md` `shape.has_bearer_api: true` `two_factor`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
- `postgres-main` `fabrik-lib/rag` `plpgsql` `CLAIMS.yaml` `fleet-postgres-main-no-pgvector` `postgres-main`
```

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

- WXT keeps `manifest.key` — the executed read of the WXT 0.21.4 install is the spec's (`spec § Grounding`, "WXT
  accepts and keeps `manifest.key`"); those files sit outside this repo, so the plan does not re-quote them. The
  plan's own proof is executable: A3's build leg asserts the built `manifest.json` carries `key` equal to the `.pub`,
  run explicitly with `-m needs_network` (Phase A step 5), whose result Phase A pastes here.

### Phase A — executed 2026-10-15

Commits: `34b4c94d7` (the kit), `d6b67f7ea`, `0297ffafc`, `723674561` (the phase's `/fabrik-review-scoped`, three
independent seats a round: confirmed 14 → 7 → 0, the round-3 remainder verifying every round-2 fix by probe and
mutant replay). Graders seen red first: 14 failed before the emitter change, 15 before round 1's fixes, 6 before
round 2's, 5 before round 3's recorded items.

```text
$ PYTHONPATH=<worktree>/src .venv/bin/python -m pytest tests/test_scaffold.py -k Chrome tests/test_scaffold_chrome_ext_wxt.py -q
74 passed, 75 deselected in 26.15s
```

Execution notes (what the build settled, against the Interfaces text above):

- `release-ext`'s three checks live in the emitted `extension/scripts/release-check.mjs`, run by the recipe's first
  line (`src/fabrik/scaffold.py` `_CX_RELEASE_CHECK_MJS`), not inline shell: the effective `VITE_PUBLIC_API_URL` (the
  plan-review S1-P1 fix) is resolved as WXT's own `loadEnv` does — `wxt/dist/core/utils/env.mjs:10-31`, read in
  `/opt/job-agent/extension/node_modules`: the environment, else the last of `.env`, `.env.local`, `.env.<mode>`,
  `.env.<mode>.local`, `.env.<browser>`, `.env.<browser>.local`, `.env.<mode>.<browser>`,
  `.env.<mode>.<browser>.local`, parsed with `node:util` `parseEnv`. Review round 1 also had it refuse `STORE_BUILD=1`,
  a malformed `.pub`, a dirty tree, a non-Chrome `package.json` version, a colon-form line and a host-less URL.
- The key is resolved by a shared `extension/scripts/manifest-key.mjs` (with `manifest-key.d.mts`), relative to its own
  file rather than the cwd; `wxt.config.ts` sets `key: pinnedKey()`; a `.pub` that is not a base64 SPKI key whose
  export round-trips fails the build, the gate and keygen.
- The checker's pure rules live in an import-free `src/lib/update-version.ts` (`isNewer`, `parseLatest`,
  `secureBase` — the stored backend must be https or local http), so A4 is graded by executing them under node.
- The popup relies on `@wxt-dev/i18n`'s auto-import of `i18n` (`@wxt-dev/i18n/dist/module.mjs:13-16` registers
  `imports: [{from: "#i18n", name: "i18n"}]`) instead of an explicit `#i18n` import, which the emitted tsconfig's own
  `paths` would not resolve.
- keygen rebuilds a lost `.pub` from the `.pem`; the emitted `.gitignore` also ignores `.env.*.local`.
- **UNEXECUTED — missing infra:** step 5's network build test (`-m needs_network -k builds`) and an emitted-project
  `pnpm compile` / `pnpm lint` were run three times and each `pnpm install` timed out: WSL cannot resolve
  `registry.npmjs.org` (`curl: (28) Resolving timed out after 15000 milliseconds`). Phase C re-runs all three before
  the Finish review.

### Phase B — executed 2026-10-15

Step 1's census, re-run at execution (`command grep -rn CORS_ORIGINS src/ templates/ tests/ scripts/`): the same 7 source
hits as at authoring (`src/fabrik/scaffold.py:2554`, `:2705`, `:2709`, `templates/saas-skeleton/.env.example:19`,
`scripts/gather_envs.py:141`, and the two chrome lines this phase removed), none in the emitted chrome-extension server;
after the removal 5 non-test hits remain, none of them in the chrome-extension paths.

Commits: `4c2b1ce2a` (the backend), `9eb64fb75`, `21eb04b4f` and `4f29e9e6a` (the phase's `/fabrik-review-scoped`,
three independent seats: confirmed 12 → 0). Graders seen red first: 12 failed before the emitter change; round 1's strengthened graders
proven by red-on-revert in a throwaway worktree (8 mutants — template filter, no-store, URL check, URL strip, error
level, credentials, log-at-import, read-at-import — each turned its grader red; baseline 18 passed before and after).

```text
$ PYTHONPATH=<worktree>/src .venv/bin/python -m pytest tests/test_scaffold.py tests/test_scaffold_chrome_ext_wxt.py tests/orchestrator/test_template_defaults.py tests/test_scaffold_spec_generation.py tests/test_spec_generator.py -q
264 passed, 1 skipped, 1 deselected in 54.13s
```

Execution notes:

- Appetite overrun: 178 of 60 minutes, almost all of it a ~2-hour box network outage (DNS `EAI_AGAIN`) that killed two of the three review seats mid-run and stalled the session; the work itself was the planned scope, so nothing was re-planned.
- The scaffold's own spec generator copies the canonical compose `environment:` into the spec's `env:`, so the four
  `EXTENSION_*` values arrive in `env:` on the template path; `templates/chrome-extension/compose.yaml.j2`'s env loop
  skips those four names (review round 1), and B5b renders the template from the generated spec to prove each appears
  once. The plan's "a project's service spec must not repeat these names" (Phase B Interfaces) is therefore enforced by
  the template, not left to the spec author.
- `GET /extension/latest` also sends `Cache-Control: no-store` (review round 1).
- Recorded, not changed: `access-control-allow-credentials: true` on responses with no allow-origin (FastAPI's
  behaviour); server-side validation of the release values (the extension's checker validates, A4); the opt-in reachable
  through a spec's `env:` on the template path (the operator's own spec).

### Phase C — the Finish review (whole-plan `/fabrik-review`)

Receipt: `docs/development/reviews/2026-10-15-plan-1-chrome-extension-devmode-release-kit-review.md`. Pass 1 found what
the two phase reviews missed, and four of its fixes change what the Interfaces above say; where they differ, this
block holds:

- Phase A Interfaces (`update-check.ts`): a 404 from `/extension/latest` now CLEARS the stored notice (a withdrawn
  release must not keep its banner); any other non-2xx or a body failing validation keeps it. The rule is the pure
  `nextNotice(status, body, current)` in `update-version.ts`, executed by A4. The popup re-validates the stored
  notice with `parseLatest` on read.
- Phase A Interfaces (the version rule): the shipped `VERSION_RE` refuses a leading zero and caps each integer at
  65535 (Chrome's rule), stricter than the `^\d{1,5}(\.\d{1,5}){0,3}$` written above.
- `keygen.mjs` refuses to mint when `extension-key.pub` is committed but missing locally (restore it from git), and
  refuses a `.pub` that does not match the `.pem` beside it; the "not a public key" message suggests deleting the
  `.pub` only when a `.pem` exists to rebuild it from.
- The release gate refuses a `VITE_PUBLIC_API_URL` containing `$` (WXT expands env-file variables with
  dotenv-expand, so the built URL is not the written text), and its next steps say to commit `.env.production`.
- The emitted server builds its CORS kwargs as typed `allow_origins` / `allow_origin_regex` (mypy rejected the
  mixed-value `**dict`; B7 runs mypy on the emitted server).
- Phase B Interfaces ("must not repeat these names"): superseded by the template filter, which now also skips
  `PYTHONUNBUFFERED` and `LOG_LEVEL`, the two `defaults.yaml` values the template already sets (B5b).

## Self-audit

- Every behaviour in `spec § Validation` maps to a row: spec 1 → A0/A1, 2-3 → A1/A2, 4-5 → A3, 6 → B1/B2, 7 → B3/B4/B4b, 8 → A7,
  9 → A6, 10 → A7, 11 → B5, 12 → A4/A5, 13 → B6.
- Diff estimate ≈335 lines in 1 code file and 2 templates (tests excluded): inside `Profile: small` (≤ ~400, ≤ 5).
- Every touchpoint is a `path:line` in today's emitter; every new file is named by path.

## Residual unknowns

- **R1 — resolved at plan-review round zero.** `_write_canonical_compose` writes literal Traefik label values
  (invariant 4, `src/fabrik/scaffold.py:1029-1031`), so the exact-origin label is dropped and the Traefik CORS labels
  are removed; FastAPI alone answers CORS.
- **R2 — WXT's zip name.** `release-ext` takes the newest `.output/*-chrome.zip` rather than assuming the exact name
  (`70-chrome-ext.md:65` states the `<name>-<version>-chrome.zip` shape).

## Pass Ledger

The `/fabrik-plan-review` joint loop over this plan and its spec; the per-candidate detail is in the receipt `docs/development/reviews/2026-10-14-plan-1-chrome-extension-devmode-release-kit-plan-review.md`.

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (O: plan rule/grammar sections) + sonnet×2 (S1: plan other sections; S2: the spec) · all axes | found: 18, new: 18, confirmed: 15, fixed: 15, unexecuted: 0, edits: 15 | method: citation + re-derivation — full pass (15 confirmed, 2 refuted, 1 superseded by a fix) | d3d9e8b1… → ba8ee040… (plan); spec 4d9c3c4f… → 77cafae5… |
| Pass 2 | opus×1 + sonnet×2 (the round-1 slice owners) · delta over the round-1 fix + one hop | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0, edits: 3 | method: re-derivation — 15 ledger rows re-verified (14 DEFECT_ABSENT, O-O12 DEFECT_PRESENT), 3 confirmed | ba8ee040… → 82330ea1… (plan); spec 77cafae5… → 91e7d686… |
| Pass 3 | opus×1 (O) + sonnet×1 (S2) — the slice owners whose ledger rows or files the round-2 fix touched; shape: agent-tool (the Workflow launch was cancelled by an account switch, then refused at the approval prompt) | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 2 | method: re-derivation — 4 ledger rows re-verified (all DEFECT_ABSENT), 2 confirmed in the fix hunks | 82330ea1… → ce19d1e6… (plan); spec 91e7d686… → 06cb0341… |
| Pass 4 | opus×1 (O) + sonnet×1 (S2) (the slice owners); shape: agent-tool | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 3 | method: re-derivation — 5 ledger rows re-verified (all DEFECT_ABSENT); 1 confirmed in the fix hunks, 1 confirmed from a seat's one-hop note when the orchestrator executed it | ce19d1e6… → d6cebea7… (plan); spec 06cb0341… → c4ef8876… |
| Pass 5 | opus×1 (O) + sonnet×2 (S1, S2) (the slice owners); shape: agent-tool | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 3 | method: re-derivation — 8 ledger rows re-verified (7 DEFECT_ABSENT, S2-S3 residue); stall breaker tripped (rounds 3-5 confirmed 2, 2, 2) — foundation named and removed, see below | d6cebea7… → 4d517845… (plan); spec c4ef8876… → c2f93162… |
| Pass 6 | opus×1 (O) + sonnet×1 (S2) (the round-1 slice owners; S1 re-stated at its last verified 4/4) · delta over the round-5 fix; standing clean since Pass 1: every other class; shape: agent-tool | found: 1, new: 1, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — 7 ledger rows re-verified (all DEFECT_ABSENT); O-O19 RECORDED — measured | 4d517845… → 4d517845… ✓ (plan); spec c2f93162… → c2f93162… ✓ → quiet |
| Pass 7 | opus×1 (O) + sonnet×2 (S1, S2) — the panel's delta round over its 18 accepted changes; S1's seat stalled (no result, carried to Pass 8); shape: agent-tool | found: 6, new: 6, confirmed: 6, fixed: 6, unexecuted: 0, edits: 6 | method: re-derivation + executed probes (a CORS-middleware probe of every B3/B4 branch) — see Pass 7 candidates | c453df3a… → d8153216… (plan); spec 16f476c7… → 3e557f9d… |
| Pass 8 | opus×1 (O) + sonnet×2 (S1, S2) (the slice owners; S1's full ledger re-run) | found: 4, new: 4, confirmed: 2, fixed: 2, unexecuted: 0, edits: 4 | method: re-derivation + a scratch Makefile proving the `--env-file` conditional; O-Q1 (B4b's Then), O-Q2 (no step emitted the Makefile change) confirmed; two estimate notes RECORDED — measured (wording; changes no behaviour) | d8153216… → cc7bfdc3… (plan); spec 3e557f9d… → 28e15e69… |
| Pass 9 | opus×1 (O) + sonnet×1 (S2) (the round-1 slice owners; S1 re-stated at its last verified 5/5) · delta over the round-8 fix; standing clean since Pass 1: every other class; shape: agent-tool | found: 0, new: 0, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — 6 ledger rows re-verified (all DEFECT_ABSENT); the orchestrator executed the one claim no seat could read (uvicorn `--env-file` is `click.Path(exists=True)`, `uvicorn/main.py:193`) | cc7bfdc3… → cc7bfdc3… ✓ (plan); spec 28e15e69… → 28e15e69… ✓ → **CONVERGED** |
