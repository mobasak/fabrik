# Cascade Models and Credits

**Last Updated:** 2026-01-05

> ⚠️ **Manual Updates Required**
>
> Windsurf updates models frequently. This document may become outdated.
> Check [Windsurf Docs](https://docs.windsurf.com) for the latest model list.

---

## Model Selection

In Cascade, switch models via the dropdown under the text input box. Each model consumes different prompt credits.

---

## Available Models

### SWE Models (Windsurf In-House)

| Model | Credits | Description |
|-------|---------|-------------|
| **SWE-1.5** | 0.5 | Best agentic coding model. Near Claude 4.5-level performance at 13x speed |
| SWE-1 | - | First agentic model. Claude 3.5-level performance at lower cost |
| SWE-1-mini | - | Powers Tab suggestions, optimized for real-time latency |
| swe-grep | - | Powers context retrieval and Fast Context |

### Claude Models (Anthropic)

| Model | Credits | Notes |
|-------|---------|-------|
| Claude Haiku 4.5 | 1 | Fast, available on all tiers including Trial |
| Claude Sonnet 4.5 | 2 | Balanced performance/cost |
| Claude Sonnet 4.5 (Thinking) | 3 | Extended reasoning |
| Claude Opus 4.5 | 4 | Highest quality |
| Claude Opus 4.5 (Thinking) | 5 | Extended reasoning, premium |

### Gemini Models (Google)

| Model | Credits | Reasoning Level |
|-------|---------|-----------------|
| Gemini 3.0 Pro (minimal) | 1 | Minimal reasoning |
| Gemini 3.0 Pro (low) | 1 | Low reasoning |
| Gemini 3.0 Pro (medium) | 1.5 | Medium reasoning |
| Gemini 3.0 Pro (high) | 2 | High reasoning |

### GPT Models (OpenAI)

| Model | Credits | Reasoning Level |
|-------|---------|-----------------|
| GPT-5.2 (No Reasoning) | 1 | No extended reasoning |
| GPT-5.2 (Low Reasoning) | 1 | Low reasoning |
| GPT-5.2 (Medium Reasoning) | 1.5 | Medium reasoning |
| GPT-5.2 (High Reasoning) | 2 | High reasoning |

---

## Tier Availability

| Tier | SWE-1.5 | Claude Sonnet | Claude Opus | Haiku | Gemini | GPT |
|------|---------|---------------|-------------|-------|--------|-----|
| **Free** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Pro** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Teams** | ✅ | ✅ (3 credits) | ✅ (6 credits) | ✅ | ✅ | ✅ |
| **Enterprise** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Trial** | - | - | - | ✅ | ✅ | ✅ |

---

## Bring Your Own Key (BYOK)

**Available to:** Free and paid individual users only (not Teams/Enterprise)

Supported BYOK models:
- Claude 4 Sonnet
- Claude 4 Sonnet (Thinking)
- Claude 4 Opus
- Claude 4 Opus (Thinking)

**Setup:** Settings → Subscription → Add API Key

---

## Fabrik Recommendations

For Fabrik workflow, recommended models by task:

| Task | Recommended Model | Why |
|------|-------------------|-----|
| **Quick edits** | SWE-1.5 (0.5 credits) | Fast, cheap, good for routine work |
| **Complex refactoring** | Claude Sonnet 4.5 | Good balance of quality/cost |
| **Architecture planning** | Claude Opus 4.5 (Thinking) | Deep reasoning needed |
| **Exploration/research** | Gemini 3.0 Pro (low) | Cheap exploration |
| **Code review** | SWE-1.5 or Claude Sonnet | Context-aware analysis |

---

## Credit Optimization Tips

1. **Start with SWE-1.5** (0.5 credits) for most tasks
2. **Escalate to Sonnet** when SWE-1.5 struggles
3. **Use Opus sparingly** for complex architectural decisions
4. **Gemini low/minimal** for bulk exploration
5. **Thinking models** only when extended reasoning helps

---

## See Also

- [Factory.ai Models](../droid-exec-usage.md) - droid exec model selection
- [Recommended Extensions](recommended-extensions.md)
