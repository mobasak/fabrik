"""T05 — `/fabrik-vision` EXISTING reads the two work stores; `/fabrik-epics-review` mints the
merge-owner row (D-154, D-155; `docs/superpowers/specs/2026-09-06-multi-agent-adoption-design.md` § D4).

One test per Behavior-Contract row in
`docs/development/plans/2026-09-06-plan-2-multi-agent-adoption/T05-vision-and-epics-review-text.md`:
(1) the vision source's EXISTING-mode read list gains `docs/development/PLANS.md` +
`docs/STRATEGIC_BACKLOG.md`, and its epic-seed paragraph names `owner:` inheritance from a `[name]` tag;
(2) the epics-review source's Step 1.5 names `decisions.py --merge-owner` and the `MERGE OWNER:` row
mint; (3) the assembler renders both edited sources clean (no unresolved `{{...}}` placeholder, no
render error) and every composed skill description stays within the 1024-char cap Claude Code enforces,
AND `check_command_corpus.py` — the other half of that gate pair — exits clean.

Round-1 acceptance review (native Opus finder + pool trio) found the vision source carries THREE
parallel EXISTING-mode read enumerations — Phase 0's acting-set bullet (:63-66), Phase 2's `Reads from
the project itself` bullet, and the E-analysis `Read existing project state` load-step — and only the
first had been extended, so the step that actually OPENS the files never named the two work stores.
`test_vision_existing_read_list_names_both_work_stores` below now bounds-greps all three. It also found
`check_command_corpus.py` was never invoked despite being named in Behavior-Contract row 3 (fixed by
`test_check_command_corpus_exits_clean`).
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
CORPUS_CHECK = REPO / "scripts" / "enforcement" / "check_command_corpus.py"
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


def _segment(text: str, pattern: str, label: str) -> str:
    m = re.search(pattern, text, re.S)
    assert m, f"{label} not found"
    return m.group(0)


# ---------------------------------------------------------------------------
# Row 1 — /fabrik-vision EXISTING-mode read list (all THREE enumerations) +
# epic-seed paragraph
# ---------------------------------------------------------------------------


def test_vision_existing_read_list_names_both_work_stores():
    text = VISION.read_text()

    # (a) Phase 0's acting-set bullet: "EXISTING mode only" up to the fabrik-lib bullet.
    acting_set = _segment(
        text,
        r"- EXISTING mode only —.*?(?=\n- `/opt/fabrik-lib/README\.md`)",
        "Phase 0's EXISTING-mode-only acting-set bullet",
    )
    assert "docs/development/PLANS.md" in acting_set, (
        f"PLANS.md missing from the Phase-0 acting-set bullet:\n{acting_set}"
    )
    assert "docs/STRATEGIC_BACKLOG.md" in acting_set, (
        f"STRATEGIC_BACKLOG.md missing from the Phase-0 acting-set bullet:\n{acting_set}"
    )

    # (b) Phase 2's "Reads from the project itself:" bullet — a SEPARATE enumeration.
    required_inputs = _segment(
        text,
        r"\*\*Reads from the project itself:\*\*.*?(?=\n\n\*\*⚠ Project files may be pre-rules)",
        "Phase 2's `Reads from the project itself:` bullet",
    )
    assert "docs/development/PLANS.md" in required_inputs, (
        f"PLANS.md missing from the Phase-2 required-inputs bullet:\n{required_inputs}"
    )
    assert "docs/STRATEGIC_BACKLOG.md" in required_inputs, (
        f"STRATEGIC_BACKLOG.md missing from the Phase-2 required-inputs bullet:\n{required_inputs}"
    )
    assert "Merge owner" in required_inputs, (
        f"the <!-- Merge owner: ... --> header not named in the Phase-2 bullet:\n{required_inputs}"
    )

    # (c) The E-analysis "Read existing project state" load-step — the bullet that
    # actually OPENS the files, distinct from the two enumerations above.
    load_step = _segment(
        text,
        r"\*\*Read existing project state\*\*.*?(?=\n- `\.windsurf/rules/` — synced from this repo)",
        "the E-analysis `Read existing project state` load-step",
    )
    assert "docs/development/PLANS.md" in load_step, (
        f"PLANS.md missing from the E-analysis load-step:\n{load_step}"
    )
    assert "docs/STRATEGIC_BACKLOG.md" in load_step, (
        f"STRATEGIC_BACKLOG.md missing from the E-analysis load-step:\n{load_step}"
    )
    assert "Merge owner" in load_step, (
        f"the <!-- Merge owner: ... --> header not named in the E-analysis load-step:\n{load_step}"
    )


def test_vision_epic_seed_paragraph_names_owner_inheritance_from_name_tag():
    para = _segment(
        VISION.read_text(),
        r"\*\*The two work stores seed the same Scale Assessment / epic seeds.*?\n\n",
        "epic-seed paragraph (Scale Assessment / epic seeds)",
    )
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
    section = _segment(
        EPICS_REVIEW.read_text(),
        r"## Phase 2 — Step 1\.5.*?(?=\n## )",
        "Phase 2 — Step 1.5 section",
    )
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
# Row 3 — the assembler renders both edited sources clean, within the skill cap,
# AND check_command_corpus.py exits clean (the other half of the gate pair)
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


def test_check_command_corpus_exits_clean():
    """Behavior-Contract row 3 names BOTH `assemble_commands.py --check` and
    `check_command_corpus.py` as the row-3 gate pair — round-1 review, defect 3: the
    suite never invoked the second half."""
    if not CORPUS_CHECK.exists():
        pytest.skip(f"{CORPUS_CHECK} absent in this environment")
    result = subprocess.run(
        [sys.executable, str(CORPUS_CHECK)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"check_command_corpus.py exited {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
