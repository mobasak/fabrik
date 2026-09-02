# Plan 1 — Deployment Verification Contract (hub build)

Status: **DRAFT** (re-opened 2026-09-02 by `/fabrik-plan-review` R6: fabrik-lib BUILT AND SHIPPED the comparison
axis this plan binds to — `01M1GQR1R3TD9AE68YVSP0DT51`, their `e48ba19c`/`53c098c2`, 75 tests — so every line that
described their build as pending, and the absence of any vendoring step, is now wrong; the R1–R5 CONVERGED stamp at
md5 `51edd8a4` (D-080) is VOID for this run and must be re-earned). Spec CONVERGED (J5) and APPROVED (D-077).
Date: 2026-09-01 · amended 2026-09-02 (fabrik-lib binding · row-shape split · corpus conformance)
Spec: `docs/superpowers/specs/2026-09-01-deployment-verification-contract-design.md` (status per its header — read it, do not trust this line)
Scope: **`/opt/fabrik` only** — 12 file groups, three of them FLEET-SYNCED. Execution order **C → A → B → D** (see Phase B). Routed feature-scale (spec defect 15: the epic verdict was wrong).

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
| 10 | `docs/reference/deployment-verification.md` (**NEW**) | the contract is a NEW SUBSYSTEM (two commands, a seeded artifact, a verdict algebra) — evaluation-checklist item 64 owes it its OWN reference doc (grep/`ls` first: none exists); describes the CURRENT architecture, links the spec |
| 11 | `capabilities.json` + `docs/CAPABILITIES.md` | **REGENERATED**, never hand-edited: `scripts/generate_capability_index.py` enumerates `commands/_sources/*.md` (`:461`) so a new command changes both |
| 12 | `libs/health_probe/` (**NEW** at the hub — `health_probe.py` + `fingerprint.py`, a byte-for-byte copy of `/opt/fabrik-lib/health-probe/` at their `e48ba19c` (module) / `53c098c2` (post-ship review), each file headed `# VENDORED-FROM fabrik-lib health-probe @ <sha>`) + `scripts/fabrik_synced_manifest.py::VENDORED_DIRS` (`:115` — append `"libs/health_probe"`) | **VENDOR AS SHIPPED** (spec ladder: VENDOR + ENHANCE; fabrik-lib's rule: *"Vendor, don't depend"*, README § How to vendor). `VENDORED_DIRS` is what BOTH the scaffolder (`scaffold.py::_fabrik_vendored_dirs`, `:552-562`, copies at `:1168-1173`) and the fleet sync (`fabrik_synced_manifest.py:288-289`) read, so one entry seeds every NEW project and distributes to every EXISTING one — the per-project onboarding row below no longer has to vendor anything by hand. ⚠️ **FLEET-SYNCED**: the manifest is a governance-sync trigger surface and the dir syncs recursively to ~46 repos; the module imports `httpx` at load (`health_probe.py:50`) and probes need `psycopg2-binary`/`redis` (their `requirements.txt`), so the parity stub imports it LAZILY inside the Layer-3/4 rows and never at module top — a static/store project that skips Layers 2–4 never loads it |

**Governance files are deliberately NOT File Scope** — `CHANGELOG.md`, `INDEX.md`, `docs/README.md`, `docs/DECISIONS.md`, `docs/STRATEGIC_BACKLOG.md` (the live list is `scripts/enforcement/check_plan_tickets.py::GOVERNANCE_FILES`): they are shared-append surfaces every concurrent plan touches, so they are Phase D doc-sync STEPS, never owned paths. **Project-side outputs are not hub scope either:** `scripts/verify_prod_parity.py`, `docs/DEPLOYMENT.md`, `docs/OPERATIONS.md` are what `/fabrik-deploy-checklist` writes IN THE PROJECT THAT RUNS IT — this plan ships the command and the seeded template, never those files.

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

- **fabrik-lib `health-probe` — the comparison axis is THEIRS, and it has SHIPPED.** Filed
  `01M1ESR5KJW5Z1EE2YE55MBTE8`; they specced (`5f5b2e6f`), then **BUILT AND SHIPPED** it (`01M1GQR1R3TD9AE68YVSP0DT51`:
  their `9f1c657a`, `e48ba19c`, `be1026d2`, `b3162f0d`, post-ship review `53c098c2`; D-029; 75 tests green, re-run
  here 2026-09-02). ⚠️ **The FALLBACK is RETIRED** (spec Amendment 2) **and so is the "implement the shape locally
  until their build lands" clause** — there is no local shim to write and none to delete later: File Scope row 12
  VENDORS the shipped module as-is and Phase A consumes it. What stays out of scope is the module's FUTURE: a
  fabrik-lib bump is re-vendored by replacing `libs/health_probe/` and its `VENDORED-FROM` sha (a routine sync, not
  this plan). Interface, verified at their HEAD by execution: `compare(name, expected, actual, *, comparator=None)
  -> dict[str, object]`, tri-state `match` with `compare_error` on a raising comparator, `run_all_checks() ->
  list[dict[str, object]]`, `cli(..., mismatch_exit=2, strict=False)` with `mismatch_exit` VALIDATED to `2..255`
  (`health_probe.py:521-544` — `0` reports success, `1` collides with the liveness exit, `≥256` wraps to `0` on POSIX).
- **Per-project onboarding (27 deployable repos)** — self-serve; each project's own agent runs the new
  command in its own repo. Cross-repo commits are a HARD STOP, so this is not mine to execute.

## Corpus conformance contract — MEASURED from the existing commands, binding on Phases A–C

The operator's directive on approval: *"use same approach"*. Every rule below was read from the machinery
this run, not recalled; the anchors are what `/fabrik-plan-review` re-derives.

**1. Anatomy of a source command** (`commands/_sources/fabrik-data-contract.md` as the authoring template,
`commands/_sources/fabrik-deploy-verify.md` as the verify template; `commands/assemble_commands.py` renders `_sources` + `_fragments`
→ `~/.claude/commands/*.md` and a thin `SKILL.md` wrapper per command via `_emit_skill`):

| element | how the corpus does it | anchor |
|---|---|---|
| frontmatter | `description:` carries **TRIGGER — EN / TR phrases, SKIP (→ the sibling that owns the near-miss), Stage**; `argument-hint:` | `commands/_sources/fabrik-features.md:1-3`, `commands/_sources/fabrik-deploy-verify.md:1-3` |
| intro | what it produces, the seam it sits in as a fenced pipeline line, and the **HARD GATE** ("no plan builds against a `DRAFT` contract") | `commands/_sources/fabrik-data-contract.md:7-19` |
| run record | `{{include:run-record}}` FIRST; `--phases` is DERIVED from `## Phase N —` headings (`_phase_count`, falls back to section count, never 0) | `commands/assemble_commands.py::_phase_count`, `commands/_fragments/run-record.md` tokens `COMMAND`/`PHASES` |
| termination — authoring | `{{include:term-edit}}` + `PARAMS` tokens `ARTIFACT · DONE_ACT · DONE_WORD · AXES · EXEMPT_NOTE` (render-time; no EXTRACT row — that table is the retired migration path): pass shape 1-wide + k-scoped + 1-wide, `method:` column, ≥1 `method: re-derivation` row, md5 anti-cheat, `new:` counts, stall breaker, probe duty (`$ ` fences) | `commands/_fragments/term-edit.md`, `commands/assemble_commands.py:394-` (PARAMS), `:734` (lookup), `:748` (the leftover-token refusal) |
| termination — verify | hand-written **token families** `PASS · FAIL (+route) · INCONCLUSIVE · NOT-RUN (<cause>)`, "routes are asks, never actions", early-stop on a shared root cause with `NOT-RUN` rows | `commands/_sources/fabrik-deploy-verify.md:24-43` |
| grounding gate | `{{include:grounding-artifact}}` with `PARAMS` `SUBJECT`/`EXAMPLES` — every claim at a freshly-read `path:line`; universal/negative claims need the enumerating command | `commands/_fragments/grounding-artifact.md`, `commands/assemble_commands.py:556` |
| phases | `## Phase N — <title>` headings; each phase tagged **`[anywhere]`** or **`[hub-side]`** (where it may run) | `commands/_sources/fabrik-deploy-verify.md:73,108,126,160,168,180` |
| modes | Phase 0 declares **Mode A (spec-driven) / B (reverse-generate from what exists) / C (fresh stub)** and states which and why; the seeded DRAFT stub is "meant to be edited through — NOT a STOP"; a `FROZEN` artifact → STOP, then re-freeze with a Version bump | `commands/_sources/fabrik-data-contract.md:22-54` |
| converge loop | a self-audit phase listing the axes; each pass records what it re-read and changed; terminates ONLY on an edit-free md5-verified no-op | `commands/_sources/fabrik-data-contract.md:142-162`, `commands/_sources/fabrik-features.md:88-104` |
| freeze | Status flip + **`docs/DECISIONS.md` row in the SAME change**; header `Status · Version · Date · Mode` + the freeze rule verbatim; the flip is the exempt post-convergence write; a **gate coupling** named (which check WARNs on drift) | `commands/_sources/fabrik-data-contract.md:164-181` |
| hand-off | the NEXT rule per mode; on a version BUMP a **Downstream impact** table and the NEXT line becomes the owed re-freeze | `fabrik-data-contract.md:183-190, 206-225` |
| question bar | `{{include:questionbar}}` with tokens `CHANGES_WHAT · RESOLVE_FROM · NEVER_FOR · DO_RAISE` | `commands/_fragments/questionbar.md`, `commands/assemble_commands.py` PARAMS |
| guardrails | `## Guardrails — never` — a short negative-space list | `commands/_sources/fabrik-data-contract.md:192-204` |
| subagents | `{{include:subagents-core}}` with `HEADLINE · TASK_TYPE · PROJECT · FLOOR · EXTRA`; pool-default for gradeable fan-out + `set_quality`; `_floor()` when a review needs native Opus | `commands/assemble_commands.py::_floor`, PARAMS |
| output | `## Output (always, last thing)` — a FIXED fenced block with a row vocabulary, then `Next command: …` | `commands/_sources/fabrik-deploy-verify.md:199-216` |
| close-out | `close-feedback` is **auto-appended to every rendered command** — never written into a source | `commands/assemble_commands.py:27-29`, `tests/test_close_feedback_autoappend.py` |
| untrusted input | `{{include:injection}}` where the command reads fetched/third-party content — the checklist reads project docs (D-065) and DEV state, so it declares them DATA | `commands/_fragments/injection.md` |
| prompt authoring | Parts A–C of `docs/reference/MD/ai-prompt-templates.md` bind: B.2 termination, B.3 evidence-before-assertion, B.4 `path:line`, B.5 question bar, B.9 honest reporting, B.11 untrusted input | `docs/reference/MD/ai-prompt-templates.md:256-317` |

**2. Registration** — a new command is not "a file in `_sources/`": it is (a) the source, (b) a `NEXT`
entry (`commands/assemble_commands.py:49`, the successor line the wrapper prints), (c) a `PARAMS` block with every token the included fragments carry — **a token left unfilled does not ship literally, it REFUSES the whole render** (`:748` collects `unresolved […]` into `errs`; `:248` is the same guard for orchestrator wrappers), which is what makes a missing block loud rather than a silent defect; `EXTRACT` (`:331`) is NOT part of registration,
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
   row's `{system,status,detail,expected,actual,match,compare_error}`. **The rows come from the VENDORED
   module** (`libs/health_probe/health_probe.py`, File Scope row 12): `run_all_checks() -> list[dict[str, object]]`
   (their `:492-500` — a type-level widening, runtime unchanged), so every value is `object` to a type-checker:
   the runner reads the row SHAPE by key presence (`"expected" in row and "actual" in row`), the tri-state as
   `row.get("match")` split `is True` / `is False` / `is None`, and coerces `str(row["system"])`/`str(row["status"])`
   before any string comparison. ⚠️ The hub gate's mypy EXCLUDES `templates/`, `scripts/` and `tests/`
   (`pyproject.toml:83-86`), so no type-checker guards this at the hub — the executed test in step 7 does.
5. **Implement the verdict algebra** — `UP` (Layers 1+3) / `COMPLETE` (Layer 2 + parity) / `RUNNING` (Layer
   4) separately failable; `CONFIRMED` requires all three; **`UNVERIFIED`** when no FROZEN contract;
   `not obligated` (a `shape:` exemption) distinct from `not checked` (an `UNVERIFIABLE (<why>)` row);
   **`match` read BY ROW SHAPE, never by value** (spec § Verdict algebra, the one-rule table): `expected`+
   `actual`+`None` = attempted-unresolved ⇒ **FAIL CLOSED**, denies `CONFIRMED`, exit 2 — never "not
   checked"; a row with no `expected`/`actual` is not a parity row (outside the parity denominator, judged
   under `UP`); `True` = numerator; `False` = denies `CONFIRMED`, exit 2. **Precedence `1 → 2 → 0`**
   (liveness wins) never upgrades a verdict.
