---
description: One small change, one decision, one commit — the lane between a right-now fix and the spec chain. Six phases on ONE run record: SIZE (the start IS the gate), MEASURE, DESIGN, BUILD, REVIEW, CLOSE — the D-row is the durable artifact. TRIGGER — EN: "one small change with one decision", "fix + decide", "small change, one call to make"; TR: "küçük bir değişiklik, tek karar", "düzelt ve karar ver". SKIP — /fabrik-spec's own triggers, and what the SIZE gate refuses: a ONE-WAY decision, real trade-offs, no decision at all; at lane v2 also a contract path, consumers=external or an appetite over 240 min; at lane v1 also more than 3 files or a sync/heavy surface — each names its own lane (a new mechanism is recorded, never refused — D-315). Stage: utility.
argument-hint: "[the ask in one line — sized against the SMALLEST change that discharges it, before drafting]"
---

**One small change, one decision, one commit.** This command SEQUENCES existing machinery and
RESTATES none of it — the run record, the FIX DIRECTIVE, `/fabrik-review-scoped`, the close-out
feedback and the decision-ledger rule keep their own text. New here: the SIZE gate (phase 0), the DESIGN step (phase 2), phase 5's re-measure of its own
commit, and the UPGRADE ratchet. A feature splitting into independently shippable slices is
several of these runs, never one bundling them (D6).

**Two lane versions share this text** (`.fabrik/lane.json`; `start` prints which). **Lane v1**
(a repo pinning `{"version": 1}`) is the old file-count gate —
`command-run-protocol.md:52`'s `start` row. **Lane v2** replaces the
file count with the module tests and adds every *(v2)*-tagged mechanism below: the `consumers=`
key, `--appetite`/`--why`/`--from-downgrade`, `--design-amend`, the undeclared-path REFUSAL, the
space-separated multi-commit close, `--review`, and the Behaviours UPGRADE's four close-raised
tokens.

{{include:run-record}}
{{include:orient}}

