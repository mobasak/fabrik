# Plan 1 — plan-lock release check: make a finished plan's unreleased lock visible the day it happens

Status: CONVERGED

**Spec:** `docs/superpowers/specs/2026-08-25-plan-lock-release-check-design.md` (CONVERGED, review 2,
8 passes, md5 `6b853a48`, commit `381b0f6e`; operator-approved 2026-08-26).
**Owner:** `[infra]` · **Shape:** monolith (2 phases) · **Stage:** 4-build

> **Shape decision, stated because it trips a stated trigger — and re-argued from measurement at
> review time.** The spine+ticket set is triggered by ANY of: >3 phases · projected monolith
> >~300 lines · a phase READ set over `READ_BUDGET_BYTES` (262144). This file is **~570 lines**, so
> the line trigger fires at roughly 1.9×. **Kept as a monolith deliberately**, on evidence rather
> than preference:
>
> ```
> $ per-phase READ set (the phase's files + its Context Files) vs the 262144 budget
> Phase A: 153924 bytes  (59%)      Phase B: 137344 bytes  (52%)
> $ line accounting (the totals drift as the review edits the file; the SPLIT is the stable signal)
> phase bodies (## Phase A → ## Review Record) 268 · everything else ~300
> ```
>
> The **exact** trigger — the byte budget the line count only proxies for — does not fire, with ~40%
> headroom in both phases; each is comfortably codeable by one cold agent. Only **268 lines are the
> phases themselves**; the rest is Context Ledger / Global Constraints / Review Record / Coverage
> Checklist / Evidence / Self-audit / Residual unknowns — **every one of which a spine carries
> identically**, so converting
> lengthens the artifact rather than shortening it, and mints a mandatory `Integration: true` ticket
> whose only Touches are receipts for a two-file deliverable. The command's own convention keeps
> work this small in a monolith. **A reviewer who disagrees now has the numbers to argue with rather
> than a preference to accept.**

---

## What we already agreed (distilled from the spec + this conversation)

- **Goal.** Detect a `.fabrik/plan-locks/<id>.json` left **non-terminal** after its plan finished, so
  the omission surfaces at its cause rather than a week later as a hard `BLOCKED` halt at another
  agent's `/fabrik-execute-plan` step 7.
- **Chosen approach.** One standalone advisory check `scripts/enforcement/check_plan_lock_release.py`,
  registered in `final_gate.py` via `run_optional_check(..., warn_only=True)`, modelled on
  `check_vendored_drift.py`. It is the **executable backing for `fabrik-catchup.md:47-60` probe 1**,
  which already specifies rule 1 in prose.
- **Rejected, do not revisit:** auto-releasing a lock · age-based staleness · folding into
  `check_plan_tickets.py` · a pre-commit hook · leaving probe 1 as prose · building the mechanical
  acquire/release writer *now* (better long-term, out of scope here, with a named deletion trigger).
- **Operator decisions this turn.** Spec approved as CONVERGED. Build the detector, not the
  mechanical writer.
- **No external dependencies.** stdlib only (`json`, `pathlib`, `re`, `argparse`). The live-research
  gate is vacuously satisfied — there is no third-party fact in this design to go stale.

## Global Constraints (every phase inherits these — copied verbatim from the binding sources)

- **stdlib only.** `json`, `pathlib`, `re`, `argparse`. No new dependency; `pyproject.toml` /
  `requirements.txt` are NOT authorised by this plan.
- **`warn_only=True` still FAILS the gate on ANY non-zero exit** (`scripts/final_gate.py:267-268`:
  *"registered warn_only=True but exited {code} — its contract changed"*). Every failure path returns
  **0** with an honest line. The exception guard catches the **CLASS** (`except Exception`), never an
  enumerated list of types.
- **NEVER auto-reclaim.** The check reports; freeing another plan's lock is an operator action
  (`fabrik-execute-plan.md:73-78`). The check writes nothing, ever.
- **The remediation TEXT names the owner and the sanctioned action** — owner releases per Finish
  step 5; **operator DELETES** per `fabrik-execute-plan.md:77`. Locks are git-tracked
  (`git ls-files .fabrik/plan-locks/` → 49), so telling an arbitrary reader to "release it" instructs
  a HARD-STOP violation (commit a file you did not author) from the check's own output.
- **Do not edit `check_convergence.EXECUTED`** (`scripts/enforcement/check_convergence.py:122-126`).
  It backs a **blocking**, fleet-synced gate; widening it for an advisory check's convenience risks
  reddening ~46 repos. Import and reuse it; extend the legacy alternation in the NEW module.
- **Fleet blast radius.** `scripts/enforcement/**` and `scripts/final_gate.py` are governance-sync
  trigger surfaces → this distributes to ~46 repos. **No manifest edit is needed** (verified:
  `fabrik_synced_manifest.py:100-101` is a recursive dir, `rglob("*")` at `:259-272`). ⚠️ The
  pre-commit hook guards on `[ "$(pwd)" = "/opt/fabrik" ]` (`.pre-commit-config.yaml:67`) — **work in
  the hub checkout, not a worktree**, or the sync fires for nobody.
- **NEVER-ROUTE — the whole deliverable.** `NEVER_ROUTE_PREFIXES` (`check_plan_tickets.py:212-218`)
  contains **both** `scripts/enforcement/` and `scripts/final_gate.py`. Every code step here is
  **NATIVE**; the pool may ground and find, never write.
- **12-Factor non-negotiables** (inherited by every phase): logs = unbuffered stdout only, **never a
  logfile** (XI) · migrations never from startup (XII) · same backing services dev/test/prod (X) · no
  sticky sessions (VI) · no daemonizing / PID files (VIII) · workers requeue in-flight jobs on SIGTERM
  (IX) · releases immutable (V) · granular env vars, no grouped sets (III) · shelled-out binaries
  pinned in the Dockerfile (II). *This plan ships one CLI script and touches none of these; they bind
  anyway so no step can quietly violate one.*
- **Tests must never write the operator's real state.** Every fixture builds its corpus under
  `tmp_path`; the one live assertion reads a **copy** of another repo's locks, never the original.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | Behavior Contract — one test per user-observable behavior, risk-ordered; **watched-fail-first**: a non-trivial test proves nothing until SEEN RED | `45-testing-strategy.md:24` |
