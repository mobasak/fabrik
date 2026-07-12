# Autonomous Factory — Requirements & Decisions

**Status:** LIVING (requirements capture) · **Owner:** operator · **Date:** 2026-07-12

The idea→deploy autonomous pipeline: operator specs & plans interactively; AI agents
code / review / doc-update autonomously; two human gates (plan in, deploy out).

---

## Requirements

### Goal
- **R1** — Two phases: (a) operator + AI **spec & plan** interactively; (b) AIs **code → review → doc** autonomously.
- **R2** — 24/7 unattended, headless; survives sleep/reboot.
- **R3** — 50 concurrent projects = **queue depth**, drained continuously. *(Grounded: ~55 projects in `/opt`; ProArt = 24 cores / 47GB.)*
- **R10** — Whole lifecycle: spec · data-contract · ui-design · plan · execute · review · docs · deploy. **Producer** stages + **converger** stages.

### Review / models
- **R4** — Cheap diverse pool (≤$1.5/Mtok, distinct families) does the bulk of review.
- **R5** — Opus rationed: judge + high-risk escalation only.
- **R6** — Full coverage, token-efficient: lens-split over the whole diff; cheap models compress context for the judge.
- **R7** — Converge-to-no-op loops, never one shallow pass.

### Enforcement & learning
- **R8** — Control flow in **code, not prose**: the driver runs the loops and calls `fanout` itself.
- **R9** — Flywheel: every pool run recorded; `pick_models` learns.

### Human gates
- **R12** — Escalate only on genuine blockers (Apprise → Telegram).
- **R14** — Exactly two gates: **plan approval in**, **deploy approval out** (deploy = manual `fabrik apply`).

### Constraints
- **R11** — Reuse what exists. *(Grounded: `fabrik-lib/job-queue` = driver core; + `alerting`, `watchdog`, `subagents`/`fanout`, `claude_rotate`.)*
- **R13** — Cost-conscious: subscription + pool; no compute rental.
- **R15** — Lightweight cockpit, no Electron fleet-of-windows. **→ Cockpit + planning surface = VS Code (Claude sessions side by side).**

---

## Decisions

- **D1 / D6** — Cockpit + planning surface = **VS Code** (as used today).
- **D2** — **Traycer: BEING EVALUATED** (not dropped). Operator's two-step workflow (mega-epic-breakdown → epic-to-ticket-breakdown → automated agent orchestration) is a candidate front-end. Will not be dropped without retesting. Known limitation to weigh: Traycer's planning chat **cannot run commands or use our MCP/web-search tools** — it reads `AGENTS.md` and asks questions only. Open evaluation: keep Traycer as the epic/ticket GUI, OR build our own Traycer-like front-end (Claude Code CLI, which *does* have command + MCP + web access) that overcomes that limitation.
- **D3** — Driver = vendor `fabrik-lib/job-queue` + two `process_fn` handlers (producer = `claude -p` worktree worker; converger = in-code `fanout` review loop) + transitions table + Telegram digest + thin `fabrik factory` CLI.
- **D4** — Converger executed by the driver, in code (not an agent asked to).
- **D5** — Capacity from `job-queue/autoscale.py` (real cgroup numbers); fleet later via `postgres-main`.
- **Zed** — dropped (no in-window multi-thread view; doesn't match "many agent sessions visible at once").
- **Vibe Kanban** — dropped as cockpit (parked systemd service on `localhost:57300`, leave-or-remove TBD).
- **Gate 2** — Telegram digest → review branches in VS Code Source Control diff → merge → manual `fabrik apply`.

---

## Cargo order

1. **Shakedown:** plan-2 (`fabrik-capability-catalog`, CONVERGED 2026-07-12, execution-ready).
2. **First mission:** the 4-stack customer-finding pipeline — whatsapp-agent · tryton-crm · trade-intelligence · tojlo-mail (wpf parked). Milestone = pipeline complete + deployed.
3. **Then the queue opens:** youtube, calendar-orchestration-engine, brand-identity-creator, iterative-image-editor, … toward 50.

---

## Still open

- **Traycer evaluation** (retest; keep-as-GUI vs build-our-own).
- Phase-4 capacity measurement (real per-worker numbers).
- Vibe Kanban parked service — leave or remove.
