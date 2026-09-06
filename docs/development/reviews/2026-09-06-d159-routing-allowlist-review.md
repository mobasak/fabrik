# Review — the hub-side operator routing ALLOWLIST (D-159)

Status: IN-PROGRESS
Surface: HEAD `aca5b0389dd72176273b7cff16e760e2e546b25b` + `git diff HEAD | md5sum` = `e66f70788a9aa6235a519512630adff6`
Anchor: NO prior review report exists for this scope (searched `docs/development/reviews/*routing*`, `*allowlist*` — 0 hits), so this run is a full WIDE pass 1, not a verification-and-delta.
Scope: `scripts/kilo-benchmarks/rank_task_subagents.py` (+85/-2) · `tests/test_operator_routing_deny.py` (+81/-4) · `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` (regenerated, +52/-62)
Routed up from `/fabrik-review-scoped` at its step-1 classification.

## Why this is a heavy surface (measured, not assumed)

`fabrik_synced_manifest.GOVERNANCE_DIRS` contains `docs/reference/kilo`, and
`TASK_SUBAGENT_SELECTION.md` is present in project copies (verified `/opt/youtube`, `/opt/transdoc`).
The generator under review therefore decides what `pick_models` routes to in **45 repos**, not just
the hub. Add a NEW mechanism and operator-named work, and three of § 1a's heavy triggers are met.

⚠️ Shared tree: `libs/subagents/*`, `PORTS.md` and others are dirty with SIBLING work and are NOT in
scope. The `Surface:` md5 above hashes the whole `git diff HEAD`, which necessarily includes their
uncommitted files — the reviewed scope is the three paths named above and nothing else.

## Rubric

Generated fresh by `python scripts/review_rubric.py --changed <the three paths>`; full output in the
run's scratchpad. The FLOOR (`core/35-security-auth`, `core/25-data-postgres`, `core/30-ops`, the
twelve 12-Factor axes) is injected but largely orthogonal to a markdown generator; the classes that
bite here are the four standing recurrence classes, carried into the checklist below.

## Coverage Checklist

| # | Class | Source | Status |
|---|---|---|---|
| C1 | fail-open vs fail-closed on the backstop (every path that can emit zero sections for a kind) | standing | UNCHECKED |
| C2 | the 9-column parse contract — `cells[1]` model, `cells[-1]` n | standing (boundary/sentinel) | UNCHECKED |
| C3 | a FIFTH injection path past the four allowlist filter points | standing (boundary) | UNCHECKED |
| C4 | determinism of the emitted doc + the empty-allowlist off switch | standing | UNCHECKED |
| C5 | behavior-without-a-test; tests that survive a material mutation | standing | UNCHECKED |
| C6 | fleet blast radius — 1–2 models per kind across 45 repos vs `62-using-subagents.md` fan-out diversity | FLOOR (hub lens) | UNCHECKED |
| C7 | staleness interaction — does the allowlist evaporate when the synced doc ages out? | standing (fail-open) | UNCHECKED |
| C8 | the daily revert by ai-model-catalog's forked ranker — guard vs trust | standing (cost/limit + ops) | UNCHECKED |

## Findings — Pass 1

### F1 — CONFIRMED. The doc's own `## ✅` header asserts something the doc contradicts

`TASK_SUBAGENT_SELECTION.md:6` reads *"## ✅ Selected subagents — the gate shortlists (`pick_models`
picks from these)"*, and the `### Reviewers — 8 selected` table under it lists `qwen/qwen3-max` and
`google/gemini-3-flash-preview` — both on `OPERATOR_DENY["review"]` — plus four `claude-code/*`
entries that are spawn-native and never pool-routed. Executed: `select._synced_ranking()["review"]`
returns `['deepseek/deepseek-v4-flash', 'deepseek/deepseek-v3.2-exp']`. So the doc tells a reader
eight reviewers are routable while routing offers two.

Pre-existing (the denies already created the gap) but **this change widens it 4→2 and ships it to 45
repos**, and the reader misled is as likely to be an agent planning a dispatch as a human. Failure
input: an agent reads the ✅ section to choose a reviewer, names `qwen/qwen3-max`, and gets a model
routing refuses. Class: the doc is a governance artifact and a false assertion in it is a defect.

