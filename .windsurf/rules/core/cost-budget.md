---
activation: glob
globs: ["**/cost_budget*", "**/libs/cost_budget/**", "**/watchdog/**", "**/llm_client*", "**/openrouter*", "**/anthropic_client*", "**/llm/**"]
description: Per-project LLM cost caps + shared cost_ledger + fail-open WAL — required for any service calling paid AI APIs or the watchdog sidecar
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (tech-plan step)
     GOAL: No project bleeds money on a runaway LLM loop overnight. Per-project caps; subscription burn visible per project.
     TRAYCER USAGE: For every Watchdog / LLM-Integration epic, include a cost-budget ticket with concrete daily caps from the Vision Summary.
     AGENT USAGE: Vendor /opt/fabrik-lib/cost-budget/. Call check_caps() BEFORE every LLM call; record_cost() AFTER. Never bypass for "just this one prompt." -->

# Cost Budget Rules

**Activation:** Glob — cost-budget code paths, watchdog sidecar, LLM clients (OpenRouter, Anthropic, Claude Code subprocess).
**Purpose:** Hard caps on AI spend per project, with portfolio visibility and a fail-open buffer so cap enforcement survives postgres-main outages.

---

## When to Use

Vendor `cost-budget` whenever a service calls **any** paid API where uncontrolled volume costs money:

- LLM APIs (Anthropic, OpenAI, OpenRouter, Gemini, Mistral, etc.).
- Translation APIs (DeepL, Azure Translator).
- OCR / vision APIs.
- Any usage-based external API where a bug or a runaway loop costs more than you'd lose to a bad sleep.

**Mandatory for every project that runs the watchdog sidecar.** The watchdog reasons with an LLM; without a cap, a feedback loop (sidecar diagnoses sidecar diagnosing sidecar) could empty your budget overnight.

