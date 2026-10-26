---
description: Converge a cut epic set to a fixed point — the review twin of /fabrik-epics. Integrity + owner assignment run in CODE first (`epic_order.py --check` → `--assign <names>` → `--check --owners`), then rubric-armed lenses (features · ticket structure · graph + disjoint owned_paths · infra decisions · handoff) with dispatched fixups, looping to a hash-proven quiet round; persists the Cross-Epic Validation Report and names every window's /fabrik-spec launch. TRIGGER — EN: "validate the epics", "are the epics ready to build"; TR: "epikleri doğrula", "epikler yapıma hazır mı". SKIP: cutting the epics (→ /fabrik-epics) · one epic's own design (→ /fabrik-spec). Stage: 1-design.
argument-hint: "[<agent names, comma-separated — agent-1 FIRST (the merge owner, this window), e.g. alpha,beta,gamma> [--expected-count <N — the epic count in /fabrik-epics' persisted epic-proposal spec>]]"
---

# Cross-Epic Validation — converge the epic set, assign its owners

> **⚠️ POOL OFF — D-181.** Run every fan-out this command names NATIVELY — Claude Task subagents (`fabrik-reviewer` · `fabrik-researcher` · `fabrik-gui` · general-purpose): same unit split, same author-blind rule, same decide/refute/merge by you. A suspended `fanout` REFUSES with a `ValueError` if two units name the same path; never hand-roll run_agents + record_run. Never write `NO-POOL:` for it: `check_subagent_flywheel.py`'s pool-or-declare layer stands down by the same ruling (`_POOL_POLICY_ON = False`, D-182). Canonical: `62-using-subagents.md` § Dispatch policy.

You are the **cross-epic (epic-set) review orchestrator** — agent-1's session, in the main checkout, the window that will later own the merges. After `/fabrik-epics` writes one file per epic, read the whole decomposition and prove it ready to execute: every feature covered exactly once, no broken or invented dependencies, disjoint parallel lanes, one named owner per epic, each ticket self-sufficient for its window's corpus chain. Dispatch reviewer agents to find seam defects and fixup agents to close them. It halts only on the 3 BLOCKED cases. It writes no epic content itself; the fixup agents do (Phase 4).

{{include:run-record}}
{{include:orient}}
{{include:term-edit}}

## Phase 0 — Reads budget, orientation, and the owner set