6. **Always pass `strict=True`** to the vendored `health-probe` CLI (`cli(..., strict=False)` is still their
   default at `:560-561`). Proven at `health_probe.py:448`
   (`critical = critical or set()`) with `:478`/`:481`: `critical` undeclared ⇒ every probe DOWN still
   `sys.exit(0)` while printing `DOWN:`. A runner that omits it is fail-open on liveness — reproduced by three
   independent builds (fabrik-lib runs 3, 6 and their plan-review). **`mismatch_exit` stays the default `2`**
   — their `_validated_mismatch_exit` (`:521-544`) refuses `0`, `1` and `≥256` (executed here: `2`/`255`
   accepted, `0`/`1`/`256` raise `ValueError`), so the fail-open shapes the spec's Amendment 3 hunted are
   unreachable through the CLI; the runner never passes anything else.
7. **EXECUTE the verdict algebra before calling it built** (fabrik-lib's D-026): ship
   `tests/test_deploy_verify_verdict.py` feeding the algebra the four row shapes (liveness-only/`None` ·
   `expected`+`actual`+`None` · `+False` · `+True`) plus a critical-DOWN co-occurring with a mismatch;
   assert fail-closed on attempted-unresolved, `CONFIRMED` denied by either condition independently,
   exit `1` over `2` never upgrading, a liveness-only row absent from the parity denominator. **The parity rows
   are PRODUCED by the vendored `compare()`, never hand-written** — `compare("companies", 3, 3)`, `compare(…, 3, 0)`
   and `compare(…, 3, None, comparator=<raises>)` are the three shapes, so the test binds to the SHIPPED row
   semantics (a raising comparator keeps `system` and sets `compare_error`, `match: None`) and breaks the day
   a re-vendor changes them. Reference: `verdict_algebra_shipped.py` in § Evidence (8/8 on shipped rows).
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

⚠️ **EXECUTION ORDER IS C → A → B → D, and B's registration lands in ONE commit** — proven by running
`check_command_corpus.audit()` over a scratch copy carrying the new source: it returned exactly four
problems, all *"`scripts/verify_prod_parity.py` does not exist"* (predicate 3 resolves every
`scripts/*.py` a source names against the repo and `templates/**`). **Phase A's rewritten runner cites that
same path** (its step 1 reads the contract header), so predicate 3 binds A as well as B: Phase C's template
must exist before EITHER gate runs — hence C first (plan-review pass 1 found the earlier "A → C → B → D"
would have reddened Phase A's own gate). Predicate 2 (every `/fabrik-x` a source names must resolve to a
real source) means the `NEXT` retargets, the `/fabrik-release` precondition and the pipeline line may only
be committed TOGETHER WITH or AFTER the new source — never before. Phases keep their letters (the ledger
cites them); the order of execution is what changes.

**Steps**
1. **Author `commands/_sources/fabrik-deploy-checklist.md`** with every element of § Corpus conformance 1,
   in this order:
   - frontmatter — `description:` **exactly as in Appendix A** (785 chars: TRIGGER — EN: *"author the deploy
     checklist"*, *"what must prod contain"*, *"freeze the parity contract"*; TR: *"deploy kontrol listesini yaz"*,
     *"prod'da ne olmalı"*; SKIP → `/fabrik-deploy-verify` · `/fabrik-data-contract` · `/fabrik-features`;
     `Stage: 6-release`). ⚠️ The composed skill description (`description` + *"Invoke for …"* + the `NEXT` line)
     must stay **under 1024 chars** — `assemble_commands.py::_emit_skill` REFUSES the render otherwise; the first
     draft composed to 1366 and was refused (plan-review pass R4 found this step still quoting that draft).
     `argument-hint:` the spec path (Mode A) or nothing (Mode B/C).
   - intro + the seam as a fenced line — `/fabrik-features REFRESH → /fabrik-deploy-checklist (FREEZE) →
     /fabrik-release (precondition: FROZEN) → deploy triad → /fabrik-deploy-verify (consumes)` — and the
     HARD GATE: **no `/fabrik-release` READY verdict and no `CONFIRMED` verify against a `DRAFT` contract**.
   - `{{include:run-record}}` · `{{include:term-edit}}` (its tokens via the `PARAMS` block in step 2) · `{{include:grounding-artifact}}` ·
     `{{include:injection}}` (project docs + DEV state are DATA).
   - `## Phase 0 — Establish MODE + scope` `[anywhere]`: Mode **A** spec-driven (the approved spec's inventory
     + `shape:`) · **B** reverse-generate (an existing deployed project — derive from code, compose,
     scheduler, `alembic heads`, DEV) · **C** fresh (fill the seeded stub minimally). Read `project.yaml::type`
     → the per-type pack (all 13 `SCAFFOLD_TYPES`; store types get the provenance rows only); read
     `specs/services/<id>.yaml` `shape:`; the seeded stub's header — `DRAFT` is edited through, **`FROZEN` →
     STOP, then re-freeze with a Version bump on the operator's word**.
   - `## Phase 1 — Derive the denominators` `[anywhere]`: routes from the STARTED app's `/openapi.json` minus
     the framework's paths (a flat `app.routes` read under-counted 3 vs 27 on tryton-crm) · jobs from the live
     scheduler/`ir_cron` · env keys from `os.getenv`/`os.environ` over `src/` · services from **a YAML parse of
     compose ∪ registrar-injected sidecars** (tryton-crm: 4 declared, 5 run; an indentation regex counted 6) ·
     schema head by the TYPE's own mechanism (`alembic heads` for a scaffolded API; `ir_module` for trytond;
     `UNVERIFIABLE (<why>)` when none) — never from `FEATURES.md`/`RESILIENCE.md`/`.env.example` prose. **DEV is the state baseline minus a declared
     exclusion set** (spec § three sources; D-017 is the worked example: 760 → 3 companies).
   - `## Phase 2 — Emit the contract` `[anywhere]`: write `scripts/verify_prod_parity.py` to the seeded
     template's shape — header block, one function per corpus row returning the `compare()` row shape
     (`{system,status,detail,expected,actual,match,compare_error}`) with the corpus id in `system`, `mode:
     derived|snapshot` per row (snapshot is the marked degraded mode, spec Q1), `UNVERIFIABLE (<why>)` rows
     emitted not dropped, the exclusion set as data.
   - `## Phase 3 — Features cross-check` `[anywhere]`: every derived route ↔ a shipped `FEATURES.md` row, both
     directions, **walking EVERY table and deriving each table's status rule from its own header** (a `✅ Shipped`-
     prefixed status cell, else a non-empty `Endpoint / Module` cell — a literal-word grep read 0 of 88 on
     tryton-crm); either direction unmatched is a FINDING in the report, never a shrunk denominator.
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
row set with its denominator stated and at least one row seen red** — PREFLIGHT first: `ls /opt/tryton-crm/.venv/bin/python`
(the route derivation imports the project's app with the PROJECT's interpreter) and `cd /opt/tryton-crm` before
deriving (a hub-cwd run reported the hub's own FEATURES tables as tryton-crm's, measured); this is a cross-repo
**READ** only — nothing is written under `/opt/tryton-crm`, which would be a HARD STOP.

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
4. **Behavior test** `tests/test_scaffold_deploy_contract.py`: scaffold each of the **12 scaffoldable** types in a temp dir
   (`SCAFFOLD_TYPES` minus `wordpress`, which `create_project` refuses with `NotImplementedError` at
   `src/fabrik/scaffold.py:6049` — assert that refusal, do not parametrise over it);
   assert the stub exists, is executable, **exits 2**, and its header parses; assert a `docusaurus` scaffold
   does not publish the new doc sections; **red-on-revert** for the exit code and the exclusion.

