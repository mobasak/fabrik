"""/fabrik-execute-plan feedback queue answered in one pass (D-735): three wrong sentences and the recurring steps.

Each test pins one subject's sentence in the section that owns it; the trailer test executes the parser it describes.
"""

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-execute-plan.md"


def _norm() -> str:
    return re.sub(r"\s+", " ", SRC.read_text())


def _section(start: str, end: str) -> str:
    text = _norm()
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_a_merged_sibling_lock_is_visible_to_the_overlap_scan() -> None:
    """Row 1790897638: committed locks travel with a merged branch, so 'invisible' holds only until the merge."""
    text = _norm()
    assert (
        "A sibling AGENT's lock is invisible from here until this tree's branch contains the merge of its branch"
        in text
    )
    assert "A sibling AGENT's lock is invisible from here and that is safe" not in text


def test_the_baseline_gate_runs_in_check_mode() -> None:
    """Row 1790967489: a bare gate auto-fixes and re-stages, so the baseline must be read-only."""
    text = _norm()
    assert (
        "Record the starting gate state: `python scripts/final_gate.py --lean --check --json`"
        in text
    )


def test_the_review_artifact_binds_every_phase_not_only_gui() -> None:
    """Row 1791157267: the rule sat after 'Non-GUI phases skip this'; command_run.py refuses step for any phase."""
    text = _norm()
    assert "Non-GUI phases skip the screen steps above, never what follows." in text
    assert "Every phase's review exit — GUI or not — must EMIT AN ARTIFACT" in text
    assert "Non-GUI phases skip this. ⚠️ **That exit must EMIT AN ARTIFACT**" not in text


def test_a_resumed_run_names_receipts_with_the_plan_prefix() -> None:
    """Rows 1790974389, 1790767055: earlier phases pass `step` through the plan-prefix form, not a waiver."""
    assert (
        "which `step` reads from the record's `--surface` — so that run's `--surface` names the plan file"
        in _norm()
    )


def test_the_loop_names_the_profile_small_waiver_and_the_interpreter() -> None:
    """Rows 1790956193 and 1788820659, both in the Execution Loop block."""
    loop = _section("## Execution Loop", "## Dispatcher Mode")
    assert "under `Profile: small` add item 3b's `--review-waived`" in loop
    assert "under the repo's own interpreter, its `.venv` python where it has one" in loop
    assert "re-run step 9's path:line and symbol spot-check on this phase's cites" in loop


def test_the_preflight_repeats_before_each_phase() -> None:
    """Rows 1790392963, 1789580800, 1789247175: re-ground cites before each later phase, mechanism claims too."""
    text = _norm()
    assert (
        "Repeat the `path:line` and symbol spot-check before each later phase's first edit or dispatch"
        in text
    )
    assert "This is a **one-time upfront sanity gate**" not in text


def test_d4_wave_brief_points_at_the_catalogue_and_closes_in_order() -> None:
    """The CATALOGUE rows and 1790929913: the wave review's brief and receipt close."""
    d4 = _section("### D4 — Per-wave receive + review", "### D5 — Merge protocol")
    assert (
        "`/opt/fabrik/commands/_fragments/review-probe-catalogue.md` that match the change's SHAPE"
        in d4
    )
    assert (
        "passes `python3 scripts/enforcement/check_review_coverage.py <the receipt>` before its closing round is recorded"
        in d4
    )
    assert (
        "each wave receipt starts from `review_receipt.py --init` (the `## Coverage Checklist`"
        in d4
    )


def test_d5_compares_named_reds_and_d7_points_at_the_pause() -> None:
    """Rows 1789674993 (named reds) and 1789739684 (the pause beside the terminal states)."""
    assert (
        "on the tree before the merge and on the integrated tree, their reds compared BY NAME"
        in _section("### D5 — Merge protocol", "### D6")
    )
    assert "a NEW red → fixup routed to the **CONSUMER's coder**" in _section(
        "### D5 — Merge protocol", "### D6"
    )
    assert "**A quota pause is not a block** — D2's Quota-pause terminal owns it." in _section(
        "### D7 — Final validation", "## Subagent Strategy"
    )


