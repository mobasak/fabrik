# The Decision Ledger — every agent records decisions, every agent queries them first

Status: CONVERGED (2026-08-30 — /fabrik-spec-review converged, then re-converged folding each approval-dialogue round's intake: JSONL rejection + I8/I9, subagent/pipeline pen rule + I10; every round closed on a raised-0/edits-0 md5-stable pass)
Date: 2026-08-30
Scale verdict: **feature-scale** — one plan (governance text + template + seed + search helper + corpus wiring).
Surface: `templates/governance/CLAUDE.md` + `CLAUDE.md` + `templates/scaffold/` + `commands/_fragments/` + one hub helper script + per-repo `docs/DECISIONS.md`.
Predecessor: `docs/archive/specs/2026-08-30-decision-ledger-design.md` — REJECTED for violating the 1c
research floor (one summariser fetch). This spec re-derives every choice under real research; where the
outcome matches the predecessor, that is convergence under evidence, not reuse.

## Personas

**PRIMARY — the operator, in their own words (2026-08-30, both statements):** *"all ai agents must keep
a decision ledger/diary postgres db or file. and always query it. i dont want to struggle like this
again. all decisions will be recorded in all repos from now on with why, what, where, who, when."* and,
re-initiating: *"when i ask something, about a build, feature, decision i want a full answer not
struggling ais around to find it."*
Their minimal loop, step-counted (BUDGET = 2): (1) ask any window "where is X / did we decide Y /
why is Z like this" → (2) get the FULL answer — what, why, where — from a ledger row. Two steps;
anything longer regresses the persona this exists for. "Full answer" is the bar: a row that answers
*what* but not *where it lives* fails the persona.

**The writer** — every AI agent in every repo (3 hub roles + ~46 project agents + wef-class
multi-window repos): must be able to append a row in one edit, mid-run, with zero infrastructure
(no DB connection, no service up, no network).

**The reader-under-amnesia** — a future session, post-compaction or weeks later, that must answer
from the record rather than reconstruct. This persona is why entries carry WHERE (paths/shas/ids),
not prose alone.

**The cross-repo querier** — a hub agent answering a fleet-wide question ("which repos decided to
retire Supabase?"): needs one command over all ledgers, not 46 file opens.

**The receiver who never consented** — nobody; the ledger is internal. (Enumerated to satisfy the
personas contract's receiver check: no external party is touched.)

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "all ai agents must keep a decision ledger/diary" | IN | § The ledger file · § Write duty |
| I2 | "postgres db or file" | IN — decided FILE, postgres rejected with grounded reasons | § Storage decision |
| I3 | "and always query it" | IN | § Query duty |
| I4 | "i dont want to struggle like this again" | IN — the success criterion | § Success criteria |
| I5 | "all decisions will be recorded in all repos from now on" | IN | § Distribution · § Write duty |
| I6 | "with why, what, where, who, when" | IN — the frozen row shape | § Entry format |
| I7 | "when i ask something, about a build, feature, decision i want a full answer not struggling ais around to find it" | IN — the full-answer bar (what+why+where in one lookup; builds and features are queryable, not only rulings) | § Query duty · § Success criteria |
| I8 | "why did you decide to create decisions.md? but not db, or jsonl file?" (approval dialogue, 2026-08-30) | IN — JSONL adjudicated as a named rejected alternative | § Approaches 5 · § Storage decision |
| I9 | "what will happen to the file if it grows too much?" (approval dialogue, 2026-08-30) | IN — measured escalation triggers + v2 options | § Storage decision (hybrid para) |
| I10 | "does it take into account roles? consumers of the built?" (approval dialogue, 2026-08-30) | IN — consumer roles enumerated; who-cell is role attribution; subagent/pipeline pen rule added | § Personas · § Entry format 2 · § Write duty 5 |

Intake: 10 items — 10 IN, 0 OUT-OF-SCOPE, 0 ASK.

## The motivating failure (why this exists)

2026-08-30: "where is our own crawling MCP?" cost three sessions a combined multi-hour hunt (roster,
/opt sweep, fabrik-lib, 4 lexical session-recall queries, specs, backlogs) and produced one WRONG
answer that propagated between sessions — because the underlying decisions were never recorded
anywhere queryable. Same class, same week: the wef approval-gate re-ask, the quota-governance window
misroute. session-recall is lexical over transcripts: a decision phrased differently is invisible.
Lessons record failures; CHANGELOG records changes; **nothing records decisions.** The field names
this exact failure: *"A decision that's made but never recorded will likely be forgotten, leading to
repeated debates or later changes that unknowingly contradict the original intent"* (Microsoft Azure
Well-Architected, ADR guidance — fetched raw 2026-08-30, quote verified verbatim).

## Research grounding (1c — the approach floor, satisfied for real this time)

Method: two independent SEARCH legs + raw-fetch verification of every quoted string (curl, HTTP 200,
`grep` on the raw HTML). Tools: `mcp__exa__web_search_exa`, `WebSearch`, raw `curl` fetch.

**Leg 1 — decision-record field practice (exa search, 2026-08-30):**
- **Single-file decision log vs per-file ADRs is a NAMED distinction with a scale rule.**
  *"A decision log — a chronological flat list of decisions without lifecycle fields — is appropriate
  for small teams (three to eight people)… The log is written as a single shared file, appended as
  decisions are made, never updated in place."* — https://whychose.com/seo/adr-decision-register
  (published 2026-06-01, fetched raw 2026-08-30, quotes verified verbatim). The outgrow signal it
  gives: needing per-entry status lifecycle or a non-engineer audit UI → split into ADR directory +
  register. Neither applies per-repo here (1–3 agent "team", operator reads via chat).
- **Immutability + supersession is the universal invariant, log or ADR.** *"Once an ADR is accepted,
  it should never be reopened or changed - instead it should be superseded"* —
  https://martinfowler.com/bliki/ArchitectureDecisionRecord.html (updated 2026-03-24, fetched raw
  2026-08-30, verified). *"The ADR serves as an append-only log. Don't go back and edit accepted
  records. If a decision changes, write a new record that supersedes the original and link the two
  together."* — https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record
  (fetched raw 2026-08-30, verified). This OVERTURNS the predecessor spec's silent gap: rows must be
  append-only with an explicit supersede pointer, never edited in place.
- **Storage in source control beats every alternative for this shape.** *"source control gives you
  immutability through Git history, free authentication… discoverability through grep and code
  search, and review through the same pull request flow"* —
  https://hidekazu-konishi.com/entry/architecture_decision_records_templates_and_operations.html
  (2026-05-08). Same source: the index/first-entry convention (the first record documents adopting
  the practice) and the failure telemetry (*"If `grep -r 'docs/adr/' src/` returns zero results, the
  practice is failing silently"*).
- **Hand-rolled numbering has a known failure mode**: id collisions on concurrent merge + stale index
  + dangling supersede pointers — https://whychose.com/seo/adr-tooling-comparison (2026-05-31). With
  up-to-3 concurrent agents per repo this WILL happen here; the design treats an id collision as an
  ordinary git merge conflict (visible, trivially fixed) and adds no lock machinery — but the
  advisory check (§ Enforcement) inherits "supersede pointer must resolve" as its one mechanical row.
- **Don't backfill** — *"Write ADRs for decisions going forward. Don't backfill historical decisions
  unless someone is actively confused by one"* — https://docsio.co/blog/architecture-decision-record
  (2026-04-30). Matches § Out of scope.

**Leg 2 — AI-agent memory practice (WebSearch, 2026-08-30):**
- The field's default persistent memory for coding agents is a **flat markdown file in the repo**
  (CLAUDE.md/AGENTS.md/MEMORY.md class), with append-after-run journaling as the simplest working
  implementation — https://alexop.dev/posts/four-types-memory-coding-agents-claude-code/ (2026).
- Semantic/vector memory systems (agentmemory, mem0, Letta) exist and benchmark well on retrieval —
  https://github.com/rohitg00/agentmemory — but are retrieval MACHINERY: a service, an index, a
  dependency. Our declined-semantic-search precedent (session-recall, operator-decided) applies;
  ledger rows are structured precisely so grep suffices. Recorded as the v2 trigger, not built.

**What the research changed vs the rejected predecessor:** (a) row supersession is now explicit
(supersede-by-new-row, never edit — § Entry format rule 3); (b) the single-file-log choice is now
grounded in a named field practice with a scale rule and an outgrow signal, not asserted; (c) the
seed row D-000 records the adoption decision itself (field convention); (d) the enforcement check
gains its one mechanical row (supersede pointers resolve); (e) agent-memory field practice
independently corroborates flat-file-in-repo for exactly our writer/reader personas.

## Storage decision (I2): FILE, per repo — postgres REJECTED (this is itself ledger row D-001)

**`docs/DECISIONS.md`, one per repo, append-at-top, project-OWNED (never sync-overwritten).**

Why file beats postgres here, each reason load-bearing:
- **WHO + WHEN come free and tamper-evident** from git (`git log -- docs/DECISIONS.md` + the
  Agent-Name trailer discipline); a DB row's who/when is self-asserted.
- **Zero coupling:** works in every repo including sync-excluded ones (fabrik-lib), offline, in
  worktrees, on the VPS — a postgres ledger couples 46 repos to `postgres-main` liveness and
  credentials for the most basic act of remembering.
- **Grep-first agents:** every query duty below is a `Grep`/`Read` — the tools agents already hold;
  a DB needs a client, a DSN, and a rotation-safe secret in 46 places.
- **It is the field's named practice for this scale** (§ Research grounding: the decision-log shape,
  source-control storage, flat-file agent memory — three independent bodies of practice converge).
- **Cross-repo query stays one command** (§ Query duty) because /opt is one filesystem.

**Hybrid (per-repo file + hub indexer) is deliberately v2, not now:** the grep-over-/opt query below
is O(46 files) and instant; an indexer is machinery with no measured need yet. Revisit only if
ledgers grow past grep usefulness (backlog row, measured triggers: >2s fleet query, >500 rows in any
repo, or the whychose outgrow signal — a genuine need for per-entry status lifecycle).

## Entry format (I6 — the frozen row)

`docs/DECISIONS.md` is a table, newest row FIRST, one row per decision:

```markdown
# Decisions

Append-at-top. One row per decision; rows are IMMUTABLE — a changed decision gets a NEW row whose
what-cell opens "supersedes D-NNN:". WHY ≤ 2 lines; the full rationale lives at the WHERE links.
Query: grep this file first; fleet-wide: `python3 /opt/fabrik/scripts/decisions.py <term>`.

| id | when | who | what (the decision) | why | where |
|---|---|---|---|---|---|
| D-003 | 2026-08-30 | operator+infra | context7 MCP retired from window roster | 45 lifetime calls vs 364MB/window; WebFetch covers it | 74ad8a06 · docs/workstation/mcp-roster.md |
```

1. **id**: `D-NNN`, monotonic per repo (collision on concurrent append = ordinary merge conflict,
   visible and trivially fixed — no lock machinery; the field's known hand-rolled failure mode,
   accepted deliberately at our scale).
2. **who**: `operator` · `infra|fleet|intel` · the repo's agent · `operator+<agent>` when the
   operator ruled and the agent executed. The commit's trailers corroborate.
3. **Rows are immutable — supersede, never edit** (the universal invariant, § Research grounding):
   a reversed or changed decision mints a NEW row, `what` opening with `supersedes D-NNN:`; the old
   row is never touched. History stays honest; `git log` corroborates.
4. **what/why**: one line each — a ledger scans; it does not essay.
5. **where**: commit sha(s) · paths · spec/plan/mail ids — the pointers that turn a row into the
   full story. THIS is what kills the crawling-MCP hunt and meets I7's full-answer bar: the row
   says where the thing lives.
6. **when**: date. Finer grain comes from git.

**What is a "decision" (the write trigger, kept sharp so this is a ledger, not a diary):** an
operator ruling in chat · a spec/plan approval or Status flip · a retirement/adoption (tool, vendor,
pattern, MCP, module) · an architecture/storage/scope choice · "we built X, it lives at Y" · a
rejected option worth not re-proposing (the memory system's "don't re-propose" class, now
fleet-visible). NOT a decision: routine fixes, refactors, doc edits — those are CHANGELOG's beat.

## Ownership vs the 8 adjacent surfaces (extend, don't duplicate)

| Surface | Keeps owning | The ledger newly owns |
|---|---|---|
| LESSONS_LEARNT | how something went wrong + the class | nothing moves |
| CHANGELOG | what changed in the code, per change | nothing moves — a ledger row LINKS its changelog entry via sha |
| STRATEGIC_BACKLOG | deferred work with reasons | a backlog item's RESOLUTION becomes a ledger row |
| agent memory | per-agent working knowledge, hub-local | fleet-visible decisions graduate INTO the ledger; memory keeps pointers |
| session-recall | verbatim history, lexical | the ledger is the STRUCTURED index session-recall isn't |
| spec/plan Status flips | the artifact's own lifecycle | the flip mints a one-row summary pointing at the artifact |
| kaizen | metrics | nothing |
| PROJECT_CATALOG / BUSINESS_MODEL | what exists/ships | "where is X" rows point INTO them |

## Write duty (I1, I5)

1. **Governance (both CLAUDE.md files, § Behavior + Doc Sync Matrix row):** *"Decision made or
   received this run → its row in `docs/DECISIONS.md`, same change"* — the Doc Sync Matrix already
   binds same-change doc updates; this is one more keyed row.
2. **Command close-outs:** the close-feedback fragment gains one line — before `done`, answer
   *"did this run make or receive a DECISION? → row appended, or `none`"* (the feedback-duty model:
   the close is the moment the context still exists).
3. **Chat rulings:** an operator ruling mid-conversation is a decision the moment it lands — the
   receiving agent appends the row in its next commit.
4. **Cross-repo decisions** (hub rules affecting all repos): recorded ONCE in the hub ledger;
   project ledgers record only project-local decisions — no fan-out duplication.
5. **Subagents and the daily pipeline never hold the pen.** A subagent (pool or native) that
   surfaces a decision-shaped finding hands it to its DISPATCHING session, which appends the row —
   the same law that governs subagent findings and mail (subagents are ephemeral and cannot own a
   duty). The daily pipeline's automated runs mint rows only through the duties above (its
   close-outs included); the `who` cell then names the responsible agent, never "a subagent".

