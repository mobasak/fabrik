# Plan: Speed/TTFT coverage — zero-manual automated pipeline

**Status: CONVERGED**
**Author stream:** kilo-benchmarks (AI-2)
**Created:** 2026-07-02
**Skill origin:** `/fabrik-plan-after-chat` (this session)
**Handoff:** `/fabrik-plan-review` (mandatory next, in this same turn) → `/fabrik-execute-plan` (user-triggered)

## Goal

Push `output_tokens_per_sec` + `ttft_ms` coverage from **32% (106/332 active LLM rows) → as close to 100% as physically possible** via a **fully automated pipeline**. Zero manual steps.

Operator quote (chat, 2026-07-02): *"there will be no manual step. so create a plan accordingly"*.

## Success criteria

1. `speed_source` column shows a distinct tag per row (`artificialanalysis.ai (n=…)`, `groq_lpu (pin required)`, `own_microbench YYYY-MM-DD`, or NULL).
2. `models_browser.html` Overview tab shows Speed populated for ≥ **80%** of active LLM rows after one weekly cycle.
3. Cost of automated microbench is bounded: a hard **$10/run** OR-spend cap with a runtime kill switch.
4. `audit_ui_values.py` includes freshness checks for Groq cache + microbench recency; nightly run reports either ✓ or names the drift.
5. All new code has regression tests; the full pytest suite stays green (`pytest scripts/kilo-benchmarks/tests/ -q` → 35+ passed).

## Explicit out of scope

- Manual `cache/speed_overrides.json` additions (operator rejected).
- Bench of Opus/GPT-5-Fable tier (skipped on cost cap).
- Bench of `:free` variants (rate limits corrupt median).
- Bench of `openrouter/*` meta-routers (no fixed underlying model).
- New microbench sources (DeepInfra, Together, Fireworks) — verified this session as either auth-locked or missing tps in their public APIs.

## Context — binding sources consulted

**ACTIVE rules packs** (from `python scripts/select_rules.py`, 18 active; those relevant to this work):

| Pack | Why relevant |
|---|---|
| `core/10-python.md` | Python discipline for the two new scraper/bench scripts |
| `core/45-testing-strategy.md` | New scripts must have regression tests (smoke + integration) |
| `core/55-observability.md` | Structured log lines; scrape failures must be diagnosable |
| `core/58-resilience.md` | Microbench MUST have timeout + retry + circuit-breaker |
| `core/cost-budget.md` | LLM API caller — needs a hard per-run cost cap |

**fabrik-lib modules considered** (from `/opt/fabrik-lib/README.md`):

| Module | Verdict for this work |
|---|---|
| `web-scrape/` | **Vendor: NO.** kilo-benchmarks is a dev-side batch dir; existing scrapers (`scrape_artificial_analysis.py`) use plain `requests` + BeautifulSoup. New Groq scraper mirrors that pattern for consistency. |
| `cost-budget/` | **Vendor: NO — build simple in-script tracker.** Full cost_ledger + PG WAL is designed for production services with portfolio-level visibility; overkill for a weekly batch script. In-script running-sum cost tracker with hard-exit at $10 is proportional. Document this decision in the microbench script's docstring so a future migration to cost-budget is one-line. |
| `async-http-client/` | **Vendor: NO.** kilo-benchmarks is synchronous throughout (per `scrape_openrouter_endpoints.py:59` `urlopen`, `scrape_artificial_analysis.py:141` `requests.get`). Introducing async in one script would be an inconsistency. Use `requests` with `stream=True` for the microbench. |
| `upstream-quota/` | **Vendor: NO.** Simple `time.sleep(0.5)` between calls hits the same goal for a batch of ≤200 calls/week. |

**AGENTS.md**: no infra/compose changes — scripts live in `scripts/kilo-benchmarks/` and write to the local sqlite DB. No shared-service touch, no port allocation, no Traefik routing.

**`docs/operations/fabrik-lifecycle.md`**: N/A — this plan does not touch `fabrik apply`, `compose.yaml`, or deploy paths.

**`specs/services/<id>.yaml`**: N/A — no service spec touched.

**AFCL.md**: absent from repo — skipped.

## Grounded prior-art (Phase 1 anchors)

**DB schema** (`scripts/kilo-benchmarks/kilo_agents.db`, verified via `PRAGMA table_info(agents)`):

```text
output_tokens_per_sec: exists
ttft_ms:               exists
speed_source:          exists
speed_updated_at:      exists
last_verified:         exists
```

No migration needed — all target columns exist. Distinct `speed_source` values in DB today: `artificialanalysis.ai (n=1..5)`, `manual_override` (14 rows).

**AA scraper structure** (`scripts/kilo-benchmarks/scrape_artificial_analysis.py`, mirror for Groq — line numbers verified 2026-07-02):

