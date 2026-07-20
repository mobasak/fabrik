# Autonomous Factory — The North Star

**Status:** LIVING — **never archive** · **Owner:** operator · **Created:** 2026-07-12 · **Last updated:** 2026-07-18

> **This is the ultimate goal. Everything else in `docs/traycer/ or docs/orchestrator` exist to reach it.**
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

## Owner Working Model (how the factory is actually run — added 2026-07-18)

*The stable foundation. The commands, skills, docs and workflow below all exist to serve this. If a command contradicts this section, the command is wrong.*

**Owner.** Solo dev, ~50 focused h/week. Budget: free/cheap-but-good, **subscription-first, no compute rental** (R13). Philosophy: **fast but pro — ship → iterate → automate, no over-engineering.**

**The engine + tools — ONE tool-capable engine throughout.**

- **Traycer (desktop app)** — the planning/orchestration **layer**: the chat surface, the epic/ticket/spec **artifact store**, and the GUI. Traycer is **not an AI**; it is a harness that needs one connected to do anything.
- **Claude Max = the connected engine** (Claude Code + `claude -p`) — powers Traycer **and** is the orchestrator during coding. Because Claude Code drives Traycer, **the Traycer path has FULL tools** — shell, MCP, web, subagents. *(This very file is being edited by that engine, running inside Traycer.)* Claude Max brings its own native subagents (**haiku · sonnet · opus · fable**), Opus rationed to judgment / high-risk (R5).
- **`fabrik-lib/subagents` — the OpenRouter accompaniment.** Access to *all* OpenRouter models for any task (spec / plan / code / review / doc-review), used to **accompany** Claude Code, never replace it: (a) **different eyes** — diverse-family recall a single engine misses; (b) **cost control** — Claude Max is finite, so push cheap-but-capable models where they suffice, `set_quality`-scored to the flywheel (R4 / R9 / R23). This is the single lever for "more coverage without burning the subscription."

**Procurement discipline — best-in-class at the lowest viable cost.** For every capability a project needs, the order is **free / open-source → cheapest capable paid → build only if nothing fits.** Prefer existing libraries, packages, templates, toolsets, premade solutions, APIs, scrapers, automation tools — **vendor / integrate / use, don't rebuild** (R11 / R19). The `fabrik-lib` vendor→enhance→build ladder is the *internal-module* case of this rule; `00-trigger`'s 6-check research challenge (expensive-where-free-exists · complex-where-simple-exists · build-where-consume-exists · high-maintenance-where-set-and-forget-exists · incompatible · duplicate) is the *external* case.

**What I already have — check BEFORE proposing anything new.** The provisioned external services are catalogued in **`scripts/service_catalog.json`** — secret-free metadata, one entry per service with `category · cost · capability · url · status · used_by`. **90 services, all catalogued (0 triage)** span AI/LLM · search · scrape · captcha · proxy · domains · email · storage · research-data · media · infra. `scripts/gather_envs.py` renders the catalog into `secrets/all-envs.env` (the actual credentials) as `#svc`-annotated sections. **Planning MUST consult the catalog and never propose a new paid service for a capability already owned** — prefer an already-provisioned `cost=free|freemium` provider (procurement discipline made checkable); `used_by` shows which projects already wired it. `00-trigger`'s External-Services grounding + the 6-check read the catalog. ⚠️ **Secrets safety:** planning reads the **secret-free catalog**, never the credential values in `all-envs.env`; a value is never inlined into a plan, ticket, or doc.

**Interaction model.** The owner works **entirely through the chat window — never hand-edits a file.** Reworking a decomposition, turning epics into tickets, correcting scope — all **conversational**. Consequence for every command: it must be **fully driveable from chat** and must **persist its own artifacts** (the owner will not open a file to save them — persist-on-confirm, D6).

**The loop (idea → deploy) — two human gates (R14).**
```
idea ─▶ [full/large vision] mega-epic-breakdown ─▶ N epic files (each often 20+ tickets)
                                        │  ⟨GATE 1: owner confirms the decomposition, in chat⟩
      rework each epic CONVERSATIONALLY ◀┘  (no hand-editing — chat only)
                                        │
      per epic ─▶ epic-to-ticket-workflow ─▶ tickets ─▶ execute (coder + reviewer subagents, converged)
                                        │  ⟨GATE 2: manual `fabrik apply` — hub owns deploy execution⟩
                                     review ─▶ deploy
```

