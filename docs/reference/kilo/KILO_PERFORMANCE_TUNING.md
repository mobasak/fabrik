# Kilo CLI Performance Tuning

**Last Updated:** 2026-05-20

Optimize Kilo CLI for token cost, speed, context efficiency, and output quality. CLI-focused — covers programmatic usage patterns, not GUI settings.

---

## Context Management

Context is the #1 cost driver. Every token in the context window costs money on every turn.

### Context condensing (compaction)

When conversations grow long, Kilo auto-compacts — summarizes old history and frees context space.

**How it works:**
1. Tracks total token count (input + output + cached)
2. Triggers at `threshold_percent` of model window OR when remaining space hits safety buffer
3. Generates an "anchored summary" (goal, constraints, progress, key decisions, relevant files)
4. Replaces old history with summary. Keeps recent turns verbatim.
5. If session was already compacted, updates the existing summary (incremental, no info loss)

**Between compactions:** a lighter pruning pass replaces completed tool outputs outside a 40K-token window with `[Old tool result content cleared]`.

### Configuration

```jsonc
// opencode.json or kilo.jsonc
{
  "compaction": {
    "auto": true,                    // Enable auto-compaction (default: true)
    "threshold_percent": 80,         // Trigger at 80% of model context window
    "prune": true,                   // Clear old tool outputs beyond 40K window
    "tail_turns": 2,                 // Keep 2 recent user turns verbatim
    "preserve_recent_tokens": 8000,  // Token budget for recent turns
    "reserved": 20000                // Safety buffer kept free
  }
}
```

