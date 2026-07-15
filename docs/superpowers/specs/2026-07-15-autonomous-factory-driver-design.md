# Autonomous Factory Driver (D3 / R8) — Design Spec

**Status:** CONVERGED · **Date:** 2026-07-15 · **Owner:** operator
**Convergence (`/fabrik-spec-review`):** Pass 1 — 2 edits (split the over-claimed converger vendor row into `fanout`=VENDOR / the loop=BUILD; added the north-star row-map). Pass 2 — **0 edits, md5 `dfd9550a0329` stable** → the fixed point. External facts re-verified live this session (`claude -p` headless behaviour; Fable 5 $10/$50 metered-since-07-07; Opus $5/$25). Vendor verdict audited against the real modules (`job-queue` provides SKIP-LOCKED + fork + hard-timeout + crash-detect + autoscale + SIGTERM-requeue; `db-pool`/`alerting` confirmed; `fanout` is a single dispatch, so the converge-loop is BUILD not vendor). Axis-E constraint audit clean (no Stripe/Pinecone/Supabase/Alpine/direct-SDK; 12-Factor IX/IV/XI satisfied; cost-budget present).
**North star:** [`docs/traycer/00-autonomous-factory-north-star.md`](../../traycer/00-autonomous-factory-north-star.md) — **this spec is the design for the north star's single largest open gap.** It directly fulfils, and on ship flips to DONE, these rows of that doc:

| North-star item | What it says | This spec |
|---|---|---|
| **R2** | 24/7 unattended, headless; survives sleep/reboot | the queue worker + `Persistent` service |
| **R3** | 50 concurrent projects = queue depth, drained continuously | `jobs` table + `autoscale.py` bounds |
| **R8** | Control flow in **code, not prose** — the driver runs the loops and calls `fanout` itself | the **converger BUILD** (loop around `fanout`) |
| **D3** | Driver = vendor `job-queue` + 2 `process_fn` handlers + transitions + Telegram digest + `fabrik factory` CLI | the entire § Chosen approach |
| **D4** | The converger is executed **by the driver, in code** — not by asking an agent to loop | the converger handler |
| **R13** | subscription + pool; no compute rental | Opus-default (subscription) / Fable-opt-in / pool breadth |

Scope decided with the operator: **the whole driver**, not a harness fragment — because D4 makes the fan-out converger *a driver responsibility*, so a harness-only spec would fragment one system. **On completion, update those north-star rows from OPEN → DONE** (and this spec becomes the reference for how).

---

## Goal

A **PostgreSQL-queue-driven state machine** that runs the Fabrik lifecycle (`/fabrik-*` commands) **autonomously, 24/7**, draining a queue of `(project, stage)` jobs — so the operator stops being the loop. Two human gates only: **plan approval in**, **deploy approval out**. Everything between — spec, data-contract, ui-design, plan, execute, review, docs — runs without a human, with the review/converge loops executed **in code** (not as a prose instruction an agent may skip).

**What "done" looks like:** the operator drops a vision into a project, approves the plan when the digest pings, approves the deploy when the digest pings, and the factory does the rest — reviewing to a no-op, updating docs, recording the flywheel — across many projects concurrently, surviving sleep/reboot.

---

## Scope

**IN (this spec):** the driver — queue schema, the worker loop, the stage→handler transitions, the two `process_fn` handlers (producer + converger), the human-gate stops, the Telegram digest, and a thin `fabrik factory` CLI.

**OUT (explicitly):**
- The `/fabrik-*` commands themselves — they exist (R10 DONE); the driver *runs* them. (Their convergence is the separate ettw-review work.)
- The subagent **policy** — `.windsurf/rules/core/62-using-subagents.md` is binding and INHERITED verbatim (two runtimes, dispatch policy, parallelism shapes, model tiers). This spec does not re-derive it.
- The pool **machinery** — `fanout`/telemetry/tool-parity/enforcement are DONE (3 converged specs + shipped). The driver *calls* `fanout`; it does not rebuild it.

---

## Chosen approach — queue state-machine, vendored core, `claude -p` producers, in-code `fanout` convergers

The lifecycle is a DAG of **stages**; each `(project, stage)` is a **job** row. A vendored `job-queue` worker claims jobs (`SELECT … FOR UPDATE SKIP LOCKED`), and a single `process_fn` dispatches by stage kind:

| Stage kind | Handler | Mechanism |
|---|---|---|
| **Producer** (spec · data-contract · ui-design · plan · execute · docs-author) | spawn `claude -p "/fabrik-<stage>"` in an **isolated git worktree**, model **Opus 4.8**, `--output-format json` (captures `result` + `total_cost_usd` for the budget), `--permission-mode` for unattended | grounded below |
| **Converger** (review · docs-review · plan-review · spec-review) | run the **in-code `fanout` loop** to a no-op — the driver owns the loop (D4), not an agent's prose | `libs/subagents.fanout` |
| **Human gate** (plan-approval IN · deploy-approval OUT) | mark job `awaiting-owner`, emit a **Telegram digest**, stop. Owner replies → job transitions | `fabrik-lib/alerting` |

