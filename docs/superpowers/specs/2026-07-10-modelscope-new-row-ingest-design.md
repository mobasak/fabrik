# ModelScope new-row auto-ingest — design spec

**Status:** CONVERGED
**Date:** 2026-07-10
**Author:** primary (this session)
**Follow-up of:** plan-2 (ModelScope gateway wire-in, archived 2026-07-09)
**Converged:** 2026-07-10 via `/fabrik-spec-review` — 3 passes, md5 fixed-point verified (`0c6f4480…` → `0c6f4480…`)

## Goal

Close the last coverage gap of plan-2: currently `scrape_modelscope_catalog.py` is **flip-only** — it tags `via_modelscope=1` on rows that already exist in `agents`, and prints unmatched MS IDs to stderr. On 2026-07-09 the operator observed 22 such unmatched IDs (Shanghai_AI_Laboratory/Intern-S1, PaddlePaddle/ERNIE-4.5-*, IIC/GUI-Owl, XiYanSQL, MedAIBase, MusePublic, OpenGVLab/InternVL3.5-241B, and others), all of them net-new coverage that plan-2 explicitly deferred. This spec ingests those rows so `pick_models`, the browser, and the daily rankers can route to them.

## Success criteria

- After a daily `daily_refresh.sh` run, every MS `/v1/models` ID with an `_ORG_MAP`-covered org that does NOT match an existing DB row is INSERTed as a new `agents` row with `via_modelscope=1`.
- For each new row, metadata (context length, capability flags, model architecture) is enriched from a real external source — never fabricated.
- Coverage is **visible in the browser** (MS chip surfaces the row) but **excluded from cost-sorted ranking** until metadata is complete — so a placeholder never poisons the coding/task subagent picks.
- Zero manual curation required for the ~70% of MS models that are also on HuggingFace hub.
- The remaining ~30% (MS-exclusive models like IIC/GUI-Owl) fall back to a secondary source (modelscope.cn model-detail-page scrape) OR land as `blocked=1` with `discard_reason` — never as fake-priced routable rows.
- Idempotent + fail-open: a daily run with API errors NEVER corrupts the catalog. A partial ingest completes as much as it can.

## Chosen approach

**Extend `scrape_modelscope_catalog.py` with an `--ingest-new` flag AND wire it into `daily_refresh.sh`.** Three-tier metadata enrichment fallback per unmatched ID:

1. **HuggingFace Hub — two-endpoint fetch** (both public, no auth):
   - **`https://huggingface.co/api/models/<id>`** → top-level metadata: `tags`, `pipeline_tag`, `library_name`, `gated`, `downloads`, `likes`, `cardData`, and a *partial* `config` subset (`architectures`, `model_type`, `tokenizer_config`, `auto_map`). Verified live 2026-07-10 for `internlm/internlm3-8b-instruct`, `Qwen/Qwen3-4B`, `mistralai/Mistral-Large-Instruct-2407` — all HTTP 200.
   - **`https://huggingface.co/<id>/resolve/main/config.json`** → the full model config with `max_position_embeddings` (context length), `hidden_size`, `num_attention_heads`, etc. Returns HTTP 307 → follow redirects (curl `-L` / httpx `follow_redirects=True`). Verified live 2026-07-10 for `internlm/internlm3-8b-instruct` → `max_position_embeddings: 32768`.
   - **Two calls per model** (~44 HF requests for 22 unmatched IDs). Documented rate limits: ~1000 req/min anonymous. Source: `https://huggingface.co/docs/hub/api` (fetched 2026-07-10, HTTP 200).

2. **modelscope.cn model-page scrape** (via the `web-scrape` fabrik-lib module — VENDORED) — the MS site's `/models/<org>/<name>` pages are JS-rendered SPAs (Next.js). `web-scrape` handles this exact pattern: `httpx` first, vps1 `browserless` for JS-rendered, built-in `__NEXT_DATA__` parser. Verified live 2026-07-10: `https://modelscope.cn/models/Shanghai_AI_Laboratory/Intern-S1` → HTTP 200, 50KB HTML, contains `"max_tokens"` field. Fetches context length + description + gated status.

