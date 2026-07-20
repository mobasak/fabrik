# Claude Max 20x — effective real-world cost-per-token (Gemini deep research)

Source: Gemini deep research (https://gemini.google.com/app/9e402abeb610b819), run by the operator 2026-07-20.
Provenance: external synthesis of community telemetry + official docs; treat individual figures as
community-measured estimates unless marked official. Kept here as the grounding for the claude -p
subagent cost model ([../../superpowers/specs/2026-07-20-claude-p-first-class-scoring-design.md](../../superpowers/specs/2026-07-20-claude-p-first-class-scoring-design.md)).

## TL;DR — the figures we actually use

**Anthropic API list prices (mid-2026, $/M tokens in / out):**
| Model | Input $/M | Output $/M |
|---|--:|--:|
| Opus 4.8 / 4.7 | 5.00 | 25.00 |
| Sonnet 4.6 | 3.00 | 15.00 |
| Haiku 4.5 | 1.00 | 5.00 |
| Fable 5 | 10.00 | 50.00 |

**Prompt-cache multipliers (× the input price):** cache **read = 0.1×** · cache **write 5-min = 1.25×** ·
cache **write 1-hour = 2.0×**. In Claude Code, ~90% of tokens bill as cache reads.

**Effective subscription rate ($200/mo ÷ real throughput):** Low 860M tok/mo → $0.23/M · Typical 2.15B →
**$0.093/M** · High 3.87B → $0.052/M · Max-saturated 4.30B → $0.046/M. So the subscription runs **10–30×
cheaper than the optimized (cache-aware) API rate** ($0.92/M Sonnet, $1.53/M Opus optimized).

**Limits (why cost isn't the binding constraint — QUOTA is):** Max 20x = 20× Pro *per 5-hour window* but only
**~1.5–2× Pro weekly**. Maxing one 5-hour window can burn ~25% of the weekly allowance; sustained use exhausts
the 7-day quota in **36–48h**. Two overlapping caps: rolling **5-hour** window + a **weekly** active-compute-hour
cap (a separate Sonnet-only weekly cap too). Server-side metering is opaquely weighted by "active hours" and
does NOT match raw token counts 1:1.

**Measurement:** the community tool **`ccusage`** parses `~/.claude/projects/*.jsonl` for exact per-type token
counts and computes the cache-aware API-equivalent $. "For deriving the API-equivalent financial value of a
subscription, the raw token count is the only valid metric" — server-side "active hours" are opaque.

**Traps:** an `ANTHROPIC_API_KEY` in the shell **silently bypasses the subscription** → real API charges. Max
20x is single-user (no pooled team usage).

---

## Full research document (verbatim)

# The Economics of Agentic Ideation: An Exhaustive Unit Cost Analysis of Anthropic's Claude Max 20x

The transition from standard, conversational large language models to fully autonomous, agentic coding environments has triggered a paradigm shift in the unit economics of software engineering. As developers integrate tools like Claude Code into their daily workflows, the fundamental nature of compute consumption changes. Agentic systems operate on autonomous loops—reading expansive codebases, formulating architectural plans, executing file-by-file modifications, running automated test suites, and recursively debugging failures. Because these systems must continuously reload vast amounts of context to maintain spatial and logical awareness across multi-step operations, typical power-user workflows now routinely consume hundreds of millions, if not billions, of tokens per month.

In response to this extreme compute demand, Anthropic introduced a tiered consumer subscription model designed to cap continuous usage while providing predictable monthly costs. At the apex of this model sits the Claude Max 20x plan, priced at $200 per month. Positioned as a flat-rate alternative to the pay-as-you-go Application Programming Interface (API), this tier promises heavy developers an unmetered operational feel with significantly extended operational runways. However, a deep structural analysis reveals that the Max 20x plan operates under a complex, multi-layered quota system rather than true unlimited access.

## Official Max 20x Usage Allowances and Metering Mechanics

### Included Models and Unified Access
The Max 20x plan provides unified, cross-platform access. A single subscription covers Claude.ai web, desktop, Claude Cowork, and the Claude Code CLI, drawing from a single shared allocation pool. Models: **Sonnet 4.6** (default coding workhorse), **Opus 4.7/4.8** (flagship reasoning, reserved for planning/hard bugs), **Haiku 4.5** (fast scanning/routing), **Fable 5** (experimental, promo access, draws aggressively from the shared quota). Upgrading does not raise model intelligence or the 200K context window — the $180 premium over Pro buys usage capacity + priority routing.

### The Dual-Layered Metering System
Two overlapping caps halt inference (read-only until reset), non-overridable:
- **Rolling 5-hour window** — starts at first prompt. Max 20x = exactly 20× Pro per session (est. 200–900 prompts/window vs Pro's 10–45).
- **Weekly active-hours cap** — total model-processing hours per 7 days (idle time doesn't count). Two weekly limits: an all-model umbrella + a Sonnet-specific one. Max 20x est. 240–480 Sonnet hrs + 24–40 Opus hrs/week.

### The "20x" nomenclature controversy
Max 20x is 20× Pro *per 5-hour burst* but community testing shows only **1.5–2× the weekly budget of Max 5x**. Maxing a 5-hour window can consume ~25% of the weekly allowance; consecutive heavy sessions exhaust the 7-day quota in **36–48h**. This forces pacing and undermines the "unmetered" premise.

## Pay-As-You-Go Baseline: API + OpenRouter

### Standard token pricing (mid-2026)
Opus 4.8/4.7 $5/$25 · Sonnet 4.6 $3/$15 · Haiku 4.5 $1/$5 · Fable 5 $10/$50 (input/output per 1M).

### OpenRouter markups
A May 2026 OFox.ai audit (https://ofox.ai/blog/openrouter-pricing-hidden-markup-breakdown-2026/) confirms **zero-markup passthrough** on Anthropic inference. Fee stack: 5.5% card top-up fee ($0.80 min), 5% crypto, 0% inference markup, 5% BYOK overage after 1M free req/mo (never triggered solo). So Anthropic API list prices ≈ the OpenRouter cost.

### Prompt caching (official: https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
Cache reads = 0.1× input (90% off) · cache write 5-min = 1.25× input · cache write 1-hr = 2.0× input. In Claude Code ~90% of tokens bill as cache reads → gross tokens ≫ billed cost.

## Community-Measured Real Throughput

Local logs live in `~/.claude/projects/*.jsonl` (exact token counts). **`ccusage`** (TS CLI) computes cache-aware API-equivalent $; **Tokemon** (macOS menubar) shows depletion %. Divergence: `ccusage` reads raw client-side tokens; Anthropic's server `/usage` weights by opaque "active hours" (https://www.reddit.com/r/ClaudeCode/comments/1szpel9/). For API-equivalent VALUE, raw ccusage tokens are the valid metric.

### Case studies
- **Kyle Redelinghuys, Feb 2026** (https://www.ksred.com/i-built-a-cost-tracker-for-claude-code-to-see-if-my-subscription-was-worth-it/): 755.7M tokens/mo; Opus = 90% of spend; cost breakdown cache-reads 63% + cache-writes 34% + output 4%. API-equivalent = **$1,428.62/mo**; paid $200 → 85% savings (~7× value).
- **Extreme power user:** 2.5B tokens / 30 days without hard-capping. Saturating weekly limits all month ≈ $4,000–8,000 API-equivalent (Opus-ratio-dependent). Fable 5 promo ≈ $1,750/week API-equivalent.

### Throughput profiles
Low 860M/mo (~200M/wk) · Typical 2.15B/mo (~500M/wk) · High 3.87B/mo (~900M/wk) · Max-saturated 4.30B/mo (~1B/wk, hovering 95–99% weekly cap).

## Published Break-Even
- Duet.so Apr 2026 (https://duet.so/blog/claude-code-pricing): a dev with $15K/8mo API would pay ~$800 on Max — 93% savings; >50M tok/mo → API is "financially irresponsible."
- MorphLLM Jun 2026 (https://www.morphllm.com/ai-coding-costs): avg Sonnet bug fix $0.54 API → Max 5x breaks even at 111 fixes/mo, Max 20x at 222.
- Reddit MonkFantastic2078: Max 5x weekly ≈ $523 API (20× multiplier on $100); Max 20x weekly ≈ $1,100 (22× on $200).

## Effective Cost-Per-Token Derivation
Agentic input:output ≈ 40:1 (97.5% input/context). With 90% cache-hit, optimized blended API rates: **Sonnet $0.92/M**, **Opus $1.53/M** (vs uncached $3.29/$5.49). $200 ÷ throughput:
| Profile | Tokens/mo | Blended eff $/M | impl. input $/M | impl. output $/M |
|---|--:|--:|--:|--:|
| Low | 860M | 0.2325 | 0.230 | 1.150 |
| Typical | 2.15B | 0.0930 | 0.092 | 0.460 |
| High | 3.87B | 0.0516 | 0.051 | 0.255 |
| Max-saturated | 4.30B | 0.0465 | 0.046 | 0.230 |

Discount multiplier (typical, $0.093/M): **9.9× cheaper than Sonnet API**, **16.4× cheaper than Opus API**; at max-saturation, 20× (Sonnet) / 33.2× (Opus).

## Caveats
- **Rate-limit opportunity cost** — hard halts on quota breach; an "extra usage" toggle can overflow to metered API within a budget cap.
- **Meter anxiety removed** — the flat fee ends per-transaction friction (a qualitative driver).
- **Single-user license** — no pooled team usage; Team plan is $100/seat, siloed per seat.
- **`ANTHROPIC_API_KEY` bypass trap** — an env key silently routes to metered API; verify with `echo $ANTHROPIC_API_KEY` / `claude logout`.
- **Open-source grant** — 6-month free Max 20x for maintainers (>5K stars / 1M npm downloads).
- Effective rate falls as usage rises; per-account not pooled; server metering weighted, not raw.
