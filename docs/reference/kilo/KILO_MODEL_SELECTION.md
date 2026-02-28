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

Auto Model routes to different models based on the Kilo mode you're using:

| Mode | Model Used | Tool Access | Best For |
|------|-----------|-------------|----------|
| **architect** | Claude Opus 4.6 | Read, browser, mcp, edit (markdown only) | System design, planning, architecture |
| **orchestrator** | Claude Opus 4.6 | Limited (task creation, coordination) | Multi-step task coordination, delegation |
| **ask** | Claude Opus 4.6 | Read, browser, mcp only | Questions, explanations, learning |
| **plan** | Claude Opus 4.6 | Varies | Planning, reasoning |
| **general** | Claude Opus 4.6 | Varies | General assistance |
| **review** | Claude Opus 4.6 | Read, browser, mcp, edit (permitted) | Code review, quality analysis |
| **code** | Claude Sonnet 4.5 | Full (read, edit, browser, command, mcp) | Writing and editing code |
| **build** | Claude Sonnet 4.5 | Full | Implementation tasks |
| **debug** | Claude Sonnet 4.5 | Full (read, edit, browser, command, mcp) | Debugging and fixing issues |
| **explore** | Claude Sonnet 4.5 | Varies | Codebase exploration |

**Strategy:**
- **Planning/reasoning tasks** → Claude Opus 4.6 (deep reasoning, architectural decisions)
- **Implementation tasks** → Claude Sonnet 4.5 (fast, accurate code generation)
- **Review/quality tasks** → Claude Opus 4.6 (thorough analysis)

**Cost optimization insight:**
- Opus modes (architect, ask, review, orchestrator) typically have **lower token usage** due to limited tool access
- Sonnet modes (code, debug) have **higher token usage** due to full file operations
- Auto Model balances quality and cost automatically based on mode

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

## Free and Budget Models - Cost Optimization

**Why this matters:** AI model costs can add up quickly during development. Use Kilo Code effectively while minimizing or eliminating costs through free models, budget-friendly alternatives, and smart usage strategies.

### Completely Free Options

#### Kilo Gateway Free Models

Kilo works with AI inference providers to offer free models through the Kilo Gateway:

| Model | Provider | Best For |
|-------|----------|----------|
| **MiniMax M2.1 (free)** | MiniMax | Strong general-purpose performance |
| **Z.AI: GLM 4.7 (free)** | Z.AI | Agent-centric applications |
| **MoonshotAI: Kimi K2.5 (free)** | MoonshotAI | Agentic capabilities, tool use, reasoning, code synthesis |
| **Giga Potato (free)** | Stealth | Evaluation period free model |
| **Arcee AI: Trinity Large Preview (free)** | Arcee AI | Strong capabilities (preview) |

**Setup:** No additional setup required - available directly through Kilo Gateway.

#### OpenRouter Free Tier Models

OpenRouter offers several models with generous free tiers.

**Setup:**
1. Create free OpenRouter account
2. Get API key from dashboard
3. Configure Kilo Code with OpenRouter provider

**Available free models:**

| Model | Best For |
|-------|----------|
| **Qwen3 Coder (free)** | Agentic coding: function calling, tool use, long-context reasoning |
| **Z.AI: GLM 4.5 Air (free)** | Lightweight agent-centric applications |
| **DeepSeek: R1 0528 (free)** | Performance on par with OpenAI o1, open reasoning tokens |
| **MoonshotAI: Kimi K2 (free)** | Advanced tool use, reasoning, code synthesis |

---

### Cost-Effective Premium Models

When you need more capability than free models provide:

#### Ultra-Budget Champions (Under $0.50/M tokens)

| Model | Cost | Best For | Performance |
|-------|------|----------|-------------|
| **Mistral Devstral Small** | ~$0.20/M input | Code generation, debugging, refactoring | 85% of premium at 10% cost |
| **Llama 4 Maverick** | ~$0.30/M input | Complex reasoning, architecture planning | Excellent for most dev tasks |
| **DeepSeek v3** | ~$0.27/M input | Code analysis, large codebase understanding | Strong technical reasoning |

#### Mid-Range Value Models ($0.50-$2.00/M tokens)

| Model | Cost | Best For | Performance |
|-------|------|----------|-------------|
| **Qwen3 235B** | ~$1.20/M input | Complex projects requiring high accuracy | Near-premium at 40% cost |

---

### Smart Usage Strategies

#### The 50% Rule

**Principle:** Use budget models for 50% of tasks, premium models for the other 50%.

**Budget model tasks:**
- Code reviews and analysis
- Documentation writing
- Simple bug fixes
- Boilerplate generation
- Refactoring existing code

**Premium model tasks:**
- Complex architecture decisions
- Debugging difficult issues
- Performance optimization
- New feature design
- Critical production code

#### Context Management for Cost Savings

**Minimize context size:**
```
// Instead of mentioning entire files
@src/components/UserProfile.tsx

// Mention specific functions or sections
@src/components/UserProfile.tsx:45-67
```

**Reuse context effectively:**
- Keep key project notes in repository (`AGENTS.md`, `docs/` folder)
- Reduces need to re-explain project details
- Saves tokens per conversation

**Strategic file mentions:**
- Only include files directly relevant to task
- Use `@folder/` for broad context, specific files for targeted work