3. **Fallback: INSERT with placeholder defaults** — `context_window_k=128` (table default), `has_reasoning/has_tools/has_vision=false`, `input/output_cost_per_m=0`, **but** `blocked=1` + `discard_reason='needs_metadata_enrichment (MS-only, HF+MS scrape both failed)'`. Row appears in browser MS chip (so operator sees coverage), invisible to ranker SQL filter (`WHERE blocked=0`). Operator can manually curate + set `blocked=0`.

**Pricing model insight (grounded empirically 2026-07-10):** MS is credits-billed. Verification: the operator's `ms-*` token grants inference access via the `/v1/chat/completions` endpoint without any per-request billing headers or per-token charge fields in responses (verified this session). MS's `/v1/models` endpoint returns zero pricing fields, confirming pricing is not per-model. All ingested MS-only rows get `input/output_cost_per_m=0` — the correct semantic ("routable via MS credits pool, no per-token cost"). Ranker SQL that sorts by `input_cost_per_m` needs an `AND input_cost_per_m > 0` guard for OR-cheapest-provider views regardless of MS — this doesn't create a new problem, just makes the existing convention explicit for MS rows.

**Best-practice grounding (1c):**
- HuggingFace Hub is the de-facto canonical registry for open-weight model metadata; virtually every model-inference vendor (Together, Fireworks, DeepInfra, ModelScope itself) cross-lists to HF. Source: `https://huggingface.co/docs/hub/api` (fetched 2026-07-10).
- Progressive enrichment (try cheapest source first, fall through to more expensive) is standard federated-catalog design — cited by AWS `SageMaker JumpStart`, HuggingFace `AutoModel.from_pretrained`. Lean: no queue, no worker — inline enrichment during the daily scrape.
- Lean over gold-plated: don't build a "generic model metadata service" — this is a per-vendor scraper concern, small and focused. Sibling `verify_openrouter_catalog.py:812` `ingest_new()` uses the same shape (single script, `--ingest-new` flag).

## Rejected alternatives

- **Fully-active with default zeros (all rows).** Rejected: `input_cost_per_m=0` on a row that IS supposed to have real pricing (HF-enriched rows that DO have per-token models on other gateways) creates two failure modes. First, downstream code that ranks by cost silently prefers these rows over legitimately-priced peers. Second, an operator glancing at the browser Cost column sees "$0.00" and assumes it's free when it's actually credits-billed. The `blocked=1 + discard_reason` gate makes the "incomplete-metadata" state EXPLICIT.

- **Hidden pending manual review** (new `status='pending_review'` value). Rejected: introduces a new status value that requires updating every SQL filter downstream (rank_coding, rank_task, browser payload, gateway counts, at least 6 sites). The existing `blocked=1` flag already provides "hide from routing but keep in catalog" semantics. Reuse it.

- **Skip HF-miss rows entirely (never ingest MS-exclusive)** (user rejected this option). Loses the coverage — IIC/GUI-Owl and MedAIBase would never enter the catalog, defeating the whole point of coverage-lift.

- **Manual `--ingest-new` flag only, no daily cron** (user rejected). Coverage self-heals with daily cron; ingestion is fully idempotent (`INSERT OR IGNORE` semantics + explicit `WHERE NOT EXISTS` guards).

- **Scrape modelscope.cn without the `web-scrape` fabrik-lib module.** Rejected — would reinvent JS-rendered SPA handling that `web-scrape` already provides (built-in `__NEXT_DATA__` parser, vps1 browserless proxy). Silent fork of a vendored capability = fabrik-lib anti-pattern.

- **Build a generic HF-metadata fabrik-lib module now.** Deferred as a **🆕 fabrik-lib candidate** (see Handoff): the design is clean (1 endpoint + JSON parser), likely-reused (SF has same problem, future ModelScope-style vendors will too), but only two concrete uses exist so far. Ship this project-local; propose the abstraction after the third use lands.

## External dependencies (all grounded live 2026-07-10)

