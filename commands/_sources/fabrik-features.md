---
description: Converge docs/FEATURES.md to the COMPLETE, testable feature contract — TWO positions. EARLY (after /fabrik-spec-review approval): pin the PLANNED inventory from the approved spec (rows marked Planned) so features are decided BEFORE journeys, contract, and design. REFRESH (5-certify): discover every shipped capability (routes, jobs, CLI, screens, integrations), reconcile bidirectionally, flip Planned→Shipped, every row EXERCISABLE — the certification DENOMINATOR. TRIGGER — EN: "what are the product's features", "refresh the features list"; TR: "ürünün özellikleri ne olacak", "özellik listesini güncelle". SKIP: the certification itself (→ /fabrik-user-test, /fabrik-service-test). Stage: 5-certify (EARLY run sanctioned at design exit).
argument-hint: "[optional: a subsystem/dir to scope the sweep — omit to converge the WHOLE feature inventory]"
---

Converge this project's `docs/FEATURES.md` into the **complete, testable feature contract**. The
certification gauntlets treat every FEATURES row as inventory ("a TESTED contract, not prose") and
reconcile bidirectionally — so **a missing row is a feature that never gets tested, and a stale row is a
test that can never pass**. This command exists to make that denominator complete BEFORE certification.

{{include:run-record}}
{{include:term-edit}}
{{include:grounding-artifact}}
## Phase 0 — Establish scope + MODE

Operate on the current project (cwd). **Two sanctioned modes — state which runs:**

- **EARLY (pre-build, right after `/fabrik-spec-review` approval):** the source of truth is the APPROVED
  SPEC (+ `docs/flows.md` if the journeys are already frozen), not the code. Write one row per planned
  feature with `(Planned)` in the Description cell — the product decision, pinned before `/fabrik-flows`
  walks the journeys that must serve it, before the contract freezes fields for it, before the UI designs
  screens for it. No code sweep; the convergence loop runs spec↔rows bidirectionally (every spec
  capability a row, every row traceable to the spec — a row with no spec basis is invented scope).
- **REFRESH (post-build, the certify-time default):** the CODE is the source of truth — the full
  multi-modal sweep below. **Planned-row reconciliation:** a `(Planned)` row whose capability now ships
  flips to shipped (drop the marker, fill Endpoint/Module + how-to-exercise); a `(Planned)` row with NO
  code at certification time is un-shipped scope — surface it to the operator, never silently delete; a
  shipped capability with no Planned row is scope creep or an honest addition — surface which.

The artifact is `docs/FEATURES.md` (scaffold-seeded from
`templates/scaffold/docs/FEATURES_TEMPLATE.md` — that template IS the canonical shape: category sections,
`| Feature | Description | Endpoint / Module |` tables). If `$ARGUMENTS` names a subsystem, scope the sweep
to it and say so; otherwise the WHOLE codebase is the denominator. Read the frozen contracts if present
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
- **Integrations:** external services the code actually calls (payment, email, storage, search) — each is a
  user-visible capability ("sends receipts", "full-text search").
- **Claims elsewhere:** `README.md`/`docs/QUICKSTART.md` feature claims — anything promised there must map
  to a row or be flagged as vapor.

A capability that exists in code but not in the sweep output is the exact miss this command exists to
prevent — enumerate what you READ (files × surfaces), not what you remember.

## Phase 2 — Reconcile bidirectionally + make every row EXERCISABLE

- **Code → doc:** every discovered capability gets a row in its category table. **No capability without a
  row.**
- **Doc → code:** every existing row's `Endpoint / Module` must cite code that EXISTS (open it — a
  path that looks right is not grounding). A row whose code is gone is deleted (state the removal); a row
  whose feature half-exists is corrected to what is true today. **No row without living code.**
- **Exercisable rows — the gauntlet contract:** every row carries a non-empty **`Endpoint / Module`** cell
  (`METHOD /path` · `src/module.py` · screen name — the thing a gauntlet agent drives), and its Description
  states the user-observable behavior (what a test would assert), not implementation trivia. A row the
  gauntlets cannot turn into a scenario ("improved architecture") is not a feature row — cut or rewrite it.
- **State honesty:** deprecated/disabled/feature-flagged capabilities are marked so (`(beta)` /
  `(deprecated — <date>)`) — a gauntlet must know whether a red scenario is a defect or a flag.
- Keep the template's shape: customer-oriented categories, benefit-oriented descriptions. This file doubles
  as public feature documentation — write for the customer, cite for the agent.

## Phase 3 — Converge (the self-audit LOOP — iterate to a no-op)

Run repeated passes until one demonstrably-thorough pass makes **zero edits** (the Termination contract).
Each pass re-checks ALL of:

1. **Coverage** — re-run a fresh Phase-1 sweep on the CURRENT code: any capability the previous pass
   missed? Any route/job/screen added since?
2. **Grounding** — every row's citation opens to real code (spot-check ALL new rows, sample the old).
3. **Exercisability** — every row could be turned into a gauntlet scenario by an agent with no other
   context; every `README`/`QUICKSTART` claim maps to a row or a flagged gap.
4. **Consistency** — no row contradicts `docs/data-contract.md`, `docs/ui-design.md`, or the spec
   `shape:`; `Last Updated:` bumped; Doc Sync Matrix ripples applied (a feature row change may touch
   `QUICKSTART.md`).

After each pass, list what you re-read and what changed, then run one MORE pass — the loop terminates ONLY
on an edit-free, md5-verified no-op round.

## Guardrails — never

- Trust the existing FEATURES.md as the inventory — the CODE is the denominator; the doc is the claim.
- Write a row you didn't ground in an open file (`path:line` or a driven route) — memory is not discovery.
- Pad with implementation trivia ("refactored X", "uses Redis") — features are user-observable behaviors.
- Delete a row silently — a removed feature is stated in the run report (the operator may be tracking it).
- Leave a `README`/`QUICKSTART` claim unmapped — vapor claims are findings, not decoration.
- Hand off to certification while the loop is non-quiet — an unconverged denominator silently shrinks the
  gauntlet.

{{include:subagents-core}}
