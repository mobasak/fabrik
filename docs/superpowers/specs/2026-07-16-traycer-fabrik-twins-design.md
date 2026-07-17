# Design — Traycer workflow `-fabrik` twins (both folders)

Status: CONVERGED (via /fabrik-spec-review; re-converged after situating the twins in the full end-to-end factory + two orchestration modes — pool + native Opus, no-op)
Date: 2026-07-16
Owner: ob@ocoron.com
Governs: `docs/traycer/mega-epic-breakdown/**` + `docs/traycer/epic-to-ticket-workflow/**`

## Problem

The Traycer planning workflow is two folders of **stale, tool-less prose** meant to be pasted into the Traycer GUI:

- **`mega-epic-breakdown/`** — vision → independent epics (`00-trigger` → `02-epic-decomposition` → `03-expand-epic-files` → `04-cross-epic-validation` → `05-dispatch-epic-tickets`).
- **`epic-to-ticket-workflow/` (ettw)** — one epic → tickets → deploy (`00-trigger` → `01-epic-brief` → … → `10-cross-artifact-validation` → `11-deploy`).

In the autonomous factory (north-star D3/D4/R14), the **driver (Opus 4.8) must RUN these directly**, not a human pasting them into a GUI. So each `-command` source gets a tool-capable **`-fabrik` twin**: accurate-by-construction (grounded against real code, no stale anchors), disk-reading, dispatching through `libs/subagents`, and **converged to a no-op**.

## Why now / why this shape

- Traycer is **not retired** (owner-confirmed) — the GUI path must keep working during the transition, so each twin's grounding pass also fixes the `-command` source's **load-bearing** stale anchors (near-free), without converging the source itself.
- The twins are the **template the whole factory copies** — a defect in a converged twin propagates. Hence the convergence discipline is non-negotiable.

## The end-to-end factory these twins serve `[canonical: docs/orchestrator/00-autonomous-factory-north-star.md § The two-workflow factory]`

The `-fabrik` twins are the **command layer of the Fabrik-managed workflow** — one part of a larger idea→deploy factory. Both `docs/traycer/` chains run the **same pipeline**, differing only in **who orchestrates**. Each step is converged to a no-op by its paired review before the next starts:

1. **Front door** — a new *or existing* idea/plan → interactive Q&A → project **type · scope · requirements · data contract · GUI/screens · backend · frontend**. This is the **existing** Fabrik pipeline: `/fabrik-spec` → `/fabrik-data-contract` → *(GUI)* `/fabrik-ui-design` → `/fabrik-plan-after-chat`, grounded against the applicable `.windsurf/rules` packs + `AGENTS.md` + `CLAUDE.md`.
2. **Epic decomposition** — `mega-epic-breakdown/` splits the agreed vision into independent epics.
3. **Scaffold** — `fabrik scaffold` (one of the 11 types) if the project doesn't exist; else **review it and bring it to 100 % compatible** with the agreed `shape:`.
4. **Per-epic → tickets** — each epic runs `epic-to-ticket-workflow/` (`00-trigger` → `01-epic-brief` … → `11-deploy`).
5. **Per-ticket execution** — subagents (`claude -p` + the `libs/subagents` pool), coder + reviewer, converged per ticket.

**Two orchestration modes (both kept — north-star D2):** **Traycer-managed** = the `-command` files in the Traycer GUI (a VS Code extension, tool-less chat, its own review workflow); **Fabrik-managed** = the `-fabrik` twins orchestrated by **Opus over ACP in Zed** — the front-end will be a **Zed extension** (analog of Traycer-in-VS-Code), built **after** both folders' commands are finalized (north-star D-Zed).

**This spec's BUILD scope** = the Fabrik-managed workflow's **command twins** (both folders) + **extending the shared artifact-convergence review skill to be folder-neutral** (`/fabrik-ettw-review` → `/fabrik-workflow-review`). The front-door commands (`/fabrik-*`), `fabrik scaffold`, and `libs/subagents` **already exist** (reused, not built here); the **Zed extension is a later deliverable** — tracked, out of this spec's build scope.

## Capability delta — Traycer incapability → Fabrik capability

