---
description: One small change, one decision, one commit — the lane between a right-now fix and the spec chain. Six phases on ONE run record: SIZE (the start IS the gate), MEASURE, DESIGN, BUILD, REVIEW, CLOSE — the D-row is the durable artifact. TRIGGER — EN: "one small change with one decision", "fix + decide", "small change, one call to make"; TR: "küçük bir değişiklik, tek karar", "düzelt ve karar ver". SKIP — /fabrik-spec's own triggers, and what the SIZE gate refuses: a ONE-WAY decision, real trade-offs, no decision at all; at lane v2 also a contract path, consumers=external or an appetite over 240 min; at lane v1 also more than 3 files or a sync/heavy surface — each names its own lane (a new mechanism is recorded, never refused — D-315). Stage: utility.
argument-hint: "[the ask in one line — sized against the SMALLEST change that discharges it, before drafting]"
---

**One small change, one decision, one commit.** This command SEQUENCES existing machinery and RESTATES none of it: run record, FIX DIRECTIVE, `/fabrik-review-scoped`, close-out feedback, decision-ledger rule keep their own text.

New here: the SIZE gate (phase 0), the DESIGN step (phase 2), phase 5's re-measure of its own commit, and the UPGRADE ratchet.

Feature splitting into independently shippable slices is several runs, never one bundling them (D6).

