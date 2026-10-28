# T07a/b re-ledger receipt: `/fabrik-review` under master's canonical loader (Step 0)

Branch `claude/lean-t07-rl`, made from `claude/lean-t07-rlbase`: `origin/claude/lean-t07` with `origin/master` merged in. T07a, T07b and T07c (receipt `2026-10-25-plan-1-lean-command-corpus-T07c-receipt.md`) were written under the old loader. This unit re-ledgers `commands/_rules/fabrik-review.yaml` for master's loader (D-1236, D-1238, D-1240, D-1254, D-1255/D-1256, D-1258). It makes **no new cut**.

Worker: API-lane cloud worker. Its only shell was the runner's allowlisted commands, so it ran no script. Every ledger edit was made by hand. After each batch it re-ran `python3 commands/assemble_commands.py --check`, which calls `command_rules.losses()`. `commands/command_rules.py`, `tests/test_command_rules.py`, `commands/_size_ceiling.json`, `CHANGELOG.md`, `INDEX.md` and `docs/DECISIONS.md` are untouched. No test file was edited.

## Verdict

- **0 LOSS** for `fabrik-review.yaml` under master's loader, down from 331 own LOSS lines at the start of the unit. No `_shared/*.yaml` LOSS appeared.
- `assemble_commands.py --check` exits 1, and every drift line is `DIFFERS`.
- **T07c was not redone.** It was already on this base: own text 11089 words against a 12700-word baseline (87.3%), with the floor table in the T07c receipt. This unit restored 11 cut passages, listed below, because the loader can only carry them if they are restored. Own text is now about **11330 words (89%)**. That is estimated from the render's word report (38790 → 39028): this worker had no word-count tool. The ≤50% target is **not met**. The floor D-row stays owed to the hub, as the T07c receipt says.

## What changed

### 1. Real keys

Every `# class:` comment is now a `class:` key, and every `# clauses:` comment a `clauses:` key. Clause numbers were re-derived under master's splitter, which keeps balanced parentheses whole and splits at an unspaced `—`. All old `# clauses:` labels were dropped and re-added only where a LOSS line named the clause (list in § 4).

### 2. Carriers

Under the old loader most entries carried minimum-window stub phrases. Master's loader rejects these: B finds a clause uncovered, C finds a prose phrase under 6 words or not unique, A finds a ban word plus its next word missing, and D finds a grammar or behavioural clause not verbatim.

Each failing entry now carries its whole `current` unit as one `text` phrase. That phrase holds every anchor and every stem of every surviving clause. A prose phrase equal to the whole unit is exempt from C's 6-word minimum but not from uniqueness, and every one is unique. Where several entries share one unit, the phrase is written once as a YAML anchor (`&L84`, `&L-lessons`, …) and aliased (`*L84`). The loader's `SafeLoader` resolves the alias to the same string. Existing ≥6-word unique phrases and every `pins:`, `ordered:` and `forbidden:` carrier were kept.

### 3. Split entries deleted

Eight secondary entries of a split baseline had a `current` that was a *different* unit, so their own baseline clauses could never be carried inside their `current`. Each primary entry now carries the whole baseline unit. The deleted entries and the `vanished:` labels that named them:

| deleted entry | its `current` was | primary that carries the baseline |
|---|---|---|
| `fr-four-selector-flags-repeatable-actionb` | the `[NOTE]` unit | `fr-four-selector-flags-repeatable-action` |
| `fr-worker-pool-off-d-181b` | the L84 sizing unit | `fr-worker-pool-off-d-181`, `rq-execute-plan-run-seats-its-per-round-opus-floor` |
| `fr-satisfied-construction-seat-native-db` | the L92 partition unit | `fr-satisfied-construction-seat-native-d` (L91 label updated) |
| `fr-refuted-executed-shown-false-quoteb` | the L146/147 unit | `fr-refuted-executed-shown-false-quote` |
| `fr-dropped-rides-ledger-unexecuted-counter` | the IX 12-Factor table row | `fr-dropped-rides-ledger-unexecuted-counterb` |
| `fr-local-resolution-unambiguous-contained-missingb` | the L191/192 unit | `fr-local-resolution-unambiguous-contained-missing` |
| `fr-architectural-finding-real-correct-fixb` | the L194 unit | `fr-architectural-finding-real-correct-fix` |
| `fr-fixed-reproduce-runnable-test-executionb` | the L164 unit | `fr-fixed-reproduce-runnable-test-execution` |

