# tryton-crm deploy — command/rule/infra defects, reconstructed from session history

Status: IN-PROGRESS — first pass only, superseded in scope
**Date:** 2026-08-31 · **Author:** fleet

> ⚠️ **This is a bounded first pass, not the finished analysis.** It searched 6 lexical queries and 25
> recent sessions (see § Denominator honesty) — it did NOT walk the project's specs, plans, review
> artifacts or full chat history backwards. The operator has commissioned that deeper sweep; the brief
> for it was authored 2026-08-31 and its output lands at
> `docs/development/reviews/2026-08-31-tryton-crm-machinery-retrospective-review.md`. Findings below are
> real and evidence-backed, but treat the SET as incomplete until that sweep lands — and **verify rather
> than inherit them**: the brief instructs the deeper pass to re-derive, extend or refute this file.
**Method:** session-recall (`recent_chats` + 6 × `search_chats`) over `-opt-tryton-crm` and `-opt-fabrik`,
cross-checked against the live repo at `path:line` and the live fleet over SSH.
**Scope:** defects in our **commands, rule packs and platform machinery** that affect the tryton-crm
deployment *now*. Project-side application bugs are out of scope except where a command should have
caught them.

---

## ⚠️ Denominator honesty — what this search did and did not cover

State the bound before the conclusions, because a negative from a bounded search is not a negative:

| Probe | Bound | Result |
|---|---|---|
| `recent_chats(project=-opt-tryton-crm, n=25)` | **25 sessions, the cap I passed** | 22 of 25 are near-identical UI-QA *subagent* sessions from 2026-08-10; only **3** are substantive (the product/price API session `a0cc0bfb`, two CI auto-fix sessions) |
| `search_chats` × 6 | 10-15 hits each | 2 of the 6 returned **zero** — the index is lexical (`websearch_to_tsquery` + trigram), so a fact phrased differently is invisible |
| Index freshness | — | every call warned `recall index may be a few minutes stale (reindex hit the ~8s cap)` |

So: **this is "the defects findable in N bounded probes", not "all defects that exist".** The lexical-only
limitation matters specifically here — a defect discussed in wording I did not guess is unreachable by
this method, which is itself one of the findings below (D9).

---

## The headline

**Every deployment-affecting defect found in this deploy was already known — and none of them was
carried by a command.**

The knowledge lived in session transcripts, in a superseded plan, in a review report, and in spec
comments. The commands encode *process* (converge, verify, gate, loop to a no-op) but carry almost no
accumulated *deploy knowledge*. So each deploy rediscovers the same facts, and a deploy that does not
rediscover one ships the defect.

This is not a hypothesis. Six instances, each with a date on both ends:

| # | Fact | Known when + where | What happened on 2026-08-31 |
|---|---|---|---|
| 1 | autoheal pause has a **7200s staleness** window | **2026-08-11**, session summary § "Deploy hard facts": *"autoheal pause (`/run/fabrik-autoheal/pause` + `pause.owner`, 7200s staleness…)"* | My plan wrote the **wrong invariant** — "no single in-window step may exceed 90 minutes" — a per-step bound guarding a cumulative-mtime mechanism. Caught only after the operator repeated the same instruction verbatim |
| 2 | **readiness deadlocks `up --wait`** (liveness-not-readiness healthcheck) | **2026-08-11**, same summary | Rediscovered from zero as the "cold-start class", written up as a NEW class, and filed to infra as new |
| 3 | `from_env` **only warns** on a missing key | **2026-08-20**, seq 8491: *"`fabrik apply` reads `from_env` secrets from `/opt/tryton-crm/.env` and a missing key only *warns*"* | Survived as an unproven "residual" until the operator explicitly ordered it re-derived |
| 4 | `gotenberg` **name + alias collision** on the shared net | Recorded as a spec annotation (`specs/services/tryton-crm.yaml` `GOTENBERG_URL` comment, from deploy-plan-review F1 2026-08-11) | Re-verified by hand each round; nothing mechanical asserts it |
| 5 | `account_payment_clearing` **missing from the init snippet** | **2026-08-29**, tryton-crm session `a0cc0bfb` seq 11781: *"deploy blocker (`account_payment_clearing` missing from the init script)"* | Rediscovered by a step-diff against the superseded plan |
| 6 | The predecessor runbook's **init + RPC-user steps** | **2026-08-11 plan**, `:284` and `:313` | I marked that plan SUPERSEDED and never mined it — dropped both steps |