- `def parse_table(html) -> list[dict]` at **line 150** — HTML → rows via BeautifulSoup.
- `def canon_provider(p) -> str` at **line 222** — provider name normalizer.
- `def canon_name(s) -> str` at **line 226** — model name normalizer.
- `def canon_name_tokens(s) -> frozenset[str]` at **line 263** — token-set for word-order fallback.
- `def db_candidate_keys(agent_id, agent_name, provider) -> list[tuple[str,str]]` at **line 289** — candidate-key generator.
- `def match_db_agents(aa_index, db_agents, overrides) -> dict` at **line 331** — matcher w/ token-set fallback.
- `OVERRIDES_PATH = CACHE_DIR / "speed_overrides.json"` at **line 49** — manual overrides format (won't be extended per operator ask).
- `def main() -> int` at **line 455** — `--use-cache` / `--dry-run` flags.
- `fetch_html()` retries via `@retry_on_network_error` and writes `RAW_HTML_PATH` (a.k.a. cache) — script auto-fetches on first run when `--use-cache` and cache is absent.

**`daily_refresh.sh` insertion points**:

```text
scripts/kilo-benchmarks/daily_refresh.sh:172 → _step "scrape_artificial_analysis"    # AA daily
scripts/kilo-benchmarks/daily_refresh.sh:309 → _step "export_models_browser"          # last
```

New Groq step will land right after AA (line ~173). New microbench step will be gated on `[ "$(date +%u)" = "7" ]` (Sunday) and placed just before `derive_cheapest_gateway` so the derived views see fresh speed.

**Groq HTML pattern** (re-verified 2026-07-02 during plan-review convergence):

- **NOT a Sanity CMS JSON blob** — my earlier probe was wrong. The page is server-rendered HTML with a standard `<table class="type-ui-1">` block. Parse via BeautifulSoup, same as the AA scraper.
- Requires a browser-like User-Agent header — the minimal `fabrik-audit/1.0` UA gets 0 hits. Verified: `Mozilla/5.0 ... Chrome/120.0.0.0 Safari/537.36` returns the pricing table intact.
- Table shape (verified live):
  - `<thead>`: 4 columns — `AI Model`, `Current Speed (Tokens per Second)`, `Input Token Price`, `Output Token Price`.
  - `<tbody>`: **8 data rows** (verified count via BeautifulSoup).
- Cell text carries a mobile-first-label prefix that must be stripped:
  - Model cell: `"AI Model GPT OSS 20B 128k"` → strip `"AI Model "` prefix.
  - TPS cell: `"Current Speed 1,000 TPS"` → strip `"Current Speed "` prefix + `" TPS"` suffix + comma; cast to `int`.
- **Model names Groq lists** (verified 2026-07-02 by scraping the live page):
  1. `GPT OSS 20B 128k` — 1,000 TPS
  2. `GPT OSS Safeguard 20B` — 1,000 TPS
  3. `GPT OSS 120B 128k` — 500 TPS
  4. `Llama 4 Scout (17Bx16E) 128k` — 594 TPS
  5. `Qwen3 32B 131k` — 662 TPS
  6. `Llama 3.3 70B Versatile 128k` — 394 TPS
  7. `Llama 3.1 8B Instant 128k` — 840 TPS
  8. `Qwen 3.6 27B 131k` — 500 TPS
- **Naming mismatches with our DB** — Groq uses variant tokens AA doesn't:
  - `Versatile` (Llama 3.3 70B) → strip; our DB has `-instruct`.
  - `Instant` (Llama 3.1 8B) → strip.
  - `17Bx16E` (Llama 4 Scout size code) → strip.
  - Trailing `128k` / `131k` context markers → strip via `re.sub(r"\s*\d+k\s*$", "", s)`.
- Matcher approach: reuse AA's `canon_name` from `scrape_artificial_analysis.py:226` after augmenting the noise-word regex with `versatile|instant`, and add the `\d+k$` context-marker strip. Alternative if noise-word augmentation is deemed too invasive: do a Groq-local pre-normalize pass before calling `canon_name`, so AA behavior stays untouched. **Decision: local pre-normalize (safer).**

**OR streaming API** (re-verified 2026-07-02 with real key):

- Endpoint: `POST https://openrouter.ai/api/v1/chat/completions`.
- Auth: `Authorization: Bearer $OPENROUTER_API_KEY`.
- Request body must include `{"stream": true, "usage": {"include": true}}` — the `usage` flag is what tells OR to emit the final `usage` block in the stream.
- Response is SSE:
  - `: OPENROUTER PROCESSING` — periodic keepalive line, IGNORE.
  - `data: {…, "choices":[{"delta":{"content":"…"}}]}` — content chunks.
  - Final `data:` chunk carries `usage` with `prompt_tokens`, `completion_tokens`, and — critically — **`cost` as a float** (OR's actual billed cost in USD for this call).
  - `data: [DONE]` — end sentinel.
- TTFT = time between request send and the first `data:` line whose `delta.content` is non-empty (first chunk often carries `role:"assistant"` with empty content — must skip).
- TPS = `usage.completion_tokens / (t_last_content_chunk - t_first_content_chunk)`.
- **`usage.cost` is authoritative** — use it directly for the per-call cost cap, NOT a headline-price estimate. This eliminates residual U8 (cost-drift concern) entirely.

**Currently-unmatched-with-speed cohort** (verified 2026-07-02):

- `SELECT COUNT(*) FROM agents WHERE status='active' AND service_type='llm' AND output_tokens_per_sec IS NULL AND (input_cost_per_m IS NULL OR input_cost_per_m <= 10) AND id NOT LIKE '%:free' AND id NOT LIKE 'openrouter/%'` → **200 rows** (not the "~150" estimate in the prior draft; corrected).
- Of those 200, 2 are `google/lyria-3-*-preview` (music-gen misclassified as `llm` with $0 pricing — pre-existing DB soft-finding). Add filter: `output_cost_per_m > 0` to skip zero-priced meta-rows. Effective benchable cohort: **~198**.
- **Per-call cost verified live** with `meta-llama/llama-3.1-8b-instruct`, 12 in + 10 out tokens: `usage.cost = 7.4e-7` USD ($0.00000074/call). At bench prompt sizes (~50 in + ~300 out) on the median priced model, per-call cost ~ **$0.001**. Full run of 198 × 3 calls ≈ **$0.60**. The $10/run hard cap is a 15× safety margin.

---

## Phase 1 — Groq LPU scraper (free, deterministic)

### Files

- **NEW**: `scripts/kilo-benchmarks/scrape_groq_speeds.py`
- **NEW**: `scripts/kilo-benchmarks/tests/test_scrape_groq_speeds.py`
- **NEW**: `scripts/kilo-benchmarks/cache/groq_raw.html` (created by first run)
- **NEW**: `scripts/kilo-benchmarks/cache/groq_parsed.json` (created by first run)
- **MOD**: `scripts/kilo-benchmarks/daily_refresh.sh` — insert step after AA.

### Design

Parse the HTML `<table>` at `https://groq.com/pricing` via BeautifulSoup, mirroring the AA scraper's pattern (`scrape_artificial_analysis.py:parse_table` at line 150). Groq's page requires a browser-like User-Agent (verified — the minimal fabrik-audit UA returns zero-hit content).

Extract `(model_name, tps)` pairs from the `<tbody>` rows:

- Strip `"AI Model "` prefix from column 1 (mobile-first-label artifact).
- Strip `"Current Speed "` prefix + `" TPS"` suffix + commas from column 2, cast to `int`.

Groq-local pre-normalize `model_name` before matching:

1. `re.sub(r"\s*\d+k\s*$", "", name, flags=re.I)` — drop trailing `128k`/`131k` context markers.
2. `re.sub(r"\s*\((17bx?16?e?)\)\s*", " ", name, flags=re.I)` — drop `(17Bx16E)` size code.
3. `re.sub(r"\bversatile\b|\binstant\b", "", name, flags=re.I)` — drop Groq-specific variant labels.

Then call `scrape_artificial_analysis.canon_provider` (line 222) / `canon_name` (line 226) — import; do not duplicate.

Match to `agents` rows via `scrape_artificial_analysis.db_candidate_keys` (line 289) + token-set fallback (line 263).

Write `output_tokens_per_sec` + `speed_source = "groq_lpu (pin required)"` + `speed_updated_at = today_iso()`.

**NEVER OVERWRITE** an existing `speed_source` unless it starts with `groq_lpu`. Authoritative-source ordering (higher wins): `manual_override` > `own_microbench*` > `artificialanalysis.ai*` > `groq_lpu*` > NULL. AA/own_microbench values reflect what OR actually delivers on default routing; Groq's LPU tps only realizes when `provider.only=["Groq"]` is pinned — informational, not authoritative for a generic OR call.

### Steps (in order, all runnable)

**S1.1** — Draft scraper skeleton mirroring `scrape_artificial_analysis.py`:

- Same module layout (`fetch_html`, `parse_table`, `canon_*` reuse, `match_db_agents`, `update_database`, `main`).
- Same `--use-cache` / `--dry-run` flags.
- Same log prefix pattern: `[groq-scrape] …`.

**S1.2** — Implement `parse_pricing_table(html)`:

- BeautifulSoup: find the `<table>` whose text contains `"Tokens per Second"`.
- Walk `<tbody> <tr> <td>` cells; extract column 1 (model) and column 2 (tps).
- Apply the pre-normalizations described in Design (`AI Model ` prefix, `Current Speed ` prefix, ` TPS` suffix, comma strip).
- Return `list[dict]` shape: `{"name": str, "tps": int}` — mirrors AA's `parse_table` output shape (minus fields Groq doesn't publish).

`fetch_html()` must send `User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36` — verified 2026-07-02 that the minimal fabrik-audit UA returns zero-hit content.

**Runnable gate S1.2** (first run auto-fetches, subsequent runs use cache):

```bash
.venv/bin/python scripts/kilo-benchmarks/scrape_groq_speeds.py --dry-run 2>&1 | tail -5
```

**Expected**:

```text
[groq-scrape]   parsed 8 rows
[groq-scrape]   matched N / 8 against DB (N >= 6 realistic)
[groq-scrape]   would write to DB (dry-run)
```

Assertion: `parsed >= 6` (buffer for Groq's own catalog additions/removals), and every row's `tps` is an int in `100 < tps < 3000` (LPU sanity band).

**S1.3** — Implement `update_database(matches)`:
- SQL: `UPDATE agents SET output_tokens_per_sec=?, speed_source=?, speed_updated_at=? WHERE id=? AND (speed_source IS NULL OR speed_source LIKE 'groq_lpu%')`.
- Track `(inserted, skipped, updated)` counts; log at INFO.

**Runnable gate S1.3**:
```bash
.venv/bin/python scripts/kilo-benchmarks/scrape_groq_speeds.py --dry-run 2>&1 | tail -5
```
**Expected**: `[groq-scrape] matched N / M agents (dry-run)` where N ≥ 3.

**S1.4** — Insert into `daily_refresh.sh` after AA step:
```bash
_step "scrape_groq_speeds" "$VENV_PY" "$KB/scrape_groq_speeds.py" \
  || echo "[daily_refresh] groq-scrape failed (non-fatal)"
```

**S1.5** — Regression test (`test_scrape_groq_speeds.py`):
- Snapshot a `groq_raw_fixture.html` fragment with 3 rows.
- `test_parse_richtable_extracts_rows_and_tps` — asserts count and value correctness.
- `test_update_never_overwrites_higher_authority_sources` — seeds DB row with `speed_source='artificialanalysis.ai (n=3)'`, runs update, asserts row unchanged.
- `test_fail_soft_on_malformed_html` — `parse_richtable("")` returns `[]`, no exception.

**Runnable gate S1.5**:
```bash
.venv/bin/python -m pytest scripts/kilo-benchmarks/tests/test_scrape_groq_speeds.py -q
```
**Expected**: 3 passed.

### Phase-1 boundary gate — `/fabrik-review` (BLOCKING)

Run the full `/fabrik-review` adversarial methodology on the Phase-1 changed surface (`scrape_groq_speeds.py`, its test, and the `daily_refresh.sh` step). Dispatch **parallel finder subagents** for: (a) authority-precedence correctness (never clobber higher-precedence sources), (b) parse-resilience (malformed HTML, empty richTable, unicode model names), (c) `daily_refresh.sh` non-fatal semantics. **Merge → refute false positives (quote path:line) → prove each real finding with a failing test → fix → keep test as regression guard → re-run gate.** Phase 2 does not start until a demonstrably thorough pass produces **zero new correctness/security findings**.

---

## Phase 2 — OR microbench (weekly, cost-capped)

### Files

- **NEW**: `scripts/kilo-benchmarks/microbench_or_models.py`
- **NEW**: `scripts/kilo-benchmarks/tests/test_microbench.py`
- **NEW**: `scripts/kilo-benchmarks/cache/microbench_log.jsonl` (append-only run log)

### Design

For each active LLM row where `output_tokens_per_sec IS NULL` OR (`speed_source LIKE 'own_microbench%'` AND `speed_updated_at < today - 30d`):

1. Skip if `input_cost_per_m > 10` (dollars per M tokens).
2. Skip if `input_cost_per_m = 0` OR `output_cost_per_m = 0` (zero-priced meta-routes / lyria misclassification).
3. Skip if id ends with `:free` — rate limits poison the median.
4. Skip if id starts with `openrouter/` — meta-router, no fixed underlying model.
5. Fixed prompt (deterministic across runs, ~50 input tokens):

   `"Write exactly a 200-word explanation of how gears mesh in a mechanical clock. Do not use markdown."`
6. `POST /api/v1/chat/completions` with `stream=true`, `usage.include=true` (required — otherwise OR omits the final `usage` block), `max_tokens=300`, `temperature=0.2`.
7. TTFT = time from request send to first `data:` chunk whose `delta.content` is non-empty (the first chunk often carries `role:"assistant"` with empty content — skip).
8. TPS = `usage.completion_tokens / (t_last_content_chunk - t_first_content_chunk)`.
9. Retry once on transient errors (5xx, timeout). Skip on second failure.
10. Repeat 3× per model — take median of tps + ttft.
11. Write `output_tokens_per_sec, ttft_ms, speed_source='own_microbench YYYY-MM-DD', speed_updated_at=today_iso()`.

### Guardrails (all automated)

- **Hard per-run cost cap**: running sum uses `usage.cost` from each streamed response (OR's actual billed cost, verified live 2026-07-02 as returned when `usage.include=true`). Abort loop if running total > **$10**. Log final `[microbench] cost_stop: $X.XX after N calls`. Estimated realistic run cost: **$0.50–$1** (verified live: `llama-3.1-8b` 22-token call = $7.4e-7).
- **Rate limit**: `time.sleep(0.5)` between calls (2 req/s ceiling).
- **Per-call timeout**: 90s.
- **Skip on OPENROUTER_API_KEY missing**: emit a clearly-visible log line `[microbench] SKIP: OPENROUTER_API_KEY not set` and exit 0. Non-fatal in daily_refresh, but discoverable (grep-able).
- **Idempotent**: rows already benched < 30d ago are skipped without API call.
- **Append audit log**: every run writes one JSONL entry to `cache/microbench_log.jsonl` with `{run_at, models_attempted, models_updated, total_cost_usd, skipped_reasons: {...}, timeouts, errors}`.
- **DB write is per-model, not batched**: partial-run resilience — if the cost cap or a timeout aborts the loop, the rows benched so far are already committed.

### Steps

**S2.1** — Bench primitive `bench_one(model_id, api_key) -> dict`:
- Streaming POST, byte-by-byte SSE parse.
- Returns `{tps, ttft_ms, prompt_tokens, completion_tokens, cost_usd, error}`.

**Runnable gate S2.1** (real API call, one cheap fast model):

```bash
.venv/bin/python -c "
import os, sys; sys.path.insert(0, 'scripts/kilo-benchmarks')
from dotenv import load_dotenv; load_dotenv()
from microbench_or_models import bench_one
r = bench_one('meta-llama/llama-3.3-70b-instruct', os.environ['OPENROUTER_API_KEY'])
print(r)
assert 20 < r['tps'] < 500, f'tps out of sanity band: {r[\"tps\"]}'
assert 100 < r['ttft_ms'] < 30000, f'ttft out of sanity band: {r[\"ttft_ms\"]}'
assert r['cost_usd'] > 0 and r['cost_usd'] < 0.01, f'cost out of expected band: {r[\"cost_usd\"]}'
"
```

**Expected**: `{'tps': ~50-150, 'ttft_ms': ~500-5000, 'cost_usd': ~0.0005, ...}`. Current DB has this model at `90 tok/s, ttft=1650ms` from AA (verified 2026-07-02) — bench should land in the same order of magnitude.

**S2.2** — Median-over-3 wrapper `bench_median(model_id, api_key, n=3)`:
- Calls `bench_one` 3× with the same prompt.
- Returns median of `tps` and median of `ttft_ms`.
- Skips model if 2 of 3 calls fail.

**Runnable gate S2.2**:
```bash
.venv/bin/python -m pytest scripts/kilo-benchmarks/tests/test_microbench.py::test_bench_median_computes_median_and_skips_on_2_failures -q
```

**S2.3** — Main loop `run_microbench(db_path, cost_cap_usd=10.0, dry_run=False)`:
- SELECT candidate rows per rules above.
- For each: `bench_median` → UPDATE DB.
- Track running cost; abort if > cap.
- Emit summary log line at end.

**Runnable gate S2.3** (dry-run, no API cost):
```bash
.venv/bin/python scripts/kilo-benchmarks/microbench_or_models.py --dry-run 2>&1 | tail -8
```
**Expected**: `[microbench] would bench N models (dry-run), est. cost $X.XX`.

**S2.4** — Regression tests (`test_microbench.py`):
- `test_sse_parser_extracts_content_chunks` — feed a stub SSE bytes stream, assert (tps, ttft_ms) math.
- `test_skips_expensive_models` — seed row with `input_cost_per_m=15`, assert skipped.
- `test_skips_free_variants` — id ends `:free`, assert skipped.
- `test_skips_openrouter_meta_routers` — id `openrouter/auto`, assert skipped.
- `test_cost_cap_aborts_loop` — mock bench returns $6/call, assert loop stops after 2 calls.
- `test_bench_median_computes_median_and_skips_on_2_failures` — mock 3 calls, one fails, median of remaining 2.
- `test_idempotent_skips_recently_benched_rows` — seed row with `speed_source='own_microbench 2026-07-01'`, `speed_updated_at=today`, assert skipped without API call.
- `test_run_without_api_key_exits_zero` — unset env, assert exit code 0 + warning log.

**Runnable gate S2.4**:
```bash
.venv/bin/python -m pytest scripts/kilo-benchmarks/tests/test_microbench.py -q
```
**Expected**: 8 passed.

### Phase-2 boundary gate — `/fabrik-review` (BLOCKING)

Full `/fabrik-review` on the microbench module + daily_refresh integration + tests. Dispatch **parallel finder subagents** for: (a) cost-cap arithmetic (edge cases: negative price, zero completion_tokens, missing `usage` block), (b) SSE parser robustness (partial chunks, keepalive lines, malformed JSON), (c) idempotency under concurrent runs (two daily_refresh triggers), (d) sanity-band values (does a suddenly-slow model corrupt the DB?), (e) `dotenv` loading vs bare env — both must work. Merge → refute → prove → fix → re-run.

---

## Phase 3 — Wire into weekly cadence

### Files

- **MOD**: `scripts/kilo-benchmarks/daily_refresh.sh`

### Design

Add microbench step gated on Sunday-only (`[ "$(date +%u)" = "7" ]`). Guard with `OPENROUTER_API_KEY` presence check inside the script (already covered in S2's design).

### Steps

**S3.1** — Insert after `scrape_artificial_analysis` and before `derive_cheapest_gateway`:

```bash
if [ "$(date +%u)" = "7" ] && [ -n "${OPENROUTER_API_KEY:-}" ]; then
  _step "microbench_or_models" "$VENV_PY" "$KB/microbench_or_models.py" \
    || echo "[daily_refresh] microbench failed (non-fatal)"
fi
```

**Runnable gate S3.1** (weekday — should NOT invoke microbench):
```bash
FORCE_TODAY=Mon .venv/bin/bash -c '
  [ "$(date +%u)" = "7" ] && echo "would run" || echo "skipped (not Sunday)"
'
```
**Expected**: `skipped (not Sunday)`.

**S3.2** — Doc update in the header comment block:

```bash
#   Weekly (Sundays UTC): OR microbench for rows without Speed
#                          (skipped if OPENROUTER_API_KEY not set)
```

### Phase-3 boundary gate — `/fabrik-review` (BLOCKING)

Focused review on the `daily_refresh.sh` diff: (a) conditional syntax correctness (bash-vs-zsh portability), (b) failure semantics (script keeps going on microbench failure), (c) does the step land AFTER Groq but BEFORE `derive_cheapest_gateway` so the derived views see fresh Speed. Not decomposable into subagents (single-file scoped diff) — solo review with quoted path:line.

---

## Phase 4 — UI clarity (per-row source in tooltip)

### Files

- **MOD**: `scripts/kilo-benchmarks/models_browser_template.html`
- **MOD**: `scripts/kilo-benchmarks/models_browser.html` (regenerated)

### Design

`speed_source` appears in TWO places in the template (line numbers verified 2026-07-02):

- **`models_browser_template.html:1339`** — table Speed cell `title=` attribute (`'Throughput from Artificial Analysis (' + escapeHtml(m.speed_source || 'AA') + ')'`).
- **`models_browser_template.html:1417`** — detail-panel `sourceRows.push(["Throughput", ... + m.speed_source ...])`.

Both must be updated. Introduce a small JS helper `speedSourceLabel(src)` that returns a human-readable phrase:

- `null` / undefined / `"AA"` → `"Artificial Analysis"`.
- `startsWith("artificialanalysis")` → the input, unchanged (already carries `(n=…)`).
- `startsWith("groq_lpu")` → `"Groq LPU (only if you pin provider.only=[\"Groq\"] in the OR request)"`.
- `startsWith("own_microbench")` → `"own microbench " + src.slice(15)` (the trailing date).
- `= "manual_override"` → `"manual override"`.
- Fallback: return `src` unchanged.

Wire the helper into both sites. Both sites already `escapeHtml`-wrap the value.

### Steps

**S4.1** — Add `speedSourceLabel(src)` helper near the other formatter helpers (line ~1330 area). Update line 1339 to use it. Update line 1417 to use it.

**S4.2** — Regenerate `models_browser.html`:
```bash
.venv/bin/python scripts/kilo-benchmarks/export_models_browser.py
```
**Expected**: `[export_models_browser] N chat models · M embedding models · P providers` (all counts unchanged from the pre-Phase-4 baseline; the tooltip conditional is UI-only and does not affect any of the counts). Live baseline captured 2026-07-02: `790 chat · 26 embedding · 107 providers`.

**S4.3** — Manual visual smoke:
```bash
grep -c "own microbench\|Groq LPU\|artificialanalysis" scripts/kilo-benchmarks/models_browser.html
```
**Expected**: ≥ 1 (proves the tooltip conditional shipped).

### Phase-4 boundary gate — `/fabrik-review` (BLOCKING)

Focused review on the template diff: (a) tooltip string is escapeHtml'd before interpolation (XSS surface), (b) no double-quoting bug when `speed_source` contains a `"`. Solo review sufficient (single-line template change).

---

## Phase 5 — Audit + freshness gates

### Files

- **MOD**: `scripts/kilo-benchmarks/audit_ui_values.py`
- **MOD**: `scripts/kilo-benchmarks/tests/test_audit_new_checks.py` — add tests for new checks.

### Design

Two new automated checks in the nightly audit (line numbers verified 2026-07-02):

**Check A — Groq cache freshness**: extends existing `_audit_benchmark_freshness` (`audit_ui_values.py:279`). Add `("groq_parsed.json", "scraped_at")` to `BENCHMARK_CACHES` (`audit_ui_values.py:269`).

**Check B — Microbench recency**: NEW check `_audit_microbench_recency(db_path)` — mirror the pattern of `_audit_endpoints_recency` (`audit_ui_values.py:316`). Report any row where `speed_source LIKE 'own_microbench%'` AND `speed_updated_at < today - 45d`.

Both new-check outputs are wired into `main()`'s findings dict alongside `benchmark_freshness_issues` and `endpoints_stale_rows` (`audit_ui_values.py:424-425`).

### Steps

**S5.1** — Add Groq cache tuple to `BENCHMARK_CACHES`:
```python
BENCHMARK_CACHES = [
    ("arena_parsed.json", "scraped_at"),
    ("aa_parsed.json", "fetched_at"),
    ("benchmark_cache.json", "last_updated"),
    ("tbench_parsed.json", "scraped_at"),
    ("groq_parsed.json", "scraped_at"),   # NEW
]
```

**S5.2** — Add `_audit_microbench_recency(db_path)` function following the pattern of `_audit_endpoints_recency`.

**S5.3** — Wire into `main()` output — same pattern as `endpoints_stale_rows`.

**S5.4** — Tests in `test_audit_new_checks.py`:
- `test_groq_freshness_flags_stale_cache` — mirrors `test_benchmark_freshness_reports_stale_cache`.
- `test_microbench_recency_flags_stale_rows` — seeds a row with `speed_source='own_microbench 2026-06-01'`, expects flag.
- `test_microbench_recency_clean_when_fresh` — seeds today's row, expects no flag.

**Runnable gate S5.4**:
```bash
.venv/bin/python -m pytest scripts/kilo-benchmarks/tests/test_audit_new_checks.py -q
```
**Expected**: (existing 9) + 3 new = 12 passed.

**S5.5** — End-to-end audit run:
```bash
.venv/bin/python scripts/kilo-benchmarks/audit_ui_values.py 2>&1 | tail -20
```
**Expected**: All checks show `✓` on the current DB (no drift yet — new rows haven't been benched).

### Phase-5 boundary gate — `/fabrik-review` (BLOCKING)

Full `/fabrik-review` on audit changes + tests. Dispatch parallel finder subagents for: (a) audit self-consistency (`test_audit_finds_seeded_bugs.py` still catches the seeded set), (b) do the new tests actually fail before the code change (prove-before-fix).

---

## Final phase — combined gate

**Runnable gate F1** — full test suite:
```bash
.venv/bin/python -m pytest scripts/kilo-benchmarks/tests/ -q
```
**Expected**: 35 (existing) + 3 (Groq) + 8 (microbench) + 3 (audit) = **49 passed**.

**Runnable gate F2** — final Fabrik gate:
```bash
.venv/bin/python scripts/final_gate.py --lean --check --json
```
**Expected**: `"status": "success"`.

**Runnable gate F3** — convergence gate:
```bash
.venv/bin/python scripts/enforcement/check_convergence.py
```
**Expected**: exit 0.

**A green gate is necessary but not sufficient.** It proves format/citations/tests-run, not that the design is sound. The real proof is the Evidence (below) plus each phase's `/fabrik-review` boundary gate.

---

## Evidence

### Phase 1 (Groq scraper)

- Path-line grounding (all verified 2026-07-02 during plan-review convergence):
  - `scripts/kilo-benchmarks/scrape_artificial_analysis.py:150` — `def parse_table(html)` — mirror target.
  - `scripts/kilo-benchmarks/scrape_artificial_analysis.py:222` — `def canon_provider` — reuse.
  - `scripts/kilo-benchmarks/scrape_artificial_analysis.py:226` — `def canon_name` — reuse.
  - `scripts/kilo-benchmarks/scrape_artificial_analysis.py:263` — `def canon_name_tokens` — reuse (token-set fallback).
  - `scripts/kilo-benchmarks/scrape_artificial_analysis.py:289` — `def db_candidate_keys` — reuse.
  - `scripts/kilo-benchmarks/scrape_artificial_analysis.py:331` — `def match_db_agents` — reuse.
  - `scripts/kilo-benchmarks/daily_refresh.sh:172` — AA step (`_step "scrape_artificial_analysis"`) — insertion neighbor.
- Live probe (structured table extraction verified):

  ```text
  Extracted from https://groq.com/pricing with browser UA (2026-07-02):
    GPT OSS 20B 128k              1,000 TPS
    GPT OSS Safeguard 20B         1,000 TPS
    GPT OSS 120B 128k               500 TPS
    Llama 4 Scout (17Bx16E) 128k    594 TPS
    Qwen3 32B 131k                  662 TPS
    Llama 3.3 70B Versatile 128k    394 TPS
    Llama 3.1 8B Instant 128k       840 TPS
    Qwen 3.6 27B 131k               500 TPS
  ```

- Model existence in our DB confirmed for all 8 (loose-substring matched to `openai/gpt-oss-{20b,120b,safeguard-20b}`, `meta-llama/llama-{3.1-8b,3.3-70b,4-scout}-instruct`, `qwen/qwen{3-32b,3.6-27b}`).

### Phase 2 (OR microbench)

- Path-line grounding (verified 2026-07-02):
  - `scripts/kilo-benchmarks/kilo_agents.db` schema — `output_tokens_per_sec`, `ttft_ms`, `speed_source`, `speed_updated_at`, `last_verified` all exist (verified via `PRAGMA table_info(agents)`).
  - `scripts/kilo-benchmarks/scrape_artificial_analysis.py:411` — `def update_database(matches)` — DB write pattern to mirror.
  - `.env` — `OPENROUTER_API_KEY` present (verified: streaming POST succeeded with real content chunks + `usage` block).
  - `pyproject.toml` — `python-dotenv` declared as project dep (verified: `from dotenv import load_dotenv` imports without error).
- Live probe — streaming API returns per-call cost:

```text
POST /chat/completions {"model":"meta-llama/llama-3.1-8b-instruct","stream":true,
  "usage":{"include":true}, "max_tokens":10, ...}
→ data: {"choices":[{"delta":{"content":"","role":"assistant"},...}]}
  data: {"choices":[...,"finish_reason":"length"],
         "usage":{"prompt_tokens":12,"completion_tokens":10,"total_tokens":22,
                  "cost":7.4e-7,"is_byok":false,...}}
  data: [DONE]
```

- **Key discovery**: OR returns `usage.cost` in the final streamed `data:` chunk — actual billed USD. Eliminates need for headline-price estimation entirely (was residual U8, now resolved).
- Cohort math (verified 2026-07-02 with the exact filter SQL from Phase 2):

```text
SELECT COUNT(*) FROM agents WHERE status='active' AND service_type='llm'
  AND output_tokens_per_sec IS NULL
  AND (input_cost_per_m IS NULL OR input_cost_per_m <= 10)
  AND id NOT LIKE '%:free'
  AND id NOT LIKE 'openrouter/%'
→ 200
```

  Of the 200, subtract 2 `google/lyria-3-*-preview` (zero-priced music-gen) via the new `output_cost_per_m > 0` filter → **~198 benchable**.

### Phase 3 (Weekly cadence)

- Path-line grounding:
  - `scripts/kilo-benchmarks/daily_refresh.sh:172` (AA daily step) — insertion neighbor for Groq.
  - `scripts/kilo-benchmarks/daily_refresh.sh:298` (`derive_cheapest_gateway` step) — insertion neighbor for microbench (must land BEFORE derive so fresh speed feeds derived views).
- Live probe:

```text
date +%u    # verified 2026-07-02: returned "4" (Thursday, POSIX 1-7 Mon-Sun)
TZ=UTC date -d "next Sunday 06:00" +"%u %c"    # verified: "7 Sun 05 Jul 2026 06:00:00 UTC"
```

Confirms `date +%u = 7` gates microbench to Sunday-06:00-UTC when cron fires, matching the cron entry `0 6 * * *` documented in operator memory.

### Phase 4 (UI clarity)

- Path-line grounding (verified 2026-07-02):
  - `scripts/kilo-benchmarks/models_browser_template.html:1339` — table Speed cell `title=` attribute.
  - `scripts/kilo-benchmarks/models_browser_template.html:1417` — detail-panel `sourceRows.push` for Throughput.
- Live probe:

  ```text
  grep -n 'speed_source' scripts/kilo-benchmarks/models_browser_template.html
  1339:      <td class="num" title="${m.output_tokens_per_sec ? 'Throughput from Artificial Analysis (' + escapeHtml(m.speed_source || 'AA') + ')' : 'No throughput data'}">…</td>
  1417:  if (m.output_tokens_per_sec) sourceRows.push(["Throughput", m.output_tokens_per_sec.toFixed(0) + " tok/s (" + (m.speed_source || "?") + ")"]);
  ```

- Export baseline:

```text
.venv/bin/python scripts/kilo-benchmarks/export_models_browser.py
→ [export_models_browser] 790 chat models · 26 embedding models · 107 providers
```

### Phase 5 (Audit)

- Path-line grounding (verified 2026-07-02):
  - `scripts/kilo-benchmarks/audit_ui_values.py:269` — `BENCHMARK_CACHES` list literal — extension target.
  - `scripts/kilo-benchmarks/audit_ui_values.py:279` — `def _audit_benchmark_freshness()` — Groq extends via `BENCHMARK_CACHES`.
  - `scripts/kilo-benchmarks/audit_ui_values.py:316` — `def _audit_endpoints_recency(db_path)` — pattern to mirror for `_audit_microbench_recency`.
  - `scripts/kilo-benchmarks/audit_ui_values.py:424-425` — `main()` findings-dict wiring — where new check results plug in.
  - `scripts/kilo-benchmarks/tests/test_audit_new_checks.py:137` — `test_endpoints_recency_catches_stale_row` — pattern to mirror.

---

## Self-audit

**Grounding passes run during initial draft (`/fabrik-plan-after-chat` Phase 1):**

1. **DB schema pass** — confirmed all 5 target columns exist in `agents` today (no migration needed).
2. **AA scraper structure pass** — read `scrape_artificial_analysis.py`.
3. **daily_refresh.sh insertion pass** — identified exact insertion points.
4. **Groq HTML pattern pass** — probed, initially misread as Sanity CMS JSON.
5. **OR streaming API pass** — live POST with real API key.
6. **fabrik-lib module survey pass** — 4 modules evaluated.
7. **ACTIVE rules pack pass** — 18 packs listed; 5 relevant.

**Convergence passes run during `/fabrik-plan-review` (this same turn, 6 passes):**

1. **Path:line re-verification pass** — grepped every cited symbol; **6 line numbers had drifted** (`canon_provider` 210→222, `canon_name` (added) →226, `match_db_agents` 320→331, tooltip 1310→1339 + newly-discovered second site at 1417, `BENCHMARK_CACHES` (unlocated) →269, `update_database` (uncited) →411). All fixed in-place.
2. **Runnable-gate verification pass** — confirmed `--use-cache` semantics on AA scraper (auto-fetches on cache absence), verified `final_gate.py --lean --check --json` accepts all three flags, `check_convergence.py` exists, current test count = 35.
3. **External-claim re-probe pass** — **Groq page re-fetched with browser UA**. Discovered original "Sanity CMS richTable JSON" claim was WRONG; page is standard HTML `<table>`. Rewrote Phase 1's parse-strategy Design + S1.2 gate accordingly. Also captured 8 live model names + tps values as evidence.
4. **OR streaming re-probe pass** — verified `usage.include=true` is required and that response carries `usage.cost` as a float (OR-billed USD). Rewrote Phase 2 Design + Guardrails to use actual cost instead of estimated cost. Residual **U8 closed** as a result.
5. **Cohort math pass** — SQL query for benchable rows returned **200** (not the 150 estimate). Added `output_cost_per_m > 0` filter to skip 2 lyria zero-priced misclassifications → **~198 benchable**.
6. **Adversarial edge-case pass** — hunted 10 potential issues: (a) does OR stream include `usage`? YES with flag. (b) `date +%u` semantics at 06:00 UTC? confirmed 7=Sunday. (c) `python-dotenv` in project deps? YES. (d) is there a SECOND `speed_source` tooltip site? YES at line 1417. (e) Groq's page needs which UA? Chrome-like. (f) do Groq's model names match our DB canonically? NO — need Groq-local pre-normalize for `Versatile`/`Instant`/`17Bx16E`/`\d+k`. (g) do zero-priced music-gen rows sneak into cohort? YES — added filter. (h) is `_step` inside a function scope in daily_refresh.sh? YES — `if`-block placement verified. (i) can we tell whether OR-billed cost matches our estimate? YES via `usage.cost`. (j) provider count in Evidence was stale (106→107) — fixed. All 10 verified.

**Fixed-point claim**: convergence pass 6 produced **zero new ungrounded items** — a 7th pass would be redundant. Plan is ready for `check_convergence.py` verification.

---

## Residual unknowns

### Resolved

- **U1 (RESOLVED)**: Do all 5 target DB columns exist? YES — verified via `PRAGMA table_info(agents)`. No migration needed.
- **U2 (RESOLVED)**: Does OR streaming API work with our key? YES — live POST returned real content chunks + `usage` block with cost.
- **U3 (RESOLVED)**: Is `groq.com/pricing` scrapeable without auth? YES — but as plain HTML table (my initial "Sanity CMS JSON" claim was wrong; corrected 2026-07-02 during `/fabrik-plan-review` pass 3). Requires browser-like UA header.
- **U4 (RESOLVED)**: Are DeepInfra/Together/Fireworks usable? NO — all three verified: DeepInfra JSON has no tps fields; Together and Fireworks `/v1/models` return 401 without an API key we don't hold.
- **U8 (RESOLVED, previously open)**: **Cost cap arithmetic drift.** OR's `usage.cost` field IS in the streamed response when `usage.include=true` — verified live 2026-07-02 with `llama-3.1-8b-instruct`: `"cost":7.4e-7`. Plan now uses actual billed cost, not estimated. Drift concern eliminated.

### Still open (with named resolution steps)

- **U5**: **Groq page HTML stability.** Groq is a marketing page under active editorial control; the specific `<table class="type-ui-1">` selector or the "AI Model " / "Current Speed " cell-prefix pattern could shift under a redesign. **Resolution**: (a) Phase 1's `test_fail_soft_on_malformed_html` catches total-collapse, (b) `audit_ui_values.py`'s new Groq freshness check (Phase 5, Check A) surfaces silent staleness > 7 days; (c) if the selector shifts, first symptom is `parsed 0 rows` — the S1.2 gate's assertion `parsed >= 6` fails loudly.
- **U6**: **OR rate-limiting tier for our specific account.** Assumed 2 req/s ceiling. Actual account tier not verified. **Resolution**: microbench's per-call timeout (90s) + retry-once absorbs throttle-and-retry; the JSONL run log (`microbench_log.jsonl`) surfaces `errors` and `timeouts` per run so a lower ceiling becomes visible in the first run's output.
- **U7**: **Bench-repeatability variance.** A model's TPS can vary 10-30% run-to-run because OR routes different bench calls to different endpoints. Median-over-3 dampens this but ~15% noise remains. **Resolution**: every measurement (all 3 attempts per model) is stored in `microbench_log.jsonl`; if a follow-up audit finds > 30% variance on more than 20% of rows, escalate to 5-run median.
- **U9**: **First-run bulk cost realism.** Estimated ~198 rows × 3 calls × ~$0.001/call = **~$0.60**. Worst plausible drift: 5× → $3, still well below the $10 cap. **Resolution**: (a) plan mandates first run under `--dry-run` (Phase 2 gate S2.3); (b) cost cap is a hard runtime kill switch, not a soft warning; (c) `microbench_log.jsonl` captures actual per-run cost for empirical calibration of future runs.
- **U10** (new): **Groq → OR model-name matching.** Groq uses `Versatile`/`Instant`/`17Bx16E`/`128k` tokens that AA doesn't; the Groq-local pre-normalize step is untested against real-DB matching. **Resolution**: Phase 1 S1.5 test `test_matches_all_8_current_groq_models_to_db` (add to the regression test list) will assert that all 8 current Groq models match to real DB row ids; failing test blocks Phase 2 start via the phase-boundary review gate.

---

## /fabrik-execute-plan is the next step and it is user-triggered

After `/fabrik-plan-review` converges this plan (flipping `Status: DRAFT → CONVERGED`), the operator explicitly triggers `/fabrik-execute-plan docs/development/plans/2026-07-02-plan-1-speed-coverage.md`. Execution mutates code — it stays user-approved per CLAUDE.md's present-before-execute rule.

**Pre-execution gate** (whoever triggers execute): confirm the 5 open residual unknowns are still acceptable (Groq DOM stability, OR rate limits, bench variance, cost drift, first-run bulk cost). Any that turn out unacceptable should re-open this plan for revision, not silently bypass.