### F2 — CONFIRMED. The early stub return bypasses the allowlist entirely (fail-open)

`rank_task_subagents.py:1715-1724` returns the "No aggregated runs yet" stub BEFORE any section is
emitted — and therefore before the D-159 backstop. Its own comment says *"Routing correctly still
falls back to `_TABLE` (no rank-led sections emitted)"*. Under D-159 that "correctly" is false: the
vendored `_TABLE` is exactly the unrestricted list (minimax, z-ai, qwen, google, openai) the operator
excluded. Failure input: the flywheel DB is empty or unreachable at 06:00 → `kept` empty, neither
benchmark ran → stub emitted → **every task kind routes to non-allowed models**, silently, on the
next sync to 45 repos. Same class as the backstop itself, one layer earlier; low likelihood on the
hub (benchmarks have run) but it is a policy surface and the failure is silent.

## Refutations — Pass 1 (orchestrator, method: execution)

- **C2 REFUTED (executed).** The real parser reads the backstop rows correctly:
  `select._synced_ranking()` returns all six kinds, with `plan` and `spec` each yielding
  `['deepseek/deepseek-v4-flash', 'deepseek/deepseek-v3.2-exp']` from the emitted `[allowlist]` rows.
  The 9-column shape and the `n=0` last cell survive `cells[0].isdecimal()` and `cells[-1]`.
- **C3 REFUTED (two independent proofs).** No fifth injection path. (i) `select.py:325-332` — ANY
  `###` header whose name is not a `TaskKind` sets `current = None`, so `### Reviewers — 8 selected`
  and `### Coders — 6 selected` cannot inject rows. (ii) The display tables that follow the last
  routing section are `##`-level, which does NOT reset `current` — but every one of their rows leads
  with a backticked model name, failing `cells[0].isdecimal()`. Verified: 6 `### <kind>` headers in
  the doc, all routing; zero decimal-leading rows after `### spec`. ⚠️ Note the second protection is
  incidental (a column-order accident, not a design) — it is now guarded by
  `test_every_routing_section_in_the_live_doc_contains_only_allowed_models`, which parses with the
  real parser and would go red if a display table ever gained a rank column.
- **C4 REFUTED (executed).** Two full renders under different `PYTHONHASHSEED` differ only in live
  `n` counts (`review n_total` 10733 → 10739, per-model 1355→1357 / 1503→1505) — moved by this
  review's own pool finders recording to the flywheel mid-run. Model set and ORDER identical, which
  is what `OPERATOR_ALLOW_ORDER` being a tuple buys.

### F3 — CONFIRMED, CRITICAL. The daily revert is the HUB's OWN pipeline, and D-159 named the wrong cause

Raised by the native finder, reproduced independently by the orchestrator before acting.

`scripts/kilo-benchmarks/daily_refresh.sh` ran `rank_task_subagents` at `:177` and then, **110 lines
later in the same script**, `deliver_to_fabrik.py --apply --target-root "$FABRIK_ROOT"` at `:287`.
That delivery is a blanket copy of `/opt/ai-model-catalog/engine/out/` onto the hub root
(`deliver_to_fabrik.py:138` iterates `out_root.rglob("*")`; `_NEVER_DELIVER` at `:59` excludes only
`docs/CAPABILITIES.md`, `capabilities.json`, `llms.txt`). So the hub regenerated its own routing doc
and copied a fork's older copy over it roughly an hour later, every morning, then auto-committed it.

**Proof, executed:** the engine's `out/` copy and HEAD's committed doc are BYTE-IDENTICAL
(md5 `0330e2d09dcc9e0f4d69d53895542f0b`), and the committed doc lacks the `grounding` column the hub
ranker has emitted since `ec05a490` (2026-08-29) — so it cannot have come from the hub's ranker.
~8 days of hub output discarded, and the operator deny that landed 2026-09-05 was **never once live**
in the file routing reads. `guard_selection_freshness.py:150-151` cannot see it: it compares DATES,
and both copies carry the same stamp.

