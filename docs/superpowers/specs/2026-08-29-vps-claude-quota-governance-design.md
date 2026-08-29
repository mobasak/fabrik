# Design spec — VPS single-key Claude quota governance (ob@ocoron.com)

Status: DRAFT
Date: 2026-08-29 · Owner: fleet

## Goal

Run the whole VPS fleet's Claude usage through **one system-wide Claude Code install authenticated as a
single account (`ob@ocoron.com`)** — every consumer, host cron AND Docker container — and keep that one
account under its Claude Max usage caps **without ever capping the sysadmin fix loop**. The binding
constraint is subscription **quota**, not dollars; a per-call budget cap is banned because it breaks the
diagnose loop. So we cap *demand on the subscription*, not the work: offload routine LLM work to the metered
OpenRouter pool, reserve ob@ for the real fix session, and add a headroom-aware router that degrades
gracefully to the pool instead of failing when the cap is near.

## Intake Inventory

| I# | Item (operator's words) | Disposition | Where |
|---|---|---|---|
| I1 | "all claude consuming items **including inside dockers**, should use the system wide installed claude code over ob account" | IN | Mechanism A |
| I2 | containers reach the host's claude, don't each hold ob@ creds (prefer host-exec) | IN | Mechanism A (the broker) |
| I3 | "agreed but **if there is an issue, it must be fixed**, what do you suggest?" | IN | Mechanism B + D (fix-always) |
| I4 | pool-offload the bulk — "3 ok good" | IN | Mechanism C |
| I5 | "ok but **will we rotate in the vps systems too?**" | IN | Mechanism D (answer: no account rotation — mode fallback) |
| I6 | Claude Code CLI + OAuth only (never `ANTHROPIC_API_KEY`); no per-call $ cap on the sysadmin loop; quota is the binding constraint | IN | Constraints |
| I7 | WSL dev box keeps its own can@/sarp@/mob@ rotation | OUT-OF-SCOPE — unchanged; this spec is VPS-only. `claude_rotate.py` multi-account rotation stays for WSL. | Constraints |

Intake: 7 items — 6 IN, 1 OUT-OF-SCOPE (named), 0 ASK.

## Chosen approach — host-broker + pool-offload + a reactive+proactive headroom governor

The fleet ALREADY has the hard parts. `scripts/sysadmin/claude-run.sh` is a unified host entrypoint that runs
`claude` as the operator user against the one credential home (`/home/ozgur/.claude`); `claude_rotate.py`
detects usage-limit signals (`is_usage_limit`) AND exposes live per-account headroom
(`--status --json` → `five_hour.utilization` + `seven_day.utilization` + resets); `quota_dashboard.py` renders
it. So this design is mostly **vendor+enhance of existing sysadmin machinery + a thin broker + a router**,
not new infrastructure.

### Mechanism A — one host claude, a broker containers call (no creds in containers)

- **Host:** keep `claude-run.sh` as the single entrypoint (runs as operator, one cred home). For the
  single-key model set it to ob@ (the rotation swap becomes a no-op with one account, but `is_usage_limit`
  detection stays live for the fallback — Mechanism D).
- **Containers:** a **host-side broker** — a small stdlib loopback service bound to the Docker bridge gateway
  (e.g. `172.17.0.1:<port>`, or a unix socket bind-mounted read-only) that accepts a job `{prompt, cwd,
  tools?}` and runs it through `claude-run.sh` on the host, returning the result. **Containers hold NO
  credentials** — the one ob@ credential never leaves the host. This is preferred over mounting
  `~/.claude/.credentials.json` into each container because (a) mounting scatters the secret across N
  containers, and (b) the mount path has a live unresolved persistence bug (anthropics/claude-code #22066:
  OAuth re-prompts in containers despite mounted creds) + token-refresh-clobber + machine-binding gotchas
  (grounded below). The broker also naturally routes every container job through the SAME governor + pool
  fallback as host jobs.
- The broker is IP-allowlisted to the Docker bridge subnet + loopback only; it is NOT a public port (no
  Traefik route, no host `ports:` beyond the bridge-gateway bind). It runs `claude` with the caller's
  requested tools; a container gets exactly the sysadmin scope the host would give it.

### Mechanism B — event-driven triggering, and the fix always runs

