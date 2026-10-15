# Plan review — chrome-extension developer-mode release kit (W-e2af3303)

**Status:** CONVERGED
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
| Pass 3 | opus×1 (O) + sonnet×1 (S2) — the slice owners whose ledger rows or files the round-2 fix touched; shape: agent-tool (the Workflow launch was cancelled by an account switch, then refused at the approval prompt) | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 2 | method: re-derivation — 4 ledger rows re-verified (all DEFECT_ABSENT), 2 confirmed in the fix hunks | 82330ea1… → ce19d1e6… (plan); spec 91e7d686… → 06cb0341… |
| Pass 4 | opus×1 (O) + sonnet×1 (S2) (the slice owners); shape: agent-tool | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 3 | method: re-derivation — 5 ledger rows re-verified (all DEFECT_ABSENT); 1 confirmed in the fix hunks, 1 confirmed from a seat's one-hop note when the orchestrator executed it | ce19d1e6… → d6cebea7… (plan); spec 06cb0341… → c4ef8876… |
| Pass 5 | opus×1 (O) + sonnet×2 (S1, S2) (the slice owners); shape: agent-tool | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 3 | method: re-derivation — 8 ledger rows re-verified (7 DEFECT_ABSENT, S2-S3 residue); stall breaker tripped (rounds 3-5 confirmed 2, 2, 2) — foundation named and removed, see below | d6cebea7… → 4d517845… (plan); spec c4ef8876… → c2f93162… |
| Pass 6 | opus×1 (O) + sonnet×1 (S2) (the round-1 slice owners; S1 re-stated at its last verified 4/4) · delta over the round-5 fix; standing clean since Pass 1: every other class; shape: agent-tool | found: 1, new: 1, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — 7 ledger rows re-verified (all DEFECT_ABSENT); O-O19 RECORDED — measured | 4d517845… → 4d517845… ✓ (plan); spec c2f93162… → c2f93162… ✓ → quiet |
| Pass 7 | opus×1 (O) + sonnet×2 (S1, S2) — the panel's delta round over its 18 accepted changes; S1's seat stalled (no result, carried to Pass 8); shape: agent-tool | found: 6, new: 6, confirmed: 6, fixed: 6, unexecuted: 0, edits: 6 | method: re-derivation + executed probes (a CORS-middleware probe of every B3/B4 branch) — see Pass 7 candidates | c453df3a… → d8153216… (plan); spec 16f476c7… → 3e557f9d… |
| Pass 8 | opus×1 (O) + sonnet×2 (S1, S2) (the slice owners; S1's full ledger re-run) | found: 4, new: 4, confirmed: 2, fixed: 2, unexecuted: 0, edits: 4 | method: re-derivation + a scratch Makefile proving the `--env-file` conditional; O-Q1 (B4b's Then), O-Q2 (no step emitted the Makefile change) confirmed; two estimate notes RECORDED — measured (wording; changes no behaviour) | d8153216… → cc7bfdc3… (plan); spec 3e557f9d… → 28e15e69… |
| Pass 9 | opus×1 (O) + sonnet×1 (S2) (the round-1 slice owners; S1 re-stated at its last verified 5/5) · delta over the round-8 fix; standing clean since Pass 1: every other class; shape: agent-tool | found: 0, new: 0, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — 6 ledger rows re-verified (all DEFECT_ABSENT); the orchestrator executed the one claim no seat could read (uvicorn `--env-file` is `click.Path(exists=True)`, `uvicorn/main.py:193`) | cc7bfdc3… → cc7bfdc3… ✓ (plan); spec 28e15e69… → 28e15e69… ✓ → **CONVERGED** |

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

### Pass 3 candidates

| Id | Finding | Disposition |
|---|---|---|
| O-O15 | Phase A step 2 cited the build test's permissions assert at `:353`; it is at `tests/test_scaffold_chrome_ext_wxt.py:350` | CONFIRMED, FIXED |
| O-O16 | `grep -c '"key"'` cannot see `delete manifest[key]`, and the `key?: string` hit was not tied to the manifest type | CONFIRMED, FIXED — § Evidence greps the whole word and shows the deletion is `stripKeys`' loop over four lists (read whole) that never name `key`; the field sits in `ManifestBase` |

Also corrected from seat O's one-hop notes: the Coverage Checklist rows and spec § Validation 7 / § Decisions taken now say
"unset or empty" / "set and non-empty".

### Pass 4 candidates

| Id | Finding | Disposition |
|---|---|---|
| O-O17 | § Evidence said `stripKeys`' loop is "the only deletion" in `manifest.mjs`, measured by a filtered whole-word grep | CONFIRMED, FIXED — executed `grep -nE 'delete \|deleteProperty'`: three deletes (`manifest_version`, `host_permissions`, the `stripKeys` loop), none names `key`; prose and output corrected |
| O-N1 | A3's build leg and Phase A step 5 assumed the build test runs wherever node and pnpm exist, but it carries `needs_network`, deselected by default (`pyproject.toml:106`) | CONFIRMED, FIXED — step 5 runs it explicitly with `-m needs_network` and pastes the result; A3 says so |