| `.windsurf/rules/core/10-python.md` (ACTIVE) | Python/typing discipline; no file logging (XI), no grouped env sets (III) | `10-python.md:249`, `:252` |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | Doc Sync Matrix — a new subsystem owes a DEDICATED `docs/reference/<name>.md` + its `INDEX.md` row | `CLAUDE.md` § Doc Sync Matrix |
| `.windsurf/rules/core/62-using-subagents.md` (ACTIVE) | dispatch policy: pool-default for gradeable fan-out, native for never-route + the decide/merge | `62-using-subagents.md` § Dispatch policy |
| `scripts/final_gate.py` `run_optional_check` | `warn_only=True` implies `advisory`, and still FAILS the gate on non-zero exit | `final_gate.py:221-248`, `:267-268` |
| `scripts/enforcement/check_vendored_drift.py` registration | the **every-tier** registration site — above the `# ── Tier 1` marker | `final_gate.py:874-880`; marker at `:882` |
| `scripts/enforcement/check_pack_reachability.py` | the output-contract template: `examined_count` / `claim_pairs` / `unevaluable_types` + the `OK` vs `NOTHING VERIFIED` fork | `check_pack_reachability.py:253-255`, `:302-310` |
| `scripts/enforcement/check_convergence.py` `EXECUTED` | the hardened, anchored, decoration-tolerant plan-Status matcher — **reuse, do not edit** | `check_convergence.py:122-126`; rationale `:116-118` |
| `scripts/enforcement/check_plan_tickets.py` `NEVER_ROUTE_PREFIXES` | the deliverable is entirely never-route ⇒ native execution only | `check_plan_tickets.py:212-218` |
| `tests/enforcement/test_final_gate_registration.py` | the AST block-membership pin pattern + its built-in red (feed the defeating mutant to your own helper) | `test_final_gate_registration.py:1-11`, `:108` |
| `commands/_sources/fabrik-catchup.md` probe 1 | the finding taxonomy this check makes executable — adopt verbatim, do not invent a parallel one | `fabrik-catchup.md:47-60` |
| `commands/_sources/fabrik-execute-plan.md` | the writer's contract: `paused` `:459`, `blocked` `:563`, operator-deletes remedy `:77`, step-6 repoint `:970` | as cited |
| `scripts/fabrik_synced_manifest.py` | `scripts/enforcement/` is a recursive synced dir — no manifest edit needed | `fabrik_synced_manifest.py:100-101`, `:259-272` |
| **fabrik-lib consult** | **BUILD (project-local).** `/opt/fabrik-lib/README.md` — every module is a runtime APP capability (alerting, auth, credits, storage…); none covers repo-governance state validation. **Not a 🆕 candidate**: this encodes fabrik's own plan-lock protocol and ships by governance-sync, a different channel. | `/opt/fabrik-lib/README.md` module table |

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor.** Every phase, on completion, runs `/fabrik-review` on its changed surface to a
  coverage-adjudicated exit BEFORE its commit. No phase closes on a first-pass green.
- **Dispatch policy.** The deliverable is **never-route** (`scripts/enforcement/`,
  `scripts/final_gate.py`) ⇒ **all code is written NATIVELY**, `claude -p opus` for the classifier
  core (it is the design-heavy surface), never a pool coder. The pool IS used, read-only, for the
  Phase-A/B `/fabrik-review` finder breadth (`fanout("review", …, mode="read_only")`, flywheel-recorded
  with a `set_quality` back-fill) with native Opus added on top for the authoritative pass.
- **Parallelism + merge.** Phases A and B are strictly sequential (B registers what A creates). Within
  each phase's review gate, finders fan out in parallel and merge at the native decide/refute step
  that this session owns.

---

## Phase A — the classifier + its behavior suite (TDD, red-first on the two risky rules)

**Deliverable:** `scripts/enforcement/check_plan_lock_release.py` and
`tests/enforcement/test_plan_lock_release.py`, green, with the riskiest behaviors seen RED first.

### Interfaces

**Produces** (Phase B consumes these names verbatim):

```python
# scripts/enforcement/check_plan_lock_release.py
NON_TERMINAL: frozenset[str]           # {"active", "paused", "blocked"}
TERMINAL: frozenset[str]               # {"released", "executed", "complete", "completed"}
FINISHED_TOKENS: tuple[str, ...]       # EXECUTED, COMPLETE, COMPLETED, CLOSED, DONE, SHIPPED,
                                       # FIXED, SUPERSEDED, IMPLEMENTATION-CONVERGED

def normalise_status(raw: object) -> str                # str().strip().lower() — CASE-FOLDED
def status_value(spine_text: str) -> str | None         # extracts the VALUE off a `Status:` LINE
def strip_decoration(value: str) -> str                 # leading **, ✅, 🚧, ✔️, —, -, whitespace
def finished_token(value: str) -> str | None            # anchored on an already-extracted VALUE
def resolve_plan(root: Path, lock_path: Path, plan_field: str | None) -> PlanRef
def classify(root: Path, lock_path: Path) -> list[Finding]   # 0, 1 or MORE per lock
def main(argv: list[str] | None = None) -> int          # ALWAYS 0 — findings included
```

⚠️ **`status_value()` and `finished_token()` are two functions on purpose — an earlier draft fused
them and the result was unsatisfiable.** `finished_token` was specified to take a *value* while
step 1's fixture handed it the full line `"**Status:** ✅ EXECUTED 2026-08-14"`; `strip_decoration`
has no rule for a `Status:` prefix, so it returned `None` and step 4 could never go green. The
executing agent's only escape would have been to loosen the matcher — reintroducing exactly the
substring laxity fixture f forbids. **`status_value()` owns the `Status:` line grammar**, reusing
`check_convergence.EXECUTED`'s anchor for the canonical form; `finished_token()` only ever sees the
extracted value.