def test_one_ticket_id_per_agent_task_line_is_what_the_parser_reads() -> None:
    """Row 1791056532: the table says one ID per line, and the parser indeed drops the second ID of a list."""
    assert "one ID per `Agent-Task:` line" in _norm()
    spec = importlib.util.spec_from_file_location(
        "check_plan_tickets", ROOT / "scripts" / "enforcement" / "check_plan_tickets.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # its dataclasses resolve their module through sys.modules
    spec.loader.exec_module(mod)
    assert mod.AGENT_TASK_RE.findall("Agent-Task: T04, T05\n") == ["T04"]
    assert mod.AGENT_TASK_RE.findall("Agent-Task: T04\nAgent-Task: T05\n") == ["T04", "T05"]


def test_ruff_format_only_touches_files_formatted_at_baseline() -> None:
    """Row 1791842869 (D-793): the second verdict on the held ruff-format subject, edited."""
    text = re.sub(
        r"\s+", " ", (ROOT / "commands" / "_sources" / "fabrik-execute-plan.md").read_text()
    )
    assert (
        "Never run `ruff format` by hand beyond the plan's `## File Scope (owned paths)` — a wholesale format rewrites a sibling's lines nobody reviews; the bare gate run already formats only your staged and unpushed changes"
        in text
    )


def test_vendoring_copies_the_committed_blob_at_the_pinned_sha() -> None:
    """Row 1791898318 (D-711 audit: MISFILED): the review catalogue's re-vendor rule reaches review waves only, and this
    command's own vendoring steps never said which bytes to copy, so a sibling's uncommitted edit in fabrik-lib could
    ship. Pinned whole inside § When Vendoring step 1, and "working file" may appear there only as the thing never read.
    Not seen: a later step that contradicts it; the review wave's identity diff owns a copy taken from the working tree."""
    vendoring = _section("## When Vendoring", "## Plan Status Tracking")
    sentence = (
        "1. Copy the files as the plan specifies, each read from fabrik-lib's COMMITTED blob — `git -C /opt/fabrik-lib"
        " show <sha>:<its path in fabrik-lib>`, at the SHA the plan names or else `git -C /opt/fabrik-lib rev-parse"
        " --short=8 HEAD` — never its working file, where a sibling's uncommitted edit would ship; record that SHA as a"
        " `Vendored-From: fabrik-lib@<sha>` trailer on the task's commit 2. Fix internal imports:"
    )
    assert sentence in vendoring
    assert vendoring.count("working file") == 1


def test_the_orchestrator_waits_for_its_coders_in_turn() -> None:
    """Mail 01M4VXJ4TQ (infra): a web-ecommerce-factory run dispatched two coders with the Agent tool's default
    (background), ended its turn while they ran, and took 132 run-record Stop blocks; the hook's stand-down covers
    stamped review seats only. An Opus + Fable panel chose foreground waves."""
    text = _norm()
    assert (
        "dispatch up to 3 coders in ONE message of FOREGROUND Agent calls (the turn holds until the wave returns)"
        in text
    )
    assert (
        "Every coder dispatch — a wave, a fixup, a salvage review, a re-dispatch — is a FOREGROUND Agent call, so"
        " this check runs when the call returns, against the coder's wall-clock from dispatch;"
        in text
    )
    assert (
        "each passing `run_in_background=False`: they still run in parallel, and the turn holds until every one"
        " returns." in text
    )
    pattern = _section("### Dispatch pattern", "### Model selection")
    assert pattern.count("run_in_background=False,") == 3
    assert pattern.count('model="sonnet",') == 3


def test_a_small_sync_path_plan_runs_in_its_own_worktree() -> None:
    """Row 1791912630: a Profile: small plan in the main checkout on a governance-sync path would distribute every
    phase commit fleet-wide; it runs in an isolation worktree and reaches the fleet once, at the Finish merge."""
    text = re.sub(r"\s+", " ", SRC.read_text(encoding="utf-8"))
    assert (
        "a small plan whose owned paths include a governance-sync trigger path (the `governance-sync` files-filter"
        " in `.pre-commit-config.yaml`) runs in its own isolation worktree, step 8's `EnterWorktree` path even with"
        " no other plan-lock active"
    ) in text
    assert "its phases still commit one by one, and the plan reaches the fleet ONCE" in text
    assert (
        "or this is a `Profile: small` plan whose owned paths include a governance-sync trigger path"
        in text
    )
    assert "(step 8's concurrent-run or sync-path isolation; `BASE`" in text
    assert (
        "That hook run is the Finish sync; run `sync_enforcement_to_projects.py --force` by hand only when it"
        " prints a sync failure."
    ) in text


def test_a_wave_checks_fleet_headroom_and_a_plan_checker_is_dry_run() -> None:
    """Rows 1791975800 and 1791971650: a coder cut by the quota wall mid-ticket; rows 1791973720 and
    1791950554: a plan's identity diff showed its gaps only after a coder moved a type."""
    text = _norm()
    for needle in (
        "**Headroom before a wave:** act on the fleet's band — at AMBER or RED dispatch no new wave and say so"
        " on the Board.",
        "when the `QUOTA:` line's `successor` reads `none`, compare its `wall in ~<m>m` forecast for the hot"
        " window with the wave's summed ticket `Appetite:`",
        "**A plan-named checker is dry-run before its tickets' coders.** When a ticket's acceptance rests on a"
        " checker the plan names (an identity diff, a parity script, a snapshot compare), run it once on a"
        " throwaway head of the ticket's unit, a scratch build the orchestrator makes before the coder is dispatched"
        " and never commits (it is no ticket code)",
    ):
        assert needle in text, needle


def test_the_finish_docs_review_runs_before_the_finish_review() -> None:
    """Row 1792042079: the docs review excluded docs the receipt 'graded', which read as the Finish review first; a code
    defect a doc claim exposes must land inside the heavy review, as the Finish pseudo-code and D7 already order it."""
    text = _norm()
    assert "and BEFORE that review, so a code defect a doc claim exposes lands inside it" in text
    # the exclusion is computable before the review: the docs its `--init --changed` list will name (review_receipt.py
    # writes Hunt rows for those paths only), never rows a receipt that does not exist yet "graded"
    assert (
        "MINUS the docs the whole-plan `/fabrik-review`'s `--init --changed` list will name" in text
    )
    assert (
        "MINUS the docs §Finish's /fabrik-review --init --changed list will name, BEFORE that review"
        in text
    )
    assert "After item 5's docs review, run **`/fabrik-review`" in text
    for stale in (
        "receipt graded",
        "row that graded each",
        "heavy review graded",
        "--init rows name",
    ):
        assert stale not in text, stale
    assert text.index("run /fabrik-docs-review over the changed docs") < text.index(
        "run §Finish: /fabrik-review"
    )


def test_a_backlog_referrer_is_repointed_through_the_work_store() -> None:
    """Row 1792251373: Finish step 6 told the finisher to repoint rows in `docs/STRATEGIC_BACKLOG.md`, whose open items
    are a block `work.py render` writes from each item's `title`, so a row edited apart from its item is overwritten. The sentence is asserted whole,
    between the clause before it and the sentence after it, so a dropped or appended exception fails it."""
    assert (
        "IN THIS SAME COMMIT** — `docs/STRATEGIC_BACKLOG.md` (rows routed out of its reviews) for any plan worth executing; a row "
        "inside that file's `AUTO-GENERATED:BACKLOG` block is written by `work.py render` from its work item, the "
        "block's only writer (`docs/reference/work-tracking.md`), so change the item in `.fabrik/work/<id>.json` (a"
        " delivered one closes with `work.py done <id> --evidence <sha>`) and run `work.py render` rather than "
        "editing the row. Doc Link Integrity DOES catch a missed one"
    ) in _norm()


def test_a_linked_worktree_grades_its_own_tree_not_a_shared_runtime() -> None:
    """Row 1792337134 (recurrence of the held clone-proof-uses-docker-run): a gate or live request served by a shared
    runtime that mounts the main checkout runs MAIN's code, so the sentence points at the doc that says how to prove the
    tree's own code, and D7's live request points back at it."""
    assert (
        "against the two-level rule above. In any linked worktree, a gate or live request that a shared runtime serves (a"
        " container or service mounting the main checkout) runs MAIN's code, not this tree's; prove this tree's code as"
        " `/opt/fabrik/docs/reference/multi-agent-operating-model.md` § The shared runtime is NOT isolated says."
        " - **Verify your owned paths are clean:**"
    ) in _norm()
    assert (
        "issued against the running service (from a linked worktree, read Before You Start step 8 first), with"
        " its actual" in _norm()
    )
    doc = re.sub(
        r"\s+", " ", (ROOT / "docs" / "reference" / "multi-agent-operating-model.md").read_text()
    )
    assert "## The shared runtime is NOT isolated" in doc
    assert "running the worktree's code in-process against a throwaway database clone" in doc


def test_finish_step_5_says_the_run_flips_its_own_plan_and_when_the_coordinator_does() -> None:
    """Row 1792345477: the template gives the coordinator a finished plan's EXECUTED flip with no condition, so step 5
    names the run as the flipper, and the archiver as step 6 allows, at every position and quotes the hub charter's condition verbatim."""
    assert (
        "flip the plan `Status: EXECUTED <date>` (this run flips its own plan, and archives it as step 6 allows, at every"
        " position, (c)"
        ' included; in the hub the coordinator does both only "once every ticket is merged and its builder confirms no run will resume it",'
        " `/opt/fabrik/docs/reference/agents/coordinator.md`), **and cite the step-1 whole-plan review artifact"
    ) in _norm()
    charter = re.sub(
        r"\s+", " ", (ROOT / "docs" / "reference" / "agents" / "coordinator.md").read_text()
    )
    assert "once every ticket is merged and its builder confirms no run will resume it" in charter


def test_the_loop_step_names_the_phase_review_artifact() -> None:
    """Rows 1792433336, 1792472008, 1792465109: the artifact rule sat only in item 3b, so the loop step never said it."""
    loop = _section("/fabrik-review on phase's changed surface", "UPDATE THE PLAN FILE")
    # pinned from the line before to the line after, so a prefixed or appended clause turns it red
    assert (
        "THEN next phase → before the phase's closing commit (the one that stages the plan file), write its receipt to"
        " docs/development/reviews/ as `<plan-stem>-phase-<N>-review.md`, `<plan-stem>` being the plan file's whole"
        " stem (when it starts with a `<date>-plan-<n>-` prefix, that prefix keeps it findable after a resume; without"
        " one, a resumed run finds the earlier receipts only when it was started with `command_run.py start"
        " --resume-from <seed>`, which keeps the original start time, and a seed exists only after a `blocked` close"
        " at the quota wall (`--wall`, or a reason naming the wall) or an operator's pause (`--paused`); after a crash"
        " or a `handoff`, waive each earlier phase whose receipt the gate cannot see,"
        " naming that receipt in the reason); under `Profile: small` there is no file,"
        " so pass item 3b's `--review-waived` on the next `step` call instead — `step --phase N+1` refuses without"
        " one (item 3b's artifact rule) fix CONFIRMED findings"
    ) in loop
    item_3b = _section("3b. **GUI phases", "4. **All HARD STOPS")
    assert "(only a `<date>-plan-<n>` stem has the escape)" in item_3b, (
        "item 3b lost the unprefixed-stem limit"
    )
    assert "or starting with the plan's `<date>-plan-<n>-` prefix)" in item_3b, (
        "item 3b lost the prefix escape"
    )
    assert (
        "the waiver is for a phase that has none, or for an unprefixed plan's earlier receipt that a resume without a"
        " seed cannot see (named in the reason)."
    ) in item_3b
    assert 'goes through `--review-waived "<reason>"`' in item_3b
    assert '`--review-waived "Profile: small' in item_3b
