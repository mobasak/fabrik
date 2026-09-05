#!/usr/bin/env python3
# AFTER-EDIT: scripts/review_rubric.py
"""Edge-case tests for review_rubric.py — promote-to-check_* byproduct, missing pack/checklist
fallback, and CLI exit codes.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "review_rubric", REPO / "scripts" / "review_rubric.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["review_rubric"] = mod
    spec.loader.exec_module(mod)
    return mod


def _mk_pack(root: Path, rel: str, globs: list[str], mandates: list[str]) -> None:
    p = root / ".windsurf" / "rules" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    glob_str = ", ".join(f'"{g}"' for g in globs)
    body = "\n".join(mandates)
    p.write_text(
        f"---\nactivation: glob\nglobs: [{glob_str}]\ndescription: test pack {rel}\n---\n\n"
        f"# {rel}\n\n{body}\n",
        encoding="utf-8",
    )


def _mk_tree(root: Path) -> None:
    """Minimal rules tree: the 3 floor packs + one glob pack, + both checklists."""
    for floor_rel, mandate in [
        ("core/35-security-auth.md", "- Auth MUST use Pattern A (`fastapi-user-auth`)."),
        (
            "core/25-data-postgres.md",
            "- Never use `localhost` as a DB host — `postgres-main:5432`.",
        ),
        (
            "core/30-ops.md",
            "- Every compose service MUST declare `deploy.resources.limits.memory`.",
        ),
    ]:
        _mk_pack(root, floor_rel, ["**/nonexistent-floor-trigger-*.xyz"], [mandate])
    _mk_pack(
        root,
        "core/99-zzz-test.md",
        ["**/*.zzz"],
        ["- Files of type zzz MUST be frobnicated.", "- ⚠️ never defrobnicate in prod."],
    )
    mega = root / "docs" / "orchestrator" / "mega-epic-breakdown"
    ettw = root / "docs" / "orchestrator" / "epic-to-ticket-workflow"
    mega.mkdir(parents=True)
    ettw.mkdir(parents=True)
    (mega / "EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md").write_text(
        "# Mega checklist\n\n1. Does it respect the mega lifecycle?\n2. Is the vision persisted?\n",
        encoding="utf-8",
    )
    (ettw / "EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md").write_text(
        "# Ettw checklist\n\n1. Does it reference the 4-stage lifecycle?\n2. Is INFRA-CHECK emitted?\n",
        encoding="utf-8",
    )


# ── Test 1: promote-to-check_* byproduct ──────────────────────────────────────────


def test_promote_section_emitted_when_greppable_mandates_exist(tmp_path):
    """A floor/matched mandate containing a backticked literal produces a
    '# promote-to-check_*:' section listing it."""
    _mk_tree(tmp_path)
    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)

    # The floor packs all carry backtick literals
    assert "# promote-to-check_*:" in out, "promote section header should be present"
    assert "fastapi-user-auth" in out
    assert "postgres-main" in out
    assert "deploy.resources.limits.memory" in out
    # The matched pack has no backtick literals, so it doesn't contribute to promote
    assert "frobnicated" in out  # matched pack IS in the rubric
    # The promote header should mention the count (3 unique mandates from the floor)
    assert "3 injected mandate" in out
    # The TAIL lists each mandate's backtick literals only — never the full mandate text again
    # (re-emitting ~20 FLOOR lines verbatim doubled the rubric; wef 01M1QEY5, 2026-09-05).
    tail = out.split("# promote-to-check_*:", 1)[1].splitlines()[1:]
    tail = [line for line in tail if line.strip()]
    assert tail, "promote tail should list the literals"
    assert all(line.startswith("- `") for line in tail), tail
    assert not any(rr._MANDATE.search(line) for line in tail), tail


def test_promote_section_absent_when_no_greppable_mandates(tmp_path):
    """With NO greppable mandates (no backticked literals), the promote-to-check_*
    section is absent from the rubric."""
    rr = _load()
    # Build a tree where NONE of the mandate lines contains a backtick literal
    for floor_rel, mandate in [
        ("core/35-security-auth.md", "- Auth MUST use Pattern A."),
        ("core/25-data-postgres.md", "- Never use localhost as a DB host."),
        ("core/30-ops.md", "- Every compose service MUST declare memory limits."),
    ]:
        _mk_pack(tmp_path, floor_rel, ["**/nonexistent-floor-trigger-*.xyz"], [mandate])
    _mk_pack(
        tmp_path,
        "core/99-zzz-test.md",
        ["**/*.zzz"],
        ["- Files of type zzz MUST be frobnicated.", "- ⚠️ never defrobnicate in prod."],
    )
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "# promote-to-check_*:" not in out, "no promote section when no backtick content"


# ── Test 2: missing floor pack fallback ────────────────────────────────────────────


def test_missing_floor_pack_emits_marker_no_crash(tmp_path):
    """Delete one floor pack from the tmp tree → the rubric still emits (no crash)
    and carries the '(pack missing' marker for it."""
    _mk_tree(tmp_path)
    # Delete one of the three floor packs
    (tmp_path / ".windsurf" / "rules" / "core" / "35-security-auth.md").unlink()

    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)

    # No crash — output is non-empty
    assert out
    # The missing-pack marker is present
    assert "pack missing" in out
    assert "core/35-security-auth.md" in out
    # The other two floor packs are still present
    assert "core/25-data-postgres.md" in out
    assert "core/30-ops.md" in out
    # The matched pack still works
    assert "core/99-zzz-test.md" in out
    assert "MUST be frobnicated" in out


# ── Test 3: missing checklist fallback ─────────────────────────────────────────────


def test_missing_checklist_emits_marker_no_crash(tmp_path):
    """--workflow with the checklist file absent → '(checklist missing' marker, no crash."""
    _mk_tree(tmp_path)
    # Delete the mega checklist
    checklist = (
        tmp_path
        / "docs"
        / "orchestrator"
        / "mega-epic-breakdown"
        / "EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md"
    )
    checklist.unlink()

    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow="mega", root=tmp_path)

    assert out
    assert "checklist missing" in out
    # The other workflow (ettw) checklist is still present
    out2 = rr.build_rubric(["src/thing.zzz"], workflow="ettw", root=tmp_path)
    assert "checklist missing" not in out2
    assert "4-stage lifecycle" in out2


# ── Test 4: CLI exit codes ─────────────────────────────────────────────────────────


def test_cli_changed_project_root_exits_zero_and_prints_rubric(tmp_path):
    """Running the script via subprocess `python scripts/review_rubric.py
    --changed x.zzz --project-root <tmp>` exits 0 and prints the rubric."""
    _mk_tree(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "review_rubric.py"),
            "--changed",
            "x.zzz",
            "--project-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "REVIEW RUBRIC" in result.stdout
    assert "FLOOR" in result.stdout
    assert "core/99-zzz-test.md" in result.stdout  # matched pack for x.zzz
    assert "MUST be frobnicated" in result.stdout
    assert "12-FACTOR" in result.stdout


def test_cli_workflow_bogus_exits_nonzero(tmp_path):
    """`--workflow bogus` exits nonzero because 'bogus' is not a valid choice
    (argparse rejects it before any rubric is built)."""
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "review_rubric.py"),
            "--changed",
            "x.zzz",
            "--project-root",
            str(tmp_path),
            "--workflow",
            "bogus",
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode != 0, (
        f"expected non-zero exit for bogus workflow; stdout: {result.stdout}"
    )


def test_conditional_sections_excluded_from_mandates(tmp_path):
    """A mandate under a heading marked legacy/migration-only/deprecated/retired is NOT
    injected (F1: dual-pattern packs must not arm reviewers with retired rules), while the
    unmarked default section's mandate IS."""
    _mk_tree(tmp_path)
    p = tmp_path / ".windsurf" / "rules" / "core" / "96-dual.md"
    p.write_text(
        '---\nactivation: glob\nglobs: ["**/*.zzz"]\ndescription: dual pack\n---\n\n'
        "# dual\n\n## Default way\n\n- New code MUST use the default path.\n\n"
        "### Old way (legacy / migration-only)\n\n- Old code MUST use the retired path.\n\n"
        "## Another core section\n\n- Everything MUST be logged.\n",
        encoding="utf-8",
    )
    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "MUST use the default path" in out
    assert "MUST be logged" in out  # skipping ENDS when a same-or-higher heading follows
    assert "retired path" not in out  # the legacy section never arms a reviewer