⚠️ **My D-159 row asserted the fork's cron writes the hub path. That is false** — the fork's
`_output_root()` (`engine/rank_task_subagents.py:158`) resolves to its own `out/`, and no
`OUTPUT_ROOT` is exported on its ranker step. Superseded by **D-166**; correction sent to
ai-model-catalog as `01M1VRKN8AXPBE181TJPJ7BP4D`. FIXED hub-side by moving the ranker step after
delivery — no cross-repo dependency.

### F4 — CONFIRMED, HIGH. The backstop was all-or-nothing, which broke the `exclude=` reliability lever

`emitted_task_types.add(task_type)` fires as soon as ONE row survives, so the backstop (which
triggers on a MISSING section) could never top up a kind that kept one of the two allowlisted models.
Measured pre-fix: `code`, `docs` and `research` each drew ONE model, and `pick_models(kind,
exclude=(rank1,))` returned `[]` — which `agent.py` turns into
`ValueError: fanout: pick_models(...) returned no models`. `select.py:559` documents `exclude` as
"the reliability lever" for a model that failed this session, so a one-model kind converts a routine
provider hiccup into a raised batch. FIXED with an in-section top-up; verified after: every kind
draws 2 and survives excluding rank 1.

### F5 — CONFIRMED, HIGH (REPORTED, not fixed). Staleness is a whole-document fail-open

`select.py:474` calls `load_task_ranking(path, max_age_days=14)`; `:300-309` returns `{}` for the
ENTIRE doc past that age, and `pick_models` then falls to `_TABLE` per kind. Executed against a copy
stamped `2026-08-01`: all six kinds revert, and `deepseek/deepseek-v4-pro` — `OPERATOR_DENY_ALWAYS`,
the model the hub refuses to route ever — returns at rank 4 in four of them. On-box every repo
resolves the hub doc directly, so this bites OFF-box: a deployed container uses its synced copy,
whose stamp freezes at the last deploy. 15 days without a redeploy and that service routes
unrestricted, silently (`load_task_ranking` never raises). Not fixable in the generator — the
behaviour is in the vendored parser. Routed to the operator and to fabrik-lib's in-flight spec.

### F6 — CONFIRMED (REPORTED, decision input). `code` now routes solely to a model measured at 0.00 success

⚠️ **CORRECTED in the closing pass — my first figures used the wrong baseline.** I took the "before"
costs from HEAD's committed doc, which is the FORK's output on a different aggregation window
(`code n_total` 187 vs 130, `review` 13825 vs 10765), so the delta conflated the allowlist with a
different generator AND a different data window. Re-derived against the honest baseline — the same
live `_query_rows()` data through the hub ranker with `OPERATOR_ALLOW = frozenset()`, which is the
documented off switch:

| kind | rank 1 without the allowlist | rank 1 with it | per-run cost |
|---|---|---|---|
| `code` | `openai/gpt-5.6-luna` — success **0.68**, $0.0212 | `deepseek/deepseek-v3.2-exp` — success **0.00**, n=10, avg_quality 0.62/5 | $0.0212 → $0.0962 (**4.5×**, not the 4.8× I first wrote) |
| `research` | `deepseek/deepseek-v3.2` — $0.0077 | `deepseek/deepseek-v4-flash` — $0.0160 | **2.08×** — reproduces exactly |
| `docs` | `deepseek/deepseek-v4-flash` — $0.0078 | same | **no change** (I implied one; there is none) |
| `plan` | *no section at all* — its only row was `deepseek-v4-pro`, `OPERATOR_DENY_ALWAYS` | allowlist | `plan` was ALREADY falling through to `_TABLE` before D-159 |

The correct baseline **strengthens** the finding rather than softening it: the model the allowlist
displaced on `code` measures success 0.68 against the retained model's 0.00, on the same window. Two
of three kinds also get more expensive per run, which inverts the "two CHEAP deepseek agents" intent.
This is a consequence of the operator's roster, not a defect in its implementation — surfaced for
their decision, not fixed.

### F7 — CONFIRMED. `_allowed()` blessed `claude-code/*`, and the tests used it as the definition

