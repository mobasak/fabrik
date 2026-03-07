# Kilo Agent System - Final Update (March 2026)

**Date:** 2026-03-07
**Total Agents:** 46 (down from 65 duplicates)
**Tier System:** Opus 4.6 Enhanced (Free → Economy → Standard → Pro → Expert → Apex + Specialist)
**Naming:** Simple `{tier}-{N}` format (e.g., `free-1`, `econ-3`, `apex-1`)

---

## What Changed

### Before (Problematic)
- **65 agents** (40 original + 50 new = duplicates)
- **Confusing tiers:** Auto, Balanced, Economy, Free, Massive, Prime, Reasoning, Strong, Ultra
- **Complex naming:** `Prime01-opus46-code-max-i500-o2500.sh`
- **No clear defaults:** Which agent to pick in each tier?

### After (Clean)
- **46 agents** (each model exactly once)
- **Intuitive tiers:** Free → Economy → Standard → Pro → Expert → Apex (clear cost progression)
- **Simple naming:** `free-1.sh`, `econ-3.sh`, `expert-5.sh`
- **Default guidance:** `-1` suffix is the recommended default for each tier

---

## New Tier System

| Tier | Cost Range | Agents | Default | Use For |
|------|------------|--------|---------|---------|
| **Free** | $0 | 10 | `free-1` (deepseek-r1) | Sandbox, rapid iteration, bulk tasks |
| **Economy** | $0.001-0.10 | 9 | `econ-1` (gemini-3-flash) | Quick tasks, docs, tests, small edits |
| **Standard** | $0.10-0.50 | 6 | `std-1` (devstral-small) | Daily development, feature implementation |
| **Pro** | $0.50-3.00 | 6 | `pro-1` (glm-5) | Production code, code review, refactoring |
| **Expert** | $3.00-10.00 | 7 | `expert-1` (sonnet-4.5) | Architecture, security, deep analysis |
| **Apex** | $20-40 | 3 | `apex-1` (gpt-5.2-pro) | Epic planning, critical decisions |
| **Specialist** | Varies | 5 | N/A | Task-specific (refactor, docs, test) |

**Total:** 46 agents (no duplicates)

---

## Tier Details

### Free Tier ($0)
**Use for:** Sandbox development, rapid trial-and-error, high-volume automation

| Agent ID | Model | Specialty |
|----------|-------|-----------|
| `free-0` | auto | Meta-router (automatic dispatch) |
| `free-1` | deepseek-r1 | **DEFAULT** - o1-level performance, zero cost |
| `free-2` | minimax-m2.1 | Strong general-purpose |
| `free-3` | glm-4.7-free | Agent-centric |
| `free-4` | kimi-k2.5 | Agentic capabilities |
| `free-5` | kimi-k2 | Advanced tool use |
| `free-6` | qwen3-coder | Agentic coding |
| `free-7` | trinity-large | Strong capabilities preview |
| `free-8` | glm-4.5-air | Lightweight agent |
| `free-9` | giga-potato | Evaluation period |

---

### Economy Tier ($0.001-0.10)
**Use for:** Quick tasks, scaffolding, tests, documentation, simple bug fixes

| Agent ID | Model | Specialty | $/1M in |
|----------|-------|-----------|---------|
| `econ-1` | gemini-3-flash | **DEFAULT** - Fast prototyping | $0.005 |
| `econ-2` | gemini-2.5-flash | 40% better than 3-flash | $0.007 |
| `econ-3` | minimax-m2.5 | Cheapest non-free | $0.003 |
| `econ-4` | glm-4.7 | Multilingual | $0.006 |
| `econ-5` | gpt-5.2 | General coding | $0.018 |
| `econ-6` | gpt-5.2-codex | Code generation | $0.018 |
| `econ-7` | gpt-5.3-codex | General coding | $0.018 |
| `econ-8` | seed-2.0-mini | Efficient reasoning | $0.03 |
| `econ-9` | glm-4.7-flash | Fast multilingual | $0.07 |

---

### Standard Tier ($0.10-0.50)
**Use for:** Daily development, routine features, isolated component development

| Agent ID | Model | Specialty | $/1M in |
|----------|-------|-----------|---------|
| `std-1` | devstral-small | **DEFAULT** - 85% premium at 10% cost | $0.20 |
| `std-2` | grok-4.1-fast | Fast inference | $0.20 |
| `std-3` | codestral | Specialized code | $0.25 |
| `std-4` | grok-4-fast | Fast inference (newer) | $0.25 |
| `std-5` | deepseek-v3.2 | Code analysis | $0.27 |
| `std-6` | llama-4-maverick | Complex reasoning | $0.30 |

---

