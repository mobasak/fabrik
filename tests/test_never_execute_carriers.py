"""W-a86563c9: the never-execute rule (D-850) rides every surface that executes a script.

D-850 carried it to the three places SEAT rules live (the fragment, fabrik-reviewer's house rules,
the review-loop workflow). This grader pins the rest: the orchestrator's own execute rules
(term-coverage and term-edit round-zero rule (1), fabrik-review Phase 2), the two other agents
with a Bash tool, subagents-core's cwd-rooted-tool rule (final_gate's caches) and
fabrik-command-improve's scratch-repo verb rule (hard-coded live paths). Each assertion reads the
source the rule is written in, and the last one reads the RENDERED corpus the agents receive.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMD = ROOT / "commands"

CLAUSE = "deletes, deploys, provisions, writes outside"
ORCHESTRATOR = "EXECUTING A CLAIM NEVER RUNS A DESTRUCTIVE SCRIPT LIVE"


def _read(rel: str) -> str:
    return (CMD / rel).read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    head = text.index(start)
    return text[head : text.index(end, head)]


def test_orchestrator_execute_rules_carry_the_carve_out() -> None:
    for rel in ("_fragments/term-coverage.md", "_fragments/term-edit.md"):
        text = _read(rel)
        assert ORCHESTRATOR in text, rel
        rule = text[text.index(ORCHESTRATOR) :]
        assert CLAUSE in rule[:1200], rel
        assert "hard-codes" in rule[:1200], rel


def test_fabrik_review_phase_2_points_at_the_carve_out() -> None:
    phase2 = _section(_read("_sources/fabrik-review.md"), "## Phase 2", "## Phase 3")
    assert "term-coverage.md` rule (1)" in phase2
    assert "destructive" in phase2


def test_bash_agents_carry_the_never_execute_clause() -> None:
    for rel in ("_agents/design-review.md", "_agents/fabrik-gui.md"):
        text = _read(rel)
        assert "read a script before you execute it, its `--help` included" in text, rel
        assert "never execute one that " + CLAUSE in text, rel
        assert "executing includes importing it and calling a function, `runpy`, a test that runs it" in text, rel


def test_subagents_core_roots_final_gate_in_the_copy() -> None:
    text = _read("_fragments/subagents-core.md")
    rule = text[text.index("a tool that roots itself at the working directory") :][:900]
    assert "`scripts/final_gate.py`" in rule
    assert "`.mypy_cache`" in rule and "`.ruff_cache`" in rule


def test_command_improve_scratch_repo_rule_names_hard_coded_paths() -> None:
    phase3 = _section(_read("_sources/fabrik-command-improve.md"), "## PHASE 3", "## PHASE 4")
    verb = phase3[phase3.index("a verb is run end to end in a scratch repo") :]
    assert "hard-codes" in verb[:1500]
    assert "`scripts/proof_run.py`" in verb[:1500]


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
    for agent in ("design-review", "fabrik-gui", "fabrik-reviewer"):
        assert "never execute one that " + CLAUSE in (out / "_agents" / f"{agent}.md").read_text(encoding="utf-8"), agent
    assert "hard-codes" in (out / "fabrik-command-improve.md").read_text(encoding="utf-8")