The predicate returned True for `claude-code/*` on the reasoning that they are stripped upstream. The
strip exists only at `:1665` and `:1693` (the code/review benchmark supplements); the **fleet-rows
loop has no such strip**, so `_allowed` was the only gate there. Worse, the new tests use `_allowed`
as the definition of "routable", so a `claude-code/*` row would have been blessed by the guard.
FIXED: `_allowed` now returns False for them, making it the single source of truth.

### F8 — CONFIRMED. The no-data stub bypassed the allowlist entirely (see F2 above, fixed)

### F9 — CONFIRMED. `62-using-subagents.md:61` was falsified by this change

A BINDING synced rule described `fanout` as selecting "family-diverse" models. D-159 pins every kind
to one vendor family, and `.windsurf/rules` ships to the same 45 repos in the same sync — so the rule
and its falsification would have travelled together. FIXED in place (family diversity restated as
best-effort, bounded by what `pick_models` returns); filed to infra as `01M1VRMZ645SG89M3VM05K85VP`
because the pack is their beat.

### REFUTED in round 1, with proof

- **Fleet loop never marks a kind emitted** (R2 finder) — REFUTED: `emitted_task_types.add(task_type)`
  at `:1833`.
- **Both fallback blocks can emit a zero-row section** — REFUTED: `:1839` and `:1855` are guarded by
  `and coding_fallback_models` / `and review_benchmark`, so neither is entered with an empty list.
- **The `### plan (n_total=0, operator allowlist — …)` header will not parse** — REFUTED by
  execution: `select.py:329` matches `^###\s+([A-Za-z][\w-]*)`, which is satisfied regardless of the
  trailing text; `_synced_ranking()` returns the rows.
- **`[allowlist]` in the `shrunk_q` cell will raise on a float cast** — REFUTED: the parser reads
  `cells[1]` and `cells[-1]` only.
- **`min_n` drops the `n=0` allowlist rows** — REFUTED as live, recorded as latent: `pick_models` has
  no `min_n` parameter at all, and the only caller passing it is a test.

### F10 — OUT OF SURFACE, pre-existing, reported not fixed

`scripts/kilo-benchmarks/tests/test_golden_parity.py` is RED at HEAD: 10 failures, e.g.
`assert cg.verify() == 0, "the oracle reports drift on an unmodified tree"`. Attributed cleanly —
running the suite with HEAD's `TASK_SUBAGENT_SELECTION.md` and again with mine gives **10 failures
both ways and an IDENTICAL failure set** (`comm -23` of the two sorted lists is empty), so none of it
is attributable to this change.

The cause is in its premise: the suite requires an unmodified tree, and this hub runs three
concurrent sessions plus a daily pipeline, so the tree is essentially never clean. It is invisible
day to day because the hub deliberately runs no pytest leg in the gate. On my beat
(`scripts/kilo-benchmarks/`), but fixing 10 failures in a suite whose surface a sibling is actively
holding (`stash@{0}: sibling-agent-daily-refresh-outputs-parked-by-opus`) is outside this review's
scope and would collide. Reported to the operator; not fixed here.

### F11 — CONFIRMED, mine, found and fixed in the closing window

`check_routing_policy.py` resolved its hub root as "the relative root, ELSE `/opt/fabrik`". The
fallback was added to survive a symlinked `scripts/` dir — a hazard raised in pass 2 and, on
reflection, hypothetical. Its real effect is not hypothetical: this file ships to ~45 project repos,
and in a project copy on this box `/opt/youtube/scripts/enforcement/…` resolves relatively to
`/opt/youtube` (no ranker → correct skip) and then the fallback found `/opt/fabrik`'s ranker and made
a **project's gate report on hub state**. Verified both branches by execution before and after.
FIXED: the fallback is gone; belonging is the question, not availability. A hub `git worktree` still
resolves to itself because it carries the full tree.

## Findings — Pass 3 (the closing re-derivation pass)

Nine raised by an independent native finder plus a 3-unit pool sweep; **five of the nine were defects
in Pass 1's own fixes**, which is the case for running the pass at all.

