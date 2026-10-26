---
description: Converge a FROZEN docs/ui-design.md to a fixed point — an INDEPENDENT adversarial review (design-system integrity, data-wiring vs docs/data-contract.md, screen/flow coverage, click budgets, surface-pack + a11y, consistency + internal contradictions) → edit-free no-op. Distinct from /fabrik-ui-design (author self-convergence; this is the INDEPENDENT author-blind pass AFTER it), /design-review (rendered UI), and the Build Verification Loop. TRIGGER — EN: "review/harden this UI design contract", "is this ui-design.md ready"; TR: "bu UI tasarım sözleşmesini gözden geçir", "bu ui-design.md hazır mı" — fires on a FROZEN contract, never a running app (→ /design-review) or a plan review (→ /fabrik-plan-review). Stage: 2-contract.
argument-hint: "[path to docs/ui-design.md — omit to use the current project's frozen UI design contract]"
---

Converge this UI/UX design contract to a fixed point — do not stop after one pass. **Fixed point = a full review round that CONFIRMS zero — the Termination contract's closing round.** This is the INDEPENDENT adversarial pass after `/fabrik-ui-design`'s author self-convergence. It reviews the design CONTRACT, at design time: `docs/ui-design.md` itself against its sources. No running app, no pixels: it never opens a browser — it grounds text against text.

{{include:run-record}}
{{include:orient}}
{{include:term-edit}}
(After the closing round: the approval gate at the end.)

{{include:grounding-artifact}}
- Also read the frozen `docs/data-contract.md` for every field a screen binds — a field not backed by a real column is an invented-surface defect.

## Phase 0 — Establish scope

The contract under review is `$ARGUMENTS` (if empty, the current project's `docs/ui-design.md`; state which file and its `Surface:` and `Design system:` header values). It MUST be `Status: FROZEN` — if it's still `DRAFT`, stop and route back to `/fabrik-ui-design`. Scope = every screen, flow, IA node and per-screen component/state/field mapping, checked against its four binding sources (a fifth, the built navigation, when the surface is already built — axis C), all read THIS session:
- the `/fabrik-spec` design doc (the product's goal + core workflow — the tasks the UI must serve),
- `docs/data-contract.md` (the FROZEN field dictionary — screens may render only these),
- the established design system (`.windsurf/rules/core/ocoron-design-system.md` / `.windsurf/rules/core/tojlo-design-system.md` — a house brand only when the project declares it; a Tojlo mobile surface adds `.windsurf/rules/mobile-app/tojlo-mobile-design-system.md`) / (CREATE, any surface) the project's own `docs/design-system.md`, and in every case `.windsurf/rules/core/design-system-template.md` for the structure — the only components/tokens/states a screen may use),
- the **surface pack** for the contract's `Surface:` — `saas/60-saas-ui.md` (web page inventory) · `mobile-app/80-mobile.md` (RN screen inventory + a11y) plus `mobile-app/ocoron-mobile-design-system.md` (the component patterns — every mobile project, whatever its brand or mode) · `chrome-ext/70-chrome-ext.md` (MV3 surfaces) · `desktop-app/72-desktop.md`. Read the pack(s) that match.

**Size ceiling: 25,000 tokens (about 1,100 lines) — the Read tool's page cap; a contract above it is read PARTIALLY by every seat, so the review's first finding is the split: history to `docs/archive/ui-design-history.md`, the live contract under the ceiling. Until it is split, every seat reads it in ranges and names the line ranges it read; a range no seat names is unread.**

## Phase 1 — Adversarial grounding to a fixed point (round 1 one seat per axis — the units floor, D-208; later passes the same seats over their own axes, D-335)

Treat every screen/flow/mapping as unproven until verified against those sources. Run repeated passes until one demonstrably-thorough pass finds zero new gaps. Cover six axes, one INDEPENDENT seat per axis at round 1; **spot-verify against the spec's INTENT, since the written spec can itself be wrong.**

**A) Design-system integrity.** Every screen's components (Phase-5 blocks) come **only from the established system** — on a mobile surface built to the component patterns in `mobile-app/ocoron-mobile-design-system.md`. Flag any invented component where a system primitive exists, any off-token visual, any screen missing its enriched states (loading/empty/error/permission-denied/success/partial/disabled), and any form control that breaks `design-system-template.md` § Forms and Inline Editing, § Forms (Accessibility) or § Permissions UX. If the system was CREATED (not adopted), confirm it defines every component the screens reference — a screen citing a component the design system never defined is a defect on one side or the other; reconcile it. For a shadcn-based system, verify each referenced component actually exists via the connected shadcn MCP (`mcp__shadcn__search_items_in_registries` / `view_items_in_registries`), and re-check any component-library API the contract leans on via `WebFetch` of their official docs; a contract naming a component that isn't real is a defect. On a web surface, check the microcopy and any token the project authored beyond its kit against `frontend-design:frontend-design`'s AI-generated clusters, listed in `core/63-frontend-design.md`; a kit or house token, a pattern the template prescribes or an operator ruling is never a finding, and a finding terminates FIXED or REFUTED like any other — never by editing a frozen contract in place.

**B) Data-wiring vs the FROZEN data contract.** For **every** field any screen reads or writes, OPEN `docs/data-contract.md` and confirm the entity/field exists with a compatible type. Flag an **invented field** (on a screen, absent from the contract) and an **orphan** (in the contract, surfaced on no screen, when the spec implies it should be). A screen showing a field the data contract lacks is the #1 UI-contract defect — reconcile it in the data contract (via `/fabrik-data-contract`), never by silently adding it here.