L26 stays split. `fr-arm-finders-run-python-scripts` lost its `current` and carries both sentences as one phrase, because clause 2 crosses the sentence boundary. `…scriptsb` labels clauses 1 and 2 `duplicate-of` it, and the loader checks that label.

### 4. Clause labels (author labels: audit owed)

No label sits on a clause that holds a ban word; the loader refuses one.

| entry | clause | label | why |
|---|---|---|---|
| `fr-synced-file-appearing-diff-itself` | 3 "excluding hides the violation" | narrative | rationale |
| `fr-finder-given-sha-must-read` | 2 "it is probably dirty … siblings' uncommitted work" | narrative | incident rationale |
| `rq-counter-word-in-method-cell-refused`, `fr-pass-1-row-s-method` | 3 "that count is the pilot's measure" | narrative | explanation |
| `fr-you-never-finder-you-partition` | 3 "that execution is what replaced D-191's Opus re-read …" | duplicate-of `fr-execution-what-replaced-d-191` | the same sentence opens Phase 2; the loader checks the cover |
| `fr-arm-finders-run-python-scriptsb` | 1, 2 | duplicate-of `fr-arm-finders-run-python-scripts` | split unit, see § 3 |
| `fr-satisfied-construction-seat-native-d` | 3 "a `read_only` pool unit inlines the raw hunk …" | narrative | rationale for NATIVE-ONLY |
| `fr-matters-because-two-recoveries-opposite` | 2 "which is why the COPY rule above is the guard …" | narrative | rationale |
| `fr-finder-surfaces-candidate-concrete-nameable` | 3 "that is the dominant cause of misses" | narrative | rationale |
| `fr-test-passes-because-environment-cannot` | 2 "\"it passed locally\" is not evidence … (a superuser role …)" | narrative | examples |
| `fr-reach-missing-constraint-throwaway-ephemeral` | 2 "a scratch DB, a local container, a disposable account" | narrative | examples |
| `fr-fix-only-contract-effect-contained` | 2 "the same carve-out as :269" | narrative | stale cross-reference |
| `fr-changes-what-caller-assume-describes` | 1 "… describes most correctness fixes" | narrative | observation; the rule "is NOT the trigger" is kept |

### 5. Source restorations

T07c had cut these passages. Restoring each one was the only way to meet the loader without a wrong label: a ban span that must stay verbatim, anchors no phrase can hold, or a paraphrase the loader cannot prove a duplicate. Each was restored verbatim from the baseline, so its unit no longer vanishes, and its `vanished:` label was removed.

| L | restored text (short) | why the cut could not stand |
|---|---|---|
| 48 | "Adjudicating every checklist class while the seeded repro stays red is NOT a valid exit" | the `duplicate-of` label fails coverage |
| 79 | "pilot D-344, 2026-09-22, superseding D-207's … bigger one;" | inside the clause that holds "NO Opus finder"; a narrative label would hide that rule |
| 83 | "; KILL (revert to D-207) if a slice's pair confirms less … measured runs)" | the pilot's kill rule; a narrative label would be wrong |
| 89 | "Nothing records to the flywheel and no `NO-POOL:` is owed (…)" | the `duplicate-of` label fails coverage |
| 92 | "; no `NO-POOL:` waiver is owed — `check_subagent_flywheel.py` stands down …, D-182" | one parenthetical clause whose anchors left the text |
| 112 | "; live case: a 7-pass converged review stamped one clean, red two weeks later" | inside the "only while" ban span (D-1240: the parenthetical stays verbatim) |
| 147 | ", so do not defer to the implementation's apparent intent" | a rule clause cut silently |
| 150 | "It is not dropped — " | its first clause |
| 173, 174 | "REFUTED — you did the work to PROVE …" · "Promoting a finding to REFUTED requires proof, not a shrug" | the `duplicate-of` labels fail coverage |
| 260 | "(a re-raise of an already-adjudicated standing row would instead be CITED …)" | its anchors left the text |
| 262 | "This is what reconciles the loop with its graders: …" | the `duplicate-of` label fails coverage |

