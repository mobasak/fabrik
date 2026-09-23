"""Chunk 7 (D-363) — the producing commands delegate large reads, rank approaches by a judge panel, and close in
four calls.

`/fabrik-spec` includes all three fragments; `/fabrik-plan-after-chat` includes the delegated reads and the close
but no judge panel — it never selects an approach itself (a THIN input routes to `/fabrik-spec`). The rendered
text is graded through the assembler's own `--check`; these pins grade the SOURCE contract the render expands.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCES = REPO / "commands" / "_sources"
FRAGS = REPO / "commands" / "_fragments"


def _includes(name: str) -> list[str]:
    return re.findall(r"^\{\{include:([\w-]+)\}\}$", (SOURCES / f"{name}.md").read_text(), re.M)


def test_each_producing_command_includes_the_fragments_its_shape_needs() -> None:
    spec = _includes("fabrik-spec")
    plan = _includes("fabrik-plan-after-chat")
    for frag in ("delegated-reads", "judge-panel", "close-chain"):
        assert frag in spec, f"/fabrik-spec lacks {frag}"
    assert "delegated-reads" in plan and "close-chain" in plan
    assert "judge-panel" not in plan, (
        "plan-after-chat selects no approach itself; a panel there ranks nothing"
    )


def test_the_close_chain_runs_its_four_calls_in_order_with_the_artifact_committed_before_the_ledgers() -> (
    None
):
    body = " ".join((FRAGS / "close-chain.md").read_text().split())
    marks = [body.index(m) for m in ("(1)", "(2)", "(3)", "(4)")]
    assert marks == sorted(marks), "the four calls are numbered in order"
    two = body[marks[1] : marks[2]]
    assert two.index("explicit pathspec FIRST") < two.index("private-index recipe"), (
        "the Doc Sync check reads only the staged diff: a ledger committed first reads missing"
    )
    assert "final_gate.py --check --json" in body[marks[2] : marks[3]]
    assert "--feedback" in body[marks[3] :], "a close without --feedback is refused by the tool"
    assert body.index("BEFORE the chain") < marks[0], "the inputs are written before call (1)"


def test_the_judge_panel_brief_never_carries_the_leads_recommendation() -> None:
    body = " ".join((FRAGS / "judge-panel.md").read_text().split())
    assert "WITHOUT your recommendation" in body
    assert "THREE" in body and "ONE message" in body


def test_a_delegated_read_returns_anchored_claims_the_lead_still_executes() -> None:
    body = " ".join((FRAGS / "delegated-reads.md").read_text().split())
    assert "`path:line`" in body and "EXECUTES every claim" in body
    assert "never evidence" in body


def test_the_close_chain_pushes_and_the_panel_brief_is_neutral() -> None:
    """Review of chunk 7, pass 1: the chain never pushed (A-S3), and a write-up that led with the lead's pick
    leaked it to the 'blind' panel (A-S1)."""
    close = " ".join((FRAGS / "close-chain.md").read_text().split())
    assert "`git push` (never `--force`; a rejected push takes CLAUDE.md § EXIT's ladder)" in close
    panel = " ".join((FRAGS / "judge-panel.md").read_text().split())
    assert "alphabetical order at equal depth" in panel and "only after the panel returns" in panel


def test_every_artifact_check_the_close_names_is_a_real_script_and_flag() -> None:
    """Review of chunk 7, A-S4: the ARTIFACT_CHECK strings render into two commands and nothing checked them."""
    import importlib.util
    import subprocess
    import sys

    spec = importlib.util.spec_from_file_location(
        "assemble_probe", REPO / "commands" / "assemble_commands.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    for command in ("fabrik-spec", "fabrik-plan-after-chat"):
        text = mod.PARAMS[command]["close-chain"]["ARTIFACT_CHECK"]
        calls = re.findall(r"`python3 (scripts/\S+\.py)([^`]*)`", text)
        assert calls, (command, text)
        for script, rest in calls:
            assert (REPO / script).is_file(), script
            helptext = subprocess.run(
                [sys.executable, str(REPO / script), "--help"],
                capture_output=True,
                text=True,
                timeout=60,
                stdin=subprocess.DEVNULL,
                check=False,
            ).stdout
            for flag in re.findall(r"--[^\s`<>]+", rest):
                assert re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", helptext), (
                    command,
                    script,
                    flag,
                )


_DELEGATED = {
    "fabrik-spec",
    "fabrik-plan-after-chat",
    "fabrik-ui-design",
    "fabrik-vision",
    "fabrik-epics",
    "fabrik-flows",
    "fabrik-rivals",
    "fabrik-deploy-plan",
    "fabrik-user-test",
    "fabrik-service-test",
    "fabrik-catchup",
    "fabrik-command-improve",
    "fabrik-release",
    "fabrik-deploy",
    "fabrik-deploy-verify",
    "fabrik-decommission",
    "fabrik-upstream",
    "fabrik-generate-tests",
    "fabrik-execute-plan",
    "fabrik-data-contract",
    "fabrik-features",
    "fabrik-deploy-checklist",
    "fabrik-doc-converge",
}


def test_every_command_but_the_task_lane_closes_through_the_chain_and_the_readers_delegate() -> (
    None
):
    """Chunk 7 rollout: the four-call close is the edit every command shares (§ 5.3) — /fabrik-task alone keeps its
    own close; delegated reads go to the commands that read large sources themselves, never to the review family,
    whose seats read."""
    names = sorted(p.stem for p in SOURCES.glob("*.md"))
    assert len(names) >= 38, len(names)
    missing_close = [n for n in names if n != "fabrik-task" and "close-chain" not in _includes(n)]
    assert not missing_close, missing_close
    assert "close-chain" not in _includes("fabrik-task"), "/fabrik-task keeps its own close (§ 5.3)"
    assert {n for n in names if "delegated-reads" in _includes(n)} == _DELEGATED


def test_the_assembler_fills_the_close_chain_for_a_command_with_no_params() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "assemble_probe2", REPO / "commands" / "assemble_commands.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    assert "close-chain" not in mod.PARAMS.get("fabrik-rivals", {}), (
        "the default path is what this grades"
    )
    src = (REPO / "commands" / "assemble_commands.py").read_text()
    assert 'if fr == "close-chain":' in src and 'params.setdefault("COMMAND", name)' in src


def test_the_close_chain_follows_every_section_of_the_command_and_yields_to_its_own_close() -> None:
    """Rollout review, pass 1: an include placed mid-file put the close before the run record (design-review),
    before the phases (workflow-review) and before the sections its `done` consumes (review, deploy-checklist);
    and a generic chain appended to a command with its own close contradicted it. (The assembler's close-out
    feedback block still follows the chain in the render — the chain follows every section of the command's OWN text.) (halted, refused, handoff,
    blocked and paused exits; a different order)."""
    late = [
        p.stem
        for p in SOURCES.glob("*.md")
        if "{{include:close-chain}}" in p.read_text()
        and p.read_text().rstrip("\n").splitlines()[-1] != "{{include:close-chain}}"
    ]
    assert not late, late
    body = " ".join((FRAGS / "close-chain.md").read_text().split())
    assert "this command's own close text wins wherever it names something else" in body
    assert "the close this command's own text names for how the run ended" in body
    assert "It runs BEFORE the response's closing seven-line block" in body, (
        "a chain placed after an Output section must still run before it (review pass 2)"
    )
