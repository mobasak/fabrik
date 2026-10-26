# T05b receipt — shared fragments: subagents-core and the grounding, intake and test-loop fragments, migration part b

- Branch `claude/lean-t05`, on top of T05a (`77ed535`). Start commit of the unit (its baseline commit): `61d1f4b99c6a8188a281f86799268fe54ee1b5d1`.
- The ticket cuts no text: `git diff --stat 61d1f4b -- commands/_fragments/` is empty. The baselines written in part a are untouched (sha256 unchanged).

## Entries added (part b), and the pins they replace

Class and clause tags are YAML comments, as in part a (the loader at the base takes no `class`/`clauses` keys).

| entry id (ledger) | class | carrier | pin deleted |
|---|---|---|---|
| `sc-by-file-two-finders-per-slice` (`subagents-core.yaml`, +2 carriers) | ban | `` `/fabrik-execute-plan`'s per-round Opus finder floor, once at D7 under `Profile: small`, is its own rule and still stands ``; `then the union is NOT the full pass: the receipt names the unread slices, and further full-pass waves … since round 1 is not complete until every slice is read.` | `tests/test_plan_review_queue_pass.py::test_the_opus_floor_and_the_half_blocked_split_are_stated` (the `core` assert; the plan and review asserts stay); `tests/test_review_command_text_defects.py::test_a_trimmed_round_one_sweeps_its_unread_slices_before_any_delta_pass` (the `sc` presence assert; the term-edit presence assert and the absence assert stay) |
| `sc-d8-seat-folder-and-scratch-homes` (+4 carriers) | ban | the `The scratch dir a brief names is a SEAT FOLDER …` sentence; `a start that printed `RUN-SCRATCH: none — <why>` …`; the `the pins dir (the PIN paragraph below) …` clause; the `a tree is staged in a seat folder only as …` clause | `tests/test_run_scratch_brief_wording.py::test_the_seat_folder_rule_is_stated_once_in_subagents_core` (five presence asserts on `d8`) |
| `sc-pin-afresh-per-pass` | prose | `--pins-dir <a NEW dir per pass>`; `the pins dir sits where the D8 paragraph puts it` | `tests/test_run_scratch_brief_wording.py::test_the_pin_paragraph_defers_the_pins_dir_root_to_d8` (two presence asserts; its absence assert stays) |
| `sc-d8-absolute-paths-in-briefs` | ban | `The dispatcher writes every pin, copy, fix and scratch path a brief names as a literal absolute path, never one relative to a checkout or a placeholder the seat expands` | `tests/test_spec_review_queue_pass.py::test_flow_fixes_panel_residue_and_absolute_brief_paths` (the `core` assert, 1 of its asserts; the others stay) |
| `sc-d8-never-execute-an-unread-or-destructive-script` | ban | the whole `A seat reads a script before it EXECUTES it … (read-only by rule)` clause | `tests/test_plan_review_queue_pass.py::test_a_seat_never_executes_a_script_that_acts_outside_its_scratch` (the `core` assert; the `fabrik-reviewer.md` assert stays) |
| `dr-large-reads-go-to-seats` (`delegated-reads.yaml`) | ban | `a question with several parts is numbered in the brief, … asked again, never read as empty.` | `tests/test_spec_plan_lane_text.py::test_fabrik_spec_carries_its_recurring_feedback_rules` (the `reads` assert; every other assert in the test stays) |

## Pins kept on purpose

- `tests/test_run_scratch_brief_wording.py::test_the_seat_folder_rule_is_stated_once_in_subagents_core` keeps `core.count("under the run's disposable folder") == 1` and `core.count("`<run scratch>/seat-<n>/`") == 1`: each asserts that a phrase appears exactly once, so it also guards against a second statement of the rule (an absence pin). The RULE sentence that holds both phrases is carried verbatim in `sc-d8-seat-folder-and-scratch-homes`.
- `tests/test_run_scratch_brief_wording.py::test_the_review_loops_d8_names_put_their_pins_under_scratch` relates the fragment to four command sources and stays (spine § Global Constraints, cross-file assert); the `durable `SCRATCH:` folder (D-836), as … do so an interrupted pass keeps its pins;` clause it reads is also a carrier.
- The `fabrik-reviewer.md` halves of the two never-execute / refusal tests and the `term-edit.md` half of the trimmed-slices test are pins on other files and stay.
- `tests/test_spec_review_queue_pass.py` has no other pin on these ten files.

## Gates

- `python3 -m pytest -q tests/test_command_rules.py -rP` → 32 passed, 3 skipped; `LEDGER subagents-core.yaml: 10 entries · vanished {}`, `LEDGER delegated-reads.yaml: 1 entries · vanished {}`, the other eight `0 entries`.
- `python3 commands/assemble_commands.py --check` → exit 1, every DRIFT line `DIFFERS from what this tree renders` or `MISSING`; no LOSS (no exit 4 or 5).
- `python3 -m pytest -q tests/test_plan_review_queue_pass.py tests/test_review_command_text_defects.py tests/test_run_scratch_brief_wording.py tests/test_spec_plan_lane_text.py tests/test_spec_review_queue_pass.py` → 72 passed, 0 failed.

## LEFT FOR THE HUB

- Merge, `CHANGELOG.md` / `INDEX.md` / `docs/DECISIONS.md` rows.
- The author-blind audit of the migrated entries rides with T05c's receipt.
