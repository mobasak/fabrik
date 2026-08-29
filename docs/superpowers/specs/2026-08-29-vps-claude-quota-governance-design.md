# Design spec — VPS single-key Claude quota governance (ob@ocoron.com)

Status: CONVERGED
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

### Mechanism A — one host claude on ob@, a TWO-TIER broker (no creds + no operator shell for containers)

The credential stays on the host; but a container calling "the host's claude" must NEVER get the operator's
full-tool shell — that is a container→host confused-deputy (a compromised container would run
`{prompt:"exfil ~/.ssh", tools:[bash]}` as the operator). So the broker exposes exactly two tiers, and the
privileged tier is unreachable from a container:

- **Tier 1 — the HOST sysadmin loop (full tools, operator).** `claude-run.sh` stays the single host entrypoint
  (runs as operator, one cred home, set to ob@; the rotation swap is a no-op with one account, but
  `is_usage_limit` detection stays live for Mechanism D). Only HOST processes (the healer, host crons) invoke
  it. It is **never bound to a socket a container can reach.**
- **Tier 2 — the container broker (COMPLETION-ONLY, no host tools).** A small stdlib loopback service bound to
  the Docker bridge gateway (or a per-container bind-mounted unix socket) accepts a job `{prompt, model?}` and
  runs `claude -p` **with an EMPTY tool allowlist (`--allowedTools ""` / no bash/edit/MCP)** — pure
  prompt→completion, subscription-billed on ob@, with **no filesystem, shell, or network tool access**. A
  container gets an LLM answer, never an operator shell. Controls, all mandatory: **(a) per-caller
  authentication** — a per-container shared token (issued at deploy, not IP — every container is on the bridge
  subnet, so an IP allowlist authorizes the exact threat it should exclude); **(b) per-caller quota budget**
  (F4) so one misbehaving container cannot drain ob@ — tracked in a **state store** (`redis-main`, a counter
  per caller keyed to the ob@ window), decremented per job and **reset on the 5-hour + weekly window
  boundaries** (so it maps to the real caps); a restarted broker recovers the counters from the store, never
  forgets them. A caller over budget is refused (or downgraded to pool) — the budget is a mechanism, not a
  label; **(c) an audit line per job** (caller, prompt hash,
  tokens); **(d) the class is assigned by the broker from the caller identity, never self-labelled** — a
  container's work is `routine` by construction, so it is always poolable/sheddable (Mechanism C/D).
- **Containers hold NO credentials** — preferred over mounting `~/.claude/.credentials.json` because mounting
  scatters the secret across N containers and hits the live unresolved persistence bug (anthropics/claude-code
  #22066: OAuth re-prompts despite mounted creds) + token-refresh-clobber + machine-binding gotchas (grounded
  below).
- The broker is loopback/bridge-gateway-bound only — no Traefik route, no public host `ports:`. **A container
  never reaches Tier 1**; the only host-tool claude runs are host-initiated (the sysadmin loop).

### Mechanism B — event-driven triggering, and the fix always runs

**The ob@ (incident) path is event-driven**, so ob@'s quota tracks the incident rate (rare), not a poll
cadence: the fleet already has an event-driven trigger surface — the fabrik-lib **watchdog sidecar** ingests
GlitchTip errors on `:8889` (its ingest server + trigger bus, e.g. `test_ingest_server.py` /
`test_trigger_error_tracker_webhook.py`); the healer runs on an actual incident. Scheduled consumers
(the cron digests/audits below) DO exist and DO run on a cadence (F5) — but they are all **pool-routed**
(Mechanism C), so they never load ob@'s cap. Only the event-driven incident path spends ob@; a polling bot
on ob@ is exactly the anti-pattern this split avoids. **But when an issue
fires it MUST be handled** (I3). The governor (D) never blocks an incident on ob@ — but the honest invariant
is **"an incident is never DROPPED,"** NOT "always auto-fixed," because a live-host fix (restart a container,
tail a live log, edit a prod config) needs Claude Code's real tool loop on the host, which ONLY ob@ can do:
the OpenRouter pool runs its workers in a **bwrap sandbox** (`libs/subagents/sandbox.py` — `--unshare-net`,
read-only host bind, throwaway git worktree, edits captured as a diff) and **structurally cannot** touch the
live host. So the incident path is: **ob@ has headroom → autonomous fix on ob@** (the normal case, kept normal
by the reserve in D); **ob@ exhausted → the pool DIAGNOSES read-only** (propose the fix from a
context bundle) **+ Telegram the operator with that proposal for a gated apply** — the incident is escalated
with a ready diagnosis, never silently dropped. **A sandboxed pool worker has no network + a read-only host
bind, so it cannot gather live context itself (F3) — a HOST-side marshaller (a plain script, NOT the capped
claude) assembles the context bundle** — the trigger payload (the GlitchTip webhook that fired the incident)
+ the relevant `docker logs`/`journalctl` tails + a `docker ps`/state snapshot — **into the worker's worktree
BEFORE dispatch**; the pool then reasons over that bundle. Without the marshaller the pool can diagnose
nothing, so it is a named build step, not an afterthought. Autonomous fixing degrades to human-gated exactly when quota
is scarce; the design's real job is to make ob@-exhaustion-during-an-incident RARE (the reserve + pool-offload
+ retiring the keepalive ping), not to pretend a sandboxed model can fix a live host.

