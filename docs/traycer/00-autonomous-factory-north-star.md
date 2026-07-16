# Autonomous Factory — The North Star

**Status:** LIVING — **never archive** · **Owner:** operator · **Created:** 2026-07-12 · **Last updated:** 2026-07-16

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

## The two-workflow factory (end-to-end) — added 2026-07-16

Both `docs/traycer/` chains run the **same end-to-end pipeline**; they differ only in **who orchestrates**.

**The pipeline (idea → deploy) — every step converged to a no-op by its paired review before the next starts (R7/CC1, extended across the whole factory):**

1. **Front door** — a new *or existing* idea/plan → interactive Q&A → project **type · scope · requirements · data contract · GUI/screens · backend · frontend**. This IS the Fabrik pipeline: `/fabrik-spec` → `/fabrik-data-contract` → *(GUI)* `/fabrik-ui-design` → `/fabrik-plan-after-chat` — each grounded against the applicable `.windsurf/rules` packs + `AGENTS.md` + `CLAUDE.md`, and converged by its paired `-review`.
2. **Epic decomposition** — on the operator's agreement, `mega-epic-breakdown/` splits the vision into independent epics (`00-trigger` → `02-epic-decomposition` → `03-expand-epic-files` → `04-cross-epic-validation` → `05-dispatch-epic-tickets`).
3. **Scaffold** — create the scaffold project (`fabrik scaffold`, one of the 11 types) if it doesn't exist; if it does, **review it and bring it to 100 % compatible** with the agreed spec/`shape:`.
4. **Per-epic → tickets** — each epic runs the `epic-to-ticket-workflow/` (`00-trigger` → `01-epic-brief` … `10-cross-artifact-validation` → `11-deploy`).
5. **Per-ticket execution** — each ticket is executed by subagents (`claude -p` and the `libs/subagents` pool), coder + reviewer, converged per ticket.

**Two orchestration modes (both KEPT — D2):**

- **Traycer-managed** — the `-command` files, orchestrated in the **Traycer GUI** (a VS Code extension) with its **own** review workflow. Traycer's chat is **tool-less** (reads `AGENTS.md`, asks questions — no shell / MCP / web), so its accuracy ceiling is what the operator pastes.
- **Fabrik-managed** — the `-fabrik` twins, orchestrated by **Opus over ACP inside Zed** (D-Zed, reconsidered 2026-07-16). The orchestration front-end will be a **Zed extension** — the Fabrik analog of Traycer-in-VS-Code — using Zed's Agent Client Protocol + the `spawn_agent` / `wait_for_peer_replies` coordinator primitives to drive the coder/reviewer subagent threads. **Built after both folders' commands are finalized.**

---

## Requirements

**DONE** = built and in use · **PARTIAL** = built but not enforced end-to-end · **OPEN** = not built.

> ✅ **Verification status — every row was mechanically checked against the repo on 2026-07-14.**
> Each DONE row was proven by a command (does the file exist? does the command actually say it?), not
> asserted from memory. One row (**R5**, Opus rationing) initially failed and turned out to be a bad grep,
> not a missing requirement — `fabrik-review.md:110` mandates a native Opus reviewer for the
> authoritative/high-risk pass. The OPEN rows were verified as genuinely open (`job-queue` is not wired
> into `fabrik`; the driver does not exist).

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
| **R15** | Lightweight cockpit — no Electron fleet-of-windows. | DONE (VS Code today, single-window; the Fabrik workflow's **Zed** cockpit — Rust/GPUI, not Electron — is planned, D-Zed, built later) |

### Working discipline — stated in chat, folded in 2026-07-14

These were operator requirements all along; they lived in the transcript instead of on this page, so
nothing tracked whether they stayed true. Recorded now, with their real state.

| # | Requirement | State |
|---|---|---|
| **R16** | **Run multiple agents in one project concurrently, on different scopes, WITHOUT touching the same files.** | ✅ **DONE 2026-07-14** — `02`'s parallel gate now emits 3 verdicts (artifacts · **file-scope disjointness** · **single migration owner**); the new `Owned paths:` field carries the contract through all 7 hops (02→03→04→05→the agent's `File Scope`) |
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

