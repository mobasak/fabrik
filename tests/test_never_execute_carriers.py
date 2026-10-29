"""W-a86563c9: the never-execute rule (D-850) rides every surface that executes a script.

D-850 carried it to the three places SEAT rules live (the fragment, fabrik-reviewer's house rules,
the review-loop workflow). This grader pins the rest: the orchestrator's own execute rules
(term-coverage and term-edit round-zero rule (1), fabrik-review Phase 2, fabrik-review-scoped,
delegated-reads), the two other agents with a Bash tool, subagents-core's writer-only gate line
and fabrik-command-improve's scratch-repo verb rule (hard-coded live paths). Each assertion reads
the source the rule is written in, and the last one reads the RENDERED corpus the agents receive.
No faked run is offered anywhere: a list of fakes is never complete (D-1338).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMD = ROOT / "commands"

CLAUSE = "deletes, deploys, provisions, writes outside"
ORCHESTRATOR = "EXECUTING A CLAIM NEVER RUNS A DESTRUCTIVE SCRIPT**"
SHORT = (
    "a script that deletes, deploys, provisions, writes outside scratch or contacts a non-local host is never run, "
    "faked or not, unless running it is the act the command itself exists to perform"
)


def _read(rel: str) -> str:
    return (CMD / rel).read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    head = text.index(start)
    return text[head : text.index(end, head)]


def test_orchestrator_execute_rules_carry_the_carve_out() -> None:
    residue = {
        "_fragments/term-coverage.md": "takes the per-finding BLOCKED escalation below",
        "_fragments/term-edit.md": "rather than what running the script DOES",
    }
    for rel, fail_closed in residue.items():
        text = _read(rel)
        assert text.count(ORCHESTRATOR) == 1, rel
        rule = text[text.index(ORCHESTRATOR) :][:1500]
        assert CLAUSE in rule and "never run to settle a claim, faked or not" in rule, rel
        assert "a path the script hard-codes" in rule, rel
        assert "a read-only probe (an HTTP status GET" in rule, rel
        assert fail_closed in rule, rel
        assert "fake that RAISES" not in text, rel


def test_lead_execute_rules_point_at_the_carve_out() -> None:
    phase2 = _section(_read("_sources/fabrik-review.md"), "## Phase 2", "## Phase 3")
    assert "`/opt/fabrik/commands/_fragments/term-coverage.md` rule (1)'s never-run clause" in phase2
    assert "is never run, faked or not, and takes" in phase2
    scoped = _read("_sources/fabrik-review-scoped.md")
    assert "yourself before you fix. In such a check " + SHORT in scoped
    assert "its candidate is paused and posted under `## BLOCKED`" in scoped
    delegated = _read("_fragments/delegated-reads.md")
    assert "EXECUTES every claim it writes" in delegated
    assert "In executing a claim, " + SHORT in delegated
    assert "a claim only such a run settles is deleted or reworded" in delegated


def test_bash_agents_carry_the_never_execute_clause() -> None:
    fit = {
        "_agents/design-review.md": "The preview environment your brief names, local or hosted",
        "_agents/fabrik-gui.md": "The project's own build, test and package toolchain",
    }
    for rel, own in fit.items():
        text = _read(rel)
        assert "read a script before you execute it, its `--help` included" in text, rel
        assert "never execute one that " + CLAUSE in text, rel
        assert "executing includes importing it and calling a function, `runpy`, a test that runs it" in text, rel
        assert "whatever binary does it, even when a step asks you to" in text, rel
        assert "name it in your report as not run, with the script's cited lines" in text, rel
        assert "else a folder of your own under the session scratchpad your harness prints, never its root" in text or (
            "else a folder of your own under the session scratchpad, never its root" in text
        ), rel
        assert own in text, rel


def test_subagents_core_keeps_final_gate_off_read_only_seats() -> None:
    text = _read("_fragments/subagents-core.md")
    assert "`-m pytest`, `scripts/final_gate.py --check` (bare," not in text
    rule = text[text.index("`scripts/final_gate.py --check` (never bare") :][:900]
    assert "is a WRITER seat's line (a seat its brief assigns files to edit)" in rule
    assert "a read-only seat never runs it" in rule
    assert "`.mypy_cache`" in rule and "`.ruff_cache`" in rule
    for flag in ("--basetemp=<its scratch dir>/pt", "`-m mypy --cache-dir=<its scratch dir>/mypy`", "`-m ruff check --no-cache`"):
        assert flag in text, flag


def test_command_improve_scratch_repo_rule_names_hard_coded_paths() -> None:
    phase3 = _section(_read("_sources/fabrik-command-improve.md"), "## PHASE 3", "## PHASE 4")
    verb = phase3[phase3.index("a verb is run end to end in a scratch repo") :]
    assert "A script that hard-codes a live path (`scripts/proof_run.py`'s" in verb[:1500]
    assert "so one that writes, deletes or deploys is read, never run" in verb[:1500]


def _renderer():
    spec = importlib.util.spec_from_file_location("ac_never_execute", CMD / "assemble_commands.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ac_never_execute"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_render_carries_every_clause(tmp_path: Path) -> None:
    out = tmp_path / "commands"
    out.mkdir()
    _renderer().render(out, None, agents_dest=out / "_agents")
    for name in ("fabrik-review", "fabrik-repo-review", "fabrik-plan-review", "fabrik-spec-review"):
        assert ORCHESTRATOR in (out / f"{name}.md").read_text(encoding="utf-8"), name
    for name in ("fabrik-review-scoped", "fabrik-spec", "fabrik-plan-after-chat", "fabrik-command-improve"):
        assert SHORT in (out / f"{name}.md").read_text(encoding="utf-8"), name
    for agent in ("design-review", "fabrik-gui", "fabrik-reviewer"):
        assert "never execute one that " + CLAUSE in (out / "_agents" / f"{agent}.md").read_text(encoding="utf-8"), agent
    improve = (out / "fabrik-command-improve.md").read_text(encoding="utf-8")
    assert "A script that hard-codes a live path" in improve and "fake that RAISES" not in improve
