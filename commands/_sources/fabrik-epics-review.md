---
description: Converge a cut epic set to a fixed point — the review twin of /fabrik-epics. Integrity + owner assignment run in CODE first (`epic_order.py --check` → `--assign <names>` → `--check --owners`), then rubric-armed lenses (features · ticket structure · graph + disjoint owned_paths · infra decisions · handoff) with dispatched fixups, looping to a hash-proven quiet round; persists the Cross-Epic Validation Report and names every window's /fabrik-spec launch. TRIGGER — EN: "validate the epics", "are the epics ready to build"; TR: "epikleri doğrula", "epikler yapıma hazır mı". SKIP: cutting the epics (→ /fabrik-epics) · one epic's own design (→ /fabrik-spec). Stage: 1-design.
argument-hint: "[<agent names, comma-separated — agent-1 FIRST (the merge owner, this window), e.g. alpha,beta,gamma> [--expected-count <N — the epic count in /fabrik-epics' persisted epic-proposal spec>]]"
---

# Cross-Epic Validation — converge the epic set, assign its owners

You are the **cross-epic (epic-set) review orchestrator** — agent-1's session, in the main checkout, the
window that will later own the merges. After `/fabrik-epics` writes one file per epic, this command reads
the **whole decomposition** and proves it is ready to execute: every feature covered exactly once, no
broken or invented dependencies, disjoint parallel lanes, one named owner per epic, each ticket
self-sufficient for its window's corpus chain. It dispatches reviewer agents to find seam defects and
fixup agents to close them, and **runs the epic set to its lens-adjudicated exit — it does not stop and
ask** except on the three BLOCKED cases. It writes no epic content itself; the fixup agents do (Phase 4).

**Why a converging review, not an audit.** `/fabrik-epics` produces; a single PASS/FAIL pass would hand
the owner a defect list and stop. A doer produces, a separate review forces the no-op — this command
converges the artifact set instead. It is AUTONOMOUS: the operator already agreed to the decomposition at
`/fabrik-epics`' checkpoint; there is no human step here (the two human gates are plan-in — the operator's
spec/plan approval upstream — and deploy-out, Gate 2). It halts only on the 3 BLOCKED cases.

{{include:run-record}}

## Phase 0 — Reads budget, orientation, and the owner set