### Pro Tier ($0.50-3.00)
**Use for:** Production code generation, codebase-wide refactoring, PR reviews

| Agent ID | Model | Specialty | $/1M in |
|----------|-------|-----------|---------|
| `pro-1` | glm-5 | **DEFAULT** - Advanced reasoning | $1.00 |
| `pro-2` | qwen3-235b | Near-premium accuracy | $1.20 |
| `pro-3` | gpt-5.2-chat | Code review | $1.75 |
| `pro-4` | gemini-3.1-pro | Multi-modal | $2.00 |
| `pro-5` | qwen3.5-397b | Massive context (397B params) | $2.00 |
| `pro-6` | gemini-2.5-pro | Next-gen flagship | $2.50 |

---

### Expert Tier ($3.00-10.00)
**Use for:** Code review, security analysis, architecture validation, BLOCKER detection

| Agent ID | Model | Specialty | $/1M in |
|----------|-------|-----------|---------|
| `expert-1` | claude-sonnet-4.5 | **DEFAULT** - Fast coding | $3.00 |
| `expert-2` | claude-sonnet-4.6 | Balanced review | $3.00 |
| `expert-3` | claude-3.7-sonnet | Latest Sonnet | $3.00 |
| `expert-4` | claude-3.7-sonnet:thinking | Extended thinking | $3.50 |
| `expert-5` | claude-opus-4.5 | Deep reasoning | $5.00 |
| `expert-6` | claude-opus-4.6 | Complex refactoring | $5.00 |
| `expert-7` | o3-mini-high | Fast chain-of-thought | $10.00 |

---

### Apex Tier ($20-40)
**Use for:** Epic planning, multi-phase technical design, critical architecture decisions

| Agent ID | Model | Specialty | $/1M in |
|----------|-------|-----------|---------|
| `apex-1` | gpt-5.2-pro | **DEFAULT** - Deep analysis | $21.00 |
| `apex-2` | o1-pro | Flagship reasoning | $35.00 |
| `apex-3` | o3-pro | Maximum reasoning depth | $40.00 |

**Cost:** Expect $1-5+ per invocation. Reserve for truly critical tasks.

---

### Specialist Tier (Task-Specific)
**Use for:** Single-purpose CI/CD tasks with locked system prompts

| Agent ID | Model | Purpose | $/1M in |
|----------|-------|---------|---------|
| `spec-refactor` | codestral | Refactoring only | $0.25 |
| `spec-docs` | codestral | Documentation only | $0.25 |
| `spec-test` | codestral | Test generation only | $0.25 |
| `spec-translate` | codestral | Language translation only | $0.25 |
| `spec-review` | codestral | Code review only | $0.25 |

---

## Naming Convention

**Format:** `{tier}-{N}.sh` where N is cost-ordered (cheapest first)

**Rules:**
- `-0` = meta-router (auto dispatch)
- `-1` = **recommended default** for that tier
- `-2, -3, ...` = alternatives, ordered by cost

**Examples:**
- `free-1.sh` → deepseek-r1 (best free model)
- `econ-1.sh` → gemini-3-flash (cheapest Economy, recommended default)
- `std-1.sh` → devstral-small (best quality-to-cost for daily work)
- `expert-1.sh` → claude-sonnet-4.5 (cheapest Expert, recommended default)
- `apex-3.sh` → o3-pro (most expensive, maximum reasoning)

---

## Use Case → Tier Mapping

| Use Case | Recommended Tier | Default Agent | Rationale |
|----------|-----------------|---------------|-----------|
| **Epic Planning** | Apex | `apex-1` (gpt-5.2-pro) | Max reasoning for architecture |
| **Code Review (critical)** | Expert | `expert-2` (sonnet-4.6) | High accuracy for BLOCKERs |
| **Code Review (routine)** | Pro | `pro-6` (gemini-2.5-pro) | Good enough for non-critical |
| **Feature Implementation** | Standard | `std-1` (devstral-small) | Best quality/cost for coding |
| **Bug Fixes** | Standard | `std-1` (devstral-small) | Moderate complexity |
| **Test Generation** | Economy | `econ-1` (gemini-3-flash) | Verifiable, cheap suffices |
| **Documentation** | Economy | `econ-1` (gemini-3-flash) | Low-risk, high-volume |
| **Rapid Prototyping** | Free | `free-1` (deepseek-r1) | Zero cost, iterate freely |
| **Security Audit** | Expert | `expert-6` (opus-4.6) | Deep code understanding |
| **Refactoring** | Specialist | `spec-refactor` | Purpose-built |

---

## How to Use in Traycer

