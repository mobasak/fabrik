# Plan review — chrome-extension developer-mode release kit (W-e2af3303)

**Status:** IN-PROGRESS
**Command:** /fabrik-plan-review · joint loop over a `Size: small` spec (spec § The delta D10)
**Artifacts:** `docs/development/plans/2026-10-14-plan-1-chrome-extension-devmode-release-kit.md` and
`docs/superpowers/specs/2026-10-14-chrome-extension-devmode-release-kit-design.md`, both DRAFT at 5f6d1983b.

## Round zero — the orchestrator's pre-pin probe

Executed before the first pin; each fix is in the round-1 pin.

| # | Finding | Evidence | Fix |
|---|---|---|---|
| Z1 | The design's exact-origin Traefik label `accesscontrolalloworiginlist=chrome-extension://${EXTENSION_ID}` relies on compose interpolation in a Traefik label, which `_write_canonical_compose` rules out | `src/fabrik/scaffold.py:1029-1031` (invariant 4: "a ``${VAR:-default}`` label once reached Traefik verbatim") | The Traefik CORS labels are removed from the emitter and the template; FastAPI's exact-origin `CORSMiddleware` is the single CORS authority. Spec § Chosen approach item 5, § What exists today, § Rejected alternatives, § Validation 11; plan Phase B, B5, File Scope, R1 |
| Z2 | `templates/chrome-extension/compose.yaml.j2` carries its own Traefik CORS labels and a stale `CORS_ORIGINS` line the plan did not name | the template's lines 17-22 and 27; rendered at `src/fabrik/template_renderer.py:156` | Added to the plan's Phase B interface and File Scope |
| Z3 | `tests/test_scaffold_chrome_ext_wxt.py:102-114` pins the regex label this change removes | the test's line 111 asserts `accesscontrolalloworiginlistregex=^chrome-extension://.*$` | Phase B step 1 replaces it with the B5 grader; File Scope names it |
| Z4 | The Constraints Digest lacked a row for the MATCHED `core/40-documentation` pack | the plan's rubric run (MATCHED core/40) | Digest and Context Ledger rows added (`core/40-documentation.md:134`) |

## Ask ↔ spec

Built from the spec's own § Intake Inventory (13 items: 11 IN, 2 OUT-OF-SCOPE).

| I# | The ask (anchored) | Where the spec answers it | Where the plan builds it | Disposition |
|---|---|---|---|---|
| I1 | pinned manifest `key`, private key out of the repo (01M3WQXZ3Y HOW 1) | § Chosen approach — the key | Phase A (keygen, `wxt.config.ts`, `.gitignore`); A1-A3, A7 | IN |
| I2 | tighten CORS to the exact ID (01M3WQXZ3Y HOW 1) | § Chosen approach item 5 | Phase B CORS; B3, B4, B5 | IN |
| I3 | public `GET /extension/latest` from env (01M3WQXZ3Y HOW 2) | § Chosen approach — the endpoint | Phase B endpoint; B1, B2 | IN |
| I4 | update checker on startup and an alarm, popup notice (01M3WQXZ3Y HOW 3) | § Chosen approach — the update checker | Phase A checker, background, popup; A4, A5 | IN |
| I5 | `INSTALL.md` with the four steps and both caveats (01M3WQXZ3Y HOW 4) | § Chosen approach — the INSTALL guide | Phase A; A6 | IN |
| I6 | `wxt zip` is enough (01M3WQXZ3Y WHERE) | § Chosen approach — release target | Phase A Makefile; A7 | IN |
| I7 | keypair at scaffold time or first release (W-e2af3303) | § Chosen approach, § Rejected alternatives | Phase A keygen on first need | IN |
| I8 | job-agent and whatsapp-agent (01M3WQXZ3Y WHEN) | out of scope; reply to fleet | — | OUT-OF-SCOPE |
| I9 | zip hosted with its SHA-256 (`89`:129) | § Chosen approach — release target | Phase A Makefile; A7; Phase B endpoint `sha256` | IN |
| I10 | bump only after the zip is reachable (`89`:125) | § Personas, § Lifecycle | Phase B reads env per request | IN |
| I11 | backend still serves the previous version (`89`:127) | § Constraints — additive route | Phase B additive route | IN |
| I12 | no agent publishes (`89`:136) | § Personas | Global Constraints; A7 | IN |
| I13 | enterprise `.crx` variant (`89`:133) | out of scope; key kept | — | OUT-OF-SCOPE |

## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (O: plan rule/grammar sections) + sonnet×2 (S1: plan other sections; S2: the spec) · all axes | found: 18, new: 18, confirmed: 15, fixed: 15, unexecuted: 0, edits: 15 | method: citation + re-derivation — full pass (15 confirmed, 2 refuted, 1 superseded by a fix) | d3d9e8b1… → ba8ee040… (plan); spec 4d9c3c4f… → 77cafae5… |
| Pass 2 | opus×1 + sonnet×2 (the round-1 slice owners) · delta over the round-1 fix + one hop | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0, edits: 3 | method: re-derivation — 15 ledger rows re-verified (14 DEFECT_ABSENT, O-O12 DEFECT_PRESENT), 3 confirmed | ba8ee040… → 82330ea1… (plan); spec 77cafae5… → 91e7d686… |

### Pass 1 candidates

| Id | Finding | Disposition |
|---|---|---|
| O-O1 | The four env names never reach the container: the canonical compose has no `env_file` and its environment is `PORT`/`LOG_LEVEL` only (`src/fabrik/scaffold.py:1100-1102`) | CONFIRMED, FIXED — `extra_env_lines` with four `${VAR:-}` lines; B5 asserts them |
| O-O2 | `defaults.yaml` `EXTENSION_ID: ""` renders `- EXTENSION_ID=` through the template's env loop (`compose.yaml.j2:28-30`, `template_renderer.py:127`) | CONFIRMED, FIXED — no default added; the template path takes the names from the spec's `env:` |
| O-O3 | Step 1's grep omits `scripts/`, and "nothing reads `CORS_ORIGINS`" was unscoped (7 hits) | CONFIRMED, FIXED — grep widened, the 7 hits named, the claim scoped to the emitted chrome-extension server |
| O-O4 | The unset-`EXTENSION_ID` regex fallback contradicts core/35 "never hardcode origins" with no recorded exception | CONFIRMED, FIXED — spec § Decisions taken records the exception; the approval row names it |
| O-O5 | The Gate 2 digest quote dropped the source's bold markers | CONFIRMED, FIXED — quoted verbatim |
| O-O6 | `scaffold.py:673` claimed blank | REFUTED — line 673 is `'*.pem\n'` |
| O-O7, S1-S1 | A7's "no curl" is unsatisfiable over the whole Makefile (`docker-smoke` curls at `:6045`) | CONFIRMED, FIXED — A7 extracts the `release-ext` recipe |
| O-O8 | Each make line is its own shell: the checksum step would run at the root and record an `extension/.output/` path | CONFIRMED, FIXED — one recipe line, `cd .output`, bare-name checksum |
| O-O9 | B3/B4 need import-time env and lifespan; the emitted logger swaps root handlers (`:960`) so caplog never sees the warning | CONFIRMED, FIXED — B1-B4 run the server in a subprocess, `with TestClient(app)`, B4 on stdout |
| O-O10 | The comment above the compose call (`:5975-5978`) would still say CORS goes via Traefik | CONFIRMED, FIXED — rewritten in Phase B |
| O-O11 | B1 covered only "unset", not empty; B5 did not check the emitted compose for `CORS_ORIGINS` | CONFIRMED, FIXED — B1 parametrised (unset, empty, partial); B5 widened |
| O-O12 | The WXT `key` retention claim had no executed output in the plan | CONFIRMED, FIXED — A3 extends the existing build test to assert the built manifest's `key` |
| S1-S2 | A1's 392 chars holds only for RSA-2048, which the keygen interface did not state | CONFIRMED, FIXED — `modulusLength: 2048` named |
| S1-S3 | `release-ext` missing from `.PHONY` | CONFIRMED, FIXED — added; A7 asserts it |
| S2-S1 | The spec's Validation never names the test pinning the regex label | REFUTED — plan Phase B step 1 replaces it with B5 |
| S2-S2 | `wxt.config.ts` reading `VITE_PUBLIC_API_URL` has no grounded mechanism | RECORDED — measured (superseded: `host_permissions` dropped, so the config reads no env) |
| S2-S3 | Behaviour with only some `EXTENSION_LATEST_*` set was undefined | CONFIRMED, FIXED — 404 unless all three are set and non-empty |

Found during the orchestrator's re-execution: `test_wxt_scaffold_builds_and_manifest_has_permissions`
(`tests/test_scaffold_chrome_ext_wxt.py:323-355`) pins the exact permissions list, so adding `alarms` breaks it — FIXED:
the File Scope names it and A3 extends it.

### Pass 2 candidates

| Id | Finding | Disposition |
|---|---|---|
| O-O12 | The WXT evidence bullet still carried no executed output | CONFIRMED, FIXED — the grep commands and their output are pasted in § Evidence |
| O-O13 | `test_wxt_config_declares_mv3_permissions_and_icons` (`tests/test_scaffold_chrome_ext_wxt.py:133-142`) pins the exact permissions string that `alarms` changes | CONFIRMED, FIXED — File Scope and Phase A step 2 name it |
| O-O14 | `${EXTENSION_ID:-}` delivers "not set" as `""`; the CORS branch and B4 knew only set/unset | CONFIRMED, FIXED — set-and-non-empty vs unset-or-empty in plan and spec; B4 covers both |
