# GlitchTip scrubbing in the scaffold is a deny-by-default SHAPE, not a flag list (build plan)

Status: DRAFT
**Owner:** infra authors; T02 (the emitter + the back-fill notices at merge) is fleet's beat (scaffolding) — named per ticket; execution on the operator's go-word
Shape: spine + 4 tickets (the READ set of the scope is 445,243 bytes against the 262,144 per-ticket budget, and `src/fabrik/scaffold.py` alone is 280,969 — see § Self-audit § Sizing)
Source: mail `01M1QSRJ6M0MB3RGAWZD5F4ZT2` (site-provisioner, CRITICAL) + its correction `01M1QWM094Z6S0ZYGPKTB4NPY0`; proposal `/opt/site-provisioner/docs/reference/upstream-proposals/2026-09-05-scaffold-glitchtip-remaining-channels.md` (221 lines, addendum "five was an undercount", corrected at their `060c096`)
Ledger: D-126 (minted in this change)

## What we already agreed

- **The problem (proposal § The claim, grounded; hub emitter `src/fabrik/scaffold.py:1712-1733`):** the scaffold's `sentry_sdk.init` carries the f273064c two-flag fix (`include_local_variables=False`, `max_request_body_size="never"`, `:1729-1730`) and nothing else; the sender reproduced ~11 further channels against sentry-sdk 2.68.1 — `before_send` is SKIPPED for transaction events (`client.py:917-922`), outbound request URLs land in breadcrumbs with no PII gate and persist onto later events (a live Bing API key left the process inside an unrelated error), `EventScrubber` never touches `logentry` (`scrubber.py:170-176`), `request.url`/`query_string`, db-span SQL, `span.data["http.query"]`, headers delegated to a 7-name list, source context, the transaction name, and containers kept WHOLESALE after passing a top-level allowlist (frame `vars` rode inside `exception`/`threads`).
- **The direction is the SHAPE, never a longer list (sender's SYSTEMIC + INDUCTIVE, accepted):** the two-flag fix is itself a denylist; two of the sender's own class fixes were denylist-shaped one level in. Every count so far was an undercount; "the count is not what the hub should act on — the shape is." So: deny-by-default allowlists per event key / request key / header / span key / context key / frame key / mechanism key, plus LEAF-SHAPE enforcement (an allowlisted key holding an unexpected container is nulled), registered as BOTH `before_send` and `before_send_transaction`, `include_source_context=False`, `max_breadcrumbs=0`, `server_name` = the service name.
- **Vendor, don't build (CLAUDE.md § Pointers; `fabrik-lib/README.md` row 57 `observability/`):** the reference implementation is `/opt/site-provisioner/api/glitchtip_init.py` (33,955 bytes) guarded by 59 tests in `/opt/site-provisioner/tests/test_glitchtip_init.py`; fabrik-lib's `observability/` module carries no scrubber (`grep before_send|scrub` → 0 hits in `/opt/fabrik-lib/observability/*.py`). The module is copied into the hub's scaffold template tree and emitted by copy, the way `templates/scaffold/python/pause_state.py` already is (`src/fabrik/scaffold.py:1744`).
- **The fleet default for the stdlib-logging channel — DECIDED here, D-126 (reversible: a re-emit):** the proposal's open question ("how many scaffolded services log through stdlib `logging` rather than structlog") is MEASURED: 11 repos on the box carry a `glitchtip_init.py`; stdlib `logging` appears in ≥1 tracked file in **10 of 11**, structlog in 11 of 11; with the STRICTER denominator the review demanded — a stdlib-only file that CALLS `logger.error/exception/critical` — it is **6 of 11** (brand-identiy-creator 6 files, seo 21, transdoc 7, web-ecommerce-factory 5, site-provisioner 1, tryton-crm 1; § Evidence, Phase A). Same verdict either way: a majority loses ERROR signal. Closing the channel entirely (site-provisioner's own D-007) would silence `logger.error` events fleet-wide. Verdict: log EVENTS are KEPT (`LoggingIntegration(event_level=logging.ERROR, level=None)`), BREADCRUMBS are OFF (`level=None` + `max_breadcrumbs=0`), and `logentry` is reduced to the raw template (`_ALLOWED_LOGENTRY_KEYS = {"message"}` — `params`/`formatted` dropped, the interpolation channel closed). The vendored module already implements exactly this shape for `logentry`; only the `LoggingIntegration` kwargs differ from site-provisioner's (theirs: `event_level=None`).
- **Which emitters are in scope (measured by `ast`, § Evidence Phase A):** the Python init is written by `_scaffold_fastapi_backend` (`src/fabrik/scaffold.py:1567-1868`), reached by `python-api`, `python-api-gpu` (via `_scaffold_python_api:1929`) and `saas-skeleton` (`_scaffold_saas_backend:3276`) — 3 of the 12 scaffoldable types. `node-api` (`_scaffold_node_api:3613`) and `chrome-extension` (`_scaffold_chrome_extension:4462/4480/4733`, an isolated BrowserClient) have their own inits: the Node/browser `beforeSend` equivalent is a RESIDUAL follow-up, not this plan (the channels were reproduced against the Python SDK only). The other 7 types emit no Sentry init.
- **The guard asserts the CAPTURED EVENT, never the kwarg (rule 55 § "Verify on the CAPTURED EVENT"; the original mail's instruction, which is what surfaced all of this):** `tests/test_scaffold_glitchtip_security.py` today asserts two flag strings in the emitted text (`:40-41`, 2 tests) — which is why the gap was invisible to the hub's own enforcement.
- **Already-deployed services are NOT re-emitted by this plan.** The back-fill is a notice to the 11 repos naming the vendoring step (T05); the rule-pack sentence "a project scaffolded BEFORE that date still has the old init" (`.windsurf/rules/core/55-observability.md:~273`) is rewritten to point at the module.
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
| T01 | Vendor the scrubber into the scaffold template tree | — | ⚡ | ⬜ | |
| T03 | The guard asserts the captured event through a swapped transport | T01 | ⚡ | ⬜ | |
| T04 | Rule 55 § Error Reporting states the shape | T01 | ⚡ | ⬜ | |
| T02 | The FastAPI emitter copies the module (integration, last; the back-fill notices at merge) | T03, T04 | — | ⬜ | |

## Merge Order

1. T01
2. T03
3. T04
4. T02

(T03 and T04 are parallel after T01; T02 is the single `Integration: true` ticket and merges last — its byte-equality tests consume T01's template and T03's guard runs in its gate.)

## Interfaces## Interfaces

- `templates/scaffold/python/glitchtip_init.py` → copied by `_scaffold_fastapi_backend` to `src/<package>/glitchtip_init.py` with the `{pkg}` docstring placeholder substituted; public surface unchanged: `init_glitchtip() -> bool` (the app calls it once at module load, `src/fabrik/scaffold.py:1793-1800`).
- The module's `_scrub_event(event, hint)` is registered as `before_send` AND `before_send_transaction`; `LoggingIntegration(event_level=logging.ERROR, level=None)`; `max_breadcrumbs=0`; `include_source_context=False`; `server_name=os.environ.get("SERVICE_NAME", "<name>")`.
- The guard (`tests/test_scaffold_glitchtip_security.py`) scaffolds a `python-api` into `tmp_path`, imports the emitted module, swaps `sentry_sdk`'s transport for a capturing one, raises inside a FastAPI route with secrets in locals / body / headers / URL query / a `logger.error("%s", secret)` / an outbound request breadcrumb, and asserts on the captured error event AND transaction event.

## Global Constraints

- Deny-by-default + leaf-shape is the shape; no ticket adds a denylist (a finding that wants one is a BLOCKED spec contradiction, not a fix).
- The vendored module is COPIED (fabrik-lib law); its origin and revision are recorded in its docstring (`site-provisioner api/glitchtip_init.py @ 060c096`).
- `sentry-sdk[fastapi]>=2.18.0` stays the pin the scaffold emits (`src/fabrik/scaffold.py:2125`). The hub `.venv` has NEITHER `sentry_sdk` NOR `structlog` (measured); T03 AUTHORISES adding both to `pyproject.toml` `[project.optional-dependencies] dev` (the deps-file HARD STOP is lifted by this ticket, for these two lines only) and the guard RECORDS the installed version in its output.
- Synced surfaces: `.windsurf/rules/core/55-observability.md` distributes to 45 repos on commit; `templates/scaffold/**` and `src/fabrik/scaffold.py` are hub-only.
- Every ticket: watched-fail-first graders; `/fabrik-review` at each phase boundary (execute-plan's own contract); explicit pathspecs; no `git add -A`.

## Behavior Contract

- **Given** the template file, **When** parsed with `ast`, **Then** it defines `init_glitchtip` and `_scrub_event`, the string `before_send_transaction=_scrub_event` appears once (`/opt/site-provisioner/api/glitchtip_init.py:604` is the reference line), and the tokens `{pkg}` and `{name}` each appear exactly once.
- **Given** the template, **When** its `LoggingIntegration(` call is read, **Then** it carries `event_level=logging.ERROR` and `level=None` — the fleet default, not site-provisioner's `event_level=None` (D-126).
- **Given** `_ALLOWED_LOGENTRY_KEYS`, **When** read, **Then** it is exactly `{"message"}` (the interpolation channel closed; `params`/`formatted` never pass).
- **Given** an event whose allowlisted key holds an unexpected container, **When** `_scrub_event` runs, **Then** that key is nulled (leaf-shape) — imported and executed in the test, not read.
- **Given** a `python-api` scaffold into `tmp_path`, **When** `src/<pkg>/glitchtip_init.py` is read, **Then** it equals the template with `{pkg}`/`{name}` substituted and contains neither token (other braces are the module's own).
- **Given** `python-api-gpu` and `saas-skeleton` scaffolds, **When** the same file is read, **Then** the same holds (3 of 3 reaching types).
- **Given** the template file is absent, **When** the scaffold runs, **Then** it raises (no silent skip) — proven by monkeypatching `TEMPLATE_DIR`.
- **Given** the existing scaffold suite (`tests/test_scaffold.py`), **When** run, **Then** it is green — nothing else in `_scaffold_fastapi_backend` changed.
- **Given** the merge, **When** the back-fill notices are sent, **Then** one mail id per repo carrying a `glitchtip_init.py` is recorded in this ticket's review artifact, the count re-measured with its denominator, and `mail.py` prints no D-035 advisory.
- **Given** the emitted module with a capturing transport, **When** a route raises with the six secrets in play, **Then** the serialized ERROR event contains none of them (substring search over the whole event).
- **Given** `traces_sample_rate=1.0`, **When** the request completes, **Then** the captured TRANSACTION event contains none of them either (`before_send_transaction` is registered; `client.py:917-922` skips `before_send` for transactions).
- **Given** a `logger.error("otp=%s", secret)`, **When** captured, **Then** `logentry == {"message": "otp=%s"}` — the template, never the interpolation; and no breadcrumb carries it.
- **Given** the current inline literal (the two-flag init at `src/fabrik/scaffold.py:1678-1735`), **When** the same assertions run against it, **Then** they are RED — recorded in the ticket's review artifact as the watched fail.
- **Given** the Node emitter, **When** the existing two Node assertions run, **Then** they still pass (unchanged surface).
- **Given** the hub `.venv` after `pip install -e .[dev]`, **When** the guard imports the template module, **Then** `init_glitchtip()` returns True and `sentry_sdk.VERSION` is printed — a False (the ImportError path) fails the test.
- **Given** T01's template tests in the same file, **When** T03 merges, **Then** they are byte-identical (the diff touches only the two replaced tests and the additions).
- **Given** the rewritten section, **When** read, **Then** the words "deny-by-default", "leaf", "before_send_transaction", "max_breadcrumbs=0" and "include_source_context=False" each appear, and "Two init flags are MANDATORY" is reframed as the floor.
- **Given** the Node paragraph (`.windsurf/rules/core/55-observability.md:246-254`), **When** diffed, **Then** it is byte-identical (the asymmetry correction of 2026-08-28 is not touched).
- **Given** the back-fill sentence, **When** read, **Then** it names the template path and the vendoring step, and no longer says "as of 2026-08-28 … add them".
- **Given** the 7 types with no Sentry init, **When** the section is read from one of their repos, **Then** one sentence says the section does not apply to them.

## Context Ledger

| Source | Read | Bound into |
|---|---|---|
| `python scripts/select_rules.py` — 26 ACTIVE | core/10-python, core/45-testing-strategy, core/55-observability, core/40-documentation, core/35-security-auth, core/62-using-subagents (+ the 20 others named by the run) | T01–T05 gates; § Global Constraints |
| `agents-fabrik.md` § Scaffold Types (`:384`), GlitchTip row (`:196`) | 12 scaffoldable types; GlitchTip at errors.vps1 | § What we already agreed (emitters in scope) |
| `fabrik-lib/README.md:57` `observability/` | logging + Sentry init, NO scrubber | vendor from site-provisioner instead |
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

- `src/fabrik/scaffold.py:1678` (the inline `glitchtip_init.py` literal), `:1712` (`sentry_sdk.init(`), `:1729-1730` (the two flags), `:1744` (`pause_src = TEMPLATE_DIR / "python" / "pause_state.py"` — the copy pattern), `:244` (`TEMPLATE_DIR = FABRIK_ROOT / "templates" / "scaffold"`), `:2125` (the sentry-sdk pin); `tests/test_scaffold_glitchtip_security.py:31-53`; `.windsurf/rules/core/55-observability.md:232-275`.

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
ModuleNotFoundError: No module named 'sentry_sdk'   (structlog likewise — T03 authorises the dev extras)
$ find <scope> -type f -exec cat {} + | wc -c
445243
$ wc -c src/fabrik/scaffold.py
280969
```

### Phase B — the reference module and its guard

- `/opt/site-provisioner/api/glitchtip_init.py:33-141` (the allowlists), `:168` (`_keep`), `:390` (`_scrub_event`), `:527-620` (`init_glitchtip` / `_init_sdk`: `before_send=_scrub_event`, `before_send_transaction=_scrub_event`, `include_source_context=False`, `LoggingIntegration(event_level=None, level=None)`); `/opt/site-provisioner/tests/test_glitchtip_init.py` (59 tests).

```
$ grep -c "def test_" /opt/site-provisioner/tests/test_glitchtip_init.py
59
$ grep -rn "before_send\|scrub" /opt/fabrik-lib/observability/*.py | wc -l
0
```

## Self-audit

- Grounding passes: every claim above is a `path:line` I read this session or a fenced output I ran; the channel list is the sender's, reproduced by them — this plan does not re-count it (the shape is what is acted on).
- Completeness (a) — a consumer of the plan's output exists in File Scope: the guard test consumes the emitted module; `_scaffold_fastapi_backend` consumes the template file; the rule pack is read by every project.
- Completeness (b) — every ticket's Touches path is in File Scope (T01: template + the test; T02: scaffold.py + the test; T03: the test; T04: rule 55); governance surfaces are orchestrator-applied and listed as such.
- Sizing: per-ticket READ sets measured in-repo (T01 59,803; T03 62,638; T04 57,494 — Touches + Context Files, `wc -c`, with the not-yet-created template counted at 0) PLUS the out-of-repo reads the gate counts as 0 and the tickets name with their bytes (module 33,955; its tests 69,210; the proposal 15,111); T02's Touches is `src/fabrik/scaffold.py` alone at 280,969 > 262,144 — `Integration: true`, last in Merge Order, with the reason stated in the ticket (a one-function edit inside a 281 KB file).
- Fire rate of the new structure: the guard runs on every hub gate; the emitted module runs in every new python-api/saas-skeleton service with a DSN set.

## Residual unknowns

- **Resolved:** the logging-channel default (D-126); which types emit the init (3 Python, 1 Node, 1 browser); whether fabrik-lib holds a scrubber (no).
- **Open — Node/browser parity:** `node-api`'s `Sentry.init` (`scaffold.py:3613`) and `chrome-extension`'s BrowserClient have no `beforeSend` shape; owner fleet; probe: reproduce the URL-in-breadcrumb and logentry channels against `@sentry/node`, then a sibling plan. Named in T05's notice.
- **Open — the 11 deployed services:** they back-fill by vendoring the module themselves; T05's notice names the step; nothing here re-emits them. Owner: each repo, on fleet's notice.

## Execution Discipline

- Owners: T01/T03/T04 infra; T02 fleet (scaffolding beat), including the back-fill notices at its merge. The dispatching session mails fleet the plan pointer at the go-word; a single session may execute all five if the operator says so.
- Per ticket: the ticket's Gate lines green, `/fabrik-review` over the ticket's diff to a quiet round, commit with explicit pathspecs + trailers (`Agent-Phase`), push; the orchestrator fills the Commit cell and applies CHANGELOG/INDEX/DECISIONS.
- Pool by default for review finders; native for the guard's design (a security surface).
