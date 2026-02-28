# Kilo Agent Update Schedule & Automation

**Last Updated:** 2026-02-28

## Automated Update Schedule

### Daily Updates (Cron)
```bash
# /etc/cron.d/kilo-agent-updater
0 2 * * * ozgur python /opt/fabrik/scripts/kilo_agent_updater.py --sync >> /var/log/kilo-updates.log 2>&1
```

**What gets updated:**
- Model pricing from Kilo cache
- Provider base URLs
- Context window sizes
- Max output token limits
- Model availability status

### Weekly Validation
```bash
# Every Monday at 3 AM
0 3 * * 1 ozgur python /opt/fabrik/scripts/kilo_agent_updater.py --validate >> /var/log/kilo-validation.log 2>&1
```

**Checks:**
- All agents still valid in Kilo catalog
- No deprecated models
- Provider endpoint changes

## Arena & TBench Integration

### Current Status: **Manual**

The Chatbot Arena and Terminal-Bench leaderboards are currently **manually reviewed** and integrated into agent selection.

### Planned Automation (Phase 2)

**Script:** `/opt/fabrik/scripts/kilo_leaderboard_sync.py` (to be created)

**Features:**
- Scrape Arena rankings weekly
- Scrape TBench scores weekly
- Auto-generate recommendations for agent updates
- Notify if top-ranked models are missing from stack
- Track ranking changes over time

**Cron schedule:**
```bash
# Every Sunday at 4 AM
0 4 * * 0 ozgur python /opt/fabrik/scripts/kilo_leaderboard_sync.py --check-rankings
```

**Output:**
- `/opt/fabrik/scripts/.arena_rankings.json` - Latest Arena data
- `/opt/fabrik/scripts/.tbench_scores.json` - Latest TBench data
- Notification if stack needs updating

### Implementation Roadmap

**Phase 1 (Current):**
- ✅ Manual agent selection from leaderboards
- ✅ Automated config updates (pricing, endpoints)
- ✅ Daily sync via cron

**Phase 2 (Planned - Q2 2026):**
- ⏳ Auto-scrape Arena rankings
- ⏳ Auto-scrape TBench scores
- ⏳ Recommendation engine for stack updates
- ⏳ Slack/email notifications for ranking changes

**Phase 3 (Future):**
- ⏳ Auto-create agents for new top-ranked models
- ⏳ A/B testing framework for agent performance
- ⏳ Cost/performance optimization engine

## Manual Review Triggers

**When to manually review agents:**
1. New model announced by major provider (OpenAI, Anthropic, Google)
2. Arena rankings show new model in top 10
3. TBench leaderboard changes significantly (>5% accuracy shift)
4. Kilo adds new provider with competitive pricing
5. Security vulnerability in existing model

## Pricing Collection for Priority Models

**Priority Model List (17 models):**
- GPT-5.3, GPT-5.2 (all variants)
- Gemini-3.1, Gemini-3-Flash
- Claude Sonnet 4.5/4.6, Opus 4.5/4.6
- Minimax M2.5, Grok-4.20
- GLM-4.7, GLM-5, Seed2.0 Pro

**Pricing Status:**
- ✅ 7 models: Have cached pricing from Kilo
- ⏳ 10 models: Need manual collection from provider websites

### Manual Pricing Collection (10 models)

**Why Manual?** Kilo's aggressive prompt caching makes API-based extraction unreliable for separate input/output pricing. Cached tokens from previous calls create negative input values that break regression models.

**Guide:** `/opt/fabrik/scripts/MANUAL_PRICING_GUIDE.md`

**Provider Pricing URLs:**
- Anthropic: https://www.anthropic.com/pricing (4 models)
- Google: https://ai.google.dev/pricing (2 models)
- OpenAI: https://openai.com/api/pricing/ (2 models)
- Z-AI/GLM: https://bigmodel.cn/pricing (2 models)

**Models Needing Pricing:**
```
Anthropic: claude-opus-4.5, claude-opus-4.6, claude-sonnet-4.5, claude-sonnet-4.6
Google: gemini-3.1-pro-preview, gemini-3.1-pro-preview-customtools
OpenAI: gpt-5.2-chat, gpt-5.2-pro
Z-AI: glm-4.7-flash, glm-5
```

**Collection Process:**
1. Visit provider pricing page
2. Find model (may have date suffix like `-20250929`)
3. Record input/output prices per 1M tokens in USD
4. Update cache: `python /opt/fabrik/scripts/update_pricing_cache.py --manual`

**Update Frequency:**
- Review quarterly or when providers announce pricing changes
- Check for new models monthly

## Update Procedure

**Automated (runs daily):**
```bash
python /opt/fabrik/scripts/kilo_agent_updater.py --sync
```

**Manual (after leaderboard review):**
```bash
# 1. Review latest rankings
open https://openlm.ai/chatbot-arena/
open https://www.tbench.ai/leaderboard/terminal-bench/2.0

# 2. Update agent stack JSON
vim /opt/fabrik/scripts/kilo_final_validated_stack.json

# 3. Validate changes
python /opt/fabrik/scripts/kilo_agent_updater.py --validate

# 4. Apply updates
python /opt/fabrik/scripts/kilo_agent_updater.py --sync

# 5. Test new agents
kilo run --model <new-model> --variant high "test prompt"
```

## Monitoring

**Logs:**
- `/var/log/kilo-updates.log` - Daily sync log
- `/var/log/kilo-validation.log` - Weekly validation log

**Alerts:**
- Validation failures trigger email to `admin@example.com`
- New top-10 Arena models trigger Slack notification

## Cost Tracking

**Built-in tracking:**
```bash
kilo stats  # Show token usage and costs
```

**Monthly reports:**
```bash
python /opt/fabrik/scripts/kilo_cost_report.py --month $(date +%Y-%m)
```

## Security Updates

**CVE monitoring:** Manual (check provider security bulletins)
**Model deprecations:** Auto-detected by validator
**API key rotation:** Quarterly (manual)