Row 1 is the sharpest: the exact number (`7200s`) was in a session summary three weeks before I wrote a
plan whose invariant contradicts it.

---

## Defects by surface

### D1 — `/fabrik-deploy`: no infra-wiring floor
`commands/_sources/fabrik-deploy.md`:258-266 makes the exit gate *"the plan's verification battery"* —
whatever the author happened to write. The command names **zero** of the 10 canonical registrars (grep
count 0 for each of netdata/grafana/backrest/prometheus/loki/gatus/traefik/authelia/meilisearch/redis/
postgres across its 336 lines).
**Live consequence:** zitadel deployed through this triad 2026-08-28; its Prometheus target has been DOWN
since 2026-08-29T00:17:04Z (404) with `ServiceUnhealthy` **firing ~2.5 days**. The monitoring worked
perfectly. Nothing in the pipeline asked.

### D2 — `/fabrik-deploy-verify`: probes a different URL than the registrar configures
Hardcodes `curl https://<domain>/metrics`; the registrar scrapes `monitoring.metrics_path`
(`infrastructure.py`:979). `grep metrics_path` in that command = **0 hits**. 1 of 1 specs with a custom
path is mis-verified — and it is the one that broke.
**Real check, hub-side, one line:** `GET prometheus:9090/api/v1/targets` → assert `health=="up"` for
`job=fabrik-<id>`.

### D3 — `/fabrik-deploy-verify`: 5 of 10 registrars declared unverifiable from a vantage it *has*
backrest / grafana / promtail-loki / cadvisor marked "not project-verifiable — informational only";
traefik "implied". The command explicitly runs **hub-side with fleet SSH** (its own § "Where this runs").
Each verified in one command this run: backrest via `docker exec backrest cat /config/config.json`
(7 plans); loki via `/loki/api/v1/label/container_name/values` (26 containers); prometheus via
`/api/v1/targets` (22 targets, 1 down).

### D4 — `fabrik audit-registrars` exists; **no command consumes it**
0 hits across all of `commands/_sources/`. Purpose-built live-vs-spec comparator, already wired to a
metric (`fabrik_audit_drift_total`), an alert rule (`configs/prometheus/rules/fabrik-drift.yml`:13) and a
cron pusher (`scripts/audit_all_registrars.py`). Currently firing drift on `site-provisioner/postgres`
and `zitadel/postgres`.
⚠️ **Caveat that must ride with any fix:** it verifies *config presence*, not function — it reported
`prometheus present` for the very job that 404s. A floor built on it alone still passes zitadel.

### D5 — `/fabrik-deploy-plan`: no supersede contract
Nothing requires a step-level diff against a plan you supersede. Two causes, both command-level:
- **Staleness-axis collapse.** A runbook has two independent axes — WHAT ships (version-sensitive,
  genuinely stale after 295 commits) and HOW it comes up (version-insensitive, still correct). I measured
  the first rigorously and generalised "stale" across both.
- **Distillation loss.** The triad's class list came from a readiness review that kept the init HAZARDS
  ("B2 restart-after-init", "autoheal × init") and dropped the init STEPS — because a human was running
  them. A step a human used to perform is exactly the step an automated runbook must carry.

### D6 — no command teaches rollback-on-failure semantics
My S3 said *"verify: deployment complete"* while its own S3a said *"apply WILL FAIL"*. Nothing catches a
step whose success criterion is unreachable. The consequence was invisible: `_provision_dns` records a
`dns` resource (`orchestrator/__init__.py`:163) → `DeployError` on the `--wait` timeout → handler at
`:213` sees non-empty `created_resources` → `_rollback_dns` (`rollback.py`:186) **deletes the record the
step just created**. `--keep-on-failure` (`cli.py`:420) suppresses exactly this; no deploy command
mentions the flag.