⚠️ **Neither generic line above is this lane's** — `command_run.py` REFUSES a `fabrik-task` `start`
without `--file`/`--declare` and a `done` without `--commit`; paste the SIZE line and phase 5's close.
`handoff` is the record's third sanctioned terminal (`AGENT_CLOSED_STATES`): UPGRADE uses it.
`<durable>` is the `SCRATCH:` path `start` prints (under `<main checkout>/.tmp/runs/`, so it survives a WSL
`/tmp` wipe and the worktree's removal), never `RUN-SCRATCH:` — one spelling, or phase 5's `cat` reads a path
phase 2 never wrote; a linked-worktree session, whose Write tool refuses a main-checkout path, changes each
file as a copy in its scratchpad (`cp` it from that path first when it exists) and `cp`s the whole copy back
after every change, which keeps any content byte for byte; with no `SCRATCH:` line, it is
`<scratchpad>/fabrik-task/<started_at>` (in /tmp).

## SIZE — phase 0 is the `start` itself

Apply the lane table (`CLAUDE.md` § Orient step 0) to the **smallest change that discharges the ask,
before drafting**. Then open the record:

```bash
python3 scripts/command_run.py start --command fabrik-task --phases 5 \
  --terminal "<the one-line condition that ends this run>" \
  --surface "<the subject, one phrase>" \
  --file "<path 1>" --file "<path 2>" \
  --declare decision=yes,heavy=no,mechanism=no,oneway=no,tradeoffs=no,consumers=internal
```

*(v2)* `consumers=external` when another repo reads the change; v1 ignores the key. `heavy=yes` includes
operator-named work (lane row 1b), declared here rather than found at phase 4.

`--file` is repeatable, ONE quoted repo path each. A path that does not exist yet is accepted on
purpose: **declare the grader you are about to write**, `git check-ignore -v` each new file path and `git add` it just
before phase 5's pathspec commit, which refuses an unstaged one (an ignored one stays out without `-f`); `ls` and grep
every other path for the rule first, since a typo reads as that grader; a golden or snapshot that pins the output is
declared too. Declare the CODE surface ONLY — the close excludes the Doc Sync Matrix destinations, the ledger files and
`docs/CAPABILITIES.md`, so declaring `CHANGELOG.md` burns a slot and can refuse the start on a sibling's WIP.

The tool prints either CORRECTIONS, each naming itself (a DIRTY declared path may be a sibling's
WIP — message the author, never stage it), or a LANE verdict naming where the work belongs. Read
every line: flag gaps print together, path checks stop at the first. ⚠️ `sync lane test SKIPPED` on
stderr means the hub filter was unreadable — that test did NOT run. **A refusal is the answer, not an obstacle**: take the named lane, no record was opened. On
success it prints `RECORD: <started_at>` and `SCRATCH: <path>` — the second is `<durable>`.

⚠️ **COBRA (D-253).** The cheapest way to satisfy this gate without producing the outcome is to
UNDER-DECLARE here and touch more at phase 3; the counter is phase 5's re-measure of this run's own
commit. All twelve cobras and their counters are § Constraints C3 of
`/opt/fabrik/docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md`.

## Phase 1 — MEASURE

FIX DIRECTIVE step 1 whole — a failure reported with a command is replayed by that command, never a reconstruction,
and a work item's cited `path:line` is grepped here, in the cited file, for the symbol it names, and a failure or
error path it claims there is replayed on a copy carrying the state it needs (a grep hit can sit in dead code); a
miss, or a replay on a copy carrying that state that does not fail as claimed, is a finding PROBLEM states, never the
item's wording, and a replay whose copy cannot carry that state is recorded unverified, never as refuted (MIRROR
greps every name the design uses again). Then, before phase 2 and any edit, each command and its output goes to
`<durable>/measure.md`, beside phase 2's `design.md`, never in it (a pasted line opening with a field word or a `#`
moves the declared paths): the tests that import, grade or run the declared files (grep the tests for each file's
name and every mode or flag the change extends, since a test that runs a script by subprocess never imports it), that
slice and never the whole suite (a red now is pre-existing); `git fetch` and the declared paths diffed against the
remote branch the work merges into (`origin/master` in the hub; elsewhere name the ref chosen, or say there is no
remote); the prior record grepped — `docs/DECISIONS.md`, the files' docstrings (and a copied script's),
`/opt/fabrik-mail/<repo>/archive`, the work store where the repo keeps one, the fragment or pack the rule already
lives in; the population the change writes or thresholds measured (its readers are MIRROR's) — every writer, every
occurrence of the shape it admits, every host it runs on, every config and env value a changed format can sit in
(grep them for its shape, e.g. `${`), the transport handing a new env var to the process (compose `environment:`,
`env_file`, a build arg, another launcher) read on the started process (e.g. `docker compose run --rm <svc> env`, its
keys recorded, never its values), and the n behind any rate, bound or zero the design will claim; each external
contract probed live once, a list read whole, never a sample — each by EXECUTING the real path on real data (the
producer's code, the tool's run output per mode, the design's own classifier, the writer of each state value it
trusts or ranks on), never a source read or a proxy: the tests that drive it by subprocess, the completion gate's own
command, a recipe's real target layout, the reported incident replayed on a copy one step past its symptom (what the
reporter did next), a tool that scopes by a commit or diff range run where the branch's merge-base is its merge
target's tip and where the target has moved past it, each spelling of a parsed input that the commands and docs
feeding it prescribe, a mechanism copied from another script run read-only against the live state of each host it
will run on (a side-effecting step on a copy), each callee a fail-open branch wraps and how it fails, whether a
production path reaches the text, what a concurrent reader sees mid-write, a before/after hash of every file it
writes, the codec a change touches run on non-UTF-8 bytes, NUL and that codec's own escape, an independent parser for
a parsed format, its operator-facing strings in every worker it feeds, a count repo-wide (`.venv`/`.claude` excluded)
and per artifact class, whose commits a gate's new scope holds, and the whole output, not one field, with each hook
output it grows sized against Claude Code's 10,000-character cap (https://code.claude.com/docs/en/hooks); a grader
the design relies on is shown red on a deliberately broken input, since a pass proves nothing until it can fail. Then
`python scripts/select_rules.py --changed <the declared paths>` — the path-scoped form — and READ the packs it
prints.