### Mechanism C — pool-offload the bulk, reserve ob@ for the fix

All **routine/triage** LLM work goes to the metered OpenRouter pool (`libs/subagents` `fanout` /
`pick_models`, no default price cap): classify an error, "is this a real error", summarize logs, kaizen
digests, doc-summarization. Only when triage concludes "this needs a real multi-tool Claude Code fix
session" does it spend ob@'s subscription quota. With one account we push MORE to the pool than the old
3-account plan did — ob@'s quota is thereby mostly *reserved* for incident-fixing.

**The full ob@-consumer inventory (F5) — every one routes through the governor, no exceptions.** Enumerate the
live box consumers so nothing spends ob@ unrouted: `bot.py` (watchdog/healer), the kaizen crons
(`kaizen_*.py`), `weekly_catchup.sh`, `morning-report.sh` / `daily-digest.sh` / `weekly-security.sh`,
`proactive-check.sh`, `canary_grounding.py`, `ci_health_probe.py`, the daily VPS-docs pipeline's LLM steps,
plus every container job via the broker. Most are `routine` and go to the pool — only a genuine
watchdog/healer incident spends ob@. **But "routine" is NOT automatically "poolable" (F6):** a consumer whose
LLM step is **pure reasoning over host-gathered text** (the script gathers via bash, the LLM only reasons)
pools cleanly; a consumer whose LLM step needs Claude Code's **host tool loop** (a live scan, a proactive
remediation — `proactive-check.sh` / `weekly-security.sh` are the suspects) **cannot** run in the net-isolated
read-only sandbox and would be starved if blindly pooled. So each inventory row gets a plan-time verdict —
**pure-reasoning → pool · needs-host-tools → runs on ob@ as low-priority routine** (governed + sheddable to a
proposal, never blindly pooled). The blanket "all routine → pool" is replaced by this per-row verdict. **Retire the keepalive ping under single-key:** `claude-keepalive-rotate.sh`
runs `claude -p ping` to keep OAuth tokens warm — that earned its keep under multi-account WSL rotation, but on
a single, regularly-USED ob@ it just burns the 5h/weekly quota this design is conserving, for zero rotation
benefit. Drop the ob@ ping (a normally-used account needs no keepalive); if a warmth signal is ever wanted,
use the free `oauth/usage` telemetry probe (Mechanism D), never a billed message.

### Mechanism D — the quota governor: a headroom-aware router, never a per-call cap

A thin router in front of `claude-run.sh` (host) and the broker (containers). It combines **proactive** and
**reactive** headroom signals, and — the key protection — it **reserves ob@ quota for incidents**:

- **Class is assigned SERVER-SIDE from the trigger source, never self-labelled (F4).** An incident is a
  watchdog/healer event (a real fault); routine is a cron digest / a container completion / a kaizen summary.
  The governor derives the class from *which trigger fired*, so a caller (a container via the broker) cannot
  relabel its work `incident` to skip shedding. Every container job is `routine` by construction; each broker
  caller also carries a per-caller quota budget so one container cannot drain ob@.
- **The incident reserve — the real mechanism that keeps the fix on ob@ — spans ALL THREE cap windows (F1).**
  ob@ has a **5-hour rolling** cap AND a **7-day weekly** cap (both apply) plus a **separately-tracked
  Opus-weekly** sub-limit; the fix loop consumes all three. So the reserve holds back headroom on EACH: the
  governor sheds routine to the pool whenever **ANY** window crosses its reserve threshold —
  `max(five_hour.utilization, seven_day.utilization, opus_weekly.utilization)` ≥ the reserve (default ≈80%).
  A weekly-only reserve is the trap: weekly could sit at 40% while a routine burst fills the **5-hour** window,
  5h-capping ob@ exactly when an incident fires. Reserving on the 5h window (the short, fast-filling one) is
  the load-bearing half — the 5h reset slides, so it recovers fast, but only if routine stops feeding it.
- **Proactive:** before a *routine* ob@ call, read `claude_rotate.py --status --json` → ob@'s
  `five_hour.utilization` + `seven_day.utilization` (+ the Opus-weekly figure); if the MAX across windows is
  above the reserve threshold, route routine **pool-only** or defer past the (nearest) reset — every window's
  utilization is a live input, none is fetched-and-discarded. **This status read does NOT spend message
  quota** — it hits the `oauth/usage` + `oauth/profile` telemetry endpoints (`claude_rotate.py`), not the
  messages API, so the governor's own headroom probe is free.
- **Reactive:** if any ob@ call returns an `is_usage_limit` signal, mark ob@ capped until its reset and route
  subsequent routine work to the pool; an incident in that state escalates via the pool-diagnosis +
  operator-gated-apply path (Mechanism B) — never a de-facto per-call cap on the fix, and never dropped.
