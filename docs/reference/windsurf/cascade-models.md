# Cascade Models and Credits

**Last Updated:** 2026-01-05

> 📋 **Source:** `scripts/droid_models.py` contains the authoritative model list.
>
> Run `python scripts/droid_models.py windsurf` to see all models.

---

## Model Selection

In Cascade, switch models via the dropdown under the text input box. Each model consumes different prompt credits.

**Total Models:** 63 across 5 tiers

---

## Free Tier (11 models)

| Model | Credits |
|-------|---------|
| Penguin Alpha | Free |
| **SWE-1** | Free |
| **SWE-1.5** | Free |
| GPT-5.1-Codex | Free |
| GPT-5.1-Codex Low | Free |
| GPT-5.1-Codex Max Low | Free |
| GPT-5.1-Codex Mini | Free |
| GPT-5.1-Codex Mini Low | Free |
| DeepSeek R1 (0528) | Free |
| DeepSeek V3 (0324) | Free |
| Grok Code Fast 1 | Free |

---

## Budget Tier (14 models, 0.125x - 0.5x)

| Model | Credits |
|-------|---------|
| xAI Grok-3 mini (Thinking) | 0.125x |
| Gemini 3 Flash Low | 0.25x |
| Gemini 3 Flash Minimal | 0.25x |
| GPT-OSS 120B (Medium) | 0.25x |
| Gemini 3 Flash Medium | 0.375x |
| SWE-1.5 Fast | 0.5x |
| GPT-5 (Low Reasoning) | 0.5x |
| GPT-5.1 (No Reasoning) | 0.5x |
| GPT-5.1 (Low Reasoning) | 0.5x |
| GPT-5.1-Codex Max Medium | 0.5x |
| Kimi K2 | 0.5x |
| Minimax M2 | 0.5x |
| Qwen3-Coder | 0.5x |
| Gemini 3 Flash High | 0.5x |

---

## Standard Tier (13 models, 1x)

| Model | Credits |
|-------|---------|
| Claude Haiku 4.5 | 1x |
| Gemini 2.5 Pro | 1x |
| Gemini 3 Pro Low | 1x |
| GPT-4.1 | 1x |
| GPT-4o | 1x |
| GPT-5 (Medium Reasoning) | 1x |
| GPT-5.1 (Medium Reasoning) | 1x |
| GPT-5.1 (No Reasoning, Priority) | 1x |
| GPT-5.1 (Low, Priority) | 1x |
| GPT-5.2 No Reasoning | 1x |
| GPT-5.2 Low Reasoning | 1x |
| o3 | 1x |
| o3 (High Reasoning) | 1x |

---

## Premium Tier (15 models, 2x - 3x)

| Model | Credits |
|-------|---------|
| Claude 3.5 Sonnet | 2x |
| Claude 3.7 Sonnet | 2x |
| Claude Sonnet 4 | 2x |
| Claude Sonnet 4.5 | 2x |
| Gemini 3 Pro High | 2x |
| GPT-5 (High Reasoning) | 2x |
| GPT-5.1 (High Reasoning) | 2x |
| GPT-5.1 (Medium, Priority) | 2x |
| GPT-5.2 No Reasoning Fast | 2x |
| GPT-5.2 Low Reasoning Fast | 2x |
| GPT-5.2 Medium Reasoning | 2x |
| Claude 3.7 Sonnet (Thinking) | 3x |
| Claude Sonnet 4 (Thinking) | 3x |
| Claude Sonnet 4.5 (Thinking) | 3x |
| GPT-5.2 High Reasoning | 3x |

---

## Ultra Tier (10 models, 4x - 20x)

| Model | Credits |
|-------|---------|
| Claude Opus 4.5 | 4x |
| GPT-5.1 (High, Priority) | 4x |
| GPT-5.2 Medium Reasoning Fast | 4x |
| Claude Opus 4.5 (Thinking) | 5x |
| GPT-5.2 High Reasoning Fast | 6x |
| GPT-5.2 X-High Reasoning | 8x |
| Claude Sonnet 4.5 (1M) | 10x |
| GPT-5.2 X-High Reasoning Fast | 16x |
| Claude Opus 4.1 | 20x |
| Claude Opus 4.1 (Thinking) | 20x |

---

## SWE Models (Windsurf In-House)

| Model | Description |
|-------|-------------|
| **SWE-1.5** | Best agentic coding model. Near Claude 4.5-level at 13x speed |
| SWE-1.5 Fast | Faster variant (0.5x credits) |
| SWE-1 | First agentic model. Claude 3.5-level at lower cost |
| SWE-1-mini | Powers Tab suggestions, real-time latency |
| swe-grep | Powers context retrieval and Fast Context |

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

| Task | Recommended Model | Credits |
|------|-------------------|---------|
| **Quick edits** | SWE-1.5 | Free |
| **Fast iteration** | GPT-5.1-Codex | Free |
| **Bulk exploration** | Gemini 3 Flash Low | 0.25x |
| **Complex refactoring** | Claude Sonnet 4.5 | 2x |
| **Architecture planning** | Claude Opus 4.5 (Thinking) | 5x |
| **Code review** | SWE-1.5 or Claude Sonnet | Free/2x |

---

## Credit Optimization Tips

1. **Start with Free tier** - SWE-1.5, DeepSeek, GPT-5.1-Codex
2. **Use Budget for bulk work** - Gemini Flash variants (0.25x)
3. **Standard for quality** - Claude Haiku, o3
4. **Premium sparingly** - Sonnet for complex tasks
5. **Ultra rarely** - Opus only for critical decisions

---

## CLI Commands

```bash
# List all Windsurf models
python scripts/droid_models.py windsurf

# Filter by tier
python scripts/droid_models.py windsurf free     # 11 models
python scripts/droid_models.py windsurf budget   # 14 models
python scripts/droid_models.py windsurf standard # 13 models
python scripts/droid_models.py windsurf premium  # 15 models
python scripts/droid_models.py windsurf ultra    # 10 models
```

---

## See Also

- [Factory.ai Models](../droid-exec-usage.md) - droid exec model selection
- [Recommended Extensions](recommended-extensions.md)