**C) Coverage / completeness.** Every spec task has a flow (Phase 3); every flow's screens are in the inventory (Phase 2); every inventory screen is reachable in the IA (Phase 4) — hunt orphaned screens and dead nav nodes. When the surface is already built, its navigation is a fifth binding source, read this session: ground each menu/IA claim against it (the router's route table, or the surface's menu registry), not the contract's own earlier version — a tree that was never built reads as consistent with itself. Every auth level (public/authed/admin) a screen claims is consistent with the spec. No placeholders (`TBD`/`TODO`/"tbd screen").

**D) Flows — minimal-click + logical.** Recompute each flow's click count against its budget — **any flow over budget is a defect the author was supposed to redesign, not ship;** flag it. Confirm each primary task has a one-action entry from the dashboard/home, that error/empty/dead-end paths are named, and that no flow routes through a screen the inventory doesn't list.

**E) Surface-pack + accessibility conformance.** The screen inventory + nav match the surface pack's mandated inventory and conventions (MV3 popup+options mandatory; mobile tab/stack structure). Accessibility-by-design is present per the pack (WCAG 2.2 AA baseline, target sizes — 44/48dp mobile, focus order, keyboard reachability, dark+light). A surface-pack rule the contract violates: the pack wins — flag and fix.

**F) Consistency + internal contradictions.** The same task-type uses the same pattern across screens; naming + microcopy follow the design system's voice; no two sections contradict (an IA that buries a screen Phase 3 calls primary; a state listed on one screen and forgotten on its twin).

**Parallelism — UNCONDITIONAL, every round.** Dispatch one INDEPENDENT native seat per axis — recipe in § Subagents — in parallel, then merge + **REFUTE** any finding you can disprove (quote the contract line, data-contract field or pack rule that makes it a non-issue) before editing. When `dispatch_headroom.py` trims the round (its `COST:` line names units with NO seat), dispatch exactly the seats it prints, one axis each; the seatless axes are named in the round's ledger and swept by further full-pass waves before any delta pass. Round 1 is complete only when every axis has had its seat, and a seat whose slice was too large reports the screens or sections it did not reach, which join that next wave. **Never solo, never two:** a surface with fewer than three units still dispatches **THREE seats on DIFFERENT angles** over it.

After each pass, list what you re-grounded (which screens you read, which `docs/data-contract.md` fields you confirmed, which pack rules you checked) and what you found, then fix the contract. **The loop terminates ONLY at the Termination contract's closing round — the round-1 seats over their own axes at `confirmed: 0`, md5 unchanged** — the only proof of convergence. The pass in which you fixed anything is never the last; run one more. A pass that finds nothing must still enumerate its coverage; an empty pass with no evidence doesn't count.

## Phase 2 — Handoff-readiness (so planning can BUILD against it without inventing)

The contract is reviewed only if a planner (Traycer or `/fabrik-plan-after-chat`) and a builder can consume it as-is:
- **Every screen** carries a complete Phase-5 block: layout skeleton · design-system components per region · enriched states · data mapping (GUI field ↔ data-contract column) · form controls, where the screen has forms. A screen missing any of these is not build-ready — fix it.
- **Every flow** is testable by the Build Verification Loop: a named entry, an ordered click path within budget, a success end-state.
- **Every cross-reference resolves to the DESIGN it names**, not merely to a heading: if "the decision lives in §5.6", §5.6 must state that decision (its components, states or rule).
- **The freeze is real:** `Status: FROZEN` + `Version` + `Date` + `Surface` + `Design system` header set; the verbatim freeze rule present. If your review edited anything, the freeze is stale until the bump Convergence describes — owed by the orchestrator, not a seat finding.

