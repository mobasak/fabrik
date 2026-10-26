# T05a receipt — shared fragments: subagents-core and the grounding, intake and test-loop fragments, migration part a

- Branch `claude/lean-t05` on `origin/kaizen-lean-u01`. **Start commit (the unit's baseline commit): `61d1f4b99c6a8188a281f86799268fe54ee1b5d1`.**
- The ticket cuts no text: the ten shared files are byte-identical to the start commit (`git diff --stat 61d1f4b -- commands/_fragments/` is empty).

## Baselines written (never rewritten by T05b or T05c)

| shared file | own-text words (`wc -w`) | baseline units | `baseline_sha256` (first 16) |
|---|---|---|---|
| `commands/_fragments/subagents-core.md` | 4028 | 48 | `60e5ebc03b84ea52` |
| `commands/_fragments/delegated-reads.md` | 194 | 4 | `c7e7818be3458527` |
| `commands/_fragments/grounding-artifact.md` | 581 | 18 | `95e45e1792aa5d43` |
| `commands/_fragments/grounding-code.md` | 389 | 10 | `877580fe99c89762` |
| `commands/_fragments/grounding-rules.md` | 483 | 16 | `0930d1b24e2e5e97` |
| `commands/_fragments/questionbar.md` | 73 | 5 | `3e2e9fd6f6a3591e` |
| `commands/_fragments/injection.md` | 47 | 2 | `f1f7d60f753a1d9b` |
| `commands/_fragments/test-generation-loop.md` | 630 | 14 | `c7394d5e63ca5e1b` |
| `commands/_fragments/chat-intake.md` | 560 | 20 | `005911b4172db18a` |
| `commands/_fragments/repo-identity.md` | 208 | 6 | `89a2945ee3233c42` |
| **total** | **7193** | | |

Ledgers exist for all ten files. Only `subagents-core.yaml` carries entries in part a (7); the other nine carry `entries: []`, because no part-a test pins their text.

## Entries written (7, all in `subagents-core.yaml`) and the pins they replace

Class and clause tags are YAML comments (`# class:`, `# clauses:`): the loader at the base (`_ENTRY` has no `class`/`clauses`) does not yet take them as keys.

| entry id | class | carrier (verbatim from the start commit) | pin deleted |
|---|---|---|---|
| `sc-review-shaped-fan-out-workflow` | ban | `runs, outside the hub (D-961: the hub never calls it), as ONE `Workflow` call` | `tests/test_review_queue_pass.py::test_every_workflow_command_carries_the_no_workflow_in_the_hub_note` (the `core` assert, 1 of 2) |
| `sc-pin-writes-read-only-copies-and-a-manifest` | prose | `pass it, outside the hub (D-961), into the `fabrik-review-loop.js` args` | same test (the `core` assert, 2 of 2) |
| `sc-d8-seat-folder-and-scratch-homes` | ban | the worktree-lead `cp` clause; the lead-creates-the-seat-folder clause; the `so nothing durable is written there …` span | `tests/test_review_queue_pass.py::test_a_worktree_lead_writes_scratch_files_by_cp` (whole test); `tests/test_review_queue_pass.py::test_the_lead_creates_each_seat_folder_before_dispatch` (the presence assert; its absence assert stays); `tests/test_review_scoped_queue_pass.py::test_a_brief_tells_each_seat_to_create_its_folder_first` (whole test) |
| `sc-d8-one-plain-command-per-bash-call` | ban | the `docs_updater.py` `os.chdir` clause; `say in MACHINERY which command was refused how many times of how many tries` | `tests/test_review_queue_pass.py::test_a_cwd_rooted_tool_runs_after_an_os_chdir` (the clause and "nothing added after" asserts; its behavioural `docs_updater` subprocess half stays) |
| `sc-d8-a-refused-act-is-never-disguised` | ban | the whole `A command reshaped after any refusal …` sentence | `tests/test_review_scoped_queue_pass.py::test_a_seat_never_disguises_a_refused_act` (the `core.count(...) == 1` assert; the two-file `for text in (agent, core)` loop stays) |
| `sc-by-file-two-finders-per-slice` | ban | `since round 1 is not complete until every slice is read` | `tests/test_review_queue_pass.py::test_a_fix_between_round_one_waves_is_in_the_delta_surface` (whole test, shared with the next row) |
| `sc-fix-between-waves-in-the-next-pin` | prose | `A fix the lead makes between waves is in the next wave's pin, as every fix is in the pin cut after it.` | same test |

Two pins stay as tests, on purpose: `tests/test_command_improve_queue_pass.py` only checks that the seven seat homes exist (no text pin on these files), and the cross-file loop `test_the_opt_in_fallback_is_stated_in_every_copy` relates every copy of the Workflow fallback clause.

## Gates

- `python3 -m pytest -q tests/test_command_rules.py -rP` → 32 passed, 3 skipped; the PASSES section prints one `LEDGER` line per ledger (ten shared ledgers: `subagents-core.yaml: 7 entries · vanished {}`, the other nine `0 entries · vanished {}`).
- `python3 commands/assemble_commands.py --check` → exit 1, every DRIFT line `DIFFERS from what this tree renders` or `MISSING` (installed corpus stays master's); no LOSS line, no exit 4 or 5.
- `python3 -m pytest -q tests/test_command_improve_queue_pass.py tests/test_review_queue_pass.py tests/test_review_scoped_queue_pass.py` → 113 passed, 1 failed. The one red, `test_review_queue_pass.py::test_a_cwd_rooted_tool_runs_after_an_os_chdir`, is red at the start commit too (`psutil` is not installed in this clone, so `docs_updater` prints an error where the test expects a path).
- Failure set at the start commit over the reader-test union (49 files, spine § Global Constraints): 55 failed, 4 collection errors (`tests/orchestrator/test_e2e_rollback.py`, `test_infrastructure.py`, `test_registrar_failures_not_green.py`, `test_spoke_dsn_mesh.py`: `dotenv` is not installed in this clone). These are pre-existing reds from missing box services and packages; the 59-line list is in the T05c receipt. No test this ticket touches added to that set.

## LEFT FOR THE HUB

- Merge of this branch; the `CHANGELOG.md`, `INDEX.md` and `docs/DECISIONS.md` rows (tooling and ledger files outside this ticket's Touches were not edited).
- The author-blind audit of the pin entries is owed with T05c (the entries are carried, not reworded, in part a).
