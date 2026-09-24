---
activation: glob
globs: ["**/cost_budget*", "**/libs/cost_budget/**", "**/watchdog/**", "**/llm_client*", "**/openrouter*", "**/anthropic_client*", "**/llm/**"]
description: Per-project cost caps on paid APIs — the fail-open accounting lane, the fail-closed reservation lane, the watchdog's caps, and what the ledger's dollar figures mean
trigger: glob
currency_pass: 2026-09-24
---
<!-- CONSUMER: coding agents (all) + the planning commands (/fabrik-spec, /fabrik-plan-after-chat) when a feature calls paid APIs
     GOAL: no project bleeds money on a runaway loop overnight; per-project caps; spend visible per project
     AGENT USAGE: vendor /opt/fabrik-lib/cost-budget/; pick the lane below; check before every paid call, record after it; never bypass.
     PLANNING: a feature or epic that calls paid APIs carries its caps (daily USD, invocations, per-task bound) into the plan as a concrete ticket. -->

# Cost Budget Rules

**Activation:** Glob — cost-budget code paths, the watchdog sidecar, LLM clients.
**Purpose:** hard ceilings on paid-API spend per project, with portfolio visibility, surviving a `postgres-main` outage.

**Sources:** external facts re-grounded on 2026-09-24 (`docs/reference/research/2026-09-24-cost-budget-currency-ledger.md`); the load-bearing ones are in `.windsurf/rules/CLAIMS.yaml` (`pack: core/cost-budget.md`). Module behaviour is cited to `/opt/fabrik-lib/cost-budget/` and `/opt/fabrik-lib/watchdog/`. The cap values and the escalation thresholds below are house heuristics — tune them on a week of real ledger data.

---

## When to Use — and Which Lane

Vendor `cost-budget` (`cp -r /opt/fabrik-lib/cost-budget libs/cost_budget`) whenever a service calls a paid API where a bug or a runaway loop costs money: LLM APIs, translation, OCR/vision, any usage-billed API. It is a safety cap, not billing or rate limiting (`api-quota`, `concurrency-throttle` do those).

The module has two lanes. Pick by what an overshoot costs:

| Lane | Module | Failure mode | Use it for |
|---|---|---|---|
| **Accounting** | `cost_budget.py` — `check_caps()` before, `record_cost()` after | **Fail-OPEN**: a `postgres-main` outage queues rows to a local SQLite WAL and never blocks work. The cap is SOFT: the check runs before the call, so the call that crosses the cap is spent in full, and N concurrent callers can each pass the check and overshoot by up to N calls | Internal LLM use where one extra call is acceptable: the watchdog, dev tooling, portfolio visibility |
| **Reservation** | `cost_reservations.py` — `reserve()` in the caller's transaction, then `settle()` / `abandon()`, plus a scheduled `reclaim()` | **Fail-CLOSED**: `reserve()` raises `BudgetExceeded` / `DailyCapExceeded` when it cannot admit; no reservation, no paid call | Customer-facing or per-tenant paid work, or a shared metered pool, where an overshoot must be impossible (a monthly budget plus a per-tenant daily cap) |

Never "helpfully" make `reserve()` fall open — a silent overshoot is what it exists to stop. The reservation lane's policy is all call arguments (`estimate_usd`, `monthly_budget_usd`, `daily_cap`); the module does not convert credits to USD. Roll the caller's transaction back on ANY `LedgerRefusal` (`with pg_conn:` around the job insert and `reserve()`) — a committed `DailyCapExceeded` leaves the month total inflated. `settle` / `abandon` / `reclaim` need the tenant armed (pass `tenant_id=`) or, under FORCE RLS, they silently no-op; a cross-tenant `reclaim` needs a maintenance role outside RLS (module README § Gotchas).

**Provisioning:** `fabrik apply` creates the shared `fabrik_analytics` database on `postgres-main` with the `cost_ledger` and reservation-table DDL; host projects never apply these schemas themselves, and a consumer outside the registrar calls `cost_reservations.init()` once. `cost_ledger` is meant to be append-only (`INSERT, SELECT`) and the reservation tables `INSERT, SELECT, UPDATE`, but no apply path runs those GRANTs today (`drivers/postgres.py` grants only when a caller passes `grant_to_role`, and none does — filed to fleet). The DSN is yours to set: `FABRIK_ANALYTICS_URL` in the project's environment (nothing injects it — the watchdog sidecar gets its own `WATCHDOG_PG_DSN`). Set it wherever the ledger exists: `check_caps()` reads it to tell "no connection" from "no ledger", and without it a failed connect reads as `stale=False`.

## The Watchdog's Caps

The watchdog sidecar carries its own copy of the accounting lane — a project running the watchdog does not vendor it separately. Its caps live in the spec:

```yaml
# specs/services/my-project.yaml
watchdog:
  enabled: true
  daily_budget_usd: 1.0          # USD cap — ALL providers, Claude Code included (see below)
  daily_invocations_cap: 200     # call-count cap
```