The twin is not a re-format of the source; it exists to **do what Traycer structurally cannot**. Traycer is a GUI planner with **no tools** — it reads only pasted context, runs no shell, has no web access, dispatches nothing, and loops through a human copy-paste. Each twin closes a specific gap with a specific Fabrik capability. This is the *why* behind the enforcement bar below; no twin should ship without the capabilities its role needs.

| Traycer incapability | Fabrik capability the twin adds | Which twins gain it |
|---|---|---|
| Can't read disk → cites `path:line` from pasted memory (ungrounded / hallucinated) | **Disk-reads** — grounds every anchor/count/trigger against the real file | **all** |
| Can't run shell → no gate, no git, no inspection | **Shell** — `final_gate.py --check`, `git`, spec/compose inspection | **all** |
| No web tools → external facts from training memory (stale by construction) | **Live research** — `fanout("research")` grounders (exa/brave/firecrawl/context7) re-verify each external fact/best-practice live | mega-`00` (its `/fabrik-spec` live-research gate); ettw `00`–`03` where the source touches a vendor |
| Can't dispatch → serial, single-agent, no flywheel | **Subagent dispatch for the twin's own producing work** — pool `fanout` + native, records the flywheel | **producing**: ettw `06`/`07` (coders), review twins `08`/`10`/mega-`04` (finders), mega-`00` (research grounders), mega-`03` (one grounder per epic file). ⚠️ **Decision (this spec):** the mega doers dispatch subagents for the **grounding/research** legs only — the **synthesis/decision** (the decomposition, the epic-file content, the vision) stays the **driving Opus's**, exactly as `/fabrik-spec` and `/fabrik-plan-after-chat` do. mega-`02`'s decomposition is single-agent judgment (+ optional grounder fan-out for its consistency checks). |
| No loop mechanism → one pass, human decides "good enough" | **Convergence-to-no-op** — pool+native finder loop, md5-stable | doers (paired review) / review twins (own loop) |
| Human paste-loop between every step | **Autonomous driver** — Opus 4.8 runs the chain between the R14 two gates | the driver runs all; `11`/human gates excepted |

**Litmus per twin:** *"which of these capabilities does this twin's role require, and does its `-fabrik` text actually use them?"* — the first five are text-encoded per twin; the sixth (autonomous-driver) is a property of the chain the driver runs, assessed at the chain level, not per-twin. A twin that merely re-formats the source (no disk-reads, no dispatch where its role needs it) has not closed the gap — it is not done.

## The enforcement bar (what "same detail as the fabrik commands" means)

Each twin carries the enforcement **appropriate to its role** (mapped in the parity matrix below — a human-gated `11` or a thin dispatcher `05` applies less than a full doer), drawn from the same discipline the `/fabrik-*` commands enforce: the north-star CC1–CC7 build principles `[canonical: docs/orchestrator/00-autonomous-factory-north-star.md § Command-chain build plan]`. That discipline set:

1. **Grounding** — every claim (anchors, counts, triggers) verified against real `path:line`; the stale source is a map of what to verify, never truth.
2. **CC2 citation discipline** — provenance-tagged `[canonical: …]` / inlined / zero hollow (checklist **item 132**), plus a `Reads:` budget header (anti-bloat, anti-poisoning).
3. **Convergence-to-no-op via a SEPARATE fresh-context review (CC1)** — a doer produces; a *separate* review forces the fixed point, because "a fresh-context review converges better than a loop embedded in the doer's own blind-spot-sharing context." Proven by an **md5-stable no-op round** (Pass Ledger, `found:0, fixed:0`).
4. **The pool + native-Opus review floor** `[canonical: .windsurf/rules/core/62-using-subagents.md § Dispatch policy]` — every review dispatches **both** the OpenRouter pool breadth (`fanout("review", …)`, records the flywheel via `set_quality`) **AND ≥1 native `fabrik-reviewer` on Opus** (the pool never runs `anthropic/*`). Evidence it earns its cost this build: the pool caught real defects native Opus missed on ettw `09` (recorded in the `1fd8dfdb` commit body) — complementary recall, not a reversal of the standing "native Opus catches what the pool misses" lesson.
5. **Checklist yardstick** — `EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md` (ettw) / `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` (mega), 0-FAIL.
6. **Termination contract** — the review loops inside one invocation to the no-op; never hand back on a non-zero ledger row.

