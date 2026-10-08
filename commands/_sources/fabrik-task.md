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
`<sid>` is `$CLAUDE_CODE_SESSION_ID` — one spelling, or phase 5's `cat` reads a path phase 2 never wrote.

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

*(v2)* `consumers=external` when another repo reads the change; v1 ignores the key.

`--file` is repeatable, ONE quoted repo path each. A path that does not exist yet is accepted on
purpose: **declare the grader you are about to write.** Declare the CODE surface ONLY — the close
excludes the Doc Sync Matrix destinations, the ledger files and `docs/CAPABILITIES.md`, so declaring
`CHANGELOG.md` burns a slot and can refuse the start on a sibling's WIP.

The tool prints either CORRECTIONS, each naming itself (a DIRTY declared path may be a sibling's
WIP — message the author, never stage it), or a LANE verdict naming where the work belongs. Read
every line: flag gaps print together, path checks stop at the first. ⚠️ `sync lane test SKIPPED` on
stderr means the hub filter was unreadable — that test did NOT run. **A refusal is the answer, not an obstacle**: take the named lane, no record was opened. On
success it prints `RECORD: <started_at>` — paste it into the phase-2 path.

⚠️ **COBRA (D-253).** The cheapest way to satisfy this gate without producing the outcome is to
UNDER-DECLARE here and touch more at phase 3; the counter is phase 5's re-measure of this run's own
commit. All twelve cobras and their counters are § Constraints C3 of
`/opt/fabrik/docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md`.

## Phase 1 — MEASURE