def test_letter_suffixed_checklist_items_injected(tmp_path):
    """84a.-style sub-items are checklist items too (F2)."""
    _mk_tree(tmp_path)
    f = (
        tmp_path
        / "docs"
        / "orchestrator"
        / "mega-epic-breakdown"
        / "EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md"
    )
    f.write_text(
        "# Mega checklist\n\n84. Does it persist?\n84a. Does the mirror persist too?\n",
        encoding="utf-8",
    )
    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow="mega", root=tmp_path)
    assert "84. Does it persist?" in out
    assert "84a. Does the mirror persist too?" in out


def test_nested_conditional_heading_does_not_end_outer_skip(tmp_path):
    """A conditional section containing a NESTED conditional heading stays fully skipped —
    the inner heading must not deepen the skip boundary (regression: outer-skip early exit)."""
    _mk_tree(tmp_path)
    p = tmp_path / ".windsurf" / "rules" / "core" / "95-nested.md"
    p.write_text(
        '---\nactivation: glob\nglobs: ["**/*.zzz"]\ndescription: nested\n---\n\n'
        "# nested\n\n# Legacy Features (legacy)\n\n## Old Subsystem\n\n- Old MUST stay.\n\n"
        "### Deprecated API (deprecated)\n\n- Older MUST stay too.\n\n"
        "## Still Inside Legacy\n\n- Inner MUST never leak.\n\n"
        "# Core\n\n- Core MUST be emitted.\n",
        encoding="utf-8",
    )
    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "Old MUST stay" not in out
    assert "Older MUST stay too" not in out
    assert "Inner MUST never leak" not in out  # the leak the fix prevents
    assert "Core MUST be emitted" in out  # skip ends at the next top-level heading


