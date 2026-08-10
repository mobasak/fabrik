# Plan — Review-loop overhaul: converge in ~3 rounds instead of ~8, without losing recall

Status: DRAFT
Owner: hub (command corpus fragments + enforcement)
Operator directive (verbatim, 2026-08-10): "we need to be faster, make less mistakes" · "i dont want
to lose functionality. also i dont want to lose time too." · "first review pass must be perfect"

## What we already agreed

- **Scope is the 3 shared FRAGMENTS, not the 10 review commands.** Grounded: `subagents-core.md` is
  included by 9 of 10 review commands, `term-coverage.md` by the two code-review commands,
  `term-edit.md` by the five artifact-review commands. Editing fragments cannot produce divergence
  between commands; editing ten files invites it.
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
- **Operator constraints:** no functionality loss, no time loss, blast radius ~48 repos.

## Shape decision — MONOLITH (3 phases), stated per the command's Phase-2 gate

Three phases, not four+: each is the smallest unit carrying its own test cycle and worth a fresh
`/fabrik-review` (the command's own right-sizing definition). Phase A is a measurement that GATES
the others; Phase B is one coherent semantic change to the loop contract (splitting the two loop
fragments would risk exactly the divergence the fragment scoping exists to prevent); Phase C is the
enforcement backstop. Projected length is under the ~300-line monolith trigger and no phase's READ
set approaches `READ_BUDGET_BYTES`.

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
overlapping `owned_paths` (`workspace.py:426` — "An agent with empty `owned_paths` (unrestricted)
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
| Fragment `subagents-core.md` | the dispatch policy 9 of 10 review commands inherit | `commands/_fragments/subagents-core.md:3` |
| Fragment `term-coverage.md` | the code-review loop: "fresh full round after any fix", no ceiling | `commands/_fragments/term-coverage.md:13-21` |
| Fragment `term-edit.md` | the artifact-review loop (plan/spec/ui/workflow/deploy-plan reviews) | included by 5 commands per the render map |
| `check_mutation.py` | advisory by design — opt-in, diff-scoped, always exits 0 | `scripts/enforcement/check_mutation.py:8-12` |
| `fabrik-execute-plan.md` | already mandates `/fabrik-generate-tests` per phase — unenforced | `commands/_sources/fabrik-execute-plan.md:321` |
| fabrik-lib | **consulted — no applicable module.** The table has no review-orchestration, mutation-testing or gate-enforcement module (`api-smoke-test` is endpoint smoke, `llm-dispatch` is `claude -p` plumbing). Build fresh inside the existing hub enforcement surface; not a new-module candidate (hub-corpus-specific, not reusable across project types) | `/opt/fabrik-lib/README.md` module table |
| `specs/services/*.yaml` `shape:` | **N/A** — no service, no DB/cache/metrics/search/admin surface changes | — |

## Global Constraints

- **Fleet blast radius:** every file in File Scope is fleet-synced or renders box-wide. A change must
  be correct for ALL ~48 projects, not just the hub.
- **Fragments are the edit surface.** Never hand-edit a rendered command in `~/.claude/commands/`;
  never edit one of the 10 review commands to change behaviour a fragment owns.
- **Merge-time render only:** `commands/assemble_commands.py` runs from merged master in the MAIN
  checkout — never from a worktree (the renderer PRUNES artifacts absent from the current tree).
  `--check` (temp-dir) is always safe.
- **No functionality loss** is a hard acceptance criterion, not an aspiration: every behaviour the
  current loop guarantees (adjudicated checklist, no silent skips, ledger honesty, BLOCKED
  escalation, minimum two rounds) must still be mandated after the edit.
- Commands state rules present-tense; change-history goes to CHANGELOG/git, never into a fragment.
- 12-Factor: N/A to prose fragments; the enforcement scripts add no logfile, no daemon, no host
  ports, no backing-service substitution.

## Phase A — Measure before changing: the finder-shape A/B

**Why first:** the only leg of the design still unproven. This session's evidence (pool 1/7 real vs
native 15/18) is n=1 and confounded — different models, different brief depth, AND different tool
access varied together. Phase B's VERIFY stage design depends on which factor dominates.

**Interfaces — Produces:** a decision record naming which VERIFY dispatch shape Phase B writes into
the fragments (`tool-enabled pool over candidates` vs `native over candidates`), plus measured
precision and wall-clock for each arm.

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
sys.exit(0 if len(arms)==3 and 'CHOSEN SHAPE:' in t else 1)"` → exit 0.
Expected: three arm rows each carrying raised/real/wall-clock, and a line beginning `CHOSEN SHAPE:`
naming the shape and the arm that justifies it.

**Behavior Contract (Phase A):**
- **Given** three arms with a known ground-truth finding set, **When** the A/B runs, **Then** each
  arm's precision is computed against that set rather than asserted
  (`docs/development/reviews/2026-08-10-hub-governance-gates-review.md`).
- **Given** arm 2 uses `tools_enabled=True`, **When** its `owned_paths` overlap, **Then** the run is
  rejected as invalid (it would measure serialization, not tool access) — assert disjointness before
  dispatch (`libs/subagents/agent.py:636`).

Closing sequence: run gate A → `python scripts/enforcement/check_doc_sync.py` → **`/fabrik-review` on
Phase A's changed surface, run to its coverage-adjudicated exit** → commit with provenance trailers.

## Phase B — Rewrite the loop contract in the two loop fragments

**Interfaces — Consumes:** Phase A's chosen VERIFY shape. **Produces:** the loop semantics every
review command inherits.

Steps:

1. `commands/_fragments/term-coverage.md` — replace the round semantics:
   - **Pass 1 is a WIDE sweep**: every class in the rubric partition is assigned to a finder in the
     SAME round. A round that samples a subset is not a pass-1.
   - **Passes 2+ are scoped to the fix diff PLUS its callers and callees** — spelled out, with the
     reason stated once: today's severest finding sat in a function no fix had edited.
   - **Exit** = a fix-diff-scoped pass raises nothing new AND the checklist is fully adjudicated.
     The existing "minimum two rounds", BLOCKED escalation, ledger-honesty and no-silent-skip rules
     are carried VERBATIM — no functionality loss.
   - Replace "a fresh, fully-independent finder round on the updated code" (`term-coverage.md:15`,
     which is what forces a full re-sweep per fix) with the scoped form, keeping the "the pass that
     changed code is never the last look at those classes" guarantee intact.
2. `commands/_fragments/term-edit.md` — the same round semantics for artifact reviews. This is the
   fragment that drove 13 plan passes on one plan; the scoped-successor rule applies to prose
   identically (pass 2+ reviews the EDITS, not the whole artifact).
3. **`.windsurf/rules/core/62-using-subagents.md` § Parallelism — the CANONICAL edit, and the named
   CONSUMER of Phase A's artifact** (`docs/development/reviews/2026-08-10-finder-shape-ab.md` → its
   `CHOSEN SHAPE:` line is what this step transcribes; the artifact is not written-and-never-read).
   If Phase A chose a dispatch change, add it there as a named third shape
   (`FIND read-only + parallel → VERIFY tools-enabled over the CANDIDATE list only`), with the
   serialization trap restated inline so no future editor re-makes the proposal this plan rejected.
   Writing it anywhere else leaves the pack contradicting the fragments that defer to it.
