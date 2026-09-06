# Kilo Agent Management

**Script:** `scripts/kilo-benchmarks/` (multiple scripts)

> Automated agent discovery, benchmarking, role assignment, and runtime selection.

This document covers tools for managing AI agents in `scripts/kilo-benchmarks/`.

## WSL Startup Workflow (Automatic Daily)

**Trigger:** `~/.bashrc` sources `scripts/wsl_startup_hook.sh` on WSL start

**Steps:**
1. `kilo_agents_db.py all` - Sync ALL ~330 Kilo CLI models + 4 custom local Ollama agents (FREE)
   - **Kilo CLI:** Vision support, tool calling, reasoning modes, context windows, input/output costs
   - **Local Ollama agents:** fabrik-coder, fabrik-fixer, fabrik-reviewer, fabrik-docs
   - Creates daily historical snapshot
2. `update_kilo_benchmarks.py --force` - Scrape Arena ELO, TBench, Windsurf models (FREE)
3. `scrape_artificial_analysis.py` - Scrape throughput + TTFT from artificialanalysis.ai (FREE)
   - Updates `output_tokens_per_sec` and `ttft_ms` columns
   - Manual proxies in `cache/speed_overrides.json` fill gaps for models AA doesn't track
4. `role_mapper.py` - Deterministic role assignment (FREE, ~50ms, byte-identical re-runs)
   - Pipeline: `pre_filter.py` → `selector.py` → `post_filter.py` → DB write
   - No LLM in the loop; rules live in `role_configs.yaml`
5. `generate_kilo_agents.py` - Generate CLI agent scripts in `~/.traycer/cli-agents/` (FREE)

**Cost:** $0/day | **Duration:** ~3-4 minutes (dominated by benchmark scrapes) | **Log:** `scripts/kilo-benchmarks/cache/update.log`

## Database Statistics

| Metric | Value |
|--------|-------|
| Total Agents | 332 |
| Active | 332 |
| With Reasoning | 157 |
| Blocked | 2 |

### Blocked Agents

| Agent ID | Name | Reason |
|----------|------|--------|
| `qwen/qwen3-235b-a22b-2507` | Qwen3 235B A22B Instruct 2507 | Ignores documentation prompts - outputs conversational "I'm ready to assist" |
| `deepseek/deepseek-v3.2` | DeepSeek V3.2 | Too slow (109s per review) |

To manage blocked agents: `python manage_blocked.py list|block|unblock`

### Latest Test Results (2026-03-24)

**Documentator Agent Tests:** 40/40 passed | 303s total

| Scenario | File | Agent Used | Time |
|----------|------|------------|------|
| 01 | new_public_function | xAI: Grok 4 Fast | 20s |
| 02 | new_class | xAI: Grok 4 Fast | 22s |
| 03 | new_endpoint | Xiaomi: MiMo-V2-Flash | 28s |
| 04 | new_env_var | Xiaomi: MiMo-V2-Flash | 26s |
| 05 | breaking_change | xAI: Grok 4 Fast | 38s |
| 06 | schema_change | xAI: Grok 4 Fast | 32s |
| 07 | large_change | xAI: Grok 4 Fast | 45s |
| 08 | combined | Xiaomi: MiMo-V2-Flash | 51s |
| 09 | docker_change | Xiaomi: MiMo-V2-Flash | 6s |
| 10 | cli_command | xAI: Grok 4 Fast | 35s |

**Agent selection:** Automatic based on complexity routing. Blocked agents (Qwen3, DeepSeek V3.2) excluded.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  Benchmark      │───▶│  kilo_agents.db  │◀───│  Role Mapper        │
│  Scrapers       │    │  (SQLite)        │    │  (deterministic:    │
│                 │    │                  │    │   floors + cost ↑)  │
└─────────────────┘    └────────┬─────────┘    └─────────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Agent Selector  │
                       │ (Runtime)       │
                       └─────────────────┘
