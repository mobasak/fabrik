# Cascade Models and Credits

**Last Updated:** 2026-02-23

> 📋 **Source:** `scripts/droid_models.py` contains the authoritative model list.
>
> Run `python scripts/droid_models.py windsurf` to see all models.

---

## Model Selection

In Cascade, switch models via the dropdown under the text input box. Each model consumes different prompt credits.

**Total Models:** 97 across tiers + BYOK

---

## Free Tier (7 models)

| Model | Credits |
|-------|---------|
| GPT-5.1-Codex | Free |
| GPT-5.1-Codex Low | Free |
| GPT-5.1-Codex Max Low | Free |
| GPT-5.1-Codex-Mini | Free |
| GPT-5.1-Codex-Mini Low | Free |
| Grok Code Fast 1 | Free |
| SWE-1.5 🎁 | Free |

---

## Budget Tier (11 models, 0.125x - 0.75x)

| Model | Credits |
|-------|---------|
| xAI Grok-3 mini Thinking | 0.125x |
| GLM 4.7 (Beta) | 0.25x |
| GPT-OSS 120B Medium Thinking | 0.25x |
| GPT-5 Low Thinking | 0.5x |
| GPT-5-Codex | 0.5x |
| GPT-5.1 | 0.5x |
| GPT-5.1 Low Thinking | 0.5x |
| GPT-5.1-Codex Max Medium | 0.5x |
| Kimi K2 | 0.5x |
| Minimax M2.1 (Beta) | 0.5x |
| SWE-1.5 Fast 🎁 | 0.5x |
| Gemini 3 Flash Minimal (New) | 0.75x |

---

## Standard Tier (21 models, 1x)

| Model | Credits |
|-------|---------|
| Claude Haiku 4.5 | 1x |
| Gemini 2.5 Pro | 1x |
| Gemini 3 Flash Low (New) | 1x |
| Gemini 3 Flash Medium (New) | 1x |
| Gemini 3 Pro Low Thinking | 1x |
| Gemini 3.1 Pro Low Thinking (New 🎁) | 1x |
| GPT-4.1 | 1x |
| GPT-4o | 1x |
| GPT-5 Medium Thinking | 1x |
| GPT-5.1 Fast | 1x |
| GPT-5.1 Medium Thinking | 1x |
| GPT-5.2 Low Thinking | 1x |
| GPT-5.2-Codex Low | 1x |
| GPT-5.2-Codex Medium | 1x |
| GPT-5.3-Codex Low (New) | 1x |
| Kimi K2.5 (New) | 1x |
| Minimax M2.5 (New) | 1x |
| o3 | 1x |
| o3 High Reasoning | 1x |
| xAI Grok-3 | 1x |

---

## Budget-Standard Tier (1 model, 1.5x)

| Model | Credits |
|-------|---------|
| GLM-5 (New) | 1.5x |

---

## Standard-Premium Tier (1 model, 1.75x)

| Model | Credits |
|-------|---------|
| Gemini 3 Flash High (New) | 1.75x |

---

## Premium Tier (18 models, 2x - 3x)

| Model | Credits |
|-------|---------|
| Claude 3.5 Sonnet | 2x |
| Claude 3.7 Sonnet | 2x |
| Claude Sonnet 4 | 2x |
| Claude Sonnet 4.5 🎁 | 2x |
| GPT-5 High Thinking | 2x |
| GPT-5.1 High Thinking | 2x |
| GPT-5.2 Fast | 2x |
| GPT-5.2 Medium Thinking | 2x |
| GPT-5.2-Codex High | 2x |
| GPT-5.3-Codex High (New) | 2x |
| Gemini 3 Pro High Thinking | 2x |
| GPT-5.3-Codex High (New) | 2.5x |
| Claude 3.7 Sonnet (Thinking) | 3x |
| Claude Sonnet 4 Thinking | 3x |
| Claude Sonnet 4.5 Thinking 🎁 | 3x |
| GPT-5.2 High Thinking | 3x |
| GPT-5.2-Codex XHigh | 3x |

---

## Ultra Tier (19 models, 4x - 30x)

| Model | Credits |
|-------|---------|
| Claude Opus 4.5 | 4x |
| Claude Sonnet 4.6 (New) | 4x |
| GPT-5.1 High Thinking Fast | 4x |
| GPT-5.2 Medium Thinking Fast | 4x |
| GPT-5.2-Codex High Fast | 4x |
| GPT-5.3-Codex High Fast (New) | 5x |
| Claude Opus 4.6 | 6x |
| GPT-5.2 High Thinking Fast | 6x |
| GPT-5.2-Codex XHigh Fast | 6x |
| Claude Sonnet 4.6 Thinking (New) | 6x |
| Claude Opus 4.6 Thinking | 8x |
| GPT-5.2 XHigh Thinking | 8x |
| GPT-5.3-Codex XHigh Fast (New) | 8x |
| Claude Opus 4.6 1M | 10x |
| Claude Sonnet 4.5 1M | 10x |
| GPT-5.2 XHigh Thinking Fast | 16x |
| Claude Sonnet 4.6 Thinking 1M | 16x |
| Claude Opus 4.6 Fast (New) | 24x |
| Claude Opus 4.6 Thinking Fast (New) | 30x |

---

## BYOK Models (Bring Your Own Key)

| Model | Status |
|-------|--------|
| Claude Opus 4 BYOK (Beta) | BYOK |
| Claude Opus 4 Thinking BYOK (Beta) | BYOK |
| Claude Sonnet 4 BYOK | BYOK |
| Claude Sonnet 4 Thinking BYOK | BYOK |

**Available to:** Free and paid individual users only (not Teams/Enterprise)
**Setup:** Settings → Subscription → Add API Key

---

## SWE Models (Windsurf In-House)

| Model | Description |
|-------|-------------|
| **SWE-1.5 🎁** | Best agentic coding model. Near Claude 4.5-level at 13x speed |
| SWE-1.5 Fast 🎁 | Faster variant (0.5x credits) |

---

## CLI Commands

```bash
# List all Windsurf models
python scripts/droid_models.py windsurf

# Filter by tier
python scripts/droid_models.py windsurf free     # 7 models
python scripts/droid_models.py windsurf budget   # 11 models
python scripts/droid_models.py windsurf standard # 21 models
python scripts/droid_models.py windsurf premium  # 18 models
python scripts/droid_models.py windsurf ultra    # 19 models
```

---

## See Also

- [Factory.ai Models](../droid-exec-usage.md) - droid exec model selection
- [Recommended Extensions](recommended-extensions.md)