### Option 1: By Agent ID (Recommended)
```
Use free-1 for rapid prototyping
Use std-1 for daily implementation
Use expert-1 for code review
Use apex-1 for Epic architecture validation
```

### Option 2: By Tier (Auto-selects default)
```
Use Free tier for sandbox testing
Use Expert tier for security review
Use Apex tier for critical planning
```

### Option 3: Auto-Select
```
Review this Epic plan for BLOCKER issues
(Traycer will auto-select based on complexity)
```

---

## Migration from Old System

**No action required.** Old agent scripts backed up to `~/.traycer/cli-agents-backup-20260307/`

**New agent locations:**
- Old: `~/.traycer/cli-agents/Prime01-opus46-code-max-i500-o2500.sh`
- New: `~/.traycer/cli-agents/expert-6.sh`

**Finding equivalents:**

| Old Agent | New Agent | Tier Change |
|-----------|-----------|-------------|
| Prime01-opus46 | expert-6 | Prime → Expert |
| Reasoning01-o3pro | apex-3 | Reasoning → Apex |
| Strong03-gemini25pro | pro-6 | Strong → Pro |
| Balanced05-o3minihigh | expert-7 | Balanced → Expert |
| Economy01-flash25 | econ-2 | Economy → Economy |
| Free08-deepseekr1 | free-1 | Free → Free |

---

## Cost Comparison: Old vs New for Epic Planning

| Approach | Agents | Total Cost | Reasoning Quality |
|----------|--------|------------|-------------------|
| **Old (Prime tier)** | opus-4.6 (3 calls) | ~$13 | Good |
| **Old (Reasoning tier)** | o3-pro (3 calls) | ~$80 | Excellent |
| **New (Apex tier)** | apex-1 (3 calls) | ~$42 | Very Good |
| **New (Hybrid)** | apex-1 (1) + expert-4 (2) | ~$21 | Very Good |

**Recommendation:** Hybrid approach - `apex-1` for initial architecture review, `expert-4` (sonnet:thinking) for verification.

---

## Regenerating Agents

```bash
# Already done - agents generated at ~/.traycer/cli-agents/

# To verify health:
bash /opt/fabrik/scripts/kilo_agent_health.sh

# To regenerate from scratch:
python /opt/fabrik/scripts/generate_kilo_agents.py
```

**Source files:**
- Agent definitions: `/opt/fabrik/scripts/kilo_47_agents_final.json`
- Generator: `/opt/fabrik/scripts/generate_kilo_agents.py`
- Output: `~/.traycer/cli-agents/*.sh` (46 files)

---

## What Changed Under the Hood

### generate_kilo_agents.py
- **AGENTS_FILE:** `kilo_47_agents_final.json` (was `kilo_50_agents_new.json`)
- **TIER_ORDER:** `["Free", "Economy", "Standard", "Pro", "Expert", "Apex", "Specialist"]`
- **Naming:** Uses `agent_id` directly from JSON (e.g., `free-1`, `econ-3`)
- **No normalization:** Agent ID is canonical, no complex filename encoding

### kilo_47_agents_final.json
- **46 unique agents** (down from 50, removed duplicates)
- **agent_id field:** New canonical identifier (e.g., `"agent_id": "free-1"`)
- **Tier assignments:** Based on cost brackets, not arbitrary groupings

---

## Design Decisions (From 3-Model Consultation)

**Consulted models:**
- GPT-5.3 Codex Thinking
- Gemini 3.1 Pro
- **Claude Opus 4.6** (SELECTED)

**Why Opus 4.6 approach won:**
1. Clear cost progression (Free → Economy → Standard → Pro → Expert → Apex)
2. `-1` suffix as default removes decision fatigue
3. Natural English tier names (no "T0-T6" or arbitrary letters)
4. Task-aligned use cases, not model-centric groupings
5. Prevents duplicates via agent_id as unique key

---

## Known Limitations

1. **Apex tier cost:** $21-40/1M makes it expensive for frequent use
2. **O-series models:** May have slower response times due to extended thinking
3. **Limited Specialist agents:** Only Codestral variants currently

---

## Next Steps

1. ✅ Agents generated and verified (46 healthy)
2. ⏭️ Test Apex tier with real Epic planning
3. ⏭️ Monitor cost vs quality for Expert vs Apex
4. ⏭️ Add more Specialist agents if needed (security, translation, etc.)

---

## Support

**Health check:** `bash /opt/fabrik/scripts/kilo_agent_health.sh`
**Documentation:** `docs/traycer/TRAYCER-KILO-AGENTS-GUIDE.md`
**Generator:** `scripts/generate_kilo_agents.py`
**Backup:** `~/.traycer/cli-agents-backup-20260307/` (old 65 agents)
