---
description: Converge docs/FEATURES.md to the COMPLETE, testable feature contract — TWO positions. EARLY (after /fabrik-spec-review approval): pin the PLANNED inventory from the approved spec (rows marked Planned) so features are decided BEFORE journeys, contract, and design. REFRESH (5-certify): discover every shipped capability (routes, jobs, CLI, screens, integrations), reconcile bidirectionally, flip Planned→Shipped, every row EXERCISABLE — the certification CROSS-CHECK, not the denominator. TRIGGER — EN: "what are the product's features", "refresh the features list"; TR: "ürünün özellikleri ne olacak", "özellik listesini güncelle". SKIP: the certification itself (→ /fabrik-user-test, /fabrik-service-test). Stage: 5-certify.
argument-hint: "[optional: a subsystem/dir to scope the sweep, or a plan dir / FEATURES section for a scoped REFRESH — omit to converge the WHOLE feature inventory]"
---

Converge this project's `docs/FEATURES.md` into the **complete, testable feature contract**. The
certification gauntlets treat every FEATURES row as inventory ("a TESTED contract, not prose") and
reconcile bidirectionally — so **a missing row is a feature that never gets tested, and a stale row is a
test that can never pass**. This command exists to make that CROSS-CHECK complete BEFORE certification.

⚠️ **FEATURES.md is not the denominator, and saying so is a gate failure.** `check_certification_coverage.py`
flags a cert board whose source resolves to a doc: *"FEATURES.md documents what the project BUILT;
certification must cover what it SHIPS. The doc inventory is a cross-check, never the denominator."*
The denominator is the project's LIVE REGISTRY (its routes, menus, jobs, endpoints — per scaffold type).

{{include:run-record}}
{{include:orient}}

{{include:delegated-reads}}
{{include:term-edit}}
{{include:grounding-artifact}}
## Phase 0 — Establish scope + MODE

Operate on the current project (cwd). **Two sanctioned modes (REFRESH may run scoped) — state which runs:**

