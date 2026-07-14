# Autonomous Factory — The North Star

**Status:** LIVING — **never archive** · **Owner:** operator · **Created:** 2026-07-12 · **Last updated:** 2026-07-14

> **This is the ultimate goal. Everything else in `docs/traycer/` exists to reach it.**
>
> The two workflow chains in this folder — `mega-epic-breakdown/` (vision → epics) and
> `epic-to-ticket-workflow/` (epic → tickets → code) — are **being evaluated and hardened against the
> requirements below**. When a command file here is reviewed, converged, twinned or rewritten, the
> question it must answer is: *does this move us toward the requirements on this page?*
>
> **Do not archive this file.** It is not a finished spec — it is the target the work is aimed at.

The idea→deploy autonomous pipeline: the operator specs & plans interactively; AI agents code, review
and doc-update autonomously; **two human gates** (plan in, deploy out).

---

## Requirements

**DONE** = built and in use · **PARTIAL** = built but not enforced end-to-end · **OPEN** = not built.

### Goal

| # | Requirement | State |
|---|---|---|
| **R1** | Two phases: (a) operator + AI **spec & plan** interactively; (b) AIs **code → review → doc** autonomously. | PARTIAL |
| **R2** | 24/7 unattended, headless; survives sleep/reboot. | **OPEN** |
| **R3** | 50 concurrent projects = **queue depth**, drained continuously. *(~55 projects in `/opt`; ProArt = 24 cores / 47 GB.)* | **OPEN** |
| **R10** | Whole lifecycle: spec · data-contract · ui-design · plan · execute · review · docs · deploy. **Producer** stages + **converger** stages. | DONE (commands exist) |

### Review / models

| # | Requirement | State |
|---|---|---|
| **R4** | Cheap diverse pool (≤$1.5/Mtok, distinct families) does the bulk of review. | DONE (`fanout`) |
| **R5** | Opus rationed: judge + high-risk escalation only. | DONE |
| **R6** | Full coverage, token-efficient: lens-split over the whole diff; cheap models compress context for the judge. | DONE |
| **R7** | **Converge-to-no-op loops**, never one shallow pass. | DONE (every `*-review` command) |

### Enforcement & learning

| # | Requirement | State |
|---|---|---|
| **R8** | Control flow in **code, not prose**: the driver runs the loops and calls `fanout` itself. | **OPEN** — the loops still live in command prose |
| **R9** | Flywheel: every pool run recorded; `pick_models` learns. | DONE (`check_subagent_flywheel.py`) |

### Human gates

| # | Requirement | State |
|---|---|---|
| **R12** | Escalate only on genuine blockers (Apprise → Telegram). | PARTIAL |
| **R14** | Exactly **two gates**: plan approval in, deploy approval out (deploy = manual `fabrik apply`). | DONE |

### Constraints

| # | Requirement | State |
|---|---|---|
| **R11** | Reuse what exists (`fabrik-lib/job-queue` = driver core; + `alerting`, `watchdog`, `subagents`/`fanout`, `claude_rotate`). | DONE (policy) |
| **R13** | Cost-conscious: subscription + pool; **no compute rental**. | DONE |
| **R15** | Lightweight cockpit — no Electron fleet-of-windows. | DONE (VS Code) |

### Working discipline — stated in chat, folded in 2026-07-14

These were operator requirements all along; they lived in the transcript instead of on this page, so
nothing tracked whether they stayed true. Recorded now, with their real state.

| # | Requirement | State |
|---|---|---|
| **R16** | **Run multiple agents in one project concurrently, on different scopes, WITHOUT touching the same files.** | PARTIAL — plans declare `File Scope (owned paths)`, but **`02`'s epic parallel-gate never checks file/schema disjointness** (see § Still open) |
| **R17** | Plan/spec creation must **ground 100 % truth** via exa / WebSearch / firecrawl — never training memory. | DONE (`/fabrik-spec`, `/fabrik-plan-after-chat`) |
| **R18** | Enforce **doc updates** and the **full Tier-2 `final_gate.py`** — `--lean` is never an acceptance gate. | DONE (Doc Sync Matrix + gate) |
| **R19** | Agents **consult `fabrik-lib`** before building any capability from scratch — vendor, don't rebuild. | DONE (Context Ledger) |
| **R20** | `/fabrik-review` after **every phase**, iterated until a pass finds nothing and changes nothing. | DONE (execute-plan phase boundaries) |
| **R21** | A finished plan is **archived only after it is 100 % verified**. | DONE (`/fabrik-execute-plan` Finish) |
| **R22** | During spec/plan, agents **propose new `fabrik-lib` modules** when a capability is reusable. | DONE (🆕 fabrik-lib candidate) |
| **R23** | **Every command's work is assignable to subagents; parallel where suitable.** Claude's own models first, then `minimax-m3`; cost-conservative. | DONE (`62-using-subagents.md`) |
| **R24** | **All project docs kept up to date** — cheapest correct way; cheap pool models author the doc patches. | DONE (`/fabrik-docs-review`) |
| **R25** | `/fabrik-spec-review` **stops for operator approval**; `/fabrik-plan-review` runs to no-op **autonomously** (never breaking the autonomous run). | DONE |
| **R26** | A separate **UI-design command** — lean, minimal clicks, **design-system first**. | DONE (`/fabrik-ui-design`) |
| **R27** | **Synced files carry a warning**: agents never edit them locally; they propose upstream only if the change is correct for ALL projects. | DONE (`check_synced_unmodified.py`) |
| **R28** | A fix to a vendored `fabrik-lib` template leaves an **upstream note**, so every future project inherits it. | DONE (`UPSTREAM_FEEDBACK.md`) |

