"""/fabrik-task feedback queue answered in one pass (D-735) — each rule sits in the phase that owns it.

Rows answered: the /fabrik-task queue of 2026-10-11, then later passes (each commit's trailer lists its `ts`). Each test
pins one subject's rule inside the section a reader of that phase reads, so a rule moved to the wrong
phase or dropped fails here.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-task.md"
CRITIQUE = ROOT / "commands" / "_fragments" / "design-critique.md"


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def _section(start: str, end: str) -> str:
    text = _norm(SRC)
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_size_check_ignores_each_new_path() -> None:
    """Row 1792293040, the second verdict on held new-file-must-git-added: a declared path that does not exist yet
    fell under a `lib/` ignore rule and never reached the commit; SIZE now check-ignores and stages each new file."""
    assert (
        "**declare the grader you are about to write**, `git check-ignore -v` each new file path and `git add` it"
        " just before phase 5's pathspec commit, which refuses an unstaged one (an ignored one stays out without `-f`);"
        " `ls` and grep every other path for the rule first"
    ) in _section("## SIZE", "## Phase 1")


def test_measure_runs_a_codec_change_on_its_edge_inputs() -> None:
    """Row 1792291304, the second verdict on held design-list-input-grammar: MEASURE runs the codec a change touches
    on non-UTF-8 bytes, NUL and that codec's own escape before design.md is written."""
    assert (
        "the codec a change touches run on non-UTF-8 bytes, NUL and that codec's own escape, an independent parser for"
        " a parsed format" in _section("## Phase 1", "## Phase 2")
    )


def test_size_checks_each_declared_path_before_declaring_it() -> None:
    """Rows 1790966184, 1791467990: a typo'd declared path is accepted silently as a grader."""
    assert (
        "`ls` and grep every other path for the rule first, since a typo reads as that grader"
        in _section("## SIZE", "## Phase 1")
    )


def test_measure_executes_the_real_path() -> None:
    """S2 (population): the population is measured by executing the real path, never a proxy."""
    assert (
        "each by EXECUTING the real path on real data (the producer's code, the tool's run output per mode, "
        "the design's own classifier, the writer of each state value it trusts or ranks on), never a source read or a proxy"
    ) in _section("## Phase 1", "## Phase 2")


def test_the_lane_critique_brief_asks_seats_to_execute() -> None:
    """S3 (critique brief): replay the incident, run claims against the real tool, pin the tree."""
    phase2 = _section("## Phase 2", "## Phase 3")
    assert (
        "This lane's brief also has each seat EXECUTE: replay the reported incident and the real corpus through the design"
        in phase2
    )
    assert (
        "pins the tree (a commit or `git archive` copy) and any live state file the design reads"
        in phase2
    )


def test_the_pre_record_checklist_sits_before_the_record_call() -> None:
    """S4 (design order): the refusal shapes and the one-shot rule precede the `step --design` call."""
    phase2 = _section("## Phase 2", "## Phase 3")
    checklist = phase2.index("`--design` lands ONCE. Record them:")
    assert checklist < phase2.index("step --phase 2 --title")


def test_mirror_searches_the_whole_tree_and_names_fail_direction() -> None:
    """S1 (readers) and the fail-direction rows: where the search runs, and which error is dangerous."""
    phase2 = _section("## Phase 2", "## Phase 3")
    assert (
        "The search is the whole tracked tree (tests, their pinned strings and hardcoded values, `commands/`, UI, docs)"
        in phase2
    )
    assert (
        "names its fail direction — which error is dangerous, an answer versus an outage" in phase2
    )
    assert "Every function, anchor or subject the design names is grepped to exist" in phase2


def test_v1_commits_once_with_the_ledgers_and_graders_execute() -> None:
    """Row 1790689315 (v1's one commit vs phase 5's ledger commit) and S6 (graders)."""
    phase3 = _section("## Phase 3", "## Phase 4")
    assert (
        "At v1 that one commit also carries phase 5's ledgers, so nothing is committed before phase 5"
        in phase3
    )
    assert "every guard and threshold edge the change adds is mutated" in phase3


def test_the_third_review_question_excludes_an_equivalent_implementation() -> None:
    """Row 1790692304: any nameable equivalent implementation read as an UPGRADE verdict."""
    phase4 = _section("## Phase 4", "## Phase 5")
    assert (
        "a second approach whose merits the build cannot settle (an equivalent implementation is not one)"
        in phase4
    )
    assert "Under the urgent-90 CHECKPOINT the record stays open" in phase4
    assert "the declaration said did not exist" not in phase4