- **EARLY (pre-build, right after `/fabrik-spec-review` approval):** the source of truth is the APPROVED
  SPEC (+ `docs/flows.md` if the journeys are already frozen), not the code. Write one row per planned
  feature with `(Planned)` in the Description cell — the product decision, pinned before `/fabrik-flows`
  (the decision itself was MINTED by the spec approval's `docs/DECISIONS.md` row at `/fabrik-spec-review`;
  rows here transcribe it, which is why a row with no spec basis is invented scope)
  walks the journeys that must serve it, before the contract freezes fields for it, before the UI designs
  screens for it. No code sweep; the convergence loop runs spec↔rows bidirectionally (every spec
  capability a row, every row traceable to the spec — a row with no spec basis is invented scope). A Planned row's
  Description states the behaviour as Phase 2 asks of every row, then carries `Spec §<n>:` and EVERY condition of
  its clause — each when, unless, only-if, limit or other condition, wherever in the spec it sits, a neighbouring
  sentence or a table cell included — in the spec's own words or figures, quoted as whole spans cut only at their
  ends, never inside, never reworded and never elided with `…`, the section cited for each span (`Spec §3: … ·
  §7: …`, on the row's one table line): a paraphrase still traces to the spec, and still drops the condition the
  plan then builds without. A Planned row
  that points at existing code it extends cites a SYMBOL in a named file (`src/billing.py::charge`), never a line
  number.
  A row citing a work item (`W-xxxxxxxx`) resolves to `.fabrik/work/W-xxxxxxxx.json` in the store of the repo
  that filed it (a hub item is not in a project's store); check the citation there.
- **REFRESH (post-build, the certify-time default):** the CODE is the source of truth — the full
  multi-modal sweep below. **Planned-row reconciliation:** a `(Planned)` row whose capability now ships
  flips to shipped (drop the marker, fill or re-ground Endpoint/Module + how-to-exercise — an EARLY symbol of
  the code it extended is not the new endpoint; its `Spec §<n>:` conditions stay on the row until a test asserts
  each); a `(Planned)` row with NO
  code at certification time is un-shipped scope — surface it to the operator, never silently delete; a
  shipped capability with no Planned row is scope creep or an honest addition — surface which. An operator
  disposition received on either (drop / keep-planned / adopt) is a RECEIVED decision — its
  `docs/DECISIONS.md` row lands in the same change — stage the row WITH the artifact edit and commit
  them together per CLAUDE.md § EXIT — classified at mint (drop/keep/adopt of un-shipped
  scope are normally reversible — plain rows) (CLAUDE.md § the decision ledger). After a plan, every row its
  merged tickets' `## Deltas` blocks wrote (`/fabrik-execute-plan` D3) is re-grounded like a Planned row, Planned
  or not.

- **REFRESH, scoped** (`$ARGUMENTS` names a plan dir or one FEATURES section): the CODE stays the denominator,
  narrowed — Phase 1 sweeps the registry entries (routes, jobs, screens, CLI) the plan's diff added or changed, or
  the code behind the named section, instead of the whole codebase. The doc side checked against it is every
  row on that code, every row the plan's `## Deltas` blocks wrote, and one row per user-observable behaviour in
  the plan's tickets' `## Behavior Contract` (several Given/When/Then rows can map to one). State the scope and
  the population it gives. A scoped run never hands off to certification.

Mode ambiguity resolves reversibly: no `docs/FEATURES.md` on disk → seed it from the template first, then
reconcile; EARLY invoked where code already ships → say so and run REFRESH instead (the code outranks the
spec once it exists), except for features the approved spec ADDS: those are EARLY rows, marked `(Planned)`, in the same file.

The artifact is `docs/FEATURES.md` (scaffold-seeded from
`templates/scaffold/docs/FEATURES_TEMPLATE.md` — that template IS the canonical shape: category sections,
`| Feature | Description | Endpoint / Module |` tables). If `$ARGUMENTS` names a subsystem, scope
the sweep to it and say so; a plan dir or a FEATURES section heading runs REFRESH scoped (above); otherwise the WHOLE codebase is the denominator. Read the frozen contracts if present
(`docs/data-contract.md`, `docs/ui-design.md`) and the spec `shape:` — features must not contradict them.

## Phase 1 — Discover every shipped capability (multi-modal sweep — each mode catches what the others miss)

Treat the CODE as the source of truth, never the existing doc. Enumerate capabilities from EVERY surface
that exists in this project:

- **Routes/API:** the router/app registrations (FastAPI/Express routes, `include_router`, URL maps) — every
  endpoint group a consumer can call.
- **Jobs/workers:** Beat/cron schedules, queue consumers, `@task` handlers (`docs/RESILIENCE.md` §7 is the
  canonical jobs inventory — reconcile against it, don't duplicate it).
- **CLI/entrypoints:** `pyproject.toml`/`package.json` scripts, `__main__`, Makefile targets a user runs.
- **UI screens/flows** (GUI projects): `docs/ui-design.md` screens + the real router/nav — every screen a
  user reaches is a feature surface.
- **Integrations:** external services the code actually calls (payment, email, storage, search).
- **Claims elsewhere:** `README.md`/`docs/QUICKSTART.md` feature claims — anything promised there must map
  to a row or be flagged as vapor.

A capability that exists in code but not in the sweep output is the exact miss this command exists to
prevent — enumerate what you READ (files × surfaces), not what you remember.

## Phase 2 — Reconcile bidirectionally + make every row EXERCISABLE

- **Code → doc:** every discovered capability gets a row in its category table. **No capability without a
  row.**
- **Doc → code:** every existing row's `Endpoint / Module` must cite code that EXISTS (open it — a
  path that looks right is not grounding). A row whose code is gone is deleted (state the removal); a row
  whose feature half-exists is corrected to what is true today. A route row's claim holds for every mode the route
  serves — its default and each query-parameter variant — or names the modes it covers. **No row without living code.**
- **Exercisable rows — the gauntlet contract:** every row carries a non-empty **`Endpoint / Module`** cell
  (`METHOD /path` · `src/module.py` · screen name — the thing a gauntlet agent drives), and its Description
  states the user-observable behavior (what a test would assert), not implementation trivia. A row the
  gauntlets cannot turn into a scenario ("improved architecture") is not a feature row — cut or rewrite it.
- **State honesty:** deprecated/disabled/feature-flagged capabilities are marked so (`(beta)` /
  `(deprecated — <date>)`) — a gauntlet must know whether a red scenario is a defect or a flag. A shipped row states the CURRENT
  behaviour; a known defect is a pointer to its backlog row or work item, never an enumeration of its cases. A code
  defect the grounding finds with no row yet is filed to its owner (a mail to the code's owning session, or a backlog
  row) and the feature row points at that id — never patched inside a features run.
- Keep the template's shape: customer-oriented categories, benefit-oriented descriptions. 

## Phase 3 — Converge (the self-audit LOOP — iterate to a no-op)

Run repeated passes until the Termination contract's closing round — `confirmed: 0`, md5 unchanged — is reached.
Each pass re-checks ALL of:

1. **Coverage** — before counting, name each denominator's expected population and where it comes from (the
   router's route count, the jobs inventory, the scoped mode's list), so a 0 or a partial walk fails loudly; count a table's data rows by
   anchoring on them, never by `tail -n +N` after a filter (a separator row the filter drops shifts the offset);
   then re-run a fresh Phase-1 sweep on the CURRENT code: any capability the previous pass
   missed? Any route/job/screen added since?
2. **Grounding** — every row's citation opens to real code (spot-check ALL new rows, sample the old).
3. **Exercisability** — every row could be turned into a gauntlet scenario by an agent with no other
   context; every `README`/`QUICKSTART` claim maps to a row or a flagged gap.
4. **Consistency** — no row contradicts `docs/data-contract.md`, `docs/ui-design.md`, or the spec
   `shape:`; `Last Updated:` bumped; Doc Sync Matrix ripples applied (a feature row change may touch
   `QUICKSTART.md`).

After each pass, list what you re-read and what changed, then run one MORE pass — the loop terminates ONLY
at the Termination contract's closing round (`confirmed: 0`, md5-verified).

## Guardrails — never

- Trust the existing FEATURES.md as the inventory — the CODE is the denominator; the doc is the claim.
- Write a row you didn't ground in an open file (`path:line` or a driven route; a Planned row's symbol in a
  named file) — memory is not discovery.
- Pad with implementation trivia ("refactored X", "uses Redis") — features are user-observable behaviors.
- Delete a row silently.
- Leave a `README`/`QUICKSTART` claim unmapped.
- Hand off to certification from a scoped REFRESH.
- Hand off to certification while the loop is non-quiet.

{{include:subagents-core}}

{{include:close-chain}}