⚠️ **`main()` returns 0 even when there ARE findings — this is the highest-consequence line in the
plan.** The enforcement corpus is split: `check_review_coverage.py:1463` returns `1` on findings,
while `check_pack_reachability.py:321` and `check_vendored_drift.py:156` always return `0`. An
implementer following the first habit turns this advisory row into a **blocking red across ~46
repos** on the first sync (`final_gate.py:262-270`: *"registered warn_only=True but exited {code} —
its contract changed"*). The Behavior Contract carries a dedicated row and a red-on-revert for it.

`Finding` is a dataclass carrying `label` ∈ the eight labels, `lock` (name), `detail`, `remedy`.
`PlanRef` carries `location` ∈ `{"archived", "live", "missing"}`, `status_value: str | None`,
`spine: Path | None`, `field_resolved: bool`.

⚠️ **`classify` returns a LIST, not `Finding | None` — an earlier draft of this block had the
singular form and it cannot express the plan's own behaviour.** One lock can carry several labels at
once, and the motivating instance did: `2026-08-19-plan-1-kaizen-m1-event-stream` was `active` **and**
archived (`STALE LOCK`) **and** had `completed_at` set with `final_commit` null (`HALF-APPLIED
FINISH`). `PLAN FIELD STALE` is likewise defined as *detail added to an existing finding*, which a
single-value return cannot represent. The census line counts per label, so a lock contributing to two
counters is the normal case, not an edge one.

**Consumes:** nothing from an earlier phase (this is the first).

### Steps

0. **Create the module as a deliberately-WRONG stub first — the red must be an ASSERTION failure,
   not a `ModuleNotFoundError`.** Write `scripts/enforcement/check_plan_lock_release.py` containing
   only the shebang, the `# AFTER-EDIT:` header, and stubs whose behaviour is *plausible but wrong*:
   `finished_token()` doing a **substring** search (the defect under test) and `classify()` keying on
   `status == "active"` alone (review 1's rejected axiom). ⚠️ **This ordering is the whole point of
   the step:** a test that red-fails on an import error has proven only that the file is absent — it
   has never exercised its own assertion, so it cannot demonstrate the assertion discriminates. The
   stub makes step 1's and step 2's reds land on the `assert`, which is what watched-fail-first
   (`45-testing-strategy.md:24`) actually requires. The wrong stub is never committed; step 3
   replaces it in the same working session.
1. **Write the failing test for the anchored matcher and watch it go RED on the assertion.** In
   `tests/enforcement/test_plan_lock_release.py`, assert `finished_token()` returns a token for the
   **extracted value** `"✅ EXECUTED 2026-08-14"` (and, separately, that
   `status_value("**Status:** ✅ EXECUTED 2026-08-14")` yields that value) and **None** for
   `"Issue 1 RESOLVED (§2.8) … Tier-D is not yet ENABLED"`. Run
   `python -m pytest tests/enforcement/test_plan_lock_release.py -q` → **expect a failing assertion
   on the second case** (the substring stub returns `RESOLVED`), not a collection error. Record the
   red output.
   *Why this one first: an un-anchored substring match is the single defect that would make the
   inductive limb unsafe, and it is the one the spec proved wrong by measurement (6 false positives).*
2. **Write the failing test for the non-terminal partition and watch it go RED on the assertion.**
   Assert a lock with `status:"paused"` whose plan is archived IS flagged, and that
   `status:"released"` is skipped. Against the step-0 stub the `paused` case fails (it keys on
   `active` alone) — again a real assertion red, not an import error.
3. **Create `scripts/enforcement/check_plan_lock_release.py`** with, in order:
   - line 1 `#!/usr/bin/env python3`; **line 2 the coupling header**
     `# AFTER-EDIT: tests/enforcement/test_plan_lock_release.py` (mandated by
     `check_script_headers.py:11`; the sibling carries it at `check_pack_reachability.py:2`).
   - a module docstring naming the measured class it closes, the advisory contract, **and the two
     named exit triggers** (promote to blocking after two clean weekly syncs; delete in favour of the
     mechanical writer after >2 NEW instances) — the spec requires those live in the docstring where
     the next agent reads them, not only in the spec.
   - `NON_TERMINAL` / `TERMINAL` / `FINISHED_TOKENS` as module constants.
   - `normalise_status()` applied before EVERY partition test. ⚠️ **The partition is case-folded
     and that is not cosmetic** — the fleet carries a live `"RELEASED"` (upper-case) lock at
     `tryton-crm/2026-08-25-plan-2-turkish-catalogue-integrity-and-release-closure.json`, on a
     correctly archived plan. Un-folded, it lands in `UNKNOWN STATUS` and tryton-crm prints a false
     positive on every gate run.
   - `strip_decoration()` — strip leading whitespace, `**`, `✅`, `🚧`, `✔️`, `—`, `-`.
   - `finished_token()` — `strip_decoration` then `startswith` against `FINISHED_TOKENS`, case-folded.
     **Never a substring search.** `RESOLVED` and `CONVERGED` are deliberately absent.
   - `resolve_plan()` — **four-way** stem resolution, in order: `plans/<stem>.md` ·
     `plans/<stem>/<stem>.md` · `plans/archived/<stem>.md` · `plans/archived/<stem>/<stem>.md`.

     ⚠️ **This is THIS plan's own design decision, not an inherited convention — an earlier draft
     cited `check_plan_tickets.py:1481` as precedent and that citation is false.** That line is
     `cand = root / "docs" / "development" / "plans" / lf.stem`, gated on `cand.is_dir()` at
     `:1482`: it tries **one** location, never `.md`, never `archived/`. An implementer following
     the citation resolves every single-file `.md` plan — the majority of the corpus — to
     `missing`, inverting fixtures a, c, d, h and k, and Phase B step 5's live assertion returns
     `ORPHAN` instead of `STALE LOCK`. Each of the four branches gets its own fixture.

     Also resolve the lock's **`plan` field** through the same stem-tolerant resolver: 11 fleet
     locks store a bare stem rather than a path, and treating those as unresolved emits a
     standalone `PLAN FIELD STALE` on a lock whose field is correct (measured live on
     `transdoc/2026-08-25-plan-2-seam.json`, `status:"active"`, `plan:"2026-08-25-plan-2-seam"`). Record `field_resolved=False` when the raw `plan`
     value does not resolve as stored — that is the `PLAN FIELD STALE` signal.

     ⚠️ **`PLAN FIELD STALE` is emitted ONLY for NON-TERMINAL locks, and that scoping is the
     difference between 2 findings and 37.** The spec derived this rule from a hub-only count (2 of
     48). Measured across the fleet it is far noisier — unless scoped:

     ```
     $ stored-path resolution across 203 path-storing fleet locks
       non-terminal  STALE     2      non-terminal  resolves     4
       terminal      STALE    35      terminal      resolves   162
     ```

     **37 of 203 (18.2%) unscoped — 35 of them on TERMINAL locks**, i.e. dead history on finished
     work: unactionable, and re-pointing a released lock's field would destroy provenance
     (`fabrik-execute-plan.md:69-71`). Landing it unscoped fires 37 times on day one — the exact
     "fires fleet-wide and gets ignored" failure § Constraints warns about, reached by the same
     hub-only-measurement mistake the upstream spec spent a review round correcting. Scoped to
     non-terminal it fires **twice**, and both locks are already flagged by another rule
     (`brand-identiy-creator` STALE, `whatsapp-agent` ORPHAN) — so the label adds *detail to an
     existing finding*, never a standalone line. Consequently the **hub has zero** live cases for
     this rule: both its stale paths sit on `released` locks.
   - `classify()` — the jurisdiction test FIRST (a lock carrying a **`holder`** field **and**
     `owned_paths == ["**"]` ⇒ `FOREIGN LOCK`, **returned immediately**, never judged), then the
     case-folded status partition, then rule 1A / 1B / rule 2 / `ORPHAN LOCK` / `UNEVALUABLE`.

     ⚠️ **`UNKNOWN STATUS` ACCUMULATES, it does not return** — only `FOREIGN LOCK` short-circuits.
     A misspelled non-terminal status (`"actve"`) on an archived plan must yield **both**
     `UNKNOWN STATUS` and `STALE LOCK`; returning early would suppress a real finding behind a typo,
     and fixture i (`"finshed"` on a non-archived plan) cannot discriminate the two behaviours.
     This is why `classify()` returns a list.

     ⚠️ **The jurisdiction test must NOT inspect the `plan` value's shape — an earlier draft of this
     step also required "no path separator" and that conjunction is measurably wrong.** One of
     fabrik-lib's seven repo-locks carries a `/` inside its prose description:

     ```
     $ repo-lock plan values — does the description contain a separator?
     repo-lock-OBASAK-EB840-2222300.json  sep=True   holder=True  owned=['**']
     repo-lock-OBASAK-EB840-344494.json   sep=False  holder=True  owned=['**']   (+5 more, sep=False)
     ```

     With the separator clause, that lock fails the conjunction, falls through, and is reported as
     `ORPHAN LOCK` — the exact noise the `FOREIGN LOCK` class exists to prevent, in the one repo that
     has seven of them. Keying on prose is what broke it.

     **`holder` + `owned_paths == ["**"]` is decisive, and the two signals agree perfectly across the
     whole fleet** — no plan lock owns the entire repo:

     ```
     $ (owned_paths == ["**"], holder present) across every fleet lock (~213 at measurement)
     {(True, True): 7, (False, False): 207}     # zero mixed cases
     ```

     Either condition alone would suffice; the conjunction is kept because a future writer adding one
     without the other should be surfaced, not silently absorbed.
   - **Reuse `check_convergence.EXECUTED`** for the canonical form — applied by `status_value()` to
     the **raw `Status:` line** (it requires the literal `Status` + `:`, so it can never match an
     extracted value); `finished_token()` then handles the legacy alternation on the value, using
     the same anchor discipline. Do not edit the import target.

     ⚠️ **Name the import idiom explicitly — `final_gate.py:261` invokes optional checks as a BARE
     SCRIPT** (`run_cmd([PYTHON, str(full_path)] + args)`), so `sys.path[0]` is
     `scripts/enforcement/` and a package-relative `from .check_convergence import EXECUTED` raises
     `ImportError` — which, per the `main()` note above, lands as a fleet-wide blocking red. Use the
     same-dir idiom the siblings use (`check_pack_reachability.py:52-58`, `check_doc_stubs.py:28-30`,
     `check_phase_tests.py:31-33`). On the test side, `tests/enforcement/` has **no `conftest.py`**
     and `pyproject.toml` sets no `pythonpath`, so the test file does its own
     `sys.path.insert(0, REPO / "scripts" / "enforcement")`, as 11 siblings do (e.g.
     `test_pack_reachability.py:27-31`).
   - every field read is `.get()` with an explicit absent-case; **"absent" is never conflated with
     "null"** (rule 2 keys on `final_commit` *missing or falsy*, and the message says which).
4. **Run steps 1–2's tests → GREEN.** Then complete the behavior suite from the spec's fixture table
   (a–l), each under `tmp_path`:

### Behavior Contract

- **Given** a lock `status:"active"` whose stem resolves under `plans/archived/`, **When** the check
  runs, **Then** it emits `STALE LOCK` naming that lock (spec fixture a).
- **Given** a non-terminal lock with a completion timestamp and `final_commit` **absent**, **When** the
  check runs, **Then** it emits `HALF-APPLIED FINISH` (fixture b).
- **Given** a lock `status:"active"` whose plan is under `plans/` reading `**Status:** ✅ EXECUTED
  2026-08-14`, **When** the check runs, **Then** it emits `LIKELY STALE LOCK` quoting the token
  (fixture c).
- **Given** an archived plan reading `Status: NOT_STARTED` with an active lock, **When** the check
  runs, **Then** the message says `ARCHIVED` and quotes `NOT_STARTED`, and **never** asserts
  `EXECUTED` (fixture d).
- **Given** an archived plan-set directory with **no** `<dirname>.md` spine, **When** the check runs,
  **Then** the lock is counted `UNEVALUABLE`, never `terminal` (fixture e).
- **Given** a plan whose status is `Issue 1 RESOLVED (§2.8) … not yet ENABLED`, **When** the check
  runs, **Then** the lock is **NOT** flagged (fixture f — the substring false positive).
- **Given** a `paused` or `blocked` lock on an un-archived, unfinished plan, **When** the check runs,
  **Then** it is **NOT** flagged (fixture g — the sanctioned carve-out, both spellings).
- **Given** a `paused` lock whose plan IS archived, **When** the check runs, **Then** it IS flagged —
  non-terminal gates the rule, it is not itself the finding (fixture h).
- **Given** a lock with `status:"finshed"` (a typo), **When** the check runs, **Then** it emits
  `UNKNOWN STATUS` and is never counted terminal (fixture i).
- **Given** a non-terminal lock with `finished_at` set and `final_commit` absent, **When** the check
  runs, **Then** it emits `HALF-APPLIED FINISH` — the timestamp **key family**, not just
  `completed_at` (fixture j).
- **Given** a **non-terminal** lock whose `plan` field does not resolve but whose stem does, **When**
  the check runs, **Then** it emits `PLAN FIELD STALE` **and** still evaluates the lock normally
  (fixture k).
- **Given** a **terminal** (`released`) lock whose `plan` field does not resolve, **When** the check
  runs, **Then** it is **NOT** flagged — 35 of the fleet's 37 stale paths are this shape, and
  re-pointing a released lock destroys provenance (fixture m).
- **Given** a `repo-lock-<host>-<pid>.json` carrying `holder` and `owned_paths:["**"]` — **including
  the one whose prose `plan` value contains a `/`** — **When** the check runs, **Then** it emits
  `FOREIGN LOCK`, counted but not judged, and **never** `ORPHAN LOCK` (fixture l).
- **Given** the motivating instance's exact shape — `active`, plan archived, `completed_at` set,
  `final_commit` null — **When** the check runs, **Then** it emits **BOTH** `STALE LOCK` and
  `HALF-APPLIED FINISH` for that one lock, and the census counts it under both labels (fixture n).
  *A single-finding-per-lock implementation passes every other row and fails only this one.*
- **Given** a corpus with **>=1 finding**, **When** `main()` runs, **Then** it returns **0** and
  prints the findings. *The single highest-consequence row: `return 1 if findings else 0` turns this
  advisory row into a blocking red across ~46 repos.*
- **Given** a corpus in which every lock is terminal, **When** the check runs, **Then** it prints
  `NOTHING VERIFIED`, never `OK`.
- **Given** a corpus with >=1 evaluable non-terminal lock and no findings, **When** the check runs,
  **Then** it prints `OK` with the census — the other half of the fork, which an
  always-`NOTHING VERIFIED` implementation would otherwise satisfy untested.
- **Given** a repo with **no `.fabrik/plan-locks/` directory at all** (30 of ~46 synced repos),
  **When** the check runs, **Then** it exits 0 with **EMPTY stdout** — not `NOTHING VERIFIED`.
  *`warn_only` implies `advisory`, so stdout prints on every pass; without this the check emits a
  block on every gate run forever in 30 repos. The model it copies self-skips out of scope:
  `check_vendored_drift.py` prints 3281 bytes at the hub and 0 in a project.*
- **Given** a lock whose status is `"RELEASED"` (upper-case, live today in `tryton-crm`), **When** the
  check runs, **Then** it is treated as **terminal** and not flagged — the partition is case-folded.
- **Given** an archived plan whose spine EXISTS but carries **no `Status:` line**, **When** the check
  runs, **Then** the lock is counted `UNEVALUABLE`, never "no token means not finished". *Latent
  today (0 such spines fleet-wide) and exactly the fail-silent-green the `NOTHING VERIFIED` fork
  exists to stop.*
- **Given** an unreadable / non-dict / malformed lock JSON, **When** the check runs, **Then** it exits
  **0**, counts the lock `UNEVALUABLE`, and prints no traceback.

5. **Prove red-on-revert for every guard a do-nothing implementation would pass.** ⚠️ **An earlier
   draft named two (f and l) and was wrong about both the count and the membership** — an
   independent reviewer ran the do-nothing model M0 (`classify()` always returns `[]`; `main()`
   always prints `NOTHING VERIFIED` and returns 0) over the whole contract. **`l` actually FAILS M0**
   (it asserts a positive, `FOREIGN LOCK`); only its *"never `ORPHAN LOCK`"* clause is vacuous. And
   five rows pass M0 that the draft never named. The real list, each neutered → its row must go RED
   → restore:

   | mutant to inject | row that must go RED |
   |---|---|
   | `finished_token` → substring search | f (the substring false positive) |
   | flag any non-terminal lock regardless of plan state | **g** — the carve-out the whole design rests on; a, b, c and h all still pass this mutant |
   | drop the jurisdiction test | l's *"never `ORPHAN LOCK`"* clause |
   | always print `NOTHING VERIFIED` | the **`OK`-branch** row — otherwise half the output fork is untested |
   | missing spine ⇒ counted terminal | e (`UNEVALUABLE` never counted clean) |
   | `PLAN FIELD STALE` unscoped | m (terminal locks not flagged) |
   | `main()` → `return 1 if findings else 0` | the exit-0-with-findings row (**the fleet-red guard**) |

   **The neutered state is never staged or committed.**
6. **Append the `CHANGELOG.md` `[Unreleased]` entry — BEFORE the gate, not after** —
   `### Added — Plan-lock release advisory gate (2026-08-26)`. ⚠️ **Phase A cannot go green without
   it, and the ordering is the point.** `check_doc_sync.py:32` counts `scripts/` as
   `SIGNIFICANT_DIRS` with no exemption, and `:264-270` **ERRORs** (`return 1` at `:355-361`) on
   significant code staged without `CHANGELOG.md`; it is registered **blocking** at
   `final_gate.py:952-954`. An earlier draft both said *"no doc row is owed by Phase A"* and placed
   this step after the gate run — either alone reddens the gate and pushes the agent into
   improvising a governance-surface edit mid-phase. Then run
   `python scripts/enforcement/check_doc_sync.py`. *(The subsystem doc itself still lands in Phase B,
   where the check becomes a live gate row.)*
7. Run the phase gate → green.
8. **`/fabrik-review` on Phase A's changed surface — BLOCKING**, to a coverage-adjudicated exit: pool
   finder breadth (`fanout("review", …, mode="read_only")`, flywheel-recorded, `set_quality`
   back-filled) **plus** native Opus for the authoritative pass; refute, prove-before-fix with a kept
   regression test, re-run the gate after each fix. Iterate to `found: 0`.
9. Commit Phase A — explicit paths only, with Agent Provenance Trailers (`Agent-Role: primary`,
   `Agent-Name: infra`, `Agent-Phase: A`).

**Phase A gate:** `python -m pytest tests/enforcement/test_plan_lock_release.py -q` → all pass; then
`git add scripts/enforcement/check_plan_lock_release.py tests/enforcement/test_plan_lock_release.py
&& python scripts/enforcement/check_script_headers.py` → output **names the file with no warning**.
⚠️ **The `git add` is load-bearing:** `check_script_headers.py:47-52` inspects `git diff --cached
--name-only` and returns 0 immediately when nothing is staged, so running it before the commit
certifies nothing — "no finding" and "no file examined" print identically. It is WARN-only (`:16`),
so exit 0 is not the signal; the named-file line is.

---

## Phase B — register it every-tier, pin the registration, document the subsystem

**Deliverable:** the check is a live advisory row in every gate tier, the registration is pinned
against the two mutants that would silently disable it, and the subsystem has its own reference doc.

### Interfaces

**Consumes** from Phase A: `scripts/enforcement/check_plan_lock_release.py` and every symbol in
Phase A's *Produces* block, by those exact names.
**Produces:** a `run_optional_check(...)` row named `"Plan-lock release"`; `docs/reference/plan-lock-lifecycle.md`.

### Steps

1. **Write the AST registration pin FIRST and watch it go RED.** In
   `tests/enforcement/test_final_gate_registration.py`, add
   `test_plan_lock_release_registered_every_tier()` asserting the `"check_plan_lock_release.py"`
   literal has **no `ast.If` ancestor whose test mentions the name `tier` at all — ANY operator**.
   Run → **RED** (no registration exists yet).

   ⚠️ **Do NOT mirror `_phase_tests_in_tier2_only` — a literal mirror is VACUOUS against the two
   mutants that actually matter.** That helper (`test_final_gate_registration.py:38-49`) matches
   only `ast.Compare` + `ast.Eq` + `comparators[0].value == 2`. The `if tier …` census in
   `final_gate.py` is: `:884 if tier in (1, 2):` (`ast.In`) · `:1089 if tier == 1:` ·
   `:1093 if tier == 2:` · `:1306 if tier == 3:` · `:1451 if tier >= 2:` (`ast.GtE`). Both
   independent reviewers implemented the mirrored helper and ran the mutants:

   ```
   pin passes on mutant [if tier in (1,2):]  -> True   <-- registration NOT every-tier, pin GREEN
   pin passes on mutant [if tier >= 2:]      -> True   <-- registration NOT every-tier, pin GREEN
   pin passes on mutant [if tier == 2:]      -> False
   ```

   `if tier in (1, 2):` at `:884` is **four lines below the insertion point** — the single most
   likely place a later edit moves it — and an `Eq`-only pin waves it through, killing the check in
   `--systemic`. `if tier >= 2:` kills it in `--lean`, the mode this plan calls load-bearing.
2. **Give the pin its own built-in red with ALL THREE mutants**, per that file's established pattern
   (`test_final_gate_registration.py:1-11`): feed the helper synthetic sources nesting the
   registration inside `if tier == 2:`, `if tier in (1, 2):` and `if tier >= 2:`, and assert it
   returns False for **each**. A single-mutant red is how the mirrored version passed while blind.
3. **Register the check in `scripts/final_gate.py`** immediately after the
   `check_vendored_drift.py` block (`:874-880`) and **before** the `# ── Tier 1: Showstoppers only ──`
   marker at `:882` — that position is what makes it every-tier:
   ```python
   results.append(
       run_optional_check(
           "scripts/enforcement/check_plan_lock_release.py",
           "Plan-lock release",
           warn_only=True,
       )
   )
   ```
   Carry a comment naming **why every-tier**: `--lean` is the mode agents run *during* execution,
   which is exactly when a lock is live; a tier-2-only registration would be absent precisely then
   (and `WARN_ONLY_CHECKS` is populated as a side effect of the call, `:246-248`, so a tier-gated
   check is not even listed as advisory in the modes where it does not run).
4. Run step 1's pin → **GREEN**.
5. **Verify the check against the real fleet, read-only.** Copy another repo's lock corpus into
   `tmp_path` and assert the check finds the known live instance:
   ```
   /opt/brand-identiy-creator/.fabrik/plan-locks/2026-08-10-plan-1-deep-research.json
     → status:"active", plan archived → STALE LOCK
   ```
   This is the plan's only assertion against real-world data and it is **read-only on a copy** — the
   lock belongs to another repo and is never touched. *(If that lock has been released by the time
   this runs, the assertion is re-pointed at whatever the fleet sweep reports and the plan's Evidence
   is updated — the corpus is live and moved twice during the spec review.)*
6. **Write `docs/reference/plan-lock-lifecycle.md`** (Doc Sync Matrix: new subsystem ⇒ a dedicated
   reference doc; `ls docs/reference/ | grep -i lock` returned nothing, so this extends nothing).
   Content: the lock's real lifecycle (created step 7, released Finish step 5, `plan` repointed Finish
   step 6), the seven status values and the non-terminal/terminal/unrecognised partition, the eight
   labels, the two sanctioned steady states, the `FOREIGN LOCK` jurisdiction boundary, and the two
   named exit triggers. **Annotate as pool-reconciled + native-verified** (`scripts/doc_reconcile.py`),
   not hand-authored from scratch.
7. **Docs (owned by this phase):**
   - **`docs/workflows/FINAL_GATE_WORKFLOW.md`** — add the row for the new every-tier advisory
     check. ⚠️ **Not optional and easy to miss:** `final_gate.py:2` is
     `# AFTER-EDIT: docs/workflows/FINAL_GATE_WORKFLOW.md`, and `check_script_headers.py:73-77`
     WARNs when a staged script's header names a coupled file that is not also staged. That doc is
     the canonical per-check inventory (`:161-162` list the other every-tier rows), so omitting it
     leaves the gate's own reference silently wrong about what runs.
   - `INDEX.md` row for both new files, and the `docs/README.md` row for the reference doc.
     (`check_doc_index.py:69-83` hard-fails on a tracked `docs/**/*.md` missing from `INDEX.md`, and
     `docs/reference/` is not in its `EXCLUDE_PREFIXES` — so the INDEX row is gate-enforced, not a
     courtesy.)
   - The `CHANGELOG.md` entry was already appended in **Phase A step 6**; do not duplicate it.

   `INDEX.md`, `docs/README.md` and `CHANGELOG.md` are shared-append governance surfaces — appended,
   never overwritten, and deliberately **outside** File Scope.
8. Run the phase gate → green.
9. `python scripts/enforcement/check_doc_sync.py` + `python scripts/enforcement/check_doc_stubs.py`.
10. **`/fabrik-review` on Phase B's changed surface — BLOCKING**, same methodology and same
    pool-breadth + native-Opus dispatch as Phase A step 8. Iterate to `found: 0`.
11. **`/fabrik-docs-review`** on the new reference doc — converge the docs to a truthful fixed point
    (the touch-on-change gates prove presence, not correctness).
12. **Full gate + convergence:** `python scripts/final_gate.py --check --json` → `"status":"success"`,
    and `python scripts/enforcement/check_convergence.py` → exit 0. **A green gate is necessary but
    not sufficient** — it proves citations and format, not that the design is sound; the real proof is
    the Evidence below plus the red-first runs in Phase A.
13. **Commit from `/opt/fabrik` itself, not a worktree** — the governance-sync pre-commit hook guards
    on `[ "$(pwd)" = "/opt/fabrik" ]` (`.pre-commit-config.yaml:67`). Then **verify distribution
    landed** in a sample project (`ls /opt/transdoc/scripts/enforcement/check_plan_lock_release.py`);
    if it did not, run `python scripts/sync_enforcement_to_projects.py --force`. Explicit paths +
    provenance trailers (`Agent-Phase: B`).

**Phase B gate:** `python -m pytest tests/enforcement/test_final_gate_registration.py
tests/enforcement/test_plan_lock_release.py -q` → all pass; `python scripts/final_gate.py --check
--json` → `"status":"success"`; the new row appears in `--lean`, default and `--systemic` output.

---

## Review Record — the rubric that armed the convergence review

Run at review time over this plan's `## File Scope (owned paths)`, which IS the changed-path set:

```
$ python scripts/review_rubric.py --changed \
    scripts/enforcement/check_plan_lock_release.py \
    tests/enforcement/test_plan_lock_release.py \
    tests/enforcement/test_final_gate_registration.py \
    scripts/final_gate.py \
    docs/reference/plan-lock-lifecycle.md
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# 119 lines / 23468 bytes

## FLOOR — always injected, regardless of glob
  core/35-security-auth.md · core/25-data-postgres.md · core/30-ops.md · 12-FACTOR (all twelve axes)

## MATCHED — packs whose globs hit the changed paths
  core/10-python.md          (hit: check_plan_lock_release.py, final_gate.py,
                                   test_final_gate_registration.py)
  core/40-documentation.md   (hit: docs/reference/plan-lock-lifecycle.md)
  core/45-testing-strategy.md (hit: test_final_gate_registration.py, test_plan_lock_release.py)
# promote-to-check_*: 51 injected mandate(s) look deterministically greppable
```

The MATCHED packs are reproduced in full in the Context Ledger rows above; the FLOOR block is
summarised to its pack list rather than pasted whole, because its ~100 lines are auth / RLS /
compose / Traefik / session mandates for a deployed service and this deliverable is a stdlib CLI
script with no network, no DB, no container and no request path. **Every FLOOR class is still
adjudicated below** — summarising the source is not skipping the sweep.

⚠️ **One rubric mandate is REFUTED for this repo, recorded so it is not re-raised.**
`45-testing-strategy.md` says *"Run tests: `uv run pytest tests/` (never bare `pytest` — Fabrik
uses `uv`)"*, and this plan's gates use `python -m pytest`. The pack is written for **scaffolded
projects**; the hub runs its own suite differently, and the hub's own gate proves it:

```
$ grep -n 'pytest' scripts/final_gate.py | sed -n '4p'
774:  [PYTHON, "-m", "pytest", "tests/", "-x", "-q", "--color=no", "-p", "no:cacheprovider"],
```

Three archived, converged hub plans use the same form (`2026-07-20-plan-1-docs-truth-convergence.md:199`,
`2026-08-04-plan-1-spine-ticket-plans.md:348`, `2026-08-10-plan-2-review-loop-overhaul.md:424`).
`python -m pytest` is correct here.

## Coverage Checklist

Derived from the `review_rubric.py` invocation above (FLOOR + MATCHED) plus the four standing
recurrence classes. Every row carries a verdict and the paths actually hunted.

| # | Class (source) | Verdict | Evidence — what was hunted |
|---|---|---|---|
| 1 | Auth / JWT / session handling (FLOOR `core/35-security-auth.md`) | REFUTED | The deliverable has no auth surface: no request path, no token, no session. `classify()` reads local JSON and prints. No row applies. |
| 2 | Secrets / config in code; grouped env sets (FLOOR `35` + `10-python.md`) | CLEAN | The check takes **no** configuration — no env var, no DSN, no secret. Verified against the plan's Interfaces block: `main(argv)` only. |
| 3 | Postgres / migrations / schema (FLOOR `core/25-data-postgres.md`) | REFUTED | No DB. stdlib only (`json`, `pathlib`, `re`, `argparse`), pinned in § Global Constraints. |
| 4 | Docker / compose / Traefik / ports / memory limits (FLOOR `core/30-ops.md`) | REFUTED | Ships no service, no container, no port. One CLI script invoked in-process by `final_gate.py`. |
| 5 | 12-Factor, all twelve axes (FLOOR) | CLEAN | Swept in § Global Constraints, which copies all twelve verbatim. The two that could bite a CLI: **XI** — the check prints to stdout only, never opens a log file; **III** — no config at all. |
| 6 | Python discipline (MATCHED `core/10-python.md`) | CLEAN | No `uv`/dep change (Global Constraints forbids touching `pyproject.toml`); no `logger.exception()`; no file logging; stdlib imports only. |
| 7 | Documentation discipline (MATCHED `core/40-documentation.md`) | CLEAN | Phase B step 6 emits the dedicated `docs/reference/plan-lock-lifecycle.md` (checked-before-create: `ls docs/reference/ \| grep -i lock` → empty); step 7 adds the `INDEX.md` + `docs/README.md` rows; step 11 runs `/fabrik-docs-review`. Trailer-block rule applies at commit (Phase A step 9, Phase B step 13). |
| 8 | Testing strategy (MATCHED `core/45-testing-strategy.md`) | FIXED (4) | 21-row Behavior Contract, one row per distinct observable behavior. **This class absorbed the most fixes of any row (9).** Red-first was producing a `ModuleNotFoundError` rather than an assertion failure → Phase A gained **step 0** (a deliberately-wrong stub). The vacuity audit named the wrong two rows: `l` actually FAILS the do-nothing model, while `g`, `e`, `k`, the `NOTHING VERIFIED` row and the (missing) `OK`-branch row all passed it — step 5's red-on-revert list is now a seven-mutant matrix. Six rows were added: exit-0-with-findings, the `OK` branch, the empty-corpus inert contract, upper-case `RELEASED`, a spine with no `Status:` line, and the multi-label lock. `uv run pytest` mandate REFUTED above with evidence. |
| 9 | **fail-open vs fail-closed on every gate/guard** (standing) | CLEAN | Deliberately **fail-soft by contract**: every failure path returns 0 with an honest line, because `warn_only=True` still FAILS the gate on non-zero exit (`final_gate.py:267-268`). The *reporting* side fails CLOSED instead — an unreadable lock becomes `UNEVALUABLE`, never a silent pass, and an all-unevaluable run prints `NOTHING VERIFIED`, never `OK`. Both directions are covered by Behavior Contract rows 13–14. |
| 10 | **cost / quota / limit accounting edges** (standing) | FIXED (1) | The check makes no paid call and holds no quota — but the **noise budget IS a limit-accounting edge, and pass 1 found a real defect here**: `PLAN FIELD STALE` was written unscoped off a hub-only count (2 of 48) and would have fired **37 times fleet-wide** on day one. Scoped to non-terminal it fires twice. The other limit in play — the gate's 500-char / 10-line advisory truncation — is answered by the census-line-first output contract (Phase A step 3). |
| 11 | **boundary / sentinel / prefix collisions** (standing) | CLEAN | This is the deliverable's dominant risk class and is where the spec's own review found most defects: the anchored-vs-substring token match (fixture f), the `repo-lock-` **prefix** that is a different protocol (fixture l), `complete` vs `completed` as distinct status values, and `absent` vs `null` for `final_commit`. All four have Behavior Contract rows. |
| 12 | **behavior-without-a-test** (standing) | FIXED (1) | Every one of the eight output labels has a Behavior Contract row; the registration position — the one behavior outside the check module — is pinned by the AST test in Phase B steps 1–2, with its own built-in red. **Pass 5 found one gap here and fixed it:** making `classify()` return a LIST created a multi-label behavior with no row, so fixture **n** was added (the motivating lock is simultaneously `STALE LOCK` and `HALF-APPLIED FINISH`); a single-finding implementation passes all fifteen other rows and fails only that one. |