Also from the one-hop notes: spec § Rejected alternatives now reads "unset or empty".

### Pass 5 candidates

| Id | Finding | Disposition |
|---|---|---|
| O-O18 | § Evidence's `grep -nw key … \| wc -l` → `3` hides whether a strip list names `"key"` | CONFIRMED, FIXED — then superseded by the foundation fix below |
| S2-S3 (residue) | spec § Validation 6 said "unless all three values are set", without "and non-empty" | CONFIRMED, FIXED |

**Stall breaker (rounds 3-5 confirmed 2 → 2 → 2).** Every confirmed defect in rounds 3-5 but one sat in a single plan
bullet: § Evidence's hand-quoted greps of the WXT install under `/opt/job-agent`, a path outside every seat's readable
roots. No seat could execute those checks, so each round re-graded the block's shape and each rewrite seeded the next
wording defect (the orchestrator's own re-execution in round 5 also caught an `awk` interval check that was silently
vacuous under this box's awk). The foundation is the evidence's location, not the design. Fix: the bullet now points to
the spec's executed § Grounding read and to A3's executable build leg (`-m needs_network`), which asserts the built
manifest's `key`; nothing outside the seats' roots is re-quoted. A removal, not new content.

### Pass 6 candidates (closing)

| Id | Finding | Disposition |
|---|---|---|
| O-O19 | Phase A step 5 lets a skipped build test stand as the pasted result of A3's build leg | RECORDED — measured (the host that executes the plan has node v24.18.0 and pnpm 11.24.0, so the build leg runs; the explicit selector `-m needs_network -k builds` collects exactly 1 test, executed: `1/30 tests collected (29 deselected)`) |
| O-note | Coverage Checklist row "RECURRENCE fail-open" says the endpoint 404s "unless all three values are set", without "and non-empty" | RECORDED — measured (wording; changes no behaviour — an adjudication note; the interface, B1(b) and spec § Validation 6 carry "and non-empty") |

## Design-approval panel (D-613)

Both seats read the pinned spec (md5 c2f931620e37176f870408253c92e766) and plan (md5 4d5178456fb0524468901299861dd420) cold.

- `VERDICT: sound-with-changes — docs/development/plans/2026-10-14-plan-1-chrome-extension-devmode-release-kit.md + docs/superpowers/specs/2026-10-14-chrome-extension-devmode-release-kit-design.md` (opus)
- `VERDICT: sound-with-changes — docs/development/plans/2026-10-14-plan-1-chrome-extension-devmode-release-kit.md + docs/superpowers/specs/2026-10-14-chrome-extension-devmode-release-kit-design.md` (fable)

Every concern was executed against the base copy and ACCEPTED; none was rejected or left open.

| Seat · # | Concern | Evidence executed | Disposition |
|---|---|---|---|
| opus 1, fable 2 | `release-ext` minted the key and built from an uncommitted tree, so the ID could drift and the `.pem` be lost | `89-extension-launch-checklist.md:120-121` ("from the pushed SHA"); the recipe had no tracked-key or clean-tree check | ACCEPTED — `release-ext` refuses unless the `.pub` is tracked and the tree clean; keygen is a separate step 0; A7 runs the refusal |
| opus 2 | the checker would nag store and policy installs | spec item 2 changed only `key` | ACCEPTED — the checker returns when the manifest has `update_url`; A4 |
| opus 3, fable 5 | with no backend URL the checker silently self-404s; the Options page's stored URL was ignored | `src/fabrik/scaffold.py:5532` (`?? ''`), `:5386-5395` (`settings.apiUrl`) | ACCEPTED — base = stored `apiUrl` else `API_BASE_URL`, early return when empty; `release-ext` requires an https `VITE_PUBLIC_API_URL`; A4, A7 |
| opus 4 | the release loop never asked for `EXTENSION_ID`; a malformed value broke CORS silently | spec step 4 named three values; no validation | ACCEPTED — `release-ext` prints four values; the server strips and validates `^[a-p]{32}$`, logging `cors_extension_id_invalid`; B3(b), B4(c) |
| fable 1 | the unset-ID default was fail-OPEN (credentialed any-extension regex) | `src/fabrik/scaffold.py:5871-5872`; compose `${EXTENSION_ID:-}` | ACCEPTED — closed by default (empty allow-list); the regex only behind the local `CORS_ALLOW_ANY_EXTENSION=1`; the core/35 exception is gone; B4, B4b |
| opus 5 | spec said the alarm is re-created on every SW start, which resets its period | `chrome.alarms.create` replaces a same-named alarm; spec vs plan disagreed | ACCEPTED — create only when `alarms.get` finds none, in spec and plan; A5 |
| opus 6, fable 3 | INSTALL.md not copied beside the zip; the onboarding link had no target; no backup instruction | the recipe copied nothing; no hosted URL at scaffold time; Lifecycle cited a guide line that did not exist | ACCEPTED — `cp ../INSTALL.md .`; the onboarding link dropped; keygen prints the backup warning; A1, A7 |
| opus 7, fable 7 | the template path did not pass the four names | `compose.yaml.j2:24-30`, `template_renderer.py:127` | ACCEPTED — the template replaces its `CORS_ORIGINS` line with the four `${VAR:-}` lines; B5 |
| opus 8 | the OAuth `chromiumapp.org` redirect changes with the dev ID | `70-chrome-ext.md` § Auth | ACCEPTED — recorded in the spec's dissent fold and § Decisions taken (run keygen before registering a redirect) |
| opus 9 | `is_public` described as making the backend reachable | `src/fabrik/spec_loader.py:269-274` (gates Gatus) | ACCEPTED — reworded in § Shape |
| opus 10 | size line, surface pin, A1/A2 without a node skip | spec header; plan surface; `tests/test_scaffold_chrome_ext_wxt.py:323-326` | ACCEPTED — all three corrected |
| fable 4 | ledger upd-5 and prac-19 dispositions argued the opposite of the spec | ledger rows upd-5, prac-19 | ACCEPTED — dispositions rewritten; `check_research_ledger.py`: 0 refused of 43 |
| fable 6 | A1/A2 run `node` with no skip guard | as opus 10 | ACCEPTED — A1/A2 skip without `node` |
| fable 8 | "unzip over the same folder" leaves stale chunks | — | ACCEPTED — "replace the folder's contents" |

### Pass 7 candidates (the panel's delta round)

| Id | Finding | Disposition |
|---|---|---|
| O-P1 | the local `CORS_ALLOW_ANY_EXTENSION` opt-in (and `EXTENSION_ID`) could never reach the dev server: the emitted server loads no `.env` and `make dev`/`dev-server` pass no `--env-file` | CONFIRMED (executed: no `load_dotenv` in the chrome emitter; `src/fabrik/scaffold.py:6007-6016` uvicorn lines carry no `--env-file`), FIXED — both pass `$(if $(wildcard .env),--env-file .env,)`; B6 |
| O-P2 | spec Validation 1 (keygen emitted) mapped only to A1, which now skips without `node` | CONFIRMED, FIXED — A0 reads the emitted file and script, never skips |
| O-P3 | the grader-mechanism note named only B4's stdout assertion, not B4b's | CONFIRMED, FIXED |
| O-P4 | the diff estimate differed between the header and the Self-audit | CONFIRMED, FIXED — ≈335 in both |
| O-note | the closed case logged `cors_any_extension_origin` while admitting no origin | CONFIRMED (in the round's own hunk), FIXED — the closed case logs `cors_no_extension_id`; B4 |
| S2-P1 | the Personas update step read "unzip it into the same folder's contents" | CONFIRMED, FIXED — "replace the folder's contents with the new zip's" |
| S2-P2 | the dissent fold cited a README line no step emits | CONFIRMED, FIXED — the keygen header and `release-ext`'s refusal carry it |

### Pass 8 candidates

| Id | Finding | Disposition |
|---|---|---|
| O-Q1 | B4b's Then said "the warning is logged" while two warnings now exist | CONFIRMED, FIXED — names `cors_any_extension_origin` and excludes `cors_no_extension_id` |
| O-Q2 | no Phase B step emitted the Makefile `--env-file` change that B6 grades | CONFIRMED, FIXED — step 3 adds it (`src/fabrik/scaffold.py:6010`, `:6015`) |
| O-note | spec § Validation had no item for the dev `--env-file` behaviour; the core/30-ops row named one warning | FIXED — spec Validation 13 (mapped to B6); the row now names the structured startup logs |
| S1-Q1, S2-note | the plan header's ≈335 sits beside its own ≈327 itemised sum; the spec's size lines use a different basis | RECORDED — measured (wording; an approximate estimate, changes no behaviour) |
| O-note (pre-existing) | the emitted `dev` recipe's `trap 'kill 0' SIGINT` fails under `/bin/sh` (dash wants `INT`) | RECORDED — out of scope (pre-existing emitter defect, not this change); a backlog item at execution |

## Per-phase verdicts

### Phase A — the extension and the release (keygen, manifest key, checker, INSTALL, `release-ext`): CONVERGED (Pass 9 confirmed 0; slice S1 verified 5/5)

### Phase B — the backend (endpoint, closed-by-default CORS, compose env passthrough, dev `--env-file`): CONVERGED (Pass 9 confirmed 0; slice O verified 4/4)

### Phase C — Finish (whole-plan `/fabrik-review`, CHANGELOG, decision row, gate, merge request): CONVERGED (Pass 9 confirmed 0; no finding touched it)

### The spec (joint loop, `Size: small`): CONVERGED (Pass 9 confirmed 0; slice S2 verified 4/4); approval row D-893

## Gate

`python scripts/final_gate.py --check --json` over the staged approval commit (docs-only, so the static tier is skipped by design); the head of its output, verbatim:

```json
{
  "status": "success",
  "tier": 2,
  "passed": 58,
  "failed": 0,
  "skipped": 1,
  "skipped_checks": [
    "static tier"
  ],
```
