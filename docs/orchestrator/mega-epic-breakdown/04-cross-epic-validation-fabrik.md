<!-- ⚠️ FABRIK FACTORY WORKFLOW — CROSS-EPIC VALIDATION (our own, tool-capable twin of
     04-cross-epic-validation-command). Run DIRECTLY by our orchestrator agent (Opus 4.8, via the driver) —
     never pasted into a planner GUI.
     THIS IS THE MEGA ANALOG OF ettw `10-cross-artifact-validation` — a CONVERGING review, not a one-shot
     audit. Opus dispatches reviewer agents across the cross-epic seams AND fixup agents to close what they
     find, and runs the epic set to its lens-adjudicated exit (every Step-4 report lens PASS-with-evidence, min-2 rounds, no ceiling). It is AUTONOMOUS: the operator already agreed to the
     decomposition at `02`; there is no human step here `[canonical: north star § Human gates — R14: the two
     gates are plan-in (the operator's spec/plan approval upstream) and deploy-out (`11-deploy`)]`. It halts
     only on the 3 BLOCKED cases.
     ⚠️ Persistence: we have NO Traycer store and no `read_spec`/`read_ticket` tools — those are Traycer's.
     Epic tickets are FILES under `docs/development/epics/` (written by `03-expand-epic-files-fabrik`).

     Reads (open NOTHING else to act — every other citation below is `[canonical: …]` provenance you act on
     from the inline decision, or `(deeper, optional: …)` you may skip):
       · the **epic ticket FILES** — `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md` (enumerate with
         Glob; the file count IS the epic count)
       · the **Vision Summary** (`00-trigger-mega-epic-fabrik` output — its `## Full Feature Inventory` and, in
         EXISTING mode, its `## Compliance Report`)
       · the **Infrastructure Decisions** spec — content decided by `02`, PERSISTED by `03` to
         `docs/superpowers/specs/YYYY-MM-DD-<project>-infrastructure-decisions.md`; read it from disk (every
         ticket cites that path). It ALSO carries `## Deferred Compliance (not actioned this run)` — lens D's source for the
         `fix-later`/`accept-as-legacy` rows, which emit no epic and live nowhere else — + the **Dependency Graph** (`02-epic-decomposition-fabrik`, in conversation)
       · `PORTS.md` — the port-allocation registry (a `Port` claim is checked against it, not eyeballed)
       · `src/fabrik/orchestrator/infrastructure.py` — the applicability matrix, to check `Registrars` ↔ `Shape`
       · `.windsurf/rules/**` — existence check only, to confirm a cited `Rule Packs` entry is real
       · during fixup — each returned agent's diff + its `final_gate.py --json` output
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). No hard-coded item count here. -->

# Cross-Epic Validation

<!-- rule-grounding-cite v1 · companion to rule-grounding-gate v1 (commands/_fragments/grounding-rules.md) -->
⚠️ **Constraints-Digest citation (BINDING):** every architecture, tool, or dependency selection in this
step cites a row of the upstream CONSTRAINTS DIGEST or states `unconstrained`; a selection that collides
with a digest row is DEAD. If no digest artifact exists upstream, STOP — run the Rule-grounding gate
before proceeding. fabrik-lib verdicts follow the same law: vendor/wrap/build cited, never assumed.

## Role

The **cross-epic (epic-set) review orchestrator** — Opus 4.8, running the driver's loop `[canonical: docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md]`. After `03-expand-epic-files-fabrik` writes one file per epic, this reads the **whole decomposition** and proves it is ready to execute: every feature covered exactly once, no broken or invented dependencies, disjoint parallel lanes, each ticket self-sufficient for the ettw chain. It dispatches reviewer agents to find seam defects and fixup agents to close them, and **runs the epic set to its lens-adjudicated exit — it does not stop and ask** except on the three BLOCKED cases. It writes no epic content itself; the fixup agents do (Step 3).

**Why a converging review, not an audit** `[canonical: north star § Command-chain build plan — CC1: a doer produces, a separate review forces the no-op]`: `02`/`03` produce; a single PASS/FAIL pass would hand the owner a defect list and stop. This is the mega analog of ettw `10` — it converges the artifact set instead.

## Core Philosophy

