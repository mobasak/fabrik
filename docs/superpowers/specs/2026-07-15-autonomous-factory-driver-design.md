# Autonomous Factory Driver (D3 / R8) — Design Spec

**Status:** CONVERGED 2026-07-19 (rewritten + re-converged via /fabrik-spec-review, 8-pass ledger, md5 no-op `ae36e681…`; supersedes the 2026-07-15 convergence) — **awaiting operator approval**
**Date:** 2026-07-15 · **Rewritten:** 2026-07-19 · **Owner:** operator
**Why rewritten:** two things landed after the original convergence. (1) The **enforcement architecture**
(spec `2026-07-18-fabrik-factory-architecture-design.md`, EXECUTED 2026-07-19) — armed reviews via
`scripts/review_rubric.py` are now live fleet-wide **inside the commands**, so the driver no longer needs a
converger of its own — it sequences commands that already converge themselves.
(2) The operator's working model sharpened: Traycer Desktop sessions (parallel, one per project) are the
interactive surface AND the execution engine from `07-execute` (Phased YOLO auto-executes); the operator is
**at the screen all day**; there is **no Telegram** in the loop. What is missing is only the **conveyor**:
nothing advances a project from one command to the next, picks the next epic/project, or resumes a dead
run. The driver is that conveyor — nothing more.

**North star:** [`docs/orchestrator/00-autonomous-factory-north-star.md`](../../orchestrator/00-autonomous-factory-north-star.md)

| North-star item | This spec |
|---|---|
| **R2** 24/7 unattended between the gates | the artifact-state worker (survives crash/reboot — state IS the artifacts) |
| **R3** ~50 projects = queue depth | the project backlog + `autoscale.py` capacity bounds |
| **R8/D4** control flow in code, not prose | the advancement state machine runs in driver **code**; the armed converge loops run inside each command's own headless run (delta vs R8's original "driver runs the loops" wording — amend alongside R14) |
| **R13** subscription + pool, no rental | `claude -p` on Max (Opus default); pool via the commands' own dispatch |
| **R14** two human gates | Gate 1 = the 00 intent LOCK · Gate 2 = present + manual deploy |

**Cockpit relationship (unchanged, per `orchestrator-cockpit-requirements.md`):** this driver is the
**headless twin** of the interactive cockpit. Traycer Desktop today — or the agetor fork if it wins the
live evaluation — renders the same artifact state; the driver is the backend either front-end sits on.
Nothing here depends on that choice.

---

## Goal — the operator's two flows, hands-off between the two touches

*(ettw = the **epic-to-ticket workflow** chain, `docs/orchestrator/epic-to-ticket-workflow/00…11`; mega =
`docs/orchestrator/mega-epic-breakdown/00→02→03→04`.)*

```
BIG:    /00-trigger (mega) — operator talks, intent captured, Vision Summary LOCKED ⟨GATE 1⟩
        → 02 → 03 → 04 → [PER-EPIC: ettw 00→01→…→06→07 execute→08 code-vs-spec→10 cross-artifact
                          →11 deploy-prep = that epic's PRESENT ⟨GATE 2 — operator runs `fabrik apply`;
                          the driver's 11 then verifies + reports⟩]
        — the whole 00→11 ettw chain runs PER EPIC; the project is done when its last epic's 11 verifies.
SMALL (single-epic):  /00-trigger (ettw, chat-only orient) → 01 decisions-lock (DRAFT artifact)
        → 01R decisions-review (converge to no-op → operator confirm = LOCKED ⟨GATE 1⟩)
        → 02/03 → … → 06 → 07 → 08 → 10 → 11 ⟨GATE 2, same⟩
(09-revise is a SIDE-LOOP, not a linear stage — reached by an operator scope-change, an 08 Product
Misalignment, or a BLOCKED-3 escalation; the driver re-enters the chain from wherever 09 lands.)
```