def test_non_legacy_heading_not_skipped(tmp_path):
    """'Non-legacy' in a heading must NOT trigger the conditional skip (word-boundary +
    lookbehind regression)."""
    _mk_tree(tmp_path)
    p = tmp_path / ".windsurf" / "rules" / "core" / "94-nonlegacy.md"
    p.write_text(
        '---\nactivation: glob\nglobs: ["**/*.zzz"]\ndescription: nonlegacy\n---\n\n'
        "# nonlegacy\n\n## Non-legacy Features\n\n- Core MUST be armed.\n",
        encoding="utf-8",
    )
    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "Core MUST be armed" in out


def test_fenced_code_never_parsed_as_headings_or_mandates(tmp_path):
    """Fence interior is invisible: a `# MUST` code comment must not close a conditional skip
    (leak), and a BANNED example line must not be injected as a mandate (noise)."""
    _mk_tree(tmp_path)
    p = tmp_path / ".windsurf" / "rules" / "core" / "93-fenced.md"
    p.write_text(
        '---\nactivation: glob\nglobs: ["**/*.zzz"]\ndescription: fenced\n---\n\n'
        "# fenced\n\n## Legacy example (legacy)\n\n```python\n# MUST never do this in new code\n"
        "old_call()\n```\n\n- Legacy MUST hide.\n\n## Real\n\n"
        '```python\nSECRET = "x"  # BANNED example\n```\n\n- Real MUST show.\n',
        encoding="utf-8",
    )
    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "Legacy MUST hide" not in out  # the fence-comment no longer ends the skip
    assert "Real MUST show" in out
    assert "BANNED example" not in out  # code-sample lines are not mandates


def test_tilde_fences_tracked_like_backticks(tmp_path):
    """~~~ fences are fences too (CommonMark) — their interior never leaks or injects."""
    _mk_tree(tmp_path)
    p = tmp_path / ".windsurf" / "rules" / "core" / "92-tilde.md"
    p.write_text(
        '---\nactivation: glob\nglobs: ["**/*.zzz"]\ndescription: tilde\n---\n\n'
        "# tilde\n\n## Legacy example (legacy)\n\n~~~python\n# MUST never do this\nold()\n~~~\n\n"
        "- Legacy MUST hide.\n\n## Real\n\n- Real MUST show.\n",
        encoding="utf-8",
    )
    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "Legacy MUST hide" not in out
    assert "Real MUST show" in out


