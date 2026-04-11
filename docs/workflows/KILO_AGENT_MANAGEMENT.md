# Kilo Agent Management

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
3. `role_mapper.py` - AI-powered role assignment via Gemini 3.1 Pro (~$0.18)
   - Analyzes candidates and assigns to roles
   - Includes both Kilo CLI models and custom local agents
4. `generate_kilo_agents.py` - Generate CLI agent scripts in `~/.traycer/cli-agents/` (FREE)

**Cost:** ~$0.18/day | **Duration:** ~3-4 minutes | **Log:** `scripts/kilo-benchmarks/cache/update.log`

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
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Benchmark      │───▶│  kilo_agents.db  │◀───│  Role Mapper    │
│  Scrapers       │    │  (SQLite)        │    │  (AI-powered)   │
└─────────────────┘    └────────┬─────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Agent Selector  │
                       │ (Runtime)       │
                       └─────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `kilo_agents.db` | SQLite database — **source of truth** |
| `kilo_agents.sql` | Database schema |
| `db_models.py` | **DB-driven model selection for Kilo wrappers** (replaces hardcoded lists) |
| `role_mapper.py` | AI-powered role assignment (uses Gemini 3.1 Pro) |
| `role_selector.py` | Role selection utilities |
| `agent_selector.py` | Runtime agent selection by task complexity |
| `manage_blocked.py` | CLI to block/unblock agents |
| `kilo_agents_db.py` | Database operations and sync |
| `scrape_benchmarks.py` | Scrape arena/tbench scores |
| `update_kilo_benchmarks.py` | Update DB with scraped data |
| `discover_kilo_agents.py` | Discover ALL Kilo agents with full capabilities |
| `migrate_roles_v2.py` | Schema migration (Roles V2) |
| `assignments.json` | Cached role assignments |
| `kilo_all_agents.json` | Full agent discovery cache |
| `kilo_selected_agents.json` | Filtered agent selection cache |

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
python scrape_benchmarks.py
# Gets arena ELO and tbench accuracy from leaderboards
```

### Step 3: Sync to Database

```bash
python update_kilo_benchmarks.py
# Updates kilo_agents.db with scraped data
```

### Step 4: Run AI Role Assignment

```bash
python role_mapper.py
# Uses Gemini 3.1 Pro to assign 5 agents per role based on:
# - coding: tbench_accuracy + has_tools
# - reviewing: arena_elo + has_vision
# - fixing: tbench + elo combined
# - documentation: perf_per_dollar (cheap + adequate)
# - testing: tbench_accuracy
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

Task complexity determines which priority agents are tried:

| Complexity | Tries Priorities | Use Case |
|------------|------------------|----------|
| `simple` | 5 → 4 → 3 → 2 → 1 | Cheapest first |
| `medium` | 3 → 2 → 4 → 1 → 5 | Balanced |
| `complex` | 1 → 2 → 3 | Best only (fails if unavailable) |

---

## Roles

| Role | Primary Criteria | Agents |
|------|------------------|--------|
| `coding` | tbench_accuracy + has_tools | 5 |
| `reviewing` | arena_elo + has_vision | 5 |
| `fixing` | tbench + elo combined | 5 |
| `documentation` | perf_per_dollar | 5 |
| `testing` | tbench_accuracy | 5 |

---

## Workflow

1. **Discover** — `discover_kilo_agents.py` extracts ALL capabilities from `kilo models --verbose`
2. **Scrape** — `scrape_benchmarks.py` gets latest arena/tbench scores
3. **Sync** — `update_kilo_benchmarks.py` updates database
4. **Assign** — `role_mapper.py` uses AI to assign 5 agents per role
5. **Test** — Manual testing, results logged in `AGENT_TESTING.md`
6. **Block** — `manage_blocked.py` to exclude problematic agents
7. **Select** — `agent_selector.py` for runtime agent selection

### WSL Startup Automation

The entire workflow runs automatically on WSL startup via `.bashrc` hooks:

```bash
# In ~/.bashrc (add these lines):
source /opt/fabrik/scripts/wsl_startup_hook.sh
[ -f /opt/fabrik/scripts/kilo_model_sync_startup.sh ] && /opt/fabrik/scripts/kilo_model_sync_startup.sh
```

> **Full startup pipeline reference:** `docs/workflows/DATA_SYNC_WORKFLOW.md`

**Persistent processes (started on every WSL boot, run continuously):**
- `watch_env_changes.sh` — Monitors `/opt/*/.env` file changes via `inotifywait`, auto-runs `consolidate_envs.py --apply` to keep `/opt/fabrik/.env` in sync. Log: `.tmp/env_watcher.log`