### D7 — no command carries the maintenance-window contract
`fabrik-autoheal` runs **every minute** on vps1. Deploys pause it by touching
`/run/fabrik-autoheal/pause`. Read live (`/usr/local/bin/fabrik-autoheal`:42-48): the guard is
`now - mtime(pause)` and a pause older than **7200s is IGNORED** — `STALE pause file (>2h) ignored —
healing resumes`, logged only to syslog.
Three sub-defects in my own plan, none of which any command would have caught:
1. **Wrong shape of bound** — per-step 90 min cannot guard a cumulative-mtime mechanism. Six consecutive
   20-minute steps each pass and still expire the pause.
2. **No command** — the step said "refresh the pause" and gave none, unlike open and close. The heartbeat
   *is* a `touch`.
3. **Wrong placement** — the single heartbeat sat *after* the run's only operator gate, the one step that
   stalls unboundedly because it waits on a human.
Also: `/run` is tmpfs, so a reboot voids the window silently.

### D8 — the target decision need not name what it costs
`vps-fleet-architecture.md`:211 states plainly that spokes exist as *"independent tenant landing zones"*,
and W4 *"first real tenant on a spoke"* is still pending. This deploy puts a public multitenant CRM on
the **hub**, beside `postgres-main`, the observability HQ, the backup destination and admin ingress.
The placement is **correct** — measured **135 ms** mesh RTT this run, so every trytond ORM query would
cross the Atlantic (20 queries/request ≈ 2.7 s before any work) — but the plan asserted "hub-only infra"
qualitatively and never named the blast-radius concession it bought.

### D9 — "ground against the infra docs" is not enforceable as written, and I proved it
I ran `/fabrik-deploy-plan-review` **to a converged no-op** having only *grepped* `docs/infrastructure/`
— 5,532 lines across 14 files, of which I had actually read one partial section. The review converged
anyway. Only when the operator repeated the instruction verbatim did I read
`vps-fleet-architecture.md` end-to-end and immediately find D7 and D8.
**A grep answers a question you already thought to ask; the canonical doc tells you which questions
exist.** Nothing detects a converged review that cites zero lines from the architecture doc.

### D10 — evidence-method traps (near-misses, recorded so they are not re-walked)
- **A oneshot systemd unit is invisible to `--state=running`.** I nearly filed "boot units missing
  fleet-wide"; `fabrik-compose-boot`, `iptables-docker-user`, `iptables-openvpn` are all oneshots and
  correctly absent. `systemctl is-enabled` is the real check — all enabled on all 3 hosts.
- **A transient SSH failure reads exactly like a finding.** An `audit-registrars` run mid-session
  returned `unknown` across the board (`kex_exchange_identification: Connection reset` — I had been
  hammering the host); a clean re-run gave entirely different verdicts.
Both are the same family as the truncated-pipe and case-sensitivity traps already in the corpus: **the
probe's own semantics decided the answer, not the fleet's state.**

---

## Rule-pack defects (root, and why they were invisible)

### R1 — `60-watchdog.md` described a discipline as if it were behavior
Its "When to enable" matrix claimed a shape-driven default (`python-api`/`node-api` conditional on
`is_admin_dashboard` OR `has_persistent_data`; static off). **The resolver never implemented any of it** —
`resolve_applicability` is a one-line unconditional `watchdog_cfg.get("enabled", True)` with no `kind`
test, and its own comment says the matrix *"is operator discipline … not encoded here"*
(`infrastructure.py`:328-329).
**The class: a rule-pack table that reads like behavior but is actually discipline is invisible drift —
nothing fails when they disagree.** Retired under D-052.

