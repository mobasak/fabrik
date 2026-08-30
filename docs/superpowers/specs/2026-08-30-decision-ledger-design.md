# The Decision Ledger — every agent records decisions, every agent queries them first

Status: DRAFT
Date: 2026-08-30
Scale verdict: **feature-scale** — one plan (governance text + template + seed + search helper + corpus wiring).
Surface: `templates/governance/CLAUDE.md` + `CLAUDE.md` + `templates/scaffold/` + `commands/_fragments/` + one hub helper script + per-repo `docs/DECISIONS.md`.

## Personas

**PRIMARY — the operator, in their own words (2026-08-30):** *"all ai agents must keep a decision
ledger/diary postgres db or file. and always query it. i dont want to struggle like this again. all
decisions will be recorded in all repos from now on with why, what, where, who, when."*
Their minimal loop, step-counted (BUDGET = 2): (1) ask any window "where is X / did we decide Y" →
(2) get the answer from a ledger row, with the why and the where — not a multi-hour hunt. Two steps;
anything longer regresses the persona this exists for.

**The writer** — every AI agent in every repo (3 hub roles + ~46 project agents + wef-class
multi-window repos): must be able to append a row in one edit, mid-run, with zero infrastructure
(no DB connection, no service up).

**The reader-under-amnesia** — a future session, post-compaction or weeks later, that must answer
from the record rather than reconstruct. This persona is why entries carry WHERE (paths/ids), not
prose alone.