FIX DIRECTIVE step 1 whole — a failure reported with a command is replayed by that command, never
a reconstruction. Then, before phase 2 and any edit, each command and its output goes to
`<scratchpad>/fabrik-task/<sid>/<started_at>/measure.md`, beside phase 2's `design.md`, never in
it (a pasted line opening with a field word or a `#` moves the declared paths): the tests that
import or grade the declared files, that slice and never the whole suite (a red now is
pre-existing); `git fetch` and the declared paths diffed against the remote branch the work merges
into (`origin/master` in the hub; elsewhere name the ref chosen, or say there is no remote); the prior record grepped — `docs/DECISIONS.md`, the files' docstrings,
`/opt/fabrik-mail/<repo>/archive`, the work store where the repo keeps one, the fragment or pack
the rule already lives in; the population the change writes or thresholds measured (its readers
are MIRROR's) — every writer, every occurrence of the shape it admits, every host it runs on, and
the n behind any rate, bound or zero the design will claim; each external contract probed live
once, a list read whole, never a sample. Then
`python scripts/select_rules.py --changed <the declared paths>` — the path-scoped form — and READ
the packs it prints.

## Phase 2 — DESIGN, where it will be minted

Write six fields — **PROBLEM · APPROACH · DECISION (reversible?) · MIRROR · OUT · TERMINAL** — to
`<scratchpad>/fabrik-task/<sid>/<started_at>/design.md`.

{{include:design-critique}}

Then record them:

```bash
python3 scripts/command_run.py step --phase 2 --title "design: <that path>" \
  --design <scratchpad>/fabrik-task/<sid>/<started_at>/design.md
```

`--design` stores that file's TEXT whole (no cap — D-314), so the
design outlives the scratch. A refusal discards the `step`: fix the file and
re-run, or the record stays at phase 1. It lands ONCE — a second `--design` is ignored with a NOTE
while everything else reads like success. Add a `## Behaviours` list — each naming its test, at
most 7 (an 8th is the `behaviours` UPGRADE, *(v2)*) — and name every file the build will touch,
the Behaviours' tests, deletions and a rename's both paths included, under line-start UPPERCASE
`APPROACH:`/`MIRROR:` labels, before any line opening with a field word or a `#` (fenced or not),
one bare repo-relative path per backtick pair (`a.py::f`, `a.py:120` and `a.py, b.py` match
nothing; of receipts, only a `--review` one is exempt): *(v2)* a committed path missing from both
REFUSES `done` at close (v1 measures `--file` instead and only RECORDS); the remedy is
`step --phase 2 --design-amend <path>` *(v2)*, append-only — it never overwrites a recorded field —
and counted on the close as `design_amends`.
MIRROR is mandatory (`CLAUDE.md` § Behavior) and names every reader of what changes — callers,
each branch of a changed function, every resolver of the same identity, consumers of a moved or
deleted file, other surfaces stating a changed claim, the gates that grade it — each found by an
executed search, with the shape it now fails on and its cost measured, never estimated. A reader
the build leaves untouched is named without backticks: every backticked MIRROR path counts as
declared at a *(v2)* close. The fields
are the D-row's draft: APPROACH+DECISION+MIRROR → *what*, PROBLEM → *why*, the declared files →
*where*; OUT and TERMINAL stay in the record. ⚠️ A literal `|` is written `&#124;` — a backslash
escape makes `check_decisions_unique.py` read a 7-cell row.

## Phase 3 — BUILD

**Plan locks first** — no CLI reads them: each `*.json` in `.fabrik/plan-locks/` with `status: active`.
A declared path inside another lock's `owned_paths` is a STOP; so is an ACTIVE lock whose `owned_paths` is empty or absent — that matches nothing and passes everything. Then the change and its grader, red-first per FIX
DIRECTIVE 4; a shared-append file goes through § EXIT's private-index recipe, never the working file.
One commit carries it at v1; *(v2)* several may, SPACE-separated — `done --commit shaA shaB …`
measures each in order; a sync-path run (D7) commits ONCE, after phase 4, in the main checkout
(`done` refuses more outside a worktree; `blocked`/`handoff` only note it).

## Phase 4 — REVIEW

Invoke the review phase 0 already picked — at v1 always `/fabrik-review-scoped` (a v1 sync/heavy
surface never reaches the lane — it routes right-now instead); *(v2)* `/fabrik-review-scoped`, or
the full `/fabrik-review` for a sync, heavy, migration or >5-file surface (D2, D7) — unchanged,
never from memory; nested here, its own scope-growth stop fires at the FIRST own-fix-only round,
not the third (D8), still closing only on a confirmed-zero pass. Give its seat briefs
the phase-2 `design.md` path and the phase-0 declaration, plus three questions: *does the change ESCAPE the declared files? did it add a mechanism the declaration said `no` to?
can you name a second approach the declaration said did not exist?* A `yes` to the first or third is that seat's UPGRADE verdict — take it; a `yes` to the second corrects the D-row (name the mechanism there), never the lane (D-315). A declared file left UNTOUCHED is padding
(a guaranteed `0` nothing sees) or unfinished work: finish phase 3 or say why in the D-row — never
an UPGRADE, which would strand the run.

## Phase 5 — CLOSE, in this order

1. The Doc Sync Matrix rows this change keys (`CLAUDE.md`) — the folded `/fabrik-docs-review`.
2. The D-row in `docs/DECISIONS.md` from the phase-2 draft, if there was a decision — minting and the
   reversible/ONE-WAY classification stay the decision-ledger rule's.
3. `CHANGELOG.md` atop `[Unreleased]`; `docs/LESSONS_LEARNT.md` or an explicit `none`.
4. `python scripts/final_gate.py --json` → `status: "success"`.
5. Commit with explicit pathspecs + provenance trailers, **chaining the capture off the commit** (the window never closes — a sibling landing inside is captured instead):

```bash
mkdir -p <scratchpad>/fabrik-task/<sid>/<started_at> \
  && <your § EXIT commit: pathspecs, trailers via -F, private-index for shared-append files> \
  && git rev-parse -q --verify HEAD >> <scratchpad>/fabrik-task/<sid>/<started_at>/commit.sha || exit 1
```

6. § EXIT's push ladder (never `--force`), then close — the capture file, not a post-ladder `HEAD`
   read, is what names YOUR commit:

```bash
python3 scripts/command_run.py done --command fabrik-task \
  --commit $(cat <scratchpad>/fabrik-task/<sid>/<started_at>/commit.sha) \
  --evidence "<what proves the terminal condition>" --feedback "<the four fields>"
```

The close re-measures every commit. At v1 an undeclared path is RECORDED as `oversized_mini`,
never refused. *(v2)* a path missing from APPROACH/MIRROR/an amendment REFUSES `done` (phase 2's
rule and remedy); `blocked`/`handoff` record it as `oversized_mini` instead, never refusing a
sanctioned halt. *(v2)* a contract or new-source hit found only here REFUSES `done` and `handoff`
too, until `--review <a full /fabrik-review receipt>` names one — `blocked` needs none.

## UPGRADE — the one-way ratchet, available from phase 1

A module-test crossing — a decision turned one-way, a trade-off that appeared, a sync/heavy surface
noticed mid-build, or a phase-4 seat's verdict (a mechanism found mid-run is not a crossing: the
D-row names it — D-315) —
**first materialises the seed** (the
phase-2 `design.md` plus a `## RESUME` block naming the test crossed; before the design exists, that
block alone, naming phase 1's `measure.md`), then closes. ⚠️ **`UPGRADE:` must BEGIN the value, and the record takes the FIRST WHITESPACE TOKEN after it** —
lead with `files` · `oneway` · `tradeoffs` · `seat` · `sync` · `heavy` (v1 and v2) · *(v2)*
`contract` · `new-source` · `behaviours` · `appetite`, then a dash and the detail. Nothing
downgrades mid-run:

- **To the spec chain** (`files`, `oneway`, `tradeoffs`, `seat`) — the build stops and
  `/fabrik-spec` opens seeded with that file, by your hand:

```bash
python3 scripts/command_run.py handoff --command fabrik-task \
  --resume <scratchpad>/fabrik-task/<sid>/<started_at>/design.md \
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
