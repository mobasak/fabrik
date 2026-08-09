# How Agents Pick Commands, Fix vs Route, and When They Stop for You

Operator reference for three questions that decide how autonomous a session is:
how an agent *selects* the right command from bare prose, how a certification
gauntlet decides *fix-on-the-fly vs route to a pipeline command*, and exactly
*when an agent stops to ask you* vs resolves things itself. Grounded in the
2026-08-07 autotrigger wave (`docs/reference/receipts-2026-08-07-autotrigger.md`).

---

## 1. Command selection without you naming it (the four-layer stack)

You type bare prose ("bu projeyi emekliye ayır", "certify this end to end") and
the right skill fires. Four layers, cheapest first — each catches what the one
above missed:

| Layer | Mechanism | What it catches |
|---|---|---|
| 1. Router hook | `.claude/hooks/skill_router.py` (`UserPromptSubmit`, fleet-synced): intent-anchored EN+TR regexes → resolved against the LIVE `~/.claude/skills/fabrik-*` roster → injects *"This request matches /fabrik-X (Stage: N) — invoke the skill, or state in one line why it does not apply."* Deterministic, fires before the model reads your prompt. A skill that is the target of an EXISTING stem auto-enrolls the moment it lands (roster is read at fire time); a genuinely new intent still needs a stem+keyword row in the router. | The common phrasings (EN broadly; a subset of the advertised TR forms — layers 2-3 cover the rest model-side) |
| 2. Orient step-0 | CLAUDE.md § Orient: at run start the agent classifies your request against the frozen stage table (`1-design … 6-release / gate / utility`) and invokes the matching skill — "a task that matches a stage and is executed without its skill is a defect". | Paraphrases the regexes miss — model-side semantic matching |
| 3. TRIGGER descriptions | All 24 skill descriptions carry concrete TRIGGER phrasings (EN+TR) + exactly one `Stage:` + SKIP boundaries naming the confusable sibling (review vs repo-review vs rules-review vs workflow-review vs design-review; ui-design vs ui-design-review; user-test vs service-test vs deploy-verify). | Disambiguation when several commands are plausible |
| 4. Artifact gates | `scripts/enforcement/check_stage_artifacts.py` (Tier-2): a plan flipping CONVERGED on a DRAFT spec, or a contract claiming FROZEN without its mandated header + freeze rule, reds the gate. | The backstop — when selection failed anyway, the OUTPUT betrays the skipped stage |

Selection details worth knowing:

- **Certification fork is computed, not guessed:** the `test` intent routes by
  `project.yaml::type` — headless types → `/fabrik-service-test`, UI-bearing →
  `/fabrik-user-test`; `wordpress` (deploy-only) and directories with NO
  `project.yaml` (the hub) get no test routing at all.
- **The router never blocks or rewrites** — it injects a nudge with an escape
  ("or state in one line why it does not apply"). Precision was tuned so
  ordinary dev prose ("run the tests and fix the failures", "bu satırı kaldır")
  stays silent.
- **The Haiku fallback classifier** (for prompts the regexes miss) is built and
  tested but **opt-in** (`FABRIK_ROUTER_HAIKU=1`): measured isolated cold-starts
  were 8.6–10.7s — a synchronous tax on every unmatched prompt costs more than
  the missed matches it recovers. Layers 2–3 cover the gap model-side.
- **`/design-review` is deliberately un-routed** (non-`fabrik-` prefixed, outside
  the roster glob): it is a pipeline-invoked GUI sub-gate, never fired from prose.

## 2. Every command names its successor — and the hardening loops auto-chain

