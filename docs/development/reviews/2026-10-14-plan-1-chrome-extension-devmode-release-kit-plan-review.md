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