## File Scope (owned paths)

- scripts/enforcement/check_plan_lock_release.py
- tests/enforcement/test_plan_lock_release.py
- tests/enforcement/test_final_gate_registration.py
- scripts/final_gate.py
- docs/workflows/FINAL_GATE_WORKFLOW.md
- docs/reference/plan-lock-lifecycle.md

*(`CHANGELOG.md`, `INDEX.md`, `docs/README.md`, `docs/FEATURES.md` and `docs/LESSONS_LEARNT.md` are
shared-append governance surfaces and stay OUT of File Scope by contract — locking them would make
every pair of concurrent plans collide.)*

⚠️ **Serialization note:** `scripts/final_gate.py` is a high-traffic hub path. Before starting,
confirm no sibling plan's lock owns it — this is exactly the class of overlap that BLOCKED the
inert-rule-packs plan at step 7 and motivated this whole check.

## Evidence

**Phase A**

- `scripts/enforcement/check_convergence.py:122-126` — the `EXECUTED` regex to reuse, read this turn;
  its rationale at `:116-118` reaches the same anchoring conclusion the spec reached by measurement.
- `scripts/enforcement/check_plan_tickets.py:212-218` — `NEVER_ROUTE_PREFIXES` contains both
  `scripts/enforcement/` and `scripts/final_gate.py`, which is what forces native execution:

```
$ sed -n '212,218p' scripts/enforcement/check_plan_tickets.py
NEVER_ROUTE_PREFIXES = (
    "scripts/enforcement/",
    "scripts/final_gate.py",
    "alembic/",
    "db/migrations/",
    "secrets/",
)
```

- The fixture table is not invented — every shape is measured. The classifier's hardest cases,
  re-run at plan time:

```
$ plan-shaped vs other, across all 16 /opt repos carrying locks
plan-shaped 188 | other 25          # 7 of the 25 are fabrik-lib repo-lock-<host>-<pid>.json
$ anchored vs substring finished-token match
LIVE: anchored=5 substring-only=1   ARCH: anchored=61 substring-only=5
```

**Phase B**

- `scripts/final_gate.py:874-880` — the `check_vendored_drift` registration, read this turn: it sits
  above the `# ── Tier 1: Showstoppers only ──` marker at `:882`, which is precisely the every-tier
  position this plan copies.
- `scripts/final_gate.py:267-268` — the `warn_only` contract that forces every failure path to exit 0.
- `tests/enforcement/test_final_gate_registration.py:1-11` — the AST-pin pattern *and* its
  built-in-red convention, both reused verbatim by Phase B steps 1–2.
- The fleet corpus this check will judge on landing day, and the live instance Phase B step 5 asserts
  against:

```
$ fleet lock corpus + day-one output — SNAPSHOT, 2026-08-26 ~13:30 UTC
~213 locks across 16 repos; {released 197, active 6, executed 6, complete 2, completed 1, paused 1}
brand-identiy-creator  2026-08-10-plan-1-deep-research.json  active  STALE (plan archived)
whatsapp-agent         plan-6-multitenant-whatsapp.json      paused  ORPHAN (no plan found)
fabrik-lib             repo-lock-OBASAK-EB840-344494.json    active  FOREIGN (not a plan lock)
```

⚠️ **The TOTAL drifts; the RATIOS and the named instances do not.** This corpus is mutated by other
sessions while the check reads it — the total moved 212 → 213 → 215 during this review alone, and a
later pass measured `active 5` plus an upper-case `RELEASED` and a `blocked` that were not present at
13:30. Treat the total as a snapshot. **The load-bearing figures are the ones that reproduce on every
re-run:** the jurisdiction discriminator (7 both / 0 mixed), the `PLAN FIELD STALE` split
(35 terminal / 2 non-terminal), the repo-lock-with-a-separator count (1), and the named instances
above. Phase B step 5 re-runs the sweep rather than trusting this block.

- `ls docs/reference/ | grep -i lock` → no output, so the subsystem doc extends nothing and is a
  genuinely new file (checked before create, per `CLAUDE.md`).

## Self-audit

**Grounding passes run.** Opened and read this turn: `check_convergence.py:110-130`,
`check_plan_tickets.py:212-218`, `final_gate.py:215-252` / `:875-884` / `:1140-1155`,
`check_pack_reachability.py:240-315`, `test_final_gate_registration.py:1-40`,
`check_script_headers.py:11`, `45-testing-strategy.md:1-40`, `/opt/fabrik-lib/README.md`. Ran
`select_rules.py` (25 ACTIVE packs; the four binding here are in the Context Ledger). Re-ran the
fleet lock sweep and the anchored-matcher measurement. **Found and corrected while planning:** the
deliverable is entirely never-route, which the spec never states — that flips the whole dispatch
policy to native and is now in § Execution Discipline.