5. **Vendor `health-probe` AS SHIPPED** (File Scope row 12): `cp /opt/fabrik-lib/health-probe/{health_probe.py,fingerprint.py}
   libs/health_probe/` (READ from fabrik-lib, WRITE only in this repo), prepend `# VENDORED-FROM fabrik-lib
   health-probe @ <sha>` to each (`git -C /opt/fabrik-lib log -1 --format=%h -- health-probe/<file>`), append
   `"libs/health_probe"` to `VENDORED_DIRS` (`fabrik_synced_manifest.py:115`) — the scaffolder copies it at
   `scaffold.py:1168-1173` and the fleet sync distributes it (`fabrik_synced_manifest.py:288-289`). The stub
   template imports it **lazily** (`from libs.health_probe.health_probe import compare` inside the row
   functions), and an `ImportError` there is a row `UNVERIFIABLE (health_probe not vendored — sync pending)`
   that still exits 2: fail-closed, named, never a crash. Test: the seeded copy is byte-identical to the hub's
   `libs/health_probe/` and the hub's copy differs from `/opt/fabrik-lib/health-probe/` ONLY by the
   `VENDORED-FROM` line (drift is then a red test, not a silent fork); red-on-revert by deleting the manifest entry.

**Gate:** `final_gate --json` success · `timeout 900 pytest tests/test_scaffold*.py` green · the exit-code and
docusaurus-exclusion assertions proven **red-on-revert** · the manifest entry asserted where the sync and the
scaffolder both read it: `python -c "import sys; sys.path.insert(0, 'scripts'); from fabrik_synced_manifest import
VENDORED_DIRS; assert 'libs/health_probe' in VENDORED_DIRS"` (⚠️ NOT `sync_enforcement_to_projects.py --dry-run`:
measured 2026-09-02 it prints per-FILE rows for the governance set only — 10,531 lines, none naming
`libs/subagents`, today's vendored dir — so it cannot witness a vendored-dir entry).

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
never a hub-only experiment on that path · **last step: `/fabrik-docs-review`** over every doc this plan
touched or made stale (the Doc Sync Matrix is a floor, not a whitelist).

## Spec coverage map — every committed spec element → the phase that builds it

| spec element (docs/superpowers/specs/2026-09-01-deployment-verification-contract-design.md) | built by |
|---|---|
| Approach B — extend `/fabrik-deploy-verify`, project-run, contract-driven | Phase A |
| Layer 1 identity (SHA · migration head · image digest · lockfile) | Phase A step 2 |
| Layer 3 derived at RUN time from `_REGISTRAR_ORDER` | Phase A step 3 |
| Phase 6 blocking + contract-driven parity | Phase A step 4 |
| Verdict algebra incl. `UNVERIFIED`, `not obligated` vs `not checked`, row-shape `match`, precedence 1→2→0 | Phase A steps 5–7 (executed test) |
| Amendment 2/3 — bind to `compare()`, four keys, `strict=True` always | Phase A steps 4–7 (typing at 4 · algebra at 5 · `strict`/`mismatch_exit` at 6 · rows from the vendored `compare()` at 7); the draft's Phase 2 row shape |
| Amendment 1 — a NEW project-side authoring command + DEPLOYMENT/OPERATIONS refresh from CODE+SPEC+DEV | Phase B (Appendix A) |
| Denominator integrity (derived where derivable, cross-checked where declared) | the draft's Phase 1 table + Phase 3 |
| Three-source model — DEV minus declared exclusions | the draft's Phase 1 state-baseline row + Phase 2 exclusion data |
| "A check that cannot fail is a defect" | the draft's Phase 5 (SEE EVERY ROW RED) + Phase A's gate rewrite |
| § Born compliant — scaffolder seeds the artifacts, stub exits non-zero, docusaurus caveat | Phase C |
| fabrik-lib ladder — VENDOR + ENHANCE `health-probe`; runner stays hub-side (D-072) | Phase C step 5 (VENDORED as SHIPPED, File Scope row 12, synced) · Phase A steps 4–7 (the consumer) · OUT OF SCOPE row (their future bumps) |
| Per-type packs (13 types; store types provenance-only) | the draft's Phase 0 + Phase 2 `UNVERIFIABLE`-by-default for store/static packs |
| Deferred: `fabrik apply` moving to projects (I1b); tryton-crm's RESILIENCE converge (I22) | not built — spec § Deferred names both; unchanged here |

## Execution discipline — binding on `/fabrik-execute-plan`

- **Review at every phase boundary.** Phase N complete → the FULL `/fabrik-review` adversarial methodology
  on Phase N's changed surface (independent finders for recall → refute → prove-before-fix with a kept
  regression test) → only then Phase N+1. Phases A and B are HEAVY surfaces (a synced governance
  template, an enforcement-adjacent assembler edit, a fleet-wide command) — never the scoped variant.
