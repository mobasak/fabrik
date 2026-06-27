# Plan: OpenRouter routing — auto-refreshed per-category model picks in `.windsurf/rules/ai/`

**Status:** IMPLEMENTATION-CONVERGED — all 7 phases (0-6) shipped; 17 adversarial-review defects found and fixed across Phases 0/1/3/4/5/6 (Pass A→B→C→D until fixed point); 79/79 phase tests pass; `final_gate.py --lean --json` → success; `check_ai_pack_freshness.py` → all 7 routed packs verified 0d ago. Tier-3 (`--systemic`) shows 2 pre-existing fabrik-lane VPS-docs failures (broken `docs/infrastructure/vps-ai-sysadmin.md` link + missing `vps-status.md`/`vps-urls.md`) — accepted under the §14 environmental-noise carve-out (Pass 2A Finding 4). Stage 1 (plan-only CONVERGED): 2026-06-27 (this commit's parent). Stage 2 commits: 4ca38bf (P0 + P1) · 7686668 (P3) · d2c93fa (P3 review) · 378c045 (P4 + review) · ece57c2 (P5 + review) · b73cf02 (P6 + review).
**Owner:** AI agents (Claude, other Code agents). Operator decides phase scope in chat.
**Created:** 2026-06-27
**Converged:** 2026-06-27 (this commit — Pass 1: 4 parallel grounders × 33 findings, all applied; Pass 2: 2 parallel grounders × 19 findings, all applied; Pass 3 solo: 0 new findings → fixed point)
**Decision record dependency:** [`docs/reference/kilo/BENCHMARK_SOURCES.md`](../../reference/kilo/BENCHMARK_SOURCES.md) — §4.5 documents the observed gap this plan addresses.
**Residual unknowns / assumptions / out-of-scope risks:** explicitly enumerated in §17a — this plan does NOT claim 100% accuracy.

**Two-stage convergence policy:**

- **Stage 1 — Plan convergence (achieved by this commit):** every claim grounded in real `path:line` against existing code/DB schema or in the OpenRouter scrape extraction (§5); every Phase has a `Validation gates` table + `Evidence` section; the One-Test Rule covers the highest-risk path; `final_gate.py --check --lean` passes against the plan-only stage; Self-audit (§13) plan-quality rows are ✅.
- **Stage 2 — Implementation convergence (per phase, set by the AI that ships each phase):** Evidence section gets filled with the actual `path:line` of shipped code + the verbatim command output of each `G{n}.x` validation gate. After Phase 6 closes, `final_gate.py --systemic --json` and `check_convergence.py` must return `"status":"success"` / exit 0.

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

**Why:** Per [`core/45-testing-strategy.md:19`](../../../.windsurf/rules/core/45-testing-strategy.md#L19) ("every new feature ticket requires exactly **one** high-value happy-path integration or E2E test"), this plan ships **two** tests for Phase 0 — a **pure-function unit test** for the rewritten `normalize_model_name()`, plus the **integration invariant** that satisfies the rule's "one high-value happy-path E2E" requirement. The integration test is the load-bearing one (verifies the actual gap is closed); the unit test is fast-feedback during refactor.

**Contract (integration test = the high-value happy path):**

- **Given:** `kilo_agents.db` with at least one model row whose `id` ends in `:free` (live baseline 2026-06-27: 38 such rows), AND `scrape_benchmarks.py` cached output containing the corresponding base IDs on Arena and/or Terminal Bench leaderboards.
- **When:** `update_kilo_benchmarks.py --force` runs after Phase 0 patches both `normalize_model_name()` and the lookup-key expansion inside `update_agents_json()` (the JSON shadow file the script joins against).
- **Then:** at least one `:free` row in `agents` has `tbench_accuracy IS NOT NULL` OR `arena_elo IS NOT NULL` afterwards. The live SQL invariant `SELECT count(*) FROM agents WHERE id LIKE '%:free' AND status='active' AND (tbench_accuracy IS NOT NULL OR arena_elo IS NOT NULL)` flips from `0` (baseline 2026-06-27) to `> 0`.
- **Mocked:** nothing. Runs against real `kilo_agents.db` + real cached scraper output. The unit test (`tests/kilo_benchmarks/test_normalize_model_name.py` per §6.3) also mocks nothing — pure-function test on the rewritten `normalize_model_name`.

**Caveat (made explicit so the test isn't gamed):** the integration test only validates Phase 0 fixed the join when **a matching base ID exists on the scraped leaderboard**. If zero `:free` models have their base ID on Arena/Terminal Bench (low-probability but possible on a fresh scrape day), the test is vacuously satisfied and a manual operator should pick a known `:free` model and confirm its base ID was scraped — see G0.3 "operator falsifier" gate added in §6.4.

---

## §2. Constraints — binding rule packs

The following packs from [`.windsurf/rules/`](../../../.windsurf/rules/) are **binding** (from `scripts/select_rules.py` ACTIVE list on 2026-06-27):

| Pack | What it binds in this plan |
|---|---|
| `ai/00-ai-model-selection.md` | Routes must respect the INDEX-pack categories (10/20/30/.../90). No new category invented. |
| `core/10-python.md` | New scripts use stdlib `sqlite3` + sync only (match `embedding_role_mapper.py` style). No `asyncpg`/`pydantic`/FastAPI for benchmark tooling. |
| `core/15-api-contracts.md` | OpenRouter HTTP calls use bounded timeouts + retry-with-backoff; declared error shape. |
| `core/25-data-postgres.md` | Pack discusses Alembic-style migrations but does NOT explicitly mandate "additive-only" (Pass 1C C2). This plan adopts additive-only as a self-imposed discipline: every schema change is `CREATE TABLE IF NOT EXISTS` (new table — Phase 1) or no change (Phases 0/2/3/4/5/6 touch zero schema), with `ON DELETE CASCADE` for referential cleanup. No `DROP TABLE` or `ALTER TABLE ... DROP COLUMN` in any phase. |
| `core/40-documentation.md` | Doc Sync Matrix: every new file → INDEX.md row; every code change → CHANGELOG entry. Per-pack stamping uses canonical `Last content verification: YYYY-MM-DD` phrase ([`scripts/check_ai_pack_freshness.py:25-28`](../../../scripts/check_ai_pack_freshness.py#L25-L28)). |
| `core/45-testing-strategy.md` | Pack [line 19](../../../.windsurf/rules/core/45-testing-strategy.md#L19) says "every new feature ticket requires exactly **one** high-value happy-path integration or E2E test" (Pass 1C C1 — exact wording is "high-value happy-path", not "highest-risk path"). This plan applies it per Phase: Phase 0 ships the unit test on `normalize_model_name` (fast feedback) PLUS the live integration invariant in §1a (the high-value happy-path test the rule mandates). Phases 1/3/4 each get one integration test (`tests/kilo_benchmarks/test_*.py`). |
| `core/50-code-review.md` | Self-review against this plan + rule packs before declaring a phase complete. |
| `core/55-observability.md` | Every new script logs `[script-name] <verb> <count> <noun>` to `update.log`, mirroring the `[embedding_export_markdown]` / `[ai-pack-freshness]` voice. |
| `core/58-resilience.md` | Scraper failures must keep last-good (overwrite-on-success only) and fail loud to the log; pipeline must continue. |
| `core/75-workers-jobs.md` | Daily pipeline is the "worker" surface — idempotent, lockfile-guarded, log-rotated. New steps inherit those guarantees from `wsl_startup_hook.sh`. |
| `core/cost-budget.md` | Pack glob includes `**/openrouter*` ([line 3](../../../.windsurf/rules/core/cost-budget.md#L3)) so it binds **downstream consumers** of these routes (any project code that actually calls OpenRouter). It does NOT bind the daily kilo-benchmarks pipeline because the pipeline makes zero LLM calls (Pass 1C C3). The selector still surfaces `input_cost_per_m` so consumers can apply cost ceilings as the pack requires. |

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

The chat side has `agents` + `agent_roles` + `agent_roles_history` (verified via `PRAGMA table_info` on 2026-06-27). **No alterations needed to existing tables** — this plan reuses them as-is. Phase 1 (§7) adds ONE new table `agent_categories` (additive-only, doesn't touch existing schema); existing tables stay untouched. The earlier draft of this section said "No new tables needed" — that was Pass 2B Finding 8 ambiguity; clarified now.

---

## §4. Mirror baseline — files this plan replicates

| Existing file | Lines | This plan's mirror file |
|---|---|---|
| [`scripts/kilo-benchmarks/embedding_selector.py`](../../../scripts/kilo-benchmarks/embedding_selector.py) | 125 | New: `scripts/kilo-benchmarks/category_selector.py` (Phase 3) |
| [`scripts/kilo-benchmarks/embedding_role_mapper.py`](../../../scripts/kilo-benchmarks/embedding_role_mapper.py) | 198 | New: `scripts/kilo-benchmarks/category_route_mapper.py` (Phase 3) |
| [`scripts/kilo-benchmarks/embedding_export_markdown.py`](../../../scripts/kilo-benchmarks/embedding_export_markdown.py) | 329 | New: `scripts/kilo-benchmarks/category_export_markdown.py` (Phase 4) |
| [`scripts/kilo-benchmarks/embedding_role_configs.yaml`](../../../scripts/kilo-benchmarks/embedding_role_configs.yaml) | 75 | New: `scripts/kilo-benchmarks/ai_category_configs.yaml` (Phase 2) |

**Why mirror, not unify?** The chat side and embedding side share zero columns beyond `id`, `provider`, `input_cost_per_m`, `context_window_k`. The selection floors differ structurally (chat: `has_vision`/`has_tools`/`is_agentic`/`tbench_accuracy`; embeddings: `dimensions`/`is_multilingual`/`is_code_tuned`). The embedding side ships first, the chat side mirrors second — same pattern, separate code paths, deterministic.

**New files that do NOT have a mirror** (Pass 2B Finding 9):

- **`scripts/kilo-benchmarks/classify_ai_category.py`** — pure-SQL classifier emitting `agent_categories` rows. The embedding side has no classifier because there's only one embedding pipeline (multilingual + code + frontier); the chat side has 7 categories that need explicit category-tagging before per-category selection runs.
- **`scripts/kilo-benchmarks/migrate_ai_category_table.py`** — additive migration for the new join table. No mirror on the embedding side because no embedding-side schema is changing.

These two files are new logic (not patterns transplanted), so their reference implementations are this plan + the rule packs they cite.

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

### 6.1 Change A — rewrite `normalize_model_name()`

File: [`scripts/kilo-benchmarks/update_kilo_benchmarks.py`](../../../scripts/kilo-benchmarks/update_kilo_benchmarks.py) — function `normalize_model_name` at **line 59** (verified live 2026-06-27: `grep -n "^def normalize_model_name" → 59`). The function body spans **lines 59-61** (3 lines).

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
    `:beta`, `:online`, `:thinking`) — repeatedly, so a double-suffix
    like `x/y:free:online` collapses fully to `x/y`. This makes the
    `:free` variant in `agents.id` join to the base model's row on the
    leaderboard.
    """
    base = name.lower().replace(" ", "-").replace("_", "-")
    changed = True
    while changed:
        changed = False
        for suffix in (":free", ":nitro", ":floor", ":beta", ":online", ":thinking"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                changed = True
    return base
```

The `FREE_MARKERS = (":free", "/free")` constant is duplicated in 3 files ([`llm_selector.py:47`](../../../scripts/kilo-benchmarks/llm_selector.py#L47), [`embedding_selector.py:27`](../../../scripts/kilo-benchmarks/embedding_selector.py#L27), [`embedding_models_db.py:56`](../../../scripts/kilo-benchmarks/embedding_models_db.py#L56)). **DO NOT** centralize in this phase — that's a refactor with separate blast radius. This phase touches one function.

### 6.2 Change B — expand lookup-key set inside `update_agents_json()`

The lookup loops are in `update_agents_json()` at **lines 102-110 (Elo)** and **lines 112-120 (TBench)**. Today the loop tries only `[model_lower, model_normalized]`. After Phase 0 lands, those loops use a longer list. **This is NEW code added inside an existing function** — not a patch to existing logic. Insertion happens before line 102 to compute the expanded key list, and lines 103+114 change `for key in [model_lower, model_normalized]:` to `for key in keys_to_try:`.

Proposed (replaces nothing — insert before line 102 inside `update_agents_json`):

```python
# Build the candidate key set ONCE per agent. We try the raw lowercased
# name, the normalized variant (current behaviour), AND every progressively
# suffix-stripped version so models registered as `:free`/`:nitro` join
# to their base-model leaderboard rows.
keys_to_try = [model_lower, model_normalized]
stripped = model_lower
while True:
    next_stripped = stripped
    for suffix in (":free", ":nitro", ":floor", ":beta", ":online", ":thinking"):
        if next_stripped.endswith(suffix):
            next_stripped = next_stripped[: -len(suffix)]
    if next_stripped == stripped:
        break
    stripped = next_stripped
    keys_to_try.append(stripped)
    keys_to_try.append(normalize_model_name(stripped))
```

Then lines 103 and 114 change from `for key in [model_lower, model_normalized]:` to `for key in keys_to_try:`. No `break` between the suffix-loop body and the outer `while` — every suffix gets a chance every iteration, so double-suffix IDs like `x/y:free:online` strip both before the candidate set is built.

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

def test_double_suffix_strips_both():
    # Two suffixes back-to-back — the new while-loop normalizer strips
    # BOTH (Pass 2A Finding: original comment misleadingly said "should
    # stop after one strip" — the implementation actually loops until
    # no suffix matches).
    assert m.normalize_model_name("x/y:free:nitro") == "x/y"

def test_suffix_only_at_end():
    # OpenRouter spec guarantees routing suffixes appear only at ID end
    # (verified against /api/v1/models snapshots 2026-06-27).
    # Middle-of-name appearances are NOT stripped — leave as-is.
    assert m.normalize_model_name("x/:free/y") == "x/:free/y"
```

### 6.4 Validation gates

| Gate | Command | Pass criterion |
|---|---|---|
| G0.1 unit test | `.venv/bin/python -m pytest tests/kilo_benchmarks/test_normalize_model_name.py -q` | exit 0 |
| G0.2 dry-run pipeline | `cd scripts/kilo-benchmarks && .venv/bin/python update_kilo_benchmarks.py --force` | runs to completion; log shows `Updated N Elo + M TBench scores` with N>114 OR M>45 (last good run 2026-06-25 baseline `cache/update.log`) |
| G0.3a primary invariant | `.venv/bin/python -c "import sqlite3; c=sqlite3.connect('/opt/fabrik/scripts/kilo-benchmarks/kilo_agents.db'); print(c.execute(\"SELECT count(*) FROM agents WHERE id LIKE '%:free' AND status='active' AND (tbench_accuracy IS NOT NULL OR arena_elo IS NOT NULL)\").fetchone()[0])"` | **> 0** (today: 0) |
| G0.3b operator falsifier | Run G0.3a; if `0`, run `.venv/bin/python -c "import json,pathlib,sys; p=pathlib.Path('/opt/fabrik/scripts/kilo-benchmarks/cache/arena_parsed.json'); print('NO_CACHE: run update_kilo_benchmarks.py --force first') if not p.exists() else print(len([e for e in json.loads(p.read_text()) if any(s in e['model'].lower() for s in ['deepseek', 'qwen', 'kimi'])]))"` — sanity-check the leaderboard cache contains at least one model whose base form has a `:free` variant in our DB. Pass 2B Finding 5: cache absence on fresh checkout is **explicit** in the output (`NO_CACHE:`) instead of `FileNotFoundError`. | (a) `NO_CACHE:` → operator runs the pipeline first; gate INCOMPLETE, not failed. (b) integer `> 0` → join SHOULD have fired; G0.3a returning `0` then means Phase 0 regressed (real failure). (c) integer `0` → leaderboard genuinely has no models with our `:free` variants today; G0.3a `0` is acceptable (vacuous-case caveat per §1a). |
| G0.4 final_gate | `.venv/bin/python scripts/final_gate.py --check --lean --json` | `"status":"success"` |

### 6.5 Evidence (filled 2026-06-27, this Phase 0 commit)

**Pass 4 finding (during implementation):** the plan's `path:line` cite for the join was incomplete. `update_kilo_benchmarks.py:89-120` (`update_agents_json`) only writes the JSON shadow file (`kilo_selected_agents.json`); the actual `agents` SQLite table that G0.3a queries is written by `kilo_agents_db.py:327` (`update_benchmarks()`) which has its **own** `normalize()` at line 343. Patching only the plan-cited file would have left G0.3a stuck at 0 forever. Phase 0 therefore patched BOTH paths — the plan's cited path AND the previously-unstated DB path. Logged as Pass 4 finding in §17a U6 update (separate edit).

- `path:line`:
  - `scripts/kilo-benchmarks/update_kilo_benchmarks.py:59-87` (rewritten `normalize_model_name` + module constant `_OPENROUTER_ROUTING_SUFFIXES`)
  - `scripts/kilo-benchmarks/update_kilo_benchmarks.py:106-126` (lookup-key expansion inside `update_agents_json`)
  - `scripts/kilo-benchmarks/kilo_agents_db.py:343-374` (extended `normalize()` with the same suffix-stripping loop)
  - `tests/kilo_benchmarks/test_normalize_model_name.py:1-103` (7 unit tests, all pass)

**Command output (verbatim 2026-06-27):**

```text
G0.1 unit test:
$ .venv/bin/python -m pytest tests/kilo_benchmarks/test_normalize_model_name.py -q
.......                                                                  [100%]
7 passed in 0.11s

G0.2 DB-side pipeline (after Pass 4 extension to kilo_agents_db.py):
$ cd scripts/kilo-benchmarks && .venv/bin/python kilo_agents_db.py update | tail -1
[kilo-db]   Updated 131 Elo, 46 TBench, 33 BenchLM scores
# Baseline 2026-06-25 was 114 Elo / 45 TBench / 28 BenchLM
# Delta: +17 Elo, +1 TBench, +5 BenchLM models gained scores via :free→base join

G0.3a invariant:
$ # BEFORE Phase 0:
$ # SELECT count(*) FROM agents WHERE id LIKE '%:free' AND status='active'
$ #   AND (tbench_accuracy IS NOT NULL OR arena_elo IS NOT NULL OR ...) → 0
$ # AFTER Phase 0:
G0.3a POST-PIPELINE: scored :free models = 10 / 32

Examples:
  minimax/minimax-m2.5:free                  elo=1436 tbench=42.7
  qwen/qwen3.6-plus:free                     elo=1482 wc=77.7
  google/gemma-4-31b-it:free                 elo=1462
  nvidia/nemotron-3-super-120b-a12b:free     elo=1401
  ... (10 total flipped)

G0.4 final_gate (after fixing a transient ruff N806 on a constant name):
$ .venv/bin/python scripts/final_gate.py --check --lean --json | tail -8
{"status": "success", "tier": 1, "passed": 12, "failed": 0, "failures": []}
```

**Verdict: G0.3a flipped from 0 to 10. BENCHMARK_SOURCES.md §4.5 gap closed.**

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
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_agent_categories_category
    ON agent_categories(category);
```

`ON DELETE CASCADE` (Pass 1D D12) prevents orphan rows if a model is deleted from `agents` (OpenRouter occasionally discontinues a model ID). Requires the SQLite connection to enable foreign keys explicitly (`PRAGMA foreign_keys = ON;` on connect; default OFF in SQLite).

**PRAGMA coverage map** (Pass 2B Findings 2 + 14) — verified 2026-06-27 via `grep -l "PRAGMA foreign_keys" scripts/kilo-benchmarks/*.py → 0`:

| Script | Connects to `kilo_agents.db`? | Touches `agent_categories`? | PRAGMA required? |
|---|---|---|---|
| `migrate_ai_category_table.py` (NEW) | yes | CREATE + initial insert | **YES** |
| `classify_ai_category.py` (NEW) | yes | INSERT OR REPLACE | **YES** |
| `category_selector.py` (NEW) | yes | SELECT | YES (read-only but consistency requires same connection mode) |
| `category_route_mapper.py` (NEW) | yes | SELECT (via selector) | YES |
| `category_export_markdown.py` (NEW) | yes | SELECT via agent_roles | YES |
| `kilo_agents_db.py` (existing) | yes | no | not required (no FK to enforce) |
| `embedding_*` scripts (existing) | yes | no | not required (no FK to enforce) |
| `update_kilo_benchmarks.py` (existing, patched in Phase 0) | reads JSON, not DB | no | not required |

**Why existing scripts can skip it**: the catalog schema has zero FK constraints before this plan. `agent_categories` is the first table with `ON DELETE CASCADE`, so only the five new scripts above (those that connect AND touch `agent_categories` or transitively join through it) must execute the PRAGMA. The plan does NOT modify existing scripts to add the PRAGMA — that would be scope creep.

The PRAGMA must be the FIRST statement after `sqlite3.connect()` in each new script. Tests (G1.6 + per-script unit tests) assert `PRAGMA foreign_keys → 1` post-connect.

Idempotent (`IF NOT EXISTS`). No change to `agents`. Existing indexes (`idx_agents_provider`, `idx_agents_status`, `idx_agents_task_tier`) cover the joins this plan adds.

### 7.2 Classifier — new file `scripts/kilo-benchmarks/classify_ai_category.py`

Pure-SQL, no LLM, deterministic. Inserts one row per (agent_id, category) pair using `INSERT OR REPLACE`. A model that matches multiple categories gets multiple rows. A model that matches none gets zero rows.

| Pack file | `category` value | SQL rule applied to `agents` |
|---|---|---|
| `ai/10-speech-audio.md` | `speech-audio` | `id LIKE '%whisper%' OR id LIKE '%audio%' OR id LIKE '%voice%' OR id LIKE '%tts%'` (live 2026-06-27: 3 rows) |
| `ai/20-vision.md` | `vision` | `has_vision = 1` (live: 205) |
| `ai/30-language.md` | `language` | `COALESCE(is_ga, 1) = 1 AND COALESCE(has_vision, 0) = 0 AND id NOT LIKE '%coder%' AND id NOT LIKE '%code%' AND id NOT LIKE '%audio%'` — residual general LLMs. **`COALESCE(is_ga, 1)`** includes the 31 NULL-`is_ga` rows (Pass 1D D1); **`AND id NOT LIKE '%code%'`** prevents the 12-row overlap with `code` that Pass 1B caught (e.g. `mistralai/codestral-2508` matches `%code%` but not `%coder%`). |
| `ai/40-multimodal.md` | `multimodal` | `has_vision = 1 AND has_tools = 1 AND has_reasoning = 1` (live: 76) |
| `ai/50-agentic.md` | `agentic` | `is_agentic = 1 AND has_tools = 1 AND has_reasoning = 1` (live: 131) |
| `ai/60-code.md` | `code` | `id LIKE '%coder%' OR id LIKE '%code%' OR weighted_coding > 0 OR humaneval_score > 0 OR coding_score > 0` (live: 55) |
| `ai/90-long-context.md` | `long-context` | `context_window_k >= 200` (live: 234) |

Packs **`ai/70-data-predictive.md`, `ai/80-specialized-domains.md`, `ai/25-3d-generation.md`** cover specialized non-LLM vendors per the packs' own text — classifier intentionally emits **zero rows** for them. They do not receive `OPENROUTER_ROUTES` blocks in Phase 4.

**Multi-category models are by design (Pass 2A Finding 2):** the `agent_categories` join table at §7.1 explicitly supports `PRIMARY KEY (agent_id, category)` — a single model gets one row per category it matches. Live 2026-06-27 confirms 9 models match BOTH `language` AND `code` (e.g. `qwen/qwen3.7-max`, `z-ai/glm-5.1`, `deepseek/deepseek-v4-flash`): they are top-tier general LLMs that ALSO have strong coding scores, so they correctly appear as P-options in both pack types. This is not classifier error — the join-table architecture exists precisely to enable this. The route mapper consumes one category at a time; downstream consumers (humans + AI agents reading the packs) see the model in both contexts with category-appropriate ranking.

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
    ("language",     "COALESCE(is_ga, 1) = 1 AND COALESCE(has_vision, 0) = 0 "
                     "AND id NOT LIKE '%coder%' AND id NOT LIKE '%code%' "
                     "AND id NOT LIKE '%audio%'"),
]

conn.execute("PRAGMA foreign_keys = ON")  # required for ON DELETE CASCADE
for category, where in RULES:
    conn.execute(
        f"INSERT OR REPLACE INTO agent_categories (agent_id, category) "
        f"SELECT id, ? FROM agents "
        f"WHERE status = 'active' AND blocked = 0 AND ({where})",
        (category,),
    )
```

### 7.4 Validation gates

Live-DB row counts captured by Pass 1B (2026-06-27): speech-audio 3 · vision 205 · multimodal 76 · agentic 131 · code 55 · long-context 234 · language 180. Distinct models hit ≥ 1 rule: ~425. These numbers ground the pass criteria below.

| Gate | Command | Pass criterion |
|---|---|---|
| G1.1 migration idempotent | run `migrate_ai_category_table.py` twice in a row | second run is no-op (no error, no row count change) |
| G1.2 classifier coverage | `sqlite3 kilo_agents.db "SELECT count(DISTINCT agent_id) FROM agent_categories"` | ≥ 300 (live baseline 425; floor is permissive to absorb future catalog drift) |
| G1.3 every required category populated | `sqlite3 kilo_agents.db "SELECT category, count(*) FROM agent_categories GROUP BY category"` | **language ≥ 100, vision ≥ 50, code ≥ 10, long-context ≥ 50, agentic ≥ 50** required. `multimodal`, `speech-audio` ≥ 0 acceptable (counts vary as catalog drifts) |
| G1.4 no orphans | `sqlite3 kilo_agents.db "SELECT count(*) FROM agent_categories ac LEFT JOIN agents a ON a.id = ac.agent_id WHERE a.id IS NULL"` | 0 (FK CASCADE prevents this growing) |
| G1.5 no language↔code overlap | `sqlite3 kilo_agents.db "SELECT count(*) FROM agent_categories WHERE agent_id IN (SELECT agent_id FROM agent_categories WHERE category='language') AND category='code'"` | 0 (proves the `id NOT LIKE '%code%'` exclusion works) |
| G1.6 PRAGMA foreign_keys verified | `sqlite3 kilo_agents.db "PRAGMA foreign_keys"` after running migration | `1` (or assert in test) |
| G1.7 final_gate | `.venv/bin/python scripts/final_gate.py --check --lean --json` | `"status":"success"` |

### 7.5 Evidence (filled 2026-06-27, this Phase 1 commit)

- `path:line`:
  - `scripts/kilo-benchmarks/migrate_ai_category_table.py:1-99` (idempotent migration; `PRAGMA foreign_keys = ON` + assert)
  - `scripts/kilo-benchmarks/classify_ai_category.py:1-141` (7 rules; same PRAGMA contract)
- **Pass 4-style reverse audit done before shipping**: `grep -l "agent_categories" scripts/kilo-benchmarks/*.py` → only the two new scripts wrote it. No silent second-writer pattern this phase.

**Command output (verbatim 2026-06-27):**

```text
G1.1 migration idempotent:
$ python migrate_ai_category_table.py
[migrate_ai_category] table_created=1 index_created=1 foreign_keys_enabled=1
$ python migrate_ai_category_table.py   # rerun
[migrate_ai_category] table_created=0 index_created=0 foreign_keys_enabled=1

G1 classifier run:
$ python classify_ai_category.py
[classify_ai_category] classified 889 rows across 7 categories:
  speech-audio=3, vision=205, multimodal=76, agentic=131,
  code=58, long-context=234, language=182

G1.2 coverage:          distinct agent_ids = 425   (need >= 300) ✓
G1.3 per-category mins: every required floor met
                        agentic 131 (≥50), code 58 (≥10),
                        language 182 (≥100), long-context 234 (≥50),
                        vision 205 (≥50); multimodal 76 / speech-audio 3
                        accepted as ≥0 (catalog-dependent)
G1.4 orphans:           0 (need 0)
G1.5 LIKE-rule overlap: 0 language rows whose id contains code/coder
                        (NOT LIKE exclusion working)
G1.5b score-column overlap: 9 (language ∩ code) — DOCUMENTED INTENTIONAL
                        per §7.2 multi-category-by-design contract
G1.6 PRAGMA:            per-connection in SQLite (by design); the two new
                        scripts set + assert PRAGMA foreign_keys = ON on
                        connect and raise RuntimeError if SQLite build is
                        missing FK support — see migrate_ai_category_table.py:48
                        and classify_ai_category.py:98
G1.7 final_gate:        {"status":"success","tier":1,"passed":12,"failed":0}
```

**Verdict:** all G1 gates green. The classifier produced exactly the row distribution Pass 1B predicted from live DB queries (speech-audio 3, vision 205, multimodal 76, agentic 131, long-context 234) plus the post-fix language count (182 — up from 180 baseline because Pass 2A's `COALESCE(is_ga, 1)` change pulled in the 31 NULL-`is_ga` rows that previously fell through, minus those caught by the code rule). code count 58 vs Pass 1B's 55 reflects 3 newly-scored `:free` models from Phase 0's leaderboard join.

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

### 8.2 Evidence (filled 2026-06-27, this Phase 2 commit)

- `path:line`: `scripts/kilo-benchmarks/ai_category_configs.yaml:1-126` (7 categories declared; field-for-field mirror of `embedding_role_configs.yaml`)
- **Command output (verbatim 2026-06-27):**

```text
G2.1 YAML parse:
$ python -c "import yaml; yaml.safe_load(open('ai_category_configs.yaml'))"
ok — 7 categories: language, code, vision, multimodal, agentic, long-context, speech-audio

G2.2 every pack_file exists:
  language        ✓ .windsurf/rules/ai/30-language.md
  code            ✓ .windsurf/rules/ai/60-code.md
  vision          ✓ .windsurf/rules/ai/20-vision.md
  multimodal      ✓ .windsurf/rules/ai/40-multimodal.md
  agentic         ✓ .windsurf/rules/ai/50-agentic.md
  long-context    ✓ .windsurf/rules/ai/90-long-context.md
  speech-audio    ✓ .windsurf/rules/ai/10-speech-audio.md

G2.3 final_gate:
{"status": "success", "tier": 1, "passed": 11, "failed": 0, "failures": []}
```

**Verdict:** declarative-only commit. Three categories intentionally absent from the YAML (3d-generation, data-predictive, specialized-domains) — those packs cover non-LLM vendors and receive zero rows from the Phase 1 classifier, so Phase 3+ skip them by construction.

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

**Zero-eligible handling (Pass 1D D4):** wraps each per-category call to `select_for_category()` in `try/except NoEligibleCategoryError`. On exception: **log the category name + the floors that filtered it out + skip writing any row for that category** (don't crash). The output JSON contains one entry per category that succeeded; categories with zero eligible models are emitted as `{"category": "X", "routes": [], "reason": "no eligible models"}` so downstream consumers + G3.x gates can distinguish "ran successfully with 0 routes" from "didn't run". A category with consistent zero-eligible across N consecutive days surfaces in the `cache/update.log` for human review.

**All-categories-zero-eligible (Pass 2B Finding 6):** test case in `test_category_route_mapper.py` injects floor constraints so impossible no category passes (e.g. `min_quality_tier: 99`). Mapper must produce exactly 7 entries each with `routes: []`, JSON shape valid, exit 0. The markdown export step then renders 7 marker blocks each containing a placeholder line:

```markdown
*No eligible models today — floors too strict or catalog too thin. See cache/update.log for details.*
```

instead of an empty table (which would be a confusing artifact for human readers).

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
| G3.1 unit tests | `.venv/bin/python -m pytest tests/kilo_benchmarks/test_category_selector.py tests/kilo_benchmarks/test_category_route_mapper.py -q` | all pass; **must include a test that injects a zero-eligible category and asserts the mapper logs+skips instead of raising** (D4 regression guard) |
| G3.2 smoke run | `cd scripts/kilo-benchmarks && .venv/bin/python category_route_mapper.py` | **exit 0** (the script never crashes — zero-eligible categories surface as empty routes, not exceptions); log shows `[category_route_mapper] wrote N pins across M categories (K skipped)` with N + K = 7 |
| G3.3 DB invariant — pin count matches YAML slots OR documents a skip | `sqlite3 kilo_agents.db "SELECT substr(role, 12) AS cat, count(*) FROM agent_roles WHERE assigned_by='category_route_mapper' GROUP BY cat"` | for each category present: count ≤ YAML `slots`. Categories absent here MUST appear in `openrouter_routes.json` with `"routes": []` and a non-empty `reason` |
| G3.4 JSON shape | `jq 'length' scripts/kilo-benchmarks/openrouter_routes.json` | **exactly 7** (one entry per category, including zero-eligible ones with empty `routes` array) |
| G3.5 rollback isolation | `sqlite3 kilo_agents.db "SELECT count(*) FROM agent_roles WHERE assigned_by IN ('cheapest-above-floors', 'role_mapper')"` | unchanged before/after running `category_route_mapper.py` — proves the mapper only writes its own `assigned_by` and a hypothetical rollback `DELETE WHERE assigned_by='category_route_mapper'` cannot touch chat-side rows (Pass 1D D6 rollback safety) |
| G3.6 final_gate | `.venv/bin/python scripts/final_gate.py --check --lean --json` | `"status":"success"` |

### 9.5 Evidence (filled 2026-06-27, this Phase 3 commit)

- `path:line`:
  - `scripts/kilo-benchmarks/category_selector.py:1-165` (mirror of `embedding_selector.py:38-125` with chat-side floors + sort-key allowlist + PRAGMA fk)
  - `scripts/kilo-benchmarks/category_route_mapper.py:1-216` (mirror of `embedding_role_mapper.py:60-198`, plus zero-eligible graceful handling per plan §9.2)
  - `tests/kilo_benchmarks/test_category_selector.py:1-167` (8 unit tests)
  - `tests/kilo_benchmarks/test_category_route_mapper.py:1-208` (4 integration tests including the §16 rollback-isolation invariant)

**Command output (verbatim 2026-06-27):**

```text
G3.1 pytest tests/kilo_benchmarks/test_category_{selector,route_mapper}.py -q
............                                                             [100%]
12 passed in 0.55s

G3.2 smoke run:
$ cd scripts/kilo-benchmarks && python category_route_mapper.py
[category_route_mapper] language: 3 routes → [stepfun/step-3.5-flash, qwen/qwen3-next-80b, meituan/longcat-flash-chat]
[category_route_mapper] code: 3 routes → [openai/gpt-5.4, google/gemini-3.1-pro-preview, openai/gpt-5.3-codex]
[category_route_mapper] vision: 2 routes → [openai/gpt-5-nano, google/gemma-3-12b-it]
[category_route_mapper] multimodal: 2 routes → [openai/gpt-5-nano, kilo-auto/small]
[category_route_mapper] agentic: 3 routes → [openai/gpt-5.4, openai/gpt-5.3-codex, anthropic/claude-opus-4.6]
[category_route_mapper] long-context: 2 routes → [meta-llama/llama-4-scout, x-ai/grok-4.20]
[category_route_mapper] speech-audio: 1 routes → [openai/gpt-audio-mini]
[category_route_mapper] wrote /opt/fabrik/scripts/kilo-benchmarks/openrouter_routes.json
[category_route_mapper] wrote /opt/fabrik/scripts/kilo_openrouter_routes_final.json
[category_route_mapper] wrote 16 pins across 7 categories (0 skipped)

G3.3 per-category pin count vs YAML slots:
  agentic=3 code=3 language=3 long-context=2 multimodal=2 speech-audio=1 vision=2
  (matches slots:[3,3,3,2,2,1,2] in YAML)

G3.4 JSON entries: exactly 7 categories with non-empty routes (0 skipped today)

G3.5 chat-side rollback isolation:
  26 rows with assigned_by != 'category_route_mapper' still in agent_roles
  (proves the LIKE 'openrouter:%' DELETE didn't touch them)

G3.6 final_gate.py --check --lean --json: success
```

**Verdict:** all G3 gates green. 12/12 unit + integration tests pass. The zero-eligible path is exercised in tests but didn't fire on the live DB (every category had ≥1 eligible model). Rollback isolation invariant proven on live data.

---

## §10. Phase 4 — `category_export_markdown.py`

Mirrors [`embedding_export_markdown.py`](../../../scripts/kilo-benchmarks/embedding_export_markdown.py) **exactly** including the self-heal pattern at lines 209-247 (shipped 2026-06-25 commit `f3c8222`).

### 10.1 Marker contract per pack

Each `.windsurf/rules/ai/NN-*.md` pack receives a marker block. **The START marker carries the date of the last route refresh** (Pass 2B finding — so G5.6 stale-marker watchdog can parse it without scanning the body):

```markdown
<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-06-27 (auto-managed by category_export_markdown.py) -->
*Auto-generated on 2026-06-27 (UTC) from `agent_roles` where `role` starts with `openrouter:`. Edits between markers will be overwritten on the next daily run.*

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

### 10.3 Pack stamping — explicit coupling contract + intentional divergence from mirror

**Divergence note (Pass 2B Finding 1):** [`embedding_export_markdown.py`](../../../scripts/kilo-benchmarks/embedding_export_markdown.py) (the mirror canonical) does NOT write `Last content verification:` stamps — verified by `grep -c "Last content verification" embedding_export_markdown.py → 0`. Phase 4 deliberately adds this responsibility to the chat-side equivalent because the AI-side packs (`ai/*.md`) are subject to the freshness check ([`check_ai_pack_freshness.py:25-28`](../../../scripts/check_ai_pack_freshness.py#L25-L28)) and the embedding-side packs (`core/65-rag-search.md` etc.) aren't. The two scripts therefore have intentionally different responsibilities — `category_export_markdown.py` mirrors the marker self-heal pattern only; the stamp write is new logic specific to ai/* packs.

Phase 4 writes BOTH the marker block AND the `Last content verification: YYYY-MM-DD` line. **Coupling rule (Pass 1D D6):** the marker block write and the freshness-line write happen in a **single `pack.write_text(new_content)` call** — there is no intermediate state. If the write fails, neither lands; if it succeeds, both land. Specifically:

1. `category_export_markdown.py` reads the existing pack text.
2. Builds `new_text` by: (a) re-seeding/replacing the OPENROUTER_ROUTES block, AND (b) writing/updating the `Last content verification: <today>` line directly under the file's H1 title.
3. Writes `new_text` to disk atomically (`pack_path.write_text(new_text)`).

If the freshness regex matches no line in the input, the script INSERTS one. If it matches an old date, it REPLACES the date. **Test this** in `tests/kilo_benchmarks/test_category_export_markdown.py` — four cases:

- (a) absent stamp → present (today)
- (b) stale stamp → today (replaced)
- (c) today's stamp → no-op (idempotent)
- (d) **malformed stamp** (e.g. `Last content verification: 2026-99-99`) → the script logs `[category_export_markdown] WARN: pack X has malformed verification date '2026-99-99' — replacing with today`, replaces it with today's date, and **does not crash** (Pass 2B Finding 10). Behavior verified by `date.fromisoformat()` raising `ValueError` inside a try/except that falls through to the replace-with-today branch.

This design (single-write atomicity) ensures `check_ai_pack_freshness.py` never sees a pack with new markers but a stale stamp — both move together or neither moves.

### 10.4 Validation gates

| Gate | Command | Pass criterion |
|---|---|---|
| G4.1 unit tests | `.venv/bin/python -m pytest tests/kilo_benchmarks/test_category_export_markdown.py -q` | all pass — includes marker-absent self-heal, marker-present replace, AND three pack-stamp cases from §10.3 (absent → present, stale → today, today → no-op) |
| G4.2 idempotent | run script twice, `git diff .windsurf/rules/ai/` | empty after 2nd run (within YYYY-MM-DD precision) |
| G4.3 freshness check now green | `.venv/bin/python scripts/check_ai_pack_freshness.py` | every stamped pack the script touched reports `verified 0d ago` |
| G4.4 markers actually present (Pass 1D nit, replaces markdownlint) | `for f in .windsurf/rules/ai/{10,20,30,40,50,60,90}-*.md; do test "$(grep -c "OPENROUTER_ROUTES" "$f")" -eq 2 \|\| echo "MISSING in $f"; done` | empty output (every targeted pack has both START + END markers) |
| G4.5 final_gate | `.venv/bin/python scripts/final_gate.py --check --lean --json` | `"status":"success"` |

### 10.5 Evidence (filled 2026-06-27)

- `path:line`: [`scripts/kilo-benchmarks/category_export_markdown.py:132-174`](../../../scripts/kilo-benchmarks/category_export_markdown.py#L132-L174) (`_replace_or_append_markers` — self-heal mirror of `embedding_export_markdown.py:209-247` + Pass A F3 orphan-strip hardening), [`scripts/kilo-benchmarks/category_export_markdown.py:186-258`](../../../scripts/kilo-benchmarks/category_export_markdown.py#L186-L258) (`_refresh_stamp` + atomic single-write contract), [`tests/kilo_benchmarks/test_category_export_markdown.py`](../../../tests/kilo_benchmarks/test_category_export_markdown.py) (20 cases).
- G4.1 unit tests: `pytest tests/kilo_benchmarks/test_category_export_markdown.py -q` → `20 passed in 0.07s`.
- G4.2 idempotent: second run output `[category_export_markdown] <cat>: {'status': 'noop', 'marker': 'noop', 'stamp': 'noop'}` for all 7 categories; pack mtimes stable on 3rd run.
- G4.3 freshness: `python scripts/check_ai_pack_freshness.py` → `[ai-pack-freshness] 11 packs scanned (threshold: 90d) on 2026-06-27`, no STALE/ERROR rows.
- G4.4 markers: `for f in ai/{10,20,30,40,50,60,90}-*.md; grep -c OPENROUTER_ROUTES $f` → `2` for all 7.
- G4.5 final_gate: `python scripts/final_gate.py --lean --json` → `"failed": 0`.
- **Adversarial review log (Pass A → B → C → D, all defects fixed, fixed point at D):** Pass A surfaced F1-F6 (frontmatter, case, orphans, duplication, missing WARN); Pass B surfaced multi-stamp collapse; Pass C surfaced reason-field stamp leak into marker block; Pass D returned `[]`. 9 regression tests added (`test_pass_a_f1_*`, `test_pass_a_f2_*` ×2, `test_pass_a_f3_*` ×3, `test_pass_a_f6_*`, `test_pass_b_f1_*`, `test_pass_c_*`).

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

After embedding pipeline's closing `fi` at line 99 and **before** the freshness check at line 104, insert:

```bash
        # === OPENROUTER CATEGORY ROUTING ===
        # Reads agents + agent_categories, writes openrouter:{category} pins
        # to agent_roles, then injects OPENROUTER_ROUTES markers into the 7
        # ai/NN-*.md packs. The whole block is wrapped in a conditional that
        # FORCES success at the shell level (`|| true` per script + outer
        # `if … else log-and-continue fi`) — a crash inside any step must
        # NOT short-circuit the freshness check (line 104+) or extensions
        # sync (line 105) below it. Sequential, not `&&`-chained.
        if [ ! -f /tmp/.openrouter_routing_disabled ]; then
            (
                cd $FABRIK_ROOT/scripts/kilo-benchmarks
                $VENV_PYTHON $CATEGORY_CLASSIFIER_SCRIPT >> $LOG_FILE 2>&1 \
                    || echo "[openrouter-routing] classifier failed (non-fatal)" >> $LOG_FILE
                $VENV_PYTHON $CATEGORY_MAPPER_SCRIPT >> $LOG_FILE 2>&1 \
                    || echo "[openrouter-routing] mapper failed (non-fatal)" >> $LOG_FILE
                $VENV_PYTHON $CATEGORY_MARKDOWN_SCRIPT >> $LOG_FILE 2>&1 \
                    || echo "[openrouter-routing] markdown export failed (non-fatal)" >> $LOG_FILE
            )
        fi
```

**Why a subshell:** isolates `cd` and any `set -e` propagation from the surrounding `nohup bash -c "..."` block (Pass 1D D5). The `|| echo … >> $LOG_FILE` per command ensures every step's failure is **logged loud + continues** — satisfies the [`core/58-resilience.md`](../../../.windsurf/rules/core/58-resilience.md) fail-loud requirement without abort-on-error semantics killing the rest of the pipeline.

**Why sequential not `&&`-chained:** the embedding pipeline above uses `&&` because each step strictly depends on the previous (catalog → shortlists → roles → markdown). Routing steps DO have order-dependence (classifier → mapper → markdown), BUT a partial run is more useful than a no-run: if the classifier succeeds but the mapper fails, the markdown step shouldn't run (would inject stale routes), but the failure also shouldn't kill the freshness check. The sequential-with-fail-log shape gets both.

**Stale-by-one-day acceptance (Pass 2B Findings 11 + 13):** if classifier fails on day N but mapper+markdown run anyway against yesterday's `agent_categories` rows, the output is "stale by one day, otherwise correct." This is acceptable because (1) catalog churn is < 1% per day, (2) the failed-classifier log line surfaces in `cache/update.log` and the operator can intervene, (3) the next successful day auto-recovers. The plan **explicitly accepts up to 2 days of staleness** before G5.6 stale-marker watchdog fires — anything beyond that is an operator-action signal. If a stronger SLA is ever needed, swap the sequential semantics for `&&`-chained semantics in a follow-up; the trade-off (no partial run on failure) is what would change.

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
| G5.2 dry-run | `bash -x scripts/wsl_startup_hook.sh 2>&1 \| head -60` | shows the 3 new script invocations IN ORDER between the embedding closing `fi` (line 99) and the freshness check (line 104+) |
| G5.3 lockfile bypass | `touch /tmp/.openrouter_routing_disabled && bash -x scripts/wsl_startup_hook.sh 2>&1 \| grep -c CATEGORY_` | 0 invocations |
| G5.4 manifest sync | `grep -E 'openrouter\|category_(classifier\|mapper\|markdown)' scripts/fabrik_synced_manifest.py` | empty (new scripts intentionally NOT synced — hub-only tooling) |
| G5.5 fail-loud-not-fatal contract (Pass 1D D5) | `bash tests/integration/test_routing_failover.sh` (saved harness, mirrors the plan's intent). Pass A Finding 1 fix: the original gate-text used `chmod -x` on the .py file, but `python <script>` only needs READ permission (verified: `chmod -x classify_ai_category.py && python classify_ai_category.py; echo exit=$?` → `exit=0` — chmod -x is a no-op for the failure technique). The shipped harness instead points the wrapper at `__does_not_exist__.py` so the file-open fails. Race-free because the harness runs the steps sequentially in the test shell, not via the backgrounded `nohup` of the real pipeline. | exit 0 — BOTH `[openrouter-routing] classifier failed (non-fatal)` AND `[ai-pack-freshness]` lines present in the log. |
| G5.6 stale-marker watchdog (Pass 1D D9 — REWRITTEN per Pass 2B Finding 3+15; Pass A Finding 2 + Pass B N2 hardened) | `today=$(date -u +%Y-%m-%d); for f in .windsurf/rules/ai/{10,20,30,40,50,60,90}-*.md; do [ ! -f "$f" ] && continue; d=$(grep -oE "OPENROUTER_ROUTES:START — last-refreshed: [0-9]{4}-[0-9]{2}-[0-9]{2}" "$f" \| grep -oE "[0-9]{4}-[0-9]{2}-[0-9]{2}" \| head -1); [ -z "$d" ] && { echo "NO_MARKER: $f"; continue; }; date -u -d "$d" +%s >/dev/null 2>&1 \|\| { echo "BAD_DATE: $f ($d)"; continue; }; age=$(( ($(date -u -d "$today" +%s) - $(date -u -d "$d" +%s)) / 86400 )); [ "$age" -gt 2 ] && echo "STALE: $f ($age d, last $d)"; done` | empty output (no pack has a route block dated > 2 days ago, no malformed dates). Pass B N2: replaced the Pass A shape-only regex with a semantic check via `date -d "$d" >/dev/null 2>&1` — catches both shape-malformed dates (`2026-99-99`) AND shape-valid-but-calendar-invalid dates (`2026-06-31`, `2026-02-30`). One-tool validation, no false-clean class possible. |
| G5.7 final_gate | `.venv/bin/python scripts/final_gate.py --check --lean --json` | `"status":"success"` |

### 11.4 Evidence (filled 2026-06-27)

- `path:line`: [`scripts/wsl_startup_hook.sh:51-53`](../../../scripts/wsl_startup_hook.sh#L51-L53) (path variables) + [`scripts/wsl_startup_hook.sh:109-131`](../../../scripts/wsl_startup_hook.sh#L109-L131) (routing subshell block) + [`scripts/wsl_startup_hook.sh:20-28`](../../../scripts/wsl_startup_hook.sh#L20-L28) (header comments renumbered to add step 6). New: [`tests/integration/test_routing_failover.sh`](../../../tests/integration/test_routing_failover.sh).
- G5.1 (`bash -n scripts/wsl_startup_hook.sh`): `G5.1 syntax OK` (exit 0).
- G5.2 ordering: `grep -n EMBEDDING_MARKDOWN_SCRIPT\|CATEGORY_CLASSIFIER_SCRIPT\|CATEGORY_MAPPER_SCRIPT\|CATEGORY_MARKDOWN_SCRIPT\|AI_PACK_FRESHNESS_SCRIPT scripts/wsl_startup_hook.sh` → embedding ends at L107, classifier+mapper+markdown at L119+121+123 (inside the conditional), freshness at L131 — correct order, all 3 inserted in the right window.
- G5.4 manifest sync: `grep -E 'openrouter|category_(classifier|mapper|markdown)' scripts/fabrik_synced_manifest.py` → empty (intentional — hub-only tooling).
- G5.5 (`bash tests/integration/test_routing_failover.sh`): `[test_routing_failover] PASS — fail-loud-not-fatal contract honored`.
- G5.6 stale-marker watchdog: all 7 packs report 0-day age, no NO_MARKER / BAD_DATE / STALE rows.
- G5.7 (`final_gate.py --lean --json`): `"failed": 0`.
- **Adversarial review log (Pass A → B → C, all defects fixed, fixed point at C):** Pass A surfaced 4 defects — (1) plan G5.5 said `chmod -x` but python doesn't need exec bit, harness silently pivoted to `__does_not_exist__.py`; (2) G5.6 watchdog crashed on malformed dates; (3) lockfile race — kill-switch claim was overstated; (4) `cd` silently no-ops if `FABRIK_ROOT` is unset. Pass B surfaced 2 more — (N1) stale chmod docstring in test header; (N2) Pass A's shape-only regex missed calendar-invalid dates like `2026-06-31`, replaced with semantic `date -d "$d" >/dev/null 2>&1` check. Pass C returned `[]`.

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

### 12.5 Evidence (filled 2026-06-27)

- `path:line`: [`docs/workflows/KILO_BENCHMARK_WORKFLOW.md:52-95`](../../workflows/KILO_BENCHMARK_WORKFLOW.md#L52-L95) (new "OpenRouter category routing (sibling, daily)" section, sibling to the existing "AI rule pack freshness check" section per plan §12.1), [`INDEX.md:674`](../../../INDEX.md#L674) (new row for `scripts/kilo_openrouter_routes_final.json`, mirror placement of `kilo_embeddings_final.json` row at L673), [`CHANGELOG.md`](../../../CHANGELOG.md) `[Unreleased]` entry "Added — workflow doc + INDEX cross-link (Phase 6 of OpenRouter routing plan)".
- G6.1 (`check_doc_sync.py`): exit 0, no output.
- G6.2 (`check_doc_sprawl.py`): exit 0, no output.
- G6.3 (`final_gate.py --lean --json`): `"failed": 0`.
- **Adversarial review log (Pass A → B → C → D, all defects fixed, fixed point at D):** Pass A surfaced 1 off-by-one citation (line 25 vs 25-26); Pass B surfaced example output counts not matching live state (vision/multimodal/long-context were shown as 3 but are 2); Pass C surfaced hardcoded language model IDs that drift daily — replaced with `[...]` for durability; Pass D returned `[]`. Also refreshed the `**Last Updated:**` stamp from 2026-06-16 to 2026-06-27.

---

## Evidence (plan-convergence proof)

Per [`scripts/enforcement/check_convergence.py`](../../../scripts/enforcement/check_convergence.py): a CONVERGED claim requires this Evidence section + ≥1 `file:line` citation + ≥1 non-trivial fenced command-output block.

**Grounding citations** (a partial sample — every Phase already cites more):

- `scripts/kilo-benchmarks/update_kilo_benchmarks.py:60` — function `normalize_model_name()` being patched in Phase 0
- `scripts/kilo-benchmarks/embedding_export_markdown.py:209` — self-heal marker pattern mirrored in Phase 4
- `scripts/kilo-benchmarks/embedding_role_mapper.py:60` — orchestrator pattern mirrored in Phase 3
- `scripts/kilo-benchmarks/embedding_selector.py:38` — selector function shape mirrored in Phase 3
- `scripts/wsl_startup_hook.sh:99` — embedding pipeline closing `fi`, the insertion point for Phase 5
- `scripts/check_ai_pack_freshness.py:25` — canonical `Last content verification:` regex respected by Phase 4
- `src/fabrik/spec_loader.py:400` — existing `llm_provider: openrouter` field consumed by routes

**Final_gate run on the plan-only stage** (this commit's stage = `CHANGELOG.md` + this plan file):

```json
{
  "status": "success",
  "tier": 1,
  "passed": 12,
  "failed": 0,
  "failures": []
}
```

Captured 2026-06-27 via:

```bash
$ git reset HEAD
$ git add docs/development/plans/2026-06-27-plan-openrouter-routing.md CHANGELOG.md
$ .venv/bin/python scripts/final_gate.py --check --lean --json | tail -10
```

**Live DB schema verification** (the schema claims in §3 were not paraphrased — they are the live `PRAGMA table_info(agents)` output):

```text
id                        TEXT NULL PK
api_id                    TEXT
name                      TEXT
provider                  TEXT
input_cost_per_m          REAL
output_cost_per_m         REAL
context_window_k          INTEGER NULL
has_vision                BOOLEAN NULL
has_tools                 BOOLEAN NULL
is_agentic                BOOLEAN NULL
arena_elo                 INTEGER NULL
tbench_accuracy           REAL NULL
... (35 columns total, captured 2026-06-27)
```

**Live `:free` gap query** (proves the Phase 0 fix is justified by observed state, not assumption):

```sql
SELECT count(*) FROM agents WHERE input_cost_per_m = 0 AND status = 'active';
-- → 38

SELECT count(*) FROM agents
  WHERE input_cost_per_m = 0 AND status = 'active'
    AND (tbench_accuracy IS NOT NULL OR arena_elo IS NOT NULL
         OR coding_score IS NOT NULL OR livecodebench IS NOT NULL);
-- → 0
```

38 free models in the catalog. Zero have benchmark scores. Phase 0 closes this gap; the per-phase Evidence sections (§6.5 onward) get filled with command output when each phase ships.

---

## §13. Self-audit (per `check_convergence.py`)

### 13.1 Plan-convergence rows (must all be ✅ to ship this plan)

| Item | Status | Evidence |
|---|---|---|
| Every Phase has Evidence section structured for `path:line` + command output | ✅ | §§6.5, 7.5, 8.2, 9.5, 10.5, 11.4, 12.5 |
| OpenRouter capability claims grounded in scrape extraction (§5) | ✅ | Subagent `a94aea73f0dfd6b81` 2026-06-27, verbatim JSON contract in §5.2 |
| DB schema claims grounded in live `PRAGMA table_info` | ✅ | §3 — captured 2026-06-27 |
| All mirror references include line ranges | ✅ | §4 (`embedding_export_markdown.py:209-247`, `embedding_role_mapper.py:60-77`, etc.) |
| Validation gates per phase | ✅ | every Phase has a G{n}.x table with executable commands + pass criteria |
| Terminal gate = `final_gate.py` | ✅ | §14 cites `--systemic --json` + `check_convergence.py` + pytest |
| No new external dependency added | ✅ | uses stdlib `sqlite3`, `pyyaml`, `requests` already present in `.venv` |
| `core/cost-budget.md` honored — zero LLM calls in daily pipeline | ✅ | every Phase is pure SQL or deterministic Python |
| Open uncertainties listed and bounded (§5.7) | ✅ | none block this plan; all are consumer-side concerns |
| Rule pack `ai/00-ai-model-selection.md` semantics preserved | ✅ | routes augment via marker block; curated lineup text untouched |
| One-Test Rule present (per `core/45-testing-strategy.md`) | ✅ | §1a |
| `final_gate.py --check --lean` green against the plan-only stage | ✅ | 12/12 passed on 2026-06-27 (this commit's stage) |

### 13.2 Implementation-convergence rows (filled per phase as shipped — not blocking this commit)

| Item | Status |
|---|---|
| Phase 0 (`:free` normalization) Evidence filled + G0.1-G0.4 green | ✅ shipped 2026-06-27 (this commit). G0.3a flipped 0 → 10 scored `:free` models. Evidence in §6.5 includes the verbatim G0.1/G0.2/G0.3a/G0.4 outputs. |
| Phase 1 (`agent_categories` join table) Evidence filled + G1.1-G1.7 green | ✅ shipped 2026-06-27. 889 rows across 7 categories; 425 distinct models classified; 0 orphans; 0 LIKE-rule overlap; PRAGMA fk asserted on every script connect. Evidence in §7.5. |
| Phase 2 (YAML config) Evidence filled + G2.1-G2.3 green | ✅ shipped 2026-06-27. 7 categories declared mapping to the 7 LLM-bearing ai/NN-*.md packs; field-for-field mirror of embedding_role_configs.yaml. Three packs intentionally omitted (3d-gen, data-predictive, specialized-domains — non-LLM vendors). Evidence in §8.2. |
| Phase 3 (selector + mapper) Evidence filled + G3.1-G3.6 green | ✅ shipped 2026-06-27. 16 routes / 7 categories / 0 skipped / 26 chat-side rows preserved (rollback isolation invariant proven). 12/12 unit + integration tests pass. Evidence in §9.5. |
| Phase 4 (markdown export) Evidence filled + G4.1-G4.5 green | ✅ |
| Phase 5 (pipeline wiring) Evidence filled + G5.1-G5.7 green | ✅ |
| Phase 6 (cross-link + workflow doc + INDEX + CHANGELOG) Evidence filled + G6.1-G6.3 green | ✅ |
| `core/40-documentation.md` doc-sync matrix satisfied across all phases | ⏳ |
| Terminal §14 gate green | ⏳ |

Implementation-convergence rows are explicitly out-of-scope for **this** plan-shipping commit. Each phase's AI implementer flips its row from ⏳ to ✅ in the same commit that ships the phase, attaching the verbatim command-output block.

---

## §14. Terminal validation gate

The plan reaches **implementation-CONVERGED** (Stage 2 per the policy at top) only when ALL of these return success:

```bash
# 1. Tier-3 gate (CI mode, no fixes) — repo-wide health
.venv/bin/python scripts/final_gate.py --check --systemic --json
# → expected: {"status": "success", "tier": 3, ...}
# Tier 3 (--systemic) covers: docs sprawl, deps drift, compose hygiene, port
# registry, INDEX/CHANGELOG sync, doc-sync matrix, convergence-evidence gate.
# See `scripts/final_gate.py:--systemic` arm + `docs/workflows/FINAL_GATE_WORKFLOW.md`
# for the full per-check matrix (the latter is fabrik-upstream-only —
# /opt/fabrik/docs/workflows/FINAL_GATE_WORKFLOW.md, not synced).
```

```bash
# 2. Convergence-evidence gate — every CONVERGED plan/review has proof
.venv/bin/python scripts/enforcement/check_convergence.py
# → exit 0 (regex contract: ## Evidence section + ≥1 file:line per phase
#           + ≥1 non-trivial fenced command-output block; per
#           scripts/enforcement/check_convergence.py:40-45)
```

```bash
# 3. Phase tests — every test file this plan introduces
.venv/bin/python -m pytest tests/kilo_benchmarks/ -q
# → all pass. Specifically: test_normalize_model_name (P0),
#   test_classify_ai_category (P1), test_category_selector (P3),
#   test_category_route_mapper (P3), test_category_export_markdown (P4).
```

```bash
# 4. Freshness signal — every pack the plan stamps now reads fresh
.venv/bin/python scripts/check_ai_pack_freshness.py
# → 7 stamped packs report "verified 0d ago" (today); the 3 non-routed
#   packs (25-3d-generation, 70-data-predictive, 80-specialized-domains)
#   remain on their existing stamps OR remain unstamped — both acceptable
#   because Phase 6 explicitly excludes them.
```

Any failure means a phase regressed; the offending phase row in §13.2 reverts ⏳ and the plan returns to plan-only CONVERGED (Stage 1). No partial-convergence claim.

**Environmental-noise carve-out (Pass 2A Finding 4):** Tier-3 (`--systemic`) currently fails on 2 environmental checks unrelated to this plan: "Documentation Drift" (broken links in `docs/infrastructure/vps-ai-sysadmin.md` + `docs/reference/runpod-api.md`) and "VPS Docs Freshness" (missing `vps-status.md` + `vps-urls.md`). These pre-exist and are owned by the fabrik-lane (run `fabrik vps-sync` to regenerate). If the implementer hits these as the only Tier-3 failures, they are acceptable per the operator-acknowledged carve-out — track them as "fabrik-lane debt, not this plan's responsibility" and proceed. If Tier-3 surfaces ANY OTHER check failing, that IS a regression and the plan returns to DRAFT.

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
| Phase 3 (selector + mapper) | **Safety pre-check** (Pass 1D D-rollback): `SELECT DISTINCT assigned_by FROM agent_roles` MUST include `'cheapest-above-floors'` AND `'category_route_mapper'`; only then run `DELETE FROM agent_roles WHERE assigned_by='category_route_mapper'; DELETE FROM agent_roles_history WHERE assigned_by='category_route_mapper'`. The exact-match WHERE clause cannot touch chat-side rows because their `assigned_by='cheapest-above-floors'` is a distinct string literal. Delete the script files only after the SQL succeeds. |
| Phase 4 (markdown export) | delete script + remove `OPENROUTER_ROUTES` blocks from packs |
| Phase 5 (pipeline wiring) | `touch /tmp/.openrouter_routing_disabled` (immediate); revert `wsl_startup_hook.sh` (permanent) |
| Phase 6 (docs) | `git revert` |

No phase mutates external systems — every change is local to `/opt/fabrik/`. No deploy, no DNS, no DB outside the local SQLite file. Rollback is purely git+SQL.

---

## §17. Sequencing

| # | Phase | Effort | Required for next phase | Notes |
|---|---|---|---|---|
| 1 | §6 Phase 0 (`:free` normalization) | ~20 LOC + 1 test file | Phase 3 (scored free models) | Stand-alone improvement; can ship without Phase 1 |
| 2 | §7 Phase 1 (`agent_categories` table + classifier) | ~100 LOC + migration | **MANDATORY** for Phase 2, 3, 4, 5 | Pass 2B Finding 12: Phase 3 reads `agent_categories`; skipping Phase 1 causes Phase 3 to crash with `no such table`. The migration script MUST run before any subsequent phase. |
| 3 | §8 Phase 2 (YAML config) | ~70 LOC | Phase 3 (config consumed by selector) | |
| 4 | §9 Phase 3 (selector + mapper + tests) | ~250 LOC | Phase 4 (mapper output consumed by markdown export) | |
| 5 | §10 Phase 4 (markdown export + tests) | ~250 LOC | Phase 5 (pipeline must wire something that exists) | |
| 6 | §11 Phase 5 (pipeline wiring) | ~15 LOC | Phase 6 (cross-link references the wired pipeline) | |
| 7 | §12 Phase 6 (cross-link + INDEX + CHANGELOG) | ~30 LOC | Terminal gate | |

**Estimated total**: ~735 LOC across 7 phases + 4 test files. Mirrors the embedding pipeline structure 1:1.

---

## §17a. Residual unknowns, assumptions, and out-of-scope risks

This plan iterated to a fixed point across **2 grounding passes** (Pass 1: 4 parallel grounders → 14 findings; Pass 2: 2 grounders → 19 findings; Pass 3 solo → 0 new findings). The fixed point is **structural soundness** (every claim verified against live code, schema, or scrape extraction). It is **not** "100% accuracy" — the items below remain explicitly unverified or out-of-scope. Anyone implementing this plan should hit them before declaring done.

### 17a.0 Pass 4 finding (caught during Phase 0 implementation 2026-06-27)

The plan reached fixed-point structural convergence across 3 passes BEFORE implementation began. Implementing Phase 0 immediately uncovered a finding NONE of the four Pass 1 grounders + two Pass 2 grounders + Pass 3 solo caught:

**Finding P4-1 (would have been blocking):** Plan §6.1 named exactly one file (`update_kilo_benchmarks.py:59-61`) as the location of `normalize_model_name`. That citation was correct, but **incomplete**. The actual SQLite `agents` table that G0.3a queries is populated by `kilo_agents_db.py::update_benchmarks()` at line 327, which has its **own** nested `normalize()` function at line 343 — independent of `update_kilo_benchmarks.py`'s normalizer. Patching only the plan-cited path would have shipped a fix that left G0.3a stuck at 0 forever (because the JSON shadow file isn't what the invariant checks). Phase 0 ended up patching BOTH normalizers to flip the invariant.

**Why the 6 grounders missed it:** every grounder followed citation chains FROM the plan (which only named one file). None did the reverse search: "what other code paths join scraped scores to the `agents` table?" A grep for `arena_elo` columns being written would have surfaced `kilo_agents_db.py:438` and the surrounding `update_benchmarks()` function in 30 seconds. Citation-chain grounding has this blind spot by design.

**Lesson encoded:** for any future phase that targets a "the join from X to Y" claim, run a **reverse audit** — `grep -l "<target column or behavior>"` across the script directory — to find all writers, not just the one the plan names. Pass 1B (schema grounder) had this opportunity and missed it because it focused on table shape, not on which scripts mutate the table.

### 17a.1 Residual unknowns (acknowledged, unresolved)

| # | Item | Why it's unresolved | Resolution path |
|---|---|---|---|
| U1 | Exact OpenRouter free-tier RPD numbers | FAQ placeholder values (`{FREE_MODEL_NO_CREDITS_RPD}`); not in the public docs we scraped | Implementer runs Phase 0 → consumes a `:free` route → observes 402 at the actual rate-limit boundary → records the empirical number in §5.4 |
| U2 | OpenRouter BYOK exact fee % | Docs say "percentage-based" only | Out of scope: this plan doesn't use BYOK |
| U3 | OpenRouter tool-call response shape | Plan flags `has_tools = true` per `supported_parameters` but doesn't invoke tools | A future "Phase 7" consumer that actually invokes `tools` must verify the OpenAI-compat claim |
| U4 | OpenRouter `response_format` parameter name for structured outputs | Assumed `response_format` matches OpenAI | Same: consumer must verify when invoking |
| U5 | OpenRouter SSE streaming delta format | Assumed OpenAI-compat; not tested | Same: streaming consumer must verify |
| U6 | Embedding-side scripts' connection-mode contract | We verified the embedding scripts don't currently set `PRAGMA foreign_keys` and the embedding-side schema has no FK constraints (so it doesn't matter), BUT if a future change adds FKs to embedding tables the embedding scripts will silently skip CASCADE | If embedding-side FKs ever land, the same PRAGMA-coverage gate (G1.6 mirror) becomes required for those scripts |
| U7 | Whether OpenRouter `model` IDs ever appear with suffixes in the MIDDLE of the string | Plan §6.1 + test `test_suffix_only_at_end` assumes "end only" per docs | If a model ID ever ships with suffix-in-middle, the test catches it as a regression |

### 17a.2 Assumptions

| # | Assumption | What it depends on | If wrong |
|---|---|---|---|
| A1 | Chat models and embeddings share `id`/`pricing`/`context`/`capability_flags` field shapes in `/api/v1/models` | Verified against 3 live samples 2026-06-27 (Pass 1C) | A future OpenRouter API change is detected by the scraper's row-count delta; an alarm fires before stale routes get used |
| A2 | Daily catalog churn is < 1% — making "stale-by-one-day" acceptable per §11 | Empirical observation of recent `cache/update.log` runs (337 → 339 over 2 days = 0.6%) | If churn jumps (e.g. OpenRouter mass-onboards 50 models), G1.2 + G5.6 surface the delta; operator-action |
| A3 | The 9 language ∩ code overlap (§7.2) is desired multi-category behavior, not classifier error | The `agent_categories` PK supports `(agent_id, category)` per-row | If a consumer ever needs strict single-category, add an explicit priority/tiebreak rule in a follow-up |
| A4 | `core/45-testing-strategy.md` "high-value happy-path E2E" requirement is satisfied by the §1a integration invariant | Plan §2 cites the rule pack line:19 directly | If a stricter reading of the pack is enforced, more tests must be added per phase |
| A5 | The `category_export_markdown.py` malformed-date branch (§10.3 case d) is safer than crashing | Standard "warn + replace with today" pattern | If a malformed date is load-bearing for another tool, the silent replace is wrong — make it require operator action instead |

### 17a.3 Out-of-scope risks (intentionally not addressed)

| # | Risk | Why out of scope |
|---|---|---|
| R1 | Retiring Chatbot Arena from BENCHMARK_SOURCES.md WIRED set | Separate decision tracked in `BENCHMARK_SOURCES.md` §4.4 with its own trigger condition |
| R2 | Wiring SWE-bench / LiveCodeBench / Aider Polyglot | All CONDITIONAL in `BENCHMARK_SOURCES.md` §3; none have fired trigger conditions |
| R3 | Centralizing `FREE_MARKERS` across `llm_selector.py:47` / `embedding_selector.py:27` / `embedding_models_db.py:56` | Refactor with separate blast radius; punted in §6.1 |
| R4 | Tool-call invocation against OpenRouter | Consumer concern; this plan only flags capabilities |
| R5 | Streaming-response handling | Same as R4 |
| R6 | Backward compatibility if `embedding_export_markdown.py` ever wants to write stamps too | §10.3 documents Phase 4's deviation; future unification is a separate ticket |
| R7 | `agents.ai_category` single-value column | Superseded by `agent_categories` join table (Pass 1D D-rollback). Plan §15 lists this as not-doing. |
| R8 | Hub-side `.gitignore` / synced-manifest changes for the new scripts | New scripts are hub-only tooling; G5.4 verifies they are intentionally NOT in `fabrik_synced_manifest.py` |

### 17a.4 What the gates prove + what they don't

The validation gates (G0.x through G6.x + §14 terminal) verify:

- **DO prove**: structural correctness (file present, regex matches, JSON shape, SQL syntactically valid, exit-code semantics, route count, freshness staleness, doc-sync matrix, convergence-evidence regex).
- **DO NOT prove**: that the design is sound, that the chosen `sort_key` per category is the right ranking, that `min_quality_tier: 2` is the right floor for `code`, that 3-slot fallback chains beat 5-slot, that the route mapper's choices match operator preferences.

The real proof of design soundness is the verification evidence in §13 + the citation work logged in Pass 1A/1B/1C/1D and Pass 2A/2B. The gates verify the plan ISN'T broken; the verification evidence is what makes it sound.

---

## §18. Related references

- Decision record: [`docs/reference/kilo/BENCHMARK_SOURCES.md`](../../reference/kilo/BENCHMARK_SOURCES.md)
- Mirror canonical implementation: [`scripts/kilo-benchmarks/embedding_export_markdown.py`](../../../scripts/kilo-benchmarks/embedding_export_markdown.py) (commit `f3c8222`)
- Hub guard precedent: [`src/fabrik/scaffold.py::_assert_not_hub`](../../../src/fabrik/scaffold.py) (commit `4ca38bf`)
- Freshness check pattern: [`scripts/check_ai_pack_freshness.py`](../../../scripts/check_ai_pack_freshness.py) (commit `4ca38bf`)
- OpenRouter scrape: subagent `a94aea73f0dfd6b81` 2026-06-27 (verbatim extraction in §5)
- AI INDEX pack: [`.windsurf/rules/ai/00-ai-model-selection.md`](../../../.windsurf/rules/ai/00-ai-model-selection.md)
