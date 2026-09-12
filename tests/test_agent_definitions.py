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


def test_a_blank_line_in_the_frontmatter_fails_the_render_loudly():
    """The defect that hid `fabrik-reviewer` from the agent roster: a second paragraph inside the
    `description:` scalar. A blank line at column 0 ends a plain YAML scalar, so the loader dropped
    the definition — while every check stayed green, because the FILE renders perfectly. The only
    symptom was a Task dispatch answering "agent type not found", mid-review, one seat short."""
    good = "---\nname: x\ndescription: one line\ntools: Read\n---\n\nbody\n"
    assert asm._agent_frontmatter_defect(good) is None
    bad = "---\nname: x\ndescription: one line\n\n**A second paragraph.**\n\ntools: Read\n---\n\nbody\n"
    assert "blank line" in (asm._agent_frontmatter_defect(bad) or "")
    assert "no `name:` key" in (
        asm._agent_frontmatter_defect("---\ndescription: d\n---\nb\n") or ""
    )
    assert asm._agent_frontmatter_defect("no frontmatter at all\n")


def test_every_agent_source_would_actually_register():
    """The live sources, not a fixture: each must survive the loader, or the seat does not exist."""
    broken = {
        p.name: asm._agent_frontmatter_defect(p.read_text(encoding="utf-8"))
        for p in SRC.glob("*.md")
    }
    assert not {k: v for k, v in broken.items() if v}, broken


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
        declared = next(
            ln.split(":", 1)[1].strip() for ln in head.splitlines() if ln.startswith("name:")
        )
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


def test_every_agent_definition_carries_the_git_verb_prohibition():
    """Spec D8 (pass 3): every native seat definition carries the shared git-verb sentence — a
    reviewer seat's `git stash --keep-index` swept three sessions' uncommitted work mid-pass
    (2026-09-11). Asserted on the SOURCES, per file, by the key phrase."""
    phrase = "no git command that mutates state"
    srcs = sorted(SRC.glob("*.md"))
    assert len(srcs) == 4, [p.name for p in srcs]
    missing = [p.name for p in srcs if phrase not in p.read_text(encoding="utf-8").lower()]
    assert not missing, missing


def test_the_stash_recovery_recipe_is_byte_identical_in_both_contracts():
    """The recipe sentence (pass 3, spec D8) lives INSIDE the § Shared repo bullet of both
    contracts; the bullets differ by design, the recipe substring — from the start anchor to the
    end anchor inclusive — must not."""
    start, end = "git stash show --name-only 'stash@{0}'", "never a pop"

    def recipe(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        i = text.find(start)
        assert i >= 0, f"{path.name}: start anchor absent"
        j = text.find(end, i)
        assert j >= 0, f"{path.name}: end anchor absent after the start anchor"
        return text[i : j + len(end)]

    hub = recipe(REPO / "CLAUDE.md")
    tpl = recipe(REPO / "templates" / "governance" / "CLAUDE.md")
    assert hub == tpl
    assert "git show 'stash@{0}':<path>" in hub


def test_the_mail_triage_agent_sentences_are_present_once():
    """T2.12: the reviewer reads a materialised tree or a commit with `git -C <repo> show`;
    T2.19: the researcher names the two exa web_fetch drops (tables, late sections)."""
    reviewer = (SRC / "fabrik-reviewer.md").read_text(encoding="utf-8")
    researcher = (SRC / "fabrik-researcher.md").read_text(encoding="utf-8")
    assert reviewer.count("with `git -C <repo>` when the repo is not your cwd") == 1
    assert researcher.count("silently DROPS TABLES") == 1
