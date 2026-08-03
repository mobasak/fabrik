---
description: Converge a FROZEN docs/ui-design.md to a fixed point — an INDEPENDENT adversarial review of the UI/UX design contract (design-system integrity, data-wiring vs docs/data-contract.md, screen/flow coverage, minimal-click flows, surface-pack + a11y conformance, consistency) → an edit-free no-op round. The design-time analogue of /fabrik-spec-review; distinct from /design-review (rendered UI) and the Build Verification Loop (built screens). Runs after /fabrik-ui-design, before planning.
argument-hint: "[path to docs/ui-design.md — omit to use the current project's frozen UI design contract]"
---

Converge this UI/UX design contract to a fixed point — do not stop after one pass. **Fixed point = a full review
round that needs no edits.** This is to `/fabrik-ui-design` what `/fabrik-spec-review` is to `/fabrik-spec`: the
adversarial, INDEPENDENT hardening of a design artifact its author already self-converged (`/fabrik-ui-design`
froze it; that pass cannot see its own blind spots — this one can). The things a design contract gets wrong —
and the ones this pass exists to catch — are **(1) a screen that renders a field the data contract doesn't have
(or invents a component the design system doesn't define), (2) a spec task with no flow, a flow with no screen,
or a screen no navigation reaches, and (3) a flow that quietly blew its click budget.** All are invisible until
someone re-grounds the contract against the spec, the data contract, the design system, and the surface pack.

**Where this sits in the three UI review layers (do not conflate them):**
1. **`/fabrik-ui-design-review` (THIS) — the design CONTRACT, at design time.** Reviews `docs/ui-design.md`
   itself against its sources. No running app, no pixels — the artifact.
2. **Build Verification Loop (in `/fabrik-ui-design`) — the BUILT screen vs the contract, at build time.**
   Drives the running UI, asserts it matches the frozen contract (a11y/visual/token gate).
3. **`/design-review` — the RENDERED UI's craft, at build time.** Aesthetic / UX / responsive critique of the
   live screen. Complements #2.
This command is #1: it never opens a browser — it grounds text against text.

{{include:term-edit}}
(After the no-op: the approval gate at the end.)

{{include:grounding-artifact}}
- Also read the frozen `docs/data-contract.md` for every field a screen binds — a field not backed by a real column is an invented-surface defect.

## Phase 0 — Establish scope

The contract under review is `$ARGUMENTS` (if empty, the current project's `docs/ui-design.md` — locate it and
state which file + its `Surface:` and `Design system:` header values). **It MUST be `Status: FROZEN`** — if it's
still `DRAFT`, stop and route back to `/fabrik-ui-design` (you review a frozen artifact, you don't finish its
authoring). Scope = every screen, every flow, every IA node, every per-screen component/state/field mapping,
checked against its four binding sources, all read THIS session:
- the **`/fabrik-spec` design doc** (the product's goal + core workflow — the tasks the UI must serve),
- **`docs/data-contract.md`** (the FROZEN field dictionary — screens may render only these),
- the **established design system** (`.windsurf/rules/core/ocoron-design-system.md` / `.windsurf/rules/core/tojlo-design-system.md`; mobile surface → the RN variants `.windsurf/rules/mobile-app/ocoron-mobile-design-system.md` / `tojlo-mobile-design-system.md` / the project's
  `docs/design-system.md` — the only components/tokens/states a screen may use),
- the **surface pack** for the contract's `Surface:` — `saas/60-saas-ui.md` (web page inventory) ·
  `mobile-app/80-mobile.md` (RN screen inventory + a11y) · `chrome-ext/70-chrome-ext.md` (MV3 surfaces) ·
  `desktop-app/72-desktop.md`. Read the pack(s) that match.

## Phase 1 — Adversarial grounding to a fixed point (parallel grounders per axis)

Treat every screen/flow/mapping as unproven until verified against those sources. Run repeated passes until one
demonstrably-thorough pass finds zero new gaps. Cover six axes — one INDEPENDENT grounder each when the contract
is large; **spot-verify against the spec's INTENT, since the written spec can itself be wrong.**

**A) Design-system integrity.** Every screen's components (Phase-5 blocks) come **only** from the established
system — flag any bespoke/invented component where a system primitive exists, any off-token visual, any screen
missing its enriched states (loading/empty/error/permission-denied/success/partial/disabled). If the system was
CREATED (not adopted), confirm it defines every component the screens reference — a screen citing a component
the design system never defined is a defect on one side or the other; reconcile it. **For a shadcn-based system,
verify each referenced component actually exists** via the connected **shadcn MCP**
(`mcp__shadcn__search_items_in_registries` / `view_items_in_registries`), and re-check any component-library API
the contract leans on (Radix/NativeWind/Tamagui) with `mcp__context7`; a contract naming a component that isn't
real is a defect.

**B) Data-wiring vs the FROZEN data contract.** For **every** field any screen reads or writes, OPEN
`docs/data-contract.md` and confirm the entity/field exists with a compatible type. Flag: an **invented field**
(on a screen, absent from the contract) and an **orphan** (in the contract, surfaced on no screen, when the spec
implies it should be). A screen showing a field the data contract lacks is the #1 UI-contract defect — reconcile
it in the data contract (via `/fabrik-data-contract`), never by silently adding it here.

**C) Coverage / completeness.** Every spec task has a flow (Phase 3); every flow's screens are in the inventory
(Phase 2); every inventory screen is reachable in the IA (Phase 4) — hunt orphaned screens and dead nav nodes.
Every auth level (public/authed/admin) a screen claims is consistent with the spec. No placeholders
(`TBD`/`TODO`/"tbd screen").

