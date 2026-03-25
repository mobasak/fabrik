# Kilo Agent Naming Convention

**Last Updated:** 2026-03-10

---

## Overview

Kilo agent scripts in `~/.traycer/cli-agents/` use a **tier-based naming convention** that encodes:
- Performance tier (Free/Economy/Standard/Pro/Expert/Apex/Specialist)
- Rank within tier
- Model identifier
- Agent role (code/review)
- Reasoning effort variant
- Token pricing (input/output per 1M)

**Key Feature:** Tier names are prefixed with `T1-` through `T7-` so Traycer's alphabetical sorting shows agents in capability order (T1-Free first → T7-Specialist last).

---

## Naming Format

```
<PREFIX><NN>-<model>-<role>-<effort>-i<IN>-o<OUT>.sh
```

### Components

| Component | Description | Values |
|-----------|-------------|--------|
| `<PREFIX>` | Tier with sort prefix | `T1-Free`, `T2-Economy`, `T3-Standard`, `T4-Pro`, `T5-Expert`, `T6-Apex`, `T7-Specialist` |
| `<NN>` | Rank within tier | `00`, `01`, `02`, etc. (0-indexed) |
| `<model>` | Normalized model name | `opus46`, `gpt53codex`, `gemini31pro`, `sonnet46`, etc. |
| `<role>` | Agent purpose | `code`, `review` |
| `<effort>` | Reasoning variant | `auto`, `minimal`, `low`, `medium`, `high`, `max` |
| `<IN>` | Input price per 1M | Encoded (price × 100, no decimals) |
| `<OUT>` | Output price per 1M | Encoded (price × 100, no decimals) |

---

## Pricing Encoding

**Rule:** Value × 100, remove decimal point

| Price | Encoded |
|-------|---------|
| $0.01 | `001` |
| $0.02 | `002` |
| $0.20 | `020` |
| $0.50 | `050` |
| $1.00 | `100` |
| $3.00 | `300` |
| $5.00 | `500` |
| $14.00 | `1400` |
| $168.00 | `16800` |

---

## Tier Classification

### 🆓 Free Tier
**Zero-cost models for prototyping**
- kilo/auto (routing wrapper)
- DeepSeek-R1, Minimax M2.1
- GLM-4.7-Free, Kimi-K2.5
- $0/1M input and output

### 💸 Economy Tier
**Budget-friendly, fast iteration**
- Gemini-2.5-Flash, Minimax M2.5
- GLM-4.7, DeepSeek-v3.2
- GPT-5-nano, GPT-5-mini
- $0.001-0.10/1M input

### ⚖️ Standard Tier
**Daily development workhorses**
- Gemini-3-Flash, Gemini-2.5-Pro
- O3-mini-high, O4-mini
- GPT-5.1-Codex variants
- $0.10-0.50/1M input

### 💪 Pro Tier
**Production-grade coding and review**
- GPT-5.2, GPT-5.3-Codex
- Gemini 3.1 Pro
- Claude Sonnet 4.5/4.6
- $0.50-3.00/1M input

### 🔬 Expert Tier
**Complex analysis and architecture**
- Claude Opus 4.5/4.6
- $3.00-10.00/1M input

### 🔥 Apex Tier
**Mission-critical decisions**
- GPT-5.2-Pro, GPT-5.4-Pro
- O1-Pro, O3-Pro
- $15.00+/1M input

### 🎯 Specialist Tier
**Task-specific Codestral variants**
- codestral-docs, codestral-refactor
- codestral-review, codestral-test
- Optimized for specific tasks

---

## Examples

### Free Tier
```bash
Free00-auto-code-auto-i000-o000.sh       # Kilo auto-router
Free01-deepseekr1-code-max-i000-o000.sh  # DeepSeek-R1 code
Free02-minimax21-code-medium-i000-o000.sh # Minimax M2.1 code
```

### Economy Tier
```bash
Economy00-flash25-code-minimal-i030-o250.sh  # Gemini-2.5-Flash code
Economy09-deepseek32-code-medium-i025-o040.sh # DeepSeek v3.2 code
Economy13-gpt5nano-code-minimal-i005-o040.sh  # GPT-5-nano code
```

### Pro Tier
```bash
Pro05-sonnet45-code-high-i300-o1500.sh   # Sonnet 4.5 code
Pro06-sonnet46-review-max-i300-o1500.sh  # Sonnet 4.6 review
Pro11-sonnet46-code-max-i300-o1500.sh    # Sonnet 4.6 code (max)
Pro12-sonnet46-code-high-i300-o1500.sh   # Sonnet 4.6 code (high)
```

### Expert Tier
```bash
Expert00-opus45-review-max-i500-o2500.sh # Opus 4.5 review
Expert01-opus46-code-max-i500-o2500.sh   # Opus 4.6 code
```

### Apex Tier
```bash
Apex00-gpt52pro-review-max-i2100-o16800.sh # GPT-5.2-Pro review
Apex02-o3pro-review-max-i2000-o8000.sh     # O3-Pro review
```

---

## Benefits

✅ **Sortable** - Scripts sort by tier → rank → model
✅ **Grep-able** - Filter by tier, role, or price range
✅ **Machine-parseable** - Stable format for automation
✅ **Visible pricing** - Know cost before using
✅ **Future-proof** - Handles new models/pricing
✅ **Traycer-ordered** - mtime sequencing ensures correct listing order

---

## Script Generation

**Do NOT rename scripts manually.**

Scripts are auto-generated from the agent registry:
```bash
python /opt/fabrik/scripts/generate_kilo_agents.py
```

This reads `/opt/fabrik/scripts/kilo_47_agents_final.json` and generates all agent scripts with:
- **Alphabetical sorting**: Tier prefixes (T1-T7) ensure correct capability order
- **Duplicate prevention**: Skips unchanged files (updates mtime only)
- **Orphan cleanup**: Removes .sh files not in current agent list

---

## Script Structure

Each agent script:
1. Saves task context to `.droid/review-context/task-${TRAYCER_TASK_ID}.md` (unique per task)
2. Calls `kilo run` with appropriate model/variant/agent
3. Uses `--format json --auto` for Traycer integration
4. Passes `$TRAYCER_PROMPT` from environment

---

## Session Management

Session IDs are maintained by Kilo CLI automatically. No explicit session tracking needed in agent scripts.

---

## See Also

- `/opt/fabrik/scripts/kilo_47_agents_final.json` - Agent definitions (57 agents)
- `/opt/fabrik/scripts/generate_kilo_agents.py` - Script generator
- `/opt/fabrik/docs/reference/kilo/KILO_MODEL_CAPABILITIES.md` - Model capabilities
- `~/.traycer/cli-agents/` - Generated agent scripts