- **The governor NEVER blocks an incident** (honoring the no-per-call-cap rule) — it only sheds/offloads
  *routine* work when quota is scarce.
- **Single-flight fix loop (F2).** The ob@ fix path takes a lock — concurrent incidents SERIALIZE (a bounded
  incident queue), so the reserve only ever needs headroom for ONE live fix at a time; a second incident
  waits its turn (or, if ob@ is exhausted by the first, escalates via the pool-diagnosis path). Two racing
  Opus fix loops are exactly what tips the 5h/Opus window, so serializing is also what keeps the reserve math
  (one-fix's-worth) valid.
- **Degraded / unknown-headroom is fail-SAFE (F7).** If the `--status` probe fails (telemetry 5xx, timeout,
  parse error) or the governor process is unavailable, the default is **routine → pool** (unknown headroom is
  treated as "no reserve left" — never risk the cap) and **incident → still tries ob@** (never-block).
  Consumers reach ob@ ONLY through the governor — `claude-run.sh`/the broker refuse a call that did not come
  through it — so a down governor degrades to pool-for-routine, never a silent bypass that floods ob@.
- **Alert:** Telegram the operator on any reserve-threshold or cap crossing via the proven
  `claude-sound.sh mesh-notify` transport (no new alerting machinery).
- Utilization is read **live** — never hardcoded caps — because Anthropic does not publish the numeric caps
  (only per-account Settings → Usage; grounded); the governor keys on the live `utilization` %.

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
- **A broker that runs the operator's FULL-tool claude on caller-supplied tools.** Rejected — a
  confused-deputy: a compromised container would get host RCE + secret exfil as the operator. The broker's
  container tier is completion-only (empty tool allowlist, per-caller auth + budget + audit); the full-tool
  operator claude is host-initiated only and never reachable from a container (Mechanism A).
- **"The pool autonomously fixes the incident when ob@ is capped."** Rejected — `libs/subagents` workers run
  in a bwrap sandbox (no network, read-only host, throwaway worktree) and structurally cannot touch the live
  host. The capped-incident path is pool read-only diagnosis + an operator-gated apply, not an autonomous
  sandboxed fix (Mechanism B).

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
| The metered LLM pool (routine offload + capped-incident diagnosis) | **VENDOR — `libs/subagents`** | `fanout`/`pick_models` for routine; a **read-only diagnosis** pass when ob@ is capped (the sandboxed worker cannot fix a live host — Mechanism B), never an autonomous fix |
| Operator alert transport | **VENDOR — `claude-sound.sh mesh-notify`** | Telegram, proven; no new alerting |
| The **completion-only container broker** (containers → host claude, no creds, no host tools) | **BUILD** (small, justified) | No documented standard exists; a stdlib loopback/socket service, `claude -p` with an EMPTY tool allowlist + per-caller token/budget/audit. `🆕 fabrik-lib candidate`? NO — VPS-fleet-specific glue, not generic |
| The **governor router** (server-side class + reserve + proactive/reactive routing + never-dropped invariant) | **BUILD** (small, justified) | Thin decision layer over the reused status/limit/pool primitives; sysadmin-specific |

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

**Resolved (first review):** the docker-creds gotchas → two-tier host-broker; the broker confused-deputy →
container tier completion-only + per-caller auth/budget/audit, full-tool claude host-only; the capped-incident
path → pool read-only diagnosis + operator-gated apply; the class authority → server-side from the trigger;
the consumer inventory + keepalive-ping retirement; the reuse surface.

**Resolved (second review — these were design-level, not tuning):** the **cap model spans THREE windows**
(5h-rolling + 7-day-weekly + Opus-weekly) and the reserve sheds on `max(utilization)` across all of them (F1 —
the 5h window is no longer a read-but-unused signal); the **pool-diagnosis context is marshalled by a
HOST-side script** (trigger payload + log tails + state snapshot into the worktree before dispatch) since the
sandboxed worker cannot gather it (F3); the **fix loop is single-flight** so concurrent incidents serialize
and the one-fix reserve holds (F2); **degraded/unknown-headroom fails SAFE** (routine→pool, incident→ob@; no
governor bypass) (F7); the **per-caller budget has a `redis-main` counter reset on the 5h+weekly boundaries**
(F4); **"routine" ≠ "poolable"** — each consumer gets a pure-reasoning-vs-needs-host-tools verdict (F6).

**Still-open (each genuinely a plan-time tuning/wiring choice, none a design fork):**
- **The exact reserve/shed threshold %** — default ≈80% weekly utilization; tune from the live board.
- **Broker transport: loopback HTTP on the bridge gateway vs a bind-mounted unix socket** — decide at plan time
  from which container runtimes need it; both keep the secret on the host.
- **The broker's per-caller token issuance mechanism** (how a container gets its token at deploy) — resolution:
  inject at `fabrik apply` time as a per-service env secret, grounded at plan time against the deploy path.
