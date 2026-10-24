# Lean command corpus — half the size, no rule lost

Status: DRAFT
Profile: full
Size: large
Work item: W-96f36043 (P0) · Decisions: D-1216 (the program), D-1217 (this design, panel-approved) · Author: kaizen · 2026-10-25

## Personas

- **PRIMARY — the operator**, who pays for every run's minutes and tokens: "most of our commands like this and
  taking too much time to execute them" (D-1216). Their loop is: invoke a `/fabrik-*` command, wait, and read the
  close. This spec shortens the wait, not the loop.
- **The agents that execute the commands**: the hub's builders (infra, infra-2, infra-3, fleet, intel, kaizen),
  every project's agents on ~46 repos, and the seats they dispatch. They read the rendered text and pay its
  tokens on every run and every seat.
- **kaizen**: the duty-holder for the rewrites, the ledgers and the command wording of L1/L2 (D-627 beat).
- **infra-2 (W-a9b5e763)**: the duty-holder for the code: the measure script's hook into `--check`, L1's ceiling
  check and L2's refusal.
- **The coordinator**: merges each phase and renders the corpus at merge (D-874). It holds the edit freeze on a
  command while that command's phase runs.
- **The Opus + Fable panel and the review seats**: the automated consumers of the ledger. They audit vanished
  sentences and weakened rules.
- **Later `/fabrik-command-improve` runs**: the consumer of the standing gate. Every edit after the program passes
  the ledger and the ceiling.

## Problem

The `/fabrik-*` corpus grew 2.7× in ten weeks, and the loop that edits it only adds text. The operator's
words (D-1216): "very long, complex and not lean … taking too much time to execute them." The measurements
below were taken on 2026-10-25 from `~/.claude/commands/*.md` (rendered) and
`~/.claude/state/command-feedback.jsonl` (4,465 rows; 3,682 `done` closes since 2026-09-21).

| Command | Rendered words | Lines | Runs | Median min | Hours | Median Mtok/run |
|---|---|---|---|---|---|---|
| `/fabrik-review` | 27,571 | 946 | 947 | 32 | 743 | 30.3 |
| `/fabrik-task` | 8,714 | 611 | 510 | 51 | 558 | 53.4 |
| `/fabrik-review-scoped` | 9,551 | 491 | 1,120 | 21 | 534 | 18.4 |
| `/fabrik-execute-plan` | 21,366 | 1,622 | 127 | 97 | 496 | 113.9 |
| `/fabrik-spec` | 19,105 | — | 148 | 19 | 161 | 28.8 |
| `/fabrik-command-improve` | 10,536 | 712 | 302 | 18 | 151 | 18.8 |
| `/fabrik-plan-review` | 23,211 | — | 156 | 45 | 146 | 49.7 |
| `/fabrik-plan-after-chat` | 21,575 | — | 131 | 49 | 117 | 67.2 |
| `/fabrik-spec-review` | 20,672 | — | 77 | 46 | 86 | 53.8 |

The four top rows account for 2,331 of the 3,072 hours. The installed `/fabrik-*` render (from master) totals 577,205
words over 38 files. Master's 40 sources render 40 commands in all, `design-review` and `hibernate` included;
this branch, cut before `/fabrik-reverse-engineer` landed, holds 39. Of the 35,892 fragment words, three fragments hold 18,371:
`review-probe-catalogue`, `term-coverage` and `term-edit`. Rendered `/fabrik-review` carries 129 citations of 42
distinct decision ids and 23 mentions of 12 distinct dates. Among the 3,682 `done` closes since 09-21, the
`change:` axis reads 2,449 `accurate` against 220 `lean`.

**External grounding.** Each item below was fetched on 2026-10-25 by a `fabrik-researcher` seat. All three
pages were read with `exa web_fetch`; IFScale was first located by `WebSearch`.
- Anthropic's skill guidance: "Keep the `SKILL.md` body under 500 lines for optimal performance". It also says
  "Claude reads `SKILL.md` only when the Skill becomes relevant, and reads additional files only as needed",
  that "every token competes with conversation history", and asks of each paragraph "Does this paragraph justify
  its token cost?"
  (https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).