Consumers fire on **real events**, not polling: the watchdog already ingests GlitchTip errors on `:8889`
(`agent.py _IngestHandler`); the healer runs on an actual incident. Quota then tracks the incident rate
(rare), not a poll cadence — a polling bot on one account is what burns a weekly cap. **But when an issue
fires it MUST be fixed** (I3): the governor (D) never blocks an incident fix — it runs on ob@ if there is
headroom, and if ob@ is exhausted it **falls the fix over to a tools-enabled OpenRouter pool agent**
(`libs/subagents`, `tools_enabled=True`) so the incident is never dropped because a subscription cap was hit.

### Mechanism C — pool-offload the bulk, reserve ob@ for the fix

All **routine/triage** LLM work goes to the metered OpenRouter pool (`libs/subagents` `fanout` /
`pick_models`, no default price cap): classify an error, "is this a real error", summarize logs, kaizen
digests, doc-summarization. Only when triage concludes "this needs a real multi-tool Claude Code fix
session" does it spend ob@'s subscription quota. With one account we push MORE to the pool than the old
3-account plan did — ob@'s quota is thereby mostly *reserved* for incident-fixing.

### Mechanism D — the quota governor: a headroom-aware router, never a per-call cap

A thin router in front of `claude-run.sh` (host) and the broker (containers). It combines **proactive** and
**reactive** headroom signals:

- **Proactive:** before a *routine* ob@ call, read `claude_rotate.py --status --json` → ob@'s
  `five_hour.utilization` + `seven_day.utilization`. If weekly headroom is below a threshold (the weekly is
  the binding cap — grounded), route routine work **pool-only** or defer it past the reset.
- **Reactive:** if any ob@ call returns an `is_usage_limit` signal, mark ob@ capped until its reset and route
  subsequent work to the pool (routine) or the pool-fix fallback (incident).
- **Invariant:** an **incident fix ALWAYS runs** — ob@ if it has headroom, else the tools-enabled pool agent,
  else an operator alert. The governor NEVER blocks urgent work (honoring the no-per-call-cap rule); it only
  sheds/offloads the non-urgent when quota is scarce.
- **Alert:** Telegram the operator on any cap-threshold crossing via the proven `claude-sound.sh mesh-notify`
  transport (no new alerting machinery).
- The utilization values are read **live** — never hardcoded caps — because Anthropic does not publish the
  numeric caps (only per-account Settings → Usage); the governor keys on the live `utilization` % the status
  probe already returns.

**No account rotation on the VPS (I5 answered).** Single-key means there is no second account to rotate *to*
on the box. The only "rotation" is the **mode fallback**: ob@ subscription → OpenRouter pool. The WSL dev box
keeps its own can@/sarp@/mob@ account rotation (`claude_rotate.py`, out of scope).

## Rejected alternatives

