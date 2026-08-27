# Plan — certification denominator: a generated, registry-sourced ledger with a deny-list exit

Status: CONVERGED — md5-verified no-op round (b0266c18), 2 rounds, 5 findings fixed

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
| `OUT-OF-SCOPE(reason)` | **not our product's functionality** — a third party's own hosted page beyond our redirect. Justified per-ID and reviewable. |
| `UNVISITED` | not terminal. **Blocks the close.** |

⚠️ **The upstream proposal proposes a third disposition, `DEFERRED(reason)`, and this plan REJECTS
it** (operator, 2026-08-27: *"i dont accept deferred… as like a real qc engineer all functionality
must be tested"*). A "later" disposition is the loophole that would let this entire change be
ignored: the tail that most needs generating is exactly the tail that would be deferred. The
divergence must be carried back to tryton-crm, whose reference implementation is being built against
the proposal's three-state model.

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
- `INDEX.md`, `docs/README.md` (dir row already covers `reference/`), `CHANGELOG.md`

## Behavior Contract

One test per distinct observable behaviour, risk-ordered, TDD for the risky ones:

1. A ledger with any `UNVISITED` ID → the check reports NOT CONVERGED.
2. A ledger where every ID is `EXERCISED` or `OUT-OF-SCOPE(reason)` → converged.
3. `OUT-OF-SCOPE` with an empty/missing reason → rejected (a bare disposition is not a justification).
4. **`DEFERRED` appearing anywhere in a ledger → rejected as an unknown disposition**, naming the
   operator ruling. This is the clause most likely to be re-introduced by someone reading the
   upstream proposal instead of this plan.
5. A close-time re-enumeration that finds an ID absent from the ledger → NOT CONVERGED (anti-cheat).
6. A ledger whose `source` is a doc rather than a registry → rejected; the doc inventory is a
   cross-check, never the denominator.
7. A generator that could not reach its registry → the ledger records the refusal and the check
   fails LOUD, naming what could not be enumerated.
8. Missing ledger entirely → advisory WARN on landing (never a hard red), per the rollout ruling.
9. **The check never turns the gate red on landing** — `warn_only=True` and exit 0 on EVERY path,
   including the guard's own error path. `scripts/final_gate.py:198-208` converts a non-zero
   `warn_only` exit into a blocking red fleet-wide, and this class has now bitten twice in one week:
   `check_plan_lock_release` hit it five times during its build, and a sibling check reddened ~46
   repos via the `wordpress` `NotImplementedError`. **Write this test FIRST (TDD) and copy
   `check_plan_lock_release.py`'s guard shape verbatim** — a `try` around the WHOLE body including
   the output path, catching the CLASS, with the message naming `type(exc).__name__` and never
   `repr(exc)`.
10. The evidence path recorded against an `EXERCISED` ID must **exist on disk**; a ledger row citing
    a path nobody produced is rejected.

## Context Files

- `commands/_sources/fabrik-user-test.md`, `commands/_sources/fabrik-service-test.md`
- `scripts/enforcement/check_plan_lock_release.py` — the closest sibling: an advisory, fleet-synced,
  `warn_only` check with a census-first output and a hard exit-0 contract. **Copy its shape.**
- `scripts/enforcement/check_review_coverage.py` — the closest sibling for *reading a ledger out of a
  markdown artifact* and grading it.
- `docs/reference/plan-lock-lifecycle.md` — the doc shape for an advisory subsystem.
- `src/fabrik/scaffold.py:138` — `SCAFFOLD_TYPES`, the registry-table denominator.

---

## Phase A — the ledger FORMAT and the grader (no command changes yet)

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

**A2. Write `check_certification_coverage.py`** — reads the ledger, computes the fraction, and
reports. `warn_only=True`, exit 0 on every path, census-first output (the 500-char/10-line advisory
budget applies — see `plan-lock-lifecycle.md`).

**A3. Tests** — the nine Behavior Contract rows, each proven red-on-revert.

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
| `wordpress` | **NONE — retired.** See the trap below. |

⚠️ **`wordpress` is the one gap in the proposal's table (11 of 12), and it is the dangerous kind.**
`src/fabrik/scaffold.py:5783` raises `NotImplementedError` for it — *"WordPress is out of fabrik:
scaffolding moved to /opt/wpf (2026-06-17)"* — while `:146` keeps it in `SCAFFOLD_TYPES` "for legacy
deploy/shape". A sibling advisory check hit exactly this: it iterated `SCAFFOLD_TYPES`, the
`NotImplementedError` escaped, the non-zero exit turned a `warn_only` row into a **blocking red
across ~46 repos**. The grader must therefore treat `wordpress` as an explicit, guarded row that
returns "no registry, type retired" and MUST NOT reach the scaffolder. This is a Behavior Contract
row, not a comment.

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
| **2 (terminal)** | the same five, re-swept | **0** | **0** |

Round 2 made no edits — `md5 b0266c18` unchanged — so this is a genuine no-op exit, not a
re-derivation. The five round-1 findings were: the `wordpress` gap (the dangerous one), the
unsettled declaration home, the ungradeable evidence clause, the under-stated `warn_only` exit
contract, and an allowlist claim resting on a citation rather than an executed verdict.

⚠️ **One round-2 candidate was withdrawn as a probe artifact, not a plan defect.** A gradeability
sweep reported 3 Behavior Contract rows with "no mechanical verdict"; the regex had captured only
the FIRST line of each wrapped list item, so verbs on the continuation lines were invisible. Re-run
with a parser that joins continuations: 0 of 10 rows ungradeable. Recorded because reading a verdict
out of a broken probe is how a good artifact gets damaged.

## Residuals

- Promotion from advisory to blocking — deliberately out of scope, a later operator decision (D4).
- Whether already-green certifications are re-run — answered by the rollout choice: they are not
  invalidated, but their real fraction becomes visible on landing day.
