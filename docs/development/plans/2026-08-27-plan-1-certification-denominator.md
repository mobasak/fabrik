# Plan — certification denominator: a generated, registry-sourced ledger with a deny-list exit

Status: CONVERGED — 11 rounds, 15 findings fixed; round 11 a no-op (23 contract rows, 0 ungradeable)

**Origin:** operator directive 2026-08-27 — *"our /fabrik-user-test and /fabrik-service-test commands
are not enforcing agents to test all product surface. it must… the goal is to test finished product
100% fully."* Upstream proposal from tryton-crm (mail `01M0YTBH22XYYG2D4TJVM3NCR7`, ACCEPTED + acked,
disposition `done`), full text at
`/opt/tryton-crm/docs/reference/upstream-proposals/2026-08-26-certification-denominator-must-come-from-a-live-registry.md`.

## The defect, validated against the hub's own sources

Not re-derived — each of these was checked this session before the plan was written:

| Claim | Verified at |
|---|---|
| The ledger is PROSE WITH COUNTS, no stable IDs, no artifact | `commands/_sources/fabrik-user-test.md:87-90` — *"the **Inventory Ledger** — `journeys[] · features[] · pages[] · flows[] · elements[] · states[]` with counts"* |
| Same shape on the headless side | `commands/_sources/fabrik-service-test.md:76` — `journeys[] · features[] · endpoints[] · jobs[] · events[]` |
| **There is NO grader at all** | `scripts/enforcement/` holds `check_review_coverage.py` (reviews) and `check_test_coverage.py` (unit tests). Nothing reads a certification ledger. |
| The anti-cheat precedent exists | `commands/_sources/fabrik-features.md:87` — *"on an edit-free, md5-verified no-op round"* |
| `warn_only` is the sanctioned advisory landing | `scripts/final_gate.py:198-208`, registered via `run_optional_check` (`:221`, call site `:849`) |

The agent authors the denominator, grades itself against it, and the gate never looks. On a surface
the project authored, the agent's enumeration and reality converge and this never bites. On an
**inherited** surface it under-counts silently and the run terminates **honestly and wrong** — a true
statement about the wrong denominator, which neither command can self-detect.

**The measured instance** (tryton-crm, `saas-skeleton` wrapping a vendored Tryton ERP), taken
immediately after a genuine md5-verified `/fabrik-features` no-op — so the denominator was as healthy
as the current contract can make it:

```
FEATURES.md:    30 shipped rows, ~12 browser-reachable
live registry:  271 menus · 316 window actions · 80 wizards · 19 reports
                142 model buttons · 867 views
authored split: 19 ours / 252 vendored — 93% of the navigation a customer clicks is inherited
```

A `/fabrik-user-test` run would have exercised ~12 of ~1,700, found no new inventory, and reported a
converged gauntlet. **This is not a stale-doc problem and `/fabrik-features` is not the fix** — a
perfectly converged FEATURES.md is still the wrong denominator, because it documents what the project
BUILT and certification must cover what the product SHIPS.

## ⚠️ The contract this plan builds — and where it OVERRIDES its own source

**Every ID reaches a terminal disposition. There are exactly two, and `DEFERRED` is not one of them.**

| Disposition | Meaning |
|---|---|
| `EXERCISED` | visited and asserted on, with an evidence path. The depth of the assertion is set by risk tier. |
| `OUT-OF-SCOPE(reason)` | **not our product's functionality** — a third party's own hosted page beyond our redirect. The reason must NAME THE EXTERNAL OWNER; see the closed loophole below. |
| `UNVISITED` | not terminal. **Blocks the close.** |

