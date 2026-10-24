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
        "run the full `/fabrik-review` (skipping its own `--init`) with its rows in a draft"
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
        "A full `/fabrik-review` over committed work runs after phase 5 step 5 on a draft in `<durable>`, its receipt"
        " made once, after the last `--commit` (the ledger commit or a later fix), that commit its `--range` tip, and"
        " committed alone; a receipt the D-row cites is made before that commit instead (`--restamp`, phase 5); a"
        " scoped one needs none."
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
        " `commit.sha`, and the receipt is made ONCE, after the last one — `/fabrik-review`'s committed-fix form (a"
        " sync-path run in the main checkout, which `done` holds to one commit, reviews BEFORE that commit instead —"
        " the `--restamp` form below):"
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
    at design time, so a check the build changed shipped with a fire rate nobody re-measured on what ships."""
    assert (
        "before phase 4, MEASURE's test slice re-runs on the built tree, and so does MEASURE's population measurement when the"
        " change adds, changes or removes a check, guard or threshold."
    ) in _norm(SRC)


def test_measure_executes_the_incidents_sequel_both_geometries_prescribed_spellings_and_a_copied_mechanism() -> (
    None
):
    """Rows 1792361074, 1792363058, 1792365690, 1792401257: each design was sent back by its critiques for a case
    MEASURE never executed — what the reporter did next, a merge target that moved past the merge-base, a spelling
    another command prescribes, a copied guard on the live host — so MEASURE executes each before design.md is
    written, the grammar admits the recorded spellings, and the critiques run a copied mechanism."""
    assert (
        "a recipe's real target layout, the reported incident replayed on a copy one step past its symptom (what the"
        " reporter did next), a tool that scopes by a commit or diff range run where the branch's merge-base is its merge"
        " target's tip and where the target has moved past it, each spelling of a parsed input that the commands and docs"
        " feeding it prescribe, a mechanism copied from another script run read-only against the live state of each host"
        " it will run on (a side-effecting step on a copy),"
    ) in _section("## Phase 1", "## Phase 2")
    phase2 = _section("## Phase 2", "## Phase 3")
    assert (
        "a strict grammar and fails closed on the rest. That grammar admits every spelling MEASURE recorded."
        in phase2
    )
    assert (
        "run a mechanism the design copies read-only against the live state of each host it will run on (a side-effecting"
        " step on a copy);"
    ) in phase2


def test_measure_replays_the_items_proposed_fix_and_reads_an_unreachable_source() -> None:
    """Rows 1792467014 (a recurrence of held measure-refuted-ticket-premise), 1792452880, 1792830212 and
    1792780963: a fix the item proposed, or a prior slice's stated reason, was adopted unreplayed, and an unreachable
    tool's claim was recorded unverified with its source unread; the read never upgrades the claim, since phase 1
    counts a source read as no measurement."""
    phase1 = _section("## Phase 1", "## Phase 2")
    assert (
        "A fix the item proposes, and a prior slice's stated reason the design builds on, are replayed the same way, on"
        " a copy, before the design adopts either; a replay that overturns either is stated in PROBLEM."
    ) in phase1
    assert (
        "An unreachable tool's server source, where one exists, is read before a claim is recorded unverified, and"
        " the read never upgrades it."
    ) in phase1


def test_measure_greps_the_prior_record_by_the_items_id() -> None:
    """Row 1792445219 (a finer cut of held read-sibling-row-ruling-first): the grep ran on subject words only; the
    id clause follows the whole list, so it binds every source the list names."""
    assert (
        "the fragment or pack the rule already lives in — each searched by the item's id too, plans and specs included;"
    ) in _section("## Phase 1", "## Phase 2")


def test_measure_runs_a_surfaced_outcome_twice() -> None:
    """Row 1792459184 (a recurrence of held replay-seat-recipe-twice): an outcome seen once was not traced to the
    line the operator reads."""
    assert "a surfaced outcome run twice and traced to the line the operator reads," in _section(
        "## Phase 1", "## Phase 2"
    )


def test_design_tables_a_written_files_malformed_shapes() -> None:
    """Row 1792451004 (a recurrence of held design-list-input-grammar): a marker-block file's broken shapes were
    found by the critiques, not the design's table."""
    assert (
        "A marker-block or append-only file the change writes is tabled absent, begin without end, end without begin,"
        " nested and duplicate."
    ) in _section("## Phase 2", "## Phase 3")