Two lane versions share this text (`.fabrik/lane.json`; `start` prints which): lane v1 (repo pinning `{"version": 1}`) is old file-count gate (`command-run-protocol.md:52`'s `start` row).

Lane v2 replaces file count with module tests, adding every *(v2)*-tagged mechanism below: `consumers=`, `--appetite`/`--why`/`--from-downgrade`, `--design-amend`, undeclared-path REFUSAL, the space-separated multi-commit close, `--review`, and the Behaviours UPGRADE's four close-raised tokens.

{{include:run-record}}
{{include:orient}}

⚠️ Neither generic line above is this lane's: `command_run.py` REFUSES a `fabrik-task` `start` without `--file`/`--declare` and a `done` without `--commit`; paste SIZE line and phase 5's close.

`handoff` is record's third sanctioned terminal (`AGENT_CLOSED_STATES`): UPGRADE uses it.

`<durable>` is `SCRATCH:` path `start` prints (under the session's own checkout's `.tmp/runs/`, which is `<main checkout>/.tmp/runs/` in the main checkout and inside the worktree itself in a worktree session, surviving WSL `/tmp` wipe but not a worktree's removal), never `RUN-SCRATCH:`: one spelling, or phase 5's `cat` reads path phase 2 never wrote.

Linked-worktree session, whose Write tool refuses a main-checkout path, changes each file as a copy in its scratchpad (`cp` it from that path first when it exists) and `cp`s the whole copy back after every change, which keeps any content byte for byte; with no `SCRATCH:` line, it is `<scratchpad>/fabrik-task/<started_at>` (in /tmp).

## SIZE — phase 0 is the `start` itself

Apply lane table (`CLAUDE.md` § Orient step 0) to smallest change that discharges the ask, before drafting, then open record:

```bash
python3 scripts/command_run.py start --command fabrik-task --phases 5 \
  --terminal "<the one-line condition that ends this run>" \
  --surface "<the subject, one phrase>" \
  --file "<path 1>" --file "<path 2>" \
  --declare decision=yes,heavy=no,mechanism=no,oneway=no,tradeoffs=no,consumers=internal
```

*(v2)* `consumers=external` when another repo reads it; v1 ignores key.

`heavy=yes` includes operator-named work (lane row 1b), declared here, not found at phase 4.

`--file` is repeatable, ONE quoted repo path each.

Path that does not exist yet is accepted on purpose: declare grader you are about to write, `git check-ignore -v` each new file path and `git add` it just before phase 5's pathspec commit, which refuses an unstaged one (an ignored one stays out without `-f`); `ls` and grep every other path for the rule first, since typo reads as that grader; golden or snapshot that pins output is declared too.

Declare CODE surface ONLY: the close excludes the Doc Sync Matrix destinations, the ledger files and `docs/CAPABILITIES.md`, so declaring `CHANGELOG.md` burns a slot and can refuse the start on a sibling's WIP.

Tool prints either CORRECTIONS, each naming itself (DIRTY declared path may be sibling's WIP; message author, never stage it), or a LANE verdict naming where the work belongs; read every line: flag gaps print together, path checks stop at first.

⚠️ `sync lane test SKIPPED` on stderr means hub filter was unreadable — that test did NOT run.

A refusal is the answer, not an obstacle: take the named lane, no record was opened; on success it prints `RECORD: <started_at>` and `SCRATCH: <path>`, second being `<durable>`.

⚠️ **COBRA (D-253).** Cheapest way to satisfy this gate without producing outcome is to UNDER-DECLARE here and touch more at phase 3; counter is phase 5's re-measure of this run's own commit (all twelve cobras and their counters are § Constraints C3 of `/opt/fabrik/docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md`).

## Phase 1 — MEASURE

FIX DIRECTIVE step 1 whole: failure reported with command is replayed by that command, never a reconstruction, and a work item's cited `path:line` is grepped here, in the cited file, for the symbol it names, and a failure or error path it claims there is replayed on a copy carrying the state it needs (a grep hit can sit in dead code).

Miss, or replay on copy carrying that state not failing as claimed, is finding PROBLEM states, never the item's wording, and a replay whose copy cannot carry that state is recorded unverified, never as refuted (MIRROR greps every name the design uses again).

Fix item proposes and prior slice's stated reason the design builds on are replayed the same way, on a copy, before design adopts either; replay overturning either is stated in PROBLEM.

Unreachable tool's server source, where one exists, is read before claim is recorded unverified, and read never upgrades it.

Before phase 2 and any edit, each command and its output goes to `<durable>/measure.md`, beside phase 2's `design.md`, never in it (a pasted line opening with a field word or a `#` moves the declared paths): the tests that import, grade or run the declared files (grep the tests for each file's name and every mode or flag the change extends, since a test that runs a script by subprocess never imports it), that slice and never the whole suite (a red now is pre-existing).

`git fetch`, declared paths diffed against remote branch work merges into (`origin/master` in hub; elsewhere name ref chosen, or say no remote).

Prior record grepped: `docs/DECISIONS.md`, files' docstrings (and copied script's), `/opt/fabrik-mail/<repo>/archive`, work store where the repo keeps one, fragment or pack rule lives in, each searched by item's id too, plans and specs included.

Population change writes or thresholds measured (readers are MIRROR's): every writer, every occurrence of the shape it admits, every host it runs on, every config and env value changed format can sit in (grep them for its shape, `${`), the transport handing a new env var to the process (compose `environment:`, `env_file`, build arg, another launcher) read on started process (`docker compose run --rm <svc> env`, its keys recorded, never its values), and the n behind any rate, bound or zero the design will claim (a count is no fail direction: before a no-change verdict rests on one, the inputs the grammar admits and the corpus lacks are constructed and run).

Each external contract probed live once, list read whole, never a sample.

Each by EXECUTING real path on real data (producer's code, tool's run output per mode, design's own classifier, writer of each state value it trusts or ranks on), never a source read or a proxy: the tests that drive it by subprocess, the completion gate's own command, a surfaced outcome run twice and traced to the line the operator reads, a recipe's real target layout, the reported incident replayed on a copy one step past its symptom (what the reporter did next), a tool that scopes by a commit or diff range run where the branch's merge-base is its merge target's tip and where the target has moved past it, each spelling of a parsed input that the commands and docs feeding it prescribe, a mechanism copied from another script run read-only against the live state of each host it will run on (a side-effecting step on a copy), each callee a fail-open branch wraps and how it fails, whether a production path reaches the text, what a concurrent reader sees mid-write, a before/after hash of every file it writes, the codec a change touches run on non-UTF-8 bytes, NUL and that codec's own escape, an independent parser for a parsed format (every probe run under an interpreter shown to import its libraries and each extra it enables: a system `python3` may lack one), its operator-facing strings in every worker it feeds, a count repo-wide (`.venv`/`.claude` excluded) and per artifact class, whose commits a gate's new scope holds, and the whole output, not one field, with each hook output it grows sized against Claude Code's 10,000-character cap (https://code.claude.com/docs/en/hooks).

Grader design relies on is shown red on a deliberately broken input, since pass proves nothing until it can fail.

Then `python scripts/select_rules.py --changed <the declared paths>` — the path-scoped form — and READ packs it prints.

## Phase 2 — DESIGN, where it will be minted

Write six fields — **PROBLEM · APPROACH · DECISION (reversible?) · MIRROR · OUT · TERMINAL** — to `<durable>/design.md`.

Mechanism copied from another script carries, as Behaviours tested here (several may share one), failure directions its tests and D-rows settled.

Before such copy, rule another component already applies is tried as read of its output (stdout, a record, an exported function); when copy stays, DECISION says why read cannot serve.

Each input design branches on is tabulated whole in `design.md` table, outside Behaviours list: every value state it reads can hold, unit another tool's rule is evaluated per (window, agent, repo), every path through guard (forced refresh after write as well as periodic one).

Parser it adds takes strict grammar admitting every spelling MEASURE recorded and failing closed on rest.

Beside each input table records its live row count, values those rows hold and duplicates of any key design cuts rows by, from executed read of those rows, never assumed.

Marker-block or append-only file the change writes is tabled absent, begin without end, end without begin, nested and duplicate.

So is each tag parser it adds or extends reads, plus that tag quoted inside its own content.

Before critique seats are stamped, read plan locks (no CLI does: each `*.json` in `.fabrik/plan-locks/` with `status: active`): declared path or one backticked in APPROACH/MIRROR inside another lock's `owned_paths` is STOP, and so is ACTIVE lock whose `owned_paths` is empty or absent (it matches nothing and passes everything), so a locked path stops the run before a seat is spent.

{{include:design-critique}}

Before seats go out: re-read `design.md` against working tree; DECISION names its evidence and whether independent of change; shipped config is executed; borrowed fixtures are listed with what each stubs; existing suites run against throwaway scratch build of new refusal (not phase 3).

This lane's brief has each seat EXECUTE: replay reported incident and real corpus through design; run each matcher, semantics or shell claim against real tool under live guard, new parser on input outside its grammar; sweep sibling write paths and tests pinning moved value; name each new guard's fail direction and any second approach build cannot settle; run mechanism design copies read-only against the live state of each host it will run on (a side-effecting step on a copy); execute one claim about every external dependency (both seats are `fabrik-reviewer`, with no web tool: lead fetches provider-docs fact into brief).

It pins tree (commit or `git archive` copy) and any live state file design reads, names unmerged branch owning mirrored file, bars live-provider credentials (no `.env` loaded, no provider client built) and asks for small outputs.

Wait for both in-turn: with stamped seats out, Stop hook's run-record block stands down and will not hold you.

Concern is ACCEPTED only after the tests are grepped for every line it touches; optional one adding behaviour only when provable inside the declared files, else filed to its owner; later executed review finding may override it, recorded in D-row with the drift noted.

Second approach build cannot settle (equivalent implementation is not one), its seat's claim executed and holding, is § UPGRADE crossing `tradeoffs`, taken here before `--design`, never folded in as ACCEPTED.

Before this call: re-read `design.md`, and `--terminal` against its TERMINAL as MEASURE and critiques left it (change rides as `--terminal-amend`); lock check again, on every path (critique may add one, and a lock may be taken while the seats ran); each Behaviour names its test; every touched path is bare in backticks under `APPROACH:`/`MIRROR:`; `--design` lands ONCE; record them:

```bash
python3 scripts/command_run.py step --phase 2 --title "design: <that path>" \
  --design <durable>/design.md
```

If MEASURE or critiques changed what ends run, restate it with `--terminal-amend "<one line>"` on that `--design` call or any step before it — refused once the design is recorded, so no run moves its goal to fit the result; `terminal_amends` keeps old one.

There is no DECISION amend: design is recorded after critiques fold.

`--design` stores that file's TEXT whole (no cap — D-314), so the design outlives the scratch.

A refusal discards the `step`: fix the file and re-run, or the record stays at phase 1. A second `--design` is ignored, with only a NOTE.

Add `## Behaviours` list, each naming its test, at most 7 (8th is `behaviours` UPGRADE, *(v2)*).

Name every file build will touch, Behaviours' tests, deletions and rename's both paths included, under line-start UPPERCASE `APPROACH:`/`MIRROR:` labels, before any line opening with field word or `#` (fenced or not), one bare repo-relative path per backtick pair (`a.py::f`, `a.py:120` and `a.py, b.py` match nothing; `.md` under `docs/development/reviews/` but `archived/` is exempt): *(v2)* committed path missing from both REFUSES `done` at close (v1 measures `--file` instead and only RECORDS); the remedy is `step --phase <the current phase> --design-amend <path>` *(v2)*, append-only — it never overwrites a recorded field — and counted on close as `design_amends`.

Amend runs while `fabrik-task` record is top one, never under a nested run.

MIRROR is mandatory (`CLAUDE.md` § Behavior) and names every reader of what changes — callers, each branch of changed function, every resolver of same identity, consumers of moved or deleted file, other surfaces stating changed claim, gates that grade it — each found by executed search, with shape it now fails on and its cost measured, never estimated.

Search is whole tracked tree (tests, their pinned strings and hardcoded values, `commands/`, UI, docs), every other `/opt` main checkout's tests and CI files citing changed path, and every vendored copy outside it (`find /opt` by the file's name, `.claude/worktrees/` counted apart) under every spelling of identifier and its rule's key verbs: literal path beside any constant, every party text reaches, every reader of changed record shape or stdout (grep its tests for `== {` and `len(`), every Python reader of a name by an `ast.walk` census beside the grep, never `tree.body` alone (a function-local or `try:` import sits below it; a string-named import, `getattr` or subprocess argv is no import node, so the grep finds it), the hub scripts the text tells a project to run, the file handing a new env var to the process and the spec, the parser a read config belongs to, whether a normalised form is what readers receive, the form a ported validator's source validates, the first-or-every rule for a repeating field, the paths guarded code opens and the env each reads, and for a registration or allowlist the checks each bucket runs; sibling write paths included.

Each new guard, veto or fallback names its fail direction: which error is dangerous, answer versus outage.

Every function, anchor or subject design names is grepped to exist, and each guard claim relies on is quoted.

Reader build leaves untouched is named without backticks: every backticked MIRROR path counts as declared at *(v2)* close.

Fields are D-row's draft: APPROACH+DECISION+MIRROR → *what*, PROBLEM → *why*, declared files → *where*; OUT and TERMINAL stay in record.

⚠️ literal `|` is written `&#124;`: backslash escape makes `check_decisions_unique.py` read 7-cell row.

## Phase 3 — BUILD

Re-run phase 2's plan-lock check first: `--design-amend` path or lock taken since is same STOP.

Change and its grader, red-first per FIX DIRECTIVE 4 against recorded design (test drafted before critiques folded is rewritten, never made green); a shared-append file goes through § EXIT's private-index recipe, never the working file.

One commit carries it at v1; *(v2)* several may, SPACE-separated — `done --commit shaA shaB …` measures each in order; sync-path run (D7) commits ONCE, after phase 4, in main checkout (`done` refuses more outside a worktree; `blocked`/`handoff` only note it).

At v1 that one commit also carries phase 5's ledgers, so nothing is committed before phase 5; each grader names its input domain and borrowed fixtures, EXECUTES executable subject, runs hermetic (box env stripped, e.g. `env -u DATABASE_URL`) on production's transport and is red on base by its named assertion; every guard and threshold edge change adds is mutated.

Never run a formatter by hand beyond the declared paths.

Gate helpers new call shape must satisfy are read first, a removed duplicate is guarded behaviourally, never by text shape, a new threshold is derived in its comment, and a probe worktree carries the built dist a test reads at import.

Test that writes live store pins it to tmp root: the hub's `tests/conftest.py` pins mail root and `~/.claude/state` files, work-store test passes tmp repo, and new store gets its pin there; before phase 4, MEASURE's test slice re-runs on built tree, and so does MEASURE's population measurement when change adds, changes or removes check, guard or threshold.

## Phase 4 — REVIEW

Invoke review phase 0 already picked — at v1 always `/fabrik-review-scoped` (v1 sync/heavy surface never reaches the lane — it routes right-now instead); *(v2)* `/fabrik-review-scoped`, or full `/fabrik-review` for sync, heavy, migration or >5-file surface (D2, D7) — unchanged, never from memory; nested here, its own scope-growth stop fires at FIRST own-fix-only round, not the third (D8), still closing only on a confirmed-zero pass.

Full `/fabrik-review` over committed work runs after phase 5 step 5 on draft in `<durable>`, its receipt made once, after last `--commit` (the ledger commit or a later fix), that commit its `--range` tip, and committed alone; receipt D-row cites is made before that commit instead (`--restamp`, phase 5); scoped one needs none.

*(v2)* Seats still out at a turn end meet the Stop hook's uncommitted-work block (three times, then it warns through), so the review is dispatched AFTER phase 5 steps 1-5 by default — every run commit captured as step 5 says — a full `/fabrik-review` then taking the after-commit `--range` form phase 5 numbers; a review that finishes inside the turn may still run BEFORE commit, and a sync-path run in main checkout must (phase 5).

Give its seat briefs phase-2 `design.md` path and phase-0 declaration, plus three questions: *does change ESCAPE declared files? did it add mechanism declaration said `no` to? can you name second approach whose merits build cannot settle (an equivalent implementation is not one)?* `yes` to first or third is that seat's UPGRADE verdict — take it; `yes` to second corrects D-row (name mechanism there), never the lane (D-315).

Declared file left UNTOUCHED is padding (guaranteed `0` nothing sees) or unfinished work: finish phase 3 or say why in D-row — never an UPGRADE, which would strand the run.

Decision review changes is re-drafted into D-row with drift noted; each path review fix touches that APPROACH/MIRROR does not name gets phase 2's plan-lock check before fix edits it and, once nested review has closed, *(v2)* `step --phase 4 --design-amend <path>`.

Review is sized before dispatch — callers fix may touch counted, quota runway read; seats create nothing outside scratch (installed corpus included), where nested review keeps its resume artifacts (workflow `args` — pass, ledger — and pin dir).

Under urgent-90 CHECKPOINT record stays open, *(v2)* build is committed through phase 5 step 5's capture line (v1 keeps it uncommitted), and review is sized to runway.

## Phase 5 — CLOSE, in this order

1. Doc Sync Matrix rows this change keys (`CLAUDE.md`) — folded `/fabrik-docs-review`.
2. D-row in `docs/DECISIONS.md` from phase-2 draft, if there was decision — minting and reversible/ONE-WAY classification stay decision-ledger rule's.
3. `CHANGELOG.md` atop `[Unreleased]`; `docs/LESSONS_LEARNT.md` or explicit `none`.
4. `python scripts/final_gate.py --json` → `status: "success"`.
5. Commit with explicit pathspecs + provenance trailers, then capture it, found by its own subject — a `HEAD` read would capture a sibling's commit landing while the post-commit hook runs. Each line is its own plain call, never chained to the commit, which a linked worktree's isolation guard refuses:

```bash
mkdir -p <durable>
<your § EXIT commit: pathspecs, trailers via -F <msg>, private-index for shared-append files>
python3 scripts/command_run.py capture --msg <msg> --out <durable>/commit.sha
```

`capture` finds the newest commit whose message holds `<msg>`'s subject, appends its sha when that commit's own subject is exactly `<msg>`'s, and exits 1 appending nothing otherwise; every run commit — the build's, the ledgers', each a review fix makes — is captured this way.

6. § EXIT's push ladder (never `--force`), then close — capture file, not post-ladder `HEAD` read, is what names YOUR commit:

```bash
python3 scripts/command_run.py done --command fabrik-task \
  --commit $(cat <durable>/commit.sha) \
  --evidence "<what proves the terminal condition>" --feedback "<the four fields>"
```

Close re-measures every commit: at v1 undeclared path is RECORDED as `oversized_mini`, never refused.

*(v2)* path missing from APPROACH/MIRROR/an amendment REFUSES `done` (phase 2's rule and remedy); `blocked`/`handoff` record it as `oversized_mini` instead, never refusing a sanctioned halt.

*(v2)* contract or new-source hit found only here REFUSES `done` and `handoff` too, until `--review <a full /fabrik-review receipt>` names one — `blocked` needs none.

Its range tip must be the LAST `--commit` (`task_lane.py` check (d)), and in the after-commit `--range` form each commit a review fix makes is a run commit: make it through step 5's capture line so its sha lands in `commit.sha`, and the receipt is made ONCE, after the last one, committed alone and never captured or passed to `--commit`; a full `/fabrik-review` over committed work — that form, `/fabrik-review`'s committed-fix form — closes in this order, after step 5's ledger commit:

1. Run full `/fabrik-review` (skipping its own `--init`) with its rows in draft, `review_receipt.py --init --lane --range <base>..HEAD --changed <paths> --out <durable>/<slug>-receipt-draft.md`, until its closing pass — a sync-path run in main checkout, which `done` holds to one commit, takes the `--restamp` form below instead.
2. Run `final_gate.py --check --json` BEFORE step 3's `--init`, so fix gate forces is run commit that lands, captured, first.
3. After last sha in `commit.sha`, `review_receipt.py --init --lane --changed <every path in base..that sha> --scope <slug> --range <base>..<that sha>` — Surface line it writes is what check (d) reads.
4. Carry draft's rows into it (rubric class draft lacked is hunt still owed), run `/fabrik-review`'s close ORDER on it (gate while IN-PROGRESS, embedded, flipped to `Status: CONVERGED`, re-run), then commit that receipt alone (outside D7's one-commit sync-path rule) and push it.
5. Close the nested review's record, then step 6's `done`.

Or review BEFORE commit: `--init` without `--range`, then `review_receipt.py --restamp <receipt>` after review's last fix — receipt rides in that commit and (d) re-hashes its paths (W-ebbedc88).

When two critique verdicts differ or concern stayed OPEN, `--evidence` names split; terminal changed was restated with `--terminal-amend` on or before `--design` call.

## UPGRADE — the one-way ratchet, available from phase 1

Module-test crossing — decision turned one-way, trade-off that appeared, sync/heavy surface noticed mid-build, or phase-4 seat's verdict (mechanism found mid-run is not crossing: D-row names it — D-315) — first materialises seed (phase-2 `design.md` plus `## RESUME` block naming test crossed; before design exists, that block alone, naming phase 1's `measure.md`), then closes; critique returning after handoff is appended to that seed file before `/fabrik-spec` opens from it (never to the `resume_copy`).

⚠️ **`UPGRADE:` must BEGIN the value, and the record takes the FIRST WHITESPACE TOKEN after it** — lead with `files` · `oneway` · `tradeoffs` · `seat` · `sync` · `heavy` (v1 and v2) · *(v2)* `contract` · `new-source` · `behaviours` · `appetite`, then dash and detail; nothing downgrades mid-run:

- **To spec chain** (`files`, `oneway`, `tradeoffs`, `seat`) — build stops and `/fabrik-spec` opens seeded with that file, by your hand:

```bash
python3 scripts/command_run.py handoff --command fabrik-task \
  --resume <durable>/design.md \
  --reason "UPGRADE: <token> — <the test crossed>" --feedback "<the four fields>"
```

- **In place** (`sync` or `heavy`, found mid-run): change is NOT abandoned — finish phase 3, run full `/fabrik-review` at phase 4 instead of `/fabrik-review-scoped` (seeded with `design.md`; nested heavy record is accepted deliberately), discharge phase 5 in full and close with phase-5 `done` line, `--commit` and all, its `--evidence` reading `"UPGRADE: sync — <proof>"`.

`done`, not `handoff`: nothing stays open.

⚠️ `sync` claim close cannot verify from commit's paths is REFUSED — if no sync path survived into commit it was `heavy`, or none.

*(v2)* last four — `contract` · `new-source` · `behaviours` · `appetite` — close ALSO raises itself, from commit, WHETHER OR NOT you typed them: `contract`/`new-source` REFUSE `done`/ `handoff` until `--review <receipt>` names one; `behaviours`/`appetite` are findings only.

Typing one early only pins which proof text the row records — close's own re-measure, never your text, decides whether `--review` is owed.