For Claude Code subscription calls (the watchdog's primary provider), the cap is **per-project invocation count**, not USD — the subscription is flat-cost but its quota is finite, and one project shouldn't burn the whole subscription on everyone else's behalf.

## Per-Project Budget Setting

Caps live in the spec:

```yaml
# specs/services/my-project.yaml
watchdog:
  enabled: true
  daily_budget_usd: 1.0          # OpenRouter (fallback) cost cap
  daily_invocations_cap: 200     # Claude Code (primary) subscription cap
```

Recommended starting points (tune after a week of real data):

| Project kind | `daily_budget_usd` | `daily_invocations_cap` |
| --- | --- | --- |
| Small SaaS (low traffic) | 0.50 | 100 |
| Mid SaaS / API | 1.00 | 200 |
| High-volume worker / RAG | 2.50 | 500 |
| Internal tool | 0.25 | 50 |

**Per-task soft cap** (separate from daily cap): set a per-incident hard ceiling in code so one stuck reasoning loop can't burn the daily budget in one minute. A typical OOM diagnosis should be under 20 LLM calls — make 50 the per-incident cap.

## Tiered Model Selection Ladder

The watchdog (and any cost-conscious LLM caller) escalates models, not collapses to the most expensive one. Run the ladder top to bottom; STOP at the first tier that returns a usable answer:

| Tier | Claude Code (primary) | OpenRouter (fallback) | When to use |
| --- | --- | --- | --- |
| **1 — cheap** | Haiku | Gemini Flash / Haiku via OpenRouter | First pass on every incident. Returns structured output with a self-rated confidence (0.0–1.0). |
| **2 — expensive** | Sonnet | Sonnet via OpenRouter | Tier 1 confidence < 0.7 OR rule-based heuristic triggered (stack trace, cross-system failure). |
| **3 — rule-only fallback** | — | — | All providers failed OR cap hit. Drop to deterministic rules per `core/self-healing.md`. |

**Acknowledged limitation:** cheap-model self-rated confidence is unreliable. Always layer rule-based heuristics on top — if logs contain `Traceback`, `SIGSEGV`, `OOMKilled`, or `panic`, escalate regardless of confidence.

## Kill-Switch Semantics

Cap reached → `check_caps()` returns `over_cap=True`. Caller MUST NOT issue an LLM call.

**Drop to rule-only mode** means:

- No LLM reasoning until the daily window resets (midnight UTC).
- Sidecar continues to observe and emits Prometheus metrics.
- Sidecar continues to alert based on **hard rule thresholds** (e.g., `OOMKilled` event → restart + Apprise; queue backlog > N → pause worker + Apprise).
- Sidecar does NOT escalate "budget reached" itself as urgent — it's a warning. Owner sees it in the daily metrics review or via the `cost_budget_over_cap{project=...} 1` metric.

The kill-switch is **per-project**. One project burning its cap does not affect any other project's LLM access.

## Cost-Per-Success Metric

Recommended metric to surface in Grafana:

```
cost_per_resolved_incident_usd =
    SUM(cost_usd) / COUNT(DISTINCT incident_id WHERE resolution='auto')
over a rolling 7-day window per project_id.
```

This is the most honest measure of whether the watchdog is earning its keep. If a project's `cost_per_resolved_incident_usd` is climbing without a matching drop in owner-pages, the watchdog is spending without resolving — investigate.

Alert when:

- `cost_per_resolved_incident_usd > $0.50` per project (tune per project; SaaS with $10/mo customers needs tighter than RAG with $1k/mo customers).
- `cost_per_resolved_incident_usd` rises >50% week-over-week with no change in incident volume.

## Portfolio Analytics

Direct SQL against `cost_ledger` (sample queries in `cost-budget/README.md` and `cost-budget/schema_pg.sql`). Common shapes:

- Monthly spend per project.
- Claude Code subscription burn per project (provider='claude-code' count).
- Most expensive incident in last week.
- Spend by model (which tier are we actually escalating to?).

Wire one Grafana dashboard with these queries; review weekly.

## Anti-Patterns (what NOT to do)

- **Calling the expensive tier unconditionally.** Tier 1 first, every time. Defeats the budget purpose if you skip it.
- **Ignoring `state.stale=True`.** Means postgres-main was unreachable when caps were computed. Treat the WAL-only cap as authoritative (it has every uncommitted call); do NOT assume "well, the real cap is lower, let me spend." That's how you discover the daily cap was already breached when postgres returns.
- **Mixing test invocations with production rows.** Use a `project_id` prefix of `test-` for synthetic events; filter portfolio queries with `WHERE project_id NOT LIKE 'test-%'`.
- **Catching exceptions from `record_cost()` and skipping.** `record_cost()` is fail-open by design — it never raises on postgres-main failure (just queues to WAL). If you ARE getting an exception, it's a WAL-local failure (disk full, schema missing) — a real bug to fix, not to swallow.
- **Bypassing `check_caps()` "just this one time" for an important incident.** Cap-bypass turns into the default real fast. If you genuinely need more budget for a project, raise the spec config — don't bypass the function.
- **Mixing the watchdog's cost-budget with a host project's own LLM cost tracking.** They can both write to the same `cost_ledger`; use different `project_id` values (e.g., `myproject` and `myproject-llm-feature`) to keep them separable.

## Worked Example — Tier Escalation

Watchdog observes an OOM on `my-saas`:

```python
state = cb.check_caps(pg_conn=pg, wal_path=wal, project_id="my-saas",
                     daily_usd_cap=1.0, daily_invocations_cap=200)
if cb.drop_to_rule_only_mode(state):
    return self_heal_via_rules(incident)  # restart and alert; no LLM

# Tier 1: cheap model first.
diag = call_claude_code_haiku(incident_context, output_format="structured")
cb.record_cost(pg_conn=pg, wal_path=wal, event=CostEvent(
    project_id="my-saas",
    provider="claude-code",
    model="claude-haiku-4-5",
    in_tokens=diag.in_tokens,
    out_tokens=diag.out_tokens,
    cost_usd=0.0,  # subscription
    incident_id=incident.id,
))

# Heuristic escalation regardless of confidence.
needs_escalation = (
    diag.confidence < 0.7
    or any(s in incident.logs for s in ("Traceback", "SIGSEGV", "OOMKilled"))
)
if not needs_escalation:
    return execute_tier_a_action(diag.action)

# Tier 2: expensive model.
diag = call_claude_code_sonnet(incident_context, output_format="structured")
cb.record_cost(pg_conn=pg, wal_path=wal, event=CostEvent(
    project_id="my-saas",
    provider="claude-code",
    model="claude-sonnet-4-6",
    in_tokens=diag.in_tokens,
    out_tokens=diag.out_tokens,
    cost_usd=0.0,
    incident_id=incident.id,
))

if diag.action_tier in ("A",):
    return execute_tier_a_action(diag.action)
elif diag.action_tier in ("B",):
    if owner_opted_in_tier_b(project_id="my-saas"):
        return execute_tier_b_action(diag.action)
    # Otherwise Tier B requires owner approval → escalate (no autonomous action).

# Tier C or no autonomous action possible.
return escalate_to_owner_via_apprise(diag.reason)
```

This flow keeps the cheap tier as the default, escalates only when needed, and records every call so portfolio analytics know where the money (or subscription burn) went.
