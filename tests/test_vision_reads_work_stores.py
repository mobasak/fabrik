"""T05 — `/fabrik-vision` EXISTING reads the two work stores; `/fabrik-epics-review` mints the
merge-owner row (D-154, D-155; `docs/superpowers/specs/2026-09-06-multi-agent-adoption-design.md` § D4).

One test per Behavior-Contract row in
`docs/development/plans/2026-09-06-plan-2-multi-agent-adoption/T05-vision-and-epics-review-text.md`:
(1) the vision source's EXISTING-mode read list gains `docs/development/PLANS.md` +
`docs/STRATEGIC_BACKLOG.md`, and its epic-seed paragraph names `owner:` inheritance from a `[name]` tag;
(2) the epics-review source's Step 1.5 names `decisions.py --merge-owner` and the `MERGE OWNER:` row
mint; (3) the assembler renders both edited sources clean (no unresolved `{{...}}` placeholder, no
render error) and every composed skill description stays within the 1024-char cap Claude Code enforces.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
VISION = REPO / "commands" / "_sources" / "fabrik-vision.md"
EPICS_REVIEW = REPO / "commands" / "_sources" / "fabrik-epics-review.md"
ASSEMBLER = REPO / "commands" / "assemble_commands.py"
SKILL_CAP = 1024


def _load_assembler():
    spec = importlib.util.spec_from_file_location("_ac_t05", ASSEMBLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _skill_description(sk: Path, name: str) -> str:
    """The composed description exactly as Claude Code parses it — the YAML value."""
    text = (sk / name / "SKILL.md").read_text()
    end = text.index("\n---", 3)
    return yaml.safe_load(text[3:end])["description"]


# ---------------------------------------------------------------------------
# Row 1 — /fabrik-vision EXISTING-mode read list + epic-seed paragraph
# ---------------------------------------------------------------------------


def test_vision_existing_read_list_names_both_work_stores():
    text = VISION.read_text()
    # The bullet segment: from "EXISTING mode only" to the next top-level bullet
    # (the fabrik-lib vendor-ladder bullet) — the exact window the ticket's Behavior
    # Contract row names.
    m = re.search(
        r"- EXISTING mode only —.*?(?=\n- `/opt/fabrik-lib/README\.md`)",
        text,
        re.S,
    )
    assert m, "EXISTING mode only bullet (up to the fabrik-lib bullet) not found"
    segment = m.group(0)
    assert "docs/development/PLANS.md" in segment, (
        f"PLANS.md missing from the EXISTING-mode read list:\n{segment}"
    )
    assert "docs/STRATEGIC_BACKLOG.md" in segment, (
        f"STRATEGIC_BACKLOG.md missing from the EXISTING-mode read list:\n{segment}"
    )


def test_vision_epic_seed_paragraph_names_owner_inheritance_from_name_tag():
    text = VISION.read_text()
    m = re.search(
        r"\*\*The two work stores seed the same Scale Assessment / epic seeds.*?\n\n",
        text,
        re.S,
    )
    assert m, "epic-seed paragraph (Scale Assessment / epic seeds) not found"
    para = m.group(0)
    assert "docs/development/PLANS.md" in para
    assert "docs/STRATEGIC_BACKLOG.md" in para
    assert "[name]" in para, f"paragraph does not name the `[name]` tag:\n{para}"
    assert "owner: beta" in para, (
        f"paragraph does not spell out owner: inheritance from a [beta] row:\n{para}"
    )
    assert "D-154" in para, f"paragraph does not cite the ruling D-154:\n{para}"


# ---------------------------------------------------------------------------
# Row 2 — /fabrik-epics-review § Step 1.5 mints the merge-owner row
# ---------------------------------------------------------------------------


def test_epics_review_step_1_5_names_merge_owner_read_and_mint():
    text = EPICS_REVIEW.read_text()
    m = re.search(
        r"## Phase 2 — Step 1\.5.*?(?=\n## )",
        text,
        re.S,
    )
    assert m, "Phase 2 — Step 1.5 section not found"
    section = m.group(0)
    assert "decisions.py --merge-owner" in section, (
        f"Step 1.5 does not name `decisions.py --merge-owner`:\n{section}"
    )
    assert "UNDECLARED" in section
    assert "MERGE OWNER:" in section, (
        f"Step 1.5 does not name the MERGE OWNER: row mint:\n{section}"
    )
    assert "--next-id" in section, (
        f"Step 1.5 does not name minting the id via --next-id:\n{section}"
    )
    assert "D-154" in section, f"Step 1.5 does not cite the ruling D-154:\n{section}"


# ---------------------------------------------------------------------------
# Row 3 — the assembler renders both edited sources clean, within the skill cap
# ---------------------------------------------------------------------------


def test_edited_sources_render_clean_and_within_skill_cap():
    ac = _load_assembler()
    with tempfile.TemporaryDirectory() as td:
        tmp, sk, ag = Path(td), Path(td) / "_skills", Path(td) / "_agents"
        # render() sys.exit(2)s on ANY source's unresolved {{...}} placeholder or unknown
        # fragment — a bare successful return is itself the "zero render errors" proof.
        ac.render(tmp, sk, agents_dest=ag)
        for name in ("fabrik-vision", "fabrik-epics-review"):
            rendered = (tmp / f"{name}.md").read_text()
            assert "{{" not in rendered, f"{name}: unresolved placeholder survived the render"
            desc = _skill_description(sk, name)
            assert len(desc) <= SKILL_CAP, f"{name}: composed description {len(desc)} > {SKILL_CAP}"


def test_assemble_commands_check_reports_no_render_error_and_only_expected_drift():
    """`assemble_commands.py --check` diffs the render against the INSTALLED corpus
    (`~/.claude/commands`) — from a worktree whose two sources are edited but not yet
    box-wide-rendered, that installed copy is expected to differ (T05's own DO-NOT: never
    render from a worktree). The invariant this test owns is narrower and environment-
    independent: the check never crashes, never reports a RENDER ERROR/unresolved
    placeholder, and any drift it does report names only the two files this ticket
    touched (or is empty once installed catches up) — never an unrelated command."""
    out = Path.home() / ".claude" / "commands"
    if not out.exists():
        pytest.skip("~/.claude/commands absent in this environment — nothing installed to diff")
    result = subprocess.run(
        [sys.executable, str(ASSEMBLER), "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "Traceback" not in result.stderr, f"--check crashed:\n{result.stderr}"
    assert "RENDER ERRORS" not in result.stdout, f"--check hit a render error:\n{result.stdout}"
    if result.returncode == 0:
        return  # installed corpus already caught up with this change — fully converged
    assert result.returncode == 1, (
        f"unexpected exit {result.returncode} (stdout={result.stdout!r} stderr={result.stderr!r})"
    )
    allowed = ("fabrik-vision", "fabrik-epics-review")
    lines = result.stdout.splitlines()
    assert "DRIFT:" in lines, f"exit 1 with no DRIFT: header — unexpected shape:\n{result.stdout}"
    # only the lines AFTER the "DRIFT:" header are per-item findings (`print(" -", x)`); the
    # line(s) before it are render()'s own "rendered N commands -> ..." status line(s).
    for raw in lines[lines.index("DRIFT:") + 1 :]:
        item = raw.strip(" -")
        assert item.split(":", 1)[0].split("/")[-1].startswith(allowed), (
            f"drift outside the two edited sources: {item}"
        )