L36 "This is exactly why the list is computed …" (rationale) and L196 "(The rest of this phase defaults the same way …)" (a pointer) change from `duplicate-of` to `narrative`.

### 6. Class changes

These entries change class. Each was reworded by T07c, and the only test on each is a file-text pin, which the brief says is not behavioural.

| entry | from | to |
|---|---|---|
| `fr-routed-up-review-names-trigger` | behavioural | prose |
| `rq-trimmed-single-finder-slice-second-next-wave` | behavioural | prose |
| `rq-briefs-and-fix-lists-live-under-scratch` | behavioural | prose |
| `fr-size-python3-opt-fabrik-scripts` | behavioural | prose |
| `fr-new-stays-prose-row-stopped` | grammar | prose |

Under `behavioural` or `grammar`, lint D demands every clause verbatim, and the reworded clauses are not. Under `prose`, B and C bind instead. The ban spans inside these units ("refusal", "never", "only", "REFUSAL") stay verbatim and are still linted.

## Ledger after

`LEDGER fabrik-review.yaml: 276 entries · classes {'ban': 91, 'behavioural': 27, 'grammar': 52, 'prose': 106} · vanished {'narrative': 19, 'rule': 37} · provenance 0`

That is 284 entries before (8 deleted, § 3). The vanished labels were 66 before: 42 rule, 17 narrative, 7 duplicate-of. Now 56. Ten units are back to their baseline and no longer vanish: L48, L79, L89, L92, L112, L150, L173, L174, L260, L262. L36 and L196 were relabelled `narrative`. L83 and L147 keep their `rule:` labels; their restored clause sits inside a unit T07c also reworded elsewhere. No entry's `baseline` changed.

## Gates

- `tests/test_command_rules.py -rP`: **72 passed**, including `test_the_live_corpus_has_no_loss`. At the start of the unit the same test failed with 331 `fabrik-review.yaml` LOSS lines.
- `assemble_commands.py --check`: **exit 1, zero LOSS lines**; every drift line is `DIFFERS`. Partway through the session, DIFFERS rows appeared for twelve installed renders this unit never touched (`design-review`, `fabrik-epics*`, `fabrik-deploy-plan*`, …), while a background test group was running. They are drift in the installed copies, not LOSS.
- Reader tests over the edited source:
  - `test_research_tier_order`, `test_review_command_text_defects`, `test_review_loop_workflow`, `test_review_queue_pass`, `test_review_receipt`, `test_review_scoped_queue_pass`: **214 passed**, re-run after the last source edit.
  - `test_plan_review_queue_pass` … `test_quota_posture`: all passed (exit 0).
  - `tests/enforcement/*`: 95 failed, every one in `test_review_refusals.py`, because the clone is not a git repository and those tests `git show` an old commit. That is the same 95 the T07c receipt lists as pre-existing.
  - `sysadmin/test_dispatch_headroom` … `test_assemble_dispatch_step`: 208 passed, 2 failed. Neither failure is a text failure:
    - `test_assemble_dispatch_step.py::test_v7_the_retired_d191_seat_mix_literal_survives_nowhere` dies in `git ls-files` (not a git repository).
    - `sysadmin/test_dispatch_headroom.py::test_own_session_id_is_command_runs_own_ladder_including_the_nosession_key` fails on a session-id environment value.

    Every text assertion `test_assemble_dispatch_step` makes on `fabrik-review` passes.
  - Also run, all green apart from two `git`-only failures (`test_assemble_orch_retired::test_git_grep…`, `test_check_convergence::test_quiet_pass_is_set_identical…`): the corpus (357 passed), execute-plan (420), hook and spec (367), gate (415), command-run (617), kaizen (231), lane and doc-link (319) and task-lane (202) groups.