- **Read the ticket FILES from disk — never conversation memory.** Validating a ticket against your memory of it is how a stale ticket passes. Enumerate with Glob; read every one fresh.
- **Every finding is binary + evidenced** — PASS/FAIL with the specific `path:line` (or the two contradicting tickets). No "looks good."
- **Tool-capable advantage — verify, don't take the ticket's word.** Unlike the Traycer twin, this command CAN open `PORTS.md`, the rule packs, and `src/fabrik/orchestrator/infrastructure.py`. A ticket that *claims* `needs_database: true` is checked against whether it *lists* the postgres registrar; a cited pack is confirmed to exist.
- **Surgical fix here; boundary re-cuts route back.** A missing Metadata field, a wrong title format, an absent `Owned paths` → a scoped fixup, dispatched and re-reviewed. A change to the epic **boundaries** (orphans, duplicates, a wrong split) → route to `02-epic-decomposition-fabrik` (then `03` to recreate); this command never re-cuts epics.
- **The only cases that PAUSE a thread are the 3 BLOCKED cases** `[canonical: CLAUDE.md § Behavior — the three BLOCKED cases]`: 3 consecutive same-test failures on one fixup · missing infra · an unresolvable spec contradiction. On any → Apprise→Telegram, pause THAT thread, continue the rest. ⚠️ A **missing or corrupt upstream artifact is a ROUTE-BACK, not a halt** — hand it to `00`/`02`/`03`, which re-emit, and the driver re-enters here. Neither is a human stop.
- **Flavour-aware staging** — a **delta-feature** epic must pass all four stages (scaffold → implement → `fabrik apply` → `fabrik verify`); a **Retrofit** epic on an already-deployed service creates **no new deploy unit**, so it owns no Stage-1/Stage-3 — its Stage-3 equivalent is the gate + the compliance-row flip `[canonical: 03-expand-epic-files-fabrik § Success Criteria]`. Validate each epic against the stages its **flavour** actually owns, never a blanket four. *(deeper, optional: `docs/operations/fabrik-lifecycle.md` — it covers only stages 3–4 and carries **no** stage model, so it cannot settle this; the flavour rule above does.)*

## Input Contract

**Required** — hard requirements, not preferences; if any is absent this command does not review, it **routes back** (Step 1):

- **Vision Summary** (`00-trigger-mega-epic-fabrik`) — its `## Full Feature Inventory` is lens A's yardstick; in EXISTING mode its `## Compliance Report` drives lens D's Deferred-Compliance check.
- **Infrastructure Decisions** spec (decided by `02`, persisted to disk by `03` at `docs/superpowers/specs/YYYY-MM-DD-<project>-infrastructure-decisions.md` — read it there; it also carries the `## Deferred Compliance (not actioned this run)` section lens D checks) + **Dependency Graph** (`02-epic-decomposition-fabrik`, in conversation) — lens D's and lens C's yardsticks.
- **Epic ticket FILES** (`03-expand-epic-files-fabrik`) — one per epic under `docs/development/epics/`; enumerate with Glob, **the file count IS the epic count**.

## Output Contract

**Format:** the Cross-Epic Validation Report (markdown, structure in Step 4), posted to the Telegram digest at the adjudicated exit. **Structure-bounded, NOT token-capped** `[canonical: EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md — item 93]`: a PASS/FAIL-row-per-check report is already bounded by "fill this template once", so a numeric budget would only force harmful truncation of exactly the failures the owner most needs to see. **Do not add one.**
**Result:** the adjudicated verdict — every report lens PASS-with-evidence, with the round ledger, fixup count and any route-backs; never a bare defect list.
**Consumed by:** the cockpit (epic cards → GUI card-click dispatch) / the driver (`epic_order.py --json` → phase queue); or `02`/`03`/`00` on a route-back. (`05-dispatch` retired — dispatch is code + GUI, not a command.)

## Processing User Request

### Step 1: Read All Artifacts

Glob `docs/development/epics/*.md` and read every ticket in full; read the Vision Summary + Infrastructure Decisions + Dependency Graph. **If any is missing, do not review — ROUTE BACK** (not a halt): state which, hand to the creating command (`00` for the Vision Summary; `02` for the decomposition CONTENT; `03` for a ticket **or for the Infrastructure Decisions FILE** — `02` writes nothing to disk, so only `03` can re-emit a missing spec file), and re-enter here once it re-emits. State: *"Read the Vision Summary + Infrastructure Decisions and [M] epic tickets."*

### Step 1.5: Ticket-Set Integrity — run in CODE (folded from the retired `05`)