Both default to these values and reset at midnight UTC; a watchdog enabled with both caps at 0 is refused by `fabrik apply` (`orchestrator/infrastructure.py`) and by the `WatchdogConfig` validator (`spec_loader.py`) that `plan` and `audit` use. ⚠️ A single cap of 0 does NOT disable that cap, whatever the spec description says: `check_caps()` tests `spent >= cap`, so a 0 cap is over from the first second and the watchdog runs rule-only every day — keep both caps above 0 (filed to fleet). **Sizing:** a Claude Code diagnosis counts at API list price (next section) and the default model is Opus, so a $1 day covers only a handful of diagnoses — size `daily_budget_usd` from a week of `SUM(cost_usd)` for the project, and keep `daily_invocations_cap` as the hard count ceiling.

**What the watchdog actually calls:** one diagnosis per incident — `claude -p --model opus --output-format json` by default (`WATCHDOG_CLAUDE_MODEL`; the `opus` alias is the recommended Opus for your provider, not necessarily the newest release), then the OpenRouter fallback (`WATCHDOG_CHEAP_MODEL`), then rule-only mode (`watchdog_sidecar/llm_client.py::diagnose`). There is no automatic Haiku→Sonnet escalation inside it. ⚠️ That describes the ops-only path. With `auto_code_fix` on (which requires `propose_fix_prs`), the coordinator diagnoses without a cap check, then runs up to two more Opus fix runs (and an advisor call when `verify_before_deploy` is on) — none of it recorded to the ledger, so the daily caps do not bound that path (filed to fabrik-lib). ⚠️ **Its default fallback model is dead:** `anthropic/claude-3.5-haiku` (the hub's `drivers/watchdog.py` default and the sidecar's) is retired on Anthropic's API and has no OpenRouter endpoint, so a Claude Code failure falls straight to rule-only. Set `watchdog.cheap_model: anthropic/claude-haiku-4.5` in the spec until the defaults move (filed to fleet and fabrik-lib). The sidecar's copy of the module and the library have drifted both ways (the sidecar lacks `invocations_provider`; the library lacks the sidecar's non-finite-total guard).

**There is no per-incident dollar cap, by operator ruling.** `WATCHDOG_PER_INCIDENT_BUDGET_USD` (deployed default 0.25) is accepted and ignored: the sidecar must not pass `--max-budget-usd` (`llm_client.py`: "no $ caps on sysadmin; session-init cache cost alone exceeds any sane per-call cap"). The daily caps are the only ceiling on one incident; `--max-turns` is the flag that bounds a call without that conflict. (The spec model still documents a 0.50 default passed to `--max-budget-usd` — filed to fleet.)

## What the Ledger's Dollars Mean

- **Claude Code rows record `total_cost_usd` from the CLI's JSON envelope** (`llm_client` → `record_cost`), not 0. On a subscription that figure is a client-side estimate at API list prices, not money billed — Anthropic's docs say not to trigger financial decisions from it. It is still the right unit for a cap: it measures subscription quota burn in API-dollar terms, so `daily_budget_usd` binds Claude Code calls too (sizing: § The Watchdog's Caps).
- **OpenRouter rows are real spend** — OpenRouter returns token usage and cost on every response. Give the fallback's key a per-key credit limit on OpenRouter as a second, provider-side ceiling: once the key's `limit_remaining` is exhausted, OpenRouter answers 402 until the limit is raised or resets.
- **Invocation cap per provider:** the USD cap is all-provider; pass `invocations_provider` to `check_caps()` so a burst of fallback HTTP calls cannot exhaust the CLI's call budget — and match the provider string your rows carry: `claude-code` for the watchdog's rows, `claude-cli` for rows recorded through `llm-dispatch`'s hooks. A mismatch counts nothing and the cap never binds.

## Kill-Switch Semantics

- Cap reached → `check_caps().over_cap` is true → `drop_to_rule_only_mode()` returns true → the caller MUST NOT issue the paid call. The window reopens at midnight UTC.
- The watchdog then escalates each incident to Apprise without diagnosis, titled `(BUDGET-CAP)`, and arms the deadman (`core/self-healing.md` — one `docker restart` after its timeout); no LLM-chosen Tier A/B action runs until midnight UTC (the deadman's own Tier-A `restart_container` still fires). Anomaly detection keeps running.
- **`stale` is fail-DANGEROUS, not fail-safe.** When `postgres-main` is unreachable, `check_caps()` sets `stale=True` and totals from the WAL alone — but a successful `record_cost()` deletes its WAL row, so the WAL holds only unreplayed calls and the total reads near $0. `drop_to_rule_only_mode()` looks at `over_cap` only. **Treat `stale=True` as over cap** (`over_cap or stale`) for any spending decision; the watchdog does not yet (filed to fabrik-lib). The reservation lane has no such mode — it refuses instead.
- The kill-switch is per project: one project's cap never touches another's.
- Metrics: `prometheus_metrics()` renders `llm_cost_dollars_total`, `llm_cost_dollars_cap`, `llm_invocations_total`, `llm_invocations_cap`, `cost_budget_over_cap`, `cost_budget_stale` (labelled `project`). The watchdog sidecar does not export them today (filed to fabrik-lib); a project that wants the alert serves the string itself — and alerts on `cost_budget_stale == 1` as well as on the cap.

## Model Selection for Your Own LLM Callers

For an LLM caller you write, climb the model ladder in `ai/00-ai-model-selection.md` § the dispatch ladder (Haiku first, each rung only when the previous one measurably falls short); falling back to deterministic rules when every provider fails or the cap is hit is your code's job. Wire this module into fabrik-lib `llm-dispatch` through its `budget_check` / `budget_record` hooks rather than hand-rolling the calls. Bound each task in code too — a turn or attempt limit per task (`--max-turns` on a `claude -p` leg) — so one stuck loop cannot burn the day's cap in minutes.

**Do not trust self-rated confidence alone:** research finds verbalized LLM confidence overconfident in absolute terms (expected calibration error around 0.1 for 70B+ models) and sensitive to how it is asked, so always layer deterministic triggers on top — `Traceback`, `SIGSEGV`, `OOMKilled`, `panic` in the logs escalate regardless of confidence.

## Cost-Per-Success Metric

The honest measure of whether an LLM loop earns its keep is spend per resolved incident over a rolling 7 days, per project, and whether it climbs without a matching drop in owner pages. ⚠️ The data is not joinable today: `cost_ledger` has an `incident_id` column but the watchdog records costs without it, and resolutions (`auto` / `manual` / `expired`) live in the sidecar's local SQLite state, not in `cost_ledger` (filed to fabrik-lib). Until then, divide the day's `SUM(cost_usd)` by the sidecar's auto-resolved count. Once it is joinable, alert when it exceeds a per-project target (start at $0.50; tighter for low-ARPU products) or rises more than 50% week over week with flat incident volume.

## Portfolio Analytics

Query `cost_ledger` directly (samples in the module's `schema_pg.sql` and README): monthly spend per project, Claude Code calls per project (`provider = 'claude-code'`), spend by model, most expensive incident (empty for watchdog rows until they carry `incident_id` — § Cost-Per-Success). Wire one Grafana dashboard and review it weekly.

## Anti-Patterns

- **Reading `stale=True` as "safe to spend".** It means the total is missing today's recorded spend — see Kill-Switch.
- **Treating Claude Code rows as free.** They carry an API-price estimate; the USD cap counts them.
- **Mixing test and production rows.** Prefix synthetic `project_id`s with `test-`; filter `WHERE project_id NOT LIKE 'test-%'`.
- **Swallowing an exception from `record_cost()`.** It never raises on a `postgres-main` failure (it queues to the WAL); an exception is a local fault (disk full, schema missing) — fix it. Under `llm-dispatch` the dispatcher swallows it with a `cost record failed` warning: alert on that warning.
- **Bypassing the check "just this once".** Raise the spec cap instead.
- **Sharing one `project_id` between the watchdog and a feature's own LLM calls.** Use distinct ids (`myproject`, `myproject-llm-feature`) so each keeps its own cap and ledger rows.
- **Using the accounting lane where an overshoot is unacceptable.** That is the reservation lane's job.
- **Gating one provider.** With `llm-dispatch`, a `budget_check` that refuses `claude-cli` sends the call down the METERED OpenRouter leg — it redirects the spend instead of stopping it. The hook must refuse EVERY provider when `over_cap or stale`, and it fails open on an exception, so it must never raise.

## Worked Example — `llm-dispatch` Hooks on the Accounting Lane

```python
from libs.cost_budget import cost_budget as cb

PROJECT = "my-saas-summarizer"

def budget_check(provider: str) -> bool:
    # Called by llm-dispatch before EACH provider leg. Refuse all of them together,
    # and never raise — an exception here fails OPEN.
    try:
        state = cb.check_caps(pg_conn=pg, wal_path=wal, project_id=PROJECT,
                              daily_usd_cap=2.0, daily_invocations_cap=500,
                              invocations_provider="claude-cli")
        return not (cb.drop_to_rule_only_mode(state) or state.stale)
    except Exception:
        return False

def budget_record(provider: str, model: str, usage: dict, cost_usd: float) -> None:
    # provider is "claude-cli" or "openrouter"; llm-dispatch calls this on SUCCESS only.
    cb.record_cost(pg_conn=pg, wal_path=wal, event=cb.CostEvent(
        project_id=PROJECT, provider=provider, model=model,
        in_tokens=usage.get("input_tokens", usage.get("prompt_tokens", 0)),      # Claude / OpenRouter keys
        out_tokens=usage.get("output_tokens", usage.get("completion_tokens", 0)),
        cost_usd=cost_usd,                 # Claude Code's estimate — it counts toward the USD cap
        incident_id=current_request_id.get(),   # a contextvar you set per request; the hook carries no id
    ))
```

In `budget_check`, pass `invocations_provider="claude-cli"` — the string these rows carry. `llm-dispatch` raises on a failed call before it records, so a failed call's spend (a `--max-turns` exit, say) never reaches the ledger: leave headroom in the cap (filed to fabrik-lib).

Pass both as the dispatcher's `budget_check` / `budget_record` hooks, start the ladder at Haiku, and escalate only on a measured shortfall or a deterministic trigger.