def test_the_receipt_range_tip_is_the_last_commit() -> None:
    """S5 (receipt close): task_lane.py check (d) refuses unless the range tip is the LAST --commit."""
    close = _section("## Phase 5", "## UPGRADE")
    assert "Its range tip must be the LAST `--commit` (`task_lane.py` check (d))" in close
    assert "never captured or passed to `--commit`" in close
    # review_receipt.py requires --changed and --out/--scope; the tip is the last captured sha (round 1).
    assert (
        "--changed <every path in base..that sha> --scope <slug> --range <base>..<that sha>"
        in close
    )
    assert "after the last sha in `commit.sha`" in close


def test_critique_is_not_rerun_on_the_folded_version() -> None:
    """Row 1791070230: 'once per artifact version' read as re-critiquing every folded design.md."""
    text = _norm(CRITIQUE)
    assert "a version that ONLY folds its ACCEPTED concerns is not a new one" in text


def test_second_pass_names_the_specific_steps_in_their_phases() -> None:
    """The 2026-10-12 second pass (D-747): the specific steps the first pass left open sit in their phase."""
    measure = _section("## Phase 1", "## Phase 2")
    assert "the tests that drive it by subprocess, the completion gate's own command" in measure
    assert (
        "what a concurrent reader sees mid-write, a before/after hash of every file it writes"
        in measure
    )
    phase2 = _section("## Phase 2", "## Phase 3")
    assert "Before the seats go out: re-read `design.md` against the working tree" in phase2
    # the fixtures and the scratch-suite run precede the critique, not the record call (round 2)
    assert phase2.index("the fixtures a grader borrows") < phase2.index(
        "This lane's brief also has each seat"
    )
    # round 1 of pass 2: the hook stands down for stamped seats, and an override goes to the D-row
    assert "the Stop hook's run-record block stands down and will not hold you" in phase2
    assert "may override it, recorded in the D-row with the drift noted" in phase2
    assert "execute one claim about every external dependency" in phase2
    assert (
        "A concern is ACCEPTED only after the tests are grepped for every line it touches" in phase2
    )
    assert "DECISION names its evidence and whether it is independent of the change" in phase2
    assert "the literal path beside any constant, every party a text reaches" in phase2
    phase3 = _section("## Phase 3", "## Phase 4")
    assert "a removed duplicate is guarded behaviourally, never by text shape" in phase3
    assert "a probe worktree carries the built dist a test reads at import" in phase3
    phase4 = _section("## Phase 4", "## Phase 5")
    assert (
        "The review is sized before dispatch — the callers a fix may touch counted, the quota runway read"
        in phase4
    )
    close = _section("## Phase 5", "## UPGRADE")
    assert (
        "run the full `/fabrik-review` into it (skipping its own `--init`) until `Status: CONVERGED`"
        in close
    )
    assert (
        "`--evidence` names the split; a terminal it changed was restated with `--terminal-amend`"
        in close
    )
    upgrade = _norm(SRC)[_norm(SRC).index("## UPGRADE") :]
    assert (
        "appended to that seed file before `/fabrik-spec` opens from it (never to the `resume_copy`)"
        in upgrade
    )


def test_size_declares_operator_named_work_as_heavy() -> None:
    """Row 1791755899: operator-named work is lane row 1b's heavy surface, declared at SIZE, not found at phase 4."""
    assert "`heavy=yes` includes operator-named work (lane row 1b)" in _section(
        "## SIZE", "## Phase 1"
    )


def test_phase_four_names_the_committed_work_receipt_up_front() -> None:
    """Row 1791845646: the nested review learned the `--range` init only at phase 5's close."""
    text = " ".join((ROOT / "commands" / "_sources" / "fabrik-task.md").read_text().split())
    review = text[
        text.index("Invoke the review phase 0 already picked") : text.index("Give its seat briefs")
    ]
    assert (
        "A full `/fabrik-review` over committed work runs after phase 5 step 5, its receipt's `--range` tip the last"
        " `--commit` (the ledger commit or a later fix), committed alone; a receipt the D-row cites is made before that"
        " commit instead (`--restamp`, phase 5); a scoped one needs none."
    ) in review
    # row 1792287653 (recurring held re-make-receipt-before-the-d-row-cites-it): the range tip is phase 5's last
    # commit, so a D-row the receipt cites is already in it — phase 5's own recipe commits the receipt alone after it
    assert (
        "Its range tip must be the LAST `--commit`" in text
        and "then commit that receipt alone" in text
    )