**The chains already expect this driver.** Grounded 2026-07-19: the ettw `07`–`11` headers each open with
*"Run DIRECTLY by our orchestrator agent (Opus 4.8, via the driver) — never pasted into a planner GUI"*, `08`
states *"There is NO human step between the plan-in gate (passed) and the deploy-out gate (11-deploy)"*, and
`11-deploy` is already specified non-autonomous (*"the driver PREPARES the deploy … and STOPS; the OPERATOR
runs `fabrik apply`"*). This spec builds the driver those files were written for.

**Gate-1 supersession (record, don't hide):** north-star R14 words gate 1 as *"plan approval in"*. The
operator's 2026-07-19 direction moves gate 1 **earlier — to the `00` intent lock** ("after 00-trigger, and my
intent is very well captured, I should not be needed at all"); every later plan/decision is **externally
checked and locked** by the armed loops instead of operator-approved. Doc implication: amend north-star R14's
wording when this spec executes. (`09-revise` remains the operator's re-steering entry any time they choose.)

After the operator's **intent lock at `00`**, the driver advances the chain command-by-command —
**every plan and decision externally checked and locked** (the armed converge loops each command already
carries) — through execution and review, and comes back only to **present the finished project**.
The operator watches everything live (same files, same Traycer sessions), and may review or rework
**anything, any time** — the driver resumes from the corrected artifacts. Presence is optional by design;
intervention is always possible.

**Research intake:** the operator's external deep-research (Gemini etc.) drops into
`docs/development/plans/00-research.md` / `docs/preplans/*.md` — `00-trigger` Path A already consumes it
cumulatively. That is the front door for "help the project enter properly."

---

## Scope

**IN:** the conveyor — artifact-state detection, chain advancement (headless `claude -p` runs of the same
`-fabrik` command files), per-project parallel lanes with capacity bounds, crash/stall detection + resume,
coordinated back-off on transient external-API failure (vendored `pause-state`, optional),
the two gate states, a thin `fabrik factory` CLI (`status` / `queue` / `pause` / `resume`).

**OUT (each already exists — the driver only *drives* them):**
- The `-fabrik` command chains (mega + ettw) — they are the stages, persisted to disk by design.
- Execution + phase review — **Traycer Phased YOLO owns `07`-onward** in session-driven projects; in
  driver-driven lanes the same `07-execute-fabrik` command runs headless (it dispatches its own coders).
- The armed reviews — `review_rubric.py` + the converge-to-no-op contracts live **inside** the commands
  (enforcement architecture, shipped). The driver just runs the commands, which converge themselves; it
  re-implements nothing and carries no converge loop of its own.
- The subagent pool, the rule packs, the MCP toolbox — reached by the commands, per `62-using-subagents.md`.
- ~~Telegram digest~~ — **removed** (operator: at the screen all day; the artifacts + status CLI are the surface).

---

## Chosen approach — artifact-state conveyor over the existing chains

**State = the artifacts.** Every chain command persists its output to disk (Vision Summary, epic files,
tickets, INFRA-CHECK, validation verdicts) — the chains were built disk-first precisely so no state lives
in a context window. The driver holds **no state of its own** beyond the queue: it *reads* each project's
artifact tree to know exactly which command is next. Crash/reboot recovery is therefore free — rescan.

| Concern | Mechanism |
|---|---|
| **What's next?** | per-chain transitions table (`00→02→03→04→[per-epic: ettw 00→01→01R→…→06→07→08→10→11]`; small flow skips mega; `09` = side-loop re-entry) + an artifact-completion predicate per command (its declared output exists + carries its terminal status marker) |
| **Advance** | run the next command **headless**: `claude -p` on the same `-fabrik` file, in the project tree, model per stage (Opus default, R13), `--output-format json` for result + cost |
| **External check & lock** | inherited from the commands: each carries its armed review / convergence contract (`review_rubric.py`-injected finders, no-op termination); a command that hasn't reached its locked terminal state is not "complete" — the driver will not advance past it |
| **Parallelism** | one lane per project (multiple projects concurrently); inside a BIG project, per-epic fan-out where the chain declares independence (04's disjoint `Owned paths`) — **each epic is its own sub-lane with an independent state** (one epic parked `ready-for-operator` never blocks a sibling epic); a stage that touches **project-level shared artifacts** (e.g. a cross-epic summary) serializes on the project lane — only epic-owned-path stages fan out; `autoscale.py` (vendored, cgroup-aware) bounds total concurrent heavy work, and **only running stages consume capacity** (a parked or waiting lane holds no slot) |
| **Session coexistence** | shared disk store — a Traycer session and the driver **don't fight over stage boundaries**: `fabrik factory pause <project>` parks a lane **at the next boundary** (the in-flight stage completes; `pause --now` SIGTERMs it → vendored requeue); `resume` **refreshes the snapshot** and re-derives the next command from the current artifact state (crash recovery IS a resume — restart also refreshes, so a stale snapshot never false-trips the guard). The mtime guard is evaluated at **stage boundaries**, against a pre-stage snapshot stored **on the queue row** (Postgres — survives a driver crash); a running stage's own writes never trip it. The **mid-stage window** (operator rework while a stage runs) is guarded by discipline (`pause` first), not enforcement, until the plan's file-watch-abort lands — see Open unknowns |
| **Stall/crash** | the **watchdog path**, deliberately distinct from clean shutdown: watchdog fires (per-run hard timeout, or no artifact mtime advancing — evaluated per **running** stage only; a paused lane has no running stage) → **SIGKILL** the stage + `defer_fn` (requeue + retry bump); clean SIGTERM shutdown instead uses `defer_until_fn` (requeue, **no** bump) — both are real vendored callbacks (`poll_worker.py:84-90`; `retry_count` on the job row, `reference_claim.py:189`). One retry, then mark the lane `BLOCKED` with a visible `BLOCKED.md`-style marker (operational status, NOT a chain artifact — the one file class the driver itself writes). **Blocked causes, exhaustively:** a command's own BLOCKED report (CLAUDE.md's three cases: 3× same-test failure, missing infra, unresolvable spec contradiction) **or** the driver's two operational causes (watchdog retry-exhaustion, unpermitted-tool abort). A watchdog false-positive is bounded by design: the hard timeout is the primary kill, the no-progress fuse is deliberately long (stages legitimately compute without writing for stretches), and a wrong kill costs one retry then a visible, operator-recoverable `BLOCKED`. **Escape:** the operator fixes the cause and `resume`s — `resume` (including after a `09` re-steer: the operator resumes when done) clears `BLOCKED` and re-derives from artifacts, which simply **re-runs the incomplete stage** |
| **Gate 1** | **format FIXED (2026-07-19 reshape):** BIG = the mega `00` Vision confirm, persisted to `docs/superpowers/specs/YYYY-MM-DD-<project>-vision.md`; SMALL = the operator confirm at **ettw `01R`**, which writes the **`Status: LOCKED <date>`** line into `docs/superpowers/specs/YYYY-MM-DD-<slug>-decisions.md` — the driver's Gate-1 predicate greps that line. Per-epic ettw runs inside a BIG flow **auto-lock** at `01R`'s no-op (vision already operator-locked; no per-epic gate) |
| **Gate 2** | ettw `11-deploy` has two predicate-detected states — no special halt protocol: (1) `11-prepared` (deploy ticket + PRESENT summary written; the subprocess exits normally) is a **park predicate, NOT a completion predicate** — the lane parks `ready-for-operator` and `11` counts as *incomplete*; the **operator runs `fabrik apply`** from the hub, then `fabrik factory resume` → re-derivation picks the still-incomplete `11` and re-runs it (idempotent; it skips prep and verifies) → (2) `11-verified` — the **only** completion predicate for `11` → lane `done`; a verify **failure** follows the normal stage paths (`11`'s own fix loop → retry → `BLOCKED` missing-infra) — the lane never silently goes `done` (trigger-not-execute, R14). A `09` entry parks the same way (`needs-operator` — `09` is operator-owned re-steering by design), so **any cycle through `09` passes through the operator**: no autonomous 08↔09 oscillation is possible |
| **Attention surface** | the operator's open sessions + `fabrik factory status` (one screen: per-project lane, current command, waiting-on, blocked) — **no push channel** |

**Orchestrator model (re-grounded 2026-07-19):** headless runs on **Opus 4.8 via the Max
subscription** (`claude -p`); Fable 5 strictly opt-in per-stage — **inside the same subscription auth**
(`/model` in the prompt / `--model`), never a raw `ANTHROPIC_API_KEY` (R13 has no carve-out); the headless
producer checks the daily credit ledger (summed from `total_cost_usd`) **before launch**, as an **atomic
check-and-reserve on the queue DB** (two concurrent launches can't both pass) — over budget ⇒ the stage is
**launched on Opus instead** (a pre-launch model swap, never a mid-run abort). Cheap breadth stays on the OpenRouter pool *inside* the commands.
**Episodic memory** stays wired (producers inherit the user-scoped plugin; hits are leads, re-grounded live).

---

## External dependencies (all re-grounded LIVE 2026-07-19, this session)

| Dependency | Grounded fact | Source · date |
|---|---|---|
| **`claude -p` headless** | Non-interactive, same agent loop; `--model`; `--output-format json` → `result` + `session_id` + `total_cost_usd`; skills/commands invocable in the prompt (`/skill-name` expands); `--resume <session_id>` (project-dir-scoped) for stage crash-resume; SIGTERM aborts the turn, kills the Bash process tree, runs SessionEnd hooks, exits 143. **Unattended permissioning is fail-closed by design:** `--allowedTools` (permission-rule syntax) + `--permission-mode dontAsk` — an unpermitted tool call **aborts the run** (no hang, no `--dangerously-skip-permissions`). ⚠️ **Never `--bare`:** bare mode skips OAuth/keychain (auth would require `ANTHROPIC_API_KEY` — forbidden by R13); non-bare also correctly loads CLAUDE.md/skills, which the commands need | code.claude.com/docs/en/headless · fetched 2026-07-19 |
| **Opus 4.8** | `claude-opus-4-8`, $5 in / $25 out per MTok — subscription-billed via `claude -p` on Max → the operational default | platform.claude.com/docs/en/docs/about-claude/pricing · fetched 2026-07-19 |
| **Fable 5** | `claude-fable-5`, $10 in / $50 out per MTok (API-metered; metered for us since 2026-07-07) → opt-in only, never the default | platform.claude.com/docs/en/docs/about-claude/pricing · fetched 2026-07-19 |
| **Postgres `SKIP LOCKED` queue (the 1c leanness grounding)** | The primary source itself names the use case: *"can be used to avoid lock contention with multiple consumers accessing a queue-like table"* — with Postgres already deployed and `fabrik-lib/job-queue` already implementing it, a broker (Celery/Redis/RabbitMQ) adds infrastructure for zero gain at this scale (~20 workers, one host) | postgresql.org/docs/16/sql-select.html (Locking Clause) · fetched 2026-07-19 |

## fabrik-lib verdict (vendor→enhance→build)

| Capability | Verdict | Module / why |
|---|---|---|
| Queue + worker fork-loop + hard-timeout + crash detect + SIGTERM-requeue | **VENDOR** | `fabrik-lib/job-queue` — verified 2026-07-19: SKIP LOCKED claim (`reference_claim.py:81`), SIGTERM kill-children-then-requeue (`poll_worker.py:515-547`). ⚠️ README: vendor sibling **`db-pool/`** alongside (`reference_claim` imports `db_pool`); `observability/`/`pause-state/` optional, auto-detected |
| Capacity bounds (R3) | **VENDOR** | `job-queue/autoscale.py` — cgroup-aware, copy verbatim |
| Armed review round | **VENDOR (shipped)** | the commands' own `review_rubric.py` injection — the driver never re-implements review |
| **Artifact-completion predicates + transitions table + no-artifact-progress watchdog** | **BUILD** | the novel core: per-command "is its output complete + locked?" checks over the chains' declared artifacts; the no-progress watchdog reuses the same artifact reads (hard-timeout/crash-detect stay vendored) |
| **Headless producer** (`claude -p` run + JSON parse + cost/timeout cap + stage-table row → CLI flags materialization + the Fable daily-credit ledger) | **BUILD** (thin) | ladder ran: `claude-evaluator/` inspected 2026-07-19 — a batch *evaluation* harness (prompt-template + items → scored JSON), not a generic command-file runner; its subprocess pattern is reference material. 💡 fabrik-lib candidate `claude-worker` — propose to hub, don't write cross-repo |
| Coordinated back-off on transient API failure (all lanes pause when Claude API is overloaded) | **VENDOR (optional)** | `fabrik-lib/pause-state` — Redis sliding-TTL cluster pause; distinct from operator `pause` (intent, persistent) — this one is failure back-off (TTL, auto-clears) |
| **`fabrik factory` CLI** (`status`/`queue`/`pause`/`resume`) | **BUILD** (thin) | hub-local — lives with the driver on `/opt/fabrik` (per § Shape: hub operational tooling) |
| ~~Telegram digest~~ | **DROPPED** | operator requirement 2026-07-19 — no push channel; artifacts + status CLI are the surface |

---

## Shape / infra implications

Hub operational tooling (like the watchdog): a worker process + CLI on the hub. Postgres `jobs` table
(WSL local pg ↔ `postgres-main`, swappable by `DATABASE_URL`, 12-Factor IV). No Traefik route, no `shape:`
flags. **Vendored footprint:** `job-queue` + `db-pool` (hard dependency) + `observability`/`pause-state`
(optional, auto-detected). Headless producers run in the **project tree** (the chains manage their own
worktrees where they need them — e.g. `07`'s coder dispatch); the driver adds (provisions, never edits)
worktrees only if two lanes must touch one repo. Crash recovery = artifact rescan **+ the queue row**
(Postgres holds the snapshot + `retry_count`).

## Rejected alternatives

1. **Always-on orchestrator agent** (one long session that loops in its own prose) — the R8 anti-pattern;
   dies with its context; no crash recovery. Rejected in the original spec; still rejected.
2. **The original full D3 driver** (producer workers + in-code converger as driver-owned machinery) —
   **superseded 2026-07-19**: Traycer Phased YOLO already executes `07`-onward with a file-watcher-driven
   implement→review→verify→commit cycle, and the armed converge loops live inside the commands. Rebuilding
   them in the driver would duplicate two shipped systems. The driver is the *conveyor only*.
3. **Broker queue (Redis/Celery/RabbitMQ)** — more moving parts than the vendored Postgres-`SKIP LOCKED`
   queue. Rejected then, rejected now.
4. **Push notifications (Telegram)** — operator is at the screen; a push channel adds a surface nobody
   reads. Dropped 2026-07-19.

## Constraints (binding)

- **R13 / `feedback_claude_code_not_api`:** subscription `claude -p`; never `ANTHROPIC_API_KEY` operationally.
- **R8/D4:** advancement + convergence-detection run in the driver's **code**; the loops the commands carry
  are invoked, never paraphrased into prose the driver hopes an agent follows.
- **R14:** exactly two gate **kinds** — the flow-entry `00` intent lock in, present/manual-deploy out. A
  BIG project has **one intent lock for the whole project** (the mega `00`; per-epic ettw `00`s are not
  gates) plus one deploy gate per epic. Between them: external check + lock at every step, operator
  intervention always *possible*, never *required*.
- **`62-using-subagents.md`** inherited verbatim by every headless run (the commands carry it).
- **12-Factor IX:** SIGTERM requeues the in-flight lane (vendored); stages idempotent — idempotency comes
  from the commands' **own** converge-to-no-op contracts (re-running a partially-complete command converges
  to the same locked artifact); the driver's completion predicates only *detect* doneness, they don't create it.
- **12-Factor III + XI (the driver process itself):** the checked-in **stage table** is *design* (per-stage
  model/allow-list — identical across deploys); anything **deploy-varying** (DSNs, endpoints, log level,
  caps) lives in **env vars**; no secrets in code. Logs = unbuffered JSON to stdout (systemd/journald
  captures) — the driver never writes or rotates a logfile.
- **Runaway protection without per-call caps** (mandate "watchdog + cost-budget", per the operator's
  no-budget-caps stance): headless runs are subscription-billed (no per-token spend to cap); runaway-LOOP
  protection = per-run hard timeout + no-artifact-progress watchdog + retry-once-then-`BLOCKED`; the only
  metered path (Fable 5 opt-in) carries a daily credit cap.
- **Shared-tree safety:** the driver never edits artifacts itself; only the commands do. `git` operations
  follow the chains' own pathspec discipline.

## Open / blocking unknowns

| Unknown | Status | Resolution step |
|---|---|---|
| ~~Fully-unattended `claude -p` permission flags~~ | **RESOLVED 2026-07-19** | grounded live (headless docs): `--allowedTools` rules + `--permission-mode dontAsk`; an unpermitted tool **aborts** the run (fail-closed by design); never `--bare` (kills OAuth). Plan enumerates the per-stage allow-list |
| Per-command completion predicates — exact terminal markers per chain command (e.g. 04's `PASS` block, 06's ticket set, plan `Status:` values), **plus** the `BLOCKED` marker name/format (the one driver-owned format). ~~The Gate-1 lock-marker format~~ — **RESOLVED 2026-07-19**: the `Status: LOCKED <date>` line in the decisions artifact (ettw `01`/`01R`) / the persisted vision file (mega `00`) | OPEN (plan-time enumeration) | derive from each command's Output Contract section (the chains already declare them); the plan fixes the `BLOCKED` format |
| Traycer-session collision detection — is mtime-guard enough, or does Traycer hold locks worth honoring? Includes the **mid-stage window**: an operator reworking artifacts while a headless stage is running (the boundary guard can't see it) | OPEN (small) | observe a live session at plan time; default = `pause` before reworking (guidance) + mtime guard at boundaries; plan evaluates a file-watch abort for the mid-stage window |
| Fable-5 opt-in stages + credit ceiling | OPEN (policy) | default never; per-stage attribute + daily cap; owner sets |
| ettw `09-revise` (and possibly others) still reference **Telegram** escalation — the operator dropped Telegram 2026-07-19 | OPEN (chain cleanup, not driver scope) | plan adds a step: sweep `docs/orchestrator/**` for Telegram references, retarget escalation to the `BLOCKED` marker + `fabrik factory status` |

None blocks the design — all resolve at plan time.

## Success criteria (testable)

1. **Conveys:** on a test project with Gate 1 locked (a `Status: LOCKED` decisions artifact — SMALL — or a
   confirmed persisted vision — BIG), starting the driver advances the chain to the next locked terminal
   artifact with zero operator input (artifact appears + predicate satisfied).
2. **Crash-resumes:** `kill -9` mid-stage → restart → the driver re-derives the SAME next command from the
   artifact tree and continues (no duplicate stage, no skipped stage).
3. **Disposes cleanly:** SIGTERM → the in-flight lane's job row returns to `pending` (vendored requeue);
   restart picks it up.
4. **Coexists:** `pause <project>` → no advancement; edit an artifact while paused, `resume` → the next
   command derives from the corrected state (resume re-derives directly — no false `BLOCKED`, no stale
   snapshot trip).
5. **Gates hold:** without Gate 1's lock marker (no `LOCKED` decisions artifact / confirmed vision) the
   lane never advances; `11` **parks** the lane
   `ready-for-operator` pre-`fabrik apply`; the driver never invokes `fabrik apply` itself; after the
   operator applies and `resume`s, the re-run `11` verifies + reports and the lane goes `done`.
6. **Fails closed:** a stage hitting an unpermitted tool aborts → one retry → the `BLOCKED` marker
   (format fixed at plan time) + `status` shows `blocked` (never a silent hang).
7. **Parallel lanes:** two projects with locked `00`s advance concurrently, each in its own lane, within
   the `autoscale.py` capacity bound.
8. **End-to-end (the shakedown):** one SMALL test project runs `00`-lock → `11-verified` with exactly two
   operator touch-points (touch 1 = the lock; touch 2 = `fabrik apply` + `resume` together) and zero other
   input.
9. **Side-loop parks:** a forced `08` Product-Misalignment routes to `09` and the lane parks
   `needs-operator` — the park is the mechanism that makes an autonomous `08`↔`09` cycle impossible.

## 💡 fabrik-lib candidate

**`claude-worker`** — generic headless runner: `run(command_file, cwd, model, caps) -> {result, cost,
session_id, exit}` with timeout/cost enforcement. Reusable by any factory. Propose to the hub; never
write cross-repo from here.
