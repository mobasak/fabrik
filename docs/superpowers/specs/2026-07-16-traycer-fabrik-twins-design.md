# Design — Traycer workflow `-fabrik` twins (both folders)

Status: CONVERGED (internal-tooling spec — the design is settled in the north-star § Command-chain build plan, CC1–CC7; this consolidates it + the cross-folder remaining work)
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

## The enforcement bar (what "same detail as the fabrik commands" means)

Every twin carries the same bar the `/fabrik-*` commands enforce, governed by CC1–CC7 `[canonical: docs/traycer/00-autonomous-factory-north-star.md § Command-chain build plan]`:

1. **Grounding** — every claim (anchors, counts, triggers) verified against real `path:line`; the stale source is a map of what to verify, never truth.
2. **CC2 citation discipline** — provenance-tagged `[canonical: …]` / inlined / zero hollow (checklist **item 132**), plus a `Reads:` budget header (anti-bloat, anti-poisoning).
3. **Convergence-to-no-op via a SEPARATE fresh-context review (CC1)** — a doer produces; a *separate* review forces the fixed point, because "a fresh-context review converges better than a loop embedded in the doer's own blind-spot-sharing context." Proven by an **md5-stable no-op round** (Pass Ledger, `found:0, fixed:0`).
4. **The pool + native-Opus review floor** `[canonical: .windsurf/rules/core/62-using-subagents.md § Dispatch policy]` — every review dispatches **both** the OpenRouter pool breadth (`fanout("review", …)`, records the flywheel via `set_quality`) **AND ≥1 native `fabrik-reviewer` on Opus** (the pool never runs `anthropic/*`). Evidence it earns its cost this build: the pool caught real defects native Opus missed on ettw `09`/`10`.
5. **Checklist yardstick** — `EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md` (ettw) / `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` (mega), 0-FAIL.
6. **Termination contract** — the review loops inside one invocation to the no-op; never hand back on a non-zero ledger row.

The autonomous twins additionally encode: dispatch through `libs/subagents` (`pick_models`/`fanout`, live roster — never hard-coded), the coder tiers (`06-ticket-breakdown-fabrik` § Step 9: simple→pool `pick_models("code")` ≤$1.5; complex→mid pool or `claude -p sonnet`; critical→`claude -p opus`), and the **3 BLOCKED halt cases** `[canonical: CLAUDE.md § Behavior]` as the only non-autonomous stops.

## Scope — role-parity across BOTH folders

The mega tier is **purely spec / plan / decompose / review / dispatch** — GUI and coding are delegated *downward* to the per-epic ettw chain (`/fabrik-ui-design`, `07-execute`), so there is **no mega GUI or coding command** to build.

| Command | Role | Fabrik-command analog | Enforcement it must carry |
|---|---|---|---|
| ettw `00`–`06` | producers (trigger/spec/plan/deploy-plan/outline/breakdown) | `/fabrik-spec`, `/fabrik-plan-after-chat`, `/fabrik-data-contract` | CC2 + convergence via shared `/fabrik-ettw-review` |
| ettw `07` | autonomous execution | `/fabrik-execute-plan` | dispatch + per-ticket converge; paired review = `08` |
| ettw `08` | code-vs-spec review | `/fabrik-review` | pool+native, loop-to-no-op (CC5) |
| ettw `09` | requirements revision | *(re-steer)* | operator decides + autonomous re-exec; paired review = `10` |
| ettw `10` | spec-vs-spec cross-artifact review | `/fabrik-review`/`/fabrik-plan-review` | pool+native, loop-to-no-op (CC5) |
| ettw `11` | deploy-out human gate | *(none — 2nd human gate, R14)* | **not** autonomous; different shape |
| mega `00` | vision/intake + fabrik-lib verdict | **`/fabrik-spec`** | + BLOCKING live-research grounding gate |
| mega `02` | decompose into epics | **`/fabrik-plan-after-chat`** | CC2 + convergence |
| mega `03` | produce epic-file specs | **`/fabrik-spec`/epic-brief** | CC2 + convergence |
| mega `04` | cross-epic integration review | **`/fabrik-review`** | pool+native, loop-to-no-op |
| mega `05` | dispatch epics to ettw | *(dispatcher)* | thin — reviews live downstream in ettw |

## Current state (grounded 2026-07-16)

- **ettw `00`–`10` `-fabrik`: DONE** — each grounded + converged to an md5-stable no-op, checklist + item-132 clean, gate green, committed (`de0fb8f1` 08 · `1fd8dfdb` 09 · `f1c246d9` 10, and earlier for 00–07). Shared review skill **`/fabrik-ettw-review`** exists.
- **ettw `11-deploy`: NO twin yet** — remaining.
- **mega `00`/`02`/`03`/`04`/`05` `-fabrik`: exist but PRE-discipline** — a scan shows **no** `Reads:` header, **zero** `[canonical:]` citations, **no** pool+native review floor, **no** termination contract; `04` is a single-pass "quality auditor", not a converging review. **No `/fabrik-mega-review` skill.**

## Success criteria

1. Every `-fabrik` twin in both folders is grounded (no stale anchor), converged to an **md5-stable no-op** via its paired review, checklist 0-FAIL + item-132, gate green, committed with provenance trailers.
2. Every mega **doer** has a convergence review — the shared **`/fabrik-mega-review <artifact> <type>`** skill (sibling of `/fabrik-ettw-review`) for `00`/`02`/`03`; `04` **is** the cross-epic review, rebuilt to the pool+native loop-to-no-op discipline.
3. Role-parity achieved: where a mega command's role matches a fabrik command, it carries the same enforcement (esp. mega `00` gets `/fabrik-spec`'s live-research gate).
4. Traycer GUI path intact — each `-command` source's load-bearing stale anchors fixed in the grounding pass.

## Out of scope

- The Traycer `-command` sources' full convergence (legacy; only load-bearing anchor fixes).
- The autonomous driver itself `[canonical: docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md]`.
- Any mega-tier GUI/coding command (delegated to the per-epic ettw chain).

## Residuals / risks

- **Shared-tree concurrency** — both folders are edited by sibling AIs; every commit stages explicit paths, `git commit -- <paths>`, provenance trailers (a lint-ratchet false-positive from a sibling's Python already occurred this build and was correctly *not* touched).
- **Roster drift** — the pool coder/reviewer roster must stay LIVE via `pick_models`, never snapshotted into a twin.
- **Checklist drift** — the two `EVALUATION_CHECKLIST_*` files are the yardstick; a hard-coded item count in any twin/source is a defect (already dropped from converged twins + sources).
