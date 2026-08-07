# Financials — [PROJECT_NAME]

**Last Updated:** [DATE]
**Source of truth for:** pricing, costs, margins, unit economics

---

## 0. Mode — Billed SaaS vs Internal Tool

<!--
  Pick one. Most of this doc is written for billed-SaaS projects. Internal
  tools / infrastructure services don't have subscription tiers, credit packs,
  or margin math — but they DO have costs that matter for budgeting and
  capacity planning. If you're an internal tool, skip §§1–3, §§5–8, §10 and
  fill only §§4 (Infrastructure Costs) and §9 (Live Metrics) — that's the
  "what does it cost us to run this?" view.
-->

This project is: **[ ] Billed SaaS** · **[ ] Internal tool / infrastructure service**

**If Internal tool:** §§1, 2, 3, 5, 6, 7, 8, 10 do not apply — delete them. Keep:

- §4 (Infrastructure Costs) — what we pay to run it
- §9 (Live Metrics) — actuals vs budget
- Add a one-line "What manual cost does this save?" sentence here (e.g. "without this, manual domain provisioning takes 2h/domain at $X/h").

---

## 1. Subscription Tiers

5-tier structure. Free is a loss leader. Each tier must be strictly better value per-unit than the one below it.

| | Free | Starter | Plus | Pro | Business |
|---|---|---|---|---|---|
| **Price** | $0/mo | $X/mo | $X/mo | $X/mo | $X/mo |
| **Credits/mo** | 10 | X | X | X | X |
| **Per credit** | free | $X | $X | $X | $X |
| **Feature 1** | Limited | Yes | Yes | Yes | Yes |
| **Feature 2** | No | No | Yes | Yes | Yes |
| **Feature 3** | No | No | No | Yes | Yes |
| **API access** | No | No | No | Yes | Yes |
| **Priority queue** | No | No | No | Yes | Yes |

**Pricing rule:** per-credit cost MUST decrease monotonically as tier increases:

```
Business < Pro < Plus < Starter (per-credit cost)
```

If a user on Starter is paying more per-credit than they would on Plus, the tier boundary is wrong.

---

## 2. Credit Packs (Top-up)

One-time purchases for users who exhaust monthly credits before renewal.

| Pack | Credits | Price | Per credit |
|---|---|---|---|
| Micro | X | $X | $X |
| Small | X | $X | $X |
| Medium | X | $X | $X |
| Large | X | $X | $X |

### Pricing Rule (mandatory)

**Packs must ALWAYS be more expensive per-credit than any subscription tier.** Packs are emergency top-ups, not a substitute for subscribing. This ensures upgrading is always the better deal for regular users.

Complete per-credit rate ladder (cheapest → most expensive):

```
Business < Pro < Plus < Starter < Large pack < Medium pack < Small pack < Micro pack
```

**Nudge rule:** if a user buys packs totaling more than the next tier up in a billing cycle, surface an upgrade nudge: "You spent $X on packs this month — [TIER] gives you X credits for $X."

---

## 3. Credit Costs (What the User Pays)

Define what each user-facing operation costs in credits. Keep it simple — flat per-operation pricing is easier to understand than variable pricing.

| Operation | Credit cost | Notes |
|---|---|---|
| [Primary operation] | X credits | Flat per unit |
| [Secondary operation] | X credits | Flat per unit |
| [Premium operation] | X credits | Only available on Plus+ |
| [Expensive operation] | X credits | Consider surcharge or tier cap |

**Rules:**
- Flat per-operation pricing (not variable by duration/size) unless the cost variance exceeds 10x between operations
- If an operation has a 10x+ cost range, split into tiers (e.g., "standard" vs "extended") rather than variable pricing
- Free tier gets enough credits to complete the core action 2-3 times — enough to experience value, not enough to abuse

---

## 4. Infrastructure Costs (What We Pay)

### 4.1 Variable Costs Per Operation

Fill this from production data. Until you have production data, estimate from API pricing pages.

| Service | What it does | Cost/operation | % of total | Notes |
|---|---|---|---|---|
| [Primary API] | Core processing | $X | X% | The main cost driver |
| [Secondary API] | Enrichment/fallback | $X | X% | Only fires X% of the time |
| [Proxy/bandwidth] | Network costs | $X | X% | Per-request or per-GB |
| [Storage] | File/data storage | $X | X% | Usually negligible at small scale |
| **TOTAL** | | **$X/operation** | | Verified from production data |

**Key insight to discover:** which path is free/cheap (the common case) vs which path is expensive (the rare case). Most SaaS products have a "happy path" that costs nearly nothing and an "expensive path" that dominates the cost when it fires. Identify both. Price based on the blended rate, not the expensive path.

### 4.2 Fixed Costs — Monthly

| Item | Cost/mo | Notes |
|---|---|---|
| **VPS (fabrik apply)** | $X | Shared across projects (allocate proportionally) |
| **Domain** | $X | Annual ÷ 12 |
| **Third-party subscriptions** | $X | Any monthly API plans, proxy subscriptions |
| **Prepaid pools** | $X | Amortized (total prepaid ÷ expected months of usage) |
| **Development tooling (project share)** | $X | Claude Max + OpenRouter pool + Traycer ÷ active projects |
| **Total fixed** | **$X/mo** | |

