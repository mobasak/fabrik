# Kilo Model Selection Guide

**Last Updated:** 2026-02-28

This guide covers practical model selection strategies for Kilo Code, focusing on real-time data and performance leaderboards rather than static recommendations.

---

## Auto Model (kilo/auto) - Smart Routing

**The easiest way to use Kilo:** Let the system automatically select the optimal AI model based on your current task mode.

### How It Works

1. Select `kilo/auto` as your model in the model dropdown
2. Start working in any mode (Code, Architect, Debug, etc.)
3. The system automatically routes your requests to the best model for that task

**No configuration needed.**

### Mode-to-Model Mapping

Auto Model routes to different models based on task type:

| Mode | Model Used | Best For |
|------|-----------|----------|
| **architect** | Claude Opus 4.6 | System design, planning |
| **orchestrator** | Claude Opus 4.6 | Multi-step task coordination |
| **ask** | Claude Opus 4.6 | Questions, explanations |
| **plan** | Claude Opus 4.6 | Planning, reasoning |
| **general** | Claude Opus 4.6 | General assistance |
| **code** | Claude Sonnet 4.5 | Writing and editing code |
| **build** | Claude Sonnet 4.5 | Implementation tasks |
| **debug** | Claude Sonnet 4.5 | Debugging and fixing issues |
| **explore** | Claude Sonnet 4.5 | Codebase exploration |

**Strategy:**
- **Planning/reasoning tasks** → Claude Opus 4.6 (deep reasoning, architectural decisions)
- **Implementation tasks** → Claude Sonnet 4.5 (fast, accurate code generation)

### Benefits

**✅ Simplified Setup**
- No manual model switching when changing modes
- Transparent background routing

**✅ Cost Optimization**
- Uses economical Sonnet for implementation (speed matters)
- Reserves Opus for planning (benefits from deeper reasoning)
- Optimal cost-to-capability ratio automatically

**✅ Best-in-Class Models**
- Always routes to Claude's latest and most capable models
- Claude Opus for reasoning-intensive tasks
- Claude Sonnet for implementation-focused tasks

### Requirements

⚠️ **Version Requirements:**
- VS Code/JetBrains extension v5.2.3+
- CLI v1.0.15+

On older versions, `kilo/auto` defaults to Claude Sonnet for all requests.

### Getting Started

**Quick Setup:**
1. Open Kilo Code in VS Code or JetBrains
2. Click the model selector dropdown
3. Choose `kilo/auto`
4. Start chatting - the right model is selected automatically

### When to Use Auto Model

Auto Model is ideal for:
- **Developers who frequently switch between planning and coding** - No need to remember which model works best
- **Teams wanting consistent model selection** - Everyone gets optimal routing without individual configuration
- **Cost-conscious developers** - Automatically balances cost and capability
- **New Kilo Code users** - Great defaults without needing to understand model differences

### When to Use a Specific Model

You may want to select a specific model instead when:
- Cost is not a factor for a particular task
- You need a particular model's unique capabilities (e.g., very long context windows)
- You're working with a specialized provider or local model
- You want full control over model selection

---

## The Philosophy: Live Data Over Static Lists

**The honest truth:** By the time model recommendations are written down, they're probably already outdated. New models drop every few weeks, existing ones get updated, prices shift, and yesterday's champion becomes today's budget option.

Instead of maintaining a static list that's perpetually behind, use **real-time leaderboards** showing which models are actually succeeding right now.

---

## Live Model Selection Resources

### Primary Leaderboards to Watch

