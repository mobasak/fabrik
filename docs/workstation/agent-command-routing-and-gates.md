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
| 1. Router hook | `.claude/hooks/skill_router.py` (`UserPromptSubmit`, fleet-synced): intent-anchored EN+TR regexes → resolved against the LIVE `~/.claude/skills/fabrik-*` roster → injects *"This request matches /fabrik-X (Stage: N) — invoke the skill, or state in one line why it does not apply."* Deterministic, fires before the model reads your prompt. A skill added tomorrow auto-enrolls (roster is read at fire time). | The common phrasings, both languages |
| 2. Orient step-0 | CLAUDE.md § Orient: at run start the agent classifies your request against the frozen stage table (`1-design … 6-release / gate / utility`) and invokes the matching skill — "a task that matches a stage and is executed without its skill is a defect". | Paraphrases the regexes miss — model-side semantic matching |
| 3. TRIGGER descriptions | All 24 skill descriptions carry concrete TRIGGER phrasings (EN+TR) + exactly one `Stage:` + SKIP boundaries naming the confusable sibling (review vs repo-review vs rules-review vs workflow-review vs design-review; ui-design vs ui-design-review; user-test vs service-test vs deploy-verify). | Disambiguation when several commands are plausible |
| 4. Artifact gates | `scripts/enforcement/check_stage_artifacts.py` (Tier-2): a plan flipping CONVERGED on a DRAFT spec, or a contract claiming FROZEN without its mandated header + freeze rule, reds the gate. | The backstop — when selection failed anyway, the OUTPUT betrays the skipped stage |

Selection details worth knowing:

- **Certification fork is computed, not guessed:** the `test` intent routes by
  `project.yaml::type` — headless types → `/fabrik-service-test`, UI-bearing →
  `/fabrik-user-test`; a directory with NO `project.yaml` (the hub) gets no test
  routing at all.
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

## 2. Every command names its successor

The `NEXT` map in `commands/assemble_commands.py` renders a "Next command: …"
terminal line into every command body and a "NEXT: …" clause into every skill
description — chaining is assembler-enforced, not remembered. Terminal commands
say "NEXT: none" explicitly. Current chain highlights: `/fabrik-release` → Gate 2
(you run `fabrik apply`) → `/fabrik-deploy-verify` (terminal); `/fabrik-catchup`
→ the routed converge command per queue item; `/fabrik-review` → back to the
phase that invoked it (a gate, not a stage).

## 3. Fix on the fly vs route to a command (the gauntlets' disposition rule)

`/fabrik-user-test` and `/fabrik-service-test` decide by **what the finding
proves is wrong**, never by how easy the fix looks (source:
`commands/_sources/fabrik-user-test.md` Phases 4–7):

| Evidence | Disposition |
|---|---|
| Presentation/surface-layer defect, or doc drift (stale FEATURES row) | **FIXED in-run** — failing spec first → fix → green → affected flows re-run |
| Contract right, code wrong (backend/schema/logic) | **ROUTED → `/fabrik-review`** on the owning module, in a FRESH context, seeded with a **committed RED repro** the review may not exit without turning green |
| App right, doc stale (frozen contract lags reality) | **ROUTED → `/fabrik-data-contract` / `/fabrik-ui-design`** re-freeze |
| Design wrong or MISSING (journey blocked by a nonexistent screen/field/endpoint) | **DESIGN-GAP BRIEF → you** — persisted with the exact `/fabrik-spec` invocation; the row stops at "operator decision" |

Guards that make it mechanical: the **path-gate** (a "small fix" whose diff
touches anything outside the owned layer is AUTO-reclassified to the code-wrong
route — the diff decides); routed fixes execute **in the same run** in fresh
contexts (a handoff is deferred sequencing, not exported work); and
**`/fabrik-release` is blocked while any HANDED-OFF row is open**, so routed
findings can't rot.

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