def test_the_brief_fetches_provider_docs_for_seats_without_web() -> None:
    """Row 1792412516: a fabrik-reviewer seat was asked to execute a provider-docs claim it cannot reach."""
    assert (
        "execute one claim about every external dependency (both seats are `fabrik-reviewer`, with no web tool: the"
        " lead fetches a provider-docs fact into the brief)"
    ) in _section("## Phase 2", "## Phase 3")


def test_design_amend_runs_while_the_task_record_is_on_top() -> None:
    """Row 1792418646 (a recurrence of held design-amend-needs-top-record): the amend was tried under a nested
    review: the step landed on the nested record, the active one, and command_run.py refused it (--design-amend
    belongs to --command fabrik-task)."""
    assert (
        "and counted on the close as `design_amends`. The amend runs while the `fabrik-task` record is the top one,"
        " never under a nested run."
    ) in _section("## Phase 2", "## Phase 3")


def test_the_inputs_table_comes_from_measures_read_of_the_live_rows() -> None:
    """Rows 1792587704, 1792574009, 1792544635: a cut key's duplicates and a filtered field's constant value were
    found by the critiques, because the table was filled before any live row was read."""
    assert (
        "That grammar admits every spelling MEASURE recorded. Beside each input the table records its live row count,"
        " the values those rows hold and the duplicates of any key the design cuts rows by, from an executed read of"
        " those rows, never assumed. A marker-block"
    ) in _section("## Phase 2", "## Phase 3")


def test_design_tables_each_new_parser_tag_quoted_inside_its_content() -> None:
    """Row 1792573888 (a recurrence of held design-list-input-grammar): a parser over model output met its own tag
    quoted inside the content it wraps."""
    assert (
        "nested and duplicate. So is each tag a parser it adds or extends reads, plus that tag quoted inside its own content."
    ) in _section("## Phase 2", "## Phase 3")


def test_the_vendored_copy_census_counts_the_worktrees_apart() -> None:
    """Row 1792585649: `find /opt` counted every `.claude/worktrees/` checkout and the inflated count went into the
    design."""
    assert (
        "(`find /opt` by the file's name, `.claude/worktrees/` counted apart) under every spelling"
        in _section("## Phase 2", "## Phase 3")
    )


def test_a_second_design_is_ignored_with_only_a_note() -> None:
    """D-1103 cut the once-only sentence to its one fact: command_run.py prints a NOTE and the step carries on."""
    assert (
        "re-run, or the record stays at phase 1. A second `--design` is ignored, with only a NOTE. Add a"
    ) in _section("## Phase 2", "## Phase 3")


def test_a_terminal_resting_on_another_partys_act_names_who_performs_it() -> None:
    """Row 1792612721, the second verdict on held what-do-terminal-names: a terminal naming a live effect on shared
    state (a port, a service, a deploy) said nothing about who triggers it. The rule lives in the run-record fragment,
    which 36 of the 39 commands that open a record include (the other three prescribe a terminal no third party
    acts on), and the terminal names the hand-off, since a close cannot wait for an act that comes after it."""
    live = re.sub(
        r"<!--.*?-->",
        "",
        (ROOT / "commands" / "_fragments" / "run-record.md").read_text(),
        flags=re.S,
    )
    frag = re.sub(r"\s+", " ", live)
    section = frag[frag.index("`--surface` is what makes") : frag.index("Close it EXACTLY ONE")]
    assert (
        "Where the outcome rests on an act this run does not perform (a deploy, a service restart, a port another"
        " process binds, a merge by its owner), the `--terminal` names the hand-off and who performs the act, and"
        " `--evidence` says whether they had acted at the close."
    ) in section
    src = re.sub(r"<!--.*?-->", "", SRC.read_text(), flags=re.S)
    assert src.index("{{include:run-record}}") < src.index("## SIZE")


