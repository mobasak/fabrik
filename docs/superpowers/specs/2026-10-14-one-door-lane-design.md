# One door — the lane decision as one rule and one executed verb

Status: CONVERGED
Size: small (≈350 lines, 5 files)
Profile: delta — on `docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md` (D-492, D-507; D9 and the lane table superseded in part). Every Intake item maps to code or text that exists today (the lane gate, the three contracts, the three command sources, the hooks, the report).
Owner: kaizen (text) · infra (code) · Intake: operator conversation 2026-10-14 (kaizen window) · D-858, D-859 · W-1ad56485
Decided by: the Opus + Fable design panel (D-558/D-613, operator ruling "I don't want to be involved") and the Phase-3 judge panel (three Sonnet seats), both unanimous for approach B.

## Personas

- **PRIMARY — the operator**, in their own words: *"i dont want to be get involved in now, task, spec selection process. agents should decide it by selecting most suitable and best approach. lean, fast, error free (less errors, best practise)."* Minimal loop, steps counted (the STEP BUDGET downstream contracts meet or bump): (1) the operator writes a request; (2) the agent runs the lane verb; (3) the verb prints one verdict and the agent states it in one line; (4) the lane's own work runs (now / task / spec); (5) its review runs; (6) the change is committed and merged. **Six steps; the operator touches only step 1.** A `now:` / `task:` / `spec:` prefix in the request is available, never required.
- **Any repo agent** (the four hub agents; the ~46 synced projects' agents; fabrik-lib's agents) — runs the verb before any edit and takes what it prints.
- **`command_run.py` (automated, fleet-synced)** — holds the verb and the three start refusals; records the verdict.
- **`task_lane.py` (automated, fleet-synced, PURE)** — holds the measurable tests the verb executes and the trip list the rule text is pinned to.
- **The Stop hook `final_gate_stop.py` (automated, fleet-synced)** — names a missing verdict on a record-less edit.
- **The prompt router `skill_router.py` (automated, fleet-synced)** — says "run the lane check first", never a stage.
- **`command_feedback_report.py` (automated)** — the weekly per-agent report of verdict against outcome; kaizen reads it.
- **The three command sources** `/fabrik-spec`, `/fabrik-task`, `/fabrik-review-scoped` (automated) — point at the verb; `/fabrik-spec` Phase 0 shrinks to "verdict present, or refuse".
- **The merge owner** (infra) — merges the hub change; the post-merge sync carries the template and the scripts.
- **fabrik-lib's agents** — apply the rule text to their hand-kept CLAUDE.md on kaizen's mail.

## Goal

Every agent on the box routes a request into now, `/fabrik-task` or `/fabrik-spec` alone, from one rule and one executed verb, so that a request with no nameable irreversibility and no research-settled trade-off cannot open a spec, a pure fix is not dressed in design fields, and the operator is never asked which door.

## Why this exists

Measured in the box ledgers since lane v2 shipped (2026-10-02; `~/.claude/state/command-feedback.jsonl`, `lane-refusals.jsonl`, `seeds/`): 315 `/fabrik-task` closes, 77 `/fabrik-spec` closes, 9 lane refusals (4 trade-off, 3 contract, 1 one-way, 1 appetite), 16 task→spec upgrades, 0 DOWNGRADE seeds. At most 25 of the 77 specs could have met any gate; at least 52 never did. 21 of the 77 spec closes name the lane or `Size: small` in their own feedback. The operator's words: *"agents tend to choose spec flow even for small requests of mine"*; *"the existing rules defined for this selection mechanically … are pathetic."*

Root cause: three doors, one gate. The agent reads a six-row table plus four paragraphs, answers judgment questions about its own request, and only the `/fabrik-task` answer is checked by code. `/fabrik-spec start` checks nothing; `/fabrik-review-scoped start` checks nothing; the prompt router pushes toward spec and has no task trigger. The literature names the failure: *"As organizations get larger, there seems to be a tendency to use the heavy-weight Type 1 decision-making process on most decisions, including many Type 2 decisions"* (Bezos, 2015 letter); *"Ambiguity on which work needed an RFC. Every team had autonomy to decide … many different interpretations"* (Uber, via Pragmatic Engineer). The approach resolves exactly that: one rule routed by the cost of a wrong first attempt, one verb that executes what is measurable and records what is not, refusals at all three doors, and a report that shows each agent's verdicts against outcomes.

## What exists today (grounded)

