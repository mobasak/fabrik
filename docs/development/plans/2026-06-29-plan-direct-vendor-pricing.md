---
Status: DRAFT (v3)
Owner: ozgur
Created: 2026-06-29
Last revised: 2026-06-29 (v3 — switched to existing `browserless` on vps1 for JS rendering; dropped Crawl4AI/Firecrawl; fabrik-lib module is a thin browserless client)
---

## Revision history

- **v1** — Per-vendor `requests` + Firecrawl free for 4 heavy-JS vendors. Rejected: Firecrawl credit cap risk + external dependency.
- **v2** — Crawl4AI inside a `fabrik-lib/web-scrape/` Python module. Rejected: would add Chromium (~120MB) + Crawl4AI to every consumer project, and we already pay 2GB RAM for `browserless` on vps1.
- **v3 (current)** — Use the **existing `browserless` container** on vps1 ([docs/infrastructure/vps-complete-inventory.md:124](../../infrastructure/vps-complete-inventory.md#L124) — Headless Chrome HTTP API at `browser.vps1.ocoron.com`). `fabrik-lib/web-scrape/` becomes a thin HTTP client (httpx + bs4 + a Next.js hydration parser). Zero new infra. Zero new heavyweight deps in `.venv`. Reusable across all Fabrik projects via the same mesh-or-public endpoint.

# Direct-vendor pricing & status — complete daily refresh

## Problem

The AI Models Browser carries **96 direct-vendor rows across 28 providers** in [scripts/kilo-benchmarks/seed_direct_vendors.py:1](../../../scripts/kilo-benchmarks/seed_direct_vendors.py#L1) whose `input_cost_per_m`, `status`, `name`, and `description` are **hardcoded** in the `VENDORS` dict (operator-encoded from training-data knowledge — disclosed at [seed_direct_vendors.py:79-94](../../../scripts/kilo-benchmarks/seed_direct_vendors.py#L79-L94)). The daily pipeline at [daily_refresh.sh:114](../../../scripts/kilo-benchmarks/daily_refresh.sh#L114) re-runs the seeder daily, but that just re-asserts the same hardcoded values. There is no automated price refresh, no automated EOL detection.

Consequences:
1. **Price drift goes silent** — if ElevenLabs raises Multilingual v2 from $0.30/1K to $0.35/1K chars, the catalog shows the old price until someone manually edits `seed_direct_vendors.py`.
2. **EOL goes silent** — `verify_openrouter_catalog.py --apply` ([verify_openrouter_catalog.py:486-492](../../../scripts/kilo-benchmarks/verify_openrouter_catalog.py#L486-L492)) only flips OpenRouter-routed rows to `deprecated`. Direct-vendor rows (Soniox, ElevenLabs, AssemblyAI, Coqui, etc.) have no equivalent check.
3. **Operator distrust of the browser** — the Status / Verified tooltips at [models_browser_template.html:519](../../../scripts/kilo-benchmarks/models_browser_template.html#L519) now explicitly document this gap (committed `7addc7da`), but documenting a gap is not the same as closing it.

Scope: 96 rows / 28 providers / 8 service types — exact distribution in §Inventory.

## Goal

Every direct-vendor row's `input_cost_per_m`, `pricing_unit`, and `status` are refreshed from the vendor's authoritative source daily via `daily_refresh.sh`. Price diffs > 10% emit a Telegram alert. Rows missing from a vendor's catalog for 7 consecutive days flip to `status='deprecated'`. Idempotent: re-running with the same source HTML produces the same DB writes.

Out of scope (call out, don't pretend):
- **Routing decisions** — this plan refreshes the catalog; selectors stay as-is.
- **Subscription / credit vendors** (Suno, Udio, HeyGen, Pika) — no per-call pricing to scrape; we'll detect catalog presence only (status), not price. Document that gap in the Status tooltip.
- **The 20 `provider='unknown'` LLM rows** — separate puzzle (Kilo-only specialty LLMs where seed didn't populate provider). Handled in Phase 4 but tracked as its own deliverable.
- **Description / capability flips** — vendors changing model descriptions are too noisy to track automatically; manual quarterly review stays the source of truth.

## Inventory

```
service_type   rows
image_gen      25
llm            20  (← 20 provider='unknown'; Phase 4)
tts            13
video_gen      12
stt            11
translation     6
ocr             5
music_gen       4
TOTAL          96
```

Provider distribution: 28 distinct providers; top 8 cover 60 rows: `openai=10, google=8, bfl=7, recraft=6, stability=6, elevenlabs=5, azure=4, runway=3`. Long tail of single-row providers (cartesia, coqui, heygen, llamaindex, mistral, pika, qwen, speechmatics — 8 providers × 1 row each).

Full inventory query:
```sql
SELECT provider, service_type, id, input_cost_per_m, pricing_unit, status
FROM agents WHERE via_openrouter=0 AND via_kilo=0 ORDER BY provider, id;
```

## Fetch infrastructure (post-v3)

**Two fetch methods only**, both routed through `fabrik-lib/web-scrape/`:

1. `fetch_static(url)` — `httpx.get` for pages that ship server-rendered HTML or carry data in `__NEXT_DATA__` script tags. Used for ~24 of 28 vendors.
2. `fetch_rendered(url)` — POST to **vps1 `browserless`** (`https://browser.vps1.ocoron.com/content` with `{"url": ...}`). Returns fully-rendered HTML after JS execution. Used for the ~4 heavy-JS vendors (HeyGen, Pika, Suno, Udio) and any vendor Phase 0 grounding finds needs JS.

Both methods share one cache layer (per-vendor JSON under `cache/direct_vendor_<vendor>.{html,json}`), one retry policy, and one robots.txt check. The orchestrator calls only the high-level methods; vendor parsers never touch the network.

Existing pattern references: [fetch_replicate_prices.py:1-22](../../../scripts/kilo-benchmarks/fetch_replicate_prices.py#L1-L22) (Next.js hydration scrape). [scrape_artificial_analysis.py:1-21](../../../scripts/kilo-benchmarks/scrape_artificial_analysis.py#L1-L21) (HTTP fetch + cache + match).

**Browserless capacity check** (confirm during Phase 0, but here's the napkin math):
- 28 vendors × 1 call/day → ~30 browserless requests/day
- Vps1 `browserless` is sized 2GB RAM, idle (currently consumed only by ad-hoc Gotenberg-style PDFs and n8n flows)
- One browserless `/content` call ≈ 2-4s wall-clock with cold Chromium pool; ≈ 0.5s warm
- Per-day overhead: ~30 × 3s = 90s of Chromium time — negligible
- No new infra to deploy; we're using a service we already pay 2GB RAM for

Initial fetch-method tiering (Phase 0 will verify each by grounding the actual vendor URLs):

| Tier | Count | Vendors | Method | Per-vendor effort |
|---|---|---|---|---|
| **JSON API** | 5 | google-cloud, azure, aws, deepl, openai | Direct API/SDK (boto3 etc.) | 0.5d |
| **Next.js hydration** | 10 | anthropic, elevenlabs, stability, bfl, recraft, cartesia, ideogram, runway, luma, kling | `fetch_static` + parse `__NEXT_DATA__` | 0.5d |
| **Static HTML** | 9 | assemblyai, deepgram, speechmatics, soniox, playht, coqui (HuggingFace), llamaindex, mistral, qwen | `fetch_static` + bs4 selectors | 0.5d |
| **Heavy JS via browserless** | 4 | heygen, pika, suno, udio | `fetch_rendered` (vps1 browserless) | 0.5d |
| **Subscription only — status detection only** | (subset of above) | suno, udio, heygen, pika | No per-call pricing; only verify model still listed | included in their tier |

Phase 0 grounds these tiers per vendor — assigned method may shift based on actual page structure.

## Architecture

**Two layers, clean separation:**

```
fabrik-lib/web-scrape/                           ← reusable, vendored by any project
  webscrape.py
    fetch_static(url, **kw) -> str               (httpx, no JS)
    fetch_rendered(url, **kw) -> str             (POST browserless /content)
    extract_nextjs_data(html) -> dict            (parses __NEXT_DATA__)
    extract_apollo_state(html) -> dict           (parses Apollo SSR cache)
    cache_get(key) / cache_put(key, content)     (file-cache TTL)
    + ROBOTS.txt check, retries, alerting hook

scripts/kilo-benchmarks/
  fetch_direct_vendor_prices.py                  ← THIS PLAN'S DELIVERABLE — consumer of fabrik-lib/web-scrape
  direct_vendor_pricing_registry.yaml            ← per-vendor URL + parser + expected unit
  direct_vendor_parsers/
    elevenlabs.py     extract(content) -> [ParsedRow]
    soniox.py         extract(content) -> [ParsedRow]
    ... (28 modules total, each ~30 lines, pure function, no I/O)
```

The orchestrator owns: registry parsing, fetch dispatch, validation, DB merge, alerting. The parsers own: just transforming `content` (HTML/JSON dict) into `[ParsedRow]`. The fabrik-lib module owns: HTTP, caching, JS rendering, robots.txt — completely reusable for any future project.

**Orchestrator** — `scripts/kilo-benchmarks/fetch_direct_vendor_prices.py`:
- Reads registry YAML
- For each vendor: `fabrik_lib.webscrape.fetch_*` → invoke parser → validate → DB merge
- Atomic: SQLite transaction per vendor; rollback on parser exception
- Cache layer lives in fabrik-lib (file-cache module already exists); orchestrator just passes a cache dir

**Registry** — `scripts/kilo-benchmarks/direct_vendor_pricing_registry.yaml`:
```yaml
elevenlabs:
  pricing_url: https://elevenlabs.io/pricing
  fetch_method: nextjs_hydration   # | static_html | json_api | firecrawl
  parser_module: direct_vendor_parsers.elevenlabs
  models:
    elevenlabs/multilingual-v2:
      slug_on_page: multilingual_v2
      expected_unit: M-chars
    elevenlabs/flash-v2.5:
      slug_on_page: flash_v2_5
      expected_unit: M-chars
  consecutive_failures: 0            # bumped on parser exception
  last_scraped: null                 # ISO date; bumped on success
```

**Per-vendor parsers** — `scripts/kilo-benchmarks/direct_vendor_parsers/<vendor>.py`:
- Pure function: `def extract(payload: str | dict) -> list[ParsedRow]`
- Returns `[{model_slug, input_price_per_M, pricing_unit, raw_price_text, source_url}]`
- No HTTP, no DB writes — orchestrator owns I/O

**DB schema additions** (one migration):
```sql
ALTER TABLE agents ADD COLUMN last_price_scraped TEXT;       -- ISO date
ALTER TABLE agents ADD COLUMN consecutive_pricing_misses INT DEFAULT 0;
ALTER TABLE agents ADD COLUMN price_scrape_source TEXT;      -- vendor_url for audit
```

**Failure model** (each rule has a concrete consequence — no silent failures):

| Condition | Consequence |
|---|---|
| HTTP 4xx/5xx for vendor URL | Log + Telegram alert ; row untouched ; `vendor.consecutive_failures += 1` |
| Parser exception | Log + Telegram alert ; row untouched ; same counter |
| Parsed `pricing_unit` ≠ DB `pricing_unit` | **REFUSE** to write (likely parse bug) ; log + alert |
| Parsed price diff > 10% vs DB | Telegram alert "ElevenLabs Multilingual: was $0.30/1K, now $0.35/1K — verify" ; **still writes** the new price (10% is the audit threshold, not the block threshold) |
| Parsed price diff > 50% vs DB | **REFUSE** to write ; log + alert (almost certainly a parse bug — vendors don't 1.5× overnight) |
| Row missing from parsed set for `consecutive_pricing_misses >= 3` | `status = 'deprecated_pending'` (yellow in UI) |
| Row missing from parsed set for `consecutive_pricing_misses >= 7` | `status = 'deprecated'` |
| `vendor.consecutive_failures >= 7` | Telegram escalation: "ElevenLabs scraper down 7 days, prices stale; manual audit needed" |

**Alerting** — reuse the existing `fabrik-lib/alerting/` module (Apprise → Telegram, via vps1's already-deployed `apprise` container). One channel: existing `kilo-catalog` (per operator's Q2 selection).

**Error tracking** — wire to `fabrik-lib/observability/` which dispatches into vps1's already-deployed `glitchtip-web` (errors.vps1.ocoron.com). Parser exceptions get a Glitchtip issue with the vendor name + raw URL as tags. No new error-tracking infra needed.

## Phases

### Phase -1 — Build `fabrik-lib/web-scrape/` from its SPEC.md (1 day)

**Deliverable**: `fabrik-lib/web-scrape/` module (separate repo: `mobasak/fabrik-lib`). Contract is the canonical [fabrik-lib/web-scrape/SPEC.md](../../../../fabrik-lib/web-scrape/SPEC.md) — built by an AI agent (Claude Code / Traycer) reading that spec directly. Includes README, requirements.txt (`httpx`, `beautifulsoup4`, `pyyaml`), `webscrape.py`, `test_webscrape.py`, row added to `fabrik-lib/README.md` table.

**Why first**: every subsequent phase consumes this module. If we build it inside `scripts/kilo-benchmarks/` first and "extract later", we'll never extract (history shows this in every codebase). Build the reusable shape first, consume from it.

**Evidence section produced**: `pytest fabrik-lib/web-scrape/test_webscrape.py` green; `fabrik_lib.webscrape.fetch_rendered("https://example.com")` returns Chrome-rendered HTML against vps1 browserless; README rendered in `/opt/fabrik-lib/README.md` table.

### Phase 0 — Per-vendor URL + parsing-method grounding (1 day)

**Deliverable**: every one of the 28 vendors has a verified pricing URL and a confirmed fetch method. The tier table in §Aggregator landscape gets validated — if e.g. Cartesia is actually a static-HTML page (not Next.js), it shifts tier. No code yet.

**Method**: `curl -s <vendor_url>` for each. Inspect for `__NEXT_DATA__` script tags (Next.js hydration). Inspect for clean `<table>` or pricing-card divs (static HTML). Note JS-required pages.

**Evidence section produced**: `## Evidence` per-vendor block with the URL + fetch method + a sample of the parseable JSON/HTML chunk.

### Phase 1 — Orchestrator + alerting + 5 JSON-API vendors (2 days)

**Deliverable**:
- `fetch_direct_vendor_prices.py` orchestrator (full skeleton: registry load, vendor loop, cache, DB merge, alert)
- Registry YAML with all 28 vendors stubbed (only the 5 JSON-API vendors populated with parsers)
- Per-vendor parsers for `openai/`, `google/cloud-*`, `azure/`, `aws/` (boto3 already in deps), `deepl/`
- DB migration `migrate_direct_vendor_pricing_columns.py`
- Wired into `daily_refresh.sh` after `seed_direct_vendors.py` step
- Tests: `tests/test_fetch_direct_vendor_prices.py` (parser per vendor + orchestrator-level retry / 4xx / unit-mismatch / 50%-diff-block path)
- One Telegram alert verified end-to-end (run with a mocked 5xx; observe alert fires)

**Evidence section produced**: orchestrator log showing 5 vendors scraped + 0 diffs (idempotent on first day); the test suite output; the alert log line.

**Success criterion**: 25/96 rows pass the new pipeline; remaining 71 still seed-only with `last_price_scraped IS NULL` (so the Voice/Audio tab Status tooltip can distinguish — "auto-refreshed" vs "seed-only").

### Phase 2 — Next.js hydration + static HTML vendors (3 days)

**Deliverable**: parsers for 21 vendors → 53 rows.
- Sub-phase 2a: 10 Next.js vendors (~1.5d). Pattern is uniform per `fetch_replicate_prices.py`.
- Sub-phase 2b: 11 static-HTML vendors (~1.5d). Variance per page is higher — each parser is bespoke. Cache the raw page so re-runs are deterministic.

**Evidence section produced**: per-vendor row "before / after" diff (DB price vs scraped price) for all 21 vendors. Any diffs > 10% get a per-row explanation (e.g. "ElevenLabs raised Multilingual on 2026-04-12 — our seed was stale; verified live"). Goal: convince the operator the diffs are real, not parser bugs.

### Phase 3 — Browserless `fetch_rendered` for 4 heavy-JS vendors (1 day)

**Deliverable**: parsers for `heygen, pika, suno, udio` using `fabrik_lib.webscrape.fetch_rendered` (POSTs to vps1 `browser.vps1.ocoron.com`).
- For subscription-only vendors (suno, udio, pika, heygen): parser ONLY verifies model presence; does NOT write `input_cost_per_m`. Updates `last_scraped` + `consecutive_pricing_misses` only.
- Browserless capacity check: confirm 4 daily calls don't bump RAM/CPU above 70% of the 2GB limit ([vps-complete-inventory.md:124](../../infrastructure/vps-complete-inventory.md#L124)).
- Failure mode: if browserless is unreachable from WSL, fall back to `fetch_static` and log a warning — these 4 vendors will silently fail static parse (that's expected; alerting kicks in after `consecutive_failures >= 7`).

**Evidence section produced**: browserless `/content` log (4 calls, all succeed); vps1 cAdvisor memory chart of browserless container during the 4-vendor run.

### Phase 4 — `provider='unknown'` LLM rows (0.5 day)

**Deliverable**: backfill `provider` for 20 LLM rows. Likely a SQL fix using the `id` prefix (`<provider>/<model>` convention).

**Evidence section produced**: row count `WHERE provider='unknown'` before (20) / after (0).

### Phase 5 — Observability + ops doc (0.5 day)

**Deliverable**:
- Daily-refresh summary in `cache/direct_vendor_audit_<date>.md`: per-vendor success/failure, per-row diff, alert log
- Section in `docs/operations/AI_MODELS_BROWSER_OPS.md` describing how to manually trigger the scraper, how to add a new vendor, how to interpret the audit file
- Cron alert if `fetch_direct_vendor_prices.py` is skipped 2 days in a row (i.e. cron is broken)

**Evidence section produced**: ops doc rendered; one round-trip of "add a new vendor in <15 min" tested by adding a placeholder vendor + reverting.

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Vendor blocks scraping (robots.txt / Cloudflare) | Medium | Per-vendor robots.txt check during Phase 0 grounding; fall back to Firecrawl which respects bot policies; for hard blockers, manual quarterly audit + Status tooltip warning |
| vps1 `browserless` OOM under daily load | Very Low | 28 calls/day × ~3s each = 90s of total Chromium time; browserless container has 2GB and is otherwise idle. cAdvisor verification in Phase 3 evidence. |
| vps1 `browserless` unreachable from WSL (network blip) | Low | Orchestrator retries 3× with exponential backoff via `fabrik-lib/web-scrape`. If still fails, that vendor's `consecutive_failures` bumps; 7 consecutive days → escalation alert. No silent skip. |
| Parser breaks silently when vendor redesigns | High | `consecutive_failures` counter + 7-day Telegram escalation; cache the last-known-good payload so we KNOW when the page shape changed |
| Parser writes wrong unit (e.g. dollars when DB expects cents-per-M) | Medium | Unit-mismatch refusal (no write) + 50%-diff refusal (no write) — both catch unit shifts |
| Status flipping a still-active vendor to 'deprecated' over a multi-day outage | Medium | 7-day window before deprecation; deprecation flag distinct from `deprecated_pending` so UI can show ambiguity |
| Subscription vendors (suno, udio, etc.) have no price to scrape — we can't fully cover them | Confirmed | Phase 3 explicitly documents this; Status tooltip and audit file mark these as "presence-only" |

## Self-audit

What I do NOT yet know and must learn in Phase 0:
- Exact `pricing_url` for every vendor (some vendors have separate pricing-by-region pages)
- Whether each Next.js page actually hydrates pricing data (some defer to client-side fetch)
- Whether AWS/Azure pricing APIs return per-model granularity (might be too coarse for AssemblyAI/Polly)
- Whether the 20 `provider='unknown'` rows are actually parseable as `<provider>/<model>` ID strings

Phase 0 is the binding planning step. If grounding reveals e.g. 6 vendors need Firecrawl instead of 4, Phase 3 expands and Phase 2 shrinks; total effort approximately constant.

## Success criteria (definition of done)

1. `SELECT COUNT(*) FROM agents WHERE via_openrouter=0 AND via_kilo=0 AND last_price_scraped IS NULL` returns 0 (or only the 4 subscription-only rows that explicitly opt out).
2. A vendor pricing change appears in the catalog within 24h (verified by manually editing a seed price + observing the scraper correct it on next run).
3. A vendor EOL'ing a model shows up as `status='deprecated'` within 7 days (verified by temporarily removing a row from a vendor's catalog mock + observing the state machine).
4. Telegram alert fires when a vendor scraper fails 7 days in a row (verified by mocking a 7-day 5xx series).
5. Daily refresh completes in ≤ 5 minutes (current: ~90 seconds; adds ~30 vendor fetches; budget ~3 minutes).
6. `scripts/final_gate.py --lean --json` is green after every phase commit.

## Status

`DRAFT` → operator review → `AWAITING_EXECUTION` → execute phase-by-phase → `CONVERGED` only when all success criteria pass with embedded evidence.
