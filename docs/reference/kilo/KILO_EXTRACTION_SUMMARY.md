
# KILO AI COMPREHENSIVE EXTRACTION SUMMARY
**Date:** 2026-02-28
**Status:** COMPLETE

## Extraction Results

### Models Extracted
- **Total Models:** 319
- **Total Providers:** 57
- **Models with Verified Pricing:** 16 (from Kilo cache)
- **Models with Estimated Pricing:** 15 (from market research)
- **Models without Pricing:** 288 (requires provider documentation)

### Variants Discovered
Kilo supports `--variant` flag for reasoning effort control:
- **minimal** - Fastest, cheapest, least reasoning
- **low** - Light reasoning
- **medium** - Balanced (default)
- **high** - Enhanced reasoning
- **max** - Maximum reasoning, highest cost

### Categories
- Coding Specialists: 20 models
- Vision/Multimodal: 17 models
- Thinking/Reasoning: 20 models
- Fast (Flash): 14 models
- Budget (Mini): 41 models
- Premium (Pro): 17 models
- Claude Opus: 4 models
- Claude Sonnet: 6 models
- Claude Haiku: 3 models

## Files Created

### Data Files
1. `/opt/fabrik/scripts/kilo_all_models.json` - Complete 319 model catalog
2. `/opt/fabrik/scripts/kilo_comprehensive_db.json` - Models with variants, pricing, specialties
3. `/opt/fabrik/scripts/kilo_all_models_table.csv` - All 319 models in CSV format
4. `/opt/fabrik/scripts/kilo_verified_models_table.csv` - 16 verified models in CSV format
5. `/opt/fabrik/scripts/kilo_streamlined_stack.json` - 8 verified agents for implementation

### Documentation
1. `/opt/fabrik/docs/reference/kilo-ai-documentation.md` - Complete Kilo AI documentation
2. `/opt/fabrik/scripts/validation_issues.json` - Validation report from external review

### Pricing Data
1. `/opt/fabrik/scripts/.model_update_cache.json` - Official Kilo cache (16 models)
2. `/opt/fabrik/scripts/kilo_pricing_comprehensive.json` - Extended pricing database (31 models)

## Verified Pricing (16 Models)

| Model | Provider | Cost |
|-------|----------|------|
| minimax-m2.5 | minimax | $0.12/10M |
| gemini-3-flash-preview | google | $0.20/10M |
| glm-4.7 | zhipu-ai | $0.25/10M |
| kimi-k2.5 | moonshotai | $0.25/10M |
| claude-haiku-4-5 | anthropic | $0.40/10M |
| gpt-5.1 | openai | $0.50/10M |
| gpt-5.1-codex | openai | $0.50/10M |
| gpt-5.1-codex-max | openai | $0.50/10M |
| gpt-5.2 | openai | $0.70/10M |
| gpt-5.2-codex | openai | $0.70/10M |
| gpt-5.3-codex | openai | $0.70/10M |
| gemini-3-pro-preview | google | $0.80/10M |
| claude-sonnet-4-5 | anthropic | $1.20/10M |
| claude-opus-4-5 | anthropic | $2.00/10M |
| claude-opus-4-6 | anthropic | $2.00/10M |
| claude-opus-4-6-fast | anthropic | $12.00/10M |

## Kilo Documentation Structure

### CLI Commands
- `kilo models` - List all models
- `kilo models --verbose` - Show costs and details
- `kilo agent` - Manage agents
- `kilo run --model <model> --variant <variant>` - Run with specific model/variant
- `kilo stats` - Show usage statistics
- `kilo web` - Web interface
- `kilo mcp` - Model Context Protocol servers

### File Locations
- Agents: `~/.traycer/cli-agents/`
- Sessions: `~/.traycer/sessions/`
- Cache: `/opt/fabrik/scripts/.model_update_cache.json`
- Comprehensive DB: `/opt/fabrik/scripts/kilo_comprehensive_db.json`

## Next Steps

1. **Verify remaining pricing** - Contact providers for 288 models without pricing
2. **Test variants** - Validate minimal/low/medium/high/max behavior
3. **Create production agents** - Use streamlined stack (8 verified agents)
4. **Document use cases** - Map each model to specific coding/review tasks
5. **Set up monitoring** - Track token usage and costs via `kilo stats`

## Streamlined Stack (Ready for Implementation)

8 verified agents with confirmed pricing:
1. Code Minimax-M2.5 ($0.12/10M) - Ultra budget
2. Code Gemini-3-Flash ($0.20/10M) - Fast budget
3. Code GPT-5.2 ($0.70/10M) - General purpose
4. Code Gemini-3-Pro ($0.80/10M) - Complex logic
5. Review Claude-Opus-4.6 ($2.00/10M) - Premium security
6. Code Kimi-K2.5 ($0.25/10M) - Long context
7. Review Gemini-3-Flash ($0.20/10M) - Fast review
8. Review GPT-5.2 ($0.70/10M) - General review

**Average cost:** $0.62/10M tokens