**Reads budget (the hollow-citation discipline).** Every backticked path in this command is one of two
things: the list below is the **acting set** — open these, this run, before you act on anything. Every
OTHER backticked path is **provenance for a decision already stated inline** — act on the inline sentence;
open the source only if that sentence is insufficient to act on (and if it IS insufficient, that is a
defect in THIS command — report it, don't silently absorb an extra read). Editing this source: every
change passes `docs/orchestrator/mega-epic-breakdown/EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md`
(every applicable item — N/A is valid; forgetting to check is not; no hard-coded item count here).

**Acting set:**
- The **epic ticket FILES** — `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md`, written by
  `/fabrik-epics`. Enumerate with Glob and read every one fresh. They are FILES on disk — there is no
  ticket store and no conversation-memory copy; a ticket validated against your memory of it is how a
  stale ticket passes.
- The **Vision Summary** (`/fabrik-vision`'s persisted output at
  `docs/superpowers/specs/YYYY-MM-DD-<project>-vision.md`) — its `## Full Feature Inventory` and, in
  EXISTING mode, its `## Compliance Report`.
- The **Infrastructure Decisions** spec — decided and PERSISTED by `/fabrik-epics` to
  `docs/superpowers/specs/YYYY-MM-DD-<project>-infrastructure-decisions.md`; read it from disk (every
  ticket cites that path). It ALSO carries `## Deferred Compliance (not actioned this run)` — lens D's
  source for the `fix-later`/`accept-as-legacy` rows, which emit no epic and live nowhere else — plus the
  **Dependency Graph** (`/fabrik-epics`' mermaid, in its output).
- The **epic-proposal spec** — `/fabrik-epics`' persisted
  `docs/superpowers/specs/YYYY-MM-DD-<project>-epic-proposal.md`; its epic count is Phase 2's
  `--expected-count` (the file count under `docs/development/epics/` is never that number).
- `PORTS.md` — the port-allocation registry (a `Port` claim is checked against it, not eyeballed).
- `src/fabrik/orchestrator/infrastructure.py` — the applicability matrix, to check `Registrars` ↔ `Shape`.
- `.windsurf/rules/**` — existence check only, to confirm a cited `Rule Packs` entry is real.
- `docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md` — the typed frontmatter
  `scripts/epic_order.py` reads (`epic_n`, `depends_on`, `parallel_with`, `owned_paths`, `owner`, `title`).
- During fixup — each returned agent's diff + its `final_gate.py --json` output.

**The owner set (from the argument).** The operator names this run's agents, comma-separated, **agent-1
FIRST** — agent-1 is the merge owner and the main-checkout window (the one running this command); agents
2..N are worktree windows. Names must match `[a-z0-9-]{1,32}` (`epic_order.py` validates them before
touching any file — a bad name is a usage error, exit 2, nothing written). No names given → ask once
(the question bar below: the answer materially changes every `owner:` field and is derivable from
nothing on disk); never invent a set. Record the set, in order, in the run — Phase 5 carries it into the
report and the per-window hand-off.

## Core philosophy

- **Read the ticket FILES from disk — never conversation memory.** Enumerate with Glob; read every one
  fresh, every round.
- **Every finding is binary + evidenced** — PASS/FAIL with the specific `path:line` (or the two
  contradicting tickets). No "looks good."
- **Verify, don't take the ticket's word.** This command CAN open `PORTS.md`, the rule packs, and
  `src/fabrik/orchestrator/infrastructure.py`. A ticket that *claims* `needs_database: true` is checked
  against whether it *lists* the postgres registrar; a cited pack is confirmed to exist.
- **Surgical fix here; boundary re-cuts route back.** A missing Metadata field, a wrong title format, an
  absent `Owned paths` → a scoped fixup, dispatched and re-reviewed. A change to the epic **boundaries**
  (orphans, duplicates, a wrong split, shared `owned_paths` between parallel epics) → route to
  `/fabrik-epics` (which re-cuts and re-writes the affected files); this command never re-cuts epics.
- **The only cases that PAUSE a finding are the 3 BLOCKED cases** (CLAUDE.md § Behavior): 3 consecutive
  same-test failures on one fixup · missing infra · an unresolvable spec contradiction. On any → state
  `BLOCKED: <what> — searched: <sources> — missing: <need>`, persist the report `Status: IN-PROGRESS`
  with its `## BLOCKED:` line filled (the template's slot under `Status:`, Phase 5), pause THAT finding,
  continue the rest; when nothing
  else remains, close the run record with `blocked`. ⚠️ A **missing or corrupt upstream artifact is a
  ROUTE-BACK, not a halt** — hand it to `/fabrik-vision` (the Vision Summary) or `/fabrik-epics` (a ticket,
  the Infrastructure Decisions file, the graph), which re-emit, and re-enter here. Neither is a human stop.
- **Flavour-aware staging** — a **delta-feature** epic must pass all four stages (scaffold → implement →
  `fabrik apply` → `fabrik verify`); a **Retrofit** epic on an already-deployed service creates **no new
  deploy unit**, so it owns no Stage-1/Stage-3 — its Stage-3 equivalent is the gate + the compliance-row
  flip (`/fabrik-epics` § Success Criteria by flavour). Validate each epic against the stages its
  **flavour** actually owns, never a blanket four. *(deeper, optional: `docs/operations/fabrik-lifecycle.md`
  — it covers only stages 3–4 and carries **no** stage model, so it cannot settle this; the flavour rule
  above does.)*

## Input contract

**Required** — hard requirements, not preferences; if any is absent this command does not review, it
**routes back** (Phase 1):

- **Vision Summary** (`/fabrik-vision`) — its `## Full Feature Inventory` is lens A's yardstick; in
  EXISTING mode its `## Compliance Report` drives lens D's Deferred-Compliance check.
- **Infrastructure Decisions** spec (decided and persisted by `/fabrik-epics` at
  `docs/superpowers/specs/YYYY-MM-DD-<project>-infrastructure-decisions.md` — read it there; it also
  carries the `## Deferred Compliance (not actioned this run)` section lens D checks) + **Dependency
  Graph** (`/fabrik-epics`' mermaid) — lens D's and lens C's yardsticks.
- **Epic ticket FILES** (`/fabrik-epics`) — one per epic under `docs/development/epics/`; enumerate with
  Glob. The file count is a fact, never the epic count — Phase 2's `--expected-count` is the count-match.
- **The owner set** — the operator's agent names (Phase 0).

## Output contract

**Format:** the Cross-Epic Validation Report (markdown, structure in Phase 5), PERSISTED to
`docs/development/reviews/YYYY-MM-DD-mega-<vision-slug>-validation-review.md` at the adjudicated exit.
**Structure-bounded, NOT token-capped** (mega checklist item 93): a PASS/FAIL-row-per-check report is
already bounded by "fill this template once", so a numeric budget would only force harmful truncation of
exactly the failures the owner most needs to see. **Do not add one.**
**Result:** the adjudicated verdict — every report lens PASS-with-evidence, with the round ledger, fixup
count, any route-backs, the owner set and the per-window next step; never a bare defect list.
**Consumed by:** each window's `/fabrik-spec docs/development/epics/<its epic>.md` run (it reads its own
epic's `owner:`), agent-1's merge order (`epic_order.py --json` phases), or `/fabrik-vision` /
`/fabrik-epics` on a route-back.

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

Control flow in code, not prose. The ticket-set integrity — count-match against `/fabrik-epics`' proposal,
epic-number contiguity, duplicate/orphan detection, the parallel-set disjointness / single-migration-owner
proof, frontmatter shape — is the deterministic gate `scripts/epic_order.py`, run over the typed frontmatter
(`EPIC-ARTIFACT-SCHEMA.md`). The script is HUB-ONLY (no synced copy), so it is always invoked by its hub
path. **Three commands, in this order, and the order is the point:** `--check` proves integrity,
`--assign` writes the owners, `--check --owners` proves the assignment — so the owner row can never fail
on a first pass, and no lens ever runs over an unassigned or broken set.

**2a — integrity:**

```bash
python3 /opt/fabrik/scripts/epic_order.py --check --expected-count <N — the epic count in /fabrik-epics' persisted epic-proposal spec> \
        --epics-dir docs/development/epics
```

- **PASS (exit 0, `INTEGRITY: PASS`)** → 2b.
- **FAIL (exit 1, `INTEGRITY: FAIL` + one line per finding)** → **STOP on the findings. `--assign` is
  NEVER invoked over a failing set** (it would refuse anyway — exit 1, no file touched — but the refusal
  is the machinery's backstop, not your plan). Route by cause, off the machine verdict, not a hand diff:
  - *count mismatch / missing number* (deficit) → `/fabrik-epics` to recreate ONLY the named epic(s); do
    not discard the rest.
  - *duplicate epic number* (stale/redundant copy) → the older date-prefix file is stale → `rm` it, then
    re-enter.
  - *no frontmatter / bad title / bad `epic_n` / duplicate `owner:` line / a block list under a scalar
    field* → `/fabrik-epics` (it must emit the epic-artifact schema).
  - *overlapping `owned_paths` in one `phased_order()` phase* — intersected as realised PATHS, not glob
    strings: `src/app/**` against `src/app/models/**` overlaps; `libs/**/a/**` against `libs/**/b/**` does
    not; epics in DIFFERENT phases never run concurrently and are not compared — *or two migration owners
    in one phase, or a `depends_on` CYCLE* (a named finding, rc 1) → boundary re-cut → `/fabrik-epics`.
    A PASS here proves every same-phase lane disjoint under the two predicates the check runs —
    realised-file intersection + glob subsumption. The class it cannot see before the code exists is two
    globs that intersect without either containing the other (`src/*/handlers.py` against `src/api/*`
    passes rc 0 until `src/api/handlers.py` is created) — so lens C's disjointness row still intersects
    the real paths itself, over every same-phase pair, marked or not.
  - *the frontmatter graph disagrees with itself or the body* — `depends_on` naming an unknown epic ·
    `parallel_with` naming itself · `parallel_with` naming an unknown epic · `parallel_with` contradicting
    `phased_order()` → `/fabrik-epics` (it re-emits the graph and the affected files together).
  - Re-run this gate after any fix — a recreated ticket has never passed integrity.

The `--expected-count` — the epic count read from `/fabrik-epics`' persisted epic-proposal spec
(`docs/superpowers/specs/YYYY-MM-DD-<project>-epic-proposal.md`, in the acting set) — IS the chain's
count-match, in code; the Glob file count is never taken AS the epic count (that is exactly the deficit a
file count cannot see).

**2b — assign the owners (the operator's names, agent-1 first):**

```bash
python3 /opt/fabrik/scripts/epic_order.py --assign <alpha,beta,gamma> --epics-dir docs/development/epics
```

- Round-robin over `phased_order()` — each phase's epics handed to the names in `epic_n` order, the
  rotation continuing across phases — deterministic, balanced, no judgment; it writes `owner: <name>` into
  each file's frontmatter (after `owned_paths:`, the schema's field order) and prints `ASSIGN: OK`.
- Idempotent: a repeat over the same phased order changes no byte. It **refuses** (`ASSIGN: REFUSED`,
  exit 1, no file touched) when integrity reports any finding OTHER than the owner-membership class
  `--check --owners` adds (that class is exactly what 2b exists to clear — a set with empty `owner:`
  fields is assignable, not refused) — an EMPTY `--epics-dir` included (nothing to assign is a refusal,
  never a vacuous OK). A refusal after a
  PASS at 2a is a defect in the machinery: file it (§ Close-out feedback), never hand-edit `owner:`
  around it. A MISSING or misspelled `--epics-dir` is not a refusal at all — it is a usage error
  (`epic_order: no such dir: <path>`, exit 2, before any file is read): fix the path and re-run, file
  nothing.
- `--assign` is its own action — it cannot be combined with `--check` or `--json`.
- Re-run 2b after any route-back that recreated a file: the recreated ticket carries `owner: ""`.

**2c — prove the assignment:**

```bash
python3 /opt/fabrik/scripts/epic_order.py --check --owners <alpha,beta,gamma> \
        --expected-count <N> --epics-dir docs/development/epics
```

- **PASS** → every epic carries exactly one `owner` ∈ the named set (and the whole of 2a still holds) →
  Phase 3. State: *"Integrity PASS · assigned <names> · owners PASS over [M] epics."*
- **FAIL** → an epic whose owner is missing or outside the set, or a 2a-class finding that appeared
  between the two checks (a sibling session edited the tree — it runs several agents). Never edit
  `owner:` by hand; re-run 2a → 2b → 2c, and if the same finding survives three runs it is BLOCKED
  case 1.

Only after 2c passes does any lens run. The SET hash Phase 4 records at the start of round 1 is taken
AFTER 2c — `--assign` edits every epic file, and a hash taken before it would show the assignment as a
"fixup" nobody dispatched.

## Phase 3 — Dispatch the cross-epic review — reviewer agents, BOTH mechanisms

**ARM every reviewer FIRST (an un-armed reviewer measured ~0–22% defect recall):** run
`python3 /opt/fabrik/scripts/review_rubric.py --changed <the epic files under review>` and **inject its
output into every reviewer agent's prompt** as the rubric they hunt against. The rubric carries two layers:
**(1) the mandatory-core floor** — `core/35-security-auth` + `core/25-data-postgres` + `core/30-ops` + all
twelve 12-Factor axes — always injected regardless of glob and never skippable, so the review is never
un-armed on the high-blast-radius rules; **(2)** every pack whose glob matches a changed path (mandate
lines only). (No `--workflow` here: this command reviews the chain's runtime PRODUCTS — epics / artifacts —
not command files themselves; the `EVALUATION_CHECKLIST_*` authoring-QA injects only when a review's
subject IS a command file, e.g. `/fabrik-workflow-review`.) The whole rubric is computed fresh by the
script; nothing is inherited from the doer. Honesty: the injection STEP is maximally enforced (the rubric
is always injected); this raises compliance probability — it does **not** make compliance guaranteed.

Dispatch through the **`libs/subagents` module** — **BOTH** layers, never either/or
(`core/62-using-subagents.md` § Dispatch policy; the mechanics are in § Subagents at the end):

- **Pool breadth** — `fanout("review", units, repo=…, project="mega-review", mode="read_only")` picks
  family-diverse, flywheel-ranked review models (no default price cap) and auto-records each run to the
  flywheel. ⚠️ **Passing `project=` is what makes it record** — omit it and you land zero flywheel rows.
  After you adjudicate, back-fill your 0–5 verdict with
  `set_quality(r.agent_id, score, project="mega-review", task_type="review", model=r.model)` (an unscored
  row teaches the flywheel nothing; ⚠️ never hand-roll run_agents + record_run — it no-ops).
- **≥1 native `fabrik-reviewer` on Opus** — the authoritative pass (the pool never runs `anthropic/*`, so
  pool-only is not valid). It owns the high-risk seams: the parallel-set disjointness, the
  single-migration-owner rule, and `Registrars` ↔ `Shape`.

Each reviewer commits to a lens before seeing the others; **you refute/merge/decide**. The lenses:

**A. Feature coverage** — extract the Vision Summary's `## Full Feature Inventory`; map each feature to
the epic claiming it in `### Scope > In:`.

| Check | PASS | FAIL |
|---|---|---|
| Inventory present | section present AND ≥1 feature | missing/empty → Vision Summary corrupted; route to `/fabrik-vision`, do NOT continue |
| Every feature assigned | all mapped (counts BOTH numbered delta features `1,2,…` AND EXISTING-mode Retrofit features `R1,R2,…`) | feature #X "[name]" in no epic |
| No feature in two epics | each in exactly one (delta + Retrofit alike) | #X claimed by Epic A and Epic B |
| No phantom features | epics contain only inventory features | Epic N claims "[name]" absent from the Vision Summary |

**B. Epic ticket structure** — per ticket:

| Check | PASS | FAIL |
|---|---|---|
| Title format | `Epic N — [Name]` exactly (em-dash, single spaces; optional `Retrofit:` prefix in `[Name]`) | en-dash/hyphen/missing space/wrong number |
| `### Summary` · `### Scope` (In+Out) | present | missing |
| `### Success Criteria` — **by flavour** | delta-feature 5–8; **Retrofit 3–5** (`/fabrik-epics` § Success Criteria) | below the per-flavour minimum |
| deploy/gate-level criterion | delta: "`fabrik apply` succeeds" or "/health 200". Retrofit (no new deploy unit): `scripts/final_gate.py` success + the Compliance-Report gap moving Partial/Violates → Compliant | neither flavour's criterion present |
| resilience criterion | delta: states what happens when a dependency is down. Retrofit: N/A **iff** the area is not resilience/external-call related (Title lacks `Resilience` AND Universal categories lacks #5) | absent AND the epic IS resilience-related |
| `### Out of Scope` | present — other epics, vision-level exclusions, or an explicit `none — …` reason | missing, vague, OR cites a non-existent Epic N |
| `### Dependencies` — **all 5 sub-bullets** | `Consumes from prior epics` · `Produces for later epics` · `Depends on` · `Parallel with` · **`Owned paths`**, each with content or an explicit `none` reason. ⚠️ **`Owned paths` is NOT optional and `none` is NOT valid** — every epic writes something, and lens C's disjointness + migration checks intersect exactly this field | any sub-bullet missing/empty, OR `Owned paths` absent or `none` (it makes lens C unrunnable and any `Parallel with:` claim unverifiable) |
| Typed frontmatter ↔ body | `depends_on` / `parallel_with` / `owned_paths` in the frontmatter equal the `### Dependencies` sub-bullets `Depends on` / `Parallel with` / `Owned paths` (the three list fields — `owner` lives in the frontmatter only and is Phase 2c's code verdict, never re-filed here) | frontmatter and body disagree — `epic_order.py` orders by the FRONTMATTER, so the body is what a reader would wrongly trust |
| `### Metadata` — **structure only** | the `### Metadata` section exists with all 15 rows present. ⚠️ **Field VALUES are lens E's authority, not B's** — do not judge them here, or two nominally-orthogonal lenses file the same finding twice and the merge reads one check as two lenses corroborating | section missing, or fewer than 15 rows |
| Dependencies name artifacts | tables/functions/endpoints/env vars named (or explicit `none` for atomic-root / terminal-output epics) | vague only ("Epic 1's infrastructure") |
| Entry point | `Entry point: /fabrik-spec <this file>` — the window's first command | missing, or names anything else |

**C. Dependency graph** — cross-reference the graph against every `### Dependencies`.

**Graph form:** `/fabrik-epics` emits a **mermaid diagram with `subgraph "Phase N"` blocks**; prose instead
→ the owner cannot see the shape of their own decomposition → route to `/fabrik-epics`. Terminology is
**`Phase`, never `Batch`** (consistent with `epic_order.py --json`). The mermaid is the human-readable twin
of the machine truth — `epic_order.py` derives the authoritative phased order from the typed frontmatter,
and the mermaid must not contradict it. **Epic-count sanity:** state the count + a one-line verdict —
**3–7 typical**; the operator's stated range is **E = 3–20**; **10+** ⇒ recommend re-examining boundaries
for layer-slicing (likely split by layer, not domain) — re-examined, never re-cut by reflex; **2** ⇒ the
vision may not need this workflow. A **surfaced observation, not a hard FAIL** — but never unremarked.

| Check | PASS | FAIL |
|---|---|---|
| No cycles | DAG validated | Epic A → B → A |
| Graph matches tickets | every dependency in the graph appears in a `### Dependencies` | Epic N depends on M but the graph omits it |
| Root epic(s) identified | ≥1 epic with no upstream | none — everything depends on something |
| **Parallel lanes identified** | every set of epics with **no mutual dependency** is marked `Parallel with:` — this row DEFINES the input set the two rows below intersect | a mutually-independent pair left unmarked → the disjointness + migration gates never see it, and the owner loses free parallelism (mega checklist item 79) |
| **Parallel epics have DISJOINT `Owned paths`** | for every `Parallel with:` pair — and every same-phase pair in `epic_order.py --json`, marked or not — intersect their `Owned paths:` as PATHS yourself (two globs that intersect without either containing the other, e.g. `src/*/handlers.py` against `src/api/*`, is the class Phase 2a's check cannot see before the code exists) → empty; and the body agrees with the frontmatter 2a checked | A and B are parallel but both write `[glob]` → two agents writing one file is a merge conflict by construction → re-cut the boundary or make it sequential |
| **At most ONE migration owner per parallel set** | only one epic in a set owns `alembic/versions/**` / `db/schema.sql` | two parallel epics own migrations → concurrent Alembic heads race the version table and wedge the deploy (12-Factor XII) → the non-schema epic must `depends-on` the schema epic |
| Produced artifacts consumed | every `Produces` has a matching `Consumes` — N/A for a single-epic proposal and for terminal-output epics producing end-user output only | A produces X, nobody consumes it, epic count > 1, and X is internal (table/endpoint/env var/queue) |
| **CRITICAL PATH stated + matches** | `/fabrik-epics` emits a `Critical path:` line (e.g. `Critical path: Epic 1 → Epic 3 → Epic 5 (3 deep)`) — the longest chain; confirm present AND consistent with the validated graph | missing or contradicts the graph → route to `/fabrik-epics`. ⚠️ Without it nobody knows what gates delivery |
| **SPLIT-CANDIDATE per critical-path epic** | every critical-path epic carries `SPLIT-CANDIDATE: yes (<how>) / no (<why>)` | missing on any — a critical-path epic splittable into a blocking + non-blocking half **MUST** be split; that is the only way to shorten delivery |
| **Graph is MINIMAL** | every **sequential** pair has a stated artifact reason (`Consumes:` names what B takes from A); if epics CAN be parallel they MUST be | B `depends-on` A but consumes **nothing** → an invented edge lengthening the critical path for free → reclassify to parallel (then it must pass the two gates above) |

**D. Infrastructure Decisions** — read the spec; verify against the tickets.

| Check | PASS | FAIL |
|---|---|---|
| All shared decisions present | per `/fabrik-epics`' Infrastructure Decisions: Database · Auth · Email · Background Processing · Embedding Model (if RAG) · Self-Healing Ladder (if `shape.kind ∈ {service, worker}`) · Watchdog Wiring (**ON by default** — the resolver reads the raw spec dict, `src/fabrik/orchestrator/infrastructure.py`: watchdog applies unless the spec sets watchdog enabled false; ⚠️ the `shape.kind` matrix in `core/60-watchdog.md` is **operator discipline, NOT code-enforced** — a `static-site` gets a watchdog despite the matrix saying `off`) · Observability Defaults · Cost Guardrails (any paid-API use) · Backing Services · External Services · Domain Structure · Shared Env Vars · Shared Shape Decisions | missing section: [name] |
| Tickets reference, not duplicate | epics say "Inherited from Infrastructure Decisions" | Epic N re-defines [decision] differently |
| No contradictions | consistent across all tickets | Epic N says X, the spec says Y |
| **Deferred Compliance appendix** (EXISTING mode only) | if the Compliance Report has any `fix-later` / `accept-as-legacy` row, an appendix lists every one — those rows emit **no epic**, so the appendix is their only carrier, and `/fabrik-epics` persists it into the Infrastructure Decisions spec's `## Deferred Compliance (not actioned this run)` section — **read it there**, not from conversation. N/A in NEW mode or when all rows are `fix-now` | such a row appears in no epic and no appendix → the owner's deliberate deferral was silently dropped. Route to `/fabrik-epics` naming the cause: present in the Compliance Report but missing from the spec's section (it didn't carry them), or deferred by the owner but never surfaced (its compliance-rows step) |

**E. Handoff readiness** — each ticket must feed **`/fabrik-spec docs/development/epics/<this file>`**,
the epic-file intake, which reads the ticket's 15-field Metadata as intake rows (every field, plus the
derived Watchdog and LLM-gateway rows) and inherits the Vision's fabrik-lib Verdict + Rejected Alternatives
without re-running the ladder. ⚠️ **The entry point is `/fabrik-spec <epic file>`, not a chat brief** —
a window that specs its epic from conversation loses every Metadata field the intake would have pinned.

| Check | PASS | FAIL |
|---|---|---|
| `Port` | present **and not already allocated** — verify against `PORTS.md`, don't eyeball | missing, OR taken in `PORTS.md`, OR two epics claim the same port → route to `/fabrik-epics` (it allocates from `PORTS.md`) |
| `target_vps` | `vps1`/`vps2`/`vps3` | missing — the plan cannot pick the DB host |
| `Responsive` / `Dark+Light` | present AND the value **matches the feature trigger** — mandatory iff a GUI surface exists (saas-skeleton / docusaurus front / chrome-extension popup / mobile-app / desktop-app, OR python-api/node-api/file-api with `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML) — the trigger is the GUI SURFACE, not the scaffold type (`/fabrik-vision` § Rule-area applicability matrix); `N/A` only when no HTML/native UI exists | missing, OR `N/A — non-GUI scaffold` on an epic whose Shape has `is_admin_dashboard`/`is_public`+HTML — a rule-pack violation, not a metadata gap |
| **`Registrars` ↔ `Shape`** — a SEMANTIC cross-check, not presence | every firing flag has its registrar listed: `needs_database`⇒postgres · `needs_cache`⇒redis · `has_persistent_data`⇒backrest · `has_search_feature`⇒meilisearch · **`is_public` AND `spec.domain`**⇒gatus · **`is_admin_dashboard` AND `spec.domain`**⇒authelia · **`exposes_metrics` AND `spec.domain`**⇒prometheus; plus **glitchtip** (`shape.kind ∈ {service, worker, wordpress}`), **grafana** (always) and **watchdog** (opt-OUT). ⚠️ `has_bearer_api` fires **no** registrar — only the Authelia `^/api/` bypass (`src/fabrik/orchestrator/infrastructure.py` — the applicability matrix) | the list contradicts `Shape` — e.g. `needs_database: true` but postgres absent. **Not a metadata gap — a silently-broken deploy**: `fabrik apply` skips the registrar and the service comes up without its database (CLAUDE.md § Spec contract awareness) → route to `/fabrik-epics` |
| the other **10** fields — present **and value-shaped** (not presence-only) | `Scaffold` · `Shape` · `Concurrency` · `i18n` · `Rule Packs` · `HAS_USER_GUIDE` ∈ {true,false} · **`Universal categories` = comma-separated 1–14, verbatim from `/fabrik-epics`' universal-categories step** (a hand-invented list is a FAIL) · `Email` ∈ {transactional, marketing, two-stream, none, N/A} · `Abuse Detection` = `required` (SaaS w/ free tier) or `N/A — <reason>` · `FINANCIALS` = `required` (SaaS launch gate) or `N/A — <reason>` | missing: [name], **or present with an off-contract value** — a presence-only pass is the same regression this table flags for `Registrars` |
| Ticket is self-sufficient | the whole corpus chain for one window (`/fabrik-spec <epic file>` → `/fabrik-spec-review` → `/fabrik-features` → `/fabrik-flows` → `/fabrik-data-contract` → *(GUI)* `/fabrik-ui-design` → `/fabrik-plan-after-chat` → `/fabrik-plan-review` → `/fabrik-execute-plan`) runs from ONLY this ticket + the Infrastructure Decisions spec | needs context only the Vision Summary carries |

## Phase 4 — Converge to a no-op — fixup, don't stop

Classify every surviving finding, then handle it autonomously — everything short of a BLOCKED case:

- **Surgical ticket fix** (a missing Metadata field, a wrong title format, an absent `Owned paths`, an
  off-contract field value, a body that disagrees with its frontmatter) → a **scoped fixup ticket** naming
  the finding's `path:line` + the required value, **dispatched** through `libs/subagents`: the pool via
  `fanout("docs", units, repo=…, project="mega-review", mode="write")` for an epic-file edit — `mode="write"`
  is load-bearing (the default `read_only` unit has no file tools and cannot edit anything), **one unit
  per epic file** as its `owned_paths` — `fanout` REFUSES with a `ValueError` if two units name the same
  path, so merge all of one file's findings into ONE unit (two findings on the same epic is the common
  case) — or a native Opus subagent for a high-risk one (e.g. a migration-owner correction). Re-read +
  re-review to confirm.
  ⚠️ **NOT** a `Registrars`↔`Shape` mismatch — lens E routes that to `/fabrik-epics` (a silently-broken
  deploy, not a metadata gap) and lens E is the authority on it. ⚠️ A fixup **never touches `owner:`** —
  the field is `epic_order.py --assign`'s; a fixup that needs a different owner is a boundary question.
- **Boundary / scope change** (orphans, duplicates, phantoms, a wrong split, shared `owned_paths` between
  parallel epics, a port re-allocation, a missing Infrastructure-Decisions **section** or **FILE**, a
  missing or incomplete `## Deferred Compliance (not actioned this run)` section — routed by cause, per
  lens D) → **route back** to `/fabrik-epics`, which re-cuts and recreates the affected tickets; re-enter
  at Phase 2 (a recreated ticket has never passed integrity and carries `owner: ""`). Never re-cut epics
  here.
- **Vision Summary corrupted** (lens A's inventory missing/empty) → route to `/fabrik-vision`; do NOT
  continue.
- **BLOCKED cases** — 3 consecutive same-test failures on one fixup → case 1; missing infra → case 2;
  unresolvable spec contradiction → case 3 — each handled as § Core philosophy states (persist
  `Status: IN-PROGRESS` + `## BLOCKED`, pause that finding, continue the rest).

**LOOP:** every fixup dispatched → re-reviewed (Phase 3) → re-classified — **until every verdict lens of
the Phase-5 report template carries an adjudicated PASS-with-evidence, with zero unresolved findings** (the
template is the single source of the lens set). **The final round must itself be QUIET — `found: 0,
fixed: 0`, counting every raised candidate including later-refuted ones** (a round that raised 3 and
refuted all 3 owes the next round; the loop, not the checklist, decides when hunting stops). A quiet round
alone is still not sufficient — every lens must ALSO be adjudicated (a quiet sample from finders that
looked at too little proves nothing). **Minimum two full rounds, ALWAYS** (the round that first completes
the lenses is never the exit round — a fresh round must re-adjudicate them); the pass that produced a
fixup is never the last look at the lenses it touched. **There is NO round ceiling** — while anything is
still being raised, the next round is owed; the run loops until the exit holds. The ONLY non-quiet stop
is the command's own **BLOCKED escalation** (a finding surviving 3 consecutive fix attempts → pause that
finding, keep looping the rest) — never a self-declared residual. Keep the `found:`/`fixed:` ledger per
round (`found` counts refuted candidates too).

**Anti-cheat (mechanical, not vibes) — the SET hash** (the same machinery as `/fabrik-plan-review`'s
combined-hash rule, for the same reason): record the epic set's combined hash at the **start and end of
every round** — round 1's start is taken AFTER Phase 2c:

```bash
find docs/development/epics -name '*.md' -print0 | LC_ALL=C sort -z | xargs -0 md5sum | md5sum
```

(`LC_ALL=C` is load-bearing: locale collation orders `Alpha.md`/`alpha.md` and nested paths differently
from byte order, and the gate recomputes this hash in byte order — a locale-sorted hash reads as "never
computed".)

Fixups edit epic files, so a round that changed anything shows a different hash — which is exactly why
**the exit round must show `md5(start) == md5(end)`** on top of its quiet ledger: identical hashes prove
the final round was genuinely edit-free rather than asserted so. A quiet ledger with a moved hash is a
round that fixed something and called itself quiet — run the next round.

**Record hashes IN FULL (all 32 hex chars), per round, and let them CHAIN**: round N's `md5(end)` must
equal round N+1's `md5(start)` (a gap means the set changed between reviewed rounds, off the books), and
the Phase-5 report's `Surface:` line carries the final `md5(end)` verbatim. `check_review_coverage.py`
machine-verifies all of it — full-length hashes, the chain, Surface == final end, a both-counters-quiet
final row — **and recomputes the live epic-set hash against `Surface:` when the report is gated**, so a
hash that was typed rather than computed cannot pass. Truncated hashes fail; that is deliberate (a bare
year once passed as an "unmoved hash").

## Phase 5 — Report + hand off

**PERSIST the report FIRST.** The report is written to
`docs/development/reviews/YYYY-MM-DD-mega-<vision-slug>-validation-review.md` — the file is the record.
⚠️ **The filename and the H1 are a CONTRACT, not a style choice.** `check_review_coverage.py` (run by
`final_gate` and the Stop hook) routes a report through the cross-epic grammar by exactly two keys — the
H1 `# Cross-Epic Validation Report` as the file's first line (a vision suffix after it is allowed) OR the
reserved filename suffix `mega-<slug>-validation-review.md`. Either key alone still routes it (the
filename key exists precisely so a mega-shaped name can never route weaker, whatever its title says);
lose BOTH and the report silently falls through to the ordinary review grammar, and nothing below is
enforced. Carry both, always. A report that lives only in chat is invisible to every gate. The grammar it
enforces on the persisted file:

- a `Surface:` line at column 0 carrying the **final SET hash** from Phase 4's anti-cheat;
- the **per-round `found:`/`fixed:` ledger with each round's start/end hash** — minimum two rounds,
  final round `found: 0, fixed: 0` with `md5(start) == md5(end)`; the ledger TABLE is the report's ONLY
  `found:`/`fixed:` table, and no Pass-style prose counter lives outside it;
- **every lens line adjudicated** — no `[PASS]`/`[N]`/`[list]` template placeholders may survive into
  the persisted report (a placeholder is a lens nobody adjudicated wearing a verdict's clothes);
- `Status: IN-PROGRESS` at column 0 **within the report's first 10 lines** (the template slots it at
  line 3) is the sanctioned escape for a run interrupted mid-loop or paused on a BLOCKED finding — never a
  way to ship an unconverged set. Below line 10 it is ignored, deliberately: an escape hatch that works
  from anywhere in the body is quotable from anywhere in the body.

The template:

```markdown
# Cross-Epic Validation Report
Surface: <final md5(end), FULL 32 hex — from Phase 4's anti-cheat, never truncated>
Status: <omit when converged; `Status: IN-PROGRESS` for an interrupted or BLOCKED run — the gate reads this ONLY from the report's first 10 lines, which is why its slot is here>
## BLOCKED: <finding> — attempts: 3 · <what · searched · missing>   (only on a Status: IN-PROGRESS report; omit when converged)

Rounds (found counts refuted candidates too; FULL hashes, chained — round N's end = round N+1's start):
| round | found: | fixed: | md5(start) → md5(end) |
|------:|-------:|-------:|---|
| 1 | found: 7 | fixed: 6 | <32-hex-A> → <32-hex-B> |
| 2 | found: 0 | fixed: 0 | <32-hex-B> → <32-hex-B> |

## Feature Coverage: [PASS] — [N] features across [M] epics · orphans: none · duplicates: none
## Epic Tickets: [PASS] — per-epic verdict with evidence
## Dependency Graph: [PASS] — no cycles · roots: [list] · parallel lanes: [list] (disjoint paths verified)
   Critical path: Epic 1 → Epic 3 → Epic 5 (3 deep) · SPLIT-CANDIDATE stated on each
## Infrastructure Decisions: [PASS] — no contradictions, no missing sections
## Handoff Readiness: [PASS] — 15-field Metadata complete; Registrars match Shape; ports free in PORTS.md
## Overall: PASS  ·  Fixups this run: [N]  ·  Routed back: [none / list]
## Recommended Execution Order  (topological phases; `⚡` = parallel within a phase)
Phase 1 (root): Epic 1 ⚡ Epic 2   Phase 2: Epic 3   …
(single-epic: `Phase 1: Epic 1 — [name] (atomic — no phasing required).`)
## Owner set (agent-1 first): alpha, beta, gamma — `epic_order.py --check --owners` PASS over [M] epics
## Next per window
alpha (agent-1, main checkout — this window):            /fabrik-spec docs/development/epics/<epic-1 file>
beta  — `CLAUDE_AGENT=beta claude --worktree beta -n beta-<repo>`   → /fabrik-spec docs/development/epics/<epic-2 file>
gamma — `CLAUDE_AGENT=gamma claude --worktree gamma -n gamma-<repo>` → /fabrik-spec docs/development/epics/<epic-3 file>
Phase 2 (after Phase 1 merges): beta → /fabrik-spec docs/development/epics/<epic-4 file> · …
```

⚠️ **Generate the `## Recommended Execution Order` in CODE, do not hand-derive it** — the topological
phases come from the same script that gated integrity:

```bash
python3 /opt/fabrik/scripts/epic_order.py --json --epics-dir docs/development/epics
```

Paste its `phases` into the report verbatim. It is deterministic over `depends_on`/`parallel_with`, so the
order is reproducible — not a per-run judgement. `## Owner set` and `## Next per window` are derived the
same way: each epic's `owner:` (read from its frontmatter, never from memory of 2b) joined onto those
phases; the owner set is printed **in the operator's order — agent-1 = the first name**.

**Hand off — EVERY window gets its line, none is left to derive its own.** At the adjudicated exit,
dispatch is not a command that renders instructions; it is the operator opening windows:

- **agent-1 (the first name)** stays in the **main checkout** — the window running this command, already
  launched as `CLAUDE_AGENT=<name> claude -n <name>-<repo>` — and runs
  `/fabrik-spec docs/development/epics/<its epic>.md` on its Phase-1 epic. It is also the merge owner:
  finished branches merge into master in `epic_order` phase order, one at a time, rebased first, and it
  runs the tail after the last merge (`/fabrik-features` REFRESH → `/fabrik-conformance-review` when
  E ≥ 2 → certification → `/fabrik-deploy-checklist` → `/fabrik-release`).
- **agents 2..N** each launch `CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>` (the
  session name is `<name>-<repo>` because session names are box-wide — a bare `-n <name>` collides across
  repos) and run `/fabrik-spec docs/development/epics/<its epic>.md` on their Phase-1 epic; later-phase
  epics wait for the phase before them to merge, and are named on the same line so nobody re-derives them.
- Epics in the same phase run **concurrently, one per named agent**; an agent with no Phase-1 epic starts
  on its first later-phase epic only when that phase opens.

A route-back instead hands to `/fabrik-epics` or `/fabrik-vision` and re-enters here after they re-emit.

## Does NOT

- **Re-cut epic boundaries or re-derive the vision** — it validates what exists; boundary changes route to
  `/fabrik-epics`.
- **Expect a paired review of its own** — this command IS the review twin of `/fabrik-epics`: it has no
  downstream paired review and self-converges via its own finder loop, which is also why it is not a
  `type` in `/fabrik-workflow-review`, whose types are the producer doers.
- **Write epic content itself** — **the orchestrator never writes `docs/development/epics/`**. A
  *surgical* edit is the dispatched fixup agent's job (Phase 4); an `owner:` value is
  `epic_order.py --assign`'s; a *re-creation* after a boundary route-back is `/fabrik-epics`'.
- **Stop and wait for the owner on a finding** — the operator agreed to the decomposition at
  `/fabrik-epics`' checkpoint; drift is handled by fixup + re-dispatch + re-review. Only the 3 BLOCKED cases
  pause a finding.
- **Take a ticket's word** — every PASS is grounded in the real repo (`PORTS.md`, `infrastructure.py`, the
  rule packs), never the ticket's own claim.
- **Rely on conversation memory** — tickets are FILES; read them fresh with Glob/Read, every round.
- **Start any epic's own chain** — each window runs `/fabrik-spec` on its owned epic; this command names
  the dispatch per window and emits the code-generated order, it never runs a window's work.
- **Validate rule-pack CONTENT** — it verifies the `Rule Packs` field propagates and that a cited pack
  exists; the pack semantics are the producer commands' job.
- **Apply a blanket 4-stage expectation to a Retrofit epic** — a Retrofit on a deployed service owns no
  Stage-1/Stage-3 (§ Core philosophy).
- **Hand-edit `owner:`, or run `--assign` over a set that failed `--check`** — the assignment is code, its
  proof is `--check --owners`, and a refusal is a finding to file, not a field to type.
- **Push the DEFAULT branch from a worktree, or commit files you did not author** — the gate auto-STAGES;
  staging is not committing, and CLAUDE.md § EXIT + § HARD STOPS make committing AND pushing your own work
  at task end REQUIRED (the Stop hook enforces it). Commit with explicit pathspecs + Agent Provenance
  Trailers and push the CURRENT branch.

## Acceptance criteria

- Every epic ticket read as a FILE from `docs/development/epics/` (Glob/Read); the specs read fresh —
  never from memory.
- Ticket-set integrity gated in code (`epic_order.py --check --expected-count`) BEFORE any assignment, and
  `--assign <names>` never invoked over a failing set.
- Every epic carries exactly one `owner` ∈ the operator's set, proven by `--check --owners <names>`
  BEFORE any lens ran; the set's order (agent-1 first) recorded in the report.
- Review dispatched through `libs/subagents` — **pool `fanout("review")` recording the flywheel AND ≥1
  native `fabrik-reviewer` on Opus** — across every report lens, with the orchestrator refuting / merging
  / deciding.
- Feature coverage (delta + `R`-prefixed alike), ticket structure (incl. all 5 `Dependencies` sub-bullets
  with a real `Owned paths`, frontmatter ↔ body agreement, the `/fabrik-spec` entry point), graph (cycles,
  roots, **disjoint parallel paths**, **single migration owner**, consumed artifacts, critical path +
  SPLIT-CANDIDATE, minimality), Infrastructure Decisions (+ the Deferred Compliance appendix in EXISTING
  mode), and handoff readiness (15 fields; **`Registrars` ↔ `Shape`**; `Port` free in `PORTS.md`) all
  verified — each binary with `path:line` evidence.
- Findings handled **autonomously**: surgical fixups dispatched (pool `fanout("docs", …, mode="write")`,
  one unit per epic file, or a native Opus subagent), re-reviewed, **looping to the lens-adjudicated exit (min-2 rounds, no ceiling,
  chained full hashes)**; boundary/scope changes routed to `/fabrik-epics`; a corrupted Vision Summary to
  `/fabrik-vision`; only the 3 BLOCKED cases pause a finding.
- Epic-count sanity surfaced (3–7 typical; E = 3–20 accepted; 10+ or 2 remarked, never a silent pass).
- The report persisted at `docs/development/reviews/YYYY-MM-DD-mega-<vision-slug>-validation-review.md`
  with the H1 `# Cross-Epic Validation Report` — the two keys `check_review_coverage.py` routes on — and
  gated green by it.
- The exit report emits the code-generated topological execution order (`epic_order.py --json`), the owner
  set in order, and **one `/fabrik-spec docs/development/epics/<its epic>.md` line per window** with the
  exact launch form — agent-1 in the main checkout, agents 2..N via
  `CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>`.

{{include:questionbar}}

{{include:subagents-core}}