### R2 — `30-ops.md`'s Deployment Checklist verifies FORM only
Every one of its ~19 items is a **static file property** — base image, memory limits, Traefik labels, no
`ports:` section, `.dockerignore` present. Not one asks whether the service works when it comes up or
whether the infrastructure it claims is actually attached. That is why none of D1-D8 could ever have been
caught by it. **A `shape:` flag is a claim about RUNTIME, and the registrar believes it.**

---

## The systemic class

**The pipeline verifies that a declaration EXISTS, never that it is TRUE.**

- At **deploy** time: that a registrar RAN, not that what it produced works (D1-D4).
  `_provision_prometheus` swallows failures as non-fatal (`infrastructure.py`:1001-1002),
  `add_scrape_target` means only "job appended to file", and `fabrik apply` reports success — so a
  permanently-404 target is indistinguishable from a healthy one at every layer the pipeline reads.
- At **spec** time: that a flag is DECLARED, not that the runtime honours it (R2).
- In a **runbook**: that a step was WRITTEN, not that its bound matches the mechanism it guards (D7) or
  that its success criterion is reachable (D6).
- In a **review**: that a pass CONVERGED, not that the pass read anything (D9).

And the meta-layer, which is the reason this report exists: **knowledge accumulates in transcripts and
review reports, not in commands** — so it is re-derived per deploy, by whoever happens to look, or lost.

---

## Disposition

**Fixed in this repo (fleet beat), pushed:**

| Commit | What |
|---|---|
| `b6133f6a` | `audit_backrest` matched a plan id no registrar creates (`{name}-data`) — backrest could **never** report `present` for any service. A structural false-MISSING on the *backup* registrar |
| `8b4738a6` | A backrest plan pointed at a non-existent path now reports `drift`. `_provision_backrest` hardcodes `/opt/<name>/data` regardless of where data lives → PAPER BACKUP. Live: `/opt/zitadel/data` absent while `zitadel-data` points at it. Routed through the existing drift metric → `FabrikRegistrarDrift` |
| `c256e3e3` | D-052: every project gets a watchdog — 15 real specs flipped |
| `6dec1619` | `30-ops.md` § **Deployment Completeness** (8 classes settled at SPEC time); `60-watchdog.md` matrix retired (R1) |
| `c89240f7` | Plan: window heartbeat contract (D7), Phase 1 concession + measured RTT (D8) |
| `a69682da` | Plan: S3 `--keep-on-failure` + reachable verify (D6); infra-utilization matrix |

**Routed to infra (their beat, their open manifesto pass), mail `01M1BTY6M1F88BTX6YG975CMRV`:**
D1-D10 as command-corpus changes, plus ~8 orchestrator/command sites whose watchdog opt-out language is
stale under D-052 (strongest: `epic-to-ticket-workflow/01-decisions-lock-fabrik.md`:122, which offers
`accept-defaults/raise/opt-out` at the exact moment a project locks its decisions).

**Open operator decisions:**
1. Gate 2 — `/fabrik-deploy` for tryton-crm.
2. zitadel's firing alert: needs `ZITADEL_METRICS_TYPE=otel` + a redeploy of the live IdP, or
   `exposes_metrics: false` and drop the scrape job. Recommended: the former.

---

## What would actually stop the recurrence

Ranked by leverage, all cheap:

1. **An infra floor `/fabrik-deploy` cannot skip** — `fabrik audit-registrars --json --spec <spec>` with
   no `missing`/`drift` row, **plus** the live prometheus target-health assertion (D4's caveat: the audit
   alone still passes zitadel).
2. **A deploy-knowledge surface commands can cite.** `30-ops.md` § Deployment Completeness is that
   surface and is sized to be referenced rather than restated; the six rediscovered facts in the headline
   table belong there, not in transcripts. This is the single change that addresses the meta-class.
3. **A supersede step-diff** in `/fabrik-deploy-plan` (D5) — each dropped step retired with evidence or
   carried.
4. **A grounding assertion with a named FILE** (D9) — a converged deploy review that cites zero lines
   from `vps-fleet-architecture.md` has not grounded.