`[canonical: north-star R8/D4 — control flow in code, not prose]` The ticket-set integrity that `05-dispatch` used to do by hand — count-match against `02`'s proposal, epic-number contiguity, duplicate/orphan detection, and the parallel-set disjointness / single-migration-owner proof — is now the deterministic gate `scripts/epic_order.py`, run over the typed frontmatter (`[canonical: EPIC-ARTIFACT-SCHEMA.md]`). **`05` no longer exists; this leg absorbs its Step 1.**

```bash
python /opt/fabrik/scripts/epic_order.py --check --expected-count <N from 02's Compact Epic Proposal> \
       --epics-dir docs/development/epics
```

- **PASS (exit 0)** → continue to Step 2.
- **FAIL (exit 1)** → the script prints each finding. Route by cause, exactly as `05` did — but now off a machine verdict, not a hand diff:
  - *count mismatch / missing number* (deficit) → `03-expand-epic-files-fabrik` to recreate ONLY the named epic(s); do not discard the rest.
  - *duplicate epic number* (stale/redundant copy) → the older date-prefix file is stale → `rm` it, then re-enter.
  - *no frontmatter / bad title / bad `epic_n`* → `03` (it must emit the epic-artifact schema).
  - *shared `owned_paths` or two migration owners in a parallel set* → boundary re-cut → `02-epic-decomposition-fabrik` (then `03`).
  Re-run this gate after any fix — a recreated ticket has never passed integrity.

⚠️ This closes the gap that made `04` unable to catch a deficit: it previously took the Glob file count AS the epic count. The `--expected-count` from `02`'s proposal is now the chain's count-match, in code.

### Step 2: Dispatch the Cross-Epic Review — reviewer agents (BOTH mechanisms)

**ARM every reviewer FIRST (spec G5/G6 — an un-armed reviewer measured ~0–22% defect recall):** run
`python /opt/fabrik/scripts/review_rubric.py --changed <the epic files under review>` and
**inject its output into every reviewer agent's prompt** as the rubric they hunt against. The rubric
carries two layers: **(1) the mandatory-core floor** — `core/35-security-auth` +
`core/25-data-postgres` + `core/30-ops` + all twelve 12-Factor axes — always injected regardless of glob
and never skippable, so the review is never un-armed on the high-blast-radius rules; **(2)** every pack
whose glob matches a changed path (mandate lines only). (No `--workflow` here: this command reviews the
chain's runtime PRODUCTS — epics / artifacts / implemented code — not the 00-N command files themselves;
the `EVALUATION_CHECKLIST_*` authoring-QA injects only when a review's subject IS a command file, e.g.
`/fabrik-workflow-review`.) The whole rubric is computed fresh by the script; nothing is inherited from
the doer. Honesty (L1): the injection STEP is maximally enforced (the rubric is always injected); this
raises compliance probability — it does **not** make compliance guaranteed.

Dispatch through the **`libs/subagents` module** — **BOTH** layers, never either/or `[canonical: core/62-using-subagents.md § Dispatch policy]`:

- **Pool breadth** — `fanout("review", units, repo=…, project="mega-review", mode="read_only")` picks family-diverse, flywheel-ranked review models (no default price cap) and auto-records each run to the flywheel. ⚠️ **Passing `project=` is what makes it record** — omit it and you land zero flywheel rows `[canonical: libs/subagents/agent.py — fanout records only when project is set]`. After you adjudicate, back-fill your 0–5 verdict with `set_quality(r.agent_id, score, project="mega-review", task_type="review", model=r.model)` `[canonical: libs/subagents/pg_ledger.py — set_quality]` (an unscored row teaches the flywheel nothing; ⚠️ never hand-roll run_agents + record_run — it no-ops).
- **≥1 native `fabrik-reviewer` on Opus** — the authoritative pass (the pool never runs `anthropic/*`, so pool-only is not valid). It owns the high-risk seams: the parallel-set disjointness, the single-migration-owner rule, and `Registrars` ↔ `Shape`.

Each reviewer commits to a lens before seeing the others; **you (Opus) refute/merge/decide**. The lenses:

**A. Feature coverage** — extract the Vision Summary's `## Full Feature Inventory`; map each feature to the epic claiming it in `### Scope > In:`.

| Check | PASS | FAIL |
|---|---|---|
| Inventory present | section present AND ≥1 feature | missing/empty → Vision Summary corrupted; route to `00-trigger-mega-epic-fabrik`, do NOT continue |
| Every feature assigned | all mapped (counts BOTH numbered delta features `1,2,…` AND EXISTING-mode Retrofit features `R1,R2,…`) | feature #X "[name]" in no epic |
| No feature in two epics | each in exactly one (delta + Retrofit alike) | #X claimed by Epic A and Epic B |
| No phantom features | epics contain only inventory features | Epic N claims "[name]" absent from the Vision Summary |