- **D1 / D6** — Cockpit + planning surface = **VS Code** for the **Traycer-managed** workflow (as used today); **Zed** for the **Fabrik-managed** workflow (via the ACP orchestration extension, D-Zed). Zed is Rust/GPUI, **not** Electron → it satisfies **R15** ("no Electron fleet-of-windows") better than VS Code, not worse.
- **D2** — **RESOLVED 2026-07-16: BOTH workflows are kept** (no longer either/or). (1) **Traycer-managed** — Traycer stays the epic/ticket GUI for the `-command` files (its chat is **tool-less**: reads `AGENTS.md`, asks questions only — no shell / MCP / web). (2) **Fabrik-managed** — our own **tool-capable** front-end = the `-fabrik` twins, orchestrated by Opus over ACP in Zed (D-Zed). The two are the same pipeline, different orchestrators (see § The two-workflow factory).
  → **In flight:** the `-fabrik` twins. **ettw `00`–`10` built + converged** (2026-07-16); `11-deploy` + the `mega` parity (a `/fabrik-mega-review` skill, `04` rebuilt to the review discipline, `00`/`02`/`03`/`05` brought to parity) remain — tracked in `docs/superpowers/{specs,plans}/2026-07-16-traycer-fabrik-twins-*`.
- **D3** — Driver = vendor `fabrik-lib/job-queue` + two `process_fn` handlers (producer = `claude -p`
  worktree worker; converger = in-code `fanout` review loop) + a transitions table + Telegram digest +
  a thin `fabrik factory` CLI.
  → ✅ **CONVERGED design spec (2026-07-15):** `docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md`
  (scope = the WHOLE driver, not a harness fragment; **Opus 4.8 default orchestrator / Fable 5 opt-in** —
  Fable is $10/$50, 2× Opus, metered since 07-07, so subscription-Opus is the default per R13; **episodic
  memory wired to the orchestrator** — Opus + each `claude -p` producer inherit the user-scoped plugin and
  search history before re-deriving). Build pending — after the epic-to-ticket-workflow command review.
- **D4** — The converger is executed **by the driver, in code** — not by asking an agent to loop (R8).
  → the spec above splits this correctly: `fanout` (single dispatch) is VENDOR; the **converge-to-no-op loop
  around it is BUILD** — the R8/D4 core the driver exists to provide.
- **D5** — Capacity from `job-queue/autoscale.py` (real cgroup numbers); fleet later via `postgres-main`.
- **D-Zed — RECONSIDERED 2026-07-16 (reversed).** Zed was dropped for "no in-window multi-thread view"; that reason is now **stale**. Grounded live 2026-07-16 (`zed.dev/acp`, `zed.dev/docs/ai/external-agents`, `github.com/zed-industries/zed` discussions #48304 + #55122): Zed shipped a **Threads Sidebar** (v0.233.5) with **parallel agent threads** + cross-thread **ACP coordinator primitives** (`create_thread`, `spawn_agent` — awaits its child, `post_to_thread`, `wait_for_peer_replies` — *"required for external-ACP coordinators"*), and **Claude Agent (Claude Code) runs on ACP in Zed** today. ⚠️ **Shipped vs. proposed:** the Threads Sidebar (v0.233.5), parallel agent threads, `create_thread`, and `spawn_agent` (which awaits its child) have **shipped**; the cross-thread coordinator tools an external-ACP orchestrator also needs (`post_to_thread`, `wait_for_peer_replies` — the latter *"required for external-ACP coordinators"*) are **proposed / in flight** (discussion #55122), so the extension may need to layer them. Decision: the **Fabrik-managed orchestration front-end = a Zed extension speaking ACP** (the analog of Traycer-in-VS-Code), driving the coder/reviewer subagent threads. **Built after both folders' commands are finalized**; its engine — reuse the D3 `job-queue` backend vs. ACP-native `spawn_agent` orchestration — is settled at extension-build time.
- **Vibe Kanban** — ✅ **RETIRED 2026-07-14** (operator: "retire it and stop its service in wsl").
  `systemctl stop` + `disable` on `vibe-kanban.service`; port 57300 free, 0 processes. Unit file and
  `~/.vibe-kanban/` binary remain on disk but inert. *(For the record: it is an off-the-shelf board that
  runs coding agents in git worktrees — genuinely adjacent to D3's driver — but it knows nothing about
  `/fabrik-*`, the Tier-2 gate, or the rule packs, so it would run agents OUTSIDE the quality system.)*
- **Gate 2** — Telegram digest → review branches in VS Code Source Control diff → merge → manual `fabrik apply`.
- **Epic ticket store (2026-07-14)** — our orchestrator has **no native ticket store** (Traycer does), so
  `03-expand-epic-files-fabrik` **writes one file per epic** to
  `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md` (allowlisted in `CLAUDE.md`; matched by
  `check_doc_sprawl.py`). A breakdown that lives only in a context window dies with it.

---

## Command-chain build plan — the epic-to-ticket `-fabrik` twins (2026-07-15)

The `epic-to-ticket-workflow/` twins are built on the decisions below (operator session 2026-07-15). They serve **R7** (converge-to-no-op), **R8** (control flow forced, not hoped-for), **R23** (subagent parallelism), and an explicit **anti-bloat / anti-content-poisoning** discipline.

- **CC1 — Doer → review pairing.** Every doer command gets a **separate** review command that forces convergence to a no-op (the `/fabrik-spec` → `/fabrik-spec-review` pattern). A fresh-context review invocation converges better than a loop embedded in the doer's own blind-spot-sharing context. Review commands share **one lean template** (convergence contract + finder fan-out + checklist + gate), specialized per artifact — thin files, not ten more heavy ones.
- **CC2 — Citation discipline: "self-sufficient at point of use."** Every reference is classified **PROVENANCE** (decision already inline → tag `[canonical: file §X]`, never opened) / **HOLLOW** (unactionable without opening → inline the minimal decision, then tag) / **DEPTH-POINTER** (optional detail → mark `(deeper, optional: …)`). Enforced by a **`Reads:` budget header** (a closed, **section-scoped** read-set) at the top of every twin + checklist **item 132**. Kills bloat AND content-poisoning **structurally** — the runtime agent acts from inline decisions and never ingests a referenced doc's other (stale / contradictory / adversarial) content.
- **CC3 — Fold the data-contract freeze into `03-tech-plan`** (data-shaped epics); no separate command — keeps the doer chain lean.
- **CC4 — `04` is deploy-*plan*; `11` is the deploy.**
- **CC5 — `08`/`10` roles under CC1:** `08-implementation-validation` **is** `07-execute`'s review (code vs spec); `10-cross-artifact-validation` **is** the cross-cutting integration review (plan→execute boundary + `09-revise`'s review). Distinct jobs — **not** merged.
- **CC6 — Per-command build pipeline (serial; one command fully before the next):** reconcile the Traycer source to a no-op (`/fabrik-docs-review`) + hollow-citation sweep → fix per the design critique + citation discipline + add the `Reads:` header → checklist-eval to **0 FAIL** (144 items) → build the tool-capable twin (embedded convergence terminal phase, fan-out on ground/validate, live-research on vendor-touch, disk-reads for epic files) → north-star check (R2/R3/R7/R8/R23) → gate + commit (explicit paths).
- **CC7 — Template first:** `01-epic-brief-fabrik` + its `01-review` twin are built first as the reference pair; the operator reviews the pattern before it is replicated across `02`–`11`.

