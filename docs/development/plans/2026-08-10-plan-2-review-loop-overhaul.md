# Plan — Review-loop overhaul: converge in ~3 rounds instead of ~8, without losing recall

Status: CONVERGED
Owner: hub (command corpus fragments + enforcement)
Operator directive (verbatim, 2026-08-10): "we need to be faster, make less mistakes" · "i dont want
to lose functionality. also i dont want to lose time too." · "first review pass must be perfect"

## What we already agreed

- **Scope is the 3 shared FRAGMENTS** — but the blast radius is WIDER than "review commands", and
  getting this wrong was the plan's most dangerous error. Exhaustive grep of
  `commands/_sources/*.md` (not the render table):
  **`term-coverage` → 4** (`fabrik-review`, `fabrik-repo-review`, **`fabrik-user-test`,
  `fabrik-service-test`**) · **`term-edit` → 8** (`fabrik-plan-review`, `fabrik-spec-review`,
  `fabrik-ui-design-review`, `fabrik-workflow-review`, **`fabrik-features`, `fabrik-doc-converge`,
  `fabrik-data-contract`, `fabrik-ui-design`**) · **`subagents-core` → 12**. And `design-review`
  carries NO fragment at all, so this plan does not touch it.
  **The bolded consumers are not reviews:** they are the 5-certify certification gauntlets and the
  2-contract freezing / doc-convergence commands. A loop change written blindly into `term-coverage`
  rewrites the termination contract of `/fabrik-user-test` and `/fabrik-service-test`, where
  "callers and callees" is meaningless and whole uncertified journeys could escape. Phase B is
  therefore CONDITIONAL by construction (see its step 1).
- **Pass 1 sweeps the full failure-class partition wide; passes 2+ are scoped to the fix diff PLUS
  its callers/callees** (not the changed lines — today's severest bug sat in a function never
  edited). Loop terminates when a fix-diff-scoped pass finds nothing new.
- **Fix-induced findings are real and irreducible.** Counted this session: 5 of 18 native findings
  were about code created by the previous round's fixes. "First pass perfect" is the right target
  for PRE-EXISTING defects and structurally impossible overall — the loop must expect regressions
  from its own fixes rather than treat them as pass-1 failures.
- **The build-time Behavior-Contract test step already exists and is not enforced.** Mandated at
  `commands/_sources/fabrik-execute-plan.md:321`; no gate checks it ran.
- **Mutation verification is deliberately advisory** (`check_mutation.py:8-12`: opt-in via
  `FABRIK_MUTMUT=1`, "ALWAYS exits 0"). Making it blocking is the highest-risk change and is staged
  last, behind a time cap and diff scoping.
- **Rule packs are IN SCOPE** (operator, verbatim 2026-08-10): "we can change rulesets if the change
  make us better." This matters structurally: the fragments defer to
  `core/62-using-subagents.md` as "the canonical detail", so a dispatch-shape change written only
  into a fragment would leave the pack contradicting it — the divergence class this plan's fragment
  scoping exists to prevent. The canonical statement goes in the PACK; the fragment keeps pointing
  at it.
