"""/fabrik-plan-review feedback queue answered in one pass per run (D-735): each test pins one subject's rule in the
section of fabrik-plan-review.md, design-critique.md or term-edit.md whose reader acts on it.
"""

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAG = ROOT / "commands" / "_fragments" / "design-critique.md"


def _accepted_clause() -> str:
    text = re.sub(r"\s+", " ", FRAG.read_text())
    start = text.index("in spec-review and plan-review it re-opens the loop")
    return text[start : text.index("in `/fabrik-task`", start)]


def test_the_accepted_delta_round_is_recorded_and_its_advisory_expected() -> None:
    """Row 1791770042 (and spec-review's 1791303387): the delta is the next Pass, slices restated, advisory expected."""
    clause = _accepted_clause()
    assert (
        "recorded as the next Pass with every slice an earlier round stated re-stated in `--slices`"
        in clause
    )
    assert (
        "an OSCILLATING advisory naming that round's count after an earlier 0 is expected there, not drift"
        in clause
    )


def test_the_advisory_the_clause_expects_is_what_command_run_prints() -> None:
    """A quiet round then a panel delta confirming k: from round 5 the advisory on that round names `0 → k`."""
    spec = importlib.util.spec_from_file_location(
        "command_run", ROOT / "scripts" / "command_run.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    warning = mod.convergence_warning([5, 3, 1, 0, 4])
    assert "OSCILLATING" in warning and "0 → 4" in warning
    assert (
        mod.convergence_warning([3, 0, 4]) == ""
    )  # below the heuristic's minimum rounds it stays silent


def test_the_opus_floor_and_the_half_blocked_split_are_stated() -> None:
    """Mail 01M3VSFP9D (fabrik-lib): D-344's 'no Opus finder' hid execute-plan's floor; a half-blocked plan had no split rule."""
    core = " ".join((ROOT / "commands" / "_fragments" / "subagents-core.md").read_text().split())
    assert (
        "`/fabrik-execute-plan`'s per-round Opus finder floor, once at D7 under `Profile: small`, is its own rule and still stands"
        in core
    )
    plan = " ".join((ROOT / "commands" / "_sources" / "fabrik-plan-review.md").read_text().split())
    assert (
        "SPLIT the plan: the phases BEFORE the first blocked one keep the plan's name, converge and execute; that phase and every later one move to a new `DRAFT` plan"
        in plan
    )


def test_a_seat_never_executes_a_script_that_acts_outside_its_scratch() -> None:
    """Row 1791938982 (fleet, 2026-10-14): four plan-review seats executed scripts/proof_run.py because the brief said
    to confirm what a sentence described, and destroyed a live fixture. The rule rides in both texts a seat can load:
    the seat-isolation paragraph of subagents-core and the native reviewer's house rules, whose verdict for such a
    claim is `unverified`."""
    core = " ".join((ROOT / "commands" / "_fragments" / "subagents-core.md").read_text().split())
    assert (
        "A seat reads a script before it EXECUTES it, its `--help` included, and never executes one that deletes,"
        " deploys, provisions, writes outside its scratch dir or contacts a non-local host, whatever binary does it,"
        " even when its brief asks it to confirm what that script does: it cites the lines and returns that claim"
        " `unverified` (read-only by rule)" in core
    )
    agent = " ".join((ROOT / "commands" / "_agents" / "fabrik-reviewer.md").read_text().split())
    assert (
        "read a script before you execute it, its `--help` included, and never execute one that deletes, deploys,"
        " provisions, writes outside your scratch dir or contacts a non-local host, whatever binary does it, even"
        " when a check asks you to: cite the lines and return that claim `unverified` (read-only by rule);"
        in agent
    )


def test_the_ledger_home_names_what_the_gate_grades_in_plan_and_receipt() -> None:
    """Row 1792013533 (kaizen, 2026-10-15, the one-door monolith loop): the command said the Pass Ledger lives in the
    review receipt, and the lead learnt by precedent (the venv plan) that the PLAN must carry its own ledger too —
    `check_convergence._check_plan` grades the plan text's `method: re-derivation` Pass row for every plan (:710) and
    its last `confirmed: 0` row for a monolith (:717-722; `_check_spine_set` grades a spine's, :464), and never opens
    the receipt; the receipt is graded by its own
    ledger only when its header `Command:` label names this command AND it carries no live `## Coverage Checklist`
    heading (`_is_design_receipt`, :1310) — which the `review_receipt.py --init` skeleton emits (:247), so a receipt
    built from it is read as a code review and owes the gate embed. The sentence now states both homes (ledger and Residual), which function grades which row for a spine and a
    monolith, and both receipt conditions. Mutants, each a failing assertion: restore 'lives in the review receipt' (the receipt-only claim);
    drop 'a spine's or a monolith's'; drop the `_check_plan` row grammar; drop the Coverage Checklist condition; drop
    the skeleton clause; move the sentence out of Phase 1."""
    src = ROOT / "commands" / "_sources" / "fabrik-plan-review.md"
    text = " ".join(src.read_text().split())
    phase1 = text[
        text.index("## Phase 1 — Grounding passes") : text.index(
            "## Phase 2 — Make every step executable"
        )
    ]
    sentence = "The plan and its review receipt both carry the Pass Ledger and its Residual. At the flip `check_convergence.py` grades the PLAN's own rows, a spine's or a monolith's — a `method: re-derivation` Pass row (`_check_plan`) and a last counter row reading `confirmed: 0` (`_check_plan` for a monolith, `_check_spine_set` for a spine) — beside the plan's adjudicated Coverage Checklist (step 2). The review receipt, `docs/development/reviews/<YYYY-MM-DD>-<slug>-plan-review.md`, whose first 10 lines carry the line `**Command:** /fabrik-plan-review`, carries the same ledger plus the panel table and the ask↔spec table: once it claims a finished review, the gate grades it by its ledger only under that label and with no `## Coverage Checklist` heading of its own (`_is_design_receipt`), and demands a code review's gate embed otherwise — `review_receipt.py --init` writes receipts for the two code-review commands only and always emits that heading."
    assert phase1.count(sentence) == 1, "the ledger-home sentence is stated once, in Phase 1"
    assert "Pass Ledger lives in the review receipt" not in text, "the receipt-only claim is gone"
    # the two homes are named exactly once each in Phase 1 — a second statement is a restatement that drifts
    assert phase1.count("The plan and its review receipt both carry the Pass Ledger") == 1
    lowered = text.lower()
    for restatement in (
        "lives only in the review receipt",
        "receipt holds only",
        "only in the receipt",
        "lives only in the plan",
        "only in the plan",
    ):
        assert restatement not in lowered, restatement
    assert phase1.count("`_is_design_receipt`") == 1


def test_round_zero_scripts_step_references_and_mutant_predictions() -> None:
    """Row 1792092814, the sixth verdict answered from rule (1) as already stated: three of six rounds found a step
    reference, a count or a mutant prediction the lead's own fix added, unexecuted. Rule (1) now names the two kinds
    it left out, in both homes of the round-zero rule (term-edit for text loops, term-coverage for code loops)."""
    clause = (
        "AND every count, enumeration, line anchor, step reference, mutant prediction (a mutant its grader is said to"
        " kill) or negative, is executed at round 1, or before the pin that first carries it,"
    )
    # row 1792194120: an advisory count the plan quotes is re-run when a fix changes what it counts, not only its text
    rerun = (
        "re-run and re-cited when the claim or what it measures changes (a fix that changes what a quoted advisory"
        " counts, such as a plan's Touches)"
    )
    for name in ("term-edit.md", "term-coverage.md"):
        text = re.sub(r"\s+", " ", (ROOT / "commands" / "_fragments" / name).read_text())
        assert clause in text, name
        assert rerun in text, name


def _flat(rel: str) -> str:
    return re.sub(r"\s+", " ", (ROOT / rel).read_text())


def test_the_reader_census_counts_running_copies_by_lineage() -> None:
    """Rows 1792415669, 1792408756 (a recurrence of held census-by-call-site): a census counted the paths its grep
    returned and missed hand-vendored and image-built copies. The rule lands in /fabrik-plan-after-chat's census,
    which plan-review's Reader census bullet points at; the grep still finds them, the count is of running copies."""
    assert (
        "and runs before the Phase 2 shape decision. Its count is of the copies that run, each classed by its lineage"
        " (imported, hand-vendored, built into an image) and by the channel that delivers it, never of the paths the"
        " grep returned."
    ) in _flat("commands/_sources/fabrik-plan-after-chat.md")


def test_a_critique_concern_proposes_its_exact_text() -> None:
    """Row 1792452348 (a recurrence of held critique-exact-replacement-text): a narrowing was paraphrased, then folded
    differently from what the seat meant; a structural concern has no single text, so the rule binds a wording."""
    assert (
        "and the change it proposes, as the exact text when the change is a wording (a SQL predicate, a regex, a"
        " sentence);"
    ) in _flat("commands/_fragments/design-critique.md")


def test_a_behavioural_fix_claim_cites_its_branch_in_both_round_zero_homes() -> None:
    """Row 1792411873 (a recurrence of held fix-sentence-names-its-code-site): a fix described what code does on an
    error without citing the line that does it. The interface rule has two homes, so both round zeros carry it."""
    for rel, at in (
        ("commands/_fragments/term-edit.md", "at the pinned SHA"),
        ("commands/_fragments/term-coverage.md", "at the commit the round's briefs pin"),
    ):
        text = _flat(rel)
        zero = text[text.index("**Round zero") : text.index("bind the probe:")]
        assert (
            "behavioural claim a fix writes (what code does on an error, a fallback, a refusal) cites the line that"
            f" implements it (an `except`, `return`, `raise`, `||` fallback or default value) {at}, and is re-read"
            " against it before the pin"
        ) in zero, rel


def test_a_changed_predicate_runs_against_its_pinning_tests_before_the_first_pin() -> None:
    """Rows 1792407014, 1792446405 (a recurrence of held execute-gate-recipes-round1): a changed predicate was run only
    on the plan's own cases, and a seat found the column-level and other-schema shapes in review."""
    assert (
        "so no seat is the first to execute it. A predicate, matcher or filter the plan changes is also run on a"
        " scratch copy against the tests that assert its current behaviour, each failure named as the change the plan"
        " intends or a defect, and against every input shape its grammar admits beyond the plan's own cases (another"
        " schema, a column-level grant)."
    ) in _flat("commands/_sources/fabrik-plan-review.md")


SRC_REL = "commands/_sources/fabrik-plan-review.md"


def _span(after: str, before: str) -> str:
    """The raw text between the ONE live copy of `after` and the next `before`. The anchor must be live (outside every
    HTML comment), and the span is compared with its comments kept, so an exemption hidden in a comment inside the
    span, or a rule moved into one, cannot pass."""
    raw = (ROOT / SRC_REL).read_text(encoding="utf-8")
    live = re.sub(r"\s+", " ", re.sub(r"<!--.*?-->", " ", raw, flags=re.S))
    text = re.sub(r"\s+", " ", raw)
    assert live.count(after) == 1 == text.count(after), (
        f"anchor not unique, moved or commented out: {after!r}"
    )
    i = text.index(after) + len(after)
    assert before in text[i:], f"end marker {before!r} not after {after!r}"
    return text[i : text.index(before, i)]


def test_a_run_lives_in_the_plan_and_is_re_run_before_each_later_pin() -> None:
    """Rows 1792489145, 1792560450, 1792561946, 1792543087: a prototype's corpus sat in scratch, a spec's consumer CI
    snippet went unexecuted, and a folded fix was pinned without re-running the predecessor corpus."""


def test_only_the_orchestrator_runs_the_combined_set_hash() -> None:
    """Row 1792583409: the set-hash recipe told seats to re-derive it, with a cd, && and pipes they may not run."""
    assert _span("COMBINED hash — ", " `d41d8cd98f00b204e9800998ecf8427e` is the empty input") == (
        "`(cd \"<plan-dir>\" && find . -name '*.md' -print0 | LC_ALL=C sort -z | xargs -0 md5sum) | md5sum` —"
        " recorded per pass by the orchestrator, run from inside the set so md5sum's path column reads the same"
        " relative `./…` wherever the set sits (a typed `<plan-dir>` puts its own spelling into every line, and the"
        " hashes differ); a seat never runs it, since its `cd`, `&&` and pipes are shapes the seats'"
        " one-plain-command rule bars, and states instead the per-file hash it read against the pin's"
        " `MANIFEST.pins.md5` (the Subagents section);"
    )


def test_a_substituted_test_value_names_its_guard() -> None:
    """Row 1792413935 (W-2cef0b6b, carried from /fabrik-execute-plan): a test edit that swapped a value hid that the
    test no longer guarded its behaviour."""
    assert _span(
        "A plan light on test coverage must NOT converge. ", " - **Wired-consumer audit"
    ) == (
        "A step or ticket that edits an existing test by substituting a value (an expected literal, an input, a"
        " threshold) names, in its own Scope (a monolith step: in the step itself) and never as a Behavior Contract"
        " row, the guard that test exercised and the"
        " test that still exercises it after the edit; an"
        " unnamed one is a finding, since a substituted value can leave a test that no longer fails when its"
        " behaviour regresses."
    )


def test_each_ticket_carries_the_substituted_value_rule() -> None:
    """Round-1 review: the rule sat only in the per-phase pillar, which a plan SET's per-ticket axes never read."""
    assert _span("- **Behavior Contract ≤8 G/W/T rows** ", ", each grounded") == (
        "(and the Behavior Contract pillar's substituted-test-value rule holds for the ticket)"
    )


SRC = ROOT / "commands" / "_sources" / "fabrik-plan-review.md"
TERM_EDIT = ROOT / "commands" / "_fragments" / "term-edit.md"


def _live(path: Path) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<!--.*?-->", "", path.read_text(), flags=re.S))


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_a_field_a_reader_reads_is_a_closed_token() -> None:
    """Rows 1792654902 and 1792595691 (after held free-text-parser-to-structured-channel): prose matching kept growing
    negation lists."""
    item2 = _between(_live(SRC), "2. **Coverage Checklist.**", "3. **Constraints-Digest audit")
    assert (
        "A field a hook, script or grader the plan specifies will read is a closed token (a fixed label, an enum, a"
        " key), probed before the first pin with its negations and look-alikes, never matched as prose; a grader the"
        " plan puts over prose checks presence only, and what the prose means is a named review check from round 1."
    ) in item2


def test_a_seat_runs_pinned_code_from_an_archive_with_the_pins_laid_over_it() -> None:
    """Rows 1792656795 and 1792642953: seats imported pinned code from the live checkout; PIN_IMPORT forbids the pins
    dir alone on sys.path."""
    pre = _between(_live(SRC), "**Convergence precondition (mechanical):**", "## Phase 1")
    assert (
        "A seat that imports or runs code the plan cites builds an archive of the base SHA with the pinned "
        "files laid over it (the `PIN_IMPORT` recipe in `.claude/workflows/fabrik-review-loop.js`, which "
        "`/opt/fabrik/commands/_fragments/review-probe-catalogue.md` § Seat isolation names), never imports "
        "from the live checkout and never puts the pins dir alone on `sys.path`."
    ) in pre


def test_a_step_that_runs_a_script_is_grounded_against_its_parser() -> None:
    """Row 1792643178 (after held execute-gate-recipes-round1): a step's script mode went unchecked; `--help` runs a
    script with no parser for real, so the read comes first."""
    phase2 = _between(_live(SRC), "## Phase 2", "## Phase 3")
    assert (
        "A step that runs a script names its mode (the subcommand or flags), and the review grounds that command"
        " against the script's argument parser read at the pinned SHA, running `--help` only once that read shows the"
        " script parses arguments; a mode the parser does not accept is a finding."
    ) in phase2


def test_critique_seats_run_one_plain_command_per_call() -> None:
    """Rows 1792657810 and 1792663298: the house-rules list omitted the one-plain-command rule, so leads wrote
    `mkdir … && cd …` into critique briefs."""
    rules = _between(
        _live(FRAG), "the house rules every seat brief carries:", "- its concerns, ranked"
    )
    assert (
        "and one plain command per Bash call: the seat's own `mkdir -p` on its absolute folder first, then "
        "absolute paths, never `cd`, `&&`, a pipe or a `$VAR`."
    ) in rules
