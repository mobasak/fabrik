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

The four top rows account for 2,331 of the roughly 3,100 hours. The corpus totals 577,205 rendered words over 38
commands. Of the 35,892 fragment words, three fragments hold 18,371: `review-probe-catalogue`, `term-coverage`
and `term-edit`. Rendered `/fabrik-review` cites 129 decision ids and 23 dates. Since 09-21 the `change:` axis
reads 2,621 `accurate` against 235 `lean`.

**External grounding.** Each item below was fetched on 2026-10-25 by a `fabrik-researcher` seat. All three
pages were read with `exa web_fetch`; IFScale was first located by `WebSearch`.
- Anthropic's skill guidance: "Keep the `SKILL.md` body under 500 lines for optimal performance". It also says
  "Claude reads `SKILL.md` only when the Skill becomes relevant, and reads additional files only as needed",
  that "every token competes with conversation history", and asks of each paragraph "Does this paragraph justify
  its token cost?"
  (https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).
- IFScale: "even the best frontier models only achieve 68% accuracy at the max density of 500 instructions"
  (https://arxiv.org/abs/2507.11538).
- Anthropic's Claude 4 prompting guidance recommends giving a one-clause reason ("…so never use ellipses since
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

Intake: 13 items. 12 are IN and 1 is OUT-OF-SCOPE (named above). None is ASK.

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

## Target

The **halved quantity** is a command's *own text*: its rendered words plus the kaizen-owned files it reads (the
fragments already expanded, and the `commands/_agents/*.md` definition of every seat it dispatches). Each
command reaches at most 50% of its own-text baseline, or the floor its ledger sets (§ Binding, KILL).

The baseline is measured at the start of the command's own phase, never at spec approval. Kaizen keeps editing
commands until then, and a ledger cut early would miss rules added later. Non-program edits to a command are
frozen while its phase runs. A command meets the target only when its rule test is green at the same commit.

Each command's **full measure** (§ The measure) is published as its baseline before any cut. It must not grow
(L1).

## The measure (anti-cobra)

`measure(cmd) = render + reads`. `render` is the words of the rendered command (fragments included). `reads` is
the words of everything else the run's agent or its seats take in because the command points at it:
1. **Every repo file path the rendered text names, whatever the verb or none.** A file the agent only WRITES is
   excluded through a declared allowlist of output-path patterns (`docs/development/reviews/*`, `<SCRATCH>/…`,
   the ledgers), never by guessing from the verb. A script the agent only runs is excluded. Each file counts
   once, at its size at the measuring commit, closed one level deep.
2. **The agent definition of every `subagent_type` the command dispatches**, once per command. A seat loads it
   as its prompt whether or not the text says "read".
3. **The full text of every decision row the command orders the agent to consult or apply.** A decision id kept
   only as a history marker is free, but lever (a) deletes those anyway. `docs/DECISIONS.md` as a whole and
   `CLAUDE.md` do not count, since every session loads or queries them regardless of the command.
4. **The `--help` or printed form of any script whose output the command orders the agent to read and follow.**

**Cobra:** the cheapest evasions and what closes each:
- Moving text into a fragment, a seat definition or a reference doc does nothing, because each counts.
- Moving text into a decision row the command cites counts the row (item 3).
- Moving text into a script's stdout ("run X and follow what it prints") counts it (item 4), and the rule test
  refuses an `enforced` carrier that only proves a printed string.
- Deleting a rule is caught by the rule test.
- Weakening a rule's wording is caught by the rule test's sentence check and the audit pair.

## The rule test

1. **Fragment ledgers first.** A fragment rendered into more than one command gets its own ledger,
   `commands/_rules/_fragments/<frag>.yaml`, built and landed before that fragment is cut. That ledger is asserted
   against every render that includes the fragment, so a cut made in one command's phase cannot lose a rule in
   another command that has no ledger yet.
2. **Completeness by construction.** At the phase start a script splits the baseline render into sentences and
   diffs them against the rewrite. **Every baseline sentence with no surviving match must be classified**:
   - `rule:<ledger id>`, where the rule is still carried elsewhere;
   - `duplicate-of:<ledger id>`;
   - `narrative`, meaning history, an anecdote, an id or a date that binds nothing.

   Two author-blind seats (one Sonnet, one Haiku) classify the vanished sentences and the lead adjudicates their
   union. Recall therefore does not depend on a seat noticing every rule in 27k words. A deleted sentence with no
   classification fails the test.
