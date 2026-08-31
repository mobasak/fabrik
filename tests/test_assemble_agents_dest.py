"""render() must never touch live ~/.claude/agents unless dest IS the live commands dir.

Red-proven 2026-08-31: two review finders' inspection renders (render(tmpdir) /
--dest /tmp/x) silently overwrote the live agent files — the STRATEGIC_BACKLOG
promotion trigger that landed this guard.
"""
import importlib.util
import tempfile
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "ac", Path(__file__).resolve().parents[1] / "commands" / "assemble_commands.py")
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)


def test_non_live_dest_render_never_touches_live_agents():
    live = ac.AGENTS
    before = {p.name: (p.stat().st_mtime_ns, p.stat().st_size) for p in live.glob("*.md")}
    with tempfile.TemporaryDirectory() as td:
        ac.render(Path(td))
        after = {p.name: (p.stat().st_mtime_ns, p.stat().st_size) for p in live.glob("*.md")}
        assert after == before, "non-live-dest render mutated live agents"
        assert (Path(td) / "_agents").is_dir(), "agents not co-located beside dest"
        assert list((Path(td) / "_agents").glob("*.md")), "co-located agents dir empty"


def test_explicit_agents_dest_still_honored():
    with tempfile.TemporaryDirectory() as td:
        ag = Path(td) / "custom-agents"
        ac.render(Path(td) / "cmds", agents_dest=ag)
        assert list(ag.glob("*.md")), "explicit agents_dest not used"