def test_phase_three_formats_the_declared_paths_only() -> None:
    """Row 1791848436: a package-wide formatter run rewrote eight files nobody declared."""
    text = " ".join((ROOT / "commands" / "_sources" / "fabrik-task.md").read_text().split())
    build = text[text.index("## Phase 3 — BUILD") : text.index("## Phase 4 — REVIEW")]
    assert "Never run a formatter by hand beyond the declared paths." in build


def test_the_plan_lock_check_runs_before_the_design_is_recorded() -> None:
    """Row 1791868540: the lock check sat in phase 3, after --design had recorded a locked APPROACH path."""
    text = " ".join((ROOT / "commands" / "_sources" / "fabrik-task.md").read_text().split())
    design = text[
        text.index("## Phase 2") : text.index(
            "```bash python3 scripts/command_run.py step --phase 2"
        )
    ]
    assert (
        "read the plan locks (no CLI does: each `*.json` in `.fabrik/plan-locks/` with `status: active`)"
        in design
    )
    assert (
        "a declared path or one backticked in APPROACH/MIRROR inside another lock's `owned_paths` is a STOP"
        in design
    )
    build = text[text.index("## Phase 3 — BUILD") : text.index("## Phase 4 — REVIEW")]
    assert (
        "Re-run phase 2's plan-lock check first: a `--design-amend` path or a lock taken since is the same STOP."
        in build
    )


def test_measure_finds_exact_set_asserts_and_behaviours_carry_a_copied_scripts_settled_failures() -> (
    None
):
    """Rows 1791935733 (exact-set and line-count asserts on an extended record, found late) and 1791933860
    (a mirrored hub mechanism re-opened a fail-open the hub design had already settled), W-b4e1dfb2."""
    assert (
        "every reader of a changed record shape or stdout (grep its tests for `== {` and `len(`),"
    ) in _section("## Phase 2", "## Phase 3")
    assert (
        "the prior record grepped — `docs/DECISIONS.md`, the files' docstrings (and a copied script's),"
    ) in _section("## Phase 1", "## Phase 2")
    assert (
        "A mechanism copied from another script carries, as Behaviours tested here (several may share one), the"
        " failure directions its tests and D-rows settled."
    ) in _section("## Phase 2", "## Phase 3")


def test_design_tabulates_its_inputs_and_the_close_captures_by_subject() -> None:
    """Rows 1792119826, 1792097261, 1792094113 (a status file's third value, a forced refresh under a periodic
    guard and a rule's per-window unit each went untabled), recurring held design-branches-on-several and
    design-list-input-grammar, plus 1792019578 (a parser of another language); rows 1792057883 and 1792056989
    (a grown hook output passed the 10,000-character cap); row 1792008185 (`--terminal-amend` read as a later
    step); row 1792003124 (a pre-fold test made green); row 1792034245 (a HEAD read captured a sibling's commit).
    Mutants: drop any clause, let the amend ride "up to" the call again, or restore the HEAD-read capture."""
    design = _section("## Phase 2", "## Phase 3")
    for needle in (
        "Each input the design branches on is tabulated whole in a `design.md` table, outside the Behaviours list:"
        " every value a state it reads can hold,",
        "the unit another tool's rule is evaluated per (window, agent, repo),",
        "every path through a guard (a forced refresh after a write as well as the periodic one);",
        "a parser it adds takes a strict grammar and fails closed on the rest.",
        '`--terminal-amend "<one line>"` on that `--design` call or any step before it',
        "against the real tool under the live guard, a new parser on input outside its grammar;",
    ):
        assert needle in design, needle
    assert "up to that call" not in design
    assert "restated with `--terminal-amend` on or before the `--design` call." in _section(
        "## Phase 5", "## UPGRADE"
    )
    assert (
        "DIRECTIVE 4 against the recorded design (a test drafted before the critiques folded is rewritten, never made"
        " green);"
    ) in _section("## Phase 3", "## Phase 4")
    close = _section("## Phase 5", "## UPGRADE")
    # the subject comes from the -F message file (a pasted one would run its backticks); the grep finds a
    # candidate; the exact %s comparison refuses a body-quoting sibling, a prefix and a miss
    assert "trailers via -F <msg>," in close
    assert (
        '&& subj=$(head -n1 <msg>) && sha=$(git log -1 --format=%H -F --grep "$subj") && [ -n "$sha" ] \\'
        in close
    )
    assert (
        '&& [ "$(git log -1 --format=%s "$sha")" = "$subj" ] && echo "$sha" >> <durable>/commit.sha || exit 1'
    ) in close
    assert '"<your subject>"' not in close
    assert "rev-parse -q --verify HEAD" not in close
    assert (
        "with each hook output it grows sized against Claude Code's 10,000-character cap"
        " (https://code.claude.com/docs/en/hooks)"
    ) in _section("## Phase 1", "## Phase 2")