4. `commands/_fragments/subagents-core.md` — point at the pack's new shape in one line. The fragment
   states WHICH shape this command uses; the pack states what the shape IS. No duplication: a
   fragment that restates the pack is how the two drift.
5. Re-render from merged master in the MAIN checkout: `python commands/assemble_commands.py`, then
   `--check` for zero drift. ⚠️ `.windsurf/rules/` is a governance-sync TRIGGER — this commit
   distributes the pack edit to ~48 repos; it must be correct for ALL of them.

Validation gate B: `python commands/assemble_commands.py --check` exits 0 with no DRIFT lines;
`grep -c` proves each of the 10 review commands received the new loop text via its fragment (9 for
`subagents-core`, 2 for `term-coverage`, 5 for `term-edit`); and a no-functionality-loss diff review
confirms every guarantee listed in Global Constraints still appears in the rendered output.

**Behavior Contract (Phase B):**
- **Given** a VERIFY shape is adopted, **When** the pack and the fragments are both read, **Then**
  the pack STATES the shape and the fragment only REFERENCES it — no restatement that could drift
  (`.windsurf/rules/core/62-using-subagents.md:77-93`).
- **Given** the fragments are edited, **When** the corpus renders, **Then** all 10 review commands
  carry the new loop semantics and `--check` reports no drift
  (`commands/assemble_commands.py:83`).