**Use a cheap model for compaction** (saves cost — compaction model doesn't need to be smart):

```jsonc
{
  "agent": {
    "compaction": {
      "model": "anthropic/claude-haiku-4-5"
    }
  }
}
```

### Manual triggers

```bash
# In TUI
/compact      # aliases: /smol, /condense

# In CLI TUI
<leader>c     # keyboard shortcut
```

### Environment overrides

```bash
KILO_DISABLE_AUTOCOMPACT=1    # Force compaction.auto = false
KILO_DISABLE_PRUNE=1          # Force compaction.prune = false
```

### Tuning rules

| Situation | Setting | Why |
|---|---|---|
| Complex multi-file refactor | `threshold_percent: 70` | Compact early — preserve headroom for tool calls |
| Simple Q&A / docs | `threshold_percent: 90` | Compact late — conversations are short |
| Large context model (1M tokens) | `reserved: 40000` | More buffer for long outputs |
| Small context model (128K) | `reserved: 15000` | Less buffer needed |
| Long sessions you don't want to lose | `tail_turns: 4` | Keep more recent turns after compaction |

---

## Token Cost Optimization

### 1. Selective context — the biggest lever

**Don't load entire files.** Reference specific line ranges:

```
# Bad — loads entire file into context
@src/components/UserProfile.tsx

# Good — loads only 22 lines
@src/components/UserProfile.tsx:45-67
```

**Only include files directly relevant to the task.** Every `@file` mention is tokens.

### 2. Prompt caching

Providers (Anthropic, Google) cache repeated prompt prefixes. Cache hits reduce input token cost by ~90%.

**How to maximize cache hits:**
- Keep system prompts stable across turns (don't rewrite them)
- Place large stable context (AGENTS.md, project rules) at the beginning of the prompt
- Avoid changing early-prompt content between turns
- Session continuity (`--continue`) maintains cache automatically

**Fabrik pattern:** `kilo_code_review.py` preserves session_id across escalation for ~30-50% token savings.

### 3. Instruction overhead

Custom instructions (AGENTS.md, skills, rules) are loaded into every turn.

**Minimize overhead:**
- Keep AGENTS.md concise — use `AGENTS-compact.md` for Kilo CLI agents (not the full AGENTS.md)
- Use per-directory instructions (loaded only when agent reads files in that directory)
- Disable MCP servers you're not using — each adds tools to context
- Consolidate instruction files — 1 file with 50 lines beats 5 files with 10 lines each (fewer file-load tokens)

```jsonc
// Global config — only load compact instructions
{
  "instructions": ["AGENTS-compact.md"]
}
```

### 4. Model-tier routing

Don't use expensive models for cheap tasks.

| Task | Use | Don't use | Savings |
|---|---|---|---|
| Docs, changelogs | Free/local (Ollama) | Any cloud model | 100% |
| Simple fixes, linting | Budget ($0.03-0.10/M) | Sonnet/Opus | 90%+ |
| Standard coding | Mid-tier ($0.50-2/M) | Opus | 70% |
| Complex architecture | Premium ($3-15/M) | — | Full cost justified |

**Fabrik automated routing:** `kilo_auto_route.py` classifies tickets and picks the cheapest model that clears quality floors. See [KILO_AGENT_SELECTION_GUIDE.md](KILO_AGENT_SELECTION_GUIDE.md).

### 5. Mode-based cost control

Modes restrict tool access, which reduces token burn from tool calls:

| Mode | Tool access | Cost impact |
|---|---|---|
| `ask` | Read only | Very low — no edit/bash tokens |
| `architect` | Read + markdown edit | Low |
| `code` | Full | High — file ops generate large tool outputs |
| `debug` | Full | High |

**Rule:** Use `ask` mode for Q&A. Switch to `code` only when you need to write files.

### 6. Variant selection

Variants control reasoning effort (thinking tokens). Higher variant = more output tokens = more cost.

| Variant | Reasoning | Cost | Use when |
|---|---|---|---|
| `minimal` | Lowest | Cheapest | Simple formatting, boilerplate |
| `low` | Light | Low | Routine coding |
| `high` | Deep | Medium-high | Complex logic, architecture |
| `max` | Maximum | Highest | Security audit, critical decisions |

```bash
kilo run --variant minimal "Rename userId to user_id in this file"
kilo run --variant max "Review this auth middleware for security issues"
```

---

## Speed Optimization

### 1. Timeout tuning

```bash
# Kilo code review script
export KILO_IDLE_TIMEOUT=120     # Kill if no output for 120s (default)
export KILO_HARD_TIMEOUT=1200    # Absolute max 20min (default)
export KILO_POLL_INTERVAL=2      # Check output every 2s (default)

# Agent scripts
export KILO_TIMEOUT=600          # 10min default for agent scripts
```

**Fabrik uses liveness-based monitoring, not blind timeouts.** The process is killed only if truly idle (no stdout/stderr for `IDLE_TIMEOUT` seconds). Active processes that are producing output are never killed early.

### 2. Batch processing

```bash
# Review files in batches (kilo_code_review.py does this automatically)
# MAX_FILES_PER_BATCH controls batch size

# For autonomous batch jobs, loop with --auto
for f in data/*.csv; do
  kilo run --auto --file "$f" "Extract email addresses and write to output/" 
done
```

### 3. FlashBoot and NVMe (RunPod)

If using `kilo serve` as a backend with GPU providers:
- Enable FlashBoot on RunPod endpoints (+10% cost, -90% cold start)
- Use NVMe-backed volumes for model weights
- See [76-gpu-workers.md](../../.windsurf/rules/76-gpu-workers.md) for GPU optimization

### 4. Local models for zero-latency

For high-frequency, low-complexity tasks, local Ollama models eliminate network round-trip:

```bash
# Configure Ollama provider
# In opencode.json:
{
  "provider": {
    "ollama": {
      "options": {
        "baseURL": "http://localhost:11434/v1"
      }
    }
  }
}
```

**Tradeoffs:** Zero API cost, zero latency. But: no prompt caching, no vision, smaller context windows, quality limited by local VRAM (8GB RTX 5070 → max ~32B parameter model).

See [LOCAL_LLM_INFRASTRUCTURE.md](../LOCAL_LLM_INFRASTRUCTURE.md) for fabrik's local model setup.

---

## Output Quality Optimization

### 1. Skills for repeatable quality

Don't rely on ad-hoc prompts. Encode domain knowledge in skills:

```
~/.kilo/skills/security-review/SKILL.md
```

Skills ensure every agent follows the same standard procedure. See [KILO_USAGE_GUIDE.md](KILO_USAGE_GUIDE.md#skills).

### 2. Pre-review gates

Run deterministic checks before expensive AI review:

```bash
# kilo_code_review.py runs these automatically:
# - Schema validation
# - Evidence validation (issues must cite code)
# - Plan coverage (every spec requirement must be reviewed)
```

Catches structural failures at zero token cost.

### 3. False-negative mitigation

When a cheap model says "all clear" on high-risk code — verify with a stronger model:

| Risk | Trigger | Verify with |
|---|---|---|
| HIGH | PASS with zero findings, tier < Strong | Claude Sonnet 4.6 |
| CRITICAL | PASS with zero findings, tier < Prime | Claude Opus 4.6 |

See [KILO_REVIEW_GUIDE.md](KILO_REVIEW_GUIDE.md) for the full escalation pipeline.

### 4. Issue deduplication

Across multi-pass reviews, fingerprint issues by (file, line, category, severity) to prevent repeated findings. `kilo_code_review.py` does this via `get_issue_fingerprint()`.

### 5. Max output tokens

Every output token competes with conversation history for context space.

| Task type | Max output | Why |
|---|---|---|
| Code implementation | 8K-16K | Preserve conversation history |
| Architecture planning | 32K-64K | Need space for detailed plans |
| Debugging | 32K-64K | Detailed analysis needed |
| Q&A | 16K-32K | Balance explanation vs history |

Configure per-agent:
```jsonc
{
  "agent": {
    "code": {
      "maxOutputTokens": 16384
    },
    "architect": {
      "maxOutputTokens": 65536
    }
  }
}
```

---

## Monitoring

### Token usage and cost

```bash
# Kilo built-in stats
kilo stats

# Fabrik cost report (from usage logs)
python3 scripts/kilo_cost_report.py
python3 scripts/kilo_cost_report.py --by-model --by-filetype --days 7

# Enable per-agent tracking
export KILO_TRACK_COST=1
# Logs to: .droid/kilo_usage.jsonl
```

### Agent health

```bash
# Verify all agent scripts
bash scripts/kilo_agent_health.sh

# Test model connectivity
kilo roll-call openai     # Test all OpenAI models
kilo roll-call anthropic  # Test all Anthropic models
```

### Context progress

In the CLI TUI, the context progress graph shows token usage in real-time. Watch for sessions approaching the limit — compact before you hit it.

---

## Quick Decision Matrix

| Goal | Do this |
|---|---|
| Reduce cost 80%+ | Route docs/simple tasks to free/local models |
| Reduce cost 30-50% | Preserve session_id for prompt cache hits |
| Reduce cost 10-20% | Disable unused MCP servers, use AGENTS-compact.md |
| Speed up responses | Use `minimal`/`low` variant for routine tasks |
| Speed up long sessions | Set `compaction.threshold_percent: 70` |
| Improve review quality | Use `max` variant + pre-review gates |
| Avoid false negatives | Enable verify-high-risk (default on) |
| Scale to 1000+ files | Batch with --auto, use efficiency models |
| Zero-cost development | Use Ollama locally or Kilo Gateway free models |

---

## See Also

- [KILO_REVIEW_GUIDE.md](KILO_REVIEW_GUIDE.md) — Cost-aware review pipeline with escalation
- [KILO_USAGE_GUIDE.md](KILO_USAGE_GUIDE.md) — Skills, MCP, workflows, autonomous mode
- [KILO_MODEL_SELECTION.md](KILO_MODEL_SELECTION.md) — Model selection strategies
- [KILO_AGENT_SELECTION_GUIDE.md](KILO_AGENT_SELECTION_GUIDE.md) — Automated model routing
- [KILO_CLI_REFERENCE.md](KILO_CLI_REFERENCE.md) — Complete command reference
- [KILO_TROUBLESHOOTING.md](KILO_TROUBLESHOOTING.md) — Common issues