```

## Files

Grouped by pipeline stage. Every active script has an explicit role; the deprecated/scratch ones are called out at the end so newcomers don't waste time on them.

### Storage & schema

| File | Role |
| ---- | ---- |
| `kilo_agents.db` | SQLite database — **source of truth** for agent capabilities, benchmarks, and current role assignments. Tables: `agents`, `agent_roles`, `agent_roles_history`. |
| `kilo_agents.sql` | Schema reference. Mirrors `kilo_agents.db`. Read-only; do not execute against a live DB. |

### Discovery (find what agents exist)

| File | Role | Triggered by | Output |
| ---- | ---- | ------------ | ------ |
| `discover_kilo_agents.py` | Extracts the FULL capability profile of every Kilo CLI model (~332 models): pricing, context window, vision/tools/reasoning flags, variants. | Manual on first setup or after Kilo CLI updates. | `kilo_all_agents.json` |
| `kilo_agents_db.py` | Master DB sync. Reads `kilo_all_agents.json` + local Ollama models, writes/updates rows in `agents`. Also creates daily snapshots and exports. | WSL startup (daily pipeline); CLI: `kilo_agents_db.py all`. | Rows in `agents` table |

### Benchmark ingestion (score every agent)

| File | Role | Source | Updates |
| ---- | ---- | ------ | ------- |
| `scrape_benchmarks.py` | Scrapes Arena ELO from openlm.ai/chatbot-arena and Terminal-Bench accuracy from tbench.ai. | HTML scraping with retry. | `cache/arena_*.{html,json}`, `cache/tbench_*.{html,json}` |
| `scrape_benchlm.py` | Scrapes coding benchmark data from `benchlm.ai/api/data/leaderboard?category=coding` — SWE-bench Pro, weighted_coding, LiveCodeBench. | JSON API. | `cache/benchlm_cache.json` |
| `scrape_artificial_analysis.py` | Scrapes throughput (tokens/sec) + TTFT from artificialanalysis.ai/leaderboards/models, matches to DB agents via canonical (provider, name) keys, applies manual overrides, writes `output_tokens_per_sec` + `ttft_ms` columns. | HTML scraping. | `cache/aa_raw.html`, `cache/aa_parsed.json`, agent rows |
| ~~`scrape_windsurf_models.py`~~ | **Retired 2026-07-20** — moved to `scripts/.archive/scrape_windsurf_models.py`; no longer invoked by the daily pipeline. Windsurf Cascade itself was retired 2026-07-19 (see `project_kilo_cascade_retired`), so the Cascade credit-multiplier catalog it scraped is dead data. The rest of the benchmark-ingestion pipeline below is unaffected and still live. | — | — |
| `update_kilo_benchmarks.py` | Orchestrator: calls the scrapers, builds (model → score) maps, applies them to `kilo_agents.db`, also updates `docs/traycer/kilo_selected_agents.md` and Cascade docs. | WSL startup (daily, with 20 h cache window); `--force` overrides cache. | `cache/benchmark_cache.json`, agent rows, docs |

### Selection pipeline (deterministic, no LLM)

Runs in strict order: `pre_filter` → `selector` → `post_filter` → DB write. All four files live in `scripts/kilo-benchmarks/`.

| File | Role | Reads | Writes |
| ---- | ---- | ----- | ------ |
| `pre_filter.py` | Generates per-role candidate shortlists with hard SQL filters (e.g., coding needs `has_tools=1 AND is_agentic=1`; reviewing needs `has_reasoning=1`). Computes derived metrics (`inverse_total_cost`, `mean_normalized_tbench_elo`, `perf_per_dollar`) per model. Caps each shortlist at 10–12 candidates. | `agents` table | `shortlists.json` |
| `selector.py` | Implements "cheapest-above-floors" selection. For each role: drop models with NULL primary metric, drop models below `quality_floor`, drop models below `speed_floor`, apply optional `cost_cap`, sort survivors by `total_cost` ascending, tiebreak by quality descending, take top `fleet_size`. No padding with dominated picks — empty slots are surfaced honestly. | `shortlists.json`, `role_configs.yaml` | List of assignments + skipped_slots |
| `post_filter.py` | Single unified loop enforcing two constraints on the reviewing fleet: provider dominance (max 2 slots per provider) and family diversity (≥2 distinct providers AND ≥1 not in coding P1–P2). Swaps the lowest-priority offender for the best alternate from a fresh provider (preferring providers not already in coding P1–P2). Max 5 iterations. | Assignments from selector, `shortlists.json` | Mutated assignment list with swap rationale in `reason` |
| `role_mapper.py` | Orchestrator. Calls `pre_filter` → `selector` → `post_filter`, archives the previous `agent_roles` rows into `agent_roles_history`, writes the new assignments. CLI: `--dry-run`, `--show`, `--update-docs`. | All of the above + `agents` | `agent_roles`, `agent_roles_history` |

### Configuration

| File | Role |
| ---- | ---- |
| `role_configs.yaml` | Per-role rules consumed by `selector.py`: `primary_metric`, `quality_floor`, `speed_floor`, optional `cost_cap`, `fleet_size`. Edit this to tune the fleet without touching code. |
| `cache/speed_overrides.json` | Manual `{tps, ttft_ms}` per agent id for models artificialanalysis.ai doesn't track (e.g., Opus 4.6 uses 4.7 as proxy). Each entry carries a `_proxy` field explaining the source. Loaded by `scrape_artificial_analysis.py` and takes precedence over scraped data. |

### Runtime selection (for Kilo CLI wrappers and routers)

| File | Role |
| ---- | ---- |
| `classify_ticket.py` | Rule-based dispatch-time classifier. Returns `(role, confidence)` for a ticket — `coding_simple` for renames/typing/docstrings, `coding_complex` for new features/migrations/integrations. Default-to-complex when uncertain. No LLM. |
| `db_models.py` | Programmatic interface for Kilo wrappers — `get_model_for_priority()`, `get_model_avoiding_provider()` (same-family guard), `get_tier_models()`, `get_fallback_chain()`, `is_model_blocked()`. Legacy `role="coding"` resolves to `coding_complex` via internal alias. |
| `kilo_telemetry.py` | Ticket-outcome telemetry helper. `start_ticket()` opens a `ticket_outcomes` row at classification time; `complete_ticket()` updates it with duration/cost/revisions. Imported by the auto-router. Run standalone with `python kilo_telemetry.py 30` for the 30-day audit summary. |
| `/opt/fabrik/scripts/kilo_auto_route.py` | **Runtime auto-router.** Reads a Traycer ticket from `$TRAYCER_PROMPT`, calls `classify_ticket`, resolves the role to a Kilo model via `db_models`, applies same-family guard if `--exclude-provider` is set, opens a telemetry row, then `exec`s `kilo run`. The file where the architecture's value materializes — see [Dispatcher integration](#dispatcher-integration) below. |
| `/opt/fabrik/scripts/coding-auto.sh` | Thin shell wrapper that Traycer can call directly. Pulls `TRAYCER_PROMPT` / `TRAYCER_PROMPT_TMP_FILE`, computes title and ticket-id, delegates to `kilo_auto_route.py`. Install to `~/.traycer/cli-agents/` to expose to Traycer. |
| `agent_selector.py` | Runtime task-to-agent router. Selects an agent based on task complexity (`simple` / `medium` / `complex`) — see [Complexity Routing](#complexity-routing) for the priority traversal order. |
| `role_selector.py` | CLI/utility for ad-hoc queries: `python role_selector.py --role coding_complex --require-vision`. Less used now that `db_models.py` covers the wrapper path. |

### Operations

| File | Role |
| ---- | ---- |
| `manage_blocked.py` | CLI to block/unblock agents. Sets `agents.blocked = 1` and `agents.block_reason`. Blocked agents are excluded by every selector. Commands: `list`, `block`, `unblock`. |
| `migrate_roles_v2.py` | One-time schema migration (Roles V2): added `blocked` / `block_reason` columns, removed `task_complexity`, pre-blocked known-bad models. Should not need re-running. |

### Caches & intermediate artifacts (under `cache/` unless noted)

| File | What it holds | Lifetime |
| ---- | ------------- | -------- |
| `aa_raw.html` | Last scrape of artificialanalysis.ai leaderboard. | Refreshed on each `scrape_artificial_analysis.py` run. |
| `aa_parsed.json` | Parsed AA rows + match results (`agent_id → {tps, ttft_ms, source}`). | Per scrape. |
| `arena_raw.html`, `arena_parsed.json` | Arena ELO snapshot. | Per `scrape_benchmarks.py` run. |
| `tbench_raw.html`, `tbench_parsed.json` | Terminal-Bench snapshot. | Per `scrape_benchmarks.py` run. |
| `benchlm_cache.json` | BenchLM coding scores. | Per `scrape_benchlm.py` run. |
| ~~`windsurf_raw.html`, `windsurf_parsed.json`~~ | **Stale cache** — was the Windsurf Cascade model catalog. `scrape_windsurf_models.py` retired 2026-07-20 (moved to `scripts/.archive/`); these cache files no longer refresh. | Not refreshed (script retired). |
| `benchmark_cache.json` | Last-update timestamp + combined map, used by `update_kilo_benchmarks.py` to skip runs within the 20 h window. | Refreshed on each successful merge. |
| `update.log` | Append-only log for the daily pipeline. | Manually rotated. |
| `shortlists.json` (top of `kilo-benchmarks/`) | Last `pre_filter.py` output, one section per role. Handy for debugging selection. | Overwritten on every `role_mapper.py` run. |
| `kilo_all_agents.json` | Full discovery output from `discover_kilo_agents.py`. | Refreshed on discovery runs. |
| `kilo_selected_agents.json` | Filtered subset used by docs/traycer. | Refreshed by `update_kilo_benchmarks.py`. |

### Deprecated / scratch (do not extend)

| File | Status |
| ---- | ------ |
| `process.py`, `process_v2.py`, `compute_assignments.py` | One-off scratch utilities from the LLM-based selection era. No docstrings, embedded data dumps. Kept for reference until next cleanup; **do not import or extend**. |

## Quick Start

### View Current Assignments

```bash
python role_mapper.py --show
```

### Run New Role Assignment

```bash
python role_mapper.py
```

### Block/Unblock Agents

```bash
python manage_blocked.py list                          # List blocked
python manage_blocked.py block "agent/id" "reason"     # Block
python manage_blocked.py unblock "agent/id"            # Unblock
```

### Select Agent at Runtime

```python
from agent_selector import select_agent, select_reviewer