def test_measure_greps_config_and_env_values_and_design_reads_a_copied_rule_first() -> None:
    """Row 1792233945 (a `${` format change missed the spec env values that carry it), recurring held
    measure-the-env-writers-not-only-the-spec, and row 1792258556 (a var compose read only for interpolation, never
    handed to the container), the same subject again; row 1792240470 (a rule copied from another component could have
    been read from its output), recurring the untagged reject 1791965012 (every other place the rule lives) and
    held gate-legs-before-a-new-leg (reuse what already runs before drafting a duplicate)."""
    assert (
        "every host it runs on, every config and env value a changed format can sit in (grep them for its shape,"
        " e.g. `${`), the transport handing a new env var to the process (compose `environment:`, `env_file`, a"
        " build arg, another launcher) read on the started process (e.g. `docker compose run --rm <svc> env`, its"
        " keys recorded, never its values), and the n behind"
    ) in _section("## Phase 1", "## Phase 2")
    assert (
        "D-rows settled. Before such a copy, a rule another component already applies is tried as a read of its"
        " output (stdout, a record, an exported function); when the copy stays, DECISION says why the read cannot"
        " serve. Each input"
    ) in _section("## Phase 2", "## Phase 3")


def test_review_fix_commits_go_through_the_capture_and_mirror_censuses_the_whole_ast() -> None:
    """Row 1792327651 (a full review's fix commits read as outside the run, so the receipt range was rebuilt by hand
    twice; row 1792309961's confusion read the tip rule the same way, after answered rejects 1792289109 and
    1791923102 on that line) and row 1792303601, the second sighting of held ast-census-for-python-imports (a
    `tree.body` scan missed a function-local import)."""
    assert (
        "Its range tip must be the LAST `--commit` (`task_lane.py` check (d)), and in the after-commit `--range` form"
        " each commit a review fix makes is a run commit: make it through step 5's capture line so its sha lands in"
        " `commit.sha`, and re-make the receipt after the last one as `/fabrik-review`'s exit proofs say (a sync-path"
        " run in the main checkout, which `done` holds to one commit, reviews BEFORE that commit instead — the"
        " `--restamp` form below): after the last sha in"
    ) in _section("## Phase 5", "## UPGRADE")
    assert (
        "every Python reader of a name by an `ast.walk` census beside the grep, never `tree.body` alone (a"
        " function-local or `try:` import sits below it; a string-named import, `getattr` or subprocess argv is no"
        " import node, so the grep finds it),"
    ) in _section("## Phase 2", "## Phase 3")


def test_measure_greps_a_work_items_cited_line_before_the_design_takes_its_wording() -> None:
    """Row 1792330126, the second sighting of held measure-refuted-ticket-premise: a design took a work item's
    wording about a cited file:line that did not hold the symbol the item named."""
    assert (
        "a failure reported with a command is replayed by that command, never a reconstruction, and a work item's cited"
        " `path:line` is grepped here, in the cited file, for the symbol it names, and a failure or error path it claims there is"
        " replayed on a copy carrying the state it needs (a grep hit can sit in dead code); a miss, or a replay on a"
        " copy carrying that state that does not fail as claimed, is a finding PROBLEM states, never the item's"
        " wording, and a replay whose copy cannot carry that state is recorded unverified, never as refuted (MIRROR"
        " greps every name the design uses again)."
    ) in _section("## Phase 1", "## Phase 2")


def test_a_phase_2_critique_naming_an_unsettled_second_approach_is_the_upgrade_crossing() -> None:
    """Row 1792339442: phase 2 asked seats for a second approach the build cannot settle but gave no disposition, so a
    yes was folded in as ACCEPTED and phase 4 raised the same yes as UPGRADE after the build."""
    assert (
        "A second approach the build cannot settle (an equivalent implementation is not one), its seat's claim executed and holding, is the § UPGRADE crossing `tradeoffs`, taken here before"
        " `--design`, never folded in as ACCEPTED."
    ) in _section("## Phase 2", "## Phase 3")


def test_build_re_runs_the_population_measurement_for_a_changed_check_or_guard() -> None:
    """Row 1792352977 (a recurrence of held resweep-corpus-on-widened-guard): MEASURE's population was measured only
    at design time, so a check widened by the build shipped with a fire rate nobody re-measured on what ships."""
    assert (
        "before phase 4, MEASURE's test slice re-runs on the built tree, and so does its population measurement when the"
        " change adds or widens a check or guard."
    ) in _norm(SRC)