**(a) Coverage — every "What we already agreed" item maps to a phase.** Goal → A (classifier) + B
(registration makes it run). Standalone advisory check → B step 3. Executable backing for
`fabrik-catchup` probe 1 → A step 3 `classify()` adopts its taxonomy. Rejected alternatives → nothing
in either phase revisits them. stdlib-only → Global Constraints; no manifest edit is authorised. The
spec's eight labels, its twelve fixtures (plus **m**, added by this review's pass 1), the
`NOTHING VERIFIED` fork, the census line, never-auto-reclaim, and the remediation wording →
Phase A steps 3–4 + the 21-row Behavior Contract. Registration tier → B steps 1–4.
`AFTER-EDIT` header → A step 3. **No gap found; no phase added.**

**(b) Cross-phase signature consistency.** Phase B consumes exactly the names Phase A's *Produces*
block exposes — `check_plan_lock_release.py` (path), and the module needs no importable symbol for B
beyond being executable, since `run_optional_check` shells out by path. The one shared symbol name
between the two phases is the display string `"Plan-lock release"`, used in B step 3 and asserted in
B's gate. **Checked: no name appears in one phase and differently in the other.**

**(c) Independent review coverage.** The author's own passes cannot substitute for author-blindness,
so the convergence loop dispatched **pool breadth (3 finders, flywheel-recorded) plus TWO independent
Opus grounders**. They agreed on the most severe finding without seeing each other's work — the AST
registration pin, mirrored as originally specified, is **vacuous against the two mutants that matter**
(`if tier in (1, 2):` is `ast.In`, `if tier >= 2:` is `ast.GtE`; the existing helper matches only
`ast.Eq` vs `2`). Both implemented the helper and ran the mutants rather than reasoning about it.

Between them they also caught: `main()` needing to return **0 even with findings** (the enforcement
corpus is split, and the wrong habit reddens ~46 repos on the first sync); a **false citation** —
`check_plan_tickets.py:1481` resolves one location gated on `is_dir()`, not the four-way `.md`+archived
resolution this plan attributed to it; a live upper-case `"RELEASED"` lock in `tryton-crm` that an
un-folded partition reports as `UNKNOWN STATUS`; step 1's fixture handing a full `Status:` LINE to a
function specified to take a VALUE, making step 4 **unreachable**; a bare-stem `plan` field in
`transdoc` that emits a standalone `PLAN FIELD STALE` the plan says cannot happen; the missing
`docs/workflows/FINAL_GATE_WORKFLOW.md` coupling; the absent inert contract (30 lock-less repos would
print a block on every gate run forever); the `check_doc_sync` **blocking** ERROR that would have
reddened Phase A; and a vacuity audit that named the wrong rows.

**Fixed-point claim.** Reached: the closing pass re-read the whole plan, re-ran every embedded probe,
and made zero edits with an identical md5 (see the Pass Ledger in the review report).

## Pass Ledger — `/fabrik-plan-review`, 2026-08-26

| Pass | axes re-checked | raised | new: | edits | note |
|-----:|---|---:|---:|---:|---|
| 1 | rubric armed · Coverage Checklist derived · pool finders merged | 5 | 5 | 10 | `uv run pytest` mandate REFUTED for the hub; red-first, jurisdiction and `PLAN FIELD STALE` scoping fixed |
| 2 | cross-references to pass-1 edits | 2 | 2 | 2 | stale fixture count, stale step-5 header |
| 3 | every `path:line` citation re-resolved | 2 | 2 | 3 | self-referential line count made drift-robust |
| 4 | File Scope · placeholders · gate runnability | 1 | 1 | 0 | the one candidate was my checker's bug — REFUTED |
| 5 | Interfaces signatures | 2 | 2 | 3 | `classify() -> Finding \| None` cannot express multi-label locks; fixture n added |
| 6 | full structural + gates | 0 | 0 | 0 | quiet — **and wrong to trust**, see pass 7 |
| 7 | **independent grounders: pool ×3 + Opus ×2** | 15 | 15 | 15 | the AST pin was vacuous; `main()` exit-0; a false citation; case-folding; an unreachable step 4 |
| 8 | step ordering after the merge | 2 | 2 | 2 | CHANGELOG step sat *after* the gate it must precede |
| 9 | all probes re-run | 2 | 2 | 2 | fleet totals drifting mid-review → snapshot + durable-ratio split |
| 10 | all probes · structural · gates | **0** | **0** | **0** | ✓ md5 identical → **CONVERGED** |

`new:` falls 5 → 2 → 2 → 1 → 2 → 0 → **15** → 2 → 2 → 0. **The spike at pass 7 is the point of this
ledger:** pass 6 was a genuine author no-op, and had the loop exited there, fifteen defects — six of
them MAJOR, two of them fleet-reddening — would have shipped. An author's quiet pass measures what
occurred to the author. Only the independent grounders moved the number.

Durable probes re-run at the close and reproducing verbatim: `NEVER_ROUTE_PREFIXES` contains both
deliverable surfaces · per-phase READ sets 153924 / 137344 bytes · jurisdiction discriminator 7 both
/ 0 mixed · `PLAN FIELD STALE` 35 terminal vs 2 non-terminal · 1 repo-lock whose prose `plan` carries
a separator · `check_plans` and `check_convergence` both exit 0.

## Residual unknowns

**RESOLVED**

- *Monolith or spine+ticket?* Monolith. Two phases (<3), the projected file is ~300 lines, and each
  phase's READ set is far under `READ_BUDGET_BYTES` (262144).
- *Does the check need a manifest entry to reach the fleet?* No — `scripts/enforcement/` is a
  recursive synced directory (`fabrik_synced_manifest.py:100-101`, `:259-272`).
- *Which registration tier?* Every-tier, above the `# ── Tier 1` marker, matching
  `check_vendored_drift.py` — because `--lean` is the mode agents run while a lock is live.
- *Does a `docs/reference/` doc for this already exist?* No (`ls | grep -i lock` → empty).
- *Is a fabrik-lib module applicable?* No — BUILD project-local; the README's modules are runtime app
  capabilities, and this encodes fabrik's own governance protocol.

**STILL OPEN — each with its resolution step**

1. **The live assertion's target may be released before Phase B runs.** The fleet corpus moved twice
   during the spec review. **Resolution (self-service, no operator input):** Phase B step 5 re-runs
   the fleet sweep first and points the assertion at whatever non-terminal-on-archived lock it
   reports; if the fleet is genuinely clean by then, the assertion degrades to the `tmp_path`
   fixture-corpus form and the plan's Evidence records that the live case was gone. The check is not
   blocked either way.
2. **`FOREIGN LOCK`'s only live instances sit in a repo the check does not reach by sync.** All
   seven `repo-lock-<host>-<pid>.json` files are in `/opt/fabrik-lib`, which is **sync-excluded**
   (`sync_enforcement_to_projects.py:795` — *"Reference implementation store (vendor, don't
   depend)"*). The class is still correct and cheap, and it must exist before fabrik-lib vendors the
   check — but nobody should read the 7 as "covered on landing day". **Resolution: none needed for
   this plan;** recorded so the next agent does not mistake the measurement for coverage. (Related:
   the hub currently owes fabrik-lib a packs-only pull path — a separate, already-filed decision.)
3. **Whether `blocked` locks in the wild use `status:"blocked"` or stay `status:"active"`.** The
   command contradicts itself (`:85` vs `:563`) and both readings are handled as non-terminal, so the
   check is correct under either. **Resolution:** none needed for this plan — the contradiction is
   filed against `commands/_sources/fabrik-execute-plan.md` as separate work, deliberately not fixed
   here because changing the lock protocol's prose carries its own fleet blast radius.