# Select by complexity
agent = select_agent("coding", "complex")   # Best coder
agent = select_agent("coding", "simple")    # Cheapest adequate

# Select reviewer with vision
agent = select_reviewer("complex", require_vision=True)
```

---

## Agent Discovery (From Scratch)

If you need to rebuild the agent database from scratch or refresh after Kilo CLI updates:

### Step 1: Discover All Kilo Agents

```bash
cd /opt/fabrik/scripts/kilo-benchmarks
python discover_kilo_agents.py
# Output: kilo_all_agents.json (~332 models with full capabilities)
```

This extracts ALL capabilities from `kilo models --verbose` including:
- Vision, tools, reasoning, audio/video support
- Cost per token (input/output/cache)
- Context window and output limits
- Available variants (thinking modes, etc.)

### Step 2: Scrape Benchmark Scores

```bash
python scrape_benchmarks.py             # Arena ELO + tbench accuracy
python scrape_artificial_analysis.py    # Throughput (tokens/sec) + TTFT
```

### Step 3: Sync to Database

```bash
python update_kilo_benchmarks.py
# Updates kilo_agents.db with scraped data
```

### Step 4: Run Deterministic Role Assignment

```bash
python role_mapper.py --dry-run    # Preview without writing to DB
python role_mapper.py              # Apply to DB

# Pipeline (no LLM in the loop):
# 1. pre_filter.py     — per-role SQL shortlists + derived metrics
# 2. selector.py       — filter by quality_floor + speed_floor, sort by cost ASC
# 3. post_filter.py    — provider dominance + family diversity rules
# 4. role_mapper.py    — archive previous assignments, write new ones
#
# Floors and metrics live in role_configs.yaml. Cheapest qualified agent wins P1.
```

### Step 5: Verify and Block Bad Agents

```bash
# View current assignments
python role_mapper.py --show

# Block agents that don't work well
python manage_blocked.py block "qwen/qwen3-235b" "Ignores structured prompts"

# List blocked agents
python manage_blocked.py list
```

### How Scripts Use Agents

```
kilo_code_review.py  ──reads──▶  kilo_agents.db  ◀──reads──  kilo_docs_enforcer.py
                                      ▲
                                      │
                                  populated by
                                      │
                     discover_kilo_agents.py → role_mapper.py
```

---

## For AI Agents: How to Access Role Assignments

### Option 1: Direct Database Query (Recommended)

```python
import sqlite3
from pathlib import Path

DB_PATH = Path("/opt/fabrik/scripts/kilo-benchmarks/kilo_agents.db")

def get_agent_for_role(role: str, priority: int = 1) -> dict | None:
    """Get assigned agent for a role and priority."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT a.api_id, a.name, a.arena_elo, a.has_vision
        FROM agent_roles r
        JOIN agents a ON a.id = r.agent_id
        WHERE r.role = ? AND r.priority = ?
          AND a.status = 'active' AND a.blocked = 0
    """, (role, priority))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# Example
agent = get_agent_for_role("coding", 1)
print(agent["api_id"])  # e.g., "openai/gpt-5.4"
```

### Option 2: Use db_models Module (For Kilo Wrappers)

```python
import sys
sys.path.insert(0, "/opt/fabrik/scripts/kilo-benchmarks")
from db_models import get_tier_models, get_fallback_chain, is_model_blocked

# Get models by tier (for escalation)
tiers = get_tier_models("reviewing")
# Returns: {"Prime": ["kilo/anthropic/claude-opus-4.6"], "Strong": [...], ...}

# Get fallback chain (priority order)
chain = get_fallback_chain("reviewing")
# Returns: ["kilo/anthropic/claude-opus-4.6", "kilo/google/gemini-3.1-pro-preview", ...]

# Check if model is blocked
if not is_model_blocked("anthropic/claude-opus-4.6"):
    # Use model
    pass
```

**Used by:** `kilo_code_review.py` (replaces hardcoded `TIER_MODELS` and `MODEL_FALLBACK_CHAIN`)

### Option 3: Use agent_selector Module

```python
import sys
sys.path.insert(0, "/opt/fabrik/scripts/kilo-benchmarks")
from agent_selector import select_agent, COMPLEXITY_MAP

# Complexity routing
agent = select_agent("reviewing", "complex")  # Returns dict with api_id, name, etc.
```

### Option 4: Shell Query

```bash
sqlite3 /opt/fabrik/scripts/kilo-benchmarks/kilo_agents.db \
  "SELECT a.api_id FROM agent_roles r JOIN agents a ON a.id = r.agent_id \
   WHERE r.role = 'coding' AND r.priority = 1 AND a.blocked = 0"