def test_measure_runs_each_probe_under_an_interpreter_shown_to_import_it() -> None:
    """Rows 1792766698, 1792734746: an oracle probe imported the system python's markdown_it, which lacks linkify,
    and had to be re-pointed at the venv; most project venvs lack linkify too, so the import is shown, not assumed."""
    assert (
        "an independent parser for a parsed format (every probe run under an interpreter shown to import its"
        " libraries and each extra it enables: a system `python3` may lack one)"
    ) in _section("## Phase 1", "## Phase 2")


def test_review_amends_each_path_a_fix_touches_at_phase_4_after_the_nested_review() -> None:
    """Row 1792765470 (a recurrence of held design-amend-needs-top-record, stated in phase 2): --design-amend was
    refused while the nested review was the top record, and phase 4 did not say when the amend runs. `step` sets the
    record's phase to the one it names (command_run.py), so the amend names phase 4."""
    assert (
        "noted; each path a review fix touches that APPROACH/MIRROR does not name has phase 2's plan-lock check run on"
        " it before the fix edits it, and gets *(v2)* `step --phase 4 --design-amend <path>` once the nested review has"
        " closed."
    ) in _section("## Phase 4", "## Phase 5")


def test_mirror_searches_other_checkouts_tests_for_a_changed_path() -> None:
    """Row 1792731898: MIRROR read the consumer's script but not its tests, and both critiques spent their top
    concern on a hard-failing live-hub test one directory over; a name-only `find /opt` finds copies, not citers."""
    assert (
        "docs), every other `/opt` main checkout's tests and CI files citing a changed path, and every vendored copy"
        " outside"
    ) in _section("## Phase 2", "## Phase 3")


def test_plan_locks_are_read_before_the_critique_seats_and_the_terminal_before_design() -> None:
    """Row 1792834386: the plan-lock read sat after both critiques, so a locked path stopped the run only after two
    seats were spent; it now precedes the critique fragment that stamps the seats, and the pre-`--design` checklist
    re-runs it on every path, since a lock may be taken while the seats run (row 1791868540's defect). Rows
    1792835476 and 1792831669 (ten answered rejects cite the `--terminal-amend` line, a line not followed): the
    checklist now opens by re-reading `--terminal` against design.md's TERMINAL as MEASURE and the critiques left it."""
    phase2 = _section("## Phase 2", "## Phase 3")
    lock = phase2.index(
        "Before the critique seats below are stamped, read the plan locks (no CLI does:"
    )
    assert lock < phase2.index("{{include:design-critique}}"), (
        "the lock read must precede the seats' stamp"
    )
    pre_seats = phase2[lock : phase2.index("{{include:design-critique}}")]
    assert "inside another lock's `owned_paths` is a STOP," in pre_seats
    assert "so a locked path stops the run before a seat is spent." in pre_seats
    assert phase2.count("read the plan locks") == 1, "the lock read is stated twice in phase 2"
    start = phase2.index("Then, before this call:")
    checklist = phase2[start : phase2.index("```bash", start)]
    assert checklist.startswith(
        "Then, before this call: re-read `design.md`, and `--terminal` against its TERMINAL as MEASURE and the"
        " critiques left it (a change rides this call as the `--terminal-amend` below); the lock check again, on every"
        " path (a critique may add one, and a lock may be taken while the seats ran); each Behaviour names its test;"
    )


def test_measure_says_a_zero_count_is_no_fail_direction() -> None:
    """Row 1792832940, a recurrence of held zero-instance-class-refusal-first: a no-change verdict rested on a corpus
    count for a shape the parser's grammar admits; MEASURE now constructs and runs the admitted inputs the corpus
    lacks before such a verdict."""
    assert (
        "the n behind any rate, bound or zero the design will claim (a count is no fail direction: before a no-change"
        " verdict rests on one, the inputs the grammar admits and the corpus lacks are constructed and run);"
    ) in _section("## Phase 1", "## Phase 2")
