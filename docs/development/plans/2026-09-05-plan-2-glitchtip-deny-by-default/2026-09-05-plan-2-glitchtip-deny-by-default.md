# GlitchTip scrubbing in the scaffold is a deny-by-default SHAPE, not a flag list (build plan)

Status: CONVERGED (2026-09-05 — /fabrik-plan-review, 13 author-blind rounds (passes 12–13 = the 2026-09-05 re-pin re-opens): pool finders 5 per round (52 of 55 returned; 3 deaths re-dispatched or recorded) + the orchestrator's own execution each round — 36 findings fixed across passes 1–10, round 11 a full fresh sweep with 0; every `path:line` in the set resolved against the real files (24 of 24), the printed extraction block and census loop run verbatim; emit gates 0 ✗ 0 ⚠ at every commit; closing HEAD ff667c97)
**Owner:** infra authors; T02 (the emitter + the back-fill notices at merge) is fleet's beat (scaffolding) — named per ticket; execution on the operator's go-word
Shape: spine + 4 tickets (the READ set of the scope is 445,243 bytes against the 262,144 per-ticket budget, and `src/fabrik/scaffold.py` alone is 280,969 — see § Self-audit § Sizing)
Source: mail `01M1QSRJ6M0MB3RGAWZD5F4ZT2` (site-provisioner, CRITICAL) + its correction `01M1QWM094Z6S0ZYGPKTB4NPY0`; proposal `/opt/site-provisioner/docs/reference/upstream-proposals/2026-09-05-scaffold-glitchtip-remaining-channels.md` (221 lines, addendum "five was an undercount", corrected at their `060c096`)
Ledger: D-126 (minted in this change)

## What we already agreed

- **The problem (proposal § The claim, grounded; hub emitter `src/fabrik/scaffold.py:1712-1733`):** the scaffold's `sentry_sdk.init` carries the f273064c two-flag fix (`include_local_variables=False`, `max_request_body_size="never"`, `:1729-1730`) plus the FastAPI/Starlette integrations (`:1731-1734`) and NO hook, scrubber, breadcrumb or source-context setting; the sender reproduced ~11 further channels against sentry-sdk 2.68.1 — `before_send` is SKIPPED for transaction events (sentry-sdk 2.68.1 `client.py:917-922`, the sender's citation), outbound request URLs land in breadcrumbs with no PII gate and persist onto later events (a live Bing API key left the process inside an unrelated error), `EventScrubber` never touches `logentry` (sentry-sdk 2.68.1 `scrubber.py:170-176`, the sender's citation), `request.url`/`query_string`, db-span SQL, `span.data["http.query"]`, headers delegated to a 7-name list, source context, the transaction name, and containers kept WHOLESALE after passing a top-level allowlist (frame `vars` rode inside `exception`/`threads`).
- **The direction is the SHAPE, never a longer list (sender's SYSTEMIC + INDUCTIVE, accepted):** the two-flag fix is itself a denylist; two of the sender's own class fixes were denylist-shaped one level in. Every count so far was an undercount; "the count is not what the hub should act on — the shape is." So: deny-by-default allowlists per event key / request key / header / span key / context key / frame key / mechanism key, plus LEAF-SHAPE enforcement (an allowlisted key holding an unexpected container is nulled), registered as BOTH `before_send` and `before_send_transaction`, `include_source_context=False`, `max_breadcrumbs=0`, `server_name` = the service name.
- **Vendor, don't build (CLAUDE.md § Pointers; `/opt/fabrik-lib/README.md:57` row 57 `observability/`):** the reference implementation is `/opt/site-provisioner/api/glitchtip_init.py` (33,955 bytes) guarded by 59 tests in `/opt/site-provisioner/tests/test_glitchtip_init.py`; fabrik-lib's `observability/` module carries no scrubber (`grep before_send|scrub` → 0 hits in `/opt/fabrik-lib/observability/*.py`). The module is copied into the hub's scaffold template tree and emitted by copy, the way `templates/scaffold/python/pause_state.py` already is (`src/fabrik/scaffold.py:1744`).
- **The fleet default for the stdlib-logging channel — DECIDED here, D-126 (reversible: a re-emit):** the proposal's open question ("how many scaffolded services log through stdlib `logging` rather than structlog") is MEASURED: 11 repos on the box carry a `glitchtip_init.py`; stdlib `logging` appears in ≥1 tracked file in **10 of 11**, structlog in 11 of 11; with the STRICTER denominator the review demanded — a stdlib-only file that CALLS `logger.error/exception/critical` — it is **6 of 11** (brand-identiy-creator 6 files, seo 21, transdoc 7, web-ecommerce-factory 5, site-provisioner 1, tryton-crm 1; § Evidence, Phase A). Same verdict either way: a majority loses ERROR signal. Closing the channel entirely (site-provisioner's own D-007) would silence `logger.error` events fleet-wide. Verdict: log EVENTS are KEPT (`LoggingIntegration(event_level=logging.ERROR, level=None)`), BREADCRUMBS are OFF (`level=None` + `max_breadcrumbs=0`), and `logentry` is reduced to the raw template (`_ALLOWED_LOGENTRY_KEYS = {"message"}` — `params`/`formatted` dropped, the interpolation channel closed). The vendored module already implements exactly this shape for `logentry`; only the `LoggingIntegration` kwargs differ from site-provisioner's (theirs: `event_level=None`). Duplicates are not a cost of this default: a `logger.exception(...)` inside an `except` and the framework integration capture the SAME exception object, and sentry-sdk's `DedupeIntegration` (on by default) drops the second; a plain `logger.error("…")` with no `exc_info` is a distinct event — the ERROR signal the default exists to keep (review pass 8 asked; this is the answer).
- **Which emitters are in scope (measured by `ast`, § Evidence Phase A):** the Python init is written by `_scaffold_fastapi_backend` (`src/fabrik/scaffold.py:1567-1868`), reached by `python-api`, `python-api-gpu` (via `_scaffold_python_api:1929`) and `saas-skeleton` (`_scaffold_saas_backend:3276`) — 3 of the 12 scaffoldable types. `node-api` (`_scaffold_node_api`, `src/fabrik/scaffold.py:3613`) and `chrome-extension` (`_scaffold_chrome_extension:4462/4480/4733`, an isolated BrowserClient) have their own inits: the Node/browser `beforeSend` equivalent is a RESIDUAL follow-up, not this plan (the channels were reproduced against the Python SDK only). The other 7 types emit no Sentry init.
- **The guard asserts the CAPTURED EVENT, never the kwarg (rule 55 § "Verify on the CAPTURED EVENT"; the original mail's instruction, which is what surfaced all of this):** `tests/test_scaffold_glitchtip_security.py` today asserts two flag strings in the emitted text (`:40-41`, 2 tests) — which is why the gap was invisible to the hub's own enforcement.
- **Already-deployed services are NOT re-emitted by this plan.** The back-fill is a notice to the 11 repos naming the vendoring step (T02's merge notice); the rule-pack sentence "a project scaffolded BEFORE that date still has the old init" (`.windsurf/rules/core/55-observability.md:~273`) is rewritten to point at the module.
- **Rejected:** (a) extending the flag list (the sender's whole argument); (b) importing fabrik-lib's `observability/` across repos (vendor law); (c) a hub-side `before_send` name-denylist (rule 55: "the thing that already failed"); (d) closing log events entirely as the FLEET default (10 of 11 would lose ERROR signal — site-provisioner's per-repo choice stands for them).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | operator: "before starting executing this plan, we must handl all your waiting mails" — this plan IS the handling of `01M1QSRJ6M0MB3RGAWZD5F4ZT2` | IN — SIZED as plan work per CLAUDE.md § SIZING | this set |
| I2 | mail WHAT: "~11 FURTHER channels … every NEW scaffold emitted fleet-wide still ships them" | IN | T01, T02 |
| I3 | mail SYSTEMIC: "the prescribed two-flag fix is itself a denylist … emit that shape, not a longer flag list" | IN — the direction | § What we already agreed; T01 |
| I4 | mail HOW: "decide the fleet default for the logging channel … emit `include_source_context=False`, register `before_send_transaction` … extend the guard test to assert whatever is chosen" | IN — decided (D-126), T01, T03 | header Ledger; T03 |
| I5 | proposal § Direction 4: "Correct the 'only free-text' sentence in the 55-observability rule pack" | IN | T04 |
| I5b | proposal: "every NEW scaffold emitted fleet-wide still ships them" — and the deployed ones do not re-emit | IN — the notice at T02's merge names the vendoring step | T02 Docs line |
| I6 | proposal § What I cannot see: "How many scaffolded services log through stdlib logging rather than structlog" | IN — measured 10 of 11 | § Evidence Phase A; D-126 |
| I7 | correction `01M1QWM094Z6S0ZYGPKTB4NPY0`: "`_meta` IS an event field … `aggregates` and `attrs` are NOT" | IN — the vendored module's allowlists are taken from their corrected `060c096` | T01 |
| I8 | mail WHO: "infra owns the emitter, the guard test and the rule pack" — hub beats say scaffolding is FLEET's | IN — Owner per ticket: T02 fleet, T01/T03/T04 infra; fleet is mailed the plan pointer at the go-word | header; § Execution Discipline |
| I9 | Node/browser parity (`node-api`, `chrome-extension` inits) | OUT — named residual (the channels were reproduced against the Python SDK) | § Residual unknowns |

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | Vendor the scrubber into the scaffold template tree | — | ⚡ | ✅ | `b38bc674` |
| T03 | The guard asserts the captured event through a swapped transport | T01 | ⚡ | ✅ | `5ab9550d` |
| T04 | Rule 55 § Error Reporting states the shape | T01 | ⚡ | ✅ | `0af2ece9` |
| T02 | The FastAPI emitter copies the module (integration, last; the back-fill notices at merge) | T03, T04 | — | ✅ | `ad038829` |

**EXECUTED 2026-09-05** by fleet in one session (the operator released the whole set; this spine's own
Execution Discipline permits one session to run it). Merge order followed: T01 → T03 → T04 → T02. Every
ticket's Gate lines green, a native in-line adversarial pass at each boundary, each committed with explicit
pathspecs and pushed. Deviations and findings, recorded rather than smoothed over:

- **T01's written pin was one commit stale** (`7b83573`; the file was at `4f5c158`). Followed T01's own
  "VERIFY the revision first" instruction and vendored the current committed revision, recording that sha.
- **T04's "seven header names" did not survive verification.** sentry-sdk 2.68.1's scrubber matches 37
  names (`DEFAULT_DENYLIST` 33 + `DEFAULT_PII_DENYLIST` 4). The load-bearing half held —
  `X-Signing-Secret` matches none of them — so the synced pack shipped the measured 37, not the seven.
- **The per-platform census was re-derived by SCAFFOLDING each of the 12 types**, not by reading the
  dispatch: Python reaches `python-api`/`python-api-gpu`/`saas-skeleton`, Node only `node-api`, seven types
  emit nothing, `chrome-extension` has its own BrowserClient.
- **T03's watched fail is this plan's most valuable artifact:**
  `secrets reached the wire through: ['apikey', 'header', 'otp', 'query']` against the init the scaffold
  was shipping — site-provisioner's report reproduced by our own guard rather than believed.
- **T02's back-fill notices: 11 sent, of 43 `/opt` git repos** (census re-measured at merge; hub and
  `templates/` excluded, per the ticket's command). No D-035 advisory on any.
- **Residue reported, not fixed:** `requires_fabrik_env` was left unused by T03's replacement and is used
  again by T02's tests; the Node test still calls `create_project` without it, which T03 forbade touching.
- **One collision, mine:** the T03 commit swept infra's uncommitted CHANGELOG entry (`git commit -- <path>`
  reads the working tree). Nothing lost, no amend; the later commits added a heading-count check that
  caught the same window before T02.

## Merge Order

1. T01
2. T03
3. T04
4. T02

(T03 and T04 are parallel after T01; T02 is the single `Integration: true` ticket and merges last — its byte-equality tests consume T01's template and T03's guard runs in its gate.)

## Interfaces

- `templates/scaffold/python/glitchtip_init.py` → copied by `_scaffold_fastapi_backend` to `src/<package>/glitchtip_init.py` with the `{pkg}` docstring placeholder substituted; public surface unchanged: `init_glitchtip() -> bool` (the app calls it once at module load, `src/fabrik/scaffold.py:1793-1800`).
- The module's `_scrub_event(event, hint)` is registered as `before_send` AND `before_send_transaction`; `LoggingIntegration(event_level=logging.ERROR, level=None)`; `max_breadcrumbs=0`; `include_source_context=False`; `server_name=os.environ.get("SERVICE_NAME", "<name>")`.
- The guard (`tests/test_scaffold_glitchtip_security.py`) scaffolds a `python-api` into `tmp_path`, imports the emitted module, swaps `sentry_sdk`'s transport for a capturing one, raises inside a FastAPI route with secrets in locals / body / headers / URL query / a `logger.error("%s", secret)` / an outbound request breadcrumb, and asserts on the captured error event AND transaction event.

## Global Constraints

- Deny-by-default + leaf-shape is the shape; no ticket adds a denylist (a finding that wants one is a BLOCKED spec contradiction, not a fix).
- The vendored module is COPIED (fabrik-lib law); its origin and revision are recorded in its docstring (`site-provisioner api/glitchtip_init.py @ 7b83573` — re-pinned from `060c096` → `8e2f436` (D-127) → `7b83573` (D-130) on 2026-09-05 as items 13–14 landed graded and then corrected: `_reduce_origin`, `_redact_userinfo_in_text` now redacting the REACHABLE field with damaged separators accepted — the mechanism is a URL-PARSE failure, their D-016).
- `sentry-sdk[fastapi]>=2.18.0` stays the pin the scaffold emits (`src/fabrik/scaffold.py:2125`). The hub `.venv` has NEITHER `sentry_sdk` NOR `structlog` (measured); T01 — first in Merge Order — AUTHORISES adding both to `pyproject.toml` `[project.optional-dependencies] dev` (the deps-file HARD STOP is lifted by this ticket, for these two lines only) and the guard RECORDS the installed version in its output.
- Synced surfaces: `.windsurf/rules/core/55-observability.md` distributes to 45 repos on commit; `templates/scaffold/**` and `src/fabrik/scaffold.py` are hub-only.
- Every ticket: watched-fail-first graders; `/fabrik-review` at each phase boundary (execute-plan's own contract); explicit pathspecs; no `git add -A`.

## Behavior Contract

- **Given** the hub `.venv` after `pip install -e .[dev]`, **When** `python -c "import sentry_sdk, structlog"` runs, **Then** both import and the sentry-sdk version is printed (the first step of this ticket; every later gate depends on it).
- **Given** the template file, **When** parsed with `ast`, **Then** it defines `init_glitchtip` and `_scrub_event`, the string `before_send_transaction=_scrub_event` appears once (`/opt/site-provisioner/api/glitchtip_init.py:606` is the reference line — pass 2 corrected 604), and the tokens `{pkg}` and `{name}` each appear exactly once.
- **Given** the template, **When** its `LoggingIntegration(` call is read, **Then** it carries `event_level=logging.ERROR` and `level=None` — the fleet default, not site-provisioner's `event_level=None` (D-126).
- **Given** the template's `integrations=[...]`, **When** read, **Then** both integrations carry `transaction_style="endpoint"` (the scaffold's naming, kept).
- **Given** `_ALLOWED_LOGENTRY_KEYS`, **When** read, **Then** it is exactly `{"message"}` (the interpolation channel closed; `params`/`formatted` never pass).
- **Given** an event whose allowlisted key holds an unexpected container, **When** `_scrub_event` runs, **Then** that key is nulled (leaf-shape) — imported and executed in the test, not read.
- **Given** a `python-api` scaffold into `tmp_path`, **When** `src/<pkg>/glitchtip_init.py` is read, **Then** it equals the template with `{pkg}`/`{name}` substituted and contains neither token (other braces are the module's own).
- **Given** `python-api-gpu` and `saas-skeleton` scaffolds, **When** the same file is read, **Then** the same holds (3 of 3 reaching types).
- **Given** the template file is absent, **When** the scaffold runs, **Then** it raises (no silent skip) — proven by monkeypatching `TEMPLATE_DIR`.
- **Given** the existing scaffold suite (`tests/test_scaffold.py`), **When** run, **Then** it is green — nothing else in `_scaffold_fastapi_backend` changed.
- **Given** T03's tests in the same file (merged earlier), **When** this ticket merges, **Then** they are byte-identical — this ticket only APPENDS.
- **Given** the merge, **When** the back-fill notices are sent, **Then** one mail id per repo carrying a `glitchtip_init.py` is recorded in this ticket's review artifact, the count re-measured with its denominator, and `mail.py` prints no D-035 advisory.
- **Given** the emitted module with a capturing transport, **When** a route raises with the six secrets in play, **Then** the serialized ERROR event contains none of them (substring search over the whole event).
- **Given** `traces_sample_rate=1.0`, **When** the request completes, **Then** the captured TRANSACTION event contains none of them either (`before_send_transaction` is registered; `client.py:917-922` skips `before_send` for transactions).
- **Given** a `logger.error("otp=%s", secret)`, **When** captured, **Then** `logentry == {"message": "otp=%s"}` — the template, never the interpolation; and no breadcrumb carries it.
- **Given** the current inline literal extracted to `/tmp/old_glitchtip_init.py`, **When** `GLITCHTIP_GUARD_MODULE=/tmp/old_glitchtip_init.py python -m pytest … -k captured_event` runs, **Then** it is RED — the failing assertion names recorded in the ticket's review artifact as the watched fail.
- **Given** the Node emitter, **When** the existing two Node assertions run, **Then** they still pass (unchanged surface).
- **Given** the hub `.venv` (T01 installed the dev extras), **When** the guard imports the template module, **Then** `init_glitchtip()` returns True and `sentry_sdk.VERSION` is printed — a False (the ImportError path) fails the test.
- **Given** T01's template tests in the same file, **When** T03 merges, **Then** they are byte-identical (the diff touches only the two replaced tests and the additions).
- **Given** the rewritten section, **When** read, **Then** the words "deny-by-default", "leaf", "before_send_transaction", "max_breadcrumbs=0" and "include_source_context=False" each appear, and "Two init flags are MANDATORY" is reframed as the floor.
- **Given** the Node paragraph (`.windsurf/rules/core/55-observability.md:246-254`), **When** diffed, **Then** it is byte-identical (the asymmetry correction of 2026-08-28 is not touched).
- **Given** the header paragraph (`:256-260`), **When** read, **Then** it no longer says the header channel is closed by the SDK alone; it names the seven-name limit and the allowlist.
- **Given** the back-fill sentence, **When** read, **Then** it names the template path and the vendoring step, and no longer says "as of 2026-08-28 … add them".
- **Given** the 7 types with no Sentry init, **When** the section is read from one of their repos, **Then** one sentence says the section does not apply to them.
- **Given** the per-platform blocks, **When** read, **Then** the Python list is exactly `python-api`, `python-api-gpu`, `saas-skeleton` and the Node list exactly `node-api` — `file-worker` and `file-api` no longer appear (review pass 9 caught the old lists past the ticket's first range).

## Context Ledger

| Source | Read | Bound into |
|---|---|---|
| `python scripts/select_rules.py` — 26 ACTIVE | core/10-python, core/45-testing-strategy, core/55-observability, core/40-documentation, core/35-security-auth, core/62-using-subagents (+ the 20 others named by the run) | T01–T04 gates; § Global Constraints |
| `agents-fabrik.md` § Scaffold Types (`:384`), GlitchTip row (`:196`) | 12 scaffoldable types; GlitchTip at errors.vps1 | § What we already agreed (emitters in scope) |
| `/opt/fabrik-lib/README.md:57` `observability/` | logging + Sentry init, NO scrubber | vendor from site-provisioner instead |
| `docs/DECISIONS.md` (`decisions.py glitchtip`: hub 0 rows; site-provisioner D-007/D-009/D-010) | their per-repo choices, not fleet rulings | D-126 minted here |
| 12-Factor | config from env (`SERVICE_NAME`, sample rates), no code branch on host | § Interfaces |

## File Scope (owned paths)

- templates/scaffold/python/glitchtip_init.py
- src/fabrik/scaffold.py
- pyproject.toml
- tests/test_scaffold_glitchtip_security.py
- .windsurf/rules/core/55-observability.md
- docs/development/plans/2026-09-05-plan-2-glitchtip-deny-by-default/

(CHANGELOG.md, INDEX.md, docs/FEATURES.md and docs/DECISIONS.md are governance surfaces — orchestrator-applied, never in Touches or File Scope.)

## Evidence

### Phase A — grounding (the emitters, the census, the sizing)

- `src/fabrik/scaffold.py:1678` (the inline `glitchtip_init.py` literal), `:1712` (`sentry_sdk.init(`), `:1729-1730` (the two flags), `:1744` (`pause_src = TEMPLATE_DIR / "python" / "pause_state.py"` — the copy pattern), `:244` (`TEMPLATE_DIR = FABRIK_ROOT / "templates" / "scaffold"`), `:2125` (the sentry-sdk pin); `tests/test_scaffold_glitchtip_security.py:31-53`; `.windsurf/rules/core/55-observability.md:232-334`.

```
$ python3 - (ast: enclosing functions + callers)
sentry init emitters by function: {'_scaffold_fastapi_backend': [1675, 1678, 1712], '_scaffold_node_api': [3613], '_scaffold_chrome_extension': [4462, 4480, 4733]}
callers: {'_scaffold_python_api': ['_scaffold_fastapi_backend'], '_scaffold_saas_backend': ['_scaffold_fastapi_backend'], '_scaffold_python_api_gpu': ['_scaffold_python_api']}
$ python3 - (census of /opt repos with a glitchtip_init.py)
repos with a glitchtip_init.py: 11
repos where stdlib logging appears in ≥1 file: 10 of 11 | structlog in ≥1 file: 11 of 11
$ python3 - (stricter: a stdlib-only file calling error/exception/critical)
repos: 11 | repos with ≥1 STDLIB-ONLY file calling error/exception/critical: 6 → [('brand-identiy-creator', 6), ('seo', 21), ('site-provisioner', 1), ('transdoc', 7), ('tryton-crm', 1), ('web-ecommerce-factory', 5)]
$ .venv/bin/python -c "import sentry_sdk"
ModuleNotFoundError: No module named 'sentry_sdk'   (structlog likewise — T01 authorises the dev extras as its first step)
$ find <scope> -type f -exec cat {} + | wc -c
445243
$ wc -c src/fabrik/scaffold.py
280969
```

### Phase B — the reference module and its guard

- `/opt/site-provisioner/api/glitchtip_init.py:33-138` + `:304-307` (the allowlists, at 7b83573), `:168` (`_keep`), `:350` (`_redact_userinfo_in_text`), `:382` (`_reduce_logentry`), `:483` (`_scrub_event`), `:634-727` (`init_glitchtip` / `_init_sdk`: `before_send=_scrub_event`, `before_send_transaction=_scrub_event`, `include_source_context=False`, `LoggingIntegration(event_level=None, level=None)`); `/opt/site-provisioner/tests/test_glitchtip_init.py` (59 tests).

```
$ grep -c "def test_" /opt/site-provisioner/tests/test_glitchtip_init.py
75
$ grep -rn "before_send\|scrub" /opt/fabrik-lib/observability/*.py | wc -l
0
```

## Self-audit

- Grounding passes: every claim above is a `path:line` I read this session or a fenced output I ran; the channel list is the sender's, reproduced by them against sentry-sdk 2.68.1 — this plan does not re-count it (the shape is what is acted on). Review pass 3 measured `httpx` 0.28.1 and `fastapi` 0.141.1 present in the hub `.venv` (T03's breadcrumb probe needs no extra) and the reference's last revision `060c096` at plan time — `8e2f436` at the Pass 12 re-pin (D-127).
- Completeness (a) — a consumer of the plan's output exists in File Scope: the guard test consumes the emitted module; `_scaffold_fastapi_backend` consumes the template file; the rule pack is read by every project.
- Completeness (b) — every ticket's Touches path is in File Scope (T01: template + the test + pyproject.toml; T02: scaffold.py + the test; T03: the test; T04: rule 55); governance surfaces are orchestrator-applied and listed as such.
- Sizing: per-ticket READ sets measured in-repo (T01 59,803; T03 62,638; T04 57,494 — Touches + Context Files, `wc -c`, with the not-yet-created template counted at 0) PLUS the out-of-repo reads the gate counts as 0 and the tickets name with their bytes (module 33,955; its tests 69,210; the proposal 15,111); T02's Touches is `src/fabrik/scaffold.py` alone at 280,969 > 262,144 — `Integration: true`, last in Merge Order, with the reason stated in the ticket (a one-function edit inside a 281 KB file).
- Fire rate of the new structure: the guard runs on every hub gate; the emitted module runs in every new python-api/saas-skeleton service with a DSN set.

## Residual unknowns

- **Resolved:** the logging-channel default (D-126); which types emit the init (3 Python, 1 Node, 1 browser); whether fabrik-lib holds a scrubber (no).
- **Open — Node/browser parity:** `node-api`'s `Sentry.init` (`src/fabrik/scaffold.py:3613`) and `chrome-extension`'s BrowserClient have no `beforeSend` shape; owner fleet; probe: reproduce the URL-in-breadcrumb and logentry channels against `@sentry/node`, then a sibling plan. Not in the back-fill notices (every recipient is a Python init — T02); it lives here, for the sibling plan.
- **Open — the 11 deployed services:** they back-fill by vendoring the module themselves; the back-fill notices T02 sends at its merge names the step; nothing here re-emits them. Owner: each repo, on fleet's notice.

## Execution Discipline

- Owners: T01/T03/T04 infra; T02 fleet (scaffolding beat), including the back-fill notices at its merge. The dispatching session mails fleet the plan pointer at the go-word; a single session may execute all five if the operator says so.
- Per ticket: the ticket's Gate lines green, `/fabrik-review` over the ticket's diff to a quiet round, commit with explicit pathspecs + trailers (`Agent-Phase`), push; the orchestrator fills the Commit cell and applies CHANGELOG/INDEX/DECISIONS.
- Pool by default for review finders; native for the guard's design (a security surface).

## Coverage Checklist

Armed 2026-09-05 by running the rubric over this plan's `## File Scope (owned paths)` (the five
glob-matching entries; the plan dir itself matches no pack). Pasted output, verbatim:

```
$ python scripts/review_rubric.py --changed templates/scaffold/python/glitchtip_init.py src/fabrik/scaffold.py tests/test_scaffold_glitchtip_security.py .windsurf/rules/core/55-observability.md pyproject.toml
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)

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
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
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
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.**
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
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }`
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a
- VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and
- plan; never let a service-named plan be mistaken for the protection.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to
- a bare `exec "$@"`.* An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > sees a file that looks exactly like a migration step, and ships a deploy where migrations never run —
- > the rule producing the very defect it exists to prevent. Do not re-add either without a `path:line` in
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

### core/10-python.md  (hit: src/fabrik/scaffold.py, templates/scaffold/python/glitchtip_init.py, tests/test_scaffold_glitchtip_security.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: .windsurf/rules/core/55-observability.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (cheap-pool author → verify → converge):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. The hub's epic-to-ticket workflow (`/opt/fabrik/docs/orchestrator/epic-to-ticket-workflow/06-ticket-breakdown-fabrik.md`) injects these rows per ticket.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero
- from AI bots — agents never go looking. It follows (inference, not measurement) that a file only
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed
- daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_scaffold_glitchtip_security.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has
- a `pyproject.toml`/`uv.lock`**. ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into
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
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

### core/55-observability.md  (hit: templates/scaffold/python/glitchtip_init.py)
- ⚠️ **The shipper is Promtail today and Promtail reached END OF LIFE (2026-03-02)** — no
- **The label set is the PIPELINE's, not yours** — live: `container_name`, `filename`, `host`, `job`, `service_name`, `stream`. An app cannot add labels by logging a field; a JSON field is queried with `| json`, never as a label.
- > *"A twelve-factor app never concerns itself with routing or storage of its output stream. It should not attempt to write to or manage logfiles."*
**Mandate.** The app writes structured events, unbuffered, to `stdout` and **nothing else**. The app MUST NEVER write, rotate, append to, truncate, compress, age out, or otherwise manage a logfile, and MUST NEVER decide where logs are stored, how long they are kept, or how they are routed. Routing, rotation, retention, and storage are exclusively the **execution environment's** concern.
**BANNED in app code:**
- The scaffolded logger (structlog / pino — see § Pre-Scaffolded Logging) writes to stdout. Do not add a second handler, sink, or transport alongside the stdout one.
- ❌ **BANNED — in-app file logging:**
- > **⚠️ THE SERVER'S OWN LOGGERS ARE NOT YOURS — and they leak plain text by default.**
**Chrome extension frontend:** Use `chrome.storage.local` buffer pattern per the Chrome Extension Telemetry section below. Do not use pino directly in service workers.
- Every `python-api` and `node-api` scaffold emits a pre-configured `/metrics` endpoint. DO NOT create custom metrics modules. **A VENDORED module (fabrik-lib copies) never constructs its own `Counter`/`Histogram` either:** the scaffold serves `/metrics` from a PRIVATE `CollectorRegistry` (`scaffold.py::metrics_app`), so a module-made metric on the global default registry is invisible on 8 of the 11 `/metrics` surfaces measured 2026-09-02 and the module cannot know which registry its host scrapes. A module exposes an injectable callback (`on_<event>: Callable | None`) and a structured log-once; the HOST wires the callback to the registry it owns in one line. Precedent: fabrik-lib `async-http-client` (01M1GVYN, 01M1GY91).
- Name metrics with `snake_case` and a **base-unit** suffix (`_seconds`, `_bytes`); `_total` is the COUNTER suffix and composes with units (`process_cpu_seconds_total`). ⚠️ `prometheus_client` appends `_total` to a Counter itself — declare `Counter("requests", …)`, never `Counter("requests_total", …)`, and never `_count` (an OpenMetrics reserved suffix).
- ⚠️ **Know which failure YOUR stack gives you — they are not the same.** Under an OTel SDK, a
- Every `sentry_sdk.init` / `Sentry.init` in the fleet MUST set both:
| `max_request_body_size="never"` | **n/a — see below** | the request BODY, attached irrespective of `send_default_pii` (that flag gates COOKIES). Every auth, payments-webhook and token-exchange route is exposed the moment it logs an error while handling its request. **PYTHON ONLY** |
- ⚠️ **The two SDKs are NOT symmetric, and the Node column originally said otherwise — that was my
- already closed by `sendDefaultPii: false`, which makes the SDK report body **size only, never
- `httpIntegration({ maxIncomingRequestBodySize: 'none' })` — note `'none'`, not `'never'`.
**Never port an option name across SDKs by symmetry; check that SDK's own docs.**
**Verify on the CAPTURED EVENT, never the init kwarg.** Swap the SDK transport in a test, make a
- ⚠️ The scaffold emits both flags as of 2026-08-28. **A project scaffolded BEFORE that date still
- This is intentional: services without DSN configured never pay for SDK runtime cost
- ⚠️ **Outside that set nothing captures it.** A deliberate 401/403/429 you WANT audited reaches GlitchTip never — widen `failed_request_status_codes` in the init rather than sprinkling `capture_exception` through handlers.
- For `chrome-extension`: use `@sentry/browser` in the popup/options/side-panel (trusted extension pages). **In content scripts, never call the global `Sentry.init`** — a content script shares the host page's `window`, so global-state integrations hijack host-page errors. Build an isolated `BrowserClient` + `Scope` (drop `GlobalHandlers` / `Breadcrumbs`) and wrap with `makeBrowserOfflineTransport` (IndexedDB buffer/flush). Service workers use the `chrome.storage.local` buffer pattern (see Chrome Extension Telemetry below).
- **Caught-and-handled** exceptions: log with stack traces via `exc_info=True` in Python (dedicated JSON attribute, never raw multi-line text). **Unhandled** exceptions (FastAPI 500s, uncaught throws): do NOT log tracebacks — GlitchTip auto-captures them. Log a short event name + `correlation_id` only. See § Error Reporting above.
- In FastAPI: use `contextvars` + ASGI middleware to bind the ID to `structlog` context. Never use `threading.local()` in async code.
- ⚠️ **Why this fleet stops at a correlation ID, and what to name the field.** Probed 2026-09-01 across
- datasources (loki, prometheus). ⚠️ Not "no spans at all": Sentry-SDK services already emit
- So do NOT instrument distributed tracing here: spans with nowhere to go are cost without a consumer,
- Never rely on downstream log processors (Promtail, Logstash) for redaction — unredacted data may persist in transport buffers.
- **Never** use high-cardinality values as Loki stream labels. `request_id`, `user_id`, `session_id`, `client_ip` must remain inside the JSON payload only.
- ⚠️ **The label set is the PIPELINE's — an app cannot create one by logging a field.** See § Loki
- `/health` is Authelia-bypassed on all services. The bypass is **resource-based, not domain-bound** — `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file`). Never protect these paths.
- Never use UUID or timestamp-suffixed container names in Gatus configs or inter-service URLs — they drift per redeploy.
- MV3 service workers are ephemeral (terminated after ~30s idle). Do not hold logs in memory waiting for a batch window.
- Do not propose OTel instrumentation for a fleet service without new evidence. Measured against
- GlitchTip DSN comes from `GLITCHTIP_DSN` env var injected by the orchestrator from the GlitchTip registrar — do NOT hardcode the DSN in the repo.

# promote-to-check_*: 96 injected mandate(s) look deterministically greppable
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
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
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an
```

Every row below was adjudicated by execution against the set's tickets (the eleven rounds of the
Pass Ledger). Verdict vocabulary: CLEAN (swept, nothing raised) · FIXED (raised, closed in the set)
· REFUTED (raised, shown wrong against the primary source).

| Row | Verdict | Evidence |
|---|---|---|
| FLOOR core/35-security-auth | FIXED | the plan IS the security surface: deny-by-default per-key allowlists + leaf-shape on both `before_send` and `before_send_transaction`, `include_source_context=False`, `max_breadcrumbs=0` (T01 § Steps; D-126); no secret, credential or PII channel left to a denylist |
| FLOOR core/25-data-postgres | CLEAN | no DB surface in the set — File Scope is scaffold template + emitter + test + rule 55 + pyproject dev extras |
| FLOOR core/30-ops | CLEAN | no compose/port/memory-limit surface; the emitted module changes what an already-deployed service SENDS, not how it runs (T04 blast-radius row) |
| FLOOR 12-FACTOR | FIXED | config via env only — `GLITCHTIP_TRACES_SAMPLE_RATE` read by the module, set in T03's guard through `monkeypatch.setenv`, never a literal in code |
| MATCHED core/10-python (scaffold.py, template, test) | FIXED | `import logging` missing from the vendored module's LoggingIntegration call (T01); `{pkg}`/`{name}` substitution pinned to `str.replace` on tokens that occur exactly once — `.format()` would corrupt the module's own braces (T01, T02) |
| MATCHED core/40-documentation (rule 55) | FIXED | T04 rewrites the WHOLE § Error Reporting range `:232-334` (not the first paragraph), corrects the header sentence, names the emitting types (python-api, python-api-gpu, saas-skeleton; node-api residual), and keeps the Node paragraph byte-identical — verified by `diff` in its gate |
| MATCHED core/45-testing-strategy (guard test) | FIXED | the guard asserts the CAPTURED event through a swapped transport (`monkeypatch.setattr(sentry_sdk.get_client().transport, "capture_envelope", events.append)`), `init_glitchtip() is True`, replaces the kwarg-asserting test BY NAME; its watched fail runs against the CURRENT inline literal (T03) |
| MATCHED core/55-observability (template) | FIXED | logging channel decided (D-126: events at ERROR, breadcrumbs off, logentry reduced to the template via `_ALLOWED_LOGENTRY_KEYS = {"message"}`); `_meta` reduced via `_reduce_metadata`; `transaction_style="endpoint"` kept (T01) |
| standing: fail-open/fail-closed | FIXED | the vendored scrubber fails CLOSED — an allowlisted key holding an unexpected container is nulled; the guard proves the captured event, so a silent no-init is a red test not a green kwarg (T03) |
| standing: cost/quota accounting | CLEAN | no metered call in the set; the pool finders' cost is recorded on the flywheel (`record_agent_run` per unit, 11 rounds) |
| standing: boundary/sentinel/prefix | FIXED | read-budget boundary: `src/fabrik/scaffold.py` alone is 280,969 B against the 262,144 per-ticket budget, so T02 is the single `Integration: true` ticket and LAST in Merge Order (§ Sizing) |
| standing: behavior-without-a-test | FIXED | every Behavior Contract bullet has a Gate line; T02 appends byte-equality tests for the emitted module; T01 appends the vendored module's own test |
| ledger: census | FIXED | the 10-of-11 stdlib-logging census re-run from the script in § Evidence; denominator restated as files that CALL `logger.error`/`.exception`, not files that import logging (T02 back-fill loop excludes hub/templates) |
| ledger: sdk-semantics | FIXED | `LoggingIntegration(event_level=logging.ERROR, level=None)` still ships `logentry.params`/`formatted` before the scrubber; the vendored `_scrub_event` strips them — read at `/opt/site-provisioner/api/glitchtip_init.py:382-395` (`_reduce_logentry`, 7b83573) and its logentry tests; `before_send` is skipped for transactions (sentry-sdk `client.py:917-922`), hence `before_send_transaction` |
| ledger: substitution | FIXED | the inline literal is a plain triple-quoted string with LITERAL `{pkg}`; T02 uses `str.replace` on `{pkg}`/`{name}` from `package_name`/`name`, each token present exactly once (T01 asserts the count) |
| ledger: guard-executability | FIXED | `sentry_sdk.integrations.fastapi` imports in the hub `.venv`; `sentry-sdk[fastapi]>=2.18.0` + `structlog>=24` authorised in `pyproject.toml` dev extras as T01's FIRST step; `_serialize` via `item.payload.json` |
| ledger: deps | FIXED | the deps-file edit is authorised in-ticket (HARD STOP row) — T01 step 1, not an implicit side effect |
| ledger: grammar | FIXED | Ticket Board leading pipes; numbered `## Merge Order` = ticket set; Touches ⊆ File Scope; governance surfaces out of Touches; spine `## Behavior Contract` = verbatim union of ticket bullets; the doubled `## Interfaces` heading removed at the flip |
| ledger: sizing | FIXED | per-ticket in-repo read sets re-measured with `find … \| wc -c`; out-of-repo Context Files count 0 at the gate and are named in Scope prose (WARN accepted) |
| ledger: ledger | CLEAN | D-126 row: 6 cells, no bare pipe, CLASS reversible in the where cell, supersedes nothing (`decisions.py --check` clean) |
| ledger: ordering | FIXED | Merge Order T01, T03, T04, T02 — acyclic against Depends, Integration last; T03's watched fail is against the literal T02 has not yet replaced |

## Pass Ledger

Every row is a round that actually ran. `method: citation` re-verifies that a cited anchor exists;
`method: re-derivation` recomputes the fact from its primary source (a re-run census, an import
executed in the venv, a `diff` of the Node paragraph, a byte count); `method: gate` is a mechanical
check's own verdict. The ledger classes (census · sdk-semantics · substitution ·
guard-executability · deps · grammar · sizing · ledger · ordering) were fixed at round 1 and
RE-SWEPT every round — no round re-scoped.

| Pass | axes re-checked | method | raised | new classes | edits |
|-----:|---|---|---:|---:|---:|
| Pass 1 | author-blind #1 — pool finders over all nine classes; every citation re-resolved | method: re-derivation | 9 | 0 | 9 |
| Pass 2 | author-blind #2 — sdk-semantics (logentry path read in the vendored source), substitution mechanism | method: re-derivation | 5 | 0 | 5 |
| Pass 3 | author-blind #3 — guard-executability (imports executed in the venv), deps authorisation | method: re-derivation | 5 | 0 | 5 |
| Pass 4 | author-blind #4 — grammar + sizing (dead finder partition re-dispatched as a pair) | method: gate | 2 | 0 | 2 |
| Pass 5 | author-blind #5 — census re-run, denominator restated | method: re-derivation | 3 | 0 | 3 |
| Pass 6 | author-blind #6 — rule 55 range + Node paragraph `diff`, type lists (three dead finders re-dispatched) | method: re-derivation | 5 | 0 | 5 |
| Pass 7 | author-blind #7 — ordering + ledger row shape | method: gate | 2 | 0 | 2 |
| Pass 8 | author-blind #8 — T03 watched fail extracted verbatim and run | method: re-derivation | 1 | 0 | 1 |
| Pass 9 | author-blind #9 — Behavior Contract roll-up equality, Touches ⊆ File Scope | method: gate | 2 | 0 | 2 |
| Pass 10 | author-blind #10 — full nine-class sweep after the round-9 edits | method: re-derivation | 2 | 0 | 2 |
| Pass 11 | author-blind #11 — the closing pass: every class re-swept from primary source, `command_run.py round` printed TERMINAL | **method: re-derivation** | 0 | 0 | 0 |
| Pass 12 | RE-OPENED 2026-09-05 on site-provisioner 01M1R5EE (item 14): the vendor pin was stale — `060c096` → `8e2f436` re-derived (`ast` parses; 71 `def test_` vs 46; `before_send_transaction` ×2; `_redact_userinfo_in_text` present; module line cites re-resolved); D-127 minted; one finding, closed in the set | **method: re-derivation** | 1 | 0 | 1 |
| Pass 13 | RE-OPENED again on site-provisioner 01M1R78S (item 14 CORRECTED: the DSN reaches the field through a URL-PARSE failure, 1 of 6 shapes, not a connection failure — their D-016): the pin moved `8e2f436` → `7b83573` (4 module/test commits: the reachable field redacted, damaged separators accepted, termination pinned); re-derived on the blob: `ast` parses, 75 `def test_`, `before_send_transaction` ×2, every cite re-resolved; D-130 minted; one finding, closed in the set | **method: re-derivation** | 1 | 0 | 1 |

Round totals: 38 raised over passes 1–10, 12 and 13, 38 closed in the set, 0 open; pass 11 raised 0 — the
no-op round — and passes 12–13 (the re-opens) each closed their single finding in the same change. Plan-dir commits carrying the rounds, newest first: ff667c97 5a1a6d4d 72f96a6e 504abbcd 091a220c cd93ff2f 42864624 c3de9601 dacae798 d7fed38b 6620467d .