- **R1 — CONFIRMED, HIGH, FIXED.** My `emitted_task_types.add("code"/"review")` re-created F4 on the
  mode-(b) fallback paths: those blocks mark a kind emitted, the backstop then skips it, and a
  fallback section built from ONE allowlisted model shipped a one-model kind → `exclude` → `[]` →
  `ValueError`. Latent when found (both fallback lists were empty or complete). FIXED by running the
  top-up in **all three** emitters. Grader added and proven red-on-revert.
- **R2 — CONFIRMED, FIXED (twice).** The top-up's `already` set and `start` rank came from the fleet
  rows alone, so a model the benchmark supplement had already appended was re-emitted at a duplicate
  rank. My first fix (`max(len(scored), code_last_rank, review_last_rank) + 1`) **did not work** —
  executed, the review section still came out `1, 2, 2` with `v4-flash` twice — because the
  supplements update neither tracker. Real fix: the supplements now RECORD what they emit. Verified
  across review/code/docs: no duplicate rank or model.
- **R3 — CONFIRMED, FIXED.** My `## ✅` header rename broke the nightly contract oracle
  (`tests/golden/structure.json` freezes the old string; `capture_golden.py --verify` reported
  `skeleton LOST`). Re-snapshotted **that one artifact's skeleton only** — a blanket `--snapshot`
  would have silently blessed 12 pre-existing drift rows that are not mine. Verified: my row gone,
  the other 12 intact.
- **R4 — CONFIRMED, ACCEPTED + DOCUMENTED.** `[allowlist]` cells fail the float cast, so
  `select.py:400-404` skips the ungrounded-quality penalty for the whole kind. Real behavioural
  change, latent while every live grounding cell reads `✓`. Not fixed here: the row cannot carry a
  measurement it does not have, and inventing one would be worse.
- **R5 — CONFIRMED, FIXED.** The F4 fix shipped with **no grader** — `exclude` appeared nowhere in
  the test file. Fix Directive #4 violation, mine. Added
  `test_excluding_the_top_model_still_leaves_a_worker` (all six kinds) plus graders for R1 and R2.
- **R6 — CONFIRMED, FIXED.** After moving the ranker, its failure path still said "non-fatal — the
  previous doc stands". That became FALSE: post-move the previous doc is the unrestricted one
  delivery just copied in. It now fires `pipeline_alert.sh` like every other policy-critical step.
- **Pool finder — CONFIRMED, FIXED.** `select._synced_ranking()` sat OUTSIDE the try/except, so an
  `AttributeError` after a re-vendor (it is a PRIVATE function of a vendored module) would exit
  non-zero — and `warn_only` reads a non-zero exit as a broken contract that FAILS the gate. An
  advisory check would have become blocking across 45 repos. Now guarded, returning 0 with an
  explicit "UNVERIFIED this run" line.
- **Pool finder — CONFIRMED, FIXED.** Dropping the `/opt/fabrik` fallback left a silent false-SKIP if
  `__file__` resolves outside the tree. Second candidate is now `git rev-parse --show-toplevel` —
  "which checkout am I in", which is the right question and keeps project copies skipping.
- **R7/R8/R9 — CONFIRMED, LOW, recorded not fixed.** A docstring overstates the DRY guarantee; the
  "byte-identical when the allowlist is empty" claim is false (the `claude-code/*` strip in the fleet
  loop is unconditional — 0 of 76 live rows are affected); and from a hub worktree the check asserts
  about the main checkout's doc, which is what its docstring says it does.

### Re-derivation of the artifact's own claims (method: re-derivation)

An independent finder re-derived all five load-bearing claims from primary sources: **(a) VERIFIED**
(md5 match), **(b) VERIFIED** (`grep -c grounding` on HEAD = 0; `ec05a490` dated 2026-08-29),
**(c) VERIFIED** (`deliver_to_fabrik.py:138` rglob, `:59` three exclusions), **(d) VERIFIED**
(`max_age_days=14` at `:474`; a stale copy reverts all six kinds with `v4-pro` at rank 4 in four),
**(e) PARTLY WRONG** — corrected in F6 above.