1. **The lane gate** — `scripts/task_lane.py:313` `admit`; the contract test `:167` `contract_hit`; `_APPETITE_MAX = 240` (`:72`); `_FULL_REVIEW_FILES = 5` (`:67`); `record_refusal` (`:400`). Called from `scripts/command_run.py:4143` `_task_size_gate(command=)` — for every `--command fabrik-task` start and, since D-862 (f0a6d1326, after this spec's first draft), for a `--command fabrik-spec` start that passes `--file`/`--declare` (`:5368-5376`, opt-in); a flagless spec start is noted as ungated (`:5402`), and every other command's start refuses the lane flags (`:5381`, `:5395` — "belong to --command fabrik-task"). Executed: `grep -n` at master f0a6d1326.
2. **The spec door** — `commands/_sources/fabrik-spec.md:23-58` Phase 0 DOWNGRADE check (D9 + D-858): applies the lane tests to the brief INSIDE the spec run, after `start`; the handoff join reads only an `LR-` id (`command_run.py:3985` `_DOWNGRADE_REASON`). No code refuses a FLAGLESS `/fabrik-spec start`; the flagged one (D-862) refuses a `lane` route without `--why` and ledgers the override as a `spec-start` row (`:4102-4107`, `:4122-4139`).
3. **The now door** — `.claude/hooks/final_gate_stop.py:1395` (`unreviewed-spontaneous`, `_unreviewed_spontaneous` `:1745`) blocks a record-less editing turn after the fact; `/fabrik-review-scoped start` takes no declaration.
4. **The router** — `.claude/hooks/skill_router.py:110` maps spec/design words to `/fabrik-spec`; `grep -c fabrik-task` = 0 (executed); `:25-32` records the rejection of a per-prompt model call for latency.
5. **The contracts** — `CLAUDE.md:75-92` (table, precedence, D-859 default paragraph `:88`, no-code `:90`, tripwire `:92`); `templates/governance/CLAUDE.md:66-83` (mirror, D-859 `:79`); `/opt/fabrik-lib/CLAUDE.md` ~379-394 (hand-kept; D-859 requested by mail 01M4XTZ9PZRMTJV4HJ5D49M60G). Graders: `tests/test_governance_template_split.py` (row mirror, prose mirror), `tests/test_spec_plan_lane_text.py`, `tests/test_command_run_lane_v2.py`, `tests/test_fabrik_task_source.py`.
6. **The report** — `scripts/command_feedback_report.py:1527` prints `adoption t/(t+standalone)` (task closes over task plus standalone scoped reviews), refusal and downgrade shares; it has no verdict-vs-outcome view.
7. **Precedents** — D-315 (a mechanism is recorded, never a refusal), D-507 (lane v2 everywhere), D-532/D-533 (Volkan's port narrowed row 5 to a BREAKING contract change a shipped client reads), D-858 (spec Phase 0 lane check), D-859 (the default paragraph).

## The delta

**R1 — The rule.** One text, byte-identical in `CLAUDE.md` § Orient step 0 and `templates/governance/CLAUDE.md`, requested verbatim for `/opt/fabrik-lib/CLAUDE.md`; it replaces the six-row table, the precedence paragraph, the D-859 paragraph, the no-code clause and the tripwire:

    LANE — decide before you draft; run the lane verb; say its verdict in one line; then act.

    Q1  Would a wrong first attempt need more than ONE revert in THIS repo to undo?
        Yes → /fabrik-spec.  That is: a published name, URL or contract a shipped client reads moves
        or breaks — another repo or person must change BY HAND (a synced path reverts through the
        sync and does not count); it will not finish in one session; data others stored changes
        shape or is destroyed, or anything else a revert would not undo; two approaches the build
        itself cannot rank (a trade-off the build settles is ordinary task work).
    Q2  Does the request leave a CHOICE a caller, operator or stored row will depend on — an
        interface, a flag, a shape, a new mechanism?
        Yes → /fabrik-task.  The decision goes in its six fields and its D-row; a new mechanism is
        recorded there, never a reason for spec.
    Q3  Otherwise — a fix (--fix) or a docs-only change — → now, then the review.  Q1 and the
        review line still apply to it: a docs-only change on a contract path is Q1, on a synced
        path it owes the full review.

    Review, every lane: a synced, hook, gate, vendored, auth, schema, migration or concurrency
    path, operator-named work (an explicit full-review ask or a named code or config change —
    naming alone never routes up a docs- or ledger-only diff, D-892), or more than 5 files, takes
    the full /fabrik-review; anything else the scoped one.
    Under doubt: task — a thing you can NAME that a revert would not undo is not doubt, it is Q1.
    A task that trips Q1 mid-build hands itself to /fabrik-spec.
    Your word wins: a request starting now: / task: / spec: is the verdict.

Row map from the superseded table: 1/1b → the review line; 2 and 6 → Q2; 3 and 4 → Q1; 4b → Q3; 5 → Q1 (contract, consumers, one session). The four clauses of Q1 are `admit`'s four `chain:` routes in order — `contract`, `appetite`, `oneway`, `tradeoffs` (`scripts/task_lane.py:365-381`) — two executed from the file list and the appetite, two named by the agent; rendered from one constant (`render_q1`, compared after whitespace normalisation — the contract hard-wraps the sentence) and pinned by a test that also counts the routes, so text and code cannot disagree.

**R2 — The verb.** `python3 scripts/command_run.py lane --ask "<the request, verbatim>" --file <path>… [--appetite <min>] [--fix] [--oneway "<what cannot be undone>"] [--tradeoff "<A> vs <B>"]`. It completes the declaration (`decision=yes` unless `--fix`, and `--fix` or a docs-only list never skips Q1 — a contract path or an over-appetite fix is still `spec`; `consumers=internal`, `heavy=no`, `mechanism=no` unless a `--declare k=v` says otherwise; `oneway`/`tradeoffs` from the two flags) and executes `admit`'s own tests in `task_lane.py` (a contract path — `specs/services/`, `openapi*`, `*.schema.json` — present or deleted, by its name; a declared `consumers=external`; appetite > 240; a docs-only file list → now; a sync, heavy, migration or more-than-5-files surface → the full review, never a trip), prints exactly ONE verdict with its reason, and appends a row to `~/.claude/state/lane-verdicts.jsonl` (request text, file list, flags, verdict, reason, session, repo, time, enforcement mode). Verdicts: `LANE: now — <reason> → <review owed>` · `LANE: task → <the /fabrik-task start line, ready to paste>` · `LANE: spec — tripped: <one reason>`. A spec verdict needs a measurable trip or a named `--oneway`/`--tradeoff`; with neither it prints task and says why. A request beginning `now:`, `task:` or `spec:` is that verdict, recorded as an operator ruling. The verdict is bound to its file list: a start whose `--file` set is not a subset of the verdict's is a mismatch.

**R3 — The doors.** `/fabrik-spec start`, `/fabrik-task start` and `/fabrik-review-scoped start` look up the newest verdict of this session whose lane matches and whose file list covers theirs (or take `--lane-verdict <id>` — a verdict from another window, named in the refusal text too); none → the refusal prints the verb to run. Only a TOP-LEVEL start is checked: a start nested in a running `/fabrik-task` or `/fabrik-execute-plan` record (`/fabrik-review-scoped` as the task's phase 4 or a plan's phase review) records `nested` and proceeds — any other running record does not exempt it — and a `/fabrik-task --from-downgrade <LR-id>` start is satisfied by that refusal row when the ledger holds it (the spec run's own verdict). A task that UPGRADES mid-build re-runs the verb with the trip it crossed before the spec start — the handoff text names it. `/fabrik-task start` keeps its own `admit` re-check unchanged. The Stop hook's `unreviewed-spontaneous` cause names the missing verdict: "run `command_run.py lane` first". The router's Tier-1 directive becomes "run the lane check first (`command_run.py lane`)" for every stage it matches today.

**R4 — Enforcement mode and rollout.** One dated constant `_LANE_ENFORCE = {"hub": "warn", "fleet": "dryrun", "since": "<the merge date>"}` (no `deny_after_days`: nothing reads it, the flip is a reviewed commit) in `task_lane.py`, read by the three refusals through `enforce_mode(is_hub, override)` (the hook names the verb and reads no mode — it imports nothing, `final_gate_stop.py:566-570`; the override is an env seam read in `command_run.py`, recorded on every door row as `mode_source`): `dryrun` records only; `warn` records and prints the refusal text but proceeds; `deny` refuses. Day one: hub `warn`, fleet `dryrun`. After seven days the report's fire rate is read (R5) and the constant flips to `deny` in one reviewed commit — or stays, with the reason in a D-row. The bar for that flip, a first setting the week's D-row re-sets with the measured numbers: top-level `missing` + `mismatch` door rows at or under 1 in 5 of the hub's top-level starts over the week's last three days (the verb is adopted; a higher share means `deny` would refuse real work). Kill rule: more than 1 in 5 JOINED `task` verdicts handing off to spec in a week reverts the doors to `warn` and re-opens the rule text; over-route alarm: more than 1 in 3 `spec` verdicts closing `Size: small` (either outcome) re-opens the rule text the same way.

**R5 — The counter (D-253).** Every close records `lane_verdict` and `lane_outcome` on the feedback row: a `now` whose own commits after the verdict (the record's `Agent-Name`, from the verdict's recorded HEAD) add a source file or exceed 5 counted files; a `task` that handed off; a `spec` whose Phase 5 wrote `Size: small` with no trip named (`small-no-trip`) or on a named `--oneway`/`--tradeoff` (`small-named`); an operator prefix. the existing `command_feedback_report.py --lane` report gains a `verdicts` section (no second flag) printing per agent and per repo: verdicts by lane, the `--fix` share, outcomes by class, the fire rate of each door outcome in each mode, overrides, operator-prefix rows split from agent overrides, the kill-rule ratio over task verdicts JOINED to a closed task (both numbers printed: `3/12 joined (of 15 verdicts)`), and the over-route ratio (`small-no-trip` + `small-named` over spec verdicts). The cheapest way to satisfy the gate is `--fix` on everything or a one-word `--oneway`; the counter is that both are recorded under the agent's name — `fix` share and `small-named` per agent — and read weekly.

**R6 — The command sources.** `/fabrik-spec` Phase 0's DOWNGRADE bullet shrinks to: "a `spec` verdict of this session is present (the start refused otherwise); a `--oneway`/`--tradeoff` reason it carries is the brief's § Why; a refusal row (`LR-`) is still read for the D9 handoff". `/fabrik-task` § SIZE opens with the verb's printed start line. `/fabrik-review-scoped`'s record opens from a `now` verdict. `agents-fabrik-core.md` "Front door" points at the rule.

## Contract deltas

None in `docs/data-contract.md` or `docs/ui-design.md`. The command-run protocol doc (`docs/reference/command-run-protocol.md`) gains the `lane` verb row, the `lane-verdicts.jsonl` file, the three refusals and the two feedback fields.

## Cost

Code: ~350 lines across 5 files — `scripts/command_run.py` (verb, three refusals, feedback fields), `scripts/task_lane.py` (the trip-list constant, `lane_verdict()` pure function, `_LANE_ENFORCE`), `.claude/hooks/final_gate_stop.py` (one cause text), `.claude/hooks/skill_router.py` (one directive text), `scripts/command_feedback_report.py` (the `--lane` report's `verdicts` section). Text: two contracts, three command sources, the protocol doc, the fabrik-lib mail. Tests: new graders in `tests/test_command_run_lane_v2.py`, `tests/test_governance_template_split.py` (rule text pinned to the constant), `tests/test_spec_plan_lane_text.py`. Run cost per request: one Python call, no model call.

## Validation

- Red-first graders: the verb's verdict for each trip and for the prefix; a start without a verdict refused in `deny`, printed in `warn`, silent in `dryrun`; the file-list binding; the feedback fields on close; the report's fire rate and kill ratio; the rule text in both contracts rendered from the same constant the verb reads (a changed constant reds the contract test).
- Replay: the hub's last 300 non-merge commits through `lane_verdict()` as `tests/test_lane_replay.py` already does for `classify_commit`; the lane distribution pinned (the 21-row tasks fixture carries no file lists, so it is not replayed).
- The parent spec's § Validation V7–V10 stay green (the `admit` path is unchanged).

## Decisions taken

- Approach B over A (text only) and C (a Haiku lane judge): design panel unanimous, judge panel unanimous. C rejected: anchors on nouns, a model call per edit (`skill_router.py:25-32` already rejected that latency), cannot block, conflicts with `task_lane.py`'s PURE/replay contract.
- Tie-break "under doubt, task", with a nameable irreversibility counted as Q1: both panels; Bezos's footnote (under-routing a one-way decision is the fatal error) is answered by requiring the irreversibility to be NAMED, which the verb records.
- Rollout: hub `warn` on day one, fleet `dryrun`, `deny` after a week's measured fire rate (judge panel 2:1; D-253; OPA's dryrun→warn→deny). The design panel's deny-at-once is recorded as the rejected alternative: the two files are the fleet's most load-bearing synced scripts and no fire-rate data exists.
- `Size: small`: 5 code files, ≈350 lines; `/fabrik-plan-after-chat` plans it as `Profile: small`, `/fabrik-plan-review` holds the approval gate with its Opus + Fable critiques; the plan phase touching `final_gate_stop.py` owes the full `/fabrik-review` (a hook path).

## Chosen approach

B — the rule plus one door (R1–R6). Grounded live, every source fetched 2026-10-14 (WebSearch, Brave, exa and firecrawl across three research seats and the lead):

- Route by reversibility — *"Many decisions are reversible, two-way doors. Those decisions can use a light-weight process."* Bezos, 2016 shareholder letter: https://www.sec.gov/Archives/edgar/data/1018724/000119312517120198/d373368dex991.htm — and the 2015 letter on the failure mode: https://www.sec.gov/Archives/edgar/data/1018724/000119312516530910/d168744dex991.htm
- The spec test is the presence of a trade-off — *"If a doc basically says 'This is how we are going to implement it' without going into trade-offs … it would probably have been a better idea to write the actual program right away."* Ubl, Design Docs at Google: https://www.industrialempathy.com/posts/design-docs-at-google/
- Significance — *"expensive to reverse, crosses team boundaries, or constrains future decisions"*: https://www.catio.tech/blog/architecture-decision-record — and *"difficult to reverse"*: https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record — with Nygard's five categories: https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- The gate re-tiers, never the author — *"may be closed with a polite request to submit an RFC first"*: https://rust-lang.github.io/rfcs/ — and Uber's central tiering after self-classification failed at scale: https://newsletter.pragmaticengineer.com/p/rfcs-and-design-docs
- Staged enforcement — `enforcementAction` dryrun / warn / deny: https://open-policy-agent.github.io/gatekeeper/website/docs/violations/
- The paved road stays the easiest path — Spotify golden paths: https://engineering.atspotify.com/2020/08/how-we-use-golden-paths-to-solve-fragmentation-in-our-software-ecosystem — and the golden-cage failure when it does not: https://platformengineering.org/blog/golden-cage-syndrome-why-internal-developer-platforms-fail

Full ledger, every returned fact dispositioned: `docs/reference/research/2026-10-14-one-door-lane-ledger.md`.

## Rejected alternatives

- **A — rule text only.** Repeats today's mechanism; the table already said "under doubt task" (D-859) and the spec door still has no gate. Both panels.
- **C — an independent model judge.** See Decisions taken.
- **Size or file-count thresholds as the lane test.** A one-line change to a published contract is spec work; a 20-file rename is now work (D-507 removed the file count for the same reason).
- **Always task, upgrade on trip.** A pure fix carries design fields it does not need; the research gate is reached late.
- **Operator prefix as the only mechanism.** Moves every request's routing to the operator, who ruled themselves out of the loop.
- **"Under doubt, spec."** Repeats the measured over-routing; the Bezos asymmetry is answered by the NAMED-irreversibility clause instead.
- **Deny at once on all doors.** Rejected for the fleet-synced blast radius with no fire-rate data; kept as the week-two step.
- **A fourth "lightweight RFC" tier** (Lubow, DesignDoc blogs): `/fabrik-task` with its two-seat critique IS that tier; a fourth lane adds a boundary without adding a check.

## Lifecycle

- **Adoption:** hub first (`warn`), then the post-merge sync carries the scripts, hooks and template to the fleet in `dryrun`; fabrik-lib applies the text by mail. The first week's report is the acceptance test.
- **Growth:** the verdict ledger grows one row per request; `command_feedback_report.py` reads it like the feedback ledger (same rotation rule); a new measurable trip is one constant row, which re-renders the rule text through the pinned test.
- **Degradation:** an unreadable ledger reads as no verdict → in `dryrun`/`warn` nothing blocks; in `deny` the refusal prints the verb and the agent re-runs it (idempotent). A missing constant falls back to `dryrun`.
- **Retirement or supersession:** flipping `_LANE_ENFORCE` to `dryrun` disables every refusal in one commit; the rule text is restored from git; the kill rule names the trigger.

## External dependencies

None — no vendor API, library or paid service. The approach grounding above cites eleven live sources, each fetched this session and filed in the research ledger.

## fabrik-lib verdict

| Capability | Verdict | Module · why |
|---|---|---|
| routing a request by measurable tests | BUILD (hub-local) | no module covers it; `decision-gate` is a typed-decision MODEL lane (D-527/D-550), rejected here (approach C); not a lib candidate — it reads hub-only state and the fleet's own contract |

## Shape/infra implications

No scaffold type, no `shape:` flag, no service. A new state file `~/.claude/state/lane-verdicts.jsonl` beside the existing ledgers; the hub's `tests/conftest.py` pin for `~/.claude/state` covers it.

## Constraints Digest

| Quote | Source |
|---|---|
| Edit existing docs instead of creating new ones. | `.windsurf/rules/core/40-documentation.md:186` |
| Reference: `docs/reference/**/*.md` | `.windsurf/rules/core/40-documentation.md:192` |
| One H1 per document | `.windsurf/rules/core/40-documentation.md:241` |
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| Use type hints for all function signatures | `.windsurf/rules/core/10-python.md:160` |

Selections against the digest: the spec lives at an allowlisted path (row 2's sibling allowlist, plans and specs); the protocol doc is extended, not duplicated (row 1); every grader is red-first (row 4); the verb and `lane_verdict()` are typed (row 5). Nothing else in this delta is constrained by a matched pack.

## Documentation landing sites

`docs/reference/command-run-protocol.md` (the verb, the ledger, the refusals, the feedback fields); `CLAUDE.md` and `templates/governance/CLAUDE.md` (the rule); `docs/DECISIONS.md` (this decision and the rollout flip); `CHANGELOG.md`; `INDEX.md` (this spec, the research ledger); `docs/reference/research/2026-10-14-one-door-lane-ledger.md`; `/opt/fabrik-lib/CLAUDE.md` by mail.

## Constraints

Fleet-synced scripts and hooks (`command_run.py`, `task_lane.py`, `.claude/hooks/`): one behaviour for 46 repos, backward-compatible under `dryrun`; `task_lane.py` stays PURE and replay-graded; no model call on the request path; no new daemon or store outside `~/.claude/state`; the `/fabrik-task` `admit` path unchanged; `check_governance_drift` anchors untouched.

## Open unknowns

- **Resolved:** the approach (two panels); the tie-break; `Size: small`; rollout order.
- **Open, with its step:** the exact wording of the `consumers=external` test the verb can execute (a declared file in the governance-sync manifest vs a `specs/services/` path) — settled at plan time by reading `fabrik_synced_manifest.py` and `task_lane.contract_hit`, and pinned in the replay. The fire rate under `dryrun` — measured in week one; the `deny` flip is its own D-row.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"spec flow is long and time consuming but good, task flow is for combined path for not too complex implementations but agents tend to choose spec flow even for small requests of mine"* | IN | Why this exists |
| I2 | *"analyze and suggest the most efficient approach"* | IN | Chosen approach, Decisions taken |
| I3 | *"if fabrik-task used, as like fabrik-execute finished, there must be fabrik-review or fabrik-scoped-review automatically right?"* | IN | What exists today 5 (phase-4 review unchanged); R1 review line |
| I4 | *"are you 100% sure about this root cause and solution now?"* | IN | Why this exists (measured), What exists today |
| I5 | *"make edit 1 via /fabrik-command-improve fabrik-spec and mail item 2 to infra"* | IN | done as D-858 and mail 01M4XQN131A897DAFH628FJFKJ, which R2/R3 supersede |
| I6 | *"is it enough to make this change in fabrik-spec? dont we need to do any changes in fabrik-task, and 3 different claude.md files ?"* | IN | R1 (three contracts), R6 (three sources) |
| I7 | *"they must be flawless, crystal clear, lean, effective."* | IN | Goal, R1 |
| I8 | *"i havent see you using brainstorming skill and also searching online for that."* | IN | research ledger; Chosen approach citations |
| I9 | *"i dont want to be get involved in now, task, spec selection process. agents should decide it by selecting most suitable and best approach. lean, fast, error free (less errors, best practise)"* | IN | Personas (primary), Goal, R2 (no operator gate) |
| I10 | *"where is the rules defined for this selection mechanically?"* | IN | What exists today |
| I11 | *"you know the existing rules defined for this selection mechanically and they are pathetic."* | IN | Why this exists |
| I12 | *"consulting them is good approach."* | IN | Decisions taken (two panels) |
| I13 | fabrik-lib's hand-kept copy of the lane table | IN | R1 (by mail), Lifecycle |

Intake: 13 items — 13 IN, 0 OUT-OF-SCOPE, 0 ASK.