The autonomous twins additionally encode: dispatch through `libs/subagents` (`pick_models`/`fanout`, live roster — never hard-coded), the coder tiers (`06-ticket-breakdown-fabrik` § Step 9: simple→pool `pick_models("code")` ≤$1.5; complex→mid pool or `claude -p sonnet`; critical→`claude -p opus`), and the **3 BLOCKED halt cases** `[canonical: CLAUDE.md § Behavior]` as the only stops **within the autonomous execution loop** (a `09` operator scope-decision is a plan-level re-steer — a requirements change re-opening the plan-in gate — not an execution stop).

## Scope — role-parity across BOTH folders

The mega tier is **purely spec / plan / decompose / review / dispatch** — GUI and coding are delegated *downward* to the per-epic ettw chain (GUI to the design step — ettw `02-core-flows-fabrik` + the `/fabrik-ui-design` command; coding to ettw `07-execute-fabrik`), so there is **no mega GUI or coding command** to build.

| Command | Role | Fabrik-command analog | Enforcement it must carry |
|---|---|---|---|
| ettw `00`–`06` | producers (trigger/spec/plan/deploy-plan/outline/breakdown) | `/fabrik-spec`, `/fabrik-plan-after-chat`, `/fabrik-data-contract` | CC2 + convergence via shared `/fabrik-workflow-review` |
| ettw `07` | autonomous execution | `/fabrik-execute-plan` | dispatch + per-ticket converge; paired review = `08` |
| ettw `08` | code-vs-spec review | `/fabrik-review` | pool+native, loop-to-no-op (CC5) |
| ettw `09` | requirements revision | *(re-steer)* | operator decides + autonomous re-exec; paired review = `10` |
| ettw `10` | spec-vs-spec cross-artifact review | `/fabrik-review`/`/fabrik-plan-review` | pool+native, loop-to-no-op (CC5) |
| ettw `11` | deploy-out human gate | *(none — 2nd human gate, R14)* | **not** autonomous; different shape |
| mega `00` | vision/intake + fabrik-lib verdict | **`/fabrik-spec`** | CC2 + convergence via `/fabrik-workflow-review` + a BLOCKING live-research grounding gate |
| mega `02` | decompose into epics | **`/fabrik-plan-after-chat`** | CC2 + convergence via `/fabrik-workflow-review` |
| mega `03` | produce epic-file specs | **`/fabrik-spec`** (spec/epic-brief role) | CC2 + convergence via `/fabrik-workflow-review` |
| mega `04` | cross-epic integration review | **`/fabrik-review`** | pool+native, loop-to-no-op |
| mega `05` | dispatch epics to ettw | *(dispatcher)* | thin — reviews live downstream in ettw |

## Current state (grounded 2026-07-16)