**D) Flows — minimal-click + logical.** Recompute each flow's click count against its budget — **any flow over
budget is a defect the author was supposed to redesign, not ship;** flag it. Confirm each primary task has a
one-action entry from the dashboard/home; that error/empty/dead-end paths are named, not just the happy path;
that no flow routes through a screen the inventory doesn't list.

**E) Surface-pack + accessibility conformance.** The screen inventory + nav match the surface pack's mandated
inventory and conventions (e.g. web landing/login/dashboard/settings/billing; MV3 popup+options mandatory;
mobile tab/stack structure). Accessibility-by-design is present per the pack (WCAG 2.2 AA baseline, target sizes
— 44/48dp mobile, focus order, keyboard reachability, dark+light). A surface-pack rule the contract violates:
the pack wins — flag and fix.

**F) Consistency + internal contradictions.** Same task-type uses the same pattern across screens; naming +
microcopy follow the design system's voice; no two sections contradict (an IA that buries a screen Phase 3 calls
primary; a state listed on one screen and forgotten on its twin).

**Parallelism — the DEFAULT for a multi-surface or multi-screen contract.** With **2+ surfaces or more than a
handful of screens**, `fanout` one INDEPENDENT grounder per axis (or per surface) — recipe in § Subagents — run
them in parallel, then merge + **REFUTE** any finding you can disprove (quote the contract line / the
data-contract field / the pack rule that makes it a non-issue) before editing. Only a tiny single-surface
contract loops solo.

After each pass, list what you re-grounded (which screens you read, which `docs/data-contract.md` fields you
confirmed, which pack rules you checked) and what you found, then fix the contract. **The loop terminates ONLY
when a full, demonstrably-thorough pass makes ZERO edits** — a no-op round is the only proof of convergence. The
pass in which you fixed anything is never the last; run one more. A pass that finds nothing must still enumerate
its coverage; an empty pass with no evidence doesn't count.

## Phase 2 — Handoff-readiness (so planning can BUILD against it without inventing)

The contract is reviewed only if a planner (Traycer or `/fabrik-plan-after-chat`) and a builder can consume it
as-is:
- **Every screen** carries a complete Phase-5 block: layout skeleton · design-system components per region ·
  enriched states · data mapping (GUI field ↔ data-contract column). A screen missing any of these is not
  build-ready — fix it.
- **Every flow** is testable by the Build Verification Loop: a named entry, an ordered click path within budget,
  a success end-state — so the built screen can be asserted against it.
- **The freeze is real:** `Status: FROZEN` + `Version` + `Date` + `Surface` + `Design system` header set; the verbatim
  freeze rule present. If your review edited anything, the freeze is stale — see Convergence.

## Phase 3 — The contract must make each screen build-verifiable

Verify (add/fix if missing) that the frozen contract lets the downstream build enforce it:
1. **Every screen's states are enumerated** — so the Build Verification Loop can assert each is rendered (a
   screen with only a happy-path state is under-specified).
2. **Every flow has a click budget** — so "minimal-click" is a checkable number at build time, not a vibe.
3. **Every field maps to a data-contract column** — so "no invented field" is mechanically checkable against
   `docs/ui-design.md` + `docs/data-contract.md` during the build loop.
A contract that can't be build-verified against its own claims isn't done.

## Convergence & residuals

Do not promise "100% coverage" — iterate to a fixed point, then enumerate residual unknowns / assumptions /
out-of-scope risks, separating **resolved** from **still-open** (each open one with a named resolution step).
**Convergence = a full review round (all axes + merge/refute) that produced ZERO edits.** That edit-free,
md5-verified round is the ONLY thing that earns the independent-review attestation; your say-so or "I fixed what
I found" does not.

- **Clean no-op (no edits):** the FROZEN contract stands. Add a one-line attestation to its header —
  `Independently reviewed: v<N> — /fabrik-ui-design-review no-op <YYYY-MM-DD>` — and report the Pass Ledger.
- **You edited the contract:** editing a FROZEN artifact re-opens it — per the freeze rule, **bump `Version` and
  re-freeze** (the edit-free confirming pass above IS the re-freeze convergence). Only then attest.
- **A BLOCKING gap remains** (a screen needs a field the data contract lacks and you can't reconcile it here; a
  spec task with no resolvable flow): stop, set `Status: DRAFT`, name the blocker, route to `/fabrik-ui-design`
  (or `/fabrik-data-contract` for a field gap). Do NOT attest.

**Do not commit** unless the user says so this turn (`git add` is fine).

## After the attestation — STOP and ask for the user's UI approval (do NOT auto-chain)

Like `/fabrik-spec-review`, this is a **design approval gate**: a frozen UI contract commits agents to build
every screen/flow in it, so a **human signs off on the UI before planning/building begins.** Once the edit-free
no-op round earns the attestation:

- **Present** the reviewed contract + a short summary (screens, key flows + their click budgets, any
  reconciliations) + the full Pass Ledger, and **STOP — explicitly ask the user to approve the UI design.**
- **Do NOT auto-invoke planning.** Name what comes next so it's clear, but don't call it: **Claude Code path** →
  `/fabrik-plan-after-chat` (references `docs/ui-design.md` + the design system + `docs/data-contract.md` as
  binding UI truth, its screen-building phases each running the Build Verification Loop to a no-op); **Traycer
  path** → paste/link the reviewed contract as the UI-epic Context File.
- Only **on the user's explicit approval (a later turn)** does planning run — and if they're on the Claude Code
  path, then auto-invoke `/fabrik-plan-after-chat` (don't make them re-type it). If they ask for changes,
  **re-open the loop** on their feedback. Never hand off on an unattested / `DRAFT` contract.

{{include:subagents-core}}
