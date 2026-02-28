# Kilo Agent Naming Convention

**Last Updated:** 2026-02-28

---

## Overview

Kilo agent scripts in `~/.traycer/cli-agents/` use a **tier-based naming convention** that encodes:
- Performance tier (Prime/Strong/Balanced/Economy)
- Rank within tier
- Model identifier
- Agent role (code/review)
- Reasoning effort variant
- Token pricing (input/output per 1M)

---

## Naming Format

```
<TIER><NN>-<model>-<role>-<effort>-i<IN>-o<OUT>.sh
```

### Components

| Component | Description | Values |
|-----------|-------------|--------|
| `<TIER>` | Performance tier | `P` (Prime), `S` (Strong), `B` (Balanced), `E` (Economy) |
| `<NN>` | Rank within tier | `01`, `02`, `03`, etc. |
| `<model>` | Normalized model name | `opus46`, `gpt53codex`, `gemini31pro`, etc. |
| `<role>` | Agent purpose | `code`, `review` |
| `<effort>` | Reasoning variant | `minimal`, `low`, `medium`, `high`, `max` |
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

### 🔥 Prime Tier (P)
**Premium models for mission-critical work**
- Claude Opus 4.5/4.6
- GPT-5.2-Pro
- High cost, maximum reasoning

### 💪 Strong Tier (S)
**Production-grade coding and review**
- GPT-5.3-Codex, GPT-5.2
- Gemini 3.1 Pro
- Claude Sonnet 4.5/4.6
- Balanced cost/performance

### ⚖ Balanced Tier (B)
**Good performance, reasonable cost**
- GPT-5.2-Codex
- Gemini 3.1 CustomTools
- GLM-5, Grok-4.1-Fast
- Mid-tier pricing

### 💸 Economy Tier (E)
**Budget-friendly, fast iteration**
- Gemini-3-Flash
- Minimax M2.5
- GLM-4.7-Flash
- Seed-2.0-Mini
- Minimal cost

---

## Examples

### Prime Tier
```bash
P01-opus46-review-max-i500-o2500.sh      # Claude Opus 4.6 review
P02-gpt52pro-review-max-i2100-o16800.sh  # GPT-5.2-Pro review
P03-opus45-review-max-i500-o2500.sh      # Claude Opus 4.5 review
```

### Strong Tier
```bash
S01-gpt53codex-code-high-i002-o005.sh    # GPT-5.3-Codex code
S02-gpt52-code-high-i002-o005.sh         # GPT-5.2 code
S03-gemini31pro-code-high-i200-o1200.sh  # Gemini 3.1 Pro code
S04-sonnet46-review-max-i300-o1500.sh    # Sonnet 4.6 review
S05-sonnet45-review-max-i300-o1500.sh    # Sonnet 4.5 review
```

### Balanced Tier
```bash
B01-gpt52codex-code-high-i002-o005.sh    # GPT-5.2-Codex code
B02-gemini31tools-code-high-i200-o1200.sh # Gemini 3.1 CustomTools
B03-glm5-review-high-i100-o320.sh        # GLM-5 review
B04-grok41fast-code-high-i020-o050.sh    # Grok-4.1-Fast code
```

### Economy Tier
```bash
E01-flash3-code-minimal-i001-o001.sh     # Gemini-3-Flash code
E02-m25-code-low-i000-o001.sh            # Minimax M2.5 code
E03-glm47flash-code-minimal-i007-o040.sh # GLM-4.7-Flash code
E04-seed20mini-review-max-i003-o031.sh   # Seed-2.0-Mini review
```

---

## Benefits

✅ **Sortable** - Scripts sort by tier → rank → model
✅ **Grep-able** - Filter by tier, role, or price range
✅ **Machine-parseable** - Stable format for automation
✅ **Visible pricing** - Know cost before using
✅ **Future-proof** - Handles new models/pricing

---

## Script Generation

**Do NOT rename scripts manually.**

Scripts are auto-generated from the pricing registry:
```bash
python /opt/fabrik/scripts/generate_kilo_agents.py
```

This reads `/opt/fabrik/scripts/kilo_18_agents_complete.json` and generates all agent scripts with consistent naming.

---

## Script Structure

Each agent script:
1. Saves task context to `.droid/review-context/task.md`
2. Calls `kilo run` with appropriate model/variant/agent
3. Uses `--format json --auto` for Traycer integration
4. Passes `$TRAYCER_PROMPT` from environment

---

## Session Management

Session IDs are maintained by Kilo CLI automatically. No explicit session tracking needed in agent scripts.

---

## See Also

- `/opt/fabrik/scripts/kilo_18_agents_complete.json` - Agent definitions
- `/opt/fabrik/docs/reference/KILO_UPDATE_SCHEDULE.md` - Update process
- `~/.traycer/cli-agents/save-plan-md.sh` - Plan saving utility