## Pass Ledger

| Pass | method | found | new | fixed | finders |
|---|---|---|---|---|---|
| Pass 1 | method: citation | found: 9 | new: 9 | fixed: 7 | pool `fanout("review", 5 units, read_only)` — dispatched 5, **returned 5** (agent-000-54aad8, agent-001-31c527, agent-002-c4ce42, agent-003-c11853, agent-004-f17c0b; $0.0203); native Opus on C6/C7/C8 — dispatched 1, **returned 1**; orchestrator executable verification closed C2/C3/C4 |
| Pass 2 | method: gate | found: 6 | new: 6 | fixed: 0 | pool `fanout("review", 3 units, read_only)` — dispatched 3, **returned 3** (agent-000-6edc1e, agent-001-e79a3e, agent-002-6726b2; $0.0086). All 6 candidates REFUTED by execution — see § Refutations (pass 2) |

### Refutations — Pass 2 (method: execution, every one disproved by running the code)

- **"`set(by_task)` yields row TUPLES, so `sorted()` raises TypeError on every normal run"** — REFUTED.
  `by_task` is a dict keyed by task_type (`task_rows = by_task[task_type]`), so `set(by_task)` is the
  key set. Executed: `render([("code", "deepseek/deepseek-v4-flash", 40, 0.01, 3.0, 0.9)])` returns 44
  lines, no exception.
- **"`state='error'` now emits the same stub as a healthy empty pool, so an aggregation failure
  publishes a policy doc silently"** — REFUTED at `rank_task_subagents.py:1668`: the `state == "error"`
  branch returns the distinct ⚠️ AGGREGATION FAILED text and returns BEFORE the allowlist stub is
  reached. `:2033` additionally refuses to overwrite a good existing doc in that state.
- **"the stub loses the no-data signal"** — REFUTED: the emitted stub still opens with "No aggregated
  runs yet", and now states what routing does instead of leaving the reader to infer it.
- **"`_hub_root()` false-SKIPs when `scripts/` is a symlink"** — REFUTED: `_hub_root()` iterates TWO
  candidates and the second is `DEFAULT_HUB = /opt/fabrik`, which is exactly that guard.
- **"the grounding column shows `—` for allowlist rows, implying an unmeasured model"** — REFUTED as a
  defect: `—` is the correct rendering for a model with no canary measurement for that kind, and the
  row's `[allowlist]` marker already says the row is policy, not measurement.
- **"the check can false-pass if the doc is replaced after it validates"** — REFUTED as out of scope:
  a gate asserts state AT GATE TIME; no gate can close a TOCTOU against a later writer. ⚠️ Recorded as
  a stated LIMITATION, not a fix: the nightly auto-commit path does not run `final_gate`, so a
  regression there is caught on the next human commit, not at the moment it lands. The ordering fix
  (F3) addresses the cause; this check is the net beneath it.

## Gate — RE-MEASURED in the closing pass (not inherited)

```
python scripts/final_gate.py --json
status: success | failures: 0 | warnings: 5 | skipped_checks: ['pytest']
Routing Policy (operator deny + allowlist):
  check_routing_policy: OK — 6 of 6 task kinds have a routing section, 12 routable
  model entries, all allowed and none denied
```

⚠️ `skipped_checks: ['pytest']` is the hub's deliberate design (no `.fabrik/run-pytest`), so the gate
asserts nothing about the suite. Run separately this turn: **43 passed** across
`test_operator_routing_deny.py` (21), `test_claude_p_cost.py`, `test_price_ratios_current.py`, and
**182 passed / 10 pre-existing failures** across every suite that imports the ranker — the 10 being
F10, proven identical with and without this change. The 5 warnings are pre-existing advisories
(review-coverage backlog, vendored drift, untracked sibling files), none on this surface.

Ordering verified for the `daily_refresh.sh` change: `deliver_to_fabrik` (:287) → `rank_task_subagents`
(:309) → `sync_enforcement_to_projects` (:480), so the hub's own doc is what distributes. No step
between the old (:177) and new (:309) positions reads the selection doc.
