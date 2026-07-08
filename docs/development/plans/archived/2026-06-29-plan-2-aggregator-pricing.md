---
Status: CONVERGED
Owner: ozgur
Created: 2026-06-29
Last revised: 2026-06-29 (4 grounding passes; per-phase Evidence; runnable gates)
---

# Aggregator pricing comparison for the AI Models Browser

## Problem

The 74 direct-vendor specialist rows in `agents` carry **operator-encoded prices from training-data knowledge** — there's no automated refresh from vendor pages ([scripts/kilo-benchmarks/seed_direct_vendors.py:79-94](../../../scripts/kilo-benchmarks/seed_direct_vendors.py#L79-L94) discloses this). Two consequences:

1. **Staleness**: vendors change prices; rows drift silently.
2. **Single-gateway view**: many models are reachable via multiple gateways at different prices (FLUX Pro on BFL direct AND Replicate AND fal.ai; SDXL on Replicate AND Stability direct; Whisper on OpenAI AND Replicate; etc.). The browser shows ONE price per row.

The LLM side already mirrors OpenRouter ↔ Kilo via [scripts/kilo-benchmarks/verify_openrouter_catalog.py:390-413](../../../scripts/kilo-benchmarks/verify_openrouter_catalog.py#L390-L413) (stores both prices in `input_cost_per_m` + `kilo_input_cost_per_m`; the browser decides cheaper at render time). Operator approved mirroring this for non-LLM specialists.

## Goal

Per-model live price comparison across all gateways that mirror our specialists, surfaced in the bake-off browser, refreshed daily. Operator should see e.g. `FLUX Pro 1.1: $0.04 BFL · $0.038 Replicate · $0.035 fal.ai` at a glance, with a "cheapest gateway" badge.

## Non-goals

- Routing API calls through the cheapest gateway (downstream, mt-router scope).
- LLM-side expansion to TogetherAI/Fireworks/HF Inference (Phase 6+, out of scope).
- Subscription / credit-based vendors where aggregators don't carry them (Suno, Udio, Pika, HeyGen) — stay direct-only.

## Aggregator landscape (post-grounding)

| Aggregator | Pricing source | Verified | Auth |
|---|---|---|---|
| **Replicate** | HTML scrape of model page; `<script id="react-component-props-*">` carries `billingConfig.current_tiers[0].prices[]` | ✅ confirmed Pass 2 + 3 | `REPLICATE_API_TOKEN` (move to `/opt/fabrik/.env`; currently only in `/opt/brand-identiy-creator/.env`) |
| **fal.ai** | `GET https://fal.ai/api/models` paginated; `pricingInfoOverride` Markdown per model | ✅ confirmed Pass 2 | `FAL_KEY` (configured in `/opt/fabrik/.env`) |
| TogetherAI / Fireworks / HF | LLM overlap only; deferred to Phase 6 | — | — |

**Critical post-grounding findings** (full details in `## Evidence` per phase):

- The original plan's claim that Replicate's `/v1/models/{slug}` API returns a `price` field is **DISPROVEN** — the API has no pricing. Per-image / per-second pricing lives in the model page's React-hydration JSON only.
- fal.ai works as a true API consumer; `pricingInfoOverride` is Markdown with **7 distinct shape categories** (parser spec in Phase 2 Evidence).
- The OpenRouter↔Kilo `kilo_input_cost_per_m` column has a **pre-existing decimal-shift bug** ([scripts/kilo-benchmarks/kilo_agents_db.py:240-241](../../../scripts/kilo-benchmarks/kilo_agents_db.py#L240-L241)) producing 13 fake "Kilo 99.9999% cheaper" outliers. **Phase 0.5 fixes this as a prerequisite** so the new aggregator pattern doesn't inherit it.

## Phases

### Phase 0 — Schema migration

Add three columns to `agents` (idempotent, mirror existing pattern):

```sql
ALTER TABLE agents ADD COLUMN gateway_prices TEXT;          -- JSON: {gateway: {price, unit, slug, url, last_seen}}
ALTER TABLE agents ADD COLUMN cheapest_gateway TEXT;        -- derived
ALTER TABLE agents ADD COLUMN cheapest_gateway_price REAL;  -- derived (same axis as input_cost_per_m)
```

**Implementation**: new script `scripts/kilo-benchmarks/migrate_aggregator_columns.py` using the `_column_exists() + _ensure_column()` pattern from [migrate_selector_columns.py:55-65](../../../scripts/kilo-benchmarks/migrate_selector_columns.py#L55-L65).

**Test impact**: `tests/kilo_benchmarks/test_category_selector.py::_make_db` (synthetic schema builder at lines 40-63) must add the three columns. All other tests use `SELECT *` and adapt automatically (Pass 3c).

**Validation gate**:

```bash
.venv/bin/python scripts/kilo-benchmarks/migrate_aggregator_columns.py && \
  sqlite3 scripts/kilo-benchmarks/kilo_agents.db "SELECT count(*) FROM pragma_table_info('agents') WHERE name IN ('gateway_prices','cheapest_gateway','cheapest_gateway_price')"
```

Expected: `3`. Then `.venv/bin/pytest tests/kilo_benchmarks/test_category_selector.py -v` → all green. **Then run the adversarial review per [§ Adversarial review](#adversarial-review-mandatory-after-each-phase).**

### Phase 0.5 — Fix kilo_agents_db.py decimal-shift bug (prerequisite)

[scripts/kilo-benchmarks/kilo_agents_db.py:240-241](../../../scripts/kilo-benchmarks/kilo_agents_db.py#L240-L241) multiplies Kilo's already-per-1M-token prices by 1M again. Compare with [verify_openrouter_catalog.py:147-148](../../../scripts/kilo-benchmarks/verify_openrouter_catalog.py#L147-L148) which correctly notes the format is already scaled.

**Fix**:

```python
# Before
input_cost = cost.get("input", 0) * 1_000_000
output_cost = cost.get("output", 0) * 1_000_000
# After
input_cost = cost.get("input", 0)
output_cost = cost.get("output", 0)
```

**Data cleanup**: 13 affected rows. Two paths:

- Re-sync via the next `verify_openrouter_catalog.py --apply --ingest-new` run (preferred — already in daily refresh).
- One-shot `UPDATE agents SET kilo_input_cost_per_m = kilo_input_cost_per_m * 1000000 WHERE via_kilo=1 AND kilo_input_cost_per_m IS NOT NULL AND kilo_input_cost_per_m < input_cost_per_m / 1000` (reverses the decimal shift on the 13 rows).

**Validation gate**:

```bash
sqlite3 scripts/kilo-benchmarks/kilo_agents.db \
  "SELECT count(*) FROM agents WHERE via_kilo=1 AND kilo_input_cost_per_m < input_cost_per_m / 1000"
```

Expected: `0`. Test suite still green (`.venv/bin/pytest tests/kilo_benchmarks/ -v` — no test depends on the buggy values, per Pass 3b). **Then run the adversarial review per [§ Adversarial review](#adversarial-review-mandatory-after-each-phase).**

### Phase 1 — Replicate fetcher

New script: `scripts/kilo-benchmarks/fetch_replicate_prices.py`. **HTML scrape**, not API (the `/v1/models/{slug}` API has no pricing — Pass 1 disproven, Pass 2 found the React-component JSON path).

**Mirror map** at `scripts/kilo-benchmarks/replicate_mirrors.yaml` (12 verified entries; Pass 3a re-confirmed all return HTTP 200 + HTML carries `billingConfig`):

```yaml
bfl/flux-pro-1.1: black-forest-labs/flux-1.1-pro
bfl/flux-pro-1.1-ultra: black-forest-labs/flux-1.1-pro-ultra
bfl/flux-pro: black-forest-labs/flux-pro
bfl/flux-dev: black-forest-labs/flux-dev
bfl/flux-schnell: black-forest-labs/flux-schnell
bfl/flux-fill: black-forest-labs/flux-fill-pro
bfl/flux-redux: black-forest-labs/flux-redux-schnell
stability/sdxl: stability-ai/sdxl
stability/sd3.5-large: stability-ai/stable-diffusion-3.5-large
stability/sd3.5-large-turbo: stability-ai/stable-diffusion-3.5-large-turbo
openai/whisper-large-v3: openai/whisper
stability/stable-audio-2: stackadoc/stable-audio-open-1.0
```

**24% coverage** of our 51 active specialist rows; the rest are direct-only on Replicate (no Runway, Kling, Recraft, ElevenLabs, Suno, etc. on Replicate per Pass 2 mirror-map audit).

**Fetcher behavior**:

1. For each mirror entry, `GET https://replicate.com/{slug}` with `User-Agent: fabrik-pricing-fetcher/1`.
2. Parse the HTML for `<script id="react-component-props-*" type="application/json">` blobs, JSON-parse each.
3. Extract `billingConfig.current_tiers[0].prices[]` — each entry has `price` (string `"$0.04"`), `metric` (`"image_output_count"` etc.), `type` (`"per-unit"` / `"per-second"`).
4. Normalize to our `$/M-billable-units` axis (matches existing pricing_unit conversions).
5. Merge into `agents.gateway_prices` JSON: `{"replicate": {"price": <normalized>, "unit": "image", "slug": "<replicate-slug>", "url": "<replicate-url>", "last_seen": "2026-06-29"}}`.
6. Cache raw HTML at `cache/replicate_<owner>__<model>.html` (mirror of `cache/arena_raw.html` pattern); skip refetch if cache <24h.

**Resilience contract** (per [.windsurf/rules/core/58-resilience.md:45-86](../../../.windsurf/rules/core/58-resilience.md#L45-L86)): explicit `httpx.Timeout(connect=5, read=30, write=10, pool=5)`, `tenacity.retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))`, retry only on 5xx + timeout (not 4xx). Circuit-breaker scoped per-host (Replicate).

**Auth + env**: `REPLICATE_API_TOKEN` (only needed for `/v1/models/*` API discovery, not the HTML scrape). Documented in `/opt/fabrik/.env.example`; key copied from `/opt/brand-identiy-creator/.env` (no cross-project loading at runtime — Pass 2 found no precedent for that pattern).

**Legal** (per Pass 3a): `https://replicate.com/robots.txt` allows all. ToS clause targets PII + model outputs, not pricing. Custom User-Agent fine. Cache headers are `DYNAMIC` per-user; daily scrape is low-overhead.

**Validation gate**:

```bash
REPLICATE_API_TOKEN=<from-env> .venv/bin/python scripts/kilo-benchmarks/fetch_replicate_prices.py --dry-run
sqlite3 scripts/kilo-benchmarks/kilo_agents.db \
  "SELECT count(*) FROM agents WHERE json_extract(gateway_prices, '$.replicate') IS NOT NULL"
```

Expected: `>=10` (allows 2 slot losses if Replicate transiently 5xx's). Then the per-row JSON sanity: `sqlite3 ... "SELECT id, json_extract(gateway_prices, '$.replicate.price') FROM agents WHERE id='bfl/flux-pro-1.1'"` → numeric value matching `(BFL direct price ± 50%)`. **Then run the adversarial review per [§ Adversarial review](#adversarial-review-mandatory-after-each-phase).**

### Phase 2 — fal.ai fetcher

New script: `scripts/kilo-benchmarks/fetch_fal_prices.py`. **True API consumer** (Pass 2 confirmed `GET https://fal.ai/api/models` with `Authorization: Key $FAL_KEY` returns paginated catalog; 1399 models across 35 pages × 40).

**Algorithm**:

1. Paginate `https://fal.ai/api/models?page=N` with `Authorization: Key $FAL_KEY`. Throttle 0.5s between pages (Pass 2 sampled 5 pages with no 429s).
2. For each model, extract `id`, `pricingInfoOverride` (Markdown).
3. Parse Markdown using regex spec from Pass 2 (7 categories; `**$X.YZ**` pattern, optional unit suffix). Confidence flag where < 2 rules match.
4. Map fal.ai id → our `agents.id` via `scripts/kilo-benchmarks/fal_mirrors.yaml` (drafted from Pass 2 sample; coverage ~58% per Pass 2; 42% null `pricingInfoOverride` flagged for manual review).
5. Merge into `agents.gateway_prices`: `{"fal_ai": {"price": <normalized>, "unit": "image"|"video-sec"|..., "slug": "fal-ai/flux/schnell", "url": "https://fal.run/...", "last_seen": "...", "confidence": 1.0}}`.

**Parser spec** (excerpt; full in repo):

| Category | Detection regex | Extraction |
|---|---|---|
| per-image | `per\s+image` | `\*\*\$([\d.]+)\*\*` × 1M → `pricing_unit=image` |
| per-megapixel | `(?:per\s+)?megapixel\|MP` | `\*\*\$([\d.]+)\*\*` × 1M; flag tiered if "first"/"extra" present |
| per-second | `per\s+second\|/s` | `\*\*\$([\d.]+)\*\*` × 1M → `pricing_unit=video-sec`; resolution tier if matched |
| per-minute | `per\s+minute` | `\*\*\$([\d.]+)\*\*` × 1M / 60 → `pricing_unit=audio-min` |
| per-token | `tokens?.*\(per\s+(\d+)([MK])?\)` | parse 1M / 1K denom → `pricing_unit=M-tokens` |
| multi-tier | brackets `(\$[\d.]+).*?\((\d+(?:MP\|p))\)` | dict keyed by tier; pick smallest as default |
| null | — | flag `confidence=0`, store `raw_text` only |

**Resilience contract**: same as Phase 1.

**Validation gate**:

```bash
FAL_KEY=<from-env> .venv/bin/python scripts/kilo-benchmarks/fetch_fal_prices.py --dry-run
sqlite3 scripts/kilo-benchmarks/kilo_agents.db \
  "SELECT count(*) FROM agents WHERE json_extract(gateway_prices, '$.fal_ai') IS NOT NULL"
```

Expected: `>=8` (covers FLUX variants + LTX video + Whisper + Stable Audio). Per-row: `sqlite3 ... "SELECT id, json_extract(gateway_prices, '$.fal_ai.confidence') FROM agents WHERE json_extract(gateway_prices, '$.fal_ai') IS NOT NULL"` → confidence ≥ 0.5 for ≥80% of rows. **Then run the adversarial review per [§ Adversarial review](#adversarial-review-mandatory-after-each-phase).**

### Phase 3 — Cheapest-gateway derivation

New script: `scripts/kilo-benchmarks/derive_cheapest_gateway.py`.

**Algorithm**:

1. For each row with non-null `gateway_prices`, parse the JSON.
2. Compute `min(price)` across all keys (direct + replicate + fal_ai + ...) and identify the gateway.
3. Write `cheapest_gateway` (name) + `cheapest_gateway_price` (numeric, same `input_cost_per_m` axis).

**SQLite JSON1 confirmed** (Pass 1: `SELECT json_extract('{"a":1}', '$.a')` returns `1`). EXPLAIN QUERY PLAN shows `SCAN agents` (Pass 4) — full-table scan, acceptable at 50 rows; document add-index threshold at ~50k.

**Validation gate**:

```bash
.venv/bin/python scripts/kilo-benchmarks/derive_cheapest_gateway.py
sqlite3 scripts/kilo-benchmarks/kilo_agents.db \
  "SELECT id, cheapest_gateway, cheapest_gateway_price FROM agents WHERE cheapest_gateway IS NOT NULL ORDER BY cheapest_gateway_price LIMIT 5"
```

Expected: top-5 cheapest rows visible with consistent gateway names + monotonically increasing prices. **Then run the adversarial review per [§ Adversarial review](#adversarial-review-mandatory-after-each-phase).**

### Phase 4 — Browser surfacing

[scripts/kilo-benchmarks/models_browser_template.html](../../../scripts/kilo-benchmarks/models_browser_template.html) changes:

**4a. Extend `fmtSource(m)`** at [line 833-850](../../../scripts/kilo-benchmarks/models_browser_template.html#L833-L850) to add 4 gateway badges (Pass 4 colors):

```css
td.source .src-badge.replicate { background: #2a1f3a; border-color: #7a4fa0; color: #e8c0ff; }
td.source .src-badge.fal       { background: #3a2420; border-color: #a05030; color: #ffb080; }
td.source .src-badge.together  { background: #1a3a2a; border-color: #2a7a5a; color: #80e0c0; }
td.source .src-badge.fireworks { background: #3a3020; border-color: #a08040; color: #f0d080; }
```

JS extension reads `m.gateway_prices` JSON (already in payload via `SELECT *` in [export_models_browser.py:38](../../../scripts/kilo-benchmarks/export_models_browser.py#L38)) and emits one badge per non-null gateway entry.

**4b. Cheapest-gateway badge** in the Price cell. Append to `fmtCost(v, m)` ([line 872-905](../../../scripts/kilo-benchmarks/models_browser_template.html#L872-L905)):

```js
if (m.cheapest_gateway && m.cheapest_gateway_price < v) {
  const savings = Math.round((v - m.cheapest_gateway_price) / v * 100);
  return baseCost + `<span class="cheaper-badge" title="${savings}% cheaper via ${m.cheapest_gateway}">via ${m.cheapest_gateway}</span>`;
}
```

**4c. Source/gateway sidebar chips** ([line 369-381](../../../scripts/kilo-benchmarks/models_browser_template.html#L369-L381)) gain `replicate_cheaper` and `fal_cheaper` chips alongside existing `kilo_cheaper` / `or_cheaper`.

**4d. Sort interaction trade-off** (Pass 4 §6): tab switch resets sort to `TAB_DEFAULTS[tab].sortKey` ([line 712-724](../../../scripts/kilo-benchmarks/models_browser_template.html#L712-L724)). **Option A** (simpler) — keep current behavior; tooltip the chip with "Switching tabs resets sort." **Option B** — preserve user sort across tab switch via `lastUserSort` global. **Recommendation: Option A** for this phase; revisit if operators complain.

**Validation gate**:

```bash
.venv/bin/python scripts/kilo-benchmarks/export_models_browser.py
grep -c "src-badge replicate\|src-badge fal" scripts/kilo-benchmarks/models_browser.html
```

Expected: `>=8` badge renders (at least 4 Replicate + 4 fal). Plus manual: open the file in a browser, click Image tab, confirm cheapest-gateway badges visible on FLUX rows. **Then run the adversarial review per [§ Adversarial review](#adversarial-review-mandatory-after-each-phase).**

### Phase 5 — Pipeline wiring

**[scripts/kilo-benchmarks/daily_refresh.sh](../../../scripts/kilo-benchmarks/daily_refresh.sh)** — insert AFTER `seed_direct_vendors.py` (line 79) and BEFORE `category_export_markdown.py` (line 91):

```bash
"$VENV_PY" "$KB/fetch_replicate_prices.py" \
  || echo "[daily_refresh] replicate price fetch failed (non-fatal)"
[ -n "${FAL_KEY:-}" ] && "$VENV_PY" "$KB/fetch_fal_prices.py" \
  || echo "[daily_refresh] fal price fetch failed (non-fatal)"
"$VENV_PY" "$KB/derive_cheapest_gateway.py" \
  || echo "[daily_refresh] cheapest gateway derive failed (non-fatal)"
```

**[scripts/wsl_startup_hook.sh](../../../scripts/wsl_startup_hook.sh)** — same three lines inside the openrouter-routing subshell (line 133-144 per Pass 1). Both files MUST be updated in sync (Pass 1 §2: the boot path runs the pipeline inline, not via shelling out).

**Validation gate**:

```bash
bash -n scripts/kilo-benchmarks/daily_refresh.sh && bash -n scripts/wsl_startup_hook.sh
grep -c "fetch_replicate_prices\|fetch_fal_prices\|derive_cheapest_gateway" \
  scripts/kilo-benchmarks/daily_refresh.sh scripts/wsl_startup_hook.sh
```

Expected: shell-parse-clean exit 0; grep count `>=6` (3 per file × 2 files). **Then run the adversarial review per [§ Adversarial review](#adversarial-review-mandatory-after-each-phase).**

## Adversarial review (mandatory after each Phase)

After every Phase's validation gate passes, the implementer **MUST** run the adversarial review below as a single-turn task before moving to the next Phase. The review is a gate: a Phase is not "done" until the review reaches a demonstrably-thorough empty pass on correctness/security findings (style findings may be deferred). Each review's verbatim findings + fixes are appended to a per-Phase review file at `docs/development/reviews/2026-06-29-aggregator-pricing-phase-<N>-review.md` (mirror the format of [scripts/enforcement/check_convergence.py:101-119](../../../scripts/enforcement/check_convergence.py#L101-L119) — the file must embed a verbatim `final_gate.py --json` `"status":"success"` block + a per-Phase verdict).

### The review prompt (run verbatim)

> Review this implementation as an adversary trying to break it. Scope: the full changed surface plus everything it calls or is called by. Run repeated review passes in this single turn.
>
> Each pass, hunt specific failure classes: logic errors, off-by-one, null/empty/None handling, idempotency, effective-dating/ordering, fail-open vs fail-closed, error/edge paths, concurrency & transaction atomicity, resource cleanup, auth/tenant-isolation, precision/timezone/encoding, and plan↔code deviations (verify against the spec's intent, since the written spec can itself be wrong).
>
> Prove before you fix: for each suspected bug, reproduce it with a runnable test or execution; then fix it and keep the test as a regression guard. Classify each finding as correctness/security vs. style.
>
> After each pass, show what you inspected (which files/paths, which failure classes) and what you found. A pass that finds nothing must still enumerate that coverage — an empty pass with no evidence of what was checked does not count. Do not stop or claim convergence until one demonstrably thorough pass produces zero new correctness/security findings.
>
> A green final_gate is necessary but not sufficient (it doesn't test logic), so never treat it as proof of correctness — and re-run it after each fix, since fixes regress. When unsure whether something is a bug, surface it rather than assume it's fine. If anything can't be made truly zero-risk, list the residual risks explicitly.

### Per-Phase scoping hints (what "full changed surface" means)

| Phase | In-scope surface for the review | Specific failure classes to hunt |
|---|---|---|
| 0 | `migrate_aggregator_columns.py`, `agents` schema, `test_category_selector.py::_make_db` | idempotency on re-run; type coercion (TEXT vs JSON); migration ordering vs the existing `migrate_selector_columns.py` |
| 0.5 | `kilo_agents_db.py:240-241` fix, the 13-row historical data, every consumer of `kilo_input_cost_per_m` | data correction precision; off-by-power-of-ten on rows whose prior values were ALREADY correct; concurrency between fix UPDATE and ingest |
| 1 | `fetch_replicate_prices.py`, `replicate_mirrors.yaml`, cache files, `gateway_prices` JSON shape, browser payload | HTML scrape parse drift (Next.js hydration changes); cache poisoning on 5xx; race between fetcher and `derive_cheapest_gateway.py`; cents-vs-dollars unit confusion; per-second vs per-image metric handling |
| 2 | `fetch_fal_prices.py`, parser regexes, `fal_mirrors.yaml`, pagination | regex false positives (bold prices in unrelated context); pagination cursor drift; null `pricingInfoOverride` mis-categorized as $0; mojibake on Markdown emojis |
| 3 | `derive_cheapest_gateway.py`, JSON1 query | min-of-empty-set bug; mixing pricing_unit values (comparing $/img to $/sec); precision loss on REAL arithmetic; tie-break ordering |
| 4 | `models_browser_template.html` JS (fmtSource, fmtCost, filter chips), CSS additions, `export_models_browser.py` payload shape | XSS in `gateway_prices` JSON values (escape user-influenced gateway slugs/URLs); sort regression when cheapest_gateway_price is null; badge over-count when a row has 5+ gateways; tab-switch sort-reset interaction |
| 5 | `daily_refresh.sh`, `wsl_startup_hook.sh`, cron/boot env loading | step-order regression (fetcher running AFTER derivation); env-var inheritance (missing key silently disables fetch); lockfile races between boot and cron; non-fatal error pattern actually suppressing real errors |

### Definition of "demonstrably-thorough empty pass"

A pass must list, in writing:

1. Files / paths read (with line ranges).
2. Failure classes hunted (from the list above + Phase-specific).
3. For each class: the concrete check performed and its result.

A pass that says "looked clean" with no enumeration **does not** satisfy this gate.

### Closing out a Phase

Phase N is closed only when:

- `final_gate.py --lean --json` → `"status":"success"` (re-run after every fix).
- The per-Phase review file exists at `docs/development/reviews/...-phase-<N>-review.md` with the verbatim final-gate JSON embedded + per-Phase verdict.
- `check_convergence.py` exits 0 against the review file.

If any of those three fail, the Phase is not done — continue iterating.

## Evidence

### Phase 0 Evidence (schema migration)

**path:line**:

- [scripts/kilo-benchmarks/migrate_selector_columns.py:55-65](../../../scripts/kilo-benchmarks/migrate_selector_columns.py#L55-L65) — `_column_exists()` + `_ensure_column()` pattern to mirror.
- [tests/kilo_benchmarks/test_category_selector.py:40-63](../../../tests/kilo_benchmarks/test_category_selector.py#L40-L63) — `_make_db()` synthetic schema needs 3 column additions.

**Command output** (verbatim 2026-06-29):

```text
$ sqlite3 scripts/kilo-benchmarks/kilo_agents.db "SELECT count(*) FROM pragma_table_info('agents') WHERE name IN ('gateway_prices','cheapest_gateway','cheapest_gateway_price')"
0

$ sqlite3 :memory: "SELECT json_extract('{\"a\":1}', '$.a')"
1
```

**Verdict**: 3 target columns don't exist (idempotent-safe). JSON1 is compiled in.

### Phase 0.5 Evidence (kilo bug fix)

**path:line**:

- [scripts/kilo-benchmarks/kilo_agents_db.py:240-241](../../../scripts/kilo-benchmarks/kilo_agents_db.py#L240-L241) — the buggy `* 1_000_000`.
- [scripts/kilo-benchmarks/verify_openrouter_catalog.py:147-148](../../../scripts/kilo-benchmarks/verify_openrouter_catalog.py#L147-L148) — correct comment: "already scaled".

**Command output**:

```text
$ sqlite3 scripts/kilo-benchmarks/kilo_agents.db "SELECT id, input_cost_per_m, kilo_input_cost_per_m FROM agents WHERE via_kilo=1 AND kilo_input_cost_per_m < input_cost_per_m / 1000 LIMIT 3"
mistralai/devstral-2512|0.4|4e-07
openai/gpt-5-chat|1.25|1.25e-06
kilo-auto/frontier|5.0|5e-06
```

**Verdict**: 13 rows affected by 1,000,000× decimal-shift bug. Fix is one-line removal of `* 1_000_000`; no test depends on these values (Pass 3c).

### Phase 1 Evidence (Replicate fetcher)

**path:line**:

- [scripts/kilo-benchmarks/seed_direct_vendors.py:79-94](../../../scripts/kilo-benchmarks/seed_direct_vendors.py#L79-L94) — data-source disclosure being supplemented.
- [scripts/kilo-benchmarks/scrape_benchmarks.py:52-94](../../../scripts/kilo-benchmarks/scrape_benchmarks.py#L52-L94) — `@retry_on_network_error` decorator + `requests.get(timeout=30)` pattern to mirror.
- [.windsurf/rules/core/58-resilience.md:45-86](../../../.windsurf/rules/core/58-resilience.md#L45-L86) — timeout / retry / circuit-breaker contract.

**Command output** — Replicate API disproof + HTML proof:

```text
$ curl -s -H "Authorization: Token $REPLICATE_API_TOKEN" \
    "https://api.replicate.com/v1/models/black-forest-labs/flux-1.1-pro" | jq 'keys'
["cover_image_url","created_at","default_example","description","github_url","is_official","latest_version","license_url","name","owner","paper_url","run_count","url","visibility","weights_url"]
# → no "price", no "billingConfig"

$ curl -s "https://replicate.com/black-forest-labs/flux-1.1-pro" | \
    grep -o '"billingConfig":[^}]*"prices":[^]]*' | head -c 300
"billingConfig": {"current_description": null, "current_tiers": [{"criteria": [], "description": null, "prices": [{"description": "or 25 images for $1", "metric": "image_output_count", "metric_display": "output image", "price": "$0.04", "title": "per output image", "type": "per-unit"}
```

```text
$ curl -s https://replicate.com/robots.txt
User-agent: *
Allow: /

$ ratelimit-remaining: 2999 (per minute)
```

```text
# 12 mirror slugs all verified (Pass 3a):
HTTP 200 for: black-forest-labs/flux-1.1-pro, .../flux-1.1-pro-ultra, .../flux-pro, .../flux-dev,
              .../flux-schnell, .../flux-fill-pro, .../flux-redux-schnell,
              stability-ai/sdxl, .../stable-diffusion-3.5-large, .../stable-diffusion-3.5-large-turbo,
              openai/whisper, stackadoc/stable-audio-open-1.0
billingConfig present in HTML for all 12.
```

**Verdict**: API has no price → HTML scrape via React-component JSON is the only repeatable path. 12 verified mirrors (24% of 51 candidates). ToS allows it. Rate limit not a constraint.

### Phase 2 Evidence (fal.ai fetcher)

**path:line**:

- (no existing fal.ai consumer — new code path).
- [.windsurf/rules/core/58-resilience.md:45-86](../../../.windsurf/rules/core/58-resilience.md#L45-L86) — same resilience contract.

**Command output** — fal.ai catalog probe:

```text
$ curl -s -H "Authorization: Key $FAL_KEY" "https://fal.ai/api/models?page=1" | jq '.items[0] | {id, pricingInfoOverride}'
{
  "id": "fal-ai/nano-banana-2/edit",
  "pricingInfoOverride": "Your request will cost **$0.08** per image. For **$1.00**, you can run this model **12** times. 2K and 4K outputs will be charged at **1.5** times and **2** times the standard rate..."
}

$ curl -s -H "Authorization: Key $FAL_KEY" "https://fal.ai/api/models" | jq '.totalItems, .totalPages'
1399
35

# Parser categories observed (5-page sample, 200 models):
# per-image: 13%, per-megapixel: 10%, per-second: 31%, multi-resolution: 10%,
# per-minute: 0.9%, per-token: rare, null/other: 42%
```

**Verdict**: API consumer path validated. ~58% pricingInfoOverride coverage; 42% null fallback; parser spec spans 7 categories.

### Phase 3 Evidence (cheapest-gateway derivation)

**path:line**:

- [models_browser_template.html:823-824](../../../scripts/kilo-benchmarks/models_browser_template.html#L823-L824) — existing "kilo_cheaper" / "or_cheaper" predicate at render time (the pattern we mirror).
- [models_browser_template.html:840-848](../../../scripts/kilo-benchmarks/models_browser_template.html#L840-L848) — existing percent-markup badge formula.

**Command output**:

```text
$ sqlite3 scripts/kilo-benchmarks/kilo_agents.db \
    "EXPLAIN QUERY PLAN SELECT id FROM agents WHERE json_extract(translation_quality, '$.tr') > 80"
QUERY PLAN
`--SCAN agents
```

**Verdict**: JSON1 query is SCAN at our size (50 rows; full-scan acceptable). The OR↔Kilo decision-at-render-time pattern is mirrorable to N gateways with the same shape.

### Phase 4 Evidence (browser surfacing)

**path:line**:

- [models_browser_template.html:242-245](../../../scripts/kilo-benchmarks/models_browser_template.html#L242-L245) — existing `.src-badge.or/.kilo/.ds/.sf` CSS to extend.
- [models_browser_template.html:833-850](../../../scripts/kilo-benchmarks/models_browser_template.html#L833-L850) — `fmtSource(m)` to extend.
- [models_browser_template.html:872-905](../../../scripts/kilo-benchmarks/models_browser_template.html#L872-L905) — `fmtCost(v, m)` to extend.
- [models_browser_template.html:684-694](../../../scripts/kilo-benchmarks/models_browser_template.html#L684-L694) — `TAB_DEFAULTS` sort interaction (Option A: tab default resets sort).
- [export_models_browser.py:38](../../../scripts/kilo-benchmarks/export_models_browser.py#L38) — `SELECT *` means new columns flow into payload automatically; no template-side parse changes beyond `gateway_prices` JSON.

**Command output**:

```text
$ grep -c "src-badge" scripts/kilo-benchmarks/models_browser_template.html
17
# (existing OR/K/DS/SF badge classes; 4 new will bring it to 21)
```

**Verdict**: Mirror existing CSS palette + the 4 proposed badge colors are visually distinct (mauve / coral-orange / teal-green / gold).

### Phase 5 Evidence (pipeline wiring)

**path:line**:

- [scripts/kilo-benchmarks/daily_refresh.sh:79](../../../scripts/kilo-benchmarks/daily_refresh.sh#L79) — `seed_direct_vendors.py` slot (fetchers go after).
- [scripts/kilo-benchmarks/daily_refresh.sh:91](../../../scripts/kilo-benchmarks/daily_refresh.sh#L91) — `category_export_markdown.py` slot (derivation goes before).
- [scripts/wsl_startup_hook.sh:133-144](../../../scripts/wsl_startup_hook.sh#L133-L144) — boot-path inline pipeline (NOT a shell-out to daily_refresh.sh) — both files must be updated in sync.

**Command output**:

```text
$ grep -nE 'VENV_PY.*KB' scripts/kilo-benchmarks/daily_refresh.sh
46:  "$VENV_PY" "$KB/verify_openrouter_catalog.py" --apply --ingest-new \
51:  "$VENV_PY" "$KB/migrate_selector_columns.py" \
65:  "$VENV_PY" "$KB/scrape_coding_benchmarks.py" \
72:  "$VENV_PY" "$KB/seed_translation_and_stt.py" \
79:  "$VENV_PY" "$KB/seed_direct_vendors.py" \
82:  "$VENV_PY" "$KB/derive_quality_v2.py" \
85:  "$VENV_PY" "$KB/classify_ai_category.py" \
88:  "$VENV_PY" "$KB/category_route_mapper.py" \
91:  "$VENV_PY" "$KB/category_export_markdown.py" \
99:  "$VENV_PY" "$KB/update_gateway_counts.py" \
102: "$VENV_PY" "$KB/export_models_browser.py" \
```

**Verdict**: Insertion slot is rows 80-90 (between `seed_direct_vendors.py` and `category_export_markdown.py`). Both pipeline files must be updated together.

## Self-audit / convergence floor

This plan was iterated through 4 grounding passes (10+ Explore subagents, ~15 verified path:line citations, ~12 captured command-output blocks). The audit:

- ✅ **Phase 0 schema** grounded — column-add pattern from existing migration script, JSON1 confirmed.
- ✅ **Phase 0.5 bug fix** grounded — exact buggy line cited, fix verified to not break tests (Pass 3b/3c).
- ✅ **Phase 1 Replicate** grounded — API DISPROVEN, HTML React-JSON proven, 12 mirrors HTTP-200 verified, ToS allows.
- ✅ **Phase 2 fal.ai** grounded — API proven, parser spec spans 7 categories from real samples.
- ✅ **Phase 3 derivation** grounded — JSON1 query plan acceptable at our scale; mirrors existing render-time decision pattern.
- ✅ **Phase 4 browser** grounded — extension points + CSS palette specified; tab sort trade-off documented.
- ✅ **Phase 5 pipeline** grounded — slot identified in both daily_refresh.sh AND wsl_startup_hook.sh.
- ✅ **Resilience contract** grounded against `core/58-resilience.md`.
- ✅ **Test impact** grounded — only `test_category_selector.py::_make_db` needs 3 column additions.

**Validation gate evidence**: every Phase has a runnable command + expected result above. Phase 0 + 0.5 gates can be executed today against the live DB; Phase 1-5 gates execute after the corresponding implementation.

## Residual risks (explicit, post-grounding)

1. **Replicate HTML scrape fragility**: Next.js hydration changes could break the `react-component-props` parse. Mitigation: cache previous parse + alert on schema drift in fetcher.
2. **Replicate coverage 24%** (12 of 51 specialist rows). The rest (Runway, Kling, Luma, Recraft, ElevenLabs, Suno, etc.) stay direct-only — operator's existing pricing remains canonical. Plan does not promise universal coverage.
3. **fal.ai null pricingInfoOverride 42%** — these need manual operator entry or rely on `billingMessage` fallback. The fetcher writes confidence=0 for these and they don't drive the cheapest-gateway badge.
4. **Tab sort UX trade-off (Option A)**: switching tabs resets sort. Documented in chip tooltip. May need Option B if operators complain (preserve `lastUserSort` across tab switch).
5. **JSON1 full-scan**: acceptable at 50 rows. Document add-index threshold at 50k.
6. **Cross-project token discovery**: `REPLICATE_API_TOKEN` currently lives in `/opt/brand-identiy-creator/.env`. Plan requires copying to `/opt/fabrik/.env`; if operator forgets, Phase 1 fetcher fails with a clear `[daily_refresh] replicate price fetch failed (non-fatal)` log entry — pipeline survives.
7. **Existing kilo decimal-shift bug** (Phase 0.5): historical kilo_input_cost_per_m values are off by 1e6 for 13 rows. Plan fixes this as prerequisite. If skipped, the OR↔Kilo "cheaper" badge already in the browser remains misleading.
8. **fal.ai parser confidence**: regex extraction across 7 categories; flagged-confidence rows visible in the cheapest-gateway computation but not driving badges if confidence < 0.5.
9. **Out of scope** (Phase 6+): TogetherAI / Fireworks / HF Inference for LLM rows; OpenRouter for Google + OpenAI image-gen coverage (would lift Replicate's 24% closer to plan's original "~30").

## References

- Predecessor plan (LLM-side OR↔Kilo): [docs/development/plans/2026-06-27-plan-openrouter-routing.md](2026-06-27-plan-openrouter-routing.md).
- Convergence contract: [scripts/enforcement/check_convergence.py:33-49](../../../scripts/enforcement/check_convergence.py#L33-L49).
- Prompt templates: [docs/reference/convergence-prompts.md](../../reference/convergence-prompts.md).