- IFScale: "even the best frontier models only achieve 68% accuracy at the max density of 500 instructions"
  (https://arxiv.org/abs/2507.11538).
- Anthropic's "Prompting best practices" page (formerly the Claude 4 page; its URL is unchanged) recommends giving a one-clause reason ("…so never use ellipses since
  the text-to-speech engine will not know how to pronounce them") and "Tell Claude what to do instead of what not
  to do". It never recommends narrating a rule's history
  (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-4-best-practices).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "every /fabrik-* command at half its rendered size or less" | IN | § Target |
| I2 | "WITHOUT losing a rule" (D-331) | IN | § The rule test |
| I3 | "proven by a before/after rule test per command … no byte count as the measure" | IN | § The rule test |
| I4 | "longest and most-run first: /fabrik-review, /fabrik-task, /fabrik-review-scoped, then the rest" | IN | § Order. The panel moved `/fabrik-review-scoped` first, as the pilot, and the shared fragments ahead of `/fabrik-review` |
| I5 | "/fabrik-command-improve may land only an edit that keeps or shrinks the rendered size" | IN | § Loop changes L1 |
| I6 | "the FEEDBACK form gains a required 'what could be removed' field" | IN | § Loop changes L2 |
| I7 | "measure the RENDERED text plus everything it orders read" (cobra, D-253) | IN | § The measure |
| I8 | "governance-sync paths, so the full /fabrik-review" | IN | § Review and landing |
| I9 | "intel will send you a per-phase time breakdown" (W-0a91bf86) | IN | § Order, an input to the per-command cut |
| I10 | "The speed items (W-1fb11ec8 and its parts) count as the same program" (D-1216) | OUT-OF-SCOPE | They are W-1fb11ec8's own items. This spec cuts text, not machinery |
| I11 | infra-2's preview-first lane clause, W-a0a32de2 | IN | § Order: lands first, and the rewrite carries it under the rule test |
| I12 | "the 2026-09-21 byte-cut program is the anti-pattern" (D-330) | IN | § Rejected alternatives R1 |
| I13 | coordinator: the L1/L2 code is the existing item W-a9b5e763 (infra-2) | IN | § Loop changes |
| I14 | "ALL OTHER BUILDER WORK PAUSES UNTIL IT IS FINISHED" (D-1216) | IN | § Program holds |
| I15 | "/fabrik-command-improve runs are PAUSED until the loop is changed" (D-1216) | IN | § Program holds |
| I16 | "kaizen is not doing its work properly" (D-1216) | IN | § Loop changes: L1 and L2 change what the loop is measured on, and § Program holds lifts the improve pause only when they land |

| I17 | coordinator, relaying the complaint's TIME: "the spec must also set the seat and round budget each command may spend … with its own before/after measure: wall-clock per run" | IN | § Time budget |

Intake: 17 items. 16 are IN and 1 is OUT-OF-SCOPE (named above). None is ASK.

## Constraints Digest

| Quote | Source |
|---|---|
| this table is its project-facing rendering, kept in step, never a second truth | `.windsurf/rules/core/40-documentation.md:94` |

The command text is not code, so it is otherwise unconstrained by the ACTIVE packs. The binding constraints are
the rulings below: D-331, D-330 and D-253, plus `CLAUDE.md` § Behavior "Merge-time render only".

## Panel

On 2026-10-25 an Opus seat and a Fable seat each read this draft, author-blind and independently. Both returned
`APPROVE-WITH-AMENDMENTS` and their amendments agree, so the panel decides the design (D-1217). Every amendment
is folded into the sections below. Where the two differed in degree, both are kept:
- L1's headroom (Opus) and its split ceilings (Fable).
- The floor: Opus would accept the KILL clause, while Fable asked for a floor derived from the ledger. The
  derived floor is kept, because it is evidence, not a failure.

## Program holds

D-1216 sets two holds, and this spec names who holds each and what lifts it:
- **All other builder work pauses until the program finishes.** The coordinator holds it: it assigns no other
  builder work from the moment this program starts, including between its phases (D-874's assign job). It is
  lifted when § Binding's CLOSE-OUT is met, or when the program is killed (§ Binding, KILL). A gate or a P0 incident still goes to the coordinator, which may rule an exception and
  record it.
- **`/fabrik-command-improve` runs are paused until the loop is changed.** kaizen holds it, because it owns the
  queues (D-627): it runs no `/fabrik-command-improve`, and rows keep accumulating, so none is lost. It is lifted
  when the tooling phase (§ Order step 1: L1, L2 and the standing gate) is merged. kaizen tells the coordinator in
  the same turn.

## Target

The **halved quantity** is a command's *own text*. That is its `render` plus every kaizen-owned file in its
`reads`: any file under `commands/` (the fragments, the `commands/_agents/*.md` definition of every seat it
dispatches, and any `commands/_branches/*.md` file lever (e) creates). It also includes any file anywhere that
this program creates or grows for a command. Each command reaches at most 50% of its own-text baseline, or the
floor its ledger sets (§ Binding, KILL). A file outside `commands/` that another beat owns stays in the full
measure only.

The baseline is measured at the start of the command's own phase, never at spec approval. kaizen keeps editing
commands until then, and a ledger cut early would miss rules added later. The coordinator freezes non-program
edits to a command while its phase runs. A command meets the target only when its rule test is green at the
same commit.

Each command's **full measure** (§ The measure) is published as its baseline in the tooling phase, before any
cut. It must not grow (L1).

## The measure (anti-cobra)

`measure(cmd) = render + reads`. `render` is the words of the rendered command, fragments included. `reads` is
the words of everything else the run's agent or its seats take in because the command points at it:
1. **Every repo file path the rendered text names, whatever the verb or none.** A file the agent only WRITES is
   excluded through a declared allowlist of output-path patterns (`docs/development/reviews/*`, `<SCRATCH>/…`,
   the ledgers), never by guessing from the verb. A script the agent only runs is excluded. Each file counts
   once, at its size at the measuring commit. Only paths the render names count: a path named only inside
   another counted file does not.
2. **The agent definition of every `subagent_type` the command dispatches**, counted once per command. A seat
   loads it as its prompt whether or not the text says "read". A shared definition such as `fabrik-reviewer`
   therefore counts in every command that dispatches it. That is deliberate, because it is read once per seat.
3. **The full text of every decision row the command orders the agent to consult or apply.** A decision id kept
   only as a history marker is free, but lever (a) deletes those anyway. `docs/DECISIONS.md` as a whole and
   `CLAUDE.md` do not count, because every session loads or queries them regardless of the command.
4. **The `--help` or printed form of any script whose output the command orders the agent to read and follow.**

**Cobra:** the cheapest evasions, and what closes each:
- Moving text into a fragment, a seat definition, a lever-(e) branch file or a new kaizen doc does nothing,
  because each one is own text (§ Target).
- Moving text into another beat's reference doc grows the full measure, which L1 forbids.
- Moving text into a decision row the command cites counts the row (item 3).
- Moving text into a script's stdout ("run X and follow what it prints") counts it (item 4), and the rule test
  refuses an `enforced` carrier that only proves a printed string.
- Deleting a rule is caught by the rule test.
- Weakening a rule's wording is caught by the rule test's sentence check and the audit pair.

## The rule test

1. **Shared-file ledgers first.** Every file under `commands/` that more than one command's own text contains
   gets its own ledger, `commands/_rules/_shared/<file>.yaml`, before it is cut. That covers four routes:
   - a fragment pulled in by `{{include:`: 24 fragments today, counted over `commands/_sources/*.md`;
   - `close-feedback`, which `assemble_commands.py` appends to every render without a directive
     (`_CLOSE_FEEDBACK`, line 31);
   - a file named as a read path, such as `review-probe-catalogue`, which no render includes and six sources
     name;
   - a `commands/_agents/*.md` definition that more than one command dispatches.

   That ledger is asserted against the shared file itself, so a cut made in one command's phase cannot lose a
   rule in a command that has no ledger yet.
2. **Completeness by construction.** At the phase start a script splits the baseline own text into sentences and
   diffs them against the rewrite. **Every baseline sentence with no surviving match must be classified** as one
   of:
   - `rule:<ledger id>`: the rule is still carried elsewhere;
   - `duplicate-of:<ledger id>`;
   - `narrative`: history, an anecdote, an id or a date that binds nothing.

   Two author-blind seats (one Sonnet, one Haiku) classify the vanished sentences, and the lead adjudicates their
   union. Recall therefore does not depend on a seat noticing every rule in 27k words. A deleted sentence with no
   classification fails the test. How much rewording still counts as a surviving match is U2.
3. **The ledger.** `commands/_rules/<cmd>.yaml` holds one entry per rule unit: a step, an order, a ban, a
   threshold, a format, a refusal or a close condition. Each entry has these fields:
   - `id`;
   - `file`: the own-text file that carries it; the render by default, otherwise a `_fragments/`, `_agents/`,
     `_branches/` or read-path file (a shared ledger's `file` is always the shared file itself);
   - `section`: the heading in that file the rule must sit under;
   - `baseline`: the verbatim baseline sentence;
   - `current`: the verbatim sentence that states it now;
   - its carriers.

   Every phrase an existing pin test holds is an input. That includes pins on files that are not the render,
   such as `_agents/fabrik-reviewer.md`, `review-probe-catalogue.md` and `.claude/workflows/*.js`. A pinned phrase
   with no entry is a rule that was missed, and it is added. A pin on a file that is not own text keeps its test.
4. **Carriers.** Every entry has at least one of these:
   - `text: [<phrase>, …]`: each phrase must sit inside the sentence equal to `current`, under `section`, in
     `file`.
   - `ordered: [<id>, …]`: the named rules appear in this order. Use it for step sequences and close orders.
   - `forbidden: [<phrase>, …]`: an absence pin, for wording that must stay gone. Absence pins are never retired.
   - `enforced: <test node id>`: valid only under three conditions:
     - the test proves a REFUSAL (a non-zero exit or an absent side effect), using the call shape the command
       actually issues;
     - the refusal fires at the step that forms the input, never only at the close;
     - a `text` carrier names the invocation and shows one correct example, so the agent still knows to call the
       script and what passes.

     A test that asserts a printed string is a text pin, and the ledger loader refuses it.
5. **The test.** `tests/test_command_rules.py` renders the corpus itself, with
   `render(tmp_path, None, agents_dest=tmp_path / "_agents")`, the pattern `tests/test_assemble_agents_dest.py`
   uses. It then asserts every ledger against that render and the files the ledgers name, and prints each
   ledger's entry count. It never reads
   `--check`'s directory, which `check()` deletes on exit (`assemble_commands.py:1323`, `:1382`). A failed carrier
   is a LOSS, and the test is red. Because `current` is stored, any later reword shows up as a ledger diff the
   reviewer must read. The audit pair inside the command's full `/fabrik-review` also reports any `current` that
   is weaker than its `baseline`. For example, the positive lever must not drop a ban: a NEVER clause keeps its
   NEVER as a `text` phrase.
6. **Standing gate.** `assemble_commands.py --check` calls the same ledger function on its own temp render before
   that directory is deleted. It runs for every edit to a ledgered command, `/fabrik-command-improve`'s included.
   It is the edit contract, not a one-off. A render that fails stops `--check` before the gate can run: 2 for
   collected render errors, 1 for a render defect raised as `SystemExit("<msg>")`. On a finished render the
   gate runs BEFORE the drift comparison. When several fire, the exit is the first that applies in this order:
   - 4: a LOSS;
   - 5: a `render` ceiling breach (L1);
   - 1: drift.

   So a mid-rewrite drift never masks a LOSS.
7. **Retiring pins.** A presence pin whose rule is now a ledger entry is deleted in the same commit. Absence pins
   become `forbidden:` carriers or stay.
8. **A rule removed on purpose** needs a D-row that names its ledger id, and the entry moves to a `retired:`
   list. It is never deleted silently.
9. **The tail.** A command outside the top four (741 of the 3,072 hours since 09-21, combined) may use the light
   form. Every rule still gets a ledger entry and the standing gate. In the light form:
   - a rule whose baseline sentence survives unchanged gets its entry generated by script, as a `text` carrier
     copied from that sentence;
   - the seats classify only the vanished sentences and write carriers only for reworded rules.

## Time budget (seats and rounds)

The operator's complaint is time. intel's table (U4) puts the minutes in seat time and rounds, not in reading
the text. So each rewrite ticket for a review-family command (`/fabrik-review`, `/fabrik-review-scoped`,
`/fabrik-task`'s nested review, `/fabrik-execute-plan`'s phase reviews) carries a second, independent
before/after measure. That measure and its levers are set out below.

- **The measure** is intel's W-0a91bf86 method: its scripts, kept with that receipt, re-run per command over
  `done` runs. It has three parts:
  - wall-clock per run (median and p90);
  - seat-minutes per run (the idle-gap-cut figure);
  - rounds per run.

  The before value is the window ending at the phase start. The after value is the first 14 days after the
  merge. **Target:** the median wall-clock per run at or below 50% of its baseline for the top four commands.
  It is reported per command and is not a gate, because a run's length also moves with its surface.
- **The levers are rule changes, never rule losses.** Seat counts, slice sizing and pass shapes are standing
  rulings:
  - D-206: the exit counter, with no round ceiling;
  - D-208: the seat floor;
  - D-335: the delta pass is the round-1 seats on their own slices;
  - D-344: the Sonnet plus Haiku finder pair;
  - D-355, the operator's: "this is a target not cap. if the checks/reviews finished prematurely, it will not
    help at all".

  A ticket may propose changing one. The change is a new D-row superseding that ruling, decided by the Opus +
  Fable panel per change and recorded in the ledger's `retired:` list against the entries it rewrites. It is
  never a silent cut. **No lever caps the round count** (D-355). The levers a ticket may propose are:
  - **T1, seats per slice:** one finder per slice instead of the D-344 pair, where intel's data shows the
    second seat confirms nothing the first missed.
  - **T2, the closing pass:** it re-runs only the open claims' commands. A slice with no open claim is restated,
    not re-dispatched, which is D-335 as written; the rewrite states it once, plainly.
  - **T3, no double review:** `/fabrik-task`'s phase 4 nested review is the run's only review pass. It is never
    repeated by the parent.
  - **T4, briefs:** a seat brief carries the question and the pin, never the command's own rules. Seats read
    less, and the brief-writing time drops.
  - **T5, per-round obligations:** the lead's per-round steps (hygiene, pins, md5 pairs, ledger rows) are
    scripted where a script exists, and stated once.
- **Cobra:** the cheapest way to halve wall-clock is to stop reviews early. The counter is defects found later
  on the same surface. For 14 days after landing, the confirmed findings that later reviews make on files a
  fast review closed are compared with the baseline window's rate. A rise flags the lever, and the panel
  revisits it.

## How a command is cut (the rewrite rules)

Each lever keeps the rule:
- **(a) Remove narrative.** Incident stories, dates, mail ids, "measured: …" anecdotes and decision ids cited as
  history all go (D-331). Keep a narrative clause only when it is the rule's one-clause reason, the sentence that
  defines the class the rule covers. For example, keep "a grader constructs the rows it needs, so it only tests
  the branch the author imagined", and drop the measured anecdote around it.
- **(b) State a rule once.** A rule stated in more than one place in one render keeps one statement. A rule in a
  fragment is never merged with one in the source, because they sit in different ledgers.
- **(c) Let a tool enforce a format**, only under the `enforced` carrier's conditions above: the refusal fires
  where the input is formed, and the text keeps the invocation plus one correct example. A refusal that fires
  only at the close stays as text, because a wrong form found at close costs a whole re-close.
- **(d) Write positive imperatives with a one-clause reason**, per the Anthropic guidance above. A NEVER or
  refusal clause keeps its ban verbatim.
- **(e) Load only what the run needs.** A branch most runs never take may move into a `commands/_branches/*.md`
  file that the command reads on that branch only. It is own text, so this lever buys clarity, not score.

## Loop changes

- **L1: the size ratchet.** `commands/_size_ceiling.json` holds two ceilings per command:
  - `render`: the own-text measure plus 3% headroom. It ratchets down on every shrink, and raising it needs a
    D-row. A shared seat definition that grows counts against every command that dispatches it.
  - `reads`: the frozen set of paths outside `commands/`, with their total. A kaizen edit that ADDS a path to the
    set needs a D-row naming it. A file in the set that grows for its owner's own reasons never fails `--check`.
    It is printed as a report line, and kaizen reviews it at the next phase close (U3).

  `assemble_commands.py --check` exits 5 on a `render` ceiling breach, after the ledger gate has passed, so no
  render is paid for by deleting a rule.

  Before a command's own phase, `/fabrik-command-improve` may not grow it. An edit that would grow it is queued to
  that phase, not paid for with deletions. The `/fabrik-command-improve` text says that an edit must fit its
  ceiling and pass the ledger. Three kinds of addition are exempt from that queueing:
  - the program's own landed text: the `remove:` wording and the ceiling sentence;
  - a clause landed under a D-row, such as infra-2's lane clause (W-a0a32de2);
  - a P0 fix.

  The exempt text is then part of the baseline its command's phase measures.

  **Cobra:** the cheapest pass is deleting a rule to make room, which the ledger gate stops. The second cheapest
  is D-row inflation to raise ceilings, which kaizen counts from the ceiling file's git log (§ Lifecycle).
- **L2: the remove field.** The FEEDBACK verdict gains a fifth required field: `remove: "<a sentence quoted
  verbatim from the rendered command>" | none`. `command_run.py` refuses a quote that is absent from the render.
  The digest groups `remove:` rows by phrase, so N runs naming one sentence become a deletion candidate with
  evidence. `/fabrik-command-improve` treats a candidate as a ledger check, never as permission to delete. This is
  the only new close grammar the program adds.
  **Cobra:** `remove: none` everywhere. kaizen reads that ratio as the loop's lean signal (§ Lifecycle).
- L1's checker, L2's refusal and the ledger gate's hook into `--check` are code in infra's beat
  (`assemble_commands.py`, `command_run.py`). They land as the plan's infra tickets under the existing item
  W-a9b5e763 (infra-2, blocked by this spec), and the plan mints no second item. The command wording that names
  them is kaizen's: the `close-feedback` fragment and the `/fabrik-command-improve` source.

## Order

Each item is one plan phase, one full `/fabrik-review` and one merge by the coordinator:
1. **Tooling.** It delivers:
   - the sentence diff and the ledger loader;
   - the measure script;
   - `test_command_rules.py` and the standing gate;
   - L1 and L2 (W-a9b5e763);
   - every command's full-measure baseline, published.
2. **Pilot: `/fabrik-review-scoped`** (1,120 runs, 9,551 words, about a third of `/fabrik-review`'s size). The
   fragments it includes are `no-workflow-hub`, `run-record`, `orient`, `scope-growth-exit` and `close-chain`,
   plus the auto-appended `close-feedback`. It also reads `review-probe-catalogue` and dispatches the
   `fabrik-reviewer`, `fabrik-researcher` and `fabrik-gui` definitions. Every one of those that
   another command's own text also contains gets its ledger in this phase, before the pilot cuts it: all but
   `scope-growth-exit`. The pilot shakes out the YAML grammar, the audit pair and
   the ceilings.
3. **The remaining shared files**: every one § The rule test step 1 names that the pilot did not cover, the
   fragments `term-coverage`, `term-edit` and `subagents-core` among them.
4. **`/fabrik-review`.** The review that reviews every later phase lands only after the pilot has proven the
   tooling.
5. `/fabrik-task`, `/fabrik-execute-plan`, `/fabrik-command-improve`.
6. The rest, in descending order of hours, in the light form.

intel's per-phase time table (W-0a91bf86) picks the sections each command cuts hardest. infra-2's lane clause
(W-a0a32de2) lands before the commands it touches are rewritten, and the rewrite carries it.

## fabrik-lib verdict

| Capability | Verdict | Module | Why |
|---|---|---|---|
| Sentence diff and classification table | build | none | Hub-internal tooling over the command corpus. No `/opt/fabrik-lib/README.md` module diffs prose or holds a rule ledger. The nearest, `claude-evaluator/`, scores items and does not diff them. |
| Rule ledger loader and `test_command_rules.py` | build | none | It reads hub-only paths (`commands/_rules/`) and is consumed by `assemble_commands.py`. No project reuses it, so it is not proposed as a module. |
| The measure and the L1 ceilings | build (extends `commands/assemble_commands.py`) | none | It extends the renderer that already owns `--check`. |
| L2's quoted `remove:` refusal | build (extends `scripts/command_run.py`) | none | It extends the close that already refuses the other four fields. |

## Lifecycle

kaizen holds every duty in this section. It reads each trigger at its daily read of the kaizen instrument's
digest (the charter's § Beat: "you read the same numbers daily"), and each trigger that fires opens a kaizen work item (`work.py add`)
naming the command and carrying the value as evidence. The triggers, each with its source:
- **Ledger size.** A command whose ledger passes 300 entries does too much: it is split, not trimmed. The source
  is the entry count `test_command_rules.py` prints per ledger.
- **The TRIPWIRE** in § Binding. The source is `command-feedback.jsonl`'s `wall_s` and token fields, per command,
  over `done` closes.
- **Ceiling raises.** A command raises its `render` ceiling twice in 30 days. The source is `git log -p --
  commands/_size_ceiling.json`, counting increases per command, since the file holds only the current value.
- **Rote `remove:` answers.** After L2 lands, the `remove: none` share of all closes stays above 90% for 14
  consecutive days, which means the field is answered by rote. The source is `command-feedback.jsonl`'s `remove`
  field, and the denominator is every close row of the day.

Two more duties, and who holds them:
- **Retirement.** A command retired from the corpus takes its ledger and ceiling row with it, in the same commit.
  kaizen does this.
- **Documentation.** When the tooling phase lands, `docs/reference/command-corpus-check.md` (the corpus
  integrity gate's doc) gains a "Rule ledger and size ceiling" section, and its `INDEX.md` row is updated, by
  infra-2 under W-a9b5e763. No second doc is created. kaizen edits its own charter's Method step 3 to name the
  ledger gate.

## Review and landing

Every command source is a governance-sync path, so every phase owes the full `/fabrik-review`, whose seats
include the rule test's audit pair. The worktree never renders; the coordinator renders the corpus at merge.

## Rejected alternatives

- **R1 — a byte cut with existing graders as the loss check** (the 2026-09-21 program, D-330). It passed every
  grader and lost 21 ungraded rules, because graders only cover what someone pinned.
- **R2 — a word cap alone.** It invites the fragment and reference-doc evasion and says nothing about loss.
- **R3 — progressive disclosure scored at firing frequency.** It needs per-branch telemetry that does not exist
  and rewards moving rules out of sight. Lever (e) stays, unscored.
- **R4 — a seat-extracted rule list as the only completeness proof** (this draft's first version). Recall rests
  on a seat reading 27k words. The sentence diff makes completeness mechanical (both panel seats).
- **R5 — halving the full measure.** That would mean cutting infra's and docs' reference files, which belong to
  other beats. The own-text quantity is halved, and the full measure must not grow.

## Residual unknowns

Resolved:
- the halved quantity: own text, not the full measure (R5);
- the first target: the pilot is `/fabrik-review-scoped`;
- who owns the code: W-a9b5e763.

Still open, each with its resolution step:
- **U1 — the words-per-rule figure behind the floor** is unknown until the pilot lands. The resolution: the
  pilot's own words per rule, recorded by kaizen in the pilot phase's D-row, is used until any command reaches
  50%; from then on it is the median over the commands that reached 50% (§ Binding, KILL).
- **U2 — the sentence matcher's tolerance.** How much rewording still counts as "surviving" is set at the
  tooling phase. It is probed against the pilot's baseline with both an over-matching case (a reworded ban read
  as surviving) and an under-matching case (an unchanged sentence read as vanished), and recorded with the
  tooling.
- **U3 — whether infra's reference docs grow** while the program runs. They are reported against the frozen
  `reads` set, never blocked (L1). kaizen reviews the report lines at each phase's close and mails the owning
  beat when a grown doc is a candidate for its own lean pass.
- **U4 — intel's per-phase time table (W-0a91bf86)** — RESOLVED 2026-10-25. The table is
  `docs/development/reviews/2026-10-25-w-0a91bf86-lean-program-phase-wall-clock.md` on branch `intel-w0a91bf86`.
  - Seats run for 53-64% of a full review's wall-clock and 67-73% of a scoped review's. A `/fabrik-task` run is
    60% its nested review.
  - The median run is 3 rounds. Each round after the first adds 5.9 min (review) or 4.1 min (scoped).
  - The command text is 2.7% of a task or scoped run's cache reads, and 7.9% of a full review's.

  So the text cut buys most of its time indirectly: fewer steps and rules for the lead and the seats to follow,
  and fewer rounds. Prefix tokens buy little. Each rewrite ticket therefore cuts hardest where the text drives
  rounds and seat work: the termination contract, the seat briefs and the per-round obligations. The TRIPWIRE
  stays as written; a run that does not get faster flags that cut.

## § Binding (ONE-WAY: every command, fleet-wide)

CLASS: one-way. Every project's rendered commands change, and the ledger becomes the standing edit contract.
BUDGET: the 40 commands master renders today, and any added before the program closes. The pilot and the top four take one session each; the tail uses the light
form.
KILL: there is no per-command KILL. A command that cannot reach 50% without a LOSS stops at a **recorded floor**,
written as a D-row: its live rule count × the words-per-rule figure U1 defines.
The program as a whole is killed if the pilot cannot reach 60% of its own-text baseline with a green rule test.
CONFIDENCE: medium. Both panel seats estimated `/fabrik-review` at 40-65% of its render from a dense sample, so
a floor near 55-60% is likely there.
COUNTER: the ledger's own size. Its YAML is not rendered and costs no run tokens; the measure counts none of it.
TRIPWIRE: within 2 weeks of a command landing, EITHER its median wall-minutes OR its median Mtok per run (both
from `command-feedback.jsonl`, `done` closes) has failed to fall.
CLOSE-OUT: every command at or under 50% of its own text, or at a recorded floor; the full measure not grown;
L1, L2 and the standing ledger gate live; `remove:` rows flowing.