- **Pool-default, native on top.** Gradeable fan-out uses the OpenRouter pool (`fanout("review", …)` for
  finders; `fanout("docs", …)` for Phase B's per-surface denominator grounders) and records to the
  flywheel; a native Opus pass is ADDED for the two high-blast slices — File Scope row 5 (the synced
  pipeline line) and Phase A's verdict algebra. A standing NO-POOL directive is declared in the in-cycle
  commit message, where `check_subagent_flywheel.py` reads it.
- **Parallelism, with the merge points named.** Phase C's per-type scaffold assertions fan out one unit
  per SCAFFOLDABLE `SCAFFOLD_TYPES` entry (12 — `wordpress` is refused at `scaffold.py:6049`) and merge into
  one red-on-revert table; Phase B's dry-run grounders fan out
  one per denominator surface (routes · services · env · jobs · schema, read-only) and merge into the
  Output block; Phase A's Layer-1/Layer-3 rewrites are sequential (one file).

## Behavior Contracts — one test per user-observable behavior, risk-ordered, seen red first

**Phase A (`tests/test_deploy_verify_verdict.py` + `tests/test_check_command_corpus.py`)**

| behavior | test | seen red how |
|---|---|---|
| an attempted-but-unresolved parity row (`expected`/`actual` + `match None`) denies `CONFIRMED` and exits 2 | `test_unresolved_fails_closed` | the RETIRED `None → not checked` rule run beside it returns CONFIRMED/0 |
| a critical DOWN co-occurring with a mismatch exits 1, never upgrades the verdict | `test_precedence_liveness_wins` | assert against a rule that returns 2 |
| a liveness-only row is outside the parity denominator | `test_liveness_row_not_in_denominator` | count it in and watch `N` grow |
| no FROZEN contract ⇒ `UNVERIFIED`, never `CONFIRMED` | `test_no_contract_is_unverified` | a DRAFT header passed as FROZEN |
| the parity rows the algebra is tested on come from the VENDORED `compare()` — a raising comparator yields `match: None` + `compare_error`, keeps `system` | `test_rows_come_from_vendored_compare` | replace the vendored import with a hand-written dict and watch the `compare_error` assertion vanish |
| the rendered runner carries `## Phase 6 — Parity` and the `UNVERIFIED` vocabulary | `test_deploy_verify_source_carries_parity_phase` | run against HEAD's source (red today) |

**Phase B (`tests/test_check_command_corpus.py` extension)**

| behavior | test | seen red how |
|---|---|---|
| the rendered command carries `## Phase 5 — SEE EVERY ROW RED`, the header rule and the Output block | `test_deploy_checklist_renders_to_the_anatomy` | run against a source with the phase removed |
| the composed skill description stays under 1024 chars | `test_deploy_checklist_skill_description_within_limit` | the first draft's 1366-char description |
| a Mode-B dry run on a real project yields a non-empty row set with its denominators stated | the Phase B gate's dry run (executed, pasted) | a hub-cwd run gave the hub's numbers — the cwd assertion |

**Phase C (`tests/test_scaffold_deploy_contract.py`)**

| behavior | test | seen red how |
|---|---|---|
| every SCAFFOLDABLE type seeds an executable stub whose header parses and which exits 2 | `test_stub_seeded_and_exits_2[type]` — **12 params**: `SCAFFOLD_TYPES` minus `wordpress`, which `create_project` special-cases at `src/fabrik/scaffold.py:6049` (scaffolding moved to `/opt/wpf`; the name stays in the registry for deploy/shape only) | stub exit 0 on revert |
| `wordpress` is refused by the scaffolder, not silently seeded | `test_wordpress_is_not_scaffolded` | let the branch fall through on revert |
| a `docusaurus` scaffold publishes none of the new doc-template sections | `test_docusaurus_does_not_publish_fleet_ai_sections` | remove the exclude on revert |
| the DEPLOYMENT/OPERATIONS templates carry the fleet-AI sentinel sections | `test_fleet_ai_sections_present` | template without them |
| a scaffolded project carries `libs/health_probe/` byte-identical to the hub's vendored copy, and the hub's copy differs from fabrik-lib's only by the `VENDORED-FROM` line | `test_health_probe_vendored_and_in_sync` | delete the `VENDORED_DIRS` entry on revert |
| the stub with `libs/health_probe/` missing exits 2 with a named `UNVERIFIABLE (health_probe not vendored …)` row, never a traceback | `test_stub_without_vendored_module_fails_closed` | let the ImportError propagate on revert |

## Self-audit

- **Execution order is C → A → B → D** (pass 1 of `/fabrik-plan-review` found predicate 3 binds Phase A too).
- **Every phase has a runnable gate** — no phase exits on inspection, and every Phase A/B gate names the
  corpus checks the new text must pass (`check_command_corpus.py`, the two corpus tests, `--check` render,
  capability-index regeneration), not just the generic `final_gate`.
- **The plan follows the corpus's own approach, measured not recalled** — § Corpus conformance contract is a
  table of anchors read this run; `/fabrik-plan-review`'s re-derivation pass re-opens every one of them.
- **The riskiest step is File Scope row 5** — a synced governance template; wrong for ONE of ~46 projects
  and it ships to all of them. Second riskiest: Phase C's docusaurus caveat, guarded by a test, not a comment.
- **This plan binds to fabrik-lib's SHIPPED module, vendored, not to a shape re-implemented here** — their
  build landed before execution began (`01M1GQR1R3`, 75 tests re-run at their HEAD), so the earlier "implement
  the same shape locally until it lands" clause became DEAD scope and was struck in R6, together with the
  vendoring step it had made unnecessary to write (File Scope row 12, Phase C step 5). The verdict test now
  consumes rows from the real `compare()`, so a future re-vendor that changes row semantics turns a test red
  instead of silently re-opening the fail-open Amendment 3 closed.
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
285:    "docs/data-contract-template.md": "docs/data-contract.md",  # frozen field dictionary; filled by /fabrik-data-contract
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
14
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

**EXECUTED at fabrik-lib HEAD, READ-ONLY (R6, 2026-09-02 — the shipped interface, not its spec):**

```
$ git -C /opt/fabrik-lib log -1 --format='%h %s' -- health-probe/health_probe.py
e48ba19c feat(health-probe): Phase B — exit semantics, precedence, and a validated mismatch code
$ grep -nE "^def compare\(|def run_all_checks|list\[dict\[str, object\]\]|def _validated_mismatch_exit|2 <= code <= 255|mismatch_exit: int = 2|strict: bool = False" /opt/fabrik-lib/health-probe/health_probe.py
81:def compare(
492:def run_all_checks(
494:) -> list[dict[str, object]]:
500:    results: list[dict[str, object]] = []
521:def _validated_mismatch_exit(value: object) -> int:
541:    if not 2 <= code <= 255:
560:    mismatch_exit: int = 2,
561:    strict: bool = False,
$ grep -n "^import httpx" /opt/fabrik-lib/health-probe/health_probe.py
50:import httpx as httpx  # explicit re-export: lets `h.httpx` be monkeypatched by callers
$ cd /opt/fabrik-lib && .venv/bin/python -m pytest health-probe -q | tail -1
75 passed in 8.44s
$ .venv/bin/python verdict_algebra_shipped.py     # the J5 algebra fed rows from the REAL compare()
shipped rows: {'system': 'companies', 'status': 'OK', 'match': True} {'match': False} {'match': None, 'compare_error': "RuntimeError('x')"}
PASS agree -> CONFIRMED/0
PASS differ -> FAIL/2
PASS raise -> attempted-unresolved FAILS CLOSED/2
PASS raise keeps system name
PASS raise carries compare_error
PASS liveness row outside parity denominator
PASS DOWN + differ -> exit 1 outranks 2
PASS mismatch_exit 2 accepted, 0/1/256 refused
8/8 assertions on SHIPPED rows
$ grep -n 'VENDORED_DIRS' scripts/fabrik_synced_manifest.py src/fabrik/scaffold.py | cut -c1-90
scripts/fabrik_synced_manifest.py:115:VENDORED_DIRS = ["libs/subagents"]
scripts/fabrik_synced_manifest.py:289:    for rel_dir in [*GOVERNANCE_DIRS, ENFORCEMENT_DIR, *VENDORED_DIRS]:
src/fabrik/scaffold.py:560:    from fabrik_synced_manifest import VENDORED_DIRS
$ sed -n 83,86p pyproject.toml
exclude = [
    "^scripts/",  # Standalone scripts, not part of package
    "^tests/",
    "^templates/",
$ python scripts/review_rubric.py --changed <File Scope, 19 paths> | grep -c '^### '
10          # 7 before row 12; the three new MATCHED packs are 55-observability · 58-resilience · self-healing
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
`docs/reference/MD/ai-prompt-templates.md:256-317` · Phase C → `src/fabrik/scaffold.py:285,293,479,552-562,1127,1168-1173`,
`templates/scaffold/docs/data-contract-template.md:1-10`, `scripts/fabrik_synced_manifest.py:115,288-289`,
`/opt/fabrik-lib/health-probe/{health_probe.py,fingerprint.py}` (READ) · Phase D → `scripts/enforcement/check_convergence.py`.

## Coverage Checklist

**Rubric invocation** — `python scripts/review_rubric.py --changed commands/_sources/fabrik-deploy-checklist.md commands/_sources/fabrik-deploy-verify.md commands/assemble_commands.py commands/_sources/fabrik-release.md CLAUDE.md templates/governance/CLAUDE.md templates/scaffold/scripts/verify_prod_parity.py src/fabrik/scaffold.py templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md templates/scaffold/docs/OPERATIONS_TEMPLATE.md tests/test_scaffold_deploy_contract.py tests/test_check_command_corpus.py tests/test_deploy_verify_verdict.py docs/reference/deployment-verification.md capabilities.json docs/CAPABILITIES.md libs/health_probe/health_probe.py libs/health_probe/fingerprint.py scripts/fabrik_synced_manifest.py` — the FULL File Scope (plan-review pass 1: the earlier invocation covered 2 of 11 groups and missed three MATCHED packs)

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
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.**
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }`
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a
- VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and
- plan; never let a service-named plan be mistaken for the protection.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to
- a bare `exec "$@"`.* An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > sees a file that looks exactly like a migration step, and ships a deploy where migrations never run —
- > the rule producing the very defect it exists to prevent. Do not re-add either without a `path:line` in
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: commands/assemble_commands.py, libs/health_probe/fingerprint.py, libs/health_probe/health_probe.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: CLAUDE.md, commands/_sources/fabrik-deploy-checklist.md, commands/_sources/fabrik-deploy-verify.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (cheap-pool author → verify → converge):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. The hub's epic-to-ticket workflow (`/opt/fabrik/docs/orchestrator/epic-to-ticket-workflow/06-ticket-breakdown-fabrik.md`) injects these rows per ticket.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero
- from AI bots — agents never go looking. It follows (inference, not measurement) that a file only
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed
- daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_check_command_corpus.py, tests/test_deploy_verify_verdict.py, tests/test_scaffold_deploy_contract.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has
- a `pyproject.toml`/`uv.lock`**. ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

### core/55-observability.md  (hit: libs/health_probe/fingerprint.py, libs/health_probe/health_probe.py)
- ⚠️ **The shipper is Promtail today and Promtail reached END OF LIFE (2026-03-02)** — no
- **The label set is the PIPELINE's, not yours** — live: `container_name`, `filename`, `host`, `job`, `service_name`, `stream`. An app cannot add labels by logging a field; a JSON field is queried with `| json`, never as a label.
- > *"A twelve-factor app never concerns itself with routing or storage of its output stream. It should not attempt to write to or manage logfiles."*
**Mandate.** The app writes structured events, unbuffered, to `stdout` and **nothing else**. The app MUST NEVER write, rotate, append to, truncate, compress, age out, or otherwise manage a logfile, and MUST NEVER decide where logs are stored, how long they are kept, or how they are routed. Routing, rotation, retention, and storage are exclusively the **execution environment's** concern.
**BANNED in app code:**
- The scaffolded logger (structlog / pino — see § Pre-Scaffolded Logging) writes to stdout. Do not add a second handler, sink, or transport alongside the stdout one.
- ❌ **BANNED — in-app file logging:**
- > **⚠️ THE SERVER'S OWN LOGGERS ARE NOT YOURS — and they leak plain text by default.**
**Chrome extension frontend:** Use `chrome.storage.local` buffer pattern per the Chrome Extension Telemetry section below. Do not use pino directly in service workers.
- Name metrics with `snake_case` and a **base-unit** suffix (`_seconds`, `_bytes`); `_total` is the COUNTER suffix and composes with units (`process_cpu_seconds_total`). ⚠️ `prometheus_client` appends `_total` to a Counter itself — declare `Counter("requests", …)`, never `Counter("requests_total", …)`, and never `_count` (an OpenMetrics reserved suffix).
- ⚠️ **Know which failure YOUR stack gives you — they are not the same.** Under an OTel SDK, a
- Every `sentry_sdk.init` / `Sentry.init` in the fleet MUST set both:
| `max_request_body_size="never"` | **n/a — see below** | the request BODY, attached irrespective of `send_default_pii` (that flag gates COOKIES). Every auth, payments-webhook and token-exchange route is exposed the moment it logs an error while handling its request. **PYTHON ONLY** |
- ⚠️ **The two SDKs are NOT symmetric, and the Node column originally said otherwise — that was my
- already closed by `sendDefaultPii: false`, which makes the SDK report body **size only, never
- `httpIntegration({ maxIncomingRequestBodySize: 'none' })` — note `'none'`, not `'never'`.
**Never port an option name across SDKs by symmetry; check that SDK's own docs.**
**Verify on the CAPTURED EVENT, never the init kwarg.** Swap the SDK transport in a test, make a
- ⚠️ The scaffold emits both flags as of 2026-08-28. **A project scaffolded BEFORE that date still
- This is intentional: services without DSN configured never pay for SDK runtime cost
- ⚠️ **Outside that set nothing captures it.** A deliberate 401/403/429 you WANT audited reaches GlitchTip never — widen `failed_request_status_codes` in the init rather than sprinkling `capture_exception` through handlers.
- For `chrome-extension`: use `@sentry/browser` in the popup/options/side-panel (trusted extension pages). **In content scripts, never call the global `Sentry.init`** — a content script shares the host page's `window`, so global-state integrations hijack host-page errors. Build an isolated `BrowserClient` + `Scope` (drop `GlobalHandlers` / `Breadcrumbs`) and wrap with `makeBrowserOfflineTransport` (IndexedDB buffer/flush). Service workers use the `chrome.storage.local` buffer pattern (see Chrome Extension Telemetry below).
- **Caught-and-handled** exceptions: log with stack traces via `exc_info=True` in Python (dedicated JSON attribute, never raw multi-line text). **Unhandled** exceptions (FastAPI 500s, uncaught throws): do NOT log tracebacks — GlitchTip auto-captures them. Log a short event name + `correlation_id` only. See § Error Reporting above.
- In FastAPI: use `contextvars` + ASGI middleware to bind the ID to `structlog` context. Never use `threading.local()` in async code.
- ⚠️ **Why this fleet stops at a correlation ID, and what to name the field.** Probed 2026-09-01 across
- datasources (loki, prometheus). ⚠️ Not "no spans at all": Sentry-SDK services already emit
- So do NOT instrument distributed tracing here: spans with nowhere to go are cost without a consumer,
- Never rely on downstream log processors (Promtail, Logstash) for redaction — unredacted data may persist in transport buffers.
- **Never** use high-cardinality values as Loki stream labels. `request_id`, `user_id`, `session_id`, `client_ip` must remain inside the JSON payload only.
- ⚠️ **The label set is the PIPELINE's — an app cannot create one by logging a field.** See § Loki
- `/health` is Authelia-bypassed on all services. The bypass is **resource-based, not domain-bound** — `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file`). Never protect these paths.
- Never use UUID or timestamp-suffixed container names in Gatus configs or inter-service URLs — they drift per redeploy.
- MV3 service workers are ephemeral (terminated after ~30s idle). Do not hold logs in memory waiting for a batch window.
- Do not propose OTel instrumentation for a fleet service without new evidence. Measured against
- GlitchTip DSN comes from `GLITCHTIP_DSN` env var injected by the orchestrator from the GlitchTip registrar — do NOT hardcode the DSN in the repo.