---

## Decisions

- **D1 / D6** — Cockpit + planning surface = **VS Code** (as used today).
- **D2** — **Traycer: BEING EVALUATED — not dropped.** The operator's two-step workflow
  (`mega-epic-breakdown` → `epic-to-ticket-workflow` → automated agent orchestration) is a candidate
  front-end and **will not be dropped without retesting**. Known limitation to weigh: Traycer's planning
  chat **cannot run commands or use our MCP/web-search tools** — it reads `AGENTS.md` and asks questions
  only. Open evaluation: keep Traycer as the epic/ticket GUI, **or** build our own front-end on Claude
  Code, which *does* have command + MCP + web access.
  → **In flight:** the `-fabrik` twins (`00-trigger-fabrik`, `02-epic-decomposition-fabrik`,
  `03-expand-epic-files-fabrik`) **are** that own front-end, built tool-capable. `04` and `05` have no twin yet.
- **D3** — Driver = vendor `fabrik-lib/job-queue` + two `process_fn` handlers (producer = `claude -p`
  worktree worker; converger = in-code `fanout` review loop) + a transitions table + Telegram digest +
  a thin `fabrik factory` CLI.
- **D4** — The converger is executed **by the driver, in code** — not by asking an agent to loop (R8).
- **D5** — Capacity from `job-queue/autoscale.py` (real cgroup numbers); fleet later via `postgres-main`.
- **Zed** — dropped (no in-window multi-thread view).
- **Vibe Kanban** — dropped as cockpit (parked systemd service on `localhost:57300`; leave-or-remove TBD).
- **Gate 2** — Telegram digest → review branches in VS Code Source Control diff → merge → manual `fabrik apply`.
- **Epic ticket store (2026-07-14)** — our orchestrator has **no native ticket store** (Traycer does), so
  `03-expand-epic-files-fabrik` **writes one file per epic** to
  `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md` (allowlisted in `CLAUDE.md`; matched by
  `check_doc_sprawl.py`). A breakdown that lives only in a context window dies with it.

---

## Cargo order

1. **Shakedown:** plan-2 (`fabrik-capability-catalog`, CONVERGED 2026-07-12, execution-ready).
2. **First mission:** the 4-stack customer-finding pipeline — whatsapp-agent · tryton-crm ·
   trade-intelligence · tojlo-mail (wpf parked). Milestone = pipeline complete + deployed.
3. **Then the queue opens:** youtube, calendar-orchestration-engine, brand-identity-creator,
   iterative-image-editor, … toward 50.

---

## Still open — the distance between here and the top of this page

- **R2 / R3 — the driver itself is NOT BUILT.** The autonomous, 24/7, queue-drained factory (D3) does not
  exist. Today **the operator is still the loop**: every command is invoked by hand. This is the single
  largest gap between where we are and this page.
- **R8 — the loops live in prose, not code.** Every `*-review` command *tells* an agent to converge to a
  no-op. A driver would *run* that loop. **Prose is not enforcement** — and that is the lesson the rest of
  this repo keeps re-learning.
- **R16 — epic-level file/schema disjointness is unchecked.** `mega-epic-breakdown/02`'s parallel gate
  verifies only artifact **consumption** ("does B consume what A produces?"). It never checks whether two
  epics labelled *parallel* **write the same files or the same migration**. Harmless while epics run
  sequentially; it bites the instant anything acts on a `parallel` label.
- **Traycer evaluation** — retest; keep-as-GUI vs. finish our own twins (`04` and `05` still have none).
- Phase-4 capacity measurement (real per-worker numbers).
- Vibe Kanban parked service — leave or remove.