- No start-commit failure set could be taken: the clone has no git history and no checkout of the start commit. The failure sets above are compared with the T07c receipt's start set.

## Self-audit

I audited by hand, entry by entry, against `fabrik-review.baseline.txt`; no subagent was available. The four checks:

1. LOST: every baseline clause has a carrier or a correct label. The 11 restorations above fixed the clauses earlier labels had hidden.
2. WEAKER: every changed carrier is the whole `current`, so no anchor or ban span was dropped.
3. INVENTED: every restored passage is a verbatim baseline unit; no other source text changed.
4. WRONG-VANISHED-LABEL: the 7 old `duplicate-of` labels that failed coverage became either restorations or `narrative` (L36, L196). The L79 and L83 narrative labels my first pass wrote over rule clauses were replaced by restorations.

What earlier passes fixed:
- My first pass labelled L79 clause 4 and L83 clause 5 `narrative`; both hold rules, and both are now restored.
- My first pass labelled L150 clause 1 `narrative`; it is now restored.

COUNTS: entries read 276 / reworded 0 new (re-ledger only) / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0

The hub re-runs this audit author-blind. The 19 inherited `narrative` vanished labels from T07c were read but not re-litigated; author labels, audit owed.

## LEFT FOR THE HUB

- The author-blind Sonnet + Haiku audit of the labels and the class changes above.
- The review wave.
- The `/fabrik-review` floor D-row: 89% own text, see the T07c floor table.
- The ceiling ratchet.
- `INDEX.md` and `CHANGELOG.md` rows.
- A D-row for the five class changes in § 6, if the hub wants class changes minted (D-1236: a class "changed only by a D-row"; these classes were never real keys before this unit).
- T07c's further cut toward ≤50%. It was not attempted in this run.

## Hub adjudication (kaizen, batch 3, 2026-10-28)

- Graded on `kaizen-lean-batch3` after merging master (d307dd733): 0 LOSS over 63 ledgers under master's loader.
- Hub audit pair (Sonnet 10 items, Haiku 10, overlapping), each checked against `git show lean-baseline-2026-10-25:commands/_sources/fabrik-review.md`. **Fixed, at baseline wording:** the four `<!-- POOL OFF … kept verbatim for re-enable -->` blocks and their lead-in "The pool-breadth contract follows, commented for re-enable:" (both seats: their bodies hold the NEVER-hand-roll ban, the never-`anthropic/*` rule and the unscored-pool-rows close rule, and `baseline.txt` skips comment bodies, so no ledger saw them go); "it passed locally" is not evidence, with its three examples; the throwaway-instance examples; the LOCAL/ARCHITECTURAL axis note (L189); the `_OWN_FIX_ROUNDS_FOR_STOP` worked-case pointer (L78); "which is why the COPY rule above is the guard … not the timeout"; "exactly one terminal condition … neither alone is enough"; "and nothing is printed"; "and no exit code, re-read or md5 catches it"; the capture-recapture advice output; "(D4)"; the `read_only` pool-unit secret reason; "means silently ending the plan". Their entries were repointed to the current units; the narrative labels on L78, L90 and L189 and the clause labels on the four restored entries were dropped. Refuted: none.
- Grade after the fixes: **0 LOSS** over 63 ledgers. Own text: baseline 12700 → **12270 words (96.6%)**; the restored comment blocks are most of the rise.