3. **The ledger.** `commands/_rules/<cmd>.yaml` holds one entry per rule unit (a step, an order, a ban, a
   threshold, a format, a refusal or a close condition), with these fields:
   - `id`
   - `section`: the heading the rule must sit under
   - `baseline`: the verbatim baseline sentence
   - `current`: the verbatim sentence that states it now
   - its carriers

   Every phrase an existing pin test holds is an input. A pinned phrase with no entry is a rule that was missed,
   and it is added.
4. **Carriers.** Every entry has at least one:
   - `text: [<phrase>, …]`: each phrase must sit inside the sentence equal to `current`, under `section`.
   - `ordered: [<id>, …]`: the named rules appear in this order, for step sequences and close orders.
   - `forbidden: [<phrase>, …]`: an absence pin. Wording that must stay gone. Absence pins are never retired.
   - `enforced: <test node id>`: valid only with three conditions. The test proves a REFUSAL (a non-zero exit or
     an absent side effect), using the call shape the command actually issues. The refusal fires at the step
     that forms the input, never only at the close. And a `text` carrier names the invocation and shows one
     correct example, so the agent still knows to call the script and what passes. A test that asserts a
     printed string is a text pin, and the ledger loader refuses it.
5. **The test.** `tests/test_command_rules.py` asserts every ledger against a temp render. It reads the render
   from `assemble_commands.py --check`'s temp directory and tolerates that command's drift exit code, which is
   expected mid-rewrite. A failed carrier is a LOSS, and the test is red. Because `current` is stored, any later
   reword shows up as a ledger diff the reviewer must read. The audit pair inside the command's full
   `/fabrik-review` also reports any `current` that is weaker than its `baseline`. For example, the positive
   lever must not drop a ban: a NEVER clause keeps its NEVER as a `text` phrase.
6. **Standing gate.** After the program the ledger test runs inside `assemble_commands.py --check` for every
   edit to a ledgered command, `/fabrik-command-improve`'s included. It is the edit contract, not a one-off.
7. **Retiring pins.** A presence pin whose rule is now a ledger entry is deleted in the same commit. Absence pins
   become `forbidden:` carriers or stay.
8. **A rule removed on purpose** needs a D-row that names its ledger id, and the entry moves to a `retired:`
   list. It is never deleted silently.
9. **The tail.** Commands outside the top four (under 400 hours combined) may use the light form: steps 1, 2 and
   7 only. The sentence classification table is the rule test, and `text` carriers are written only for the
   rules whose sentences were reworded.

## How a command is cut (the rewrite rules)

Each lever keeps the rule:
- **(a) Remove narrative.** Incident stories, dates, mail ids, "measured: …" anecdotes and decision ids cited as
  history all go (D-331). Keep a narrative clause only when it is the rule's one-clause reason, the sentence
  that defines the class the rule covers. For example, keep "a grader constructs the rows it needs, so it only
  tests the branch the author imagined", and drop the measured anecdote around it.
- **(b) State a rule once.** A rule stated in more than one place in one render keeps one statement. A rule in a
  fragment is never merged with one in the source, because they sit in different ledgers.
- **(c) Let a tool enforce a format**, only under the `enforced` carrier's conditions above: the refusal fires
  where the input is formed, and the text keeps the invocation plus one correct example. A refusal that fires
  only at the close stays as text, because a wrong form found at close costs a whole re-close.
- **(d) Write positive imperatives with a one-clause reason**, per the Anthropic guidance above. A NEVER or
  refusal clause keeps its ban verbatim.
- **(e) Load only what the run needs.** A branch most runs never take may move into a file the command reads on
  that branch only. It still counts in the measure, so this lever buys clarity, not score.

## Loop changes

- **L1 — the size ratchet.** `commands/_size_ceiling.json` holds two ceilings per command:
  - `render`: the new own-text measure plus 3% headroom. It ratchets down on every shrink, and raising it needs
    a D-row.
  - `reads`: the frozen set of paths plus their total. A grown or added file needs a D-row naming it. Each
    ordered-read doc's own size belongs to its beat, so an infra doc growing for its own reasons does not block
    a command render; it is reported.

  `assemble_commands.py --check` fails a render over either ceiling, and only after the ledger test passes, so a
  render cannot be paid for by deleting a rule. A command with no ledger yet refuses additions outright: they are
  queued to its phase rather than paid for with deletions. `/fabrik-command-improve`'s text says that an edit must
  fit its ceiling and pass the ledger.
  **Cobra:** the cheapest pass is deleting a rule to make room, which the ledger gate stops. The second cheapest is
  D-row inflation to raise ceilings, which the digest lists by command.