```

---

## Database Schema




<!-- AUTO-GENERATED:SCHEMA_AGENTS_START -->

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| **Identity** | | | |
|--------|------|---------|-------------|
| id | TEXT |  | PRIMARY KEY |
| api_id | TEXT |  |  |
| name | TEXT |  |  |
| provider | TEXT |  |  |
| **Pricing** | | | |
|--------|------|---------|-------------|
| input_cost_per_m | REAL | 0 |  |
| output_cost_per_m | REAL | 0 |  |
| **Capabilities** | | | |
|--------|------|---------|-------------|
| context_window_k | INTEGER | 128 |  |
| has_vision | BOOLEAN | FALSE |  |
| has_tools | BOOLEAN | FALSE |  |
| is_agentic | BOOLEAN | FALSE |  |
| **Benchmarks** | | | |
|--------|------|---------|-------------|
| arena_elo | INTEGER |  |  |
| tbench_accuracy | REAL |  |  |
| **Derived Metrics** | | | |
|--------|------|---------|-------------|
| task_tier | INTEGER | 2 |  |
| perf_per_dollar | REAL |  |  |
| **Status** | | | |
|--------|------|---------|-------------|
| status | TEXT | 'active' |  |
| discard_reason | TEXT |  |  |
| **Metadata** | | | |
|--------|------|---------|-------------|
| fallback_model_id | TEXT |  |  |
| last_verified | DATE |  |  |
| created_at | TIMESTAMP | CURRENT_TIMESTAMP |  |
| updated_at | TIMESTAMP | CURRENT_TIMESTAMP |  |
| variant | TEXT | 'standard' |  |
| **Status** | | | |
|--------|------|---------|-------------|
| blocked | INTEGER | 0 |  |
| block_reason | TEXT |  |  |
| **Other** | | | |
|--------|------|---------|-------------|
| has_reasoning | BOOLEAN | FALSE |  |
| humaneval_score | REAL |  |  |
| coding_score | REAL |  |  |

<!-- AUTO-GENERATED:SCHEMA_AGENTS_END -->
### Migration History

- **2026-03-27**: Removed `humaneval_score` and `coding_score` from database (fabricated data)
- **2026-03-26**: Added capability columns to `local_models` table
- **2026-03-26**: Initial schema with hardware tracking for local models

---

## Complexity Routing

Task complexity determines which priority agents are tried. **Priority semantics:
P1 = cheapest qualified, P5 = most expensive fallback** (still above floors). The router
escalates UP the priority list when it needs more quality.

| Complexity | Tries Priorities | Use Case |
| ---------- | ---------------- | -------- |
| `simple` | 1 → 2 → 3 → 4 → 5 | Default. Cheapest qualified agent first. |
| `medium` | 2 → 3 → 1 → 4 → 5 | Skip the cheapest; start from mid-tier. |
| `complex` | 5 → 4 → 3 → 2 → 1 | Hardest tickets. Most expensive (= highest-quality among qualified) first. |

> **Migration note:** prior to 2026-05 the order was inverted (P1 = best capability,
> P5 = cheapest). The selector now uses "cheapest-above-floors" mode — see
> [Selection Pipeline](#selection-pipeline-deterministic) below.

---

## Roles and Selection Criteria

### Priority Scale

Every priority slot meets the role's `quality_floor` AND `speed_floor`. Priorities only
differentiate on cost.

| Priority | Description |
| -------- | ----------- |
| 1 | Cheapest agent meeting all floors — the default for every task |
| 2 | Next-cheapest qualified agent (fallback when P1 rate-limits) |
| 3 | Middle of the cost range |
| 4 | Higher-cost qualified agent (often the highest-quality option) |
| 5 | Most expensive qualified agent — usually a premium model with the best benchmarks |

### Role-Specific Criteria

Configured in `role_configs.yaml`. Both floors must pass; among survivors, sort by
total cost ascending. Models with NULL on the primary metric OR NULL on
`output_tokens_per_sec` are excluded — add manual proxies to
`cache/speed_overrides.json` to bring them back.

| Role | Primary Metric | Quality Floor | Speed Floor (tps) | Cost Cap | Secondary Floor | Fleet Size | Required Capabilities |
| ---- | -------------- | ------------- | ----------------- | -------- | --------------- | ---------- | --------------------- |
| `coding_simple` | `weighted_coding` | 75.0 | 40 | $5/M | — | 5 | `has_tools=1 AND is_agentic=1` |
| `coding_complex` | `weighted_coding` | 85.0 | 40 | none | `tbench_accuracy ≥ 60` | 5 | `has_tools=1 AND is_agentic=1` |
| `reviewing` | `arena_elo` | 1480 | 30 | none | — | 5 | `has_reasoning=1` |
| `fixing` | `mean_normalized_tbench_elo` | 0.70 | 40 | none | `tbench_accuracy ≥ 60` | 5 | `has_tools=1 AND is_agentic=1` |
| `documentation` | `arena_elo` | 1430 | 50 | none | — | 5 | `arena_elo>=1400 AND input_cost<=$1` (pre_filter) |
| `testing` | `tbench_accuracy` | 75.0 | 40 | $20/M | — | 5 | `has_tools=1 AND is_agentic=1` |

**The two coding roles** — `coding_simple` and `coding_complex` — split the original
single `coding` role into a fast-cheap tier (renames, type hints, docstrings, small
single-file changes) and a high-quality tier (new features, migrations, integrations,
multi-file refactors). Tickets are routed at dispatch time by
[`classify_ticket.py`](../../scripts/kilo-benchmarks/classify_ticket.py) — see
[Ticket Classification](#ticket-classification) below. Legacy callers passing
`role="coding"` resolve to `coding_complex` via the alias in `db_models.py`.

### Ticket Classification

The two coding roles only matter if tickets land on the right one. Classification
runs at **dispatch time** (when the Kilo wrapper or Traycer router asks "which
coding role do I use?"), not at selection time. Implemented in
[`classify_ticket.py`](../../scripts/kilo-benchmarks/classify_ticket.py).

**Rule-based, no LLM.** Cheap (microseconds), deterministic, explainable. Three
ordered rule layers:

1. **Hard rules first.** `estimated_files >= 3` OR `estimated_lines >= 100`
   → `coding_complex`. Size dominates everything else.
2. **Keyword voting.** Lowercased `title + description` matched against two
   curated keyword sets:
   - `COMPLEX_KEYWORDS`: design, architect, refactor, migrate, integrate, webhook,
     queue, performance, optimize, auth, security, schema, breaking change, etc.
   - `SIMPLE_KEYWORDS`: rename, type hint, docstring, format, lint, import,
     logger, constant, todo, etc.
   If a complex keyword fires → `coding_complex`. Else if a simple keyword fires
   → `coding_simple`. **Complex wins ties** when both match.
3. **Default to complex** when nothing matches. Misrouting a simple ticket to
   the complex tier costs ~$15 in API spend; misrouting a complex ticket to the
   simple tier ships broken code that has to be reworked. Cost regression beats
   quality regression every time.

**Return shape:** `(role, confidence)` where `confidence` identifies which rule
fired — `"rule:files>=3"`, `"rule:lines>=100"`, `"keyword:complex"`,
`"keyword:simple"`, or `"default:complex"`. Log this alongside the role in
`ticket_outcomes` (see [Telemetry](#telemetry)) so you can
audit classifier behaviour and refine the keyword lists over time.

**Integration pattern** (Kilo wrapper / Traycer router):

```python
from classify_ticket import classify_ticket
from db_models import get_model_for_priority

role, confidence = classify_ticket(ticket)            # "coding_simple" | "coding_complex"
model = get_model_for_priority(role, priority=1)      # cheapest qualified for that tier
# ... dispatch to model, then log outcome
```

**Exhaustion fallback** (when the entire `coding_simple` fleet is rate-limited).
The current snapshot has only 3 entries in `coding_simple` (Qwen3.6 Plus, Kimi K2.5,
GLM 5) and the floor + cost cap will never produce 5; that's by design, not a bug.
If all three are unavailable simultaneously, the dispatcher MUST have a documented
fallback. **Default policy: fall through to `coding_complex` P1.** Ships the ticket
at higher cost rather than dropping it.

```python
role, confidence = classify_ticket(ticket)
for priority in range(1, 6):                          # walk the tier's priorities
    model = get_model_for_priority(role, priority)
    if model and provider_available(model):           # 429/5xx-aware health probe
        break
else:
    # Exhausted the requested tier — escalate, never drop.
    if role == "coding_simple":
        model = get_model_for_priority("coding_complex", priority=1)
    else:
        raise NoQualifiedAgent(role=role, ticket_id=ticket["id"])
