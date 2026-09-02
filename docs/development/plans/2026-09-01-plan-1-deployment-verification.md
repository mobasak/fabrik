# Plan 1 — Deployment Verification Contract (hub build)

Status: **DRAFT** — the spec is **CONVERGED and APPROVED** (J5 quiet at md5 `cdb48812`; approval D-077). On the
same approval the operator directed *"study the structure, enforcement, loop, convergence and all aspects of
our existing commands to use same approach and update the plan"* — so this revision RE-AUTHORS Phases A–C to
the command-corpus conventions measured in § Corpus conformance contract, and it owes `/fabrik-plan-review`
before execution: a plan cannot self-grade a rewrite of its own phases.
Date: 2026-09-01 · amended 2026-09-02 (fabrik-lib binding · row-shape split · corpus conformance)
Spec: `docs/superpowers/specs/2026-09-01-deployment-verification-contract-design.md` (status per its header — read it, do not trust this line)
Scope: **`/opt/fabrik` only** — 11 file groups, two of them FLEET-SYNCED. Execution order A → C → B → D (see Phase B). Routed feature-scale (spec defect 15: the epic verdict was wrong).

## Why this plan exists

I certified tryton-crm `DEPLOY CONFIRMED LIVE` with every check green while production held **0 of its
760 companies**. Liveness checks cannot fail on a missing product, because nothing declared what the
product should contain.

## File Scope (exhaustive — nothing outside this list)

