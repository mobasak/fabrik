# /fabrik-task carries feature-sized work; the spec chain is for modules — design

Status: CONVERGED (D-487, /fabrik-spec-review 2026-10-02 — awaiting the operator's design approval)
Profile: delta — on `docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md` (D-293, D-314, D-315). Every Intake item maps to code that exists today (`scripts/command_run.py::_task_size_gate`, `commands/_sources/fabrik-task.md`, the two CLAUDE.md lane tables, `commands/_sources/fabrik-plan-after-chat.md` § Profile: small); one new consumer is named (Volkan's `/task` port, D-319), so `## Personas` is written in full.
Owner: infra · Intake: mail 01M3WJMFWAXHT81W0ETCFZTNV6 (web-ecommerce-factory, supersedes 01M3WJ6B) · W-e053ba60

## Personas

- **PRIMARY — the operator**, in their own words: *"fabrik-task must cover more work. this is very limited"* and *"for a feature addition fabrik-task should be able to be used. spec/specreview/plan/planreview/execute/review cycle must be bigger modules."* (2026-10-01, quoted in the intake mail), then to infra 2026-10-02: *"i need one major change now too."* The operator pays in wall-clock: every change the gate sends to the chain costs ~6.6 h of agent time before it ships (§ What exists today, row 5).
- **The lane's driver — any repo agent** (hub infra/fleet/intel; the ~46 synced projects' main-checkout and worktree agents; fabrik-lib's three) choosing a lane at § Orient step 0. It holds every declaration and the close.
- **`command_run.py` (automated)** — holds the gate: `start` admission, the `round`/`line` status, the `done` re-measure. It is fleet-synced, so every repo runs the same gate.
- **The phase-4 review seats (automated)** — `/fabrik-review-scoped` or the full `/fabrik-review`, chosen by surface; they hold the UPGRADE verdict.
- **The merge owner** of each repo (D-471) — receives a multi-commit task branch as one merge request.
- **Consumers outside the hub's sync:** fabrik-lib (sync-excluded; its CLAUDE.md is generated, so it adopts by mail) and Volkan's Mac `/task` port, which carries a SELF-GRADED copy of the size gate without `command_run.py` (D-319) — it gets the new rule text by mail, not code.

**Step budget — the primary's loop, counted:** (1) state the feature → (2) agent declares at `start` and is admitted → (3) design note with the Behaviours list → (4) build, one or more commits → (5) review sized by surface → (6) close → (7) merge request merged. **7 steps** (a close-time `upgrade` record does not add a step: the work is committed; it is a measured verdict the kill criteria count), against the chain's spec → spec-review → approval → plan → plan-review → execute → finish review → merge (8 stages, three of them review loops). The budget is frozen: a later change that adds a step to the lane owes a bump here.

## Goal

A feature that settles one reversible decision, touches no public contract, and fits one working session goes through `/fabrik-task`, however many existing files it edits. The spec chain is reserved for **modules**: work that changes something read outside the repo, a one-way decision, an open trade-off, a body of new source files, or more than a session of work.

## Why this exists

The lane's only size test is a file count: more than 3 declared files sends the work to the chain (`scripts/command_run.py:2809` `_TASK_MAX_FILES = 3`, applied at :3178-3192). That number was grounded on commit size, not on how much has to be decided: *"69% touch ≤3 non-ledger files … "≤3" is the two-thirds line, not a round number"* (lane spec :91). Measured consequence since the lane shipped (feedback ledger, 594 rows since 2026-09-18, re-derived 2026-10-02):

| Path | Runs | Median | Total |
|---|---|---|---|
| `/fabrik-task` | 20 (17 done, 3 handed off = 15%) | 46 min | 17.7 h |
| `/fabrik-spec` | 32 | 60 min | 64.1 h |
| `/fabrik-spec-review` | 38 | 45 min | 67.5 h |
| `/fabrik-plan-after-chat` | 26 | 52 min | 33.3 h |
| `/fabrik-plan-review` | 29 | 39 min | 30.7 h |
| `/fabrik-execute-plan` | 31 | 197 min | 167.1 h |

A chain change runs ~6.6 h at the medians (60+45+52+39+197 min), 363 h in total; 3.3 h of each is documents and their own review loops before code. Small work rode it: a one-file fix (fabrik-lib revenuecat `state.py`), a wizard guard with 884 min of execution under `Profile: small` (tryton-crm), an 8-minute task refused on `files` that became a 209-minute spec (web-ecommerce-factory wef1), and one decision across 6 files with ~4.5 h of spec so far (web-ecommerce-factory llm-dispatch). Field practice sizes by decision, not by files (§ External dependencies): Google writes a design doc when the design is ambiguous or has trade-offs, else *"write the actual program right away"*; Rust needs an RFC only for "substantial" changes to the user-visible surface; Amazon splits one-way from two-way doors; Shape Up bounds work by a fixed time "appetite". The approach below replaces the file count with exactly those tests, so the four cases above enter the lane while modules still go to the chain.

## What exists today (grounded)

1. **The gate** — `scripts/command_run.py:3019` `_task_size_gate`. The close diffs with `--name-status -M -C` (`:3363`), so a copied file reads `C`, not `A`; `.sql` is a Doc Sync suffix (`:3232`), so `db/schema.sql` is in the close's exclusion set; a second `--design` is ignored with a NOTE (`:3952-3958`). Declare keys `:2807` `("decision", "heavy", "mechanism", "oneway", "tradeoffs")` — there is no `sync` key; sync is an executable regex read from `.pre-commit-config.yaml` (`:3143-3162`, fails OPEN with a warning when unreadable). Precedence `:3178-3192`: files > 3, `oneway`, `tradeoffs` → `/fabrik-spec`; then sync, `heavy` → "right-now + /fabrik-review"; then `decision!=yes` → "right-now + /fabrik-review-scoped". `mechanism` is recorded only (D-315).
2. **The close** — `done` requires `--commit` (one SHA, `:3616`, `:3478`), re-measures it, and RECORDS undeclared or oversized paths as `oversized_mini` (`:3571-3572`, `:3658`), never refuses them; exclusions are the five ledgers + `docs/CAPABILITIES.md` + the Doc Sync Matrix destinations (`:3216-3297`).
3. **The command** — `commands/_sources/fabrik-task.md`: SIZE :19 · MEASURE :48 · DESIGN :54 (six fields, `--design` uncapped, D-314) · BUILD :72 · REVIEW :78 (`/fabrik-review-scoped`) · CLOSE :86 (`oversized_mini` recorded, :110-111) · UPGRADE :113 (`files`/`oneway`/`tradeoffs`/`seat` hand off to `/fabrik-spec`; `sync`/`heavy` upgrade in place to the full review).
4. **The lane tables** — `CLAUDE.md:70` (precedence) and rows `:75-82`; `templates/governance/CLAUDE.md:64`, rows `:68-75`. Rows 2–6 identical; rows 1/1b differ in wording only. The template reaches 47 repos by the governance sync; fabrik-lib regenerates its own.
5. **`Profile: small`** — defined in `commands/_sources/fabrik-plan-after-chat.md:210-224` (D-169: ≤ ~400 code lines AND ≤ 5 code files); honoured by `/fabrik-execute-plan` (:48, :250-252) and `/fabrik-review-scoped` (:31). `/fabrik-spec-review` and `/fabrik-plan-review` never mention it; spec-review ends at the operator's design-approval gate (`fabrik-spec-review.md:280-294`), plan-review runs to CONVERGED with no gate (`fabrik-plan-review.md:17`).
6. **Replay** (last 300 non-merge hub commits ending c84f0b0b7, `git log --no-merges -300` + `show --name-status`; FILES = distinct paths minus the five ledgers, `docs/CAPABILITIES.md`, `docs/reference/`, `docs/workstation/`, `docs/development/reviews/`, `.fabrik/work/`; new source = status `A`, not under `tests/`, not `test_*`, not `.md`; sync = the governance-sync `files:` regex of `.pre-commit-config.yaml`; docs-only = every path `.md` or under `.fabrik/`): 191 docs-only; of the 109 others, 47% touch a sync path, 65% touch ≤3 files, 84% ≤5, and 95% add ≤2 new non-test non-doc source files. Lane-eligible: today's rule (not sync, ≤3 files) 45 of 109 (41%); the proposed (not sync, ≤2 new source files) 56 of 109 (51%). In the hub the sync filter, not the file count, is the dominant exclusion; projects rarely touch a sync path, so the file count is their binding constraint.

## The delta

**D1 — The module test replaces the file count at `start`.** `_TASK_MAX_FILES` and its refusal go; `--file` stays required (the declared paths feed the sync and contract tests at `start`). A change goes to the spec chain when ANY of these holds; otherwise it is `/fabrik-task`:

| Test | How it is answered | Checked again at close |
|---|---|---|
| **contract** — changes something read outside this repo | declared `consumers=external\|internal`, plus an executable path test: `specs/services/` and any `openapi*.json`/`openapi*.yaml` or `*.schema.json` at any depth, outside dependency directories (`node_modules/`, `.venv/`, `vendor/`) | yes — the close runs the path test over EVERY committed path before any exclusion is applied (so a Doc Sync destination cannot hide one) |
| **oneway** — costly or impossible to undo | declared (unchanged); a destructive migration (drop, rename, type change) is `oneway=yes` by definition | — |
| **tradeoffs** — two approaches to settle before building | declared (unchanged) | — |
| **new-source** — more than 2 new files that are neither tests nor `.md` | executable at close: status `A` OR `C` (a copy is a new file) | yes |
| **appetite** — more than one session | declared `--appetite <minutes>`, default 240; > 240 → chain | elapsed vs appetite (D4) |

At `start` a hit sends the work to the chain: a declared `consumers=external`, or a declared `--file` matching the path test. `consumers=internal` never overrides a path hit, so outside fabrik-lib the declaration can only add a hit, never remove one. A hit first seen at CLOSE — a committed path the agent did not declare that matches the path test, or a third new source file — cannot un-build committed work, so it takes the heavy-surface treatment: the close records `upgrade: contract` or `upgrade: new-source`, and `done` and `handoff` are REFUSED until `--review <receipt>` names a receipt that (a) lies under `docs/development/reviews/`, (b) passes `scripts/enforcement/check_review_coverage.py`, (c) names exactly `/fabrik-review` on its `**Command:**` line — `/fabrik-review-scoped` shares the prefix and does not discharge it — and (d) was made with `review_receipt.py --range <base>..<last listed commit>`, so its `**Surface:**` line ends at the run's last commit. That receipt is the one committed path D3.3's declaration check exempts — the close itself demands it. `blocked` records the `upgrade:` and does not require the receipt: a sanctioned halt is never trapped. A governance-sync path keeps today's disposition — right-now with the full `/fabrik-review`, outside the lane (row 1, unchanged; it is not sent to the chain). In fabrik-lib, whose modules are top-level directories vendored by ~46 repos (it has no `libs/`), the contract test is the declaration plus fabrik-lib's own ruling on what its public interface is — routed to it by mail (§ Open unknowns).

**D2 — Heavy surfaces enter the lane with the full review.** `heavy=yes` (a project's `libs/` copied from fabrik-lib — the hub's own `libs/subagents/` stays off-limits to the hub, D-137 — a gate or hook outside the sync filter, auth, concurrency, operator-named work, and any migration file: a path segment `migrations/` or `alembic/versions/` at any depth, e.g. `web/db/migrations/`, `apps/web/prisma/migrations/`) no longer leaves the lane: phase 4 runs the full `/fabrik-review` instead of the scoped one. More than 5 touched files likewise selects the full review (matching CLAUDE.md § 1a's review sizing). Neither is a refusal.

**D3 — `/fabrik-task` gains, and only these:**
1. A `## Behaviours` list in the design note: each behaviour names its test; at most 7. An 8th is an UPGRADE (the work is a module).
2. Several commits under one record: `done --commit` accepts a comma-separated list, measured commit by commit in the given order; a path renamed in an earlier commit carries its declared membership into the later ones (the `:3519-3541` rule applied across the list, never a range diff that could pull in another session's commits).
3. Every committed non-excluded path must appear (backticked) in the design note's APPROACH or MIRROR, or the close REFUSES — today it is only recorded. To keep that refusal from wedging a run that found it needs one more file, the design note gains an APPEND-only amendment (`step --phase 2 --design-amend <file>`): it adds a paragraph, never overwrites the recorded design (the lane spec's "no later step overwrites it", `2026-09-17-fabrik-task-lane-design.md:106`, holds), and the close records `design_amends: <n>` with the paths each amendment added, so a refusal answered by a late amendment is counted, not free. The refusal applies to `done` only; `blocked` and `handoff` record their commits as today. Listing every path is the plan the lane does not otherwise write, so the cheap path produces the outcome.
4. `loc_added` recorded at close; more than 800 added lines is printed as a `change:` finding, not a refusal.

It does NOT gain a spec file, a plan file, a plan review, a ticket board or a second review loop — those would rebuild the chain inside the lane.

**D4 — The appetite is visible and has a breaker.** `line` prints `elapsed <m>/<appetite> min`. Past 2× the appetite the line prints the UPGRADE order every turn and the close records `over_appetite`. It is not a refusal: Shape Up's circuit breaker cancels by default, but an agent mid-commit cannot be cancelled without stranding work, so the breaker here is a standing order plus a recorded verdict the kill criteria count (§ Validation). Divergence from the source stated, not hidden.

**D5 — (moved out.)** Folding spec-review into plan-review under `Profile: small` cannot be decided here: the profile is set by `/fabrik-plan-after-chat` from a plan's size (`fabrik-plan-after-chat.md:210-224`), after the spec, and moving the operator's approval gate needs its own design. It is independent of D1–D4 and goes to its own change (STRATEGIC_BACKLOG row "Profile: small — one design-review loop").

**D6 — Independent slices are several task runs.** A feature that splits into slices each shippable alone takes several `/fabrik-task` runs, not the chain. Only slices tied by a shared, unsettled design belong in the chain — and the `tradeoffs` test already sends those there.

## Contract deltas

No data-contract or ui-design change. The interface change is to `command_run.py` for `fabrik-task`: `start` keeps `--file`, `--declare` gains `consumers=external|internal`, `--appetite <min>` is new (default 240), the `files` refusal is removed, and `start` stamps `gate: 2` on the record; `step --phase 2 --design-amend` is new; `done --commit` accepts a list and `done --review <receipt>` is new (none exists today); the close may record `upgrade: contract|new-source|behaviours` itself (today `upgrade` is parsed only from `--evidence`, `:3305`). Both CLAUDE.md lane tables: row 5 (files > 3) is replaced by the module tests and row 1b's disposition changes per D2; rows 1, 2, 3, 4 and 4b are unchanged. A governance-sync change: the template reaches 47 repos at merge; fabrik-lib and Volkan's port by mail.

## Cost

Build: `command_run.py` gate + close (~200 lines with tests), `fabrik-task.md`, two CLAUDE.md tables. Full `/fabrik-review` before merge (sync path). Run cost falls: on the replay, 12 hub commits per 109 newly qualify and 1 no longer does (≤ 3 files but > 2 new source files), a net +11; in projects the 3-file wall is the binding constraint and most feature work clears it.

## Validation

- **V0 (before rollout):** replay the last 300 hub commits and the 20 task rows through the new gate. Ship only if ≥ 50% of decision-bearing commits fit; the two historical handoffs not caused by the file count (a seat's verdict; the design cap, since removed by D-314) still route the same way, and the wef1 page sample, refused on `files`, must be admitted — a V0 step replays that web-ecommerce-factory commit (the hub replay covers only `/opt/fabrik`) and records its new-source and contract results. The hub replay is also extended with the contract path test, which it does not yet model.
- **V1–V6 (graders, red-first):** a 6-file feature with 2 new source files is admitted; 3 new source files found at close → `done` refused until a full-review receipt is named; a commit touching `specs/services/x.yaml` declared `consumers=internal` → `done` refused until a full-review receipt is named; an undeclared committed path → close refused; 8 Behaviours → UPGRADE; elapsed > 2× appetite → `over_appetite` recorded and the UPGRADE line printed.
- **30-day success:** task runs ≥ 2× spec runs (today 20 vs 32), task median ≤ 120 min, UPGRADE ≤ 20%.
- **Kill (revert the specific admission, not the lane):** handoff > 35% over 20 runs, task median > 240 min, or > 2 post-merge fixes citing one task D-row.

## Decisions taken

- File count is not a lane test; the module tests are (D1). Reversible: a gate constant and a table row.
- The contract test is executable at close regardless of declaration (D1, judge 2); a close-time hit owes the full `/fabrik-review` receipt rather than the chain, because the work is already committed.
- The appetite breaker is a standing order plus a recorded verdict, not a cancel (D4) — stated divergence from Shape Up.
- Heavy surfaces, migrations included, enter the lane with the full review (D2) — supersedes row 1b's disposition.
- An undeclared committed path is refused at close, with an append-only design amendment as the remedy (D3.3) — supersedes D-290's "exactly two feedback fields" (adds `loc_added`, `over_appetite`, close-recorded `upgrade`) and the record-only stance of the `oversized_mini` docstring.
- At most 7 Behaviours per task (D3.1); independent slices are several task runs (D6).
- The Profile: small fold is moved to its own change (D5).
- The intake mail's "1 engineer-month" attribution to Google is wrong: the page has no such threshold (fetched 2026-10-02); the spec cites what the page says.

## Chosen approach

**B — the module test**, ranked first by all three judges of a blind panel (2026-10-02; approaches given alphabetically, no recommendation named). Reasons: it is the only one that changes the binding constraint (the file count in projects) while keeping an executable check — the close re-measures new files and contract paths against the actual commit — and it ships its own Cobra counter (D3.3). It fits three of the four motivating cases outright (the wef1 page sample, the llm-dispatch work, the one-file fix); the fourth (884 min of execution) was already in the chain and is routed OUT below.

## Rejected alternatives

- **A — appetite only** (drop file counting; admit on not-sync, not-oneway, no trade-off, appetite ≤ 240). Rejected by all three judges: appetite alone is self-report with no executable counter, and it drops the new-file signal that is 95% predictive on the replay.
- **C — raise the cap to 8.** Rejected: keeps sizing on the proxy the field evidence and the replay both discredit, adds no check, and moves the same refusal to a 9-file feature.
- **Raise the cap to 5** — same class as C.
- **Send any change splitting into ≥ 2 independently shippable commits to the chain** (Fable's draft, per the intake). Rejected: independent slices are cheaper as several task runs (D6); the trade-off test already catches slices that share an unsettled design.
- **A hard-cancel circuit breaker** (Shape Up's default). Rejected for the lane: cancelling mid-commit strands work; the standing order plus the kill criteria give the same signal without the loss (D4).
- **Folding spec-review into plan-review for every profile.** Not taken: a full-profile spec carries the decisions a plan inherits.
- **Sync paths into the lane with the full review** (the D2 analogue). Not taken: a sync path is a public contract for ~46 repos and today's right-now + full review already avoids the chain for it.
- **Keep recording undeclared paths (no refusal).** Not taken: with the file cap gone, the design note's path list is the only size record; the append-only amendment removes the deadlock that made refusal unsafe.
- **New-source test only, no appetite.** Not taken: a two-file change can still be a day of work; the appetite catches the size a file count cannot.

## Lifecycle

Adoption: the gate change ships with the merge; the governance sync carries the template rows to 47 repos; fabrik-lib and Volkan's port get the rule text by mail. A record opened before the merge carries no `gate: 2` stamp, and its close keeps the old behaviour (records undeclared paths, one `--commit` SHA — a two-commit run closes on its last commit as today); only stamped records get multi-commit closes, D1's close re-check and D3.3's refusal. Growth: the contract-prefix list grows when a new public surface appears (a new service-spec location, a new schema path) — a one-line constant change, triggered by any post-merge fix citing an undetected contract. Degradation: an unreadable sync filter keeps failing OPEN with a warning, as today; a stamped record with no recorded design cannot pass D3.3, so its close is refused until `--design` is recorded. Retirement: the kill criteria revert the admission rule alone; the lane itself stays.

## External dependencies

Fetched 2026-10-02 by native research seats; quotes verbatim from the primary pages.
- Google design docs — https://www.industrialempathy.com/posts/design-docs-at-google/ : *"If a doc basically says “This is how we are going to implement it” without going into trade-offs, alternatives, and explaining decision making (or if the solution is so obvious as to mean there were no trade-offs), then it would probably have been a better idea to write the actual program right away."* No size or file-count threshold on the page.
- Rust RFCs — https://github.com/rust-lang/rfcs/blob/master/README.md : *"You need to follow this process if you intend to make "substantial" changes"*; exempt: *"Additions only likely to be _noticed by_ other developers-of-rust, invisible to users-of-rust."*
- Amazon 2015 shareholder letter — https://www.sec.gov/Archives/edgar/data/1018724/000119312516530910/d168744dex991.htm : *"Some decisions are consequential and irreversible or nearly irreversible – one-way doors – and these decisions must be made methodically, carefully, slowly"* (found by brave search).
- Shape Up — https://basecamp.com/shapeup/4.5-appendix-06 : *"Appetite: The amount of time we want to spend on a project, as opposed to an estimate."* · *"Circuit breaker: A risk management technique: Cancel projects that don’t ship in one cycle by default instead of extending them by default."*
- Counter-evidence, reported: Mantid sizes partly by file count, as one heuristic of seven (https://developer.mantidproject.org/DesignDocumentGuides.html); a GitHub workflow gates on > 100 lines of core code (github/gh-aw); Chromium counts CLs for mechanical sweeps. None sizes design work by file count alone.

## fabrik-lib verdict

None — hub tooling; no fabrik-lib module covers lane admission (BUILD inside `command_run.py`, not a candidate: hub-specific).

## Shape/infra implications

None — no service, no `shape:` change; hub scripts and command text only.

## Constraints

Packs matched by the surface: `core/10-python.md`, `core/40-documentation.md` (select_rules, 2026-10-02). Governance-sync paths take the full `/fabrik-review` (CLAUDE.md § 1a, D-289); the template's UNIVERSAL anchors must survive the row edit.

## Documentation landing sites

The lane spec gets a SUPERSEDED-IN-PART banner pointing here; `docs/reference/command-run-protocol.md` (the `start`/`done` flags); `commands/_sources/fabrik-task.md` (the Behaviours list, multi-commit close); both CLAUDE.md lane tables; a D-row superseding D-293's row-5 text and D-315; CHANGELOG.

## Open unknowns

- fabrik-lib's contract surface: its modules are top-level directories vendored by ~46 repos, so path rules cannot say which change alters a public interface — resolution: a mail to fabrik-lib-sentinel with this spec; its ruling (a public-API file list, or `consumers=external` for every module change) lands in its own CLAUDE.md.
- The contract-prefix list's completeness for non-Python projects (e.g. a Node `openapi` path elsewhere) — resolution: V0 replay over three project repos' last 100 commits before rollout.
- Volkan's `/task` port has no `command_run.py`; whether its self-graded gate should mirror D1 — resolution: a mail to Volkan's channel with the rule text; his port adopts or declines.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"fabrik-task must cover more work. this is very limited"* | IN | D1, D2 |
| I2 | *"for a feature addition fabrik-task should be able to be used"* | IN | Goal, D1, D3 |
| I3 | *"spec/specreview/plan/planreview/execute/review cycle must be bigger modules"* | IN (partial) | D1 (chain only for modules); the one-loop fold is routed with I8; enlarging the chain's stages for full-profile work is OUT-OF-SCOPE → STRATEGIC_BACKLOG row "chain stage consolidation for full-profile specs" |
| I4 | *"i need one major change now too"* — this proposal | IN | this spec |
| I5 | mail item 1: module test (contract/oneway/tradeoffs/>2 new files/appetite) | IN | D1 |
| I6 | mail item 2: heavy surfaces in the lane with the full review; sync + drop/alter migrations out | IN | D2, D1 |
| I7 | mail item 3: Behaviours ≤ 7, multi-commit, review by surface, elapsed/appetite line | IN | D3, D4, D2 |
| I8 | mail item 4: fold spec-review into plan-review under Profile: small | OUT-OF-SCOPE | the profile is set after the spec (D5); its own change → STRATEGIC_BACKLOG row "Profile: small — one design-review loop" |
| I9 | mail item 5: independent slices → several task runs | IN | D6 |
| I10 | mail COBRA counters (paths in design.md; appetite > 480 shows the chain; loc_added) | IN (changed) | D3.3, D3.4; appetite > 240 already routes to the chain, so the 480 display is not needed |
| I11 | mail VALIDATION/KILL | IN | § Validation |
| I12 | an execution-time breaker inside the chain (the 884-min case) — judge 3 | OUT-OF-SCOPE | STRATEGIC_BACKLOG row "appetite/breaker for /fabrik-execute-plan" |
| I13 | D-485 `where:` field — the lane's close inherits it | IN | carried; no change here |

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | spec md5 (start → end) |
|---|---|---|---|---|
| Pass 1 | opus×1 (delta, decisions, approach, rejected) · sonnet×1 (personas, grounding, validation, lifecycle, intake) · sonnet×1 fabrik-researcher (external quotes) — intake · personas · facts · approach · completeness · constraints | found: 17, new: 17, confirmed: 17, fixed: 17, unexecuted: 0, edits: 16 | method: citation — full partitioned pass; every candidate executed by the orchestrator (fabrik-lib `libs/` count 0; `.sql` in `_TASK_DOC_SUFFIXES` :3232; trade-intelligence `web/db/migrations` 133/200; `-M -C` :3363; second `--design` ignored :3952-3958; :3616); URL status probes 5/5 = 200 | 492403733c56 → 01e4ee404d90 |
| Pass 2 | opus×1, sonnet×1 (round-1 owners, own slices + one hop) | found: 8, new: 8, confirmed: 7, fixed: 7, unexecuted: 0, edits: 9 | method: re-derivation — fix hunks re-read whole; old candidates 17/17 re-checked; replay re-run (12 gained, 1 lost, net +11); own-fix: 7 of 7 (round 1 hunks) | 01e4ee404d90 → 446f2851967a |
| Pass 3 | opus×1, sonnet×1 (round-1 owners) | found: 6, new: 6, confirmed: 5, fixed: 5, unexecuted: 0, edits: 4 | method: re-derivation — round-2 hunks; own-fix: 5 of 5; scope-growth stop fired (two of three rounds ≥ two-thirds own-fix) → close-time paragraph rewritten in one batch; class rewrite — D1 close-time paragraph | 446f2851967a → 1ba5d3d57be1 |
| Pass 4 | opus×1, sonnet×1 (round-1 owners, the fixed set only) | found: 3, new: 3, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the fixed set re-verified (R3-1..R3-5 now false, each executed: `check_review_coverage.py` on a real receipt rc 0; `review_receipt.py:79-82` range tip); replay numbers, arithmetic and anchors :2809 :3616 :3232 :3363 re-derived true; 3 own-fix residuals RECORDED to the work store (receipt `**Command:**` line is hard-coded at `review_receipt.py:138`; `handoff --review` missing from Contract deltas; the receipt's own commit stays out of `--commit`) | 1ba5d3d57be1 → 1ba5d3d57be1 |
