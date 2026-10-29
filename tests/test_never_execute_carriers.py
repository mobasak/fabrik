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


POINTER = "`/opt/fabrik/commands/_fragments/term-coverage.md` rule (1)'s never-live clause"
INLINE = "a script that deletes, deploys, provisions, writes outside scratch or contacts a non-local host is never run live"


def test_orchestrator_execute_rules_carry_the_carve_out() -> None:
    residue = {
        "_fragments/term-coverage.md": "BLOCKED-escalated as missing infra",
        "_fragments/term-edit.md": "DELETED or reworded to what the pinned lines say",
    }
    for rel, fail_closed in residue.items():
        text = _read(rel)
        assert ORCHESTRATOR in text, rel
        rule = text[text.index(ORCHESTRATOR) :][:1600]
        assert CLAUSE in rule and "hard-codes" in rule, rel
        assert "replaced by a fake that RAISES" in rule, rel
        assert fail_closed in rule, rel


def test_lead_execute_rules_point_at_the_carve_out() -> None:
    phase2 = _section(_read("_sources/fabrik-review.md"), "## Phase 2", "## Phase 3")
    assert POINTER in phase2
    # the two inline forms cite no path: a cited fragment counts as a read against every includer's word ceiling
    scoped = _read("_sources/fabrik-review-scoped.md")
    assert "yourself before you fix. In such a check " + INLINE in scoped
    assert "a candidate no such run settles is BLOCKED-escalated" in scoped
    delegated = _read("_fragments/delegated-reads.md")
    assert "EXECUTES every claim it writes" in delegated
    assert "In executing a claim, " + INLINE in delegated
    assert "a claim no such run settles is deleted or reworded" in delegated


def test_bash_agents_carry_the_never_execute_clause() -> None:
    fit = {
        "_agents/design-review.md": "your scratch dir is the folder your brief names",
        "_agents/fabrik-gui.md": "the local preview server you drive is not a non-local host",
    }
    for rel, own in fit.items():
        text = _read(rel)
        assert "read a script before you execute it, its `--help` included" in text, rel
        assert "never execute one that " + CLAUSE in text, rel
        assert "executing includes importing it and calling a function, `runpy`, a test that runs it" in text, rel
        assert own in text, rel


def test_subagents_core_keeps_final_gate_off_read_only_seats() -> None:
    text = _read("_fragments/subagents-core.md")
    assert "`-m pytest`, `scripts/final_gate.py --check` (bare," not in text
    rule = text[text.index("`scripts/final_gate.py --check` (never bare") :][:900]
    assert "is a WRITER seat's line" in rule and "a read-only seat never runs it" in rule
    assert "`.mypy_cache`" in rule and "`.ruff_cache`" in rule
    assert "`ruff check --no-cache`" in text and "`-m mypy --cache-dir=<its scratch dir>/mypy`" in text


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
    for name in ("fabrik-review-scoped", "fabrik-spec", "fabrik-plan-after-chat"):
        assert INLINE in (out / f"{name}.md").read_text(encoding="utf-8"), name
    for agent in ("design-review", "fabrik-gui", "fabrik-reviewer"):
        assert "never execute one that " + CLAUSE in (out / "_agents" / f"{agent}.md").read_text(encoding="utf-8"), agent
    assert "hard-codes" in (out / "fabrik-command-improve.md").read_text(encoding="utf-8")