**Daily pipeline (runs once per WSL boot day, non-blocking, chained):**
1. `sync_projects.py` — Refresh project registry + BUSINESS_MODEL.md + PORTS.md
2. `sync_cascade_backup.sh` — Check Cascade memory backup freshness (warn if >7d)
3. `health_summary.py` — Scaffold health overview across all projects
4. `kilo_agents_db.py all` — Agent sync + benchmarks + snapshots + export
5. `update_kilo_benchmarks.py --force` — Scrape latest benchmark scores
6. `role_mapper.py` — AI role assignment
7. `generate_kilo_agents.py` — **Generate Traycer CLI agent scripts**
8. `sync_extensions.sh` — Windsurf extensions documentation

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
1. Query `kilo_agents.db` for models assigned to `reviewing` role
2. Select tier based on risk:
   - **High risk** → Prime tier (Claude Opus, etc.)
   - **Medium risk** → Strong tier
   - **Low risk** → Good tier (cost-efficient)
3. Validate model has `has_reasoning=1` (required for code review)
4. Build fallback chain from DB priorities

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

## Final Assignment Table (2026-04-12)

**Source:** `kilo_agents.db` agent_roles table | **Assigned by:** `kilo/google/gemini-3.1-pro-preview`

| Role | Pri | Agent | ELO | TBench | Vision | Thinking | $/M In | $/M Out | PPD |
|------|-----|-------|-----|--------|--------|----------|--------|---------|-----|
| coding | 1 | Anthropic: Claude Opus 4.6 | 1535 | 82.9% | ✅ | ✅ | $5.00 | $25.00 | 77 |
| coding | 2 | OpenAI: GPT-5.4 | 1468 | 81.8% | ✅ | ✅ | $2.50 | $15.00 | 124 |
| coding | 3 | Google: Gemini 3.1 Pro Preview | 1531 | 80.2% | ✅ | ✅ | $2.00 | $12.00 | 161 |
| coding | 4 | OpenAI: GPT-5.3-Codex | — | 78.4% | ✅ | ✅ | $1.75 | $14.00 | — |
| documentation | 1 | OpenAI: gpt-oss-20b | 1371 | 3.4% | — | ✅ | $0.03 | $0.14 | 12187 |
| documentation | 2 | Google: Gemma 3 27B | 1356 | — | ✅ | — | $0.08 | $0.16 | 9686 |
| documentation | 3 | OpenAI: gpt-oss-120b | 1398 | 18.7% | — | ✅ | $0.04 | $0.19 | 9182 |
| documentation | 4 | Qwen: Qwen3 32B | 1376 | — | — | ✅ | $0.08 | $0.24 | 6880 |
| documentation | 5 | Xiaomi: MiMo-V2-Flash | 1411 | — | — | ✅ | $0.09 | $0.29 | 5879 |
| fixing | 1 | Anthropic: Claude Opus 4.6 | 1535 | 82.9% | ✅ | ✅ | $5.00 | $25.00 | 77 |
| fixing | 2 | Google: Gemini 3.1 Pro Preview | 1531 | 80.2% | ✅ | ✅ | $2.00 | $12.00 | 161 |
| fixing | 3 | OpenAI: GPT-5.4 | 1468 | 81.8% | ✅ | ✅ | $2.50 | $15.00 | 124 |
| fixing | 4 | OpenAI: GPT-5.3-Codex | — | 78.4% | ✅ | ✅ | $1.75 | $14.00 | — |
| reviewing | 1 | Anthropic: Claude Opus 4.6 | 1535 | 82.9% | ✅ | ✅ | $5.00 | $25.00 | 77 |
| reviewing | 2 | Google: Gemini 3.1 Pro Preview | 1531 | 80.2% | ✅ | ✅ | $2.00 | $12.00 | 161 |
| reviewing | 3 | Google: Gemini 3 Pro Preview | 1501 | 69.4% | ✅ | ✅ | $2.00 | $12.00 | 158 |
| reviewing | 4 | Anthropic: Claude Sonnet 4.6 | 1500 | — | ✅ | ✅ | $3.00 | $15.00 | 125 |
| reviewing | 5 | Anthropic: Claude Opus 4.5 | 1496 | 63.1% | ✅ | ✅ | $5.00 | $25.00 | 75 |
| testing | 1 | Anthropic: Claude Opus 4.6 | 1535 | 82.9% | ✅ | ✅ | $5.00 | $25.00 | 77 |
| testing | 2 | OpenAI: GPT-5.4 | 1468 | 81.8% | ✅ | ✅ | $2.50 | $15.00 | 124 |
| testing | 3 | Google: Gemini 3 Flash Preview | 1470 | 64.3% | ✅ | ✅ | $0.50 | $3.00 | 619 |
| testing | 4 | Z.ai: GLM 5 | 1461 | 52.4% | — | ✅ | $0.72 | $2.30 | 767 |
| testing | 5 | MiniMax: MiniMax M2.5 | 1436 | 42.7% | — | ✅ | $0.12 | $0.99 | 1860 |

---

## Query Current Assignments

```bash
sqlite3 -header -column kilo_agents.db \
  "SELECT r.role, r.priority, a.name, a.arena_elo
   FROM agent_roles r JOIN agents a ON a.id = r.agent_id
   ORDER BY r.role, r.priority"
```