## Phase 2 — DESIGN, where it will be minted

Write six fields — **PROBLEM · APPROACH · DECISION (reversible?) · MIRROR · OUT · TERMINAL** — to
`<durable>/design.md`. A mechanism copied from another script carries, as Behaviours tested here (several may share
one), the failure directions its tests and D-rows settled. Before such a copy, a rule another component already
applies is tried as a read of its output (stdout, a record, an exported function); when the copy stays, DECISION says
why the read cannot serve. Each input the design branches on is tabulated whole in a `design.md` table, outside the
Behaviours list: every value a state it reads can hold, the unit another tool's rule is evaluated per (window, agent,
repo), every path through a guard (a forced refresh after a write as well as the periodic one); a parser it adds
takes a strict grammar and fails closed on the rest. That grammar admits every spelling MEASURE recorded.

{{include:design-critique}}

Before the seats go out: re-read `design.md` against the working tree; DECISION names its evidence and whether it is
independent of the change; a shipped config is executed; the fixtures a grader borrows are listed with what each
stubs; the existing suites run against a throwaway scratch build of a new refusal (not phase 3). This lane's brief
also has each seat EXECUTE: replay the reported incident and the real corpus through the design; run each matcher,
semantics or shell claim against the real tool under the live guard, a new parser on input outside its grammar; sweep
sibling write paths and the tests pinning a moved value; name each new guard's fail direction and any second approach
the build cannot settle; run a mechanism the design copies read-only against the live state of each host it will run
on (a side-effecting step on a copy); execute one claim about every external dependency. It pins the tree (a commit
or `git archive` copy) and any live state file the design reads, names the unmerged branch owning a mirrored file,
bars live-provider credentials (no `.env` loaded, no provider client built) and asks for small outputs. Wait for both
in-turn: with stamped seats out, the Stop hook's run-record block stands down and will not hold you. A concern is
ACCEPTED only after the tests are grepped for every line it touches; an optional one adding behaviour only when
provable inside the declared files, else filed to its owner; a later executed review finding may override it,
recorded in the D-row with the drift noted. A second approach the build cannot settle (an equivalent implementation
is not one), its seat's claim executed and holding, is the § UPGRADE crossing `tradeoffs`, taken here before
`--design`, never folded in as ACCEPTED. Then, before this call: read the plan locks (no CLI does: each `*.json` in
`.fabrik/plan-locks/` with `status: active`) — a declared path or one backticked in APPROACH/MIRROR inside another
lock's `owned_paths` is a STOP, and so is an ACTIVE lock whose `owned_paths` is empty or absent (it matches nothing
and passes everything); re-read `design.md`; each Behaviour names its test; every touched path is bare in backticks
under `APPROACH:`/`MIRROR:`; `--design` lands ONCE. Record them:

```bash
python3 scripts/command_run.py step --phase 2 --title "design: <that path>" \
  --design <durable>/design.md
```

If MEASURE or the critiques changed what ends the run, restate it with
`--terminal-amend "<one line>"` on that `--design` call or any step before it — refused once the design is recorded,
so no run moves its goal to fit the result; `terminal_amends` keeps the old one. There is no
DECISION amend: the design is recorded after the critiques fold.

