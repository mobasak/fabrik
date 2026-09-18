---
description: One small change, one decision, one commit — the lane between a right-now fix and the spec chain. Six phases on ONE run record: SIZE (the start IS the gate), MEASURE, DESIGN, BUILD, REVIEW, CLOSE — the D-row is the durable artifact. TRIGGER — EN: "one small change with one decision", "fix + decide", "small change, one call to make"; TR: "küçük bir değişiklik, tek karar", "düzelt ve karar ver". SKIP — /fabrik-spec's own triggers, and anything the SIZE gate refuses: more than 3 files, a new mechanism, a ONE-WAY decision, real trade-offs, a governance-sync or heavy surface, or no decision at all — each names its own lane. Stage: utility.
argument-hint: "[the ask in one line — sized against the SMALLEST change that discharges it, before drafting]"
---

**One small change, one decision, one commit.** This command SEQUENCES existing machinery and
RESTATES none of it — the run record, the FIX DIRECTIVE, `/fabrik-review-scoped`, the close-out
feedback and the decision-ledger rule keep their own text. New here: the SIZE gate (phase 0), the DESIGN step (phase 2), phase 5's re-measure of its own
commit, and the UPGRADE ratchet.

{{include:run-record}}

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
  --declare decision=yes,heavy=no,mechanism=no,oneway=no,tradeoffs=no
```

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
commit. All twelve, each with its counter or its honest lack of one, are (1)–(12) in § Constraints C3 of
`/opt/fabrik/docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md`; read them there, not here.

## Phase 1 — MEASURE

FIX DIRECTIVE step 1. Then
`python scripts/select_rules.py --changed <the declared paths>` — the path-scoped form — and READ
the packs it prints.

## Phase 2 — DESIGN, where it will be minted

Write six fields — **PROBLEM · APPROACH · DECISION (reversible?) · MIRROR · OUT · TERMINAL** — to
`<scratchpad>/fabrik-task/<sid>/<started_at>/design.md`, then put them in the record:

```bash
python3 scripts/command_run.py step --phase 2 --title "design: <that path>" \
  --design <scratchpad>/fabrik-task/<sid>/<started_at>/design.md
```

`--design` stores that file's TEXT — refusing it over the ledger field cap rather than truncating — so the
design outlives the scratch. A refusal discards the whole `step`: fix the file and
re-run, or the record stays at phase 1. It lands ONCE — a second `--design` is ignored with a NOTE
while everything else reads like success. MIRROR is mandatory (`CLAUDE.md` § Behavior). The fields
are the D-row's draft: APPROACH+DECISION+MIRROR → *what*, PROBLEM → *why*, the declared files →
*where*; OUT and TERMINAL stay in the record. ⚠️ A literal `|` is written `&#124;` — a backslash
escape makes `check_decisions_unique.py` read a 7-cell row.

## Phase 3 — BUILD

**Plan locks first** — no CLI reads them: each `*.json` in `.fabrik/plan-locks/` with `status: active`.
A declared path inside another lock's `owned_paths` is a STOP; so is an ACTIVE lock whose `owned_paths` is empty or absent — that matches nothing and passes everything. Then the change and its grader, red-first per FIX
DIRECTIVE 4; a shared-append file goes through § EXIT's private-index recipe, never the working file.

## Phase 4 — REVIEW

Invoke `/fabrik-review-scoped` as the skill — unchanged, never from memory. Give its seat briefs
the phase-2 `design.md` path and the phase-0 declaration, plus three questions: *does the change ESCAPE the declared files? did it add a mechanism the declaration said `no` to?
can you name a second approach the declaration said did not exist?* A `yes` to any is that seat's UPGRADE verdict — take it. A declared file left UNTOUCHED is padding
(a guaranteed `0` nothing sees) or unfinished work: finish phase 3 or say why in the D-row — never
an UPGRADE, which would strand the run. This is
where spec-review is folded in: the design is reviewed with what it produced.

## Phase 5 — CLOSE, in this order

1. The Doc Sync Matrix rows this change keys (`CLAUDE.md`) — the folded `/fabrik-docs-review`.
2. The D-row in `docs/DECISIONS.md` from the phase-2 draft, if there was a decision — minting and the
   reversible/ONE-WAY classification stay the decision-ledger rule's.
3. `CHANGELOG.md` atop `[Unreleased]`; `docs/LESSONS_LEARNT.md` or an explicit `none`.
4. `python scripts/final_gate.py --json` → `status: "success"`.
5. Commit with explicit pathspecs + provenance trailers, **chaining the capture off the commit** — that narrows the window to the instant the commit returns; it never closes, and a sibling landing inside is captured instead:

```bash
mkdir -p <scratchpad>/fabrik-task/<sid>/<started_at> \
  && <your § EXIT commit: pathspecs, trailers via -F, private-index for shared-append files> \
  && git rev-parse -q --verify HEAD > <scratchpad>/fabrik-task/<sid>/<started_at>/commit.sha || exit 1
```

6. § EXIT's push ladder (never `--force`), then close — the capture file, not a post-ladder `HEAD`
   read, is what names YOUR commit:

```bash
python3 scripts/command_run.py done --command fabrik-task \
  --commit "$(cat <scratchpad>/fabrik-task/<sid>/<started_at>/commit.sha)" \
  --evidence "<what proves the terminal condition>" --feedback "<the four fields>"
```

The close re-measures that commit and records `oversized_mini`. A non-zero count is not a failure to
hide — it is the lane's own honesty; `change:` is where you say what the gate should have asked.

## UPGRADE — the one-way ratchet, available from phase 1

A size input crossing — a fourth file, a verb that must exist, a decision turned one-way, a trade-off
that appeared, or a phase-4 seat's verdict — **first materialises the seed** (the
phase-2 `design.md` plus a `## RESUME` block naming the test crossed; before the design exists, that
block alone), then closes. ⚠️ **`UPGRADE:` must BEGIN the value, and the record takes the FIRST WHITESPACE TOKEN after it** —
lead with `files` · `mechanism` · `oneway` · `tradeoffs` · `seat` · `sync` · `heavy`, then a dash and the detail. Nothing downgrades mid-run:

- **To the spec chain** (`files`, `mechanism`, `oneway`, `tradeoffs`, `seat`) — the build stops and
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
  not `handoff`: nothing stays open. ⚠️ A `sync` claim the close cannot refute from the commit's paths
  is REFUSED — if no sync path survived into the commit it was `heavy`, or none.