⚠️ **The upstream proposal proposes a third disposition, `DEFERRED(reason)`, and this plan REJECTS
it** (operator, 2026-08-27: *"i dont accept deferred… as like a real qc engineer all functionality
must be tested"*). A "later" disposition is the loophole that would let this entire change be
ignored: the tail that most needs generating is exactly the tail that would be deferred. The
divergence must be carried back to tryton-crm, whose reference implementation is being built against
the proposal's three-state model.

### ⚠️ The loophole removing `DEFERRED` left open (found on re-review)

Deleting `DEFERRED` moved the hole; it did not close it. `OUT-OF-SCOPE(reason)` was graded on one
thing only — that the reason string is non-empty — with **no bound on how many IDs may carry it**.
An agent facing 1,700 IDs could mark 1,688 `OUT-OF-SCOPE(inherited vendor surface)` and 12
`EXERCISED`, and the grader would report CONVERGED. That is **the tryton-crm scenario verbatim**
(~12 of ~1,700, converged) with a different word in the disposition column.

Three mechanical closures, because prose asking for good judgement is what produced this defect:

1. **A rejected-reason list.** `inherited`, `vendored`, `third-party code`, `generated`, `legacy`,
   `low priority`, `not ours to fix` are **REJECTED as OUT-OF-SCOPE reasons**. Every one of them
   describes *how our surface came to exist*, not whether a customer can click it. Inherited
   surfaces are precisely what T3 exists for. A valid reason **names an external owner** — a domain
   or vendor whose system the user has left ours to reach.
2. **The disposition census always prints** — `N exercised · M out-of-scope · K unvisited` — so a
   1,688/12 split is visible at a glance and cannot hide behind a converged verdict.
3. **`out-of-scope > exercised` does not converge silently.** It is reported as a distinct verdict
   requiring an explicit operator acknowledgement line in the ledger. A product that is mostly
   out-of-scope is a claim about the product, and a human should have to make it.

**Risk tiers set DEPTH, never whether something is tested.** This is what makes 100% EXERCISED
achievable rather than aspirational:

- **T1** — money / tenancy / PII / authorisation journeys → full UI-truth-vs-system-truth.
- **T2** — surfaces the project authored or modified → deep.
- **T3** — inherited and untouched → **generated** smoke (opens · renders · no traceback · no
  untranslated leak · respects scope). Still EXERCISED, with a real assertion.

Hand-authoring 1,700 tests is not feasible; **generating** 1,700 smoke assertions is. Generation is
the mechanism that makes the operator's bar reachable, which is why T3-must-be-generated is a
contract clause and not advice.

## Scope

Six mechanisms from the proposal (CORE 1-3, TRACTABLE 4-5, DURABLE 6), **plus the missing grader**
the proposal did not know was absent.

## Touches

- `commands/_sources/fabrik-user-test.md` — Phase 1 denominator + termination contract
- `commands/_sources/fabrik-service-test.md` — same
- `commands/assemble_commands.py` — PARAMS if the fragments need new substitutions
- `scripts/enforcement/check_certification_coverage.py` — **NEW**, the grader
- `scripts/final_gate.py` — one `run_optional_check` registration, `warn_only=True`
- `tests/enforcement/test_certification_coverage.py` — **NEW**
- `docs/reference/certification-denominator.md` — **NEW** subsystem reference
- the generated per-surface artifacts: `docs/reference/certification/<surface>-ledger.md`
  (the denominator) and `<surface>-plan.md` (the phased test plan the run executes)
- **`CLAUDE.md` + `scripts/enforcement/check_doc_sprawl.py`** — the allowlist row for
  `docs/development/certifications/YYYY-MM-DD-cert-<surface>/` (`TC##[a-z]?-<slug>.md` tickets only,
  gate-enforced shape, not a free `**`). ⚠️ This is a **fleet-wide governance edit** — CLAUDE.md is a
  synced surface and the change distributes to ~46 repos.
- `INDEX.md`, `docs/README.md` (dir row already covers `reference/`), `CHANGELOG.md`

## Behavior Contract

One row per distinct observable behaviour, risk-ordered, TDD for the risky ones.

- **Given** a generated ledger containing any ID whose disposition is `UNVISITED`, **When** the
  grader runs, **Then** it reports NOT CONVERGED and names the unvisited IDs.
- **Given** a ledger where every ID is `EXERCISED` or `OUT-OF-SCOPE(reason)`, **When** the grader
  runs, **Then** it reports CONVERGED with the computed fraction.
- **Given** a row dispositioned `OUT-OF-SCOPE` with an empty or missing reason, **When** the grader
  runs, **Then** the row is rejected — a bare disposition is not a justification.
- **Given** a row dispositioned `DEFERRED`, **When** the grader runs, **Then** it is rejected as an
  unknown disposition, citing the operator ruling. *(This is the clause most likely to be
  re-introduced by someone reading the upstream proposal, which proposes `DEFERRED`, instead of this
  plan.)*
- **Given** an `EXERCISED` row whose evidence path does not exist on disk, **When** the grader runs,
  **Then** the row is rejected — the strongest mechanical proxy for "the assertion was real".
- **Given** a close-time re-enumeration of the registry that yields an ID absent from the ledger,
  **When** the grader diffs them, **Then** it reports NOT CONVERGED (the anti-cheat).
- **Given** a generator that under-enumerates CONSISTENTLY, **When** the close-time diff runs,
  **Then** the diff alone cannot catch it — both enumerations come from the same generator, so a
  short list agrees with itself. The generator must therefore emit a **raw `registry_total`**
  (a count taken straight from the registry, e.g. `SELECT count(*)`) alongside the enumerated IDs,
  and **Then** `ids_enumerated != registry_total` is a REFUSAL that fails LOUD naming the shortfall.
- **Given** a doc-derived inventory that diverges sharply from the registry, **When** the grader
  runs, **Then** the divergence is REPORTED. This is the bidirectional-reconciliation value the plan
  claimed for the demoted doc inventory and then never used — an independent second opinion on the
  denominator is exactly what catches a short generator that agrees with itself.
- **Given** an `OUT-OF-SCOPE` reason drawn from the rejected list (`inherited`, `vendored`,
  `generated`, `legacy`, `low priority`, …), **When** the grader runs, **Then** the row is rejected —
  those describe how our surface came to exist, not whether a customer can click it.
- **Given** a ledger where `out-of-scope` rows outnumber `exercised` rows, **When** the grader runs,
  **Then** it does NOT report a silent CONVERGED — it emits a distinct verdict requiring an explicit
  operator acknowledgement line.
- **Given** a ledger whose `source` resolves to a doc rather than a registry, **When** the grader
  runs, **Then** it is rejected — the doc inventory is a cross-check, never the denominator.
- **Given** a generator that could not reach its declared registry, **When** it emits the ledger,
  **Then** the refusal is recorded and the grader fails LOUD naming what could not be enumerated —
  never a silently short list.
- **Given** the dead legacy string `wordpress` still present in `SCAFFOLD_TYPES`, **When** anything
  in the grader iterates the frozenset, **Then** it exits 0 without reaching the scaffolder — a pure
  crash guard, because `scaffold.py:5783` raises `NotImplementedError` while `:146` keeps the string,
  and a sibling check let that escape and reddened ~46 repos. We ship no WordPress projects; this
  asserts nothing about certification.
- **Given** a generated ledger, **When** the command completes Phase 1, **Then** a CERT BOARD exists
  at `docs/development/certifications/YYYY-MM-DD-cert-<surface>/` — a spine with `## Test Board`
  plus `TC##[a-z]?-<slug>.md` tickets — reusing the plan-set SHAPE while occupying a separate
  namespace.
- **Given** a cert board, **When** `/fabrik-execute-plan`'s dispatcher detection runs against it,
  **Then** it does NOT claim it — the heading is `## Test Board`, not `## Ticket Board`, and the
  directory is not `plans/YYYY-MM-DD-plan-<slug>/`. **This is the anti-mix-up assertion and it is
  tested directly**, because the dispatcher's second trigger is the heading STRING alone
  (`fabrik-execute-plan.md:34-38`), so a cert board carrying the wrong heading would be dispatched
  to coding agents.
- **Given** a certification run, **When** it acquires its scope lock, **Then** the lock file must
  exist under `.fabrik/cert-locks/`, and a lock written to `.fabrik/plan-locks/` is **rejected** —
  `check_phase_tests.py:36` and `final_gate_stop.py:785` both read the plan-lock dir, so a cert lock
  there would arm the Stop hook and scope phase tests as if source were being written.
- **Given** a `TC##` ticket with no `Runner:` field, **When** the cert checker runs, **Then** it is
  rejected — the dispatcher's default unit is a coder, and an unrouted test ticket would put a
  coding agent on a browser job.
- **Given** a test ticket whose exercise FAILED, **When** a `Runner: fix` ticket for it is merged,
  **Then** the original test ticket is still non-terminal until it is RE-RUN green — the fix does
  not close the test.
- **Given** a certification board whose tickets do not cover the ledger exactly, **When** the new
  coverage check runs, **Then** it is rejected — a registry ID in NO ticket re-opens the `UNVISITED`
  hole one level up, and an ID in TWO tickets double-counts the fraction. **This ID↔ticket link is
  the ONLY genuinely new check**; board shape is already `check_plan_tickets.py`'s job.
- **Given** a registry of ~1,700 IDs, **When** the board is generated, **Then** the ticket COUNT is
  bounded and the bound is graded — IDs are grouped per touchpoint, not one ticket per ID. A naive
  generator emitting 1,700 tickets against a dispatcher that runs 3 at a time is ~570 dispatch
  cycles: technically "converged", operationally never finishing. `check_plan_tickets.py:1318` bounds
  a single ticket's SIZE; nothing bounds a board's LENGTH, and the cert checker must.
- **Given** an issue found while exercising a ticket, **When** it is recorded, **Then** it becomes
  ANOTHER TICKET ON THE SAME BOARD — never an entry in a prose "HANDED-OFF list", which is how the
  current contract lets a known defect leave the run unowned.
- **Given** a ticket whose fix has landed, **When** the dispatcher closes it, **Then** the ticket's
  own gate must pass — the RETEST is the ticket lifecycle, not a separate phase anyone can skip.
- **Given** a project with no ledger at all, **When** the grader runs on landing day, **Then** it
  WARNs and exits 0 — advisory rollout, never a hard red.
- **Given** a cert board whose heading is `## Ticket Board`, or whose lock sits in
  `.fabrik/plan-locks/`, **When** the guard runs, **Then** it FAILS BLOCKING — **not advisory, from
  day one.**

  ⚠️ The advisory rollout was ruled for COVERAGE COMPLETENESS: nobody's release should freeze because
  their real fraction is now visible. It was NOT ruled for a wrong-agent dispatch. A mis-headed cert
  board is a safety defect — it puts CODING agents on a test board holding a lock
  `final_gate_stop.py:785` believes in — and a warn-only safety guard is one nobody reads until
  after the damage. Applying `warn_only` uniformly across both would have mis-applied the ruling.
- **Given** ANY input at all, including a corrupt ledger and a raising guard path, **When** the
  grader runs, **Then** it exits 0. `scripts/final_gate.py:198-208` converts a non-zero `warn_only`
  exit into a blocking red fleet-wide; this class bit `check_plan_lock_release` five times in one
  week. **Write this test FIRST (TDD)** and copy `check_plan_lock_release.py`'s guard shape verbatim
  — a `try` around the WHOLE body including the output path, catching the CLASS, with the message
  naming `type(exc).__name__` and never `repr(exc)`.

- **Mocked:** nothing is mocked in the grader's own tests — they run against ledger FIXTURES written
  to `tmp_path`, which is the real parser against real files. The registry PROBES (Phase B) are the
  only mocked surface: a live ERP/route-table is not reachable from a unit test, so each probe is
  tested against a captured registry fixture, with the live path proven once against tryton-crm's
  reference generator (Phase D2).

## Context Files

- `commands/_sources/fabrik-user-test.md`, `commands/_sources/fabrik-service-test.md`
- `scripts/enforcement/check_plan_lock_release.py` — the closest sibling: an advisory, fleet-synced,
  `warn_only` check with a census-first output and a hard exit-0 contract. **Copy its shape.**
- `scripts/enforcement/check_review_coverage.py` — the closest sibling for *reading a ledger out of a
  markdown artifact* and grading it.
- `docs/reference/plan-lock-lifecycle.md` — the doc shape for an advisory subsystem.
- `src/fabrik/scaffold.py:138` — `SCAFFOLD_TYPES`, the registry-table denominator.

---

## ⚠️ CERTIFICATION IS A TICKET BOARD, NOT A GAUNTLET — the reframe that supersedes the artifact design

Operator, 2026-08-27: *"as like a real qc engineer all user/service touchpoint must be tested, issues
detected and resolved and retested by this command… as like completing tickets, our orchestrator
agent should manage the entire tests."*

**This supersedes the bespoke `<surface>-plan.md` artifact an earlier round of this plan invented.**
That was a parallel universe built next to machinery the hub already ships. Verified before
rewriting:

| What certification needs | What already exists |
|---|---|
| a decomposed, trackable unit of test work | **plan-SET**: `docs/development/plans/YYYY-MM-DD-plan-<slug>/` — spine with `## Ticket Board` + `T##[a-z]?-<slug>.md` tickets, **already in the CLAUDE.md allowlist as a gate-enforced shape** |
| something to run the board to completion | **`/fabrik-execute-plan` DISPATCHER MODE** — triggered by a plan-set directory or a `## Ticket Board` spine; iterates the Board, `Agent-Task: T##` provenance, no `Agent-Phase` |
| a grader for the board's shape | **`scripts/enforcement/check_plan_tickets.py`** — *"Spine↔ticket plan-set contract gate"*: Board section parsing (`:92`), duplicate rows (`:727`), a ticket file with no Board row (`:738`), ticket-size limits (`:1318`) |
| the detect → fix → **retest** loop | the dispatcher's own ticket lifecycle: a ticket is not DONE until its gate passes, so a fix is re-verified by construction |
| resumability across sessions | Board state — a four-figure ledger spans sessions and the Board already carries per-ticket state |

**So the design changes shape.** Phase 1 of each certification command does not emit a novel
document — it **generates a plan-SET**: one ticket per touchpoint group, sized so a single agent can
hold it, with the registry ID(s) each ticket covers named in the ticket. Then the run hands the board
to the dispatcher. An issue found mid-run becomes **another ticket on the same board**, so it cannot
rot in a "HANDED-OFF list" the way the current prose contract allows.

**The operator never runs a planning command first.** Asking a human to hand-author a plan before
each certification would be absurd at 1,700 IDs; the command generates the board. `/fabrik-plan-*`
stays where it belongs — for implementation work a human is deciding.

**What this deletes from the plan:** the invented `<surface>-plan.md` format (Phase A1b), and most of
the invented grader. `check_plan_tickets.py` already grades board SHAPE. The only thing it cannot
know is whether the board's tickets **cover the registry** — that link is the one genuinely new
check, and it is small: *every registry ID appears in exactly one ticket*.

## ⚠️ NAMESPACE SEPARATION — a cert board must never be mistaken for an implementation plan

Operator, 2026-08-27: *"be sure name test tickets differently and do not cause ticket mix up with
fabrik-plan-after-chat and execute commands."* The concern is correct and the collision is real —
the reframe above, as first written, would have caused it. Four systems key on the plan-set shape:

| System | What it keys on | Collision if a cert board reuses the shape |
|---|---|---|
| Doc allowlist — `CLAUDE.md:132`, `check_doc_sprawl.py` | `docs/development/plans/YYYY-MM-DD-plan-<slug>/` with `T##[a-z]?-<slug>.md` **only** | a `cert-` dir or a `TC##` file is BLOCKED today — the allowlist row is part of this work |
| `check_plan_tickets.py:90` `PLAN_DIR_NAME_RE` | `^\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+$` | a cert dir does not match → silently UNGRADED |
| `/fabrik-execute-plan` dispatcher detection (`:34-38`) | the plan-set dir **OR a spine with `## Ticket Board` present** | ⚠️ **the dangerous one** — `## Ticket Board` alone triggers DISPATCHER MODE regardless of directory, so a cert spine would be dispatched as an implementation plan |
| plan-locks — `check_phase_tests.py:36`, `final_gate_stop.py:785` | `.fabrik/plan-locks/*.json` | a cert run's lock would arm the Stop hook and scope phase tests as if code were being written |

**The separation, on all four axes:**

| Axis | Implementation work | Certification work |
|---|---|---|
| directory | `docs/development/plans/YYYY-MM-DD-plan-<slug>/` | **`docs/development/certifications/YYYY-MM-DD-cert-<surface>/`** |
| ticket file | `T##[a-z]?-<slug>.md` | **`TC##[a-z]?-<slug>.md`** (TC = test case) |
| board heading | `## Ticket Board` | **`## Test Board`** — this is what stops dispatcher detection claiming it |
| lock | `.fabrik/plan-locks/` | **`.fabrik/cert-locks/`** |
| grader | `check_plan_tickets.py` | a sibling cert checker |

`## Test Board` is the load-bearing one: the dispatcher's second trigger is the *heading string*, so a
different heading is what mechanically prevents `/fabrik-execute-plan` from adopting a cert board.

⚠️ **The honest cost of this decision.** Full separation means the certification command runs **its
own dispatch loop, modelled on the D-loop, not `/fabrik-execute-plan` verbatim**. That is more work
than reuse, and it risks the two loops drifting apart over time. It is chosen anyway because the
alternative — a cert board that IS an implementation plan to every tool on the box — is precisely
the mix-up the operator ruled out, and a wrong dispatch would put a coding agent on a test board with
a plan-lock the Stop hook believes in. The drift risk is mitigated by the cert loop citing the D-loop
as its source and by both being graded by sibling checkers.

## ⚠️ Ticket→RUNNER routing — a cert ticket is not a coding ticket

Found while tracing the end-state, and unnamed until now: the dispatcher's unit is a **coder**, but a
certification ticket drives a browser or probes an API. The hooks exist —
`/fabrik-execute-plan:198-199` already routes a GUI build+verify unit as
`subagent_type: fabrik-gui`, and `check_plan_tickets.py:35` already cross-checks routing against a
ticket's `Complexity:` — but nothing lets a ticket say *what kind of agent runs me*.

Every `TC##` ticket therefore declares a **`Runner:`** field, and the cert checker rejects a ticket
without one:

| `Runner:` | Used for | Dispatched as |
|---|---|---|
| `gui` | UI-bearing surfaces — a screen, a flow, an element | `subagent_type: fabrik-gui` (browser MCPs) |
| `service` | endpoints, jobs, events, contracts | a headless probe unit |
| `generated-smoke` | the T3 inherited tail | a generated loop, never a hand-authored spec |
| `fix` | a ticket opened BY a failure, whose work is code | a coding agent, and the only `Runner:` that writes source |

`Runner: fix` is what keeps detect→fix→retest inside one board: the failing test ticket stays open,
its fix ticket is a coding unit, and the test ticket cannot flip terminal until it is re-run green.

## ⚠️ The method must be SYSTEMATIC, not just the denominator

Operator, 2026-08-27: *"these two commands/skills — they must be systematic as like
`/fabrik-plan-after-chat`."* This is a second requirement, and the first draft of this plan missed
it: fixing the DENOMINATOR (what must be covered) while leaving the METHOD ad-hoc would produce an
honest number attached to an unrepeatable process.

`/fabrik-plan-after-chat` is systematic because of six concrete mechanisms, every one of which
already exists in this repo and is reusable here:

| Mechanism | Where it lives today | What certification gets |
|---|---|---|
| A run record opened as the command's FIRST act | `scripts/command_run.py` | the run is visible and un-abandonable; the pinned `RUN:` line survives a compaction |
| Numbered phases in dependency order | the plan schema | certification runs phase by phase, not as one opaque gauntlet |
| Every claim grounded BEFORE writing | § Phase 1 grounding | every ID traced to the registry row that produced it |
| A structured ARTIFACT with a fixed schema | the plan file | **the ledger is not enough — the run emits a CERTIFICATION PLAN** |
| Auto-convergence to an md5-verified no-op via a paired review | `/fabrik-plan-review` | the gauntlet closes on a quiet round, not on the agent's judgement |
| Gate enforcement of the artifact's shape | `check_convergence.py`, `check_test_proposal.py` | `check_certification_coverage.py` (Phase A) |

**The consequence for the design.** Phase 1 of each command does not merely enumerate a ledger — it
**generates a certification PLAN** over that ledger and writes it to
`docs/reference/certification/<surface>-plan.md`: the IDs grouped into phases by risk tier, each
phase carrying its own runnable gate and evidence slots, in dependency order (T1 journeys before the
T3 sweep, because a broken auth boundary invalidates everything behind it). Execution then walks
that plan phase by phase, exactly as `/fabrik-execute-plan` walks an implementation plan — with
`command_run.py step` at each phase and `round` at each convergence pass.

That is what makes "100% fully" *repeatable* rather than a one-off heroic run: the plan is an
artifact, so a second run diffs against the first, a resumed run knows where it stopped, and a
reviewer can see which phase a claim came from.

## Phase A — the two artifact FORMATS and the grader (no command changes yet)

The grader first, deliberately: a contract with no grader is what produced this defect, and building
the checker before the prose means the prose has something to be true against.

**A1. Define the ledger artifact** at **`docs/reference/certification/<surface>-ledger.md`**.

⚠️ Resolved at plan time, not left to execution: `scripts/enforcement/check_doc_sprawl.py:31-42`
holds **CLOSED** allowlists (`ALLOWED_NEW_ROOT_DOCS`, `ALLOWED_NEW_DOCS_SCAFFOLD`) plus strict
patterns for plans/archive — a new `docs/certification/` tree would trip it and would have needed a
fleet-wide governance edit to the allowlist. `docs/reference/**/*.md` is already allowlisted
(CLAUDE.md § HARD STOPS), so siting the ledger under `docs/reference/certification/` needs **no
governance change at all**. Take the free path.

Machine-readable block with one row per ID:

```
| ID | tier | disposition | evidence | source |
|---|---|---|---|---|
| MENU-0142 | T3 | EXERCISED | .tmp/cert/menu-0142.png | registry:ir_ui_menu |
| ROUTE-POST-/v1/parties | T1 | EXERCISED | tests/e2e/test_parties.py::test_post | registry:app.routes |
```

**A1b. The test plan is a PLAN-SET, not a new format.** Superseded in round 9: an earlier round
invented `<surface>-plan.md` and defined its schema. That was wrong — the hub already ships the
shape, the dispatcher and the grader (see the reframe above). The command generates
`docs/development/plans/YYYY-MM-DD-cert-<surface>/` as a spine + `T##` tickets, which
`check_plan_tickets.py` already grades and `/fabrik-execute-plan` already runs.

Same schema discipline as an implementation plan, because that is what "systematic like
`/fabrik-plan-after-chat`" means mechanically:

```
## Phase T1 — money / tenancy / PII / authorisation      gate: <runnable command>
| ID | tier | assertion | evidence |
## Phase T2 — authored or modified surfaces              gate: <runnable command>
## Phase T3 — inherited (GENERATED smoke)                gate: <runnable command>
```

Every ID in the ledger appears in exactly one phase (the grader checks the partition is total and
disjoint — an ID in no phase is the `UNVISITED` hole re-opened one level up, and an ID in two phases
double-counts the coverage fraction). Phases run in dependency order: T1 first, because a broken auth
boundary invalidates every result behind it.

**A2. Write `check_certification_coverage.py`** — reads the ledger, computes the fraction, and
reports. `warn_only=True`, exit 0 on every path, census-first output (the 500-char/10-line advisory
budget applies — see `plan-lock-lifecycle.md`).

**A3. Tests — ONE PER BEHAVIOR CONTRACT ROW, counted mechanically, each proven red-on-revert.**

⚠️ This step said *"the nine Behavior Contract rows"* while the contract had grown to **23** — 14 rows
with no test assigned, inside the plan whose whole purpose is to stop behavior-without-a-test. A
literal count in prose goes stale the moment the contract grows, so the count is not restated here:
**the phase gate asserts parity mechanically** —

```
rows=$(grep -c '^- \*\*Given\*\*' <the plan's Behavior Contract section>)
tests=$(pytest tests/enforcement/test_certification_coverage.py --collect-only -q | tail -1)
# parity is the gate; a contract row with no test FAILS the phase
```

**Gate:** `python -m pytest tests/enforcement/test_certification_coverage.py -q` + `ruff` +
`python scripts/final_gate.py --check --json` → `"status":"success"`.

### Evidence
- [x] allowlist resolved at plan time **by execution, not by reading the allowlist**:
      `check_doc_sprawl.py` is registered at `final_gate.py:1402` (it binds), and a live probe gave
      `BLOCKED: docs/certification/_probe.md` with exit 1 while `docs/reference/certification/_probe.md`
      passed unmentioned. The ledger sites under `docs/reference/certification/` and needs no
      governance edit.
- [ ] fenced `pytest` output showing every Behavior Contract row green
- [ ] fenced red-on-revert matrix, source restored byte-identical

---

## Phase B — the registry table: how a project DECLARES its denominator

The genuinely new work, and the part the hub must not guess. 12 `SCAFFOLD_TYPES`
(`src/fabrik/scaffold.py:138`) with different registry shapes.

**B1. Adopt the proposal's table** (it is well-grounded) as the *default* per type:

| Scaffold type | Registry |
|---|---|
| `python-api` · `python-api-gpu` · `node-api` · `file-api` · `saas-skeleton` | live route table (FastAPI `app.routes`, Express `_router.stack`) or the emitted OpenAPI |
| `file-worker` (+ any queue-bearing type) | the task/beat registry — registered job names + schedules |
| `static-site` · `docusaurus` | `sitemap.xml` / the build manifest |
| `chrome-extension` | the MV3 manifest — popup · options · content-script matches · commands |
| `mobile-app` | the navigator route tree |
| `desktop-app` | the window + application-menu registry |
| any type wrapping a vendored platform | **that platform's own registry** |

The table covers **every product type we actually ship**. `SCAFFOLD_TYPES` also still contains the
string `wordpress` (`src/fabrik/scaffold.py:146`), but **we have no WordPress projects** — zero
`project.yaml` files declare it, and CLAUDE.md records the type as *"out of fabrik — `/opt/wpf`
archived 2026-08-07"*. It is dead legacy, **not a product surface**, and it gets no registry row.

It gets one thing only: a **crash guard**. `scaffold.py:5783` raises `NotImplementedError` on it
while `:146` keeps the string in the frozenset, and a sibling advisory check iterated
`SCAFFOLD_TYPES`, let that escape, and turned a `warn_only` row into a blocking red across ~46
repos. So the grader must never reach the scaffolder for it. That is a one-line guard and a
regression test — nothing about certification.

**B2. The DECLARATION mechanism** — the hub must not infer.

⚠️ **SETTLED at plan time** — this was an execution-blocking unknown and the contract forbids
carrying those into execution, so it was resolved during review rather than deferred to Phase B.

`specs/services/<id>.yaml::shape` is **the wrong home**: `src/fabrik/spec_loader.py:205-215` states
`Shape` *"declares what the project IS — orthogonal properties that determine which infrastructure
registrars (postgres, gatus, backrest, glitchtip, grafana, authelia, meilisearch) are applicable"*.
A certification denominator is not an infrastructure registrar; hanging it there makes `shape:` mean
two things.

**The home is `project.yaml`**, which describes itself as *"Project metadata — source of truth"* and
already carries **exactly this pattern**: `has_user_guide: true if project has user-facing docs
(activates user-guide gate)`, consumed by `scripts/enforcement/check_user_guide.py:7-8` — *"0 - Pass
(guide present, or `has_user_guide` is false/absent) · 1 - Fail (`has_user_guide: true` but
docs/user-guide/ missing or empty)"*. A project.yaml flag arming an enforcement check is a shipped,
working precedent, so the denominator declaration copies it:

```yaml
certification_registry:          # absent => fall back to the B1 table AND record the fallback
  source: registry:ir_ui_menu    # what the denominator resolves to
  enumerate: <command or module path that emits the IDs>
```

Absent-and-falling-back must be as auditable as declared — `check_user_guide` passes on absent, and
this check must likewise never punish a project for not having adopted the key yet (the rollout is
advisory).

An undeclared source falls back to the B1 table **and records that it fell back**; a registry that
cannot be reached fails LOUD naming what could not be enumerated. A declared-and-justified fallback
is auditable; an inferred one is not.

**B3. The authored-vs-inherited discriminator must be MECHANICAL** — tryton-crm derives theirs from
`ir_model_data.module`. The contract must require a derivation, not a judgement, because tiering is
only tractable if the split is computed.

### Evidence
- [ ] the real loader's `path:line` for wherever the declaration lands
- [ ] fenced output of the declaration resolving on ≥2 different scaffold types

---

## Phase C — rewrite both command contracts

**C1. `/fabrik-user-test` Phase 1** — the denominator resolves to a registry; the four discovery modes
are demoted to *cross-checks* (their bidirectional-reconciliation value is real and is kept); the
ledger is GENERATED, never hand-written.

**C2. `/fabrik-service-test`** — identical change. Its `endpoints exercised / inventory` fraction is
only as good as *inventory*, and an inherited or gateway-mounted endpoint is invisible to it exactly
as an inherited screen is to the GUI gauntlet.

**C3. Both termination contracts** — replace *"loop until discovery is dry"* (evaluated by the agent
that built the inventory) with the deny-list: **every ID terminal, `UNVISITED` blocks the close**,
plus the close-time re-enumeration diff.

**C4. Render the corpus** — from the **MAIN checkout on merged master**, verified with
`git worktree list --porcelain | sed -n '1s/^worktree //p'` before rendering. Never from a worktree:
the renderer PRUNES installed commands absent from the current tree's `_sources/`.

### Evidence
- [ ] `assemble_commands.py --check` → *"installed commands + skills match rendered sources"*
- [ ] the `worktree list` output proving the render was from the main checkout

---

## Phase D — land ADVISORY, and validate against the reference

**D1. Register in `final_gate.py`** via `run_optional_check(..., warn_only=True)` — advisory
fleet-wide on landing (operator ruling: nothing grandfathered, nothing silently re-baselined, no
release frozen on day one). Every project immediately SEES its real coverage fraction and its
UNVISITED list.

**D2. Validate against tryton-crm's reference** — they are building the generator + ledger + T3
generated-smoke loop for the vendored-platform case (the hardest registry shape) and sending it back.
**The hub design must be checked against their working generator BEFORE it binds fleet-wide.** Four
answers were requested and must be reconciled into the contract: ID-scheme stability across
migrations/environments; the mechanical authored-vs-inherited discriminator; what T3 smoke honestly
asserts; and where the generator REFUSES.

**D3. Carry the `DEFERRED` divergence back to them** — their reference is being built against the
proposal's three-state model and this plan ships two.

**D4. Promotion to blocking is a SEPARATE, later operator decision** — taken once the fleet has run
it and the output is signal rather than noise. Not in this plan.

### Evidence
- [ ] fenced `final_gate --check` showing the new advisory row present and green
- [ ] the fleet sweep: the check run against ≥5 real projects, exit 0 everywhere

---

## Self-audit

- **Does this actually enforce the operator's bar?** Yes for *coverage* — `UNVISITED` blocks the
  close and `DEFERRED` is rejected, so nothing can be parked. **Honest limit, and the strongest
  mechanical proxy available:** the grader cannot verify that the assertion behind an ID was
  *meaningful* — a generated T3 smoke asserting nothing would pass. It CAN verify more than the plan
  first claimed: the evidence path must **exist on disk** (not merely be a non-empty string), which
  is mechanically checkable and defeats the cheapest cheat — a ledger of plausible-looking paths
  nobody produced. That becomes a Behavior Contract row. The residual limit is then narrow and
  specific, and belongs stated in the reference doc rather than implied away.
- **Biggest risk:** the per-scaffold-type registry probe (Phase B). Most are one-liners; the
  vendored-platform case is per-platform and is the only genuinely new work. Mitigated by validating
  against tryton-crm's reference before binding.
- **What would make this fail the way its target failed?** Shipping the contract without the grader.
  Phase A is first for exactly that reason.
- **Blast radius:** both command sources render box-wide to `~/.claude`; the enforcement check is a
  governance-sync trigger surface (`scripts/enforcement/`) and distributes to ~46 repos on commit
  from `/opt/fabrik`.

## Convergence

| Round | classes swept | found | fixed |
|---:|---|---:|---:|
| 1 | ungradeable-clauses · warn-only-exit · declaration-residual · scaffold-type-coverage · doc-allowlist | 5 | 5 |
| 2 | the same five, re-swept | 0 | 0 |
| **3 (gate-driven)** | Behavior Contract FORMAT — the gate found what all three prose rounds missed | 1 | 1 |
| 4 (operator correction) | `wordpress` framing · the SYSTEMATIC-method requirement the first draft missed | 2 | 2 |
| 5 | re-swept after the round-4 additions | 1 | 1 |
| 6 | full re-sweep: contract/phase parity · partition · wordpress · method · residuals | 0 | 0 |
| 7 (re-invocation) | **disposition-loophole · generator-integrity · cross-check-unused** — three NEW classes | 3 | 3 |
| 8 | the same six, re-swept; 17 contract rows, 0 ungradeable | 0 | 0 |
| 9 (operator reframe) | certification is a TICKET BOARD, not a bespoke artifact | 1 | 1 |
| 10 (operator: no mix-up) | namespace separation across 4 systems · ticket→Runner routing | 2 | 2 |
| **11 (terminal)** | all 7 classes re-swept; 23 contract rows, 0 ungradeable | **0** | **0** |

Round 2 made no edits — `md5 b0266c18` unchanged — so this is a genuine no-op exit, not a
re-derivation. The five round-1 findings were: the `wordpress` gap (the dangerous one), the
unsettled declaration home, the ungradeable evidence clause, the under-stated `warn_only` exit
contract, and an allowlist claim resting on a citation rather than an executed verdict.

⚠️ **Round 10 — the operator caught a collision the reframe itself introduced.** *"be sure name test
tickets differently and do not cause ticket mix up."* Round 9 moved certification onto the plan-set
shape and, in doing so, would have made a cert board indistinguishable from an implementation plan to
four separate systems — worst of all the dispatcher, whose second trigger is the bare heading string
`## Ticket Board`, so a cert spine would have been dispatched to coding agents holding a plan-lock
the Stop hook believes in. Separated on all four axes (directory · `TC##` · `## Test Board` ·
`.fabrik/cert-locks/`), with the cost stated: the cert loop is now its own, modelled on the D-loop
rather than reusing it. The same round settled the `Runner:` field that tracing the end-state had
surfaced as unnamed.

⚠️ **Round 9 — the operator's reframe, and it deleted more of this plan than any review round.**
*"as like completing tickets, our orchestrator agent should manage the entire tests."* Earlier rounds
invented a `<surface>-plan.md` artifact, defined its schema, and specified a grader for it — all of
it a parallel universe beside machinery the hub already ships: the plan-SET shape (allowlisted,
gate-enforced), `/fabrik-execute-plan` DISPATCHER MODE, and `check_plan_tickets.py`. The lesson is
the one this repo keeps re-learning: **check what already exists before designing the thing.** Six
review rounds hardened an artifact that should never have been invented — none of them asked whether
the hub already had one.

⚠️ **Round 7 came from a RE-INVOCATION of `/fabrik-plan-review` on an already-CONVERGED plan, and it
found the two worst defects in the document.** Every earlier round was run by the plan's own author,
and the two holes below are exactly what an author is blind to — both let the contract be satisfied
by a product that was never tested:

- **`OUT-OF-SCOPE` had absorbed the abuse `DEFERRED` was deleted for.** It was graded on one thing:
  a non-empty reason. Nothing bounded how many IDs could carry it. 1,688 `OUT-OF-SCOPE(inherited
  vendor surface)` + 12 `EXERCISED` = CONVERGED — the tryton-crm scenario verbatim, with a different
  word in the disposition column. Closed with a rejected-reason list (`inherited`/`vendored`/
  `legacy`/… describe how our surface came to exist, not whether a customer can click it), an
  always-printed disposition census, and a distinct non-silent verdict when out-of-scope outnumbers
  exercised.
- **The anti-cheat could not see a consistently-short generator.** The close-time re-enumeration
  diffs the registry against the ledger, but BOTH enumerations come from the same generator — a
  short list agrees with itself and the diff is empty. This is the plan's own thesis reproduced one
  level down: a true statement about the wrong denominator. Closed by requiring a raw
  `registry_total` (a count taken straight from the registry) against `ids_enumerated`, and by
  finally GRADING the doc-derived cross-check the plan had demoted, praised, and never used — an
  independent second opinion is precisely what catches a generator that agrees with itself.

⚠️ **Round 4 was the OPERATOR, and both corrections were fair.** (a) The plan gave `wordpress` a row
in the registry table; we ship **zero** WordPress projects and CLAUDE.md records the type as out of
fabrik, so a dead legacy string had been dressed up as a product surface. It is now a crash guard
only. (b) More importantly, the first draft fixed the DENOMINATOR and left the METHOD ad-hoc —
*"they must be systematic as like /fabrik-plan-after-chat"* is a second requirement, and an honest
coverage number attached to an unrepeatable process is half the job.

⚠️ **Round 5 then caught the defect round 4 introduced** — the new Behavior Contract row asserted a
certification PLAN artifact exists while no phase defined its format: a contract clause with no
grader, which is the exact class this plan exists to remove. Phase A1b now defines it, and the
partition (total and disjoint over the ledger) is itself a graded row. The round that adds
something is never the last round.

⚠️ **Round 3 was the GATE, not me, and it is the most instructive round.** `final_gate` rejected the
plan: *"Behavior Contract missing the Given/When/Then structure"* (`check_test_proposal.py:200-205`).
Three prose review rounds had audited whether each row was *gradeable* and never checked whether the
section met the FORMAT the gate actually enforces — a plan whose entire thesis is *"a contract with
no grader gets ignored"*, failing its own grader. Rewritten as Given/When/Then, and the `Mocked:`
line the format also requires is now present. This is the same lesson the plan encodes: prose review
is not a substitute for running the check.

⚠️ **One round-2 candidate was withdrawn as a probe artifact, not a plan defect.** A gradeability
sweep reported 3 Behavior Contract rows with "no mechanical verdict"; the regex had captured only
the FIRST line of each wrapped list item, so verbs on the continuation lines were invisible. Re-run
with a parser that joins continuations: 0 of 10 rows ungradeable. Recorded because reading a verdict
out of a broken probe is how a good artifact gets damaged.

## Residuals

- Promotion from advisory to blocking — deliberately out of scope, a later operator decision (D4).
- Whether already-green certifications are re-run — answered by the rollout choice: they are not
  invalidated, but their real fraction becomes visible on landing day.