- **Three additions approved by the operator (2026-08-10 — "approved folding the three additions
  into plan-2"):** (1) a **stall circuit-breaker** in both loop fragments — 3 consecutive rounds
  with a non-decreasing count of NEW candidates STOPS the loop with `## BLOCKED: NON-CONVERGENCE`
  naming the suspected foundation error; re-grounding the design is the fix, never round N+1.
  Evidence: the deploy-triad executor spent rounds labelled up to 21 (14 fix commits,
  `e4b31ade..3b66faa1`, 15:40→19:34 the same day) on 3 files, each late round re-litigating
  semantics — measured non-convergence IS a verdict, and nothing in the current contract says so.
  (2) a **probe-duty finding class** in `term-edit.md` — pass 1 of an artifact review RE-RUNS the
  artifact's embedded probes (fenced command + output) instead of re-deriving its claims, and a
  load-bearing claim carrying NO probe is itself a standing finding ("ungrounded claim" — the class
  that cost this plan two review passes, § the grounding result below). (3) **role separation** in
  `62-using-subagents.md` — the loop-closing pass runs in a context that did not author the
  artifact; an author's own quiet round never closes the loop. Evidence: the deploy-triad plan's
  author declared a premature CONVERGED; an operator-forced independent round then found 5 findings
  the self-review had missed (commit `f598364c`, title verbatim: "independent round found 5 my
  self-review missed").
- **Operator constraints:** no functionality loss, no time loss, blast radius ~48 repos.

## Shape decision — MONOLITH (3 phases), stated per the command's Phase-2 gate

Three phases, not four+: each is the smallest unit carrying its own test cycle and worth a fresh
`/fabrik-review` (the command's own right-sizing definition). Phase A is a measurement that GATES
the others; Phase B is one coherent semantic change to the loop contract (splitting the two loop
fragments would risk exactly the divergence the fragment scoping exists to prevent); Phase C is the
enforcement backstop. Shape triggers re-checked at review pass 4 — the emit-time length projection
did NOT survive review: the file has grown past the ~300-line monolith projection (506 lines at
that pass — 505 by `git cat-file -p <pre-wave-commit> | wc -l`, the probed figure) by absorbing
review evidence and provenance, not additional work units. The other two
triggers stay inside budget: phases = 3 (not >3), and the largest phase READ set measures 46,447
bytes vs the 262,144 `READ_BUDGET_BYTES` budget (probe: `find <Phase-B files> -exec cat {} + |
wc -c`). Adjudication: the monolith STANDS — the line trigger is an emit-time projection heuristic
("both shapes are first-class, no forced migration", fabrik-plan-after-chat § Shape decision), the
executor's real burdens (phase count, read bytes) are both in budget, and re-shaping a converged
plan trades operator time for a proxy metric, against the no-time-loss constraint.

## ⚠️ The grounding result that changed the design — and the RE-grounding that reversed it

**First pass (WRONG, recorded because the error is instructive).** The plan initially rejected
"give breadth finders execution" on the theory that class-partitioned finders read the same surface,
so they cannot have disjoint `owned_paths`, so `tools_enabled=True` would collapse them into one
serial group. A pool grounder independently reached the same wrong conclusion and called arm 2
"structurally impossible".

**Re-grounding (CORRECT, read this run):** `owned_paths` governs **WRITES, not READS**.

- `libs/subagents/workspace.py:97` — `git worktree add --detach <wt> <base>`: each tool-enabled agent
  gets a **full checkout**. There is no sparse checkout; it can READ the entire tree.
- `libs/subagents/agent.py:483` — `stray = workspace.out_of_scope_paths(paths, spec.owned_paths)`
  where `paths` comes from `workspace.changed_paths` (`workspace.py:230`). The scope check is
  **post-hoc, on what the agent CHANGED**. `agent.py:13` states it outright: "a post-hoc scope check".
- `workspace.py:419` `disjoint()` groups by `owned_paths` overlap only — reads never enter it.

**Therefore tool-enabled finders CAN run in parallel:** give each one a distinct write scope (its own
report file, e.g. `owned_paths=[".tmp/finders/<class>.md"]`) and it reads the whole surface while
remaining disjoint from its siblings. The serialization trap is real, but it is triggered by EMPTY or
overlapping `owned_paths` (`workspace.py:425` — "An agent with empty `owned_paths` (unrestricted)
overlaps everything"), not by shared reads.

**Consequence for this plan:** the original proposal is viable and Phase A's arm 2 is constructible —
provided each finder declares a distinct write scope. Phase A now measures a real choice rather than
ratifying a mistaken constraint. This block stays in the plan as the standing warning: the trap is
empty/overlapping WRITE scope, and the fix is a per-finder report path, not abandoning execution.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/62-using-subagents.md` (ACTIVE, **EDITED by Phase B**) | the two parallelism shapes — read-only = the parallelism trigger, tools-enabled + overlapping `owned_paths` = serial; and the CANONICAL home the fragments defer to, so a new shape is written HERE | `.windsurf/rules/core/62-using-subagents.md:77-93`, mechanism at `libs/subagents/agent.py:636` |
| `core/45-testing-strategy.md` (ACTIVE, **EDITED by Phase C**) | test-per-behaviour, risk-ordered, TDD for the risky — and the canonical rule a new gate must cite, since enforcement with no pack rule behind it is unappealable | pack § Behavior Contract |
| `core/40-documentation.md` (ACTIVE) | command/fragment prose conventions; commands state rules present-tense, never change-history | pack § writing style |
| `core/10-python.md` (ACTIVE) | the enforcement scripts' typing/env discipline | pack § typing |
| Fragment `subagents-core.md` | the dispatch policy 12 command sources inherit (reviews AND the spec/plan/contract authors) | `commands/_fragments/subagents-core.md:3` |
| Fragment `term-coverage.md` | the code-review loop: "fresh full round after any fix", no ceiling | `commands/_fragments/term-coverage.md:13-21` |
| Fragment `term-edit.md` | the artifact-review loop (plan/spec/ui/workflow reviews + the 2-contract freeze / doc-convergence commands) | included by 8 command sources (grep-measured) |
| `check_mutation.py` | advisory by design — opt-in, diff-scoped, always exits 0 | `scripts/enforcement/check_mutation.py:8-12` |
| `fabrik-execute-plan.md` | already mandates `/fabrik-generate-tests` per phase — unenforced | `commands/_sources/fabrik-execute-plan.md:321` |
| fabrik-lib | **consulted — no applicable module.** The table has no review-orchestration, mutation-testing or gate-enforcement module (`api-smoke-test` is endpoint smoke, `llm-dispatch` is `claude -p` plumbing). Build fresh inside the existing hub enforcement surface; not a new-module candidate (hub-corpus-specific, not reusable across project types) | `/opt/fabrik-lib/README.md` module table |
| `specs/services/*.yaml` `shape:` | **N/A** — no service, no DB/cache/metrics/search/admin surface changes | — |

## Global Constraints

- **Fleet blast radius:** every file in File Scope is fleet-synced or renders box-wide. A change must
  be correct for ALL ~48 projects, not just the hub.
- **Fragments are the edit surface.** Never hand-edit a rendered command in `~/.claude/commands/`;
  never edit a consumer command source to change behaviour a fragment owns (24 consumer renders
  across the three fragments — the 4/8/12 counts above).
- **Merge-time render only:** `commands/assemble_commands.py` runs from merged master in the MAIN
  checkout — never from a worktree (the renderer PRUNES artifacts absent from the current tree).
  `--check` (temp-dir) is always safe.
- **No functionality loss** is a hard acceptance criterion, and the checklist is the FULL guarantee
  set of `term-coverage.md`, not a sample. The first draft listed five and a review found ~13; the
  omissions were the pre-pass-1 obligations and the recall machinery. Every one of these must still
  be mandated after the edit: (1) exit needs BOTH a quiet round and an adjudicated checklist ·
  (2) pre-pass-1 ANCHOR (read the newest prior review + compute the surface hash) · (3) pre-pass-1
  RUBRIC (`review_rubric.py --changed`, pasted verbatim) · (4) pre-pass-1 PERSIST (the review file
  exists before pass 1; a chat-only review does not exist) · (5) the four standing recurrence
  classes · (6) `found:` counts REFUTED candidates too · (7) every row CLEAN/FIXED/REFUTED, no
  UNCHECKED · (8) the post-fix confirming re-check, and a spot-verify is NEVER the closing round ·
  (9) mechanical gates green · (10) ledger rows name their finders; a fabricated row is forgery ·
  (11) minimum two full rounds · (12) no round ceiling · (13) return control exactly once, with the
  safety HARD STOP and "context is never a reason to stop". Gate B asserts each survives.
  Phase B ADDS a 14th — the stall circuit-breaker — and it must be WRITTEN so (12) survives
  verbatim: the breaker keys on measured NON-PROGRESS (3 consecutive rounds with non-decreasing
  new-candidate counts), never on round count; unbounded rounds while converging remain the
  contract.
- Commands state rules present-tense; change-history goes to CHANGELOG/git, never into a fragment.
- 12-Factor: N/A to prose fragments; the enforcement scripts add no logfile, no daemon, no host
  ports, no backing-service substitution.

## Phase A — Measure before changing: the finder-shape A/B

**Why first:** the only leg of the design still unproven. This session's evidence (pool 1/7 real vs
native 15/18) is n=1 and confounded — different models, different brief depth, AND different tool
access varied together. Phase B's VERIFY stage design depends on which factor dominates.

**Interfaces — Produces:** a decision record naming the winning dispatch shape Phase B transcribes —
arm 1's read-only status quo · arm 2's tool-enabled finders with per-finder report paths · arm 3's
read-only FIND + tool-enabled VERIFY over candidates — plus measured precision, recall and
wall-clock for each arm.

Steps:

0. **Toolchain preflight (first step, per the plan-review environment gate):** assert the tools the
   phase shells out to exist in the environment it runs in —
   `.venv/bin/python -c "import libs.subagents, pytest, ruff" && .venv/bin/python -m pytest --version`.
   All three arms run hub-side from `/opt/fabrik` with `.venv`; a missing one stops the phase here
   rather than mid-experiment.
1. **Ground truth without circularity.** Do NOT score arms by matching this agent's own prior ledger
   (`2026-08-10-hub-governance-gates-review.md`) — the author of that ledger is the author of this
   plan, and a grounder flagged the circularity correctly. Instead: pool every candidate from all
   arms into one anonymised list (arm labels stripped), adjudicate each ONCE by the standing
   evidence rule — reproduce it or refute it by execution — and only then attribute verdicts back to
   arms. The verdict is earned per candidate, not inherited from a prior document.
2. Run **arm 1** — `fanout("review", units=<4 class-partitioned briefs>, mode="read_only")`, the
   current shape. Record: candidates raised, how many match a known-real finding, wall-clock.
3. Run **arm 2** — the SAME 4 briefs and the SAME pinned roster (`pick_models("review", n=4)`,
   roster passed explicitly to both arms so model capability is held constant), but
   `tools_enabled=True` and **each unit owning a DISTINCT write path**
   (`owned_paths=[".tmp/finders/<class>.md"]`) so `disjoint()` puts each in its own group. **Assert
   parallelism was actually achieved** before trusting the arm: if wall-clock ≈ the sum of unit
   latencies rather than the max, the units serialized and the arm is INVALID — discard and fix the
   scopes (`libs/subagents/workspace.py:419`). Record the same three numbers.
4. Run **arm 3** — read-only FIND (arm 1's candidates) followed by a tool-enabled VERIFY pass over
   the candidate list only. Record precision after verification and total wall-clock.
5. Record **recall as well as precision** — precision alone rewards an arm that raises one safe
   finding. Recall is measured against the UNION of adjudicated-real findings across all arms (the
   best available denominator; state plainly that it is a lower bound on true defects, not absolute
   recall).
6. Write the decision record to `docs/development/reviews/2026-08-10-finder-shape-ab.md`: each arm's
   raised / real / precision / recall / wall-clock, whether arm 2 achieved parallelism, which factor
   dominates, and the chosen shape. **If no arm beats arm 1 on precision AND recall at comparable
   wall-clock, Phase B ships the loop changes WITHOUT a dispatch change** — a legitimate outcome, and
   the reason this phase runs first.

Validation gate A (runnable):
`python -c "import re,sys; t=open('docs/development/reviews/2026-08-10-finder-shape-ab.md').read();
arms=re.findall(r'arm ([123]).*?raised[:= ]+(\d+).*?real[:= ]+(\d+).*?wall[-_ ]?clock[:= ]+(\d+)', t, re.S|re.I);
sys.exit(0 if len(arms)==3 and 'CHOSEN SHAPE:' in t and re.search(r'recall', t, re.I) else 1)"` → exit 0.
Expected: three arm rows each carrying raised/real/wall-clock, a recall figure per arm (step 5's
mandate — the gate asserts the word appears; the reviewer verifies the numbers), and a line
beginning `CHOSEN SHAPE:` naming the shape and the arm that justifies it.

**Behavior Contract (Phase A):**
- **Given** three arms, **When** the A/B runs, **Then** each arm's precision and recall are
  computed against the pooled anonymised adjudication union of step 1 — never against the plan
  author's prior ledger (`2026-08-10-hub-governance-gates-review.md` is the circular baseline
  step 1 forbids).
- **Given** arm 2 uses `tools_enabled=True`, **When** its `owned_paths` overlap, **Then** the run is
  rejected as invalid (it would measure serialization, not tool access) — assert disjointness before
  dispatch (`libs/subagents/agent.py:636`).

Closing sequence: run gate A → `python scripts/enforcement/check_doc_sync.py` → **`/fabrik-review` on
Phase A's changed surface, run to its coverage-adjudicated exit** → commit with provenance trailers.

## Phase B — Rewrite the loop contract in the two loop fragments

**Interfaces — Consumes:** Phase A's chosen VERIFY shape. **Produces:** the loop semantics every
review command inherits.

Steps:

1. `commands/_fragments/term-coverage.md` — replace the round semantics. **Three corrections a
   review forced into this step; do not simplify them away:**
   - **Pass 1 is a WIDE sweep**: every class in the rubric partition is assigned to a finder in the
     SAME round. A round that samples a subset is not a pass-1.
   - **Middle passes (2 … N-1) are scoped** to the fix diff PLUS its callers and callees.
   - **The CLOSING pass is a FULL fresh sweep — non-negotiable.** The first draft made scoped
     passes run all the way to exit, which re-institutionalizes the exact defect
     `term-coverage.md:15` records ("a loop closed on 'round 11 spot-verify only' … leaving the
     post-fix surface without its full fresh sweep"). The concrete escape: pass 1's finder for class
     X samples file A and misses a class-X defect in file B; fixes land in file C; a scoped pass 2
     covers C and its neighbours; B is never re-examined and the loop exits with the defect live.
     The unbounded fresh round is the RECALL mechanism — what this plan removes is one full sweep
     PER FIX, not the full sweep itself. Net effect: 1 wide + k scoped + 1 wide, instead of k+1 wide.
   - **The scoped form applies ONLY when the review's surface is a DIFF.** `term-coverage` is also
     included by `fabrik-user-test` and `fabrik-service-test`, whose surface is journeys/personas
     /states, not a changed-file set; those keep discovery-until-dry unchanged. State the condition
     in the fragment so the gauntlets are not silently rewritten.
   - The real text forcing a full re-sweep per fix is `term-coverage.md:19` ("a fresh, independent
     round must re-adjudicate it") plus `:21` ("There is NO round ceiling") — **not** `:15`, and the
     string "a fresh, fully-independent finder round on the updated code" does NOT exist in the file
     (a review caught the first draft instructing the executor to search for a literal that isn't
     there). Edit `:19`/`:21`; leave `:15` intact, since it is the guarantee the closing sweep keeps.
   - **The stall circuit-breaker (operator-approved addition).** If 3 consecutive rounds raise a
     non-decreasing count of NEW candidates, the loop STOPS and emits `## BLOCKED: NON-CONVERGENCE`
     naming the suspected foundation error (a design claim, a contract, the decomposition) — round
     N+1 spends review time on a defect that lives UPSTREAM of the surface. This is NOT a round
     ceiling: rounds stay unbounded while the new-candidate count is falling; the breaker fires only
     on measured non-progress, and it routes to re-grounding exactly as the existing BLOCKED
     escalation (`term-coverage.md:21`) routes a thrice-stuck finding.
2. `commands/_fragments/term-edit.md` — the same round semantics for artifact reviews. This is the
   fragment that governed the quota-health spec's convergence the same day — 37 findings absorbed
   over passes 1-3, then an md5-verified no-op on pass 4 (commit titles verbatim: `4a51bc9f`,
   `0d82d67e`); the scoped-successor rule applies to prose
   identically (pass 2+ reviews the EDITS, not the whole artifact). Two additions land here too:
   the same stall circuit-breaker (term-edit's per-axis 3-attempt BLOCKED at `term-edit.md:7`
   stays — the breaker adds the LOOP-level rule the per-axis one cannot see), and the **probe
   duty**: pass 1 RE-RUNS every probe the artifact embeds (fenced command + output) rather than
   re-deriving its claims, and a load-bearing claim with NO probe is a standing finding class
   ("ungrounded claim"). The authoring-side mandate (plans/specs must CARRY probes) is deliberately
   NOT edited into `/fabrik-plan-after-chat` by this plan — outside File Scope; the review-side duty
   creates the authoring pressure, and wiring the authoring commands is a named residual.
3. **`.windsurf/rules/core/62-using-subagents.md` § Parallelism — the CANONICAL edit, and the named
   CONSUMER of Phase A's artifact** (`docs/development/reviews/2026-08-10-finder-shape-ab.md` → its
   `CHOSEN SHAPE:` line is what this step transcribes; the artifact is not written-and-never-read).
   If Phase A chose a dispatch change, add it there as a named third shape
   (`FIND read-only + parallel → VERIFY tools-enabled over the CANDIDATE list only`), with the
   serialization trap restated inline so no future editor re-makes the proposal this plan rejected.
   Writing it anywhere else leaves the pack contradicting the fragments that defer to it.
   Two more edits ride the same section pass: (a) **§ Role separation (operator-approved
   addition)** — precisely scoped: the closing round's **FINDER pass** runs in a context that did
   NOT author the artifact (a dispatched fresh subagent, or a post-compaction session re-grounding
   from disk); **adjudication — decide/refute/merge — stays with the orchestrator**, per CLAUDE.md
   § Subagent fan-out ("the decide/refute/merge you own"). The rule governs who HUNTS last, never
   who adjudicates; an author's own quiet round never closes the loop. The fragments already
   require "a fresh, independent round" (`term-coverage.md:19`); the pack defines what
   "independent" MEANS and the fragments keep pointing at it (no duplication, per step 4's rule).
   This plan's own phase-closing `/fabrik-review` rounds apply the rule from Phase A onward
   (dispatch the closing round's finders to fresh non-author subagents) — do not wait for Phase B
   to render it. (b) refresh the section's
   STALE internal citations while editing it: it currently cites `workspace.py:321` and
   `agent.py:430/:435` for mechanisms that live at `workspace.py:419-425` (`disjoint()`, "empty
   `owned_paths` overlaps everything") and `agent.py:632-636` (the grouping) — verified live
   2026-08-10.
4. `commands/_fragments/subagents-core.md` — point at the pack's new shape in one line. The fragment
   states WHICH shape this command uses; the pack states what the shape IS. No duplication: a
   fragment that restates the pack is how the two drift.
5. Re-render from merged master in the MAIN checkout: `python commands/assemble_commands.py`, then
   `--check` for zero drift. ⚠️ `.windsurf/rules/` is a governance-sync TRIGGER — this commit
   distributes the pack edit to ~48 repos; it must be correct for ALL of them.

Validation gate B: `python commands/assemble_commands.py --check` exits 0 with no DRIFT lines;
`grep -l` over the RENDERED output proves every consumer received the text its fragment carries —
**4 for `term-coverage`, 8 for `term-edit`, 12 for `subagents-core`** (live counts, re-measured;
the old 9/2/5 figures were this plan's own stale enumeration, caught in pass 3) — plus two negative
checks: rendered `design-review` unchanged (it includes NO fragment) and the two certification
gauntlets still carrying discovery-until-dry, not the diff-scoped form; and a no-functionality-loss
diff review confirms every guarantee in Global Constraints (all 13 + the breaker) still appears in
the rendered output.

**Behavior Contract (Phase B):**
- **Given** a VERIFY shape is adopted, **When** the pack and the fragments are both read, **Then**
  the pack STATES the shape and the fragment only REFERENCES it — no restatement that could drift
  (`.windsurf/rules/core/62-using-subagents.md:77-93`).
- **Given** the fragments are edited, **When** the corpus renders, **Then** every fragment consumer
  (4 `term-coverage` + 8 `term-edit` + 12 `subagents-core` renders) carries the loop text its
  fragment owns and `--check` reports no drift
  (`--check` renders to a temp dir and diffs; `assemble_commands.py:83` is the 1024-char skill-description limit, NOT the drift check — cited correctly here after a review caught the mis-citation).
- **Given** the loop rewrite, **When** the rendered `term-coverage` text is read, **Then** the
  adjudicated-checklist, minimum-two-rounds, BLOCKED-escalation and ledger-honesty guarantees are
  still present verbatim (`commands/_fragments/term-coverage.md:13-21`).
- **Given** 3 consecutive rounds each raising a NEW-candidate count ≥ the round before, **When** the
  loop evaluates continuation, **Then** it STOPS with `## BLOCKED: NON-CONVERGENCE` instead of
  dispatching the next round — and a run whose counts are FALLING is never stopped by it (the
  no-round-ceiling guarantee survives, `commands/_fragments/term-coverage.md:21`).
- **Given** an artifact embedding probes, **When** pass 1 of its review runs, **Then** each probe is
  RE-RUN, and a load-bearing claim with no probe is raised as a finding
  (`commands/_fragments/term-edit.md`, added by step 2).
- **Given** a review loop whose artifact was authored in this context, **When** the closing round
  arrives, **Then** its FINDER pass runs in a non-author context while adjudication stays with the
  orchestrator, and the author's own quiet round does not close the loop
  (`.windsurf/rules/core/62-using-subagents.md` § Role separation, added by step 3).

Closing sequence: gate B → `check_doc_sync.py` → **`/fabrik-review` to a coverage-adjudicated
exit** → commit.

## Phase C — Enforce what is already mandated (and stage the risky one)

**Interfaces — Consumes:** nothing from A/B. **Produces:** two gate behaviours the fleet inherits.

Steps:

1. **New `scripts/enforcement/check_phase_tests.py` — driven by the plan's DECLARED contract, never
   by a diff heuristic.** A grounder correctly killed the first design ("compare changed source
   files against tests added in the range"): "behaviour" cannot be inferred from a diff — refactors,
   perf work, config, logging, docstrings and vendored/generated code would all be flagged, and a
   gate that cries wolf on every change is a time sink, which is the operator's stated constraint.
   **The deterministic version:** the plan ALREADY enumerates each phase's behaviours as
   `## Behavior Contract` G/W/T rows. The check reads those rows for the phase being closed and
   asserts the range added at least one test per row — nothing is inferred, and a phase with no
   declared behaviours is silent by construction. Scope it to the plan-execution window (a plan lock
   with a `baseline_commit`, as `check_plan_tickets` already does for its missing-trailer finding).
   **The range boundary is the phase's END, after its `/fabrik-generate-tests` step — never the code
   commit.** `fabrik-execute-plan.md:321` mandates commit-code-THEN-generate-tests, so at the code
   commit the range always contains source changes and zero test delta; a check anchored there fires
   on every correctly-executed phase (review finding — a structural false positive, not a tuning
   problem). **WARN, not ERROR** — observe the real rate first; escalation is a later, separate
   decision. **Pre-build check — RESOLVED with proof (2026-08-10):** `check_plan_tickets.py:5-6`
   fires only for plan-SET directories, but monolith execution locks DO carry the anchor: both live
   monolith locks were read this pass — `.fabrik/plan-locks/2026-08-10-plan-1-deploy-command-triad.json`
   and `…-plan-1-quota-health.json` each contain `baseline_commit` (full key set verified:
   `baseline_commit, baseline_gate, branch, owned_paths, plan, started_at, status`). The executor
   still re-asserts the key on ITS OWN lock as this step's first line — one `python -c` read, no
   longer a design risk.
2. Register it in `final_gate.py`'s Tier-2 block next to the sibling optional checks; add it to
   `docs/workflows/FINAL_GATE_WORKFLOW.md`'s enumeration (18 → 19, and the total).
2b. **State the rule in `.windsurf/rules/core/45-testing-strategy.md`** — "a phase that ships
   user-observable behaviour shows its Behavior-Contract tests in the same range". ⚠️ That pack is
   `activation: glob` on test-file paths (`45-testing-strategy.md:2-5`), so it does NOT load in the
   case the rule targets — shipping behaviour WITHOUT touching a test file (review finding). The
   pack is therefore the WARN's CITATION, not its trigger; the always-loaded statement already
   exists at `CLAUDE.md` § Completion Contract item 1, and the check cites both.
3. **`check_mutation.py` — staged, still not blocking, and it must name its INVOKER or be cut.**
   A review found the first draft shipped capability with no caller: the script stays
   `FABRIK_MUTMUT`-gated and always exits 0, and residual #3 defers the decision that would turn it
   on — so nothing would ever run the new code. Either wire it to a named invoker (the nightly
   `FABRIK_MUTMUT=1` run) in this step, or drop step 3 entirely. Add diff-scoped selection of tests
   ADDED in the range and a hard wall-clock cap, keep `FABRIK_MUTMUT` opt-in and exit 0.
   ⚠️ `check_mutation.py:2` carries `# AFTER-EDIT: docs/CONFIGURATION.md` — editing it obliges
   staging that file, so it is in File Scope below.
   Record in the plan's residuals that flipping it blocking is a SEPARATE operator decision after
   observing WARN-rate — per the operator's "stage it last" and the no-time-loss constraint.
4. Tests for both: `tests/enforcement/test_phase_tests_gate.py` (behaviour-without-test detected;
   docs-only phase not flagged; no plan lock ⇒ silent) and a mutation-cap test extending the
   EXISTING `tests/test_check_mutation.py` (repo-root `tests/`, verified present — in File Scope
   below so the plan owns the file it edits).

Validation gate C: `python -m pytest tests/enforcement/test_phase_tests_gate.py -q` green;
`python scripts/enforcement/check_phase_tests.py` exits 0 on the hub; the FULL gate
`python scripts/final_gate.py --check --json` reports `"status":"success"` and the new check appears
in its check list.

**Behavior Contract (Phase C):**
- **Given** a phase range that added a source behaviour and no test, **When** the check runs,
  **Then** it WARNs and names the file (`scripts/enforcement/check_phase_tests.py`).
- **Given** a docs-only range, **When** the check runs, **Then** it is silent (no false positive
  across 48 repos).
- **Given** no plan lock with a `baseline_commit`, **When** the check runs, **Then** it exits 0
  silently — ad-hoc work is not plan execution.
- **Given** `FABRIK_MUTMUT` unset, **When** `check_mutation.py` runs, **Then** it still exits 0 —
  the staging guarantee (`scripts/enforcement/check_mutation.py:8-12`).

Closing sequence: gate C → `check_doc_sync.py` + the `FINAL_GATE_WORKFLOW.md` update → **`/fabrik-review`
to a coverage-adjudicated exit** → `/fabrik-docs-review` → `python scripts/final_gate.py --check --json`
to `"status":"success"` → `python scripts/enforcement/check_convergence.py` → commit.

## File Scope (owned paths)

- `commands/_fragments/term-coverage.md`
- `commands/_fragments/term-edit.md`
- `commands/_fragments/subagents-core.md`
- `.windsurf/rules/core/62-using-subagents.md`
- `.windsurf/rules/core/45-testing-strategy.md`
- `scripts/enforcement/check_phase_tests.py`
- `scripts/enforcement/check_mutation.py`
- `scripts/final_gate.py`
- `tests/enforcement/test_phase_tests_gate.py`
- `tests/test_check_mutation.py` (the mutation-cap test extends it — Phase C step 4)
- `docs/workflows/FINAL_GATE_WORKFLOW.md`
- `docs/development/reviews/2026-08-10-finder-shape-ab.md`
- `docs/CONFIGURATION.md` (forced by `check_mutation.py:2`'s `# AFTER-EDIT:` coupling)

(Governance files CHANGELOG/INDEX/docs README/FEATURES + `docs/LESSONS_LEARNT.md` are deliberately
OUT of File Scope — shared-append surfaces outside the plan lock.)

## Evidence

- Fragment sharing, the whole basis of the scope decision — RE-measured in pass 3 (this block's
  first draft said 9/2/5 while the plan's own top section carried the true counts — the exact drift
  class the probe duty exists to kill; the fenced run below is the live probe):

```
$ cd commands/_sources && for f in term-coverage term-edit subagents-core; do \
    printf '%s %s\n' "$f" "$(grep -l include:$f *.md | wc -l)"; done; grep -c include: design-review.md
term-coverage 4
term-edit 8
subagents-core 12
0
```

```
fabrik-review.md         includes: {{include:term-coverage}} {{include:grounding-code}} {{include:subagents-core}}
fabrik-plan-review.md    includes: {{include:term-edit}} {{include:grounding-artifact}} {{include:subagents-core}}
fabrik-workflow-review.md includes: {{include:term-edit}} {{include:grounding-artifact}}
```

- The serialization mechanism that rejected the original proposal — `libs/subagents/agent.py:632-636`
  (the block starts at `:632`; the `tools_enabled` grouping line is `:636` — range re-verified by
  the pass-4 independent grounder after two earlier label errors):

```
    groups = [
        {writer_ids[k] for k in g}
        for g in workspace.disjoint([list(specs[i].owned_paths) for i in writer_ids])
    ]
    groups += [{i} for i, s in enumerate(specs) if not s.tools_enabled]
```

- Mutation testing is advisory by design — `scripts/enforcement/check_mutation.py:8-12`:

```
$ sed -n '8,12p' scripts/enforcement/check_mutation.py
`.windsurf/rules/core/45-testing-strategy.md` this is **advisory + diff-scoped, NOT a per-PR blocking gate**
(full mutmut runs take minutes–hours and carry equivalent-mutant noise). So in the per-commit `final_gate`
it is **opt-in**: it runs only when `FABRIK_MUTMUT=1` (nightly / CI / on-demand), mutates only the
**committed** changed Python (applied code — never the dirty worktree), leans on mutmut's incremental mode
for diff-scoping, and **ALWAYS exits 0** (advisory, never blocks).
```

(Provenance of this block: the first draft silently dropped lines 9 and 11 with no ellipsis — a
doctored evidence artifact, caught in review. The corrected quote then went STALE when the file's
docstring was edited underneath it the same day; re-captured verbatim from the live file in pass 3.
The claim — opt-in, diff-scoped, always exits 0 — held through both artifact failures, which is the
probe duty's argument in miniature: re-run the probe, don't trust the pasted output.)

- The problem this plan exists to fix. Mid-day in-session measurement (~14:30): 174 commits / 34
  feat / 81 fix-or-review = **2.4 rework commits per feature**; `brand-identiy-creator` Phase A
  built 597 lines in ~33 min then spent ~2h34m adding 1,514 lines (mostly tests) across 8 review
  rounds (method: commit-log inspection of `/opt/brand-identiy-creator`). Re-probed at review
  pass 4 (evening) — the ratio had WORSENED to **2.9**; the probe and its verbatim output (this
  bullet previously carried a bare table with no probe — the plan's own "ungrounded claim" class,
  raised by the pass-4 grounder against the plan itself):

```
$ TOT=0; FEAT=0; RW=0; for g in /opt/*/.git; do r=${g%/.git}; \
    s=$(git -C "$r" log --since='2026-08-10 00:00' --format='%s' 2>/dev/null) || continue; \
    [ -z "$s" ] && continue; t=$(printf '%s\n' "$s" | wc -l); \
    f=$(printf '%s\n' "$s" | grep -c '^feat'); w=$(printf '%s\n' "$s" | grep -cE '^fix|review'); \
    TOT=$((TOT+t)); FEAT=$((FEAT+f)); RW=$((RW+w)); done; \
  echo "fleet today: commits=$TOT feat=$FEAT fix-or-review=$RW"
fleet today: commits=216 feat=38 fix-or-review=112
$ for p in brand-identiy-creator fabrik web-ecommerce-factory iterative_image_editor; do \
    s=$(git -C /opt/$p log --since='2026-08-10 00:00' --format='%s'); \
    printf '%-24s feat=%-3s fix=%-3s review=%-3s plan=%-3s\n' "$p" \
      "$(printf '%s\n' "$s" | grep -c '^feat')" "$(printf '%s\n' "$s" | grep -c '^fix')" \
      "$(printf '%s\n' "$s" | grep -cie review)" "$(printf '%s\n' "$s" | grep -cie plan)"; done
brand-identiy-creator    feat=2   fix=9   review=13  plan=17
fabrik                   feat=9   fix=46  review=25  plan=14
web-ecommerce-factory    feat=16  fix=12  review=0   plan=2
iterative_image_editor   feat=6   fix=10  review=1   plan=2
```

  (web-ecommerce-factory's zero-review row pays later — a hero default reached 14 pages;
  iterative_image_editor shipped 4 sequential fixes to ONE guard bug.)

## Self-audit

Grounding passes run: (1) fragment-inclusion map across ALL `commands/_sources/*.md` — produced the
scope decision; (2) `select_rules.py` → 24 ACTIVE packs, `62-using-subagents` read in full — produced the
rejection of the tool-enabled-finders proposal; (3) `agent.py` grouping code read at
`path:line` — confirmed the serialization mechanism rather than trusting the pack's prose;
(4) fabrik-lib table consulted — no applicable module, build fresh, not a new-module candidate.

**(a) Coverage of "What we already agreed":** fragment scoping → Phase B steps 1-3 + File Scope ·
wide pass 1 / scoped passes 2+ → Phase B step 1 · fix-induced findings are expected → encoded in
the exit condition, Phase B step 1 · build-time test step enforcement → Phase C steps 1-2 ·
mutation staged last → Phase C step 3 + residuals · the A/B before shipping the unproven leg →
Phase A. No agreed item is unassigned.

**(b) Cross-phase signature consistency:** Phase A *Produces* the chosen VERIFY shape; Phase B step 3
*Consumes* exactly that and is explicitly allowed to be a no-op if arm 3 loses. Phase C consumes
nothing from A or B, so it could run first — it is ordered last only because it is the riskiest.

**(c) The three operator-approved additions (2026-08-10):** stall breaker → Phase B steps 1-2 +
Behavior Contract + Global Constraints (the 14th guarantee, written to preserve (12)) · probe duty
→ Phase B step 2 + Behavior Contract (authoring-side wiring = named residual 5) · role separation →
Phase B step 3 + Behavior Contract. Each lands in a file already in File Scope; File Scope is
unchanged by the additions.

Review state: CONVERGED under `/fabrik-plan-review`, six passes — pass 1 (8 edits) · pass 2 (11 native
findings absorbed, incl. the owned_paths reversal and the true fragment counts) · pass 3 (the three
additions + this pass's own catches: the stale 9/2/5 counts in three places, the drifted mutation
quote, the stale 62-pack internal citations, the lock pre-check resolved with proof) · pass 4 (an
independent NON-AUTHOR grounder — the role-separation rule applied to this plan's own review —
returned 3 CONFIRMED + 4 PLAUSIBLE, merged with the orchestrator's 5: the `agent.py:632-636`
off-by-one, the `f598364c` finding-count, the mutation-cap test's missing File-Scope home, the
probe-less rework table, the false under-300-lines shape claim, and role-separation's
finder-vs-adjudicator precision) · pass 5 (non-author verify of the pass-4 wave: 1 minor defect —
the 505/506 line figure — plus the latent gate-A recall gap, both fixed) · pass 6 (confirming full
linear re-read: zero candidates, zero edits, md5 stable). The numbered
Pass Ledger with md5s lives in the review report per `term-edit.md:7`; the Status flipped on
pass 6's edit-free, md5-verified no-op.

## Residual unknowns

**Resolved:** the finder-parallelism trap (grounded at `agent.py:636`, design corrected); the scope
question (fragments, not commands); whether the build-time test rule exists (it does, at
`fabrik-execute-plan.md:321` — the gap is enforcement).

**Still open:**

1. **Which VERIFY shape wins** — resolution step: Phase A, before any fragment carries it.
2. **Whether `check_phase_tests.py` can attribute "behaviour" reliably enough to avoid false
   positives across 48 repos** — resolution step: it ships WARN-only in Phase C, and the residual is
   revisited with real WARN-rate data before any ERROR-tier escalation.
3. **Whether mutation verification should ever become blocking** — deliberately NOT decided here.
   Resolution step: a separate operator decision after observing the diff-scoped, time-capped
   advisory run; this plan only makes that observation possible.
4. **The breaker threshold (3 consecutive non-decreasing rounds)** — a constant chosen from one
   day's evidence (the 21-round stall would have tripped it by round ~7). Resolution step: ship it,
   count real trips for a period, then tune; a threshold debate without trip data is guessing.
5. **Authoring-side probe mandate** (plans/specs must CARRY probes, in `/fabrik-plan-after-chat` /
   `/fabrik-spec`) — deliberately out of this plan's File Scope. Resolution step: the review-side
   probe duty ships first and creates the pressure; wiring the authoring commands is a follow-up
   plan once the finding class proves its rate.