- **Given** the loop rewrite, **When** the rendered `term-coverage` text is read, **Then** the
  adjudicated-checklist, minimum-two-rounds, BLOCKED-escalation and ledger-honesty guarantees are
  still present verbatim (`commands/_fragments/term-coverage.md:13-21`).

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
   **WARN, not ERROR** — observe the real rate first; escalation is a later, separate decision.
2. Register it in `final_gate.py`'s Tier-2 block next to the sibling optional checks; add it to
   `docs/workflows/FINAL_GATE_WORKFLOW.md`'s enumeration (18 → 19, and the total).
2b. **State the rule in `.windsurf/rules/core/45-testing-strategy.md`** — "a phase that ships
   user-observable behaviour shows its Behavior-Contract tests in the same range". A gate with no
   pack rule behind it is unappealable and gets `noqa`'d; the pack is what the WARN cites.
3. **`check_mutation.py` — staged, still not blocking in this plan.** Add diff-scoped selection of
   tests ADDED in the range and a hard wall-clock cap, keep `FABRIK_MUTMUT` opt-in and exit 0.
   Record in the plan's residuals that flipping it blocking is a SEPARATE operator decision after
   observing WARN-rate — per the operator's "stage it last" and the no-time-loss constraint.
4. Tests for both: `tests/enforcement/test_phase_tests_gate.py` (behaviour-without-test detected;
   docs-only phase not flagged; no plan lock ⇒ silent) and a mutation-cap test.

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
- `docs/workflows/FINAL_GATE_WORKFLOW.md`
- `docs/development/reviews/2026-08-10-finder-shape-ab.md`

(Governance files CHANGELOG/INDEX/docs README/FEATURES + `docs/LESSONS_LEARNT.md` are deliberately
OUT of File Scope — shared-append surfaces outside the plan lock.)

## Evidence

- Fragment sharing, the whole basis of the scope decision — measured this session:
  `subagents-core` included by 9 of 10 review commands, `term-coverage` by 2, `term-edit` by 5.

```
fabrik-review.md         includes: {{include:term-coverage}} {{include:grounding-code}} {{include:subagents-core}}
fabrik-plan-review.md    includes: {{include:term-edit}} {{include:grounding-artifact}} {{include:subagents-core}}
fabrik-workflow-review.md includes: {{include:term-edit}} {{include:grounding-artifact}}
```

- The serialization mechanism that rejected the original proposal — `libs/subagents/agent.py:636`:

```
    groups = [
        {writer_ids[k] for k in g}
        for g in workspace.disjoint([list(specs[i].owned_paths) for i in writer_ids])
    ]
    groups += [{i} for i, s in enumerate(specs) if not s.tools_enabled]
```

- Mutation testing is advisory by design — `scripts/enforcement/check_mutation.py:8-12`:

```
`.windsurf/rules/core/45-testing-strategy.md` this is **advisory + diff-scoped, NOT a per-PR blocking gate**
it is **opt-in**: it runs only when `FABRIK_MUTMUT=1` (nightly / CI / on-demand), mutates only the
for diff-scoping, and **ALWAYS exits 0** (advisory, never blocks).
```

- The problem this plan exists to fix, measured fleet-wide today: 174 commits, 34 features, 81
  fix-or-review commits = **2.4 rework commits per feature**; `brand-identiy-creator` Phase A built
  597 lines in ~33 min then spent ~2h34m adding 1,514 lines (mostly tests) across 8 review rounds.

```
project                  feat  fix review plan  | rework per feat
brand-identiy-creator       2    0     10   17  | 5.0
fabrik                      8   13     19    6  | 4.0
web-ecommerce-factory      14   12      0    0  | 0.9   (pays it later: a hero default reached 14 pages)
iterative_image_editor      6    7      0    1  | 1.2   (4 sequential fixes to ONE guard bug)
```

## Self-audit

Grounding passes run: (1) fragment-inclusion map across all 10 review commands — produced the scope
decision; (2) `select_rules.py` → 24 ACTIVE packs, `62-using-subagents` read in full — produced the
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

Not a fixed point yet: `/fabrik-plan-review` has not run.

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