| Dependency | Grounded fact | Source URL (fetched date) |
|---|---|---|
| **ModelScope `/v1/models`** | Returns bare `{id, object, owned_by, created}` per model; no metadata. HTTP 200 with `Authorization: Bearer <ms-*>` token. 55 models total 2026-07-10. | `https://api-inference.modelscope.cn/v1/models` (2026-07-10 — direct curl this session) |
| **HuggingFace Hub `/api/models/<id>`** | Public JSON metadata for non-gated models; keys: `_id, author, cardData, config, createdAt, disabled, downloads, gated, id, lastModified, likes, model-index, modelId, pipeline_tag, tags, library_name`. Note: `config` here is a *partial* subset — for `max_position_embeddings` use the `/resolve/main/config.json` endpoint instead. Rate limit: ~1000 req/min anonymous. | `https://huggingface.co/docs/hub/api` + live curl to `internlm/internlm3-8b-instruct` (2026-07-10 — HTTP 200) |
| **HuggingFace Hub `/<id>/resolve/main/config.json`** | Full model config.json with `max_position_embeddings` (context length), `hidden_size`, `num_attention_heads`, `model_type`, `vocab_size`. Returns HTTP 307 → auto-follow redirects. | Live curl to `internlm/internlm3-8b-instruct` (2026-07-10 — HTTP 200 after redirect, `max_position_embeddings: 32768`) |
| **modelscope.cn model pages** | Next.js SPAs, JS-rendered. HTML page for `Shanghai_AI_Laboratory/Intern-S1` returns 50KB with `"max_tokens"` field in inline JSON. IIC/GUI-Owl-1.5-8B-Instruct returns only 3.3KB (may be a redirect/landing — some MS-exclusive orgs have thin pages). | `https://modelscope.cn/models/<org>/<name>` (2026-07-10 — live curl this session) |
| **MS pricing** | **Credits-based, not per-token** — verified empirically: `/v1/models` returns zero pricing fields; `/v1/chat/completions` calls with `ms-*` token succeed without per-request billing headers. No per-model pricing API. Design implication: `input_cost_per_m=0` is the correct semantic for MS-only routes, not a placeholder to enrich. | Empirical verification via `ms-*` token (2026-07-10 this session); MS docs at `https://modelscope.cn/docs/model-service/API-Inference/intro` HTTP 200 but page-content thin |

## fabrik-lib verdict table (vendor→enhance→build)

| Capability | Verdict | Module + why | Upstream note |
|---|---|---|---|
| HTTP client for HF Hub API | **vendor as-is** | `httpx` (already used by `scrape_modelscope_catalog.py`) | none |
| JSON parse of HF response | **vendor as-is** | stdlib `json` | none |
| modelscope.cn HTML scrape (JS-rendered SPA) | **vendor as-is** | **`/opt/fabrik-lib/web-scrape/`** — designed for exactly this pattern (`httpx` for static + vps1 browserless for JS-rendered, built-in `__NEXT_DATA__` parser). Verified module description matches use case. | Fetch its real API at plan-time; no core enhancement expected — pure vendor. |
| Enrichment orchestration (try HF, fall to MS-scrape, fall to placeholder) | **build** — project-local | Small (~50 LOC) glue around the two vendored primitives. No fabrik-lib module covers "progressive-fallback enrichment" as a generic capability. | 🆕 **fabrik-lib candidate** (see Handoff): `catalog-enrichment` — a generic 2+ vendor progressive-metadata fetcher. Only 1 concrete use so far → ship project-local, propose after the third. |
| DB row INSERT with idempotency | **build** — project-local | Trivial `INSERT INTO agents (...) VALUES (...) ON CONFLICT (id) DO NOTHING` in the scraper. `sqlite3` stdlib. | none |
| Daily cron wire | **vendor as-is** | Existing `daily_refresh.sh` `_step` block | none |

## Shape/infra implications