**Which workflow — three tiers.** Feature-scale (one operator-carried plan) → the `/fabrik-spec` pipeline. Epic → `epic-to-ticket-workflow` directly. Full / large vision → `mega-epic-breakdown` (vision → epics). Existing project → mega `00` in **EXISTING mode**. Test: needs tickets + dispatched agents ⇒ epic/vision; one operator-carried plan ⇒ feature-scale.

**One command set.** The runnable chain is the tool-capable **`-fabrik`** files under `docs/orchestrator/**`. The old `docs/traycer/{mega-epic-breakdown,epic-to-ticket-workflow}/` **`-command` twins were a tool-less mirror** premised on a now-false "Traycer can't use tools" assumption — **archived 2026-07-18** (D2 corrected). No two-set lockstep tax.

---

## Enforcement Model (the governing law) — added 2026-07-18

> **Nothing is ambient. Every load-bearing constraint reaches the acting agent through one of three delivery
> tiers — mechanical gate, compiled context, or armed review — never by an agent voluntarily reading a
> governance doc.**

The reliability ladder (full design + honest bounds: spec `docs/superpowers/specs/archived/2026-07-18-fabrik-factory-architecture-design.md`):

| Tier | Mechanism | Catches |
|---|---|---|
| **1 — Mechanical gate** | `final_gate.py` (Tier-2) · `check_*` suite · `epic_order.py` · hooks | Deterministic violations — can't be skimmed |
| **2 — Compiled context** | self-sufficient command files (decisions inlined at authoring time) + the one auto-loaded `CLAUDE.md` | The agent skipping context — it's in the window |
| **3 — Armed review** | `review_rubric.py` injects the matched packs + a mandatory-core floor into every finder; looped to a no-op | Semantic violations a script can't catch |

Honesty bound (spec § Known limitations L1–L4): Tier 3 is **probabilistic** — injection raises compliance
probability, it does not prove it. Standing direction: **drain Tier 3 into Tier 1** — every mandate
expressible as a deterministic grep migrates to a `check_*` gate (`review_rubric.py` emits promote
candidates as a byproduct), so the ladder gets sounder over time.

## The two-workflow factory (end-to-end) — added 2026-07-16 · front door widened to THREE tiers 2026-07-18

The two orchestrator chains (mega + ettw) run the **same end-to-end pipeline** and differ only in **who orchestrates**; since 2026-07-18 the front door is **three-tiered by scale** (step 1) — the feature-scale `/fabrik-spec` pipeline is the third entry, not a chain of its own.

**The pipeline (idea → deploy) — every step converged to a no-op by its paired review before the next starts (R7/CC1, extended across the whole factory):**

1. **Front door — three tiers by scale, symmetric routing.** **Feature-scale** (one plan an operator
   session carries) → `/fabrik-spec` → `/fabrik-data-contract` → *(GUI)* `/fabrik-ui-design` →
   `/fabrik-plan-after-chat` → execute — each grounded against the applicable `.windsurf/rules` packs and
   converged by its paired `-review`. **Epic** (needs a ticket store + dispatched agents) →
   `epic-to-ticket-workflow/00-trigger-fabrik` directly. **Multi-epic vision** →
   `mega-epic-breakdown/00-trigger-mega-epic-fabrik` (spec-grade intake — its Required sections carry everything
   `/fabrik-spec` produces; its Scale Assessment down-routes). The distinguishing test, once: *does it need
   tickets and dispatched agents, or is it one plan an operator session can carry?* Routing is symmetric —
   `/fabrik-spec` up-routes and ettw-00 mirrors (shipped 2026-07-18), so no entry point is "wrong." (Existing project → mega-00 in **EXISTING mode** — see § Which workflow.) ⚠️ A feature-scale entry **completes at its `execute`** — steps 2–5 below are the epic/vision tiers' path, not a continuation of feature-scale work.
