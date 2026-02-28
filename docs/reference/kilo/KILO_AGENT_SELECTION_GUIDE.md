# Kilo Agent Selection Guide - Complete Catalog

**Generated:** 2026-02-28
**Total Models:** 319
**Providers:** 57

## Complete Model Catalog

**File:** `/opt/fabrik/scripts/KILO_COMPLETE_AGENT_CATALOG.json`

This JSON file contains ALL 319 Kilo models with:
- Model ID and provider
- Specialties (coding, reasoning, vision, fast, budget, premium)
- Recommended use cases
- Pricing (verified or TBD)
- Recommended variants (high, max, etc.)
- Suitability for code vs review agents

## Top Providers by Model Count

| Provider | Models | With Pricing | Available |
|----------|--------|--------------|-----------|
| openai | 62 | 16 | All GPT-5.x, GPT-4.x, O1, O3 |
| google | 46 | 2 | Gemini 2.x, 3.x, 4.x |
| anthropic | 13 | 5 | Claude Opus, Sonnet, Haiku 3.x-4.x |
| meta-llama | 19 | 0 | Llama 3.x, 4.x |
| qwen | 17 | 0 | Qwen 2.x, 3.x, QwQ |
| mistralai | 16 | 0 | Mistral, Codestral, Pixtral |
| deepseek | 14 | 0 | DeepSeek V2, V3, R1 |
| z-ai (GLM) | 10 | 1 | GLM-4.x, GLM-5 |
| x-ai (Grok) | 8 | 0 | Grok 3, 4, 4.1 |
| moonshotai (Kimi) | 6 | 1 | Kimi K2, K2.5 |
| minimax | 7 | 1 | MiniMax M1, M2, M2.5 |
| nvidia | 6 | 0 | Nemotron models |
| cohere | 6 | 0 | Command series |
| bytedance-seed | 5 | 0 | Seed 1.x, 2.x |
| ... and 43 more providers | 84 | 0 | Various |

## Models by Capability

### Coding Specialists (76 models)
- OpenAI: gpt-5.x-codex, gpt-4.x-codex
- Qwen: qwen-coder, qwen3.5-coder
- DeepSeek: deepseek-coder-v2
- Mistral: codestral-2508
- ... and 60+ more

### Reasoning/Thinking (48 models)
- OpenAI: o1, o3, gpt-5.x with thinking
- DeepSeek: deepseek-r1, deepseek-reasoner
- Anthropic: claude-x-thinking variants
- Kimi: kimi-k2-thinking
- ... and 40+ more

### Vision/Multimodal (32 models)
- Google: gemini-x.xv (vision variants)
- Anthropic: claude-x.xv
- OpenAI: gpt-4v variants
- ... and 25+ more

### Fast/Flash (45 models)
- Google: gemini-flash, gemini-turbo
- Groq: various fast variants
- ... and 40+ more

### Budget/Mini (68 models)
- Google: gemini-flash, gemini-nano
- OpenAI: gpt-4o-mini variants
- Meta: llama-3.x-8b variants
- ... and 60+ more

## Pricing Coverage

- **Total models:** 319
- **With verified pricing:** 16 (5%)
- **Pricing TBD:** 303 (95%)

**Verified pricing models:**
1. minimax-m2.5 ($0.12/10M)
2. gemini-3-flash-preview ($0.20/10M)
3. glm-4.7 ($0.25/10M)
4. kimi-k2.5 ($0.25/10M)
5. claude-haiku-4-5 ($0.40/10M)
6. gpt-5.1, gpt-5.1-codex ($0.50/10M)
7. gpt-5.2, gpt-5.2-codex, gpt-5.3-codex ($0.70/10M)
8. gemini-3-pro-preview ($0.80/10M)
9. claude-sonnet-4-5 ($1.20/10M)
10. claude-opus-4-5, claude-opus-4-6 ($2.00/10M)
11. claude-opus-4-6-fast ($12.00/10M)

## Provider Highlights

### Chinese AI Providers
- **z-ai (GLM):** 10 models, GLM-4.x to GLM-5
- **moonshotai (Kimi):** 6 models, long context specialists (200K+)
- **deepseek:** 14 models, reasoning specialists (R1)
- **qwen:** 17 models, coding specialists
- **baidu:** 5 models, ERNIE series
- **tencent:** 2 models, Hunyuan series
- **bytedance-seed:** 5 models, Seed 2.0

### Western AI Providers
- **openai:** 62 models, GPT/O-series dominance
- **anthropic:** 13 models, Claude quality
- **google:** 46 models, Gemini variety
- **meta-llama:** 19 models, open source
- **mistralai:** 16 models, European AI
- **cohere:** 6 models, enterprise focus
- **x-ai (Grok):** 8 models, real-time capable

### Specialty Providers
- **nvidia:** 6 models, GPU-optimized (Nemotron)
- **perplexity:** 4 models, search-enhanced (Sonar)
- **amazon:** 7 models, AWS-native (Nova)
- **01-ai:** 3 models, Yi series
- **swe-agent:** 0 models (NOT in Kilo catalog)

## How to Use This Catalog

1. **Browse by provider:** See `/opt/fabrik/scripts/kilo_all_319_models_analyzed.json`
2. **Browse by capability:** See categories in same file
3. **Full agent data:** See `/opt/fabrik/scripts/KILO_COMPLETE_AGENT_CATALOG.json`
4. **Select agents:** Pick models based on:
   - Provider preference
   - Pricing (if available)
   - Specialty (coding/reasoning/vision/etc.)
   - Use case (code gen/review/debug/etc.)

## Next Steps

The catalog is ready. You can now:
1. Select specific models from the 319 available
2. Request agents for specific providers (GLM, Kimi, Grok, etc.)
3. Filter by pricing, capability, or specialty
4. Create custom agent combinations

All data is in the JSON files for programmatic access.
