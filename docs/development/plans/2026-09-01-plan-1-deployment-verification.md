# Plan 1 — Deployment Verification Contract (hub build)

Status: **DRAFT** — the spec is **CONVERGED and APPROVED** (J5 quiet at md5 `cdb48812`; approval D-077). On the
same approval the operator directed *"study the structure, enforcement, loop, convergence and all aspects of
our existing commands to use same approach and update the plan"* — so this revision RE-AUTHORS Phases A–C to
the command-corpus conventions measured in § Corpus conformance contract, and it owes `/fabrik-plan-review`
before execution: a plan cannot self-grade a rewrite of its own phases.
Date: 2026-09-01 · amended 2026-09-02 (fabrik-lib binding · row-shape split · corpus conformance)
Spec: `docs/superpowers/specs/2026-09-01-deployment-verification-contract-design.md` (status per its header — read it, do not trust this line)
Scope: **`/opt/fabrik` only** — 10 file groups, two of them FLEET-SYNCED. Routed feature-scale (spec defect 15: the epic verdict was wrong).

## Why this plan exists

I certified tryton-crm `DEPLOY CONFIRMED LIVE` with every check green while production held **0 of its
760 companies**. Liveness checks cannot fail on a missing product, because nothing declared what the
product should contain.

## File Scope (exhaustive — nothing outside this list)

| # | path | change |
|---|---|---|
| 1 | `commands/_sources/fabrik-deploy-checklist.md` | **NEW** — the project-side authoring command, built to the anatomy in § Corpus conformance |
| 2 | `commands/_sources/fabrik-deploy-verify.md` | rewrite (216 lines today) — keeps its verify-command anatomy, gains Layer 1 + derived Layer 3 + blocking contract-driven parity |
| 3 | `commands/assemble_commands.py` | **registration, not logic**: `NEXT` entries (`:49`) for the new command + retargets for `fabrik-features`/`fabrik-deploy-verify`; an `EXTRACT` row (`:331`) and a `PARAMS` block (`:394`) for the new command; the runner's `PARAMS` examples (`:556`) gain parity-shaped examples |
| 4 | `commands/_sources/fabrik-release.md` | one precondition paragraph on the VPS path (`:76-86`): a parity contract that is not `FROZEN` is `BLOCKED: parity contract DRAFT → /fabrik-deploy-checklist` — the mirror of its existing certification-handoff precondition (`:20-35`) |
| 5 | `CLAUDE.md:333` + `templates/governance/CLAUDE.md:339` | the § Pipeline flow line names the new command between `/fabrik-features` REFRESH and certification/release. ⚠️ **`templates/governance/CLAUDE.md` is FLEET-SYNCED** — the post-commit governance-sync distributes it to ~46 repos |
| 6 | `templates/scaffold/scripts/verify_prod_parity.py` (**NEW** template) + `src/fabrik/scaffold.py` (`SCRIPT_FILES` + the copy loop at `:1127`) + `templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md` / `OPERATIONS_TEMPLATE.md` (fleet-AI sections, D-065) | born-compliant seeding on the `scaffold.py:285` precedent |
| 7 | `tests/test_scaffold_deploy_contract.py` | **NEW** — Phase C guards (stub exits non-zero; docusaurus does not publish the doc templates' new sections) |
| 8 | `tests/test_check_command_corpus.py` (extend) | Phase A/B guards — the rendered commands carry the required sections; ⚠️ the earlier File Scope named `tests/test_command_corpus.py`, **which does not exist** (`ls tests/ \| grep -i corpus` → only `test_check_command_corpus.py`) |
| 9 | `tests/test_deploy_verify_verdict.py` | **NEW** — Phase A step 7: the EXECUTED verdict-algebra check (four row shapes + DOWN/mismatch co-occurrence), watched-fail-first |
| 10 | `capabilities.json` + `docs/CAPABILITIES.md` + `INDEX.md` | **REGENERATED / doc-sync**, never hand-edited: `scripts/generate_capability_index.py` enumerates `commands/_sources/*.md` (`:461`) so a new command changes both; `INDEX.md` rows for every new file (Doc Sync Matrix) |

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
| termination — authoring | `{{include:term-edit}}` via an `EXTRACT` row + `PARAMS` tokens `ARTIFACT · DONE_ACT · DONE_WORD · AXES · EXEMPT_NOTE`: pass shape 1-wide + k-scoped + 1-wide, `method:` column, ≥1 `method: re-derivation` row, md5 anti-cheat, `new:` counts, stall breaker, probe duty (`$ ` fences) | `_fragments/term-edit.md`, `assemble_commands.py:331-345` (EXTRACT), `:394-` (PARAMS) |
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
entry (`assemble_commands.py:49`, the successor line the wrapper prints), (c) an `EXTRACT` row naming which
fragment replaces which section (`:331`), (d) a `PARAMS` block with every token the included fragments
carry (a token left unfilled **ships literally** — `:248` guards the wrappers, `:748` guards bodies),
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
   REFRESH branch to name `/fabrik-deploy-checklist` before certification; an `EXTRACT` row
   `[("termination","term-edit",None),("grounding","grounding-artifact",None),("questionbar","questionbar",None),("subagents","subagents-core",None)]`;
   a `PARAMS` block — `term-edit`: `ARTIFACT` "parity contract", `DONE_ACT` "flip `Status: DRAFT → FROZEN`",
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