| # | path | change |
|---|---|---|
| 1 | `commands/_sources/fabrik-deploy-checklist.md` | **NEW** — the project-side authoring command, built to the anatomy in § Corpus conformance |
| 2 | `commands/_sources/fabrik-deploy-verify.md` | rewrite (216 lines today) — keeps its verify-command anatomy, gains Layer 1 + derived Layer 3 + blocking contract-driven parity |
| 3 | `commands/assemble_commands.py` | **registration, not logic**: `NEXT` entries (`:49`) for the new command + retargets for `fabrik-features`/`fabrik-deploy-verify`; a `PARAMS` block (`:394`) carrying ALL 16 tokens the included fragments declare — **`render()` resolves `{{include:…}}` from `PARAMS` alone and REFUSES the render on any unresolved token (proven by execution, § Evidence); `EXTRACT` (`:331`) is the retired July-migration table (`extract()` globs `~/.claude/commands.bak-20260721-0615`) and is NOT edited** — the runner's `PARAMS` examples (`:556`) gain parity-shaped examples |
| 4 | `commands/_sources/fabrik-release.md` | one precondition paragraph on the VPS path (`:76-86`): a parity contract that is not `FROZEN` is `BLOCKED: parity contract DRAFT → /fabrik-deploy-checklist` — the mirror of its existing certification-handoff precondition (`:20-35`) |
| 5 | `CLAUDE.md:61,333` + `templates/governance/CLAUDE.md:53,339` | the § Orient **stage table** row for `6-release` (`:61` / `:53`) AND the § Pipeline flow line (`:333` / `:339`) name the new command between `/fabrik-features` REFRESH and certification/release (evaluation-checklist items 56–57: both places, both files). ⚠️ **`templates/governance/CLAUDE.md` is FLEET-SYNCED** — the post-commit governance-sync distributes it to ~46 repos |
| 6 | `templates/scaffold/scripts/verify_prod_parity.py` (**NEW** template) + `src/fabrik/scaffold.py` (`SCRIPT_FILES` + the copy loop at `:1127`) + `templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md` / `OPERATIONS_TEMPLATE.md` (fleet-AI sections, D-065) | born-compliant seeding on the `scaffold.py:285` precedent |
| 7 | `tests/test_scaffold_deploy_contract.py` | **NEW** — Phase C guards (stub exits non-zero; docusaurus does not publish the doc templates' new sections) |
| 8 | `tests/test_check_command_corpus.py` (extend) | Phase A/B guards — the rendered commands carry the required sections; ⚠️ the earlier File Scope named `tests/test_command_corpus.py`, **which does not exist** (`ls tests/ \| grep -i corpus` → only `test_check_command_corpus.py`) |
| 9 | `tests/test_deploy_verify_verdict.py` | **NEW** — Phase A step 7: the EXECUTED verdict-algebra check (four row shapes + DOWN/mismatch co-occurrence), watched-fail-first |
| 10 | `docs/reference/deployment-verification.md` (**NEW**) + `docs/README.md` | the contract is a NEW SUBSYSTEM (two commands, a seeded artifact, a verdict algebra) — evaluation-checklist item 64 owes it its OWN reference doc (grep/`ls` first: none exists); describes the CURRENT architecture, links the spec |
| 11 | `capabilities.json` + `docs/CAPABILITIES.md` + `INDEX.md` | **REGENERATED / doc-sync**, never hand-edited: `scripts/generate_capability_index.py` enumerates `commands/_sources/*.md` (`:461`) so a new command changes both; `INDEX.md` rows for every new file (Doc Sync Matrix) |

**READ-ONLY inputs, not edited:** `src/fabrik/orchestrator/infrastructure.py` (`_REGISTRAR_ORDER`),
`docs/superpowers/specs/2026-09-01-deployment-verification-contract-design.md`, `commands/_fragments/*.md`
(the shared blocks are consumed by include, never edited for one command), `.claude/hooks/skill_router.py`
(auto-enrolls a new skill at fire time — `:104-108` *"a not-yet-built sibling command auto-enroll[s] instead
of needing an edit here"*; a routing stem is added ONLY if the trigger audit shows the command reaches nowhere,
because that file's own measured policy is that a loose pattern is worse than a gap).

⚠️ **FLEET-SYNCED SURFACE.** Every `commands/_sources/` edit distributes to 43 repos on commit, and File
Scope row 5 touches the synced governance template. **Merge-time render only** — never bare-render
`assemble_commands.py` from a worktree (it PRUNES installed commands absent from the current tree). `--check`
is always safe.

## OUT OF SCOPE — named, not silently dropped

- **fabrik-lib `health-probe` enhancement** — filed `01M1ESR5KJW5Z1EE2YE55MBTE8`; **they** spec and
  implement, and **they have: ACCEPTED + CONVERGED** (`5f5b2e6f`, their
  `docs/superpowers/specs/2026-09-02-health-probe-comparison-mode-design.md`). ⚠️ **The FALLBACK is
  RETIRED as the plan of record** (spec Amendment 2). This plan now binds to their settled interface —
  `compare(name, expected, actual, *, comparator=None)`, tri-state `match`, `cli(..., mismatch_exit=2,
  strict=False)` — and the hub-side runner implements **that same shape** locally until their build lands,
  so the eventual swap is a deletion, not a rewrite. **Still nothing blocks on their BUILD**: the binding
  is to an interface, not to an artifact.
- **Per-project onboarding (27 deployable repos)** — self-serve; each project's own agent runs the new
  command in its own repo. Cross-repo commits are a HARD STOP, so this is not mine to execute.

## Corpus conformance contract — MEASURED from the existing commands, binding on Phases A–C

The operator's directive on approval: *"use same approach"*. Every rule below was read from the machinery
this run, not recalled; the anchors are what `/fabrik-plan-review` re-derives.

**1. Anatomy of a source command** (`commands/_sources/fabrik-data-contract.md` as the authoring template,
`fabrik-deploy-verify.md` as the verify template; `assemble_commands.py` renders `_sources` + `_fragments`
→ `~/.claude/commands/*.md` and a thin `SKILL.md` wrapper per command via `_emit_skill`):

| element | how the corpus does it | anchor |
|---|---|---|
| frontmatter | `description:` carries **TRIGGER — EN / TR phrases, SKIP (→ the sibling that owns the near-miss), Stage**; `argument-hint:` | `fabrik-features.md:1-3`, `fabrik-deploy-verify.md:1-3` |
| intro | what it produces, the seam it sits in as a fenced pipeline line, and the **HARD GATE** ("no plan builds against a `DRAFT` contract") | `fabrik-data-contract.md:7-19` |
| run record | `{{include:run-record}}` FIRST; `--phases` is DERIVED from `## Phase N —` headings (`_phase_count`, falls back to section count, never 0) | `assemble_commands.py::_phase_count`, `_fragments/run-record.md` tokens `COMMAND`/`PHASES` |
| termination — authoring | `{{include:term-edit}}` + `PARAMS` tokens `ARTIFACT · DONE_ACT · DONE_WORD · AXES · EXEMPT_NOTE` (render-time; no EXTRACT row — that table is the retired migration path): pass shape 1-wide + k-scoped + 1-wide, `method:` column, ≥1 `method: re-derivation` row, md5 anti-cheat, `new:` counts, stall breaker, probe duty (`$ ` fences) | `_fragments/term-edit.md`, `assemble_commands.py:394-` (PARAMS), `:734` (lookup), `:748` (the leftover-token refusal) |
| termination — verify | hand-written **token families** `PASS · FAIL (+route) · INCONCLUSIVE · NOT-RUN (<cause>)`, "routes are asks, never actions", early-stop on a shared root cause with `NOT-RUN` rows | `fabrik-deploy-verify.md:24-43` |
| grounding gate | `{{include:grounding-artifact}}` with `PARAMS` `SUBJECT`/`EXAMPLES` — every claim at a freshly-read `path:line`; universal/negative claims need the enumerating command | `_fragments/grounding-artifact.md`, `assemble_commands.py:556` |
| phases | `## Phase N — <title>` headings; each phase tagged **`[anywhere]`** or **`[hub-side]`** (where it may run) | `fabrik-deploy-verify.md:73,108,126,160,168,180` |
| modes | Phase 0 declares **Mode A (spec-driven) / B (reverse-generate from what exists) / C (fresh stub)** and states which and why; the seeded DRAFT stub is "meant to be edited through — NOT a STOP"; a `FROZEN` artifact → STOP, then re-freeze with a Version bump | `fabrik-data-contract.md:22-54` |
| converge loop | a self-audit phase listing the axes; each pass records what it re-read and changed; terminates ONLY on an edit-free md5-verified no-op | `fabrik-data-contract.md:142-162`, `fabrik-features.md:88-104` |
| freeze | Status flip + **`docs/DECISIONS.md` row in the SAME change**; header `Status · Version · Date · Mode` + the freeze rule verbatim; the flip is the exempt post-convergence write; a **gate coupling** named (which check WARNs on drift) | `fabrik-data-contract.md:164-181` |
| hand-off | the NEXT rule per mode; on a version BUMP a **Downstream impact** table and the NEXT line becomes the owed re-freeze | `fabrik-data-contract.md:183-190, 206-225` |
| question bar | `{{include:questionbar}}` with tokens `CHANGES_WHAT · RESOLVE_FROM · NEVER_FOR · DO_RAISE` | `_fragments/questionbar.md`, `assemble_commands.py` PARAMS |
| guardrails | `## Guardrails — never` — a short negative-space list | `fabrik-data-contract.md:192-204` |
| subagents | `{{include:subagents-core}}` with `HEADLINE · TASK_TYPE · PROJECT · FLOOR · EXTRA`; pool-default for gradeable fan-out + `set_quality`; `_floor()` when a review needs native Opus | `assemble_commands.py::_floor`, PARAMS |
| output | `## Output (always, last thing)` — a FIXED fenced block with a row vocabulary, then `Next command: …` | `fabrik-deploy-verify.md:199-216` |
| close-out | `close-feedback` is **auto-appended to every rendered command** — never written into a source | `assemble_commands.py:27-29`, `tests/test_close_feedback_autoappend.py` |
| untrusted input | `{{include:injection}}` where the command reads fetched/third-party content — the checklist reads project docs (D-065) and DEV state, so it declares them DATA | `_fragments/injection.md` |
| prompt authoring | Parts A–C of `docs/reference/MD/ai-prompt-templates.md` bind: B.2 termination, B.3 evidence-before-assertion, B.4 `path:line`, B.5 question bar, B.9 honest reporting, B.11 untrusted input | `ai-prompt-templates.md:256-317` |

**2. Registration** — a new command is not "a file in `_sources/`": it is (a) the source, (b) a `NEXT`
entry (`assemble_commands.py:49`, the successor line the wrapper prints), (c) a `PARAMS` block with every token the included fragments carry — **a token left unfilled does not ship literally, it REFUSES the whole render** (`:748` collects `unresolved […]` into `errs`; `:248` is the same guard for orchestrator wrappers), which is what makes a missing block loud rather than a silent defect; `EXTRACT` (`:331`) is NOT part of registration,
(e) the auto-emitted `SKILL.md` wrapper, (f) the auto-enrolled router entry, (g) regenerated
`capabilities.json` + `docs/CAPABILITIES.md`.

**3. Enforcement the new text must pass** — `scripts/enforcement/check_command_corpus.py` (referenced paths
must EXIST; an advertised close must be runnable with `--feedback`; a claimed caller must actually call; every
command opens a run record), `tests/test_check_command_corpus.py::test_live_corpus_is_clean`,
`tests/test_close_feedback_autoappend.py` (the obligation reaches every source), `assemble_commands.py
--check` (temp-dir render, the only safe form outside master), `scripts/generate_capability_index.py`
(deterministic from `_sources`, `:456-475`).

**4. The artifact convention** (`templates/scaffold/docs/data-contract-template.md:1-10`): a seeded DRAFT stub
with a **Status / Version / Date / Mode** header, the FREEZE rule verbatim, and a FREEZE CHECKLIST; the md5
anti-cheat is measured on the artifact; downstream consumers pin the Version and a synced gate WARNs on a
stale pin. The parity contract is a **script**, per spec Q3 — so the header lives in a machine-readable
comment block the runner parses, and the FREEZE CHECKLIST is the script's own `--self-check` mode.

## Phase A — `/fabrik-deploy-verify` rewrite (the runner)

**Keep the verify-command anatomy intact** — the rewrite ADDS layers, it does not re-shape the command:
"Where this runs" (`:13-19`), the run record + grounding include (`:21-22`), the token-family termination
contract (`:24-43`), the Phase-0 store-surface hand-back with its own two-line closing form (`:47-61`),
spoke-awareness (`:65-69`), the sibling-discriminator DNS phase (`:73-106`), liveness-vs-readiness (`:108-124`),
the `[anywhere]`/`[hub-side]` tags, "routes are asks", and the fixed Output block (`:199-216`).

**Steps**
1. **Phase 0 additions:** read the parity contract's header block from `scripts/verify_prod_parity.py`
   (`Status`, `Version`, `Mode`) — **`Status: FROZEN` is the obligation gate**: absent or `DRAFT` ⇒ the run's
   VERDICT is **`UNVERIFIED`** (terminal, never `CONFIRMED`, per spec Q2) and the Output's `ROUTES` names
   `/fabrik-deploy-checklist`. Read `docs/DEPLOYMENT.md` + `OPERATIONS.md` fleet-AI sections (D-065) as the
   declaration inputs.
2. **New `## Phase 1b — Identity` `[hub-side]`** (Layer 1): deployed SHA == tested SHA (`git rev-parse HEAD` on
   the VPS checkout vs the green-CI commit), `alembic current` == `alembic heads` (DB types), image digest ==
   built digest, lockfile hash. *(Measured absent today: `rev-parse` 0, `alembic` 0, `digest` 0.)* Nothing below
   it means anything if it fails — the phase is **early-stop** on FAIL, every later row `NOT-RUN (identity)`.
3. **Rewrite Phase 3 so the registrar table is DERIVED at RUN time** — the command instructs the agent to
   read `infrastructure.py::_REGISTRAR_ORDER` live and emit one row per registrar, keyed by name, using the
   existing per-registrar "Verify via" cells as the rule text. ⚠️ **DECIDED, RUN time not render time:**
   render-time injection would need an `assemble_commands.py` LOGIC change (out of scope — row 3 is
   registration only) and would re-freeze the list into rendered text, re-creating the hand-listed staleness.
   The 10 today: postgres · redis · gatus · backrest · glitchtip · grafana · authelia · meilisearch ·
   prometheus · watchdog. A registrar with no rule text is a `FAIL (unmapped registrar → /fabrik-review)`,
   never a silent skip — that is the `present-but-inert` mode applied to the verifier itself.
4. **Phase 6 becomes `## Phase 6 — Parity (contract-driven, BLOCKING)` `[anywhere]`** — remove the
   "first 3 rows" cap; execute `scripts/verify_prod_parity.py --json` against the LIVE service (read-only
   rows only; a mutating row is named, never run — the existing rule at `:190-193`); consume every
   row's `{system,status,detail,expected,actual,match,compare_error}`.
5. **Implement the verdict algebra** — `UP` (Layers 1+3) / `COMPLETE` (Layer 2 + parity) / `RUNNING` (Layer
   4) separately failable; `CONFIRMED` requires all three; **`UNVERIFIED`** when no FROZEN contract;
   `not obligated` (a `shape:` exemption) distinct from `not checked` (an `UNVERIFIABLE (<why>)` row);
   **`match` read BY ROW SHAPE, never by value** (spec § Verdict algebra, the one-rule table): `expected`+
   `actual`+`None` = attempted-unresolved ⇒ **FAIL CLOSED**, denies `CONFIRMED`, exit 2 — never "not
   checked"; a row with no `expected`/`actual` is not a parity row (outside the parity denominator, judged
   under `UP`); `True` = numerator; `False` = denies `CONFIRMED`, exit 2. **Precedence `1 → 2 → 0`**
   (liveness wins) never upgrades a verdict.
6. **Always pass `strict=True`** to the vendored `health-probe` CLI. Proven at `health_probe.py:448`
   (`critical = critical or set()`) with `:478`/`:481`: `critical` undeclared ⇒ every probe DOWN still
   `sys.exit(0)` while printing `DOWN:`. A runner that omits it is fail-open on liveness — reproduced by three
   independent builds (fabrik-lib runs 3, 6 and their plan-review).
7. **EXECUTE the verdict algebra before calling it built** (fabrik-lib's D-026): ship
   `tests/test_deploy_verify_verdict.py` feeding the algebra the four row shapes (liveness-only/`None` ·
   `expected`+`actual`+`None` · `+False` · `+True`) plus a critical-DOWN co-occurring with a mismatch;
   assert fail-closed on attempted-unresolved, `CONFIRMED` denied by either condition independently,
   exit `1` over `2` never upgrading, a liveness-only row absent from the parity denominator.
   **Watched-fail-first** — run the RETIRED uniform `None → not checked` rule beside the real one and
   assert it produces the false all-clear (the scratch `verdict_algebra_check.py` from spec-review J5 is the
   reference: 13 assertions, retired rule reproduces the defect).
8. **Output block + registration:** add `IDENTITY:` and `PARITY: <n> agree / <n> disagree / <n> unresolved
   / <n> UNVERIFIABLE of <N> (contract v<N>, Mode <A|B|C>)` rows; VERDICT vocabulary becomes
   `DEPLOY CONFIRMED | VERIFICATION FAILED — <n> FAIL routed | UNVERIFIED — no FROZEN parity contract →
   /fabrik-deploy-checklist | VERIFICATION INCOMPLETE — …`. Update the description (TRIGGER/SKIP/Stage),
   the `NEXT` entry (`assemble_commands.py:80` → *"none — terminal; a FAIL's route is the next action; an
   UNVERIFIED verdict routes to /fabrik-deploy-checklist"*), and the `PARAMS` `EXAMPLES` at `:556` (add: *"a
   parity PASS read off a `match: None` row"*, *"a registrar row copied from the command instead of
   `_REGISTRAR_ORDER`"*).

**Gate:** `python scripts/final_gate.py --json` → success · `python commands/assemble_commands.py --check`
(temp-dir render, safe) · `python scripts/enforcement/check_command_corpus.py` clean ·
`pytest tests/test_check_command_corpus.py tests/test_close_feedback_autoappend.py` green ·
**`pytest tests/test_deploy_verify_verdict.py` green, with its red-on-revert shown** ·
`grep -c _REGISTRAR_ORDER commands/_sources/fabrik-deploy-verify.md` **≥ 2** ·
`grep -c 'read .*_REGISTRAR_ORDER.* live\|derive .* from .*_REGISTRAR_ORDER' commands/_sources/fabrik-deploy-verify.md` ≥ 1 ·
`grep -c '^## Phase 6 — Parity' commands/_sources/fabrik-deploy-verify.md` = 1 ·
`grep -c 'UNVERIFIED' commands/_sources/fabrik-deploy-verify.md` ≥ 2 (Phase 0 rule + Output vocabulary).

⚠️ **The `≥ 1` the `_REGISTRAR_ORDER` grep replaces was a CHECK THAT CANNOT FAIL — it already passed before
Phase A ran** (spec-review pass H1): `grep -c` returns **1** today from an incidental mention at
`commands/_sources/fabrik-deploy-verify.md:137`. A gate satisfied by the pre-existing state is the
*present-but-inert* failure mode applied to the plan's own gate; the spec's rule is *"a check that cannot
fail is a defect."*

**Evidence owed:** the 10 registrar names re-derived from `infrastructure.py` in-run; a `--check` render
showing no pruning; the verdict test's red run pasted.

## Phase B — `/fabrik-deploy-checklist`, the new authoring command (built to the anatomy)

⚠️ **EXECUTION ORDER IS A → C → B → D, and B's registration lands in ONE commit** — proven by running
`check_command_corpus.audit()` over a scratch copy carrying the new source: it returned exactly two
problems, both *"`scripts/verify_prod_parity.py` does not exist"* (predicate 3 resolves every
`scripts/*.py` a source names against the repo and `templates/**`). So Phase C's template must exist before
this phase's gate runs. And predicate 2 (every `/fabrik-x` a source names must resolve to a real source)
means the `NEXT` retargets, the `/fabrik-release` precondition and the pipeline line may only be committed
TOGETHER WITH or AFTER the new source — never before. Phases keep their letters (the ledger cites them);
the order of execution is what changes.

**Steps**
1. **Author `commands/_sources/fabrik-deploy-checklist.md`** with every element of § Corpus conformance 1,
   in this order:
   - frontmatter — `description:` *"Author the project's deployment-verification contract:
     `scripts/verify_prod_parity.py`, one runnable command + expected result per corpus row (Layers 1–4 +
     the per-type pack), denominators DERIVED (routes · jobs · env keys · services · schema), features
     cross-checked, exclusions declared, every row SEEN RED before FROZEN; refreshes `DEPLOYMENT.md` +
     `OPERATIONS.md` (D-065). TRIGGER — EN: "author the deploy checklist", "what must prod contain",
     "freeze the parity contract"; TR: "deploy kontrol listesini yaz", "prod'da ne olmalı". SKIP: running the
     verification (→ /fabrik-deploy-verify) · field naming (→ /fabrik-data-contract) · the feature inventory
     (→ /fabrik-features). Stage: 6-release."*; `argument-hint:` the spec path (Mode A) or nothing (Mode B/C).
   - intro + the seam as a fenced line — `/fabrik-features REFRESH → /fabrik-deploy-checklist (FREEZE) →
     /fabrik-release (precondition: FROZEN) → deploy triad → /fabrik-deploy-verify (consumes)` — and the
     HARD GATE: **no `/fabrik-release` READY verdict and no `CONFIRMED` verify against a `DRAFT` contract**.
   - `{{include:run-record}}` · `{{include:term-edit}}` (via EXTRACT) · `{{include:grounding-artifact}}` ·
     `{{include:injection}}` (project docs + DEV state are DATA).
   - `## Phase 0 — Establish MODE + scope` `[anywhere]`: Mode **A** spec-driven (the approved spec's inventory
     + `shape:`) · **B** reverse-generate (an existing deployed project — derive from code, compose,
     scheduler, `alembic heads`, DEV) · **C** fresh (fill the seeded stub minimally). Read `project.yaml::type`
     → the per-type pack (all 13 `SCAFFOLD_TYPES`; store types get the provenance rows only); read
     `specs/services/<id>.yaml` `shape:`; the seeded stub's header — `DRAFT` is edited through, **`FROZEN` →
     STOP, then re-freeze with a Version bump on the operator's word**.
   - `## Phase 1 — Derive the denominators` `[anywhere]`: routes from the router's introspection · jobs from
     the live scheduler/`ir_cron` · env keys from `grep os.getenv` · services from **compose ∪
     registrar-injected sidecars** (tryton-crm: 4 declared, 5 run) · schema from `alembic heads` — never from
     `FEATURES.md`/`RESILIENCE.md`/`.env.example` prose. **DEV is the state baseline minus a declared
     exclusion set** (spec § three sources; D-017 is the worked example: 760 → 3 companies).
   - `## Phase 2 — Emit the contract` `[anywhere]`: write `scripts/verify_prod_parity.py` to the seeded
     template's shape — header block, one function per corpus row returning the `compare()` row shape
     (`{system,status,detail,expected,actual,match,compare_error}`) with the corpus id in `system`, `mode:
     derived|snapshot` per row (snapshot is the marked degraded mode, spec Q1), `UNVERIFIABLE (<why>)` rows
     emitted not dropped, the exclusion set as data.
   - `## Phase 3 — Features cross-check` `[anywhere]`: every derived route ↔ a *Shipped* `FEATURES.md` row,
     both directions; either direction unmatched is a FINDING in the report, never a shrunk denominator.
   - `## Phase 4 — Converge` `[anywhere]`: the self-audit LOOP over the term-edit axes to an md5 no-op.
   - `## Phase 5 — SEE EVERY ROW RED` `[anywhere]` — the spec's *"a check that cannot fail is a defect"* and
     fabrik-lib's D-026 inside the authoring command: run the contract against DEV (expected green), then
     against a deliberately broken DEV state per row class (a dropped row, a renamed env key, a stopped job)
     and assert each row FAILS; a row that cannot be made to fail is rewritten or marked `UNVERIFIABLE
     (cannot be seen red: <why>)`. Paste the red run into the report.
   - `## Phase 6 — Freeze + wire the truth`: header `Status: FROZEN · Version: v<N> · Date · Mode`, the freeze
     rule verbatim (*"Frozen — no agent adds, removes or re-derives a row not listed here. Any change = bump
     Version + re-freeze via `/fabrik-deploy-checklist`."*), **the `docs/DECISIONS.md` row in the same
     change**, refresh `DEPLOYMENT.md` + `OPERATIONS.md` **from CODE + SPEC + DEV, never from PROD** (the
     hazard rule), and name the gate coupling: a change to compose / the scheduler / `os.getenv` set /
     `alembic heads` without a contract bump is a WARN (the `check_schema_sync.py` shape, extended).
     **Grader ruling (evaluation-checklist items 35–37, stated not implied):** today NO executable check
     grades the parity script's `FROZEN` header — `check_stage_artifacts.py` grades only
     `data-contract`/`ui-design` FROZEN flips. That is a DELIBERATE deferral, not an oversight: the header
     grammar is settled here, and extending `check_stage_artifacts.py` to it is a `docs/STRATEGIC_BACKLOG.md`
     row minted in Phase D with this plan's commit as its trigger — never silently absent.
   - `## Phase 7 — Hand off`: Mode A/B → `/fabrik-release` (its precondition now reads this header); on a
     BUMP → the Downstream-impact table (which verify rows changed) and NEXT names the re-verify.
   - `{{include:questionbar}}` · `## Guardrails — never` (derive from PROD · drop a row · freeze on an
     editing pass · invent a check without a corpus id · execute a mutating row against prod · treat a
     `None` match as agreement) · `## Re-freeze close-out` · `{{include:subagents-core}}` ·
     `## Output (always, last thing)` — a fixed block: `DEPLOY-CHECKLIST: <project> · Mode <A|B|C> · v<N>`,
     `ROWS: <N> (<n> derived / <n> snapshot / <n> UNVERIFIABLE)`, `RED-SEEN: <n> of <N>`,
     `FEATURES: <n> routes ↔ <n> rows, <n> unmatched`, `DOCS: DEPLOYMENT.md + OPERATIONS.md refreshed`,
     `STATUS: FROZEN v<N> | DRAFT (<why>)`, then `Next command: /fabrik-release`.
2. **Register it** (`commands/assemble_commands.py`, registration only): `NEXT["fabrik-deploy-checklist"] =
   "/fabrik-release — its VPS-path precondition reads the FROZEN header. On a version BUMP with downstream
   impact: /fabrik-deploy-verify re-run against the bumped contract."`; retarget `NEXT["fabrik-features"]`'s
   REFRESH branch to name `/fabrik-deploy-checklist` before certification;
   a `PARAMS` block (no `EXTRACT` row — see § Corpus conformance 2) — `term-edit`: `ARTIFACT` "parity contract", `DONE_ACT` "flip `Status: DRAFT → FROZEN`",
   `DONE_WORD` "FROZEN", `AXES` "corpus coverage · derived denominators · features cross-check ·
   executability · exclusions · red-seen · docs", `EXEMPT_NOTE` (the Phase-6 flip is exempt);
   `grounding-artifact`: `SUBJECT` "contract row", `EXAMPLES` *a route "verified" the router never registers,
   a job count read from RESILIENCE.md, a row count taken from PROD, a `None` match read as agreement*;
   `questionbar`: `CHANGES_WHAT` "the contract (what prod must contain, or which dev state is excluded)",
   `RESOLVE_FROM` "the spec, `shape:`, the router, the scheduler, DEV, the project's decision ledger",
   `NEVER_FOR` "a row's wording, its ordering, or an obvious expected value — derive it", `DO_RAISE` "an
   exclusion the ledger does not settle (fixture vs real data), or a row that cannot be seen red";
   `subagents-core`: `HEADLINE` "pool-default per denominator surface", `TASK_TYPE` '"docs"', `PROJECT`
   "deploy-checklist", `FLOOR` "", `EXTRA` one pool grounder per surface (routes · jobs · env · services ·
   schema) in `mode="read_only"` with the surface's code inlined; the exclusion-set judgement and the
   red-seen runs stay native.
3. **`fabrik-release.md` precondition** (`:76`, VPS path): before step 1 — *"`scripts/verify_prod_parity.py`
   header `Status: FROZEN` (read it, do not assume it) — else `BLOCKED: parity contract DRAFT →
   /fabrik-deploy-checklist`; a contract whose Version is behind the compose/scheduler/env set is a ⚠ WARN in
   the Gate-2 block."* Mirrors the certification-handoff precondition at `:20-35`, same grammar.
4. **Pipeline line** — `CLAUDE.md:333` and `templates/governance/CLAUDE.md:339`: insert **`/fabrik-deploy-checklist`**
   after the `/fabrik-features` denominator refresh and before end-to-end certification. ⚠️ Synced surface —
   correct for ALL ~46 projects (store types run it in provenance-only form, per the per-type pack).
5. **Regenerate** `capabilities.json` + `docs/CAPABILITIES.md` (`scripts/generate_capability_index.py`) and
   add `INDEX.md` rows.

**Gate:** `final_gate --json` success · `assemble_commands.py --check` · `check_command_corpus.py` clean · the
new command appears in `NEXT` and renders a `SKILL.md` wrapper in the `--check` temp dir · `pytest
tests/test_check_command_corpus.py` green with a new test asserting the rendered checklist command carries
`## Phase 5 — SEE EVERY ROW RED`, the `Status:` header rule and the Output block · `generate_capability_index.py`
diff is empty after regeneration · **a dry authoring run against tryton-crm (Mode B) produces a non-empty
row set with its denominator stated and at least one row seen red**.

**Evidence owed:** the rendered command's section spine (`grep -nE '^## ' ~/.claude/commands/fabrik-deploy-checklist.md`)
matching the anatomy table; the tryton-crm dry run's Output block pasted.

## Phase C — scaffolder seeding (born compliant)

**Steps**
1. **The stub is a TEMPLATE, copied by the existing script loop** — `templates/scaffold/scripts/verify_prod_parity.py`
   added to `SCRIPT_FILES` (`scaffold.py:479`), copied and `chmod 755` by the loop at `scaffold.py:1127` (the
   same path that seeds `runc`/`rund`/…). Its header block: `# Status: DRAFT ·
   Version: v0 · Date: <scaffold date> · Mode: —` + the freeze rule; its body prints *"parity contract not yet
   authored — run /fabrik-deploy-checklist"* and **`sys.exit(2)`** (an unfilled contract fails closed, and
   `2` is the contract's own "disagrees/unresolved" code, so a runner reading it gets the right branch).
2. **`specs/services/<id>.yaml`** generated from `project.yaml` + `shape:` at scaffold time (why 27 repos lack
   one and no future repo will), and the **fleet-AI sections** added to `templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md`
   / `OPERATIONS_TEMPLATE.md` (D-065) with `<to be filled by /fabrik-deploy-checklist>` sentinels the
   existing `check_doc_stubs` WARN can see.
3. ⚠️ **Docusaurus leak caveat** (`scaffold.py:293`): the script seeds into `scripts/` (outside `docs/`, never
   published); the two doc templates ARE in `docs/` — so the new sections must contain no host, DSN or count
   sentinels that would be a leak when published, and the existing content-docs `exclude` is asserted by test.
4. **Behavior test** `tests/test_scaffold_deploy_contract.py`: scaffold each of the 13 types in a temp dir;
   assert the stub exists, is executable, **exits 2**, and its header parses; assert a `docusaurus` scaffold
   does not publish the new doc sections; **red-on-revert** for the exit code and the exclusion.

**Gate:** `final_gate --json` success · `timeout 900 pytest tests/test_scaffold*.py` green · the exit-code and
docusaurus-exclusion assertions proven **red-on-revert**.

⚠️ **The 900s budget is MEASURED, not guessed** (2026-09-02, idle box, no concurrent runs):
`1 failed, 251 passed, 1 deselected in 560.49s (9m20s)`. 900s leaves ~60% headroom.
Three corrections behind that number, all mine:
- The suite was called HUNG three times. It never was — `test_scaffold.py` is **65 passed in 274.75s**
  and every rc=124 came from a timeout set below it, twice compounded by concurrent runs I had launched.
- `compose_traefik` WAS pathological (200s+ → **46 passed in 54s**) because `_scaffold` re-ran
  `create_project` (~24s) per parametrized test; fixed by caching per type (`7cca80f9`).
- The `1 deselected` is the `pnpm install` test, correctly marked `needs_network` (`84cb5dd3`) — the
  one genuinely network-bound case, and never the blocker I first blamed.
The lone red (`saas_backend::test_auth_and_headers`) was a **stale test**, not a scaffold defect: it
asserted Supabase Pattern B after `4a5e9b5b` deliberately flipped the scaffold to Pattern A. Fixed
against measured emitted output, so this gate can actually reach green.

## Phase D — convergence

`/fabrik-review` over the full diff to a raised-zero round (heavy surface: a new command + a synced
governance template + scaffold emission ⇒ the FULL review, pool breadth + native Opus) · `docs_updater.py
--check` · `python scripts/generate_capability_index.py` then `git diff --exit-code capabilities.json
docs/CAPABILITIES.md` (regenerated, never hand-edited) · `INDEX.md` rows for every new file · CHANGELOG entry
· `docs/DECISIONS.md` row — a **"built X at Y"** row (verification ownership moves to the project; the
authoring command exists) · **sync-consciousness:** the commit touching `templates/governance/CLAUDE.md`
distributes fleet-wide via the post-commit governance-sync — know the blast radius before staging, and
never a hub-only experiment on that path.

## Self-audit

- **Every phase has a runnable gate** — no phase exits on inspection, and every Phase A/B gate names the
  corpus checks the new text must pass (`check_command_corpus.py`, the two corpus tests, `--check` render,
  capability-index regeneration), not just the generic `final_gate`.
- **The plan follows the corpus's own approach, measured not recalled** — § Corpus conformance contract is a
  table of anchors read this run; `/fabrik-plan-review`'s re-derivation pass re-opens every one of them.
- **The riskiest step is File Scope row 5** — a synced governance template; wrong for ONE of ~46 projects
  and it ships to all of them. Second riskiest: Phase C's docusaurus caveat, guarded by a test, not a comment.
- **This plan binds to a fabrik-lib INTERFACE but depends on no fabrik-lib ARTIFACT** — their `compare()`
  shape, tri-state `match` and exit ranking are settled and Phase A is written to them; their *build* is not
  a prerequisite, because the runner implements the same shape locally until it lands. Binding to a settled
  interface costs nothing and makes the swap a deletion; the old fallback would have invented a second shape.
- **Two design checks are EXECUTED, not read** — Phase A step 7 (the verdict algebra, watched-fail-first
  against the retired rule) and Phase B's Phase 5 (every contract row seen RED). Five text-only CONVERGED
  stamps on the spec were each wrong; the plan does not repeat the method.
- **Residual risk, named:** the store/static per-type packs are the least-grounded content in the spec (no
  such deploy was exercised). Phase B ships their rows `UNVERIFIABLE` **by default** rather than guessing.

## Evidence (re-derived from primary sources, this run)

```
$ grep -n '_REGISTRAR_ORDER' src/fabrik/orchestrator/infrastructure.py | head -1
151:_REGISTRAR_ORDER = (
$ grep -n 'data-contract-template' src/fabrik/scaffold.py
285:    "docs/data-contract-template.md": "docs/data-contract.md",  # frozen field dictionary
$ grep -n '^SCRIPT_FILES = \|Copy executable scripts from templates/scaffold/scripts' src/fabrik/scaffold.py
479:SCRIPT_FILES = [
1127:    # Copy executable scripts from templates/scaffold/scripts/
$ wc -l < commands/_sources/fabrik-deploy-verify.md
216
$ grep -n '^NEXT = {\|^EXTRACT = {\|^PARAMS = {\|"fabrik-deploy-verify": {' commands/assemble_commands.py
49:NEXT = {
331:EXTRACT = {
394:PARAMS = {
556:    "fabrik-deploy-verify": {
$ grep -c -- '--check' commands/assemble_commands.py
4
$ ls tests/ | grep -i corpus
test_check_command_corpus.py
$ grep -n 'commands" / "_sources' scripts/generate_capability_index.py
461:    for f in sorted((root / "commands" / "_sources").glob("*.md")):
$ grep -n 'fabrik-deploy-verify' CLAUDE.md templates/governance/CLAUDE.md | cut -d: -f1,2
CLAUDE.md:61
CLAUDE.md:333
templates/governance/CLAUDE.md:53
templates/governance/CLAUDE.md:339
$ grep -c 'include:run-record' commands/_sources/*.md | awk -F: '{s+=$2} END{print s}'
29
$ ls tests/test_scaffold*.py | wc -l
13
```

**EXECUTED, not read — a stub of the new source rendered through the real pipeline in a scratch copy
of `_sources/` (2026-09-02, the operator's "are you sure?"):**

```
# EXP1 — the stub with its includes but NO PARAMS entry
RENDER ERRORS:
 - fabrik-deploy-checklist: unresolved ['{{ARTIFACT}}', '{{AXES}}', '{{CHANGES_WHAT}}', '{{DONE_ACT}}',
   '{{DONE_WORD}}', '{{DO_RAISE}}', '{{EXAMPLES}}', '{{EXEMPT_NOTE}}', '{{EXTRA}}', '{{FLOOR}}',
   '{{HEADLINE}}', '{{NEVER_FOR}}', '{{PROJECT}}', '{{RESOLVE_FROM}}', '{{SUBJECT}}', '{{TASK_TYPE}}']
# → the render REFUSES (fail-closed); these 16 are exactly the tokens Phase B step 2's PARAMS block fills

# EXP2 — the same stub WITH the PARAMS block Phase B step 2 specifies
rendered 33 commands … + 33 skills … + 4 agents
EXP2 (with PARAMS) → rendered 240 lines; leftover tokens: []
   phases derived: 8 | run-record start line: python3 scripts/command_run.py start --command fabrik-deploy-checklist --phases 8 \
   SKILL wrapper emitted: True | Next line present: True
   close-feedback auto-appended: True

# EXP3 — scripts/enforcement/check_command_corpus.audit() over the scratch sources
EXP3 corpus audit → total problems: 2 | about the stub: 2
   - …/_sources/fabrik-deploy-checklist.md:2: scripts/verify_prod_parity.py does not exist
   - …/_sources/fabrik-deploy-checklist.md:29: scripts/verify_prod_parity.py does not exist
# → predicate 3; the ONLY defect, and it is an ORDERING defect: Phase C's template must land before Phase B

# EXP4 — scripts/enforcement/check_trigger_routing.grade() over the same scratch sources
grade() → (mis-routes=[], correct=92, nowhere=48, broken_promises=[])
# → the stub's 5 advertised phrases route NOWHERE (the check's contract: safe, a denominator, never a
#   finding); no stem is added — skill_router.py's own policy is that a loose pattern is worse than the gap
```

**What the executed run proves and what it does NOT:** it proves the anatomy + PARAMS + registration
mechanics of Phase B render and pass the corpus predicates once Phase C's template exists, and that the
run-record phase count derives correctly from the `## Phase N` headings. It does **not** prove the command's
BODY (the phase prose is a stub), the runner rewrite (Phase A is not exercised by this experiment), or the
pipeline-line edit on the synced template (only `/fabrik-execute-plan`'s gate can). Those are exactly the
surfaces `/fabrik-plan-review` and then execution must ground.

**Per-phase anchors:** Phase A → `commands/_sources/fabrik-deploy-verify.md:24-43` (the token-family
termination contract the rewrite must keep), `:126-158` (Phase 3, to be derived), `:180-197` (Phase 6, to
become Parity), `:199-216` (Output), `src/fabrik/orchestrator/infrastructure.py:151`, `assemble_commands.py:80,556` ·
Phase B → `commands/_sources/fabrik-data-contract.md:22-54,142-190,206-225` (the authoring anatomy),
`commands/_fragments/term-edit.md`, `assemble_commands.py:49,331,394`, `commands/_sources/fabrik-release.md:20-35,76-86`,
`CLAUDE.md:333`, `templates/governance/CLAUDE.md:339`, `scripts/generate_capability_index.py:461`,
`docs/reference/MD/ai-prompt-templates.md:256-317` · Phase C → `src/fabrik/scaffold.py:285,293,479,1127`,
`templates/scaffold/docs/data-contract-template.md:1-10` · Phase D → `scripts/enforcement/check_convergence.py`.

## Coverage Checklist

**Rubric invocation** — `python scripts/review_rubric.py --changed commands/_sources/fabrik-deploy-verify.md src/fabrik/scaffold.py`

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
   [FLOOR continues — the rows above are the ones bearing on this surface]
```

**What the rubric changed here:** the FLOOR's internal-service-auth row (`X-Internal-Token` +
`hmac.compare_digest`, never an inline `APIKeyHeader`) is what the parity contract's own probes must use
when they call a sibling service — recorded so Phase B does not hand-roll auth in generated check rows.


| Class | Verdict | Evidence |
|---|---|---|
| Gate runnability (every phase exits on a real command) | CLEAN | `--check` verified present (4 refs); 13 `tests/test_scaffold*.py` |
| File Scope completeness | **FIXED** | `tests/**` was unbounded → 2 named files; `infrastructure.py` declared READ-ONLY |
| Render-time vs run-time ambiguity | **FIXED** | decided RUN time; render-time would need an out-of-scope `assemble_commands.py` change |
| Cross-repo boundary | CLEAN | fabrik-lib filed not planned; 27-repo onboarding self-serve |
| Fleet-sync blast radius | CLEAN | merge-time render only; `--check` is the safe form |
| **fail-open/fail-closed** (standing) | CLEAN | the seeded stub EXITS NON-ZERO — an unfilled contract fails closed |
| **boundary/sentinel/prefix** (standing) | CLEAN | docusaurus leak boundary guarded by a test, not a comment |
| **cost/quota accounting** (standing) | CLEAN | no metered spend; no subagent fan-out planned |
| **behavior-without-a-test** (standing) | **FIXED** | Phase C's two assertions require red-on-revert proof |

## Pass ledger (`/fabrik-plan-review`)

| Pass | Axes | Raised | Fixed | md5 |
|---:|---|---:|---:|---|
| Pass 1 | gate-runnability · File Scope completeness · fabrik-lib fallback · render-vs-run ambiguity | 4 | 4 | `acbdf439…` → `49c6bc8c…` |
| Pass 2 | full confirming re-sweep | 0 | 0 | stable |
| Pass 3 | method: re-derivation — every count re-run against its primary source, not re-cited | 1 | 1 | edited |
| Pass 4 | confirming | **0** | **0** | stable ✓ |

| — | **operator approved the design (D-077) and directed: re-author to the command-corpus conventions — convergence voided, `/fabrik-plan-review` owed** | — | — | — |

**Pass 4 terminal — `found: 0, fixed: 0`.** *(Historical — the corpus re-authoring above post-dates it.)*

**Pass 3 (re-derivation) found a 5th:** I had written *"meilisearch has no verification row at all"*.
Re-running the grep shows it has **1** in the command — the absence was in my **spec's Layer 3**, not the
command. `_REGISTRAR_ORDER` is also at `:151`, not the range I had carried from another document. Both
corrected. This is why the closing pass must re-derive rather than re-read: passes 1–2 re-verified my
citations and my citations agreed with me.

**Findings, all mine:**
1. `tests/**` was an unbounded File Scope — replaced with two named test files.
2. `infrastructure.py` was referenced by Phase A but absent from scope — declared as a **READ-ONLY input**.
3. **Layer 3 derivation was ambiguous between render-time and run-time**, and the two have different File
   Scopes. **Decided: RUN time** — render-time injection would need an `assemble_commands.py` change
   (out of scope) *and* would re-freeze the list into rendered text, recreating the exact staleness this
   fixes.
4. Gates verified runnable, not assumed: `assemble_commands.py --check` exists (4 references), 13
   `tests/test_scaffold*.py` files present.

Status at the end of that review: CONVERGED — **now DRAFT again** (header).

## Next

`/fabrik-plan-review docs/development/plans/2026-09-01-plan-1-deployment-verification.md` — the corpus
re-authoring rewrote Phases A–C and the File Scope; a plan cannot self-grade that. Then, on the operator's
approval, `/fabrik-execute-plan`.

## Appendix A — Phase B source DRAFT, proven through the real pipeline (2026-09-02)

The operator asked twice whether the command could be created properly. The answer is this draft — the
**complete source** Phase B starts from, not a stub — plus what executing it showed. It lives here rather
than in `commands/_sources/` because a file there renders box-wide and corpus predicate 3 fails until
Phase C seeds `templates/scaffold/scripts/verify_prod_parity.py` (execution order A → C → B → D).

**Executed against the draft (scratch copy of `_sources/` + the assembler imported, PARAMS from Phase B
step 2, NEXT from step 2):**

```
render:   387 lines · leftover tokens [] · phases derived 8 · SKILL.md emitted (1643 bytes, under the
          1024-char composed-description limit at assemble_commands.py::_emit_skill — the FIRST draft's
          description composed to 1366 and the renderer REFUSED it; trimmed to 785)
audit:    check_command_corpus.audit() → 4 problems, all "scripts/verify_prod_parity.py does not exist"
          (predicate 3; closes when Phase C's template lands — the ordering rule above)
triggers: check_trigger_routing.grade() → mis-routes=[] correct=92 nowhere=48 broken=[]
          (the draft's 5 phrases route nowhere — safe by that check's contract; no stem added)
checklist: 31/31 mechanical items of docs/reference/command-evaluation-checklist.md pass on the RENDERED text
dry run:  Mode B against /opt/tryton-crm, from the PROJECT root — services 4 (yaml parse) + 1 sidecar ·
          env keys 38 distinct over 53 files · FEATURES 25 tables / 212 rows / 88 shipped (every table
          walked, status rule per header; a first-table-only read gave 0) · D-017 exclusion ruling read
          from the WHAT cell · jobs/schema/state correctly UNVERIFIABLE from a static run (trytond
          ir.cron, no alembic, no DEV DB started) · routes: a flat app.routes read gives 3 application
          routes while the started app's /openapi.json gives 27 paths — the include_router'd v1_router
          (prefix /internal/v1, api/__init__.py:26) is NESTED, not attached later (my first diagnosis
          was wrong; the executed TestClient run corrected it) — see Phase 1's routes row
draft md5: 110cdcd8
```

**Four body rules exist only because the dry run found them:** derive routes from the started app's
`/openapi.json` (a flat `app.routes` read under-counts 3 vs 27) and subtract framework paths, stating
both counts · walk every FEATURES table with a per-table header rule · read the ledger's WHAT cell ·
label every static-run derivation that needs the live system `UNVERIFIABLE (<why>)`.

```markdown
---
description: Author the project's deployment-verification CONTRACT — `scripts/verify_prod_parity.py`: one runnable check + expected result per corpus row, every denominator DERIVED from the system (route table · compose ∪ sidecars · `os.getenv` · scheduler · schema head), features cross-checked, DEV-minus-exclusions baseline, every row SEEN RED before `FROZEN`; refreshes the fleet-AI sections of `DEPLOYMENT.md` + `OPERATIONS.md` from CODE + SPEC + DEV, never PROD. TRIGGER — EN: "author the deploy checklist", "what must prod contain", "freeze the parity contract"; TR: "deploy kontrol listesini yaz", "prod'da ne olmalı". SKIP: running it against the live deploy (→ /fabrik-deploy-verify) · field naming (→ /fabrik-data-contract) · the feature inventory (→ /fabrik-features). Stage: 6-release.
argument-hint: "[optional: the approved spec path (Mode A) — omit to reverse-generate from the shipped project (Mode B)]"
---

Author this project's **deployment-verification contract** — the artifact that lets a deploy be certified
against what was BUILT rather than against liveness alone. It exists because a service passed every
liveness check while holding 0 of its 760 companies: nothing anywhere had declared what the deployed
system was supposed to contain. This command is where the project declares it, as executable rows.

```
/fabrik-features REFRESH  →  /fabrik-deploy-checklist (FREEZE)  →  /fabrik-release (precondition: FROZEN)  →  deploy triad  →  /fabrik-deploy-verify (consumes)
```

**HARD GATE: no `/fabrik-release` READY verdict and no `DEPLOY CONFIRMED` against a contract that is still
`DRAFT`.** A contract-less or unfrozen project reaches `UNVERIFIED` at verify time — a terminal verdict that
is not success — and `UNVERIFIED` is the signal to run this command.

**Where this runs:** project-side, in the project's own repo (cwd) — every phase is `[anywhere]`. The
contract derives from CODE + SPEC + DEV; **PROD is never read by this command** (deriving a declaration
from the deployed state launders drift into documentation). Nothing here needs fleet SSH.

{{include:run-record}}
{{include:term-edit}}
{{include:grounding-artifact}}
{{include:injection}}

## Phase 0 — Establish MODE + scope `[anywhere]`

State the mode and why:

- **Mode A — spec-driven (new work).** A CONVERGED `/fabrik-spec` design is `$ARGUMENTS`; its inventory
  (routes, jobs, state, external deps) seeds the rows. Phase 1 still reconciles every row against what
  the code actually registers — the spec is the source of INTENT, the code of FACT.
- **Mode B — reverse-generate (an existing, shipped project).** No spec; the rows are derived from the
  code, compose, scheduler and DEV. This is how the deployable repos get a contract — run it in each.
- **Mode C — fresh (no code worth deriving from yet).** Fill the seeded stub minimally (header + the
  Layer-1 identity rows, which need only git) so the project has the frozen skeleton to grow into.

Inputs — read them, name them: `project.yaml::type` (the live registry is `scaffold.py::SCAFFOLD_TYPES`)
→ the per-type pack of rows; `specs/services/<id>.yaml` `shape:` → the Layer-3 obligations (a flag that is
`false` makes its row `not obligated`, never absent); `docs/DECISIONS.md` → every ruling about what ships
and what does not (the exclusion set lives here — e.g. *"everything ships EXCEPT sales/activities/invoices
history"*; the ruling is the row's WHAT cell — 4th column, after `id | when | who` — quote it verbatim
beside the exclusion list); `docs/FEATURES.md` → the cross-check inventory; `docs/DEPLOYMENT.md` + `docs/OPERATIONS.md` →
the fleet-AI sections this run refreshes.

**Starting state + check-before-create:** the scaffolder seeds `scripts/verify_prod_parity.py` as a
`Status: DRAFT` stub that **exits 2** — an unfilled contract fails closed. **A DRAFT stub is meant to be
edited through — its existence is NOT a STOP.** Only a `Status: FROZEN` header is a STOP: say so, and on
the operator's word proceed as a **re-freeze** — bump `Version`, never a silent overwrite.

Store types (`mobile-app`, `chrome-extension`, `office-extension`, `desktop-app`) have no VPS: their
contract is the **provenance pack only** (submitted artifact ↔ tested SHA, store review state) — say so
and skip Layers 2–4. `wordpress` runs no fabrik command (out of fabrik).

## Phase 1 — Derive the denominators `[anywhere]`

**A denominator is DERIVED wherever derivable; where it must be declared it is CROSS-CHECKED against a
derived proxy.** Each source below is authoritative; the prose next to it is never the sole basis.

| denominator | derive from (authoritative) | never from | when underivable |
|---|---|---|---|
| routes | the app's OWN published table: **`/openapi.json` from the started app** (a `TestClient(app)` context runs the lifespan; or the running DEV server), **then subtract the framework's paths** (`/`, `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect`) and state BOTH counts (`total / application`). ⚠️ A flat read of `app.routes` UNDER-COUNTS: routers included via `include_router` sit nested under router objects whose own `.routes` must be walked — measured on a real project, flat `app.routes` gave **3** application routes while `/openapi.json` gave **27** paths. ⚠️ Never a `grep include_router`: a composed `v1_router` carries its prefix on the parent (`prefix="/internal/v1"`), and the grep returns nothing | `FEATURES.md` prose · a flat `app.routes` read | `UNVERIFIABLE (no introspection: <why>)` |
| services | `yaml.safe_load(compose)["services"]` ∪ the registrar-injected sidecars the `shape:` flags imply (a `watchdog` container appears in no compose file). ⚠️ Never an indentation regex — it counts `volumes:`/`networks:` keys as services (measured: 6 for 4) | compose read by eye | — (always derivable) |
| env keys | `os.getenv(...)`/`os.environ[...]` names over `src/` (every key, de-duplicated) | `.env.example` alone | — |
| scheduled jobs | the live scheduler: `ir_cron` rows for a Tryton stack, Beat/APScheduler registrations for a scaffolded API, `crontab -l` for a host job | `RESILIENCE.md` §7 | `UNVERIFIABLE (scheduler not introspectable from here: <why>)` |
| schema head | the type's OWN mechanism: `alembic heads` for a scaffolded API; module state (`ir_module`) for trytond; a migrations dir count for node | `db/schema.sql`, a doc | `UNVERIFIABLE (no migration tool: <why>)` — never a guess |
| state baseline | **DEV minus the declared exclusion set** — row counts, reference data, translations, filestore counts measured in DEV; exclusions from `docs/DECISIONS.md` (fixture companies, test users, history the ruling excludes) | PROD (see the hazard rule) | a missing exclusion ruling is the one thing to RAISE (§ Question bar) |
| features | not derivable — `FEATURES.md` is prose | — | cross-checked in Phase 3, never trusted alone |

Record every derivation as the COMMAND that produced it and its COUNT (`routes: 23 via app.routes` ·
`services: 4 + 1 sidecar` · `env keys: 32 distinct over 49 sites`). A count without its command is a
claim.

**Parallelism — the default with 2+ derivation surfaces:** one pool grounder per surface (routes · jobs ·
env · services · schema) per § Subagents; the exclusion-set judgement and every DEV measurement stay
native — they read the project's own environment.

## Phase 2 — Emit the contract `[anywhere]`

Write `scripts/verify_prod_parity.py` to the seeded template's shape:

- **Header block** (machine-readable, the runner and the release precondition parse it):
  `# Status: DRAFT | FROZEN · Version: v<N> · Date: YYYY-MM-DD · Mode: A | B | C` and the freeze rule
  verbatim: *"Frozen — no agent adds, removes or re-derives a row not listed here. Any change = bump Version
  + re-freeze via `/fabrik-deploy-checklist`."*
- **One function per corpus row**, named by its corpus id (`L1_identity_sha`, `L2_routes`,
  `L2_state_companies`, `L3_postgres`, …), returning the `health-probe` comparison row shape —
  `{system, status, detail, expected, actual, match, compare_error}` — with `system` = the corpus id.
  `expected` is DERIVED at run time where Phase 1 derived it (**snapshot values are a cache of a
  derivation; ship the derivation**); a row that can only snapshot is marked `mode: snapshot` in `detail`
  — the legal *degraded* form, reported as such, never silently.
- **`UNVERIFIABLE (<why>)` rows are emitted, never dropped** — they count in the denominator so shrinkage
  is visible. The store-type and static-type packs ship `UNVERIFIABLE` by default; a wrong check that
  silently passes is worse than a stated gap.
- **The exclusion set is data** in the script (a list with the ruling's `D-NNN` beside it), applied to the
  DEV baseline, so the runner and a reader see what was excluded and why.
- **Read-only against the target.** A row that would mutate the deployed service is written as
  `UNVERIFIABLE (mutating — needs a scoped payload + the operator's go)`, never executed.
- `--json` prints the row list; `--self-check` runs the FREEZE CHECKLIST (header parses · every function
  returns the row shape · every `UNVERIFIABLE` carries a why · the exclusion list names a ruling) and
  exits non-zero on any miss.

## Phase 3 — Features cross-check `[anywhere]`

`FEATURES.md` is prose and cannot be derived, so it is cross-checked instead: **every derived route maps
to a shipped feature row, and every shipped feature row to a route.** **Walk EVERY table in the file, and
derive each table's status rule from ITS OWN header** — a `Status` column when present (a `✅ Shipped`-prefixed
cell is shipped; variants like `✅ Shipped (sandbox)` count), else a non-empty `Endpoint / Module` cell (the
scaffold template carries no status column at all). Do not assume a vocabulary and do not stop at the first
table: measured on a real project, the FIRST table's header was `Feature | Description | Module` with no
status cell, a literal-word grep returned 0, and the shipped rows (37, `✅ Shipped`) lived in a LATER table. **A route with no feature row, or a feature row with no route, is
a FINDING** in the report and a row in the contract (`L2_features_crosscheck`, expected 0 unmatched) —
that is what makes an under-declared inventory detectable rather than a smaller denominator.

## Phase 4 — Converge `[anywhere]` (the self-audit LOOP — iterate to a no-op)

Run repeated passes until one demonstrably-thorough pass makes zero edits to the script (Termination
contract). Each pass checks ALL of: **corpus coverage** (a row per applicable Layer 1–4 + pack check,
`UNVERIFIABLE` where it must be) · **derived denominators** (every `expected` traces to a Phase-1 command
and count) · **features cross-check** (both directions) · **executability** (`--json` runs; `--self-check`
green) · **exclusions** (each names its ruling) · **red-seen** (Phase 5's table complete) · **docs** (the
fleet-AI sections say what the rows assert). List what you re-read and what changed, then run one MORE
pass.

## Phase 5 — SEE EVERY ROW RED `[anywhere]`

*A check that cannot fail is a defect.* Before freezing, prove each row can fail:

1. Run the contract against DEV — expected: every derived row `match: True`, every `UNVERIFIABLE` row
   `match: None` with its why.
2. For each row CLASS, break DEV deliberately and re-run: drop a table's rows for a state row · rename an
   env key for the env row · stop the scheduler for the jobs row · remove a route for the routes row ·
   detach a service for the services row. **Each targeted row must report `match: False`** (or, for a
   raising comparator, `match: None` **with `compare_error` set** — that is fail-closed, not green).
   Restore DEV after each.
3. A row that cannot be made to fail is REWRITTEN, or marked `UNVERIFIABLE (cannot be seen red: <why>)`.
4. Paste the red table into the report: `row · how DEV was broken · result`. **A contract with no red
   table is DRAFT** whatever its header says.

## Phase 6 — Freeze + wire the truth `[anywhere]`

- **The freeze (and every re-freeze bump) is a Status flip — mint its `docs/DECISIONS.md` row in the SAME
  change** (classify at mint; a contract freeze is normally reversible-by-re-freeze).
- Set the header: `Status: FROZEN · Version: v<N> · Date · Mode`, freeze rule verbatim. **This header write
  is a post-convergence action, exempt from the no-op rule** — measured on the body, not the flip.
- **Refresh the fleet-AI sections of `docs/DEPLOYMENT.md` and `docs/OPERATIONS.md`** (D-065) — the
  services/jobs/env/dependency inventory Phase 1 derived IS the content those sections owe. Touch ONLY the
  sentinel-marked fleet-AI sections the template seeds; the project's own runbook prose is theirs.
  ⚠️ **HAZARD — derive these from CODE + SPEC + DEV, never from PROD.** *"prod has 0 companies, therefore
  document 0 companies"* makes an empty-database certification self-consistent and still wrong. The docs
  declare what SHOULD be true; the verify run reports what IS; the gap between them is the product.
- **Gate coupling, stated:** a change to compose services, the scheduler, the `os.getenv` set or the
  schema head without a Version bump is drift the runner will surface as a `match: False` on the next
  verify. No enforcement check grades this header today — that is a deliberate, recorded deferral
  (`docs/STRATEGIC_BACKLOG.md`), not an oversight.

## Phase 7 — Hand off `[anywhere]`

- **Mode A / B:** the contract is `FROZEN` → **`/fabrik-release`**, whose VPS-path precondition reads this
  header and BLOCKS on `DRAFT`. State this and stop.
- **Mode C:** stop at the filled stub, `Status: DRAFT`, and say which rows await code.
- **On a version BUMP:** the Re-freeze close-out below names what the next `/fabrik-deploy-verify` must
  re-run.

{{include:questionbar}}
## Guardrails — never
- Derive a row, a count or a doc section from PROD — the deployed state is the thing under test.
- Drop a row you cannot assert — emit it `UNVERIFIABLE (<why>)`; a shrunk denominator hides the gap.
- Freeze on a pass whose reconciliation made edits, or on a contract with no red table.
- Invent a check with no corpus id, or read `match: None` as agreement anywhere.
- Execute a mutating row, or read PROD data, from this command — it authors; `/fabrik-deploy-verify` runs.
- Hand off to `/fabrik-release` while the header is `DRAFT`.

## Re-freeze close-out (runs ONLY when this run was a version bump N→N+1 on an already-FROZEN contract)

1. **Diff the script against its pre-run version** (`git diff HEAD -- scripts/verify_prod_parity.py`)
   and extract the changed row ids and expected values.
2. **Emit a Downstream impact table**: `changed row → what the next verify must re-run → why`. Zero
   changed rows is a stated result, never an omitted one.
3. **The NEXT line becomes the owed re-verify** when the impact is non-empty: `/fabrik-deploy-verify`
   against the bumped Version, with the changed rows named as its arguments.

{{include:subagents-core}}
## Output (always, last thing)

```
DEPLOY-CHECKLIST: <project> · type <scaffold type> · Mode <A|B|C> · contract v<N>
DENOMINATORS: routes <n> (via <cmd>) · services <n>+<sidecars> · env keys <n> · jobs <n> | UNVERIFIABLE (<why>) · schema <head> | UNVERIFIABLE (<why>)
ROWS: <N> total — <n> derived / <n> snapshot / <n> UNVERIFIABLE / <n> not obligated
RED-SEEN: <n> of <N> asserting rows proven able to fail · <n> cannot-be-seen-red (listed)
FEATURES: <n> routes ↔ <n> shipped rows · <n> unmatched (FINDINGS listed)
EXCLUSIONS: <n> items, rulings <D-NNN, …>
DOCS: DEPLOYMENT.md + OPERATIONS.md fleet-AI sections refreshed from CODE + SPEC + DEV
STATUS: FROZEN v<N> | DRAFT (<why>)
```

Next command: `/fabrik-release` — its VPS-path precondition reads the `FROZEN` header. On a version BUMP
with downstream impact: `/fabrik-deploy-verify` re-run against the bumped contract, changed rows named.

```
/fabrik-features REFRESH  →  /fabrik-deploy-checklist (FREEZE)  →  /fabrik-release (precondition: FROZEN)  →  deploy triad  →  /fabrik-deploy-verify (consumes)
```

**HARD GATE: no `/fabrik-release` READY verdict and no `DEPLOY CONFIRMED` against a contract that is still
`DRAFT`.** A contract-less or unfrozen project reaches `UNVERIFIED` at verify time — a terminal verdict that
is not success — and `UNVERIFIED` is the signal to run this command.

**Where this runs:** project-side, in the project's own repo (cwd) — every phase is `[anywhere]`. The
contract derives from CODE + SPEC + DEV; **PROD is never read by this command** (deriving a declaration
from the deployed state launders drift into documentation). Nothing here needs fleet SSH.

{{include:run-record}}
{{include:term-edit}}
{{include:grounding-artifact}}
{{include:injection}}

## Phase 0 — Establish MODE + scope `[anywhere]`

State the mode and why:

- **Mode A — spec-driven (new work).** A CONVERGED `/fabrik-spec` design is `$ARGUMENTS`; its inventory
  (routes, jobs, state, external deps) seeds the rows. Phase 1 still reconciles every row against what
  the code actually registers — the spec is the source of INTENT, the code of FACT.
- **Mode B — reverse-generate (an existing, shipped project).** No spec; the rows are derived from the
  code, compose, scheduler and DEV. This is how the deployable repos get a contract — run it in each.
- **Mode C — fresh (no code worth deriving from yet).** Fill the seeded stub minimally (header + the
  Layer-1 identity rows, which need only git) so the project has the frozen skeleton to grow into.

Inputs — read them, name them: `project.yaml::type` (the live registry is `scaffold.py::SCAFFOLD_TYPES`)
→ the per-type pack of rows; `specs/services/<id>.yaml` `shape:` → the Layer-3 obligations (a flag that is
`false` makes its row `not obligated`, never absent); `docs/DECISIONS.md` → every ruling about what ships
and what does not (the exclusion set lives here — e.g. *"everything ships EXCEPT sales/activities/invoices
history"*; the ruling is the row's WHAT cell — 4th column, after `id | when | who` — quote it verbatim
beside the exclusion list); `docs/FEATURES.md` → the cross-check inventory; `docs/DEPLOYMENT.md` + `docs/OPERATIONS.md` →
the fleet-AI sections this run refreshes.

**Starting state + check-before-create:** the scaffolder seeds `scripts/verify_prod_parity.py` as a
`Status: DRAFT` stub that **exits 2** — an unfilled contract fails closed. **A DRAFT stub is meant to be
edited through — its existence is NOT a STOP.** Only a `Status: FROZEN` header is a STOP: say so, and on
the operator's word proceed as a **re-freeze** — bump `Version`, never a silent overwrite.

Store types (`mobile-app`, `chrome-extension`, `office-extension`, `desktop-app`) have no VPS: their
contract is the **provenance pack only** (submitted artifact ↔ tested SHA, store review state) — say so
and skip Layers 2–4. `wordpress` runs no fabrik command (out of fabrik).

## Phase 1 — Derive the denominators `[anywhere]`

**A denominator is DERIVED wherever derivable; where it must be declared it is CROSS-CHECKED against a
derived proxy.** Each source below is authoritative; the prose next to it is never the sole basis.

| denominator | derive from (authoritative) | never from | when underivable |
|---|---|---|---|
| routes | the app's OWN route table — import the app and read `app.routes` (or the running DEV `/openapi.json`), **then subtract the framework's routes** (`/`, `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect`) and state BOTH counts (`total / application`). ⚠️ Never a `grep include_router`: a router mounted as a composed `v1_router` carries its prefix on the parent, and the grep returns nothing (measured on a real project — 8 sub-routers, 0 prefixes by grep) | `FEATURES.md` prose | `UNVERIFIABLE (no introspection: <why>)` |
| services | `yaml.safe_load(compose)["services"]` ∪ the registrar-injected sidecars the `shape:` flags imply (a `watchdog` container appears in no compose file). ⚠️ Never an indentation regex — it counts `volumes:`/`networks:` keys as services (measured: 6 for 4) | compose read by eye | — (always derivable) |
| env keys | `os.getenv(...)`/`os.environ[...]` names over `src/` (every key, de-duplicated) | `.env.example` alone | — |
| scheduled jobs | the live scheduler: `ir_cron` rows for a Tryton stack, Beat/APScheduler registrations for a scaffolded API, `crontab -l` for a host job | `RESILIENCE.md` §7 | `UNVERIFIABLE (scheduler not introspectable from here: <why>)` |
| schema head | the type's OWN mechanism: `alembic heads` for a scaffolded API; module state (`ir_module`) for trytond; a migrations dir count for node | `db/schema.sql`, a doc | `UNVERIFIABLE (no migration tool: <why>)` — never a guess |
| state baseline | **DEV minus the declared exclusion set** — row counts, reference data, translations, filestore counts measured in DEV; exclusions from `docs/DECISIONS.md` (fixture companies, test users, history the ruling excludes) | PROD (see the hazard rule) | a missing exclusion ruling is the one thing to RAISE (§ Question bar) |
| features | not derivable — `FEATURES.md` is prose | — | cross-checked in Phase 3, never trusted alone |

Record every derivation as the COMMAND that produced it and its COUNT (`routes: 23 via app.routes` ·
`services: 4 + 1 sidecar` · `env keys: 32 distinct over 49 sites`). A count without its command is a
claim.

**Parallelism — the default with 2+ derivation surfaces:** one pool grounder per surface (routes · jobs ·
env · services · schema) per § Subagents; the exclusion-set judgement and every DEV measurement stay
native — they read the project's own environment.

## Phase 2 — Emit the contract `[anywhere]`

Write `scripts/verify_prod_parity.py` to the seeded template's shape:

- **Header block** (machine-readable, the runner and the release precondition parse it):
  `# Status: DRAFT | FROZEN · Version: v<N> · Date: YYYY-MM-DD · Mode: A | B | C` and the freeze rule
  verbatim: *"Frozen — no agent adds, removes or re-derives a row not listed here. Any change = bump Version
  + re-freeze via `/fabrik-deploy-checklist`."*
- **One function per corpus row**, named by its corpus id (`L1_identity_sha`, `L2_routes`,
  `L2_state_companies`, `L3_postgres`, …), returning the `health-probe` comparison row shape —
  `{system, status, detail, expected, actual, match, compare_error}` — with `system` = the corpus id.
  `expected` is DERIVED at run time where Phase 1 derived it (**snapshot values are a cache of a
  derivation; ship the derivation**); a row that can only snapshot is marked `mode: snapshot` in `detail`
  — the legal *degraded* form, reported as such, never silently.
- **`UNVERIFIABLE (<why>)` rows are emitted, never dropped** — they count in the denominator so shrinkage
  is visible. The store-type and static-type packs ship `UNVERIFIABLE` by default; a wrong check that
  silently passes is worse than a stated gap.
- **The exclusion set is data** in the script (a list with the ruling's `D-NNN` beside it), applied to the
  DEV baseline, so the runner and a reader see what was excluded and why.
- **Read-only against the target.** A row that would mutate the deployed service is written as
  `UNVERIFIABLE (mutating — needs a scoped payload + the operator's go)`, never executed.
- `--json` prints the row list; `--self-check` runs the FREEZE CHECKLIST (header parses · every function
  returns the row shape · every `UNVERIFIABLE` carries a why · the exclusion list names a ruling) and
  exits non-zero on any miss.

## Phase 3 — Features cross-check `[anywhere]`

`FEATURES.md` is prose and cannot be derived, so it is cross-checked instead: **every derived route maps
to a shipped feature row, and every shipped feature row to a route.** **Walk EVERY table in the file, and
derive each table's status rule from ITS OWN header** — a `Status` column when present (a `✅ Shipped`-prefixed
cell is shipped; variants like `✅ Shipped (sandbox)` count), else a non-empty `Endpoint / Module` cell (the
scaffold template carries no status column at all). Do not assume a vocabulary and do not stop at the first
table: measured on a real project, the FIRST table's header was `Feature | Description | Module` with no
status cell, a literal-word grep returned 0, and the shipped rows (37, `✅ Shipped`) lived in a LATER table. **A route with no feature row, or a feature row with no route, is
a FINDING** in the report and a row in the contract (`L2_features_crosscheck`, expected 0 unmatched) —
that is what makes an under-declared inventory detectable rather than a smaller denominator.

## Phase 4 — Converge `[anywhere]` (the self-audit LOOP — iterate to a no-op)

Run repeated passes until one demonstrably-thorough pass makes zero edits to the script (Termination
contract). Each pass checks ALL of: **corpus coverage** (a row per applicable Layer 1–4 + pack check,
`UNVERIFIABLE` where it must be) · **derived denominators** (every `expected` traces to a Phase-1 command
and count) · **features cross-check** (both directions) · **executability** (`--json` runs; `--self-check`
green) · **exclusions** (each names its ruling) · **red-seen** (Phase 5's table complete) · **docs** (the
fleet-AI sections say what the rows assert). List what you re-read and what changed, then run one MORE
pass.

## Phase 5 — SEE EVERY ROW RED `[anywhere]`

*A check that cannot fail is a defect.* Before freezing, prove each row can fail:

1. Run the contract against DEV — expected: every derived row `match: True`, every `UNVERIFIABLE` row
   `match: None` with its why.
2. For each row CLASS, break DEV deliberately and re-run: drop a table's rows for a state row · rename an
   env key for the env row · stop the scheduler for the jobs row · remove a route for the routes row ·
   detach a service for the services row. **Each targeted row must report `match: False`** (or, for a
   raising comparator, `match: None` **with `compare_error` set** — that is fail-closed, not green).
   Restore DEV after each.
3. A row that cannot be made to fail is REWRITTEN, or marked `UNVERIFIABLE (cannot be seen red: <why>)`.
4. Paste the red table into the report: `row · how DEV was broken · result`. **A contract with no red
   table is DRAFT** whatever its header says.

## Phase 6 — Freeze + wire the truth `[anywhere]`

- **The freeze (and every re-freeze bump) is a Status flip — mint its `docs/DECISIONS.md` row in the SAME
  change** (classify at mint; a contract freeze is normally reversible-by-re-freeze).
- Set the header: `Status: FROZEN · Version: v<N> · Date · Mode`, freeze rule verbatim. **This header write
  is a post-convergence action, exempt from the no-op rule** — measured on the body, not the flip.
- **Refresh the fleet-AI sections of `docs/DEPLOYMENT.md` and `docs/OPERATIONS.md`** (D-065) — the
  services/jobs/env/dependency inventory Phase 1 derived IS the content those sections owe. Touch ONLY the
  sentinel-marked fleet-AI sections the template seeds; the project's own runbook prose is theirs.
  ⚠️ **HAZARD — derive these from CODE + SPEC + DEV, never from PROD.** *"prod has 0 companies, therefore
  document 0 companies"* makes an empty-database certification self-consistent and still wrong. The docs
  declare what SHOULD be true; the verify run reports what IS; the gap between them is the product.
- **Gate coupling, stated:** a change to compose services, the scheduler, the `os.getenv` set or the
  schema head without a Version bump is drift the runner will surface as a `match: False` on the next
  verify. No enforcement check grades this header today — that is a deliberate, recorded deferral
  (`docs/STRATEGIC_BACKLOG.md`), not an oversight.

## Phase 7 — Hand off `[anywhere]`

- **Mode A / B:** the contract is `FROZEN` → **`/fabrik-release`**, whose VPS-path precondition reads this
  header and BLOCKS on `DRAFT`. State this and stop.
- **Mode C:** stop at the filled stub, `Status: DRAFT`, and say which rows await code.
- **On a version BUMP:** the Re-freeze close-out below names what the next `/fabrik-deploy-verify` must
  re-run.

{{include:questionbar}}
## Guardrails — never
- Derive a row, a count or a doc section from PROD — the deployed state is the thing under test.
- Drop a row you cannot assert — emit it `UNVERIFIABLE (<why>)`; a shrunk denominator hides the gap.
- Freeze on a pass whose reconciliation made edits, or on a contract with no red table.
- Invent a check with no corpus id, or read `match: None` as agreement anywhere.
- Execute a mutating row, or read PROD data, from this command — it authors; `/fabrik-deploy-verify` runs.
- Hand off to `/fabrik-release` while the header is `DRAFT`.

## Re-freeze close-out (runs ONLY when this run was a version bump N→N+1 on an already-FROZEN contract)

1. **Diff the script against its pre-run version** (`git diff HEAD -- scripts/verify_prod_parity.py`)
   and extract the changed row ids and expected values.
2. **Emit a Downstream impact table**: `changed row → what the next verify must re-run → why`. Zero
   changed rows is a stated result, never an omitted one.
3. **The NEXT line becomes the owed re-verify** when the impact is non-empty: `/fabrik-deploy-verify`
   against the bumped Version, with the changed rows named as its arguments.

{{include:subagents-core}}
## Output (always, last thing)

```
DEPLOY-CHECKLIST: <project> · type <scaffold type> · Mode <A|B|C> · contract v<N>
DENOMINATORS: routes <n> (via <cmd>) · services <n>+<sidecars> · env keys <n> · jobs <n> | UNVERIFIABLE (<why>) · schema <head> | UNVERIFIABLE (<why>)
ROWS: <N> total — <n> derived / <n> snapshot / <n> UNVERIFIABLE / <n> not obligated
RED-SEEN: <n> of <N> asserting rows proven able to fail · <n> cannot-be-seen-red (listed)
FEATURES: <n> routes ↔ <n> shipped rows · <n> unmatched (FINDINGS listed)
EXCLUSIONS: <n> items, rulings <D-NNN, …>
DOCS: DEPLOYMENT.md + OPERATIONS.md fleet-AI sections refreshed from CODE + SPEC + DEV
STATUS: FROZEN v<N> | DRAFT (<why>)
```

Next command: `/fabrik-release` — its VPS-path precondition reads the `FROZEN` header. On a version BUMP
with downstream impact: `/fabrik-deploy-verify` re-run against the bumped contract, changed rows named.

```