**B. Epic ticket structure** — per ticket:

| Check | PASS | FAIL |
|---|---|---|
| Title format | `Epic N — [Name]` exactly (em-dash, single spaces; optional `Retrofit:` prefix in `[Name]`) | en-dash/hyphen/missing space/wrong number |
| `### Summary` · `### Scope` (In+Out) | present | missing |
| `### Success Criteria` — **by flavour** | delta-feature 5–8; **Retrofit 3–5** `[canonical: 03-expand-epic-files-fabrik § Success Criteria]` | below the per-flavour minimum |
| deploy/gate-level criterion | delta: "`fabrik apply` succeeds" or "/health 200". Retrofit (no new deploy unit): `scripts/final_gate.py` success + the Compliance-Report gap moving Partial/Violates → Compliant | neither flavour's criterion present |
| resilience criterion | delta: states what happens when a dependency is down. Retrofit: N/A **iff** the area is not resilience/external-call related (Title lacks `Resilience` AND Universal categories lacks #5) | absent AND the epic IS resilience-related |
| `### Out of Scope` | present — other epics, vision-level exclusions, or an explicit `none — …` reason | missing, vague, OR cites a non-existent Epic N |
| `### Dependencies` — **all 5 sub-bullets** | `Consumes from prior epics` · `Produces for later epics` · `Depends on` · `Parallel with` · **`Owned paths`**, each with content or an explicit `none` reason. ⚠️ **`Owned paths` is NOT optional and `none` is NOT valid** — every epic writes something, and lens C's disjointness + migration checks intersect exactly this field | any sub-bullet missing/empty, OR `Owned paths` absent or `none` (it makes lens C unrunnable and any `Parallel with:` claim unverifiable) |
| `### Metadata` — **structure only** | the `### Metadata` section exists with all 15 rows present. ⚠️ **Field VALUES are lens E's authority, not B's** — do not judge them here, or two nominally-orthogonal lenses file the same finding twice and the merge reads one check as two lenses corroborating | section missing, or fewer than 15 rows |
| Dependencies name artifacts | tables/functions/endpoints/env vars named (or explicit `none` for atomic-root / terminal-output epics) | vague only ("Epic 1's infrastructure") |

**C. Dependency graph** — cross-reference the graph against every `### Dependencies`.

**Graph form:** `02` emits a **mermaid diagram with `subgraph "Phase N"` blocks**; prose instead → the owner cannot see the shape of their own decomposition → route to `02`. Terminology is **`Phase`, never `Batch`** (consistent across 02/04/05). **Epic-count sanity:** state the count + a one-line verdict — **3–7 typical**; **10+** ⇒ recommend re-examining boundaries (likely split by layer, not domain); **2** ⇒ the vision may not need this workflow. A **surfaced observation, not a hard FAIL** — but never unremarked.

| Check | PASS | FAIL |
|---|---|---|
| No cycles | DAG validated | Epic A → B → A |
| Graph matches tickets | every dependency in the graph appears in a `### Dependencies` | Epic N depends on M but the graph omits it |
| Root epic(s) identified | ≥1 epic with no upstream | none — everything depends on something |
| **Parallel lanes identified** | every set of epics with **no mutual dependency** is marked `Parallel with:` — this row DEFINES the input set the two rows below intersect | a mutually-independent pair left unmarked → the disjointness + migration gates never see it, and the owner loses free parallelism `[canonical: EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md — item 79, "parallel lanes identified"]` |
| **Parallel epics have DISJOINT `Owned paths`** | for every `Parallel with:` pair, intersect their `Owned paths:` → empty | A and B are parallel but both write `[glob]` → two agents writing one file is a merge conflict by construction → re-cut the boundary or make it sequential |
| **At most ONE migration owner per parallel set** | only one epic in a set owns `alembic/versions/**` / `db/schema.sql` | two parallel epics own migrations → concurrent Alembic heads race the version table and wedge the deploy (12-Factor XII) → the non-schema epic must `depends-on` the schema epic |
| Produced artifacts consumed | every `Produces` has a matching `Consumes` — N/A for a single-epic proposal and for terminal-output epics producing end-user output only | A produces X, nobody consumes it, epic count > 1, and X is internal (table/endpoint/env var/queue) |
| **CRITICAL PATH stated + matches** | `02` sub-step **2d** emits `Critical path: Epic 1 → 3 → 5 (3 deep)` — the longest chain; confirm present AND consistent with the validated graph | missing or contradicts the graph → route to `02` 2d. ⚠️ Without it nobody knows what gates delivery |
| **SPLIT-CANDIDATE per critical-path epic** | every critical-path epic carries `SPLIT-CANDIDATE: yes (<how>) / no (<why>)` per `02` 2d | missing on any — a critical-path epic splittable into a blocking + non-blocking half **MUST** be split; that is the only way to shorten delivery |
| **Graph is MINIMAL** | every **sequential** pair has a stated artifact reason (`Consumes:` names what B takes from A); if epics CAN be parallel they MUST be | B `depends-on` A but consumes **nothing** → an invented edge lengthening the critical path for free → reclassify to parallel (then it must pass the two gates above) |

**D. Infrastructure Decisions** — read the spec; verify against the tickets.

| Check | PASS | FAIL |
|---|---|---|
| All shared decisions present | per `02` Step 3: Database · Auth · Email · Background Processing · Embedding Model (if RAG) · Self-Healing Ladder (if `shape.kind ∈ {service, worker}`) · Watchdog Wiring (**ON by default** — the resolver reads the raw spec dict `[canonical: src/fabrik/orchestrator/infrastructure.py — watchdog applies unless the spec sets watchdog enabled false]`; ⚠️ the `shape.kind` matrix in `core/60-watchdog.md` is **operator discipline, NOT code-enforced** — a `static-site` gets a watchdog despite the matrix saying `off`) · Observability Defaults · Cost Guardrails (any paid-API use) · Backing Services · External Services · Domain Structure · Shared Env Vars · Shared Shape Decisions | missing section: [name] |
| Tickets reference, not duplicate | epics say "Inherited from Infrastructure Decisions" | Epic N re-defines [decision] differently |
| No contradictions | consistent across all tickets | Epic N says X, the spec says Y |
| **Deferred Compliance appendix** (EXISTING mode only) | if the Compliance Report has any `fix-later` / `accept-as-legacy` row, an appendix lists every one — those rows emit **no epic**, so the appendix is their only carrier, and `03` persists it into the Infrastructure Decisions spec's `## Deferred Compliance (not actioned this run)` section — **read it there**, not from conversation `[canonical: 02-epic-decomposition-fabrik § Step 2b — fix-later/accept-as-legacy rows emit no epic]`. N/A in NEW mode or when all rows are `fix-now` | such a row appears in no epic and no appendix → the owner's deliberate deferral was silently dropped. ⚠️ Route by cause: present in the Compliance Report but missing from the spec's section → `03` (it didn't carry them); deferred by the owner but never surfaced by 02 → `02` 2b |

