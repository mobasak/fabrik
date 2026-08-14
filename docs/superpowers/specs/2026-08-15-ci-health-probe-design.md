# Design spec — fleet CI-health probe (detect CI that never ran)

Status: DRAFT
Date: 2026-08-15 · Owner: infra

## The problem, from a live incident

2026-08-15: GitHub refused to start Actions jobs on every PRIVATE repo (Free plan, 2000-minute
allowance crossed in July, $0 spending limit → jobs refused rather than billed). Symptoms:
1-second "failures", **zero steps**, no logs, and a billing annotation. tryton-crm,
trade-intelligence and youtube had dead CI; the hub was unaffected only because it is PUBLIC
(unmetered). **The operator discovered it by noticing red checks repo by repo.**

Nothing on the box could have seen it:

- `final_gate.py` runs ruff/pytest LOCALLY — a repo is green on the box while its CI never runs.
- `ci_fix_dispatcher.py:109-135` (`recent_failures`) selects runs by `status=failure` + branch +
  age. It has **no way to distinguish "tests failed" from "job never started"**, so it would have
  dispatched `claude -p` workers to fix code that was never broken — burning quota on an
  unfixable class, during a quota-caused outage.
- The usage curve was public in the billing API the whole time: **529 → 1478 → 2074 → 2409
  minutes/month** (May→Aug), crossing 2000 in July. Nobody was reading it.

## Grounded facts (live, this session)

- The signature of a refused job is exact and cheap to detect:
  `gh api repos/{o}/{r}/actions/runs/<id>/jobs --jq '.jobs[0].steps | length'` → **0**, with
  `conclusion=failure`, and the annotation text *"The job was not started because recent account
  payments have failed or your spending limit needs to be increased"*.
- The predictive number is one call: `gh api /users/<user>/settings/billing/usage` →
  `usageItems[] {date, product:"actions", sku:"Actions Linux", quantity}` (the per-user endpoint
  that replaced the 410'd `/settings/billing/actions`).
- Included allowances (fetched from GitHub docs this session): **Free 2000 min/mo · Pro 3000 ·
  Team 3000**; Linux 2-core overage **$0.006/min**; **public repos unmetered**; **self-hosted
  runners free**. Plan readable at `gh api /user --jq .plan.name` (now: `pro`).
- Alert transport already exists and is proven: `claude-sound.sh mesh-notify <sid> <cwd> <err>`
  (Telegram, `/opt/*` cwd gate, per-target suppression). No new alerting machinery.

## Approach (single)

A `scripts/sysadmin/ci_health_probe.py` on cron, plus a one-line defect fix in the dispatcher.

1. **Block detection (reactive).** For every `/opt` git repo with a GitHub remote, read the most
   recent run; if `conclusion=failure` AND the job has **zero steps**, classify it
   `never-started` and (when cheap) attach the annotation text. One `gh run list` per repo, plus
   one `jobs` call only for failures.
2. **Quota foresight (predictive) — the half that would have PREVENTED this.** One billing call
   for the account: current-month Actions minutes vs the plan's included allowance. WARN at
   **80%**, ALERT at **100%**. This is deliberately CI-scoped; the wider subscription/spend layer
   is a separate deferred spec (memory: `subscription-spend-tracking-gap`).
3. **Alert once, not per repo.** A fleet-wide block is ONE Telegram naming the affected repos
   (today that would have been one message instead of three discoveries), with a 24h suppress
   stamp in `~/.claude/state/` (the VM-cut-survivable dir).
4. **Stop the dispatcher wasting quota (defect fix).** `recent_failures` gains a
   `never-started` filter: a run whose job has zero steps is EXCLUDED from fix dispatch and
   reported instead. Fixing code that was never the problem is the worst possible use of the
   resource that caused the outage.

## Requirements → acceptance

| # | Requirement | Acceptance |
|---|---|---|
| 1 | A never-started run is classified, not treated as a test failure | fixture: a run JSON with `conclusion=failure` + `steps: []` → classified `never-started`; a run with real failed steps → `test-failure` |
| 2 | The dispatcher never dispatches on a never-started run | `recent_failures` returns [] for the zero-step fixture; returns the run for a genuine failure |
| 3 | Quota foresight fires BEFORE the wall | fixture: 1700/2000 min → WARN; 2100/2000 → ALERT; 900/3000 (Pro) → silent |
| 4 | One alert per event, not per repo | 3 blocked repos in one tick → exactly one mesh-notify call naming all three |
| 5 | Suppression survives a VM cut | stamp in `~/.claude/state/`; second tick within 24h sends nothing |
| 6 | Costs nothing | no Actions minutes consumed (API reads only); ≤2 gh calls per repo per run + 1 account call |
| 7 | Fails soft | no network / no `gh` / unauthenticated → log and exit 0, never a cron traceback |

## Out of scope

- The subscription/spend layer across all 39 paid services (deferred by the operator 2026-08-15).
- Auto-remediation of billing (raising limits, changing plans) — alerting only; money decisions
  stay with the operator.
- Self-hosted runner migration (the escape hatch if usage grows again).

## Risks

- **Zero-step detection could false-positive** on a cancelled run or a workflow-syntax error;
  both are ALSO "CI did not run" and worth surfacing, so the classifier reports the observed
  reason rather than asserting "billing".
- **The billing endpoint moved once already** (410 on the old path) — the probe must treat a
  non-200 as "unknown", never as "0 minutes used" (a fail-open zero would silence the alert
  exactly when the API changes again).
