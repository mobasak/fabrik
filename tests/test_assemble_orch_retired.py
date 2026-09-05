"""T07a — the orchestrator-wrapper path is retired; the three mega sources render.

Plan `2026-09-03-plan-1-multi-agent-per-repo`, spec § Chain consolidation (c): the four mega docs
become THREE assembled corpus commands (`/fabrik-vision` · `/fabrik-epics` · `/fabrik-epics-review`)
and the 17 generated `fab-*` wrappers leave the assembler. One test per Behavior-Contract row, each
seen red against the pre-T07a assembler (render `SystemExit(2)` on the unfilled `questionbar` /
`subagents-core` placeholders; the retired names still importable; the keep-set still sparing the
`fab-*` wrappers from the prune; no NEXT row for the three).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
ASSEMBLER = REPO / "commands" / "assemble_commands.py"
_spec = importlib.util.spec_from_file_location("ac", ASSEMBLER)
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)

MEGA = ("fabrik-vision", "fabrik-epics", "fabrik-epics-review")
RETIRED_NAMES = (
    "ORCH_SOURCES",
    "TRAYCER_SKILLS",
    "_orch_phase_count",
    "_render_orch_wrapper",
    "_emit_orch_wrappers",
)
# The four tokens the ticket's `git grep -l` gate names; `-l` prints nothing on no match, which is
# the only shape that yields a checkable NOTHING (`-c` prefixes the filename on a hit).
RETIRED_TOKEN_RE = r"_traycer-skills\|fab-mega-0\|fab-ettw-\|epic-to-ticket-workflow"
SKILL_CAP = 1024


def _render(td: str, seed_skill: str | None = None) -> tuple[Path, Path, Path | None]:
    """Render to a temp tree; `seed_skill` pre-installs a wrapper in the INSTALLED shape — a real
    directory whose `SKILL.md` is a symlink into a tracked tree (the pre-T07a render symlinked
    `~/.claude/skills/<fab-*>/SKILL.md` → `docs/orchestrator/_traycer-skills/<fab-*>/SKILL.md`)."""
    tmp, sk, ag = Path(td), Path(td) / "_skills", Path(td) / "_agents"
    target = None
    if seed_skill:
        target = tmp / "_tracked" / seed_skill / "SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text(f"---\nname: {seed_skill}\n---\n\n{ac.SKILL_BANNER}\n")
        d = sk / seed_skill
        d.mkdir(parents=True)
        os.symlink(target, d / "SKILL.md")
    ac.render(tmp, sk, agents_dest=ag)
    return tmp, sk, target


def _skill_description(sk: Path, name: str) -> str:
    """The composed description exactly as Claude Code parses it — the YAML value, not the source."""
    text = (sk / name / "SKILL.md").read_text()
    end = text.index("\n---", 3)
    return yaml.safe_load(text[3:end])["description"]


def test_three_mega_sources_render_with_fragments_resolved_and_no_fab_wrapper():
    record_head = (ac.FRAG / "run-record.md").read_text().split("\n", 1)[0]
    feedback_head = (ac.FRAG / "close-feedback.md").read_text().split("\n", 1)[0]
    with tempfile.TemporaryDirectory() as td:
        tmp, sk, _ = _render(td)
        for name in MEGA:
            cmd = (tmp / f"{name}.md").read_text()
            assert "{{" not in cmd, f"{name}: unresolved placeholder survived the render"
            assert record_head in cmd, f"{name}: run-record fragment missing"
            assert f"--command {name} --phases" in cmd, f"{name}: run-record COMMAND not resolved"
            assert feedback_head in cmd, f"{name}: close-feedback fragment missing"
            wrapper = (sk / name / "SKILL.md").read_text()
            assert "{{" not in wrapper
            assert f"**Next in the pipeline:** {ac.NEXT[name]}" in wrapper, (
                f"{name}: NEXT not in wrapper"
            )
        assert not list(sk.glob("fab-*")), "a fab-* orchestrator wrapper was emitted"


def test_module_exposes_no_orchestrator_wrapper_names():
    for n in RETIRED_NAMES:
        assert not hasattr(ac, n), f"{n} still defined"
    assert ASSEMBLER.read_text().count("ORCH_SOURCES") == 0


def test_git_grep_for_retired_tokens_prints_nothing():
    r = subprocess.run(
        ["git", "grep", "-l", RETIRED_TOKEN_RE, "--", "commands/assemble_commands.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.stdout == "", f"retired tokens still present:\n{r.stdout}"
    assert r.returncode == 1, (
        f"git grep rc={r.returncode} stderr={r.stderr}"
    )  # 1 = no match, 0 = a hit


def test_render_prunes_an_installed_fab_wrapper_carrying_the_banner():
    with tempfile.TemporaryDirectory() as td:
        _, sk, target = _render(td, seed_skill="fab-mega-00-trigger")
        assert not (sk / "fab-mega-00-trigger").exists(), (
            "installed fab-* wrapper survived the prune"
        )
        assert target is not None and target.is_file(), (
            "the prune followed the symlink into the tracked tree"
        )
        assert ac.SKILL_BANNER in target.read_text()


def test_next_map_and_every_composed_description_fits_the_skill_cap():
    sources = sorted(p.stem for p in ac.SRC.glob("*.md"))
    assert set(MEGA) <= set(sources)
    with tempfile.TemporaryDirectory() as td:
        _, sk, _ = _render(td)
        review = _skill_description(sk, "fabrik-epics-review")
        assert "NEXT: per window: /fabrik-spec docs/development/epics/<its epic>.md" in review
        # the launch form the source mandates everywhere it states it (fabrik-epics-review.md:444,
        # :445, :470, :536): without the env a window gets no Agent-Name trailer, no charter
        assert "CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>" in review
        assert "/fabrik-vision when the work is multi-epic" in _skill_description(
            sk, "fabrik-rivals"
        )
        lengths = {name: len(_skill_description(sk, name)) for name in sources}
        over = {n: ln for n, ln in lengths.items() if ln > SKILL_CAP}
        assert not over, f"composed description over {SKILL_CAP}: {over}"
        assert len(lengths) == len(sources)  # the denominator: every source, not a hand-picked few