---

## 5. Margin Analysis

### Formula

```
Revenue per tier      = subscription price
Max operations        = credits ÷ credits-per-operation
Variable cost         = max operations × cost-per-operation (blended)
Margin                = revenue - variable cost
Margin %              = margin ÷ revenue × 100
```

### Blended Cost Margins (all paths weighted by actual frequency)

| Tier | Revenue | Max operations | Variable cost | **Margin** | **Margin %** |
|---|---|---|---|---|---|
| **Free** | $0 | X | $X | -$X | loss leader |
| **Starter** | $X | X | $X | **$X** | **X%** |
| **Plus** | $X | X | $X | **$X** | **X%** |
| **Pro** | $X | X | $X | **$X** | **X%** |
| **Business** | $X | X | $X | **$X** | **X%** |

### Realistic Margins (common path only — the path 90%+ of operations take)

Most operations take the cheap path. Calculate margins using only the common-path cost to see the realistic picture.

| Tier | Revenue | Max operations | Variable cost | **Margin** | **Margin %** |
|---|---|---|---|---|---|
| **Starter** | $X | X | $X | **$X** | **X%** |
| **Plus** | $X | X | $X | **$X** | **X%** |
| **Pro** | $X | X | $X | **$X** | **X%** |
| **Business** | $X | X | $X | **$X** | **X%** |

### Worst Case (100% expensive path)

Calculate what happens if every single operation hits the expensive path. If any paid tier shows a loss, you need one of:
- Cap the expensive operation per tier
- Add a surcharge for the expensive path
- Increase the credit cost for that operation

| Tier | Revenue | Max operations | Variable cost | **Margin** |
|---|---|---|---|---|
| **Starter** | $X | X | $X | **$X (profit/loss?)** |
| **Plus** | $X | X | $X | **$X** |
| **Pro** | $X | X | $X | **$X** |
| **Business** | $X | X | $X | **$X** |

**Rule:** if worst-case shows a loss on ANY paid tier, add a mitigation before launch. Never launch with a tier that loses money under realistic abuse scenarios.

---

## 6. Break-even

```
Monthly burn     = fixed costs + (development tooling share)
Break-even       = monthly burn ÷ average revenue per subscriber
```

| Scenario | Revenue needed | Subscribers |
|---|---|---|
| Cover infra only | $X/mo | X subscribers at [tier] |
| Cover infra + dev tooling | $X/mo | X subscribers at [tier] |
| Profitable (2x infra) | $X/mo | X subscribers at [tier] |

---

## 7. Prepaid Pool Tracking

For any prepaid service (API credits, bandwidth pools, etc.), track balance and burn rate.

| Pool | Prepaid total | Spent | Remaining | Usage rate | Runway |
|---|---|---|---|---|---|
| [Service 1] | $X | $X | $X | $X/mo | X months |
| [Service 2] | $X | $X | $X | $X/mo | X months |

---

## 8. Key Risks

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| **Expensive path dominance** | Margins collapse if cheap path fails | Low (monitor %) | Cap expensive operations per tier; surcharge |
| **Prepaid pool depletion** | Service degrades when pool hits $0 | Medium (track runway) | Auto-alert at 20% remaining; top-up plan |
| **API quota exhaustion** | Free-tier limits hit; operations fail | Medium at scale | Implement queuing; request quota increase |
| **VPS capacity** | Response times degrade under load | Low until 10x growth | Worker autoscaling; upgrade plan documented |
| **Abuse (free tier farming)** | Credits burned by bots, no revenue | Medium | See `saas/87-abuse-detection.md` |

---

## 9. Live Metrics (auto-updated)

<!-- LIVE_METRICS_START -->
### Production Metrics (auto-updated [DATE])

| Metric | Value |
|---|---|
| Total operations (all-time) | X |
| Operations via cheap path | X% |
| Operations via expensive path | X% |
| Total variable cost (all-time) | $X |
| **Cost per operation (blended)** | **$X** |
| **Cost per operation (cheap path only)** | **$X** |
| Current throughput | X/hr |

<!-- LIVE_METRICS_END -->

To auto-update this section, create `scripts/update_financials.py` that queries your database for production metrics and overwrites between the markers above.

---

## 10. Pricing Validation Checklist

Before launch, verify:

- [ ] Per-credit cost decreases monotonically across tiers (Business < Pro < Plus < Starter)
- [ ] All packs are more expensive per-credit than any subscription tier
- [ ] Free tier gives enough credits to experience core value (2-3 operations)
- [ ] No paid tier loses money under realistic worst-case (not just average case)
- [ ] Break-even is achievable with < 50 subscribers
- [ ] Upgrade nudge logic exists (pack spend > next tier price → nudge)
- [ ] Expensive-path operations are capped or surcharged per tier
- [ ] Prepaid pools have > 3 months runway
- [ ] `scripts/update_financials.py` exists and is wired to production DB
