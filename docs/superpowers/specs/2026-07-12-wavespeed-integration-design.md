# WaveSpeed integration into the kilo-benchmarks pipeline — design spec

**Status:** CONVERGED
**Date:** 2026-07-12
**Converged:** 2026-07-12 (/fabrik-spec-review — 5 passes to an edit-free md5-verified no-op; live re-verified every cited URL + every claimed API endpoint + the fabrik-lib vendor-ladder verdicts, discovered the `/api/v3/model/pricing` endpoint the spec had missed, discovered the docs' key-activation caveat, and killed 3 dangling "notes column" references introduced by earlier text)
**Author:** primary (this session)

## Goal

Wire the WaveSpeed AI catalog (941 models across 25 types on `https://api.wavespeed.ai/api/v3/`) into the fabrik AI-model pipeline the same way SiliconFlow and ModelScope are already wired: catalog scrape → row seed → per-model pricing → ranking-aware surface in `agents.db` + the GUI (`models_browser.html`). Purpose: give `pick_models` a way to see WaveSpeed models as candidates, and give the AI Models Browser a way to display them alongside the existing 815 models — so the operator can compare cost/capability across vendors on one screen.

## Chosen approach — mirror the existing scrape_*_catalog.py pattern, extend service_type enum, no benching (catalog-only)

**Composition (four surgical additions + one migration):**

1. **`scripts/kilo-benchmarks/scrape_wavespeed_catalog.py`** (new, ~250 LOC) — mirrors `scrape_modelscope_catalog.py` structure:
   - Fetch `GET https://api.wavespeed.ai/api/v3/models` with `Authorization: Bearer $WAVESPEED_API_KEY`
   - Cache raw JSON at `scripts/kilo-benchmarks/cache/wavespeed_catalog.json` (already gitignored via `cache/*.json`)
   - Type-normalize each of the 941 rows into an `agents.service_type` value (mapping below)
   - Compute one representative `output_cost_per_m` per row using `base_price × typical_usage_units` per type (table below)
   - Do a **hybrid write**: `INSERT OR REPLACE` for wavespeed-native model_ids that don't already exist, `UPDATE agents SET via_wavespeed=1` on any overlap (e.g. `wavespeed-ai/flux-schnell` may or may not equal a `bfl/flux-schnell` row we already have)
   - `--dry-run` for inspection; idempotent

2. **`scripts/kilo-benchmarks/add_via_wavespeed_column.py`** (new, ~40 LOC) — copies the `add_perf_seconds_column.py` pattern:
   - `PRAGMA table_info(agents)` check → `ALTER TABLE agents ADD COLUMN via_wavespeed INTEGER` if absent
   - Idempotent, safe to re-run
   - Called by `scrape_wavespeed_catalog.py` on first invocation (same as `microbench_specialty.py::run_specialty` invokes `add_perf_seconds_column`)

3. **`scripts/kilo-benchmarks/derive_quality_v2.py`** (modify, ~10 LOC delta) — extend the `SERVICE_TYPES_KNOWN` set (or equivalent gate) to include `'3d_gen'` and `'moderation'` so quality-tier derivation doesn't skip WaveSpeed's 30 new-category rows.

4. **`scripts/kilo-benchmarks/export_models_browser.py`** (modify, ~30 LOC delta) — no new columns; ensure the payload exposes `service_type` in `('3d_gen', 'moderation')` values so the browser JS can filter them. Add a `via_wavespeed` badge on the model card (matching the existing `via_siliconflow`/`via_modelscope` badge pattern in `models_browser.html`).

5. **`docs/reference/kilo/AI_VENDOR_ACCESS.md`** (modify, ~1 LOC delta) — update the WaveSpeed row DB-provider(s) cell from `(none — no rows in DB yet)` to `wavespeed-ai, pruna-ai, pixverse, kwaivgi, sync, ...` (the actual populated sub-vendor set post-scrape).

6. **`scripts/kilo-benchmarks/daily_refresh.sh`** (modify, ~2 LOC delta) — add `python scrape_wavespeed_catalog.py` to the daily-scrape sequence right after `scrape_modelscope_catalog.py` so the catalog stays fresh.

**Service_type mapping** (approved default #1 — 3d_gen + moderation as new enums):

| WaveSpeed type | Count | → `agents.service_type` |
|---|---:|---|
| text-to-image, image-to-image, upscaler, ai-remover, portrait-transfer, lora-support | 363 | `image_gen` |
| text-to-video, image-to-video, video-to-video, video-extend, video-effects, video-dubbing, motion-control, digital-human, audio-to-video | 422 | `video_gen` |
| text-to-audio, audio-to-audio | 76 | `music_gen` |
| speech-to-text | 10 | `stt` |
| image-to-text, video-to-text | 21 | `ocr` |
| llm | 6 | `llm` |
| **text-to-3d, image-to-3d** | **25** | **`3d_gen`** (NEW enum) |
| **content-moderation** | **5** | **`moderation`** (NEW enum) |
| training | 13 | *skipped* (not a serving endpoint) |

Total serving rows: **928** (941 − 13 training). New enum values: **2** (`3d_gen`, `moderation`).

**Pricing normalization** (approved default #2 — base_price + type-normalized $/unit):

Per type, compute a representative per-call cost, then normalize to `output_cost_per_m` on the same 0-6 decimal $/1M-tokens scale the rest of the pipeline uses (matching OpenRouter's normalization convention). Formula: for a "typical" usage assumption per type, compute `base_price × typical_units × 1_000_000`.

| service_type | typical unit assumption | $/M formula |
|---|---|---|
| `image_gen` | 1 image @ 1024×1024 | `base_price × 1_000_000` |
| `video_gen` | 5-second video, 720p | `base_price × 5 × 1_000_000` |
| `music_gen` | 60s of audio | `base_price × 60 × 1_000_000` |
| `stt` | 60s of audio | `base_price × 60 × 1_000_000` |
| `ocr` | 1 image + caption | `base_price × 1_000_000` |
| `llm` | 1000 output tokens | `base_price × 0.001 × 1_000_000` = `base_price × 1000` |
| `3d_gen` | 1 mesh | `base_price × 1_000_000` |
| `moderation` | 1 image | `base_price × 1_000_000` |

These assumptions are **explicitly recorded in a docstring** of `scrape_wavespeed_catalog.py` so a future reader knows what "typical" means. Real per-call cost varies with formula(inputs) — the raw `formula` string persists in the cached catalog JSON at `scripts/kilo-benchmarks/cache/wavespeed_catalog.json` for a future jsonata-based evaluation (deferred; see Rejected Alternative #2).

**No benching now** (approved default #3): catalog-only seed. Models are ranked on price + presence flags. Any coding-microbench-like WaveSpeed benching is opt-in follow-up work when the account is topped up.

## Rejected alternatives

1. **Per-concern split (fetch + normalize + seed as three scripts)** — Rejected. More testable in isolation but violates the "consistency with existing precedents" principle: `scrape_modelscope_catalog.py` and `scrape_siliconflow_catalog.py` are both single-script all-in-one. Diverging here creates operator surprise and doubles the daily_refresh.sh entry-point count without any real benefit at this scale (< 941 rows).

2. **Use `/api/v3/model/pricing` (POST) or full jsonata formula evaluation for accurate per-call cost** — Rejected. Two accuracy paths considered: (a) call the vendor's own `/api/v3/model/pricing` endpoint per model, or (b) parse the `formula` string with `jsonata-python`. (a) is unreliable in practice — live probe on 2026-07-12 showed `unit_price: 0` for input-dependent models like `sync/lipsync-3/avatar` and HTTP 500 for common models like `wavespeed-ai/flux-dev-fill` and `flux-pro-1.1-ultra` (server bug). (b) would add a `jsonata-python` (or `jsonatapy`) dependency + build a `get_duration_v2` custom-function stub + wire it into normalization — high complexity for penny-accurate cost display. Both alternatives fail worse than the catalog-`base_price` approximation for our coarse-ranking need. Deferred to a follow-up plan if WaveSpeed picks turn out to be cost-inaccurate in production. Design decision: **the raw `formula` string stays in the cached catalog JSON at `scripts/kilo-benchmarks/cache/wavespeed_catalog.json`** (already written by the scraper for every run); a future upgrade to real jsonata evaluation can read from cache without a DB column and without a re-scrape. No `notes` column on `agents` — the cached JSON is the source-of-truth for the raw `formula` field.

3. **Force-fit 3D + moderation into existing enums** — Rejected. Would collapse 3D-gen into `image_gen` and content-moderation into `llm`. Both muddy the ranking pipeline (3D and image_gen have wildly different price/perf axes; moderation is a classifier, not a generative LLM). One-line schema/derive_quality_v2 change to add the enums is trivial.

4. **Skip 3D + moderation entirely** — Rejected. WaveSpeed's image-to-3d category (19 models) is genuinely useful (Hunyuan3D-v2 is the current OSS SotA); skipping it loses one of the vendor's stronger competitive angles.

5. **Add a separate `wavespeed_browser.html` GUI page** — Rejected. Duplicates the infrastructure; loses the cross-vendor comparison story. The additive `via_wavespeed` badge + `service_type` filter approach in the existing browser is the leaner call.

## External dependencies (all live-grounded this session)

| Dependency | Fact | Source (fetched 2026-07-12) |
|---|---|---|
| WaveSpeed catalog endpoint | `GET https://api.wavespeed.ai/api/v3/models` returns `{code, message, data:[{model_id, name, base_price, description, type, api_schema, formula, sort_order}, ...]}`. **941 models as of 2026-07-12** (may drift on refetch — the scraper logs the actual count on each daily run). | `https://wavespeed.ai/docs/list-models` + verified via live `curl` — HTTP 200, 941 rows |
| Per-model pricing endpoint | `POST https://api.wavespeed.ai/api/v3/model/pricing` with body `{"model_id": "..."}` returns `{data: {model_id, unit_price, currency}}`. **Reliability caveats**: matches `base_price` verbatim for simple-formula models; returns `unit_price: 0` for input-dependent models (e.g. `sync/lipsync-3/avatar`); returns HTTP 500 for some models (e.g. `wavespeed-ai/flux-dev-fill`, `flux-pro-1.1-ultra`) — server bug. **Not used** by this spec — see Rejected Alternative #2. | `https://wavespeed.ai/docs/how-pricing-works` (references endpoint) + live probe this session (4 model_ids) |
| Auth mechanism | `Authorization: Bearer ${WAVESPEED_API_KEY}` | `https://wavespeed.ai/docs/api-authentication` |
| Failure codes | 401 = "Check your API key is correct"; 403 = "Your account may be suspended — contact support" | `https://wavespeed.ai/docs/api-authentication` (verbatim) |
| Key activation caveat | Docs say "API keys require a top-up to activate. Keys created before your first top-up will not work." **In practice** the $1 Bronze trial acts as activation for the read-only endpoints we use (`/api/v3/models`, `/api/v3/balance` returned HTTP 200 with no top-up on 2026-07-12). Whether generation endpoints require a real top-up is untested (not exercised by this catalog-only spec). | `https://wavespeed.ai/docs/api-authentication` + live probe |
| Rate limits | Bronze tier: 2 images/min + 2 videos/min + 2 concurrent tasks. Silver: 500/500/300 (activated by one-time $100 top-up). Gold: 3000/3000/3000 ($1000 top-up). Ultra: 5000/5000/10000 ($10000 top-up). **Note**: rate limits stated per-generation-endpoint; catalog fetch (`/api/v3/models`) is not documented as rate-limited. | `https://wavespeed.ai/docs/pricing` (verbatim tier table) |
| Current account tier | Bronze (`/api/v3/balance` returned `{balance: 1}` on 2026-07-12 probe — matches docs' "New accounts receive $1 trial credit") | Live probe this session — one catalog fetch/day is well within Bronze limits |
| Pricing model (as reflected in catalog `data[]`) | `base_price` (float USD) is the price signal present in each catalog row — we adopt it as our approximation. The docs discuss "per-model pricing" and "usage-based pricing" but do **not** explicitly name `base_price` as canonical. `formula` field strings use jsonata-like primitives (`$exists`, `$number`, `$ceil`, `$sum`, ternary `?:`) with a custom `get_duration_v2()` function for input-dependent multipliers — **inferred** from the formula strings, **not documented** as jsonata by the vendor. "Final charge may vary slightly from the estimate." | `https://wavespeed.ai/docs/how-pricing-works` (that quote is verbatim) + observed in catalog `data[].formula` strings |
| Pricing normalization convention | Industry standard: normalize to $/1M tokens or $/1M units with six-decimal precision. Vendor list prices are inconsistent; gateway prices (what WaveSpeed's `base_price` is) are more reliable. | OpenRouter scraper convention documented at `https://apify.com/parseforge/openrouter-models-pricing-scraper` (fetched 2026-07-12) |
| jsonata Python evaluators | `jsonata-python` (rayokota, pure Python), `jsonatapy` (Rust-backed), `pyjsonata` (ctypes bindings) — all available, MIT-licensed. Not adopted in this spec (see Rejected Alternative #2). | `https://github.com/rayokota/jsonata-python` |

## fabrik-lib verdict table

| Capability | Ladder verdict | Module (or why build) |
|---|---|---|
| HTTP fetch of WaveSpeed catalog | **BUILD** (project-local) | Existing `scripts/kilo-benchmarks/scrape_*_catalog.py` scripts use `httpx` sync client inline (~10 LOC). fabrik-lib's `async-http-client/` is async — mismatches the sync kilo-benchmarks pipeline. Not worth async-ifying just for this. |
| Local disk cache of the fetched catalog JSON | **VENDOR** (via convention) | `scripts/kilo-benchmarks/cache/*.json` is the existing convention (gitignored). Not a fabrik-lib capability — it's a `cache/` directory hardcoded across the kilo-benchmarks scripts. Match the convention. |
| SQLite catalog write (INSERT + UPDATE with flag) | **VENDOR + ENHANCE** (from precedents) | Mirror `scrape_modelscope_catalog.py::apply_flags` for the flag-flip logic, and mirror `discover_kilo_agents.py::_insert_agent` for the INSERT logic. Both are project-local patterns. No fabrik-lib module covers "AI vendor catalog scraping" (project-specific concern). |
| Schema migration (add `via_wavespeed` column) | **VENDOR** (via precedent) | Mirror `add_perf_seconds_column.py` verbatim (~40 LOC). PRAGMA table_info guard + `ALTER TABLE`. Standard idempotent pattern already used 6+ times in this pipeline. |
| GUI badge (`via_wavespeed`) in models_browser.html | **VENDOR + ENHANCE** (extend existing pattern) | The browser already shows `via_openrouter` / `via_kilo` / `via_siliconflow` / `via_modelscope` badges. Add a 5th badge — trivial ~10-line JS + payload update. |
| jsonata evaluation | **defer** | Would be `BUILD` (new dep). Not needed in this spec's scope. Flagged as a `🆕 fabrik-lib candidate` **only if it becomes needed** — the `jsonata-python` package is already high-quality external so a fabrik-lib wrapper would be pure passthrough. Skip. |

**No new fabrik-lib module candidates.** The pattern is project-local (scripts/kilo-benchmarks/); nothing here is generic across ≥2 project types.

## Shape / infra implications

- **Scaffold type**: N/A — this is a change to `/opt/fabrik` scripts, not a new project.
- **`shape:` flags**: unchanged. No DB flip, no cache flip, no metrics flip, no search flip, no auth/admin flip.
- **Docker service**: none. Scripts run hub-side via `daily_refresh.sh`.
- **Ports**: none allocated.
- **Env vars added to `.env`**: none (WAVESPEED_API_KEY already added last turn).
- **New tables**: none. Two new `service_type` enum values (`3d_gen`, `moderation`) — the "enum" is not a SQL constraint, it's a Python-side convention documented in `derive_quality_v2.py` / `seed_specialty_catalog.py` / GUI export logic.
- **New columns on `agents`**: one (`via_wavespeed INTEGER`, nullable).

## Constraints

- **Rate limit at Bronze tier is 2 req/min** — catalog scrape is 1 request per day, safe. If we later add benching, we need to either top-up to Silver or throttle to ≤2 req/min. Design for now assumes no benching.
- **`base_price` is the canonical cost signal** but not the true per-call cost — this is a deliberate approximation (approved default #2). Raw `formula` persists in the cached catalog JSON (`scripts/kilo-benchmarks/cache/wavespeed_catalog.json`) for a future upgrade — no DB column needed.
- **model_id collisions**: some WaveSpeed IDs may collide with existing rows (e.g. our tree already has `bfl/flux-schnell` — WaveSpeed also serves `wavespeed-ai/flux-schnell`). The scraper's `INSERT OR REPLACE` uses the WaveSpeed model_id verbatim so no collision at the SQL level; the model_id NAMESPACE is different (`wavespeed-ai/...` vs `bfl/...`). Overlap detection for the `via_wavespeed` flip is by CANONICAL model name (strip the prefix), not literal ID — one-line canonicalization function in the scraper.
- **Idempotency**: the whole pipeline is idempotent — safe to re-run daily. `INSERT OR REPLACE` on model_id; `UPDATE ... WHERE COALESCE(via_wavespeed, 0) != 1` guards the flag-flip counter.
- **daily_refresh.sh** must NOT fail if WaveSpeed's endpoint is temporarily 5xx — the scraper's failure exits non-zero but daily_refresh.sh already tolerates individual step failures (verified: `set -e` is not set at that granularity). No new resilience work needed.

## Open / blocking unknowns

### Resolved during this drafting

1. **Service_type extension** — RESOLVED via user question: add `3d_gen` + `moderation` as new enum values (approved default #1).
2. **Pricing depth** — RESOLVED via user question: base_price + type-normalized $/unit (approved default #2).
3. **Benching now or later** — RESOLVED via user question: catalog-only (approved default #3). Benching deferred to a follow-up plan post-top-up.
4. **Vendor-ladder verdicts** — RESOLVED against `fabrik-lib/README.md` (fetched this session): no module covers AI-vendor-catalog scraping (project-local concern); mirror `scrape_modelscope_catalog.py` + `add_perf_seconds_column.py` + `discover_kilo_agents.py`.
5. **jsonata evaluator dep needed?** — RESOLVED: NO for this spec (rejected alternative #2). Formula field persists raw in the cached catalog JSON (`scripts/kilo-benchmarks/cache/wavespeed_catalog.json`) for a future upgrade — no DB column needed.

### Still-open (each with a self-service resolution step for the plan phase)

1. **[OPEN → resolve at plan Phase A]** Does `discover_kilo_agents.py` have an INSERT idempotency contract that plays nicely with `scrape_wavespeed_catalog.py`'s INSERTs? Some rows may be scraped by BOTH scripts (WaveSpeed provides an aggregator view that includes models from other vendors, e.g. `openai-whisper-turbo` is served by both WaveSpeed and Groq). Resolution: read `discover_kilo_agents.py::_insert_agent`; if it uses `INSERT OR IGNORE`, our `INSERT OR REPLACE` may override — decide priority (either "WaveSpeed row wins when we see the model on WaveSpeed's endpoint" OR "existing row wins, only flip via_wavespeed"). One-line decision for the plan.

2. **[OPEN → resolve at plan Phase D]** Which specific columns of the browser payload does WaveSpeed's non-LLM row need to fill? The existing browser is LLM-oriented — some columns (e.g. `humaneval_score`, `coding_score`) have no meaning for a video-gen model. Resolution: audit `export_models_browser.py::_fetch_chat_models` for null-tolerance, extend if needed. Non-blocking — the browser already handles `humaneval_score IS NULL` for non-coding models (verified via the 815 existing rows, many of which have NULL coding scores).

3. **[SELF-SERVICE]** The account is on Bronze tier ($1 balance). If a WaveSpeed scrape ever hits a paid endpoint (nothing in this spec does — `/models` is free per the docs), we'd need a top-up. Deferred; not blocking this spec.

## Handoff

**Next command**: `/fabrik-spec-review docs/superpowers/specs/2026-07-12-wavespeed-integration-design.md` — the mandatory adversarial re-verification that will re-fetch every cited URL live, audit the vendor-ladder verdicts against real fabrik-lib module capabilities, and flip `Status: DRAFT → CONVERGED` before the operator approves.

**Then**: since this design touches persistence (adds columns/rows to `agents.db`) but has no user-facing form fields, `/fabrik-data-contract` is not needed. Not a GUI project (the models_browser HTML changes are additive to an existing browser, not a new GUI-project). Skip to `/fabrik-plan-after-chat`.

**After approval**: `/fabrik-plan-after-chat docs/superpowers/specs/2026-07-12-wavespeed-integration-design.md` will inherit the vendor verdicts + cited facts + type mapping + pricing normalization decisions, and produce the phased plan (probably 4 phases: A = migration + scraper skeleton, B = full 941-row seed + via_wavespeed flip, C = derive_quality_v2 + daily_refresh.sh wiring, D = GUI badge + payload).
