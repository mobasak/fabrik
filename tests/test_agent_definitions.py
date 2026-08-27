"""The subagent definitions are GENERATED from the repo, not hand-authored on the box.

Before this, `~/.claude/agents/` held four definitions (214 lines) that existed ONLY on this
machine: no repo source, no generator, not in git, invisible to `check_command_corpus.py` and to
every sync. Three consequences, all real:

- a defect in a subagent's brief could not be reviewed, because there was nothing to diff;
- the corpus check audited 31 commands and 31 skills while the agents those commands DISPATCH were
  outside its jurisdiction entirely — the same blind spot that once left the orchestrator wrappers
  unaudited (`docs/reference/command-corpus-check.md` § The orchestrator corpus);
- the obligations every command carries (the feedback duty) could not reach them.

The sources are now `commands/_agents/*.md` and the renderer owns the destination, exactly as it
already owns `~/.claude/commands` and `~/.claude/skills`.
"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("asm", REPO / "commands" / "assemble_commands.py")
assert _spec and _spec.loader
asm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(asm)

SRC = REPO / "commands" / "_agents"
MARKER = "## ⚠️ Machinery findings"


def _render() -> Path:
    tmp = Path(tempfile.mkdtemp())
    asm.render(tmp, tmp / "_skills", agents_dest=tmp / "_agents")
    return tmp / "_agents"


def test_every_source_agent_is_rendered():
    out = _render()
    srcs = {p.name for p in SRC.glob("*.md")}
    assert srcs, "no agent sources — the harness is broken, not the assertion"
    assert {p.name for p in out.glob("*.md")} == srcs


def test_every_rendered_agent_carries_the_machinery_duty():
    out = _render()
    missing = [p.name for p in out.glob("*.md") if MARKER not in p.read_text(encoding="utf-8")]
    assert not missing, f"agents shipping without the machinery duty: {missing}"


def test_the_duty_is_appended_once():
    out = _render()
    for p in out.glob("*.md"):
        assert p.read_text(encoding="utf-8").count(MARKER) == 1, p.name


def test_the_frontmatter_survives_rendering():
    """Claude Code parses `name:`/`description:`/tool fields out of the frontmatter — a renderer
    that disturbed the block would silently unregister the agent."""
    out = _render()
    for p in out.glob("*.md"):
        text = p.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{p.name}: frontmatter must lead the file"
        head = text.split("\n---", 1)[0]
        assert "name:" in head and "description:" in head, f"{p.name}: {head[:80]}"


def test_the_rendered_name_matches_the_filename():
    """A `name:` that disagrees with its filename registers an agent nobody can dispatch by path."""
    out = _render()
    for p in out.glob("*.md"):
        head = p.read_text(encoding="utf-8").split("\n---", 1)[0]
        declared = next(ln.split(":", 1)[1].strip() for ln in head.splitlines() if ln.startswith("name:"))
        assert declared == p.stem, f"{p.name} declares name: {declared}"


def test_a_generated_orphan_is_pruned_but_a_hand_authored_file_is_not():
    """Same contract the command renderer already keeps: prune what WE generated, never touch a file
    a human put there. Deleting an operator's local agent would be data loss."""
    out = _render()
    (out / "gone.md").write_text(asm.BANNER + "---\nname: gone\n---\n", encoding="utf-8")
    (out / "mine.md").write_text("---\nname: mine\n---\nhand-authored\n", encoding="utf-8")
    asm.render(out.parent, out.parent / "_skills", agents_dest=out)
    assert not (out / "gone.md").exists(), "a generated orphan must be pruned"
    assert (out / "mine.md").exists(), "a hand-authored file must survive"


def test_check_detects_drift_in_a_rendered_agent():
    """`--check` is what makes the sources CANONICAL rather than merely first."""
    out = _render()
    target = out / "fabrik-reviewer.md"
    target.write_text(target.read_text(encoding="utf-8") + "\nhand-edited\n", encoding="utf-8")
    drift = asm.agent_drift(out)
    assert any("fabrik-reviewer" in d for d in drift), drift


def test_the_live_box_matches_the_repo_sources():
    """The point of the whole change: what the box actually dispatches is what the repo says."""
    drift = asm.agent_drift(asm.AGENTS)
    assert drift == [], f"~/.claude/agents drifted from commands/_agents: {drift}"