- **ettw `00`–`11` `-fabrik`: DONE** — each grounded + converged to an md5-stable no-op, checklist clean, gate green, committed. `11-deploy-fabrik` landed this run (`1fd7d432`) as the deploy-out HUMAN gate: the driver prepares and verifies, the operator runs `fabrik apply`; the driver runs no `fabrik` command.
- **mega `00`/`02`/`03`/`04`/`05` `-fabrik`: DONE** — all five now carry a `Reads:` budget + `[canonical:]` citations and are converged to md5-stable no-ops (`08b84c4a`, `7b6c0584`, `c7c1ba05`, `d87cab4c`). Dispatch per § Capability delta: `00` fans out research grounders, `03` one adjudicator per epic file, `04` the review finders; `02` is correctly single-agent (its decomposition is judgment, and the Vision Summary arrives pre-grounded). Both Traycer twins were kept in factual + logic lockstep throughout.
- **The convergence review reaches mega** — `~/.claude/commands/fabrik-workflow-review.md` (renamed from `fabrik-ettw-review`, `962fd46f`) is folder-neutral: the `type` argument selects the yardstick by PATH, never a count. It serves the producer doers only — ettw `00`–`06` and mega `00`/`02`/`03`; `07`→`08` and `09`→`10` have dedicated paired reviews and `11` is a human gate.
- **Mega checklist parity closed** — `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` is now **102 items**; the hollow-citation item (#102) was added to match ettw's #132.
- **The 02→03→04→05 persistence contract is closed** (`d87cab4c`) — `02` decides and persists nothing; `03` writes the tickets to `docs/development/epics/` AND the Infrastructure Decisions spec (carrying 02's Deferred Compliance appendix) to `docs/superpowers/specs/`; `04` reads that spec from disk; `05` dispatches. Before this, every ticket referenced a spec that died with the session, so the cold-context promise was false.


## Success criteria

1. Every `-fabrik` twin in both folders is grounded (no stale anchor) and converged to an **md5-stable no-op** — doers via their paired review, review twins (`08`/`10`/mega `04`) via their own loop-to-no-op, the human-gated `11` and thin dispatcher `05` via a grounding+consistency pass — checklist 0-FAIL + item-132, gate green, committed with provenance trailers.
2. Every mega **doer** has a convergence review — via **`/fabrik-workflow-review <artifact> <type>`**: the existing `/fabrik-ettw-review` **EXTENDED to be folder-neutral and renamed**, *not* a second skill. It gains the mega types (`vision-summary`/`epic-decomposition`/`expanded-epic-files`), a **type-conditional yardstick** (ettw types → `EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md`; mega types → `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` — by path, never a hard-coded item count), generalized item refs (no hardcoded 126/127/132), and a folder-derived `project=`. Its 8 existing callers are updated **two different ways**: the 7 ettw `00`–`06` footers by a **mechanical name swap**; the north star by a **semantic rewrite** (its status prose → past tense, dropping the now-false "the shared `/fabrik-ettw-review` skill exists" clause — a find-replace there would leave the canonical doc asserting a file that no longer exists). `04` **is** the cross-epic review, rebuilt to the pool+native loop-to-no-op discipline. **A duplicate `/fabrik-mega-review` is explicitly rejected** — ~83 % of the 47-line skill is folder-neutral machinery — only ~8 lines are ettw-bound (frontmatter `description`, the L5 body framing, the `Reads:` header, the `type` enum, the three item refs 126/127/132, the `project=` label); duplicating it to vary those violates CC1 + "extend, don't duplicate."
2a. The **mega checklist gains a hollow-citation item** (the ettw-132 analog), closing the CC2 yardstick gap.
3. Role-parity achieved: where a mega command's role matches a fabrik command, it carries the same enforcement (esp. mega `00` gets `/fabrik-spec`'s live-research gate).
4. Traycer GUI path intact — each `-command` source's load-bearing stale anchors fixed in the grounding pass.
5. **Capability delta closed** — each twin passes the § Capability-delta litmus: it actually USES every Fabrik capability its role requires (disk-reads; shell; live research where it touches external facts; subagent dispatch for its producing work per the decision above; convergence), not merely re-formatting the source.
6. **Factory-fit** — the converged twins slot into the end-to-end pipeline (§ The end-to-end factory): the mega chain consumes the front-door output and the ettw chain consumes each dispatched epic, so a full idea→deploy run is executable in the Fabrik-managed mode once `11-deploy` + the mega parity land (the Zed extension then makes it interactive — later).

## Out of scope

- The Traycer `-command` sources' full convergence (legacy; only load-bearing anchor fixes).
- The autonomous driver itself `[canonical: docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md]`.
- The **Zed-ACP orchestration extension** — the Fabrik-managed front-end (north-star D-Zed); built **after** both folders' commands are finalized, tracked here but not built by this spec.
- The **front-door commands** (`/fabrik-spec`/`-data-contract`/`-ui-design`/`-plan-after-chat`), `fabrik scaffold`, and `libs/subagents` — they **already exist** and are reused, not (re)built here.
- Any mega-tier GUI/coding command (delegated to the per-epic ettw chain).

## Residuals / risks

- **Shared-tree concurrency** — both folders are edited by sibling AIs; every commit stages explicit paths, `git commit -- <paths>`, provenance trailers (a lint-ratchet false-positive from a sibling's Python already occurred this build and was correctly *not* touched).
- **Roster drift** — the pool coder/reviewer roster must stay LIVE via `pick_models`, never snapshotted into a twin.
- **Checklist drift** — the two `EVALUATION_CHECKLIST_*` files are the yardstick; a hard-coded item count in any twin/source is a defect (already dropped from converged twins + sources).