## Query duty (I3, I7)

1. **Before answering "where is X / did we decide Y / why is Z like this / what did we build for W":
   Grep `docs/DECISIONS.md` (repo) then `python3 /opt/fabrik/scripts/decisions.py <term>` (fleet)
   BEFORE any wider hunt** — added to the governance read-it-don't-recall-it clause and the
   session-recall mandate (ledger first: structured beats lexical). The answer owed is the ROW's
   full triple — what, why, where — not a bare location (I7).
2. **/fabrik-spec Phase 0 episodic-memory step + /fabrik-plan-after-chat grounding + the ASK-bar
   derivation sources**: `docs/DECISIONS.md` joins the list of frozen artifacts consulted before
   any question reaches the operator.
3. **The fleet helper:** `scripts/decisions.py` (hub) — `grep -i` over `/opt/*/docs/DECISIONS.md`
   + the hub's own, printing `repo · id · when · who · what · where`. ~30 lines, stdlib, read-only.

## Distribution (I5)

- **New repos:** the scaffolder seeds the header + D-000 row — per field convention, D-000 records
  the ADOPTION decision itself ("this repo keeps a decision ledger; scaffolded as type X from spec
  Y") — fleet's beat (`templates/scaffold/`).
- **Existing ~46:** seed-if-missing via the sanctioned sync machinery
  (`sync_enforcement_to_projects.py` gains a seed-not-overwrite entry, exactly PORTS.md's
  SEEDED_NOT_ENFORCED class) — the file is project-owned from birth; the sync NEVER touches an
  existing ledger.
- **Hub:** `docs/DECISIONS.md` created in this plan, seeded with this week's real decisions
  (context7 retirement · volume-prune withdrawal + never-offer rule · cache-prune _npx gate ·
  persona law · design-system ladder · governance-sync post-commit move · ASK-bar · the 1c
  APPROACH-FLOOR · this very storage decision) — the format proven on real rows on day 1.
- **Naming:** `DECISIONS.md` joins CLAUDE.md's naming-exceptions list (sibling of FEATURES.md).

## Enforcement (measured-first, per the fix directive)

Day 1: **advisory only** — the close-out line + the Doc Sync Matrix row (judgment-enforced like the
rest of the matrix's floor). NO mechanical "was a decision recorded" gate: that predicate is not
mechanically decidable, and a check that nags every commit is wallpaper. ONE narrow mechanical row
ships with the helper (cheap, precise, zero false positives): **every `supersedes D-NNN` pointer must
resolve to an existing row id** — the dangling-pointer failure the tooling research names. Measure
adoption after 2 weeks (kaizen can count ledger appends/repo); if ~zero, the escalation candidate is
a check that a `Status:`-flip commit touches DECISIONS.md in the same change — THAT subset is
mechanical. Backlog row carries the trigger.

## Success criteria (I4, I7)

- The crawling-MCP question class ("where is X / did we decide Y / what did we build for W") answers
  from a ledger row in ≤ 2 steps, and the answer carries the full what+why+where — no exhaustive
  hunts, no partial answers.
- A rejected option (Factory, Supabase, per-project binding…) is never re-proposed by an agent that
  queried the ledger — the memory system's protection, now fleet-wide.
- Zero new infrastructure: no DB, no service, no daemon; works in every repo today.

## External dependencies

None at runtime — the design is files + git + one stdlib script. The research sources above are
design-time citations, not dependencies.

## fabrik-lib verdict table

| Capability | Verdict | Why |
|---|---|---|
| ledger storage | BUILD (a doc template, not code) | no module covers governance doc shapes; not module-shaped |
| fleet query | BUILD (`scripts/decisions.py`, ~30 lines stdlib) | grep wrapper; below the new-module bar (process tooling, not reusable product code); no existing module greps /opt-wide |
| distribution | VENDOR existing machinery | scaffolder templates + `sync_enforcement_to_projects.py` seed-if-missing — both exist |

No fabrik-lib candidates — nothing here clears the ≥2-project-types code-reuse bar; it is process.

## Shape/infra implications

None. No scaffold-type change, no `shape:` flags, no service, no port, no DB. `docs/DECISIONS.md`
is correct and identical for all 12 SCAFFOLD_TYPES (it is type-independent governance, like
CHANGELOG). Rotation-safe: nothing keyed to account dirs; plain files in each repo.

## Constraints digest (rule-grounding gate)

| rule | pack:line | implication |
|---|---|---|
| doc discipline: no skipped headings, fenced blocks only | core/40-documentation | the ledger template complies |
| new .md allowlist | CLAUDE.md § HARD STOPS | `docs/DECISIONS.md` = scaffold-doc class once seeded; hub adds allowlist/naming awareness in the same change |
| synced ≠ project-owned | CLAUDE.md § sync-consciousness | ledger is SEEDED_NOT_ENFORCED — never in the enforced-synced set |
| commands are rules, not changelogs | memory/feedback | the ledger is DATA, not command text — no conflict |
| Doc Sync Matrix is a FLOOR | CLAUDE.md § Doc Sync Matrix | the new keyed row binds same-change appends |

## Approaches considered

1. **Per-repo single-file `docs/DECISIONS.md` decision log + hub grep helper (CHOSEN)** — the
   field's named practice for small-team decision recording (single shared file, append-only,
   never updated in place), with ADR immutability semantics per row (supersede-by-new-row); zero
   infra, git-native WHO/WHEN, works everywhere, one command fleet-wide. Scores 5/5 on the owner
   criteria (quality: field-standard semantics; TCO: ~zero; ship: one plan; maintain: none;
   set-and-forget: yes).
2. **Per-decision ADR files (`docs/decisions/NNNN-*.md`)** — the dominant convention for
   engineering orgs (Fowler, Microsoft, StackFYI) — REJECTED for this fleet: 46 repos × file
   sprawl vs the .md allowlist; the depth a per-file ADR carries (context, options, consequences)
   already lives in our specs/plans — the field itself says the design doc is the planning artifact
   and the record is the pointer; scanning 30 one-line rows beats opening 30 files; and the log
   format is the named right-size for a 1–3-agent "team" per repo.
3. **Postgres table on `postgres-main`** — REJECTED: coupling, credentials in 46 repos,
   offline/worktree failure, self-asserted who/when — and against all three research bodies
   (decision records belong in source control; agent memory defaults to flat files; the operator's
   struggle is a READ problem grep already solves).
4. **Semantic memory service (agentmemory/mem0 class)** — REJECTED for v1: retrieval machinery with
   a service dependency; our declined-semantic-search precedent applies; structured rows make grep
   sufficient. Sits behind the v2 trigger with the hybrid indexer.
5. **Structured data file (JSONL/CSV, one record per line)** — REJECTED (operator asked, 2026-08-30):
   machine-parsing is its only advantage, and no program consumes the ledger — the readers are
   agents-in-chat and the operator, for whom a markdown table renders, scans, and self-documents its
   columns; JSONL renders as noise and needs a schema doc. Grep works identically on both; the ~30-line
   helper parses either trivially. Field practice keeps decision records and agent-memory files as
   markdown-in-repo (§ Research grounding), and the governance doc family + doc-discipline machinery
   (allowlist, sync matrix) already govern the .md shape. Concurrent-append merge behavior is the same
   in both formats.

## Out of scope (each with its destination)

- **Postgres/hybrid backend + semantic retrieval** → rejected above; revisit triggers recorded in
  the backlog row (§ Storage decision).
- **Per-decision ADR files** → rejected (§ Approaches 2); the row + WHERE links carry the load.
- **Backfilling history** → field practice says don't (Docsio, cited); only this week's hub
  decisions seed the hub ledger — wrong-memory rows are worse than absent rows.
- **A web UI / non-engineer browsing layer** (log4brains class) → no audience; the operator reads
  through agents. If that changes, the whychose outgrow signal governs.

## Beat split

- **infra (this repo, my beat):** both CLAUDE.md governance clauses · close-feedback fragment ·
  command Phase-0 wiring · `scripts/decisions.py` (incl. the supersede-pointer check) · the hub
  ledger + seed rows · naming exception · sync seed-if-missing entry.
- **fleet:** scaffolder template seed (`templates/scaffold/`) + PROJECT_CATALOG note.
- **No fabrik-lib involvement** — governance + one stdlib script; the new-module bar is not met.

## Open/blocking unknowns

- **Resolved:** storage (file — grounded); row semantics (immutable + supersede — grounded);
  distribution path (existing sync machinery — verified in predecessor run); enforcement posture
  (advisory-first — the fix directive's measured-before-shipped).
- **Open, non-blocking:** adoption rate is unknowable pre-rollout — the 2-week kaizen measurement
  (§ Enforcement) is the named resolution step. Whether project agents converge on consistent
  "what counts as a decision" judgment — the write-trigger list is the mitigation; the measurement
  reads the actual rows and tightens the list if they diary-drift.

## Residual assumptions

- /opt stays a single filesystem visible to the hub (true today; the fleet helper depends on it).
- Git remains the corroborating who/when layer — repos where commits are batched under one trailer
  weaken WHO precision to the row's own who-cell (acceptable: the cell is primary, git is backup).