#### Model Switching Strategies

**Start cheap, escalate when needed:**
1. Begin with free models (Qwen3 Coder, GLM-4.5-Air)
2. Switch to budget models if free models struggle
3. Escalate to premium models only for complex tasks

**Use API Configuration Profiles:**
- Set up multiple profiles for different cost tiers
- Quick switching between free, budget, and premium models
- Match model capability to task complexity

#### Mode-Based Cost Optimization

**Use appropriate modes to limit expensive operations:**

| Mode | Purpose | Tool Access | Cost Impact | Recommended Model Tier |
|------|---------|-------------|-------------|----------------------|
| **Ask** | Information gathering, learning | Read-only | **Very Low** | Free/Budget (no edits) |
| **Architect** | Planning, design | Markdown edits only | **Low** | Budget for simple, Premium for complex design |
| **Review** | Code quality analysis | Read + limited edit | **Medium** | Premium (quality critical) |
| **Orchestrator** | Task delegation | Task creation only | **Medium** | Budget for coordination |
| **Code** | Implementation | Full file operations | **High** | Budget → Premium escalation |
| **Debug** | Troubleshooting | Full file operations | **High** | Premium for complex, Budget for simple |

**Mode selection for cost savings:**

```
Daily workflow:
1. Morning planning → Architect mode + DeepSeek R1 (FREE)
2. Learning/exploration → Ask mode + Qwen3 Coder (FREE)
3. Simple implementation → Code mode + Mistral Devstral Small ($0.20/M)
4. Complex features → Code mode + Claude Sonnet 4.5 (premium)
5. Pre-commit review → Review mode + Claude Opus 4.6 (premium)
6. Quick bug fixes → Debug mode + Budget model
7. Complex debugging → Debug mode + Premium model
```

**Custom modes for budget control:**
- Create modes that restrict expensive tools
- Limit file access to specific directories
- Control which operations are auto-approved
- Define cost-tier preferences per mode

---

### Real-World Performance Comparisons

#### Code Generation Tasks

**Simple function creation:**
- Mistral Devstral Small: 95% success rate (FREE)
- Budget models: 95-98% success rate ($0.20-0.50/M)
- Premium models: 98% success rate ($30/M)

**Verdict:** Budget models are excellent for simple code generation.

**Complex refactoring:**
- Budget models: 70-80% success rate
- Premium models: 90-95% success rate

**Recommendation:** Start with budget, escalate if needed.

#### Debugging Performance

**Simple bugs:**
- Free models: Usually sufficient
- Budget models: Excellent performance
- Premium models: Overkill for most cases

**Complex system issues:**
- Free models: 40-60% success rate
- Budget models: 60-80% success rate
- Premium models: 85-95% success rate

---

### Hybrid Approach Recommendations

#### Daily Development Workflow

**Morning planning session:**
- Use Architect mode with DeepSeek R1 (free)
- Plan features and architecture
- Create task breakdowns

**Implementation phase:**
- Use Code mode with budget models
- Generate and modify code
- Handle routine development tasks

**Complex problem solving:**
- Switch to premium models when stuck
- Use for critical debugging
- Architecture decisions affecting multiple systems

#### Project Phase Strategy

**Early development:**
- Free and budget models for prototyping
- Rapid iteration without cost concerns
- Establish patterns and structure

**Production preparation:**
- Premium models for critical code review
- Performance optimization
- Security considerations

---

### Cost Monitoring and Control

#### Track Your Usage

**Monitor credit consumption:**
- Check cost estimates in chat history
- Review monthly usage patterns
- Identify high-cost operations

**Set spending limits:**
- Use provider billing alerts
- Configure provider rate limits
- Set daily/monthly budgets

#### Cost-Saving Tips

**Reduce system prompt size:**
- Disable MCP if not using external tools
- Use focused custom modes
- Minimize unnecessary context

**Optimize conversation length:**
- Use Checkpoints to reset context
- Start fresh conversations for unrelated tasks
- Archive completed work

**Batch similar tasks:**
- Group related code changes
- Handle multiple files in single requests
- Reduce conversation overhead

---

### Getting Started with Budget Models

#### Quick Setup Guide

1. **Create OpenRouter account** for free models
2. **Configure multiple providers** in Kilo Code
3. **Set up API Configuration Profiles** for easy switching
4. **Escalate to budget models** when needed
5. **Reserve premium models** for complex work

#### Recommended Provider Mix

**Free tier foundation:**
- OpenRouter - Free models
- Groq - Fast inference for supported models
- Z.ai - Free GLM-4.5-Flash

**Budget tier options:**
- DeepSeek - Excellent value models
- Mistral - Specialized coding models

**Premium tier backup:**
- Anthropic - Claude for complex reasoning
- OpenAI - GPT-4 for critical tasks

---

### Measuring Success

**Track these metrics:**
- Monthly AI costs vs. development productivity
- Task completion rates by model tier
- Time saved vs. money spent
- Code quality improvements

**Success indicators:**
- 70%+ of tasks completed with free/budget models
- Monthly costs under target budget
- Maintained or improved code quality
- Faster development cycles

**Rule of thumb:** Start with free options, gradually incorporate budget models as needs and comfort with costs grow.

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
