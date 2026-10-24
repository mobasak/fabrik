# Lean command corpus — half the size, no rule lost

Status: DRAFT
Profile: full
Size: large
Work item: W-96f36043 (P0) · Decision: D-1216 · Author: kaizen · 2026-10-25

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

**External grounding.** Each item below was fetched on 2026-10-25 by a `fabrik-researcher` seat through exa.
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
| I4 | "longest and most-run first: /fabrik-review, /fabrik-task, /fabrik-review-scoped, then the rest" | IN | § Order |
| I5 | "/fabrik-command-improve may land only an edit that keeps or shrinks the rendered size" | IN | § Loop changes L1 |
| I6 | "the FEEDBACK form gains a required 'what could be removed' field" | IN | § Loop changes L2 |
| I7 | "measure the RENDERED text plus everything it orders read" (cobra, D-253) | IN | § The measure |
| I8 | "governance-sync paths, so the full /fabrik-review" | IN | § Review and landing |
| I9 | "intel will send you a per-phase time breakdown" (W-0a91bf86) | IN | § Order, an input to the per-command cut |
| I10 | "The speed items (W-1fb11ec8 and its parts) count as the same program" (D-1216) | OUT-OF-SCOPE | They are W-1fb11ec8's own items. This spec cuts text, not machinery; § Order names the hand-off |
| I11 | infra-2's preview-first lane clause, W-a0a32de2 | IN | § Order: lands first, and the rewrite carries it under the rule test |
| I12 | "the 2026-09-21 byte-cut program is the anti-pattern" (D-330) | IN | § Rejected alternatives R1 |

Intake: 12 items. 11 are IN and 1 is OUT-OF-SCOPE (named above). None is ASK.

## Constraints Digest

| Quote | Source |
|---|---|
| this table is its project-facing rendering, kept in step, never a second truth | `.windsurf/rules/core/40-documentation.md:94` |

The command text is not code, so it is otherwise unconstrained by the ACTIVE packs. The binding constraints are
the rulings below: D-331, D-330 and D-253, plus `CLAUDE.md` § Behavior "Merge-time render only".

## Target

Every rendered `/fabrik-*` command is at most 50% of its baseline **measure** (§ The measure). The baseline is
fixed at this spec's approval commit. A command meets the target only when its rule test (§ The rule test) is
green at the same commit.

## The measure (anti-cobra)

`measure(cmd)` is the words of the rendered command plus the words of every repo file the rendered text tells the
agent to READ. Such a file is found by a path match on a read verb (`read`, `open`, `see … for`, `follow`, `per`)
or by an `{{include:}}` already expanded. Each file counts once, at its size at the measuring commit, closed one
level deep. Files the agent only RUNS (scripts) or WRITES (ledgers) do not count. The decision ledger
`docs/DECISIONS.md` and `CLAUDE.md` do not count: they are loaded or queried by every session whatever the
command says.

**Cobra:**
- Moving text into a fragment does nothing, because the rendered text already includes it.
- Moving text into a new or grown reference doc the command orders read counts in full.
- Moving a rule into a script's refusal message counts as carried only through § The rule test's `enforced`
  carrier, which needs a test that proves the refusal fires.
- The remaining cheap evasion is **deleting a rule**, and the rule test exists to catch exactly that.
- Weakening a rule's wording until it no longer binds is caught by the seat audit (§ The rule test, step 3), not
  by the measure.

## The rule test

1. **Baseline ledger.** Before a command is rewritten, its rendered text is cut into rule units by two
   author-blind seats over the pinned baseline. A rule unit is one normative statement: a step, an order, a ban,
   a threshold, a format, a refusal or a close condition. The seats' union is adjudicated by the lead and written
   to `commands/_rules/<cmd>.yaml`, one entry per rule: `id`, the verbatim baseline sentence, and a `carrier`.
   Every phrase that an existing pin test (`tests/test_*` asserting command text) holds is an input. A pinned
   phrase with no ledger entry is a rule the seats missed, and it is added.
2. **Carriers.** Each rule is carried in one of two ways:
   - `text: [<key phrase>, …]`: one or more short phrases that must all appear in the new rendered text.
   - `enforced: <test node id>`: a test proving a script refuses or performs it. Only a rule a script already
     enforces may use this carrier.
3. **The test.** `tests/test_command_rules.py` loads each ledger and asserts every carrier against the rendered
   text from `assemble_commands.py --check`'s temp render. A rule with no carrier present is a LOSS, and the test
   is red. Then a seat audit pairs every ledger entry with the new line that states it and reports any entry whose
   new statement is weaker than the baseline sentence. It is author-blind, one Sonnet seat plus one Haiku seat,
   inside the command's full `/fabrik-review`. A weakened rule is a confirmed finding.
