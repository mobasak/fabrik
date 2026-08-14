# CI-health probe — catching CI that never ran

**What it is:** `scripts/sysadmin/ci_health_probe.py`, hourly on cron at `:35` (five minutes
before `ci_fix_dispatcher` at `:40`, deliberately — see below). Costs nothing: API reads only,
no Actions minutes consumed.

## The gap it closes

`final_gate.py` runs ruff/pytest **on the box**. A repo can be perfectly green locally while its
GitHub CI never runs at all — and nothing watched for that. On **2026-08-15** GitHub refused to
start Actions jobs on every PRIVATE repo (Free-plan 2000-minute allowance crossed in July, `$0`
spending limit → refusal instead of billing). Jobs "failed" in one second with **zero steps** and
no logs. The operator discovered it by noticing red checks repo by repo; the probe would have
sent one message.

## Two legs

**Reactive — "did it actually run?"** A job with `conclusion=failure` and an **empty steps list**
never reached a runner. That signature covers billing refusals, invalid workflow YAML, and
dispatch-time cancellations. The probe reports GitHub's own annotation text rather than guessing
the cause, and **dates the run** — after a billing fix the newest run is often still a pre-fix
failure, so "blocked" without an age misleads.

**Predictive — "when will it die?"** One call reads current-month Actions minutes against the
plan's included allowance (`/users/<login>/settings/billing/usage`; Free 2000 · Pro 3000 · Team
3000; public repos unmetered; self-hosted runners free). WARN at 80%, ALERT at 100%. This is the
half that would have PREVENTED the outage — the curve was **529 → 1478 → 2074 → 2409** minutes
over four months, public in the API, unwatched. A non-200 reads as **UNKNOWN, never as zero**: a
fail-open zero would silence the alert exactly when the endpoint moves (it already moved once).

## The dispatcher defect it also fixed

`ci_fix_dispatcher.py` selected failures by status+branch+age with no way to tell "tests failed"
from "job never started" — so during the outage it would have dispatched `claude -p` workers to
fix code that was never broken, burning the very quota whose exhaustion caused the failures.
`recent_failures` now skips zero-step runs and says so. That is why the probe runs first.

## Operating it

```bash
python3 /opt/fabrik/scripts/sysadmin/ci_health_probe.py          # full report
python3 /opt/fabrik/scripts/sysadmin/ci_health_probe.py --quiet  # cron mode (silent when healthy)
```

Alerts go through the existing `claude-sound.sh mesh-notify` Telegram path — **one message per
event naming every affected repo**, not one per repo — with a 24h suppress stamp in
`~/.claude/state/` (VM-cut-survivable). Knobs: `CI_PROBE_WARN_PCT` (80), `CI_PROBE_SUPPRESS_S`
(86400), `CI_PROBE_OPT_ROOT` (/opt).

## Related

- `docs/superpowers/specs/2026-08-15-ci-health-probe-design.md` (design + the incident)
- Deferred sibling: a subscription/spend layer over `scripts/service_catalog.json` — 39 active
  paid services with no plan/price/renewal/quota tracked (memory: `subscription-spend-tracking-gap`)