## Phase 3 — The contract must make each screen build-verifiable

Verify (add/fix if missing) that the frozen contract lets the downstream build enforce it: every screen's states enumerated (a screen with only a happy-path state is under-specified), every flow given a click budget, and every field mapped to a data-contract column. A contract that can't be build-verified against its own claims isn't done.

## Convergence & residuals

Do not promise "100% coverage" — iterate to a fixed point, then enumerate residual unknowns, separating **resolved** from **still-open**. **Convergence = the Termination contract's closing round (all axes + merge/refute, `confirmed: 0`).** That md5-verified round is the ONLY thing that earns the independent-review attestation; your say-so or "I fixed what I found" does not.

- **Closing round at `confirmed: 0` (no edits):** the FROZEN contract stands. Add a one-line attestation to its header — `Independently reviewed: v<N> — /fabrik-ui-design-review confirmed: 0 <YYYY-MM-DD>` — and report the Pass Ledger.
- **You edited the contract:** the header keeps its reviewed `Version` (still `FROZEN`) while the fix rounds run, and every seat brief says so — an edit this review made is not an in-place-edit finding. The bump is the LAST edit, made before the closing round, which is then quiet against the bumped text. Editing a FROZEN artifact re-opens it — per the freeze rule, bump `Version` and re-freeze. The bump is a Status-flip event: **mint its `docs/DECISIONS.md` row staged in the same commit as the artifact** (classify at mint — plain row normally). Only then attest.
- **A BLOCKING gap remains** (a screen needs a field the data contract lacks and you can't reconcile it here; a spec task with no resolvable flow): stop, set `Status: DRAFT`, name the blocker, route to `/fabrik-ui-design` (or `/fabrik-data-contract` for a field gap), and **mint the `docs/DECISIONS.md` row for the FROZEN→DRAFT flip in the same commit** (classify at mint). Do NOT attest. **Close the run record on this path** — `blocked --command fabrik-ui-design-review --reason "<the gap · what you searched · what is missing>" --feedback "<...>"`; "stop" alone leaves the record `running`, which the Stop hook blocks the turn on.

`check_frozen_chain.py` grades the attestation: it WARNs when the newest `Independently reviewed: v<N>` is older than the contract's current `Version:`. A history of rounds is correct and is not drift — only the newest entry is graded — and a contract with NO attestation is silent, since most have never had a twin run. It proves the claim is CURRENT, not that it is TRUE — ledger honesty is still on you.

**Do not commit** unless the user says so this turn (`git add` is fine). ⚠️ **Superseded where it conflicts with CLAUDE.md § EXIT:** an uncommitted artifact is an UNFINISHED task and the Stop hook BLOCKS the turn on it, so **COMMIT the artifact** — on a shared tree parked WIP is the only work that can be silently destroyed, and committing a `DRAFT`/`FROZEN` artifact is not approving it; its own `Status:` line carries that. What still needs the user's word is the APPROVAL and anything beyond this artifact's own paths.

## After the attestation — the panel answers the UI approval gate

Like `/fabrik-spec-review`, this is a **design approval gate**: once the closing round (`confirmed: 0`) earns the attestation, the panel answers it; its brief carries the contract, the screens, the key flows with their click budgets and any reconciliations.

{{include:design-critique}}

{{include:design-gate-panel}}

- **On a split**, end the turn with this block, written as plain lines, not inside a code fence:

  ```
  DECISION NEEDED (ground: gate)
  - Question: Do you approve this UI design?
  - Why it is yours: UI design approval of <docs/ui-design.md path> — a frozen UI contract commits agents to build every screen/flow in it; the panel split.
  - Options: A — approve as frozen, and planning starts from this contract · B — take the disputed changes, and the loop re-opens on them.
  - Recommendation: <A or B>, with the one disputed concern that decides it.
  - Panel: opus="<its VERDICT line>" fable="<its VERDICT line>" → split
  ```

- **The next step:** **Claude Code path** → `/fabrik-plan-after-chat` (binding UI truth: `docs/ui-design.md` + the design system + `docs/data-contract.md`); **Traycer path** → paste/link the reviewed contract as the UI-epic Context File. On a split, the operator's answer decides; on requested changes, **re-open the loop**. Never hand off on an unattested / `DRAFT` contract.


{{include:subagents-core}}

{{include:close-chain}}