- **Mount `~/.claude/.credentials.json` into every container.** Works in practice but scatters the one secret
  across N containers and inherits the live unresolved persistence bug (#22066) + refresh-clobber +
  machine-binding gotchas. Rejected in favor of the host-broker (secret stays on the host, one place).
- **A second hot-spare account on the VPS (account rotation).** Contradicts the operator's single-key
  decision; the pool is the failover instead.
- **`ANTHROPIC_API_KEY` for the container/headless path** (Anthropic's own headless guidance). Rejected — it
  bills the API, not the Max subscription, the opposite of the goal (I6).
- **Hardcoded cap numbers + a fixed per-call budget.** Rejected — the caps aren't published (read live %), and
  a per-call cap breaks the diagnose loop (banned).
- **A predictive-only OR reactive-only governor.** Rejected — combine both: proactive shedding for routine +
  reactive fallback on a real limit signal.

## External dependencies (grounded live 2026-08-29)

- **Claude Max usage limits** — a **5-hour rolling session limit** AND a **7-day weekly limit** apply
  simultaneously; the 5-hour window slides (resets 5h after it begins), the weekly resets on a **fixed
  per-account cadence**. **There is no separate "daily" cap** — the short window IS the 5-hour session. Opus
  has its own separately-tracked weekly sub-limit. **Exact numeric caps are NOT published** — visible only
  per-account in Settings → Usage, so the governor must read live utilization, not hardcode caps. Source:
  https://support.claude.com/en/articles/11049741-what-is-the-max-plan +
  https://support.claude.com/en/articles/9797557-usage-limit-best-practices (fetched 2026-08-29). This matches
  the fleet's existing `five_hour` + `seven_day` model (`claude_rotate.py`).
- **Claude Code CLI in Docker** — mounting the host OAuth credential into a container is a *community* pattern
  that works but is not officially blessed and carries live gotchas: token-refresh clobbering, a persistence
  bug (anthropics/claude-code **#22066**, closed-as-duplicate = acknowledged) where the CLI re-prompts despite
  mounted creds, and machine/keychain binding. There is **no documented standard host-broker pattern** — the
  broker in Mechanism A is a bespoke build, but it aligns with the fleet's existing host-side dispatcher
  (`claude-run.sh`, `claude_rotate.py`) better than scattering creds. Sources:
  https://github.com/anthropics/claude-code/issues/22066 · https://foldr.uk/claude-code-pro-subscription-docker/
  · https://github.com/cabinlab/claude-code-sdk-docker/blob/main/docs/AUTHENTICATION.md (fetched 2026-08-29).

## fabrik-lib / reuse verdict

| Capability | Verdict | Why |
|---|---|---|
| Unified host claude entrypoint (run as operator, one cred home) | **VENDOR (reuse) — `claude-run.sh`** | Already the drop-in `claude` wrapper; set to ob@ single-key |
| Usage-limit signal detection (reactive) | **VENDOR — `claude_rotate.py::is_usage_limit`** | Regex covers weekly/session/5h/"out of extra usage" |
| Live per-account headroom (proactive) | **VENDOR — `claude_rotate.py --status --json`** | Returns `five_hour`/`seven_day` utilization + resets; the governor's proactive input |
| Operator-facing quota board | **VENDOR+ENHANCE — `quota_dashboard.py`** | Add an ob@-VPS panel + the governor's current routing mode |
| The metered LLM pool (offload + fix fallback) | **VENDOR — `libs/subagents`** | `fanout`/`pick_models` for routine; `tools_enabled=True` agent for the pool-fix fallback |
| Operator alert transport | **VENDOR — `claude-sound.sh mesh-notify`** | Telegram, proven; no new alerting |
| The **host broker** (containers → host claude) | **BUILD** (small, justified) | No documented standard exists; a stdlib loopback/socket service on the bridge gateway. `🆕 fabrik-lib candidate`? NO — VPS-fleet-specific glue, not generic |
| The **governor router** (proactive+reactive routing + fix-always invariant) | **BUILD** (small, justified) | Thin decision layer over the reused status/limit/pool primitives; sysadmin-specific |

No new fabrik-lib module proposed — the two builds are fleet-specific sysadmin glue over reused primitives.

## Shape / infra implications

- **Not a scaffold type / not a deployed Docker service of its own** — this is **box-local sysadmin tooling**
  under `scripts/sysadmin/` (host crons + one small broker process), the same class as `claude_rotate.py` /
  `quota_dashboard.py`. Documented in `docs/workstation/` (box-local), not a project `docs/reference/`.
- The broker binds the Docker **bridge gateway** loopback only (allowlisted to the bridge subnet + `127.0.0.1`)
  — no Traefik route, no public host `ports:`.
- No DB, no new deployed service. Config via env (`CLAUDE_OPERATOR_USER`, broker port, headroom thresholds).

## Constraints

- Claude Code CLI + subscription OAuth only for the fix loop; **never `ANTHROPIC_API_KEY`** on the operational
  path (I6, `feedback_claude_code_not_api`).
- **No per-call $ budget cap** on the sysadmin loop (`feedback_no_budget_caps_sysadmin`) — the governor sheds
  demand, it never caps the fix.
- One credential stays on the host; containers never hold ob@ creds.
- The fix is never dropped because a subscription cap was hit — it falls over to the pool.

## Open / blocking unknowns

**Resolved:** the cap model (5h + weekly, no daily, numbers unpublished → read live %); the docker-creds
gotchas → host-broker chosen; the reuse surface (claude-run/claude_rotate/quota_dashboard/subagents).

**Still-open (each with a resolution step, none blocking the design):**
- **The exact headroom threshold %** at which routine work sheds to the pool — resolution: pick a conservative
  default (e.g. shed routine at ≥80% weekly utilization), tune from the live board; a config knob, not a
  design fork.
- **Broker transport: loopback HTTP on the bridge gateway vs a bind-mounted unix socket** — resolution: decide
  at plan time from which container runtimes need it (a socket is tighter but needs a per-container mount; a
  gateway-bound loopback port is simpler for many containers). Both keep the secret on the host; the choice
  doesn't change the design.
- **Whether the tools-enabled pool-fix fallback needs a scoped tool allowlist** (a pool model running bash on
  the VPS) — resolution: constrain the fallback agent to read-only diagnosis + a proposal by default, escalate
  to an operator-gated write; grounded at plan time against `libs/subagents` capabilities.