**E. Handoff readiness** — each ticket must feed **`epic-to-ticket-workflow/00-trigger-fabrik` in multi-epic (consume) mode**, which reads the ticket's 15-field Metadata **as the INFRA-CHECK** and only then hands to `01-decisions-lock-fabrik`. ⚠️ **The entry point is `00`, not `01`** — `01` § Path B *assumes* the INFRA-CHECK exists, and `00` is the only command that emits it.

| Check | PASS | FAIL |
|---|---|---|
| `Port` | present **and not already allocated** — verify against `PORTS.md`, don't eyeball | missing, OR taken in `PORTS.md`, OR two epics claim the same port → route to `02` (it allocates from `PORTS.md`) |
| `target_vps` | `vps1`/`vps2`/`vps3` | missing — the tech plan cannot pick the DB host |
| `Responsive` / `Dark+Light` | present AND the value **matches the feature trigger** — mandatory iff a GUI surface exists (saas-skeleton / docusaurus front / chrome-extension popup / mobile-app / desktop-app, OR python-api/node-api/file-api with `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML) `[canonical: 00-trigger-mega-epic-fabrik § Rule-area applicability matrix — the trigger is the GUI SURFACE, not the scaffold type]`; `N/A` only when no HTML/native UI exists | missing, OR `N/A — non-GUI scaffold` on an epic whose Shape has `is_admin_dashboard`/`is_public`+HTML — a rule-pack violation, not a metadata gap |
| **`Registrars` ↔ `Shape`** — a SEMANTIC cross-check, not presence | every firing flag has its registrar listed: `needs_database`⇒postgres · `needs_cache`⇒redis · `has_persistent_data`⇒backrest · `has_search_feature`⇒meilisearch · **`is_public` AND `spec.domain`**⇒gatus · **`is_admin_dashboard` AND `spec.domain`**⇒authelia · **`exposes_metrics` AND `spec.domain`**⇒prometheus; plus **glitchtip** (`shape.kind ∈ {service, worker, wordpress}`), **grafana** (always) and **watchdog** (opt-OUT). ⚠️ `has_bearer_api` fires **no** registrar — only the Authelia `^/api/` bypass `[canonical: src/fabrik/orchestrator/infrastructure.py — the applicability matrix]` | the list contradicts `Shape` — e.g. `needs_database: true` but postgres absent. **Not a metadata gap — a silently-broken deploy**: `fabrik apply` skips the registrar and the service comes up without its database `[canonical: CLAUDE.md § Spec contract awareness]` → route to `02` |
| the other **10** fields — present **and value-shaped** (not presence-only) | `Scaffold` · `Shape` · `Concurrency` · `i18n` · `Rule Packs` · `HAS_USER_GUIDE` ∈ {true,false} · **`Universal categories` = comma-separated 1–14, verbatim from `02` sub-step 2h** (a hand-invented list is a FAIL) · `Email` ∈ {transactional, marketing, two-stream, none, N/A} · `Abuse Detection` = `required` (SaaS w/ free tier) or `N/A — <reason>` · `FINANCIALS` = `required` (SaaS launch gate) or `N/A — <reason>` | missing: [name], **or present with an off-contract value** — a presence-only pass is the same regression this table flags for `Registrars` |
| Ticket is self-sufficient | the whole ettw chain (`00-trigger` consume → `01-decisions-lock`) runs from ONLY this ticket + the Infrastructure Decisions spec | needs context only the Vision Summary carries |

### Step 3: Converge to a No-Op — fixup, don't stop

Classify every surviving finding, then handle it autonomously — everything short of a BLOCKED case:

- **Surgical ticket fix** (a missing Metadata field, a wrong title format, an absent `Owned paths`, an off-contract field value) → a **scoped fixup ticket** naming the finding's `path:line` + the required value, **dispatched** through `libs/subagents`: the pool `pick_models("docs")`/`pick_models("spec")` via `fanout` for an epic-file edit, or **`claude -p opus`** for a high-risk one (e.g. a migration-owner correction) `[canonical: 06-ticket-breakdown-fabrik § Step 9 — the coder tiers]`. Re-read + re-review to confirm. ⚠️ **NOT** a `Registrars`↔`Shape` mismatch — lens E routes that to `02` (a silently-broken deploy, not a metadata gap) and lens E is the authority on it.
- **Boundary / scope change** (orphans, duplicates, phantoms, a wrong split, a port re-allocation, a missing Infrastructure-Decisions **section**) → **route back**: `02-epic-decomposition-fabrik` (boundaries, ports, Step 3 sections, sub-step 2h universal coverage) — ⚠️ but a missing Infrastructure-Decisions **FILE** is `03`'s (02 persists nothing), and a missing or incomplete `## Deferred Compliance (not actioned this run)` section inside it routes **by cause, per lens D — the authority on it**: rows present in the Compliance Report but absent from the spec → `03` didn't carry them; rows the owner deferred that `02` never surfaced → `02` 2b. Then `03-expand-epic-files-fabrik` to recreate the affected tickets. Never re-cut epics here.
- **Vision Summary corrupted** (lens A's inventory missing/empty) → route to `00-trigger-mega-epic-fabrik`; do NOT continue.
- **BLOCKED cases** — 3 consecutive same-test failures on one fixup → case 1 (Telegram, pause that thread, continue); missing infra → case 2; unresolvable spec contradiction → case 3.

**LOOP:** every fixup dispatched → re-reviewed (Step 2) → re-classified — **until every verdict lens of the Step-4 report template carries an adjudicated PASS-with-evidence, with zero unresolved findings** (the template is the single source of the lens set). **The final round must itself be QUIET — `found: 0, fixed: 0`, counting every raised candidate including later-refuted ones** (a round that raised 3 and refuted all 3 owes the next round; the loop, not the checklist, decides when hunting stops). A quiet round alone is still not sufficient — every lens must ALSO be adjudicated (a quiet sample from finders that looked at too little proves nothing). **Minimum two full rounds, ALWAYS** (the round that first completes the lenses is never the exit round — a fresh round must re-adjudicate them); the pass that produced a fixup is never the last look at the lenses it touched. **There is NO round ceiling** — while anything is still being raised, the next round is owed; the run loops until the exit holds. The ONLY non-quiet stop is the command's own **BLOCKED escalation** (a finding surviving 3 consecutive fix attempts → pause that finding, Telegram the operator, keep looping the rest) — never a self-declared residual. Keep the `found:`/`fixed:` ledger per round (`found` counts refuted candidates too).

**Anti-cheat (mechanical, not vibes) — the SET hash** `[canonical: /fabrik-plan-review's combined-hash rule — same machinery, same reason]`: record the epic set's combined hash at the **start and end of every round**:

```bash
find docs/development/epics -name '*.md' -print0 | sort -z | xargs -0 md5sum | md5sum
```

Fixups edit epic files, so a round that changed anything shows a different hash — which is exactly why **the exit round must show `md5(start) == md5(end)`** on top of its quiet ledger: identical hashes prove the final round was genuinely edit-free rather than asserted so. A quiet ledger with a moved hash is a round that fixed something and called itself quiet — run the next round. Record both hashes per round in the ledger; the Step-4 report's `Surface:` line carries the final hash, and `check_review_coverage.py` refuses the report without it.

### Step 4: Report + Hand Off

**PERSIST the report FIRST, then post it.** The report is written to
`docs/development/reviews/YYYY-MM-DD-mega-<vision-slug>-validation-review.md` — Telegram is the
notification, the file is the record. ⚠️ This is not bookkeeping, it is the enforcement seam: a
report that only went to Telegram is invisible to every gate, which is precisely how this
command's exit went un-policed until 2026-08-16 (`/fabrik-plan-review`'s exit is read by
`check_convergence.py`; this one was read by nobody). `check_review_coverage.py` (run by
`final_gate` and the Stop hook) now enforces the persisted report's grammar:

- a `Surface:` line at column 0 carrying the **final SET hash** from Step 3's anti-cheat;
- the **per-round `found:`/`fixed:` ledger with each round's start/end hash** — minimum two
  rounds, final round `found: 0, fixed: 0` with `md5(start) == md5(end)`;
- **every lens line adjudicated** — no `[PASS]`/`[N]`/`[list]` template placeholders may survive
  into the persisted report (a placeholder is a lens nobody adjudicated wearing a verdict's
  clothes);
- `Status: IN-PROGRESS` at column 0 is the sanctioned escape for a run interrupted mid-loop —
  never a way to ship an unconverged set.

Then post the same report to the Telegram digest (not a per-finding prompt):

```markdown
# Cross-Epic Validation Report
Surface: <final combined md5 of docs/development/epics/*.md — from Step 3's anti-cheat>

Rounds (found counts refuted candidates too; hashes from the Step-3 anti-cheat):
| round | found: | fixed: | md5(start) → md5(end) |
|------:|-------:|-------:|---|
| 1 | found: 7 | fixed: 6 | a1b2… → 9f8e… |
| 2 | found: 0 | fixed: 0 | 9f8e… → 9f8e… ✓ |

## Feature Coverage: [PASS] — [N] features across [M] epics · orphans: none · duplicates: none
## Epic Tickets: [PASS] — per-epic verdict with evidence
## Dependency Graph: [PASS] — no cycles · roots: [list] · parallel lanes: [list] (disjoint paths verified)
   Critical path: Epic 1 → 3 → 5 (3 deep) · SPLIT-CANDIDATE stated on each
## Infrastructure Decisions: [PASS] — no contradictions, no missing sections
## Handoff Readiness: [PASS] — 15-field Metadata complete; Registrars match Shape; ports free in PORTS.md
## Overall: PASS  ·  Fixups this run: [N]  ·  Routed back: [none / list]
## Recommended Execution Order  (topological phases; `⚡` = parallel within a phase)
Phase 1 (root): Epic 1 ⚡ Epic 2   Phase 2: Epic 3   …
(single-epic: `Phase 1: Epic 1 — [name] (atomic — no phasing required).`)
```

⚠️ **Generate the `## Recommended Execution Order` in CODE, do not hand-derive it** `[canonical: north-star R8/D4]` — the topological phases come from the same script that gated integrity:

```bash
python /opt/fabrik/scripts/epic_order.py --json --epics-dir docs/development/epics
```

Paste its `phases` into the report verbatim. It is deterministic over `depends_on`/`parallel_with`, so the order is reproducible and driver-consumable — not a per-run judgement.

**Hand off.** At the adjudicated exit, dispatch is not a command that renders instructions; it is:
- **In Traycer / the cockpit** — the operator **clicks an epic card** (mirrored by `03` via `traycer_mirror.py`), which opens the epic-to-ticket workflow for that epic in `consume` mode. The card carries the epic's `owned_paths` as the executing agent's File Scope.
- **Headless / the driver** — the driver reads `epic_order.py --json` and enqueues each phase in order (parallel `⚡` epics concurrently), running `epic-to-ticket-workflow/00-trigger-fabrik` (consume mode) per epic.

A route-back instead hands to `02`/`03`/`00` and re-enters here after they re-emit.

## Does NOT

- **Re-cut epic boundaries or re-derive the vision** — it validates what exists; boundary changes route to `02-epic-decomposition-fabrik` (then `03`).
- **Write epic content itself** — **Opus never writes `docs/development/epics/`**. A *surgical* edit is the dispatched fixup agent's job (Step 3); a *re-creation* after a boundary route-back is `03-expand-epic-files-fabrik`'s.
- **Stop and wait for the owner on a finding** — the operator agreed to the decomposition at `02`; drift is handled by fixup + re-dispatch + re-review. Only the 3 BLOCKED cases pause a thread (via Telegram).
- **Take a ticket's word** — every PASS is grounded in the real repo (`PORTS.md`, `infrastructure.py`, the rule packs), never the ticket's own claim.
- **Rely on conversation memory or a Traycer store** — tickets are FILES; read them fresh with Glob/Read. There is no `read_spec`/`read_ticket` here.
- **Dispatch the epics** — dispatch is the cockpit card-click / the driver's phase queue (`05-dispatch` retired); this command only converges the set and emits the code-generated order.
- **Validate rule-pack CONTENT** — it verifies the `Rule Packs` field propagates and that a cited pack exists; the pack semantics are the producer commands' job.
- **Apply a blanket 4-stage expectation to a Retrofit epic** — a Retrofit on a deployed service owns no Stage-1/Stage-3 (Core Philosophy).
- **Run `git commit` / `push`** — `scripts/final_gate.py` auto-stages on success (CLAUDE.md HARD STOPS).

## Acceptance Criteria

- Every epic ticket read as a FILE from `docs/development/epics/` (Glob/Read); the specs read fresh — never from memory or a Traycer store.
- Review dispatched through `libs/subagents` — **pool `fanout("review")` recording the flywheel AND ≥1 native `fabrik-reviewer` on Opus** — across every report lens, with Opus refuting/merging/deciding.
- Feature coverage (delta + `R`-prefixed alike), ticket structure (incl. all 5 `Dependencies` sub-bullets with a real `Owned paths`), graph (cycles, roots, **disjoint parallel paths**, **single migration owner**, consumed artifacts, critical path + SPLIT-CANDIDATE, minimality), Infrastructure Decisions (+ the Deferred Compliance appendix in EXISTING mode), and handoff readiness (15 fields; **`Registrars` ↔ `Shape`**; `Port` free in `PORTS.md`) all verified — each binary with `path:line` evidence.
- Findings handled **autonomously**: surgical fixups dispatched (pool `pick_models("docs"/"spec")` or `claude -p`), re-reviewed, **looping to the lens-adjudicated exit (min-2 rounds, no ceiling)**; boundary/scope changes routed to `02`/`03`; a corrupted Vision Summary to `00`; only the 3 BLOCKED cases pause (Telegram).
- Epic-count sanity surfaced (3–7 typical; 10+ or 2 remarked, never a silent pass).
- Ticket-set integrity gated in code (`epic_order.py --check --expected-count`, folded from retired `05`) before the review lenses run.
- The exit report emits the code-generated topological execution order (`epic_order.py --json`) for the cockpit (card-click) / driver (phase queue) to dispatch — `05-dispatch` retired.

---

**Next (CC1 pairing, north star § Command-chain build plan):** `04` **is** the mega chain's cross-epic review — the analog of ettw `10` `[canonical: north star § Command-chain build plan — CC5, "10-cross-artifact-validation is the cross-cutting integration review"]`. It is a review twin, so it has **no downstream paired review**: it self-converges via its own finder loop (which is also why it is not a `type` in `/fabrik-workflow-review`, whose types are the producer doers). It also **absorbs the retired `05`**: ticket-set integrity (Step 1.5) + the code-generated execution order (Step 4) are now `04`'s, run via `scripts/epic_order.py`. At the adjudicated exit → cockpit card-click / driver phase-queue dispatch; a route-back re-enters via `02`/`03`/`00`.