2. **Epic decomposition** — on the operator's agreement, `mega-epic-breakdown/` splits the vision into independent epics (`00-trigger` → `02-epic-decomposition` → `03-expand-epic-files` → `04-cross-epic-validation` → `05-dispatch-epic-tickets`).
3. **Scaffold** — create the scaffold project (`fabrik scaffold`, one of the 11 types) if it doesn't exist; if it does, **review it and bring it to 100 % compatible** with the agreed spec/`shape:`.
4. **Per-epic → tickets** — each epic runs the `epic-to-ticket-workflow/` (`00-trigger` → `01-decisions-lock` … `10-cross-artifact-validation` → `11-deploy`).
5. **Per-ticket execution** — each ticket is executed by subagents (`claude -p` and the `libs/subagents` pool), coder + reviewer, converged per ticket.

**One tool-capable engine — the front-end is interchangeable (D2 corrected 2026-07-18):**

The engine is **Claude Max behind Traycer** (see § Owner Working Model) and it runs the single tool-capable **`-fabrik`** command set. What can change is only the *front-end shell*:

- **Traycer desktop (current)** — the planning/ticket GUI + artifact store, powered by Claude Code with **full tools**. This replaced the old "tool-less Traycer / `-command` twins" model — that assumption was false, and the `docs/traycer/**` `-command` mirror is **retired**.
- **Zed extension (future, D-Zed)** — the Fabrik analog of Traycer, Claude/Opus over ACP using `spawn_agent` / `wait_for_peer_replies` to drive coder/reviewer threads. Built later; **same pipeline, same `-fabrik` commands, different shell** — not a second command set.

---

## Requirements

**DONE** = built and in use · **PARTIAL** = built but not enforced end-to-end · **OPEN** = not built.

> ✅ **Verification status — every row was mechanically checked against the repo on 2026-07-14.**
> Each DONE row was proven by a command (does the file exist? does the command actually say it?), not
> asserted from memory. One row (**R5**, Opus rationing) initially failed and turned out to be a bad grep,
> not a missing requirement — `fabrik-review.md:135-136` mandates a native Opus reviewer for the
> authoritative/high-risk pass. The OPEN rows were verified as genuinely open (`job-queue` is not wired
> into `fabrik`; the driver does not exist).

### Goal

| #             | Requirement                                                                                                                                                | State                 |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| **R1**  | Two phases: (a) operator + AI**spec & plan** interactively; (b) AIs **code → review → doc** autonomously.                                    | PARTIAL               |
| **R2**  | 24/7 unattended, headless; survives sleep/reboot.                                                                                                          | **OPEN**        |
| **R3**  | 50 concurrent projects =**queue depth**, drained continuously. *(~55 projects in `/opt`; ProArt = 24 cores / 47 GB.)*                            | **OPEN**        |
| **R10** | Whole lifecycle: spec · data-contract · ui-design · plan · execute · review · docs · deploy.**Producer** stages + **converger** stages. | DONE (commands exist) |

### Review / models

| #            | Requirement                                                                                                  | State                            |
| ------------ | ------------------------------------------------------------------------------------------------------------ | -------------------------------- |
| **R4** | Cheap diverse pool (flywheel-ranked via `pick_models`, distinct families; no default price cap) does the bulk of review.                                 | DONE (`fanout`)                |
| **R5** | Opus rationed: judge + high-risk escalation only.                                                            | DONE                             |
| **R6** | Full coverage, token-efficient: lens-split over the whole diff; cheap models compress context for the judge. | DONE                             |
| **R7** | **Converge-to-no-op loops**, never one shallow pass.                                                   | DONE (every`*-review` command) |

### Enforcement & learning

| #            | Requirement                                                                                      | State                                                   |
| ------------ | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------- |
| **R8** | Control flow in**code, not prose**: the driver runs the loops and calls `fanout` itself. | **OPEN** — the loops still live in command prose |
| **R9** | Flywheel: every pool run recorded;`pick_models` learns.                                        | DONE (`check_subagent_flywheel.py`)                   |

### Human gates

| #             | Requirement                                                                                           | State   |
| ------------- | ----------------------------------------------------------------------------------------------------- | ------- |
| **R12** | Escalate only on genuine blockers (Apprise → Telegram).                                              | PARTIAL |
| **R14** | Exactly**two gates**: plan approval in, deploy approval out (deploy = manual `fabrik apply`). | DONE    |