Status: **ettw `00`–`10` built + converged** (2026-07-16, each to an md5-stable no-op via its paired review — commits through `f1c246d9`); the shared `/fabrik-ettw-review` skill exists. Remaining: `11-deploy` + the `mega` parity (a `/fabrik-mega-review` skill; `04` rebuilt to the review discipline; `00`/`02`/`03`/`05` brought to parity). Tracked in `docs/superpowers/{specs,plans}/2026-07-16-traycer-fabrik-twins-*`.

---

## Cargo order

1. ~~**Shakedown:** plan-2 (`fabrik-capability-catalog`).~~ ✅ **DONE** — `Status: EXECUTED 2026-07-12`,
   both phases shipped + reviewed to CLEAN, plan archived
   (`docs/development/plans/archived/2026-07-12-plan-2-fabrik-capability-catalog.md`).
2. **First mission (NEXT):** the 4-stack customer-finding pipeline — whatsapp-agent · tryton-crm ·
   trade-intelligence · tojlo-mail (wpf parked). Milestone = pipeline complete + deployed.
3. **Then the queue opens:** youtube, calendar-orchestration-engine, brand-identity-creator,
   iterative-image-editor, … toward 50.

---

## Still open — the distance between here and the top of this page

- **R2 / R3 — the driver itself is NOT BUILT** (but now DESIGNED). The autonomous, 24/7, queue-drained
  factory (D3) does not exist yet — today **the operator is still the loop**. ✅ **Its design is now a
  CONVERGED spec** (`docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md`, 2026-07-15);
  **build pending** after the epic-to-ticket-workflow command review. Still the single largest gap — but the
  path from here is now planned, not blank.
- **R8 — the loops live in prose, not code** (design done). Every `*-review` command *tells* an agent to
  converge to a no-op; a driver would *run* that loop. The CONVERGED driver spec designs exactly this (the
  converge-to-no-op loop around vendored `fanout` = the BUILD core). **Prose is not enforcement** — and that is the lesson the rest of
  this repo keeps re-learning.
- **Fabrik-managed twins + Zed extension** — finish the remaining twins (`11-deploy` + the `mega` parity: a `/fabrik-mega-review` skill, `04` rebuilt to the review discipline, `00`/`02`/`03`/`05` brought to parity), then build the Zed-ACP orchestration extension (D-Zed). *(No longer a keep-vs-replace evaluation — D2 is RESOLVED, both workflows kept.)*
- Phase-4 capacity measurement (real per-worker numbers).
- Vibe Kanban parked service — leave or remove.