A **transitions table** (`stage → next_stage`, with the human-gate stops) is the only project-specific control flow. `autoscale.py` (cgroup-aware) bounds concurrent workers to the box — the R3 capacity concern, **already solved in the vendored module**. On SIGTERM, `poll_worker` requeues the in-flight job (12-Factor IX) — already handled.

**Why this is the lean/pro-grade choice (cited best-practice):** a Postgres-`SKIP LOCKED` queue is the current standard for a broker-less, crash-safe job queue — no Redis/RabbitMQ/Celery to operate (fewer moving parts, reality-challenge #2). The `job-queue` README encodes exactly this pattern, and it is already vendored across the fleet. The alternative (an always-on orchestrator *agent* that loops in its own prose) is precisely the R8 anti-pattern the north star names.

**Orchestrator model — Opus 4.8 default, Fable 5 opt-in (grounded decision):** Fable 5 is **$10/$50 per M — 2× Opus 4.8** ($5/$25) and **metered on usage-credits since 2026-07-07**. The operational stack is **subscription-billed** via `claude -p` (R13; `feedback_claude_code_not_api`). So the always-on producer/orchestrator runs **Opus 4.8 on the Max subscription**; **Fable 5 is opt-in per-stage** only where its long-horizon "work for days, delegate to sub-agents, check its own work" strength justifies burning credits (e.g. a whole-epic execute). Cheap breadth stays on the **OpenRouter pool** (`minimax-m3`, ≤$1.5/Mtok) per 62.

**Episodic memory wired to the orchestrator (operator requirement):** the Opus orchestrator and every `claude -p` producer inherit the **user-scoped `episodic-memory` plugin** (semantic search over past conversations, local SQLite, no API cost). Each producer stage's prompt carries the standing hook — *search history for a prior decision / rejected approach / known wall before re-deriving it* — the same hook now in `00-trigger-fabrik` and `/fabrik-spec`. ⚠️ A hit is a **lead, not a citation**: external facts in it are re-grounded live. (Note: the index is built by a capped systemd service; see `feedback_cap_heavy_local_jobs` — the driver must not trigger a full re-index inline.)

**Nesting — a non-issue (was my flagged risk, now dissolved):** producers are `claude -p` **subprocesses** (fresh Claude Code invocations — they may spawn their *own* subagents freely); convergers call `fanout` (**pool = separate OS processes**). Neither is a nested native Claude subagent, so the one-level nesting limit never applies. The whole system is separate OS processes coordinated by Postgres rows.

---

## External dependencies (grounded this session)

| Dependency | Grounded fact | Source · date |
|---|---|---|
| **`claude -p` headless** | Non-interactive; same agent loop; `--model`, `--output-format json` (→ `result` + `session_id` + `total_cost_usd`), `--allowedTools` / `--permission-mode` for unattended runs; built for shell/cron/CI. A subprocess — spawns its own subagents. | https://code.claude.com/docs/en/headless · 2026-07-15 |
| **Claude Fable 5** | `claude-fable-5`; **$10 / $50 per M** (2× Opus 4.8); designed to "work for days, delegate to sub-agents, check its own work"; on Max subscription through 2026-07-07, **usage-credits (metered) after**. | https://openrouter.ai/anthropic/claude-fable-5 · platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5 · 2026-07-15 |
| **Opus 4.8** | `claude-opus-4-8`; $5 / $25 per M; subscription-billed via `claude -p` on Max — the operational default. | Anthropic pricing · session context · 2026-07-15 |

---

## fabrik-lib verdict (vendor→enhance→build)

| Capability | Verdict | Module / why |
|---|---|---|
| Job queue + worker fork-loop + hard-timeout + crash detection + graceful shutdown | **VENDOR** | `fabrik-lib/job-queue` (`poll_worker.py` + `reference_claim.py`) — copy + vendor sibling `db-pool` |
| Autoscale workers to the box (R3 capacity) | **VENDOR** | `job-queue/autoscale.py` — cgroup-aware, 0 project refs, copy verbatim |
| Parallel fan-out dispatch (one review round: spawn N graders, record, return) | **VENDOR** | `libs/subagents.fanout` (`agent.py:701`) — a **single** dispatch; already built + telemetry-recorded |
| **Converge-to-no-op LOOP around `fanout`** (call → detect zero-findings/zero-edits → repeat → stop) | **BUILD** | ⚠️ **This is the R8/D4 core — the "loop in code" the whole driver exists to provide.** `fanout` does ONE round; the *loop* is not vendored. Thin, but it is the novel deliverable, NOT free. Project-local (the no-op predicate is per-command). |
| Telegram digest at the human gates | **VENDOR** | `fabrik-lib/alerting` (Apprise → the VPS Apprise service) |
| **Producer handler** — `process_fn` that runs `claude -p "/fabrik-<stage>"` in a git worktree, parses the JSON result + cost, maps exit → next stage | **BUILD** | thin (no module wraps `claude -p` worktree runs). **💡 fabrik-lib candidate: `claude-worker`** — generic, ≥2 project types (any factory), small interface (`run(cmd, worktree, model) -> {result, cost, session}`), would've saved this project work. Propose to hub; do not write cross-repo. |
| **Transitions table + `fabrik factory` CLI** (`start`/`enqueue`/`status`/`approve`) | **BUILD** | the truly-novel core — the Fabrik-lifecycle-specific control flow. Project-local. |

---

## Shape / infra implications

Not a scaffolded product service — **hub operational tooling**, like the watchdog / sysadmin bot: a long-running worker process + a CLI on the hub (WSL dev, then vps1). Uses **Postgres for the `jobs` table** (WSL: local pg; hub: `postgres-main` — swappable by `DATABASE_URL`, 12-Factor IV). No Traefik route, no `shape:` flags of its own; git worktrees under a scratch dir give each producer an isolated tree (the disjoint-`owned_paths` concurrency contract from mega/02 becomes real here). Subscription-billed; the watchdog's cost-budget pattern guards any Fable-5 opt-in.

---

## Rejected alternatives

1. **Always-on orchestrator *agent*** — one long `claude -p` (Opus or Fable) session that orchestrates everything in its own reasoning, spawning subagents, no external queue. **Rejected:** it *is* the R8 anti-pattern (control flow in the agent's prose, not code); no crash-recovery; dies with the context window; can't drain 50 projects; metered if Fable. The whole north star exists to replace this.
2. **Off-the-shelf agent-orchestration board (Vibe Kanban / similar)** — **Rejected:** operator retired Vibe Kanban this session; it runs agents *outside* the `/fabrik-*` quality system (no Tier-2 gate, no rule packs, no flywheel). Adjacent to D3 but wrong-shaped.
3. **Broker queue (Redis/Celery/RabbitMQ)** — **Rejected:** more moving parts than a Postgres-`SKIP LOCKED` queue that's already vendored and crash-safe (reality-challenge #2; `job-queue` README's whole thesis).

---

## Constraints (binding)

- **R13 / `feedback_claude_code_not_api`:** subscription-billed (Opus via `claude -p`), OpenRouter pool for cheap breadth. Fable 5 metered → opt-in only. Never the `ANTHROPIC_API_KEY` operational path.
- **R8 / D4:** the converger loop runs **in the driver's code**, calling `fanout` — never "ask an agent to loop."
- **Two gates only:** plan-approval IN, deploy-approval OUT (deploy = manual `fabrik apply`, trigger-not-execute).
- **62-using-subagents.md** inherited verbatim (dispatch policy, model tiers, parallelism shapes).
- **12-Factor IX:** requeue in-flight job on SIGTERM (vendored `poll_worker` does this) + idempotent stages.
- **Shared-tree safety:** each producer runs in its **own git worktree** — the disjoint-`owned_paths` contract enforced physically.

---

## Open / blocking unknowns

| Unknown | Status | Resolution step |
|---|---|---|
| Exact `claude -p` flags for fully-unattended permission (which `--permission-mode` value avoids all prompts without `--dangerously-skip-permissions`) | OPEN (non-blocking) | Resolve at plan time from `code.claude.com/docs/en/headless` + a live `claude -p --help`; a producer that hits a permission prompt must fail-closed to `awaiting-owner`, not hang. |
| Does a producer stage that ITSELF stops for the plan-approval gate (`/fabrik-plan-after-chat` presents, waits) compose with headless mode? | OPEN (design) | The producer for a gated stage runs to the *presentation* then exits with an `awaiting-owner` signal; the driver emits the digest. The gate is a driver state, not an in-agent wait. Confirm at plan time. |
| Fable-5 opt-in trigger — which stages, and a hard credit ceiling | OPEN (policy) | Default: never; opt-in per-stage via a `model: fable-5` job attribute + a watchdog-style daily credit cap. Owner sets the ceiling. |
| `jobs` table schema — reuse `reference_claim`'s generic shape vs a factory-specific one | OPEN (small) | Start from `reference_claim.py`'s generic `jobs` table; add `stage` + `project` columns. Decide at plan time. |

None blocks the design — all are plan-time or policy resolutions, not un-grounded external facts.

---

## 💡 fabrik-lib candidate

**`claude-worker`** — a generic `process_fn` that runs `claude -p <command>` in an isolated git worktree, parses the JSON result + `total_cost_usd`, enforces a per-run cost/timeout cap, and returns `{result, cost, session_id, exit}`. Reusable by any Fabrik "factory" (this driver, a future test-generation factory, a docs-refresh factory). Small interface, no business logic. **Propose to the hub — do not write into `/opt/fabrik-lib` from here (cross-repo HARD STOP).**