- **L2 — the remove field.** The FEEDBACK verdict gains a fifth required field: `remove: "<a sentence quoted
  verbatim from the rendered command>" | none`. `command_run.py` refuses a quote that is absent from the render.
  The digest groups `remove:` rows by phrase, so N runs naming one sentence become a deletion candidate with
  evidence. `/fabrik-command-improve` treats a candidate as a ledger check, never as permission to delete. This is
  the only new close grammar the program adds.
  **Cobra:** `remove: none` everywhere. The digest reports that ratio, and kaizen reads it as the loop's lean
  signal.
- L1's checker, L2's refusal and the ledger test's hook into `--check` are code in infra's beat
  (`assemble_commands.py`, `command_run.py`). They land as the plan's infra tickets under the existing item
  W-a9b5e763 (infra-2, blocked by this spec), and the plan mints no second item. The command wording that names
  them is kaizen's: the `close-feedback` fragment and the `/fabrik-command-improve` source.

## Order

Each item is one plan phase, one full `/fabrik-review` and one merge by the coordinator:
1. **Tooling:** the sentence-diff and ledger loader, the measure script, `test_command_rules.py`, and L1 and L2
   (W-a9b5e763). Every command's full-measure baseline is published.
2. **Pilot: `/fabrik-review-scoped`** (1,120 runs, 9,551 words, the same fragments). It shakes out the YAML
   grammar, the audit pair and the ceilings at a third of `/fabrik-review`'s size.
3. **Shared fragments**, with fragment ledgers asserted in every including render: `term-coverage`, `term-edit`,
   `subagents-core`, `review-probe-catalogue`, `close-chain`, `close-feedback` and `orient`.
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

- **Growth:** the ledgers grow with the rules. A command whose ledger passes about 300 entries is a signal that the
  command does too much, and it is split, not trimmed.
- **Escalation triggers, measured from `command-feedback.jsonl` and the ceiling file:**
  - the TRIPWIRE in § Binding;
  - a command raising its `render` ceiling twice in 30 days;
  - the `remove: none` ratio staying above 90% for two weeks after L2 lands, which means the field is answered
    by rote.

  Each trigger opens a kaizen work item naming the command.
- **Retirement:** a command retired from the corpus takes its ledger and ceiling row with it, in the same commit.
- **Documentation:** this spec. When the tooling phase lands, `docs/reference/command-corpus-check.md` (the
  corpus integrity gate's doc) gains a "Rule ledger and size ceiling" section and its `INDEX.md` row is updated;
  no second doc is created. The kaizen charter's Method step 3 names the ledger gate.

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
- **U1 — the words-per-rule figure behind the floor** is unknown until the pilot lands. The resolution is the
  pilot's measured median, recorded in its phase's D-row.
- **U2 — the sentence matcher's tolerance.** How much rewording still counts as "surviving" is set at the
  tooling phase. It is probed against the pilot's baseline with both an over-matching case (a reworded ban read
  as surviving) and an under-matching case (an unchanged sentence read as vanished), and recorded with the
  tooling.
- **U3 — whether infra's reference docs grow** while the program runs. They are reported against the frozen
  `reads` set, never blocked (L1). They are reviewed at each phase's close.
- **U4 — intel's per-phase time table (W-0a91bf86)** is not yet received. It only orders the cuts inside a
  command, and no design element depends on it.

## § Binding (ONE-WAY: every command, fleet-wide)

CLASS: one-way. Every project's rendered commands change, and the ledger becomes the standing edit contract.
BUDGET: about 30 commands. The pilot and the top four take one session each; the tail uses the light form.
KILL: no KILL per command. A command that cannot reach 50% without a LOSS stops at a **recorded floor** derived
from its ledger (its live rule count × the median words per rule of the commands that reached 50%), written as a
D-row. The program is killed if the pilot cannot reach 60% of its own-text baseline with a green rule test.
CONFIDENCE: medium. Both panel seats estimated `/fabrik-review` at 40-65% of its render from a dense sample, so
a floor near 55-60% is likely there.
COUNTER: the ledger's own size. Its YAML is not rendered and costs no run tokens; the measure counts none of it.
TRIPWIRE: median wall-minutes AND median Mtok per run, both from `command-feedback.jsonl`, fail to fall within 2
weeks of a command landing.
CLOSE-OUT: every command at or under 50% of its own text, or at a recorded floor; the full measure not grown;
L1, L2 and the standing ledger gate live; `remove:` rows flowing.