### core/58-resilience.md  (hit: libs/health_probe/fingerprint.py, libs/health_probe/health_probe.py)
- indexed here, never restated; "can actually suffer" is decided by § Per-Scaffold Applicability above.
- ⚠️ **Rows 9 and 22 make "autorecovery" honest.** Everything else recovers a *call*; row 9 recovers the
- **`httpx.AsyncClient`** is the only HTTP client for async FastAPI. Never use `requests` (sync, blocks the event loop).
**`wait_random_exponential` / `wait_exponential_jitter`, never bare `wait_exponential`**. Not a style
- 400/401/403/404/422 — a permanent client error retried is just load. ⚠️ **`429` and `408` are the
- vendor and `408` is transient by definition, so a flat "never retry 4xx" makes an agent give up on
- curve does. ⚠️ **Two legal formats**: delay-seconds (`120`) *or* an HTTP-date
- **⚠️ Inline retry vs PAUSE — and `429` is where they meet.** An inline retry handles a **blip**; a
- discovery spares the whole queue. ⚠️ **Clamp that TTL too** (§7a): the inline cap stops a hostile
- QUEUE for a day. A vendor number never becomes a TTL unclamped. This is why the classifier pauses on
- **⚠️ Retry at ONE layer.** Retries compose multiplicatively: tenacity ×3 in a job, a queue retry ×3
- **⚠️ Retrying a non-idempotent write can double-charge, double-send or double-create.** A `POST` (or
- a timeout you never saw the response to is a second real mutation. `PUT`/`DELETE` are idempotent by
- **Graceful fallback** — cached data, a default, or a clear error. Never let an external failure crash
- your endpoint. ⚠️ That includes the *parse*: a `200` with malformed JSON raises `JSONDecodeError`,
- Clients call a **self-hosted FastAPI backend** (Pattern A — `fabrik-lib/fastapi-user-auth`), never a database-as-a-service SDK directly. Browser `fetch` / mobile HTTP clients have no built-in timeout or retry — wire them explicitly:
- **Backend outage fallback:** cached data (MMKV on mobile, localStorage on web) or a clear error state — never a blank screen or crash.
- **Auth token refresh:** the app's auth client owns the refresh flow (`35-security-auth.md` Pattern A). Never scatter ad-hoc refresh logic across service calls.
| **`open` returns the fallback IMMEDIATELY**, never a queued timeout wait | you re-pay the read timeout on every call to a dead dependency |
- distributed breaker: never back it with Redis to "share" state. ⚠️ Corollary: with N workers, up to
- **Never auto-run migrations at startup** — a one-shot deploy step (`30-ops` § Release & Admin).
- ⚠️ **The "fail readiness first, then drain" step in every Kubernetes guide does NOT apply here by
- **The signal must arrive.** Shell-form `CMD` makes `/bin/sh` PID 1, which never forwards SIGTERM —
- stampedes the origin — a herd from your own cache, not a retry loop, so jitter and backoff never
| **Backblaze B2** (S3 API, `boto3`) | 30s connect / 120s read | return an error; never block a request on an upload |
- B2 uploads go async via the job queue, never inline in a handler. **boto3 is sync** — keep it in the
- worker or a thread executor, never inside an `async def` route.
- B2 downloads use server-side presigned URLs (generation is local, no I/O — safe in async). Never
- ⚠️ **Never point `HEALTHCHECK` at the dependency-checking endpoint** — one `postgres-main` blip would
- flip every container on the fleet to `unhealthy` at once. A DB blip degrades readiness; it must never
- Both endpoints are Authelia-bypassed on all services. Never protect them.
- ⚠️ **Docker does NOT restart an unhealthy container.** `restart: unless-stopped` acts on process
- never a restart. A process that is **wedged but alive** is recovered by nothing in compose: that is
- the watchdog's Tier A `restart_container` (`60-watchdog`), and it is why the watchdog exists. Never
- see pause state without it firing Gatus alerts. ⚠️ That deliberate green is exactly why a long pause
- 1. **Detection is proactive AND reactive.** Beat tasks poll vendor balance APIs *before* workers fail; error classifiers map exceptions to pause keys on the way through. Never one without the other for a critical dependency.
- ⚠️ **So a pause carries its FIRST-set time and escalates exactly once past N× its TTL**
- boot). Sliding TTL: every detection event calls `set_pause(...)` with a fresh TTL — never `setnx`,
- never permanent. Scope (§2c of the project's RESILIENCE.md):
- your dependencies, never inline at a call site.
- The classifier maps transient signals → pause. Its mirror-image rule is just as load-bearing: **an operational failure must never be written as a terminal *content* verdict.** Model the outcome on two axes — **(transport outcome) × (content evidence)** — and record a content terminal (`deleted`, `private`, `unavailable`…) only on **positive content evidence**. Everything else is transient.
| 1 | **No single point of death** — one model or endpoint dying must not stop the loop | **Declare** the mechanism in §2b. Outage-aware routing is step 1 of OpenRouter's default strategy and a `models` array falls back on **any** error. ⚠️ **The trap: setting `sort` or `order` DISABLES load balancing, and the outage step is *part of* it** — pinning silently opts you out of the protection you think you have (claims row `openrouter-pin-disables-failover`); if you pin, you owe the `models` array explicitly | **Build it**: probe the quality-ordered candidates **once at run start** (never per item) and rebuild the chain from live survivors, best first, so it self-restores on recovery. Base it on `fabrik-lib/health-probe/`; the shared chain-rebuild helper is requested, not shipped, so promotion logic is project-local today. Needs **intra-provider** (2+ models of one provider) AND **cross-provider** diversity |
| Worker clears `dispatched:<id>` flag when paused | Worker MUST keep the flag on pause-skip (queue bloat) |
| Backup that has never been restored to staging | Run §10 drill within 30 days or it doesn't exist |
| A fallback chain whose **bottom rung has never been executed** | Exercise the last resort on a schedule — an untested fallback is a silently-dead one, and the chain is a rung shorter than its author believes |
- one-shot migration step boot must never do
- [ ] Retries use **jittered** backoff (`wait_random_exponential`/`wait_exponential_jitter`, never bare
- naming only `TimeoutException`/`ConnectError` never retries a 429.
- state — never a blank screen.

### core/self-healing.md  (hit: libs/health_probe/fingerprint.py, libs/health_probe/health_probe.py)
- AGENT USAGE: Pick the failure class, walk the ladder top-to-bottom, stop at the first step that resolves. Never invent a step. Never skip a step. -->
- Each row reads left-to-right: **Symptom** (an observable signal) → **First response** (a `58-resilience` primitive) → **Fallback** (another primitive or a `60-watchdog` Tier A action) → **Escalate** (operator-bound). The agent picks the row matching the active failure, walks left-to-right, and **stops at the first step that resolves**. Never skip rightward.
**⚠️ Row 10 is NOT the deadman timer, and the difference is the whole point.** The Tier-C deadman below
- deadman never armed because nothing escalated, and a container restart would not have helped a process
- If a failure class doesn't appear in the table above, the rule is: **add the row to this pack first, then the response logic to the code.** Never silently invent a self-healing response — it'll diverge from the operator's mental model and break the ladder's discipline.
- 4. **Self-healing without a visible signal.** A pause flag, breaker, or rate-limit reject that doesn't increment a counter and emit a structured log line is invisible — when it misfires, you can't tell. Every ladder step MUST emit a counter AND a `structlog.info()` (or `pino.info()`) row carrying the resource name + reason; without that, the next operator audit has no way to tell the difference between "step fired and recovered" and "step never ran". **Tier-D steps (stabilize / remediate / apply / rollback) are held to the same bar:** each MUST emit a counter + structured log AND write the `incidents` / `approvals` / `deploys` tables — an unaudited or irreversible code-remediation is not self-healing, it's an unreviewed deploy.

# promote-to-check_*: 123 injected mandate(s) look deterministically greppable
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an
```

**What the rubric changed here:** the FLOOR's internal-service-auth row (`X-Internal-Token` +
`hmac.compare_digest`, never an inline `APIKeyHeader`) is what the parity contract's own probes must use
when they call a sibling service — recorded so Phase B does not hand-roll auth in generated check rows.
The three MATCHED packs the full invocation surfaced are adjudicated in the rows below and quoted in
§ Constraints Digest.

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
| **behavior-without-a-test** (standing) | **FIXED** | Phase C's two assertions require red-on-revert proof; plan-review pass 1 added a Behavior Contract table to Phases A, B and C |
| core/10-python (MATCHED: `assemble_commands.py`, `scaffold.py`, the template script) | CLEAN | the seeded `verify_prod_parity.py` is a SCRIPT, not a service config surface — bare `os.getenv` is the sanctioned form there (`.windsurf/rules/core/25-data-postgres.md:67-69` carve-out); no new Settings surface is introduced |
| core/40-documentation (MATCHED: `CLAUDE.md`, `INDEX.md`, the new source) | CLEAN | the one new `.md` is `docs/reference/deployment-verification.md`, inside the DEFAULT-DENY allowlist (`docs/reference/**`); the plan lives at the mandated `docs/development/plans/YYYY-MM-DD-plan-<name>.md` path; INDEX/README are Phase D doc-sync steps |
| core/55-observability (MATCHED R7: `libs/health_probe/*.py`, the vendored module) | CLEAN | the module writes to `stdout` only (`health_probe.py:605-631` are `print`s; 0 `logging.`/`open(` sites in 647 lines) and probes compose service names, never UUID-suffixed ones — the pack's container-name rule binds Phase B's Layer-3 targets, quoted in the digest |
| core/58-resilience (MATCHED R7: `libs/health_probe/*.py`) | CLEAN | every probe carries a timeout (`connect_timeout=8` at `:182`/`:226`, `timeout or TIMEOUT` at `:265`) and NO retry loop — a one-shot probe retries at ONE layer, the caller's; the runner never becomes a container `HEALTHCHECK` (digest quote); a defect found in the vendored code is FILED to fabrik-lib, never patched in the copy |
| core/self-healing (MATCHED R7: `libs/health_probe/*.py`) | REFUTED (not applicable) | the module and the runner take NO self-healing action — a FAIL row ROUTES (`routes are asks, never actions`, Phase A anatomy) and the ladder rule *"add the row to this pack first"* is what forbids the runner from inventing a response; hunted: `health_probe.py` for `restart`/`pause`/`set_pause` → 0 of 647 lines |
| core/45-testing-strategy (MATCHED: the three test files) | **FIXED** | every phase now carries a Behavior Contract (one test per user-observable behavior, seen red first); Phase A step 7's watched-fail-first runs the RETIRED rule beside the real one |
| **order-vs-gate** (found pass 1) | **FIXED** | Phase A's runner cites `scripts/verify_prod_parity.py` → corpus predicate 3 binds A as well as B → order C → A → B → D |
| **governance files in File Scope** (found pass 1) | **FIXED** | `INDEX.md`/`docs/README.md` removed from owned paths per `check_plan_tickets.py::GOVERNANCE_FILES`; project-side outputs labelled as not hub scope |
| **directory-less anchors** (found pass 1) | **FIXED** | every § Corpus conformance anchor now carries its directory; re-derived by `sed` in pass 2 |

## Constraints Digest — the MATCHED + FLOOR packs, one verbatim mandate each (the proof the pack was open)

| quote (verbatim) | cited pack and line | what it binds in this plan |
|---|---|---|
| Watched-fail-first (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract) | `.windsurf/rules/core/45-testing-strategy.md:21` | every test Phases A–C add is seen red before green — Phase A step 7 runs the RETIRED verdict rule beside the real one; Phase C's exit-code and docusaurus assertions are proven red-on-revert |
| every ticket enumerates its distinct user-observable behaviors / acceptance criteria and tests each one | `.windsurf/rules/core/45-testing-strategy.md:19` | the Behavior Contract table each phase now carries |
| PREFERRED - Pydantic BaseSettings (FastAPI-idiomatic) | `.windsurf/rules/core/10-python.md:96` | the hub code this plan touches (`assemble_commands.py`, `scaffold.py`) introduces no new config surface; the seeded parity SCRIPT reads env with bare `os.getenv`, which is the sanctioned form for a script (below) |
| Use Pydantic BaseSettings (per 10-python.md § Config Loading) — never raw os.getenv for an | `.windsurf/rules/core/25-data-postgres.md:60` | the SERVICE-config mandate; `:67-69` carves out scripts — `verify_prod_parity.py` is a script, so its `os.getenv` reads satisfy `35-security-auth`, not violate this |
| config via env vars only (os.getenv("KEY", "default")); ZERO secrets/constants in code | `.windsurf/rules/core/35-security-auth.md:266` | the parity contract carries NO expected VALUE that is a secret — row expectations are counts, hashes, names, presence; the exclusion list names rulings, never credentials |
| deploy.resources.limits.memory is mandatory. | `.windsurf/rules/core/30-ops.md:148` | Phase B's services denominator (yaml parse) can and does assert every service declares the limit — a compose row without it is a `match: False`, not a skipped check |
| Location: docs/development/plans/YYYY-MM-DD-plan-<name>.md | `.windsurf/rules/core/40-documentation.md:157` | this plan's own path; the reference doc it adds sits in `docs/reference/**`, the allowlisted home |
| Never point HEALTHCHECK at the dependency-checking endpoint | `.windsurf/rules/core/58-resilience.md:469` | the vendored probes back the PARITY runner, run by an agent at verify time — never a compose `HEALTHCHECK`; Phase A step 4's Layer-3/4 rows read the service, they do not define its liveness |
| Never use UUID or timestamp-suffixed container names in Gatus configs or inter-service URLs — they drift per redeploy. | `.windsurf/rules/core/55-observability.md:468` | the draft's Phase 1 services denominator and Layer-3 targets are compose SERVICE names; a UUID-named target is a row defect, not a probe target |
| add the row to this pack first, then the response logic to the code. | `.windsurf/rules/core/self-healing.md:64` | the runner never self-heals: a FAIL routes to a command, a mismatch is reported — no response logic is written in this plan, so no ladder row is owed |
| Edit existing docs instead of creating new ones. | `.windsurf/rules/core/40-documentation.md:185` | the ONE new doc (`docs/reference/deployment-verification.md`) is justified by evaluation-checklist item 64 (a new subsystem owes its own reference doc) and the plan says to `grep`/`ls` first |

## Pass ledger (`/fabrik-plan-review`)

| Pass | Axes | Raised | Fixed | md5 |
|---:|---|---:|---:|---|
| Pass 1 | gate-runnability · File Scope completeness · fabrik-lib fallback · render-vs-run ambiguity | 4 | 4 | `acbdf439…` → `49c6bc8c…` |
| Pass 2 | full confirming re-sweep | 0 | 0 | stable |
| Pass 3 | method: re-derivation — every count re-run against its primary source, not re-cited | 1 | 1 | edited |
| Pass 4 | confirming | **0** | **0** | stable ✓ |
| — | **operator approved the design (D-077) and directed: re-author to the command-corpus conventions — convergence voided, `/fabrik-plan-review` re-run** | — | — | — |
| R1 | full read: conformance anchors · Appendix A vs Phase B · order vs gates · File Scope exhaustiveness · Evidence re-run · flip graders · feature-scale | method: citation + live grep + execution | 11 (new: 11) | 11 | `347bc891…` → `49adfe47…` |
| R2 | every R1 edit re-derived: anchors by `sed`, digest quotes via `check_rule_grounding._norm`, rubric paste diffed against a fresh run, Evidence block re-executed, embedded-source md5 | **method: re-derivation** | 5 (new: 5) | 5 | `49adfe47…` → `6368b7ae…` |
| R3 | closing read of the new sections + every R2 edit re-derived + the grader's own parsers executed on the digest | **method: re-derivation + execution** | 3 (new: 3) | 3 | `6368b7ae…` → `d9155630…` |
| R4 | closing FULL fresh read of the whole plan + the battery (anchors · digest · rubric · Evidence · md5 · File Scope · residues) + the three flip graders run on a temp-flipped copy | **method: re-derivation + execution** | 4 (new: 4) | 4 | `155e1fc6…` → `51edd8a4…` |
| R5 | closing fresh read of the R4 region + BIDIRECTIONAL prose↔source (14/14) + the full battery + flip graders with exit codes and denominator | **method: re-derivation + execution** | **0 (new: 0)** | **0** | `51edd8a4…` → `51edd8a4…` ✓ → **CONVERGED** |

| — | **operator approved the design (D-077) and directed: re-author to the command-corpus conventions — convergence voided, `/fabrik-plan-review` owed** | — | — | — |
| — | **fabrik-lib SHIPPED the comparison axis (`01M1GQR1R3`, 2026-09-02) after R5 — the operator asked for the mail to be checked and the review re-run; the R5 stamp (D-080) is VOID for this run** | — | — | — |
| R6 | WIDE fresh read attacking (A) every "their build lands later" clause · (B) `run_all_checks` typing under the hub's mypy scope · (C) `mismatch_exit` 2..255 · (D) the algebra on rows from the REAL `compare()` · (E) the R1–R5 class ledger re-swept (File Scope existence 11/11 · rubric re-run 7/7 packs identical · Evidence probes) | **method: citation + execution** (their suite 75/75, `_validated_mismatch_exit` 0/1/2/255/256, `compare()` three shapes, `verdict_algebra_shipped.py` 8/8) | 6 (new: 6) | 6 | `60f26eb8…` → `7a6cbbd4…` |
| R7 | SCOPED to the R6 edits + their cross-references: coverage-map step range · Phase C gate re-grounded (the sync dry-run cannot witness a vendored dir — measured) · rubric re-run over the 19-path File Scope → 3 NEW MATCHED packs (55 · 58 · self-healing) adjudicated in the Coverage Checklist and quoted in the Constraints Digest · Evidence block gains the executed R6 probes | **method: execution + citation** | 3 (new: 3) | 3 | `989e7e7a…` → `0e96f806…` |

**Standing:** the `## Constraints Digest` HEADER row reads as one QUOTE-NOT-FOUND in `check_rule_grounding` (advisory) — its `_digest_rows` has no header rule and `PATH_TOKEN_RE = [\w./-]+` matches any word, so every honest header is a phantom; adjudicated in pass R3, filed to infra at this review's close; never counted as a raise.

**Pass 4 terminal — `found: 0, fixed: 0`.** *(Historical — the corpus re-authoring above post-dates it.)*

**Pass R1 (this review — 11 defects, all the author's, in text written the same day):** the appendix's
fenced source was embedded TWICE (a re-embed script matched the source's own first inner fence) · every
§ Corpus conformance anchor was directory-less and resolved nowhere by `sed` · the scaffold-test count
read 13 (re-derived: 14) · the rubric was armed over 2 of 11 File-Scope groups and missed three MATCHED
packs · no `## Constraints Digest` (the rule-grounding grader's NO-DIGEST) · no per-phase
`/fabrik-review` boundary, pool-default or parallelism statement · execution order A → C → B → D would
have reddened Phase A's own gate (its rewritten runner cites `scripts/verify_prod_parity.py`, so
corpus predicate 3 binds A too — now C → A → B → D) · no Behavior Contract per phase · no
`/fabrik-docs-review` last step · `INDEX.md`/`docs/README.md` sat in File Scope though they are
governance files the gate keeps out · no spec-coverage map · no toolchain preflight for the cross-repo
dry run. Clean on the first read: Appendix A vs Phase B (30/30 elements, 16/16 PARAMS tokens), feature-scale
(no ticket store, no dispatched agents), provider-death (no unattended external loop — N/A, stated).

**Pass R2 (re-derivation of R1's edits — 5 more, all in R1's own text):** one NEW directory-less anchor
in a Coverage row (`core/25-data-postgres.md:67-69`) — the class R1 had just fixed, recurring in the fix ·
the pasted rubric came from a different invocation than the plan states (INDEX.md was in the captured
run but not the stated one — one hit-list line differed) · one Evidence line's recorded output was a
hand-trimmed comment tail, not the command's real output · the appendix prose still said A → C → B → D ·
the digest's header cell literally read `file:line`, which the grader's row parser reads as a path (renamed;
the grader's header rule is filed separately). 7 of 8 digest quotes FOUND through the grader's own
normaliser before the header fix; embedded-source md5 `110cdcd8` = scratch = stated.

**Pass R3 (closing read + execution — 3 more, all in R1/R2 text):** the Phase C Behavior Contract and the
Execution discipline said **13** scaffold params, but `create_project` refuses `wordpress` with
`NotImplementedError` (`src/fabrik/scaffold.py:6049`) — a parametrised stub test over all 13 fails by
construction; now 12 + an explicit refusal assertion, and Phase C step 4 says the same · the
40-documentation digest quote began with "Rule:", which `check_rule_grounding._digest_rows` DROPS as
rule-header noise (`quote.lower().startswith("rule")`) — the row was silently absent from the grader's
count; rephrased to the verbatim clause after the colon · the digest's header row is parsed as a data row
by the same function (it has no header rule; any second cell matching its path-token regex is a citation) —
a phantom QUOTE-NOT-FOUND on every digest whose header names its column honestly, filed to infra at close.
Clean on re-derivation: anchors resolve by `sed` (22 lines), rubric paste identical to the stated
invocation's fresh output, Evidence 11/11 re-executed OK, `$ ...` elided probes 0, File Scope 0 unaccounted,
order residue only inside this narrative.

**Pass R4 (closing full read — 4 more, one class: Phase B's PROSE had drifted from the embedded SOURCE):**
step 1 still said `{{include:term-edit}}` *"(via EXTRACT)"* · it still QUOTED the first draft's 1366-char
description — the one `_emit_skill` refused — instead of the 785-char one in Appendix A · its Phase 1 bullet
still derived routes from "the router's introspection" and schema from `alembic heads`, where the source says
the started app's `/openapi.json` and the type's own mechanism (the dry run's two sharpest findings) · its
Phase 3 bullet keyed the cross-check on the literal word *Shipped*, the vocabulary a first-table grep read
as 0 of 88. The R1 attack-B script had checked *source ⊇ prose elements*, never *prose = source* — a
one-directional check passing while the artifact that will actually be committed disagreed with the plan
describing it. Battery clean: 22 anchors resolve, digest 8/8 FOUND (+ the Standing header phantom), rubric
paste identical, Evidence 11/11 re-executed, embedded md5 `110cdcd8` three ways, File Scope 0 unaccounted,
elided probes 0. Flip graders on a temp-flipped copy: `check_convergence` silent/0, `check_stage_artifacts`
silent/0, `check_rule_grounding` exactly the one Standing phantom.

**Pass R5 terminal — `found: 0, fixed: 0`, md5 `51edd8a4` identical start→end.** Prose↔source checked in
BOTH directions this time (14/14 load-bearing rules agree); 22 anchors resolve by `sed`; digest 8/8 quotes
FOUND through the grader's own normaliser; rubric paste identical to a fresh run of the stated invocation;
Evidence 11/11 re-executed identical; embedded-source md5 `110cdcd8` three ways; File Scope 0 unaccounted;
elided probes 0. The two remaining "EXTRACT" strings are the Evidence block's own grep and its measured
output line — facts, not claims — refuted. `check_convergence` listed exactly this plan as its target and
exited 0; `check_stage_artifacts` 0; `check_rule_grounding` the one cited Standing phantom (filed to infra:
`01M1GSBZ9HYZP18QZSNR09W62G`).

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

`/fabrik-execute-plan docs/development/plans/2026-09-01-plan-1-deployment-verification.md` — on the operator's
approval (a contractual gate: the plan mutates a fleet-synced governance template and a box-wide command corpus).
Execution order C → A → B → D.

## Appendix A — Phase B source DRAFT, proven through the real pipeline (2026-09-02)

The operator asked twice whether the command could be created properly. The answer is this draft — the
**complete source** Phase B starts from, not a stub — plus what executing it showed. It lives here rather
than in `commands/_sources/` because a file there renders box-wide and corpus predicate 3 fails until
Phase C seeds `templates/scaffold/scripts/verify_prod_parity.py` (execution order C → A → B → D).

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

````markdown
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
`Status: DRAFT` stub that **exits 2** — an unfilled contract fails closed — and the fleet sync seeds the
vendored `libs/health_probe/` it imports (VENDORED_DIRS). **If `libs/health_probe/health_probe.py` is absent**
(a repo the sync has not reached yet): copy it from `/opt/fabrik-lib/health-probe/` into THIS repo's
`libs/health_probe/` (a read of the sibling repo and a write in your own tree — not a cross-repo edit), say so
in the report, and carry on; the next sync overwrites it with the identical bytes. **A DRAFT stub is meant to be
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
````