**The cross-repo querier** — a hub agent answering a fleet-wide question ("which repos decided to
retire Supabase?"): needs one command over all ledgers, not 46 file opens.

**The receiver who never consented** — nobody; the ledger is internal. (Enumerated to satisfy the
personas contract's receiver check: no external party is touched.)

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "all ai agents must keep a decision ledger/diary" | IN | § The ledger file · § Write duty |
| I2 | "postgres db or file" | IN — decided FILE, postgres rejected with reasons | § Storage decision |
| I3 | "and always query it" | IN | § Query duty |
| I4 | "i dont want to struggle like this again" | IN — the success criterion | § Success criteria |
| I5 | "all decisions will be recorded in all repos from now on" | IN | § Distribution · § Write duty |
| I6 | "with why, what, where, who, when" | IN — the frozen row shape | § Entry format |

Intake: 6 items — 6 IN, 0 OUT-OF-SCOPE, 0 ASK.

## The motivating failure (why this exists)

2026-08-30: "where is our own crawling MCP?" cost three sessions a combined multi-hour hunt (roster,
/opt sweep, fabrik-lib, 4 lexical session-recall queries, specs, backlogs) and produced one WRONG
answer that propagated between sessions — because the underlying decisions were never recorded
anywhere queryable. Same class, same week: the wef approval-gate re-ask, the quota-governance
window misroute. session-recall is lexical over transcripts: a decision phrased differently is
invisible. Lessons record failures; CHANGELOG records changes; **nothing records decisions.**

## Storage decision (I2): FILE, per repo — postgres REJECTED (this is itself ledger row D-001)

**`docs/DECISIONS.md`, one per repo, append-at-top, project-OWNED (never sync-overwritten).**

Why file beats postgres here, each reason load-bearing:
- **WHO + WHEN come free and tamper-evident** from git (`git log -- docs/DECISIONS.md` + the
  Agent-Name trailer discipline); a DB row's who/when is self-asserted.
- **Zero coupling:** works in every repo including sync-excluded ones (fabrik-lib), offline, in
  worktrees, on the VPS — a postgres ledger couples 46 repos to `postgres-main` liveness and
  credentials for the most basic act of remembering.
- **Grep-first agents:** every query duty below is a `Grep`/`Read` — the tools agents already
  hold; a DB needs a client, a DSN, and a rotation-safe secret in 46 places.
- **The industry-standard shape:** this is the ADR "decision log" practice (adr.github.io,
  fetched 2026-08-30 — "a justified design choice… enabling future stakeholders to understand the
  trade-offs"), adapted to ONE ledger file per repo instead of one file per decision — leaner to
  grep, and 46 repos of per-decision file sprawl is the .md-allowlist's enemy.
- **Cross-repo query stays one command** (§ Query duty) because /opt is one filesystem.

**Hybrid (per-repo file + hub indexer) is deliberately v2, not now:** the grep-over-/opt query
below is O(46 files) and instant; an indexer is machinery with no measured need yet. Revisit only
if ledgers grow past grep usefulness (backlog row, measured trigger: >2s query or >500 rows/repo).

## Entry format (I6 — the frozen row)

`docs/DECISIONS.md` is a table, newest row FIRST, one row per decision:

```markdown
# Decisions

Append-at-top. One row per decision. WHY ≤ 2 lines; the full rationale lives at the WHERE links.
Query: grep this file first; fleet-wide: `python3 /opt/fabrik/scripts/decisions.py <term>`.

| id | when | who | what (the decision) | why | where |
|---|---|---|---|---|---|
| D-003 | 2026-08-30 | operator+infra | context7 MCP retired from window roster | 45 lifetime calls vs 364MB/window; WebFetch covers it | 74ad8a06 · docs/workstation/mcp-roster.md |
```

- **id**: `D-NNN`, monotonic per repo (collision on concurrent append = ordinary merge conflict,
  visible and trivially fixed — no lock machinery).
- **who**: `operator` · `infra|fleet|intel` · the repo's agent · `operator+<agent>` when the
  operator ruled and the agent executed. The commit's trailers corroborate.
- **what/why**: one line each — a ledger scans; it does not essay.
- **where**: commit sha(s) · paths · spec/plan/mail ids — the pointers that turn a row into the
  full story. THIS is what kills the crawling-MCP hunt: the row says where the thing lives.
- **when**: date. Finer grain comes from git.

**What is a "decision" (the write trigger, kept sharp so this is a ledger, not a diary):** an
operator ruling in chat · a spec/plan approval or Status flip · a retirement/adoption
(tool, vendor, pattern, MCP, module) · an architecture/storage/scope choice · "we built X, it
lives at Y" · a rejected option worth not re-proposing (the memory system's "don't re-propose"
class, now fleet-visible). NOT a decision: routine fixes, refactors, doc edits — those are
CHANGELOG's beat.

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
   *"did this run make or receive a DECISION? → row appended, or `none`"* (the feedback-duty
   model: the close is the moment the context still exists).
3. **Chat rulings:** an operator ruling mid-conversation is a decision the moment it lands —
   the receiving agent appends the row in its next commit.
4. **Cross-repo decisions** (hub rules affecting all repos): recorded ONCE in the hub ledger;
   project ledgers record only project-local decisions — no fan-out duplication.

## Query duty (I3)

1. **Before answering "where is X / did we decide Y / why is Z like this": Grep `docs/DECISIONS.md`
   (repo) then `python3 /opt/fabrik/scripts/decisions.py <term>` (fleet) BEFORE any wider hunt** —
   added to the governance read-it-don't-recall-it clause and the session-recall mandate (ledger
   first: structured beats lexical).
2. **/fabrik-spec Phase 0 episodic-memory step + /fabrik-plan-after-chat grounding + the ASK-bar
   derivation sources**: `docs/DECISIONS.md` joins the list of frozen artifacts consulted before
   any question reaches the operator.
3. **The fleet helper:** `scripts/decisions.py` (hub) — `grep -i` over `/opt/*/docs/DECISIONS.md`
   + the hub's own, printing `repo · id · when · who · what · where`. ~30 lines, stdlib, read-only.

## Distribution (I5)

- **New repos:** the scaffolder seeds the header + D-000 row ("repo scaffolded, type X, spec Y") —
  fleet's beat (`templates/scaffold/`).
- **Existing ~46:** seed-if-missing via the sanctioned sync machinery
  (`sync_enforcement_to_projects.py` gains a seed-not-overwrite entry, exactly PORTS.md's
  SEEDED_NOT_ENFORCED class) — the file is project-owned from birth; the sync NEVER touches an
  existing ledger.
- **Hub:** `docs/DECISIONS.md` created in this plan, seeded with this week's real decisions
  (context7 retirement · volume-prune withdrawal + never-offer rule · cache-prune _npx gate ·
  persona law · design-system ladder · governance-sync post-commit move · ASK-bar · this very
  storage decision) — the format proven on real rows on day 1.
- **Naming:** `DECISIONS.md` joins CLAUDE.md's naming-exceptions list (sibling of FEATURES.md).

## Enforcement (measured-first, per the fix directive)

Day 1: **advisory only** — the close-out line + the Doc Sync Matrix row (judgment-enforced like the
rest of the matrix's floor). NO mechanical gate yet: "did this run contain a decision" is not
mechanically decidable, and a check that nags every commit is wallpaper. Measure after 2 weeks
(kaizen can count ledger appends/repo); if adoption is ~zero, the escalation is a check that a
`Status:`-flip commit touches DECISIONS.md in the same change — THAT subset is mechanical. Backlog
row carries the trigger.

## Success criteria (I4)

- The crawling-MCP question class ("where is X / did we decide Y") answers from a ledger row in
  ≤ 2 steps — no exhaustive hunts.
- A rejected option (Factory, Supabase, per-project binding…) is never re-proposed by an agent that
  queried the ledger — the memory system's protection, now fleet-wide.
- Zero new infrastructure: no DB, no service, no daemon; works in every repo today.

## Out of scope (each with its destination)

- **Postgres/hybrid backend** → rejected above; revisit trigger recorded in the backlog row.
- **Semantic search over ledgers** → session-recall's declined-semantic decision applies (ledger
  rows are structured precisely so grep suffices).
- **Per-decision ADR files** → rejected for sprawl; the row + WHERE links carry the load.
- **Backfilling history** → only this week's hub decisions seed the hub ledger; deeper archaeology
  is not worth the reconstruction risk (wrong-memory rows are worse than absent rows).

## Beat split

- **infra (this repo, my beat):** both CLAUDE.md governance clauses · close-feedback fragment ·
  command Phase-0 wiring · `scripts/decisions.py` · the hub ledger + seed rows · naming exception ·
  sync seed-if-missing entry.
- **fleet:** scaffolder template seed (`templates/scaffold/`) + PROJECT_CATALOG note.
- **No fabrik-lib involvement** — governance + one stdlib script; the new-module bar is not met
  (not code ≥2 types vendor; it is process).

## Constraints digest (rule-grounding gate)

| rule | pack:line | implication |
|---|---|---|
| doc discipline: no skipped headings, fenced blocks only | core/40-documentation | the ledger template complies |
| new .md allowlist | CLAUDE.md § HARD STOPS | `docs/DECISIONS.md` = scaffold-doc class once seeded; hub adds allowlist/naming awareness in the same change |
| synced ≠ project-owned | CLAUDE.md § sync-consciousness | ledger is SEEDED_NOT_ENFORCED — never in the enforced-synced set |
| commands are rules, not changelogs | memory/feedback | the ledger is DATA, not command text — no conflict |

## Approaches considered

1. **Per-repo `docs/DECISIONS.md` + hub grep helper (CHOSEN)** — zero infra, git-native W5,
   works everywhere, one command fleet-wide.
2. Postgres table on postgres-main — rejected: coupling, credentials in 46 repos, offline/worktree
   failure, self-asserted who/when, and the operator's struggle is a READ problem grep already solves.
3. Per-decision ADR files (`docs/decisions/NNNN-*.md`) — rejected: 46 repos × file sprawl vs the
   .md allowlist; scanning 30 one-line decisions beats opening 30 files; MADR's depth belongs in
   specs, which we already have.