The `NEXT` map in `commands/assemble_commands.py` renders a "NEXT: …" clause into
every skill description and a "**Next in the pipeline:** …" line into every skill
wrapper body — that half is assembler-enforced. Five command bodies additionally
hand-carry a "Next command:" terminal line in their `_sources` (catchup,
decommission, deploy-verify, release, upstream). Terminal entries state their
terminal disposition explicitly in the NEXT map (e.g. "none — terminal", "no
linear successor — resume the caller").

**Which hand-offs are FORCED (same run, no return of control) vs which STOP for you:**

```
/fabrik-spec ──AUTO──▶ /fabrik-spec-review ──STOP: design approval──▶ (data-contract / ui-design / plan-after-chat)
/fabrik-plan-after-chat ──AUTO──▶ /fabrik-plan-review ──▶ ready; YOU dispatch /fabrik-execute-plan
/fabrik-execute-plan ──FORCED per phase (phase mode) / per ticket pre-merge (dispatcher)──▶ /fabrik-review
                     ──then──▶ whole-plan review (§Finish) / D7 validation ──▶ certification gauntlet
/fabrik-user-test | /fabrik-service-test ──▶ /fabrik-release ──STOP: Gate 2──▶ YOU run `fabrik apply` ──▶ /fabrik-deploy-verify (terminal)
```

- `/fabrik-spec`'s source makes it explicit: *"MANDATORY final step — immediately
  invoke `/fabrik-spec-review <spec path>`"* — a spec is written `DRAFT` and only
  the review's md5-verified no-op round flips it `CONVERGED`. Same for
  plan-after-chat → plan-review.
- The asymmetry is deliberate: **hardening loops auto-chain; decision points
  stop.** Spec-review converges *then* halts for your sign-off (the design gate);
  release halts at Gate 2 (the deploy gate). An agent that auto-chained past
  either would be self-approving your decisions.
- Reviews inside execution are never end-loaded: phase mode runs the full
  `/fabrik-review` at EVERY phase boundary (next phase starts only after its
  coverage-adjudicated exit) plus one over the whole-plan cumulative diff at
  §Finish; dispatcher mode reviews EVERY ticket to a clean round as the merge
  precondition (a Board row cannot reach ✅ un-reviewed — the flip lives in the
  same commit as the reviewed code), plus D7's whole-plan validation to
  `found: 0, fixed: 0` at the end. Cascade control: fast inner loop per unit,
  slower outer loop over the integrated whole.

## 3. Fix on the fly vs route to a command (the gauntlets' disposition rule)

`/fabrik-user-test` and `/fabrik-service-test` decide by **what the finding
proves is wrong**, never by how easy the fix looks (source:
`commands/_sources/fabrik-user-test.md` Phases 4–7):

| Evidence | Disposition |
|---|---|
| Presentation/surface-layer defect, or doc drift (stale FEATURES row) | **FIXED in-run** — failing spec first → fix → green → affected flows re-run |
| The RIG is wrong (the test's own assertion/selector/fixture — wrong casing, missing alias, a repro asserting a contract that never existed) | **RIG-FIXED in-run** — repair or delete the defective test citing the contract line; never "fix" correct code into agreeing with a broken test |
| Contract right, code wrong (backend/schema/logic) | **ROUTED → `/fabrik-review`** on the owning module, in a FRESH context, seeded with a **committed RED repro + wire/state evidence**; the review turns the repro green — or proves the repro itself rig-defective and fixes the repro instead (its REPRO-DEFECTIVE exit) |
| App right, doc stale (frozen contract lags reality) | **ROUTED → `/fabrik-data-contract` / `/fabrik-ui-design`** re-freeze |
| Design wrong or MISSING (journey blocked by a nonexistent screen/field/endpoint) | **DESIGN-GAP BRIEF → you** — persisted with the exact `/fabrik-spec` invocation; the row stops at "operator decision" |

Guards that make it mechanical: the **rig-refute floor** (a red test is a
symptom, not proof — one schema/alias/selector lookup + the actual body or
system state before any row survives as a service/app finding); the
**path-gate** (a "small fix" whose diff touches anything outside the owned
layer is AUTO-reclassified to the code-wrong route — the diff decides); **wire/
state evidence** on every code-wrong route (gate-enforced: an OPEN row routed
to `/fabrik-review` without an `evidence:` slot fails
`check_review_coverage.py`); a **ledger-freshness pass** before routing
(re-run the row's repro — its current color decides, not the ledger's); routed
fixes execute **in the same run** in fresh contexts (a handoff is deferred
sequencing, not exported work); and **`/fabrik-release` is blocked while any
HANDED-OFF row is open**, so routed findings can't rot.

## 4. When the agent stops for you vs resolves it itself

Autonomous by default; the stops are designed, named, and arrive with the
evidence pre-packaged:

**Never asks — resolves itself:** anything answerable from self-service sources
(rule packs, `agents-fabrik.md`, `docs/`, `AFCL.md`, grep); findings inside
review/certification loops (fix → prove → loop to convergence); everything
inside a pre-approved plan's scope (present-before-execute is suspended there —
only 3 BLOCKED cases halt: 3× same-test failure, missing infra, spec
contradiction, each reported in the `BLOCKED:` format, not asked).

**Always stops — the human gates:**

| Gate | Where |
|---|---|
| Design sign-off | `/fabrik-spec-review` ends at approval, never auto-chains |
| Product questions | gauntlet design-gap briefs ("never decide a product question inside a test run") |
| Deploy | `/fabrik-release` Gate 2 — you run `fabrik apply`; agents never do |
| Retirement / teardown | `/fabrik-decommission` Phase 1.5 confirmation before ANY move; `fabrik destroy` is yours |
| Publish | `git push` — always operator-authorized |
| Stuck finding | after 3 failed fix attempts → BLOCKED-escalated to you; the loop continues on everything else |

Control-loop framing: inner loops run closed and unattended; you are the outer
controller — the system breaks the loop only at setpoint-changing (design,
product) and irreversible-actuation (deploy, teardown, publish) points.

## 5. The awareness + anti-stall mesh (what every session starts with and may not end without)

**Session start — the ORIENT block.** A fleet-synced SessionStart hook
(`.claude/hooks/session_orient.py`) opens every project session with a binding
orientation: the synced `CLAUDE.md` is loaded and binding (never edited
locally — projects receive it from the hub's `templates/governance/CLAUDE.md`;
the hub's own `CLAUDE.md` is a separate platform-repo contract), the agent's
`MEMORY.md` state (entry count, or a save-per-contract reminder), the
session-recall tools (`search_chats` · `recent_chats` · `get_chat`) with their
mandatory-use cases, and the enforcement mesh itself. Fail-open — a broken
orientation never blocks a session. Running sessions are unaffected;
the block binds at each NEW session start.

**Session end — three Stop-hook causes.** A session may not end while (a) the
gate is red on files IT authored (path-token attribution — a sibling's dirt on
the shared tree never blocks you), (b) its own work sits uncommitted, or
(c) the final message is a checkpoint-stall: a first-person promise ("I'll run
it and report"), a permission question the session's own active plan already
answers, or a **passive obligation** ("Pass 7 is owed", "I still owe the
confirming round") with no dispatch in the same turn. Negations ("no further
pass is owed"), causal "due to", credit "owed to", quotations, and named human
gates are exempt; three blocked attempts warn through.

**Every task-completing response** ends with the 6-line FINAL OUTPUT block —
gate freshness, docs, changelog, lessons, plus `DONE:` (what actually landed)
and `NEXT:` (the successor named precisely: exact command + args, the exact
operator decision, or `none — terminal`; own-session work named in NEXT is
dispatched, not narrated).