4. **Retiring pins.** A phrase pin whose rule is now a ledger entry is deleted in the same commit. The ledger
   replaces it, so a later rewording edits one key phrase, not N pin tests.
5. **A rule removed on purpose** needs a D-row that names the ledger id. It is never deleted silently.

## How a command is cut (the rewrite rules)

The following levers apply in order, and each keeps the rule:
- **(a) Remove narrative.** Incident stories, dates, mail ids, "measured: …" anecdotes and decision ids cited as
  the rule's history all go (D-331). A decision id stays only where the agent must consult it.
- **(b) State a rule once.** Where the same rule appears in more than one place in one rendered command, keep
  one statement.
- **(c) Let tools enforce the format.** Where a script refuses a malformed input with a message, the command
  shows the correct form once, and the refusal grammar goes. The rule's carrier becomes `enforced`.
- **(d) Write positive imperatives with a one-clause reason**, per the Anthropic guidance above.
- **(e) Load only what the run needs.** A branch most runs never take (for example `/fabrik-spec`'s epic-file
  intake) may move into a reference file the command orders read only on that branch. It still counts in the
  measure, so this lever buys clarity, not score.

## Loop changes

- **L1 — the size ratchet.** `commands/_size_ceiling.json` holds each command's measure. `assemble_commands.py
  --check` fails a render whose measure for any command exceeds its ceiling. A shrink lowers the ceiling in the
  same commit, so the ceiling only ever goes down. Raising it needs a D-row. `/fabrik-command-improve`'s PHASE
  text says that an edit answering a row must fit inside the ceiling, taking from elsewhere in the command what
  it adds. **Cobra:** the cheapest way to pass is to move the added text into a reference doc. The measure counts
  ordered reads, which closes that.
- **L2 — the remove field.** The FEEDBACK verdict gains a fifth required field, `remove: <the sentence or step
  this run did not need> | none`. `command_run.py` refuses a close without it, as it does for the other four.
  `command_feedback_report.py --queue` shows `remove:` rows first. **Cobra:** `remove: none` everywhere. The
  digest reports the ratio of `remove: none`, and kaizen reads it as the loop's lean signal.
- L1's checker and L2's refusal are code in infra's beat (`assemble_commands.py`, `command_run.py`). They land as
  plan tickets owned by infra. The command wording that names them (the `close-feedback` fragment and the
  `/fabrik-command-improve` source) is kaizen's.

## Order

Each item is one plan phase, one command, one full `/fabrik-review`, and one merge by the coordinator:
- P0 is L1 and L2 plus the ledger tooling.
- Then `/fabrik-review` with its fragments (`term-coverage`, `term-edit`, `subagents-core`,
  `review-probe-catalogue`).
- Then `/fabrik-task`, `/fabrik-review-scoped`, `/fabrik-execute-plan` and `/fabrik-command-improve`.
- The remaining commands follow in descending order of hours.

intel's per-phase time table (W-0a91bf86) picks the sections cut hardest inside each command. infra-2's lane
clause (W-a0a32de2) lands before the commands it touches are rewritten, and the rewrite carries it.

## Review and landing

Every command source is a governance-sync path, so every phase owes the full `/fabrik-review`, its seats
including the rule test's audit pair. The worktree never renders. The coordinator renders the corpus at merge.

## Rejected alternatives

- **R1 — a byte cut with existing graders as the loss check** (the 2026-09-21 program, D-330). It passed every
  grader and lost 21 ungraded rules. The ledger exists because graders only cover what someone pinned.
- **R2 — a word cap alone.** It invites the fragment and reference-doc evasion and says nothing about loss.
- **R3 — progressive disclosure scored at firing frequency** (counting a conditional read by how often its branch
  fires). It is more accurate, but it needs per-branch telemetry that does not exist, and it rewards moving rules
  out of sight. Lever (e) stays, unscored.

## § Binding (ONE-WAY: every command, fleet-wide)

CLASS: one-way. Every project's rendered commands change, and the ledger becomes the edit contract.
BUDGET: about 30 commands, the top four first, and one session per large command.
KILL: a command whose rule test cannot reach 50% without a LOSS stops at its floor, with a D-row naming the
rules that hold it there.
CONFIDENCE: medium. The narrative share is large: 129 decision ids and 23 dates in `/fabrik-review` alone.
COUNTER: the ledger's own size. Its YAML is not rendered and costs no run tokens.
TRIPWIRE: median wall-minutes per command, which `command-feedback.jsonl` reports, does not fall within 2 weeks
of a command landing.
CLOSE-OUT: every command at or under its 50% ceiling, or at a recorded floor; L1 and L2 live; `remove:` rows
flowing.
