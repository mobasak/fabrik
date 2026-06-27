# Plan: OpenRouter routing — auto-refreshed per-category model picks in `.windsurf/rules/ai/`

**Status:** DRAFT
**Owner:** AI agents (Claude, other Code agents). Operator decides phase scope in chat.
**Created:** 2026-06-27
**Decision record dependency:** [`docs/reference/kilo/BENCHMARK_SOURCES.md`](../../reference/kilo/BENCHMARK_SOURCES.md) — §4.5 documents the observed gap this plan addresses.
**Convergence policy:** Status flips to **CONVERGED** only after **all** of the following are green:
1. `python scripts/final_gate.py --systemic --json` returns `"status":"success"`
2. `python scripts/enforcement/check_convergence.py` passes
3. The Self-audit (§13) lists zero open items.

---

## §1. Context — what we have today

The Fabrik daily WSL pipeline ([`scripts/wsl_startup_hook.sh`](../../../scripts/wsl_startup_hook.sh)) already:

- Pulls the OpenRouter chat-model catalog into `kilo_agents.db.agents` via [`scripts/kilo-benchmarks/kilo_agents_db.py`](../../../scripts/kilo-benchmarks/kilo_agents_db.py). The last successful pipeline run (`scripts/kilo-benchmarks/cache/update.log`, 2026-06-25) imported **337 chat models**.
- Pulls the OpenRouter embeddings catalog into `kilo_agents.db.embedding_models` via [`scripts/kilo-benchmarks/embedding_models_db.py:35`](../../../scripts/kilo-benchmarks/embedding_models_db.py#L35) (`OPENROUTER_EMBEDDINGS_URL`).
- Runs the deterministic embedding selection pipeline:
  - [`embedding_pre_filter.py`](../../../scripts/kilo-benchmarks/embedding_pre_filter.py) → shortlists
  - [`embedding_role_mapper.py`](../../../scripts/kilo-benchmarks/embedding_role_mapper.py) → `embedding_roles` + `embedding_roles_history`
  - [`embedding_export_markdown.py:209-247`](../../../scripts/kilo-benchmarks/embedding_export_markdown.py#L209-L247) → self-healing marker injection into `.windsurf/rules/core/65-rag-search.md`, `KILO_AGENT_SELECTION_GUIDE.md`, `KILO_MODEL_CAPABILITIES.md`
- Honors per-project LLM cost caps via the `core/cost-budget.md` pack (glob includes `**/openrouter*`).
- Accepts `llm_provider: openrouter` per service spec via [`src/fabrik/spec_loader.py:400-431`](../../../src/fabrik/spec_loader.py#L400-L431).

What is **missing**:

| Gap | Evidence |
|---|---|
| Per-category OpenRouter routes in `.windsurf/rules/ai/NN-*.md` packs | `grep -l 'OPENROUTER_ROUTES\|OPENROUTER_ID' .windsurf/rules/ai/*.md` → 0 hits |
| Daily auto-refresh of those routes | No script in `scripts/kilo-benchmarks/` mirrors `embedding_export_markdown.py` for chat categories |
| Quality scores for the 38 `:free` models | `SELECT count(*) FROM agents WHERE input_cost_per_m = 0 AND status = 'active' AND tbench_accuracy IS NOT NULL` → **0** (live query, 2026-06-27). Caused by [`update_kilo_benchmarks.py:60-61`](../../../scripts/kilo-benchmarks/update_kilo_benchmarks.py#L60-L61) `normalize_model_name()` not stripping the `:free` suffix before joining to the scraped scores. |

This plan closes those three gaps in **7 phases**, each with explicit validation gates and grounded in real code/schema/HTTP behavior.

---

## §1a. One-Test Rule

**Why:** Per [`core/45-testing-strategy.md`](../../../.windsurf/rules/core/45-testing-strategy.md), every ticket ships exactly one test for the highest-risk path. In this plan the highest-risk path is the `:free` ID normalization in Phase 0 — if it regresses, **all** benchmark-to-model joins break (e.g. `tbench_accuracy`, `arena_elo`, `weighted_coding` columns no longer populate for the 38 free-tier models), the role mapper picks stale data, and the failure is silent (rows just stay NULL).

**Contract:**

- **Given:** `kilo_agents.db` with at least one model row whose `id` ends in `:free` (e.g. `deepseek/deepseek-v4-flash:free`), AND the corresponding base ID (`deepseek/deepseek-v4-flash`) present on a scraped leaderboard (`scrape_benchmarks.py` cached output).
- **When:** `update_kilo_benchmarks.py --force` runs after the Phase 0 patch to `normalize_model_name()` is applied.
- **Then:** the `:free` row's `tbench_accuracy` / `arena_elo` / `coding_score` columns get populated from the base model's scraped score. Live SQL invariant: `SELECT count(*) FROM agents WHERE id LIKE '%:free' AND status='active' AND (tbench_accuracy IS NOT NULL OR arena_elo IS NOT NULL)` returns `> 0` (today's baseline: `0`).
- **Mocked:** nothing in the live integration test — runs against the real DB. The unit test (`tests/kilo_benchmarks/test_normalize_model_name.py` per §6.3) mocks nothing either — it's a pure-function test on the rewritten `normalize_model_name()`.

---

## §2. Constraints — binding rule packs

The following packs from [`.windsurf/rules/`](../../../.windsurf/rules/) are **binding** (from `scripts/select_rules.py` ACTIVE list on 2026-06-27):

| Pack | What it binds in this plan |
|---|---|
| `ai/00-ai-model-selection.md` | Routes must respect the INDEX-pack categories (10/20/30/.../90). No new category invented. |
| `core/10-python.md` | New scripts use stdlib `sqlite3` + sync only (match `embedding_role_mapper.py` style). No `asyncpg`/`pydantic`/FastAPI for benchmark tooling. |
| `core/15-api-contracts.md` | OpenRouter HTTP calls use bounded timeouts + retry-with-backoff; declared error shape. |
| `core/25-data-postgres.md` | Schema changes via additive migration (new column nullable; backfill; never drop). Mirror the chat-side pattern. |
| `core/40-documentation.md` | Doc Sync Matrix: every new file → INDEX.md row; every code change → CHANGELOG entry. Per-pack stamping uses canonical `Last content verification: YYYY-MM-DD` phrase ([`scripts/check_ai_pack_freshness.py:25-28`](../../../scripts/check_ai_pack_freshness.py#L25-L28)). |
| `core/45-testing-strategy.md` | 1 test per highest-risk path per phase. Phase 0 = normalization unit test. Phase 3/4 = selector + mapper integration test. |
| `core/50-code-review.md` | Self-review against this plan + rule packs before declaring a phase complete. |
| `core/55-observability.md` | Every new script logs `[script-name] <verb> <count> <noun>` to `update.log`, mirroring the `[embedding_export_markdown]` / `[ai-pack-freshness]` voice. |
| `core/58-resilience.md` | Scraper failures must keep last-good (overwrite-on-success only) and fail loud to the log; pipeline must continue. |
| `core/75-workers-jobs.md` | Daily pipeline is the "worker" surface — idempotent, lockfile-guarded, log-rotated. New steps inherit those guarantees from `wsl_startup_hook.sh`. |
| `core/cost-budget.md` | Selector must surface `input_cost_per_m` so routes can be cost-floored. The route mapper itself makes zero LLM calls (deterministic SQL only). |

Non-binding but consulted for shape: `ai/30-language.md`, `ai/60-code.md`, `ai/90-long-context.md` (route consumers). `core/65-rag-search.md` is the existing mirror; `embedding_export_markdown.py` is the canonical implementation we follow line-for-line.

---

## §3. Schema baseline — verified against live `kilo_agents.db` on 2026-06-27

### 3.1 `agents` table (chat models)

35 columns. Full list captured below. The ones the route mapper will read:

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PK | OpenRouter model ID (e.g. `deepseek/deepseek-v4-flash:free`) |
| `provider` | TEXT | Top-level provider slug |
| `input_cost_per_m`, `output_cost_per_m` | REAL | Already normalized to per-million by `kilo_agents_db.py`; OpenRouter raw is per-token (see §5) |
| `context_window_k` | INT | Thousands of tokens |
| `has_vision`, `has_tools`, `is_agentic`, `has_reasoning` | BOOLEAN | Already set from OpenRouter's `supported_parameters` + modalities |
| `arena_elo`, `tbench_accuracy`, `coding_score`, `livecodebench`, `swe_bench_pro`, `weighted_coding`, `humaneval_score` | REAL | The 4 WIRED benchmark sources land here per [`BENCHMARK_SOURCES.md`](../../reference/kilo/BENCHMARK_SOURCES.md) §2 |
| `output_tokens_per_sec`, `ttft_ms` | REAL | Artificial Analysis throughput/latency |
| `quality_tier`, `task_tier` | INT | Derived tiering (1=bulk, 2=mid, 3=frontier) |
| `is_ga` | INT | 1 if generally available; 0 if preview/free/beta/experimental ([`migrate_selector_columns.py:80`](../../../scripts/kilo-benchmarks/migrate_selector_columns.py#L80)) |
| `status` | TEXT | `'active'` is the working filter |
| `blocked`, `block_reason` | INT/TEXT | Blocklist; always filter `blocked = 0` |

### 3.2 `agent_roles` (existing, repurposed) — chat role pins

| Column | Type |
|---|---|
| `id` | INTEGER PK |
| `role` | TEXT (currently the chat-pipeline's role names; will be extended) |
| `agent_id` | TEXT FK → agents.id |
| `priority` | INT (1=primary, 2=fallback, etc.) |
| `reason`, `min_elo`, `assigned_by`, `assigned_at`, `score_used`, `score_type` | metadata |

Indexes: `idx_roles_role`, `idx_roles_agent` — sufficient for category-prefixed roles without schema change.

### 3.3 Mirror tables already exist for embeddings

| Table | Mirror columns |
|---|---|
| `embedding_models` | id, provider, input_cost_per_m, context_window_k, dimensions, is_multilingual, is_code_tuned, is_ga, quality_tier, status, blocked, last_verified, … |
| `embedding_roles` | id, role, model_id, priority, reason, score_used, score_type, assigned_by, assigned_at |
| `embedding_roles_history` | id, role, priority, model_id, snapshot_date, score_used, input_cost_per_m, assigned_by, created_at |

The chat side has `agents` + `agent_roles` + `agent_roles_history` (verified via `PRAGMA table_info` on 2026-06-27). **No new tables needed for this plan.**

---

## §4. Mirror baseline — files this plan replicates

| Existing file | Lines | This plan's mirror file |
|---|---|---|
| [`scripts/kilo-benchmarks/embedding_selector.py`](../../../scripts/kilo-benchmarks/embedding_selector.py) | 125 | New: `scripts/kilo-benchmarks/category_selector.py` (Phase 3) |
| [`scripts/kilo-benchmarks/embedding_role_mapper.py`](../../../scripts/kilo-benchmarks/embedding_role_mapper.py) | 198 | New: `scripts/kilo-benchmarks/category_route_mapper.py` (Phase 3) |
| [`scripts/kilo-benchmarks/embedding_export_markdown.py`](../../../scripts/kilo-benchmarks/embedding_export_markdown.py) | 329 | New: `scripts/kilo-benchmarks/category_export_markdown.py` (Phase 4) |
| [`scripts/kilo-benchmarks/embedding_role_configs.yaml`](../../../scripts/kilo-benchmarks/embedding_role_configs.yaml) | 75 | New: `scripts/kilo-benchmarks/ai_category_configs.yaml` (Phase 2) |

**Why mirror, not unify?** The chat side and embedding side share zero columns beyond `id`, `provider`, `input_cost_per_m`, `context_window_k`. The selection floors differ structurally (chat: `has_vision`/`has_tools`/`is_agentic`/`tbench_accuracy`; embeddings: `dimensions`/`is_multilingual`/`is_code_tuned`). The embedding side ships first, the chat side mirrors second — same pattern, separate code paths, deterministic.

The self-heal marker pattern in [`embedding_export_markdown.py:209-247`](../../../scripts/kilo-benchmarks/embedding_export_markdown.py#L209-L247) (shipped 2026-06-25 in commit `f3c8222`) is the canonical implementation; Phase 4 inlines its exact logic.

---

## §5. OpenRouter capabilities — verbatim extraction (2026-06-27)

Sourced via WebFetch by subagent `a94aea73f0dfd6b81` against live `https://openrouter.ai/api/v1/models` + docs pages.

### 5.1 Authentication

```
Authorization: Bearer ${OPENROUTER_API_KEY}
HTTP-Referer:  ${WEBSITE_URL}        (optional; needed only for leaderboard attribution)
X-OpenRouter-Title: ${APP_NAME}      (optional; paired with HTTP-Referer)
```

Env var name `OPENROUTER_API_KEY` is already in [`.env:310`](../../../.env) — value not echoed. Watchdog uses `WATCHDOG_OPENROUTER_KEY` ([`.env:355`](../../../.env)). Base URL: `https://openrouter.ai/api/v1/`.

### 5.2 `/api/v1/models` — exact JSON contract

Always-present fields (verified against 3 live sample entries):

```json
{
  "id":                "sakana/fugu-ultra",                  // OpenRouter model ID — joins to agents.id
  "canonical_slug":    "sakana/fugu-ultra-20260615",         // version-pinned slug
  "hugging_face_id":   null,
  "name":              "Sakana: Fugu Ultra",
  "created":           1782276303,                            // unix timestamp
  "description":       "Fugu Ultra is...",
  "context_length":    1000000,                               // → context_window_k = ceil(context_length / 1000)
  "architecture": {
    "modality":            "text+image->text",
    "input_modalities":    ["text", "image"],                 // → has_vision = "image" in input_modalities
    "output_modalities":   ["text"],
    "tokenizer":           "Other",                           // or "Gemini", etc.
    "instruct_type":       null
  },
  "pricing": {
    "prompt":              "0.000005",                        // string decimal, PER TOKEN — multiply by 1_000_000 for /M
    "completion":          "0.00003",
    "web_search":          "0.01",                            // optional, per-search
    "input_cache_read":    "0.0000005",                       // optional; 10% of prompt
    "input_cache_write":   "0.000000375",                     // optional
    "image":               "0.000002",                        // optional, per-image
    "audio":               "0.000002",                        // optional, per-audio-token
    "internal_reasoning":  "0.000012"                         // optional, reasoning-token cost
  },
  "top_provider": {
    "context_length":          1000000,
    "max_completion_tokens":   128000,
    "is_moderated":            false
  },
  "per_request_limits":   null,
  "supported_parameters": [                                   // CRITICAL: derive capability flags from here
    "include_reasoning", "reasoning", "structured_outputs",
    "tool_choice", "tools", "web_search_options"
  ],
  "default_parameters":   {},
  "supported_voices":     null,
  "knowledge_cutoff":     null,
  "expiration_date":      null,
  "links": { "details": "/api/v1/models/{canonical_slug}/endpoints" },
  "reasoning": {                                              // present ONLY in reasoning models
    "mandatory":           true,
    "default_enabled":     true,
    "supported_efforts":   ["max", "xhigh", "high"],
    "default_effort":      "xhigh"
  }
  // "benchmarks": {...}                                      // optional; never observed in 3 live samples
}
```

**Critical pricing detail**: `pricing.prompt` and `pricing.completion` are **JSON string decimals, per-token**. Current code in `kilo_agents_db.py` already multiplies by 1_000_000 to populate `input_cost_per_m` / `output_cost_per_m` — verify in §6.

### 5.3 Capability derivation rules (no schema change required)

```python
has_vision    = "image" in model["architecture"]["input_modalities"]
has_tools     = "tools" in model["supported_parameters"]
has_reasoning = "reasoning" in model and model["reasoning"].get("mandatory", False)
has_caching   = "input_cache_read" in model["pricing"]
context_window_k = (model["top_provider"]["context_length"] or model["context_length"]) // 1000
```

### 5.4 Free-tier semantics

- Free models are IDed by `:free` suffix in `id` (e.g. `deepseek/deepseek-v4-flash:free`).
- **Without purchased credits**: low daily RPD cap (docs: placeholder `{FREE_MODEL_NO_CREDITS_RPD}`, FAQ pegs at ~20–50 req/day). Limit-exceeded returns `402 Payment Required`.
- **With any credit purchased**: higher daily RPD on free models (docs: `{FREE_MODEL_HAS_CREDITS_RPD}`, exact number FAQ-only).
- Rate limits are **global per account** — adding API keys does not increase capacity.
- Quota endpoint: `GET /api/v1/key` returns remaining credits + usage metrics.

**Plan stance**: free models are PAUSE-state candidates ([`core/58-resilience.md`](../../../.windsurf/rules/core/58-resilience.md)), not P1 routes. The selector ranks them but flags them so the consumer can choose between "use free as Tier-3 fallback" or "block free for batch work". Driven by per-category `allow_free` flag in YAML, mirroring [`embedding_selector.py:84-88`](../../../scripts/kilo-benchmarks/embedding_selector.py#L84-L88).

### 5.5 Provider routing knobs

- `models: [a, b, c]` parameter on the chat request → ordered fallback chain. Triggers: context-exceeded, moderation block, provider rate-limit, provider downtime. Charged for whichever model actually responded (returned in response `model` field).
- `:nitro` suffix on model id → throughput-optimized provider variant.
- `:floor` suffix on model id → cheapest provider for that model.
- `plugins` parameter enables web search, PDF parsing, healing. Not used by this plan.

**Plan stance**: route mapper emits a P1 + P2 + P3 chain per category; the consumer (in this plan: rule packs / future spec) decides whether to forward the chain to OpenRouter via the `models` parameter.

### 5.6 Tool-calling / structured outputs

`supported_parameters` is the source of truth. Always set `has_tools = "tools" in supported_parameters`. OpenRouter claims OpenAI-compatible tool-call schema (`tools`, `tool_choice`, `finish_reason="tool_calls"`). Subagent flagged this as **assumed not verified**; the plan does not depend on tool-call ergonomics — it only flags which models support them.

### 5.7 Open uncertainties (logged for next AI to test, not blocking this plan)

| Uncertainty | Source | Mitigation in plan |
|---|---|---|
| Exact free-model RPD numbers | FAQ placeholders | YAML sets a conservative `notes: "treat free as ~20 rpd; require credits for production"`; not used as a numeric floor |
| BYOK exact fee % | "percentage-based" only | Plan does not depend on BYOK accounting |
| Tool-call response shape | OpenAI-compat claimed but not verified | Plan flags `has_tools` but does not invoke tools |
| Structured-outputs parameter name | Assumed `response_format` | Plan flags `supports_structured_outputs` from `supported_parameters` but does not invoke |
| Streaming SSE delta format | Assumed OpenAI | Plan does not stream |

---

## §6. Phase 0 — `:free` ID normalization fix

**Justification** (per `core/cost-budget.md` + `BENCHMARK_SOURCES.md` §4.5): observed gap — 38 free-tier models, 0 with quality scores.

### 6.1 Change

File: [`scripts/kilo-benchmarks/update_kilo_benchmarks.py:60-61`](../../../scripts/kilo-benchmarks/update_kilo_benchmarks.py#L60-L61)

Existing:
```python
def normalize_model_name(name: str) -> str:
    """Normalize model name for matching."""
    return name.lower().replace(" ", "-").replace("_", "-")
```

Proposed:
```python
def normalize_model_name(name: str) -> str:
    """Normalize model name for matching against scraped leaderboard entries.

    Strips OpenRouter routing suffixes (`:free`, `:nitro`, `:floor`,
    `:beta`, `:online`, `:thinking`) so the underlying model on the
    leaderboard joins to its `:free` variant in `agents.id`.
    """
    base = name.lower().replace(" ", "-").replace("_", "-")
    for suffix in (":free", ":nitro", ":floor", ":beta", ":online", ":thinking"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return base
```

The `FREE_MARKERS = (":free", "/free")` constant is duplicated in 3 files ([`llm_selector.py:47`](../../../scripts/kilo-benchmarks/llm_selector.py#L47), [`embedding_selector.py:27`](../../../scripts/kilo-benchmarks/embedding_selector.py#L27), [`embedding_models_db.py:56`](../../../scripts/kilo-benchmarks/embedding_models_db.py#L56)). **DO NOT** centralize in this phase — that's a refactor with separate blast radius. This phase touches one function.

### 6.2 Lookup-key expansion

In the same file at [`update_kilo_benchmarks.py:102-110, 112-120`](../../../scripts/kilo-benchmarks/update_kilo_benchmarks.py#L102-L120) the `for key in [model_lower, model_normalized]: if key in elo_map: …` loops also try the suffix-stripped variants. Specifically:

```python
keys_to_try = [model_lower, model_normalized]
# Also try stripping known OpenRouter suffixes from the lookup side
for suffix in (":free", ":nitro", ":floor", ":beta", ":online", ":thinking"):
    if model_lower.endswith(suffix):
        keys_to_try.append(model_lower[: -len(suffix)])
        keys_to_try.append(model_normalized[: -len(suffix)])
        break
```

### 6.3 Test (new file)

Create `tests/kilo_benchmarks/test_normalize_model_name.py`:

```python
from kilo_benchmarks_path_helper import import_update_kilo_benchmarks
m = import_update_kilo_benchmarks()

def test_strips_free_suffix():
    assert m.normalize_model_name("deepseek/deepseek-v4-flash:free") \
        == m.normalize_model_name("deepseek/deepseek-v4-flash")

def test_strips_nitro_floor_beta():
    for suf in (":nitro", ":floor", ":beta", ":online", ":thinking"):
        assert m.normalize_model_name(f"x/y{suf}") == "x/y"

def test_idempotent():
    n1 = m.normalize_model_name("Qwen 3.5 Plus")
    n2 = m.normalize_model_name(n1)
    assert n1 == n2

def test_no_double_strip():
    # Two suffixes back-to-back is unusual but should stop after one strip
    assert m.normalize_model_name("x/y:free:nitro") in {"x/y:free", "x/y"}
```

### 6.4 Validation gates

| Gate | Command | Pass criterion |
|---|---|---|
| G0.1 unit test | `.venv/bin/python -m pytest tests/kilo_benchmarks/test_normalize_model_name.py -q` | exit 0 |
| G0.2 dry-run pipeline | `cd scripts/kilo-benchmarks && .venv/bin/python update_kilo_benchmarks.py --force` | runs to completion; log shows `Updated N Elo + M TBench scores` with N>114 OR M>45 (last good run baseline) |
| G0.3 DB count | `SELECT count(*) FROM agents WHERE input_cost_per_m=0 AND status='active' AND (tbench_accuracy IS NOT NULL OR arena_elo IS NOT NULL)` | **> 0** (today: 0) |
| G0.4 final_gate | `.venv/bin/python scripts/final_gate.py --lean --json` | `"status":"success"` |

### 6.5 Evidence (to be filled when phase implemented)

- `path:line`: [`scripts/kilo-benchmarks/update_kilo_benchmarks.py:60-86`](../../../scripts/kilo-benchmarks/update_kilo_benchmarks.py#L60-L86) (diff)
- Command output: `pytest` summary + DB count delta + gate JSON

---

## §7. Phase 1 — `agent_categories` join table + classifier

A model may sit in multiple categories (e.g. an `is_agentic + has_vision + context_window_k >= 200` model fits agentic ∩ vision ∩ long-context). One TEXT column on `agents` cannot represent that. Schema is a **join table**, additive-only per [`core/25-data-postgres.md`](../../../.windsurf/rules/core/25-data-postgres.md):

### 7.1 Schema (one new table, one new index)

Migration script: new file [`scripts/kilo-benchmarks/migrate_ai_category_table.py`](../../../scripts/kilo-benchmarks/migrate_ai_category_table.py) mirroring [`migrate_selector_columns.py`](../../../scripts/kilo-benchmarks/migrate_selector_columns.py).

```sql
CREATE TABLE IF NOT EXISTS agent_categories (
    agent_id       TEXT NOT NULL,
    category       TEXT NOT NULL,
    classified_at  TIMESTAMP DEFAULT (datetime('now')),
    PRIMARY KEY (agent_id, category),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);
CREATE INDEX IF NOT EXISTS idx_agent_categories_category
    ON agent_categories(category);
```

Idempotent (`IF NOT EXISTS`). No change to `agents`. Existing indexes (`idx_agents_provider`, `idx_agents_status`, `idx_agents_task_tier`) cover the joins this plan adds.

### 7.2 Classifier — new file `scripts/kilo-benchmarks/classify_ai_category.py`

Pure-SQL, no LLM, deterministic. Inserts one row per (agent_id, category) pair using `INSERT OR REPLACE`. A model that matches multiple categories gets multiple rows. A model that matches none gets zero rows.

| Pack file | `category` value | SQL rule applied to `agents` |
|---|---|---|
| `ai/10-speech-audio.md` | `speech-audio` | `id LIKE '%whisper%' OR id LIKE '%audio%' OR id LIKE '%voice%' OR id LIKE '%tts%'` |
| `ai/20-vision.md` | `vision` | `has_vision = 1` |
| `ai/30-language.md` | `language` | `is_ga = 1 AND has_vision = 0 AND id NOT LIKE '%coder%' AND id NOT LIKE '%audio%'` (residual general LLMs) |
| `ai/40-multimodal.md` | `multimodal` | `has_vision = 1 AND has_tools = 1 AND has_reasoning = 1` |
| `ai/50-agentic.md` | `agentic` | `is_agentic = 1 AND has_tools = 1 AND has_reasoning = 1` |
| `ai/60-code.md` | `code` | `id LIKE '%coder%' OR id LIKE '%code%' OR weighted_coding > 0 OR humaneval_score > 0 OR coding_score > 0` |
| `ai/90-long-context.md` | `long-context` | `context_window_k >= 200` |

Packs **`ai/70-data-predictive.md`, `ai/80-specialized-domains.md`, `ai/25-3d-generation.md`** cover specialized non-LLM vendors per the packs' own text — classifier intentionally emits **zero rows** for them. They do not receive `OPENROUTER_ROUTES` blocks in Phase 4.

Pseudo-code shape:

```python
RULES = [
    ("speech-audio", "id LIKE '%whisper%' OR id LIKE '%audio%' "
                     "OR id LIKE '%voice%' OR id LIKE '%tts%'"),
    ("vision",       "has_vision = 1"),
    ("multimodal",   "has_vision = 1 AND has_tools = 1 AND has_reasoning = 1"),
    ("agentic",      "is_agentic = 1 AND has_tools = 1 AND has_reasoning = 1"),
    ("code",         "id LIKE '%coder%' OR id LIKE '%code%' "
                     "OR weighted_coding > 0 OR humaneval_score > 0 "
                     "OR coding_score > 0"),
    ("long-context", "context_window_k >= 200"),
    ("language",     "is_ga = 1 AND has_vision = 0 "
                     "AND id NOT LIKE '%coder%' AND id NOT LIKE '%audio%'"),
]

for category, where in RULES:
    conn.execute(
        f"INSERT OR REPLACE INTO agent_categories (agent_id, category) "
        f"SELECT id, ? FROM agents "
        f"WHERE status = 'active' AND blocked = 0 AND ({where})",
        (category,),
    )
```

### 7.4 Validation gates

| Gate | Command | Pass criterion |
|---|---|---|
| G1.1 migration idempotent | run twice in a row | second run is no-op (no error) |
| G1.2 classifier coverage | `SELECT count(DISTINCT agent_id) FROM agent_categories` | ≥ 200 (337 total chat models; expect ~200 to fit at least one category) |
| G1.3 every category populated | `SELECT category, count(*) FROM agent_categories GROUP BY category` | each of {speech-audio, vision, language, multimodal, agentic, code, long-context} has ≥ 1 row |
| G1.4 no orphans | `SELECT count(*) FROM agent_categories ac LEFT JOIN agents a ON a.id = ac.agent_id WHERE a.id IS NULL` | 0 |
| G1.5 gate | `.venv/bin/python scripts/final_gate.py --lean --json` | `"status":"success"` |

### 7.5 Evidence

- `path:line`: migration script + classifier
- Command output: G1.2 + G1.3 + G1.5 stdout

---

## §8. Phase 2 — `ai_category_configs.yaml`

Mirror [`embedding_role_configs.yaml`](../../../scripts/kilo-benchmarks/embedding_role_configs.yaml). New file [`scripts/kilo-benchmarks/ai_category_configs.yaml`](../../../scripts/kilo-benchmarks/ai_category_configs.yaml).

```yaml
# Category configurations for the OpenRouter route selection pipeline.
#
# Mirrors embedding_role_configs.yaml. Used by category_selector.py and
# category_route_mapper.py. Pure SQL, no LLM.
#
# Field semantics
# ---------------
# slots                  Number of priority slots per category (P1..Pn)
# min_quality_tier       1=bulk, 2=mid, 3=frontier
# min_context_window_k   Hard floor (thousands of tokens)
# require_tools          True → only has_tools = 1
# require_reasoning      True → only has_reasoning = 1
# require_vision         True → only has_vision = 1
# allow_free             False → exclude :free/_free IDs (rate-limited)
# stability_required     True → only is_ga = 1
# sort_key               Primary sort: 'input_cost_per_m ASC' or 'tbench_accuracy DESC'
# pack_file              Destination .windsurf/rules/ai/NN-*.md for the
#                        OPENROUTER_ROUTES marker block

categories:
  language:
    pack_file: .windsurf/rules/ai/30-language.md
    slots: 3
    min_quality_tier: 2
    min_context_window_k: 32
    allow_free: true            # rank free as Tier-3 fallback
    stability_required: false   # include free even though not GA
    sort_key: input_cost_per_m ASC
    notes: |
      Default LLM category. Free tier is included so the route ladder is
      P1=paid-mid, P2=paid-mid-cheaper, P3=free-fallback. Consumers decide
      to consume P3 or not via cost-budget.md.

  code:
    pack_file: .windsurf/rules/ai/60-code.md
    slots: 3
    min_quality_tier: 2
    min_context_window_k: 64
    require_tools: true
    allow_free: true
    stability_required: false
    sort_key: tbench_accuracy DESC
    notes: |
      Coding agents need long context (file imports, error context) + tools
      (edit/run). Sort by tbench_accuracy because we have observed scores
      and they map to real edit-test success.

  vision:
    pack_file: .windsurf/rules/ai/20-vision.md
    slots: 2
    require_vision: true
    allow_free: false           # vision-free models are rare/unstable
    stability_required: true
    sort_key: input_cost_per_m ASC
    notes: |
      Specialized vendors (Recraft/FLUX) own image GEN; vision packs cover
      VLM (vision-language) — only general-purpose LLMs with image input.

  multimodal:
    pack_file: .windsurf/rules/ai/40-multimodal.md
    slots: 2
    require_vision: true
    require_tools: true
    require_reasoning: true
    allow_free: false
    stability_required: true
    sort_key: input_cost_per_m ASC

  agentic:
    pack_file: .windsurf/rules/ai/50-agentic.md
    slots: 3
    require_tools: true
    require_reasoning: true
    allow_free: false           # agentic needs SLA, not free-quota
    stability_required: true
    sort_key: tbench_accuracy DESC

  long-context:
    pack_file: .windsurf/rules/ai/90-long-context.md
    slots: 2
    min_context_window_k: 200
    allow_free: true
    stability_required: false
    sort_key: context_window_k DESC

  speech-audio:
    pack_file: .windsurf/rules/ai/10-speech-audio.md
    slots: 1
    allow_free: false
    stability_required: true
    sort_key: input_cost_per_m ASC
    notes: |
      Most speech-audio capacity is via specialized vendors (Soniox per
      ai/00-ai-model-selection.md). Only one OpenRouter route emitted for
      models matching the speech-audio classifier rule.
```

### 8.1 Validation gates

| Gate | Command | Pass criterion |
|---|---|---|
| G2.1 YAML parse | `.venv/bin/python -c "import yaml; yaml.safe_load(open('scripts/kilo-benchmarks/ai_category_configs.yaml'))"` | exit 0 |
| G2.2 all categories cover a pack file | shell glob check | every `pack_file` exists |
| G2.3 gate | `.venv/bin/python scripts/final_gate.py --lean --json` | `"status":"success"` |

### 8.2 Evidence (to be filled when phase implemented)

- `path:line`: `scripts/kilo-benchmarks/ai_category_configs.yaml:1-<EOF>`
- Command output: G2.1 stdout + G2.3 JSON

---

## §9. Phase 3 — `category_selector.py` + `category_route_mapper.py`

### 9.1 `category_selector.py` (mirrors `embedding_selector.py`)

API:

```python
def select_for_category(
    cfg: dict,
    *,
    db_path: Path | str = DB_PATH,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Apply category floors against `agents JOIN agent_categories USING (agent_id ↔ id)`
    and return up to N rows ranked by the category's sort_key. Mirror of
    embedding_selector.select_for_role (line:38-125)."""
```

SQL skeleton (verified against schema in §3):

```sql
SELECT a.*
FROM agents a
JOIN agent_categories ac ON ac.agent_id = a.id
WHERE ac.category = ?
  AND a.status = 'active'
  AND a.blocked = 0
  AND a.quality_tier >= ?
  AND a.context_window_k >= ?
  AND a.input_cost_per_m >= 0
  -- conditional: AND a.has_tools = 1
  -- conditional: AND a.has_vision = 1
  -- conditional: AND a.has_reasoning = 1
  -- conditional: AND a.is_ga = 1
  -- conditional: AND (LOWER(a.id) NOT LIKE '%:free%' AND LOWER(a.id) NOT LIKE '%/free%')
ORDER BY {sort_key},
         COALESCE(a.arena_elo, 0) DESC,
         a.id ASC
LIMIT ?
```

Raises `NoEligibleCategoryError` mirroring [`NoEligibleEmbeddingError`](../../../scripts/kilo-benchmarks/embedding_selector.py#L34).

### 9.2 `category_route_mapper.py` (mirrors `embedding_role_mapper.py`)

Daily orchestrator. Writes:

- `agent_roles` rows with `role = 'openrouter:{category}'` and `assigned_by = 'category_route_mapper'`. The existing schema has zero blockers — `role` is `TEXT`, no FK to a roles table.
- `agent_roles_history` snapshot. Same.
- `scripts/kilo-benchmarks/openrouter_routes.json` (machine-readable mirror of `embedding_assignments.json`).
- `scripts/kilo_openrouter_routes_final.json` (Traycer/downstream consumer; mirror of `kilo_embeddings_final.json`).

Idempotent (same day → same output) per [`embedding_role_mapper.py:60-77`](../../../scripts/kilo-benchmarks/embedding_role_mapper.py#L60-L77) pattern.

### 9.3 Tests

`tests/kilo_benchmarks/test_category_selector.py` — mirrors `tests/kilo_benchmarks/test_embedding_selector.py`:
- floors enforcement (e.g. `require_vision: true` → vision-less rows excluded)
- `allow_free: false` excludes `:free` IDs
- `sort_key` ordering correct
- `NoEligibleCategoryError` when zero eligible

`tests/kilo_benchmarks/test_category_route_mapper.py`:
- Idempotency (run twice → same pin rows)
- History row count = pin row count per run
- Each category's slot count matches YAML

### 9.4 Validation gates

| Gate | Command | Pass criterion |
|---|---|---|
| G3.1 unit tests | `pytest tests/kilo_benchmarks/test_category_selector.py tests/kilo_benchmarks/test_category_route_mapper.py -q` | all pass |
| G3.2 smoke run | `cd scripts/kilo-benchmarks && .venv/bin/python category_route_mapper.py` | exit 0; log shows `Wrote N pins across M categories` |
| G3.3 DB invariant | `SELECT category, count(*) FROM (SELECT substr(role, 12) AS category FROM agent_roles WHERE assigned_by='category_route_mapper') GROUP BY category` | matches YAML slots per category |
| G3.4 JSON shape | `jq '.routes | length' scripts/kilo-benchmarks/openrouter_routes.json` | ≥ 7 (one per category, fewer if a category had no eligible) |
| G3.5 final_gate | `.venv/bin/python scripts/final_gate.py --lean --json` | `"status":"success"` |

### 9.5 Evidence (to be filled when phase implemented)

- `path:line`: `scripts/kilo-benchmarks/category_selector.py:<class>:<line>` + `scripts/kilo-benchmarks/category_route_mapper.py:<orchestrator>:<line>`
- Command output: G3.1 pytest summary + G3.3 SQL output + G3.5 JSON

---

## §10. Phase 4 — `category_export_markdown.py`

Mirrors [`embedding_export_markdown.py`](../../../scripts/kilo-benchmarks/embedding_export_markdown.py) **exactly** including the self-heal pattern at lines 209-247 (shipped 2026-06-25 commit `f3c8222`).

### 10.1 Marker contract per pack

Each `.windsurf/rules/ai/NN-*.md` pack receives a marker block:

```markdown
<!-- OPENROUTER_ROUTES:START (auto-managed by category_export_markdown.py) -->
*Auto-generated on YYYY-MM-DD (UTC) from `agent_roles` where `role` starts with `openrouter:`. Edits between markers will be overwritten on the next daily run.*

| Priority | OpenRouter ID                              | Cost ($/M in)   | Context | Status |
|---|---|---|---|---|
| P1 | `deepseek/deepseek-v4-flash:free`         | $0.00           | 1048k   | free  |
| P2 | `openai/gpt-5.5`                          | $5.00           | 200k    | paid  |
| P3 | `anthropic/claude-opus-4.8`               | $15.00          | 200k    | paid  |

To consume via Fabrik spec: `llm_provider: openrouter` + `llm_model: <P1 id>`. Fallback chain via OpenRouter `models: [P1, P2, P3]` parameter (see §5.5 of plan).
<!-- OPENROUTER_ROUTES:END -->
```

### 10.2 Self-heal contract

When markers absent (chat-pipeline regenerated host file): append `<marker>\n<body>\n<marker>` at end-of-file. Verbatim copy of [`embedding_export_markdown.py:209-247`](../../../scripts/kilo-benchmarks/embedding_export_markdown.py#L209-L247).

### 10.3 Pack stamping

Phase 4 ALSO ensures each touched pack has a `Last content verification: YYYY-MM-DD` line (per [`check_ai_pack_freshness.py:25-28`](../../../scripts/check_ai_pack_freshness.py#L25-L28) regex). The route-injection itself counts as the verification — the line is updated by `category_export_markdown.py` on every successful write, scoped to packs it actually injected into. Packs that have a stamp earlier than today get refreshed; packs that lack the stamp entirely get it added immediately after the title.

### 10.4 Validation gates

| Gate | Command | Pass criterion |
|---|---|---|
| G4.1 unit tests | `pytest tests/kilo_benchmarks/test_category_export_markdown.py -q` | all pass (marker-absent self-heal; marker-present replace; pack stamp refresh) |
| G4.2 idempotent | run script twice, `git diff .windsurf/rules/ai/` | empty after 2nd run (within YYYY-MM-DD precision) |
| G4.3 freshness check now green | `.venv/bin/python scripts/check_ai_pack_freshness.py` | every stamped pack reports `verified Nd ago` with N < 7 |
| G4.4 markdown lint | `markdownlint .windsurf/rules/ai/30-language.md` | exit 0 (no MD060/MD032 violations introduced) |
| G4.5 final_gate | `.venv/bin/python scripts/final_gate.py --lean --json` | `"status":"success"` |

### 10.5 Evidence (to be filled when phase implemented)

- `path:line`: `scripts/kilo-benchmarks/category_export_markdown.py:<self-heal>:<line>` (mirror of `embedding_export_markdown.py:209-247`)
- Command output: G4.2 git-diff empty + G4.3 freshness output + G4.5 JSON

---

## §11. Phase 5 — Pipeline wiring

### 11.1 Insertion point in `wsl_startup_hook.sh`

Current state ([`scripts/wsl_startup_hook.sh:95-108`](../../../scripts/wsl_startup_hook.sh#L95-L108)):

```bash
cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $EMBEDDING_DB_SCRIPT all >> $LOG_FILE 2>&1 && \
cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $EMBEDDING_PREFILTER_SCRIPT >> $LOG_FILE 2>&1 && \
cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $EMBEDDING_MAPPER_SCRIPT >> $LOG_FILE 2>&1 && \
cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $EMBEDDING_MARKDOWN_SCRIPT >> $LOG_FILE 2>&1
fi
# === AI RULE PACK FRESHNESS CHECK (warn-only) ===
# ...
$VENV_PYTHON $AI_PACK_FRESHNESS_SCRIPT >> $LOG_FILE 2>&1
cd $FABRIK_ROOT && bash $EXTENSIONS_SCRIPT >> $LOG_FILE 2>&1
```

After embedding pipeline's closing `fi` and **before** the freshness check, insert:

```bash
        # === OPENROUTER CATEGORY ROUTING ===
        # Reads agents + agent_categories, writes openrouter:{category} pins
        # to agent_roles, then injects OPENROUTER_ROUTES markers into the 7
        # ai/NN-*.md packs. Independent failure: a broken routing step must
        # NOT kill the freshness check or extensions sync below, so this
        # runs OUTSIDE the embedding && chain.
        if [ ! -f /tmp/.openrouter_routing_disabled ]; then
            cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $CATEGORY_CLASSIFIER_SCRIPT >> $LOG_FILE 2>&1
            cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $CATEGORY_MAPPER_SCRIPT >> $LOG_FILE 2>&1
            cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $CATEGORY_MARKDOWN_SCRIPT >> $LOG_FILE 2>&1
        fi
```

Plus the corresponding script-path variables at lines 27-44 of `wsl_startup_hook.sh`:

```bash
CATEGORY_CLASSIFIER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/classify_ai_category.py"
CATEGORY_MAPPER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/category_route_mapper.py"
CATEGORY_MARKDOWN_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/category_export_markdown.py"
```

Header comment update — current state (verified via `grep -n '^# [0-9]' wsl_startup_hook.sh`):

```bash
# 5. Kilo agent workflow (daily, deterministic — no LLM):
# 6. AI rule pack freshness check (warn-only): warns in update.log ...
# 7. Extensions sync: auto-update Windsurf extensions documentation (daily)
```

New state — insert new step 6, push 6→7, 7→8:

```bash
# 5. Kilo agent workflow (daily, deterministic — no LLM):
# 6. OpenRouter category routing (daily, deterministic): classifies models
#    into the 7 ai/NN-*.md packs, ranks per-category, injects
#    OPENROUTER_ROUTES markers. Pure SQL, no LLM, no network calls beyond
#    what step 5 already made.
# 7. AI rule pack freshness check (warn-only): warns in update.log ...
# 8. Extensions sync: auto-update Windsurf extensions documentation (daily)
```

Renumbering convention follows the precedent set by commit `4ca38bf` (the freshness check insertion).

### 11.2 Failure semantics

- Lockfile `/tmp/.openrouter_routing_disabled` lets operator kill the step without editing the hook.
- The block runs OUTSIDE the embedding `&&` chain — its failure does not kill freshness/extensions.
- Each script logs `[script-name] ...` lines on success/failure. The `>> $LOG_FILE 2>&1` ensures errors land in `update.log` even when the pipeline backgrounds.

### 11.3 Validation gates

| Gate | Command | Pass criterion |
|---|---|---|
| G5.1 syntax | `bash -n scripts/wsl_startup_hook.sh` | exit 0 |
| G5.2 dry-run | `bash -x scripts/wsl_startup_hook.sh 2>&1 \| head -40` | shows the 3 new script invocations in order, after embedding step, before freshness check |
| G5.3 lockfile bypass | `touch /tmp/.openrouter_routing_disabled && bash -x scripts/wsl_startup_hook.sh 2>&1 \| grep openrouter` | 0 invocations |
| G5.4 manifest sync | `grep openrouter scripts/fabrik_synced_manifest.py` | new scripts intentionally NOT synced (hub-only tooling) |
| G5.5 final_gate | `.venv/bin/python scripts/final_gate.py --lean --json` | `"status":"success"` |

### 11.4 Evidence (to be filled when phase implemented)

- `path:line`: `scripts/wsl_startup_hook.sh:<new-block>:<line>` + variables added at lines 27-44 range
- Command output: G5.1 + G5.2 + G5.5 stdout

---

## §12. Phase 6 — Cross-link + workflow doc + CHANGELOG

### 12.1 Update workflow doc

Append a section to [`docs/workflows/KILO_BENCHMARK_WORKFLOW.md`](../../workflows/KILO_BENCHMARK_WORKFLOW.md) named **"OpenRouter category routing (sibling, daily)"** mirroring the existing "AI rule pack freshness check (sibling, warn-only)" section structure. Includes:

- One-paragraph what-it-does
- The 7 categories table
- Output shape in `cache/update.log`
- Cross-link to this plan
- Cross-link to [`BENCHMARK_SOURCES.md`](../../reference/kilo/BENCHMARK_SOURCES.md)

### 12.2 Update INDEX.md

Per Doc Sync Matrix in CLAUDE.md: file added → INDEX.md row. INDEX.md is a project-tree-shape file at root (verified: groups entries by parent directory, not per-file). Per the existing INDEX convention (`scripts/kilo-benchmarks/` is listed as a single bucket, not file-by-file), the only entry to add is the consumer artifact:

- `scripts/kilo_openrouter_routes_final.json` — the Traycer/downstream consumer mirror of `kilo_embeddings_final.json` (which IS in INDEX). Per [`scripts/enforcement/check_doc_sync.py`](../../../scripts/enforcement/check_doc_sync.py) — `_is_significant_code` does not flag YAML config or per-script test additions inside an already-indexed bucket; verify in G6.1 before declaring done.

If `check_doc_sync.py` does flag any new file, add a bucket line not per-file (mirror the existing INDEX entry style for the `scripts/kilo-benchmarks/` cluster).

### 12.3 CHANGELOG entries

One entry per phase under `## [Unreleased]`. Categories: `Added` for new scripts; `Fixed` for the `:free` normalization fix.

### 12.4 Validation gates

| Gate | Command | Pass criterion |
|---|---|---|
| G6.1 doc sync matrix | `.venv/bin/python scripts/enforcement/check_doc_sync.py` | exit 0 |
| G6.2 doc sprawl | `.venv/bin/python scripts/enforcement/check_doc_sprawl.py` | exit 0 |
| G6.3 final_gate | `.venv/bin/python scripts/final_gate.py --lean --json` | `"status":"success"` |

### 12.5 Evidence (to be filled when phase implemented)

- `path:line`: `docs/workflows/KILO_BENCHMARK_WORKFLOW.md:<new-section>:<line>` + `INDEX.md:<consumer-row>:<line>` + `CHANGELOG.md:<Unreleased>:<line>`
- Command output: G6.1 + G6.2 + G6.3 stdout

---

## §13. Self-audit (per `check_convergence.py`)

| Item | Status |
|---|---|
| Every Phase has Evidence section with at least 1 `path:line` + 1 command output block | ⏳ to be filled per phase as implemented |
| OpenRouter capability claims grounded in scrape extraction (§5) | ✅ — subagent `a94aea73f0dfd6b81` 2026-06-27 |
| DB schema claims grounded in live `PRAGMA table_info` | ✅ — 2026-06-27 live query |
| All mirror references include line ranges | ✅ — every mirror cites `path:line` |
| Validation gates per phase | ✅ — every phase has a G{n}.x table |
| Terminal gate = `final_gate.py` | ✅ — §14 |
| `core/40-documentation.md` doc-sync matrix satisfied | ⏳ — Phase 6 closes this |
| No new external dependency added | ✅ — uses stdlib `sqlite3`, `pyyaml`, `requests` already present |
| `core/cost-budget.md` honored — zero LLM calls in daily pipeline | ✅ — pure SQL deterministic |
| Open uncertainties listed and bounded (§5.7) | ✅ — none block this plan |
| Rule pack `ai/00-ai-model-selection.md` semantics preserved | ✅ — routes augment, don't replace, the curated lineup |

Open items: items marked ⏳ flip to ✅ as each phase ships. Plan moves to `CONVERGED` only when all rows are ✅ AND §14 terminal gate is green.

---

## §14. Terminal validation gate

The plan is CONVERGED only when:

```bash
.venv/bin/python scripts/final_gate.py --systemic --json
# → "status": "success"
.venv/bin/python scripts/enforcement/check_convergence.py
# → exit 0
.venv/bin/python -m pytest tests/kilo_benchmarks/ -q
# → all pass
.venv/bin/python scripts/check_ai_pack_freshness.py
# → all 7 routed packs show "verified Nd ago" with N < 7
```

All four MUST return success. Any failure means a phase regressed and the plan returns to DRAFT.

---

## §15. What we are NOT doing (out of scope)

| Out of scope | Why |
|---|---|
| Wiring SWE-bench / LiveCodeBench / Aider Polyglot | `BENCHMARK_SOURCES.md` §3 marks all CONDITIONAL with trigger conditions; none have fired |
| Centralizing `FREE_MARKERS` constant across 3 files | Refactor with separate blast radius; explicitly punted in §6.1 |
| Tool-call invocation against OpenRouter | Plan only flags `has_tools`; invocation is a consumer concern |
| Streaming SSE handling | Plan only flags `has_streaming`; not invoked |
| Retiring Chatbot Arena | `BENCHMARK_SOURCES.md` §4.4 names the trigger (4-week zero-weight observation); separate decision |
| Adding `agents.ai_category` single-value column | Superseded by `agent_categories` join table in §7.3 |

---

## §16. Rollback procedure (per `core/58-resilience.md`)

If any phase ships and then needs reverting:

| Phase | Rollback |
|---|---|
| Phase 0 (`:free` normalization) | `git revert <commit>` — single-function change in one file |
| Phase 1 (`agent_categories` table) | `DROP TABLE agent_categories; DROP INDEX idx_agent_categories_category;` + `git revert` migration script |
| Phase 2 (YAML config) | delete file |
| Phase 3 (selector + mapper) | delete files + `DELETE FROM agent_roles WHERE assigned_by='category_route_mapper'; DELETE FROM agent_roles_history WHERE assigned_by='category_route_mapper'` |
| Phase 4 (markdown export) | delete script + remove `OPENROUTER_ROUTES` blocks from packs |
| Phase 5 (pipeline wiring) | `touch /tmp/.openrouter_routing_disabled` (immediate); revert `wsl_startup_hook.sh` (permanent) |
| Phase 6 (docs) | `git revert` |

No phase mutates external systems — every change is local to `/opt/fabrik/`. No deploy, no DNS, no DB outside the local SQLite file. Rollback is purely git+SQL.

---

## §17. Sequencing

| # | Phase | Effort | Blocks |
|---|---|---|---|
| 1 | §6 Phase 0 (`:free` normalization) | ~20 LOC + 1 test file | Phase 3 (selector needs scored free models to consider) |
| 2 | §7 Phase 1 (`agent_categories` table + classifier) | ~100 LOC + migration | Phase 2, 3 |
| 3 | §8 Phase 2 (YAML config) | ~70 LOC | Phase 3 |
| 4 | §9 Phase 3 (selector + mapper + tests) | ~250 LOC | Phase 4 |
| 5 | §10 Phase 4 (markdown export + tests) | ~250 LOC | Phase 5 |
| 6 | §11 Phase 5 (pipeline wiring) | ~15 LOC | Phase 6 |
| 7 | §12 Phase 6 (cross-link + INDEX + CHANGELOG) | ~30 LOC | Terminal gate |

**Estimated total**: ~735 LOC across 7 phases + 4 test files. Mirrors the embedding pipeline structure 1:1.

---

## §18. Related references

- Decision record: [`docs/reference/kilo/BENCHMARK_SOURCES.md`](../../reference/kilo/BENCHMARK_SOURCES.md)
- Mirror canonical implementation: [`scripts/kilo-benchmarks/embedding_export_markdown.py`](../../../scripts/kilo-benchmarks/embedding_export_markdown.py) (commit `f3c8222`)
- Hub guard precedent: [`src/fabrik/scaffold.py::_assert_not_hub`](../../../src/fabrik/scaffold.py) (commit `4ca38bf`)
- Freshness check pattern: [`scripts/check_ai_pack_freshness.py`](../../../scripts/check_ai_pack_freshness.py) (commit `4ca38bf`)
- OpenRouter scrape: subagent `a94aea73f0dfd6b81` 2026-06-27 (verbatim extraction in §5)
- AI INDEX pack: [`.windsurf/rules/ai/00-ai-model-selection.md`](../../../.windsurf/rules/ai/00-ai-model-selection.md)
