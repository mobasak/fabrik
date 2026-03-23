# Kilo Agent Management

> Automated agent discovery, benchmarking, role assignment, and runtime selection.

This document covers tools for managing AI agents in `scripts/kilo-benchmarks/`.

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

### Key Tables

**`agents`** — All available agents with benchmarks
```sql
id, api_id, name, provider, arena_elo, tbench_accuracy,
has_vision, has_tools, is_agentic, perf_per_dollar,
status, blocked, block_reason
```

**`agent_roles`** — Role assignments (5 per role)
```sql
role, agent_id, priority (1-5), min_elo, assigned_by
```

**`agent_roles_history`** — Archived assignments

### Key Views

**`v_role_assignments`** — Current assignments with agent details (excludes blocked)

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

## Final Assignment Table (2026-03-23)

**Source:** `kilo_agents.db` role_assignments table

### Reviewing Role

| Pri | Model | Provider | Elo | Tier | Status |
|-----|-------|----------|-----|------|--------|
| 1 | Claude Opus 4.6 | anthropic | 1535 | Prime | ✅ Tested |
| 2 | Gemini 3.1 Pro Preview | google | 1531 | Strong | ✅ Tested |
| 3 | GPT-5.4 | openai | 1468 | Balanced | ✅ Tested |
| 4 | Grok 4 | x-ai | 1453 | Economy | ✅ Tested |
| 5 | Qwen3 VL 235B Thinking | qwen | 1432 | Economy | ✅ Tested |

### Coding Role

| Pri | Model | Provider | TBench | Tier | Status |
|-----|-------|----------|--------|------|--------|
| 1 | GPT-5.4 | openai | 81.8% | Prime | ✅ Tested |
| 2 | Claude Sonnet 4.5 | anthropic | 40.1% | Strong | ✅ Tested |
| 3 | Gemini 3.1 Flash Lite | google | ~ | Balanced | ✅ Tested |
| 4 | MiniMax M2.5 | minimax | 42.2% | Economy | ✅ Tested |
| 5 | DeepSeek V3.2 Exp | deepseek | 39.6% | Economy | ✅ Tested |

### Fixing Role

| Pri | Model | Provider | Elo | Tier | Status |
|-----|-------|----------|-----|------|--------|
| 1 | Claude Sonnet 4.5 | anthropic | 1464 | Prime | ✅ Tested |
| 2 | GPT-5.4 | openai | 1468 | Strong | ✅ Tested |
| 3 | Gemini 3.1 Flash | google | 1470 | Balanced | ✅ Tested |
| 4 | GLM 4.7 | z-ai | 1460 | Economy | ✅ Tested |
| 5 | Kimi K2 Thinking | moonshotai | 1450 | Economy | ✅ Tested |

### Documentation Role

| Pri | Model | Provider | $/Perf | Tier | Status |
|-----|-------|----------|--------|------|--------|
| 1 | Qwen3 235B Instruct | qwen | 15709 | Economy | ✅ Tested |
| 2 | GPT-OSS-20B | openai | 15233 | Economy | ✅ Tested |
| 3 | MiMo V2 Flash | xiaomi | 5879 | Economy | ✅ Tested (borderline) |
| 4 | Claude Haiku 3.5 | anthropic | 359 | Balanced | Active |
| 5 | Grok 4 Fast | x-ai | 3391 | Economy | ✅ Tested |

---

## Query Current Assignments

```bash
sqlite3 -header -column kilo_agents.db \
  "SELECT r.role, r.priority, a.name, a.arena_elo
   FROM agent_roles r JOIN agents a ON a.id = r.agent_id
   ORDER BY r.role, r.priority"
```