### Constraints

| #             | Requirement                                                                                                                            | State                                                                                                                                        |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **R11** | Reuse what exists (`fabrik-lib/job-queue` = driver core; + `alerting`, `watchdog`, `subagents`/`fanout`, `claude_rotate`). | DONE (policy)                                                                                                                                |
| **R13** | Cost-conscious: subscription + pool;**no compute rental**.                                                                       | DONE                                                                                                                                         |
| **R15** | Lightweight cockpit — no Electron fleet-of-windows.                                                                                   | DONE (VS Code today, single-window; the Fabrik workflow's**Zed** cockpit — Rust/GPUI, not Electron — is planned, D-Zed, built later) |

### Working discipline — stated in chat, folded in 2026-07-14

These were operator requirements all along; they lived in the transcript instead of on this page, so
nothing tracked whether they stayed true. Recorded now, with their real state.

| #             | Requirement                                                                                                                                                      | State                                                                                                                                                                                                                                                                                |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **R16** | **Run multiple agents in one project concurrently, on different scopes, WITHOUT touching the same files.**                                                 | ✅**DONE 2026-07-14** — `02`'s parallel gate now emits 3 verdicts (artifacts · **file-scope disjointness** · **single migration owner**); the new `Owned paths:` field carries the contract through all 7 hops (02→03→04→the agent's `File Scope`) |
| **R17** | Plan/spec creation must**ground 100 % truth** via exa / WebSearch / firecrawl — never training memory.                                                    | DONE (`/fabrik-spec`, `/fabrik-plan-after-chat`)                                                                                                                                                                                                                                 |
| **R18** | Enforce**doc updates** and the **full Tier-2 `final_gate.py`** — `--lean` is never an acceptance gate.                                          | DONE (Doc Sync Matrix + gate)                                                                                                                                                                                                                                                        |
| **R19** | Agents**consult `fabrik-lib`** before building any capability from scratch — vendor, don't rebuild.                                                     | DONE (Context Ledger)                                                                                                                                                                                                                                                                |
| **R20** | `/fabrik-review` after **every phase**, iterated until a pass finds nothing and changes nothing.                                                         | DONE (execute-plan phase boundaries)                                                                                                                                                                                                                                                 |
| **R21** | A finished plan is**archived only after it is 100 % verified**.                                                                                            | DONE (`/fabrik-execute-plan` Finish)                                                                                                                                                                                                                                               |
| **R22** | During spec/plan, agents**propose new `fabrik-lib` modules** when a capability is reusable.                                                              | DONE (🆕 fabrik-lib candidate)                                                                                                                                                                                                                                                       |
| **R23** | **Every command's work is assignable to subagents; parallel where suitable.** Claude's own models first, then the flywheel's top-ranked pool models (`TASK_SUBAGENT_SELECTION.md`); cost-conservative.           | DONE (`62-using-subagents.md`)                                                                                                                                                                                                                                                     |
| **R24** | **All project docs kept up to date** — cheapest correct way; cheap pool models author the doc patches.                                                    | DONE (`/fabrik-docs-review`)                                                                                                                                                                                                                                                       |
| **R25** | `/fabrik-spec-review` **stops for operator approval**; `/fabrik-plan-review` runs to no-op **autonomously** (never breaking the autonomous run). | DONE                                                                                                                                                                                                                                                                                 |
| **R26** | A separate**UI-design command** — lean, minimal clicks, **design-system first**.                                                                    | DONE (`/fabrik-ui-design`)                                                                                                                                                                                                                                                         |
| **R27** | **Synced files carry a warning**: agents never edit them locally; they propose upstream only if the change is correct for ALL projects.                    | DONE (`check_synced_unmodified.py`)                                                                                                                                                                                                                                                |
| **R28** | A fix to a vendored`fabrik-lib` template leaves an **upstream note**, so every future project inherits it.                                               | DONE (`UPSTREAM_FEEDBACK.md`)                                                                                                                                                                                                                                                      |

---

## Decisions

- **D-Enforce (2026-07-18):** the reliability ladder is the factory's compliance model — see § Enforcement Model + spec 2026-07-18-fabrik-factory-architecture-design.
- **D1 / D6 — updated 2026-07-18.** Current cockpit + planning surface = the **Traycer desktop app** (tool-capable, Claude-Max-powered — Traycer is now its own desktop app, no longer a VS Code extension). Planned future **alternative** front-end = a **Zed/ACP extension** (D-Zed) driving the *same* `-fabrik` chain — Rust/GPUI, not Electron, satisfying **R15** ("no Electron fleet-of-windows"). **One workflow, interchangeable front-end** — not two "managed" workflows.
- **D2 — CORRECTED 2026-07-18: ONE tool-capable command set; Traycer is NOT tool-less.** The earlier "two workflows — tool-less Traycer (`-command`) vs tool-capable Fabrik (`-fabrik`)" split rested on a false premise. **Traycer's desktop app is powered by Claude Max (Claude Code), so it has full tools** (shell / MCP / web / subagents) — this file is edited by exactly that engine, running inside Traycer. So there is **one runnable, tool-capable chain: the `-fabrik` files in `docs/orchestrator/**`** (the single source of truth). The `docs/traycer/{mega-epic-breakdown,epic-to-ticket-workflow}/` `-command` twins (a tool-less mirror) were **archived 2026-07-18** — no lockstep tax. The *front-end* stays interchangeable (Traycer desktop today; a Zed/ACP extension later, D-Zed), but both drive the same `-fabrik` commands. See § Owner Working Model.
  → **Status:** ettw `00`–`11` built + converged (2026-07-16); **mega `00`/`02`/`03` brought to the enforcement bar, `04` is the convergence twin, `05` retired (2026-07-18)**. Shared review skill = `/fabrik-workflow-review` (folder-neutral; a duplicate `/fabrik-mega-review` was rejected per CC1's "one lean template"). Design history: `docs/superpowers/{specs,plans}/2026-07-16-traycer-fabrik-twins-*`.
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
- **CC6 — Per-command build pipeline (serial; one command fully before the next):** reconcile the Traycer source to a no-op (`/fabrik-docs-review`) + hollow-citation sweep → fix per the design critique + citation discipline + add the `Reads:` header → checklist-eval to **0 FAIL** (against `EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md` — by path; never a hard-coded count) → build the tool-capable twin (embedded convergence terminal phase, fan-out on ground/validate, live-research on vendor-touch, disk-reads for epic files) → north-star check (R2/R3/R7/R8/R23) → gate + commit (explicit paths).
- **CC7 — Template first:** `01-decisions-lock-fabrik` + its `01R-decisions-review-fabrik` twin are built first as the reference pair; the operator reviews the pattern before it is replicated across `02`–`11`.

Status: **the ettw chain is COMPLETE — `00`–`11` built + converged** (2026-07-16, each to an md5-stable no-op via its paired review — commits through `1fd7d432`; `11-deploy` is the human gate, converged by a grounding+consistency pass). The shared review skill was **extended folder-neutral + renamed → `/fabrik-workflow-review`** (it now serves BOTH folders via a type-conditional yardstick; a duplicate `/fabrik-mega-review` was rejected per CC1). Remaining: the **`mega` parity** — `04` rebuilt to the review discipline; `00`/`02`/`03`/`05` brought to parity. Tracked in `docs/superpowers/{specs,plans}/2026-07-16-traycer-fabrik-twins-*`.

---

## Cargo order

1. ~~**Shakedown:** plan-2 (`fabrik-capability-catalog`).~~ ✅ **DONE** — `Status: EXECUTED 2026-07-12`,
   both phases shipped + reviewed to CLEAN, plan archived
   (`docs/development/plans/archived/2026-07-12-plan-2-fabrik-capability-catalog.md`).
2. **Enforcement rollout (infra — NEXT, the keystone; quick):** execute the CONVERGED **enforcement-architecture**
   plan (`plan-2`, 2026-07-18) — arms every review with the matched rule rubric + mandatory-core floor, one
   tool-capable command set, compiled context.
3. **First mission — operator-in-the-loop (the shakedown, BEFORE the driver):** the 4-stack customer-finding
   pipeline — whatsapp-agent · tryton-crm · trade-intelligence · tojlo-mail (wpf parked). Run it **by hand** first:
   (a) shakes the chains down on real multi-project work; (b) produces the **real per-worker capacity numbers**
   (Phase-4 measurement, still open) the driver's autoscaling needs as *input, not guess*; (c) ships the
   revenue-relevant pipeline months earlier. Milestone = pipeline complete + deployed. *(Ship → iterate → automate:
   one car by hand before the conveyor belt.)*
4. **Build the driver (D3 / R8·D4) — LAST, and reconciled:** the CONVERGED 2026-07-15 spec, but ⚠️ **reconcile it
   against the enforcement architecture FIRST.** Its in-code converger predates `review_rubric.py`, so as-spec'd it
   would run **un-armed reviews** (the ~20%-recall failure enforcement exists to kill). The converger MUST call
   `review_rubric.py` and inject its output into every finder prompt **in code** — which moves rubric injection from
   command prose (Tier 2, skimmable) into driver code (**Tier 1, can't be skimmed**): the drain-Tier-3-into-Tier-1
   direction applied to the enforcement mechanism itself. Feed it the mission's real capacity numbers.
5. **Then the queue opens:** youtube, calendar-orchestration-engine, brand-identity-creator,
   iterative-image-editor, … toward 50.

---

## Still open — the distance between here and the top of this page

- **R2 / R3 — the driver itself is NOT BUILT** (but now DESIGNED). The autonomous, 24/7, queue-drained
  factory (D3) does not exist yet — today **the operator is still the loop**. ✅ **Its design is now a
  CONVERGED spec** (`docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md`, 2026-07-15);
  **build pending.** Still the single largest gap — but the path from here is now planned, not blank. ⚠️ **Build it
  AFTER the first mission** (which yields the real capacity numbers its autoscaling needs), and **reconcile it
  against the enforcement architecture FIRST** — its 07-15 converger predates `review_rubric.py`, so as-spec'd it
  would run **un-armed reviews**; the converger MUST call `review_rubric.py` in code (Cargo order #4 — the biggest
  synergy: rubric injection lands in Tier-1 code, not Tier-2 prose).
- **R8 — the loops live in prose, not code** (design done). Every `*-review` command *tells* an agent to
  converge to a no-op; a driver would *run* that loop. The CONVERGED driver spec designs exactly this (the
  converge-to-no-op loop around vendored `fanout` = the BUILD core). **Prose is not enforcement** — and that is the lesson the rest of
  this repo keeps re-learning.
- **Fabrik-managed twins + Zed extension** — the ettw chain (`00`–`11`), the folder-neutral `/fabrik-workflow-review` skill, **and now the `mega` parity are DONE** (2026-07-18: `00`/`02`/`03` brought to the enforcement bar, `04` is the convergence twin, `05` retired, and — **D2 corrected** — the tool-less `-command` twins were **archived** since Traycer-desktop is Claude-Max-powered and tool-capable; there is now **ONE tool-capable `-fabrik` command set**). What remains here is only building the **Zed-ACP orchestration extension** (D-Zed) as the alternative front-end — Traycer-desktop is the current cockpit.
- **Enforcement architecture (the reliability ladder) — ✅ EXECUTED 2026-07-19** (merge `5a5184a2`; all 4 phases review-looped to no-ops; fleet-synced to 46 projects). The keystone that makes autonomy *trustworthy*: mechanical gates (Tier 1) · self-sufficient compiled commands (Tier 2) · armed adversarial review — `scripts/review_rubric.py` injects the matched rule rubric + the mandatory-core floor into every finder (Tier 3, live in `/fabrik-review` + mega-`04` + ettw-`08`/`10`), with the honest bound that Tier 3 raises compliance *probability*, not certainty (**L1**) — which is *why the two human gates stay*. Spec (`docs/superpowers/specs/archived/2026-07-18-fabrik-factory-architecture-design.md`) + plan (**archived**: `docs/development/plans/archived/2026-07-18-plan-2-fabrik-factory-enforcement-architecture.md`). Standing direction: *drain Tier 3 into Tier 1* — every grep-able mandate migrates to a `check_*` gate over time, so the ladder gets sounder. Directly serves **R7/R8** (converge-to-no-op; prose→enforcement).
- Phase-4 capacity measurement (real per-worker numbers).
- Vibe Kanban parked service — leave or remove.