def test_unclosed_fence_surfaces_malformed_pack_warning(tmp_path):
    """An unclosed fence must not SILENTLY starve the rubric — the anomaly is surfaced in
    the rubric output itself so the armed reviewer sees the gap."""
    _mk_tree(tmp_path)
    p = tmp_path / ".windsurf" / "rules" / "core" / "91-unclosed.md"
    p.write_text(
        '---\nactivation: glob\nglobs: ["**/*.zzz"]\ndescription: unclosed\n---\n\n'
        "# unclosed\n\n```python\nstray()\n\n## Real\n\n- Real MUST show.\n",
        encoding="utf-8",
    )
    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "MALFORMED PACK" in out  # loud, in-band
    assert "Real MUST show" not in out  # (still swallowed — but no longer silently)


def test_literal_other_delimiter_inside_fence_is_content(tmp_path):
    """A literal ~~~ inside a ```-opened fence is example CONTENT — it must not close the
    fence (delimiter-matched toggling), so the outer skip survives and later core mandates
    emit with no false malformed-pack report."""
    _mk_tree(tmp_path)
    p = tmp_path / ".windsurf" / "rules" / "core" / "90-mixed.md"
    p.write_text(
        '---\nactivation: glob\nglobs: ["**/*.zzz"]\ndescription: mixed\n---\n\n'
        "# mixed\n\n## Legacy (legacy)\n\n```python\nold_call()\n~~~\n# MUST hide comment\n```\n\n"
        "- Legacy MUST hide.\n\n## Real\n\n- Real MUST show.\n",
        encoding="utf-8",
    )
    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "Legacy MUST hide" not in out  # skip survived the literal ~~~
    assert "Real MUST show" in out  # core mandate not swallowed
    assert "MALFORMED PACK" not in out  # fences ARE balanced — no false report


def test_longer_fence_nests_literal_shorter_fence(tmp_path):
    """A ````-opened block showing a literal ``` example (the standard CommonMark nesting
    trick) must not close early, mis-swallow later core mandates, or false-report MALFORMED."""
    _mk_tree(tmp_path)
    p = tmp_path / ".windsurf" / "rules" / "core" / "89-quadfence.md"
    p.write_text(
        '---\nactivation: glob\nglobs: ["**/*.zzz"]\ndescription: quad\n---\n\n'
        "# quad\n\n## Legacy (legacy)\n\n````markdown\nExample of a fence:\n```\n"
        "- SNEAKY MUST leak here?\n````\n\n- Legacy MUST hide.\n\n## Real\n\n- Real MUST show.\n",
        encoding="utf-8",
    )
    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "SNEAKY" not in out
    assert "Legacy MUST hide" not in out
    assert "Real MUST show" in out
    assert "MALFORMED PACK" not in out


# ── Wrapped-bullet joining (wef 01M1QEY5: a mandate cut before its condition) ─────────────────
def _lines(body: str):
    return _load()._mandate_lines(body)


def test_wrapped_bullet_is_joined_to_its_continuation():
    assert _lines(
        "- Use `Settings` — never raw `os.getenv` **for an\n  application setting**.\n"
    ) == ["- Use `Settings` — never raw `os.getenv` **for an application setting**."]


def test_heading_fence_and_numbered_item_end_a_bullet():
    """Text after a heading, after a fenced example, or a `1.` item is NEW content — folding it
    into the previous bullet fabricates a mandate that no pack line says."""
    assert _lines("- MUST do X\n## Next\nplain text\n") == ["- MUST do X"]
    assert _lines("- MUST do X\n```\ncode\n```\ntrailing text\n") == ["- MUST do X"]
    assert _lines("- MUST do X\n1. then a numbered step\n") == ["- MUST do X"]


def test_join_cap_marks_instead_of_silently_cutting():
    rr = _load()
    body = "- MUST do X\n" + "".join(f"more {i}\n" for i in range(rr._JOIN_CAP + 3))
    (line,) = _lines(body)
    assert line.endswith(rr._JOIN_MARK)
    assert f"more {rr._JOIN_CAP - 1}" in line and f"more {rr._JOIN_CAP}" not in line


def test_promote_tail_never_cuts_a_literal():
    rr = _load()
    line = "- MUST use " + " ".join(f"`literal-{i}-{'x' * 50}`" for i in range(5))
    out = rr._literals(line)
    assert len(out) <= rr._LITERALS_CAP
    for lit in out.split(" "):
        assert lit.startswith("`") and lit.endswith("`"), lit
    assert out.count("`") % 2 == 0