```

Watch the telemetry: if `coding_simple` exhaustion fires more than ~5% of dispatched
simple tickets, the cost savings are leaking. Either widen the simple-tier admission
(lower `weighted_coding` floor from 75 to 72, raise cost cap from $5 to $7) or add a
queue-and-retry path before falling through.

**Ship test** — run these five tickets through the classifier and confirm the
expected role:

| Ticket | Expected | Why |
| ------ | -------- | --- |
| "Rename `db_path` to `database_path`" | `coding_simple` | "rename" matches simple list |
| "Add type hints to `process_event()`" | `coding_simple` | "type hints" matches simple list |
| "Implement OAuth2 token refresh flow" | `coding_complex` | "oauth" matches complex list |
| "Migrate from psycopg2 to asyncpg in scheduler" | `coding_complex` | "migrate" matches + estimated_files≥3 |
| "Fix the import ordering" (ambiguous) | `coding_simple` | "import" matches simple; no complex hit |

Run `python scripts/kilo-benchmarks/classify_ticket.py` to execute the test suite.

### Telemetry

A SQLite table in `kilo_agents.db` tracks every dispatched ticket so the
classifier and floors can be tuned from real data, not guesses.

```sql
CREATE TABLE ticket_outcomes (
    ticket_id TEXT PRIMARY KEY,
    role_called TEXT NOT NULL,           -- coding_simple | coding_complex | reviewing | fixing | documentation | testing
    classifier_confidence TEXT NOT NULL, -- 'rule:files>=3', 'keyword:complex', 'default:complex', ...
    priority_used INTEGER,               -- 1-5, which slot the dispatcher actually called
    agent_used TEXT,                     -- e.g., 'kilo/google/gemini-3.1-pro-preview'
    cost_usd REAL,
    revisions_needed INTEGER DEFAULT 0,
    bug_shipped INTEGER DEFAULT 0,
    duration_seconds REAL,
    classified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

What this lets you answer after 100 tickets:

- **How often does `default:complex` fire?** High % → keyword lists are weak; add the missing patterns.
- **How often do `coding_simple` tickets need revisions?** High → floor too low; bump `weighted_coding` floor from 75 to 78.
- **Did `coding_complex` tickets actually need premium models?** If P4-P5 are rarely called, the cost cap can drop.
- **Provider-outage exposure** — group `agent_used` by provider and date to see real concentration in practice vs. the snapshot in the [Final Assignment Table](#final-assignment-table-2026-05-13).

The router writes one row per ticket; the analyst (or a future cron job) reads it.

**First audit query** — run after the first ~50 dispatched tickets to see the
classifier+floors against real workload:

```sql
SELECT
    role_called,
    classifier_confidence,
    COUNT(*)                          AS n,
    ROUND(AVG(revisions_needed), 2)   AS avg_revisions,
    ROUND(SUM(cost_usd), 2)           AS total_cost_usd,
    ROUND(AVG(duration_seconds), 1)   AS avg_seconds,
    SUM(bug_shipped)                  AS bugs_shipped
FROM ticket_outcomes
WHERE classified_at > datetime('now', '-30 days')
GROUP BY role_called, classifier_confidence
ORDER BY n DESC;
```

Interpretation cheat sheet:

| Pattern in output | Meaning | Fix |
| ----------------- | ------- | --- |
| `default:complex` is a top-3 row | Keyword lists miss real patterns | Add the missing nouns/verbs to `SIMPLE_KEYWORDS` or `COMPLEX_KEYWORDS` |
| `coding_simple` rows have `avg_revisions > 0.3` | Floor too low or wrong agents | Raise `weighted_coding` floor to 78, or add `tbench_accuracy >= 50` secondary floor |
| `coding_complex` rows have `bugs_shipped > 0` | Premium tier shipping broken code | Audit `agent_used` — may need to block a specific model |
| `coding_complex` with `avg_revisions = 0` AND agent_used identical | That ticket type is safely routable to simple | Move its keyword from `COMPLEX_KEYWORDS` to `SIMPLE_KEYWORDS` |
| Wide gap between `coding_simple` total_cost and `coding_complex` total_cost | Working as designed — savings are real | Confirm before further tuning |

Re-run the query monthly. Decisions backed by 50+ rows are durable; decisions on 5 rows are noise.

### Dispatcher integration

Everything above describes how agents are *selected*. None of it saves a single dollar
until something *calls* the selection at ticket dispatch time. That's what
`scripts/kilo_auto_route.py` does, and it's the file Traycer should invoke instead
of the per-role agent scripts in `~/.traycer/cli-agents/`.

**Three runtime concerns, one file:**

1. **Classification** — `classify_ticket(ticket)` returns `(role, confidence)`.
2. **Resolution** — `get_model_for_priority(role, priority=1)` returns the cheapest qualified `kilo/...` id; or `get_model_avoiding_provider(role, exclude_provider)` for the same-family guard.
3. **Telemetry** — `start_ticket(...)` opens a row at classification time, `complete_ticket(...)` closes it with duration when Kilo exits.

**Wiring:** Traycer calls [`scripts/coding-auto.sh`](../../scripts/coding-auto.sh) (a thin shell wrapper that reads `$TRAYCER_PROMPT` and execs `kilo_auto_route.py`). Install once:

```bash
cp /opt/fabrik/scripts/coding-auto.sh ~/.traycer/cli-agents/
chmod +x ~/.traycer/cli-agents/coding-auto.sh
```

After that, every Traycer dispatch of `coding-auto.sh` runs the full pipeline: classifier picks `coding_simple` or `coding_complex`, the cheapest qualified model wins, a telemetry row gets opened, Kilo runs, the row gets closed with the actual duration.

**Same-family guard at runtime.** When orchestrating a code → review chain, capture the coder's provider and feed it to the reviewer dispatch:

```bash
# 1. Dispatch the coder (auto-classified, may pick any provider)
python /opt/fabrik/scripts/kilo_auto_route.py \
    --ticket-id "$TICKET_ID-code" --auto-classify

# 2. Discover which provider was chosen
CODER_PROVIDER=$(python /opt/fabrik/scripts/kilo_auto_route.py \
    --role coding_complex --description "noop" --print-provider)

# 3. Dispatch the reviewer with cross-family preference
python /opt/fabrik/scripts/kilo_auto_route.py \
    --ticket-id "$TICKET_ID-review" --role reviewing \
    --exclude-provider "$CODER_PROVIDER"
```

`get_model_avoiding_provider()` walks priorities 1 → 5 and returns the first agent whose provider is NOT `$CODER_PROVIDER`. If every reviewing slot is the same provider, it falls through to the cheapest qualified rather than dropping the ticket — the `resolution` field on the telemetry row records `"same-family-guard:fallback"` so audits can spot when the guard ran out of options.

**What gets logged.** Every dispatch writes one `ticket_outcomes` row:

| Column | Value |
| ------ | ----- |
| `ticket_id` | `$TRAYCER_TASK_ID` (or generated UUID for ad-hoc runs) |
| `role_called` | e.g. `coding_complex` |
| `classifier_confidence` | `"keyword:complex\|priority-1"` — classifier rule + resolution path |
| `priority_used` | actual priority dispatched (after same-family escalation) |
| `agent_used` | full `kilo/provider/model` id |
| `duration_seconds` | wall time from dispatcher start to Kilo exit |
| `cost_usd` | Summed from `step_finish` events in Kilo's `--format json` output (see below). NULL only if `--format default` was used or the run had no step_finish events. |
| `revisions_needed` / `bug_shipped` | `0` by default; the orchestrator updates these later from review outcomes |

**How `cost_usd` gets captured.** The dispatcher invokes Kilo with `--format json`,
which makes Kilo emit a stream of concatenated JSON event objects. `parse_kilo_json_stream`
in `kilo_telemetry.py` walks that stream and:

- sums `cost` from every `type:"step_finish"` event into the final `cost_usd`
- concatenates every `type:"text"` event into a single string, which the dispatcher
  re-emits to stdout so Traycer / the caller sees the model's response unchanged
- tracks `had_step_finish` — if no step_finish appeared, the run was incomplete
  and the dispatcher writes `cost_usd=NULL` rather than misleadingly logging `$0`

If a caller passes `--format default` to the dispatcher (e.g. for interactive
streaming where buffering output is bad), the parser is bypassed and `cost_usd`
stays NULL. That's the explicit trade-off — streaming or cost capture, pick one
per invocation.

**Different from `.droid/kilo_usage.jsonl`.** `kilo_code_review.py` writes that
file with aggregated review/fix session totals (one row per review session).
`ticket_outcomes` is per-ticket and per-dispatcher-call. Both use the same
underlying cost source (step_finish events) but record different units of work.
`kilo_cost_report.py` reads the `.droid/` log; the audit query above reads
`ticket_outcomes`. They complement rather than duplicate.

**Day-to-day audit:** `python scripts/kilo-benchmarks/kilo_telemetry.py 30` prints the recommended summary across the last 30 days. The interpretation cheat-sheet in the [Telemetry](#telemetry) section above tells you which output patterns justify which floor / keyword changes.

### Hard Rules (Enforced by selector.py + post_filter.py)

1. **SKIP** any agent where the role's primary metric is NULL (metric homogeneity — no cross-metric ranking).
2. **SKIP** any agent where `output_tokens_per_sec` is NULL (can't verify speed floor).
3. Only `status='active' AND blocked=0` agents are considered.
4. **Provider dominance** (reviewing only): max 2 slots per provider. Violations trigger a swap to the next-best alternate, preferring providers not already in coding P1–P2.
5. **Family diversity** (reviewing only): ≥2 distinct providers AND ≥1 provider not present in coding P1–P2.
6. The SAME agent CAN appear in multiple roles.
7. **Fleet size is a maximum, not a target.** If only 3 agents meet the floors, assign 3 — never pad with sub-floor or dominated picks. Unfilled slots are tracked in `skipped_slots` with the exact reason.
8. **Cost monotonicity invariant** — within every role, priority N+1 has total cost ≥ priority N. The selector outputs cost-ascending order by construction; `post_filter.py` re-sorts every role and reassigns priorities after any swap so a dominance/diversity swap can never silently invert P4/P5. Logged as `Monotonicity re-sort: <role> P<old> → P<new>` in warnings when it fires.

### Selection Pipeline (Deterministic)

The pipeline is `pre_filter` → `selector` → `post_filter` → DB write. No LLM in the loop.

**1. `pre_filter.py`** — produces per-role candidate lists with SQL hard filters and
derived metrics. Outputs `shortlists.json`.

- Coding: `has_tools=1 AND is_agentic=1`, ranked by `weighted_coding`
- Reviewing: `has_reasoning=1`, ranked by `arena_elo`
- Fixing: `has_tools=1 AND is_agentic=1`, ranked by `mean_normalized_tbench_elo` = `(tbench_accuracy/100 + arena_elo/1600) / 2`
- Documentation: `arena_elo>=1400 AND input_cost<=$1.00`, ranked by `arena_elo`
- Testing: `has_tools=1 AND is_agentic=1`, ranked by `tbench_accuracy` (fallback: `weighted_coding`)

**2. `selector.py`** — "cheapest-above-floors" mode. For each role:

1. Apply `cost_cap` if specified.
2. Drop models whose primary metric is below `quality_floor`.
3. Drop models whose `output_tokens_per_sec` is below `speed_floor` (or NULL).
4. Sort survivors by `total_cost = input_cost + output_cost` ascending.
5. Tiebreak by primary metric descending (equal-cost slots prefer higher quality).
6. Take top N (`fleet_size`, default 5).

Prints one debug line per role showing the qualified fleet:
`[selector] coding qualified (weighted_coding≥80.0, speed≥40.0tps): kimi-k2.5(82.60/66tps@$2.30), ...`

**3. `post_filter.py`** — single unified swap loop. Enforces dominance + diversity in
one pass (max 5 iterations). When a swap is needed, picks the lowest-priority offender
and replaces it with the best-ranked alternate from a provider not already used.

**Properties:** $0 cost, ~50ms runtime, byte-identical output across re-runs, full
traceability (skipped slots + dominance swaps explained in `reason` fields).

**Cost:** $0/day | **Duration:** ~50ms | **Log:** `scripts/kilo-benchmarks/cache/update.log`

---

## Workflow

1. **Discover** — `discover_kilo_agents.py` extracts capabilities from `kilo models --verbose`
2. **Scrape** — `scrape_benchmarks.py` (arena + tbench) and `scrape_artificial_analysis.py` (throughput + TTFT)
3. **Sync** — `update_kilo_benchmarks.py` writes benchmark data to `kilo_agents.db`
4. **Override** — edit `cache/speed_overrides.json` to fill gaps for models AA doesn't track (proxy from a sibling version)
5. **Assign** — `role_mapper.py` runs the deterministic pipeline and writes 5 agents per role
6. **Test** — Manual testing; no dedicated results log exists (`AGENT_TESTING.md` does not exist anywhere in the repo — confirmed absent 2026-07-20). Notable findings go to `docs/LESSONS_LEARNT.md` instead.
7. **Block** — `manage_blocked.py` to exclude problematic agents
8. **Select** — `agent_selector.py` for runtime agent selection

### WSL Startup Automation

The entire workflow runs automatically on WSL startup via `.bashrc` hooks:

```bash
# In ~/.bashrc (add these lines):
source /opt/fabrik/scripts/wsl_startup_hook.sh
[ -f /opt/fabrik/scripts/kilo_model_sync_startup.sh ] && /opt/fabrik/scripts/kilo_model_sync_startup.sh
```

> **Full startup pipeline reference:** `docs/workflows/DATA_SYNC_WORKFLOW.md`

**Persistent processes (started on every WSL boot, run continuously):**
- `watch_env_changes.sh` — Monitors `/opt/*/.env` file changes via `inotifywait` and runs the **read-only** `audit_envs.py` violation audit. Log: `.tmp/env_watcher.log`
  - **Note:** the old `consolidate_envs.py --apply` auto-sync is **deprecated** (script retired to `scripts/consolidate_envs.py.deprecated`), so that consolidation is dormant. `/opt/fabrik/.env` is now the **canonical** source, maintained directly and mirrored off-site by the W9 DR watcher (`fabrik-dr-watcher.service` + `scripts/dr_env_backup.sh`). See `docs/operations/credential-recovery.md`.

**Daily pipeline (runs once per WSL boot day, non-blocking, chained):**

1. `sync_projects.py` — Refresh project registry + BUSINESS_MODEL.md + PORTS.md
2. `sync_cascade_backup.sh` — Check Cascade memory backup freshness (warn if >7d)
3. `health_summary.py` — Scaffold health overview across all projects
4. `kilo_agents_db.py all` — Sync model catalog from Kilo CLI + Ollama; daily snapshot + export
5. `update_kilo_benchmarks.py --force` — Scrape Arena ELO + Terminal-Bench, write to DB
6. `scrape_artificial_analysis.py` — Scrape throughput (tokens/sec) + TTFT from artificialanalysis.ai, apply `cache/speed_overrides.json`, write to DB
7. `role_mapper.py` — Deterministic role assignment (pre_filter → selector → post_filter → DB write). ~50ms, $0, byte-identical re-runs
8. `generate_kilo_agents.py` — **Generate Traycer CLI agent scripts** from current `agent_roles`
9. `sync_extensions.sh` — Windsurf extensions documentation

**Failure handling:** the Kilo sub-pipeline (steps 4–8) is chained with `&&` — if any step fails, the rest are skipped and the log shows the break point. Steps 1–3 and 9 are advisory and use `;` so cascade failures don't block downstream steps. Set `FABRIK_DISABLE_KILO_WORKFLOW=1` in the environment to skip steps 4–8 entirely.

**Schema Documentation Auto-Generation:**
- When `sync` detects schema changes (new columns), it automatically updates this file's schema section
- When `ollama-sync` detects schema changes, it updates `LOCAL_LLM_INFRASTRUCTURE.md` schema section
- Manual trigger: `kilo_agents_db.py schema-docs`

**Lock files prevent duplicate runs:** `/tmp/.fabrik_daily_YYYYMMDD`

**Logs:**
- Daily pipeline: `/opt/fabrik/scripts/kilo-benchmarks/cache/update.log`
- Env watcher: `/opt/fabrik/.tmp/env_watcher.log`

---

## Traycer CLI Agent Generation

`generate_kilo_agents.py` reads coding/fixing role assignments from `kilo_agents.db` and generates Traycer CLI agent scripts in `~/.traycer/cli-agents/`.

### Naming Convention

```
code&fix-{priority}-{model}-{variant}-o{OUT}-ppd{PPD}.sh
```

| Component | Description |
|-----------|-------------|
| `code&fix` | Role (combined coding+fixing if same variant) |
| `{priority}` | Priority rank (1=best, 4=fallback) |
| `{model}` | Normalized model name (e.g., `opus46`, `gpt54`) |
| `{variant}` | Thinking mode (`max` or `high`) |
| `o{OUT}` | Output cost per 1M tokens × 100 |
| `ppd{PPD}` | Performance Per Dollar score |

### Variant Strategy

| Priority | Variant | Rationale |
|----------|---------|-----------|
| 1-2 | `max` | Top agents — full reasoning for accuracy |
| 3-4 | `high` | Fallback agents — balanced cost/quality |

### Deduplication

Agents appearing in both coding and fixing with same variant are combined into a single `code&fix-*` script.

### Manual Run

```bash
# Dry run
python /opt/fabrik/scripts/generate_kilo_agents.py --dry-run

# Generate scripts
python /opt/fabrik/scripts/generate_kilo_agents.py
```

### Output

Scripts are generated in `~/.traycer/cli-agents/`:

```
code&fix-1-opus46-max-o2500-ppd076.sh                    # Opus 4.6 (coding #1, fixing #1)
coding-2-gpt54-max-o1500-ppd123.sh                       # GPT-5.4 (coding #2)
coding-3-gemini31pro-high-o1200-ppd161.sh                # Gemini 3.1 Pro (coding #3)
code&fix-4-gpt53codex-high-o1400-ppd---.sh               # GPT-5.3-Codex (coding #4, fixing #4)
fixing-2-gemini31pro-max-o1200-ppd161.sh                 # Gemini 3.1 Pro (fixing #2)
fixing-3-gpt54-high-o1500-ppd123.sh                      # GPT-5.4 (fixing #3)
coding-1-fabrik-coder-qwen32b-local-o0000-ppd999.sh      # Qwen 2.5 Coder 32B (local)
fixing-1-fabrik-fixer-ds16b-local-o0000-ppd999.sh        # DeepSeek Coder V2 16B (local)
documentation-1-fabrik-docs-llama8b-local-o0000-ppd999.sh # Llama 3.1 8B (local docs)
reviewing-1-fabrik-reviewer-llama70b-local-o0000-ppd999.sh # Llama 3.1 70B (local review)
```

---

## Model Capability Extraction

`discover_kilo_agents.py` extracts ALL capabilities from `kilo models --verbose`:

### Extracted Fields

| Field | Type | Description |
|-------|------|-------------|
| **Core Capabilities** | | |
| `has_reasoning` | bool | Extended thinking/reasoning mode |
| `has_tools` | bool | Function/tool calling support |
| `has_attachment` | bool | File attachment support |
| `has_temperature` | bool | Temperature parameter support |
| `has_interleaved` | bool | Interleaved input/output |
| **Input Modalities** | | |
| `input_text` | bool | Text input |
| `input_image` | bool | Image/vision input |
| `input_audio` | bool | Audio input |
| `input_video` | bool | Video input |
| `input_pdf` | bool | PDF document input |
| **Output Modalities** | | |
| `output_text` | bool | Text output |
| `output_image` | bool | Image generation |
| `output_audio` | bool | Audio/speech output |
| `output_video` | bool | Video generation |
| **Costs** | | |
| `input_cost` | float | Cost per input token |
| `output_cost` | float | Cost per output token |
| `cache_read_cost` | float | Prompt cache read cost |
| `cache_write_cost` | float | Prompt cache write cost |
| **Limits** | | |
| `context_window` | int | Max context tokens |
| `max_output` | int | Max output tokens |
| **Metadata** | | |
| `release_date` | str | Model release date |
| `variants` | dict | Available variants (e.g., thinking modes) |

### Usage

```bash
# Refresh all model capabilities
python discover_kilo_agents.py

# Output: kilo_all_agents.json (~332 models)
```

---

## kilo_code_review.py Workflow

The main code review script follows this step-by-step process:

### Phase 1: Pre-Commit Checks
1. Run `pre-commit` hooks if available (formatting, linting)
2. Skip if pre-commit not installed

### Phase 2: Diff Collection
1. Collect staged diff (`git diff --staged`) or file diff
2. Calculate diff statistics (files, lines changed)
3. Determine risk level based on:
   - File paths (security-sensitive dirs)
   - File types (credentials, configs)
   - Change volume

### Phase 3: Model Selection (DB-Driven)

Under cheapest-above-floors semantics, every priority slot for `reviewing` already
meets the quality + speed floors. Risk-based selection only chooses **how high to
start in the cost ladder**, not whether quality is acceptable.

1. Query `kilo_agents.db` for models assigned to `reviewing` role.
2. Pick a starting priority based on risk, then escalate:
   - **High risk** → start at P5 (most expensive qualified = highest quality among survivors), fall back to P4 if rate-limited
   - **Medium risk** → start at P3 (mid-cost), fall back P4 → P5
   - **Low risk** → start at P1 (cheapest qualified), fall back P2 → P3
3. Validate model has `has_reasoning=1` (required for code review).
4. Build fallback chain from DB priorities. The legacy tier names in
   [`db_models.py`](../../scripts/kilo-benchmarks/db_models.py) still work —
   "Prime" tier resolves to P5, "Free" to P1 — but new code should reference
   priority numbers directly to avoid the cognitive flip.

### Phase 4: Review Execution
1. Build prompt with:
   - System instructions (output schema, severity levels)
   - Plan description (what the code should do)
   - Full diff content
2. Call Kilo CLI: `kilo run --model <model> --format json --auto`
3. Parse JSONL response (handle streaming events)
4. Validate response against JSON schema

### Phase 5: Retry Logic
- **Idle timeout (120s)**: If no output for 120s, retry with same model
- **Schema validation failure**: Retry with JSON skeleton hint
- **Model errors**: Escalate to next model in fallback chain
- **Max 3 iterations** per review

### Phase 6: Issue Management
1. Parse issues from response
2. Deduplicate against previous iterations
3. Track issue state (open, fixed, wontfix)
4. Output results (JSON, Markdown, or plain)

### Timeout Behavior

The 120-second **idle timeout** triggers when:
- No output is received for 120 consecutive seconds
- The model may still be "thinking" but not streaming

**What happens:**
1. Current request is killed
2. Same prompt is retried with same model
3. After 2 retries, escalates to fallback model

**Limitation:** Kilo CLI doesn't support interactive/streaming progress. The timeout is a safeguard against hung requests, not a reflection of model capability.

**Workaround for long-running reviews:**
```bash
# Increase timeout (not recommended - masks real issues)
# Edit kilo_code_review.py: IDLE_TIMEOUT_SECONDS = 180
```

---

## Final Assignment Table (2026-05-13)

**Source:** `kilo_agents.db` agent_roles table | **Assigned by:** `cheapest-above-floors` | **Order:** P1 = cheapest qualified, P5 = most expensive (= highest quality among survivors)

| Role | Pri | Agent | ELO | TBench | WC | tps | Vision | Reason | $/M In | $/M Out | Total $/M |
| ---- | --- | ----- | --- | ------ | -- | --- | ------ | ------ | ------ | ------- | --------- |
| coding_complex | 1 | Google: Gemini 3.1 Pro Preview | 1531 | 80.2% | 93.9 | 133 | ✅ | ✅ | $2.00 | $12.00 | $14.00 |
| coding_complex | 2 | OpenAI: GPT-5.3-Codex | — | 78.4% | 88.7 | 87 | ✅ | ✅ | $1.75 | $14.00 | $15.75 |
| coding_complex | 3 | OpenAI: GPT-5.4 | 1468 | 81.8% | 89.3 | 74 | ✅ | ✅ | $2.50 | $15.00 | $17.50 |
| coding_complex | 4 | Anthropic: Claude Opus 4.6 | 1535 | 79.8% | 86.9 | 72 | ✅ | ✅ | $5.00 | $25.00 | $30.00 |
| coding_simple | 1 | Qwen: Qwen3.6 Plus | 1482 | — | 77.9 | 53 | ✅ | — | $0.33 | $1.95 | $2.27 |
| coding_simple | 2 | MoonshotAI: Kimi K2.5 | — | 43.2% | 82.6 | 66 | ✅ | ✅ | $0.40 | $1.90 | $2.30 |
| coding_simple | 3 | Z.ai: GLM 5 | 1461 | 52.4% | 77.0 | 75 | — | ✅ | $0.60 | $1.92 | $2.52 |
| documentation | 1 | Z.ai: GLM 4.7 | 1460 | 33.4% | 74.7 | 70 | — | ✅ | $0.40 | $1.75 | $2.15 |
| documentation | 2 | Qwen: Qwen3.6 Plus | 1482 | — | 77.9 | 53 | ✅ | — | $0.33 | $1.95 | $2.27 |
| documentation | 3 | Z.ai: GLM 5 | 1461 | 52.4% | 77.0 | 75 | — | ✅ | $0.60 | $1.92 | $2.52 |
| documentation | 4 | Qwen: Qwen3.5 397B A17B | 1463 | — | — | 52 | ✅ | ✅ | $0.39 | $2.34 | $2.73 |
| documentation | 5 | Google: Gemini 3 Flash Preview | 1470 | 64.3% | 58.2 | 174 | ✅ | ✅ | $0.50 | $3.00 | $3.50 |
| fixing | 1 | Google: Gemini 3 Flash Preview | 1470 | 64.3% | 58.2 | 174 | ✅ | ✅ | $0.50 | $3.00 | $3.50 |
| fixing | 2 | Google: Gemini 3.1 Pro Preview | 1531 | 80.2% | 93.9 | 133 | ✅ | ✅ | $2.00 | $12.00 | $14.00 |
| fixing | 3 | Google: Gemini 3 Pro Preview | 1501 | 69.4% | 74.1 | 130 | ✅ | ✅ | $2.00 | $12.00 | $14.00 |
| fixing | 4 | OpenAI: GPT-5.2 | 1465 | 64.9% | 82.4 | 74 | ✅ | ✅ | $1.75 | $14.00 | $15.75 |
| fixing | 5 | OpenAI: GPT-5.4 | 1468 | 81.8% | 89.3 | 74 | ✅ | ✅ | $2.50 | $15.00 | $17.50 |
| reviewing | 1 | Google: Gemini 3.1 Pro Preview | 1531 | 80.2% | 93.9 | 133 | ✅ | ✅ | $2.00 | $12.00 | $14.00 |
| reviewing | 2 | Google: Gemini 3 Pro Preview | 1501 | 69.4% | 74.1 | 130 | ✅ | ✅ | $2.00 | $12.00 | $14.00 |
| reviewing | 3 | OpenAI: GPT-5.4 | 1468 | 81.8% | 89.3 | 74 | ✅ | ✅ | $2.50 | $15.00 | $17.50 |
| reviewing | 4 | Anthropic: Claude Sonnet 4.6 | 1500 | — | 83.1 | 52 | ✅ | ✅ | $3.00 | $15.00 | $18.00 |
| reviewing | 5 | Anthropic: Claude Opus 4.6 | 1535 | 79.8% | 86.9 | 72 | ✅ | ✅ | $5.00 | $25.00 | $30.00 |
| testing | 1 | Google: Gemini 3.1 Pro Preview | 1531 | 80.2% | 93.9 | 133 | ✅ | ✅ | $2.00 | $12.00 | $14.00 |
| testing | 2 | OpenAI: GPT-5.3-Codex | — | 78.4% | 88.7 | 87 | ✅ | ✅ | $1.75 | $14.00 | $15.75 |
| testing | 3 | OpenAI: GPT-5.4 | 1468 | 81.8% | 89.3 | 74 | ✅ | ✅ | $2.50 | $15.00 | $17.50 |

---

## Query Current Assignments

```bash
sqlite3 -header -column kilo_agents.db \
  "SELECT r.role, r.priority, a.name, a.arena_elo
   FROM agent_roles r JOIN agents a ON a.id = r.agent_id
   ORDER BY r.role, r.priority"
```

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/generate_kilo_agents.py`
- `scripts/kilo-benchmarks/agent_selector.py`
- `scripts/kilo-benchmarks/classify_ticket.py`
- `scripts/kilo-benchmarks/db_models.py`
- `scripts/kilo-benchmarks/kilo_telemetry.py`
- `scripts/kilo_auto_route.py`
<!-- END related-scripts -->