**Reads budget.** The list below is the **acting set** — open these, this run, before you act. Every OTHER backticked path is provenance for a decision already stated inline — act on the inline sentence; open the source only if that sentence is insufficient to act on (and if it IS insufficient, that is a defect in THIS command — report it, don't silently absorb an extra read). Editing this source: every change passes `docs/orchestrator/mega-epic-breakdown/EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md`.

**Acting set:**
- The **epic ticket FILES** — `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md`. Enumerate with Glob and read every one fresh; a ticket validated against your memory of it is how a stale ticket passes.
- The **Vision Summary** (`docs/superpowers/specs/YYYY-MM-DD-<project>-vision.md`) — its `## Full Feature Inventory` and, in EXISTING mode, its `## Compliance Report`.
- The **Infrastructure Decisions** spec — `docs/superpowers/specs/YYYY-MM-DD-<project>-infrastructure-decisions.md`; it carries `## Deferred Compliance (not actioned this run)` (lens D's source) and the **Dependency Graph** mermaid.
- The **epic-proposal spec** — `docs/superpowers/specs/YYYY-MM-DD-<project>-epic-proposal.md`; its epic count is Phase 2's `--expected-count` (the file count under `docs/development/epics/` is never that number).
- `PORTS.md` — a `Port` claim is checked against it, not eyeballed.
- `src/fabrik/orchestrator/infrastructure.py` — the applicability matrix, to check `Registrars` ↔ `Shape`.
- `.windsurf/rules/**` — existence check only, to confirm a cited `Rule Packs` entry is real.
- `docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md` — the typed frontmatter `scripts/epic_order.py` reads.
- During fixup — each returned agent's diff + its `final_gate.py --json` output.

**The owner set (from the argument).** The operator names this run's agents, **agent-1 FIRST** (the merge owner and the main-checkout window); agents 2..N are worktree windows. Names must match `[a-z0-9-]{1,32}` (`epic_order.py` validates them before touching any file — a bad name is a usage error, exit 2). No names given → ask once (the question bar below); never invent a set. Record the set, in order — Phase 5 carries it into the report and the hand-off.

## Core philosophy

- **Read the ticket FILES from disk — never conversation memory.** Enumerate with Glob; read every one fresh, every round.
- **Every finding is binary + evidenced** — PASS/FAIL with the specific `path:line` (or the two contradicting tickets). No "looks good."
- **Verify, don't take the ticket's word.** A ticket that *claims* `needs_database: true` is checked against whether it *lists* the postgres registrar; a cited pack is confirmed to exist.
- **Surgical fix here; boundary re-cuts route back.** A missing Metadata field, a wrong title format, an absent `Owned paths` → a scoped fixup, dispatched and re-reviewed. A change to the epic **boundaries** (orphans, duplicates, a wrong split, shared `owned_paths` between parallel epics) → route to `/fabrik-epics`, which re-cuts and re-writes; this command never re-cuts epics.
- **The only cases that PAUSE a finding are the 3 BLOCKED cases** (CLAUDE.md § Behavior): 3 consecutive same-test failures on one fixup · missing infra · an unresolvable spec contradiction. On any → state `BLOCKED: <what> — searched: <sources> — missing: <need>`, persist the report `Status: IN-PROGRESS` with its `## BLOCKED:` line filled, pause THAT finding, continue the rest; when nothing else remains, close the run record with `blocked`. ⚠️ A **missing or corrupt upstream artifact is a ROUTE-BACK, not a halt** — hand it to `/fabrik-vision` (the Vision Summary) or `/fabrik-epics` (a ticket, the Infrastructure Decisions file, the graph), which re-emit, and re-enter here.
- **Flavour-aware staging** — a **delta-feature** epic must pass all four stages (scaffold → implement → `fabrik apply` → `fabrik verify`); a **Retrofit** epic on an already-deployed service creates **no new deploy unit**, so it owns no Stage-1/Stage-3; validate each epic against the stages its **flavour** actually owns, never a blanket four. *(`docs/operations/fabrik-lifecycle.md` covers only stages 3–4 and carries no stage model, so it cannot settle this; the flavour rule above does.)*

## Output contract

The Cross-Epic Validation Report (structure in Phase 5), PERSISTED to `docs/development/reviews/YYYY-MM-DD-mega-<vision-slug>-validation-review.md` at the adjudicated exit. **Structure-bounded, NOT token-capped**: a numeric budget would only force harmful truncation of exactly the failures the owner most needs to see. Do not add one. The result is the adjudicated verdict — every report lens PASS-with-evidence, with the round ledger, fixup count, route-backs, owner set and per-window next step; never a bare defect list.

## Phase 1 — Rule-grounding gate + read all artifacts

{{include:grounding-rules}}

⚠️ **Constraints-Digest citation (BINDING):** every architecture, tool, or dependency selection in this
command cites a row of the upstream CONSTRAINTS DIGEST or states `unconstrained`; a selection that collides
with a digest row is DEAD. If no digest artifact exists upstream, STOP — run the Rule-grounding gate above
before proceeding. fabrik-lib verdicts follow the same law: vendor/wrap/build cited, never assumed.

**Read all artifacts.** Glob `docs/development/epics/*.md` and read every ticket in full; read the Vision
Summary + Infrastructure Decisions + Dependency Graph. **If any is missing, do not review — ROUTE BACK**
(not a halt): state which, hand to the creating command (`/fabrik-vision` for the Vision Summary;
`/fabrik-epics` for the decomposition, a ticket, the graph, **or the Infrastructure Decisions FILE**), and
re-enter here once it re-emits. State: *"Read the Vision Summary + Infrastructure Decisions and [M] epic
tickets; owner set: <names>."*

## Phase 2 — Step 1.5: ticket-set integrity + owner assignment, in CODE

Ticket-set integrity is the deterministic gate `scripts/epic_order.py`. The script is HUB-ONLY (no synced copy), so it is always invoked by its hub path. **Three commands, in this order, and the order is the point:** `--check` proves integrity, `--assign` writes the owners, `--check --owners` proves the assignment — so the owner row can never fail on a first pass, and no lens ever runs over an unassigned or broken set.

**2a — integrity:**

```bash
python3 /opt/fabrik/scripts/epic_order.py --check --expected-count <N — the epic count in /fabrik-epics' persisted epic-proposal spec> \
        --epics-dir docs/development/epics
```

- **PASS (exit 0, `INTEGRITY: PASS`)** → 2b.
- **FAIL (exit 1, `INTEGRITY: FAIL` + one line per finding)** → **STOP on the findings. `--assign` is NEVER invoked over a failing set** (it would refuse anyway — exit 1, no file touched — but the refusal is the machinery's backstop, not your plan). Route by cause, off the machine verdict, not a hand diff:
  - *count mismatch / missing number* → `/fabrik-epics` to recreate ONLY the named epic(s).
  - *duplicate epic number* → the older date-prefix file is stale → `rm` it, then re-enter.
  - *no frontmatter / bad title / bad `epic_n` / duplicate `owner:` line / a block list under a scalar field* → `/fabrik-epics` (it must emit the epic-artifact schema).
  - *overlapping `owned_paths` in one `phased_order()` phase*, or *two migration owners in one phase*, or *a `depends_on` CYCLE* → boundary re-cut → `/fabrik-epics`. Epics in DIFFERENT phases never run concurrently and are not compared. The check cannot see two globs that intersect without either containing the other (`src/*/handlers.py` against `src/api/*`), so lens C's disjointness row still intersects the real paths itself.
  - *the frontmatter graph disagrees with itself or the body* → `/fabrik-epics`.
  - Re-run this gate after any fix — a recreated ticket has never passed integrity.

The `--expected-count` read from the epic-proposal spec IS the count-match, in code; the Glob file count is a fact, never the epic count, and is never taken AS the epic count (that is exactly the deficit a file count cannot see).

**2b — assign the owners (the operator's names, agent-1 first):**

```bash
python3 /opt/fabrik/scripts/epic_order.py --assign <alpha,beta,gamma> --epics-dir docs/development/epics
```

- Round-robin over `phased_order()`; it writes `owner: <name>` into each file's frontmatter and prints `ASSIGN: OK`.
- It refuses (`ASSIGN: REFUSED`, exit 1, no file touched) when integrity reports any finding OTHER than the owner-membership class `--check --owners` adds (that class is exactly what 2b exists to clear — a set with empty `owner:` fields is assignable, not refused) — an EMPTY `--epics-dir` included (nothing to assign is a refusal, never a vacuous OK). A refusal after a PASS at 2a is a defect in the machinery: file it (§ Close-out feedback), never hand-edit `owner:` around it.
- A MISSING or misspelled `--epics-dir` is not a refusal at all — it is a usage error (exit 2): fix the path and re-run, file nothing. So is a FIRST name that cannot be the merge owner (`undeclared`, or one opening with `-`): put another agent first and re-run.
- `--assign` is its own action — it cannot be combined with `--check` or `--json`. Re-run 2b after any route-back that recreated a file (the recreated ticket carries `owner: ""`).
- After `--assign` succeeds, run `python3 /opt/fabrik/scripts/decisions.py --merge-owner .`; when it prints `UNDECLARED` (exit 3), mint the `MERGE OWNER: <first name>` row in `docs/DECISIONS.md` — id via `python3 /opt/fabrik/scripts/decisions.py --reserve-id .` — in the same change (D-154).

**2c — prove the assignment:**

```bash
python3 /opt/fabrik/scripts/epic_order.py --check --owners <alpha,beta,gamma> \
        --expected-count <N> --epics-dir docs/development/epics
```

- **PASS** → every epic carries exactly one `owner` ∈ the named set → Phase 3. State: *"Integrity PASS · assigned <names> · owners PASS over [M] epics."*
- **FAIL** → an owner missing or outside the set, or a 2a-class finding that appeared between the two checks. Never edit `owner:` by hand; re-run 2a → 2b → 2c, and if the same finding survives three runs it is BLOCKED case 1.

Only after 2c passes does any lens run. The SET hash Phase 4 records at the start of round 1 is taken AFTER 2c, since `--assign` edits every epic file.

## Phase 3 — Dispatch the cross-epic review — reviewer agents, BOTH mechanisms

**ARM every reviewer FIRST:** run `python3 /opt/fabrik/scripts/review_rubric.py --changed <the epic files under review>` and **inject its output into every reviewer agent's prompt** as the rubric they hunt against. It carries **(1) the mandatory-core floor** — `core/35-security-auth` + `core/25-data-postgres` + `core/30-ops` + all twelve 12-Factor axes — always injected regardless of glob and never skippable, so the review is never un-armed on the high-blast-radius rules; **(2)** every pack whose glob matches a changed path (mandate lines only). No `--workflow` here: the `EVALUATION_CHECKLIST_*` authoring-QA injects only when a review's subject IS a command file, e.g. `/fabrik-workflow-review`.

Dispatch native seats (`core/62-using-subagents.md` § Dispatch policy):

- **Breadth** — one native `fabrik-reviewer` seat on Sonnet PER LENS, all dispatched in one message: the lens count is the PARTITION and `dispatch_headroom.py --units <N> --mechanical 0` prints the seats — stamped BEFORE they go out with `python3 scripts/command_run.py dispatch --seats <n>` (D-191 — a lens is a judgement, no Haiku mechanical seat), never a token 1–2.
- **≥1 native `fabrik-reviewer` on Opus** — the authoritative pass, owning the high-risk seams: parallel-set disjointness, the single-migration-owner rule, and `Registrars` ↔ `Shape`.

Each reviewer commits to a lens before seeing the others; **you refute/merge/decide**.

**A. Feature coverage** — map each feature of the Vision Summary's `## Full Feature Inventory` to the epic claiming it in `### Scope > In:`.

| Check | PASS | FAIL |
|---|---|---|
| Inventory present | section present AND ≥1 feature | missing/empty → route to `/fabrik-vision`, do NOT continue |
| Every feature assigned | all mapped (numbered delta features `1,2,…` AND EXISTING-mode Retrofit features `R1,R2,…`) | feature #X "[name]" in no epic |
| No feature in two epics | each in exactly one | #X claimed by Epic A and Epic B |
| No phantom features | epics contain only inventory features | Epic N claims "[name]" absent from the Vision Summary |

**B. Epic ticket structure** — per ticket:

| Check | PASS | FAIL |
|---|---|---|
| Title format | `Epic N — [Name]` exactly (em-dash, single spaces; optional `Retrofit:` prefix) | en-dash/hyphen/missing space/wrong number |
| `### Summary` · `### Scope` (In+Out) | present | missing |
| `### Success Criteria` — **by flavour** | delta-feature 5–8; **Retrofit 3–5** | below the per-flavour minimum |
| deploy/gate-level criterion | delta: "`fabrik apply` succeeds" or "/health 200". Retrofit: `scripts/final_gate.py` success + the Compliance-Report gap moving Partial/Violates → Compliant | neither flavour's criterion present |
| resilience criterion | delta: states what happens when a dependency is down. Retrofit: N/A **iff** the area is not resilience/external-call related | absent AND the epic IS resilience-related |
| `### Out of Scope` | present — other epics, vision-level exclusions, or an explicit `none — …` reason | missing, vague, OR cites a non-existent Epic N |
| `### Dependencies` — **all 5 sub-bullets** | `Consumes from prior epics` · `Produces for later epics` · `Depends on` · `Parallel with` · **`Owned paths`**, each with content or an explicit `none` reason. ⚠️ **`Owned paths` is NOT optional and `none` is NOT valid** — lens C intersects exactly this field | any sub-bullet missing/empty, OR `Owned paths` absent or `none` |
| Typed frontmatter ↔ body | `depends_on` / `parallel_with` / `owned_paths` equal the `### Dependencies` sub-bullets (`owner` lives in the frontmatter only and is Phase 2c's code verdict, never re-filed here) | they disagree — `epic_order.py` orders by the FRONTMATTER |
| `### Metadata` — **structure only** | all 15 rows present. ⚠️ **Field VALUES are lens E's authority, not B's** — do not judge them here | section missing, or fewer than 15 rows |
| Dependencies name artifacts | tables/functions/endpoints/env vars named (or explicit `none` for atomic-root / terminal-output epics) | vague only ("Epic 1's infrastructure") |
| Entry point | `Entry point: /fabrik-spec <this file>` | missing, or names anything else |

**C. Dependency graph** — cross-reference the graph against every `### Dependencies`. `/fabrik-epics` emits a **mermaid diagram with `subgraph "Phase N"` blocks**; prose instead → route to `/fabrik-epics`. Terminology is **`Phase`, never `Batch`** (consistent with `epic_order.py --json`). The mermaid is the human-readable twin of the machine truth — `epic_order.py` derives the phased order from the typed frontmatter, and the mermaid must not contradict it. **Epic-count sanity:** state the count + a one-line verdict — **3–7 typical**; accepted **E = 3–20**; **10+** ⇒ re-examine boundaries for layer-slicing, never re-cut by reflex; **2** ⇒ the vision may not need this workflow. A surfaced observation, not a hard FAIL — but never unremarked.

| Check | PASS | FAIL |
|---|---|---|
| No cycles | DAG validated | Epic A → B → A |
| Graph matches tickets | every dependency in the graph appears in a `### Dependencies` | Epic N depends on M but the graph omits it |
| Root epic(s) identified | ≥1 epic with no upstream | none |
| **Parallel lanes identified** | every set of epics with **no mutual dependency** is marked `Parallel with:` — this row DEFINES the input set the two rows below intersect | a mutually-independent pair left unmarked → the disjointness + migration gates never see it, and the owner loses free parallelism (mega checklist item 79) |
| **Parallel epics have DISJOINT `Owned paths`** | for every `Parallel with:` pair — and every same-phase pair in `epic_order.py --json`, marked or not — their `Owned paths:` intersected as PATHS yourself are empty; the body agrees with the frontmatter | A and B are parallel but both write `[glob]` → re-cut the boundary or make it sequential |
| **At most ONE migration owner per parallel set** | only one epic in a set owns `alembic/versions/**` / `db/schema.sql` | two parallel epics own migrations → concurrent Alembic heads wedge the deploy → the non-schema epic must `depends-on` the schema epic |
| Produced artifacts consumed | every `Produces` has a matching `Consumes` — N/A for a single-epic proposal and for terminal-output epics producing end-user output only | A produces X, nobody consumes it, epic count > 1, and X is internal |
| **CRITICAL PATH stated + matches** | a `Critical path:` line (e.g. `Critical path: Epic 1 → Epic 3 → Epic 5 (3 deep)`) consistent with the validated graph | missing or contradicts the graph → route to `/fabrik-epics` |
| **SPLIT-CANDIDATE per critical-path epic** | every critical-path epic carries `SPLIT-CANDIDATE: yes (<how>) / no (<why>)` | missing on any — a critical-path epic splittable into a blocking + non-blocking half **MUST** be split; that is the only way to shorten delivery |
| **Graph is MINIMAL** | every **sequential** pair has a stated artifact reason (`Consumes:` names what B takes from A); if epics CAN be parallel they MUST be | B `depends-on` A but consumes **nothing** → reclassify to parallel (then it must pass the two gates above) |

**D. Infrastructure Decisions** — read the spec; verify against the tickets.

| Check | PASS | FAIL |
|---|---|---|
| All shared decisions present | Database · Auth · Email · Background Processing · Embedding Model (if RAG) · Self-Healing Ladder (if `shape.kind ∈ {service, worker}`) · Watchdog Wiring (**ON by default** — the resolver reads the raw spec dict, `src/fabrik/orchestrator/infrastructure.py`; the `shape.kind` matrix in `core/60-watchdog.md` is **operator discipline, NOT code-enforced**) · Observability Defaults · Cost Guardrails (any paid-API use) · Backing Services · External Services · Domain Structure · Shared Env Vars · Shared Shape Decisions | missing section: [name] |
| Tickets reference, not duplicate | epics say "Inherited from Infrastructure Decisions" | Epic N re-defines [decision] differently |
| No contradictions | consistent across all tickets | Epic N says X, the spec says Y |
| **Deferred Compliance appendix** (EXISTING mode only) | if the Compliance Report has any `fix-later` / `accept-as-legacy` row, the spec's `## Deferred Compliance (not actioned this run)` section lists every one — those rows emit **no epic**, so it is their only carrier, and `/fabrik-epics` persists it into the Infrastructure Decisions spec's `## Deferred Compliance (not actioned this run)` section. N/A in NEW mode or when all rows are `fix-now` | such a row appears in no epic and no appendix → route to `/fabrik-epics` naming the cause: missing from the spec's section, or deferred by the owner but never surfaced (its compliance-rows step) |

**E. Handoff readiness** — each ticket must feed **`/fabrik-spec docs/development/epics/<this file>`**, the epic-file intake, which reads the ticket's 15-field Metadata as intake rows (every field, plus the derived Watchdog and LLM-gateway rows) and inherits the Vision's fabrik-lib Verdict + Rejected Alternatives without re-running the ladder. ⚠️ **The entry point is `/fabrik-spec <epic file>`, not a chat brief** — chat loses every Metadata field the intake would have pinned.

| Check | PASS | FAIL |
|---|---|---|
| `Port` | present **and not already allocated** — verify against `PORTS.md`, don't eyeball | missing, OR taken in `PORTS.md`, OR two epics claim the same port → route to `/fabrik-epics` |
| `target_vps` | `vps1`/`vps2`/`vps3` | missing |
| `Responsive` / `Dark+Light` | present AND the value **matches the feature trigger** — mandatory iff a GUI surface exists (a GUI scaffold, OR python-api/node-api/file-api with `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML) — the trigger is the GUI SURFACE, not the scaffold type; `N/A` only when no HTML/native UI exists | missing, OR `N/A — non-GUI scaffold` on an epic whose Shape has `is_admin_dashboard`/`is_public`+HTML |
| **`Registrars` ↔ `Shape`** — a SEMANTIC cross-check, not presence | every firing flag has its registrar listed: `needs_database`⇒postgres · `needs_cache`⇒redis · `has_persistent_data`⇒backrest · `has_search_feature`⇒meilisearch · **`is_public` AND `spec.domain`**⇒gatus · **`is_admin_dashboard` AND `spec.domain`**⇒authelia · **`exposes_metrics` AND `spec.domain`**⇒prometheus; plus **glitchtip** (`shape.kind ∈ {service, worker, wordpress}`), **grafana** (always) and **watchdog** (opt-OUT). ⚠️ `has_bearer_api` fires **no** registrar — only the Authelia `^/api/` bypass (`src/fabrik/orchestrator/infrastructure.py`) | the list contradicts `Shape` — e.g. `needs_database: true` but postgres absent: a silently-broken deploy, not a metadata gap → route to `/fabrik-epics` |
| the other **10** fields — present **and value-shaped** (not presence-only) | `Scaffold` · `Shape` · `Concurrency` · `i18n` · `Rule Packs` · `HAS_USER_GUIDE` ∈ {true,false} · **`Universal categories` = comma-separated 1–14, verbatim from `/fabrik-epics`' universal-categories step** · `Email` ∈ {transactional, marketing, two-stream, none, N/A} · `Abuse Detection` = `required` (SaaS w/ free tier) or `N/A — <reason>` · `FINANCIALS` = `required` (SaaS launch gate) or `N/A — <reason>` | missing: [name], **or present with an off-contract value** — a presence-only pass is the same regression this table flags for `Registrars` |
| Ticket is self-sufficient | the whole corpus chain for one window (`/fabrik-spec <epic file>` → `/fabrik-spec-review` → `/fabrik-features` → `/fabrik-flows` → `/fabrik-data-contract` → *(GUI)* `/fabrik-ui-design` → `/fabrik-plan-after-chat` → `/fabrik-plan-review` → `/fabrik-execute-plan`) runs from ONLY this ticket + the Infrastructure Decisions spec | needs context only the Vision Summary carries |

## Phase 4 — Converge to the closing round — fixup, don't stop

Classify every surviving finding, then handle it autonomously — everything short of a BLOCKED case:

- **Surgical ticket fix** (a missing Metadata field, a wrong title format, an absent `Owned paths`, an off-contract field value, a body that disagrees with its frontmatter) → a **scoped fixup ticket** naming the finding's `path:line` + the required value, **dispatched** to a native `general-purpose` seat — **one seat per epic file**, briefed to touch ONLY that file, so merge all of one file's findings into ONE seat — or a native Opus subagent for a high-risk one (e.g. a migration-owner correction). Re-read + re-review to confirm. ⚠️ **NOT** a `Registrars`↔`Shape` mismatch — lens E routes that to `/fabrik-epics`. ⚠️ A fixup never touches `owner:` — a fixup that needs a different owner is a boundary question.
- **Boundary / scope change** (orphans, duplicates, phantoms, a wrong split, shared `owned_paths` between parallel epics, a port re-allocation, a missing Infrastructure-Decisions **section** or **FILE**, a missing or incomplete `## Deferred Compliance (not actioned this run)` section) → **route back** to `/fabrik-epics`; re-enter at Phase 2 (a recreated ticket has never passed integrity and carries `owner: ""`). Never re-cut epics here.
- **Vision Summary corrupted** (lens A's inventory missing/empty) → route to `/fabrik-vision`; do NOT continue.
- **BLOCKED cases** — 3 consecutive same-test failures on one fixup → case 1; missing infra → case 2; unresolvable spec contradiction → case 3 — each handled as § Core philosophy states.

**LOOP:** every fixup dispatched → re-reviewed (Phase 3) → re-classified — **until every verdict lens of the Phase-5 report template carries an adjudicated PASS-with-evidence, with zero unresolved findings**. **The final round must itself be QUIET as the Termination contract above defines it — `confirmed: 0, fixed: 0, unexecuted: 0`; refuted and RECORDED candidates never count (D-206)** — with `found:` still written on the row as raw recall (`found:` is never 'fixed' to zero to please the gate). A quiet round alone is still not sufficient — every lens must ALSO be adjudicated (a quiet sample from finders that looked at too little proves nothing). **Minimum two full rounds, ALWAYS** (the round that first completes the lenses is never the exit round — a fresh round must re-adjudicate them); the pass that produced a fixup is never the last look at the lenses it touched. **There is NO round ceiling.** The ONLY non-quiet stop is the command's own **BLOCKED escalation** (a finding surviving 3 consecutive fix attempts → pause that finding, keep looping the rest) — never a self-declared residual. Keep the fragment's Pass Ledger per round (`found:` counts every candidate raised, `confirmed:` only the ones that held).

**Anti-cheat — the SET hash:** record the epic set's combined hash at the **start and end of every round** — round 1's start is taken AFTER Phase 2c:

```bash
find docs/development/epics -name '*.md' -print0 | LC_ALL=C sort -z | xargs -0 md5sum | md5sum
```

(`LC_ALL=C` is load-bearing: the gate recomputes this hash in byte order, and a locale-sorted hash reads as "never computed".)

Fixups edit epic files, so the exit round **must show `md5(start) == md5(end)`** on top of its quiet ledger: identical hashes prove the final round was genuinely the closing round (`confirmed: 0`) rather than asserted so; a quiet ledger with a moved hash is a round that fixed something and called itself quiet — run the next round. **Record hashes IN FULL (all 32 hex chars), per round, and let them CHAIN**: round N's `md5(end)` must equal round N+1's `md5(start)` (a gap means the set changed between reviewed rounds, off the books), and the Phase-5 report's `Surface:` line carries the final `md5(end)` verbatim. `check_review_coverage.py` machine-verifies it and recomputes the live epic-set hash against `Surface:`; truncated hashes fail.

## Phase 5 — Report + hand off

**PERSIST the report FIRST** to `docs/development/reviews/YYYY-MM-DD-mega-<vision-slug>-validation-review.md` — the file is the record. ⚠️ **The filename and the H1 are a CONTRACT.** `check_review_coverage.py` routes a report through the cross-epic grammar by exactly two keys — the H1 `# Cross-Epic Validation Report` as the file's first line (a vision suffix after it is allowed) OR the reserved filename suffix `mega-<slug>-validation-review.md`; lose BOTH and the report silently falls through to the ordinary review grammar. Either key alone still routes it (the filename key exists precisely so a mega-shaped name can never route weaker, whatever its title says). Carry both, always. A report that lives only in chat is invisible to every gate. The grammar it enforces:

- a `Surface:` line at column 0 carrying the **final SET hash** from Phase 4;
- the **per-round ledger with each round's start/end hash** — minimum two rounds, final round `confirmed: 0, fixed: 0` (with `found:` on the row) and `md5(start) == md5(end)`; that TABLE is the report's ONLY counter table, and no Pass-style prose counter lives outside it;
- **every lens line adjudicated** — no `[PASS]`/`[N]`/`[list]` template placeholders may survive into the persisted report;
- `Status: IN-PROGRESS` at column 0 **within the report's first 10 lines** is the sanctioned escape for a run interrupted mid-loop or paused on a BLOCKED finding — never a way to ship an unconverged set. Below line 10 it is ignored, deliberately.

The template:

```markdown
# Cross-Epic Validation Report
Surface: <final md5(end), FULL 32 hex — from Phase 4's anti-cheat, never truncated>
Status: <omit when converged; `Status: IN-PROGRESS` for an interrupted or BLOCKED run — the gate reads this ONLY from the report's first 10 lines, which is why its slot is here>
## BLOCKED: <finding> — attempts: 3 · <what · searched · missing>   (only on a Status: IN-PROGRESS report; omit when converged)

Rounds (the fragment's counters; FULL hashes, chained — round N's end = round N+1's start):
| round | counters | md5(start) → md5(end) |
|------:|---|---|
| Pass 1 | found: 7, new: 7, confirmed: 6, fixed: 6, unexecuted: 0 | <32-hex-A> → <32-hex-B> |
| Pass 2 | found: 1, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | <32-hex-B> → <32-hex-B> |

## Feature Coverage: [PASS] — [N] features across [M] epics · orphans: none · duplicates: none
## Epic Tickets: [PASS] — per-epic verdict with evidence
## Dependency Graph: [PASS] — no cycles · roots: [list] · parallel lanes: [list] (disjoint paths verified)
   Critical path: Epic 1 → Epic 3 → Epic 5 (3 deep) · SPLIT-CANDIDATE stated on each
## Infrastructure Decisions: [PASS] — no contradictions, no missing sections
## Handoff Readiness: [PASS] — 15-field Metadata complete; Registrars match Shape; ports free in PORTS.md
## Overall: PASS  ·  Fixups this run: [N]  ·  Routed back: [none / list]
## Recommended Execution Order  (topological phases; `⚡` = parallel within a phase)
Phase 1 (root): Epic 1 ⚡ Epic 2   Phase 2: Epic 3   …
## Owner set (agent-1 first): alpha, beta, gamma — `epic_order.py --check --owners` PASS over [M] epics
## Next per window
alpha (agent-1, main checkout — this window):            /fabrik-spec docs/development/epics/<epic-1 file>
beta  — `CLAUDE_AGENT=beta claude --worktree beta -n beta-<repo>`   → /fabrik-spec docs/development/epics/<epic-2 file>
```

⚠️ **Generate the `## Recommended Execution Order` in CODE, do not hand-derive it:**

```bash
python3 /opt/fabrik/scripts/epic_order.py --json --epics-dir docs/development/epics
```

Paste its `phases` into the report verbatim. `## Owner set` and `## Next per window` are derived the same way: each epic's `owner:` (read from its frontmatter, never from memory of 2b) joined onto those phases, the owner set in the operator's order — agent-1 = the first name.

**Hand off — EVERY window gets its line:**

- **agent-1** stays in the **main checkout** and runs `/fabrik-spec docs/development/epics/<its epic>.md` on its Phase-1 epic. It is also the merge owner: finished branches merge into master in `epic_order` phase order, one at a time, through `scripts/merge_request.py merge` (a refused requester brings the base in by merging it into its pushed branch, never a rebase), and it runs the tail after the last merge (`/fabrik-features` REFRESH → `/fabrik-conformance-review` when E ≥ 2 → certification → `/fabrik-deploy-checklist` → `/fabrik-release`).
- **agents 2..N** each launch `CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>` and run `/fabrik-spec docs/development/epics/<its epic>.md` on their Phase-1 epic; later-phase epics wait for the phase before them to merge, and are named on the same line.
- Epics in the same phase run **concurrently, one per named agent**; an agent with no Phase-1 epic starts on its first later-phase epic only when that phase opens.

## Does NOT

- **Re-cut epic boundaries or re-derive the vision** — boundary changes route to `/fabrik-epics`.
- **Write epic content itself** — **the orchestrator never writes `docs/development/epics/`**; a *surgical* edit is the dispatched fixup agent's job, an `owner:` value is `epic_order.py --assign`'s.
- **Expect a paired review of its own** — this command IS the review twin of `/fabrik-epics` and self-converges via its own finder loop.
- **Stop and wait for the owner on a finding.** Only the 3 BLOCKED cases pause a finding.
- **Take a ticket's word** — every PASS is grounded in the real repo, never the ticket's own claim.
- **Start any epic's own chain** — this command names the dispatch per window and never runs a window's work.
- **Validate rule-pack CONTENT** — it verifies only that the `Rule Packs` field propagates and a cited pack exists.
- **Hand-edit `owner:`, or run `--assign` over a set that failed `--check`** — a refusal is a finding to file, not a field to type.
- **Push the DEFAULT branch from a worktree, or commit files you did not author** — commit with explicit pathspecs + Agent Provenance Trailers and push the CURRENT branch.

## Acceptance criteria

Every epic ticket read as a FILE (Glob/Read), the specs read fresh — never from memory; integrity gated in code BEFORE any assignment, `--assign <names>` never invoked over a failing set; every epic carrying exactly one `owner` ∈ the operator's set, proven by `--check --owners <names>` BEFORE any lens ran, the merge-owner ledger row present or minted; one Sonnet `fabrik-reviewer` seat per lens AND ≥1 on Opus; all five lenses verified with `path:line` evidence; findings fixed autonomously, looping to the lens-adjudicated exit (min-2 rounds, no ceiling, chained full hashes), only the 3 BLOCKED cases pause a finding; epic-count sanity surfaced, never a silent pass; the report persisted under the H1 `# Cross-Epic Validation Report`, gated green by `check_review_coverage.py`, with the code-generated execution order, the owner set and one `/fabrik-spec` line per window.

{{include:questionbar}}


{{include:subagents-core}}

{{include:close-chain}}