`--design` stores that file's TEXT whole (no cap — D-314), so the
design outlives the scratch. A refusal discards the `step`: fix the file and
re-run, or the record stays at phase 1. It lands ONCE — a second `--design` is ignored with a NOTE
while everything else reads like success. Add a `## Behaviours` list — each naming its test, at
most 7 (an 8th is the `behaviours` UPGRADE, *(v2)*) — and name every file the build will touch,
the Behaviours' tests, deletions and a rename's both paths included, under line-start UPPERCASE
`APPROACH:`/`MIRROR:` labels, before any line opening with a field word or a `#` (fenced or not),
one bare repo-relative path per backtick pair (`a.py::f`, `a.py:120` and `a.py, b.py` match
nothing; a `.md` under `docs/development/reviews/` but `archived/` is exempt): *(v2)* a committed
path missing from both
REFUSES `done` at close (v1 measures `--file` instead and only RECORDS); the remedy is
`step --phase 2 --design-amend <path>` *(v2)*, append-only — it never overwrites a recorded field —
and counted on the close as `design_amends`.
MIRROR is mandatory (`CLAUDE.md` § Behavior) and names every reader of what changes — callers,
each branch of a changed function, every resolver of the same identity, consumers of a moved or
deleted file, other surfaces stating a changed claim, the gates that grade it — each found by an
executed search, with the shape it now fails on and its cost measured, never estimated. The search is the
whole tracked tree (tests, their pinned strings and hardcoded values, `commands/`, UI, docs) and every vendored copy outside it (`find /opt` by the file's name) under every spelling of the identifier and its rule's key
verbs — the literal path beside any constant, every party a text reaches, every reader of a changed record shape
or stdout (grep its tests for `== {` and `len(`), every Python reader of a name by an `ast.walk` census beside the
grep, never `tree.body` alone (a function-local or `try:` import sits below it; a string-named import, `getattr` or
subprocess argv is no import node, so the grep finds it),
the hub scripts the text tells a project to run, the file handing a new env var to the process and the spec, the
parser a read config belongs to, whether a normalised form is what readers receive, the form a ported validator's source validates, the first-or-every rule for a
repeating field, the paths guarded code opens and the env each reads, and for a registration or allowlist the
checks each bucket runs — sibling write paths included; each new guard, veto or fallback names its fail direction — which error is
dangerous, an answer versus an outage. Every function, anchor or subject the design names is grepped to exist,
and each guard a claim relies on is quoted. A reader
the build leaves untouched is named without backticks: every backticked MIRROR path counts as
declared at a *(v2)* close. The fields
are the D-row's draft: APPROACH+DECISION+MIRROR → *what*, PROBLEM → *why*, the declared files →
*where*; OUT and TERMINAL stay in the record. ⚠️ A literal `|` is written `&#124;` — a backslash
escape makes `check_decisions_unique.py` read a 7-cell row.

## Phase 3 — BUILD

Re-run phase 2's plan-lock check first: a `--design-amend` path or a lock taken since is the same STOP. The change and its grader, red-first per FIX
DIRECTIVE 4 against the recorded design (a test drafted before the critiques folded is rewritten, never made green); a shared-append file goes through § EXIT's private-index recipe, never the working file.
One commit carries it at v1; *(v2)* several may, SPACE-separated — `done --commit shaA shaB …`
measures each in order; a sync-path run (D7) commits ONCE, after phase 4, in the main checkout
(`done` refuses more outside a worktree; `blocked`/`handoff` only note it). At v1 that one
commit also carries phase 5's ledgers, so nothing is committed before phase 5. Each grader names its input domain
and borrowed fixtures, EXECUTES an executable subject, runs hermetic (box env stripped, e.g. `env -u DATABASE_URL`) on production's transport and is red on base
by its named assertion; every guard and threshold edge the change adds is mutated. Never run a formatter by hand beyond the declared paths. The gate helpers a new call shape must satisfy are read
first, a removed duplicate is guarded behaviourally, never by text shape, a new threshold is derived in its
comment, and a probe worktree carries the built dist a test reads at import. A test that writes a live store pins it to a tmp root: the hub's `tests/conftest.py` already pins the mail root and the `~/.claude/state` files, a work-store test passes a tmp repo, and a new store gets its pin there; before phase 4, MEASURE's test slice re-runs on the built tree, and so does MEASURE's population measurement when the change adds, changes or removes a check, guard or threshold.

## Phase 4 — REVIEW

Invoke the review phase 0 already picked — at v1 always `/fabrik-review-scoped` (a v1 sync/heavy
surface never reaches the lane — it routes right-now instead); *(v2)* `/fabrik-review-scoped`, or
the full `/fabrik-review` for a sync, heavy, migration or >5-file surface (D2, D7) — unchanged,
never from memory; nested here, its own scope-growth stop fires at the FIRST own-fix-only round,
not the third (D8), still closing only on a confirmed-zero pass. A full `/fabrik-review` over committed work runs after phase 5 step 5, its receipt's `--range` tip the last `--commit` (the ledger commit or a later fix), committed alone; a receipt the D-row cites is made before that commit instead (`--restamp`, phase 5); a scoped one needs none. Give its seat briefs
the phase-2 `design.md` path and the phase-0 declaration, plus three questions: *does the change ESCAPE the declared files? did it add a mechanism the declaration said `no` to?
can you name a second approach whose merits the build cannot settle (an equivalent implementation is not one)?* A `yes` to the first or third is that seat's UPGRADE verdict — take it; a `yes` to the second corrects the D-row (name the mechanism there), never the lane (D-315). A declared file left UNTOUCHED is padding
(a guaranteed `0` nothing sees) or unfinished work: finish phase 3 or say why in the D-row — never
an UPGRADE, which would strand the run. A decision the review changes is re-drafted into the D-row with the drift
noted. The review is sized before dispatch — the callers a fix may touch counted, the quota runway read; seats
create nothing outside scratch (an installed corpus included), where the nested review keeps its resume artifacts (the workflow `args` — pass, ledger — and the pin dir). Under
the urgent-90 CHECKPOINT the record stays open, *(v2)* the build is committed through phase 5 step 5's
capture line (v1 keeps it uncommitted), and the review is sized to the runway.

## Phase 5 — CLOSE, in this order

1. The Doc Sync Matrix rows this change keys (`CLAUDE.md`) — the folded `/fabrik-docs-review`.
2. The D-row in `docs/DECISIONS.md` from the phase-2 draft, if there was a decision — minting and the
   reversible/ONE-WAY classification stay the decision-ledger rule's.
3. `CHANGELOG.md` atop `[Unreleased]`; `docs/LESSONS_LEARNT.md` or an explicit `none`.
4. `python scripts/final_gate.py --json` → `status: "success"`.
5. Commit with explicit pathspecs + provenance trailers, **chaining the capture off the commit**, found by its own subject — a `HEAD` read would capture a sibling's commit landing while the post-commit hook runs:

```bash
mkdir -p <durable> \
  && <your § EXIT commit: pathspecs, trailers via -F <msg>, private-index for shared-append files> \
  && subj=$(head -n1 <msg>) && sha=$(git log -1 --format=%H -F --grep "$subj") && [ -n "$sha" ] \
  && [ "$(git log -1 --format=%s "$sha")" = "$subj" ] && echo "$sha" >> <durable>/commit.sha || exit 1
```

6. § EXIT's push ladder (never `--force`), then close — the capture file, not a post-ladder `HEAD`
   read, is what names YOUR commit:

```bash
python3 scripts/command_run.py done --command fabrik-task \
  --commit $(cat <durable>/commit.sha) \
  --evidence "<what proves the terminal condition>" --feedback "<the four fields>"
```

The close re-measures every commit. At v1 an undeclared path is RECORDED as `oversized_mini`,
never refused. *(v2)* a path missing from APPROACH/MIRROR/an amendment REFUSES `done` (phase 2's
rule and remedy); `blocked`/`handoff` record it as `oversized_mini` instead, never refusing a
sanctioned halt. *(v2)* a contract or new-source hit found only here REFUSES `done` and `handoff`
too, until `--review <a full /fabrik-review receipt>` names one — `blocked` needs none. Its range tip must be the LAST `--commit` (`task_lane.py` check (d)), and
in the after-commit `--range` form each commit a review fix makes is a run commit: make it through step 5's capture line
so its sha lands in `commit.sha`, and re-make the receipt after the last one as `/fabrik-review`'s exit proofs say (a
sync-path run in the main checkout, which `done` holds to one commit, reviews BEFORE that commit instead — the
`--restamp` form below):
after the last sha in `commit.sha`, `review_receipt.py --init --lane --changed <every path in base..that sha> --scope <slug>
--range <base>..<that sha>` — the Surface line it writes is what check (d) reads (a re-tip after a fix commit takes a new `--scope`), run the full `/fabrik-review` into it (skipping its own `--init`) until `Status: CONVERGED`, then commit that receipt alone
(outside D7's one-commit sync-path rule) and push it — never captured or passed to `--commit`. Or review BEFORE the commit: `--init` without `--range`, then `review_receipt.py --restamp <receipt>` after the review's last fix — the receipt rides in that commit and (d) re-hashes its paths (W-ebbedc88). When the two critique verdicts differ or a concern stayed OPEN, `--evidence` names the split; a
terminal it changed was restated with `--terminal-amend` on or before the `--design` call.

## UPGRADE — the one-way ratchet, available from phase 1

A module-test crossing — a decision turned one-way, a trade-off that appeared, a sync/heavy surface
noticed mid-build, or a phase-4 seat's verdict (a mechanism found mid-run is not a crossing: the
D-row names it — D-315) —
**first materialises the seed** (the
phase-2 `design.md` plus a `## RESUME` block naming the test crossed; before the design exists, that
block alone, naming phase 1's `measure.md`), then closes; a critique returning after the handoff is appended to
that seed file before `/fabrik-spec` opens from it (never to the `resume_copy`). ⚠️ **`UPGRADE:` must BEGIN the value, and the record takes the FIRST WHITESPACE TOKEN after it** —
lead with `files` · `oneway` · `tradeoffs` · `seat` · `sync` · `heavy` (v1 and v2) · *(v2)*
`contract` · `new-source` · `behaviours` · `appetite`, then a dash and the detail. Nothing
downgrades mid-run:

- **To the spec chain** (`files`, `oneway`, `tradeoffs`, `seat`) — the build stops and
  `/fabrik-spec` opens seeded with that file, by your hand:

```bash
python3 scripts/command_run.py handoff --command fabrik-task \
  --resume <durable>/design.md \
  --reason "UPGRADE: <token> — <the test crossed>" --feedback "<the four fields>"
```

- **In place** (`sync` or `heavy` — found mid-run) — the change is NOT abandoned: finish phase 3, run
  the full `/fabrik-review` at phase 4 instead of `/fabrik-review-scoped` (seeded with `design.md`; the
  nested heavy record is accepted deliberately), discharge phase 5 in full, and close with the phase-5
  `done` line — `--commit` and all — its `--evidence` reading `"UPGRADE: sync — <proof>"`. `done`,
  not `handoff`: nothing stays open. ⚠️ A `sync` claim the close cannot verify from the commit's paths
  is REFUSED — if no sync path survived into the commit it was `heavy`, or none.

*(v2)* The last four — `contract` · `new-source` · `behaviours` · `appetite` — the close ALSO raises
itself, from the commit, WHETHER OR NOT you typed them: `contract`/`new-source` REFUSE `done`/
`handoff` until `--review <receipt>` names one; `behaviours`/`appetite` are findings only. Typing
one early only pins which proof text the row records — the close's own re-measure, never your
text, decides whether `--review` is owed.