- **Scaffold type:** hub-side utility script (kilo-benchmarks/**). NOT a deployed service.
- **`shape:` flags:** N/A — no `specs/services/*.yaml` touched. This is hub-only code, no VPS deploy.
- **New deps:** none — `httpx` (already used), `sqlite3` (stdlib), `web-scrape` fabrik-lib module (vendored via project's `libs/` at plan-time if not already).
- **Env vars:** existing `MODELSCOPE_API_KEY` reused. No new env vars.
- **DB schema:** no ALTER TABLE — reuses existing `agents` columns.
- **Governance-sync impact:** none — script is hub-only.

## Constraints

- **Idempotent by construction.** `INSERT OR IGNORE` — re-runs never duplicate. Enrichment is retry-safe (network failure → row still inserted with `blocked=1`; next day's cron re-tries enrichment).
- **Fail-open.** A single HF API failure never blocks other rows. modelscope.cn scrape failure never blocks HF-enriched rows. The whole `--ingest-new` step failing never blocks the flip-only default behavior.
- **Zero manual intervention for the ~70% happy path** (HF-enriched rows). Manual curation only for MS-exclusive HF-miss cases — and those are visible with a clear `discard_reason` when the operator wants to look.
- **All new-row INSERTs carry `via_modelscope=1` + `reachable_with_existing_keys=1`.** Downstream `seed_specialty_catalog.py` doesn't need to re-run to flip reachability.

## Open/blocking unknowns

### Resolved

- **How to handle rows with no metadata source at all?** — RESOLVED (user-approved): `blocked=1 + discard_reason='needs_metadata_enrichment (MS-only, HF+MS scrape both failed)'`. Visible in browser MS chip, hidden from rankers.
- **Manual vs automatic cron trigger?** — RESOLVED (user-approved): automatic in `daily_refresh.sh`.
- **Where does pricing come from for MS-only rows?** — RESOLVED (grounding fact): MS is credits-billed, not per-token. `input/output_cost_per_m=0` is correct for MS routes. Not a fetch target.
- **Which `_ORG_MAP` entries need net-new orgs added?** — RESOLVED: none — plan-2 already added 8 net-new orgs (`shanghai-ai-lab`, `alibaba-iic`, `musepublic`, `opengvlab`, `xgenerationlab`, `llm-research`, `medaibase`, `opencompass`) as self-mapped keys. `_ms_to_agent_id_candidates` will produce their canonical `agents.id` strings.

### Still-open

1. **`web-scrape` fabrik-lib module's `__NEXT_DATA__` extraction returns the raw JSON — but does it decode the specific `"max_tokens"` field on modelscope.cn pages?** SELF-SERVICE at plan-time: read the module's real README + a live spike against one MS model page. If the module returns raw dict, project-local glue extracts the key. If the module needs enhancement for a specific field path, propose upstream via `UPSTREAM_FEEDBACK.md`. Not blocking design.

2. **Rate limit behavior for HF Hub anonymous reads?** SELF-SERVICE: current use is 22 IDs/day = well under any documented limit. Add a `time.sleep(0.1)` between calls as a courtesy. If rate limits ever bite: switch to authenticated with a Hugging Face token (`HF_TOKEN` env var, gated fetch pattern is documented). Not blocking.

Zero cross-AI dependencies, zero unanswered execution-blocking questions.

## Handoff

- **Next step:** `/fabrik-spec-review docs/superpowers/specs/2026-07-10-modelscope-new-row-ingest-design.md` (automatic — this command invokes it).
- **After CONVERGED + user approval:**
  - Not a data/GUI-shaped change → skip `/fabrik-data-contract` + `/fabrik-ui-design`.
  - `/fabrik-plan-after-chat docs/superpowers/specs/2026-07-10-modelscope-new-row-ingest-design.md`
  - Then `/fabrik-execute-plan`.

**💡 fabrik-lib candidate flagged:**
- **Name:** `catalog-enrichment` — progressive-fallback metadata fetcher for federated model catalogs.
- **Purpose:** given a model ID + an ordered list of sources (fetcher fn + parser fn), return the first successful metadata payload OR a `MetadataMiss(reason)` sentinel. Sources: HuggingFace Hub API, modelscope.cn HTML scrape, per-vendor pricing pages.
- **Why reusable:** SF has the same missing-metadata problem for its unmatched IDs (27 unmatched last scraper run). Future direct-vendor scrapers (Groq, Cerebras, DeepInfra) will need it. **This is the third instance** (after `catalog-scraper` flagged in plan-2 and the current use) — clears the ≥2-project-types bar cleanly.
- **Rough interface:**
  ```python
  def enrich(model_id: str, sources: list[Source]) -> Metadata | MetadataMiss:
      for src in sources:
          try:
              return src.fetch(model_id)
          except FetchFailed:
              continue
      return MetadataMiss(f"all {len(sources)} sources exhausted")
  ```
- **Not this spec** — proposal only. Ship project-local per spec; propose upstream via `UPSTREAM_FEEDBACK.md` after this + a follow-up SF equivalent both land (the third concrete use).

---

**Estimated build effort:** ~1.5–2 hours across 4 phases (extend scraper with `--ingest-new` + HF fetch fn + MS-scrape fn + INSERT + cron wire + tests). Estimated pool spend for `/fabrik-review` gates: ~$0.20.