| Leaderboard | Focus | URL |
|-------------|-------|-----|
| **Kilo Usage Data** | Real usage from Kilo Code users | [kilo.ai/leaderboard](https://kilo.ai/leaderboard) |
| **Chatbot Arena** | User preference rankings across tasks | [openlm.ai/chatbot-arena](https://openlm.ai/chatbot-arena/) |
| **Terminal-Bench** | Terminal/CLI coding performance | [tbench.ai/leaderboard/terminal-bench/2.0](https://www.tbench.ai/leaderboard/terminal-bench/2.0) |

### Why Live Data Matters

- **Kilo Leaderboard** - Not lab benchmarks, but real usage data from developers like you, updated continuously
- **See what's working today** - Which models people are choosing for different tasks
- **Track shifting landscape** - How the model space is evolving in real-time
- **Performance + Cost** - Balance of capability, speed, and pricing

👉 **Check current rankings at [kilo.ai/models](https://kilo.ai/models)**

---

## General Guidance (Evergreen Principles)

While specific model rankings change constantly, these principles stay consistent:

### For Complex Coding Tasks

**Best for:** Nuanced requirements, large refactors, architectural decisions

**Typical models:**
- Claude Sonnet 4.5/4.6, Claude Opus 4.5/4.6
- GPT-5.2, GPT-5.3
- Gemini 3.1 Pro

**Characteristics:**
- Premium pricing
- Deep reasoning capabilities
- Handle multi-step logic
- Understand large codebases

### For Everyday Coding

**Best for:** Most development tasks, incremental features, bug fixes

**Typical models:**
- Mid-tier models with good balance
- Fast enough to maintain flow state
- Capable enough for standard tasks

**Characteristics:**
- Balanced speed/cost/quality
- 32K-128K context windows
- Good for iterative development
- Cost-effective for high volume

### For Budget-Conscious Work

**Best for:** Rapid iteration, experimentation, learning

**Newer efficient models keep surprising with price-to-performance:**
- DeepSeek (R1, Coder variants)
- Qwen (Coder series)
- GLM-4/5
- Minimax

**Characteristics:**
- Low cost per token
- Can handle more than expected
- Good for high-volume tasks
- Suitable for non-critical work

### For Local/Private Work

**Best for:** Privacy-sensitive code, zero API costs, offline development

**Tools:**
- Ollama
- LM Studio

**Tradeoffs:**
- Privacy + Zero API costs
- vs. Speed + Capability
- Local compute requirements
- Model size constraints

---

## Context Windows Matter

Context window size directly impacts your workflow effectiveness:

| Use Case | Recommended Context | Rationale |
|----------|---------------------|-----------|
| **Small projects** | 32-64K tokens | Scripts, single components, isolated modules |
| **Standard applications** | 128K tokens | Multi-file context, typical app structure |
| **Large codebases** | 256K+ tokens | Cross-system understanding, full context |
| **Massive systems** | 1M+ tokens | Available but effectiveness degrades at extremes |

**Note:** Check [provider documentation](KILO_AGENT_SELECTION_GUIDE.md) for specific context limits on each model.

---

## Max Tokens Settings (Thinking Models)

⚠️ **Critical consideration for thinking models:**

Every token you allocate to output takes away from space available to store conversation history.

### Recommendations

| Mode | Max Tokens | Rationale |
|------|------------|-----------|
| **Architect** | High (32K-64K) | Needs space for detailed planning |
| **Debug** | High (32K-64K) | Detailed analysis and explanation |
| **Code** | Low (8K-16K) | Preserve conversation history |
| **Ask** | Medium (16K-32K) | Balance explanation vs history |

### Recovery from Context Limit Errors

If you hit "input length and max tokens exceed context limit" error:

1. **Delete a message** - Remove earlier messages from conversation
2. **Roll back to checkpoint** - Use `/timeline` to fork from earlier point
3. **Switch to long-context model** - e.g., Gemini 3.x/4.x for that message
4. **Compact session** - Use `/compact` to summarize history

---

## Fabrik-Specific Recommendations

### For Traycer Phased YOLO Workflow

Fabrik's 9-step workflow (Traycer → Code → Final Gate → Kilo Review → Deploy) has specific model requirements:

#### Step 2 - Coder Implementation
- **Primary:** Gemini 3.1 Pro High Thinking (1x cost)
- **Escalation:** Claude Sonnet 4.5 Thinking (3x cost) if stuck
- **Why:** Balance speed, cost, and quality for coding

#### Step 4 - Kilo Review
- **Primary:** Claude Opus 4.6 (max reasoning, 128K output)
- **Fallback:** Gemini 3.1 Pro or Sonnet 4.6
- **Why:** Best reasoning for security, spec compliance, edge cases

### For Code Review (kilo_code_review.py)

Default model selection logic in `scripts/kilo_code_review.py`:

```python
# Can be overridden via KILO_REVIEW_MODEL env var
DEFAULT_REVIEW_MODEL = "kilo/anthropic/claude-opus-4.6"
```

**Why Claude Opus 4.6:**
- Best reasoning for code review
- 128K max output (handles large reviews)
- Excellent at spotting security issues
- Strong spec compliance checking

---

## Model Selection by Task Type

### Code Generation
- **Fast iterations:** Grok-4.1-Fast, Gemini-3-Flash
- **Production quality:** GPT-5.3-Codex, Claude Sonnet 4.6
- **Complex logic:** Claude Opus 4.6, GPT-5.2-Pro

### Code Review
- **Security-focused:** Claude Opus 4.6, GPT-5.2-Pro
- **Fast feedback:** Claude Sonnet 4.5, GPT-5.2
- **Budget review:** Gemini 3.1 Pro, GLM-5

### Refactoring
- **Large refactors:** Claude Opus 4.6, GPT-5.2-Pro (need deep understanding)
- **Incremental:** Claude Sonnet 4.5, GPT-5.3-Codex
- **Safe refactors:** Mid-tier models with good reasoning

### Debugging
- **Complex bugs:** Claude Opus 4.6, GPT-5.2-Pro (deep reasoning)
- **Standard bugs:** Claude Sonnet 4.5, Gemini 3.1 Pro
- **Syntax errors:** Budget models sufficient

### Documentation
- **Technical docs:** Claude Sonnet 4.5, GPT-5.2 (clear explanations)
- **API docs:** Mid-tier models
- **Comments:** Budget models sufficient

---

## Cost Optimization Strategies

### Progressive Model Escalation

Start with cheaper models, escalate only when needed:

1. **First attempt:** Budget/mid-tier model (e.g., Gemini 3.1 Pro)
2. **If stuck:** Escalate to strong tier (e.g., Claude Sonnet 4.5)
3. **If still stuck:** Escalate to premium (e.g., Claude Opus 4.6)

### Task-Appropriate Selection

- **Simple tasks:** Don't waste premium model credits
- **Critical tasks:** Don't skimp on model quality
- **Iterative work:** Use fast models to maintain flow
- **Final review:** Use best reasoning models

### Session Continuation

Use `kilo --continue` to maintain context without repeating expensive model calls on the same information.

---

## Staying Current

The AI model space moves fast. Here's how to stay informed:

### Regular Checks
- **Weekly:** Check [kilo.ai/leaderboard](https://kilo.ai/leaderboard) for ranking shifts
- **Monthly:** Review [Chatbot Arena](https://openlm.ai/chatbot-arena/) for new entrants
- **Monthly:** Check [Terminal-Bench](https://www.tbench.ai/leaderboard/terminal-bench/2.0) for CLI coding leaders

### Automated Updates (Fabrik)
```bash
# Daily automated updates via cron
0 2 * * * ozgur python /opt/fabrik/scripts/kilo_agent_updater.py --sync
```

See [KILO_UPDATE_SCHEDULE.md](KILO_UPDATE_SCHEDULE.md) for automation details.

### When to Re-evaluate

Re-evaluate model choices when:
- New major model release (GPT-6, Claude Opus 5, etc.)
- Significant price changes
- Performance issues with current selection
- New use case requiring different characteristics

---

## See Also

- **[KILO_AGENT_SELECTION_GUIDE.md](KILO_AGENT_SELECTION_GUIDE.md)** - Complete 319 model catalog
- **[KILO_CLI_REFERENCE.md](KILO_CLI_REFERENCE.md)** - CLI commands and model selection
- **[KILO_UPDATE_SCHEDULE.md](KILO_UPDATE_SCHEDULE.md)** - Automated update schedule
- **[Kilo Live Models](https://kilo.ai/models)** - Real-time usage data
- **[Chatbot Arena](https://openlm.ai/chatbot-arena/)** - Community rankings
- **[Terminal-Bench](https://www.tbench.ai/leaderboard/terminal-bench/2.0)** - CLI coding leaderboard
